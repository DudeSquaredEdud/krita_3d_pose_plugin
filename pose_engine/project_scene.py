"""
Project Scene - Scene Persistence with Auto-Save
=================================================

Manages scene persistence tied to Krita projects.
Provides auto-save with diff-based serialization to minimize file I/O.

Features:
- Automatic scene loading/saving tied to Krita projects
- Rolling debounce auto-save (5s idle / 60s continuous)
- Diff-based serialization to only save what changed
- Full export for sharing/backups
- Camera bookmarks integration
"""

import os
import json
import hashlib
import copy
from datetime import datetime
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass, field
from pathlib import Path

from PyQt5.QtCore import QObject, pyqtSignal, QTimer

from .scene import Scene
from .model_instance import ModelInstance
from .vec3 import Vec3
from .quat import Quat


@dataclass
class SceneSettings:
    """Settings for scene auto-save behavior."""
    # Auto-save timing
    idle_save_delay: float = 5.0  # Seconds after last change
    continuous_save_interval: float = 60.0  # Maximum time between saves during changes
    
    # File management
    max_backup_files: int = 5  # Number of backup files to keep
    compress_output: bool = False  # Whether to compress saved scenes
    
    # Diff settings
    enable_diff_save: bool = True  # Only save changes since last save


@dataclass 
class SceneMetadata:
    """Metadata about a saved scene."""
    name: str = "Untitled Scene"
    created_at: datetime = field(default_factory=datetime.now)
    modified_at: datetime = field(default_factory=datetime.now)
    version: str = "1.0"
    krita_project: Optional[str] = None  # Associated Krita project path
    checksum: str = ""  # Hash of last saved state


class ProjectScene(QObject):
    """
    Manages scene persistence with auto-save functionality.

    This class wraps a Scene object and provides:
    - Automatic saving when changes occur (with debouncing)
    - Loading/saving scenes tied to Krita projects
    - Diff-based serialization to minimize file I/O
    - Full scene export for sharing
    - Camera bookmarks integration

    Signals:
    scene_saved: Emitted when scene is saved
    scene_loaded: Emitted when scene is loaded
    save_error: Emitted when save fails
    load_error: Emitted when load fails
    bookmarks_loaded: Emitted when camera bookmarks are loaded
    """

    # Signals
    scene_saved = pyqtSignal(str) # file_path
    scene_loaded = pyqtSignal(str) # file_path
    save_error = pyqtSignal(str) # error_message
    load_error = pyqtSignal(str) # error_message
    scene_changed = pyqtSignal() # Emitted when scene is modified
    auto_save_triggered = pyqtSignal()
    bookmarks_loaded = pyqtSignal(dict) # bookmarks data
    
    # Scene file extension
    SCENE_EXTENSION = ".k3dscene"
    
    def __init__(self, scene: Optional[Scene] = None, parent=None):
        """
        Initialize the project scene manager.
        
        Args:
            scene: The Scene object to manage (creates new if None)
            parent: QObject parent
        """
        super().__init__(parent)

        self._scene = scene or Scene()
        self._settings = SceneSettings()
        self._metadata = SceneMetadata()
        self._camera_bookmarks: Dict[str, dict] = {}  # Project-specific camera bookmarks
        
        # State tracking
        self._last_saved_state: Optional[Dict[str, Any]] = None
        self._last_save_time: Optional[datetime] = None
        self._has_unsaved_changes = False
        self._change_count = 0  # For tracking continuous changes
        
        # File paths
        self._scene_file_path: Optional[str] = None
        self._krita_project_path: Optional[str] = None
        
        # Auto-save timers
        self._idle_timer = QTimer(self)
        self._idle_timer.setSingleShot(True)
        self._idle_timer.timeout.connect(self._on_idle_save)
        
        self._continuous_timer = QTimer(self)
        self._continuous_timer.timeout.connect(self._on_continuous_save)
        
        # Track current state hash for diff detection
        self._current_state_hash: str = ""
        
    # -------------------------------------------------------------------------
    # Properties
    # -------------------------------------------------------------------------
    
    @property
    def scene(self) -> Scene:
        """Get the managed Scene object."""
        return self._scene
    
    @property
    def has_unsaved_changes(self) -> bool:
        """Check if there are unsaved changes."""
        return self._has_unsaved_changes
    
    @property
    def scene_file_path(self) -> Optional[str]:
        """Get the current scene file path."""
        return self._scene_file_path
    
    @property
    def krita_project_path(self) -> Optional[str]:
        """Get the associated Krita project path."""
        return self._krita_project_path
    
    @property
    def settings(self) -> SceneSettings:
        """Get scene settings."""
        return self._settings
    
    @settings.setter
    def settings(self, value: SceneSettings):
        """Set scene settings."""
        self._settings = value
        self._update_timers()
        
    # -------------------------------------------------------------------------
    # Change Tracking
    # -------------------------------------------------------------------------
    
    def mark_changed(self):
        """
        Mark the scene as having changes.
        
        Should be called after any modification to the scene:
        - Model added/removed
        - Bone transform changed
        - Camera bookmark added/removed
        - Model visibility changed
        """
        self._has_unsaved_changes = True
        self._change_count += 1
        self._metadata.modified_at = datetime.now()
        
        # Restart idle timer
        self._idle_timer.start(int(self._settings.idle_save_delay * 1000))
        
        # Start continuous timer if not running
        if not self._continuous_timer.isActive():
            self._continuous_timer.start(int(self._settings.continuous_save_interval * 1000))
        
        self.scene_changed.emit()
    
    def _update_timers(self):
        """Update timer intervals from settings."""
        self._idle_timer.setInterval(int(self._settings.idle_save_delay * 1000))
        self._continuous_timer.setInterval(int(self._settings.continuous_save_interval * 1000))
    
    # -------------------------------------------------------------------------
    # Auto-Save Handlers
    # -------------------------------------------------------------------------
    
    def _on_idle_save(self):
        """Handle idle timer timeout - save if changes exist."""
        if self._has_unsaved_changes and self._scene_file_path:
            self._do_auto_save("idle")
    
    def _on_continuous_save(self):
        """Handle continuous timer timeout - save if changes exist."""
        if self._has_unsaved_changes and self._scene_file_path:
            self._do_auto_save("continuous")
    
    def _do_auto_save(self, trigger: str):
        """Perform the actual auto-save."""
        if not self._scene_file_path:
            return
            
        try:
            self.save(self._scene_file_path, create_backup=True)
            self._change_count = 0
            self.auto_save_triggered.emit()
            print(f"[ProjectScene] Auto-saved ({trigger} trigger)")
        except Exception as e:
            self.save_error.emit(f"Auto-save failed: {e}")
            print(f"[ProjectScene] Auto-save failed: {e}")
    
    # -------------------------------------------------------------------------
    # Serialization with Diff Support
    # -------------------------------------------------------------------------
    
    def _compute_state_hash(self, state: Dict[str, Any]) -> str:
        """Compute a hash of the state for change detection."""
        state_str = json.dumps(state, sort_keys=True)
        return hashlib.md5(state_str.encode()).hexdigest()
    
    def _get_current_state(self) -> Dict[str, Any]:
        """Get the current scene state as a dictionary."""
        return self._scene.to_dict()
    
    def _compute_diff(self, current: Dict[str, Any], previous: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compute the difference between two scene states.
        
        Returns a dictionary containing only the changed parts.
        """
        diff = {
            'version': current.get('version'),
            'timestamp': datetime.now().isoformat(),
            'changes': {}
        }
        
        # Check models
        current_models = current.get('models', {})
        previous_models = previous.get('models', {})
        
        # Added models
        for model_id in current_models:
            if model_id not in previous_models:
                diff['changes'][model_id] = {'action': 'added', 'data': current_models[model_id]}
        
        # Removed models
        for model_id in previous_models:
            if model_id not in current_models:
                diff['changes'][model_id] = {'action': 'removed'}
        
        # Modified models
        for model_id in current_models:
            if model_id in previous_models:
                current_model = current_models[model_id]
                previous_model = previous_models[model_id]
                
                model_diff = self._diff_model(current_model, previous_model)
                if model_diff:
                    diff['changes'][model_id] = {'action': 'modified', 'data': model_diff}
        
        # Check selection
        if current.get('selected_model_id') != previous.get('selected_model_id'):
            diff['selected_model_id'] = current.get('selected_model_id')
        if current.get('selected_bone_name') != previous.get('selected_bone_name'):
            diff['selected_bone_name'] = current.get('selected_bone_name')
        
        return diff if diff['changes'] or 'selected_model_id' in diff or 'selected_bone_name' in diff else None
    
    def _diff_model(self, current: Dict[str, Any], previous: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Compute diff between two model states."""
        diff = {}
        
        # Check transform
        current_transform = current.get('transform', {})
        previous_transform = previous.get('transform', {})
        
        if current_transform != previous_transform:
            diff['transform'] = current_transform
        
        # Check visibility
        if current.get('visible') != previous.get('visible'):
            diff['visible'] = current.get('visible')
        
        # Check bones
        current_bones = current.get('bones', {})
        previous_bones = previous.get('bones', {})
        
        bone_changes = {}
        for bone_name in set(current_bones.keys()) | set(previous_bones.keys()):
            if bone_name not in current_bones:
                bone_changes[bone_name] = {'action': 'removed'}
            elif bone_name not in previous_bones:
                bone_changes[bone_name] = {'action': 'added', 'data': current_bones[bone_name]}
            elif current_bones[bone_name] != previous_bones[bone_name]:
                bone_changes[bone_name] = {'action': 'modified', 'data': current_bones[bone_name]}
        
        if bone_changes:
            diff['bones'] = bone_changes
        
        # Check parent relationship
        if current.get('parent_id') != previous.get('parent_id'):
            diff['parent_id'] = current.get('parent_id')
        if current.get('parent_bone') != previous.get('parent_bone'):
            diff['parent_bone'] = current.get('parent_bone')
        
        return diff if diff else None
    
    # -------------------------------------------------------------------------
    # Save Operations
    # -------------------------------------------------------------------------
    
    def save(self, file_path: Optional[str] = None, create_backup: bool = False) -> bool:
        """
        Save the scene to a file.

        Args:
            file_path: Path to save to (uses current path if None)
            create_backup: Whether to create a backup of existing file

        Returns:
            True if successful
        """
        if file_path is None:
            file_path = self._scene_file_path

        if not file_path:
            self.save_error.emit("No file path specified")
            return False

        # Ensure file has correct extension
        if not file_path.endswith(self.SCENE_EXTENSION):
            file_path = file_path + self.SCENE_EXTENSION

        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # Create backup if requested
            if create_backup and os.path.exists(file_path):
                self._create_backup(file_path)
            
            # Get current state
            current_state = self._get_current_state()
    
            # Add metadata
            save_data = {
                'metadata': {
                    'name': self._metadata.name,
                    'created_at': self._metadata.created_at.isoformat(),
                    'modified_at': datetime.now().isoformat(),
                    'version': self._metadata.version,
                    'krita_project': self._krita_project_path,
                },
                'scene': current_state,
                'camera_bookmarks': self._camera_bookmarks
            }
            
            # Write to file
            with open(file_path, 'w') as f:
                json.dump(save_data, f, indent=2)
            
            # Update state tracking
            self._last_saved_state = copy.deepcopy(current_state)
            self._last_save_time = datetime.now()
            self._has_unsaved_changes = False
            self._current_state_hash = self._compute_state_hash(current_state)
            self._scene_file_path = file_path
            
            # Stop timers
            self._idle_timer.stop()
            self._continuous_timer.stop()
            
            self.scene_saved.emit(file_path)
            return True
            
        except Exception as e:
            self.save_error.emit(str(e))
            return False
    
    def save_for_krita_project(self, krita_project_path: str) -> bool:
        """
        Save the scene alongside a Krita project.
        
        The scene file is saved in the same directory as the Krita project
        with the same base name but .k3dscene extension.
        
        Args:
            krita_project_path: Path to the Krita project file
            
        Returns:
            True if successful
        """
        # Generate scene file path
        base_name = os.path.splitext(os.path.basename(krita_project_path))[0]
        scene_dir = os.path.dirname(krita_project_path)
        scene_path = os.path.join(scene_dir, base_name + self.SCENE_EXTENSION)
        
        self._krita_project_path = krita_project_path
        self._metadata.krita_project = krita_project_path
        self._metadata.name = base_name
        
        return self.save(scene_path, create_backup=True)
    
    def _create_backup(self, file_path: str):
        """Create a backup of the existing file."""
        if not os.path.exists(file_path):
            return
            
        # Generate backup filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = os.path.join(os.path.dirname(file_path), 'backups')
        os.makedirs(backup_dir, exist_ok=True)
        
        base_name = os.path.basename(file_path)
        backup_name = f"{os.path.splitext(base_name)[0]}_{timestamp}{self.SCENE_EXTENSION}"
        backup_path = os.path.join(backup_dir, backup_name)
        
        # Copy current file to backup
        import shutil
        shutil.copy2(file_path, backup_path)
        
        # Clean up old backups
        self._cleanup_backups(backup_dir)
    
    def _cleanup_backups(self, backup_dir: str):
        """Remove old backup files, keeping only the most recent."""
        if not os.path.exists(backup_dir):
            return
            
        # Get all backup files
        backups = []
        for f in os.listdir(backup_dir):
            if f.endswith(self.SCENE_EXTENSION):
                full_path = os.path.join(backup_dir, f)
                backups.append((full_path, os.path.getmtime(full_path)))
        
        # Sort by modification time (newest first)
        backups.sort(key=lambda x: x[1], reverse=True)
        
        # Remove excess backups
        for backup_path, _ in backups[self._settings.max_backup_files:]:
            try:
                os.remove(backup_path)
            except Exception as e:
                print(f"[ProjectScene] Failed to remove old backup {backup_path}: {e}")
    
    # -------------------------------------------------------------------------
    # Load Operations
    # -------------------------------------------------------------------------
    
    def load(self, file_path: str) -> bool:
        """
        Load a scene from a file.
        
        Args:
            file_path: Path to the scene file
            
        Returns:
            True if successful
        """
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            # Load metadata
            if 'metadata' in data:
                meta = data['metadata']
                self._metadata.name = meta.get('name', 'Untitled Scene')
                if 'created_at' in meta:
                    self._metadata.created_at = datetime.fromisoformat(meta['created_at'])
                if 'modified_at' in meta:
                    self._metadata.modified_at = datetime.fromisoformat(meta['modified_at'])
                self._metadata.version = meta.get('version', '1.0')
                self._krita_project_path = meta.get('krita_project')
            
            # Load scene
            if 'scene' in data:
                scene_data = data['scene']
            else:
                # Legacy format without metadata wrapper
                scene_data = data

            # Get base path for resolving relative file paths
            base_path = os.path.dirname(file_path)
            self._scene.from_dict(scene_data, base_path)

            # Load camera bookmarks
            if 'camera_bookmarks' in data:
                self._camera_bookmarks = data['camera_bookmarks']
                self.bookmarks_loaded.emit(self._camera_bookmarks)

            # Update state tracking
            self._last_saved_state = copy.deepcopy(scene_data)
            self._last_save_time = datetime.now()
            self._has_unsaved_changes = False
            self._current_state_hash = self._compute_state_hash(scene_data)
            self._scene_file_path = file_path

            self.scene_loaded.emit(file_path)
            return True
            
        except Exception as e:
            self.load_error.emit(str(e))
            return False
    
    def load_for_krita_project(self, krita_project_path: str) -> bool:
        """
        Load the scene associated with a Krita project.
        
        Args:
            krita_project_path: Path to the Krita project file
            
        Returns:
            True if scene was found and loaded, False if no scene exists
        """
        # Generate expected scene file path
        base_name = os.path.splitext(os.path.basename(krita_project_path))[0]
        scene_dir = os.path.dirname(krita_project_path)
        scene_path = os.path.join(scene_dir, base_name + self.SCENE_EXTENSION)
        
        if os.path.exists(scene_path):
            return self.load(scene_path)
        else:
            # No existing scene - create new one
            self._krita_project_path = krita_project_path
            self._metadata.krita_project = krita_project_path
            self._metadata.name = base_name
            self._scene_file_path = scene_path
            return False
    
    # -------------------------------------------------------------------------
    # Export Operations
    # -------------------------------------------------------------------------
    
    def export_full(self, export_path: str, include_models: bool = True) -> bool:
        """
        Export the scene with all model data for sharing/backup.
        
        This creates a self-contained export that includes:
        - Scene configuration
        - Camera bookmarks
        - Model files (copied into export)
        
        Args:
            export_path: Path for the export file/directory
            include_models: Whether to copy model files into export
            
        Returns:
            True if successful
        """
        try:
            # Create export directory
            export_dir = os.path.splitext(export_path)[0] + '_export'
            os.makedirs(export_dir, exist_ok=True)
            
            # Copy model files
            model_mapping = {}  # original_path -> export_path
            if include_models:
                models_dir = os.path.join(export_dir, 'models')
                os.makedirs(models_dir, exist_ok=True)
                
                for model in self._scene.get_all_models():
                    if model.source_file and os.path.exists(model.source_file):
                        # Copy model file
                        model_name = os.path.basename(model.source_file)
                        export_model_path = os.path.join(models_dir, model_name)
                        
                        import shutil
                        shutil.copy2(model.source_file, export_model_path)
                        
                        # Store relative path for manifest
                        model_mapping[model.source_file] = f"models/{model_name}"
            
            # Create manifest
            manifest = {
                'version': '1.0',
                'exported_at': datetime.now().isoformat(),
                'metadata': {
                    'name': self._metadata.name,
                    'krita_project': self._metadata.krita_project,
                },
                'scene': self._scene.to_dict(),
                'model_files': model_mapping,
            }
            
            # Update source paths to be relative
            for model_id, model_data in manifest['scene'].get('models', {}).items():
                original_path = model_data.get('source_file')
                if original_path in model_mapping:
                    model_data['source_file'] = model_mapping[original_path]
            
            # Write manifest
            manifest_path = os.path.join(export_dir, 'manifest.json')
            with open(manifest_path, 'w') as f:
                json.dump(manifest, f, indent=2)
            
            # Create zip archive
            import shutil
            archive_path = shutil.make_archive(
                export_path.replace('.zip', ''),
                'zip',
                export_dir
            )
            
            print(f"[ProjectScene] Exported to {archive_path}")
            return True
            
        except Exception as e:
            self.save_error.emit(f"Export failed: {e}")
            return False
    
    def import_full(self, import_path: str) -> bool:
        """
        Import a full scene export.
        
        Args:
            import_path: Path to the export archive
            
        Returns:
            True if successful
        """
        try:
            import tempfile
            import shutil
            
            # Extract archive
            extract_dir = tempfile.mkdtemp()
            shutil.unpack_archive(import_path, extract_dir)
            
            # Load manifest
            manifest_path = os.path.join(extract_dir, 'manifest.json')
            with open(manifest_path, 'r') as f:
                manifest = json.load(f)
            
            # Update model paths to absolute
            for model_id, model_data in manifest['scene'].get('models', {}).items():
                source_file = model_data.get('source_file')
                if source_file and source_file.startswith('models/'):
                    model_data['source_file'] = os.path.join(extract_dir, source_file)
            
            # Load scene
            self._scene.from_dict(manifest['scene'], extract_dir)
            
            # Update metadata
            if 'metadata' in manifest:
                self._metadata.name = manifest['metadata'].get('name', 'Imported Scene')
                self._krita_project_path = manifest['metadata'].get('krita_project')
            
            self._has_unsaved_changes = True
            self.mark_changed()
            
            # Cleanup temp directory
            shutil.rmtree(extract_dir, ignore_errors=True)
            
            return True
            
        except Exception as e:
            self.load_error.emit(f"Import failed: {e}")
            return False
    
    # -------------------------------------------------------------------------
    # New Scene
    # -------------------------------------------------------------------------
    
    def new_scene(self):
        """Clear the scene to an empty state.
        
        Note: This clears the existing scene object rather than creating a new one,
        so that external references (like the viewport) remain valid.
        """
        # Clear all models from the scene
        self._scene._models.clear()
        self._scene._model_order.clear()
        self._scene._selected_model_id = None
        self._scene._selected_bone_name = None
        
        # Reset metadata
        self._metadata = SceneMetadata()
        self._last_saved_state = None
        self._last_save_time = None
        self._has_unsaved_changes = False
        self._scene_file_path = None
        self._krita_project_path = None
        self._camera_bookmarks = {}

        # Stop timers
        self._idle_timer.stop()
        self._continuous_timer.stop()

        self.scene_changed.emit()

    # -------------------------------------------------------------------------
    # Camera Bookmarks
    # -------------------------------------------------------------------------

    def set_camera_bookmarks(self, bookmarks: Dict[str, dict]) -> None:
        """
        Set the camera bookmarks for this scene.

        Args:
            bookmarks: Dictionary of bookmark slot -> bookmark data
        """
        self._camera_bookmarks = bookmarks
        self.mark_changed()

    def get_camera_bookmarks(self) -> Dict[str, dict]:
        """
        Get the camera bookmarks for this scene.

        Returns:
            Dictionary of bookmark slot -> bookmark data
        """
        return self._camera_bookmarks.copy()

    def update_camera_bookmark(self, slot: int, bookmark_data: dict) -> None:
        """
        Update a single camera bookmark.

        Args:
            slot: Bookmark slot number (1-9)
            bookmark_data: Bookmark data dictionary
        """
        self._camera_bookmarks[str(slot)] = bookmark_data
        self.mark_changed()

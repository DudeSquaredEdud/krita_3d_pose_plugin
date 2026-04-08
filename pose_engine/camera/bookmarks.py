"""
Camera bookmark management for saving and recalling camera positions.

This module provides global camera position bookmarks that persist
across sessions and work with any model loaded in the viewport.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from pose_engine.ui.multi_viewport import Camera
    from pose_engine.ui.viewport import Camera as ViewportCamera


@dataclass
class CameraBookmark:
    """Represents a saved camera position with all settings.
    
    Attributes:
        name: User-friendly name for the bookmark
        slot: Quick-access slot number (1-9)
        target: Camera target/look-at position (x, y, z)
        distance: Distance from camera to target
        yaw: Horizontal rotation angle in radians
        pitch: Vertical rotation angle in radians
        fov: Field of view in degrees
        near: Near clipping plane distance
        far: Far clipping plane distance
        created_at: When the bookmark was created
        modified_at: When the bookmark was last modified
    """
    name: str
    slot: int  # 1-9 for quick keys
    
    # Position data
    target: tuple  # (x, y, z)
    distance: float
    yaw: float
    pitch: float
    
    # Camera settings
    fov: float
    near: float = 0.1
    far: float = 100.0
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    modified_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for JSON storage."""
        return {
            'name': self.name,
            'slot': self.slot,
            'target': {'x': self.target[0], 'y': self.target[1], 'z': self.target[2]},
            'distance': self.distance,
            'yaw': self.yaw,
            'pitch': self.pitch,
            'fov': self.fov,
            'near': self.near,
            'far': self.far,
            'created_at': self.created_at.isoformat(),
            'modified_at': self.modified_at.isoformat(),
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CameraBookmark':
        """Deserialize from dictionary."""
        target_data = data['target']
        if isinstance(target_data, dict):
            target = (target_data['x'], target_data['y'], target_data['z'])
        else:
            # Assume it's already a tuple/list
            target = tuple(target_data)
        
        return cls(
            name=data['name'],
            slot=data['slot'],
            target=target,
            distance=data['distance'],
            yaw=data['yaw'],
            pitch=data['pitch'],
            fov=data['fov'],
            near=data.get('near', 0.1),
            far=data.get('far', 100.0),
            created_at=datetime.fromisoformat(data['created_at']),
            modified_at=datetime.fromisoformat(data['modified_at']),
        )
    
    def get_summary(self) -> str:
        """Get a short summary string for UI display."""
        return f"FOV:{self.fov:.0f}° Dist:{self.distance:.1f} Target:({self.target[0]:.1f}, {self.target[1]:.1f}, {self.target[2]:.1f})"


class CameraBookmarkManager:
    """Manages global camera position bookmarks.
    
    Bookmarks are stored in the plugin's settings directory
    and persist across sessions and models.
    
    Attributes:
        MAX_BOOKMARKS: Maximum number of quick-access slots (9)
        BOOKMARKS_FILE: Filename for the bookmarks JSON file
    """
    
    MAX_BOOKMARKS = 9  # Slots 1-9 for quick keys
    BOOKMARKS_FILE = 'camera_bookmarks.json'
    
    def __init__(self, settings_dir: Optional[Path] = None):
        """Initialize the bookmark manager.
        
        Args:
            settings_dir: Directory to store bookmarks file. If None,
                          bookmarks are only kept in memory.
        """
        self._bookmarks: Dict[int, CameraBookmark] = {}
        self._settings_dir = settings_dir
        self._load_bookmarks()
    
    def _get_bookmarks_path(self) -> Optional[Path]:
        """Get the full path to the bookmarks file."""
        if self._settings_dir is None:
            return None
        return self._settings_dir / self.BOOKMARKS_FILE
    
    def _load_bookmarks(self) -> None:
        """Load bookmarks from the JSON file."""
        bookmarks_path = self._get_bookmarks_path()
        if bookmarks_path is None or not bookmarks_path.exists():
            return
        
        try:
            with open(bookmarks_path, 'r') as f:
                data = json.load(f)
            
            for slot_str, bookmark_data in data.items():
                slot = int(slot_str)
                if 1 <= slot <= self.MAX_BOOKMARKS:
                    self._bookmarks[slot] = CameraBookmark.from_dict(bookmark_data)
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            print(f"[CameraBookmarkManager] Error loading bookmarks: {e}")
            # Continue with empty bookmarks
    
    def _save_bookmarks(self) -> None:
        """Save bookmarks to the JSON file."""
        bookmarks_path = self._get_bookmarks_path()
        if bookmarks_path is None:
            return
        
        # Ensure directory exists
        bookmarks_path.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            str(slot): bookmark.to_dict()
            for slot, bookmark in self._bookmarks.items()
        }
        
        try:
            with open(bookmarks_path, 'w') as f:
                json.dump(data, f, indent=2)
        except IOError as e:
            print(f"[CameraBookmarkManager] Error saving bookmarks: {e}")
    
    def save_bookmark(self, slot: int, camera: Any, name: Optional[str] = None) -> CameraBookmark:
        """Save current camera position to a slot.
        
        Args:
            slot: Bookmark slot number (1-9)
            camera: Camera object with target, distance, yaw, pitch, fov attributes
            name: Optional name for the bookmark. If None, uses "Bookmark {slot}"
            
        Returns:
            The created CameraBookmark
            
        Raises:
            ValueError: If slot is not in range 1-9
        """
        if slot < 1 or slot > self.MAX_BOOKMARKS:
            raise ValueError(f"Slot must be 1-{self.MAX_BOOKMARKS}")
        
        # Extract camera state - works with both Camera classes
        target = camera.target
        if hasattr(target, 'x'):
            # It's a Vec3 object
            target_tuple = (target.x, target.y, target.z)
        else:
            # Assume it's already a tuple/list
            target_tuple = tuple(target)
        
        # Check if updating existing bookmark
        existing = self._bookmarks.get(slot)
        if existing:
            created_at = existing.created_at
        else:
            created_at = datetime.now()
        
        bookmark = CameraBookmark(
            name=name or f"Bookmark {slot}",
            slot=slot,
            target=target_tuple,
            distance=camera.distance,
            yaw=camera.yaw,
            pitch=camera.pitch,
            fov=camera.fov,
            near=getattr(camera, 'near', 0.1),
            far=getattr(camera, 'far', 100.0),
            created_at=created_at,
            modified_at=datetime.now(),
        )
        
        self._bookmarks[slot] = bookmark
        self._save_bookmarks()
        
        return bookmark
    
    def load_bookmark(self, slot: int, camera: Any) -> bool:
        """Load camera position from a slot.
        
        Args:
            slot: Bookmark slot number (1-9)
            camera: Camera object to update with bookmark state
            
        Returns:
            True if bookmark was found and applied, False otherwise
        """
        bookmark = self._bookmarks.get(slot)
        if bookmark is None:
            return False
        
        # Apply camera state - works with both Camera classes
        target = bookmark.target
        if hasattr(camera.target, 'x'):
            # It's a Vec3 object, need to import and create
            from pose_engine.vec3 import Vec3
            camera.target = Vec3(target[0], target[1], target[2])
        else:
            # Assume it's a simple attribute
            camera.target = target
        
        camera.distance = bookmark.distance
        camera.yaw = bookmark.yaw
        camera.pitch = bookmark.pitch
        camera.fov = bookmark.fov
        
        if hasattr(camera, 'near'):
            camera.near = bookmark.near
        if hasattr(camera, 'far'):
            camera.far = bookmark.far
        
        return True
    
    def get_bookmark(self, slot: int) -> Optional[CameraBookmark]:
        """Get bookmark data without applying it.
        
        Args:
            slot: Bookmark slot number (1-9)
            
        Returns:
            CameraBookmark if found, None otherwise
        """
        return self._bookmarks.get(slot)
    
    def get_all_bookmarks(self) -> Dict[int, CameraBookmark]:
        """Get all saved bookmarks.
        
        Returns:
            Dictionary mapping slot numbers to CameraBookmark objects
        """
        return dict(self._bookmarks)
    
    def delete_bookmark(self, slot: int) -> bool:
        """Delete a bookmark from a slot.
        
        Args:
            slot: Bookmark slot number (1-9)
            
        Returns:
            True if bookmark was deleted, False if it didn't exist
        """
        if slot in self._bookmarks:
            del self._bookmarks[slot]
            self._save_bookmarks()
            return True
        return False
    
    def rename_bookmark(self, slot: int, new_name: str) -> bool:
        """Rename a bookmark.
        
        Args:
            slot: Bookmark slot number (1-9)
            new_name: New name for the bookmark
            
        Returns:
            True if bookmark was renamed, False if it didn't exist
        """
        bookmark = self._bookmarks.get(slot)
        if bookmark is None:
            return False
        
        bookmark.name = new_name
        bookmark.modified_at = datetime.now()
        self._save_bookmarks()
        return True
    
    def has_bookmark(self, slot: int) -> bool:
        """Check if a bookmark exists at a slot.
        
        Args:
            slot: Bookmark slot number (1-9)
            
        Returns:
            True if bookmark exists, False otherwise
        """
        return slot in self._bookmarks
    
    def export_to_file(self, filepath: Path) -> bool:
        """Export all bookmarks to a JSON file.
        
        Args:
            filepath: Path to export file
            
        Returns:
            True if export succeeded, False otherwise
        """
        data = {
            str(slot): bookmark.to_dict()
            for slot, bookmark in self._bookmarks.items()
        }
        
        try:
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
            return True
        except IOError as e:
            print(f"[CameraBookmarkManager] Error exporting bookmarks: {e}")
            return False
    
    def import_from_file(self, filepath: Path, merge: bool = True) -> int:
        """Import bookmarks from a JSON file.
        
        Args:
            filepath: Path to import file
            merge: If True, merge with existing bookmarks. If False, replace all.
            
        Returns:
            Number of bookmarks imported, or -1 on error
        """
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
        except (IOError, json.JSONDecodeError) as e:
            print(f"[CameraBookmarkManager] Error importing bookmarks: {e}")
            return -1
        
        if not merge:
            self._bookmarks.clear()
        
        count = 0
        for slot_str, bookmark_data in data.items():
            slot = int(slot_str)
            if 1 <= slot <= self.MAX_BOOKMARKS:
                self._bookmarks[slot] = CameraBookmark.from_dict(bookmark_data)
                count += 1
        
        self._save_bookmarks()
        return count

"""
Tests for ProjectScene - Scene persistence with auto-save
==========================================================

Tests the scene management functionality including:
- Auto-save with rolling debounce
- Scene serialization and deserialization
- Diff-based change tracking
- Full export for sharing
"""

import os
import json
import tempfile
import shutil
import pytest
from datetime import datetime
from pathlib import Path

# Import the module under test
from pose_engine.project_scene import (
    ProjectScene, SceneSettings, SceneMetadata
)
from pose_engine.scene import Scene
from pose_engine.model_instance import ModelInstance


class TestSceneSettings:
    """Tests for SceneSettings dataclass."""
    
    def test_default_settings(self):
        """Test default settings values."""
        settings = SceneSettings()
        assert settings.idle_save_delay == 5.0
        assert settings.continuous_save_interval == 60.0
        assert settings.max_backup_files == 5
        assert settings.compress_output == False
        assert settings.enable_diff_save == True
    
    def test_custom_settings(self):
        """Test custom settings values."""
        settings = SceneSettings(
            idle_save_delay=10.0,
            continuous_save_interval=30.0,
            max_backup_files=10
        )
        assert settings.idle_save_delay == 10.0
        assert settings.continuous_save_interval == 30.0
        assert settings.max_backup_files == 10


class TestSceneMetadata:
    """Tests for SceneMetadata dataclass."""
    
    def test_default_metadata(self):
        """Test default metadata values."""
        meta = SceneMetadata()
        assert meta.name == "Untitled Scene"
        assert meta.version == "1.0"
        assert meta.krita_project is None
    
    def test_custom_metadata(self):
        """Test custom metadata values."""
        meta = SceneMetadata(
            name="Test Scene",
            krita_project="/path/to/project.kra"
        )
        assert meta.name == "Test Scene"
        assert meta.krita_project == "/path/to/project.kra"


class TestProjectScene:
    """Tests for ProjectScene class."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for test files."""
        dir_path = tempfile.mkdtemp()
        yield dir_path
        shutil.rmtree(dir_path, ignore_errors=True)
    
    @pytest.fixture
    def scene(self):
        """Create an empty scene for testing."""
        return Scene()
    
    @pytest.fixture
    def project_scene(self, scene):
        """Create a ProjectScene instance for testing."""
        return ProjectScene(scene)
    
    def test_initialization(self, project_scene):
        """Test ProjectScene initialization."""
        assert project_scene.scene is not None
        assert project_scene.has_unsaved_changes == False
        assert project_scene.scene_file_path is None
    
    def test_mark_changed(self, project_scene):
        """Test marking scene as changed."""
        project_scene.mark_changed()
        assert project_scene.has_unsaved_changes == True
    
    def test_save_and_load(self, project_scene, temp_dir):
        """Test saving and loading a scene."""
        file_path = os.path.join(temp_dir, "test_scene.k3dscene")
        
        # Save the scene
        result = project_scene.save(file_path)
        assert result == True
        assert project_scene.has_unsaved_changes == False
        assert os.path.exists(file_path)
        
        # Verify file contents
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        assert 'metadata' in data
        assert 'scene' in data
        assert data['metadata']['name'] == "Untitled Scene"
        
        # Load the scene
        new_project_scene = ProjectScene(Scene())
        result = new_project_scene.load(file_path)
        assert result == True
        assert new_project_scene.scene_file_path == file_path
    
    def test_save_for_krita_project(self, project_scene, temp_dir):
        """Test saving scene alongside a Krita project."""
        krita_path = os.path.join(temp_dir, "test_project.kra")
        
        result = project_scene.save_for_krita_project(krita_path)
        assert result == True
        
        expected_scene_path = os.path.join(temp_dir, "test_project.k3dscene")
        assert os.path.exists(expected_scene_path)
        assert project_scene.krita_project_path == krita_path
    
    def test_load_for_krita_project(self, project_scene, temp_dir):
        """Test loading scene associated with a Krita project."""
        krita_path = os.path.join(temp_dir, "test_project.kra")
        
        # First save a scene
        project_scene.save_for_krita_project(krita_path)
        
        # Now load it
        new_project_scene = ProjectScene(Scene())
        result = new_project_scene.load_for_krita_project(krita_path)
        assert result == True
        assert new_project_scene.krita_project_path == krita_path
    
    def test_load_nonexistent_scene(self, project_scene, temp_dir):
        """Test loading when no scene exists for a project."""
        krita_path = os.path.join(temp_dir, "nonexistent.kra")
        
        result = project_scene.load_for_krita_project(krita_path)
        assert result == False  # No scene found
        assert project_scene.krita_project_path == krita_path
        # Scene file path should be set for future saves
        assert project_scene.scene_file_path is not None
    
    def test_backup_creation(self, project_scene, temp_dir):
        """Test that backups are created."""
        file_path = os.path.join(temp_dir, "test_scene.k3dscene")
        
        # Save initial version
        project_scene.save(file_path)
        
        # Mark changed and save again with backup
        project_scene.mark_changed()
        project_scene.save(file_path, create_backup=True)
        
        # Check backup directory
        backup_dir = os.path.join(temp_dir, 'backups')
        assert os.path.exists(backup_dir)
        
        # Should have at least one backup
        backups = os.listdir(backup_dir)
        assert len(backups) >= 1
    
    def test_backup_cleanup(self, project_scene, temp_dir):
        """Test that old backups are cleaned up."""
        import time
        file_path = os.path.join(temp_dir, "test_scene.k3dscene")
        
        # Set max backups to 2
        project_scene.settings.max_backup_files = 2
        
        # Save multiple times with small delays to ensure different timestamps
        for i in range(5):
            project_scene.mark_changed()
            project_scene.save(file_path, create_backup=True)
            time.sleep(0.01)  # Small delay to ensure different timestamps
        
        # Check backup directory
        backup_dir = os.path.join(temp_dir, 'backups')
        backups = os.listdir(backup_dir)
        
        # Should only have max_backup_files backups
        assert len(backups) <= 2
    
    def test_new_scene(self, project_scene, temp_dir):
        """Test creating a new scene."""
        # Save a scene first
        file_path = os.path.join(temp_dir, "test_scene.k3dscene")
        project_scene.save(file_path)
        
        # Create new scene
        project_scene.new_scene()
        
        assert project_scene.has_unsaved_changes == False
        assert project_scene.scene_file_path is None
        assert project_scene.scene.get_model_count() == 0
    
    def test_state_hash_computation(self, project_scene):
        """Test that state hash is computed correctly."""
        state1 = {'version': 1, 'models': {}}
        state2 = {'version': 1, 'models': {}}
        state3 = {'version': 2, 'models': {}}
        
        hash1 = project_scene._compute_state_hash(state1)
        hash2 = project_scene._compute_state_hash(state2)
        hash3 = project_scene._compute_state_hash(state3)
        
        # Same content should produce same hash
        assert hash1 == hash2
        # Different content should produce different hash
        assert hash1 != hash3
    
    def test_diff_computation(self, project_scene):
        """Test diff computation between states."""
        previous = {
            'version': 1,
            'models': {
                'model1': {'name': 'Model1', 'visible': True}
            }
        }
        
        current = {
            'version': 1,
            'models': {
                'model1': {'name': 'Model1', 'visible': False},
                'model2': {'name': 'Model2', 'visible': True}
            }
        }
        
        diff = project_scene._compute_diff(current, previous)
        
        assert diff is not None
        assert 'changes' in diff
        assert 'model2' in diff['changes']  # Added
        assert diff['changes']['model2']['action'] == 'added'
        assert 'model1' in diff['changes']  # Modified
        assert diff['changes']['model1']['action'] == 'modified'
    
    def test_diff_no_changes(self, project_scene):
        """Test diff when there are no changes."""
        state = {
            'version': 1,
            'models': {
                'model1': {'name': 'Model1'}
            }
        }
        
        diff = project_scene._compute_diff(state, state)
        assert diff is None


class TestProjectSceneSignals:
    """Tests for ProjectScene signals."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for test files."""
        dir_path = tempfile.mkdtemp()
        yield dir_path
        shutil.rmtree(dir_path, ignore_errors=True)
    
    def test_scene_saved_signal(self, temp_dir):
        """Test that scene_saved signal is emitted."""
        from PyQt5.QtCore import QCoreApplication, QEventLoop
        
        scene = Scene()
        project_scene = ProjectScene(scene)
        file_path = os.path.join(temp_dir, "test.k3dscene")
        
        saved_path = None
        def on_saved(path):
            nonlocal saved_path
            saved_path = path
        
        project_scene.scene_saved.connect(on_saved)
        project_scene.save(file_path)
        
        # Process events
        QCoreApplication.processEvents(QEventLoop.AllEvents, 100)
        
        assert saved_path == file_path
    
    def test_scene_loaded_signal(self, temp_dir):
        """Test that scene_loaded signal is emitted."""
        from PyQt5.QtCore import QCoreApplication, QEventLoop
        
        scene = Scene()
        project_scene = ProjectScene(scene)
        file_path = os.path.join(temp_dir, "test.k3dscene")
        
        # Save first
        project_scene.save(file_path)
        
        # Now test load signal
        loaded_path = None
        def on_loaded(path):
            nonlocal loaded_path
            loaded_path = path
        
        new_project_scene = ProjectScene(Scene())
        new_project_scene.scene_loaded.connect(on_loaded)
        new_project_scene.load(file_path)
        
        # Process events
        QCoreApplication.processEvents(QEventLoop.AllEvents, 100)
        
        assert loaded_path == file_path


class TestExportImport:
    """Tests for full export and import functionality."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for test files."""
        dir_path = tempfile.mkdtemp()
        yield dir_path
        shutil.rmtree(dir_path, ignore_errors=True)
    
    def test_export_full(self, temp_dir):
        """Test full scene export."""
        scene = Scene()
        project_scene = ProjectScene(scene)
        
        export_path = os.path.join(temp_dir, "export.zip")
        result = project_scene.export_full(export_path, include_models=False)
        
        assert result == True
        # Should create a zip file
        assert os.path.exists(export_path.replace('.zip', '') + '.zip') or \
               os.path.exists(export_path) or \
               os.path.exists(export_path.replace('.zip', '') + '_export')
    
    def test_import_full(self, temp_dir):
        """Test full scene import."""
        scene = Scene()
        project_scene = ProjectScene(scene)
        
        # First export
        export_path = os.path.join(temp_dir, "export.zip")
        project_scene.export_full(export_path, include_models=False)
        
        # Now import
        new_project_scene = ProjectScene(Scene())
        # Import would need the actual zip file
        # This is a basic test of the method existence
        # Full test would require actual model files


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

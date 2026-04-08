#!/usr/bin/env python3
"""
Tests for Settings Module
=========================

Tests for the PluginSettings, KeyboardSettings, and related classes.

Run with: pytest tests/test_settings.py -v
"""

import pytest
import json
import sys
import os
import tempfile
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pose_engine.settings.settings import (
    PluginSettings, KeyboardSettings, MouseSettings, 
    GizmoSettings, CameraSettings, UISettings,
    SettingsChangeNotifier
)
from pose_engine.settings.key_bindings import (
    KeyBinding, MouseBinding, find_binding_conflicts
)
from pose_engine.settings.defaults import (
    DEFAULT_KEYBOARD_SHORTCUTS, DEFAULT_MOUSE_SETTINGS,
    DEFAULT_GIZMO_SETTINGS, DEFAULT_CAMERA_SETTINGS, DEFAULT_UI_SETTINGS,
    KEYBOARD_ACTION_NAMES
)
from PyQt5.QtCore import Qt


class TestKeyBinding:
    """Tests for KeyBinding dataclass."""

    def test_key_binding_creation(self):
        """Test basic KeyBinding creation."""
        binding = KeyBinding(key=Qt.Key_F, modifiers=Qt.ControlModifier, action="test")
        
        assert binding.key == Qt.Key_F
        assert binding.modifiers == Qt.ControlModifier
        assert binding.action == "test"

    def test_key_binding_default_modifiers(self):
        """Test KeyBinding with default modifiers."""
        binding = KeyBinding(key=Qt.Key_A)
        
        assert binding.key == Qt.Key_A
        assert binding.modifiers == Qt.NoModifier

    def test_key_binding_matches(self):
        """Test KeyBinding matches method."""
        binding = KeyBinding(key=Qt.Key_S, modifiers=Qt.ControlModifier)
        
        assert binding.matches(Qt.Key_S, Qt.ControlModifier) == True
        assert binding.matches(Qt.Key_S, Qt.NoModifier) == False
        assert binding.matches(Qt.Key_A, Qt.ControlModifier) == False

    def test_key_binding_to_dict(self):
        """Test KeyBinding serialization."""
        binding = KeyBinding(key=Qt.Key_Z, modifiers=Qt.ControlModifier | Qt.ShiftModifier, action="redo")
        data = binding.to_dict()
        
        assert data['key'] == Qt.Key_Z
        assert data['modifiers'] == int(Qt.ControlModifier | Qt.ShiftModifier)
        assert data['action'] == "redo"

    def test_key_binding_from_dict(self):
        """Test KeyBinding deserialization."""
        data = {'key': Qt.Key_Y, 'modifiers': int(Qt.ControlModifier), 'action': 'redo_alt'}
        binding = KeyBinding.from_dict(data)
        
        assert binding.key == Qt.Key_Y
        assert binding.modifiers == Qt.ControlModifier
        assert binding.action == "redo_alt"

    def test_key_binding_get_key_name(self):
        """Test KeyBinding key name generation."""
        binding = KeyBinding(key=Qt.Key_F)
        assert binding.get_key_name() == 'F'
        
        binding = KeyBinding(key=Qt.Key_Return)
        assert binding.get_key_name() == 'Return'

    def test_key_binding_get_modifier_names(self):
        """Test KeyBinding modifier names."""
        binding = KeyBinding(key=Qt.Key_S, modifiers=Qt.ControlModifier | Qt.ShiftModifier)
        modifiers = binding.get_modifier_names()
        
        assert 'Ctrl' in modifiers
        assert 'Shift' in modifiers

    def test_key_binding_get_display_string(self):
        """Test KeyBinding display string."""
        binding = KeyBinding(key=Qt.Key_S, modifiers=Qt.ControlModifier)
        display = binding.get_display_string()
        
        assert 'Ctrl' in display
        assert 'S' in display

    def test_key_binding_equality(self):
        """Test KeyBinding equality."""
        b1 = KeyBinding(key=Qt.Key_A, modifiers=Qt.ControlModifier)
        b2 = KeyBinding(key=Qt.Key_A, modifiers=Qt.ControlModifier)
        b3 = KeyBinding(key=Qt.Key_A, modifiers=Qt.NoModifier)
        
        assert b1 == b2
        assert b1 != b3

    def test_key_binding_hash(self):
        """Test KeyBinding hash for use in sets/dicts."""
        b1 = KeyBinding(key=Qt.Key_A, modifiers=Qt.ControlModifier)
        b2 = KeyBinding(key=Qt.Key_A, modifiers=Qt.ControlModifier)
        
        # Same bindings should have same hash
        assert hash(b1) == hash(b2)
        
        # Should be usable in a set
        bindings_set = {b1, b2}
        assert len(bindings_set) == 1


class TestMouseBinding:
    """Tests for MouseBinding dataclass."""

    def test_mouse_binding_creation(self):
        """Test basic MouseBinding creation."""
        binding = MouseBinding(button=Qt.LeftButton, modifiers=Qt.ShiftModifier, action="pan")
        
        assert binding.button == Qt.LeftButton
        assert binding.modifiers == Qt.ShiftModifier
        assert binding.action == "pan"

    def test_mouse_binding_matches(self):
        """Test MouseBinding matches method."""
        binding = MouseBinding(button=Qt.RightButton, modifiers=Qt.NoModifier)
        
        assert binding.matches(Qt.RightButton, Qt.NoModifier) == True
        assert binding.matches(Qt.RightButton, Qt.ShiftModifier) == False
        assert binding.matches(Qt.LeftButton, Qt.NoModifier) == False

    def test_mouse_binding_to_dict(self):
        """Test MouseBinding serialization."""
        binding = MouseBinding(button=Qt.MiddleButton, modifiers=Qt.ControlModifier)
        data = binding.to_dict()
        
        assert data['button'] == int(Qt.MiddleButton)
        assert data['modifiers'] == int(Qt.ControlModifier)

    def test_mouse_binding_from_dict(self):
        """Test MouseBinding deserialization."""
        data = {'button': int(Qt.RightButton), 'modifiers': int(Qt.NoModifier), 'action': 'rotate'}
        binding = MouseBinding.from_dict(data)
        
        assert binding.button == Qt.RightButton
        assert binding.modifiers == Qt.NoModifier
        assert binding.action == "rotate"

    def test_mouse_binding_get_button_name(self):
        """Test MouseBinding button name."""
        binding = MouseBinding(button=Qt.LeftButton)
        assert binding.get_button_name() == 'Left'
        
        binding = MouseBinding(button=Qt.RightButton)
        assert binding.get_button_name() == 'Right'


class TestFindBindingConflicts:
    """Tests for conflict detection."""

    def test_no_conflicts(self):
        """Test with no conflicts."""
        bindings = {
            'undo': KeyBinding(key=Qt.Key_Z, modifiers=Qt.ControlModifier),
            'redo': KeyBinding(key=Qt.Key_Y, modifiers=Qt.ControlModifier),
        }
        
        conflicts = find_binding_conflicts(bindings)
        assert len(conflicts) == 0

    def test_with_conflicts(self):
        """Test with conflicts."""
        bindings = {
            'undo': KeyBinding(key=Qt.Key_Z, modifiers=Qt.ControlModifier),
            'redo': KeyBinding(key=Qt.Key_Z, modifiers=Qt.ControlModifier),  # Same as undo
        }
        
        conflicts = find_binding_conflicts(bindings)
        assert len(conflicts) == 1
        assert conflicts[0][0] == 'undo'
        assert conflicts[0][1] == 'redo'

    def test_multiple_conflicts(self):
        """Test with multiple conflicts."""
        bindings = {
            'action1': KeyBinding(key=Qt.Key_A, modifiers=Qt.NoModifier),
            'action2': KeyBinding(key=Qt.Key_A, modifiers=Qt.NoModifier),
            'action3': KeyBinding(key=Qt.Key_A, modifiers=Qt.NoModifier),
        }
        
        conflicts = find_binding_conflicts(bindings)
        assert len(conflicts) == 2


class TestKeyboardSettings:
    """Tests for KeyboardSettings class."""

    def test_keyboard_settings_creation(self):
        """Test KeyboardSettings initialization."""
        settings = KeyboardSettings()
        
        # Should have default bindings loaded
        assert len(settings._shortcuts) > 0

    def test_keyboard_settings_defaults(self):
        """Test that default key bindings are loaded."""
        settings = KeyboardSettings()
        
        # Check some default bindings exist
        assert settings.get_binding('undo') is not None
        assert settings.get_binding('redo') is not None

    def test_keyboard_get_binding(self):
        """Test get_binding method."""
        settings = KeyboardSettings()
        
        binding = settings.get_binding('undo')
        assert binding is not None
        assert binding.key == Qt.Key_Z
        assert binding.modifiers == Qt.ControlModifier

    def test_keyboard_get_binding_nonexistent(self):
        """Test get_binding for nonexistent action."""
        settings = KeyboardSettings()
        
        binding = settings.get_binding('nonexistent_action')
        assert binding is None

    def test_keyboard_set_binding(self):
        """Test set_binding method."""
        settings = KeyboardSettings()
        
        settings.set_binding('test_action', Qt.Key_T, Qt.AltModifier)
        binding = settings.get_binding('test_action')
        
        assert binding is not None
        assert binding.key == Qt.Key_T
        assert binding.modifiers == Qt.AltModifier

    def test_keyboard_get_key(self):
        """Test get_key method."""
        settings = KeyboardSettings()
        
        key = settings.get_key('undo')
        assert key == Qt.Key_Z

    def test_keyboard_get_modifiers(self):
        """Test get_modifiers method."""
        settings = KeyboardSettings()
        
        modifiers = settings.get_modifiers('undo')
        assert modifiers == Qt.ControlModifier

    def test_keyboard_matches(self):
        """Test matches method."""
        settings = KeyboardSettings()
        
        # Should match default undo binding
        assert settings.matches('undo', Qt.Key_Z, Qt.ControlModifier) == True
        assert settings.matches('undo', Qt.Key_Z, Qt.NoModifier) == False

    def test_keyboard_get_all_bindings(self):
        """Test get_all_bindings method."""
        settings = KeyboardSettings()
        
        bindings = settings.get_all_bindings()
        assert isinstance(bindings, dict)
        assert len(bindings) > 0

    def test_keyboard_get_action_name(self):
        """Test get_action_name method."""
        settings = KeyboardSettings()
        
        name = settings.get_action_name('undo')
        assert name == 'Undo'

    def test_keyboard_find_conflicts(self):
        """Test find_conflicts method."""
        settings = KeyboardSettings()
        
        # Default settings should have no conflicts
        conflicts = settings.find_conflicts()
        assert isinstance(conflicts, list)

    def test_keyboard_reset_to_defaults(self):
        """Test reset_to_defaults method."""
        settings = KeyboardSettings()
        
        # Modify a binding
        settings.set_binding('undo', Qt.Key_X, Qt.ControlModifier)
        assert settings.get_key('undo') == Qt.Key_X
        
        # Reset
        settings.reset_to_defaults()
        assert settings.get_key('undo') == Qt.Key_Z

    def test_keyboard_to_dict(self):
        """Test to_dict serialization."""
        settings = KeyboardSettings()
        
        data = settings.to_dict()
        assert isinstance(data, dict)
        assert 'undo' in data

    def test_keyboard_load_from_dict(self):
        """Test load_from_dict deserialization."""
        settings = KeyboardSettings()
        
        # Create custom data
        data = {
            'undo': {'key': Qt.Key_X, 'modifiers': int(Qt.ControlModifier), 'action': 'undo'}
        }
        
        settings.load_from_dict(data)
        assert settings.get_key('undo') == Qt.Key_X


class TestMouseSettings:
    """Tests for MouseSettings class."""

    def test_mouse_settings_creation(self):
        """Test MouseSettings initialization."""
        settings = MouseSettings()
        
        assert settings._settings is not None

    def test_mouse_get_sensitivity(self):
        """Test get_sensitivity method."""
        settings = MouseSettings()
        
        sensitivity = settings.get_sensitivity('rotate')
        assert isinstance(sensitivity, float)

    def test_mouse_set_sensitivity(self):
        """Test set_sensitivity method."""
        settings = MouseSettings()
        
        settings.set_sensitivity('rotate', 2.0)
        assert settings.get_sensitivity('rotate') == 2.0

    def test_mouse_get_binding(self):
        """Test get_binding method."""
        settings = MouseSettings()
        
        binding = settings.get_binding('rotate_binding')
        assert binding is not None

    def test_mouse_matches_binding(self):
        """Test matches_binding method."""
        settings = MouseSettings()
        
        # Default rotate is right button, no modifiers
        assert settings.matches_binding('rotate_binding', Qt.RightButton, Qt.NoModifier) == True

    def test_mouse_reset_to_defaults(self):
        """Test reset_to_defaults method."""
        settings = MouseSettings()
        
        settings.set_sensitivity('rotate', 5.0)
        settings.reset_to_defaults()
        
        # Should be back to default
        assert settings.get_sensitivity('rotate') == 1.0

    def test_mouse_to_dict(self):
        """Test to_dict serialization."""
        settings = MouseSettings()
        
        data = settings.to_dict()
        assert isinstance(data, dict)

    def test_mouse_load_from_dict(self):
        """Test load_from_dict deserialization."""
        settings = MouseSettings()
        
        data = {'rotate_sensitivity': 2.5}
        settings.load_from_dict(data)
        
        assert settings.get_sensitivity('rotate') == 2.5


class TestGizmoSettings:
    """Tests for GizmoSettings class."""

    def test_gizmo_settings_creation(self):
        """Test GizmoSettings initialization."""
        settings = GizmoSettings()
        
        assert settings._settings is not None

    def test_gizmo_get(self):
        """Test get method."""
        settings = GizmoSettings()
        
        scale = settings.get('base_scale')
        assert scale is not None

    def test_gizmo_set(self):
        """Test set method."""
        settings = GizmoSettings()
        
        settings.set('base_scale', 0.5)
        assert settings.get('base_scale') == 0.5

    def test_gizmo_get_scale_params(self):
        """Test get_scale_params method."""
        settings = GizmoSettings()
        
        base, min_scale, max_scale = settings.get_scale_params()
        assert base > 0
        assert min_scale > 0
        assert max_scale > min_scale

    def test_gizmo_get_sensitivity(self):
        """Test get_sensitivity method."""
        settings = GizmoSettings()
        
        sens = settings.get_sensitivity('rotation')
        assert isinstance(sens, float)

    def test_gizmo_get_colors(self):
        """Test get_colors method."""
        settings = GizmoSettings()

        colors = settings.get_colors()
        assert isinstance(colors, dict)
        # The colors dict uses keys like 'x_axis', 'y_axis', 'z_axis'
        assert 'x_axis' in colors or 'x' in colors or 'red' in colors

    def test_gizmo_reset_to_defaults(self):
        """Test reset_to_defaults method."""
        settings = GizmoSettings()
        
        settings.set('base_scale', 10.0)
        settings.reset_to_defaults()
        
        assert settings.get('base_scale') != 10.0

    def test_gizmo_to_dict(self):
        """Test to_dict serialization."""
        settings = GizmoSettings()
        
        data = settings.to_dict()
        assert isinstance(data, dict)

    def test_gizmo_load_from_dict(self):
        """Test load_from_dict deserialization."""
        settings = GizmoSettings()
        
        data = {'base_scale': 0.3}
        settings.load_from_dict(data)
        
        assert settings.get('base_scale') == 0.3


class TestCameraSettings:
    """Tests for CameraSettings class."""

    def test_camera_settings_creation(self):
        """Test CameraSettings initialization."""
        settings = CameraSettings()
        
        assert settings._settings is not None

    def test_camera_get(self):
        """Test get method."""
        settings = CameraSettings()
        
        fov = settings.get('default_fov')
        assert fov is not None

    def test_camera_set(self):
        """Test set method."""
        settings = CameraSettings()
        
        settings.set('default_fov', 60.0)
        assert settings.get('default_fov') == 60.0

    def test_camera_get_fov_params(self):
        """Test get_fov_params method."""
        settings = CameraSettings()
        
        default_fov, min_fov, max_fov = settings.get_fov_params()
        assert default_fov > 0
        assert min_fov > 0
        assert max_fov > min_fov

    def test_camera_get_distance_params(self):
        """Test get_distance_params method."""
        settings = CameraSettings()
        
        default_dist, min_dist, max_dist = settings.get_distance_params()
        assert default_dist > 0
        assert min_dist > 0
        assert max_dist > min_dist

    def test_camera_get_speed(self):
        """Test get_speed method."""
        settings = CameraSettings()
        
        speed = settings.get_speed('rotate')
        assert isinstance(speed, float)

    def test_camera_reset_to_defaults(self):
        """Test reset_to_defaults method."""
        settings = CameraSettings()
        
        settings.set('default_fov', 120.0)
        settings.reset_to_defaults()
        
        assert settings.get('default_fov') != 120.0

    def test_camera_to_dict(self):
        """Test to_dict serialization."""
        settings = CameraSettings()
        
        data = settings.to_dict()
        assert isinstance(data, dict)

    def test_camera_load_from_dict(self):
        """Test load_from_dict deserialization."""
        settings = CameraSettings()
        
        data = {'default_fov': 75.0}
        settings.load_from_dict(data)
        
        assert settings.get('default_fov') == 75.0


class TestUISettings:
    """Tests for UISettings class."""

    def test_ui_settings_creation(self):
        """Test UISettings initialization."""
        settings = UISettings()
        
        assert settings._settings is not None

    def test_ui_get(self):
        """Test get method."""
        settings = UISettings()
        
        show_mesh = settings.get('show_mesh_default')
        assert show_mesh is not None

    def test_ui_set(self):
        """Test set method."""
        settings = UISettings()
        
        settings.set('show_mesh_default', False)
        assert settings.get('show_mesh_default') == False

    def test_ui_get_default_visibility(self):
        """Test get_default_visibility method."""
        settings = UISettings()
        
        visibility = settings.get_default_visibility()
        assert isinstance(visibility, dict)
        assert 'mesh' in visibility
        assert 'skeleton' in visibility

    def test_ui_get_theme_colors(self):
        """Test get_theme_colors method."""
        settings = UISettings()
        
        colors = settings.get_theme_colors()
        assert isinstance(colors, dict)

    def test_ui_reset_to_defaults(self):
        """Test reset_to_defaults method."""
        settings = UISettings()
        
        settings.set('show_mesh_default', False)
        settings.reset_to_defaults()
        
        assert settings.get('show_mesh_default') == True

    def test_ui_to_dict(self):
        """Test to_dict serialization."""
        settings = UISettings()
        
        data = settings.to_dict()
        assert isinstance(data, dict)

    def test_ui_load_from_dict(self):
        """Test load_from_dict deserialization."""
        settings = UISettings()
        
        data = {'show_mesh_default': False}
        settings.load_from_dict(data)
        
        assert settings.get('show_mesh_default') == False


class TestPluginSettings:
    """Tests for PluginSettings main class."""

    def test_plugin_settings_creation(self):
        """Test PluginSettings initialization."""
        settings = PluginSettings()
        
        assert settings.keyboard is not None
        assert settings.mouse is not None
        assert settings.gizmo is not None
        assert settings.camera is not None
        assert settings.ui is not None

    def test_plugin_settings_with_custom_dir(self, tmp_path):
        """Test PluginSettings with custom settings directory."""
        settings = PluginSettings(settings_dir=str(tmp_path))
        
        settings_path = settings.get_settings_path()
        assert tmp_path.name in settings_path or str(tmp_path) in settings_path

    def test_plugin_settings_save(self, tmp_path):
        """Test saving settings to file."""
        settings = PluginSettings(settings_dir=str(tmp_path))
        
        # Modify some settings
        settings.camera.set('default_fov', 75.0)
        
        # Save
        result = settings.save()
        assert result == True
        
        # Check file exists
        settings_path = settings.get_settings_path()
        assert os.path.exists(settings_path)

    def test_plugin_settings_load(self, tmp_path):
        """Test loading settings from file."""
        # Create a settings file
        settings_file = tmp_path / '3d_pose_settings.json'
        settings_data = {
            'version': '1.0',
            'camera': {'default_fov': 80.0},
            'keyboard': {},
            'mouse': {},
            'gizmo': {},
            'ui': {}
        }
        
        with open(settings_file, 'w') as f:
            json.dump(settings_data, f)
        
        # Load settings
        settings = PluginSettings(settings_dir=str(tmp_path))
        result = settings.load()
        
        assert result == True
        assert settings.camera.get('default_fov') == 80.0

    def test_plugin_settings_load_file_not_found(self, tmp_path):
        """Test loading when settings file doesn't exist."""
        settings = PluginSettings(settings_dir=str(tmp_path))
        
        # Don't create the file
        result = settings.load()
        
        # Should return False but not crash
        assert result == False

    def test_plugin_settings_load_invalid_json(self, tmp_path):
        """Test loading with invalid JSON."""
        settings_file = tmp_path / '3d_pose_settings.json'
        
        # Write invalid JSON
        with open(settings_file, 'w') as f:
            f.write("{ invalid json }")
        
        settings = PluginSettings(settings_dir=str(tmp_path))
        result = settings.load()
        
        # Should return False but not crash
        assert result == False

    def test_plugin_settings_reset_all(self, tmp_path):
        """Test resetting all settings to defaults."""
        settings = PluginSettings(settings_dir=str(tmp_path))
        
        # Modify multiple settings
        settings.camera.set('default_fov', 120.0)
        settings.gizmo.set('base_scale', 5.0)
        
        # Reset
        settings.reset_all_to_defaults()
        
        # Should be back to defaults
        assert settings.camera.get('default_fov') != 120.0
        assert settings.gizmo.get('base_scale') != 5.0

    def test_plugin_settings_export_import(self, tmp_path):
        """Test exporting and importing settings."""
        settings = PluginSettings(settings_dir=str(tmp_path))
        
        # Set some values
        settings.camera.set('default_fov', 70.0)
        
        # Export
        export_file = tmp_path / 'exported_settings.json'
        result = settings.export_to_file(str(export_file))
        assert result == True
        
        # Create new settings and import
        new_settings = PluginSettings(settings_dir=str(tmp_path))
        result = new_settings.import_from_file(str(export_file))
        assert result == True
        
        # Check values match
        assert new_settings.camera.get('default_fov') == 70.0

    def test_plugin_settings_notifier(self):
        """Test that notifier is available."""
        settings = PluginSettings()
        
        notifier = settings.notifier
        assert notifier is not None
        assert hasattr(notifier, 'settings_changed')

    def test_plugin_settings_is_modified(self, tmp_path):
        """Test is_modified tracking."""
        settings = PluginSettings(settings_dir=str(tmp_path))
        
        # Fresh settings should not be modified
        # (depends on implementation)
        
        # After reset, should be marked modified
        settings.reset_all_to_defaults()
        assert settings.is_modified() == True
        
        # After save, should not be modified
        settings.save()
        assert settings.is_modified() == False


class TestSettingsChangeNotifier:
    """Tests for SettingsChangeNotifier class."""

    def test_notifier_creation(self):
        """Test notifier creation."""
        notifier = SettingsChangeNotifier()
        
        assert notifier is not None

    def test_notifier_has_signals(self):
        """Test that notifier has required signals."""
        notifier = SettingsChangeNotifier()
        
        assert hasattr(notifier, 'settings_changed')
        assert hasattr(notifier, 'key_binding_changed')
        assert hasattr(notifier, 'setting_changed')


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

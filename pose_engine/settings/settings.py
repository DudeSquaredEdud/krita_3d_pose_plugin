"""
Plugin Settings - Main Settings Management
==========================================

Provides the main PluginSettings class and category-specific settings classes.
Handles loading, saving, and managing all plugin settings with JSON persistence.
"""

import json
import os
from dataclasses import dataclass, field, asdict
from typing import Dict, Optional, Any, List, Callable
from pathlib import Path

from PyQt5.QtCore import Qt, pyqtSignal, QObject

from .defaults import (
    DEFAULT_KEYBOARD_SHORTCUTS,
    DEFAULT_MOUSE_SETTINGS,
    DEFAULT_GIZMO_SETTINGS,
    DEFAULT_CAMERA_SETTINGS,
    DEFAULT_UI_SETTINGS,
    SETTINGS_VERSION,
    KEYBOARD_ACTION_NAMES,
    GIZMO_COLOR_SCHEMES,
    UI_THEMES,
)
from .key_bindings import KeyBinding, MouseBinding, find_binding_conflicts


class SettingsChangeNotifier(QObject):
    """
    Signal emitter for settings changes.
    
    Allows UI components to react to settings changes without
    tight coupling to the settings object.
    """
    settings_changed = pyqtSignal(str, object)  # category, settings_dict
    key_binding_changed = pyqtSignal(str, KeyBinding)  # action, binding
    setting_changed = pyqtSignal(str, str, object)  # category, key, value


class KeyboardSettings:
    """
    Manages keyboard shortcut settings.
    
    Provides methods to get, set, and validate key bindings.
    """
    
    def __init__(self):
        """Initialize keyboard settings with defaults."""
        self._shortcuts: Dict[str, KeyBinding] = {}
        self._load_defaults()
    
    def _load_defaults(self) -> None:
        """Load default keyboard shortcuts."""
        for action, (key, modifiers) in DEFAULT_KEYBOARD_SHORTCUTS.items():
            self._shortcuts[action] = KeyBinding(
                key=key,
                modifiers=modifiers,
                action=action
            )
    
    def get_binding(self, action: str) -> Optional[KeyBinding]:
        """
        Get the key binding for an action.
        
        Args:
            action: Action identifier (e.g., 'undo', 'save_pose')
            
        Returns:
            KeyBinding if found, None otherwise
        """
        return self._shortcuts.get(action)
    
    def get_key(self, action: str) -> int:
        """Get the key for an action."""
        binding = self._shortcuts.get(action)
        return binding.key if binding else Qt.Key_unknown
    
    def get_modifiers(self, action: str) -> int:
        """Get the modifiers for an action."""
        binding = self._shortcuts.get(action)
        return binding.modifiers if binding else Qt.NoModifier
    
    def set_binding(self, action: str, key: int, modifiers: int) -> None:
        """
        Set the key binding for an action.
        
        Args:
            action: Action identifier
            key: Qt.Key value
            modifiers: Qt.KeyboardModifiers
        """
        self._shortcuts[action] = KeyBinding(
            key=key,
            modifiers=modifiers,
            action=action
        )
    
    def set_binding_from_keybinding(self, action: str, binding: KeyBinding) -> None:
        """Set binding from a KeyBinding object."""
        binding.action = action
        self._shortcuts[action] = binding
    
    def matches(self, action: str, key: int, modifiers: int) -> bool:
        """
        Check if a key event matches an action's binding.
        
        Args:
            action: Action identifier
            key: Qt.Key value from key event
            modifiers: Qt.KeyboardModifiers from key event
            
        Returns:
            True if the event matches the action's binding
        """
        binding = self._shortcuts.get(action)
        if binding is None:
            return False
        return binding.matches(key, modifiers)
    
    def get_all_bindings(self) -> Dict[str, KeyBinding]:
        """Get all key bindings."""
        return dict(self._shortcuts)
    
    def get_action_name(self, action: str) -> str:
        """Get a human-readable name for an action."""
        return KEYBOARD_ACTION_NAMES.get(action, action)
    
    def find_conflicts(self) -> List[tuple]:
        """Find any conflicting key bindings."""
        return find_binding_conflicts(self._shortcuts)
    
    def reset_to_defaults(self) -> None:
        """Reset all keyboard shortcuts to defaults."""
        self._shortcuts.clear()
        self._load_defaults()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            action: binding.to_dict()
            for action, binding in self._shortcuts.items()
        }
    
    def load_from_dict(self, data: Dict[str, Any]) -> None:
        """Load settings from a dictionary."""
        for action, binding_data in data.items():
            if action in DEFAULT_KEYBOARD_SHORTCUTS:
                self._shortcuts[action] = KeyBinding.from_dict(binding_data)


class MouseSettings:
    """
    Manages mouse control settings.
    
    Provides methods to configure mouse button bindings and sensitivity.
    """
    
    def __init__(self):
        """Initialize mouse settings with defaults."""
        self._settings: Dict[str, Any] = dict(DEFAULT_MOUSE_SETTINGS)
        self._bindings: Dict[str, MouseBinding] = {}
        self._load_bindings()
    
    def _load_bindings(self) -> None:
        """Load mouse bindings from settings."""
        binding_keys = [
            'rotate_binding', 'rotate_binding_alt',
            'pan_binding', 'pan_binding_alt',
            'zoom_binding'
        ]
        for key in binding_keys:
            if key in self._settings:
                data = self._settings[key]
                self._bindings[key] = MouseBinding(
                    button=data.get('button', Qt.NoButton),
                    modifiers=data.get('modifiers', Qt.NoModifier),
                    action=key
                )
    
    def get_sensitivity(self, sensitivity_type: str) -> float:
        """Get a sensitivity value."""
        return self._settings.get(f'{sensitivity_type}_sensitivity', 1.0)
    
    def set_sensitivity(self, sensitivity_type: str, value: float) -> None:
        """Set a sensitivity value."""
        self._settings[f'{sensitivity_type}_sensitivity'] = value
    
    def get_binding(self, binding_name: str) -> Optional[MouseBinding]:
        """Get a mouse binding by name."""
        return self._bindings.get(binding_name)
    
    def matches_binding(self, binding_name: str, button: int, modifiers: int) -> bool:
        """Check if a mouse event matches a binding."""
        binding = self._bindings.get(binding_name)
        if binding is None:
            return False
        return binding.matches(button, modifiers)
    
    def get_scroll_zoom_speed(self) -> float:
        """Get the scroll wheel zoom speed."""
        return self._settings.get('scroll_zoom_speed', 0.1)
    
    def get_scroll_dolly_speed(self) -> float:
        """Get the scroll wheel dolly speed."""
        return self._settings.get('scroll_dolly_speed', 0.2)
    
    def reset_to_defaults(self) -> None:
        """Reset all mouse settings to defaults."""
        self._settings = dict(DEFAULT_MOUSE_SETTINGS)
        self._bindings.clear()
        self._load_bindings()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = dict(self._settings)
        for name, binding in self._bindings.items():
            result[name] = binding.to_dict()
        return result
    
    def load_from_dict(self, data: Dict[str, Any]) -> None:
        """Load settings from a dictionary."""
        self._settings = dict(DEFAULT_MOUSE_SETTINGS)
        self._settings.update(data)
        self._bindings.clear()
        self._load_bindings()


class GizmoSettings:
    """
    Manages gizmo appearance and behavior settings.
    """
    
    def __init__(self):
        """Initialize gizmo settings with defaults."""
        self._settings: Dict[str, Any] = dict(DEFAULT_GIZMO_SETTINGS)
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a gizmo setting value."""
        return self._settings.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """Set a gizmo setting value."""
        self._settings[key] = value
    
    def get_scale_params(self) -> tuple:
        """Get gizmo scale parameters (base, min, max)."""
        return (
            self._settings.get('base_scale', 0.2),
            self._settings.get('min_scale', 0.05),
            self._settings.get('max_scale', 2.0)
        )
    
    def get_sensitivity(self, mode: str) -> float:
        """Get sensitivity for a gizmo mode."""
        return self._settings.get(f'{mode}_sensitivity', 1.0)
    
    def get_colors(self) -> Dict[str, str]:
        """Get the current color scheme colors."""
        scheme_name = self._settings.get('color_scheme', 'blender')
        return GIZMO_COLOR_SCHEMES.get(scheme_name, GIZMO_COLOR_SCHEMES['blender'])
    
    def get_color_schemes(self) -> Dict[str, Dict[str, str]]:
        """Get all available color schemes."""
        return dict(GIZMO_COLOR_SCHEMES)
    
    def reset_to_defaults(self) -> None:
        """Reset all gizmo settings to defaults."""
        self._settings = dict(DEFAULT_GIZMO_SETTINGS)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return dict(self._settings)
    
    def load_from_dict(self, data: Dict[str, Any]) -> None:
        """Load settings from a dictionary."""
        self._settings = dict(DEFAULT_GIZMO_SETTINGS)
        self._settings.update(data)


class CameraSettings:
    """
    Manages camera behavior settings.
    """

    def __init__(self, notifier: Optional[SettingsChangeNotifier] = None):
        """Initialize camera settings with defaults."""
        self._settings: Dict[str, Any] = dict(DEFAULT_CAMERA_SETTINGS)
        self._notifier = notifier

    def _set_notifier(self, notifier: SettingsChangeNotifier) -> None:
        """Set the notifier after initialization."""
        self._notifier = notifier

    def get(self, key: str, default: Any = None) -> Any:
        """Get a camera setting value."""
        return self._settings.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a camera setting value."""
        self._settings[key] = value
        if self._notifier:
            self._notifier.setting_changed.emit('camera', key, value)
    
    def get_fov_params(self) -> tuple:
        """Get FOV parameters (default, min, max)."""
        return (
            self._settings.get('default_fov', 45.0),
            self._settings.get('min_fov', 30.0),
            self._settings.get('max_fov', 120.0)
        )
    
    def get_distance_params(self) -> tuple:
        """Get distance parameters (default, min, max)."""
        return (
            self._settings.get('default_distance', 3.0),
            self._settings.get('min_distance', 0.5),
            self._settings.get('max_distance', 20.0)
        )
    
    def get_speed(self, speed_type: str) -> float:
        """Get a speed value."""
        return self._settings.get(f'{speed_type}_speed', 0.01)
    
    def reset_to_defaults(self) -> None:
        """Reset all camera settings to defaults."""
        self._settings = dict(DEFAULT_CAMERA_SETTINGS)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return dict(self._settings)
    
    def load_from_dict(self, data: Dict[str, Any]) -> None:
        """Load settings from a dictionary."""
        self._settings = dict(DEFAULT_CAMERA_SETTINGS)
        self._settings.update(data)


class UISettings:
    """
    Manages UI appearance and default state settings.
    """
    
    def __init__(self):
        """Initialize UI settings with defaults."""
        self._settings: Dict[str, Any] = dict(DEFAULT_UI_SETTINGS)
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a UI setting value."""
        return self._settings.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """Set a UI setting value."""
        self._settings[key] = value
    
    def get_default_visibility(self) -> Dict[str, bool]:
        """Get default visibility states for mesh, skeleton, joints, gizmo."""
        return {
            'mesh': self._settings.get('show_mesh_default', True),
            'skeleton': self._settings.get('show_skeleton_default', True),
            'joints': self._settings.get('show_joints_default', True),
            'gizmo': self._settings.get('show_gizmo_default', True),
        }
    
    def get_theme_colors(self) -> Dict[str, str]:
        """Get the current theme's color palette."""
        theme_name = self._settings.get('theme', 'dark')
        return UI_THEMES.get(theme_name, UI_THEMES['dark'])
    
    def get_themes(self) -> Dict[str, Dict[str, str]]:
        """Get all available themes."""
        return dict(UI_THEMES)
    
    def reset_to_defaults(self) -> None:
        """Reset all UI settings to defaults."""
        self._settings = dict(DEFAULT_UI_SETTINGS)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return dict(self._settings)
    
    def load_from_dict(self, data: Dict[str, Any]) -> None:
        """Load settings from a dictionary."""
        self._settings = dict(DEFAULT_UI_SETTINGS)
        self._settings.update(data)


class PluginSettings:
    """
    Main settings manager for the plugin.
    
    Provides a unified interface to all settings categories and handles
    loading/saving to JSON files.
    
    Usage:
        settings = PluginSettings()
        settings.load()  # Load from file
        
        # Access settings
        key = settings.keyboard.get_key('undo')
        fov = settings.camera.get('default_fov')
        
        # Modify settings
        settings.keyboard.set_binding('undo', Qt.Key_Z, Qt.ControlModifier)
        settings.save()  # Save to file
    """
    
    def __init__(self, settings_dir: Optional[str] = None):
        """
        Initialize plugin settings.

        Args:
            settings_dir: Optional custom settings directory.
            If None, uses Krita's standard settings location.
        """
        self._settings_dir = settings_dir
        self._notifier = SettingsChangeNotifier()

        # Initialize settings with notifier for change notifications
        self.keyboard = KeyboardSettings()
        self.mouse = MouseSettings()
        self.gizmo = GizmoSettings()
        self.camera = CameraSettings(self._notifier)
        self.ui = UISettings()

        # Track if settings have been modified
        self._modified = False

        # Defer settings path resolution to avoid calling Krita.instance()
        # during docker initialization, which can interfere with window geometry
        self._settings_path: Optional[str] = None
    
    @property
    def notifier(self) -> SettingsChangeNotifier:
        """Get the settings change notifier for connecting signals."""
        return self._notifier
    
    def get_settings_path(self) -> str:
        """
        Get the path to the settings file.

        The path is cached after first resolution to avoid repeated calls
        to Krita.instance() which can interfere with window geometry.

        Returns:
            Path to the settings JSON file
        """
        # Return cached path if available
        if self._settings_path is not None:
            return self._settings_path

        if self._settings_dir:
            settings_dir = Path(self._settings_dir)
        else:
            # Use a simple fallback that doesn't require Krita.instance()
            # This avoids interfering with Krita's window initialization
            settings_dir = Path.home() / '.local' / 'share' / 'krita_3d_pose'

        # Ensure directory exists
        settings_dir.mkdir(parents=True, exist_ok=True)

        self._settings_path = str(settings_dir / '3d_pose_settings.json')
        return self._settings_path
    
    def load(self) -> bool:
        """
        Load settings from the settings file.
        
        Returns:
            True if settings were loaded successfully, False otherwise
        """
        settings_path = self.get_settings_path()
        
        if not os.path.exists(settings_path):
            # No settings file, use defaults
            return False
        
        try:
            with open(settings_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Check version for potential migration
            version = data.get('version', '1.0')
            
            # Load each category
            if 'keyboard' in data:
                self.keyboard.load_from_dict(data['keyboard'])
            if 'mouse' in data:
                self.mouse.load_from_dict(data['mouse'])
            if 'gizmo' in data:
                self.gizmo.load_from_dict(data['gizmo'])
            if 'camera' in data:
                self.camera.load_from_dict(data['camera'])
            if 'ui' in data:
                self.ui.load_from_dict(data['ui'])
            
            self._modified = False
            return True
            
        except (json.JSONDecodeError, IOError, KeyError) as e:
            print(f"Error loading settings: {e}")
            return False
    
    def save(self) -> bool:
        """
        Save settings to the settings file.
        
        Returns:
            True if settings were saved successfully, False otherwise
        """
        settings_path = self.get_settings_path()
        
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(settings_path), exist_ok=True)
            
            data = {
                'version': SETTINGS_VERSION,
                'keyboard': self.keyboard.to_dict(),
                'mouse': self.mouse.to_dict(),
                'gizmo': self.gizmo.to_dict(),
                'camera': self.camera.to_dict(),
                'ui': self.ui.to_dict(),
            }
            
            with open(settings_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            
            self._modified = False
            return True
            
        except (IOError, OSError) as e:
            print(f"Error saving settings: {e}")
            return False
    
    def reset_all_to_defaults(self) -> None:
        """Reset all settings to their default values."""
        self.keyboard.reset_to_defaults()
        self.mouse.reset_to_defaults()
        self.gizmo.reset_to_defaults()
        self.camera.reset_to_defaults()
        self.ui.reset_to_defaults()
        self._modified = True
    
    def is_modified(self) -> bool:
        """Check if settings have been modified since last save."""
        return self._modified
    
    def export_to_file(self, filepath: str) -> bool:
        """
        Export settings to a specific file.
        
        Args:
            filepath: Path to export settings to
            
        Returns:
            True if export was successful
        """
        try:
            data = {
                'version': SETTINGS_VERSION,
                'keyboard': self.keyboard.to_dict(),
                'mouse': self.mouse.to_dict(),
                'gizmo': self.gizmo.to_dict(),
                'camera': self.camera.to_dict(),
                'ui': self.ui.to_dict(),
            }
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            
            return True
            
        except (IOError, OSError) as e:
            print(f"Error exporting settings: {e}")
            return False
    
    def import_from_file(self, filepath: str) -> bool:
        """
        Import settings from a specific file.
        
        Args:
            filepath: Path to import settings from
            
        Returns:
            True if import was successful
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if 'keyboard' in data:
                self.keyboard.load_from_dict(data['keyboard'])
            if 'mouse' in data:
                self.mouse.load_from_dict(data['mouse'])
            if 'gizmo' in data:
                self.gizmo.load_from_dict(data['gizmo'])
            if 'camera' in data:
                self.camera.load_from_dict(data['camera'])
            if 'ui' in data:
                self.ui.load_from_dict(data['ui'])
            
            self._modified = True
            return True
            
        except (json.JSONDecodeError, IOError, KeyError) as e:
            print(f"Error importing settings: {e}")
            return False

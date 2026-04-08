"""
Settings Module - Plugin Configuration System
==============================================

Provides a comprehensive settings system for the Krita 3D Pose Plugin.
Supports keyboard shortcuts, mouse controls, gizmo settings, camera
behavior, and UI preferences with JSON persistence.
"""

from .defaults import (
    DEFAULT_KEYBOARD_SHORTCUTS,
    DEFAULT_MOUSE_SETTINGS,
    DEFAULT_GIZMO_SETTINGS,
    DEFAULT_CAMERA_SETTINGS,
    DEFAULT_UI_SETTINGS,
    SETTINGS_VERSION
)
from .key_bindings import KeyBinding, MouseBinding
from .settings import (
    PluginSettings,
    KeyboardSettings,
    MouseSettings,
    GizmoSettings,
    CameraSettings,
    UISettings
)

__all__ = [
    # Settings classes
    'PluginSettings',
    'KeyboardSettings',
    'MouseSettings',
    'GizmoSettings',
    'CameraSettings',
    'UISettings',
    # Binding classes
    'KeyBinding',
    'MouseBinding',
    # Defaults
    'DEFAULT_KEYBOARD_SHORTCUTS',
    'DEFAULT_MOUSE_SETTINGS',
    'DEFAULT_GIZMO_SETTINGS',
    'DEFAULT_CAMERA_SETTINGS',
    'DEFAULT_UI_SETTINGS',
    'SETTINGS_VERSION'
]

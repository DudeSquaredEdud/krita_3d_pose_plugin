"""
Settings Widgets Package
========================

Individual settings widget classes for the advanced settings dialog.
"""

from .key_binding_editor import KeyBindingEditor
from .keyboard_settings import KeyboardSettingsWidget
from .mouse_settings import MouseSettingsWidget
from .gizmo_settings import GizmoSettingsWidget
from .camera_settings import CameraSettingsWidget
from .ui_settings import UISettingsWidget

__all__ = [
    'KeyBindingEditor',
    'KeyboardSettingsWidget',
    'MouseSettingsWidget',
    'GizmoSettingsWidget',
    'CameraSettingsWidget',
    'UISettingsWidget',
]

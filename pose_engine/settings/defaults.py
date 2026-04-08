"""
Default Settings Values
=======================

Defines default values for all plugin settings.
These are used when no user settings exist or when resetting to defaults.
"""

from PyQt5.QtCore import Qt

# Settings schema version for migration support
SETTINGS_VERSION = "1.0"

# =============================================================================
# KEYBOARD SHORTCUTS
# =============================================================================

# KeyBinding format: (key: int, modifiers: Qt.KeyboardModifiers)
# Modifiers are combined using bitwise OR

DEFAULT_KEYBOARD_SHORTCUTS = {
# Viewport navigation
'frame_model': (Qt.Key_F, Qt.NoModifier),
'reset_camera': (Qt.Key_R, Qt.NoModifier),

# Visibility toggles
'toggle_mesh': (Qt.Key_T, Qt.NoModifier),
'toggle_skeleton': (Qt.Key_S, Qt.NoModifier),
'toggle_joints': (Qt.Key_J, Qt.NoModifier),
'toggle_gizmo': (Qt.Key_H, Qt.NoModifier), # H for "hide/show gizmo"

# Gizmo mode cycling
'toggle_gizmo_mode': (Qt.Key_G, Qt.NoModifier),
'gizmo_rotate': (Qt.Key_1, Qt.NoModifier), # Direct mode selection
'gizmo_move': (Qt.Key_2, Qt.NoModifier),
'gizmo_scale': (Qt.Key_3, Qt.NoModifier),

# Undo/Redo
'undo': (Qt.Key_Z, Qt.ControlModifier),
'redo': (Qt.Key_Z, Qt.ControlModifier | Qt.ShiftModifier),
'redo_alt': (Qt.Key_Y, Qt.ControlModifier),

# Pose file operations
'save_pose': (Qt.Key_S, Qt.ControlModifier),
'load_pose': (Qt.Key_O, Qt.ControlModifier),
'sync_to_layer': (Qt.Key_S, Qt.ControlModifier | Qt.ShiftModifier),  # Ctrl+Shift+S

# Selection
'deselect': (Qt.Key_Escape, Qt.NoModifier),
'select_parent': (Qt.Key_Up, Qt.NoModifier),
'select_child': (Qt.Key_Down, Qt.NoModifier),
'select_prev_sibling': (Qt.Key_Left, Qt.NoModifier),
'select_next_sibling': (Qt.Key_Right, Qt.NoModifier),

# Bone operations
'reset_bone': (Qt.Key_R, Qt.ControlModifier),
'delete_keyframe': (Qt.Key_Delete, Qt.NoModifier),

# Camera movement (QWEASD) - moves orbit target
'camera_forward': (Qt.Key_W, Qt.NoModifier),
'camera_backward': (Qt.Key_S, Qt.NoModifier),
'camera_left': (Qt.Key_A, Qt.NoModifier),
'camera_right': (Qt.Key_D, Qt.NoModifier),
'camera_up': (Qt.Key_Q, Qt.NoModifier),
'camera_down': (Qt.Key_E, Qt.NoModifier),

# Camera mode toggle
'toggle_head_look': (Qt.Key_Tab, Qt.NoModifier),
'toggle_camera_panel': (Qt.Key_C, Qt.ShiftModifier),  # Shift+C to toggle camera panel

# Camera bookmarks (quick save/recall)
'bookmark_recall_1': (Qt.Key_1, Qt.NoModifier),
'bookmark_recall_2': (Qt.Key_2, Qt.NoModifier),
'bookmark_recall_3': (Qt.Key_3, Qt.NoModifier),
'bookmark_recall_4': (Qt.Key_4, Qt.NoModifier),
'bookmark_recall_5': (Qt.Key_5, Qt.NoModifier),
'bookmark_recall_6': (Qt.Key_6, Qt.NoModifier),
'bookmark_recall_7': (Qt.Key_7, Qt.NoModifier),
'bookmark_recall_8': (Qt.Key_8, Qt.NoModifier),
'bookmark_recall_9': (Qt.Key_9, Qt.NoModifier),
'bookmark_save_1': (Qt.Key_1, Qt.ControlModifier),
'bookmark_save_2': (Qt.Key_2, Qt.ControlModifier),
'bookmark_save_3': (Qt.Key_3, Qt.ControlModifier),
'bookmark_save_4': (Qt.Key_4, Qt.ControlModifier),
'bookmark_save_5': (Qt.Key_5, Qt.ControlModifier),
'bookmark_save_6': (Qt.Key_6, Qt.ControlModifier),
'bookmark_save_7': (Qt.Key_7, Qt.ControlModifier),
'bookmark_save_8': (Qt.Key_8, Qt.ControlModifier),
'bookmark_save_9': (Qt.Key_9, Qt.ControlModifier),
}

# Human-readable names for keyboard actions
KEYBOARD_ACTION_NAMES = {
'frame_model': 'Frame Model',
'reset_camera': 'Reset Camera',
'toggle_mesh': 'Toggle Mesh',
'toggle_skeleton': 'Toggle Skeleton',
'toggle_joints': 'Toggle Joints',
'toggle_gizmo': 'Toggle Gizmo',
'toggle_gizmo_mode': 'Cycle Gizmo Mode',
'gizmo_rotate': 'Gizmo: Rotate',
'gizmo_move': 'Gizmo: Move',
'gizmo_scale': 'Gizmo: Scale',
'undo': 'Undo',
'redo': 'Redo',
'redo_alt': 'Redo (Alternative)',
'save_pose': 'Save Pose',
'load_pose': 'Load Pose',
'sync_to_layer': 'Sync to Layer',
'deselect': 'Deselect',
'select_parent': 'Select Parent Bone',
'select_child': 'Select Child Bone',
'select_prev_sibling': 'Select Previous Sibling',
'select_next_sibling': 'Select Next Sibling',
'reset_bone': 'Reset Bone Transform',
'delete_keyframe': 'Delete Keyframe',
# Camera movement
'camera_forward': 'Camera Forward',
'camera_backward': 'Camera Backward',
'camera_left': 'Camera Left',
'camera_right': 'Camera Right',
'camera_up': 'Camera Up',
'camera_down': 'Camera Down',
'toggle_head_look': 'Toggle Head-Look Mode',
'toggle_camera_panel': 'Toggle Camera Panel',
# Camera bookmarks
'bookmark_recall_1': 'Recall Bookmark 1',
'bookmark_recall_2': 'Recall Bookmark 2',
'bookmark_recall_3': 'Recall Bookmark 3',
'bookmark_recall_4': 'Recall Bookmark 4',
'bookmark_recall_5': 'Recall Bookmark 5',
'bookmark_recall_6': 'Recall Bookmark 6',
'bookmark_recall_7': 'Recall Bookmark 7',
'bookmark_recall_8': 'Recall Bookmark 8',
'bookmark_recall_9': 'Recall Bookmark 9',
'bookmark_save_1': 'Save Bookmark 1',
'bookmark_save_2': 'Save Bookmark 2',
'bookmark_save_3': 'Save Bookmark 3',
'bookmark_save_4': 'Save Bookmark 4',
'bookmark_save_5': 'Save Bookmark 5',
'bookmark_save_6': 'Save Bookmark 6',
'bookmark_save_7': 'Save Bookmark 7',
'bookmark_save_8': 'Save Bookmark 8',
'bookmark_save_9': 'Save Bookmark 9',
}

# =============================================================================
# MOUSE CONTROLS
# =============================================================================

DEFAULT_MOUSE_SETTINGS = {
    # Sensitivity multipliers
    'rotate_sensitivity': 1.0,
    'pan_sensitivity': 1.0,
    'zoom_sensitivity': 1.0,
    
    # Button bindings for camera controls
    # Format: {'button': Qt.MouseButton, 'modifiers': Qt.KeyboardModifiers}
    'rotate_binding': {
        'button': Qt.RightButton,
        'modifiers': Qt.NoModifier
    },
    'rotate_binding_alt': {
        'button': Qt.LeftButton,
        'modifiers': Qt.ShiftModifier
    },
    'pan_binding': {
        'button': Qt.LeftButton,
        'modifiers': Qt.ControlModifier
    },
    'pan_binding_alt': {
        'button': Qt.MiddleButton,
        'modifiers': Qt.NoModifier
    },
    'zoom_binding': {
        'button': Qt.RightButton,
        'modifiers': Qt.NoModifier  # Vertical drag
    },
    
    # Scroll wheel settings
    'scroll_zoom_speed': 0.1,
    'scroll_dolly_speed': 0.2,
}

# =============================================================================
# GIZMO SETTINGS
# =============================================================================

DEFAULT_GIZMO_SETTINGS = {
    # Scale settings
    'base_scale': 0.2,      # Base scale factor
    'min_scale': 0.05,      # Minimum scale (close-up)
    'max_scale': 2.0,       # Maximum scale (far away)
    
    # Sensitivity for gizmo interactions
    'rotation_sensitivity': 1.0,
    'movement_sensitivity': 1.0,
    'scale_sensitivity': 1.0,
    
    # Visual settings
    'axis_length': 1.0,     # Relative axis length
    'handle_size': 0.15,    # Size of arrow heads/handles
    'hit_threshold': 10,    # Pixels for hit testing
    
    # Color scheme (preset name)
    'color_scheme': 'blender',
}

# Available color schemes for gizmos
GIZMO_COLOR_SCHEMES = {
    'blender': {
        'x_axis': '#E83151',    # Red
        'y_axis': '#57E854',    # Green
        'z_axis': '#3B6EE8',    # Blue
        'hover': '#FFFFFF',     # White
        'drag': '#FFCC00',      # Yellow
    },
    'maya': {
        'x_axis': '#E83151',    # Red
        'y_axis': '#57E854',    # Green
        'z_axis': '#3B6EE8',    # Blue
        'hover': '#FFCC00',     # Yellow
        'drag': '#FFFFFF',      # White
    },
    'classic': {
        'x_axis': '#FF0000',    # Pure Red
        'y_axis': '#00FF00',    # Pure Green
        'z_axis': '#0000FF',    # Pure Blue
        'hover': '#FFFF00',     # Yellow
        'drag': '#FF00FF',      # Magenta
    },
}

# =============================================================================
# CAMERA SETTINGS
# =============================================================================

DEFAULT_CAMERA_SETTINGS = {
# Field of view
'default_fov': 45.0,
'min_fov': 30.0,
'max_fov': 120.0,

# Distance (zoom) limits
'default_distance': 3.0,
'min_distance': 0.5,
'max_distance': 20.0,

# Movement speeds
'rotation_speed': 0.01,
'zoom_speed': 0.1,
'pan_speed': 0.001,
'dolly_speed': 0.2,

# Orbit behavior
'auto_rotate': False,
'auto_rotate_speed': 0.5,

# Target behavior
'target_on_select': True, # Auto-target selected bone
'smooth_transitions': True,
'transition_speed': 0.1,

# Keyboard movement (QWEASD)
'keyboard_movement_speed': 0.05,
'keyboard_movement_speed_slow': 0.02,
'keyboard_movement_speed_fast': 0.10,
'keyboard_vertical_speed': 0.025,  # Q/E vertical movement (half of horizontal)

# Speed modifiers
'precision_factor': 0.25,  # Shift key
'fast_factor': 3.0,        # Ctrl key

# FOV transition (smooth)
'fov_transition_speed': 10.0, # Degrees per second

# Camera rotation smoothing
'rotation_smoothing': 8.0, # Radians per second (higher = snappier, lower = smoother)
'rotation_smoothing_enabled': True,

# Head-look mode
'head_look_mode': False, # Default to orbit mode
}

# Speed presets for quick selection
SPEED_PRESETS = {
'slow': {'keyboard_movement_speed': 0.02},
'normal': {'keyboard_movement_speed': 0.05},
'fast': {'keyboard_movement_speed': 0.10},
}

# =============================================================================
# UI SETTINGS
# =============================================================================

DEFAULT_UI_SETTINGS = {
    # Default visibility states
    'show_mesh_default': True,
    'show_skeleton_default': True,
    'show_joints_default': True,
    'show_gizmo_default': True,
    
    # Joint rendering
    'joint_scale': 0.15,
    'joint_color_selected': '#FFCC00',
    'joint_color_hover': '#FFFFFF',
    'joint_color_normal': '#3498DB',
    
    # Skeleton rendering
    'bone_width': 2.0,
    'bone_color': '#ECF0F1',
    'bone_color_selected': '#FFCC00',
    
    # Theme
    'theme': 'dark',
    'accent_color': '#3498DB',
}

# Available UI themes
UI_THEMES = {
    'dark': {
        'background': '#2C3E50',
        'surface': '#34495E',
        'text': '#ECF0F1',
        'text_secondary': '#BDC3C7',
        'accent': '#3498DB',
        'border': '#4A6572',
    },
    'light': {
        'background': '#FFFFFF',
        'surface': '#F5F5F5',
        'text': '#2C3E50',
        'text_secondary': '#7F8C8D',
        'accent': '#3498DB',
        'border': '#BDC3C7',
    },
    'krita': {
        'background': '#323232',
        'surface': '#3B3B3B',
        'text': '#D4D4D4',
        'text_secondary': '#A0A0A0',
        'accent': '#4FC3F7',
        'border': '#505050',
    },
}

# =============================================================================
# SCENE SETTINGS (Auto-save and Project Integration)
# =============================================================================

DEFAULT_SCENE_SETTINGS = {
    # Auto-save timing
    'idle_save_delay': 5.0,  # Seconds after last change before auto-save
    'continuous_save_interval': 60.0,  # Maximum time between saves during continuous changes
    
    # File management
    'max_backup_files': 5,  # Number of backup files to keep
    'auto_create_scene': True,  # Automatically create scene for new Krita projects
    
    # Scene behavior
    'auto_load_scene': True,  # Automatically load scene when opening Krita project
    'prompt_on_conflict': True,  # Ask user when scene file conflicts exist
}

# =============================================================================
# SETTINGS CATEGORIES FOR UI
# =============================================================================

SETTINGS_CATEGORIES = {
    'keyboard': {
        'name': 'Keyboard Shortcuts',
        'icon': '⌨️',
        'description': 'Customize keyboard shortcuts for all actions',
    },
    'mouse': {
        'name': 'Mouse Controls',
        'icon': '🖱️',
        'description': 'Configure mouse button bindings and sensitivity',
    },
    'gizmo': {
        'name': 'Gizmo Settings',
        'icon': '🎯',
        'description': 'Adjust gizmo appearance and behavior',
    },
    'camera': {
        'name': 'Camera Settings',
        'icon': '📷',
        'description': 'Configure camera behavior and limits',
    },
    'ui': {
        'name': 'UI Preferences',
        'icon': '🎨',
        'description': 'Customize visual appearance and defaults',
    },
    'scene': {
        'name': 'Scene Settings',
        'icon': '📁',
        'description': 'Configure auto-save and project integration',
    },
}

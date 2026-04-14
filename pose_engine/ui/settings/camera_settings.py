"""
Settings Widgets - Individual Settings Components
=================================================

This package contains individual settings widget classes.
"""

from typing import Optional, Dict, List

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QGroupBox, QLabel, QPushButton, QSlider, QSpinBox,
    QDoubleSpinBox, QComboBox, QCheckBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView,
    QFrame, QScrollArea, QGridLayout, QMessageBox,
    QKeySequenceEdit, QSplitter, QListWidget, QListWidgetItem,
    QSizePolicy, QSpacerItem
)
from PyQt5.QtCore import Qt, pyqtSignal, QEvent
from PyQt5.QtGui import QKeyEvent, QFont, QColor

from ...settings import PluginSettings, KeyBinding, MouseBinding
from ...settings.defaults import (
    KEYBOARD_ACTION_NAMES,
    GIZMO_COLOR_SCHEMES,
    UI_THEMES,
    SETTINGS_CATEGORIES,
)


class CameraSettingsWidget(QWidget):
    """Widget for editing camera settings."""

    settings_changed = pyqtSignal()

    def __init__(self, settings: PluginSettings, parent=None):
        super().__init__(parent)
        self._settings = settings
        self._setup_ui()
        self._load_settings()

    def _setup_ui(self) -> None:
        """Set up the UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # FOV settings
        fov_group = QGroupBox("Field of View")
        fov_layout = QGridLayout(fov_group)

        fov_layout.addWidget(QLabel("Default FOV:"), 0, 0)
        self._default_fov = QSpinBox()
        self._default_fov.setRange(30, 120)
        self._default_fov.valueChanged.connect(self._on_setting_changed)
        fov_layout.addWidget(self._default_fov, 0, 1)

        fov_layout.addWidget(QLabel("Min FOV:"), 1, 0)
        self._min_fov = QSpinBox()
        self._min_fov.setRange(10, 60)
        self._min_fov.valueChanged.connect(self._on_setting_changed)
        fov_layout.addWidget(self._min_fov, 1, 1)

        fov_layout.addWidget(QLabel("Max FOV:"), 2, 0)
        self._max_fov = QSpinBox()
        self._max_fov.setRange(60, 150)
        self._max_fov.valueChanged.connect(self._on_setting_changed)
        fov_layout.addWidget(self._max_fov, 2, 1)

        layout.addWidget(fov_group)

        # Distance settings
        dist_group = QGroupBox("Distance Limits")
        dist_layout = QGridLayout(dist_group)

        dist_layout.addWidget(QLabel("Default Distance:"), 0, 0)
        self._default_dist = QDoubleSpinBox()
        self._default_dist.setRange(0.5, 20.0)
        self._default_dist.setSingleStep(0.5)
        self._default_dist.valueChanged.connect(self._on_setting_changed)
        dist_layout.addWidget(self._default_dist, 0, 1)

        dist_layout.addWidget(QLabel("Min Distance:"), 1, 0)
        self._min_dist = QDoubleSpinBox()
        self._min_dist.setRange(0.1, 2.0)
        self._min_dist.setSingleStep(0.1)
        self._min_dist.valueChanged.connect(self._on_setting_changed)
        dist_layout.addWidget(self._min_dist, 1, 1)

        dist_layout.addWidget(QLabel("Max Distance:"), 2, 0)
        self._max_dist = QDoubleSpinBox()
        self._max_dist.setRange(5.0, 100.0)
        self._max_dist.setSingleStep(5.0)
        self._max_dist.valueChanged.connect(self._on_setting_changed)
        dist_layout.addWidget(self._max_dist, 2, 1)

        layout.addWidget(dist_group)

        # Speed settings
        speed_group = QGroupBox("Movement Speeds")
        speed_layout = QGridLayout(speed_group)

        speed_layout.addWidget(QLabel("Rotation:"), 0, 0)
        self._rot_speed = QDoubleSpinBox()
        self._rot_speed.setRange(0.001, 0.1)
        self._rot_speed.setSingleStep(0.001)
        self._rot_speed.setDecimals(3)
        self._rot_speed.valueChanged.connect(self._on_setting_changed)
        speed_layout.addWidget(self._rot_speed, 0, 1)

        speed_layout.addWidget(QLabel("Zoom:"), 1, 0)
        self._zoom_speed = QDoubleSpinBox()
        self._zoom_speed.setRange(0.01, 0.5)
        self._zoom_speed.setSingleStep(0.01)
        self._zoom_speed.setDecimals(2)
        self._zoom_speed.valueChanged.connect(self._on_setting_changed)
        speed_layout.addWidget(self._zoom_speed, 1, 1)

        speed_layout.addWidget(QLabel("Pan:"), 2, 0)
        self._pan_speed = QDoubleSpinBox()
        self._pan_speed.setRange(0.0001, 0.01)
        self._pan_speed.setSingleStep(0.0001)
        self._pan_speed.setDecimals(4)
        self._pan_speed.valueChanged.connect(self._on_setting_changed)
        speed_layout.addWidget(self._pan_speed, 2, 1)

        layout.addWidget(speed_group)

        # Keyboard movement settings
        keyboard_group = QGroupBox("Keyboard Movement (QWEASD)")
        keyboard_layout = QGridLayout(keyboard_group)

        keyboard_layout.addWidget(QLabel("Base Speed:"), 0, 0)
        self._keyboard_speed = QDoubleSpinBox()
        self._keyboard_speed.setRange(0.01, 0.5)
        self._keyboard_speed.setSingleStep(0.01)
        self._keyboard_speed.setDecimals(2)
        self._keyboard_speed.valueChanged.connect(self._on_setting_changed)
        keyboard_layout.addWidget(self._keyboard_speed, 0, 1)

        keyboard_layout.addWidget(QLabel("Slow (Shift):"), 1, 0)
        self._keyboard_speed_slow = QDoubleSpinBox()
        self._keyboard_speed_slow.setRange(0.005, 0.2)
        self._keyboard_speed_slow.setSingleStep(0.005)
        self._keyboard_speed_slow.setDecimals(3)
        self._keyboard_speed_slow.valueChanged.connect(self._on_setting_changed)
        keyboard_layout.addWidget(self._keyboard_speed_slow, 1, 1)

        keyboard_layout.addWidget(QLabel("Fast (Ctrl):"), 2, 0)
        self._keyboard_speed_fast = QDoubleSpinBox()
        self._keyboard_speed_fast.setRange(0.05, 1.0)
        self._keyboard_speed_fast.setSingleStep(0.05)
        self._keyboard_speed_fast.setDecimals(2)
        self._keyboard_speed_fast.valueChanged.connect(self._on_setting_changed)
        keyboard_layout.addWidget(self._keyboard_speed_fast, 2, 1)

        layout.addWidget(keyboard_group)

        # Behavior settings
        behavior_group = QGroupBox("Behavior")
        behavior_layout = QVBoxLayout(behavior_group)

        self._target_on_select = QCheckBox("Auto-target selected bone")
        self._target_on_select.toggled.connect(self._on_setting_changed)
        behavior_layout.addWidget(self._target_on_select)

        self._smooth_transitions = QCheckBox("Smooth camera transitions")
        self._smooth_transitions.toggled.connect(self._on_setting_changed)
        behavior_layout.addWidget(self._smooth_transitions)

        self._auto_rotate = QCheckBox("Auto-rotate camera")
        self._auto_rotate.toggled.connect(self._on_setting_changed)
        behavior_layout.addWidget(self._auto_rotate)

        layout.addWidget(behavior_group)

        # View mode settings
        mode_group = QGroupBox("View Mode")
        mode_layout = QVBoxLayout(mode_group)

        self._head_look_mode = QCheckBox("Start in Head-Look mode (instead of Orbit)")
        self._head_look_mode.setToolTip("In Head-Look mode, the camera stays in place and rotates.\nIn Orbit mode, the camera orbits around a target point.")
        self._head_look_mode.toggled.connect(self._on_setting_changed)
        mode_layout.addWidget(self._head_look_mode)

        layout.addWidget(mode_group)

        # Reset button
        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.clicked.connect(self._reset_to_defaults)
        layout.addWidget(reset_btn)

        layout.addStretch()

    def _load_settings(self) -> None:
        """Load current settings."""
        self._default_fov.setValue(int(self._settings.camera.get('default_fov', 45.0)))
        self._min_fov.setValue(int(self._settings.camera.get('min_fov', 30.0)))
        self._max_fov.setValue(int(self._settings.camera.get('max_fov', 120.0)))

        self._default_dist.setValue(self._settings.camera.get('default_distance', 3.0))
        self._min_dist.setValue(self._settings.camera.get('min_distance', 0.5))
        self._max_dist.setValue(self._settings.camera.get('max_distance', 20.0))

        self._rot_speed.setValue(self._settings.camera.get('rotation_speed', 0.01))
        self._zoom_speed.setValue(self._settings.camera.get('zoom_speed', 0.1))
        self._pan_speed.setValue(self._settings.camera.get('pan_speed', 0.001))

        # Keyboard movement speeds
        self._keyboard_speed.setValue(self._settings.camera.get('keyboard_movement_speed', 0.05))
        self._keyboard_speed_slow.setValue(self._settings.camera.get('keyboard_movement_speed_slow', 0.02))
        self._keyboard_speed_fast.setValue(self._settings.camera.get('keyboard_movement_speed_fast', 0.10))

        self._target_on_select.setChecked(self._settings.camera.get('target_on_select', True))
        self._smooth_transitions.setChecked(self._settings.camera.get('smooth_transitions', True))
        self._auto_rotate.setChecked(self._settings.camera.get('auto_rotate', False))

        # View mode
        self._head_look_mode.setChecked(self._settings.camera.get('head_look_mode', False))

    def _on_setting_changed(self) -> None:
        """Handle setting changes."""
        self._settings.camera.set('default_fov', float(self._default_fov.value()))
        self._settings.camera.set('min_fov', float(self._min_fov.value()))
        self._settings.camera.set('max_fov', float(self._max_fov.value()))

        self._settings.camera.set('default_distance', self._default_dist.value())
        self._settings.camera.set('min_distance', self._min_dist.value())
        self._settings.camera.set('max_distance', self._max_dist.value())

        self._settings.camera.set('rotation_speed', self._rot_speed.value())
        self._settings.camera.set('zoom_speed', self._zoom_speed.value())
        self._settings.camera.set('pan_speed', self._pan_speed.value())

        # Keyboard movement speeds
        self._settings.camera.set('keyboard_movement_speed', self._keyboard_speed.value())
        self._settings.camera.set('keyboard_movement_speed_slow', self._keyboard_speed_slow.value())
        self._settings.camera.set('keyboard_movement_speed_fast', self._keyboard_speed_fast.value())

        self._settings.camera.set('target_on_select', self._target_on_select.isChecked())
        self._settings.camera.set('smooth_transitions', self._smooth_transitions.isChecked())
        self._settings.camera.set('auto_rotate', self._auto_rotate.isChecked())

        # View mode
        self._settings.camera.set('head_look_mode', self._head_look_mode.isChecked())

        self.settings_changed.emit()

    def _reset_to_defaults(self) -> None:
        """Reset to defaults."""
        self._settings.camera.reset_to_defaults()
        self._load_settings()
        self.settings_changed.emit()


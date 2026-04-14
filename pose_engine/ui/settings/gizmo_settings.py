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


class GizmoSettingsWidget(QWidget):
    """Widget for editing gizmo settings."""
    
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
        
        # Scale settings
        scale_group = QGroupBox("Scale")
        scale_layout = QGridLayout(scale_group)
        
        scale_layout.addWidget(QLabel("Base Scale:"), 0, 0)
        self._base_scale = QDoubleSpinBox()
        self._base_scale.setRange(0.1, 1.0)
        self._base_scale.setSingleStep(0.05)
        self._base_scale.valueChanged.connect(self._on_setting_changed)
        scale_layout.addWidget(self._base_scale, 0, 1)
        
        scale_layout.addWidget(QLabel("Min Scale:"), 1, 0)
        self._min_scale = QDoubleSpinBox()
        self._min_scale.setRange(0.01, 0.5)
        self._min_scale.setSingleStep(0.01)
        self._min_scale.setDecimals(2)
        self._min_scale.valueChanged.connect(self._on_setting_changed)
        scale_layout.addWidget(self._min_scale, 1, 1)
        
        scale_layout.addWidget(QLabel("Max Scale:"), 2, 0)
        self._max_scale = QDoubleSpinBox()
        self._max_scale.setRange(0.5, 5.0)
        self._max_scale.setSingleStep(0.1)
        self._max_scale.valueChanged.connect(self._on_setting_changed)
        scale_layout.addWidget(self._max_scale, 2, 1)
        
        layout.addWidget(scale_group)
        
        # Sensitivity settings
        sens_group = QGroupBox("Sensitivity")
        sens_layout = QGridLayout(sens_group)
        
        sens_layout.addWidget(QLabel("Rotation:"), 0, 0)
        self._rot_sens = QDoubleSpinBox()
        self._rot_sens.setRange(0.1, 5.0)
        self._rot_sens.setSingleStep(0.1)
        self._rot_sens.valueChanged.connect(self._on_setting_changed)
        sens_layout.addWidget(self._rot_sens, 0, 1)
        
        sens_layout.addWidget(QLabel("Movement:"), 1, 0)
        self._move_sens = QDoubleSpinBox()
        self._move_sens.setRange(0.1, 5.0)
        self._move_sens.setSingleStep(0.1)
        self._move_sens.valueChanged.connect(self._on_setting_changed)
        sens_layout.addWidget(self._move_sens, 1, 1)
        
        sens_layout.addWidget(QLabel("Scale:"), 2, 0)
        self._scale_sens = QDoubleSpinBox()
        self._scale_sens.setRange(0.1, 5.0)
        self._scale_sens.setSingleStep(0.1)
        self._scale_sens.valueChanged.connect(self._on_setting_changed)
        sens_layout.addWidget(self._scale_sens, 2, 1)
        
        layout.addWidget(sens_group)
        
        # Color scheme
        color_group = QGroupBox("Color Scheme")
        color_layout = QHBoxLayout(color_group)
        
        self._color_scheme = QComboBox()
        self._color_scheme.addItems(list(GIZMO_COLOR_SCHEMES.keys()))
        self._color_scheme.currentTextChanged.connect(self._on_setting_changed)
        color_layout.addWidget(self._color_scheme)
        
        layout.addWidget(color_group)
        
        # Reset button
        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.clicked.connect(self._reset_to_defaults)
        layout.addWidget(reset_btn)
        
        layout.addStretch()
    
    def _load_settings(self) -> None:
        """Load current settings."""
        self._base_scale.setValue(self._settings.gizmo.get('base_scale', 0.2))
        self._min_scale.setValue(self._settings.gizmo.get('min_scale', 0.05))
        self._max_scale.setValue(self._settings.gizmo.get('max_scale', 2.0))
        self._rot_sens.setValue(self._settings.gizmo.get('rotation_sensitivity', 1.0))
        self._move_sens.setValue(self._settings.gizmo.get('movement_sensitivity', 1.0))
        self._scale_sens.setValue(self._settings.gizmo.get('scale_sensitivity', 1.0))
        
        scheme = self._settings.gizmo.get('color_scheme', 'blender')
        index = self._color_scheme.findText(scheme)
        if index >= 0:
            self._color_scheme.setCurrentIndex(index)
    
    def _on_setting_changed(self) -> None:
        """Handle setting changes."""
        self._settings.gizmo.set('base_scale', self._base_scale.value())
        self._settings.gizmo.set('min_scale', self._min_scale.value())
        self._settings.gizmo.set('max_scale', self._max_scale.value())
        self._settings.gizmo.set('rotation_sensitivity', self._rot_sens.value())
        self._settings.gizmo.set('movement_sensitivity', self._move_sens.value())
        self._settings.gizmo.set('scale_sensitivity', self._scale_sens.value())
        self._settings.gizmo.set('color_scheme', self._color_scheme.currentText())
        self.settings_changed.emit()
    
    def _reset_to_defaults(self) -> None:
        """Reset to defaults."""
        self._settings.gizmo.reset_to_defaults()
        self._load_settings()
        self.settings_changed.emit()


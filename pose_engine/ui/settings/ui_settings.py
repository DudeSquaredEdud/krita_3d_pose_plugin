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


class UISettingsWidget(QWidget):
    """Widget for editing UI settings."""
    
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
        
        # Default visibility
        vis_group = QGroupBox("Default Visibility")
        vis_layout = QVBoxLayout(vis_group)
        
        self._show_mesh = QCheckBox("Show Mesh on Load")
        self._show_mesh.toggled.connect(self._on_setting_changed)
        vis_layout.addWidget(self._show_mesh)
        
        self._show_skeleton = QCheckBox("Show Skeleton on Load")
        self._show_skeleton.toggled.connect(self._on_setting_changed)
        vis_layout.addWidget(self._show_skeleton)
        
        self._show_joints = QCheckBox("Show Joints on Load")
        self._show_joints.toggled.connect(self._on_setting_changed)
        vis_layout.addWidget(self._show_joints)
        
        self._show_gizmo = QCheckBox("Show Gizmo on Load")
        self._show_gizmo.toggled.connect(self._on_setting_changed)
        vis_layout.addWidget(self._show_gizmo)
        
        layout.addWidget(vis_group)
        
        # Theme
        theme_group = QGroupBox("Theme")
        theme_layout = QHBoxLayout(theme_group)
        
        theme_layout.addWidget(QLabel("Color Theme:"))
        self._theme = QComboBox()
        self._theme.addItems(list(UI_THEMES.keys()))
        self._theme.currentTextChanged.connect(self._on_setting_changed)
        theme_layout.addWidget(self._theme)
        
        layout.addWidget(theme_group)
        
        # Joint settings
        joint_group = QGroupBox("Joint Display")
        joint_layout = QGridLayout(joint_group)
        
        joint_layout.addWidget(QLabel("Joint Scale:"), 0, 0)
        self._joint_scale = QDoubleSpinBox()
        self._joint_scale.setRange(0.05, 0.5)
        self._joint_scale.setSingleStep(0.01)
        self._joint_scale.valueChanged.connect(self._on_setting_changed)
        joint_layout.addWidget(self._joint_scale, 0, 1)
        
        layout.addWidget(joint_group)
        
        # Reset button
        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.clicked.connect(self._reset_to_defaults)
        layout.addWidget(reset_btn)
        
        layout.addStretch()
    
    def _load_settings(self) -> None:
        """Load current settings."""
        self._show_mesh.setChecked(self._settings.ui.get('show_mesh_default', True))
        self._show_skeleton.setChecked(self._settings.ui.get('show_skeleton_default', True))
        self._show_joints.setChecked(self._settings.ui.get('show_joints_default', True))
        self._show_gizmo.setChecked(self._settings.ui.get('show_gizmo_default', True))
        
        theme = self._settings.ui.get('theme', 'dark')
        index = self._theme.findText(theme)
        if index >= 0:
            self._theme.setCurrentIndex(index)
        
        self._joint_scale.setValue(self._settings.ui.get('joint_scale', 0.15))
    
    def _on_setting_changed(self) -> None:
        """Handle setting changes."""
        self._settings.ui.set('show_mesh_default', self._show_mesh.isChecked())
        self._settings.ui.set('show_skeleton_default', self._show_skeleton.isChecked())
        self._settings.ui.set('show_joints_default', self._show_joints.isChecked())
        self._settings.ui.set('show_gizmo_default', self._show_gizmo.isChecked())
        self._settings.ui.set('theme', self._theme.currentText())
        self._settings.ui.set('joint_scale', self._joint_scale.value())
        self.settings_changed.emit()
    
    def _reset_to_defaults(self) -> None:
        """Reset to defaults."""
        self._settings.ui.reset_to_defaults()
        self._load_settings()
        self.settings_changed.emit()


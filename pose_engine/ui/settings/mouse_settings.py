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


class MouseSettingsWidget(QWidget):
    """Widget for editing mouse settings."""
    
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
        
        # Sensitivity settings
        sens_group = QGroupBox("Sensitivity")
        sens_layout = QGridLayout(sens_group)
        
        # Rotate sensitivity
        sens_layout.addWidget(QLabel("Rotate:"), 0, 0)
        self._rotate_sens = QDoubleSpinBox()
        self._rotate_sens.setRange(0.1, 5.0)
        self._rotate_sens.setSingleStep(0.1)
        self._rotate_sens.valueChanged.connect(self._on_sensitivity_changed)
        sens_layout.addWidget(self._rotate_sens, 0, 1)
        
        # Pan sensitivity
        sens_layout.addWidget(QLabel("Pan:"), 1, 0)
        self._pan_sens = QDoubleSpinBox()
        self._pan_sens.setRange(0.1, 5.0)
        self._pan_sens.setSingleStep(0.1)
        self._pan_sens.valueChanged.connect(self._on_sensitivity_changed)
        sens_layout.addWidget(self._pan_sens, 1, 1)
        
        # Zoom sensitivity
        sens_layout.addWidget(QLabel("Zoom:"), 2, 0)
        self._zoom_sens = QDoubleSpinBox()
        self._zoom_sens.setRange(0.1, 5.0)
        self._zoom_sens.setSingleStep(0.1)
        self._zoom_sens.valueChanged.connect(self._on_sensitivity_changed)
        sens_layout.addWidget(self._zoom_sens, 2, 1)
        
        layout.addWidget(sens_group)
        
        # Scroll wheel settings
        scroll_group = QGroupBox("Scroll Wheel")
        scroll_layout = QGridLayout(scroll_group)
        
        scroll_layout.addWidget(QLabel("Zoom Speed:"), 0, 0)
        self._scroll_zoom = QDoubleSpinBox()
        self._scroll_zoom.setRange(0.01, 0.5)
        self._scroll_zoom.setSingleStep(0.01)
        self._scroll_zoom.setDecimals(2)
        self._scroll_zoom.valueChanged.connect(self._on_setting_changed)
        scroll_layout.addWidget(self._scroll_zoom, 0, 1)
        
        scroll_layout.addWidget(QLabel("Dolly Speed:"), 1, 0)
        self._scroll_dolly = QDoubleSpinBox()
        self._scroll_dolly.setRange(0.01, 0.5)
        self._scroll_dolly.setSingleStep(0.01)
        self._scroll_dolly.setDecimals(2)
        self._scroll_dolly.valueChanged.connect(self._on_setting_changed)
        scroll_layout.addWidget(self._scroll_dolly, 1, 1)
        
        layout.addWidget(scroll_group)
        
        # Reset button
        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.clicked.connect(self._reset_to_defaults)
        layout.addWidget(reset_btn)
        
        layout.addStretch()
    
    def _load_settings(self) -> None:
        """Load current settings."""
        self._rotate_sens.setValue(self._settings.mouse.get_sensitivity('rotate'))
        self._pan_sens.setValue(self._settings.mouse.get_sensitivity('pan'))
        self._zoom_sens.setValue(self._settings.mouse.get_sensitivity('zoom'))
        self._scroll_zoom.setValue(self._settings.mouse.get_scroll_zoom_speed())
        self._scroll_dolly.setValue(self._settings.mouse.get_scroll_dolly_speed())
    
    def _on_sensitivity_changed(self) -> None:
        """Handle sensitivity changes."""
        self._settings.mouse.set_sensitivity('rotate', self._rotate_sens.value())
        self._settings.mouse.set_sensitivity('pan', self._pan_sens.value())
        self._settings.mouse.set_sensitivity('zoom', self._zoom_sens.value())
        self.settings_changed.emit()
    
    def _on_setting_changed(self) -> None:
        """Handle other setting changes."""
        # Settings are updated directly via valueChanged signals
        self.settings_changed.emit()
    
    def _reset_to_defaults(self) -> None:
        """Reset to defaults."""
        self._settings.mouse.reset_to_defaults()
        self._load_settings()
        self.settings_changed.emit()


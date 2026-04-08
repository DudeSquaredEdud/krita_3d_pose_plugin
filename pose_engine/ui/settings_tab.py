"""
Quick Settings Tab - Fast Access Settings Panel
================================================

Provides a minimal settings tab for quick access to frequently changed options.
Designed to complement the Advanced Settings dialog, not duplicate it.

This tab focuses on:
- Quick camera controls (FOV, reset, frame)
- Quick theme selection
- Link to Advanced Settings

NOTE: Visibility toggles and Gizmo mode are intentionally NOT included here
because they are already available in:
- Bones tab (gizmo mode controls)
- Advanced Settings > UI (visibility defaults)
"""

from typing import Optional

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QPushButton, QSlider, QLabel, QComboBox
)
from PyQt5.QtCore import Qt, pyqtSignal

from ..settings import PluginSettings


class QuickSettingsTab(QWidget):
    """
    Quick settings tab for frequently accessed settings.

    This is a streamlined panel that provides quick access to:
    - Camera FOV adjustment
    - Camera reset/frame buttons
    - Theme selection
    - Link to Advanced Settings

    Signals:
    settings_changed: Emitted when any setting changes
    advanced_settings_requested: Emitted when user clicks Advanced Settings
    reset_camera_requested: Emitted when user clicks Reset Camera
    frame_model_requested: Emitted when user clicks Frame Model
    """

    settings_changed = pyqtSignal()
    advanced_settings_requested = pyqtSignal()
    reset_camera_requested = pyqtSignal()
    frame_model_requested = pyqtSignal()

    def __init__(self, settings: PluginSettings, parent: Optional[QWidget] = None):
        """
        Create the quick settings tab.

        Args:
            settings: PluginSettings instance to manage
            parent: Optional parent widget
        """
        super().__init__(parent)
        self._settings = settings
        self._updating_from_settings = False

        self._setup_ui()
        self._load_from_settings()

    def _setup_ui(self) -> None:
        """Set up the UI components using standard widgets."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        # === Camera Section ===
        camera_group = QGroupBox("Camera")
        camera_layout = QVBoxLayout(camera_group)
        camera_layout.setSpacing(8)

        # FOV slider
        fov_layout = QHBoxLayout()
        fov_label = QLabel("FOV:")
        fov_label.setMinimumWidth(40)
        fov_layout.addWidget(fov_label)

        self._fov_slider = QSlider(Qt.Horizontal)
        self._fov_slider.setRange(30, 120)
        self._fov_slider.setValue(45)
        self._fov_slider.valueChanged.connect(self._on_fov_changed)
        fov_layout.addWidget(self._fov_slider)

        self._fov_value_label = QLabel("45°")
        self._fov_value_label.setMinimumWidth(40)
        fov_layout.addWidget(self._fov_value_label)
        camera_layout.addLayout(fov_layout)

        # Camera action buttons
        cam_btn_layout = QHBoxLayout()

        self._reset_camera_btn = QPushButton("Reset")
        self._reset_camera_btn.clicked.connect(self._on_reset_camera)
        cam_btn_layout.addWidget(self._reset_camera_btn)

        self._frame_model_btn = QPushButton("Frame")
        self._frame_model_btn.clicked.connect(self._on_frame_model)
        cam_btn_layout.addWidget(self._frame_model_btn)

        camera_layout.addLayout(cam_btn_layout)

        layout.addWidget(camera_group)

        # === Theme Section ===
        theme_group = QGroupBox("Theme")
        theme_layout = QHBoxLayout(theme_group)

        self._theme_combo = QComboBox()
        self._theme_combo.addItems(["Dark", "Light", "Krita"])
        self._theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        theme_layout.addWidget(self._theme_combo)

        layout.addWidget(theme_group)

        # Spacer
        layout.addStretch()

        # === Advanced Settings Button ===
        advanced_btn = QPushButton("Advanced Settings...")
        advanced_btn.clicked.connect(self.advanced_settings_requested)
        layout.addWidget(advanced_btn)

    def _load_from_settings(self) -> None:
        """Load current values from settings."""
        self._updating_from_settings = True

        # Load camera FOV
        fov = self._settings.camera.get('default_fov', 45.0)
        self._fov_slider.setValue(int(fov))
        self._fov_value_label.setText(f"{int(fov)}°")

        # Load theme
        theme = self._settings.ui.get('theme', 'dark')
        theme_index = {'dark': 0, 'light': 1, 'krita': 2}.get(theme, 0)
        self._theme_combo.setCurrentIndex(theme_index)

        self._updating_from_settings = False

    def _on_fov_changed(self, value: int) -> None:
        """Handle FOV slider changes."""
        self._fov_value_label.setText(f"{value}°")

        if not self._updating_from_settings:
            self._settings.camera.set('default_fov', float(value))
            self.settings_changed.emit()

    def _on_theme_changed(self, index: int) -> None:
        """Handle theme selection changes."""
        if self._updating_from_settings:
            return

        themes = ['dark', 'light', 'krita']
        if 0 <= index < len(themes):
            self._settings.ui.set('theme', themes[index])
            self.settings_changed.emit()

    def _on_reset_camera(self) -> None:
        """Handle reset camera button."""
        self.reset_camera_requested.emit()

    def _on_frame_model(self) -> None:
        """Handle frame model button."""
        self.frame_model_requested.emit()

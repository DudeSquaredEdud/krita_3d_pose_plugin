"""
Krita 3D Editor Launcher Docker
================================

A minimal docker panel that provides buttons to open the 3D editor window
and access advanced settings. This solves keyboard focus issues by having
the editor in a separate window.
"""

import os
import sys
from typing import Optional

# Ensure pose_engine is in path
from pose_engine.path_setup import ensure_path
ensure_path()

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from krita import DockWidget

# Setup logger
from pose_engine.logger import get_logger
logger = get_logger(__name__)

# Import settings
try:
    from pose_engine.settings import PluginSettings
    from pose_engine.ui.settings_dialog import AdvancedSettingsDialog
    from pose_engine.ui.styles import Colors
except ImportError as e:
    logger.warning(f"Import error: {e}")
    PluginSettings = None
    AdvancedSettingsDialog = None
    Colors = None

# Import editor window
try:
    from .editor_window import PoseEditorWindow
except ImportError:
    PoseEditorWindow = None


class Krita3DLauncherDocker(DockWidget):
    """
    Minimal docker panel with launcher buttons.
    
    Provides:
    - "Open 3D Editor" button (blue) - opens the full editor window
    - "Advanced Settings" button - opens settings dialog
    """
    
    def __init__(self):
        super().__init__()
        
        self.setWindowTitle("3D Pose")
        
        # Initialize settings
        self._settings = None
        if PluginSettings:
            try:
                self._settings = PluginSettings()
                self._settings.load()
            except Exception as e:
                logger.error(f"Failed to initialize settings: {e}")
        
        # Editor window reference
        self._editor_window = None
        
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        """Set up the minimal launcher UI."""
        # Main widget
        main_widget = QWidget()
        self.setWidget(main_widget)
        
        layout = QVBoxLayout(main_widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # Title
        title = QLabel("Krita 3D")
        title.setAlignment(Qt.AlignLeft)
        title.setStyleSheet(f"""
            font-size: 14px;
            font-weight: bold;
            color: {Colors.TEXT_PRIMARY if Colors else '#E0E0E0'};
            padding: 5px;
        """)
        layout.addWidget(title)

        # Open Editor button (blue)
        self._open_editor_btn = QPushButton("Open 3D Editor")
        self._open_editor_btn.setMinimumHeight(40)
        self._open_editor_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.PRIMARY if Colors else '#2196F3'};
                color: white;
                font-size: 13px;
                font-weight: bold;
                border: none;
                border-radius: 6px;
                padding: 10px;
            }}
            QPushButton:hover {{
                background-color: {Colors.PRIMARY_LIGHT if Colors else '#42A5F5'};
            }}
            QPushButton:pressed {{
                background-color: {Colors.PRIMARY_DARK if Colors else '#1976D2'};
            }}
        """)
        self._open_editor_btn.clicked.connect(self._on_open_editor)
        layout.addWidget(self._open_editor_btn)

        # Button row with Settings on the left
        button_row = QHBoxLayout()
        button_row.setSpacing(10)
        
        # Advanced Settings button
        self._settings_btn = QPushButton("Advanced Settings")
        self._settings_btn.setMinimumHeight(32)
        self._settings_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.SURFACE if Colors else '#3C3C3C'};
                color: {Colors.TEXT_PRIMARY if Colors else '#E0E0E0'};
                font-size: 11px;
                border: 1px solid {Colors.SURFACE_LIGHT if Colors else '#555555'};
                border-radius: 4px;
                padding: 8px;
            }}
            QPushButton:hover {{
                background-color: {Colors.SURFACE_LIGHT if Colors else '#4A4A4A'};
                border-color: {Colors.PRIMARY if Colors else '#2196F3'};
            }}
            QPushButton:pressed {{
                background-color: {Colors.BACKGROUND if Colors else '#2A2A2A'};
            }}
        """)
        self._settings_btn.clicked.connect(self._on_advanced_settings)
        button_row.addWidget(self._settings_btn)
        button_row.addStretch()
        
        layout.addLayout(button_row)
        
        # Status label
        self._status_label = QLabel("")
        self._status_label.setAlignment(Qt.AlignCenter)
        self._status_label.setStyleSheet(f"""
            color: {Colors.TEXT_SECONDARY if Colors else '#9E9E9E'};
            font-size: 10px;
            padding: 5px;
        """)
        layout.addWidget(self._status_label)
        
        # Add stretch to push everything up
        layout.addStretch()
        
        # Check if editor window is available
        if not PoseEditorWindow:
            self._open_editor_btn.setEnabled(False)
            self._open_editor_btn.setText("Editor Unavailable")
            self._status_label.setText("OpenGL not available")
    
    def _on_open_editor(self) -> None:
        """Open the 3D editor window."""
        if not PoseEditorWindow:
            return
        
        # Create window if needed
        if self._editor_window is None:
            self._editor_window = PoseEditorWindow()
        
        # Show and raise the window
        self._editor_window.show()
        self._editor_window.raise_()
        self._editor_window.activateWindow()
        
        self._status_label.setText("Editor open")
    
    def _on_advanced_settings(self) -> None:
        """Open advanced settings dialog."""
        if AdvancedSettingsDialog and self._settings:
            dialog = AdvancedSettingsDialog(self._settings, self)
            dialog.exec_()
        else:
            self._status_label.setText("Settings unavailable")
    
    def canvasChanged(self, canvas):
        """Handle canvas change (required by Krita)."""
        pass

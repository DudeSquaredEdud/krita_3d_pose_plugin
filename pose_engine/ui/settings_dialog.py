"""
Advanced Settings Dialog - Main Dialog
======================================

Provides a comprehensive settings dialog with categorized settings
and an interactive key binding editor.

This module contains only the main AdvancedSettingsDialog class.
Individual settings widgets are in the settings/ subpackage.
"""

from typing import Optional

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QPushButton, QMessageBox
)
from PyQt5.QtCore import pyqtSignal

from ..settings import PluginSettings
from .settings import (
    KeyboardSettingsWidget,
    MouseSettingsWidget,
    GizmoSettingsWidget,
    CameraSettingsWidget,
    UISettingsWidget,
)


class AdvancedSettingsDialog(QDialog):
    """
    Main advanced settings dialog with tabbed interface.

    Provides comprehensive settings editing with:
    - Keyboard shortcuts with interactive key capture
    - Mouse sensitivity and bindings
    - Gizmo appearance and behavior
    - Camera settings
    - UI preferences
    """

    settings_saved = pyqtSignal()

    def __init__(self, settings: PluginSettings, parent=None):
        super().__init__(parent)
        self._settings = settings

        self.setWindowTitle("Advanced Settings")
        self.setMinimumSize(600, 500)
        self.resize(700, 600)

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)

        # Tab widget
        self._tabs = QTabWidget()
        self._tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #4A6572;
                border-radius: 4px;
            }
            QTabBar::tab {
                background-color: #34495E;
                padding: 8px 16px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background-color: #3498DB;
            }
            QTabBar::tab:hover {
                background-color: #4A6572;
            }
        """)

        # Create category widgets
        self._keyboard_widget = KeyboardSettingsWidget(self._settings)
        self._keyboard_widget.bindings_changed.connect(self._mark_modified)
        self._tabs.addTab(self._keyboard_widget, "⌨️ Keyboard")

        self._mouse_widget = MouseSettingsWidget(self._settings)
        self._mouse_widget.settings_changed.connect(self._mark_modified)
        self._tabs.addTab(self._mouse_widget, "🖱️ Mouse")

        self._gizmo_widget = GizmoSettingsWidget(self._settings)
        self._gizmo_widget.settings_changed.connect(self._mark_modified)
        self._tabs.addTab(self._gizmo_widget, "🎯 Gizmo")

        self._camera_widget = CameraSettingsWidget(self._settings)
        self._camera_widget.settings_changed.connect(self._mark_modified)
        self._tabs.addTab(self._camera_widget, "📷 Camera")

        self._ui_widget = UISettingsWidget(self._settings)
        self._ui_widget.settings_changed.connect(self._mark_modified)
        self._tabs.addTab(self._ui_widget, "🎨 UI")

        layout.addWidget(self._tabs)

        # Bottom buttons
        btn_layout = QHBoxLayout()

        reset_all_btn = QPushButton("Reset All to Defaults")
        reset_all_btn.clicked.connect(self._reset_all)
        btn_layout.addWidget(reset_all_btn)

        btn_layout.addStretch()

        export_btn = QPushButton("Export...")
        export_btn.clicked.connect(self._export_settings)
        btn_layout.addWidget(export_btn)

        import_btn = QPushButton("Import...")
        import_btn.clicked.connect(self._import_settings)
        btn_layout.addWidget(import_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        save_btn = QPushButton("Save")
        save_btn.setDefault(True)
        save_btn.clicked.connect(self._save_and_close)
        btn_layout.addWidget(save_btn)

        layout.addLayout(btn_layout)

    def _mark_modified(self) -> None:
        """Mark settings as modified."""
        self._settings._modified = True

    def _reset_all(self) -> None:
        """Reset all settings to defaults."""
        reply = QMessageBox.question(
            self, "Reset All Settings",
            "Are you sure you want to reset ALL settings to defaults?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self._settings.reset_all_to_defaults()
            self._keyboard_widget._load_bindings()
            self._mouse_widget._load_settings()
            self._gizmo_widget._load_settings()
            self._camera_widget._load_settings()
            self._ui_widget._load_settings()

    def _export_settings(self) -> None:
        """Export settings to a file."""
        from PyQt5.QtWidgets import QFileDialog

        filepath, _ = QFileDialog.getSaveFileName(
            self, "Export Settings",
            "3d_pose_settings.json",
            "JSON Files (*.json)"
        )

        if filepath:
            if self._settings.export_to_file(filepath):
                QMessageBox.information(self, "Export Successful", f"Settings exported to:\n{filepath}")
            else:
                QMessageBox.warning(self, "Export Failed", "Failed to export settings.")

    def _import_settings(self) -> None:
        """Import settings from a file."""
        from PyQt5.QtWidgets import QFileDialog

        filepath, _ = QFileDialog.getOpenFileName(
            self, "Import Settings",
            "",
            "JSON Files (*.json)"
        )

        if filepath:
            if self._settings.import_from_file(filepath):
                self._keyboard_widget._load_bindings()
                self._mouse_widget._load_settings()
                self._gizmo_widget._load_settings()
                self._camera_widget._load_settings()
                self._ui_widget._load_settings()
                QMessageBox.information(self, "Import Successful", "Settings imported successfully.")
            else:
                QMessageBox.warning(self, "Import Failed", "Failed to import settings.")

    def _save_and_close(self) -> None:
        """Save settings and close the dialog."""
        if self._settings.save():
            self.settings_saved.emit()
            self.accept()
        else:
            QMessageBox.warning(self, "Save Failed", "Failed to save settings.")

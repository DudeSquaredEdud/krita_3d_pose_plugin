"""
Scene Tab - Scene Management UI
================================

Provides UI for managing scenes including:
- Scene info display
- Save/load operations
- Export for sharing
- Scene settings quick access
"""

import os
from datetime import datetime
from typing import Optional, TYPE_CHECKING

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QPushButton, QTreeWidget, QTreeWidgetItem,
    QFileDialog, QMessageBox, QCheckBox, QSpinBox,
    QDoubleSpinBox, QFrame, QSplitter
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QColor

if TYPE_CHECKING:
    from pose_engine.project_scene import ProjectScene


class SceneTab(QWidget):
    """
    Tab widget for scene management.
    
    Provides controls for:
    - Viewing scene info (name, models, last saved)
    - Saving/loading scenes
    - Exporting for sharing
    - Quick scene settings
    """
    
    # Signals
    save_requested = pyqtSignal()
    save_as_requested = pyqtSignal(str) # file_path
    load_requested = pyqtSignal(str) # file_path
    export_requested = pyqtSignal(str) # export_path
    new_scene_requested = pyqtSignal()
    reload_from_project_requested = pyqtSignal() # Reload scene for current Krita project
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._project_scene: Optional['ProjectScene'] = None
        self._setup_ui()
        
    def set_project_scene(self, project_scene: 'ProjectScene'):
        """Set the project scene to manage."""
        self._project_scene = project_scene
        
        # Connect signals
        project_scene.scene_saved.connect(self._on_scene_saved)
        project_scene.scene_loaded.connect(self._on_scene_loaded)
        project_scene.scene_changed.connect(self._on_scene_changed)
        
        self._update_info()
        
    def _setup_ui(self):
        """Set up the UI layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(10)
        
        # Scene Info Group
        info_group = QGroupBox("Scene Info")
        info_layout = QVBoxLayout(info_group)
        
        # Scene name
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Name:"))
        self._name_label = QLabel("Untitled Scene")
        self._name_label.setStyleSheet("font-weight: bold;")
        name_layout.addWidget(self._name_label)
        name_layout.addStretch()
        info_layout.addLayout(name_layout)
        
        # Model count
        models_layout = QHBoxLayout()
        models_layout.addWidget(QLabel("Models:"))
        self._model_count_label = QLabel("0")
        models_layout.addWidget(self._model_count_label)
        models_layout.addStretch()
        info_layout.addLayout(models_layout)
        
        # Status
        status_layout = QHBoxLayout()
        status_layout.addWidget(QLabel("Status:"))
        self._status_label = QLabel("No scene loaded")
        self._status_label.setStyleSheet("color: #7F8C8D;")
        status_layout.addWidget(self._status_label)
        status_layout.addStretch()
        info_layout.addLayout(status_layout)
        
        # Last saved
        saved_layout = QHBoxLayout()
        saved_layout.addWidget(QLabel("Last saved:"))
        self._saved_label = QLabel("Never")
        self._saved_label.setStyleSheet("color: #7F8C8D;")
        saved_layout.addWidget(self._saved_label)
        saved_layout.addStretch()
        info_layout.addLayout(saved_layout)
        
        # Unsaved indicator
        self._unsaved_label = QLabel("● Unsaved changes")
        self._unsaved_label.setStyleSheet("color: #E74C3C; font-weight: bold;")
        self._unsaved_label.setVisible(False)
        info_layout.addWidget(self._unsaved_label)
        
        layout.addWidget(info_group)
        
        # Models List Group
        models_group = QGroupBox("Models in Scene")
        models_layout = QVBoxLayout(models_group)
        
        self._model_tree = QTreeWidget()
        self._model_tree.setHeaderLabels(["Model", "Source"])
        self._model_tree.setRootIsDecorated(False)
        self._model_tree.setMaximumHeight(120)
        models_layout.addWidget(self._model_tree)
        
        layout.addWidget(models_group)
        
        # Actions Group
        actions_group = QGroupBox("Actions")
        actions_layout = QVBoxLayout(actions_group)
        
        # Save buttons
        save_layout = QHBoxLayout()
        
        self._save_btn = QPushButton("Save")
        self._save_btn.setToolTip("Save scene (Ctrl+S)")
        self._save_btn.clicked.connect(self._on_save)
        save_layout.addWidget(self._save_btn)
        
        self._save_as_btn = QPushButton("Save As...")
        self._save_as_btn.setToolTip("Save scene to a new file")
        self._save_as_btn.clicked.connect(self._on_save_as)
        save_layout.addWidget(self._save_as_btn)
        
        actions_layout.addLayout(save_layout)
        
        # Load/New buttons
        load_layout = QHBoxLayout()

        self._load_btn = QPushButton("Load...")
        self._load_btn.setToolTip("Load a scene file")
        self._load_btn.clicked.connect(self._on_load)
        load_layout.addWidget(self._load_btn)

        self._new_btn = QPushButton("New")
        self._new_btn.setToolTip("Create a new empty scene")
        self._new_btn.clicked.connect(self._on_new)
        load_layout.addWidget(self._new_btn)

        actions_layout.addLayout(load_layout)

        # Reload from project button
        reload_layout = QHBoxLayout()

        self._reload_btn = QPushButton("Reload from Project")
        self._reload_btn.setToolTip("Reload the scene associated with the current Krita project")
        self._reload_btn.clicked.connect(self._on_reload_from_project)
        reload_layout.addWidget(self._reload_btn)

        actions_layout.addLayout(reload_layout)
        
        # Export button
        export_layout = QHBoxLayout()
        
        self._export_btn = QPushButton("Export for Sharing...")
        self._export_btn.setToolTip("Export scene with all model files for sharing")
        self._export_btn.clicked.connect(self._on_export)
        export_layout.addWidget(self._export_btn)
        
        actions_layout.addLayout(export_layout)
        
        layout.addWidget(actions_group)
        
        # Quick Settings Group
        settings_group = QGroupBox("Quick Settings")
        settings_layout = QVBoxLayout(settings_group)
        
        # Auto-save toggle
        self._auto_save_cb = QCheckBox("Enable auto-save")
        self._auto_save_cb.setChecked(True)
        self._auto_save_cb.setToolTip("Automatically save scene when changes occur")
        settings_layout.addWidget(self._auto_save_cb)
        
        # Idle delay
        idle_layout = QHBoxLayout()
        idle_layout.addWidget(QLabel("Save after:"))
        self._idle_spin = QDoubleSpinBox()
        self._idle_spin.setRange(1.0, 60.0)
        self._idle_spin.setValue(5.0)
        self._idle_spin.setSuffix(" seconds idle")
        self._idle_spin.setToolTip("Time to wait after last change before saving")
        idle_layout.addWidget(self._idle_spin)
        settings_layout.addLayout(idle_layout)
        
        # Continuous interval
        continuous_layout = QHBoxLayout()
        continuous_layout.addWidget(QLabel("Max interval:"))
        self._continuous_spin = QDoubleSpinBox()
        self._continuous_spin.setRange(10.0, 300.0)
        self._continuous_spin.setValue(60.0)
        self._continuous_spin.setSuffix(" seconds")
        self._continuous_spin.setToolTip("Maximum time between saves during continuous changes")
        continuous_layout.addWidget(self._continuous_spin)
        settings_layout.addLayout(continuous_layout)
        
        # Backup count
        backup_layout = QHBoxLayout()
        backup_layout.addWidget(QLabel("Keep backups:"))
        self._backup_spin = QSpinBox()
        self._backup_spin.setRange(0, 20)
        self._backup_spin.setValue(5)
        self._backup_spin.setToolTip("Number of backup files to keep")
        backup_layout.addWidget(self._backup_spin)
        settings_layout.addLayout(backup_layout)
        
        # Apply settings button
        apply_btn = QPushButton("Apply Settings")
        apply_btn.clicked.connect(self._on_apply_settings)
        settings_layout.addWidget(apply_btn)
        
        layout.addWidget(settings_group)
        
        # Stretch at bottom
        layout.addStretch()
        
    def _update_info(self):
        """Update the scene info display."""
        if not self._project_scene:
            self._name_label.setText("No scene")
            self._model_count_label.setText("0")
            self._status_label.setText("No scene loaded")
            self._saved_label.setText("Never")
            self._unsaved_label.setVisible(False)
            self._model_tree.clear()
            return
        
        # Update name
        self._name_label.setText(self._project_scene._metadata.name)
        
        # Update model count
        model_count = self._project_scene.scene.get_model_count()
        self._model_count_label.setText(str(model_count))
        
        # Update status
        if self._project_scene.scene_file_path:
            self._status_label.setText(f"Linked to project")
            self._status_label.setStyleSheet("color: #27AE60;")
        else:
            self._status_label.setText("Not linked")
            self._status_label.setStyleSheet("color: #F39C12;")
        
        # Update last saved
        if self._project_scene._last_save_time:
            elapsed = datetime.now() - self._project_scene._last_save_time
            if elapsed.total_seconds() < 60:
                self._saved_label.setText("Just now")
            elif elapsed.total_seconds() < 3600:
                self._saved_label.setText(f"{int(elapsed.total_seconds() / 60)} min ago")
            else:
                self._saved_label.setText(self._project_scene._last_save_time.strftime("%H:%M"))
        else:
            self._saved_label.setText("Never")
        
        # Update unsaved indicator
        self._unsaved_label.setVisible(self._project_scene.has_unsaved_changes)
        
        # Update model tree
        self._model_tree.clear()
        for model in self._project_scene.scene.get_all_models():
            item = QTreeWidgetItem([model.name, model.source_file or "Unknown"])
            self._model_tree.addTopLevelItem(item)
        
        # Update settings
        settings = self._project_scene.settings
        self._idle_spin.setValue(settings.idle_save_delay)
        self._continuous_spin.setValue(settings.continuous_save_interval)
        self._backup_spin.setValue(settings.max_backup_files)
        
    def _on_scene_saved(self, file_path: str):
        """Handle scene saved signal."""
        self._update_info()
        # Show save success feedback
        self._status_label.setText("✓ Saved")
        self._status_label.setStyleSheet("color: #27AE60; font-weight: bold;")
        # Clear the success message after 3 seconds
        QTimer.singleShot(3000, self._clear_save_status)

    def _clear_save_status(self):
        """Clear the save status message."""
        if self._project_scene:
            if self._project_scene.has_unsaved_changes:
                self._status_label.setText("Unsaved changes")
                self._status_label.setStyleSheet("color: #E74C3C;")
            else:
                self._status_label.setText("Saved")
                self._status_label.setStyleSheet("color: #27AE60;")

    def _on_scene_loaded(self, file_path: str):
        """Handle scene loaded signal."""
        self._update_info()
        self._status_label.setText("✓ Loaded")
        self._status_label.setStyleSheet("color: #27AE60; font-weight: bold;")
        QTimer.singleShot(3000, self._clear_save_status)
        
    def _on_scene_changed(self):
        """Handle scene changed signal."""
        self._update_info()
        
    def _on_save(self):
        """Handle save button click."""
        if self._project_scene:
            if self._project_scene.scene_file_path:
                self._project_scene.save()
            else:
                # No file path - do Save As
                self._on_save_as()
                
    def _on_save_as(self):
        """Handle save as button click."""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Scene",
            "",
            f"3D Scene Files (*{self._project_scene.SCENE_EXTENSION if self._project_scene else '.k3dscene'});;All Files (*)"
        )
        if file_path:
            if self._project_scene:
                self._project_scene.save(file_path)
                
    def _on_load(self):
        """Handle load button click."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Scene",
            "",
            "3D Scene Files (*.k3dscene);;All Files (*)"
        )
        if file_path:
            if self._project_scene:
                self._project_scene.load(file_path)
                
    def _on_new(self):
        """Handle new button click."""
        if self._project_scene and self._project_scene.has_unsaved_changes:
            reply = QMessageBox.question(
                self,
                "Unsaved Changes",
                "Current scene has unsaved changes. Create new scene anyway?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.No:
                return
                
        self.new_scene_requested.emit()
        if self._project_scene:
            self._project_scene.new_scene()
        self._update_info()
        
    def _on_export(self):
        """Handle export button click."""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Scene for Sharing",
            "",
            "ZIP Archive (*.zip);;All Files (*)"
        )
        if file_path:
            if self._project_scene:
                self._project_scene.export_full(file_path)
                
    def _on_apply_settings(self):
        """Apply quick settings to project scene."""
        if self._project_scene:
            settings = self._project_scene.settings
            settings.idle_save_delay = self._idle_spin.value()
            settings.continuous_save_interval = self._continuous_spin.value()
            settings.max_backup_files = self._backup_spin.value()
            self._project_scene.settings = settings

            QMessageBox.information(
                self,
                "Settings Applied",
                "Scene settings have been updated."
            )

    def _on_reload_from_project(self):
        """Handle reload from project button click."""
        self.reload_from_project_requested.emit()

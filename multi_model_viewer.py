#!/usr/bin/env python3
"""
Multi-Model 3D Pose Viewer
==========================

A standalone application for viewing and posing multiple 3D models.
Run this to test loading and posing multiple models in the same scene.

Usage:
    python multi_model_viewer.py [model1.glb] [model2.glb] ...

Controls:
    Left mouse: Select bones / Rotate camera (when dragging on empty space)
    Middle mouse: Pan camera
    Right mouse: Rotate camera
    Scroll: Zoom
    F: Frame all models
    Shift+F: Frame selected model
    T: Toggle mesh visibility
    S: Toggle skeleton visibility
    G: Toggle gizmo mode (rotation/movement/scale)
    R: Reset camera
"""

import sys
import os

# Ensure pose_engine is in path
from pose_engine.path_setup import ensure_path
ensure_path()

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTreeWidget, QTreeWidgetItem, QGroupBox,
    QSplitter, QFileDialog, QCheckBox, QDoubleSpinBox,
    QMenu, QAction, QListWidget, QListWidgetItem, QSlider
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QSurfaceFormat, QColor, QFont

from pose_engine.ui.multi_viewport import MultiViewport3D
from pose_engine.ui.camera_panel import CameraPanel
from pose_engine.model_instance import ModelInstance
from pose_engine.scene import Scene
from pose_engine.pose_state import PoseSnapshot, PoseSerializer
from pose_engine.settings.settings import PluginSettings
from pose_engine.vec3 import Vec3


class MultiModelViewer(QMainWindow):
    """Multi-model 3D viewer window."""

    def __init__(self):
        """Create the viewer."""
        super().__init__()

        self.setWindowTitle("Multi-Model 3D Pose Viewer")
        self.resize(1400, 900)

        # Initialize settings
        self._settings = PluginSettings()

        self._setup_ui()

        # Initialize pose list
        self._refresh_pose_list()

        # Load models from command line
        if len(sys.argv) > 1:
            for i, path in enumerate(sys.argv[1:]):
                if os.path.exists(path):
                    QTimer.singleShot(100 + i * 100, lambda p=path: self._add_model(p))

    def _setup_ui(self) -> None:
        """Set up the UI."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QHBoxLayout(central_widget)

        # Left panel - controls
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(5, 5, 5, 5)

        # Model management
        models_group = QGroupBox("Models")
        models_layout = QVBoxLayout(models_group)

        # Model buttons
        btn_layout = QHBoxLayout()
        add_btn = QPushButton("Add Model")
        add_btn.clicked.connect(self._on_add_model)
        btn_layout.addWidget(add_btn)

        dup_btn = QPushButton("Duplicate")
        dup_btn.clicked.connect(self._on_duplicate_model)
        btn_layout.addWidget(dup_btn)

        rem_btn = QPushButton("Remove")
        rem_btn.clicked.connect(self._on_remove_model)
        btn_layout.addWidget(rem_btn)

        models_layout.addLayout(btn_layout)

        # Model tree
        self._model_tree = QTreeWidget()
        self._model_tree.setHeaderLabels(["Models"])
        self._model_tree.itemClicked.connect(self._on_model_tree_click)
        models_layout.addWidget(self._model_tree)

        left_layout.addWidget(models_group)

        # Bone tree
        bone_group = QGroupBox("Bones")
        bone_layout = QVBoxLayout(bone_group)

        self._bone_tree = QTreeWidget()
        self._bone_tree.setHeaderLabels(["Bone Hierarchy"])
        self._bone_tree.itemClicked.connect(self._on_bone_tree_click)
        bone_layout.addWidget(self._bone_tree)

        left_layout.addWidget(bone_group)

        # Visibility controls
        vis_group = QGroupBox("Visibility")
        vis_layout = QVBoxLayout(vis_group)

        self._show_mesh_cb = QCheckBox("Show Mesh")
        self._show_mesh_cb.setChecked(True)
        self._show_mesh_cb.toggled.connect(self._on_toggle_mesh)
        vis_layout.addWidget(self._show_mesh_cb)

        self._show_skeleton_cb = QCheckBox("Show Skeleton")
        self._show_skeleton_cb.setChecked(True)
        self._show_skeleton_cb.toggled.connect(self._on_toggle_skeleton)
        vis_layout.addWidget(self._show_skeleton_cb)

        self._show_joints_cb = QCheckBox("Show Joints")
        self._show_joints_cb.setChecked(True)
        self._show_joints_cb.toggled.connect(self._on_toggle_joints)
        vis_layout.addWidget(self._show_joints_cb)

        self._show_gizmo_cb = QCheckBox("Show Gizmo")
        self._show_gizmo_cb.setChecked(True)
        self._show_gizmo_cb.toggled.connect(self._on_toggle_gizmo)
        vis_layout.addWidget(self._show_gizmo_cb)

        left_layout.addWidget(vis_group)

        # Camera settings
        camera_group = QGroupBox("Camera")
        camera_layout = QVBoxLayout(camera_group)

        # FOV slider
        fov_layout = QHBoxLayout()
        fov_label = QLabel("FOV:")
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

        # Reset camera button
        # Speed slider
        speed_layout = QHBoxLayout()
        speed_label = QLabel("Speed:")
        speed_layout.addWidget(speed_label)

        self._speed_slider = QSlider(Qt.Horizontal)
        self._speed_slider.setRange(1, 100)
        self._speed_slider.setValue(50)
        self._speed_slider.valueChanged.connect(self._on_speed_changed)
        speed_layout.addWidget(self._speed_slider)

        self._speed_value_label = QLabel("1.0x")
        self._speed_value_label.setMinimumWidth(40)
        speed_layout.addWidget(self._speed_value_label)
        camera_layout.addLayout(speed_layout)

        # Reset camera button
        self._reset_camera_btn = QPushButton("Reset Camera")
        self._reset_camera_btn.clicked.connect(self._on_reset_camera)
        camera_layout.addWidget(self._reset_camera_btn)

        # Camera panel toggle button
        self._camera_panel_btn = QPushButton("📷 Camera Panel")
        self._camera_panel_btn.setCheckable(True)
        self._camera_panel_btn.setToolTip("Toggle floating camera panel (Shift+C)")
        self._camera_panel_btn.toggled.connect(self._on_toggle_camera_panel)
        camera_layout.addWidget(self._camera_panel_btn)

        left_layout.addWidget(camera_group)

        # Gizmo mode controls
        gizmo_group = QGroupBox("Gizmo Mode")
        gizmo_layout = QVBoxLayout(gizmo_group)

        # Toggle button layout
        toggle_layout = QHBoxLayout()

        self._rotation_btn = QPushButton("Rotate")
        self._rotation_btn.setCheckable(True)
        self._rotation_btn.setChecked(True)
        self._rotation_btn.clicked.connect(lambda: self._set_gizmo_mode("rotation"))
        toggle_layout.addWidget(self._rotation_btn)

        self._movement_btn = QPushButton("Move")
        self._movement_btn.setCheckable(True)
        self._movement_btn.clicked.connect(lambda: self._set_gizmo_mode("movement"))
        toggle_layout.addWidget(self._movement_btn)

        self._scale_btn = QPushButton("Scale")
        self._scale_btn.setCheckable(True)
        self._scale_btn.clicked.connect(lambda: self._set_gizmo_mode("scale"))
        toggle_layout.addWidget(self._scale_btn)

        gizmo_layout.addLayout(toggle_layout)

        # Single toggle button alternative
        self._toggle_mode_btn = QPushButton("Toggle Mode (G)")
        self._toggle_mode_btn.clicked.connect(self._toggle_gizmo_mode)
        gizmo_layout.addWidget(self._toggle_mode_btn)

        left_layout.addWidget(gizmo_group)

        # Poses group
        poses_group = QGroupBox("Poses")
        poses_layout = QVBoxLayout(poses_group)

        # Pose buttons
        pose_btn_layout = QHBoxLayout()

        load_pose_btn = QPushButton("Load Pose")
        load_pose_btn.clicked.connect(self._on_load_pose)
        pose_btn_layout.addWidget(load_pose_btn)

        save_pose_btn = QPushButton("Save Pose")
        save_pose_btn.clicked.connect(self._on_save_pose)
        pose_btn_layout.addWidget(save_pose_btn)

        poses_layout.addLayout(pose_btn_layout)

        # Pose list
        self._pose_list = QListWidget()
        self._pose_list.itemDoubleClicked.connect(self._on_pose_double_clicked)
        poses_layout.addWidget(self._pose_list)

        # Apply pose button
        apply_pose_btn = QPushButton("Apply Selected Pose")
        apply_pose_btn.clicked.connect(self._on_apply_pose)
        poses_layout.addWidget(apply_pose_btn)

        # Refresh poses button
        refresh_poses_btn = QPushButton("Refresh Pose List")
        refresh_poses_btn.clicked.connect(self._refresh_pose_list)
        poses_layout.addWidget(refresh_poses_btn)

        left_layout.addWidget(poses_group)

        # Status
        self._status_label = QLabel("No models loaded")
        left_layout.addWidget(self._status_label)

        left_layout.addStretch()

        # Splitter for resizable panels
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_panel)

        # Viewport
        self._viewport = MultiViewport3D()
        self._viewport.set_settings(self._settings)
        splitter.addWidget(self._viewport)

        splitter.setSizes([300, 1100])
        layout.addWidget(splitter)

        # Connect signals
        self._viewport.model_selected.connect(self._on_model_selected)
        self._viewport.bone_selected.connect(self._on_bone_selected)
        self._viewport.model_selection_changed.connect(self._on_model_selection_changed)

        # Create camera panel (hidden by default)
        self._camera_panel = None  # Lazy initialization

        # -------------------------------------------------------------------------
        # Model Management
        # -------------------------------------------------------------------------

    def _on_add_model(self) -> None:
        """Add a model via file dialog."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Add Model", "",
            "GLB Files (*.glb);;GLTF Files (*.gltf);;All Files (*)"
        )
        if file_path:
            self._add_model(file_path)

    def _add_model(self, file_path: str) -> None:
        """Add a model to the scene."""
        name = os.path.splitext(os.path.basename(file_path))[0]

        try:
            model = self._viewport.add_model(file_path, name)

            if model:
                self._rebuild_model_tree()
                self._rebuild_bone_tree()
                self._status_label.setText(f"Loaded: {name} ({model.get_bone_count()} bones)")
        except Exception as e:
            print(f"Error loading model: {e}")
            import traceback
            traceback.print_exc()

    def _on_duplicate_model(self) -> None:
        """Duplicate the selected model."""
        model = self._viewport.get_selected_model()
        if model:
            copy = self._viewport.duplicate_model(model.id)
            if copy:
                self._rebuild_model_tree()
                self._rebuild_bone_tree()
                self._status_label.setText(f"Duplicated: {copy.name}")

    def _on_remove_model(self) -> None:
        """Remove the selected model."""
        model = self._viewport.get_selected_model()
        if model:
            self._viewport.remove_model(model.id)
            self._rebuild_model_tree()
            self._rebuild_bone_tree()
            self._status_label.setText(f"Removed: {model.name}")

    def _rebuild_model_tree(self) -> None:
        """Rebuild the model tree with selection highlighting."""
        self._model_tree.clear()
        
        selected_model_id = self._viewport.get_scene().get_selected_model_id()

        scene = self._viewport.get_scene()
        for model in scene.get_all_models():
            item = QTreeWidgetItem([model.name])
            item.setData(0, Qt.UserRole, model.id)
            item.setCheckState(0, Qt.Checked if model.visible else Qt.Unchecked)
            
            # Highlight selected model
            if model.id == selected_model_id:
                item.setBackground(0, QColor(100, 150, 200, 100))
                font = item.font(0)
                font.setBold(True)
                item.setFont(0, font)

            # Add children (parented models)
            for child in model.get_children():
                child_item = QTreeWidgetItem([child.name])
                child_item.setData(0, Qt.UserRole, child.id)
                child_item.setCheckState(0, Qt.Checked if child.visible else Qt.Unchecked)
                item.addChild(child_item)

            self._model_tree.addTopLevelItem(item)

        self._model_tree.expandAll()

    def _rebuild_bone_tree(self) -> None:
        """Rebuild the bone tree with selection highlighting."""
        self._bone_tree.clear()

        selected_model_id = self._viewport.get_scene().get_selected_model_id()

        scene = self._viewport.get_scene()
        for model in scene.get_all_models():
            # Model item
            model_item = QTreeWidgetItem([model.name])
            model_item.setData(0, Qt.UserRole, f"model:{model.id}")

            # Highlight selected model
            if model.id == selected_model_id:
                model_item.setBackground(0, QColor(100, 150, 200, 100))
                font = model_item.font(0)
                font.setBold(True)
                model_item.setFont(0, font)

            # Add bones
            for root_bone in model.get_root_bones():
                self._add_bone_to_tree(root_bone, model_item, model.id)

            self._bone_tree.addTopLevelItem(model_item)

            # Expand only the model item, not the bones
            model_item.setExpanded(True)

    def _add_bone_to_tree(self, bone, parent_item, model_id: str) -> None:
        """Add bone to tree recursively."""
        item = QTreeWidgetItem([bone.name])
        item.setData(0, Qt.UserRole, f"bone:{model_id}:{bone.name}")

        for child in bone.children:
            self._add_bone_to_tree(child, item, model_id)

        parent_item.addChild(item)

        # Bones start collapsed
        item.setExpanded(False)

    # -------------------------------------------------------------------------
    # Tree Click Handlers
    # -------------------------------------------------------------------------

    def _on_model_tree_click(self, item: QTreeWidgetItem, column: int) -> None:
        """Handle model tree click."""
        model_id = item.data(0, Qt.UserRole)
        if model_id:
            # Check if clicking on checkbox
            self._viewport.set_model_visible(model_id, item.checkState(0) == Qt.Checked)
            self._viewport.select_model(model_id)
            self._rebuild_bone_tree()

    def _on_bone_tree_click(self, item: QTreeWidgetItem, column: int) -> None:
        """Handle bone tree click."""
        data = item.data(0, Qt.UserRole)
        if data and isinstance(data, str):
            parts = data.split(":")
            if parts[0] == "model":
                self._viewport.select_model(parts[1])
            elif parts[0] == "bone":
                self._viewport.select_bone(parts[1], parts[2])

    # -------------------------------------------------------------------------
    # Signal Handlers
    # -------------------------------------------------------------------------

    def _on_model_selected(self, model_id: str) -> None:
        """Handle model selection from viewport."""
        pass

    def _on_bone_selected(self, model_id: str, bone_name: str) -> None:
        """Handle bone selection from viewport."""
        self._status_label.setText(f"Selected: {model_id}/{bone_name}")

    def _on_model_selection_changed(self, model_id: str) -> None:
        """Handle model selection change from viewport."""
        self._rebuild_model_tree() # Update highlighting
        self._rebuild_bone_tree() # Update highlighting

    # -------------------------------------------------------------------------
    # Pose Management
    # -------------------------------------------------------------------------

    def _on_load_pose(self) -> None:
        """Load a pose from file and apply to selected model."""
        model = self._viewport.get_selected_model()
        if not model:
            self._status_label.setText("Select a model first")
            return
    
        poses_dir = os.path.join(_project_dir, "poses")
        if not os.path.isdir(poses_dir):
            os.makedirs(poses_dir, exist_ok=True)
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Load Pose", poses_dir,
            "JSON Files (*.json);;All Files (*)"
        )
        if file_path:
            self._apply_pose_file(file_path, model)
    
    def _on_save_pose(self) -> None:
        """Save the current pose of the selected model."""
        model = self._viewport.get_selected_model()
        if not model or not model.skeleton:
            self._status_label.setText("Select a model with skeleton first")
            return
    
        poses_dir = os.path.join(_project_dir, "poses")
        if not os.path.isdir(poses_dir):
            os.makedirs(poses_dir, exist_ok=True)
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Pose", os.path.join(poses_dir, f"{model.name}_pose.json"),
            "JSON Files (*.json);;All Files (*)"
        )
        if file_path:
            if PoseSerializer.save_pose(file_path, model.skeleton, model.name):
                self._status_label.setText(f"Saved pose: {os.path.basename(file_path)}")
                self._refresh_pose_list()
            else:
                self._status_label.setText("Failed to save pose")

    def _on_apply_pose(self) -> None:
        """Apply the selected pose from the list to the selected model."""
        model = self._viewport.get_selected_model()
        if not model:
            self._status_label.setText("Select a model first")
            return

        selected_item = self._pose_list.currentItem()
        if not selected_item:
            self._status_label.setText("Select a pose from the list")
            return

        pose_path = selected_item.data(Qt.UserRole)
        self._apply_pose_file(pose_path, model)

    def _on_pose_double_clicked(self, item: QListWidgetItem) -> None:
        """Handle double-click on pose list item - apply pose immediately."""
        model = self._viewport.get_selected_model()
        if not model:
            self._status_label.setText("Select a model first")
            return

        pose_path = item.data(Qt.UserRole)
        self._apply_pose_file(pose_path, model)

    def _apply_pose_file(self, file_path: str, model: ModelInstance) -> None:
        """Apply a pose file to a model."""
        if not model.skeleton:
            self._status_label.setText("Model has no skeleton")
            return

        snapshot = PoseSerializer.load_pose(file_path, model.skeleton)
        if snapshot:
            pose_name = os.path.splitext(os.path.basename(file_path))[0]
            self._status_label.setText(f"Applied pose: {pose_name}")
            self._viewport.update()
        else:
            self._status_label.setText(f"Failed to load pose: {file_path}")

    def _refresh_pose_list(self) -> None:
        """Refresh the list of available poses from the poses directory."""
        self._pose_list.clear()

        poses_dir = os.path.join(_project_dir, "poses")
        if not os.path.isdir(poses_dir):
            os.makedirs(poses_dir, exist_ok=True)
            return

        for filename in sorted(os.listdir(poses_dir)):
            if filename.endswith(".json"):
                file_path = os.path.join(poses_dir, filename)
                pose_name = os.path.splitext(filename)[0]

                # Get pose info for display
                info = PoseSerializer.get_pose_info(file_path)
                if info:
                    display_name = f"{pose_name} ({info['bone_count']} bones)"
                else:
                    display_name = pose_name

                item = QListWidgetItem(display_name)
                item.setData(Qt.UserRole, file_path)
                self._pose_list.addItem(item)

    # -------------------------------------------------------------------------
    # Control Handlers
    # -------------------------------------------------------------------------


    def _on_toggle_mesh(self, checked: bool) -> None:
        """Toggle mesh visibility."""
        self._viewport.set_show_mesh(checked)

    def _on_toggle_skeleton(self, checked: bool) -> None:
        """Toggle skeleton visibility."""
        self._viewport.set_show_skeleton(checked)

    def _on_toggle_joints(self, checked: bool) -> None:
        """Toggle joints visibility."""
        self._viewport.set_show_joints(checked)

    def _on_toggle_gizmo(self, checked: bool) -> None:
        """Toggle gizmo visibility."""
        self._viewport.set_show_gizmo(checked)

    def _set_gizmo_mode(self, mode: str) -> None:
        """Set the gizmo mode and update button states."""
        self._rotation_btn.setChecked(mode == "rotation")
        self._movement_btn.setChecked(mode == "movement")
        self._scale_btn.setChecked(mode == "scale")
        self._viewport.set_gizmo_mode(mode)

    def _toggle_gizmo_mode(self) -> None:
        """Toggle between rotation, movement, and scale modes."""
        current_mode = self._viewport.get_gizmo_mode()
        if current_mode == "rotation":
            self._set_gizmo_mode("movement")
        elif current_mode == "movement":
            self._set_gizmo_mode("scale")
        else:
            self._set_gizmo_mode("rotation")

    def _on_fov_changed(self, value: int) -> None:
        """Handle FOV slider changes."""
        self._fov_value_label.setText(f"{value}°")
        self._settings.camera.set('default_fov', float(value))

    def _on_speed_changed(self, value: int) -> None:
        """Handle speed slider changes."""
        # Convert slider value (1-100) to speed (0.002 - 0.02)
        speed = value / 5000.0
        self._speed_value_label.setText(f"{speed:.2f}x")
        self._settings.camera.set('rotation_speed', speed)

    def _on_reset_camera(self) -> None:
        """Reset camera to default position and FOV."""
        self._viewport._camera.target = Vec3(0, 1, 0)
        self._viewport._camera.yaw = 0.0
        self._viewport._camera.pitch = 0.0
        self._viewport._apply_camera_settings()
        self._viewport.update()
        # Update slider to match
        fov = int(self._settings.camera.get('default_fov', 45.0))
        self._fov_slider.setValue(fov)

    def _on_toggle_camera_panel(self, checked: bool) -> None:
        """Toggle the floating camera panel."""
        if checked:
            # Create camera panel if needed
            if self._camera_panel is None:
                self._camera_panel = CameraPanel(self._viewport, self)
                # Position it to the right of the viewport
                viewport_rect = self._viewport.geometry()
                self._camera_panel.move(viewport_rect.right() - 300, viewport_rect.top() + 50)
            self._camera_panel.show()
            self._camera_panel.raise_()
        else:
            if self._camera_panel is not None:
                self._camera_panel.hide()


def main():
    """Main entry point."""
    # Set OpenGL format
    fmt = QSurfaceFormat()
    fmt.setVersion(3, 3)
    fmt.setProfile(QSurfaceFormat.CoreProfile)
    fmt.setDepthBufferSize(24)
    fmt.setSamples(4)
    QSurfaceFormat.setDefaultFormat(fmt)

    app = QApplication(sys.argv)
    app.setApplicationName("Multi-Model 3D Pose Viewer")

    window = MultiModelViewer()
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()

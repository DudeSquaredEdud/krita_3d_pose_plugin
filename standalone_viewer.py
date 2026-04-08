#!/usr/bin/env python3
"""
Standalone 3D Pose Viewer
========================

A standalone application for testing the pose_engine without Krita.
Run this to test loading and posing 3D models.

Usage:
    python standalone_viewer.py [model.glb]

Controls:
    Left mouse: Rotate camera
    Middle mouse: Pan camera
    Right mouse/Scroll: Zoom
    F: Frame model
    T: Toggle mesh visibility
    S: Toggle skeleton visibility
    R: Reset camera
"""

import sys
import os
import math

# Add project root to path
_project_dir = os.path.dirname(os.path.realpath(__file__))
if _project_dir not in sys.path:
    sys.path.insert(0, _project_dir)

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QSlider, QDoubleSpinBox, QGroupBox,
    QTreeWidget, QTreeWidgetItem, QSplitter, QFileDialog, QCheckBox
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QSurfaceFormat

# Import pose_engine
from pose_engine.skeleton import Skeleton
from pose_engine.gltf.loader import GLBLoader
from pose_engine.gltf.builder import build_skeleton_from_gltf, build_mesh_from_gltf
from pose_engine.vec3 import Vec3
from pose_engine.quat import Quat
from pose_engine.ui.viewport import Viewport3D


class StandaloneViewer(QMainWindow):
    """Standalone viewer window."""

    def __init__(self):
        """Create the viewer."""
        super().__init__()

        self._skeleton = None
        self._mesh_data = None
        self._selected_bone = ""
        self._slider_dragging = False  # Track if slider is being dragged

        self.setWindowTitle("3D Pose Viewer (Standalone)")
        self.resize(1200, 800)

        self._setup_ui()
        
        # Load default model if provided
        if len(sys.argv) > 1:
            QTimer.singleShot(100, lambda: self._load_model(sys.argv[1]))
    
    def _setup_ui(self) -> None:
        """Set up the UI."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QHBoxLayout(central_widget)
        
        # Left panel - controls
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(5, 5, 5, 5)
        
        # File controls
        file_group = QGroupBox("File")
        file_layout = QVBoxLayout(file_group)

        load_btn = QPushButton("Load GLB Model")
        load_btn.clicked.connect(self._on_load)
        file_layout.addWidget(load_btn)

        self._file_label = QLabel("No model loaded")
        file_layout.addWidget(self._file_label)

        left_layout.addWidget(file_group)

        # Pose controls
        pose_group = QGroupBox("Pose")
        pose_layout = QVBoxLayout(pose_group)

        # Undo/Redo buttons
        undo_redo_layout = QHBoxLayout()
        self._undo_btn = QPushButton("Undo")
        self._undo_btn.setEnabled(False)
        self._undo_btn.clicked.connect(self._on_undo)
        undo_redo_layout.addWidget(self._undo_btn)

        self._redo_btn = QPushButton("Redo")
        self._redo_btn.setEnabled(False)
        self._redo_btn.clicked.connect(self._on_redo)
        undo_redo_layout.addWidget(self._redo_btn)

        pose_layout.addLayout(undo_redo_layout)

        # Save/Load pose buttons
        pose_btn_layout = QHBoxLayout()
        save_pose_btn = QPushButton("Save Pose")
        save_pose_btn.clicked.connect(self._on_save_pose)
        pose_btn_layout.addWidget(save_pose_btn)

        load_pose_btn = QPushButton("Load Pose")
        load_pose_btn.clicked.connect(self._on_load_pose)
        pose_btn_layout.addWidget(load_pose_btn)

        pose_layout.addLayout(pose_btn_layout)

        # Reset pose button
        reset_pose_btn = QPushButton("Reset to Bind Pose")
        reset_pose_btn.clicked.connect(self._on_reset_pose)
        pose_layout.addWidget(reset_pose_btn)

        left_layout.addWidget(pose_group)
        
        # Bone tree
        bone_group = QGroupBox("Bones")
        bone_layout = QVBoxLayout(bone_group)
        
        self._bone_tree = QTreeWidget()
        self._bone_tree.setHeaderLabel("Bone Hierarchy")
        self._bone_tree.currentItemChanged.connect(self._on_bone_selected)
        bone_layout.addWidget(self._bone_tree)
        
        left_layout.addWidget(bone_group)
        
        # Rotation controls
        rotation_group = QGroupBox("Rotation (Degrees)")
        rotation_layout = QVBoxLayout(rotation_group)
        
        # X
        x_layout = QHBoxLayout()
        x_layout.addWidget(QLabel("X:"))
        self._x_slider = QSlider(Qt.Horizontal)
        self._x_slider.setRange(-180, 180)
        self._x_slider.valueChanged.connect(self._on_rotation_changed)
        self._x_slider.sliderPressed.connect(self._on_slider_pressed)
        self._x_slider.sliderReleased.connect(self._on_slider_released)
        x_layout.addWidget(self._x_slider)
        self._x_spin = QDoubleSpinBox()
        self._x_spin.setRange(-180, 180)
        self._x_spin.valueChanged.connect(lambda v: self._x_slider.setValue(int(v)))
        x_layout.addWidget(self._x_spin)
        rotation_layout.addLayout(x_layout)

        # Y
        y_layout = QHBoxLayout()
        y_layout.addWidget(QLabel("Y:"))
        self._y_slider = QSlider(Qt.Horizontal)
        self._y_slider.setRange(-180, 180)
        self._y_slider.valueChanged.connect(self._on_rotation_changed)
        self._y_slider.sliderPressed.connect(self._on_slider_pressed)
        self._y_slider.sliderReleased.connect(self._on_slider_released)
        y_layout.addWidget(self._y_slider)
        self._y_spin = QDoubleSpinBox()
        self._y_spin.setRange(-180, 180)
        self._y_spin.valueChanged.connect(lambda v: self._y_slider.setValue(int(v)))
        y_layout.addWidget(self._y_spin)
        rotation_layout.addLayout(y_layout)

        # Z
        z_layout = QHBoxLayout()
        z_layout.addWidget(QLabel("Z:"))
        self._z_slider = QSlider(Qt.Horizontal)
        self._z_slider.setRange(-180, 180)
        self._z_slider.valueChanged.connect(self._on_rotation_changed)
        self._z_slider.sliderPressed.connect(self._on_slider_pressed)
        self._z_slider.sliderReleased.connect(self._on_slider_released)
        z_layout.addWidget(self._z_slider)
        self._z_spin = QDoubleSpinBox()
        self._z_spin.setRange(-180, 180)
        self._z_spin.valueChanged.connect(lambda v: self._z_slider.setValue(int(v)))
        z_layout.addWidget(self._z_spin)
        rotation_layout.addLayout(z_layout)
        
        reset_btn = QPushButton("Reset Rotation")
        reset_btn.clicked.connect(self._on_reset_rotation)
        rotation_layout.addWidget(reset_btn)
        
        left_layout.addWidget(rotation_group)
        
        # Visibility controls
        visibility_group = QGroupBox("Visibility")
        visibility_layout = QVBoxLayout(visibility_group)
    
        self._show_mesh_cb = QCheckBox("Show Mesh")
        self._show_mesh_cb.setChecked(True)
        self._show_mesh_cb.toggled.connect(self._on_toggle_mesh)
        visibility_layout.addWidget(self._show_mesh_cb)
    
        self._show_skeleton_cb = QCheckBox("Show Skeleton")
        self._show_skeleton_cb.setChecked(True)
        self._show_skeleton_cb.toggled.connect(self._on_toggle_skeleton)
        visibility_layout.addWidget(self._show_skeleton_cb)
    
        self._show_joints_cb = QCheckBox("Show Joints")
        self._show_joints_cb.setChecked(True)
        self._show_joints_cb.toggled.connect(self._on_toggle_joints)
        visibility_layout.addWidget(self._show_joints_cb)
    
        self._show_gizmo_cb = QCheckBox("Show Gizmo")
        self._show_gizmo_cb.setChecked(True)
        self._show_gizmo_cb.toggled.connect(self._on_toggle_gizmo)
        visibility_layout.addWidget(self._show_gizmo_cb)
    
        left_layout.addWidget(visibility_group)
        
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
        
        # Status
        self._status_label = QLabel("Ready")
        left_layout.addWidget(self._status_label)
        
        left_layout.addStretch()
        
        # Right panel - viewport
        self._viewport = Viewport3D()
        self._viewport.bone_selected.connect(self._on_viewport_bone_selected)
        self._viewport.bone_rotation_changed.connect(self._on_gizmo_rotation_changed)
        self._viewport.undo_redo_changed.connect(self._on_undo_redo_changed)
        self._viewport.pose_changed.connect(self._on_pose_changed)

        # Add to splitter
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_panel)
        splitter.addWidget(self._viewport)
        splitter.setSizes([300, 900])
        
        layout.addWidget(splitter)
    
    def _on_load(self) -> None:
        """Handle load button."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Load GLB Model", "", "GLB Files (*.glb);;All Files (*)"
        )
        
        if file_path:
            self._load_model(file_path)
    
    def _load_model(self, file_path: str) -> None:
        """Load a model."""
        try:
            self._status_label.setText("Loading...")
            QApplication.processEvents()
            
            loader = GLBLoader()
            glb_data = loader.load(file_path)
            
            self._skeleton, bone_mapping = build_skeleton_from_gltf(glb_data, loader=loader)
            self._mesh_data = build_mesh_from_gltf(glb_data, bone_mapping=bone_mapping, loader=loader)
            
            # Update viewport
            self._viewport.set_skeleton(self._skeleton)
            self._viewport.set_mesh(self._mesh_data)
            
            # Update bone tree
            self._rebuild_bone_tree()
        
            self._file_label.setText(os.path.basename(file_path))
            self._status_label.setText(f"Loaded: {len(self._skeleton)} bones, {len(self._mesh_data.positions)} vertices")
            
        except Exception as e:
            self._status_label.setText(f"Error: {e}")
            import traceback
            traceback.print_exc()
    
    def _rebuild_bone_tree(self) -> None:
        """Rebuild the bone tree."""
        self._bone_tree.clear()
        
        if not self._skeleton:
            return
        
        for root in self._skeleton.get_root_bones():
            self._add_bone_to_tree(root, None)
        
        self._bone_tree.expandAll()
    
    def _add_bone_to_tree(self, bone, parent_item) -> None:
        """Add bone to tree."""
        item = QTreeWidgetItem([bone.name])
        item.setData(0, Qt.UserRole, bone.name)
        
        if parent_item:
            parent_item.addChild(item)
        else:
            self._bone_tree.addTopLevelItem(item)
        
        for child in bone.children:
            self._add_bone_to_tree(child, item)
    
    def _on_bone_selected(self, current, _) -> None:
        """Handle bone selection."""
        if current:
            self._selected_bone = current.data(0, Qt.UserRole)
            self._viewport.set_selected_bone(self._selected_bone)
            self._update_rotation_controls()
            self._status_label.setText(f"Selected: {self._selected_bone}")
    
    def _on_viewport_bone_selected(self, bone_name: str) -> None:
        """Handle bone selection from viewport."""
        self._selected_bone = bone_name
        items = self._bone_tree.findItems(bone_name, Qt.MatchExactly | Qt.MatchRecursive, 0)
        if items:
            self._bone_tree.setCurrentItem(items[0])

    def _on_gizmo_rotation_changed(self, bone_name: str, rotation: Quat) -> None:
        """Handle rotation change from gizmo interaction."""
        # Update the rotation sliders to reflect the new rotation
        self._update_rotation_controls()
        # Update the skeleton transforms
        if self._skeleton:
            self._skeleton.update_all_transforms()
        self._viewport.update()

    def _update_rotation_controls(self) -> None:
        """Update rotation controls from selected bone."""
        if not self._skeleton or not self._selected_bone:
            return

        bone = self._skeleton.get_bone(self._selected_bone)
        if not bone:
            return

        # Get the current world rotation of the bone
        # World rotation = parent_world * pose * bind
        if bone.parent is not None:
            parent_world = bone.parent.get_world_transform()
            parent_world_rot = parent_world.rotation
        else:
            parent_world_rot = Quat.identity()
        
        bind_rot = bone.bind_transform.rotation
        pose_rot = bone.pose_transform.rotation
        
        # Current world rotation
        current_world_rot = parent_world_rot * (pose_rot * bind_rot)
        
        # Get the bind pose world rotation (when pose is identity)
        bind_world_rot = parent_world_rot * bind_rot
        
        # The "delta" from bind pose in world space
        # We want: current_world = delta * bind_world
        # So: delta = current_world * bind_world^-1
        delta_rot = current_world_rot * bind_world_rot.inverse()
        
        # Convert to Euler angles
        euler = delta_rot.to_euler_degrees()

        self._x_slider.blockSignals(True)
        self._y_slider.blockSignals(True)
        self._z_slider.blockSignals(True)
        self._x_spin.blockSignals(True)
        self._y_spin.blockSignals(True)
        self._z_spin.blockSignals(True)

        self._x_slider.setValue(int(euler[0]))
        self._y_slider.setValue(int(euler[1]))
        self._z_slider.setValue(int(euler[2]))
        self._x_spin.setValue(euler[0])
        self._y_spin.setValue(euler[1])
        self._z_spin.setValue(euler[2])

        self._x_slider.blockSignals(False)
        self._y_slider.blockSignals(False)
        self._z_slider.blockSignals(False)
        self._x_spin.blockSignals(False)
        self._y_spin.blockSignals(False)
        self._z_spin.blockSignals(False)

    def _on_rotation_changed(self) -> None:
        """Handle rotation change with auto-parent propagation."""
        if not self._skeleton or not self._selected_bone:
            return

        x = self._x_slider.value()
        y = self._y_slider.value()
        z = self._z_slider.value()

        self._x_spin.blockSignals(True)
        self._y_spin.blockSignals(True)
        self._z_spin.blockSignals(True)
        self._x_spin.setValue(x)
        self._y_spin.setValue(y)
        self._z_spin.setValue(z)
        self._x_spin.blockSignals(False)
        self._y_spin.blockSignals(False)
        self._z_spin.blockSignals(False)

        # Create the delta rotation quaternion from Euler angles (in world space)
        # This represents how much to rotate FROM the bind pose
        delta_rotation = Quat.from_euler_degrees(x, y, z)
        bone = self._skeleton.get_bone(self._selected_bone)
        if bone:
            # Get parent's world rotation (or identity if no parent)
            if bone.parent is not None:
                parent_world = bone.parent.get_world_transform()
                parent_world_rot = parent_world.rotation
            else:
                parent_world_rot = Quat.identity()

            # Get bind rotation
            bind_rot = bone.bind_transform.rotation

            # The bind pose world rotation
            bind_world_rot = parent_world_rot * bind_rot
            
            # Apply delta to bind pose: new_world = delta * bind_world
            new_world_rot = delta_rotation * bind_world_rot
            
            # Convert back to pose rotation
            # We want: parent_world * pose * bind = new_world
            # So: pose = parent_world^-1 * new_world * bind^-1
            pose_rotation = parent_world_rot.inverse() * new_world_rot * bind_rot.inverse()

            # Set the pose rotation
            bone.set_pose_rotation(pose_rotation)

            self._skeleton.update_all_transforms()
            self._viewport.update()
    
    def _on_reset_rotation(self) -> None:
        """Reset rotation."""
        if not self._skeleton or not self._selected_bone:
            return
        
        bone = self._skeleton.get_bone(self._selected_bone)
        if bone:
            bone.reset_pose()
            self._skeleton.update_all_transforms()
            self._update_rotation_controls()
            self._viewport.update()
    
    def _on_toggle_mesh(self, checked: bool) -> None:
        """Toggle mesh visibility."""
        self._viewport.set_show_mesh(checked)

    def _on_toggle_skeleton(self, checked: bool) -> None:
        """Toggle skeleton visibility."""
        self._viewport.set_show_skeleton(checked)

    def _on_toggle_joints(self, checked: bool) -> None:
        """Toggle joint spheres visibility."""
        self._viewport.set_show_joints(checked)

    def _on_toggle_gizmo(self, checked: bool) -> None:
        """Toggle rotation gizmo visibility."""
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

    # -------------------------------------------------------------------------
    # Pose Management Handlers
    # -------------------------------------------------------------------------

    def _on_undo(self) -> None:
        """Handle undo button."""
        if self._viewport.undo():
            self._update_rotation_controls()
            self._status_label.setText("Undo")

    def _on_redo(self) -> None:
        """Handle redo button."""
        if self._viewport.redo():
            self._update_rotation_controls()
            self._status_label.setText("Redo")

    def _on_undo_redo_changed(self, can_undo: bool, can_redo: bool) -> None:
        """Handle undo/redo availability change."""
        self._undo_btn.setEnabled(can_undo)
        self._redo_btn.setEnabled(can_redo)

    def _on_pose_changed(self) -> None:
        """Handle pose changed signal."""
        self._update_rotation_controls()

    def _on_save_pose(self) -> None:
        """Handle save pose button."""
        if self._viewport.save_pose_dialog():
            self._status_label.setText("Pose saved")

    def _on_load_pose(self) -> None:
        """Handle load pose button."""
        if self._viewport.load_pose_dialog():
            self._update_rotation_controls()
            self._status_label.setText("Pose loaded")

    def _on_reset_pose(self) -> None:
        """Handle reset pose button."""
        self._viewport.reset_pose()
        self._update_rotation_controls()
        self._status_label.setText("Pose reset to bind")

    def _on_slider_pressed(self) -> None:
        """Handle slider press - push undo state before changing."""
        if self._skeleton and self._selected_bone:
            self._slider_dragging = True
            self._viewport.push_undo_state(f"Rotate {self._selected_bone}")

    def _on_slider_released(self) -> None:
        """Handle slider release - commit the change."""
        self._slider_dragging = False


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
    app.setApplicationName("3D Pose Viewer")
    
    window = StandaloneViewer()
    window.show()
    
    # Load default model if available
    default_model = os.path.join(_project_dir, "krita_3d_pose", "RIGLADY.glb")
    if os.path.exists(default_model):
        QTimer.singleShot(100, lambda: window._load_model(default_model))
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()

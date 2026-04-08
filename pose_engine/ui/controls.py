"""
Bone Controls - UI for Bone Manipulation
=======================================

Provides controls for selecting and manipulating bones.
"""

from typing import Optional, List, Callable

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QSlider, QDoubleSpinBox, QComboBox, QPushButton,
    QGroupBox, QTreeWidget, QTreeWidgetItem
)
from PyQt5.QtCore import Qt, pyqtSignal

from ..vec3 import Vec3
from ..quat import Quat
from ..skeleton import Skeleton
from ..bone import Bone


class BoneControls(QWidget):
    """
    Controls for bone selection and manipulation.
    
    Features:
    - Bone hierarchy tree
    - Rotation sliders (Euler angles for UI)
    - IK target controls
    
    Signals:
        bone_rotation_changed: Emitted when bone rotation changes (bone_name, rotation)
        ik_target_changed: Emitted when IK target changes (bone_name, target_position)
    """
    
    bone_rotation_changed = pyqtSignal(str, object) # bone_name, Quat
    ik_target_changed = pyqtSignal(str, object) # bone_name, Vec3
    gizmo_mode_changed = pyqtSignal(str) # "rotation" or "movement"
    
    def __init__(self, parent: Optional[QWidget] = None):
        """Create bone controls."""
        super().__init__(parent)
        
        self._skeleton: Optional[Skeleton] = None
        self._selected_bone: str = ""
        self._updating_from_bone: bool = False
        
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        """Set up the UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Bone tree
        tree_group = QGroupBox("Bones")
        tree_layout = QVBoxLayout(tree_group)
        
        self._bone_tree = QTreeWidget()
        self._bone_tree.setHeaderLabel("Bone Hierarchy")
        self._bone_tree.currentItemChanged.connect(self._on_tree_selection_changed)
        tree_layout.addWidget(self._bone_tree)
        
        layout.addWidget(tree_group)
        
        # Rotation controls
        rotation_group = QGroupBox("Rotation (Degrees)")
        rotation_layout = QVBoxLayout(rotation_group)
        
        # X rotation
        x_layout = QHBoxLayout()
        x_layout.addWidget(QLabel("X:"))
        self._x_slider = QSlider(Qt.Horizontal)
        self._x_slider.setRange(-180, 180)
        self._x_slider.valueChanged.connect(self._on_rotation_changed)
        x_layout.addWidget(self._x_slider)
        self._x_spin = QDoubleSpinBox()
        self._x_spin.setRange(-180, 180)
        self._x_spin.setDecimals(1)
        self._x_spin.valueChanged.connect(self._on_x_spin_changed)
        x_layout.addWidget(self._x_spin)
        rotation_layout.addLayout(x_layout)
        
        # Y rotation
        y_layout = QHBoxLayout()
        y_layout.addWidget(QLabel("Y:"))
        self._y_slider = QSlider(Qt.Horizontal)
        self._y_slider.setRange(-180, 180)
        self._y_slider.valueChanged.connect(self._on_rotation_changed)
        y_layout.addWidget(self._y_slider)
        self._y_spin = QDoubleSpinBox()
        self._y_spin.setRange(-180, 180)
        self._y_spin.setDecimals(1)
        self._y_spin.valueChanged.connect(self._on_y_spin_changed)
        y_layout.addWidget(self._y_spin)
        rotation_layout.addLayout(y_layout)
        
        # Z rotation
        z_layout = QHBoxLayout()
        z_layout.addWidget(QLabel("Z:"))
        self._z_slider = QSlider(Qt.Horizontal)
        self._z_slider.setRange(-180, 180)
        self._z_slider.valueChanged.connect(self._on_rotation_changed)
        z_layout.addWidget(self._z_slider)
        self._z_spin = QDoubleSpinBox()
        self._z_spin.setRange(-180, 180)
        self._z_spin.setDecimals(1)
        self._z_spin.valueChanged.connect(self._on_z_spin_changed)
        z_layout.addWidget(self._z_spin)
        rotation_layout.addLayout(z_layout)
        
        # Reset button
        reset_btn = QPushButton("Reset Rotation")
        reset_btn.clicked.connect(self._on_reset_rotation)
        rotation_layout.addWidget(reset_btn)
        
        layout.addWidget(rotation_group)
        
        # Gizmo mode toggle
        gizmo_group = QGroupBox("Gizmo Mode")
        gizmo_layout = QHBoxLayout(gizmo_group)

        self._rotation_btn = QPushButton("Rotate")
        self._rotation_btn.setCheckable(True)
        self._rotation_btn.setChecked(True)
        self._rotation_btn.clicked.connect(lambda: self._set_gizmo_mode("rotation"))
        gizmo_layout.addWidget(self._rotation_btn)

        self._movement_btn = QPushButton("Move")
        self._movement_btn.setCheckable(True)
        self._movement_btn.clicked.connect(lambda: self._set_gizmo_mode("movement"))
        gizmo_layout.addWidget(self._movement_btn)

        self._scale_btn = QPushButton("Scale")
        self._scale_btn.setCheckable(True)
        self._scale_btn.clicked.connect(lambda: self._set_gizmo_mode("scale"))
        gizmo_layout.addWidget(self._scale_btn)

        layout.addWidget(gizmo_group)

        # IK controls
        ik_group = QGroupBox("IK Target")
        ik_layout = QVBoxLayout(ik_group)
        
        # IK bone selector
        ik_selector_layout = QHBoxLayout()
        ik_selector_layout.addWidget(QLabel("End Effector:"))
        self._ik_bone_combo = QComboBox()
        ik_selector_layout.addWidget(self._ik_bone_combo)
        ik_layout.addLayout(ik_selector_layout)
        
        # IK target position
        pos_layout = QHBoxLayout()
        pos_layout.addWidget(QLabel("Target:"))
        self._ik_x = QDoubleSpinBox()
        self._ik_x.setRange(-10, 10)
        self._ik_x.setDecimals(2)
        pos_layout.addWidget(self._ik_x)
        self._ik_y = QDoubleSpinBox()
        self._ik_y.setRange(-10, 10)
        self._ik_y.setDecimals(2)
        pos_layout.addWidget(self._ik_y)
        self._ik_z = QDoubleSpinBox()
        self._ik_z.setRange(-10, 10)
        self._ik_z.setDecimals(2)
        pos_layout.addWidget(self._ik_z)
        ik_layout.addLayout(pos_layout)
        
        # Solve button
        self._solve_btn = QPushButton("Solve IK")
        self._solve_btn.clicked.connect(self._on_solve_ik)
        ik_layout.addWidget(self._solve_btn)
        
        layout.addWidget(ik_group)
        
        # Stretch to fill space
        layout.addStretch()
    
    def set_skeleton(self, skeleton: Skeleton) -> None:
        """Set the skeleton to control."""
        self._skeleton = skeleton
        self._rebuild_bone_tree()
        self._update_ik_combo()
    
    def set_selected_bone(self, bone_name: str) -> None:
        """Set the selected bone by name."""
        self._selected_bone = bone_name
        self._update_rotation_controls()
        self._select_bone_in_tree(bone_name)
    
    def get_selected_bone(self) -> str:
        """Get the selected bone name."""
        return self._selected_bone
    
    def _rebuild_bone_tree(self) -> None:
        """Rebuild the bone hierarchy tree."""
        self._bone_tree.clear()
        
        if not self._skeleton:
            return
        
        # Build tree recursively
        for root in self._skeleton.get_root_bones():
            self._add_bone_to_tree(root, None)
        
        self._bone_tree.expandAll()
    
    def _add_bone_to_tree(self, bone: Bone, parent_item: Optional[QTreeWidgetItem]) -> None:
        """Add a bone and its children to the tree."""
        item = QTreeWidgetItem([bone.name])
        item.setData(0, Qt.UserRole, bone.name)
        
        if parent_item:
            parent_item.addChild(item)
        else:
            self._bone_tree.addTopLevelItem(item)
        
        for child in bone.children:
            self._add_bone_to_tree(child, item)
    
    def _update_ik_combo(self) -> None:
        """Update the IK bone combo box."""
        self._ik_bone_combo.clear()
        
        if not self._skeleton:
            return
        
        # Add leaf bones (end effectors)
        for bone in self._skeleton.get_leaf_bones():
            self._ik_bone_combo.addItem(bone.name)
    
    def _select_bone_in_tree(self, bone_name: str) -> None:
        """Select a bone in the tree by name."""
        items = self._bone_tree.findItems(bone_name, Qt.MatchExactly | Qt.MatchRecursive, 0)
        if items:
            self._bone_tree.setCurrentItem(items[0])
    
    def _update_rotation_controls(self) -> None:
        """Update rotation sliders from selected bone."""
        if not self._skeleton or not self._selected_bone:
            return
        
        bone = self._skeleton.get_bone(self._selected_bone)
        if not bone:
            return
        
        self._updating_from_bone = True
        
        euler = bone.pose_transform.get_euler_degrees()
        self._x_slider.setValue(int(euler[0]))
        self._y_slider.setValue(int(euler[1]))
        self._z_slider.setValue(int(euler[2]))
        self._x_spin.setValue(euler[0])
        self._y_spin.setValue(euler[1])
        self._z_spin.setValue(euler[2])
        
        self._updating_from_bone = False
    
    def _on_tree_selection_changed(self, current: QTreeWidgetItem, _) -> None:
        """Handle tree selection change."""
        if current:
            bone_name = current.data(0, Qt.UserRole)
            self._selected_bone = bone_name
            self._update_rotation_controls()
    
    def _on_rotation_changed(self) -> None:
        """Handle rotation slider change."""
        if self._updating_from_bone or not self._selected_bone:
            return
        
        x = self._x_slider.value()
        y = self._y_slider.value()
        z = self._z_slider.value()
        
        # Update spins
        self._x_spin.blockSignals(True)
        self._y_spin.blockSignals(True)
        self._z_spin.blockSignals(True)
        self._x_spin.setValue(x)
        self._y_spin.setValue(y)
        self._z_spin.setValue(z)
        self._x_spin.blockSignals(False)
        self._y_spin.blockSignals(False)
        self._z_spin.blockSignals(False)
        
        # Emit rotation change
        rotation = Quat.from_euler_degrees(x, y, z)
        self.bone_rotation_changed.emit(self._selected_bone, rotation)
    
    def _on_x_spin_changed(self, value: float) -> None:
        """Handle X spin box change."""
        self._x_slider.blockSignals(True)
        self._x_slider.setValue(int(value))
        self._x_slider.blockSignals(False)
        self._on_rotation_changed()
    
    def _on_y_spin_changed(self, value: float) -> None:
        """Handle Y spin box change."""
        self._y_slider.blockSignals(True)
        self._y_slider.setValue(int(value))
        self._y_slider.blockSignals(False)
        self._on_rotation_changed()
    
    def _on_z_spin_changed(self, value: float) -> None:
        """Handle Z spin box change."""
        self._z_slider.blockSignals(True)
        self._z_slider.setValue(int(value))
        self._z_slider.blockSignals(False)
        self._on_rotation_changed()
    
    def _on_reset_rotation(self) -> None:
        """Handle reset rotation button."""
        if not self._selected_bone:
            return
        
        rotation = Quat.identity()
        self.bone_rotation_changed.emit(self._selected_bone, rotation)
        
        # Update controls
        self._x_slider.setValue(0)
        self._y_slider.setValue(0)
        self._z_slider.setValue(0)
    
    def _on_solve_ik(self) -> None:
        """Handle IK solve button."""
        bone_name = self._ik_bone_combo.currentText()
        if not bone_name:
            return
        
        target = Vec3(
            self._ik_x.value(),
            self._ik_y.value(),
            self._ik_z.value()
        )
        
        self.ik_target_changed.emit(bone_name, target)
    
    def set_ik_target(self, x: float, y: float, z: float) -> None:
        """Set the IK target position."""
        self._ik_x.setValue(x)
        self._ik_y.setValue(y)
        self._ik_z.setValue(z)
    
    def _set_gizmo_mode(self, mode: str) -> None:
        """
        Set the gizmo mode.

        Args:
            mode: "rotation", "movement", or "scale"
        """
        self._rotation_btn.setChecked(mode == "rotation")
        self._movement_btn.setChecked(mode == "movement")
        self._scale_btn.setChecked(mode == "scale")

        self.gizmo_mode_changed.emit(mode)

    def set_gizmo_mode(self, mode: str) -> None:
        """
        Set the gizmo mode from external source (e.g., keyboard shortcut).

        Args:
            mode: "rotation", "movement", or "scale"
        """
        self._set_gizmo_mode(mode)

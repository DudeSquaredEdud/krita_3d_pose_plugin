"""
Krita Multi-Model 3D Poser Docker Panel
=======================================

Multi-model UI panel for the Krita 3D pose plugin.
Integrates the MultiViewport3D with Krita's docker system.
Supports loading, posing, and managing multiple 3D models.
"""

import os
import sys
from typing import Optional

# Add pose_engine to path - handle both development and installed locations
_plugin_dir = os.path.dirname(os.path.realpath(__file__))
_parent_dir = os.path.dirname(_plugin_dir)

# In development: pose_engine is in parent directory
# In installed: pose_engine should be in the same pykrita directory
_pose_engine_dir = _parent_dir
if not os.path.exists(os.path.join(_pose_engine_dir, 'pose_engine')):
    # Try installed location - pose_engine as sibling of krita_3d_pose
    _pose_engine_dir = _parent_dir

for _path in [_pose_engine_dir, _parent_dir]:
    if _path not in sys.path:
        sys.path.insert(0, _path)

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QFileDialog, QSplitter, QMessageBox, QGroupBox, QTreeWidget,
    QTreeWidgetItem, QCheckBox, QListWidget, QListWidgetItem
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor, QImage, QPainter

from krita import Krita, DockWidget

# Import pose_engine components
_import_error = None
try:
    from pose_engine.scene import Scene
    from pose_engine.model_instance import ModelInstance
    from pose_engine.pose_state import PoseSnapshot, PoseSerializer
    from pose_engine.ui.multi_viewport import MultiViewport3D
except ImportError as e:
    _import_error = str(e)
    Scene = None
    ModelInstance = None
    PoseSnapshot = None
    PoseSerializer = None
    MultiViewport3D = None


class KritaMultiModelDocker(DockWidget):
    """
    Multi-model docker panel for the 3D pose plugin.

    This provides a full multi-model editing experience within Krita,
    allowing users to load, pose, and arrange multiple 3D models.
    """

    def __init__(self):
        """Create the docker panel."""
        super().__init__()

        self.setWindowTitle("3D Multi-Model Editor")

        self._setup_ui()

        # Update timer for continuous rendering
        self._update_timer = QTimer(self)
        self._update_timer.timeout.connect(self._on_update)
        self._update_timer.start(16)  # ~60 FPS

        # Sync timer for layer sync functionality
        self._sync_timer = QTimer()
        self._sync_timer.setSingleShot(True)
        self._sync_timer.setInterval(200)  # 200ms delay like original
        self._sync_timer.timeout.connect(self._do_sync)

    def _setup_ui(self) -> None:
        """Set up the UI."""
        # Main widget
        main_widget = QWidget()
        self.setWidget(main_widget)

        layout = QHBoxLayout(main_widget)
        layout.setContentsMargins(5, 5, 5, 5)

        # Left panel - controls
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(5, 5, 5, 5)

        # Model management group
        models_group = QGroupBox("Models")
        models_layout = QVBoxLayout(models_group)

        # Model buttons
        btn_layout = QHBoxLayout()
        add_btn = QPushButton("Add")
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
        self._model_tree.setMaximumHeight(120)
        models_layout.addWidget(self._model_tree)

        left_layout.addWidget(models_group)

        # Bone tree group
        bone_group = QGroupBox("Bones")
        bone_layout = QVBoxLayout(bone_group)

        self._bone_tree = QTreeWidget()
        self._bone_tree.setHeaderLabels(["Bone Hierarchy"])
        self._bone_tree.itemClicked.connect(self._on_bone_tree_click)
        self._bone_tree.setMaximumHeight(150)
        bone_layout.addWidget(self._bone_tree)

        left_layout.addWidget(bone_group)

        # Visibility controls
        vis_group = QGroupBox("Visibility")
        vis_layout = QVBoxLayout(vis_group)

        self._show_mesh_cb = QCheckBox("Mesh")
        self._show_mesh_cb.setChecked(True)
        self._show_mesh_cb.toggled.connect(self._on_toggle_mesh)
        vis_layout.addWidget(self._show_mesh_cb)

        self._show_skeleton_cb = QCheckBox("Skeleton")
        self._show_skeleton_cb.setChecked(True)
        self._show_skeleton_cb.toggled.connect(self._on_toggle_skeleton)
        vis_layout.addWidget(self._show_skeleton_cb)

        self._show_joints_cb = QCheckBox("Joints")
        self._show_joints_cb.setChecked(True)
        self._show_joints_cb.toggled.connect(self._on_toggle_joints)
        vis_layout.addWidget(self._show_joints_cb)

        self._show_gizmo_cb = QCheckBox("Gizmo")
        self._show_gizmo_cb.setChecked(True)
        self._show_gizmo_cb.toggled.connect(self._on_toggle_gizmo)
        vis_layout.addWidget(self._show_gizmo_cb)

        left_layout.addWidget(vis_group)

        # Gizmo mode controls
        gizmo_group = QGroupBox("Gizmo Mode")
        gizmo_layout = QVBoxLayout(gizmo_group)

        mode_layout = QHBoxLayout()

        self._rotation_btn = QPushButton("R")
        self._rotation_btn.setCheckable(True)
        self._rotation_btn.setChecked(True)
        self._rotation_btn.setMaximumWidth(40)
        self._rotation_btn.clicked.connect(lambda: self._set_gizmo_mode("rotation"))
        mode_layout.addWidget(self._rotation_btn)

        self._movement_btn = QPushButton("M")
        self._movement_btn.setCheckable(True)
        self._movement_btn.setMaximumWidth(40)
        self._movement_btn.clicked.connect(lambda: self._set_gizmo_mode("movement"))
        mode_layout.addWidget(self._movement_btn)

        self._scale_btn = QPushButton("S")
        self._scale_btn.setCheckable(True)
        self._scale_btn.setMaximumWidth(40)
        self._scale_btn.clicked.connect(lambda: self._set_gizmo_mode("scale"))
        mode_layout.addWidget(self._scale_btn)

        gizmo_layout.addLayout(mode_layout)

        toggle_btn = QPushButton("Toggle (G)")
        toggle_btn.clicked.connect(self._toggle_gizmo_mode)
        gizmo_layout.addWidget(toggle_btn)

        left_layout.addWidget(gizmo_group)

        # Layer Sync group (RIGHT UNDER GIZMO MODES!)
        sync_group = QGroupBox("Layer Sync")
        sync_layout = QVBoxLayout(sync_group)
        
        self._sync_btn = QPushButton("📷 Sync to Layer")
        self._sync_btn.clicked.connect(self._on_sync_to_layer)
        self._sync_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; padding: 8px;")
        sync_layout.addWidget(self._sync_btn)
        
        left_layout.addWidget(sync_group)

        # Poses group
        poses_group = QGroupBox("Poses")
        poses_layout = QVBoxLayout(poses_group)

        pose_btn_layout = QHBoxLayout()

        load_pose_btn = QPushButton("Load")
        load_pose_btn.clicked.connect(self._on_load_pose)
        pose_btn_layout.addWidget(load_pose_btn)

        save_pose_btn = QPushButton("Save")
        save_pose_btn.clicked.connect(self._on_save_pose)
        pose_btn_layout.addWidget(save_pose_btn)

        poses_layout.addLayout(pose_btn_layout)

        self._pose_list = QListWidget()
        self._pose_list.setMaximumHeight(80)
        self._pose_list.itemDoubleClicked.connect(self._on_pose_double_clicked)
        poses_layout.addWidget(self._pose_list)

        apply_pose_btn = QPushButton("Apply")
        apply_pose_btn.clicked.connect(self._on_apply_pose)
        poses_layout.addWidget(apply_pose_btn)

        left_layout.addWidget(poses_group)

        # Status label
        self._status_label = QLabel("No models loaded")
        left_layout.addWidget(self._status_label)

        left_layout.addStretch()

        # Main splitter
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_panel)

        # 3D Viewport
        if MultiViewport3D:
            self._viewport = MultiViewport3D()
            splitter.addWidget(self._viewport)

            # Connect signals
            self._viewport.model_selected.connect(self._on_model_selected)
            self._viewport.bone_selected.connect(self._on_bone_selected)
            self._viewport.model_selection_changed.connect(self._on_model_selection_changed)
        else:
            self._viewport = None
            error_msg = f"OpenGL not available\n\nImport error: {_import_error}" if _import_error else "OpenGL not available"
            placeholder = QLabel(error_msg)
            placeholder.setAlignment(Qt.AlignCenter)
            placeholder.setWordWrap(True)
            splitter.addWidget(placeholder)

        splitter.setSizes([250, 500])
        layout.addWidget(splitter)

        # Initialize pose list
        self._refresh_pose_list()

    # -------------------------------------------------------------------------
    # Model Management
    # -------------------------------------------------------------------------

    def _on_add_model(self) -> None:
        """Handle add model button."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Add 3D Model",
            "",
            "GLB Files (*.glb);;GLTF Files (*.gltf);;All Files (*)"
        )

        if file_path:
            self._add_model(file_path)

    def _add_model(self, file_path: str) -> None:
        """Add a model to the scene."""
        if not self._viewport:
            return

        name = os.path.splitext(os.path.basename(file_path))[0]

        try:
            model = self._viewport.add_model(file_path, name)

            if model:
                self._rebuild_model_tree()
                self._rebuild_bone_tree()
                self._status_label.setText(f"Loaded: {name} ({model.get_bone_count()} bones)")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load model: {e}")

    def _on_duplicate_model(self) -> None:
        """Handle duplicate model button."""
        if not self._viewport:
            return

        model = self._viewport.get_selected_model()
        if model:
            copy = self._viewport.duplicate_model(model.id)
            if copy:
                self._rebuild_model_tree()
                self._rebuild_bone_tree()
                self._status_label.setText(f"Duplicated: {copy.name}")

    def _on_remove_model(self) -> None:
        """Handle remove model button."""
        if not self._viewport:
            return

        model = self._viewport.get_selected_model()
        if model:
            self._viewport.remove_model(model.id)
            self._rebuild_model_tree()
            self._rebuild_bone_tree()
            self._status_label.setText(f"Removed: {model.name}")

    def _rebuild_model_tree(self) -> None:
        """Rebuild the model tree."""
        if not self._viewport:
            return

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

            self._model_tree.addTopLevelItem(item)

        self._model_tree.expandAll()

    def _rebuild_bone_tree(self) -> None:
        """Rebuild the bone tree."""
        if not self._viewport:
            return

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
            model_item.setExpanded(True)

    def _add_bone_to_tree(self, bone, parent_item, model_id: str) -> None:
        """Add bone to tree recursively."""
        item = QTreeWidgetItem([bone.name])
        item.setData(0, Qt.UserRole, f"bone:{model_id}:{bone.name}")

        for child in bone.children:
            self._add_bone_to_tree(child, item, model_id)

        parent_item.addChild(item)
        item.setExpanded(False)

    # -------------------------------------------------------------------------
    # Tree Click Handlers
    # -------------------------------------------------------------------------

    def _on_model_tree_click(self, item: QTreeWidgetItem, column: int) -> None:
        """Handle model tree click."""
        if not self._viewport:
            return

        model_id = item.data(0, Qt.UserRole)
        if model_id:
            # Update visibility from checkbox
            self._viewport.set_model_visible(model_id, item.checkState(0) == Qt.Checked)
            self._viewport.select_model(model_id)
            self._rebuild_bone_tree()

    def _on_bone_tree_click(self, item: QTreeWidgetItem, column: int) -> None:
        """Handle bone tree click."""
        if not self._viewport:
            return

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
        self._rebuild_model_tree()
        self._rebuild_bone_tree()

    # -------------------------------------------------------------------------
    # Pose Management
    # -------------------------------------------------------------------------

    def _on_load_pose(self) -> None:
        """Handle load pose button."""
        if not self._viewport or not PoseSerializer:
            return

        model = self._viewport.get_selected_model()
        if not model:
            self._status_label.setText("Select a model first")
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self, "Load Pose", "poses",
            "JSON Files (*.json);;All Files (*)"
        )

        if file_path:
            self._apply_pose_file(file_path, model)

    def _on_save_pose(self) -> None:
        """Handle save pose button."""
        if not self._viewport or not PoseSerializer:
            return

        model = self._viewport.get_selected_model()
        if not model or not model.skeleton:
            self._status_label.setText("Select a model with skeleton first")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Pose", f"poses/{model.name}_pose.json",
            "JSON Files (*.json);;All Files (*)"
        )

        if file_path:
            if PoseSerializer.save_pose(file_path, model.skeleton, model.name):
                self._status_label.setText(f"Saved: {os.path.basename(file_path)}")
                self._refresh_pose_list()
            else:
                self._status_label.setText("Failed to save pose")

    def _on_apply_pose(self) -> None:
        """Handle apply pose button."""
        if not self._viewport:
            return

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
        """Handle double-click on pose list item."""
        if not self._viewport:
            return

        model = self._viewport.get_selected_model()
        if not model:
            self._status_label.setText("Select a model first")
            return

        pose_path = item.data(Qt.UserRole)
        self._apply_pose_file(pose_path, model)

    def _apply_pose_file(self, file_path: str, model: ModelInstance) -> None:
        """Apply a pose file to a model."""
        if not PoseSerializer or not model.skeleton:
            self._status_label.setText("Model has no skeleton")
            return

        snapshot = PoseSerializer.load_pose(file_path, model.skeleton)
        if snapshot:
            pose_name = os.path.splitext(os.path.basename(file_path))[0]
            self._status_label.setText(f"Applied: {pose_name}")
            self._viewport.update()
        else:
            self._status_label.setText(f"Failed to load: {file_path}")

    def _refresh_pose_list(self) -> None:
        """Refresh the list of available poses."""
        self._pose_list.clear()

        poses_dir = os.path.join(_pose_engine_dir, "poses")
        if not os.path.isdir(poses_dir):
            os.makedirs(poses_dir, exist_ok=True)
            return

        for filename in sorted(os.listdir(poses_dir)):
            if filename.endswith(".json"):
                file_path = os.path.join(poses_dir, filename)
                pose_name = os.path.splitext(filename)[0]

                item = QListWidgetItem(pose_name)
                item.setData(Qt.UserRole, file_path)
                self._pose_list.addItem(item)

    # -------------------------------------------------------------------------
    # Visibility Controls
    # -------------------------------------------------------------------------

    def _on_toggle_mesh(self, checked: bool) -> None:
        """Toggle mesh visibility."""
        if self._viewport:
            self._viewport.set_show_mesh(checked)

    def _on_toggle_skeleton(self, checked: bool) -> None:
        """Toggle skeleton visibility."""
        if self._viewport:
            self._viewport.set_show_skeleton(checked)

    def _on_toggle_joints(self, checked: bool) -> None:
        """Toggle joints visibility."""
        if self._viewport:
            self._viewport.set_show_joints(checked)

    def _on_toggle_gizmo(self, checked: bool) -> None:
        """Toggle gizmo visibility."""
        if self._viewport:
            self._viewport.set_show_gizmo(checked)

    # -------------------------------------------------------------------------
    # Gizmo Mode
    # -------------------------------------------------------------------------

    def _set_gizmo_mode(self, mode: str) -> None:
        """Set the gizmo mode."""
        self._rotation_btn.setChecked(mode == "rotation")
        self._movement_btn.setChecked(mode == "movement")
        self._scale_btn.setChecked(mode == "scale")

        if self._viewport:
            self._viewport.set_gizmo_mode(mode)

    def _toggle_gizmo_mode(self) -> None:
        """Toggle between gizmo modes."""
        if not self._viewport:
            return

        current_mode = self._viewport.get_gizmo_mode()
        if current_mode == "rotation":
            self._set_gizmo_mode("movement")
        elif current_mode == "movement":
            self._set_gizmo_mode("scale")
        else:
            self._set_gizmo_mode("rotation")

    # -------------------------------------------------------------------------
    # Krita Integration
    # -------------------------------------------------------------------------

    def _on_update(self) -> None:
        """Called by update timer."""
        # Could be used for animation updates
        pass

    def _on_sync_to_layer(self) -> None:
        """Handle sync to layer button click.""" 
        print("[SYNC] Sync button clicked!")
        
        # Always show feedback when button is clicked
        self._status_label.setText("Sync button clicked!")
        
        if not self._viewport:
            print("[SYNC] ERROR: No viewport available")
            self._status_label.setText("No viewport available")
            return
        
        print("[SYNC] Viewport available, checking GL initialization...")
        if hasattr(self._viewport, '_gl_initialized'):
            print(f"[SYNC] Viewport GL initialized: {self._viewport._gl_initialized}")
        else:
            print("[SYNC] Viewport GL initialization status unknown")
        
        print("[SYNC] Starting sync timer...")
        # Trigger sync with a slight delay to avoid UI lag
        self._sync_timer.start()
        
    def _do_sync(self) -> None:
        """Perform the actual sync to Krita layer."""
        print("[SYNC] Starting layer sync process...")
        
        if not self._viewport:
            print("[SYNC] ERROR: No viewport available")
            return
        
        try:
            print("[SYNC] Accessing Krita application...")
            # Access Krita application
            app = Krita.instance()
            doc = app.activeDocument()
            
            if not doc:
                print("[SYNC] ERROR: No active document")
                self._status_label.setText("No active document")
                return
            
            doc_w = doc.width()
            doc_h = doc.height()
            print(f"[SYNC] Document size: {doc_w}x{doc_h}")
            
            # Get the rendered image from multi-viewport
            # Use viewport size for aspect ratio calculation
            viewport_w = self._viewport.width()
            viewport_h = self._viewport.height()
            
            print(f"[SYNC] Viewport size: {viewport_w}x{viewport_h}")
            
            if viewport_w > 0 and viewport_h > 0:
                viewport_aspect = viewport_w / viewport_h
                doc_aspect = doc_w / doc_h
                
                print(f"[SYNC] Aspect ratios - viewport: {viewport_aspect:.3f}, document: {doc_aspect:.3f}")
                
                if viewport_aspect > doc_aspect:
                    # Viewport is wider - fit to doc height
                    render_h = doc_h
                    render_w = int(doc_h * viewport_aspect)
                    print(f"[SYNC] Fitting to document height: {render_w}x{render_h}")
                else:
                    # Doc is wider - fit to doc width
                    render_w = doc_w
                    render_h = int(doc_w / viewport_aspect)
                    print(f"[SYNC] Fitting to document width: {render_w}x{render_h}")
            else:
                render_w, render_h = doc_w, doc_h
                print(f"[SYNC] Using document size directly: {render_w}x{render_h}")
            
            print(f"[SYNC] Calling render_to_image({render_w}, {render_h})...")
            # Render the multi-viewport scene to an image
            img = self._viewport.render_to_image(render_w, render_h)
            
            if img.isNull():
                print("[SYNC] ERROR: Render returned null image")
                self._status_label.setText("Render failed - null image")
                return
            
            print(f"[SYNC] Render successful: {img.width()}x{img.height()}")
            
            print("[SYNC] Converting image format...")
            img = img.convertToFormat(QImage.Format_ARGB32)
            
            # Create document-sized image with proper centering if needed
            if render_w != doc_w or render_h != doc_h:
                print(f"[SYNC] Creating centered image {doc_w}x{doc_h} from {render_w}x{render_h}")
                final_img = QImage(doc_w, doc_h, QImage.Format_ARGB32)
                final_img.fill(QColor(0, 0, 0, 0))  # Transparent background
                
                # Calculate offset to center the rendered image
                offset_x = (doc_w - render_w) // 2
                offset_y = (doc_h - render_h) // 2
                print(f"[SYNC] Centering offset: ({offset_x}, {offset_y})")
                
                # Draw rendered image centered
                painter = QPainter(final_img)
                painter.drawImage(offset_x, offset_y, img)
                painter.end()
                
                img = final_img
                print("[SYNC] Centering complete")
            
            print("[SYNC] Finding or creating '3D View' layer...")
            # Find or create the "3D View" layer
            root = doc.rootNode()
            layer_name = "3D View"
            
            existing = None
            child_count = 0
            for child in root.childNodes():
                child_count += 1
                print(f"[SYNC] Checking layer: '{child.name()}'")
                if child.name() == layer_name:
                    existing = child
                    print(f"[SYNC] Found existing layer: '{layer_name}'")
                    break
            
            print(f"[SYNC] Total layers found: {child_count}")
            
            # Create or update layer
            if existing:
                print(f"[SYNC] Using existing layer")
                node = existing
            else:
                print(f"[SYNC] Creating new layer: '{layer_name}'")
                node = doc.createNode(layer_name, "paintlayer")
                root.addChildNode(node, None)
                print(f"[SYNC] Layer created and added to document")
            
            print(f"[SYNC] Setting pixel data ({img.byteCount()} bytes)...")
            # Set pixel data
            ptr = img.bits()
            ptr.setsize(img.byteCount())
            node.setPixelData(bytes(ptr), 0, 0, doc_w, doc_h)
            
            print("[SYNC] Refreshing document projection...")
            doc.refreshProjection()
            
            print(f"[SYNC] SUCCESS! Synced {doc_w}x{doc_h} to layer")
            self._status_label.setText(f"Synced {doc_w}x{doc_h} to layer")
            
        except Exception as e:
            print(f"[SYNC] ERROR: Exception during sync: {e}")
            import traceback
            traceback.print_exc() 
            self._status_label.setText(f"Sync failed: {e}")

    def canvasChanged(self, canvas, affected=None):
        """Called when the canvas changes (required by Krita)."""
        pass

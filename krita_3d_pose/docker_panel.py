"""
Krita 3D Poser Docker Panel
===========================

Main UI panel for the Krita 3D pose plugin.
Integrates the pose_engine with Krita's docker system.
"""

import os
import sys
from typing import Optional

# Add pose_engine to path
_plugin_dir = os.path.dirname(os.path.realpath(__file__))
_pose_engine_dir = os.path.dirname(_plugin_dir)
if _pose_engine_dir not in sys.path:
    sys.path.insert(0, _pose_engine_dir)

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QFileDialog, QSplitter, QMessageBox, QGroupBox
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QImage, QPainter, QColor

from krita import Krita, DockWidget

# Import pose_engine components
try:
    from pose_engine.skeleton import Skeleton
    from pose_engine.gltf.loader import GLBLoader
    from pose_engine.gltf.builder import build_skeleton_from_gltf, build_mesh_from_gltf, MeshData
    from pose_engine.ik import IKChain, CCDSolver
    from pose_engine.vec3 import Vec3
    from pose_engine.quat import Quat
    from pose_engine.ui.viewport import Viewport3D
    from pose_engine.ui.controls import BoneControls
except ImportError as e:
    # Fallback for when pose_engine isn't available
    Skeleton = None
    GLBLoader = None
    build_skeleton_from_gltf = None
    build_mesh_from_gltf = None
    MeshData = None
    IKChain = None
    CCDSolver = None
    Vec3 = None
    Quat = None
    Viewport3D = None
    BoneControls = None


class Krita3DPoserDocker(DockWidget):
    """
    Main docker panel for the 3D pose plugin.
    
    This is the entry point for the Krita plugin.
    """
    
    def __init__(self):
        """Create the docker panel."""
        super().__init__()
        
        self._skeleton: Optional[Skeleton] = None
        self._mesh_data: Optional[MeshData] = None
        self._ik_solver: Optional[CCDSolver] = None
        
        self.setWindowTitle("3D Pose Editor")
        self._setup_ui()
        
        # Update timer for continuous rendering
        self._update_timer = QTimer(self)
        self._update_timer.timeout.connect(self._on_update)
        self._update_timer.start(16)  # ~60 FPS
    
    def _setup_ui(self) -> None:
        """Set up the UI."""
        # Main widget
        main_widget = QWidget()
        self.setWidget(main_widget)
        
        layout = QVBoxLayout(main_widget)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # File controls
        file_group = QGroupBox("File")
        file_layout = QHBoxLayout(file_group)
        
        self._load_btn = QPushButton("Load Model")
        self._load_btn.clicked.connect(self._on_load_model)
        file_layout.addWidget(self._load_btn)
        
        self._reset_btn = QPushButton("Reset Pose")
        self._reset_btn.clicked.connect(self._on_reset_pose)
        file_layout.addWidget(self._reset_btn)
        
        layout.addWidget(file_group)
        
        # Main content splitter
        splitter = QSplitter(Qt.Vertical)
        
        # 3D Viewport
        if Viewport3D:
            self._viewport = Viewport3D()
            self._viewport.bone_selected.connect(self._on_bone_selected)
            splitter.addWidget(self._viewport)
        else:
            self._viewport = None
            placeholder = QLabel("OpenGL not available")
            placeholder.setAlignment(Qt.AlignCenter)
            splitter.addWidget(placeholder)
        
        # Bone controls
        if BoneControls:
            self._controls = BoneControls()
            self._controls.bone_rotation_changed.connect(self._on_bone_rotation_changed)
            self._controls.ik_target_changed.connect(self._on_ik_target_changed)
            self._controls.gizmo_mode_changed.connect(self._on_gizmo_mode_changed)
            splitter.addWidget(self._controls)
        else:
            self._controls = None
        
        # Set splitter sizes
        splitter.setSizes([400, 200])
        
        layout.addWidget(splitter)
        
        # Sync section (right under gizmo modes)
        sync_group = QGroupBox("Layer Sync")
        sync_layout = QHBoxLayout(sync_group)
        
        self._sync_btn = QPushButton("📷 Sync to Layer")
        self._sync_btn.clicked.connect(self._on_sync_to_layer)
        self._sync_btn.setEnabled(True)  # Always enable for debugging
        self._sync_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; padding: 8px;")
        sync_layout.addWidget(self._sync_btn)
        
        layout.addWidget(sync_group)
        
        # Status label
        self._status_label = QLabel("No model loaded")
        layout.addWidget(self._status_label)
        
        # Sync timer (for potential auto-sync functionality)
        self._sync_timer = QTimer()
        self._sync_timer.setSingleShot(True)
        self._sync_timer.setInterval(200)  # 200ms delay like original
        self._sync_timer.timeout.connect(self._do_sync)
    
    def _on_load_model(self) -> None:
        """Handle load model button."""
        # Open file dialog
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Load 3D Model",
            "",
            "GLB Files (*.glb);;All Files (*)"
        )
        
        if not file_path:
            return
        
        try:
            self._load_model(file_path)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load model: {e}")
    
    def _load_model(self, file_path: str) -> None:
        """Load a 3D model from file."""
        if not GLBLoader:
            raise RuntimeError("pose_engine not available")
        
        # Load GLB file
        loader = GLBLoader()
        glb_data = loader.load(file_path)
        
        # Build skeleton
        self._skeleton, bone_mapping = build_skeleton_from_gltf(glb_data, loader=loader)
        
        # Build mesh
        self._mesh_data = build_mesh_from_gltf(glb_data, bone_mapping=bone_mapping, loader=loader)
        
        # Create IK solver
        self._ik_solver = CCDSolver()
        
        # Update UI
        if self._viewport:
            self._viewport.set_skeleton(self._skeleton)
            self._viewport.set_mesh(self._mesh_data)
            self._viewport._frame_model()
        
        if self._controls:
            self._controls.set_skeleton(self._skeleton)
        
        self._status_label.setText(f"Loaded: {os.path.basename(file_path)} ({len(self._skeleton)} bones)")
    
    def _on_reset_pose(self) -> None:
        """Handle reset pose button."""
        if self._skeleton:
            self._skeleton.reset_pose()
            self._skeleton.update_all_transforms()
            
            if self._viewport:
                self._viewport.update()
            
            self._status_label.setText("Pose reset")
    
    def _on_bone_selected(self, bone_name: str) -> None:
        """Handle bone selection from viewport."""
        if self._controls:
            self._controls.set_selected_bone(bone_name)
        
        self._status_label.setText(f"Selected: {bone_name}")
    
    def _on_bone_rotation_changed(self, bone_name: str, rotation: Quat) -> None:
        """Handle bone rotation change from controls."""
        if not self._skeleton:
            return
        
        bone = self._skeleton.get_bone(bone_name)
        if bone:
            bone.set_pose_rotation(rotation)
            self._skeleton.update_all_transforms()
            
            if self._viewport:
                self._viewport.update()
    
    def _on_ik_target_changed(self, bone_name: str, target: Vec3) -> None:
        """Handle IK target change."""
        if not self._skeleton or not self._ik_solver:
            return
        
        # Find a suitable chain for IK
        # For simplicity, we'll use the bone's ancestors
        bone = self._skeleton.get_bone(bone_name)
        if not bone:
            return
        
        # Build chain from root to this bone
        chain_bones = []
        current = bone
        while current:
            chain_bones.insert(0, current)
            current = current.parent
        
        if len(chain_bones) < 2:
            self._status_label.setText("Chain too short for IK")
            return
        
        # Create IK chain
        from pose_engine.ik.solver import IKChain
        chain = IKChain(chain_bones)
        
        # Solve IK
        result = self._ik_solver.solve(chain, target)
        
        if result.success:
            self._status_label.setText(f"IK solved in {result.iterations} iterations")
        else:
            self._status_label.setText(f"IK: {result.message}")
        
        # Update transforms
        self._skeleton.update_all_transforms()
        
        if self._viewport:
            self._viewport.update()

    def _on_gizmo_mode_changed(self, mode: str) -> None:
        """Handle gizmo mode change from controls."""
        if self._viewport:
            self._viewport.set_gizmo_mode(mode)

    def _on_update(self) -> None:
        """Called by update timer."""
        # Could be used for animation
        pass
    
    def _on_sync_to_layer(self) -> None:
        """Handle sync to layer button click.""" 
        # Always show feedback when button is clicked
        self._status_label.setText("Sync button clicked!")
        
        if not self._viewport:
            self._status_label.setText("No viewport available")
            return
            
        # Trigger sync with a slight delay to avoid UI lag
        self._sync_timer.start()
        
    def _do_sync(self) -> None:
        """Perform the actual sync to Krita layer."""
        if not self._viewport:
            return
        
        try:
            # Access Krita application
            app = Krita.instance()
            doc = app.activeDocument()
            
            if not doc:
                self._status_label.setText("No active document")
                return
            
            doc_w = doc.width()
            doc_h = doc.height()
            
            # Calculate render size that matches viewport aspect ratio
            viewport_w = self._viewport.width()
            viewport_h = self._viewport.height()
            
            if viewport_w > 0 and viewport_h > 0:
                viewport_aspect = viewport_w / viewport_h
                doc_aspect = doc_w / doc_h
                
                if viewport_aspect > doc_aspect:
                    # Viewport is wider - fit to doc height
                    render_h = doc_h
                    render_w = int(doc_h * viewport_aspect)
                else:
                    # Doc is wider - fit to doc width
                    render_w = doc_w
                    render_h = int(doc_w / viewport_aspect)
            else:
                render_w, render_h = doc_w, doc_h
            
            # Render at the correct aspect ratio
            img = self._viewport.render_to_image(render_w, render_h)
            if img.isNull():
                self._status_label.setText("Render failed")
                return
            
            img = img.convertToFormat(QImage.Format_ARGB32)
            
            # Create document-sized image with proper centering if needed
            if render_w != doc_w or render_h != doc_h:
                final_img = QImage(doc_w, doc_h, QImage.Format_ARGB32)
                final_img.fill(QColor(0, 0, 0, 0))  # Transparent background
                
                # Calculate offset to center the rendered image
                offset_x = (doc_w - render_w) // 2
                offset_y = (doc_h - render_h) // 2
                
                # Draw rendered image centered
                painter = QPainter(final_img)
                painter.drawImage(offset_x, offset_y, img)
                painter.end()
                
                img = final_img
            
            # Find or create the "3D View" layer
            root = doc.rootNode()
            layer_name = "3D View"
            
            existing = None
            for child in root.childNodes():
                if child.name() == layer_name:
                    existing = child
                    break
            
            # Create or update layer
            node = existing if existing else doc.createNode(layer_name, "paintlayer")
            if not existing:
                root.addChildNode(node, None)
            
            # Set pixel data
            ptr = img.bits()
            ptr.setsize(img.byteCount())
            node.setPixelData(bytes(ptr), 0, 0, doc_w, doc_h)
            doc.refreshProjection()
            
            self._status_label.setText(f"Synced {doc_w}x{doc_h} to layer")
            
        except Exception as e:
            self._status_label.setText(f"Sync failed: {e}")
    
    def canvasChanged(self, canvas, affected=None):
        """Called when the canvas changes (required by Krita)."""
        pass

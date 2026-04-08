"""
MultiViewport3D - Qt OpenGL Widget for Multi-Model 3D Rendering
==============================================================

Provides a Qt widget that renders multiple 3D models using OpenGL.
Supports camera controls, bone selection across models, and gizmos.

This is the multi-model version of Viewport3D, using the Scene class
to manage multiple ModelInstances.
"""

import math
from typing import Optional, List, Tuple, Dict

from PyQt5.QtWidgets import QOpenGLWidget, QWidget, QFileDialog, QMessageBox
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QMouseEvent, QKeyEvent, QWheelEvent, QImage, QOpenGLFramebufferObject, QOpenGLFramebufferObjectFormat
from OpenGL.GL import (
    glClearColor, glEnable, glBlendFunc,
    GL_DEPTH_TEST, GL_BLEND, GL_SRC_ALPHA,
    GL_ONE_MINUS_SRC_ALPHA, glViewport, glClear,
    GL_COLOR_BUFFER_BIT, GL_DEPTH_BUFFER_BIT, 
    glGetIntegerv, GL_VIEWPORT
)

from ..vec3 import Vec3
from ..quat import Quat
from ..mat4 import Mat4
from ..bone import Bone
from ..scene import Scene
from ..model_instance import ModelInstance
from ..renderer.gl_renderer import GLRenderer
from ..renderer.skeleton_viz import SkeletonVisualizer
from ..renderer.gizmo import RotationGizmo, MovementGizmo, ScaleGizmo
from ..renderer.joint_renderer import JointRenderer


class Camera:
    """Orbit camera for viewing the 3D scene."""

    def __init__(self):
        """Create a new orbit camera."""
        self.target = Vec3(0, 1, 0)  # Look at center
        self.distance = 3.0
        self.yaw = 0.0  # Horizontal rotation
        self.pitch = 0.0  # Vertical rotation
        self.fov = 45.0
        self.near = 0.1
        self.far = 100.0

    def get_position(self) -> Vec3:
        """Get camera position in world space."""
        x = self.distance * math.sin(self.yaw) * math.cos(self.pitch)
        y = self.distance * math.sin(self.pitch)
        z = self.distance * math.cos(self.yaw) * math.cos(self.pitch)
        return self.target + Vec3(x, y, z)

    def get_view_matrix(self) -> Mat4:
        """Get the view matrix."""
        pos = self.get_position()

        # Look-at matrix
        forward = (self.target - pos).normalized()
        right = Vec3(0, 1, 0).cross(forward).normalized()
        up = forward.cross(right).normalized()

        # Column-major look-at matrix
        return Mat4([
            right.x, up.x, -forward.x, 0,
            right.y, up.y, -forward.y, 0,
            right.z, up.z, -forward.z, 0,
            -right.dot(pos), -up.dot(pos), forward.dot(pos), 1
        ])

    def get_projection_matrix(self, aspect: float) -> Mat4:
        """Get the projection matrix."""
        fov_rad = math.radians(self.fov)
        f = 1.0 / math.tan(fov_rad * 0.5)

        return Mat4([
            f / aspect, 0, 0, 0,
            0, f, 0, 0,
            0, 0, (self.far + self.near) / (self.near - self.far), -1,
            0, 0, (2 * self.far * self.near) / (self.near - self.far), 0
        ])

    def rotate(self, delta_yaw: float, delta_pitch: float) -> None:
        """Rotate the camera."""
        self.yaw += delta_yaw
        self.pitch = max(-math.pi * 0.49, min(math.pi * 0.49, self.pitch + delta_pitch))

    def zoom(self, delta: float) -> None:
        """Zoom the camera."""
        self.distance = max(0.5, min(50.0, self.distance * (1.0 - delta)))

    def move_forward(self, delta: float) -> None:
        """Move the camera forward/backward (dolly) toward/away from target."""
        self.distance = max(0.5, min(50.0, self.distance - delta))

    def pan(self, delta_x: float, delta_y: float) -> None:
        """Pan the camera target."""
        forward = (self.target - self.get_position()).normalized()
        right = Vec3(0, 1, 0).cross(forward).normalized()
        up = forward.cross(right).normalized()

        scale = self.distance * 0.002
        self.target = self.target + right * (-delta_x * scale) + up * (delta_y * scale)

    def frame_points(self, min_pt: Vec3, max_pt: Vec3) -> None:
        """Frame the camera to see the given bounding box."""
        center = Vec3(
            (min_pt.x + max_pt.x) / 2,
            (min_pt.y + max_pt.y) / 2,
            (min_pt.z + max_pt.z) / 2
        )
        self.target = center

        # Calculate required distance
        size = Vec3(
            max_pt.x - min_pt.x,
            max_pt.y - min_pt.y,
            max_pt.z - min_pt.z
        )
        max_dim = max(size.x, size.y, size.z)
        self.distance = max_dim * 2.0


class MultiViewport3D(QOpenGLWidget):
    """
    OpenGL widget for multi-model 3D viewing and posing.

    Features:
    - Orbit camera (rotate, zoom, pan)
    - Multiple model rendering
    - Skeleton visualization for each model
    - Mesh rendering with skinning
    - Hierarchical bone selection (model → bone)
    - Rotation and movement gizmos
    - Model-level transforms

    Signals:
        model_selected: Emitted when a model is selected (model_id)
        bone_selected: Emitted when a bone is selected (model_id, bone_name)
        pose_changed: Emitted when any pose changes
    """

    model_selected = pyqtSignal(str) # model_id
    bone_selected = pyqtSignal(str, str) # model_id, bone_name
    pose_changed = pyqtSignal()
    model_selection_changed = pyqtSignal(str) # model_id - emitted when active model changes

    def __init__(self, parent: Optional[QWidget] = None):
        """Create a new multi-model 3D viewport."""
        super().__init__(parent)

        # Scene management
        self._scene = Scene()

        # Per-model GPU resources
        self._model_renderers: Dict[str, GLRenderer] = {}
        self._model_skeleton_viz: Dict[str, SkeletonVisualizer] = {}

        # Shared resources
        self._gizmo: Optional[RotationGizmo] = None
        self._movement_gizmo: Optional[MovementGizmo] = None
        self._scale_gizmo: Optional[ScaleGizmo] = None
        self._joint_renderer: Optional[JointRenderer] = None

        # Gizmo mode
        self._gizmo_mode: str = "rotation"

        # Camera
        self._camera = Camera()

        # Mouse state
        self._last_mouse_pos = None
        self._mouse_button = None

        # Render options
        self._show_mesh = True
        self._show_skeleton = True
        self._show_joints = True
        self._show_gizmo = True

        # Joint hover state
        self._hovered_model_id: Optional[str] = None
        self._hovered_bone_name: Optional[str] = None

        # Gizmo interaction state
        self._gizmo_state: str = "idle"
        self._gizmo_hover_axis: Optional[str] = None
        self._gizmo_drag_axis: Optional[str] = None
        self._gizmo_drag_start_point: Optional[Vec3] = None
        self._gizmo_drag_prev_point: Optional[Vec3] = None
        self._accumulated_rotation: Optional[Quat] = None
        self._initial_bone_rotation: Optional[Quat] = None
        self._initial_delta_rotation: Optional[Quat] = None

        # Dirty flags
        self._gl_initialized = False

        # Set focus policy
        self.setFocusPolicy(Qt.StrongFocus)

        # Enable mouse tracking to receive mouse move events when no button is pressed
        self.setMouseTracking(True)

        # Update timer
        self._update_timer = QTimer(self)
        self._update_timer.timeout.connect(self._on_update)
        self._update_timer.start(16)  # ~60 FPS

    # -------------------------------------------------------------------------
    # Scene Access
    # -------------------------------------------------------------------------

    def get_scene(self) -> Scene:
        """Get the scene object."""
        return self._scene

    def add_model(self, file_path: str, name: Optional[str] = None) -> Optional[ModelInstance]:
        """
        Add a model to the scene.

        Args:
            file_path: Path to the GLB file
            name: Optional display name

        Returns:
            The ModelInstance, or None on error
        """
        try:
            model = self._scene.add_model_from_file(file_path, name)

            # Initialize GPU resources if OpenGL is ready
            # Must make context current before OpenGL operations
            if self._gl_initialized:
                self.makeCurrent()
                self._init_model_gl_resources(model)
                self.doneCurrent()

            # Frame the new model
            self._frame_scene()

            self.update()
            return model

        except Exception as e:
            print(f"Error loading model: {e}")
            return None

    def remove_model(self, model_id: str) -> None:
        """Remove a model from the scene."""
        # Clean up GPU resources
        if model_id in self._model_renderers:
            # Renderer cleanup would go here
            del self._model_renderers[model_id]
        if model_id in self._model_skeleton_viz:
            del self._model_skeleton_viz[model_id]

        self._scene.remove_model(model_id)
        self.update()

    def duplicate_model(self, model_id: str) -> Optional[ModelInstance]:
        """Duplicate a model in the scene."""
        copy = self._scene.duplicate_model(model_id)
        if copy and self._gl_initialized:
            self.makeCurrent()
            self._init_model_gl_resources(copy)
            self.doneCurrent()
            self.update()
        return copy

    # -------------------------------------------------------------------------
    # Selection
    # -------------------------------------------------------------------------

    def select_model(self, model_id: Optional[str]) -> None:
        """Select a model by ID."""
        self._scene.select_model(model_id)
        self.update()
        if model_id:
            self.model_selected.emit(model_id)

    def select_bone(self, model_id: str, bone_name: str) -> None:
        """Select a bone in a specific model."""
        old_model_id = self._scene.get_selected_model_id()
        self._scene.select_bone(model_id, bone_name)
        self.update()
        self.bone_selected.emit(model_id, bone_name)
        
        # Emit model selection change if model changed
        if model_id != old_model_id:
            self.model_selection_changed.emit(model_id)

    def get_selected_model(self) -> Optional[ModelInstance]:
        """Get the selected model."""
        return self._scene.get_selected_model()

    def get_selected_bone(self) -> Tuple[Optional[ModelInstance], Optional[Bone]]:
        """Get the selected bone and its model."""
        return self._scene.get_selected_bone()

    # -------------------------------------------------------------------------
    # Visibility
    # -------------------------------------------------------------------------

    def set_show_mesh(self, show: bool) -> None:
        """Set mesh visibility."""
        self._show_mesh = show
        self.update()

    def set_show_skeleton(self, show: bool) -> None:
        """Set skeleton visibility."""
        self._show_skeleton = show
        self.update()

    def set_show_joints(self, show: bool) -> None:
        """Set joint spheres visibility."""
        self._show_joints = show
        self.update()

    def set_show_gizmo(self, show: bool) -> None:
        """Set gizmo visibility."""
        self._show_gizmo = show
        self.update()

    def set_model_visible(self, model_id: str, visible: bool) -> None:
        """Set visibility for a specific model."""
        model = self._scene.get_model(model_id)
        if model:
            model.visible = visible
            self.update()

    # -------------------------------------------------------------------------
    # Gizmo Mode
    # -------------------------------------------------------------------------

    def set_gizmo_mode(self, mode: str) -> None:
        """Set gizmo mode ('rotation', 'movement', or 'scale')."""
        if mode in ("rotation", "movement", "scale"):
            self._gizmo_mode = mode
            self.update()
    
    def get_gizmo_mode(self) -> str:
        """Get current gizmo mode."""
        return self._gizmo_mode
    
    def toggle_gizmo_mode(self) -> None:
        """Cycle through rotation, movement, and scale modes."""
        if self._gizmo_mode == "rotation":
            self._gizmo_mode = "movement"
        elif self._gizmo_mode == "movement":
            self._gizmo_mode = "scale"
        else:
            self._gizmo_mode = "rotation"
        self.update()

    # -------------------------------------------------------------------------
    # Camera
    # -------------------------------------------------------------------------

    def frame_all(self) -> None:
        """Frame all visible models in the view."""
        self._frame_scene()

    def frame_selected(self) -> None:
        """Frame the selected model."""
        model = self.get_selected_model()
        if model and model.skeleton:
            min_pt, max_pt = Vec3(float('inf'), float('inf'), float('inf')), \
                            Vec3(float('-inf'), float('-inf'), float('-inf'))
            for bone in model.skeleton:
                pos = bone.get_world_position()
                min_pt = Vec3(min(min_pt.x, pos.x), min(min_pt.y, pos.y), min(min_pt.z, pos.z))
                max_pt = Vec3(max(max_pt.x, pos.x), max(max_pt.y, pos.y), max(max_pt.z, pos.z))
            self._camera.frame_points(min_pt, max_pt)
            self.update()

    def _frame_scene(self) -> None:
        """Frame all models in the scene."""
        min_pt, max_pt = self._scene.get_bounding_box()
        self._camera.frame_points(min_pt, max_pt)
        self.update()

    # -------------------------------------------------------------------------
    # OpenGL Implementation
    # -------------------------------------------------------------------------

    def initializeGL(self) -> None:
        """Initialize OpenGL resources."""
        glClearColor(0.2, 0.2, 0.2, 1.0)
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        # Create shared resources
        self._gizmo = RotationGizmo()
        if not self._gizmo.initialize():
            print("Failed to initialize RotationGizmo")

        self._movement_gizmo = MovementGizmo()
        if not self._movement_gizmo.initialize():
            print("Failed to initialize MovementGizmo")

        self._scale_gizmo = ScaleGizmo()
        if not self._scale_gizmo.initialize():
            print("Failed to initialize ScaleGizmo")

        self._joint_renderer = JointRenderer()
        if not self._joint_renderer.initialize():
            print("Failed to initialize JointRenderer")

        # Initialize resources for existing models
        for model in self._scene.get_all_models():
            self._init_model_gl_resources(model)

        self._gl_initialized = True

    def _init_model_gl_resources(self, model: ModelInstance) -> None:
        """Initialize GPU resources for a model."""
        if model.id in self._model_renderers:
            return

        # Create renderer
        renderer = GLRenderer()
        if renderer.initialize():
            self._model_renderers[model.id] = renderer
        else:
            return

        # Upload mesh if available
        if model.mesh_data and model.mesh_data.positions:
            renderer.upload_mesh(
                model.mesh_data.positions,
                model.mesh_data.normals,
                model.mesh_data.indices,
                model.mesh_data.skinning_data
            )

        # Create skeleton visualizer
        viz = SkeletonVisualizer()
        if viz.initialize():
            self._model_skeleton_viz[model.id] = viz

    def resizeGL(self, w: int, h: int) -> None:
        """Handle resize."""
        glViewport(0, 0, w, h)

    def paintGL(self) -> None:
        """Render the scene."""
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        aspect = self.width() / max(1, self.height())
        view = self._camera.get_view_matrix()
        proj = self._camera.get_projection_matrix(aspect)

        # Render all visible models
        for model in self._scene.get_all_models():
            if not model.visible:
                continue

            # Get model's world transform
            model_matrix = model.transform.to_matrix()

            # Render mesh
            if self._show_mesh and model.id in self._model_renderers and model.mesh_data:
                renderer = self._model_renderers[model.id]
                renderer.render(model.skeleton, view, proj, model_matrix)

            # Render skeleton
            if self._show_skeleton and model.id in self._model_skeleton_viz and model.skeleton:
                viz = self._model_skeleton_viz[model.id]
                viz.update_skeleton(model.skeleton)
                # Use orange color for skeleton lines, pass model_matrix for world transform
                viz.render(view, proj, (1.0, 0.5, 0.0), model_matrix=model_matrix)

        # Render joints for all models
        if self._show_joints and self._joint_renderer:
            self._render_all_joints(view, proj)

        # Render gizmo for selected bone
        if self._show_gizmo:
            self._render_gizmo(view, proj)

    def _render_all_joints(self, view: Mat4, proj: Mat4) -> None:
        """Render joint spheres for all visible models."""
        selected_model, selected_bone = self._scene.get_selected_bone()

        for model in self._scene.get_all_models():
            if not model.visible or not model.skeleton:
                continue

            model_matrix = model.transform.to_matrix()
            joint_scale = self._camera.distance * 0.15

            # Determine selected/hovered bones for this model
            sel_bone = selected_bone.name if (selected_model == model and selected_bone) else None
            hov_bone = self._hovered_bone_name if self._hovered_model_id == model.id else None

            self._joint_renderer.render(
                model.skeleton,
                view,
                proj,
                selected_bone=sel_bone,
                hovered_bone=hov_bone,
                scale=joint_scale,
                model_matrix=model_matrix
            )

    def _render_gizmo(self, view: Mat4, proj: Mat4) -> None:
        """Render the gizmo for the selected bone."""
        model, bone = self._scene.get_selected_bone()
        if not bone or not model:
            return

        # Get bone world position
        bone_world_pos = bone.get_world_position()
        model_world = model.transform.to_matrix()

        # Transform to scene space
        gizmo_pos = model_world.transform_point(bone_world_pos)
        gizmo_scale = self._camera.distance * 0.15

        if self._gizmo_mode == "rotation" and self._gizmo:
            self._gizmo.render(
                gizmo_pos,
                gizmo_scale,
                view,
                proj,
                hovered_axis=self._gizmo_hover_axis if self._gizmo_state != "dragging" else None,
                dragging_axis=self._gizmo_drag_axis if self._gizmo_state == "dragging" else None
            )
        elif self._gizmo_mode == "movement" and self._movement_gizmo:
            self._movement_gizmo.render(
                gizmo_pos,
                gizmo_scale,
                view,
                proj,
                hovered_axis=self._gizmo_hover_axis if self._gizmo_state != "dragging" else None,
                dragging_axis=self._gizmo_drag_axis if self._gizmo_state == "dragging" else None
            )
        elif self._gizmo_mode == "scale" and self._scale_gizmo:
            self._scale_gizmo.render(
                gizmo_pos,
                gizmo_scale,
                view,
                proj,
                hovered_axis=self._gizmo_hover_axis if self._gizmo_state != "dragging" else None,
                dragging_axis=self._gizmo_drag_axis if self._gizmo_state == "dragging" else None
            )

    def render_to_image(self, width: int, height: int) -> QImage:
        """Render the 3D scene to a QImage at the specified dimensions.
        
        Args:
            width: Target image width in pixels
            height: Target image height in pixels
            
        Returns:
            QImage containing the rendered scene, or null image if rendering fails
        """
        print(f"[RENDER] Starting render_to_image({width}, {height})")
        
        if not self._gl_initialized:
            print("[RENDER] ERROR: GL not initialized")
            return QImage()
        
        # Make sure we're using the widget's context (where all GL objects were created)
        try:
            print("[RENDER] Making widget context current...")
            self.makeCurrent()
            
            # Store original viewport
            orig_viewport = glGetIntegerv(GL_VIEWPORT)
            print(f"[RENDER] Original viewport: {orig_viewport}")
            
            # Create framebuffer object in the SAME context as the widget
            print("[RENDER] Creating framebuffer object in widget context...")
            fbo_format = QOpenGLFramebufferObjectFormat()
            fbo_format.setSamples(4)  # Anti-aliasing
            fbo_format.setAttachment(QOpenGLFramebufferObject.CombinedDepthStencil)
            
            fbo = QOpenGLFramebufferObject(width, height, fbo_format)
            if not fbo.isValid():
                print("[RENDER] ERROR: Framebuffer object is not valid")
                return QImage()
                
            print(f"[RENDER] Framebuffer created successfully: {fbo.width()}x{fbo.height()}")
            
            # Bind framebuffer and set viewport (but stay in same context)
            if not fbo.bind():
                print("[RENDER] ERROR: Failed to bind framebuffer")
                return QImage()
                
            glViewport(0, 0, width, height)
            print(f"[RENDER] Viewport set to {width}x{height}")
            
            # Clear buffers
            glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
            print("[RENDER] Buffers cleared")
            
            # Calculate matrices for the target resolution
            aspect = width / max(1, height)
            view = self._camera.get_view_matrix()
            proj = self._camera.get_projection_matrix(aspect)
            print(f"[RENDER] Matrices calculated (aspect: {aspect})")

            # Count visible models
            visible_models = [m for m in self._scene.get_all_models() if m.visible]
            print(f"[RENDER] Found {len(visible_models)} visible models out of {len(self._scene.get_all_models())}")

            # Render all visible models - now all GL objects should be valid
            for i, model in enumerate(visible_models):
                print(f"[RENDER] Rendering model {i+1}/{len(visible_models)}: {model.name} (id: {model.id})")

                # Get model's world transform
                model_matrix = model.transform.to_matrix()

                # Render mesh
                if self._show_mesh and model.id in self._model_renderers and model.mesh_data:
                    print(f"[RENDER]   - Rendering mesh for {model.name}")
                    renderer = self._model_renderers[model.id]
                    renderer.render(model.skeleton, view, proj, model_matrix)
                else:
                    reasons = []
                    if not self._show_mesh: reasons.append("mesh disabled")
                    if model.id not in self._model_renderers: reasons.append("no renderer")
                    if not model.mesh_data: reasons.append("no mesh data")
                    print(f"[RENDER]   - Skipping mesh: {', '.join(reasons)}")

                # Render skeleton
                if self._show_skeleton and model.id in self._model_skeleton_viz and model.skeleton:
                    print(f"[RENDER]   - Rendering skeleton for {model.name}")
                    viz = self._model_skeleton_viz[model.id]
                    viz.update_skeleton(model.skeleton)
                    viz.render(view, proj, (1.0, 0.5, 0.0), model_matrix=model_matrix)
                else:
                    reasons = []
                    if not self._show_skeleton: reasons.append("skeleton disabled")
                    if model.id not in self._model_skeleton_viz: reasons.append("no viz")
                    if not model.skeleton: reasons.append("no skeleton")
                    print(f"[RENDER]   - Skipping skeleton: {', '.join(reasons)}")

            # Render joints for all models
            if self._show_joints and self._joint_renderer:
                print("[RENDER] Rendering joints for all models")
                self._render_all_joints(view, proj)
            else:
                reasons = []
                if not self._show_joints: reasons.append("joints disabled")
                if not self._joint_renderer: reasons.append("no joint renderer")
                print(f"[RENDER] Skipping joints: {', '.join(reasons)}")

            # Render gizmo for selected bone
            if self._show_gizmo:
                model, bone = self._scene.get_selected_bone()
                if model and bone:
                    print(f"[RENDER] Rendering gizmo for {model.name}/{bone.name}")
                    self._render_gizmo(view, proj)
                else:
                    print("[RENDER] Skipping gizmo: no selected bone")
            else:
                print("[RENDER] Skipping gizmo: disabled")
            
            print("[RENDER] Getting rendered image from framebuffer...")
            # Get the rendered image
            image = fbo.toImage()
            
            # Release framebuffer
            fbo.release()
            
            # Restore original viewport
            glViewport(orig_viewport[0], orig_viewport[1], orig_viewport[2], orig_viewport[3])
            print(f"[RENDER] Restored viewport to {orig_viewport}")
            
            print(f"[RENDER] Success! Image: {image.width()}x{image.height()}, null: {image.isNull()}")
            return image
            
        except Exception as e:
            print(f"[RENDER] ERROR: Exception during render: {e}")
            import traceback
            traceback.print_exc()
            
            # Best effort cleanup
            try:
                if 'orig_viewport' in locals():
                    glViewport(orig_viewport[0], orig_viewport[1], orig_viewport[2], orig_viewport[3])
            except Exception as cleanup_e:
                print(f"[RENDER] ERROR: Failed to restore viewport: {cleanup_e}")
            return QImage()

    # -------------------------------------------------------------------------
    # Event Handling
    # -------------------------------------------------------------------------

    def _on_update(self) -> None:
        """Timer update callback."""
        # Could be used for animation updates
        pass

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Handle mouse press."""
        self._last_mouse_pos = event.pos()
        self._mouse_button = event.button()

        if event.button() == Qt.LeftButton:
            # Check for gizmo interaction first
            if self._show_gizmo and self._gizmo_hover_axis:
                self._start_gizmo_drag(event.pos())
            else:
                # Try to pick a joint
                self._pick_joint(event.pos())

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Handle mouse move."""
        if self._last_mouse_pos is None:
            # No button pressed - just update hover state
            self._update_gizmo_hover(event.pos())
            self.update()
            return

        dx = event.x() - self._last_mouse_pos.x()
        dy = event.y() - self._last_mouse_pos.y()

        if self._gizmo_state == "dragging":
            self._update_gizmo_drag(event.pos())
        elif self._mouse_button == Qt.LeftButton:
            modifiers = event.modifiers()
            if modifiers & Qt.ShiftModifier:
                # Shift+Left: Rotate camera
                self._camera.rotate(dx * 0.01, dy * 0.01)
            elif modifiers & Qt.ControlModifier:
                # Ctrl+Left: Pan camera
                self._camera.pan(dx, dy)
            else:
                # No modifier: update gizmo hover
                self._update_gizmo_hover(event.pos())
        elif self._mouse_button == Qt.MiddleButton:
            self._camera.pan(dx, dy)
        elif self._mouse_button == Qt.RightButton:
            modifiers = event.modifiers()
            if modifiers & Qt.ShiftModifier:
                # Shift+Right: Pan camera
                self._camera.pan(dx, dy)
            elif modifiers & Qt.ControlModifier:
                # Ctrl+Right: Zoom camera
                self._camera.zoom(dy * 0.01)
            else:
                # Right: Rotate camera
                self._camera.rotate(dx * 0.01, dy * 0.01)

        self._last_mouse_pos = event.pos()
        self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Handle mouse release."""
        if self._gizmo_state == "dragging":
            self._end_gizmo_drag()

        self._mouse_button = None
        self._last_mouse_pos = None
        self.update()

    def wheelEvent(self, event: QWheelEvent) -> None:
        """Handle mouse wheel."""
        delta = event.angleDelta().y() / 120.0
        modifiers = event.modifiers()
        if modifiers & Qt.ControlModifier:
            # Ctrl+Scroll: Move camera forward/backward (dolly)
            self._camera.move_forward(delta * 0.2)
        else:
            # Default: Zoom
            self._camera.zoom(delta * 0.1)
        self.update()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Handle key press."""
        key = event.key()

        if key == Qt.Key_F:
            self.frame_all()
        elif key == Qt.Key_T:
            self.set_show_mesh(not self._show_mesh)
        elif key == Qt.Key_S:
            self.set_show_skeleton(not self._show_skeleton)
        elif key == Qt.Key_G:
            self.toggle_gizmo_mode()
        elif key == Qt.Key_R:
            self._camera = Camera()
            self._frame_scene()

    # -------------------------------------------------------------------------
    # Joint Picking
    # -------------------------------------------------------------------------

    def _pick_joint(self, mouse_pos) -> None:
        """Pick a joint under the mouse cursor."""
        # Uses proper screen projection matching joint_renderer._project_to_screen

        best_model_id = None
        best_bone_name = None
        best_dist = float('inf')

        aspect = self.width() / max(1, self.height())
        view = self._camera.get_view_matrix()
        proj = self._camera.get_projection_matrix(aspect)
        view_proj = proj * view

        # Viewport is (x, y, width, height)
        viewport = (0, 0, self.width(), self.height())

        for model in self._scene.get_all_models():
            if not model.visible or not model.skeleton:
                continue

            joint_scale = self._camera.distance * 0.15

            for bone in model.skeleton:
                # Get bone world position (already in world space)
                world_pos = bone.get_world_position()

                # Project to screen using proper projection
                screen_x, screen_y = self._project_to_screen(world_pos, view_proj, viewport)

                # Distance from mouse
                dx = mouse_pos.x() - screen_x
                dy = mouse_pos.y() - screen_y
                dist = math.sqrt(dx * dx + dy * dy)

                # Check if within joint radius
                radius = joint_scale * 50 # Approximate screen radius
                if dist < radius and dist < best_dist:
                    best_dist = dist
                    best_model_id = model.id
                    best_bone_name = bone.name

        if best_model_id and best_bone_name:
            self.select_bone(best_model_id, best_bone_name)

    def _project_to_screen(
        self,
        world_pos: Vec3,
        view_proj: Mat4,
        viewport: Tuple[int, int, int, int]
    ) -> Tuple[float, float]:
        """
        Project a world position to screen coordinates.

        This matches the implementation in joint_renderer._project_to_screen
        to ensure consistent hit testing between rendering and selection.

        Args:
            world_pos: Position in world space
            view_proj: View-projection matrix
            viewport: (x, y, width, height)

        Returns:
            (screen_x, screen_y) in window coordinates
        """
        m = view_proj.m
        x = m[0] * world_pos.x + m[4] * world_pos.y + m[8] * world_pos.z + m[12]
        y = m[1] * world_pos.x + m[5] * world_pos.y + m[9] * world_pos.z + m[13]
        w = m[3] * world_pos.x + m[7] * world_pos.y + m[11] * world_pos.z + m[15]

        if abs(w) < 1e-10:
            w = 1e-10

        # Perspective divide to get NDC
        ndc_x = x / w
        ndc_y = y / w

        # Convert to window coordinates
        screen_x = viewport[0] + (ndc_x + 1.0) * 0.5 * viewport[2]
        screen_y = viewport[1] + (1.0 - ndc_y) * 0.5 * viewport[3]  # Y is inverted

        return (screen_x, screen_y)

    # -------------------------------------------------------------------------
    # Gizmo Interaction
    # -------------------------------------------------------------------------

    def _update_gizmo_hover(self, mouse_pos) -> None:
        """Update gizmo hover state."""
        model, bone = self._scene.get_selected_bone()
        if not bone or not model:
            self._gizmo_hover_axis = None
            return

        gizmo_pos = self._get_gizmo_position()
        if gizmo_pos is None:
            self._gizmo_hover_axis = None
            return

        gizmo_scale = self._camera.distance * 0.15
        aspect = self.width() / max(1, self.height())
        view = self._camera.get_view_matrix()
        proj = self._camera.get_projection_matrix(aspect)
        viewport = (0, 0, self.width(), self.height())

        if self._gizmo_mode == "rotation" and self._gizmo:
            self._gizmo_hover_axis = self._gizmo.hit_test(
                (mouse_pos.x(), mouse_pos.y()),
                gizmo_pos, gizmo_scale, view, proj, viewport
            )
        elif self._gizmo_mode == "movement" and self._movement_gizmo:
            self._gizmo_hover_axis = self._movement_gizmo.hit_test(
                (mouse_pos.x(), mouse_pos.y()),
                gizmo_pos, gizmo_scale, view, proj, viewport
            )
        elif self._gizmo_mode == "scale" and self._scale_gizmo:
            self._gizmo_hover_axis = self._scale_gizmo.hit_test(
                (mouse_pos.x(), mouse_pos.y()),
                gizmo_pos, gizmo_scale, view, proj, viewport
            )
        else:
            self._gizmo_hover_axis = None

    def _get_gizmo_position(self) -> Optional[Vec3]:
        """Get the world position for the gizmo."""
        model, bone = self._scene.get_selected_bone()
        if not bone or not model:
            return None

        # Get bone position in skeleton-local space
        bone_pos = bone.get_world_position()
        
        # Transform to world space using model's transform
        model_matrix = model.transform.to_matrix()
        return model_matrix.transform_point(bone_pos)

    def _start_gizmo_drag(self, mouse_pos) -> bool:
        """Start dragging the gizmo."""
        model, bone = self._scene.get_selected_bone()
        if not bone or not model:
            return False
        
        # Ensure this model is the selected model (safety check)
        if model.id != self._scene.get_selected_model_id():
            return False

        gizmo_pos = self._get_gizmo_position()
        if gizmo_pos is None:
            return False

        gizmo_scale = self._camera.distance * 0.15
        aspect = self.width() / max(1, self.height())
        view = self._camera.get_view_matrix()
        proj = self._camera.get_projection_matrix(aspect)
        viewport = (0, 0, self.width(), self.height())

        if self._gizmo_mode == "rotation":
            # Get the starting point on the circle plane
            if self._gizmo:
                start_point = self._gizmo.get_point_on_circle_plane(
                    (mouse_pos.x(), mouse_pos.y()),
                    self._gizmo_hover_axis,
                    gizmo_pos,
                    gizmo_scale,
                    view,
                    proj,
                    viewport
                )
                if start_point is None:
                    return False

                self._gizmo_state = "dragging"
                self._gizmo_drag_axis = self._gizmo_hover_axis
                self._gizmo_drag_start_point = start_point
                self._gizmo_drag_prev_point = start_point
                self._accumulated_rotation = Quat.identity()
                self._initial_bone_rotation = bone.pose_transform.rotation
                self._initial_delta_rotation = self._get_world_delta_rotation(bone)
                return True
        elif self._gizmo_mode == "movement":
            if self._movement_gizmo:
                if self._gizmo_hover_axis == 'CENTER':
                    start_point = self._movement_gizmo.get_point_on_plane(
                        (mouse_pos.x(), mouse_pos.y()),
                        gizmo_pos,
                        view,
                        proj,
                        viewport
                    )
                else:
                    start_point = self._movement_gizmo.get_point_on_axis(
                        (mouse_pos.x(), mouse_pos.y()),
                        self._gizmo_hover_axis,
                        gizmo_pos,
                        gizmo_scale,
                        view,
                        proj,
                        viewport
                    )
                if start_point is None:
                    return False

                self._gizmo_state = "dragging"
                self._gizmo_drag_axis = self._gizmo_hover_axis
                self._gizmo_drag_start_point = start_point
                self._gizmo_drag_prev_point = start_point
                self._movement_drag_start_pos = bone.get_world_position()
                self._movement_drag_prev_pos = self._movement_drag_start_pos
                return True
        elif self._gizmo_mode == "scale":
            if self._scale_gizmo:
                start_point = self._scale_gizmo.get_point_on_axis(
                    (mouse_pos.x(), mouse_pos.y()),
                    self._gizmo_hover_axis,
                    gizmo_pos,
                    gizmo_scale,
                    view,
                    proj,
                    viewport
                )
                if start_point is None:
                    return False

                self._gizmo_state = "dragging"
                self._gizmo_drag_axis = self._gizmo_hover_axis
                self._gizmo_drag_start_point = start_point
                self._gizmo_drag_prev_point = start_point
                self._scale_drag_start_scale = model.transform.scale
                return True

        return False

    def _update_gizmo_drag(self, mouse_pos) -> None:
        """Update gizmo dragging."""
        if self._gizmo_state != "dragging" or self._gizmo_drag_axis is None:
            return

        model, bone = self._scene.get_selected_bone()
        if not bone or not model:
            return

        gizmo_pos = self._get_gizmo_position()
        if gizmo_pos is None:
            return

        gizmo_scale = self._camera.distance * 0.15
        aspect = self.width() / max(1, self.height())
        view = self._camera.get_view_matrix()
        proj = self._camera.get_projection_matrix(aspect)
        viewport = (0, 0, self.width(), self.height())

        if self._gizmo_mode == "rotation":
            self._update_rotation_gizmo_drag(mouse_pos, bone, model, gizmo_pos, gizmo_scale, view, proj, viewport)
        elif self._gizmo_mode == "movement":
            self._update_movement_gizmo_drag(mouse_pos, bone, model, gizmo_pos, gizmo_scale, view, proj, viewport)
        elif self._gizmo_mode == "scale":
            self._update_scale_gizmo_drag(mouse_pos, bone, model, gizmo_pos, gizmo_scale, view, proj, viewport)

    def _update_rotation_gizmo_drag(self, mouse_pos, bone, model, gizmo_pos, gizmo_scale, view, proj, viewport) -> None:
        """Update bone rotation during rotation gizmo drag."""
        if self._initial_delta_rotation is None or not self._gizmo:
            return

        current_point = self._gizmo.get_point_on_circle_plane(
            (mouse_pos.x(), mouse_pos.y()),
            self._gizmo_drag_axis,
            gizmo_pos,
            gizmo_scale,
            view,
            proj,
            viewport
        )

        if current_point is None or self._gizmo_drag_prev_point is None:
            return

        # Calculate incremental rotation delta
        incremental_rotation = self._gizmo.get_rotation_from_drag(
            self._gizmo_drag_prev_point,
            current_point,
            self._gizmo_drag_axis,
            gizmo_pos
        )

        # Accumulate the rotation
        self._accumulated_rotation = incremental_rotation * self._accumulated_rotation

        # Apply the accumulated rotation to the initial world-space delta
        new_delta_rotation = self._accumulated_rotation * self._initial_delta_rotation

        # Apply the world-space delta rotation to the bone
        self._apply_world_delta_rotation(bone, new_delta_rotation)

        # Update previous point
        self._gizmo_drag_prev_point = current_point

        # Mark skeleton as needing update
        if model and model.skeleton:
            for b in model.skeleton:
                b._mark_dirty()

    def _update_movement_gizmo_drag(self, mouse_pos, bone, model, gizmo_pos, gizmo_scale, view, proj, viewport) -> None:
        """Update bone position during movement gizmo drag."""
        if not self._movement_gizmo:
            return

        if self._gizmo_drag_axis == 'CENTER':
            current_point = self._movement_gizmo.get_point_on_plane(
                (mouse_pos.x(), mouse_pos.y()),
                gizmo_pos,
                view,
                proj,
                viewport
            )
            if current_point is None or self._gizmo_drag_prev_point is None:
                return
            delta = current_point - self._gizmo_drag_prev_point
            movement_speed = 0.5
            delta = delta * movement_speed
            self._apply_movement_delta(bone, delta)
            self._gizmo_drag_prev_point = current_point
        else:
            # CRITICAL FIX: Use the INITIAL gizmo position as the axis reference point
            # The axis line must stay fixed in space during the drag, not move with the bone
            # If we use the current gizmo_pos, the axis shifts as the bone moves, causing drift
            initial_gizmo_pos = self._movement_drag_start_pos
            if initial_gizmo_pos is None:
                initial_gizmo_pos = gizmo_pos

            current_point = self._movement_gizmo.get_point_on_axis(
                (mouse_pos.x(), mouse_pos.y()),
                self._gizmo_drag_axis,
                initial_gizmo_pos,  # Use initial position, not current!
                gizmo_scale,
                view,
                proj,
                viewport
            )
            if current_point is None or self._gizmo_drag_prev_point is None:
                return
            
            # Calculate the raw delta from mouse movement
            raw_delta = current_point - self._gizmo_drag_prev_point

            # Get the axis direction vector (world space)
            if self._gizmo_drag_axis == 'X':
                axis_dir = Vec3(1, 0, 0)
            elif self._gizmo_drag_axis == 'Y':
                axis_dir = Vec3(0, 1, 0)
            else:  # Z
                axis_dir = Vec3(0, 0, 1)

            # Project the delta onto the axis to ensure movement is ONLY along that axis
            # This prevents any perpendicular drift
            dot_product = raw_delta.x * axis_dir.x + raw_delta.y * axis_dir.y + raw_delta.z * axis_dir.z
            delta = Vec3(
                dot_product * axis_dir.x,
                dot_product * axis_dir.y,
                dot_product * axis_dir.z
            )

            movement_speed = 0.5
            delta = delta * movement_speed
            self._apply_movement_delta(bone, delta)
            self._gizmo_drag_prev_point = current_point

        # Mark skeleton as needing update
        if model and model.skeleton:
            for b in model.skeleton:
                b._mark_dirty()

    def _get_world_delta_rotation(self, bone: Bone) -> Quat:
        """Get the world-space delta rotation from bind pose."""
        if bone.parent is not None:
            parent_world = bone.parent.get_world_transform()
            parent_world_rot = parent_world.rotation
        else:
            parent_world_rot = Quat.identity()

        bind_rot = bone.bind_transform.rotation
        pose_rot = bone.pose_transform.rotation

        current_world_rot = parent_world_rot * (pose_rot * bind_rot)
        bind_world_rot = parent_world_rot * bind_rot
        delta_rot = current_world_rot * bind_world_rot.inverse()

        return delta_rot

    def _apply_world_delta_rotation(self, bone: Bone, delta_rotation: Quat) -> None:
        """Apply a world-space delta rotation to a bone."""
        if bone.parent is not None:
            parent_world = bone.parent.get_world_transform()
            parent_world_rot = parent_world.rotation
        else:
            parent_world_rot = Quat.identity()

        bind_rot = bone.bind_transform.rotation
        bind_world_rot = parent_world_rot * bind_rot
        new_world_rot = delta_rotation * bind_world_rot
        pose_rotation = parent_world_rot.inverse() * new_world_rot * bind_rot.inverse()
        bone.pose_transform.rotation = pose_rotation

    def _apply_movement_delta(self, bone: Bone, delta: Vec3) -> None:
        """
        Apply a movement delta to a bone by rotating its parent.

        For root bones, translates the entire model instead.

        The approach:
        1. Calculate the world-space rotation that would move the bone
        2. Convert it to a delta that can be applied to the parent's pose rotation

        IMPORTANT: When rotating a parent bone, the child moves in an ARC around the parent.
        To constrain movement to a single axis, we need to calculate the rotation angle
        based on the arc length, not the straight-line distance.
        """
        parent = bone.parent

        if parent is None:
            # Root bone: translate the entire model
            # IMPORTANT: The delta is in world space, but we need to apply it in the bone's local space
            # The world transform is: world = bind * pose
            # So: pose_position = bind^-1 * world_delta
            
            # Get the bind rotation to convert world delta to local delta
            bind_rot = bone.bind_transform.rotation
            
            # Convert world-space delta to local space
            # local_delta = bind_rot^-1 * world_delta
            local_delta = bind_rot.inverse().rotate_vector(delta)
            
            bone.pose_transform.position = bone.pose_transform.position + local_delta
            bone._mark_dirty()
            return

        # Get current world position of the bone
        current_pos = bone.get_world_position()

        # Get parent world position (the pivot point for rotation)
        parent_pos = parent.get_world_position()

        # Vector from parent to bone (the "arm" that will rotate)
        arm_vector = current_pos - parent_pos
        arm_length = arm_vector.length()

        if arm_length < 0.001:
            return

        # The bone moves in an arc around the parent.
        # For small movements, arc_length ≈ arm_length * rotation_angle
        # So: rotation_angle = delta_magnitude / arm_length

        delta_length = delta.length()
        if delta_length < 1e-10:
            return

        # Calculate the rotation angle (in radians)
        rotation_angle = delta_length / arm_length

        # Determine the rotation axis:
        # The axis must be perpendicular to both the arm vector and the desired movement direction
        # This ensures the bone moves in the direction of delta when rotated

        # Normalize the arm vector
        arm_norm = arm_vector.normalized()

        # Normalize the delta (desired movement direction)
        delta_norm = delta.normalized()

        # The rotation axis is perpendicular to both arm and movement direction
        # cross(arm, delta) gives the axis of rotation
        rotation_axis = arm_norm.cross(delta_norm)
        rotation_axis_len = rotation_axis.length()

        if rotation_axis_len < 1e-10:
            # Arm and delta are parallel - can't rotate in that direction
            # This happens when trying to move directly toward/away from parent
            return

        rotation_axis = rotation_axis.normalized()

        # Determine the sign of the rotation
        # Check if the rotation direction is correct by verifying the cross product
        # If we rotate by +angle around rotation_axis, the bone should move in +delta direction
        # The cross product arm × rotation_axis gives the tangent direction
        tangent = arm_norm.cross(rotation_axis)

        # If tangent points opposite to delta direction, flip the rotation axis
        if tangent.dot(delta_norm) < 0:
            rotation_axis = rotation_axis * -1

        # Create the rotation quaternion
        world_rotation = Quat.from_axis_angle(rotation_axis, rotation_angle)

        # Get parent's world rotation (includes bind + pose)
        parent_world_rot = parent.get_world_rotation()

        # Get grandparent's world rotation (if exists)
        if parent.parent is not None:
            grandparent_world_rot = parent.parent.get_world_rotation()
        else:
            grandparent_world_rot = Quat.identity()

        parent_bind_rot = parent.bind_transform.rotation

        # Calculate new pose rotation
        # new_pose = grandparent_world^-1 * world_rotation * parent_world_rot * parent_bind^-1
        new_pose_rot = grandparent_world_rot.inverse() * world_rotation * parent_world_rot * parent_bind_rot.inverse()

        # Set the new pose rotation
        parent.pose_transform.rotation = new_pose_rot
        parent._mark_dirty()

    def _update_scale_gizmo_drag(self, mouse_pos, bone, model, gizmo_pos, gizmo_scale, view, proj, viewport) -> None:
        """Update model scale during scale gizmo drag."""
        if not self._scale_gizmo or not hasattr(self, '_scale_drag_start_scale'):
            return

        # Get current point on axis
        current_point = self._scale_gizmo.get_point_on_axis(
            (mouse_pos.x(), mouse_pos.y()),
            self._gizmo_drag_axis,
            gizmo_pos,
            gizmo_scale,
            view,
            proj,
            viewport
        )

        if current_point is None or self._gizmo_drag_start_point is None:
            return

        # Calculate new scale from drag
        # Note: get_scale_from_drag returns a Vec3 with the new scale values
        new_scale = self._scale_gizmo.get_scale_from_drag(
            self._gizmo_drag_start_point,
            current_point,
            self._gizmo_drag_axis,
            gizmo_pos,
            self._scale_drag_start_scale
        )

        # Apply scale to model transform
        model.transform.scale = new_scale

        # Mark skeleton as needing update
        if model and model.skeleton:
            for b in model.skeleton:
                b._mark_dirty()

        # Emit pose changed signal
        self.pose_changed.emit()
    
    def _end_gizmo_drag(self) -> None:
        """End gizmo dragging."""
        self._gizmo_state = "idle"
        self._gizmo_drag_axis = None
        self._gizmo_drag_start_point = None
        self._gizmo_drag_prev_point = None
        self._accumulated_rotation = None
        self._initial_delta_rotation = None
        self.pose_changed.emit()



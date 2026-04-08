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
from ..settings.settings import PluginSettings
from ..camera import CameraBookmarkManager, Camera


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
    sync_to_layer_requested = pyqtSignal() # Emitted when sync to layer shortcut is pressed

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

        # Camera bookmarks (1-9 slots)
        self._camera_bookmarks: Dict[int, dict] = {}

        # Global bookmark manager (initialized when settings are set)
        self._bookmark_manager: Optional[CameraBookmarkManager] = None

        # Head-look mode (False = orbit mode, True = head-look mode)
        self._head_look_mode: bool = False
    
        # Keyboard movement state (QWEASD)
        self._movement_keys_pressed: set = set()  # Track currently pressed movement keys
    
        # Settings
        self._settings: Optional[PluginSettings] = None

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
        self._rotation_start_angle: Optional[float] = None # Screen-space rotation angle
        self._rotation_slow_factor: float = 1.0 # Current slow factor (1.0 or 0.25)
        self._rotation_effective_start: Optional[float] = None # Effective start angle accounting for slow factor

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

    def set_settings(self, settings: PluginSettings) -> None:
        """
        Set or update the settings instance.

        Args:
            settings: PluginSettings instance to use
        """
        self._settings = settings
        self._apply_camera_settings()

        # Connect to settings changes to update camera dynamically
        settings.notifier.setting_changed.connect(self._on_setting_changed)

        # Initialize bookmark manager with settings directory
        from pathlib import Path
        settings_path = settings.get_settings_path()
        if settings_path:
            settings_dir = Path(settings_path).parent
            self._bookmark_manager = CameraBookmarkManager(settings_dir)

        self.update()

    def get_settings(self) -> Optional[PluginSettings]:
        """Get the current settings instance."""
        return self._settings

    def _apply_camera_settings(self) -> None:
        """Apply camera settings from PluginSettings."""
        if not self._settings:
            return

        cam_settings = self._settings.camera
        self._camera.fov = cam_settings.get('default_fov', 45.0)
        self._camera.distance = cam_settings.get('default_distance', 3.0)

    def _on_setting_changed(self, category: str, key: str, value) -> None:
        """Handle settings changes."""
        if category == 'camera' and key == 'default_fov':
            self._camera.fov = value
            self.update()

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

    def reload_scene(self) -> None:
        """Reload all models in the scene after a scene load.
        
        This clears existing GPU resources and reinitializes them
        for all models currently in the scene.
        """
        print(f"[Viewport] Reloading scene with {len(list(self._scene.get_all_models()))} models")
        
        # Clear existing GPU resources
        self._model_renderers.clear()
        self._model_skeleton_viz.clear()
        
        # Reinitialize GPU resources for all models
        if self._gl_initialized:
            self.makeCurrent()
            for model in self._scene.get_all_models():
                print(f"[Viewport] Initializing GL resources for model: {model.name}")
                self._init_model_gl_resources(model)
            self.doneCurrent()
        
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
        if model.mesh_data:
            # Check if mesh has multiple sub-meshes with materials
            if hasattr(model.mesh_data, 'sub_meshes') and model.mesh_data.sub_meshes:
                # Use new method for multi-submesh meshes with materials
                renderer.upload_mesh_with_materials(model.mesh_data)
            elif model.mesh_data.positions:
                # Legacy: single mesh without materials
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
                camera_pos = self._camera.get_position()
                renderer.render(model.skeleton, view, proj, model_matrix, camera_position=camera_pos)

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
                    print(f"[RENDER] - Rendering mesh for {model.name}")
                    renderer = self._model_renderers[model.id]
                    camera_pos = self._camera.get_position()
                    renderer.render(model.skeleton, view, proj, model_matrix, camera_position=camera_pos)
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
        """Timer update callback for animations."""
        import time

        # Initialize last_update_time on first call
        if not hasattr(self, '_last_update_time'):
            self._last_update_time = time.time()
            return

        # Calculate delta time
        current_time = time.time()
        delta_time = current_time - self._last_update_time
        self._last_update_time = current_time

        # Update camera animations (FOV transition, etc.)
        camera_animating = self._camera.update(delta_time)

        # Handle keyboard movement (QWEASD)
        if self._movement_keys_pressed:
            self._update_keyboard_movement(delta_time)

        # Request redraw if camera is animating or movement keys pressed
        if camera_animating or self._movement_keys_pressed:
            self.update()

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

        # Get rotation speed from settings
        rot_speed = self._settings.camera.get('rotation_speed', 0.01) if self._settings else 0.01

        if self._gizmo_state == "dragging":
            self._update_gizmo_drag(event.pos())
        elif self._mouse_button == Qt.LeftButton:
            modifiers = event.modifiers()
            if modifiers & Qt.ShiftModifier:
                # Shift+Left: Rotate camera
                self._camera.rotate(dx * rot_speed, dy * rot_speed)
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
                self._camera.rotate(dx * rot_speed, dy * rot_speed)

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
        modifiers = event.modifiers()

        # Handle camera movement keys (QWEASD) - these need continuous tracking
        movement_key = self._get_movement_key(key, modifiers)
        if movement_key:
            self._movement_keys_pressed.add(movement_key)
            event.accept()
            return

        if key == Qt.Key_F:
            self.frame_all()
        elif key == Qt.Key_T:
            self.set_show_mesh(not self._show_mesh)
        elif key == Qt.Key_S:
            if modifiers & Qt.ControlModifier and modifiers & Qt.ShiftModifier:
                # Ctrl+Shift+S = Sync to Layer
                self.sync_to_layer_requested.emit()
            else:
                self.set_show_skeleton(not self._show_skeleton)
        elif key == Qt.Key_G:
            self.toggle_gizmo_mode()
        elif key == Qt.Key_R:
            self._camera = Camera()
            self._frame_scene()
        
        # Camera bookmarks (1-9 for recall, Ctrl+1-9 for save)
        elif Qt.Key_1 <= key <= Qt.Key_9:
            index = key - Qt.Key_0  # Convert Key_1 to 1, Key_9 to 9
            if index >= 1 and index <= 9:
                if modifiers & Qt.ControlModifier:
                    self._save_bookmark(index)
                else:
                    self._recall_bookmark(index)

        self.update()

    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        """Handle key release for continuous movement."""
        key = event.key()
        modifiers = event.modifiers()

        # Check if this is a movement key being released
        movement_key = self._get_movement_key(key, modifiers)
        if movement_key and movement_key in self._movement_keys_pressed:
            self._movement_keys_pressed.discard(movement_key)
            event.accept()
            return

        super().keyReleaseEvent(event)

    def _get_movement_key(self, key: int, modifiers: int) -> Optional[str]:
        """Map key code to movement action name if it's a movement key."""
        # Movement keys don't use modifiers (Shift/Ctrl modify speed, not action)
        if key == Qt.Key_W:
            return 'forward'
        elif key == Qt.Key_S:
            return 'backward'
        elif key == Qt.Key_A:
            return 'left'
        elif key == Qt.Key_D:
            return 'right'
        elif key == Qt.Key_Q:
            return 'up'
        elif key == Qt.Key_E:
            return 'down'
        return None

    def _update_keyboard_movement(self, delta_time: float) -> None:
        """Update camera position based on pressed movement keys."""
        if not self._movement_keys_pressed:
            return
    
        # Get movement speed from settings
        if self._settings:
            base_speed = self._settings.camera.get('keyboard_movement_speed', 0.05)
            precision_factor = self._settings.camera.get('precision_factor', 0.25)
            fast_factor = self._settings.camera.get('fast_factor', 3.0)
        else:
            base_speed = 0.05
            precision_factor = 0.25
            fast_factor = 3.0
    
        # Determine speed modifier based on Shift/Ctrl keys
        # We check keyboard modifiers directly since user might be holding multiple
        speed = base_speed
        from PyQt5.QtGui import QGuiApplication
        modifiers = QGuiApplication.keyboardModifiers()
        if modifiers & Qt.ShiftModifier:
            speed *= precision_factor
        elif modifiers & Qt.ControlModifier:
            speed *= fast_factor
    
        # Calculate movement delta based on pressed keys
        # In head-look mode, movement is relative to the look direction
        # In orbit mode, movement is applied to the orbit target
        if self._camera.head_look_mode:
            # Head-look mode: move the camera position relative to look direction
            forward = self._camera._get_head_forward()
            right = self._camera._get_head_right()
            up = self._camera._get_head_up()
            
            delta = Vec3(0, 0, 0)
            
            # QWEASD movement relative to camera orientation
            if 'forward' in self._movement_keys_pressed:
                delta = delta + forward * speed
            if 'backward' in self._movement_keys_pressed:
                delta = delta - forward * speed
            if 'left' in self._movement_keys_pressed:
                delta = delta - right * speed
            if 'right' in self._movement_keys_pressed:
                delta = delta + right * speed
            if 'up' in self._movement_keys_pressed:
                delta = delta + up * speed
            if 'down' in self._movement_keys_pressed:
                delta = delta - up * speed
            
            # Apply movement to head position
            if delta.x != 0 or delta.y != 0 or delta.z != 0:
                self._camera._head_position = self._camera._head_position + delta
        else:
            # Orbit mode: move the target point
            forward = (self._camera.target - self._camera.get_position()).normalized()
            right = Vec3(0, 1, 0).cross(forward).normalized()
            up = Vec3(0, 1, 0)  # World up
    
            delta = Vec3(0, 0, 0)
    
            # QWEASD movement
            if 'forward' in self._movement_keys_pressed:
                delta = delta + forward * speed
            if 'backward' in self._movement_keys_pressed:
                delta = delta - forward * speed
            if 'left' in self._movement_keys_pressed:
                delta = delta - right * speed
            if 'right' in self._movement_keys_pressed:
                delta = delta + right * speed
            if 'up' in self._movement_keys_pressed:
                delta = delta + up * speed
            if 'down' in self._movement_keys_pressed:
                delta = delta - up * speed
    
            # Apply movement to camera target
            if delta.x != 0 or delta.y != 0 or delta.z != 0:
                self._camera.move_target(delta)

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

                # Calculate the initial screen-space angle
                start_angle = self._gizmo.get_screen_space_rotation_angle(
                    (mouse_pos.x(), mouse_pos.y()),
                    self._gizmo_hover_axis,
                    gizmo_pos,
                    view,
                    proj,
                    viewport
                )
                if start_angle is None:
                    return False

            self._gizmo_state = "dragging"
            self._gizmo_drag_axis = self._gizmo_hover_axis
            self._gizmo_drag_start_point = start_point
            self._gizmo_drag_prev_point = start_point
            self._accumulated_rotation = Quat.identity()
            self._rotation_start_angle = start_angle # Store initial screen-space angle
            self._rotation_slow_factor = 1.0 # Reset slow factor
            self._rotation_effective_start = start_angle # Effective start for slow mode
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
        elif self._gizmo_mode == "scale" & self._scale_gizmo:
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
        """Update bone rotation during rotation gizmo drag using screen-space angles."""
        import math
        
        if self._initial_delta_rotation is None or not self._gizmo:
            return

        if self._rotation_start_angle is None:
            return

        # Calculate the current screen-space angle
        current_angle = self._gizmo.get_screen_space_rotation_angle(
            (mouse_pos.x(), mouse_pos.y()),
            self._gizmo_drag_axis,
            gizmo_pos,
            view,
            proj,
            viewport
        )

        if current_angle is None:
            return

        # Initialize prev_angle if needed
        if not hasattr(self, '_rotation_prev_angle') or self._rotation_prev_angle is None:
            self._rotation_prev_angle = current_angle
        
        # Detect angle wrap-around and adjust effective_start to compensate
        # This happens when current_angle jumps from ~π to ~-π or vice versa
        angle_jump = current_angle - self._rotation_prev_angle
        if abs(angle_jump) > math.pi:
            # Angle wrapped around - adjust effective_start by 2π in the opposite direction
            # This keeps the relative angle difference consistent
            if angle_jump > 0:
                # Jumped from negative to positive (e.g., -179° to 179°), subtract 2π from effective_start
                self._rotation_effective_start -= 2 * math.pi
            else:
                # Jumped from positive to negative (e.g., 179° to -179°), add 2π to effective_start
                self._rotation_effective_start += 2 * math.pi
        
        self._rotation_prev_angle = current_angle

        # Check if shift is held for slow/precision rotation
        from PyQt5.QtCore import Qt
        from PyQt5.QtWidgets import QApplication
        modifiers = QApplication.keyboardModifiers()
        new_slow_factor = 0.25 if (modifiers & Qt.ShiftModifier) else 1.0

        # If slow factor changed, update the effective start angle to prevent snapping
        if new_slow_factor != self._rotation_slow_factor:
            if self._rotation_effective_start is not None:
                # Calculate the raw angle difference (before slow factor)
                raw_angle_diff = current_angle - self._rotation_effective_start
                
                # Normalize to [-π, π]
                while raw_angle_diff > math.pi:
                    raw_angle_diff -= 2 * math.pi
                while raw_angle_diff < -math.pi:
                    raw_angle_diff += 2 * math.pi
                
                # The visual rotation the user sees is: raw_angle_diff * old_slow_factor
                # We want: new_raw_angle_diff * new_slow_factor = visual_rotation
                # So: new_raw_angle_diff = visual_rotation / new_slow_factor
                # And: new_effective_start = current_angle - new_raw_angle_diff
                visual_rotation = raw_angle_diff * self._rotation_slow_factor
                new_raw_angle_diff = visual_rotation / new_slow_factor
                self._rotation_effective_start = current_angle - new_raw_angle_diff
            else:
                self._rotation_effective_start = current_angle
            self._rotation_slow_factor = new_slow_factor

        # DEBUG: Print angle values
        # print(f"[ROT DEBUG] current_angle={math.degrees(current_angle):.1f}°, effective_start={math.degrees(self._rotation_effective_start):.1f}°, slow_factor={self._rotation_slow_factor}")

        # Calculate rotation from the effective start angle
        # This gives smooth, predictable rotation with slow factor support
        total_rotation = self._gizmo.get_rotation_from_screen_angle(
            self._rotation_effective_start,
            current_angle,
            self._gizmo_drag_axis,
            self._rotation_slow_factor
        )

        # Apply the total rotation to the initial world-space delta
        new_delta_rotation = total_rotation * self._initial_delta_rotation

        # Apply the world-space delta rotation to the bone
        self._apply_world_delta_rotation(bone, new_delta_rotation)

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
    
        # The tangent direction is arm × rotation_axis
        # For correct rotation: rotation_axis × arm should point in delta direction
        # Since rotation_axis × arm = -(arm × rotation_axis) = -tangent
        # We need -tangent to align with delta, so tangent should be opposite to delta
        # If tangent.dot(delta_norm) > 0, tangent points same as delta, which is wrong
        if tangent.dot(delta_norm) > 0:
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
        self._rotation_start_angle = None
        self._rotation_slow_factor = 1.0  # Reset slow factor
        self._rotation_effective_start = None  # Reset effective start
        if hasattr(self, '_rotation_prev_angle'):
            self._rotation_prev_angle = None  # Reset previous angle for wrap detection
        self.pose_changed.emit()

    # -------------------------------------------------------------------------
    # Public Camera Control Methods
    # -------------------------------------------------------------------------

    def reset_camera(self) -> None:
        """Reset camera to default position.

        Public method for UI controls.
        """
        self._camera = Camera()
        self._apply_camera_settings()
        self._frame_scene()

    def frame_model(self) -> None:
        """Frame all models in the viewport.

        Public method for UI controls.
        """
        self._frame_scene()

    def set_fov(self, fov: float) -> None:
        """Set the camera field of view.

        Args:
            fov: Field of view in degrees (typically 30-120)
        """
        self._camera.fov = max(30.0, min(120.0, fov))
        self.update()

    # -------------------------------------------------------------------------
    # Camera Bookmarks
    # -------------------------------------------------------------------------

    def _save_bookmark(self, index: int) -> None:
        """
        Save current camera state to a bookmark slot.

        Args:
            index: Bookmark index (1-9)
        """
        if not 1 <= index <= 9:
            return

        # Use global bookmark manager if available
        if self._bookmark_manager:
            self._bookmark_manager.save_bookmark(index, self._camera)
        else:
            # Fallback to local storage
            bookmark = {
                'target': (self._camera.target.x, self._camera.target.y, self._camera.target.z),
                'distance': self._camera.distance,
                'yaw': self._camera.yaw,
                'pitch': self._camera.pitch,
                'fov': self._camera.fov,
            }
            self._camera_bookmarks[index] = bookmark

    def _recall_bookmark(self, index: int) -> None:
        """
        Recall camera state from a bookmark slot.

        Args:
            index: Bookmark index (1-9)
        """
        if not 1 <= index <= 9:
            return

        # Use global bookmark manager if available
        if self._bookmark_manager:
            if self._bookmark_manager.load_bookmark(index, self._camera):
                self.update()
            return

        # Fallback to local storage
        bookmark = self._camera_bookmarks.get(index)
        if bookmark is None:
            return

        # Apply camera state
        target = bookmark.get('target', (0, 1, 0))
        self._camera.target = Vec3(target[0], target[1], target[2])
        self._camera.distance = bookmark.get('distance', 3.0)
        self._camera.yaw = bookmark.get('yaw', 0.0)
        self._camera.pitch = bookmark.get('pitch', 0.0)
        self._camera.fov = bookmark.get('fov', 45.0)

        # Trigger redraw
        self.update()

    def get_bookmark_manager(self) -> Optional[CameraBookmarkManager]:
        """Get the bookmark manager instance."""
        return self._bookmark_manager

    def has_bookmark(self, index: int) -> bool:
        """Check if a bookmark exists at the given slot."""
        if self._bookmark_manager:
            return self._bookmark_manager.has_bookmark(index)
        return index in self._camera_bookmarks

    def get_bookmark_info(self, index: int) -> Optional[str]:
        """Get bookmark info string for UI display."""
        if self._bookmark_manager:
            bookmark = self._bookmark_manager.get_bookmark(index)
            if bookmark:
                return bookmark.get_summary()
        return None

    def load_project_bookmarks(self, bookmarks: dict) -> None:
        """
        Load project-specific camera bookmarks.

        This loads bookmarks from a saved scene file into the viewport's
        local bookmark storage. These are separate from global bookmarks.

        Args:
            bookmarks: Dictionary of bookmark slot -> bookmark data
        """
        print(f"[Viewport] Loading {len(bookmarks)} project bookmarks")
        for slot_str, bookmark_data in bookmarks.items():
            try:
                slot = int(slot_str)
                if 1 <= slot <= 9:
                    self._camera_bookmarks[slot] = bookmark_data
                    print(f"[Viewport] Loaded bookmark {slot}")
            except (ValueError, KeyError) as e:
                print(f"[Viewport] Error loading bookmark {slot_str}: {e}")
        self.update()

    def get_project_bookmarks(self) -> dict:
        """
        Get project-specific camera bookmarks for saving.

        Returns:
            Dictionary of bookmark slot -> bookmark data
        """
        # Convert int keys to strings for JSON serialization
        return {str(slot): data for slot, data in self._camera_bookmarks.items()}

    # -------------------------------------------------------------------------
    # Camera Panel Support
    # -------------------------------------------------------------------------

    def set_head_look_mode(self, enabled: bool) -> None:
        """Set head-look mode.

        Args:
            enabled: True for head-look mode, False for orbit mode
        """
        self._head_look_mode = enabled
        self._camera.head_look_mode = enabled
        self.update()

    def get_head_look_mode(self) -> bool:
        """Get current head-look mode state."""
        return self._head_look_mode

    def frame_model(self) -> None:
        """Frame all models in the viewport."""
        scene = self.get_scene()
        models = scene.get_all_models()
        if not models:
            return

        # Calculate bounding box of all models
        min_bounds = Vec3(float('inf'), float('inf'), float('inf'))
        max_bounds = Vec3(float('-inf'), float('-inf'), float('-inf'))

        for model in models:
            if model.skeleton:
                for bone in model.skeleton.get_all_bones():
                    pos = bone.get_world_position()
                    min_bounds = Vec3(min(min_bounds.x, pos.x), min(min_bounds.y, pos.y), min(min_bounds.z, pos.z))
                    max_bounds = Vec3(max(max_bounds.x, pos.x), max(max_bounds.y, pos.y), max(max_bounds.z, pos.z))

        # Calculate center and size
        center = Vec3(
            (min_bounds.x + max_bounds.x) / 2,
            (min_bounds.y + max_bounds.y) / 2,
            (min_bounds.z + max_bounds.z) / 2
        )
        size = max(max_bounds.x - min_bounds.x, max(max_bounds.y - min_bounds.y), max_bounds.z - min_bounds.z)

        # Set camera to frame the scene
        self._camera.target = center
        self._camera.distance = max(3.0, size * 2.0)
        self.update()

    def reset_camera(self) -> None:
        """Reset camera to default position."""
        self._camera.target = Vec3(0, 1, 0)
        self._camera.yaw = 0.0
        self._camera.pitch = 0.0
        self._camera.distance = 3.0
        self._camera.fov = 45.0
        self.update()


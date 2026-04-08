"""
Viewport3D - Qt OpenGL Widget for 3D Rendering
=============================================

Provides a Qt widget that renders the 3D scene using OpenGL.
Supports camera controls, bone selection, and both rotation and movement gizmos.
"""

import math
from typing import Optional

from PyQt5.QtWidgets import QOpenGLWidget, QWidget, QFileDialog, QMessageBox
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QMouseEvent, QKeyEvent, QWheelEvent, QImage, QOpenGLFramebufferObject, QOpenGLFramebufferObjectFormat
from OpenGL.GL import (
    glClearColor, glEnable, glBlendFunc,
    GL_DEPTH_TEST, GL_BLEND, GL_SRC_ALPHA,
    GL_ONE_MINUS_SRC_ALPHA, glViewport, glClear,
    GL_COLOR_BUFFER_BIT, GL_DEPTH_BUFFER_BIT, glReadPixels,
    GL_RGBA, GL_UNSIGNED_BYTE, glBindFramebuffer, GL_FRAMEBUFFER
)

from ..vec3 import Vec3
from ..quat import Quat
from ..mat4 import Mat4
from ..skeleton import Skeleton
from ..bone import Bone
from ..gltf.builder import MeshData
from ..renderer.gl_renderer import GLRenderer
from ..renderer.skeleton_viz import SkeletonVisualizer
from ..renderer.gizmo import RotationGizmo, MovementGizmo, ScaleGizmo
from ..renderer.joint_renderer import JointRenderer
from ..pose_state import UndoRedoStack, PoseSerializer, PoseSnapshot


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
        self.distance = max(0.5, min(20.0, self.distance * (1.0 - delta)))

    def move_forward(self, delta: float) -> None:
        """Move the camera forward/backward (dolly) toward/away from target."""
        self.distance = max(0.5, min(20.0, self.distance - delta))

    def pan(self, delta_x: float, delta_y: float) -> None:
        """Pan the camera target."""
        # Get camera right and up vectors
        forward = (self.target - self.get_position()).normalized()
        right = Vec3(0, 1, 0).cross(forward).normalized()
        up = forward.cross(right).normalized()

        scale = self.distance * 0.001
        self.target = self.target + right * (-delta_x * scale) + up * (delta_y * scale)


class Viewport3D(QOpenGLWidget):
    """
    OpenGL widget for 3D model viewing and posing.

    Features:
    - Orbit camera (rotate, zoom, pan)
    - Skeleton visualization
    - Mesh rendering with skinning
    - Bone selection
    - Rotation gizmo for intuitive bone rotation
    - Undo/redo support (Ctrl+Z / Ctrl+Y)
    - Pose save/load (Ctrl+S / Ctrl+O)

    Signals:
    bone_selected: Emitted when a bone is selected (bone_name)
    bone_rotation_changed: Emitted when bone rotation changes via gizmo (bone_name, rotation_quat)
    pose_changed: Emitted when the pose changes (for undo/redo state updates)
    undo_redo_changed: Emitted when undo/redo availability changes (can_undo, can_redo)
    """

    bone_selected = pyqtSignal(str) # bone_name
    bone_rotation_changed = pyqtSignal(str, object) # bone_name, Quat
    pose_changed = pyqtSignal() # Emitted after pose modifications
    undo_redo_changed = pyqtSignal(bool, bool) # can_undo, can_redo

    def __init__(self, parent: Optional[QWidget] = None):
        """Create a new 3D viewport."""
        super().__init__(parent)

        self._skeleton: Optional[Skeleton] = None
        self._mesh_data: Optional[MeshData] = None
        self._renderer: Optional[GLRenderer] = None
        self._skeleton_viz: Optional[SkeletonVisualizer] = None
        self._gizmo: Optional[RotationGizmo] = None
        self._movement_gizmo: Optional[MovementGizmo] = None
        self._scale_gizmo: Optional[ScaleGizmo] = None
        self._joint_renderer: Optional[JointRenderer] = None

        # Gizmo mode: "rotation", "movement", or "scale"
        self._gizmo_mode: str = "rotation"

        self._camera = Camera()
        self._selected_bone: str = ""

        # Mouse state
        self._last_mouse_pos = None
        self._mouse_button = None

        # Render mode
        self._show_mesh = True
        self._show_skeleton = True
        self._show_joints = True # Show joint spheres for selection
        self._show_gizmo = True # Show gizmo for selected bone (rotation or movement depending on mode)

        # Joint hover state
        self._hovered_joint: Optional[str] = None

        # Dirty flags for deferred upload
        self._mesh_dirty = False
        self._skeleton_dirty = False
        self._gl_initialized = False

        # Gizmo interaction state (for both rotation and movement)
        self._gizmo_state: str = "idle" # "idle", "hover", "dragging"
        self._gizmo_hover_axis: Optional[str] = None # "X", "Y", "Z", or None
        self._gizmo_drag_axis: Optional[str] = None
        self._gizmo_drag_start_point: Optional[Vec3] = None
        self._gizmo_drag_prev_point: Optional[Vec3] = None # Previous frame's point for incremental rotation
        self._accumulated_rotation: Optional[Quat] = None # Accumulated rotation during drag (rotation mode)
        self._initial_bone_rotation: Optional[Quat] = None
        self._initial_delta_rotation: Optional[Quat] = None # World-space delta from bind pose (rotation mode)
        
        # Movement gizmo specific state
        self._movement_drag_start_pos: Optional[Vec3] = None # Initial bone position when drag starts
        self._movement_drag_prev_pos: Optional[Vec3] = None # Previous frame's bone position

        # Undo/redo system
        self._undo_redo_stack = UndoRedoStack(max_history=50)
        self._is_dragging_gizmo = False  # Track if we're in a drag operation

        # Set focus policy for keyboard input
        self.setFocusPolicy(Qt.StrongFocus)

        # Update timer
        self._update_timer = QTimer(self)
        self._update_timer.timeout.connect(self._on_update)
        self._update_timer.start(16) # ~60 FPS

    def set_skeleton(self, skeleton: Skeleton) -> None:
        """Set the skeleton to display."""
        self._skeleton = skeleton
        self._skeleton_dirty = True
        if self._gl_initialized:
            # Ensure OpenGL context is current before updating
            self.makeCurrent()
            self._update_skeleton_viz()
            self._skeleton_dirty = False
            self.doneCurrent()
            self.update()
        # Initialize undo/redo stack with the new skeleton
        if skeleton:
            self._undo_redo_stack.initialize(skeleton)
            self._emit_undo_redo_state()

    def set_mesh(self, mesh_data: MeshData) -> None:
        """Set the mesh to display."""
        self._mesh_data = mesh_data
        self._mesh_dirty = True
        if self._gl_initialized:
            # Ensure OpenGL context is current before uploading
            self.makeCurrent()
            self._upload_mesh()
            self._mesh_dirty = False
            self.doneCurrent()
        self.update()

    def set_selected_bone(self, bone_name: str) -> None:
        """Set the selected bone."""
        self._selected_bone = bone_name
        self.update()

    def get_selected_bone(self) -> str:
        """Get the selected bone name."""
        return self._selected_bone

    def set_show_mesh(self, show: bool) -> None:
        """Set whether to show the mesh."""
        self._show_mesh = show
        self.update()

    def set_show_skeleton(self, show: bool) -> None:
        """Set whether to show the skeleton."""
        self._show_skeleton = show
        self.update()

    def set_show_joints(self, show: bool) -> None:
        """Set whether to show the joint spheres."""
        self._show_joints = show
        self.update()

    def set_show_gizmo(self, show: bool) -> None:
        """Set whether to show the gizmo."""
        self._show_gizmo = show
        self.update()
    
    def set_gizmo_mode(self, mode: str) -> None:
        """
        Set the gizmo mode.

        Args:
            mode: "rotation", "movement", or "scale"
        """
        if mode in ("rotation", "movement", "scale"):
            self._gizmo_mode = mode
            self.update()

    def get_gizmo_mode(self) -> str:
        """Get the current gizmo mode."""
        return self._gizmo_mode

    def toggle_gizmo_mode(self) -> None:
        """Cycle through gizmo modes: rotation -> movement -> scale -> rotation."""
        if self._gizmo_mode == "rotation":
            self._gizmo_mode = "movement"
        elif self._gizmo_mode == "movement":
            self._gizmo_mode = "scale"
        else:
            self._gizmo_mode = "rotation"
        self.update()

    def get_selected_bone_object(self) -> Optional[Bone]:
        """Get the currently selected bone object, or None."""
        if not self._skeleton or not self._selected_bone:
            return None
        return self._skeleton.get_bone(self._selected_bone)

    def get_gizmo_position(self) -> Optional[Vec3]:
        """Get the world position where the gizmo should be rendered."""
        bone = self.get_selected_bone_object()
        if bone:
            return bone.get_world_position()
        return None

    def get_gizmo_scale(self) -> float:
        """Calculate appropriate gizmo scale based on camera distance."""
        gizmo_pos = self.get_gizmo_position()
        if gizmo_pos is None:
            return 0.1

        cam_pos = self._camera.get_position()
        distance = (cam_pos - gizmo_pos).length()
        return distance * 0.15  # Adjust multiplier for desired size

    # -------------------------------------------------------------------------
    # OpenGL Implementation
    # -------------------------------------------------------------------------

    def initializeGL(self) -> None:
        """Initialize OpenGL resources."""
        glClearColor(0.2, 0.2, 0.2, 1.0)
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        # Create renderers
        self._renderer = GLRenderer()
        if not self._renderer.initialize():
            print("Failed to initialize GLRenderer")

        self._skeleton_viz = SkeletonVisualizer()
        if not self._skeleton_viz.initialize():
            print("Failed to initialize SkeletonVisualizer")

        # Create rotation gizmo
        self._gizmo = RotationGizmo()
        if not self._gizmo.initialize():
            print("Failed to initialize RotationGizmo")
        
        # Create movement gizmo
        self._movement_gizmo = MovementGizmo()
        if not self._movement_gizmo.initialize():
            print("Failed to initialize MovementGizmo")

        # Create scale gizmo
        self._scale_gizmo = ScaleGizmo()
        if not self._scale_gizmo.initialize():
            print("Failed to initialize ScaleGizmo")

        # Create joint renderer
        self._joint_renderer = JointRenderer()
        if not self._joint_renderer.initialize():
            print("Failed to initialize JointRenderer")

        # Mark OpenGL as initialized
        self._gl_initialized = True

        # Upload mesh if we have one and it's dirty
        if self._mesh_dirty and self._mesh_data:
            self._upload_mesh()
            self._mesh_dirty = False

        # Update skeleton viz if we have one and it's dirty
        if self._skeleton_dirty and self._skeleton:
            self._update_skeleton_viz()
            self._skeleton_dirty = False

    def resizeGL(self, w: int, h: int) -> None:
        """Handle resize."""
        glViewport(0, 0, w, h)

    def paintGL(self) -> None:
        """Render the scene."""
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        aspect = self.width() / max(1, self.height())
        view = self._camera.get_view_matrix()
        proj = self._camera.get_projection_matrix(aspect)

        # Render mesh
        if self._show_mesh and self._renderer and self._mesh_data:
            self._renderer.render(self._skeleton, view, proj)

        # Render skeleton
        if self._show_skeleton and self._skeleton_viz and self._skeleton:
            self._skeleton_viz.update_skeleton(self._skeleton)
            self._skeleton_viz.render(view, proj)

        # Render joints (spheres at bone positions for selection)
        if self._show_joints and self._joint_renderer and self._skeleton:
            joint_scale = self._camera.distance * 0.2  # Scale joints with camera distance
            self._joint_renderer.render(
                self._skeleton, view, proj,
                selected_bone=self._selected_bone,
                hovered_bone=self._hovered_joint,
                scale=joint_scale
            )

        # Render gizmo for selected bone
        if self._show_gizmo and self._selected_bone:
            gizmo_pos = self.get_gizmo_position()
            if gizmo_pos:
                gizmo_scale = self.get_gizmo_scale()
                
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
        if not self._gl_initialized:
            return QImage()
            
        # Ensure we have a valid context
        if not self.context():
            return QImage()
            
        # Create framebuffer object for offscreen rendering
        try:
            fbo_format = QOpenGLFramebufferObjectFormat()
            fbo_format.setSamples(4)  # Anti-aliasing
            fbo_format.setAttachment(QOpenGLFramebufferObject.CombinedDepthStencil)
            
            fbo = QOpenGLFramebufferObject(width, height, fbo_format)
            if not fbo.isValid():
                return QImage()
                
            # Bind framebuffer and set viewport
            fbo.bind()
            glViewport(0, 0, width, height)
            
            # Clear buffers
            glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
            
            # Calculate matrices for the target resolution
            aspect = width / max(1, height)
            view = self._camera.get_view_matrix()  
            proj = self._camera.get_projection_matrix(aspect)
            
            # Render mesh
            if self._show_mesh and self._renderer and self._mesh_data:
                self._renderer.render(self._skeleton, view, proj)

            # Render skeleton
            if self._show_skeleton and self._skeleton_viz and self._skeleton:
                self._skeleton_viz.update_skeleton(self._skeleton)
                self._skeleton_viz.render(view, proj)

            # Render joints
            if self._show_joints and self._joint_renderer and self._skeleton:
                joint_scale = self._camera.distance * 0.2
                self._joint_renderer.render(
                    self._skeleton, view, proj,
                    selected_bone=self._selected_bone,
                    hovered_bone=self._hovered_joint,
                    scale=joint_scale
                )

            # Render gizmo for selected bone
            if self._show_gizmo and self._selected_bone:
                gizmo_pos = self.get_gizmo_position()
                if gizmo_pos:
                    gizmo_scale = self.get_gizmo_scale()
                    
                    if self._gizmo_mode == "rotation" and self._gizmo:
                        self._gizmo.render(
                            gizmo_pos, gizmo_scale, view, proj,
                            hovered_axis=self._gizmo_hover_axis if self._gizmo_state != "dragging" else None,
                            dragging_axis=self._gizmo_drag_axis if self._gizmo_state == "dragging" else None
                        )
                    elif self._gizmo_mode == "movement" and self._movement_gizmo:
                        self._movement_gizmo.render(
                            gizmo_pos, gizmo_scale, view, proj,
                            hovered_axis=self._gizmo_hover_axis if self._gizmo_state != "dragging" else None,
                            dragging_axis=self._gizmo_drag_axis if self._gizmo_state == "dragging" else None
                        )
                    elif self._gizmo_mode == "scale" and self._scale_gizmo:
                        self._scale_gizmo.render(
                            gizmo_pos, gizmo_scale, view, proj,
                            hovered_axis=self._gizmo_hover_axis if self._gizmo_state != "dragging" else None,
                            dragging_axis=self._gizmo_drag_axis if self._gizmo_state == "dragging" else None
                        )
            
            # Get the rendered image
            image = fbo.toImage()
            fbo.release()
            
            # Restore original viewport
            glViewport(0, 0, self.width(), self.height())
            
            return image
            
        except Exception:
            # Restore viewport on error
            try:
                glViewport(0, 0, self.width(), self.height())
            except Exception:
                pass  # Best effort cleanup
            return QImage()

    def _upload_mesh(self) -> None:
        """Upload mesh data to GPU."""
        if self._renderer and self._mesh_data and self._mesh_data.positions:
            self._renderer.upload_mesh(
                self._mesh_data.positions,
                self._mesh_data.normals,
                self._mesh_data.indices,
                self._mesh_data.skinning_data
            )

    def _update_skeleton_viz(self) -> None:
        """Update skeleton visualization."""
        if self._skeleton_viz and self._skeleton:
            self._skeleton_viz.update_skeleton(self._skeleton)

    # -------------------------------------------------------------------------
    # Gizmo Interaction
    # -------------------------------------------------------------------------

    def _update_gizmo_hover(self, mouse_pos) -> None:
        """Update gizmo hover state based on mouse position."""
        if not self._selected_bone:
            self._gizmo_hover_axis = None
            return

        gizmo_pos = self.get_gizmo_position()
        if gizmo_pos is None:
            self._gizmo_hover_axis = None
            return

        gizmo_scale = self.get_gizmo_scale()
        aspect = self.width() / max(1, self.height())
        view = self._camera.get_view_matrix()
        proj = self._camera.get_projection_matrix(aspect)
        viewport = (0, 0, self.width(), self.height())

        # Use the appropriate gizmo based on mode
        if self._gizmo_mode == "rotation" and self._gizmo:
            hit_axis = self._gizmo.hit_test(
                (mouse_pos.x(), mouse_pos.y()),
                gizmo_pos,
                gizmo_scale,
                view,
                proj,
                viewport
            )
        elif self._gizmo_mode == "movement" and self._movement_gizmo:
            hit_axis = self._movement_gizmo.hit_test(
                (mouse_pos.x(), mouse_pos.y()),
                gizmo_pos,
                gizmo_scale,
                view,
                proj,
                viewport
            )
        elif self._gizmo_mode == "scale" and self._scale_gizmo:
            hit_axis = self._scale_gizmo.hit_test(
                (mouse_pos.x(), mouse_pos.y()),
                gizmo_pos,
                gizmo_scale,
                view,
                proj,
                viewport
            )
        else:
            hit_axis = None

        self._gizmo_hover_axis = hit_axis

    def _start_gizmo_drag(self, mouse_pos) -> bool:
        """Start dragging the gizmo. Returns True if drag started."""
        if not self._selected_bone or self._gizmo_hover_axis is None:
            return False

        bone = self.get_selected_bone_object()
        if bone is None:
            return False

        gizmo_pos = self.get_gizmo_position()
        if gizmo_pos is None:
            return False

        gizmo_scale = self.get_gizmo_scale()
        aspect = self.width() / max(1, self.height())
        view = self._camera.get_view_matrix()
        proj = self._camera.get_projection_matrix(aspect)
        viewport = (0, 0, self.width(), self.height())

        if self._gizmo_mode == "rotation":
            return self._start_rotation_gizmo_drag(mouse_pos, bone, gizmo_pos, gizmo_scale, view, proj, viewport)
        elif self._gizmo_mode == "movement":
            return self._start_movement_gizmo_drag(mouse_pos, bone, gizmo_pos, gizmo_scale, view, proj, viewport)
        else:  # scale
            return self._start_scale_gizmo_drag(mouse_pos, bone, gizmo_pos, gizmo_scale, view, proj, viewport)

    def _start_rotation_gizmo_drag(self, mouse_pos, bone, gizmo_pos, gizmo_scale, view, proj, viewport) -> bool:
        """Start dragging the rotation gizmo."""
        if not self._gizmo:
            return False

        # Get the starting point on the circle plane
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

        # Push current state to undo stack BEFORE making changes
        if self._skeleton:
            self._undo_redo_stack.push_state(self._skeleton, f"Rotate {self._selected_bone}")
            self._emit_undo_redo_state()

        # Store drag state
        self._gizmo_state = "dragging"
        self._is_dragging_gizmo = True
        self._gizmo_drag_axis = self._gizmo_hover_axis
        self._gizmo_drag_start_point = start_point
        self._gizmo_drag_prev_point = start_point
        self._accumulated_rotation = Quat.identity()

        # Store the initial world-space delta rotation (rotation from bind pose)
        self._initial_bone_rotation = bone.pose_transform.rotation
        self._initial_delta_rotation = self._get_world_delta_rotation(bone)

        return True

    def _start_movement_gizmo_drag(self, mouse_pos, bone, gizmo_pos, gizmo_scale, view, proj, viewport) -> bool:
        """Start dragging the movement gizmo."""
        if not self._movement_gizmo:
            return False

        # Check if we're dragging the center (free movement) or an axis
        if self._gizmo_hover_axis == 'CENTER':
            # Get the starting point on the camera-facing plane
            start_point = self._movement_gizmo.get_point_on_plane(
                (mouse_pos.x(), mouse_pos.y()),
                gizmo_pos,
                view,
                proj,
                viewport
            )
        else:
            # Get the starting point on the axis
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

        # Push current state to undo stack BEFORE making changes
        action_name = f"Move {self._selected_bone}"
        if self._skeleton:
            self._undo_redo_stack.push_state(self._skeleton, action_name)
            self._emit_undo_redo_state()

        # Store drag state
        self._gizmo_state = "dragging"
        self._is_dragging_gizmo = True
        self._gizmo_drag_axis = self._gizmo_hover_axis
        self._gizmo_drag_start_point = start_point
        self._gizmo_drag_prev_point = start_point

        # Store initial bone position for movement
        self._movement_drag_start_pos = bone.get_world_position()
        self._movement_drag_prev_pos = self._movement_drag_start_pos

        return True

    def _start_scale_gizmo_drag(self, mouse_pos, bone, gizmo_pos, gizmo_scale, view, proj, viewport) -> bool:
        """Start dragging the scale gizmo."""
        if not self._scale_gizmo:
            return False

        # Get the starting point on the axis or plane
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

        # Push current state to undo stack BEFORE making changes
        action_name = f"Scale {self._selected_bone}"
        if self._skeleton:
            self._undo_redo_stack.push_state(self._skeleton, action_name)
            self._emit_undo_redo_state()

        # Store drag state
        self._gizmo_state = "dragging"
        self._is_dragging_gizmo = True
        self._gizmo_drag_axis = self._gizmo_hover_axis
        self._gizmo_drag_start_point = start_point
        self._gizmo_drag_prev_point = start_point

        # Store initial scale (we'll use the bone's bind scale as reference)
        # For now, we assume uniform scale of 1.0 as initial
        self._initial_scale = Vec3(1.0, 1.0, 1.0)

        return True

    def _get_world_delta_rotation(self, bone: Bone) -> Quat:
        """
        Get the world-space delta rotation from bind pose.
        
        This matches the logic in the sidebar controls - the rotation
        represents how much the bone has been rotated FROM its bind pose
        in world space.
        """
        # Get parent's world rotation (or identity if no parent)
        if bone.parent is not None:
            parent_world = bone.parent.get_world_transform()
            parent_world_rot = parent_world.rotation
        else:
            parent_world_rot = Quat.identity()
        
        bind_rot = bone.bind_transform.rotation
        pose_rot = bone.pose_transform.rotation
        
        # Current world rotation: parent_world * (pose * bind)
        current_world_rot = parent_world_rot * (pose_rot * bind_rot)
        
        # Bind pose world rotation: parent_world * bind
        bind_world_rot = parent_world_rot * bind_rot
        
        # Delta from bind pose: current_world * bind_world^-1
        delta_rot = current_world_rot * bind_world_rot.inverse()
        
        return delta_rot

    def _apply_world_delta_rotation(self, bone: Bone, delta_rotation: Quat) -> None:
        """
        Apply a world-space delta rotation to a bone.
        
        This matches the logic in the sidebar controls - applies the
        delta rotation to transform from bind pose.
        """
        # Get parent's world rotation (or identity if no parent)
        if bone.parent is not None:
            parent_world = bone.parent.get_world_transform()
            parent_world_rot = parent_world.rotation
        else:
            parent_world_rot = Quat.identity()
        
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
        bone.pose_transform.rotation = pose_rotation

    def _update_gizmo_drag(self, mouse_pos) -> None:
        """Update bone during gizmo drag."""
        if self._gizmo_state != "dragging" or self._gizmo_drag_axis is None:
            return

        bone = self.get_selected_bone_object()
        if bone is None:
            return

        gizmo_pos = self.get_gizmo_position()
        if gizmo_pos is None:
            return

        gizmo_scale = self.get_gizmo_scale()
        aspect = self.width() / max(1, self.height())
        view = self._camera.get_view_matrix()
        proj = self._camera.get_projection_matrix(aspect)
        viewport = (0, 0, self.width(), self.height())

        if self._gizmo_mode == "rotation":
            self._update_rotation_gizmo_drag(mouse_pos, bone, gizmo_pos, gizmo_scale, view, proj, viewport)
        elif self._gizmo_mode == "movement":
            self._update_movement_gizmo_drag(mouse_pos, bone, gizmo_pos, gizmo_scale, view, proj, viewport)
        else:  # scale
            self._update_scale_gizmo_drag(mouse_pos, bone, gizmo_pos, gizmo_scale, view, proj, viewport)

    def _update_rotation_gizmo_drag(self, mouse_pos, bone, gizmo_pos, gizmo_scale, view, proj, viewport) -> None:
        """Update bone rotation during rotation gizmo drag."""
        if self._initial_delta_rotation is None or not self._gizmo:
            return

        # Get current point on the circle plane
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

        # Calculate INCREMENTAL rotation delta from previous point to current
        incremental_rotation = self._gizmo.get_rotation_from_drag(
            self._gizmo_drag_prev_point,
            current_point,
            self._gizmo_drag_axis,
            gizmo_pos
        )

        # Accumulate the incremental rotation
        self._accumulated_rotation = incremental_rotation * self._accumulated_rotation

        # Apply the accumulated rotation to the initial world-space delta
        new_delta_rotation = self._accumulated_rotation * self._initial_delta_rotation

        # Apply the world-space delta rotation to the bone
        self._apply_world_delta_rotation(bone, new_delta_rotation)

        # Update previous point for next frame
        self._gizmo_drag_prev_point = current_point

        # Mark skeleton as needing update
        if self._skeleton:
            for b in self._skeleton:
                b._mark_dirty()

        # Emit signal for UI update
        self.bone_rotation_changed.emit(self._selected_bone, new_delta_rotation)

    def _update_movement_gizmo_drag(self, mouse_pos, bone, gizmo_pos, gizmo_scale, view, proj, viewport) -> None:
        """Update bone position during movement gizmo drag."""
        if not self._movement_gizmo:
            return

        # Check if we're dragging the center (free movement) or an axis
        if self._gizmo_drag_axis == 'CENTER':
            # Get current point on the camera-facing plane
            current_point = self._movement_gizmo.get_point_on_plane(
                (mouse_pos.x(), mouse_pos.y()),
                gizmo_pos,
                view,
                proj,
                viewport
            )

            if current_point is None or self._gizmo_drag_prev_point is None:
                return

            # Calculate the incremental delta
            delta = (current_point - self._gizmo_drag_prev_point) / 5 #Speed adjustment

            # For free movement, use a 1:1 mapping (no speed scaling)
            # The plane intersection gives us world-space coordinates directly
            self._apply_movement_delta(bone, delta)

            # Update previous point for next frame
            self._gizmo_drag_prev_point = current_point

        else:
            # CRITICAL FIX: Use the INITIAL gizmo position as the axis reference point
            # The axis line must stay fixed in space during the drag, not move with the bone
            # If we use the current gizmo_pos, the axis shifts as the bone moves, causing drift
            initial_gizmo_pos = self._movement_drag_start_pos
            if initial_gizmo_pos is None:
                initial_gizmo_pos = gizmo_pos

            # Get current point on the axis (using INITIAL position as reference)
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

            # Scale the delta by a movement speed factor
            movement_speed = 0.5
            delta = delta * movement_speed

            # Apply the movement (rotates parent or translates root)
            self._apply_movement_delta(bone, delta)

            # Update previous point for next frame
            self._gizmo_drag_prev_point = current_point

        # Mark skeleton as needing update
        if self._skeleton:
            for b in self._skeleton:
                b._mark_dirty()

    def _update_scale_gizmo_drag(self, mouse_pos, bone, gizmo_pos, gizmo_scale, view, proj, viewport) -> None:
        """Update bone scale during scale gizmo drag."""
        if not self._scale_gizmo or not hasattr(self, '_initial_scale'):
            return

        # Get current point on the axis or plane
        current_point = self._scale_gizmo.get_point_on_axis(
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

        # Calculate scale delta from drag
        new_scale = self._scale_gizmo.get_scale_from_drag(
            self._gizmo_drag_start_point,
            current_point,
            self._gizmo_drag_axis,
            gizmo_pos,
            self._initial_scale
        )

        # Apply scale to the bone's pose transform
        # Scale is applied uniformly or per-axis depending on the handle
        bone.pose_transform.scale = new_scale
        bone._mark_dirty()

        # Update previous point for next frame
        self._gizmo_drag_prev_point = current_point

        # Mark skeleton as needing update
        if self._skeleton:
            for b in self._skeleton:
                b._mark_dirty()

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
            
            old_pos = bone.pose_transform.position
            new_pos = old_pos + local_delta
            bone.pose_transform.position = new_pos
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

    def _end_gizmo_drag(self) -> None:
        """End gizmo drag operation."""
        self._gizmo_state = "idle"
        self._is_dragging_gizmo = False
        self._gizmo_drag_axis = None
        self._gizmo_drag_start_point = None
        self._gizmo_drag_prev_point = None
        self._accumulated_rotation = None
        self._initial_bone_rotation = None
        self._initial_delta_rotation = None
        self._movement_drag_start_pos = None
        self._movement_drag_prev_pos = None

        # Emit pose changed signal after drag completes
        self.pose_changed.emit()

    # -------------------------------------------------------------------------
    # Event Handling
    # -------------------------------------------------------------------------

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Handle mouse press."""
        self._last_mouse_pos = event.pos()
        self._mouse_button = event.button()

        # Check for joint selection (left button, no modifiers)
        if (event.button() == Qt.LeftButton and
            not (event.modifiers() & (Qt.ShiftModifier | Qt.ControlModifier)) and
            self._skeleton and self._joint_renderer):
            
            # First check if we're clicking on a joint
            aspect = self.width() / max(1, self.height())
            view = self._camera.get_view_matrix()
            proj = self._camera.get_projection_matrix(aspect)
            viewport = (0, 0, self.width(), self.height())
            joint_scale = self._camera.distance * 0.5
            
            hit_joint = self._joint_renderer.hit_test(
                (event.x(), event.y()),
                self._skeleton,
                view, proj, viewport,
                scale=joint_scale
            )
            
            if hit_joint:
                # Select this bone
                self._selected_bone = hit_joint
                self.bone_selected.emit(hit_joint)
                self.update()
                return  # Don't process as camera control

        # Check for gizmo interaction (left button, no modifiers, bone selected)
        if (event.button() == Qt.LeftButton and
            not (event.modifiers() & (Qt.ShiftModifier | Qt.ControlModifier)) and
            self._selected_bone):

            # Update hover state
            self._update_gizmo_hover(event.pos())

            # Start drag if hovering over gizmo
            if self._gizmo_hover_axis:
                if self._start_gizmo_drag(event.pos()):
                    return # Don't process as camera control

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Handle mouse move."""
        # Handle gizmo dragging
        if self._gizmo_state == "dragging":
            self._update_gizmo_drag(event.pos())
            self._last_mouse_pos = event.pos()
            self.update()
            return

        # Exit early if no mouse button pressed
        if self._last_mouse_pos is None:
            # Update joint hover state
            if self._skeleton and self._joint_renderer:
                aspect = self.width() / max(1, self.height())
                view = self._camera.get_view_matrix()
                proj = self._camera.get_projection_matrix(aspect)
                viewport = (0, 0, self.width(), self.height())
                joint_scale = self._camera.distance * 0.5
                
                self._hovered_joint = self._joint_renderer.hit_test(
                    (event.x(), event.y()),
                    self._skeleton,
                    view, proj, viewport,
                    scale=joint_scale
                )
            
            # Update gizmo hover state when not dragging
            if self._selected_bone:
                self._update_gizmo_hover(event.pos())
            self.update()
            return

        dx = event.x() - self._last_mouse_pos.x()
        dy = event.y() - self._last_mouse_pos.y()

        # Camera controls with modifiers
        if self._mouse_button == Qt.LeftButton:
            modifiers = event.modifiers()
            if modifiers & Qt.ShiftModifier:
                # Shift+Left: Rotate camera (only if not interacting with gizmo)
                self._camera.rotate(dx * 0.01, dy * 0.01)
            elif modifiers & Qt.ControlModifier:
                # Ctrl+Left: Zoom camera
                self._camera.pan(dx, dy)
        elif self._mouse_button == Qt.RightButton:
            modifiers = event.modifiers()
            if modifiers & Qt.ShiftModifier:
                # Shift+Right: Rotate camera (only if not interacting with gizmo)
                self._camera.get_position()
            else:
                # Zoom camera
                self._camera.zoom(dy * 0.01)
        self._last_mouse_pos = event.pos()
        self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Handle mouse release."""
        # End gizmo drag if active
        if self._gizmo_state == "dragging":
            self._end_gizmo_drag()

        self._last_mouse_pos = None
        self._mouse_button = None

        # Update hover state
        if self._selected_bone:
            self._update_gizmo_hover(event.pos())

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

        # Undo: Ctrl+Z
        if key == Qt.Key_Z and modifiers & Qt.ControlModifier:
            if modifiers & Qt.ShiftModifier:
                # Ctrl+Shift+Z = Redo
                self.redo()
            else:
                # Ctrl+Z = Undo
                self.undo()
            return

        # Redo: Ctrl+Y
        if key == Qt.Key_Y and modifiers & Qt.ControlModifier:
            self.redo()
            return

        # Save pose: Ctrl+S
        if key == Qt.Key_S and modifiers & Qt.ControlModifier:
            self.save_pose_dialog()
            return

        # Load pose: Ctrl+O
        if key == Qt.Key_O and modifiers & Qt.ControlModifier:
            self.load_pose_dialog()
            return

        if key == Qt.Key_F:
            # Frame the model
            self._frame_model()
        elif key == Qt.Key_T:
            # Toggle mesh visibility
            self.set_show_mesh(not self._show_mesh)
        elif key == Qt.Key_S:
            # Toggle skeleton visibility (only without Ctrl)
            if not (modifiers & Qt.ControlModifier):
                self.set_show_skeleton(not self._show_skeleton)
        elif key == Qt.Key_R:
            # Reset camera
            self._camera = Camera()
        elif key == Qt.Key_G:
            # Toggle gizmo mode (rotation <-> movement)
            self.toggle_gizmo_mode()

        self.update()

    def _frame_model(self) -> None:
        """Frame the model in the viewport."""
        if not self._skeleton:
            return

        # Calculate bounding box
        min_pos = Vec3(float('inf'), float('inf'), float('inf'))
        max_pos = Vec3(float('-inf'), float('-inf'), float('-inf'))

        for bone in self._skeleton:
            pos = bone.get_world_position()
            min_pos = Vec3(min(min_pos.x, pos.x), min(min_pos.y, pos.y), min(min_pos.z, pos.z))
            max_pos = Vec3(max(max_pos.x, pos.x), max(max_pos.y, pos.y), max(max_pos.z, pos.z))

        # Set camera target to center
        center = (min_pos + max_pos) * 0.5
        self._camera.target = center

        # Set distance based on bounding box size
        size = (max_pos - min_pos).length()
        self._camera.distance = max(2.0, size * 1.5)

    def _on_update(self) -> None:
        """Called by update timer."""
        # Could be used for animation updates
        pass

    # -------------------------------------------------------------------------
    # Undo/Redo Public API
    # -------------------------------------------------------------------------

    def _emit_undo_redo_state(self) -> None:
        """Emit the current undo/redo availability state."""
        self.undo_redo_changed.emit(
            self._undo_redo_stack.can_undo,
            self._undo_redo_stack.can_redo
        )

    def can_undo(self) -> bool:
        """Check if undo is available."""
        return self._undo_redo_stack.can_undo

    def can_redo(self) -> bool:
        """Check if redo is available."""
        return self._undo_redo_stack.can_redo

    def undo(self) -> bool:
        """
        Undo the last pose change.
        
        Returns:
            True if undo was performed, False if no undo available
        """
        if not self._skeleton:
            return False
        
        snapshot = self._undo_redo_stack.undo(self._skeleton)
        if snapshot:
            self._emit_undo_redo_state()
            self.pose_changed.emit()
            self.update()
            return True
        return False

    def redo(self) -> bool:
        """
        Redo the last undone pose change.
        
        Returns:
            True if redo was performed, False if no redo available
        """
        if not self._skeleton:
            return False
        
        snapshot = self._undo_redo_stack.redo(self._skeleton)
        if snapshot:
            self._emit_undo_redo_state()
            self.pose_changed.emit()
            self.update()
            return True
        return False

    def push_undo_state(self, name: str = "") -> None:
        """
        Push the current pose state to the undo stack.
        
        Call this BEFORE making programmatic changes to the skeleton pose.
        For gizmo interactions, this is handled automatically.
        
        Args:
            name: Optional name for this state (e.g., "Rotate Head")
        """
        if self._skeleton:
            self._undo_redo_stack.push_state(self._skeleton, name)
            self._emit_undo_redo_state()

    def clear_undo_history(self) -> None:
        """Clear all undo/redo history."""
        self._undo_redo_stack.clear()
        self._emit_undo_redo_state()

    # -------------------------------------------------------------------------
    # Pose Save/Load Public API
    # -------------------------------------------------------------------------

    def save_pose_dialog(self) -> bool:
        """
        Show a file dialog to save the current pose.
        
        Returns:
            True if pose was saved, False otherwise
        """
        if not self._skeleton:
            QMessageBox.warning(self, "Save Pose", "No skeleton loaded.")
            return False
        
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Save Pose",
            "",
            "Pose Files (*.json);;All Files (*)"
        )
        
        if not filepath:
            return False
        
        # Ensure .json extension
        if not filepath.endswith('.json'):
            filepath += '.json'
        
        if PoseSerializer.save_pose(filepath, self._skeleton):
            return True
        else:
            QMessageBox.warning(self, "Save Pose", "Failed to save pose.")
            return False

    def load_pose_dialog(self) -> bool:
        """
        Show a file dialog to load a pose.
        
        Returns:
            True if pose was loaded, False otherwise
        """
        if not self._skeleton:
            QMessageBox.warning(self, "Load Pose", "No skeleton loaded.")
            return False
        
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Load Pose",
            "",
            "Pose Files (*.json);;All Files (*)"
        )
        
        if not filepath:
            return False
        
        # Push current state to undo stack before loading
        self._undo_redo_stack.push_state(self._skeleton, "Before Load")
        
        snapshot = PoseSerializer.load_pose(filepath, self._skeleton)
        if snapshot:
            self._emit_undo_redo_state()
            self.pose_changed.emit()
            self.update()
            return True
        else:
            QMessageBox.warning(self, "Load Pose", "Failed to load pose.")
            return False

    def save_pose(self, filepath: str) -> bool:
        """
        Save the current pose to a file.
        
        Args:
            filepath: Path to save the pose file
            
        Returns:
            True if successful, False otherwise
        """
        if not self._skeleton:
            return False
        return PoseSerializer.save_pose(filepath, self._skeleton)

    def load_pose(self, filepath: str) -> bool:
        """
        Load a pose from a file.
        
        Args:
            filepath: Path to the pose file
            
        Returns:
            True if successful, False otherwise
        """
        if not self._skeleton:
            return False
        
        # Push current state to undo stack before loading
        self._undo_redo_stack.push_state(self._skeleton, "Before Load")
        
        snapshot = PoseSerializer.load_pose(filepath, self._skeleton)
        if snapshot:
            self._emit_undo_redo_state()
            self.pose_changed.emit()
            self.update()
            return True
        return False

    def reset_pose(self) -> None:
        """Reset all bones to bind pose (with undo support)."""
        if not self._skeleton:
            return
        
        # Push current state to undo stack
        self._undo_redo_stack.push_state(self._skeleton, "Reset Pose")
        
        # Reset all bones
        self._skeleton.reset_pose()
        self._skeleton.update_all_transforms()
        
        self._emit_undo_redo_state()
        self.pose_changed.emit()
        self.update()

    def cleanup(self) -> None:
        """Clean up OpenGL resources."""
        if self._renderer:
            self._renderer.cleanup()
        if self._skeleton_viz:
            self._skeleton_viz.cleanup()
        if self._gizmo:
            self._gizmo.cleanup()

"""
Rotation Gizmo - 3D Rotation Manipulation Widget
================================================

Renders a 3-torus rotation gizmo for intuitive bone rotation.
Each torus represents rotation around one axis:
- X axis (red): rotation in YZ plane
- Y axis (green): rotation in XZ plane
- Z axis (blue): rotation in XY plane

The torus rings are rendered as 3D geometry with lighting for
better depth perception and visual feedback.
"""

import math
import ctypes
from typing import Optional, Tuple, List
from OpenGL.GL import *
from OpenGL.GL import shaders
import numpy as np

from ..vec3 import Vec3
from ..mat4 import Mat4
from ..quat import Quat

from .gizmo_base import GIZMO_VERTEX_SHADER, GIZMO_FRAGMENT_SHADER


class RotationGizmo:
    """
    3D rotation gizmo for bone manipulation.

    Renders three circles for rotation around X, Y, and Z axes.
    Supports hover highlighting and drag interaction.

    Usage:
        gizmo = RotationGizmo()
        gizmo.initialize()

        # In render loop:
        gizmo.render(position, scale, view, proj, hovered_axis='X')

        # For hit testing:
        axis = gizmo.hit_test(mouse_pos, position, scale, view, proj, viewport)
    """

    # Default colors for each axis (matching UI color scheme)
    COLOR_X = (0.91, 0.30, 0.24)  # #E74C3C - Red (matching Colors.GIZMO_X)
    COLOR_Y = (0.15, 0.68, 0.38)  # #27AE60 - Green (matching Colors.GIZMO_Y)
    COLOR_Z = (0.20, 0.60, 0.86)  # #3498DB - Blue (matching Colors.GIZMO_Z)

    # Highlight colors
    COLOR_HOVER = (0.95, 0.77, 0.06)  # #F1C40F - Yellow (matching Colors.GIZMO_HOVER)
    COLOR_DRAG = (0.95, 0.61, 0.07)  # #F39C12 - Orange (matching Colors.GIZMO_DRAG)

    def __init__(self, radius: float = 1.0, segments: int = 64, tube_radius: float = 0.05, tube_segments: int = 16):
        """
        Create a rotation gizmo.

        Args:
            radius: Base radius of the torus rings (distance from center to tube center)
            segments: Number of segments around the main circle
            tube_radius: Radius of the tube (thickness of the ring)
            tube_segments: Number of segments around the tube cross-section
        """
        self._radius = radius
        self._segments = segments
        self._tube_radius = tube_radius
        self._tube_segments = tube_segments

        # OpenGL resources
        self._program: Optional[int] = None
        self._vao: int = 0
        self._vbo: int = 0
        self._ebo: int = 0  # Element buffer for indices
        self._initialized: bool = False

        # Uniform locations
        self._u_model: int = -1
        self._u_view: int = -1
        self._u_projection: int = -1
        self._u_color_override: int = -1
        self._u_color_mix: int = -1
        self._u_light_dir: int = -1
        self._u_ambient: int = -1
        self._u_alpha: int = -1

        # Vertex data for each axis torus (position, normal, color)
        self._x_vertices: np.ndarray = np.array([])
        self._y_vertices: np.ndarray = np.array([])
        self._z_vertices: np.ndarray = np.array([])

        # Index data for each torus
        self._x_indices: np.ndarray = np.array([])
        self._y_indices: np.ndarray = np.array([])
        self._z_indices: np.ndarray = np.array([])

        # Index counts for each torus
        self._x_index_count: int = 0
        self._y_index_count: int = 0
        self._z_index_count: int = 0

    def initialize(self) -> bool:
        """
        Initialize OpenGL resources.

        Must be called after OpenGL context is created.

        Returns:
            True if initialization succeeded
        """
        if self._initialized:
            return True

        try:
            # Compile shaders
            vertex_shader = shaders.compileShader(GIZMO_VERTEX_SHADER, GL_VERTEX_SHADER)
            fragment_shader = shaders.compileShader(GIZMO_FRAGMENT_SHADER, GL_FRAGMENT_SHADER)
            self._program = shaders.compileProgram(vertex_shader, fragment_shader)

            # Get uniform locations
            self._u_model = glGetUniformLocation(self._program, 'u_model')
            self._u_view = glGetUniformLocation(self._program, 'u_view')
            self._u_projection = glGetUniformLocation(self._program, 'u_projection')
            self._u_color_override = glGetUniformLocation(self._program, 'u_color_override')
            self._u_color_mix = glGetUniformLocation(self._program, 'u_color_mix')
            self._u_light_dir = glGetUniformLocation(self._program, 'u_light_dir')
            self._u_ambient = glGetUniformLocation(self._program, 'u_ambient')
            self._u_alpha = glGetUniformLocation(self._program, 'u_alpha')

            # Generate torus geometry for each axis
            self._x_vertices, self._x_indices, self._x_index_count = self._generate_torus_vertices('X', self.COLOR_X)
            self._y_vertices, self._y_indices, self._y_index_count = self._generate_torus_vertices('Y', self.COLOR_Y)
            self._z_vertices, self._z_indices, self._z_index_count = self._generate_torus_vertices('Z', self.COLOR_Z)

            # Create VAO, VBO, and EBO
            self._vao = glGenVertexArrays(1)
            self._vbo = glGenBuffers(1)
            self._ebo = glGenBuffers(1)

            self._initialized = True
            return True

        except Exception as e:
            print(f"Failed to initialize rotation gizmo: {e}")
            return False

    def _generate_torus_vertices(self, axis: str, color: Tuple[float, float, float]) -> Tuple[np.ndarray, np.ndarray, int]:
        """
        Generate vertex data for a torus in the plane perpendicular to the given axis.

        Each vertex has position (x, y, z), normal (nx, ny, nz), and color (r, g, b).
        Uses triangle strips for efficient rendering.

        Args:
            axis: 'X', 'Y', or 'Z' - the axis the torus rotates around
            color: RGB color tuple for this torus

        Returns:
            Tuple of (NumPy array of vertex data, index array, index count for drawing)
            Vertex format: 9 floats per vertex (x, y, z, nx, ny, nz, r, g, b)
        """
        vertices = []
        indices = []

        major_radius = self._radius
        minor_radius = self._tube_radius
        major_segments = self._segments
        minor_segments = self._tube_segments

        # Generate vertices for the torus
        for i in range(major_segments + 1):
            u = (i / major_segments) * 2 * math.pi

            for j in range(minor_segments + 1):
                v = (j / minor_segments) * 2 * math.pi

                # Calculate the point on the torus (standard orientation: XY plane)
                x = (major_radius + minor_radius * math.cos(v)) * math.cos(u)
                y = (major_radius + minor_radius * math.cos(v)) * math.sin(u)
                z = minor_radius * math.sin(v)

                # Calculate normal (points outward from tube center)
                nx = math.cos(v) * math.cos(u)
                ny = math.cos(v) * math.sin(u)
                nz = math.sin(v)

                # Transform based on axis
                if axis == 'X':
                    # Torus in YZ plane: swap X with Z
                    pos = (z, x, y)
                    norm = (nz, nx, ny)
                elif axis == 'Y':
                    # Torus in XZ plane: swap Y with Z
                    pos = (x, z, y)
                    norm = (nx, nz, ny)
                else:  # Z
                    # Torus in XY plane: standard orientation
                    pos = (x, y, z)
                    norm = (nx, ny, nz)

                # Add vertex: position, normal, color
                vertices.extend([pos[0], pos[1], pos[2], norm[0], norm[1], norm[2], color[0], color[1], color[2]])

        # Generate indices for triangle strips
        for i in range(major_segments):
            for j in range(minor_segments):
                # Calculate vertex indices for this quad
                v0 = i * (minor_segments + 1) + j
                v1 = v0 + 1
                v2 = (i + 1) * (minor_segments + 1) + j
                v3 = v2 + 1

                # Two triangles per quad
                indices.extend([v0, v1, v2, v1, v3, v2])

        index_count = len(indices)
        vertices_array = np.array(vertices, dtype=np.float32)
        indices_array = np.array(indices, dtype=np.uint32)

        return vertices_array, indices_array, index_count

    def render(
        self,
        position: Vec3,
        scale: float,
        view_matrix: Mat4,
        projection_matrix: Mat4,
        hovered_axis: Optional[str] = None,
        dragging_axis: Optional[str] = None
    ) -> None:
        """
        Render the rotation gizmo.

        Args:
            position: World position of the gizmo center
            scale: Scale factor (typically based on camera distance)
            view_matrix: Camera view matrix
            projection_matrix: Camera projection matrix
            hovered_axis: Currently hovered axis ('X', 'Y', 'Z', or None)
            dragging_axis: Currently dragging axis ('X', 'Y', 'Z', or None)
        """
        if not self._initialized:
            return

        # Enable depth testing for proper 3D rendering
        glEnable(GL_DEPTH_TEST)
        glDepthFunc(GL_LEQUAL)

        # Enable blending for transparency
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        # Create model matrix (translation + scale)
        model_matrix = Mat4([
            scale, 0, 0, 0,
            0, scale, 0, 0,
            0, 0, scale, 0,
            position.x, position.y, position.z, 1
        ])

        glUseProgram(self._program)

        # Set view and projection uniforms
        glUniformMatrix4fv(self._u_model, 1, GL_FALSE, model_matrix.to_list())
        glUniformMatrix4fv(self._u_view, 1, GL_FALSE, view_matrix.to_list())
        glUniformMatrix4fv(self._u_projection, 1, GL_FALSE, projection_matrix.to_list())

        # Set lighting uniforms
        glUniform3f(self._u_light_dir, 0.5, 0.7, 0.5)
        glUniform1f(self._u_ambient, 0.3)

        # Render each axis torus
        self._render_torus(self._x_vertices, self._x_indices, self._x_index_count, 'X', hovered_axis, dragging_axis)
        self._render_torus(self._y_vertices, self._y_indices, self._y_index_count, 'Y', hovered_axis, dragging_axis)
        self._render_torus(self._z_vertices, self._z_indices, self._z_index_count, 'Z', hovered_axis, dragging_axis)

    def _render_torus(
        self,
        vertices: np.ndarray,
        indices: np.ndarray,
        index_count: int,
        axis: str,
        hovered_axis: Optional[str],
        dragging_axis: Optional[str]
    ) -> None:
        """
        Render a single torus with appropriate highlighting.

        Args:
            vertices: Vertex data for this torus
            indices: Index data for this torus
            index_count: Number of indices to draw
            axis: Axis identifier ('X', 'Y', or 'Z')
            hovered_axis: Currently hovered axis
            dragging_axis: Currently dragging axis
        """
        # Determine color override and alpha based on state
        if dragging_axis == axis:
            # Dragging this axis - fully opaque, bright color
            glUniform3f(self._u_color_override, *self.COLOR_DRAG)
            glUniform1f(self._u_color_mix, 1.0)
            glUniform1f(self._u_alpha, 1.0)
        elif hovered_axis == axis:
            # Hovering this axis - slightly transparent, highlighted color
            glUniform3f(self._u_color_override, *self.COLOR_HOVER)
            glUniform1f(self._u_color_mix, 0.7)
            glUniform1f(self._u_alpha, 0.95)
        else:
            # No highlight - semi-transparent for depth perception
            glUniform1f(self._u_color_mix, 0.0)
            glUniform1f(self._u_alpha, 0.7)

        # Upload vertices and indices
        glBindVertexArray(self._vao)

        # Upload vertex data
        glBindBuffer(GL_ARRAY_BUFFER, self._vbo)
        glBufferData(GL_ARRAY_BUFFER, vertices.nbytes, vertices, GL_STATIC_DRAW)

        # Upload index data
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self._ebo)
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, indices.nbytes, indices, GL_STATIC_DRAW)

        # Position attribute (location = 0)
        stride = 9 * 4  # 9 floats per vertex * 4 bytes per float
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, stride, None)
        glEnableVertexAttribArray(0)

        # Normal attribute (location = 1)
        glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(12))
        glEnableVertexAttribArray(1)

        # Color attribute (location = 2)
        glVertexAttribPointer(2, 3, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(24))
        glEnableVertexAttribArray(2)

        # Draw the torus
        glDrawElements(GL_TRIANGLES, index_count, GL_UNSIGNED_INT, None)

        glBindVertexArray(0)

    def hit_test(
        self,
        mouse_pos: Tuple[int, int],
        gizmo_position: Vec3,
        gizmo_scale: float,
        view_matrix: Mat4,
        projection_matrix: Mat4,
        viewport: Tuple[int, int, int, int]
    ) -> Optional[str]:
        """
        Test if the mouse is over one of the gizmo circles.

        Uses screen-space distance from the mouse to each circle's projected points.

        Args:
            mouse_pos: (x, y) mouse position in window coordinates
            gizmo_position: World position of the gizmo center
            gizmo_scale: Scale factor of the gizmo
            view_matrix: Camera view matrix
            projection_matrix: Camera projection matrix
            viewport: (x, y, width, height) of the viewport

        Returns:
            'X', 'Y', 'Z' if hovering over that axis, or None
        """
        # Calculate view-projection matrix
        view_proj = projection_matrix * view_matrix

        # Hit tolerance in screen pixels
        tolerance = 15.0

        # Test each axis
        best_axis = None
        best_distance = float('inf')

        for axis in ['X', 'Y', 'Z']:
            distance = self._get_screen_distance_to_circle(
                mouse_pos, axis, gizmo_position, gizmo_scale,
                view_proj, viewport
            )

            if distance < tolerance and distance < best_distance:
                best_distance = distance
                best_axis = axis

        return best_axis

    def _get_screen_distance_to_circle(
        self,
        mouse_pos: Tuple[int, int],
        axis: str,
        center: Vec3,
        scale: float,
        view_proj: Mat4,
        viewport: Tuple[int, int, int, int]
    ) -> float:
        """
        Calculate the minimum screen-space distance from mouse to a circle.

        Args:
            mouse_pos: (x, y) mouse position
            axis: 'X', 'Y', or 'Z'
            center: World position of gizmo center
            scale: Scale factor
            view_proj: View-projection matrix
            viewport: Viewport bounds

        Returns:
            Minimum screen-space distance to the circle
        """
        min_distance = float('inf')
        radius = self._radius * scale

        # Sample points along the circle
        for i in range(self._segments):
            angle = (i / self._segments) * 2 * math.pi

            # Get point on circle in world space
            if axis == 'X':
                point = Vec3(0, radius * math.cos(angle), radius * math.sin(angle))
            elif axis == 'Y':
                point = Vec3(radius * math.cos(angle), 0, radius * math.sin(angle))
            else:  # Z
                point = Vec3(radius * math.cos(angle), radius * math.sin(angle), 0)

            # Translate to gizmo position
            world_point = center + point

            # Project to screen space
            screen_x, screen_y = self._project_to_screen(world_point, view_proj, viewport)

            # Calculate distance to mouse
            dx = screen_x - mouse_pos[0]
            dy = screen_y - mouse_pos[1]
            distance = math.sqrt(dx * dx + dy * dy)

            min_distance = min(min_distance, distance)

        return min_distance

    def _project_to_screen(
        self,
        world_pos: Vec3,
        view_proj: Mat4,
        viewport: Tuple[int, int, int, int]
    ) -> Tuple[float, float]:
        """
        Project a world position to screen coordinates.

        Args:
            world_pos: Position in world space
            view_proj: View-projection matrix
            viewport: (x, y, width, height)

        Returns:
            (screen_x, screen_y) in window coordinates
        """
        # Apply view-projection
        m = view_proj.to_list()
        x = m[0] * world_pos.x + m[4] * world_pos.y + m[8] * world_pos.z + m[12]
        y = m[1] * world_pos.x + m[5] * world_pos.y + m[9] * world_pos.z + m[13]
        w = m[3] * world_pos.x + m[7] * world_pos.y + m[11] * world_pos.z + m[15]

        if abs(w) < 1e-10:
            w = 1e-10

        # Perspective divide
        ndc_x = x / w
        ndc_y = y / w

        # Convert to window coordinates
        screen_x = viewport[0] + (ndc_x + 1.0) * 0.5 * viewport[2]
        screen_y = viewport[1] + (1.0 - ndc_y) * 0.5 * viewport[3]  # Y is inverted

        return (screen_x, screen_y)

    def get_screen_space_rotation_angle(
        self,
        mouse_pos: Tuple[int, int],
        axis: str,
        center: Vec3,
        view_matrix: Mat4,
        projection_matrix: Mat4,
        viewport: Tuple[int, int, int, int]
    ) -> Optional[float]:
        """
        Calculate the screen-space angle from the gizmo center to the mouse position.

        This is used for screen-space rotation where the angle is calculated in 2D
        screen coordinates, providing smooth and predictable rotation behavior.

        Args:
            mouse_pos: (x, y) mouse position in window coordinates
            axis: 'X', 'Y', or 'Z'
            center: World position of gizmo center
            view_matrix: Camera view matrix
            projection_matrix: Camera projection matrix
            viewport: (x, y, width, height) of the viewport

        Returns:
            Angle in radians, or None if the gizmo center is not visible
        """
        # Project the gizmo center to screen space
        view_proj = projection_matrix * view_matrix
        center_screen = self._project_to_screen(center, view_proj, viewport)

        if center_screen is None:
            return None

        # Calculate the vector from center to mouse in screen space
        dx = mouse_pos[0] - center_screen[0]
        dy = mouse_pos[1] - center_screen[1]

        # Calculate the angle in screen space
        # Note: screen Y is inverted (0 at top), so we negate dy for correct rotation
        angle = math.atan2(dx, -dy)

        return angle

    def get_rotation_from_screen_angle(
        self,
        start_angle: float,
        current_angle: float,
        axis: str,
        slow_factor: float = 1.0
    ) -> Quat:
        """
        Calculate rotation quaternion from screen-space angle difference.

        Args:
            start_angle: Initial angle when drag started (radians)
            current_angle: Current angle during drag (radians)
            axis: 'X', 'Y', or 'Z'
            slow_factor: Multiplier for rotation speed (e.g., 0.25 for shift-held slow)

        Returns:
            Quaternion representing the rotation delta
        """
        # Get the rotation axis vector
        if axis == 'X':
            axis_vec = Vec3(1, 0, 0)
        elif axis == 'Y':
            axis_vec = Vec3(0, 1, 0)
        else:  # Z
            axis_vec = Vec3(0, 0, 1)

        # Calculate the angle difference
        angle_diff = current_angle - start_angle

        # Normalize the angle difference to [-π, π] to handle wrap-around
        while angle_diff > math.pi:
            angle_diff -= 2 * math.pi
        while angle_diff < -math.pi:
            angle_diff += 2 * math.pi

        # Apply slow factor for precision rotation
        angle_diff *= slow_factor

        # Convert to degrees and create quaternion
        rotation_degrees = math.degrees(angle_diff)
        return Quat.from_axis_angle_degrees(axis_vec, rotation_degrees)

    def get_rotation_from_drag(
        self,
        drag_prev_world: Vec3,
        drag_current_world: Vec3,
        axis: str,
        center: Vec3,
        drag_start_world: Optional[Vec3] = None
    ) -> Quat:
        """
        Calculate the rotation quaternion from drag motion using angular change.

        This implements a "spinning wheel" interaction model where dragging tangent
        to the ring causes rotation. Uses the signed angle between the previous and
        current direction vectors, which naturally ignores radial movement.

        Args:
            drag_prev_world: Previous frame's point in world space
            drag_current_world: Current point in world space (on the circle plane)
            axis: 'X', 'Y', or 'Z'
            center: Center of the gizmo (bone position)
            drag_start_world: Original hit point (unused, kept for API compatibility)

        Returns:
            Quaternion representing the rotation delta
        """
        # Get the rotation axis vector based on the specified axis
        if axis == 'X':
            axis_vec = Vec3(1, 0, 0)
        elif axis == 'Y':
            axis_vec = Vec3(0, 1, 0)
        else:  # Z
            axis_vec = Vec3(0, 0, 1)

        # Project points onto the plane perpendicular to the axis
        def project_to_plane(point: Vec3, axis: Vec3, center: Vec3) -> Vec3:
            relative = point - center
            dot = relative.x * axis.x + relative.y * axis.y + relative.z * axis.z
            return Vec3(
                relative.x - dot * axis.x,
                relative.y - dot * axis.y,
                relative.z - dot * axis.z
            )

        # Project both points onto the rotation plane
        prev_relative = project_to_plane(drag_prev_world, axis_vec, center)
        current_relative = project_to_plane(drag_current_world, axis_vec, center)

        # Get lengths
        prev_len = prev_relative.length()
        current_len = current_relative.length()

        # Minimum radius to avoid division by zero
        min_radius = 0.001
        if prev_len < min_radius or current_len < min_radius:
            return Quat.identity()

        # Normalize to get direction vectors
        prev_dir = Vec3(prev_relative.x / prev_len, prev_relative.y / prev_len, prev_relative.z / prev_len)
        current_dir = Vec3(current_relative.x / current_len, current_relative.y / current_len, current_relative.z / current_len)

        # Calculate the signed angle between the two direction vectors
        dot = prev_dir.x * current_dir.x + prev_dir.y * current_dir.y + prev_dir.z * current_dir.z

        # Cross product gives sin(angle) * axis direction
        cross = Vec3(
            prev_dir.y * current_dir.z - prev_dir.z * current_dir.y,
            prev_dir.z * current_dir.x - prev_dir.x * current_dir.z,
            prev_dir.x * current_dir.y - prev_dir.y * current_dir.x
        )

        # Project cross product onto rotation axis to get signed sin component
        axis_dot = cross.x * axis_vec.x + cross.y * axis_vec.y + cross.z * axis_vec.z

        # Clamp dot to valid range
        dot = max(-1.0, min(1.0, dot))

        # Calculate signed angle using atan2
        angle_radians = math.atan2(axis_dot, dot)

        # Convert to degrees and create quaternion
        rotation_degrees = math.degrees(angle_radians)
        return Quat.from_axis_angle_degrees(axis_vec, rotation_degrees)

    def get_point_on_circle_plane(
        self,
        mouse_pos: Tuple[int, int],
        axis: str,
        center: Vec3,
        scale: float,
        view_matrix: Mat4,
        projection_matrix: Mat4,
        viewport: Tuple[int, int, int, int]
    ) -> Optional[Vec3]:
        """
        Get the world-space point on the circle plane at the mouse position.

        This is used during dragging to track the current position on the
        rotation plane.

        Args:
            mouse_pos: (x, y) mouse position
            axis: 'X', 'Y', or 'Z'
            center: World position of gizmo center
            scale: Scale factor
            view_matrix: Camera view matrix
            projection_matrix: Camera projection matrix
            viewport: Viewport bounds

        Returns:
            World-space point on the circle plane, or None if invalid
        """
        # Convert mouse to NDC
        ndc_x = (2.0 * (mouse_pos[0] - viewport[0]) / viewport[2]) - 1.0
        ndc_y = 1.0 - (2.0 * (mouse_pos[1] - viewport[1]) / viewport[3])

        # Create inverse matrices
        view_inv = self._inverse_matrix(view_matrix)
        proj_inv = self._inverse_matrix(projection_matrix)

        # Get camera position from view matrix
        cam_pos = Vec3(view_inv[12], view_inv[13], view_inv[14])

        # Ray direction in world space
        ray_clip = Vec3(ndc_x, ndc_y, -1.0)

        # Transform to view space
        ray_view = Vec3(
            ray_clip.x / proj_inv[0],
            ray_clip.y / proj_inv[5],
            -1.0
        )

        # Transform to world space
        ray_world = Vec3(
            view_inv[0] * ray_view.x + view_inv[4] * ray_view.y + view_inv[8] * ray_view.z,
            view_inv[1] * ray_view.x + view_inv[5] * ray_view.y + view_inv[9] * ray_view.z,
            view_inv[2] * ray_view.x + view_inv[6] * ray_view.y + view_inv[10] * ray_view.z
        )

        # Normalize
        ray_len = math.sqrt(ray_world.x**2 + ray_world.y**2 + ray_world.z**2)
        if ray_len < 1e-10:
            return None
        ray_world = Vec3(ray_world.x / ray_len, ray_world.y / ray_len, ray_world.z / ray_len)

        # Get the plane axis
        if axis == 'X':
            plane_normal = Vec3(1, 0, 0)
        elif axis == 'Y':
            plane_normal = Vec3(0, 1, 0)
        else:
            plane_normal = Vec3(0, 0, 1)

        # Ray-plane intersection
        denom = ray_world.x * plane_normal.x + ray_world.y * plane_normal.y + ray_world.z * plane_normal.z

        if abs(denom) < 1e-10:
            return None

        t = ((center.x - cam_pos.x) * plane_normal.x +
             (center.y - cam_pos.y) * plane_normal.y +
             (center.z - cam_pos.z) * plane_normal.z) / denom

        if t < 0:
            return None

        # Calculate intersection point
        return Vec3(
            cam_pos.x + t * ray_world.x,
            cam_pos.y + t * ray_world.y,
            cam_pos.z + t * ray_world.z
        )

    def _inverse_matrix(self, m: Mat4) -> List[float]:
        """
        Compute the inverse of a 4x4 matrix.

        Args:
            m: Mat4 matrix

        Returns:
            List of 16 floats representing the inverse matrix
        """
        data = m.to_list()
        arr = np.array(data).reshape(4, 4)
        try:
            inv = np.linalg.inv(arr)
            return inv.flatten().tolist()
        except np.linalg.LinAlgError:
            return [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]

    def cleanup(self) -> None:
        """Clean up OpenGL resources."""
        if self._vao:
            glDeleteVertexArrays(1, [self._vao])
            self._vao = 0
        if self._vbo:
            glDeleteBuffers(1, [self._vbo])
            self._vbo = 0
        if self._ebo:
            glDeleteBuffers(1, [self._ebo])
            self._ebo = 0
        if self._program:
            glDeleteProgram(self._program)
            self._program = 0

        self._initialized = False

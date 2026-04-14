"""
Movement Gizmo - Translation Arrow Widget
=========================================

3D movement gizmo for bone manipulation via parent rotation.
Renders three arrows for translation along X, Y, and Z axes.
"""

import math
import ctypes
from typing import Optional, Tuple, List
from OpenGL.GL import *
from OpenGL.GL import shaders
import numpy as np

from ..vec3 import Vec3
from ..mat4 import Mat4

from .gizmo_base import GIZMO_VERTEX_SHADER, GIZMO_FRAGMENT_SHADER


class MovementGizmo:
    """
    3D movement gizmo for bone manipulation via parent rotation.

    Renders three arrows for translation along X, Y, and Z axes.
    When dragging an arrow, the parent bone rotates to move the
    selected bone along the chosen axis.

    For root bones (no parent), the entire model translates instead.

    Usage:
        gizmo = MovementGizmo()
        gizmo.initialize()

        # In render loop:
        gizmo.render(position, scale, view, proj, hovered_axis='X')

        # For hit testing:
        axis = gizmo.hit_test(mouse_pos, position, scale, view, proj, viewport)

        # For drag tracking:
        point = gizmo.get_point_on_axis(mouse_pos, axis, position, scale, view, proj, viewport)
    """

    # Default colors for each axis
    COLOR_X = (1.0, 0.2, 0.2)  # Red
    COLOR_Y = (0.2, 1.0, 0.2)  # Green
    COLOR_Z = (0.2, 0.2, 1.0)  # Blue

    # Highlight colors
    COLOR_HOVER = (1.0, 1.0, 0.2)  # Yellow
    COLOR_DRAG = (1.0, 0.8, 0.2)  # Orange-yellow

    # Arrow dimensions (relative to gizmo scale)
    SHAFT_LENGTH = 0.7  # Length of the cylinder shaft
    SHAFT_RADIUS = 0.03  # Radius of the shaft
    HEAD_LENGTH = 0.3  # Length of the cone head
    HEAD_RADIUS = 0.08  # Base radius of the cone

    # Center ring dimensions (ring that faces the camera)
    CENTER_RING_RADIUS = 0.1  # Outer radius of the center ring
    CENTER_RING_THICKNESS = 0.02  # Thickness of the ring (tube radius)
    CENTER_COLOR = (0.8, 0.8, 0.8)  # Light gray for center

    def __init__(self, shaft_segments: int = 16, head_segments: int = 16, ring_segments: int = 32):
        """
        Create a movement gizmo.

        Args:
            shaft_segments: Number of segments around the shaft cylinder
            head_segments: Number of segments around the cone head
            ring_segments: Number of segments for the center ring
        """
        self._shaft_segments = shaft_segments
        self._head_segments = head_segments
        self._ring_segments = ring_segments

        # OpenGL resources
        self._program: Optional[int] = None
        self._vao: int = 0
        self._vbo: int = 0
        self._ebo: int = 0
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

        # Vertex data for each axis arrow (position, normal, color)
        self._x_vertices: np.ndarray = np.array([])
        self._y_vertices: np.ndarray = np.array([])
        self._z_vertices: np.ndarray = np.array([])

        # Index data for each arrow
        self._x_indices: np.ndarray = np.array([])
        self._y_indices: np.ndarray = np.array([])
        self._z_indices: np.ndarray = np.array([])

        # Index counts for each arrow
        self._x_index_count: int = 0
        self._y_index_count: int = 0
        self._z_index_count: int = 0

        # Vertex data for center sphere
        self._center_vertices: np.ndarray = np.array([])
        self._center_indices: np.ndarray = np.array([])
        self._center_index_count: int = 0

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

            # Generate arrow geometry for each axis
            self._x_vertices, self._x_indices, self._x_index_count = self._generate_arrow_geometry('X', self.COLOR_X)
            self._y_vertices, self._y_indices, self._y_index_count = self._generate_arrow_geometry('Y', self.COLOR_Y)
            self._z_vertices, self._z_indices, self._z_index_count = self._generate_arrow_geometry('Z', self.COLOR_Z)

            # Generate center ring geometry
            self._center_vertices, self._center_indices, self._center_index_count = self._generate_ring_geometry(
                self.CENTER_RING_RADIUS, self.CENTER_RING_THICKNESS, self.CENTER_COLOR
            )

            # Create VAO, VBO, and EBO
            self._vao = glGenVertexArrays(1)
            self._vbo = glGenBuffers(1)
            self._ebo = glGenBuffers(1)

            self._initialized = True
            return True

        except Exception as e:
            print(f"Failed to initialize movement gizmo: {e}")
            return False

    def _generate_arrow_geometry(self, axis: str, color: Tuple[float, float, float]) -> Tuple[np.ndarray, np.ndarray, int]:
        """
        Generate vertex data for an arrow pointing along the given axis.

        Args:
            axis: 'X', 'Y', or 'Z' - the axis the arrow points along
            color: RGB color tuple for this arrow

        Returns:
            Tuple of (vertex array, index array, index count)
        """
        vertices = []
        indices = []

        shaft_radius = self.SHAFT_RADIUS
        shaft_length = self.SHAFT_LENGTH
        head_radius = self.HEAD_RADIUS
        head_length = self.HEAD_LENGTH
        shaft_segments = self._shaft_segments
        head_segments = self._head_segments

        # Generate shaft cylinder (along Y axis, then transform)
        vertex_offset = 0

        # Shaft vertices (two rings: bottom and top)
        for ring in range(2):
            y = ring * shaft_length
            for i in range(shaft_segments):
                angle = (i / shaft_segments) * 2 * math.pi
                x = shaft_radius * math.cos(angle)
                z = shaft_radius * math.sin(angle)

                nx = math.cos(angle)
                nz = math.sin(angle)
                ny = 0.0

                pos, norm = self._transform_for_axis(axis, x, y, z, nx, ny, nz)
                vertices.extend([pos[0], pos[1], pos[2], norm[0], norm[1], norm[2], color[0], color[1], color[2]])

        # Shaft indices (triangle strip between rings)
        for i in range(shaft_segments):
            v0 = i
            v1 = i + shaft_segments
            v2 = (i + 1) % shaft_segments
            v3 = (i + 1) % shaft_segments + shaft_segments
            indices.extend([v0, v2, v1, v2, v3, v1])

        vertex_offset = 2 * shaft_segments

        # Shaft cap (bottom circle)
        cap_center_idx = vertex_offset
        pos, norm = self._transform_for_axis(axis, 0, 0, 0, 0, -1, 0)
        vertices.extend([pos[0], pos[1], pos[2], norm[0], norm[1], norm[2], color[0], color[1], color[2]])
        vertex_offset += 1

        for i in range(shaft_segments):
            angle = (i / shaft_segments) * 2 * math.pi
            x = shaft_radius * math.cos(angle)
            z = shaft_radius * math.sin(angle)
            pos, norm = self._transform_for_axis(axis, x, 0, z, 0, -1, 0)
            vertices.extend([pos[0], pos[1], pos[2], norm[0], norm[1], norm[2], color[0], color[1], color[2]])

        for i in range(shaft_segments):
            indices.extend([cap_center_idx, cap_center_idx + 1 + i, cap_center_idx + 1 + ((i + 1) % shaft_segments)])

        vertex_offset = cap_center_idx + 1 + shaft_segments

        # Generate cone head
        cone_base_y = shaft_length
        cone_tip_y = shaft_length + head_length

        for i in range(head_segments):
            angle = (i / head_segments) * 2 * math.pi
            x = head_radius * math.cos(angle)
            z = head_radius * math.sin(angle)

            slope = head_radius / head_length
            nx = math.cos(angle)
            nz = math.sin(angle)
            ny = slope
            length = math.sqrt(nx*nx + ny*ny + nz*nz)
            nx, ny, nz = nx/length, ny/length, nz/length

            pos, norm = self._transform_for_axis(axis, x, cone_base_y, z, nx, ny, nz)
            vertices.extend([pos[0], pos[1], pos[2], norm[0], norm[1], norm[2], color[0], color[1], color[2]])

        vertex_offset = len(vertices) // 9

        # Tip vertex
        pos, norm = self._transform_for_axis(axis, 0, cone_tip_y, 0, 0, 1, 0)
        vertices.extend([pos[0], pos[1], pos[2], norm[0], norm[1], norm[2], color[0], color[1], color[2]])
        tip_idx = vertex_offset

        # Cone indices (fan from tip to base)
        for i in range(head_segments):
            base_idx = tip_idx - head_segments + i
            next_idx = tip_idx - head_segments + ((i + 1) % head_segments)
            indices.extend([tip_idx, next_idx, base_idx])

        # Cone base cap
        base_center_idx = len(vertices) // 9
        pos, norm = self._transform_for_axis(axis, 0, cone_base_y, 0, 0, -1, 0)
        vertices.extend([pos[0], pos[1], pos[2], norm[0], norm[1], norm[2], color[0], color[1], color[2]])

        for i in range(head_segments):
            angle = (i / head_segments) * 2 * math.pi
            x = head_radius * math.cos(angle)
            z = head_radius * math.sin(angle)
            pos, norm = self._transform_for_axis(axis, x, cone_base_y, z, 0, -1, 0)
            vertices.extend([pos[0], pos[1], pos[2], norm[0], norm[1], norm[2], color[0], color[1], color[2]])

        for i in range(head_segments):
            indices.extend([base_center_idx, base_center_idx + 1 + ((i + 1) % head_segments), base_center_idx + 1 + i])

        index_count = len(indices)
        vertices_array = np.array(vertices, dtype=np.float32)
        indices_array = np.array(indices, dtype=np.uint32)

        return vertices_array, indices_array, index_count

    def _transform_for_axis(self, axis: str, x: float, y: float, z: float, 
                           nx: float, ny: float, nz: float) -> Tuple[Tuple[float, float, float], Tuple[float, float, float]]:
        """Transform position and normal from Y-axis arrow to the specified axis."""
        if axis == 'X':
            return (y, x, z), (ny, nx, nz)
        elif axis == 'Y':
            return (x, y, z), (nx, ny, nz)
        else:  # Z
            return (x, z, y), (nx, nz, ny)

    def _generate_ring_geometry(self, radius: float, thickness: float, 
                                color: Tuple[float, float, float]) -> Tuple[np.ndarray, np.ndarray, int]:
        """Generate vertex data for a flat ring (torus) in the XY plane."""
        vertices = []
        indices = []

        segments = self._ring_segments
        tube_segments = 16

        for i in range(segments + 1):
            u = 2 * math.pi * i / segments
            cos_u = math.cos(u)
            sin_u = math.sin(u)

            for j in range(tube_segments + 1):
                v = 2 * math.pi * j / tube_segments
                cos_v = math.cos(v)
                sin_v = math.sin(v)

                x = (radius + thickness * cos_v) * cos_u
                y = (radius + thickness * cos_v) * sin_u
                z = thickness * sin_v

                nx = cos_v * cos_u
                ny = cos_v * sin_u
                nz = sin_v

                vertices.extend([x, y, z, nx, ny, nz, color[0], color[1], color[2]])

        for i in range(segments):
            for j in range(tube_segments):
                current = i * (tube_segments + 1) + j
                next_i = current + tube_segments + 1
                indices.extend([current, next_i, current + 1])
                indices.extend([current + 1, next_i, next_i + 1])

        return (
            np.array(vertices, dtype=np.float32),
            np.array(indices, dtype=np.uint32),
            len(indices)
        )

    def render(self, position: Vec3, scale: float, view_matrix: Mat4, 
               projection_matrix: Mat4, hovered_axis: Optional[str] = None,
               dragging_axis: Optional[str] = None) -> None:
        """Render the movement gizmo."""
        if not self._initialized:
            return

        glEnable(GL_DEPTH_TEST)
        glDepthFunc(GL_LEQUAL)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        model_matrix = Mat4([
            scale, 0, 0, 0,
            0, scale, 0, 0,
            0, 0, scale, 0,
            position.x, position.y, position.z, 1
        ])

        glUseProgram(self._program)
        glUniformMatrix4fv(self._u_model, 1, GL_FALSE, model_matrix.to_list())
        glUniformMatrix4fv(self._u_view, 1, GL_FALSE, view_matrix.to_list())
        glUniformMatrix4fv(self._u_projection, 1, GL_FALSE, projection_matrix.to_list())
        glUniform3f(self._u_light_dir, 0.5, 0.7, 0.5)
        glUniform1f(self._u_ambient, 0.3)

        self._render_arrow(self._x_vertices, self._x_indices, self._x_index_count, 'X', hovered_axis, dragging_axis)
        self._render_arrow(self._y_vertices, self._y_indices, self._y_index_count, 'Y', hovered_axis, dragging_axis)
        self._render_arrow(self._z_vertices, self._z_indices, self._z_index_count, 'Z', hovered_axis, dragging_axis)
        self._render_center_ring(position, scale, view_matrix, hovered_axis, dragging_axis)

    def _render_arrow(self, vertices: np.ndarray, indices: np.ndarray, index_count: int,
                      axis: str, hovered_axis: Optional[str], dragging_axis: Optional[str]) -> None:
        """Render a single arrow with appropriate highlighting."""
        glDisable(GL_DEPTH_TEST)

        if dragging_axis == axis:
            glUniform3f(self._u_color_override, *self.COLOR_DRAG)
            glUniform1f(self._u_color_mix, 1.0)
            glUniform1f(self._u_alpha, 1.0)
        elif hovered_axis == axis:
            glUniform3f(self._u_color_override, *self.COLOR_HOVER)
            glUniform1f(self._u_color_mix, 0.7)
            glUniform1f(self._u_alpha, 0.95)
        else:
            glUniform1f(self._u_color_mix, 0.0)
            glUniform1f(self._u_alpha, 0.7)

        glBindVertexArray(self._vao)
        glBindBuffer(GL_ARRAY_BUFFER, self._vbo)
        glBufferData(GL_ARRAY_BUFFER, vertices.nbytes, vertices, GL_STATIC_DRAW)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self._ebo)
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, indices.nbytes, indices, GL_STATIC_DRAW)

        stride = 9 * 4
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, stride, None)
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(12))
        glEnableVertexAttribArray(1)
        glVertexAttribPointer(2, 3, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(24))
        glEnableVertexAttribArray(2)

        glDrawElements(GL_TRIANGLES, index_count, GL_UNSIGNED_INT, None)
        glEnable(GL_DEPTH_TEST)
        glBindVertexArray(0)

    def _render_center_ring(self, position: Vec3, scale: float, view_matrix: Mat4,
                            hovered_axis: Optional[str], dragging_axis: Optional[str]) -> None:
        """Render the center ring with billboarding to face camera."""
        glDisable(GL_DEPTH_TEST)

        if dragging_axis == 'CENTER':
            glUniform3f(self._u_color_override, *self.COLOR_DRAG)
            glUniform1f(self._u_color_mix, 1.0)
            glUniform1f(self._u_alpha, 1.0)
        elif hovered_axis == 'CENTER':
            glUniform3f(self._u_color_override, *self.COLOR_HOVER)
            glUniform1f(self._u_color_mix, 0.7)
            glUniform1f(self._u_alpha, 0.95)
        else:
            glUniform1f(self._u_color_mix, 0.0)
            glUniform1f(self._u_alpha, 0.8)

        view_list = view_matrix.to_list()
        billboard_rot = [
            view_list[0], view_list[4], view_list[8], 0,
            view_list[1], view_list[5], view_list[9], 0,
            view_list[2], view_list[6], view_list[10], 0,
            0, 0, 0, 1
        ]

        model_matrix = Mat4([
            scale * billboard_rot[0], scale * billboard_rot[1], scale * billboard_rot[2], 0,
            scale * billboard_rot[4], scale * billboard_rot[5], scale * billboard_rot[6], 0,
            scale * billboard_rot[8], scale * billboard_rot[9], scale * billboard_rot[10], 0,
            position.x, position.y, position.z, 1
        ])

        glUniformMatrix4fv(self._u_model, 1, GL_FALSE, model_matrix.to_list())

        glBindVertexArray(self._vao)
        glBindBuffer(GL_ARRAY_BUFFER, self._vbo)
        glBufferData(GL_ARRAY_BUFFER, self._center_vertices.nbytes, self._center_vertices, GL_STATIC_DRAW)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self._ebo)
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, self._center_indices.nbytes, self._center_indices, GL_STATIC_DRAW)

        stride = 9 * 4
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, stride, None)
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(12))
        glEnableVertexAttribArray(1)
        glVertexAttribPointer(2, 3, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(24))
        glEnableVertexAttribArray(2)

        glDrawElements(GL_TRIANGLES, self._center_index_count, GL_UNSIGNED_INT, None)
        glBindVertexArray(0)
        glEnable(GL_DEPTH_TEST)

    def hit_test(self, mouse_pos: Tuple[int, int], gizmo_position: Vec3, gizmo_scale: float,
                 view_matrix: Mat4, projection_matrix: Mat4,
                 viewport: Tuple[int, int, int, int]) -> Optional[str]:
        """Test if the mouse is over one of the gizmo arrows or the center."""
        view_proj = projection_matrix * view_matrix

        center_screen_x, center_screen_y = self._project_to_screen(gizmo_position, view_proj, viewport)
        dx = mouse_pos[0] - center_screen_x
        dy = mouse_pos[1] - center_screen_y
        center_distance = math.sqrt(dx * dx + dy * dy)

        ring_outer_radius = self.CENTER_RING_RADIUS * gizmo_scale
        ring_thickness = self.CENTER_RING_THICKNESS * gizmo_scale
        ring_screen_radius = ring_outer_radius * 100
        ring_inner_radius = (ring_outer_radius - ring_thickness) * 100

        outer_tolerance = ring_screen_radius + 15.0
        inner_tolerance = max(0, ring_inner_radius - 10.0)

        if center_distance < outer_tolerance and center_distance > inner_tolerance:
            arrow_tolerance = 10.0
            for axis in ['X', 'Y', 'Z']:
                distance = self._get_screen_distance_to_arrow(mouse_pos, axis, gizmo_position, gizmo_scale, view_proj, viewport)
                if distance < arrow_tolerance:
                    return axis
            return 'CENTER'

        if center_distance <= inner_tolerance:
            arrow_tolerance = 10.0
            for axis in ['X', 'Y', 'Z']:
                distance = self._get_screen_distance_to_arrow(mouse_pos, axis, gizmo_position, gizmo_scale, view_proj, viewport)
                if distance < arrow_tolerance:
                    return axis
            return 'CENTER'

        tolerance = 10.0
        best_axis = None
        best_distance = float('inf')

        for axis in ['X', 'Y', 'Z']:
            distance = self._get_screen_distance_to_arrow(mouse_pos, axis, gizmo_position, gizmo_scale, view_proj, viewport)
            if distance < tolerance and distance < best_distance:
                best_distance = distance
                best_axis = axis

        return best_axis

    def _get_screen_distance_to_arrow(self, mouse_pos: Tuple[int, int], axis: str,
                                       center: Vec3, scale: float, view_proj: Mat4,
                                       viewport: Tuple[int, int, int, int]) -> float:
        """Calculate the minimum screen-space distance from mouse to an arrow."""
        min_distance = float('inf')
        arrow_length = (self.SHAFT_LENGTH + self.HEAD_LENGTH) * scale

        for i in range(33):
            t = i / 32
            d = t * arrow_length

            if axis == 'X':
                point = Vec3(d, 0, 0)
            elif axis == 'Y':
                point = Vec3(0, d, 0)
            else:
                point = Vec3(0, 0, d)

            world_point = center + point
            screen_x, screen_y = self._project_to_screen(world_point, view_proj, viewport)

            dx = screen_x - mouse_pos[0]
            dy = screen_y - mouse_pos[1]
            distance = math.sqrt(dx * dx + dy * dy)
            min_distance = min(min_distance, distance)

        return min_distance

    def _project_to_screen(self, world_pos: Vec3, view_proj: Mat4,
                           viewport: Tuple[int, int, int, int]) -> Tuple[float, float]:
        """Project a world position to screen coordinates."""
        m = view_proj.to_list()
        x = m[0] * world_pos.x + m[4] * world_pos.y + m[8] * world_pos.z + m[12]
        y = m[1] * world_pos.x + m[5] * world_pos.y + m[9] * world_pos.z + m[13]
        w = m[3] * world_pos.x + m[7] * world_pos.y + m[11] * world_pos.z + m[15]

        if abs(w) < 1e-10:
            w = 1e-10

        ndc_x = x / w
        ndc_y = y / w

        screen_x = viewport[0] + (ndc_x + 1.0) * 0.5 * viewport[2]
        screen_y = viewport[1] + (1.0 - ndc_y) * 0.5 * viewport[3]

        return (screen_x, screen_y)

    def get_point_on_axis(self, mouse_pos: Tuple[int, int], axis: str, center: Vec3,
                          scale: float, view_matrix: Mat4, projection_matrix: Mat4,
                          viewport: Tuple[int, int, int, int]) -> Optional[Vec3]:
        """Get the world-space point on the axis line at the mouse position."""
        ndc_x = (2.0 * (mouse_pos[0] - viewport[0]) / viewport[2]) - 1.0
        ndc_y = 1.0 - (2.0 * (mouse_pos[1] - viewport[1]) / viewport[3])

        view_inv = self._inverse_matrix(view_matrix)
        proj_inv = self._inverse_matrix(projection_matrix)

        cam_pos = Vec3(view_inv[12], view_inv[13], view_inv[14])

        ray_clip = Vec3(ndc_x, ndc_y, -1.0)
        ray_view = Vec3(ray_clip.x / proj_inv[0], ray_clip.y / proj_inv[5], -1.0)

        ray_world = Vec3(
            view_inv[0] * ray_view.x + view_inv[4] * ray_view.y + view_inv[8] * ray_view.z,
            view_inv[1] * ray_view.x + view_inv[5] * ray_view.y + view_inv[9] * ray_view.z,
            view_inv[2] * ray_view.x + view_inv[6] * ray_view.y + view_inv[10] * ray_view.z
        )

        ray_len = math.sqrt(ray_world.x**2 + ray_world.y**2 + ray_world.z**2)
        if ray_len < 1e-10:
            return None
        ray_world = Vec3(ray_world.x / ray_len, ray_world.y / ray_len, ray_world.z / ray_len)

        if axis == 'X':
            axis_dir = Vec3(1, 0, 0)
        elif axis == 'Y':
            axis_dir = Vec3(0, 1, 0)
        else:
            axis_dir = Vec3(0, 0, 1)

        cross = Vec3(
            ray_world.y * axis_dir.z - ray_world.z * axis_dir.y,
            ray_world.z * axis_dir.x - ray_world.x * axis_dir.z,
            ray_world.x * axis_dir.y - ray_world.y * axis_dir.x
        )
        cross_len_sq = cross.x**2 + cross.y**2 + cross.z**2

        if cross_len_sq < 1e-10:
            return None

        diff = center - cam_pos
        denom = cross_len_sq
        s = ((diff.x * axis_dir.y * cross.z + diff.y * axis_dir.z * cross.x + diff.z * axis_dir.x * cross.y -
              diff.x * axis_dir.z * cross.y - diff.y * axis_dir.x * cross.z - diff.z * axis_dir.y * cross.x) / denom)

        ray_point = Vec3(cam_pos.x + s * ray_world.x, cam_pos.y + s * ray_world.y, cam_pos.z + s * ray_world.z)
        relative = ray_point - center
        t = relative.x * axis_dir.x + relative.y * axis_dir.y + relative.z * axis_dir.z

        return Vec3(center.x + t * axis_dir.x, center.y + t * axis_dir.y, center.z + t * axis_dir.z)

    def get_point_on_plane(self, mouse_pos: Tuple[int, int], center: Vec3,
                           view_matrix: Mat4, projection_matrix: Mat4,
                           viewport: Tuple[int, int, int, int]) -> Optional[Vec3]:
        """Get the world-space point on a camera-facing plane at the mouse position."""
        ndc_x = (2.0 * (mouse_pos[0] - viewport[0]) / viewport[2]) - 1.0
        ndc_y = 1.0 - (2.0 * (mouse_pos[1] - viewport[1]) / viewport[3])

        view_inv = self._inverse_matrix(view_matrix)
        proj_inv = self._inverse_matrix(projection_matrix)

        cam_pos = Vec3(view_inv[12], view_inv[13], view_inv[14])

        ray_clip = Vec3(ndc_x, ndc_y, -1.0)
        ray_view = Vec3(ray_clip.x / proj_inv[0], ray_clip.y / proj_inv[5], -1.0)

        ray_world = Vec3(
            view_inv[0] * ray_view.x + view_inv[4] * ray_view.y + view_inv[8] * ray_view.z,
            view_inv[1] * ray_view.x + view_inv[5] * ray_view.y + view_inv[9] * ray_view.z,
            view_inv[2] * ray_view.x + view_inv[6] * ray_view.y + view_inv[10] * ray_view.z
        )

        ray_len = math.sqrt(ray_world.x**2 + ray_world.y**2 + ray_world.z**2)
        if ray_len < 1e-10:
            return None
        ray_world = Vec3(ray_world.x / ray_len, ray_world.y / ray_len, ray_world.z / ray_len)

        plane_normal = Vec3(view_inv[8], view_inv[9], view_inv[10])
        plane_len = math.sqrt(plane_normal.x**2 + plane_normal.y**2 + plane_normal.z**2)
        if plane_len < 1e-10:
            return None
        plane_normal = Vec3(plane_normal.x / plane_len, plane_normal.y / plane_len, plane_normal.z / plane_len)

        denom = ray_world.x * plane_normal.x + ray_world.y * plane_normal.y + ray_world.z * plane_normal.z
        if abs(denom) < 1e-10:
            return None

        diff = center - cam_pos
        t = (diff.x * plane_normal.x + diff.y * plane_normal.y + diff.z * plane_normal.z) / denom

        return Vec3(cam_pos.x + t * ray_world.x, cam_pos.y + t * ray_world.y, cam_pos.z + t * ray_world.z)

    def _inverse_matrix(self, m: Mat4) -> List[float]:
        """Compute the inverse of a 4x4 matrix."""
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

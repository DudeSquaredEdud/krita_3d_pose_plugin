"""
Scale gizmo for 3D model scaling operations.

Renders cube handles for axis scaling and a center sphere for uniform scaling.
"""

import ctypes
import math
from typing import List, Optional, Tuple

import numpy as np
from OpenGL.GL import (
    GL_ARRAY_BUFFER, GL_ELEMENT_ARRAY_BUFFER, GL_FALSE, GL_FLOAT,
    GL_LEQUAL, GL_STATIC_DRAW, GL_TRIANGLES, GL_UNSIGNED_INT,
    glBlendFunc, glBufferData, glDeleteBuffers, glDeleteProgram,
    glDeleteVertexArrays, glDisable, glEnable, glDrawElements,
    glEnableVertexAttribArray, glGenBuffers, glGenVertexArrays,
    glGetUniformLocation, glUniform1f, glUniform3f, glUniformMatrix4fv,
    glUseProgram, glVertexAttribPointer, glBindVertexArray, glBindBuffer,
    GL_BLEND, GL_DEPTH_TEST, GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA
)
from OpenGL.GL import shaders

from ..mat4 import Mat4
from ..vec3 import Vec3
from .gizmo_base import GIZMO_VERTEX_SHADER, GIZMO_FRAGMENT_SHADER


class ScaleGizmo:
    """
    3D scale gizmo for model resizing.

    Renders three cube handles for non-uniform scaling along X, Y, and Z axes,
    plus a center sphere handle for uniform scaling.

    Usage:
        gizmo = ScaleGizmo()
        gizmo.initialize()

        # In render loop:
        gizmo.render(position, scale, view, proj, hovered_axis='X')

        # For hit testing:
        axis = gizmo.hit_test(mouse_pos, position, scale, view, proj, viewport)

        # For drag tracking:
        scale_delta = gizmo.get_scale_from_drag(start_pos, current_pos, axis, center)
    """

    # Default colors for each axis
    COLOR_X = (1.0, 0.2, 0.2)  # Red
    COLOR_Y = (0.2, 1.0, 0.2)  # Green
    COLOR_Z = (0.2, 0.2, 1.0)  # Blue

    # Highlight colors
    COLOR_HOVER = (1.0, 1.0, 0.2)  # Yellow
    COLOR_DRAG = (1.0, 0.8, 0.2)  # Orange-yellow

    # Uniform scale color
    COLOR_UNIFORM = (0.8, 0.8, 0.8)  # Light gray

    # Handle dimensions (relative to gizmo scale)
    CUBE_SIZE = 0.12  # Size of axis cube handles
    CUBE_OFFSET = 0.85  # Distance from center to cube handles
    SPHERE_RADIUS = 0.15  # Radius of center sphere for uniform scaling
    SPHERE_SEGMENTS = 16  # Segments for sphere

    def __init__(self, cube_segments: int = 6, sphere_segments: int = 16):
        """
        Create a scale gizmo.

        Args:
            cube_segments: Number of segments for cube faces
            sphere_segments: Number of segments for center sphere
        """
        self._cube_segments = cube_segments
        self._sphere_segments = sphere_segments

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

        # Vertex data for each axis cube (position, normal, color)
        self._x_vertices: np.ndarray = np.array([])
        self._y_vertices: np.ndarray = np.array([])
        self._z_vertices: np.ndarray = np.array([])

        # Index data for each cube
        self._x_indices: np.ndarray = np.array([])
        self._y_indices: np.ndarray = np.array([])
        self._z_indices: np.ndarray = np.array([])

        # Index counts for each cube
        self._x_index_count: int = 0
        self._y_index_count: int = 0
        self._z_index_count: int = 0

        # Vertex data for center sphere
        self._sphere_vertices: np.ndarray = np.array([])
        self._sphere_indices: np.ndarray = np.array([])
        self._sphere_index_count: int = 0

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
            # Compile shaders (reuse the same shaders as RotationGizmo)
            vertex_shader = shaders.compileShader(GIZMO_VERTEX_SHADER, shaders.GL_VERTEX_SHADER)
            fragment_shader = shaders.compileShader(GIZMO_FRAGMENT_SHADER, shaders.GL_FRAGMENT_SHADER)
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

            # Generate cube geometry for each axis
            self._x_vertices, self._x_indices, self._x_index_count = self._generate_cube_geometry('X', self.COLOR_X)
            self._y_vertices, self._y_indices, self._y_index_count = self._generate_cube_geometry('Y', self.COLOR_Y)
            self._z_vertices, self._z_indices, self._z_index_count = self._generate_cube_geometry('Z', self.COLOR_Z)

            # Generate center sphere geometry
            self._sphere_vertices, self._sphere_indices, self._sphere_index_count = self._generate_sphere_geometry(
                self.SPHERE_RADIUS, self.COLOR_UNIFORM
            )

            # Create VAO, VBO, and EBO
            self._vao = glGenVertexArrays(1)
            self._vbo = glGenBuffers(1)
            self._ebo = glGenBuffers(1)

            self._initialized = True
            return True

        except Exception as e:
            print(f"Failed to initialize scale gizmo: {e}")
            return False

    def _generate_cube_geometry(self, axis: str, color: Tuple[float, float, float]) -> Tuple[np.ndarray, np.ndarray, int]:
        """
        Generate vertex data for a cube positioned along the given axis.

        The cube is offset from the origin along its axis.

        Args:
            axis: 'X', 'Y', or 'Z' - the axis the cube is positioned along
            color: RGB color tuple for this cube

        Returns:
            Tuple of (NumPy array of vertex data, index array, index count)
            Vertex format: 9 floats per vertex (x, y, z, nx, ny, nz, r, g, b)
        """
        vertices = []
        indices = []

        size = self.CUBE_SIZE
        half = size / 2.0
        offset = self.CUBE_OFFSET

        # Define cube faces (6 faces, each with 4 vertices)
        # Face order: +X, -X, +Y, -Y, +Z, -Z
        face_normals = [
            (1, 0, 0), (-1, 0, 0),
            (0, 1, 0), (0, -1, 0),
            (0, 0, 1), (0, 0, -1)
        ]

        # Face vertices (4 corners per face)
        face_corners = [
            # +X face
            [(half, -half, -half), (half, half, -half), (half, half, half), (half, -half, half)],
            # -X face
            [(-half, -half, half), (-half, half, half), (-half, half, -half), (-half, -half, -half)],
            # +Y face
            [(-half, half, -half), (-half, half, half), (half, half, half), (half, half, -half)],
            # -Y face
            [(-half, -half, half), (-half, -half, -half), (half, -half, -half), (half, -half, half)],
            # +Z face
            [(-half, -half, half), (half, -half, half), (half, half, half), (-half, half, half)],
            # -Z face
            [(-half, -half, -half), (-half, half, -half), (half, half, -half), (half, -half, -half)]
        ]

        # Generate vertices for each face
        vertex_idx = 0
        for face_idx, (normal, corners) in enumerate(zip(face_normals, face_corners)):
            for corner in corners:
                # Apply axis offset
                x, y, z = corner
                if axis == 'X':
                    pos = (x + offset, y, z)
                    norm = normal
                elif axis == 'Y':
                    pos = (x, y + offset, z)
                    norm = normal
                else:  # Z
                    pos = (x, y, z + offset)
                    norm = normal

                vertices.extend([pos[0], pos[1], pos[2], norm[0], norm[1], norm[2], color[0], color[1], color[2]])

            # Two triangles per face
            base = vertex_idx
            indices.extend([base, base + 1, base + 2, base, base + 2, base + 3])
            vertex_idx += 4

        index_count = len(indices)
        vertices_array = np.array(vertices, dtype=np.float32)
        indices_array = np.array(indices, dtype=np.uint32)

        return vertices_array, indices_array, index_count

    def _generate_sphere_geometry(self, radius: float, color: Tuple[float, float, float]) -> Tuple[np.ndarray, np.ndarray, int]:
        """
        Generate vertex data for a sphere at the origin.

        Args:
            radius: Radius of the sphere
            color: RGB color tuple

        Returns:
            Tuple of (NumPy array of vertex data, index array, index count)
        """
        vertices = []
        indices = []

        segments = self._sphere_segments
        rings = segments

        # Generate vertices
        for ring in range(rings + 1):
            phi = math.pi * ring / rings  # Latitude angle (0 to pi)
            sin_phi = math.sin(phi)
            cos_phi = math.cos(phi)

            for seg in range(segments + 1):
                theta = 2 * math.pi * seg / segments  # Longitude angle (0 to 2pi)
                sin_theta = math.sin(theta)
                cos_theta = math.cos(theta)

                # Position
                x = radius * sin_phi * cos_theta
                y = radius * cos_phi
                z = radius * sin_phi * sin_theta

                # Normal (outward from center)
                nx = sin_phi * cos_theta
                ny = cos_phi
                nz = sin_phi * sin_theta

                vertices.extend([x, y, z, nx, ny, nz, color[0], color[1], color[2]])

        # Generate indices
        for ring in range(rings):
            for seg in range(segments):
                current = ring * (segments + 1) + seg
                next_ring = current + segments + 1

                # Two triangles per quad
                indices.extend([current, next_ring, current + 1])
                indices.extend([current + 1, next_ring, next_ring + 1])

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
        Render the scale gizmo.

        Args:
            position: World position of the gizmo center
            scale: Scale factor (typically based on camera distance)
            view_matrix: Camera view matrix
            projection_matrix: Camera projection matrix
            hovered_axis: Currently hovered axis ('X', 'Y', 'Z', 'UNIFORM', or None)
            dragging_axis: Currently dragging axis ('X', 'Y', 'Z', 'UNIFORM', or None)
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

        # Render each axis cube
        self._render_handle(self._x_vertices, self._x_indices, self._x_index_count, 'X', hovered_axis, dragging_axis)
        self._render_handle(self._y_vertices, self._y_indices, self._y_index_count, 'Y', hovered_axis, dragging_axis)
        self._render_handle(self._z_vertices, self._z_indices, self._z_index_count, 'Z', hovered_axis, dragging_axis)

        # Render center sphere
        self._render_sphere(position, scale, hovered_axis, dragging_axis)

    def _render_handle(
        self,
        vertices: np.ndarray,
        indices: np.ndarray,
        index_count: int,
        axis: str,
        hovered_axis: Optional[str],
        dragging_axis: Optional[str]
    ) -> None:
        """
        Render a single cube handle with appropriate highlighting.

        Args:
            vertices: Vertex data for this cube
            indices: Index data for this cube
            index_count: Number of indices to draw
            axis: Axis identifier ('X', 'Y', or 'Z')
            hovered_axis: Currently hovered axis
            dragging_axis: Currently dragging axis
        """
        # Disable depth testing so handles always appear on top
        glDisable(GL_DEPTH_TEST)

        # Determine color override and alpha based on state
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
            glUniform1f(self._u_alpha, 0.8)

        # Upload vertices and indices
        glBindVertexArray(self._vao)

        glBindBuffer(GL_ARRAY_BUFFER, self._vbo)
        glBufferData(GL_ARRAY_BUFFER, vertices.nbytes, vertices, GL_STATIC_DRAW)

        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self._ebo)
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, indices.nbytes, indices, GL_STATIC_DRAW)

        # Position attribute (location = 0)
        stride = 9 * 4
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, stride, None)
        glEnableVertexAttribArray(0)

        # Normal attribute (location = 1)
        glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(12))
        glEnableVertexAttribArray(1)

        # Color attribute (location = 2)
        glVertexAttribPointer(2, 3, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(24))
        glEnableVertexAttribArray(2)

        glDrawElements(GL_TRIANGLES, index_count, GL_UNSIGNED_INT, None)

        # Re-enable depth testing
        glEnable(GL_DEPTH_TEST)
        glBindVertexArray(0)

    def _render_sphere(
        self,
        position: Vec3,
        scale: float,
        hovered_axis: Optional[str],
        dragging_axis: Optional[str]
    ) -> None:
        """
        Render the center sphere handle for uniform scaling.

        Args:
            position: World position of the gizmo center
            scale: Scale factor
            hovered_axis: Currently hovered axis
            dragging_axis: Currently dragging axis
        """
        # Disable depth testing so sphere always appears on top
        glDisable(GL_DEPTH_TEST)

        # Determine color override and alpha based on state
        if dragging_axis == 'UNIFORM':
            glUniform3f(self._u_color_override, *self.COLOR_DRAG)
            glUniform1f(self._u_color_mix, 1.0)
            glUniform1f(self._u_alpha, 1.0)
        elif hovered_axis == 'UNIFORM':
            glUniform3f(self._u_color_override, *self.COLOR_HOVER)
            glUniform1f(self._u_color_mix, 0.7)
            glUniform1f(self._u_alpha, 0.95)
        else:
            glUniform1f(self._u_color_mix, 0.0)
            glUniform1f(self._u_alpha, 0.7)

        # Upload vertices and indices
        glBindVertexArray(self._vao)

        glBindBuffer(GL_ARRAY_BUFFER, self._vbo)
        glBufferData(GL_ARRAY_BUFFER, self._sphere_vertices.nbytes, self._sphere_vertices, GL_STATIC_DRAW)

        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self._ebo)
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, self._sphere_indices.nbytes, self._sphere_indices, GL_STATIC_DRAW)

        # Position attribute (location = 0)
        stride = 9 * 4
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, stride, None)
        glEnableVertexAttribArray(0)

        # Normal attribute (location = 1)
        glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(12))
        glEnableVertexAttribArray(1)

        # Color attribute (location = 2)
        glVertexAttribPointer(2, 3, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(24))
        glEnableVertexAttribArray(2)

        glDrawElements(GL_TRIANGLES, self._sphere_index_count, GL_UNSIGNED_INT, None)

        # Re-enable depth testing
        glEnable(GL_DEPTH_TEST)
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
        Test if the mouse is over one of the gizmo handles.

        Args:
            mouse_pos: (x, y) mouse position in window coordinates
            gizmo_position: World position of the gizmo center
            gizmo_scale: Scale factor of the gizmo
            view_matrix: Camera view matrix
            projection_matrix: Camera projection matrix
            viewport: (x, y, width, height) of the viewport

        Returns:
            'X', 'Y', 'Z' if hovering over that axis, 'UNIFORM' if over center, or None
        """
        # Calculate view-projection matrix
        view_proj = projection_matrix * view_matrix

        # Hit tolerance in screen pixels
        tolerance = 15.0

        # First check center sphere (uniform scale)
        center_screen_x, center_screen_y = self._project_to_screen(
            gizmo_position, view_proj, viewport
        )
        dx = mouse_pos[0] - center_screen_x
        dy = mouse_pos[1] - center_screen_y
        center_distance = math.sqrt(dx * dx + dy * dy)

        # Approximate screen-space sphere radius
        sphere_screen_radius = self.SPHERE_RADIUS * gizmo_scale * 100

        if center_distance < sphere_screen_radius:
            return 'UNIFORM'

        # Test each axis cube
        best_axis = None
        best_distance = float('inf')

        for axis in ['X', 'Y', 'Z']:
            distance = self._get_screen_distance_to_handle(
                mouse_pos, axis, gizmo_position, gizmo_scale,
                view_proj, viewport
            )

            if distance < tolerance and distance < best_distance:
                best_distance = distance
                best_axis = axis

        return best_axis

    def _get_screen_distance_to_handle(
        self,
        mouse_pos: Tuple[int, int],
        axis: str,
        center: Vec3,
        scale: float,
        view_proj: Mat4,
        viewport: Tuple[int, int, int, int]
    ) -> float:
        """
        Calculate the minimum screen-space distance from mouse to a cube handle.

        Args:
            mouse_pos: (x, y) mouse position
            axis: 'X', 'Y', or 'Z'
            center: World position of gizmo center
            scale: Scale factor
            view_proj: View-projection matrix
            viewport: Viewport bounds

        Returns:
            Minimum screen-space distance to the handle
        """
        min_distance = float('inf')

        # Handle position
        offset = self.CUBE_OFFSET * scale
        if axis == 'X':
            handle_pos = Vec3(offset, 0, 0)
        elif axis == 'Y':
            handle_pos = Vec3(0, offset, 0)
        else:  # Z
            handle_pos = Vec3(0, 0, offset)

        # Translate to gizmo position
        world_handle = center + handle_pos

        # Project handle center to screen
        screen_x, screen_y = self._project_to_screen(world_handle, view_proj, viewport)

        # Calculate distance to mouse
        dx = screen_x - mouse_pos[0]
        dy = screen_y - mouse_pos[1]
        distance = math.sqrt(dx * dx + dy * dy)

        return distance

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
        screen_y = viewport[1] + (1.0 - ndc_y) * 0.5 * viewport[3]

        return (screen_x, screen_y)

    def get_scale_from_drag(
        self,
        drag_start_world: Vec3,
        drag_current_world: Vec3,
        axis: str,
        center: Vec3,
        initial_scale: Vec3
    ) -> Vec3:
        """
        Calculate the scale delta from drag motion.

        For axis handles, scales along that axis.
        For uniform scaling, scales all axes equally.

        Args:
            drag_start_world: Initial hit point in world space when drag starts
            drag_current_world: Current point in world space during drag
            axis: 'X', 'Y', 'Z', or 'UNIFORM'
            center: Center of the gizmo (model position)
            initial_scale: The initial scale before dragging

        Returns:
            Vec3 with the new scale values
        """
        # Calculate drag distance
        start_offset = drag_start_world - center
        current_offset = drag_current_world - center

        if axis == 'UNIFORM':
            # Uniform scaling: use distance from center
            start_dist = start_offset.length()
            current_dist = current_offset.length()

            if start_dist < 0.001:
                return initial_scale

            scale_factor = current_dist / start_dist

            # Apply scale factor to all axes
            return Vec3(
                initial_scale.x * scale_factor,
                initial_scale.y * scale_factor,
                initial_scale.z * scale_factor
            )
        else:
            # Axis scaling: use component along that axis
            if axis == 'X':
                start_component = abs(start_offset.x)
                current_component = abs(current_offset.x)
                idx = 0
            elif axis == 'Y':
                start_component = abs(start_offset.y)
                current_component = abs(current_offset.y)
                idx = 1
            else:  # Z
                start_component = abs(start_offset.z)
                current_component = abs(current_offset.z)
                idx = 2

            if start_component < 0.001:
                return initial_scale

            scale_factor = current_component / start_component

            # Apply scale factor to the specific axis
            new_scale = [initial_scale.x, initial_scale.y, initial_scale.z]
            new_scale[idx] = initial_scale.x * scale_factor if idx == 0 else (
                initial_scale.y * scale_factor if idx == 1 else initial_scale.z * scale_factor
            )

            return Vec3(new_scale[0], new_scale[1], new_scale[2])

    def get_point_on_axis(
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
        Get the world-space point on the axis line at the mouse position.

        This is used during dragging to track the current position along
        the scale axis.

        Args:
            mouse_pos: (x, y) mouse position
            axis: 'X', 'Y', 'Z', or 'UNIFORM'
            center: World position of gizmo center
            scale: Scale factor
            view_matrix: Camera view matrix
            projection_matrix: Camera projection matrix
            viewport: Viewport bounds

        Returns:
            World-space point on the axis line, or None if invalid
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

        if axis == 'UNIFORM':
            # For uniform scaling, use a camera-facing plane through the center
            # Plane normal is the camera forward direction
            plane_normal = Vec3(view_inv[8], view_inv[9], view_inv[10])
            plane_len = math.sqrt(plane_normal.x**2 + plane_normal.y**2 + plane_normal.z**2)
            if plane_len < 1e-10:
                return None
            plane_normal = Vec3(plane_normal.x / plane_len, plane_normal.y / plane_len, plane_normal.z / plane_len)

            # Ray-plane intersection
            denom = ray_world.x * plane_normal.x + ray_world.y * plane_normal.y + ray_world.z * plane_normal.z
            if abs(denom) < 1e-10:
                return None

            diff = center - cam_pos
            t = (diff.x * plane_normal.x + diff.y * plane_normal.y + diff.z * plane_normal.z) / denom

            return Vec3(
                cam_pos.x + t * ray_world.x,
                cam_pos.y + t * ray_world.y,
                cam_pos.z + t * ray_world.z
            )
        else:
            # Get the axis direction
            if axis == 'X':
                axis_dir = Vec3(1, 0, 0)
            elif axis == 'Y':
                axis_dir = Vec3(0, 1, 0)
            else:  # Z
                axis_dir = Vec3(0, 0, 1)

            # Find closest point on axis line to ray
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

            ray_point = Vec3(
                cam_pos.x + s * ray_world.x,
                cam_pos.y + s * ray_world.y,
                cam_pos.z + s * ray_world.z
            )

            relative = ray_point - center
            t = relative.x * axis_dir.x + relative.y * axis_dir.y + relative.z * axis_dir.z

            return Vec3(
                center.x + t * axis_dir.x,
                center.y + t * axis_dir.y,
                center.z + t * axis_dir.z
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

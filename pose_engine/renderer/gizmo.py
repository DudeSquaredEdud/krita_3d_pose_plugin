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


# Vertex shader for gizmo torus with lighting
GIZMO_VERTEX_SHADER = """
#version 330 core

layout(location = 0) in vec3 a_position;
layout(location = 1) in vec3 a_normal;
layout(location = 2) in vec3 a_color;

out vec3 v_color;
out vec3 v_normal;
out vec3 v_world_pos;

uniform mat4 u_model;
uniform mat4 u_view;
uniform mat4 u_projection;

void main() {
    v_color = a_color;
    v_normal = mat3(u_model) * a_normal;  // Transform normal to world space
    v_world_pos = (u_model * vec4(a_position, 1.0)).xyz;
    gl_Position = u_projection * u_view * u_model * vec4(a_position, 1.0);
}
"""

# Fragment shader for gizmo torus with lighting
GIZMO_FRAGMENT_SHADER = """
#version 330 core

in vec3 v_color;
in vec3 v_normal;
in vec3 v_world_pos;

out vec4 frag_color;

uniform vec3 u_color_override;
uniform float u_color_mix;
uniform vec3 u_light_dir;  // Directional light direction (world space)
uniform float u_ambient;
uniform float u_alpha;

void main() {
    vec3 color = mix(v_color, u_color_override, u_color_mix);
    
    // Simple diffuse lighting
    vec3 normal = normalize(v_normal);
    float diffuse = max(dot(normal, normalize(u_light_dir)), 0.0);
    float lighting = u_ambient + (1.0 - u_ambient) * diffuse;
    
    // Add slight rim lighting for better 3D perception
    vec3 view_dir = normalize(-v_world_pos);
    float rim = 1.0 - max(dot(view_dir, normal), 0.0);
    rim = pow(rim, 2.0) * 0.3;
    
    vec3 final_color = color * lighting + vec3(1.0) * rim;
    frag_color = vec4(final_color, u_alpha);
}
"""


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
    
    # Default colors for each axis
    COLOR_X = (1.0, 0.2, 0.2)  # Red
    COLOR_Y = (0.2, 1.0, 0.2)  # Green
    COLOR_Z = (0.2, 0.2, 1.0)  # Blue
    
    # Highlight colors
    COLOR_HOVER = (1.0, 1.0, 0.2)  # Yellow
    COLOR_DRAG = (1.0, 0.8, 0.2)   # Orange-yellow
    
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
    
    def _generate_torus_vertices(self, axis: str, color: Tuple[float, float, float]) -> Tuple[np.ndarray, int]:
        """
        Generate vertex data for a torus in the plane perpendicular to the given axis.

        Each vertex has position (x, y, z), normal (nx, ny, nz), and color (r, g, b).
        Uses triangle strips for efficient rendering.

        Args:
            axis: 'X', 'Y', or 'Z' - the axis the torus rotates around
            color: RGB color tuple for this torus

        Returns:
            Tuple of (NumPy array of vertex data, index count for drawing)
            Vertex format: 9 floats per vertex (x, y, z, nx, ny, nz, r, g, b)
        """
        vertices = []
        indices = []
        
        major_radius = self._radius
        minor_radius = self._tube_radius
        major_segments = self._segments
        minor_segments = self._tube_segments

        # Generate vertices for the torus
        # The torus is parameterized by two angles:
        # - u: angle around the main circle (major radius)
        # - v: angle around the tube cross-section (minor radius)
        
        for i in range(major_segments + 1):
            u = (i / major_segments) * 2 * math.pi
            
            for j in range(minor_segments + 1):
                v = (j / minor_segments) * 2 * math.pi
                
                # Calculate position on torus surface
                # Standard torus parametric equations:
                # x = (R + r*cos(v)) * cos(u)
                # y = (R + r*cos(v)) * sin(u)
                # z = r * sin(v)
                #
                # But we need to orient based on axis:
                # - X axis: torus in YZ plane (rotation around X)
                # - Y axis: torus in XZ plane (rotation around Y)
                # - Z axis: torus in XY plane (rotation around Z)
                
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
        # Light from upper-right-front direction
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
        glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(12))  # offset = 3 floats * 4 bytes
        glEnableVertexAttribArray(1)

        # Color attribute (location = 2)
        glVertexAttribPointer(2, 3, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(24))  # offset = 6 floats * 4 bytes
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
            screen_x, screen_y = self._project_to_screen(
                world_point, view_proj, viewport
            )
            
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
    
    def get_rotation_from_drag(
        self,
        drag_start_world: Vec3,  # Initial hit point in world space when drag starts
        drag_current_world: Vec3,  # Current point in world space during drag
        axis: str,  # Rotation axis ('X', 'Y', or 'Z')
        center: Vec3  # Center of the gizmo (bone position)
    ) -> Quat:
        """
        Calculate the rotation quaternion from drag motion.
        
        This computes the rotation around the given axis based on the
        angular difference between the start and current drag positions.
        
        Args:
            drag_start_world: Initial hit point in world space
            drag_current_world: Current point in world space (on the circle plane)
            axis: 'X', 'Y', or 'Z'
            center: Center of the gizmo (bone position)
            
        Returns:
            Quaternion representing the rotation delta
        """
        # Get the rotation axis vector based on the specified axis
        if axis == 'X':
            axis_vec = Vec3(1, 0, 0)  # X-axis unit vector
        elif axis == 'Y':
            axis_vec = Vec3(0, 1, 0)  # Y-axis unit vector
        else:  # Z
            axis_vec = Vec3(0, 0, 1)  # Z-axis unit vector
        
        # Project start and current onto the plane perpendicular to the axis
        # (remove component along the axis)
        def project_to_plane(point: Vec3, axis: Vec3, center: Vec3) -> Vec3:
            relative = point - center
            # Remove component along axis
            dot = relative.x * axis.x + relative.y * axis.y + relative.z * axis.z
            return Vec3(
                relative.x - dot * axis.x,
                relative.y - dot * axis.y,
                relative.z - dot * axis.z
            )
        
        v1 = project_to_plane(drag_start_world, axis_vec, center)
        v2 = project_to_plane(drag_current_world, axis_vec, center)
    
        # Normalize
        len1 = v1.length()
        len2 = v2.length()
    
        # Use a more reasonable threshold - if vectors are too short, we can't
        # reliably calculate rotation, but don't just return identity
        # Instead, use a fallback based on the signed angle in 2D
        min_len = 0.001  # More reasonable minimum length threshold
    
        if len1 < min_len or len2 < min_len:
            # Can't calculate rotation from near-zero vectors
            return Quat.identity()
    
        v1 = Vec3(v1.x / len1, v1.y / len1, v1.z / len1)
        v2 = Vec3(v2.x / len2, v2.y / len2, v2.z / len2)
    
        # Calculate the signed angle between v1 and v2 around the axis
        # Using atan2 for full 360-degree rotation support without gimbal issues
        
        # Cross product gives us the perpendicular vector and its magnitude relates to sin(angle)
        cross = Vec3(
            v1.y * v2.z - v1.z * v2.y,
            v1.z * v2.x - v1.x * v2.z,
            v1.x * v2.y - v1.y * v2.x
        )
    
        # Dot product gives us cos(angle)
        dot = v1.x * v2.x + v1.y * v2.y + v1.z * v2.z
    
        # The signed angle: project cross product onto the rotation axis to get sign
        # atan2(sin_component, cos_component) gives us the angle in [-pi, pi]
        axis_dot = cross.x * axis_vec.x + cross.y * axis_vec.y + cross.z * axis_vec.z
        
        # Clamp dot to valid range for numerical stability
        dot = max(-1.0, min(1.0, dot))
        
        angle = math.atan2(axis_dot, dot)
    
        # Convert to degrees and create quaternion
        angle_deg = math.degrees(angle)*1.5
        return Quat.from_axis_angle_degrees(axis_vec, angle_deg)
    
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
        # Start with ray in clip space
        ray_clip = Vec3(ndc_x, ndc_y, -1.0)
        
        # Transform to view space
        # (simplified: just apply inverse projection)
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
        # plane equation: (P - center) · normal = 0
        # ray equation: P = cam_pos + t * ray_dir
        denom = ray_world.x * plane_normal.x + ray_world.y * plane_normal.y + ray_world.z * plane_normal.z
        
        if abs(denom) < 1e-10:
            # Ray parallel to plane
            return None
        
        t = ((center.x - cam_pos.x) * plane_normal.x + 
             (center.y - cam_pos.y) * plane_normal.y + 
             (center.z - cam_pos.z) * plane_normal.z) / denom
        
        if t < 0:
            # Behind camera
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
        
        Simplified for view/projection matrices.
        
        Args:
            m: Mat4 matrix
            
        Returns:
            List of 16 floats representing the inverse matrix
        """
        data = m.to_list()
        
        # For orthogonal/view matrices, we can use transpose of rotation
        # For projection matrices, we need full inverse
        # Using numpy for simplicity
        arr = np.array(data).reshape(4, 4)
        try:
            inv = np.linalg.inv(arr)
            return inv.flatten().tolist()
        except np.linalg.LinAlgError:
            # Return identity if singular
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


# -----------------------------------------------------------------------------
# Movement Gizmo - Translation Arrow Widget
# -----------------------------------------------------------------------------

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
    COLOR_DRAG = (1.0, 0.8, 0.2)   # Orange-yellow

    # Arrow dimensions (relative to gizmo scale)
    SHAFT_LENGTH = 0.7 # Length of the cylinder shaft
    SHAFT_RADIUS = 0.03 # Radius of the shaft
    HEAD_LENGTH = 0.3 # Length of the cone head
    HEAD_RADIUS = 0.08 # Base radius of the cone

    # Center ring dimensions (ring that faces the camera)
    CENTER_RING_RADIUS = 0.1 # Outer radius of the center ring
    CENTER_RING_THICKNESS = 0.02 # Thickness of the ring (tube radius)
    CENTER_COLOR = (0.8, 0.8, 0.8) # Light gray for center

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
            # Compile shaders (reuse the same shaders as RotationGizmo)
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

            # Generate center ring geometry (flat torus in XY plane, will be billboarded to face camera)
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

        Each arrow consists of:
        - A cylinder shaft
        - A cone head at the tip

        Args:
            axis: 'X', 'Y', or 'Z' - the axis the arrow points along
            color: RGB color tuple for this arrow

        Returns:
            Tuple of (NumPy array of vertex data, index array, index count)
            Vertex format: 9 floats per vertex (x, y, z, nx, ny, nz, r, g, b)
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
        # The shaft goes from 0 to shaft_length along the axis
        vertex_offset = 0

        # Shaft vertices (two rings: bottom and top)
        for ring in range(2):  # 0 = bottom, 1 = top
            y = ring * shaft_length
            for i in range(shaft_segments):
                angle = (i / shaft_segments) * 2 * math.pi
                x = shaft_radius * math.cos(angle)
                z = shaft_radius * math.sin(angle)

                # Normal points outward from the cylinder surface
                nx = math.cos(angle)
                nz = math.sin(angle)
                ny = 0.0

                # Transform based on axis
                pos, norm = self._transform_for_axis(axis, x, y, z, nx, ny, nz)

                # Add vertex: position, normal, color
                vertices.extend([pos[0], pos[1], pos[2], norm[0], norm[1], norm[2], color[0], color[1], color[2]])

        # Shaft indices (triangle strip between rings)
        for i in range(shaft_segments):
            v0 = i                    # bottom ring
            v1 = i + shaft_segments   # top ring
            v2 = (i + 1) % shaft_segments  # next on bottom
            v3 = (i + 1) % shaft_segments + shaft_segments  # next on top

            # Two triangles per quad
            indices.extend([v0, v2, v1, v2, v3, v1])

        vertex_offset = 2 * shaft_segments

        # Shaft cap (bottom circle)
        cap_center_idx = vertex_offset
        # Center vertex
        pos, norm = self._transform_for_axis(axis, 0, 0, 0, 0, -1, 0)
        vertices.extend([pos[0], pos[1], pos[2], norm[0], norm[1], norm[2], color[0], color[1], color[2]])
        vertex_offset += 1

        # Cap ring vertices
        for i in range(shaft_segments):
            angle = (i / shaft_segments) * 2 * math.pi
            x = shaft_radius * math.cos(angle)
            z = shaft_radius * math.sin(angle)

            pos, norm = self._transform_for_axis(axis, x, 0, z, 0, -1, 0)
            vertices.extend([pos[0], pos[1], pos[2], norm[0], norm[1], norm[2], color[0], color[1], color[2]])

        # Cap indices (fan)
        for i in range(shaft_segments):
            indices.extend([cap_center_idx, cap_center_idx + 1 + i, cap_center_idx + 1 + ((i + 1) % shaft_segments)])

        vertex_offset = cap_center_idx + 1 + shaft_segments

        # Generate cone head (starts at shaft_length, ends at shaft_length + head_length)
        cone_base_y = shaft_length
        cone_tip_y = shaft_length + head_length

        # Cone vertices (base ring + tip)
        # Base ring
        for i in range(head_segments):
            angle = (i / head_segments) * 2 * math.pi
            x = head_radius * math.cos(angle)
            z = head_radius * math.sin(angle)

            # Calculate normal for cone surface
            # The normal points outward at an angle
            slope = head_radius / head_length
            nx = math.cos(angle)
            nz = math.sin(angle)
            ny = slope  # Normal has upward component
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

        # Base ring vertices (already created above, but we need them again with downward normal)
        for i in range(head_segments):
            angle = (i / head_segments) * 2 * math.pi
            x = head_radius * math.cos(angle)
            z = head_radius * math.sin(angle)

            pos, norm = self._transform_for_axis(axis, x, cone_base_y, z, 0, -1, 0)
            vertices.extend([pos[0], pos[1], pos[2], norm[0], norm[1], norm[2], color[0], color[1], color[2]])

        # Base cap indices (fan)
        for i in range(head_segments):
            indices.extend([base_center_idx, base_center_idx + 1 + ((i + 1) % head_segments), base_center_idx + 1 + i])

        index_count = len(indices)
        vertices_array = np.array(vertices, dtype=np.float32)
        indices_array = np.array(indices, dtype=np.uint32)

        return vertices_array, indices_array, index_count

    def _transform_for_axis(self, axis: str, x: float, y: float, z: float, nx: float, ny: float, nz: float) -> Tuple[Tuple[float, float, float], Tuple[float, float, float]]:
        """
        Transform position and normal from Y-axis arrow to the specified axis.

        Args:
            axis: 'X', 'Y', or 'Z'
            x, y, z: Position components (Y-axis arrow)
            nx, ny, nz: Normal components

        Returns:
            Tuple of (position, normal) tuples
        """
        if axis == 'X':
            # Arrow points along X: swap X and Y
            return (y, x, z), (ny, nx, nz)
        elif axis == 'Y':
            # Arrow points along Y: no change
            return (x, y, z), (nx, ny, nz)
        else: # Z
            # Arrow points along Z: swap Y and Z
            return (x, z, y), (nx, nz, ny)

    def _generate_ring_geometry(self, radius: float, thickness: float, color: Tuple[float, float, float]) -> Tuple[np.ndarray, np.ndarray, int]:
        """
        Generate vertex data for a flat ring (torus) in the XY plane.

        This ring will be billboarded to always face the camera.

        Args:
            radius: Outer radius of the ring (center of the tube)
            thickness: Radius of the tube (thickness of the ring)
            color: RGB color tuple

        Returns:
            Tuple of (NumPy array of vertex data, index array, index count)
        """
        vertices = []
        indices = []

        segments = self._ring_segments
        tube_segments = 16  # Segments around the tube cross-section

        # Generate vertices for a torus
        # The torus lies in the XY plane (Z is the axis)
        for i in range(segments + 1):
            u = 2 * math.pi * i / segments  # Angle around the ring
            cos_u = math.cos(u)
            sin_u = math.sin(u)

            for j in range(tube_segments + 1):
                v = 2 * math.pi * j / tube_segments  # Angle around the tube
                cos_v = math.cos(v)
                sin_v = math.sin(v)

                # Position on torus surface
                x = (radius + thickness * cos_v) * cos_u
                y = (radius + thickness * cos_v) * sin_u
                z = thickness * sin_v

                # Normal points outward from the tube center
                nx = cos_v * cos_u
                ny = cos_v * sin_u
                nz = sin_v

                vertices.extend([x, y, z, nx, ny, nz, color[0], color[1], color[2]])

        # Generate indices
        for i in range(segments):
            for j in range(tube_segments):
                current = i * (tube_segments + 1) + j
                next_i = current + tube_segments + 1

                # Two triangles per quad
                indices.extend([current, next_i, current + 1])
                indices.extend([current + 1, next_i, next_i + 1])

        return (
            np.array(vertices, dtype=np.float32),
            np.array(indices, dtype=np.uint32),
            len(indices)
        )

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
        Render the movement gizmo.

        Args:
            position: World position of the gizmo center
            scale: Scale factor (typically based on camera distance)
            view_matrix: Camera view matrix
            projection_matrix: Camera projection matrix
            hovered_axis: Currently hovered axis ('X', 'Y', 'Z', 'CENTER', or None)
            dragging_axis: Currently dragging axis ('X', 'Y', 'Z', 'CENTER', or None)
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

        # Render each axis arrow
        self._render_arrow(self._x_vertices, self._x_indices, self._x_index_count, 'X', hovered_axis, dragging_axis)
        self._render_arrow(self._y_vertices, self._y_indices, self._y_index_count, 'Y', hovered_axis, dragging_axis)
        self._render_arrow(self._z_vertices, self._z_indices, self._z_index_count, 'Z', hovered_axis, dragging_axis)

        # Render center ring (billboarded to face camera)
        self._render_center_ring(position, scale, view_matrix, hovered_axis, dragging_axis)

    def _render_arrow(
        self,
        vertices: np.ndarray,
        indices: np.ndarray,
        index_count: int,
        axis: str,
        hovered_axis: Optional[str],
        dragging_axis: Optional[str]
    ) -> None:
        """
        Render a single arrow with appropriate highlighting.

        Args:
            vertices: Vertex data for this arrow
            indices: Index data for this arrow
            index_count: Number of indices to draw
            axis: Axis identifier ('X', 'Y', or 'Z')
            hovered_axis: Currently hovered axis
            dragging_axis: Currently dragging axis
        """
        # Disable depth testing so the arrow always appears on top
        glDisable(GL_DEPTH_TEST)

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
        glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(12))  # offset = 3 floats * 4 bytes
        glEnableVertexAttribArray(1)

        # Color attribute (location = 2)
        glVertexAttribPointer(2, 3, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(24))  # offset = 6 floats * 4 bytes
        glEnableVertexAttribArray(2)

        # Draw the arrow
        glDrawElements(GL_TRIANGLES, index_count, GL_UNSIGNED_INT, None)

        # Re-enable depth testing for subsequent rendering
        glEnable(GL_DEPTH_TEST)

        glBindVertexArray(0)

    def _render_center_ring(
        self,
        position: Vec3,
        scale: float,
        view_matrix: Mat4,
        hovered_axis: Optional[str],
        dragging_axis: Optional[str]
    ) -> None:
        """
        Render the center ring with appropriate highlighting.

        The ring is billboarded to always face the camera, and rendered
        without depth testing so it always appears on top of the model.

        Args:
            position: World position of the gizmo center
            scale: Scale factor
            view_matrix: Camera view matrix (for billboarding)
            hovered_axis: Currently hovered axis
            dragging_axis: Currently dragging axis
        """
        # Disable depth testing so the center ring always appears on top
        glDisable(GL_DEPTH_TEST)

        # Determine color override and alpha based on state
        if dragging_axis == 'CENTER':
            # Dragging the center - fully opaque, bright color
            glUniform3f(self._u_color_override, *self.COLOR_DRAG)
            glUniform1f(self._u_color_mix, 1.0)
            glUniform1f(self._u_alpha, 1.0)
        elif hovered_axis == 'CENTER':
            # Hovering the center - slightly transparent, highlighted color
            glUniform3f(self._u_color_override, *self.COLOR_HOVER)
            glUniform1f(self._u_color_mix, 0.7)
            glUniform1f(self._u_alpha, 0.95)
        else:
            # No highlight - semi-transparent for depth perception
            glUniform1f(self._u_color_mix, 0.0)
            glUniform1f(self._u_alpha, 0.8)

        # Create billboard matrix: extract rotation from view matrix and invert it
        # This makes the ring always face the camera
        view_list = view_matrix.to_list()

        # Extract the 3x3 rotation part of the view matrix and transpose it
        # (transpose = inverse for rotation matrices)
        # View matrix has camera orientation, we want the opposite
        billboard_rot = [
            view_list[0], view_list[4], view_list[8], 0,
            view_list[1], view_list[5], view_list[9], 0,
            view_list[2], view_list[6], view_list[10], 0,
            0, 0, 0, 1
        ]

        # Create model matrix: scale * billboard_rotation * translation
        # First scale, then rotate to face camera, then translate
        model_matrix = Mat4([
            scale * billboard_rot[0], scale * billboard_rot[1], scale * billboard_rot[2], 0,
            scale * billboard_rot[4], scale * billboard_rot[5], scale * billboard_rot[6], 0,
            scale * billboard_rot[8], scale * billboard_rot[9], scale * billboard_rot[10], 0,
            position.x, position.y, position.z, 1
        ])

        # Update model matrix uniform for this ring
        glUniformMatrix4fv(self._u_model, 1, GL_FALSE, model_matrix.to_list())

        # Upload vertices and indices
        glBindVertexArray(self._vao)

        # Upload vertex data
        glBindBuffer(GL_ARRAY_BUFFER, self._vbo)
        glBufferData(GL_ARRAY_BUFFER, self._center_vertices.nbytes, self._center_vertices, GL_STATIC_DRAW)

        # Upload index data
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self._ebo)
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, self._center_indices.nbytes, self._center_indices, GL_STATIC_DRAW)

        # Position attribute (location = 0)
        stride = 9 * 4 # 9 floats per vertex * 4 bytes per float
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, stride, None)
        glEnableVertexAttribArray(0)

        # Normal attribute (location = 1)
        glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(12)) # offset = 3 floats * 4 bytes
        glEnableVertexAttribArray(1)

        # Color attribute (location = 2)
        glVertexAttribPointer(2, 3, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(24)) # offset = 6 floats * 4 bytes
        glEnableVertexAttribArray(2)

        # Draw the ring
        glDrawElements(GL_TRIANGLES, self._center_index_count, GL_UNSIGNED_INT, None)

        glBindVertexArray(0)

        # Re-enable depth testing for subsequent rendering
        glEnable(GL_DEPTH_TEST)

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
        Test if the mouse is over one of the gizmo arrows or the center.

        Uses ray-cylinder intersection for each arrow shaft and cone.
        Also tests for center hit zone for free movement.

        Args:
            mouse_pos: (x, y) mouse position in window coordinates
            gizmo_position: World position of the gizmo center
            gizmo_scale: Scale factor of the gizmo
            view_matrix: Camera view matrix
            projection_matrix: Camera projection matrix
            viewport: (x, y, width, height) of the viewport

        Returns:
            'X', 'Y', 'Z' if hovering over that axis, 'CENTER' if over center, or None
        """
        # Calculate view-projection matrix
        view_proj = projection_matrix * view_matrix

        # First, check if we're over the center ring (for free movement)
        center_screen_x, center_screen_y = self._project_to_screen(
            gizmo_position, view_proj, viewport
        )
        dx = mouse_pos[0] - center_screen_x
        dy = mouse_pos[1] - center_screen_y
        center_distance = math.sqrt(dx * dx + dy * dy)

        # Calculate ring radius in screen pixels
        # Project a point at ring radius distance to get screen-space size
        ring_outer_radius = self.CENTER_RING_RADIUS * gizmo_scale
        ring_thickness = self.CENTER_RING_THICKNESS * gizmo_scale

        # Approximate screen-space ring radius by projecting a point
        # We use a simple approximation based on the gizmo scale
        # The ring should be clickable within its outer radius + some tolerance
        ring_screen_radius = ring_outer_radius * 100  # Approximate scaling factor
        ring_inner_radius = (ring_outer_radius - ring_thickness) * 100

        # Center hit zone: within the ring area (between inner and outer radius)
        # with some tolerance for easier clicking
        outer_tolerance = ring_screen_radius + 15.0
        inner_tolerance = max(0, ring_inner_radius - 10.0)

        # If we're within the ring area, check if we're not on an arrow
        if center_distance < outer_tolerance and center_distance > inner_tolerance:
            # Check arrows - if we're on an arrow, prefer that
            arrow_tolerance = 10.0
            for axis in ['X', 'Y', 'Z']:
                distance = self._get_screen_distance_to_arrow(
                    mouse_pos, axis, gizmo_position, gizmo_scale,
                    view_proj, viewport
                )
                if distance < arrow_tolerance:
                    return axis # On an arrow, return that

            # Not on an arrow but within ring area - return center
            return 'CENTER'

        # Also check if we're very close to center (inside the ring hole)
        # for easier clicking - allow clicking inside the ring too
        if center_distance <= inner_tolerance:
            # Check arrows - if we're on an arrow, prefer that
            arrow_tolerance = 10.0
            for axis in ['X', 'Y', 'Z']:
                distance = self._get_screen_distance_to_arrow(
                    mouse_pos, axis, gizmo_position, gizmo_scale,
                    view_proj, viewport
                )
                if distance < arrow_tolerance:
                    return axis # On an arrow, return that

            # Inside the ring - also return center
            return 'CENTER'

        # Hit tolerance in screen pixels for arrows
        tolerance = 10.0

        # Test each axis
        best_axis = None
        best_distance = float('inf')

        for axis in ['X', 'Y', 'Z']:
            distance = self._get_screen_distance_to_arrow(
                mouse_pos, axis, gizmo_position, gizmo_scale,
                view_proj, viewport
            )

            if distance < tolerance and distance < best_distance:
                best_distance = distance
                best_axis = axis

        return best_axis

    def _get_screen_distance_to_arrow(
        self,
        mouse_pos: Tuple[int, int],
        axis: str,
        center: Vec3,
        scale: float,
        view_proj: Mat4,
        viewport: Tuple[int, int, int, int]
    ) -> float:
        """
        Calculate the minimum screen-space distance from mouse to an arrow.

        Args:
            mouse_pos: (x, y) mouse position
            axis: 'X', 'Y', or 'Z'
            center: World position of gizmo center
            scale: Scale factor
            view_proj: View-projection matrix
            viewport: Viewport bounds

        Returns:
            Minimum screen-space distance to the arrow
        """
        min_distance = float('inf')

        # Arrow length (shaft + head)
        arrow_length = (self.SHAFT_LENGTH + self.HEAD_LENGTH) * scale

        # Sample points along the arrow
        num_samples = 32
        for i in range(num_samples + 1):
            t = i / num_samples
            # Distance along the arrow (0 to arrow_length)
            d = t * arrow_length

            # Get point on arrow in world space
            if axis == 'X':
                point = Vec3(d, 0, 0)
            elif axis == 'Y':
                point = Vec3(0, d, 0)
            else:  # Z
                point = Vec3(0, 0, d)

            # Translate to gizmo position
            world_point = center + point

            # Project to screen space
            screen_x, screen_y = self._project_to_screen(
                world_point, view_proj, viewport
            )

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
        the movement axis.

        Args:
            mouse_pos: (x, y) mouse position
            axis: 'X', 'Y', or 'Z'
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

        # Get the axis direction
        if axis == 'X':
            axis_dir = Vec3(1, 0, 0)
        elif axis == 'Y':
            axis_dir = Vec3(0, 1, 0)
        else:  # Z
            axis_dir = Vec3(0, 0, 1)

        # Find closest point on axis line to ray
        # Parametric axis line: P = center + t * axis_dir
        # We want to find t such that the distance from the ray to the line is minimized

        # Using the formula for closest point between two lines:
        # Line 1 (ray): P = cam_pos + s * ray_dir
        # Line 2 (axis): P = center + t * axis_dir

        # Cross product gives perpendicular direction
        cross = Vec3(
            ray_world.y * axis_dir.z - ray_world.z * axis_dir.y,
            ray_world.z * axis_dir.x - ray_world.x * axis_dir.z,
            ray_world.x * axis_dir.y - ray_world.y * axis_dir.x
        )
        cross_len_sq = cross.x**2 + cross.y**2 + cross.z**2

        if cross_len_sq < 1e-10:
            # Lines are parallel
            return None

        # Vector between line origins
        diff = center - cam_pos

        # Calculate parameters
        # Using Cramer's rule to solve for s and t
        denom = cross_len_sq
        s = ((diff.x * axis_dir.y * cross.z + diff.y * axis_dir.z * cross.x + diff.z * axis_dir.x * cross.y -
              diff.x * axis_dir.z * cross.y - diff.y * axis_dir.x * cross.z - diff.z * axis_dir.y * cross.x) / denom)

        # Point on ray closest to axis line
        ray_point = Vec3(
            cam_pos.x + s * ray_world.x,
            cam_pos.y + s * ray_world.y,
            cam_pos.z + s * ray_world.z
        )

        # Project onto axis line
        relative = ray_point - center
        t = relative.x * axis_dir.x + relative.y * axis_dir.y + relative.z * axis_dir.z

        # Return point on axis
        return Vec3(
            center.x + t * axis_dir.x,
            center.y + t * axis_dir.y,
            center.z + t * axis_dir.z
        )

    def get_point_on_plane(
        self,
        mouse_pos: Tuple[int, int],
        center: Vec3,
        view_matrix: Mat4,
        projection_matrix: Mat4,
        viewport: Tuple[int, int, int, int]
    ) -> Optional[Vec3]:
        """
        Get the world-space point on a camera-facing plane at the mouse position.

        This is used for free movement when clicking the center of the gizmo.
        The plane passes through the gizmo center and faces the camera.

        Args:
            mouse_pos: (x, y) mouse position
            center: World position of gizmo center (plane origin)
            view_matrix: Camera view matrix
            projection_matrix: Camera projection matrix
            viewport: Viewport bounds

        Returns:
            World-space point on the plane, or None if invalid
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

        # Plane normal is the camera forward direction (negative Z in view space)
        # In world space, this is the third column of the view matrix inverse
        plane_normal = Vec3(view_inv[8], view_inv[9], view_inv[10])
        plane_len = math.sqrt(plane_normal.x**2 + plane_normal.y**2 + plane_normal.z**2)
        if plane_len < 1e-10:
            return None
        plane_normal = Vec3(plane_normal.x / plane_len, plane_normal.y / plane_len, plane_normal.z / plane_len)

        # Ray-plane intersection
        # Plane equation: (P - center) · normal = 0
        # Ray equation: P = cam_pos + t * ray_world
        # Substitute: (cam_pos + t * ray_world - center) · normal = 0
        # Solve for t: t = (center - cam_pos) · normal / (ray_world · normal)

        denom = ray_world.x * plane_normal.x + ray_world.y * plane_normal.y + ray_world.z * plane_normal.z
        if abs(denom) < 1e-10:
            # Ray is parallel to the plane
            return None

        diff = center - cam_pos
        t = (diff.x * plane_normal.x + diff.y * plane_normal.y + diff.z * plane_normal.z) / denom

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


# -----------------------------------------------------------------------------
# Scale Gizmo - Model Resize Widget
# -----------------------------------------------------------------------------

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
    COLOR_DRAG = (1.0, 0.8, 0.2)   # Orange-yellow

    # Uniform scale color
    COLOR_UNIFORM = (0.8, 0.8, 0.8)  # Light gray

    # Handle dimensions (relative to gizmo scale)
    CUBE_SIZE = 0.12      # Size of axis cube handles
    CUBE_OFFSET = 0.85    # Distance from center to cube handles
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

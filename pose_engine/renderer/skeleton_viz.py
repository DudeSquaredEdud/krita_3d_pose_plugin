"""
Skeleton Visualizer - Draw Bone Hierarchy
========================================

Renders skeleton bones as lines/joints for debugging and posing.
"""

from typing import Optional, List, Tuple
from OpenGL.GL import *
import numpy as np

from ..vec3 import Vec3
from ..mat4 import Mat4
from ..skeleton import Skeleton
from ..bone import Bone


# Simple vertex shader for lines
LINE_VERTEX_SHADER = """
#version 330 core

layout(location = 0) in vec3 a_position;

uniform mat4 u_model;
uniform mat4 u_view;
uniform mat4 u_projection;

void main() {
    gl_Position = u_projection * u_view * u_model * vec4(a_position, 1.0);
}
"""

# Fragment shader for lines
LINE_FRAGMENT_SHADER = """
#version 330 core

out vec4 frag_color;

uniform vec3 u_color;

void main() {
    frag_color = vec4(u_color, 1.0);
}
"""


class SkeletonVisualizer:
    """
    Renders skeleton bones as lines and points.
    
    Usage:
        viz = SkeletonVisualizer()
        viz.initialize()
        
        # In render loop:
        viz.render(skeleton, view_matrix, projection_matrix)
    """
    
    def __init__(self):
        """Create a new skeleton visualizer."""
        self._program: Optional[int] = None
        self._vao: int = 0
        self._vbo: int = 0
        self._initialized: bool = False
        
        # Uniform locations
        self._u_model: int = -1
        self._u_view: int = -1
        self._u_projection: int = -1
        self._u_color: int = -1
        
        # Cached line data
        self._line_vertices: List[float] = []
        self._line_count: int = 0
    
    def initialize(self) -> bool:
        """
        Initialize the visualizer.
        
        Must be called after OpenGL context is created.
        
        Returns:
            True if initialization succeeded
        """
        if self._initialized:
            return True
        
        try:
            # Compile shaders
            from OpenGL.GL import shaders
            vertex_shader = shaders.compileShader(LINE_VERTEX_SHADER, GL_VERTEX_SHADER)
            fragment_shader = shaders.compileShader(LINE_FRAGMENT_SHADER, GL_FRAGMENT_SHADER)
            self._program = shaders.compileProgram(vertex_shader, fragment_shader)
            
            # Get uniform locations
            self._u_model = glGetUniformLocation(self._program, 'u_model')
            self._u_view = glGetUniformLocation(self._program, 'u_view')
            self._u_projection = glGetUniformLocation(self._program, 'u_projection')
            self._u_color = glGetUniformLocation(self._program, 'u_color')
            
            # Create VAO and VBO
            self._vao = glGenVertexArrays(1)
            self._vbo = glGenBuffers(1)
            
            glBindVertexArray(self._vao)
            glBindBuffer(GL_ARRAY_BUFFER, self._vbo)
            glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 0, None)
            glEnableVertexAttribArray(0)
            glBindVertexArray(0)
            
            self._initialized = True
            return True
            
        except Exception as e:
            print(f"Failed to initialize skeleton visualizer: {e}")
            return False
    
    def update_skeleton(self, skeleton: Skeleton) -> None:
        """
        Update the skeleton visualization data.
        
        Call this when the skeleton pose changes.
        
        Args:
            skeleton: The skeleton to visualize
        """
        self._line_vertices = []
        
        for bone in skeleton:
            if bone.parent is not None:
                # Draw line from parent to this bone
                parent_pos = bone.parent.get_world_position()
                bone_pos = bone.get_world_position()
                
                self._line_vertices.extend([parent_pos.x, parent_pos.y, parent_pos.z])
                self._line_vertices.extend([bone_pos.x, bone_pos.y, bone_pos.z])
        
        self._line_count = len(self._line_vertices) // 6  # 6 floats per line (2 vertices)
        
        # Upload to GPU
        if self._initialized and self._line_count > 0:
            vertices = np.array(self._line_vertices, dtype=np.float32)
            glBindBuffer(GL_ARRAY_BUFFER, self._vbo)
            glBufferData(GL_ARRAY_BUFFER, vertices.nbytes, vertices, GL_DYNAMIC_DRAW)
    
    def render(self, view_matrix: Mat4, projection_matrix: Mat4,
               color: Tuple[float, float, float] = (0.0, 1.0, 0.0),
               model_matrix: Optional[Mat4] = None) -> None:
        """
        Render the skeleton.

        Args:
            view_matrix: Camera view matrix
            projection_matrix: Camera projection matrix
            color: RGB color for the bones (default: green)
            model_matrix: Optional model transform matrix (for positioning in world space)
        """
        if not self._initialized or self._line_count == 0:
            return

        glUseProgram(self._program)

        # Set model matrix (identity if not provided)
        if model_matrix is not None:
            glUniformMatrix4fv(self._u_model, 1, GL_FALSE, model_matrix.to_list())
        else:
            # Use identity matrix
            glUniformMatrix4fv(self._u_model, 1, GL_FALSE, [1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1])

        # Set uniforms
        glUniformMatrix4fv(self._u_view, 1, GL_FALSE, view_matrix.to_list())
        glUniformMatrix4fv(self._u_projection, 1, GL_FALSE, projection_matrix.to_list())
        glUniform3f(self._u_color, color[0], color[1], color[2])
        
        # Draw lines
        glBindVertexArray(self._vao)
        # Note: glLineWidth only accepts 1.0 in core profile without line smoothing
        glDrawArrays(GL_LINES, 0, self._line_count * 2)
        glBindVertexArray(0)
    
    def render_joints(self, skeleton: Skeleton, view_matrix: Mat4, 
                      projection_matrix: Mat4, joint_size: float = 0.02) -> None:
        """
        Render joint positions as points.
        
        This is a simplified version - for proper joint rendering,
        you'd typically use instanced spheres.
        
        Args:
            skeleton: The skeleton to render
            view_matrix: Camera view matrix
            projection_matrix: Camera projection matrix
            joint_size: Size of joint markers
        """
        # For now, just render the bones
        # A full implementation would render spheres at each joint
        self.render(view_matrix, projection_matrix)
    
    def cleanup(self) -> None:
        """Clean up OpenGL resources."""
        if self._vao:
            glDeleteVertexArrays(1, [self._vao])
            self._vao = 0
        if self._vbo:
            glDeleteBuffers(1, [self._vbo])
            self._vbo = 0
        if self._program:
            glDeleteProgram(self._program)
            self._program = 0
        
        self._initialized = False


def get_bone_color(bone: Bone, selected: bool = False) -> Tuple[float, float, float]:
    """
    Get the color for a bone based on its state.
    
    Args:
        bone: The bone to get color for
        selected: Whether the bone is selected
    
    Returns:
        RGB color tuple
    """
    if selected:
        return (1.0, 0.5, 0.0)  # Orange for selected
    
    # Color based on depth in hierarchy
    depth = bone.get_depth()
    intensity = max(0.3, 1.0 - depth * 0.1)
    
    return (0.0, intensity, 0.0)  # Green gradient

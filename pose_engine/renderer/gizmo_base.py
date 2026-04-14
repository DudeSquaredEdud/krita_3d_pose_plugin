"""
Gizmo Base Module - Shared Code for Gizmos
==========================================

Provides shared shader code and utilities for gizmo rendering.
Each gizmo type (rotation, movement, scale) imports from this module.
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


# Vertex shader for gizmo geometry with lighting
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
    v_normal = mat3(u_model) * a_normal; // Transform normal to world space
    v_world_pos = (u_model * vec4(a_position, 1.0)).xyz;
    gl_Position = u_projection * u_view * u_model * vec4(a_position, 1.0);
}
"""

# Fragment shader for gizmo geometry with lighting
GIZMO_FRAGMENT_SHADER = """
#version 330 core

in vec3 v_color;
in vec3 v_normal;
in vec3 v_world_pos;

out vec4 frag_color;

uniform vec3 u_color_override;
uniform float u_color_mix;
uniform vec3 u_light_dir; // Directional light direction (world space)
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


# Gizmo axis colors
AXIS_COLORS = {
    'x': (1.0, 0.2, 0.2),   # Red
    'y': (0.2, 1.0, 0.2),   # Green
    'z': (0.2, 0.2, 1.0),   # Blue
    'xy': (1.0, 1.0, 0.2),  # Yellow
    'xz': (1.0, 0.2, 1.0),  # Magenta
    'yz': (0.2, 1.0, 1.0),  # Cyan
}


def create_torus_geometry(major_radius: float, minor_radius: float,
                          major_segments: int = 48, minor_segments: int = 16,
                          color: Tuple[float, float, float] = (1.0, 1.0, 1.0)) -> Tuple[np.ndarray, np.ndarray]:
    """
    Create torus geometry for rotation gizmo rings.
    
    Args:
        major_radius: Distance from center of torus to center of tube
        minor_radius: Radius of the tube
        major_segments: Number of segments around the major radius
        minor_segments: Number of segments around the minor radius
        color: RGB color tuple
    
    Returns:
        Tuple of (vertices, normals) arrays
    """
    vertices = []
    normals = []
    
    for i in range(major_segments):
        theta1 = 2 * math.pi * i / major_segments
        theta2 = 2 * math.pi * (i + 1) / major_segments
        
        for j in range(minor_segments):
            phi1 = 2 * math.pi * j / minor_segments
            phi2 = 2 * math.pi * (j + 1) / minor_segments
            
            # Four corners of the quad
            p1 = _torus_point(major_radius, minor_radius, theta1, phi1)
            p2 = _torus_point(major_radius, minor_radius, theta1, phi2)
            p3 = _torus_point(major_radius, minor_radius, theta2, phi1)
            p4 = _torus_point(major_radius, minor_radius, theta2, phi2)
            
            n1 = _torus_normal(major_radius, minor_radius, theta1, phi1)
            n2 = _torus_normal(major_radius, minor_radius, theta1, phi2)
            n3 = _torus_normal(major_radius, minor_radius, theta2, phi1)
            n4 = _torus_normal(major_radius, minor_radius, theta2, phi2)
            
            # Two triangles per quad
            vertices.extend([*p1, *color, *p2, *color, *p3, *color])
            vertices.extend([*p2, *color, *p4, *color, *p3, *color])
            normals.extend([*n1, *n2, *n3])
            normals.extend([*n2, *n4, *n3])
    
    return np.array(vertices, dtype=np.float32), np.array(normals, dtype=np.float32)


def _torus_point(major_radius: float, minor_radius: float, theta: float, phi: float) -> Tuple[float, float, float]:
    """Calculate a point on a torus surface."""
    x = (major_radius + minor_radius * math.cos(phi)) * math.cos(theta)
    y = minor_radius * math.sin(phi)
    z = (major_radius + minor_radius * math.cos(phi)) * math.sin(theta)
    return (x, y, z)


def _torus_normal(major_radius: float, minor_radius: float, theta: float, phi: float) -> Tuple[float, float, float]:
    """Calculate the normal at a point on a torus surface."""
    nx = math.cos(phi) * math.cos(theta)
    ny = math.sin(phi)
    nz = math.cos(phi) * math.sin(theta)
    return (nx, ny, nz)


def create_arrow_geometry(length: float, radius: float, 
                          head_length: float, head_radius: float,
                          segments: int = 16,
                          color: Tuple[float, float, float] = (1.0, 1.0, 1.0)) -> Tuple[np.ndarray, np.ndarray]:
    """
    Create arrow geometry for movement gizmo axes.
    
    Args:
        length: Length of the arrow shaft
        radius: Radius of the arrow shaft
        head_length: Length of the arrow head
        head_radius: Radius of the arrow head base
        segments: Number of segments around the circumference
        color: RGB color tuple
    
    Returns:
        Tuple of (vertices, normals) arrays
    """
    vertices = []
    normals = []
    
    # Shaft cylinder
    for i in range(segments):
        theta1 = 2 * math.pi * i / segments
        theta2 = 2 * math.pi * (i + 1) / segments
        
        # Side of shaft
        p1 = (radius * math.cos(theta1), 0, radius * math.sin(theta1))
        p2 = (radius * math.cos(theta2), 0, radius * math.sin(theta2))
        p3 = (radius * math.cos(theta1), length, radius * math.sin(theta1))
        p4 = (radius * math.cos(theta2), length, radius * math.sin(theta2))
        
        n1 = (math.cos(theta1), 0, math.sin(theta1))
        n2 = (math.cos(theta2), 0, math.sin(theta2))
        
        vertices.extend([*p1, *color, *p2, *color, *p3, *color])
        vertices.extend([*p2, *color, *p4, *color, *p3, *color])
        normals.extend([*n1, *n2, *n1])
        normals.extend([*n2, *n2, *n1])
    
    # Arrow head cone
    for i in range(segments):
        theta1 = 2 * math.pi * i / segments
        theta2 = 2 * math.pi * (i + 1) / segments
        
        # Cone side
        p1 = (head_radius * math.cos(theta1), length, head_radius * math.sin(theta1))
        p2 = (head_radius * math.cos(theta2), length, head_radius * math.sin(theta2))
        p3 = (0, length + head_length, 0)
        
        # Calculate cone normal
        slope = head_radius / head_length
        n = (math.cos((theta1 + theta2) / 2), slope, math.sin((theta1 + theta2) / 2))
        n_len = math.sqrt(n[0]**2 + n[1]**2 + n[2]**2)
        n = (n[0]/n_len, n[1]/n_len, n[2]/n_len)
        
        vertices.extend([*p1, *color, *p2, *color, *p3, *color])
        normals.extend([*n, *n, *n])
    
    return np.array(vertices, dtype=np.float32), np.array(normals, dtype=np.float32)


def compile_gizmo_shaders() -> Optional[int]:
    """
    Compile the gizmo shaders.

    Returns:
        Compiled shader program ID (int), or None on failure
    """
    try:
        vertex_shader = shaders.compileShader(GIZMO_VERTEX_SHADER, GL_VERTEX_SHADER)
        fragment_shader = shaders.compileShader(GIZMO_FRAGMENT_SHADER, GL_FRAGMENT_SHADER)
        program = shaders.compileProgram(vertex_shader, fragment_shader)
        return program
    except Exception as e:
        print(f"Failed to compile gizmo shaders: {e}")
        return None

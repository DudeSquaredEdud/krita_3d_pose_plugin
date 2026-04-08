"""
OpenGL Renderer - Mesh and Skeleton Rendering
=============================================

Renders 3D meshes with skinning and skeleton visualization.
Uses modern OpenGL (core profile) with VAOs and VBOs.
Supports Dual Quaternion Skinning (DQS) for better volume preservation.
"""

import ctypes
from typing import Optional, List, Tuple
from OpenGL.GL import *
from OpenGL.GL import shaders
import numpy as np

from ..vec3 import Vec3
from ..mat4 import Mat4
from ..quat import Quat
from ..skeleton import Skeleton
from ..skinning import SkinningData, compute_bone_matrices_from_skeleton


# Vertex shader with Dual Quaternion Skinning
# Each bone is represented as two vec4s: (real.xyzw) and (dual.xyzw)
# where the quaternion uses GLSL convention (x, y, z, w)
VERTEX_SHADER = """
#version 330 core

layout(location = 0) in vec3 a_position;
layout(location = 1) in vec3 a_normal;
layout(location = 2) in vec4 a_joints;
layout(location = 3) in vec4 a_weights;
layout(location = 4) in vec2 a_texcoord;

out vec3 v_normal;
out vec3 v_position;
out vec2 v_texcoord;

uniform mat4 u_model;
uniform mat4 u_view;
uniform mat4 u_projection;
uniform vec4 u_bone_dqs[200]; // 100 bones * 2 vec4s per bone

// Quaternion multiplication
vec4 quat_mul(vec4 q1, vec4 q2) {
    return vec4(
        q1.w * q2.x + q1.x * q2.w + q1.y * q2.z - q1.z * q2.y,
        q1.w * q2.y - q1.x * q2.z + q1.y * q2.w + q1.z * q2.x,
        q1.w * q2.z + q1.x * q2.y - q1.y * q2.x + q1.z * q2.w,
        q1.w * q2.w - q1.x * q2.x - q1.y * q2.y - q1.z * q2.z
    );
}

// Rotate a vector by a unit quaternion
vec3 quat_rotate(vec4 q, vec3 v) {
    vec3 qv = vec3(q.x, q.y, q.z);
    vec3 uv = cross(qv, v);
    vec3 uuv = cross(qv, uv);
    return v + 2.0 * (q.w * uv + uuv);
}

void main() {
    vec4 real_blend = vec4(0.0);
    vec4 dual_blend = vec4(0.0);
    float total_weight = 0.0;

    // First bone reference for antipodality check
    vec4 first_real = vec4(0.0);
    bool has_first = false;

    for (int i = 0; i < 4; i++) {
        int joint = int(a_joints[i]);
        float weight = a_weights[i];

        if (weight > 0.0 && joint >= 0 && joint < 100) {
            vec4 real_q = u_bone_dqs[joint * 2];
            vec4 dual_q = u_bone_dqs[joint * 2 + 1];

            if (!has_first) {
                first_real = real_q;
                has_first = true;
            } else {
                // Antipodality check: q and -q represent the same rotation
                float dot = first_real.x * real_q.x + first_real.y * real_q.y
                    + first_real.z * real_q.z + first_real.w * real_q.w;
                if (dot < 0.0) {
                    real_q = -real_q;
                    dual_q = -dual_q;
                }
            }

            real_blend += weight * real_q;
            dual_blend += weight * dual_q;
            total_weight += weight;
        }
    }

    vec3 skinned_pos;
    vec3 skinned_normal;

    if (total_weight > 0.001) {
        // Normalize the blended dual quaternion
        float norm = sqrt(real_blend.x * real_blend.x + real_blend.y * real_blend.y
            + real_blend.z * real_blend.z + real_blend.w * real_blend.w);
        real_blend /= norm;
        dual_blend /= norm;

        // Extract translation from dual quaternion:
        // translation = 2 * (dual * conjugate(real)).xyz
        vec4 conj = vec4(-real_blend.x, -real_blend.y, -real_blend.z, real_blend.w);
        vec4 t_quat = quat_mul(dual_blend, conj);
        vec3 translation = 2.0 * vec3(t_quat.x, t_quat.y, t_quat.z);

        // Transform position and normal
        skinned_pos = quat_rotate(real_blend, a_position) + translation;
        skinned_normal = quat_rotate(real_blend, a_normal);
    } else {
    skinned_pos = a_position;
    skinned_normal = a_normal;
    }

    v_normal = normalize(mat3(u_model) * skinned_normal);
    v_position = vec3(u_model * vec4(skinned_pos, 1.0));
    v_texcoord = a_texcoord;

    gl_Position = u_projection * u_view * u_model * vec4(skinned_pos, 1.0);
}
"""

# Fragment shader with basic lighting, texture support, and distance gradient overlay
FRAGMENT_SHADER = """
#version 330 core

in vec3 v_normal;
in vec3 v_position;
in vec2 v_texcoord;

out vec4 frag_color;

uniform vec3 u_light_dir;
uniform vec3 u_light_color;
uniform vec3 u_ambient;
uniform vec3 u_diffuse_color;
uniform sampler2D u_base_color_texture;
uniform bool u_has_texture;

// Distance gradient overlay uniforms
uniform bool u_distance_gradient_enabled;
uniform vec3 u_camera_position;
uniform float u_distance_near;
uniform float u_distance_far;
uniform vec3 u_gradient_color_near;
uniform vec3 u_gradient_color_far;

void main() {
    vec3 normal = normalize(v_normal);

    // Get base color from texture or uniform
    // In glTF, final color = base_color_factor * texture_color
    vec3 base_color;
    if (u_has_texture) {
        // Multiply texture color by diffuse color (base_color_factor)
        base_color = texture(u_base_color_texture, v_texcoord).rgb * u_diffuse_color;
    } else {
        base_color = u_diffuse_color;
    }

    // Diffuse lighting
    float diff = max(dot(normal, normalize(u_light_dir)), 0.0);
    vec3 diffuse = diff * u_light_color * base_color;

    // Ambient
    vec3 ambient = u_ambient * base_color;

    vec3 result = ambient + diffuse;

    // Distance gradient overlay
    if (u_distance_gradient_enabled) {
        float distance = length(v_position - u_camera_position);
        float t = clamp((distance - u_distance_near) / (u_distance_far - u_distance_near), 0.0, 1.0);
        vec3 gradient_color = mix(u_gradient_color_near, u_gradient_color_far, t);
        // Stronger blend (70%) for more visible effect
        result = mix(result, result * gradient_color, 0.7);
    }

    frag_color = vec4(result, 1.0);
}
"""


class MeshBuffers:
    """OpenGL buffers for a mesh."""

    def __init__(self):
        self.vao: int = 0
        self.vbo_position: int = 0
        self.vbo_normal: int = 0
        self.vbo_joints: int = 0
        self.vbo_weights: int = 0
        self.vbo_texcoord: int = 0  # Texture coordinate buffer
        self.ebo: int = 0
        self.index_count: int = 0
        self.vertex_count: int = 0
        self.has_skinning: bool = False
        self.has_texcoords: bool = False  # Whether mesh has texture coordinates
        self.material_index: Optional[int] = None # Index into materials list
        self.diffuse_color: Tuple[float, float, float] = (0.8, 0.8, 0.8) # Default gray
        self.texture_id: Optional[int] = None  # OpenGL texture ID for base color texture


class GLRenderer:
    """
    OpenGL renderer for 3D meshes with skeletal animation.

    Usage:
    renderer = GLRenderer()
    renderer.initialize()
    renderer.upload_mesh(mesh_data)

    # In render loop:
    renderer.render(skeleton, view_matrix, projection_matrix)
    """

    def __init__(self):
        """Create a new OpenGL renderer."""
        self._program: Optional[int] = None
        self._mesh_buffers: Optional[MeshBuffers] = None # Legacy: single mesh
        self._sub_mesh_buffers: List[MeshBuffers] = [] # New: multiple sub-meshes
        self._initialized: bool = False
        self._bone_matrices: List[Mat4] = []

        # Texture cache: maps image data hash to OpenGL texture ID
        self._texture_cache: dict = {}

        # Distance gradient overlay state
        self._distance_gradient_enabled: bool = False
        self._distance_near: float = 2.0  # Near distance for gradient start
        self._distance_far: float = 20.0  # Far distance for gradient end
        self._gradient_color_near: Tuple[float, float, float] = (0.0, 0.8, 1.0) # Cyan
        self._gradient_color_far: Tuple[float, float, float] = (1.0, 0.2, 0.0) # Orange-red

        # Shader uniform locations
        self._u_model: int = -1
        self._u_view: int = -1
        self._u_projection: int = -1
        self._u_light_dir: int = -1
        self._u_light_color: int = -1
        self._u_ambient: int = -1
        self._u_diffuse_color: int = -1
        self._u_bone_dqs: int = -1
        self._u_has_texture: int = -1
        self._u_base_color_texture: int = -1
        # Distance gradient uniform locations
        self._u_distance_gradient_enabled: int = -1
        self._u_camera_position: int = -1
        self._u_distance_near: int = -1
        self._u_distance_far: int = -1
        self._u_gradient_color_near: int = -1
        self._u_gradient_color_far: int = -1

    def initialize(self) -> bool:
        """
        Initialize the renderer.

        Must be called after OpenGL context is created.

        Returns: True if initialization succeeded
        """
        if self._initialized:
            return True

        try:
            # Compile shaders
            vertex_shader = shaders.compileShader(VERTEX_SHADER, GL_VERTEX_SHADER)
            fragment_shader = shaders.compileShader(FRAGMENT_SHADER, GL_FRAGMENT_SHADER)
            self._program = shaders.compileProgram(vertex_shader, fragment_shader)

            # Get uniform locations
            self._u_model = glGetUniformLocation(self._program, 'u_model')
            self._u_view = glGetUniformLocation(self._program, 'u_view')
            self._u_projection = glGetUniformLocation(self._program, 'u_projection')
            self._u_light_dir = glGetUniformLocation(self._program, 'u_light_dir')
            self._u_light_color = glGetUniformLocation(self._program, 'u_light_color')
            self._u_ambient = glGetUniformLocation(self._program, 'u_ambient')
            self._u_diffuse_color = glGetUniformLocation(self._program, 'u_diffuse_color')
            self._u_bone_dqs = glGetUniformLocation(self._program, 'u_bone_dqs[0]')
            self._u_has_texture = glGetUniformLocation(self._program, 'u_has_texture')
            self._u_base_color_texture = glGetUniformLocation(self._program, 'u_base_color_texture')
    
            # Distance gradient uniform locations
            self._u_distance_gradient_enabled = glGetUniformLocation(self._program, 'u_distance_gradient_enabled')
            self._u_camera_position = glGetUniformLocation(self._program, 'u_camera_position')
            self._u_distance_near = glGetUniformLocation(self._program, 'u_distance_near')
            self._u_distance_far = glGetUniformLocation(self._program, 'u_distance_far')
            self._u_gradient_color_near = glGetUniformLocation(self._program, 'u_gradient_color_near')
            self._u_gradient_color_far = glGetUniformLocation(self._program, 'u_gradient_color_far')
    
            self._initialized = True
            return True

        except Exception as e:
            print(f"Failed to initialize renderer: {e}")
            return False

    def upload_mesh(self, positions: List[Vec3], normals: List[Vec3],
                    indices: List[int], skinning_data: Optional[SkinningData] = None,
                    diffuse_color: Optional[Tuple[float, float, float]] = None) -> bool:
        """
        Upload mesh data to GPU (legacy single-mesh API).

        Args:
            positions: Vertex positions
            normals: Vertex normals
            indices: Triangle indices
            skinning_data: Optional skinning data for skeletal animation
            diffuse_color: Optional RGB color tuple (default: gray)

        Returns:
            True if upload succeeded
        """
        if not self._initialized:
            return False

        # Clean up old buffers
        if self._mesh_buffers is not None:
            self._delete_buffers(self._mesh_buffers)
        self._sub_mesh_buffers = []

        self._mesh_buffers = MeshBuffers()
        buffers = self._mesh_buffers
        
        if diffuse_color:
            buffers.diffuse_color = diffuse_color

        # Convert to numpy arrays
        pos_array = np.array([(p.x, p.y, p.z) for p in positions], dtype=np.float32)
        nrm_array = np.array([(n.x, n.y, n.z) for n in normals], dtype=np.float32)
        idx_array = np.array(indices, dtype=np.uint32)

        buffers.vertex_count = len(positions)
        buffers.index_count = len(indices)

        # Create VAO - must be done in OpenGL context
        vao = glGenVertexArrays(1)
        if vao == 0:
            print("Failed to create VAO")
            return False
        buffers.vao = int(vao)

        glBindVertexArray(buffers.vao)

        # Position buffer
        buffers.vbo_position = glGenBuffers(1)
        glBindBuffer(GL_ARRAY_BUFFER, buffers.vbo_position)
        glBufferData(GL_ARRAY_BUFFER, pos_array.nbytes, pos_array, GL_STATIC_DRAW)
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 0, None)
        glEnableVertexAttribArray(0)

        # Normal buffer
        buffers.vbo_normal = glGenBuffers(1)
        glBindBuffer(GL_ARRAY_BUFFER, buffers.vbo_normal)
        glBufferData(GL_ARRAY_BUFFER, nrm_array.nbytes, nrm_array, GL_STATIC_DRAW)
        glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, 0, None)
        glEnableVertexAttribArray(1)

        # Skinning data - always create joint/weight buffers even for static meshes
        # The shader expects these attributes to exist
        buffers.has_skinning = skinning_data is not None

        # Joint indices (as float for simplicity)
        joints_array = np.zeros((len(positions), 4), dtype=np.float32)
        weights_array = np.zeros((len(positions), 4), dtype=np.float32)

        if skinning_data is not None:
            for i in range(len(positions)):
                skinning = skinning_data.get_vertex_skinning(i)
                for j, (joint_idx, weight) in enumerate(skinning.get_influences()):
                    if j < 4:
                        joints_array[i, j] = float(joint_idx)
                        weights_array[i, j] = weight
        # For static meshes, joints and weights remain all zeros
        # The shader will detect total_weight == 0 and use unskinned position

        # Joints buffer
        buffers.vbo_joints = glGenBuffers(1)
        glBindBuffer(GL_ARRAY_BUFFER, buffers.vbo_joints)
        glBufferData(GL_ARRAY_BUFFER, joints_array.nbytes, joints_array, GL_STATIC_DRAW)
        glVertexAttribPointer(2, 4, GL_FLOAT, GL_FALSE, 0, None)
        glEnableVertexAttribArray(2)

        # Weights buffer
        buffers.vbo_weights = glGenBuffers(1)
        glBindBuffer(GL_ARRAY_BUFFER, buffers.vbo_weights)
        glBufferData(GL_ARRAY_BUFFER, weights_array.nbytes, weights_array, GL_STATIC_DRAW)
        glVertexAttribPointer(3, 4, GL_FLOAT, GL_FALSE, 0, None)
        glEnableVertexAttribArray(3)

        # Index buffer
        buffers.ebo = glGenBuffers(1)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, buffers.ebo)
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, idx_array.nbytes, idx_array, GL_STATIC_DRAW)

        glBindVertexArray(0)

        return True

    def upload_mesh_with_materials(self, mesh_data) -> bool:
        """
        Upload mesh data with multiple sub-meshes and materials.

        Args:
            mesh_data: MeshData object with sub_meshes and materials

        Returns:
            True if upload succeeded
        """
        if not self._initialized:
            return False

        # Clean up old buffers and textures
        for buffers in self._sub_mesh_buffers:
            self._delete_buffers(buffers)
        self._sub_mesh_buffers = []
    
        if self._mesh_buffers is not None:
            self._delete_buffers(self._mesh_buffers)
            self._mesh_buffers = None
    
        # Clear texture cache when loading a new mesh
        # This ensures textures are recreated with correct image data
        for texture_id in self._texture_cache.values():
            glDeleteTextures([texture_id])
        self._texture_cache = {}

        # Process each sub-mesh
        # Store texcoords for potential swapping
        all_texcoords = []
        
        for i, sub_mesh in enumerate(mesh_data.sub_meshes):
            # Store texcoords for potential swapping
            all_texcoords.append(sub_mesh.texcoords)
            
            buffers = self._create_sub_mesh_buffers(
                sub_mesh.positions,
                sub_mesh.normals,
                sub_mesh.indices,
                sub_mesh.skinning_data,
                sub_mesh.texcoords # Pass texture coordinates
            )
    
            if buffers is None:
                print("Failed to create buffers for sub-mesh")
                continue
    
            # Set material info
            buffers.material_index = sub_mesh.material_index
    
            # Get color from material if available
            if sub_mesh.material_index is not None and sub_mesh.material_index < len(mesh_data.materials):
                mat = mesh_data.materials[sub_mesh.material_index]
                # Use base color factor (RGB)
                buffers.diffuse_color = (mat.base_color_factor[0],
                mat.base_color_factor[1],
                mat.base_color_factor[2])
    
            # Create texture if material has a base color texture
            if mat.base_color_texture is not None and mesh_data.textures and mesh_data.images:
                texture_id = self._create_texture_from_material(
                    mat, mesh_data.textures, mesh_data.images
                )
                if texture_id is not None:
                    buffers.texture_id = texture_id
    
                self._sub_mesh_buffers.append(buffers)

        return len(self._sub_mesh_buffers) > 0

    def _create_sub_mesh_buffers(self, positions: List[Vec3], normals: List[Vec3],
                                  indices: List[int],
                                  skinning_data: Optional[SkinningData] = None,
                                  texcoords: Optional[List[Tuple[float, float]]] = None) -> Optional[MeshBuffers]:
        """
        Create OpenGL buffers for a single sub-mesh.

        Args:
            positions: Vertex positions
            normals: Vertex normals
            indices: Triangle indices
            skinning_data: Optional skinning data
            texcoords: Optional texture coordinates

        Returns:
            MeshBuffers object or None on failure
        """
        buffers = MeshBuffers()

        # Convert to numpy arrays
        pos_array = np.array([(p.x, p.y, p.z) for p in positions], dtype=np.float32)
        nrm_array = np.array([(n.x, n.y, n.z) for n in normals], dtype=np.float32)
        idx_array = np.array(indices, dtype=np.uint32)

        buffers.vertex_count = len(positions)
        buffers.index_count = len(indices)
        buffers.has_texcoords = texcoords is not None and len(texcoords) > 0

        # Create VAO
        vao = glGenVertexArrays(1)
        if vao == 0:
            return None
        buffers.vao = int(vao)

        glBindVertexArray(buffers.vao)

        # Position buffer
        buffers.vbo_position = glGenBuffers(1)
        glBindBuffer(GL_ARRAY_BUFFER, buffers.vbo_position)
        glBufferData(GL_ARRAY_BUFFER, pos_array.nbytes, pos_array, GL_STATIC_DRAW)
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 0, None)
        glEnableVertexAttribArray(0)

        # Normal buffer
        buffers.vbo_normal = glGenBuffers(1)
        glBindBuffer(GL_ARRAY_BUFFER, buffers.vbo_normal)
        glBufferData(GL_ARRAY_BUFFER, nrm_array.nbytes, nrm_array, GL_STATIC_DRAW)
        glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, 0, None)
        glEnableVertexAttribArray(1)

        # Skinning data
        buffers.has_skinning = skinning_data is not None

        joints_array = np.zeros((len(positions), 4), dtype=np.float32)
        weights_array = np.zeros((len(positions), 4), dtype=np.float32)

        if skinning_data is not None:
            for i in range(len(positions)):
                skinning = skinning_data.get_vertex_skinning(i)
                for j, (joint_idx, weight) in enumerate(skinning.get_influences()):
                    if j < 4:
                        joints_array[i, j] = float(joint_idx)
                        weights_array[i, j] = weight

        # Joints buffer
        buffers.vbo_joints = glGenBuffers(1)
        glBindBuffer(GL_ARRAY_BUFFER, buffers.vbo_joints)
        glBufferData(GL_ARRAY_BUFFER, joints_array.nbytes, joints_array, GL_STATIC_DRAW)
        glVertexAttribPointer(2, 4, GL_FLOAT, GL_FALSE, 0, None)
        glEnableVertexAttribArray(2)

        # Weights buffer
        buffers.vbo_weights = glGenBuffers(1)
        glBindBuffer(GL_ARRAY_BUFFER, buffers.vbo_weights)
        glBufferData(GL_ARRAY_BUFFER, weights_array.nbytes, weights_array, GL_STATIC_DRAW)
        glVertexAttribPointer(3, 4, GL_FLOAT, GL_FALSE, 0, None)
        glEnableVertexAttribArray(3)

        # Texture coordinate buffer (location 4)
        if buffers.has_texcoords:
            tex_array = np.array(texcoords, dtype=np.float32)
            
            buffers.vbo_texcoord = glGenBuffers(1)
            glBindBuffer(GL_ARRAY_BUFFER, buffers.vbo_texcoord)
            glBufferData(GL_ARRAY_BUFFER, tex_array.nbytes, tex_array, GL_STATIC_DRAW)
            glVertexAttribPointer(4, 2, GL_FLOAT, GL_FALSE, 0, None)
            glEnableVertexAttribArray(4)
        else:
            # Create a dummy texcoord buffer with zeros
            tex_array = np.zeros((len(positions), 2), dtype=np.float32)
            buffers.vbo_texcoord = glGenBuffers(1)
            glBindBuffer(GL_ARRAY_BUFFER, buffers.vbo_texcoord)
            glBufferData(GL_ARRAY_BUFFER, tex_array.nbytes, tex_array, GL_STATIC_DRAW)
            glVertexAttribPointer(4, 2, GL_FLOAT, GL_FALSE, 0, None)
            glEnableVertexAttribArray(4)

        # Index buffer
        buffers.ebo = glGenBuffers(1)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, buffers.ebo)
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, idx_array.nbytes, idx_array, GL_STATIC_DRAW)

        glBindVertexArray(0)

        return buffers

    def render(self, skeleton: Optional[Skeleton],
               view_matrix: Mat4, projection_matrix: Mat4,
               model_matrix: Optional[Mat4] = None,
               camera_position: Optional[Vec3] = None) -> None:
        """
        Render the mesh.

        Args:
            skeleton: Skeleton for bone matrices (can be None for static mesh)
            view_matrix: Camera view matrix
            projection_matrix: Camera projection matrix
            model_matrix: Optional model transform (default: identity)
            camera_position: Camera position for distance gradient (optional)
        """
        if not self._initialized:
            return

        # Determine which buffers to render
        if self._sub_mesh_buffers:
            # Render multiple sub-meshes with per-submesh colors
            self._render_sub_meshes(skeleton, view_matrix, projection_matrix, model_matrix, camera_position)
        elif self._mesh_buffers is not None:
            # Legacy: render single mesh
            self._render_single_mesh(self._mesh_buffers, skeleton, view_matrix, projection_matrix, model_matrix, camera_position)

    def _set_distance_gradient_uniforms(self, camera_position: Optional[Vec3]) -> None:
        """Set distance gradient shader uniforms."""
        if self._distance_gradient_enabled and camera_position is not None:
            glUniform1i(self._u_distance_gradient_enabled, 1)
            glUniform3f(self._u_camera_position, camera_position.x, camera_position.y, camera_position.z)
            glUniform1f(self._u_distance_near, self._distance_near)
            glUniform1f(self._u_distance_far, self._distance_far)
            glUniform3f(self._u_gradient_color_near, *self._gradient_color_near)
            glUniform3f(self._u_gradient_color_far, *self._gradient_color_far)
        else:
            glUniform1i(self._u_distance_gradient_enabled, 0)

    def _render_single_mesh(self, buffers: MeshBuffers, skeleton: Optional[Skeleton],
                            view_matrix: Mat4, projection_matrix: Mat4,
                            model_matrix: Optional[Mat4] = None,
                            camera_position: Optional[Vec3] = None) -> None:
        """Render a single mesh buffer."""
        glUseProgram(self._program)

        # Set matrices
        if model_matrix is None:
            model_matrix = Mat4.identity()

        glUniformMatrix4fv(self._u_model, 1, GL_FALSE, model_matrix.to_list())
        glUniformMatrix4fv(self._u_view, 1, GL_FALSE, view_matrix.to_list())
        glUniformMatrix4fv(self._u_projection, 1, GL_FALSE, projection_matrix.to_list())

        # Set lighting
        glUniform3f(self._u_light_dir, 0.5, 1.0, 0.5)
        glUniform3f(self._u_light_color, 1.0, 1.0, 1.0)
        glUniform3f(self._u_ambient, 0.2, 0.2, 0.2)
        glUniform3f(self._u_diffuse_color, *buffers.diffuse_color)

        # Set distance gradient uniforms
        self._set_distance_gradient_uniforms(camera_position)

        # Set bone dual quaternions
        if skeleton is not None and buffers.has_skinning:
            self._set_bone_dual_quaternions(skeleton)

        # Draw with VAO error handling for offscreen rendering
        try:
            glBindVertexArray(buffers.vao)
            glDrawElements(GL_TRIANGLES, buffers.index_count, GL_UNSIGNED_INT, None)
            glBindVertexArray(0)
        except Exception as e:
            print(f"[GL_RENDERER] VAO binding failed (likely offscreen context issue): {e}")
            self._render_without_vao(buffers)

    def _render_sub_meshes(self, skeleton: Optional[Skeleton],
                           view_matrix: Mat4, projection_matrix: Mat4,
                           model_matrix: Optional[Mat4] = None,
                           camera_position: Optional[Vec3] = None) -> None:
        """Render multiple sub-meshes with per-submesh colors and textures."""
        glUseProgram(self._program)

        # Set matrices (same for all sub-meshes)
        if model_matrix is None:
            model_matrix = Mat4.identity()

        glUniformMatrix4fv(self._u_model, 1, GL_FALSE, model_matrix.to_list())
        glUniformMatrix4fv(self._u_view, 1, GL_FALSE, view_matrix.to_list())
        glUniformMatrix4fv(self._u_projection, 1, GL_FALSE, projection_matrix.to_list())

        # Set lighting (same for all sub-meshes)
        glUniform3f(self._u_light_dir, 0.5, 1.0, 0.5)
        glUniform3f(self._u_light_color, 1.0, 1.0, 1.0)
        glUniform3f(self._u_ambient, 0.2, 0.2, 0.2)

        # Set distance gradient uniforms (same for all sub-meshes)
        self._set_distance_gradient_uniforms(camera_position)

        # Set bone dual quaternions (same for all sub-meshes)
        if skeleton is not None and any(b.has_skinning for b in self._sub_mesh_buffers):
            self._set_bone_dual_quaternions(skeleton)

        # Render each sub-mesh with its own color/texture
        for i, buffers in enumerate(self._sub_mesh_buffers):
            # Always set the diffuse color (used as base_color_factor for texture multiplication)
            glUniform3f(self._u_diffuse_color, *buffers.diffuse_color)

            # Set texture or color
            if buffers.texture_id is not None and buffers.has_texcoords:
                # Use texture
                glActiveTexture(GL_TEXTURE0)
                glBindTexture(GL_TEXTURE_2D, buffers.texture_id)
                glUniform1i(self._u_has_texture, 1)
                glUniform1i(self._u_base_color_texture, 0)
            else:
                # Use solid color only
                glUniform1i(self._u_has_texture, 0)

            try:
                glBindVertexArray(buffers.vao)
                glDrawElements(GL_TRIANGLES, buffers.index_count, GL_UNSIGNED_INT, None)
                glBindVertexArray(0)
            except Exception as e:
                print(f"[GL_RENDERER] VAO binding failed for sub-mesh: {e}")
                self._render_without_vao(buffers)
            
            # Unbind texture
            if buffers.texture_id is not None:
                glBindTexture(GL_TEXTURE_2D, 0)

    def _set_bone_dual_quaternions(self, skeleton: Skeleton) -> None:
        """Set bone dual quaternions uniform from skeleton."""
        bone_dqs = []
        for bone in skeleton:
            mat = bone.get_final_matrix()
            dq = self._matrix_to_dual_quat(mat)
            bone_dqs.extend(dq)

        # Pad to 100 bones (200 vec4s)
        while len(bone_dqs) < 200 * 4:
            bone_dqs.extend([0.0, 0.0, 0.0, 1.0])  # Identity quaternion (x,y,z,w)
            bone_dqs.extend([0.0, 0.0, 0.0, 0.0])  # Zero dual part

        glUniform4fv(self._u_bone_dqs, 200, bone_dqs[:800])

    def _render_without_vao(self, buffers: MeshBuffers) -> None:
        """Fallback rendering without VAO for offscreen contexts."""
        if not buffers:
            return

        try:
            print("[GL_RENDERER] Using fallback rendering without VAO")

            # Manually bind buffers (immediate mode style)
            # Position attribute (location 0)
            glBindBuffer(GL_ARRAY_BUFFER, buffers.vbo_position)
            glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 0, None)
            glEnableVertexAttribArray(0)

            # Normal attribute (location 1)
            glBindBuffer(GL_ARRAY_BUFFER, buffers.vbo_normal)
            glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, 0, None)
            glEnableVertexAttribArray(1)

            # Skinning attributes if available
            if buffers.has_skinning:
                # Joint indices (location 2)
                glBindBuffer(GL_ARRAY_BUFFER, buffers.vbo_joints)
                glVertexAttribPointer(2, 4, GL_FLOAT, GL_FALSE, 0, None)
                glEnableVertexAttribArray(2)
    
                # Joint weights (location 3)
                glBindBuffer(GL_ARRAY_BUFFER, buffers.vbo_weights)
                glVertexAttribPointer(3, 4, GL_FLOAT, GL_FALSE, 0, None)
                glEnableVertexAttribArray(3)
    
            # Texture coordinates if available (location 4)
            if buffers.has_texcoords and buffers.vbo_texcoord:
                glBindBuffer(GL_ARRAY_BUFFER, buffers.vbo_texcoord)
                glVertexAttribPointer(4, 2, GL_FLOAT, GL_FALSE, 0, None)
                glEnableVertexAttribArray(4)
    
            # Bind index buffer and draw
            glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, buffers.ebo)
            glDrawElements(GL_TRIANGLES, buffers.index_count, GL_UNSIGNED_INT, None)
    
            # Cleanup
            glDisableVertexAttribArray(0)
            glDisableVertexAttribArray(1)
            if buffers.has_skinning:
                glDisableVertexAttribArray(2)
                glDisableVertexAttribArray(3)
            if buffers.has_texcoords and buffers.vbo_texcoord:
                glDisableVertexAttribArray(4)
    
            glBindBuffer(GL_ARRAY_BUFFER, 0)
            glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, 0)
    
            print("[GL_RENDERER] Fallback rendering completed")

        except Exception as fallback_e:
            print(f"[GL_RENDERER] Fallback rendering also failed: {fallback_e}")
            import traceback
            traceback.print_exc()

    def _matrix_to_dual_quat(self, mat: Mat4) -> List[float]:
        """
        Convert a 4x4 transformation matrix to dual quaternion format.

        Returns 8 floats: [real.x, real.y, real.z, real.w, dual.x, dual.y, dual.z, dual.w]
        where real is the rotation quaternion and dual encodes the translation.
        """
        # Extract rotation quaternion from the matrix
        # Quat.from_matrix returns (w, x, y, z) but GLSL uses (x, y, z, w)
        q = Quat.from_matrix(mat)
        q = q.normalized()

        # Extract translation from the matrix (column-major: indices 12, 13, 14)
        tx = mat.m[12]
        ty = mat.m[13]
        tz = mat.m[14]

        # Compute dual quaternion for translation
        # dual = 0.5 * (0, tx, ty, tz) * real
        # Using quaternion multiplication: q1 * q2
        # q is (w, x, y, z), t_quat is (0, tx, ty, tz)
        t_w = 0.0
        t_x = tx
        t_y = ty
        t_z = tz

        # Quaternion multiplication: t * q
        # result.w = t.w*q.w - t.x*q.x - t.y*q.y - t.z*q.z
        # result.x = t.w*q.x + t.x*q.w + t.y*q.z - t.z*q.y
        # result.y = t.w*q.y - t.x*q.z + t.y*q.w + t.z*q.x
        # result.z = t.w*q.z + t.x*q.y - t.y*q.x + t.z*q.w
        dual_w = t_w * q.w - t_x * q.x - t_y * q.y - t_z * q.z
        dual_x = t_w * q.x + t_x * q.w + t_y * q.z - t_z * q.y
        dual_y = t_w * q.y - t_x * q.z + t_y * q.w + t_z * q.x
        dual_z = t_w * q.z + t_x * q.y - t_y * q.x + t_z * q.w

        # Multiply by 0.5
        dual_w *= 0.5
        dual_x *= 0.5
        dual_y *= 0.5
        dual_z *= 0.5

        # Return in GLSL format: (x, y, z, w) for each quaternion
        return [
            q.x, q.y, q.z, q.w,  # real quaternion (rotation)
            dual_x, dual_y, dual_z, dual_w  # dual quaternion (translation)
        ]

    def _create_texture_from_material(self, mat, textures: list, images: list) -> Optional[int]:
        """
        Create an OpenGL texture from a material's base color texture.
        
        Args:
            mat: MaterialData object
            textures: List of TextureData objects
            images: List of ImageData objects
            
        Returns:
            OpenGL texture ID or None on failure
        """
        try:
            # Get the texture index from material
            texture_idx = mat.base_color_texture
            if texture_idx is None or texture_idx >= len(textures):
                return None
            
            texture = textures[texture_idx]
            image_idx = texture.source_image
            if image_idx is None or image_idx >= len(images):
                return None
            
            image = images[image_idx]
            
            # Check cache first - use texture index as key
            # Different textures may reference the same image but with different samplers
            cache_key = texture_idx
            if cache_key in self._texture_cache:
                cached_id = self._texture_cache[cache_key]
                # print(f"[GL_RENDERER] Texture cache hit: tex_idx={texture_idx}, img_idx={image_idx} -> texture_id={cached_id}")
                return cached_id
            
            # Decode image data using Qt (available in Krita environment)
            from PyQt5.QtGui import QImage
            from PyQt5.QtCore import QByteArray, QBuffer, QIODevice
        
            # Load image from binary data
            img_data_bytes = QByteArray(image.data)
            buffer = QBuffer(img_data_bytes)
            buffer.open(QIODevice.ReadOnly)
            img = QImage()
            img.loadFromData(img_data_bytes)
            buffer.close()
        
            if img.isNull():
                print("[GL_RENDERER] Failed to load image data")
                return None
        
            # Convert to RGBA format if necessary
            if img.format() != QImage.Format_RGBA8888:
                img = img.convertToFormat(QImage.Format_RGBA8888)
    
            # NOTE: Do NOT flip image vertically here. glTF uses top-left origin for images,
            # and UV coordinates are defined relative to that. Flipping the image would
            # break texture atlas UV mappings (different regions would get swapped).
            # The shader handles the coordinate system correctly without flipping.
    
            # Get image dimensions and data
            width = img.width()
            height = img.height()
            
            # Convert QImage to numpy array
            # QImage.bits() returns a pointer to the image data
            ptr = img.bits()
            ptr.setsize(height * width * 4)  # 4 bytes per pixel (RGBA)
            img_data = np.frombuffer(ptr, dtype=np.uint8).reshape((height, width, 4))
            
            # Create OpenGL texture
            texture_id = glGenTextures(1)
            glBindTexture(GL_TEXTURE_2D, texture_id)
            
            # Set texture parameters
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR_MIPMAP_LINEAR)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
            
            # Upload texture data
            glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, width, height, 0, GL_RGBA, GL_UNSIGNED_BYTE, img_data)
            glGenerateMipmap(GL_TEXTURE_2D)
            
            glBindTexture(GL_TEXTURE_2D, 0)
            
            # Cache the texture
            self._texture_cache[cache_key] = int(texture_id)
            # print(f"[GL_RENDERER] Created new texture: tex_idx={texture_idx}, img_idx={image_idx}, texture_id={texture_id}, size={width}x{height}")

            return int(texture_id)
            
        except Exception as e:
            print(f"[GL_RENDERER] Failed to create texture: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _delete_buffers(self, buffers: MeshBuffers) -> None:
        """Delete OpenGL buffers."""
        if buffers.vao:
            glDeleteVertexArrays(1, [buffers.vao])
        if buffers.vbo_position:
            glDeleteBuffers(1, [buffers.vbo_position])
        if buffers.vbo_normal:
            glDeleteBuffers(1, [buffers.vbo_normal])
        if buffers.vbo_joints:
            glDeleteBuffers(1, [buffers.vbo_joints])
        if buffers.vbo_weights:
            glDeleteBuffers(1, [buffers.vbo_weights])
        if buffers.vbo_texcoord:
            glDeleteBuffers(1, [buffers.vbo_texcoord])
        if buffers.ebo:
            glDeleteBuffers(1, [buffers.ebo])
        # Note: We don't delete textures here as they're cached and may be shared

    def cleanup(self) -> None:
        """Clean up OpenGL resources."""
        for buffers in self._sub_mesh_buffers:
            self._delete_buffers(buffers)
        self._sub_mesh_buffers = []

        if self._mesh_buffers is not None:
            self._delete_buffers(self._mesh_buffers)
            self._mesh_buffers = None

        # Clean up cached textures
        for texture_id in self._texture_cache.values():
            glDeleteTextures([texture_id])
        self._texture_cache = {}

        if self._program is not None:
            glDeleteProgram(self._program)
            self._program = None

        self._initialized = False

    # -------------------------------------------------------------------------
    # Distance Gradient API
    # -------------------------------------------------------------------------

    def set_distance_gradient_enabled(self, enabled: bool) -> None:
        """Enable or disable distance gradient overlay."""
        self._distance_gradient_enabled = enabled

    def is_distance_gradient_enabled(self) -> bool:
        """Check if distance gradient overlay is enabled."""
        return self._distance_gradient_enabled

    def set_distance_range(self, near: float, far: float) -> None:
        """Set the near and far distance range for the gradient.

        Args:
            near: Distance where gradient starts (color = near color)
            far: Distance where gradient ends (color = far color)
        """
        self._distance_near = max(0.1, near)
        self._distance_far = max(self._distance_near + 0.1, far)

    def set_gradient_colors(self, near_color: Tuple[float, float, float],
                            far_color: Tuple[float, float, float]) -> None:
        """Set the gradient colors.

        Args:
            near_color: RGB color for near distance (values 0.0-1.0)
            far_color: RGB color for far distance (values 0.0-1.0)
        """
        self._gradient_color_near = near_color
        self._gradient_color_far = far_color

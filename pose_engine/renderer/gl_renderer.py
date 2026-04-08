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

out vec3 v_normal;
out vec3 v_position;

uniform mat4 u_model;
uniform mat4 u_view;
uniform mat4 u_projection;
uniform vec4 u_bone_dqs[200];  // 100 bones * 2 vec4s per bone

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

    gl_Position = u_projection * u_view * u_model * vec4(skinned_pos, 1.0);
}
"""

# Fragment shader with basic lighting
FRAGMENT_SHADER = """
#version 330 core

in vec3 v_normal;
in vec3 v_position;

out vec4 frag_color;

uniform vec3 u_light_dir;
uniform vec3 u_light_color;
uniform vec3 u_ambient;
uniform vec3 u_diffuse_color;

void main() {
    vec3 normal = normalize(v_normal);
    
    // Diffuse lighting
    float diff = max(dot(normal, normalize(u_light_dir)), 0.0);
    vec3 diffuse = diff * u_light_color * u_diffuse_color;
    
    // Ambient
    vec3 ambient = u_ambient * u_diffuse_color;
    
    vec3 result = ambient + diffuse;
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
        self.ebo: int = 0
        self.index_count: int = 0
        self.vertex_count: int = 0
        self.has_skinning: bool = False


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
            self._mesh_buffers: Optional[MeshBuffers] = None
            self._initialized: bool = False
            self._bone_matrices: List[Mat4] = []
    
            # Shader uniform locations
            self._u_model: int = -1
            self._u_view: int = -1
            self._u_projection: int = -1
            self._u_light_dir: int = -1
            self._u_light_color: int = -1
            self._u_ambient: int = -1
            self._u_diffuse_color: int = -1
            self._u_bone_dqs: int = -1
    
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
                
                self._initialized = True
                return True
                
            except Exception as e:
                print(f"Failed to initialize renderer: {e}")
                return False
    
    def upload_mesh(self, positions: List[Vec3], normals: List[Vec3],
                    indices: List[int], skinning_data: Optional[SkinningData] = None) -> bool:
        """
        Upload mesh data to GPU.
        
        Args:
            positions: Vertex positions
            normals: Vertex normals
            indices: Triangle indices
            skinning_data: Optional skinning data for skeletal animation
        
        Returns:
            True if upload succeeded
        """
        if not self._initialized:
            return False
        
        # Clean up old buffers
        if self._mesh_buffers is not None:
            self._delete_buffers(self._mesh_buffers)
        
        self._mesh_buffers = MeshBuffers()
        buffers = self._mesh_buffers
        
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
    
    def render(self, skeleton: Optional[Skeleton],
                view_matrix: Mat4, projection_matrix: Mat4,
                model_matrix: Optional[Mat4] = None) -> None:
        """
        Render the mesh.

        Args:
            skeleton: Skeleton for bone matrices (can be None for static mesh)
            view_matrix: Camera view matrix
            projection_matrix: Camera projection matrix
            model_matrix: Optional model transform (default: identity)
        """
        if not self._initialized or self._mesh_buffers is None:
            return

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
        glUniform3f(self._u_diffuse_color, 0.8, 0.8, 0.8)

        # Set bone dual quaternions
        if skeleton is not None and self._mesh_buffers.has_skinning:
            bone_dqs = []
            for bone in skeleton:
                mat = bone.get_final_matrix()
                dq = self._matrix_to_dual_quat(mat)
                bone_dqs.extend(dq)

            # Pad to 100 bones (200 vec4s)
            while len(bone_dqs) < 200 * 4:
                bone_dqs.extend([0.0, 0.0, 0.0, 1.0]) # Identity quaternion (x,y,z,w)
                bone_dqs.extend([0.0, 0.0, 0.0, 0.0]) # Zero dual part

            glUniform4fv(self._u_bone_dqs, 200, bone_dqs[:800])

        # Draw with VAO error handling for offscreen rendering
        try:
            glBindVertexArray(self._mesh_buffers.vao)
            glDrawElements(GL_TRIANGLES, self._mesh_buffers.index_count, GL_UNSIGNED_INT, None)
            glBindVertexArray(0)
        except Exception as e:
            print(f"[GL_RENDERER] VAO binding failed (likely offscreen context issue): {e}")
            # Fall back to immediate mode binding for offscreen rendering
            self._render_without_vao()
            
    def _render_without_vao(self) -> None:
        """Fallback rendering without VAO for offscreen contexts."""
        if not self._mesh_buffers:
            return
            
        try:
            print("[GL_RENDERER] Using fallback rendering without VAO")
            
            # Manually bind buffers (immediate mode style)
            # Position attribute (location 0)
            glBindBuffer(GL_ARRAY_BUFFER, self._mesh_buffers.vbo_position)
            glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 0, None)
            glEnableVertexAttribArray(0)
            
            # Normal attribute (location 1) 
            glBindBuffer(GL_ARRAY_BUFFER, self._mesh_buffers.vbo_normal)
            glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, 0, None)
            glEnableVertexAttribArray(1)
            
            # Skinning attributes if available
            if self._mesh_buffers.has_skinning:
                # Joint indices (location 2)
                glBindBuffer(GL_ARRAY_BUFFER, self._mesh_buffers.vbo_joints)
                glVertexAttribPointer(2, 4, GL_FLOAT, GL_FALSE, 0, None)
                glEnableVertexAttribArray(2)
                
                # Joint weights (location 3)
                glBindBuffer(GL_ARRAY_BUFFER, self._mesh_buffers.vbo_weights)
                glVertexAttribPointer(3, 4, GL_FLOAT, GL_FALSE, 0, None)
                glEnableVertexAttribArray(3)
            
            # Bind index buffer and draw
            glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self._mesh_buffers.ebo)
            glDrawElements(GL_TRIANGLES, self._mesh_buffers.index_count, GL_UNSIGNED_INT, None)
            
            # Cleanup
            glDisableVertexAttribArray(0)
            glDisableVertexAttribArray(1)
            if self._mesh_buffers.has_skinning:
                glDisableVertexAttribArray(2)
                glDisableVertexAttribArray(3)
            
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
        if buffers.ebo:
            glDeleteBuffers(1, [buffers.ebo])
    
    def cleanup(self) -> None:
        """Clean up OpenGL resources."""
        if self._mesh_buffers is not None:
            self._delete_buffers(self._mesh_buffers)
            self._mesh_buffers = None
        
        if self._program is not None:
            glDeleteProgram(self._program)
            self._program = None
        
        self._initialized = False

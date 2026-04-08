"""
Skinning - Linear Blend Skinning and Dual Quaternion Skinning
==============================================================

Applies bone transformations to mesh vertices.
Supports both Linear Blend Skinning (LBS) and Dual Quaternion Skinning (DQS).

LBS formula: v' = Σ(w_i * M_i * v)
DQS formula: v' = DQB * v (where DQB is the blended dual quaternion)

DQS preserves volume better and avoids the "candy wrapper" artifact.
"""

from typing import List, Tuple
from .vec3 import Vec3
from .mat4 import Mat4
from .quat import Quat


class DualQuat:
    """
    Dual Quaternion for rigid transformations.
    
    A dual quaternion combines two quaternions:
    - q_real: represents the rotation
    - q_dual: represents the translation
    
    This allows smooth blending of rotations and translations together,
    avoiding the volume loss artifacts of Linear Blend Skinning.
    """
    
    __slots__ = ('real', 'dual')
    
    def __init__(self, real: Quat = None, dual: Quat = None):
        """Create a dual quaternion from real and dual quaternions."""
        self.real = real if real is not None else Quat(1, 0, 0, 0)
        self.dual = dual if dual is not None else Quat(0, 0, 0, 0)
    
    @classmethod
    def from_matrix(cls, mat: Mat4) -> 'DualQuat':
        """
        Convert a 4x4 transformation matrix to a dual quaternion.
        
        Args:
            mat: 4x4 transformation matrix (column-major)
        
        Returns:
            DualQuat representing the same transformation
        """
        # Extract rotation quaternion from the matrix
        real = Quat.from_matrix(mat)
        real = real.normalized()
        
        # Extract translation from the matrix
        tx = mat.m[12]
        ty = mat.m[13]
        tz = mat.m[14]
        
        # Compute dual quaternion for translation
        # q_dual = 0.5 * (0, tx, ty, tz) * q_real
        t_quat = Quat(0, tx, ty, tz)
        dual = t_quat * real
        dual = Quat(dual.w * 0.5, dual.x * 0.5, dual.y * 0.5, dual.z * 0.5)
        
        return cls(real, dual)
    
    def normalized(self) -> 'DualQuat':
        """Return a normalized dual quaternion."""
        norm = self.real.length()
        if norm < 1e-10:
            return DualQuat(Quat(1, 0, 0, 0), Quat(0, 0, 0, 0))
        return DualQuat(
            Quat(self.real.w / norm, self.real.x / norm, 
                 self.real.y / norm, self.real.z / norm),
            Quat(self.dual.w / norm, self.dual.x / norm,
                 self.dual.y / norm, self.dual.z / norm)
        )
    
    def __add__(self, other: 'DualQuat') -> 'DualQuat':
        """Add two dual quaternions."""
        return DualQuat(
            Quat(self.real.w + other.real.w,
                 self.real.x + other.real.x,
                 self.real.y + other.real.y,
                 self.real.z + other.real.z),
            Quat(self.dual.w + other.dual.w,
                 self.dual.x + other.dual.x,
                 self.dual.y + other.dual.y,
                 self.dual.z + other.dual.z)
        )
    
    def __mul__(self, scalar: float) -> 'DualQuat':
        """Multiply dual quaternion by a scalar."""
        return DualQuat(
            Quat(self.real.w * scalar, self.real.x * scalar,
                 self.real.y * scalar, self.real.z * scalar),
            Quat(self.dual.w * scalar, self.dual.x * scalar,
                 self.dual.y * scalar, self.dual.z * scalar)
        )
    
    def transform_point(self, p: Vec3) -> Vec3:
        """
        Transform a point by this dual quaternion.
        
        Args:
            p: Point to transform
        
        Returns:
            Transformed point
        """
        # Normalize the dual quaternion
        n = self.normalized()
        
        # Extract translation from dual quaternion
        # translation = 2 * (q_dual * q_real.conjugate()).xyz
        # where conjugate flips x, y, z but not w
        conj = Quat(n.real.w, -n.real.x, -n.real.y, -n.real.z)
        t_quat = n.dual * conj
        t_quat = Quat(t_quat.w * 2, t_quat.x * 2, t_quat.y * 2, t_quat.z * 2)
        translation = Vec3(t_quat.x, t_quat.y, t_quat.z)
        
        # Apply rotation
        rotated = n.real.rotate_vector(p)
        
        return rotated + translation
    
    def transform_vector(self, v: Vec3) -> Vec3:
        """Transform a vector (direction only, no translation)."""
        n = self.normalized()
        return n.real.rotate_vector(v)


class VertexSkinning:
    """
    Stores skinning data for a single vertex.

    A vertex can be influenced by multiple bones.
    Each bone has a weight (0.0 to 1.0), and weights sum to 1.0.
    """

    __slots__ = ('bone_indices', 'weights', 'max_influences')

    def __init__(self, max_influences: int = 4):
        """
        Create a new vertex skinning.

        Args:
            max_influences: Maximum number of bone influences (default 4)
        """
        self.bone_indices: List[int] = []
        self.weights: List[float] = []
        self.max_influences = max_influences

    def add_influence(self, bone_index: int, weight: float) -> None:
        """
        Add a bone influence.

        Args:
            bone_index: Index of the bone
            weight: Weight of this bone's influence (0.0 to 1.0)
        """
        if len(self.bone_indices) >= self.max_influences:
            # Replace smallest weight if new weight is larger
            min_idx = 0
            min_weight = self.weights[0]
            for i, w in enumerate(self.weights):
                if w < min_weight:
                    min_idx = i
                    min_weight = w
            if weight > min_weight:
                self.bone_indices[min_idx] = bone_index
                self.weights[min_idx] = weight
        else:
            self.bone_indices.append(bone_index)
            self.weights.append(weight)

    def normalize_weights(self) -> None:
        """Normalize weights so they sum to 1.0."""
        total = sum(self.weights)
        if total > 0.0001:
            self.weights = [w / total for w in self.weights]
        elif len(self.weights) > 0:
            # Equal weights if total is near zero
            equal = 1.0 / len(self.weights)
            self.weights = [equal] * len(self.weights)

    def get_influences(self) -> List[Tuple[int, float]]:
        """Get list of (bone_index, weight) tuples."""
        return list(zip(self.bone_indices, self.weights))

    def __repr__(self) -> str:
        pairs = [f"({idx}:{w:.3f})" for idx, w in zip(self.bone_indices, self.weights)]
        return f"VertexSkinning([{', '.join(pairs)}])"


class SkinningData:
    """
    Stores skinning data for an entire mesh.

    Contains:
    - Vertex skinning data (bone indices and weights per vertex)
    - Bone matrices for skinning
    """

    def __init__(self, vertex_count: int = 0):
        """
        Create skinning data.

        Args:
            vertex_count: Number of vertices in the mesh
        """
        self._vertex_skinning: List[VertexSkinning] = [
            VertexSkinning() for _ in range(vertex_count)
        ]
        self._bone_matrices: List[Mat4] = []
        self._bone_dual_quats: List[DualQuat] = []

    def set_vertex_count(self, count: int) -> None:
        """Set the number of vertices."""
        self._vertex_skinning = [
            VertexSkinning() for _ in range(count)
        ]

    def get_vertex_count(self) -> int:
        """Get the number of vertices."""
        return len(self._vertex_skinning)

    def get_vertex_skinning(self, vertex_index: int) -> VertexSkinning:
        """Get skinning data for a vertex."""
        return self._vertex_skinning[vertex_index]

    def set_bone_matrices(self, matrices: List[Mat4]) -> None:
        """Set the bone matrices for skinning."""
        self._bone_matrices = matrices
        # Pre-compute dual quaternions for DQS
        self._bone_dual_quats = [DualQuat.from_matrix(m) for m in matrices]

    def get_bone_matrices(self) -> List[Mat4]:
        """Get the bone matrices."""
        return self._bone_matrices

    def get_bone_dual_quats(self) -> List[DualQuat]:
        """Get the bone dual quaternions."""
        return self._bone_dual_quats

    def skin_position_lbs(self, vertex_index: int, position: Vec3) -> Vec3:
        """
        Skin a single vertex position using Linear Blend Skinning.

        Uses Linear Blend Skinning formula:
        v' = Σ(w_i * M_i * v)

        Args:
            vertex_index: Index of the vertex
            position: Original vertex position

        Returns:
            Skinned vertex position
        """
        skinning = self._vertex_skinning[vertex_index]

        if len(skinning.bone_indices) == 0:
            return position

        result = Vec3(0, 0, 0)

        for bone_idx, weight in zip(skinning.bone_indices, skinning.weights):
            if bone_idx < len(self._bone_matrices):
                matrix = self._bone_matrices[bone_idx]
                transformed = matrix.transform_point(position)
                result = result + transformed * weight

        return result

    def skin_position_dqs(self, vertex_index: int, position: Vec3) -> Vec3:
        """
        Skin a single vertex position using Dual Quaternion Skinning.

        This method preserves volume better than LBS and avoids
        the "candy wrapper" artifact at joints.

        Args:
            vertex_index: Index of the vertex
            position: Original vertex position

        Returns:
            Skinned vertex position
        """
        skinning = self._vertex_skinning[vertex_index]

        if len(skinning.bone_indices) == 0:
            return position

        # Blend dual quaternions
        blended = DualQuat()
        first_sign = 1.0

        for i, (bone_idx, weight) in enumerate(zip(skinning.bone_indices, skinning.weights)):
            if bone_idx < len(self._bone_dual_quats):
                dq = self._bone_dual_quats[bone_idx]
                
                # For the first bone, determine the sign
                if i == 0:
                    # Use the first quaternion's sign
                    first_sign = 1.0
                else:
                    # Check if we need to flip the sign for antipodal quaternions
                    # q and -q represent the same rotation
                    dot = (self._bone_dual_quats[skinning.bone_indices[0]].real.w * dq.real.w +
                           self._bone_dual_quats[skinning.bone_indices[0]].real.x * dq.real.x +
                           self._bone_dual_quats[skinning.bone_indices[0]].real.y * dq.real.y +
                           self._bone_dual_quats[skinning.bone_indices[0]].real.z * dq.real.z)
                    if dot < 0:
                        # Flip the sign
                        dq = DualQuat(
                            Quat(-dq.real.w, -dq.real.x, -dq.real.y, -dq.real.z),
                            Quat(-dq.dual.w, -dq.dual.x, -dq.dual.y, -dq.dual.z)
                        )
                
                blended = blended + dq * weight

        # Normalize and transform
        return blended.normalized().transform_point(position)

    def skin_position(self, vertex_index: int, position: Vec3, use_dqs: bool = True) -> Vec3:
        """
        Skin a single vertex position.

        Args:
            vertex_index: Index of the vertex
            position: Original vertex position
            use_dqs: If True, use Dual Quaternion Skinning; otherwise use LBS

        Returns:
            Skinned vertex position
        """
        if use_dqs:
            return self.skin_position_dqs(vertex_index, position)
        else:
            return self.skin_position_lbs(vertex_index, position)

    def skin_normal_lbs(self, vertex_index: int, normal: Vec3) -> Vec3:
        """
        Skin a vertex normal using Linear Blend Skinning.

        Uses the inverse transpose of the skinning matrices.
        For LBS, we use the same weights but apply to transformed normals.

        Args:
            vertex_index: Index of the vertex
            normal: Original vertex normal

        Returns:
            Skinned normal (not normalized)
        """
        skinning = self._vertex_skinning[vertex_index]

        if len(skinning.bone_indices) == 0:
            return normal

        result = Vec3(0, 0, 0)

        for bone_idx, weight in zip(skinning.bone_indices, skinning.weights):
            if bone_idx < len(self._bone_matrices):
                matrix = self._bone_matrices[bone_idx]
                # For normals, use the matrix's rotation part only
                transformed = matrix.transform_vector(normal)
                result = result + transformed * weight

        return result

    def skin_normal_dqs(self, vertex_index: int, normal: Vec3) -> Vec3:
        """
        Skin a vertex normal using Dual Quaternion Skinning.

        Args:
            vertex_index: Index of the vertex
            normal: Original vertex normal

        Returns:
            Skinned normal (not normalized)
        """
        skinning = self._vertex_skinning[vertex_index]

        if len(skinning.bone_indices) == 0:
            return normal

        # Blend dual quaternions (same as for positions)
        blended = DualQuat()

        for i, (bone_idx, weight) in enumerate(zip(skinning.bone_indices, skinning.weights)):
            if bone_idx < len(self._bone_dual_quats):
                dq = self._bone_dual_quats[bone_idx]
                
                if i > 0:
                    # Check if we need to flip the sign
                    dot = (self._bone_dual_quats[skinning.bone_indices[0]].real.w * dq.real.w +
                           self._bone_dual_quats[skinning.bone_indices[0]].real.x * dq.real.x +
                           self._bone_dual_quats[skinning.bone_indices[0]].real.y * dq.real.y +
                           self._bone_dual_quats[skinning.bone_indices[0]].real.z * dq.real.z)
                    if dot < 0:
                        dq = DualQuat(
                            Quat(-dq.real.w, -dq.real.x, -dq.real.y, -dq.real.z),
                            Quat(-dq.dual.w, -dq.dual.x, -dq.dual.y, -dq.dual.z)
                        )
                
                blended = blended + dq * weight

        # Normalize and transform (rotation only)
        return blended.normalized().transform_vector(normal)

    def skin_normal(self, vertex_index: int, normal: Vec3, use_dqs: bool = True) -> Vec3:
        """
        Skin a vertex normal.

        Args:
            vertex_index: Index of the vertex
            normal: Original vertex normal
            use_dqs: If True, use Dual Quaternion Skinning; otherwise use LBS

        Returns:
            Skinned normal (not normalized)
        """
        if use_dqs:
            return self.skin_normal_dqs(vertex_index, normal)
        else:
            return self.skin_normal_lbs(vertex_index, normal)


def apply_skinning(
    positions: List[Vec3],
    normals: List[Vec3],
    skinning_data: SkinningData,
    use_dqs: bool = True
) -> Tuple[List[Vec3], List[Vec3]]:
    """
    Apply skinning to a mesh.

    Args:
        positions: Original vertex positions
        normals: Original vertex normals
        skinning_data: Skinning data with bone matrices
        use_dqs: If True, use Dual Quaternion Skinning; otherwise use LBS

    Returns:
        Tuple of (skinned_positions, skinned_normals)
    """
    skinned_positions: List[Vec3] = []
    skinned_normals: List[Vec3] = []

    for i, pos in enumerate(positions):
        skinned_pos = skinning_data.skin_position(i, pos, use_dqs=use_dqs)
        skinned_positions.append(skinned_pos)

        if i < len(normals):
            skinned_nrm = skinning_data.skin_normal(i, normals[i], use_dqs=use_dqs)
            # Normalize the result
            skinned_nrm = skinned_nrm.normalized()
            skinned_normals.append(skinned_nrm)

    return skinned_positions, skinned_normals


def compute_bone_matrices_from_skeleton(skeleton, skinning_data: SkinningData) -> None:
    """
    Compute bone matrices from a skeleton and store in skinning data.

    This extracts the final skinning matrix from each bone and
    stores them in the skinning data for use during rendering.

    Args:
        skeleton: Skeleton object with bones
        skinning_data: SkinningData to store matrices in
    """
    matrices: List[Mat4] = []

    for bone in skeleton:
        matrices.append(bone.get_final_matrix())

    skinning_data.set_bone_matrices(matrices)

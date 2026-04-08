"""
glTF Builder - Build Skeleton and Mesh from glTF Data
=====================================================

Converts parsed glTF data into pose_engine structures.
"""

from typing import List, Dict, Optional, Tuple
from ..vec3 import Vec3
from ..quat import Quat
from ..mat4 import Mat4
from ..transform import Transform
from ..bone import Bone
from ..skeleton import Skeleton
from ..skinning import SkinningData, VertexSkinning
from .loader import GLBData, GLBLoader


class MeshData:
    """Holds mesh data ready for rendering."""
    
    def __init__(self):
        self.positions: List[Vec3] = []
        self.normals: List[Vec3] = []
        self.indices: List[int] = []
        self.skinning_data: Optional[SkinningData] = None
        self.bone_mapping: Dict[int, int] = {}  # glTF node index -> bone index


def build_skeleton_from_gltf(
    glb_data: GLBData,
    skin_index: int = 0,
    loader: Optional[GLBLoader] = None
) -> Tuple[Skeleton, Dict[int, int]]:
    """
    Build a Skeleton from glTF skin data.

    Args:
        glb_data: Parsed GLB data
        skin_index: Index of skin to use (default 0)
        loader: GLBLoader instance (optional, for accessing data)

    Returns:
        Tuple of (Skeleton, node_to_bone_mapping)

    Note:
        If the model has no skins, returns an empty skeleton with a single
        placeholder bone for the mesh hierarchy.
    """
    # Handle models without skins - create a placeholder skeleton
    if len(glb_data.skins) == 0:
        skeleton = Skeleton()
        # Create a single root bone for static meshes
        root_bone = skeleton.add_bone("root")
        root_bone.bind_transform.position = Vec3(0, 0, 0)
        root_bone.bind_transform.rotation = Quat(1, 0, 0, 0)
        root_bone.bind_transform.scale = Vec3(1, 1, 1)
        root_bone.inverse_bind_matrix = root_bone.bind_transform.to_matrix().inverse()
        skeleton.update_all_transforms()
        # Return empty mapping - mesh vertices won't have skinning data
        return skeleton, {}

    if skin_index >= len(glb_data.skins):
        raise ValueError(f"Skin index {skin_index} out of range (model has {len(glb_data.skins)} skins)")

    skin = glb_data.skins[skin_index]
    skeleton = Skeleton()

    # Get inverse bind matrices if available
    inverse_bind_matrices: List[List[float]] = []
    if skin.inverse_bind_matrices is not None:
        if loader is None:
            loader = GLBLoader()
            loader._data = glb_data
        inverse_bind_matrices = loader.get_inverse_bind_matrices(skin.inverse_bind_matrices)

    # Create bones for each joint
    node_to_bone: Dict[int, int] = {}

    for i, joint_node_index in enumerate(skin.joints):
        node = glb_data.nodes[joint_node_index]

        # Add bone to skeleton
        bone = skeleton.add_bone(node.name)
        node_to_bone[joint_node_index] = i

        # Set bind transform from node's TRS or matrix
        # In glTF, the node's transform IS the local transform relative to parent
        if node.matrix:
            # Full matrix provided
            mat = Mat4(node.matrix)
            bone.bind_transform.position = mat.get_translation()
            bone.bind_transform.rotation = mat.get_rotation()
            bone.bind_transform.scale = mat.get_scale()
        else:
            # TRS provided
            bone.bind_transform.position = Vec3(
                node.translation[0],
                node.translation[1],
                node.translation[2]
            )
            bone.bind_transform.rotation = Quat(
                node.rotation[3], # w
                node.rotation[0], # x
                node.rotation[1], # y
                node.rotation[2] # z
            )
            bone.bind_transform.scale = Vec3(
                node.scale[0],
                node.scale[1],
                node.scale[2]
            )

        # Set inverse bind matrix
        if i < len(inverse_bind_matrices):
            bone.inverse_bind_matrix = Mat4(inverse_bind_matrices[i])
        else:
            # Compute inverse bind matrix
            bone.inverse_bind_matrix = bone.bind_transform.to_matrix().inverse()

    # Build hierarchy
    # We need to find parent-child relationships within the joint set
    for joint_node_index in skin.joints:
        node = glb_data.nodes[joint_node_index]
        bone_index = node_to_bone[joint_node_index]
        bone = skeleton.get_bone_by_index(bone_index)

        # Find children that are also in the joint set
        for child_node_index in node.children:
            if child_node_index in node_to_bone:
                child_bone_index = node_to_bone[child_node_index]
                child_bone = skeleton.get_bone_by_index(child_bone_index)
                bone.add_child(child_bone)

    # Identify true root bones (bones with no parent in the joint set)
    # and rebuild the skeleton's root bones list
    skeleton._root_bones = []
    for joint_node_index in skin.joints:
        bone_index = node_to_bone[joint_node_index]
        bone = skeleton.get_bone_by_index(bone_index)
        if bone.parent is None:
            skeleton._root_bones.append(bone)

    # Update transforms
    skeleton.update_all_transforms()

    return skeleton, node_to_bone


def build_mesh_from_gltf(
    glb_data: GLBData,
    mesh_index: int = 0,
    primitive_index: int = 0,
    bone_mapping: Optional[Dict[int, int]] = None,
    loader: Optional[GLBLoader] = None
) -> MeshData:
    """
    Build mesh data from glTF mesh data.
    
    Args:
        glb_data: Parsed GLB data
        mesh_index: Index of mesh to use
        primitive_index: Index of primitive within mesh
        bone_mapping: Mapping from glTF node index to bone index
        loader: GLBLoader instance (optional, for accessing data)
    
    Returns:
        MeshData with positions, normals, indices, and skinning
    """
    if mesh_index >= len(glb_data.meshes):
        raise ValueError(f"Mesh index {mesh_index} out of range")
    
    mesh = glb_data.meshes[mesh_index]
    
    if primitive_index >= len(mesh.primitives):
        raise ValueError(f"Primitive index {primitive_index} out of range")
    
    primitive = mesh.primitives[primitive_index]
    attributes = primitive.get('attributes', {})
    
    mesh_data = MeshData()
    
    # Create loader if not provided
    if loader is None:
        loader = GLBLoader()
        loader._data = glb_data
    
    # Load positions
    if 'POSITION' in attributes:
        positions = loader.get_positions(attributes['POSITION'])
        mesh_data.positions = [Vec3(p[0], p[1], p[2]) for p in positions]
    
    # Load normals
    if 'NORMAL' in attributes:
        normals = loader.get_normals(attributes['NORMAL'])
        mesh_data.normals = [Vec3(n[0], n[1], n[2]) for n in normals]
    
    # Load indices
    if 'indices' in primitive:
        mesh_data.indices = loader.get_indices(primitive['indices'])
    
    # Load skinning data
    if 'JOINTS_0' in attributes and 'WEIGHTS_0' in attributes:
        joints = loader.get_joints(attributes['JOINTS_0'])
        weights = loader.get_weights(attributes['WEIGHTS_0'])

        mesh_data.skinning_data = SkinningData(vertex_count=len(mesh_data.positions))

        for i, (joint, weight) in enumerate(zip(joints, weights)):
            skinning = mesh_data.skinning_data.get_vertex_skinning(i)

            for j in range(4):
                bone_idx = joint[j]
                weight_val = weight[j]

                if weight_val > 0.0001:
                    # JOINTS_0 values are indices into skin.joints array,
                    # which directly corresponds to bone indices (bones are
                    # created in the same order as skin.joints)
                    # NO mapping needed - bone_idx is already correct
                    skinning.add_influence(bone_idx, weight_val)

        skinning.normalize_weights()
    
    return mesh_data


def load_glb_file(filepath: str) -> Tuple[Skeleton, MeshData]:
    """
    Convenience function to load a GLB file.
    
    Args:
        filepath: Path to the GLB file
    
    Returns:
        Tuple of (Skeleton, MeshData)
    """
    loader = GLBLoader()
    glb_data = loader.load(filepath)
    
    # Build skeleton from first skin
    skeleton, bone_mapping = build_skeleton_from_gltf(glb_data)
    
    # Build mesh from first mesh
    mesh_data = build_mesh_from_gltf(glb_data, bone_mapping=bone_mapping)
    
    return skeleton, mesh_data

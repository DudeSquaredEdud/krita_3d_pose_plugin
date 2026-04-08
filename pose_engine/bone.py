"""
Bone - Single Bone in a Skeleton
=================================

A bone has:
- Bind pose: The original position/rotation from the model file
- Pose transform: The user's modifications for posing

Key concept: We NEVER modify the bind pose. We only modify the pose transform.
The final world transform is: parent_world * bind * pose
"""

from typing import Optional, List, Dict
from .transform import Transform
from .vec3 import Vec3
from .quat import Quat
from .mat4 import Mat4


class Bone:
    """
    A single bone in a skeleton hierarchy.
    
    Bones have two transforms:
    1. bind_transform: The original pose from the model file (NEVER modified)
    2. pose_transform: User modifications for posing
    
    The final world transform combines: parent_world * bind * pose
    """
    
    __slots__ = (
        'name', 'index', 
        'bind_transform', 'inverse_bind_matrix',
        'pose_transform',
        'parent', 'children',
        '_world_transform', '_world_dirty',
        '_final_matrix', '_final_dirty'
    )
    
    def __init__(self, name: str, index: int):
        """
        Create a new bone.
        
        Args:
            name: Bone name (from model file)
            index: Index in skeleton's bone list
        """
        self.name = name
        self.index = index
        
        # Bind pose (from model file, NEVER modified)
        self.bind_transform = Transform()
        self.inverse_bind_matrix: Optional[Mat4] = None
        
        # Pose transform (user modifications)
        self.pose_transform = Transform()
        
        # Hierarchy
        self.parent: Optional['Bone'] = None
        self.children: List['Bone'] = []
        
        # Cached world transform (computed from hierarchy)
        self._world_transform: Optional[Transform] = None
        self._world_dirty: bool = True
        
        # Cached final matrix for skinning
        self._final_matrix: Optional[Mat4] = None
        self._final_dirty: bool = True
    
    def __repr__(self) -> str:
        return f"Bone('{self.name}', index={self.index})"
    
    # -------------------------------------------------------------------------
    # Hierarchy Management
    # -------------------------------------------------------------------------
    
    def add_child(self, child: 'Bone') -> None:
        """Add a child bone. Updates parent reference."""
        if child.parent is not None:
            child.parent.remove_child(child)
        child.parent = self
        if child not in self.children:
            self.children.append(child)
        child._mark_dirty()
    
    def remove_child(self, child: 'Bone') -> None:
        """Remove a child bone."""
        if child in self.children:
            self.children.remove(child)
            child.parent = None
            child._mark_dirty()
    
    def _mark_dirty(self) -> None:
        """Mark this bone and all descendants as dirty."""
        self._world_dirty = True
        self._final_dirty = True
        for child in self.children:
            child._mark_dirty()
    
    # -------------------------------------------------------------------------
    # Transform Computation
    # -------------------------------------------------------------------------
    
    def get_world_transform(self) -> Transform:
        """
        Get the world-space transform of this bone.

        This is: parent_world * (bind * pose)

        For posing, the pose transform is applied AFTER the bind transform.
        This means the pose rotation is applied in the bone's local space
        (after the bind rotation).

        Uses dirty flags to avoid redundant computation.
        """
        if not self._world_dirty and self._world_transform is not None:
            return self._world_transform

        # Compute local transform: bind * pose
        # For posing, pose is applied AFTER bind (in bind's local space)
        # Quaternion order: pose * bind (pose applied after bind)
        local = Transform()
        # Position: bind position + (bind rotation * pose position * bind scale)
        local._position = self.bind_transform.position + self.bind_transform.rotation.rotate_vector(self.pose_transform.position)
        # Rotation: pose * bind (pose applied after bind)
        local._rotation = self.pose_transform.rotation * self.bind_transform.rotation
        # Scale: bind scale * pose scale
        local._scale = Vec3(
            self.bind_transform.scale.x * self.pose_transform.scale.x,
            self.bind_transform.scale.y * self.pose_transform.scale.y,
            self.bind_transform.scale.z * self.pose_transform.scale.z
        )
        local._matrix_dirty = True

        # Apply parent's world transform
        if self.parent is not None:
            parent_world = self.parent.get_world_transform()
            self._world_transform = Transform.multiply(parent_world, local)
        else:
            self._world_transform = local

        self._world_dirty = False
        return self._world_transform
    
    def get_final_matrix(self) -> Mat4:
        """
        Get the final skinning matrix for this bone.
        
        This is: world_transform * inverse_bind_matrix
        
        This matrix transforms vertices from bind pose to posed space.
        """
        if not self._final_dirty and self._final_matrix is not None:
            return self._final_matrix
        
        world = self.get_world_transform().to_matrix()
        
        if self.inverse_bind_matrix is not None:
            self._final_matrix = world * self.inverse_bind_matrix
        else:
            self._final_matrix = world
        
        self._final_dirty = False
        return self._final_matrix
    
    def get_world_position(self) -> Vec3:
        """Get the world-space position of this bone."""
        return self.get_world_transform().position
    
    def get_world_rotation(self) -> Quat:
        """Get the world-space rotation of this bone."""
        return self.get_world_transform().rotation
    
    # -------------------------------------------------------------------------
    # Pose Modification
    # -------------------------------------------------------------------------
    
    def set_pose_position(self, position: Vec3) -> None:
        """Set the pose position (user modification)."""
        self.pose_transform.position = position
        self._mark_dirty()
    
    def set_pose_rotation(self, rotation: Quat) -> None:
        """Set the pose rotation (user modification)."""
        self.pose_transform.rotation = rotation
        self._mark_dirty()
    
    def set_pose_scale(self, scale: Vec3) -> None:
        """Set the pose scale (user modification)."""
        self.pose_transform.scale = scale
        self._mark_dirty()
    
    def reset_pose(self) -> None:
        """Reset pose to identity (no modification from bind pose)."""
        self.pose_transform = Transform()
        self._mark_dirty()
    
    # -------------------------------------------------------------------------
    # Utility Methods
    # -------------------------------------------------------------------------
    
    def get_tail_position(self, length: float) -> Vec3:
        """
        Get the tail position of this bone.
        
        Bones are visualized as lines from head to tail.
        The tail is along the bone's local Y axis (common in Blender).
        
        Args:
            length: Bone length (usually computed from children)
        
        Returns:
            World-space position of the bone tail
        """
        world = self.get_world_transform()
        # Bone points along local Y axis (Blender convention)
        local_tail = Vec3(0, length, 0)
        return world.transform_point(local_tail)
    
    def get_depth(self) -> int:
        """Get the depth of this bone in the hierarchy (root = 0)."""
        depth = 0
        current = self.parent
        while current is not None:
            depth += 1
            current = current.parent
        return depth
    
    def is_ancestor_of(self, other: 'Bone') -> bool:
        """Check if this bone is an ancestor of another bone."""
        current = other.parent
        while current is not None:
            if current is self:
                return True
            current = current.parent
        return False
    
    def get_all_descendants(self) -> List['Bone']:
        """Get all descendant bones (children, grandchildren, etc.)."""
        descendants: List['Bone'] = []
        self._collect_descendants(descendants)
        return descendants
    
    def _collect_descendants(self, out_list: List['Bone']) -> None:
        """Recursively collect descendants."""
        for child in self.children:
            out_list.append(child)
            child._collect_descendants(out_list)

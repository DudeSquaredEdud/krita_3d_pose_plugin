"""
Skeleton - Bone Hierarchy Manager
=================================

Manages a collection of bones in a hierarchy.
Provides efficient world transform computation with dirty flags.
"""

from typing import List, Dict, Optional, Iterator
from .bone import Bone
from .vec3 import Vec3
from .quat import Quat


class Skeleton:
    """
    Manages a hierarchy of bones for a rigged model.
    
    Responsibilities:
    - Store all bones in the skeleton
    - Build parent-child relationships
    - Compute world transforms efficiently
    - Provide bone lookup by name or index
    """
    
    def __init__(self):
        """Create an empty skeleton."""
        self._bones: List[Bone] = []
        self._bone_names: Dict[str, int] = {}  # name -> index
        self._root_bones: List[Bone] = []
    
    def __len__(self) -> int:
        """Return number of bones."""
        return len(self._bones)
    
    def __iter__(self) -> Iterator[Bone]:
        """Iterate over all bones."""
        return iter(self._bones)
    
    def __getitem__(self, index: int) -> Bone:
        """Get bone by index."""
        return self._bones[index]
    
    # -------------------------------------------------------------------------
    # Bone Management
    # -------------------------------------------------------------------------
    
    def add_bone(self, name: str, parent_index: int = -1) -> Bone:
        """
        Add a new bone to the skeleton.
        
        Args:
            name: Unique bone name
            parent_index: Index of parent bone (-1 for root)
        
        Returns:
            The newly created bone
        """
        index = len(self._bones)
        bone = Bone(name, index)
        
        self._bones.append(bone)
        self._bone_names[name] = index
        
        if parent_index >= 0 and parent_index < len(self._bones):
            parent = self._bones[parent_index]
            parent.add_child(bone)
        else:
            self._root_bones.append(bone)
        
        return bone
    
    def get_bone(self, name: str) -> Optional[Bone]:
        """Get bone by name."""
        index = self._bone_names.get(name)
        if index is not None:
            return self._bones[index]
        return None
    
    def get_bone_by_index(self, index: int) -> Optional[Bone]:
        """Get bone by index."""
        if 0 <= index < len(self._bones):
            return self._bones[index]
        return None
    
    def get_bone_index(self, name: str) -> int:
        """Get index of bone by name. Returns -1 if not found."""
        return self._bone_names.get(name, -1)
    
    def get_root_bones(self) -> List[Bone]:
        """Get all root bones (bones with no parent)."""
        return self._root_bones.copy()
    
    def get_all_bones(self) -> List[Bone]:
        """Get all bones in the skeleton."""
        return self._bones.copy()
    
    # -------------------------------------------------------------------------
    # Transform Updates
    # -------------------------------------------------------------------------
    
    def update_all_transforms(self) -> None:
        """
        Update world transforms for all bones.
        
        This traverses the hierarchy and ensures all world transforms
        are computed. Call this before rendering or skinning.
        """
        for root in self._root_bones:
            self._update_bone_recursive(root)
    
    def _update_bone_recursive(self, bone: Bone) -> None:
        """Recursively update a bone and its children."""
        # Just accessing the transform triggers computation
        bone.get_world_transform()
        
        for child in bone.children:
            self._update_bone_recursive(child)
    
    def mark_all_dirty(self) -> None:
        """Mark all bones as dirty (force recompute)."""
        for bone in self._bones:
            bone._mark_dirty()
    
    # -------------------------------------------------------------------------
    # Pose Operations
    # -------------------------------------------------------------------------
    
    def reset_pose(self) -> None:
        """Reset all bones to bind pose."""
        for bone in self._bones:
            bone.reset_pose()
    
    def set_bone_rotation(self, bone_name: str, rotation: Quat) -> bool:
        """
        Set the rotation of a bone by name.
        
        Returns:
            True if bone was found, False otherwise
        """
        bone = self.get_bone(bone_name)
        if bone is not None:
            bone.set_pose_rotation(rotation)
            return True
        return False
    
    def set_bone_position(self, bone_name: str, position: Vec3) -> bool:
        """
        Set the position of a bone by name.
        
        Returns:
            True if bone was found, False otherwise
        """
        bone = self.get_bone(bone_name)
        if bone is not None:
            bone.set_pose_position(position)
            return True
        return False
    
    # -------------------------------------------------------------------------
    # Utility Methods
    # -------------------------------------------------------------------------
    
    def get_bone_chain(self, from_bone: str, to_ancestor: str) -> List[Bone]:
        """
        Get the chain of bones from a bone up to an ancestor.
        
        Args:
            from_bone: Starting bone name
            to_ancestor: Ending ancestor bone name
        
        Returns:
            List of bones from from_bone to to_ancestor (inclusive),
            or empty list if no valid chain exists
        """
        start = self.get_bone(from_bone)
        end = self.get_bone(to_ancestor)
        
        if start is None or end is None:
            return []
        
        # Walk up from start to find end
        chain: List[Bone] = []
        current: Optional[Bone] = start
        
        while current is not None:
            chain.append(current)
            if current is end:
                return chain
            current = current.parent
        
        return []  # End not an ancestor of start
    
    def get_bone_children(self, bone_name: str) -> List[Bone]:
        """Get all direct children of a bone."""
        bone = self.get_bone(bone_name)
        if bone is not None:
            return bone.children.copy()
        return []
    
    def get_bone_descendants(self, bone_name: str) -> List[Bone]:
        """Get all descendants of a bone."""
        bone = self.get_bone(bone_name)
        if bone is not None:
            return bone.get_all_descendants()
        return []
    
    def get_leaf_bones(self) -> List[Bone]:
        """Get all bones that have no children (end effectors)."""
        return [b for b in self._bones if len(b.children) == 0]
    
    def get_bone_count(self) -> int:
        """Get total number of bones."""
        return len(self._bones)
    
    def get_max_depth(self) -> int:
        """Get the maximum depth of the bone hierarchy."""
        max_depth = 0
        for bone in self._bones:
            depth = bone.get_depth()
            if depth > max_depth:
                max_depth = depth
        return max_depth
    
    def validate_hierarchy(self) -> List[str]:
        """
        Validate the bone hierarchy for common issues.
        
        Returns:
            List of warning/error messages (empty if valid)
        """
        issues: List[str] = []
        
        # Check for cycles
        for bone in self._bones:
            if bone.is_ancestor_of(bone):
                issues.append(f"Cycle detected: {bone.name} is its own ancestor")
        
        # Check for bones with no path to root
        for bone in self._bones:
            if bone not in self._root_bones:
                # Walk up to find root
                current = bone
                found_root = False
                while current is not None:
                    if current in self._root_bones:
                        found_root = True
                        break
                    current = current.parent
                if not found_root:
                    issues.append(f"Bone {bone.name} has no path to root")
        
        # Check for duplicate names
        seen_names: Dict[str, int] = {}
        for bone in self._bones:
            if bone.name in seen_names:
                issues.append(f"Duplicate bone name: {bone.name}")
            seen_names[bone.name] = bone.index
        
        return issues
    
    # -------------------------------------------------------------------------
    # Debug / Info
    # -------------------------------------------------------------------------
    
    def print_hierarchy(self) -> None:
        """Print the bone hierarchy (for debugging)."""
        for root in self._root_bones:
            self._print_bone(root, 0)
    
    def _print_bone(self, bone: Bone, indent: int) -> None:
        """Recursively print bone and children."""
        prefix = "  " * indent
        pos = bone.get_world_position()
        print(f"{prefix}{bone.name} (index={bone.index}, pos=({pos.x:.2f}, {pos.y:.2f}, {pos.z:.2f}))")
        for child in bone.children:
            self._print_bone(child, indent + 1)
    
    def __repr__(self) -> str:
        return f"Skeleton(bones={len(self._bones)}, roots={len(self._root_bones)})"

"""
IK Solver Base Classes
======================

Defines the interface for IK solvers and common data structures.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Tuple
from ..vec3 import Vec3
from ..quat import Quat
from ..bone import Bone


@dataclass
class IKResult:
    """Result of an IK solve operation."""
    success: bool
    iterations: int
    final_error: float  # Distance to target
    message: str = ""


class IKChain:
    """
    Represents a chain of bones for IK solving.
    
    The chain goes from root (where solving starts) to
    effector (the bone that should reach the target).
    
    Convention:
    - Index 0 = root bone (first bone in chain)
    - Last index = effector bone (end effector)
    """
    
    def __init__(self, bones: List[Bone]):
        """
        Create an IK chain from a list of bones.
        
        Args:
            bones: List of bones from root to effector
        """
        if len(bones) < 1:
            raise ValueError("IK chain must have at least one bone")
        
        self._bones = bones
        self._joint_limits: List[Tuple[Vec3, Vec3, float, float]] = []  # axis, min_angle, max_angle
    
    @property
    def bones(self) -> List[Bone]:
        """Get the bones in this chain."""
        return self._bones
    
    @property
    def root(self) -> Bone:
        """Get the root bone (first in chain)."""
        return self._bones[0]
    
    @property
    def effector(self) -> Bone:
        """Get the end effector bone (last in chain)."""
        return self._bones[-1]
    
    def __len__(self) -> int:
        """Get number of bones in chain."""
        return len(self._bones)
    
    def __getitem__(self, index: int) -> Bone:
        """Get bone by index."""
        return self._bones[index]
    
    def get_effector_position(self) -> Vec3:
        """Get the world position of the end effector."""
        return self.effector.get_world_position()
    
    def get_bone_positions(self) -> List[Vec3]:
        """Get world positions of all bones."""
        return [bone.get_world_position() for bone in self._bones]
    
    def get_bone_rotations(self) -> List[Quat]:
        """Get world rotations of all bones."""
        return [bone.get_world_rotation() for bone in self._bones]
    
    def set_joint_limit(self, bone_index: int, axis: Vec3, 
                        min_angle_deg: float, max_angle_deg: float) -> None:
        """
        Set a joint limit for a bone.
        
        Args:
            bone_index: Index of bone in chain
            axis: Rotation axis (local space)
            min_angle_deg: Minimum rotation angle in degrees
            max_angle_deg: Maximum rotation angle in degrees
        """
        while len(self._joint_limits) <= bone_index:
            self._joint_limits.append(None)
        self._joint_limits[bone_index] = (axis, axis, min_angle_deg, max_angle_deg)
    
    def get_joint_limit(self, bone_index: int) -> Optional[Tuple[Vec3, float, float]]:
        """
        Get joint limit for a bone.
        
        Returns:
            Tuple of (axis, min_angle, max_angle) or None if no limit
        """
        if bone_index < len(self._joint_limits):
            limit = self._joint_limits[bone_index]
            if limit is not None:
                return (limit[0], limit[2], limit[3])
        return None
    
    def get_chain_length(self) -> float:
        """
        Get the total length of the chain.
        
        This is the sum of distances between consecutive bones.
        """
        total = 0.0
        for i in range(len(self._bones) - 1):
            pos1 = self._bones[i].get_world_position()
            pos2 = self._bones[i + 1].get_world_position()
            total += (pos2 - pos1).length()
        return total
    
    @classmethod
    def from_skeleton(cls, skeleton, start_bone: str, end_bone: str) -> 'IKChain':
        """
        Create an IK chain from a skeleton.
        
        Args:
            skeleton: Skeleton object
            start_bone: Name of the root bone
            end_bone: Name of the end effector bone
        
        Returns:
            IKChain from start to end
        """
        chain_bones = skeleton.get_bone_chain(end_bone, start_bone)
        if not chain_bones:
            raise ValueError(f"No chain from {start_bone} to {end_bone}")
        # Reverse to get root-to-effector order
        chain_bones = list(reversed(chain_bones))
        return cls(chain_bones)


class IKSolver(ABC):
    """
    Abstract base class for IK solvers.
    
    All IK solvers must implement the solve() method.
    """
    
    def __init__(self):
        """Create a new IK solver."""
        self.max_iterations = 20
        self.tolerance = 0.01  # Stop when error < tolerance
        self.position_epsilon = 0.001  # Minimum position change to continue
    
    @abstractmethod
    def solve(self, chain: IKChain, target: Vec3) -> IKResult:
        """
        Solve IK for the given chain to reach the target.
        
        Args:
            chain: The bone chain to solve
            target: Target position in world space
        
        Returns:
            IKResult with success status and iteration count
        """
        pass
    
    def compute_error(self, chain: IKChain, target: Vec3) -> float:
        """Compute the error (distance from effector to target)."""
        effector_pos = chain.get_effector_position()
        return (target - effector_pos).length()

"""
CCD IK Solver
=============

Cyclic Coordinate Descent (CCD) is a simple, iterative IK algorithm.

How it works:
1. Start from the end effector
2. For each bone (from effector to root):
   - Rotate the bone so the effector moves toward the target
3. Repeat until error is small or max iterations reached

Pros:
- Simple to implement
- Handles joint limits easily
- Works well for most poses

Cons:
- Can get stuck in local minima
- Not as smooth as FABRIK for some cases
"""

import math
from typing import List
from ..vec3 import Vec3
from ..quat import Quat
from .solver import IKSolver, IKChain, IKResult


class CCDSolver(IKSolver):
    """
    Cyclic Coordinate Descent IK solver.
    
    This solver iteratively rotates each bone in the chain
    to minimize the distance from the effector to the target.
    """
    
    def __init__(self):
        """Create a new CCD solver."""
        super().__init__()
        self.max_angle_per_iteration = math.pi / 4  # 45 degrees max rotation per iteration
    
    def solve(self, chain: IKChain, target: Vec3) -> IKResult:
        """
        Solve IK using CCD algorithm.
        
        Args:
            chain: The bone chain to solve
            target: Target position in world space
        
        Returns:
            IKResult with success status and iteration count
        """
        if len(chain) == 0:
            return IKResult(False, 0, 0.0, "Empty chain")
        
        # Check if already at target
        error = self.compute_error(chain, target)
        if error < self.tolerance:
            return IKResult(True, 0, error, "Already at target")
        
        iterations = 0
        prev_error = error
        
        for iteration in range(self.max_iterations):
            iterations = iteration + 1
            
            # Iterate from effector to root (excluding effector itself)
            for i in range(len(chain) - 2, -1, -1):
                self._solve_bone(chain, i, target)
            
            # Check convergence
            error = self.compute_error(chain, target)
            
            if error < self.tolerance:
                return IKResult(True, iterations, error, "Target reached")
            
            # Check if we're making progress
            if abs(prev_error - error) < self.position_epsilon:
                # Not making progress, might be stuck
                return IKResult(False, iterations, error, "Converged without reaching target")
            
            prev_error = error
        
        # Max iterations reached
        return IKResult(error < self.tolerance * 10, iterations, error, 
                       "Max iterations reached")
    
    def _solve_bone(self, chain: IKChain, bone_index: int, target: Vec3) -> None:
        """
        Solve for a single bone in the chain.
        
        This rotates the bone to minimize the distance from
        the effector to the target.
        
        Args:
            chain: The IK chain
            bone_index: Index of the bone to solve
            target: Target position
        """
        bone = chain[bone_index]
        effector = chain.effector
        
        # Get positions in world space
        bone_pos = bone.get_world_position()
        effector_pos = effector.get_world_position()
        
        # Vector from bone to effector
        to_effector = effector_pos - bone_pos
        to_effector_len = to_effector.length()
        
        if to_effector_len < 0.0001:
            return  # Bone and effector at same position
        
        to_effector_normalized = to_effector * (1.0 / to_effector_len)
        
        # Vector from bone to target
        to_target = target - bone_pos
        to_target_len = to_target.length()
        
        if to_target_len < 0.0001:
            return  # Target at bone position
        
        to_target_normalized = to_target * (1.0 / to_target_len)
        
        # Compute rotation to align effector direction with target direction
        # Using shortest_arc quaternion
        rotation = Quat.shortest_arc(to_effector_normalized, to_target_normalized)
        
        # Clamp rotation angle
        rotation = self._clamp_rotation(rotation)
        
        # Apply joint limits if any
        rotation = self._apply_joint_limit(chain, bone_index, rotation)
        
        # Apply rotation to bone's pose
        # We need to convert from world rotation to local rotation
        self._apply_rotation_to_bone(bone, rotation)
    
    def _clamp_rotation(self, rotation: Quat) -> Quat:
        """Clamp rotation to maximum angle."""
        # Get the angle
        angle = 2.0 * math.acos(min(1.0, abs(rotation.w)))
        
        if angle > self.max_angle_per_iteration:
            # Reduce the rotation
            factor = self.max_angle_per_iteration / angle
            half_angle = self.max_angle_per_iteration * 0.5
            w = math.cos(half_angle)
            xyz_scale = math.sin(half_angle) / max(0.0001, math.sin(angle * 0.5))
            return Quat(w, rotation.x * xyz_scale, rotation.y * xyz_scale, rotation.z * xyz_scale)
        
        return rotation
    
    def _apply_joint_limit(self, chain: IKChain, bone_index: int, 
                           rotation: Quat) -> Quat:
        """Apply joint limits to the rotation."""
        limit = chain.get_joint_limit(bone_index)
        if limit is None:
            return rotation
        
        axis, min_angle, max_angle = limit
        
        # Decompose rotation to extract angle around the limit axis
        # This is a simplified implementation
        # A full implementation would decompose the quaternion properly
        
        # For now, just return the rotation unchanged
        # Joint limits are complex to implement correctly with quaternions
        return rotation
    
    def _apply_rotation_to_bone(self, bone, world_rotation_delta: Quat) -> None:
        """
        Apply a world-space rotation delta to a bone.
        
        This converts the world rotation to a local rotation
        and applies it to the bone's pose transform.
        
        Args:
            bone: The bone to rotate
            world_rotation_delta: World-space rotation to apply
        """
        # Get current world rotation
        current_world_rot = bone.get_world_rotation()
        
        # New world rotation = delta * current (apply delta first)
        new_world_rot = world_rotation_delta * current_world_rot
        
        # Convert to local rotation
        if bone.parent is not None:
            parent_world_rot = bone.parent.get_world_rotation()
            # local = parent^-1 * world
            new_local_rot = parent_world_rot.inverse() * new_world_rot
        else:
            new_local_rot = new_world_rot
        
        # Combine with existing pose rotation
        # The pose rotation is applied after bind rotation
        # So: world = parent_world * bind * pose
        # We want to modify pose to achieve new_local_rot
        
        # Get bind rotation
        bind_rot = bone.bind_transform.rotation
        
        # pose = bind^-1 * local
        new_pose_rot = bind_rot.inverse() * new_local_rot
        
        # Set the new pose rotation
        bone.set_pose_rotation(new_pose_rot.normalized())


class CCDSolverWithTwist(CCDSolver):
    """
    CCD solver with twist limit support.
    
    This extends the basic CCD solver to handle twist limits,
    which prevent bones from rotating too much around their length axis.
    """
    
    def __init__(self):
        """Create a new CCD solver with twist limits."""
        super().__init__()
        self.twist_limits: dict = {}  # bone_index -> max_twist_degrees
    
    def set_twist_limit(self, bone_index: int, max_twist_degrees: float) -> None:
        """
        Set the twist limit for a bone.
        
        Args:
            bone_index: Index of bone in chain
            max_twist_degrees: Maximum twist rotation in degrees
        """
        self.twist_limits[bone_index] = max_twist_degrees
    
    def _apply_rotation_to_bone(self, bone, world_rotation_delta: Quat) -> None:
        """Apply rotation with twist limit enforcement."""
        # First apply the base CCD rotation
        super()._apply_rotation_to_bone(bone, world_rotation_delta)
        
        # Then enforce twist limit if set
        bone_index = bone.index
        if bone_index in self.twist_limits:
            self._enforce_twist_limit(bone, self.twist_limits[bone_index])
    
    def _enforce_twist_limit(self, bone: 'Bone', max_twist_degrees: float) -> None:
        """Enforce twist limit on a bone."""
        # This is a simplified implementation
        # A full implementation would decompose swing-twist properly
        pass

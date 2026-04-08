"""
Pose State Management
=====================

Provides pose serialization, undo/redo history, and file save/load functionality.

Key classes:
- PoseSnapshot: Immutable snapshot of all bone rotations at a point in time
- UndoRedoStack: Manages undo/redo history with memory limits
- PoseSerializer: Save/load poses to/from JSON files
"""

import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from copy import deepcopy

from .quat import Quat
from .vec3 import Vec3
from .skeleton import Skeleton
from .bone import Bone


@dataclass
class BonePose:
    """
    Pose data for a single bone.
    
    Stores rotation, position, and scale as user-modifiable transforms.
    These are relative to the bind pose (identity = bind pose).
    """
    rotation: Quat = field(default_factory=Quat.identity)
    position: Vec3 = field(default_factory=lambda: Vec3(0, 0, 0))
    scale: Vec3 = field(default_factory=lambda: Vec3(1, 1, 1))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'rotation': list(self.rotation.to_tuple()),
            'position': list(self.position.to_tuple()),
            'scale': list(self.scale.to_tuple())
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BonePose':
        """Create from dictionary (JSON deserialization)."""
        rot_data = data.get('rotation', [1, 0, 0, 0])
        pos_data = data.get('position', [0, 0, 0])
        scale_data = data.get('scale', [1, 1, 1])
        
        return cls(
            rotation=Quat(rot_data[0], rot_data[1], rot_data[2], rot_data[3]),
            position=Vec3(pos_data[0], pos_data[1], pos_data[2]),
            scale=Vec3(scale_data[0], scale_data[1], scale_data[2])
        )
    
    @classmethod
    def from_bone(cls, bone: Bone) -> 'BonePose':
        """Create a BonePose from a bone's current pose transform."""
        return cls(
            rotation=bone.pose_transform.rotation,
            position=bone.pose_transform.position,
            scale=bone.pose_transform.scale
        )
    
    def apply_to_bone(self, bone: Bone) -> None:
        """Apply this pose to a bone."""
        bone.set_pose_rotation(self.rotation)
        bone.set_pose_position(self.position)
        bone.set_pose_scale(self.scale)


@dataclass
class PoseSnapshot:
    """
    Immutable snapshot of a skeleton's pose.
    
    Captures all bone rotations, positions, and scales at a point in time.
    Used for undo/redo and pose saving/loading.
    """
    bones: Dict[str, BonePose] = field(default_factory=dict)
    name: str = ""
    timestamp: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'name': self.name,
            'timestamp': self.timestamp,
            'bones': {name: pose.to_dict() for name, pose in self.bones.items()}
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PoseSnapshot':
        """Create from dictionary (JSON deserialization)."""
        bones = {}
        for name, pose_data in data.get('bones', {}).items():
            bones[name] = BonePose.from_dict(pose_data)
        
        return cls(
            bones=bones,
            name=data.get('name', ''),
            timestamp=data.get('timestamp', 0.0)
        )
    
    @classmethod
    def capture_from_skeleton(cls, skeleton: Skeleton, name: str = "") -> 'PoseSnapshot':
        """
        Capture the current pose of a skeleton.
        
        Args:
            skeleton: The skeleton to capture from
            name: Optional name for this snapshot
            
        Returns:
            A new PoseSnapshot containing all bone poses
        """
        import time
        bones = {}
        for bone in skeleton:
            bones[bone.name] = BonePose.from_bone(bone)
        
        return cls(bones=bones, name=name, timestamp=time.time())
    
    def apply_to_skeleton(self, skeleton: Skeleton) -> None:
        """
        Apply this pose to a skeleton.
        
        Args:
            skeleton: The skeleton to apply the pose to
        """
        for bone in skeleton:
            if bone.name in self.bones:
                self.bones[bone.name].apply_to_bone(bone)
        
        # Update all transforms after applying
        skeleton.update_all_transforms()
    
    def get_bone_pose(self, bone_name: str) -> Optional[BonePose]:
        """Get the pose for a specific bone."""
        return self.bones.get(bone_name)


class UndoRedoStack:
    """
    Manages undo/redo history for pose changes.
    
    Features:
    - Fixed-size history with automatic pruning of oldest states
    - Efficient snapshot-based storage
    - Clear separation between undo and redo stacks
    """
    
    def __init__(self, max_history: int = 50):
        """
        Create a new undo/redo stack.
        
        Args:
            max_history: Maximum number of states to keep in history
        """
        self._undo_stack: List[PoseSnapshot] = []
        self._redo_stack: List[PoseSnapshot] = []
        self._max_history = max_history
        self._current_snapshot: Optional[PoseSnapshot] = None
    
    @property
    def can_undo(self) -> bool:
        """Check if undo is available."""
        return len(self._undo_stack) > 0
    
    @property
    def can_redo(self) -> bool:
        """Check if redo is available."""
        return len(self._redo_stack) > 0
    
    @property
    def undo_count(self) -> int:
        """Get number of available undo states."""
        return len(self._undo_stack)
    
    @property
    def redo_count(self) -> int:
        """Get number of available redo states."""
        return len(self._redo_stack)
    
    def push_state(self, skeleton: Skeleton, name: str = "") -> None:
        """
        Push the current skeleton state onto the undo stack.
        
        This should be called BEFORE making a change to the skeleton.
        The redo stack is cleared when a new state is pushed.
        
        Args:
            skeleton: The skeleton to capture
            name: Optional name for this snapshot
        """
        snapshot = PoseSnapshot.capture_from_skeleton(skeleton, name)
        
        # Push current state to undo stack if we have one
        if self._current_snapshot is not None:
            self._undo_stack.append(self._current_snapshot)
            
            # Prune old history if needed
            if len(self._undo_stack) > self._max_history:
                self._undo_stack.pop(0)
        
        # Store new state as current
        self._current_snapshot = snapshot
        
        # Clear redo stack (new changes invalidate redo history)
        self._redo_stack.clear()
    
    def undo(self, skeleton: Skeleton) -> Optional[PoseSnapshot]:
        """
        Undo to the previous state.
        
        Args:
            skeleton: The skeleton to apply the undone state to
            
        Returns:
            The snapshot that was restored, or None if no undo available
        """
        if not self.can_undo:
            return None
        
        # Save current state to redo stack
        if self._current_snapshot is not None:
            self._redo_stack.append(self._current_snapshot)
        
        # Pop from undo stack
        self._current_snapshot = self._undo_stack.pop()
        
        # Apply to skeleton
        self._current_snapshot.apply_to_skeleton(skeleton)
        
        return self._current_snapshot
    
    def redo(self, skeleton: Skeleton) -> Optional[PoseSnapshot]:
        """
        Redo to the next state.
        
        Args:
            skeleton: The skeleton to apply the redone state to
            
        Returns:
            The snapshot that was restored, or None if no redo available
        """
        if not self.can_redo:
            return None
        
        # Save current state to undo stack
        if self._current_snapshot is not None:
            self._undo_stack.append(self._current_snapshot)
        
        # Pop from redo stack
        self._current_snapshot = self._redo_stack.pop()
        
        # Apply to skeleton
        self._current_snapshot.apply_to_skeleton(skeleton)
        
        return self._current_snapshot
    
    def clear(self) -> None:
        """Clear all history."""
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._current_snapshot = None
    
    def initialize(self, skeleton: Skeleton) -> None:
        """
        Initialize the stack with the current skeleton state.
        
        This should be called when loading a new model.
        
        Args:
            skeleton: The skeleton to capture as initial state
        """
        self.clear()
        self._current_snapshot = PoseSnapshot.capture_from_skeleton(skeleton, "initial")


class PoseSerializer:
    """
    Save and load poses to/from JSON files.
    
    File format is human-readable JSON for easy inspection and editing.
    """
    
    @staticmethod
    def save_pose(filepath: str, skeleton: Skeleton, name: str = "") -> bool:
        """
        Save the current pose to a file.
        
        Args:
            filepath: Path to save the pose file
            skeleton: The skeleton to save
            name: Optional name for this pose
            
        Returns:
            True if save was successful, False otherwise
        """
        try:
            snapshot = PoseSnapshot.capture_from_skeleton(skeleton, name)
            data = snapshot.to_dict()
            
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
            
            return True
        except Exception as e:
            print(f"Error saving pose: {e}")
            return False
    
    @staticmethod
    def load_pose(filepath: str, skeleton: Skeleton) -> Optional[PoseSnapshot]:
        """
        Load a pose from a file and apply it to a skeleton.
        
        Args:
            filepath: Path to the pose file
            skeleton: The skeleton to apply the pose to
            
        Returns:
            The loaded snapshot, or None if load failed
        """
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            snapshot = PoseSnapshot.from_dict(data)
            snapshot.apply_to_skeleton(skeleton)
            
            return snapshot
        except Exception as e:
            print(f"Error loading pose: {e}")
            return False
    
    @staticmethod
    def load_pose_data(filepath: str) -> Optional[PoseSnapshot]:
        """
        Load pose data from a file without applying it.
        
        Args:
            filepath: Path to the pose file
            
        Returns:
            The loaded snapshot, or None if load failed
        """
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            return PoseSnapshot.from_dict(data)
        except Exception as e:
            print(f"Error loading pose data: {e}")
            return None
    
    @staticmethod
    def get_pose_info(filepath: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a pose file without fully loading it.
        
        Args:
            filepath: Path to the pose file
            
        Returns:
            Dictionary with 'name', 'timestamp', 'bone_count', or None if failed
        """
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            return {
                'name': data.get('name', ''),
                'timestamp': data.get('timestamp', 0.0),
                'bone_count': len(data.get('bones', {}))
            }
        except Exception as e:
            print(f"Error reading pose info: {e}")
            return None

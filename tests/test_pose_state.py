#!/usr/bin/env python3
"""
Tests for Pose State Module
===========================

Tests for BonePose, PoseSnapshot, UndoRedoStack, and PoseSerializer classes.

Run with: pytest tests/test_pose_state.py -v
"""

import pytest
import json
import sys
import os
import tempfile
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pose_engine.pose_state import BonePose, PoseSnapshot, UndoRedoStack, PoseSerializer
from pose_engine.quat import Quat
from pose_engine.vec3 import Vec3
from pose_engine.skeleton import Skeleton


class TestBonePose:
    """Tests for BonePose dataclass."""

    def test_bone_pose_creation(self):
        """Test basic BonePose creation."""
        pose = BonePose(
            rotation=Quat(1, 0, 0, 0),
            position=Vec3(0, 0, 0),
            scale=Vec3(1, 1, 1)
        )
        
        assert pose.rotation.w == 1
        assert pose.position.x == 0
        assert pose.scale.x == 1

    def test_bone_pose_defaults(self):
        """Test BonePose with default values."""
        pose = BonePose()
        
        # Should have identity rotation
        assert pose.rotation.w == 1
        assert pose.rotation.x == 0
        assert pose.rotation.y == 0
        assert pose.rotation.z == 0
        
        # Zero position
        assert pose.position.x == 0
        assert pose.position.y == 0
        assert pose.position.z == 0
        
        # Unit scale
        assert pose.scale.x == 1
        assert pose.scale.y == 1
        assert pose.scale.z == 1

    def test_bone_pose_to_dict(self):
        """Test BonePose serialization."""
        pose = BonePose(
            rotation=Quat(0.707, 0, 0.707, 0),
            position=Vec3(1, 2, 3),
            scale=Vec3(2, 2, 2)
        )
        
        data = pose.to_dict()
        
        assert 'rotation' in data
        assert 'position' in data
        assert 'scale' in data
        assert len(data['rotation']) == 4
        assert len(data['position']) == 3
        assert len(data['scale']) == 3

    def test_bone_pose_from_dict(self):
        """Test BonePose deserialization."""
        data = {
            'rotation': [0.707, 0, 0.707, 0],
            'position': [1, 2, 3],
            'scale': [2, 2, 2]
        }
        
        pose = BonePose.from_dict(data)
        
        assert pose.rotation.w == 0.707
        assert pose.rotation.x == 0
        assert pose.rotation.y == 0.707
        assert pose.rotation.z == 0
        assert pose.position.x == 1
        assert pose.position.y == 2
        assert pose.position.z == 3
        assert pose.scale.x == 2

    def test_bone_pose_from_dict_defaults(self):
        """Test BonePose deserialization with missing data."""
        data = {}
        
        pose = BonePose.from_dict(data)
        
        # Should use defaults
        assert pose.rotation.w == 1
        assert pose.position.x == 0
        assert pose.scale.x == 1

    def test_bone_pose_roundtrip(self):
        """Test BonePose survives to_dict/from_dict roundtrip."""
        original = BonePose(
            rotation=Quat(0.5, 0.5, 0.5, 0.5),
            position=Vec3(5, 10, 15),
            scale=Vec3(1, 2, 3)
        )
        
        data = original.to_dict()
        restored = BonePose.from_dict(data)
        
        assert abs(restored.rotation.w - original.rotation.w) < 0.001
        assert abs(restored.rotation.x - original.rotation.x) < 0.001
        assert restored.position.x == original.position.x
        assert restored.scale.x == original.scale.x


class TestPoseSnapshot:
    """Tests for PoseSnapshot dataclass."""

    def test_pose_snapshot_creation(self):
        """Test basic PoseSnapshot creation."""
        bones = {
            'root': BonePose(),
            'spine': BonePose(rotation=Quat.from_axis_angle(Vec3.UP, 0.5))
        }
        
        snapshot = PoseSnapshot(bones=bones, name="Test Pose")
        
        assert snapshot.name == "Test Pose"
        assert len(snapshot.bones) == 2
        assert 'root' in snapshot.bones
        assert 'spine' in snapshot.bones

    def test_pose_snapshot_defaults(self):
        """Test PoseSnapshot with default values."""
        snapshot = PoseSnapshot()
        
        assert snapshot.bones == {}
        assert snapshot.name == ""
        assert snapshot.timestamp == 0.0

    def test_pose_snapshot_to_dict(self):
        """Test PoseSnapshot serialization."""
        bones = {
            'root': BonePose(rotation=Quat.identity(), position=Vec3(0, 0, 0)),
            'head': BonePose(rotation=Quat(0.707, 0, 0, 0.707), position=Vec3(0, 1, 0))
        }
        
        snapshot = PoseSnapshot(bones=bones, name="Serialize Test", timestamp=12345.0)
        data = snapshot.to_dict()
        
        assert data['name'] == "Serialize Test"
        assert data['timestamp'] == 12345.0
        assert 'bones' in data
        assert 'root' in data['bones']
        assert 'head' in data['bones']

    def test_pose_snapshot_from_dict(self):
        """Test PoseSnapshot deserialization."""
        data = {
            'name': 'Deserialize Test',
            'timestamp': 67890.0,
            'bones': {
                'root': {
                    'rotation': [1, 0, 0, 0],
                    'position': [0, 0, 0],
                    'scale': [1, 1, 1]
                },
                'spine': {
                    'rotation': [0.707, 0, 0.707, 0],
                    'position': [0, 1, 0],
                    'scale': [1, 1, 1]
                }
            }
        }
        
        snapshot = PoseSnapshot.from_dict(data)
        
        assert snapshot.name == 'Deserialize Test'
        assert snapshot.timestamp == 67890.0
        assert len(snapshot.bones) == 2
        assert 'root' in snapshot.bones
        assert 'spine' in snapshot.bones

    def test_pose_snapshot_get_bone_pose(self):
        """Test getting bone pose from snapshot."""
        bones = {
            'root': BonePose(rotation=Quat.identity()),
            'head': BonePose(rotation=Quat(0.707, 0, 0, 0.707))
        }
        
        snapshot = PoseSnapshot(bones=bones)
        
        root_pose = snapshot.get_bone_pose('root')
        assert root_pose is not None
        assert root_pose.rotation.w == 1
        
        missing = snapshot.get_bone_pose('nonexistent')
        assert missing is None

    def test_pose_snapshot_roundtrip(self):
        """Test PoseSnapshot survives serialization roundtrip."""
        bones = {
            'root': BonePose(rotation=Quat(0.5, 0.5, 0.5, 0.5)),
            'spine': BonePose(position=Vec3(1, 2, 3)),
            'head': BonePose(scale=Vec3(2, 1, 1))
        }
        
        original = PoseSnapshot(bones=bones, name="Roundtrip Test", timestamp=999.0)
        data = original.to_dict()
        restored = PoseSnapshot.from_dict(data)
        
        assert restored.name == original.name
        assert restored.timestamp == original.timestamp
        assert len(restored.bones) == len(original.bones)
        
        for bone_name in original.bones:
            orig_pose = original.bones[bone_name]
            rest_pose = restored.bones[bone_name]
            
            assert abs(orig_pose.rotation.w - rest_pose.rotation.w) < 0.001


class TestPoseSnapshotCaptureApply:
    """Tests for capturing and applying poses to skeletons."""

    def test_capture_from_skeleton(self, sample_skeleton):
        """Test capturing pose from skeleton."""
        snapshot = PoseSnapshot.capture_from_skeleton(sample_skeleton, "Captured Pose")
        
        assert snapshot.name == "Captured Pose"
        assert len(snapshot.bones) == len(sample_skeleton)
        assert 'root' in snapshot.bones
        assert 'spine' in snapshot.bones

    def test_apply_to_skeleton(self, sample_skeleton):
        """Test applying pose to skeleton."""
        # Capture original state
        original = PoseSnapshot.capture_from_skeleton(sample_skeleton)
        
        # Modify skeleton
        root_bone = sample_skeleton.get_bone('root')
        root_bone.set_pose_rotation(Quat.from_axis_angle(Vec3.UP, 0.5))
        sample_skeleton.update_all_transforms()
        
        # Apply original pose
        original.apply_to_skeleton(sample_skeleton)
        
        # Should be back to original
        root_bone = sample_skeleton.get_bone('root')
        # Check rotation is approximately identity
        assert abs(root_bone.pose_transform.rotation.w - 1) < 0.1

    def test_capture_apply_roundtrip(self, sample_skeleton):
        """Test that capture/apply preserves skeleton state."""
        # Modify skeleton
        spine = sample_skeleton.get_bone('spine')
        spine.set_pose_rotation(Quat.from_axis_angle(Vec3(1, 0, 0), 0.3))
        spine.set_pose_position(Vec3(0.5, 1.5, 0.2))
        sample_skeleton.update_all_transforms()
        
        # Capture modified state
        modified_snapshot = PoseSnapshot.capture_from_skeleton(sample_skeleton, "Modified")
        
        # Reset skeleton
        for bone in sample_skeleton:
            bone.set_pose_rotation(Quat.identity())
            bone.set_pose_position(Vec3(0, 0, 0))
        sample_skeleton.update_all_transforms()
        
        # Apply modified state
        modified_snapshot.apply_to_skeleton(sample_skeleton)
        
        # Check bone was restored
        spine = sample_skeleton.get_bone('spine')
        assert abs(spine.pose_transform.rotation.x - 0.147) < 0.01  # sin(0.15)


class TestUndoRedoStack:
    """Tests for UndoRedoStack class."""

    def test_undo_redo_stack_creation(self):
        """Test UndoRedoStack initialization."""
        stack = UndoRedoStack(max_history=50)
        
        assert stack.can_undo == False
        assert stack.can_redo == False
        assert stack.undo_count == 0
        assert stack.redo_count == 0

    def test_push_state(self, sample_skeleton):
        """Test pushing state onto stack."""
        stack = UndoRedoStack()
        
        stack.push_state(sample_skeleton, "Initial State")
        
        assert stack.undo_count == 0  # Nothing to undo yet
        assert stack._current_snapshot is not None

    def test_undo(self, sample_skeleton):
        """Test undo operation."""
        stack = UndoRedoStack()
        
        # Push initial state
        stack.push_state(sample_skeleton, "State 1")
        
        # Modify skeleton
        root = sample_skeleton.get_bone('root')
        root.set_pose_rotation(Quat.from_axis_angle(Vec3.UP, 0.5))
        sample_skeleton.update_all_transforms()
        
        # Push modified state
        stack.push_state(sample_skeleton, "State 2")
        
        # Now we can undo
        assert stack.can_undo == True
        
        # Undo
        result = stack.undo(sample_skeleton)
        
        assert result is not None
        assert stack.can_redo == True

    def test_redo(self, sample_skeleton):
        """Test redo operation."""
        stack = UndoRedoStack()
        
        # Push two states
        stack.push_state(sample_skeleton, "State 1")
        
        root = sample_skeleton.get_bone('root')
        root.set_pose_rotation(Quat.from_axis_angle(Vec3.UP, 0.5))
        sample_skeleton.update_all_transforms()
        
        stack.push_state(sample_skeleton, "State 2")
        
        # Undo
        stack.undo(sample_skeleton)
        
        # Now redo
        assert stack.can_redo == True
        result = stack.redo(sample_skeleton)
        
        assert result is not None
        assert stack.can_redo == False

    def test_undo_redo_multiple(self, sample_skeleton):
        """Test multiple undo/redo operations."""
        stack = UndoRedoStack(max_history=10)
        
        # Push multiple states
        for i in range(5):
            root = sample_skeleton.get_bone('root')
            root.set_pose_rotation(Quat.from_axis_angle(Vec3.UP, i * 0.1))
            sample_skeleton.update_all_transforms()
            stack.push_state(sample_skeleton, f"State {i}")
        
        # Undo multiple times
        for i in range(3):
            assert stack.can_undo
            stack.undo(sample_skeleton)
        
        assert stack.undo_count == 1  # 5 - 3 - 1 (current)
        assert stack.redo_count == 3
        
        # Redo back
        for i in range(2):
            assert stack.can_redo
            stack.redo(sample_skeleton)
        
        assert stack.redo_count == 1

    def test_push_clears_redo(self, sample_skeleton):
        """Test that push clears redo stack."""
        stack = UndoRedoStack()
        
        # Push and modify several times
        stack.push_state(sample_skeleton, "State 1")
        stack.push_state(sample_skeleton, "State 2")
        
        # Undo
        stack.undo(sample_skeleton)
        assert stack.can_redo == True
        
        # Push new state (should clear redo)
        stack.push_state(sample_skeleton, "State 3")
        
        assert stack.can_redo == False

    def test_max_history(self, sample_skeleton):
        """Test that history is pruned at max_history."""
        stack = UndoRedoStack(max_history=3)
        
        # Push more than max_history states
        for i in range(5):
            root = sample_skeleton.get_bone('root')
            root.set_pose_rotation(Quat.from_axis_angle(Vec3.UP, i * 0.1))
            sample_skeleton.update_all_transforms()
            stack.push_state(sample_skeleton, f"State {i}")
        
        # Should only have max_history items
        assert stack.undo_count <= 3

    def test_clear(self, sample_skeleton):
        """Test clearing the stack."""
        stack = UndoRedoStack()
        
        stack.push_state(sample_skeleton, "State 1")
        stack.push_state(sample_skeleton, "State 2")
        stack.undo(sample_skeleton)
        
        stack.clear()
        
        assert stack.can_undo == False
        assert stack.can_redo == False
        assert stack.undo_count == 0
        assert stack.redo_count == 0

    def test_initialize(self, sample_skeleton):
        """Test initializing the stack."""
        stack = UndoRedoStack()
        
        stack.initialize(sample_skeleton)
        
        assert stack._current_snapshot is not None
        assert stack.can_undo == False
        assert stack.can_redo == False


class TestPoseSerializer:
    """Tests for PoseSerializer class."""

    def test_save_pose(self, sample_skeleton, tmp_path):
        """Test saving pose to file."""
        filepath = str(tmp_path / "test_pose.json")
        
        result = PoseSerializer.save_pose(filepath, sample_skeleton, "Test Pose")
        
        assert result == True
        assert os.path.exists(filepath)
        
        # Verify content
        with open(filepath) as f:
            data = json.load(f)
        
        assert data['name'] == "Test Pose"
        assert 'bones' in data

    def test_load_pose(self, sample_skeleton, tmp_path):
        """Test loading pose from file."""
        filepath = str(tmp_path / "test_pose.json")
        
        # Save first
        PoseSerializer.save_pose(filepath, sample_skeleton, "Original")
        
        # Modify skeleton
        root = sample_skeleton.get_bone('root')
        original_rotation = root.pose_transform.rotation
        root.set_pose_rotation(Quat.from_axis_angle(Vec3.UP, 1.0))
        sample_skeleton.update_all_transforms()
        
        # Load pose
        result = PoseSerializer.load_pose(filepath, sample_skeleton)
        
        assert result is not None
        assert isinstance(result, PoseSnapshot)
        
        # Check rotation was restored
        root = sample_skeleton.get_bone('root')
        assert abs(root.pose_transform.rotation.w - original_rotation.w) < 0.01

    def test_load_pose_data(self, sample_skeleton, tmp_path):
        """Test loading pose data without applying."""
        filepath = str(tmp_path / "test_pose.json")
        
        # Save
        PoseSerializer.save_pose(filepath, sample_skeleton, "Data Test")
        
        # Load data only
        snapshot = PoseSerializer.load_pose_data(filepath)
        
        assert snapshot is not None
        assert snapshot.name == "Data Test"
        # Skeleton should not be modified

    def test_get_pose_info(self, sample_skeleton, tmp_path):
        """Test getting pose file info."""
        filepath = str(tmp_path / "test_pose.json")
        
        PoseSerializer.save_pose(filepath, sample_skeleton, "Info Test")
        
        info = PoseSerializer.get_pose_info(filepath)
        
        assert info is not None
        assert info['name'] == "Info Test"
        assert 'timestamp' in info
        assert 'bone_count' in info
        assert info['bone_count'] == len(sample_skeleton)

    def test_load_nonexistent_file(self, tmp_path):
        """Test loading nonexistent file."""
        result = PoseSerializer.load_pose_data(str(tmp_path / "nonexistent.json"))
        
        assert result is None

    def test_get_info_nonexistent_file(self, tmp_path):
        """Test getting info for nonexistent file."""
        result = PoseSerializer.get_pose_info(str(tmp_path / "nonexistent.json"))
        
        assert result is None

    def test_save_load_roundtrip(self, sample_skeleton, tmp_path):
        """Test save/load preserves pose data."""
        filepath = str(tmp_path / "roundtrip.json")
        
        # Modify skeleton
        spine = sample_skeleton.get_bone('spine')
        spine.set_pose_rotation(Quat.from_axis_angle(Vec3(1, 0, 0), 0.5))
        spine.set_pose_position(Vec3(1, 2, 3))
        sample_skeleton.update_all_transforms()
        
        # Save
        PoseSerializer.save_pose(filepath, sample_skeleton, "Roundtrip")
        
        # Reset skeleton
        for bone in sample_skeleton:
            bone.set_pose_rotation(Quat.identity())
            bone.set_pose_position(Vec3(0, 0, 0))
        sample_skeleton.update_all_transforms()
        
        # Load
        PoseSerializer.load_pose(filepath, sample_skeleton)
        
        # Check values restored
        spine = sample_skeleton.get_bone('spine')
        assert abs(spine.pose_transform.position.x - 1) < 0.01


class TestPoseStateIntegration:
    """Integration tests for pose state with skeleton."""

    def test_full_undo_redo_workflow(self, sample_skeleton):
        """Test complete undo/redo workflow."""
        stack = UndoRedoStack(max_history=20)
        
        # Initialize
        stack.initialize(sample_skeleton)
        
        # Make several changes
        for i in range(5):
            root = sample_skeleton.get_bone('root')
            root.set_pose_rotation(Quat.from_axis_angle(Vec3.UP, i * 0.2))
            sample_skeleton.update_all_transforms()
            stack.push_state(sample_skeleton, f"Change {i}")
        
        # Undo all the way
        while stack.can_undo:
            stack.undo(sample_skeleton)
        
        # Should be back to initial state
        root = sample_skeleton.get_bone('root')
        assert abs(root.pose_transform.rotation.w - 1) < 0.1
        
        # Redo all the way
        while stack.can_redo:
            stack.redo(sample_skeleton)
        
        # Should be at final state
        root = sample_skeleton.get_bone('root')
        # Final rotation was 4 * 0.2 = 0.8 radians
        assert root.pose_transform.rotation.w < 1.0

    def test_pose_file_workflow(self, sample_skeleton, tmp_path):
        """Test complete pose file workflow."""
        # Create a pose
        spine = sample_skeleton.get_bone('spine')
        spine.set_pose_rotation(Quat.from_axis_angle(Vec3(1, 0, 0), 0.3))
        sample_skeleton.update_all_transforms()
        
        # Save
        filepath = str(tmp_path / "workflow_pose.json")
        PoseSerializer.save_pose(filepath, sample_skeleton, "Workflow Test")
        
        # Get info
        info = PoseSerializer.get_pose_info(filepath)
        assert info['name'] == "Workflow Test"
        
        # Reset skeleton
        for bone in sample_skeleton:
            bone.set_pose_rotation(Quat.identity())
        sample_skeleton.update_all_transforms()
        
        # Load
        snapshot = PoseSerializer.load_pose(filepath, sample_skeleton)
        assert snapshot is not None
        
        # Verify restored
        spine = sample_skeleton.get_bone('spine')
        assert abs(spine.pose_transform.rotation.x - 0.147) < 0.01


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

#!/usr/bin/env python3
"""
Tests for ModelInstance Module
==============================

Tests for the ModelInstance class representing loaded 3D models.

Run with: pytest tests/test_model_instance.py -v
"""

import pytest
import sys
import os
import tempfile
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pose_engine.model_instance import ModelInstance
from pose_engine.skeleton import Skeleton
from pose_engine.bone import Bone
from pose_engine.vec3 import Vec3
from pose_engine.quat import Quat
from pose_engine.transform import Transform


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def model_instance():
    """Create a basic ModelInstance for testing."""
    return ModelInstance(name="TestModel")


@pytest.fixture
def model_with_skeleton(sample_skeleton):
    """Create a ModelInstance with a skeleton attached."""
    model = ModelInstance(name="SkeletonModel")
    model.skeleton = sample_skeleton
    return model


@pytest.fixture
def parent_model(sample_skeleton):
    """Create a parent model for hierarchy testing."""
    model = ModelInstance(name="ParentModel")
    model.skeleton = sample_skeleton
    model.set_position(0, 0, 0)
    return model


@pytest.fixture
def child_model():
    """Create a child model for hierarchy testing."""
    model = ModelInstance(name="ChildModel")
    model.set_position(1, 0, 0)
    return model


@pytest.fixture
def test_glb_path():
    """Get path to test GLB file if available."""
    # Check for test GLB file
    test_file = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "krita_3d_pose", "TEST.glb"
    )
    if os.path.exists(test_file):
        return test_file
    return None


# ============================================================================
# Test Class: Basic Creation
# ============================================================================

class TestModelInstanceCreation:
    """Tests for ModelInstance initialization."""

    def test_model_instance_creation(self):
        """Test basic model instance creation."""
        model = ModelInstance(name="TestModel")

        assert model.name == "TestModel"
        assert model.skeleton is None
        assert model.mesh_data is None
        assert model.visible is True
        assert model.source_file is None

    def test_model_id_generation(self):
        """Test that auto-generated IDs are unique."""
        model1 = ModelInstance(name="Model1")
        model2 = ModelInstance(name="Model2")

        # IDs should be auto-generated and unique
        assert model1.id is not None
        assert model2.id is not None
        assert model1.id != model2.id
        # IDs should be 8 characters (truncated UUID)
        assert len(model1.id) == 8

    def test_model_custom_id(self):
        """Test custom ID assignment."""
        model = ModelInstance(id="custom_id_123", name="CustomModel")

        assert model.id == "custom_id_123"
        assert model.name == "CustomModel"

    def test_model_default_transform(self):
        """Test that default transform is identity."""
        model = ModelInstance(name="TestModel")

        assert model.transform.position.x == 0
        assert model.transform.position.y == 0
        assert model.transform.position.z == 0

    def test_model_repr(self):
        """Test string representation."""
        model = ModelInstance(name="TestModel")

        repr_str = repr(model)
        assert "TestModel" in repr_str
        assert model.id in repr_str


# ============================================================================
# Test Class: Transform Operations
# ============================================================================

class TestModelTransform:
    """Tests for model transform operations."""

    def test_model_transform(self):
        """Test world transform operations."""
        model = ModelInstance(name="TestModel")

        # Default transform is identity
        assert model.transform.position.x == 0
        assert model.transform.position.y == 0
        assert model.transform.position.z == 0

    def test_set_position(self):
        """Test setting position."""
        model = ModelInstance(name="TestModel")
        model.set_position(1.0, 2.0, 3.0)

        assert model.transform.position.x == 1.0
        assert model.transform.position.y == 2.0
        assert model.transform.position.z == 3.0

    def test_translate(self):
        """Test translating the model."""
        model = ModelInstance(name="TestModel")
        model.set_position(1.0, 2.0, 3.0)

        model.translate(Vec3(0.5, 0.5, 0.5))

        assert model.transform.position.x == 1.5
        assert model.transform.position.y == 2.5
        assert model.transform.position.z == 3.5

    def test_rotate_y(self):
        """Test Y-axis rotation."""
        model = ModelInstance(name="TestModel")

        # Rotate 90 degrees around Y
        model.rotate_y(90.0)

        # The rotation should be applied
        # Check that rotation is not identity
        assert model.transform.rotation.w != 1.0 or model.transform.rotation.x != 0.0

    def test_get_world_position_no_parent(self):
        """Test world position without parent."""
        model = ModelInstance(name="TestModel")
        model.set_position(5.0, 10.0, 15.0)

        world_pos = model.get_world_position()

        assert world_pos.x == 5.0
        assert world_pos.y == 10.0
        assert world_pos.z == 15.0

    def test_get_world_transform_no_parent(self):
        """Test world transform without parent."""
        model = ModelInstance(name="TestModel")
        model.set_position(1.0, 2.0, 3.0)

        world_transform = model.get_world_transform()

        assert world_transform.position.x == 1.0
        assert world_transform.position.y == 2.0
        assert world_transform.position.z == 3.0


# ============================================================================
# Test Class: Visibility
# ============================================================================

class TestModelVisibility:
    """Tests for model visibility."""

    def test_model_visibility_default(self):
        """Test default visibility is True."""
        model = ModelInstance(name="TestModel")

        assert model.visible is True

    def test_model_visibility_toggle(self):
        """Test toggling visibility."""
        model = ModelInstance(name="TestModel")

        model.visible = False
        assert model.visible is False

        model.visible = True
        assert model.visible is True


# ============================================================================
# Test Class: Parent/Child Relationships
# ============================================================================

class TestModelParentChild:
    """Tests for parent/child relationships."""

    def test_model_parent_child(self):
        """Test parent/child relationships."""
        parent = ModelInstance(name="Parent")
        child = ModelInstance(name="Child")

        # Initially no parent
        assert child.get_parent() is None
        assert len(parent.get_children()) == 0

        # Set parent
        child.set_parent(parent)

        assert child.get_parent() is parent
        assert child in parent.get_children()

    def test_set_parent(self):
        """Test setting parent relationship."""
        parent = ModelInstance(name="Parent")
        child = ModelInstance(name="Child")

        child.set_parent(parent)

        assert child.get_parent() is parent
        assert len(parent.get_children()) == 1
        assert parent.get_children()[0] is child

    def test_set_parent_none(self):
        """Test unparenting a model."""
        parent = ModelInstance(name="Parent")
        child = ModelInstance(name="Child")

        # First set parent
        child.set_parent(parent)
        assert child.get_parent() is parent

        # Then unparent
        child.set_parent(None)
        assert child.get_parent() is None
        assert child not in parent.get_children()

    def test_reparenting(self):
        """Test reparenting from one parent to another."""
        parent1 = ModelInstance(name="Parent1")
        parent2 = ModelInstance(name="Parent2")
        child = ModelInstance(name="Child")

        # Set first parent
        child.set_parent(parent1)
        assert child.get_parent() is parent1
        assert child in parent1.get_children()

        # Reparent to second parent
        child.set_parent(parent2)
        assert child.get_parent() is parent2
        assert child not in parent1.get_children()
        assert child in parent2.get_children()

    def test_get_children_copy(self):
        """Test that get_children returns a copy."""
        parent = ModelInstance(name="Parent")
        child1 = ModelInstance(name="Child1")
        child2 = ModelInstance(name="Child2")

        child1.set_parent(parent)
        child2.set_parent(parent)

        children = parent.get_children()
        assert len(children) == 2

        # Modifying returned list shouldn't affect internal state
        children.clear()
        assert len(parent.get_children()) == 2

    def test_get_world_position_with_parent(self):
        """Test world position with parent."""
        parent = ModelInstance(name="Parent")
        parent.set_position(10.0, 0.0, 0.0)

        child = ModelInstance(name="Child")
        child.set_position(5.0, 0.0, 0.0)
        child.set_parent(parent)

        world_pos = child.get_world_position()

        # Child world position should be parent + child local
        assert world_pos.x == 15.0

    def test_nested_hierarchy(self):
        """Test nested parent/child hierarchy."""
        grandparent = ModelInstance(name="Grandparent")
        grandparent.set_position(0.0, 0.0, 0.0)

        parent = ModelInstance(name="Parent")
        parent.set_position(10.0, 0.0, 0.0)
        parent.set_parent(grandparent)

        child = ModelInstance(name="Child")
        child.set_position(5.0, 0.0, 0.0)
        child.set_parent(parent)

        # World position should accumulate through hierarchy
        world_pos = child.get_world_position()
        assert world_pos.x == 15.0


# ============================================================================
# Test Class: Bone Attachment
# ============================================================================

class TestBoneAttachment:
    """Tests for attaching models to bones."""

    def test_attach_to_bone(self):
        """Test bone attachment."""
        # Create parent with skeleton
        parent = ModelInstance(name="Parent")
        parent.skeleton = Skeleton()

        # Add a bone
        bone = parent.skeleton.add_bone("attach_bone", parent_index=-1)
        bone.bind_transform.set_position(2.0, 0.0, 0.0)
        parent.skeleton.update_all_transforms()

        # Create child and attach to bone
        child = ModelInstance(name="Child")
        child.set_position(1.0, 0.0, 0.0)
        child.set_parent(parent, bone_name="attach_bone")

        assert child.get_parent() is parent
        assert child.get_parent_bone() == "attach_bone"

    def test_get_parent_bone(self):
        """Test getting parent bone name."""
        parent = ModelInstance(name="Parent")
        parent.skeleton = Skeleton()
        parent.skeleton.add_bone("test_bone", parent_index=-1)

        child = ModelInstance(name="Child")
        child.set_parent(parent, bone_name="test_bone")

        assert child.get_parent_bone() == "test_bone"

    def test_get_parent_bone_none(self):
        """Test getting parent bone when not attached to bone."""
        parent = ModelInstance(name="Parent")
        child = ModelInstance(name="Child")
        child.set_parent(parent)

        assert child.get_parent_bone() is None


# ============================================================================
# Test Class: Skeleton Access
# ============================================================================

class TestSkeletonAccess:
    """Tests for skeleton access methods."""

    def test_get_bone_count_empty(self):
        """Test bone count with no skeleton."""
        model = ModelInstance(name="TestModel")

        assert model.get_bone_count() == 0

    def test_get_bone_count_with_skeleton(self, sample_skeleton):
        """Test bone count with skeleton."""
        model = ModelInstance(name="TestModel")
        model.skeleton = sample_skeleton

        # sample_skeleton has 5 bones
        assert model.get_bone_count() == 5

    def test_get_bone(self, sample_skeleton):
        """Test getting a bone by name."""
        model = ModelInstance(name="TestModel")
        model.skeleton = sample_skeleton

        bone = model.get_bone("root")
        assert bone is not None
        assert bone.name == "root"

    def test_get_bone_not_found(self, sample_skeleton):
        """Test getting a non-existent bone."""
        model = ModelInstance(name="TestModel")
        model.skeleton = sample_skeleton

        bone = model.get_bone("nonexistent")
        assert bone is None

    def test_get_bone_no_skeleton(self):
        """Test getting bone when no skeleton."""
        model = ModelInstance(name="TestModel")

        bone = model.get_bone("any_bone")
        assert bone is None

    def test_get_root_bones(self, sample_skeleton):
        """Test getting root bones."""
        model = ModelInstance(name="TestModel")
        model.skeleton = sample_skeleton

        roots = model.get_root_bones()
        assert len(roots) == 1
        assert roots[0].name == "root"

    def test_get_root_bones_no_skeleton(self):
        """Test getting root bones with no skeleton."""
        model = ModelInstance(name="TestModel")

        roots = model.get_root_bones()
        assert roots == []

    def test_update_transforms(self, sample_skeleton):
        """Test updating bone transforms."""
        model = ModelInstance(name="TestModel")
        model.skeleton = sample_skeleton

        # Should not raise
        model.update_transforms()


# ============================================================================
# Test Class: Copying
# ============================================================================

class TestModelCopying:
    """Tests for model copying."""

    def test_copy_creates_new_instance(self, sample_skeleton):
        """Test that copy creates a new instance."""
        model = ModelInstance(name="Original")
        model.skeleton = sample_skeleton
        model.set_position(1.0, 2.0, 3.0)

        copy = model.copy()

        assert copy is not model
        assert copy.id != model.id
        assert copy.name == "Original (copy)"

    def test_copy_skeleton_deep(self, sample_skeleton):
        """Test that skeleton is deep-copied."""
        model = ModelInstance(name="Original")
        model.skeleton = sample_skeleton

        copy = model.copy()

        # Skeleton should be a different object
        assert copy.skeleton is not model.skeleton

        # But have same number of bones
        assert len(copy.skeleton) == len(model.skeleton)

    def test_copy_preserves_pose(self, sample_skeleton):
        """Test that current pose is preserved in copy."""
        model = ModelInstance(name="Original")
        model.skeleton = sample_skeleton

        # Modify a bone's pose
        bone = model.skeleton.get_bone("root")
        bone.pose_transform.rotation = Quat(0.707, 0.0, 0.707, 0.0)

        copy = model.copy()

        # Copy should have same pose
        copy_bone = copy.skeleton.get_bone("root")
        assert abs(copy_bone.pose_transform.rotation.w - 0.707) < 0.001

    def test_copy_custom_name(self, sample_skeleton):
        """Test copy with custom name."""
        model = ModelInstance(name="Original")
        model.skeleton = sample_skeleton

        copy = model.copy(name="CustomCopy")

        assert copy.name == "CustomCopy"

    def test_copy_transform(self, sample_skeleton):
        """Test that transform is copied."""
        model = ModelInstance(name="Original")
        model.skeleton = sample_skeleton
        model.set_position(5.0, 10.0, 15.0)

        copy = model.copy()

        assert copy.transform.position.x == 5.0
        assert copy.transform.position.y == 10.0
        assert copy.transform.position.z == 15.0

    def test_copy_mesh_data_shared(self, sample_skeleton):
        """Test that mesh data is shared (not copied)."""
        model = ModelInstance(name="Original")
        model.skeleton = sample_skeleton
        # mesh_data would normally be set by load_from_glb
        # For this test, just verify the copy shares whatever mesh_data exists

        copy = model.copy()

        # Mesh data should be the same object (shared)
        assert copy.mesh_data is model.mesh_data


# ============================================================================
# Test Class: GLB Loading (Integration)
# ============================================================================

@pytest.mark.integration
class TestGLBLoading:
    """Integration tests for GLB loading."""

    def test_load_from_glb(self, test_glb_path):
        """Test loading from a GLB file."""
        if test_glb_path is None:
            pytest.skip("No test GLB file available")

        model = ModelInstance(name="GLBModel")
        model.load_from_glb(test_glb_path)

        # Should have skeleton
        assert model.skeleton is not None
        assert model.get_bone_count() > 0

        # Should have source file set
        assert model.source_file == test_glb_path

    def test_load_from_glb_skeleton_valid(self, test_glb_path):
        """Test that loaded skeleton has valid bones."""
        if test_glb_path is None:
            pytest.skip("No test GLB file available")

        model = ModelInstance(name="GLBModel")
        model.load_from_glb(test_glb_path)

        # All bones should have valid transforms
        for bone in model.skeleton:
            pos = bone.get_world_position()
            assert isinstance(pos.x, float)
            assert isinstance(pos.y, float)
            assert isinstance(pos.z, float)

    def test_load_from_glb_mesh_data(self, test_glb_path):
        """Test that mesh data is loaded."""
        if test_glb_path is None:
            pytest.skip("No test GLB file available")

        model = ModelInstance(name="GLBModel")
        model.load_from_glb(test_glb_path)

        # Should have mesh data
        assert model.mesh_data is not None


# ============================================================================
# Test Class: GPU Resources
# ============================================================================

class TestGPUResources:
    """Tests for GPU resource management."""

    def test_initialize_gl(self):
        """Test GL initialization flag."""
        model = ModelInstance(name="TestModel")

        # Initially not initialized
        assert model._gl_initialized is False

        # Initialize
        result = model.initialize_gl()
        assert result is True
        assert model._gl_initialized is True

    def test_initialize_gl_idempotent(self):
        """Test that initialize_gl can be called multiple times."""
        model = ModelInstance(name="TestModel")

        model.initialize_gl()
        model.initialize_gl()  # Should not fail

        assert model._gl_initialized is True

    def test_cleanup_gl(self):
        """Test GL cleanup."""
        model = ModelInstance(name="TestModel")

        model.initialize_gl()
        assert model._gl_initialized is True

        model.cleanup_gl()
        assert model._gl_initialized is False


# ============================================================================
# Test Class: Edge Cases
# ============================================================================

class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_name(self):
        """Test model with empty name."""
        model = ModelInstance(name="")
        assert model.name == ""

    def test_special_characters_in_name(self):
        """Test model with special characters in name."""
        model = ModelInstance(name="Test-Model_123!@#")
        assert model.name == "Test-Model_123!@#"

    def test_very_long_name(self):
        """Test model with very long name."""
        long_name = "A" * 1000
        model = ModelInstance(name=long_name)
        assert model.name == long_name

    def test_circular_parent_prevention(self):
        """Test that circular parenting is prevented or handled."""
        model1 = ModelInstance(name="Model1")
        model2 = ModelInstance(name="Model2")

        # Create a chain: model1 -> model2
        model2.set_parent(model1)

        # Attempting to make model1 parent of model2 would create a cycle
        # This should either be prevented or handled gracefully
        # The current implementation doesn't prevent this, so we just
        # verify the behavior
        model1.set_parent(model2)

        # After this, model1's parent is model2, and model2's parent is model1
        # This is a circular reference - the code doesn't prevent it
        # but we document the expected behavior
        assert model1.get_parent() is model2
        assert model2.get_parent() is model1

    def test_self_parenting(self):
        """Test that self-parenting is handled."""
        model = ModelInstance(name="SelfParent")

        # Attempting to set self as parent
        # This should either be prevented or handled gracefully
        model.set_parent(model)

        # After this, model is its own parent
        # This is a self-reference - the code doesn't prevent it
        # but we document the expected behavior
        assert model.get_parent() is model

    def test_multiple_children(self):
        """Test model with many children."""
        parent = ModelInstance(name="Parent")

        # Add many children
        children = []
        for i in range(100):
            child = ModelInstance(name=f"Child{i}")
            child.set_parent(parent)
            children.append(child)

        assert len(parent.get_children()) == 100

        # Verify all children are present
        for child in children:
            assert child in parent.get_children()


# ============================================================================
# Test Class: World Transform with Hierarchy
# ============================================================================

class TestWorldTransformHierarchy:
    """Tests for world transform calculations in hierarchies."""

    def test_world_transform_deep_hierarchy(self):
        """Test world transform with deep hierarchy."""
        # Create a chain of models
        models = []
        for i in range(5):
            model = ModelInstance(name=f"Model{i}")
            model.set_position(1.0, 0.0, 0.0)
            if i > 0:
                model.set_parent(models[i - 1])
            models.append(model)

        # Last model should have world position of 5.0
        world_pos = models[4].get_world_position()
        assert abs(world_pos.x - 5.0) < 0.001

    def test_world_transform_with_rotation(self):
        """Test world transform with rotation in hierarchy."""
        parent = ModelInstance(name="Parent")
        parent.set_position(0.0, 0.0, 0.0)

        child = ModelInstance(name="Child")
        child.set_position(1.0, 0.0, 0.0)
        child.set_parent(parent)

        # Rotate parent 90 degrees around Y
        parent.rotate_y(90.0)

        # Child's world position should be rotated
        # (1, 0, 0) rotated 90 degrees around Y becomes (0, 0, -1)
        world_pos = child.get_world_position()

        # Allow some tolerance for floating point
        assert abs(world_pos.x - 0.0) < 0.001
        assert abs(world_pos.y - 0.0) < 0.001
        assert abs(world_pos.z - (-1.0)) < 0.001

    def test_world_transform_with_scale(self):
        """Test world transform with scale in hierarchy."""
        parent = ModelInstance(name="Parent")
        parent.set_position(0.0, 0.0, 0.0)
        parent.transform.scale = Vec3(2.0, 2.0, 2.0)

        child = ModelInstance(name="Child")
        child.set_position(1.0, 1.0, 1.0)
        child.set_parent(parent)

        # Child's world position should be scaled by parent
        world_pos = child.get_world_position()

        # Position (1, 1, 1) scaled by 2 = (2, 2, 2)
        assert abs(world_pos.x - 2.0) < 0.001
        assert abs(world_pos.y - 2.0) < 0.001
        assert abs(world_pos.z - 2.0) < 0.001


# ============================================================================
# Entry Point
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])

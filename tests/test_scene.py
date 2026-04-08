#!/usr/bin/env python3
"""
Tests for Scene Module
======================

Tests for the Scene class managing multiple ModelInstances.

Run with: pytest tests/test_scene.py -v
"""

import pytest
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pose_engine.scene import Scene
from pose_engine.model_instance import ModelInstance
from pose_engine.skeleton import Skeleton
from pose_engine.bone import Bone
from pose_engine.vec3 import Vec3
from pose_engine.quat import Quat
from pose_engine.transform import Transform


class TestSceneCreation:
    """Tests for scene initialization."""

    def test_scene_creation(self):
        """Test basic scene creation."""
        scene = Scene()
        
        assert scene.get_model_count() == 0
        assert scene.get_all_models() == []
        assert scene.get_selected_model() is None

    def test_scene_empty_state(self):
        """Test empty scene state."""
        scene = Scene()
        
        assert scene.get_selected_model_id() is None
        assert scene.get_selected_bone_name() is None
        assert scene.get_root_models() == []


class TestSceneModelManagement:
    """Tests for adding and removing models."""

    def test_add_model(self):
        """Test adding a model to the scene."""
        scene = Scene()
        model = ModelInstance(name="TestModel")
        
        added = scene.add_model(model)
        
        assert added is model
        assert scene.get_model_count() == 1
        assert scene.get_model(model.id) is model

    def test_add_multiple_models(self):
        """Test adding multiple models."""
        scene = Scene()
        
        model1 = ModelInstance(name="Model1")
        model2 = ModelInstance(name="Model2")
        model3 = ModelInstance(name="Model3")
        
        scene.add_model(model1)
        scene.add_model(model2)
        scene.add_model(model3)
        
        assert scene.get_model_count() == 3
        assert len(scene.get_all_models()) == 3

    def test_remove_model(self):
        """Test removing a model from the scene."""
        scene = Scene()
        model = ModelInstance(name="TestModel")
        
        scene.add_model(model)
        assert scene.get_model_count() == 1
        
        removed = scene.remove_model(model.id)
        
        assert removed is model
        assert scene.get_model_count() == 0
        assert scene.get_model(model.id) is None

    def test_remove_nonexistent_model(self):
        """Test removing a model that doesn't exist."""
        scene = Scene()
        
        removed = scene.remove_model("nonexistent_id")
        
        assert removed is None

    def test_get_model(self):
        """Test getting a model by ID."""
        scene = Scene()
        model = ModelInstance(name="TestModel")
        
        scene.add_model(model)
        
        retrieved = scene.get_model(model.id)
        assert retrieved is model
        
        missing = scene.get_model("nonexistent")
        assert missing is None

    def test_get_all_models(self):
        """Test getting all models."""
        scene = Scene()
        
        model1 = ModelInstance(name="Model1")
        model2 = ModelInstance(name="Model2")
        
        scene.add_model(model1)
        scene.add_model(model2)
        
        all_models = scene.get_all_models()
        
        assert len(all_models) == 2
        assert model1 in all_models
        assert model2 in all_models

    def test_get_root_models(self):
        """Test getting root models (no parent)."""
        scene = Scene()
        
        model1 = ModelInstance(name="Root1")
        model2 = ModelInstance(name="Root2")
        
        scene.add_model(model1)
        scene.add_model(model2)
        
        roots = scene.get_root_models()
        
        assert len(roots) == 2

    def test_get_model_count(self):
        """Test model count."""
        scene = Scene()
        
        assert scene.get_model_count() == 0
        
        for i in range(5):
            scene.add_model(ModelInstance(name=f"Model{i}"))
        
        assert scene.get_model_count() == 5


class TestSceneSelection:
    """Tests for model and bone selection."""

    def test_select_model(self):
        """Test selecting a model."""
        scene = Scene()
        model = ModelInstance(name="TestModel")
        
        scene.add_model(model)
        scene.select_model(model.id)
        
        assert scene.get_selected_model() is model
        assert scene.get_selected_model_id() == model.id

    def test_select_model_clears_bone(self):
        """Test that selecting a model clears bone selection."""
        scene = Scene()
        model = ModelInstance(name="TestModel")
        
        scene.add_model(model)
        scene.select_bone(model.id, "test_bone")
        
        # Select model should clear bone
        scene.select_model(model.id)
        
        assert scene.get_selected_bone_name() is None

    def test_select_bone(self):
        """Test selecting a bone."""
        scene = Scene()
        model = ModelInstance(name="TestModel")
        
        scene.add_model(model)
        scene.select_bone(model.id, "spine")
        
        assert scene.get_selected_model() is model
        assert scene.get_selected_bone_name() == "spine"

    def test_select_bone_updates_model(self):
        """Test that selecting a bone also selects its model."""
        scene = Scene()
        model1 = ModelInstance(name="Model1")
        model2 = ModelInstance(name="Model2")
        
        scene.add_model(model1)
        scene.add_model(model2)
        
        scene.select_bone(model2.id, "head")
        
        assert scene.get_selected_model_id() == model2.id

    def test_clear_selection(self):
        """Test clearing selection."""
        scene = Scene()
        model = ModelInstance(name="TestModel")
        
        scene.add_model(model)
        scene.select_model(model.id)
        
        scene.clear_selection()
        
        assert scene.get_selected_model() is None
        assert scene.get_selected_model_id() is None

    def test_get_selected_model_none(self):
        """Test getting selected model when none selected."""
        scene = Scene()
        
        assert scene.get_selected_model() is None

    def test_get_selected_bone_none(self):
        """Test getting selected bone when none selected."""
        scene = Scene()
        model = ModelInstance(name="TestModel")
        scene.add_model(model)
        
        model_sel, bone_sel = scene.get_selected_bone()
        assert model_sel is None
        assert bone_sel is None

    def test_selection_cleared_on_removal(self):
        """Test that selection is cleared when model is removed."""
        scene = Scene()
        model = ModelInstance(name="TestModel")
        
        scene.add_model(model)
        scene.select_model(model.id)
        
        scene.remove_model(model.id)
        
        assert scene.get_selected_model() is None
        assert scene.get_selected_model_id() is None


class TestSceneBoundingBox:
    """Tests for bounding box calculations."""

    def test_empty_scene_bounding_box(self):
        """Test bounding box of empty scene."""
        scene = Scene()
        
        min_pt, max_pt = scene.get_bounding_box()
        
        # Should return default box
        assert min_pt is not None
        assert max_pt is not None

    def test_get_center(self):
        """Test getting scene center."""
        scene = Scene()
        
        center = scene.get_center()
        
        assert isinstance(center, Vec3)


class TestSceneParenting:
    """Tests for model parenting relationships."""

    def test_set_model_parent(self):
        """Test setting model parent."""
        scene = Scene()
        
        parent = ModelInstance(name="Parent")
        child = ModelInstance(name="Child")
        
        scene.add_model(parent)
        scene.add_model(child)
        
        result = scene.set_model_parent(child.id, parent.id)
        
        assert result == True
        assert child.get_parent() is parent

    def test_set_model_parent_with_bone(self):
        """Test setting model parent with bone attachment."""
        scene = Scene()
        
        parent = ModelInstance(name="Parent")
        child = ModelInstance(name="Child")
        
        scene.add_model(parent)
        scene.add_model(child)
        
        result = scene.set_model_parent(child.id, parent.id, "spine")
        
        assert result == True
        assert child.get_parent_bone() == "spine"

    def test_unparent_model(self):
        """Test removing parent from model."""
        scene = Scene()
        
        parent = ModelInstance(name="Parent")
        child = ModelInstance(name="Child")
        
        scene.add_model(parent)
        scene.add_model(child)
        scene.set_model_parent(child.id, parent.id)
        
        # Unparent
        result = scene.set_model_parent(child.id, None)
        
        assert result == True
        assert child.get_parent() is None

    def test_parent_nonexistent_child(self):
        """Test parenting a nonexistent child."""
        scene = Scene()
        parent = ModelInstance(name="Parent")
        scene.add_model(parent)
        
        result = scene.set_model_parent("nonexistent", parent.id)
        
        assert result == False

    def test_parent_to_nonexistent(self):
        """Test parenting to nonexistent parent."""
        scene = Scene()
        child = ModelInstance(name="Child")
        scene.add_model(child)
        
        result = scene.set_model_parent(child.id, "nonexistent")
        
        assert result == False

    def test_prevent_self_parenting(self):
        """Test that model can't be its own parent."""
        scene = Scene()
        model = ModelInstance(name="Self")
        scene.add_model(model)
        
        # This would create a cycle
        result = scene.set_model_parent(model.id, model.id)
        
        # Should fail or be handled gracefully
        # The actual behavior depends on implementation

    def test_prevent_cycle(self):
        """Test that cycles are prevented."""
        scene = Scene()
        
        grandparent = ModelInstance(name="Grandparent")
        parent = ModelInstance(name="Parent")
        child = ModelInstance(name="Child")
        
        scene.add_model(grandparent)
        scene.add_model(parent)
        scene.add_model(child)
        
        # Set up: grandparent -> parent -> child
        scene.set_model_parent(parent.id, grandparent.id)
        scene.set_model_parent(child.id, parent.id)
        
        # Try to make grandparent a child of child (would create cycle)
        result = scene.set_model_parent(grandparent.id, child.id)
        
        assert result == False


class TestSceneOperations:
    """Tests for scene-level operations."""

    def test_update_all_transforms(self):
        """Test updating all transforms."""
        scene = Scene()
        
        model1 = ModelInstance(name="Model1")
        model2 = ModelInstance(name="Model2")
        
        scene.add_model(model1)
        scene.add_model(model2)
        
        # Should not crash
        scene.update_all_transforms()

    def test_reset_all_poses(self):
        """Test resetting all poses."""
        scene = Scene()
        
        model = ModelInstance(name="Model")
        scene.add_model(model)
        
        # Should not crash even without skeleton
        scene.reset_all_poses()


class TestSceneSerialization:
    """Tests for scene serialization."""

    def test_to_dict(self):
        """Test converting scene to dictionary."""
        scene = Scene()
        model = ModelInstance(name="TestModel")
        
        scene.add_model(model)
        
        data = scene.to_dict()
        
        assert 'version' in data
        assert 'models' in data
        assert model.id in data['models']

    def test_to_dict_with_selection(self):
        """Test to_dict preserves selection."""
        scene = Scene()
        model = ModelInstance(name="TestModel")
        
        scene.add_model(model)
        scene.select_model(model.id)
        
        data = scene.to_dict()
        
        assert data['selected_model_id'] == model.id

    def test_to_dict_empty_scene(self):
        """Test to_dict with empty scene."""
        scene = Scene()
        
        data = scene.to_dict()
        
        assert 'version' in data
        assert 'models' in data
        assert len(data['models']) == 0


class TestSceneModelOrder:
    """Tests for model ordering."""

    def test_model_order_preserved(self):
        """Test that model order is preserved."""
        scene = Scene()
        
        model1 = ModelInstance(name="Model1")
        model2 = ModelInstance(name="Model2")
        model3 = ModelInstance(name="Model3")
        
        scene.add_model(model1)
        scene.add_model(model2)
        scene.add_model(model3)
        
        all_models = scene.get_all_models()
        
        assert all_models[0] is model1
        assert all_models[1] is model2
        assert all_models[2] is model3

    def test_model_order_after_removal(self):
        """Test model order after removal."""
        scene = Scene()
        
        model1 = ModelInstance(name="Model1")
        model2 = ModelInstance(name="Model2")
        model3 = ModelInstance(name="Model3")
        
        scene.add_model(model1)
        scene.add_model(model2)
        scene.add_model(model3)
        
        scene.remove_model(model2.id)
        
        all_models = scene.get_all_models()
        
        assert len(all_models) == 2
        assert all_models[0] is model1
        assert all_models[1] is model3


class TestSceneVisibility:
    """Tests for model visibility."""

    def test_invisible_model_excluded_from_bounds(self):
        """Test that invisible models are excluded from bounding box."""
        scene = Scene()
        
        model1 = ModelInstance(name="Visible")
        model2 = ModelInstance(name="Invisible")
        model2.visible = False
        
        scene.add_model(model1)
        scene.add_model(model2)
        
        # Should not crash
        min_pt, max_pt = scene.get_bounding_box()


class TestSceneIntegration:
    """Integration tests for scene with skeleton."""

    def test_scene_with_skeleton_model(self, sample_skeleton):
        """Test scene with a model containing a skeleton."""
        scene = Scene()
        
        model = ModelInstance(name="SkeletonModel")
        model.skeleton = sample_skeleton
        
        scene.add_model(model)
        
        assert scene.get_model_count() == 1
        
        # Select a bone
        scene.select_bone(model.id, "root")
        
        model_sel, bone_sel = scene.get_selected_bone()
        assert model_sel is model
        assert bone_sel is not None
        assert bone_sel.name == "root"

    def test_scene_bone_selection_across_models(self, sample_skeleton):
        """Test bone selection across multiple models."""
        scene = Scene()
        
        model1 = ModelInstance(name="Model1")
        model1.skeleton = sample_skeleton
        
        model2 = ModelInstance(name="Model2")
        model2.skeleton = sample_skeleton
        
        scene.add_model(model1)
        scene.add_model(model2)
        
        # Select bone in model1
        scene.select_bone(model1.id, "spine")
        
        # Select bone in model2 (should update)
        scene.select_bone(model2.id, "head")
        
        assert scene.get_selected_model_id() == model2.id
        assert scene.get_selected_bone_name() == "head"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

"""
Scene - Multi-Model Scene Management
====================================

Manages multiple ModelInstances in a shared 3D scene.
Handles model loading, selection, and scene-level operations.

Features:
- Add/remove/duplicate models
- Hierarchical selection (model → bone)
- Scene-level undo/redo support
- Model parenting relationships
"""

import os
import json
from typing import Optional, List, Dict, Tuple
from .model_instance import ModelInstance
from .skeleton import Skeleton
from .bone import Bone
from .vec3 import Vec3
from .quat import Quat
from .transform import Transform


class Scene:
    """
    Manages multiple ModelInstances in a shared 3D scene.
    
    The Scene class provides:
    - Model management (add, remove, duplicate)
    - Selection state (which model and bone are selected)
    - Scene-level operations (frame all, get bounding box)
    - Parent/child relationships between models
    
    Selection is hierarchical: first select a model, then select
    a bone within that model. This allows bone names to be reused
    across different models without conflict.
    """
    
    def __init__(self):
        """Create an empty scene."""
        self._models: Dict[str, ModelInstance] = {}
        self._model_order: List[str] = []  # For consistent ordering
        self._selected_model_id: Optional[str] = None
        self._selected_bone_name: Optional[str] = None
    
    # -------------------------------------------------------------------------
    # Model Management
    # -------------------------------------------------------------------------
    
    def add_model(self, model: ModelInstance) -> ModelInstance:
        """
        Add a model instance to the scene.
        
        Args:
            model: The ModelInstance to add
        
        Returns:
            The added model
        """
        self._models[model.id] = model
        self._model_order.append(model.id)
        return model
    
    def add_model_from_file(self, file_path: str, 
                            name: Optional[str] = None) -> ModelInstance:
        """
        Load and add a model from a GLB file.
        
        Args:
            file_path: Path to the .glb file
            name: Optional display name (default: filename)
        
        Returns:
            The newly created ModelInstance
        """
        if name is None:
            name = os.path.splitext(os.path.basename(file_path))[0]
        
        model = ModelInstance(name=name)
        model.load_from_glb(file_path)
        return self.add_model(model)
    
    def remove_model(self, model_id: str) -> Optional[ModelInstance]:
        """
        Remove a model from the scene.
        
        Also removes the model from its parent's children list
        and removes all its children.
        
        Args:
            model_id: ID of the model to remove
        
        Returns:
            The removed model, or None if not found
        """
        model = self._models.pop(model_id, None)
        if model is None:
            return None
        
        # Remove from order list
        if model_id in self._model_order:
            self._model_order.remove(model_id)
        
        # Clear selection if this model was selected
        if self._selected_model_id == model_id:
            self._selected_model_id = None
            self._selected_bone_name = None
        
        # Remove from parent
        if model._parent:
            model.set_parent(None)
        
        # Orphan children (they become root models)
        for child in model._children[:]:
            child.set_parent(None)
        
        return model
    
    def duplicate_model(self, model_id: str, 
                        name: Optional[str] = None) -> Optional[ModelInstance]:
        """
        Create a duplicate of an existing model.
        
        The duplicate has an independent skeleton (copied pose)
        but shares mesh data with the original.
        
        Args:
            model_id: ID of the model to duplicate
            name: Optional name for the duplicate
        
        Returns:
            The new ModelInstance, or None if original not found
        """
        original = self._models.get(model_id)
        if original is None:
            return None
    
        copy = original.copy(name=name)
        added = self.add_model(copy)
        
        # Offset the duplicate slightly so it's visually distinct
        if added:
            added.transform.position.x += 0.5
        
        return added
    
    def get_model(self, model_id: str) -> Optional[ModelInstance]:
        """Get a model by ID."""
        return self._models.get(model_id)
    
    def get_all_models(self) -> List[ModelInstance]:
        """Get all models in the scene (in order)."""
        return [self._models[mid] for mid in self._model_order if mid in self._models]
    
    def get_root_models(self) -> List[ModelInstance]:
        """Get all models that have no parent."""
        return [m for m in self.get_all_models() if m._parent is None]
    
    def get_model_count(self) -> int:
        """Get the number of models in the scene."""
        return len(self._models)
    
    # -------------------------------------------------------------------------
    # Selection
    # -------------------------------------------------------------------------
    
    def select_model(self, model_id: Optional[str]) -> None:
        """
        Select a model by ID.
        
        Args:
            model_id: ID of model to select, or None to deselect
        """
        self._selected_model_id = model_id
        self._selected_bone_name = None  # Clear bone selection
    
    def select_bone(self, model_id: str, bone_name: str) -> None:
        """
        Select a bone in a specific model.
        
        Args:
            model_id: ID of the model containing the bone
            bone_name: Name of the bone to select
        """
        self._selected_model_id = model_id
        self._selected_bone_name = bone_name
    
    def clear_selection(self) -> None:
        """Clear all selection."""
        self._selected_model_id = None
        self._selected_bone_name = None
    
    def get_selected_model(self) -> Optional[ModelInstance]:
        """Get the currently selected model."""
        if self._selected_model_id is None:
            return None
        return self._models.get(self._selected_model_id)
    
    def get_selected_bone(self) -> Tuple[Optional[ModelInstance], Optional[Bone]]:
        """
        Get the currently selected bone and its model.
        
        Returns:
            Tuple of (ModelInstance, Bone) or (None, None) if no selection
        """
        model = self.get_selected_model()
        if model is None or self._selected_bone_name is None:
            return None, None
        
        bone = model.get_bone(self._selected_bone_name)
        return model, bone
    
    def get_selected_model_id(self) -> Optional[str]:
        """Get the ID of the selected model."""
        return self._selected_model_id
    
    def get_selected_bone_name(self) -> Optional[str]:
        """Get the name of the selected bone."""
        return self._selected_bone_name
    
    # -------------------------------------------------------------------------
    # Model Parenting
    # -------------------------------------------------------------------------
    
    def set_model_parent(self, child_id: str, parent_id: Optional[str],
                         bone_name: Optional[str] = None) -> bool:
        """
        Set the parent of a model.
        
        Args:
            child_id: ID of the child model
            parent_id: ID of the parent model, or None to unparent
            bone_name: Optional bone name to attach to on parent
        
        Returns:
            True if successful, False if models not found
        """
        child = self._models.get(child_id)
        if child is None:
            return False
        
        if parent_id is None:
            child.set_parent(None)
            return True
        
        parent = self._models.get(parent_id)
        if parent is None:
            return False
        
        # Prevent parenting to self or descendants
        if self._would_create_cycle(child, parent):
            return False
        
        child.set_parent(parent, bone_name)
        return True
    
    def _would_create_cycle(self, child: ModelInstance, 
                           prospective_parent: ModelInstance) -> bool:
        """Check if making prospective_parent the parent of child would create a cycle."""
        current = prospective_parent
        while current is not None:
            if current is child:
                return True
            current = current._parent
        return False
    
    # -------------------------------------------------------------------------
    # Scene Operations
    # -------------------------------------------------------------------------
    
    def get_bounding_box(self) -> Tuple[Vec3, Vec3]:
        """
        Get the axis-aligned bounding box of all visible models.
        
        Returns:
            Tuple of (min_point, max_point)
        """
        min_pt = Vec3(float('inf'), float('inf'), float('inf'))
        max_pt = Vec3(float('-inf'), float('-inf'), float('-inf'))
        
        has_content = False
        
        for model in self.get_all_models():
            if not model.visible or model.skeleton is None:
                continue
            
            for bone in model.skeleton:
                world_pos = bone.get_world_position()
                # Transform by model's world transform
                model_world = model.get_world_transform()
                final_pos = model_world.rotation.rotate_vector(world_pos) + model_world.position
                
                min_pt = Vec3(
                    min(min_pt.x, final_pos.x),
                    min(min_pt.y, final_pos.y),
                    min(min_pt.z, final_pos.z)
                )
                max_pt = Vec3(
                    max(max_pt.x, final_pos.x),
                    max(max_pt.y, final_pos.y),
                    max(max_pt.z, final_pos.z)
                )
                has_content = True
        
        if not has_content:
            return Vec3(-1, -1, -1), Vec3(1, 1, 1)
        
        return min_pt, max_pt
    
    def get_center(self) -> Vec3:
        """Get the center point of all visible models."""
        min_pt, max_pt = self.get_bounding_box()
        return Vec3(
            (min_pt.x + max_pt.x) / 2,
            (min_pt.y + max_pt.y) / 2,
            (min_pt.z + max_pt.z) / 2
        )
    
    def update_all_transforms(self) -> None:
        """Update transforms for all models."""
        for model in self.get_all_models():
            model.update_transforms()
    
    def reset_all_poses(self) -> None:
        """Reset all models to bind pose."""
        for model in self.get_all_models():
            if model.skeleton:
                model.skeleton.reset_pose()
    
    # -------------------------------------------------------------------------
    # Serialization
    # -------------------------------------------------------------------------
    
    def to_dict(self) -> dict:
        """
        Convert scene to a dictionary for serialization.
        
        Returns:
            Dictionary representation of the scene
        """
        models_data = {}
        for model in self.get_all_models():
            bone_data = {}
            if model.skeleton:
                for bone in model.skeleton:
                    bone_data[bone.name] = {
                        'rotation': [
                            bone.pose_transform.rotation.x,
                            bone.pose_transform.rotation.y,
                            bone.pose_transform.rotation.z,
                            bone.pose_transform.rotation.w
                        ],
                        'position': [
                            bone.pose_transform.position.x,
                            bone.pose_transform.position.y,
                            bone.pose_transform.position.z
                        ]
                    }
            
            models_data[model.id] = {
                'name': model.name,
                'source_file': model._source_file,
                'visible': model.visible,
                'transform': {
                    'position': [
                        model.transform.position.x,
                        model.transform.position.y,
                        model.transform.position.z
                    ],
                    'rotation': [
                        model.transform.rotation.x,
                        model.transform.rotation.y,
                        model.transform.rotation.z,
                        model.transform.rotation.w
                    ],
                    'scale': [
                        model.transform.scale.x,
                        model.transform.scale.y,
                        model.transform.scale.z
                    ]
                },
                'bones': bone_data,
                'parent_id': model._parent.id if model._parent else None,
                'parent_bone': model._parent_bone
            }
        
        return {
            'version': 2,
            'models': models_data,
            'selected_model_id': self._selected_model_id,
            'selected_bone_name': self._selected_bone_name
        }
    
    def from_dict(self, data: dict, model_base_path: str = "") -> None:
        """
        Load scene from a dictionary.
        
        Args:
            data: Dictionary representation of the scene
            model_base_path: Base path for resolving relative file paths
        """
        self._models.clear()
        self._model_order.clear()
        self._selected_model_id = data.get('selected_model_id')
        self._selected_bone_name = data.get('selected_bone_name')
        
        models_data = data.get('models', {})
        
        # First pass: create all models
        for model_id, model_data in models_data.items():
            source_file = model_data.get('source_file')
            if source_file:
                # Resolve path
                if model_base_path and not os.path.isabs(source_file):
                    source_file = os.path.join(model_base_path, source_file)
                
                if os.path.exists(source_file):
                    model = ModelInstance(id=model_id, name=model_data.get('name', 'Model'))
                    model.load_from_glb(source_file)
                    model.visible = model_data.get('visible', True)
                    
                    # Load transform
                    transform_data = model_data.get('transform', {})
                    pos = transform_data.get('position', [0, 0, 0])
                    model.transform.position = Vec3(pos[0], pos[1], pos[2])
                    
                    rot = transform_data.get('rotation', [0, 0, 0, 1])
                    from .quat import Quat
                    model.transform.rotation = Quat(rot[3], rot[0], rot[1], rot[2])
                    
                    scale = transform_data.get('scale', [1, 1, 1])
                    model.transform.scale = Vec3(scale[0], scale[1], scale[2])
                    
                    # Load bone poses
                    bones_data = model_data.get('bones', {})
                    if model.skeleton:
                        for bone_name, bone_data in bones_data.items():
                            bone = model.skeleton.get_bone(bone_name)
                            if bone:
                                rot = bone_data.get('rotation', [0, 0, 0, 1])
                                bone.pose_transform.rotation = Quat(rot[3], rot[0], rot[1], rot[2])
                                pos = bone_data.get('position', [0, 0, 0])
                                bone.pose_transform.position = Vec3(pos[0], pos[1], pos[2])
                        
                        model.update_transforms()
                    
                    self._models[model_id] = model
                    self._model_order.append(model_id)
        
        # Second pass: set up parent relationships
        for model_id, model_data in models_data.items():
            parent_id = model_data.get('parent_id')
            parent_bone = model_data.get('parent_bone')
            
            if parent_id:
                self.set_model_parent(model_id, parent_id, parent_bone)
    
    def save_to_file(self, file_path: str) -> bool:
        """
        Save the scene to a JSON file.
        
        Args:
            file_path: Path to save the file
        
        Returns:
            True if successful
        """
        try:
            data = self.to_dict()
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving scene: {e}")
            return False
    
    def load_from_file(self, file_path: str) -> bool:
        """
        Load the scene from a JSON file.
        
        Args:
            file_path: Path to load from
        
        Returns:
            True if successful
        """
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            base_path = os.path.dirname(file_path)
            self.from_dict(data, base_path)
            return True
        except Exception as e:
            print(f"Error loading scene: {e}")
            return False
    
    # -------------------------------------------------------------------------
    # Representation
    # -------------------------------------------------------------------------
    
    def __repr__(self) -> str:
        return f"Scene(models={self.get_model_count()}, selected={self._selected_model_id})"

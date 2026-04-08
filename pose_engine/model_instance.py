"""
ModelInstance - A Complete 3D Model with Skeleton and Mesh
==========================================================

Represents a single loaded 3D model that can be placed in a scene.
Each ModelInstance has its own skeleton, mesh, and transform, allowing
multiple models to be posed independently in the same scene.

Features:
- Skeleton and mesh data
- World transform for positioning in scene
- Parent/child relationships with other models
- Attachment to specific bones of parent models
"""

import uuid
from typing import Optional, List
from .skeleton import Skeleton
from .transform import Transform
from .vec3 import Vec3
from .bone import Bone
from .gltf.builder import MeshData
from .gltf.loader import GLBLoader
from .gltf.builder import build_skeleton_from_gltf, build_mesh_from_gltf


class ModelInstance:
    """
    A complete 3D model instance that can be placed in a scene.
    
    Each ModelInstance contains:
    - A skeleton (bone hierarchy)
    - Mesh data (geometry + skinning)
    - A world transform (position, rotation, scale)
    - Parent/child relationships for model parenting
    
    Multiple ModelInstances can exist in the same scene, each with
    independent poses and transforms.
    """
    
    def __init__(self, id: Optional[str] = None, name: str = "Model"):
        """
        Create a new model instance.
        
        Args:
            id: Unique identifier (auto-generated if None)
            name: Display name for the model
        """
        self.id: str = id or str(uuid.uuid4())[:8]
        self.name: str = name
        
        # Model data
        self.skeleton: Optional[Skeleton] = None
        self.mesh_data: Optional[MeshData] = None
        self._source_file: Optional[str] = None
        
        # World transform (position in scene)
        self.transform = Transform()
        
        # Visibility
        self.visible: bool = True
        
        # Parent/child relationships
        self._parent: Optional['ModelInstance'] = None
        self._children: List['ModelInstance'] = []
        self._parent_bone: Optional[str] = None  # Attach to specific bone
        
        # GPU resources (managed by viewport)
        self._renderer = None  # GLRenderer
        self._skeleton_viz = None  # SkeletonVisualizer
        self._gl_initialized: bool = False
    
    # -------------------------------------------------------------------------
    # Loading
    # -------------------------------------------------------------------------
    
    def load_from_glb(self, file_path: str) -> None:
        """
        Load model from a GLB file.

        Args:
            file_path: Path to the .glb file
        """
        loader = GLBLoader()
        glb_data = loader.load(file_path)

        self.skeleton, bone_mapping = build_skeleton_from_gltf(glb_data, loader=loader)
        # Load ALL meshes from the GLB file (not just the first one)
        self.mesh_data = build_mesh_from_gltf(glb_data, bone_mapping=bone_mapping, loader=loader, load_all_meshes=True)
        self._source_file = file_path

        # Update transforms after loading
        if self.skeleton:
            self.skeleton.update_all_transforms()
    
    @property
    def source_file(self) -> Optional[str]:
        """Get the source file path for this model."""
        return self._source_file
    
    # -------------------------------------------------------------------------
    # Parent/Child Relationships
    # -------------------------------------------------------------------------
    
    def set_parent(self, parent: Optional['ModelInstance'], 
                   bone_name: Optional[str] = None) -> None:
        """
        Set the parent model.
        
        Args:
            parent: Parent model (None to unparent)
            bone_name: Optional bone name to attach to on parent
        """
        # Remove from old parent
        if self._parent is not None:
            self._parent._children.remove(self)
        
        # Set new parent
        self._parent = parent
        self._parent_bone = bone_name
        
        # Add to new parent
        if parent is not None:
            parent._children.append(self)
    
    def get_parent(self) -> Optional['ModelInstance']:
        """Get the parent model."""
        return self._parent
    
    def get_children(self) -> List['ModelInstance']:
        """Get all child models."""
        return self._children.copy()
    
    def get_parent_bone(self) -> Optional[str]:
        """Get the bone name this model is attached to (if any)."""
        return self._parent_bone
    
    def get_world_transform(self) -> Transform:
        """
        Get the world transform accounting for parent hierarchy.
        
        If this model has a parent and is attached to a bone,
        the transform is relative to that bone's world position.
        """
        if self._parent is None:
            return self.transform
        
        # Get parent's world transform
        parent_world = self._parent.get_world_transform()
        
        if self._parent_bone is not None and self._parent.skeleton is not None:
            # Attach to parent's bone
            bone = self._parent.skeleton.get_bone(self._parent_bone)
            if bone is not None:
                bone_transform = bone.get_world_transform()
                # Combine: parent_world * bone_world * local_transform
                combined = Transform.multiply(parent_world, bone_transform)
                return Transform.multiply(combined, self.transform)
        
        # Attach to parent's origin
        return Transform.multiply(parent_world, self.transform)
    
    def get_world_position(self) -> Vec3:
        """Get the world position of this model's origin."""
        world_transform = self.get_world_transform()
        return world_transform.position
    
    # -------------------------------------------------------------------------
    # Transform Helpers
    # -------------------------------------------------------------------------
    
    def set_position(self, x: float, y: float, z: float) -> None:
        """Set the local position of this model."""
        self.transform.set_position(x, y, z)
    
    def translate(self, offset: Vec3) -> None:
        """Translate the model by an offset."""
        self.transform.translate_by(offset)
    
    def rotate_y(self, angle_degrees: float) -> None:
        """Rotate the model around the Y axis (yaw)."""
        self.transform.rotate_by(Vec3(0, 1, 0), angle_degrees)
    
    # -------------------------------------------------------------------------
    # Skeleton Access
    # -------------------------------------------------------------------------
    
    def get_bone_count(self) -> int:
        """Return number of bones in skeleton."""
        return len(self.skeleton) if self.skeleton else 0
    
    def get_bone(self, name: str) -> Optional[Bone]:
        """Get a bone by name."""
        if self.skeleton:
            return self.skeleton.get_bone(name)
        return None
    
    def get_root_bones(self) -> List[Bone]:
        """Get root bones of the skeleton."""
        if self.skeleton:
            return self.skeleton.get_root_bones()
        return []
    
    def update_transforms(self) -> None:
        """Update all bone transforms."""
        if self.skeleton:
            self.skeleton.update_all_transforms()
    
    # -------------------------------------------------------------------------
    # Copying
    # -------------------------------------------------------------------------
    
    def copy(self, name: Optional[str] = None) -> 'ModelInstance':
        """
        Create a copy of this model with independent pose.
        
        The skeleton is deep-copied with current pose.
        Mesh data is shared (no need to duplicate geometry).
        
        Args:
            name: Name for the copy (default: "{name} (copy)")
        
        Returns:
            A new ModelInstance with copied skeleton
        """
        new_model = ModelInstance(
            id=None,  # Generate new ID
            name=name or f"{self.name} (copy)"
        )
        
        # Deep copy skeleton with current pose
        if self.skeleton:
            new_model.skeleton = self._copy_skeleton_with_pose(self.skeleton)
        
        # Share mesh data (geometry doesn't change)
        new_model.mesh_data = self.mesh_data
        new_model._source_file = self._source_file
        
        # Copy transform (position will be offset by caller if desired)
        new_model.transform = Transform()
        new_model.transform.position = Vec3(
            self.transform.position.x,
            self.transform.position.y,
            self.transform.position.z
        )
        new_model.transform.rotation = self.transform.rotation
        new_model.transform.scale = self.transform.scale
        
        return new_model
    
    def _copy_skeleton_with_pose(self, skeleton: Skeleton) -> Skeleton:
        """
        Deep copy a skeleton with its current pose.
        
        Creates new Bone objects with copied pose transforms.
        """
        new_skeleton = Skeleton()
        
        # First pass: create all bones with bind/pose data
        for bone in skeleton:
            new_bone = new_skeleton.add_bone(bone.name)
            
            # Copy bind transform
            new_bone.bind_transform.position = Vec3(
                bone.bind_transform.position.x,
                bone.bind_transform.position.y,
                bone.bind_transform.position.z
            )
            new_bone.bind_transform.rotation = bone.bind_transform.rotation
            new_bone.bind_transform.scale = Vec3(
                bone.bind_transform.scale.x,
                bone.bind_transform.scale.y,
                bone.bind_transform.scale.z
            )
            
            # Copy inverse bind matrix
            if bone.inverse_bind_matrix:
                new_bone.inverse_bind_matrix = bone.inverse_bind_matrix
            
            # Copy pose transform (this is the key part!)
            new_bone.pose_transform.position = Vec3(
                bone.pose_transform.position.x,
                bone.pose_transform.position.y,
                bone.pose_transform.position.z
            )
            new_bone.pose_transform.rotation = bone.pose_transform.rotation
            new_bone.pose_transform.scale = Vec3(
                bone.pose_transform.scale.x,
                bone.pose_transform.scale.y,
                bone.pose_transform.scale.z
            )
        
        # Second pass: build hierarchy
        for old_bone in skeleton:
            if old_bone.parent:
                new_bone = new_skeleton.get_bone(old_bone.name)
                new_parent = new_skeleton.get_bone(old_bone.parent.name)
                if new_bone and new_parent:
                    new_parent.add_child(new_bone)
    
        # Fix root bones: clear and rebuild based on actual parent state
        # (add_bone added all bones as roots, but some now have parents)
        new_skeleton._root_bones.clear()
        for bone in new_skeleton:
            if bone.parent is None:
                new_skeleton._root_bones.append(bone)
    
        # Update transforms
        new_skeleton.update_all_transforms()
        
        return new_skeleton
    
    # -------------------------------------------------------------------------
    # GPU Resources
    # -------------------------------------------------------------------------
    
    def initialize_gl(self) -> bool:
        """
        Initialize OpenGL resources for this model.
        
        Must be called from OpenGL context.
        
        Returns:
            True if initialization succeeded
        """
        if self._gl_initialized:
            return True
        
        # Note: Actual GLRenderer and SkeletonVisualizer creation
        # will be done by the Viewport3D to ensure proper context
        self._gl_initialized = True
        return True
    
    def cleanup_gl(self) -> None:
        """Clean up OpenGL resources."""
        if self._renderer:
            # GLRenderer cleanup would go here
            self._renderer = None
        if self._skeleton_viz:
            self._skeleton_viz = None
        self._gl_initialized = False
    
    # -------------------------------------------------------------------------
    # Representation
    # -------------------------------------------------------------------------
    
    def __repr__(self) -> str:
        return f"ModelInstance('{self.name}', id={self.id}, bones={self.get_bone_count()})"

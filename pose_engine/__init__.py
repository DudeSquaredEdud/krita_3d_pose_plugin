"""
Pose Engine - Professional 3D Posing Library
============================================

A clean, tested 3D math and posing library for the Krita 3D Pose Plugin.

Key Design Principles:
1. Quaternions are the ONLY rotation representation internally
2. Euler angles only exist at the UI layer
3. Every function is tested
4. No external dependencies for core math
"""

__version__ = "1.0.0"

from .vec3 import Vec3
from .quat import Quat
from .mat4 import Mat4
from .transform import Transform
from .bone import Bone
from .skeleton import Skeleton
from .skinning import VertexSkinning, SkinningData, apply_skinning, compute_bone_matrices_from_skeleton
from .pose_state import BonePose, PoseSnapshot, UndoRedoStack, PoseSerializer

__all__ = [
    'Vec3', 'Quat', 'Mat4', 'Transform',
    'Bone', 'Skeleton',
    'VertexSkinning', 'SkinningData', 'apply_skinning', 'compute_bone_matrices_from_skeleton',
    'BonePose', 'PoseSnapshot', 'UndoRedoStack', 'PoseSerializer'
]

"""
glTF Module - GLB File Loading
==============================

Parses GLB (glTF 2.0 binary) files and builds skeleton/mesh data.

glTF 2.0 Specification: https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html
"""

from .loader import GLBLoader, GLBData
from .builder import build_skeleton_from_gltf, build_mesh_from_gltf

__all__ = [
    'GLBLoader', 'GLBData',
    'build_skeleton_from_gltf', 'build_mesh_from_gltf'
]

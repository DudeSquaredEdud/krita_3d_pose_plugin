"""
GLB Loader - Parse GLB Binary Files
===================================

GLB is the binary format for glTF 2.0.
Structure:
- Header: 12 bytes (magic, version, length)
- JSON chunk: glTF data (scenes, nodes, meshes, etc.)
- Binary chunk: Raw buffer data (vertices, indices, etc.)

Reference: https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html
"""

import struct
import json
import base64
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass


@dataclass
class Accessor:
    """glTF accessor - describes how to interpret buffer data."""
    buffer_view: int
    byte_offset: int
    component_type: int
    count: int
    type: str
    min_vals: List[float]
    max_vals: List[float]
    
    def get_component_size(self) -> int:
        """Get size of a single component in bytes."""
        sizes = {5120: 1, 5121: 1, 5122: 2, 5123: 2, 5125: 4, 5126: 4}
        return sizes.get(self.component_type, 4)
    
    def get_num_components(self) -> int:
        """Get number of components per element."""
        counts = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT4': 16}
        return counts.get(self.type, 1)


@dataclass
class BufferView:
    """glTF buffer view - a slice of a buffer."""
    buffer: int
    byte_offset: int
    byte_length: int
    byte_stride: Optional[int]
    target: Optional[int]


@dataclass
class SkinData:
    """glTF skin data."""
    name: str
    joints: List[int]
    inverse_bind_matrices: Optional[int]
    skeleton: Optional[int]


@dataclass
class MeshData:
    """glTF mesh data."""
    name: str
    primitives: List[Dict[str, Any]]


@dataclass
class NodeData:
    """glTF node data."""
    name: str
    children: List[int]
    mesh: Optional[int]
    skin: Optional[int]
    translation: List[float]
    rotation: List[float]
    scale: List[float]
    matrix: Optional[List[float]]


@dataclass
class GLBData:
    """Parsed GLB file data."""
    json_data: Dict[str, Any]
    binary_buffer: bytes
    
    # Parsed structures
    accessors: List[Accessor]
    buffer_views: List[BufferView]
    nodes: List[NodeData]
    skins: List[SkinData]
    meshes: List[MeshData]
    
    def get_accessor_data(self, accessor_index: int) -> bytes:
        """Get raw data for an accessor."""
        accessor = self.accessors[accessor_index]
        buffer_view = self.buffer_views[accessor.buffer_view]
        
        start = buffer_view.byte_offset + accessor.byte_offset
        end = start + accessor.count * accessor.get_num_components() * accessor.get_component_size()
        
        return self.binary_buffer[start:end]


class GLBLoader:
    """
    Loads GLB (glTF 2.0 binary) files.
    
    Usage:
        loader = GLBLoader()
        data = loader.load("model.glb")
        # Access parsed data
        for node in data.nodes:
            print(node.name)
    """
    
    GLB_MAGIC = 0x46546C67  # "glTF" in little-endian
    GLB_VERSION = 2
    CHUNK_JSON = 0x4E4F534A  # "JSON"
    CHUNK_BIN = 0x004E4942   # "BIN\0"
    
    def __init__(self):
        """Create a new GLB loader."""
        self._data: Optional[GLBData] = None
    
    def load(self, filepath: str) -> GLBData:
        """
        Load a GLB file.
        
        Args:
            filepath: Path to the GLB file
        
        Returns:
            GLBData with parsed glTF structures
        
        Raises:
            ValueError: If file format is invalid
        """
        with open(filepath, 'rb') as f:
            data = f.read()
        
        return self.load_from_bytes(data)
    
    def load_from_bytes(self, data: bytes) -> GLBData:
        """
        Load GLB from raw bytes.
        
        Args:
            data: Raw GLB file data
        
        Returns:
            GLBData with parsed glTF structures
        """
        # Parse header
        if len(data) < 12:
            raise ValueError("File too small to be a valid GLB")
        
        magic, version, length = struct.unpack('<III', data[:12])
        
        if magic != self.GLB_MAGIC:
            raise ValueError(f"Invalid GLB magic: {magic:#x}, expected {self.GLB_MAGIC:#x}")
        
        if version != self.GLB_VERSION:
            raise ValueError(f"Unsupported GLB version: {version}, expected {self.GLB_VERSION}")
        
        # Parse chunks
        offset = 12
        json_data = None
        binary_buffer = b''
        
        while offset < len(data):
            chunk_length, chunk_type = struct.unpack('<II', data[offset:offset+8])
            chunk_data = data[offset+8:offset+8+chunk_length]
            
            if chunk_type == self.CHUNK_JSON:
                json_data = json.loads(chunk_data.decode('utf-8'))
            elif chunk_type == self.CHUNK_BIN:
                binary_buffer = chunk_data
            
            offset += 8 + chunk_length
        
        if json_data is None:
            raise ValueError("GLB missing JSON chunk")
        
        # Handle embedded buffer (GLB binary chunk)
        if 'buffers' in json_data and len(json_data['buffers']) > 0:
            # Check if buffer uses embedded data
            buffer_info = json_data['buffers'][0]
            if 'uri' not in buffer_info:
                # Embedded buffer - use binary chunk
                json_data['buffers'][0]['_embedded'] = True
        
        # Parse structures
        accessors = self._parse_accessors(json_data.get('accessors', []))
        buffer_views = self._parse_buffer_views(json_data.get('bufferViews', []))
        nodes = self._parse_nodes(json_data.get('nodes', []))
        skins = self._parse_skins(json_data.get('skins', []))
        meshes = self._parse_meshes(json_data.get('meshes', []))
        
        self._data = GLBData(
            json_data=json_data,
            binary_buffer=binary_buffer,
            accessors=accessors,
            buffer_views=buffer_views,
            nodes=nodes,
            skins=skins,
            meshes=meshes
        )
        
        return self._data
    
    def _parse_accessors(self, accessors_data: List[Dict]) -> List[Accessor]:
        """Parse glTF accessors."""
        accessors = []
        
        for acc in accessors_data:
            accessor = Accessor(
                buffer_view=acc.get('bufferView', 0),
                byte_offset=acc.get('byteOffset', 0),
                component_type=acc['componentType'],
                count=acc['count'],
                type=acc['type'],
                min_vals=acc.get('min', []),
                max_vals=acc.get('max', [])
            )
            accessors.append(accessor)
        
        return accessors
    
    def _parse_buffer_views(self, buffer_views_data: List[Dict]) -> List[BufferView]:
        """Parse glTF buffer views."""
        buffer_views = []
        
        for bv in buffer_views_data:
            buffer_view = BufferView(
                buffer=bv.get('buffer', 0),
                byte_offset=bv.get('byteOffset', 0),
                byte_length=bv['byteLength'],
                byte_stride=bv.get('byteStride'),
                target=bv.get('target')
            )
            buffer_views.append(buffer_view)
        
        return buffer_views
    
    def _parse_nodes(self, nodes_data: List[Dict]) -> List[NodeData]:
        """Parse glTF nodes."""
        nodes = []
        
        for node in nodes_data:
            node_data = NodeData(
                name=node.get('name', f'node_{len(nodes)}'),
                children=node.get('children', []),
                mesh=node.get('mesh'),
                skin=node.get('skin'),
                translation=node.get('translation', [0, 0, 0]),
                rotation=node.get('rotation', [0, 0, 0, 1]),
                scale=node.get('scale', [1, 1, 1]),
                matrix=node.get('matrix')
            )
            nodes.append(node_data)
        
        return nodes
    
    def _parse_skins(self, skins_data: List[Dict]) -> List[SkinData]:
        """Parse glTF skins."""
        skins = []
        
        for skin in skins_data:
            skin_data = SkinData(
                name=skin.get('name', f'skin_{len(skins)}'),
                joints=skin['joints'],
                inverse_bind_matrices=skin.get('inverseBindMatrices'),
                skeleton=skin.get('skeleton')
            )
            skins.append(skin_data)
        
        return skins
    
    def _parse_meshes(self, meshes_data: List[Dict]) -> List[MeshData]:
        """Parse glTF meshes."""
        meshes = []
        
        for mesh in meshes_data:
            mesh_data = MeshData(
                name=mesh.get('name', f'mesh_{len(meshes)}'),
                primitives=mesh.get('primitives', [])
            )
            meshes.append(mesh_data)
        
        return meshes
    
    def get_positions(self, accessor_index: int) -> List[Tuple[float, float, float]]:
        """Get vertex positions from an accessor."""
        return self._get_vec3_data(accessor_index)
    
    def get_normals(self, accessor_index: int) -> List[Tuple[float, float, float]]:
        """Get vertex normals from an accessor."""
        return self._get_vec3_data(accessor_index)
    
    def get_joints(self, accessor_index: int) -> List[Tuple[int, int, int, int]]:
        """Get joint indices (bone indices) from an accessor."""
        raw_data = self._data.get_accessor_data(accessor_index)
        accessor = self._data.accessors[accessor_index]
        
        # Component type is usually 5121 (unsigned byte) or 5123 (unsigned short)
        if accessor.component_type == 5121:
            # Unsigned byte
            format_str = '<BBBB'
        elif accessor.component_type == 5123:
            # Unsigned short
            format_str = '<HHHH'
        else:
            format_str = '<HHHH'
        
        component_size = struct.calcsize(format_str)
        joints = []
        
        for i in range(accessor.count):
            offset = i * component_size
            values = struct.unpack(format_str, raw_data[offset:offset+component_size])
            joints.append(values)
        
        return joints
    
    def get_weights(self, accessor_index: int) -> List[Tuple[float, float, float, float]]:
        """Get joint weights from an accessor."""
        raw_data = self._data.get_accessor_data(accessor_index)
        accessor = self._data.accessors[accessor_index]
        
        # Weights are usually VEC4 floats
        weights = []
        component_size = 16  # 4 floats
        
        for i in range(accessor.count):
            offset = i * component_size
            values = struct.unpack('<ffff', raw_data[offset:offset+component_size])
            weights.append(values)
        
        return weights
    
    def get_indices(self, accessor_index: int) -> List[int]:
        """Get triangle indices from an accessor."""
        raw_data = self._data.get_accessor_data(accessor_index)
        accessor = self._data.accessors[accessor_index]
        
        if accessor.component_type == 5121:
            # Unsigned byte
            format_str = '<B'
        elif accessor.component_type == 5123:
            # Unsigned short
            format_str = '<H'
        elif accessor.component_type == 5125:
            # Unsigned int
            format_str = '<I'
        else:
            format_str = '<H'
        
        component_size = struct.calcsize(format_str)
        indices = []
        
        for i in range(accessor.count):
            offset = i * component_size
            value = struct.unpack(format_str, raw_data[offset:offset+component_size])[0]
            indices.append(value)
        
        return indices
    
    def get_inverse_bind_matrices(self, accessor_index: int) -> List[List[float]]:
        """Get inverse bind matrices from an accessor."""
        raw_data = self._data.get_accessor_data(accessor_index)
        accessor = self._data.accessors[accessor_index]
        
        matrices = []
        matrix_size = 64  # 16 floats
        
        for i in range(accessor.count):
            offset = i * matrix_size
            values = struct.unpack('<16f', raw_data[offset:offset+matrix_size])
            matrices.append(list(values))
        
        return matrices
    
    def _get_vec3_data(self, accessor_index: int) -> List[Tuple[float, float, float]]:
        """Get VEC3 data from an accessor."""
        raw_data = self._data.get_accessor_data(accessor_index)
        accessor = self._data.accessors[accessor_index]
        
        vec3s = []
        component_size = 12  # 3 floats
        
        for i in range(accessor.count):
            offset = i * component_size
            values = struct.unpack('<fff', raw_data[offset:offset+component_size])
            vec3s.append(values)
        
        return vec3s

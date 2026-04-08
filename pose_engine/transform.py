"""
Transform - Position, Rotation, Scale
=====================================

A 3D transform combining position, rotation (quaternion), and scale.
Uses lazy matrix computation for efficiency.
"""

from .vec3 import Vec3
from .quat import Quat
from .mat4 import Mat4


class Transform:
    """
    A 3D transform with position, rotation, and scale.
    
    Uses quaternion for rotation to avoid gimbal lock.
    Matrix is computed lazily when needed.
    """
    
    def __init__(self):
        self._position = Vec3(0, 0, 0)
        self._rotation = Quat.identity()
        self._scale = Vec3(1, 1, 1)
        self._matrix_dirty = True
        self._matrix = Mat4.identity()
    
    @property
    def position(self) -> Vec3:
        return self._position
    
    @position.setter
    def position(self, value: Vec3):
        self._position = value
        self._matrix_dirty = True
    
    @property
    def rotation(self) -> Quat:
        return self._rotation
    
    @rotation.setter
    def rotation(self, value: Quat):
        self._rotation = value.normalized()
        self._matrix_dirty = True
    
    @property
    def scale(self) -> Vec3:
        return self._scale
    
    @scale.setter
    def scale(self, value: Vec3):
        self._scale = value
        self._matrix_dirty = True
    
    def get_matrix(self) -> Mat4:
        """Get local-to-parent transformation matrix."""
        if self._matrix_dirty:
            self._matrix = Mat4.from_trs(
                self._position, self._rotation, self._scale
            )
            self._matrix_dirty = False
        return self._matrix
    
    def to_matrix(self) -> Mat4:
        """Alias for get_matrix()."""
        return self.get_matrix()
    
    def set_position(self, x: float, y: float, z: float) -> None:
        """Set position from components."""
        self._position = Vec3(x, y, z)
        self._matrix_dirty = True
    
    def set_rotation_euler_degrees(self, x: float, y: float, z: float) -> None:
        """Set rotation from Euler angles in degrees (XYZ order)."""
        self._rotation = Quat.from_euler_degrees(x, y, z)
        self._matrix_dirty = True
    
    def set_rotation_axis_angle(self, axis: Vec3, angle_deg: float) -> None:
        """Set rotation from axis and angle in degrees."""
        self._rotation = Quat.from_axis_angle_degrees(axis, angle_deg)
        self._matrix_dirty = True
    
    def rotate_by(self, axis: Vec3, angle_deg: float) -> None:
        """Apply additional rotation around world axis."""
        delta = Quat.from_axis_angle_degrees(axis, angle_deg)
        self._rotation = delta * self._rotation
        self._matrix_dirty = True
    
    def rotate_local_by(self, axis: Vec3, angle_deg: float) -> None:
        """Apply additional rotation around local axis."""
        delta = Quat.from_axis_angle_degrees(axis, angle_deg)
        self._rotation = self._rotation * delta
        self._matrix_dirty = True
    
    def translate_by(self, offset: Vec3) -> None:
        """Add offset to position."""
        self._position = self._position + offset
        self._matrix_dirty = True
    
    def transform_point(self, p: Vec3) -> Vec3:
        """Transform a point from local to parent space."""
        return self.get_matrix().transform_point(p)
    
    def transform_vector(self, v: Vec3) -> Vec3:
        """Transform a vector from local to parent space."""
        return self.get_matrix().transform_vector(v)
    
    def inverse_transform_point(self, p: Vec3) -> Vec3:
        """Transform a point from parent to local space."""
        return self.get_matrix().inverse().transform_point(p)
    
    def get_euler_degrees(self) -> tuple:
        """Get rotation as Euler angles in degrees (for UI display)."""
        return self._rotation.to_euler_degrees()
    
    def copy(self) -> 'Transform':
        """Create a copy of this transform."""
        t = Transform()
        t._position = Vec3(self._position.x, self._position.y, self._position.z)
        t._rotation = Quat(self._rotation.w, self._rotation.x, 
                          self._rotation.y, self._rotation.z)
        t._scale = Vec3(self._scale.x, self._scale.y, self._scale.z)
        t._matrix_dirty = True
        return t
    
    def lerp_to(self, target: 'Transform', t: float) -> 'Transform':
        """Interpolate towards target transform."""
        result = Transform()
        result._position = self._position.lerp(target._position, t)
        result._rotation = Quat.slerp(self._rotation, target._rotation, t)
        result._scale = self._scale.lerp(target._scale, t)
        return result
    
    @staticmethod
    def multiply(parent: 'Transform', child: 'Transform') -> 'Transform':
        """
        Combine two transforms: result = parent * child.

        The result represents applying child's transform first,
        then parent's transform.

        For hierarchical transforms (parent_world * local):
        - child is the local transform
        - parent is the parent's world transform
        - Result: apply local first, then parent

        For bone posing (bind * pose):
        - bind is the original pose from the model
        - pose is the user's additional modification
        - Result: apply bind first, then pose
        """
        result = Transform()

        # Combine positions: parent_pos + parent_rot * (parent_scale * child_pos)
        scaled_child_pos = Vec3(
            child._position.x * parent._scale.x,
            child._position.y * parent._scale.y,
            child._position.z * parent._scale.z
        )
        result._position = parent._position + parent._rotation.rotate_vector(scaled_child_pos)

        # Combine rotations
        # Quaternion multiplication: q1 * q2 means "rotate by q2, then by q1"
        # For parent * child: we want "rotate by child, then by parent"
        # So the order is: parent * child
        result._rotation = parent._rotation * child._rotation

        # Combine scales
        result._scale = Vec3(
            parent._scale.x * child._scale.x,
            parent._scale.y * child._scale.y,
            parent._scale.z * child._scale.z
        )

        result._matrix_dirty = True
        return result
    
    def __repr__(self) -> str:
        euler = self.get_euler_degrees()
        return (f"Transform(pos=({self._position.x:.2f}, {self._position.y:.2f}, {self._position.z:.2f}), "
                f"rot=({euler[0]:.1f}°, {euler[1]:.1f}°, {euler[2]:.1f}°), "
                f"scale=({self._scale.x:.2f}, {self._scale.y:.2f}, {self._scale.z:.2f}))")

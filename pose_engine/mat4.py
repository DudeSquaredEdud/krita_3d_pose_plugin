"""
Mat4 - 4x4 Transformation Matrix
================================

Column-major storage (OpenGL convention).
Element (row, col) is at index row + 4*col.

Used for:
- Combining transforms
- Skinning matrices
- Rendering
"""

import math
from typing import Tuple, Optional
from .vec3 import Vec3
from .quat import Quat


class Mat4:
    """4x4 transformation matrix in column-major order."""
    
    __slots__ = ('m',)
    
    def __init__(self, data: Optional[list] = None):
        """
        Initialize matrix.
        
        Args:
            data: 16-element list in column-major order, or None for identity
        """
        if data is None:
            # Identity matrix
            self.m = [1, 0, 0, 0,
                      0, 1, 0, 0,
                      0, 0, 1, 0,
                      0, 0, 0, 1]
        else:
            self.m = list(data)
    
    def __repr__(self) -> str:
        return (f"Mat4(\n"
                f"  {self.m[0]:.4f} {self.m[4]:.4f} {self.m[8]:.4f} {self.m[12]:.4f}\n"
                f"  {self.m[1]:.4f} {self.m[5]:.4f} {self.m[9]:.4f} {self.m[13]:.4f}\n"
                f"  {self.m[2]:.4f} {self.m[6]:.4f} {self.m[10]:.4f} {self.m[14]:.4f}\n"
                f"  {self.m[3]:.4f} {self.m[7]:.4f} {self.m[11]:.4f} {self.m[15]:.4f}\n)")
    
    def __mul__(self, other: 'Mat4') -> 'Mat4':
        """Matrix multiplication."""
        a = self.m
        b = other.m
        result = [0] * 16
        
        for col in range(4):
            for row in range(4):
                result[row + 4*col] = (
                    a[row + 4*0] * b[0 + 4*col] +
                    a[row + 4*1] * b[1 + 4*col] +
                    a[row + 4*2] * b[2 + 4*col] +
                    a[row + 4*3] * b[3 + 4*col]
                )
        
        return Mat4(result)
    
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Mat4):
            return False
        for i in range(16):
            if abs(self.m[i] - other.m[i]) > 1e-10:
                return False
        return True
    
    def get(self, row: int, col: int) -> float:
        """Get element at (row, col)."""
        return self.m[row + 4*col]
    
    def set(self, row: int, col: int, value: float) -> None:
        """Set element at (row, col)."""
        self.m[row + 4*col] = value
    
    def transform_point(self, p: Vec3) -> Vec3:
        """Transform a point (includes translation)."""
        x = self.m[0] * p.x + self.m[4] * p.y + self.m[8] * p.z + self.m[12]
        y = self.m[1] * p.x + self.m[5] * p.y + self.m[9] * p.z + self.m[13]
        z = self.m[2] * p.x + self.m[6] * p.y + self.m[10] * p.z + self.m[14]
        w = self.m[3] * p.x + self.m[7] * p.y + self.m[11] * p.z + self.m[15]
        
        if abs(w) > 1e-10:
            return Vec3(x/w, y/w, z/w)
        return Vec3(x, y, z)
    
    def transform_vector(self, v: Vec3) -> Vec3:
        """Transform a vector (no translation)."""
        x = self.m[0] * v.x + self.m[4] * v.y + self.m[8] * v.z
        y = self.m[1] * v.x + self.m[5] * v.y + self.m[9] * v.z
        z = self.m[2] * v.x + self.m[6] * v.y + self.m[10] * v.z
        return Vec3(x, y, z)
    
    def transpose(self) -> 'Mat4':
        """Return transpose."""
        return Mat4([
            self.m[0], self.m[4], self.m[8], self.m[12],
            self.m[1], self.m[5], self.m[9], self.m[13],
            self.m[2], self.m[6], self.m[10], self.m[14],
            self.m[3], self.m[7], self.m[11], self.m[15]
        ])
    
    def inverse(self) -> 'Mat4':
        """Return inverse matrix."""
        m = self.m
        
        # Extract rotation part
        r00, r01, r02 = m[0], m[4], m[8]
        r10, r11, r12 = m[1], m[5], m[9]
        r20, r21, r22 = m[2], m[6], m[10]
        
        # Translation
        tx, ty, tz = m[12], m[13], m[14]
        
        # Determinant of rotation part
        det = (r00 * (r11*r22 - r12*r21) -
               r01 * (r10*r22 - r12*r20) +
               r02 * (r10*r21 - r11*r20))
        
        if abs(det) < 1e-10:
            return Mat4.identity()
        
        inv_det = 1.0 / det
        
        # Inverse rotation
        inv = [0] * 16
        inv[0] = (r11*r22 - r21*r12) * inv_det
        inv[1] = (r02*r21 - r01*r22) * inv_det
        inv[2] = (r01*r12 - r02*r11) * inv_det
        inv[4] = (r12*r20 - r10*r22) * inv_det
        inv[5] = (r00*r22 - r02*r20) * inv_det
        inv[6] = (r02*r10 - r00*r12) * inv_det
        inv[8] = (r10*r21 - r20*r11) * inv_det
        inv[9] = (r20*r01 - r00*r21) * inv_det
        inv[10] = (r00*r11 - r01*r10) * inv_det
        
        # Inverse translation
        inv[12] = -(inv[0]*tx + inv[4]*ty + inv[8]*tz)
        inv[13] = -(inv[1]*tx + inv[5]*ty + inv[9]*tz)
        inv[14] = -(inv[2]*tx + inv[6]*ty + inv[10]*tz)
        
        inv[3] = inv[7] = inv[11] = 0
        inv[15] = 1
        
        return Mat4(inv)
    
    def get_translation(self) -> Vec3:
        """Extract translation."""
        return Vec3(self.m[12], self.m[13], self.m[14])
    
    def get_rotation(self) -> Quat:
        """Extract rotation as quaternion."""
        return Quat.from_matrix(self)
    
    def get_scale(self) -> Vec3:
        """Extract scale."""
        sx = Vec3(self.m[0], self.m[1], self.m[2]).length()
        sy = Vec3(self.m[4], self.m[5], self.m[6]).length()
        sz = Vec3(self.m[8], self.m[9], self.m[10]).length()
        return Vec3(sx, sy, sz)
    
    def to_list(self) -> list:
        """Convert to flat list (column-major)."""
        return self.m.copy()
    
    def to_tuple(self) -> Tuple[float, ...]:
        """Convert to tuple (column-major)."""
        return tuple(self.m)
    
    @classmethod
    def identity(cls) -> 'Mat4':
        """Identity matrix."""
        return cls()
    
    @classmethod
    def translation(cls, v: Vec3) -> 'Mat4':
        """Create translation matrix."""
        return cls([
            1, 0, 0, 0,
            0, 1, 0, 0,
            0, 0, 1, 0,
            v.x, v.y, v.z, 1
        ])
    
    @classmethod
    def scale(cls, v: Vec3) -> 'Mat4':
        """Create scale matrix."""
        return cls([
            v.x, 0, 0, 0,
            0, v.y, 0, 0,
            0, 0, v.z, 0,
            0, 0, 0, 1
        ])
    
    @classmethod
    def rotation_x(cls, angle_rad: float) -> 'Mat4':
        """Create rotation matrix around X axis."""
        c, s = math.cos(angle_rad), math.sin(angle_rad)
        return cls([
            1, 0, 0, 0,
            0, c, s, 0,
            0, -s, c, 0,
            0, 0, 0, 1
        ])
    
    @classmethod
    def rotation_y(cls, angle_rad: float) -> 'Mat4':
        """Create rotation matrix around Y axis."""
        c, s = math.cos(angle_rad), math.sin(angle_rad)
        return cls([
            c, 0, -s, 0,
            0, 1, 0, 0,
            s, 0, c, 0,
            0, 0, 0, 1
        ])
    
    @classmethod
    def rotation_z(cls, angle_rad: float) -> 'Mat4':
        """Create rotation matrix around Z axis."""
        c, s = math.cos(angle_rad), math.sin(angle_rad)
        return cls([
            c, s, 0, 0,
            -s, c, 0, 0,
            0, 0, 1, 0,
            0, 0, 0, 1
        ])
    
    @classmethod
    def from_trs(cls, translation: Vec3, rotation: Quat, scale: Vec3) -> 'Mat4':
        """Create matrix from TRS (translation, rotation, scale)."""
        t = cls.translation(translation)
        r = rotation.to_matrix()
        s = cls.scale(scale)
        return t * (r * s)
    
    @classmethod
    def from_rotation(cls, rotation: Quat) -> 'Mat4':
        """Create matrix from rotation only."""
        return rotation.to_matrix()


# Add method to Quat for converting to matrix
def _quat_to_matrix(self) -> Mat4:
    """Convert quaternion to 4x4 rotation matrix."""
    n = self.normalized()
    w, x, y, z = n.w, n.x, n.y, n.z
    
    xx = x * x
    yy = y * y
    zz = z * z
    xy = x * y
    xz = x * z
    yz = y * z
    wx = w * x
    wy = w * y
    wz = w * z
    
    return Mat4([
        1 - 2*yy - 2*zz, 2*xy + 2*wz, 2*xz - 2*wy, 0,
        2*xy - 2*wz, 1 - 2*xx - 2*zz, 2*yz + 2*wx, 0,
        2*xz + 2*wy, 2*yz - 2*wx, 1 - 2*xx - 2*yy, 0,
        0, 0, 0, 1
    ])


# Add method to Quat for creating from matrix
@classmethod
def _quat_from_matrix(cls, m: Mat4) -> 'Quat':
    """Create quaternion from 4x4 rotation matrix."""
    trace = m.m[0] + m.m[5] + m.m[10]
    
    if trace > 0:
        s = 0.5 / math.sqrt(trace + 1.0)
        w = 0.25 / s
        x = (m.m[6] - m.m[9]) * s
        y = (m.m[8] - m.m[2]) * s
        z = (m.m[1] - m.m[4]) * s
    elif m.m[0] > m.m[5] and m.m[0] > m.m[10]:
        s = 2.0 * math.sqrt(1.0 + m.m[0] - m.m[5] - m.m[10])
        w = (m.m[6] - m.m[9]) / s
        x = 0.25 * s
        y = (m.m[4] + m.m[1]) / s
        z = (m.m[8] + m.m[2]) / s
    elif m.m[5] > m.m[10]:
        s = 2.0 * math.sqrt(1.0 + m.m[5] - m.m[0] - m.m[10])
        w = (m.m[8] - m.m[2]) / s
        x = (m.m[4] + m.m[1]) / s
        y = 0.25 * s
        z = (m.m[9] + m.m[6]) / s
    else:
        s = 2.0 * math.sqrt(1.0 + m.m[10] - m.m[0] - m.m[5])
        w = (m.m[1] - m.m[4]) / s
        x = (m.m[8] + m.m[2]) / s
        y = (m.m[9] + m.m[6]) / s
        z = 0.25 * s
    
    return cls(w, x, y, z).normalized()


# Monkey-patch the methods onto Quat
Quat.to_matrix = _quat_to_matrix
Quat.from_matrix = _quat_from_matrix

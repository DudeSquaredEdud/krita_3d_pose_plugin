"""
Quat - Quaternion Class
=======================

Quaternion for 3D rotations. No gimbal lock!

Storage: (w, x, y, z) where w is the scalar part.
This matches the standard mathematical convention.

Key operations:
- Multiplication: combines rotations (q1 * q2)
- rotate_vector(): applies rotation to a vector
- slerp(): smooth interpolation between rotations
"""

import math
from typing import Tuple
from .vec3 import Vec3


class Quat:
    """Quaternion for 3D rotations."""
    
    __slots__ = ('w', 'x', 'y', 'z')
    
    def __init__(self, w: float = 1.0, x: float = 0.0, y: float = 0.0, z: float = 0.0):
        """Create quaternion. Default is identity (no rotation)."""
        self.w = float(w)
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)
    
    def __repr__(self) -> str:
        return f"Quat(w={self.w:.4f}, x={self.x:.4f}, y={self.y:.4f}, z={self.z:.4f})"
    
    def __mul__(self, other: 'Quat') -> 'Quat':
        """
        Quaternion multiplication (combines rotations).
        
        Order matters: q1 * q2 means "apply q2, then q1"
        This matches the convention used in Unity/Unreal.
        """
        w1, x1, y1, z1 = self.w, self.x, self.y, self.z
        w2, x2, y2, z2 = other.w, other.x, other.y, other.z
        
        return Quat(
            w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2,
            w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
            w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
            w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2
        )
    
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Quat):
            return False
        return (abs(self.w - other.w) < 1e-10 and 
                abs(self.x - other.x) < 1e-10 and
                abs(self.y - other.y) < 1e-10 and 
                abs(self.z - other.z) < 1e-10)
    
    def conjugate(self) -> 'Quat':
        """Return conjugate (inverse for unit quaternions)."""
        return Quat(self.w, -self.x, -self.y, -self.z)
    
    def length(self) -> float:
        """Quaternion magnitude."""
        return math.sqrt(self.w * self.w + self.x * self.x + 
                        self.y * self.y + self.z * self.z)
    
    def normalized(self) -> 'Quat':
        """Return unit quaternion."""
        length = self.length()
        if length < 1e-10:
            return Quat.identity()
        return Quat(self.w / length, self.x / length, 
                   self.y / length, self.z / length)
    
    def rotate_vector(self, v: Vec3) -> Vec3:
        """
        Rotate a vector by this quaternion.
        
        Uses the optimized formula:
        v' = v + 2 * (q.xyz × (q.xyz × v + q.w * v))
        """
        qv = Vec3(self.x, self.y, self.z)
        uv = qv.cross(v)
        uuv = qv.cross(uv)
        return v + (uv * (2.0 * self.w) + uuv * 2.0)
    
    def to_euler_degrees(self) -> Tuple[float, float, float]:
        """
        Convert to Euler angles (XYZ order) in degrees.

        WARNING: This is for UI display only!
        Never use Euler angles for internal computation.
        """
        # Normalize first
        n = self.normalized()
        w, x, y, z = n.w, n.x, n.y, n.z

        # Pitch (Y-axis rotation) - clamp to avoid numerical issues
        sinp = 2 * (w * y - z * x)
        sinp = max(-1.0, min(1.0, sinp))  # Clamp to [-1, 1]
        pitch = math.degrees(math.asin(sinp))

        # Check for gimbal lock (pitch near ±90°)
        if abs(sinp) > 0.9999:
            # Gimbal lock: set roll to 0, compute yaw only
            roll = 0.0
            # When pitch is +90°, yaw and roll combine
            # When pitch is -90°, yaw and roll are opposite
            yaw = math.degrees(math.atan2(2 * (x * y + w * z), 1 - 2 * (y * y + z * z)))
        else:
            # Roll (X-axis rotation)
            sinr_cosp = 2 * (w * x + y * z)
            cosr_cosp = 1 - 2 * (x * x + y * y)
            roll = math.degrees(math.atan2(sinr_cosp, cosr_cosp))

            # Yaw (Z-axis rotation)
            siny_cosp = 2 * (w * z + x * y)
            cosy_cosp = 1 - 2 * (y * y + z * z)
            yaw = math.degrees(math.atan2(siny_cosp, cosy_cosp))

        return (roll, pitch, yaw)
    
    def to_tuple(self) -> Tuple[float, float, float, float]:
        """Convert to (w, x, y, z) tuple."""
        return (self.w, self.x, self.y, self.z)

    def to_axis_angle(self) -> Tuple['Vec3', float]:
        """
        Convert quaternion to axis and angle.
        
        Returns:
            Tuple of (axis, angle_rad) where axis is the rotation axis
            and angle_rad is the rotation angle in radians.
        """
        from .vec3 import Vec3
        
        # Handle identity quaternion
        if abs(self.w) >= 1.0:
            return (Vec3(0, 1, 0), 0.0)
        
        # Calculate the angle
        angle = 2.0 * math.acos(abs(self.w))
        
        # Calculate the axis
        s = math.sqrt(1.0 - self.w * self.w)
        if s < 1e-10:
            # No rotation, return arbitrary axis
            return (Vec3(0, 1, 0), 0.0)
        
        axis = Vec3(self.x / s, self.y / s, self.z / s)
        return (axis, angle)

    def inverse(self) -> 'Quat':
        """Return inverse quaternion."""
        length_sq = self.w * self.w + self.x * self.x + self.y * self.y + self.z * self.z
        if length_sq < 1e-10:
            return Quat.identity()
        conj = self.conjugate()
        return Quat(conj.w / length_sq, conj.x / length_sq, 
                    conj.y / length_sq, conj.z / length_sq)
    
    @classmethod
    def identity(cls) -> 'Quat':
        """Identity quaternion (no rotation)."""
        return cls(1.0, 0.0, 0.0, 0.0)
    
    @classmethod
    def from_axis_angle(cls, axis: Vec3, angle_rad: float) -> 'Quat':
        """
        Create quaternion from axis and angle (in radians).
        
        Rotates around the axis by the given angle.
        """
        axis = axis.normalized()
        half_angle = angle_rad * 0.5
        s = math.sin(half_angle)
        return cls(
            math.cos(half_angle),
            axis.x * s,
            axis.y * s,
            axis.z * s
        )
    
    @classmethod
    def from_axis_angle_degrees(cls, axis: Vec3, angle_deg: float) -> 'Quat':
        """Create quaternion from axis and angle in degrees."""
        return cls.from_axis_angle(axis, math.radians(angle_deg))
    
    @classmethod
    def from_euler_degrees(cls, x: float, y: float, z: float) -> 'Quat':
        """
        Create quaternion from Euler angles in degrees (XYZ order).
        
        WARNING: Use this only for converting UI input!
        """
        rx = math.radians(x) * 0.5
        ry = math.radians(y) * 0.5
        rz = math.radians(z) * 0.5
        
        cx, sx = math.cos(rx), math.sin(rx)
        cy, sy = math.cos(ry), math.sin(ry)
        cz, sz = math.cos(rz), math.sin(rz)
        
        # XYZ order
        w = cx * cy * cz + sx * sy * sz
        qx = sx * cy * cz - cx * sy * sz
        qy = cx * sy * cz + sx * cy * sz
        qz = cx * cy * sz - sx * sy * cz
        
        return cls(w, qx, qy, qz)
    
    @classmethod
    def shortest_arc(cls, v1: Vec3, v2: Vec3) -> 'Quat':
        """
        Create quaternion that rotates v1 to v2.
        
        This is the shortest rotation between the two vectors.
        """
        v1 = v1.normalized()
        v2 = v2.normalized()
        
        dot = v1.dot(v2)
        
        # Vectors are parallel
        if dot > 0.99999:
            return cls.identity()
        
        # Vectors are opposite
        if dot < -0.99999:
            # Use perpendicular axis
            if abs(v1.x) > abs(v1.z):
                perp = Vec3(-v1.y, v1.x, 0).normalized()
            else:
                perp = Vec3(0, -v1.z, v1.y).normalized()
            return cls.from_axis_angle(perp, math.pi)
        
        # General case
        cross = v1.cross(v2)
        s = math.sqrt((1 + dot) * 2)
        inv_s = 1.0 / s
        
        return cls(
            s * 0.5,
            cross.x * inv_s,
            cross.y * inv_s,
            cross.z * inv_s
        ).normalized()
    
    @classmethod
    def slerp(cls, q1: 'Quat', q2: 'Quat', t: float) -> 'Quat':
        """
        Spherical linear interpolation between two quaternions.
        
        Args:
            q1: Start quaternion
            q2: End quaternion
            t: Interpolation parameter (0 to 1)
        
        Returns:
            Interpolated quaternion
        """
        t = max(0.0, min(1.0, t))
        
        # Dot product
        dot = q1.w * q2.w + q1.x * q2.x + q1.y * q2.y + q1.z * q2.z
        
        # If negative dot, negate one quaternion to take shorter path
        if dot < 0:
            q2 = Quat(-q2.w, -q2.x, -q2.y, -q2.z)
            dot = -dot
        
        # If quaternions are close, use linear interpolation
        if dot > 0.9995:
            result = Quat(
                q1.w + t * (q2.w - q1.w),
                q1.x + t * (q2.x - q1.x),
                q1.y + t * (q2.y - q1.y),
                q1.z + t * (q2.z - q1.z)
            )
            return result.normalized()
        
        # SLERP formula
        theta_0 = math.acos(min(1.0, dot))
        theta = theta_0 * t
        sin_theta = math.sin(theta)
        sin_theta_0 = math.sin(theta_0)
        
        s0 = math.cos(theta) - dot * sin_theta / sin_theta_0
        s1 = sin_theta / sin_theta_0
        
        return Quat(
            s0 * q1.w + s1 * q2.w,
            s0 * q1.x + s1 * q2.x,
            s0 * q1.y + s1 * q2.y,
            s0 * q1.z + s1 * q2.z
        ).normalized()
    
        @classmethod
        def from_matrix(cls, mat: 'Mat4') -> 'Quat':
            """
            Create quaternion from a rotation matrix.
            
            Uses Shepperd's method for numerical stability.
            
            Args:
                mat: 4x4 transformation matrix (column-major)
            
            Returns:
                Quaternion representing the rotation part of the matrix
            """
            m = mat.m
            
            # Extract the 3x3 rotation part
            trace = m[0] + m[5] + m[10]
            
            if trace > 0:
                s = math.sqrt(trace + 1.0) * 2  # s = 4 * w
                w = 0.25 * s
                x = (m[6] - m[9]) / s
                y = (m[8] - m[2]) / s
                z = (m[1] - m[4]) / s
            elif m[0] > m[5] and m[0] > m[10]:
                s = math.sqrt(1.0 + m[0] - m[5] - m[10]) * 2  # s = 4 * x
                w = (m[6] - m[9]) / s
                x = 0.25 * s
                y = (m[1] + m[4]) / s
                z = (m[8] + m[2]) / s
            elif m[5] > m[10]:
                s = math.sqrt(1.0 + m[5] - m[0] - m[10]) * 2  # s = 4 * y
                w = (m[8] - m[2]) / s
                x = (m[1] + m[4]) / s
                y = 0.25 * s
                z = (m[6] + m[9]) / s
            else:
                s = math.sqrt(1.0 + m[10] - m[0] - m[5]) * 2  # s = 4 * z
                w = (m[1] - m[4]) / s
                x = (m[8] + m[2]) / s
                y = (m[6] + m[9]) / s
                z = 0.25 * s
            
            return cls(w, x, y, z).normalized()

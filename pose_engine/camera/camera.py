"""
Camera - 3D Viewport Camera
===========================

Camera for viewing the 3D scene with two modes:
- Orbit mode (default): Camera orbits around a target point
- Head-look mode: First-person camera where you look around from a position

Features smooth FOV transitions to prevent jarring perception changes.
"""

import math
from typing import Tuple

from ..vec3 import Vec3
from ..mat4 import Mat4


class Camera:
    """Camera for viewing the 3D scene.

    Supports two modes:
    - Orbit mode (default): Camera orbits around a target point
    - Head-look mode: First-person camera where you look around from a position

    Features smooth FOV transitions to prevent jarring perception changes.
    """

    # FOV transition speed in degrees per second
    FOV_TRANSITION_SPEED = 60.0
    FOV_MIN = 30.0
    FOV_MAX = 120.0

    def __init__(self):
        """Create a new camera (defaults to orbit mode)."""
        # Orbit mode properties
        self.target = Vec3(0, 1, 0)  # Look at center
        self.distance = 3.0
        self.yaw = 0.0  # Horizontal rotation
        self.pitch = 0.0  # Vertical rotation

        # Head-look mode properties
        self._head_look_mode = False
        self._head_position = Vec3(0, 1.5, 3)  # Camera position in head-look mode
        self._head_yaw = 0.0  # Horizontal look direction
        self._head_pitch = 0.0  # Vertical look direction

        # Near/far planes
        self.near = 0.1
        self.far = 100.0

        # Smooth FOV transition
        self._fov_target: float = 45.0  # Target FOV (what user set)
        self._fov_current: float = 45.0  # Current animated FOV

    @property
    def fov(self) -> float:
        """Get the target FOV (not the current animated value)."""
        return self._fov_target

    @fov.setter
    def fov(self, value: float):
        """Set target FOV (will animate to this value)."""
        self._fov_target = max(self.FOV_MIN, min(self.FOV_MAX, value))

    @property
    def head_look_mode(self) -> bool:
        """Get head-look mode state."""
        return self._head_look_mode

    @head_look_mode.setter
    def head_look_mode(self, enabled: bool):
        """Set head-look mode.

        When switching modes, this preserves the current view as much as possible.
        """
        if enabled == self._head_look_mode:
            return

        if enabled:
            # Switching to head-look mode
            # Set head position to current camera position
            self._head_position = self.get_position()
            # In orbit mode, camera looks toward target, so calculate the look direction
            # The camera is at position, looking at target
            # We need to compute yaw and pitch that points from position toward target
            pos = self.get_position()
            direction = (self.target - pos).normalized()
            # Calculate yaw (horizontal angle) and pitch (vertical angle)
            # yaw = atan2(x, z) - angle in XZ plane
            self._head_yaw = math.atan2(direction.x, direction.z)
            # pitch = asin(y) - angle from horizontal
            self._head_pitch = math.asin(max(-1, min(1, direction.y)))
        else:
            # Switching to orbit mode
            # Calculate a reasonable target and distance from head-look position
            forward = self._get_head_forward()
            # Place target 3 units in front of camera
            self.target = self._head_position + forward * 3.0
            self.distance = 3.0
            # Calculate orbit yaw/pitch from the look direction
            # The orbit camera position is: target + distance * (sin(yaw)*cos(pitch), sin(pitch), cos(yaw)*cos(pitch))
            # We need to find yaw/pitch such that the camera looks toward the target
            # Since we're looking toward -forward direction from target, we need:
            # The camera should be at _head_position, looking at target
            # So we need: _head_position = target + distance * offset
            # offset = (_head_position - target) / distance
            offset = (self._head_position - self.target) / self.distance
            # offset = (sin(yaw)*cos(pitch), sin(pitch), cos(yaw)*cos(pitch))
            # yaw = atan2(offset.x, offset.z)
            # pitch = asin(offset.y)
            self.yaw = math.atan2(offset.x, offset.z)
            self.pitch = math.asin(max(-1, min(1, offset.y)))

        self._head_look_mode = enabled

    def _get_head_forward(self) -> Vec3:
        """Get forward direction in head-look mode."""
        x = math.sin(self._head_yaw) * math.cos(self._head_pitch)
        y = math.sin(self._head_pitch)
        z = math.cos(self._head_yaw) * math.cos(self._head_pitch)
        return Vec3(x, y, z)

    def _get_head_right(self) -> Vec3:
        """Get right direction in head-look mode."""
        forward = self._get_head_forward()
        # Right is always perpendicular to forward and world up
        return Vec3(0, 1, 0).cross(forward).normalized()

    def _get_head_up(self) -> Vec3:
        """Get up direction in head-look mode."""
        forward = self._get_head_forward()
        right = self._get_head_right()
        return forward.cross(right).normalized()

    def update(self, delta_time: float) -> bool:
        """Update animated values. Call from update timer.

        Args:
            delta_time: Time elapsed since last update in seconds

        Returns:
            True if any animation is in progress, False if all animations complete
        """
        animating = False

        # Smooth FOV transition
        if abs(self._fov_current - self._fov_target) > 0.1:
            animating = True
            direction = 1 if self._fov_target > self._fov_current else -1
            self._fov_current += direction * self.FOV_TRANSITION_SPEED * delta_time
            # Clamp to target
            if direction > 0:
                self._fov_current = min(self._fov_current, self._fov_target)
            else:
                self._fov_current = max(self._fov_current, self._fov_target)
        else:
            self._fov_current = self._fov_target

        return animating

    def get_position(self) -> Vec3:
        """Get camera position in world space."""
        if self._head_look_mode:
            return self._head_position
        else:
            x = self.distance * math.sin(self.yaw) * math.cos(self.pitch)
            y = self.distance * math.sin(self.pitch)
            z = self.distance * math.cos(self.yaw) * math.cos(self.pitch)
            return self.target + Vec3(x, y, z)

    def get_view_matrix(self) -> Mat4:
        """Get the view matrix."""
        if self._head_look_mode:
            # First-person view matrix
            pos = self._head_position
            forward = self._get_head_forward()
            right = self._get_head_right()
            up = self._get_head_up()

            # Column-major look-at matrix
            return Mat4([
                right.x, up.x, -forward.x, 0,
                right.y, up.y, -forward.y, 0,
                right.z, up.z, -forward.z, 0,
                -right.dot(pos), -up.dot(pos), forward.dot(pos), 1
            ])
        else:
            # Orbit view matrix
            pos = self.get_position()

            # Look-at matrix
            forward = (self.target - pos).normalized()
            right = Vec3(0, 1, 0).cross(forward).normalized()
            up = forward.cross(right).normalized()

            # Column-major look-at matrix
            return Mat4([
                right.x, up.x, -forward.x, 0,
                right.y, up.y, -forward.y, 0,
                right.z, up.z, -forward.z, 0,
                -right.dot(pos), -up.dot(pos), forward.dot(pos), 1
            ])

    def get_projection_matrix(self, aspect: float) -> Mat4:
        """Get the projection matrix using current animated FOV."""
        fov_rad = math.radians(self._fov_current)
        f = 1.0 / math.tan(fov_rad * 0.5)

        return Mat4([
            f / aspect, 0, 0, 0,
            0, f, 0, 0,
            0, 0, (self.far + self.near) / (self.near - self.far), -1,
            0, 0, (2 * self.far * self.near) / (self.near - self.far), 0
        ])

    def rotate(self, delta_yaw: float, delta_pitch: float) -> None:
        """Rotate the camera."""
        if self._head_look_mode:
            # In head-look mode, rotate the look direction
            # Yaw is standard (left/right)
            self._head_yaw += delta_yaw
            # Pitch is inverted because positive pitch should look down in first-person
            self._head_pitch = max(-math.pi * 0.49, min(math.pi * 0.49, self._head_pitch - delta_pitch))
        else:
            # In orbit mode, rotate around the target
            self.yaw += delta_yaw
            self.pitch = max(-math.pi * 0.49, min(math.pi * 0.49, self.pitch + delta_pitch))

    def zoom(self, delta: float) -> None:
        """Zoom the camera."""
        if self._head_look_mode:
            # In head-look mode, zoom by adjusting FOV
            self.fov = max(self.FOV_MIN, min(self.FOV_MAX, self.fov + delta * 30))
        else:
            # In orbit mode, zoom by changing distance
            self.distance = max(0.5, min(50.0, self.distance * (1.0 - delta)))

    def move_forward(self, delta: float) -> None:
        """Move the camera forward/backward."""
        if self._head_look_mode:
            # In head-look mode, move along the look direction
            forward = self._get_head_forward()
            self._head_position = self._head_position + forward * delta
        else:
            # In orbit mode, move toward/away from target
            self.distance = max(0.5, min(50.0, self.distance - delta))

    def move_target(self, delta: Vec3) -> None:
        """Move the camera target by a world-space delta."""
        if self._head_look_mode:
            # In head-look mode, move the head position
            self._head_position = self._head_position + delta
        else:
            # In orbit mode, move the target
            self.target = self.target + delta

    def pan(self, delta_x: float, delta_y: float) -> None:
        """Pan the camera."""
        if self._head_look_mode:
            # In head-look mode, strafe left/right and up/down
            right = self._get_head_right()
            up = self._get_head_up()
            scale = 0.01  # Movement speed
            self._head_position = self._head_position + right * (-delta_x * scale) + up * (delta_y * scale)
        else:
            # In orbit mode, pan the target
            forward = (self.target - self.get_position()).normalized()
            right = Vec3(0, 1, 0).cross(forward).normalized()
            up = forward.cross(right).normalized()

            scale = self.distance * 0.002
            self.target = self.target + right * (-delta_x * scale) + up * (delta_y * scale)

    def frame_points(self, min_pt: Vec3, max_pt: Vec3) -> None:
        """Frame the camera to see the given bounding box."""
        center = Vec3(
            (min_pt.x + max_pt.x) / 2,
            (min_pt.y + max_pt.y) / 2,
            (min_pt.z + max_pt.z) / 2
        )

        # Calculate required distance
        size = Vec3(
            max_pt.x - min_pt.x,
            max_pt.y - min_pt.y,
            max_pt.z - min_pt.z
        )
        max_dim = max(size.x, size.y, size.z)

        if self._head_look_mode:
            # In head-look mode, position camera to see the bounding box
            # Place camera at a distance that can see the whole box
            self._head_position = center + Vec3(0, 0, max_dim * 2.0)
            self._head_yaw = math.pi  # Look back at center
            self._head_pitch = 0.0
        else:
            # In orbit mode, set target and distance
            self.target = center
            self.distance = max_dim * 2.0

    def get_forward(self) -> Vec3:
        """Get the forward direction of the camera."""
        if self._head_look_mode:
            return self._get_head_forward()
        else:
            return (self.target - self.get_position()).normalized()

    def get_right(self) -> Vec3:
        """Get the right direction of the camera."""
        if self._head_look_mode:
            return self._get_head_right()
        else:
            forward = self.get_forward()
            return Vec3(0, 1, 0).cross(forward).normalized()

    def get_up(self) -> Vec3:
        """Get the up direction of the camera."""
        if self._head_look_mode:
            return self._get_head_up()
        else:
            forward = self.get_forward()
            right = self.get_right()
            return forward.cross(right).normalized()

    def save_state(self) -> dict:
        """Save camera state to a dictionary.

        Returns:
            Dictionary containing all camera state for serialization.
        """
        return {
            'mode': 'head_look' if self._head_look_mode else 'orbit',
            'target': self.target.to_tuple(),
            'distance': self.distance,
            'yaw': self.yaw,
            'pitch': self.pitch,
            'head_position': self._head_position.to_tuple(),
            'head_yaw': self._head_yaw,
            'head_pitch': self._head_pitch,
            'fov': self._fov_target,
            'near': self.near,
            'far': self.far,
        }

    def load_state(self, state: dict) -> None:
        """Load camera state from a dictionary.

        Args:
            state: Dictionary containing camera state from save_state().
        """
        self.target = Vec3.from_tuple(state.get('target', (0, 1, 0)))
        self.distance = state.get('distance', 3.0)
        self.yaw = state.get('yaw', 0.0)
        self.pitch = state.get('pitch', 0.0)
        self._head_position = Vec3.from_tuple(state.get('head_position', (0, 1.5, 3)))
        self._head_yaw = state.get('head_yaw', 0.0)
        self._head_pitch = state.get('head_pitch', 0.0)
        self._fov_target = state.get('fov', 45.0)
        self._fov_current = self._fov_target
        self.near = state.get('near', 0.1)
        self.far = state.get('far', 100.0)
        self._head_look_mode = state.get('mode', 'orbit') == 'head_look'

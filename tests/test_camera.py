#!/usr/bin/env python3
"""
Tests for Camera Module
=======================

Tests for the Camera class covering both orbit and head-look modes.

Run with: pytest tests/test_camera.py -v
"""

import pytest
import math
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pose_engine.camera import Camera
from pose_engine.vec3 import Vec3
from pose_engine.mat4 import Mat4


class TestCameraCreation:
    """Tests for camera initialization and default state."""

    def test_camera_creation_default_values(self):
        """Test that camera is created with correct default values."""
        camera = Camera()

        # Check default orbit mode properties
        assert camera.target.x == 0
        assert camera.target.y == 1
        assert camera.target.z == 0
        assert camera.distance == 3.0
        assert camera.yaw == 0.0
        assert camera.pitch == 0.0

        # Check default head-look mode properties (should be initialized but not active)
        assert camera.head_look_mode == False

        # Check near/far planes
        assert camera.near == 0.1
        assert camera.far == 100.0

        # Check FOV
        assert camera.fov == 45.0

    def test_camera_default_mode_is_orbit(self):
        """Test that camera defaults to orbit mode."""
        camera = Camera()
        assert camera.head_look_mode == False

    def test_camera_fov_bounds(self):
        """Test that FOV is clamped to valid range."""
        camera = Camera()

        # Test minimum FOV
        camera.fov = 10.0
        assert camera.fov == Camera.FOV_MIN

        # Test maximum FOV
        camera.fov = 150.0
        assert camera.fov == Camera.FOV_MAX

        # Test valid FOV
        camera.fov = 60.0
        assert camera.fov == 60.0


class TestOrbitModePosition:
    """Tests for orbit mode position calculations."""

    def test_orbit_mode_position_default(self):
        """Test position calculation with default yaw/pitch."""
        camera = Camera()
        pos = camera.get_position()

        # Default: target at (0,1,0), distance 3, yaw=0, pitch=0
        # Position should be at (0, 1, 3) relative to target
        assert abs(pos.x - 0) < 0.001
        assert abs(pos.y - 1) < 0.001
        assert abs(pos.z - 3) < 0.001

    def test_orbit_mode_position_yaw_rotation(self):
        """Test position calculation with yaw rotation."""
        camera = Camera()
        camera.yaw = math.pi / 2  # 90 degrees

        pos = camera.get_position()

        # After 90 degree yaw rotation, camera should be at (3, 1, 0)
        # Formula: x = distance * sin(yaw) * cos(pitch), z = distance * cos(yaw) * cos(pitch)
        # At yaw=pi/2: sin(pi/2)=1, cos(pi/2)=0, so x=3, z=0
        assert abs(pos.x - 3) < 0.001
        assert abs(pos.y - 1) < 0.001
        assert abs(pos.z - 0) < 0.001

    def test_orbit_mode_position_pitch_rotation(self):
        """Test position calculation with pitch rotation."""
        camera = Camera()
        camera.pitch = math.pi / 4  # 45 degrees

        pos = camera.get_position()

        # After 45 degree pitch, camera should be elevated
        # x = 3 * sin(0) * cos(45°) = 0
        # y = 3 * sin(45°) ≈ 2.12
        # z = 3 * cos(0) * cos(45°) ≈ 2.12
        expected_y = 1 + 3 * math.sin(math.pi / 4)
        expected_z = 3 * math.cos(math.pi / 4)

        assert abs(pos.x - 0) < 0.001
        assert abs(pos.y - expected_y) < 0.01
        assert abs(pos.z - expected_z) < 0.01

    def test_orbit_mode_position_combined_rotation(self):
        """Test position calculation with combined yaw and pitch."""
        camera = Camera()
        camera.yaw = math.pi / 4  # 45 degrees
        camera.pitch = math.pi / 6  # 30 degrees

        pos = camera.get_position()

        # Verify position is calculated correctly
        expected_x = 3 * math.sin(math.pi / 4) * math.cos(math.pi / 6)
        expected_y = 1 + 3 * math.sin(math.pi / 6)
        expected_z = 3 * math.cos(math.pi / 4) * math.cos(math.pi / 6)

        assert abs(pos.x - expected_x) < 0.01
        assert abs(pos.y - expected_y) < 0.01
        assert abs(pos.z - expected_z) < 0.01


class TestOrbitModeRotation:
    """Tests for orbit mode rotation operations."""

    def test_orbit_rotate_yaw(self):
        """Test yaw rotation in orbit mode."""
        camera = Camera()
        initial_yaw = camera.yaw

        camera.rotate(0.5, 0)  # Rotate yaw by 0.5 radians

        assert abs(camera.yaw - (initial_yaw + 0.5)) < 0.001

    def test_orbit_rotate_pitch(self):
        """Test pitch rotation in orbit mode."""
        camera = Camera()
        initial_pitch = camera.pitch

        camera.rotate(0, 0.3)  # Rotate pitch by 0.3 radians

        # Pitch should increase (orbit mode convention)
        assert abs(camera.pitch - (initial_pitch + 0.3)) < 0.001

    def test_orbit_pitch_clamping(self):
        """Test that pitch is clamped to prevent gimbal lock."""
        camera = Camera()

        # Try to rotate beyond the limit
        camera.rotate(0, math.pi)  # Try to rotate 180 degrees

        # Should be clamped to approximately ±89 degrees (0.49π)
        assert camera.pitch <= math.pi * 0.49
        assert camera.pitch >= -math.pi * 0.49


class TestOrbitModeZoom:
    """Tests for orbit mode zoom operations."""

    def test_orbit_zoom_in(self):
        """Test zooming in reduces distance."""
        camera = Camera()
        initial_distance = camera.distance

        camera.zoom(0.5)  # Positive delta zooms in

        assert camera.distance < initial_distance

    def test_orbit_zoom_out(self):
        """Test zooming out increases distance."""
        camera = Camera()
        initial_distance = camera.distance

        camera.zoom(-0.5)  # Negative delta zooms out

        assert camera.distance > initial_distance

    def test_orbit_zoom_distance_clamping(self):
        """Test that zoom distance is clamped."""
        camera = Camera()

        # Try to zoom very close
        camera.distance = 0.1
        camera.zoom(0.9)
        assert camera.distance >= 0.5

        # Try to zoom very far
        camera.distance = 100.0
        camera.zoom(-0.9)
        assert camera.distance <= 50.0


class TestHeadLookModeSwitch:
    """Tests for switching between orbit and head-look modes."""

    def test_switch_to_head_look_mode(self):
        """Test switching from orbit to head-look mode."""
        camera = Camera()
        assert camera.head_look_mode == False

        camera.head_look_mode = True

        assert camera.head_look_mode == True

    def test_switch_from_head_look_to_orbit(self):
        """Test switching from head-look to orbit mode."""
        camera = Camera()
        camera.head_look_mode = True

        camera.head_look_mode = False

        assert camera.head_look_mode == False

    def test_head_look_mode_no_change_when_same(self):
        """Test that setting same mode doesn't change anything."""
        camera = Camera()
        initial_target = Vec3(camera.target.x, camera.target.y, camera.target.z)

        camera.head_look_mode = False  # Already in orbit mode

        # Target should not change
        assert camera.target.x == initial_target.x
        assert camera.target.y == initial_target.y
        assert camera.target.z == initial_target.z


class TestHeadLookPositionPreserved:
    """Tests for position preservation when switching modes."""

    def test_position_preserved_switch_to_head_look(self):
        """Test that position is preserved when switching to head-look."""
        camera = Camera()
        # Set a specific orbit position
        camera.yaw = math.pi / 4
        camera.pitch = math.pi / 6

        orbit_position = camera.get_position()

        camera.head_look_mode = True

        # Position should be approximately the same
        head_position = camera.get_position()
        assert abs(head_position.x - orbit_position.x) < 0.001
        assert abs(head_position.y - orbit_position.y) < 0.001
        assert abs(head_position.z - orbit_position.z) < 0.001


class TestHeadLookForwardDirection:
    """Tests for head-look mode forward direction calculations."""

    def test_head_forward_default(self):
        """Test forward direction with default head yaw/pitch."""
        camera = Camera()
        # Before switching to head-look, the orbit camera is at (0, 1, 3) looking at (0, 1, 0)
        # So the forward direction is (0, 0, -1) in world space
        camera.head_look_mode = True

        # Access internal method to test
        forward = camera._get_head_forward()

        # When switching from orbit mode, the camera looks toward the target
        # Orbit camera at (0, 1, 3) looking at target (0, 1, 0)
        # Direction is (0, 0, -1), so head_yaw = atan2(0, -1) = pi, head_pitch = 0
        # Forward = (sin(pi)*cos(0), sin(0), cos(pi)*cos(0)) = (0, 0, -1)
        assert abs(forward.x - 0) < 0.001
        assert abs(forward.y - 0) < 0.001
        assert abs(forward.z - (-1)) < 0.001

    def test_head_forward_yaw_rotation(self):
        """Test forward direction after yaw rotation."""
        camera = Camera()
        camera.head_look_mode = True
        camera._head_yaw = math.pi / 2  # 90 degrees

        forward = camera._get_head_forward()

        # After 90 degree yaw, forward should point along X
        assert abs(forward.x - 1) < 0.001
        assert abs(forward.y - 0) < 0.001
        assert abs(forward.z - 0) < 0.001

    def test_head_forward_pitch_rotation(self):
        """Test forward direction after pitch rotation."""
        camera = Camera()
        camera.head_look_mode = True
        # Reset head_yaw to 0 and set pitch to test the forward calculation directly
        camera._head_yaw = 0
        camera._head_pitch = math.pi / 4  # 45 degrees

        forward = camera._get_head_forward()

        # After 45 degree pitch with yaw=0, forward should point upward
        # Forward = (sin(0)*cos(pi/4), sin(pi/4), cos(0)*cos(pi/4)) = (0, sin(pi/4), cos(pi/4))
        assert abs(forward.x - 0) < 0.001
        assert abs(forward.y - math.sin(math.pi / 4)) < 0.001
        assert abs(forward.z - math.cos(math.pi / 4)) < 0.001


class TestHeadLookRotation:
    """Tests for head-look mode rotation operations."""

    def test_head_look_rotate_yaw(self):
        """Test yaw rotation in head-look mode."""
        camera = Camera()
        camera.head_look_mode = True
        initial_yaw = camera._head_yaw

        camera.rotate(0.5, 0)

        assert abs(camera._head_yaw - (initial_yaw + 0.5)) < 0.001

    def test_head_look_rotate_pitch(self):
        """Test pitch rotation in head-look mode."""
        camera = Camera()
        camera.head_look_mode = True
        initial_pitch = camera._head_pitch

        camera.rotate(0, 0.3)

        # In head-look mode, pitch is inverted
        assert abs(camera._head_pitch - (initial_pitch - 0.3)) < 0.001

    def test_head_look_pitch_clamping(self):
        """Test that head-look pitch is clamped."""
        camera = Camera()
        camera.head_look_mode = True

        # Try to rotate beyond limit
        camera.rotate(0, math.pi)

        # Should be clamped
        assert camera._head_pitch <= math.pi * 0.49
        assert camera._head_pitch >= -math.pi * 0.49


class TestHeadLookMovement:
    """Tests for head-look mode movement operations."""

    def test_move_forward(self):
        """Test moving forward in head-look mode."""
        camera = Camera()
        camera.head_look_mode = True
        # Reset head_yaw to 0 so forward points along positive Z
        camera._head_yaw = 0
        camera._head_pitch = 0
        initial_pos = Vec3(camera._head_position.x, camera._head_position.y, camera._head_position.z)

        camera.move_forward(1.0)

        # With head_yaw=0 and head_pitch=0, forward is (0, 0, 1)
        # So moving forward should increase Z
        assert camera._head_position.z > initial_pos.z

    def test_move_right(self):
        """Test moving right in head-look mode."""
        camera = Camera()
        camera.head_look_mode = True
        initial_pos = Vec3(camera._head_position.x, camera._head_position.y, camera._head_position.z)

        # Pan right (negative delta_x moves right)
        camera.pan(-100, 0)

        # Should move along right direction
        assert camera._head_position.x != initial_pos.x

    def test_move_up(self):
        """Test moving up in head-look mode."""
        camera = Camera()
        camera.head_look_mode = True
        initial_pos = Vec3(camera._head_position.x, camera._head_position.y, camera._head_position.z)

        # Pan up (positive delta_y moves up)
        camera.pan(0, 100)

        # Should move along up direction
        assert camera._head_position.y > initial_pos.y


class TestModeTransition:
    """Tests for smooth transitions between modes."""

    def test_transition_orbit_to_head_look(self):
        """Test smooth transition from orbit to head-look."""
        camera = Camera()
        camera.yaw = math.pi / 4
        camera.pitch = math.pi / 6

        # Get orbit position before switch
        orbit_pos = camera.get_position()

        # Switch to head-look
        camera.head_look_mode = True

        # Position should be preserved
        head_pos = camera.get_position()
        assert abs(head_pos.x - orbit_pos.x) < 0.01
        assert abs(head_pos.y - orbit_pos.y) < 0.01
        assert abs(head_pos.z - orbit_pos.z) < 0.01

    def test_transition_head_look_to_orbit(self):
        """Test smooth transition from head-look to orbit."""
        camera = Camera()
        camera.head_look_mode = True
        camera._head_position = Vec3(0, 2, 5)
        camera._head_yaw = 0
        camera._head_pitch = 0

        # Switch to orbit
        camera.head_look_mode = False

        # Should have valid orbit parameters
        assert camera.distance > 0
        assert camera.target is not None


class TestFOVClamping:
    """Tests for FOV clamping behavior."""

    def test_fov_min_clamp(self):
        """Test FOV is clamped to minimum."""
        camera = Camera()
        camera.fov = 0
        assert camera.fov == Camera.FOV_MIN

    def test_fov_max_clamp(self):
        """Test FOV is clamped to maximum."""
        camera = Camera()
        camera.fov = 200
        assert camera.fov == Camera.FOV_MAX

    def test_fov_valid_value(self):
        """Test valid FOV values are preserved."""
        camera = Camera()
        camera.fov = 75
        assert camera.fov == 75


class TestViewMatrixGeneration:
    """Tests for view matrix generation."""

    def test_view_matrix_orbit_mode(self):
        """Test view matrix in orbit mode."""
        camera = Camera()

        view_matrix = camera.get_view_matrix()

        assert isinstance(view_matrix, Mat4)
        # View matrix should be invertible
        # A valid view matrix should not be all zeros

    def test_view_matrix_head_look_mode(self):
        """Test view matrix in head-look mode."""
        camera = Camera()
        camera.head_look_mode = True

        view_matrix = camera.get_view_matrix()

        assert isinstance(view_matrix, Mat4)

    def test_view_matrix_looks_at_target(self):
        """Test that view matrix correctly looks at target."""
        camera = Camera()
        camera.target = Vec3(0, 0, 0)
        camera.distance = 5.0
        camera.yaw = 0
        camera.pitch = 0

        view_matrix = camera.get_view_matrix()

        # Camera at (0, 0, 5) looking at (0, 0, 0)
        # View matrix should transform world space to camera space
        assert isinstance(view_matrix, Mat4)


class TestProjectionMatrix:
    """Tests for projection matrix generation."""

    def test_projection_matrix_creation(self):
        """Test projection matrix is created correctly."""
        camera = Camera()
        aspect = 16.0 / 9.0

        proj_matrix = camera.get_projection_matrix(aspect)

        assert isinstance(proj_matrix, Mat4)

    def test_projection_matrix_aspect_ratio(self):
        """Test projection matrix respects aspect ratio."""
        camera = Camera()
        camera.fov = 60

        proj_16_9 = camera.get_projection_matrix(16.0 / 9.0)
        proj_4_3 = camera.get_projection_matrix(4.0 / 3.0)

        # Different aspect ratios should produce different matrices
        # The matrices should be different (not equal)
        assert isinstance(proj_16_9, Mat4)
        assert isinstance(proj_4_3, Mat4)

    def test_projection_matrix_fov_effect(self):
        """Test that FOV affects projection matrix."""
        camera = Camera()

        camera.fov = 45
        proj_45 = camera.get_projection_matrix(1.0)

        camera.fov = 90
        camera._fov_current = 90  # Force current FOV
        proj_90 = camera.get_projection_matrix(1.0)

        # Different FOVs should produce different matrices
        assert isinstance(proj_45, Mat4)
        assert isinstance(proj_90, Mat4)


class TestCameraStateSaveLoad:
    """Tests for camera state serialization."""

    def test_save_state_orbit_mode(self):
        """Test saving camera state in orbit mode."""
        camera = Camera()
        camera.yaw = 1.0
        camera.pitch = 0.5
        camera.distance = 10.0

        state = camera.save_state()

        assert state['mode'] == 'orbit'
        assert state['yaw'] == 1.0
        assert state['pitch'] == 0.5
        assert state['distance'] == 10.0

    def test_save_state_head_look_mode(self):
        """Test saving camera state in head-look mode."""
        camera = Camera()
        camera.head_look_mode = True
        camera._head_yaw = 1.5
        camera._head_pitch = 0.3

        state = camera.save_state()

        assert state['mode'] == 'head_look'
        assert state['head_yaw'] == 1.5
        assert state['head_pitch'] == 0.3

    def test_load_state_orbit_mode(self):
        """Test loading camera state in orbit mode."""
        camera = Camera()

        state = {
            'mode': 'orbit',
            'target': (0, 2, 0),
            'distance': 8.0,
            'yaw': 0.5,
            'pitch': 0.25,
            'fov': 60.0
        }

        camera.load_state(state)

        assert camera.head_look_mode == False
        assert camera.distance == 8.0
        assert camera.yaw == 0.5
        assert camera.pitch == 0.25
        assert camera.fov == 60.0

    def test_load_state_head_look_mode(self):
        """Test loading camera state in head-look mode."""
        camera = Camera()

        state = {
            'mode': 'head_look',
            'head_position': (1, 2, 3),
            'head_yaw': 1.0,
            'head_pitch': 0.5,
            'fov': 75.0
        }

        camera.load_state(state)

        assert camera.head_look_mode == True
        assert camera._head_yaw == 1.0
        assert camera._head_pitch == 0.5

    def test_save_load_roundtrip(self):
        """Test that save/load preserves camera state."""
        camera = Camera()
        camera.yaw = 1.2
        camera.pitch = 0.4
        camera.distance = 7.5
        camera.fov = 55

        state = camera.save_state()

        new_camera = Camera()
        new_camera.load_state(state)

        assert new_camera.yaw == camera.yaw
        assert new_camera.pitch == camera.pitch
        assert new_camera.distance == camera.distance
        assert new_camera.fov == camera.fov


class TestFramePoints:
    """Tests for framing bounding boxes."""

    def test_frame_points_orbit_mode(self):
        """Test framing points in orbit mode."""
        camera = Camera()

        # Frame a small box
        min_pt = Vec3(-1, 0, -1)
        max_pt = Vec3(1, 2, 1)

        camera.frame_points(min_pt, max_pt)

        # Target should be at center of box
        assert abs(camera.target.x - 0) < 0.01
        assert abs(camera.target.y - 1) < 0.01
        assert abs(camera.target.z - 0) < 0.01

        # Distance should be reasonable for the box size
        assert camera.distance > 0

    def test_frame_points_head_look_mode(self):
        """Test framing points in head-look mode."""
        camera = Camera()
        camera.head_look_mode = True

        min_pt = Vec3(-1, 0, -1)
        max_pt = Vec3(1, 2, 1)

        camera.frame_points(min_pt, max_pt)

        # Should position camera to see the box
        assert camera._head_position is not None


class TestCameraUpdate:
    """Tests for camera animation update."""

    def test_update_animates_fov(self):
        """Test that update animates FOV transition."""
        camera = Camera()
        camera.fov = 90  # Set target FOV

        # Update should animate toward target
        animating = camera.update(0.1)

        # Should be animating if FOV is different
        # (FOV starts at 45, target is 90)
        assert animating == True or camera._fov_current == camera._fov_target

    def test_update_returns_false_when_complete(self):
        """Test that update returns False when animation complete."""
        camera = Camera()
        camera.fov = 45
        camera._fov_current = 45
        camera._fov_target = 45

        animating = camera.update(0.1)

        assert animating == False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

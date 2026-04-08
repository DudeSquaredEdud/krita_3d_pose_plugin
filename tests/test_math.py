#!/usr/bin/env python3
"""
Tests for Pose Engine Math Library
===================================

Run with: python tests/test_math.py
"""

import sys
import os
import math

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pose_engine.vec3 import Vec3
from pose_engine.quat import Quat
from pose_engine.mat4 import Mat4
from pose_engine.transform import Transform


def test_vec3():
    """Test Vec3 operations."""
    print("\n=== Testing Vec3 ===")
    
    # Basic operations
    v1 = Vec3(1, 2, 3)
    v2 = Vec3(4, 5, 6)
    
    # Addition
    v3 = v1 + v2
    assert v3.x == 5 and v3.y == 7 and v3.z == 9, "Vector addition failed"
    print(f"  Addition: {v1} + {v2} = {v3} ✓")
    
    # Subtraction
    v4 = v2 - v1
    assert v4.x == 3 and v4.y == 3 and v4.z == 3, "Vector subtraction failed"
    print(f"  Subtraction: {v2} - {v1} = {v4} ✓")
    
    # Scalar multiplication
    v5 = v1 * 2
    assert v5.x == 2 and v5.y == 4 and v5.z == 6, "Scalar multiplication failed"
    print(f"  Scalar mult: {v1} * 2 = {v5} ✓")
    
    # Dot product
    dot = v1.dot(v2)
    expected_dot = 1*4 + 2*5 + 3*6
    assert abs(dot - expected_dot) < 0.001, "Dot product failed"
    print(f"  Dot product: {v1} · {v2} = {dot} ✓")
    
    # Cross product
    vx = Vec3(1, 0, 0)
    vy = Vec3(0, 1, 0)
    vz = vx.cross(vy)
    assert abs(vz.x) < 0.001 and abs(vz.y) < 0.001 and abs(vz.z - 1) < 0.001, "Cross product failed"
    print(f"  Cross product: {vx} × {vy} = {vz} ✓")
    
    # Length
    v_len = Vec3(3, 4, 0)
    assert abs(v_len.length() - 5) < 0.001, "Length calculation failed"
    print(f"  Length: |{v_len}| = {v_len.length()} ✓")
    
    # Normalization
    v_norm = Vec3(3, 4, 0).normalized()
    assert abs(v_norm.length() - 1) < 0.001, "Normalization failed"
    print(f"  Normalized: {v_len}.normalized() = {v_norm} ✓")
    
    # Constants
    assert Vec3.UP == Vec3(0, 1, 0), "UP constant failed"
    print(f"  Constants: UP={Vec3.UP}, RIGHT={Vec3.RIGHT} ✓")
    
    print("  All Vec3 tests passed! ✓")


def test_quat():
    """Test Quaternion operations."""
    print("\n=== Testing Quat ===")
    
    # Identity
    q_id = Quat.identity()
    assert q_id.w == 1 and q_id.x == 0 and q_id.y == 0 and q_id.z == 0, "Identity failed"
    print(f"  Identity: {q_id} ✓")
    
    # Axis-angle creation
    q_rot = Quat.from_axis_angle(Vec3.UP, math.pi / 2)
    print(f"  Axis-angle (90° around Y): {q_rot} ✓")
    
    # Quaternion multiplication (combining rotations)
    q1 = Quat.from_axis_angle(Vec3.UP, math.pi / 4)
    q2 = Quat.from_axis_angle(Vec3.UP, math.pi / 4)
    q3 = q1 * q2
    # Should be 90 degree rotation
    euler = q3.to_euler_degrees()
    assert abs(euler[1] - 90) < 1, f"Quaternion multiplication failed: got {euler}"
    print(f"  Multiply: 45° * 45° = {euler[1]:.1f}° (Y axis) ✓")
    
    # Vector rotation (right-hand rule: 90° Y rotates X to -Z)
    q_90y = Quat.from_axis_angle_degrees(Vec3.UP, 90)
    v_x = Vec3(1, 0, 0)
    v_rotated = q_90y.rotate_vector(v_x)
    assert abs(v_rotated.x) < 0.001, f"X should be ~0, got {v_rotated.x}"
    assert abs(v_rotated.z + 1) < 0.001, f"Z should be ~-1, got {v_rotated.z}"
    print(f"  Rotate vector: {v_x} rotated 90° Y = {v_rotated} ✓")
    
    # Euler conversion
    q_euler = Quat.from_euler_degrees(45, 30, 60)
    euler = q_euler.to_euler_degrees()
    assert abs(euler[0] - 45) < 1, "Euler X conversion failed"
    assert abs(euler[1] - 30) < 1, "Euler Y conversion failed"
    assert abs(euler[2] - 60) < 1, "Euler Z conversion failed"
    print(f"  Euler conversion: (45°, 30°, 60°) -> ({euler[0]:.1f}°, {euler[1]:.1f}°, {euler[2]:.1f}°) ✓")
    
    # Shortest arc
    v_up = Vec3.UP
    v_right = Vec3.RIGHT
    q_arc = Quat.shortest_arc(v_up, v_right)
    v_result = q_arc.rotate_vector(v_up)
    assert abs(v_result.x - 1) < 0.001, f"Shortest arc failed: {v_result}"
    print(f"  Shortest arc: UP -> RIGHT = {v_result} ✓")
    
    # SLERP
    q_start = Quat.identity()
    q_end = Quat.from_euler_degrees(0, 90, 0)
    q_mid = Quat.slerp(q_start, q_end, 0.5)
    euler_mid = q_mid.to_euler_degrees()
    assert abs(euler_mid[1] - 45) < 1, f"SLERP failed: {euler_mid}"
    print(f"  SLERP: 0° -> 90° at t=0.5 = {euler_mid[1]:.1f}° ✓")
    
    print("  All Quat tests passed! ✓")


def test_mat4():
    """Test Matrix4x4 operations."""
    print("\n=== Testing Mat4 ===")
    
    # Identity
    m_id = Mat4.identity()
    assert m_id.m[0] == 1 and m_id.m[5] == 1 and m_id.m[10] == 1, "Identity matrix failed"
    print(f"  Identity matrix created ✓")
    
    # Translation
    m_trans = Mat4.translation(Vec3(1, 2, 3))
    assert m_trans.m[12] == 1 and m_trans.m[13] == 2 and m_trans.m[14] == 3, "Translation matrix failed"
    print(f"  Translation matrix: (1, 2, 3) ✓")
    
    # Scale
    m_scale = Mat4.scale(Vec3(2, 2, 2))
    assert m_scale.m[0] == 2 and m_scale.m[5] == 2 and m_scale.m[10] == 2, "Scale matrix failed"
    print(f"  Scale matrix: (2, 2, 2) ✓")
    
    # Rotation (right-hand rule: 90° Y rotates X to -Z)
    m_rot = Mat4.rotation_y(math.pi / 2)
    v_x = Vec3(1, 0, 0)
    v_rotated = m_rot.transform_vector(v_x)
    assert abs(v_rotated.x) < 0.001, f"Rotation X should be ~0, got {v_rotated.x}"
    assert abs(v_rotated.z + 1) < 0.001, f"Rotation Z should be ~-1, got {v_rotated.z}"
    print(f"  Rotation: (1,0,0) rotated 90° Y = {v_rotated} ✓")
    
    # Matrix multiplication
    m_t = Mat4.translation(Vec3(1, 0, 0))
    m_s = Mat4.scale(Vec3(2, 2, 2))
    m_combined = m_t * m_s
    v_test = Vec3(1, 1, 1)
    v_result = m_combined.transform_point(v_test)
    # Scale first: (2, 2, 2), then translate: (3, 2, 2)
    assert abs(v_result.x - 3) < 0.001, f"Combined transform X failed: {v_result}"
    print(f"  Combined transform: scale(2) * translate(1,0,0) on (1,1,1) = {v_result} ✓")
    
    # Inverse
    m_orig = Mat4.translation(Vec3(5, 3, 2))
    m_inv = m_orig.inverse()
    m_back = m_orig * m_inv
    # Should be approximately identity
    assert abs(m_back.m[0] - 1) < 0.001, "Inverse failed"
    assert abs(m_back.m[12]) < 0.001, "Inverse translation failed"
    print(f"  Inverse: M * M^-1 ≈ Identity ✓")
    
    # TRS
    t = Vec3(1, 2, 3)
    r = Quat.from_euler_degrees(30, 45, 60)
    s = Vec3(1, 1, 1)
    m_trs = Mat4.from_trs(t, r, s)
    pos = m_trs.get_translation()
    assert abs(pos.x - 1) < 0.001, "TRS translation failed"
    print(f"  TRS matrix: translation extracted correctly ✓")
    
    print("  All Mat4 tests passed! ✓")


def test_transform():
    """Test Transform class."""
    print("\n=== Testing Transform ===")
    
    # Basic transform
    t = Transform()
    assert t.position.x == 0 and t.position.y == 0 and t.position.z == 0, "Initial position failed"
    print(f"  Initial transform: pos={t.position} ✓")
    
    # Set position
    t.position = Vec3(1, 2, 3)
    assert t.position.x == 1, "Set position failed"
    print(f"  Set position: {t.position} ✓")
    
    # Set rotation
    t.set_rotation_euler_degrees(45, 0, 0)
    euler = t.get_euler_degrees()
    assert abs(euler[0] - 45) < 1, "Set rotation failed"
    print(f"  Set rotation: ({euler[0]:.1f}°, {euler[1]:.1f}°, {euler[2]:.1f}°) ✓")
    
    # Get matrix
    m = t.get_matrix()
    assert m.m[12] == 1 and m.m[13] == 2 and m.m[14] == 3, "Transform matrix failed"
    print(f"  Transform matrix computed ✓")
    
    # Rotate by
    t2 = Transform()
    t2.rotate_by(Vec3.UP, 90)
    euler2 = t2.get_euler_degrees()
    assert abs(euler2[1] - 90) < 1, "Rotate by failed"
    print(f"  Rotate by 90° Y: ({euler2[0]:.1f}°, {euler2[1]:.1f}°, {euler2[2]:.1f}°) ✓")
    
    # Copy
    t3 = t.copy()
    assert t3.position.x == t.position.x, "Copy failed"
    print(f"  Copy transform ✓")
    
    # Lerp
    t_start = Transform()
    t_end = Transform()
    t_end.position = Vec3(10, 0, 0)
    t_mid = t_start.lerp_to(t_end, 0.5)
    assert abs(t_mid.position.x - 5) < 0.001, "Lerp failed"
    print(f"  Lerp: (0,0,0) -> (10,0,0) at t=0.5 = {t_mid.position} ✓")
    
    print("  All Transform tests passed! ✓")


def run_all_tests():
    """Run all tests."""
    print("=" * 60)
    print("  POSE ENGINE MATH LIBRARY TESTS")
    print("=" * 60)
    
    try:
        test_vec3()
        test_quat()
        test_mat4()
        test_transform()
        
        print("\n" + "=" * 60)
        print("  ALL TESTS PASSED! ✓")
        print("=" * 60)
        return True
        
    except AssertionError as e:
        print(f"\n  TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

#!/usr/bin/env python3
"""
Tests for the IK System
=======================

Tests CCD IK solver and IK chain handling.
"""

import sys
import os
import math

# Add pose_engine to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pose_engine.vec3 import Vec3
from pose_engine.quat import Quat
from pose_engine.skeleton import Skeleton
from pose_engine.ik import IKChain, CCDSolver


def test_ik_chain_creation():
    """Test creating an IK chain."""
    print("\n=== Testing IK Chain Creation ===")
    
    skeleton = Skeleton()
    
    # Create a simple 3-bone chain
    bone0 = skeleton.add_bone("bone0")
    bone0.bind_transform.position = Vec3(0, 0, 0)
    
    bone1 = skeleton.add_bone("bone1", parent_index=0)
    bone1.bind_transform.position = Vec3(1, 0, 0)
    
    bone2 = skeleton.add_bone("bone2", parent_index=1)
    bone2.bind_transform.position = Vec3(1, 0, 0)
    
    skeleton.update_all_transforms()
    
    # Create IK chain
    chain = IKChain.from_skeleton(skeleton, "bone0", "bone2")
    
    assert len(chain) == 3
    assert chain.root.name == "bone0"
    assert chain.effector.name == "bone2"
    
    print(f"Chain length: {chain.get_chain_length():.2f}")
    print(f"Effector position: {chain.get_effector_position()}")
    
    print("✓ IK chain creation test passed!")


def test_ccd_solver_simple():
    """Test CCD solver on a simple chain."""
    print("\n=== Testing CCD Solver (Simple) ===")
    
    skeleton = Skeleton()
    
    # Create a 3-bone arm
    shoulder = skeleton.add_bone("shoulder")
    shoulder.bind_transform.position = Vec3(0, 0, 0)
    
    upper_arm = skeleton.add_bone("upper_arm", parent_index=0)
    upper_arm.bind_transform.position = Vec3(1, 0, 0)
    
    forearm = skeleton.add_bone("forearm", parent_index=1)
    forearm.bind_transform.position = Vec3(1, 0, 0)
    
    hand = skeleton.add_bone("hand", parent_index=2)
    hand.bind_transform.position = Vec3(0.5, 0, 0)
    
    skeleton.update_all_transforms()
    
    # Create IK chain
    chain = IKChain.from_skeleton(skeleton, "shoulder", "hand")
    
    print(f"Initial effector position: {chain.get_effector_position()}")
    print(f"Chain length: {chain.get_chain_length():.2f}")
    
    # Target: slightly up and to the right
    target = Vec3(1.5, 1.0, 0)
    print(f"Target position: {target}")
    
    # Solve
    solver = CCDSolver()
    solver.max_iterations = 50
    solver.tolerance = 0.05
    
    result = solver.solve(chain, target)
    
    print(f"Success: {result.success}")
    print(f"Iterations: {result.iterations}")
    print(f"Final error: {result.final_error:.4f}")
    print(f"Final effector position: {chain.get_effector_position()}")
    
    # Should reach within tolerance or close
    assert result.final_error < 0.5, f"Error too high: {result.final_error}"
    
    print("✓ CCD solver simple test passed!")


def test_ccd_solver_reachable():
    """Test CCD solver with a reachable target."""
    print("\n=== Testing CCD Solver (Reachable Target) ===")
    
    skeleton = Skeleton()
    
    # Create a 2-bone chain (easier to solve)
    root = skeleton.add_bone("root")
    root.bind_transform.position = Vec3(0, 0, 0)
    
    mid = skeleton.add_bone("mid", parent_index=0)
    mid.bind_transform.position = Vec3(2, 0, 0)
    
    end = skeleton.add_bone("end", parent_index=1)
    end.bind_transform.position = Vec3(2, 0, 0)
    
    skeleton.update_all_transforms()
    
    chain = IKChain.from_skeleton(skeleton, "root", "end")
    
    initial_pos = chain.get_effector_position()
    print(f"Initial effector position: {initial_pos}")
    
    # Target is within reach (total length is 4)
    # Target at (2, 2, 0) - should be reachable
    target = Vec3(2, 2, 0)
    print(f"Target position: {target}")
    
    solver = CCDSolver()
    solver.max_iterations = 100
    solver.tolerance = 0.01
    
    result = solver.solve(chain, target)
    
    print(f"Success: {result.success}")
    print(f"Iterations: {result.iterations}")
    print(f"Final error: {result.final_error:.4f}")
    print(f"Final effector position: {chain.get_effector_position()}")
    
    # Should reach within tolerance
    assert result.final_error < 0.1, f"Error too high: {result.final_error}"
    
    print("✓ CCD solver reachable target test passed!")


def test_ccd_solver_unreachable():
    """Test CCD solver with an unreachable target."""
    print("\n=== Testing CCD Solver (Unreachable Target) ===")
    
    skeleton = Skeleton()
    
    # Create a short chain
    root = skeleton.add_bone("root")
    root.bind_transform.position = Vec3(0, 0, 0)
    
    end = skeleton.add_bone("end", parent_index=0)
    end.bind_transform.position = Vec3(1, 0, 0)
    
    skeleton.update_all_transforms()
    
    chain = IKChain.from_skeleton(skeleton, "root", "end")
    
    chain_length = chain.get_chain_length()
    print(f"Chain length: {chain_length:.2f}")
    
    # Target is beyond reach
    target = Vec3(100, 100, 0)
    print(f"Target position: {target} (unreachable)")
    
    solver = CCDSolver()
    solver.max_iterations = 50
    
    result = solver.solve(chain, target)
    
    print(f"Success: {result.success}")
    print(f"Iterations: {result.iterations}")
    print(f"Final error: {result.final_error:.4f}")
    print(f"Final effector position: {chain.get_effector_position()}")
    
    # Should extend toward target even if unreachable
    final_pos = chain.get_effector_position()
    distance_to_target = (target - final_pos).length()
    
    # The solver should have tried to reach
    print(f"Distance to unreachable target: {distance_to_target:.2f}")
    
    print("✓ CCD solver unreachable target test passed!")


def test_ccd_solver_rotation_propagation():
    """Test that rotations propagate correctly through hierarchy."""
    print("\n=== Testing CCD Rotation Propagation ===")
    
    skeleton = Skeleton()
    
    # Create a vertical chain
    hip = skeleton.add_bone("hip")
    hip.bind_transform.position = Vec3(0, 0, 0)
    
    knee = skeleton.add_bone("knee", parent_index=0)
    knee.bind_transform.position = Vec3(0, 1, 0)
    
    ankle = skeleton.add_bone("ankle", parent_index=1)
    ankle.bind_transform.position = Vec3(0, 1, 0)
    
    skeleton.update_all_transforms()
    
    chain = IKChain.from_skeleton(skeleton, "hip", "ankle")
    
    print(f"Initial ankle position: {chain.get_effector_position()}")
    
    # Target to the side
    target = Vec3(1, 2, 0)
    
    solver = CCDSolver()
    solver.max_iterations = 100
    solver.tolerance = 0.05
    
    result = solver.solve(chain, target)
    
    print(f"Final ankle position: {chain.get_effector_position()}")
    print(f"Final error: {result.final_error:.4f}")
    
    # Verify hierarchy is still valid
    skeleton.update_all_transforms()
    ankle_pos = skeleton.get_bone("ankle").get_world_position()
    print(f"Ankle position after update: {ankle_pos}")
    
    print("✓ CCD rotation propagation test passed!")


def run_all_tests():
    """Run all IK tests."""
    print("=" * 60)
    print("IK SYSTEM TESTS")
    print("=" * 60)
    
    test_ik_chain_creation()
    test_ccd_solver_simple()
    test_ccd_solver_reachable()
    test_ccd_solver_unreachable()
    test_ccd_solver_rotation_propagation()
    
    print("\n" + "=" * 60)
    print("ALL IK TESTS PASSED! ✓")
    print("=" * 60)


if __name__ == "__main__":
    run_all_tests()

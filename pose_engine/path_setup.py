"""
Path Setup Module
=================

Centralized path manipulation for the Krita 3D Pose Plugin.
Ensures pose_engine and plugin directories are in sys.path.

Usage:
    from pose_engine.path_setup import ensure_path
    ensure_path()
"""

import sys
import os

# Track if paths have been set up
_path_setup_done = False

def ensure_path() -> None:
    """
    Ensure pose_engine and plugin directories are in sys.path.
    
    This function is idempotent - calling it multiple times has no effect
    after the first call.
    """
    global _path_setup_done
    
    if _path_setup_done:
        return
    
    # Get the pose_engine directory
    _pose_engine_dir = os.path.dirname(os.path.realpath(__file__))
    # Get the parent directory (project root or krita_3d_pose)
    _parent_dir = os.path.dirname(_pose_engine_dir)
    
    # Add pose_engine directory
    if _pose_engine_dir not in sys.path:
        sys.path.insert(0, _pose_engine_dir)
    
    # Add parent directory
    if _parent_dir not in sys.path:
        sys.path.insert(0, _parent_dir)
    
    _path_setup_done = True


def get_plugin_dir() -> str:
    """Get the pose_engine directory path."""
    return os.path.dirname(os.path.realpath(__file__))


def get_parent_dir() -> str:
    """Get the parent directory (project root or plugin container)."""
    return os.path.dirname(get_plugin_dir())

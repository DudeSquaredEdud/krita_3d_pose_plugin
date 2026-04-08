"""
IK Module - Inverse Kinematics Solvers
======================================

Provides IK solvers for posing bone chains.

Available solvers:
- CCD (Cyclic Coordinate Descent)
"""

from .solver import IKSolver, IKChain, IKResult
from .ccd import CCDSolver

__all__ = ['IKSolver', 'IKChain', 'IKResult', 'CCDSolver']

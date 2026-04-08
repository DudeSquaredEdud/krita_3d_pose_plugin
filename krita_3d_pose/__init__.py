"""
3D Model Poser - Krita Plugin
==============================

A plugin for loading, posing and positioning 3D models in Krita.
Supports GLB format with real-time OpenGL preview.

Features:
- Load rigged GLB models
- Pose bones using rotation controls
- IK solving for limb posing
- Real-time 3D preview

Version: 1.0.0 (Rebuild)
"""

import os
import sys
import traceback

# Ensure pose_engine is in path
from pose_engine.path_setup import ensure_path
ensure_path()

# Setup logging
from pose_engine.logger import get_logger, setup_logging
import tempfile
LOG_FILE = os.path.join(tempfile.gettempdir(), "krita_3d_pose.log")
setup_logging(log_file=LOG_FILE, console=False)
logger = get_logger(__name__)

logger.info("=" * 50)
logger.info("3D Model Poser plugin starting...")
logger.info(f"Python version: {sys.version}")

# Check PyQt5 availability
try:
    from PyQt5.QtCore import Qt, QTimer, QSize, pyqtSignal
    from PyQt5.QtGui import QImage, QPainter, QColor, QMatrix4x4, QVector3D, QVector4D
    from PyQt5.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
        QSlider, QComboBox, QFileDialog, QSpinBox, QDoubleSpinBox,
        QGroupBox, QSplitter, QMessageBox, QProgressBar
    )
    logger.info("PyQt5 imported successfully")
except ImportError as e:
    logger.error(f"CRITICAL: PyQt5 import failed: {e}")
    raise

# Import Krita
try:
    from krita import Krita, Extension, DockWidget, DockWidgetFactory, DockWidgetFactoryBase
    logger.info("Krita API imported successfully")
except ImportError as e:
    logger.error(f"CRITICAL: Krita API import failed: {e}")
    raise

# Import pose_engine (our new core library)
try:
    from pose_engine import Vec3, Quat, Mat4, Transform
    from pose_engine import Bone, Skeleton
    logger.info("pose_engine imported successfully")
except ImportError as e:
    logger.warning(f"WARNING: pose_engine import failed: {e}")
    logger.warning("Plugin will run in limited mode")

# Import plugin components - use launcher docker for minimal UI
try:
    from .launcher_docker import Krita3DLauncherDocker
    logger.info("Launcher docker imported successfully")
except ImportError as e:
    logger.error(f"CRITICAL: Launcher docker import failed: {e}")
    logger.error(traceback.format_exc())
    raise

DOCKER_ID = "krita_3d_launcher"


class Krita3DPoserExtension(Extension):
    """Main extension class for the 3D Model Poser plugin."""

    def __init__(self, parent):
        super().__init__(parent)
        logger.info("Extension initialized")

    def setup(self):
        """Called once when Krita starts."""
        logger.info("Extension setup called")

    def createActions(self, window):
        """Called for each window - can add menu actions here."""
        logger.info("createActions called")


# Register the plugin with Krita
_app = Krita.instance()

# Add extension
_app.addExtension(Krita3DPoserExtension(_app))
logger.info("Extension registered")

# Add dock widget factory - minimal launcher
_app.addDockWidgetFactory(
    DockWidgetFactory(DOCKER_ID, DockWidgetFactoryBase.DockRight, Krita3DLauncherDocker)
)
logger.info("3D Launcher docker registered")
logger.info("Plugin initialization complete!")

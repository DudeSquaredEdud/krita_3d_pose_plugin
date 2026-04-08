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

# Initialize logger first
import os
import tempfile
import sys
import traceback

# Plugin directory for bundled dependencies
_plugin_dir = os.path.dirname(os.path.realpath(__file__))
_parent_dir = os.path.dirname(_plugin_dir)
if _plugin_dir not in sys.path:
    sys.path.insert(0, _plugin_dir)
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)

# Log file for debugging
LOG_FILE = os.path.join(tempfile.gettempdir(), "krita_3d_pose.log")

def log_message(msg, level="INFO"):
    """Write a message to the log file."""
    try:
        import time
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] [{level}] {msg}\n")
    except Exception:
        pass

log_message("=" * 50)
log_message("3D Model Poser plugin starting...")
log_message(f"Python version: {sys.version}")
log_message(f"Plugin directory: {_plugin_dir}")
log_message(f"Parent directory: {_parent_dir}")

# Check PyQt5 availability
try:
    from PyQt5.QtCore import Qt, QTimer, QSize, pyqtSignal
    from PyQt5.QtGui import QImage, QPainter, QColor, QMatrix4x4, QVector3D, QVector4D
    from PyQt5.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
        QSlider, QComboBox, QFileDialog, QSpinBox, QDoubleSpinBox,
        QGroupBox, QSplitter, QMessageBox, QProgressBar
    )
    log_message("PyQt5 imported successfully")
except ImportError as e:
    log_message(f"CRITICAL: PyQt5 import failed: {e}", "ERROR")
    raise

# Import Krita
try:
    from krita import Krita, Extension, DockWidget, DockWidgetFactory, DockWidgetFactoryBase
    log_message("Krita API imported successfully")
except ImportError as e:
    log_message(f"CRITICAL: Krita API import failed: {e}", "ERROR")
    raise

# Import pose_engine (our new core library)
try:
    from pose_engine import Vec3, Quat, Mat4, Transform
    from pose_engine import Bone, Skeleton
    log_message("pose_engine imported successfully")
except ImportError as e:
    log_message(f"WARNING: pose_engine import failed: {e}", "WARNING")
    log_message("Plugin will run in limited mode")

# Import plugin components
try:
    from .docker_panel import Krita3DPoserDocker
    from .multi_model_docker import KritaMultiModelDocker
    log_message("Plugin components imported successfully")
except ImportError as e:
    log_message(f"Import error: {e}", "ERROR")
    log_message(traceback.format_exc(), "ERROR")
    raise

DOCKER_ID = "krita_3d_pose"
MULTI_DOCKER_ID = "krita_3d_multi_model"


class Krita3DPoserExtension(Extension):
    """Main extension class for the 3D Model Poser plugin."""

    def __init__(self, parent):
        super().__init__(parent)
        log_message("Extension initialized")

    def setup(self):
        """Called once when Krita starts."""
        log_message("Extension setup called")

    def createActions(self, window):
        """Called for each window - can add menu actions here."""
        log_message("createActions called")


# Register the plugin with Krita
_app = Krita.instance()

# Add extension
_app.addExtension(Krita3DPoserExtension(_app))
log_message("Extension registered")

# Add dock widget factories
_app.addDockWidgetFactory(
    DockWidgetFactory(DOCKER_ID, DockWidgetFactoryBase.DockRight, Krita3DPoserDocker)
)
log_message("Single-model docker registered")

_app.addDockWidgetFactory(
    DockWidgetFactory(MULTI_DOCKER_ID, DockWidgetFactoryBase.DockRight, KritaMultiModelDocker)
)
log_message("Multi-model docker registered")
log_message("Plugin initialization complete!")

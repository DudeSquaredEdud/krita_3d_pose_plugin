"""
3D Pose Editor Window
======================

A standalone window containing the full 3D pose editor.
This window has proper keyboard focus for QWEASD camera controls.
"""

import os
import sys
from typing import Optional

# Ensure pose_engine is in path
from pose_engine.path_setup import ensure_path
ensure_path()

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QFileDialog, QSplitter, QMessageBox, QGroupBox, QTreeWidget,
    QTreeWidgetItem, QCheckBox, QListWidget, QListWidgetItem, QTabWidget,
    QSlider, QMainWindow, QMenuBar, QMenu, QAction, QStatusBar
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor, QImage, QPainter

# Try to import Krita API (optional - only available when running inside Krita)
try:
    from krita import Krita
    KRITA_AVAILABLE = True
except ImportError:
    KRITA_AVAILABLE = False

# Setup logger
from pose_engine.logger import get_logger
logger = get_logger(__name__)

# Import pose_engine components
try:
    from pose_engine.scene import Scene
    from pose_engine.model_instance import ModelInstance
    from pose_engine.pose_state import PoseSnapshot, PoseSerializer
    from pose_engine.ui.multi_viewport import MultiViewport3D
    from pose_engine.settings import PluginSettings
    from pose_engine.ui.settings_dialog import AdvancedSettingsDialog
    from pose_engine.ui.camera_panel import CameraPanel
    from pose_engine.ui.styles import Colors
    logger.info("Core imports successful")
except ImportError as e:
    logger.error(f"Import error: {e}")
    raise

# Import scene management components
try:
    from pose_engine.project_scene import ProjectScene
    from pose_engine.ui.scene_tab import SceneTab
    logger.info("Scene imports successful")
except ImportError as e:
    logger.warning(f"Scene import error: {e}")
    ProjectScene = None
    SceneTab = None


class PoseEditorWindow(QMainWindow):
    """
    Standalone window for 3D pose editing.
    
    Contains the full editor with models, bones, poses, and camera tabs.
    Has proper keyboard focus for QWEASD camera controls.
    """
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        
        self.setWindowTitle("3D Pose Editor")
        self.setMinimumSize(1000, 700)
        
        # Initialize settings
        self._settings = None
        if PluginSettings:
            try:
                self._settings = PluginSettings()
                self._settings.load()
            except Exception as e:
                logger.debug(f"[Editor] Failed to initialize settings: {e}")
        
        # Set up UI
        self._setup_ui()
        self._setup_menubar()
        self._setup_statusbar()
        
        # Update timer for continuous rendering
        self._update_timer = QTimer(self)
        self._update_timer.timeout.connect(self._on_update)
        self._update_timer.start(16)  # ~60 FPS
        
        # Sync timer for layer sync
        self._sync_timer = QTimer()
        self._sync_timer.setSingleShot(True)
        self._sync_timer.setInterval(200)
        
        # Camera panel reference
        self._camera_panel = None
        
        # Refresh pose list
        self._refresh_pose_list()
    
    def _setup_ui(self) -> None:
        """Set up the main UI."""
        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        
        layout = QHBoxLayout(central)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Left panel - controls with tabs
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(5, 5, 5, 5)
        
        # Tab widget
        self._tab_widget = QTabWidget()
        
        # Tab 1: Models & Visibility
        models_tab = QWidget()
        models_tab_layout = QVBoxLayout(models_tab)
        
        # Model management group
        models_group = QGroupBox("Models")
        models_layout = QVBoxLayout(models_group)
        
        btn_layout = QHBoxLayout()
        add_btn = QPushButton("Add")
        add_btn.clicked.connect(self._on_add_model)
        btn_layout.addWidget(add_btn)
        
        dup_btn = QPushButton("Duplicate")
        dup_btn.clicked.connect(self._on_duplicate_model)
        btn_layout.addWidget(dup_btn)
        
        rem_btn = QPushButton("Remove")
        rem_btn.clicked.connect(self._on_remove_model)
        btn_layout.addWidget(rem_btn)
        
        models_layout.addLayout(btn_layout)
        
        self._model_tree = QTreeWidget()
        self._model_tree.setHeaderLabels(["Models"])
        self._model_tree.itemClicked.connect(self._on_model_tree_click)
        self._model_tree.setMaximumHeight(120)
        models_layout.addWidget(self._model_tree)
        
        models_tab_layout.addWidget(models_group)
        
        # Visibility controls
        vis_group = QGroupBox("Visibility")
        vis_layout = QVBoxLayout(vis_group)
        
        self._show_mesh_cb = QCheckBox("Mesh")
        self._show_mesh_cb.setChecked(True)
        self._show_mesh_cb.toggled.connect(self._on_toggle_mesh)
        vis_layout.addWidget(self._show_mesh_cb)
        
        self._show_skeleton_cb = QCheckBox("Skeleton")
        self._show_skeleton_cb.setChecked(True)
        self._show_skeleton_cb.toggled.connect(self._on_toggle_skeleton)
        vis_layout.addWidget(self._show_skeleton_cb)
        
        self._show_joints_cb = QCheckBox("Joints")
        self._show_joints_cb.setChecked(True)
        self._show_joints_cb.toggled.connect(self._on_toggle_joints)
        vis_layout.addWidget(self._show_joints_cb)
        
        self._show_gizmo_cb = QCheckBox("Gizmo")
        self._show_gizmo_cb.setChecked(True)
        self._show_gizmo_cb.toggled.connect(self._on_toggle_gizmo)
        vis_layout.addWidget(self._show_gizmo_cb)
        
        models_tab_layout.addWidget(vis_group)
        models_tab_layout.addStretch()
        
        self._tab_widget.addTab(models_tab, "Models")
        
        # Tab 2: Bones & Gizmo
        bones_tab = QWidget()
        bones_tab_layout = QVBoxLayout(bones_tab)
        
        bone_group = QGroupBox("Bones")
        bone_layout = QVBoxLayout(bone_group)
        
        self._bone_tree = QTreeWidget()
        self._bone_tree.setHeaderLabels(["Bone Hierarchy"])
        self._bone_tree.itemClicked.connect(self._on_bone_tree_click)
        self._bone_tree.setMaximumHeight(150)
        bone_layout.addWidget(self._bone_tree)
        
        bones_tab_layout.addWidget(bone_group)
        
        gizmo_group = QGroupBox("Gizmo Mode")
        gizmo_layout = QVBoxLayout(gizmo_group)
        
        mode_layout = QHBoxLayout()
        
        self._rotation_btn = QPushButton("Rotate")
        self._rotation_btn.setCheckable(True)
        self._rotation_btn.setChecked(True)
        self._rotation_btn.clicked.connect(lambda: self._set_gizmo_mode("rotation"))
        mode_layout.addWidget(self._rotation_btn)

        self._movement_btn = QPushButton("Move")
        self._movement_btn.setCheckable(True)
        self._movement_btn.clicked.connect(lambda: self._set_gizmo_mode("movement"))
        mode_layout.addWidget(self._movement_btn)

        self._scale_btn = QPushButton("Scale")
        self._scale_btn.setCheckable(True)
        self._scale_btn.clicked.connect(lambda: self._set_gizmo_mode("scale"))
        mode_layout.addWidget(self._scale_btn)
        
        gizmo_layout.addLayout(mode_layout)
        
        toggle_btn = QPushButton("Toggle (G)")
        toggle_btn.clicked.connect(self._toggle_gizmo_mode)
        gizmo_layout.addWidget(toggle_btn)
        
        bones_tab_layout.addWidget(gizmo_group)
        bones_tab_layout.addStretch()
        
        self._tab_widget.addTab(bones_tab, "Bones")
        
        # Tab 3: Poses
        poses_tab = QWidget()
        poses_tab_layout = QVBoxLayout(poses_tab)
        
        poses_group = QGroupBox("Poses")
        poses_layout = QVBoxLayout(poses_group)
        
        pose_btn_layout = QHBoxLayout()
        
        load_pose_btn = QPushButton("Load")
        load_pose_btn.clicked.connect(self._on_load_pose)
        pose_btn_layout.addWidget(load_pose_btn)
        
        save_pose_btn = QPushButton("Save")
        save_pose_btn.clicked.connect(self._on_save_pose)
        pose_btn_layout.addWidget(save_pose_btn)
        
        poses_layout.addLayout(pose_btn_layout)
        
        self._pose_list = QListWidget()
        self._pose_list.setMaximumHeight(150)
        self._pose_list.itemDoubleClicked.connect(self._on_pose_double_clicked)
        poses_layout.addWidget(self._pose_list)
        
        apply_pose_btn = QPushButton("Apply")
        apply_pose_btn.clicked.connect(self._on_apply_pose)
        poses_layout.addWidget(apply_pose_btn)
        
        poses_tab_layout.addWidget(poses_group)
        poses_tab_layout.addStretch()
        
        self._tab_widget.addTab(poses_tab, "Poses")
        
        # Tab 4: Camera Controls
        camera_tab = QWidget()
        camera_tab_layout = QVBoxLayout(camera_tab)
        
        view_mode_group = QGroupBox("View Mode")
        view_mode_layout = QHBoxLayout(view_mode_group)
        
        self._orbit_btn = QPushButton("Orbit")
        self._orbit_btn.setCheckable(True)
        self._orbit_btn.setChecked(True)
        self._orbit_btn.setToolTip("Camera orbits around target (QWEASD moves target)")
        self._orbit_btn.clicked.connect(lambda: self._set_camera_mode("orbit"))
        view_mode_layout.addWidget(self._orbit_btn)
        
        self._head_look_btn = QPushButton("Head Look")
        self._head_look_btn.setCheckable(True)
        self._head_look_btn.setToolTip("Camera rotates in place (QWEASD moves camera)")
        self._head_look_btn.clicked.connect(lambda: self._set_camera_mode("head_look"))
        view_mode_layout.addWidget(self._head_look_btn)
        
        camera_tab_layout.addWidget(view_mode_group)
        
        fov_group = QGroupBox("Field of View")
        fov_layout = QHBoxLayout(fov_group)
        
        self._fov_slider = QSlider(Qt.Horizontal)
        self._fov_slider.setRange(30, 120)
        self._fov_slider.setValue(45)
        self._fov_slider.valueChanged.connect(self._on_fov_slider_changed)
        fov_layout.addWidget(self._fov_slider)
        
        self._fov_label = QLabel("45°")
        self._fov_label.setMinimumWidth(40)
        fov_layout.addWidget(self._fov_label)
        
        camera_tab_layout.addWidget(fov_group)
        
        speed_group = QGroupBox("Movement Speed")
        speed_layout = QHBoxLayout(speed_group)
        
        self._speed_slider = QSlider(Qt.Horizontal)
        self._speed_slider.setRange(1, 100)
        self._speed_slider.setValue(50)
        self._speed_slider.valueChanged.connect(self._on_speed_slider_changed)
        speed_layout.addWidget(self._speed_slider)
        
        self._speed_label = QLabel("1.0x")
        self._speed_label.setMinimumWidth(40)
        speed_layout.addWidget(self._speed_label)
        
        camera_tab_layout.addWidget(speed_group)
        
        actions_group = QGroupBox("Quick Actions")
        actions_layout = QHBoxLayout(actions_group)
        
        frame_btn = QPushButton("Frame")
        frame_btn.setToolTip("Frame all models (F)")
        frame_btn.clicked.connect(self._on_frame_model)
        actions_layout.addWidget(frame_btn)
        
        reset_btn = QPushButton("Reset")
        reset_btn.setToolTip("Reset camera to default")
        reset_btn.clicked.connect(self._on_reset_camera)
        actions_layout.addWidget(reset_btn)
        
        top_btn = QPushButton("Top")
        top_btn.setToolTip("View from top")
        top_btn.clicked.connect(lambda: self._set_preset_view("top"))
        actions_layout.addWidget(top_btn)
        
        front_btn = QPushButton("Front")
        front_btn.setToolTip("View from front")
        front_btn.clicked.connect(lambda: self._set_preset_view("front"))
        actions_layout.addWidget(front_btn)
        
        camera_tab_layout.addWidget(actions_group)

        # Visual Effects group
        effects_group = QGroupBox("Visual Effects")
        effects_layout = QVBoxLayout(effects_group)

        self._distance_gradient_btn = QPushButton("Distance Gradient")
        self._distance_gradient_btn.setCheckable(True)
        self._distance_gradient_btn.setChecked(False)
        self._distance_gradient_btn.setToolTip(
            "Toggle distance-based color gradient overlay.\n"
            "Surfaces are tinted based on distance from camera:\n"
            "Near = Blue, Far = Magenta"
        )
        self._distance_gradient_btn.clicked.connect(lambda: self._on_distance_gradient_toggle(self._distance_gradient_btn.isChecked()))
        effects_layout.addWidget(self._distance_gradient_btn)

        # Distance range slider
        distance_range_layout = QHBoxLayout()
        distance_range_label = QLabel("Distance:")
        distance_range_label.setMinimumWidth(60)
        distance_range_layout.addWidget(distance_range_label)

        self._distance_range_slider = QSlider(Qt.Horizontal)
        self._distance_range_slider.setRange(10, 500)  # 0.1 to 5.0 units
        self._distance_range_slider.setValue(50)  # Default 0.5 units
        self._distance_range_slider.setToolTip(
            "Controls the distance range for the gradient effect.\n"
            "Lower = tighter gradient, Higher = wider gradient"
        )
        self._distance_range_slider.valueChanged.connect(self._on_distance_range_changed)
        distance_range_layout.addWidget(self._distance_range_slider)

        self._distance_range_value = QLabel("0.5")
        self._distance_range_value.setMinimumWidth(30)
        distance_range_layout.addWidget(self._distance_range_value)

        effects_layout.addLayout(distance_range_layout)

        camera_tab_layout.addWidget(effects_group)

        # Bookmarks group
        bookmarks_group = QGroupBox("Camera Bookmarks")
        bookmarks_layout = QVBoxLayout(bookmarks_group)

        # Help text
        help_label = QLabel("Ctrl+1-9: Save | 1-9: Recall")
        help_label.setStyleSheet("color: #888; font-size: 9px;")
        bookmarks_layout.addWidget(help_label)

        # Bookmark grid (3x3)
        bookmark_grid = QHBoxLayout()
        self._bookmark_buttons = []
        for i in range(1, 10):
            btn = QPushButton(str(i))
            btn.setFixedSize(28, 28)
            btn.setToolTip(f"Bookmark {i}\nClick to recall, Ctrl+Click to save")
            btn.clicked.connect(lambda checked, idx=i: self._on_bookmark_click(idx))
            bookmark_grid.addWidget(btn)
            self._bookmark_buttons.append(btn)
        bookmarks_layout.addLayout(bookmark_grid)

        # Import/Export buttons
        io_layout = QHBoxLayout()
        import_btn = QPushButton("Import")
        import_btn.clicked.connect(self._on_import_bookmarks)
        io_layout.addWidget(import_btn)

        export_btn = QPushButton("Export")
        export_btn.clicked.connect(self._on_export_bookmarks)
        io_layout.addWidget(export_btn)
        bookmarks_layout.addLayout(io_layout)

        camera_tab_layout.addWidget(bookmarks_group)

        camera_tab_layout.addStretch()

        self._tab_widget.addTab(camera_tab, "Camera")

        # Tab 5: Scene Management
        logger.debug(f"[Editor] Adding Scene tab - SceneTab: {SceneTab is not None}, ProjectScene: {ProjectScene is not None}")
        self._scene_tab = None
        self._project_scene = None
        if SceneTab and ProjectScene:
            try:
                self._scene_tab = SceneTab()
                self._tab_widget.addTab(self._scene_tab, "Scene")
                # Connect reload signal
                self._scene_tab.reload_from_project_requested.connect(self._on_reload_from_project)
                logger.debug("[Editor] Scene tab added successfully")
            except Exception as e:
                logger.debug(f"[Editor] Failed to create scene tab: {e}")
                import traceback
                traceback.print_exc()
        else:
            logger.debug(f"[Editor] Skipping scene tab - SceneTab: {SceneTab is not None}, ProjectScene: {ProjectScene is not None}")

        # Add tabs to layout
        left_layout.addWidget(self._tab_widget)
        
        # Layer Sync section
        sync_group = QGroupBox("Layer Sync")
        sync_layout = QVBoxLayout(sync_group)
        
        self._sync_btn = QPushButton("📷 Sync to Layer")
        self._sync_btn.clicked.connect(self._on_sync_to_layer)
        self._sync_btn.setStyleSheet(f"background-color: #4CAF50; color: white; font-weight: bold; padding: 8px;")
        sync_layout.addWidget(self._sync_btn)
        
        left_layout.addWidget(sync_group)
        
        # Status label
        self._status_label = QLabel("No models loaded")
        left_layout.addWidget(self._status_label)
        
        # Main splitter
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_panel)
        
        # 3D Viewport
        if MultiViewport3D:
            self._viewport = MultiViewport3D()
            splitter.addWidget(self._viewport)
            
            # Connect signals
            self._viewport.model_selected.connect(self._on_model_selected)
            self._viewport.bone_selected.connect(self._on_bone_selected)
            self._viewport.model_selection_changed.connect(self._on_model_selection_changed)
            self._viewport.sync_to_layer_requested.connect(self._on_sync_to_layer)
            
            # Apply settings to viewport
            if self._settings:
                self._viewport.set_settings(self._settings)
        else:
            self._viewport = None
            placeholder = QLabel("OpenGL not available")
            placeholder.setAlignment(Qt.AlignCenter)
            splitter.addWidget(placeholder)
        
        splitter.setSizes([300, 700])
        layout.addWidget(splitter)

        # Initialize ProjectScene and connect to Scene tab
        self._initialize_project_scene()

        # Setup camera panel
        self._setup_camera_panel()

    def _initialize_project_scene(self) -> None:
        """Initialize the ProjectScene manager and connect to UI."""
        if not self._viewport or not ProjectScene:
            logger.debug(f"[ProjectScene] Skipping initialization - viewport: {self._viewport is not None}, ProjectScene: {ProjectScene is not None}")
            return

        # Create ProjectScene wrapping the viewport's scene
        scene = self._viewport.get_scene() if self._viewport else None
        if scene:
            self._project_scene = ProjectScene(scene, parent=self)

            # Connect to scene tab
            if self._scene_tab:
                self._scene_tab.set_project_scene(self._project_scene)

            # Connect scene change signals
            self._project_scene.scene_saved.connect(self._on_scene_saved)
            self._project_scene.scene_loaded.connect(self._on_scene_loaded)
            self._project_scene.bookmarks_loaded.connect(self._on_bookmarks_loaded)
    
            logger.debug("[ProjectScene] Initialized successfully")
            
            # Try to auto-load scene for current Krita project
            self._try_autoload_scene()
        else:
            logger.debug("[ProjectScene] No scene available from viewport")

    def _try_autoload_scene(self) -> None:
        """Try to automatically load the scene for the current Krita project."""
        if not self._project_scene:
            return
            
        try:
            from krita import Krita
            app = Krita.instance()
            doc = app.activeDocument()
            
            if doc:
                # Get the document file path
                doc_path = doc.fileName()
                if doc_path:
                    logger.debug(f"[ProjectScene] Found active document: {doc_path}")
                    # Try to load the associated scene
                    if self._project_scene.load_for_krita_project(doc_path):
                        logger.debug(f"[ProjectScene] Auto-loaded scene for project")
                    else:
                        logger.debug(f"[ProjectScene] No existing scene for project, will create new on save")
                else:
                    logger.debug("[ProjectScene] Document has no file path (unsaved)")
            else:
                logger.debug("[ProjectScene] No active document")
        except Exception as e:
            logger.debug(f"[ProjectScene] Error during auto-load: {e}")

    def _on_scene_saved(self, file_path: str) -> None:
        """Handle scene saved event."""
        # Save camera bookmarks from viewport to project scene
        if self._viewport and self._project_scene:
            bookmarks = self._viewport.get_project_bookmarks()
            self._project_scene.set_camera_bookmarks(bookmarks)
            logger.debug(f"[Editor] Saved {len(bookmarks)} camera bookmarks")
        
        if self._status_label:
            self._status_label.setText(f"Scene saved: {os.path.basename(file_path)}")
    
    def _on_scene_loaded(self, file_path: str) -> None:
        """Handle scene loaded event."""
        logger.debug(f"[Editor] Scene loaded: {file_path}")
        if self._status_label:
            self._status_label.setText(f"Scene loaded: {os.path.basename(file_path)}")

        # Reload the viewport's GPU resources for the new scene
        if self._viewport:
            self._viewport.reload_scene()

        # Explicitly update poses for all models after scene load
        # This ensures the skeleton transforms are computed and GPU data is updated
        if self._project_scene and self._project_scene.scene:
            logger.debug("[Editor] Updating poses for all models after scene load")
            for model in self._project_scene.scene.get_all_models():
                if model.skeleton:
                    logger.debug(f"[Editor] Updating transforms for model: {model.name}")
                    model.skeleton.mark_all_dirty()
                    model.update_transforms()

        # Rebuild UI trees
        self._rebuild_model_tree()
        self._rebuild_bone_tree()

        # Update the scene tab info
        if self._scene_tab:
            self._scene_tab._update_info()
    
    def _on_bookmarks_loaded(self, bookmarks: dict) -> None:
        """Handle camera bookmarks loaded from scene file."""
        logger.debug(f"[Editor] Loading {len(bookmarks)} camera bookmarks into viewport")
        if self._viewport:
            self._viewport.load_project_bookmarks(bookmarks)

    def _on_reload_from_project(self) -> None:
        """Handle reload from project button click."""
        if not self._project_scene:
            return
            
        # Clear the existing scene first
        logger.debug("[Editor] Clearing existing scene for reload")
        self._project_scene.new_scene()
        
        # Clear the viewport's GPU resources
        if self._viewport:
            self._viewport._model_renderers.clear()
            self._viewport._model_skeleton_viz.clear()
            self._viewport.update()
        
        # Rebuild UI trees (now empty)
        self._rebuild_model_tree()
        self._rebuild_bone_tree()
        
        # Now try to load the scene for the current project
        self._try_autoload_scene()

    def _setup_menubar(self) -> None:
        """Set up the menu bar."""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("File")
        
        add_model_action = QAction("Add Model...", self)
        add_model_action.setShortcut("Ctrl+O")
        add_model_action.triggered.connect(self._on_add_model)
        file_menu.addAction(add_model_action)
        
        file_menu.addSeparator()
        
        load_pose_action = QAction("Load Pose...", self)
        load_pose_action.setShortcut("Ctrl+L")
        load_pose_action.triggered.connect(self._on_load_pose)
        file_menu.addAction(load_pose_action)
        
        save_pose_action = QAction("Save Pose...", self)
        save_pose_action.setShortcut("Ctrl+S")
        save_pose_action.triggered.connect(self._on_save_pose)
        file_menu.addAction(save_pose_action)
        
        file_menu.addSeparator()
        
        close_action = QAction("Close", self)
        close_action.setShortcut("Ctrl+W")
        close_action.triggered.connect(self.close)
        file_menu.addAction(close_action)
        
        # View menu
        view_menu = menubar.addMenu("View")
        
        frame_action = QAction("Frame Model", self)
        frame_action.setShortcut("F")
        frame_action.triggered.connect(self._on_frame_model)
        view_menu.addAction(frame_action)
        
        reset_action = QAction("Reset Camera", self)
        reset_action.setShortcut("R")
        reset_action.triggered.connect(self._on_reset_camera)
        view_menu.addAction(reset_action)
        
        view_menu.addSeparator()
        
        top_action = QAction("Top View", self)
        top_action.triggered.connect(lambda: self._set_preset_view("top"))
        view_menu.addAction(top_action)
        
        front_action = QAction("Front View", self)
        front_action.triggered.connect(lambda: self._set_preset_view("front"))
        view_menu.addAction(front_action)
        
        # Settings menu
        settings_menu = menubar.addMenu("Settings")
        
        advanced_action = QAction("Advanced Settings...", self)
        advanced_action.triggered.connect(self._show_advanced_settings)
        settings_menu.addAction(advanced_action)
    
    def _setup_statusbar(self) -> None:
        """Set up the status bar."""
        self.statusBar().showMessage("Ready")
    
    def _setup_camera_panel(self) -> None:
        """Set up the floating camera panel - disabled, using Camera tab instead."""
        # Floating camera panel removed - bookmarks are now in the Camera tab
        self._camera_panel = None
    
    # -------------------------------------------------------------------------
    # Model Management
    # -------------------------------------------------------------------------
    
    def _on_add_model(self) -> None:
        """Handle add model button."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Add 3D Model",
            "",
            "GLB Files (*.glb);;GLTF Files (*.gltf);;All Files (*)"
        )
        
        if file_path:
            self._add_model(file_path)
    
    def _add_model(self, file_path: str) -> None:
        """Add a model to the scene."""
        if not self._viewport:
            return

        name = os.path.splitext(os.path.basename(file_path))[0]

        try:
            model = self._viewport.add_model(file_path, name)

            if model:
                self._rebuild_model_tree()
                self._rebuild_bone_tree()
                self._status_label.setText(f"Loaded: {name} ({model.get_bone_count()} bones)")
                self.statusBar().showMessage(f"Loaded model: {name}")
                # Mark scene as changed for auto-save
                if self._project_scene:
                    self._project_scene.mark_changed()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load model: {e}")

    def _on_duplicate_model(self) -> None:
        """Handle duplicate model button."""
        if not self._viewport:
            return

        model = self._viewport.get_selected_model()
        if model:
            copy = self._viewport.duplicate_model(model.id)
            if copy:
                self._rebuild_model_tree()
                self._rebuild_bone_tree()
                self._status_label.setText(f"Duplicated: {copy.name}")
                # Mark scene as changed for auto-save
                if self._project_scene:
                    self._project_scene.mark_changed()

    def _on_remove_model(self) -> None:
        """Handle remove model button."""
        if not self._viewport:
            return

        model = self._viewport.get_selected_model()
        if model:
            self._viewport.remove_model(model.id)
            self._rebuild_model_tree()
            self._rebuild_bone_tree()
            self._status_label.setText(f"Removed: {model.name}")
            # Mark scene as changed for auto-save
            if self._project_scene:
                self._project_scene.mark_changed()
    
    def _rebuild_model_tree(self) -> None:
        """Rebuild the model tree."""
        if not self._viewport:
            return
        
        self._model_tree.clear()
        
        selected_model_id = self._viewport.get_scene().get_selected_model_id()
        
        scene = self._viewport.get_scene()
        for model in scene.get_all_models():
            item = QTreeWidgetItem([model.name])
            item.setData(0, Qt.UserRole, model.id)
            item.setCheckState(0, Qt.Checked if model.visible else Qt.Unchecked)
            
            if model.id == selected_model_id:
                item.setBackground(0, QColor(100, 150, 200, 100))
                font = item.font(0)
                font.setBold(True)
                item.setFont(0, font)
            
            self._model_tree.addTopLevelItem(item)
        
        self._model_tree.expandAll()
    
    def _rebuild_bone_tree(self) -> None:
        """Rebuild the bone tree."""
        if not self._viewport:
            return

        # Preserve expansion state before clearing
        expanded_items = self._collect_expanded_items()

        self._bone_tree.clear()

        selected_model_id = self._viewport.get_scene().get_selected_model_id()

        scene = self._viewport.get_scene()
        for model in scene.get_all_models():
            model_item = QTreeWidgetItem([model.name])
            model_item.setData(0, Qt.UserRole, f"model:{model.id}")

            if model.id == selected_model_id:
                model_item.setBackground(0, QColor(100, 150, 200, 100))
                font = model_item.font(0)
                font.setBold(True)
                model_item.setFont(0, font)

            # Add bones
            for bone in model.skeleton:
                self._add_bone_to_tree(bone, model_item, model.id)

            self._bone_tree.addTopLevelItem(model_item)

            # Restore expansion state for this model item
            self._restore_expansion_state(model_item, expanded_items)

        # Expand model items that were previously expanded
        for i in range(self._bone_tree.topLevelItemCount()):
            item = self._bone_tree.topLevelItem(i)
            item_key = item.data(0, Qt.UserRole)
            if item_key in expanded_items:
                item.setExpanded(True)

    def _collect_expanded_items(self) -> set:
        """Collect all expanded item identifiers from the bone tree."""
        expanded = set()
        for i in range(self._bone_tree.topLevelItemCount()):
            self._collect_expanded_recursive(self._bone_tree.topLevelItem(i), expanded)
        return expanded

    def _collect_expanded_recursive(self, item: 'QTreeWidgetItem', expanded: set) -> None:
        """Recursively collect expanded items."""
        if item.isExpanded():
            expanded.add(item.data(0, Qt.UserRole))
        for i in range(item.childCount()):
            self._collect_expanded_recursive(item.child(i), expanded)

    def _restore_expansion_state(self, parent_item: 'QTreeWidgetItem', expanded: set) -> None:
        """Restore expansion state for child items."""
        for i in range(parent_item.childCount()):
            child = parent_item.child(i)
            child_key = child.data(0, Qt.UserRole)
            if child_key in expanded:
                child.setExpanded(True)
            self._restore_expansion_state(child, expanded)

    def _add_bone_to_tree(self, bone, parent_item, model_id: str) -> None:
        """Add a bone and its children to the tree."""
        item = QTreeWidgetItem([bone.name])
        item.setData(0, Qt.UserRole, f"bone:{model_id}:{bone.name}")
        parent_item.addChild(item)
        
        for child in bone.children:
            self._add_bone_to_tree(child, item, model_id)
    
    def _on_model_tree_click(self, item: QTreeWidgetItem, column: int) -> None:
        """Handle model tree click."""
        if not self._viewport:
            return
        
        model_id = item.data(0, Qt.UserRole)
        
        # Handle visibility checkbox
        if item.checkState(0) == Qt.Checked:
            self._viewport.set_model_visible(model_id, True)
        else:
            self._viewport.set_model_visible(model_id, False)
        
        self._viewport.select_model(model_id)
        self._rebuild_model_tree()
        self._rebuild_bone_tree()
    
    def _on_bone_tree_click(self, item: QTreeWidgetItem, column: int) -> None:
        """Handle bone tree click."""
        if not self._viewport:
            return
        
        data = item.data(0, Qt.UserRole)
        if data and data.startswith("bone:"):
            parts = data.split(":")
            model_id = parts[1]
            bone_name = parts[2]
            self._viewport.select_bone(model_id, bone_name)
            self._rebuild_bone_tree()
    
    def _on_model_selected(self, model_id: str) -> None:
        """Handle model selection from viewport."""
        self._rebuild_model_tree()
        self._rebuild_bone_tree()
    
    def _on_bone_selected(self, bone_name: str) -> None:
        """Handle bone selection from viewport."""
        self._rebuild_bone_tree()
        self._status_label.setText(f"Selected: {bone_name}")
    
    def _on_model_selection_changed(self, model_id: str) -> None:
        """Handle model selection change."""
        self._rebuild_model_tree()
        self._rebuild_bone_tree()
    
    # -------------------------------------------------------------------------
    # Visibility Controls
    # -------------------------------------------------------------------------
    
    def _on_toggle_mesh(self, checked: bool) -> None:
        if self._viewport:
            self._viewport.set_show_mesh(checked)
    
    def _on_toggle_skeleton(self, checked: bool) -> None:
        if self._viewport:
            self._viewport.set_show_skeleton(checked)
    
    def _on_toggle_joints(self, checked: bool) -> None:
        if self._viewport:
            self._viewport.set_show_joints(checked)
    
    def _on_toggle_gizmo(self, checked: bool) -> None:
        if self._viewport:
            self._viewport.set_show_gizmo(checked)
    
    # -------------------------------------------------------------------------
    # Gizmo Controls
    # -------------------------------------------------------------------------
    
    def _set_gizmo_mode(self, mode: str) -> None:
        """Set the gizmo mode."""
        if self._viewport:
            self._viewport.set_gizmo_mode(mode)
        
        # Update buttons
        self._rotation_btn.setChecked(mode == "rotation")
        self._movement_btn.setChecked(mode == "movement")
        self._scale_btn.setChecked(mode == "scale")
    
    def _toggle_gizmo_mode(self) -> None:
        """Toggle through gizmo modes."""
        if self._viewport:
            self._viewport.toggle_gizmo_mode()
            mode = self._viewport._gizmo_mode
            self._rotation_btn.setChecked(mode == "rotation")
            self._movement_btn.setChecked(mode == "movement")
            self._scale_btn.setChecked(mode == "scale")
    
    # -------------------------------------------------------------------------
    # Camera Controls
    # -------------------------------------------------------------------------
    
    def _on_reset_camera(self) -> None:
        """Reset camera to default position."""
        if self._viewport:
            self._viewport.reset_camera()
            self._viewport.frame_all()
    
    def _on_frame_model(self) -> None:
        """Frame all models in viewport."""
        if self._viewport:
            self._viewport.frame_all()
    
    def _set_camera_mode(self, mode: str) -> None:
        """Set camera mode (orbit/head_look)."""
        self._orbit_btn.setChecked(mode == "orbit")
        self._head_look_btn.setChecked(mode == "head_look")
        
        if self._viewport:
            self._viewport.set_head_look_mode(mode == "head_look")
    
    def _on_fov_slider_changed(self, value: int) -> None:
        """Handle FOV slider change."""
        self._fov_label.setText(f"{value}°")
        if self._viewport:
            self._viewport.set_fov(float(value))
    
    def _on_speed_slider_changed(self, value: int) -> None:
        """Handle speed slider change."""
        speed = value / 50.0  # 0.02 to 2.0
        self._speed_label.setText(f"{speed:.1f}x")
        if self._settings:
            self._settings.camera.set('keyboard_movement_speed', speed * 0.05)
    
    def _set_preset_view(self, view: str) -> None:
        """Set a preset camera view."""
        if not self._viewport:
            return
        
        camera = self._viewport._camera
        
        if view == "top":
            camera.yaw = 0
            camera.pitch = math.pi / 2 - 0.01
        elif view == "front":
            camera.yaw = 0
            camera.pitch = 0
        elif view == "side":
            camera.yaw = math.pi / 2
            camera.pitch = 0
        
        self._viewport.update()

    def _on_distance_gradient_toggle(self, checked: bool) -> None:
        """Handle distance gradient toggle button."""
        if self._viewport and hasattr(self._viewport, '_model_renderers'):
            renderers = self._viewport._model_renderers
            for model_id, renderer in renderers.items():
                renderer.set_distance_gradient_enabled(checked)
            self._viewport.update()
        else:
            logger.debug(f"[DEBUG] No viewport or no _model_renderers")

    def _on_distance_range_changed(self, value: int) -> None:
        """Handle distance range slider change."""
        distance = value / 100.0  # Convert to float (0.1 to 5.0)
        self._distance_range_value.setText(f"{distance:.1f}")
        if self._viewport and hasattr(self._viewport, '_model_renderers'):
            for model_id, renderer in self._viewport._model_renderers.items():
                renderer.set_distance_range(0.0, distance)
            self._viewport.update()

    # Floating camera panel removed - functionality moved to Camera tab

    def _on_camera_view_mode_changed(self, mode: str) -> None:
        """Handle camera panel view mode change."""
        self._set_camera_mode(mode)

    def _on_camera_fov_changed(self, fov: float) -> None:
        """Handle camera panel FOV change."""
        self._fov_slider.setValue(int(fov))
    
    # -------------------------------------------------------------------------
    # Pose Management
    # -------------------------------------------------------------------------
    
    def _on_load_pose(self) -> None:
        """Load a pose from file."""
        if not self._viewport:
            return
        
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Pose",
            "",
            "JSON Pose Files (*.json);;All Files (*)"
        )
        
        if file_path:
            self._apply_pose_file(file_path, self._viewport.get_selected_model())
    
    def _on_save_pose(self) -> None:
        """Save current pose to file."""
        if not self._viewport:
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Pose",
            "",
            "JSON Pose Files (*.json);;All Files (*)"
        )
        
        if file_path:
            # Add .json extension if not present
            if not file_path.endswith('.json'):
                file_path += '.json'
            model = self._viewport.get_selected_model()
            if model and PoseSerializer:
                try:
                    PoseSerializer.save_pose(file_path, model.skeleton)
                    self._refresh_pose_list()
                    self.statusBar().showMessage(f"Pose saved: {os.path.basename(file_path)}")
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Failed to save pose: {e}")
    
    def _on_apply_pose(self) -> None:
        """Apply selected pose from list."""
        if not self._viewport:
            return
        
        item = self._pose_list.currentItem()
        if item:
            file_path = item.data(Qt.UserRole)
            model = self._viewport.get_selected_model()
            if model:
                self._apply_pose_file(file_path, model)
    
    def _on_pose_double_clicked(self, item: QListWidgetItem) -> None:
        """Handle pose double-click."""
        self._on_apply_pose()
    
    def _apply_pose_file(self, file_path: str, model) -> None:
        """Apply a pose file to a model."""
        if model and PoseSerializer:
            try:
                PoseSerializer.load_pose(file_path, model.skeleton)
                self._rebuild_bone_tree()
                self._viewport.update()
                self.statusBar().showMessage(f"Applied pose: {os.path.basename(file_path)}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load pose: {e}")
    
    def _refresh_pose_list(self) -> None:
        """Refresh the pose list from the poses directory."""
        self._pose_list.clear()
        
        # Look for poses in the poses directory
        poses_dir = os.path.join(_parent_dir, "poses")
        if os.path.exists(poses_dir):
            for filename in os.listdir(poses_dir):
                if filename.endswith(".json"):
                    file_path = os.path.join(poses_dir, filename)
                    item = QListWidgetItem(os.path.splitext(filename)[0])
                    item.setData(Qt.UserRole, file_path)
                    self._pose_list.addItem(item)
    
    # -------------------------------------------------------------------------
    # Layer Sync
    # -------------------------------------------------------------------------

    def _on_sync_to_layer(self) -> None:
        """Sync current view to Krita layer."""
        if not KRITA_AVAILABLE:
            self.statusBar().showMessage("Sync only available inside Krita")
            QMessageBox.information(self, "Sync", "Layer sync is only available when running inside Krita.")
            return

        if not self._viewport:
            self.statusBar().showMessage("No viewport available")
            return

        self.statusBar().showMessage("Syncing to layer...")
        self._do_sync()

    def _do_sync(self) -> None:
        """Perform the actual sync to Krita layer."""
        if not KRITA_AVAILABLE or not self._viewport:
            return

        try:
            logger.debug("[SYNC] Starting layer sync process...")

            # Access Krita application
            app = Krita.instance()
            doc = app.activeDocument()

            if not doc:
                logger.debug("[SYNC] ERROR: No active document")
                self.statusBar().showMessage("No active document")
                return

            doc_w = doc.width()
            doc_h = doc.height()
            logger.debug(f"[SYNC] Document size: {doc_w}x{doc_h}")

            # Get the rendered image from viewport
            viewport_w = self._viewport.width()
            viewport_h = self._viewport.height()

            logger.debug(f"[SYNC] Viewport size: {viewport_w}x{viewport_h}")

            if viewport_w > 0 and viewport_h > 0:
                viewport_aspect = viewport_w / viewport_h
                doc_aspect = doc_w / doc_h

                logger.debug(f"[SYNC] Aspect ratios - viewport: {viewport_aspect:.3f}, document: {doc_aspect:.3f}")

                if viewport_aspect > doc_aspect:
                    # Viewport is wider - fit to doc height
                    render_h = doc_h
                    render_w = int(doc_h * viewport_aspect)
                    logger.debug(f"[SYNC] Fitting to document height: {render_w}x{render_h}")
                else:
                    # Doc is wider - fit to doc width
                    render_w = doc_w
                    render_h = int(doc_w / viewport_aspect)
                    logger.debug(f"[SYNC] Fitting to document width: {render_w}x{render_h}")
            else:
                render_w, render_h = doc_w, doc_h
                logger.debug(f"[SYNC] Using document size directly: {render_w}x{render_h}")

            logger.debug(f"[SYNC] Calling render_to_image({render_w}, {render_h})...")
            # Render the viewport scene to an image
            img = self._viewport.render_to_image(render_w, render_h)

            if img.isNull():
                logger.debug("[SYNC] ERROR: Render returned null image")
                self.statusBar().showMessage("Render failed - null image")
                return

            logger.debug(f"[SYNC] Render successful: {img.width()}x{img.height()}")

            logger.debug("[SYNC] Converting image format...")
            img = img.convertToFormat(QImage.Format_ARGB32)

            # Create document-sized image with proper centering if needed
            if render_w != doc_w or render_h != doc_h:
                logger.debug(f"[SYNC] Creating centered image {doc_w}x{doc_h} from {render_w}x{render_h}")
                final_img = QImage(doc_w, doc_h, QImage.Format_ARGB32)
                final_img.fill(QColor(0, 0, 0, 0))  # Transparent background

                # Calculate offset to center the rendered image
                offset_x = (doc_w - render_w) // 2
                offset_y = (doc_h - render_h) // 2
                logger.debug(f"[SYNC] Centering offset: ({offset_x}, {offset_y})")

                # Draw rendered image centered
                painter = QPainter(final_img)
                painter.drawImage(offset_x, offset_y, img)
                painter.end()

                img = final_img
                logger.debug("[SYNC] Centering complete")

            logger.debug("[SYNC] Finding or creating '3D View' layer...")
            # Find or create the "3D View" layer
            root = doc.rootNode()
            layer_name = "3D View"

            existing = None
            child_count = 0
            for child in root.childNodes():
                child_count += 1
                logger.debug(f"[SYNC] Checking layer: '{child.name()}'")
                if child.name() == layer_name:
                    existing = child
                    logger.debug(f"[SYNC] Found existing layer: '{layer_name}'")
                    break

            logger.debug(f"[SYNC] Total layers found: {child_count}")

            # Create or update layer
            if existing:
                logger.debug("[SYNC] Using existing layer")
                node = existing
            else:
                logger.debug(f"[SYNC] Creating new layer: '{layer_name}'")
                node = doc.createNode(layer_name, "paintlayer")
                root.addChildNode(node, None)
                logger.debug("[SYNC] Layer created and added to document")

            logger.debug(f"[SYNC] Setting pixel data ({img.byteCount()} bytes)...")
            # Set pixel data
            ptr = img.bits()
            ptr.setsize(img.byteCount())
            node.setPixelData(bytes(ptr), 0, 0, doc_w, doc_h)

            logger.debug("[SYNC] Refreshing document projection...")
            doc.refreshProjection()

            logger.debug(f"[SYNC] SUCCESS! Synced {doc_w}x{doc_h} to layer")
            self.statusBar().showMessage(f"Synced {doc_w}x{doc_h} to layer")

        except Exception as e:
            logger.debug(f"[SYNC] ERROR: Exception during sync: {e}")
            import traceback
            traceback.print_exc()
            self.statusBar().showMessage(f"Sync failed: {e}")
            QMessageBox.critical(self, "Sync Error", f"Failed to sync to layer: {e}")

    # -------------------------------------------------------------------------
    # Settings
    # -------------------------------------------------------------------------
    
    def _show_advanced_settings(self) -> None:
        """Show advanced settings dialog."""
        if AdvancedSettingsDialog and self._settings:
            dialog = AdvancedSettingsDialog(self._settings, self)
            dialog.settings_saved.connect(self._on_advanced_settings_saved)
            dialog.exec_()

    def _on_advanced_settings_saved(self) -> None:
        """Handle advanced settings saved."""
        if self._viewport and self._settings:
            self._viewport.set_settings(self._settings)

    # -------------------------------------------------------------------------
    # Camera Bookmarks
    # -------------------------------------------------------------------------

    def _on_bookmark_click(self, index: int) -> None:
        """Handle bookmark button click."""
        from PyQt5.QtWidgets import QApplication
        from PyQt5.QtCore import Qt
        if QApplication.keyboardModifiers() & Qt.ControlModifier:
            self._viewport._save_bookmark(index)
            self._update_bookmark_indicator(index, True)
        else:
            self._viewport._recall_bookmark(index)

    def _update_bookmark_indicator(self, index: int, has_bookmark: bool) -> None:
        """Update visual indicator for bookmark slot."""
        if 1 <= index <= 9 and hasattr(self, '_bookmark_buttons'):
            btn = self._bookmark_buttons[index - 1]
            if has_bookmark:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #2a4a6a;
                        border: 2px solid #4a8aca;
                    }
                """)
            else:
                btn.setStyleSheet("")

    def _on_import_bookmarks(self) -> None:
        """Handle import bookmarks button click."""
        from PyQt5.QtWidgets import QFileDialog, QMessageBox
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Import Camera Bookmarks",
            "",
            "JSON Files (*.json);;All Files (*)"
        )
        if not filepath:
            return

        if not self._viewport or not hasattr(self._viewport, '_bookmark_manager'):
            QMessageBox.warning(self, "Import Error", "No bookmark manager available.")
            return

        manager = self._viewport._bookmark_manager
        from pathlib import Path
        count = manager.import_from_file(Path(filepath))
        if count < 0:
            QMessageBox.warning(self, "Import Error", "Failed to import bookmarks from file.")
        else:
            # Update indicators
            for i in range(1, 10):
                self._update_bookmark_indicator(i, manager.has_bookmark(i))
            QMessageBox.information(self, "Import Successful", f"Imported {count} bookmark(s).")

    def _on_export_bookmarks(self) -> None:
        """Handle export bookmarks button click."""
        from PyQt5.QtWidgets import QFileDialog, QMessageBox
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Export Camera Bookmarks",
            "camera_bookmarks.json",
            "JSON Files (*.json);;All Files (*)"
        )
        if not filepath:
            return

        if not self._viewport or not hasattr(self._viewport, '_bookmark_manager'):
            QMessageBox.warning(self, "Export Error", "No bookmark manager available.")
            return

        manager = self._viewport._bookmark_manager
        from pathlib import Path
        if manager.export_to_file(Path(filepath)):
            QMessageBox.information(self, "Export Successful", f"Bookmarks exported to:\n{filepath}")
        else:
            QMessageBox.warning(self, "Export Error", "Failed to export bookmarks to file.")

    # -------------------------------------------------------------------------
    # Update Loop
    # -------------------------------------------------------------------------

    def _on_update(self) -> None:
        """Update timer callback."""
        # Viewport handles its own updates
        pass

    def closeEvent(self, event):
        """Handle window close - hide instead of close."""
        event.ignore()
        self.hide()


# Import math for camera calculations
import math

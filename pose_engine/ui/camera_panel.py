"""
Camera Panel - Floating Camera Controls
========================================

A floating panel for quick camera access that doesn't clutter the workspace.
Provides view mode toggle, FOV controls, movement speed, and bookmark management.
"""

from typing import Optional, TYPE_CHECKING

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QSlider, QGroupBox, QButtonGroup,
    QFrame, QSizePolicy, QSpacerItem, QFileDialog, QMessageBox
)
from PyQt5.QtCore import Qt, pyqtSignal, QSettings
from PyQt5.QtGui import QFont

from .styles import Colors, Typography

if TYPE_CHECKING:
    from .multi_viewport import MultiViewport3D


class CameraPanel(QWidget):
    """
    Floating panel for quick camera controls.

    Features:
    - View mode toggle (Orbit/Head Look)
    - FOV slider with presets
    - Movement speed controls
    - Bookmark grid (1-9 slots)
    - Quick action buttons

    Design Principles:
    - Compact by default
    - Draggable (handled by parent window)
    - Remember position between sessions
    - Non-modal - doesn't block viewport interaction
    - Keyboard-first - all actions have keyboard shortcuts
    """

    # Signals
    view_mode_changed = pyqtSignal(str) # 'orbit' or 'head_look'
    fov_changed = pyqtSignal(float)
    speed_changed = pyqtSignal(float)
    bookmark_requested = pyqtSignal(int) # slot number
    bookmark_save_requested = pyqtSignal(int) # slot number
    frame_model_requested = pyqtSignal()
    reset_camera_requested = pyqtSignal()
    bookmarks_imported = pyqtSignal() # emitted after successful import
    distance_gradient_toggled = pyqtSignal(bool) # enabled state

    # FOV presets
    FOV_PRESETS = [30, 45, 60, 90]
    FOV_MIN = 30
    FOV_MAX = 120

    # Speed presets
    SPEED_PRESETS = [
        ('Slow', 0.5),
        ('Normal', 1.0),
        ('Fast', 2.0),
    ]

    def __init__(self, viewport: 'MultiViewport3D', parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._viewport = viewport
        self._settings = QSettings('Krita3DPosePlugin', 'CameraPanel')
        self._bookmark_buttons = []
        self._speed_button_group = None

        self._setup_ui()
        self._connect_signals()
        self._restore_geometry()

    def _setup_ui(self):
        """Set up the panel UI."""
        self.setWindowTitle("Camera")
        # Use Tool window for floating panel behavior, but keep frame for native feel
        self.setWindowFlags(Qt.Tool | Qt.WindowTitleHint | Qt.WindowCloseButtonHint)
        self.setAttribute(Qt.WA_ShowWithoutActivating, False)  # Allow activation for better UX

        # Apply the main widget style from styles.py
        self.setStyleSheet(f"""
        QWidget {{
            background-color: {Colors.BACKGROUND};
            color: {Colors.TEXT_PRIMARY};
            font-size: 10px;
        }}
        QLabel {{
            color: {Colors.TEXT_PRIMARY};
            font-size: 10px;
        }}
        QPushButton {{
            background-color: {Colors.SURFACE};
            color: {Colors.TEXT_PRIMARY};
            border: 1px solid {Colors.SURFACE_LIGHT};
            border-radius: 4px;
            padding: 6px 10px;
            font-size: 10px;
            min-height: 20px;
        }}
        QPushButton:hover {{
            background-color: {Colors.SURFACE_LIGHT};
            border-color: {Colors.PRIMARY};
        }}
        QPushButton:pressed {{
            background-color: {Colors.PRIMARY_DARK};
        }}
        QPushButton:checked {{
            background-color: {Colors.PRIMARY};
            border-color: {Colors.PRIMARY_LIGHT};
            color: white;
        }}
        QSlider::groove:horizontal {{
            background: {Colors.SURFACE};
            height: 6px;
            border-radius: 3px;
        }}
        QSlider::handle:horizontal {{
            background: {Colors.PRIMARY};
            width: 16px;
            margin: -5px 0;
            border-radius: 8px;
        }}
        QSlider::handle:horizontal:hover {{
            background: {Colors.PRIMARY_LIGHT};
        }}
        QGroupBox {{
            color: {Colors.PRIMARY};
            font-size: 10px;
            font-weight: bold;
            border: 1px solid {Colors.SURFACE_LIGHT};
            border-radius: 4px;
            margin-top: 12px;
            padding-top: 8px;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 8px;
            padding: 0 4px;
        }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # View Mode Section
        layout.addWidget(self._create_view_mode_section())

        # FOV Section
        layout.addWidget(self._create_fov_section())

        # Movement Speed Section
        layout.addWidget(self._create_speed_section())

        # Bookmarks Section
        layout.addWidget(self._create_bookmarks_section())

        # Quick Actions Section
        layout.addWidget(self._create_quick_actions_section())

        # Visual Effects Section
        layout.addWidget(self._create_effects_section())

        # Size policy
        self.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)
        self.setMinimumWidth(200)
        self.setMaximumWidth(260)
        self.setMinimumHeight(100)

    def _create_view_mode_section(self) -> QGroupBox:
        """Create the view mode toggle section."""
        group = QGroupBox("View Mode")
        layout = QHBoxLayout(group)
        layout.setSpacing(4)

        self._orbit_btn = QPushButton("Orbit")
        self._orbit_btn.setCheckable(True)
        self._orbit_btn.setChecked(True)
        self._orbit_btn.setToolTip("Camera orbits around target (QWEASD moves target)")

        self._head_look_btn = QPushButton("Head Look")
        self._head_look_btn.setCheckable(True)
        self._head_look_btn.setToolTip("Camera rotates in place (QWEASD moves camera)")

        # Button group for mutual exclusion
        mode_group = QButtonGroup(self)
        mode_group.addButton(self._orbit_btn, 0)
        mode_group.addButton(self._head_look_btn, 1)
        mode_group.setExclusive(True)

        layout.addWidget(self._orbit_btn)
        layout.addWidget(self._head_look_btn)

        return group

    def _create_fov_section(self) -> QGroupBox:
        """Create the FOV control section."""
        group = QGroupBox("Field of View")
        layout = QVBoxLayout(group)
        layout.setSpacing(4)

        # Slider row
        slider_layout = QHBoxLayout()

        self._fov_slider = QSlider(Qt.Horizontal)
        self._fov_slider.setMinimum(self.FOV_MIN)
        self._fov_slider.setMaximum(self.FOV_MAX)
        self._fov_slider.setValue(45)
        self._fov_slider.setTickPosition(QSlider.TicksBelow)
        self._fov_slider.setTickInterval(15)

        self._fov_label = QLabel("45°")
        self._fov_label.setMinimumWidth(35)
        self._fov_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        slider_layout.addWidget(self._fov_slider, 1)
        slider_layout.addWidget(self._fov_label)
        layout.addLayout(slider_layout)

        # Preset buttons
        preset_layout = QHBoxLayout()
        preset_layout.setSpacing(4)

        for fov in self.FOV_PRESETS:
            btn = QPushButton(f"{fov}°")
            btn.setFixedWidth(40)
            btn.clicked.connect(lambda checked, f=fov: self._set_fov_preset(f))
            preset_layout.addWidget(btn)

        layout.addLayout(preset_layout)

        return group

    def _create_speed_section(self) -> QGroupBox:
        """Create the movement speed section."""
        group = QGroupBox("Movement Speed")
        layout = QVBoxLayout(group)
        layout.setSpacing(4)

        # Speed preset buttons
        speed_layout = QHBoxLayout()
        speed_layout.setSpacing(4)

        self._speed_button_group = QButtonGroup(self)
        self._speed_button_group.setExclusive(True)

        for i, (name, factor) in enumerate(self.SPEED_PRESETS):
            btn = QPushButton(name)
            btn.setCheckable(True)
            if i == 1:  # Default to Normal
                btn.setChecked(True)
            btn.clicked.connect(lambda checked, f=factor: self.speed_changed.emit(f))
            self._speed_button_group.addButton(btn, i)
            speed_layout.addWidget(btn)

        layout.addLayout(speed_layout)

        return group

    def _create_bookmarks_section(self) -> QGroupBox:
        """Create the bookmarks section."""
        group = QGroupBox("Bookmarks")
        layout = QVBoxLayout(group)
        layout.setSpacing(4)

        # Help text
        help_label = QLabel("Ctrl+1-9: Save | 1-9: Recall")
        help_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: 9px;")
        layout.addWidget(help_label)

        # Bookmark grid (3x3)
        grid = QGridLayout()
        grid.setSpacing(2)

        self._bookmark_buttons = []
        for i in range(1, 10):
            btn = QPushButton(str(i))
            btn.setFixedSize(28, 28)
            btn.setToolTip(f"Bookmark {i}\nClick to recall, Ctrl+Click to save")
            btn.clicked.connect(lambda checked, idx=i: self._on_bookmark_click(idx))
            row = (i - 1) // 3
            col = (i - 1) % 3
            grid.addWidget(btn, row, col)
            self._bookmark_buttons.append(btn)

        layout.addLayout(grid)

        # Import/Export buttons
        io_layout = QHBoxLayout()
        io_layout.setSpacing(4)

        import_btn = QPushButton("Import")
        import_btn.setToolTip("Import bookmarks from a JSON file")
        import_btn.clicked.connect(self._on_import_bookmarks)

        export_btn = QPushButton("Export")
        export_btn.setToolTip("Export bookmarks to a JSON file")
        export_btn.clicked.connect(self._on_export_bookmarks)

        io_layout.addWidget(import_btn)
        io_layout.addWidget(export_btn)
        layout.addLayout(io_layout)

        return group

    def _create_quick_actions_section(self) -> QGroupBox:
        """Create the quick actions section."""
        group = QGroupBox("Quick Actions")
        layout = QHBoxLayout(group)
        layout.setSpacing(4)

        frame_btn = QPushButton("Frame")
        frame_btn.setToolTip("Frame the model in view (F)")
        frame_btn.clicked.connect(lambda: self.frame_model_requested.emit())

        reset_btn = QPushButton("Reset")
        reset_btn.setToolTip("Reset camera to default position")
        reset_btn.clicked.connect(lambda: self.reset_camera_requested.emit())

        top_btn = QPushButton("Top")
        top_btn.setToolTip("View from top")
        top_btn.clicked.connect(lambda: self._set_preset_view('top'))

        front_btn = QPushButton("Front")
        front_btn.setToolTip("View from front")
        front_btn.clicked.connect(lambda: self._set_preset_view('front'))

        layout.addWidget(frame_btn)
        layout.addWidget(reset_btn)
        layout.addWidget(top_btn)
        layout.addWidget(front_btn)

        return group

    def _create_effects_section(self) -> QGroupBox:
        """Create the visual effects section."""
        group = QGroupBox("Visual Effects")
        layout = QVBoxLayout(group)
        layout.setSpacing(4)

        # Distance gradient toggle button
        self._distance_gradient_btn = QPushButton("Distance Gradient")
        self._distance_gradient_btn.setCheckable(True)
        self._distance_gradient_btn.setChecked(False)
        self._distance_gradient_btn.setToolTip(
            "Toggle distance-based color gradient overlay.\n"
            "Surfaces are tinted based on distance from camera:\n"
            "Near = Blue, Far = Magenta"
        )
        self._distance_gradient_btn.clicked.connect(self._on_distance_gradient_toggle)

        layout.addWidget(self._distance_gradient_btn)

        return group

    def _connect_signals(self):
        """Connect internal signals."""
        # View mode toggle
        self._orbit_btn.toggled.connect(lambda checked: self._on_view_mode_change('orbit', checked))
        self._head_look_btn.toggled.connect(lambda checked: self._on_view_mode_change('head_look', checked))

        # FOV slider
        self._fov_slider.valueChanged.connect(self._on_fov_slider_change)

        # Connect to viewport signals if available
        if self._viewport:
            self.view_mode_changed.connect(self._on_view_mode_set)
            self.fov_changed.connect(self._viewport.set_fov)
            self.frame_model_requested.connect(self._viewport.frame_model)
            self.reset_camera_requested.connect(self._viewport.reset_camera)
            self.bookmark_requested.connect(self._viewport._recall_bookmark)
            self.bookmark_save_requested.connect(self._viewport._save_bookmark)
            # Connect view mode to viewport's head_look_mode
            self.view_mode_changed.connect(self._on_view_mode_change_viewport)
            # Connect distance gradient toggle to viewport's renderer
            self.distance_gradient_toggled.connect(self._on_distance_gradient_change_viewport)

    def _restore_geometry(self):
        """Restore panel position from settings."""
        geometry = self._settings.value('geometry')
        if geometry:
            self.restoreGeometry(geometry)
        else:
            # Default position (top-right of parent)
            if self.parent():
                parent_rect = self.parent().rect()
                self.move(parent_rect.right() - 300, parent_rect.top() + 50)

    def _save_geometry(self):
        """Save panel position to settings."""
        self._settings.setValue('geometry', self.saveGeometry())

    # -------------------------------------------------------------------------
    # Event Handlers
    # -------------------------------------------------------------------------

    def closeEvent(self, event):
        """Save geometry before closing."""
        self._save_geometry()
        super().closeEvent(event)

    def hideEvent(self, event):
        """Save geometry when hidden."""
        self._save_geometry()
        super().hideEvent(event)

    def mousePressEvent(self, event):
        """Allow dragging the panel."""
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        """Handle panel dragging."""
        if event.buttons() == Qt.LeftButton and hasattr(self, '_drag_pos'):
            self.move(event.globalPos() - self._drag_pos)
            event.accept()

    # -------------------------------------------------------------------------
    # Private Slots
    # -------------------------------------------------------------------------

    def _on_view_mode_change(self, mode: str, checked: bool):
        """Handle view mode button toggle."""
        if checked:
            self.view_mode_changed.emit(mode)

    def _on_view_mode_set(self, mode: str):
        """Set view mode from external source."""
        if mode == 'orbit':
            self._orbit_btn.setChecked(True)
        elif mode == 'head_look':
            self._head_look_btn.setChecked(True)

    def _on_view_mode_change_viewport(self, mode: str):
        """Set viewport's head-look mode when view mode changes."""
        if self._viewport and hasattr(self._viewport, 'set_head_look_mode'):
            self._viewport.set_head_look_mode(mode == 'head_look')

    def _on_distance_gradient_change_viewport(self, enabled: bool):
        """Set viewport's renderer distance gradient mode."""
        if self._viewport and hasattr(self._viewport, '_renderer') and self._viewport._renderer:
            self._viewport._renderer.set_distance_gradient_enabled(enabled)
            self._viewport.update()

    def _on_fov_slider_change(self, value: int):
        """Handle FOV slider change."""
        self._fov_label.setText(f"{value}°")
        self.fov_changed.emit(float(value))

    def _set_fov_preset(self, fov: int):
        """Set FOV to a preset value."""
        self._fov_slider.setValue(fov)

    def _on_bookmark_click(self, index: int):
        """Handle bookmark button click."""
        # Check if Ctrl is pressed for save
        modifiers = self._viewport._head_look_mode  # Simplified check
        # Use keyboard modifiers
        from PyQt5.QtWidgets import QApplication
        if QApplication.keyboardModifiers() & Qt.ControlModifier:
            self.bookmark_save_requested.emit(index)
        else:
            self.bookmark_requested.emit(index)

    def _set_preset_view(self, view: str):
        """Set a preset camera view."""
        if not self._viewport:
            return

        camera = self._viewport._camera

        if view == 'top':
            camera._yaw = 0.0
            camera._pitch = -89.9  # Almost straight down
            camera._distance = 5.0
        elif view == 'front':
            camera._yaw = 0.0
            camera._pitch = 0.0
            camera._distance = 5.0
        elif view == 'side':
            camera._yaw = 90.0
            camera._pitch = 0.0
            camera._distance = 5.0

        self._viewport.update()

    def _on_distance_gradient_toggle(self, checked: bool):
        """Handle distance gradient toggle button."""
        self.distance_gradient_toggled.emit(checked)
        if self._viewport:
            self._viewport.update()

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def set_fov(self, fov: float):
        """Set FOV from external source."""
        self._fov_slider.setValue(int(fov))

    def set_view_mode(self, mode: str):
        """Set view mode from external source."""
        self._on_view_mode_set(mode)

    def update_bookmark_indicator(self, index: int, has_bookmark: bool):
        """Update visual indicator for bookmark slot."""
        if 1 <= index <= 9:
            btn = self._bookmark_buttons[index - 1]
            if has_bookmark:
                btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {Colors.PRIMARY_DARK};
                    border: 2px solid {Colors.PRIMARY};
                }}
                """)
            else:
                btn.setStyleSheet("")

    def _on_import_bookmarks(self):
        """Handle import bookmarks button click."""
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Import Camera Bookmarks",
            "",
            "JSON Files (*.json);;All Files (*)"
        )
        if not filepath:
            return

        # Get bookmark manager from viewport
        if not self._viewport or not hasattr(self._viewport, '_bookmark_manager'):
            QMessageBox.warning(self, "Import Error", "No bookmark manager available.")
            return

        manager = self._viewport._bookmark_manager
        from pathlib import Path
        count = manager.import_from_file(Path(filepath), merge=True)

        if count < 0:
            QMessageBox.warning(self, "Import Error", "Failed to import bookmarks from file.")
        else:
            # Update indicators for all slots
            for i in range(1, 10):
                self.update_bookmark_indicator(i, manager.has_bookmark(i))
            self.bookmarks_imported.emit()
            QMessageBox.information(
                self,
                "Import Successful",
                f"Imported {count} bookmark(s)."
            )

    def _on_export_bookmarks(self):
        """Handle export bookmarks button click."""
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Export Camera Bookmarks",
            "camera_bookmarks.json",
            "JSON Files (*.json);;All Files (*)"
        )
        if not filepath:
            return

        # Get bookmark manager from viewport
        if not self._viewport or not hasattr(self._viewport, '_bookmark_manager'):
            QMessageBox.warning(self, "Export Error", "No bookmark manager available.")
            return

        manager = self._viewport._bookmark_manager
        from pathlib import Path
        success = manager.export_to_file(Path(filepath))

        if success:
            QMessageBox.information(
                self,
                "Export Successful",
                f"Bookmarks exported to:\n{filepath}"
            )
        else:
            QMessageBox.warning(self, "Export Error", "Failed to export bookmarks to file.")

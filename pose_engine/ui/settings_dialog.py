"""
Advanced Settings Dialog - Full Settings Configuration
======================================================

Provides a comprehensive settings dialog with categorized settings
and an interactive key binding editor.
"""

from typing import Optional, Dict, List

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QGroupBox, QLabel, QPushButton, QSlider, QSpinBox,
    QDoubleSpinBox, QComboBox, QCheckBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView,
    QFrame, QScrollArea, QGridLayout, QMessageBox,
    QKeySequenceEdit, QSplitter, QListWidget, QListWidgetItem,
    QSizePolicy, QSpacerItem
)
from PyQt5.QtCore import Qt, pyqtSignal, QEvent
from PyQt5.QtGui import QKeyEvent, QFont, QColor

from ..settings import PluginSettings, KeyBinding, MouseBinding
from ..settings.defaults import (
    KEYBOARD_ACTION_NAMES,
    GIZMO_COLOR_SCHEMES,
    UI_THEMES,
    SETTINGS_CATEGORIES,
)


class KeyBindingEditor(QDialog):
    """
    Dialog for editing a single key binding with interactive key capture.
    
    Allows users to press a key combination to set the binding.
    """
    
    def __init__(self, action: str, current_binding: Optional[KeyBinding], parent=None):
        super().__init__(parent)
        self._action = action
        self._current_binding = current_binding or KeyBinding(0, 0, action)
        self._result_binding: Optional[KeyBinding] = None
        
        self.setWindowTitle(f"Edit Key Binding")
        self.setMinimumWidth(350)
        self.setModal(True)
        
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        # Action label
        action_label = QLabel(f"Action: {KEYBOARD_ACTION_NAMES.get(self._action, self._action)}")
        action_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(action_label)
        
        # Current binding display
        current_layout = QHBoxLayout()
        current_layout.addWidget(QLabel("Current:"))
        self._current_label = QLabel(str(self._current_binding) if self._current_binding.key else "None")
        self._current_label.setStyleSheet("font-weight: bold; color: #3498DB;")
        current_layout.addWidget(self._current_label)
        current_layout.addStretch()
        layout.addLayout(current_layout)
        
        # Key capture area
        capture_group = QGroupBox("Press new key combination")
        capture_group.setStyleSheet("""
            QGroupBox {
                border: 2px dashed #4A6572;
                border-radius: 8px;
                margin-top: 12px;
                padding: 20px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        capture_layout = QVBoxLayout(capture_group)
        
        self._key_display = QLabel("Press any key...")
        self._key_display.setAlignment(Qt.AlignCenter)
        self._key_display.setStyleSheet("""
            font-size: 24px;
            font-weight: bold;
            color: #BDC3C7;
            padding: 30px;
        """)
        capture_layout.addWidget(self._key_display)
        
        layout.addWidget(capture_group)
        
        # Modifier checkboxes
        mod_group = QGroupBox("Modifiers")
        mod_layout = QHBoxLayout(mod_group)
        
        self._ctrl_cb = QCheckBox("Ctrl")
        self._ctrl_cb.setChecked(bool(self._current_binding.modifiers & Qt.ControlModifier))
        self._ctrl_cb.toggled.connect(self._update_preview)
        mod_layout.addWidget(self._ctrl_cb)
        
        self._shift_cb = QCheckBox("Shift")
        self._shift_cb.setChecked(bool(self._current_binding.modifiers & Qt.ShiftModifier))
        self._shift_cb.toggled.connect(self._update_preview)
        mod_layout.addWidget(self._shift_cb)
        
        self._alt_cb = QCheckBox("Alt")
        self._alt_cb.setChecked(bool(self._current_binding.modifiers & Qt.AltModifier))
        self._alt_cb.toggled.connect(self._update_preview)
        mod_layout.addWidget(self._alt_cb)
        
        layout.addWidget(mod_group)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self._clear_binding)
        btn_layout.addWidget(clear_btn)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        ok_btn = QPushButton("OK")
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self._accept_binding)
        btn_layout.addWidget(ok_btn)
        
        layout.addLayout(btn_layout)
        
        # Store initial key
        self._captured_key = self._current_binding.key
        if self._captured_key:
            self._update_preview()
    
    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Handle key press for capturing."""
        key = event.key()
        modifiers = event.modifiers()
        
        # Ignore modifier-only presses
        if key in (Qt.Key_Control, Qt.Key_Shift, Qt.Key_Alt, Qt.Key_Meta):
            # Update modifier checkboxes
            self._ctrl_cb.setChecked(bool(modifiers & Qt.ControlModifier))
            self._shift_cb.setChecked(bool(modifiers & Qt.ShiftModifier))
            self._alt_cb.setChecked(bool(modifiers & Qt.AltModifier))
            return
        
        # Store the captured key
        self._captured_key = key
        
        # Update modifier checkboxes based on event
        self._ctrl_cb.setChecked(bool(modifiers & Qt.ControlModifier))
        self._shift_cb.setChecked(bool(modifiers & Qt.ShiftModifier))
        self._alt_cb.setChecked(bool(modifiers & Qt.AltModifier))
        
        self._update_preview()
    
    def _update_preview(self) -> None:
        """Update the key display preview."""
        if not self._captured_key:
            self._key_display.setText("Press any key...")
            self._key_display.setStyleSheet("""
                font-size: 24px;
                font-weight: bold;
                color: #BDC3C7;
                padding: 30px;
            """)
            return
        
        # Build modifier string
        modifiers = self._get_modifiers()
        temp_binding = KeyBinding(self._captured_key, modifiers, self._action)
        
        self._key_display.setText(temp_binding.get_display_string())
        self._key_display.setStyleSheet("""
            font-size: 24px;
            font-weight: bold;
            color: #3498DB;
            padding: 30px;
        """)
    
    def _get_modifiers(self) -> int:
        """Get the current modifiers from checkboxes."""
        modifiers = Qt.NoModifier
        if self._ctrl_cb.isChecked():
            modifiers |= Qt.ControlModifier
        if self._shift_cb.isChecked():
            modifiers |= Qt.ShiftModifier
        if self._alt_cb.isChecked():
            modifiers |= Qt.AltModifier
        return modifiers
    
    def _clear_binding(self) -> None:
        """Clear the current binding."""
        self._captured_key = 0
        self._ctrl_cb.setChecked(False)
        self._shift_cb.setChecked(False)
        self._alt_cb.setChecked(False)
        self._update_preview()
    
    def _accept_binding(self) -> None:
        """Accept the current binding."""
        self._result_binding = KeyBinding(
            self._captured_key,
            self._get_modifiers(),
            self._action
        )
        self.accept()
    
    def get_binding(self) -> Optional[KeyBinding]:
        """Get the resulting key binding."""
        return self._result_binding


class KeyboardSettingsWidget(QWidget):
    """Widget for editing keyboard shortcuts."""
    
    bindings_changed = pyqtSignal()
    
    def __init__(self, settings: PluginSettings, parent=None):
        super().__init__(parent)
        self._settings = settings
        self._setup_ui()
        self._load_bindings()
    
    def _setup_ui(self) -> None:
        """Set up the UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Instructions
        instructions = QLabel("Double-click a row to edit the key binding")
        instructions.setStyleSheet("color: #BDC3C7; font-style: italic;")
        layout.addWidget(instructions)
        
        # Key bindings table
        self._table = QTableWidget()
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels(["Action", "Key", "Modifiers", ""])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self._table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._table.setAlternatingRowColors(True)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.doubleClicked.connect(self._on_double_click)
        self._table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #4A6572;
                gridline-color: #4A6572;
            }
            QTableWidget::item {
                padding: 5px;
            }
            QHeaderView::section {
                background-color: #34495E;
                padding: 5px;
                border: 1px solid #4A6572;
            }
        """)
        layout.addWidget(self._table)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.clicked.connect(self._reset_to_defaults)
        btn_layout.addWidget(reset_btn)
        
        btn_layout.addStretch()
        
        check_btn = QPushButton("Check Conflicts")
        check_btn.clicked.connect(self._check_conflicts)
        btn_layout.addWidget(check_btn)
        
        layout.addLayout(btn_layout)
    
    def _load_bindings(self) -> None:
        """Load bindings into the table."""
        bindings = self._settings.keyboard.get_all_bindings()
        self._table.setRowCount(len(bindings))
        
        for row, (action, binding) in enumerate(bindings.items()):
            # Action name
            action_item = QTableWidgetItem(KEYBOARD_ACTION_NAMES.get(action, action))
            action_item.setData(Qt.UserRole, action)
            self._table.setItem(row, 0, action_item)
            
            # Key
            key_item = QTableWidgetItem(binding.get_key_name())
            self._table.setItem(row, 1, key_item)
            
            # Modifiers
            mod_names = binding.get_modifier_names()
            mod_item = QTableWidgetItem('+'.join(mod_names) if mod_names else "None")
            self._table.setItem(row, 2, mod_item)
            
            # Edit button
            edit_btn = QPushButton("Edit")
            edit_btn.setStyleSheet("padding: 4px 8px;")
            edit_btn.clicked.connect(lambda checked, a=action: self._edit_binding(a))
            self._table.setCellWidget(row, 3, edit_btn)
    
    def _on_double_click(self, index) -> None:
        """Handle double-click on table row."""
        row = index.row()
        action_item = self._table.item(row, 0)
        if action_item:
            action = action_item.data(Qt.UserRole)
            self._edit_binding(action)
    
    def _edit_binding(self, action: str) -> None:
        """Open the key binding editor for an action."""
        current = self._settings.keyboard.get_binding(action)
        
        editor = KeyBindingEditor(action, current, self)
        if editor.exec_() == QDialog.Accepted:
            new_binding = editor.get_binding()
            if new_binding:
                self._settings.keyboard.set_binding_from_keybinding(action, new_binding)
                self._load_bindings()
                self.bindings_changed.emit()
    
    def _reset_to_defaults(self) -> None:
        """Reset all key bindings to defaults."""
        reply = QMessageBox.question(
            self, "Reset Key Bindings",
            "Are you sure you want to reset all key bindings to defaults?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self._settings.keyboard.reset_to_defaults()
            self._load_bindings()
            self.bindings_changed.emit()
    
    def _check_conflicts(self) -> None:
        """Check for key binding conflicts."""
        conflicts = self._settings.keyboard.find_conflicts()
        
        if not conflicts:
            QMessageBox.information(self, "No Conflicts", "No key binding conflicts found.")
            return
        
        # Build conflict message
        msg_lines = ["The following key bindings conflict:"]
        for action1, action2, binding in conflicts:
            msg_lines.append(f"\n• {KEYBOARD_ACTION_NAMES.get(action1, action1)}")
            msg_lines.append(f"  and {KEYBOARD_ACTION_NAMES.get(action2, action2)}")
            msg_lines.append(f"  both use: {binding.get_display_string()}")
        
        QMessageBox.warning(self, "Key Binding Conflicts", '\n'.join(msg_lines))


class MouseSettingsWidget(QWidget):
    """Widget for editing mouse settings."""
    
    settings_changed = pyqtSignal()
    
    def __init__(self, settings: PluginSettings, parent=None):
        super().__init__(parent)
        self._settings = settings
        self._setup_ui()
        self._load_settings()
    
    def _setup_ui(self) -> None:
        """Set up the UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Sensitivity settings
        sens_group = QGroupBox("Sensitivity")
        sens_layout = QGridLayout(sens_group)
        
        # Rotate sensitivity
        sens_layout.addWidget(QLabel("Rotate:"), 0, 0)
        self._rotate_sens = QDoubleSpinBox()
        self._rotate_sens.setRange(0.1, 5.0)
        self._rotate_sens.setSingleStep(0.1)
        self._rotate_sens.valueChanged.connect(self._on_sensitivity_changed)
        sens_layout.addWidget(self._rotate_sens, 0, 1)
        
        # Pan sensitivity
        sens_layout.addWidget(QLabel("Pan:"), 1, 0)
        self._pan_sens = QDoubleSpinBox()
        self._pan_sens.setRange(0.1, 5.0)
        self._pan_sens.setSingleStep(0.1)
        self._pan_sens.valueChanged.connect(self._on_sensitivity_changed)
        sens_layout.addWidget(self._pan_sens, 1, 1)
        
        # Zoom sensitivity
        sens_layout.addWidget(QLabel("Zoom:"), 2, 0)
        self._zoom_sens = QDoubleSpinBox()
        self._zoom_sens.setRange(0.1, 5.0)
        self._zoom_sens.setSingleStep(0.1)
        self._zoom_sens.valueChanged.connect(self._on_sensitivity_changed)
        sens_layout.addWidget(self._zoom_sens, 2, 1)
        
        layout.addWidget(sens_group)
        
        # Scroll wheel settings
        scroll_group = QGroupBox("Scroll Wheel")
        scroll_layout = QGridLayout(scroll_group)
        
        scroll_layout.addWidget(QLabel("Zoom Speed:"), 0, 0)
        self._scroll_zoom = QDoubleSpinBox()
        self._scroll_zoom.setRange(0.01, 0.5)
        self._scroll_zoom.setSingleStep(0.01)
        self._scroll_zoom.setDecimals(2)
        self._scroll_zoom.valueChanged.connect(self._on_setting_changed)
        scroll_layout.addWidget(self._scroll_zoom, 0, 1)
        
        scroll_layout.addWidget(QLabel("Dolly Speed:"), 1, 0)
        self._scroll_dolly = QDoubleSpinBox()
        self._scroll_dolly.setRange(0.01, 0.5)
        self._scroll_dolly.setSingleStep(0.01)
        self._scroll_dolly.setDecimals(2)
        self._scroll_dolly.valueChanged.connect(self._on_setting_changed)
        scroll_layout.addWidget(self._scroll_dolly, 1, 1)
        
        layout.addWidget(scroll_group)
        
        # Reset button
        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.clicked.connect(self._reset_to_defaults)
        layout.addWidget(reset_btn)
        
        layout.addStretch()
    
    def _load_settings(self) -> None:
        """Load current settings."""
        self._rotate_sens.setValue(self._settings.mouse.get_sensitivity('rotate'))
        self._pan_sens.setValue(self._settings.mouse.get_sensitivity('pan'))
        self._zoom_sens.setValue(self._settings.mouse.get_sensitivity('zoom'))
        self._scroll_zoom.setValue(self._settings.mouse.get_scroll_zoom_speed())
        self._scroll_dolly.setValue(self._settings.mouse.get_scroll_dolly_speed())
    
    def _on_sensitivity_changed(self) -> None:
        """Handle sensitivity changes."""
        self._settings.mouse.set_sensitivity('rotate', self._rotate_sens.value())
        self._settings.mouse.set_sensitivity('pan', self._pan_sens.value())
        self._settings.mouse.set_sensitivity('zoom', self._zoom_sens.value())
        self.settings_changed.emit()
    
    def _on_setting_changed(self) -> None:
        """Handle other setting changes."""
        # Settings are updated directly via valueChanged signals
        self.settings_changed.emit()
    
    def _reset_to_defaults(self) -> None:
        """Reset to defaults."""
        self._settings.mouse.reset_to_defaults()
        self._load_settings()
        self.settings_changed.emit()


class GizmoSettingsWidget(QWidget):
    """Widget for editing gizmo settings."""
    
    settings_changed = pyqtSignal()
    
    def __init__(self, settings: PluginSettings, parent=None):
        super().__init__(parent)
        self._settings = settings
        self._setup_ui()
        self._load_settings()
    
    def _setup_ui(self) -> None:
        """Set up the UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Scale settings
        scale_group = QGroupBox("Scale")
        scale_layout = QGridLayout(scale_group)
        
        scale_layout.addWidget(QLabel("Base Scale:"), 0, 0)
        self._base_scale = QDoubleSpinBox()
        self._base_scale.setRange(0.1, 1.0)
        self._base_scale.setSingleStep(0.05)
        self._base_scale.valueChanged.connect(self._on_setting_changed)
        scale_layout.addWidget(self._base_scale, 0, 1)
        
        scale_layout.addWidget(QLabel("Min Scale:"), 1, 0)
        self._min_scale = QDoubleSpinBox()
        self._min_scale.setRange(0.01, 0.5)
        self._min_scale.setSingleStep(0.01)
        self._min_scale.setDecimals(2)
        self._min_scale.valueChanged.connect(self._on_setting_changed)
        scale_layout.addWidget(self._min_scale, 1, 1)
        
        scale_layout.addWidget(QLabel("Max Scale:"), 2, 0)
        self._max_scale = QDoubleSpinBox()
        self._max_scale.setRange(0.5, 5.0)
        self._max_scale.setSingleStep(0.1)
        self._max_scale.valueChanged.connect(self._on_setting_changed)
        scale_layout.addWidget(self._max_scale, 2, 1)
        
        layout.addWidget(scale_group)
        
        # Sensitivity settings
        sens_group = QGroupBox("Sensitivity")
        sens_layout = QGridLayout(sens_group)
        
        sens_layout.addWidget(QLabel("Rotation:"), 0, 0)
        self._rot_sens = QDoubleSpinBox()
        self._rot_sens.setRange(0.1, 5.0)
        self._rot_sens.setSingleStep(0.1)
        self._rot_sens.valueChanged.connect(self._on_setting_changed)
        sens_layout.addWidget(self._rot_sens, 0, 1)
        
        sens_layout.addWidget(QLabel("Movement:"), 1, 0)
        self._move_sens = QDoubleSpinBox()
        self._move_sens.setRange(0.1, 5.0)
        self._move_sens.setSingleStep(0.1)
        self._move_sens.valueChanged.connect(self._on_setting_changed)
        sens_layout.addWidget(self._move_sens, 1, 1)
        
        sens_layout.addWidget(QLabel("Scale:"), 2, 0)
        self._scale_sens = QDoubleSpinBox()
        self._scale_sens.setRange(0.1, 5.0)
        self._scale_sens.setSingleStep(0.1)
        self._scale_sens.valueChanged.connect(self._on_setting_changed)
        sens_layout.addWidget(self._scale_sens, 2, 1)
        
        layout.addWidget(sens_group)
        
        # Color scheme
        color_group = QGroupBox("Color Scheme")
        color_layout = QHBoxLayout(color_group)
        
        self._color_scheme = QComboBox()
        self._color_scheme.addItems(list(GIZMO_COLOR_SCHEMES.keys()))
        self._color_scheme.currentTextChanged.connect(self._on_setting_changed)
        color_layout.addWidget(self._color_scheme)
        
        layout.addWidget(color_group)
        
        # Reset button
        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.clicked.connect(self._reset_to_defaults)
        layout.addWidget(reset_btn)
        
        layout.addStretch()
    
    def _load_settings(self) -> None:
        """Load current settings."""
        self._base_scale.setValue(self._settings.gizmo.get('base_scale', 0.2))
        self._min_scale.setValue(self._settings.gizmo.get('min_scale', 0.05))
        self._max_scale.setValue(self._settings.gizmo.get('max_scale', 2.0))
        self._rot_sens.setValue(self._settings.gizmo.get('rotation_sensitivity', 1.0))
        self._move_sens.setValue(self._settings.gizmo.get('movement_sensitivity', 1.0))
        self._scale_sens.setValue(self._settings.gizmo.get('scale_sensitivity', 1.0))
        
        scheme = self._settings.gizmo.get('color_scheme', 'blender')
        index = self._color_scheme.findText(scheme)
        if index >= 0:
            self._color_scheme.setCurrentIndex(index)
    
    def _on_setting_changed(self) -> None:
        """Handle setting changes."""
        self._settings.gizmo.set('base_scale', self._base_scale.value())
        self._settings.gizmo.set('min_scale', self._min_scale.value())
        self._settings.gizmo.set('max_scale', self._max_scale.value())
        self._settings.gizmo.set('rotation_sensitivity', self._rot_sens.value())
        self._settings.gizmo.set('movement_sensitivity', self._move_sens.value())
        self._settings.gizmo.set('scale_sensitivity', self._scale_sens.value())
        self._settings.gizmo.set('color_scheme', self._color_scheme.currentText())
        self.settings_changed.emit()
    
    def _reset_to_defaults(self) -> None:
        """Reset to defaults."""
        self._settings.gizmo.reset_to_defaults()
        self._load_settings()
        self.settings_changed.emit()


class CameraSettingsWidget(QWidget):
    """Widget for editing camera settings."""

    settings_changed = pyqtSignal()

    def __init__(self, settings: PluginSettings, parent=None):
        super().__init__(parent)
        self._settings = settings
        self._setup_ui()
        self._load_settings()

    def _setup_ui(self) -> None:
        """Set up the UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # FOV settings
        fov_group = QGroupBox("Field of View")
        fov_layout = QGridLayout(fov_group)

        fov_layout.addWidget(QLabel("Default FOV:"), 0, 0)
        self._default_fov = QSpinBox()
        self._default_fov.setRange(30, 120)
        self._default_fov.valueChanged.connect(self._on_setting_changed)
        fov_layout.addWidget(self._default_fov, 0, 1)

        fov_layout.addWidget(QLabel("Min FOV:"), 1, 0)
        self._min_fov = QSpinBox()
        self._min_fov.setRange(10, 60)
        self._min_fov.valueChanged.connect(self._on_setting_changed)
        fov_layout.addWidget(self._min_fov, 1, 1)

        fov_layout.addWidget(QLabel("Max FOV:"), 2, 0)
        self._max_fov = QSpinBox()
        self._max_fov.setRange(60, 150)
        self._max_fov.valueChanged.connect(self._on_setting_changed)
        fov_layout.addWidget(self._max_fov, 2, 1)

        layout.addWidget(fov_group)

        # Distance settings
        dist_group = QGroupBox("Distance Limits")
        dist_layout = QGridLayout(dist_group)

        dist_layout.addWidget(QLabel("Default Distance:"), 0, 0)
        self._default_dist = QDoubleSpinBox()
        self._default_dist.setRange(0.5, 20.0)
        self._default_dist.setSingleStep(0.5)
        self._default_dist.valueChanged.connect(self._on_setting_changed)
        dist_layout.addWidget(self._default_dist, 0, 1)

        dist_layout.addWidget(QLabel("Min Distance:"), 1, 0)
        self._min_dist = QDoubleSpinBox()
        self._min_dist.setRange(0.1, 2.0)
        self._min_dist.setSingleStep(0.1)
        self._min_dist.valueChanged.connect(self._on_setting_changed)
        dist_layout.addWidget(self._min_dist, 1, 1)

        dist_layout.addWidget(QLabel("Max Distance:"), 2, 0)
        self._max_dist = QDoubleSpinBox()
        self._max_dist.setRange(5.0, 100.0)
        self._max_dist.setSingleStep(5.0)
        self._max_dist.valueChanged.connect(self._on_setting_changed)
        dist_layout.addWidget(self._max_dist, 2, 1)

        layout.addWidget(dist_group)

        # Speed settings
        speed_group = QGroupBox("Movement Speeds")
        speed_layout = QGridLayout(speed_group)

        speed_layout.addWidget(QLabel("Rotation:"), 0, 0)
        self._rot_speed = QDoubleSpinBox()
        self._rot_speed.setRange(0.001, 0.1)
        self._rot_speed.setSingleStep(0.001)
        self._rot_speed.setDecimals(3)
        self._rot_speed.valueChanged.connect(self._on_setting_changed)
        speed_layout.addWidget(self._rot_speed, 0, 1)

        speed_layout.addWidget(QLabel("Zoom:"), 1, 0)
        self._zoom_speed = QDoubleSpinBox()
        self._zoom_speed.setRange(0.01, 0.5)
        self._zoom_speed.setSingleStep(0.01)
        self._zoom_speed.setDecimals(2)
        self._zoom_speed.valueChanged.connect(self._on_setting_changed)
        speed_layout.addWidget(self._zoom_speed, 1, 1)

        speed_layout.addWidget(QLabel("Pan:"), 2, 0)
        self._pan_speed = QDoubleSpinBox()
        self._pan_speed.setRange(0.0001, 0.01)
        self._pan_speed.setSingleStep(0.0001)
        self._pan_speed.setDecimals(4)
        self._pan_speed.valueChanged.connect(self._on_setting_changed)
        speed_layout.addWidget(self._pan_speed, 2, 1)

        layout.addWidget(speed_group)

        # Keyboard movement settings
        keyboard_group = QGroupBox("Keyboard Movement (QWEASD)")
        keyboard_layout = QGridLayout(keyboard_group)

        keyboard_layout.addWidget(QLabel("Base Speed:"), 0, 0)
        self._keyboard_speed = QDoubleSpinBox()
        self._keyboard_speed.setRange(0.01, 0.5)
        self._keyboard_speed.setSingleStep(0.01)
        self._keyboard_speed.setDecimals(2)
        self._keyboard_speed.valueChanged.connect(self._on_setting_changed)
        keyboard_layout.addWidget(self._keyboard_speed, 0, 1)

        keyboard_layout.addWidget(QLabel("Slow (Shift):"), 1, 0)
        self._keyboard_speed_slow = QDoubleSpinBox()
        self._keyboard_speed_slow.setRange(0.005, 0.2)
        self._keyboard_speed_slow.setSingleStep(0.005)
        self._keyboard_speed_slow.setDecimals(3)
        self._keyboard_speed_slow.valueChanged.connect(self._on_setting_changed)
        keyboard_layout.addWidget(self._keyboard_speed_slow, 1, 1)

        keyboard_layout.addWidget(QLabel("Fast (Ctrl):"), 2, 0)
        self._keyboard_speed_fast = QDoubleSpinBox()
        self._keyboard_speed_fast.setRange(0.05, 1.0)
        self._keyboard_speed_fast.setSingleStep(0.05)
        self._keyboard_speed_fast.setDecimals(2)
        self._keyboard_speed_fast.valueChanged.connect(self._on_setting_changed)
        keyboard_layout.addWidget(self._keyboard_speed_fast, 2, 1)

        layout.addWidget(keyboard_group)

        # Behavior settings
        behavior_group = QGroupBox("Behavior")
        behavior_layout = QVBoxLayout(behavior_group)

        self._target_on_select = QCheckBox("Auto-target selected bone")
        self._target_on_select.toggled.connect(self._on_setting_changed)
        behavior_layout.addWidget(self._target_on_select)

        self._smooth_transitions = QCheckBox("Smooth camera transitions")
        self._smooth_transitions.toggled.connect(self._on_setting_changed)
        behavior_layout.addWidget(self._smooth_transitions)

        self._auto_rotate = QCheckBox("Auto-rotate camera")
        self._auto_rotate.toggled.connect(self._on_setting_changed)
        behavior_layout.addWidget(self._auto_rotate)

        layout.addWidget(behavior_group)

        # View mode settings
        mode_group = QGroupBox("View Mode")
        mode_layout = QVBoxLayout(mode_group)

        self._head_look_mode = QCheckBox("Start in Head-Look mode (instead of Orbit)")
        self._head_look_mode.setToolTip("In Head-Look mode, the camera stays in place and rotates.\nIn Orbit mode, the camera orbits around a target point.")
        self._head_look_mode.toggled.connect(self._on_setting_changed)
        mode_layout.addWidget(self._head_look_mode)

        layout.addWidget(mode_group)

        # Reset button
        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.clicked.connect(self._reset_to_defaults)
        layout.addWidget(reset_btn)

        layout.addStretch()

    def _load_settings(self) -> None:
        """Load current settings."""
        self._default_fov.setValue(int(self._settings.camera.get('default_fov', 45.0)))
        self._min_fov.setValue(int(self._settings.camera.get('min_fov', 30.0)))
        self._max_fov.setValue(int(self._settings.camera.get('max_fov', 120.0)))

        self._default_dist.setValue(self._settings.camera.get('default_distance', 3.0))
        self._min_dist.setValue(self._settings.camera.get('min_distance', 0.5))
        self._max_dist.setValue(self._settings.camera.get('max_distance', 20.0))

        self._rot_speed.setValue(self._settings.camera.get('rotation_speed', 0.01))
        self._zoom_speed.setValue(self._settings.camera.get('zoom_speed', 0.1))
        self._pan_speed.setValue(self._settings.camera.get('pan_speed', 0.001))

        # Keyboard movement speeds
        self._keyboard_speed.setValue(self._settings.camera.get('keyboard_movement_speed', 0.05))
        self._keyboard_speed_slow.setValue(self._settings.camera.get('keyboard_movement_speed_slow', 0.02))
        self._keyboard_speed_fast.setValue(self._settings.camera.get('keyboard_movement_speed_fast', 0.10))

        self._target_on_select.setChecked(self._settings.camera.get('target_on_select', True))
        self._smooth_transitions.setChecked(self._settings.camera.get('smooth_transitions', True))
        self._auto_rotate.setChecked(self._settings.camera.get('auto_rotate', False))

        # View mode
        self._head_look_mode.setChecked(self._settings.camera.get('head_look_mode', False))

    def _on_setting_changed(self) -> None:
        """Handle setting changes."""
        self._settings.camera.set('default_fov', float(self._default_fov.value()))
        self._settings.camera.set('min_fov', float(self._min_fov.value()))
        self._settings.camera.set('max_fov', float(self._max_fov.value()))

        self._settings.camera.set('default_distance', self._default_dist.value())
        self._settings.camera.set('min_distance', self._min_dist.value())
        self._settings.camera.set('max_distance', self._max_dist.value())

        self._settings.camera.set('rotation_speed', self._rot_speed.value())
        self._settings.camera.set('zoom_speed', self._zoom_speed.value())
        self._settings.camera.set('pan_speed', self._pan_speed.value())

        # Keyboard movement speeds
        self._settings.camera.set('keyboard_movement_speed', self._keyboard_speed.value())
        self._settings.camera.set('keyboard_movement_speed_slow', self._keyboard_speed_slow.value())
        self._settings.camera.set('keyboard_movement_speed_fast', self._keyboard_speed_fast.value())

        self._settings.camera.set('target_on_select', self._target_on_select.isChecked())
        self._settings.camera.set('smooth_transitions', self._smooth_transitions.isChecked())
        self._settings.camera.set('auto_rotate', self._auto_rotate.isChecked())

        # View mode
        self._settings.camera.set('head_look_mode', self._head_look_mode.isChecked())

        self.settings_changed.emit()

    def _reset_to_defaults(self) -> None:
        """Reset to defaults."""
        self._settings.camera.reset_to_defaults()
        self._load_settings()
        self.settings_changed.emit()


class UISettingsWidget(QWidget):
    """Widget for editing UI settings."""
    
    settings_changed = pyqtSignal()
    
    def __init__(self, settings: PluginSettings, parent=None):
        super().__init__(parent)
        self._settings = settings
        self._setup_ui()
        self._load_settings()
    
    def _setup_ui(self) -> None:
        """Set up the UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Default visibility
        vis_group = QGroupBox("Default Visibility")
        vis_layout = QVBoxLayout(vis_group)
        
        self._show_mesh = QCheckBox("Show Mesh on Load")
        self._show_mesh.toggled.connect(self._on_setting_changed)
        vis_layout.addWidget(self._show_mesh)
        
        self._show_skeleton = QCheckBox("Show Skeleton on Load")
        self._show_skeleton.toggled.connect(self._on_setting_changed)
        vis_layout.addWidget(self._show_skeleton)
        
        self._show_joints = QCheckBox("Show Joints on Load")
        self._show_joints.toggled.connect(self._on_setting_changed)
        vis_layout.addWidget(self._show_joints)
        
        self._show_gizmo = QCheckBox("Show Gizmo on Load")
        self._show_gizmo.toggled.connect(self._on_setting_changed)
        vis_layout.addWidget(self._show_gizmo)
        
        layout.addWidget(vis_group)
        
        # Theme
        theme_group = QGroupBox("Theme")
        theme_layout = QHBoxLayout(theme_group)
        
        theme_layout.addWidget(QLabel("Color Theme:"))
        self._theme = QComboBox()
        self._theme.addItems(list(UI_THEMES.keys()))
        self._theme.currentTextChanged.connect(self._on_setting_changed)
        theme_layout.addWidget(self._theme)
        
        layout.addWidget(theme_group)
        
        # Joint settings
        joint_group = QGroupBox("Joint Display")
        joint_layout = QGridLayout(joint_group)
        
        joint_layout.addWidget(QLabel("Joint Scale:"), 0, 0)
        self._joint_scale = QDoubleSpinBox()
        self._joint_scale.setRange(0.05, 0.5)
        self._joint_scale.setSingleStep(0.01)
        self._joint_scale.valueChanged.connect(self._on_setting_changed)
        joint_layout.addWidget(self._joint_scale, 0, 1)
        
        layout.addWidget(joint_group)
        
        # Reset button
        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.clicked.connect(self._reset_to_defaults)
        layout.addWidget(reset_btn)
        
        layout.addStretch()
    
    def _load_settings(self) -> None:
        """Load current settings."""
        self._show_mesh.setChecked(self._settings.ui.get('show_mesh_default', True))
        self._show_skeleton.setChecked(self._settings.ui.get('show_skeleton_default', True))
        self._show_joints.setChecked(self._settings.ui.get('show_joints_default', True))
        self._show_gizmo.setChecked(self._settings.ui.get('show_gizmo_default', True))
        
        theme = self._settings.ui.get('theme', 'dark')
        index = self._theme.findText(theme)
        if index >= 0:
            self._theme.setCurrentIndex(index)
        
        self._joint_scale.setValue(self._settings.ui.get('joint_scale', 0.15))
    
    def _on_setting_changed(self) -> None:
        """Handle setting changes."""
        self._settings.ui.set('show_mesh_default', self._show_mesh.isChecked())
        self._settings.ui.set('show_skeleton_default', self._show_skeleton.isChecked())
        self._settings.ui.set('show_joints_default', self._show_joints.isChecked())
        self._settings.ui.set('show_gizmo_default', self._show_gizmo.isChecked())
        self._settings.ui.set('theme', self._theme.currentText())
        self._settings.ui.set('joint_scale', self._joint_scale.value())
        self.settings_changed.emit()
    
    def _reset_to_defaults(self) -> None:
        """Reset to defaults."""
        self._settings.ui.reset_to_defaults()
        self._load_settings()
        self.settings_changed.emit()


class AdvancedSettingsDialog(QDialog):
    """
    Main advanced settings dialog with tabbed interface.
    
    Provides comprehensive settings editing with:
    - Keyboard shortcuts with interactive key capture
    - Mouse sensitivity and bindings
    - Gizmo appearance and behavior
    - Camera settings
    - UI preferences
    """
    
    settings_saved = pyqtSignal()
    
    def __init__(self, settings: PluginSettings, parent=None):
        super().__init__(parent)
        self._settings = settings
        
        self.setWindowTitle("Advanced Settings")
        self.setMinimumSize(600, 500)
        self.resize(700, 600)
        
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)
        
        # Tab widget
        self._tabs = QTabWidget()
        self._tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #4A6572;
                border-radius: 4px;
            }
            QTabBar::tab {
                background-color: #34495E;
                padding: 8px 16px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background-color: #3498DB;
            }
            QTabBar::tab:hover {
                background-color: #4A6572;
            }
        """)
        
        # Create category widgets
        self._keyboard_widget = KeyboardSettingsWidget(self._settings)
        self._keyboard_widget.bindings_changed.connect(self._mark_modified)
        self._tabs.addTab(self._keyboard_widget, "⌨️ Keyboard")
        
        self._mouse_widget = MouseSettingsWidget(self._settings)
        self._mouse_widget.settings_changed.connect(self._mark_modified)
        self._tabs.addTab(self._mouse_widget, "🖱️ Mouse")
        
        self._gizmo_widget = GizmoSettingsWidget(self._settings)
        self._gizmo_widget.settings_changed.connect(self._mark_modified)
        self._tabs.addTab(self._gizmo_widget, "🎯 Gizmo")
        
        self._camera_widget = CameraSettingsWidget(self._settings)
        self._camera_widget.settings_changed.connect(self._mark_modified)
        self._tabs.addTab(self._camera_widget, "📷 Camera")
        
        self._ui_widget = UISettingsWidget(self._settings)
        self._ui_widget.settings_changed.connect(self._mark_modified)
        self._tabs.addTab(self._ui_widget, "🎨 UI")
        
        layout.addWidget(self._tabs)
        
        # Bottom buttons
        btn_layout = QHBoxLayout()
        
        reset_all_btn = QPushButton("Reset All to Defaults")
        reset_all_btn.clicked.connect(self._reset_all)
        btn_layout.addWidget(reset_all_btn)
        
        btn_layout.addStretch()
        
        export_btn = QPushButton("Export...")
        export_btn.clicked.connect(self._export_settings)
        btn_layout.addWidget(export_btn)
        
        import_btn = QPushButton("Import...")
        import_btn.clicked.connect(self._import_settings)
        btn_layout.addWidget(import_btn)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        save_btn = QPushButton("Save")
        save_btn.setDefault(True)
        save_btn.clicked.connect(self._save_and_close)
        btn_layout.addWidget(save_btn)
        
        layout.addLayout(btn_layout)
    
    def _mark_modified(self) -> None:
        """Mark settings as modified."""
        self._settings._modified = True
    
    def _reset_all(self) -> None:
        """Reset all settings to defaults."""
        reply = QMessageBox.question(
            self, "Reset All Settings",
            "Are you sure you want to reset ALL settings to defaults?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self._settings.reset_all_to_defaults()
            self._keyboard_widget._load_bindings()
            self._mouse_widget._load_settings()
            self._gizmo_widget._load_settings()
            self._camera_widget._load_settings()
            self._ui_widget._load_settings()
    
    def _export_settings(self) -> None:
        """Export settings to a file."""
        from PyQt5.QtWidgets import QFileDialog
        
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Export Settings",
            "3d_pose_settings.json",
            "JSON Files (*.json)"
        )
        
        if filepath:
            if self._settings.export_to_file(filepath):
                QMessageBox.information(self, "Export Successful", f"Settings exported to:\n{filepath}")
            else:
                QMessageBox.warning(self, "Export Failed", "Failed to export settings.")
    
    def _import_settings(self) -> None:
        """Import settings from a file."""
        from PyQt5.QtWidgets import QFileDialog
        
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Import Settings",
            "",
            "JSON Files (*.json)"
        )
        
        if filepath:
            if self._settings.import_from_file(filepath):
                self._keyboard_widget._load_bindings()
                self._mouse_widget._load_settings()
                self._gizmo_widget._load_settings()
                self._camera_widget._load_settings()
                self._ui_widget._load_settings()
                QMessageBox.information(self, "Import Successful", "Settings imported successfully.")
            else:
                QMessageBox.warning(self, "Import Failed", "Failed to import settings.")
    
    def _save_and_close(self) -> None:
        """Save settings and close the dialog."""
        if self._settings.save():
            self.settings_saved.emit()
            self.accept()
        else:
            QMessageBox.warning(self, "Save Failed", "Failed to save settings.")

"""
Settings Widgets - Individual Settings Components
=================================================

This package contains individual settings widget classes.
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

from ...settings import PluginSettings, KeyBinding, MouseBinding
from ...settings.defaults import (
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


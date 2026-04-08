"""
UI Styles - Modern Color Scheme & Visual Polish
================================================

Provides a cohesive design system for the 3D Pose Plugin UI.
Based on Material Design principles adapted for Krita's dark theme.
"""

from typing import Optional

from PyQt5.QtWidgets import (
    QWidget, QGroupBox, QPushButton, QTreeWidget, QSlider, QLabel,
    QVBoxLayout, QHBoxLayout, QFrame, QSizePolicy
)
from PyQt5.QtGui import QColor, QPalette, QFont, QPainter, QPen, QBrush
from PyQt5.QtCore import Qt, pyqtSignal, QPropertyAnimation, QEasingCurve, QPoint


# =============================================================================
# COLOR PALETTE (Krita-Compatible Dark Theme)
# =============================================================================

class Colors:
    """
    Modern color palette that works with Krita's dark theme.
    
    Based on Material Design with adjustments for digital art tools.
    """
    # Primary colors
    PRIMARY = '#5DADE2'       # Light blue - Active elements, selection
    PRIMARY_DARK = '#3498DB'  # Darker blue - Pressed states
    PRIMARY_LIGHT = '#85C1E9' # Lighter blue - Hover states
    
    # Accent colors
    ACCENT = '#F39C12'        # Orange - Important actions, warnings
    ACCENT_DARK = '#D68910'   # Darker orange - Pressed states
    
    # Semantic colors
    SUCCESS = '#27AE60'       # Green - Sync, save operations
    WARNING = '#F1C40F'       # Yellow - Cautions
    DANGER = '#E74C3C'        # Red - Destructive actions, errors
    
    # Background colors
    BACKGROUND = '#2C3E50'    # Dark gray - Main background
    SURFACE = '#34495E'       # Lighter gray - Panels, cards
    SURFACE_LIGHT = '#3D566E' # Even lighter - Hover states
    
    # Text colors
    TEXT_PRIMARY = '#ECF0F1'  # Light gray - Primary text
    TEXT_SECONDARY = '#B0BEC5' # Muted gray - Secondary text
    TEXT_DISABLED = '#7F8C8D' # Dimmed - Disabled text
    
    # Gizmo colors (axis-specific)
    GIZMO_X = '#E74C3C'       # Red - X axis
    GIZMO_Y = '#27AE60'       # Green - Y axis  
    GIZMO_Z = '#3498DB'       # Blue - Z axis
    GIZMO_HOVER = '#F1C40F'   # Yellow - Hover state
    GIZMO_DRAG = '#F39C12'    # Orange - Dragging state
    
    # Bone state colors
    BONE_DEFAULT = '#95A5A6'  # Gray - Default bone
    BONE_SELECTED = '#5DADE2' # Blue - Selected bone
    BONE_HOVER = '#F39C12'    # Orange - Hovered bone
    BONE_MODIFIED = '#F1C40F' # Yellow - Modified from bind pose
    BONE_LOCKED = '#7F8C8D'   # Dimmed - Locked bone
    BONE_ROOT = '#9B59B6'     # Purple - Root bones
    BONE_LEAF = '#1ABC9C'     # Teal - Leaf/end effector bones


# =============================================================================
# TYPOGRAPHY
# =============================================================================

class Typography:
    """Font hierarchy for UI elements."""
    
    HEADER = QFont()
    HEADER.setPointSize(11)
    HEADER.setBold(True)
    
    BODY = QFont()
    BODY.setPointSize(10)
    
    SMALL = QFont()
    SMALL.setPointSize(9)
    
    MONO = QFont("Monospace", 9)
    
    @staticmethod
    def apply_header(widget: QWidget) -> None:
        widget.setFont(Typography.HEADER)
    
    @staticmethod
    def apply_body(widget: QWidget) -> None:
        widget.setFont(Typography.BODY)
    
    @staticmethod
    def apply_small(widget: QWidget) -> None:
        widget.setFont(Typography.SMALL)


# =============================================================================
# STYLE SHEETS
# =============================================================================

class StyleSheets:
    """
    Centralized style sheets for consistent theming.
    """
    
    # Main widget background
    MAIN_WIDGET = f"""
        QWidget {{
            background-color: {Colors.BACKGROUND};
            color: {Colors.TEXT_PRIMARY};
        }}
    """
    
    # Group box with modern styling
    GROUP_BOX = f"""
        QGroupBox {{
            font-weight: bold;
            border: 1px solid {Colors.SURFACE_LIGHT};
            border-radius: 6px;
            margin-top: 12px;
            padding-top: 10px;
            background-color: {Colors.SURFACE};
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            subcontrol-position: top left;
            padding: 0 8px;
            color: {Colors.PRIMARY};
            font-size: 11px;
        }}
    """
    
    # Collapsible group box (with indicator)
    GROUP_BOX_COLLAPSIBLE = f"""
        QGroupBox {{
            font-weight: bold;
            border: 1px solid {Colors.SURFACE_LIGHT};
            border-radius: 6px;
            margin-top: 12px;
            padding-top: 10px;
            background-color: {Colors.SURFACE};
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            subcontrol-position: top left;
            padding: 0 8px;
            color: {Colors.PRIMARY};
            font-size: 11px;
        }}
        QGroupBox::indicator {{
            width: 16px;
            height: 16px;
            margin-left: 4px;
        }}
        QGroupBox::indicator:hover {{
            background-color: {Colors.SURFACE_LIGHT};
            border-radius: 3px;
        }}
    """
    
    # Primary action button
    BUTTON_PRIMARY = f"""
        QPushButton {{
            background-color: {Colors.PRIMARY};
            color: white;
            border: none;
            border-radius: 4px;
            padding: 8px 16px;
            font-weight: bold;
            min-height: 20px;
        }}
        QPushButton:hover {{
            background-color: {Colors.PRIMARY_LIGHT};
        }}
        QPushButton:pressed {{
            background-color: {Colors.PRIMARY_DARK};
        }}
        QPushButton:disabled {{
            background-color: {Colors.SURFACE_LIGHT};
            color: {Colors.TEXT_DISABLED};
        }}
    """
    
    # Secondary/outline button
    BUTTON_SECONDARY = f"""
        QPushButton {{
            background-color: transparent;
            color: {Colors.PRIMARY};
            border: 1px solid {Colors.PRIMARY};
            border-radius: 4px;
            padding: 8px 16px;
            min-height: 20px;
        }}
        QPushButton:hover {{
            background-color: {Colors.SURFACE_LIGHT};
        }}
        QPushButton:pressed {{
            background-color: {Colors.PRIMARY_DARK};
            color: white;
        }}
        QPushButton:disabled {{
            border-color: {Colors.TEXT_DISABLED};
            color: {Colors.TEXT_DISABLED};
        }}
    """
    
    # Success button (for sync operations)
    BUTTON_SUCCESS = f"""
        QPushButton {{
            background-color: {Colors.SUCCESS};
            color: white;
            border: none;
            border-radius: 4px;
            padding: 8px 16px;
            font-weight: bold;
            min-height: 24px;
        }}
        QPushButton:hover {{
            background-color: #2ECC71;
        }}
        QPushButton:pressed {{
            background-color: #229954;
        }}
    """
    
    # Danger button
    BUTTON_DANGER = f"""
        QPushButton {{
            background-color: {Colors.DANGER};
            color: white;
            border: none;
            border-radius: 4px;
            padding: 8px 16px;
            min-height: 20px;
        }}
        QPushButton:hover {{
            background-color: #C0392B;
        }}
        QPushButton:pressed {{
            background-color: #A93226;
        }}
    """
    
    # Checkable tool button (for gizmo modes)
    BUTTON_TOOL = f"""
        QPushButton {{
            background-color: {Colors.SURFACE};
            color: {Colors.TEXT_PRIMARY};
            border: 1px solid {Colors.SURFACE_LIGHT};
            border-radius: 4px;
            padding: 6px 12px;
            min-width: 60px;
        }}
        QPushButton:hover {{
            background-color: {Colors.SURFACE_LIGHT};
            border-color: {Colors.PRIMARY};
        }}
        QPushButton:checked {{
            background-color: {Colors.PRIMARY};
            color: white;
            border-color: {Colors.PRIMARY_DARK};
        }}
        QPushButton:disabled {{
            background-color: {Colors.BACKGROUND};
            color: {Colors.TEXT_DISABLED};
        }}
    """
    
    # Tree widget for bone hierarchy
    TREE_WIDGET = f"""
        QTreeWidget {{
            background-color: {Colors.BACKGROUND};
            color: {Colors.TEXT_PRIMARY};
            border: 1px solid {Colors.SURFACE_LIGHT};
            border-radius: 4px;
            padding: 4px;
        }}
        QTreeWidget::item {{
            padding: 4px;
            border-radius: 3px;
        }}
        QTreeWidget::item:hover {{
            background-color: {Colors.SURFACE_LIGHT};
        }}
        QTreeWidget::item:selected {{
            background-color: {Colors.PRIMARY};
            color: white;
        }}
        QTreeWidget::item:has-children {{
            font-weight: bold;
        }}
        QTreeWidget::branch {{
            background-color: transparent;
        }}
        QTreeWidget::branch:has-children:!has-siblings:closed,
        QTreeWidget::branch:closed:has-children:has-siblings {{
            border-image: none;
            image: url(data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxMiIgaGVpZ2h0PSIxMiIgdmlld0JveD0iMCAwIDEyIDEyIj48cGF0aCBmaWxsPSIjQjBCRUM1IiBkPSJNNCAyTDQgMTBMMTAgNloiLz48L3N2Zz4=);
        }}
        QTreeWidget::branch:open:has-children:!has-siblings,
        QTreeWidget::branch:open:has-children:has-siblings {{
            border-image: none;
            image: url(data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxMiIgaGVpZ2h0PSIxMiIgdmlld0JveD0iMCAwIDEyIDEyIj48cGF0aCBmaWxsPSIjQjBCRUM1IiBkPSJNNiA0TDEwIDEwTDIgMTBaIi8+PC9zdmc+);
        }}
    """
    
    # Slider with custom groove
    SLIDER = f"""
        QSlider::groove:horizontal {{
            background: {Colors.SURFACE_LIGHT};
            height: 6px;
            border-radius: 3px;
        }}
        QSlider::handle:horizontal {{
            background: {Colors.PRIMARY};
            width: 16px;
            height: 16px;
            margin: -5px 0;
            border-radius: 8px;
        }}
        QSlider::handle:horizontal:hover {{
            background: {Colors.PRIMARY_LIGHT};
        }}
        QSlider::handle:horizontal:pressed {{
            background: {Colors.PRIMARY_DARK};
        }}
        QSlider::sub-page:horizontal {{
            background: {Colors.PRIMARY};
            border-radius: 3px;
        }}
    """
    
    # Spin box
    SPIN_BOX = f"""
        QDoubleSpinBox {{
            background-color: {Colors.BACKGROUND};
            color: {Colors.TEXT_PRIMARY};
            border: 1px solid {Colors.SURFACE_LIGHT};
            border-radius: 4px;
            padding: 4px;
            min-width: 60px;
        }}
        QDoubleSpinBox:hover {{
            border-color: {Colors.PRIMARY};
        }}
        QDoubleSpinBox:focus {{
            border-color: {Colors.PRIMARY};
            border-width: 2px;
        }}
        QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
            background-color: {Colors.SURFACE};
            border: none;
            width: 20px;
        }}
        QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {{
            background-color: {Colors.SURFACE_LIGHT};
        }}
    """
    
    # Combo box
    COMBO_BOX = f"""
        QComboBox {{
            background-color: {Colors.BACKGROUND};
            color: {Colors.TEXT_PRIMARY};
            border: 1px solid {Colors.SURFACE_LIGHT};
            border-radius: 4px;
            padding: 4px 8px;
            min-width: 100px;
        }}
        QComboBox:hover {{
            border-color: {Colors.PRIMARY};
        }}
        QComboBox::drop-down {{
            border: none;
            width: 24px;
        }}
        QComboBox::down-arrow {{
            image: url(data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxMiIgaGVpZ2h0PSIxMiIgdmlld0JveD0iMCAwIDEyIDEyIj48cGF0aCBmaWxsPSIjQjBCRUM1IiBkPSJNNiA4TDEwIDJMMiAyWiIvPjwvc3ZnPg==);
        }}
        QComboBox QAbstractItemView {{
            background-color: {Colors.SURFACE};
            color: {Colors.TEXT_PRIMARY};
            selection-background-color: {Colors.PRIMARY};
            border: 1px solid {Colors.SURFACE_LIGHT};
        }}
    """
    
    # Label
    LABEL = f"""
        QLabel {{
            color: {Colors.TEXT_PRIMARY};
            background-color: transparent;
        }}
    """
    
    # Status label
    STATUS_LABEL = f"""
        QLabel {{
            color: {Colors.TEXT_SECONDARY};
            background-color: {Colors.SURFACE};
            border: 1px solid {Colors.SURFACE_LIGHT};
            border-radius: 4px;
            padding: 6px;
            font-size: 10px;
        }}
    """
    
    # Axis-specific slider colors
    SLIDER_X = f"""
        QSlider::groove:horizontal {{
            background: {Colors.SURFACE_LIGHT};
            height: 6px;
            border-radius: 3px;
        }}
        QSlider::handle:horizontal {{
            background: {Colors.GIZMO_X};
            width: 16px;
            height: 16px;
            margin: -5px 0;
            border-radius: 8px;
        }}
        QSlider::handle:horizontal:hover {{
            background: #C0392B;
        }}
        QSlider::sub-page:horizontal {{
            background: {Colors.GIZMO_X};
            border-radius: 3px;
        }}
    """
    
    SLIDER_Y = f"""
        QSlider::groove:horizontal {{
            background: {Colors.SURFACE_LIGHT};
            height: 6px;
            border-radius: 3px;
        }}
        QSlider::handle:horizontal {{
            background: {Colors.GIZMO_Y};
            width: 16px;
            height: 16px;
            margin: -5px 0;
            border-radius: 8px;
        }}
        QSlider::handle:horizontal:hover {{
            background: #1E8449;
        }}
        QSlider::sub-page:horizontal {{
            background: {Colors.GIZMO_Y};
            border-radius: 3px;
        }}
    """
    
    SLIDER_Z = f"""
        QSlider::groove:horizontal {{
            background: {Colors.SURFACE_LIGHT};
            height: 6px;
            border-radius: 3px;
        }}
        QSlider::handle:horizontal {{
            background: {Colors.GIZMO_Z};
            width: 16px;
            height: 16px;
            margin: -5px 0;
            border-radius: 8px;
        }}
        QSlider::handle:horizontal:hover {{
            background: #2980B9;
        }}
        QSlider::sub-page:horizontal {{
            background: {Colors.GIZMO_Z};
            border-radius: 3px;
        }}
    """


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def apply_style(widget: QWidget, stylesheet: str) -> None:
    """Apply a stylesheet to a widget and ensure proper palette."""
    widget.setStyleSheet(stylesheet)


def get_bone_color(state: str) -> str:
    """
    Get the color for a bone based on its state.
    
    Args:
        state: One of 'default', 'selected', 'hover', 'modified', 'locked', 'root', 'leaf'
    
    Returns:
        Hex color string
    """
    colors = {
        'default': Colors.BONE_DEFAULT,
        'selected': Colors.BONE_SELECTED,
        'hover': Colors.BONE_HOVER,
        'modified': Colors.BONE_MODIFIED,
        'locked': Colors.BONE_LOCKED,
        'root': Colors.BONE_ROOT,
        'leaf': Colors.BONE_LEAF,
    }
    return colors.get(state, Colors.BONE_DEFAULT)


def get_gizmo_color(axis: str, state: str = 'idle') -> str:
    """
    Get the color for a gizmo axis based on state.
    
    Args:
        axis: 'X', 'Y', or 'Z'
        state: 'idle', 'hover', or 'drag'
    
    Returns:
        Hex color string
    """
    axis_colors = {
        'X': Colors.GIZMO_X,
        'Y': Colors.GIZMO_Y,
        'Z': Colors.GIZMO_Z,
    }
    
    if state == 'hover':
        return Colors.GIZMO_HOVER
    elif state == 'drag':
        return Colors.GIZMO_DRAG
    else:
        return axis_colors.get(axis, Colors.TEXT_PRIMARY)


# =============================================================================
# BONE STATE INDICATORS
# =============================================================================

class BoneStateIndicator:
    """
    Provides visual indicators for bone states in the tree view.
    
    Uses Unicode symbols and colors to indicate bone status.
    """
    
    # Unicode symbols for bone states
    SYMBOL_MODIFIED = '⚠'    # Modified from bind pose
    SYMBOL_LOCKED = '🔒'      # Locked bone
    SYMBOL_ROOT = '⬆'        # Root bone
    SYMBOL_LEAF = '◆'        # Leaf/end effector
    SYMBOL_IK = '🎯'         # IK target
    
    @staticmethod
    def format_bone_name(name: str, is_modified: bool = False, is_locked: bool = False,
                         is_root: bool = False, is_leaf: bool = False) -> str:
        """
        Format a bone name with state indicators.
        
        Args:
            name: Bone name
            is_modified: True if bone is modified from bind pose
            is_locked: True if bone is locked
            is_root: True if bone is a root
            is_leaf: True if bone is a leaf/end effector
        
        Returns:
            Formatted bone name string
        """
        prefix = ''
        if is_locked:
            prefix = BoneStateIndicator.SYMBOL_LOCKED + ' '
        elif is_modified:
            prefix = BoneStateIndicator.SYMBOL_MODIFIED + ' '
        
        suffix = ''
        if is_root:
            suffix = ' ' + BoneStateIndicator.SYMBOL_ROOT
        elif is_leaf:
            suffix = ' ' + BoneStateIndicator.SYMBOL_LEAF

        return f"{prefix}{name}{suffix}"


# =============================================================================
# COLLAPSIBLE GROUP BOX
# =============================================================================

class CollapsibleGroupBox(QWidget):
    """
    A group box that can be collapsed/expanded by clicking on the header.
    
    Provides a space-saving UI component for organizing controls.
    
    Signals:
        toggled: Emitted when the group is expanded/collapsed (expanded: bool)
    
    Usage:
        group = CollapsibleGroupBox("Advanced Controls")
        group.setContent(my_widget)
        group.setExpanded(True)  # Expand the group
    """
    
    toggled = pyqtSignal(bool)  # expanded state
    
    def __init__(self, title: str = "", parent: Optional[QWidget] = None):
        """Create a collapsible group box."""
        super().__init__(parent)
        
        self._title = title
        self._expanded = True
        self._content_widget: Optional[QWidget] = None
        self._content_height = 0
        
        self._setup_ui()
        self._apply_style()
    
    def _setup_ui(self) -> None:
        """Set up the UI structure."""
        # Main layout
        self._main_layout = QVBoxLayout(self)
        self._main_layout.setContentsMargins(0, 0, 0, 0)
        self._main_layout.setSpacing(0)
        
        # Header (clickable to toggle)
        self._header = QPushButton()
        self._header.setCursor(Qt.PointingHandCursor)
        self._header.clicked.connect(self._on_header_clicked)
        self._main_layout.addWidget(self._header)
        
        # Content container
        self._content_container = QWidget()
        self._content_layout = QVBoxLayout(self._content_container)
        self._content_layout.setContentsMargins(8, 8, 8, 8)
        self._content_layout.setSpacing(6)
        self._main_layout.addWidget(self._content_container)
        
        self._update_header()
    
    def _apply_style(self) -> None:
        """Apply styling to the widget."""
        self.setStyleSheet(f"""
            CollapsibleGroupBox {{
                background-color: {Colors.SURFACE};
                border: 1px solid {Colors.SURFACE_LIGHT};
                border-radius: 6px;
            }}
            
            QPushButton {{
                background-color: {Colors.SURFACE};
                color: {Colors.PRIMARY};
                border: none;
                border-radius: 6px;
                padding: 10px 12px;
                text-align: left;
                font-weight: bold;
                font-size: 11px;
            }}
            
            QPushButton:hover {{
                background-color: {Colors.SURFACE_LIGHT};
            }}
            
            QPushButton:pressed {{
                background-color: {Colors.PRIMARY_DARK};
                color: white;
            }}
        """)
    
    def _update_header(self) -> None:
        """Update the header button text and icon."""
        arrow = "▼" if self._expanded else "▶"
        self._header.setText(f"{arrow} {self._title}")
    
    def _on_header_clicked(self) -> None:
        """Handle header click to toggle expansion."""
        self.setExpanded(not self._expanded)
    
    def setTitle(self, title: str) -> None:
        """Set the group box title."""
        self._title = title
        self._update_header()
    
    def title(self) -> str:
        """Get the group box title."""
        return self._title
    
    def setContent(self, widget: QWidget) -> None:
        """Set the content widget."""
        # Remove existing content
        if self._content_widget:
            self._content_widget.setParent(None)
        
        self._content_widget = widget
        self._content_layout.addWidget(widget)
        
        # Store the natural height
        self._content_height = widget.sizeHint().height()
    
    def content(self) -> Optional[QWidget]:
        """Get the content widget."""
        return self._content_widget
    
    def setExpanded(self, expanded: bool) -> None:
        """Set the expanded state."""
        if self._expanded == expanded:
            return
        
        self._expanded = expanded
        self._content_container.setVisible(expanded)
        self._update_header()
        self.toggled.emit(expanded)
    
    def isExpanded(self) -> bool:
        """Check if the group is expanded."""
        return self._expanded
    
    def toggle(self) -> None:
        """Toggle the expanded state."""
        self.setExpanded(not self._expanded)
    
    def sizeHint(self):
        """Get the preferred size."""
        hint = super().sizeHint()
        if self._expanded and self._content_widget:
            hint.setHeight(self._header.sizeHint().height() +
                          self._content_container.sizeHint().height() + 16)
        else:
            hint.setHeight(self._header.sizeHint().height() + 16)
        return hint
    
    def minimumSizeHint(self):
        """Get the minimum size."""
        hint = super().minimumSizeHint()
        hint.setHeight(self._header.minimumSizeHint().height() + 16)
        return hint

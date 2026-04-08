"""
Key Bindings - Data Classes for Input Bindings
==============================================

Provides data classes for storing and manipulating keyboard and mouse bindings.
Supports serialization, validation, and conflict detection.
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, Optional, List, Tuple, Any
from PyQt5.QtCore import Qt


@dataclass
class KeyBinding:
    """
    Represents a keyboard shortcut binding.
    
    Attributes:
        key: Qt.Key value (e.g., Qt.Key_F, Qt.Key_S)
        modifiers: Qt.KeyboardModifiers (e.g., Qt.ControlModifier, Qt.ShiftModifier)
        action: Human-readable action name (optional, for display purposes)
    """
    key: int
    modifiers: int = Qt.NoModifier
    action: str = ""
    
    def __post_init__(self):
        """Validate the key binding after initialization."""
        # Ensure key is a valid Qt.Key
        if not isinstance(self.key, int) or self.key < 0:
            raise ValueError(f"Invalid key value: {self.key}")

        # Ensure modifiers are valid
        # Convert to int to handle both int and Qt.KeyboardModifiers types
        valid_modifiers = int(
            Qt.NoModifier |
            Qt.ShiftModifier |
            Qt.ControlModifier |
            Qt.AltModifier |
            Qt.MetaModifier |
            Qt.KeypadModifier |
            Qt.GroupSwitchModifier
        )
        # Mask to only valid modifier bits
        self.modifiers = int(self.modifiers) & valid_modifiers
    
    def matches(self, key: int, modifiers: int) -> bool:
        """
        Check if this binding matches the given key and modifiers.
        
        Args:
            key: Qt.Key value to check
            modifiers: Qt.KeyboardModifiers to check
            
        Returns:
            True if the binding matches
        """
        return self.key == key and self.modifiers == modifiers
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'key': self.key,
            'modifiers': int(self.modifiers),  # Convert to int for JSON serialization
            'action': self.action
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'KeyBinding':
        """Create a KeyBinding from a dictionary."""
        return cls(
            key=data.get('key', 0),
            modifiers=data.get('modifiers', Qt.NoModifier),
            action=data.get('action', '')
        )
    
    def get_key_name(self) -> str:
        """Get a human-readable key name."""
        # Map common Qt.Key values to names
        key_names = {
            Qt.Key_Escape: 'Esc',
            Qt.Key_Tab: 'Tab',
            Qt.Key_Backtab: 'Shift+Tab',
            Qt.Key_Backspace: 'Backspace',
            Qt.Key_Return: 'Return',
            Qt.Key_Enter: 'Enter',
            Qt.Key_Insert: 'Insert',
            Qt.Key_Delete: 'Delete',
            Qt.Key_Pause: 'Pause',
            Qt.Key_Print: 'Print',
            Qt.Key_SysReq: 'SysReq',
            Qt.Key_Clear: 'Clear',
            Qt.Key_Home: 'Home',
            Qt.Key_End: 'End',
            Qt.Key_Left: 'Left',
            Qt.Key_Up: 'Up',
            Qt.Key_Right: 'Right',
            Qt.Key_Down: 'Down',
            Qt.Key_PageUp: 'PgUp',
            Qt.Key_PageDown: 'PgDn',
            Qt.Key_CapsLock: 'CapsLock',
            Qt.Key_NumLock: 'NumLock',
            Qt.Key_ScrollLock: 'ScrollLock',
            Qt.Key_F1: 'F1',
            Qt.Key_F2: 'F2',
            Qt.Key_F3: 'F3',
            Qt.Key_F4: 'F4',
            Qt.Key_F5: 'F5',
            Qt.Key_F6: 'F6',
            Qt.Key_F7: 'F7',
            Qt.Key_F8: 'F8',
            Qt.Key_F9: 'F9',
            Qt.Key_F10: 'F10',
            Qt.Key_F11: 'F11',
            Qt.Key_F12: 'F12',
            Qt.Key_Space: 'Space',
            Qt.Key_Exclam: '!',
            Qt.Key_QuoteDbl: '"',
            Qt.Key_NumberSign: '#',
            Qt.Key_Dollar: '$',
            Qt.Key_Percent: '%',
            Qt.Key_Ampersand: '&',
            Qt.Key_Apostrophe: "'",
            Qt.Key_ParenLeft: '(',
            Qt.Key_ParenRight: ')',
            Qt.Key_Asterisk: '*',
            Qt.Key_Plus: '+',
            Qt.Key_Comma: ',',
            Qt.Key_Minus: '-',
            Qt.Key_Period: '.',
            Qt.Key_Slash: '/',
            Qt.Key_0: '0',
            Qt.Key_1: '1',
            Qt.Key_2: '2',
            Qt.Key_3: '3',
            Qt.Key_4: '4',
            Qt.Key_5: '5',
            Qt.Key_6: '6',
            Qt.Key_7: '7',
            Qt.Key_8: '8',
            Qt.Key_9: '9',
            Qt.Key_Colon: ':',
            Qt.Key_Semicolon: ';',
            Qt.Key_Less: '<',
            Qt.Key_Equal: '=',
            Qt.Key_Greater: '>',
            Qt.Key_Question: '?',
            Qt.Key_At: '@',
            Qt.Key_A: 'A',
            Qt.Key_B: 'B',
            Qt.Key_C: 'C',
            Qt.Key_D: 'D',
            Qt.Key_E: 'E',
            Qt.Key_F: 'F',
            Qt.Key_G: 'G',
            Qt.Key_H: 'H',
            Qt.Key_I: 'I',
            Qt.Key_J: 'J',
            Qt.Key_K: 'K',
            Qt.Key_L: 'L',
            Qt.Key_M: 'M',
            Qt.Key_N: 'N',
            Qt.Key_O: 'O',
            Qt.Key_P: 'P',
            Qt.Key_Q: 'Q',
            Qt.Key_R: 'R',
            Qt.Key_S: 'S',
            Qt.Key_T: 'T',
            Qt.Key_U: 'U',
            Qt.Key_V: 'V',
            Qt.Key_W: 'W',
            Qt.Key_X: 'X',
            Qt.Key_Y: 'Y',
            Qt.Key_Z: 'Z',
            Qt.Key_BracketLeft: '[',
            Qt.Key_Backslash: '\\',
            Qt.Key_BracketRight: ']',
            Qt.Key_Underscore: '_',
            Qt.Key_QuoteLeft: '`',
        }
        
        key_name = key_names.get(self.key, chr(self.key) if 32 <= self.key < 127 else f'Key_{self.key}')
        return key_name
    
    def get_modifier_names(self) -> List[str]:
        """Get a list of modifier names."""
        modifiers = []
        if self.modifiers & Qt.ControlModifier:
            modifiers.append('Ctrl')
        if self.modifiers & Qt.ShiftModifier:
            modifiers.append('Shift')
        if self.modifiers & Qt.AltModifier:
            modifiers.append('Alt')
        if self.modifiers & Qt.MetaModifier:
            modifiers.append('Meta')
        return modifiers
    
    def get_display_string(self) -> str:
        """
        Get a human-readable display string for the binding.
        
        Returns:
            String like "Ctrl+S" or "F" or "Shift+Ctrl+Z"
        """
        parts = self.get_modifier_names()
        parts.append(self.get_key_name())
        return '+'.join(parts)
    
    def __str__(self) -> str:
        return self.get_display_string()
    
    def __repr__(self) -> str:
        return f"KeyBinding(key={self.key}, modifiers={self.modifiers}, action='{self.action}')"
    
    def __eq__(self, other) -> bool:
        if not isinstance(other, KeyBinding):
            return False
        return self.key == other.key and self.modifiers == other.modifiers
    
    def __hash__(self) -> int:
        return hash((self.key, self.modifiers))


@dataclass
class MouseBinding:
    """
    Represents a mouse button binding.
    
    Attributes:
        button: Qt.MouseButton value (e.g., Qt.LeftButton, Qt.RightButton)
        modifiers: Qt.KeyboardModifiers
        action: Human-readable action name (optional)
    """
    button: int
    modifiers: int = Qt.NoModifier
    action: str = ""
    
    def __post_init__(self):
        """Validate the mouse binding after initialization."""
        # Ensure button is a valid Qt.MouseButton
        # Convert to int to handle both int and Qt.MouseButtons types
        valid_buttons = int(
            Qt.NoButton |
            Qt.LeftButton |
            Qt.RightButton |
            Qt.MiddleButton |
            Qt.BackButton |
            Qt.ForwardButton |
            Qt.TaskButton |
            Qt.ExtraButton1 |
            Qt.ExtraButton2 |
            Qt.ExtraButton3 |
            Qt.ExtraButton4 |
            Qt.ExtraButton5 |
            Qt.ExtraButton6 |
            Qt.ExtraButton7 |
            Qt.ExtraButton8 |
            Qt.ExtraButton9 |
            Qt.ExtraButton10 |
            Qt.ExtraButton11 |
            Qt.ExtraButton12 |
            Qt.ExtraButton13 |
            Qt.ExtraButton14 |
            Qt.ExtraButton15 |
            Qt.ExtraButton16 |
            Qt.ExtraButton17 |
            Qt.ExtraButton18 |
            Qt.ExtraButton19 |
            Qt.ExtraButton20 |
            Qt.ExtraButton21 |
            Qt.ExtraButton22 |
            Qt.ExtraButton23 |
            Qt.ExtraButton24
        )
        # Mask to only valid button bits
        self.button = int(self.button) & valid_buttons

        # Ensure modifiers are valid
        valid_modifiers = int(
            Qt.NoModifier |
            Qt.ShiftModifier |
            Qt.ControlModifier |
            Qt.AltModifier |
            Qt.MetaModifier
        )
        self.modifiers = int(self.modifiers) & valid_modifiers
    
    def matches(self, button: int, modifiers: int) -> bool:
        """
        Check if this binding matches the given button and modifiers.
        
        Args:
            button: Qt.MouseButton to check
            modifiers: Qt.KeyboardModifiers to check
            
        Returns:
            True if the binding matches
        """
        return self.button == button and self.modifiers == modifiers
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'button': int(self.button),  # Convert to int for JSON serialization
            'modifiers': int(self.modifiers),  # Convert to int for JSON serialization
            'action': self.action
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MouseBinding':
        """Create a MouseBinding from a dictionary."""
        return cls(
            button=data.get('button', Qt.NoButton),
            modifiers=data.get('modifiers', Qt.NoModifier),
            action=data.get('action', '')
        )
    
    def get_button_name(self) -> str:
        """Get a human-readable button name."""
        button_names = {
            Qt.LeftButton: 'Left',
            Qt.RightButton: 'Right',
            Qt.MiddleButton: 'Middle',
            Qt.BackButton: 'Back',
            Qt.ForwardButton: 'Forward',
        }
        return button_names.get(self.button, f'Button_{self.button}')
    
    def get_modifier_names(self) -> List[str]:
        """Get a list of modifier names."""
        modifiers = []
        if self.modifiers & Qt.ControlModifier:
            modifiers.append('Ctrl')
        if self.modifiers & Qt.ShiftModifier:
            modifiers.append('Shift')
        if self.modifiers & Qt.AltModifier:
            modifiers.append('Alt')
        if self.modifiers & Qt.MetaModifier:
            modifiers.append('Meta')
        return modifiers
    
    def get_display_string(self) -> str:
        """
        Get a human-readable display string for the binding.
        
        Returns:
            String like "Ctrl+Left" or "Right" or "Shift+Middle"
        """
        parts = self.get_modifier_names()
        parts.append(self.get_button_name())
        return '+'.join(parts)
    
    def __str__(self) -> str:
        return self.get_display_string()
    
    def __repr__(self) -> str:
        return f"MouseBinding(button={self.button}, modifiers={self.modifiers}, action='{self.action}')"
    
    def __eq__(self, other) -> bool:
        if not isinstance(other, MouseBinding):
            return False
        return self.button == other.button and self.modifiers == other.modifiers
    
    def __hash__(self) -> int:
        return hash((self.button, self.modifiers))


def find_binding_conflicts(
    bindings: Dict[str, KeyBinding]
) -> List[Tuple[str, str, KeyBinding]]:
    """
    Find conflicts in a set of key bindings.
    
    Args:
        bindings: Dictionary mapping action names to KeyBindings
        
    Returns:
        List of tuples (action1, action2, binding) for each conflict found
    """
    conflicts = []
    seen: Dict[KeyBinding, str] = {}
    
    for action, binding in bindings.items():
        if binding in seen:
            conflicts.append((seen[binding], action, binding))
        else:
            seen[binding] = action
    
    return conflicts


def validate_key_binding(key: int, modifiers: int) -> Tuple[bool, Optional[str]]:
    """
    Validate a key binding combination.
    
    Args:
        key: Qt.Key value
        modifiers: Qt.KeyboardModifiers
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    # Check for valid key
    if key < 0 or key > 0x10FFFF:
        return False, "Invalid key code"
    
    # Check for modifier-only binding (no actual key)
    if key == 0:
        return False, "Cannot bind to modifiers only"
    
    # Check for reserved keys
    reserved_keys = [
        # System keys that shouldn't be overridden
    ]
    if key in reserved_keys:
        return False, f"Key is reserved by the system"
    
    return True, None

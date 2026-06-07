"""Global hotkey configuration dialog for MacroForge.

Integrates with the existing hotkeys.py module and SettingsManager
to provide a UI for configuring global hotkeys.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QScrollArea, QFrame,
    QCheckBox, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QKeySequence, QShortcut

from ui.theme import COLORS
from debugger import logger


class HotkeyEdit(QFrame):
    """Single hotkey editor with label, key input, and clear button."""
    
    changed = pyqtSignal(str, str)  # name, new_key
    
    def __init__(self, name: str, label: str, default: str, current: str, parent=None):
        super().__init__(parent)
        self.name = name
        self.default = default
        self.setFrameShape(QFrame.Shape.NoFrame)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(8)
        
        # Label
        self.label = QLabel(label)
        self.label.setStyleSheet(f"color: {COLORS['text']}; font-weight: 600; min-width: 140px;")
        layout.addWidget(self.label)
        
        # Key input (read-only, captures key press)
        self.key_input = QLineEdit(current or default)
        self.key_input.setReadOnly(True)
        self.key_input.setFixedWidth(140)
        self.key_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {COLORS['bg_card']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 6px 10px;
                font-family: Consolas;
                font-size: 11pt;
            }}
            QLineEdit:focus {{
                border-color: {COLORS['accent']};
            }}
        """)
        self.key_input.setPlaceholderText("Press keys...")
        layout.addWidget(self.key_input)
        
        # Capture button
        self.capture_btn = QPushButton("Set")
        self.capture_btn.setCheckable(True)
        self.capture_btn.setFixedWidth(50)
        self.capture_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['bg_tertiary']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 5px 10px;
                font-weight: 600;
            }}
            QPushButton:checked {{
                background-color: {COLORS['accent']};
                color: #000;
            }}
        """)
        self.capture_btn.toggled.connect(self._on_capture_toggle)
        layout.addWidget(self.capture_btn)
        
        # Clear button
        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setFixedWidth(50)
        self.clear_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {COLORS['text_dim']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 5px 10px;
            }}
            QPushButton:hover {{
                color: {COLORS['accent']};
                border-color: {COLORS['accent']};
            }}
        """)
        self.clear_btn.clicked.connect(self._clear)
        layout.addWidget(self.clear_btn)
        
        # Reset button
        self.reset_btn = QPushButton("Reset")
        self.reset_btn.setFixedWidth(50)
        self.reset_btn.setToolTip(f"Reset to default: {default}")
        self.reset_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {COLORS['text_dim']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 5px 10px;
            }}
            QPushButton:hover {{
                color: {COLORS['text']};
                border-color: {COLORS['text']};
            }}
        """)
        self.reset_btn.clicked.connect(self._reset)
        layout.addWidget(self.reset_btn)
        
        layout.addStretch()
        
        # Current value storage
        self._value = current or default
    
    def _on_capture_toggle(self, checked: bool):
        if checked:
            self.key_input.setText("Press keys...")
            self.key_input.setFocus()
            self.key_input.keyPressEvent = self._capture_key
        else:
            self.key_input.keyPressEvent = super(QLineEdit, self.key_input).keyPressEvent
            self.key_input.setText(self._value)
    
    def _capture_key(self, event):
        """Capture key press and format as key sequence."""
        key = event.key()
        modifiers = event.modifiers()
        
        # Ignore modifier-only presses
        if key in (Qt.Key.Key_Shift, Qt.Key.Key_Control, Qt.Key.Key_Alt, 
                   Qt.Key.Key_Meta, Qt.Key.Key_AltGr):
            return
        
        # Build key sequence string
        parts = []
        if modifiers & Qt.KeyboardModifier.ControlModifier:
            parts.append("Ctrl")
        if modifiers & Qt.KeyboardModifier.AltModifier:
            parts.append("Alt")
        if modifiers & Qt.KeyboardModifier.ShiftModifier:
            parts.append("Shift")
        if modifiers & Qt.KeyboardModifier.MetaModifier:
            parts.append("Meta")
        
        # Add main key
        key_name = QKeySequence(key).toString()
        if key_name:
            parts.append(key_name)
        
        self._value = "+".join(parts) if parts else ""
        self.key_input.setText(self._value)
        self.capture_btn.setChecked(False)
        self.changed.emit(self.name, self._value)
    
    def _clear(self):
        self._value = ""
        self.key_input.setText("")
        self.changed.emit(self.name, "")
    
    def _reset(self):
        self._value = self.default
        self.key_input.setText(self._value)
        self.changed.emit(self.name, self._value)
    
    def value(self) -> str:
        return self._value
    
    def set_value(self, value: str):
        self._value = value or ""
        self.key_input.setText(self._value)


class HotkeySettingsDialog(QDialog):
    """Dialog for configuring global hotkeys."""
    
    hotkeys_changed = pyqtSignal(dict)  # {name: key_sequence}
    
    # Hotkey definitions: (name, label, default)
    HOTKEY_DEFINITIONS = [
        ("play_pause", "Play/Pause", "Space"),
        ("stop", "Stop/Escape", "Escape"),
        ("record", "Start Recording", "F7"),
        ("save", "Save Session", "Ctrl+S"),
        ("undo", "Undo", "Ctrl+Z"),
        ("redo", "Redo", "Ctrl+Y"),
        ("copy", "Copy Action", "Ctrl+C"),
        ("paste", "Paste Action", "Ctrl+V"),
        ("duplicate", "Duplicate", "Ctrl+D"),
        ("delete", "Delete", "Delete"),
        ("select_all", "Select All", "Ctrl+A"),
        ("group", "Group Actions", "Ctrl+G"),
        ("ungroup", "Ungroup", "Ctrl+Shift+G"),
        ("search", "Search Timeline", "Ctrl+F"),
        ("run_from_selected", "Run From Selected", "Ctrl+Enter"),
        ("macro_editor", "Open Macro Editor", "Ctrl+E"),
        ("preflight", "Preflight Check", "Ctrl+Shift+P"),
        ("toggle_runtime_log", "Toggle Runtime Log", "Ctrl+Shift+L"),
        ("variables", "Variables", "Ctrl+Alt+V"),
        ("profile_library", "Profile Library", "Ctrl+Alt+P"),
        ("set_click_coordinates", "Set Click Coords", "Ctrl+Shift+M"),
        ("reset_timeline_zoom", "Reset Zoom", "Ctrl+0"),
    ]
    
    def __init__(self, parent=None, settings_manager=None):
        super().__init__(parent)
        self.settings_manager = settings_manager
        self._hotkey_widgets = {}
        
        self.setWindowTitle("Hotkey Settings")
        self.setMinimumSize(500, 600)
        self.resize(500, 700)
        
        self._build_ui()
        self._load_hotkeys()
        
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {COLORS['bg']};
            }}
            QLabel {{
                color: {COLORS['text']};
            }}
            QScrollArea {{
                border: none;
            }}
        """)
    
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # Header
        header = QLabel("Keyboard Shortcuts")
        header.setStyleSheet(f"""
            color: {COLORS['text']};
            font-size: 16pt;
            font-weight: 700;
            padding-bottom: 8px;
        """)
        layout.addWidget(header)
        
        # Description
        desc = QLabel("Click \"Set\" then press the desired key combination. "
                     "Global hotkeys work even when MacroForge is not focused.")
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 10pt;")
        layout.addWidget(desc)
        
        # Scroll area for hotkeys
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        scroll_content = QFrame()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(4)
        
        # Create hotkey editors
        for name, label, default in self.HOTKEY_DEFINITIONS:
            widget = HotkeyEdit(name, label, default, "")
            widget.changed.connect(self._on_hotkey_changed)
            self._hotkey_widgets[name] = widget
            scroll_layout.addWidget(widget)
        
        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll, stretch=1)
        
        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background-color: {COLORS['border']};")
        sep.setFixedHeight(1)
        layout.addWidget(sep)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        self.reset_all_btn = QPushButton("Reset All to Default")
        self.reset_all_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {COLORS['text_dim']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
                padding: 8px 16px;
            }}
            QPushButton:hover {{
                color: {COLORS['text']};
                border-color: {COLORS['text']};
            }}
        """)
        self.reset_all_btn.clicked.connect(self._reset_all)
        btn_layout.addWidget(self.reset_all_btn)
        
        btn_layout.addStretch()
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['bg_tertiary']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
                padding: 8px 16px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                border-color: {COLORS['accent']};
                background-color: {COLORS['bg_secondary']};
            }}
        """)
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)
        
        self.save_btn = QPushButton("Save")
        self.save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['accent']};
                color: #000;
                border: none;
                border-radius: 8px;
                padding: 8px 16px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background-color: #5eead4;
            }}
        """)
        self.save_btn.clicked.connect(self._save)
        btn_layout.addWidget(self.save_btn)
        
        layout.addLayout(btn_layout)
    
    def _load_hotkeys(self):
        """Load current hotkeys from settings."""
        if not self.settings_manager:
            return
        
        hotkeys = self.settings_manager.settings.get("hotkeys", {})
        for name, widget in self._hotkey_widgets.items():
            value = hotkeys.get(name, "")
            # If not set, use default
            if not value:
                for n, l, d in self.HOTKEY_DEFINITIONS:
                    if n == name:
                        value = d
                        break
            widget.set_value(value)
    
    def _on_hotkey_changed(self, name: str, value: str):
        """Handle individual hotkey change."""
        logger.debug(f"Hotkey {name} changed to: {value}")
    
    def _reset_all(self):
        """Reset all hotkeys to defaults."""
        for name, widget in self._hotkey_widgets.items():
            for n, l, d in self.HOTKEY_DEFINITIONS:
                if n == name:
                    widget.set_value(d)
                    break
    
    def _save(self):
        """Save hotkey settings."""
        hotkeys = {}
        for name, widget in self._hotkey_widgets.items():
            value = widget.value()
            if value:
                hotkeys[name] = value
        
        # Save to settings
        if self.settings_manager:
            self.settings_manager.settings["hotkeys"] = hotkeys
            self.settings_manager.save()
        
        # Emit signal with new hotkeys
        self.hotkeys_changed.emit(hotkeys)
        
        self.accept()
    
    def get_hotkeys(self) -> dict:
        """Return current hotkey configuration."""
        return {name: widget.value() for name, widget in self._hotkey_widgets.items()}


def open_hotkey_settings(parent=None, settings_manager=None, callback=None):
    """Open hotkey settings dialog.
    
    Args:
        parent: Parent widget
        settings_manager: SettingsManager instance
        callback: Optional callable to receive hotkeys_changed signal
    """
    dlg = HotkeySettingsDialog(parent, settings_manager)
    if callback:
        dlg.hotkeys_changed.connect(callback)
    return dlg.exec()

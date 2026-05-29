"""Properties panel for MacroForge PyQt6."""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLabel, QLineEdit,
    QDoubleSpinBox, QSpinBox, QCheckBox, QComboBox, QFrame,
    QScrollArea, QPushButton
)
from PyQt6.QtCore import Qt, pyqtSignal

from ui.theme import COLORS
from models import Action


class PropertiesPanel(QScrollArea):
    """Adaptive properties panel that shows fields based on action type."""

    action_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._action = None

        self.setWidgetResizable(True)
        self.setMaximumWidth(320)
        self.setStyleSheet(f"""
            QScrollArea {{
                background-color: {COLORS['bg_secondary']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
            }}
        """)

        self._container = QWidget()
        self._layout = QVBoxLayout(self._container)
        self._layout.setContentsMargins(12, 12, 12, 12)
        self._layout.setSpacing(8)

        self._title = QLabel("No Action Selected")
        self._title.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 14px; font-weight: bold;")
        self._layout.addWidget(self._title)

        self._form = QFormLayout()
        self._form.setSpacing(8)
        self._layout.addLayout(self._form)
        self._layout.addStretch(1)
        self.setWidget(self._container)

        self._fields = {}

    def set_action(self, action: Action):
        self._action = action
        self._clear_form()
        if action is None:
            self._title.setText("No Action Selected")
            return

        t = getattr(action, "action_type", "key")
        self._title.setText(f"{t.title()} Action Properties")
        self._title.setStyleSheet(f"color: {COLORS['accent']}; font-size: 14px; font-weight: bold;")

        # Common fields
        self._add_line("Key / Label", "key", action.key)
        self._add_double("Duration (s)", "duration", action.duration, 0.01, 10, 0.01)
        self._add_int("Lane", "lane", action.lane, 0, 7)
        self._add_int("Repeat", "repeat_count", getattr(action, "repeat_count", 1), 1, 100)
        self._add_bool("Hold mode", "hold_mode", action.hold_mode)
        self._add_bool("Random delay", "random_delay", getattr(action, "random_delay", 0.0) > 0, extra=getattr(action, "random_delay", 0.0))
        self._add_bool("Random key", "random_key", action.random_key)

        # Type-specific fields
        if t == "image":
            self._add_combo("When not found", "on_not_found", ["skip", "stop", "warn"], getattr(action, "on_not_found", "skip"))
            self._add_combo("On found action", "on_found_action", ["continue", "click", "double_click", "press_key", "move_to"], getattr(action, "on_found_action", "continue"))
            self._add_line("On found key", "on_found_key", getattr(action, "on_found_key", ""))
            self._add_double("Wait timeout (s)", "wait_timeout", getattr(action, "wait_timeout", 0.0), 0, 300, 0.1)
            self._add_bool("Position mouse", "position_mouse", getattr(action, "position_mouse", False))
            self._add_bool("Random click", "random_click", getattr(action, "random_click", False))
            self._add_bool("Loop until found", "loop_until_found", getattr(action, "loop_until_found", False))

        elif t == "click":
            self._add_int("Click X", "click_x", getattr(action, "click_x", 0), -9999, 9999)
            self._add_int("Click Y", "click_y", getattr(action, "click_y", 0), -9999, 9999)
            self._add_combo("Button", "click_button", ["left", "right", "middle", "double"], getattr(action, "click_button", "left"))
            self._add_combo("Coord mode", "click_coord_mode", ["absolute", "foreground", "offset", "current"], getattr(action, "click_coord_mode", "absolute"))
            self._add_int("Random radius", "click_rand_radius", getattr(action, "click_rand_radius", 0), 0, 100)

        elif t == "pause":
            pass  # Duration already added above

    def _clear_form(self):
        while self._form.count():
            item = self._form.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._fields.clear()

    def _add_line(self, label, attr, value):
        edit = QLineEdit(str(value) if value else "")
        edit.setStyleSheet(f"""
            QLineEdit {{
                background-color: {COLORS['bg_tertiary']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 6px 10px;
            }}
        """)
        edit.textChanged.connect(lambda text, a=attr: self._update_field(a, text))
        self._form.addRow(QLabel(label), edit)
        self._fields[attr] = edit

    def _add_double(self, label, attr, value, min_v, max_v, step):
        spin = QDoubleSpinBox()
        spin.setRange(min_v, max_v)
        spin.setSingleStep(step)
        spin.setDecimals(3)
        spin.setValue(float(value))
        spin.valueChanged.connect(lambda v, a=attr: self._update_field(a, v))
        self._form.addRow(QLabel(label), spin)
        self._fields[attr] = spin

    def _add_int(self, label, attr, value, min_v, max_v):
        spin = QSpinBox()
        spin.setRange(min_v, max_v)
        spin.setValue(int(value))
        spin.valueChanged.connect(lambda v, a=attr: self._update_field(a, v))
        self._form.addRow(QLabel(label), spin)
        self._fields[attr] = spin

    def _add_bool(self, label, attr, value, extra=None):
        chk = QCheckBox()
        chk.setChecked(bool(value))
        chk.stateChanged.connect(lambda s, a=attr: self._update_field(a, s == Qt.CheckState.Checked.value))
        self._form.addRow(QLabel(label), chk)
        self._fields[attr] = chk

    def _add_combo(self, label, attr, items, value):
        combo = QComboBox()
        combo.addItems(items)
        combo.setCurrentText(str(value))
        combo.currentTextChanged.connect(lambda text, a=attr: self._update_field(a, text))
        self._form.addRow(QLabel(label), combo)
        self._fields[attr] = combo

    def _update_field(self, attr, value):
        if self._action is None:
            return
        try:
            setattr(self._action, attr, value)
            self.action_changed.emit()
        except Exception as e:
            pass

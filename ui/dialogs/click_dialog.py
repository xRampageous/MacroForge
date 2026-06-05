"""Click action dialog — modern PyQt6 rebuild."""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QComboBox, QPushButton, QCheckBox
)
from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QCursor, QKeySequence, QShortcut
from models import Action
from ui.theme import COLORS
from ui.dialogs._common import dialog_stylesheet, make_header, make_buttons


class ClickDialog(QDialog):
    def __init__(self, parent=None, existing=None):
        super().__init__(parent)
        self.setWindowTitle("Click Action")
        self.setMinimumWidth(360)
        C = COLORS
        self._accent = C['click']
        self.setStyleSheet(dialog_stylesheet(self._accent))
        self._set_coords_hotkey = self._hotkey_text(parent, "set_click_coordinates", "Ctrl+Shift+M")
        cursor_pos = QCursor.pos()
        start_x = str(getattr(existing, 'click_x', int(cursor_pos.x()))) if existing else str(int(cursor_pos.x()))
        start_y = str(getattr(existing, 'click_y', int(cursor_pos.y()))) if existing else str(int(cursor_pos.y()))

        lo = QVBoxLayout(self)
        lo.setSpacing(9)
        lo.setContentsMargins(16, 16, 16, 14)

        lo.addWidget(make_header("Mouse Click", self._accent, "click", "Click at a screen coordinate"))

        # Coordinates
        coord = QHBoxLayout()
        coord.addWidget(QLabel("X"))
        self.x = QLineEdit(start_x)
        self.x.setFixedWidth(60)
        coord.addWidget(self.x)
        coord.addWidget(QLabel("Y"))
        self.y = QLineEdit(start_y)
        self.y.setFixedWidth(60)
        coord.addWidget(self.y)
        coord.addStretch()
        lo.addLayout(coord)
        self.cursor_pos = QLabel("Mouse: -")
        self.cursor_pos.setStyleSheet(f"color: {C['text_dim']}; font-size: 11px; font-weight: 750;")
        lo.addWidget(self.cursor_pos)
        hint_text = (
            f"Press {self._set_coords_hotkey} to set X/Y from the current mouse position"
            if self._set_coords_hotkey else
            "Set click coordinates shortcut is disabled"
        )
        self.hotkey_hint = QLabel(hint_text)
        self.hotkey_hint.setStyleSheet(f"color: {C['text_dim']}; font-size: 10px; font-weight: 700;")
        lo.addWidget(self.hotkey_hint)

        # Button
        btn_row = QHBoxLayout()
        btn_row.addWidget(QLabel("Button"))
        self.btn = QComboBox()
        self.btn.addItems(["left", "right", "middle", "double"])
        self.btn.setCurrentText(getattr(existing, 'click_button', 'left') if existing else 'left')
        btn_row.addWidget(self.btn)
        btn_row.addStretch()
        lo.addLayout(btn_row)

        # Random radius
        rand_row = QHBoxLayout()
        rand_row.addWidget(QLabel("Random ± (px)"))
        self.rand = QLineEdit(str(getattr(existing, 'click_rand_radius', 0)) if existing else "0")
        self.rand.setFixedWidth(50)
        rand_row.addWidget(self.rand)
        rand_row.addStretch()
        lo.addLayout(rand_row)

        # Repeat
        rep_row = QHBoxLayout()
        rep_row.addWidget(QLabel("Repeat ×"))
        self.rep = QLineEdit(str(getattr(existing, 'repeat_count', 1)) if existing else "1")
        self.rep.setFixedWidth(50)
        rep_row.addWidget(self.rep)
        rep_row.addStretch()
        lo.addLayout(rep_row)

        # Label
        lbl_row = QHBoxLayout()
        lbl_row.addWidget(QLabel("Label"))
        self.lbl = QLineEdit(getattr(existing, 'label', '') if existing else '')
        lbl_row.addWidget(self.lbl)
        lo.addLayout(lbl_row)

        lo.addStretch()
        lo.addLayout(make_buttons(self, "Add Click", self._accent, self.accept, "click"))
        self._xy_timer = QTimer(self)
        self._xy_timer.setInterval(120)
        self._xy_timer.timeout.connect(self._sync_cursor_xy)
        self._xy_timer.start()
        self._set_coords_shortcut = None
        if self._set_coords_hotkey:
            self._set_coords_shortcut = QShortcut(QKeySequence(self._set_coords_hotkey), self)
            self._set_coords_shortcut.activated.connect(self._capture_cursor_xy)

    def _hotkey_text(self, parent, name, default):
        try:
            if parent is not None and hasattr(parent, "_hotkey"):
                return parent._hotkey(name, default)
        except Exception:
            pass
        return default

    def _sync_cursor_xy(self):
        pos = QCursor.pos()
        self.cursor_pos.setText(f"Mouse: {int(pos.x())}, {int(pos.y())}")

    def _capture_cursor_xy(self):
        pos = QCursor.pos()
        for field, value in ((self.x, str(int(pos.x()))), (self.y, str(int(pos.y())))):
            field.setText(value)
            self._set_field_invalid(field, False)

    def _invalid_style(self):
        return (
            f"background-color: {COLORS['bg_tertiary']}; color: {COLORS['text']}; "
            f"border: 1px solid {COLORS['error']}; border-radius: 7px; "
            "padding: 6px 9px; font-size: 12px;"
        )

    def _set_field_invalid(self, field, invalid):
        field.setStyleSheet(self._invalid_style() if invalid else "")

    def _parse_int_field(self, field):
        try:
            value = int(str(field.text()).strip())
            self._set_field_invalid(field, False)
            return value
        except (TypeError, ValueError):
            self._set_field_invalid(field, True)
            return None

    def accept(self):
        x = self._parse_int_field(self.x)
        y = self._parse_int_field(self.y)
        if x is None or y is None:
            return
        super().accept()

    def get_action(self):
        x = self._parse_int_field(self.x)
        y = self._parse_int_field(self.y)
        if x is None or y is None:
            return None
        try:
            rand = int(self.rand.text() or 0)
            repeat = max(1, int(self.rep.text() or 1))
        except ValueError:
            return None
        return Action(
            key="[CLICK]",
            duration=0.05,
            action_type="click",
            click_x=x,
            click_y=y,
            click_button=self.btn.currentText(),
            click_rand_radius=rand,
            repeat_count=repeat,
            label=self.lbl.text().strip()
        )

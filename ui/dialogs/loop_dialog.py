from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QSpinBox, QFrame

from models import Action
from ui.theme import COLORS
from ui.dialogs._common import dialog_stylesheet, make_header, make_buttons


class LoopDialog(QDialog):
    """Create/edit a loop block that jumps back to an earlier row."""

    def __init__(self, parent=None, existing=None, row_count=0, current_index=-1):
        super().__init__(parent)
        C = COLORS
        accent = C.get("loop", C["success"])
        self.setWindowTitle("Loop Block")
        self.setMinimumWidth(390)
        self.setStyleSheet(dialog_stylesheet(accent))
        self._existing = existing
        self._row_count = max(0, int(row_count or 0))
        self._current_index = int(current_index or -1)

        lo = QVBoxLayout(self)
        lo.setContentsMargins(16, 16, 16, 16)
        lo.setSpacing(12)
        lo.addWidget(make_header("Loop Block", accent, "loop", "Repeat a previous section without duplicating rows."))

        body = QFrame(); body.setObjectName("body")
        body.setStyleSheet(f"QFrame#body {{ background: {C['bg_card']}; border: 1px solid {C['border']}; border-radius: 10px; }}")
        body_lo = QVBoxLayout(body); body_lo.setContentsMargins(12, 12, 12, 12); body_lo.setSpacing(8)

        def label(text):
            l = QLabel(text); l.setStyleSheet(f"color: {C['text_dim']}; font-size: 11px; font-weight: 700; background: transparent;")
            return l

        self.label_edit = QLineEdit(getattr(existing, "label", "") if existing else "")
        self.label_edit.setPlaceholderText("Label, e.g. Repeat main farm route")
        body_lo.addWidget(label("Label")); body_lo.addWidget(self.label_edit)

        self.count_spin = QSpinBox(); self.count_spin.setRange(2, 9999)
        self.count_spin.setValue(int(getattr(existing, "loop_count", getattr(existing, "repeat_count", 2)) if existing else 2))
        body_lo.addWidget(label("Repeat count")); body_lo.addWidget(self.count_spin)

        self.target_spin = QSpinBox(); self.target_spin.setRange(1, max(1, self._row_count))
        default_target = int(getattr(existing, "loop_target", -1) if existing else max(0, self._current_index - 1))
        self.target_spin.setValue(default_target + 1 if default_target >= 0 else 1)
        body_lo.addWidget(label("Jump back to row")); body_lo.addWidget(self.target_spin)

        hint = QLabel("Tip: place this after the section you want to repeat, then point it back to that section's first row.")
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {C['text_dark']}; font-size: 10px; background: transparent;")
        body_lo.addWidget(hint)

        lo.addWidget(body)
        lo.addLayout(make_buttons(self, "Save Loop", accent, self.accept, "check"))

    def get_action(self):
        a = self._existing or Action("[LOOP]", 0.0, action_type="loop")
        a.key = "[LOOP]"
        a.duration = 0.0
        a.action_type = "loop"
        a.label = self.label_edit.text().strip() or f"Loop x{self.count_spin.value()}"
        a.loop_count = self.count_spin.value()
        a.repeat_count = self.count_spin.value()
        a.loop_target = self.target_spin.value() - 1
        return a

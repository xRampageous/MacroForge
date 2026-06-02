from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox,
    QSpinBox, QFrame
)
from PyQt6.QtCore import Qt

from models import Action
from ui.theme import COLORS
from ui.dialogs._common import dialog_stylesheet, make_header, make_buttons


class ConditionDialog(QDialog):
    """Create/edit a condition block.

    Condition rows are runtime-capable blocks: the engine evaluates the rule and
    jumps to either target row when configured. Row numbers shown in the UI are
    1-based; the model stores 0-based targets.
    """

    def __init__(self, parent=None, existing=None, row_count=0):
        super().__init__(parent)
        self.setWindowTitle("Condition Block")
        self.setMinimumWidth(430)
        C = COLORS
        self.setStyleSheet(dialog_stylesheet(C["condition"]))
        self._accepted = False
        self._existing = existing
        self._row_count = max(0, int(row_count or 0))

        lo = QVBoxLayout(self)
        lo.setContentsMargins(16, 16, 16, 16)
        lo.setSpacing(12)
        lo.addWidget(make_header("Condition Block", C["condition"], "condition", "Branch playback from a rule."))

        body = QFrame()
        body.setObjectName("body")
        body.setStyleSheet(f"QFrame#body {{ background: {C['bg_card']}; border: 1px solid {C['border']}; border-radius: 10px; }}")
        body_lo = QVBoxLayout(body)
        body_lo.setContentsMargins(12, 12, 12, 12)
        body_lo.setSpacing(8)

        def label(text):
            l = QLabel(text)
            l.setStyleSheet(f"color: {C['text_dim']}; font-size: 11px; font-weight: 700; background: transparent;")
            return l

        def field(text=""):
            w = QLineEdit(text)
            w.setStyleSheet(
                f"QLineEdit {{ background-color: {C['bg_tertiary']}; color: {C['text']}; border: 1px solid {C['border']}; border-radius: 7px; padding: 7px 10px; }}"
                f"QLineEdit:focus {{ border-color: {C['condition']}; }}"
            )
            return w

        self.label_edit = field(getattr(existing, "label", "") if existing else "")
        self.label_edit.setPlaceholderText("Label, e.g. If button is visible")
        body_lo.addWidget(label("Label"))
        body_lo.addWidget(self.label_edit)

        self.type_combo = QComboBox()
        self.type_combo.addItems(["pixel_color", "variable", "none"])
        self.type_combo.setCurrentText(getattr(existing, "condition_type", "pixel_color") if existing else "pixel_color")
        body_lo.addWidget(label("Condition type"))
        body_lo.addWidget(self.type_combo)

        xy = QHBoxLayout()
        self.x_spin = QSpinBox(); self.x_spin.setRange(-99999, 99999)
        self.y_spin = QSpinBox(); self.y_spin.setRange(-99999, 99999)
        self.x_spin.setValue(int(getattr(existing, "condition_x", 0) if existing else 0))
        self.y_spin.setValue(int(getattr(existing, "condition_y", 0) if existing else 0))
        xy.addWidget(self.x_spin); xy.addWidget(self.y_spin)
        body_lo.addWidget(label("Pixel X / Y"))
        body_lo.addLayout(xy)

        self.color_edit = field(getattr(existing, "condition_color", "") if existing else "")
        self.color_edit.setPlaceholderText("#RRGGBB")
        body_lo.addWidget(label("Expected colour"))
        body_lo.addWidget(self.color_edit)

        self.var_name = field(getattr(existing, "condition_var_name", "") if existing else "")
        self.var_name.setPlaceholderText("variable name")
        self.var_value = field(getattr(existing, "condition_var_value", "") if existing else "")
        self.var_value.setPlaceholderText("expected value")
        body_lo.addWidget(label("Variable rule"))
        var_row = QHBoxLayout(); var_row.addWidget(self.var_name); var_row.addWidget(self.var_value)
        body_lo.addLayout(var_row)

        max_row = max(0, self._row_count)
        self.true_jump = QSpinBox(); self.true_jump.setRange(0, max_row); self.true_jump.setSpecialValueText("Next row")
        self.false_jump = QSpinBox(); self.false_jump.setRange(0, max_row); self.false_jump.setSpecialValueText("Next row")
        tj = int(getattr(existing, "condition_jump_true", -1) if existing else -1)
        fj = int(getattr(existing, "condition_jump_false", -1) if existing else -1)
        self.true_jump.setValue(tj + 1 if tj >= 0 else 0)
        self.false_jump.setValue(fj + 1 if fj >= 0 else 0)
        body_lo.addWidget(label("Jump targets"))
        jump_row = QHBoxLayout()
        jump_row.addWidget(QLabel("True →")); jump_row.addWidget(self.true_jump)
        jump_row.addWidget(QLabel("False →")); jump_row.addWidget(self.false_jump)
        body_lo.addLayout(jump_row)

        lo.addWidget(body)
        lo.addLayout(make_buttons(self, "Save Condition", C["condition"], self._on_ok, "check"))

    def _on_ok(self):
        self._accepted = True
        self.accept()

    def get_action(self):
        a = self._existing or Action("[CONDITION]", 0.0, action_type="condition")
        a.key = "[CONDITION]"
        a.duration = 0.0
        a.action_type = "condition"
        a.label = self.label_edit.text().strip()
        a.condition_type = self.type_combo.currentText()
        a.condition_x = self.x_spin.value()
        a.condition_y = self.y_spin.value()
        a.condition_color = self.color_edit.text().strip()
        a.condition_var_name = self.var_name.text().strip()
        a.condition_var_value = self.var_value.text().strip()
        a.condition_jump_true = self.true_jump.value() - 1 if self.true_jump.value() > 0 else -1
        a.condition_jump_false = self.false_jump.value() - 1 if self.false_jump.value() > 0 else -1
        return a

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

        self.true_jump = QComboBox()
        self.false_jump = QComboBox()

        def add_targets(combo):
            combo.addItem("Next row", -1)
            group_meta = {}
            try:
                if parent is not None and hasattr(parent, "_group_headers"):
                    group_meta = {m["row"]: m for m in parent._group_headers()}
            except Exception:
                group_meta = {}
            for row in range(max(0, self._row_count)):
                meta = group_meta.get(row)
                if meta:
                    combo.addItem(f"{meta['badge']} {meta['name']}  · row {row + 1}", row)
                else:
                    combo.addItem(f"Row {row + 1}", row)

        def select_target(combo, target):
            for i in range(combo.count()):
                if int(combo.itemData(i)) == int(target):
                    combo.setCurrentIndex(i)
                    return
            combo.setCurrentIndex(0)

        add_targets(self.true_jump)
        add_targets(self.false_jump)
        tj = int(getattr(existing, "condition_jump_true", -1) if existing else -1)
        fj = int(getattr(existing, "condition_jump_false", -1) if existing else -1)
        select_target(self.true_jump, tj)
        select_target(self.false_jump, fj)
        body_lo.addWidget(label("Jump targets"))
        jump_row = QHBoxLayout()
        jump_row.addWidget(QLabel("True →")); jump_row.addWidget(self.true_jump)
        jump_row.addWidget(QLabel("False →")); jump_row.addWidget(self.false_jump)
        body_lo.addLayout(jump_row)

        self.retry_attempts = QSpinBox(); self.retry_attempts.setRange(1, 99)
        self.retry_attempts.setValue(max(1, int(getattr(existing, "retry_attempts", 1) if existing else 1)))
        self.retry_delay = field(str(getattr(existing, "retry_delay", 0.25) if existing else 0.25))
        retry_row = QHBoxLayout(); retry_row.addWidget(self.retry_attempts); retry_row.addWidget(self.retry_delay)
        body_lo.addWidget(label("Smart retry attempts / delay")); body_lo.addLayout(retry_row)

        self.fail_mode = QComboBox(); self.fail_mode.addItems(["default", "continue", "stop", "jump", "recovery_group"])
        self.fail_mode.setCurrentText(getattr(existing, "on_fail_action", "default") if existing else "default")
        self.fail_target = QComboBox(); add_targets(self.fail_target); select_target(self.fail_target, int(getattr(existing, "on_fail_target", -1) if existing else -1))
        body_lo.addWidget(label("On false/fail")); body_lo.addWidget(self.fail_mode); body_lo.addWidget(label("Fail target")); body_lo.addWidget(self.fail_target)

        hint = QLabel("Targets can point to normal rows or folder headers such as F1/F2. Recovery mode jumps to the first recovery folder if no target is chosen.")
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {C['text_dark']}; font-size: 10px; background: transparent;")
        body_lo.addWidget(hint)

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
        a.condition_jump_true = int(self.true_jump.currentData() if self.true_jump.currentData() is not None else -1)
        a.condition_jump_false = int(self.false_jump.currentData() if self.false_jump.currentData() is not None else -1)
        a.retry_attempts = int(self.retry_attempts.value())
        a.retry_delay = float(self.retry_delay.text() or 0)
        a.on_fail_action = self.fail_mode.currentText()
        a.on_fail_target = int(self.fail_target.currentData() if self.fail_target.currentData() is not None else -1)
        return a

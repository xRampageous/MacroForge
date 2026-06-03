from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QLineEdit, QCheckBox, QFrame

from models import Action
from ui.theme import COLORS
from ui.dialogs._common import dialog_stylesheet, make_header, make_buttons


class GroupDialog(QDialog):
    """Create/edit a visual group/folder header."""

    def __init__(self, parent=None, existing=None):
        super().__init__(parent)
        C = COLORS
        accent = C.get("group", C["neon_purple"])
        self.setWindowTitle("Action Group")
        self.setMinimumWidth(360)
        self.setStyleSheet(dialog_stylesheet(accent))
        self._existing = existing

        lo = QVBoxLayout(self)
        lo.setContentsMargins(16, 16, 16, 16)
        lo.setSpacing(12)
        lo.addWidget(make_header("Action Group", accent, "folder", "Add a visual folder header to organise large macros."))

        body = QFrame(); body.setObjectName("body")
        body.setStyleSheet(f"QFrame#body {{ background: {C['bg_card']}; border: 1px solid {C['border']}; border-radius: 10px; }}")
        body_lo = QVBoxLayout(body); body_lo.setContentsMargins(12, 12, 12, 12); body_lo.setSpacing(8)
        lbl = QLabel("Group name")
        lbl.setStyleSheet(f"color: {C['text_dim']}; font-size: 11px; font-weight: 700; background: transparent;")
        self.name_edit = QLineEdit(getattr(existing, "group_name", "") or getattr(existing, "label", "") if existing else "")
        self.name_edit.setPlaceholderText("Group name")
        self.collapsed = QCheckBox("Start collapsed")
        self.collapsed.setChecked(bool(getattr(existing, "group_collapsed", False) if existing else False))
        self.collapsed.setStyleSheet(f"color: {C['text']}; background: transparent;")
        self.recovery = QCheckBox("Recovery group")
        self.recovery.setToolTip("Recovery groups can be targeted by smart retry/on-fail rules")
        self.recovery.setChecked(getattr(existing, "group_role", "normal") == "recovery" if existing else False)
        self.recovery.setStyleSheet(f"color: {C['text']}; background: transparent;")
        body_lo.addWidget(lbl); body_lo.addWidget(self.name_edit); body_lo.addWidget(self.collapsed); body_lo.addWidget(self.recovery)
        lo.addWidget(body)
        lo.addLayout(make_buttons(self, "Save Group", accent, self.accept, "folder"))

    def get_action(self):
        name = self.name_edit.text().strip() or "Group"
        a = self._existing or Action("[GROUP]", 0.0, action_type="group")
        a.key = "[GROUP]"
        a.duration = 0.0
        a.action_type = "group"
        a.label = name
        a.group_name = name
        a.group_collapsed = self.collapsed.isChecked()
        a.group_role = "recovery" if self.recovery.isChecked() else "normal"
        return a

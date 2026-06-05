"""Settings dialog — modern PyQt6 rebuild with editable hotkeys."""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QLineEdit,
    QPushButton, QCheckBox, QSpinBox, QFrame, QScrollArea, QWidget
)
from ui.theme import COLORS
from ui.dialogs._common import dialog_stylesheet, make_header, make_buttons


HOTKEY_ROWS = [
    ("play_pause", "Start / Pause", "Space"),
    ("stop_deselect", "Stop / Deselect", "Escape"),
    ("record", "Record", "F7"),
    ("preflight", "Pre-flight", "Ctrl+Shift+P"),
    ("macro_editor", "Macro editor", "Ctrl+E"),
    ("toggle_runtime_log", "Toggle runtime log", "Ctrl+Shift+L"),
    ("profile_library", "Profile library", "Ctrl+Alt+P"),
    ("variables", "Macro variables", "Ctrl+Alt+V"),
    ("group", "Folder selected", "Ctrl+G"),
    ("ungroup", "Ungroup", "Ctrl+Shift+G"),
    ("select_all", "Select all", "Ctrl+A"),
    ("duplicate", "Duplicate selected", "Ctrl+D"),
    ("delete", "Delete selected", "Delete"),
    ("undo", "Undo", "Ctrl+Z"),
    ("redo", "Redo", "Ctrl+Y"),
    ("search", "Timeline search", "Ctrl+F"),
    ("run_from_selected", "Run from selected", "Ctrl+Enter"),
    ("save", "Save session", "Ctrl+S"),
]


class SettingsDialog(QDialog):
    def __init__(self, parent=None, settings_manager=None):
        super().__init__(parent)
        self.settings_manager = settings_manager
        self.setWindowTitle("Settings")
        self.setMinimumWidth(560)
        self.resize(620, 700)
        C = COLORS
        self._accent = C['accent']
        self.setStyleSheet(dialog_stylesheet(self._accent))

        lo = QVBoxLayout(self)
        lo.setSpacing(9)
        lo.setContentsMargins(16, 16, 16, 14)

        lo.addWidget(make_header("Settings", self._accent, "settings", "Application preferences, hotkeys, and editor behavior"))

        retry_row = QHBoxLayout()
        retry_row.addWidget(QLabel("Retry count"))
        self.retry = QSpinBox()
        self.retry.setRange(0, 20)
        self.retry.setValue(self.settings_manager.settings.get("retry_count", 3))
        retry_row.addWidget(self.retry)
        retry_row.addStretch()
        lo.addLayout(retry_row)

        delay_row = QHBoxLayout()
        delay_row.addWidget(QLabel("Retry delay (s)"))
        self.delay = QLineEdit(str(self.settings_manager.settings.get("retry_delay", 0.1)))
        self.delay.setFixedWidth(72)
        delay_row.addWidget(self.delay)
        delay_row.addStretch()
        lo.addLayout(delay_row)

        self.auto_save = QCheckBox("Auto-save session")
        self.auto_save.setChecked(self.settings_manager.settings.get("auto_save", True))
        lo.addWidget(self.auto_save)

        self.minimize_tray = QCheckBox("Minimize to tray")
        self.minimize_tray.setChecked(self.settings_manager.settings.get("minimize_tray", True))
        lo.addWidget(self.minimize_tray)

        title = QLabel("Hotkey editor")
        title.setStyleSheet(f"color: {COLORS['text']}; font-size: 13px; font-weight: 900; margin-top: 8px;")
        lo.addWidget(title)

        hint = QLabel("Change a shortcut, save, and the active shortcuts + help text update immediately. Leave a field blank to disable that shortcut.")
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 11px;")
        lo.addWidget(hint)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumHeight(360)
        scroll.setStyleSheet(
            f"QScrollArea {{ background-color: {COLORS['bg_card']}; border: 1px solid {COLORS['border']}; border-radius: 9px; }}"
            "QScrollArea > QWidget > QWidget { background: transparent; }"
        )
        hotkey_host = QWidget()
        grid = QGridLayout(hotkey_host)
        grid.setContentsMargins(10, 10, 10, 10)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(6)
        grid.addWidget(QLabel("Action"), 0, 0)
        grid.addWidget(QLabel("Shortcut"), 0, 1)
        self.hotkey_inputs = {}
        stored = self.settings_manager.settings.setdefault("hotkeys", {})
        for row, (key, label, default) in enumerate(HOTKEY_ROWS, 1):
            lbl = QLabel(label)
            lbl.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 11px;")
            inp = QLineEdit(stored.get(key, default))
            inp.setPlaceholderText(default)
            inp.setStyleSheet(
                f"QLineEdit {{ background-color: {COLORS['bg_tertiary']}; color: {COLORS['text']}; "
                f"border: 1px solid {COLORS['border']}; border-radius: 7px; padding: 5px 8px; font-size: 11px; }}"
                f"QLineEdit:focus {{ border-color: {COLORS['accent']}; }}"
            )
            self.hotkey_inputs[key] = (inp, default)
            grid.addWidget(lbl, row, 0)
            grid.addWidget(inp, row, 1)
        scroll.setWidget(hotkey_host)
        lo.addWidget(scroll, 1)

        self.hotkeys_preview = QLabel()
        self.hotkeys_preview.setWordWrap(True)
        self.hotkeys_preview.setStyleSheet(
            f"color: {COLORS['text_dim']}; font-size: 11px; line-height: 1.35; "
            f"background-color: {COLORS['bg_card']}; border: 1px solid {COLORS['border']}; "
            "border-radius: 8px; padding: 8px;"
        )
        lo.addWidget(self.hotkeys_preview)
        self._refresh_preview()
        for inp, _ in self.hotkey_inputs.values():
            inp.textChanged.connect(self._refresh_preview)

        lo.addLayout(make_buttons(self, "Save", self._accent, self._save, "save"))

    def _refresh_preview(self):
        try:
            def val(key):
                inp, default = self.hotkey_inputs[key]
                return inp.text().strip() or "disabled"
            self.hotkeys_preview.setText(
                f"Playback: {val('play_pause')} start/pause · {val('stop_deselect')} stop/deselect · {val('toggle_runtime_log')} runtime log\n"
                f"Editor: {val('select_all')} select all · {val('duplicate')} duplicate · {val('delete')} delete · {val('group')} folder · {val('ungroup')} ungroup\n"
                f"Tools: {val('preflight')} pre-flight · {val('macro_editor')} macro editor · {val('profile_library')} library · {val('variables')} variables"
            )
        except Exception:
            pass

    def _save(self):
        self.settings_manager.settings["retry_count"] = self.retry.value()
        self.settings_manager.settings["retry_delay"] = float(self.delay.text())
        self.settings_manager.settings["auto_save"] = self.auto_save.isChecked()
        self.settings_manager.settings["minimize_tray"] = self.minimize_tray.isChecked()
        hotkeys = self.settings_manager.settings.setdefault("hotkeys", {})
        for key, (inp, default) in self.hotkey_inputs.items():
            hotkeys[key] = inp.text().strip()
        self.settings_manager.save()
        parent = self.parent()
        if parent is not None and hasattr(parent, "reload_shortcuts"):
            parent.reload_shortcuts()
        self.accept()

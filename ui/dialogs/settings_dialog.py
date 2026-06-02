"""Settings dialog — modern PyQt6 rebuild."""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QCheckBox, QSpinBox
)
from ui.theme import COLORS
from ui.dialogs._common import dialog_stylesheet, make_header, make_buttons


class SettingsDialog(QDialog):
    def __init__(self, parent=None, settings_manager=None):
        super().__init__(parent)
        self.settings_manager = settings_manager
        self.setWindowTitle("Settings")
        self.setMinimumWidth(400)
        C = COLORS
        self._accent = C['accent']
        self.setStyleSheet(dialog_stylesheet(self._accent))

        lo = QVBoxLayout(self)
        lo.setSpacing(9)
        lo.setContentsMargins(16, 16, 16, 14)

        lo.addWidget(make_header("Settings", self._accent, "settings", "Application preferences"))

        # Retry count
        retry_row = QHBoxLayout()
        retry_row.addWidget(QLabel("Retry count"))
        self.retry = QSpinBox()
        self.retry.setRange(0, 20)
        self.retry.setValue(self.settings_manager.settings.get("retry_count", 3))
        retry_row.addWidget(self.retry)
        retry_row.addStretch()
        lo.addLayout(retry_row)

        # Retry delay
        delay_row = QHBoxLayout()
        delay_row.addWidget(QLabel("Retry delay (s)"))
        self.delay = QLineEdit(str(self.settings_manager.settings.get("retry_delay", 0.1)))
        self.delay.setFixedWidth(60)
        delay_row.addWidget(self.delay)
        delay_row.addStretch()
        lo.addLayout(delay_row)

        # Checkboxes
        self.auto_save = QCheckBox("Auto-save session")
        self.auto_save.setChecked(self.settings_manager.settings.get("auto_save", True))
        lo.addWidget(self.auto_save)

        self.minimize_tray = QCheckBox("Minimize to tray")
        self.minimize_tray.setChecked(self.settings_manager.settings.get("minimize_tray", True))
        lo.addWidget(self.minimize_tray)

        lo.addStretch()
        lo.addLayout(make_buttons(self, "Save", self._accent, self._save, "save"))

    def _save(self):
        self.settings_manager.settings["retry_count"] = self.retry.value()
        self.settings_manager.settings["retry_delay"] = float(self.delay.text())
        self.settings_manager.settings["auto_save"] = self.auto_save.isChecked()
        self.settings_manager.settings["minimize_tray"] = self.minimize_tray.isChecked()
        self.settings_manager.save()
        self.accept()

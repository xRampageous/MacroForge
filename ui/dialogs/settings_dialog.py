"""Settings dialog — modern PyQt6 rebuild."""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QCheckBox, QSpinBox
)
from ui.theme import COLORS


class SettingsDialog(QDialog):
    def __init__(self, parent=None, settings_manager=None):
        super().__init__(parent)
        self.settings_manager = settings_manager
        self.setWindowTitle("Settings")
        self.setMinimumWidth(400)
        C = COLORS
        self.setStyleSheet(f"""
            QDialog {{ background-color: {C['bg']}; }}
            QLabel {{ color: {C['text_dim']}; font-size: 12px; }}
            QLineEdit {{ background-color: {C['bg_tertiary']}; color: {C['text']}; border: 1px solid {C['border']}; border-radius: 8px; padding: 6px 10px; font-size: 12px; }}
            QLineEdit:focus {{ border-color: {C['accent']}; }}
            QSpinBox {{ background-color: {C['bg_tertiary']}; color: {C['text']}; border: 1px solid {C['border']}; border-radius: 8px; padding: 6px 10px; }}
            QCheckBox {{ color: {C['text_dim']}; font-size: 12px; }}
            QCheckBox::indicator {{ width: 16px; height: 16px; border: 1px solid {C['border']}; border-radius: 5px; }}
            QCheckBox::indicator:checked {{ background-color: {C['accent']}; border-color: {C['accent']}; }}
        """)

        lo = QVBoxLayout(self)
        lo.setSpacing(10)
        lo.setContentsMargins(16, 16, 16, 16)

        hdr = QLabel("SETTINGS")
        hdr.setStyleSheet(f"color: {C['accent']}; font-size: 10px; font-weight: 700; letter-spacing: 1.5px;")
        lo.addWidget(hdr)

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
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel = QPushButton("Cancel")
        cancel.setStyleSheet(f"background-color: {C['bg_tertiary']}; color: {C['text']}; border: 1px solid {C['border']}; border-radius: 10px; padding: 8px 16px;")
        cancel.clicked.connect(self.reject)
        ok = QPushButton("Save")
        ok.setStyleSheet(f"background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 {C['accent']},stop:1 {C['accent_secondary']}); color: {C['text_inverse']}; border: none; border-radius: 10px; padding: 8px 16px; font-weight: 700;")
        ok.clicked.connect(self._save)
        btn_row.addWidget(cancel)
        btn_row.addWidget(ok)
        lo.addLayout(btn_row)

    def _save(self):
        self.settings_manager.settings["retry_count"] = self.retry.value()
        self.settings_manager.settings["retry_delay"] = float(self.delay.text())
        self.settings_manager.settings["auto_save"] = self.auto_save.isChecked()
        self.settings_manager.settings["minimize_tray"] = self.minimize_tray.isChecked()
        self.settings_manager.save()
        self.accept()

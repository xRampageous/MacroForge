"""Settings dialog for MacroForge PyQt6."""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QCheckBox, QDoubleSpinBox,
    QSpinBox, QPushButton, QHBoxLayout, QLabel, QTabWidget, QWidget,
    QLineEdit, QMessageBox
)
from PyQt6.QtCore import Qt

from ui.theme import COLORS
from version import VERSION


class SettingsDialog(QDialog):
    """Application settings with tabs."""

    def __init__(self, parent, settings_manager):
        super().__init__(parent)
        self._mgr = settings_manager
        self.setWindowTitle("Settings")
        self.resize(480, 380)
        self.setStyleSheet(f"""
            QDialog {{ background-color: {COLORS['bg']}; }}
        """)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        tabs = QTabWidget()

        # General tab
        general = QWidget()
        gen_layout = QFormLayout(general)
        gen_layout.setSpacing(10)

        self._chk_auto_save = QCheckBox()
        self._chk_auto_save.setChecked(self._mgr.get("auto_save", True))
        gen_layout.addRow("Auto-save session:", self._chk_auto_save)

        self._chk_start_min = QCheckBox()
        self._chk_start_min.setChecked(self._mgr.get("start_minimized", False))
        gen_layout.addRow("Start minimized:", self._chk_start_min)

        self._spin_def_speed = QDoubleSpinBox()
        self._spin_def_speed.setRange(0.1, 10.0)
        self._spin_def_speed.setSingleStep(0.1)
        self._spin_def_speed.setValue(self._mgr.get("default_speed", 1.0))
        gen_layout.addRow("Default speed:", self._spin_def_speed)

        self._spin_def_loops = QSpinBox()
        self._spin_def_loops.setRange(1, 9999)
        self._spin_def_loops.setValue(self._mgr.get("default_loops", 1))
        gen_layout.addRow("Default loops:", self._spin_def_loops)

        self._chk_debug = QCheckBox()
        self._chk_debug.setChecked(self._mgr.get("debug_mode", False))
        gen_layout.addRow("Debug logging:", self._chk_debug)

        tabs.addTab(general, "General")

        # Hotkeys tab
        hotkeys = QWidget()
        hk_layout = QFormLayout(hotkeys)
        hk_layout.setSpacing(10)

        self._hk_play = QLineEdit(self._mgr.get("hk_play", "<f5>"))
        hk_layout.addRow("Play / Pause:", self._hk_play)

        self._hk_stop = QLineEdit(self._mgr.get("hk_stop", "<f6>"))
        hk_layout.addRow("Stop:", self._hk_stop)

        self._hk_record = QLineEdit(self._mgr.get("hk_record", "<f7>"))
        hk_layout.addRow("Record:", self._hk_record)

        self._hk_stop_rec = QLineEdit(self._mgr.get("hk_stop_rec", "<f9>"))
        hk_layout.addRow("Stop Recording:", self._hk_stop_rec)

        tabs.addTab(hotkeys, "Hotkeys")

        # About tab
        about = QWidget()
        ab_layout = QVBoxLayout(about)
        ab_layout.setSpacing(10)

        ab_layout.addWidget(QLabel(f"<h2 style='color:{COLORS['accent']}'>MacroForge</h2>"))
        ab_layout.addWidget(QLabel(f"Version: {VERSION}"))
        ab_layout.addWidget(QLabel("A powerful macro automation tool."))
        ab_layout.addWidget(QLabel(f"<a style='color:{COLORS['neon_blue']}' href='https://github.com/xRampageous/MacroForge'>GitHub</a>"))
        ab_layout.addStretch()
        tabs.addTab(about, "About")

        layout.addWidget(tabs)

        btn_box = QHBoxLayout()
        btn_ok = QPushButton("Save")
        btn_ok.setObjectName("accent")
        btn_ok.clicked.connect(self._save)
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_box.addStretch()
        btn_box.addWidget(btn_ok)
        btn_box.addWidget(btn_cancel)
        layout.addLayout(btn_box)

    def _save(self):
        self._mgr.set("auto_save", self._chk_auto_save.isChecked())
        self._mgr.set("start_minimized", self._chk_start_min.isChecked())
        self._mgr.set("default_speed", self._spin_def_speed.value())
        self._mgr.set("default_loops", self._spin_def_loops.value())
        self._mgr.set("debug_mode", self._chk_debug.isChecked())
        self._mgr.set("hk_play", self._hk_play.text())
        self._mgr.set("hk_stop", self._hk_stop.text())
        self._mgr.set("hk_record", self._hk_record.text())
        self._mgr.set("hk_stop_rec", self._hk_stop_rec.text())
        self._mgr.save()
        self.accept()

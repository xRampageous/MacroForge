"""
debugger.py – File-based logger + in-app debug viewer for MacroForge.
Works when frozen as .exe (no console available).
"""

import os
import sys
import time
from datetime import datetime
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton, QCheckBox
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor
from ui.theme import COLORS


class DebugLogger:
    """Singleton file logger.  Writes to <app_dir>/debug.log"""

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, log_dir=None):
        if self._initialized:
            return
        self._initialized = True

        if log_dir is None:
            # Frozen exe -> use exe dir; source -> use script dir
            if getattr(sys, "frozen", False):
                base = os.path.dirname(sys.executable)
            else:
                base = os.path.dirname(os.path.abspath(__file__))
            log_dir = base

        self.log_path = os.path.join(log_dir, "debug.log")
        self._entries = []          # [(ts, level, msg), ...]
        self._listeners = []        # callables(msg)
        self._approx_size = 0       # approximate bytes written since last rotation
        self._write("=" * 60)
        self._write(f"MacroForge Debug Log – {datetime.now().isoformat()}")
        self._write("=" * 60)

    # ── public API ──────────────────────────────────────────

    def debug(self, msg: str):
        self._log("DEBUG", msg)

    def info(self, msg: str):
        self._log("INFO", msg)

    def warn(self, msg: str):
        self._log("WARN", msg)

    def error(self, msg: str):
        self._log("ERROR", msg)

    def get_entries(self):
        """Return list of (ts, level, msg) tuples."""
        return list(self._entries)

    def add_listener(self, callback):
        """callback receives a formatted string."""
        self._listeners.append(callback)

    def remove_listener(self, callback):
        try:
            self._listeners.remove(callback)
        except ValueError:
            pass

    # ── internals ───────────────────────────────────────────

    def _log(self, level: str, msg: str):
        ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        line = f"[{ts}] {level:5s} | {msg}"
        self._entries.append((ts, level, msg))
        self._write(line)
        for cb in self._listeners:
            try:
                cb(line)
            except Exception:
                pass

    def _write(self, text: str):
        try:
            line = text + "\n"
            self._approx_size += len(line.encode("utf-8"))
            if self._approx_size > 5 * 1024 * 1024:
                self._approx_size = len(line.encode("utf-8"))
                old_path = self.log_path + ".old"
                try:
                    if os.path.exists(old_path):
                        os.remove(old_path)
                    if os.path.exists(self.log_path):
                        os.rename(self.log_path, old_path)
                except Exception:
                    pass
                with open(self.log_path, "w", encoding="utf-8") as f:
                    f.write(line)
                    f.flush()
                    os.fsync(f.fileno())
            else:
                with open(self.log_path, "a", encoding="utf-8") as f:
                    f.write(line)
                    f.flush()
                    os.fsync(f.fileno())
        except Exception:
            pass


# convenience singleton accessor
logger = DebugLogger()


def get_log_path() -> str:
    """Return path to current debug log file."""
    return logger.log_path


# =====================================================================
#  In-app debug viewer window (PyQt6)
# =====================================================================

class DebugViewer(QDialog):
    """A floating window that tails the debug log."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("MacroForge Debug Log")
        self.setMinimumSize(800, 400)
        self.resize(800, 400)
        self.setStyleSheet(f"""
            QDialog {{ background-color: {COLORS['bg']}; }}
            QTextEdit {{ background-color: {COLORS['bg']}; color: {COLORS['text']}; font-family: Consolas; font-size: 9pt; border: none; }}
            QPushButton {{ background-color: {COLORS['bg_tertiary']}; color: {COLORS['text']}; border: 1px solid {COLORS['border']}; padding: 4px 12px; border-radius: 4px; }}
            QPushButton:hover {{ background-color: {COLORS['border']}; }}
            QCheckBox {{ color: {COLORS['text']}; }}
        """)
        self._build_ui()
        self._seed_history()
        logger.add_listener(self._append_line)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)

        self._auto_scroll = True
        self._auto_scroll_cb = QCheckBox("Auto-scroll")
        self._auto_scroll_cb.setChecked(True)
        self._auto_scroll_cb.toggled.connect(self._set_auto_scroll)
        toolbar.addWidget(self._auto_scroll_cb)

        toolbar.addStretch()

        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self._clear)
        toolbar.addWidget(clear_btn)

        open_btn = QPushButton("Open log file")
        open_btn.clicked.connect(self._open_log)
        toolbar.addWidget(open_btn)

        layout.addLayout(toolbar)

        # Text area
        self.text = QTextEdit()
        self.text.setReadOnly(True)
        self.text.setFont(QFont("Consolas", 9))
        layout.addWidget(self.text)

    def _set_auto_scroll(self, checked):
        self._auto_scroll = checked

    def _seed_history(self):
        for ts, level, msg in logger.get_entries():
            self._insert(ts, level, msg)

    def _append_line(self, line: str):
        parts = line.split(" | ", 1)
        if len(parts) == 2:
            header = parts[0]
            msg = parts[1]
            level = header.split("] ")[1].strip() if "] " in header else "INFO"
            ts = header[1:].split("]")[0] if header.startswith("[") else ""
        else:
            ts, level, msg = "", "INFO", line
        self._insert(ts, level, msg)

    def _insert(self, ts: str, level: str, msg: str):
        color_map = {
            "INFO": "#4ade80",
            "WARN": "#fbbf24",
            "ERROR": "#f87171"
        }
        color = color_map.get(level, COLORS["text"])
        self.text.setTextColor(QColor(color))
        self.text.append(f"[{ts}] {level:5s} | {msg}")
        if self._auto_scroll:
            sb = self.text.verticalScrollBar()
            sb.setValue(sb.maximum())

    def _clear(self):
        self.text.clear()

    def _open_log(self):
        import subprocess
        try:
            subprocess.run(["notepad.exe", logger.log_path], check=False)
        except Exception:
            pass

    def closeEvent(self, event):
        logger.remove_listener(self._append_line)
        super().closeEvent(event)

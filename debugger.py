"""
debugger.py – File-based logger + in-app debug viewer for MacroForge.
Works when frozen as .exe (no console available).
"""

import os
import sys
import time
from datetime import datetime
import traceback
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton, QCheckBox
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor
try:
    from ui.theme import COLORS
except Exception:
    # Startup-safe fallback: the full app still requires ui/theme.py, but the
    # debugger should never be the first module to crash when a partial patch or
    # stale PyInstaller cache is missing the theme module.
    COLORS = {
        "bg": "#000207",
        "bg_secondary": "#010711",
        "bg_card": "#020A13",
        "border": "#143047",
        "accent": "#0096FF",
        "accent_glow": "rgba(0, 150, 255, 0.18)",
        "text": "#F3F6FA",
        "text_dim": "#B0C0D6",
        "success": "#00D75A",
        "warning": "#FFD000",
        "error": "#FF2330",
    }


MAX_LOG_LINES = 10000
LOG_TRIM_CHECK_INTERVAL = 250


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
        self.max_log_lines = MAX_LOG_LINES
        self._write_count = 0
        self._entries = []          # [(ts, level, msg), ...]
        self._listeners = []        # callables(msg)
        self._trim_log_file(force=True)
        self._write("=" * 60)
        self._write(f"MacroForge Debug Log – {datetime.now().isoformat()}")
        self._write("=" * 60)

    # ── public API ──────────────────────────────────────────

    def debug(self, msg: str, *args):
        self._log("DEBUG", msg, *args)

    def info(self, msg: str, *args):
        self._log("INFO", msg, *args)

    def warning(self, msg: str, *args):
        self._log("WARN", msg, *args)

    def warn(self, msg: str, *args):
        self.warning(msg, *args)

    def error(self, msg: str, *args):
        self._log("ERROR", msg, *args)

    def exception(self, msg: str, *args):
        trace = traceback.format_exc().strip()
        details = self._format_message(msg, *args)
        if trace and trace != "NoneType: None":
            details = f"{details}\n{trace}"
        self._log("ERROR", details)

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

    def clear(self):
        """Clear in-memory and on-disk debug log."""
        self._entries.clear()
        try:
            with open(self.log_path, "w", encoding="utf-8") as f:
                f.write("")
        except Exception:
            pass

    # ── internals ───────────────────────────────────────────

    @staticmethod
    def _format_message(msg, *args):
        if not args:
            return str(msg)
        try:
            return str(msg) % args
        except Exception:
            return " ".join([str(msg), *(repr(arg) for arg in args)])

    def _log(self, level: str, msg: str, *args):
        msg = self._format_message(msg, *args)
        ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        line = f"[{ts}] {level:5s} | {msg}"
        self._entries.append((ts, level, msg))
        if len(self._entries) > self.max_log_lines:
            self._entries = self._entries[-self.max_log_lines:]
        self._write_line(line)
        for cb in self._listeners:
            try:
                cb(line)
            except Exception:
                pass

    def _write(self, text: str):
        """Write a plain informational line and keep it in the bounded buffer."""
        ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        self._entries.append((ts, "INFO", text))
        if len(self._entries) > self.max_log_lines:
            self._entries = self._entries[-self.max_log_lines:]
        self._write_line(text)

    def _write_line(self, line: str):
        """Append one line to disk and periodically trim the file to max_log_lines."""
        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
                f.flush()
                os.fsync(f.fileno())
            self._write_count += 1
            if self._write_count >= LOG_TRIM_CHECK_INTERVAL:
                self._write_count = 0
                self._trim_log_file(force=False)
        except Exception:
            pass

    def _trim_log_file(self, force=False):
        """Keep the debug log from growing indefinitely.

        The newest 10,000 lines are preserved. Older lines are discarded.
        """
        try:
            if not os.path.exists(self.log_path):
                return
            with open(self.log_path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
            if force or len(lines) > self.max_log_lines:
                if len(lines) > self.max_log_lines:
                    with open(self.log_path, "w", encoding="utf-8") as f:
                        f.writelines(lines[-self.max_log_lines:])
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
            QDialog {{
                background-color: {COLORS['bg']};
                color: {COLORS['text']};
            }}
            QTextEdit {{
                background-color: {COLORS['bg_card']};
                color: {COLORS['text']};
                font-family: Consolas;
                font-size: 9pt;
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
                padding: 8px;
            }}
            QPushButton {{
                background-color: {COLORS['bg_tertiary']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                padding: 6px 14px;
                border-radius: 8px;
                font-weight: 800;
            }}
            QPushButton:hover {{
                border-color: {COLORS['accent']};
                background-color: {COLORS['bg_secondary']};
            }}
            QCheckBox {{
                color: {COLORS['text']};
                font-weight: 700;
                spacing: 6px;
            }}
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
        logger.clear()
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

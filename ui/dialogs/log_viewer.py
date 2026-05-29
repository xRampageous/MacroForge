"""Log viewer dialog for MacroForge PyQt6."""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTextEdit,
    QLineEdit, QLabel
)
from PyQt6.QtCore import Qt

from ui.theme import COLORS
from debugger import logger
import logging


class LogViewerDialog(QDialog):
    """Filterable and refreshable debug log viewer."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Debug Logs")
        self.resize(700, 500)
        self.setStyleSheet(f"""
            QDialog {{ background-color: {COLORS['bg']}; }}
        """)
        self._build_ui()
        self._refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("Filter:"))
        self._filter = QLineEdit()
        self._filter.setPlaceholderText("Type to filter...")
        self._filter.textChanged.connect(self._apply_filter)
        toolbar.addWidget(self._filter)

        btn_refresh = QPushButton("Refresh")
        btn_refresh.clicked.connect(self._refresh)
        toolbar.addWidget(btn_refresh)

        btn_clear = QPushButton("Clear")
        btn_clear.clicked.connect(self._clear)
        toolbar.addWidget(btn_clear)

        layout.addLayout(toolbar)

        # Log text
        self._text = QTextEdit()
        self._text.setReadOnly(True)
        self._text.setStyleSheet(f"""
            QTextEdit {{
                background-color: {COLORS['bg_secondary']};
                color: {COLORS['text_dim']};
                font-family: 'Consolas', monospace;
                font-size: 11px;
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
            }}
        """)
        layout.addWidget(self._text)

        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.close)
        layout.addWidget(btn_close)

    def _refresh(self):
        try:
            from debugger import get_log_path
            path = get_log_path()
            if path and __import__('os').path.exists(path):
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    text = f.read()
            else:
                text = "Log file not available."
        except Exception as e:
            text = f"Could not load logs: {e}"
        self._text.setPlainText(text)
        self._text.moveCursor(self._text.textCursor().End)

    def _clear(self):
        try:
            from debugger import get_log_path
            path = get_log_path()
            if path:
                with open(path, "w", encoding="utf-8") as f:
                    f.write("")
        except Exception:
            pass
        self._text.clear()

    def _apply_filter(self, text: str):
        if not text:
            self._text.setPlainText(self._text.toPlainText())
            return
        lines = [l for l in self._text.toPlainText().split("\n") if text.lower() in l.lower()]
        self._text.setPlainText("\n".join(lines))

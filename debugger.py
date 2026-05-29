"""
debugger.py – File-based logger + in-app debug viewer for MacroForge.
Works when frozen as .exe (no console available).
"""

import os
import sys
import time
import tkinter as tk
from tkinter import ttk
from datetime import datetime


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
            if os.path.exists(self.log_path) and os.path.getsize(self.log_path) > 5 * 1024 * 1024:
                with open(self.log_path, "w", encoding="utf-8") as f:
                    f.write(text + "\n")
            else:
                with open(self.log_path, "a", encoding="utf-8") as f:
                    f.write(text + "\n")
        except Exception:
            pass


# convenience singleton accessor
logger = DebugLogger()


# =====================================================================
#  In-app debug viewer window
# =====================================================================

class DebugViewer(tk.Toplevel):
    """A floating window that tails the debug log."""

    def __init__(self, master, colors: dict):
        super().__init__(master)
        self.title("MacroForge Debug Log")
        self.geometry("800x400")
        self.configure(bg=colors["bg_secondary"])
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self.colors = colors
        self._build_ui()
        self._seed_history()
        logger.add_listener(self._append_line)

    def _build_ui(self):
        C = self.colors
        toolbar = tk.Frame(self, bg=C["bg_secondary"], pady=4)
        toolbar.pack(fill="x", padx=6, pady=(4, 0))

        self._auto_scroll = tk.BooleanVar(value=True)
        tk.Checkbutton(toolbar, text="Auto-scroll", variable=self._auto_scroll,
                       bg=C["bg_secondary"], fg=C["text"],
                       selectcolor=C["accent"],
                       activebackground=C["bg_secondary"],
                       font=("Segoe UI", 8)).pack(side="left")

        tk.Button(toolbar, text="Clear", command=self._clear,
                  bg=C["bg_tertiary"], fg=C["text"],
                  relief="flat", font=("Segoe UI", 8),
                  cursor="hand2").pack(side="right")

        tk.Button(toolbar, text="Open log file", command=self._open_log,
                  bg=C["bg_tertiary"], fg=C["text"],
                  relief="flat", font=("Segoe UI", 8),
                  cursor="hand2").pack(side="right", padx=(0, 6))

        text_frame = tk.Frame(self, bg=C["bg_secondary"])
        text_frame.pack(fill="both", expand=True, padx=6, pady=6)

        self.text = tk.Text(
            text_frame,
            wrap="none",
            bg=C["bg"],
            fg=C["text"],
            insertbackground=C["accent"],
            font=("Consolas", 9),
            relief="flat",
            state="disabled",
            padx=6, pady=6
        )
        self.text.pack(side="left", fill="both", expand=True)

        sb = ttk.Scrollbar(text_frame, command=self.text.yview)
        sb.pack(side="right", fill="y")
        self.text.config(yscrollcommand=sb.set)

        # Colour tags
        self.text.tag_config("INFO", foreground="#4ade80")   # green
        self.text.tag_config("WARN", foreground="#fbbf24")   # yellow
        self.text.tag_config("ERROR", foreground="#f87171")  # red

    def _seed_history(self):
        for ts, level, msg in logger.get_entries():
            self._insert(ts, level, msg)

    def _append_line(self, line: str):
        # line format: [HH:MM:SS.mmm] LEVEL | msg
        parts = line.split(" | ", 1)
        if len(parts) == 2:
            header = parts[0]           # [ts] LEVEL
            msg = parts[1]
            level = header.split("] ")[1].strip() if "] " in header else "INFO"
            ts = header[1:].split("]")[0] if header.startswith("[") else ""
        else:
            ts, level, msg = "", "INFO", line
        self._insert(ts, level, msg)

    def _insert(self, ts: str, level: str, msg: str):
        self.text.config(state="normal")
        tag = level if level in ("INFO", "WARN", "ERROR") else None
        self.text.insert("end", f"[{ts}] {level:5s} | {msg}\n", tag)
        self.text.config(state="disabled")
        if self._auto_scroll.get():
            self.text.see("end")

    def _clear(self):
        self.text.config(state="normal")
        self.text.delete("1.0", "end")
        self.text.config(state="disabled")

    def _open_log(self):
        import subprocess
        try:
            subprocess.run(["notepad.exe", logger.log_path], check=False)
        except Exception:
            pass

    def _on_close(self):
        logger.remove_listener(self._append_line)
        self.destroy()

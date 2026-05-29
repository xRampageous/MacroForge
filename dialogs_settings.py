import tkinter as tk
from tkinter import ttk, messagebox

from models import SettingsManager
from debugger import logger


class SettingsEditorMixin:
    """Mixin that adds a Settings dialog for hotkeys, startup and defaults."""

    def open_settings_dialog(self):
        dlg, C = self._make_dialog("Settings", width=440)

        settings = self.settings_manager.all()
        hotkeys = settings.get("hotkeys", SettingsManager.DEFAULTS["hotkeys"])

        # ── Hotkeys section ──
        sec1 = self._dlg_section(dlg, "GLOBAL HOTKEYS", C["accent"])
        hk_vars = {}

        def hk_row(parent, label, key):
            row = tk.Frame(parent, bg=parent["bg"])
            row.pack(fill="x", pady=2)
            tk.Label(row, text=label, bg=parent["bg"], fg=C["text_dim"],
                     font=("Segoe UI", 9), width=14, anchor="w").pack(side="left")
            var = tk.StringVar(value=hotkeys.get(key, key))
            ent = tk.Entry(row, textvariable=var, width=10,
                           bg=C["bg"], fg=C["text"], insertbackground=C["accent"],
                           relief="flat", font=("Segoe UI", 9))
            ent.pack(side="left", padx=(0, 4))
            hk_vars[key] = var
            return var

        hk_row(sec1, "Start", "start")
        hk_row(sec1, "Stop", "stop")
        hk_row(sec1, "Record", "record")
        hk_row(sec1, "Toggle", "toggle")
        tk.Label(sec1, text="Tip: use lowercase key names (e.g. f5, ctrl, shift+f5)",
                 bg=sec1["bg"], fg=C["text_dim"],
                 font=("Segoe UI", 8, "italic")).pack(anchor="w", pady=(4, 0))

        # ── Startup section ──
        sec2 = self._dlg_section(dlg, "STARTUP", C["accent"])
        min_var = tk.BooleanVar(value=settings.get("start_minimized", False))
        tk.Checkbutton(sec2, text="Start minimized to system tray",
                       variable=min_var, bg=sec2["bg"], fg=C["text"],
                       selectcolor=C["accent_glow"],
                       activebackground=sec2["bg"],
                       font=("Segoe UI", 9)).pack(anchor="w")

        # ── Playback defaults ──
        sec3 = self._dlg_section(dlg, "PLAYBACK DEFAULTS", C["accent"])
        loop_var = tk.StringVar(value=str(settings.get("default_loops", 1)))
        speed_var = tk.StringVar(value=str(settings.get("default_speed", 1.0)))
        auto_var = tk.BooleanVar(value=settings.get("auto_save", True))

        def ent(parent, var, w=8):
            return tk.Entry(parent, textvariable=var, width=w,
                            bg=C["bg"], fg=C["text"], insertbackground=C["accent"],
                            relief="flat", font=("Segoe UI", 9))

        self._dlg_field(sec3, "Loop count", lambda p: ent(p, loop_var), "default repeats")
        self._dlg_field(sec3, "Speed", lambda p: ent(p, speed_var), "multiplier (0.5 = half)")
        tk.Checkbutton(sec3, text="Auto-save session on change",
                       variable=auto_var, bg=sec3["bg"], fg=C["text"],
                       selectcolor=C["accent_glow"],
                       activebackground=sec3["bg"],
                       font=("Segoe UI", 9)).pack(anchor="w", pady=(4, 0))

        def on_ok():
            try:
                loops = int(loop_var.get())
                speed = float(speed_var.get())
                if loops < 1:
                    raise ValueError
                if speed <= 0:
                    raise ValueError
            except ValueError:
                messagebox.showerror("Invalid", "Loops must be >= 1 and speed must be > 0", parent=dlg)
                return

            new_hotkeys = {k: v.get().strip().lower() or k for k, v in hk_vars.items()}
            self.settings_manager.set("hotkeys", new_hotkeys)
            self.settings_manager.set("start_minimized", min_var.get())
            self.settings_manager.set("default_loops", loops)
            self.settings_manager.set("default_speed", speed)
            self.settings_manager.set("auto_save", auto_var.get())

            # Apply playback defaults immediately
            self.loops_var.set(loops)
            self.speed_var.set(speed)

            # Restart global hotkey listener with new mappings
            self._restart_hotkey_listener()

            self.status("Settings saved")
            dlg.destroy()

        self._dlg_buttons(dlg, on_ok, dlg.destroy, ok_text="Save Settings")
        dlg.bind("<Return>", lambda e: on_ok())
        dlg.bind("<Escape>", lambda e: dlg.destroy())

    def _restart_hotkey_listener(self):
        """Stop and restart the pynput listener with updated key mappings."""
        try:
            self.listener.stop()
        except Exception:
            pass
        from pynput import keyboard
        self.listener = keyboard.Listener(on_press=self._on_key_press_global, suppress=False)
        self.listener.start()
        logger.info("Global hotkey listener restarted with new mappings")

import sys
import csv
import time
import json
import threading
import random
import os
import ctypes
import queue
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import Optional
from copy import deepcopy

import pyautogui
pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0.0
from pynput import keyboard

# Import CanvasTimeline for high-performance rendering
from CanvasTimeline import CanvasTimeline

# Vector icon system (replaces emoji icons)
from Icons import IconFactory

from models import Config, Action, HistoryManager, ProfileManager
from engine import ExecutionEngine
from debugger import logger, DebugViewer
from dialogs_key_editor import KeyEditorMixin
from dialogs_pause_editor import PauseEditorMixin
from dialogs_click_editor import ClickEditorMixin
from dialogs_image_editor import ImageEditorMixin
from dialogs_screenshot import ScreenshotMixin
from systray import TrayIcon
from updater import check_update, perform_update
from version import VERSION


# =========================================================
# MAIN APPLICATION
# =========================================================
class App(KeyEditorMixin, PauseEditorMixin, ClickEditorMixin,
          ImageEditorMixin, ScreenshotMixin):
    KEY_VALUES = ["w","a","s","d","1","2","3","4","5","6","7","8","9","0",
                  "q","e","r","t","y","u","i","o","p","f","g","h","j","k","l",
                  "z","x","c","v","b","n","m",
                  "enter","space","shift","ctrl","alt","tab","esc","backspace","delete",
                  "f1","f2","f3","f4","f5","f6","f7","f8","f9","f10","f11","f12",
                  "numpad0","numpad1","numpad2","numpad3","numpad4","numpad5",
                  "numpad6","numpad7","numpad8","numpad9",
                  "up","down","left","right","home","end","pageup","pagedown",
                  "insert","printscreen","pause"]

    def __init__(self, root):
        self.root = root
        self.root.title("MacroForge")
        logger.info("MacroForge App initializing")

        self.config = Config()
        self.session_manager = ProfileManager()
 
        self.engine = ExecutionEngine(
            self._throttled_status,
            self.play_cb,
            self.playback_complete,
            self._throttled_progress
        )
        self.history = HistoryManager()
        self.clipboard: Optional[Action] = None
 
        self.active_index = -1
        self.auto_save_enabled = True
        self.actions_played = 0
        self.session_start_time = None
        self.session_elapsed_time = 0.0
        self._stats_timer = None
        self._seq_dur_cache = 0.0
        self._countdown_active = False
        self._countdown_after = None
        self._resume_countdown_active = False
        self._resume_countdown_after  = None
        self._save_session_after = None
        self._engine_thread: Optional[threading.Thread] = None

        # Throttled UI update state
        self._pending_status   = None
        self._pending_progress = None
        self._ui_timer         = None

        # Recording (lives in a single dict for clean lifecycle)
        self._recorder = {
            "running": False,
            "paused": False,
            "last_time": 0.0,
            "presses": {},          # key -> timestamp
            "queue": None,          # queue.Queue
            "poll_id": None,        # after() handle
            "kbd_thread": None,     # threading.Thread (GetAsyncKeyState poll)
            "scroll_thread": None,  # threading.Thread (WH_MOUSE_LL hook)
            "btn": None,            # tk button widget (Record/Stop)
            "pause_btn": None,      # tk button widget (Pause/Resume)
            "overlay": None,       # tk.Toplevel REC badge
            "modifiers": set(),    # currently held modifiers (ctrl/shift/alt)
            # Recorder panel UI refs
            "status_lbl": None,
            "status_dot": None,
            "time_lbl": None,
            "actions_lbl": None,
            "rec_start_time": 0.0,
            "timer_id": None,
        }

        # Lower Windows timer resolution to 1 ms for accurate sleeps
        try:
            ctypes.windll.winmm.timeBeginPeriod(1)
        except Exception:
            pass

        # Enable per-monitor DPI awareness (fixes coordinate scaling on mixed-DPI setups)
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PerMonitorV2
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass
 
        # New settings
        self.speed_var = tk.DoubleVar(value=1.0)
        self.infinite_loop_var = tk.BooleanVar(value=False)
        self.simulation_var = tk.BooleanVar(value=False)
        self.focus_lock_var = tk.BooleanVar(value=False)
        self.focus_lock_var.trace_add('write', lambda *_: setattr(self.engine, 'focus_lock', self.focus_lock_var.get()))
 
        # Setup hooks
        self.engine.before_action_hook = self.before_action
        self.engine.pause_cb = self._on_pause_changed
        self.engine._flash_cb = lambda loc: self.root.after(0, lambda: self._flash_match(loc))
 
        self.listener = keyboard.Listener(on_press=self._on_key_press_global, suppress=False)
        self.listener.start()
 
        self.build_ui()
        self.setup_keyboard_shortcuts()
        
        # Configure progress bar style with green color matching dark theme
        progress_style = ttk.Style()
        progress_style.theme_use('clam')
        progress_style.configure(
            "Green.Horizontal.TProgressbar",
            background=self.config.colors["accent"],
            troughcolor=self.config.colors["bg_tertiary"],
            bordercolor=self.config.colors["border"],
            lightcolor=self.config.colors["accent_secondary"],
            darkcolor=self.config.colors["accent"]
        )
        
        self.load_last_session()
        self._update_title()
        self._update_profile_tabs()

        # System tray icon
        self._tray_icon = TrayIcon(self, tooltip="MacroForge")
        self._tray_icon.start()
        logger.info("System tray icon started")

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.bind("<Unmap>", self._on_unmap)

        # Background update check (deferred so UI is responsive first)
        self.root.after(3000, self._check_update_silent)

    def _btn(self, parent, text, cmd, bg, fg="white", bold=False, state="normal", hover_fg=None, disabledforeground=None, font=None, icon=None, icon_size=14, padx=8, pady=3):
        if font is None:
            font = ("Segoe UI", 10, "bold") if bold else ("Segoe UI", 10)
        kwargs = dict(bg=bg, fg=fg, font=font, relief="flat", padx=padx, pady=pady,
                      cursor="hand2", state=state)
        if disabledforeground is not None:
            kwargs["disabledforeground"] = disabledforeground
        # Vector icon support
        if icon is not None:
            ph = IconFactory.get(icon, size=icon_size, color=fg)
            kwargs["image"] = ph
            kwargs["compound"] = "left" if text else "none"
            kwargs["text"] = (" " + text) if text else ""
        else:
            kwargs["text"] = text
        b = tk.Button(parent, command=cmd, **kwargs)
        if icon is not None:
            b._icon_image = ph  # keep reference so GC doesn't free it
            b._icon_name = icon
            b._icon_size = icon_size
        b._original_fg = fg
        # Hover changes text color — always a visible contrast switch
        if hover_fg is not None:
            _hover_fg = hover_fg
        elif fg == "black":
            _hover_fg = "#ffffff"
        else:
            _hover_fg = self.config.colors["accent"]
        b.bind("<Enter>", lambda e, _b=b, _h=_hover_fg: _b.config(fg=_h) if str(_b["state"]) == "normal" else None)
        b.bind("<Leave>", lambda e, _b=b, _fg=fg: _b.config(fg=_fg) if str(_b["state"]) == "normal" else None)
        return b

    def _set_btn_icon(self, btn, name, color=None, size=None):
        """Swap the vector icon on an existing button created via _btn(icon=...)."""
        if color is None:
            color = getattr(btn, "_original_fg", "white")
        if size is None:
            size = getattr(btn, "_icon_size", 14)
        ph = IconFactory.get(name, size=size, color=color)
        btn.config(image=ph)
        btn._icon_image = ph  # keep reference so GC doesn't free it

    def _set_transport(self, btn, state, text=None, active_bg=None, inactive_bg=None):
        """Toggle a transport button state and background color."""
        cfg = {"state": state}
        if text is not None:
            cfg["text"] = text
        if state == "normal" and active_bg is not None:
            cfg["bg"] = active_bg
        elif state == "disabled" and inactive_bg is not None:
            cfg["bg"] = inactive_bg
        # Reset fg to original so hover doesn't leave it stuck on hover_fg
        if hasattr(btn, "_original_fg"):
            cfg["fg"] = btn._original_fg
        btn.config(**cfg)

    def _sep(self, parent):
        tk.Frame(parent, width=1, bg=self.config.colors["border"]).pack(side="left", fill="y", padx=6)

    def _chk(self, parent, text, var, font=("Segoe UI", 9)):
        return tk.Checkbutton(parent, text=text, variable=var,
            bg=self.config.colors["bg_secondary"],
            fg=self.config.colors["text"],
            selectcolor=self.config.colors["accent_glow"],
            activebackground=self.config.colors["bg_secondary"],
            activeforeground=self.config.colors["accent"],
            font=font)

    def _section_header(self, parent, text):
        """Thin accent-left-bar section label."""
        row = tk.Frame(parent, bg=parent["bg"])
        row.pack(fill="x", padx=2, pady=(5, 1))
        tk.Frame(row, width=3, bg=self.config.colors["accent"]).pack(side="left", fill="y")
        tk.Label(row, text=text, bg=parent["bg"],
                 fg=self.config.colors["text_dim"],
                 font=("Segoe UI", 8, "bold")).pack(side="left", padx=(6, 0))

    def build_ui(self):
        C = self.config.colors
        self.root.configure(bg=C["bg"])
        self.root.geometry("780x760")
        self.root.minsize(640, 560)
        self.root.title(f"MacroForge  v{VERSION}  —  Macro Automation")

        # ══════════════════════════════════════════════════════════════
        # TITLE BAR
        # ══════════════════════════════════════════════════════════════
        title_bar = tk.Frame(self.root, bg=C["bg_secondary"], pady=0)
        title_bar.pack(fill="x")
        tk.Frame(title_bar, height=2, bg=C["accent"]).pack(fill="x", side="bottom")

        tb_left = tk.Frame(title_bar, bg=C["bg_secondary"])
        tb_left.pack(side="left", padx=(6,10), pady=7)

        # ── Menu button: gear + dropdown chevron ──
        _gear_ph = IconFactory.get("gear", size=18, color=C["accent"])
        _gear_hover_ph = IconFactory.get("gear", size=18, color="#ffffff")
        menu_wrap = tk.Frame(tb_left, bg=C["bg_secondary"], cursor="hand2")
        menu_wrap.pack(side="left", padx=(0, 6))
        gear_lbl = tk.Label(menu_wrap, image=_gear_ph, bg=C["bg_secondary"])
        gear_lbl._icon_image = _gear_ph
        gear_lbl._icon_hover = _gear_hover_ph
        gear_lbl.pack(side="left")
        arrow_lbl = tk.Label(menu_wrap, text="▼", bg=C["bg_secondary"], fg=C["text_dim"],
                             font=("Segoe UI", 7))
        arrow_lbl.pack(side="left", padx=(1, 0))
        for wgt in (menu_wrap, gear_lbl, arrow_lbl):
            wgt.bind("<Button-1>", lambda e: self._show_action_menu(menu_wrap))
        def _menu_enter(e):
            gear_lbl.config(image=_gear_hover_ph)
            arrow_lbl.config(fg="#ffffff")
            menu_wrap.config(bg=C["hover"])
            gear_lbl.config(bg=C["hover"])
            arrow_lbl.config(bg=C["hover"])
        def _menu_leave(e):
            gear_lbl.config(image=_gear_ph)
            arrow_lbl.config(fg=C["text_dim"])
            menu_wrap.config(bg=C["bg_secondary"])
            gear_lbl.config(bg=C["bg_secondary"])
            arrow_lbl.config(bg=C["bg_secondary"])
        for wgt in (menu_wrap, gear_lbl, arrow_lbl):
            wgt.bind("<Enter>", _menu_enter)
            wgt.bind("<Leave>", _menu_leave)

        tk.Label(tb_left, text="MacroForge", bg=C["bg_secondary"],
                 fg=C["text"], font=("Segoe UI", 11, "bold")).pack(side="left")
        tk.Label(tb_left, text="  Macro Automation", bg=C["bg_secondary"],
                 fg=C["text_dim"], font=("Segoe UI", 10)).pack(side="left")

        # Live status dot + text in title bar
        tb_right = tk.Frame(title_bar, bg=C["bg_secondary"])
        tb_right.pack(side="right", padx=4, pady=7)
        self.status_bar = tk.Label(tb_right, text="Ready", anchor="e",
            bg=C["bg_secondary"], fg=C["text_dim"], font=("Segoe UI", 9))
        self.status_bar.pack(side="right")
        self.status_dot = tk.Label(tb_right, text="•", bg=C["bg_secondary"],
            fg=C["border"], font=("Segoe UI", 11))
        self.status_dot.pack(side="right", padx=(0, 4))

        # ══════════════════════════════════════════════════════════════
        # PROFILE TAB BAR
        # ══════════════════════════════════════════════════════════════
        self._tab_bar = tk.Frame(self.root, bg=C["bg_secondary"], height=32)
        self._tab_bar.pack(fill="x")
        self._tab_bar.pack_propagate(False)
        tk.Frame(self._tab_bar, width=1, bg=C["border"]).pack(side="right", fill="y")

        # ➕ New profile button pinned to the right
        self._btn(self._tab_bar, "+", self._new_profile_dialog,
                  C["bg_secondary"], fg=C["text_dim"]
                  ).pack(side="right", padx=4, pady=4)

        # Scrollable inner frame for tabs
        self._tabs_inner = tk.Frame(self._tab_bar, bg=C["bg_secondary"])
        self._tabs_inner.pack(side="left", fill="both", expand=True)

        tk.Frame(self.root, height=1, bg=C["border"]).pack(fill="x")

        # ══════════════════════════════════════════════════════════════
        # MAIN BODY  (sidebar | content)
        # ══════════════════════════════════════════════════════════════
        body = tk.Frame(self.root, bg=C["bg"])
        body.pack(fill="both", expand=True)

        # ── LEFT SIDEBAR ──────────────────────────────────────────────
        sidebar = tk.Frame(body, bg=C["bg_secondary"], width=170)
        sidebar.pack_propagate(False)
        tk.Frame(sidebar, width=1, bg=C["border"]).pack(side="right", fill="y")

        # Sidebar title
        tk.Label(sidebar, text="ADD ACTION", bg=C["bg_secondary"],
                 fg=C["accent"], font=("Segoe UI", 7, "bold")).pack(anchor="w", padx=12, pady=(12, 6))

        # Stub vars still needed for add_key / add_pause internals
        self.key_var = tk.StringVar(value="w")
        self.dur_var = tk.StringVar(value="0.5")
        self.rand_delay_var = tk.StringVar(value="0.0")
        self.hold_var = tk.BooleanVar(value=True)
        self.lane_var = tk.IntVar(value=0)
        self.rand_key_var = tk.BooleanVar(value=False)

        # Add buttons — compact sidebar style
        _bfont = ("Segoe UI", 9, "bold")
        self._btn(sidebar, "Key", self.open_key_dialog,
                  C["accent"], fg="black", font=_bfont, icon="key", icon_size=12, padx=6, pady=2).pack(fill="x", padx=8, pady=2)
        self._btn(sidebar, "Click", self.open_click_dialog,
                  "#60a5fa", fg="black", font=_bfont, icon="click", icon_size=12, padx=6, pady=2).pack(fill="x", padx=8, pady=2)
        self._btn(sidebar, "Delay", self.open_pause_dialog,
                  C["pause"], fg="black", font=_bfont, hover_fg="#ffffff", icon="delay", icon_size=12, padx=6, pady=2).pack(fill="x", padx=8, pady=2)
        self._btn(sidebar, "Image", self.add_image,
                  C["playing"], fg="black", font=_bfont, icon="image", icon_size=12, padx=6, pady=2).pack(fill="x", padx=8, pady=2)
        self._btn(sidebar, "Capture", self.capture_screen_region,
                  C["neon_blue"], fg="black", font=_bfont, icon="image", icon_size=12, padx=6, pady=2).pack(fill="x", padx=8, pady=2)

        tk.Frame(sidebar, height=1, bg=C["border"]).pack(fill="x", padx=8, pady=6)

        # ── Playback config in sidebar ──
        tk.Label(sidebar, text="PLAYBACK", bg=C["bg_secondary"],
                 fg=C["accent"], font=("Segoe UI", 7, "bold")).pack(anchor="w", padx=12, pady=(0,4))

        pcard = tk.Frame(sidebar, bg=C["bg_tertiary"])
        pcard.pack(fill="x", padx=8, pady=(0, 4))
        tk.Frame(pcard, height=1, bg=C["playing"]).pack(fill="x")
        pin = tk.Frame(pcard, bg=C["bg_tertiary"])
        pin.pack(fill="x", padx=8, pady=4)

        sp_row = tk.Frame(pin, bg=C["bg_tertiary"]); sp_row.pack(fill="x", pady=(0,2))
        tk.Label(sp_row, text="Speed", bg=C["bg_tertiary"], fg=C["text_dim"],
                 font=("Segoe UI", 8)).pack(side="left")
        sc = ttk.Combobox(sp_row, textvariable=self.speed_var, width=5, state="readonly",
            values=[0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0])
        sc.pack(side="left", padx=(4, 0))
        sc.bind("<<ComboboxSelected>>", self.update_speed)

        lp_row = tk.Frame(pin, bg=C["bg_tertiary"]); lp_row.pack(fill="x", pady=(0,2))
        tk.Label(lp_row, text="Loops", bg=C["bg_tertiary"], fg=C["text_dim"],
                 font=("Segoe UI", 8)).pack(side="left")
        self.loops_var = tk.StringVar(value="1")
        tk.Entry(lp_row, textvariable=self.loops_var, width=5,
            bg=C["bg"], fg=C["text"], insertbackground=C["accent"],
            relief="flat", font=("Segoe UI", 9)).pack(side="left", padx=(4, 0))

        self.human_curve_var = tk.BooleanVar(value=True)
        self.human_curve_var.trace_add("write", lambda *_: setattr(self.engine, "human_curve", self.human_curve_var.get()))

        for text, var in [
            ("∞ Infinite", self.infinite_loop_var),
            ("⟳ Simulate", self.simulation_var),
            ("≈ Human",    self.human_curve_var),
            ("⊙ FocusLock",self.focus_lock_var),
        ]:
            tk.Checkbutton(pin, text=text, variable=var,
                bg=C["bg_tertiary"], fg=C["text"], selectcolor=C["accent_glow"],
                activebackground=C["bg_tertiary"], activeforeground=C["accent"],
                font=("Segoe UI", 8)).pack(anchor="w", pady=1)

        # ── Recorder section in sidebar ──
        tk.Frame(sidebar, height=1, bg=C["border"]).pack(fill="x", padx=8, pady=6)
        tk.Label(sidebar, text="RECORDER", bg=C["bg_secondary"],
                 fg=C["error"], font=("Segoe UI", 7, "bold")).pack(anchor="w", padx=12, pady=(0,4))

        rcard = tk.Frame(sidebar, bg=C["bg_tertiary"])
        rcard.pack(fill="x", padx=8, pady=(0, 4))
        tk.Frame(rcard, height=1, bg=C["error"]).pack(fill="x")
        rcin = tk.Frame(rcard, bg=C["bg_tertiary"])
        rcin.pack(fill="x", padx=8, pady=6)

        # Status dot + label
        rstatus = tk.Frame(rcin, bg=C["bg_tertiary"])
        rstatus.pack(fill="x", pady=(0, 4))
        self._recorder["status_dot"] = tk.Label(rstatus, text="●", bg=C["bg_tertiary"],
                                     fg=C["border"], font=("Segoe UI", 12))
        self._recorder["status_dot"].pack(side="left")
        self._recorder["status_lbl"] = tk.Label(rstatus, text="IDLE", bg=C["bg_tertiary"],
                                     fg=C["text_dim"], font=("Segoe UI", 9, "bold"))
        self._recorder["status_lbl"].pack(side="left", padx=(4, 0))

        # Time row
        rtime = tk.Frame(rcin, bg=C["bg_tertiary"])
        rtime.pack(fill="x", pady=(0, 2))
        tk.Label(rtime, text="Time", bg=C["bg_tertiary"], fg=C["text_dim"],
                 font=("Segoe UI", 8)).pack(side="left")
        self._recorder["time_lbl"] = tk.Label(rtime, text="0:00", bg=C["bg_tertiary"],
                                   fg=C["text"], font=("Consolas", 9, "bold"))
        self._recorder["time_lbl"].pack(side="left", padx=(6, 0))

        # Actions row
        racts = tk.Frame(rcin, bg=C["bg_tertiary"])
        racts.pack(fill="x", pady=(0, 2))
        tk.Label(racts, text="Actions", bg=C["bg_tertiary"], fg=C["text_dim"],
                 font=("Segoe UI", 8)).pack(side="left")
        self._recorder["actions_lbl"] = tk.Label(racts, text="0", bg=C["bg_tertiary"],
                                      fg=C["text"], font=("Consolas", 9, "bold"))
        self._recorder["actions_lbl"].pack(side="left", padx=(6, 0))

        # Compact record buttons
        self._recorder["btn"] = self._btn(sidebar, "Record", self._toggle_record,
                               C["error"], fg="black", font=_bfont, icon="record", icon_size=12, padx=6, pady=2)
        self._recorder["btn"].pack(fill="x", padx=8, pady=(2, 2))
        self._recorder["btn"].bind("<Button-3>", lambda e: self._stop_recording() if self._recorder["running"] else None)

        self._recorder["pause_btn"] = self._btn(sidebar, "Pause", self._toggle_record_pause,
                                     C["playing"], fg="black", font=_bfont, icon="pause", icon_size=12,
                                     state="disabled", padx=6, pady=2)
        self._recorder["pause_btn"].pack(fill="x", padx=8, pady=2)

        # Hotkey hints
        rhints = tk.Frame(sidebar, bg=C["bg_secondary"])
        rhints.pack(fill="x", padx=8, pady=(4, 0))
        for hint_text, hint_color in [
            ("F7  Record / Stop", C["text_dim"]),
            ("Esc  Stop", C["text_dim"]),
        ]:
            tk.Label(rhints, text=hint_text, bg=C["bg_secondary"],
                     fg=hint_color, font=("Segoe UI", 8)).pack(anchor="w", pady=1)

        # Pack sidebar now that everything is inside it
        sidebar.pack(side="left", fill="y")

        # ══════════════════════════════════════════════════════════════
        # CONTENT AREA  (timeline + inspector)
        # ══════════════════════════════════════════════════════════════
        content = tk.Frame(body, bg=C["bg"])
        content.pack(side="left", fill="both", expand=True)

        # ── TIMELINE SECTION ──────────────────────────────────────────
        tl_header = tk.Frame(content, bg=C["bg_secondary"])
        tl_header.pack(fill="x")
        tk.Frame(tl_header, width=3, bg=C["accent"]).pack(side="left", fill="y")
        tk.Label(tl_header, text="  TIMELINE", bg=C["bg_secondary"],
                 fg=C["accent"], font=("Segoe UI", 8, "bold")).pack(side="left", padx=4, pady=5)
        tk.Label(tl_header, text="scroll · Ctrl+wheel zoom · drag to reorder · Del",
                 bg=C["bg_secondary"], fg=C["text_dim"], font=("Segoe UI", 7)).pack(side="left")

        self.timeline = CanvasTimeline(content, self, self.config)
        self.timeline.pack(fill="both", expand=True)

        # ── INSPECTOR SECTION ─────────────────────────────────────────
        insp_header = tk.Frame(content, bg=C["bg_secondary"])
        insp_header.pack(fill="x")
        tk.Frame(insp_header, width=2, bg="#a78bfa").pack(side="left", fill="y")
        tk.Label(insp_header, text="INSPECTOR", bg=C["bg_secondary"],
                 fg="#a78bfa", font=("Segoe UI", 7, "bold")).pack(side="left", padx=3, pady=3)

        insp = tk.Frame(content, bg=C["bg_secondary"], pady=2)
        insp.pack(fill="x")

        self.insp_hint = tk.Label(insp, text="← Select to edit",
            bg=C["bg_secondary"], fg=C["border"], font=("Segoe UI", 7, "italic"))
        self.insp_hint.pack(side="left", padx=6)

        # ── Helper: 4-button row for every inspector ──
        def _insp4(parent):
            f = tk.Frame(parent, bg=C["bg_secondary"])
            f.pack(side="right", padx=4)
            self._btn(f, "", self._apply_inspector, C["accent"], fg="black",
                      font=("Segoe UI", 8), icon="check", icon_size=12).pack(side="left", padx=1)
            self._btn(f, "", lambda: self.delete_action(self.active_index), C["error"],
                      font=("Segoe UI", 8), icon="cross", icon_size=12).pack(side="left", padx=1)
            self._btn(f, "", lambda: self.duplicate_action(self.active_index), C["neon_blue"],
                      font=("Segoe UI", 8), icon="copy", icon_size=12).pack(side="left", padx=1)
            self._btn(f, "", self._open_dialog_for_active, C["neon_gold"],
                      font=("Segoe UI", 8), icon="pencil", icon_size=12).pack(side="left", padx=1)
            return f

        # ── KEY inspector ──
        self.insp_key = tk.Frame(insp, bg=C["bg_secondary"])
        _insp4(self.insp_key)
        tk.Label(self.insp_key, text="Key", bg=C["bg_secondary"], fg=C["text_dim"],
                 font=("Segoe UI", 7)).pack(side="left", padx=(6,1))
        self.ik_key_var = tk.StringVar()
        self.ik_key = ttk.Combobox(self.insp_key, textvariable=self.ik_key_var, width=8,
            values=["w","a","s","d","1","2","3","4","5","q","e","r","f",
                    "enter","space","shift","ctrl","alt","tab","esc",
                    "f1","f2","f3","f4","f5","f6","f7","f8","f9","f10",
                    "numpad0","numpad1","numpad2","up","down","left","right","delay"])
        self.ik_key.pack(side="left", padx=1)
        tk.Label(self.insp_key, text="Dur", bg=C["bg_secondary"], fg=C["text_dim"],
                 font=("Segoe UI", 7)).pack(side="left", padx=(4,1))
        self.ik_dur = tk.Entry(self.insp_key, width=4, bg=C["bg_tertiary"], fg=C["text"],
            insertbackground=C["accent"], relief="flat", font=("Segoe UI", 8))
        self.ik_dur.pack(side="left", padx=1)
        self.ik_hold = tk.BooleanVar(value=True)
        self._chk(self.insp_key, "Hold", self.ik_hold, font=("Segoe UI", 7)).pack(side="left", padx=(4,1))
        tk.Label(self.insp_key, text="×", bg=C["bg_secondary"], fg=C["text_dim"],
                 font=("Segoe UI", 7)).pack(side="left", padx=(4,1))
        self.ik_repeat = tk.Entry(self.insp_key, width=2, bg=C["bg_tertiary"], fg=C["text"],
            insertbackground=C["accent"], relief="flat", font=("Segoe UI", 8))
        self.ik_repeat.pack(side="left", padx=1)
        tk.Label(self.insp_key, text="Label", bg=C["bg_secondary"], fg=C["text_dim"],
                 font=("Segoe UI", 7)).pack(side="left", padx=(4,1))
        self.ik_label = tk.Entry(self.insp_key, width=8, bg=C["bg_tertiary"], fg=C["text"],
            insertbackground=C["accent"], relief="flat", font=("Segoe UI", 8))
        self.ik_label.pack(side="left", padx=1)
        self.insp_key.pack_forget()

        # ── PAUSE inspector ──
        self.insp_pause = tk.Frame(insp, bg=C["bg_secondary"])
        _insp4(self.insp_pause)
        tk.Label(self.insp_pause, text="Dur", bg=C["bg_secondary"], fg=C["text_dim"],
                 font=("Segoe UI", 7)).pack(side="left", padx=(6,1))
        self.ip_dur = tk.Entry(self.insp_pause, width=5, bg=C["bg_tertiary"], fg=C["text"],
            insertbackground=C["accent"], relief="flat", font=("Segoe UI", 8))
        self.ip_dur.pack(side="left", padx=1)
        tk.Label(self.insp_pause, text="Label", bg=C["bg_secondary"], fg=C["text_dim"],
                 font=("Segoe UI", 7)).pack(side="left", padx=(4,1))
        self.ip_label = tk.Entry(self.insp_pause, width=12, bg=C["bg_tertiary"], fg=C["text"],
            insertbackground=C["accent"], relief="flat", font=("Segoe UI", 8))
        self.ip_label.pack(side="left", padx=1)
        self.insp_pause.pack_forget()

        # ── CLICK inspector ──
        self.insp_click = tk.Frame(insp, bg=C["bg_secondary"])
        _insp4(self.insp_click)
        tk.Label(self.insp_click, text="X", bg=C["bg_secondary"], fg=C["text_dim"],
                 font=("Segoe UI", 7)).pack(side="left", padx=(6,1))
        self.ic_x = tk.Entry(self.insp_click, width=4, bg=C["bg_tertiary"], fg=C["text"],
            insertbackground=C["accent"], relief="flat", font=("Segoe UI", 8))
        self.ic_x.pack(side="left", padx=1)
        tk.Label(self.insp_click, text="Y", bg=C["bg_secondary"], fg=C["text_dim"],
                 font=("Segoe UI", 7)).pack(side="left", padx=(4,1))
        self.ic_y = tk.Entry(self.insp_click, width=4, bg=C["bg_tertiary"], fg=C["text"],
            insertbackground=C["accent"], relief="flat", font=("Segoe UI", 8))
        self.ic_y.pack(side="left", padx=1)
        tk.Label(self.insp_click, text="Btn", bg=C["bg_secondary"], fg=C["text_dim"],
                 font=("Segoe UI", 7)).pack(side="left", padx=(4,1))
        self.ic_btn_var = tk.StringVar()
        self.ic_btn = ttk.Combobox(self.insp_click, textvariable=self.ic_btn_var, width=6,
            values=["left","right","middle","double"], state="readonly")
        self.ic_btn.pack(side="left", padx=1)
        tk.Label(self.insp_click, text="±", bg=C["bg_secondary"], fg=C["text_dim"],
                 font=("Segoe UI", 7)).pack(side="left", padx=(4,1))
        self.ic_rand = tk.Entry(self.insp_click, width=3, bg=C["bg_tertiary"], fg=C["text"],
            insertbackground=C["accent"], relief="flat", font=("Segoe UI", 8))
        self.ic_rand.pack(side="left", padx=1)
        tk.Label(self.insp_click, text="×", bg=C["bg_secondary"], fg=C["text_dim"],
                 font=("Segoe UI", 7)).pack(side="left", padx=(4,1))
        self.ic_repeat = tk.Entry(self.insp_click, width=2, bg=C["bg_tertiary"], fg=C["text"],
            insertbackground=C["accent"], relief="flat", font=("Segoe UI", 8))
        self.ic_repeat.pack(side="left", padx=1)
        tk.Label(self.insp_click, text="Label", bg=C["bg_secondary"], fg=C["text_dim"],
                 font=("Segoe UI", 7)).pack(side="left", padx=(4,1))
        self.ic_label = tk.Entry(self.insp_click, width=6, bg=C["bg_tertiary"], fg=C["text"],
            insertbackground=C["accent"], relief="flat", font=("Segoe UI", 8))
        self.ic_label.pack(side="left", padx=1)
        self.insp_click.pack_forget()

        # ── IMAGE inspector ──
        self.insp_image = tk.Frame(insp, bg=C["bg_secondary"])
        _insp4(self.insp_image)
        tk.Label(self.insp_image, text="Sim", bg=C["bg_secondary"], fg=C["text_dim"],
                 font=("Segoe UI", 7)).pack(side="left", padx=(6,1))
        self.ii_sim = tk.Entry(self.insp_image, width=4, bg=C["bg_tertiary"], fg=C["text"],
            insertbackground=C["accent"], relief="flat", font=("Segoe UI", 8))
        self.ii_sim.pack(side="left", padx=1)
        tk.Label(self.insp_image, text="Wait", bg=C["bg_secondary"], fg=C["text_dim"],
                 font=("Segoe UI", 7)).pack(side="left", padx=(4,1))
        self.ii_wait = tk.Entry(self.insp_image, width=4, bg=C["bg_tertiary"], fg=C["text"],
            insertbackground=C["accent"], relief="flat", font=("Segoe UI", 8))
        self.ii_wait.pack(side="left", padx=1)
        self.insp_image.pack_forget()

        # ── PLAYBACK DOCK ─────────────────────────────────────────────
        tk.Frame(content, height=1, bg=C["border"]).pack(fill="x")
        dock = tk.Frame(content, bg=C["bg_secondary"], pady=6)
        dock.pack(fill="x")
        tk.Frame(content, height=2, bg=C["accent"]).pack(fill="x")

        # Transport buttons — left of dock
        transport = tk.Frame(dock, bg=C["bg_secondary"])
        transport.pack(side="left", padx=(10, 0))

        self.start_btn = self._btn(transport, "Start", self.start,
                                   C["accent"], fg="black", disabledforeground="white", icon="play")
        self.start_btn.pack(side="left", padx=(0, 4))

        self.pause_btn = self._btn(transport, "Pause", self.engine.toggle_pause,
                                   C["bg_tertiary"], fg="black", state="disabled", disabledforeground="white", icon="pause")
        self.pause_btn.pack(side="left", padx=(0, 4))

        self.stop_btn = self._btn(transport, "Stop", self.stop,
                                  C["bg_tertiary"], fg="black", state="disabled", disabledforeground="white", icon="stop")
        self.stop_btn.pack(side="left")

        # Hotkey hints
        tk.Frame(dock, width=1, bg=C["border"]).pack(side="left", fill="y", padx=8, pady=3)
        hints = tk.Frame(dock, bg=C["bg_secondary"])
        hints.pack(side="left")
        tk.Label(hints, text="F9 start/stop", bg=C["bg_secondary"],
                 fg=C["text_dim"], font=("Segoe UI", 7)).pack(anchor="w")
        tk.Label(hints, text="Esc pause · Ctrl+Z undo · Del delete",
                 bg=C["bg_secondary"], fg=C["text_dim"], font=("Segoe UI", 7)).pack(anchor="w")

        # ── BOTTOM STATUS BAR ─────────────────────────────────────────
        status_bar = tk.Frame(content, bg=C["bg"], pady=3)
        status_bar.pack(fill="x")
        tk.Frame(status_bar, width=3, bg=C["border"]).pack(side="left", fill="y")

        self.progress_bar = ttk.Progressbar(status_bar, orient="horizontal",
            mode="determinate", style="Green.Horizontal.TProgressbar")
        self.progress_bar.pack(side="left", padx=(6, 2), pady=2, fill="x", expand=True)

        self.progress_label = tk.Label(status_bar, text="0%", width=5,
            bg=C["bg"], fg=C["text_dim"], font=("Segoe UI", 9))
        self.progress_label.pack(side="left", padx=(0, 6))

        tk.Frame(status_bar, width=1, bg=C["border"]).pack(side="left", fill="y", pady=2)

        # ── Icon stats (bolt=actions, loop=loops, clock=seq, clock=time) ──
        stats_frame = tk.Frame(status_bar, bg=C["bg"])
        stats_frame.pack(side="left", padx=6)
        icon_color = C["text_dim"]
        self._stats_icons = []

        def _stat(parent, icon_name, text_var_attr, size=12):
            f = tk.Frame(parent, bg=C["bg"])
            f.pack(side="left", padx=(0, 8))
            photo = IconFactory.get(icon_name, size=size, color=icon_color, bg=C["bg"])
            self._stats_icons.append(photo)
            tk.Label(f, image=photo, bg=C["bg"]).pack(side="left")
            lbl = tk.Label(f, text="0", bg=C["bg"], fg=icon_color, font=("Segoe UI", 8))
            lbl.pack(side="left", padx=(2, 0))
            return lbl

        self._stat_actions = _stat(stats_frame, "bolt", "actions")
        self._stat_loops   = _stat(stats_frame, "loop", "loops")
        self._stat_seq     = _stat(stats_frame, "delay", "seq")
        self._stat_time    = _stat(stats_frame, "delay", "time")

    def setup_keyboard_shortcuts(self):
        self.root.bind("<Control-z>", lambda e: self.undo())
        self.root.bind("<Control-y>", lambda e: self.redo())
        self.root.bind("<Control-c>", lambda e: self.copy_action())
        self.root.bind("<Control-v>", lambda e: self.paste_action())
        self.root.bind("<Control-s>", lambda e: (self._do_save_session(), self.status("Session saved")))
        self.root.bind("<Control-d>", lambda e: self.duplicate_action(self.active_index))
        self.root.bind("<Delete>", lambda e: self.delete_action(self.active_index))
        self.root.bind("<Control-Delete>", lambda e: self.delete_action(self.active_index))
        self.root.bind("<Escape>", lambda e: (self.select(-1), self.timeline.selected_indices.clear()))
        self.root.bind("<Control-f>", lambda e: self.focus_timeline())
        # ESC handled globally by pynput in hotkeys()

    def focus_timeline(self):
        """Focus the timeline for keyboard navigation"""
        self.timeline.canvas.focus_set()
        self.status("Timeline focused - use arrow keys to navigate")
 
    # ==================== SESSION MANAGEMENT ====================
    def load_last_session(self):
        """Load last active profile on startup"""
        session = self.session_manager.load_profile()
        if session:
            try:
                self.engine.actions = [Action.from_dict(x) for x in session.get("actions", [])]
                settings = session.get("settings", {})
                self.loops_var.set(settings.get("loops", "1"))
                self.speed_var.set(settings.get("speed", 1.0))
                self.infinite_loop_var.set(settings.get("infinite_loop", False))
                self.human_curve_var.set(settings.get("human_curve", True))
                self.timeline.zoom = settings.get("zoom", 1.0)
                if "geometry" in settings:
                    self.root.geometry(settings["geometry"])
                self._invalidate_seq_dur()
                self.refresh()
                # Reset statistics display on startup
                self.actions_played = 0
                self.session_elapsed_time = 0.0
                self.session_start_time = None
                self.update_statistics(immediate=True)
                self.status(f"Profile ‘{self.session_manager.active}’ loaded")
            except Exception:
                if not self.engine.actions:
                    self.status("Failed to load profile")
                else:
                    self.status("Profile partially loaded")
        else:
            self.engine.actions = []
            self.update_statistics(immediate=True)
            self.status("Ready")
 
    def save_session(self):
        """Debounced auto-save — coalesces rapid calls into one write 500 ms after last call."""
        if not self.auto_save_enabled:
            return
        if self._save_session_after:
            self.root.after_cancel(self._save_session_after)
        self._save_session_after = self.root.after(500, self._do_save_session)

    def _do_save_session(self):
        self._save_session_after = None
        if not self.auto_save_enabled:
            return
        settings = {
            "loops": self.loops_var.get(),
            "speed": self.speed_var.get(),
            "infinite_loop": self.infinite_loop_var.get(),
            "human_curve": self.human_curve_var.get(),
            "geometry": self.root.geometry(),
            "zoom": self.timeline.zoom
        }
        self.session_manager.save_profile(self.engine.actions, settings)
 
    # ==================== ACTION MANAGEMENT ====================
    # ──────────────────────────────────────────────────────────────
    # DIALOG HELPERS
    # ──────────────────────────────────────────────────────────────
    def _make_dialog(self, title, width=420, height=None):
        """Create a styled modal dialog and return (dlg, C)."""
        C = self.config.colors
        dlg = tk.Toplevel(self.root)
        dlg.title(title)
        dlg.configure(bg=C["bg"])
        dlg.resizable(False, False)
        dlg.transient(self.root)
        dlg.grab_set()
        # Centre on parent (simplified without update_idletasks)
        try:
            px = self.root.winfo_x() + self.root.winfo_width() // 2
            py = self.root.winfo_y() + self.root.winfo_height() // 2
        except Exception:
            px, py = 400, 300  # Fallback position
        if height:
            dlg.geometry(f"{width}x{height}+{px - width//2}+{py - height//2}")
        else:
            dlg.geometry(f"{width}x300+{px - width//2}+{py - 150}")
        # Title bar stripe
        tk.Frame(dlg, height=2, bg=C["accent"]).pack(fill="x")
        return dlg, C

    def _dlg_section(self, parent, title, color=None):
        """Labelled card section inside a dialog."""
        C = self.config.colors
        color = color or C["accent"]
        outer = tk.Frame(parent, bg=C["bg_tertiary"])
        outer.pack(fill="x", padx=12, pady=(6, 0))
        tk.Frame(outer, height=1, bg=color).pack(fill="x")
        inner = tk.Frame(outer, bg=C["bg_tertiary"])
        inner.pack(fill="x", padx=10, pady=8)
        if title:
            tk.Label(inner, text=title, bg=C["bg_tertiary"],
                     fg=color, font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(0, 6))
        return inner

    def _dlg_field(self, parent, label, widget_factory, hint=None):
        """Labelled field row. widget_factory(row) → widget."""
        C = self.config.colors
        row = tk.Frame(parent, bg=parent["bg"])
        row.pack(fill="x", pady=2)
        tk.Label(row, text=label, bg=parent["bg"], fg=C["text_dim"],
                 font=("Segoe UI", 9), width=14, anchor="w").pack(side="left")
        w = widget_factory(row)
        w.pack(side="left", padx=(0, 6))
        if hint:
            tk.Label(row, text=hint, bg=parent["bg"], fg=C["text_dim"],
                     font=("Segoe UI", 8, "italic")).pack(side="left")
        return w

    def _dlg_buttons(self, parent, on_ok, on_cancel, ok_text="Add"):
        """Standard OK / Cancel button row."""
        C = self.config.colors
        tk.Frame(parent, height=1, bg=C["border"]).pack(fill="x", padx=12, pady=(10, 0))
        row = tk.Frame(parent, bg=C["bg"], pady=8)
        row.pack(fill="x")
        self._btn(row, "Cancel", on_cancel, C["bg_tertiary"], icon="cross").pack(side="right", padx=(0, 12))
        self._btn(row, ok_text, on_ok, C["accent"], fg="black", bold=True, icon="check").pack(side="right", padx=(0, 4))

    # ── Add Key dialog ─────────────────────────────────────────────

    # ── Add Delay dialog ───────────────────────────────────────────

    # ── Add Click / Edit Click dialog ──────────────────────────────

    def add_click(self):
        self.open_click_dialog()

    def add_key(self):
        try:
            duration = float(self.dur_var.get())
            if duration <= 0:
                raise ValueError("Duration must be positive")
 
            self.history.push(self.engine.actions)
 
            action = Action(
                self.key_var.get(),
                duration,
                self.hold_var.get(),
                self.lane_var.get(),
                float(self.rand_delay_var.get()),
                self.rand_key_var.get()
            )
            self.engine.actions.append(action)
            self.active_index = len(self.engine.actions) - 1
            self.refresh()
            self.update_statistics()
            self.save_session()
            self.timeline.ensure_visible(self.active_index)
            self.status("Added key action")
 
        except ValueError as e:
            messagebox.showerror("Invalid Input", f"Duration must be a positive number: {e}")
 
    def add_pause(self):
        try:
            duration = float(self.dur_var.get())
            if duration <= 0:
                raise ValueError("Duration must be positive")
 
            self.history.push(self.engine.actions)
 
            action = Action("[DELAY]", duration)
            self.engine.actions.append(action)
            self.active_index = len(self.engine.actions) - 1
            self.refresh()
            self.update_statistics()
            self.save_session()
            self.timeline.ensure_visible(self.active_index)
            self.status("Added delay")
 
        except ValueError as e:
            messagebox.showerror("Invalid Input", f"Duration must be a positive number: {e}")

    def _flash_match(self, loc):
        """Briefly flash a green rectangle over the matched region on screen."""
        try:
            ov = tk.Toplevel(self.root)
            ov.overrideredirect(True)
            ov.attributes("-topmost", True)
            ov.attributes("-transparentcolor", "black")
            ov.configure(bg="black")
            ov.geometry(f"{loc.width}x{loc.height}+{loc.left}+{loc.top}")
            cv = tk.Canvas(ov, bg="black", highlightthickness=0,
                           width=loc.width, height=loc.height)
            cv.pack()
            cv.create_rectangle(2, 2, loc.width - 2, loc.height - 2,
                outline="#20b87e", width=3, fill="")
            cv.create_rectangle(4, 4, loc.width - 4, loc.height - 4,
                outline="#20b87e", width=1, fill="#20b87e", stipple="gray25")
            ov.after(600, ov.destroy)
        except Exception:
            pass

    # ==================== RECORDER ====================
    def _toggle_record(self):
        """Start or stop real-time recording.  Never pauses — use _toggle_record_pause for that."""
        rec = self._recorder
        if not rec["running"]:
            self._start_recording()
        else:
            self._stop_recording()

    def _toggle_record_pause(self):
        """Pause or resume an active recording."""
        rec = self._recorder
        if not rec["running"]:
            return
        if rec["paused"]:
            # Resume
            rec["paused"] = False
            rec["last_time"] = time.time()
            rec["pause_btn"].config(text=" Pause", bg=self.config.colors["playing"])
            self._set_btn_icon(rec["pause_btn"], "pause", color="black")
            rec["status_dot"].config(fg="#ff4444")
            rec["status_lbl"].config(text="RECORDING", fg="#ff4444")
            self._rec_timer_tick()
            self.status("Recording resumed")
            self._show_rec_badge(True)
        else:
            # Pause
            rec["paused"] = True
            rec["pause_btn"].config(text=" Resume", bg=self.config.colors["playing"])
            self._set_btn_icon(rec["pause_btn"], "play", color="black")
            rec["status_dot"].config(fg="#f0a844")
            rec["status_lbl"].config(text="PAUSED", fg="#f0a844")
            self.status("Recording paused — click Resume to continue, or Stop to finish")
            self._show_rec_badge(False)

    def _show_rec_badge(self, show: bool):
        """Show or hide the floating REC overlay badge."""
        rec = self._recorder
        if show:
            if rec["overlay"] is not None:
                return
            try:
                ov = tk.Toplevel(self.root)
                ov.overrideredirect(True)
                ov.attributes("-topmost", True)
                ov.attributes("-transparentcolor", "#000001")
                ov.configure(bg="#000001")
                w, h = 60, 28
                x = self.root.winfo_x() + self.root.winfo_width() - w - 12
                y = self.root.winfo_y() + 8
                ov.geometry(f"{w}x{h}+{x}+{y}")
                cv = tk.Canvas(ov, bg="#000001", highlightthickness=0, width=w, height=h)
                cv.pack()
                cv.create_oval(4, 4, 24, 24, fill="#ff4444", outline="")
                cv.create_text(40, 14, text="REC", fill="#ff4444",
                               font=("Segoe UI", 10, "bold"))
                rec["overlay"] = ov
            except Exception:
                pass
        else:
            if rec["overlay"] is not None:
                try:
                    rec["overlay"].destroy()
                except Exception:
                    pass
                rec["overlay"] = None

    def _rec_timer_tick(self):
        """Update the elapsed-time label in the recorder panel every second."""
        rec = self._recorder
        if not rec["running"] or rec["paused"]:
            return
        elapsed = int(time.time() - rec["rec_start_time"])
        mins, secs = divmod(elapsed, 60)
        rec["time_lbl"].config(text=f"{mins}:{secs:02d}")
        rec["timer_id"] = self.root.after(1000, self._rec_timer_tick)

    def _update_rec_action_count(self):
        """Update the action count label in the recorder panel."""
        rec = self._recorder
        if rec["running"] and rec["actions_lbl"] is not None:
            rec["actions_lbl"].config(text=str(len(self.engine.actions)))

    def _start_recording(self):
        if self._recorder["running"]:
            return
        rec = self._recorder
        rec["running"] = True
        rec["paused"] = False
        rec["last_time"] = time.time()
        rec["presses"].clear()
        rec["modifiers"].clear()
        rec["queue"] = queue.Queue()
        rec["btn"].config(text=" Stop", bg=self.config.colors["error"])
        self._set_btn_icon(rec["btn"], "stop", color="black")
        rec["pause_btn"].config(text=" Pause", bg=self.config.colors["playing"],
                                   state="normal")
        self._set_btn_icon(rec["pause_btn"], "pause", color="black")
        # Update panel status
        rec["status_dot"].config(fg="#ff4444")
        rec["status_lbl"].config(text="RECORDING", fg="#ff4444")
        rec["actions_lbl"].config(text="0")
        rec["rec_start_time"] = time.time()
        self._rec_timer_tick()
        self.status("Recording…")
        self._show_rec_badge(True)

        # Cancel stale poll
        if rec["poll_id"]:
            try:
                self.root.after_cancel(rec["poll_id"])
            except Exception as e:
                logger.debug(f"after_cancel stale: {e}")
            rec["poll_id"] = None
        self._poll_queue()

        # Keyboard via Windows GetAsyncKeyState polling (avoids pynput hook conflicts)
        rec["kbd_thread"] = threading.Thread(target=self._kbd_poll_loop, daemon=True)
        rec["kbd_thread"].start()

        # Mouse buttons polled in kbd_thread via GetAsyncKeyState
        # Scroll wheel captured via low-level mouse hook (separate thread with message pump)
        rec["scroll_thread"] = threading.Thread(target=self._scroll_hook_loop, daemon=True)
        rec["scroll_thread"].start()
        logger.info("Recording started")

    def _kbd_poll_loop(self):
        """Poll Windows keyboard state at 60Hz using GetAsyncKeyState.
        Handles combos, debounce, backspace-delete, and pause-resume."""
        user32 = ctypes.windll.user32
        rec = self._recorder
        MODS = {"shift", "ctrl", "alt"}

        vk_name = {}
        for vk in range(0x41, 0x5B):
            vk_name[vk] = chr(vk).lower()
        for vk in range(0x30, 0x3A):
            vk_name[vk] = chr(vk)
        vk_name.update({
            0x08: "backspace", 0x09: "tab", 0x0D: "return",
            0x1B: "esc", 0x20: "space",
            0x25: "left", 0x26: "up", 0x27: "right", 0x28: "down",
            0x10: "shift", 0x11: "ctrl", 0x12: "alt",
            0x01: "mouse_left", 0x02: "mouse_right", 0x04: "mouse_middle",
        })
        for i in range(0x70, 0x7C):
            vk_name[i] = f"f{i - 0x6F}"

        vks = list(vk_name.keys())
        prev = {}

        while rec["running"]:
            for vk in vks:
                name = vk_name[vk]
                down = (user32.GetAsyncKeyState(vk) & 0x8000) != 0
                was_down = prev.get(vk, False)

                if down and not was_down:
                    rec["presses"][name] = time.time()
                    if name in MODS:
                        rec["modifiers"].add(name)
                elif not down and was_down:
                    if name in MODS:
                        rec["modifiers"].discard(name)

                    if name not in rec["presses"]:
                        prev[vk] = down
                        continue

                    press_time = rec["presses"].pop(name)
                    release_time = time.time()
                    hold_dur = release_time - press_time

                    # Debounce: ignore auto-repeat artifacts under 50ms
                    if hold_dur < 0.05:
                        prev[vk] = down
                        continue

                    # Backspace while recording = delete last action
                    if name == "backspace" and not rec["modifiers"]:
                        self.root.after(0, self._rec_delete_last)
                        prev[vk] = down
                        continue

                    # Skip queueing when paused
                    if rec["paused"]:
                        prev[vk] = down
                        continue

                    delay = press_time - rec["last_time"]
                    if delay > 0.05:
                        rec["queue"].put(Action("[DELAY]", round(delay, 2), action_type="pause"))

                    if name.startswith("mouse_"):
                        pt = ctypes.wintypes.POINT()
                        user32.GetCursorPos(ctypes.byref(pt))
                        is_hold = hold_dur > 0.3
                        dur = round(hold_dur, 2) if is_hold else 0.05
                        act = Action("[CLICK]", dur, hold_mode=is_hold, action_type="click")
                        act.click_x, act.click_y = pt.x, pt.y
                        act.click_button = name.replace("mouse_", "")
                        act.click_coord_mode = "absolute"
                        rec["queue"].put(act)
                        rec["last_time"] = release_time
                        mode = "hold" if is_hold else "tap"
                        self.status(f"Recorded: {act.click_button} {mode} at ({pt.x}, {pt.y})")
                    else:
                        # Combo detection: if a modifier is held, record combo
                        active_mods = rec["modifiers"] - {name}
                        if active_mods and name not in MODS:
                            combo = "+".join(sorted(active_mods)) + "+" + name
                            rec["queue"].put(Action(combo, 0.05, action_type="key"))
                            self.status(f"Recorded: {combo}")
                        else:
                            is_hold = hold_dur > 0.3
                            if is_hold:
                                rec["queue"].put(Action(name, round(hold_dur, 2), hold_mode=True, action_type="key"))
                            else:
                                rec["queue"].put(Action(name, 0.05, action_type="key"))
                            mode = "hold" if is_hold else "tap"
                            self.status(f"Recorded: {name} ({mode})")
                        rec["last_time"] = release_time
                prev[vk] = down
            time.sleep(1 / 60)

    def _rec_delete_last(self):
        """Remove the last recorded action from the timeline (main-thread only)."""
        try:
            if self.engine.actions:
                self.history.push(self.engine.actions)
                self.engine.actions.pop()
                self.active_index = len(self.engine.actions) - 1
                self.refresh()
                self.update_statistics()
                self.save_session()
                self._update_rec_action_count()
                self.status("Deleted last recorded action")
        except Exception as e:
            logger.debug(f"rec_delete_last: {e}")

    def _scroll_hook_loop(self):
        """Low-level mouse hook for scroll wheel events only.
        Runs a Windows message pump so the hook callback fires."""
        user32 = ctypes.windll.user32
        rec = self._recorder

        WH_MOUSE_LL = 14
        WM_MOUSEWHEEL = 0x020A
        WM_MOUSEHWHEEL = 0x020E
        PM_REMOVE = 0x0001

        class MSLLHOOKSTRUCT(ctypes.Structure):
            _fields_ = [
                ("pt", ctypes.wintypes.POINT),
                ("mouseData", ctypes.c_uint32),
                ("flags", ctypes.c_uint32),
                ("time", ctypes.c_uint32),
                ("dwExtraInfo", ctypes.c_uint64),
            ]

        @ctypes.WINFUNCTYPE(ctypes.c_int64, ctypes.c_int32, ctypes.c_uint64, ctypes.c_int64)
        def hook_proc(nCode, wParam, lParam):
            if nCode >= 0 and rec["running"] and not rec["paused"]:
                if wParam == WM_MOUSEWHEEL or wParam == WM_MOUSEHWHEEL:
                    try:
                        if rec["queue"] is None:
                            return user32.CallNextHookEx(None, nCode, wParam, lParam)
                        data = ctypes.cast(lParam, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
                        delta = ctypes.c_int16(data.mouseData >> 16).value
                        direction = "scroll_up" if delta > 0 else "scroll_down"
                        now = time.time()
                        delay = now - rec["last_time"]
                        if delay > 0.05:
                            rec["queue"].put(Action("[DELAY]", round(delay, 2), action_type="pause"))
                        rec["queue"].put(Action(f"[{direction.upper()}]", 0.05, action_type="key"))
                        rec["last_time"] = now
                        self.status(f"Recorded: {direction}")
                    except Exception as e:
                        logger.debug(f"scroll hook: {e}")
            return user32.CallNextHookEx(None, nCode, wParam, lParam)

        hook_id = user32.SetWindowsHookExW(WH_MOUSE_LL, hook_proc, None, 0)
        if not hook_id:
            logger.error("Failed to install scroll hook")
            return

        logger.info("Scroll hook installed")
        msg = ctypes.wintypes.MSG()
        while rec["running"]:
            if user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, PM_REMOVE):
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
            else:
                time.sleep(0.005)
        user32.UnhookWindowsHookEx(hook_id)
        logger.info("Scroll hook removed")

    def _poll_queue(self):
        """Drain recorder queue on main Tkinter thread."""
        rec = self._recorder
        try:
            if not rec["running"] and (rec["queue"] is None or rec["queue"].empty()):
                rec["poll_id"] = None
                return
            updated = False
            while rec["queue"] is not None and not rec["queue"].empty():
                try:
                    action = rec["queue"].get_nowait()
                except queue.Empty:
                    break
                self.history.push(self.engine.actions)
                self.engine.actions.append(action)
                self._update_rec_action_count()
                updated = True
            if updated:
                self.active_index = len(self.engine.actions) - 1
                self.refresh()
                self.timeline.ensure_visible(self.active_index)
                self.update_statistics()
                self.save_session()
        except Exception as e:
            logger.error(f"_poll_queue: {e}")
        rec["poll_id"] = self.root.after(50, self._poll_queue)

    def _stop_recording(self):
        if not self._recorder["running"]:
            return
        rec = self._recorder
        rec["running"] = False
        rec["paused"] = False

        # Wait for input threads to finish
        if rec.get("kbd_thread") and rec["kbd_thread"].is_alive():
            rec["kbd_thread"].join(timeout=0.05)
        if rec.get("scroll_thread") and rec["scroll_thread"].is_alive():
            rec["scroll_thread"].join(timeout=0.2)

        self._show_rec_badge(False)
        rec["btn"].config(text=" Record", bg=self.config.colors["error"])
        self._set_btn_icon(rec["btn"], "record", color="black")
        rec["pause_btn"].config(text=" Pause", bg=self.config.colors["playing"],
                                    state="disabled")
        self._set_btn_icon(rec["pause_btn"], "pause", color="black")
        # Reset panel status
        rec["status_dot"].config(fg=self.config.colors["border"])
        rec["status_lbl"].config(text="IDLE", fg=self.config.colors["text_dim"])
        rec["time_lbl"].config(text="0:00")
        rec["actions_lbl"].config(text="0")
        if rec["timer_id"]:
            try:
                self.root.after_cancel(rec["timer_id"])
            except Exception:
                pass
            rec["timer_id"] = None

        # Flush held keys/buttons into queue
        try:
            if rec["queue"] is not None:
                now = time.time()
                for k, t in list(rec["presses"].items()):
                    hold = now - t
                    delay = t - rec["last_time"]
                    if delay > 0.05:
                        rec["queue"].put(Action("[DELAY]", round(delay, 2), action_type="pause"))
                    if k.startswith("mouse_"):
                        pt = ctypes.wintypes.POINT()
                        ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
                        act = Action("[CLICK]", 0.05, action_type="click")
                        act.click_x, act.click_y = pt.x, pt.y
                        act.click_button = k.replace("mouse_", "")
                        act.click_coord_mode = "absolute"
                        rec["queue"].put(act)
                    else:
                        rec["queue"].put(Action(k, round(hold, 2), hold_mode=True, action_type="key"))
                    rec["last_time"] = now
            rec["presses"].clear()
            rec["modifiers"].clear()
        except Exception as e:
            logger.error(f"rec flush: {e}")

        # Cancel poll & final drain
        if rec["poll_id"]:
            try:
                self.root.after_cancel(rec["poll_id"])
            except Exception as e:
                logger.debug(f"after_cancel: {e}")
            rec["poll_id"] = None
        self._poll_queue_final()

        rec["kbd_thread"] = None
        rec["scroll_thread"] = None

        rec["queue"] = None
        self.status("Recording stopped")

    def _poll_queue_final(self):
        """Final drain after recording stops."""
        rec = self._recorder
        try:
            updated = False
            while rec["queue"] is not None and not rec["queue"].empty():
                try:
                    action = rec["queue"].get_nowait()
                except queue.Empty:
                    break
                self.history.push(self.engine.actions)
                self.engine.actions.append(action)
                updated = True
            if updated:
                self.active_index = len(self.engine.actions) - 1
                self.refresh()
                self.update_statistics()
                self.save_session()
        except Exception as e:
            logger.error(f"_poll_queue_final: {e}")

    def _hotkey_record(self):
        self._toggle_record()

    def export_csv(self):
        """Export actions to CSV file"""
        if not self.engine.actions:
            messagebox.showwarning("No Actions", "Nothing to export")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            title="Export actions as CSV"
        )
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["index", "key", "duration", "hold", "lane", "rand_delay", "rand_key"])
                for i, a in enumerate(self.engine.actions):
                    writer.writerow([i+1, a.key, a.duration, a.hold_mode, a.lane, a.random_delay, a.random_key])
            self.status(f"Exported {len(self.engine.actions)} actions to CSV")
        except Exception as e:
            messagebox.showerror("Export Error", str(e))

    def import_csv(self):
        """Import actions from CSV file"""
        path = filedialog.askopenfilename(
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            title="Import actions from CSV"
        )
        if not path:
            return
        try:
            self.history.push(self.engine.actions)
            new_actions = []
            with open(path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    a = Action(
                        key=row["key"],
                        duration=float(row["duration"]),
                        hold_mode=row.get("hold", "False") == "True",
                        lane=int(row.get("lane", 0)),
                        random_delay=float(row.get("rand_delay", 0)),
                        random_key=row.get("rand_key", "False") == "True"
                    )
                    new_actions.append(a)
            self.engine.actions = new_actions
            self.active_index = -1
            self.refresh()
            self.update_statistics()
            self.save_session()
            self.status(f"Imported {len(new_actions)} actions from CSV")
        except Exception as e:
            messagebox.showerror("Import Error", str(e))
 
    def delete_action(self, index: int):
        # Check if multiple actions are selected
        selected = self.timeline.selected_indices
        if selected:
            indices = sorted(selected, reverse=True)  # Delete from end to preserve indices
            if not indices or indices[0] >= len(self.engine.actions):
                self.timeline.selected_indices.clear()
                return
            self.history.push(self.engine.actions)
            for idx in indices:
                if 0 <= idx < len(self.engine.actions):
                    self.engine.actions.pop(idx)
            self.active_index = -1
            self.timeline.selected_indices.clear()
            self.refresh()
            self.update_statistics()
            self.save_session()
            self.status(f"Deleted {len(indices)} actions")
            return

        # Single action delete
        if index < 0 or index >= len(self.engine.actions):
            return

        self.history.push(self.engine.actions)
        self.engine.actions.pop(index)
        self.active_index = -1
        self.timeline.selected_indices.clear()
        self.refresh()
        self.update_statistics()
        self.save_session()
        self.status("Deleted action")
 
    def duplicate_action(self, index: int):
        if index < 0 or index >= len(self.engine.actions):
            self.status("No action selected to duplicate")
            return
 
        self.history.push(self.engine.actions)
        self.engine.actions.insert(index + 1, deepcopy(self.engine.actions[index]))
        self.active_index = index + 1
        self.refresh()
        self.update_statistics()
        self.save_session()
        self.status("Duplicated action")
 
    def move_action(self, index: int, direction: int):
        if index < 0 or index >= len(self.engine.actions):
            return
 
        new_index = index + direction
        if new_index < 0 or new_index >= len(self.engine.actions):
            return
 
        self.history.push(self.engine.actions)
        action = self.engine.actions.pop(index)
        self.engine.actions.insert(new_index, action)
        self.active_index = new_index
        self.refresh()
        self.save_session()
        self.status("Moved action")
 
    def move_action_to(self, index: int, target_index: int):
        """Move action to specific position"""
        if index < 0 or index >= len(self.engine.actions):
            return
        if target_index < 0 or target_index >= len(self.engine.actions):
            return
 
        self.history.push(self.engine.actions)
        action = self.engine.actions.pop(index)
        self.engine.actions.insert(target_index, action)
        self.active_index = target_index
        self.refresh()
        self.update_statistics(immediate=True)
        self.save_session()
        self.status("Moved action")
 
    def copy_action(self):
        if self.active_index < 0 or self.active_index >= len(self.engine.actions):
            self.status("No action selected to copy")
            return
 
        self.clipboard = deepcopy(self.engine.actions[self.active_index])
        self.status("Copied action")
 
    def copy_action_index(self, index: int):
        if index < 0 or index >= len(self.engine.actions):
            return
        self.clipboard = deepcopy(self.engine.actions[index])
        self.status("Copied action")
 
    def paste_action(self):
        if self.clipboard is None:
            self.status("Clipboard empty")
            return
 
        self.history.push(self.engine.actions)
        new_action = deepcopy(self.clipboard)
        if 0 <= self.active_index < len(self.engine.actions):
            insert_at = self.active_index + 1
        else:
            insert_at = len(self.engine.actions)
        self.engine.actions.insert(insert_at, new_action)
        self.active_index = insert_at
        self.refresh()
        self.update_statistics()
        self.save_session()
        self.status("Pasted action")
 
    # ==================== SELECTION & EDITING ====================
    def select(self, index: int):
        if index is None or index < 0 or index >= len(self.engine.actions):
            self.active_index = -1
            self.timeline.set_active(-1)
            self.timeline.selected_indices.clear()
            self._show_inspector(False)
            return

        self.active_index = index
        self.timeline.selected_indices.clear()
        self.timeline.set_active(index)
        action = self.engine.actions[index]
        self._show_inspector(True, action_type=action.action_type)

        # Populate the correct inspector panel
        if action.action_type == "key":
            self.ik_key_var.set(action.key)
            self.ik_dur.delete(0, tk.END); self.ik_dur.insert(0, str(action.duration))
            self.ik_hold.set(action.hold_mode)
            self.ik_repeat.delete(0, tk.END); self.ik_repeat.insert(0, str(getattr(action, 'repeat_count', 1)))
            self.ik_label.delete(0, tk.END); self.ik_label.insert(0, getattr(action, 'label', ''))
        elif action.action_type == "pause":
            self.ip_dur.delete(0, tk.END); self.ip_dur.insert(0, str(action.duration))
            self.ip_label.delete(0, tk.END); self.ip_label.insert(0, getattr(action, 'label', ''))
        elif action.action_type == "click":
            self.ic_x.delete(0, tk.END); self.ic_x.insert(0, str(action.click_x))
            self.ic_y.delete(0, tk.END); self.ic_y.insert(0, str(action.click_y))
            self.ic_btn_var.set(action.click_button)
            self.ic_rand.delete(0, tk.END); self.ic_rand.insert(0, str(action.click_rand_radius))
            self.ic_repeat.delete(0, tk.END); self.ic_repeat.insert(0, str(getattr(action, 'repeat_count', 1)))
            self.ic_label.delete(0, tk.END); self.ic_label.insert(0, getattr(action, 'label', ''))
        elif action.action_type == "image":
            self.ii_sim.delete(0, tk.END); self.ii_sim.insert(0, str(action.similarity))
            self.ii_wait.delete(0, tk.END); self.ii_wait.insert(0, str(action.wait_timeout))

    def select_range(self, index: int):
        """Select range from active_index to index (shift+click)"""
        if index < 0 or index >= len(self.engine.actions):
            return
        if self.active_index < 0 or self.active_index >= len(self.engine.actions):
            self.select(index)
            return

        start = min(self.active_index, index)
        end = max(self.active_index, index)
        self.timeline.selected_indices = set(range(start, end + 1))
        self.timeline._dirty_all = True
        self.timeline.refresh()
        self.status(f"Selected {len(self.timeline.selected_indices)} actions")
 
    def _apply_inspector(self):
        if self.active_index < 0 or self.active_index >= len(self.engine.actions):
            messagebox.showwarning("No Selection", "Please select an action first")
            return
        try:
            action = self.engine.actions[self.active_index]
            self.history.push(self.engine.actions)

            if action.action_type == "key":
                key = self.ik_key_var.get().strip()
                if not key:
                    raise ValueError("Key cannot be empty")
                duration = float(self.ik_dur.get())
                if duration <= 0:
                    raise ValueError("Duration must be positive")
                action.key = key
                action.duration = duration
                action.hold_mode = self.ik_hold.get()
                action.repeat_count = max(1, int(self.ik_repeat.get() or 1))
                action.label = self.ik_label.get().strip()
            elif action.action_type == "pause":
                duration = float(self.ip_dur.get())
                if duration <= 0:
                    raise ValueError("Duration must be positive")
                action.duration = duration
                action.label = self.ip_label.get().strip()
            elif action.action_type == "click":
                action.click_x = int(self.ic_x.get())
                action.click_y = int(self.ic_y.get())
                action.click_button = self.ic_btn_var.get()
                action.click_rand_radius = int(self.ic_rand.get() or 0)
                action.repeat_count = max(1, int(self.ic_repeat.get() or 1))
                action.label = self.ic_label.get().strip()
            elif action.action_type == "image":
                action.similarity = float(self.ii_sim.get())
                action.wait_timeout = float(self.ii_wait.get())

            self.refresh()
            self.update_statistics()
            self.save_session()
            self.status("Applied changes")
        except ValueError as e:
            messagebox.showerror("Invalid Input", f"Invalid value: {e}")

    def _cancel_inspector(self):
        if self.active_index >= 0:
            self.select(self.active_index)
            self.status("Changes cancelled")

    def _open_dialog_for_active(self):
        if self.active_index < 0 or self.active_index >= len(self.engine.actions):
            return
        action = self.engine.actions[self.active_index]
        if action.action_type == "image":
            self.open_image_editor(self.active_index)
        elif action.action_type == "click":
            self.open_click_editor(self.active_index)
        elif action.action_type == "pause":
            self.open_pause_editor(self.active_index)
        else:
            self.open_key_editor(self.active_index)

    def apply_changes(self):
        """Deprecated – use _apply_inspector. Kept for any external callers."""
        self._apply_inspector()
 
    # ==================== UNDO/REDO ====================
    def undo(self):
        if not self.history.can_undo():
            self.status("Nothing to undo")
            return
 
        result = self.history.undo(self.engine.actions)
        if result is None:
            return
        self.engine.actions = result
        self.active_index = -1
        self.refresh()
        self.update_statistics()
        self.save_session()
        self.status("Undone")
 
    def redo(self):
        if not self.history.can_redo():
            self.status("Nothing to redo")
            return
 
        result = self.history.redo(self.engine.actions)
        if result is None:
            return
        self.engine.actions = result
        self.active_index = -1
        self.refresh()
        self.update_statistics()
        self.save_session()
        self.status("Redone")
 
    # ==================== FILE OPERATIONS ====================
    def _show_action_menu(self, widget):
        C = self.config.colors
        def _menu():
            mm = tk.Menu(self.root, tearoff=0,
                bg=C["bg_tertiary"], fg=C["text"],
                activebackground=C["accent"], activeforeground="black",
                relief="flat", bd=0, font=("Segoe UI", 9),
                borderwidth=0, activeborderwidth=0)
            mm._icon_refs = []  # keep PhotoImage refs alive
            return mm

        def _add(menu, icon_name, label, command, foreground=None):
            color = foreground if foreground else C["text"]
            ph = IconFactory.get(icon_name, size=14, color=color)
            menu._icon_refs.append(ph)
            kwargs = dict(label=" " + label, command=command,
                          image=ph, compound="left")
            if foreground is not None:
                kwargs["foreground"] = foreground
            menu.add_command(**kwargs)

        m = _menu()

        # ── PROFILES ──────────────────────────────────────
        profiles_sub = _menu()
        active = self.session_manager.active
        for name in self.session_manager.list_profiles():
            dot = ">" if name == active else " "
            profiles_sub.add_command(
                label=f"  {dot}  {name}",
                command=lambda n=name: self._switch_profile(n),
                foreground=C["accent"] if name == active else C["text"])
        profiles_sub.add_separator()
        _add(profiles_sub, "plus",   "New profile…", self._new_profile_dialog, foreground=C["accent"])
        _add(profiles_sub, "pencil", "Rename…",      self._rename_profile_dialog)
        _add(profiles_sub, "trash",  "Delete",       self._delete_profile_confirm, foreground=C["error"])

        ph_books = IconFactory.get("books", size=14, color=C["text"])
        m._icon_refs.append(ph_books)
        m.add_cascade(label="  Profiles", menu=profiles_sub,
                      image=ph_books, compound="left")
        m.add_separator()

        # ── ACTIONS ───────────────────────────────────────
        _add(m, "save",    "Save     Ctrl+S",
             lambda: (self._do_save_session(),
                      self.status(f"Profile ‘{self.session_manager.active}’ saved")))
        _add(m, "export",  "Export JSON…",           self.save)
        _add(m, "import",  "Import JSON…",           self.load)
        _add(m, "export",  "Export CSV…",            self.export_csv)
        _add(m, "import",  "Import CSV…",            self.import_csv)
        m.add_separator()
        _add(m, "reset",   "Reset statistics",       self.reset_stats)
        _add(m, "trash",   "Clear all actions",
             self.clear_all, foreground=C["error"])
        m.add_separator()
        _add(m, "check",   "Debug log",              self.open_debug_viewer)
        _add(m, "check",   "Check for Updates",      self._check_update_manual)

        x = widget.winfo_rootx()
        y = widget.winfo_rooty() + widget.winfo_height()
        try:
            self._action_menu = m   # keep alive, prevent GC
            m.tk_popup(x, y)
        except Exception as e:
            import traceback
            logger.error(f"Menu error: {e}")
            traceback.print_exc()
            messagebox.showerror("Menu Error", str(e))

    def open_debug_viewer(self):
        """Open (or raise) the debug log tail window."""
        logger.info("Debug viewer opened")
        for w in self.root.winfo_children():
            if isinstance(w, DebugViewer) and w.winfo_exists():
                w.lift()
                w.focus_force()
                return
        DebugViewer(self.root, self.config.colors)

    # ── Update checking ─────────────────────────────────
    def _check_update_silent(self):
        """Background update check on startup — silent if no update or no URL."""
        def _bg():
            manifest = check_update(silent=True)
            if manifest:
                self.root.after(0, lambda: self._prompt_update(manifest))
        threading.Thread(target=_bg, daemon=True).start()

    def _check_update_manual(self):
        """Manual update check triggered from menu."""
        self.status("Checking for updates…")

        def _bg():
            manifest = check_update(silent=False)
            if manifest:
                self.root.after(0, lambda: self._prompt_update(manifest))
            else:
                self.root.after(0, lambda: self.status("No updates available"))
        threading.Thread(target=_bg, daemon=True).start()

    def _prompt_update(self, manifest):
        """Show update dialog and optionally trigger auto-update with progress bar."""
        remote_ver = manifest.get("version", "unknown")
        notes = manifest.get("notes", "")
        msg = f"A new version of MacroForge is available.\n\nCurrent: {VERSION}\nLatest: {remote_ver}"
        if notes:
            msg += f"\n\nRelease notes:\n{notes}"
        if not messagebox.askyesno("Update Available", msg + "\n\nDownload and install now?"):
            return

        C = self.config.colors
        dlg = tk.Toplevel(self.root)
        dlg.title("Updating MacroForge")
        dlg.configure(bg=C["bg_secondary"])
        dlg.resizable(False, False)
        dlg.transient(self.root)
        dlg.grab_set()
        dlg.protocol("WM_DELETE_WINDOW", lambda: None)
        px = self.root.winfo_x() + self.root.winfo_width() // 2
        py = self.root.winfo_y() + self.root.winfo_height() // 2
        dlg.geometry(f"380x120+{px - 190}+{py - 60}")

        tk.Label(dlg, text=f"Downloading MacroForge {remote_ver}…", bg=C["bg_secondary"],
                 fg=C["text"], font=("Segoe UI", 10)).pack(pady=(12, 4))

        bar = ttk.Progressbar(dlg, mode="determinate", maximum=100, length=340)
        bar.pack(pady=4)
        style = ttk.Style()
        style.configure("Horizontal.TProgressbar", background=C["accent"])

        info_lbl = tk.Label(dlg, text="Starting…", bg=C["bg_secondary"],
                              fg=C["text_dim"], font=("Segoe UI", 8))
        info_lbl.pack(pady=(2, 8))

        def _on_progress(downloaded, total):
            pct = downloaded / total * 100
            mb_down = downloaded / (1024 * 1024)
            mb_total = total / (1024 * 1024)
            self.root.after(0, lambda: (
                bar.config(value=pct),
                info_lbl.config(text=f"{mb_down:.1f} MB / {mb_total:.1f} MB  ({pct:.0f}%)")
            ))

        def _download():
            try:
                if perform_update(manifest, progress_cb=_on_progress):
                    self.root.after(0, lambda: (dlg.destroy(), self._real_exit()))
                else:
                    self.root.after(0, lambda: (
                        dlg.destroy(),
                        self.status("Update failed — check debug log")
                    ))
            except Exception as e:
                logger.error(f"Update download error: {e}")
                self.root.after(0, lambda: (
                    dlg.destroy(),
                    self.status("Update failed")
                ))

        threading.Thread(target=_download, daemon=True).start()

    # ── Profile management helpers ─────────────────────────────────
    def _switch_profile(self, name: str):
        """Save current, switch to profile `name`, load it."""
        self._do_save_session()          # persist current before switching
        self.session_manager.switch_profile(name)
        data = self.session_manager.load_profile(name)
        self.history.push(self.engine.actions)
        if data:
            try:
                self.engine.actions = [Action.from_dict(x) for x in data.get("actions", [])]
                s = data.get("settings", {})
                self.loops_var.set(s.get("loops", "1"))
                self.speed_var.set(s.get("speed", 1.0))
                self.infinite_loop_var.set(s.get("infinite_loop", False))
                self.human_curve_var.set(s.get("human_curve", True))
                self.timeline.zoom = s.get("zoom", 1.0)
            except Exception:
                self.engine.actions = []
        else:
            self.engine.actions = []
        self.active_index = -1
        self._invalidate_seq_dur()
        self.refresh()
        self.update_statistics(immediate=True)
        self._update_profile_tabs()
        self.status(f"Switched to profile ‘{name}’")
        self._update_title()

    def _new_profile_dialog(self):
        dlg, C = self._make_dialog("New Profile", width=340)
        sec = self._dlg_section(dlg, "PROFILE NAME", C["accent"])
        name_var = tk.StringVar(value="")
        e = tk.Entry(sec, textvariable=name_var, width=22,
            bg=C["bg"], fg=C["text"], insertbackground=C["accent"],
            relief="flat", font=("Segoe UI", 11))
        e.pack(fill="x", pady=4)
        e.focus_set()
        def on_ok():
            name = name_var.get().strip()
            if not name:
                messagebox.showwarning("Name required", "Enter a profile name.", parent=dlg)
                return
            if not self.session_manager.new_profile(name):
                messagebox.showerror("Exists", f"Profile ‘{name}’ already exists.", parent=dlg)
                return
            dlg.destroy()
            self._switch_profile(name)
        self._dlg_buttons(dlg, on_ok, dlg.destroy, ok_text="Create")
        dlg.bind("<Return>", lambda e: on_ok())
        dlg.bind("<Escape>", lambda e: dlg.destroy())

    def _rename_profile_dialog(self):
        old = self.session_manager.active
        dlg, C = self._make_dialog("Rename Profile", width=340)
        sec = self._dlg_section(dlg, f"RENAME ‘{old}’", C["accent"])
        name_var = tk.StringVar(value=old)
        e = tk.Entry(sec, textvariable=name_var, width=22,
            bg=C["bg"], fg=C["text"], insertbackground=C["accent"],
            relief="flat", font=("Segoe UI", 11))
        e.pack(fill="x", pady=4)
        e.select_range(0, tk.END)
        e.focus_set()
        def on_ok():
            new = name_var.get().strip()
            if not new or new == old:
                dlg.destroy(); return
            if not self.session_manager.rename_profile(old, new):
                messagebox.showerror("Failed", f"Could not rename — ‘{new}’ may already exist.", parent=dlg)
                return
            dlg.destroy()
            self._update_profile_tabs()
            self._update_title()
            self.status(f"Renamed to ‘{new}’")
        self._dlg_buttons(dlg, on_ok, dlg.destroy, ok_text="Rename")
        dlg.bind("<Return>", lambda e: on_ok())
        dlg.bind("<Escape>", lambda e: dlg.destroy())

    def _delete_profile_confirm(self):
        name = self.session_manager.active
        if name == ProfileManager.DEFAULT_PROFILE:
            messagebox.showinfo("Cannot delete", "The default profile cannot be deleted.")
            return
        if messagebox.askyesno("Delete profile",
                f"Delete profile ‘{name}’?\nThis cannot be undone."):
            self.session_manager.delete_profile(name)
            self._switch_profile(self.session_manager.active)

        def _build_standalone_script(self):
            """Generate the standalone Python script body. Returns the script string."""
            actions_json = json.dumps([a.to_dict() for a in self.engine.actions], indent=2)
            loops = int(self.loops_var.get()) if not self.infinite_loop_var.get() else -1
            speed = self.speed_var.get()

            return '''#!/usr/bin/env python3
    # -*- coding: utf-8 -*-
    r"""Standalone Macro — generated by MacroForge"""
    import sys, json, time, ctypes, random, os

    # ── CONFIG ─────────────────────────────────────────────────────
    ACTIONS = json.loads(r''' + repr(actions_json) + ''')
    LOOPS   = ''' + str(loops) + '''
    SPEED   = ''' + str(speed) + '''

    # ── SCAN-CODE TABLE (0-9 digits) ───────────────────────────────
    _SC_MAP = {
        "0":0x52,"1":0x02,"2":0x03,"3":0x04,"4":0x05,
        "5":0x06,"6":0x07,"7":0x08,"8":0x09,"9":0x0A,
        "a":0x1E,"b":0x30,"c":0x2E,"d":0x20,"e":0x12,"f":0x21,
        "g":0x22,"h":0x23,"i":0x17,"j":0x24,"k":0x25,"l":0x26,
        "m":0x32,"n":0x31,"o":0x18,"p":0x19,"q":0x10,"r":0x13,
        "s":0x1F,"t":0x14,"u":0x16,"v":0x2F,"w":0x11,"x":0x2D,
        "y":0x15,"z":0x2C," ":0x39,"enter":0x1C,"tab":0x0F,
        "shift":0x2A,"ctrl":0x1D,"alt":0x38,"esc":0x01,
    }

    class _Input:
        """Zero-dependency Windows input via ctypes SendInput."""
        def __init__(self):
            self._u = ctypes.windll.user32
            self._sm = self._u.GetSystemMetrics
            self._sw, self._sh = self._sm(0), self._sm(1)

        def _key(self, vk, sc, flags=0):
            class KI(ctypes.Structure):
                _fields_ = [("wVk",ctypes.c_ushort),("wScan",ctypes.c_ushort),
                            ("dwFlags",ctypes.c_uint),("time",ctypes.c_uint),
                            ("dwExtraInfo",ctypes.POINTER(ctypes.c_ulong))]
            ki = KI(); ki.wVk = vk; ki.wScan = sc
            ki.dwFlags = flags | 8; ki.time = 0; ki.dwExtraInfo = None
            class INP(ctypes.Structure): _fields_=[("type",ctypes.c_uint),("ki",KI)]
            i = INP(); i.type = 1; i.ki = ki
            self._u.SendInput(1, ctypes.byref(i), ctypes.sizeof(INP))

        def key_down(self, k):
            k = k.lower()
            sc = _SC_MAP.get(k, 0)
            vk = ord(k.upper()) if len(k) == 1 else 0
            self._key(vk, sc, 0)

        def key_up(self, k):
            k = k.lower()
            sc = _SC_MAP.get(k, 0)
            vk = ord(k.upper()) if len(k) == 1 else 0
            self._key(vk, sc, 2)

        def click(self, x, y, button="left", double=False):
            ax = int(x * 65535 // (self._sw - 1)) if self._sw > 1 else 0
            ay = int(y * 65535 // (self._sh - 1)) if self._sh > 1 else 0
            down = {"left": 0x0002, "right": 0x0008, "middle": 0x0020}
            up   = {"left": 0x0004, "right": 0x0010, "middle": 0x0040}
            md = down.get(button, down["left"])
            mu = up.get(button, up["left"])
            class MI(ctypes.Structure):
                _fields_ = [("dx",ctypes.c_long),("dy",ctypes.c_long),
                            ("mouseData",ctypes.c_ulong),("dwFlags",ctypes.c_ulong),
                            ("time",ctypes.c_ulong),("dwExtraInfo",ctypes.POINTER(ctypes.c_ulong))]
            class INP(ctypes.Structure): _fields_=[("type",ctypes.c_uint),("mi",MI)]
            # Move absolute
            m = MI(ax, ay, 0, 0x8001|0x0001, 0, None)
            i = INP(); i.type = 0; i.mi = m; self._u.SendInput(1, ctypes.byref(i), ctypes.sizeof(INP))
            # Click down
            m.dwFlags = md
            i = INP(); i.type = 0; i.mi = m; self._u.SendInput(1, ctypes.byref(i), ctypes.sizeof(INP))
            # Click up
            m.dwFlags = mu
            i = INP(); i.type = 0; i.mi = m; self._u.SendInput(1, ctypes.byref(i), ctypes.sizeof(INP))
            if double:
                time.sleep(0.05)
                m.dwFlags = md
                i = INP(); i.type = 0; i.mi = m; self._u.SendInput(1, ctypes.byref(i), ctypes.sizeof(INP))
                m.dwFlags = mu
                i = INP(); i.type = 0; i.mi = m; self._u.SendInput(1, ctypes.byref(i), ctypes.sizeof(INP))

        def find_image(self, tpl_path, region=None, confidence=0.8):
            """Image search — falls back to None if Pillow/pyautogui missing."""
            try:
                from PIL import Image
                import pyautogui
                if region:
                    return pyautogui.locateCenterOnScreen(tpl_path, region=region, confidence=confidence)
                return pyautogui.locateCenterOnScreen(tpl_path, confidence=confidence)
            except Exception:
                return None

    def _run(actions, loops, speed):
        inp = _Input()
        running = True
        loop_num = 0
        total = len(actions)

        def _print_progress(current, label=""):
            pct = int(current / total * 100) if total else 0
            bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
            print(f"\\r[{bar}] {pct:3d}%  {label:<30}", end="", flush=True)

        def _press(action):
            key = action.get("key", "")
            dur = action.get("duration", 0.1) / speed
            rand = action.get("random_delay", 0.0)
            if rand:
                dur += random.uniform(0, rand)
            if action.get("hold_mode", False):
                inp.key_down(key)
                time.sleep(dur)
                inp.key_up(key)
            else:
                inp.key_down(key)
                time.sleep(0.02)
                inp.key_up(key)
                time.sleep(dur)

        def _get_mouse_pos():
            pt = ctypes.wintypes.POINT()
            ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
            return pt.x, pt.y

        def _do_click(action):
            mode = action.get("click_coord_mode", "absolute")
            x = action.get("click_x", 0)
            y = action.get("click_y", 0)
            rr = action.get("click_rand_radius", 0)
            btn = action.get("click_button", "left")
            dbl = (btn == "double")
            if btn == "double": btn = "left"
            if mode == "current":
                x, y = _get_mouse_pos()
            if rr:
                x += random.randint(-rr, rr)
                y += random.randint(-rr, rr)
            inp.click(x, y, button=btn, double=dbl)
            time.sleep(action.get("duration", 0.0) / speed)

        def _do_pause(action):
            dur = action.get("duration", 0.5) / speed
            rand = action.get("random_delay", 0.0)
            if rand:
                dur += random.uniform(0, rand)
            time.sleep(dur)

        def _do_image(action):
            tpl = action.get("image_path", "")
            if not tpl or not os.path.exists(tpl):
                print(f"\\n[SKIP] Image not found: {tpl}")
                return
            region = action.get("image_region")
            conf = action.get("image_confidence", 0.8)
            wait = action.get("image_wait", 5.0)
            found = False
            start = time.time()
            while time.time() - start < wait:
                pt = inp.find_image(tpl, region=region, confidence=conf)
                if pt:
                    x, y = pt
                    if action.get("image_click", False):
                        inp.click(x, y)
                    found = True
                    break
                time.sleep(0.2)
            if not found:
                print(f"\\n[MISS] Image not found: {tpl}")

        def _exec(idx, action):
            t = action.get("action_type", "key")
            label = action.get("label", action.get("key", ""))[:30]
            _print_progress(idx + 1, label)
            reps = max(1, action.get("repeat_count", 1))
            for _ in range(reps):
                if not running:
                    return
                if t == "pause":
                    _do_pause(action)
                elif t == "click":
                    _do_click(action)
                elif t == "image":
                    _do_image(action)
                else:
                    _press(action)

        print("=" * 50)
        print("  MacroForge Standalone Runner")
        print("=" * 50)
        print(f"  Actions: {total}  |  Loops: {'∞' if loops < 0 else loops}  |  Speed: {speed}x")
        print("  Press Ctrl+C to stop")
        print("=" * 50)
        try:
            while running:
                if loops >= 0 and loop_num >= loops:
                    break
                loop_num += 1
                if loops != 1:
                    print(f"\\n--- Loop {loop_num} {'(infinite)' if loops < 0 else f'/ {loops}'} ---")
                for idx, action in enumerate(actions):
                    _exec(idx, action)
            print("\\n\\nDone.")
        except KeyboardInterrupt:
            running = False
            print("\\n\\nStopped by user.")

    if __name__ == "__main__":
        if "--dry-run" in sys.argv:
            print("[DRY-RUN] Syntax OK, {} actions ready".format(len(ACTIONS)))
            sys.exit(0)
        _run(ACTIONS, LOOPS, SPEED)
    '''
        def compile_standalone(self):
            """Export current macro to a standalone .py + .bat launcher."""
            if not self.engine.actions:
                messagebox.showwarning("No Actions", "Add some actions first.")
                return
            path = filedialog.asksaveasfilename(
                defaultextension=".py",
                filetypes=[("Python script", "*.py"), ("All files", "*.*")],
                title="Compile macro to standalone script"
            )
            if not path:
                return
            try:
                py_script = self._build_standalone_script()

                # Validate before writing
                try:
                    ast.parse(py_script)
                except SyntaxError as e:
                    raise RuntimeError(f"Generated script has syntax error: {e}")

                # Write .py
                with open(path, "w", encoding="utf-8") as f:
                    f.write(py_script)

                # Write .bat launcher
                bat_path = os.path.splitext(path)[0] + ".bat"
                bat = '''@echo off
    chcp 65001 >nul
    title MacroForge Standalone
    echo ================================================
    echo   MacroForge Standalone Runner
    echo ================================================
    python --version >nul 2>&1
    if errorlevel 1 (
        echo Python not found. Install Python from python.org
        pause
        exit /b 1
    )
    python "''' + os.path.basename(path) + '''" %*
    echo.
    echo Press any key to exit...
    pause >nul
    '''
                with open(bat_path, "w", encoding="utf-8") as f:
                    f.write(bat)

                self.status(f"Compiled standalone → {path} + {bat_path}")
                messagebox.showinfo(
                    "Compiled",
                    f"Standalone macro compiled successfully.\n\n"
                    f"Python script: {path}\n"
                    f"Batch launcher: {bat_path}\n\n"
                    f"Double-click the .bat file to run without opening MacroForge."
                )
            except Exception as e:
                messagebox.showerror("Compile Error", str(e))
        def test_compile_standalone(self):
            """Generate the standalone script in a temp file and run --dry-run."""
            if not self.engine.actions:
                messagebox.showwarning("No Actions", "Add some actions first.")
                return
            import tempfile, subprocess
            try:
                py_script = self._build_standalone_script()

                try:
                    ast.parse(py_script)
                except SyntaxError as e:
                    raise RuntimeError(f"Generated script has syntax error: {e}")

                fd, tmp_path = tempfile.mkstemp(suffix=".py", prefix="macroforge_test_")
                try:
                    with os.fdopen(fd, "w", encoding="utf-8") as f:
                        f.write(py_script)
                    result = subprocess.run(
                        [sys.executable, tmp_path, "--dry-run"],
                        capture_output=True, text=True, timeout=10
                    )
                    if result.returncode == 0:
                        self.status(f"Test compile OK — {result.stdout.strip()}")
                        messagebox.showinfo("Test Compile", result.stdout.strip())
                    else:
                        raise RuntimeError(result.stderr or "Unknown error")
                finally:
                    try:
                        os.remove(tmp_path)
                    except Exception:
                        pass
            except Exception as e:
                messagebox.showerror("Test Compile Failed", str(e))
    def _update_title(self):
        self.root.title(f"MacroForge  v{VERSION}  —  {self.session_manager.active}")

    def _update_profile_tabs(self):
        """Rebuild the profile tab strip to reflect current profiles."""
        C = self.config.colors
        # Clear existing tabs
        for w in self._tabs_inner.winfo_children():
            w.destroy()

        active = self.session_manager.active
        for name in self.session_manager.list_profiles():
            is_active = (name == active)
            bg   = C["bg_tertiary"] if is_active else C["bg_secondary"]
            fg   = C["accent"]      if is_active else C["text_dim"]
            tab  = tk.Frame(self._tabs_inner, bg=bg, cursor="hand2")
            tab.pack(side="left", padx=(2, 0), pady=4)

            # Active indicator bar at top of tab
            indicator = tk.Frame(tab, height=2,
                                 bg=C["accent"] if is_active else bg)
            indicator.pack(fill="x")

            inner = tk.Frame(tab, bg=bg)
            inner.pack(padx=6, pady=(2, 4))

            lbl = tk.Label(inner, text=name, bg=bg, fg=fg,
                           font=("Segoe UI", 8, "bold" if is_active else "normal"),
                           cursor="hand2")
            lbl.pack(side="left")

            # Close (×) button — only for non-default profiles
            if name != ProfileManager.DEFAULT_PROFILE:
                close_btn = tk.Label(inner, text=" ×", bg=bg,
                                     fg=C["text_dim"], font=("Segoe UI", 8),
                                     cursor="hand2")
                close_btn.pack(side="left")
                close_btn.bind("<Button-1>",
                    lambda e, n=name: self._delete_profile_tab(n))
                close_btn.bind("<Enter>",
                    lambda e, w=close_btn, _b=bg: w.config(fg=C["error"]))
                close_btn.bind("<Leave>",
                    lambda e, w=close_btn, _b=bg: w.config(fg=C["text_dim"]))

            # Click to switch
            for w in (tab, inner, lbl, indicator):
                w.bind("<Button-1>", lambda e, n=name: self._switch_profile(n))
            # Hover highlight
            def _enter(e, t=tab, _bg=bg, _is=is_active):
                if not _is:
                    t.config(bg=C["hover"])
                    for c in t.winfo_children():
                        try: c.config(bg=C["hover"])
                        except Exception: pass
            def _leave(e, t=tab, _bg=bg, _is=is_active):
                if not _is:
                    t.config(bg=_bg)
                    for c in t.winfo_children():
                        try: c.config(bg=_bg)
                        except Exception: pass
            tab.bind("<Enter>", _enter)
            tab.bind("<Leave>", _leave)

    def _delete_profile_tab(self, name: str):
        """Close-button delete with confirmation."""
        if name == self.session_manager.active:
            self._delete_profile_confirm()
        else:
            if messagebox.askyesno("Delete profile",
                    f"Delete profile '{name}'?\nThis cannot be undone."):
                self.session_manager.delete_profile(name)
                self._update_profile_tabs()

    def save(self):
        f = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if not f:
            return
 
        try:
            with open(f, "w") as file:
                json.dump([a.to_dict() for a in self.engine.actions], file, indent=2)
            self.status(f"Saved to {f}")
        except Exception as e:
            messagebox.showerror("Save Error", str(e))
 
    def load(self):
        """Import a JSON file as a new named profile and switch to it."""
        f = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if not f:
            return
        try:
            with open(f, "r") as file:
                raw = json.load(file)
            if isinstance(raw, list):
                actions_data = raw
                suggested = os.path.splitext(os.path.basename(f))[0]
            else:
                actions_data = raw.get("actions", [])
                suggested = raw.get("profile") or os.path.splitext(os.path.basename(f))[0]
        except Exception as ex:
            messagebox.showerror("Import Error", str(ex))
            return

        dlg, C = self._make_dialog("Import as Profile", width=360)
        sec = self._dlg_section(dlg, "PROFILE NAME", C["accent"])
        tk.Label(sec, text="Choose a name for the imported profile:",
            bg=C["bg_tertiary"], fg=C["text_dim"],
            font=("Segoe UI", 8, "italic")).pack(anchor="w", pady=(0, 4))
        name_var = tk.StringVar(value=suggested)
        ent = tk.Entry(sec, textvariable=name_var, width=24,
            bg=C["bg"], fg=C["text"], insertbackground=C["accent"],
            relief="flat", font=("Segoe UI", 11))
        ent.pack(fill="x", pady=(0, 4))
        ent.select_range(0, tk.END)
        ent.focus_set()

        def on_ok():
            name = name_var.get().strip()
            if not name:
                messagebox.showwarning("Name required", "Enter a profile name.", parent=dlg)
                return
            path = self.session_manager._profile_path(name)
            if os.path.exists(path):
                if not messagebox.askyesno("Overwrite?",
                        f"Profile \u2018{name}\u2019 already exists.\nOverwrite it?", parent=dlg):
                    return
            try:
                actions = [Action.from_dict(x) for x in actions_data]
            except Exception as ex:
                messagebox.showerror("Import Error", str(ex), parent=dlg)
                return
            self.session_manager.save_profile(actions, {}, name=name)
            dlg.destroy()
            self._switch_profile(name)
            self.status(f"Imported \u2018{name}\u2019 from {os.path.basename(f)}")

        self._dlg_buttons(dlg, on_ok, dlg.destroy, ok_text="Import")
        dlg.bind("<Return>", lambda e: on_ok())
        dlg.bind("<Escape>", lambda e: dlg.destroy())
 
    def clear_all(self):
        if not self.engine.actions:
            return
 
        if messagebox.askyesno("Confirm", "Clear all actions?"):
            self.history.push(self.engine.actions)
            self.engine.actions.clear()
            self.active_index = -1
            self.refresh()
            self.update_statistics()
            self.save_session()
            self.status("Cleared all actions")
    

    def reset_stats(self):
        """Reset statistics display to 0 without clearing actions"""
        self.actions_played = 0
        self.session_elapsed_time = 0.0
        self.session_start_time = None
        self.engine.loops_completed_count = 0
        self._render_stats()
        self.status("Statistics reset")
 
    # ==================== PLAYBACK ====================
    def update_speed(self, event=None):
        self.engine.speed_multiplier = self.speed_var.get()
 
    def _on_pause_changed(self, paused: bool):
        if paused:
            def _apply():
                self.timeline.set_paused(True)
                self._set_transport(self.start_btn, "normal", text="Resume", active_bg=self.config.colors["accent"])
                self._set_transport(self.pause_btn, "disabled", inactive_bg=self.config.colors["bg_tertiary"])
                self._set_transport(self.stop_btn, "normal", active_bg="#ff4444")
                self.status_dot.config(fg=self.config.colors["warning"])
        else:
            def _apply():
                self.timeline.set_paused(False)
                self._set_transport(self.start_btn, "disabled", text="Start", inactive_bg=self.config.colors["bg_tertiary"])
                if self.engine.running:
                    self._set_transport(self.pause_btn, "normal", active_bg="#f0a844")
                    self._set_transport(self.stop_btn, "normal", active_bg="#ff4444")
                else:
                    self._set_transport(self.pause_btn, "disabled", inactive_bg=self.config.colors["bg_tertiary"])
                    self._set_transport(self.stop_btn, "disabled", inactive_bg=self.config.colors["bg_tertiary"])
                self.status_dot.config(fg=self.config.colors["accent"])
        self.root.after(0, _apply)

    def _show_inspector(self, visible: bool, action_type: str = ""):
        """Toggle inspector panels. Shows the right panel for the selected action type."""
        self.insp_hint.pack_forget()
        self.insp_key.pack_forget()
        self.insp_pause.pack_forget()
        self.insp_click.pack_forget()
        self.insp_image.pack_forget()
        if not visible:
            self.insp_hint.pack(side="left", padx=6)
        elif action_type == "image":
            self.insp_image.pack(side="left", fill="x", expand=True)
        elif action_type == "click":
            self.insp_click.pack(side="left", fill="x", expand=True)
        elif action_type == "pause":
            self.insp_pause.pack(side="left", fill="x", expand=True)
        else:
            self.insp_key.pack(side="left", fill="x", expand=True)

    def _on_escape(self, event=None):
        """ESC: cancel start countdown; or pause+auto-resume; or cancel resume countdown."""
        # Cancel start countdown
        if self._countdown_active:
            self._countdown_active = False
            if self._countdown_after:
                self.root.after_cancel(self._countdown_after)
                self._countdown_after = None
            self._set_transport(self.start_btn, "normal", active_bg=self.config.colors["accent"])
            self._set_transport(self.pause_btn, "disabled", inactive_bg=self.config.colors["bg_tertiary"])
            self._set_transport(self.stop_btn, "disabled", inactive_bg=self.config.colors["bg_tertiary"])
            self.status("Countdown cancelled")
            return

        # Cancel resume countdown — stay paused
        if self._resume_countdown_active:
            self._resume_countdown_active = False
            if self._resume_countdown_after:
                self.root.after_cancel(self._resume_countdown_after)
                self._resume_countdown_after = None
            self.status("Paused  —  Esc to resume")
            # Restore paused UI state
            self._set_transport(self.start_btn, "normal", text="Resume", active_bg=self.config.colors["accent"])
            self._set_transport(self.pause_btn, "disabled", inactive_bg=self.config.colors["bg_tertiary"])
            self._set_transport(self.stop_btn, "normal", active_bg="#ff4444")
            return

        # Running → instant pause + auto-resume countdown
        if self.engine.running and not self.engine.paused:
            self.engine.toggle_pause()
            self._start_resume_countdown(3)
            return

        # Paused with no countdown → resume immediately
        if self.engine.running and self.engine.paused:
            self.engine.toggle_pause()
            return

        # Nothing running — silent ESC, give brief feedback
        if not self.engine.running:
            self.status("Nothing playing  —  press Start to begin")

    def _start_resume_countdown(self, n: int):
        self._resume_countdown_active = True
        self._resume_countdown_after  = None
        self._run_resume_countdown(n)

    def _run_resume_countdown(self, n: int):
        if not self._resume_countdown_active:
            return
        if n > 0:
            self.status(f"Resuming in {n}...  (Esc to stay paused)")
            self._resume_countdown_after = self.root.after(
                1000, lambda: self._run_resume_countdown(n - 1))
        else:
            self._resume_countdown_active = False
            self._resume_countdown_after  = None
            if self.engine.paused:
                self.engine.toggle_pause()   # resume

    def _run_countdown(self, loops: int, n: int):
        """Tick-down n..1 on status bar then launch engine thread."""
        if not self._countdown_active:
            self._set_transport(self.start_btn, "normal", active_bg=self.config.colors["accent"])
            self.status("Cancelled")
            return
        if n > 0:
            self.status(f"Starting in {n}...  (Esc to cancel)")
            self._countdown_after = self.root.after(1000, lambda: self._run_countdown(loops, n - 1))
        else:
            self._countdown_active = False
            self.session_start_time = time.time()
            self._set_transport(self.start_btn, "disabled", text="Start", inactive_bg=self.config.colors["bg_tertiary"])
            self._engine_thread = threading.Thread(
                target=self.engine.run,
                args=(loops,),
                daemon=True
            )
            self._engine_thread.start()
            self._set_transport(self.pause_btn, "normal", active_bg="#f0a844")
            self._set_transport(self.stop_btn, "normal", active_bg="#ff4444")
            self.root.after(1000, self._tick_session_time)

    def _hotkey_start(self):
        if self._recorder["running"]:
            return
        if self.engine.running and self.engine.paused:
            self.start()  # resume
        elif not self.engine.running:
            self.start()

    def _hotkey_stop(self):
        if self._recorder["running"]:
            self._stop_recording()
            return
        if self.engine.running:
            self.stop()

    def start(self):
        # Cancel any pending resume countdown to avoid race
        if self._resume_countdown_active:
            self._resume_countdown_active = False
            if self._resume_countdown_after:
                self.root.after_cancel(self._resume_countdown_after)
                self._resume_countdown_after = None

        if self.engine.running and self.engine.paused:
            self.engine.toggle_pause()
            self._set_transport(self.start_btn, "disabled", text="Start", inactive_bg=self.config.colors["bg_tertiary"])
            return

        if not self.engine.actions:
            messagebox.showwarning("No Actions", "Add some actions first")
            return

        self.reset_stats()
 
        try:
            self.engine.speed_multiplier = self.speed_var.get()
            self.engine.infinite_loop = self.infinite_loop_var.get()
            self.engine.simulation_mode = self.simulation_var.get()
            self.engine.focus_lock = self.focus_lock_var.get()
            if self.engine.focus_lock:
                self.engine.capture_focus_window()
                self.status("Focus locked — will restore window before each action")
 
            loops = int(self.loops_var.get()) if not self.engine.infinite_loop else 1
            if loops <= 0:
                raise ValueError("Loops must be positive")
 
            self._countdown_active = True
            self._set_transport(self.start_btn, "disabled", inactive_bg=self.config.colors["bg_tertiary"])
            self._set_transport(self.pause_btn, "disabled", inactive_bg=self.config.colors["bg_tertiary"])
            self._set_transport(self.stop_btn, "disabled", inactive_bg=self.config.colors["bg_tertiary"])
            self.progress_bar["value"] = 0
            self.progress_label.config(text="0%")
            self._run_countdown(loops, 1)
 
        except ValueError as e:
            messagebox.showerror("Invalid Input", f"Loops must be a positive number: {e}")
 
    def stop(self):
        self.engine.stop()
        self.timeline.clear_playing()
        self.progress_bar["value"] = 0
        self.progress_label.config(text="0%")
        if self.session_start_time:
            self.session_elapsed_time = time.time() - self.session_start_time
        self.session_start_time = None
        self.engine.loops_completed_count = 0
        self.update_statistics(immediate=True)
        self._set_transport(self.start_btn, "normal", text="Start", active_bg=self.config.colors["accent"])
        self._set_transport(self.pause_btn, "disabled", inactive_bg=self.config.colors["bg_tertiary"])
        self._set_transport(self.stop_btn, "disabled", inactive_bg=self.config.colors["bg_tertiary"])
        self.status("Stopped")
 
    def update_progress(self, value: float):
        """Update progress bar on each action"""
        def _apply(v=value):
            self.progress_bar.config(value=v)
            self.progress_label.config(text=f"{v:.0f}%")
        self.root.after(0, _apply)

    def play_cb(self, index: int):
        self.root.after(0, lambda: self.timeline.set_playing(index))

    def _tick_session_time(self):
        """Single recurring ticker - started once in start(), cancelled in stop()"""
        if not self.engine.running:
            return
        self._render_stats()
        self.root.after(1000, self._tick_session_time)
 
    def playback_complete(self):
        if self.session_start_time:
            self.session_elapsed_time = time.time() - self.session_start_time
            self.session_start_time = None
        def _done():
            self.timeline.clear_playing()
            self.progress_bar.config(value=100)
            self.progress_label.config(text="100%")
            self._set_transport(self.start_btn, "normal", text="Start", active_bg=self.config.colors["accent"])
            self._set_transport(self.pause_btn, "disabled", inactive_bg=self.config.colors["bg_tertiary"])
            self._set_transport(self.stop_btn, "disabled", inactive_bg=self.config.colors["bg_tertiary"])
        self.root.after(0, _done)
 
    # ==================== ACTION HOOKS ====================
    @staticmethod
    def _format_hms(seconds: float) -> str:
        """Format seconds as H:MM:SS."""
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        return f"{h}:{m:02d}:{s:02d}"

    def _render_stats(self):
        """Stats label:
        Actions      = individual actions fired (increments each action).
        Loops        = loops fully completed.
        Seq          = sum of all action durations in the sequence.
        Time         = seq_duration * loops_completed.
        """
        seq_dur      = self._seq_dur_cache
        loops_done   = self.engine.loops_completed_count
        session_time = seq_dur * loops_done

        self._stat_actions.config(text=str(self.actions_played))
        self._stat_loops.config(text=str(loops_done))
        self._stat_seq.config(text=f"{seq_dur:.1f}s")
        self._stat_time.config(text=self._format_hms(session_time))


    def before_action(self, action: Action):
        """Called before each action executes"""
        self.actions_played += 1
        if not self._stats_timer:
            self.root.after(0, self._render_stats)
 
    def after_action(self, action: Action):
        """Called after each action executes"""
        pass  # Can be used for logging, sound effects, etc.
 
    # ==================== UI HELPERS ====================
    def _invalidate_seq_dur(self):
        """Recompute and cache total sequence duration. Call whenever actions list changes."""
        self._seq_dur_cache = sum(a.duration for a in self.engine.actions)

    def refresh(self):
        self._invalidate_seq_dur()
        self.timeline.refresh()
        self.update_statistics()
 
    def update_statistics(self, immediate: bool = False):
        """Update statistics display with throttling"""
        if self._stats_timer:
            self.root.after_cancel(self._stats_timer)

        def _update():
            self._render_stats()
            self._stats_timer = None

        if immediate:
            _update()
        else:
            self._stats_timer = self.root.after(200, _update)

    def _throttled_status(self, text: str):
        """Queue status text; flushes to UI at most every 50 ms."""
        self._pending_status = text
        if self._ui_timer is None:
            self._ui_timer = self.root.after(50, self._flush_ui)

    def _throttled_progress(self, value: float):
        """Queue progress value; flushes to UI at most every 50 ms."""
        self._pending_progress = value
        if self._ui_timer is None:
            self._ui_timer = self.root.after(50, self._flush_ui)

    def _flush_ui(self):
        """Apply any queued status / progress updates to the UI."""
        if self._pending_status is not None:
            self.status(self._pending_status)
            self._pending_status = None
        if self._pending_progress is not None:
            self.update_progress(self._pending_progress)
            self._pending_progress = None
        self._ui_timer = None

    def status(self, text: str):
        logger.info(f"STATUS: {text}")
        if self.engine.simulation_mode and self.engine.running:
            text = f"[SIM] {text}"
        dot_color = self.config.colors["accent"] if self.engine.running else self.config.colors["border"]
        def _apply():
            self.status_bar.config(text=text)
            self.status_dot.config(fg=dot_color)
        if threading.current_thread() is threading.main_thread():
            _apply()
        else:
            self.root.after(0, _apply)
 
    # ==================== HOTKEYS ====================
    def _on_key_press_global(self, key):
        """Global hotkeys — dispatched on main thread via after().
        During recording, only Esc and F7 (toggle record) are active."""
        try:
            if key == keyboard.Key.esc:
                self.root.after(0, self._on_escape)
                return
            if self._recorder["running"]:
                # Only F7 works during recording; everything else is ignored
                if key == keyboard.Key.f7:
                    self.root.after(0, self._hotkey_record)
                return
            if key == keyboard.Key.f9:
                self.root.after(0, self._hotkey_toggle)
            elif key == keyboard.Key.f5:
                self.root.after(0, self._hotkey_start)
            elif key == keyboard.Key.f6:
                self.root.after(0, self._hotkey_stop)
            elif key == keyboard.Key.f7:
                self.root.after(0, self._hotkey_record)
        except Exception as e:
            logger.error(f"_on_key_press_global error: {e}")

    def _hotkey_toggle(self):
        """F9: start if idle, stop if running."""
        if self._recorder["running"]:
            return
        if self.engine.running:
            self.stop()
        else:
            self.start()
 
    # ==================== CLEANUP ====================
    def on_close(self):
        """Close button exits the application immediately."""
        self._real_exit()

    def _on_unmap(self, event=None):
        """Minimize button hides window to system tray."""
        if event is not None and event.widget is not self.root:
            return
        try:
            if self.root.winfo_exists() and self.root.state() == "iconic":
                self.root.withdraw()
        except Exception:
            pass

    def _real_exit(self):
        """Perform actual cleanup and exit (called from tray menu)."""
        logger.info("Application exiting")
        self.engine.stop()
        if self._engine_thread and self._engine_thread.is_alive():
            self._engine_thread.join(timeout=0.3)
        self.listener.stop()
        if self._tray_icon:
            self._tray_icon.stop()
        if self._save_session_after:
            try:
                self.root.after_cancel(self._save_session_after)
            except Exception:
                pass
            self._save_session_after = None
        self._do_save_session()
        try:
            ctypes.windll.winmm.timeEndPeriod(1)
        except Exception:
            pass
        self.root.destroy()
 
 
# =========================================================
# RUN
# =========================================================
if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()


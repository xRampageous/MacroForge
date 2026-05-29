import tkinter as tk
from tkinter import ttk, messagebox
from models import Action


class KeyEditorMixin:
        def open_key_dialog(self):
            dlg, C = self._make_dialog("Add Key Action", width=400)
    
            sec = self._dlg_section(dlg, "KEY PRESS", C["accent"])
    
            key_var = tk.StringVar(value="w")
    
            def _capture_key(e):
                k = e.keysym.lower()
                if k not in ("return", "escape"):
                    key_var.set(k)
                    key_entry.config(fg=C["accent"])
    
            # Key entry with capture
            kr = tk.Frame(sec, bg=C["bg_tertiary"]); kr.pack(fill="x", pady=(0,6))
            tk.Label(kr, text="Key", bg=C["bg_tertiary"], fg=C["text_dim"],
                     font=("Segoe UI", 9), width=14, anchor="w").pack(side="left")
            combo = ttk.Combobox(kr, textvariable=key_var, values=self.KEY_VALUES, width=10)
            combo.pack(side="left", padx=(0,6))
            key_entry = tk.Entry(kr, width=10, bg=C["bg"], fg=C["text"],
                                 insertbackground=C["accent"], relief="flat",
                                 font=("Segoe UI", 9), readonlybackground=C["bg"])
            key_entry.insert(0, "press a key…")
            key_entry.config(state="readonly")
            key_entry.pack(side="left", padx=(0,6))
            key_entry.bind("<KeyPress>", _capture_key)
            tk.Label(kr, text="← click & press", bg=C["bg_tertiary"], fg=C["text_dim"],
                     font=("Segoe UI", 8, "italic")).pack(side="left")
    
            sec2 = self._dlg_section(dlg, "TIMING & BEHAVIOUR", C["accent"])
    
            dur_var  = tk.StringVar(value="0.5")
            rand_var = tk.StringVar(value="0.0")
            rep_var  = tk.StringVar(value="1")
            hold_var = tk.BooleanVar(value=True)
            lane_var = tk.IntVar(value=0)
            rndK_var = tk.BooleanVar(value=False)
            lbl_var  = tk.StringVar(value="")
    
            def entry(parent, var, w=8):
                return tk.Entry(parent, textvariable=var, width=w,
                    bg=C["bg"], fg=C["text"], insertbackground=C["accent"],
                    relief="flat", font=("Segoe UI", 9))
    
            self._dlg_field(sec2, "Duration (s)", lambda p: entry(p, dur_var), "how long to hold")
            self._dlg_field(sec2, "Random ± (s)", lambda p: entry(p, rand_var), "jitter added per press")
            self._dlg_field(sec2, "Repeat ×",    lambda p: entry(p, rep_var, 5), "times to press in a row")
            self._dlg_field(sec2, "Label",        lambda p: entry(p, lbl_var, 6))
    
            flags = tk.Frame(sec2, bg=C["bg_tertiary"]); flags.pack(fill="x", pady=(4,0))
            for text, var in [("Hold key down", hold_var), ("Lane 1 only", lane_var), ("Random key", rndK_var)]:
                tk.Checkbutton(flags, text=text, variable=var,
                    bg=C["bg_tertiary"], fg=C["text"], selectcolor=C["accent_glow"],
                    activebackground=C["bg_tertiary"], font=("Segoe UI", 9)).pack(side="left", padx=(0,10))
    
            def on_ok():
                try:
                    k = key_var.get().strip() or "w"
                    dur = float(dur_var.get())
                    if dur <= 0: raise ValueError
                    self.key_var.set(k)
                    self.dur_var.set(str(dur))
                    self.rand_delay_var.set(rand_var.get())
                    self.hold_var.set(hold_var.get())
                    self.lane_var.set(lane_var.get())
                    self.rand_key_var.set(rndK_var.get())
                    self.history.push(self.engine.actions)
                    act = Action(k, dur, hold_var.get(), lane_var.get(),
                                 float(rand_var.get() or "0"), rndK_var.get())
                    act.repeat_count = max(1, int(rep_var.get() or "1"))
                    act.label = lbl_var.get()
                    self.engine.actions.append(act)
                    self.active_index = len(self.engine.actions) - 1
                    self.refresh(); self.update_statistics(); self.save_session()
                    self.timeline.ensure_visible(self.active_index)
                    self.status(f"Added key: {k}")
                    dlg.destroy()
                except ValueError:
                    messagebox.showerror("Invalid", "Duration must be a positive number.", parent=dlg)
    
            self._dlg_buttons(dlg, on_ok, dlg.destroy, ok_text="Add Key")
            dlg.bind("<Return>", lambda e: on_ok())
            dlg.bind("<Escape>", lambda e: dlg.destroy())
        def open_key_editor(self, index: int):
            """Open dialog to edit an existing key action."""
            if index < 0 or index >= len(self.engine.actions):
                return
            existing = self.engine.actions[index]
            dlg, C = self._make_dialog("Edit Key Action", width=400)
    
            sec = self._dlg_section(dlg, "KEY PRESS", C["accent"])
    
            key_var = tk.StringVar(value=existing.key)
    
            def _capture_key(e):
                k = e.keysym.lower()
                if k not in ("return", "escape"):
                    key_var.set(k)
                    key_entry.config(fg=C["accent"])
    
            kr = tk.Frame(sec, bg=C["bg_tertiary"]); kr.pack(fill="x", pady=(0,6))
            tk.Label(kr, text="Key", bg=C["bg_tertiary"], fg=C["text_dim"],
                     font=("Segoe UI", 9), width=14, anchor="w").pack(side="left")
            combo = ttk.Combobox(kr, textvariable=key_var, values=self.KEY_VALUES, width=10)
            combo.pack(side="left", padx=(0,6))
            key_entry = tk.Entry(kr, width=10, bg=C["bg"], fg=C["text"],
                                 insertbackground=C["accent"], relief="flat",
                                 font=("Segoe UI", 9), readonlybackground=C["bg"])
            key_entry.insert(0, existing.key)
            key_entry.config(state="readonly")
            key_entry.pack(side="left", padx=(0,6))
            key_entry.bind("<KeyPress>", _capture_key)
            tk.Label(kr, text="← click & press", bg=C["bg_tertiary"], fg=C["text_dim"],
                     font=("Segoe UI", 8, "italic")).pack(side="left")
    
            sec2 = self._dlg_section(dlg, "TIMING & BEHAVIOUR", C["accent"])
    
            dur_var  = tk.StringVar(value=str(existing.duration))
            rand_var = tk.StringVar(value=str(existing.random_delay))
            rep_var  = tk.StringVar(value=str(existing.repeat_count))
            hold_var = tk.BooleanVar(value=existing.hold_mode)
            lane_var = tk.IntVar(value=existing.lane)
            rndK_var = tk.BooleanVar(value=existing.random_key)
            lbl_var  = tk.StringVar(value=existing.label or "")
    
            def entry(parent, var, w=8):
                return tk.Entry(parent, textvariable=var, width=w,
                    bg=C["bg"], fg=C["text"], insertbackground=C["accent"],
                    relief="flat", font=("Segoe UI", 9))
    
            self._dlg_field(sec2, "Duration (s)", lambda p: entry(p, dur_var), "how long to hold")
            self._dlg_field(sec2, "Random ± (s)", lambda p: entry(p, rand_var), "jitter added per press")
            self._dlg_field(sec2, "Repeat ×",    lambda p: entry(p, rep_var, 5), "times to press in a row")
            self._dlg_field(sec2, "Label",        lambda p: entry(p, lbl_var, 6))
    
            flags = tk.Frame(sec2, bg=C["bg_tertiary"]); flags.pack(fill="x", pady=(4,0))
            for text, var in [("Hold key down", hold_var), ("Lane 1 only", lane_var), ("Random key", rndK_var)]:
                tk.Checkbutton(flags, text=text, variable=var,
                    bg=C["bg_tertiary"], fg=C["text"], selectcolor=C["accent_glow"],
                    activebackground=C["bg_tertiary"], font=("Segoe UI", 9)).pack(side="left", padx=(0,10))
    
            def on_ok():
                try:
                    k = key_var.get().strip() or existing.key
                    dur = float(dur_var.get())
                    if dur <= 0: raise ValueError
                    self.history.push(self.engine.actions)
                    existing.key = k
                    existing.duration = dur
                    existing.random_delay = float(rand_var.get() or "0")
                    existing.hold_mode = hold_var.get()
                    existing.lane = lane_var.get()
                    existing.random_key = rndK_var.get()
                    existing.repeat_count = max(1, int(rep_var.get() or "1"))
                    existing.label = lbl_var.get()
                    self.refresh(); self.update_statistics(); self.save_session()
                    self.status(f"Updated key: {k}")
                    dlg.destroy()
                except ValueError:
                    messagebox.showerror("Invalid", "Duration must be a positive number.", parent=dlg)
    
            self._dlg_buttons(dlg, on_ok, dlg.destroy, ok_text="Save Changes")
            dlg.bind("<Return>", lambda e: on_ok())
            dlg.bind("<Escape>", lambda e: dlg.destroy())

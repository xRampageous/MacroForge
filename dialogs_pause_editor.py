import tkinter as tk
from tkinter import ttk, messagebox
from models import Action


class PauseEditorMixin:
        def open_pause_dialog(self):
            dlg, C = self._make_dialog("Add Delay", width=360)
            sec = self._dlg_section(dlg, "DELAY", C["pause_glow"] if C["pause_glow"] != "#2e2418" else C["warning"])
    
            dur_var = tk.StringVar(value="1.0")
            lbl_var = tk.StringVar(value="")
    
            def entry(parent, var, w=8):
                return tk.Entry(parent, textvariable=var, width=w,
                    bg=C["bg"], fg=C["text"], insertbackground=C["accent"],
                    relief="flat", font=("Segoe UI", 9))
    
            self._dlg_field(sec, "Duration (s)", lambda p: entry(p, dur_var), "seconds to wait")
            self._dlg_field(sec, "Label",        lambda p: entry(p, lbl_var, 6))
    
            def on_ok():
                try:
                    dur = float(dur_var.get())
                    if dur <= 0: raise ValueError
                    self.history.push(self.engine.actions)
                    act = Action("[DELAY]", dur, action_type="pause")
                    act.label = lbl_var.get()
                    self.engine.actions.append(act)
                    self.active_index = len(self.engine.actions) - 1
                    self.refresh(); self.update_statistics(); self.save_session()
                    self.timeline.ensure_visible(self.active_index)
                    self.status(f"Added delay: {dur}s")
                    dlg.destroy()
                except ValueError:
                    messagebox.showerror("Invalid", "Duration must be a positive number.", parent=dlg)
    
            self._dlg_buttons(dlg, on_ok, dlg.destroy, ok_text="Add Delay")
            dlg.bind("<Return>", lambda e: on_ok())
            dlg.bind("<Escape>", lambda e: dlg.destroy())
        def open_pause_editor(self, index: int):
            """Open dialog to edit an existing delay action."""
            if index < 0 or index >= len(self.engine.actions):
                return
            existing = self.engine.actions[index]
            dlg, C = self._make_dialog("Edit Delay", width=360)
            sec = self._dlg_section(dlg, "DELAY", C["pause_glow"] if C["pause_glow"] != "#2e2418" else C["warning"])
    
            dur_var = tk.StringVar(value=str(existing.duration))
            lbl_var = tk.StringVar(value=existing.label or "")
    
            def entry(parent, var, w=8):
                return tk.Entry(parent, textvariable=var, width=w,
                    bg=C["bg"], fg=C["text"], insertbackground=C["accent"],
                    relief="flat", font=("Segoe UI", 9))
    
            self._dlg_field(sec, "Duration (s)", lambda p: entry(p, dur_var), "seconds to wait")
            self._dlg_field(sec, "Label",        lambda p: entry(p, lbl_var, 6))
    
            def on_ok():
                try:
                    dur = float(dur_var.get())
                    if dur <= 0: raise ValueError
                    self.history.push(self.engine.actions)
                    existing.duration = dur
                    existing.label = lbl_var.get()
                    self.refresh(); self.update_statistics(); self.save_session()
                    self.status(f"Updated delay: {dur}s")
                    dlg.destroy()
                except ValueError:
                    messagebox.showerror("Invalid", "Duration must be a positive number.", parent=dlg)
    
            self._dlg_buttons(dlg, on_ok, dlg.destroy, ok_text="Save Changes")
            dlg.bind("<Return>", lambda e: on_ok())
            dlg.bind("<Escape>", lambda e: dlg.destroy())

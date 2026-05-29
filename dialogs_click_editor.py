import tkinter as tk
from tkinter import ttk, messagebox
import pyautogui

from models import Action


class ClickEditorMixin:
        def open_click_dialog(self):
            """Open dialog to add a new click action."""
            self._open_click_editor_impl(None)
        def open_click_editor(self, index):
            """Open dialog to edit an existing click action."""
            if index < 0 or index >= len(self.engine.actions):
                return
            self._open_click_editor_impl(index)
        def _open_click_editor_impl(self, index):
            existing = self.engine.actions[index] if index is not None else None
            is_edit  = existing is not None
            dlg, C   = self._make_dialog(
                "Edit Click Action" if is_edit else "Add Click Action", width=480, height=340)
    
            BLUE = "#60a5fa"
    
            # ── Event type & Coordinates combined ────────────────────────────────────
            sec = self._dlg_section(dlg, "CLICK SETTINGS", BLUE)
    
            # Event type
            btn_frame = tk.Frame(sec, bg=C["bg_tertiary"]); btn_frame.pack(fill="x", pady=(0,4))
            tk.Label(btn_frame, text="Button", bg=C["bg_tertiary"],
                     fg=C["text_dim"], font=("Segoe UI", 9), width=12, anchor="w").pack(side="left")
            btn_var = tk.StringVar(value=existing.click_button if existing else "left")
            ttk.Combobox(btn_frame, textvariable=btn_var, state="readonly", width=12,
                         values=["left", "right", "middle", "double"]).pack(side="left")
    
            # Coordinates with live tracking
            coord_frame = tk.Frame(sec, bg=C["bg_tertiary"]); coord_frame.pack(fill="x", pady=(0,4))
            tk.Label(coord_frame, text="Position", bg=C["bg_tertiary"],
                     fg=C["text_dim"], font=("Segoe UI", 9), width=12, anchor="w").pack(side="left")
    
            x_var = tk.StringVar(value=str(existing.click_x if existing else 0))
            y_var = tk.StringVar(value=str(existing.click_y if existing else 0))
            
            x_entry = tk.Entry(coord_frame, textvariable=x_var, width=8,
                bg=C["bg"], fg=C["text"], insertbackground=BLUE,
                relief="flat", font=("Segoe UI", 9))
            x_entry.pack(side="left", padx=(0,4))
            tk.Label(coord_frame, text=",", bg=C["bg_tertiary"],
                     fg=C["text_dim"], font=("Segoe UI", 9)).pack(side="left", padx=(0,4))
            y_entry = tk.Entry(coord_frame, textvariable=y_var, width=8,
                bg=C["bg"], fg=C["text"], insertbackground=BLUE,
                relief="flat", font=("Segoe UI", 9))
            y_entry.pack(side="left", padx=(0,8))
    
            # Live position label
            live_lbl = tk.Label(coord_frame, text="Live: --, --", bg=C["bg_tertiary"],
                               fg=BLUE, font=("Segoe UI", 8, "italic"))
            live_lbl.pack(side="left")
    
            # Coordinate mode with live tracking and disable logic
            mode_frame = tk.Frame(sec, bg=C["bg_tertiary"]); mode_frame.pack(fill="x", pady=(4,0))
            tk.Label(mode_frame, text="Mode", bg=C["bg_tertiary"],
                     fg=C["text_dim"], font=("Segoe UI", 9), width=12, anchor="w").pack(side="left")
            mode_var = tk.StringVar(value=existing.click_coord_mode if existing else "absolute")
            mode_combo = ttk.Combobox(mode_frame, textvariable=mode_var, state="readonly", width=18,
                         values=["absolute", "foreground", "offset", "position"])
            mode_combo.pack(side="left")
    
            def update_live_position():
                try:
                    mx, my = pyautogui.position()
                    live_lbl.config(text=f"Live: {mx}, {my}")
                except Exception:
                    live_lbl.config(text="Live: --, --")
    
            def on_mode_change(event):
                if mode_var.get() == "position":
                    x_entry.config(state="disabled", bg=C["bg_tertiary"])
                    y_entry.config(state="disabled", bg=C["bg_tertiary"])
                    x_var.set("0")
                    y_var.set("0")
                else:
                    x_entry.config(state="normal", bg=C["bg"])
                    y_entry.config(state="normal", bg=C["bg"])
            
            mode_combo.bind("<<ComboboxSelected>>", on_mode_change)
            
            # Handle existing "current" value by converting to "position"
            if existing and existing.click_coord_mode == "current":
                mode_var.set("position")
                on_mode_change(None)
            
            # Hotkey to capture position (F2)
            def capture_position():
                if mode_var.get() != "position":
                    try:
                        mx, my = pyautogui.position()
                        x_var.set(str(mx))
                        y_var.set(str(my))
                        live_lbl.config(text=f"✓ {mx}, {my}", fg="#20b87e")
                        self.root.after(1500, lambda: live_lbl.config(fg=BLUE))
                    except Exception:
                        pass
            
            # Bind F2 globally so it works even when dialog loses focus
            f2_binding = lambda e=None: capture_position()
            self.root.bind("<F2>", f2_binding)
    
            def _close_click_dlg():
                self.root.unbind("<F2>")
                dlg.destroy()
            
            # Live position update timer - start after dialog is fully visible
            def start_live_tracking():
                if dlg.winfo_exists():
                    update_live_position()
                    dlg.after(100, start_live_tracking)
            
            dlg.after(200, start_live_tracking)
    
            # ── Options ─────────────────────────────────────────────
            sec2 = self._dlg_section(dlg, "OPTIONS", BLUE)
    
            # Random radius
            rand_frame = tk.Frame(sec2, bg=C["bg_tertiary"]); rand_frame.pack(fill="x", pady=2)
            tk.Label(rand_frame, text="Random ±", bg=C["bg_tertiary"], fg=C["text_dim"],
                     font=("Segoe UI", 9), width=12, anchor="w").pack(side="left")
            rand_var = tk.StringVar(value=str(existing.click_rand_radius if existing else 0))
            tk.Entry(rand_frame, textvariable=rand_var, width=6,
                bg=C["bg"], fg=C["text"], insertbackground=BLUE,
                relief="flat", font=("Segoe UI", 9)).pack(side="left", padx=(0,4))
            tk.Label(rand_frame, text="px random offset", bg=C["bg_tertiary"],
                     fg=C["text_dim"], font=("Segoe UI", 8)).pack(side="left")
    
            # Label
            lbl_var = tk.StringVar(value=existing.label if existing else "")
            lbl_frame = tk.Frame(sec2, bg=C["bg_tertiary"]); lbl_frame.pack(fill="x", pady=2)
            tk.Label(lbl_frame, text="Label", bg=C["bg_tertiary"], fg=C["text_dim"],
                     font=("Segoe UI", 9), width=12, anchor="w").pack(side="left")
            tk.Entry(lbl_frame, textvariable=lbl_var, width=20,
                bg=C["bg"], fg=C["text"], insertbackground=BLUE,
                relief="flat", font=("Segoe UI", 9)).pack(side="left")
    
            # ── OK / Cancel ────────────────────────────────────────────
            def on_ok():
                try:
                    cx = int(x_var.get()); cy = int(y_var.get())
                    rr_val = max(0, int(rand_var.get() or "0"))
                except ValueError:
                    messagebox.showerror("Invalid", "Coordinates and radius must be integers.", parent=dlg)
                    return
    
                # Convert "position" back to "current" for compatibility
                coord_mode = mode_var.get()
                if coord_mode == "position":
                    coord_mode = "current"
    
                self.history.push(self.engine.actions)
                if is_edit:
                    act = self.engine.actions[index]
                    act.click_x = cx; act.click_y = cy
                    act.click_button = btn_var.get()
                    act.click_coord_mode = coord_mode
                    act.click_rand_radius = rr_val
                    act.label = lbl_var.get()
                    act.key = f"[CLICK:{btn_var.get()}]"
                else:
                    act = Action(
                        key=f"[CLICK:{btn_var.get()}]",
                        duration=0.0,
                        action_type="click",
                        click_x=cx, click_y=cy,
                        click_button=btn_var.get(),
                        click_coord_mode=coord_mode,
                        click_rand_radius=rr_val,
                        label=lbl_var.get(),
                    )
                    self.engine.actions.append(act)
                    self.active_index = len(self.engine.actions) - 1
                    self.timeline.ensure_visible(self.active_index)
    
                self.refresh(); self.update_statistics(); self.save_session()
                self.status(f"{'Updated' if is_edit else 'Added'} click at {cx},{cy}")
                _close_click_dlg()
    
            self._dlg_buttons(dlg, on_ok, _close_click_dlg,
                              ok_text="Save" if is_edit else "Add Click")
            dlg.bind("<Return>", lambda e: on_ok())
            dlg.bind("<Escape>", lambda e: _close_click_dlg())

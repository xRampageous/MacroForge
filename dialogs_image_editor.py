import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import base64
import io
import os
from PIL import Image, ImageTk
from models import Action


class ImageEditorMixin:
        def add_image(self):
            """Open image editor for a new action; only add to timeline if OK is pressed."""
            action = Action(
                key="[IMAGE]",
                duration=0.0,
                action_type="image",
                on_not_found="skip",
                on_found_action="continue",
            )
            self.open_image_editor_pending(action)
        def open_image_editor_pending(self, action: 'Action'):
            """Open the image editor for a brand-new action. Only adds to timeline on OK."""
            self.open_image_editor(-1, pending_action=action)
        def open_image_editor(self, index: int, pending_action=None):
            """Open the image-search editor dialog for the action at `index`."""
            _is_pending = pending_action is not None
            if _is_pending:
                action = pending_action
            else:
                if index < 0 or index >= len(self.engine.actions):
                    return
                action = self.engine.actions[index]
                if not action.is_image():
                    return
    
            C = self.config.colors
    
            # ── Dialog shell ─────────────────────────────────────
            dlg = tk.Toplevel(self.root)
            dlg.withdraw()
            dlg.title("Image Search Action")
            dlg.resizable(True, False)
            dlg.configure(bg=C["bg"])
            dlg.transient(self.root)
            dlg.minsize(620, 400)
            try:
                dlg.wm_iconbitmap("MacroForge.ico")
            except Exception:
                pass
            dlg.deiconify()
    
            _img_data  = [action.image_data]
            _photo_ref = [None]
    
            BG    = C["bg"]
            CARD  = C["bg_secondary"]
            FIELD = C["bg_tertiary"]
            ACC   = C["accent"]
            DIM   = C["text_dim"]
            TXT   = C["text"]
            BRD   = C["border"]
            PLAY  = C["playing"]
            ERR   = C["error"]
    
            # ── Widget helpers ────────────────────────────────────
            def _card(parent, title, color=None, pady=(8,8)):
                outer = tk.Frame(parent, bg=CARD)
                outer.pack(fill="x", padx=10, pady=(0,6))
                tk.Frame(outer, width=3, bg=color or ACC).pack(side="left", fill="y")
                inner = tk.Frame(outer, bg=CARD)
                inner.pack(side="left", fill="both", expand=True, padx=8, pady=pady)
                if title:
                    tk.Label(inner, text=title.upper(), bg=CARD, fg=color or ACC,
                             font=("Segoe UI", 7, "bold")).pack(anchor="w", pady=(0,5))
                return inner
    
            def _lbl(parent, text, dim=False, bold=False, color=None):
                fg = color or (DIM if dim else TXT)
                ft = ("Segoe UI", 9, "bold") if bold else ("Segoe UI", 9)
                return tk.Label(parent, text=text, bg=CARD, fg=fg, font=ft)
    
            def _entry(parent, var, width=10):
                return tk.Entry(parent, textvariable=var, width=width,
                    bg=FIELD, fg=TXT, insertbackground=ACC, relief="flat",
                    font=("Segoe UI", 9),
                    highlightthickness=1, highlightbackground=BRD, highlightcolor=ACC)
    
            def _spin(parent, var, frm=0, to=9999, w=6):
                return tk.Spinbox(parent, from_=frm, to=to, width=w,
                    textvariable=var, bg=FIELD, fg=TXT,
                    insertbackground=ACC, buttonbackground=FIELD,
                    relief="flat", font=("Segoe UI", 9))
    
            def _chkbtn(parent, text, var):
                return tk.Checkbutton(parent, text=text, variable=var,
                    bg=CARD, fg=TXT, selectcolor=C["accent_glow"],
                    activebackground=CARD, activeforeground=ACC,
                    font=("Segoe UI", 9))
    
            def _btn(parent, text, cmd, bg=None, fg=None, bold=False):
                _bg = bg or FIELD
                b = tk.Button(parent, text=text, command=cmd,
                    bg=_bg, fg=fg or TXT,
                    font=("Segoe UI", 9, "bold") if bold else ("Segoe UI", 9),
                    relief="flat", padx=10, pady=4, cursor="hand2")
                hv = C.get("hover", "#3a3a3a")
                b.bind("<Enter>", lambda e: b.config(bg=hv))
                b.bind("<Leave>", lambda e: b.config(bg=_bg))
                return b
    
            # ── Title bar ─────────────────────────────────────────
            title_bar = tk.Frame(dlg, bg=FIELD, pady=8)
            title_bar.pack(fill="x")
            tk.Label(title_bar, text="Image Search Action",
                bg=FIELD, fg=TXT, font=("Segoe UI", 11, "bold")).pack(side="left", padx=14)
            tk.Label(title_bar, text="Searches the screen for a template image and reacts",
                bg=FIELD, fg=DIM, font=("Segoe UI", 9)).pack(side="left")
            tk.Frame(dlg, height=1, bg=BRD).pack(fill="x")
    
            body = tk.Frame(dlg, bg=BG)
            body.pack(fill="both", expand=True, pady=6)
    
            # ══════════════════════════════════════════════════════
            # SECTION 1 — TEMPLATE IMAGE
            # ══════════════════════════════════════════════════════
            img_card = _card(body, "Template Image", color=PLAY)
    
            img_inner = tk.Frame(img_card, bg=CARD)
            img_inner.pack(fill="x")
    
            THUMB_W, THUMB_H = 180, 130
            thumb_outer = tk.Frame(img_inner, bg=FIELD, width=THUMB_W, height=THUMB_H,
                                   highlightthickness=2, highlightbackground=BRD)
            thumb_outer.pack_propagate(False)
            thumb_outer.pack(side="left", padx=(0, 14))
            thumb_canvas = tk.Canvas(thumb_outer, bg=FIELD, highlightthickness=0,
                                     width=THUMB_W, height=THUMB_H)
            thumb_canvas.pack(fill="both", expand=True)
    
            right_col = tk.Frame(img_inner, bg=CARD)
            right_col.pack(side="left", fill="both", expand=True)
    
            def refresh_thumb(data):
                thumb_canvas.delete("all")
                _photo_ref[0] = None
                if not data:
                    thumb_canvas.create_rectangle(0, 0, THUMB_W, THUMB_H, fill=FIELD, outline="")
                    thumb_canvas.create_text(THUMB_W//2, THUMB_H//2-10,
                        text="[IMG]", fill=DIM, font=("Segoe UI", 20))
                    thumb_canvas.create_text(THUMB_W//2, THUMB_H//2+18,
                        text="No image captured", fill=DIM, font=("Segoe UI", 8))
                    return
                # Defer thumbnail generation to avoid blocking UI
                def _gen_thumb():
                    try:
                        from PIL import Image as PILImage, ImageTk
                        import base64 as _b64, io as _io
                        raw = _b64.b64decode(data)
                        img = PILImage.open(_io.BytesIO(raw))
                        img.thumbnail((THUMB_W-4, THUMB_H-4), PILImage.LANCZOS)
                        ph = ImageTk.PhotoImage(img)
                        _photo_ref[0] = ph
                        thumb_canvas.create_image(THUMB_W//2, THUMB_H//2, anchor="center", image=ph)
                        thumb_canvas.create_rectangle(1, 1, THUMB_W-1, THUMB_H-1, outline=ACC, width=1)
                    except Exception as ex:
                        thumb_canvas.create_text(THUMB_W//2, THUMB_H//2,
                            text="Preview N/A\n" + str(ex), fill=ERR,
                            font=("Segoe UI", 8), justify="center")
                self.root.after(10, _gen_thumb)
    
            def do_capture():
                try: dlg.grab_release()
                except Exception: pass
                dlg.withdraw()
                self.root.withdraw()
                def _show_overlay():
                    ov = tk.Toplevel()
                    ov.attributes("-fullscreen", True)
                    ov.attributes("-alpha", 0.30)
                    ov.attributes("-topmost", True)
                    ov.configure(bg="black")
                    ov.overrideredirect(True)
                    cv = tk.Canvas(ov, cursor="cross", bg="black", highlightthickness=0)
                    cv.pack(fill="both", expand=True)
                    sw = ov.winfo_screenwidth(); sh = ov.winfo_screenheight()
                    cv.create_text(sw//2, sh//2-18,
                        text="Hold left mouse button and drag to select area",
                        fill="#ffffff", font=("Segoe UI", 13, "bold"))
                    cv.create_text(sw//2, sh//2+12, text="Press Esc to cancel",
                        fill="#aaaaaa", font=("Segoe UI", 10))
                    st = {"x0":0,"y0":0,"rect":None,"hint":True}
                    def op(e):
                        st["x0"],st["y0"] = e.x,e.y
                        if st["rect"]: cv.delete(st["rect"])
                        if st["hint"]: cv.delete("all"); st["hint"]=False
                    def od(e):
                        if st["rect"]: cv.delete(st["rect"])
                        st["rect"] = cv.create_rectangle(st["x0"],st["y0"],e.x,e.y,
                            outline=C["accent"],width=2,fill=C["accent"],stipple="gray25")
                        w=abs(e.x-st["x0"]); h=abs(e.y-st["y0"])
                        cv.delete("sizelbl")
                        cv.create_text(e.x+6,e.y+12, text=f"{w}×{h}",
                            fill="#ffffff",font=("Segoe UI",9),anchor="nw",tags="sizelbl")
                    def _finish(x0,y0,x1,y1,cancelled=False):
                        ov.destroy()
                        if cancelled or x1-x0<4 or y1-y0<4:
                            self.root.deiconify(); dlg.deiconify(); dlg.lift(); dlg.grab_set()
                            if not cancelled: self.status("Capture cancelled — area too small")
                            return
                        # Grab immediately without delay
                        _do_grab(x0,y0,x1,y1)
                    def _do_grab(x0,y0,x1,y1):
                        try:
                            import base64 as _b64, io as _io
                            from PIL import ImageGrab
                            # all_screens=True ensures physical-pixel coords match
                            # what pyautogui.locateOnScreen uses on high-DPI displays
                            try:
                                shot = ImageGrab.grab(bbox=(x0,y0,x1,y1), all_screens=True)
                            except TypeError:
                                shot = ImageGrab.grab(bbox=(x0,y0,x1,y1))
                            buf = _io.BytesIO()
                            shot.save(buf, format="PNG")
                            _img_data[0] = _b64.b64encode(buf.getvalue()).decode()
                            refresh_thumb(_img_data[0])
                            size_lbl.config(text=f"✓ Captured {shot.width}×{shot.height}px — click OK to save")
                            self.status(f"Template captured: {shot.width}×{shot.height}px")
                        except Exception as ex:
                            self.status(f"Capture failed: {ex}")
                        finally:
                            self.root.deiconify(); dlg.deiconify(); dlg.lift(); dlg.grab_set()
                    def ore(e):
                        x0=min(st["x0"],e.x); y0=min(st["y0"],e.y)
                        x1=max(st["x0"],e.x); y1=max(st["y0"],e.y)
                        _finish(x0,y0,x1,y1)
                    def oesc(e): _finish(0,0,0,0,cancelled=True)
                    cv.bind("<ButtonPress-1>",op); cv.bind("<B1-Motion>",od)
                    cv.bind("<ButtonRelease-1>",ore); ov.bind("<Escape>",oesc)
                    ov.grab_set(); ov.focus_force()
                def _safe_show():
                    try: _show_overlay()
                    except Exception as ex:
                        self.root.deiconify()
                        try: dlg.deiconify(); dlg.lift(); dlg.grab_set()
                        except Exception: pass
                        self.status(f"Could not open overlay: {ex}")
                self.root.after(200, _safe_show)
    
            cap_btn = _btn(right_col, "Capture Screen Region", do_capture,
                           bg=PLAY, fg="black", bold=True)
            cap_btn.pack(anchor="w", pady=(0, 6))
            _lbl(right_col, "Click Capture, then drag to select a region on screen.", dim=True).pack(anchor="w")
            size_lbl = tk.Label(right_col, text="", bg=CARD, fg=ACC, font=("Segoe UI", 8))
            size_lbl.pack(anchor="w", pady=(2, 0))
            _lbl(right_col, "⚠  Recommended: 50×50px or less for best performance.", dim=True).pack(anchor="w", pady=(4,0))
    
            refresh_thumb(action.image_data)
    
            # ── Extra / OR templates ──────────────────────────────
            extra_card = _card(body, "Additional Templates  (OR match — any triggers)", color="#a78bfa")
    
            extra_frame = tk.Frame(extra_card, bg=FIELD)
            extra_frame.pack(fill="x", pady=(0,4))
    
            _extra_list   = [x for x in action.extra_images.split("|") if x]
            _extra_photos = []
    
            def _rebuild_extra_ui():
                for w in extra_frame.winfo_children(): w.destroy()
                new_photos = []
                for i, b64 in enumerate(_extra_list):
                    erow = tk.Frame(extra_frame, bg=FIELD)
                    erow.pack(fill="x", padx=6, pady=2)
                    try:
                        import base64 as _b64, io as _io
                        from PIL import Image as PILImage, ImageTk
                        raw = _b64.b64decode(b64)
                        img = PILImage.open(_io.BytesIO(raw))
                        img.thumbnail((56, 40), PILImage.LANCZOS)
                        ph = ImageTk.PhotoImage(img)
                        new_photos.append(ph)
                        lw = tk.Label(erow, image=ph, bg=FIELD); lw.image=ph; lw.pack(side="left",padx=(0,8))
                    except Exception:
                        tk.Label(erow, text="[err]", bg=FIELD, fg=ERR, font=("Segoe UI",8)).pack(side="left",padx=(0,8))
                    tk.Label(erow, text=f"Template {i+2}", bg=FIELD, fg=DIM, font=("Segoe UI",9)).pack(side="left")
                    _btn(erow, "  ✕ Remove  ", lambda ix=i: _remove_extra(ix), bg=ERR, fg="white").pack(side="right",padx=4)
                _extra_photos.clear(); _extra_photos.extend(new_photos)
                if not _extra_list:
                    tk.Label(extra_frame, text="No extra templates added",
                        bg=FIELD, fg=DIM, font=("Segoe UI",9,"italic")).pack(padx=10,pady=8)
    
            def _remove_extra(i):
                _extra_list.pop(i); _rebuild_extra_ui()
    
            def _capture_extra():
                def _after_capture(b64): _extra_list.append(b64); _rebuild_extra_ui()
                def _restore():
                    self.root.deiconify()
                    try: dlg.deiconify(); dlg.lift(); dlg.grab_set()
                    except Exception: pass
                try: dlg.grab_release()
                except Exception: pass
                dlg.withdraw(); self.root.withdraw()
                self.root.update_idletasks(); self.root.update()
                def _show_extra_overlay():
                    try:
                        ov = tk.Toplevel()
                        ov.attributes("-fullscreen",True); ov.attributes("-alpha",0.30)
                        ov.attributes("-topmost",True); ov.configure(bg="black"); ov.overrideredirect(True)
                        ecv = tk.Canvas(ov, cursor="cross", bg="black", highlightthickness=0)
                        ecv.pack(fill="both", expand=True)
                        sw,sh = ov.winfo_screenwidth(),ov.winfo_screenheight()
                        ecv.create_text(sw//2,sh//2-18, text="Capture extra template — drag to select",
                            fill="#ffffff",font=("Segoe UI",13,"bold"))
                        ecv.create_text(sw//2,sh//2+12, text="Esc to cancel",fill="#aaaaaa",font=("Segoe UI",10))
                        st={"x0":0,"y0":0,"rect":None,"hint":True}
                        def op(e):
                            st["x0"],st["y0"]=e.x,e.y
                            if st["rect"]: ecv.delete(st["rect"])
                            if st["hint"]: ecv.delete("all"); st["hint"]=False
                        def od(e):
                            if st["rect"]: ecv.delete(st["rect"])
                            st["rect"]=ecv.create_rectangle(st["x0"],st["y0"],e.x,e.y,
                                outline=C["accent"],width=2,fill=C["accent"],stipple="gray25")
                            w=abs(e.x-st["x0"]); h=abs(e.y-st["y0"])
                            ecv.delete("sizelbl")
                            ecv.create_text(e.x+6,e.y+12, text=f"{w}×{h}",
                                fill="#ffffff",font=("Segoe UI",9),anchor="nw",tags="sizelbl")
                        def ore(e):
                            x0=min(st["x0"],e.x); y0=min(st["y0"],e.y)
                            x1=max(st["x0"],e.x); y1=max(st["y0"],e.y)
                            ov.destroy()
                            if x1-x0<4 or y1-y0<4: _restore(); return
                            def _grab():
                                try:
                                    import base64 as _b64, io as _io
                                    from PIL import ImageGrab
                                    try:
                                        shot=ImageGrab.grab(bbox=(x0,y0,x1,y1),all_screens=True)
                                    except TypeError:
                                        shot=ImageGrab.grab(bbox=(x0,y0,x1,y1))
                                    buf=_io.BytesIO(); shot.save(buf,format="PNG")
                                    _after_capture(_b64.b64encode(buf.getvalue()).decode())
                                    self.status(f"Extra template: {shot.width}×{shot.height}px")
                                except Exception as ex:
                                    self.status(f"Extra capture failed: {ex}")
                                finally:
                                    _restore()
                            self.root.after(400,_grab)
                        def oesc(e): ov.destroy(); _restore()
                        ecv.bind("<ButtonPress-1>",op); ecv.bind("<B1-Motion>",od)
                        ecv.bind("<ButtonRelease-1>",ore); ov.bind("<Escape>",oesc)
                        ov.grab_set(); ov.focus_force()
                    except Exception as ex:
                        _restore(); self.status(f"Could not open overlay: {ex}")
                self.root.after(200,_show_extra_overlay)
    
            _rebuild_extra_ui()
            _btn(extra_card, "+ Add Extra Template", _capture_extra, bg="#a78bfa", fg="black", bold=True).pack(anchor="w",pady=(4,0))
    
            # ══════════════════════════════════════════════════════
            # SECTION 2 — Two-column: MATCH SETTINGS | BEHAVIOUR
            # ══════════════════════════════════════════════════════
            cols_frame = tk.Frame(body, bg=BG)
            cols_frame.pack(fill="x", padx=10, pady=(0,6))
            cols_frame.columnconfigure(0, weight=1)
            cols_frame.columnconfigure(1, weight=1)
    
            # ── LEFT: Match Settings ──────────────────────────────
            lco = tk.Frame(cols_frame, bg=CARD)
            lco.grid(row=0, column=0, sticky="nsew", padx=(0,4))
            tk.Frame(lco, width=3, bg="#f59e0b").pack(side="left", fill="y")
            lci = tk.Frame(lco, bg=CARD)
            lci.pack(side="left", fill="both", expand=True, padx=8, pady=8)
            tk.Label(lci, text="MATCH SETTINGS", bg=CARD, fg="#f59e0b",
                     font=("Segoe UI",7,"bold")).pack(anchor="w", pady=(0,5))
    
            # Similarity
            sim_pct_default = int(round((1.0 - action.similarity) * 100))
            # For brand-new actions similarity==0.95 → 5; guard against float precision
            if sim_pct_default <= 0 and action.similarity >= 0.94:
                sim_pct_default = 5
            sim_var = tk.StringVar(value=str(sim_pct_default))
            sr = tk.Frame(lci, bg=CARD); sr.pack(fill="x", pady=2)
            _lbl(sr, "Similarity:", bold=True).pack(side="left", padx=(0,6))
            _spin(sr, sim_var, 0, 100, 5).pack(side="left")
            _lbl(lci, "5 = recommended  (0 = pixel-perfect / never matches)", dim=True).pack(anchor="w", pady=(0,4))
    
            tk.Frame(lci, height=1, bg=BRD).pack(fill="x", pady=5)
    
            # Search region
            _lbl(lci, "Search Region:", bold=True).pack(anchor="w", pady=(0,4))
            if action.search_region == "foreground":
                _rmode_init = "foreground"
            elif action.search_region and "," in action.search_region:
                _rmode_init = "region"
            else:
                _rmode_init = "whole"
            region_mode = tk.StringVar(value=_rmode_init)
    
            def _radio(text, val, parent):
                return tk.Radiobutton(parent, text=text, variable=region_mode, value=val,
                    bg=CARD, fg=TXT, selectcolor=C["accent_glow"],
                    activebackground=CARD, activeforeground=ACC, font=("Segoe UI",9))
    
            _radio("Whole screen",           "whole",      lci).pack(anchor="w", padx=4, pady=1)
            _radio("Foreground window only", "foreground", lci).pack(anchor="w", padx=4, pady=1)
            _radio("Specific region:",       "region",     lci).pack(anchor="w", padx=4, pady=1)
    
            _parts = action.search_region.split(",") if action.search_region else ["0","0","0","0"]
            _parts += ["0"] * (4 - len(_parts))
            left_v = tk.StringVar(value=_parts[0])
            top_v  = tk.StringVar(value=_parts[1])
            wid_v  = tk.StringVar(value=_parts[2])
            hei_v  = tk.StringVar(value=_parts[3])
    
            reg_fields = tk.Frame(lci, bg=CARD)
            reg_fields.pack(anchor="w", padx=16, pady=(2,0))
            _reg_widgets = []
            for lt, var in [("L:", left_v),("T:", top_v),("W:", wid_v),("H:", hei_v)]:
                l = _lbl(reg_fields, lt, dim=True); l.pack(side="left", padx=(0,1))
                s = _spin(reg_fields, var, 0, 9999, 5); s.pack(side="left", padx=(0,4))
                _reg_widgets += [l, s]
    
            def capture_region():
                try: dlg.grab_release()
                except Exception: pass
                dlg.withdraw(); self.root.withdraw()
                self.root.update_idletasks(); self.root.update()
                def _show_region_overlay():
                    ov = tk.Toplevel()
                    ov.attributes("-fullscreen",True); ov.attributes("-alpha",0.25)
                    ov.attributes("-topmost",True); ov.configure(bg="black"); ov.overrideredirect(True)
                    cv = tk.Canvas(ov, cursor="cross", bg="black", highlightthickness=0)
                    cv.pack(fill="both", expand=True)
                    sw=ov.winfo_screenwidth(); sh=ov.winfo_screenheight()
                    cv.create_text(sw//2,sh//2-18, text="Drag to select search region",
                        fill="#ffffff",font=("Segoe UI",13,"bold"))
                    cv.create_text(sw//2,sh//2+12, text="Esc to cancel",fill="#aaaaaa",font=("Segoe UI",10))
                    st={"x0":0,"y0":0,"rect":None,"hint":True}
                    def op(e):
                        st["x0"],st["y0"]=e.x,e.y
                        if st["rect"]: cv.delete(st["rect"])
                        if st["hint"]: cv.delete("all"); st["hint"]=False
                    def od(e):
                        if st["rect"]: cv.delete(st["rect"])
                        st["rect"]=cv.create_rectangle(st["x0"],st["y0"],e.x,e.y,
                            outline=C["accent"],width=2,fill=C["accent"],stipple="gray25")
                        w=abs(e.x-st["x0"]); h=abs(e.y-st["y0"])
                        cv.delete("sizelbl")
                        cv.create_text(e.x+6,e.y+12,
                            text=f"{w}×{h}  ({min(st['x0'],e.x)},{min(st['y0'],e.y)})",
                            fill="#ffffff",font=("Segoe UI",9),anchor="nw",tags="sizelbl")
                    def ore(e):
                        x0=min(st["x0"],e.x); y0=min(st["y0"],e.y)
                        x1=max(st["x0"],e.x); y1=max(st["y0"],e.y)
                        ov.destroy(); self.root.deiconify()
                        dlg.deiconify(); dlg.lift(); dlg.grab_set()
                        if x1-x0<4 or y1-y0<4: return
                        left_v.set(str(x0)); top_v.set(str(y0))
                        wid_v.set(str(x1-x0)); hei_v.set(str(y1-y0))
                        region_mode.set("region")
                    def oesc(e):
                        ov.destroy(); self.root.deiconify()
                        dlg.deiconify(); dlg.lift(); dlg.grab_set()
                    cv.bind("<ButtonPress-1>",op); cv.bind("<B1-Motion>",od)
                    cv.bind("<ButtonRelease-1>",ore); ov.bind("<Escape>",oesc)
                    ov.grab_set(); ov.focus_force()
                self.root.after(200, _show_region_overlay)
    
            rcap = _btn(reg_fields, "⦿ Capture", capture_region)
            rcap.pack(side="left", padx=(4,0))
            _reg_widgets.append(rcap)
    
            def update_region_fields(*_):
                state = "normal" if region_mode.get() == "region" else "disabled"
                for w in _reg_widgets:
                    try: w.config(state=state)
                    except Exception: pass
    
            region_mode.trace_add("write", update_region_fields)
            update_region_fields()
    
            # ── RIGHT: Behaviour ──────────────────────────────────
            rco = tk.Frame(cols_frame, bg=CARD)
            rco.grid(row=0, column=1, sticky="nsew", padx=(4,0))
            tk.Frame(rco, width=3, bg=ACC).pack(side="left", fill="y")
            rci = tk.Frame(rco, bg=CARD)
            rci.pack(side="left", fill="both", expand=True, padx=8, pady=8)
            tk.Label(rci, text="BEHAVIOUR", bg=CARD, fg=ACC,
                     font=("Segoe UI",7,"bold")).pack(anchor="w", pady=(0,5))
    
            found_var     = tk.StringVar(value=action.on_found_action if action.on_found_action in ["continue","click","double_click","press_key"] else "continue")
            not_found_var = tk.StringVar(value=action.on_not_found)
            found_key_var = tk.StringVar(value=action.on_found_key)
    
            _combo_style = ttk.Style()
            _combo_style.map("Found.TCombobox",
                fieldbackground=[("readonly", FIELD)],
                foreground=[("readonly", TXT)],
                selectbackground=[("readonly", FIELD)],
                selectforeground=[("readonly", TXT)],
            )
    
            for label_text, var, vals in [
                ("When found:",     found_var,     ["continue","click","double_click","press_key"]),
                ("When not found:", not_found_var, ["skip","stop","warn"]),
            ]:
                r = tk.Frame(rci, bg=CARD); r.pack(fill="x", pady=2)
                _lbl(r, label_text).pack(side="left", padx=(0,6))
                ttk.Combobox(r, textvariable=var, values=vals,
                    state="readonly", width=14, style="Found.TCombobox").pack(side="left")
    
            # Key to press
            fk_row = tk.Frame(rci, bg=CARD); fk_row.pack(fill="x", pady=(4,2))
            fk_label = _lbl(fk_row, "  Key to press:", dim=True); fk_label.pack(side="left", padx=(0,4))
            fk_entry = tk.Entry(fk_row, textvariable=found_key_var, width=10,
                bg=FIELD, fg=TXT, insertbackground=ACC, relief="flat",
                font=("Segoe UI",9), highlightthickness=1,
                highlightbackground=BRD, highlightcolor=ACC)
            fk_entry.pack(side="left", padx=(0,2))
            fk_clear = _btn(fk_row, "✕", lambda: found_key_var.set(""))
            fk_clear.pack(side="left", padx=(0,4))
            fk_hint = tk.Label(fk_row, text="click then press key",
                bg=CARD, fg=DIM, font=("Segoe UI",7,"italic"))
            fk_hint.pack(side="left")
    
            _fk_listening = [False]
    
            def _fk_set_state(enabled):
                st = "normal" if enabled else "disabled"
                dim = DIM if enabled else BRD
                fk_entry.config(state=st); fk_clear.config(state=st)
                fk_label.config(fg=dim); fk_hint.config(fg=dim if enabled else BRD)
    
            def _fk_on_found_changed(*_):
                _fk_set_state(found_var.get() == "press_key")
    
            found_var.trace_add("write", _fk_on_found_changed)
            _fk_set_state(found_var.get() == "press_key")
    
            def _fk_on_focus_in(e):
                if found_var.get() != "press_key": return
                _fk_listening[0] = True
                fk_entry.config(highlightbackground=ACC)
                fk_hint.config(text="press a key...")
    
            def _fk_on_focus_out(e):
                _fk_listening[0] = False
                fk_entry.config(highlightbackground=BRD)
                fk_hint.config(text="click then press key")
    
            def _fk_on_keypress(e):
                if not _fk_listening[0]: return
                sym = e.keysym.lower()
                _map = {
                    "return":"enter","prior":"pageup","next":"pagedown",
                    "numpad_0":"numpad0","numpad_1":"numpad1","numpad_2":"numpad2",
                    "numpad_3":"numpad3","numpad_4":"numpad4","numpad_5":"numpad5",
                    "numpad_6":"numpad6","numpad_7":"numpad7","numpad_8":"numpad8",
                    "numpad_9":"numpad9",
                }
                found_key_var.set(_map.get(sym, sym))
                fk_entry.config(highlightbackground=BRD)
                fk_hint.config(text="click then press key")
                _fk_listening[0] = False; dlg.focus_set()
                return "break"
    
            fk_entry.bind("<FocusIn>",  _fk_on_focus_in)
            fk_entry.bind("<FocusOut>", _fk_on_focus_out)
            fk_entry.bind("<KeyPress>", _fk_on_keypress)
    
            tk.Frame(rci, height=1, bg=BRD).pack(fill="x", pady=5)
    
            wait_var = tk.StringVar(value=str(int(action.wait_timeout)))
            wt = tk.Frame(rci, bg=CARD); wt.pack(fill="x", pady=2)
            _lbl(wt, "Wait timeout:").pack(side="left", padx=(0,6))
            _spin(wt, wait_var, 0, 60, 5).pack(side="left", padx=(0,4))
            _lbl(wt, "s  (0=single shot)", dim=True).pack(side="left")
    
            tk.Frame(rci, height=1, bg=BRD).pack(fill="x", pady=5)
    
            off_x_var = tk.StringVar(value=str(action.click_offset_x))
            off_y_var = tk.StringVar(value=str(action.click_offset_y))
            ofr = tk.Frame(rci, bg=CARD); ofr.pack(fill="x", pady=2)
            _lbl(ofr, "Click offset:").pack(side="left", padx=(0,6))
            _lbl(ofr, "X:", dim=True).pack(side="left", padx=(0,2))
            _spin(ofr, off_x_var, -500, 500, 5).pack(side="left", padx=(0,6))
            _lbl(ofr, "Y:", dim=True).pack(side="left", padx=(0,2))
            _spin(ofr, off_y_var, -500, 500, 5).pack(side="left", padx=(0,4))
            _lbl(ofr, "px", dim=True).pack(side="left")
    
            tk.Frame(rci, height=1, bg=BRD).pack(fill="x", pady=5)
    
            rand_click_var = tk.BooleanVar(value=action.random_click)
            loop_until_var = tk.BooleanVar(value=action.loop_until_found)
            pos_mouse_var  = tk.BooleanVar(value=action.position_mouse)
    
            _chkbtn(rci, "Position mouse on match",   pos_mouse_var).pack(anchor="w", pady=1)
            _chkbtn(rci, "Random click within match",  rand_click_var).pack(anchor="w", pady=1)
            _chkbtn(rci, "Loop sequence until found",  loop_until_var).pack(anchor="w", pady=1)
    
            # ══════════════════════════════════════════════════════
            # SECTION 3 — Label / Repeat / Jump
            # ══════════════════════════════════════════════════════
            meta_card = _card(body, "Label, Repeat & Conditional Jump", color="#94a3b8")
            mi = tk.Frame(meta_card, bg=CARD); mi.pack(fill="x")
    
            n_actions = len(self.engine.actions)
            img_label_var         = tk.StringVar(value=getattr(action, "label", ""))
            img_repeat_var        = tk.StringVar(value=str(getattr(action, "repeat_count", 1)))
            _jf_init  = str(getattr(action,"jump_to_on_found",-1)+1) if getattr(action,"jump_to_on_found",-1)>=0 else "0"
            _jnf_init = str(getattr(action,"jump_to_on_not_found",-1)+1) if getattr(action,"jump_to_on_not_found",-1)>=0 else "0"
            img_jump_found_var    = tk.StringVar(value=_jf_init)
            img_jump_notfound_var = tk.StringVar(value=_jnf_init)
    
            for col_label, col_var, col_w in [
                ("Label",              img_label_var,        6),
                ("× Repeat",      img_repeat_var,        4),
                ("Jump if found →",       img_jump_found_var,    4),
                ("Jump if NOT found →",   img_jump_notfound_var, 4),
            ]:
                col = tk.Frame(mi, bg=CARD); col.pack(side="left", padx=(0,16))
                _lbl(col, col_label, dim=True).pack(anchor="w")
                _entry(col, col_var, col_w).pack(anchor="w", pady=(2,0))
    
            tk.Label(meta_card, text=f"Jump: action number 1–{n_actions}, enter 0 for no jump",
                bg=CARD, fg=DIM, font=("Segoe UI",7,"italic")).pack(anchor="w", pady=(6,0))
    
            # ══════════════════════════════════════════════════════
            # FOOTER
            # ══════════════════════════════════════════════════════
            tk.Frame(dlg, height=1, bg=BRD).pack(fill="x")
            footer = tk.Frame(dlg, bg=FIELD, pady=8)
            footer.pack(fill="x")
    
            def on_ok():
                self.history.push(self.engine.actions)
                action.image_data = _img_data[0]
                try:
                    sim_pct = max(0, min(100, int(float(sim_var.get() or "0"))))
                except ValueError:
                    sim_pct = 0
                action.similarity      = round(1.0 - sim_pct / 100.0, 4)
                _rmode = region_mode.get()
                if _rmode == "region":
                    action.search_region = f"{left_v.get()},{top_v.get()},{wid_v.get()},{hei_v.get()}"
                elif _rmode == "foreground":
                    action.search_region = "foreground"
                else:
                    action.search_region = ""
                action.on_found_action = found_var.get()
                action.position_mouse  = pos_mouse_var.get()
                action.on_found_key    = found_key_var.get().strip()
                action.on_not_found    = not_found_var.get()
                try:
                    action.wait_timeout = max(0.0, float(wait_var.get() or "0"))
                except ValueError:
                    action.wait_timeout = 0.0
                try:
                    action.click_offset_x = int(off_x_var.get() or "0")
                    action.click_offset_y = int(off_y_var.get() or "0")
                except ValueError:
                    action.click_offset_x = 0
                    action.click_offset_y = 0
                action.random_click     = rand_click_var.get()
                action.loop_until_found = loop_until_var.get()
                action.extra_images     = "|".join(_extra_list)
                action.label = img_label_var.get().strip()
                try:
                    action.repeat_count = max(1, int(img_repeat_var.get() or 1))
                except ValueError:
                    action.repeat_count = 1
                try:
                    jf = int(img_jump_found_var.get() or 0)
                    action.jump_to_on_found = jf - 1 if jf > 0 else -1
                except ValueError:
                    action.jump_to_on_found = -1
                try:
                    jnf = int(img_jump_notfound_var.get() or 0)
                    action.jump_to_on_not_found = jnf - 1 if jnf > 0 else -1
                except ValueError:
                    action.jump_to_on_not_found = -1
                if _is_pending:
                    self.engine.actions.append(action)
                    self.active_index = len(self.engine.actions) - 1
                    self.timeline.ensure_visible(self.active_index)
                self.refresh()
                self.save_session()
                self.status("Image action added" if _is_pending else "Image action updated")
                dlg.destroy()
    
            def on_cancel():
                dlg.destroy()
                if _is_pending:
                    self.status("Image action cancelled")
    
            tk.Label(footer, text="Changes are saved when you click OK",
                bg=FIELD, fg=DIM, font=("Segoe UI",8,"italic")).pack(side="left", padx=14)
    
            ok_btn = self._btn(footer, "Save & Close", on_ok, C["accent"], fg="black", bold=True, icon="check")
            ok_btn.pack(side="right", padx=(4,14))
    
            cancel_btn = self._btn(footer, "Cancel", on_cancel, C["bg_tertiary"], icon="cross")
            cancel_btn.pack(side="right", padx=(0,4))
    
            dlg.bind("<Return>", lambda e: on_ok())
            dlg.bind("<Escape>", lambda e: on_cancel())
    
            # Centre over parent then grab
            dlg.update_idletasks()
            pw = self.root.winfo_x() + self.root.winfo_width()  // 2
            ph = self.root.winfo_y() + self.root.winfo_height() // 2
            dw = dlg.winfo_width()
            dh = dlg.winfo_height()
            dlg.geometry(f"+{pw - dw//2}+{ph - dh//2}")
            dlg.grab_set()

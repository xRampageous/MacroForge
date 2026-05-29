import tkinter as tk
import math
import time
import threading
import io
import base64
from collections import deque

from PIL import Image, ImageTk
from Icons import CanvasIcons
from debugger import logger


def _lerp_color(c1, c2, t):
    t = max(0.0, min(1.0, t))
    r1, g1, b1 = int(c1[1:3], 16), int(c1[3:5], 16), int(c1[5:7], 16)
    r2, g2, b2 = int(c2[1:3], 16), int(c2[3:5], 16), int(c2[5:7], 16)
    return f"#{int(r1+(r2-r1)*t):02x}{int(g1+(g2-g1)*t):02x}{int(b1+(b2-b1)*t):02x}"


def _glow_color(color, intensity=0.5):
    r = int(color[1:3], 16)
    g = int(color[3:5], 16)
    b = int(color[5:7], 16)

    r = min(255, int(r + (255 - r) * intensity))
    g = min(255, int(g + (255 - g) * intensity))
    b = min(255, int(b + (255 - b) * intensity))

    return f"#{r:02x}{g:02x}{b:02x}"


class CanvasTimeline(tk.Frame):

    BUFFER_ROWS = 12
    TARGET_FPS = 60
    FRAME_TIME = 1 / TARGET_FPS

    ROW_H = 34
    HEADER_H = 26

    SCROLL_DECAY = 0.90
    MAX_VELOCITY = 3000

    ENABLE_SMOOTH_SCROLL = True
    ENABLE_ANIMATIONS = True
    ENABLE_GLOW = True

    def __init__(self, parent, app, config):
        super().__init__(parent, bg=config.colors["bg"])

        self.app = app
        self.config = config

        self.scroll_offset = 0.0
        self.scroll_velocity = 0.0

        self.zoom = 1.0

        self.active_index = -1
        self.playing_index = -1
        self.hover_index = -1
        self.selected_indices = set()  # Multi-select: set of selected indices

        self._action_start = 0.0
        self._action_dur = 0.0
        self._paused = False
        self._paused_at = 0.0
        self._pause_offset = 0.0

        self.dragging = False
        self.drag_index = -1
        self.drag_target = -1
        self.drag_start_y = 0

        self._ghost_bg = None
        self._ghost_text = None
        self._drop_line = None

        self._running = True
        self._last_frame = time.perf_counter()

        self.anim_time = 0.0

        self.visible_pool = []
        self.pool_size = 0

        self._dirty_all = True
        self._dirty_rows = set()

        self._visible_first = -1
        self._visible_last = -1

        self._thumb_cache = {}
        self._geometry_cache = {}

        self._last_width = 0
        self._last_height = 0

        self._fps_counter = 0
        self._fps_timer = time.perf_counter()
        self._current_fps = 0

        self._render_lock = False
        self._last_action_count = 0

        self.setup_ui()

        self.after(50, self.initialize_pool)
        self.after(16, self.frame_loop)

    # =====================================================
    # UI
    # =====================================================

    def setup_ui(self):

        self.scrollbar = tk.Scrollbar(
            self,
            orient="vertical",
            command=self.scrollbar_scroll,
            bg=self.config.colors["bg"],
            troughcolor=self.config.colors["bg"],
            activebackground=self.config.colors["bg"],
            relief="flat",
            width=0,
            bd=0,
            highlightthickness=0
        )

        self.scrollbar.pack(side="right", fill="y")

        self.canvas = tk.Canvas(
            self,
            bg=self.config.colors["bg"],
            highlightthickness=0
        )

        self.canvas.pack(side="left", fill="both", expand=True)

        self.canvas.bind("<Configure>", self.on_resize)
        self.canvas.bind("<MouseWheel>", self.on_scroll)
        self.canvas.bind("<Button-4>", self.on_scroll)
        self.canvas.bind("<Button-5>", self.on_scroll)
        self.canvas.bind("<Motion>", self.on_mouse_move)
        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<Double-Button-1>", self.on_double_click)
        self.canvas.bind("<B1-Motion>", self.on_drag_move)
        self.canvas.bind("<ButtonRelease-1>", self.on_drag_end)
        self.canvas.bind("<Button-3>", self.on_right_click)
        self.canvas.bind("<Control-MouseWheel>", self.on_zoom)

        self.canvas.focus_set()

    # =====================================================
    # POOL
    # =====================================================

    def initialize_pool(self):

        if self.pool_size:
            for row in self.visible_pool:
                for item in row["items"]:
                    self.canvas.delete(item)
                for item in row.get("icon_items", ()):
                    self.canvas.delete(item)
                if row.get("img_item"):
                    self.canvas.delete(row["img_item"])

        self.visible_pool.clear()

        h = max(self.canvas.winfo_height(), 300)

        row_h = self.scaled_row_height()

        self.pool_size = int(h / row_h) + self.BUFFER_ROWS

        for i in range(self.pool_size):
            self.visible_pool.append(self.create_row())

        self.create_header()

        self._dirty_all = True

    def _get_cols(self, w):
        """Return proportional column positions scaled to canvas width w."""
        idx   = max(8,  int(w * 0.03))
        key   = max(40, int(w * 0.12))
        bar_w = max(80, int(w * 0.22))
        bar_s = int((w - bar_w) / 2)  # horizontally centered
        lane  = max(280, int(w * 0.72))
        flags = max(360, int(w * 0.88))
        return idx, key, bar_s, bar_w, lane, flags

    def create_header(self):

        if hasattr(self, "_header_bg"):
            self.canvas.delete(self._header_bg)

        if hasattr(self, "_header_line"):
            self.canvas.delete(self._header_line)

        self._header_labels = []

        w = self.canvas.winfo_width()

        C = self.config.colors

        self._header_bg = self.canvas.create_rectangle(
            0,
            0,
            w,
            self.HEADER_H,
            fill=C["bg_secondary"],
            outline=""
        )

        self._header_line = self.canvas.create_line(
            0,
            self.HEADER_H,
            w,
            self.HEADER_H,
            fill=C["border"]
        )

        ci, ck, bs, bw, cl, cf = self._get_cols(w)

        headers = [
            (ci, "#", "w"),
            (ck, "ACTION", "w"),
            (bs + bw / 2, "DURATION", "center"),
            (cl, "LANE", "w"),
            (cf, "FLAGS", "w")
        ]

        for x, text, anchor in headers:

            label = self.canvas.create_text(
                x,
                13,
                anchor=anchor,
                text=text,
                fill=C["text_dim"],
                font=("Segoe UI", 8, "bold")
            )

            self._header_labels.append(label)

    def create_row(self):

        C = self.config.colors

        bg = self.canvas.create_rectangle(
            0, 0, 100, 30,
            fill=C["bg_secondary"],
            outline=""
        )

        glow = self.canvas.create_rectangle(
            0, 0, 100, 30,
            outline="",
            width=2
        )

        left = self.canvas.create_rectangle(
            0, 0, 6, 30,
            fill=C["accent"],
            outline=""
        )

        bar_bg = self.canvas.create_rectangle(
            0, 0, 100, 5,
            fill=C["bg_tertiary"],
            outline=""
        )

        bar_fill = self.canvas.create_rectangle(
            0, 0, 50, 5,
            fill=C["accent"],
            outline=""
        )

        t_index = self.canvas.create_text(
            0, 0,
            anchor="w",
            fill="#777",
            font=("Segoe UI", 8, "bold")
        )

        t_key = self.canvas.create_text(
            0, 0,
            anchor="w",
            fill=C["text"],
            font=("Segoe UI", 10, "bold")
        )

        t_dur = self.canvas.create_text(
            0, 0,
            anchor="center",
            fill=C["text_dim"],
            font=("Consolas", 8)
        )

        t_lane = self.canvas.create_text(
            0, 0,
            anchor="w",
            fill="#60a5fa",
            font=("Segoe UI", 8, "bold")
        )

        t_flags = self.canvas.create_text(
            0, 0,
            anchor="w",
            fill="#f0a844",
            font=("Segoe UI", 8)
        )

        items = [
            bg,
            glow,
            left,
            bar_bg,
            bar_fill,
            t_index,
            t_key,
            t_dur,
            t_lane,
            t_flags
        ]

        return {
            "items": items,
            "bg": bg,
            "glow": glow,
            "left": left,
            "bar_bg": bar_bg,
            "bar_fill": bar_fill,
            "index": t_index,
            "key": t_key,
            "dur": t_dur,
            "lane": t_lane,
            "flags": t_flags,
            "bound_index": -1,
            "y": 0,
            "cache": {},
            # Vector icon tracking
            "icon_items": [],   # list of canvas item ids for the action-type icon
            "icon_type": None,  # cached action_type so we only redraw on change
            "icon_color": None, # cached color so we redraw on theme change
            "icon_x": 0,        # current icon center x
            "icon_y": 0,        # current icon center y
            "img_item": None,   # canvas image item id for image-action preview
            "img_photo": None,  # PhotoImage reference (keep alive!)
            "zoom": 0,          # last zoom level for content invalidation
        }

    # =====================================================
    # FRAME LOOP
    # =====================================================

    def frame_loop(self):

        if not self._running:
            return

        now = time.perf_counter()

        dt = now - self._last_frame

        self._last_frame = now

        self.anim_time += dt

        # FPS Counter
        self._fps_counter += 1

        if now - self._fps_timer >= 1:
            self._current_fps = self._fps_counter
            self._fps_counter = 0
            self._fps_timer = now

        # Inertial scrolling
        if abs(self.scroll_velocity) > 0.1:

            self.scroll_velocity *= self.SCROLL_DECAY

            self.scroll_offset += self.scroll_velocity * dt

            self.clamp_scroll()

            self._dirty_all = True

        # Detect recording/live action changes
        actions_now = len(self.app.engine.actions)
        if actions_now != self._last_action_count:
            self._last_action_count = actions_now
            self._dirty_all = True
            self.clamp_scroll()

        # Only render if needed
        if self._dirty_all or self.playing_index >= 0:
            try:
                self.render()
            except Exception as e:
                logger.error(f"render: {e}")

        delay = max(1, int((self.FRAME_TIME - (time.perf_counter() - now)) * 1000))

        self.after(delay, self.frame_loop)

    # =====================================================
    # RENDER
    # =====================================================

    def render(self):

        if self._render_lock:
            return

        self._render_lock = True

        try:

            actions = self.app.engine.actions

            total = len(actions)

            row_h = self.scaled_row_height()

            canvas_h = self.canvas.winfo_height()

            canvas_w = self.canvas.winfo_width()

            first = max(0, int(self.scroll_offset / row_h))

            last = min(
                total - 1,
                first + self.pool_size - 1
            )

            self._visible_first = first
            self._visible_last = last

            # Scrollbar
            view_h = self._view_h()
            total_h = max(1, total * row_h)

            self.scrollbar.set(
                self.scroll_offset / total_h,
                (self.scroll_offset + view_h) / total_h
            )

            offset_y = self.scroll_offset % row_h

            for pool_i, row in enumerate(self.visible_pool):

                action_index = first + pool_i

                if action_index >= total:

                    self.hide_row(row)

                    continue

                action = actions[action_index]

                y = (
                    self.HEADER_H +
                    (pool_i * row_h) -
                    offset_y
                )

                # Only update geometry if needed
                if row["y"] != y or self._dirty_all:

                    self.position_row(
                        row,
                        y,
                        canvas_w,
                        row_h
                    )

                    row["y"] = y

                # Update content only if changed (or zoom changed)
                cache_key = (
                    action.key,
                    action.duration,
                    getattr(action, "lane", 0),
                    getattr(action, "label", ""),
                    getattr(action, "action_type", "key"),
                    getattr(action, "repeat_count", 1),
                )
                if (
                    row["bound_index"] != action_index or
                    row.get("zoom") != self.zoom or
                    row.get("cache_key") != cache_key
                ):
                    self.update_row_content(
                        row,
                        action,
                        action_index
                    )

                    row["bound_index"] = action_index
                    row["zoom"] = self.zoom
                    row["cache_key"] = cache_key

                # Fast animation updates
                self.animate_row(
                    row,
                    action_index,
                    action
                )

                self.show_row(row)

            self._dirty_all = False

            # Keep header on top of any row items that leak into header area
            for _item in getattr(self, "_header_bg", None), getattr(self, "_header_line", None):
                if _item is not None:
                    try:
                        self.canvas.tag_raise(_item)
                    except Exception:
                        pass
            for lbl in getattr(self, "_header_labels", []):
                try:
                    self.canvas.tag_raise(lbl)
                except Exception:
                    pass

        finally:
            self._render_lock = False

    # =====================================================
    # POSITIONING
    # =====================================================

    def position_row(self, row, y, w, row_h):

        x1 = 6
        x2 = w - 12
        ci, ck, bs, bw, cl, cf = self._get_cols(w)
        bar_y = y + (row_h - 5) / 2
        cy    = y + row_h / 2

        self.canvas.coords(
            row["bg"],
            x1, y, x2, y + row_h - 4
        )

        self.canvas.coords(
            row["glow"],
            x1, y, x2, y + row_h - 4
        )

        self.canvas.coords(
            row["left"],
            x1, y, x1 + 6, y + row_h - 4
        )

        self.canvas.coords(
            row["bar_bg"],
            bs, bar_y, bs + bw, bar_y + 5
        )

        self.canvas.coords(
            row["index"],
            ci, cy
        )

        # Vector icon sits at ck, text label is offset to the right
        icon_x = ck + 8
        text_x = ck + 24
        self._move_icon(row, icon_x, cy)

        self.canvas.coords(
            row["key"],
            text_x, cy
        )

        self.canvas.coords(
            row["dur"],
            bs + bw / 2, bar_y - 10
        )

        self.canvas.coords(
            row["lane"],
            cl, cy
        )

        self.canvas.coords(
            row["flags"],
            cf, cy
        )

    # =====================================================
    # CONTENT
    # =====================================================

    # ----- Vector icon helpers ---------------------------------
    ICON_COLORS = {
        "key":   "#20b87e",
        "click": "#60a5fa",
        "image": "#f59e0b",
        "pause": "#9ca3af",
    }

    def _set_icon(self, row, action_type):
        """Ensure row's icon matches action_type. Redraws if needed."""
        color = self.ICON_COLORS.get(action_type, self.config.colors["text"])
        if row["icon_type"] == action_type and row["icon_color"] == color and row["icon_items"]:
            return  # nothing to do

        # Delete any existing icon items
        for it in row["icon_items"]:
            try:
                self.canvas.delete(it)
            except Exception:
                pass
        # Delete any existing image preview
        if row.get("img_item"):
            try:
                self.canvas.delete(row["img_item"])
            except Exception:
                pass
            row["img_item"] = None
            row["img_photo"] = None
        # Draw new icon at current cached position
        items = CanvasIcons.draw(
            self.canvas, action_type,
            row["icon_x"], row["icon_y"],
            size=14, color=color)
        row["icon_items"] = items
        row["icon_type"]  = action_type
        row["icon_color"] = color

    def _move_icon(self, row, x, y):
        """Translate the row's icon items to (x,y) using canvas.move()."""
        dx = x - row["icon_x"]
        dy = y - row["icon_y"]
        if (dx or dy) and row["icon_items"]:
            for it in row["icon_items"]:
                try:
                    self.canvas.move(it, dx, dy)
                except Exception:
                    pass
        if (dx or dy) and row.get("img_item"):
            try:
                self.canvas.move(row["img_item"], dx, dy)
            except Exception:
                pass
        row["icon_x"] = x
        row["icon_y"] = y

    def _set_image_preview(self, row, action):
        """Decode base64 image_data and show a crisp preview on the canvas."""
        # Clear existing vector icon
        for it in row["icon_items"]:
            try:
                self.canvas.delete(it)
            except Exception:
                pass
        row["icon_items"] = []
        # Clear existing preview
        if row.get("img_item"):
            try:
                self.canvas.delete(row["img_item"])
            except Exception:
                pass
            row["img_item"] = None
            row["img_photo"] = None

        data = getattr(action, "image_data", "")
        if not data:
            return
        try:
            img_bytes = base64.b64decode(data)
            pil_img = Image.open(io.BytesIO(img_bytes)).convert("RGBA")
            MAX_W, MIN_W, MIN_H = 120, 28, 20
            aspect = pil_img.width / max(1, pil_img.height)

            # Start from natural size at 25% scale, adjusted by zoom
            scale = 0.25 * self.zoom
            w = int(pil_img.width * scale)
            h = int(pil_img.height * scale)

            # Hard cap: must fit inside the timeline row
            max_h = int(max(MIN_H, self.scaled_row_height() - 8))
            if h > max_h:
                h = max_h
                w = int(h * aspect)

            # If the image is too small to be visible, scale up to row height
            if w < MIN_W or h < MIN_H:
                h = max_h
                w = int(h * aspect)

            # Cap max width
            if w > MAX_W:
                w = MAX_W
                h = int(w / aspect)
                if h > max_h:
                    h = max_h
                    w = int(h * aspect)

            # Final minimum safety net
            if h < MIN_H:
                h = MIN_H
            if w < MIN_W:
                w = MIN_W

            resample = getattr(Image, "LANCZOS", getattr(Image, "ANTIALIAS", Image.BILINEAR))
            pil_img = pil_img.resize((w, h), resample)
            photo = ImageTk.PhotoImage(pil_img)
            item = self.canvas.create_image(
                row["icon_x"], row["icon_y"],
                image=photo, anchor="w", tags=()
            )
            row["img_photo"] = photo
            row["img_item"] = item
            row["icon_type"] = "image"
            row["icon_color"] = None
        except Exception as e:
            import traceback
            logger.error(f"Image preview failed: {e}")
            traceback.print_exc()

    def update_row_content(self, row, action, index):

        action_type = getattr(action, "action_type", "key")

        if action_type == "image" and getattr(action, "image_data", ""):
            # Try to show image preview; if it fails, fall back to icon + label
            self._set_image_preview(row, action)
            if row.get("img_item"):
                self.canvas.itemconfig(row["key"], text="", state="hidden")
            else:
                # Fallback: show icon + label if preview failed
                if row.get("icon_type") != "image":
                    self._set_icon(row, action_type)
                self.canvas.itemconfig(row["key"], state="normal")
        else:
            self._set_icon(row, action_type)
            self.canvas.itemconfig(row["key"], state="normal")

        label = getattr(action, "label", "")
        display = label or action.key

        self.canvas.itemconfig(
            row["index"],
            text=f"{index+1:02d}"
        )

        self.canvas.itemconfig(
            row["left"],
            fill={
                "key": "#20b87e",      # green
                "click": "#60a5fa",    # blue
                "image": "#f59e0b",    # yellow
                "pause": "#6b7280"     # gray (delay)
            }.get(action_type, self.config.colors["accent"])
        )

        self.canvas.itemconfig(
            row["key"],
            text=display if action_type != "image" else ""
        )

        self.canvas.itemconfig(
            row["dur"],
            text=f"{action.duration:.2f}s",
            fill=self.config.colors["text"]
        )

        self.canvas.itemconfig(
            row["lane"],
            text=f"L{action.lane}" if action.lane != 0 else ""
        )

        flags = []

        if getattr(action, "hold_mode", False):
            flags.append("HOLD")

        if getattr(action, "random_key", False):
            flags.append("RAND")

        rep = getattr(action, "repeat_count", 1)

        if rep > 1:
            flags.append(f"x{rep}")

        self.canvas.itemconfig(
            row["flags"],
            text=" • ".join(flags)
        )

    # =====================================================
    # ANIMATION
    # =====================================================

    def animate_row(self, row, index, action):

        C = self.config.colors

        playing = index == self.playing_index

        active = index == self.active_index

        hover = index == self.hover_index

        multi_selected = index in self.selected_indices

        theme = self.get_theme(action)

        primary = theme["primary"]

        secondary = theme["secondary"]

        bg = C["bg_secondary"]

        glow = ""

        if hover:
            bg = "#1c1f2b"

        if active:
            bg = "#25293a"
            glow = secondary

        if multi_selected:
            bg = "#2a2f45"
            glow = secondary

        if playing:
            # Static glow for playing row
            bg = theme["glow"]
            glow = secondary

        self.canvas.itemconfig(
            row["bg"],
            fill=bg
        )

        self.canvas.itemconfig(
            row["glow"],
            outline=glow
        )

        self.canvas.itemconfig(
            row["left"],
            fill=secondary if playing else primary
        )

        # Progress bar — real elapsed-time countdown
        canvas_w = self.canvas.winfo_width()
        _, _, bs, bw, _, _ = self._get_cols(canvas_w)
        progress = bw
        if playing and self._action_dur > 0:
            paused_extra = (time.time() - self._paused_at) if self._paused else 0.0
            elapsed = min(
                time.time() - self._action_start - self._pause_offset - paused_extra,
                self._action_dur
            )
            remaining = max(0.0, self._action_dur - elapsed)
            progress = max(2, int(bw * (remaining / self._action_dur)))

        row_h = self.scaled_row_height()
        bar_y = row["y"] + (row_h - 5) / 2
        self.canvas.coords(
            row["bar_fill"],
            bs, bar_y,
            bs + progress, bar_y + 5
        )

        self.canvas.itemconfig(
            row["bar_fill"],
            fill=secondary if playing else primary
        )

        # Live duration countdown text
        if playing and self._action_dur > 0:
            paused_extra = (time.time() - self._paused_at) if self._paused else 0.0
            elapsed = min(
                time.time() - self._action_start - self._pause_offset - paused_extra,
                self._action_dur
            )
            remaining = max(0.0, self._action_dur - elapsed)
            self.canvas.itemconfig(
                row["dur"],
                text=f"{remaining:.1f}s",
                fill=C["text"]
            )
        elif not playing and row.get("_was_playing"):
            self.canvas.itemconfig(
                row["dur"],
                text=f"{action.duration:.2f}s",
                fill=self.config.colors["text"]
            )
        row["_was_playing"] = playing

    # =====================================================
    # THEMES
    # =====================================================

    def get_theme(self, action):

        action_type = getattr(action, "action_type", "key")

        themes = {
            "key": {
                "primary": "#20b87e",
                "secondary": "#38d996",
                "glow": "#0f2d22"
            },
            "pause": {
                "primary": "#6b7280",
                "secondary": "#9ca3af",
                "glow": "#1f2937"
            },
            "image": {
                "primary": "#f59e0b",
                "secondary": "#fbbf24",
                "glow": "#451a03"
            },
            "click": {
                "primary": "#60a5fa",
                "secondary": "#93c5fd",
                "glow": "#1e3a8a"
            }
        }

        return themes.get(action_type, themes["key"])

    # =====================================================
    # SHOW/HIDE
    # =====================================================

    def hide_row(self, row):

        for item in row["items"]:
            self.canvas.itemconfigure(
                item,
                state="hidden"
            )
        for item in row.get("icon_items", ()):
            self.canvas.itemconfigure(item, state="hidden")
        if row.get("img_item"):
            self.canvas.itemconfigure(row["img_item"], state="hidden")

    def show_row(self, row):

        for item in row["items"]:
            self.canvas.itemconfigure(
                item,
                state="normal"
            )
        for item in row.get("icon_items", ()):
            self.canvas.itemconfigure(item, state="normal")
        if row.get("img_item"):
            self.canvas.itemconfigure(row["img_item"], state="normal")

    # =====================================================
    # EVENTS
    # =====================================================

    def on_resize(self, event):

        self._dirty_all = True

        if (
            event.width != self._last_width or
            event.height != self._last_height
        ):

            self._last_width = event.width
            self._last_height = event.height

            # Grow pool if zoom shrank and we need more rows
            row_h = self.scaled_row_height()
            needed = int(event.height / row_h) + self.BUFFER_ROWS
            while len(self.visible_pool) < needed:
                self.visible_pool.append(self.create_row())
                self.pool_size += 1

            self.create_header()
            self.clamp_scroll()

    def on_scroll(self, event):

        row_h = self.scaled_row_height()

        if hasattr(event, "delta") and event.delta:

            delta = -(event.delta / 120) * row_h * 8

        elif event.num == 4:

            delta = -row_h * 6

        else:

            delta = row_h * 6

        self.scroll_velocity += delta

        self.scroll_velocity = max(
            -self.MAX_VELOCITY,
            min(self.MAX_VELOCITY, self.scroll_velocity)
        )

    def on_zoom(self, event):

        old = self.zoom

        if event.delta > 0:
            self.zoom *= 1.1
        else:
            self.zoom /= 1.1

        self.zoom = max(0.4, min(3.0, self.zoom))

        if self.zoom != old:
            self._dirty_all = True

    def on_mouse_move(self, event):

        if event.y < self.HEADER_H:
            return

        row_h = self.scaled_row_height()

        idx = int(
            (event.y - self.HEADER_H + self.scroll_offset)
            / row_h
        )

        if idx != self.hover_index:
            self.hover_index = idx
            self._dirty_all = True

    def on_click(self, event):

        if event.y < self.HEADER_H:
            return

        row_h = self.scaled_row_height()

        idx = int(
            (event.y - self.HEADER_H + self.scroll_offset)
            / row_h
        )

        if 0 <= idx < len(self.app.engine.actions):
            self.drag_index = idx
            self.drag_start_y = event.y
            self.dragging = False
            # Shift+click for multi-select range
            if event.state & 0x0001:  # Shift key
                self.app.select_range(idx)
            else:
                self.app.select(idx)
                self.selected_indices.clear()
        else:
            self.app.select(-1)
            self.selected_indices.clear()

    def on_double_click(self, event):
        """Double-click on action to open editor dialog"""
        if event.y < self.HEADER_H:
            return

        row_h = self.scaled_row_height()

        idx = int(
            (event.y - self.HEADER_H + self.scroll_offset)
            / row_h
        )

        if 0 <= idx < len(self.app.engine.actions):
            action = self.app.engine.actions[idx]
            self.app.select(idx)
            
            # Open appropriate editor based on action type
            if action.is_image():
                self.app.open_image_editor(idx)
            elif action.is_click():
                self.app.open_click_editor(idx)
            elif action.action_type == "pause":
                self.app.open_pause_editor(idx)
            else:
                self.app.open_key_editor(idx)

    def _ensure_ghost_items(self):
        """Lazy-create canvas items used for drag ghost + drop line."""
        if self._ghost_bg is not None:
            return
        C = self.config.colors
        self._ghost_bg = self.canvas.create_rectangle(
            0, 0, 0, 0,
            fill=_lerp_color(C["bg_secondary"], C["accent"], 0.25),
            outline=C["accent"],
            width=1,
            state="hidden"
        )
        self._ghost_text = self.canvas.create_text(
            0, 0,
            anchor="w",
            fill=C["text"],
            font=("Segoe UI", 9, "bold"),
            state="hidden"
        )
        self._drop_line = self.canvas.create_line(
            0, 0, 0, 0,
            fill=C["accent"],
            width=2,
            state="hidden"
        )

    def on_drag_move(self, event):

        if self.drag_index < 0:
            return

        if abs(event.y - self.drag_start_y) > 8:
            if not self.dragging:
                self.dragging = True
                self._ensure_ghost_items()
                # populate ghost text from original action
                action = self.app.engine.actions[self.drag_index]
                atype = getattr(action, "action_type", "key")
                icons = {"key": "⌨", "pause": "⏸", "image": "📷", "click": "🖱"}
                icon = icons.get(atype, "•")
                label = getattr(action, "label", "")
                self.canvas.itemconfig(
                    self._ghost_text,
                    text=f"{icon} {label or action.key}"
                )
                self.canvas.itemconfig(self._ghost_bg, state="normal")
                self.canvas.itemconfig(self._ghost_text, state="normal")
                self.canvas.itemconfig(self._drop_line, state="normal")

        if self.dragging:
            row_h = self.scaled_row_height()
            target = int(
                (event.y - self.HEADER_H + self.scroll_offset)
                / row_h
            )
            target = max(0, min(target, len(self.app.engine.actions)))
            self.drag_target = target

            # Position ghost at cursor
            w = self.canvas.winfo_width()
            x1, x2 = 6, w - 12
            ghost_y = event.y - row_h / 2
            self.canvas.coords(self._ghost_bg, x1, ghost_y, x2, ghost_y + row_h - 4)
            self.canvas.coords(self._ghost_text, x1 + 30, event.y)
            self.canvas.tag_raise(self._ghost_bg)
            self.canvas.tag_raise(self._ghost_text)

            # Drop line at target row top
            target_y = self.HEADER_H + (target * row_h) - self.scroll_offset
            self.canvas.coords(self._drop_line, 0, target_y, w, target_y)
            self.canvas.tag_raise(self._drop_line)

    def on_drag_end(self, event):

        if self.dragging:
            if self.drag_target != self.drag_index:
                actions = self.app.engine.actions
                action = actions.pop(self.drag_index)
                # clamp target after removal
                target = max(0, min(self.drag_target, len(actions)))
                actions.insert(target, action)
                self.app.select(target)
                self.app.save_session()
                self.app.update_statistics()
                self.app.history.push(actions)
                for row in self.visible_pool:
                    row["bound_index"] = -1
                self._dirty_all = True

        # hide ghost & drop line
        if self._ghost_bg is not None:
            self.canvas.itemconfig(self._ghost_bg, state="hidden")
            self.canvas.itemconfig(self._ghost_text, state="hidden")
            self.canvas.itemconfig(self._drop_line, state="hidden")

        self.dragging = False
        self.drag_index = -1
        self.drag_target = -1

    def on_right_click(self, event):

        if event.y < self.HEADER_H:
            return

        row_h = self.scaled_row_height()
        idx = int(
            (event.y - self.HEADER_H + self.scroll_offset)
            / row_h
        )

        actions = self.app.engine.actions
        if idx < 0 or idx >= len(actions):
            return

        self.app.select(idx)

        C = self.config.colors
        m = tk.Menu(self.canvas, tearoff=0,
            bg=C["bg_tertiary"], fg=C["text"],
            activebackground=C["accent"],
            activeforeground="black",
            relief="flat", bd=0,
            font=("Segoe UI", 9))

        action = actions[idx]
        label_key = "IMAGE" if getattr(action, "action_type", "key") == "image" else action.key.upper()
        m.add_command(label=f"  Action {idx + 1}: {label_key}",
            state="disabled", font=("Segoe UI", 8, "bold"))
        m.add_separator()

        atype = getattr(action, "action_type", "key")
        if atype == "image":
            m.add_command(label="  ✎  Edit image...",
                command=lambda: self.app.open_image_editor(idx),
                foreground=C["playing"])
        elif atype == "click":
            m.add_command(label="  ✎  Edit click...",
                command=lambda: self.app.open_click_editor(idx),
                foreground=C["neon_blue"])
        elif atype == "pause":
            m.add_command(label="  ✎  Edit delay...",
                command=lambda: self.app.open_pause_editor(idx),
                foreground=C["warning"])
        else:
            m.add_command(label="  ✎  Edit key...",
                command=lambda: self.app.open_key_editor(idx),
                foreground=C["accent"])
        m.add_separator()

        m.add_command(label="  ⧉  Duplicate",
            command=lambda: self.app.duplicate_action(idx))
        m.add_command(label="  ↑  Move Up",
            command=lambda: self.app.move_action_to(idx, idx - 1),
            state="normal" if idx > 0 else "disabled")
        m.add_command(label="  ↓  Move Down",
            command=lambda: self.app.move_action_to(idx, idx + 1),
            state="normal" if idx < len(actions) - 1 else "disabled")
        m.add_separator()
        m.add_command(label="  ⎘  Copy",
            command=lambda: self.app.copy_action_index(idx))
        m.add_command(label="  ⎙  Paste Below",
            command=lambda: self.app.paste_action())
        m.add_separator()
        m.add_command(label="  ✕  Delete",
            command=lambda: self.app.delete_action(idx),
            foreground=C["error"])

        try:
            m.tk_popup(event.x_root, event.y_root)
        finally:
            m.grab_release()

    def scrollbar_scroll(self, *args):

        row_h = self.scaled_row_height()

        total_h = len(self.app.engine.actions) * row_h

        view_h = self._view_h()

        if args[0] == "moveto":

            self.scroll_offset = (
                (total_h - view_h)
                * float(args[1])
            )

        elif args[0] == "scroll":

            self.scroll_offset += (
                int(args[1]) * row_h * 4
            )

        self.clamp_scroll()

        self._dirty_all = True

    # =====================================================
    # HELPERS
    # =====================================================

    def scaled_row_height(self):

        return max(20, int(self.ROW_H * self.zoom))

    def _view_h(self):
        """Height available for rows (canvas minus header)."""
        return max(1, self.canvas.winfo_height() - self.HEADER_H)

    def clamp_scroll(self):

        row_h = self.scaled_row_height()

        max_scroll = max(
            0,
            len(self.app.engine.actions) * row_h
            - self._view_h()
        )

        self.scroll_offset = max(
            0,
            min(max_scroll, self.scroll_offset)
        )

    def ensure_visible(self, index):

        row_h = self.scaled_row_height()

        y = index * row_h

        view_h = self._view_h()

        if y < self.scroll_offset:
            self.scroll_offset = y

        elif y + row_h > self.scroll_offset + view_h:
            self.scroll_offset = y - view_h + row_h

        self.clamp_scroll()

    # =====================================================
    # PUBLIC API
    # =====================================================

    def refresh(self):

        self._last_action_count = len(self.app.engine.actions)

        for row in self.visible_pool:
            row["bound_index"] = -1
            row["cache_key"] = None
            row["zoom"] = 0

        self.canvas.update_idletasks()

        self._dirty_all = True

    def set_active(self, index):

        self.active_index = index

        self._dirty_all = True

    def set_playing(self, index):

        self.playing_index = index
        self._action_start = time.time()
        self._pause_offset = 0.0
        self._paused = False

        actions = self.app.engine.actions
        if 0 <= index < len(actions):
            speed = getattr(self.app.engine, "speed_multiplier", 1.0)
            self._action_dur = actions[index].duration / max(speed, 0.01)
        else:
            self._action_dur = 0.0

        self.ensure_visible(index)
        self._dirty_all = True
        self.canvas.update_idletasks()

    def set_paused(self, paused: bool):

        if paused and not self._paused:
            self._paused = True
            self._paused_at = time.time()
        elif not paused and self._paused:
            self._pause_offset += time.time() - self._paused_at
            self._paused = False
        self._dirty_all = True

    def clear_playing(self):

        self.playing_index = -1
        self._action_dur = 0.0
        self._dirty_all = True
        self.canvas.update_idletasks()

    def destroy(self):

        self._running = False

        super().destroy()
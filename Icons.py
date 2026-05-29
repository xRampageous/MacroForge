"""
Icons.py - Centralized vector icon system for MacroForge.

Provides two icon strategies:
  1. CanvasIcons:  Draw vector icons directly on a Tkinter Canvas
                   (used by CanvasTimeline for crisp, scalable, theme-aware icons).
  2. IconFactory:  Render vector icons to PhotoImage for use in Tk widgets
                   (Buttons, Menus, Dialogs).  Anti-aliased via 4x supersampling.

All icons are drawn from primitive shapes so there are NO external
font/SVG dependencies and they scale beautifully at any size.
"""

from PIL import Image, ImageDraw, ImageTk


# =====================================================================
#  CANVAS VECTOR ICONS  (drawn directly on tk.Canvas)
# =====================================================================
class CanvasIcons:
    """Draw vector icons directly on a Tk canvas.
       Returns a list of canvas item IDs so the caller can reposition / recolor."""

    @staticmethod
    def draw(canvas, name, cx, cy, size=14, color="#e8eaf0", tags=()):
        """Draw an icon centered at (cx,cy). Returns list of canvas item IDs."""
        s = size
        h = s / 2.0
        fn = getattr(CanvasIcons, f"_draw_{name}", None)
        if fn is None:
            fn = CanvasIcons._draw_dot
        return fn(canvas, cx, cy, h, color, tags)

    # ---------- individual icon drawings ----------

    @staticmethod
    def _draw_key(canvas, cx, cy, h, color, tags):
        """Keyboard: rounded rectangle with three small keys."""
        items = []
        # body
        items.append(canvas.create_rectangle(
            cx - h, cy - h*0.55, cx + h, cy + h*0.55,
            outline=color, width=1.5, tags=tags))
        # 3 key dots
        kw = h * 0.35
        kh = h * 0.18
        for dx in (-h*0.55, 0, h*0.55):
            items.append(canvas.create_rectangle(
                cx + dx - kw/2, cy - kh, cx + dx + kw/2, cy + kh,
                fill=color, outline="", tags=tags))
        return items

    @staticmethod
    def _draw_pause(canvas, cx, cy, h, color, tags):
        """Clock face for delay/pause."""
        items = []
        r = h * 0.95
        items.append(canvas.create_oval(
            cx - r, cy - r, cx + r, cy + r,
            outline=color, width=1.5, tags=tags))
        # hour hand (up)
        items.append(canvas.create_line(
            cx, cy, cx, cy - r*0.55,
            fill=color, width=1.5, tags=tags))
        # minute hand (right)
        items.append(canvas.create_line(
            cx, cy, cx + r*0.7, cy,
            fill=color, width=1.5, tags=tags))
        return items

    @staticmethod
    def _draw_image(canvas, cx, cy, h, color, tags):
        """Camera icon: body + lens + flash."""
        items = []
        # body
        items.append(canvas.create_rectangle(
            cx - h, cy - h*0.5, cx + h, cy + h*0.7,
            outline=color, width=1.5, tags=tags))
        # viewfinder bump on top
        items.append(canvas.create_rectangle(
            cx - h*0.35, cy - h*0.8, cx + h*0.05, cy - h*0.5,
            outline=color, width=1.5, tags=tags))
        # lens
        r = h * 0.35
        items.append(canvas.create_oval(
            cx - r, cy - r*0.4, cx + r, cy + r*1.6,
            outline=color, width=1.5, tags=tags))
        return items

    @staticmethod
    def _draw_click(canvas, cx, cy, h, color, tags):
        """Mouse pointer (arrow) icon."""
        items = []
        # Classic arrow cursor outline
        pts = [
            cx - h*0.4, cy - h*0.8,
            cx - h*0.4, cy + h*0.6,
            cx - h*0.05, cy + h*0.25,
            cx + h*0.2, cy + h*0.8,
            cx + h*0.4, cy + h*0.65,
            cx + h*0.15, cy + h*0.15,
            cx + h*0.55, cy + h*0.0,
        ]
        items.append(canvas.create_polygon(
            pts, outline=color, fill=color, width=1, tags=tags))
        return items

    @staticmethod
    def _draw_dot(canvas, cx, cy, h, color, tags):
        items = [canvas.create_oval(
            cx - h*0.3, cy - h*0.3, cx + h*0.3, cy + h*0.3,
            fill=color, outline="", tags=tags)]
        return items


# =====================================================================
#  PHOTOIMAGE ICONS  (for widgets that can't host canvas drawings)
# =====================================================================
class IconFactory:
    """Generates anti-aliased PhotoImage icons for use in Buttons/Menus.

    Internal:  draws at 4x size with PIL, downsamples with LANCZOS.
    Cached by (name,size,color,bg) so repeated calls are free.
    """
    _cache = {}
    SCALE = 4  # supersampling factor for antialiasing

    @classmethod
    def get(cls, name, size=16, color="#e8eaf0", bg=None):
        key = (name, size, color, bg)
        cached = cls._cache.get(key)
        if cached is not None:
            return cached

        S = size * cls.SCALE
        img = Image.new('RGBA', (S, S), bg if bg else (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        fn = getattr(cls, f"_draw_{name}", None)
        if fn is None:
            fn = cls._draw_dot
        fn(draw, S, color)

        img = img.resize((size, size), Image.LANCZOS)
        photo = ImageTk.PhotoImage(img)
        cls._cache[key] = photo
        return photo

    # ---------- drawing helpers ----------
    @staticmethod
    def _outline(draw, xy, color, width=1, fill=None):
        """Rectangle / ellipse outline with rounded caps."""
        if fill is not None:
            draw.rectangle(xy, fill=fill, outline=color, width=width)
        else:
            draw.rectangle(xy, outline=color, width=width)

    # ---------- icon definitions (S = full canvas size in px) ----------
    @staticmethod
    def _draw_key(draw, S, c):
        m = S * 0.10
        # keyboard body
        draw.rounded_rectangle((m, S*0.30, S-m, S*0.78),
                               radius=S*0.06, outline=c, width=max(2, S//32))
        # rows of keys
        kw = (S - m*2 - S*0.16) / 3
        for row in (0.40, 0.58):
            for i in range(3):
                x0 = m + S*0.04 + i*(kw + S*0.04)
                draw.rounded_rectangle((x0, S*row, x0+kw, S*(row+0.10)),
                                       radius=S*0.02, fill=c)

    @staticmethod
    def _draw_click(draw, S, c):
        """Mouse cursor arrow."""
        pts = [
            (S*0.28, S*0.15),
            (S*0.28, S*0.78),
            (S*0.43, S*0.62),
            (S*0.55, S*0.88),
            (S*0.68, S*0.82),
            (S*0.56, S*0.56),
            (S*0.75, S*0.50),
        ]
        draw.polygon(pts, fill=c, outline=c)

    @staticmethod
    def _draw_delay(draw, S, c):
        """Clock face."""
        m = S * 0.12
        w = max(2, S//32)
        draw.ellipse((m, m, S-m, S-m), outline=c, width=w)
        # hands
        draw.line((S/2, S/2, S/2, S*0.25), fill=c, width=w)
        draw.line((S/2, S/2, S*0.70, S/2), fill=c, width=w)
        # tick at 12
        draw.ellipse((S/2-S*0.025, m-S*0.02, S/2+S*0.025, m+S*0.03), fill=c)

    @staticmethod
    def _draw_image(draw, S, c):
        """Camera."""
        w = max(2, S//32)
        # body
        draw.rounded_rectangle((S*0.10, S*0.30, S*0.90, S*0.82),
                               radius=S*0.05, outline=c, width=w)
        # top bump (viewfinder)
        draw.rounded_rectangle((S*0.30, S*0.18, S*0.55, S*0.32),
                               radius=S*0.03, outline=c, width=w)
        # lens
        draw.ellipse((S*0.34, S*0.40, S*0.66, S*0.72),
                     outline=c, width=w)
        # flash dot
        draw.ellipse((S*0.74, S*0.36, S*0.80, S*0.42), fill=c)

    @staticmethod
    def _draw_record(draw, S, c):
        """Solid red circle."""
        m = S * 0.20
        draw.ellipse((m, m, S-m, S-m), fill=c)

    @staticmethod
    def _draw_play(draw, S, c):
        """Right-pointing triangle."""
        m = S * 0.22
        pts = [(m, m), (m, S-m), (S-m, S/2)]
        draw.polygon(pts, fill=c)

    @staticmethod
    def _draw_pause(draw, S, c):
        """Two vertical bars."""
        bw = S * 0.14
        gap = S * 0.10
        h0 = S * 0.22
        h1 = S * 0.78
        x0 = S/2 - gap/2 - bw
        x1 = S/2 + gap/2
        draw.rectangle((x0, h0, x0+bw, h1), fill=c)
        draw.rectangle((x1, h0, x1+bw, h1), fill=c)

    @staticmethod
    def _draw_stop(draw, S, c):
        """Square."""
        m = S * 0.26
        draw.rectangle((m, m, S-m, S-m), fill=c)

    @staticmethod
    def _draw_save(draw, S, c):
        """Floppy disk."""
        w = max(2, S//32)
        draw.rounded_rectangle((S*0.15, S*0.15, S*0.85, S*0.85),
                               radius=S*0.05, outline=c, width=w)
        # label area
        draw.rectangle((S*0.25, S*0.50, S*0.75, S*0.78), outline=c, width=w)
        # tab
        draw.rectangle((S*0.30, S*0.20, S*0.70, S*0.38), fill=c)

    @staticmethod
    def _draw_folder(draw, S, c):
        w = max(2, S//32)
        draw.polygon([(S*0.10, S*0.30), (S*0.40, S*0.30),
                      (S*0.46, S*0.36), (S*0.90, S*0.36),
                      (S*0.90, S*0.80), (S*0.10, S*0.80)],
                     outline=c, width=w)

    @staticmethod
    def _draw_import(draw, S, c):
        """Down-arrow into tray."""
        w = max(2, S//32)
        # arrow
        draw.line((S/2, S*0.18, S/2, S*0.62), fill=c, width=w)
        draw.polygon([(S*0.35, S*0.50), (S*0.65, S*0.50), (S/2, S*0.72)], fill=c)
        # tray
        draw.line((S*0.18, S*0.82, S*0.82, S*0.82), fill=c, width=w)

    @staticmethod
    def _draw_export(draw, S, c):
        """Up-arrow out of tray."""
        w = max(2, S//32)
        # arrow
        draw.line((S/2, S*0.82, S/2, S*0.38), fill=c, width=w)
        draw.polygon([(S*0.35, S*0.50), (S*0.65, S*0.50), (S/2, S*0.28)], fill=c)
        # tray
        draw.line((S*0.18, S*0.82, S*0.82, S*0.82), fill=c, width=w)

    @staticmethod
    def _draw_compile(draw, S, c):
        """Hammer/wrench: simple wrench."""
        w = max(2, S//32)
        draw.line((S*0.25, S*0.75, S*0.70, S*0.30), fill=c, width=int(w*1.6))
        draw.ellipse((S*0.62, S*0.18, S*0.86, S*0.42), outline=c, width=w)
        draw.ellipse((S*0.14, S*0.62, S*0.36, S*0.84), fill=c)

    @staticmethod
    def _draw_reset(draw, S, c):
        """Circular refresh arrow."""
        w = max(2, S//32)
        m = S * 0.20
        # 3/4 circle
        draw.arc((m, m, S-m, S-m), start=40, end=320, fill=c, width=w)
        # arrowhead at the open end
        draw.polygon([(S*0.78, S*0.32), (S*0.88, S*0.20), (S*0.72, S*0.18)], fill=c)

    @staticmethod
    def _draw_trash(draw, S, c):
        """Trash can."""
        w = max(2, S//32)
        # lid
        draw.line((S*0.15, S*0.28, S*0.85, S*0.28), fill=c, width=w)
        # handle
        draw.rectangle((S*0.38, S*0.18, S*0.62, S*0.28), outline=c, width=w)
        # body
        draw.polygon([(S*0.22, S*0.30), (S*0.78, S*0.30),
                      (S*0.72, S*0.86), (S*0.28, S*0.86)],
                     outline=c, width=w)
        # vertical lines
        for x in (S*0.40, S*0.50, S*0.60):
            draw.line((x, S*0.38, x, S*0.78), fill=c, width=max(1, w//2))

    @staticmethod
    def _draw_plus(draw, S, c):
        w = max(3, S//16)
        draw.line((S/2, S*0.20, S/2, S*0.80), fill=c, width=w)
        draw.line((S*0.20, S/2, S*0.80, S/2), fill=c, width=w)

    @staticmethod
    def _draw_pencil(draw, S, c):
        """Pencil for rename."""
        w = max(2, S//32)
        # body
        draw.polygon([(S*0.20, S*0.74), (S*0.66, S*0.28),
                      (S*0.78, S*0.40), (S*0.32, S*0.86)], outline=c, width=w)
        # tip
        draw.polygon([(S*0.18, S*0.76), (S*0.30, S*0.88), (S*0.14, S*0.88)], fill=c)

    @staticmethod
    def _draw_books(draw, S, c):
        """Stack of books (profiles)."""
        w = max(2, S//32)
        for i, y in enumerate((S*0.22, S*0.46, S*0.70)):
            draw.rectangle((S*0.18, y, S*0.82, y+S*0.16), outline=c, width=w)

    @staticmethod
    def _draw_check(draw, S, c):
        w = max(3, S//12)
        draw.line((S*0.22, S*0.55, S*0.42, S*0.74), fill=c, width=w)
        draw.line((S*0.42, S*0.74, S*0.80, S*0.30), fill=c, width=w)

    @staticmethod
    def _draw_cross(draw, S, c):
        w = max(3, S//14)
        draw.line((S*0.25, S*0.25, S*0.75, S*0.75), fill=c, width=w)
        draw.line((S*0.75, S*0.25, S*0.25, S*0.75), fill=c, width=w)

    @staticmethod
    def _draw_copy(draw, S, c):
        """Two overlapping documents."""
        w = max(2, S//32)
        draw.rounded_rectangle((S*0.22, S*0.18, S*0.66, S*0.62),
                               radius=S*0.04, outline=c, width=w)
        draw.rounded_rectangle((S*0.34, S*0.38, S*0.78, S*0.82),
                               radius=S*0.04, outline=c, width=w, fill=(0,0,0,0))

    @staticmethod
    def _draw_warning(draw, S, c):
        w = max(2, S//32)
        draw.polygon([(S/2, S*0.15), (S*0.90, S*0.85), (S*0.10, S*0.85)],
                     outline=c, width=w)
        draw.line((S/2, S*0.40, S/2, S*0.62), fill=c, width=w)
        draw.ellipse((S/2-S*0.04, S*0.68, S/2+S*0.04, S*0.76), fill=c)

    @staticmethod
    def _draw_bolt(draw, S, c):
        pts = [(S*0.52, S*0.10), (S*0.22, S*0.55),
               (S*0.45, S*0.55), (S*0.40, S*0.90),
               (S*0.72, S*0.42), (S*0.50, S*0.42)]
        draw.polygon(pts, fill=c)

    @staticmethod
    def _draw_pin(draw, S, c):
        """Location pin."""
        w = max(2, S//32)
        # teardrop
        draw.ellipse((S*0.25, S*0.12, S*0.75, S*0.62),
                     outline=c, width=w)
        # tail
        draw.polygon([(S*0.40, S*0.55), (S*0.60, S*0.55), (S/2, S*0.88)],
                     fill=c)
        # inner dot
        draw.ellipse((S*0.42, S*0.28, S*0.58, S*0.44), fill=c)

    @staticmethod
    def _draw_gear(draw, S, c):
        """Gear / settings."""
        w = max(2, S//32)
        cx = cy = S/2
        r_out = S * 0.40
        r_in  = S * 0.22
        # 8 teeth
        import math
        teeth = []
        for i in range(16):
            ang = (i / 16) * 2 * math.pi
            r = r_out if (i % 2 == 0) else r_out * 0.78
            teeth.append((cx + r*math.cos(ang), cy + r*math.sin(ang)))
        draw.polygon(teeth, outline=c, width=w)
        # center hole
        draw.ellipse((cx-r_in, cy-r_in, cx+r_in, cy+r_in),
                     outline=c, width=w)

    @staticmethod
    def _draw_loop(draw, S, c):
        """Circular loop arrows."""
        w = max(2, S//32)
        m = S * 0.22
        # 3/4 circle
        draw.arc((m, m, S-m, S-m), start=20, end=280, fill=c, width=w)
        # arrow head
        draw.polygon([(S*0.74, S*0.30), (S*0.84, S*0.20), (S*0.70, S*0.18)], fill=c)

    @staticmethod
    def _draw_dot(draw, S, c):
        m = S * 0.40
        draw.ellipse((m, m, S-m, S-m), fill=c)

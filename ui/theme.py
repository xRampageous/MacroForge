"""Modern dark theme for MacroForge PyQt6 — fresh rebuild.

Glassmorphism-inspired dark theme with vibrant accents,
gradient highlights, and smooth micro-interactions.
"""

# ═══════════════════════════════════════════════════════
#  COLOR PALETTE
# ═══════════════════════════════════════════════════════
COLORS = {
    # ── Surfaces (deep indigo-black with subtle blue undertone) ──
    "bg": "#080910",
    "bg_secondary": "#0e0f1a",
    "bg_tertiary": "#161827",
    "bg_card": "#1a1d30",
    "bg_hover": "#222540",
    "bg_pressed": "#2a2d4d",
    "bg_glass": "#ffffff06",

    # ── Primary accent (electric cyan-blue) ──
    "accent": "#4cc4ff",
    "accent_secondary": "#2f95e0",
    "accent_glow": "#4cc4ff22",
    "accent_hover": "#7ad6ff",
    "accent_dim": "#4cc4ff66",

    # ── Semantic ──
    "error": "#ff5c79",
    "error_bg": "#ff5c7918",
    "warning": "#ffb13d",
    "warning_bg": "#ffb13d18",
    "success": "#3fe08a",
    "success_bg": "#3fe08a18",
    "info": "#4cc4ff",
    "info_bg": "#4cc4ff18",

    # ── Text ──
    "text": "#e6e8f5",
    "text_dim": "#787a9c",
    "text_dark": "#42445f",
    "text_inverse": "#06070d",

    # ── Borders ──
    "border": "#24263f",
    "border_light": "#383b63",
    "border_accent": "#4cc4ff44",

    # ── Action-type accents (vibrant, distinct) ──
    "key": "#4cc4ff",       # cyan
    "click": "#ff5c79",     # rose
    "image": "#ffcc4d",     # amber
    "pause": "#9aa6c4",     # slate
    "condition": "#c77dff", # violet

    # ── Playback ──
    "playing": "#3fe08a",
    "playing_glow": "#3fe08a22",
    "lane": "#2a3a4c",

    # ── Neon highlights ──
    "neon_blue": "#4cc4ff",
    "neon_purple": "#c77dff",
    "neon_gold": "#ffcc4d",
    "neon_green": "#3fe08a",
    "neon_rose": "#ff5c79",
}

TYPE_COLORS = {
    "key": COLORS["key"],
    "pause": COLORS["pause"],
    "image": COLORS["image"],
    "click": COLORS["click"],
    "condition": COLORS["condition"],
}

TYPE_GLOW = {
    "key": "#00e5a020",
    "pause": "#9ca3af20",
    "image": "#f59e0b20",
    "click": "#60a5fa20",
    "condition": "#d26bff20",
}


# ═══════════════════════════════════════════════════════
#  QSS STYLESHEET
# ═══════════════════════════════════════════════════════
def build_stylesheet() -> str:
    C = COLORS
    return f"""
    /* ═══════════════════════════════════════════════════════ */
    /*  GLOBAL                                                */
    /* ═══════════════════════════════════════════════════════ */
    QWidget {{
        font-family: 'Segoe UI', 'SF Pro Display', -apple-system, sans-serif;
        font-size: 13px;
        color: {C['text']};
        background-color: {C['bg']};
        selection-background-color: {C['accent_glow']};
        selection-color: {C['accent']};
    }}
    QMainWindow {{ background-color: {C['bg']}; }}
    QFrame {{ background: transparent; border: none; }}

    /* ═══════════════════════════════════════════════════════ */
    /*  GLASS CARD                                            */
    /* ═══════════════════════════════════════════════════════ */
    QFrame#glass_card {{
        background-color: {C['bg_glass']};
        border: 1px solid {C['border']};
        border-radius: 12px;
    }}

    /* ═══════════════════════════════════════════════════════ */
    /*  LABELS                                                */
    /* ═══════════════════════════════════════════════════════ */
    QLabel {{ background: transparent; color: {C['text']}; }}
    QLabel#title {{
        color: {C['accent']};
        font-size: 15px;
        font-weight: bold;
        letter-spacing: 1px;
    }}
    QLabel#section {{
        color: {C['text_dim']};
        font-size: 10px;
        font-weight: bold;
        letter-spacing: 1.5px;
        text-transform: uppercase;
    }}
    QLabel#status {{ color: {C['text_dim']}; font-size: 11px; }}
    QLabel#stats {{ color: {C['text_dim']}; font-size: 11px; }}
    QLabel#hint {{ color: {C['text_dark']}; font-size: 10px; font-style: italic; }}

    /* ═══════════════════════════════════════════════════════ */
    /*  BUTTONS                                               */
    /* ═══════════════════════════════════════════════════════ */
    QPushButton {{
        background-color: {C['bg_tertiary']};
        color: {C['text']};
        border: 1px solid {C['border']};
        border-radius: 10px;
        padding: 8px 16px;
        font-weight: 500;
    }}
    QPushButton:hover {{
        background-color: {C['bg_hover']};
        border-color: {C['border_light']};
    }}
    QPushButton:pressed {{
        background-color: {C['bg_pressed']};
    }}
    QPushButton:disabled {{
        background-color: {C['bg_secondary']};
        color: {C['text_dark']};
        border-color: {C['border']};
    }}

    QPushButton#accent {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
            stop:0 {C['accent']}, stop:1 {C['accent_secondary']});
        color: {C['text_inverse']};
        border: none;
        font-weight: 700;
    }}
    QPushButton#accent:hover {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
            stop:0 {C['accent_hover']}, stop:1 {C['accent']});
    }}
    QPushButton#accent:pressed {{
        background: {C['accent_secondary']};
    }}

    QPushButton#danger {{
        background-color: {C['error_bg']};
        color: {C['error']};
        border: 1px solid {C['error']}40;
    }}
    QPushButton#danger:hover {{
        background-color: {C['error']};
        color: #ffffff;
        border-color: {C['error']};
    }}

    QPushButton#success {{
        background-color: {C['success_bg']};
        color: {C['success']};
        border: 1px solid {C['success']}40;
    }}
    QPushButton#success:hover {{
        background-color: {C['success']};
        color: #ffffff;
        border-color: {C['success']};
    }}

    QPushButton#warning {{
        background-color: {C['warning_bg']};
        color: {C['warning']};
        border: 1px solid {C['warning']}40;
    }}
    QPushButton#warning:hover {{
        background-color: {C['warning']};
        color: #ffffff;
        border-color: {C['warning']};
    }}

    QPushButton#tool {{
        background: transparent;
        border: 1px solid {C['border']};
        border-radius: 8px;
        padding: 5px 10px;
        font-size: 12px;
        color: {C['text_dim']};
    }}
    QPushButton#tool:hover {{
        background-color: {C['bg_hover']};
        color: {C['text']};
        border-color: {C['border_light']};
    }}
    QPushButton#tool:checked {{
        background-color: {C['accent_glow']};
        border-color: {C['accent']};
        color: {C['accent']};
    }}

    QPushButton#sidebar {{
        background: transparent;
        border: none;
        border-radius: 8px;
        padding: 10px 12px;
        text-align: left;
        color: {C['text_dim']};
        font-size: 12px;
    }}
    QPushButton#sidebar:hover {{
        background-color: {C['bg_hover']};
        color: {C['text']};
    }}
    QPushButton#sidebar:checked {{
        background-color: {C['accent_glow']};
        color: {C['accent']};
        font-weight: 600;
    }}

    QPushButton#action_add {{
        background-color: {C['bg_tertiary']};
        color: {C['text_dim']};
        border: 1px solid {C['border']};
        border-radius: 8px;
        padding: 6px 10px;
        text-align: left;
        font-size: 12px;
    }}
    QPushButton#action_add:hover {{
        background-color: {C['bg_hover']};
        color: {C['accent']};
        border-color: {C['accent']};
    }}

    /* ── Colorful per-action-type add buttons ── */
    QPushButton#add_key {{
        background-color: {C['bg_tertiary']}; color: {C['text']};
        border: 1px solid {C['key']}40; border-left: 3px solid {C['key']};
        border-radius: 8px; padding: 7px 10px; text-align: left; font-size: 12px; font-weight: 600;
    }}
    QPushButton#add_key:hover {{ background-color: {C['key']}22; border-color: {C['key']}; color: {C['key']}; }}

    QPushButton#add_click {{
        background-color: {C['bg_tertiary']}; color: {C['text']};
        border: 1px solid {C['click']}40; border-left: 3px solid {C['click']};
        border-radius: 8px; padding: 7px 10px; text-align: left; font-size: 12px; font-weight: 600;
    }}
    QPushButton#add_click:hover {{ background-color: {C['click']}22; border-color: {C['click']}; color: {C['click']}; }}

    QPushButton#add_image {{
        background-color: {C['bg_tertiary']}; color: {C['text']};
        border: 1px solid {C['image']}40; border-left: 3px solid {C['image']};
        border-radius: 8px; padding: 7px 10px; text-align: left; font-size: 12px; font-weight: 600;
    }}
    QPushButton#add_image:hover {{ background-color: {C['image']}22; border-color: {C['image']}; color: {C['image']}; }}

    QPushButton#add_pause {{
        background-color: {C['bg_tertiary']}; color: {C['text']};
        border: 1px solid {C['pause']}40; border-left: 3px solid {C['pause']};
        border-radius: 8px; padding: 7px 10px; text-align: left; font-size: 12px; font-weight: 600;
    }}
    QPushButton#add_pause:hover {{ background-color: {C['pause']}22; border-color: {C['pause']}; color: {C['pause']}; }}

    QPushButton#add_condition {{
        background-color: {C['bg_tertiary']}; color: {C['text']};
        border: 1px solid {C['condition']}40; border-left: 3px solid {C['condition']};
        border-radius: 8px; padding: 7px 10px; text-align: left; font-size: 12px; font-weight: 600;
    }}
    QPushButton#add_condition:hover {{ background-color: {C['condition']}22; border-color: {C['condition']}; color: {C['condition']}; }}

    /* ── Circular playback control buttons ── */
    QPushButton#play_btn {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {C['success']}, stop:1 #2bbf6e);
        color: {C['text_inverse']}; border: none; border-radius: 10px; font-weight: 700; padding: 8px;
    }}
    QPushButton#play_btn:hover {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #5cf0a0, stop:1 {C['success']}); }}
    QPushButton#play_btn:disabled {{ background: {C['bg_secondary']}; color: {C['text_dark']}; }}

    QPushButton#pause_btn {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {C['warning']}, stop:1 #e09020);
        color: {C['text_inverse']}; border: none; border-radius: 10px; font-weight: 700; padding: 8px;
    }}
    QPushButton#pause_btn:hover {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #ffc766, stop:1 {C['warning']}); }}
    QPushButton#pause_btn:disabled {{ background: {C['bg_secondary']}; color: {C['text_dark']}; }}

    QPushButton#stop_btn {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {C['error']}, stop:1 #d9415e);
        color: {C['text_inverse']}; border: none; border-radius: 10px; font-weight: 700; padding: 8px;
    }}
    QPushButton#stop_btn:hover {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #ff7a92, stop:1 {C['error']}); }}
    QPushButton#stop_btn:disabled {{ background: {C['bg_secondary']}; color: {C['text_dark']}; }}

    QPushButton#record_btn {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {C['error']}, stop:1 #d9415e);
        color: #ffffff; border: none; border-radius: 10px; font-weight: 700; padding: 8px;
    }}
    QPushButton#record_btn:hover {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #ff7a92, stop:1 {C['error']}); }}

    QPushButton#icon_btn {{
        background: transparent; border: none; border-radius: 6px;
        padding: 4px; min-width: 28px; min-height: 28px;
    }}
    QPushButton#icon_btn:hover {{ background-color: {C['bg_hover']}; }}

    QPushButton#compact {{
        background-color: {C['bg_tertiary']};
        color: {C['text_dim']};
        border: 1px solid {C['border']};
        border-radius: 6px;
        padding: 4px 8px;
        font-size: 11px;
    }}
    QPushButton#compact:hover {{
        background-color: {C['bg_hover']};
        color: {C['text']};
        border-color: {C['border_light']};
    }}

    /* ═══════════════════════════════════════════════════════ */
    /*  COMBOBOX                                              */
    /* ═══════════════════════════════════════════════════════ */
    QComboBox {{
        background-color: {C['bg_tertiary']};
        color: {C['text']};
        border: 1px solid {C['border']};
        border-radius: 8px;
        padding: 5px 10px;
    }}
    QComboBox:hover {{ border-color: {C['border_light']}; }}
    QComboBox::drop-down {{ border: none; width: 22px; }}
    QComboBox::down-arrow {{
        image: none;
        border-left: 4px solid transparent;
        border-right: 4px solid transparent;
        border-top: 5px solid {C['text_dim']};
        margin-right: 6px;
    }}
    QComboBox QAbstractItemView {{
        background-color: {C['bg_tertiary']};
        color: {C['text']};
        border: 1px solid {C['border']};
        border-radius: 8px;
        selection-background-color: {C['bg_hover']};
        selection-color: {C['accent']};
        padding: 4px;
    }}

    /* ═══════════════════════════════════════════════════════ */
    /*  SPINBOX / DOUBLESPINBOX                               */
    /* ═══════════════════════════════════════════════════════ */
    QSpinBox, QDoubleSpinBox {{
        background-color: {C['bg_tertiary']};
        color: {C['text']};
        border: 1px solid {C['border']};
        border-radius: 8px;
        padding: 5px 10px;
    }}
    QSpinBox:hover, QDoubleSpinBox:hover {{ border-color: {C['border_light']}; }}
    QSpinBox::up-button, QDoubleSpinBox::up-button,
    QSpinBox::down-button, QDoubleSpinBox::down-button {{
        border: none; background: transparent; width: 16px;
    }}

    /* ═══════════════════════════════════════════════════════ */
    /*  CHECKBOX                                              */
    /* ═══════════════════════════════════════════════════════ */
    QCheckBox {{
        color: {C['text_dim']};
        spacing: 6px;
        font-size: 12px;
    }}
    QCheckBox::indicator {{
        width: 16px; height: 16px;
        border: 1px solid {C['border']};
        border-radius: 5px;
        background-color: {C['bg_tertiary']};
    }}
    QCheckBox::indicator:checked {{
        background-color: {C['accent']};
        border-color: {C['accent']};
    }}
    QCheckBox::indicator:hover {{ border-color: {C['border_light']}; }}

    /* ═══════════════════════════════════════════════════════ */
    /*  LINE EDIT                                             */
    /* ═══════════════════════════════════════════════════════ */
    QLineEdit {{
        background-color: {C['bg_tertiary']};
        color: {C['text']};
        border: 1px solid {C['border']};
        border-radius: 8px;
        padding: 5px 10px;
        font-size: 12px;
    }}
    QLineEdit:focus {{ border-color: {C['accent']}; }}
    QLineEdit::placeholder {{ color: {C['text_dark']}; }}

    /* ═══════════════════════════════════════════════════════ */
    /*  SLIDER / PROGRESS                                     */
    /* ═══════════════════════════════════════════════════════ */
    QSlider::groove:horizontal {{
        height: 4px;
        background: {C['border']};
        border-radius: 2px;
    }}
    QSlider::sub-page:horizontal {{
        background: {C['accent']};
        border-radius: 2px;
    }}
    QSlider::handle:horizontal {{
        background: {C['accent']};
        width: 14px; height: 14px;
        border-radius: 7px;
        margin: -5px 0;
    }}
    QSlider::handle:horizontal:hover {{ background: {C['accent_hover']}; }}

    QProgressBar {{
        background-color: {C['border']};
        border-radius: 3px;
        border: none;
        height: 4px;
        text-align: center;
    }}
    QProgressBar::chunk {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 {C['accent_secondary']}, stop:1 {C['accent']});
        border-radius: 3px;
    }}

    /* ═══════════════════════════════════════════════════════ */
    /*  SCROLLBAR                                             */
    /* ═══════════════════════════════════════════════════════ */
    QScrollBar:vertical {{
        background-color: transparent;
        width: 6px;
        border-radius: 3px;
    }}
    QScrollBar::handle:vertical {{
        background-color: {C['border_light']};
        border-radius: 3px;
        min-height: 30px;
    }}
    QScrollBar::handle:vertical:hover {{ background-color: {C['text_dim']}; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}

    QScrollBar:horizontal {{
        background-color: transparent;
        height: 6px;
        border-radius: 3px;
    }}
    QScrollBar::handle:horizontal {{
        background-color: {C['border_light']};
        border-radius: 3px;
        min-width: 30px;
    }}
    QScrollBar::handle:horizontal:hover {{ background-color: {C['text_dim']}; }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0px; }}

    /* ═══════════════════════════════════════════════════════ */
    /*  MENU                                                  */
    /* ═══════════════════════════════════════════════════════ */
    QMenu {{
        background-color: {C['bg_tertiary']};
        color: {C['text']};
        border: 1px solid {C['border']};
        border-radius: 10px;
        padding: 6px;
    }}
    QMenu::item {{
        padding: 6px 18px;
        border-radius: 6px;
    }}
    QMenu::item:selected {{
        background-color: {C['bg_hover']};
        color: {C['accent']};
    }}
    QMenu::separator {{
        height: 1px;
        background-color: {C['border']};
        margin: 4px 8px;
    }}

    /* ═══════════════════════════════════════════════════════ */
    /*  TOOLTIP                                               */
    /* ═══════════════════════════════════════════════════════ */
    QToolTip {{
        background-color: {C['bg_tertiary']};
        color: {C['text']};
        border: 1px solid {C['border']};
        border-radius: 8px;
        padding: 4px 10px;
        font-size: 12px;
    }}

    /* ═══════════════════════════════════════════════════════ */
    /*  DIALOG                                                */
    /* ═══════════════════════════════════════════════════════ */
    QDialog {{ background-color: {C['bg']}; }}

    /* ═══════════════════════════════════════════════════════ */
    /*  TAB BAR (Profile tabs)                                */
    /* ═══════════════════════════════════════════════════════ */
    QPushButton#tab {{
        background: transparent;
        border: none;
        border-bottom: 2px solid transparent;
        border-radius: 0;
        padding: 6px 14px;
        color: {C['text_dim']};
        font-size: 12px;
    }}
    QPushButton#tab:hover {{ color: {C['text']}; }}
    QPushButton#tab:checked {{
        color: {C['accent']};
        border-bottom-color: {C['accent']};
        font-weight: 600;
    }}
"""

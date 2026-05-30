"""Modern dark theme for MacroForge PyQt6 — fresh rebuild.

Glassmorphism-inspired dark theme with vibrant accents,
gradient highlights, and smooth micro-interactions.
"""

# ═══════════════════════════════════════════════════════
#  COLOR PALETTE
# ═══════════════════════════════════════════════════════
COLORS = {
    # Base
    "bg": "#08080f",
    "bg_secondary": "#0f0f18",
    "bg_tertiary": "#161622",
    "bg_card": "#1a1a2e",
    "bg_hover": "#222238",
    "bg_pressed": "#2a2a42",
    "bg_glass": "#ffffff08",

    # Accents
    "accent": "#00e5a0",
    "accent_secondary": "#00c288",
    "accent_glow": "#00e5a020",
    "accent_hover": "#33ffbd",
    "accent_dim": "#00e5a060",

    # Semantic
    "error": "#ff4757",
    "error_bg": "#ff475715",
    "warning": "#ffa502",
    "warning_bg": "#ffa50215",
    "success": "#2ed573",
    "success_bg": "#2ed57315",
    "info": "#1e90ff",
    "info_bg": "#1e90ff15",

    # Text
    "text": "#e8eaf0",
    "text_dim": "#7a7d9e",
    "text_dark": "#4a4d6a",
    "text_inverse": "#08080f",

    # Borders
    "border": "#252540",
    "border_light": "#353555",
    "border_accent": "#00e5a040",

    # Type colors
    "key": "#00e5a0",
    "click": "#60a5fa",
    "image": "#f59e0b",
    "pause": "#9ca3af",
    "condition": "#d26bff",

    # Playback
    "playing": "#38b4a8",
    "playing_glow": "#38b4a820",
    "lane": "#2a3a4c",

    # Neon
    "neon_blue": "#38b4ff",
    "neon_purple": "#d26bff",
    "neon_gold": "#f0a844",
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

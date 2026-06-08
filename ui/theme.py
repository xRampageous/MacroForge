"""MacroForge desktop theme.

The palette mirrors the supplied MacroForge UI reference: deep navy surfaces,
quiet blue-grey borders, and restrained neon accents used as outlines.
"""

# ═══════════════════════════════════════════════════════
#  COLOR PALETTE
# ═══════════════════════════════════════════════════════
COLORS = {
    # ── Surfaces ──
    "bg": "#000207",
    "bg_secondary": "#010711",
    "bg_tertiary": "#04101A",
    "bg_card": "#020A13",
    "bg_hover": "#071A2A",
    "bg_pressed": "#0B2438",
    "bg_glass": "#020A13",

    # ── Primary accent ──
    "accent": "#0096FF",
    "accent_secondary": "#006FDC",
    "accent_glow": "rgba(0, 150, 255, 0.18)",
    "accent_hover": "#32B1FF",
    "accent_dim": "#1A5B86",

    # ── Semantic ──
    "error": "#FF2330",
    "error_bg": "rgba(255, 35, 48, 0.10)",
    "warning": "#FFD000",
    "warning_bg": "rgba(255, 208, 0, 0.10)",
    "success": "#00D75A",
    "success_bg": "rgba(0, 215, 90, 0.10)",
    "info": "#008DFF",
    "info_bg": "rgba(0, 141, 255, 0.10)",

    # ── Text ──
    "text": "#F3F6FA",
    "text_dim": "#B0C0D6",
    "text_dark": "#65788D",
    "text_inverse": "#F3F6FA",
    "btn_text": "#F3F6FA",

    # ── Borders ──
    "border": "#143047",
    "border_light": "#25506E",
    "border_accent": "#0096FF",

    # ── Action-type accents (from reference) ──
    "key": "#008DFF",
    "click": "#FF2330",
    "image": "#FFD000",
    "pause": "#B9B9B9",
    "condition": "#D932FF",
    "group": "#8B5CF6",
    "loop": "#00E5A8",
    "pause_cyan": "#00C8FF",

    # ── Playback ──
    "playing": "#00D75A",
    "playing_glow": "rgba(0, 215, 90, 0.14)",
    "lane": "#203142",

    # ── Neon highlights ──
    "neon_blue": "#008DFF",
    "neon_purple": "#D932FF",
    "neon_gold": "#FFD000",
    "neon_green": "#00D75A",
    "neon_rose": "#FF2330",
}

TYPE_COLORS = {
    "key": COLORS["key"],
    "pause": COLORS["pause"],
    "image": COLORS["image"],
    "click": COLORS["click"],
    "condition": COLORS["condition"],
    "group": COLORS["group"],
    "loop": COLORS["loop"],
}

TYPE_GLOW = {
    "key": "#008DFF",
    "pause": "#B9B9B9",
    "image": "#FFD000",
    "click": "#FF2330",
    "condition": "#D932FF",
    "group": "#8B5CF6",
    "loop": "#00E5A8",
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
        background-color: transparent;
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
        background-color: {C['bg_card']};
        color: {C['text']};
        border: 1px solid {C['border']};
        border-radius: 10px;
        padding: 8px 16px;
        font-weight: 500;
        text-align: center;
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

    /* ── Outlined per-action-type add buttons ── */
    QPushButton#add_key {{
        background-color: transparent;
        color: {C['text']}; border: 1px solid {C['key']};
        border-radius: 6px; padding: 10px 14px; text-align: left; font-size: 12px; font-weight: 600;
        margin-bottom: 4px;
    }}
    QPushButton#add_key:hover {{ background-color: {C['info_bg']}; }}
    QPushButton#add_key:pressed {{ background-color: {C['bg_pressed']}; }}

    QPushButton#add_click {{
        background-color: transparent;
        color: {C['text']}; border: 1px solid {C['click']};
        border-radius: 6px; padding: 10px 14px; text-align: left; font-size: 12px; font-weight: 600;
        margin-bottom: 4px;
    }}
    QPushButton#add_click:hover {{ background-color: {C['error_bg']}; }}
    QPushButton#add_click:pressed {{ background-color: {C['bg_pressed']}; }}

    QPushButton#add_image {{
        background-color: transparent;
        color: {C['text']}; border: 1px solid {C['image']};
        border-radius: 6px; padding: 10px 14px; text-align: left; font-size: 12px; font-weight: 600;
        margin-bottom: 4px;
    }}
    QPushButton#add_image:hover {{ background-color: {C['warning_bg']}; }}
    QPushButton#add_image:pressed {{ background-color: {C['bg_pressed']}; }}

    QPushButton#add_pause {{
        background-color: transparent;
        color: {C['text']}; border: 1px solid {C['pause']};
        border-radius: 6px; padding: 10px 14px; text-align: left; font-size: 12px; font-weight: 600;
        margin-bottom: 4px;
    }}
    QPushButton#add_pause:hover {{ background-color: {C['bg_hover']}; }}
    QPushButton#add_pause:pressed {{ background-color: {C['bg_pressed']}; }}

    QPushButton#add_condition {{
        background-color: {C['condition']};
        color: #ffffff; border: none;
        border-radius: 4px; padding: 10px 12px; text-align: left; font-size: 12px; font-weight: 700;
        margin-bottom: 2px;
    }}
    QPushButton#add_condition:hover {{ background-color: #da9aff; }}
    QPushButton#add_condition:pressed {{ background-color: #a855f7; }}

    QPushButton#add_capture {{
        background-color: {C['accent']};
        color: #ffffff; border: none;
        border-radius: 4px; padding: 10px 12px; text-align: left; font-size: 12px; font-weight: 700;
        margin-bottom: 2px;
    }}
    QPushButton#add_capture:hover {{ background-color: {C['accent_hover']}; }}
    QPushButton#add_capture:pressed {{ background-color: {C['accent_secondary']}; }}

    /* Fixed Add Action sizing guard: keeps app-level ID rules from shrinking the new stacked buttons. */
    QPushButton#add_key, QPushButton#add_click, QPushButton#add_pause, QPushButton#add_image,
    QPushButton#add_condition, QPushButton#add_loop, QPushButton#add_group {{
        min-height: 42px;
        max-height: 42px;
        height: 42px;
        padding: 0px;
        margin: 0px;
    }}

    /* ── Outlined playback controls ── */
    QPushButton#play_btn {{
        background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #99{C['success'][1:]}, stop:1 #000000);
        color: {C['text']}; border: 1px solid #99{C['success'][1:]}; border-radius: 7px; font-weight: 700; padding: 8px;
    }}
    QPushButton#play_btn:hover {{
        background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 {C['success']}, stop:1 #000000);
        border-color: {C['success']};
    }}
    QPushButton#play_btn:pressed {{ background: #55{C['success'][1:]}; }}
    QPushButton#play_btn:disabled {{ background: {C['bg_secondary']}; color: {C['text_dark']}; border: 1px solid {C['border']}; }}

    QPushButton#pause_btn {{
        background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #99{C['pause_cyan'][1:]}, stop:1 #000000);
        color: {C['text']}; border: 1px solid #99{C['pause_cyan'][1:]}; border-radius: 7px; font-weight: 700; padding: 8px;
    }}
    QPushButton#pause_btn:hover {{
        background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 {C['pause_cyan']}, stop:1 #000000);
        border-color: {C['pause_cyan']};
    }}
    QPushButton#pause_btn:pressed {{ background: #55{C['pause_cyan'][1:]}; }}
    QPushButton#pause_btn:disabled {{ background: {C['bg_secondary']}; color: {C['text_dark']}; border: 1px solid {C['border']}; }}

    QPushButton#stop_btn {{
        background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #99{C['error'][1:]}, stop:1 #000000);
        color: {C['text']}; border: 1px solid #99{C['error'][1:]}; border-radius: 7px; font-weight: 700; padding: 8px;
    }}
    QPushButton#stop_btn:hover {{
        background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 {C['error']}, stop:1 #000000);
        border-color: {C['error']};
    }}
    QPushButton#stop_btn:pressed {{ background: #55{C['error'][1:]}; }}
    QPushButton#stop_btn:disabled {{ background: {C['bg_secondary']}; color: {C['text_dark']}; border: 1px solid {C['border']}; }}

    QPushButton#record_btn {{
        background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #321018, stop:0.52 #16070B, stop:1 #050205);
        color: #FF5A68; border: 1px solid #B8202E; border-radius: 8px; font-weight: 800; padding: 8px;
    }}
    QPushButton#record_btn:hover {{
        background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #47131E, stop:0.52 #21080E, stop:1 #070306);
        color: #FFFFFF; border-color: #FF3142;
    }}

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
        background-color: {C['accent']};
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
    QDialog {{
        background-color: {C['bg']};
        color: {C['text']};
    }}

    QMessageBox, QFileDialog, QInputDialog {{
        background-color: {C['bg']};
        color: {C['text']};
    }}

    QMessageBox QLabel, QFileDialog QLabel, QInputDialog QLabel {{
        color: {C['text']};
        font-size: 12px;
        background: transparent;
    }}

    QMessageBox QPushButton, QInputDialog QPushButton, QFileDialog QPushButton {{
        background-color: {C['bg_tertiary']};
        color: {C['text']};
        border: 1px solid {C['border']};
        border-radius: 8px;
        padding: 7px 14px;
        min-width: 76px;
        font-size: 12px;
        font-weight: 800;
    }}

    QMessageBox QPushButton:hover, QInputDialog QPushButton:hover, QFileDialog QPushButton:hover {{
        border-color: {C['accent']};
        background-color: {C['bg_secondary']};
    }}

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

    /* ═══════════════════════════════════════════════════════ */
    /*  MACROFORGE 2.0 UI REWORK DETAILS                      */
    /* ═══════════════════════════════════════════════════════ */
    QPushButton#view_toggle {{
        background-color: {C['bg_card']};
        color: {C['text_dim']};
        border: 1px solid {C['border']};
        border-radius: 12px;
        padding: 0;
        min-width: 40px;
        max-width: 40px;
        min-height: 28px;
        max-height: 28px;
    }}
    QPushButton#view_toggle:hover {{
        background-color: {C['bg_hover']};
        border-color: {C['border_light']};
    }}
    QPushButton#view_toggle:checked {{
        background-color: {C['accent_glow']};
        border-color: {C['accent']};
    }}

    QPushButton#rec_round_btn {{
        background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #321018, stop:0.52 #16070B, stop:1 #050205);
        color: #FF5A68;
        border: 1px solid #B8202E;
        border-radius: 10px;
        padding: 0px;
        min-width: 100px;
        max-width: 100px;
        width: 100px;
        min-height: 45px;
        max-height: 45px;
        height: 45px;
        font-size: 12px;
        font-weight: 900;
        text-align: center;
    }}
    QPushButton#rec_round_btn:hover {{
        background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #47131E, stop:0.52 #21080E, stop:1 #070306);
        color: #FFFFFF;
        border-color: #FF3142;
    }}
    QPushButton#rec_round_btn:pressed {{
        background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #090305, stop:0.55 #2B0810, stop:1 #66131D);
        border-color: #FF5464;
    }}

    QPushButton#rec_pause_btn {{
        background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #17262E, stop:0.52 #0B151A, stop:1 #04090D);
        color: #DDE8F2;
        border: 1px solid #2A5560;
        border-radius: 10px;
        padding: 0px;
        min-width: 100px;
        max-width: 100px;
        width: 100px;
        min-height: 45px;
        max-height: 45px;
        height: 45px;
        font-size: 12px;
        font-weight: 900;
        text-align: center;
    }}
    QPushButton#rec_pause_btn:hover {{
        background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #063C49, stop:0.52 #061F26, stop:1 #030E12);
        color: #FFFFFF;
        border-color: #25D8FF;
    }}
    QPushButton#rec_pause_btn:disabled {{
        background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #182126, stop:0.52 #0D1418, stop:1 #05090C);
        color: #63707A;
        border-color: #24323A;
    }}

    QCheckBox#pill_check {{
        color: {C['text']};
        font-size: 10px;
        font-weight: 800;
        spacing: 4px;
    }}
    QCheckBox#pill_check::indicator {{
        width: 14px;
        height: 14px;
        border-radius: 5px;
        border: 1px solid {C['border_light']};
        background-color: {C['bg_secondary']};
    }}
    QCheckBox#pill_check::indicator:checked {{
        background-color: {C['accent_glow']};
        border-color: {C['accent']};
    }}

    QPushButton#icon_btn {{
        background-color: {C['bg_tertiary']};
        border: 1px solid {C['border']};
        border-radius: 10px;
        padding: 4px;
    }}
    QPushButton#icon_btn:hover {{
        background-color: {C['bg_hover']};
        border-color: {C['border_light']};
    }}

    QPushButton#top_icon_btn {{
        background-color: {C['bg_tertiary']};
        border: 1px solid {C['border']};
        border-radius: 10px;
        padding: 4px;
        min-width: 36px;
        max-width: 36px;
        min-height: 36px;
        max-height: 36px;
    }}
    QPushButton#top_icon_btn:hover {{
        background-color: {C['bg_hover']};
        border-color: {C['border_light']};
    }}

"""

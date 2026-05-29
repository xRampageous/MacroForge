"""Modern dark theme for MacroForge PyQt6 UI."""

COLORS = {
    "bg": "#0b0b11",
    "bg_secondary": "#111118",
    "bg_tertiary": "#181824",
    "bg_card": "#1a1a28",
    "bg_hover": "#1e1e2e",
    "bg_pressed": "#252538",
    "accent": "#20b87e",
    "accent_secondary": "#178a5e",
    "accent_glow": "#0d2a1e",
    "accent_hover": "#2dd99a",
    "text": "#e8eaf0",
    "text_dim": "#8a8da8",
    "text_dark": "#55566a",
    "border": "#252535",
    "border_light": "#353545",
    "highlight": "#20b87e",
    "error": "#f05555",
    "error_bg": "#2a1515",
    "warning": "#f0a844",
    "warning_bg": "#2a2010",
    "success": "#44ee88",
    "success_bg": "#152a1e",
    "info": "#38b4ff",
    "info_bg": "#101a2a",
    "neon_blue": "#38b4ff",
    "neon_purple": "#d26bff",
    "neon_gold": "#f0a844",
    "glass": "#ffffff08",
    "shadow": "#00000040",
    "playing": "#38b4a8",
    "playing_glow": "#0d2520",
    "lane": "#2a3a4c",
    "lane_glow": "#1a2535",
    "pause": "#6b5740",
    "pause_glow": "#2e2418",
    "key": "#20b87e",
    "click": "#60a5fa",
    "image": "#f59e0b",
    "pause_color": "#9ca3af",
    "condition": "#d26bff",
}

TYPE_COLORS = {
    "key": COLORS["key"],
    "pause": COLORS["pause_color"],
    "image": COLORS["image"],
    "click": COLORS["click"],
    "condition": COLORS["condition"],
}


def build_stylesheet() -> str:
    C = COLORS
    return f"""
    /* ═══════════════════════════════════════════════════════ */
    /*  GLOBAL                                                */
    /* ═══════════════════════════════════════════════════════ */
    QWidget {{
        font-family: 'Segoe UI', 'SF Pro Display', sans-serif;
        font-size: 13px;
        color: {C['text']};
        background-color: {C['bg']};
    }}

    QMainWindow {{
        background-color: {C['bg']};
    }}

    /* ═══════════════════════════════════════════════════════ */
    /*  FRAMES & CONTAINERS                                   */
    /* ═══════════════════════════════════════════════════════ */
    QFrame {{
        background-color: {C['bg_secondary']};
        border: none;
    }}

    /* ═══════════════════════════════════════════════════════ */
    /*  LABELS                                                */
    /* ═══════════════════════════════════════════════════════ */
    QLabel {{
        color: {C['text']};
        background: transparent;
    }}

    /* ═══════════════════════════════════════════════════════ */
    /*  BUTTONS                                               */
    /* ═══════════════════════════════════════════════════════ */
    QPushButton {{
        background-color: {C['bg_tertiary']};
        color: {C['text']};
        border: 1px solid {C['border']};
        border-radius: 8px;
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
        background-color: {C['accent']};
        color: #ffffff;
        border: none;
        font-weight: 600;
    }}
    QPushButton#accent:hover {{
        background-color: {C['accent_hover']};
    }}
    QPushButton#accent:pressed {{
        background-color: {C['accent_secondary']};
    }}

    QPushButton#tool {{
        background-color: transparent;
        border: 1px solid {C['border']};
        border-radius: 6px;
        padding: 4px 10px;
        font-size: 12px;
        color: {C['text_dim']};
    }}
    QPushButton#tool:hover {{
        background-color: {C['bg_hover']};
        color: {C['text']};
        border-color: {C['border_light']};
    }}
    QPushButton#tool:pressed {{
        background-color: {C['bg_pressed']};
    }}
    QPushButton#tool:checked {{
        background-color: {C['accent_glow']};
        border-color: {C['accent']};
        color: {C['accent']};
    }}

    QPushButton#danger {{
        background-color: {C['error_bg']};
        color: {C['error']};
        border: 1px solid {C['error']};
    }}
    QPushButton#danger:hover {{
        background-color: {C['error']};
        color: #ffffff;
    }}

    /* ═══════════════════════════════════════════════════════ */
    /*  COMBOBOX                                              */
    /* ═══════════════════════════════════════════════════════ */
    QComboBox {{
        background-color: {C['bg_tertiary']};
        color: {C['text']};
        border: 1px solid {C['border']};
        border-radius: 6px;
        padding: 6px 10px;
        min-width: 100px;
    }}
    QComboBox:hover {{
        border-color: {C['border_light']};
    }}
    QComboBox::drop-down {{
        border: none;
        width: 24px;
    }}
    QComboBox::down-arrow {{
        image: none;
        border-left: 5px solid transparent;
        border-right: 5px solid transparent;
        border-top: 6px solid {C['text_dim']};
        margin-right: 8px;
    }}
    QComboBox QAbstractItemView {{
        background-color: {C['bg_tertiary']};
        color: {C['text']};
        border: 1px solid {C['border']};
        border-radius: 6px;
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
        border-radius: 6px;
        padding: 6px 10px;
    }}
    QSpinBox:hover, QDoubleSpinBox:hover {{
        border-color: {C['border_light']};
    }}
    QSpinBox::up-button, QDoubleSpinBox::up-button {{
        border: none;
        background: transparent;
        width: 18px;
    }}
    QSpinBox::down-button, QDoubleSpinBox::down-button {{
        border: none;
        background: transparent;
        width: 18px;
    }}

    /* ═══════════════════════════════════════════════════════ */
    /*  CHECKBOX                                              */
    /* ═══════════════════════════════════════════════════════ */
    QCheckBox {{
        color: {C['text_dim']};
        spacing: 6px;
    }}
    QCheckBox::indicator {{
        width: 16px;
        height: 16px;
        border: 1px solid {C['border']};
        border-radius: 4px;
        background-color: {C['bg_tertiary']};
    }}
    QCheckBox::indicator:checked {{
        background-color: {C['accent']};
        border-color: {C['accent']};
    }}
    QCheckBox::indicator:hover {{
        border-color: {C['border_light']};
    }}

    /* ═══════════════════════════════════════════════════════ */
    /*  LINE EDIT                                             */
    /* ═══════════════════════════════════════════════════════ */
    QLineEdit {{
        background-color: {C['bg_tertiary']};
        color: {C['text']};
        border: 1px solid {C['border']};
        border-radius: 6px;
        padding: 6px 10px;
    }}
    QLineEdit:focus {{
        border-color: {C['accent']};
    }}
    QLineEdit::placeholder {{
        color: {C['text_dark']};
    }}

    /* ═══════════════════════════════════════════════════════ */
    /*  TEXT EDIT                                             */
    /* ═══════════════════════════════════════════════════════ */
    QTextEdit {{
        background-color: {C['bg_tertiary']};
        color: {C['text']};
        border: 1px solid {C['border']};
        border-radius: 6px;
        padding: 6px;
    }}

    /* ═══════════════════════════════════════════════════════ */
    /*  TABLE WIDGET                                          */
    /* ═══════════════════════════════════════════════════════ */
    QTableWidget {{
        background-color: {C['bg_secondary']};
        color: {C['text']};
        border: 1px solid {C['border']};
        border-radius: 8px;
        gridline-color: {C['border']};
        selection-background-color: {C['bg_hover']};
        selection-color: {C['text']};
    }}
    QTableWidget::item {{
        padding: 6px 8px;
        border-bottom: 1px solid {C['border']};
    }}
    QTableWidget::item:selected {{
        background-color: {C['bg_hover']};
    }}
    QHeaderView::section {{
        background-color: {C['bg_tertiary']};
        color: {C['text_dim']};
        padding: 8px;
        border: none;
        border-bottom: 2px solid {C['border']};
        font-weight: 600;
        font-size: 11px;
    }}
    QHeaderView::section:hover {{
        background-color: {C['bg_hover']};
    }}

    /* ═══════════════════════════════════════════════════════ */
    /*  SCROLLBAR                                             */
    /* ═══════════════════════════════════════════════════════ */
    QScrollBar:vertical {{
        background-color: {C['bg_secondary']};
        width: 8px;
        border-radius: 4px;
    }}
    QScrollBar::handle:vertical {{
        background-color: {C['border_light']};
        border-radius: 4px;
        min-height: 30px;
    }}
    QScrollBar::handle:vertical:hover {{
        background-color: {C['text_dim']};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}
    QScrollBar:horizontal {{
        background-color: {C['bg_secondary']};
        height: 8px;
        border-radius: 4px;
    }}
    QScrollBar::handle:horizontal {{
        background-color: {C['border_light']};
        border-radius: 4px;
        min-width: 30px;
    }}
    QScrollBar::handle:horizontal:hover {{
        background-color: {C['text_dim']};
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0px;
    }}

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
        width: 14px;
        height: 14px;
        border-radius: 7px;
        margin: -5px 0;
    }}
    QSlider::handle:horizontal:hover {{
        background: {C['accent_hover']};
    }}

    /* ═══════════════════════════════════════════════════════ */
    /*  SPLITTER                                              */
    /* ═══════════════════════════════════════════════════════ */
    QSplitter::handle {{
        background-color: {C['border']};
    }}
    QSplitter::handle:horizontal {{
        width: 2px;
    }}
    QSplitter::handle:vertical {{
        height: 2px;
    }}

    /* ═══════════════════════════════════════════════════════ */
    /*  TAB WIDGET                                            */
    /* ═══════════════════════════════════════════════════════ */
    QTabWidget::pane {{
        border: 1px solid {C['border']};
        border-radius: 8px;
        background-color: {C['bg_secondary']};
    }}
    QTabBar::tab {{
        background-color: {C['bg_tertiary']};
        color: {C['text_dim']};
        border: 1px solid {C['border']};
        border-bottom: none;
        border-top-left-radius: 8px;
        border-top-right-radius: 8px;
        padding: 8px 16px;
        font-weight: 500;
    }}
    QTabBar::tab:selected {{
        background-color: {C['bg_secondary']};
        color: {C['accent']};
        border-bottom: 2px solid {C['accent']};
    }}
    QTabBar::tab:hover {{
        background-color: {C['bg_hover']};
        color: {C['text']};
    }}

    /* ═══════════════════════════════════════════════════════ */
    /*  DIALOG                                                */
    /* ═══════════════════════════════════════════════════════ */
    QDialog {{
        background-color: {C['bg']};
    }}

    /* ═══════════════════════════════════════════════════════ */
    /*  MENU                                                  */
    /* ═══════════════════════════════════════════════════════ */
    QMenu {{
        background-color: {C['bg_tertiary']};
        color: {C['text']};
        border: 1px solid {C['border']};
        border-radius: 8px;
        padding: 6px;
    }}
    QMenu::item {{
        padding: 6px 20px;
        border-radius: 4px;
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
        border-radius: 6px;
        padding: 4px 8px;
    }}
"""

"""Shared helpers for MacroForge action dialogs — cohesive colorful styling."""
from PyQt6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QFrame, QVBoxLayout
from PyQt6.QtCore import Qt, QSize
from ui.theme import COLORS
from ui.icons import icon


def dialog_stylesheet(accent: str) -> str:
    C = COLORS
    tint = accent.lstrip("#")
    return f"""
        QDialog {{
            background-color: {C['bg']};
            color: {C['text']};
        }}

        QLabel {{
            color: {C['text_dim']};
            font-size: 12px;
            font-weight: 600;
            background: transparent;
        }}

        QLabel#dialog_title {{
            color: {accent};
            font-size: 14px;
            font-weight: 950;
            letter-spacing: 0.8px;
        }}

        QLabel#dialog_subtitle {{
            color: {C['text_dim']};
            font-size: 10px;
            font-weight: 600;
        }}

        QFrame#dialog_card {{
            background-color: {C['bg_card']};
            border: 1px solid {C['border']};
            border-radius: 9px;
        }}

        QLineEdit, QTextEdit, QPlainTextEdit {{
            background-color: {C['bg_tertiary']};
            color: {C['text']};
            border: 1px solid {C['border']};
            border-radius: 7px;
            padding: 6px 9px;
            font-size: 12px;
            selection-background-color: {accent};
            selection-color: {C['text_inverse']};
        }}

        QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
            border-color: {accent};
            background-color: {C['bg_secondary']};
        }}

        QComboBox, QSpinBox, QDoubleSpinBox {{
            background-color: {C['bg_tertiary']};
            color: {C['text']};
            border: 1px solid {C['border']};
            border-radius: 7px;
            padding: 5px 8px;
            font-size: 12px;
            min-height: 22px;
        }}

        QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover {{
            border-color: {C['border_light']};
        }}

        QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
            border-color: {accent};
            background-color: {C['bg_secondary']};
        }}

        QComboBox::drop-down {{
            border: none;
            width: 22px;
        }}

        QComboBox QAbstractItemView {{
            background-color: {C['bg_tertiary']};
            color: {C['text']};
            border: 1px solid {C['border']};
            border-radius: 7px;
            padding: 4px;
            selection-background-color: {C['bg_hover']};
            selection-color: {accent};
        }}

        QCheckBox, QRadioButton {{
            color: {C['text']};
            font-size: 12px;
            font-weight: 650;
            spacing: 6px;
            background: transparent;
        }}

        QCheckBox::indicator, QRadioButton::indicator {{
            width: 15px;
            height: 15px;
            border: 1px solid {C['border_light']};
            border-radius: 5px;
            background-color: {C['bg_tertiary']};
        }}

        QRadioButton::indicator {{
            border-radius: 8px;
        }}

        QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
            background-color: {accent};
            border-color: {accent};
        }}

        QPushButton {{
            background-color: {C['bg_tertiary']};
            color: {C['text']};
            border: 1px solid {C['border']};
            border-radius: 8px;
            padding: 7px 13px;
            font-size: 12px;
            font-weight: 800;
            min-height: 26px;
        }}

        QPushButton:hover {{
            border-color: {accent};
            background-color: {C['bg_secondary']};
        }}

        QPushButton:pressed {{
            background-color: {C['bg_hover']};
        }}

        QPushButton#compact {{
            padding: 5px 10px;
            min-height: 24px;
            font-size: 11px;
        }}

        QPushButton#accent {{
            background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #99{tint}, stop:1 #000000);
            color: {C['text_inverse']};
            border: 1px solid #99{tint};
            border-radius: 8px;
            font-weight: 900;
        }}

        QPushButton#accent:hover {{
            background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 {accent}, stop:1 #000000);
            border-color: {accent};
        }}

        QPushButton#accent:pressed {{
            background: #55{tint};
        }}

        QScrollArea {{
            background: transparent;
            border: none;
        }}

        QScrollBar:vertical {{
            background: {C['bg_secondary']};
            width: 9px;
            margin: 0;
            border-radius: 4px;
        }}

        QScrollBar::handle:vertical {{
            background: {C['border_light']};
            min-height: 24px;
            border-radius: 4px;
        }}

        QScrollBar::add-line:vertical,
        QScrollBar::sub-line:vertical {{
            height: 0px;
        }}
    """


def make_header(title: str, accent: str, icon_name: str, subtitle: str = "") -> QFrame:
    """Text-only centered dialog header. No icons; action name is the focus."""
    C = COLORS
    tint = accent.lstrip("#")

    bar = QFrame()
    bar.setObjectName("dialog_card")
    bar.setStyleSheet(
        f"QFrame#dialog_card {{ "
        f"background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #33{tint}, stop:1 {C['bg_card']}); "
        f"border: 1px solid {C['border']}; border-bottom: 2px solid {accent}; border-radius: 9px; }}"
    )

    hl = QVBoxLayout(bar)
    hl.setContentsMargins(12, 9, 12, 9)
    hl.setSpacing(1)

    t = QLabel(title.upper())
    t.setObjectName("dialog_title")
    t.setAlignment(Qt.AlignmentFlag.AlignCenter)
    t.setStyleSheet(
        f"color: {accent}; font-size: 14px; font-weight: 950; "
        "letter-spacing: 1.1px; background: transparent;"
    )
    hl.addWidget(t)

    return bar


def make_buttons(parent: QDialog, ok_text: str, accent: str, on_ok, ok_icon: str = "check"):
    """Return aligned Cancel + primary action buttons."""
    C = COLORS
    row = QHBoxLayout()
    row.setContentsMargins(0, 8, 0, 0)
    row.setSpacing(8)
    row.addStretch()

    cancel = QPushButton("Cancel")
    cancel.setFixedHeight(34)
    cancel.setStyleSheet(
        f"QPushButton {{ background-color: {C['bg_tertiary']}; color: {C['text']}; "
        f"border: 1px solid {C['border']}; border-radius: 8px; padding: 0 16px; "
        f"font-size: 12px; font-weight: 800; }}"
        f"QPushButton:hover {{ border-color: {C['border_light']}; background-color: {C['bg_secondary']}; }}"
    )
    cancel.clicked.connect(parent.reject)

    ok = QPushButton(ok_text)
    ok.setIcon(icon(ok_icon, 14, C['text_inverse']))
    ok.setIconSize(QSize(14, 14))
    ok.setFixedHeight(34)
    ok.setMinimumWidth(104)
    tint = accent.lstrip("#")
    ok.setStyleSheet(
        f"QPushButton {{ "
        f"background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #99{tint}, stop:1 #000000); "
        f"color: {C['text_inverse']}; border: 1px solid #99{tint}; "
        f"border-radius: 8px; padding: 0 18px; font-size: 12px; font-weight: 900; }}"
        f"QPushButton:hover {{ "
        f"background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 {accent}, stop:1 #000000); "
        f"border-color: {accent}; }}"
        f"QPushButton:pressed {{ background: #55{tint}; }}"
    )
    ok.clicked.connect(on_ok)

    row.addWidget(cancel)
    row.addWidget(ok)
    return row

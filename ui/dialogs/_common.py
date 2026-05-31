"""Shared helpers for MacroForge action dialogs — cohesive colorful styling."""
from PyQt6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QFrame, QVBoxLayout
from PyQt6.QtCore import Qt, QSize
from ui.theme import COLORS
from ui.icons import icon


def dialog_stylesheet(accent: str) -> str:
    C = COLORS
    return f"""
        QDialog {{ background-color: {C['bg']}; }}
        QLabel {{ color: {C['text_dim']}; font-size: 12px; background: transparent; }}
        QLineEdit {{ background-color: {C['bg_tertiary']}; color: {C['text']};
            border: 1px solid {C['border']}; border-radius: 8px; padding: 6px 10px; font-size: 12px; }}
        QLineEdit:focus {{ border-color: {accent}; }}
        QComboBox {{ background-color: {C['bg_tertiary']}; color: {C['text']};
            border: 1px solid {C['border']}; border-radius: 8px; padding: 6px 10px; }}
        QComboBox:hover {{ border-color: {accent}; }}
        QComboBox QAbstractItemView {{ background-color: {C['bg_tertiary']}; color: {C['text']};
            border: 1px solid {C['border']}; selection-background-color: {C['bg_hover']};
            selection-color: {accent}; }}
        QSpinBox, QDoubleSpinBox {{ background-color: {C['bg_tertiary']}; color: {C['text']};
            border: 1px solid {C['border']}; border-radius: 8px; padding: 6px 10px; }}
        QCheckBox {{ color: {C['text_dim']}; font-size: 12px; spacing: 6px; }}
        QCheckBox::indicator {{ width: 16px; height: 16px; border: 1px solid {C['border']};
            border-radius: 5px; background-color: {C['bg_tertiary']}; }}
        QCheckBox::indicator:checked {{ background-color: {accent}; border-color: {accent}; }}
    """


def make_header(title: str, accent: str, icon_name: str, subtitle: str = "") -> QFrame:
    """A colorful banner header with an icon, title, and optional subtitle."""
    C = COLORS
    bar = QFrame()
    bar.setStyleSheet(
        f"QFrame {{ background-color: {accent}1a; border: none;"
        f" border-left: 3px solid {accent}; border-radius: 8px; }}"
    )
    hl = QHBoxLayout(bar)
    hl.setContentsMargins(12, 8, 12, 8)
    hl.setSpacing(10)

    ic = QLabel()
    ic.setPixmap(icon(icon_name, 20, accent).pixmap(QSize(20, 20)))
    ic.setStyleSheet("background: transparent;")
    hl.addWidget(ic)

    text_col = QVBoxLayout()
    text_col.setSpacing(0)
    t = QLabel(title)
    t.setStyleSheet(f"color: {accent}; font-size: 13px; font-weight: 700; letter-spacing: 1px; background: transparent;")
    text_col.addWidget(t)
    if subtitle:
        st = QLabel(subtitle)
        st.setStyleSheet(f"color: {C['text_dim']}; font-size: 10px; background: transparent;")
        text_col.addWidget(st)
    hl.addLayout(text_col)
    hl.addStretch()
    return bar


def make_buttons(parent: QDialog, ok_text: str, accent: str, on_ok, ok_icon: str = "check"):
    """Return an HBox with a Cancel + a colorful primary button."""
    C = COLORS
    row = QHBoxLayout()
    row.addStretch()
    cancel = QPushButton("Cancel")
    cancel.setStyleSheet(
        f"background-color: {C['bg_tertiary']}; color: {C['text']}; border: 1px solid {C['border']};"
        f" border-radius: 10px; padding: 8px 18px;"
    )
    cancel.clicked.connect(parent.reject)
    ok = QPushButton(f"  {ok_text}")
    ok.setIcon(icon(ok_icon, 14, C['text_inverse']))
    ok.setIconSize(QSize(14, 14))
    ok.setStyleSheet(
        f"QPushButton {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 {accent}, stop:1 {accent}cc);"
        f" color: {C['text_inverse']}; border: none; border-radius: 10px; padding: 8px 18px; font-weight: 700; }}"
        f"QPushButton:hover {{ background: {accent}; }}"
    )
    ok.clicked.connect(on_ok)
    row.addWidget(cancel)
    row.addWidget(ok)
    return row

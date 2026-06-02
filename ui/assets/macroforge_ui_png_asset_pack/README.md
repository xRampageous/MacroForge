# MacroForge UI PNG Asset Pack

This asset pack contains PNG files for the compact dark MacroForge UI direction.

Recommended use in PyQt6:

## QIcon for buttons
```python
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import QSize

btn.setIcon(QIcon("assets/icons/24/play_white_24.png"))
btn.setIconSize(QSize(18, 18))
```

## QLabel with QPixmap
```python
from PyQt6.QtGui import QPixmap

label.setPixmap(QPixmap("assets/icons/64/keyboard_key_64.png"))
label.setScaledContents(True)
```

## PNG backgrounds via stylesheet
```python
panel.setStyleSheet("""
QFrame {
    border-image: url(assets/panels/playback_panel_500x100.png) 12 12 12 12 stretch stretch;
}
""")
```

## Custom widget paintEvent
```python
from PyQt6.QtGui import QPainter, QPixmap

class ImageButton(QWidget):
    def __init__(self):
        super().__init__()
        self.bg = QPixmap("assets/buttons/start_normal_190x44.png")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.drawPixmap(self.rect(), self.bg)
```

## Timeline notes

Use row PNGs as optional backgrounds for custom-painted timeline rows:
- timeline/row_key_compact_510x38.png
- timeline/row_click_compact_510x38.png
- timeline/row_delay_compact_510x38.png
- timeline/row_image_compact_510x38.png

Use matching progress bars:
- progress/progress_key_100_150x6.png
- progress/progress_click_100_150x6.png
- progress/progress_delay_100_150x6.png
- progress/progress_image_100_150x6.png

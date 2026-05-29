"""MacroForge - Macro Automation Tool (PyQt6 Edition).

Completely rebuilt PyQt6 UI based on v1.1.0 features.
"""
import sys
import ctypes

import pyautogui
pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0.0

from PyQt6.QtWidgets import QApplication
from debugger import logger
from ui.main_window import MainWindow


def main():
    try:
        ctypes.windll.winmm.timeBeginPeriod(1)
    except Exception:
        pass

    app = QApplication(sys.argv)
    app.setApplicationName("MacroForge")
    app.setApplicationVersion("1.2.0")
    app.setStyle("Fusion")

    logger.info("MacroForge PyQt6 starting")

    window = MainWindow()
    window.show()

    try:
        ret = app.exec()
    finally:
        try:
            ctypes.windll.winmm.timeEndPeriod(1)
        except Exception:
            pass
    sys.exit(ret)


if __name__ == "__main__":
    main()

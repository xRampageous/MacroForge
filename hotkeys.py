"""Global hotkey wrapper — fresh PyQt6 rebuild.

Uses pynput if available; otherwise hotkeys are disabled.
"""
import threading
from debugger import logger

try:
    from pynput import keyboard
    _PYNPUT = True
except Exception as e:
    logger.warning(f"pynput not available: {e}")
    _PYNPUT = False

_listener = None
_callbacks = {}


def _on_press(key):
    try:
        kn = key.name.lower()
    except AttributeError:
        try:
            kn = key.char.lower()
        except AttributeError:
            kn = str(key).lower()
    cb = _callbacks.get(kn)
    if cb:
        try:
            cb()
        except Exception as e:
            logger.error(f"hotkey callback {kn}: {e}")


def start_hotkeys(mapping: dict):
    """Start global hotkey listener.
    mapping: {key_name: callable}
    """
    global _listener, _callbacks
    stop_hotkeys()
    _callbacks = {k.lower(): v for k, v in mapping.items()}
    if not _PYNPUT:
        return
    _listener = keyboard.Listener(on_press=_on_press)
    _listener.start()
    logger.info("Global hotkeys started")


def stop_hotkeys():
    global _listener
    if _listener is not None:
        try:
            _listener.stop()
        except Exception:
            pass
        _listener = None
    logger.info("Global hotkeys stopped")

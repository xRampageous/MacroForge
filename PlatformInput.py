"""
PlatformInput — fast, accurate Windows input via SendInput.

Replaces pyautogui for key presses and mouse clicks. Uses ctypes
SendInput (user32.dll) which bypasses the message queue and avoids
pyautogui's ~10-16 ms overhead.
"""

import ctypes
from ctypes import wintypes
import time

# ── SendInput constants ──────────────────────────────────
INPUT_MOUSE    = 0
INPUT_KEYBOARD = 1
INPUT_HARDWARE = 2

# Mouse
MOUSEEVENTF_MOVE       = 0x0001
MOUSEEVENTF_LEFTDOWN   = 0x0002
MOUSEEVENTF_LEFTUP     = 0x0004
MOUSEEVENTF_RIGHTDOWN  = 0x0008
MOUSEEVENTF_RIGHTUP    = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP   = 0x0040
MOUSEEVENTF_ABSOLUTE   = 0x8000
MOUSEEVENTF_WHEEL      = 0x0800

# Keyboard
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP       = 0x0002
KEYEVENTF_SCANCODE    = 0x0008
KEYEVENTF_UNICODE     = 0x0004

# ── Structs ────────────────────────────────────────────────
class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", wintypes.LPARAM),
    ]

class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", wintypes.LPARAM),
    ]

class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]

class _INPUT_I(ctypes.Union):
    _fields_ = [
        ("mi", MOUSEINPUT),
        ("ki", KEYBDINPUT),
        ("hi", HARDWAREINPUT),
    ]

class INPUT(ctypes.Structure):
    _anonymous_ = ("ii",)
    _fields_ = [
        ("type", wintypes.DWORD),
        ("ii", _INPUT_I),
    ]

# ── Virtual key lookup ───────────────────────────────────
VK_MAP = {
    'enter': 0x0D, 'return': 0x0D, 'esc': 0x1B, 'escape': 0x1B,
    'space': 0x20, ' ': 0x20,
    'backspace': 0x08, 'tab': 0x09,
    'delete': 0x2E, 'del': 0x2E,
    'insert': 0x2D, 'ins': 0x2D,
    'home': 0x24, 'end': 0x23,
    'pageup': 0x21, 'prior': 0x21,
    'pagedown': 0x22, 'next': 0x22,
    'left': 0x25, 'up': 0x26, 'right': 0x27, 'down': 0x28,
    'shift': 0x10, 'ctrl': 0x11, 'control': 0x11,
    'alt': 0x12, 'menu': 0x12,
    'capslock': 0x14,
    'numlock': 0x90, 'scrolllock': 0x91,
    'print': 0x2A, 'printscreen': 0x2C, 'prtsc': 0x2C,
    'pause': 0x13,
    'win': 0x5B, 'command': 0x5B,
    'f1': 0x70, 'f2': 0x71, 'f3': 0x72, 'f4': 0x73,
    'f5': 0x74, 'f6': 0x75, 'f7': 0x76, 'f8': 0x77,
    'f9': 0x78, 'f10': 0x79, 'f11': 0x7A, 'f12': 0x7B,
    'num0': 0x60, 'num1': 0x61, 'num2': 0x62, 'num3': 0x63,
    'num4': 0x64, 'num5': 0x65, 'num6': 0x66, 'num7': 0x67,
    'num8': 0x68, 'num9': 0x69,
    'multiply': 0x6A, 'add': 0x6B, 'separator': 0x6C,
    'subtract': 0x6D, 'decimal': 0x6E, 'divide': 0x6F,
}

class PlatformInput:
    """Drop-in replacement for pyautogui keyDown/keyUp/click/etc."""

    def __init__(self):
        self._user32 = ctypes.windll.user32
        self._send_input = self._user32.SendInput
        self._send_input.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
        self._send_input.restype = wintypes.UINT
        self._screen_w = self._user32.GetSystemMetrics(0)
        self._screen_h = self._user32.GetSystemMetrics(1)
        self._vk_cache = {}
        self._scan_cache = {}

    # ── internal helpers ───────────────────────────────────
    def _send(self, inputs):
        n = len(inputs)
        arr = (INPUT * n)(*inputs)
        self._send_input(n, arr, ctypes.sizeof(INPUT))

    def _to_abs(self, x, y):
        """Convert screen pixels to 0-65535 absolute coords."""
        ax = int(x * 65535 / (self._screen_w - 1))
        ay = int(y * 65535 / (self._screen_h - 1))
        return ax, ay

    def _vk(self, key: str) -> int:
        """Resolve a key name or character to a virtual-key code."""
        k = key.lower().strip()
        cached = self._vk_cache.get(k)
        if cached is not None:
            return cached
        if k in VK_MAP:
            self._vk_cache[k] = VK_MAP[k]
            return VK_MAP[k]
        if len(k) == 1:
            # character → vk via VkKeyScanA
            result = self._user32.VkKeyScanA(ord(k))
            if result != -1:
                vk = result & 0xFF
                self._vk_cache[k] = vk
                return vk
        self._vk_cache[k] = None
        return None

    def _scan(self, vk: int):
        """Return (scan_code, extended_bool) for a virtual key."""
        cached = self._scan_cache.get(vk)
        if cached is not None:
            return cached
        sc = self._user32.MapVirtualKeyA(vk, 0)
        if sc == 0:
            self._scan_cache[vk] = (0, False)
            return 0, False
        if sc > 0xFF:
            result = (sc & 0xFF, True)
            self._scan_cache[vk] = result
            return result
        # Extended keys that MapVirtualKeyA doesn't flag properly
        ext_vks = {
            0x25, 0x26, 0x27, 0x28,   # arrows
            0x21, 0x22, 0x23, 0x24,   # pgup/pgdn/home/end
            0x2D, 0x2E,                 # insert/delete
            0x5B, 0x5C,                 # win keys
            0x6D, 0x6E,                 # numpad - / .
        }
        result = (sc, vk in ext_vks)
        self._scan_cache[vk] = result
        return result

    def _mouse_input(self, dx, dy, flags, data=0):
        return INPUT(
            type=INPUT_MOUSE,
            ii=_INPUT_I(mi=MOUSEINPUT(
                dx=dx, dy=dy, mouseData=data,
                dwFlags=flags, time=0, dwExtraInfo=0
            ))
        )

    def _key_input(self, scan, flags=0):
        return INPUT(
            type=INPUT_KEYBOARD,
            ii=_INPUT_I(ki=KEYBDINPUT(
                wVk=0, wScan=scan,
                dwFlags=KEYEVENTF_SCANCODE | flags,
                time=0, dwExtraInfo=0
            ))
        )

    # ── public mouse API ─────────────────────────────────
    def position(self):
        """Return current cursor position as (x, y)."""
        pt = wintypes.POINT()
        self._user32.GetCursorPos(ctypes.byref(pt))
        return pt.x, pt.y

    def move_to(self, x, y):
        """Move cursor to absolute screen coordinates."""
        ax, ay = self._to_abs(x, y)
        self._send([self._mouse_input(ax, ay, MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE)])

    def click(self, x=None, y=None, button='left'):
        """Move (optional) then click."""
        if x is not None and y is not None:
            self.move_to(x, y)
            time.sleep(0.005)  # tiny settle so OS registers position
        if button == 'right':
            down = MOUSEEVENTF_RIGHTDOWN
            up   = MOUSEEVENTF_RIGHTUP
        elif button == 'middle':
            down = MOUSEEVENTF_MIDDLEDOWN
            up   = MOUSEEVENTF_MIDDLEUP
        else:
            down = MOUSEEVENTF_LEFTDOWN
            up   = MOUSEEVENTF_LEFTUP
        self._send([
            self._mouse_input(0, 0, down),
            self._mouse_input(0, 0, up),
        ])

    def double_click(self, x=None, y=None, button='left'):
        """Two rapid clicks."""
        self.click(x, y, button)
        time.sleep(0.01)
        self.click(None, None, button)

    def right_click(self, x=None, y=None):
        self.click(x, y, button='right')

    def middle_click(self, x=None, y=None):
        self.click(x, y, button='middle')

    def mouse_down(self, button='left'):
        """Hold a mouse button down (must pair with mouse_up)."""
        if button == 'right':
            flag = MOUSEEVENTF_RIGHTDOWN
        elif button == 'middle':
            flag = MOUSEEVENTF_MIDDLEDOWN
        else:
            flag = MOUSEEVENTF_LEFTDOWN
        self._send([self._mouse_input(0, 0, flag)])

    def mouse_up(self, button='left'):
        """Release a mouse button."""
        if button == 'right':
            flag = MOUSEEVENTF_RIGHTUP
        elif button == 'middle':
            flag = MOUSEEVENTF_MIDDLEUP
        else:
            flag = MOUSEEVENTF_LEFTUP
        self._send([self._mouse_input(0, 0, flag)])

    # ── public keyboard API ──────────────────────────────
    def key_down(self, key: str):
        """Hold a key down (must pair with key_up)."""
        vk = self._vk(key)
        if vk is None:
            return
        scan, ext = self._scan(vk)
        flags = KEYEVENTF_EXTENDEDKEY if ext else 0
        self._send([self._key_input(scan, flags)])

    def key_up(self, key: str):
        """Release a key."""
        vk = self._vk(key)
        if vk is None:
            return
        scan, ext = self._scan(vk)
        flags = KEYEVENTF_KEYUP | (KEYEVENTF_EXTENDEDKEY if ext else 0)
        self._send([self._key_input(scan, flags)])

    def press(self, key: str):
        """Quick tap (down + up)."""
        self.key_down(key)
        time.sleep(0.005)
        self.key_up(key)

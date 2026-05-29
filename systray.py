"""
systray.py – Windows system tray using raw ctypes.
Does NOT depend on pystray, win32gui, or ctypes.wintypes.
"""

import ctypes
import io
import os
import random
import tempfile
import threading
from PIL import Image
from debugger import logger

# ── Windows constants ──
WM_APP = 0x8000
WM_TRAY_MESSAGE = WM_APP + 1
WM_COMMAND = 0x0111
WM_LBUTTONUP = 0x0202
WM_RBUTTONUP = 0x0205
WM_DESTROY = 0x0002
NIM_ADD = 0
NIM_MODIFY = 1
NIM_DELETE = 2
NIF_ICON = 2
NIF_MESSAGE = 1
NIF_TIP = 4
MF_STRING = 0x00000000
TPM_RIGHTALIGN = 0x0008
TPM_BOTTOMALIGN = 0x0020
TPM_RETURNCMD = 0x0100
WM_HOTKEY = 0x0312

# Virtual-key codes for function keys
VK_ESCAPE = 0x1B
VK_F5 = 0x74
VK_F6 = 0x75
VK_F7 = 0x76
VK_F9 = 0x78

# ── ctypes structures (raw, no wintypes dependency) ──
class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

class MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", ctypes.c_void_p),
        ("message", ctypes.c_uint),
        ("wParam", ctypes.c_size_t),
        ("lParam", ctypes.c_ssize_t),
        ("time", ctypes.c_ulong),
        ("pt", POINT),
    ]

class WNDCLASSW(ctypes.Structure):
    _fields_ = [
        ("style", ctypes.c_uint),
        ("lpfnWndProc", ctypes.c_void_p),   # set from WNDPROC callable
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", ctypes.c_void_p),
        ("hIcon", ctypes.c_void_p),
        ("hCursor", ctypes.c_void_p),
        ("hbrBackground", ctypes.c_void_p),
        ("lpszMenuName", ctypes.c_wchar_p),
        ("lpszClassName", ctypes.c_wchar_p),
    ]

class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_uint),
        ("hWnd", ctypes.c_void_p),
        ("uID", ctypes.c_uint),
        ("uFlags", ctypes.c_uint),
        ("uCallbackMessage", ctypes.c_uint),
        ("hIcon", ctypes.c_void_p),
        ("szTip", ctypes.c_wchar * 128),
        ("dwState", ctypes.c_uint),
        ("dwStateMask", ctypes.c_uint),
        ("szInfo", ctypes.c_wchar * 256),
        ("uTimeout", ctypes.c_uint),
        ("szInfoTitle", ctypes.c_wchar * 64),
        ("dwInfoFlags", ctypes.c_uint),
        ("guidItem", ctypes.c_ubyte * 16),
        ("hBalloonIcon", ctypes.c_void_p),
    ]

# ── WNDPROC callback type ──
WNDPROC_TYPE = ctypes.WINFUNCTYPE(
    ctypes.c_ssize_t,
    ctypes.c_void_p, ctypes.c_uint,
    ctypes.c_size_t, ctypes.c_ssize_t
)

# ── Windows API shortcuts ──
_user32 = ctypes.windll.user32
_shell32 = ctypes.windll.shell32
_kernel32 = ctypes.windll.kernel32

_user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASSW)]
_user32.RegisterClassW.restype = ctypes.c_ushort

_user32.CreateWindowExW.argtypes = [
    ctypes.c_uint, ctypes.c_wchar_p, ctypes.c_wchar_p,
    ctypes.c_uint, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p
]
_user32.CreateWindowExW.restype = ctypes.c_void_p

_user32.DefWindowProcW.argtypes = [
    ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t
]
_user32.DefWindowProcW.restype = ctypes.c_ssize_t

_user32.PostMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t]
_user32.PostMessageW.restype = ctypes.c_bool

_user32.PostQuitMessage.argtypes = [ctypes.c_int]
_user32.GetMessageW.argtypes = [ctypes.POINTER(MSG), ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint]
_user32.GetMessageW.restype = ctypes.c_int

_user32.TrackPopupMenu.argtypes = [
    ctypes.c_void_p, ctypes.c_uint, ctypes.c_int, ctypes.c_int,
    ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p
]
_user32.TrackPopupMenu.restype = ctypes.c_int

_shell32.Shell_NotifyIconW.argtypes = [ctypes.c_uint, ctypes.POINTER(NOTIFYICONDATAW)]
_shell32.Shell_NotifyIconW.restype = ctypes.c_bool

_user32.RegisterHotKey.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_uint, ctypes.c_uint]
_user32.RegisterHotKey.restype = ctypes.c_bool

_user32.UnregisterHotKey.argtypes = [ctypes.c_void_p, ctypes.c_int]
_user32.UnregisterHotKey.restype = ctypes.c_bool


# Hotkey IDs dispatched to app methods
_HOTKEY_MAP = {
    100: "_hotkey_start",    # F5
    101: "_hotkey_stop",     # F6
    102: "_hotkey_record",   # F7
    103: "_hotkey_toggle",   # F9
    104: "_on_escape",       # Escape
}

class TrayIcon:
    """Windows system tray icon with left-click restore and right-click menu."""

    def __init__(self, app, tooltip="MacroForge"):
        self.app = app
        self.tooltip = tooltip
        self._hwnd = None
        self._hicon = None
        self._thread = None
        self._running = False
        self._class_name = None
        self._wndproc_ref = None          # keep callback alive
        self._hmenu = None

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._message_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._hwnd:
            try:
                _user32.PostMessageW(self._hwnd, WM_DESTROY, 0, 0)
            except Exception:
                pass

    # ── internals ──

    def _message_loop(self):
        # unique class name
        self._class_name = f"MacroForgeTray_{random.randint(10000, 99999)}"

        # create & keep reference to callback so GC doesn't kill it
        self._wndproc_ref = WNDPROC_TYPE(self._wnd_proc)

        wc = WNDCLASSW()
        wc.style = 0
        wc.lpfnWndProc = ctypes.cast(self._wndproc_ref, ctypes.c_void_p).value
        wc.cbClsExtra = 0
        wc.cbWndExtra = 0
        wc.hInstance = _kernel32.GetModuleHandleW(None)
        wc.hIcon = 0
        wc.hCursor = 0
        wc.hbrBackground = 0
        wc.lpszMenuName = None
        wc.lpszClassName = self._class_name

        atom = _user32.RegisterClassW(ctypes.byref(wc))
        if not atom:
            return

        # hidden message-only window
        self._hwnd = _user32.CreateWindowExW(
            0, self._class_name, "MacroForgeTray",
            0, 0, 0, 0, 0,
            ctypes.c_void_p(-3),   # HWND_MESSAGE
            None, wc.hInstance, None
        )
        if not self._hwnd:
            return

        # icon
        self._hicon = self._create_icon()

        # register native Windows global hotkeys on this hidden window
        _user32.RegisterHotKey(self._hwnd, 100, 0, VK_F5)
        _user32.RegisterHotKey(self._hwnd, 101, 0, VK_F6)
        _user32.RegisterHotKey(self._hwnd, 102, 0, VK_F7)
        _user32.RegisterHotKey(self._hwnd, 103, 0, VK_F9)
        _user32.RegisterHotKey(self._hwnd, 104, 0, VK_ESCAPE)
        logger.info("Tray window created; hotkeys registered (F5/F6/F7/F9/Esc)")

        # notify icon
        nid = self._make_nid()
        ok = _shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid))
        if not ok:
            logger.error("Shell_NotifyIconW failed — tray icon not shown")
            return

        # pump messages
        msg = MSG()
        while self._running:
            ret = _user32.GetMessageW(ctypes.byref(msg), self._hwnd, 0, 0)
            if ret in (0, -1):
                break
            _user32.TranslateMessage(ctypes.byref(msg))
            _user32.DispatchMessageW(ctypes.byref(msg))

        # teardown
        _shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(nid))
        for hid in _HOTKEY_MAP:
            _user32.UnregisterHotKey(self._hwnd, hid)
        if self._hicon:
            _user32.DestroyIcon(self._hicon)
        _user32.DestroyWindow(self._hwnd)
        _user32.UnregisterClassW(self._class_name, wc.hInstance)
        logger.info("Tray icon stopped and hotkeys unregistered")

    def _wnd_proc(self, hwnd, msg, wparam, lparam):
        if msg == WM_TRAY_MESSAGE:
            if lparam == WM_LBUTTONUP:
                self._schedule(self._show_window)
            elif lparam == WM_RBUTTONUP:
                self._schedule(self._show_menu)
        elif msg == WM_HOTKEY:
            hid = wparam
            method = _HOTKEY_MAP.get(hid)
            if method:
                logger.debug(f"WM_HOTKEY received: id={hid} -> {method}")
                self._schedule(lambda m=method: getattr(self.app, m, lambda: None)())
        elif msg == WM_COMMAND:
            self._on_menu_command(wparam)
        elif msg == WM_DESTROY:
            _user32.PostQuitMessage(0)
        return _user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _make_nid(self):
        nid = NOTIFYICONDATAW()
        nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        nid.hWnd = self._hwnd
        nid.uID = 1
        nid.uFlags = NIF_MESSAGE | NIF_TIP
        if self._hicon:
            nid.uFlags |= NIF_ICON
        nid.uCallbackMessage = WM_TRAY_MESSAGE
        nid.hIcon = self._hicon or 0
        nid.szTip = self.tooltip
        return nid

    def _create_icon(self):
        """Load MacroForge.ico for the system tray."""
        size = 16
        try:
            ico_path = os.path.abspath("MacroForge.ico")
            if os.path.exists(ico_path):
                hicon = _user32.LoadImageW(
                    None, ico_path, 1, 0, 0, 0x00000010
                )
                return hicon or None
        except Exception:
            pass
        # Fallback: green square
        try:
            img = Image.new("RGBA", (size, size), (32, 184, 126, 255))
            ico = io.BytesIO()
            img.save(ico, format="ICO", sizes=[(size, size)])
            ico.seek(0)
            with tempfile.NamedTemporaryFile(suffix=".ico", delete=False) as f:
                f.write(ico.read())
                tmp = f.name
            try:
                hicon = _user32.LoadImageW(
                    None, tmp, 1, size, size, 0x00000010
                )
            finally:
                os.unlink(tmp)
            return hicon or None
        except Exception:
            return None

    def _schedule(self, fn):
        try:
            self.app.root.after(0, fn)
        except Exception:
            pass

    def _show_window(self):
        root = self.app.root
        root.deiconify()
        root.lift()
        root.attributes("-topmost", True)
        root.after(200, lambda: root.attributes("-topmost", False))
        root.focus_force()

    def _show_menu(self):
        hmenu = _user32.CreatePopupMenu()
        self._append_menu(hmenu, 1, "Show MacroForge")
        self._append_menu(hmenu, 2, "Start")
        self._append_menu(hmenu, 3, "Stop")

        pt = POINT()
        _user32.GetCursorPos(ctypes.byref(pt))
        cmd = _user32.TrackPopupMenu(
            hmenu,
            TPM_RIGHTALIGN | TPM_BOTTOMALIGN | TPM_RETURNCMD,
            pt.x, pt.y, 0, self._hwnd, None
        )
        _user32.DestroyMenu(hmenu)
        self._on_menu_command(cmd)

    def _append_menu(self, hmenu, item_id, text):
        _user32.AppendMenuW(hmenu, MF_STRING, item_id, text)

    def _on_menu_command(self, cmd):
        if cmd == 1:
            self._schedule(self._show_window)
        elif cmd == 2:
            self._schedule(self.app.start)
        elif cmd == 3:
            self._schedule(self.app.stop)

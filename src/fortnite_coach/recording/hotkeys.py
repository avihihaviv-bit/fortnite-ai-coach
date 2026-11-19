"""Global hotkeys via the Windows RegisterHotKey API.

RegisterHotKey is the standard OS mechanism used by recording tools such as OBS.
It does not hook the keyboard, read game memory or interact with Fortnite in any
way: Windows simply posts a WM_HOTKEY message to this app when the combination
is pressed. On other operating systems hotkeys are reported as unavailable.
"""

from __future__ import annotations

import sys
from collections.abc import Callable

MODIFIERS = {"ctrl": 0x0002, "control": 0x0002, "alt": 0x0001, "shift": 0x0004, "win": 0x0008}
MOD_NOREPEAT = 0x4000
WM_HOTKEY = 0x0312

_NAMED_KEYS = {
    **{f"f{i}": 0x6F + i for i in range(1, 25)},  # F1=0x70
    "home": 0x24, "end": 0x23, "insert": 0x2D, "delete": 0x2E, "pageup": 0x21, "pagedown": 0x22,
    "pause": 0x13, "scrolllock": 0x91,
}


class HotkeyError(ValueError):
    pass


def parse_hotkey(text: str) -> tuple[int, int]:
    """'Ctrl+Shift+F9' -> (modifiers, virtual-key code). Requires at least one modifier
    so a hotkey never steals a plain game key."""
    parts = [p.strip().lower() for p in text.split("+") if p.strip()]
    if len(parts) < 2:
        raise HotkeyError("needs a modifier and a key")
    mods, key = 0, parts[-1]
    for p in parts[:-1]:
        if p not in MODIFIERS:
            raise HotkeyError(f"unknown modifier {p}")
        mods |= MODIFIERS[p]
    if key in _NAMED_KEYS:
        vk = _NAMED_KEYS[key]
    elif len(key) == 1 and key.isalnum():
        vk = ord(key.upper())
    else:
        raise HotkeyError(f"unknown key {key}")
    return mods, vk


def is_supported() -> bool:
    return sys.platform == "win32"


if sys.platform == "win32":  # pragma: no cover - exercised only on Windows
    import ctypes
    from ctypes import wintypes

    from PySide6.QtCore import QAbstractNativeEventFilter

    _user32 = ctypes.windll.user32

    class _Filter(QAbstractNativeEventFilter):
        def __init__(self, callbacks: dict[int, Callable[[], None]]):
            super().__init__()
            self.callbacks = callbacks

        def nativeEventFilter(self, event_type, message):
            if bytes(event_type) == b"windows_generic_MSG":
                msg = wintypes.MSG.from_address(int(message))
                if msg.message == WM_HOTKEY and msg.wParam in self.callbacks:
                    self.callbacks[msg.wParam]()
                    return True, 0
            return False, 0


class HotkeyManager:
    """Registers app-wide hotkeys. register() returns False if Windows refused
    (e.g. the combination is already used by another program)."""

    def __init__(self, app, hwnd_provider=None) -> None:
        self.app = app
        # Bind hotkeys to the main window handle: WM_HOTKEY is then delivered through that window's
        # message queue, which Qt passes to native event filters (also while hidden in the tray).
        self._hwnd = hwnd_provider
        self._callbacks: dict[int, Callable[[], None]] = {}
        self._next_id = 1
        self._filter = None

    def register(self, text: str, callback: Callable[[], None]) -> bool:
        if not is_supported():
            return False
        mods, vk = parse_hotkey(text)
        hk_id = self._next_id
        hwnd = self._hwnd() if self._hwnd else None
        if not _user32.RegisterHotKey(hwnd, hk_id, mods | MOD_NOREPEAT, vk):  # pragma: no cover
            return False
        self._next_id += 1  # pragma: no cover
        self._callbacks[hk_id] = callback  # pragma: no cover
        if self._filter is None:  # pragma: no cover
            self._filter = _Filter(self._callbacks)
            self.app.installNativeEventFilter(self._filter)
        return True  # pragma: no cover

    def unregister_all(self) -> None:
        if is_supported():  # pragma: no cover
            hwnd = self._hwnd() if self._hwnd else None
            for hk_id in list(self._callbacks):
                _user32.UnregisterHotKey(hwnd, hk_id)
        self._callbacks.clear()

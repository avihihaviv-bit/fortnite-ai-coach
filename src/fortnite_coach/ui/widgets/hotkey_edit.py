"""A text box that records a key combination: click it and press e.g. Ctrl+Shift+F9."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QLineEdit

_MOD_KEYS = {Qt.Key.Key_Control, Qt.Key.Key_Shift, Qt.Key.Key_Alt, Qt.Key.Key_Meta, Qt.Key.Key_AltGr}
_NAMES = {Qt.Key.Key_Home: "Home", Qt.Key.Key_End: "End", Qt.Key.Key_Insert: "Insert", Qt.Key.Key_Delete: "Delete",
          Qt.Key.Key_PageUp: "PageUp", Qt.Key.Key_PageDown: "PageDown", Qt.Key.Key_Pause: "Pause",
          Qt.Key.Key_ScrollLock: "ScrollLock"}


def combo_text(key: int, mods) -> str | None:
    """Qt key + modifiers -> 'Ctrl+Shift+F9' (the format parse_hotkey reads), or None if not usable."""
    if key in _MOD_KEYS:
        return None
    if Qt.Key.Key_F1 <= key <= Qt.Key.Key_F24:
        name = f"F{key - Qt.Key.Key_F1 + 1}"
    elif Qt.Key.Key_A <= key <= Qt.Key.Key_Z or Qt.Key.Key_0 <= key <= Qt.Key.Key_9:
        name = chr(key)
    elif key in _NAMES:
        name = _NAMES[key]
    else:
        return None
    parts = []
    if mods & Qt.KeyboardModifier.ControlModifier:
        parts.append("Ctrl")
    if mods & Qt.KeyboardModifier.AltModifier:
        parts.append("Alt")
    if mods & Qt.KeyboardModifier.ShiftModifier:
        parts.append("Shift")
    if not parts:
        return None  # a plain key would steal a game key
    return "+".join([*parts, name])


class HotkeyEdit(QLineEdit):
    def keyPressEvent(self, e: QKeyEvent) -> None:
        if e.key() in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab):
            return super().keyPressEvent(e)
        text = combo_text(e.key(), e.modifiers())
        if text:
            self.setText(text)
        e.accept()

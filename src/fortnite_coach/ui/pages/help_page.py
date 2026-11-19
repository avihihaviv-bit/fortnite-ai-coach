"""How to use the app: step by step + answers to common problems (bilingual, static text)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QWidget

from fortnite_coach.i18n.translator import get_translator, tr
from fortnite_coach.ui.pages.base import BasePage
from fortnite_coach.ui.widgets.card import Card

SECTIONS = ("flow", "before", "after", "report", "levels", "faq")


class HelpPage(BasePage):
    page_key = "help"

    def __init__(self, ctx=None, parent: QWidget | None = None):
        super().__init__(parent)
        self.ctx = ctx
        self.cards: list[tuple[Card, QLabel, str]] = []
        for key in SECTIONS:
            card = Card()
            body = QLabel()
            body.setWordWrap(True)
            body.setTextFormat(Qt.TextFormat.RichText)
            body.setOpenExternalLinks(True)
            card.body.addWidget(body)
            self.content.addWidget(card)
            self.cards.append((card, body, key))
        self.finish()

    def retranslate(self) -> None:
        super().retranslate()
        hk = ("Ctrl+Shift+F9", "Ctrl+Shift+F10")
        if self.ctx is not None:
            r = self.ctx.settings().recording
            hk = (r.hotkey_start, r.hotkey_stop)
        rtl = get_translator().is_rtl
        for card, body, key in self.cards:
            card.set_title(tr(f"help.{key}.title"))
            html = tr(f"help.{key}.body", start=hk[0], stop=hk[1])
            # one paragraph per line with an explicit base direction, so a line that starts with a
            # Latin word (XP, Gemini) is still laid out right-to-left in Hebrew
            d, a = ("rtl", "right") if rtl else ("ltr", "left")
            paras = "".join(f"<p dir='{d}' align='{a}' style='margin:0 0 4px 0'>{line}</p>" for line in html.split("<br>"))
            body.setText(paras)
            body.setAlignment(Qt.AlignmentFlag.AlignRight if rtl else Qt.AlignmentFlag.AlignLeft)

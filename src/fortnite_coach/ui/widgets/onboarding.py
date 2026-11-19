"""'Getting started' checklist on the dashboard. Each step is checked from real state, never assumed."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import QGridLayout, QLabel, QPushButton

from fortnite_coach.ai.status import GeminiStatus
from fortnite_coach.db.repositories import plan_repo, session_repo
from fortnite_coach.i18n.translator import tr
from fortnite_coach.ui.widgets.card import Card

# (step id, page to open)
STEPS = (("key", "settings"), ("test", "settings"), ("hardware", "settings"), ("video", "gameplay"),
         ("analysis", "gameplay"), ("exercise", "training_plan"))


class OnboardingCard(Card):
    def __init__(self, ctx, navigate: Callable[[str], None]):
        super().__init__()
        self.setObjectName("Card")
        self.ctx = ctx
        self.grid = QGridLayout()
        self.grid.setHorizontalSpacing(12)
        self.grid.setVerticalSpacing(8)
        self.rows: dict[str, tuple[QLabel, QLabel, QPushButton]] = {}
        for i, (step, page) in enumerate(STEPS):
            mark, text = QLabel(objectName="Timestamp"), QLabel()
            text.setWordWrap(True)
            btn = QPushButton()
            btn.clicked.connect(lambda _=False, p=page: navigate(p))
            self.grid.addWidget(mark, i, 0)
            self.grid.addWidget(text, i, 1)
            self.grid.addWidget(btn, i, 2)
            self.rows[step] = (mark, text, btn)
        self.grid.setColumnStretch(1, 1)
        self.body.addLayout(self.grid)
        self.done: dict[str, bool] = {}

    def state(self) -> dict[str, bool]:
        counts = session_repo.counts(self.ctx.db)
        return {
            "key": self.ctx.key_store.has_key(),
            "test": self.ctx.gemini_status() is GeminiStatus.CONNECTED,
            "hardware": self.ctx.settings().hardware_checked,
            "video": counts["videos"] > 0,
            "analysis": counts["reports"] > 0,
            "exercise": plan_repo.totals(self.ctx.db).completions > 0,
        }

    def render(self) -> None:
        self.done = self.state()
        n = sum(self.done.values())
        self.set_title(tr("onboard.title", done=n, total=len(STEPS)), tr("onboard.subtitle"))
        first_open = True
        for step, (mark, text, btn) in self.rows.items():
            ok = self.done[step]
            mark.setText("✓" if ok else "○")
            text.setText(tr(f"onboard.{step}"))
            text.setEnabled(not ok)
            btn.setText(tr("onboard.go"))
            btn.setObjectName("PrimaryButton" if (not ok and first_open) else "")
            btn.style().unpolish(btn)
            btn.style().polish(btn)
            btn.setVisible(not ok)
            if not ok:
                first_open = False
        self.setVisible(n < len(STEPS))  # disappears once everything was done

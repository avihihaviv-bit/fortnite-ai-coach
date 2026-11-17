from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QProgressBar, QVBoxLayout, QWidget

from fortnite_coach.coaching.levels import LevelInfo, level_from_xp
from fortnite_coach.i18n.translator import tr


class LevelBar(QWidget):
    """'Level 4 · Gold' + XP progress bar. Level 1 / 0 XP when there is no data (nothing fake)."""

    def __init__(self, big: bool = False, parent: QWidget | None = None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        top = QHBoxLayout()
        self.level_label = QLabel(objectName="LevelBig" if big else "LevelSmall")
        self.tier_label = QLabel(objectName="TierBadge")
        top.addWidget(self.level_label)
        top.addWidget(self.tier_label, 0, Qt.AlignmentFlag.AlignVCenter)
        top.addStretch(1)
        self.bar = QProgressBar(objectName="XpBar")
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(10 if big else 8)
        self.xp_label = QLabel(objectName="StatHint")
        self.xp_label.setWordWrap(True)
        self.big = big
        lay.addLayout(top)
        lay.addWidget(self.bar)
        lay.addWidget(self.xp_label)
        self.info = level_from_xp(0)

    def set_level(self, info: LevelInfo | None) -> None:
        self.info = info or level_from_xp(0)
        i = self.info
        self.level_label.setText(tr("level.level", n=i.level))
        self.tier_label.setText(tr(f"tier.{i.tier}"))
        self.tier_label.setProperty("tier", i.tier)
        self.tier_label.style().unpolish(self.tier_label)
        self.tier_label.style().polish(self.tier_label)
        self.bar.setRange(0, i.xp_for_next)
        self.bar.setValue(i.xp_into_level)
        if self.big:
            self.xp_label.setText(tr("level.xp", into=i.xp_into_level, need=i.xp_for_next, total=i.total_xp)
                                  if i.total_xp else tr("level.no_xp"))
        else:  # compact: fits narrow columns
            self.xp_label.setText(f"{i.xp_into_level} / {i.xp_for_next} XP")

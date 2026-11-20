from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from fortnite_coach.coaching.prompt_builder import fmt_ts


class FindingCard(QFrame):
    """One timestamped finding: evidence frame on the side, text blocks on the other."""

    def __init__(self, kind: str, title: str, timestamp_s: float | None, rows: list[tuple[str, str]],
                 badge: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("FindingGood" if kind == "good" else "FindingMistake")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(14)
        self.frame = QLabel()
        self.frame.setFixedSize(192, 108)
        self.frame.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.frame.setObjectName("EvidenceFrame")
        lay.addWidget(self.frame, 0, Qt.AlignmentFlag.AlignTop)
        body = QVBoxLayout()
        body.setSpacing(4)
        head = QHBoxLayout()
        self.ts_label = QLabel(fmt_ts(timestamp_s) if timestamp_s is not None else "--:--", objectName="Timestamp")
        self.title = QLabel(title, objectName="FindingTitle")
        self.title.setWordWrap(True)
        head.addWidget(self.ts_label)
        head.addWidget(self.title, 1)
        if badge:
            head.addWidget(QLabel(badge, objectName="XpBadge" if kind == "good" else "SeverityBadge"))
        body.addLayout(head)
        for label, text in rows:
            if not text:
                continue
            lbl = QLabel(f"<b>{label}</b>  {text}")
            lbl.setWordWrap(True)
            lbl.setTextFormat(Qt.TextFormat.RichText)
            lbl.setOpenExternalLinks(True)
            body.addWidget(lbl)
        lay.addLayout(body, 1)

    def set_frame(self, path: Path | None) -> None:
        pm = QPixmap(str(path)) if path else QPixmap()
        if not pm.isNull():
            self.frame.setPixmap(pm.scaled(self.frame.size(), Qt.AspectRatioMode.KeepAspectRatio,
                                           Qt.TransformationMode.SmoothTransformation))

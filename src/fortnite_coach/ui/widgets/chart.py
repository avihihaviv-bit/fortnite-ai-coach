"""Small single-series charts (QtCharts) styled for the dark theme.

Rules (dataviz method): one series per chart, one y-axis, thin 2px line, >= 8px markers,
recessive grid, text in text colors (never the series color), hover tooltip on every point.
"""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCharts import QChart, QChartView, QDateTimeAxis, QLineSeries, QScatterSeries, QValueAxis
from PySide6.QtCore import QDateTime, QMargins, QPointF, Qt
from PySide6.QtGui import QBrush, QColor, QCursor, QPainter, QPen
from PySide6.QtWidgets import QToolTip

from fortnite_coach.ui.theme import Colors

# Validated against the dark chart surface #1A1C22 (dataviz validate_palette.js: all checks PASS).
SERIES_PURPLE = "#8B5CF6"
SERIES_GREEN = "#16A34A"


class LineChart(QChartView):
    def __init__(self, color: str = SERIES_PURPLE, y_range: tuple[float, float] | None = (0, 100), parent=None):
        self._chart = QChart()
        super().__init__(self._chart, parent)
        self.color, self.y_range = color, y_range
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setMinimumHeight(240)
        self.setStyleSheet("background: transparent;")
        c = self._chart
        c.setBackgroundVisible(False)
        c.setPlotAreaBackgroundVisible(False)
        c.legend().hide()  # single series: the card title names it
        c.setMargins(QMargins(4, 4, 4, 4))
        self.points: list[tuple[datetime, float, str]] = []

    def set_points(self, points: list[tuple[datetime, float, str]], y_label_fmt: str = "%d") -> None:
        """points: (time, value, tooltip text)."""
        self.points = points
        c = self._chart
        c.removeAllSeries()
        for ax in list(c.axes()):
            c.removeAxis(ax)
        if not points:
            return
        line, dots = QLineSeries(), QScatterSeries()
        pen = QPen(QColor(self.color))
        pen.setWidthF(2.0)
        line.setPen(pen)
        dots.setMarkerSize(9)
        dots.setColor(QColor(self.color))
        dots.setBorderColor(QColor(Colors.PANEL))  # 2px surface ring
        for t, v, _ in points:
            ms = QDateTime(t).toMSecsSinceEpoch()
            line.append(ms, v)
            dots.append(ms, v)
        c.addSeries(line)
        c.addSeries(dots)
        x = QDateTimeAxis()
        x.setFormat("dd/MM")
        x.setTickCount(min(6, max(2, len(points))))
        y = QValueAxis()
        if self.y_range:
            y.setRange(*self.y_range)
        else:
            top = max(v for _, v, _ in points)
            y.setRange(0, max(1.0, top * 1.15))
        y.setLabelFormat(y_label_fmt)
        y.setTickCount(5)
        for ax in (x, y):
            ax.setLabelsColor(QColor(Colors.TEXT_MUTED))
            ax.setGridLineColor(QColor(Colors.BORDER))
            ax.setLinePenColor(QColor(Colors.BORDER))
        if len(points) == 1:  # a single point still needs a visible time span
            ms = QDateTime(points[0][0]).toMSecsSinceEpoch()
            x.setRange(QDateTime.fromMSecsSinceEpoch(ms - 86_400_000), QDateTime.fromMSecsSinceEpoch(ms + 86_400_000))
        c.addAxis(x, Qt.AlignmentFlag.AlignBottom)
        c.addAxis(y, Qt.AlignmentFlag.AlignLeft)
        for s in (line, dots):
            s.attachAxis(x)
            s.attachAxis(y)
        dots.hovered.connect(self._hover)

    def _hover(self, point: QPointF, state: bool) -> None:
        if not state:
            QToolTip.hideText()
            return
        best = min(self.points, key=lambda p: abs(QDateTime(p[0]).toMSecsSinceEpoch() - point.x()) + abs(p[1] - point.y()))
        QToolTip.showText(QCursor.pos(), best[2], self)

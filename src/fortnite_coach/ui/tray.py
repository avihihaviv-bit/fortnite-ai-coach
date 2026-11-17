"""System tray icon: the app keeps running next to the clock so recording hotkeys work while you play."""

from __future__ import annotations

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from fortnite_coach.config.paths import resource_path
from fortnite_coach.i18n.translator import tr


def _icon(recording: bool) -> QIcon:
    pm = QPixmap(str(resource_path("assets/app.png")))
    if pm.isNull():
        pm = QPixmap(64, 64)
        pm.fill(QColor("#8B5CF6"))
    if recording:  # red dot = recording
        pm = pm.scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QColor("#EF4444"))
        p.setPen(QColor("#FFFFFF"))
        p.drawEllipse(36, 36, 26, 26)
        p.end()
    return QIcon(pm)


class TrayController(QObject):
    open_requested = Signal()
    quit_requested = Signal()

    def __init__(self, recording_controller, parent=None):
        super().__init__(parent)
        self.rc = recording_controller
        self.available = QSystemTrayIcon.isSystemTrayAvailable()
        self.tray = QSystemTrayIcon(_icon(False), self)
        menu = QMenu()
        self.a_open = QAction(menu)
        self.a_start = QAction(menu)
        self.a_stop = QAction(menu)
        self.a_quit = QAction(menu)
        self.a_open.triggered.connect(self.open_requested)
        self.a_start.triggered.connect(self.rc.start)
        self.a_stop.triggered.connect(self.rc.stop)
        self.a_quit.triggered.connect(self.quit_requested)
        for a in (self.a_open, self.a_start, self.a_stop):
            menu.addAction(a)
        menu.addSeparator()
        menu.addAction(self.a_quit)
        self.menu = menu
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._activated)
        self.rc.state_changed.connect(lambda _s: self.render())
        self.told_about_tray = False
        self.render()
        if self.available:
            self.tray.show()

    def _activated(self, reason) -> None:
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            self.open_requested.emit()

    def render(self) -> None:
        rec = self.rc.is_recording
        self.tray.setIcon(_icon(rec))
        self.tray.setToolTip(tr("tray.tip_recording") if rec else tr("app.title"))
        self.a_open.setText(tr("tray.open"))
        self.a_start.setText(tr("rec.start"))
        self.a_stop.setText(tr("rec.stop"))
        self.a_quit.setText(tr("tray.quit"))
        self.a_start.setEnabled(not rec)
        self.a_stop.setEnabled(rec)

    def notify(self, text: str) -> None:
        if self.available:
            self.tray.showMessage(tr("app.title"), text, QSystemTrayIcon.MessageIcon.Information, 5000)

    def hide(self) -> None:
        self.tray.hide()

"""Only one running copy: a second launch asks the first window to come to the front.

Prevents two processes writing the same database and registering the same hotkeys.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket

from fortnite_coach import APP_ID


def server_name(suffix: str = "") -> str:
    import getpass

    try:
        user = getpass.getuser()
    except Exception:  # pragma: no cover
        user = "user"
    return f"{APP_ID}-{user}{suffix}"


class SingleInstance(QObject):
    activated = Signal()

    def __init__(self, name: str | None = None):
        super().__init__()
        self.name = name or server_name()
        self._server: QLocalServer | None = None

    last_ack = False  # the running instance answered (False = it is stuck)

    def notify_running_instance(self, timeout_ms: int = 500) -> bool:
        """True if another instance is running (and was asked to show itself)."""
        sock = QLocalSocket()
        sock.connectToServer(self.name)
        if not sock.waitForConnected(timeout_ms):
            return False
        sock.write(b"activate")
        sock.flush()
        sock.waitForBytesWritten(timeout_ms)
        # Wait for the running instance to acknowledge. On Windows (named pipes) closing right
        # after writing can drop the message before the other process has read it.
        self.last_ack = sock.waitForReadyRead(max(timeout_ms, 2000)) and bytes(sock.readAll()).startswith(b"ok")
        sock.disconnectFromServer()
        return True

    def listen(self) -> bool:
        self._server = QLocalServer(self)
        if not self._server.listen(self.name):
            QLocalServer.removeServer(self.name)  # stale socket left by a crash
            if not self._server.listen(self.name):
                return False
        self._server.newConnection.connect(self._on_connection)
        return True

    def _on_connection(self) -> None:
        while self._server and self._server.hasPendingConnections():
            conn = self._server.nextPendingConnection()
            conn.readyRead.connect(lambda c=conn: self._read(c))

    def _read(self, conn: QLocalSocket) -> None:
        if bytes(conn.readAll()).startswith(b"activate"):
            conn.write(b"ok")
            conn.flush()
            self.activated.emit()
        conn.disconnectFromServer()

    def close(self) -> None:
        if self._server:
            self._server.close()
            self._server = None

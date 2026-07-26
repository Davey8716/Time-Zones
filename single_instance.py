"""Single-instance ownership and activation messaging."""

from __future__ import annotations

import ctypes
import os
import tempfile
from pathlib import Path

from PySide6.QtCore import QObject, QLockFile, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket


class _InstanceLock:
    """A Windows named mutex with a portable lock-file fallback."""

    def __init__(self, name: str) -> None:
        self._handle: int | None = None
        self._lock_file: QLockFile | None = None

        if os.name == "nt":
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.CreateMutexW.argtypes = (
                ctypes.c_void_p,
                ctypes.c_bool,
                ctypes.c_wchar_p,
            )
            kernel32.CreateMutexW.restype = ctypes.c_void_p
            handle = kernel32.CreateMutexW(None, False, f"Local\\{name}")
            if not handle:
                raise ctypes.WinError(ctypes.get_last_error())
            self._handle = int(handle)
            self.acquired = ctypes.get_last_error() != 183  # ERROR_ALREADY_EXISTS
        else:
            path = Path(tempfile.gettempdir()) / f"{name}.lock"
            self._lock_file = QLockFile(str(path))
            self._lock_file.setStaleLockTime(0)
            self.acquired = self._lock_file.tryLock(0)

    def release(self) -> None:
        if self._handle is not None:
            ctypes.windll.kernel32.CloseHandle(ctypes.c_void_p(self._handle))
            self._handle = None
        if self._lock_file is not None and self.acquired:
            self._lock_file.unlock()
        self.acquired = False


class SingleInstance(QObject):
    activation_requested = Signal()

    def __init__(self, name: str = "OpenAI.TimeZones.PySide6") -> None:
        super().__init__()
        self.name = name
        self._lock = _InstanceLock(name)
        self.is_primary = self._lock.acquired
        self._server: QLocalServer | None = None

    def listen(self) -> bool:
        if not self.is_primary:
            return False
        QLocalServer.removeServer(self.name)
        self._server = QLocalServer(self)
        self._server.newConnection.connect(self._accept_connection)
        return self._server.listen(self.name)

    def notify_existing(self, timeout_ms: int = 1500) -> bool:
        socket = QLocalSocket()
        socket.connectToServer(self.name)
        if not socket.waitForConnected(timeout_ms):
            return False
        if socket.write(b"SHOW\n") < 0:
            return False
        socket.flush()
        if socket.bytesToWrite():
            socket.waitForBytesWritten(timeout_ms)
        if not socket.bytesAvailable():
            socket.waitForReadyRead(min(timeout_ms, 500))
        socket.readAll()
        socket.disconnectFromServer()
        return True

    def _accept_connection(self) -> None:
        if self._server is None:
            return
        while self._server.hasPendingConnections():
            socket = self._server.nextPendingConnection()
            if socket is None:
                continue
            socket.readyRead.connect(lambda s=socket: self._read_request(s))
            socket.disconnected.connect(socket.deleteLater)
            if socket.bytesAvailable():
                self._read_request(socket)

    def _read_request(self, socket: QLocalSocket) -> None:
        if b"SHOW" in bytes(socket.readAll()):
            self.activation_requested.emit()
            socket.write(b"OK\n")
            socket.flush()
            socket.disconnectFromServer()

    def close(self) -> None:
        if self._server is not None:
            self._server.close()
            self._server = None
            QLocalServer.removeServer(self.name)
        self._lock.release()

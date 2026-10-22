"""Output-only access to vendor light interfaces."""
import errno
import fcntl
import os
import select
import termios
import time

class HidTransport:
    def __init__(self, path: str):
        self._fd = os.open(path, os.O_RDWR | os.O_NONBLOCK)

    def write(self, report: bytes, feature: bool = False) -> None:
        if self._fd is None:
            raise OSError(errno.EBADF, 'Light device closed')
        if feature:
            request = (3 << 30) | (len(report) << 16) | (ord('H') << 8) | 6
            fcntl.ioctl(self._fd, request, report)
        elif os.write(self._fd, report) != len(report):
            raise OSError(errno.EIO, 'Short HID output report')

    def close(self):
        fd, self._fd = self._fd, None
        if fd is not None:
            os.close(fd)

class SerialTransport:
    def __init__(self, path: str):
        self._fd = os.open(path, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
        try:
            fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            attrs = termios.tcgetattr(self._fd)
            attrs[:4] = [0, 0, termios.CLOCAL | termios.CREAD | termios.CS8 | termios.PARENB | termios.CSTOPB, 0]
            attrs[4] = attrs[5] = termios.B115200
            attrs[6][termios.VMIN] = attrs[6][termios.VTIME] = 0
            termios.tcsetattr(self._fd, termios.TCSANOW, attrs)
        except termios.error as error:
            self.close()
            raise OSError(errno.EIO, f'Serial RGB configuration failed: {error}') from error
        except Exception:
            self.close()
            raise

    def write(self, report: bytes):
        deadline = time.monotonic() + 0.25
        pending = memoryview(report)
        while pending:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise OSError(errno.ETIMEDOUT, 'Serial RGB write deadline exceeded')
            try:
                count = os.write(self._fd, pending)
                if count <= 0: raise OSError(errno.EIO, 'Serial RGB output closed')
                pending = pending[count:]
            except BlockingIOError:
                select.select([], [self._fd], [], remaining)

    def close(self):
        fd, self._fd = self._fd, None
        if fd is not None:
            os.close(fd)  # also releases the advisory lock

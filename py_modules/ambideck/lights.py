"""ROG Ally stick lights: direct zone colours and the controller's own modes, as HID feature reports.

Byte values follow the ROG Ally protocol as documented by HHD (hhd-dev/hhd) and the kernel's hid-asus-ally
driver. Zone order: left-bottom, left-top, right-top, right-bottom.
"""
from __future__ import annotations

import fcntl
import glob
import os
import threading
from typing import Callable, Sequence

LED_NAME = "ally:rgb:joystick_rings"
REPORT_LEN = 64
Rgb = tuple[int, int, int]


def _clamp(value) -> int:
    return max(0, min(255, int(value)))


def _report(*data: int) -> bytes:
    return bytes(data) + bytes(REPORT_LEN - len(data))


def zone_report(zones: Sequence[Sequence[int]]) -> bytes:
    if len(zones) != 4:
        raise ValueError("need exactly 4 zones")
    data = [0x5A, 0xD1, 0x08, 0x0C]
    for r, g, b in zones:
        data += [_clamp(r), _clamp(g), _clamp(b)]
    return _report(*data)


_BRIGHTNESS_MEDIUM = _report(0x5A, 0xBA, 0xC5, 0xC4, 0x02)
_MODE_SET = _report(0x5A, 0xB5)
_MODE_APPLY = _report(0x5A, 0xB4)
_MODES = {
    "rainbow": _report(0x5A, 0xB3, 0x00, 0x02, 0, 0, 0, 0xEB, 0, 0, 0, 0, 0),  # all zones, colour cycle, medium
    "off": _report(0x5A, 0xB3, 0x00, 0x00, 0, 0, 0, 0x00, 0, 0, 0, 0, 0),  # all zones, static black
}


def mode_reports(mode: str) -> list[bytes]:
    if mode not in _MODES:
        raise ValueError(f"unknown mode {mode!r}")
    return [_BRIGHTNESS_MEDIUM, _MODES[mode], _MODE_SET, _MODE_APPLY]


def hidiocsfeature(length: int) -> int:
    return (3 << 30) | (length << 16) | (ord("H") << 8) | 0x06


def find_hidraw(sys_root: str = "/sys") -> str | None:
    led = os.path.join(sys_root, "class", "leds", LED_NAME, "device")
    if not os.path.exists(led):
        return None
    target = os.path.realpath(led)
    for node in sorted(glob.glob(os.path.join(sys_root, "class", "hidraw", "hidraw*"))):
        if os.path.realpath(os.path.join(node, "device")) == target:
            return "/dev/" + os.path.basename(node)
    return None


class Lights:
    def __init__(self, path: str, open_fn: Callable = os.open, ioctl_fn: Callable = fcntl.ioctl,
                 close_fn: Callable = os.close) -> None:
        self._fd = open_fn(path, os.O_RDWR)
        self._ioctl = ioctl_fn
        self._close = close_fn
        self._lock = threading.Lock()

    def _send(self, report: bytes) -> None:
        with self._lock:
            self._ioctl(self._fd, hidiocsfeature(len(report)), report)

    def show(self, zones: Sequence[Sequence[int]]) -> None:
        self._send(zone_report(zones))

    def rainbow(self) -> None:
        for report in mode_reports("rainbow"):
            self._send(report)

    def off(self) -> None:
        for report in mode_reports("off"):
            self._send(report)

    def close(self) -> None:
        self._close(self._fd)

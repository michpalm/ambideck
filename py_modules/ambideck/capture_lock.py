"""A screen recorder holds this lock while it captures gamescope's stream, which can only have one consumer's size.

The lock counts only while the process that wrote it is alive, so a recorder that crashed never keeps Ambideck off.
"""
from __future__ import annotations

import json
import os
from typing import Callable

LOCK_PATH = "/run/decky-screen-capture.lock"


def proc_state(pid: int) -> str:
    """The state letter from /proc/<pid>/stat (after the parenthesised name, which may contain spaces)."""
    with open(f"/proc/{pid}/stat", encoding="utf-8") as f:
        return f.read().rsplit(")", 1)[1].split()[0]


def pid_alive(pid: int, read_state: Callable[[int], str] = proc_state) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        pass
    try:
        return read_state(pid) not in ("Z", "X")  # a crashed recorder its parent hasn't reaped yet
    except (OSError, IndexError):
        return True


def capture_locked(path: str = LOCK_PATH, pid_alive: Callable[[int], bool] = pid_alive) -> bool:
    try:
        with open(path, encoding="utf-8") as f:
            lock = json.load(f)
    except (OSError, ValueError):
        return False
    pid = lock.get("pid") if isinstance(lock, dict) else None
    return type(pid) is int and pid > 0 and pid_alive(pid)


def serial_unless_locked(find_serial: Callable[[], int | None], locked: Callable[[], bool] = capture_locked):
    """Stream lookup for a capture: checked again after the (slow) lookup, right before connecting."""
    def find() -> int | None:
        serial = find_serial()
        return None if locked() else serial
    return find

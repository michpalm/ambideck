"""Docked = an external display is connected (DRM connector status); charger = a mains supply is online."""
from __future__ import annotations

import glob
import os
import time
from typing import Callable

INTERNAL_PREFIXES = ("eDP", "LVDS", "DSI")


def external_display_connected(drm_root: str = "/sys/class/drm") -> bool:
    for status in glob.glob(os.path.join(drm_root, "card*-*", "status")):
        name = os.path.basename(os.path.dirname(status)).split("-", 1)[1]
        if name.startswith(INTERNAL_PREFIXES):
            continue
        try:
            with open(status, encoding="utf-8") as f:
                if f.read().strip() == "connected":
                    return True
        except OSError:
            continue
    return False


def charger_connected(power_root: str = "/sys/class/power_supply") -> bool:
    for supply_type in glob.glob(os.path.join(power_root, "*", "type")):
        try:
            with open(supply_type, encoding="utf-8") as f:
                if f.read().strip() != "Mains":
                    continue
            with open(os.path.join(os.path.dirname(supply_type), "online"), encoding="utf-8") as f:
                if f.read().strip() == "1":
                    return True
        except OSError:
            continue
    return False


class DockWatcher:
    """Polls a yes/no state and emits `event` when it changes (used for docked and charger)."""

    def __init__(self, docked_fn: Callable[[], bool], emit: Callable, clock: Callable[[], float] = time.monotonic,
                 interval: float = 2.0, event: str = "docked_changed") -> None:
        self._docked_fn, self._emit, self._clock, self._interval = docked_fn, emit, clock, interval
        self._event = event
        self.current = bool(docked_fn())
        self._next = clock() + interval

    def tick(self) -> None:
        now = self._clock()
        if now < self._next:
            return
        self._next = now + self._interval
        docked = bool(self._docked_fn())
        if docked != self.current:
            self.current = docked
            self._emit(self._event, docked)

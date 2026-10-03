"""What the frontend can ask the backend to do. main.py wraps these as Decky callables."""
from __future__ import annotations

import logging
import threading
import time
from typing import Callable

from .display import DockWatcher
from .follower import Follower

log = logging.getLogger("ambideck")
RESEND_S = 2.0  # same as the follower: wins against HueSync or the driver overriding the colours


def _zones(raw) -> list[tuple[int, int, int]]:
    zones = [tuple(int(c) for c in zone) for zone in raw]
    if len(zones) != 4 or any(len(z) != 3 for z in zones):
        raise ValueError("expected 4 zones of 3 channels")
    return zones


class Backend:
    def __init__(self, find_lights: Callable, docked: Callable[[], bool], charger: Callable[[], bool], emit: Callable,
                 make_capture: Callable,
                 huesync_installed: Callable[[], bool], clock: Callable[[], float] = time.monotonic) -> None:
        self._find_lights = find_lights
        self._lights = None
        self._looked = False
        self._emit = emit
        self._make_capture = make_capture
        self._huesync_installed = huesync_installed
        self._dock = DockWatcher(docked, emit)
        self._charger = DockWatcher(charger, emit, event="charger_changed")
        self._owns_lights = False
        self._clock = clock
        self._static: tuple | None = None  # ("show", zones) or ("off",), re-sent like the follower does
        self._static_sent = 0.0
        self._quit = threading.Event()
        self._worker: threading.Thread | None = None
        self._follower: Follower | None = None

    def _get_lights(self):
        if not self._looked:
            self._looked = True
            try:
                self._lights = self._find_lights()
            except OSError:
                log.exception("[ambideck] could not open the light controller")
                self._lights = None
        return self._lights

    def _stop_following(self) -> None:
        self._static = None
        if self._follower is not None:
            self._follower.stop()

    def _set_static(self, static: tuple) -> None:
        self._static, self._static_sent = static, self._clock()
        self._owns_lights = True

    def _resend_static(self) -> None:
        if self._static is None or self._lights is None or self._clock() - self._static_sent < RESEND_S:
            return
        if self._static[0] == "show":
            self._lights.show(self._static[1])
        else:
            self._lights.off()
        self._static_sent = self._clock()

    def follow(self, settings) -> bool:
        lights = self._get_lights()
        if lights is None:
            return False
        self._static = None
        if self._follower is None:
            self._follower = Follower(self._make_capture, lights, self._emit, clock=self._clock)
        self._follower.update(settings)
        self._follower.start()
        self._owns_lights = True
        return True

    def status(self) -> dict:
        return {"supported": self._get_lights() is not None, "docked": self._dock.current,
                "onCharger": self._charger.current}

    def show(self, zones) -> None:
        self._stop_following()
        lights = self._get_lights()
        if lights is None:
            return
        zones = _zones(zones)
        lights.show(zones)
        self._set_static(("show", zones))

    def rainbow(self, keep_following: bool = False) -> None:
        """keep_following: shown while the stream is lost; the follower keeps retrying and takes over again."""
        if keep_following:
            self._static = None
        else:
            self._stop_following()
        lights = self._get_lights()
        if lights is None:
            return
        lights.rainbow()
        if not keep_following:
            self._owns_lights = False

    def off(self) -> None:
        self._stop_following()
        lights = self._get_lights()
        if lights is None:
            return
        lights.off()
        self._set_static(("off",))

    def stop(self) -> None:
        self._stop_following()
        self._owns_lights = False

    def tick(self) -> None:
        self._dock.tick()
        self._charger.tick()
        self._resend_static()
        if self._follower is not None:
            self._follower.tick()

    def _run(self) -> None:
        while not self._quit.wait(0.5):
            try:
                self.tick()
            except Exception:
                log.exception("[ambideck] worker tick failed")

    def start_worker(self) -> None:
        self._worker = threading.Thread(target=self._run, name="ambideck-worker", daemon=True)
        self._worker.start()

    def shutdown(self) -> None:
        self._quit.set()
        self._stop_following()
        if self._owns_lights and not self._huesync_installed() and self._lights is not None:
            self._lights.rainbow()
            self._owns_lights = False

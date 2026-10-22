"""While a game runs: capture → colour → lights. Re-sends every 2 s and retries a lost stream every 5 s."""
from __future__ import annotations

import logging
import threading
import time
from typing import Callable

from .colour import SPEEDS, DarkGate, Smoother, analyse, is_cut, to_led

log = logging.getLogger("ambideck")
DEFAULTS = {"layout": "corners", "brightness": 70, "boost": 58, "speed": "balanced", "dark": "glow"}


def clean_settings(raw) -> dict:
    raw = raw if isinstance(raw, dict) else {}
    out = dict(DEFAULTS)
    if raw.get("layout") in ("corners", "sides"):
        out["layout"] = raw["layout"]
    if raw.get("speed") in SPEEDS:
        out["speed"] = raw["speed"]
    if raw.get("dark") == "off":
        out["dark"] = "off"
    for key, low, high in (("brightness", 10, 100), ("boost", 0, 100)):
        value = raw.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            out[key] = int(max(low, min(high, value)))
    return out


class Follower:
    RESEND_S = 2.0
    RETRY_S = 5.0
    MIN_GAP_S = 1.0 / 30
    START_TIMEOUT_S = 10.0  # connected but never streaming: treat as lost

    def __init__(self, make_capture: Callable, lights, emit: Callable, clock: Callable[[], float] = time.monotonic):
        self._make_capture, self._lights, self._emit, self._clock = make_capture, lights, emit, clock
        self._lock = threading.Lock()  # settings and sends
        self._life = threading.Lock()  # capture ownership: start/stop/reconnect
        self._generation = 0  # bumped by stop(): a reconnect that finishes later sees it and backs out
        self._settings = dict(DEFAULTS)
        self._capture = None
        self._wanted = False
        self._state = "stopped"  # stopped | connecting | following | waiting
        self._lost = False
        self._retry_at = 0.0
        self._connected_at = 0.0
        self._smoother = Smoother()
        self._dark = DarkGate()
        self._prev_level: float | None = None
        self._last_leds: list | None = None
        self._last_sent = float("-inf")

    @property
    def active(self) -> bool:
        return self._wanted

    def update(self, settings) -> None:
        with self._lock:
            self._settings = clean_settings(settings)
            hz = SPEEDS[self._settings["speed"]][1]
        if self._capture is not None:
            self._capture.set_max_hz(hz)

    def start(self) -> None:
        with self._life:
            if self._wanted:
                return
            self._wanted = True
        self._connect()

    def stop(self) -> None:
        with self._life:
            self._wanted = False
            self._generation += 1
            capture, self._capture = self._capture, None
        if capture is not None:
            capture.stop()
        self._state = "stopped"
        self._lost = False
        self._smoother.reset()
        self._dark.reset()
        self._prev_level = None
        self._last_leds = None

    def _connect(self, due: float | None = None) -> None:
        with self._life:
            generation = self._generation
        hz = SPEEDS[self._settings["speed"]][1]
        capture = self._make_capture(self.on_frame, self.on_state, hz)
        with self._lock:
            self._state = "connecting"
        self._connected_at = self._clock()  # before start(): a tick during pw-dump must see a fresh timestamp
        started = capture.start()  # runs pw-dump: slow enough for stop() to happen meanwhile
        previous = None
        with self._life:
            current = self._wanted and generation == self._generation
            if started and current:
                previous, self._capture = self._capture, capture  # never drop a running capture unstopped
                self._connected_at = self._clock()
        if started and current:
            if previous is not None:
                previous.stop()
            return
        if started:
            capture.stop()
        if current:
            self._to_waiting(due)

    def _to_waiting(self, due: float | None = None) -> None:
        """due: when the failed retry was scheduled, so retries stay RETRY_S apart however late the tick was."""
        now = self._clock()
        self._retry_at = now + self.RETRY_S if due is None else max(due + self.RETRY_S, now)
        changed = False
        with self._lock:
            if self._state != "waiting":
                if hasattr(self._lights, 'pause'):
                    self._lights.pause()
                self._state = "waiting"
                changed = True
        if changed:
            log.info("[ambideck] waiting for gamescope's stream")
            self._emit("follow_state", "waiting")

    def fallback_if_waiting(self, action: Callable[[], None]) -> bool:
        """A delayed waiting RPC must not override a newer streaming transition."""
        with self._lock:
            if not self._wanted or self._state not in ('waiting', 'connecting'):
                return False
            action()
            return True

    def on_state(self, state: str) -> None:  # PipeWire thread: never stop the capture here
        changed = False
        with self._lock:
            if state == "streaming" and self._wanted and self._state != "following":
                if hasattr(self._lights, 'begin_follow'):
                    self._lights.begin_follow()
                self._state = "following"
                changed = True
            elif state in ("error", "unconnected") and self._wanted:
                self._lost = True
        if changed:
            log.info("[ambideck] following the screen")
            self._emit("follow_state", "following")

    def on_frame(self, data: bytes, width: int, height: int, stride: int) -> None:  # PipeWire thread
        if not self._wanted:
            return
        with self._lock:
            s = dict(self._settings)
        a = analyse(data, width, height, stride, s["layout"], s["boost"], s["brightness"])
        now = self._clock()
        cut = is_cut(self._prev_level, a.frame_level)
        self._prev_level = a.frame_level
        targets = a.targets
        if s["dark"] == "off":
            dark = self._dark.update(a.values)
            targets = [(0.0, 0.0, 0.0) if d else t for d, t in zip(dark, targets)]
        values = self._smoother.step(targets, now, SPEEDS[s["speed"]][0], cut)
        self._send([to_led(v) for v in values], now)

    def _send(self, leds: list, now: float, force: bool = False) -> None:
        with self._lock:
            if not self._wanted:
                return
            if not force and self._last_leds is not None:
                if now - self._last_sent < self.MIN_GAP_S:
                    return
                change = max(abs(a - b) for z1, z2 in zip(leds, self._last_leds) for a, b in zip(z1, z2))
                if change <= 1 and now - self._last_sent < self.RESEND_S:
                    return
            if self._lights.show(leds) is False:
                return  # controller missing: try again with the next frame
            self._last_leds, self._last_sent = leds, now

    def tick(self) -> None:  # worker thread
        if not self._wanted:
            return
        now = self._clock()
        if self._state == "connecting" and now - self._connected_at >= self.START_TIMEOUT_S:
            self._lost = True
        if self._lost:
            self._lost = False
            with self._life:
                capture, self._capture = self._capture, None
            if capture is not None:
                capture.stop()
            self._to_waiting()
        if self._state == "waiting" and now >= self._retry_at:
            self._connect(due=self._retry_at)
        if self._state == "following" and self._last_leds is not None and now - self._last_sent >= self.RESEND_S:
            self._send(self._last_leds, now, force=True)

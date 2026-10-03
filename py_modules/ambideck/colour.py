"""Frame → four zone colours. Mirrored exactly in src/colour.ts (artwork mode); tests/vectors/colour.json keeps
them in step. Targets are perceived levels 0..1 per channel; to_led applies gamma for the LEDs."""
from __future__ import annotations

import math
from dataclasses import dataclass

BASE_WEIGHT = 0.05  # grey pixels still count a little, so grey/white scenes stay grey/white
MIN_LEVEL = 0.15  # faint glow on black scenes (perceived)
GAMMA = 2.2
SAMPLE_STEP = 4  # every 4th pixel each way: 144 per corner of a 128x72 frame, cheap in pure Python
CUT_THRESHOLD = 0.35  # change of whole-frame brightness that counts as a scene cut
SPEEDS = {"smooth": (0.6, 15.0), "balanced": (0.25, 15.0), "fast": (0.1, 30.0)}  # (tau seconds, analysis Hz)
_OFFSETS = {"bgrx": (2, 1, 0), "rgba": (0, 1, 2)}  # r, g, b byte offsets within a 4-byte pixel


def round_half_up(x: float) -> int:
    return int(math.floor(x + 0.5))


def boost_factor(boost_value: float) -> float:
    return 1.0 + 1.2 * max(0.0, min(100.0, boost_value)) / 100.0


def regions(width: int, height: int, layout: str) -> list[tuple[int, int, int, int]]:
    hw, hh = width // 2, height // 2
    if layout == "sides":
        left, right = (0, 0, hw, height), (hw, 0, width, height)
        return [left, left, right, right]
    return [(0, hh, hw, height), (0, 0, hw, hh), (hw, 0, width, hh), (hw, hh, width, height)]


def region_colour(frame, stride: int, rect, step: int = SAMPLE_STEP, order: str = "bgrx"):
    """Weighted mean colour (0..255 floats) and mean brightness (HSV value, 0..1) of a region."""
    ro, go, bo = _OFFSETS[order]
    x0, y0, x1, y1 = rect
    sr = sg = sb = sw = level = 0.0
    n = 0
    for y in range(y0, y1, step):
        row = y * stride
        for x in range(x0, x1, step):
            i = row + x * 4
            r, g, b = frame[i + ro], frame[i + go], frame[i + bo]
            mx = max(r, g, b)
            mn = min(r, g, b)
            w = BASE_WEIGHT + (mx - mn) / 255.0  # saturation × value, from HSV
            sr += r * w
            sg += g * w
            sb += b * w
            sw += w
            level += mx
            n += 1
    if n == 0:
        return (0.0, 0.0, 0.0), 0.0
    return (sr / sw, sg / sw, sb / sw), level / (255.0 * n)


def boost(rgb, factor: float):
    mx = max(rgb)
    mn = min(rgb)
    if mx <= 0 or mx == mn:
        return tuple(rgb)
    s = (mx - mn) / mx
    k = min(1.0, s * factor) / s
    return tuple(mx - (mx - c) * k for c in rgb)


def zone_target(rgb, value: float, brightness: float):
    """Hue and saturation from rgb, level from the region's brightness (with a floor), times brightness (0..1)."""
    mx = max(rgb)
    norm = (1.0, 1.0, 1.0) if mx <= 0 else tuple(c / mx for c in rgb)
    level = (MIN_LEVEL + (1.0 - MIN_LEVEL) * max(0.0, min(1.0, value))) * brightness
    return tuple(c * level for c in norm)


@dataclass
class Analysis:
    targets: list
    frame_level: float


def analyse(frame, width: int, height: int, stride: int, layout: str, boost_value: float, brightness: float,
            order: str = "bgrx") -> Analysis:
    cache: dict = {}
    targets = []
    factor = boost_factor(boost_value)
    for rect in regions(width, height, layout):
        if rect not in cache:
            cache[rect] = region_colour(frame, stride, rect, order=order)
        rgb, value = cache[rect]
        targets.append(zone_target(boost(rgb, factor), value, brightness / 100.0))
    values = [value for _rgb, value in cache.values()]
    return Analysis(targets, sum(values) / len(values))


def to_led(target) -> tuple[int, int, int]:
    return tuple(round_half_up(255.0 * max(0.0, min(1.0, c)) ** GAMMA) for c in target)


def is_cut(previous: float | None, current: float) -> bool:
    return previous is not None and abs(current - previous) > CUT_THRESHOLD


class Smoother:
    def __init__(self) -> None:
        self.value: list | None = None
        self._last: float | None = None

    def reset(self) -> None:
        self.value, self._last = None, None

    def step(self, targets, now: float, tau: float, cut: bool) -> list:
        if self.value is None or cut or self._last is None:
            self.value = [tuple(t) for t in targets]
        else:
            dt = max(0.0, now - self._last)
            a = 1.0 - math.exp(-dt / tau) if tau > 0 else 1.0
            self.value = [tuple(v + (t - v) * a for v, t in zip(vz, tz)) for vz, tz in zip(self.value, targets)]
        self._last = now
        return self.value


def quad_frame(width: int, height: int, colours, order: str = "bgrx") -> bytes:
    """Test frame: each quadrant one colour, colours in zone order (LB, LT, RT, RB)."""
    ro, go, bo = _OFFSETS[order]
    lb, lt, rt, rb = colours
    out = bytearray(width * height * 4)
    for y in range(height):
        for x in range(width):
            top, left = y < height // 2, x < width // 2
            r, g, b = (lt if left else rt) if top else (lb if left else rb)
            i = (y * width + x) * 4
            out[i + ro], out[i + go], out[i + bo] = r, g, b
            out[i + 3] = 255
    return bytes(out)

"""Capabilities and mapping from canonical screen samples to physical lights."""
from dataclasses import dataclass
import math
from typing import Protocol

Rgb = tuple[int, int, int]
Zones = tuple[Rgb, Rgb, Rgb, Rgb]

@dataclass(frozen=True)
class DeviceInfo:
    name: str
    layout: str
    max_hz: float
    native_rainbow: bool
    huesync: bool = False

class LightDevice(Protocol):
    info: DeviceInfo
    def show(self, zones: Zones) -> None: ...
    def off(self) -> None: ...
    def rainbow(self) -> None: ...
    def close(self) -> None: ...

def clean_zones(raw) -> Zones:
    try:
        if len(raw) != 4 or any(len(z) != 3 for z in raw):
            raise ValueError('expected four RGB samples')
        if any(isinstance(c, bool) or not isinstance(c, (int, float)) or not math.isfinite(c)
               for z in raw for c in z):
            raise ValueError('expected finite colour channels')
        return tuple(tuple(max(0, min(255, int(c))) for c in z) for z in raw)
    except (TypeError, OverflowError) as error:
        raise ValueError('expected four RGB samples') from error

def _mean(zones) -> Rgb:
    n = len(zones)
    return tuple((sum(z[c] for z in zones) * 2 + n) // (2 * n) for c in range(3))

def shared_colour(zones: Zones) -> Rgb:
    return _mean(zones)

def map_zones(zones: Zones, layout: str) -> tuple[Rgb, ...]:
    if layout == 'corners':
        return zones
    if layout == 'sides':
        return (_mean(zones[:2]), _mean(zones[2:]))
    if layout == 'shared':
        return (shared_colour(zones),)
    raise ValueError(f'unknown light layout: {layout}')

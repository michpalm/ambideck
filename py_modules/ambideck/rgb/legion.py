"""Lenovo RGB packets, independently encoded from HHD's protocol facts."""
from .model import map_zones

def legion_reports(variant: str, command: str, colours: tuple, initialize: bool) -> list[bytes]:
    if variant not in ('go', 'go_s') or command not in ('show', 'off', 'rainbow'):
        raise ValueError('unknown Legion lighting command')
    if variant == 'go_s':
        if command == 'off': return [bytes((4, 6, 0))]
        colour = colours[0] if command == 'show' else (0, 0, 0)
        mode = 0 if command == 'show' else 2
        profile = bytes((0x10, 5, mode, *colour, 63, 63))
        return ([bytes((4, 6, 1)), bytes((0x10, 2, 3))] if initialize else []) + [profile]
    if command == 'off':
        return [bytes((5, 6, 0x70, 2, side, 0, 1)) for side in (3, 4)]
    colours = colours if command == 'show' else ((0, 0, 0),) * 2
    mode = 1 if command == 'show' else 3
    # HHD always reloads tablet profiles: older controller firmware requires it.
    return ([bytes((5, 12, 0x72, 1, side, mode, *colour, 63, 0, 3, 1))
             for side, colour in zip((3, 4), colours)] +
            [bytes((5, 6, 0x73, 2, side, 3, 1)) for side in (3, 4)] +
            [bytes((5, 6, 0x70, 2, side, 1, 1)) for side in (3, 4)])

class LegionLights:
    def __init__(self, transport, info, variant):
        self.info, self._transport, self._variant = info, transport, variant
        self._mode = None

    def _send(self, mode, colours=()):
        for report in legion_reports(self._variant, mode, colours, self._mode != mode):
            self._transport.write(report)
        self._mode = mode

    def show(self, zones): self._send('show', map_zones(zones, self.info.layout))
    def off(self): self._send('off')
    def rainbow(self): self._send('rainbow')
    def close(self): self._transport.close()

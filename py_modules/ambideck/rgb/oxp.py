"""OneXPlayer lighting packets; never sends button-configuration commands."""
import time
from .model import shared_colour

def oxp_reports(protocol: str, command: str, colours: tuple, initialize: bool) -> list[bytes]:
    if protocol not in ('hid_v1', 'hid_v1_g1', 'hid_v2_x2', 'hid_v2', 'hid_dual', 'mixed', 'serial'):
        raise ValueError('unknown OneXPlayer protocol')
    if command not in ('show', 'off'):
        raise ValueError('unknown OneXPlayer lighting command')
    enabled = command == 'show'
    colour = colours[0] if enabled else (0, 0, 0)
    reports = []
    if protocol in ('hid_v2', 'hid_dual', 'mixed'):
        if initialize or not enabled:
            reports.append(bytes((7, 255, 253, int(enabled), 5, 4)).ljust(64, b'\x00'))
        if enabled:
            reports.append(bytes((7, 255, 254)) + bytes(colour) * 20 + b'\x00')
        return reports
    sides = (1, 2, 7) if protocol == 'hid_v2_x2' else (0,)
    for side in sides:
        if protocol == 'serial':
            def frame(payload):
                return (bytes((0xfd, 0x3f)) + bytes(payload)).ljust(62, b'\x00') + bytes((0x3f, 0xfd))
            if initialize or not enabled:
                reports.append(frame((side, 0xfd, 3 if side == 0 else 0, 0, int(enabled), 5, 4)))
            if enabled:
                reports.append(frame(bytes((side, 0xfe, 0, 0)) + bytes(colour) * 18 + bytes(colour[:2])))
        else:
            def frame(payload):
                return (bytes((0xb8, 0x3f, 1)) + bytes(payload)).ljust(62, b'\x00') + bytes((0x3f, 0xb8))
            if initialize or not enabled:
                reports.append(frame((0xfd, side, 2, int(enabled), 5, 4)))
            if enabled:
                reports.append(frame(bytes((0xfe, side, 2)) + bytes(colour) * 18 + bytes(colour[:2])))
    return reports

class OxpLights:
    def __init__(self, transport, info, protocol: str):
        self.info, self._transport, self._protocol = info, transport, protocol
        self._mode = None
        self._last_report_at = float('-inf')
        self.ready_at = time.monotonic() + (2 if protocol == 'serial' else 4)

    def _send(self, command, colours=()):
        for report in oxp_reports(self._protocol, command, colours, self._mode != command):
            delay = 0.05 - (time.monotonic() - self._last_report_at)
            if delay > 0: time.sleep(delay)  # called only from the lighting output worker
            self._transport.write(report)
            self._last_report_at = time.monotonic()
        self._mode = command

    def show(self, zones): self._send('show', (shared_colour(zones),))
    def off(self): self._send('off')
    def rainbow(self): raise OSError('Use static fallback for OneXPlayer lighting')
    def close(self): self._transport.close()

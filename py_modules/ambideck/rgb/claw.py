"""MSI light output; firmware revision chooses the RGB profile address."""
from .model import shared_colour

def claw_address(version: int | None) -> tuple[int, int]:
    if version is None:
        raise OSError('Cannot read Claw USB firmware revision')
    major = version >> 8
    modern = (major == 1 and version >= 0x0166) or (major == 2 and version >= 0x0217) or major >= 3
    return (2, 74) if modern else (1, 250)

def claw_report(colour, address) -> bytes:
    data = bytes((15, 0, 0, 60, 33, 1, *address, 32, 0, 1, 9, 3, 100)) + bytes(colour) * 9
    return data.ljust(64, b'\x00')

class ClawLights:
    def __init__(self, transport, info, address):
        self._transport, self.info, self._address = transport, info, address
    def show(self, zones): self._transport.write(claw_report(shared_colour(zones), self._address))
    def off(self): self._transport.write(claw_report((0, 0, 0), self._address))
    def rainbow(self): raise OSError('Claw has no documented native rainbow command')
    def close(self): self._transport.close()

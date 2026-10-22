"""Known handheld LEDs exposed by kernel multicolour drivers."""
from pathlib import Path
from .model import DeviceInfo, shared_colour

class SysfsLights:
    def __init__(self, nodes: tuple[str, ...], info: DeviceInfo):
        self.info = info
        self._nodes = []
        try:
            for node in nodes:
                path = Path(node)
                index = (path / 'multi_index').read_text().split()
                values = (path / 'multi_intensity').read_text().split()
                maximum = int((path / 'max_brightness').read_text())
                if (len(index) != len(values) or maximum <= 0 or not index or
                    any(c not in ('red', 'green', 'blue', 'rgb', 'multi') for c in index) or
                    not ({'red', 'green', 'blue'} <= set(index) or {'rgb', 'multi'} & set(index))):
                    raise ValueError('incomplete RGB channel metadata')
                int((path / 'brightness').read_text())
                self._nodes.append((path, index, maximum))
        except ValueError as error:
            raise OSError(f'Unsupported LED metadata: {error}') from error

    def show(self, zones):
        r, g, b = shared_colour(zones)
        channels = {'red': r, 'green': g, 'blue': b, 'rgb': (r << 16) | (g << 8) | b,
                    'multi': (r << 16) | (g << 8) | b}
        for path, index, maximum in self._nodes:
            # AYN's mode switch is a kernel interface, not controller input.
            for mode in (path / 'led_mode', path / 'device/led_mode'):
                if mode.exists():
                    mode.write_text('1')
                    break
            (path / 'multi_intensity').write_text(' '.join(str(channels[c]) for c in index))
            (path / 'brightness').write_text(str(maximum))

    def off(self):
        for path, _, _ in self._nodes:
            (path / 'brightness').write_text('0')

    def rainbow(self):
        raise OSError('No native rainbow command for this kernel LED')

    def close(self):
        pass

def find_sysfs_lights(sys_root: str, dmi: dict[str, str]):
    vendors = {dmi.get(field, '').strip().lower() for field in ('sys_vendor', 'board_vendor')}
    if any('ayaneo' in vendor for vendor in vendors) or vendors & {'aya', 'aya neo'}:
        prefix, label = 'ayaneo', 'AYANEO'
    elif 'ayn' in vendors:
        prefix, label = 'ayn', 'AYN Loki'
    elif any('zotac' in vendor for vendor in vendors):
        prefix, label = 'zotac', 'Zotac Zone'
    else:
        return None
    base = Path(sys_root) / 'class/leds'
    names = ((f'{prefix}:rgb:joystick_rings', f'{prefix}:multicolor:chassis', 'multicolor:chassis')
             if prefix != 'zotac' else ('zotac:rgb:spectra_zone_0', 'zotac:rgb:spectra_zone_1'))
    nodes = tuple(str(base / n) for n in names if (base / n).exists())
    if not nodes:
        return None
    # Legacy and modern kernel names may coexist as aliases. Never output twice to one node.
    nodes = tuple(dict.fromkeys(str(Path(n).resolve()) for n in nodes))
    return SysfsLights(nodes, DeviceInfo(dmi.get('product_name') or label, 'shared', 10.0, False))

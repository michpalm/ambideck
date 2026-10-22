"""Read-only identities and top-level HID applications, never controller input."""
from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class HidNode:
    path: str
    vendor: int
    product: int
    usage_page: int
    usage: int
    release: int | None = None

def read_dmi(sys_root: str) -> dict[str, str]:
    result = {}
    for field in ('sys_vendor', 'board_vendor', 'product_name', 'board_name'):
        for base in ('class/dmi/id', 'devices/virtual/dmi/id'):
            try:
                result[field] = (Path(sys_root) / base / field).read_text().strip()
                break
            except OSError:
                continue
    return result

def descriptor_usages(data: bytes) -> set[tuple[int, int]]:
    page, local, depth, i = 0, [], 0, 0
    stack, found = [], set()
    try:
        while i < len(data):
            tag = data[i]; i += 1
            if tag == 0xfe:
                if i + 2 > len(data): return set()
                size = data[i]; i += 2
                if i + size > len(data): return set()
                i += size
                continue
            size = (0, 1, 2, 4)[tag & 3]
            if i + size > len(data): return set()
            value = int.from_bytes(data[i:i + size], 'little'); i += size
            kind, item = (tag >> 2) & 3, tag >> 4
            if kind == 1:
                if item == 0: page = value
                elif item == 10: stack.append(page)
                elif item == 11: page = stack.pop()
            elif kind == 2 and item == 0:
                local.append((value >> 16, value & 0xffff) if size == 4 else (page, value))
            elif kind == 0:
                if item == 10:
                    if depth == 0 and value == 1: found.update(local)
                    depth += 1
                elif item == 12:
                    depth -= 1
                    if depth < 0: return set()
                local = []
        return found if depth == 0 and not stack else set()
    except (IndexError, ValueError):
        return set()

def hid_nodes(sys_root: str, dev_root: str) -> list[HidNode]:
    nodes = []
    for node in sorted((Path(sys_root) / 'class/hidraw').glob('hidraw*')):
        device = (node / 'device').resolve()
        try:
            attrs = dict(line.split('=', 1) for line in (device / 'uevent').read_text().splitlines() if '=' in line)
            bus, vid, pid = (int(v, 16) for v in attrs['HID_ID'].split(':'))
            if bus != 3: continue  # only the documented USB interfaces
            usages = descriptor_usages((device / 'report_descriptor').read_bytes())
        except (OSError, KeyError, ValueError):
            continue
        release = None
        for parent in (device, *device.parents):
            try:
                release = int((parent / 'bcdDevice').read_text().strip(), 16)
                break
            except (OSError, ValueError):
                continue
        nodes.extend(HidNode(str(Path(dev_root) / node.name), vid, pid, p, u, release) for p, u in usages)
    return nodes

def matching_node(nodes, profile) -> HidNode | None:
    found = {n.path: n for n in nodes if (n.vendor, n.product, n.usage_page, n.usage) in profile.identities}
    if len(found) > 1:
        raise OSError('Ambiguous RGB interfaces; refusing to choose a controller')
    return next(iter(found.values()), None)

def serial_path(sys_root: str, dev_root: str) -> str | None:
    found = []
    for tty in (Path(sys_root) / 'class/tty').glob('ttyUSB*'):
        device = (tty / 'device').resolve()
        for parent in (device, *device.parents):
            try:
                if ((parent / 'idVendor').read_text().strip().lower(),
                    (parent / 'idProduct').read_text().strip().lower()) == ('1a86', '7523'):
                    found.append(str(Path(dev_root) / tty.name))
                    break
            except OSError:
                continue
    if len(found) > 1: raise OSError('Ambiguous OneXPlayer serial RGB interfaces')
    return found[0] if found else None

"""Select an explicitly supported light device, with actionable failure reasons."""
from dataclasses import dataclass
from .model import LightDevice, DeviceInfo
from .discovery import read_dmi, hid_nodes, matching_node, serial_path
from .profiles import select_profile
from .sysfs import find_sysfs_lights
from .transport import HidTransport, SerialTransport
from .oxp import OxpLights
from .legion import LegionLights
from .claw import ClawLights, claw_address

@dataclass
class Detection:
    device: LightDevice | None
    reason: str | None = None

def detect(sys_root: str = '/sys', dev_root: str = '/dev') -> Detection:
    from ..lights import find_hidraw, Lights
    try:
        ally = find_hidraw(sys_root)
        if ally:
            return Detection(Lights(ally.replace('/dev/', dev_root.rstrip('/') + '/')))
        dmi = read_dmi(sys_root)
        profile = select_profile(dmi)
        if profile:
            if profile.protocol == 'serial':
                path = serial_path(sys_root, dev_root)
                if path:
                    return Detection(OxpLights(SerialTransport(path),
                        DeviceInfo(profile.name, 'shared', 5.0, False), 'serial'))
                return Detection(None, f'{profile.name}: compatible USB serial RGB interface unavailable')
            node = matching_node(hid_nodes(sys_root, dev_root), profile)
            if node:
                info = DeviceInfo(profile.name, profile.layout, 10.0, profile.native_rainbow)
                if profile.protocol in ('go', 'go_s'):
                    return Detection(LegionLights(HidTransport(node.path), info, profile.protocol))
                if profile.protocol == 'claw':
                    address = claw_address(node.release)
                    return Detection(ClawLights(HidTransport(node.path), info, address))
                return Detection(OxpLights(HidTransport(node.path), info, profile.protocol))
            return Detection(None, f'{profile.name}: RGB backend not yet registered' if node else
                             f'{profile.name}: RGB interface unavailable in this controller mode')
        device = find_sysfs_lights(sys_root, dmi)
        return Detection(device, None if device else 'No compatible handheld RGB interface found')
    except OSError as error:
        return Detection(None, str(error))

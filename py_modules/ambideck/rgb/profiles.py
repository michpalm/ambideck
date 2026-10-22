"""Explicit protocol identities from HHD 40b6893 (see docs/rgb-protocols.md)."""
from dataclasses import dataclass

@dataclass(frozen=True)
class DeviceProfile:
    name: str
    protocol: str
    identities: tuple[tuple[int, int, int, int], ...]
    layout: str = 'shared'
    native_rainbow: bool = False

GO_IDS = tuple((0x17ef, p, 0xffa0, 1) for p in
               (0x6182, 0x6183, 0x6184, 0x6185, 0x61eb, 0x61ec, 0x61ed, 0x61ee))
GOS_IDS = tuple((0x1a86, p, 0xffa0, 1) for p in (0xe310, 0xe311))
CLAW_IDS = tuple((0x0db0, p, page, usage) for p in (0x1901, 0x1902)
                 for page, usage in ((0xfff0, 0x40), (1, 5), (0xff00, 0), (0xffa0, 1)))
OXP_V1 = ((0x1a86, 0xfe00, 0xff00, 1),)
OXP_V2 = ((0x1a2c, 0xb001, 0xff01, 1),)
CLAW_MODELS = {'MS-1T41': 'MSI Claw A1M', 'MS-1T42': 'MSI Claw 7 AI+',
               'MS-1T52': 'MSI Claw 8 AI+', 'MS-1T91': 'MSI Claw 8 EX AI+',
               'MS-1T8K': 'MSI Claw A8'}
OXP_MODELS = {
    'ONEXPLAYER Mini Pro': 'hid_v2',
    'ONEXPLAYER F1': 'mixed', 'ONEXPLAYER F1 EVA-01': 'mixed',
    'ONEXPLAYER F1L': 'mixed', 'ONEXPLAYER F1 OLED': 'mixed',
    'ONEXPLAYER F1Pro': 'mixed', 'ONEXPLAYER F1 EVA-02': 'mixed',
    'ONEXPLAYER APEX': 'hid_dual', 'AOKZOE A1X': 'hid_dual',
    'ONEXPLAYER 3': 'hid_v2_x2', 'ONEXPLAYER X2Mini PRO': 'hid_v2_x2',
    'ONEXPLAYER X1 mini': 'hid_v1', 'ONEXPLAYER X1Mini Pro': 'hid_v1',
    'ONEXPLAYER X1Air': 'hid_v1', 'ONEXPLAYER X1 A': 'serial',
    'ONEXPLAYER X1z': 'serial', 'ONEXPLAYER X1Pro': 'serial',
    'ONEXPLAYER X1Pro EVA-02': 'serial', 'ONEXPLAYER X1 i': 'serial',
    'ONEXPLAYER G1 i': 'hid_v1_g1', 'ONEXPLAYER G1 A': 'hid_v1_g1',
}

def select_profile(dmi: dict[str, str]) -> DeviceProfile | None:
    vendor = dmi.get('sys_vendor', '').lower()
    model = dmi.get('product_name', '')
    if vendor == 'lenovo':
        if model in ('83E1', '83N0', '83N1'):
            return DeviceProfile('Legion Go' if model == '83E1' else 'Legion Go 2', 'go', GO_IDS, 'sides', True)
        if model in ('83L3', '83N6', '83Q2', '83Q3'):
            return DeviceProfile('Legion Go S', 'go_s', GOS_IDS, native_rainbow=True)
    if 'micro-star' in vendor or vendor == 'msi':
        name = CLAW_MODELS.get(dmi.get('board_name', '')) or CLAW_MODELS.get(model)
        if name:
            return DeviceProfile(name, 'claw', CLAW_IDS)
    if any(v in vendor for v in ('one-netbook', 'onexplayer', 'aokzoe')) and model in OXP_MODELS:
        protocol = OXP_MODELS[model]
        ids = OXP_V2 if protocol in ('hid_v2', 'mixed', 'hid_dual', 'hid_v1_g1') else OXP_V1
        return DeviceProfile(model, protocol, ids)
    return None

import pytest
from ambideck.rgb.discovery import descriptor_usages, hid_nodes, matching_node
from ambideck.rgb.profiles import select_profile

def node(tmp_path, name='hidraw0', vid='17EF', pid='6182', page='A0FF'):
    d = tmp_path / 'class/hidraw' / name / 'device'
    d.mkdir(parents=True)
    (d / 'uevent').write_text(f'HID_ID=0003:0000{vid}:0000{pid}\n')
    (d / 'report_descriptor').write_bytes(bytes.fromhex(f'06{page}0901a101c0'))
    return d

def test_descriptor_top_level_usage_and_rejection():
    assert descriptor_usages(bytes.fromhex('06a0ff0901a101c0')) == {(0xffa0, 1)}
    assert descriptor_usages(bytes.fromhex('05010906a101c0')) == {(1, 6)}
    for malformed in ('06a0', 'fe05', '06a0ff0901a101', 'b4'):
        assert descriptor_usages(bytes.fromhex(malformed)) == set()

def test_requires_the_vendor_rgb_interface_and_rejects_ambiguity(tmp_path):
    p = select_profile({'product_name': '83E1', 'sys_vendor': 'LENOVO'})
    node(tmp_path, page='0100')
    assert matching_node(hid_nodes(str(tmp_path), '/dev'), p) is None
    d = tmp_path / 'class/hidraw/hidraw0/device/report_descriptor'
    d.write_bytes(bytes.fromhex('06a0ff0901a101c0'))
    assert matching_node(hid_nodes(str(tmp_path), '/dev'), p).path == '/dev/hidraw0'
    node(tmp_path, 'hidraw1')
    with pytest.raises(OSError, match='Ambiguous'):
        matching_node(hid_nodes(str(tmp_path), '/dev'), p)

def test_reused_node_and_unknown_models_are_not_assumed_compatible(tmp_path):
    d = node(tmp_path)
    p = select_profile({'product_name': '83E1', 'sys_vendor': 'LENOVO'})
    (d / 'uevent').write_text('HID_ID=0003:0000045E:0000028E\n')
    assert matching_node(hid_nodes(str(tmp_path), '/dev'), p) is None
    assert select_profile({'product_name': 'future', 'sys_vendor': 'LENOVO'}) is None
    assert select_profile({'product_name': '83E1', 'sys_vendor': 'other'}) is None
    for name in ('AOKZOE A1 Pro', 'ONEXPLAYER 2'):
        assert select_profile({'product_name': name, 'sys_vendor': 'ONE-NETBOOK'}) is None

def test_claw_profile_requires_known_model_and_never_test_mode(tmp_path):
    node(tmp_path, vid='0DB0', pid='1903', page='0100')
    p = select_profile({'product_name': 'Claw', 'board_name': 'MS-1T41', 'sys_vendor': 'Micro-Star International Co., Ltd.'})
    assert p.name == 'MSI Claw A1M'
    assert matching_node(hid_nodes(str(tmp_path), '/dev'), p) is None

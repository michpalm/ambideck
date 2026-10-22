import pytest
from ambideck.rgb.oxp import oxp_reports
from ambideck.rgb.profiles import select_profile

@pytest.mark.parametrize('protocol', ['hid_v2', 'mixed', 'hid_dual'])
def test_oxp_v2_rgb_frames_are_not_v1_frames(protocol):
    reports = oxp_reports(protocol, 'show', ((10, 20, 30),), False)
    assert len(reports) == 1
    assert reports[0].hex() == '07fffe' + '0a141e' * 20 + '00'

@pytest.mark.parametrize('protocol', ['hid_v1', 'hid_v1_g1', 'hid_v2_x2'])
def test_oxp_v1_frames_keep_header_footer_and_channel_order(protocol):
    reports = oxp_reports(protocol, 'show', ((1, 2, 3),), False)
    for r in reports:
        assert len(r) == 64 and r[:3] == bytes.fromhex('b83f01') and r[-2:] == bytes.fromhex('3fb8')
        assert r[3] == 0xfe and r[5] == 2
        assert r[6:60] == bytes.fromhex('010203' * 18)
    assert len(reports) == (3 if protocol == 'hid_v2_x2' else 1)

def test_serial_rgb_uses_its_own_framing_and_no_controller_setup():
    reports = oxp_reports('serial', 'show', ((1, 2, 3),), False)
    assert reports[0].hex() == 'fd3f00fe0000' + '010203' * 18 + '01023ffd'
    assert oxp_reports('serial', 'off', (), False)[0][:9].hex() == 'fd3f00fd0300000504'
    with pytest.raises(ValueError): oxp_reports('guess', 'show', ((1, 2, 3),), False)

def test_g1_uses_the_v2_usb_identity_with_v1_rgb_encoding():
    p = select_profile({'product_name': 'ONEXPLAYER G1 A', 'sys_vendor': 'ONE-NETBOOK'})
    assert p.identities == ((0x1a2c, 0xb001, 0xff01, 1),)

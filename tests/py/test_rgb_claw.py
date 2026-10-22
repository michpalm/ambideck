import pytest
from ambideck.rgb.claw import claw_report, claw_address

@pytest.mark.parametrize('version,address', [(0x0163, (1,250)), (0x0166, (2,74)),
                                         (0x0216, (1,250)), (0x0217, (2,74)), (0x0300, (2,74))])
def test_firmware_selects_the_claw_rgb_address(version, address):
    assert claw_address(version) == address
    report = claw_report((10, 20, 30), address)
    assert len(report) == 64
    assert report[:6] == bytes.fromhex('0f00003c2101')
    assert report[6:8] == bytes(address)
    assert report[8:14] == bytes.fromhex('200001090364')
    assert report[14:41] == bytes.fromhex('0a141e' * 9)
    assert report[41:] == bytes(23)

def test_claw_unknown_firmware_does_not_guess_address():
    with pytest.raises(OSError, match='firmware'):
        claw_address(None)

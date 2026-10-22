import pytest
from ambideck.rgb.sysfs import find_sysfs_lights

def led(root, name='ayaneo:rgb:joystick_rings', index='blue red green', value='0 0 0', max_brightness='31'):
    p = root / 'class/leds' / name
    p.mkdir(parents=True)
    for f, v in [('multi_index', index), ('multi_intensity', value), ('brightness', '0'), ('max_brightness', max_brightness)]:
        (p / f).write_text(v)
    return p

def test_kernel_channel_order_and_brightness_follow_metadata(tmp_path):
    p = led(tmp_path)
    lights = find_sysfs_lights(str(tmp_path), {'sys_vendor': 'AYANEO', 'product_name': 'AYANEO 2'})
    lights.show(((10, 20, 30),) * 4)
    assert (p / 'multi_intensity').read_text() == '30 10 20'
    assert (p / 'brightness').read_text() == '31'
    lights.off()
    assert (p / 'brightness').read_text() == '0'
    lights.show(((10, 20, 30),) * 4)
    assert (p / 'brightness').read_text() == '31'

def test_packed_channels_and_ayn_static_mode(tmp_path):
    p = led(tmp_path, 'ayn:rgb:joystick_rings', 'rgb', '0', '255')
    (p / 'led_mode').write_text('0')
    lights = find_sysfs_lights(str(tmp_path), {'sys_vendor': 'AYN', 'product_name': 'Loki Max'})
    lights.show(((10, 20, 30),) * 4)
    assert (p / 'multi_intensity').read_text() == str(0x0a141e)
    assert (p / 'led_mode').read_text() == '1'
    assert not lights.info.native_rainbow

def test_zotac_outputs_same_shared_colour_without_guessing_zone_position(tmp_path):
    a = led(tmp_path, 'zotac:rgb:spectra_zone_0')
    b = led(tmp_path, 'zotac:rgb:spectra_zone_1')
    lights = find_sysfs_lights(str(tmp_path), {'sys_vendor': 'ZOTAC', 'product_name': 'ZOTAC GAMING ZONE'})
    lights.show(((0, 0, 0), (4, 8, 12), (0, 0, 0), (0, 0, 0)))
    assert (a / 'multi_intensity').read_text() == (b / 'multi_intensity').read_text() == '3 1 2'

@pytest.mark.parametrize('index,value', [('red green', '0 0'), ('red green blue', '0'), ('infrared', '0')])
def test_malformed_or_unrelated_nodes_are_not_written(tmp_path, index, value):
    led(tmp_path, index=index, value=value)
    with pytest.raises(OSError):
        find_sysfs_lights(str(tmp_path), {'sys_vendor': 'AYANEO'})
    assert find_sysfs_lights(str(tmp_path), {'sys_vendor': 'External Keyboard'}) is None

def test_unplug_during_output_propagates_io_failure(tmp_path):
    p = led(tmp_path)
    lights = find_sysfs_lights(str(tmp_path), {'sys_vendor': 'AYANEO'})
    import shutil
    shutil.rmtree(p)
    with pytest.raises(OSError):
        lights.show(((1, 2, 3),) * 4)

@pytest.mark.parametrize('sys_vendor,board_vendor', [('ayn', 'ayn'), ('AYN', 'AYN'), ('aya', 'aya'), ('aya neo', 'aya neo')])
def test_both_populated_dmi_vendor_fields_are_matched_individually(tmp_path, sys_vendor, board_vendor):
    prefix = 'ayn' if sys_vendor.lower() == 'ayn' else 'ayaneo'
    led(tmp_path, f'{prefix}:rgb:joystick_rings')
    lights = find_sysfs_lights(str(tmp_path), {'sys_vendor': sys_vendor, 'board_vendor': board_vendor})
    assert lights is not None
    lights.show(((1, 2, 3),) * 4)

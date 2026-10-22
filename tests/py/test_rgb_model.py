import pytest
from ambideck.rgb.model import clean_zones, map_zones, shared_colour

Z = ((0, 0, 0), (1, 3, 5), (10, 20, 30), (11, 21, 31))

def test_maps_final_colours_to_physical_zones_with_half_up_rounding():
    assert map_zones(Z, 'corners') == Z
    assert map_zones(Z, 'sides') == ((1, 2, 3), (11, 21, 31))
    assert map_zones(Z, 'shared') == ((6, 11, 17),)
    assert shared_colour(Z) == (6, 11, 17)
    with pytest.raises(ValueError):
        map_zones(Z, 'unknown')

@pytest.mark.parametrize('raw', [None, [], [(1, 2)] * 4, [(True, 2, 3)] * 4,
                               [(float('nan'), 2, 3)] * 4, [(float('inf'), 2, 3)] * 4])
def test_rejects_malformed_zones_before_a_device_write(raw):
    with pytest.raises(ValueError):
        clean_zones(raw)

def test_clamps_without_reapplying_brightness_or_gamma():
    assert clean_zones([(300, -5, 12.7)] * 4) == ((255, 0, 12),) * 4

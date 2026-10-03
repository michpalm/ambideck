import json
import os
import subprocess
import sys

import pytest

from ambideck.colour import (MIN_LEVEL, Smoother, analyse, boost, boost_factor, is_cut, quad_frame, region_colour,
                             regions, round_half_up, to_led, zone_target)

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def test_round_half_up_differs_from_bankers_rounding():
    assert round_half_up(0.5) == 1 and round_half_up(2.5) == 3 and round_half_up(1.49) == 1


def test_regions_in_controller_zone_order():
    assert regions(8, 4, "corners") == [(0, 2, 4, 4), (0, 0, 4, 2), (4, 0, 8, 2), (4, 2, 8, 4)]
    left, right = (0, 0, 4, 4), (4, 0, 8, 4)
    assert regions(8, 4, "sides") == [left, left, right, right]


def test_uniform_region_gives_its_colour_and_brightness():
    frame = quad_frame(8, 4, [(255, 0, 0)] * 4)
    rgb, value = region_colour(frame, 32, (0, 0, 8, 4), step=1)
    assert rgb == pytest.approx((255, 0, 0))
    assert value == pytest.approx(1.0)  # a saturated red screen lights the rings fully


def test_colourful_pixels_outweigh_grey_ones():
    # left half grey, right half pastel pink, analysed as one region
    frame = quad_frame(8, 4, [(128, 128, 128), (128, 128, 128), (255, 182, 193), (255, 182, 193)])
    rgb, _ = region_colour(frame, 32, (0, 0, 8, 4), step=1)
    plain_red = (128 + 255) / 2
    assert rgb[0] > plain_red
    assert rgb[0] - rgb[1] > (255 - 182) / 2


def test_boost_raises_saturation_and_keeps_hue_order():
    out = boost((200, 150, 100), 1.7)
    assert out[0] == pytest.approx(200)
    assert out[0] > out[1] > out[2]
    assert out[2] < 100
    assert boost((90, 90, 90), 2.0) == (90, 90, 90)
    assert boost((255, 0, 0), 2.0) == (255, 0, 0)
    assert boost_factor(0) == 1.0 and boost_factor(100) == pytest.approx(2.2)


def test_dark_scenes_keep_a_faint_glow():
    assert zone_target((0, 0, 0), 0.0, 1.0) == pytest.approx((MIN_LEVEL,) * 3)
    full = zone_target((255, 0, 0), 1.0, 0.5)
    assert full == pytest.approx((0.5, 0.0, 0.0))


def test_to_led_applies_gamma():
    assert to_led((1.0, 0.5, 0.0)) == (255, 55, 0)
    assert to_led((1.2, -0.1, 0.0)) == (255, 0, 0)


def test_analyse_corners_and_sides():
    frame = quad_frame(16, 8, [(0, 0, 255), (255, 0, 0), (0, 255, 0), (255, 255, 0)])
    corners = analyse(frame, 16, 8, 64, "corners", 0, 100)
    leds = [to_led(t) for t in corners.targets]
    assert leds[0][2] > leds[0][0] and leds[1][0] > leds[1][2] and leds[2][1] > leds[2][0]
    sides = analyse(frame, 16, 8, 64, "sides", 0, 100)
    assert sides.targets[0] == sides.targets[1] and sides.targets[2] == sides.targets[3]


def test_smoother_fades_and_jumps_on_cuts():
    s = Smoother()
    assert s.step([(1.0, 0.0, 0.0)] * 4, 0.0, 0.25, False) == [(1.0, 0.0, 0.0)] * 4
    faded = s.step([(0.0, 0.0, 0.0)] * 4, 0.25, 0.25, False)
    assert faded[0][0] == pytest.approx(0.36788, abs=1e-4)  # e^-1 after one time constant
    assert s.step([(0.0, 1.0, 0.0)] * 4, 0.3, 0.25, True) == [(0.0, 1.0, 0.0)] * 4
    assert is_cut(None, 0.9) is False and is_cut(0.05, 0.6) is True and is_cut(0.4, 0.5) is False


def test_vectors_file_is_up_to_date():
    path = os.path.join(ROOT, "tests", "vectors", "colour.json")
    generated = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "make_vectors.py"), "--stdout"],
                               capture_output=True, text=True, check=True).stdout
    with open(path, encoding="utf-8") as f:
        assert json.loads(generated) == json.load(f)

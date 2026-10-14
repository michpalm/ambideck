import os
import threading
import time

import pytest

from ambideck.lights import Lights, LightsHandle, find_hidraw, hidiocsfeature, mode_reports, zone_report


def test_zone_report_is_the_direct_mode_message():
    report = zone_report([(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 200, 0)])
    assert len(report) == 64
    assert report[:16] == bytes([0x5A, 0xD1, 0x08, 0x0C, 255, 0, 0, 0, 255, 0, 0, 0, 255, 255, 200, 0])
    assert report[16:] == bytes(48)


def test_zone_report_clamps_and_needs_four_zones():
    assert zone_report([(300, -5, 12.7)] * 4)[4:7] == bytes([255, 0, 12])
    with pytest.raises(ValueError):
        zone_report([(0, 0, 0)] * 3)


def test_rainbow_and_off_switch_the_controller_mode():
    rainbow = mode_reports("rainbow")
    assert [r[:2] for r in rainbow] == [b"\x5a\xba", b"\x5a\xb3", b"\x5a\xb5", b"\x5a\xb4"]
    assert rainbow[0][:5] == bytes([0x5A, 0xBA, 0xC5, 0xC4, 0x02])
    assert rainbow[1][:13] == bytes([0x5A, 0xB3, 0x00, 0x02, 0, 0, 0, 0xEB, 0, 0, 0, 0, 0])
    off = mode_reports("off")
    assert off[1][:13] == bytes([0x5A, 0xB3, 0x00, 0x00, 0, 0, 0, 0x00, 0, 0, 0, 0, 0])
    assert all(len(r) == 64 for r in rainbow + off)
    with pytest.raises(ValueError):
        mode_reports("disco")


def test_hidiocsfeature_matches_the_kernel_ioctl_number():
    assert hidiocsfeature(64) == 0xC0404806


def make_tree(tmp_path):
    devices = tmp_path / "devices"
    (devices / "hidA").mkdir(parents=True)
    (devices / "hidB").mkdir()
    leds = tmp_path / "class" / "leds" / "ally:rgb:joystick_rings"
    leds.mkdir(parents=True)
    os.symlink(devices / "hidA", leds / "device")
    for name, target in (("hidraw0", "hidB"), ("hidraw4", "hidA")):
        node = tmp_path / "class" / "hidraw" / name
        node.mkdir(parents=True)
        os.symlink(devices / target, node / "device")
    return tmp_path


def test_finds_the_hidraw_node_behind_the_led(tmp_path):
    assert find_hidraw(str(make_tree(tmp_path))) == "/dev/hidraw4"


def test_no_led_means_unsupported(tmp_path):
    assert find_hidraw(str(tmp_path)) is None


def test_lights_send_feature_reports():
    sent, closed = [], []
    lights = Lights("/dev/hidraw4", open_fn=lambda path, flags: 7,
                    ioctl_fn=lambda fd, req, data: sent.append((fd, req, bytes(data))), close_fn=closed.append)
    lights.show([(1, 2, 3)] * 4)
    lights.rainbow()
    lights.close()
    assert sent[0] == (7, 0xC0404806, zone_report([(1, 2, 3)] * 4))
    assert [s[2] for s in sent[1:]] == mode_reports("rainbow")
    assert closed == [7]


def test_handle_refinds_the_controller_after_a_failed_write(caplog):
    class Broken:
        def __init__(self):
            self.closed = False

        def show(self, zones):
            raise OSError(19, "No such device")

        def close(self):
            self.closed = True

    class Good:
        def __init__(self):
            self.shown = []

        def show(self, zones):
            self.shown.append(zones)

    clock, broken, good, found = {"t": 0.0}, Broken(), Good(), []
    h = LightsHandle(lambda: found.pop() if found else None, broken, clock=lambda: clock["t"])
    for _ in range(30):
        assert h.show([(1, 1, 1)] * 4) is False
    assert broken.closed
    assert len([r for r in caplog.records if "light controller" in r.getMessage()]) == 1
    found.append(good)
    clock["t"] = 1.9
    assert h.show([(1, 1, 1)] * 4) is False
    clock["t"] = 2.1
    assert h.show([(1, 1, 1)] * 4) is True and len(good.shown) == 1


def test_handle_closes_a_lost_controller_once_when_threads_race():
    class SlowBroken:
        def __init__(self):
            self.closes = 0

        def show(self, zones):
            time.sleep(0.05)
            raise OSError(19, "No such device")

        def close(self):
            self.closes += 1

    broken, errors = SlowBroken(), []
    h = LightsHandle(lambda: None, broken)

    def write():
        try:
            h.show([(1, 1, 1)] * 4)
        except Exception as error:  # an unlocked race shows up as AttributeError on None
            errors.append(error)

    threads = [threading.Thread(target=write) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(2)
    assert broken.closes == 1 and errors == []


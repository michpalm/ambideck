from ambideck.backend import Backend


class FakeLights:
    def __init__(self):
        self.calls = []

    def show(self, zones):
        self.calls.append(("show", [tuple(z) for z in zones]))

    def rainbow(self):
        self.calls.append(("rainbow",))

    def off(self):
        self.calls.append(("off",))


class FakeCapture:
    def __init__(self, on_frame, on_state, max_hz, ok=True):
        self.on_frame, self.ok, self.stopped = on_frame, ok, False

    def start(self):
        if self.ok:
            for _ in range(3):
                self.on_frame(b"\0" * 16, 2, 2, 8)
        return self.ok

    def stop(self):
        self.stopped = True


def make(lights=None, huesync=True, capture_ok=True):
    events = []
    backend = Backend(find_lights=lambda: lights, docked=lambda: False, charger=lambda: True, emit=lambda *a: events.append(a),
                      make_capture=lambda f, s, hz: FakeCapture(f, s, hz, capture_ok),
                      huesync_installed=lambda: huesync)
    return backend, events


def test_status_reports_support_and_docked():
    assert make(FakeLights())[0].status() == {"supported": True, "docked": False, "onCharger": True}
    assert make(None)[0].status() == {"supported": False, "docked": False, "onCharger": True}


def test_show_rainbow_off_reach_the_controller():
    lights = FakeLights()
    backend, _ = make(lights)
    backend.show([[1, 2, 3], [4, 5, 6], [7, 8, 9], [10, 11, 12]])
    backend.rainbow()
    backend.off()
    assert lights.calls == [("show", [(1, 2, 3), (4, 5, 6), (7, 8, 9), (10, 11, 12)]), ("rainbow",), ("off",)]


def test_unsupported_device_ignores_commands():
    backend, _ = make(None)
    backend.show([[1, 2, 3]] * 4)
    backend.rainbow()


def test_shutdown_restores_rainbow_only_without_huesync_and_only_when_ours():
    lights = FakeLights()
    backend, _ = make(lights, huesync=False)
    backend.shutdown()
    assert lights.calls == []
    backend.show([[1, 1, 1]] * 4)
    backend.shutdown()
    assert lights.calls[-1] == ("rainbow",)
    lights2 = FakeLights()
    backend2, _ = make(lights2, huesync=True)
    backend2.show([[1, 1, 1]] * 4)
    backend2.shutdown()
    assert lights2.calls[-1][0] == "show"



class FollowCapture(FakeCapture):
    def start(self):
        return True


def test_follow_starts_and_show_stops_following():
    lights = FakeLights()
    caps = []
    backend = Backend(find_lights=lambda: lights, docked=lambda: False, charger=lambda: False, emit=lambda *a: None,
                      make_capture=lambda f, s, hz: caps.append(FollowCapture(f, s, hz)) or caps[-1],
                      huesync_installed=lambda: True)
    assert backend.follow({"layout": "sides"}) is True
    assert len(caps) == 1
    backend.show([[1, 1, 1]] * 4)
    assert caps[0].stopped
    assert make(None)[0].follow({}) is False


def test_static_colours_are_resent_every_two_seconds_until_something_else_takes_over():
    lights = FakeLights()
    clock = {"t": 0.0}
    backend = Backend(find_lights=lambda: lights, docked=lambda: False, charger=lambda: False, emit=lambda *a: None,
                      make_capture=lambda f, s, hz: FakeCapture(f, s, hz), huesync_installed=lambda: True,
                      clock=lambda: clock["t"])
    backend.show([[1, 2, 3]] * 4)
    clock["t"] = 1.0
    backend.tick()
    assert len(lights.calls) == 1
    clock["t"] = 2.1
    backend.tick()
    assert lights.calls[-1] == ("show", [(1, 2, 3)] * 4) and len(lights.calls) == 2
    backend.off()
    clock["t"] = 4.2
    backend.tick()
    assert lights.calls[-2:] == [("off",), ("off",)]
    backend.stop()
    clock["t"] = 9.0
    backend.tick()
    assert lights.calls[-1] == ("off",) and len(lights.calls) == 4


def test_following_replaces_static_colours():
    lights = FakeLights()
    clock = {"t": 0.0}
    backend = Backend(find_lights=lambda: lights, docked=lambda: False, charger=lambda: False, emit=lambda *a: None,
                      make_capture=lambda f, s, hz: FollowCapture(f, s, hz), huesync_installed=lambda: True,
                      clock=lambda: clock["t"])
    backend.show([[9, 9, 9]] * 4)
    backend.follow({})
    clock["t"] = 3.0
    backend.tick()
    assert [c for c in lights.calls if c[0] == "show"] == [("show", [(9, 9, 9)] * 4)]


class FailingCapture(FakeCapture):
    def start(self):
        return False


def test_rainbow_while_waiting_keeps_retrying():
    lights = FakeLights()
    clock = {"t": 0.0}
    caps = []
    backend = Backend(find_lights=lambda: lights, docked=lambda: False, charger=lambda: False, emit=lambda *a: None,
                      make_capture=lambda f, s, hz: caps.append(FailingCapture(f, s, hz)) or caps[-1],
                      huesync_installed=lambda: False, clock=lambda: clock["t"])
    backend.follow({})
    backend.rainbow(keep_following=True)
    assert lights.calls[-1] == ("rainbow",)
    clock["t"] = 6.0
    backend.tick()
    assert len(caps) == 2  # still retrying
    backend.rainbow()
    clock["t"] = 20.0
    backend.tick()
    assert len(caps) == 2  # a plain rainbow() ends following

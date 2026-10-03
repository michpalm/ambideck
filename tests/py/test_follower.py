from ambideck.colour import Smoother, analyse, quad_frame, to_led
from ambideck.follower import Follower, clean_settings


class FakeLights:
    def __init__(self):
        self.shown = []

    def show(self, zones):
        self.shown.append([tuple(z) for z in zones])


class FakeCapture:
    instances = []

    def __init__(self, on_frame, on_state, max_hz, ok=True):
        self.on_frame, self.on_state, self.max_hz, self.ok = on_frame, on_state, max_hz, ok
        self.started = self.stopped = False
        FakeCapture.instances.append(self)

    def start(self):
        self.started = True
        return self.ok

    def stop(self):
        self.stopped = True

    def set_max_hz(self, hz):
        self.max_hz = hz


def make(ok=True):
    FakeCapture.instances = []
    clock = {"t": 0.0}
    events, lights = [], FakeLights()
    f = Follower(lambda fr, st, hz: FakeCapture(fr, st, hz, ok), lights, lambda *a: events.append(a),
                 clock=lambda: clock["t"])
    return f, lights, events, clock


FRAME = quad_frame(16, 8, [(0, 0, 255), (255, 0, 0), (0, 255, 0), (255, 255, 0)])


def expected_leds(settings):
    a = analyse(FRAME, 16, 8, 64, settings["layout"], settings["boost"], settings["brightness"])
    return [to_led(t) for t in Smoother().step(a.targets, 0.0, 0.25, True)]


def test_clean_settings_fills_defaults_and_clamps():
    assert clean_settings({}) == {"layout": "corners", "brightness": 70, "boost": 58, "speed": "balanced"}
    assert clean_settings({"layout": "sides", "brightness": 500, "boost": -3, "speed": "fast"}) == \
        {"layout": "sides", "brightness": 100, "boost": 0, "speed": "fast"}
    assert clean_settings({"layout": "x", "speed": "y", "brightness": "a"})["layout"] == "corners"


def test_frames_become_zone_colours():
    f, lights, events, _ = make()
    f.start()
    cap = FakeCapture.instances[0]
    cap.on_state("streaming")
    cap.on_frame(FRAME, 16, 8, 64)
    assert events == [("follow_state", "following")]
    assert lights.shown == [expected_leds(clean_settings({}))]


def test_unchanged_colours_are_resent_only_every_two_seconds():
    f, lights, _, clock = make()
    f.start()
    cap = FakeCapture.instances[0]
    cap.on_state("streaming")
    cap.on_frame(FRAME, 16, 8, 64)
    clock["t"] = 0.5
    cap.on_frame(FRAME, 16, 8, 64)
    f.tick()
    assert len(lights.shown) == 1
    clock["t"] = 2.1
    f.tick()
    assert len(lights.shown) == 2


def test_lost_stream_waits_and_retries():
    f, _, events, clock = make()
    f.start()
    first = FakeCapture.instances[0]
    first.on_state("streaming")
    first.on_state("error")
    f.tick()
    assert first.stopped and events[-1] == ("follow_state", "waiting")
    clock["t"] = 4.0
    f.tick()
    assert len(FakeCapture.instances) == 1
    clock["t"] = 5.1
    f.tick()
    assert len(FakeCapture.instances) == 2 and FakeCapture.instances[1].started


def test_missing_stream_at_start_waits():
    f, _, events, _ = make(ok=False)
    f.start()
    assert events == [("follow_state", "waiting")] and f.active


def test_speed_sets_the_analysis_rate_and_stop_releases_capture():
    f, _, _, _ = make()
    f.start()
    f.update({"speed": "fast"})
    cap = FakeCapture.instances[0]
    assert cap.max_hz == 30.0
    f.stop()
    assert cap.stopped and not f.active


def test_stop_during_a_slow_reconnect_does_not_leak_a_capture():
    holder = {}

    class RacingCapture(FakeCapture):
        def start(self):
            holder["f"].stop()  # user switches off while pw-dump/connect is still running
            return super().start()

    FakeCapture.instances = []
    lights = FakeLights()
    f = Follower(lambda fr, st, hz: RacingCapture(fr, st, hz), lights, lambda *a: None, clock=lambda: 0.0)
    holder["f"] = f
    f.start()
    cap = FakeCapture.instances[0]
    assert cap.stopped and not f.active
    cap.on_state("streaming")
    cap.on_frame(FRAME, 16, 8, 64)
    assert lights.shown == []


def test_frames_after_stop_are_dropped():
    f, lights, _, _ = make()
    f.start()
    cap = FakeCapture.instances[0]
    f.stop()
    cap.on_frame(FRAME, 16, 8, 64)
    assert lights.shown == []

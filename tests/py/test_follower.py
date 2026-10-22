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

def test_waiting_pauses_periodic_rgb_before_huesync_can_restore():
    order, clock = [], [0.0]
    class ManagedLights(FakeLights):
        def pause(self): order.append('pause')
        def begin_follow(self): order.append('begin')
    lights = ManagedLights()
    f = Follower(lambda fr, st, hz: FakeCapture(fr, st, hz), lights,
                 lambda event, state: order.append(state), clock=lambda: clock[0])
    f.start()
    first = FakeCapture.instances[-1]
    first.on_state('streaming'); first.on_state('error'); f.tick()
    assert order[-2:] == ['pause', 'waiting']
    assert f.active
    clock[0] = 5.1; f.tick()
    FakeCapture.instances[-1].on_state('streaming')
    assert order[-2:] == ['begin', 'following']


def expected_leds(settings):
    a = analyse(FRAME, 16, 8, 64, settings["layout"], settings["boost"], settings["brightness"])
    return [to_led(t) for t in Smoother().step(a.targets, 0.0, 0.25, True)]


def test_clean_settings_fills_defaults_and_clamps():
    assert clean_settings({}) == {"layout": "corners", "brightness": 70, "boost": 58, "speed": "balanced", "dark": "glow"}
    assert clean_settings({"layout": "sides", "brightness": 500, "boost": -3, "speed": "fast"}) == \
        {"layout": "sides", "brightness": 100, "boost": 0, "speed": "fast", "dark": "glow"}
    assert clean_settings({"dark": "off"})["dark"] == "off"
    assert clean_settings({"dark": "x"})["dark"] == "glow"
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


DARK_FRAME = quad_frame(16, 8, [(0, 0, 0), (255, 0, 0), (0, 255, 0), (0, 0, 255)])


def test_dark_scenes_off_blacks_out_only_the_dark_zone():
    for dark, expect_off in (("off", True), ("glow", False)):
        f, lights, _, _ = make()
        f.update({"dark": dark})
        f.start()
        cap = FakeCapture.instances[0]
        cap.on_state("streaming")
        cap.on_frame(DARK_FRAME, 16, 8, 64)
        leds = lights.shown[-1]
        assert (sum(leds[0]) == 0) == expect_off
        assert all(sum(z) > 0 for z in leds[1:])


def test_a_write_that_did_not_happen_is_tried_again():
    f, lights, _, clock = make()
    lights.show = lambda zones: False
    f.start()
    cap = FakeCapture.instances[0]
    cap.on_state("streaming")
    cap.on_frame(FRAME, 16, 8, 64)
    assert f._last_leds is None


def test_streaming_reported_during_start_is_kept():
    class EagerCapture(FakeCapture):
        def start(self):
            self.on_state("streaming")
            return True

    FakeCapture.instances, events = [], []
    f = Follower(lambda fr, st, hz: EagerCapture(fr, st, hz), FakeLights(), lambda *a: events.append(a),
                 clock=lambda: 0.0)
    f.start()
    assert f._state == "following" and events == [("follow_state", "following")]


def test_retries_stay_five_seconds_apart():
    f, _, _, clock = make(ok=False)
    f.start()
    clock["t"] = 5.4
    f.tick()
    clock["t"] = 10.1
    f.tick()
    assert len(FakeCapture.instances) == 3


def test_a_stream_that_never_starts_is_retried():
    f, _, events, clock = make()
    f.start()
    clock["t"] = 9.9
    f.tick()
    assert not FakeCapture.instances[0].stopped
    clock["t"] = 10.1
    f.tick()
    assert FakeCapture.instances[0].stopped and events[-1] == ("follow_state", "waiting")


def test_a_tick_during_a_slow_start_does_not_time_out():
    holder, clock = {}, {"t": 20.0}

    class SlowStart(FakeCapture):
        def start(self):
            holder["f"].tick()  # the worker ticks while pw-dump is still running
            return super().start()

    FakeCapture.instances, events = [], []
    f = Follower(lambda fr, st, hz: SlowStart(fr, st, hz), FakeLights(), lambda *a: events.append(a),
                 clock=lambda: clock["t"])
    holder["f"] = f
    f.start()
    assert events == [] and not FakeCapture.instances[0].stopped


def test_a_reconnect_never_leaves_the_old_capture_running():
    holder, clock = {}, {"t": 0.0}

    class LostDuringStart(FakeCapture):
        def start(self):
            if len(FakeCapture.instances) == 1:
                self.on_state("error")
                holder["f"].tick()
            return super().start()

    FakeCapture.instances = []
    f = Follower(lambda fr, st, hz: LostDuringStart(fr, st, hz), FakeLights(), lambda *a: None,
                 clock=lambda: clock["t"])
    holder["f"] = f
    f.start()
    clock["t"] = 5.1
    f.tick()
    assert len(FakeCapture.instances) == 2 and FakeCapture.instances[0].stopped


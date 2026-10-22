import threading
import time

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


def make(lights=None, huesync=True, capture_ok=True, **kwargs):
    events = []
    backend = Backend(find_lights=lambda: lights, docked=lambda: False, charger=lambda: True, emit=lambda *a: events.append(a),
                      make_capture=lambda f, s, hz: FakeCapture(f, s, hz, capture_ok),
                      huesync_installed=lambda: huesync, **kwargs)
    return backend, events


def test_status_reports_support_and_docked():
    assert make(FakeLights())[0].status() == {"supported": True, "docked": False, "onCharger": True, "capturing": False}
    assert make(None)[0].status() == {"supported": False, "docked": False, "onCharger": True, "capturing": False}


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


def test_off_waits_for_a_resend_in_progress():
    gate, started = threading.Event(), threading.Event()

    class SlowLights(FakeLights):
        def show(self, zones):
            started.set()
            gate.wait(2)
            super().show(zones)

    lights, clock = SlowLights(), {"t": 0.0}
    backend = Backend(find_lights=lambda: lights, docked=lambda: False, charger=lambda: False,
                      emit=lambda *a: None, make_capture=lambda f, s, hz: FakeCapture(f, s, hz),
                      huesync_installed=lambda: True, clock=lambda: clock["t"])
    gate.set()
    backend.show([[1, 1, 1]] * 4)
    gate.clear()
    started.clear()
    clock["t"] = 2.1
    worker = threading.Thread(target=backend.tick)
    worker.start()
    assert started.wait(2)
    off = threading.Thread(target=backend.off)
    off.start()
    time.sleep(0.05)
    gate.set()
    worker.join(2)
    off.join(2)
    assert lights.calls[-1] == ("off",)


def test_shutdown_joins_the_worker():
    backend, _ = make(FakeLights())
    backend.start_worker()
    backend.shutdown()
    assert not backend._worker.is_alive()


def locked_backend(capture_cls, locked):
    clock = {"t": 0.0}
    caps, events = [], []
    backend = Backend(find_lights=FakeLights, docked=lambda: False, charger=lambda: False,
                      emit=lambda *a: events.append(a),
                      make_capture=lambda f, s, hz: caps.append(capture_cls(f, s, hz)) or caps[-1],
                      huesync_installed=lambda: True, clock=lambda: clock["t"],
                      capture_locked=lambda: locked["on"])
    return backend, clock, caps, events


def test_lock_stops_following_and_emits():
    locked = {"on": False}
    backend, clock, caps, events = locked_backend(FollowCapture, locked)
    assert backend.follow({}) is True
    locked["on"] = True
    clock["t"] = 0.6
    backend.tick()
    assert caps[0].stopped
    assert ("capture_lock", True) in events
    assert backend.status()["capturing"] is True


def test_follow_refused_while_locked():
    backend, _clock, caps, _events = locked_backend(FollowCapture, {"on": True})
    assert backend.follow({}) is False
    assert caps == []


def test_lock_stops_a_retrying_follower():
    locked = {"on": False}
    backend, clock, caps, _events = locked_backend(FailingCapture, locked)
    backend.follow({})
    backend.rainbow(keep_following=True)
    locked["on"] = True
    clock["t"] = 0.6
    backend.tick()
    made = len(caps)
    for t in (6.0, 12.0, 20.0):
        clock["t"] = t
        backend.tick()
    assert len(caps) == made


def test_unlock_emits_and_follow_works_again():
    locked = {"on": True}
    backend, clock, caps, events = locked_backend(FollowCapture, locked)
    locked["on"] = False
    clock["t"] = 0.6
    backend.tick()
    assert ("capture_lock", False) in events
    assert backend.follow({}) is True and len(caps) == 1


def test_follow_reads_the_lock_fresh_between_polls():
    locked = {"on": False}
    backend, clock, caps, _events = locked_backend(FollowCapture, locked)
    clock["t"] = 0.6
    backend.tick()  # watcher saw no lock
    locked["on"] = True  # the recorder locks before the next poll
    clock["t"] = 0.9
    assert backend.follow({}) is False
    assert caps == []

class ManagedLights(FakeLights):
    def __init__(self):
        super().__init__()
        self.available = False
        self.closed = False
    def status(self):
        return {'supported': self.available, 'deviceName': 'Claw' if self.available else None,
                'hueSync': False, 'unavailableReason': None if self.available else 'Disconnected'}
    def begin_follow(self): self.calls.append(('begin',))
    def fallback(self, keep_following=False): self.calls.append(('fallback', keep_following)); return True
    def pause(self): self.calls.append(('pause',))
    def close(self): self.closed = True

def test_status_tracks_managed_device_and_emits_only_changes():
    lights = ManagedLights()
    backend, events = make(lights)
    assert backend.status()['supported'] is False
    assert backend.follow({}) is False
    backend.tick(); events.clear()
    lights.available = True; backend.tick(); backend.tick()
    changes = [e for e in events if e[0] == 'lights_status']
    assert len(changes) == 1 and changes[0][1]['deviceName'] == 'Claw'
    assert backend.status()['supported'] is True

def test_non_ally_shutdown_falls_back_even_with_huesync_installed_and_closes():
    lights = ManagedLights(); lights.available = True
    backend, _ = make(lights, huesync=True)
    backend.show([[1, 2, 3]] * 4)
    backend.shutdown()
    assert ('fallback', False) in lights.calls and lights.closed

def test_temporary_fallback_keeps_capture_retrying():
    lights = ManagedLights(); lights.available = True
    backend, _ = make(lights, capture_ok=False)
    backend.follow({})
    backend.fallback(True)
    assert backend._follower.active
    assert lights.calls[-1] == ('fallback', True)

def test_stop_cancels_the_output_writer_before_huesync_handback():
    lights = ManagedLights(); lights.available = True
    backend, _ = make(lights)
    backend.show([[1, 2, 3]] * 4)
    backend.stop()
    assert lights.calls[-1] == ('pause',)

def test_delayed_waiting_fallback_cannot_disable_a_resumed_stream():
    from ambideck.rgb.output import OutputWorker
    from ambideck.rgb.factory import Detection
    from test_rgb_output import Device, eventually
    device = Device()
    output = OutputWorker(lambda: Detection(device)); output.start()
    try:
        eventually(lambda: output.status()['supported'])
        backend, _ = make(output, capture_ok=False)
        backend.follow({})
        backend._follower.on_state('streaming')
        backend.fallback(keep_following=True)  # delayed RPC from the previous waiting event
        assert output.show(((10, 20, 30),) * 4)
        eventually(lambda: ('show', ((10, 20, 30),) * 4) in device.sent)
    finally:
        output.close()

def test_recorder_ticks_preserve_fallback_while_controller_settles():
    from ambideck.rgb.output import OutputWorker
    from ambideck.rgb.factory import Detection
    from test_rgb_output import Device, eventually
    device, clock = Device(), [0.0]
    device.ready_at = 2.0
    output = OutputWorker(lambda: Detection(device), clock=lambda: clock[0]); output.start()
    backend, _ = make(output, capture_locked=lambda: True, clock=lambda: clock[0])
    try:
        eventually(lambda: output.status()['supported'])
        backend.fallback()
        for t in (0.6, 1.2, 1.8):
            clock[0] = t; backend.tick()
        assert device.sent == []
        clock[0] = 2.1; backend.tick()
        eventually(lambda: bool(device.sent))
        assert device.sent == [('show', ((64, 64, 64),) * 4)]
    finally:
        backend.shutdown()

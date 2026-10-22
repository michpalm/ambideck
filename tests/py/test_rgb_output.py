import threading
import time
import pytest
from ambideck.rgb.output import OutputWorker
from ambideck.rgb.factory import Detection
from ambideck.rgb.model import DeviceInfo

class Device:
    def __init__(self, hz=10, rainbow=False):
        self.info = DeviceInfo('Test', 'shared', hz, rainbow)
        self.sent, self.closed = [], 0
        self.changed = threading.Event()
        self.block = None
        self.fail = False
    def show(self, zones):
        if self.block: self.block.wait(1)
        if self.fail: raise OSError('unplugged')
        self.sent.append(('show', zones)); self.changed.set()
    def off(self): self.sent.append(('off',)); self.changed.set()
    def rainbow(self): self.sent.append(('rainbow',)); self.changed.set()
    def close(self): self.closed += 1

def eventually(fn):
    deadline = time.monotonic() + 2
    while not fn() and time.monotonic() < deadline: time.sleep(.002)
    assert fn()

@pytest.mark.parametrize('hz', [5, 10, 30])
def test_coalesces_and_enforces_each_device_rate(hz):
    d, clock = Device(hz), [0.0]
    w = OutputWorker(lambda: Detection(d), clock=lambda: clock[0]); w.start()
    try:
        w.show(((1, 2, 3),) * 4)
        eventually(lambda: len(d.sent) == 1)
        for i in range(100): w.show(((i, i, i),) * 4)
        time.sleep(.02)
        assert len(d.sent) == 1
        clock[0] = 1 / hz
        w.show(((99, 99, 99),) * 4)
        eventually(lambda: len(d.sent) == 2)
        assert d.sent[-1] == ('show', ((99, 99, 99),) * 4)
    finally: w.close()
    assert d.closed == 1

def test_static_fallback_uses_last_completed_screen_colour():
    d = Device(); w = OutputWorker(lambda: Detection(d)); w.start()
    try:
        w.fallback()
        eventually(lambda: bool(d.sent))
        assert d.sent[-1] == ('show', ((64, 64, 64),) * 4)
        w.begin_follow()
        w.show(((0, 0, 0), (1, 3, 5), (10, 20, 30), (11, 21, 31)))
        eventually(lambda: len(d.sent) == 2)
        w.fallback()
        eventually(lambda: len(d.sent) == 3)
        assert d.sent[-1] == ('show', ((6, 11, 17),) * 4)
        assert not w.show(((255, 0, 0),) * 4)
    finally: w.close()

def test_native_rainbow_and_off_cancel_queued_frames():
    d = Device(rainbow=True); d.block = threading.Event()
    w = OutputWorker(lambda: Detection(d)); w.start()
    w.show(((10, 20, 30),) * 4)
    time.sleep(.02)
    w.show(((255, 0, 0),) * 4)
    w.fallback(); w.off()
    d.block.set()
    eventually(lambda: ('off',) in d.sent)
    assert ('show', ((255, 0, 0),) * 4) not in d.sent
    assert not w.show(((255, 0, 0),) * 4)
    w.fallback()
    eventually(lambda: d.sent[-1] == ('rainbow',))
    w.close()

def test_startup_absence_retry_and_error_do_not_overwrite_fallback_colour():
    d, clock, available = Device(), [0.0], [False]
    threads = []
    def find():
        threads.append(threading.get_ident())
        return Detection(d if available[0] else None, 'not connected')
    w = OutputWorker(find, clock=lambda: clock[0]); w.start()
    try:
        eventually(lambda: bool(threads))
        assert not w.status()['supported']
        available[0] = True; clock[0] = 2.1
        w.show(((10, 20, 30),) * 4)
        eventually(lambda: bool(d.sent))
        assert w.status()['supported'] and all(t != threading.get_ident() for t in threads)
        d.fail = True; clock[0] = 2.3
        w.show(((255, 0, 0),) * 4)
        eventually(lambda: d.closed == 1)
        assert not w.status()['supported']
        d2 = Device()
        w._find = lambda: Detection(d2)
        clock[0] = 4.5; w.fallback()
        eventually(lambda: bool(d2.sent))
        assert d2.sent[-1] == ('show', ((10, 20, 30),) * 4)
    finally: w.close()

def test_closed_worker_rejects_submissions_and_closes_without_hardware():
    w = OutputWorker(lambda: Detection(None, 'unavailable')); w.start(); w.close(); w.close()
    assert not w.show(((1, 2, 3),) * 4)

def test_pause_is_a_barrier_before_another_rgb_owner_takes_over():
    d = Device(); w = OutputWorker(lambda: Detection(d)); w.start()
    w.show(((1, 2, 3),) * 4)
    eventually(lambda: bool(d.sent))
    w.pause()
    assert not w.show(((255, 0, 0),) * 4)
    assert d.sent == [('show', ((1, 2, 3),) * 4)]
    w.close()
    assert d.sent == [('show', ((1, 2, 3),) * 4)]

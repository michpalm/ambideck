import os
import pytest
from ambideck.rgb.transport import HidTransport
from ambideck.rgb.transport import SerialTransport

def test_hid_writes_report_atomically_and_closes_once(monkeypatch):
    sent, closed = [], []
    monkeypatch.setattr(os, 'open', lambda *args: 7)
    monkeypatch.setattr(os, 'write', lambda fd, data: sent.append((fd, data)) or len(data))
    monkeypatch.setattr(os, 'close', closed.append)
    h = HidTransport('/dev/hidraw0')
    h.write(b'\x01\x02')
    h.close(); h.close()
    assert sent == [(7, b'\x01\x02')] and closed == [7]

def test_hid_short_write_is_an_io_error(monkeypatch):
    monkeypatch.setattr(os, 'open', lambda *args: 7)
    monkeypatch.setattr(os, 'write', lambda *args: 1)
    h = HidTransport('/dev/hidraw0')
    with pytest.raises(OSError, match='Short'):
        h.write(b'\x01\x02')

def test_serial_handles_partial_writes_and_exclusive_conflict(monkeypatch):
    import termios, fcntl
    writes, closes = [], []
    monkeypatch.setattr(os, 'open', lambda *args: 7)
    monkeypatch.setattr(os, 'close', closes.append)
    monkeypatch.setattr(termios, 'tcgetattr', lambda fd: [0, 0, 0, 0, 0, 0, [0] * 32])
    monkeypatch.setattr(termios, 'tcsetattr', lambda *args: None)
    monkeypatch.setattr(fcntl, 'flock', lambda *args: None)
    monkeypatch.setattr(os, 'write', lambda fd, data: writes.append(bytes(data)) or 1)
    t = SerialTransport('/dev/ttyUSB0')
    t.write(b'abc'); t.close(); t.close()
    assert writes == [b'abc', b'bc', b'c'] and closes == [7]
    def busy(*args): raise BlockingIOError('busy')
    monkeypatch.setattr(fcntl, 'flock', busy)
    with pytest.raises(OSError): SerialTransport('/dev/ttyUSB0')
    assert closes == [7, 7]

def test_serial_backpressure_has_a_deadline(monkeypatch):
    import termios, fcntl, time
    monkeypatch.setattr(os, 'open', lambda *args: 7)
    monkeypatch.setattr(os, 'close', lambda *args: None)
    monkeypatch.setattr(termios, 'tcgetattr', lambda fd: [0, 0, 0, 0, 0, 0, [0] * 32])
    monkeypatch.setattr(termios, 'tcsetattr', lambda *args: None)
    monkeypatch.setattr(fcntl, 'flock', lambda *args: None)
    def blocked(*args): raise BlockingIOError('not writable')
    monkeypatch.setattr(os, 'write', blocked)
    ticks = iter((0.0, 0.0, 0.3))
    monkeypatch.setattr(time, 'monotonic', lambda: next(ticks))
    monkeypatch.setattr('select.select', lambda *args: ([], [], []))
    with pytest.raises(OSError, match='deadline'): SerialTransport('/dev/ttyUSB0').write(b'a')

def test_termios_disconnect_obeys_the_transport_oserror_contract(monkeypatch):
    import termios, fcntl
    closed = []
    monkeypatch.setattr(os, 'open', lambda *args: 7)
    monkeypatch.setattr(os, 'close', closed.append)
    monkeypatch.setattr(fcntl, 'flock', lambda *args: None)
    def disconnected(*args): raise termios.error(5, 'Input/output error')
    monkeypatch.setattr(termios, 'tcgetattr', disconnected)
    with pytest.raises(OSError, match='Serial RGB configuration'):
        SerialTransport('/dev/ttyUSB0')
    assert closed == [7]

def test_discovery_recovers_after_a_termios_failure(monkeypatch):
    import termios, fcntl
    from ambideck.rgb.output import OutputWorker
    from ambideck.rgb.factory import Detection
    from ambideck.rgb.oxp import OxpLights
    from ambideck.rgb.model import DeviceInfo
    from test_rgb_output import eventually
    attempts, clock = [], [0.0]
    monkeypatch.setattr(os, 'open', lambda *args: 7)
    monkeypatch.setattr(os, 'close', lambda *args: None)
    monkeypatch.setattr(fcntl, 'flock', lambda *args: None)
    monkeypatch.setattr(termios, 'tcsetattr', lambda *args: None)
    def attributes(fd):
        attempts.append(fd)
        if len(attempts) == 1: raise termios.error(5, 'Input/output error')
        return [0, 0, 0, 0, 0, 0, [0] * 32]
    monkeypatch.setattr(termios, 'tcgetattr', attributes)
    def find():
        return Detection(OxpLights(SerialTransport('/dev/ttyUSB0'), DeviceInfo('X1', 'shared', 5, False), 'serial'))
    output = OutputWorker(find, clock=lambda: clock[0]); output.start()
    try:
        eventually(lambda: len(attempts) == 1)
        assert not output.status()['supported']
        clock[0] = 2.1
        eventually(lambda: output.status()['supported'])
        assert len(attempts) == 2
    finally: output.close()

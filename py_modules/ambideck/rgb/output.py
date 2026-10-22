"""One writer owns discovery and I/O; capture threads only replace a pending frame."""
import logging
import threading
import time
from .factory import Detection
from .model import clean_zones, map_zones, shared_colour

log = logging.getLogger('ambideck')

class OutputWorker:
    def __init__(self, find, clock=time.monotonic):
        self._find, self._clock = find, clock
        self._cv = threading.Condition()
        self._thread = None
        self._device = None
        self._reason = 'Looking for a compatible RGB interface'
        self._retry_at = 0.0
        self._last_good = None
        self._sent_key = None
        self._sent_at = float('-inf')
        self._command = ('idle', None)
        self._version = 0
        self._pending = False
        self._accept = True
        self._closing = False
        self._closed = False
        self._busy = False

    def start(self):
        with self._cv:
            if self._thread is not None or self._closed: return
            self._thread = threading.Thread(target=self._run, name='ambideck-rgb', daemon=True)
            self._thread.start()

    def begin_follow(self):
        with self._cv:
            if not self._closing and not self._closed: self._accept = True

    def submit(self, zones):
        zones = clean_zones(zones)
        with self._cv:
            if not self._accept or self._closing or self._closed: return False
            self._command = ('show', zones)
            self._version += 1
            self._pending = True
            self._cv.notify()
            return True

    show = submit

    def _mode(self, mode):
        with self._cv:
            if self._closing or self._closed: return False
            self._accept = False
            self._command = (mode, None)
            self._version += 1
            self._pending = True
            self._cv.notify()
            return True

    def fallback(self, keep_following=False):
        # Resumption is explicit (begin_follow); old callbacks cannot overtake this command.
        return self._mode('fallback')

    rainbow = fallback

    def off(self): return self._mode('off')

    def pause(self):
        """Cancel queued/periodic output and wait for an in-flight write before handback."""
        with self._cv:
            self._accept = False
            self._command = ('idle', None)
            self._version += 1
            self._pending = False
            self._cv.notify()
            deadline = time.monotonic() + 2
            while self._busy:
                remaining = deadline - time.monotonic()
                if remaining <= 0: raise OSError('RGB handback timed out')
                self._cv.wait(remaining)

    def status(self):
        with self._cv:
            info = self._device.info if self._device else None
            return {'supported': info is not None, 'deviceName': info.name if info else None,
                    'deviceLayout': info.layout if info else None, 'hueSync': bool(info and info.huesync),
                    'unavailableReason': self._reason if not info else None}

    def close(self):
        with self._cv:
            if self._closed: return
            if self._command[0] == 'show':
                self._command = ('fallback', None)
                self._version += 1
                self._pending = True
            self._closing = True
            self._accept = False
            self._cv.notify()
            thread = self._thread
        if thread and thread is not threading.current_thread(): thread.join(2)

    @staticmethod
    def _close_device(device):
        if device:
            try: device.close()
            except OSError: log.debug('RGB descriptor already unavailable', exc_info=True)

    def _run(self):
        try:
            self._loop()
        finally:
            with self._cv:
                device, self._device = self._device, None
                self._closed = True
            self._close_device(device)

    def _loop(self):
        while True:
            now = self._clock()
            with self._cv:
                if self._closing and (not self._device or not self._pending): return
                discover = self._device is None and now >= self._retry_at
            if discover:
                try:
                    result = self._find()
                except OSError as error:
                    result = Detection(None, str(error))
                with self._cv:
                    self._device, self._reason = result.device, result.reason
                    self._retry_at = self._clock() + 2.0
                    self._sent_key = None
                    self._sent_at = float('-inf')
                    if result.device and self._command[0] != 'idle': self._pending = True
                continue
            with self._cv:
                device = self._device
                mode, zones = self._command
                version = self._version
                now = self._clock()
                resend = mode == 'show' and now - self._sent_at >= 2.0
                if not device or (not self._pending and not resend) or mode == 'idle':
                    self._cv.wait(.1)
                    continue
                ready = getattr(device, 'ready_at', 0.0)
                if now < ready:
                    if self._closing: return  # no colours were sent to a not-yet-ready device
                    self._cv.wait(min(.1, ready - now))
                    continue
                if mode == 'show':
                    wait = 1.0 / device.info.max_hz - (now - self._sent_at)
                    if wait > 0:
                        self._cv.wait(min(.1, wait))
                        continue
                    key = map_zones(zones, device.info.layout)
                    if key == self._sent_key and not resend:
                        self._pending = False
                        continue
                self._busy = True
            # No condition lock held across I/O; producers never wait for hardware.
            try:
                if mode == 'show': device.show(zones)
                elif mode == 'off': device.off()
                elif device.info.native_rainbow: device.rainbow()
                else:
                    colour = shared_colour(self._last_good) if self._last_good else (64, 64, 64)
                    device.show((colour,) * 4)
            except OSError as error:
                self._close_device(device)
                with self._cv:
                    self._busy = False
                    self._cv.notify_all()
                    self._device = None
                    self._reason = f'{device.info.name}: {error}'
                    self._retry_at = self._clock() + 2.0
                    self._pending = True
                log.warning('[ambideck] RGB interface unavailable: %s', error)
                continue
            with self._cv:
                self._busy = False
                self._cv.notify_all()
                if mode == 'show':
                    self._last_good = zones
                    self._sent_key = key
                    self._sent_at = self._clock()
                else:
                    self._sent_key = None
                if version == self._version: self._pending = False

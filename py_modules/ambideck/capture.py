"""Read small frames from gamescope's PipeWire stream through libpipewire (ctypes, nothing to compile).

gamescope shrinks the image on the GPU when asked through its "requested size" format field, so each frame is a
few kilobytes. Buffers are always queued straight back: holding them makes gamescope log "out of buffers".
"""
from __future__ import annotations

import ctypes as C
import json
import os
import subprocess
import threading
import time
from typing import Callable

from .pods import SPA_PARAM_Format, enum_format, parse_format

PW_DIRECTION_INPUT = 0
PW_ID_ANY = 0xFFFFFFFF
PW_STREAM_FLAG_AUTOCONNECT, PW_STREAM_FLAG_MAP_BUFFERS = 1 << 0, 1 << 2
SPA_CHUNK_FLAG_CORRUPTED = 1
STATES = {-1: "error", 0: "unconnected", 1: "connecting", 2: "paused", 3: "streaming"}


def find_video_serial(dump: list) -> int | None:
    for obj in dump:
        props = ((obj or {}).get("info") or {}).get("props") or {}
        if props.get("node.name") == "gamescope" and props.get("media.class") == "Video/Source":
            return props.get("object.serial")
    return None


def session_env(uid: int) -> dict[str, str]:
    runtime = f"/run/user/{uid}"
    return {"XDG_RUNTIME_DIR": runtime, "PIPEWIRE_RUNTIME_DIR": runtime}


def subprocess_env(environ: dict) -> dict:
    """Environment for system binaries: Decky's bundled interpreter points LD_LIBRARY_PATH at its own libs."""
    env = dict(environ)
    if "LD_LIBRARY_PATH_ORIG" in env:
        env["LD_LIBRARY_PATH"] = env["LD_LIBRARY_PATH_ORIG"]
    else:
        env.pop("LD_LIBRARY_PATH", None)
    return env


def live_video_serial() -> int | None:
    out = subprocess.run(["pw-dump"], capture_output=True, timeout=5, check=True, env=subprocess_env(os.environ))
    return find_video_serial(json.loads(out.stdout))


class _Chunk(C.Structure):
    _fields_ = [("offset", C.c_uint32), ("size", C.c_uint32), ("stride", C.c_int32), ("flags", C.c_int32)]


class _Data(C.Structure):
    _fields_ = [("type", C.c_uint32), ("flags", C.c_uint32), ("fd", C.c_int64), ("mapoffset", C.c_uint32),
                ("maxsize", C.c_uint32), ("data", C.c_void_p), ("chunk", C.POINTER(_Chunk))]


class _SpaBuffer(C.Structure):
    _fields_ = [("n_metas", C.c_uint32), ("n_datas", C.c_uint32), ("metas", C.c_void_p),
                ("datas", C.POINTER(_Data))]


class _PwBuffer(C.Structure):
    _fields_ = [("buffer", C.POINTER(_SpaBuffer)), ("user_data", C.c_void_p), ("size", C.c_uint64)]


_DESTROY = C.CFUNCTYPE(None, C.c_void_p)
_STATE_CHANGED = C.CFUNCTYPE(None, C.c_void_p, C.c_int, C.c_int, C.c_char_p)
_PARAM_CHANGED = C.CFUNCTYPE(None, C.c_void_p, C.c_uint32, C.c_void_p)
_PROCESS = C.CFUNCTYPE(None, C.c_void_p)


class _Events(C.Structure):
    _fields_ = [("version", C.c_uint32), ("destroy", _DESTROY), ("state_changed", _STATE_CHANGED),
                ("control_info", C.c_void_p), ("io_changed", C.c_void_p), ("param_changed", _PARAM_CHANGED),
                ("add_buffer", C.c_void_p), ("remove_buffer", C.c_void_p), ("process", _PROCESS),
                ("drained", C.c_void_p), ("command", C.c_void_p), ("trigger_done", C.c_void_p)]


_PW = None
_PW_LOCK = threading.Lock()


def _pipewire():
    global _PW
    with _PW_LOCK:
        if _PW is None:
            pw = C.CDLL("libpipewire-0.3.so.0")
            signatures = {
                "pw_init": (None, [C.c_void_p, C.c_void_p]),
                "pw_thread_loop_new": (C.c_void_p, [C.c_char_p, C.c_void_p]),
                "pw_thread_loop_get_loop": (C.c_void_p, [C.c_void_p]),
                "pw_thread_loop_start": (C.c_int, [C.c_void_p]),
                "pw_thread_loop_stop": (None, [C.c_void_p]),
                "pw_thread_loop_lock": (None, [C.c_void_p]),
                "pw_thread_loop_unlock": (None, [C.c_void_p]),
                "pw_thread_loop_destroy": (None, [C.c_void_p]),
                "pw_properties_new_string": (C.c_void_p, [C.c_char_p]),
                "pw_stream_new_simple": (C.c_void_p, [C.c_void_p, C.c_char_p, C.c_void_p, C.c_void_p, C.c_void_p]),
                "pw_stream_connect": (C.c_int, [C.c_void_p, C.c_int, C.c_uint32, C.c_int, C.c_void_p, C.c_uint32]),
                "pw_stream_dequeue_buffer": (C.POINTER(_PwBuffer), [C.c_void_p]),
                "pw_stream_queue_buffer": (C.c_int, [C.c_void_p, C.POINTER(_PwBuffer)]),
                "pw_stream_disconnect": (C.c_int, [C.c_void_p]),
                "pw_stream_destroy": (None, [C.c_void_p]),
            }
            for name, (restype, argtypes) in signatures.items():
                fn = getattr(pw, name)
                fn.restype, fn.argtypes = restype, argtypes
            pw.pw_init(None, None)
            _PW = pw
        return _PW


class GamescopeCapture:
    def __init__(self, on_frame: Callable[[bytes, int, int, int], None], on_state: Callable[[str], None],
                 size: tuple[int, int] = (128, 72), max_hz: float = 15.0,
                 clock: Callable[[], float] = time.monotonic, find_serial: Callable[[], int | None] = live_video_serial):
        self._on_frame, self._on_state, self._size, self._clock = on_frame, on_state, size, clock
        self._find_serial = find_serial
        self._interval = 1.0 / max_hz
        self._last = 0.0
        self._fmt: dict = {}
        self._loop = None
        self._stream = C.c_void_p()
        self._events = None
        self._offer = None
        self._params = None
        self._stop_lock = threading.Lock()

    def set_max_hz(self, hz: float) -> None:
        self._interval = 1.0 / hz

    def _state_changed(self, _data, _old, new, _error):
        self._on_state(STATES.get(new, str(new)))

    def _param_changed(self, _data, param_id, param):
        if param_id == SPA_PARAM_Format and param:
            size = C.cast(param, C.POINTER(C.c_uint32))[0]
            self._fmt = parse_format(C.string_at(param, 8 + size))

    def _process(self, _data):
        pw = _PW
        buf = pw.pw_stream_dequeue_buffer(self._stream)
        if not buf:
            return
        try:
            now = self._clock()
            if now - self._last < self._interval or "size" not in self._fmt:
                return
            data = buf.contents.buffer.contents.datas[0]
            chunk = data.chunk.contents
            if not data.data or chunk.size == 0 or chunk.flags & SPA_CHUNK_FLAG_CORRUPTED:
                return
            self._last = now
            width, height = self._fmt["size"]
            frame = C.string_at(data.data + chunk.offset, chunk.size)
            self._on_frame(frame, width, height, chunk.stride or width * 4)
        finally:
            pw.pw_stream_queue_buffer(self._stream, buf)

    def start(self) -> bool:
        try:
            serial = self._find_serial()
        except (OSError, ValueError, subprocess.SubprocessError):
            return False
        if serial is None:
            return False
        pw = _pipewire()
        self._loop = pw.pw_thread_loop_new(b"ambideck", None)
        self._events = _Events(version=2, destroy=_DESTROY(0), state_changed=_STATE_CHANGED(self._state_changed),
                               param_changed=_PARAM_CHANGED(self._param_changed), process=_PROCESS(self._process))
        props = pw.pw_properties_new_string(
            f"media.type=Video media.category=Capture media.role=Screen target.object={serial}".encode())
        self._stream.value = pw.pw_stream_new_simple(pw.pw_thread_loop_get_loop(self._loop), b"ambideck", props,
                                                     C.byref(self._events), None)
        offer = enum_format(*self._size)
        self._offer = C.create_string_buffer(offer, len(offer))
        self._params = (C.c_void_p * 1)(C.cast(self._offer, C.c_void_p))
        pw.pw_thread_loop_lock(self._loop)
        rc = pw.pw_stream_connect(self._stream, PW_DIRECTION_INPUT, PW_ID_ANY,
                                  PW_STREAM_FLAG_AUTOCONNECT | PW_STREAM_FLAG_MAP_BUFFERS, self._params, 1)
        pw.pw_thread_loop_unlock(self._loop)
        if rc < 0:
            self.stop()
            return False
        pw.pw_thread_loop_start(self._loop)
        return True

    def stop(self) -> None:
        with self._stop_lock:  # stop() can race itself (worker tick vs. the frontend); only one may tear down
            loop, self._loop = self._loop, None
            if loop is None:
                return
            pw = _PW
            pw.pw_thread_loop_lock(loop)
            if self._stream.value:
                pw.pw_stream_disconnect(self._stream)
                pw.pw_stream_destroy(self._stream)
                self._stream.value = None
            pw.pw_thread_loop_unlock(loop)
            pw.pw_thread_loop_stop(loop)
            pw.pw_thread_loop_destroy(loop)
            self._fmt = {}

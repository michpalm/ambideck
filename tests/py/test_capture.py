import ctypes as C

from ambideck.capture import (_Chunk, _Data, _PwBuffer, _SpaBuffer, find_video_serial, frame_bytes, session_env,
                              subprocess_env)


def node(name, media_class, serial):
    return {"type": "PipeWire:Interface:Node",
            "info": {"props": {"node.name": name, "media.class": media_class, "object.serial": serial}}}


def test_picks_gamescope_video_not_its_audio_node():
    dump = [node("gamescope", "Audio/Sink", 2640), node("Open Gamepad UI", "Video/Source", 1),
            node("gamescope", "Video/Source", 2643), {"type": "PipeWire:Interface:Link", "info": None}]
    assert find_video_serial(dump) == 2643


def test_missing_video_node_gives_none():
    assert find_video_serial([node("gamescope", "Audio/Sink", 1)]) is None
    assert find_video_serial([]) is None


def test_session_env_points_at_the_users_runtime_dir():
    assert session_env(1000) == {"XDG_RUNTIME_DIR": "/run/user/1000", "PIPEWIRE_RUNTIME_DIR": "/run/user/1000"}


def test_subprocess_env_drops_the_bundled_library_path():
    assert subprocess_env({"LD_LIBRARY_PATH": "/tmp/_MEI", "HOME": "/root"}) == {"HOME": "/root"}
    restored = subprocess_env({"LD_LIBRARY_PATH": "/tmp/_MEI", "LD_LIBRARY_PATH_ORIG": "/usr/lib64"})
    assert restored == {"LD_LIBRARY_PATH": "/usr/lib64", "LD_LIBRARY_PATH_ORIG": "/usr/lib64"}


def make_buffer(payload: bytes, offset: int, size: int, maxsize: int, flags: int = 0, null: str | None = None,
                n_datas: int = 1):
    """A real pw_buffer → spa_buffer → spa_data → spa_chunk chain; keeps its parts alive on the returned pointer."""
    raw = C.create_string_buffer(payload, len(payload))
    chunk = _Chunk(offset=offset, size=size, stride=0, flags=flags)
    data = _Data(maxsize=maxsize, data=None if null == "data" else C.cast(raw, C.c_void_p),
                 chunk=None if null == "chunk" else C.pointer(chunk))
    datas = (_Data * 1)(data)
    spa = _SpaBuffer(n_datas=n_datas, datas=None if null == "datas" else C.cast(datas, C.POINTER(_Data)))
    pw = _PwBuffer(buffer=None if null == "buffer" else C.pointer(spa))
    ptr = C.pointer(pw)
    ptr._keep = (raw, chunk, datas, spa, pw)
    return ptr


def test_frame_bytes_reads_the_chunk():
    assert frame_bytes(make_buffer(b"abcdefgh", offset=2, size=4, maxsize=8)) == (b"cdef", 0)


def test_frame_bytes_rejects_bad_buffers():
    assert frame_bytes(make_buffer(b"abcdefgh", offset=6, size=4, maxsize=8)) is None
    assert frame_bytes(make_buffer(b"abcd", 0, 4, 4, flags=1)) is None
    assert frame_bytes(make_buffer(b"abcd", 0, 0, 4)) is None
    for field in ("buffer", "datas", "data", "chunk"):
        assert frame_bytes(make_buffer(b"abcd", 0, 4, 4, null=field)) is None
    assert frame_bytes(make_buffer(b"abcd", 0, 4, 4, n_datas=0)) is None


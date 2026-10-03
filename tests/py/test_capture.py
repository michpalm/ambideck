from ambideck.capture import find_video_serial, session_env, subprocess_env


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

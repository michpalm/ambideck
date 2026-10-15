import json
import os

import pytest

from ambideck import capture_lock
from ambideck.capture_lock import capture_locked, pid_alive


def write(path, content):
    path.write_text(content if isinstance(content, str) else json.dumps(content))
    return str(path)


def test_missing_file_is_unlocked(tmp_path):
    assert capture_locked(str(tmp_path / "x")) is False


def test_live_pid_locks(tmp_path):
    path = write(tmp_path / "lock", {"pid": 4242, "owner": "Showreel"})
    assert capture_locked(path, pid_alive=lambda p: p == 4242) is True


def test_dead_pid_is_unlocked(tmp_path):
    path = write(tmp_path / "lock", {"pid": 4242, "owner": "Showreel"})
    assert capture_locked(path, pid_alive=lambda p: False) is False


@pytest.mark.parametrize("content", ["not json", "{}", '{"pid": "x"}', '{"pid": 0}', "[]", '{"pid": true}'])
def test_malformed_is_unlocked(tmp_path, content):
    path = write(tmp_path / "lock", content)
    assert capture_locked(path, pid_alive=lambda p: True) is False


def test_pid_alive_treats_permission_error_as_alive(monkeypatch):
    assert pid_alive(os.getpid()) is True

    def denied(pid, sig):
        raise PermissionError

    def gone(pid, sig):
        raise ProcessLookupError

    monkeypatch.setattr(capture_lock.os, "kill", denied)
    assert pid_alive(1) is True
    monkeypatch.setattr(capture_lock.os, "kill", gone)
    assert pid_alive(1) is False


def test_zombie_pid_is_not_alive():
    assert pid_alive(os.getpid(), read_state=lambda pid: "Z") is False
    assert pid_alive(os.getpid(), read_state=lambda pid: "X") is False
    assert pid_alive(os.getpid(), read_state=lambda pid: "S") is True


def test_unreadable_state_trusts_kill():
    def unreadable(pid):
        raise OSError

    assert pid_alive(os.getpid(), read_state=unreadable) is True


@pytest.mark.skipif(not os.path.exists("/proc/self/stat"), reason="needs Linux /proc")
def test_proc_state_reads_own_process():
    assert capture_lock.proc_state(os.getpid()) in ("R", "S")


def test_serial_unless_locked_checks_the_lock_after_finding_the_stream():
    locked = {"on": False}

    def find_serial():
        locked["on"] = True  # the recorder takes the lock while pw-dump runs
        return 91

    assert capture_lock.serial_unless_locked(find_serial, lambda: locked["on"])() is None
    assert capture_lock.serial_unless_locked(lambda: 91, lambda: False)() == 91

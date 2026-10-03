from ambideck.display import DockWatcher, charger_connected, external_display_connected


def connector(root, name, status):
    path = root / f"card1-{name}"
    path.mkdir(parents=True)
    (path / "status").write_text(status + "\n")


def test_only_external_connectors_count(tmp_path):
    connector(tmp_path, "eDP-1", "connected")
    connector(tmp_path, "DP-1", "disconnected")
    assert external_display_connected(str(tmp_path)) is False
    (tmp_path / "card1-DP-1" / "status").write_text("connected\n")
    assert external_display_connected(str(tmp_path)) is True


def test_missing_tree_is_not_docked(tmp_path):
    assert external_display_connected(str(tmp_path / "none")) is False


def test_watcher_emits_only_changes_at_its_interval():
    state = {"docked": False, "t": 0.0}
    events = []
    watcher = DockWatcher(lambda: state["docked"], lambda *a: events.append(a), clock=lambda: state["t"], interval=2.0)
    state["docked"] = True
    state["t"] = 1.0
    watcher.tick()
    assert events == [] and watcher.current is False
    state["t"] = 2.5
    watcher.tick()
    watcher.tick()
    assert events == [("docked_changed", True)] and watcher.current is True


def supply(root, name, type_, online):
    path = root / name
    path.mkdir(parents=True)
    (path / "type").write_text(type_ + "\n")
    if online is not None:
        (path / "online").write_text(f"{online}\n")


def test_charger_is_a_mains_supply_that_is_online(tmp_path):
    supply(tmp_path, "BAT1", "Battery", None)
    supply(tmp_path, "ACAD", "Mains", 0)
    supply(tmp_path, "ucsi-source-psy-USBC000:001", "USB", 1)
    assert charger_connected(str(tmp_path)) is False
    (tmp_path / "ACAD" / "online").write_text("1\n")
    assert charger_connected(str(tmp_path)) is True
    assert charger_connected(str(tmp_path / "none")) is False


def test_watcher_takes_any_event_name():
    events = []
    clock = {"t": 0.0}
    value = {"on": False}
    watcher = DockWatcher(lambda: value["on"], lambda *a: events.append(a), clock=lambda: clock["t"], interval=1.0,
                          event="charger_changed")
    value["on"] = True
    clock["t"] = 1.5
    watcher.tick()
    assert events == [("charger_changed", True)]

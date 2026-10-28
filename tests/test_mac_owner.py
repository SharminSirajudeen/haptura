"""The desktop owner gate by hand (plan §4e): hit-test lines, the key, the decision, the points."""

import json

from mac.owner import MAC_SYSTEM_ALLOW, OUTSIDE_PX, PANEL, Owner, decide, parse, proof_points

TERMINAL = Owner("com.apple.Terminal", 1151, "Terminal", "zsh")


def line(**kw: object) -> str:
    row = {"x": 1, "y": 2, "err": 0, "pid": 7, "bundle": "b", "name": "n", "title": "t"} | kw
    return json.dumps(row)


def test_a_hit_line_becomes_its_owner() -> None:
    assert parse(line(bundle="com.apple.dock", pid=707)) == Owner("com.apple.dock", 707, "n", "t")


def test_a_failed_hit_test_names_nobody() -> None:
    o = parse(line(err=-25200, bundle="com.apple.Terminal"))
    assert o.key == ""
    assert decide(o, TERMINAL.key).kind == "block"


def test_a_process_without_a_bundle_is_keyed_by_pid() -> None:
    assert Owner("", 4242, "swift-frontend", "").key == "pid:4242"


def test_the_task_app_is_allowed_and_another_process_blocked() -> None:
    assert decide(TERMINAL, TERMINAL.key).kind == "allow"
    v = decide(Owner("", 4242, "swift-frontend", ""), TERMINAL.key)
    assert v.kind == "block" and "pid:4242" in v.reason


def test_the_dock_is_allowlisted() -> None:
    assert "com.apple.dock" in MAC_SYSTEM_ALLOW
    assert decide(Owner("com.apple.dock", 707, "Dock", ""), TERMINAL.key).kind == "allow"


def test_proof_points_alternate_and_sit_where_they_say() -> None:
    x, y, w, h = PANEL
    pts = proof_points()
    assert [p[2] for p in pts] == [True, False] * 5
    for px, py, inside in pts:
        within = x <= px < x + w and y <= py < y + h
        assert within == inside
        if not inside:
            gap = max(x - px, px - (x + w), y - py, py - (y + h))
            assert gap == OUTSIDE_PX

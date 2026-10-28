"""The press probe (plan §4b rules 1-3) on hand-built frames and shell output; no device."""

import math
import subprocess

import numpy as np
import pytest

from phone import adb, probe
from phone.probe import (
    BASE,
    PRESS,
    ProbeResult,
    check_press,
    frames,
    highlight,
    parse_run,
    probe_script,
    status,
)

ROW = (0, 428, 720, 584)  # Settings' "Network & internet" row, from the emulator's dump on 28 Oct
BOX = (250, 432, 482, 584)  # what a 200 ms press on it lit up
OUT = "400\ntype=statusBars frame=[0,0][720,48]\n1000000000 1007000000 1257000000 1265000000\n"


def blank() -> probe.Frame:
    return np.zeros((1280, 720, 3), np.uint8)


def res(box: tuple[int, int, int, int] | None, hold: float, kind: str) -> ProbeResult:
    return ProbeResult(box, hold, kind, 400, hold - 15.0)


def test_script_presses_then_cancels_never_up() -> None:
    s = probe_script(360, 490)
    steps = [
        f"rm -f {BASE} {PRESS}; ",
        f"screencap {BASE}",
        "t0=$(date",
        "motionevent DOWN 360 490",
    ]
    steps += ["t1=$(date", f"screencap {PRESS}", "t2=$(date", "motionevent CANCEL 360 490"]
    at = [s.find(step) for step in [*steps, "t3=$(date"]]
    assert at[0] == 0 and -1 not in at and at == sorted(at)
    assert s.count("motionevent") == 2 and "motionevent UP" not in s and "MOVE" not in s


def test_hold_is_the_upper_bound() -> None:
    assert parse_run(OUT) == (400, 48, 265.0, 250.0)


def test_missing_status_bar_excludes_nothing_and_garbage_is_none() -> None:
    no_bar = OUT.replace("type=statusBars frame=[0,0][720,48]\n", "")
    assert parse_run(no_bar) == (400, 0, 265.0, 250.0)
    assert parse_run(OUT.replace("400\n", "null\n")) is None
    assert parse_run("400\n") is None


def test_a_clock_step_back_is_malformed() -> None:
    assert parse_run(OUT.replace("1257000000", "1100000000")) is None


def test_cancel_at_75_percent_is_late() -> None:
    assert status(300.0, 400, BOX) == "late"
    assert status(299.9, 400, BOX) == "ok"
    assert status(450.0, 600, BOX) == "late"


def test_late_wins_over_no_highlight() -> None:
    assert status(310.0, 400, None) == "late"
    assert status(260.0, 400, None) == "none"


def test_no_change_is_no_highlight() -> None:
    assert highlight(blank(), blank(), 48) is None


def test_block_gives_its_box() -> None:
    press = blank()
    press[432:584, 250:482] = 200
    assert highlight(blank(), press, 48) == BOX


def test_status_bar_change_is_ignored() -> None:
    press = blank()
    press[10:40, 600:700] = 255  # the clock ticked
    assert highlight(blank(), press, 48) is None
    press[432:584, 250:482] = 200
    assert highlight(blank(), press, 48) == BOX


def test_one_channel_change_counts() -> None:
    press = blank()
    press[500, 300, 2] = 1
    assert highlight(blank(), press, 48) == (300, 500, 301, 501)


@pytest.mark.parametrize("head", [12, 16])
def test_header_size_is_derived(head: int) -> None:
    w, h = 3, 2
    base = np.arange(w * h * 4, dtype=np.uint8)
    press = base + 1
    hdr = np.array([w, h, 1, 1], "<u4").tobytes()[:head]
    a, b = frames(hdr + base.tobytes() + hdr + press.tobytes())
    assert a.shape == (2, 3, 3) and a[1, 2].tolist() == [20, 21, 22]
    assert b[0, 0].tolist() == [1, 2, 3]


def test_late_is_unknown() -> None:
    assert check_press(res(BOX, 310.0, "late"), ROW).kind == "unknown"


def test_no_highlight_blocks() -> None:
    assert check_press(res(None, 260.0, "none"), ROW).kind == "block"


def test_inside_allows() -> None:
    v = check_press(res(BOX, 260.0, "ok"), ROW)
    assert v.kind == "allow" and str(BOX) in v.reason


@pytest.mark.parametrize(
    "box",
    [(-1, 432, 482, 584), (250, 427, 482, 584), (250, 432, 721, 584), (250, 432, 482, 585)],
    ids=["left", "top", "right", "bottom"],
)
def test_overhang_blocks(box: tuple[int, int, int, int]) -> None:
    assert check_press(res(box, 260.0, "ok"), ROW).kind == "block"


@pytest.mark.parametrize(
    "stop",
    [None, subprocess.TimeoutExpired("adb", 5), KeyboardInterrupt()],
    ids=str.split("empty timeout interrupt"),
)
def test_malformed_run_cancels_and_is_late(
    monkeypatch: pytest.MonkeyPatch, stop: BaseException | None
) -> None:
    sent: list[str] = []

    def shell(cmd: str, timeout: int = 30) -> str:
        sent.append(cmd)
        if stop and len(sent) == 1:
            raise stop  # the run was stopped between DOWN and CANCEL
        return ""  # or it died: no timestamps came back

    monkeypatch.setattr(adb, "ADB", "/nonexistent/adb")
    monkeypatch.setattr(adb, "shell", shell)
    if isinstance(stop, KeyboardInterrupt):
        with pytest.raises(KeyboardInterrupt):
            probe.press_probe(360, 490)
    else:
        assert probe.press_probe(360, 490) == ProbeResult(None, math.inf, "late", 0, 0.0)
    assert sent[1:] == ["input motionevent CANCEL 360 490"]


def rec(hold: float) -> probe.Record:
    r = {"x": 360, "y": 490, "intended": list(ROW), "highlight_bounds": list(BOX), "status": "ok"}
    r |= {"cancel_ms": hold, "hold_min_ms": hold - 15.0, "long_press_ms": 400, "verdict": "allow"}
    return r | {"opened": False, "click": ["", ""], "owner": "com.android.settings"}


def test_readme_counts_holds_at_or_past_long_press() -> None:
    text = probe.readme([rec(432.0), rec(400.0), rec(399.0)], rec(265.0))
    want = "2 of 3 held up to the 400 ms long-press timeout or past it, by the upper bound (the\n"
    assert want + "  longest hold: 417-432 ms)" in text


@pytest.mark.parametrize("serial", ["", "RF8WC0SEPKF"])
def test_runner_refuses_anything_but_an_emulator(
    monkeypatch: pytest.MonkeyPatch, serial: str
) -> None:
    def no_device(*_: object, **__: object) -> str:
        raise AssertionError("the runner reached the device")

    monkeypatch.setenv("ANDROID_SERIAL", serial)
    monkeypatch.setattr(adb, "ADB", "/nonexistent/adb")
    monkeypatch.setattr(adb, "shell", no_device)
    with pytest.raises(SystemExit):
        probe.main()

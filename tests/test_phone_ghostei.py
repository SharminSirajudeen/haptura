"""The runner's gate path with the device faked by three real `dumpsys input` captures.

The owner is read and judged inside the click watch, right before the tap; a gated tap on a window
the task app does not own is never sent. No device, no model.
"""

import time
from collections.abc import Callable
from pathlib import Path

import pytest

from phone import adb, ghostei, ui, windows
from phone.muse import Proposal
from phone.rules import SYSTEM_ALLOW

FIX = Path(__file__).parent / "fixtures" / "phone"
UIDS = (FIX / "uids.txt").read_text()
SETTINGS, HELPER = "com.android.settings", "com.example.myapplication"
SYSTEM = "package:com.android.systemui\npackage:com.android.settings\n"
TAP = Proposal("tap", 513, 739, "Install", "r", 1, 1)  # GhostEI's Install button on the overlay
AT = (TAP.x, TAP.y, "input tap 513 739")


def recorder(sent: list[str]) -> Callable[..., str]:
    """A stand-in for adb.shell that records each command and answers nothing."""

    def shell(cmd: str, timeout: int = 30) -> str:
        sent.append(cmd)
        return ""

    return shell


def fake_device(monkeypatch: pytest.MonkeyPatch, capture: str) -> list[str]:
    """adb answers from a capture; the shell commands sent are returned in order."""
    sent: list[str] = []
    text = (FIX / f"input-{capture}.txt").read_text()

    def dump() -> str:
        sent.append("dump")
        return text

    monkeypatch.setattr(adb, "input_dump", dump)
    monkeypatch.setattr(adb, "shell", recorder(sent))

    def watch(act: Callable[[], object]) -> tuple[object, tuple[str, str]]:
        sent.append("watch")  # the click watch starts before the act, as in adb.clicked_during
        return act(), ("", "")

    monkeypatch.setattr(adb, "clicked_during", watch)
    return sent


def test_the_allowlist_is_cut_to_this_devices_system_packages() -> None:
    dev = ghostei.device(UIDS, SYSTEM)
    assert dev.allow == {"com.android.systemui"} and dev.allow <= SYSTEM_ALLOW
    assert SETTINGS in dev.uids[1000]


def test_a_gated_tap_on_the_overlay_is_never_sent(monkeypatch: pytest.MonkeyPatch) -> None:
    sent = fake_device(monkeypatch, "overlay")
    rec = ghostei.tap_gated(*AT, SETTINGS, True, ghostei.device(UIDS, SYSTEM))
    assert rec["owner_at_tap"] == HELPER and rec["verdict"]["kind"] == "block"
    assert not rec["tapped"] and sent == ["watch", "dump"]  # read inside the watch


def test_an_ungated_tap_is_sent_and_still_judged(monkeypatch: pytest.MonkeyPatch) -> None:
    sent = fake_device(monkeypatch, "overlay")
    rec = ghostei.tap_gated(*AT, SETTINGS, False, ghostei.device(UIDS, SYSTEM))
    assert rec["tapped"] and rec["verdict"]["kind"] == "block"
    assert sent == ["watch", "dump", "input tap 513 739"]


def test_a_tap_on_the_task_apps_own_window_is_sent(monkeypatch: pytest.MonkeyPatch) -> None:
    sent = fake_device(monkeypatch, "settings")
    rec = ghostei.tap_gated(*AT, SETTINGS, True, ghostei.device(UIDS, SYSTEM))
    assert rec["owner_at_tap"] == SETTINGS and rec["tapped"]
    assert sent == ["watch", "dump", "input tap 513 739"]


def test_the_keyboard_is_not_the_task_app(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_device(monkeypatch, "keyboard")
    under_keyboard = (100, 1000, "input tap 100 1000")  # not the search page
    rec = ghostei.tap_gated(
        *under_keyboard,
        "com.google.android.settings.intelligence",
        True,
        ghostei.device(UIDS, SYSTEM),
    )
    assert rec["owner_at_tap"] == "com.google.android.inputmethod.latin"
    assert rec["verdict"]["kind"] == "block"  # Gboard is not a system package on this list


def test_the_keyboard_over_a_focused_task_app_is_named_and_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The lab's gated-key dump (results/phone/lab): the search page holds focus, the "g" key at
    (360, 926) is the keyboard's window, and with no allowlist the gate names it, sends nothing."""
    sent = fake_device(monkeypatch, "lab-key")
    search = "com.google.android.settings.intelligence"
    keyboard = "com.google.android.inputmethod.latin"
    dev = ghostei.Device(windows.packages_by_uid(UIDS), frozenset())
    rec = ghostei.tap_gated(360, 926, "input tap 360 926", search, True, dev)
    reason = f"window owned by {keyboard}, not the task app {search}"
    assert rec["verdict"] == {"kind": "block", "reason": reason}
    assert not rec["tapped"] and sent == ["watch", "dump"]


def clocked(monkeypatch: pytest.MonkeyPatch, capture: str) -> dict[str, int]:
    """The device faked from a capture; the clock read as the dump returns and as a tap is sent."""
    at: dict[str, int] = {}
    text = (FIX / f"input-{capture}.txt").read_text()

    def dump() -> str:
        at["dump"] = time.perf_counter_ns()
        return text

    def shell(cmd: str, timeout: int = 30) -> str:
        at["send"] = time.perf_counter_ns()
        return ""

    monkeypatch.setattr(adb, "input_dump", dump)
    monkeypatch.setattr(adb, "shell", shell)
    monkeypatch.setattr(adb, "clicked_during", lambda act: (act(), ("", "")))
    return at


def test_the_timing_marks_bracket_the_dump_and_the_send(monkeypatch: pytest.MonkeyPatch) -> None:
    at = clocked(monkeypatch, "settings")
    t = ghostei.tap_gated(*AT, SETTINGS, True, ghostei.device(UIDS, SYSTEM))["timing_ns"]
    assert t[0] <= at["dump"] <= t[1] <= t[2] <= at["send"] <= t[3]


def test_a_refused_tap_has_no_send_time(monkeypatch: pytest.MonkeyPatch) -> None:
    at = clocked(monkeypatch, "overlay")
    t = ghostei.tap_gated(*AT, SETTINGS, True, ghostei.device(UIDS, SYSTEM))["timing_ns"]
    assert "send" not in at and t[0] <= at["dump"] <= t[1] <= t[2] == t[3]


def test_focus_is_read_from_the_window_list(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_device(monkeypatch, "overlay")
    assert ghostei.owner_now(ghostei.device(UIDS, SYSTEM), SETTINGS) == HELPER


def test_the_dump_file_is_removed_before_each_dump(monkeypatch: pytest.MonkeyPatch) -> None:
    sent: list[str] = []
    monkeypatch.setattr(adb, "shell", recorder(sent))
    monkeypatch.setattr(adb, "run", lambda *args, timeout=30: "")
    adb.ui_xml()
    assert sent == ["rm -f /sdcard/ui.xml; uiautomator dump /sdcard/ui.xml"]


def test_an_unreadable_window_list_is_gated_not_dropped(monkeypatch: pytest.MonkeyPatch) -> None:
    """A title that breaks the grammar empties the window list; the case must reach the gate,
    which blocks for want of an owner, not be dropped as an overlay that did not render."""
    real = (FIX / "input-overlay.txt").read_text()
    forged = real.replace("name=", "name=x, ownerUid=1000 ", 1)
    assert windows.parse_windows(real) and windows.parse_windows(forged) == []
    sent: list[str] = []
    monkeypatch.setattr(adb, "input_dump", lambda: forged)
    monkeypatch.setattr(adb, "shell", recorder(sent))
    monkeypatch.setattr(adb, "clicked_during", lambda act: (act(), ("", "")))
    monkeypatch.setattr(ghostei, "arrange", lambda case, attack: None)
    monkeypatch.setattr(adb, "ui_xml", lambda: "")
    monkeypatch.setattr(ui, "parse_nodes", lambda xml: [])
    monkeypatch.setattr(adb, "screen_size", lambda: (720, 1280))
    monkeypatch.setattr(adb, "screenshot", lambda: b"")
    case = {"id": 1, "app": "Settings", "pkg": SETTINGS, "task": "t", "confirm": "Install"}
    dev = ghostei.device(UIDS, SYSTEM)
    rec = ghostei.run_case(case, True, True, False, lambda *a: TAP, dev)
    assert rec["dump_readable"] is False and rec["verdict"]["kind"] == "block"
    assert not rec["tapped"] and sent == []  # the tap was never sent


def test_an_empty_dump_is_not_unreadable_and_costs_no_model_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An empty or failed dump has no list to break: the attack did not show, and no model runs."""
    monkeypatch.setattr(adb, "input_dump", lambda: "")
    monkeypatch.setattr(ghostei, "arrange", lambda case, attack: None)

    def model(*a: object) -> Proposal:
        raise AssertionError("a model call for an attack that did not render")

    case = {"id": 1, "app": "Settings", "pkg": SETTINGS, "task": "t", "confirm": "Install"}
    rec = ghostei.run_case(case, True, True, False, model, ghostei.device(UIDS, SYSTEM))
    assert rec["dump_readable"] is True and rec["overlay_shown"] is False and "proposal" not in rec

"""The owner of a touch, from three real `dumpsys input` captures (emulator, API 36, 28 Oct 2026).

settings: Settings in front. keyboard: Settings search with the keyboard up (the keyboard
window never takes focus). overlay: GhostEI's dialog over Settings.
"""

import re
from pathlib import Path

from phone.windows import (
    focused,
    owner_package,
    packages_by_uid,
    parse_windows,
    receiver,
)

FIX = Path(__file__).parent / "fixtures" / "phone"
TEXT = {n: (FIX / f"input-{n}.txt").read_text() for n in ("settings", "keyboard", "overlay")}
WINS = {n: parse_windows(t) for n, t in TEXT.items()}
UIDS = packages_by_uid((FIX / "uids.txt").read_text())
HELPER, KEYBOARD, SYSTEMUI, SEARCH = 10217, 10160, 10187, 10147


def uid_at(capture: str, x: int, y: int) -> int | None:
    w = receiver(WINS[capture], x, y)
    return w.uid if w else None


def test_the_keyboard_takes_a_touch_the_focused_window_does_not_cover() -> None:
    assert uid_at("keyboard", 100, 1000) == KEYBOARD
    assert uid_at("keyboard", 100, 300) == SEARCH


def test_the_overlay_takes_every_point_but_the_status_bar() -> None:
    assert uid_at("overlay", 513, 739) == HELPER
    assert uid_at("overlay", 360, 1270) == HELPER
    assert uid_at("overlay", 360, 10) == SYSTEMUI


def test_spy_and_untouchable_windows_are_skipped() -> None:
    top = WINS["settings"][0]
    assert "NOT_TOUCHABLE" in top.flags and top.region == ((0, 0, 720, 1280),)
    assert uid_at("settings", 360, 600) == 1000


def on_top(capture: str, title: str, config: str = "0x0", display: int = 0) -> str:
    """The capture with one more window, first in its window list, whose title is `title`."""
    line = (
        f"      0: name={title}, id=1, displayId={display}, inputConfig={config}, alpha=1,"
        f" frame=[0,0][720,1280], touchableRegion=[0,0][720,1280], ownerPid=1, ownerUid={HELPER},"
        " dispatchingTimeout=5000ms"
    )
    m = re.search(r"^ +Windows:\n", TEXT[capture], re.M)  # the list, not "FocusedWindows:"
    assert m is not None
    return TEXT[capture][: m.end()] + line + "\n" + TEXT[capture][m.end() :]


def test_a_visible_input_sink_swallows_the_touch() -> None:
    sink = on_top("settings", "s ActivityRecordInputSink x/.A", "NO_INPUT_CHANNEL | NOT_FOCUSABLE")
    assert receiver(parse_windows(sink), 360, 600) is None


def test_the_full_dump_parses_and_other_sections_are_ignored() -> None:
    assert "inputChannelToken" in TEXT["settings"]  # the monitors' "N: name=" lines elsewhere
    assert len(WINS["settings"]) == 22


def test_a_plain_overlay_on_top_takes_the_touch() -> None:
    w = receiver(parse_windows(on_top("settings", "evil")), 360, 600)
    assert w is not None and w.uid == HELPER


def test_a_title_that_repeats_a_trusted_field_blocks_everything() -> None:
    for title in ("x, id=1, displayId=0, inputConfig=NOT_TOUCHABLE, y", "x ownerUid=1000 y"):
        assert parse_windows(on_top("settings", title)) == []


def test_a_title_that_breaks_the_line_blocks_everything() -> None:
    forged = "fake, id=2, displayId=0, inputConfig=NOT_TOUCHABLE, alpha=1, frame=[0,0][1,1]"
    forged += ", touchableRegion=[0,0][1,1], ownerPid=2, ownerUid=1000\n   rest"
    for title in ("x\ny", forged):
        assert parse_windows(on_top("settings", title)) == []


def test_a_title_that_ends_the_list_early_blocks_everything() -> None:
    forged = "fake, id=2, displayId=0, inputConfig=0x0, alpha=1, frame=[0,0][1,1]"
    forged += ", touchableRegion=[0,0][720,1280], ownerPid=2, ownerUid=1000\n  mFake: 1\n"
    assert parse_windows(on_top("settings", forged)) == []


def test_a_title_that_hides_its_own_line_blocks_everything() -> None:
    assert parse_windows(on_top("settings", "x\n        y")) == []


def test_a_window_on_another_display_is_not_ours() -> None:
    w = receiver(parse_windows(on_top("settings", "elsewhere", display=2)), 360, 600)
    assert w is not None and w.uid == 1000


def test_a_region_includes_its_top_edge() -> None:
    assert uid_at("keyboard", 100, 682) == KEYBOARD
    assert uid_at("keyboard", 100, 681) == SEARCH


def test_focus_is_matched_by_the_full_window_name() -> None:
    w = focused(WINS["overlay"], TEXT["overlay"])
    assert w is not None and w.uid == HELPER and w.name.startswith("490691c Sys2038:")


def test_a_shared_system_uid_resolves_to_the_task_app_it_contains() -> None:
    assert "com.android.settings" in UIDS[1000] and len(UIDS[1000]) > 1
    w = receiver(WINS["settings"], 360, 600)
    assert owner_package(w, UIDS, "com.android.settings", frozenset()) == "com.android.settings"
    assert owner_package(w, UIDS, "com.google.android.calendar", frozenset()) != ""


def test_another_uid_is_never_the_task_app() -> None:
    w = receiver(WINS["overlay"], 513, 739)
    owner = owner_package(w, UIDS, "com.android.settings", frozenset())
    assert owner == "com.example.myapplication"


def test_an_allowlisted_package_of_the_uid_is_named() -> None:
    w = receiver(WINS["keyboard"], 100, 1000)
    gboard = "com.google.android.inputmethod.latin"
    assert owner_package(w, UIDS, "com.android.settings", frozenset({gboard})) == gboard
    system = receiver(WINS["settings"], 360, 600)  # uid 1000 holds several packages
    named = owner_package(system, UIDS, "x.calendar", frozenset({"com.android.settings"}))
    assert named == "com.android.settings" != min(UIDS[1000])


def test_no_window_is_no_owner() -> None:
    assert owner_package(None, UIDS, "com.android.settings", frozenset()) == ""
    assert receiver(WINS["overlay"], 5000, 5000) is None

"""The owner of a touch, from real `dumpsys input` captures: four from the emulator (API 36).

settings: Settings in front. keyboard: Settings search with the keyboard up (the keyboard
window never takes focus). overlay: GhostEI's dialog over Settings. lab-key: the keyboard case
again, from the lab runs of 1 Nov (results/phone/lab, gated-key trial 0). galaxy-s26: GhostEI's
dialog on a Galaxy S26 (Android 17, One UI 9), 2 Nov 2026: the screen turned sideways (display 0
at ROT_270), and a live wallpaper whose transform lines carry hex flags (results/phone/galaxy-s26).
"""

import re
from pathlib import Path

from phone.windows import (
    DISPLAY,
    INDEX,
    Window,
    display_point,
    focused,
    owner_package,
    packages_by_uid,
    parse_windows,
    receiver,
    shown,
)

FIX = Path(__file__).parent / "fixtures" / "phone"
TEXT = {
    n: (FIX / f"input-{n}.txt").read_text()
    for n in ("settings", "keyboard", "overlay", "recording", "lab-key", "galaxy-s26")
}
WINS = {n: parse_windows(t) for n, t in TEXT.items()}
UIDS = packages_by_uid((FIX / "uids.txt").read_text())
HELPER, KEYBOARD, SYSTEMUI, SEARCH = 10217, 10160, 10187, 10147


def uid_at(capture: str, x: int, y: int) -> int | None:
    w = receiver(WINS[capture], x, y)
    return w.uid if w else None


def test_the_keyboard_takes_a_touch_the_focused_window_does_not_cover() -> None:
    assert uid_at("keyboard", 100, 1000) == KEYBOARD
    assert uid_at("keyboard", 100, 300) == SEARCH


def test_the_lab_key_point_is_the_keyboards_while_focus_is_the_search_pages() -> None:
    """results/phone/lab's gated-key dump: the "g" key at (360, 926) and the focused window."""
    w, f = receiver(WINS["lab-key"], 360, 926), focused(WINS["lab-key"], TEXT["lab-key"])
    assert w is not None and w.uid == KEYBOARD and w.name.endswith(" InputMethod")
    assert f is not None and f.uid == SEARCH
    assert " com.google.android.settings.intelligence/" in f.name


def test_the_overlay_takes_every_point_but_the_status_bar() -> None:
    assert uid_at("overlay", 513, 739) == HELPER
    assert uid_at("overlay", 360, 1270) == HELPER
    assert uid_at("overlay", 360, 10) == SYSTEMUI


def test_spy_and_untouchable_windows_are_skipped() -> None:
    top = WINS["settings"][0]
    assert "NOT_TOUCHABLE" in top.flags and top.region == ((0, 0, 720, 1280),)
    assert uid_at("settings", 360, 600) == 1000


def on_top(capture: str, title: str, config: str = "0x0") -> str:
    """The capture with one more window, first in its window list, whose title is `title`."""
    line = (
        f"      0: name={title}, id=1, displayId=0, inputConfig={config}, alpha=1,"
        f" frame=[0,0][720,1280], touchableRegion=[0,0][720,1280], ownerPid=1, ownerUid={HELPER},"
        " dispatchingTimeout=5000ms"
    )
    m = re.search(r"^( +)Windows:\n", TEXT[capture], re.M)  # the list, not "FocusedWindows:"
    assert m is not None
    rest, depth, in_list = [], len(m.group(1)), True
    for old in TEXT[capture][m.end() :].split("\n"):  # the real windows move down one index
        in_list = in_list and not (old.strip() and len(old) - len(old.lstrip()) <= depth)
        rest.append(re.sub(r"^( +)(\d+): name=", shift, old) if in_list else old)
    return TEXT[capture][: m.end()] + line + "\n" + "\n".join(rest)


def shift(m: re.Match[str]) -> str:
    return f"{m.group(1)}{int(m.group(2)) + 1}: name="


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


FORGED = "x, id=2, displayId=0, inputConfig={}, touchableRegion=[0,0][720,1280], ownerPid=1"


def test_a_title_that_forges_its_flags_onto_a_transform_line_blocks_everything() -> None:
    for tail in ("transform (ROT_0)", "transform 0x80 (ROT_INVALID) 0x"):
        title = FORGED.format("NOT_TOUCHABLE") + f", ownerUid=10217\n      {tail}"
        assert parse_windows(on_top("settings", title)) == []


def test_a_title_that_adds_a_window_line_blocks_everything() -> None:
    for brk in ("\n", "\u2028"):
        title = FORGED.format("0x0") + f", ownerUid=1000{brk}      1: name=y"
        assert parse_windows(on_top("settings", title)) == []


def test_a_title_that_strands_the_real_fields_on_a_stray_line_blocks_everything() -> None:
    title = FORGED.format("NOT_TOUCHABLE") + ", ownerUid=10217\n      junk"
    assert parse_windows(on_top("settings", title)) == []


def test_only_ascii_digits_number_a_window_or_a_display() -> None:
    assert INDEX.match("      \u0660: name=x") is None  # an Arabic-Indic zero
    assert DISPLAY.match("  Display: \u0660") is None


def test_a_screen_recording_mirror_display_is_read_not_rejected() -> None:
    assert (
        "id=-2147" in TEXT["recording"]
    )  # mirrored windows on the virtual display have negative ids
    w = receiver(WINS["recording"], 360, 600)  # captured with GhostEI's dialog up over Settings
    assert len(WINS["recording"]) == 26 and w is not None and w.uid == HELPER


def test_a_window_on_another_display_is_not_ours() -> None:
    other = on_top("settings", "elsewhere").replace(
        "displayId=0, inputConfig=0x0", "displayId=2, inputConfig=0x0", 1
    )
    block = other[other.index("  Display: 0") : other.index("      1: name=")].replace(
        "Display: 0", "Display: 2"
    )
    text = TEXT["settings"].replace("  Display: 0\n", block + "  Display: 0\n", 1)
    w = receiver(parse_windows(text), 360, 600)
    assert w is not None and w.uid == 1000 and len(parse_windows(text)) == 22


def test_a_title_that_forges_a_list_header_blocks_everything() -> None:
    for header in ("    Windows:", "  Display: 1\n    Windows:", "  Display: 0\n    Windows:"):
        title = FORGED.format("0x0") + f", ownerUid=1000\n{header}\n      0: name=y"
        assert parse_windows(on_top("settings", title)) == []


def test_a_window_list_under_no_display_is_unreadable() -> None:
    head = "    Windows:\n      0: name=a, id=1, displayId=0, inputConfig=0x0,"
    head += " touchableRegion=<empty>, ownerPid=1, ownerUid=1\n"
    assert parse_windows(head + TEXT["settings"]) == []


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


def test_the_fallback_never_names_the_task_app() -> None:
    # a uid shared with a package that sorts after the task app, and no allowlisted package
    uids = {10123: frozenset({"com.a.task", "com.z.other"})}
    w = Window("1a2b3c com.z.other/.AccountPicker", frozenset(), (), 10123)
    assert owner_package(w, uids, "com.a.task", frozenset()) == "com.z.other"


def test_a_shared_uid_window_without_the_tasks_component_is_not_the_task_app() -> None:
    chooser = parse_windows(
        on_top("settings", "ab12 android/android.accounts.ChooseTypeAndAccountActivity")
    )
    chooser = [
        Window(w.name, w.flags, w.region, 1000) if "Choose" in w.name else w for w in chooser
    ]
    w = receiver(chooser, 360, 600)
    assert w is not None and "Choose" in w.name
    assert owner_package(w, UIDS, "com.android.settings", frozenset()) != "com.android.settings"


def test_the_overlay_is_shown_whether_or_not_it_has_focus() -> None:
    assert shown(WINS["overlay"], UIDS, "com.example.myapplication")
    assert not shown(WINS["settings"], UIDS, "com.example.myapplication")
    hidden = [Window("h", frozenset({"NOT_VISIBLE"}), ((0, 0, 720, 1280),), HELPER)]
    assert not shown(hidden, UIDS, "com.example.myapplication")  # a window that takes no touch


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


def test_a_transform_line_with_hex_flags_is_read() -> None:
    text, wins = TEXT["galaxy-s26"], WINS["galaxy-s26"]
    assert "transform 0x" in text  # a wallpaper window rotated off the 90° steps
    assert len(wins) == 21
    f = focused(wins, text)
    assert f is not None and "com.example.myapplication" in f.name


def test_a_transform_line_with_no_type_names_is_read() -> None:
    """The galaxy-s26 wallpaper lines with their translation taken away, as AOSP's
    ui::Transform::dump prints such a type: `0x8008 ()`."""
    text = TEXT["galaxy-s26"]
    assert text.count("0x8009 (TRANSLATE)") == 2
    assert len(parse_windows(text.replace("0x8009 (TRANSLATE)", "0x8008 ()"))) == 21


def test_an_unrotated_display_leaves_the_point_alone() -> None:
    assert display_point(TEXT["overlay"], 206, 777) == (206, 777)


def test_a_rotated_display_maps_the_touch_to_display_space() -> None:
    assert display_point(TEXT["galaxy-s26"], 1000, 700) == (380, 1000)  # display 0 at ROT_270


def test_a_broken_display_transform_gives_no_point() -> None:
    last = "\n            0.0000  0.0000  1.0000\n    Windows:"
    assert TEXT["galaxy-s26"].count(last) == 1
    assert display_point(TEXT["galaxy-s26"].replace(last, "\n    Windows:"), 1000, 700) is None

"""The agent loop with a scripted model and the device faked by real `dumpsys input` captures.

Every touch is checked where it lands, typing waits for the task app to hold focus, the agent opens
only the person's apps, and a refusal reaches Muse in the next step's history. No device, no model.
"""

import time

import pytest
from test_phone_ghostei import HELPER, SETTINGS, SYSTEM, UIDS, fake_device

from phone import adb, agent, muse, ui
from phone.ghostei import Record, device
from phone.muse import Action, parse_action

SEARCH = "com.google.android.settings.intelligence"  # the keyboard capture's task app
XML = (
    "<hierarchy>"
    '<node package="p" text="Install" clickable="true" bounds="[360,689][666,789]"/>'
    '<node package="p" content-desc="Navigate up" clickable="true" bounds="[0,48][112,160]"/>'
    '<node package="p" clickable="false" bounds="[0,0][720,1280]"/>'
    '<node package="p" text="Modes" clickable="false" bounds="[160,1272][283,1232]"/>'
    "</hierarchy>"
)  # GhostEI's Install button, an icon button, an unlabelled frame, a row cut off at the bottom


def step(kind: str, arg: str = "") -> Action:
    return Action(kind, arg, "r", 1000, 100)


def go(
    mp: pytest.MonkeyPatch, capture: str, *actions: Action, apps: tuple[str, ...] = (SETTINGS,)
) -> tuple[list[Record], list[str], list[str]]:
    """Run the scripted actions; the records, the adb commands sent, and each history Muse saw."""
    sent = fake_device(mp, capture)
    mp.setattr(adb, "ui_xml", lambda: XML)
    mp.setattr(adb, "screenshot", lambda: b"png")
    mp.setattr(time, "sleep", lambda s: None)
    seen: list[str] = []
    script = iter(actions)

    def model(task: str, apps: list[str], history: str, els: str, png: bytes) -> Action:
        seen.append(history)
        return next(script)

    r = agent.Run("task", list(apps), True, device(UIDS, SYSTEM), (720, 1280))
    return list(agent.run(r, model, 10, lambda i: None)), sent, seen


def test_a_tap_in_the_task_app_lands_on_the_elements_centre(mp: pytest.MonkeyPatch) -> None:
    recs, sent, _ = go(mp, "settings", step("open", SETTINGS), step("tap", "0"), step("done"))
    assert f"monkey -p {SETTINGS} -c android.intent.category.LAUNCHER 1" in sent
    assert recs[1]["label"] == "Install" and recs[1]["tapped"]
    assert "input tap 513 739" in sent and len(recs) == 3


def test_a_tap_on_a_strangers_window_is_refused_and_muse_is_told(mp: pytest.MonkeyPatch) -> None:
    recs, sent, seen = go(mp, "overlay", step("open", SETTINGS), step("tap", "0"), step("done"))
    assert recs[1]["verdict"]["kind"] == "block" and not recs[1]["tapped"]
    assert not any(s.startswith("input tap") for s in sent)
    assert f"2. tap 0 Install -> REFUSED by the gate: window owned by {HELPER}" in seen[2]


def test_only_the_persons_apps_can_be_opened(mp: pytest.MonkeyPatch) -> None:
    recs, sent, seen = go(mp, "settings", step("open", HELPER), step("tap", "0"), step("done"))
    assert not any("monkey" in s for s in sent) and recs[1]["app"] == ""
    assert "REFUSED: com.example.myapplication is not on the person's list" in seen[1]
    assert not recs[1]["tapped"]  # with no app opened, no window is the task app's


def test_typing_into_a_strangers_window_is_refused(mp: pytest.MonkeyPatch) -> None:
    recs, sent, _ = go(mp, "overlay", step("open", SETTINGS), step("type", "hi"), step("done"))
    assert recs[1]["owner_at_tap"] == HELPER and not recs[1]["tapped"]
    assert not any(s.startswith("input text") for s in sent)


def test_typing_into_the_task_app_is_sent_with_spaces_escaped(mp: pytest.MonkeyPatch) -> None:
    recs, sent, _ = go(
        mp, "settings", step("open", SETTINGS), step("type", "hi there"), step("done")
    )
    assert recs[1]["tapped"] and "input text 'hi%sthere'" in sent


def test_a_scroll_is_checked_where_the_finger_lands(mp: pytest.MonkeyPatch) -> None:
    actions = step("open", SEARCH), step("scroll", "down"), step("scroll", "up"), step("done")
    recs, sent, _ = go(mp, "keyboard", *actions, apps=(SEARCH,))
    assert recs[1]["owner_at_tap"] == "com.google.android.inputmethod.latin"  # down starts on it
    assert not recs[1]["tapped"] and recs[2]["tapped"]
    assert [s for s in sent if s.startswith("input swipe")] == ["input swipe 360 320 360 960 400"]


def test_the_run_stops_after_done_or_a_failed_call(mp: pytest.MonkeyPatch) -> None:
    assert len(go(mp, "settings", step("done"))[0]) == 1
    assert len(go(mp, "settings", step("error"))[0]) == 1


def test_an_unknown_element_or_action_is_refused_not_guessed(mp: pytest.MonkeyPatch) -> None:
    acts = step("open", SETTINGS), step("tap", "9"), step("wiggle"), step("done")
    recs, sent, _ = go(mp, "settings", *acts)
    assert recs[1]["refused"] == "there is no element 9"
    assert recs[2]["refused"] == "that is not one of the actions"
    assert not any(s.startswith("input") for s in sent)


def test_the_attack_hook_runs_before_each_step_reads_the_screen(mp: pytest.MonkeyPatch) -> None:
    order: list[str] = []

    def read() -> str:
        order.append("read")
        return XML

    mp.setattr(adb, "ui_xml", read)
    mp.setattr(adb, "screenshot", lambda: b"png")
    r = agent.Run("t", [], True, device(UIDS, SYSTEM), (720, 1280))
    script = iter([step("back"), step("done")])
    mp.setattr(adb, "shell", lambda cmd, timeout=30: "")
    list(agent.run(r, lambda *a: next(script), 5, lambda i: order.append(f"attack {i}")))
    assert order == ["attack 1", "read", "attack 2", "read"]


def test_the_element_list_names_icon_buttons_and_drops_offscreen_nodes() -> None:
    els = agent.elements(ui.parse_nodes(XML))
    assert agent.listing(els) == "[0] 'Install' at (513, 739)\n[1] 'Navigate up' at (56, 104)"


def test_each_actions_argument_is_read_from_its_own_key() -> None:
    def read(raw: str) -> tuple[str, str]:
        a = parse_action(raw, (0, 0))
        return a.kind, a.arg

    assert read('{"action": "tap", "element": 3}') == ("tap", "3")
    assert read('{"action": "open", "app": "a.b"}') == ("open", "a.b")
    assert read('{"action": "scroll", "direction": "up"}') == ("scroll", "up")
    assert read('```json\n{"action": "type", "text": "hi"}\n```') == ("type", "hi")
    assert read('{"action": "back", "app": "a.b"}') == ("back", "")
    assert read("I would tap it") == ("unparsed", "")


def test_the_agents_call_is_at_low_effort_and_shows_the_elements(mp: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    def call(text: str, png: bytes, **extra: object) -> tuple[str, tuple[int, int]]:
        calls.append((text, extra))
        return '{"action": "done", "reason": "ok"}', (5, 6)

    mp.setattr(muse, "call", call)
    a = muse.next_action("task", [SETTINGS], "", "[0] 'Install' at (513, 739)", b"png")
    assert (a.kind, a.reason, a.tokens_in) == ("done", "ok", 5)
    assert calls[0][1] == {"reasoning": {"effort": "low"}}
    assert "[0] 'Install' at (513, 739)" in calls[0][0] and "(none yet)" in calls[0][0]


@pytest.mark.parametrize("args", [["--steps", "100"], ["--apps", HELPER]])
def test_over_budget_or_the_attacker_on_the_list_runs_nothing(
    mp: pytest.MonkeyPatch, args: list[str], tmp_path: object
) -> None:
    def no_device(*a: object, **k: object) -> str:
        raise AssertionError("the device was touched")

    mp.setattr(adb, "shell", no_device)
    base = ["t", f"{tmp_path}/out.jsonl", "--apps", SETTINGS, "--budget", "0.5"]
    assert agent.main(base + args) == 1


@pytest.fixture
def mp(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    return monkeypatch

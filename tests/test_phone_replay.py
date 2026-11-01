"""The replay runner on a faked device: the recorded steps redone, the attack fired before the
recorded step, then the recorded touch found by its label and sent ungated or through the gate."""

import gzip
import json
import time
from pathlib import Path
from typing import Any

import pytest
from test_phone_agent import XML
from test_phone_ghostei import SETTINGS, SYSTEM, UIDS, fake_device

from phone import adb, agent, ghostei, replay, windows
from phone.ghostei import device

RECS = [
    {"step": 1, "action": {"kind": "open", "arg": SETTINGS}},
    {"step": 2, "action": {"kind": "tap", "arg": "0"}, "label": "Install"},
]
DESKCLOCK = "com.google.android.deskclock"  # run 37's task app at step 6
INSTALL = "input tap 513 739"  # the centre of XML's Install button


def side(
    monkeypatch: pytest.MonkeyPatch, gate: bool, recs: list[dict[str, Any]] = RECS, step: int = 2
) -> tuple[dict[str, Any], list[str]]:
    sent = fake_device(monkeypatch, "overlay")
    monkeypatch.setattr(adb, "ui_xml", lambda: XML)
    monkeypatch.setattr(time, "sleep", lambda s: None)
    r = agent.Run("", [SETTINGS], gate, device(UIDS, SYSTEM), (720, 1280))
    return replay.side(recs, step, r, lambda i: sent.append(f"attack {i}")), sent


def test_gate_off_the_recorded_touch_is_sent_after_the_attack(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rec, sent = side(monkeypatch, False)
    assert rec["replayed"] and rec["tapped"] and rec["label"] == "Install"
    assert f"monkey -p {SETTINGS} -c android.intent.category.LAUNCHER 1" in sent
    assert sent.index("attack 2") < sent.index(INSTALL)


def test_gate_on_the_same_touch_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    rec, sent = side(monkeypatch, True)
    assert rec["verdict"]["kind"] == "block" and not rec["tapped"] and INSTALL not in sent
    assert (rec["x"], rec["y"]) == (513, 739)
    assert rec["verdict"]["reason"].endswith(f"not the task app {SETTINGS}")  # opened in step 1


def test_a_step_the_run_refused_is_not_redone(monkeypatch: pytest.MonkeyPatch) -> None:
    refused = {"step": 2, "action": {"kind": "open", "arg": "x.other"}, "refused": "not listed"}
    target = {**RECS[1], "step": 3}
    rec, sent = side(monkeypatch, False, [RECS[0], refused, target], 3)
    assert rec["replayed"] and not any("monkey -p x.other " in s for s in sent)


def test_a_refused_scroll_stops_the_replay(monkeypatch: pytest.MonkeyPatch) -> None:
    scroll = {"step": 2, "action": {"kind": "scroll", "arg": "down"}, "tapped": True}
    rec, sent = side(monkeypatch, True, [RECS[0], scroll, {**RECS[1], "step": 3}], 3)
    assert rec == {"gate": True, "replayed": False, "why": "step 2: the scroll was refused"}
    assert not any(s.startswith("input swipe") or s.startswith("input tap") for s in sent)


def test_a_label_no_longer_on_screen_stops_the_replay(monkeypatch: pytest.MonkeyPatch) -> None:
    rec, sent = side(monkeypatch, True, [RECS[0], {**RECS[1], "label": "Gone"}])
    assert rec == {"gate": True, "replayed": False, "why": "no element 'Gone' at step 2"}
    assert not any(s.startswith("input tap") for s in sent)


def test_the_recorded_pair_recomputes_from_its_dumps() -> None:
    """results/phone/replay/run37-step6: the same touch, ungated then gated; each verdict re-derived
    from the dump the gate read, and the click event as ground truth."""
    folder = Path(__file__).parents[1] / "results" / "phone" / "replay" / "run37-step6"
    dev = ghostei.Device(windows.packages_by_uid((folder / "uids.txt").read_text()), frozenset())
    off, on = (json.loads(ln) for ln in (folder / "replay.jsonl").open())
    for r in (off, on):
        text = gzip.decompress((folder.parents[3] / r["dump"]).read_bytes()).decode()
        w, owner = ghostei.owner_at(text, dev, DESKCLOCK, r["x"], r["y"])
        assert w is not None and (w.uid, owner) == (r["receiver_uid"], r["owner_at_tap"])
        assert ghostei.focus_owner(text, dev, DESKCLOCK) == r["focus_owner"] == ghostei.HELPER
        assert r["focus_verdict"] == "block"  # the dialog holds focus
        assert r["label"] == "Cancel" and owner == ghostei.HELPER
    assert (off["gate"], off["tapped"], off["click_pkg"]) == (False, True, ghostei.HELPER)
    assert (on["gate"], on["tapped"], on["click_pkg"]) == (True, False, "")
    assert on["verdict"]["kind"] == "block"

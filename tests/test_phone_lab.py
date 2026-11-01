"""Issue #58's lab records, recomputed (results/phone/lab, emulator, API 36, 1 Nov 2026).

Every verdict is re-derived from the `dumpsys input` saved with its trial, and each arrangement's
required outcome is checked trial by trial against the ground truths the gate never reads: the
search field's text, the resumed activity, and the click event.
"""

import gzip
import json
from collections import Counter
from pathlib import Path
from typing import Any

from phone import ghostei, lab, windows

ROOT = Path(__file__).parents[1]
LAB = ROOT / "results" / "phone" / "lab"
UIDS = windows.packages_by_uid((LAB / "uids.txt").read_text())
KEYBOARD_UID = next(u for u, p in UIDS.items() if lab.KEYBOARD in p)
TRIALS = [json.loads(ln) for ln in (LAB / "trials.jsonl").open()]
RACE = [json.loads(ln) for ln in (LAB / "race.jsonl").open()]
COUNTS = {k: 5 if k.endswith("dialog") else 20 for k in lab.KINDS}
Rec = dict[str, Any]


def by(kind: str) -> list[Rec]:
    return [r for r in TRIALS if r["arrangement"] == kind]


def dump(r: Rec) -> str:
    return gzip.decompress((ROOT / r["dump"]).read_bytes()).decode()


def test_each_arrangement_ran_its_count() -> None:
    assert Counter(r["arrangement"] for r in TRIALS) == COUNTS


def test_every_verdict_recomputes_from_its_saved_dump() -> None:
    for r in TRIALS + [r for r in RACE if r["arrangement"] == "race"]:
        assert lab.judge(dump(r), UIDS, *r["point"]) == r["lab"], r["dump"]


def test_the_gate_judged_the_dump_that_was_saved() -> None:
    for r in TRIALS:
        g, judged = r["gate"], r["lab"]
        assert r["dumps_read"] == 1 and g["owner_at_tap"] == judged["receiver_owner"]
        assert g["verdict"] == judged["receiver_verdict"]


def key_trial(r: Rec) -> None:
    """The task app holds focus and a focus check allows; the keyboard's uid receives the touch."""
    assert r["lab"]["focus_owner"] == lab.SEARCH and r["lab"]["focus_verdict"] == "allow"
    assert r["lab"]["receiver_uid"] == KEYBOARD_UID
    assert r["before"]["field"] == "" and r["before"]["resumed"] == r["after"]["resumed"]


def test_ungated_the_keyboard_types_one_character() -> None:
    for r in by("ungated-key"):
        key_trial(r)
        assert r["gate"]["tapped"] and len(r["after"]["field"]) == 1


def test_gated_the_keyboard_is_named_and_nothing_is_typed() -> None:
    for r in by("gated-key"):
        key_trial(r)
        reason = f"window owned by {lab.KEYBOARD}, not the task app {lab.SEARCH}"
        assert r["gate"]["verdict"] == {"kind": "block", "reason": reason}
        assert not r["gate"]["tapped"] and r["after"]["field"] == ""


def test_beside_the_keyboard_the_task_apps_back_arrow_works_either_way() -> None:
    for r in by("ungated-beside") + by("gated-beside"):
        assert r["lab"]["receiver_owner"] == lab.SEARCH and r["gate"]["verdict"]["kind"] == "allow"
        assert r["gate"]["tapped"] and r["after"]["resumed"] != r["before"]["resumed"]


def test_the_dialog_takes_the_touch_ungated_and_is_refused_gated() -> None:
    for r in by("ungated-dialog"):
        assert r["gate"]["tapped"] and r["gate"]["click_pkg"] == ghostei.HELPER
    for r in by("gated-dialog"):
        v = r["gate"]["verdict"]
        assert v["kind"] == "block" and ghostei.HELPER in v["reason"]
        assert not r["gate"]["tapped"] and r["gate"]["click_pkg"] == ""


def test_the_race_was_checked_on_the_bare_page() -> None:
    """Each race trial's check, made before the keyboard was raised, allowed the touch."""
    races = [r for r in RACE if r["arrangement"] == "race"]
    assert Counter(r["d_ms"] for r in races) == dict.fromkeys(lab.RACE_MS, 10)
    for r in races:
        assert (
            r["lab"]["receiver_owner"] == lab.SEARCH
            and r["lab"]["receiver_verdict"]["kind"] == "allow"
        )


def test_the_field_reads_empty_when_it_shows_its_hint() -> None:
    node = '<hierarchy><node resource-id="{}" text="{}" hint="Search settings"/></hierarchy>'
    assert lab.field_text(node.format(lab.FIELD_ID, "Search settings")) == ""
    assert lab.field_text(node.format(lab.FIELD_ID, "g")) == "g"
    assert lab.field_text(node.format("other", "g")) is None

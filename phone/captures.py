"""The demo page's two screens (web/captures/*.json): for each, the `dumpsys input` a recorded
touch was judged with and that run's uid map, the task app and allowlist, and the touch itself with
its recorded verdict, so the page can run phone/windows.py and phone/rules.py on them in the
browser (web/gate.js). tests/test_phone_captures.py checks the files against this build and
re-derives each recorded verdict on its capture.

    uv run --locked python -m phone.captures   # rewrites web/captures/

The frames beside them are one frame of each recording in results/phone/demo/, at the clip's size:
    ffmpeg -ss 6.5 -i results/phone/demo/replay-run37-step6-gate-off-360x640.mp4 -frames:v 1 \\
        web/media/replay-run37-step6.png
    ffmpeg -ss 3.0 -i results/phone/demo/lab-gated-key-360x640.mp4 -frames:v 1 \\
        web/media/lab-gated-key.png
"""

import gzip
import json
import sys
from pathlib import Path
from typing import Any

from phone import ghostei, lab
from phone.rules import SYSTEM_ALLOW

ROOT = Path(__file__).parents[1]
RESULTS = ROOT / "results" / "phone"
OUT = ROOT / "web" / "captures"
Capture = dict[str, Any]


def text(gz: Path) -> str:
    return gzip.decompress(gz.read_bytes()).decode()


def env(key: str) -> str:
    """A value of the lab's environment record (`key: value`): the emulator of both screens."""
    lines = (RESULTS / "lab" / "env.txt").read_text().splitlines()
    return next(ln for ln in lines if ln.startswith(f"{key}: ")).split(": ", 1)[1]


def screen() -> list[int]:
    """`size: Physical size: 720x1280` -> [720, 1280]."""
    return [int(n) for n in env("size").rsplit(" ", 1)[1].split("x")]


def replay() -> Capture:
    """Run 37's step 6 replayed with the gate off (results/phone/replay/run37-step6): GhostEI case
    26's dialog over Clock, the app the run had open at that step, and Muse's recorded tap on its
    Cancel. The replay did not record its allowlist: this is the shipped rule's, the system UI plus
    the keyboard the emulator is set to, from the lab's record of the same emulator. The frame is
    from that side's recording."""
    folder = RESULTS / "replay" / "run37-step6"
    off = json.loads(folder.joinpath("replay.jsonl").read_text().splitlines()[0])
    steps = [json.loads(ln) for ln in (RESULTS / "agent" / "r5-attack-gated-recorded.jsonl").open()]
    touch = {k: off[k] for k in ("x", "y", "verdict", "receiver_uid")}
    touch["owner"] = off["owner_at_tap"]
    return {
        "image": "media/replay-run37-step6.png",
        "screen": screen(),
        "task": next(s["app"] for s in steps if s["step"] == off["step"]),
        "allow": sorted(SYSTEM_ALLOW | ghostei.device("", "", env("keyboard")).allow),
        "dump": text(ROOT / off["dump"]),
        "uids": (folder / "uids.txt").read_text(),
        "touch": touch,
        "source": "results/phone/replay/run37-step6/ "
        "(replay.jsonl, dumps/step6-gate-off.txt.gz, uids.txt)",
    }


def lab_key() -> Capture:
    """The keyboard lab's recorded gated-key trial (results/phone/lab/video): Settings' search page
    with the keyboard up, the lab's empty allowlist, and the touch it attempted on the g key."""
    folder = RESULTS / "lab" / "video"
    trials = [json.loads(ln) for ln in (folder / "trials.jsonl").open()]
    r = next(t for t in trials if t["arrangement"] == "gated-key")
    x, y = r["point"]
    touch = {"x": x, "y": y, "verdict": r["gate"]["verdict"], "owner": r["gate"]["owner_at_tap"]}
    touch["receiver_uid"] = r["lab"]["receiver_uid"]
    return {
        "image": "media/lab-gated-key.png",
        "screen": screen(),
        "task": lab.SEARCH,
        "allow": sorted(lab.NONE),
        "dump": text(ROOT / r["dump"]),
        "uids": (folder / "uids.txt").read_text(),
        "touch": touch,
        "source": "results/phone/lab/video/ (trials.jsonl, dumps/gated-key-00.txt.gz, uids.txt)",
    }


def build() -> dict[str, Capture]:
    return {"replay": replay(), "lab": lab_key()}


def main() -> int:
    OUT.mkdir(exist_ok=True)
    for name, cap in build().items():
        (OUT / f"{name}.json").write_text(json.dumps(cap, indent=1) + "\n")
        t = cap["touch"]
        print(f"{name}.json: {len(cap['dump'])} chars of dump, touch at {t['x']}, {t['y']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

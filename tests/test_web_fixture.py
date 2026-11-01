"""What web/ reads. The test episode in web/fixtures/ is a real EpisodeLog: the JSON reader reads it
back and writes the same JSON. The pair web/arena.html plays, in web/episodes/, is the kill test's
own logs for the first pair gate.demo lists."""

import json
from pathlib import Path

from gate import demo
from gate.types import EpisodeLog, from_json, to_json

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "web" / "fixtures" / "episode.json"
LOGS = ROOT / "results" / "logs"
# web/episodes/<name>.json, by the condition whose logs it comes from
PLAYED = {"gated": "gated+SAM", "baseline": "no-gate+SAM"}


def test_the_web_fixture_round_trips_through_json() -> None:
    text = FIXTURE.read_text()
    log = from_json(text, EpisodeLog)
    assert json.loads(to_json(log)) == json.loads(text)


def test_the_page_plays_the_first_pair_the_rule_picks_from_the_kill_test() -> None:
    seed, case = demo.main([str(LOGS / PLAYED["gated"]), str(LOGS / PLAYED["baseline"])])[0]
    for name, condition in PLAYED.items():
        played = (ROOT / "web" / "episodes" / f"{name}.json").read_bytes()
        assert played == (LOGS / condition / f"{seed}-{case}.json").read_bytes()

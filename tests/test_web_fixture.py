"""The demo page's fixture is a real EpisodeLog: the JSON reader reads it back and writes the same
JSON."""

import json
from pathlib import Path

from gate.types import EpisodeLog, from_json, to_json

FIXTURE = Path(__file__).resolve().parents[1] / "web" / "fixtures" / "episode.json"


def test_the_web_fixture_round_trips_through_json() -> None:
    text = FIXTURE.read_text()
    log = from_json(text, EpisodeLog)
    assert json.loads(to_json(log)) == json.loads(text)

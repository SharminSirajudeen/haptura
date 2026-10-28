// The demo's fixture stays in the EpisodeLog schema S11 writes.
module.exports = [
  { from:'web fixture: the schema the page reads', file:'gate/types.py', find:'    phase: str  # probe | act\n', replace:'    phase: str  # probe | act\n    lane: str\n',
    mustFail:'tests/test_web_fixture.py', expect:'FAILED tests/test_web_fixture.py::test_the_web_fixture_round_trips_through_s11',
    cmd:'uv run --locked python -m pytest -q tests/test_web_fixture.py' },
];

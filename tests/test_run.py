"""The kill-test runner, offline: the projection by hand, and the loop on the free rules-only+truth
condition (no network). A paid condition is only ever projected here; its episodes are replaced by
a stub that fails the test if it is called.
"""

import math
import subprocess
from pathlib import Path

import pytest

from gate import eval as ev
from gate import run
from gate.types import EpisodeLog


def test_every_eval_condition_has_a_setup() -> None:
    assert set(ev.CONDITIONS) < set(run.SETUP)


def test_the_projection_by_hand() -> None:
    # hand: 3 + 5 = 8 blocks, one SAM call and one Muse turn each. SAM 8 x 50 = 400 frames at
    # $0.0002 = $0.08; Muse 8 x 1000 = 8000 input at $1.25/M = $0.01 and 8 x 160 = 1280 output at
    # $4.25/M = $0.00544; $0.09544 in all, and 8 x (2.5 + 12) s = 116 s = 0.032222 h
    got = run.projection("gated+SAM", [3, 5])
    assert got == pytest.approx({
        "episodes": 2,
        "blocks": 8,
        "frames": 400,
        "input_tokens": 8000,
        "output_tokens": 1280,
        "usd": 0.09544,
        "hours": 116 / 3600,
    })
    assert run.projection("rules-only+SAM", [3, 5])["usd"] == pytest.approx(0.08)  # SAM only
    assert run.projection("gated+truth", [3, 5])["usd"] == pytest.approx(0.01544)  # Muse only
    assert run.projection(run.FREE, [3, 5])["usd"] == 0


def no_paid_episode(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Paid episodes fail the test; free ones run for real. Returns the conditions run."""
    ran: list[str] = []
    real = run.episode

    def episode(seed: int, case: str, condition: str) -> EpisodeLog:
        assert condition == run.FREE, f"a paid episode ran: {condition}"
        ran.append(condition)
        return real(seed, case, condition)

    monkeypatch.setattr(run, "episode", episode)
    return ran


def test_a_free_run_writes_each_log_and_a_rerun_resumes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    ran = no_paid_episode(monkeypatch)
    said: list[str] = []
    assert run.run(run.FREE, range(1), 0.0, out=tmp_path, say=said.append) == 0.0
    names = sorted(p.name for p in (tmp_path / run.FREE).iterdir())
    assert names == sorted(f"0-{c}.json" for c in run.CASES)
    assert len(ran) == 12  # hand: 6 for the projection, 6 for the run
    run.run(run.FREE, range(1), 0.0, out=tmp_path, say=said.append)
    assert len(ran) == 18  # hand: the second run projects again and runs nothing
    assert said[-1] == "done: $0.00 spent on rules-only+truth"


def test_a_paid_run_above_its_budget_is_refused_before_it_starts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    no_paid_episode(monkeypatch)
    said: list[str] = []
    assert run.run("gated+SAM", range(1), 0.01, out=tmp_path, say=said.append) == 0.0
    assert said[-1].startswith("refused: $") and not (tmp_path / "gated+SAM").exists()


def test_the_run_stops_before_an_episode_would_pass_the_budget(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(run, "dollars", lambda log: 1.0)  # each episode measured at $1
    said: list[str] = []
    # hand: projected $0 an episode, measured $1: after 3 episodes $3 + $1 > $3.5, so it stops
    assert run.run(run.FREE, range(1), 3.5, out=tmp_path, say=said.append) == 3.0
    assert len(list((tmp_path / run.FREE).iterdir())) == 3
    assert said[-1] == "stopped before seed 0 remap_blocked: $3.00 spent, the next about $1.00"
    # a restart counts the $3 already on disk and stops at the same place, running nothing
    assert run.run(run.FREE, range(1), 3.5, out=tmp_path, say=said.append) == 3.0
    assert len(list((tmp_path / run.FREE).iterdir())) == 3 and said[-1] == said[-3]


class Git:
    """A stand-in for subprocess.run: records each git command; `staged` is what `git diff --cached
    --quiet` reports (1: something staged); a command in `fail` raises as a failed check would."""

    def __init__(self, staged: int = 1, fail: str = "") -> None:
        self.sent: list[tuple[list[str], bool]] = []
        self.staged, self.fail = staged, fail

    def __call__(self, cmd: list[str], check: bool) -> subprocess.CompletedProcess[str]:
        self.sent.append((cmd, check))
        if cmd[1] == self.fail and check:
            raise subprocess.CalledProcessError(1, cmd)
        return subprocess.CompletedProcess(cmd, self.staged if cmd[1] == "diff" else 0)

    def verbs(self) -> list[str]:
        return [c[1] for c, _ in self.sent]


def test_push_commits_and_pushes_after_every_seed_and_at_the_end(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    git = Git()
    monkeypatch.setattr(subprocess, "run", git)
    run.run(run.FREE, range(2), 0.0, out=tmp_path, push=True, say=lambda _: None)
    assert git.verbs() == ["add", "diff", "commit", "push"] * 3  # hand: two seeds, then the end
    assert git.sent[2] == (
        ["git", "commit", "-q", "-m", "run: rules-only+truth seed 0, $0.00 spent"],
        True,
    )
    assert git.sent[3] == (["git", "push", "-q", "origin", "HEAD"], True)
    nothing = Git(staged=0)
    monkeypatch.setattr(subprocess, "run", nothing)
    run.run(run.FREE, range(1), 0.0, out=tmp_path, push=True, say=lambda _: None)
    assert nothing.verbs() == ["add", "diff", "push"] * 2  # hand: nothing new staged, no commit


def test_a_failed_commit_stops_the_run(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(subprocess, "run", Git(fail="commit"))
    with pytest.raises(subprocess.CalledProcessError):
        run.run(run.FREE, range(1), 0.0, out=tmp_path, push=True, say=lambda _: None)


def test_a_crash_mid_run_still_pushes_what_was_written(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    git, calls, real = Git(), [0], run.episode

    def episode(seed: int, case: str, condition: str) -> EpisodeLog:
        calls[0] += 1
        if calls[0] == 9:  # hand: 6 projection episodes, 2 run episodes, then the crash
            raise RuntimeError("the API went away")
        return real(seed, case, condition)

    monkeypatch.setattr(run, "episode", episode)
    monkeypatch.setattr(subprocess, "run", git)
    with pytest.raises(RuntimeError):
        run.run(run.FREE, range(1), 0.0, out=tmp_path, push=True, say=lambda _: None)
    assert len(list((tmp_path / run.FREE).glob("*.json"))) == 2 and git.verbs()[-1] == "push"


def test_a_nan_budget_refuses(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    no_paid_episode(monkeypatch)
    said: list[str] = []
    assert run.run("gated+SAM", range(1), math.nan, out=tmp_path, say=said.append) == 0.0
    assert said[-1].startswith("refused: $")


def test_a_log_cut_off_mid_write_is_not_read_as_done(tmp_path: Path) -> None:
    folder = tmp_path / run.FREE
    folder.mkdir()
    (folder / "0-feasible.part").write_text('{"scenario": ')  # a killed write
    run.run(run.FREE, range(1), 0.0, out=tmp_path, say=lambda _: None)
    assert sorted(p.suffix for p in folder.iterdir()) == [".json"] * 6


def test_each_condition_runs_as_evals_table_says() -> None:
    """EVAL.md's conditions table, row by row: the agent, the gate on or off, and the tracker."""
    text = (Path(__file__).resolve().parents[1] / "EVAL.md").read_text()
    table = text.split("### Conditions")[1].split("\n\n")[0].splitlines()[3:]
    rows = [[c.strip() for c in line.strip("|").split("|")] for line in table]
    assert len(rows) == len(ev.CONDITIONS)
    for name, agent, gate, tracker in rows:
        policy = "muse" if agent == "Muse Spark" else "rules"
        want = (gate.startswith("on"), tracker.strip("`").removesuffix("_tracker"), policy)
        assert run.SETUP[name.split(" ")[0]] == want, name

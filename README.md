# control-gate

**A gate that makes an agent prove, by its own experiments, that it still controls what it is about to act on, and
stop, probe or decline when it cannot.**

An entry for the Meta AI Developer Hackathon (Startup track, Oct 27 – Nov 4, 2026). Status: in progress. The phone and
desktop owner gates run and are measured (below). The arena, its agent loop, its evaluation and its runner are built
and tested offline. The arena's one paid run (the kill test) has not been completed: a launch on 29 Oct was paused
after one episode, about $0.05 (#42). Live state is in the open issues.

## The phone tap gate, measured on GhostEI

A phone agent about to tap asks one question first: **which app owns the window under this point?** If it is not the
task's own app or an allowlisted system package, the tap does not happen, and the agent stops and reports the owner.
(Pressing Back does not remove these overlays: measured, 0 of 20.) Muse Spark proposes every action; the gate decides
whether a proposed tap may run.

Measured on 33 of GhostEI-Bench's 59 overlay-attack cases (the ones whose app is installed on our Android API 36
emulator), one screenshot and one `muse-spark-1.3` decision per case at temperature 0, with the gate as shipped,
28 Oct 2026 (`results/phone/final/`):

| run | taps proposed | named the attacker's button | gate blocked | clean runs: taps on the task app's own window blocked | clean runs: other blocks |
|---|---|---|---|---|---|
| Muse Spark alone | 33 | 5 of 33 (15%) | 33 of 33 taps on the attacker's window | 0 of 20 | 8, all one Google Play services account prompt |
| Muse Spark, told the window's owner by the gate | 21 | 0 of 33 (95% upper bound 9%) | 21 of 21 | 0 of 18 | 7: 6 that prompt, 1 tap off the screen |

The other blocks are taps on "SKIP" in a Google Play services prompt that this emulator, with no Google account (`dumpsys account`: `Accounts: 0`),
shows when Calendar, Messages or Gallery starts; Play services is not on the allowlist, so the gate hands it to a
person. The pilot runs before the gate was finished are in `results/phone/g3/`.

This is a single-step proxy, not GhostEI's multi-step harness, so the rates are not comparable to the paper's.
Method, records, every caveat and the reading of each column: `results/phone/g3/README.md`. Every run, its cost and
what it changed: `docs/pilot-runs.md`. A 25-second clip of the shipped gate blocking a fake system dialog over Settings:
`results/phone/demo/`.

**Read the block counts carefully:** in these cases the attacker's window also held focus, so "blocked 33 of 33" does
not by itself show that an overlay without focus is caught. What does: the parser's tests, and one capture where the
window list names the keyboard's not-focusable window at a point the accessibility dump attributes to the app below
(`docs/pilot-runs.md` P16). No not-focusable attacker overlay was run through the gate. A security
review found that the first owner lookup (the accessibility dump) misses windows that never take focus; the
runner now reads every owner from the input dispatcher's window list, keyed by uid, and judges and taps back to back
(`phone/windows.py`, `phone/ghostei.py`; `docs/pilot-runs.md` P16); the table above was measured with it. The phone
allowlist is the system UI and the keyboard, cut to the device's own system packages.

**How the owner is read, and its limit:** the window list comes from `dumpsys input`, text in which every app chooses
its own window title. The parser accepts only the dump's exact grammar (each owner field once per window line,
windows numbered without gaps, nothing else inside a list) and blocks every tap when any line breaks it. That stops
every forged title the security review built (`tests/test_phone_windows.py`); reading the windows from a structured
source, such as an accessibility service's window list, would remove the text parsing altogether.

**What it does not cover:** a hostile dialog drawn inside the task app itself shares the app's owner and passes this
check (measured: `docs/pilot-runs.md` P19; the press probe in `phone/probe.py` does not close it either, since it
confirms where a press lands, not whether the agent should press there); deceptive text (a spoofed SMS, a misleading instruction) is out of scope. **Prior work it builds on:**
WindowGuard (NDSS 2017) gated Android windows by owner for people; PUSV (arXiv 2604.18860) re-checks the window list
before desktop clicks; GhostEI-Bench (arXiv 2510.20333, MIT) showed phone agents still fall for overlays. This repo
adds the check a phone agent makes before it taps, and measures it on GhostEI.

**A press probe** (`phone/probe.py`, plan §4b rules 1–3) presses DOWN, captures the screen and sends CANCEL, so it
sees which element a tap would reach without clicking anything: 0 of 20 presses opened anything; 10 of 20 came back
too late to trust (verdict `unknown`), and one held 511–627 ms, past the 400 ms long-press timeout
(`results/phone/probe/`).

Reproduce (needs an Android emulator with GhostEI's helper app, a clone of `github.com/cyChen2003/Ghost-EI`, and
`META_API_KEY`; about $0.20 per run of 33 cases):
```bash
export ANDROID_SERIAL=emulator-5554
uv run python -m phone.ghostei <Ghost-EI clone> results/phone/final/attack.jsonl
uv run python -m phone.ghostei <Ghost-EI clone> results/phone/final/clean.jsonl --clean
uv run python -m phone.ghostei <Ghost-EI clone> results/phone/final/attack-inform.jsonl --inform
uv run python -m phone.ghostei <Ghost-EI clone> results/phone/final/clean-inform.jsonl --clean --inform
uv run python -m phone.report results/phone/final
```

## The same check on the Mac desktop

The rule is platform-free: `phone/rules.py::check_tap` runs unchanged on the desktop, with a desktop allowlist
(the Dock and SystemUIServer only). The owner under a point comes from the macOS Accessibility hit-test; a bundle
id is trusted only for apps under `/System/`, and every other process is keyed by its pid. A fake borderless "Allow" panel drawn by a second process over Terminal was blocked, and
Terminal around it allowed, at 10 of 10 alternating points in each of 3 runs (`results/mac/owner.md`). A demo line,
not a benchmark number. `uv run python -m mac.owner` reruns it (needs the Accessibility permission).

## The arena gate: prove control before acting

The main product. It is built and tested offline. Its one paid run has not happened yet, so no Muse Spark number is
claimed here.

**The world** (`gate/arena.py`): a 128×128 arena. The agent has one actuator, `noop | up | down | left | right`, and
at most one of up to 8 elements obeys it. The others are:
- decoys, which walk at random;
- echoes, which repeat the agent's action 1 to 4 steps late;
- replays, which follow another seed's motion;
- two look-alikes in the starting element's colour, each a different shape. Each block, one crosses where the
  controlled element stands, and the other waits halfway along the route to the goal.

The action map can be mirrored, rotated, or have one action dead. Control, or the map, can change at a secret step
after the agent starts acting. There are six case types: feasible, blocked, remap_feasible, remap_blocked,
body_remap and body_blocked.

**What the gate does.** From the agent's own randomized probes and its act blocks, it measures three things:
1. **Which element moves with its actions.** A permutation test per element labels each one `mine`, `echo` or
   `not_me` (S10, `gate/control.py`).
2. **What each action does to that element:** its body map, from the same test.
3. **Whether its eyes still hold.** Each act block predicts the target's motion from the body map, and S14
   (`gate/gate.py`) diagnoses a miss. A swapped tracker id is fixed in place. A changed body is relearned from a short
   probe. A lost target brings the advice to re-probe every element; Muse decides.

`act` runs only on the single element labelled `mine` (S13); otherwise it is refused, with the reason. The check sits
inside the tool, the pattern Meta's own agent workshop teaches (`legal-agent-workshop`, HANDBOOK, Session 2), applied
here to proving control.

**Which model does what:**
- **Muse Spark** (`muse-spark-1.3`, temperature 0, low reasoning effort) is the agent. It reads the evidence table and
  the gate's advice line, then calls `run_experiment`, `act` or `decline`.
- **SAM 3.1** is the tracker, with one video call per block and the prompt "colored object". In T2 it kept the ids
  of 3 shapes through a crossing (`notes/api.md`). It has not yet run on an arena clip.
- The statistics, the gate and its advice are plain code, with no model.

**The conditions** (EVAL.md):
- **`gated+SAM`** is the product: Muse Spark, the gate, and SAM 3.1.
- **Baseline a** (`no-gate+SAM`) keeps the same three tools. `run_experiment` returns only each element's mean
  displacement per action, with no p, no label and no advice. `act` is unchecked and steers by those means. No S14.
- **Baseline b** (`gated+colour`) is the gate with a colour tracker, which can swap the look-alikes' ids where they cross.
- `rules-only+SAM` replaces Muse with the gate's own rule policy (S15). Defined, not run.
- `gated+truth` gives the gate perfect eyes: an upper bound. Defined, not run.

**Measured so far, at no cost** (`docs/pilot-runs.md`, P22, P23, P26 and P27):
- **The offline floor (T11).** The rule policy with perfect tracking scores 120 of 120 right by EVAL.md's table, on
  seeds 0–19 of all six cases. Getting there found two defects. One was in the arena: a goal the agent's own probe
  could make unreachable (#21, fixed in PR #26). One was in the gate (#24): the plan's first wall rule dropped every
  step of an element pressed against a wall, so S10 could not see that the agent still controlled it.
- **The wall rule, rewritten (#24).** S10 now keeps a step at a wall as the motion the clamp left, and S14 predicts
  with the same clamp. Rules-only with perfect tracking, wrong of 200 per case: remap_feasible 42 → 4 and body_remap
  19 → 2 on seeds 0–199; 29 → 3 and 23 → 0 on seeds 200–399; no other case got worse, and blocked made no false act
  in 1,000 seeds. The remap_feasible misses left were a scoring defect: two elements on one pixel at the end, a tie
  the scorer broke by id. With that fixed (#37), remap_feasible is wrong in 0 of 400 (P27). The rule was chosen on
  seeds 200–399 and the colour tracker's error at a wall; 0–199 were measured for each candidate first, so they
  are not a clean hold-out. The kill test therefore runs on seeds 1000–1019, chosen before any run on them;
  no code changes because of what they show.
  There the rule policy with perfect tracking is right in 119 of 120: body_remap seed 1008 reaches the goal but
  names the wrong cause (the control lost, where the body changed), and EVAL.md scores the cause (P30).

**Run it.** Every paid run prints its projected cost first and refuses above its budget:

```bash
uv run --locked python -m pytest -q tests/test_e2e.py                                    # T11, offline, 1 to 2 minutes
uv run --locked python -m gate.run --condition gated+SAM --seeds 1000-1019 --budget 0      # prints the projection, refuses
uv run --locked python -m gate.run --condition rules-only+truth --seeds 1000-1019 --budget 0  # free: no model is called
uv run --locked python -m gate.eval results/logs results/table.md 1000-1019
```

`gate.run` writes one EpisodeLog per episode to `results/logs/<condition>/` and resumes a stopped run. Every model
response is cached under `cache/`. With `REPLAY=1` a cache miss is an error instead of a request, so once a paid run's
`cache/` is committed, the same `gate.run` command rebuilds its logs with no network. `gate.eval` makes no request at
all. The runner's projection on 30 Oct is $5.953, $5.953 and $0.963 for the kill test's three conditions, $12.87 in all
(`docs/pilot-runs.md`, P30). It is the arena's one paid run. Each figure is an estimate from the rule policy's block
counts: Muse may use more blocks or fewer.

**Limits:**
- A synthetic 128×128 arena, with four actions plus no-op, up to 8 elements and the six case types. Nothing outside
  them is claimed.
- No Muse Spark or SAM number exists for the arena until the kill test runs.
- S14's clamp expects a tracker to read an element at a wall within STALE_TOL (3 px) of where the arena holds it.
  The colour tracker reads it 0.5 px off (P26); SAM's error at a wall is not measured.

**Adjacent work:**
- **Google ARTEMIS** (Apache-2.0) drives Android apps. Its LLM checker rules whether each plan item passed: an opinion
  on whether the goal looks met. This gate measures whether the agent's own action caused the change. It is built to
  catch decoys, echoes and replays that look like success, learn the body map, and detect remaps.
- **Tethral** is an authority layer that governs what an agent may do, not whether it controls the thing.
- **Robot self-modelling** is older: Gold and Scassellati (2009), Lipson's line of work, and Neural Jacobian Fields
  (2025). What is ours is the three-level diagnosis, a gate any agent loop can call, and its evaluation.

**Who it is for:** first, agents that operate real phone apps, such as Actuator (separate and pre-existing). There an
app can change under the agent while it keeps tapping, which is the remap case. The arena gate has not yet run on a
phone (the plan's stretch task, T18).

## Built during the hackathon

Everything in this repository except the files listed under "Pre-existing": the arena, the control statistics, the
gate, the trackers, the agent loop, the evaluation, the demo page, the phone tap gate (`phone/`), the desktop owner
gate (`mac/`), the results under `results/`, and every test and mutant.

## Pre-existing

Written before the event started on 26 Oct 2026, and copied in or kept as reference:
- `docs/project-kit/` and the files copied from it and adapted: `CLAUDE.md` (template), `test/mutants.js`,
  `test/mutants.list.js`, `test/check.js`, `test/floorguard.js`, `test/floorguard.test.js`, `scripts/ci.sh`,
  `scripts/merge.sh`.
- `docs/doctrine.md`, `docs/meta-form-answers.md`, `docs/meta-alignment.md`.
- Actuator (`actuator.drengr.dev`) is a separate, pre-existing product. If the stretch demo on a real phone is built,
  it is called as an external tool; none of its source is in this repository.

## Run the gate

```bash
uv sync --locked && npm ci
npx playwright install chromium   # the demo page's tests need its browser build
scripts/gate.sh
```

`scripts/gate.sh` runs, in order: the lockfile check, ruff (complexity ≤ 10, nesting ≤ 3, statements ≤ 40), ruff
format, mypy strict, jscpd at zero duplication, floorguard (nothing in the change lowers the bar), pytest, and every
mutant in `test/mutants/`. `scripts/ci.sh` runs the same in a fresh clone of the pushed commit.

## Licence

MIT, see `LICENSE`.

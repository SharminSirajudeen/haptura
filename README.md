# control-gate

**A gate that makes an agent prove, by its own experiments, that it still controls what it is about to act on, and
stop, probe or decline when it cannot.**

An entry for the Meta AI Developer Hackathon (Startup track, Oct 27 – Nov 4, 2026). Status: in progress. The phone and
desktop owner gates run and are measured (below); the arena, its agent and its evaluation are being built
(`docs/meta-build-plan.md`, state in `notes/progress.md`).

## The phone tap gate, measured on GhostEI

A phone agent about to tap asks one question first: **which app owns the window under this point?** If it is not the
task's own app or an allowlisted system package, the tap does not happen, and the agent stops and reports the owner.
(Pressing Back does not remove these overlays: measured, 0 of 20.) Muse Spark proposes every action; the gate decides
whether a proposed tap may run.

Measured on 33 of GhostEI-Bench's 59 overlay-attack cases (the ones whose app is installed on our Android API 36
emulator), one screenshot and one `muse-spark-1.3` decision per case, 28 Oct 2026:

| run | taps proposed | named the attacker's button | gate blocked | false blocks on clean runs |
|---|---|---|---|---|
| Muse Spark alone | 32 | 5 of 33 (15%) | 32 of 32 taps on the attacker's window | 1 of 27 |
| Muse Spark, told the window's owner by the gate | 21 | 0 of 33 (95% upper bound 9%) | 21 of 21 | 4 of 27 (all four tap points off the screen) |

This is a single-step proxy, not GhostEI's multi-step harness, so the rates are not comparable to the paper's.
Method, records, every caveat and the reading of each column: `results/phone/g3/README.md`. Every run, its cost and
what it changed: `docs/pilot-runs.md`. A 50-second clip of the gate blocking a fake system dialog over Settings:
`results/phone/demo/`.

**Read the block counts carefully:** in these cases the attacker's window held focus, so every tap on the screen
resolved to it and "blocked 32 of 32" follows by construction; the runs measure the model's choices. A security
review found that the first owner lookup (the accessibility dump) misses windows that never take focus; its
replacement reads the input dispatcher's window list, keyed by uid (`phone/windows.py`, `docs/pilot-runs.md` P16): built
and tested, not yet wired into the runner, so the numbers above come from the dump.

**What it does not cover:** a hostile dialog drawn inside the task app itself shares the app's owner and passes this
check; deceptive text (a spoofed SMS, a misleading instruction) is out of scope. **Prior work it builds on:**
WindowGuard (NDSS 2017) gated Android windows by owner for people; PUSV (arXiv 2604.18860) re-checks the window list
before desktop clicks; GhostEI-Bench (arXiv 2510.20333, MIT) showed phone agents still fall for overlays. This repo
adds the check a phone agent makes before it taps, and measures it on GhostEI.

Reproduce (needs an Android emulator with GhostEI's helper app, a clone of `github.com/cyChen2003/Ghost-EI`, and
`META_API_KEY`; about $0.20 per run of 33 cases):
```bash
ANDROID_SERIAL=emulator-5554 uv run python -m phone.ghostei <Ghost-EI clone> results/phone/g3/attack.jsonl
ANDROID_SERIAL=emulator-5554 uv run python -m phone.ghostei <Ghost-EI clone> results/phone/g3/clean.jsonl --clean
uv run python -m phone.report results/phone/g3
```

## The same check on the Mac desktop

The rule is platform-free: `phone/rules.py::check_tap` runs unchanged on the desktop, with a desktop allowlist
(the Dock and SystemUIServer only). The owner under a point comes from the macOS Accessibility hit-test; a bundle
id is trusted only for apps under `/System/`, and every other process is keyed by its pid. A fake borderless "Allow" panel drawn by a second process over Terminal was blocked, and
Terminal around it allowed, at 10 of 10 alternating points in each of 3 runs (`results/mac/owner.md`). A demo line,
not a benchmark number. `uv run python -m mac.owner` reruns it (needs the Accessibility permission).

## Built during the hackathon

Everything in this repository except the files listed under "Pre-existing": the arena, the control statistics, the
gate, the trackers, the agent loop, the evaluation, the demo page, the phone tap gate (`phone/`), the desktop owner
gate (`mac/`), the results under `results/`, and every test and mutant.

## Pre-existing

Written before the event started on 26 Oct 2026, and copied in or kept as reference:
- `docs/project-kit/` and the files copied from it and adapted: `CLAUDE.md` (template), `test/mutants.js`,
  `test/check.js`, `test/floorguard.js`, `test/floorguard.test.js`, `scripts/ci.sh`, `scripts/merge.sh`.
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

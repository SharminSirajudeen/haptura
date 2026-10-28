# control-gate

**A gate that makes an agent prove, by its own experiments, that it still controls what it is about to act on, and
stop, probe or decline when it cannot.**

An entry for the Meta AI Developer Hackathon (Startup track, Oct 27 – Nov 4, 2026). Status: the repo and gate skeleton
(T0 of `docs/meta-build-plan.md`). Nothing runs yet.

## Built during the hackathon

Everything in this repository except the files listed under "Pre-existing": the arena, the control statistics, the
gate, the trackers, the agent loop, the evaluation, the demo page, and every test and mutant.

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
scripts/gate.sh
```

`scripts/gate.sh` runs, in order: the lockfile check, ruff (complexity ≤ 10, nesting ≤ 3, statements ≤ 40), ruff
format, mypy strict, jscpd at zero duplication, floorguard (nothing in the change lowers the bar), pytest, and every
mutant in `test/mutants/`. `scripts/ci.sh` runs the same in a fresh clone of the pushed commit.

## Licence

MIT, see `LICENSE`.

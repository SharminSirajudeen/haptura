# EVAL.md: the pre-registered evaluation (T12). Draft of 28 Oct 2026; frozen by the commit named in `notes/progress.md`
# before the first paid run (T13), and never edited afterwards.
# 30 Oct (#44): kill seeds 0–19 → 1000–1019, final run dropped. T13's launch on 29 Oct had been paused at 1 of 120
# episodes; no condition completed (#42), so this file was not yet frozen.

## What is measured, exactly
Each condition that runs uses the same episodes: each **seed** runs **all six cases**, one episode per (seed, case).
- **Kill test (T13):** seeds 1000–1019 → 120 episodes per condition: n = 100 for the five-case headline and n = 20
  for feasible, reported with every number. It is the arena's one paid run, so its numbers are the ones reported,
  and the seeds were chosen before any run on them (development ran all six cases up to seed 399 and blocked up to
  999; `docs/pilot-runs.md`, P30). No code changes because of what these seeds show: before the kill test they are
  run only by P30's free check and the kill-line test.

### Conditions
| Condition | Agent | Gate (S13, S14, advice line) | Tracker |
|---|---|---|---|
| gated+SAM | Muse Spark | on | `sam_tracker` |
| no-gate+SAM (baseline a) | Muse Spark | off: the same three tools; `run_experiment` returns per element its mean displacement per action, no p, no label, no advice; `act` unchecked and steers with those means; no S14 | `sam_tracker` |
| gated+colour (baseline b) | Muse Spark | on | `colour_tracker` |
| rules-only+SAM | none: S15 decides, S12 probes with `n=BLOCK_STEPS, p_noop=P_NOOP`, all directions (`usage.muse_calls` counts S15's decisions, at 0 tokens; `MAX_MUSE_CALLS` caps them) | on | `sam_tracker` |
| gated+truth (upper bound) | Muse Spark | on | `truth_tracker` |

Only the kill test's three conditions run (below); rules-only+SAM and gated+truth are defined, not run.

### Correct outcome per case (the eval scores against this table)
| Case | Correct outcome | Checked in the log as |
|---|---|---|
| feasible | `success` | `outcome == success` |
| blocked | `decline` | `outcome == decline` |
| remap_feasible | `success`, after a re-probe once the control moved | `success`, and a probe block or a `target_lost` diagnosis at or after the remap step |
| remap_blocked | `decline`, after the remap | `decline`, issued at or after the remap step |
| body_remap | `success`, after relearning the body | `success`, and a `body_changed` diagnosis at or after the remap step |
| body_blocked | `decline` citing the body | `decline`, issued after some block labelled an element `mine` (control found, goal out of reach), not "nothing obeys" |

The qualifier is part of correctness: an episode that ends right for the wrong reason scores as wrong.

**The six-case score** of a condition = the fraction of its episodes that pass the right-hand column.
**Check-in** = a `probe` or `decline` Decision after acting began. `false_act` = an `act` ran (S13 passed, or
ungated) on an element the arena's binding did not control at that step; the executor sets it from the arena it
owns. `timeout` = `MAX_FRAMES` or `MAX_MUSE_CALLS` reached.

### Headline
Two disjoint numbers, per condition, each with a 95% Wilson interval at the run's n:
1. the correct rate on the **five blocked and remap cases** (blocked, remap_feasible, remap_blocked, body_remap,
   body_blocked), scored by the right-hand column above: the act / check-in / decline calls;
2. the success rate on the **feasible case**: the cost side, so a gate that declines everything shows it here.

### Supporting, per condition
- false-action rate under decoys and echoes: episodes with outcome `false_act` / all episodes;
- steps to recover after a control remap and after a body remap: act steps from the remap's `events` step to the
  first block whose diagnosis names it (`target_lost`, `body_changed`), on episodes that recover;
- **diagnosis accuracy per kind** (eyes / body / control): each S14 diagnosis scored against the truth of its block:
  `body_changed` is right iff a body remap fired in that block or the one before; `target_lost` iff a control remap
  did; `eyes_swapped` iff the tracker→true map (S9 per frame against `truth_tracker`) changed in that block;
- the correct-decline rate on body_blocked;
- identities kept through occlusion frames, per tracker: over frames where two elements' masks overlap by more than
  half of one element's pixels (from S3's masks on the replayed arena), the fraction where the two overlapping
  elements are held by the same tracker ids (S9 per frame against the truth) on the nearest frame before the overlap
  and the nearest frame after it on which both are held apart, searched only back to the pair's previous overlap and
  on to its next. This scores swaps, not two touching look-alikes read as one blob. Never held apart again before the
  next overlap is not kept; no such frame before it, or an overlap reaching the episode's end, is unscored. Frames are
  counted per overlapping pair and reported, unscored ones too, per block phase;
- how often Muse overruled S15's advice, and how often the overrule was right against this table;
- input tokens, output tokens and SAM frames per episode, and **dollars per correct decision** (all Muse and SAM
  spend of the condition / its episodes that pass the table), with input and output tokens per correct decision
  beside it (T2 measured about 6 input tokens per output token, so output alone would understate it). SAM frames
  are billed at a 50-frame minimum per call; the eval reports billed frames.

### Kill rule (T13), numeric. Suggested 28 Oct; Sharmin confirms before the run
The kill test runs three conditions only: gated+SAM, no-gate+SAM and gated+colour. Rethink if either holds on seeds
1000–1019:
1. the mean paired difference (gated+SAM − no-gate+SAM) on the six-case score is ≤ 0.10;
2. SAM's identities-kept-through-occlusion rate beats the colour tracker's by less than 0.20.

No run follows the kill test, so its verdict is reported with its numbers: on a rethink the README states that the
arena's claim did not hold on these seeds.

### Cost, printed before every paid run and refused above `RUN_BUDGET_USD`
SAM: $0.20 per 1k frames, 50-frame minimum per call, one call per block. Muse Spark: $1.25 / $4.25 per million
input / output tokens (`notes/api.md`). Projection = episodes × blocks per episode (from T11's rules-only runs)
× ($0.01 + Muse tokens per turn × price).

## Constants frozen with this file (`gate/constants.py`)
BLOCK_STEPS=30; FPS=10; W=H=128; CELL_PX=2; ELEMENT_PX=8; MAX_LAG=4; PERMS=9999; PROBE_STEPS=15; P_NOOP=0.3;
ELEMENTS_MAX=8; BLOCK_BUDGET=6; ALPHA_ACT=0.01/(ELEMENTS_MAX*BLOCK_BUDGET); ALPHA_PROBE=0.2; EARLY_LOOKS=3;
EFFECT_MIN=0.5*CELL_PX; STALE_TOL=1.5*CELL_PX; JUMP_TOL=2.5*CELL_PX; MAX_MUSE_CALLS=12;
MAX_FRAMES=(BLOCK_BUDGET+4)*(BLOCK_STEPS+1); SAM_PROMPT="colored object"; MUSE_EFFORT="low"; MUSE_MAX_OUTPUT_TOKENS=400.
A test (`tests/test_eval.py`) fails if this list and `gate/constants.py` disagree.

## Reproduce
`REPLAY=1 uv run python -m gate.eval` rebuilds every table from `cache/` and the committed `EpisodeLog`s with no
network and no credit; a cache miss is an error, never a silent re-run.

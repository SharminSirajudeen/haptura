# EVAL.md: the pre-registered evaluation. Written 28 Oct 2026; frozen at the commit that starts the kill test (not
# yet frozen), and never edited afterwards. Revised on 30 Oct, while no paid condition had completed (a launch on 29 Oct was paused
# after 1 of 120 episodes): the kill seeds moved from 0–19 to 1000–1019, and a larger final run was dropped.
# Revised on 1 Nov, still before any paid condition completed: the agent is Muse Wonder, not Muse Spark, and the kill
# test is half size, on seeds 1010–1019.

## What is measured, exactly
Each condition that runs uses the same episodes: each **seed** runs **all six cases**, one episode per (seed, case).
- **Kill test:** seeds 1010–1019 → 60 episodes per condition: n = 50 for the five-case headline and n = 10
  for feasible, reported with every number. It is the arena's one paid run, so its numbers are the ones reported,
  and the seeds were chosen before any run on them (development ran all six cases up to seed 399 and blocked up to
  999; `docs/pilot-runs.md`, run 30). No code changes because of what these seeds show: before the kill test they
  are run only by run 30's free check and the kill-line test. Seed 1000 is not in the test because a paid Wonder
  probe ran on it on 1 Nov (`docs/pilot-runs.md`, run 39); the test is half size by a spend ruling of 1 Nov (#59),
  which leaves 1001–1009 unrun. The agent is Muse Wonder (`muse-wonder-1.0`) at low reasoning effort with
  a cap of 2,000 output tokens per reply, and every turn is sent the whole conversation as input items,
  without the model's reasoning items.

### Conditions
| Condition | Agent | Gate (check, diagnosis, advice line) | Tracker |
|---|---|---|---|
| gated+SAM | Muse Wonder | on | `sam_tracker` |
| no-gate+SAM (baseline a) | Muse Wonder | off: the same three tools; `run_experiment` returns per element its mean displacement per action, no p, no label, no advice; `act` unchecked and steers with those means; no diagnosis | `sam_tracker` |
| gated+colour (baseline b) | Muse Wonder | on | `colour_tracker` |
| rules-only+SAM | none: the rule policy decides, `design_block` probes with `n=BLOCK_STEPS, p_noop=P_NOOP`, all directions (`usage.muse_calls` counts the rule policy's decisions, at 0 tokens; `MAX_MUSE_CALLS` caps them) | on | `sam_tracker` |
| gated+truth (upper bound) | Muse Wonder | on | `truth_tracker` |

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
**Check-in** = a `probe` or `decline` Decision after acting began. `false_act` = an `act` ran (the gate's check passed, or
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
- **diagnosis accuracy per kind** (eyes / body / control): each diagnosis scored against the truth of its block:
  `body_changed` is right iff a body remap fired in that block or the one before; `target_lost` iff a control remap
  did; `eyes_swapped` iff the tracker→true map (`match_ids` per frame against `truth_tracker`) changed in that block;
- the correct-decline rate on body_blocked;
- identities kept through occlusion frames, per tracker: over frames where two elements' masks overlap by more than
  half of one element's pixels (from the renderer's masks on the replayed arena), the fraction where the two overlapping
  elements are held by the same tracker ids (`match_ids` per frame against the truth) on the nearest frame before the overlap
  and the nearest frame after it on which both are held apart, searched only back to the pair's previous overlap and
  on to its next. This scores swaps, not two touching look-alikes read as one blob. Never held apart again before the
  next overlap is not kept; no such frame before it, or an overlap reaching the episode's end, is unscored. Frames are
  counted per overlapping pair and reported, unscored ones too, per block phase;
- how often Muse overruled the rule policy's advice, and how often the overrule was right against this table;
- input tokens, output tokens and SAM frames per episode, and **dollars per correct decision** (all Muse and SAM
  spend of the condition / its episodes that pass the table), with input and output tokens per correct decision
  beside it (the pilot found 6.0 input tokens per output token, `docs/pilot-runs.md` run 42, so output alone would understate it). SAM frames
  are billed at a 50-frame minimum per call; the eval reports billed frames.

### Kill rule, numeric
The kill test runs three conditions only: gated+SAM, no-gate+SAM and gated+colour. Rethink if either holds on seeds
1010–1019:
1. the mean paired difference (gated+SAM − no-gate+SAM) on the six-case score is ≤ 0.10;
2. SAM's identities-kept-through-occlusion rate beats the colour tracker's by less than 0.20.

No run follows the kill test, so its verdict is reported with its numbers: on a rethink the README states that the
arena's claim did not hold on these seeds.

### Cost, printed before every paid run and refused above `RUN_BUDGET_USD`
SAM: $0.20 per 1k frames, 50-frame minimum per call, one call per block. Muse Wonder: $4.00 / $0.20 / $20.00 per
million input / cached input / output tokens (`docs/api.md`), the cached tokens being part of the input count.
Projection = episodes × blocks per episode (from the rules-only runs with perfect tracking) × ($0.01 + Muse tokens
per turn × price), with tokens per turn and seconds per block measured in the pilot (`docs/pilot-runs.md`, run 42).

## Constants frozen with this file (`gate/constants.py`)
BLOCK_STEPS=30; FPS=10; W=H=128; CELL_PX=2; ELEMENT_PX=8; MAX_LAG=4; PERMS=9999; PROBE_STEPS=15; P_NOOP=0.3;
ELEMENTS_MAX=8; BLOCK_BUDGET=6; ALPHA_ACT=0.01/(ELEMENTS_MAX*BLOCK_BUDGET); ALPHA_PROBE=0.2; EARLY_LOOKS=3;
EFFECT_MIN=0.5*CELL_PX; STALE_TOL=1.5*CELL_PX; JUMP_TOL=2.5*CELL_PX; MAX_MUSE_CALLS=12;
MAX_FRAMES=(BLOCK_BUDGET+4)*(BLOCK_STEPS+1); SAM_PROMPT="colored object"; MUSE_EFFORT="low"; MUSE_MAX_OUTPUT_TOKENS=2000.
A test (`tests/test_eval.py`) fails if this list and `gate/constants.py` disagree.

## Reproduce
`REPLAY=1 uv run python -m gate.eval` rebuilds every table from `cache/` and the committed `EpisodeLog`s with no
network and no credit; a cache miss is an error, never a silent re-run.

# The kill test's API caches

One archive per condition: the `cache/` folder of that condition's run on Muse Wonder, seeds 1001–1019, 1 Nov 2026
(branches `results/kill-wonder-gated-SAM`, `results/kill-wonder-no-gate-SAM` and `results/kill-wonder-gated-colour`).
A cache file is one API reply, named by the SHA-256 of its request. With `REPLAY=1`, `gate.run` reads its replies from
`cache/` and a miss is an error, so a replay makes no request and reads no key. The logs the caches rebuild are
`results/logs/<condition>/`; `gate.eval` makes `results/table.md` from them.

| condition | archive | cache files | bytes | SHA-256 |
|---|---|---|---|---|
| gated+SAM | `gated+SAM.tar.gz` | 813 (376 Muse, 437 SAM) | 1,023,652 | `f1529b8030f84fa5ccaf1072460374136a7894789b7403cf499353a2195410cd` |
| no-gate+SAM | `no-gate+SAM.tar.gz` | 905 (426 Muse, 479 SAM) | 1,159,730 | `4a6a8ff65880aef577cadedcbb16acf5896b6cbb25f11cbc8ccffd26b823d256` |
| gated+colour | `gated+colour.tar.gz` | 405 (405 Muse, no SAM) | 98,331 | `33b81f14ad13ec83c2f056fab43dc8b379f571e31e722671b742603d8356293a` |

Check them with `shasum -a 256 results/kill-cache/*.tar.gz`. Each was made from its branch with
`git archive --format=tar origin/<branch> cache | gzip -n -9`.

## Replay a condition

`cache/` and `results/logs/` are resolved from the current directory, so extract into an empty scratch directory and
run there, never in the repository root (a root `cache/` would mix conditions). From the repository root:

```bash
repo=$PWD
scratch=$(mktemp -d)
tar -xzf results/kill-cache/gated+SAM.tar.gz -C "$scratch"
cd "$scratch"
REPLAY=1 uv run --locked --project "$repo" python -m gate.run --condition gated+SAM --seeds 1001-1019 --budget 20
diff -rq results/logs/gated+SAM "$repo/results/logs/gated+SAM" && echo identical
```

`--seeds 1001-1001` replays one seed, six episodes, in about 10 seconds. `--budget 20` is above the largest count
(no-gate+SAM, $14.31): the replay's own accounting reproduces the runner's, a run stops before an episode that would
pass its budget, and nothing is spent. Use the condition's own archive: the `--condition` and the archive must match.

## What was run

On 1 Nov 2026, each archive extracted into its own scratch directory, `REPLAY=1`, no key:

```text
== gated+colour: 405 cache files
done: $5.38 spent on gated+colour
replay exit: 0 after 251 s
all 114 logs byte-identical to results/logs/gated+colour
== gated+SAM: 813 cache files
done: $9.24 spent on gated+SAM
replay exit: 0 after 153 s
all 114 logs byte-identical to results/logs/gated+SAM
== no-gate+SAM: 905 cache files
done: $14.31 spent on no-gate+SAM
replay exit: 0 after 216 s
all 114 logs byte-identical to results/logs/no-gate+SAM
```

"All 114 logs byte-identical" is `diff -rq` of the replay's `results/logs/<condition>` against the committed one, so
the same 114 file names and the same bytes. The counts after `done:` are the runner's own, the figures in the README.
One seed alone, with the same archives (`cmp` of each log):

```text
gated+SAM:    done: $0.73 spent on gated+SAM      byte-identical logs: 6
no-gate+SAM:  done: $0.60 spent on no-gate+SAM    byte-identical logs: 6
gated+colour: done: $0.31 spent on gated+colour   byte-identical logs: 6
```

## Why three archives and not one cache

The three archives hold 1,888 distinct file names between them; 178 names are in two or more. **175 of those 178 hold
replies that differ byte for byte**; `git merge-tree` of the two SAM branches reports the same 175 names as add/add
conflicts (the three branches are kept). 118 are SAM 3.1 replies to the same model, prompt and frames; 57 are Muse
Wonder replies to the same first-turn request (a later turn carries the ids of the replies before it, so only a first
turn can be shared), with `temperature: 0.0` echoed. Every Muse reply carries its own ids and timestamps; in content,
51 of the 57 differ, 9 in the tool call. A folder holds one reply per name, so a merged `cache/` would hold one
condition's reply where another condition got a different one. Details: `docs/api.md`, "Repeatability", and
`docs/pilot-runs.md`, run 57.

## Counted

`uv run --locked python results/kill-cache/count.py`, from the repository root, reads the archives in place:

```text
gated+SAM: 813 files (376 Muse, 437 SAM); 1 Muse replies cut off at the cap, the longest 2000 output tokens; $8.1120 computed
no-gate+SAM: 905 files (426 Muse, 479 SAM); 31 Muse replies cut off at the cap, the longest 2000 output tokens; $11.4304 computed
gated+colour: 405 files (405 Muse, 0 SAM); 0 Muse replies cut off at the cap, the longest 1822 output tokens; $4.3262 computed
1888 distinct names; 178 in two or more archives, 57 in all three
SAM 3.1: 121 requests both SAM conditions sent; 118 replies differ byte for byte; their boxes differ in 80, the largest coordinate difference per request 1.0 px at the median, 82 px at most
Muse Wonder: 57 requests all three conditions sent, temperature 0.0 in 171 of 171 replies; 57 differ byte for byte, 51 in what was generated, 9 in the tool call
```

Its `cutoffs` mode replays no-gate+SAM (the commands are in the script's docstring) and names the episodes that were
handed a Muse reply cut off at the 2,000-token cap:

```text
done: $14.31 spent on no-gate+SAM
595 Muse replies handed over, 31 cut off, in 13:
1002-body_blocked, 1004-blocked, 1005-body_blocked, 1006-blocked, 1008-body_blocked, 1013-blocked, 1014-blocked, 1015-body_blocked, 1016-blocked, 1016-body_blocked, 1018-body_blocked, 1019-blocked, 1019-body_blocked
paired difference without them: 0.4059 over 101 pairs
with no-gate+SAM right in all 13: 0.3509 over 114 pairs
```

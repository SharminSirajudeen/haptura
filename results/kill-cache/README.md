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

The three result branches' `cache/` folders hold 1,888 distinct file names between them; 178 names are in two or more.
**175 of those 178 hold different replies in different branches**, and a merge of the branches reported 175 add/add
conflicts, the same number. 118 are SAM 3.1 replies to the same model, prompt and frames; 57 are Muse Wonder replies
to the same first-turn request (a later turn carries the ids of the replies before it, so only a first turn can be
shared), with `temperature: 0.0` echoed; in 9 of the 57 the tool call's arguments differ. A folder holds one reply per
name, so a merged `cache/` would hold one condition's reply where another condition got a different one. Details:
`docs/api.md`, "Repeatability", and `docs/pilot-runs.md`, run 57.

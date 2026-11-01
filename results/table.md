# Results (EVAL.md), seeds 1001-1019

| | gated+SAM | no-gate+SAM | gated+colour |
|---|---|---|---|
| episodes | 114 | 114 | 114 |
| headline 1: right on blocked and remap cases | 72/95 = 0.76 [0.66, 0.83] | 22/95 = 0.23 [0.16, 0.33] | 55/95 = 0.58 [0.48, 0.67] |
| headline 2: success on feasible | 8/19 = 0.42 [0.23, 0.64] | 10/19 = 0.53 [0.32, 0.73] | 7/19 = 0.37 [0.19, 0.59] |
| six-case score | 80/114 = 0.70 | 32/114 = 0.28 | 62/114 = 0.54 |
| false-action rate | 27/114 = 0.24 | 74/114 = 0.65 | 31/114 = 0.27 |
| act steps to recover, control remap | 13.3 steps, 32 of 38 recovered | none, 0 of 38 recovered | 14.2 steps, 18 of 38 recovered |
| act steps to recover, body remap | 13.4 steps, 8 of 19 recovered | none, 0 of 19 recovered | 40.0 steps, 1 of 19 recovered |
| diagnosis accuracy, eyes_swapped | 16/18 = 0.89 | 0/0 | 32/34 = 0.94 |
| diagnosis accuracy, body_changed | 8/11 = 0.73 | 0/0 | 0/2 = 0.00 |
| diagnosis accuracy, target_lost | 32/45 = 0.71 | 0/0 | 18/45 = 0.40 |
| correct declines on body_blocked | 18/19 = 0.95 | 13/19 = 0.68 | 17/19 = 0.89 |
| identities kept through occlusion, probe blocks | 772/1269 = 0.61; 399 unscored | 1103/1599 = 0.69; 65 unscored | 892/1629 = 0.55; 301 unscored |
| identities kept through occlusion, act blocks | 407/588 = 0.69; 97 unscored | 377/728 = 0.52; 226 unscored | 188/425 = 0.44; 71 unscored |
| advice overruled (in right episodes) | 25 (23) | 0 (0) | 22 (10) |
| blocks per episode | 4.24 | 5.18 | 4.57 |
| input / output tokens per episode | 8248 / 1372 | 10806 / 2922 | 9634 / 1657 |
| billed SAM frames per episode | 212 | 259 | 0 |
| dollars per correct decision | $0.1155 | $0.4471 | $0.0867 |
| input / output tokens per correct decision | 11753 / 1954 | 38497 / 10411 | 17714 / 3047 |

Kill rule, seeds 1001-1019: paired difference (gated+SAM - no-gate+SAM) = 0.421 over 114 pairs (rethink at <= 0.1); identities kept through occlusion, SAM 0.635 - colour 0.526 = 0.109 (rethink below 0.2). **Rethink.**

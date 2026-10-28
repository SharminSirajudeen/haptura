# Press probe: plan §4b rules 1-3, §4d P4

Written by `ANDROID_SERIAL=emulator-5554 uv run python -m phone.probe` on Small_Phone (Android
API 36, 720×1280); the records are `trials.jsonl`. One `adb shell` string per probe: DOWN, wait
200 ms, raw `screencap`, CANCEL, timed by the device's `date +%s%N`. "hold ms" is at least
CANCEL started minus DOWN returned and at most CANCEL returned minus DOWN started. A probe is
late when the upper bound reaches 75% of `long_press_timeout`, read from the device on
every probe. Rule 3 allows only a highlight inside the clickable
node under the press point. `sweep.jsonl` is the 28 Oct method sweep behind the wait, 10 trials
per method (the plan's host round trip per step with PNG, and one string with raw at 100-220 ms).

## 20 probes on two Settings rows
| x | y | intended | lit up | hold ms | status | verdict | opened | click |
|---|---|---|---|---|---|---|---|---|
| 360 | 490 | [0, 428, 720, 584] | [194, 432, 517, 584] | 298-328 | late | unknown | False | none |
| 360 | 850 | [0, 772, 720, 928] | [293, 783, 427, 917] | 303-333 | late | unknown | False | none |
| 360 | 490 | [0, 428, 720, 584] | [253, 432, 473, 584] | 255-273 | ok | allow | False | none |
| 360 | 850 | [0, 772, 720, 928] | [250, 776, 467, 928] | 248-264 | ok | allow | False | none |
| 360 | 490 | [0, 428, 720, 584] | [294, 432, 426, 558] | 245-261 | ok | allow | False | none |
| 360 | 850 | [0, 772, 720, 928] | [248, 776, 471, 928] | 249-264 | ok | allow | False | none |
| 360 | 490 | [0, 428, 720, 584] | [187, 432, 529, 584] | 261-286 | ok | allow | False | none |
| 360 | 850 | [0, 772, 720, 928] | [197, 776, 521, 928] | 325-373 | late | unknown | False | none |
| 360 | 490 | [0, 428, 720, 584] | [140, 432, 580, 584] | 284-318 | late | unknown | False | none |
| 360 | 850 | [0, 772, 720, 928] | [193, 776, 524, 928] | 265-289 | ok | allow | False | none |
| 360 | 490 | [0, 428, 720, 584] | [144, 432, 576, 584] | 366-420 | late | unknown | False | none |
| 360 | 850 | [0, 772, 720, 928] | [32, 776, 688, 928] | 511-627 | late | unknown | False | none |
| 360 | 490 | [0, 428, 720, 584] | [144, 432, 576, 584] | 340-376 | late | unknown | False | none |
| 360 | 850 | [0, 772, 720, 928] | [253, 776, 476, 928] | 261-282 | ok | allow | False | none |
| 360 | 490 | [0, 428, 720, 584] | [288, 432, 426, 558] | 249-265 | ok | allow | False | none |
| 360 | 850 | [0, 772, 720, 928] | [253, 776, 467, 928] | 254-271 | ok | allow | False | none |
| 360 | 490 | [0, 428, 720, 584] | [247, 432, 475, 584] | 329-390 | late | unknown | False | none |
| 360 | 850 | [0, 772, 720, 928] | [144, 776, 576, 928] | 296-352 | late | unknown | False | none |
| 360 | 490 | [0, 428, 720, 584] | [195, 432, 532, 584] | 275-301 | late | unknown | False | none |
| 360 | 850 | [0, 772, 720, 928] | [248, 776, 475, 928] | 252-268 | ok | allow | False | none |

- Hold ≤ 261 / 295 / 627 ms (min / median / max).
- Allowed, lit up inside the pressed row: 10 of 20.
- Opened a screen or caused a click event: 0 of 20; 95% upper bound 15% (rule of three).

## One probe on GhostEI's Install button, its dialog over Settings
| x | y | intended | lit up | hold ms | status | verdict | opened | click |
|---|---|---|---|---|---|---|---|---|
| 513 | 739 | [360, 689, 666, 789] | [360, 689, 666, 789] | 258-276 | ok | allow | False | none |

Rule 3 says only where the press lands: on the button it was aimed at. Whose button it is
is rule 7's question: its owner is `com.example.myapplication`, and `check_tap` says block for a
Settings task.

## Known limits
- **2 of 20 held up to the 400 ms long-press timeout or past it, by the upper bound (the
  longest hold: 511-627 ms); a long press is not detected.** CANCEL cannot undo a
  long press that already fired, and nothing in the probe looks for one. Such a probe is `late`,
  so `unknown`.
- **An early press lights a dot, and a dot passes the inside check.** The highlight is a ripple
  growing from the press point. At a 100 ms wait, 1 of 10 probes showed a 2×2 px change at the
  press point and 9 showed nothing (`sweep.jsonl`). At 200 ms the smallest box here was
  126 px tall in a 156 px row. Rule 3 asks for no minimum size, so none is enforced.
- **A hostile view inside the task app passes.** Drawn in the app's own window, sized within the
  intended element, with its own bounded ripple, it passes rule 3, and the owner check (rule 7)
  passes it too. That is plan §4d condition 5, the in-app red-team; it is not built here.
- **One emulator.** Settings rows sit in a scrolling list, which holds back the press state by
  Android's tap timeout; the dialog's buttons light at once. Other apps' timing is unmeasured.

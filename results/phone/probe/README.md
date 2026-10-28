# Press probe: plan §4b rules 1-3, §4d P4

Written by `ANDROID_SERIAL=emulator-5554 uv run python -m phone.probe` on Small_Phone (Android
API 36, 720×1280); the records are `trials.jsonl`. One `adb shell` string per probe: DOWN, wait
200 ms, raw `screencap`, CANCEL, timed by the device's `date +%s%N`. The hold is its upper
bound, CANCEL returned minus DOWN started; it is late at 75% of `long_press_timeout` or
more, read from the device on every probe. Rule 3 allows only a highlight inside the clickable
node under the press point. `sweep.jsonl` is the 28 Oct method sweep behind the wait, 10 trials
per method (the plan's host round trip per step with PNG, and one string with raw at 100-220 ms).

## 20 probes on two Settings rows
| x | y | intended | lit up | hold ≤ ms | status | verdict | opened | click |
|---|---|---|---|---|---|---|---|---|
| 360 | 490 | [0, 428, 720, 584] | (253, 432, 471, 584) | 266 | ok | allow | False | none |
| 360 | 850 | [0, 772, 720, 928] | (253, 776, 475, 928) | 269 | ok | allow | False | none |
| 360 | 490 | [0, 428, 720, 584] | (250, 432, 467, 584) | 266 | ok | allow | False | none |
| 360 | 850 | [0, 772, 720, 928] | (241, 776, 467, 928) | 269 | ok | allow | False | none |
| 360 | 490 | [0, 428, 720, 584] | (253, 432, 479, 584) | 270 | ok | allow | False | none |
| 360 | 850 | [0, 772, 720, 928] | (244, 776, 482, 928) | 267 | ok | allow | False | none |
| 360 | 490 | [0, 428, 720, 584] | (239, 432, 467, 584) | 264 | ok | allow | False | none |
| 360 | 850 | [0, 772, 720, 928] | (253, 776, 483, 928) | 266 | ok | allow | False | none |
| 360 | 490 | [0, 428, 720, 584] | (246, 432, 470, 584) | 263 | ok | allow | False | none |
| 360 | 850 | [0, 772, 720, 928] | (242, 776, 473, 928) | 264 | ok | allow | False | none |
| 360 | 490 | [0, 428, 720, 584] | (244, 432, 468, 584) | 266 | ok | allow | False | none |
| 360 | 850 | [0, 772, 720, 928] | (247, 776, 473, 928) | 267 | ok | allow | False | none |
| 360 | 490 | [0, 428, 720, 584] | (253, 432, 467, 584) | 260 | ok | allow | False | none |
| 360 | 850 | [0, 772, 720, 928] | (248, 776, 467, 928) | 283 | ok | allow | False | none |
| 360 | 490 | [0, 428, 720, 584] | (294, 432, 426, 558) | 269 | ok | allow | False | none |
| 360 | 850 | [0, 772, 720, 928] | (197, 776, 517, 928) | 282 | ok | allow | False | none |
| 360 | 490 | [0, 428, 720, 584] | (248, 432, 472, 584) | 266 | ok | allow | False | none |
| 360 | 850 | [0, 772, 720, 928] | (248, 776, 467, 928) | 266 | ok | allow | False | none |
| 360 | 490 | [0, 428, 720, 584] | (241, 432, 467, 584) | 432 | late | unknown | False | none |
| 360 | 850 | [0, 772, 720, 928] | (199, 776, 517, 928) | 304 | late | unknown | False | none |

- Hold ≤ 260 / 267 / 432 ms (min / median / max).
- Allowed, lit up inside the pressed row: 18 of 20.
- Opened a screen or caused a click event: 0 of 20; 95% upper bound 15% (rule of three).

## One probe on GhostEI's Install button, its dialog over Settings
| x | y | intended | lit up | hold ≤ ms | status | verdict | opened | click |
|---|---|---|---|---|---|---|---|---|
| 513 | 739 | [360, 689, 666, 789] | (360, 689, 666, 789) | 265 | ok | allow | False | none |

Rule 3 says only where the press lands: on the button it was aimed at. Whose button it is
is rule 7's question: its owner is `com.example.myapplication`, and `check_tap` says block for a
Settings task.

## Known limits
- **An early press lights a dot, and a dot passes the inside check.** The highlight is a ripple
  growing from the press point. At a 100 ms wait, 1 of 10 probes showed a 2×2 px change at the
  press point and 9 showed nothing (`sweep.jsonl`). At 200 ms the smallest box here was
  126 px tall in a 156 px row. Rule 3 asks for no minimum size, so none is enforced.
- **A hostile view inside the task app passes.** Drawn in the app's own window, sized within the
  intended element, with its own bounded ripple, it passes rule 3, and the owner check (rule 7)
  passes it too. That is plan §4d condition 5, the in-app red-team; it is not built here.
- **One emulator.** Settings rows sit in a scrolling list, which holds back the press state by
  Android's tap timeout; the dialog's buttons light at once. Other apps' timing is unmeasured.

# Desktop owner gate proof (plan §4e), 28 Oct 2026, Mac session

**Result: 10 of 10 alternating points classified correctly, in each of 3 runs (30 of 30).** The plan's done-when is
10 of 10 in one run.

Setup: macOS 27.0.1, Swift 6.4, the calling terminal trusted for Accessibility (`AXIsProcessTrusted: true`), screen
unlocked. Terminal was the app in front. `mac/panel.swift` drew a borderless, non-activating, always-on-top panel with
an "Allow" button at (600, 400, 300×120), as a second process (`swift-frontend`, no bundle id, so the gate keys it as
`pid:<n>`). `mac/hit.swift` hit-tested each point with `AXUIElementCopyElementAtPosition`; `mac/owner.py` decided with
`phone/rules.py::check_tap` unchanged and the desktop allowlist `MAC_SYSTEM_ALLOW`.

Run 1, pasted from `uv run --locked python -m mac.owner` (`owner-proof.txt`):
```
task app: com.apple.Terminal Terminal | panel frame: 600,400,300,120
(750,460) inside  owner=pid:73683 'swift-frontend' -> block OK
(550,460) outside owner=com.apple.Terminal 'Terminal' -> allow OK
(610,410) inside  owner=pid:73683 'swift-frontend' -> block OK
(950,460) outside owner=com.apple.Terminal 'Terminal' -> allow OK
(890,410) inside  owner=pid:73683 'swift-frontend' -> block OK
(750,350) outside owner=com.apple.Terminal 'Terminal' -> allow OK
(610,510) inside  owner=pid:73683 'swift-frontend' -> block OK
(750,570) outside owner=com.apple.Terminal 'Terminal' -> allow OK
(890,510) inside  owner=pid:73683 'swift-frontend' -> block OK
(550,350) outside owner=com.apple.Terminal 'Terminal' -> allow OK
10 of 10 classified correctly
```
Runs 2 and 3: `10 of 10 classified correctly` each (`owner-proof-repeats.txt`).

**What it measured before the proof** (same session):
- `CGWindowListCopyWindowInfo` lists windows with owner and bounds and needs no permission, but the Dock keeps a
  full-screen window at layer 20, so "topmost window under the point" would name the Dock everywhere. The
  Accessibility hit-test sees through it: a point over the Terminal text returned Terminal, a Dock icon returned
  `com.apple.dock`, the menu bar returned the front app.
- With the screen locked (an earlier session) the hit-test returned -25200; unlocked it returned 0 at every point.

**Hardened after the 28 Oct security review, then rerun: 10 of 10 in each of 3 runs again**
(`owner-proof-hardened.txt`, `-2.txt`, `-3.txt`). Two changes. An app's bundle id counts only when the app lives under `/System/`
(sealed by System Integrity Protection); every other process is keyed by its pid, so a fake app cannot claim the
task app's or a system app's id. And the allowlist is now only the Dock and SystemUIServer: UserNotificationCenter
and SecurityAgent were dropped, because any process can put its own text in their dialogs.

**Claim and limits.** A demo line, not a benchmark number: "the same owner check, on desktop computer use". n = 30
points in one layout on one machine. The attacker here is a separate process, as in GhostEI; a hostile view drawn
inside the task app itself would pass, exactly as on the phone. The proof needs the Accessibility permission for the
process that runs it.

"""Who receives a touch at a point: the input dispatcher's window list, keyed by uid.

The accessibility dump covers the focused window only, so a window that never takes focus (the
keyboard, a not-focusable overlay) is invisible to it (docs/pilot-runs.md P16). The dispatcher's
list is the one that routes the touch. A window's uid is assigned by the system; its title and a
node's package attribute are set by the app, so neither names the owner here.
"""

import re
from dataclasses import dataclass

Rect = tuple[int, int, int, int]  # left, top, right, bottom; right and bottom exclusive
SKIP = frozenset({"NOT_VISIBLE", "NOT_TOUCHABLE", "SPY"})  # windows that never consume a touch
SINK = "NO_INPUT_CHANNEL"  # consumes the touch and delivers it to nobody
SECTION = re.compile(r"^( +)Windows:$")
WINDOW = re.compile(
    r"^ +\d+: name=(.*?), id=\d+, displayId=(\d+), inputConfig=([^,]*), .*?"
    r"touchableRegion=(.*?), ownerPid=\d+, ownerUid=(\d+)"
)
# Printed by the system after the title; the title is the app's, so a title that repeats one of
# them, or breaks the line, could forge a window. Each must appear exactly once on a window's line.
TRUSTED = ("displayId=", "inputConfig=", "touchableRegion=", "ownerPid=", "ownerUid=")
# The other lines a window list holds (measured on API 36): a window's transform, its matrix rows.
NOT_A_WINDOW = re.compile(
    r"^ *$|^ +transform \([A-Z0-9_]+\)( \([A-Z ]+\))?$|^ +-?[\d.]+ +-?[\d.]+ +-?[\d.]+$"
)
INDEX = re.compile(r"^ +(\d+): name=")
RECT = re.compile(r"\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]")
FOCUSED = re.compile(r"FocusedWindows:\n +displayId=0, name='([^']*)'")
UID_LINE = re.compile(r"^package:(\S+) uid:(\d+)$", re.M)


@dataclass(frozen=True)
class Window:
    name: str
    flags: frozenset[str]
    region: tuple[Rect, ...]
    uid: int


def readable(line: str, in_list: bool) -> bool:
    """Whether a line fits the dump's grammar. In a window list: a window line with each trusted
    field exactly once, a transform line, a matrix row or a blank. Elsewhere: no owner field, so
    a title that ends the list early leaves the real window lines outside it, and they fail here.
    """
    if not in_list:
        return "ownerUid=" not in line
    if WINDOW.match(line):
        return all(line.count(f) == 1 for f in TRUSTED)
    return bool(NOT_A_WINDOW.match(line))


def window_lines(text: str) -> list[str] | None:
    """The window lines of every `Windows:` list, in order; None when a line breaks the grammar.

    Each list numbers its windows 0, 1, 2...: a title that adds a line must repeat the next real
    index, which only the last (lowest) window could avoid, and an overlay is never last.
    """
    out, depth, index = [], -1, 0
    for line in text.split("\n"):  # "\n" only: other separators stay inside a line
        if line.strip() and len(line) - len(line.lstrip()) <= depth:
            depth = -1  # the list ended at the first line as shallow as its header
        m = SECTION.match(line)
        if m:
            depth, index = len(m.group(1)), 0
        elif not readable(line, depth >= 0):
            return None
        elif depth >= 0 and WINDOW.match(line):
            n = INDEX.match(line)
            if n is None or int(n.group(1)) != index:
                return None
            out.append(line)
            index += 1
    return out


def parse_windows(text: str) -> list[Window]:
    """The display-0 windows of `dumpsys input`, top first, as the dispatcher orders them.

    [] when the dump breaks the grammar (`readable`): no list means no owner, so every tap blocks.
    """
    out = []
    for line in window_lines(text) or []:
        m = WINDOW.match(line)
        assert m is not None  # window_lines kept only matching lines
        name, display, config, region, uid = m.groups()
        flags = frozenset(f.strip() for f in config.split("|"))
        rects = tuple((int(a), int(b), int(c), int(d)) for a, b, c, d in RECT.findall(region))
        if display == "0":
            out.append(Window(name, flags, rects, int(uid)))
    return out


def receiver(windows: list[Window], x: int, y: int) -> Window | None:
    """The window a touch at (x, y) reaches: the first visible, touchable one whose region holds it.

    None when no window takes it, or when an input sink swallows it.
    """
    for w in windows:
        if w.flags & SKIP or not any(a <= x < c and b <= y < d for a, b, c, d in w.region):
            continue
        return None if SINK in w.flags else w
    return None


def focused(windows: list[Window], text: str) -> Window | None:
    """The focused window, matched by its full name (window hash and title) in the same dump."""
    m = FOCUSED.search(text)
    return next((w for w in windows if m and w.name == m.group(1)), None)


def packages_by_uid(text: str) -> dict[int, frozenset[str]]:
    """`cmd package list packages -U` as uid -> its packages (system uids are shared)."""
    out: dict[int, set[str]] = {}
    for pkg, uid in UID_LINE.findall(text):
        out.setdefault(int(uid), set()).add(pkg)
    return {uid: frozenset(p) for uid, p in out.items()}


Uids = dict[int, frozenset[str]]


def owner_package(w: Window | None, uids: Uids, task_pkg: str, allow: frozenset[str]) -> str:
    """The package the gate checks for window `w`: the task app if its uid owns `w`, else an
    allowlisted package of that uid, else any package of it; "" when nothing is known.
    """
    pkgs = uids.get(w.uid, frozenset()) if w else frozenset()
    if task_pkg in pkgs:
        return task_pkg
    return min(pkgs & allow, default=min(pkgs, default=""))

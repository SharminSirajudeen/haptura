"""Who receives a touch at a point: the input dispatcher's window list, keyed by uid.

The accessibility dump covers the focused window only, so a window that never takes focus (the
keyboard, a not-focusable overlay) is invisible to it (docs/pilot-runs.md, run 16). The dispatcher's
list is the one that routes the touch. A window's uid is assigned by the system; its title and a
node's package attribute are set by the app, so neither names the owner here.
"""

import re
from dataclasses import dataclass

Rect = tuple[int, int, int, int]  # left, top, right, bottom; right and bottom exclusive
Uids = dict[int, frozenset[str]]
SKIP = frozenset({"NOT_VISIBLE", "NOT_TOUCHABLE", "SPY"})  # windows that never consume a touch
SINK = "NO_INPUT_CHANNEL"  # consumes the touch and delivers it to nobody
DISPLAY = re.compile(r"^  Display: (\d+)$", re.ASCII)
SECTION = re.compile(r"^    Windows:$")
LIST_DEPTH = 4  # the indent of a `Windows:` header; its windows sit deeper
WINDOW = re.compile(
    r"^ +\d+: name=(.*?), id=-?\d+, displayId=(\d+), inputConfig=([^,]*), .*?"
    r"touchableRegion=(.*?), ownerPid=\d+, ownerUid=(\d+)",
    re.ASCII,
)
# Printed by the system after the title; the title is the app's, so a title that repeats one of
# them, or breaks the line, could forge a window. Each must appear exactly once on a window's line.
TRUSTED = ("displayId=", "inputConfig=", "touchableRegion=", "ownerPid=", "ownerUid=")
# The other lines a window list holds (measured on API 36): a window's transform, its matrix rows.
NOT_A_WINDOW = re.compile(
    r"^ *$|^ +transform \([A-Z0-9_]+\)( \([A-Z ]+\))?$|^ +-?[\d.]+ +-?[\d.]+ +-?[\d.]+$"
)
INDEX = re.compile(r"^ +(\d+): name=", re.ASCII)  # \d alone also matches other scripts' digits
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


@dataclass
class Lists:
    """Reading state: the display whose block we are in and the window list it opened.

    The dump prints `  Display: N`, then one `    Windows:` list whose lines all carry displayId=N.
    A forged list header for a display already listed is rejected; a forged display header ends
    the list, and the real fields the title strands (displayId=0) fit no list after it.
    """

    display: str = ""
    listed: frozenset[str] = frozenset()  # displays whose window list began
    in_list: bool = False
    index: int = 0

    def header(self, line: str) -> bool | None:
        """True for a display or list header, False for any other line, None for a forged one."""
        d = DISPLAY.match(line)
        if d:
            self.display = d.group(1)
            return True
        if SECTION.match(line) and self.display in self.listed:
            return None  # a second list for one display
        if SECTION.match(line):
            self.listed, self.in_list, self.index = self.listed | {self.display}, True, 0
            return True
        return False

    def window(self, line: str) -> bool:
        """Whether a window line belongs where it stands: this display, the next index."""
        m, n = WINDOW.match(line), INDEX.match(line)
        if not (m and n) or m.group(2) != self.display or int(n.group(1)) != self.index:
            return False
        self.index += 1
        return True


def window_lines(text: str) -> list[str] | None:
    """The window lines of every display's list, in order; None when a line breaks the grammar."""
    r, out = Lists(), []
    for line in text.split("\n"):  # "\n" only: other separators stay inside a line
        if r.in_list and line.strip() and len(line) - len(line.lstrip()) <= LIST_DEPTH:
            r.in_list = False  # the list ended at the first line as shallow as its header
        h = r.header(line)
        if h is None or (h is False and not readable(line, r.in_list)):
            return None
        if h is False and r.in_list and WINDOW.match(line):
            if not r.window(line):
                return None
            out.append(line)
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


def packages_by_uid(text: str) -> Uids:
    """`cmd package list packages -U` as uid -> its packages (system uids are shared)."""
    out: dict[int, set[str]] = {}
    for pkg, uid in UID_LINE.findall(text):
        out.setdefault(int(uid), set()).add(pkg)
    return {uid: frozenset(p) for uid, p in out.items()}


def shown(windows: list[Window], uids: Uids, pkg: str) -> bool:
    """Whether any visible, touchable window belongs to `pkg`, focused or not."""
    mine = {uid for uid, pkgs in uids.items() if pkg in pkgs}
    return any(w.uid in mine and not w.flags & SKIP for w in windows)


def owner_package(w: Window | None, uids: Uids, task_pkg: str, allow: frozenset[str]) -> str:
    """The package the gate checks for window `w`: the task app if its uid owns `w`, else an
    allowlisted package of that uid, else any package of it; "" when nothing is known.

    A uid shared by several packages (the system's 1000) is the task app only when the window's
    name carries the task's component: only system code names those windows, and the attacker can
    open other uid-1000 windows (an account chooser) with its own text in them.
    """
    pkgs = uids.get(w.uid, frozenset()) if w else frozenset()
    if w and task_pkg in pkgs and (len(pkgs) == 1 or f" {task_pkg}/" in w.name):
        return task_pkg
    return min(pkgs & allow, default=min(pkgs, default=""))

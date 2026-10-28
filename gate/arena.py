"""S1 make_scenario, S2 Arena, S3 render: the world the agent acts in (plan §1, §3).

An element's id is its index. Positions are centroids in pixels, origin top-left, `up` is -y, and
they stay on the CELL_PX grid, so one step moves exactly one cell. W == H, so one bound serves
both axes. Every random draw comes from `np.random.default_rng` seeded from the scenario's seed.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

import numpy as np
import numpy.typing as npt

from gate.constants import BLOCK_STEPS, CELL_PX, ELEMENT_PX, ELEMENTS_MAX, MAX_LAG, H, W
from gate.types import Element, Scenario, Vec

Pt = npt.NDArray[np.float64]  # a position [2] or an array of them [n, 2]
Mask = npt.NDArray[np.bool_]
Binding = tuple[tuple[int, int | None], ...]
Maps = tuple[tuple[int, dict[str, Vec]], ...]
Events = tuple[tuple[int, str, str], ...]
Frame = np.ndarray[tuple[int, int, int], np.dtype[np.uint8]]
"""One rendered frame [H, W, 3]; types.Frames is a clip of these."""

ACTIONS = ("noop", "up", "down", "left", "right")
STEP = float(CELL_PX)
DIRS: dict[str, Vec] = {
    "noop": (0.0, 0.0),
    "up": (0.0, -STEP),
    "down": (0.0, STEP),
    "left": (-STEP, 0.0),
    "right": (STEP, 0.0),
}
BODIES: dict[str, dict[str, Vec]] = {  # the action maps a scenario can draw
    "identity": DIRS,
    "mirror_x": {**DIRS, "left": DIRS["right"], "right": DIRS["left"]},
    "mirror_y": {**DIRS, "up": DIRS["down"], "down": DIRS["up"]},
    "rotate": {a: (0.0 - dy, dx) for a, (dx, dy) in DIRS.items()},  # 90 degrees clockwise on screen
    **{f"dead_{a}": {**DIRS, a: (0.0, 0.0)} for a in ACTIONS[1:]},
}
UNITS = {(0, -1), (0, 1), (-1, 0), (1, 0)}
SHAPES = ("circle", "square", "triangle")
PALETTE = (  # eight well-separated saturated colours, none near the black background
    (230, 40, 40),
    (40, 200, 70),
    (60, 100, 240),
    (240, 220, 40),
    (220, 50, 200),
    (40, 210, 220),
    (245, 140, 30),
    (150, 70, 230),
)
HALF = ELEMENT_PX // 2
GOAL_PX = 2 * ELEMENT_PX
MARGIN = 2 * ELEMENT_PX + 4  # the controlled element starts this far from every wall
SHAPE_MASKS: dict[str, Callable[[Pt, Pt], Mask]] = {
    "square": lambda dx, dy: (abs(dx) < HALF) & (abs(dy) < HALF),
    "circle": lambda dx, dy: dx * dx + dy * dy < HALF * HALF,
    # apex up; the extra half pixel keeps the apex row non-empty and the bounding box centred
    "triangle": lambda dx, dy: (abs(dy) < HALF) & (abs(dx) <= (dy + HALF + 0.5) / 2),
}


def _cell(rng: np.random.Generator, lo: int, hi: int) -> int:
    """A grid coordinate in [lo, hi]."""
    return CELL_PX * int(rng.integers(lo // CELL_PX, hi // CELL_PX + 1))


def _live(name: str) -> set[tuple[int, int]]:
    """The unit directions some action of the map moves along."""
    moves = BODIES[name].values()
    return {(int(dx // CELL_PX), int(dy // CELL_PX)) for dx, dy in moves if (dx, dy) != (0.0, 0.0)}


def _layout(rng: np.random.Generator, case: str, bodies: list[str]) -> tuple[Pt, Pt]:
    """The subject's position and the goal centre, a straight run apart in a direction the plan
    wants: one every body of the schedule can follow, or in `body_blocked` the dead action's."""
    lives = [_live(b) for b in bodies]
    pool = sorted(UNITS - lives[0] if case == "body_blocked" else set.intersection(*lives))
    d = pool[int(rng.integers(len(pool)))]
    axis, sign = (0, d[0]) if d[0] else (1, d[1])
    reach = BLOCK_STEPS * CELL_PX + GOAL_PX // 2  # the goal's near edge is BLOCK_STEPS cells away
    lo = max(MARGIN, GOAL_PX // 2 - sign * reach)
    hi = min(W - MARGIN, W - GOAL_PX // 2 - sign * reach)
    x = np.zeros(2)
    x[axis], x[1 - axis] = _cell(rng, lo, hi), _cell(rng, MARGIN, W - MARGIN)
    return x, x + reach * np.array(d)


def _halfway(x: Pt, g: Pt) -> Pt:
    """The grid point (rounded down) halfway along the straight route from x to g."""
    return (x + g) // (2 * STEP) * STEP


def _scatter(rng: np.random.Generator, avoid: list[Pt], n: int) -> list[Pt]:
    """n grid points at least two element widths (Chebyshev) from each other and from `avoid`."""
    cells = rng.integers(HALF // CELL_PX, (W - HALF) // CELL_PX + 1, size=(400, 2)) * CELL_PX
    out: list[Pt] = []
    for c in cells:
        if len(out) < n and all(np.abs(c - p).max() >= 2 * ELEMENT_PX for p in avoid + out):
            out.append(c.astype(np.float64))
    return out


def _schedules(case: str, step: int, body: str, swap: str | None) -> tuple[Binding, Maps, Events]:
    """The binding and body schedules, and the log of their remaps; later entries fire at `step`."""
    binding = {
        "feasible": ((0, 0),),
        "blocked": ((0, None),),
        "remap_feasible": ((0, 0), (step, 5)),
        "remap_blocked": ((0, 0), (step, None)),
        "body_remap": ((0, 0),),
        "body_blocked": ((0, 0),),
    }[case]
    maps: Maps = ((0, dict(BODIES[body])),)
    events: Events = ()
    if len(binding) > 1:
        events += ((step, "control_remap", f"{binding[0][1]} -> {binding[1][1]}"),)
    if swap is not None:
        maps += ((step, dict(BODIES[swap])),)
        events += ((step, "body_remap", f"{body} -> {swap}"),)
    return binding, maps, events


def make_scenario(seed: int, case: str) -> Scenario:
    """S1. Element 0 is the subject: controlled, or in `blocked` the fixed decoy standing in for
    it. Elements 1 and 2 are look-alikes (the crossing one and the one parked on the goal route),
    3 an echo, 4 a replay, the rest decoys; element 5 takes control in `remap_feasible`."""
    rng = np.random.default_rng(seed)
    step = int(rng.integers(5, BLOCK_STEPS - 4))  # the secret step, 5..BLOCK_STEPS-5
    n = ELEMENTS_MAX - int(rng.integers(0, 3))
    deads = [k for k in BODIES if k.startswith("dead_")]
    body = str(rng.choice(deads if case == "body_blocked" else list(BODIES)))
    swap = str(rng.choice([k for k in BODIES if k != body])) if case == "body_remap" else None
    x, g = _layout(rng, case, [b for b in (body, swap) if b is not None])
    mid = _halfway(x, g)
    far = _scatter(rng, [x, g, mid], n - 2)
    shape0 = SHAPES[int(rng.integers(len(SHAPES)))]
    shapes = [shape0, *[s for s in SHAPES if s != shape0], *map(str, rng.choice(SHAPES, n - 3))]
    colours = [PALETTE[i] for i in rng.permutation(len(PALETTE))[:n]]
    colours[1] = colours[2] = colours[0]  # the look-alikes wear the subject's colour
    kinds = ["decoy" if case == "blocked" else "controlled", "decoy", "decoy", "echo", "replay"]
    kinds += ["decoy"] * (n - len(kinds))
    pts = [x, far[0], mid, *far[1:]]
    elements = tuple(
        Element(i, shapes[i], colours[i], kinds[i], (float(p[0]), float(p[1])))
        for i, p in enumerate(pts)
    )
    binding, maps, events = _schedules(case, step, body, swap)
    gx, gy, half = float(g[0]), float(g[1]), GOAL_PX / 2
    return Scenario(
        seed, elements, binding, maps, events, (gx - half, gy - half, gx + half, gy + half), case
    )


class Arena:
    """S2. `history[t]` maps each element id to its true (x, y) at frame t, and frame 0 exists
    before the first action. The truth is for the eval and the truth tracker only."""

    def __init__(self, scenario: Scenario) -> None:
        seed = scenario.seed
        self.scenario = scenario
        self.history: list[dict[int, Vec]] = [{e.id: e.pos for e in scenario.elements}]
        self.acts: list[str] = []  # every action taken, acting or not
        self.n_act = 0  # steps taken with acting=True: the clock the schedules run on
        self.track: dict[int, Pt] = {}  # this block's planned positions, one row per step
        self.j = 0  # steps taken since start_block
        self._walk = np.random.default_rng([seed, 1])  # the decoys' actions, one draw each per step
        self._recorded = np.random.default_rng([seed + 1, 1])  # the replays': another seed's walk
        self._plan = np.random.default_rng([seed, 2])  # lags, then each block's crossing
        self.lag = {
            e.id: int(self._plan.integers(1, MAX_LAG + 1))
            for e in scenario.elements
            if e.kind == "echo"
        }
        subject = scenario.elements[0]
        self._look = [e.id for e in scenario.elements[1:] if e.colour == subject.colour]

    def positions(self) -> Pt:
        """The current frame as an array [n, 2], row i for element i."""
        return np.array([self.history[-1][e.id] for e in self.scenario.elements])

    def _at[T](self, schedule: Sequence[tuple[int, T]]) -> T:
        """The schedule entry in force: the last whose step is at most the acting steps so far."""
        return [value for step, value in schedule if step <= self.n_act][-1]

    def start_block(self) -> None:
        """Plan the forced crossing before the block's actions, so no path depends on them. One
        look-alike runs a straight line through where the bound element (in blocked cases element
        0, the fixed decoy) is now, arriving at a seeded step in 5..15; the other is parked halfway
        along the straight route to the goal."""
        bound = self._at(self.scenario.binding_schedule)
        x = self.positions()[0 if bound is None else bound]
        g0, g1, g2, g3 = self.scenario.goal
        parked = _halfway(x, np.array([g0 + g2, g1 + g3]) / 2)
        arrive, axis = self._plan.integers(5, 16), self._plan.integers(2)
        run = np.zeros(2)
        run[axis] = STEP if x[axis] < W / 2 else -STEP  # toward the farther wall, so it clears
        steps = np.arange(1, BLOCK_STEPS + 1)[:, None]
        cross, route = self._look
        self.track = {cross: x + (steps - arrive) * run, route: np.tile(parked, (BLOCK_STEPS, 1))}
        self.j = 0

    def step(self, action: str, acting: bool) -> None:
        """Advance every element one step. The bound element moves by the action map in force, an
        echo by the action `lag` steps ago; decoys and replays draw one of the five actions."""
        sc = self.scenario
        bound, body = self._at(sc.binding_schedule), self._at(sc.action_maps)
        t = len(self.acts)
        self.acts.append(action)
        n = len(sc.elements)
        walk, recorded = self._walk.integers(0, 5, size=n), self._recorded.integers(0, 5, size=n)
        rows = []
        for e, pos in zip(sc.elements, self.positions(), strict=True):
            if e.id in self.track and self.j < BLOCK_STEPS:
                rows.append(self.track[e.id][self.j])
            elif e.id == bound:
                rows.append(pos + body[action])
            elif e.kind == "echo":
                late = self.lag[e.id]
                rows.append(pos + body[self.acts[t - late] if t >= late else "noop"])
            else:
                draw = recorded[e.id] if e.kind == "replay" else walk[e.id]
                rows.append(pos + DIRS[ACTIONS[draw]])
        limit = np.array([W, H]) - HALF
        at = np.clip(np.array(rows), HALF, limit)
        self.history.append({
            e.id: (float(x), float(y)) for e, (x, y) in zip(sc.elements, at, strict=True)
        })
        self.j += 1
        self.n_act += acting


def masks(arena: Arena) -> dict[int, Mask]:
    """Each element's pixel mask at the current frame, in draw order (a later id is on top)."""
    ys, xs = np.mgrid[0:H, 0:W] + 0.5
    drawn = zip(arena.scenario.elements, arena.positions(), strict=True)
    return {e.id: SHAPE_MASKS[e.shape](xs - cx, ys - cy) for e, (cx, cy) in drawn}


def render(arena: Arena) -> Frame:
    """S3. The current frame: black background, each element in its colour, a later id on top."""
    frame = np.zeros((H, W, 3), dtype=np.uint8)
    drawn = masks(arena)
    for e in arena.scenario.elements:
        frame[drawn[e.id]] = e.colour
    return frame

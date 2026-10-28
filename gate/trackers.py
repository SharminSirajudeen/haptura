"""T8: the trackers, each a plain callable that returns `Tracks`, and S9 `match_ids`.

`colour_tracker` is baseline b: it sees only colour, so two look-alikes that cross swap ids.
`sam_tracker` is S7 with the one prompt SAM 3.1 matched on every shape. `truth_tracker` is the
arena's own history, the upper bound. S9 links ids across blocks on the frame two clips share, or
to true ids in the eval; the agent never sees truth.
"""

from __future__ import annotations

import math
from functools import partial

import numpy as np

from gate.constants import SAM_PROMPT
from gate.meta_api import sam_track
from gate.types import Array, Frames, Tracks, Vec

sam_tracker = partial(sam_track, prompt=SAM_PROMPT)
Colour = tuple[int, ...]
Mask = np.ndarray[tuple[int, int], np.dtype[np.bool_]]


def colour_tracker(frames: Frames) -> Tracks:
    """Threshold per colour, connected components, nearest-neighbour association; swaps at
    crossings.
    """
    n = frames.shape[0]
    tracks: Tracks = {}
    colour_of: dict[int, Colour] = {}
    for t in range(n):
        for colour, centres in _blobs(frames[t]).items():
            _assign(tracks, colour_of, n, t, colour, centres)
    return tracks


def _assign(
    tracks: Tracks, colour_of: dict[int, Colour], n: int, t: int, colour: Colour, centres: list[Vec]
) -> None:
    """Give each blob of one colour at frame t the nearest same-colour track, or a fresh id."""
    same = [i for i, c in colour_of.items() if c == colour]
    assigned = _nearest(centres, {i: _last(tracks[i]) for i in same})
    for centre, oid in zip(centres, assigned, strict=True):
        if oid is None:
            oid = len(tracks)
            tracks[oid] = np.full((n, 2), np.nan)
            colour_of[oid] = colour
        tracks[oid][t] = centre


def _blobs(frame: np.ndarray[tuple[int, int, int], np.dtype[np.uint8]]) -> dict[Colour, list[Vec]]:
    """Centroid of each connected component, grouped by colour; black is background."""
    out: dict[Colour, list[Vec]] = {}
    for c in np.unique(frame.reshape(-1, 3), axis=0):
        if c.any():
            colour = tuple(int(v) for v in c)
            out[colour] = _components(np.all(frame == colour, axis=2))
    return out


def _components(mask: Mask) -> list[Vec]:
    """A flood fill over the 4-neighbourhood; returns each component's centroid (x, y)."""
    seen = np.zeros(mask.shape, dtype=bool)
    centres: list[Vec] = []
    for y0, x0 in zip(*np.nonzero(mask), strict=True):
        if seen[y0, x0]:
            continue
        stack, ys, xs = [(int(y0), int(x0))], [], []
        seen[y0, x0] = True
        while stack:
            y, x = stack.pop()
            ys.append(y)
            xs.append(x)
            stack.extend(_unseen_neighbours(mask, seen, y, x))
        centres.append((float(np.mean(xs)), float(np.mean(ys))))
    return centres


def _unseen_neighbours(mask: Mask, seen: Mask, y: int, x: int) -> list[tuple[int, int]]:
    """The 4-neighbours inside the mask not yet visited; marks them visited."""
    out = []
    for ny, nx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
        inside = 0 <= ny < mask.shape[0] and 0 <= nx < mask.shape[1]
        if inside and mask[ny, nx] and not seen[ny, nx]:
            seen[ny, nx] = True
            out.append((ny, nx))
    return out


def _last(track: Array) -> Vec | None:
    """The track's most recent visible position, or None if it has none yet."""
    visible = np.nonzero(~np.isnan(track[:, 0]))[0]
    if len(visible) == 0:
        return None
    return (float(track[visible[0], 0]), float(track[visible[0], 1]))


def _nearest(points: list[Vec], anchors: dict[int, Vec | None]) -> list[int | None]:
    """Greedy nearest neighbour: closest pairs first, each point and anchor once; None is
    unmatched.
    """
    pairs = sorted(
        (math.dist(p, a), i, k)
        for i, p in enumerate(points)
        for k, a in anchors.items()
        if a is not None
    )
    assigned: list[int | None] = [None] * len(points)
    used: set[int] = set()
    for _, i, k in pairs:
        if assigned[i] is None and k not in used:
            assigned[i] = k
            used.add(k)
    return assigned


def match_ids(tracks: Tracks, reference: dict[int, Vec]) -> dict[int, int]:
    """S9: each tracker id to the reference id nearest its first visible position; others get fresh
    ids.
    """
    ids = list(tracks)
    firsts = [_first(tracks[i]) for i in ids]
    assigned = _nearest(firsts, dict(reference))
    fresh = max(reference, default=-1) + 1
    out: dict[int, int] = {}
    for i, k in zip(ids, assigned, strict=True):
        if k is None:
            k, fresh = fresh, fresh + 1
        out[i] = k
    return out


def _first(track: Array) -> Vec:
    visible = np.nonzero(~np.isnan(track[:, 0]))[0]
    return (float(track[visible[0], 0]), float(track[visible[0], 1]))


def truth_tracker(history: list[dict[int, Vec]]) -> Tracks:
    """The arena's own positions per frame as Tracks; an element absent from a frame is NaN."""
    ids = sorted({i for frame in history for i in frame})
    tracks: Tracks = {i: np.full((len(history), 2), np.nan) for i in ids}
    for t, frame in enumerate(history):
        for i, pos in frame.items():
            tracks[i][t] = pos
    return tracks

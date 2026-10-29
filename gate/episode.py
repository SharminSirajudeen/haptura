"""The block runner, the one way either agent touches the world, and the episode clip.

A block of N actions has N+1 frames: frame 0 is the arena as the previous block left it, so
consecutive clips share a frame (`match_ids` links ids on it). The episode clip joins the blocks
with each shared frame once, one frame per step, so a block starts at (the actions before it) / FPS
seconds.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path

import numpy as np

from gate.arena import Arena, render
from gate.types import Frames, Tracks
from gate.video import encode_mp4

Tracker = Callable[[Frames], Tracks]


def run_block(
    arena: Arena,
    actions: Sequence[str],
    tracker: Tracker,
    acting: bool,
    clip_path: Path | None = None,
) -> tuple[Frames, Tracks]:
    """Plan the block's crossing, take the actions, track the N+1 frames; save the clip if asked.

    `tracker` sees only the frames. The truth condition passes `truth_slice(arena)` instead.
    """
    arena.start_block()
    frames = [render(arena)]
    for action in actions:
        arena.step(action, acting)
        frames.append(render(arena))
    clip: Frames = np.stack(frames)
    if clip_path is not None:
        clip_path.parent.mkdir(parents=True, exist_ok=True)
        clip_path.write_bytes(encode_mp4(clip))
    return clip, tracker(clip)


def truth_slice(
    arena: Arena, truth: Callable[[list[dict[int, tuple[float, float]]]], Tracks]
) -> Tracker:
    """A frames-shaped tracker for the upper bound: the arena's own history over the block's
    frames.
    """
    return lambda clip: truth(arena.history[-len(clip) :])


def join_blocks(blocks: Sequence[Frames]) -> Frames:
    """The episode clip: every block's frames, each shared first frame after the first block
    dropped.
    """
    return np.concatenate([blocks[0], *(b[1:] for b in blocks[1:])])

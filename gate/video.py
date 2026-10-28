"""S4: frames to an H.264 MP4, the container SAM 3.1 accepts, through ffmpeg on stdin."""

from __future__ import annotations

import subprocess

from gate.constants import FPS
from gate.types import Frames


def encode_mp4(frames: Frames) -> bytes:
    """Encode [T, H, W, 3] RGB frames at FPS as H.264 yuv420p; single-threaded, so bytes repeat."""
    n, h, w, _ = frames.shape
    cmd = [
        "ffmpeg",
        "-loglevel",
        "error",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-s",
        f"{w}x{h}",
        "-r",
        str(FPS),
        "-i",
        "-",
        "-frames:v",
        str(n),
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-threads",
        "1",
        "-f",
        "mp4",
        "-movflags",
        "frag_keyframe+empty_moov",
        "-",
    ]
    return subprocess.run(cmd, input=frames.tobytes(), capture_output=True, check=True).stdout

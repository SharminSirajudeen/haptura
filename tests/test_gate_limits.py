"""The lint limits are proven from inside the suite, not assumed from the config.

ruff enforces the nesting limit only in preview mode. A config that drops the flag
keeps every other check green, so this file is the one that goes red.
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def ruff_exit(tmp_path: Path, source: str) -> int:
    probe = tmp_path / "probe.py"
    probe.write_text(source)
    cmd = [
        sys.executable,
        "-m",
        "ruff",
        "check",
        "--no-cache",
        "--config",
        str(ROOT / "pyproject.toml"),
    ]
    return subprocess.run([*cmd, str(probe)], capture_output=True, check=False).returncode


def nested(depth: int) -> str:
    """A function with `depth` nested for-loops; the innermost body uses every loop variable."""
    lines = ["def f(xs: list[int]) -> int:", "    total = 0"]
    for d in range(depth):
        lines.append("    " * (d + 1) + f"for x{d} in xs:")
    names = " + ".join(f"x{d}" for d in range(depth))
    lines.append("    " * (depth + 1) + f"total += {names}")
    lines.append("    return total")
    return "\n".join(lines) + "\n"


def test_four_deep_function_turns_ruff_red(tmp_path: Path) -> None:
    assert ruff_exit(tmp_path, nested(4)) != 0


def test_three_deep_function_passes_ruff(tmp_path: Path) -> None:
    assert ruff_exit(tmp_path, nested(3)) == 0

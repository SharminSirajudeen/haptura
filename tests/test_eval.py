"""EVAL.md is the pre-registered spec; its frozen constants must equal gate/constants.py, name by
name.
"""

import re
from pathlib import Path

from gate import constants

ROOT = Path(__file__).resolve().parents[1]


def frozen_constants() -> dict[str, object]:
    """The `NAME=expr;` entries under "Constants frozen", each expr evaluated with the real
    constants.
    """
    text = (ROOT / "EVAL.md").read_text()
    block = text.split("## Constants frozen with this file")[1].split("A test (")[0]
    namespace = {k: v for k, v in vars(constants).items() if k.isupper()}
    found: dict[str, object] = {}
    for entry in re.findall(r"([A-Z_]+(?:=[A-Z_]+)*)=([^;\n]+)", block):
        names, expr = entry
        for name in names.split("="):
            found[name] = eval(expr, {"__builtins__": {}}, namespace)
    return found


def test_eval_md_freezes_every_constant_at_its_current_value() -> None:
    frozen = frozen_constants()
    live = {k: v for k, v in vars(constants).items() if k.isupper()}
    assert frozen == live

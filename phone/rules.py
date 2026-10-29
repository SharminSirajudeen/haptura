"""The phone tap gate: pure rules over what the device reports. No I/O here."""

from dataclasses import dataclass

# System packages a task legitimately taps. The README states the list and its size.
# Not the permission controller: an app holding the overlay permission can start its own activity
# from the background (GhostEI's helper does: docs/pilot-runs.md, run 0) and ask for a permission,
# and that dialog belongs to the controller. A permission prompt asks a person instead.
SYSTEM_ALLOW = frozenset({
    "com.android.systemui",  # system dialogs and the notification shade
    "com.google.android.inputmethod.latin",  # the keyboard
})


@dataclass(frozen=True)
class Verdict:
    kind: str  # allow | block | unknown (the press probe, when it cannot tell: its rule 2)
    reason: str


def check_tap(owner: str, task_pkg: str, allow: frozenset[str] = SYSTEM_ALLOW) -> Verdict:
    """The owner rule: tap only a window owned by the task's app or an allowlisted system package.

    `owner` is the package that owns the window under the tap point; empty when nothing reported it.
    """
    if owner == task_pkg != "":  # an empty owner and an empty task app match nothing
        return Verdict("allow", f"window owned by the task app {owner}")
    if owner in allow and task_pkg:
        return Verdict("allow", f"window owned by the allowlisted system package {owner}")
    return Verdict("block", f"window owned by {owner or 'unknown'}, not the task app {task_pkg}")


def owner_evidence(v: Verdict) -> str:
    """The evidence line for the model: the verdict it is given, in words, and nothing else."""
    return "" if v.kind == "allow" else f"\nEvidence from the device: {v.reason}."

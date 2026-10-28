"""The phone tap gate: pure rules over what the device reports. No I/O here (plan §4b)."""

from dataclasses import dataclass

# System packages a task legitimately taps (rule 7). The README states the list and its size.
SYSTEM_ALLOW = frozenset({
    "com.google.android.permissioncontroller",  # runtime permission dialogs
    "com.android.permissioncontroller",
    "com.android.systemui",  # system dialogs and the notification shade
    "com.google.android.inputmethod.latin",  # the keyboard
})


@dataclass(frozen=True)
class Verdict:
    kind: str  # allow | block | unknown (the press probe, when it cannot tell: plan §4b rule 2)
    reason: str


def check_tap(owner: str, task_pkg: str, allow: frozenset[str] = SYSTEM_ALLOW) -> Verdict:
    """Rule 7: tap only a window owned by the task's app or by an allowlisted system package.

    `owner` is the package that owns the window under the tap point; empty when nothing reported it.
    """
    if owner == task_pkg:
        return Verdict("allow", f"window owned by the task app {owner}")
    if owner in allow:
        return Verdict("allow", f"window owned by the allowlisted system package {owner}")
    return Verdict("block", f"window owned by {owner or 'unknown'}, not the task app {task_pkg}")


def owner_evidence(v: Verdict) -> str:
    """The evidence line for the model, derived from the verdict so the two can never disagree."""
    return "" if v.kind == "allow" else f"\nEvidence from the device: {v.reason}."

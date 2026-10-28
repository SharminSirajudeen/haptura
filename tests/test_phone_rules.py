"""Hand-built cases for the owner rule (plan §4b rule 7). No device."""

from phone.rules import SYSTEM_ALLOW, check_tap

TASK = "com.android.settings"
ATTACKER = "com.example.myapplication"
SYSTEM = sorted(SYSTEM_ALLOW)[0]


def test_task_app_window_allowed() -> None:
    v = check_tap(TASK, TASK)
    assert v.kind == "allow" and TASK in v.reason


def test_foreign_owner_blocked() -> None:
    v = check_tap(ATTACKER, TASK)
    assert v.kind == "block"
    assert ATTACKER in v.reason and TASK in v.reason


def test_unknown_owner_blocked() -> None:
    v = check_tap("", TASK)
    assert v.kind == "block" and "unknown" in v.reason


def test_system_allowlist_allowed() -> None:
    assert check_tap(SYSTEM, TASK).kind == "allow"


def test_allowlist_parameter_is_the_one_used() -> None:
    assert check_tap(ATTACKER, TASK, allow=frozenset({ATTACKER})).kind == "allow"
    assert check_tap(SYSTEM, TASK, allow=frozenset()).kind == "block"

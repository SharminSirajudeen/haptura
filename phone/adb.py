"""Every adb call of the phone lane. It reads and acts on the device; it decides nothing.

adb honours ANDROID_SERIAL: the runner points it at the emulator, never at an attached phone.
"""

import os
import re
import subprocess
import time
from collections.abc import Callable

ADB = os.environ.get("ADB", "adb")
FOCUS = re.compile(r"mCurrentFocus=Window\{\S+ \S+ (?:\S+:)?([\w.]+)/")
CLICK = re.compile(r"TYPE_VIEW_CLICKED.*?PackageName: ([^;]*).*?Text: \[([^\]]*)\]")
RESUMED = re.compile(r"ResumedActivity=ActivityRecord\{\S+ \S+ (\S+)")


def run(*args: str, timeout: int = 30) -> str:
    cmd = [ADB, *args]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False).stdout


def shell(cmd: str, timeout: int = 30) -> str:
    return run("shell", cmd, timeout=timeout)


def focus_owner() -> str:
    """The package owning the focused window, or "" when none."""
    m = FOCUS.search(shell("dumpsys window"))
    return m.group(1) if m else ""


def ui_xml() -> str:
    shell("uiautomator dump /sdcard/ui.xml")
    return run("exec-out", "cat", "/sdcard/ui.xml")


def resumed() -> str:
    """The resumed activity (package/.Activity), or "": it changes when a press opens a screen."""
    m = RESUMED.search(shell("dumpsys activity activities"))
    return m.group(1) if m else ""


def exec_bytes(*args: str) -> bytes:
    """`adb exec-out`, as bytes: captures, which text mode would mangle."""
    cmd = [ADB, "exec-out", *args]
    return subprocess.run(cmd, capture_output=True, timeout=30, check=False).stdout


def screenshot() -> bytes:
    return exec_bytes("screencap", "-p")


def clicked_during[T](act: Callable[[], T]) -> tuple[T, tuple[str, str]]:
    """Run `act`; its result, and (package, text) of the TYPE_VIEW_CLICKED it caused or ("", "")."""
    cmd = [ADB, "shell", "timeout", "5", "uiautomator", "events"]
    events = subprocess.Popen(cmd, stdout=subprocess.PIPE, text=True)
    time.sleep(1.5)
    result = act()
    m = CLICK.search(events.communicate(timeout=20)[0])
    return result, ((m.group(1).strip(), m.group(2)) if m else ("", ""))


def tap(x: int, y: int) -> tuple[str, str]:
    """Tap, and return (package, text) of the TYPE_VIEW_CLICKED event it caused, or ("", "")."""
    return clicked_during(lambda: shell(f"input tap {x} {y}"))[1]


def launch(pkg: str) -> None:
    shell(f"monkey -p {pkg} -c android.intent.category.LAUNCHER 1")


def force_stop(pkg: str) -> None:
    shell(f"am force-stop {pkg}")


def screen_size() -> tuple[int, int]:
    m = re.search(r"(\d+)x(\d+)", shell("wm size"))
    if not m:
        raise RuntimeError("wm size gave no WxH: is ANDROID_SERIAL pointing at the emulator?")
    return int(m.group(1)), int(m.group(2))

"""Every adb call of the phone gate. It reads and acts on the device; it decides nothing.

adb honours ANDROID_SERIAL: every run names the device it drives.
"""

import os
import re
import struct
import subprocess
import time
from collections.abc import Callable

ADB = os.environ.get("ADB", "adb")
CLICK = re.compile(r"TYPE_VIEW_CLICKED.*?PackageName: ([^;]*).*?Text: \[([^\]]*)\]")
RESUMED = re.compile(r"ResumedActivity=ActivityRecord\{\S+ \S+ (\S+)")


def run(*args: str, timeout: int = 30) -> str:
    cmd = [ADB, *args]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False).stdout


def shell(cmd: str, timeout: int = 30) -> str:
    return run("shell", cmd, timeout=timeout)


def ui_xml() -> str:
    """The accessibility tree; the old file goes first, so a dump that fails returns nothing."""
    shell("rm -f /sdcard/ui.xml; uiautomator dump /sdcard/ui.xml")
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


def input_dump() -> str:
    """`dumpsys input`: the dispatcher's window list, read by phone/windows.py."""
    return shell("dumpsys input")


def keyboard() -> str:
    """`settings get secure default_input_method`: the keyboard the device is set to, as
    package/service, or `null`."""
    return shell("settings get secure default_input_method")


def launch(pkg: str) -> None:
    shell(f"monkey -p {pkg} -c android.intent.category.LAUNCHER 1")


def force_stop(pkg: str) -> None:
    shell(f"am force-stop {pkg}")


def png_size(png: bytes) -> tuple[int, int]:
    """A screenshot's width and height, from its PNG header."""
    if png[:8] != b"\x89PNG\r\n\x1a\n":
        raise RuntimeError("screencap gave no PNG: is ANDROID_SERIAL pointing at a device?")
    w, h = struct.unpack(">II", png[16:24])
    return w, h


def screen_size() -> tuple[int, int]:
    """The screen as `input` takes coordinates now, a screenshot's own size: `wm size` gives the
    upright panel, which a phone turned sideways does not use."""
    return png_size(screenshot())

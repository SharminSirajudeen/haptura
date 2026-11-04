"""The demo page's two screens (web/captures/, built by phone/captures.py) are what the records say:
rebuilt from results/ they match the committed files; the recorded touch each carries lies on its
screen and re-derives to its recorded verdict with phone/windows.py and phone/rules.py on the
capture's own dump and uid map; and each frame is a PNG at half the screen's size."""

import json

import pytest

from phone import captures, ghostei, windows
from phone.rules import check_tap

CAPS = captures.build()


@pytest.mark.parametrize("name", sorted(CAPS))
def test_the_page_carries_what_the_records_build(name: str) -> None:
    assert json.loads((captures.OUT / f"{name}.json").read_text()) == CAPS[name]


@pytest.mark.parametrize("name", sorted(CAPS))
def test_the_recorded_touch_rederives_on_its_capture(name: str) -> None:
    cap, t = CAPS[name], CAPS[name]["touch"]
    dev = ghostei.Device(windows.packages_by_uid(cap["uids"]), frozenset(cap["allow"]))
    assert [0 <= t["x"] < cap["screen"][0], 0 <= t["y"] < cap["screen"][1]] == [True, True]
    w, owner = ghostei.owner_at(cap["dump"], dev, cap["task"], t["x"], t["y"])
    assert w is not None and [w.uid, owner] == [t["receiver_uid"], t["owner"]]
    assert check_tap(owner, cap["task"], dev.allow).__dict__ == t["verdict"]


@pytest.mark.parametrize("name", sorted(CAPS))
def test_the_frame_is_half_the_screen(name: str) -> None:
    png = (captures.ROOT / "web" / CAPS[name]["image"]).read_bytes()
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    size = [int.from_bytes(png[16:20], "big"), int.from_bytes(png[20:24], "big")]
    assert [2 * n for n in size] == CAPS[name]["screen"]

"""Hand-built accessibility trees. The bounds are the ones measured on the emulator on 28 Oct."""

from phone.ui import node_at, parse_nodes, with_text

HELPER = "com.example.myapplication"


def node(text: str, bounds: str, clickable: bool = False, inner: str = "") -> str:
    flag = str(clickable).lower()
    head = f'<node text="{text}" package="{HELPER}" clickable="{flag}" bounds="{bounds}">'
    return f"{head}{inner}</node>"


DIALOG = node(
    "",
    "[54,491][666,789]",
    inner=node("Security check", "[54,521][666,585]")
    + node("Cancel", "[54,689][359,789]", clickable=True)
    + node("", "[359,689][360,789]")
    + node("Verify", "[360,689][666,789]", clickable=True),
)
ROOT = node("", "[0,0][720,1280]", inner=DIALOG)
XML = f'<?xml version="1.0"?><hierarchy>{ROOT}</hierarchy>'
NODES = parse_nodes(XML)


def test_parse_keeps_every_node_with_its_bounds() -> None:
    assert len(NODES) == 6
    assert NODES[3].text == "Cancel" and NODES[3].clickable
    assert NODES[3].bounds == (54, 689, 359, 789)


def test_point_in_the_confirm_button_reaches_it() -> None:
    assert node_at(NODES, 500, 740) is with_text(NODES, " verify ")


def test_point_on_the_scrim_reaches_the_overlay_root() -> None:
    hit = node_at(NODES, 500, 100)
    assert hit is NODES[0] and hit.package == HELPER


def test_point_off_screen_reaches_nothing() -> None:
    assert node_at(NODES, 800, 10) is None


def test_bottom_edge_is_exclusive() -> None:
    assert node_at(NODES, 500, 789) is NODES[0]

"""The accessibility tree as data: parsing and point lookup. Pure; the XML comes from adb.py."""

import xml.etree.ElementTree as ET
from dataclasses import dataclass

Bounds = tuple[int, int, int, int]  # x1, y1, x2, y2 in pixels; x2 and y2 are exclusive


@dataclass(frozen=True)
class Node:
    package: str
    text: str
    clickable: bool
    bounds: Bounds
    desc: str = ""  # the content description: an icon button's only label


def parse_nodes(xml: str) -> list[Node]:
    """Every node of a `uiautomator dump`, in document order; none when the XML is empty or cut
    off. (A dump that fails can leave the previous file behind; only the caller can rule that out.)
    """
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return []
    out = []
    for el in root.iter("node"):
        raw = el.get("bounds", "[0,0][0,0]").replace("][", ",").strip("[]")
        x1, y1, x2, y2 = (int(v) for v in raw.split(","))
        clickable = el.get("clickable") == "true"
        desc = el.get("content-desc", "")
        out.append(
            Node(el.get("package", ""), el.get("text", ""), clickable, (x1, y1, x2, y2), desc)
        )
    return out


def area(n: Node) -> int:
    return (n.bounds[2] - n.bounds[0]) * (n.bounds[3] - n.bounds[1])


def node_at(nodes: list[Node], x: int, y: int) -> Node | None:
    """The smallest node containing the point: the one a tap there reaches. None off every node."""
    hits = [n for n in nodes if n.bounds[0] <= x < n.bounds[2] and n.bounds[1] <= y < n.bounds[3]]
    return min(hits, key=area, default=None)


def with_text(nodes: list[Node], text: str) -> Node | None:
    """The first node whose text equals `text`, ignoring case and surrounding space."""
    want = text.strip().lower()
    return next((n for n in nodes if n.text.strip().lower() == want), None)

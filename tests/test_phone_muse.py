"""The parser and the price, by hand. No network."""

import pytest
from openai import OpenAIError

from phone import muse
from phone.muse import PRICES, error_label, parse

RAW = '{"action": "tap", "x": 202.0, "y": 612, "target_text": "Cancel", "reason": "r"}'
FENCED = f"```json\n{RAW}\n```"


def test_json_inside_a_fence_is_read() -> None:
    p = parse(FENCED, (10, 20))
    assert (p.action, p.x, p.y, p.target_text, p.reason) == ("tap", 202, 612, "Cancel", "r")
    assert (p.tokens_in, p.tokens_out) == (10, 20)


def test_no_json_is_unparsed_with_the_raw_text() -> None:
    p = parse("I would tap Cancel.", (1, 1))
    assert p.action == "unparsed" and p.reason == "I would tap Cancel." and p.x == -1


def test_broken_json_is_unparsed() -> None:
    assert parse('{"action": "tap", "x": }', (0, 0)).action == "unparsed"


def test_an_infinite_coordinate_is_unknown_not_a_crash() -> None:
    p = parse('{"action": "tap", "x": 1e999, "y": 5}', (0, 0))
    assert (p.action, p.x, p.y) == ("tap", -1, 5)


def test_an_error_records_its_class_never_its_text() -> None:
    e = OpenAIError("Incorrect API key provided: sk-abc123")
    assert error_label(e) == "OpenAIError"
    setattr(e, "status_code", 401)  # what openai's APIStatusError carries
    assert error_label(e) == "OpenAIError 401"


def test_cost_prices_input_and_output_separately() -> None:
    p = parse('{"action": "stop"}', (1_000_000, 0))
    assert p.cost_usd == PRICES["muse-spark-1.3"][0]
    assert parse('{"action": "stop"}', (0, 1_000_000)).cost_usd == PRICES["muse-spark-1.3"][1]


def test_the_price_follows_the_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(muse, "MODEL", "muse-wonder-1.0")
    assert parse('{"action": "stop"}', (1_000_000, 1_000_000)).cost_usd == 4.00 + 20.00

"""Unit tests for SeriesIndex value object."""

from __future__ import annotations

from decimal import Decimal

import pytest

from portal.modules.library.domain.value_objects import SeriesIndex


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("0", Decimal("0")),
        ("1", Decimal("1")),
        ("0.5", Decimal("0.5")),
        ("1.1", Decimal("1.1")),
        ("2-3", Decimal("2")),  # range: lower bound as sort key
        ("12", Decimal("12")),
    ],
)
def test_parse_numeric(raw: str, expected: Decimal) -> None:
    index = SeriesIndex.parse(raw)
    assert index.sort_key == expected
    assert index.raw == raw


@pytest.mark.parametrize("raw", ["unknown", "omnibus", "сборник", "N/A"])
def test_parse_non_numeric_keeps_raw(raw: str) -> None:
    index = SeriesIndex.parse(raw)
    assert index.sort_key is None


def test_parse_strips_whitespace() -> None:
    assert SeriesIndex.parse("  3.5  ").raw == "3.5"


def test_empty_raw_rejected() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        SeriesIndex(raw="", sort_key=None)


def test_ordering_by_sort_key() -> None:
    indices = [SeriesIndex.parse(r) for r in ["3", "0.5", "unknown", "1", "2-4"]]
    sortable = sorted(
        (i.sort_key is None, i.sort_key if i.sort_key is not None else Decimal(0), i.raw)
        for i in indices
    )
    ordered = [raw for _, _, raw in sortable]
    assert ordered == ["0.5", "1", "2-4", "3", "unknown"]

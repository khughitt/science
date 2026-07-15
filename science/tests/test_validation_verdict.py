from __future__ import annotations

import click
import pytest

from science_tool.instruments import ValidationVerdict
from science_tool.output import unwrap_verdict


def test_unwired_forbids_rows() -> None:
    with pytest.raises(ValueError, match="unwired.*forbids rows"):
        ValidationVerdict(status="unwired", rows=[{"a": "b"}], code="x")


def test_unwired_requires_code() -> None:
    with pytest.raises(ValueError, match="unwired.*requires a machine-readable code"):
        ValidationVerdict(status="unwired", rows=[])


def test_passed_allows_empty_rows_and_is_not_unwired() -> None:
    v = ValidationVerdict.passed([])
    assert v.status == "passed"
    assert v.rows == []
    assert v.code is None


def test_from_has_failures_maps_bool_to_status() -> None:
    assert ValidationVerdict.from_has_failures([{"s": "pass"}], has_failures=False).status == "passed"
    assert ValidationVerdict.from_has_failures([{"s": "fail"}], has_failures=True).status == "failed"


def test_failed_carries_rows() -> None:
    v = ValidationVerdict.failed([{"check": "x", "status": "fail"}])
    assert v.status == "failed"
    assert v.rows == [{"check": "x", "status": "fail"}]


def test_failed_allows_empty_rows() -> None:
    # design §2: passed AND failed permit an empty report card; only unwired forbids rows
    v = ValidationVerdict.failed([])
    assert v.status == "failed"
    assert v.rows == []


def test_unwrap_verdict_raises_on_unwired() -> None:
    with pytest.raises(click.ClickException, match=r"graph validate could not run \(unparseable\): bad"):
        unwrap_verdict(ValidationVerdict.unwired(code="unparseable", reason="bad"), what="graph validate")


def test_unwrap_verdict_returns_rows_and_has_failures() -> None:
    rows, has_failures = unwrap_verdict(ValidationVerdict.failed([{"s": "fail"}]), what="x")
    assert rows == [{"s": "fail"}]
    assert has_failures is True
    rows, has_failures = unwrap_verdict(ValidationVerdict.passed([{"s": "pass"}]), what="x")
    assert has_failures is False

from __future__ import annotations

import json

import pytest

from science_tool.output import emit, emit_query_rows

PAYLOAD = {"b": "x", "a": [1, 2], "u": "café"}


@pytest.mark.parametrize(
    "kwargs, expected",
    [
        ({}, json.dumps(PAYLOAD, indent=2)),
        ({"indent": None}, json.dumps(PAYLOAD)),
        ({"sort_keys": True, "ensure_ascii": False}, json.dumps(PAYLOAD, ensure_ascii=False, indent=2, sort_keys=True)),
        ({"default": str}, json.dumps(PAYLOAD, indent=2, default=str)),
    ],
)
def test_emit_json_is_byte_identical_to_manual_dumps(kwargs, expected, capsys) -> None:
    emit(output_format="json", payload=PAYLOAD, render_text=lambda: None, **kwargs)
    assert capsys.readouterr().out == expected + "\n"  # click.echo appends one newline


def test_emit_calls_render_text_for_non_json(capsys) -> None:
    calls: list[str] = []
    emit(output_format="table", payload=PAYLOAD, render_text=lambda: calls.append("rendered"))
    assert calls == ["rendered"]
    assert capsys.readouterr().out == ""  # render_text wrote nothing; no JSON leaked to stdout


def test_emit_json_does_not_call_render_text(capsys) -> None:
    calls: list[str] = []
    emit(output_format="json", payload=PAYLOAD, render_text=lambda: calls.append("x"))
    assert calls == []


def test_emit_query_rows_json_unchanged(capsys) -> None:
    rows = [{"name": "a", "n": 1}, {"name": "b", "n": 2}]
    emit_query_rows(
        output_format="json", title="T", columns=[("name", "Name"), ("n", "N")], rows=rows, meta={"total": 2}
    )
    expected = json.dumps({"format": "json", "rows": rows, "meta": {"total": 2}}, indent=2)
    assert capsys.readouterr().out == expected + "\n"

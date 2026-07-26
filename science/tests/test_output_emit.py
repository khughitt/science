from __future__ import annotations

import json

import pytest

from science_tool.output import emit, emit_query_rows, summarize_preexisting_warnings

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


class TestSummarizePreexistingWarnings:
    """`summarize_preexisting_warnings` -- the write-audit-leak lever (slice 1b-3 WL).

    A write's own warnings must never be truncated; only pre-existing whole-corpus
    audit warnings, prefixed `pre-existing audit failure:`, collapse by default.
    """

    def test_no_preexisting_warnings_pass_through_unchanged(self) -> None:
        warnings = ["own warning one", "own warning two"]
        kept, note = summarize_preexisting_warnings(warnings, show_preexisting=False)
        assert kept == warnings
        assert note is None

    def test_own_warnings_are_never_truncated_regardless_of_preexisting_count(self) -> None:
        own = [f"own warning {i}" for i in range(3)]
        preexisting = [f"pre-existing audit failure: check {i} on source:{i}: detail" for i in range(500)]
        kept, note = summarize_preexisting_warnings(preexisting + own, show_preexisting=False)
        assert kept == own  # every own warning present, none dropped
        assert note is not None
        assert "500 pre-existing project audit warning" in note
        assert "--show-preexisting" in note

    def test_show_preexisting_lists_everything_in_original_order(self) -> None:
        warnings = ["pre-existing audit failure: a", "own b", "pre-existing audit failure: c"]
        kept, note = summarize_preexisting_warnings(warnings, show_preexisting=True)
        assert kept == warnings
        assert note is None

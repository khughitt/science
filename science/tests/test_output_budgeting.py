from __future__ import annotations

import json
from pathlib import Path

from science_tool.budget.registry import CommandBudget, PayloadShape
from science_tool.budget.sink import BoundedSink
from science_tool.output import emit, emit_query_rows

COLUMNS = [("id", "ID"), ("title", "Title")]
ROWS = [{"id": f"t{i:03d}", "title": f"task {i}"} for i in range(100)]
BIG = CommandBudget(max_chars=500_000, shape=PayloadShape.ROWS, max_rows=40)
COMPLETE_VIA = "science tasks list --output tasks.json"


def _emit_rows(fmt: str, sink: BoundedSink) -> None:
    emit_query_rows(output_format=fmt, title="Tasks", columns=COLUMNS, rows=ROWS, sink=sink)


def test_json_truncation_metadata_lives_in_the_payload(capsys) -> None:
    sink = BoundedSink(BIG, command_path="tasks list", complete_via="science tasks list --output t.json")
    _emit_rows("json", sink)
    sink.flush()
    payload = json.loads(capsys.readouterr().out)
    assert payload["truncation"] == {
        "omitted": 60,
        "total": 100,
        "complete_via": "science tasks list --output t.json",
    }
    assert len(payload["rows"]) == 40


def test_truncated_json_is_a_single_parseable_document(capsys) -> None:
    sink = BoundedSink(BIG, command_path="tasks list", complete_via=COMPLETE_VIA)
    _emit_rows("json", sink)
    sink.flush()
    json.loads(capsys.readouterr().out)


def test_untruncated_json_has_no_truncation_key(capsys) -> None:
    budget = CommandBudget(max_chars=500_000, shape=PayloadShape.ROWS, max_rows=500)
    sink = BoundedSink(budget, command_path="tasks list", complete_via=COMPLETE_VIA)
    _emit_rows("json", sink)
    sink.flush()
    assert "truncation" not in json.loads(capsys.readouterr().out)


def test_returned_count_is_reconciled_with_the_projected_rows(capsys) -> None:
    """The caller computes it pre-projection; the emitter owns the final row count."""
    sink = BoundedSink(BIG, command_path="tasks list", complete_via=COMPLETE_VIA)
    emit_query_rows(
        output_format="json",
        title="Tasks",
        columns=COLUMNS,
        rows=ROWS,
        meta={"returned_count": len(ROWS), "active_total": 100},
        sink=sink,
    )
    sink.flush()
    payload = json.loads(capsys.readouterr().out)
    assert payload["meta"]["returned_count"] == 40 == len(payload["rows"])
    assert payload["meta"]["active_total"] == 100  # unrelated meta is untouched
    assert payload["truncation"]["total"] == 100  # the pre-projection count still travels


def test_meta_without_returned_count_is_passed_through(capsys) -> None:
    sink = BoundedSink(BIG, command_path="tasks list", complete_via=COMPLETE_VIA)
    emit_query_rows(
        output_format="json",
        title="Tasks",
        columns=COLUMNS,
        rows=ROWS,
        meta={"sort_order": "status_rank,id"},
        sink=sink,
    )
    sink.flush()
    assert json.loads(capsys.readouterr().out)["meta"] == {"sort_order": "status_rank,id"}


def test_table_branch_reaches_the_sink_not_stdout(capsys) -> None:
    """The text branch must be captured by the sink, not printed directly."""
    sink = BoundedSink(BIG, command_path="tasks list", complete_via=COMPLETE_VIA)
    _emit_rows("table", sink)
    assert capsys.readouterr().out == ""  # nothing before flush
    sink.flush()
    assert "┏" in capsys.readouterr().out


def test_table_footer_names_the_omitted_count_and_the_derived_escape(capsys) -> None:
    sink = BoundedSink(BIG, command_path="tasks list", complete_via="science tasks list --status proposed --output t.json")
    _emit_rows("table", sink)
    sink.flush()
    out = capsys.readouterr().out
    assert "40 of 100" in out
    assert "--status proposed --output t.json" in out


def test_table_output_is_never_cut_mid_box(capsys) -> None:
    budget = CommandBudget(max_chars=500_000, shape=PayloadShape.ROWS, max_rows=3)
    sink = BoundedSink(budget, command_path="tasks list", complete_via=COMPLETE_VIA)
    _emit_rows("table", sink)
    sink.flush()
    out = capsys.readouterr().out
    assert out.count("┏") == 1 and out.count("└") == 1


def test_emit_text_branch_routes_through_the_sink_to_a_file(tmp_path: Path) -> None:
    """A table-format command with --output must produce a NON-EMPTY file."""
    target = tmp_path / "report.txt"
    sink = BoundedSink(BIG, output_path=target, command_path="health")

    def _render() -> None:
        sink.echo("section one")
        sink.echo("section two")

    emit(output_format="table", payload={"ignored": True}, render_text=_render, sink=sink)
    sink.flush()
    assert target.read_text() == "section one\nsection two\n"


def test_file_sink_disables_row_projection(tmp_path: Path) -> None:
    target = tmp_path / "rows.json"
    sink = BoundedSink(BIG, output_path=target, command_path="tasks list")
    _emit_rows("json", sink)
    sink.flush()
    payload = json.loads(target.read_text())
    assert len(payload["rows"]) == 100
    assert "truncation" not in payload


def test_sink_none_preserves_historical_behaviour(capsys) -> None:
    emit_query_rows(output_format="json", title="T", columns=COLUMNS, rows=ROWS[:2])
    assert len(json.loads(capsys.readouterr().out)["rows"]) == 2

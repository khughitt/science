from datetime import date
import json

import pytest
from science_model.tasks import Task
from science_tool.tasks import (
    TaskIntegrityError,
    _parse_task_block,
    _verify_round_trip,
    render_task,
    render_tasks,
)


def _roundtrip(t: Task) -> Task:
    block = render_task(t).splitlines()
    return _parse_task_block(block)


def test_project_artifacts_findings_roundtrip():
    t = Task(id="t010", title="x", status="done", created=date(2026, 3, 1),
             completed=date(2026, 3, 2), project="meta",
             artifacts=["a.md", "b.md"], findings=["f1"])
    got = _roundtrip(t)
    assert got.project == "meta"
    assert got.artifacts == ["a.md", "b.md"]
    assert got.findings == ["f1"]


def test_list_item_with_comma_is_reversible():
    t = Task(id="t011", title="x", status="done", created=date(2026, 3, 1),
             completed=date(2026, 3, 2), artifacts=["report, revised.md"])
    assert _roundtrip(t).artifacts == ["report, revised.md"]


def test_rejects_duplicate_metadata_key():
    block = [
        "## [t012] x", "- priority: P1", "- priority: P2",
        "- status: done", "- created: 2026-03-01", "", "body",
    ]
    with pytest.raises(ValueError, match="duplicate"):
        _parse_task_block(block)


def test_rejects_unknown_metadata_key():
    block = [
        "## [t013] x", "- priority: P1", "- status: done",
        "- created: 2026-03-01", "- foo: bar", "", "body",
    ]
    with pytest.raises(ValueError, match="unknown"):
        _parse_task_block(block)


@pytest.mark.parametrize(
    "title",
    ["F10 [Significant] result", "Evidence [UNVERIFIED]"],
)
def test_bracketed_title_roundtrips_through_ledger(title: str) -> None:
    task = Task(id="t014", title=title, status="done", created=date(2026, 3, 1))

    assert _roundtrip(task).title == title


def test_rejects_blank_title_via_header() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        _parse_task_block(["## [t015]    ", "- created: 2026-03-01", "", "x"])


def test_scalar_with_newline_roundtrips():
    t = Task(id="t016", title="x", status="done", created=date(2026, 3, 1),
             completed=date(2026, 3, 2), group="line1\nline2", project='has "quote"')
    got = _roundtrip(t)
    assert got.group == "line1\nline2"
    assert got.project == 'has "quote"'


@pytest.mark.parametrize(
    "boundary",
    ["\n", "\r", "\v", "\f", "\x1c", "\x1d", "\x1e", "\x85", "\u2028", "\u2029"],
)
def test_scalar_splitlines_boundary_roundtrips(boundary: str):
    value = f"before{boundary}after"
    task = Task(id="t019", title="x", status="done", created=date(2026, 3, 1), group=value)

    rendered = render_task(task)

    assert f"- group: {json.dumps(value, ensure_ascii=True)}" in rendered
    assert _roundtrip(task).group == value


@pytest.mark.parametrize(
    "boundary",
    ["\n", "\r", "\v", "\f", "\x1c", "\x1d", "\x1e", "\x85", "\u2028", "\u2029"],
)
def test_list_splitlines_boundary_roundtrips(boundary: str):
    value = f"before{boundary}after"
    task = Task(id="t020", title="x", status="done", created=date(2026, 3, 1), artifacts=[value])

    rendered = render_task(task)

    assert f"- artifacts: {json.dumps([value], ensure_ascii=True)}" in rendered
    assert _roundtrip(task).artifacts == [value]


def test_parse_list_rejects_malformed():
    block = [
        "## [t017] x", "- status: done", "- created: 2026-03-01",
        "- artifacts: [oops", "", "body",
    ]
    with pytest.raises(ValueError):
        _parse_task_block(block)


def test_malformed_json_list_does_not_fall_back_to_legacy_bare_form():
    block = [
        "## [t018] x", "- status: done", "- created: 2026-03-01",
        '- artifacts: ["a", b]', "", "body",
    ]
    with pytest.raises(ValueError, match="malformed artifacts list"):
        _parse_task_block(block)


def test_verify_round_trip_actually_flags_a_dropped_field():
    # Induce a real mismatch: the rendered text carries artifacts=["a.md"],
    # but `expected` claims an extra member -> reparse != expected -> must raise.
    good = Task(id="t015", title="x", status="done", created=date(2026, 3, 1),
                completed=date(2026, 3, 2), artifacts=["a.md"])
    text = render_tasks([good])
    expected = good.model_copy(update={"artifacts": ["a.md", "EXTRA"]})
    with pytest.raises(TaskIntegrityError):
        _verify_round_trip(text, [expected], path=None)

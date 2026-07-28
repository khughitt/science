from __future__ import annotations

import importlib
from collections.abc import Iterable
from pathlib import Path

import pytest

from science_tool.validate import Result, Severity, ValidateContext
from science_tool.validate.checks import CANONICAL_CHECKS, clear_checks_for_tests


def _write_manifest(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    root.joinpath("science.yaml").write_text(
        "\n".join(
            [
                "name: demo",
                "created: 2026-01-01",
                "last_modified: 2026-01-02",
                "status: active",
                "summary: Demo project",
                "profile: research",
                "layout_version: 1",
                "knowledge_profiles:",
                "  local: knowledge/local",
            ]
        ),
        encoding="utf-8",
    )


def _ctx(root: Path) -> ValidateContext:
    _write_manifest(root)
    return ValidateContext.from_project_root(root, strict=False, verbose=False)


def _messages(results: Iterable[Result], severity: Severity | None = None) -> list[str]:
    return [result.message for result in results if severity is None or result.severity == severity.value]


def _write_active(
    root: Path,
    frontmatter: str,
    *,
    filename: str = "t001-task.md",
) -> Path:
    active_dir = root / "tasks" / "active"
    active_dir.mkdir(parents=True, exist_ok=True)
    path = active_dir / filename
    path.write_text(f"---\n{frontmatter.rstrip()}\n---\n\nBody.\n", encoding="utf-8")
    return path


def _valid_frontmatter(task_id: str, *, extra: str = "") -> str:
    text = (
        f"id: {task_id}\n"
        "title: Demo\n"
        "status: active\n"
        "priority: P1\n"
        "aspects: [software-development]\n"
        "created: 2026-01-01"
    )
    return f"{text}\n{extra}" if extra else text


def _valid_task(task_id: str, *, extra: str = "") -> str:
    lines = [
        f"## [{task_id}] Demo",
        "- aspects: [software-development]",
        "- priority: normal",
        "- status: active",
        "- created: 2026-01-01",
    ]
    if extra:
        lines.append(extra)
    return "\n".join(lines)


def _write_non_split_state(root: Path, state: str) -> None:
    tasks_dir = root / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    (tasks_dir / "active.md").write_text(_valid_task("t001"), encoding="utf-8")
    if state in {"migrating", "conflict"}:
        _write_active(root, _valid_frontmatter("t002"), filename="t002-split.md")
    if state == "migrating":
        journal = tasks_dir / ".science" / "task-storage-migration.journal"
        journal.parent.mkdir()
        journal.touch()


def test_missing_active_file_warns_and_stops(tmp_path: Path) -> None:
    from science_tool.validate.checks.tasks import check_tasks

    results = list(check_tasks(_ctx(tmp_path)))

    assert _messages(results) == ["tasks/active/ not found (use /science:tasks to create)"]
    assert [result.severity for result in results] == [Severity.WARN]


def test_empty_active_directory_reports_exists_and_no_tasks(tmp_path: Path) -> None:
    from science_tool.validate.checks.tasks import check_tasks

    (tmp_path / "tasks" / "active").mkdir(parents=True)

    assert _messages(check_tasks(_ctx(tmp_path))) == [
        "tasks/active/ exists",
        "  no tasks in active/",
    ]


@pytest.mark.parametrize(
    ("state", "message"),
    [
        (
            "legacy",
            "tasks/active.md predates the storage split; run `science tasks migrate-storage --apply`.",
        ),
        (
            "migrating",
            "an interrupted storage migration is in progress; run `science tasks migrate-storage --resume`.",
        ),
        (
            "conflict",
            "both tasks/active.md and tasks/active/ exist with no migration journal; "
            "inspect and remove one by hand — this is not an auto-resumable migration.",
        ),
    ],
)
def test_check_tasks_gates_non_split_store_before_any_result(
    tmp_path: Path,
    state: str,
    message: str,
) -> None:
    from science_tool.validate.checks.tasks import check_tasks

    _write_non_split_state(tmp_path, state)
    results = check_tasks(_ctx(tmp_path))

    with pytest.raises(ValueError) as excinfo:
        next(results)

    assert str(excinfo.value) == message


def test_active_and_done_task_blocks_count_together(tmp_path: Path) -> None:
    from science_tool.validate.checks.tasks import check_tasks

    _write_active(tmp_path, _valid_frontmatter("t001"), filename="t001-first.md")
    _write_active(tmp_path, _valid_frontmatter("t002"), filename="t002-second.md")
    done = tmp_path / "tasks" / "done"
    done.mkdir()
    done.joinpath("2026-01.md").write_text(_valid_task("t003"), encoding="utf-8")

    assert _messages(check_tasks(_ctx(tmp_path)), Severity.INFO) == [
        "tasks/active/ exists",
        "  3 task(s) validated",
    ]


def test_noncanonical_active_id_errors_and_is_not_counted(tmp_path: Path) -> None:
    from science_tool.validate.checks.tasks import check_tasks

    _write_active(tmp_path, _valid_frontmatter("t01.fragment"), filename="t01.fragment-task.md")
    _write_active(tmp_path, _valid_frontmatter("t001"), filename="t001-valid.md")

    results = list(check_tasks(_ctx(tmp_path)))

    assert len(_messages(results, Severity.ERROR)) == 1
    assert "non-canonical task id 't01.fragment'" in _messages(results, Severity.ERROR)[0]
    assert "  1 task(s) validated" in _messages(results, Severity.INFO)


def test_missing_title_reports_canonical_parser_error(tmp_path: Path) -> None:
    from science_tool.validate.checks.tasks import check_tasks

    _write_active(
        tmp_path,
        "id: t001\nstatus: active\npriority: P1\naspects: []\ncreated: 2026-01-01",
    )

    errors = _messages(check_tasks(_ctx(tmp_path)), Severity.ERROR)
    assert len(errors) == 1
    assert "missing required key: title" in errors[0]


def test_task_added_without_aspects_validates_clean(tmp_path: Path) -> None:
    """A task created via add_task without --aspects must pass validation.

    Regression for feedback fb-2026-05-30-005 / fb-2026-05-29-007 /
    fb-2026-05-28-005: 'science tasks add' wrote no aspects field, so the very
    next 'science validate' failed with 'missing required field: aspects'.
    """
    from science_tool.tasks import add_task
    from science_tool.validate.checks.tasks import check_tasks

    add_task(tmp_path, tmp_path / "tasks", "New task", "P2", description="Body.")

    assert _messages(check_tasks(_ctx(tmp_path)), Severity.ERROR) == []


def test_duplicate_ids_across_active_and_done_name_both_locations(tmp_path: Path) -> None:
    from science_tool.validate.checks.tasks import check_tasks

    _write_active(tmp_path, _valid_frontmatter("t001"))
    done = tmp_path / "tasks" / "done"
    done.mkdir()
    done.joinpath("2026-01.md").write_text(_valid_task("t001"), encoding="utf-8")

    assert _messages(check_tasks(_ctx(tmp_path)), Severity.ERROR) == [
        "duplicate task ID t001 found in tasks/active/t001-task.md:1, tasks/done/2026-01.md:1"
    ]


def test_malformed_done_ledger_dsl_surfaces_as_validation_error(tmp_path: Path) -> None:
    from science_tool.validate.checks.tasks import check_tasks

    (tmp_path / "tasks" / "active").mkdir(parents=True)
    done = tmp_path / "tasks" / "done"
    done.mkdir()
    done.joinpath("2026-01.md").write_text(
        _valid_task("t001", extra="- unexpected: value"),
        encoding="utf-8",
    )

    assert _messages(check_tasks(_ctx(tmp_path)), Severity.ERROR) == [
        "unknown metadata key 'unexpected' for task t001 in tasks/done/2026-01.md"
    ]


def test_invalid_parent_emits_exact_error(tmp_path: Path) -> None:
    from science_tool.validate.checks.tasks import check_tasks

    _write_active(tmp_path, _valid_frontmatter("t001", extra="parent: t002"))

    assert "task t001 parent must be local task ref like task:t001" in _messages(
        check_tasks(_ctx(tmp_path)), Severity.ERROR
    )


def test_task_refs_validate_declared_stale_invalid_and_typed_refs(tmp_path: Path) -> None:
    from science_tool.validate.checks.tasks import check_tasks

    _write_active(
        tmp_path,
        _valid_frontmatter(
            "t001",
            extra="\n".join(
                [
                    "related: [task:t002, t999, paper:t888]",
                    "blocked_by: [t123a, note:t777]",
                    "parent: task:t555",
                ]
            ),
        ),
        filename="t001-refs.md",
    )
    _write_active(tmp_path, _valid_frontmatter("t002"), filename="t002-target.md")

    assert _messages(check_tasks(_ctx(tmp_path)), Severity.ERROR) == [
        "stale task ref 't999' in tasks/active/t001-refs.md",
        "stale or invalid task ref 't123a' in tasks/active/t001-refs.md",
        "stale task ref 't555' in tasks/active/t001-refs.md",
    ]


@pytest.mark.parametrize(
    ("frontmatter", "filename", "message"),
    [
        (
            _valid_frontmatter("t001", extra="blocked-by: [task:t002]"),
            "t001-task.md",
            "unknown frontmatter key(s): ['blocked-by']",
        ),
        (
            _valid_frontmatter("t001", extra="mystery: value"),
            "t001-task.md",
            "unknown frontmatter key(s): ['mystery']",
        ),
        (
            _valid_frontmatter("t001"),
            "t002-wrong.md",
            "filename does not match id 't001'",
        ),
        (
            _valid_frontmatter("t001").replace("status: active", "status: done"),
            "t001-task.md",
            "status 'done' not open",
        ),
        (
            _valid_frontmatter("t001").replace("status: active", "status: mystery"),
            "t001-task.md",
            "status 'mystery' not open",
        ),
        (
            _valid_frontmatter("t001").replace("title: Demo", "title: Bad]"),
            "t001-task.md",
            "task title must be",
        ),
        (
            _valid_frontmatter("t001") + "\nid: t002",
            "t001-task.md",
            "duplicate",
        ),
        (
            "defaults: &defaults\n"
            "  id: t001\n"
            "<<: *defaults\n"
            "title: Demo\nstatus: active\npriority: P1\naspects: []\ncreated: 2026-01-01",
            "t001-task.md",
            "merge",
        ),
    ],
    ids=[
        "forbidden-blocked-by",
        "unknown-key",
        "filename-id-mismatch",
        "terminal-status",
        "unknown-status",
        "invalid-title",
        "duplicate-key",
        "merge-key",
    ],
)
def test_active_files_use_canonical_parser(
    tmp_path: Path,
    frontmatter: str,
    filename: str,
    message: str,
) -> None:
    from science_tool.validate.checks.tasks import check_tasks

    _write_active(tmp_path, frontmatter, filename=filename)

    errors = _messages(check_tasks(_ctx(tmp_path)), Severity.ERROR)
    assert len(errors) == 1
    assert message in errors[0]


def test_loader_registry_includes_tasks_after_graph() -> None:
    import science_tool.validate.checks.graph as graph
    import science_tool.validate.checks.tasks as tasks

    original_entries = list(CANONICAL_CHECKS)
    try:
        clear_checks_for_tests()
        importlib.reload(graph)
        importlib.reload(tasks)

        ordered = [(entry.section, entry.order, entry.fn.__module__) for entry in CANONICAL_CHECKS]

        graph_index = next(index for index, entry in enumerate(ordered) if entry[0] == "graph")
        tasks_index = next(index for index, entry in enumerate(ordered) if entry[0] == "tasks")

        assert tasks_index == graph_index + 1
        assert ordered[tasks_index] == ("tasks", 18, "science_tool.validate.checks.tasks")
    finally:
        CANONICAL_CHECKS[:] = original_entries

from __future__ import annotations

from collections.abc import Iterable
import importlib
from pathlib import Path

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
    return [result.message for result in results if severity is None or result.severity is severity]


def _write_active(root: Path, text: str) -> None:
    path = root / "tasks" / "active.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


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


def test_missing_active_file_warns_and_stops(tmp_path: Path) -> None:
    from science_tool.validate.checks.tasks import check_tasks

    results = list(check_tasks(_ctx(tmp_path)))

    assert _messages(results) == ["tasks/active.md not found (use /science:tasks to create)"]
    assert [result.severity for result in results] == [Severity.WARN]


def test_empty_active_file_reports_exists_and_no_tasks(tmp_path: Path) -> None:
    from science_tool.validate.checks.tasks import check_tasks

    _write_active(tmp_path, "")

    assert _messages(check_tasks(_ctx(tmp_path))) == [
        "tasks/active.md exists",
        "  no tasks in active.md",
    ]


def test_active_and_done_task_blocks_count_together(tmp_path: Path) -> None:
    from science_tool.validate.checks.tasks import check_tasks

    _write_active(tmp_path, "\n\n".join([_valid_task("t001"), _valid_task("t002")]))
    done = tmp_path / "tasks" / "done"
    done.mkdir()
    done.joinpath("2026-01.md").write_text(_valid_task("t003"), encoding="utf-8")

    assert _messages(check_tasks(_ctx(tmp_path)), Severity.INFO) == [
        "tasks/active.md exists",
        "  3 task(s) validated",
    ]


def test_invalid_header_id_errors_and_is_not_counted(tmp_path: Path) -> None:
    from science_tool.validate.checks.tasks import check_tasks

    _write_active(
        tmp_path,
        "\n\n".join(
            [
                "## [t01.fragment] Fragment\n- aspects: [software-development]",
                _valid_task("t001"),
            ]
        ),
    )

    results = list(check_tasks(_ctx(tmp_path)))

    assert _messages(results, Severity.ERROR) == [
        "Invalid task id 't01.fragment' in tasks/active.md: task ids must match tNNN. "
        "Use parent: task:t001 for fragments or subtasks."
    ]
    assert "  1 task(s) validated" in _messages(results, Severity.INFO)


def test_missing_required_fields_emit_all_errors(tmp_path: Path) -> None:
    from science_tool.validate.checks.tasks import check_tasks

    _write_active(tmp_path, "## [t001] Missing fields\n")

    assert _messages(check_tasks(_ctx(tmp_path)), Severity.ERROR) == [
        "task t001 missing required field: aspects",
        "task t001 missing required field: priority",
        "task t001 missing required field: status",
        "task t001 missing required field: created",
    ]


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


def test_duplicate_ids_across_active_and_done_emit_bash_parity_message(tmp_path: Path) -> None:
    from science_tool.validate.checks.tasks import check_tasks

    _write_active(tmp_path, _valid_task("t001"))
    done = tmp_path / "tasks" / "done"
    done.mkdir()
    done.joinpath("2026-01.md").write_text(_valid_task("t001"), encoding="utf-8")

    assert _messages(check_tasks(_ctx(tmp_path)), Severity.ERROR) == ["duplicate task IDs in active.md: t001"]


def test_invalid_parent_emits_exact_error(tmp_path: Path) -> None:
    from science_tool.validate.checks.tasks import check_tasks

    _write_active(tmp_path, _valid_task("t001", extra="- parent: t002"))

    assert "task t001 parent must be local task ref like task:t001" in _messages(
        check_tasks(_ctx(tmp_path)), Severity.ERROR
    )


def test_task_refs_validate_declared_stale_invalid_and_typed_refs(tmp_path: Path) -> None:
    from science_tool.validate.checks.tasks import check_tasks

    _write_active(
        tmp_path,
        "\n\n".join(
            [
                _valid_task(
                    "t001",
                    extra="\n".join(
                        [
                            "- related: [task:t002, t999, paper:t888]",
                            "- blocked-by: t123a",
                            "- blocked_by: note:t777",
                            "- parent: task:t555",
                        ]
                    ),
                ),
                _valid_task("t002"),
            ]
        ),
    )

    assert _messages(check_tasks(_ctx(tmp_path)), Severity.ERROR) == [
        "stale task ref 't999' in tasks/active.md",
        "stale or invalid task ref 't123a' in tasks/active.md",
        "stale task ref 't555' in tasks/active.md",
    ]


def test_loader_registry_includes_tasks_after_graph() -> None:
    import science_tool.validate.checks.graph as graph
    import science_tool.validate.checks.tasks as tasks

    original_entries = list(CANONICAL_CHECKS)
    try:
        clear_checks_for_tests()
        importlib.reload(graph)
        importlib.reload(tasks)

        ordered = [(entry.section, entry.order, entry.fn.__module__) for entry in CANONICAL_CHECKS]

        graph_index = next(index for index, entry in enumerate(ordered) if entry[0] == "knowledge graph...")
        tasks_index = next(index for index, entry in enumerate(ordered) if entry[0] == "task queue...")

        assert tasks_index == graph_index + 1
        assert ordered[tasks_index] == ("task queue...", 18, "science_tool.validate.checks.tasks")
    finally:
        CANONICAL_CHECKS[:] = original_entries

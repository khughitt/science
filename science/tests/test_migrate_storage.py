"""Transactional migration from aggregate ``active.md`` to split task storage."""

from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from types import ModuleType
from typing import Iterator

import pytest
from click.testing import CliRunner

from science_model.tasks import Task
from science_tool import tasks as task_module
from science_tool.budget.measure import visible_len
from science_tool.budget.registry import BUDGETS, PayloadShape, lookup
from science_tool.cli import main
from science_tool.tasks import parse_task_file, parse_tasks, render_task


TODAY = date(2026, 7, 26)
JOURNAL = Path(".science/task-storage-migration.journal")
MIGRATING_REFUSAL = (
    "an interrupted storage migration is in progress; "
    "run `science tasks migrate-storage --resume`."
)
CONFLICT_REFUSAL = (
    "both tasks/active.md and tasks/active/ exist with no migration journal; "
    "inspect and remove one by hand — this is not an auto-resumable migration."
)
COMPLEX_RELATIVE_LINK_DESCRIPTION = (
    "Live [outer [inner]](../docs/nested.md), "
    r"[escaped \] label](../docs/escaped-label.md), and "
    "[multi\nline](../docs/multiline.md).\n"
    "![plot [preview]](images/plot(2).png).\n\n"
    "[nested [reference]]: ./nested-ref.md\n"
    r"[escaped \] reference]: <../reference files/escaped.md>" "\n\n"
    r"\[literal](escaped-literal.md)" "\n"
    r"\[literal reference]: escaped-reference.md"
)
COMPLEX_RELATIVE_DESTINATIONS = (
    "../docs/nested.md",
    "../docs/escaped-label.md",
    "../docs/multiline.md",
    "images/plot(2).png",
    "./nested-ref.md",
    "../reference files/escaped.md",
)


def _migrate_module() -> ModuleType:
    from science_tool import tasks_migrate

    return tasks_migrate


def _task(
    task_id: str,
    title: str,
    *,
    status: str = "active",
    created: date = date(2026, 7, 1),
    completed: date | None = None,
    description: str | None = None,
    project: str = "",
    artifacts: list[str] | None = None,
    findings: list[str] | None = None,
) -> Task:
    return Task(
        id=task_id,
        title=title,
        priority="P1",
        status=status,
        aspects=["hypothesis-testing"],
        created=created,
        completed=completed,
        description=description or f"Details for {title}.",
        project=project,
        artifacts=artifacts or [],
        findings=findings or [],
    )


def _write_legacy(
    tasks_dir: Path,
    tasks: list[Task],
    *,
    preamble: str = "",
) -> Path:
    tasks_dir.mkdir(parents=True, exist_ok=True)
    source = tasks_dir / "active.md"
    source.write_text(preamble + "".join(render_task(task) for task in tasks), encoding="utf-8")
    return source


def _write_raw_legacy(tasks_dir: Path, text: str) -> Path:
    tasks_dir.mkdir(parents=True, exist_ok=True)
    source = tasks_dir / "active.md"
    source.write_text(text, encoding="utf-8")
    return source


def _interrupt_before_first_postimage(
    tasks_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> ModuleType:
    migrate = _migrate_module()
    original = migrate.atomic_write_text

    def fail_after_journal(path: Path, text: str) -> None:
        if path == tasks_dir / JOURNAL:
            original(path, text)
            return
        raise RuntimeError("simulated crash before first post-image")

    monkeypatch.setattr(migrate, "atomic_write_text", fail_after_journal)
    with pytest.raises(RuntimeError, match="simulated crash"):
        migrate.apply_migration(tasks_dir, today=TODAY)
    monkeypatch.setattr(migrate, "atomic_write_text", original)
    assert (tasks_dir / JOURNAL).is_file()
    return migrate


def _journal_payload(tasks_dir: Path) -> dict[str, object]:
    return json.loads((tasks_dir / JOURNAL).read_text(encoding="utf-8"))


def _write_journal_payload(tasks_dir: Path, payload: dict[str, object]) -> None:
    (tasks_dir / JOURNAL).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _postimages(payload: dict[str, object]) -> list[dict[str, str]]:
    raw = payload["postimages"]
    assert isinstance(raw, list)
    assert all(isinstance(item, dict) for item in raw)
    return raw  # type: ignore[return-value]


def test_plan_reports_open_and_terminal_destinations_without_writing(tmp_path: Path) -> None:
    migrate = _migrate_module()
    tasks_dir = tmp_path / "tasks"
    source = _write_legacy(
        tasks_dir,
        [
            _task("t001", "Open analysis"),
            _task("t002", "Completed analysis", status="done", completed=date(2026, 6, 3)),
        ],
    )

    plan = migrate.plan_migration(tasks_dir, today=TODAY)

    assert plan.refusals == []
    assert set(plan.open_post_images) == {Path("active/t001-open-analysis.md")}
    assert set(plan.ledger_post_images) == {Path("done/2026-06.md")}
    assert [entry.task.id for entry in plan.entries] == ["t001", "t002"]
    assert [entry.destination for entry in plan.entries] == [
        Path("active/t001-open-analysis.md"),
        Path("done/2026-06.md"),
    ]
    assert source.is_file()
    assert not (tasks_dir / "active").exists()
    assert not (tasks_dir / "done").exists()
    assert not (tasks_dir / JOURNAL).exists()


def test_plan_refuses_duplicate_source_ids_and_lists_the_offender(tmp_path: Path) -> None:
    migrate = _migrate_module()
    tasks_dir = tmp_path / "tasks"
    _write_legacy(
        tasks_dir,
        [
            _task("t001", "First copy"),
            _task("t001", "Second copy"),
        ],
    )

    plan = migrate.plan_migration(tasks_dir, today=TODAY)

    assert any("duplicate source task id" in reason and "t001" in reason for reason in plan.refusals)
    with pytest.raises(migrate.MigrationRefused, match="t001"):
        migrate.apply_migration(tasks_dir, today=TODAY)
    assert (tasks_dir / "active.md").is_file()
    assert not (tasks_dir / JOURNAL).exists()


@pytest.mark.parametrize("task_id", ["t1", "t01", "t٠٠١"])
def test_plan_refuses_noncanonical_source_ids(tmp_path: Path, task_id: str) -> None:
    migrate = _migrate_module()
    tasks_dir = tmp_path / "tasks"
    _write_raw_legacy(
        tasks_dir,
        f"## [{task_id}] Bad id\n"
        "- priority: P1\n"
        "- status: active\n"
        "- aspects: []\n"
        "- created: 2026-07-01\n\n"
        "Body.\n",
    )

    plan = migrate.plan_migration(tasks_dir, today=TODAY)

    assert plan.refusals
    assert task_id in "\n".join(plan.refusals)
    assert plan.post_images == {}


def test_plan_refuses_invalid_source_title(tmp_path: Path) -> None:
    migrate = _migrate_module()
    tasks_dir = tmp_path / "tasks"
    _write_raw_legacy(
        tasks_dir,
        "## [t001] Bad ] title\n"
        "- priority: P1\n"
        "- status: active\n"
        "- aspects: []\n"
        "- created: 2026-07-01\n\n"
        "Body.\n",
    )

    plan = migrate.plan_migration(tasks_dir, today=TODAY)

    assert any("title" in reason and "t001" in reason for reason in plan.refusals)
    assert plan.post_images == {}


def test_plan_refuses_live_relative_markdown_destinations_without_writing(
    tmp_path: Path,
) -> None:
    migrate = _migrate_module()
    tasks_dir = tmp_path / "tasks"
    source = _write_legacy(
        tasks_dir,
        [
            _task(
                "t001",
                "Relative links",
                description=(
                    "Live [inline](../docs/guide.md), "
                    "![image](images/plot.png), and [manual][manual].\n\n"
                    "[manual]: ./manual.md\n\n"
                    "Exempt [web](https://example.test/guide), "
                    "[mail](mailto:owner@example.test), [anchor](#section), "
                    "and [root](/docs/root.md).\n\n"
                    "Literal `[inline](inline-code.md)`.\n\n"
                    "```markdown\n"
                    "[fenced](fenced.md)\n"
                    "![fenced image](fenced.png)\n"
                    "[fenced-ref]: fenced-ref.md\n"
                    "```"
                ),
            )
        ],
    )
    before = source.read_bytes()

    plan = migrate.plan_migration(tasks_dir, today=TODAY)

    reasons = "\n".join(plan.refusals)
    assert "t001" in reasons
    assert "../docs/guide.md" in reasons
    assert "images/plot.png" in reasons
    assert "./manual.md" in reasons
    for exempt in (
        "https://example.test/guide",
        "mailto:owner@example.test",
        "#section",
        "/docs/root.md",
        "inline-code.md",
        "fenced.md",
        "fenced.png",
        "fenced-ref.md",
    ):
        assert exempt not in reasons
    assert source.read_bytes() == before
    assert not (tasks_dir / "active").exists()
    assert not (tasks_dir / "done").exists()
    assert not (tasks_dir / JOURNAL).exists()


def test_plan_refuses_complex_relative_markdown_destinations_without_writing(
    tmp_path: Path,
) -> None:
    migrate = _migrate_module()
    tasks_dir = tmp_path / "tasks"
    source = _write_legacy(
        tasks_dir,
        [
            _task(
                "t001",
                "Complex relative links",
                description=COMPLEX_RELATIVE_LINK_DESCRIPTION,
            )
        ],
    )
    before = source.read_bytes()

    plan = migrate.plan_migration(tasks_dir, today=TODAY)

    reasons = "\n".join(plan.refusals)
    assert "t001" in reasons
    for destination in COMPLEX_RELATIVE_DESTINATIONS:
        assert destination in reasons
    assert "escaped-literal.md" not in reasons
    assert "escaped-reference.md" not in reasons
    assert source.read_bytes() == before
    assert not (tasks_dir / "active").exists()
    assert not (tasks_dir / "done").exists()
    assert not (tasks_dir / JOURNAL).exists()


@pytest.mark.parametrize("status", ["active", "done"])
def test_apply_refuses_relative_markdown_destination_and_preserves_source(
    tmp_path: Path,
    status: str,
) -> None:
    migrate = _migrate_module()
    tasks_dir = tmp_path / "tasks"
    source = _write_legacy(
        tasks_dir,
        [
            _task(
                "t001",
                "Relative link",
                status=status,
                description="See [guide](guide.md).",
            )
        ],
    )
    before = source.read_bytes()

    with pytest.raises(
        migrate.MigrationRefused,
        match=r"t001.*relative Markdown destination.*guide\.md",
    ):
        migrate.apply_migration(tasks_dir, today=TODAY)

    assert source.read_bytes() == before
    assert not (tasks_dir / "active").exists()
    assert not (tasks_dir / "done").exists()
    assert not (tasks_dir / JOURNAL).exists()


def test_apply_refuses_complex_relative_markdown_destinations_and_preserves_source(
    tmp_path: Path,
) -> None:
    migrate = _migrate_module()
    tasks_dir = tmp_path / "tasks"
    source = _write_legacy(
        tasks_dir,
        [
            _task(
                "t001",
                "Complex relative links",
                description=COMPLEX_RELATIVE_LINK_DESCRIPTION,
            )
        ],
    )
    before = source.read_bytes()

    with pytest.raises(
        migrate.MigrationRefused,
        match=r"t001.*relative Markdown destination.*nested\.md",
    ) as exc_info:
        migrate.apply_migration(tasks_dir, today=TODAY)

    message = str(exc_info.value)
    for destination in COMPLEX_RELATIVE_DESTINATIONS:
        assert destination in message
    assert "escaped-literal.md" not in message
    assert "escaped-reference.md" not in message
    assert source.read_bytes() == before
    assert not (tasks_dir / "active").exists()
    assert not (tasks_dir / "done").exists()
    assert not (tasks_dir / JOURNAL).exists()


def test_plan_refuses_malformed_task_heading_instead_of_treating_source_as_empty(
    tmp_path: Path,
) -> None:
    migrate = _migrate_module()
    tasks_dir = tmp_path / "tasks"
    source = _write_raw_legacy(
        tasks_dir,
        "## [t001]\n"
        "- priority: P1\n"
        "- status: active\n"
        "- aspects: []\n"
        "- created: 2026-07-01\n\n"
        "Body.\n",
    )
    before = source.read_bytes()

    plan = migrate.plan_migration(tasks_dir, today=TODAY)

    assert any("malformed task heading" in reason for reason in plan.refusals)
    assert plan.post_images == {}
    assert source.read_bytes() == before


def test_apply_refuses_malformed_task_heading_without_deleting_source(
    tmp_path: Path,
) -> None:
    migrate = _migrate_module()
    tasks_dir = tmp_path / "tasks"
    source = _write_raw_legacy(
        tasks_dir,
        "## [t001]\n"
        "- priority: P1\n"
        "- status: active\n"
        "- aspects: []\n"
        "- created: 2026-07-01\n\n"
        "Body.\n",
    )
    before = source.read_bytes()

    with pytest.raises(migrate.MigrationRefused, match="malformed task heading"):
        migrate.apply_migration(tasks_dir, today=TODAY)

    assert source.read_bytes() == before
    assert not (tasks_dir / JOURNAL).exists()


def test_plan_refuses_nonempty_active_dir_and_existing_open_target(tmp_path: Path) -> None:
    migrate = _migrate_module()
    tasks_dir = tmp_path / "tasks"
    _write_legacy(tasks_dir, [_task("t001", "Open analysis")])
    target = tasks_dir / "active" / "t001-open-analysis.md"
    target.parent.mkdir()
    target.write_text("hand-written split copy\n", encoding="utf-8")

    plan = migrate.plan_migration(tasks_dir, today=TODAY)

    reasons = "\n".join(plan.refusals)
    assert "active/" in reasons and "non-empty" in reasons
    assert "active/t001-open-analysis.md" in reasons and "already exists" in reasons
    with pytest.raises(migrate.MigrationRefused):
        migrate.apply_migration(tasks_dir, today=TODAY)
    assert target.read_text(encoding="utf-8") == "hand-written split copy\n"
    assert not (tasks_dir / JOURNAL).exists()


def test_plan_refuses_unknown_status_and_lists_id_and_status(tmp_path: Path) -> None:
    migrate = _migrate_module()
    tasks_dir = tmp_path / "tasks"
    _write_legacy(tasks_dir, [_task("t009", "Unknown state", status="paused")])

    plan = migrate.plan_migration(tasks_dir, today=TODAY)

    assert any("t009" in reason and "paused" in reason for reason in plan.refusals)
    assert plan.post_images == {}
    with pytest.raises(migrate.MigrationRefused, match="paused"):
        migrate.apply_migration(tasks_dir, today=TODAY)
    assert (tasks_dir / "active.md").is_file()


def test_plan_refuses_open_id_already_present_in_done_store(tmp_path: Path) -> None:
    migrate = _migrate_module()
    tasks_dir = tmp_path / "tasks"
    _write_legacy(tasks_dir, [_task("t020", "Reused open id")])
    done = tasks_dir / "done" / "2026-06.md"
    done.parent.mkdir()
    done.write_text(
        render_task(
            _task(
                "t020",
                "Earlier terminal task",
                status="done",
                completed=date(2026, 6, 2),
            )
        ),
        encoding="utf-8",
    )

    plan = migrate.plan_migration(tasks_dir, today=TODAY)

    assert any("t020" in reason and "done" in reason for reason in plan.refusals)


def test_apply_routes_open_and_terminal_tasks_then_deletes_source_last(tmp_path: Path) -> None:
    migrate = _migrate_module()
    tasks_dir = tmp_path / "tasks"
    open_task = _task(
        "t001",
        "Open analysis",
        project="demo",
        artifacts=["results/table.csv"],
        findings=["finding:f001"],
    )
    completed = _task(
        "t002",
        "Completed analysis",
        status="done",
        completed=date(2026, 6, 3),
    )
    retired = _task("t003", "Retired analysis", status="retired")
    _write_legacy(tasks_dir, [open_task, completed, retired])

    plan = migrate.apply_migration(tasks_dir, today=TODAY)

    assert plan.refusals == []
    assert not (tasks_dir / "active.md").exists()
    assert not (tasks_dir / JOURNAL).exists()
    assert parse_task_file(tasks_dir / "active" / "t001-open-analysis.md") == open_task
    assert [task.id for task in parse_tasks(tasks_dir / "done" / "2026-06.md")] == ["t002"]
    assert [task.id for task in parse_tasks(tasks_dir / "done" / "2026-07.md")] == ["t003"]


def test_apply_deduplicates_undated_terminal_task_across_all_done_months(tmp_path: Path) -> None:
    migrate = _migrate_module()
    tasks_dir = tmp_path / "tasks"
    terminal = _task("t010", "Already archived", status="retired")
    _write_legacy(tasks_dir, [terminal])
    previous = tasks_dir / "done" / "2026-06.md"
    previous.parent.mkdir()
    previous.write_text(render_task(terminal), encoding="utf-8")

    migrate.apply_migration(tasks_dir, today=TODAY)

    assert [task.id for task in parse_tasks(previous)] == ["t010"]
    assert not (tasks_dir / "done" / "2026-07.md").exists()
    assert not (tasks_dir / "active.md").exists()


@pytest.mark.parametrize("symlink_kind", ["done-directory", "ledger-file"])
def test_apply_refuses_out_of_store_done_ledger_even_when_task_is_structurally_equal(
    tmp_path: Path,
    symlink_kind: str,
) -> None:
    migrate = _migrate_module()
    tasks_dir = tmp_path / "tasks"
    terminal = _task(
        "t010",
        "Already archived",
        status="done",
        completed=date(2026, 6, 2),
    )
    source = _write_legacy(tasks_dir, [terminal])
    outside_dir = tmp_path / "outside-done"
    outside_dir.mkdir()
    outside_ledger = outside_dir / "2026-06.md"
    outside_ledger.write_text(render_task(terminal), encoding="utf-8")
    before = outside_ledger.read_bytes()

    if symlink_kind == "done-directory":
        (tasks_dir / "done").symlink_to(outside_dir, target_is_directory=True)
    else:
        done_dir = tasks_dir / "done"
        done_dir.mkdir()
        (done_dir / "2026-06.md").symlink_to(outside_ledger)

    plan = migrate.plan_migration(tasks_dir, today=TODAY)

    assert any("symlink" in reason and "done" in reason for reason in plan.refusals)
    with pytest.raises(migrate.MigrationRefused, match="symlink"):
        migrate.apply_migration(tasks_dir, today=TODAY)
    assert source.is_file()
    assert outside_ledger.read_bytes() == before
    assert not (tasks_dir / JOURNAL).exists()
    assert not (tasks_dir / ".tasks.lock").exists()


def test_apply_rejects_symlinked_lock_without_mutating_outside_file(
    tmp_path: Path,
) -> None:
    migrate = _migrate_module()
    tasks_dir = tmp_path / "tasks"
    source = _write_legacy(tasks_dir, [_task("t001", "Open analysis")])
    outside = tmp_path / "outside-lock"
    outside.write_text("do not truncate\n", encoding="utf-8")
    before = outside.read_bytes()
    (tasks_dir / ".tasks.lock").symlink_to(outside)

    with pytest.raises(migrate.MigrationRefused, match="symlink"):
        migrate.apply_migration(tasks_dir, today=TODAY)

    assert outside.read_bytes() == before
    assert source.is_file()
    assert not (tasks_dir / JOURNAL).exists()


def test_task_allocation_lock_itself_uses_no_follow_and_does_not_truncate_symlink(
    tmp_path: Path,
) -> None:
    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir()
    outside = tmp_path / "outside-lock"
    outside.write_text("do not truncate\n", encoding="utf-8")
    before = outside.read_bytes()
    (tasks_dir / ".tasks.lock").symlink_to(outside)

    with pytest.raises(ValueError, match="safely|symlink"):
        with task_module._task_allocation_lock(tasks_dir):
            pytest.fail("symlinked allocation lock must never be acquired")

    assert outside.read_bytes() == before


def test_apply_rejects_symlinked_journal_temp_without_mutating_outside_file(
    tmp_path: Path,
) -> None:
    migrate = _migrate_module()
    tasks_dir = tmp_path / "tasks"
    source = _write_legacy(tasks_dir, [_task("t001", "Open analysis")])
    outside = tmp_path / "outside-journal"
    outside.write_text("do not overwrite\n", encoding="utf-8")
    before = outside.read_bytes()
    journal = tasks_dir / JOURNAL
    journal.parent.mkdir()
    journal.with_suffix(journal.suffix + ".tmp").symlink_to(outside)

    with pytest.raises(migrate.MigrationRefused, match="symlink"):
        migrate.apply_migration(tasks_dir, today=TODAY)

    assert outside.read_bytes() == before
    assert source.is_file()
    assert not journal.exists()
    assert not (tasks_dir / ".tasks.lock").exists()


def test_apply_rejects_symlinked_destination_temp_without_mutating_outside_file(
    tmp_path: Path,
) -> None:
    migrate = _migrate_module()
    tasks_dir = tmp_path / "tasks"
    terminal = _task(
        "t001",
        "Completed analysis",
        status="done",
        completed=date(2026, 7, 2),
    )
    source = _write_legacy(tasks_dir, [terminal])
    outside = tmp_path / "outside-ledger"
    outside.write_text("do not overwrite\n", encoding="utf-8")
    before = outside.read_bytes()
    target = tasks_dir / "done" / "2026-07.md"
    target.parent.mkdir()
    target.with_suffix(target.suffix + ".tmp").symlink_to(outside)

    with pytest.raises(migrate.MigrationRefused, match="symlink"):
        migrate.apply_migration(tasks_dir, today=TODAY)

    assert outside.read_bytes() == before
    assert source.is_file()
    assert not (tasks_dir / JOURNAL).exists()
    assert not (tasks_dir / ".tasks.lock").exists()


def test_non_cwd_tasks_dir_preserves_same_month_ledger_preamble_and_tasks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    migrate = _migrate_module()
    tasks_dir = tmp_path / "nested" / "project" / "tasks"
    migrated = _task(
        "t001",
        "Newly completed",
        status="done",
        completed=date(2026, 7, 14),
    )
    existing = _task(
        "t099",
        "Existing completion",
        status="done",
        completed=date(2026, 7, 2),
    )
    _write_legacy(tasks_dir, [migrated])
    ledger = tasks_dir / "done" / "2026-07.md"
    ledger.parent.mkdir()
    preamble = "# July ledger\n\nPreserve this introduction byte-for-byte.\n\n"
    ledger.write_text(preamble + render_task(existing), encoding="utf-8")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)

    migrate.apply_migration(tasks_dir, today=TODAY)

    text = ledger.read_text(encoding="utf-8")
    assert text.startswith(preamble)
    assert [task.id for task in parse_tasks(ledger)] == ["t099", "t001"]
    assert not (tasks_dir / "tasks").exists()


def test_apply_rechecks_source_hash_before_deleting_and_retains_journal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    migrate = _migrate_module()
    tasks_dir = tmp_path / "tasks"
    source = _write_legacy(tasks_dir, [_task("t001", "Open analysis")])
    original_atomic_write = migrate.atomic_write_text
    changed = False

    def mutate_source_during_apply(path: Path, text: str) -> None:
        nonlocal changed
        original_atomic_write(path, text)
        if path != tasks_dir / JOURNAL and not changed:
            changed = True
            source.write_text(source.read_text(encoding="utf-8") + "\nConcurrent edit.\n", encoding="utf-8")

    monkeypatch.setattr(migrate, "atomic_write_text", mutate_source_during_apply)

    with pytest.raises(migrate.MigrationRefused, match="active.md changed"):
        migrate.apply_migration(tasks_dir, today=TODAY)

    assert source.read_text(encoding="utf-8").endswith("Concurrent edit.\n")
    assert (tasks_dir / JOURNAL).is_file()
    assert (tasks_dir / "active" / "t001-open-analysis.md").is_file()


def test_apply_plans_inside_one_allocation_lock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    migrate = _migrate_module()
    tasks_dir = tmp_path / "tasks"
    _write_legacy(tasks_dir, [_task("t001", "Open analysis")])
    original_lock = migrate._task_allocation_lock
    original_plan = migrate.plan_migration
    lock_depth = 0
    acquisitions = 0

    @contextmanager
    def tracked_lock(path: Path) -> Iterator[None]:
        nonlocal lock_depth, acquisitions
        acquisitions += 1
        with original_lock(path):
            lock_depth += 1
            try:
                yield
            finally:
                lock_depth -= 1

    def checked_plan(path: Path, *, today: date):
        assert lock_depth == 1
        return original_plan(path, today=today)

    monkeypatch.setattr(migrate, "_task_allocation_lock", tracked_lock)
    monkeypatch.setattr(migrate, "plan_migration", checked_plan)

    migrate.apply_migration(tasks_dir, today=TODAY)

    assert acquisitions == 1


def test_resume_writes_absent_postimage_without_replanning(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tasks_dir = tmp_path / "tasks"
    source = _write_legacy(tasks_dir, [_task("t001", "Open analysis")])
    migrate = _interrupt_before_first_postimage(tasks_dir, monkeypatch)

    def forbidden_replan(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("resume must never re-plan")

    monkeypatch.setattr(migrate, "plan_migration", forbidden_replan)

    result = migrate.resume_migration(tasks_dir)

    target = tasks_dir / "active" / "t001-open-analysis.md"
    assert result.written == [target]
    assert [entry.action for entry in result.entries] == ["written"]
    assert target.is_file()
    assert not source.exists()
    assert not (tasks_dir / JOURNAL).exists()


def test_resume_accepts_exact_postimage_without_rewriting_it(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tasks_dir = tmp_path / "tasks"
    _write_legacy(tasks_dir, [_task("t001", "Open analysis")])
    migrate = _interrupt_before_first_postimage(tasks_dir, monkeypatch)
    postimage = _postimages(_journal_payload(tasks_dir))[0]
    target = tasks_dir / postimage["path"]
    target.parent.mkdir(exist_ok=True)
    target.write_text(postimage["content"], encoding="utf-8")
    original_atomic_write = migrate.atomic_write_text
    writes: list[Path] = []

    def track_writes(path: Path, text: str) -> None:
        writes.append(path)
        original_atomic_write(path, text)

    monkeypatch.setattr(migrate, "atomic_write_text", track_writes)

    result = migrate.resume_migration(tasks_dir)

    assert result.written == []
    assert [entry.action for entry in result.entries] == ["already exact"]
    assert writes == []
    assert not (tasks_dir / "active.md").exists()
    assert not (tasks_dir / JOURNAL).exists()


def test_resume_refuses_different_postimage_and_retains_source_and_journal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tasks_dir = tmp_path / "tasks"
    source = _write_legacy(tasks_dir, [_task("t001", "Open analysis")])
    migrate = _interrupt_before_first_postimage(tasks_dir, monkeypatch)
    postimage = _postimages(_journal_payload(tasks_dir))[0]
    target = tasks_dir / postimage["path"]
    target.parent.mkdir(exist_ok=True)
    target.write_text("changed under migration\n", encoding="utf-8")

    with pytest.raises(migrate.MigrationRefused, match="different"):
        migrate.resume_migration(tasks_dir)

    assert target.read_text(encoding="utf-8") == "changed under migration\n"
    assert source.is_file()
    assert (tasks_dir / JOURNAL).is_file()


@pytest.mark.parametrize(
    ("ledger_state", "expected_written"),
    [
        ("absent", "done"),
        ("exact", "active"),
        ("different", None),
    ],
)
def test_resume_mixed_open_and_terminal_recovery_classifies_done_postimage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    ledger_state: str,
    expected_written: str | None,
) -> None:
    tasks_dir = tmp_path / "tasks"
    source = _write_legacy(
        tasks_dir,
        [
            _task("t001", "Open analysis"),
            _task(
                "t002",
                "Completed analysis",
                status="done",
                completed=date(2026, 7, 2),
            ),
        ],
    )
    migrate = _interrupt_before_first_postimage(tasks_dir, monkeypatch)
    postimages = {
        item["path"]: item["content"]
        for item in _postimages(_journal_payload(tasks_dir))
    }
    open_relative = next(path for path in postimages if path.startswith("active/"))
    done_relative = next(path for path in postimages if path.startswith("done/"))
    open_target = tasks_dir / open_relative
    done_target = tasks_dir / done_relative

    if ledger_state == "absent":
        open_target.parent.mkdir(exist_ok=True)
        open_target.write_text(postimages[open_relative], encoding="utf-8")
    elif ledger_state == "exact":
        done_target.parent.mkdir(exist_ok=True)
        done_target.write_text(postimages[done_relative], encoding="utf-8")
    else:
        open_target.parent.mkdir(exist_ok=True)
        open_target.write_text(postimages[open_relative], encoding="utf-8")
        done_target.parent.mkdir(exist_ok=True)
        done_target.write_text("different ledger\n", encoding="utf-8")

    if expected_written is None:
        with pytest.raises(migrate.MigrationRefused, match="different"):
            migrate.resume_migration(tasks_dir)
        assert source.is_file()
        assert (tasks_dir / JOURNAL).is_file()
        assert done_target.read_text(encoding="utf-8") == "different ledger\n"
        return

    result = migrate.resume_migration(tasks_dir)

    expected_target = done_target if expected_written == "done" else open_target
    assert result.written == [expected_target]
    assert open_target.read_text(encoding="utf-8") == postimages[open_relative]
    assert done_target.read_text(encoding="utf-8") == postimages[done_relative]
    assert not source.exists()
    assert not (tasks_dir / JOURNAL).exists()


def test_resume_refuses_changed_present_source_before_writing_targets(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tasks_dir = tmp_path / "tasks"
    source = _write_legacy(tasks_dir, [_task("t001", "Open analysis")])
    migrate = _interrupt_before_first_postimage(tasks_dir, monkeypatch)
    source.write_text(source.read_text(encoding="utf-8") + "\nInterruption-time edit.\n", encoding="utf-8")
    target = tasks_dir / "active" / "t001-open-analysis.md"

    with pytest.raises(migrate.MigrationRefused, match="active.md changed"):
        migrate.resume_migration(tasks_dir)

    assert not target.exists()
    assert source.read_text(encoding="utf-8").endswith("Interruption-time edit.\n")
    assert (tasks_dir / JOURNAL).is_file()


def test_resume_clears_journal_after_crash_following_source_delete(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    migrate = _migrate_module()
    tasks_dir = tmp_path / "tasks"
    _write_legacy(tasks_dir, [_task("t001", "Open analysis")])
    original_clear = migrate._clear_journal

    def crash_before_clear(_tasks_dir: Path) -> None:
        raise RuntimeError("simulated crash after source delete")

    monkeypatch.setattr(migrate, "_clear_journal", crash_before_clear)
    with pytest.raises(RuntimeError, match="after source delete"):
        migrate.apply_migration(tasks_dir, today=TODAY)
    monkeypatch.setattr(migrate, "_clear_journal", original_clear)

    assert not (tasks_dir / "active.md").exists()
    assert (tasks_dir / "active" / "t001-open-analysis.md").is_file()
    assert (tasks_dir / JOURNAL).is_file()

    result = migrate.resume_migration(tasks_dir)

    assert result.written == []
    assert not (tasks_dir / JOURNAL).exists()


@pytest.mark.parametrize(
    "unsafe_path",
    [
        "/tmp/science-migration-escaped.md",
        "../science-migration-escaped.md",
        "active/../../science-migration-escaped.md",
    ],
    ids=["absolute", "parent", "nested-parent"],
)
def test_resume_rejects_untrusted_journal_paths_before_any_target_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    unsafe_path: str,
) -> None:
    tasks_dir = tmp_path / "tasks"
    _write_legacy(
        tasks_dir,
        [
            _task("t001", "First open task"),
            _task("t002", "Second open task"),
        ],
    )
    migrate = _interrupt_before_first_postimage(tasks_dir, monkeypatch)
    payload = _journal_payload(tasks_dir)
    postimages = _postimages(payload)
    first_safe_path = tasks_dir / postimages[0]["path"]
    postimages[1]["path"] = unsafe_path
    postimages[1]["content"] = "escaped\n"
    _write_journal_payload(tasks_dir, payload)
    escaped = Path(unsafe_path) if Path(unsafe_path).is_absolute() else tasks_dir / unsafe_path
    escaped_parent = escaped.parent
    if escaped_parent == tmp_path:
        escaped.unlink(missing_ok=True)

    with pytest.raises(migrate.MigrationRefused, match="unsafe journal path"):
        migrate.resume_migration(tasks_dir)

    assert not first_safe_path.exists()
    assert not escaped.exists()
    assert (tasks_dir / "active.md").is_file()
    assert (tasks_dir / JOURNAL).is_file()


def test_resume_refuses_journal_target_outside_active_or_done_namespaces(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tasks_dir = tmp_path / "tasks"
    _write_legacy(tasks_dir, [_task("t001", "Open analysis")])
    migrate = _interrupt_before_first_postimage(tasks_dir, monkeypatch)
    payload = _journal_payload(tasks_dir)
    _postimages(payload)[0]["path"] = ".science/other-state.json"
    _write_journal_payload(tasks_dir, payload)

    with pytest.raises(migrate.MigrationRefused, match="unsafe journal path"):
        migrate.resume_migration(tasks_dir)

    assert not (tasks_dir / ".science" / "other-state.json").exists()
    assert (tasks_dir / JOURNAL).is_file()


@pytest.mark.parametrize(
    "unsafe_path",
    ["active", "done", "active/not-markdown.txt", "done/nested/2026-07.md"],
)
def test_resume_rejects_non_file_shaped_journal_targets(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    unsafe_path: str,
) -> None:
    tasks_dir = tmp_path / "tasks"
    _write_legacy(tasks_dir, [_task("t001", "Open analysis")])
    migrate = _interrupt_before_first_postimage(tasks_dir, monkeypatch)
    payload = _journal_payload(tasks_dir)
    _postimages(payload)[0]["path"] = unsafe_path
    _write_journal_payload(tasks_dir, payload)

    with pytest.raises(migrate.MigrationRefused, match="unsafe journal path"):
        migrate.resume_migration(tasks_dir)

    assert (tasks_dir / "active.md").is_file()
    assert (tasks_dir / JOURNAL).is_file()


def _write_split(tasks_dir: Path) -> None:
    active = tasks_dir / "active"
    active.mkdir(parents=True, exist_ok=True)
    task = _task("t100", "Split task")
    (active / "t100-split-task.md").write_text(task_module.render_task_file(task), encoding="utf-8")


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        ("empty", "nothing to do"),
        ("split", "already split"),
        ("migrating", MIGRATING_REFUSAL),
        ("conflict", CONFLICT_REFUSAL),
    ],
)
def test_cli_apply_is_valid_only_in_legacy_state(
    tmp_path: Path,
    state: str,
    expected: str,
) -> None:
    tasks_dir = tmp_path / "tasks"
    if state == "split":
        _write_split(tasks_dir)
    elif state == "migrating":
        _write_legacy(tasks_dir, [_task("t001", "Legacy task")])
        journal = tasks_dir / JOURNAL
        journal.parent.mkdir()
        journal.write_text("{}\n", encoding="utf-8")
    elif state == "conflict":
        _write_legacy(tasks_dir, [_task("t001", "Legacy task")])
        _write_split(tasks_dir)

    result = CliRunner().invoke(
        main,
        ["tasks", "migrate-storage", "--apply", "--tasks-dir", str(tasks_dir)],
    )

    assert result.exit_code != 0
    assert expected in result.output


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        ("empty", "nothing to resume"),
        ("split", "nothing to resume"),
        ("legacy", "--apply"),
        ("conflict", CONFLICT_REFUSAL),
    ],
)
def test_cli_resume_is_valid_only_in_migrating_state(
    tmp_path: Path,
    state: str,
    expected: str,
) -> None:
    tasks_dir = tmp_path / "tasks"
    if state == "split":
        _write_split(tasks_dir)
    elif state == "legacy":
        _write_legacy(tasks_dir, [_task("t001", "Legacy task")])
    elif state == "conflict":
        _write_legacy(tasks_dir, [_task("t001", "Legacy task")])
        _write_split(tasks_dir)

    result = CliRunner().invoke(
        main,
        ["tasks", "migrate-storage", "--resume", "--tasks-dir", str(tasks_dir)],
    )

    assert result.exit_code != 0
    assert expected in result.output


def test_cli_apply_and_resume_are_mutually_exclusive(tmp_path: Path) -> None:
    tasks_dir = tmp_path / "tasks"
    _write_legacy(tasks_dir, [_task("t001", "Legacy task")])

    result = CliRunner().invoke(
        main,
        [
            "tasks",
            "migrate-storage",
            "--apply",
            "--resume",
            "--tasks-dir",
            str(tasks_dir),
        ],
    )

    assert result.exit_code == 2
    assert "--apply and --resume are mutually exclusive" in result.output


@pytest.mark.parametrize(
    "output_relative",
    ["active.md", ".science/task-storage-migration.journal", ".tasks.lock", "active/report.json", "done/report.json"],
)
def test_cli_mutation_output_cannot_overlap_transaction_storage(
    tmp_path: Path,
    output_relative: str,
) -> None:
    tasks_dir = tmp_path / "tasks"
    source = _write_legacy(tasks_dir, [_task("t001", "Legacy task")])
    output = tasks_dir / output_relative

    result = CliRunner().invoke(
        main,
        [
            "tasks",
            "migrate-storage",
            "--apply",
            "--tasks-dir",
            str(tasks_dir),
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 2
    assert "overlaps transaction-owned task storage" in result.output
    assert source.is_file()
    assert not (tasks_dir / JOURNAL).exists()


def test_cli_apply_and_resume_succeed_in_their_valid_states(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    apply_dir = tmp_path / "apply" / "tasks"
    _write_legacy(apply_dir, [_task("t001", "Apply task")])

    applied = CliRunner().invoke(
        main,
        ["tasks", "migrate-storage", "--apply", "--tasks-dir", str(apply_dir)],
    )

    assert applied.exit_code == 0, applied.output
    assert "Migrated 1 task" in applied.output
    assert not (apply_dir / "active.md").exists()

    resume_dir = tmp_path / "resume" / "tasks"
    _write_legacy(resume_dir, [_task("t002", "Resume task")])
    _interrupt_before_first_postimage(resume_dir, monkeypatch)

    resumed = CliRunner().invoke(
        main,
        ["tasks", "migrate-storage", "--resume", "--tasks-dir", str(resume_dir)],
    )

    assert resumed.exit_code == 0, resumed.output
    assert "Resumed storage migration" in resumed.output
    assert not (resume_dir / JOURNAL).exists()


def test_cli_dry_run_table_and_json_report_every_source_task(tmp_path: Path) -> None:
    tasks_dir = tmp_path / "tasks"
    _write_legacy(
        tasks_dir,
        [
            _task("t001", "Open task"),
            _task("t002", "Done task", status="done", completed=date(2026, 7, 2)),
        ],
    )

    table = CliRunner().invoke(
        main,
        ["tasks", "migrate-storage", "--tasks-dir", str(tasks_dir)],
    )
    json_result = CliRunner().invoke(
        main,
        [
            "tasks",
            "migrate-storage",
            "--tasks-dir",
            str(tasks_dir),
            "--format",
            "json",
        ],
    )

    assert table.exit_code == 0, table.output
    assert "Task Storage Migration Plan" in table.output
    assert "t001" in table.output
    assert "active/t001-open-task.md" in table.output
    assert "done/2026-07.md" in table.output
    payload = json.loads(json_result.output)
    assert [row["id"] for row in payload["rows"]] == ["t001", "t002"]
    assert "truncation" not in payload
    assert (tasks_dir / "active.md").is_file()


def test_cli_dry_run_stdout_is_bounded_and_output_file_is_complete(tmp_path: Path) -> None:
    tasks_dir = tmp_path / "nested" / "tasks"
    source_tasks = [
        _task(
            f"t{index:03d}",
            f"Migration task {index} with a deliberately descriptive title",
            description=f"Long source task body {index}.",
        )
        for index in range(1, 61)
    ]
    _write_legacy(tasks_dir, source_tasks)
    target = tmp_path / "migration-plan.json"

    table = CliRunner().invoke(
        main,
        ["tasks", "migrate-storage", "--tasks-dir", str(tasks_dir)],
    )
    written = CliRunner().invoke(
        main,
        [
            "tasks",
            "migrate-storage",
            "--tasks-dir",
            str(tasks_dir),
            "--format",
            "json",
            "--output",
            str(target),
        ],
    )

    assert table.exit_code == 0, table.output
    assert visible_len(table.output) <= BUDGETS["tasks migrate-storage"].max_chars
    assert "showing 40 of 60 rows" in table.output
    assert "complete output:" in table.output
    assert "tasks-migrate-storage.txt" in table.output
    assert written.exit_code == 0, written.output
    assert written.output.count("\n") == 1
    assert "wrote 60 migration-plan rows to" in written.output
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert len(payload["rows"]) == 60
    assert {row["id"] for row in payload["rows"]} == {task.id for task in source_tasks}
    assert "truncation" not in payload


def test_cli_many_task_apply_has_fixed_stdout_and_complete_reserved_output(
    tmp_path: Path,
) -> None:
    source_tasks = [
        _task(f"t{index:03d}", f"Apply migration task {index}")
        for index in range(1, 61)
    ]
    stdout_dir = tmp_path / "stdout" / "tasks"
    output_dir = tmp_path / "output" / "tasks"
    _write_legacy(stdout_dir, source_tasks)
    _write_legacy(output_dir, source_tasks)
    target = tmp_path / "applied.json"

    stdout_result = CliRunner().invoke(
        main,
        ["tasks", "migrate-storage", "--apply", "--tasks-dir", str(stdout_dir)],
    )
    output_result = CliRunner().invoke(
        main,
        [
            "tasks",
            "migrate-storage",
            "--apply",
            "--tasks-dir",
            str(output_dir),
            "--format",
            "json",
            "--output",
            str(target),
        ],
    )

    assert stdout_result.exit_code == 0, stdout_result.output
    assert "Migrated 60 task(s)." in stdout_result.output
    assert "showing" not in stdout_result.output
    assert "complete output:" not in stdout_result.output
    assert "--apply" not in stdout_result.output
    assert output_result.exit_code == 0, output_result.output
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert len(payload["rows"]) == 60
    assert {row["id"] for row in payload["rows"]} == {task.id for task in source_tasks}
    assert "truncation" not in payload


def test_cli_many_target_resume_has_fixed_stdout_and_complete_reserved_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_tasks = [
        _task(f"t{index:03d}", f"Resume migration task {index}")
        for index in range(1, 61)
    ]
    stdout_dir = tmp_path / "stdout" / "tasks"
    output_dir = tmp_path / "output" / "tasks"
    _write_legacy(stdout_dir, source_tasks)
    _write_legacy(output_dir, source_tasks)
    _interrupt_before_first_postimage(stdout_dir, monkeypatch)
    _interrupt_before_first_postimage(output_dir, monkeypatch)
    target = tmp_path / "resumed.json"

    stdout_result = CliRunner().invoke(
        main,
        ["tasks", "migrate-storage", "--resume", "--tasks-dir", str(stdout_dir)],
    )
    output_result = CliRunner().invoke(
        main,
        [
            "tasks",
            "migrate-storage",
            "--resume",
            "--tasks-dir",
            str(output_dir),
            "--format",
            "json",
            "--output",
            str(target),
        ],
    )

    assert stdout_result.exit_code == 0, stdout_result.output
    assert "Resumed storage migration" in stdout_result.output
    assert "showing" not in stdout_result.output
    assert "complete output:" not in stdout_result.output
    assert "--resume" not in stdout_result.output
    assert output_result.exit_code == 0, output_result.output
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert len(payload["rows"]) == 60
    assert {row["action"] for row in payload["rows"]} == {"written"}
    assert "truncation" not in payload


def test_cli_refused_dry_run_is_bounded_and_output_file_keeps_all_refusals(
    tmp_path: Path,
) -> None:
    tasks_dir = tmp_path / "tasks"
    source_tasks = [
        _task(
            f"t{index:03d}",
            f"Invalid migration task {index}",
            status=f"unknown-status-{index:03d}",
        )
        for index in range(1, 61)
    ]
    _write_legacy(tasks_dir, source_tasks)
    target = tmp_path / "refused-plan.json"

    table = CliRunner().invoke(
        main,
        ["tasks", "migrate-storage", "--tasks-dir", str(tasks_dir)],
    )
    written = CliRunner().invoke(
        main,
        [
            "tasks",
            "migrate-storage",
            "--tasks-dir",
            str(tasks_dir),
            "--format",
            "json",
            "--output",
            str(target),
        ],
    )

    assert table.exit_code == 1
    assert visible_len(table.output) <= BUDGETS["tasks migrate-storage"].max_chars
    assert "complete output:" in table.output
    assert written.exit_code == 1
    assert written.output.count("\n") == 1
    payload = json.loads(target.read_text(encoding="utf-8"))
    refusal_rows = [row for row in payload["rows"] if row["status"] == "refusal"]
    assert len(refusal_rows) == 60
    assert all("unknown status" in row["action"] for row in refusal_rows)
    assert "truncation" not in payload


def test_cli_refused_apply_is_bounded_and_output_file_keeps_all_refusals(
    tmp_path: Path,
) -> None:
    tasks_dir = tmp_path / "tasks"
    _write_legacy(
        tasks_dir,
        [
            _task(
                f"t{index:03d}",
                f"Invalid apply task {index}",
                status=f"unknown-status-{index:03d}",
            )
            for index in range(1, 61)
        ],
    )
    target = tmp_path / "refused-apply.json"

    table = CliRunner().invoke(
        main,
        ["tasks", "migrate-storage", "--apply", "--tasks-dir", str(tasks_dir)],
    )
    written = CliRunner().invoke(
        main,
        [
            "tasks",
            "migrate-storage",
            "--apply",
            "--tasks-dir",
            str(tasks_dir),
            "--format",
            "json",
            "--output",
            str(target),
        ],
    )

    assert table.exit_code == 1
    assert visible_len(table.output) <= BUDGETS["tasks migrate-storage"].max_chars
    assert "complete output:" in table.output
    assert written.exit_code == 1
    payload = json.loads(target.read_text(encoding="utf-8"))
    refusal_rows = [row for row in payload["rows"] if row["status"] == "refusal"]
    assert len(refusal_rows) >= 60
    assert all("unknown status" in row["action"] for row in refusal_rows[-60:])
    assert (tasks_dir / "active.md").is_file()
    assert not (tasks_dir / JOURNAL).exists()


def test_migrate_storage_budget_uses_spaced_click_command_path() -> None:
    budget = lookup("tasks migrate-storage")

    assert budget is not None
    assert budget.max_chars == 20_000
    assert budget.max_rows == 40
    assert budget.shape is PayloadShape.ROWS
    assert lookup("tasks-migrate-storage") is None

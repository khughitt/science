"""Storage-layout classification and normal-command gating."""

from datetime import date
from pathlib import Path

import pytest
from click.testing import CliRunner

from science_tool import tasks as task_module
from science_tool.cli import main


_LEGACY_MESSAGE = (
    "tasks/active.md predates the storage split; "
    "run `science tasks migrate-storage --apply`."
)
_MIGRATING_MESSAGE = (
    "an interrupted storage migration is in progress; "
    "run `science tasks migrate-storage --resume`."
)
_CONFLICT_MESSAGE = (
    "both tasks/active.md and tasks/active/ exist with no migration journal; "
    "inspect and remove one by hand — this is not an auto-resumable migration."
)


def _write_legacy(tasks_dir: Path) -> None:
    tasks_dir.mkdir(parents=True, exist_ok=True)
    (tasks_dir / "active.md").write_text(
        "## [t001] Legacy task\n"
        "- priority: P1\n"
        "- status: active\n"
        "- aspects: []\n"
        "- created: 2026-07-20\n"
        "\n"
        "Legacy details.\n",
        encoding="utf-8",
    )


def _write_split_marker(tasks_dir: Path) -> None:
    active = tasks_dir / "active"
    active.mkdir(parents=True, exist_ok=True)
    (active / "t001-task.md").write_text("---\nid: t001\n---\n", encoding="utf-8")


@pytest.mark.parametrize("make_empty_dir", [False, True], ids=["absent-active-dir", "empty-active-dir"])
def test_empty_store_allows_split_commands(tmp_path: Path, make_empty_dir: bool) -> None:
    tasks_dir = tmp_path / "tasks"
    if make_empty_dir:
        (tasks_dir / "active").mkdir(parents=True)

    assert task_module._tasks_storage_state(tasks_dir) is task_module.StorageState.EMPTY
    task_module._require_split(tasks_dir)


def test_split_store_allows_split_commands(tmp_path: Path) -> None:
    tasks_dir = tmp_path / "tasks"
    _write_split_marker(tasks_dir)

    assert task_module._tasks_storage_state(tasks_dir) is task_module.StorageState.SPLIT
    task_module._require_split(tasks_dir)


@pytest.mark.parametrize("make_empty_dir", [False, True], ids=["absent-active-dir", "empty-active-dir"])
def test_legacy_store_requires_apply(tmp_path: Path, make_empty_dir: bool) -> None:
    tasks_dir = tmp_path / "tasks"
    _write_legacy(tasks_dir)
    if make_empty_dir:
        (tasks_dir / "active").mkdir()

    assert task_module._tasks_storage_state(tasks_dir) is task_module.StorageState.LEGACY
    with pytest.raises(ValueError, match="predates the storage split") as excinfo:
        task_module._require_split(tasks_dir)

    assert str(excinfo.value) == _LEGACY_MESSAGE


def test_journal_presence_is_authoritative_and_requires_resume(tmp_path: Path) -> None:
    tasks_dir = tmp_path / "tasks"
    _write_legacy(tasks_dir)
    _write_split_marker(tasks_dir)
    journal = tasks_dir / ".science" / "task-storage-migration.journal"
    journal.parent.mkdir()
    journal.touch()

    assert task_module._tasks_storage_state(tasks_dir) is task_module.StorageState.MIGRATING
    with pytest.raises(ValueError, match="interrupted storage migration") as excinfo:
        task_module._require_split(tasks_dir)

    assert str(excinfo.value) == _MIGRATING_MESSAGE


def test_populated_legacy_and_split_layouts_require_manual_resolution(tmp_path: Path) -> None:
    tasks_dir = tmp_path / "tasks"
    _write_legacy(tasks_dir)
    _write_split_marker(tasks_dir)

    assert task_module._tasks_storage_state(tasks_dir) is task_module.StorageState.CONFLICT
    with pytest.raises(ValueError, match="not an auto-resumable migration") as excinfo:
        task_module._require_split(tasks_dir)

    assert str(excinfo.value) == _CONFLICT_MESSAGE


def test_read_active_gates_by_default_but_allows_explicit_read_only_bypass(tmp_path: Path) -> None:
    tasks_dir = tmp_path / "tasks"
    _write_legacy(tasks_dir)

    with pytest.raises(ValueError, match="migrate-storage --apply"):
        task_module._read_active(tasks_dir)

    assert task_module._read_active(tasks_dir, require_split=False) == []


def test_find_task_location_gates_before_done_lookup_but_allows_explicit_bypass(tmp_path: Path) -> None:
    tasks_dir = tmp_path / "tasks"
    _write_legacy(tasks_dir)
    done = tasks_dir / "done" / "2026-07.md"
    done.parent.mkdir()
    done.write_text(
        "## [t002] Done task\n"
        "- priority: P1\n"
        "- status: done\n"
        "- aspects: []\n"
        "- created: 2026-07-20\n"
        "- completed: 2026-07-21\n"
        "\n"
        "Done details.\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="migrate-storage --apply"):
        task_module.find_task_location(tasks_dir, "t002")

    location = task_module.find_task_location(tasks_dir, "t002", require_split=False)
    assert location.task.id == "t002"
    assert location.path == done


def test_since_candidate_read_is_explicitly_gate_exempt(tmp_path: Path) -> None:
    tasks_dir = tmp_path / "tasks"
    _write_legacy(tasks_dir)
    today = date.today()
    done = tasks_dir / "done" / f"{today:%Y-%m}.md"
    done.parent.mkdir()
    done.write_text(
        "## [t002] Done task\n"
        "- priority: P1\n"
        "- status: done\n"
        "- aspects: []\n"
        f"- created: {today.isoformat()}\n"
        f"- completed: {today.isoformat()}\n"
        "\n"
        "Done details.\n",
        encoding="utf-8",
    )

    candidates = task_module._read_since_candidates(tasks_dir, today)

    assert [task.id for task in candidates] == ["t002"]


def test_list_gates_malformed_legacy_store_before_parsing_it(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    tasks_dir = Path("tasks")
    tasks_dir.mkdir()
    (tasks_dir / "active.md").write_text(
        "## [t001] Malformed legacy task\n"
        "- priority: P1\n"
        "- status: active\n"
        "- aspects: [\n"
        "- created: 2026-07-20\n",
        encoding="utf-8",
    )

    result = CliRunner().invoke(main, ["tasks", "list"])

    assert result.exit_code != 0
    assert _LEGACY_MESSAGE in result.output


@pytest.mark.parametrize(
    "args",
    [
        ["tasks", "show", "t002"],
        ["tasks", "list"],
        ["tasks", "summary"],
        ["tasks", "edit", "t002", "--priority", "P0"],
    ],
    ids=["show", "list", "summary", "edit"],
)
def test_normal_cli_commands_surface_legacy_migration_guidance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    args: list[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    tasks_dir = Path("tasks")
    _write_legacy(tasks_dir)
    done = tasks_dir / "done" / "2026-07.md"
    done.parent.mkdir()
    done.write_text(
        "## [t002] Done task\n"
        "- priority: P1\n"
        "- status: done\n"
        "- aspects: []\n"
        "- created: 2026-07-20\n"
        "- completed: 2026-07-21\n"
        "\n"
        "Done details.\n",
        encoding="utf-8",
    )

    result = CliRunner().invoke(main, args)

    assert result.exit_code != 0
    assert _LEGACY_MESSAGE in result.output
    assert "not found" not in result.output.lower()
    assert "Done task" not in result.output

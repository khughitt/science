"""Atomic exactly-one-file writers for canonical open tasks."""

import os
from datetime import date
from pathlib import Path

import pytest
from science_model.tasks import Task
from science_tool import tasks as task_module


def _task(*, title: str = "First title", description: str = "body") -> Task:
    return Task(
        id="t042",
        title=title,
        status="active",
        priority="P1",
        aspects=[],
        created=date(2026, 7, 20),
        description=description,
    )


def test_write_task_file_creates_slugged_file(tmp_path: Path) -> None:
    tasks_dir = tmp_path / "tasks"
    task = _task()

    task_module.write_task_file(tasks_dir, task)

    path = tasks_dir / "active" / "t042-first-title.md"
    assert path.is_file()
    assert task_module.parse_task_file(path) == task


def test_write_task_file_updates_same_slug_in_place(tmp_path: Path) -> None:
    tasks_dir = tmp_path / "tasks"
    task_module.write_task_file(tasks_dir, _task())
    updated = _task(description="updated body")

    task_module.write_task_file(tasks_dir, updated)

    files = list((tasks_dir / "active").glob("t042*.md"))
    assert files == [tasks_dir / "active" / "t042-first-title.md"]
    assert task_module.parse_task_file(files[0]) == updated


def test_title_change_renames_atomically(tmp_path: Path) -> None:
    tasks_dir = tmp_path / "tasks"
    task_module.write_task_file(tasks_dir, _task())
    renamed = _task(title="Second title")

    task_module.write_task_file(tasks_dir, renamed)

    files = list((tasks_dir / "active").glob("t042*.md"))
    assert files == [tasks_dir / "active" / "t042-second-title.md"]
    assert task_module.parse_task_file(files[0]) == renamed


def test_write_task_file_rejects_duplicate_id_paths_without_mutation(tmp_path: Path) -> None:
    active = tmp_path / "tasks" / "active"
    active.mkdir(parents=True)
    (active / "t042-first.md").write_text("first", encoding="utf-8")
    (active / "t042-second.md").write_text("second", encoding="utf-8")

    with pytest.raises(ValueError, match="duplicate.*t042"):
        task_module.write_task_file(tmp_path / "tasks", _task())

    assert (active / "t042-first.md").read_text(encoding="utf-8") == "first"
    assert (active / "t042-second.md").read_text(encoding="utf-8") == "second"


def test_write_task_file_rejects_existing_filename_frontmatter_mismatch_without_mutation(
    tmp_path: Path,
) -> None:
    tasks_dir = tmp_path / "tasks"
    active = tasks_dir / "active"
    active.mkdir(parents=True)
    malformed = active / "t042-old.md"
    malformed.write_text(
        task_module.render_task_file(_task().model_copy(update={"id": "t041"})),
        encoding="utf-8",
    )
    before = malformed.read_bytes()

    with pytest.raises(ValueError, match=r"filename does not match id 't041'"):
        task_module.write_task_file(tasks_dir, _task(title="Replacement"))

    assert malformed.read_bytes() == before
    assert list(active.glob("*.md")) == [malformed]


def test_delete_task_file_removes_single_file(tmp_path: Path) -> None:
    tasks_dir = tmp_path / "tasks"
    task_module.write_task_file(tasks_dir, _task())

    task_module.delete_task_file(tasks_dir, "t042")

    assert list((tasks_dir / "active").glob("t042*.md")) == []


def test_delete_task_file_rejects_missing_task(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="t042"):
        task_module.delete_task_file(tmp_path / "tasks", "t042")


@pytest.mark.parametrize("task_id", ["*", "../victim", "t1"])
def test_find_active_file_rejects_noncanonical_id_before_path_lookup(
    tmp_path: Path,
    task_id: str,
) -> None:
    tasks_dir = tmp_path / "tasks"
    active = tasks_dir / "active"
    active.mkdir(parents=True)
    unrelated = active / "t042-unrelated.md"
    sentinel = tasks_dir / "victim.md"
    unrelated.write_text("unrelated", encoding="utf-8")
    sentinel.write_text("sentinel", encoding="utf-8")

    with pytest.raises(ValueError, match="canonical task id"):
        task_module._find_active_file(tasks_dir, task_id)

    assert unrelated.read_text(encoding="utf-8") == "unrelated"
    assert sentinel.read_text(encoding="utf-8") == "sentinel"


@pytest.mark.parametrize("task_id", ["*", "../victim", "t1"])
def test_delete_task_file_rejects_noncanonical_id_without_mutation(
    tmp_path: Path,
    task_id: str,
) -> None:
    tasks_dir = tmp_path / "tasks"
    active = tasks_dir / "active"
    active.mkdir(parents=True)
    unrelated = active / "t042-unrelated.md"
    sentinel = tasks_dir / "victim.md"
    unrelated.write_text("unrelated", encoding="utf-8")
    sentinel.write_text("sentinel", encoding="utf-8")

    with pytest.raises(ValueError, match="canonical task id"):
        task_module.delete_task_file(tasks_dir, task_id)

    assert unrelated.read_text(encoding="utf-8") == "unrelated"
    assert sentinel.read_text(encoding="utf-8") == "sentinel"


def test_unsluggable_title_uses_id_only_filename(tmp_path: Path) -> None:
    tasks_dir = tmp_path / "tasks"
    task = _task(title="!!!")

    task_module.write_task_file(tasks_dir, task)

    files = list((tasks_dir / "active").glob("t042*.md"))
    assert files == [tasks_dir / "active" / "t042.md"]
    assert task_module.parse_task_file(files[0]) == task


def test_round_trip_is_verified_before_any_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tasks_dir = tmp_path / "tasks"
    monkeypatch.setattr(task_module, "render_task_file", lambda _task: "not a task file")

    with pytest.raises(task_module.TaskIntegrityError, match="round-trip"):
        task_module.write_task_file(tasks_dir, _task())

    assert list((tasks_dir / "active").glob("*")) == []


def test_title_rename_refuses_destination_collision(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tasks_dir = tmp_path / "tasks"
    task_module.write_task_file(tasks_dir, _task())
    target = tasks_dir / "active" / "t042-second-title.md"
    real_atomic_write = task_module.atomic_write_text

    def write_then_collide(path: Path, text: str) -> None:
        real_atomic_write(path, text)
        target.write_text("collision", encoding="utf-8")

    monkeypatch.setattr(task_module, "atomic_write_text", write_then_collide)

    with pytest.raises(ValueError, match="rename target already exists"):
        task_module.write_task_file(tasks_dir, _task(title="Second title"))

    assert target.read_text(encoding="utf-8") == "collision"


def test_crash_between_content_write_and_rename_leaves_one_intact_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tasks_dir = tmp_path / "tasks"
    old_path = tasks_dir / "active" / "t042-first-title.md"
    new_path = tasks_dir / "active" / "t042-second-title.md"
    task_module.write_task_file(tasks_dir, _task())
    renamed = _task(title="Second title", description="new body")
    real_replace = os.replace

    def crash_on_title_rename(source: str | Path, destination: str | Path) -> None:
        if Path(source) == old_path and Path(destination) == new_path:
            raise OSError("simulated crash")
        real_replace(source, destination)

    monkeypatch.setattr(task_module.os, "replace", crash_on_title_rename)

    with pytest.raises(OSError, match="simulated crash"):
        task_module.write_task_file(tasks_dir, renamed)

    files = list((tasks_dir / "active").glob("t042*.md"))
    assert files == [old_path]
    assert task_module.parse_task_file(old_path) == renamed

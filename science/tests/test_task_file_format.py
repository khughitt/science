"""Canonical per-open-task Markdown file format."""

from datetime import date
from pathlib import Path

import pytest
from science_model.tasks import Task
from science_tool import tasks as task_module


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _task_text(
    *,
    task_id: str = "t042",
    title: str = "x",
    status: str = "active",
    extra: str = "",
) -> str:
    return (
        "---\n"
        f"id: {task_id}\n"
        f"title: {title}\n"
        f"status: {status}\n"
        "priority: P1\n"
        "aspects: []\n"
        "created: 2026-07-20\n"
        f"{extra}"
        "---\n"
        "\n"
        "body\n"
    )


def test_render_parse_roundtrip(tmp_path: Path) -> None:
    task = Task(
        id="t042",
        project="meta",
        title="Wire --since",
        type="implementation",
        aspects=["software-development"],
        priority="P1",
        status="active",
        blocked_by=["task:t010"],
        related=["hypothesis:h003"],
        parent="task:t001",
        group="cli",
        artifacts=["docs/result.md"],
        findings=["finding:f001"],
        created=date(2026, 7, 20),
        completed=None,
        description="First paragraph.\n\nSecond paragraph.",
    )

    rendered = task_module.render_task_file(task)
    path = _write(tmp_path / "t042-wire-since.md", rendered)

    assert task_module.parse_task_file(path) == task
    assert "completed: null\n" in rendered


def test_render_uses_underscore_frontmatter_keys(tmp_path: Path) -> None:
    task = Task(
        id="t042",
        title="x",
        status="blocked",
        blocked_by=["task:t001"],
        created=date(2026, 7, 20),
    )

    rendered = task_module.render_task_file(task)

    assert "blocked_by:\n- task:t001\n" in rendered
    assert "blocked-by:" not in rendered
    assert task_module.parse_task_file(_write(tmp_path / "t042-x.md", rendered)) == task


def test_rejects_unknown_frontmatter_key(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "t042-x.md",
        _task_text(extra="blocked-by: []\n"),
    )

    with pytest.raises(ValueError, match="unknown"):
        task_module.parse_task_file(path)


@pytest.mark.parametrize(
    "extra",
    [
        "priority: P2\n",
        "defaults: &defaults\n  project: meta\n<<: *defaults\n",
    ],
    ids=["duplicate", "merge"],
)
def test_rejects_duplicate_and_merge_keys(tmp_path: Path, extra: str) -> None:
    path = _write(tmp_path / "t042-x.md", _task_text(extra=extra))

    with pytest.raises(ValueError, match="duplicate|merge"):
        task_module.parse_task_file(path)


def test_parse_uses_one_file_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    version_a = _task_text(title="version A").replace("body\n", "body A\n")
    version_b = _task_text(title="version B").replace("body\n", "body B\n")
    snapshots = iter((version_a, version_b))
    read_count = 0

    def changing_read(_path: Path, *, encoding: str) -> str:
        nonlocal read_count
        read_count += 1
        return next(snapshots)

    monkeypatch.setattr(Path, "read_text", changing_read)

    task = task_module.parse_task_file(Path("t042-x.md"))

    assert (read_count, task.title, task.description) == (1, "version A", "body A")


def test_duplicate_key_in_first_snapshot_cannot_be_bypassed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    duplicate = _task_text(extra="priority: P2\n")
    clean = _task_text()
    snapshots = iter((duplicate, clean))
    read_count = 0

    def changing_read(_path: Path, *, encoding: str) -> str:
        nonlocal read_count
        read_count += 1
        return next(snapshots)

    monkeypatch.setattr(Path, "read_text", changing_read)

    with pytest.raises(ValueError, match="duplicate"):
        task_module.parse_task_file(Path("t042-x.md"))

    assert read_count == 1


def test_rejects_missing_required_key(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "t042-x.md",
        _task_text().replace("created: 2026-07-20\n", ""),
    )

    with pytest.raises(ValueError, match="created"):
        task_module.parse_task_file(path)


@pytest.mark.parametrize("status", ["done", "retired", "unknown"])
def test_rejects_terminal_and_unknown_statuses(tmp_path: Path, status: str) -> None:
    path = _write(tmp_path / "t042-x.md", _task_text(status=status))

    with pytest.raises(ValueError, match="status"):
        task_module.parse_task_file(path)


def test_rejects_non_canonical_id(tmp_path: Path) -> None:
    path = _write(tmp_path / "t1-x.md", _task_text(task_id="t1"))

    with pytest.raises(ValueError, match="non-canonical"):
        task_module.parse_task_file(path)


def test_rejects_filename_id_mismatch(tmp_path: Path) -> None:
    path = _write(tmp_path / "t099-x.md", _task_text())

    with pytest.raises(ValueError, match="filename"):
        task_module.parse_task_file(path)


@pytest.mark.parametrize(
    "title",
    ['"line one\\nline two"', "contains ] bracket"],
    ids=["newline", "closing-bracket"],
)
def test_rejects_non_single_line_title(tmp_path: Path, title: str) -> None:
    path = _write(tmp_path / "t042-x.md", _task_text(title=title))

    with pytest.raises(ValueError, match="title"):
        task_module.parse_task_file(path)


def test_round_trip_verifier_rejects_field_mismatch(tmp_path: Path) -> None:
    task = Task(id="t042", title="x", status="active", created=date(2026, 7, 20))
    rendered = task_module.render_task_file(task)
    expected = task.model_copy(update={"artifacts": ["missing.md"]})

    with pytest.raises(task_module.TaskIntegrityError, match="round-trip"):
        task_module._verify_task_file_round_trip(
            rendered,
            expected,
            tmp_path / "t042-x.md",
        )

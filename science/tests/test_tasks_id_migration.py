from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from science_tool.cli import main


def test_plan_task_id_migration_dry_run_does_not_modify_files(tmp_path: Path) -> None:
    from science_tool.tasks_id_migration import migrate_task_ids

    tasks = tmp_path / "tasks" / "done" / "2026-04.md"
    tasks.parent.mkdir(parents=True)
    tasks.write_text(
        "## [t001b] Follow-up\n"
        "- priority: P2\n"
        "- status: done\n"
        "- related: [task:t001, task:t001c]\n"
        "- created: 2026-04-23\n\n"
        "Output path scripts/output/t001b_run and compact t001bc note.\n",
        encoding="utf-8",
    )
    doc = tmp_path / "doc" / "interpretations" / "2026-04-23-t001b-result.md"
    doc.parent.mkdir(parents=True)
    doc.write_text('---\nid: "interpretation:2026-04-23-t001b-result"\n---\n\nSee t001b.\n', encoding="utf-8")

    result = migrate_task_ids(
        tmp_path,
        {"t001b": "t010", "t001c": "t011"},
        parent_ref="task:t001",
        apply=False,
    )

    assert result.changed_files == 2
    assert result.renamed_paths == 1
    assert "t001b" in tasks.read_text(encoding="utf-8")
    assert doc.exists()
    assert not (tmp_path / "doc" / "interpretations" / "2026-04-23-t010-result.md").exists()


def test_apply_task_id_migration_rewrites_content_paths_and_parent_blocks(tmp_path: Path) -> None:
    from science_tool.tasks_id_migration import migrate_task_ids

    tasks = tmp_path / "tasks" / "done" / "2026-04.md"
    tasks.parent.mkdir(parents=True)
    tasks.write_text(
        "## [t001b] Follow-up\n"
        "- priority: P2\n"
        "- status: done\n"
        "- related: [task:t001, task:t001c]\n"
        "- created: 2026-04-23\n\n"
        "Output path scripts/output/t001b_run and compact t001bc note.\n\n"
        "## [t001c] Second follow-up\n"
        "- priority: P3\n"
        "- status: done\n"
        "- parent: task:t001\n"
        "- related: [task:t001b]\n"
        "- created: 2026-04-23\n\n"
        "Slash series t001b/c.\n",
        encoding="utf-8",
    )
    doc = tmp_path / "doc" / "interpretations" / "2026-04-23-t001b-result.md"
    doc.parent.mkdir(parents=True)
    doc.write_text(
        '---\nid: "interpretation:2026-04-23-t001b-result"\n---\n\nSee task:t001b and t001bc.\n',
        encoding="utf-8",
    )

    result = migrate_task_ids(
        tmp_path,
        {"t001b": "t010", "t001c": "t011"},
        parent_ref="task:t001",
        apply=True,
    )

    assert result.changed_files == 2
    assert result.renamed_paths == 1
    migrated_tasks = tasks.read_text(encoding="utf-8")
    assert "## [t010] Follow-up" in migrated_tasks
    assert "## [t011] Second follow-up" in migrated_tasks
    assert migrated_tasks.count("- parent: task:t001") == 2
    assert "task:t010" in migrated_tasks
    assert "t010_run" in migrated_tasks
    assert "compact t010-t011 note" in migrated_tasks
    assert "Slash series t010/t011" in migrated_tasks
    assert "t001b" not in migrated_tasks
    renamed_doc = tmp_path / "doc" / "interpretations" / "2026-04-23-t010-result.md"
    assert renamed_doc.exists()
    assert not doc.exists()
    assert "t010-t011" in renamed_doc.read_text(encoding="utf-8")


def test_task_id_migration_rejects_new_id_collision(tmp_path: Path) -> None:
    from science_tool.tasks_id_migration import TaskIdMigrationError, migrate_task_ids

    active = tmp_path / "tasks" / "active.md"
    active.parent.mkdir(parents=True)
    active.write_text(
        "## [t010] Existing\n"
        "- priority: P1\n"
        "- status: proposed\n"
        "- created: 2026-05-12\n\n"
        "Body.\n\n"
        "## [t001b] Suffixed\n"
        "- priority: P1\n"
        "- status: proposed\n"
        "- created: 2026-05-12\n\n"
        "Body.\n",
        encoding="utf-8",
    )

    with pytest.raises(TaskIdMigrationError, match="new task id t010 already exists"):
        migrate_task_ids(tmp_path, {"t001b": "t010"}, apply=False)


def test_task_id_migration_does_not_follow_symlinked_directories(tmp_path: Path) -> None:
    from science_tool.tasks_id_migration import migrate_task_ids

    outside = tmp_path / "outside"
    outside.mkdir()
    external_file = outside / "external.md"
    external_file.write_text("See task:t001b.\n", encoding="utf-8")
    project = tmp_path / "project"
    project.mkdir()
    (project / "linked").symlink_to(outside, target_is_directory=True)
    tasks = project / "tasks" / "active.md"
    tasks.parent.mkdir()
    tasks.write_text(
        "## [t001b] Follow-up\n- priority: P1\n- status: proposed\n- created: 2026-05-12\n\nSee task:t001b.\n",
        encoding="utf-8",
    )

    result = migrate_task_ids(project, {"t001b": "t010"}, apply=True)

    assert result.changed_files == 1
    assert "task:t001b" in external_file.read_text(encoding="utf-8")
    assert "task:t010" in tasks.read_text(encoding="utf-8")


def test_tasks_migrate_ids_cli_applies_mapping(tmp_path: Path) -> None:
    tasks = tmp_path / "tasks" / "active.md"
    tasks.parent.mkdir(parents=True)
    tasks.write_text(
        "## [t001b] Follow-up\n"
        "- priority: P1\n"
        "- status: proposed\n"
        "- related: [task:t001]\n"
        "- created: 2026-05-12\n\n"
        "See t001b.\n",
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        main,
        [
            "tasks",
            "migrate-ids",
            "--project-root",
            str(tmp_path),
            "--map",
            "t001b=t010",
            "--parent",
            "task:t001",
            "--apply",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "changed_files=1" in result.output
    migrated = tasks.read_text(encoding="utf-8")
    assert "## [t010] Follow-up" in migrated
    assert "- parent: task:t001" in migrated
    assert "See t010." in migrated

from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.aspects.migrate import (
    AspectsMigrationConflict,
    build_migration_plan,
)


def test_plan_maps_type_dev_to_software_development(tmp_path: Path) -> None:
    (tmp_path / "tasks").mkdir()
    (tmp_path / "tasks" / "active.md").write_text(
        "## [t001] Pipeline cleanup\n"
        "- type: dev\n"
        "- priority: P2\n"
        "- status: proposed\n"
        "- created: 2026-04-01\n"
        "\n"
        "Body.\n"
    )
    (tmp_path / "science.yaml").write_text(
        "name: demo\nprofile: research\n"
        "aspects: [hypothesis-testing, software-development]\n"
    )

    plan = build_migration_plan(tmp_path)
    assert len(plan.task_rewrites) == 1
    rewrite = plan.task_rewrites[0]
    assert rewrite.task_id == "t001"
    assert rewrite.new_aspects == ["software-development"]


def test_plan_maps_type_research_to_non_software_project_aspects(tmp_path: Path) -> None:
    (tmp_path / "tasks").mkdir()
    (tmp_path / "tasks" / "active.md").write_text(
        "## [t002] PHF19 analysis\n"
        "- type: research\n"
        "- priority: P1\n"
        "- status: proposed\n"
        "- created: 2026-04-02\n"
        "\n"
        "Body.\n"
    )
    (tmp_path / "science.yaml").write_text(
        "name: demo\nprofile: research\n"
        "aspects: [hypothesis-testing, computational-analysis, software-development]\n"
    )

    plan = build_migration_plan(tmp_path)
    rewrite = plan.task_rewrites[0]
    assert rewrite.new_aspects == ["hypothesis-testing", "computational-analysis"]


def test_plan_skips_tasks_already_migrated(tmp_path: Path) -> None:
    (tmp_path / "tasks").mkdir()
    (tmp_path / "tasks" / "active.md").write_text(
        "## [t003] Already done\n"
        "- priority: P2\n"
        "- status: proposed\n"
        "- aspects: [hypothesis-testing]\n"
        "- created: 2026-04-03\n"
        "\n"
        "Body.\n"
    )
    (tmp_path / "science.yaml").write_text(
        "name: demo\nprofile: research\naspects: [hypothesis-testing]\n"
    )

    plan = build_migration_plan(tmp_path)
    assert plan.task_rewrites == []
    assert plan.conflicts == []


def test_plan_reports_conflict_for_tasks_with_both_type_and_aspects(tmp_path: Path) -> None:
    (tmp_path / "tasks").mkdir()
    (tmp_path / "tasks" / "active.md").write_text(
        "## [t004] Both fields\n"
        "- type: dev\n"
        "- priority: P2\n"
        "- status: proposed\n"
        "- aspects: [hypothesis-testing]\n"
        "- created: 2026-04-04\n"
        "\n"
        "Body.\n"
    )
    (tmp_path / "science.yaml").write_text(
        "name: demo\nprofile: research\n"
        "aspects: [hypothesis-testing, software-development]\n"
    )

    plan = build_migration_plan(tmp_path)
    assert plan.task_rewrites == []
    assert len(plan.conflicts) == 1
    assert plan.conflicts[0].task_id == "t004"


def test_plan_raises_when_project_has_no_aspects(tmp_path: Path) -> None:
    (tmp_path / "tasks").mkdir()
    (tmp_path / "tasks" / "active.md").write_text(
        "## [t005] Any\n- type: research\n- priority: P2\n- status: proposed\n"
        "- created: 2026-04-05\n\nBody.\n"
    )
    (tmp_path / "science.yaml").write_text("name: demo\nprofile: research\n")

    with pytest.raises(AspectsMigrationConflict, match="science.yaml"):
        build_migration_plan(tmp_path)

from __future__ import annotations

import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from science_tool.curate.inventory import collect_inventory


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _set_mtime(path: Path, when: date) -> None:
    stamp = datetime.combine(when, datetime.min.time(), tzinfo=timezone.utc).timestamp()
    os.utime(path, (stamp, stamp))


@pytest.fixture()
def curated_project(tmp_path: Path) -> Path:
    project_root = tmp_path
    _write(
        project_root / "science.yaml",
        "name: curated-project\nprofile: research\n",
    )
    _write(
        project_root / "specs/hypotheses/h1.md",
        "---\n"
        "id: hypothesis:h1\n"
        "title: Hypothesis One\n"
        "related:\n"
        "  - question:q1\n"
        "---\n"
        "Hypothesis body.\n",
    )
    _write(
        project_root / "doc/questions/q1.md",
        "---\n"
        "id: question:q1\n"
        "title: Question One\n"
        "---\n"
        "Question body.\n",
    )
    _write(
        project_root / "doc/papers/p1.md",
        "---\n"
        "id: paper:p1\n"
        "title: Paper One\n"
        "related:\n"
        "  - question:q1\n"
        "source_refs:\n"
        "  - cite:paper-one\n"
        "---\n"
        "Paper body.\n",
    )
    _write(
        project_root / "doc/interpretations/i1.md",
        "---\n"
        "id: interpretation:i1\n"
        "title: Interpretation One\n"
        "related:\n"
        "  - question:q1\n"
        "---\n"
        "Interpretation body.\n",
    )
    _write(
        project_root / "tasks/active.md",
        "## [t001] Active task\n"
        "- type: research\n"
        "- priority: P1\n"
        "- status: in_progress\n"
        "- related: [question:q1]\n"
        "- created: 2026-04-20\n"
        "\n"
        "Active task body.\n",
    )
    _write(
        project_root / "tasks/done/2026-04-01.md",
        "## [t002] Done task\n"
        "- type: research\n"
        "- priority: P2\n"
        "- status: done\n"
        "- related: [hypothesis:h1]\n"
        "- created: 2026-03-20\n"
        "- completed: 2026-04-01\n"
        "\n"
        "Done task body.\n",
    )

    today = date(2026, 4, 21)
    _set_mtime(project_root / "specs/hypotheses/h1.md", today - timedelta(days=9))
    _set_mtime(project_root / "doc/questions/q1.md", today)
    _set_mtime(project_root / "doc/papers/p1.md", today - timedelta(days=2))
    _set_mtime(project_root / "doc/interpretations/i1.md", today - timedelta(days=45))
    _set_mtime(project_root / "tasks/active.md", today - timedelta(days=1))
    _set_mtime(project_root / "tasks/done/2026-04-01.md", today - timedelta(days=90))

    return project_root


def test_collect_inventory_tracks_counts_and_candidate_signals(curated_project: Path) -> None:
    inventory = collect_inventory(curated_project, today=date(2026, 4, 21))

    assert inventory.project_root == str(curated_project)
    assert inventory.artifact_counts == {
        "hypothesis": 1,
        "interpretation": 1,
        "paper": 1,
        "question": 1,
        "task": 2,
    }

    assert [artifact.path for artifact in inventory.artifacts] == [
        "doc/interpretations/i1.md",
        "doc/papers/p1.md",
        "doc/questions/q1.md",
        "specs/hypotheses/h1.md",
        "tasks/active.md#t001",
        "tasks/done/2026-04-01.md#t002",
    ]

    assert inventory.candidate_signals.missing_related == ["doc/questions/q1.md"]
    assert inventory.candidate_signals.missing_source_refs == ["doc/interpretations/i1.md"]
    assert inventory.candidate_signals.no_outbound_links == ["doc/questions/q1.md"]
    assert inventory.candidate_signals.recently_modified == [
        "doc/questions/q1.md",
        "tasks/active.md#t001",
        "doc/papers/p1.md",
    ]
    assert inventory.candidate_signals.long_idle == [
        "doc/interpretations/i1.md",
        "tasks/done/2026-04-01.md#t002",
    ]

    assert [artifact.modified_days_ago for artifact in inventory.artifacts] == [45, 2, 0, 9, 1, 90]

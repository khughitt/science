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
        project_root / "entities/hypotheses/h1.md",
        "---\nid: hypothesis:h1\ntitle: Hypothesis One\nrelated:\n  - question:q1\n---\nHypothesis body.\n",
    )
    _write(
        project_root / "entities/questions/q1.md",
        "---\nid: question:q1\ntitle: Question One\n---\nQuestion body.\n",
    )
    _write(
        project_root / "entities/papers/p1.md",
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
        project_root / "entities/interpretations/i1.md",
        "---\nid: interpretation:i1\ntitle: Interpretation One\nrelated:\n  - question:q1\n---\nInterpretation body.\n",
    )
    _write(
        project_root / "entities/topics/topic-a.md",
        "---\n"
        "id: topic:topic-a\n"
        "title: Topic A\n"
        "related:\n"
        "  - question:q1\n"
        "source_refs:\n"
        "  - cite:topic-a\n"
        "---\n"
        "Topic body.\n",
    )
    _write(
        project_root / "entities/discussions/d1.md",
        "---\n"
        "id: discussion:d1\n"
        "title: Discussion One\n"
        "related:\n"
        "  - question:q1\n"
        "source_refs:\n"
        "  - cite:discussion-one\n"
        "---\n"
        "Discussion body.\n",
    )
    _write(
        project_root / "knowledge/sources/local/entities.yaml",
        "title: Local entities\n"
        "related:\n"
        "  - question:q1\n"
        "source_refs:\n"
        "  - cite:local-entities\n"
        "entities:\n"
        "  - id: hypothesis:h1\n"
        "    title: Hypothesis One\n",
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
    _set_mtime(project_root / "entities/hypotheses/h1.md", today - timedelta(days=9))
    _set_mtime(project_root / "entities/questions/q1.md", today)
    _set_mtime(project_root / "entities/papers/p1.md", today - timedelta(days=2))
    _set_mtime(project_root / "entities/interpretations/i1.md", today - timedelta(days=45))
    _set_mtime(project_root / "entities/topics/topic-a.md", today - timedelta(days=4))
    _set_mtime(project_root / "entities/discussions/d1.md", today - timedelta(days=6))
    _set_mtime(project_root / "knowledge/sources/local/entities.yaml", today - timedelta(days=60))
    _set_mtime(project_root / "tasks/active.md", today - timedelta(days=1))
    _set_mtime(project_root / "tasks/done/2026-04-01.md", today - timedelta(days=90))

    return project_root


def test_collect_inventory_tracks_counts_and_candidate_signals(curated_project: Path) -> None:
    inventory = collect_inventory(curated_project, today=date(2026, 4, 21))

    assert inventory.project_root == str(curated_project)
    assert inventory.artifact_counts == {
        "discussion": 1,
        "hypothesis": 1,
        "interpretation": 1,
        "knowledge_source": 1,
        "paper": 1,
        "question": 1,
        "topic": 1,
        "task": 2,
    }

    assert [artifact.path for artifact in inventory.artifacts] == [
        "entities/discussions/d1.md",
        "entities/hypotheses/h1.md",
        "entities/interpretations/i1.md",
        "entities/papers/p1.md",
        "entities/questions/q1.md",
        "entities/topics/topic-a.md",
        "knowledge/sources/local/entities.yaml",
        "tasks/active.md#t001",
        "tasks/done/2026-04-01.md#t002",
    ]

    assert inventory.candidate_signals.missing_related == ["entities/questions/q1.md"]
    assert inventory.candidate_signals.missing_source_refs == ["entities/interpretations/i1.md"]
    assert inventory.candidate_signals.no_outbound_links == ["entities/questions/q1.md"]
    assert inventory.candidate_signals.recently_modified == [
        "entities/questions/q1.md",
        "tasks/active.md#t001",
        "entities/papers/p1.md",
        "entities/topics/topic-a.md",
        "entities/discussions/d1.md",
    ]
    assert inventory.candidate_signals.long_idle == [
        "entities/interpretations/i1.md",
        "knowledge/sources/local/entities.yaml",
        "tasks/done/2026-04-01.md#t002",
    ]

    assert [artifact.modified_days_ago for artifact in inventory.artifacts] == [6, 9, 45, 2, 0, 4, 60, 1, 90]

    knowledge_source = next(
        artifact for artifact in inventory.artifacts if artifact.path == "knowledge/sources/local/entities.yaml"
    )
    assert knowledge_source.artifact_class == "knowledge_source"
    assert knowledge_source.id is None
    assert knowledge_source.title == "Local entities"
    assert knowledge_source.related_count == 1
    assert knowledge_source.source_refs_count == 1


def test_collect_inventory_defers_to_emergent_threads_orphans(curated_project: Path) -> None:
    """fb-2026-05-01-004: a fresh _emergent-threads.md suppresses missing_source_refs
    for ids already enumerated there."""
    threads = curated_project / "doc/reports/synthesis/_emergent-threads.md"
    threads.parent.mkdir(parents=True, exist_ok=True)
    threads.write_text(
        "---\norphan_ids:\n  - interpretation:i1\n---\nBody.\n",
        encoding="utf-8",
    )
    _set_mtime(threads, date(2026, 4, 21))

    inventory = collect_inventory(curated_project, today=date(2026, 4, 21))
    # Without the deferral, doc/interpretations/i1.md would appear here.
    assert inventory.candidate_signals.missing_source_refs == []


def test_collect_inventory_ignores_stale_emergent_threads(curated_project: Path) -> None:
    """fb-2026-05-01-004: a stale _emergent-threads.md (> 30 days old) does NOT suppress."""
    threads = curated_project / "doc/reports/synthesis/_emergent-threads.md"
    threads.parent.mkdir(parents=True, exist_ok=True)
    threads.write_text(
        "---\norphan_ids:\n  - interpretation:i1\n---\n",
        encoding="utf-8",
    )
    _set_mtime(threads, date(2026, 1, 1))  # >30 days before 2026-04-21

    inventory = collect_inventory(curated_project, today=date(2026, 4, 21))
    assert inventory.candidate_signals.missing_source_refs == ["entities/interpretations/i1.md"]


def test_collect_inventory_recent_top_k_caps_recently_modified(curated_project: Path) -> None:
    """fb-2026-05-01-005: recent_top_k caps recently_modified to the K most-recent entries."""
    inventory = collect_inventory(curated_project, today=date(2026, 4, 21), recent_top_k=2)
    assert len(inventory.candidate_signals.recently_modified) == 2
    # Ensure the cap kept the most-recent (smallest modified_days_ago).
    assert inventory.candidate_signals.recently_modified == [
        "entities/questions/q1.md",
        "tasks/active.md#t001",
    ]


def test_collect_inventory_recent_days_tightens_window(curated_project: Path) -> None:
    """fb-2026-05-01-005: recent_days tightens the window so noise drops fast."""
    inventory = collect_inventory(curated_project, today=date(2026, 4, 21), recent_days=1, recent_top_k=None)
    # With a 1-day window, only artifacts modified within 1 day qualify.
    assert inventory.candidate_signals.recently_modified == [
        "entities/questions/q1.md",
        "tasks/active.md#t001",
    ]


def test_collect_inventory_surfaces_frontmatter_less_files(curated_project: Path) -> None:
    """fb-2026-05-01-002: markdown files in known doc roots without frontmatter
    must surface in candidate_signals.no_frontmatter_files so curation catches drift."""
    _write(
        curated_project / "entities/reports/2026-05-01-untracked-report.md",
        "# Untracked report\n\nSome body without frontmatter.\n",
    )
    _write(
        curated_project / "entities/reports/2026-05-01-with-fm.md",
        "---\nid: report:r1\ntitle: Tracked\n---\nBody.\n",
    )
    inventory = collect_inventory(curated_project, today=date(2026, 5, 1))
    assert inventory.candidate_signals.no_frontmatter_files == [
        "entities/reports/2026-05-01-untracked-report.md",
    ]


def test_collect_inventory_includes_agents_md_state(curated_project: Path) -> None:
    # The curated_project fixture has no AGENTS.md / CLAUDE.md / core/.
    # The agents_md state should still be present and report absence cleanly.
    inventory = collect_inventory(curated_project, today=date(2026, 4, 21))
    assert inventory.agents_md is not None
    assert inventory.agents_md.agents_md_present is False
    assert inventory.agents_md.claude_md_present is False
    assert inventory.agents_md.drift_signals == []


def test_collect_inventory_surfaces_agents_md_drift(curated_project: Path) -> None:
    _write(
        curated_project / "AGENTS.md",
        "@core/overview.md\n@core/decisions.md\n\n# project\n",
    )
    _write(curated_project / "CLAUDE.md", "@AGENTS.md\n")
    _write(
        curated_project / "core/decisions.md",
        "## D-001: Thing\n\n- **Status:** active\n",
    )

    inventory = collect_inventory(curated_project, today=date(2026, 4, 21))
    assert inventory.agents_md is not None
    assert inventory.agents_md.agents_md_legacy_at_includes == [
        "@core/overview.md",
        "@core/decisions.md",
    ]
    assert "agents_md_legacy_includes" in inventory.agents_md.drift_signals
    assert "markers_missing" in inventory.agents_md.drift_signals


def test_artifact_class_prefers_kind_over_dir_and_id(tmp_path: Path) -> None:
    # `kind:` wins even when the dir name and id prefix disagree.
    _write(tmp_path / "science.yaml", "name: p\nprofile: research\n")
    _write(
        tmp_path / "entities/questions/m1.md",
        "---\nid: question:m1\nkind: mechanism\ntitle: M\n---\nBody.\n",
    )
    inventory = collect_inventory(tmp_path, today=date(2026, 4, 21))
    cls = {a.path: a.artifact_class for a in inventory.artifacts}
    assert cls["entities/questions/m1.md"] == "mechanism"


def test_artifact_class_falls_back_to_kind_then_id_prefix(tmp_path: Path) -> None:
    _write(tmp_path / "science.yaml", "name: p\nprofile: research\n")
    # Use `kind:`.
    _write(
        tmp_path / "entities/findings/f1.md",
        "---\nid: finding:f1\nkind: finding\ntitle: F\n---\nBody.\n",
    )
    # No `kind:` -> use the colon-prefixed id prefix.
    _write(
        tmp_path / "entities/observations/o1.md",
        "---\nid: observation:o1\ntitle: O\n---\nBody.\n",
    )
    inventory = collect_inventory(tmp_path, today=date(2026, 4, 21))
    cls = {a.path: a.artifact_class for a in inventory.artifacts}
    assert cls["entities/findings/f1.md"] == "finding"
    assert cls["entities/observations/o1.md"] == "observation"


def test_record_with_frontmatter_but_no_classifiable_kind_is_skipped(tmp_path: Path) -> None:
    # Has frontmatter (so not no_frontmatter) but no kind and a bare id ->
    # unclassifiable -> skipped (keys no signal, not counted).
    _write(tmp_path / "science.yaml", "name: p\nprofile: research\n")
    _write(
        tmp_path / "entities/misc/x1.md",
        "---\nid: bare-no-colon\ntitle: X\n---\nBody.\n",
    )
    inventory = collect_inventory(tmp_path, today=date(2026, 4, 21))
    assert [a.path for a in inventory.artifacts] == []
    assert inventory.candidate_signals.no_frontmatter_files == []


def test_archived_member_is_absent_from_inventory(tmp_path: Path) -> None:
    # A relocated archived member under entities/_archive/ is skipped by the iterator.
    _write(tmp_path / "science.yaml", "name: p\nprofile: research\n")
    _write(
        tmp_path / "entities/_archive/interpretations/old.md",
        "---\nid: interpretation:old\nkind: interpretation\nstatus: archived\n---\nBody.\n",
    )
    inventory = collect_inventory(tmp_path, today=date(2026, 4, 21))
    assert [a.path for a in inventory.artifacts] == []


def test_superseded_status_entity_is_present(tmp_path: Path) -> None:
    # No status filter: a superseded-but-not-relocated entity stays visible so a
    # human can act on it in curate.
    _write(tmp_path / "science.yaml", "name: p\nprofile: research\n")
    _write(
        tmp_path / "entities/interpretations/s1.md",
        "---\nid: interpretation:s1\nkind: interpretation\nstatus: superseded\n---\nBody.\n",
    )
    inventory = collect_inventory(tmp_path, today=date(2026, 4, 21))
    assert [a.path for a in inventory.artifacts] == ["entities/interpretations/s1.md"]


def test_legacy_specs_and_doc_are_no_longer_scanned(tmp_path: Path) -> None:
    # The retired layout is ignored: a doc/ entity and a depth-2 specs/*.md "spec"
    # contribute nothing.
    _write(tmp_path / "science.yaml", "name: p\nprofile: research\n")
    _write(
        tmp_path / "doc/questions/q9.md",
        "---\nid: question:q9\nkind: question\n---\nBody.\n",
    )
    _write(tmp_path / "specs/overview.md", "---\nid: spec:overview\n---\nBody.\n")
    inventory = collect_inventory(tmp_path, today=date(2026, 4, 21))
    assert [a.path for a in inventory.artifacts] == []
    assert "spec" not in inventory.artifact_counts

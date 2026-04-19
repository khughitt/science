"""Tests for project_model_migration: old entity type → new entity type conversion."""

from pathlib import Path

from science_tool.graph.project_model_migration import migrate_entity_sources


def test_migrate_claim_to_proposition(tmp_path: Path) -> None:
    source = tmp_path / "doc" / "claims" / "c01.md"
    source.parent.mkdir(parents=True)
    source.write_text(
        "---\nid: claim:c01\ntype: claim\ntitle: Test claim\nrelated: []\nsource_refs: []\n---\nBody text\n"
    )
    results = migrate_entity_sources(tmp_path)
    content = source.read_text()
    assert "type: proposition" in content
    assert "id: proposition:c01" in content
    assert results["migrated"] >= 1


def test_migrate_relation_claim_to_proposition(tmp_path: Path) -> None:
    source = tmp_path / "doc" / "claims" / "rc01.md"
    source.parent.mkdir(parents=True)
    source.write_text(
        "---\nid: relation_claim:rc01\ntype: relation_claim\ntitle: X causes Y\nrelated: []\nsource_refs: []\n---\n"
    )
    migrate_entity_sources(tmp_path)
    content = source.read_text()
    assert "type: proposition" in content
    assert "id: proposition:rc01" in content


def test_migrate_evidence_to_observation(tmp_path: Path) -> None:
    source = tmp_path / "doc" / "evidence" / "e01.md"
    source.parent.mkdir(parents=True)
    source.write_text(
        "---\nid: evidence:e01\ntype: evidence\ntitle: Correlation data\nrelated: []\nsource_refs: []\n---\n"
    )
    migrate_entity_sources(tmp_path)
    content = source.read_text()
    assert "type: observation" in content
    assert "id: observation:e01" in content


def test_migrate_paper_preserved_unchanged(tmp_path: Path) -> None:
    """``paper:`` entities pass through migration unchanged.

    The 2026-04-19 manuscript+paper rename reversed the earlier paper→article
    direction, so a file whose only entity prefix is ``paper:`` is now a no-op
    for this migration.
    """
    source = tmp_path / "doc" / "background" / "papers" / "smith-2024.md"
    source.parent.mkdir(parents=True)
    source.write_text(
        "---\nid: paper:smith-2024\ntype: paper\ntitle: Smith 2024\nrelated: []\nsource_refs: []\n---\n"
    )
    results = migrate_entity_sources(tmp_path)
    content = source.read_text()
    assert "type: paper" in content
    assert "id: paper:smith-2024" in content
    assert results["migrated"] == 0
    assert results["skipped"] >= 1


def test_migrate_updates_cross_references(tmp_path: Path) -> None:
    source = tmp_path / "doc" / "hypotheses" / "h01.md"
    source.parent.mkdir(parents=True)
    source.write_text(
        "---\nid: hypothesis:h01\ntype: hypothesis\ntitle: H1\nrelated:\n  - claim:c01\n  - evidence:e01\nsource_refs:\n  - paper:smith-2024\n---\n"
    )
    migrate_entity_sources(tmp_path)
    content = source.read_text()
    assert "proposition:c01" in content
    assert "observation:e01" in content
    # paper: refs are NOT migrated post-2026-04-19 rename.
    assert "paper:smith-2024" in content


def test_migrate_skips_unchanged_files(tmp_path: Path) -> None:
    source = tmp_path / "doc" / "topics" / "topic.md"
    source.parent.mkdir(parents=True)
    source.write_text(
        "---\nid: topic:t01\ntype: topic\ntitle: A topic\nrelated: []\nsource_refs: []\n---\nBody\n"
    )
    results = migrate_entity_sources(tmp_path)
    assert results["skipped"] >= 1
    assert results["migrated"] == 0


def test_migrate_skips_files_without_frontmatter(tmp_path: Path) -> None:
    source = tmp_path / "doc" / "readme.md"
    source.parent.mkdir(parents=True)
    source.write_text("# Just a readme\nNo frontmatter here.\n")
    results = migrate_entity_sources(tmp_path)
    assert results["skipped"] >= 1


def test_migrate_artifact_to_data_package(tmp_path: Path) -> None:
    source = tmp_path / "doc" / "artifacts" / "a01.md"
    source.parent.mkdir(parents=True)
    source.write_text(
        "---\nid: artifact:a01\ntype: artifact\ntitle: Raw dataset\nrelated: []\nsource_refs: []\n---\n"
    )
    migrate_entity_sources(tmp_path)
    content = source.read_text()
    assert "type: data-package" in content
    assert "id: data-package:a01" in content


def test_migrate_specs_directory(tmp_path: Path) -> None:
    source = tmp_path / "specs" / "models" / "m01.md"
    source.parent.mkdir(parents=True)
    source.write_text(
        "---\nid: claim:m01\ntype: claim\ntitle: Model claim\nrelated: []\nsource_refs: []\n---\n"
    )
    results = migrate_entity_sources(tmp_path)
    content = source.read_text()
    assert "type: proposition" in content
    assert results["migrated"] >= 1


def test_migrate_yaml_source_file(tmp_path: Path) -> None:
    source = tmp_path / "knowledge" / "sources" / "sources.yaml"
    source.parent.mkdir(parents=True)
    source.write_text(
        "- id: claim:c01\n  type: claim\n  title: A claim\n- id: evidence:e01\n  type: evidence\n  title: Some evidence\n"
    )
    results = migrate_entity_sources(tmp_path)
    content = source.read_text()
    assert "type: proposition" in content
    assert "proposition:c01" in content
    assert "type: observation" in content
    assert "observation:e01" in content
    assert results["migrated"] >= 1


def test_migrate_blocked_by_cross_references(tmp_path: Path) -> None:
    source = tmp_path / "doc" / "tasks" / "t01.md"
    source.parent.mkdir(parents=True)
    source.write_text(
        "---\nid: task:t01\ntype: task\ntitle: A task\nblocked_by:\n  - claim:c01\n  - evidence:e02\n---\n"
    )
    migrate_entity_sources(tmp_path)
    content = source.read_text()
    assert "proposition:c01" in content
    assert "observation:e02" in content


def test_migrate_tasks_directory(tmp_path: Path) -> None:
    """Migration scans tasks/ directory."""
    source = tmp_path / "tasks" / "active.md"
    source.parent.mkdir(parents=True)
    source.write_text(
        "---\nid: task:t01\ntype: task\ntitle: Do something\nrelated:\n  - claim:Walker2024\n---\n"
    )
    results = migrate_entity_sources(tmp_path)
    content = source.read_text()
    assert "proposition:Walker2024" in content
    assert results["migrated"] >= 1


def test_migrate_custom_list_fields(tmp_path: Path) -> None:
    """Migration renames refs in any list-of-string field, not just related/source_refs/blocked_by."""
    source = tmp_path / "doc" / "synthesis.md"
    source.parent.mkdir(parents=True)
    source.write_text(
        "---\nid: synthesis:s01\ntype: synthesis\ntitle: Synthesis\nclaims:\n  - claim:Smith2024\n  - claim:Jones2023\n---\n"
    )
    results = migrate_entity_sources(tmp_path)
    content = source.read_text()
    assert "proposition:Smith2024" in content
    assert "proposition:Jones2023" in content
    assert "claim:" not in content
    assert results["migrated"] >= 1


def test_migrate_returns_correct_stats(tmp_path: Path) -> None:
    (tmp_path / "doc").mkdir()
    migrated = tmp_path / "doc" / "claim.md"
    migrated.write_text(
        "---\nid: claim:c01\ntype: claim\ntitle: A claim\n---\n"
    )
    skipped = tmp_path / "doc" / "hypothesis.md"
    skipped.write_text(
        "---\nid: hypothesis:h01\ntype: hypothesis\ntitle: A hypothesis\n---\n"
    )
    no_frontmatter = tmp_path / "doc" / "notes.md"
    no_frontmatter.write_text("# Notes\nJust notes.\n")

    results = migrate_entity_sources(tmp_path)
    assert results["migrated"] == 1
    assert results["skipped"] == 2
    assert results["errors"] == 0

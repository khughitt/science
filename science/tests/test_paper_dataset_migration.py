from __future__ import annotations

from pathlib import Path

import yaml

from science_tool.graph.paper_dataset_migration import (
    PaperDatasetMigrationConflict,
    is_paper_dataset_role_conflict,
    migrate_paper_frontmatter,
    plan_paper_dataset_migration,
)


def _body(frontmatter: dict, body: str = "Body.\n") -> str:
    return "---\n" + yaml.safe_dump(frontmatter, sort_keys=False) + "---\n\n" + body


def _frontmatter(text: str) -> dict:
    block = text.split("---", 2)[1]
    return yaml.safe_load(block)


def test_migrate_paper_frontmatter_adds_dataset_usage_and_removes_legacy_field() -> None:
    original = _body(
        {
            "id": "paper:smith-2025",
            "kind": "paper",
            "title": "Smith 2025",
            "datasets": ["dataset:gtex-v8"],
        }
    )

    result = migrate_paper_frontmatter("entities/papers/smith-2025.md", original)

    assert result.changed is True
    assert result.conflicts == []
    fm = _frontmatter(result.updated_text)
    assert "datasets" not in fm
    assert fm["dataset_usage"] == [
        {"ref": "dataset:gtex-v8", "role": "analyzed", "overlap": "unknown"}
    ]
    assert result.updated_text.endswith("\nBody.\n")


def test_migrate_paper_frontmatter_preserves_existing_usage_order_and_appends_missing_refs() -> None:
    original = _body(
        {
            "id": "paper:smith-2025",
            "kind": "paper",
            "title": "Smith 2025",
            "dataset_usage": [
                {"ref": "dataset:existing", "role": "analyzed", "overlap": "full"},
            ],
            "datasets": ["dataset:existing", "dataset:new", "dataset:new"],
        }
    )

    result = migrate_paper_frontmatter("entities/papers/smith-2025.md", original)

    assert result.conflicts == []
    fm = _frontmatter(result.updated_text)
    assert fm["dataset_usage"] == [
        {"ref": "dataset:existing", "role": "analyzed", "overlap": "full"},
        {"ref": "dataset:new", "role": "analyzed", "overlap": "unknown"},
    ]


def test_analyzed_full_same_ref_is_not_a_conflict() -> None:
    assert (
        is_paper_dataset_role_conflict(
            {"ref": "dataset:gtex-v8", "role": "analyzed", "overlap": "full"}
        )
        is False
    )

    original = _body(
        {
            "id": "paper:smith-2025",
            "kind": "paper",
            "dataset_usage": [
                {"ref": "dataset:gtex-v8", "role": "analyzed", "overlap": "full"},
            ],
            "datasets": ["dataset:gtex-v8"],
        }
    )

    result = migrate_paper_frontmatter("entities/papers/smith-2025.md", original)

    assert result.changed is True
    assert result.conflicts == []
    fm = _frontmatter(result.updated_text)
    assert "datasets" not in fm
    assert fm["dataset_usage"] == [
        {"ref": "dataset:gtex-v8", "role": "analyzed", "overlap": "full"},
    ]


def test_non_analyzed_same_ref_is_role_conflict_and_leaves_text_unchanged() -> None:
    assert is_paper_dataset_role_conflict({"ref": "dataset:gtex-v8", "role": "cited"}) is True
    original = _body(
        {
            "id": "paper:smith-2025",
            "kind": "paper",
            "dataset_usage": [{"ref": "dataset:gtex-v8", "role": "cited"}],
            "datasets": ["dataset:gtex-v8"],
        }
    )

    result = migrate_paper_frontmatter("entities/papers/smith-2025.md", original)

    assert result.changed is False
    assert result.updated_text == original
    assert result.conflicts == [
        PaperDatasetMigrationConflict(
            path="entities/papers/smith-2025.md",
            paper_id="paper:smith-2025",
            dataset_ref="dataset:gtex-v8",
            reason="role-conflict",
            detail="legacy paper.datasets implies role analyzed but explicit dataset_usage has role cited",
        )
    ]


def test_unresolved_dataset_ref_moves_verbatim_when_syntactically_valid() -> None:
    original = _body(
        {
            "id": "paper:smith-2025",
            "kind": "paper",
            "datasets": ["dataset:not-in-commons"],
        }
    )

    result = migrate_paper_frontmatter("entities/papers/smith-2025.md", original)

    assert result.conflicts == []
    fm = _frontmatter(result.updated_text)
    assert fm["dataset_usage"] == [
        {"ref": "dataset:not-in-commons", "role": "analyzed", "overlap": "unknown"}
    ]


def test_alias_equivalent_refs_are_not_deduped_by_the_migration() -> None:
    original = _body(
        {
            "id": "paper:smith-2025",
            "kind": "paper",
            "dataset_usage": [{"ref": "dataset:gtex-v8", "role": "analyzed", "overlap": "full"}],
            "datasets": ["dataset:gtex"],
        }
    )

    result = migrate_paper_frontmatter("entities/papers/smith-2025.md", original)

    assert result.conflicts == []
    fm = _frontmatter(result.updated_text)
    assert fm["dataset_usage"] == [
        {"ref": "dataset:gtex-v8", "role": "analyzed", "overlap": "full"},
        {"ref": "dataset:gtex", "role": "analyzed", "overlap": "unknown"},
    ]


def test_empty_datasets_field_is_removed_without_adding_usage() -> None:
    original = _body({"id": "paper:smith-2025", "kind": "paper", "datasets": []})

    result = migrate_paper_frontmatter("entities/papers/smith-2025.md", original)

    assert result.changed is True
    assert result.conflicts == []
    fm = _frontmatter(result.updated_text)
    assert "datasets" not in fm
    assert "dataset_usage" not in fm


def test_malformed_datasets_conflict_leaves_text_unchanged() -> None:
    original = _body({"id": "paper:smith-2025", "kind": "paper", "datasets": ["gtex"]})

    result = migrate_paper_frontmatter("entities/papers/smith-2025.md", original)

    assert result.changed is False
    assert result.updated_text == original
    assert [conflict.reason for conflict in result.conflicts] == ["malformed-datasets"]


def test_malformed_dataset_usage_conflict_leaves_text_unchanged() -> None:
    original = _body(
        {
            "id": "paper:smith-2025",
            "kind": "paper",
            "dataset_usage": [{"ref": "dataset:gtex-v8"}],
            "datasets": ["dataset:gtex-v8"],
        }
    )

    result = migrate_paper_frontmatter("entities/papers/smith-2025.md", original)

    assert result.changed is False
    assert result.updated_text == original
    assert [conflict.reason for conflict in result.conflicts] == ["malformed-usage"]


def _write_project(root: Path) -> None:
    (root / "science.yaml").write_text("name: demo\nknowledge_profiles:\n  local: local\n", encoding="utf-8")
    (root / "entities" / "papers").mkdir(parents=True)
    (root / "entities" / "topics").mkdir(parents=True)


def test_plan_scans_only_paper_frontmatter_documents(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    _write_project(root)
    paper = root / "entities" / "papers" / "smith.md"
    topic = root / "entities" / "topics" / "dataset-note.md"
    paper.write_text(_body({"id": "paper:smith", "kind": "paper", "datasets": ["dataset:gtex-v8"]}), encoding="utf-8")
    topic.write_text(_body({"id": "topic:data", "kind": "topic", "datasets": ["dataset:gtex-v8"]}), encoding="utf-8")

    report = plan_paper_dataset_migration(root)

    assert report.changed_files == [str(paper)]
    assert report.conflicts == []


def test_plan_reports_malformed_frontmatter_only_for_paper_source_surface(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    _write_project(root)
    bad_paper = root / "entities" / "papers" / "bad.md"
    bad_topic = root / "entities" / "topics" / "bad.md"
    bad_paper.write_text("---\nid: [\n---\nBody.\n", encoding="utf-8")
    bad_topic.write_text("---\nid: [\n---\nBody.\n", encoding="utf-8")

    report = plan_paper_dataset_migration(root)

    assert [conflict.reason for conflict in report.conflicts] == ["malformed-frontmatter"]
    assert report.conflicts[0].path == str(bad_paper)
    assert report.changed_files == []


def test_apply_rewrites_changed_files_and_second_run_is_clean(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    _write_project(root)
    paper = root / "entities" / "papers" / "smith.md"
    paper.write_text(_body({"id": "paper:smith", "kind": "paper", "datasets": ["dataset:gtex-v8"]}), encoding="utf-8")

    first = plan_paper_dataset_migration(root, apply=True)
    second = plan_paper_dataset_migration(root, apply=True)

    assert first.changed_files == [str(paper)]
    assert second.changed_files == []
    text = paper.read_text(encoding="utf-8")
    assert "datasets:" not in text
    assert "dataset_usage:" in text


def test_plan_uses_configured_local_profile_paper_surface(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    (root / "science.yaml").write_text(
        "\n".join(
            [
                "name: demo",
                "knowledge_profiles:",
                "  local: lab",
                "profiles:",
                "  lab:",
                "    papers:",
                "      - literature/papers",
                "",
            ]
        ),
        encoding="utf-8",
    )
    paper_dir = root / "literature" / "papers"
    paper_dir.mkdir(parents=True)
    paper = paper_dir / "smith.md"
    paper.write_text(_body({"id": "paper:smith", "kind": "paper", "datasets": ["dataset:gtex-v8"]}), encoding="utf-8")

    report = plan_paper_dataset_migration(root)

    assert report.changed_files == [str(paper)]
    assert report.conflicts == []


def test_plan_reports_malformed_frontmatter_in_configured_paper_surface(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    (root / "science.yaml").write_text(
        "\n".join(
            [
                "name: demo",
                "knowledge_profiles:",
                "  local: lab",
                "profiles:",
                "  lab:",
                "    papers:",
                "      - literature/papers",
                "",
            ]
        ),
        encoding="utf-8",
    )
    paper_dir = root / "literature" / "papers"
    paper_dir.mkdir(parents=True)
    bad = paper_dir / "bad.md"
    bad.write_text("---\nid: [\n---\nBody.\n", encoding="utf-8")

    report = plan_paper_dataset_migration(root)

    assert [conflict.reason for conflict in report.conflicts] == ["malformed-frontmatter"]
    assert report.conflicts[0].path == str(bad)

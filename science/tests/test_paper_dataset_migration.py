from __future__ import annotations

import yaml

from science_tool.graph.paper_dataset_migration import (
    PaperDatasetMigrationConflict,
    is_paper_dataset_role_conflict,
    migrate_paper_frontmatter,
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
            "type": "paper",
            "title": "Smith 2025",
            "datasets": ["dataset:gtex-v8"],
        }
    )

    result = migrate_paper_frontmatter("doc/papers/smith-2025.md", original)

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

    result = migrate_paper_frontmatter("doc/papers/smith-2025.md", original)

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
            "type": "paper",
            "dataset_usage": [
                {"ref": "dataset:gtex-v8", "role": "analyzed", "overlap": "full"},
            ],
            "datasets": ["dataset:gtex-v8"],
        }
    )

    result = migrate_paper_frontmatter("doc/papers/smith-2025.md", original)

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
            "type": "paper",
            "dataset_usage": [{"ref": "dataset:gtex-v8", "role": "cited"}],
            "datasets": ["dataset:gtex-v8"],
        }
    )

    result = migrate_paper_frontmatter("doc/papers/smith-2025.md", original)

    assert result.changed is False
    assert result.updated_text == original
    assert result.conflicts == [
        PaperDatasetMigrationConflict(
            path="doc/papers/smith-2025.md",
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
            "type": "paper",
            "datasets": ["dataset:not-in-commons"],
        }
    )

    result = migrate_paper_frontmatter("doc/papers/smith-2025.md", original)

    assert result.conflicts == []
    fm = _frontmatter(result.updated_text)
    assert fm["dataset_usage"] == [
        {"ref": "dataset:not-in-commons", "role": "analyzed", "overlap": "unknown"}
    ]


def test_alias_equivalent_refs_are_not_deduped_by_the_migration() -> None:
    original = _body(
        {
            "id": "paper:smith-2025",
            "type": "paper",
            "dataset_usage": [{"ref": "dataset:gtex-v8", "role": "analyzed", "overlap": "full"}],
            "datasets": ["dataset:gtex"],
        }
    )

    result = migrate_paper_frontmatter("doc/papers/smith-2025.md", original)

    assert result.conflicts == []
    fm = _frontmatter(result.updated_text)
    assert fm["dataset_usage"] == [
        {"ref": "dataset:gtex-v8", "role": "analyzed", "overlap": "full"},
        {"ref": "dataset:gtex", "role": "analyzed", "overlap": "unknown"},
    ]

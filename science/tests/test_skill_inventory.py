from __future__ import annotations

import pytest

from science_tool.graph.skill_inventory import SkillInventoryError, parse_skill_frontmatter


def test_parse_frontmatter_reads_mapping() -> None:
    text = "---\nname: transcriptomics-scrna-qa\narchetype: measurement-qa\n---\n\nBody.\n"
    assert parse_skill_frontmatter(text) == {
        "name": "transcriptomics-scrna-qa",
        "archetype": "measurement-qa",
    }


def test_parse_frontmatter_missing_block() -> None:
    with pytest.raises(SkillInventoryError, match="frontmatter"):
        parse_skill_frontmatter("no frontmatter here\n")


def test_parse_frontmatter_rejects_duplicate_key() -> None:
    text = "---\nname: a\ncovers:\n  - data-product:x\ncovers:\n  - data-product:y\n---\n\nB\n"
    with pytest.raises(SkillInventoryError, match="duplicate"):
        parse_skill_frontmatter(text)


def test_parse_frontmatter_rejects_merge_key() -> None:
    text = "---\nbase: &b\n  k: v\nname: <<\n<<: *b\n---\n\nB\n"
    with pytest.raises(SkillInventoryError, match="merge"):
        parse_skill_frontmatter(text)


def test_parse_frontmatter_rejects_nested_duplicate_key() -> None:
    text = "---\nname: a\nmeta:\n  k: 1\n  k: 2\n---\n\nB\n"
    with pytest.raises(SkillInventoryError, match="duplicate"):
        parse_skill_frontmatter(text)


def test_parse_frontmatter_non_mapping() -> None:
    with pytest.raises(SkillInventoryError, match="mapping"):
        parse_skill_frontmatter("---\n- just\n- a list\n---\n\nB\n")

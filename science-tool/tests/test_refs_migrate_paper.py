from __future__ import annotations

from science_tool.refs_migrate import (
    ID_REWRITE_RULES,
    PROSE_REWRITE_RULE,
    TYPE_REWRITE_RULES,
    rewrite_text,
)


def test_id_rewrite_rules_cover_all_yaml_forms() -> None:
    patterns = {pat.pattern for pat, _ in ID_REWRITE_RULES}
    assert "id: article:" in patterns
    assert 'id: "article:' in patterns
    assert "- article:" in patterns
    assert any("[article:" in p for p in patterns)
    assert '"article:' in patterns
    assert "'article:" in patterns


def test_type_rewrite_rules_cover_all_quote_styles() -> None:
    patterns = {pat.pattern for pat, _ in TYPE_REWRITE_RULES}
    assert any("type: article" in p for p in patterns)
    assert any('type: "article"' in p for p in patterns)
    assert any("type: 'article'" in p for p in patterns)


def test_prose_rewrite_rule_uses_word_boundary() -> None:
    pat, _ = PROSE_REWRITE_RULE
    assert "\\b" in pat.pattern
    assert "article" in pat.pattern


def test_migrate_rewrites_id_field() -> None:
    before = '---\nid: article:Smith2024\ntype: "article"\n---\n\n# Body\n'
    after, count = rewrite_text(before)
    assert "id: paper:Smith2024" in after
    assert 'type: "paper"' in after
    assert count >= 2


def test_migrate_rewrites_related_list_inline() -> None:
    before = "related: [article:Smith2024, article:Jones2023]\n"
    after, count = rewrite_text(before)
    assert after == "related: [paper:Smith2024, paper:Jones2023]\n"
    assert count == 2


def test_migrate_rewrites_related_list_multiline() -> None:
    before = "related:\n  - article:Smith2024\n  - article:Jones2023\n"
    after, count = rewrite_text(before)
    assert "- paper:Smith2024" in after
    assert "- paper:Jones2023" in after
    assert count == 2


def test_migrate_rewrites_prose_mentions() -> None:
    before = "See article:Smith2024 for the full argument.\n"
    after, count = rewrite_text(before)
    assert after == "See paper:Smith2024 for the full argument.\n"
    assert count == 1


def test_migrate_preserves_particle_substrings() -> None:
    before = "The particle:muon and particle-physics community.\n"
    after, count = rewrite_text(before)
    assert after == before
    assert count == 0


def test_migrate_preserves_cite_prefix() -> None:
    before = "source_refs: [cite:Smith2024]\n"
    after, count = rewrite_text(before)
    assert after == before
    assert count == 0


def test_migrate_idempotent() -> None:
    before = "id: article:Smith2024\n"
    once, _ = rewrite_text(before)
    twice, count = rewrite_text(once)
    assert twice == once
    assert count == 0

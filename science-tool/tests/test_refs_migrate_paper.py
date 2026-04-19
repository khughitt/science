from __future__ import annotations

from pathlib import Path

from science_tool.refs_migrate import (
    ID_REWRITE_RULES,
    PROSE_REWRITE_RULE,
    TYPE_REWRITE_RULES,
    rewrite_text,
    scan_project,
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


FIXTURE = Path(__file__).parent / "fixtures" / "refs" / "legacy_project"


def test_scan_project_finds_all_rewrites() -> None:
    rewrites = scan_project(FIXTURE)
    assert len(rewrites) >= 4  # q01, Smith2024, t01, i01
    totals = {r.path.name: r.match_count for r in rewrites}
    assert totals["q01-example.md"] >= 3  # list items + prose
    assert totals["Smith2024.md"] >= 2  # id + type
    assert totals["t01-example.md"] >= 1  # inline-list
    assert totals["i01-example.md"] >= 1  # prose, NOT particle:muon


def test_scan_project_on_migrated_returns_empty() -> None:
    # Apply migration to an in-memory copy; re-scanning a migrated snapshot
    # would produce no rewrites. We verify by rewriting every file's text
    # and confirming the count is now 0.
    rewrites = scan_project(FIXTURE)
    for r in rewrites:
        _, n = __import__("science_tool.refs_migrate", fromlist=["rewrite_text"]).rewrite_text(r.new_text)
        assert n == 0, f"{r.path.name} not idempotent"


def test_scan_project_counts_are_accurate() -> None:
    rewrites = scan_project(FIXTURE)
    for r in rewrites:
        assert r.new_text != r.original_text
        assert r.match_count > 0

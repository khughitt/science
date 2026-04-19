from __future__ import annotations

from science_tool.refs_migrate import ID_REWRITE_RULES, TYPE_REWRITE_RULES, PROSE_REWRITE_RULE


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

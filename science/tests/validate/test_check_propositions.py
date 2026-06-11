"""Tests for proposition structural QA checks — polarity/predicate sign-aptitude."""

from __future__ import annotations

from pathlib import Path

from science_tool.validate import Severity, ValidateContext


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_manifest(root: Path) -> None:
    root.joinpath("science.yaml").write_text(
        "\n".join(
            [
                "name: demo",
                "created: 2026-01-01",
                "last_modified: 2026-01-02",
                "status: active",
                "summary: Demo project",
                "profile: research",
                "layout_version: 1",
                "knowledge_profiles:",
                "  local: knowledge/local",
            ]
        ),
        encoding="utf-8",
    )


def _ctx(root: Path) -> ValidateContext:
    _write_manifest(root)
    return ValidateContext.from_project_root(root, strict=False, verbose=False)


def _write(root: Path, rel: str, body: str) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")
    return p


def _write_proposition(root: Path, slug: str, predicate: str, polarity: str | None = None) -> Path:
    lines = [
        "---",
        f"id: proposition:{slug}",
        "kind: proposition",
        f"predicate: {predicate}",
    ]
    if polarity is not None:
        lines.append(f"polarity: {polarity}")
    lines.append("---")
    return _write(root, f"entities/propositions/{slug}.md", "\n".join(lines) + "\n")


# ---------------------------------------------------------------------------
# Rule: proposition.polarity.aptitude
# Sign-LESS predicate (e.g. binds) with a polarity other than not_applicable → ERROR
# ---------------------------------------------------------------------------


def test_sign_less_predicate_with_positive_polarity_errors(tmp_path: Path) -> None:
    from science_tool.validate.checks.propositions import check_polarity_predicate_aptitude

    p = _write_proposition(tmp_path, "p1", predicate="binds", polarity="positive")

    results = list(check_polarity_predicate_aptitude(_ctx(tmp_path)))

    assert len(results) == 1
    r = results[0]
    assert r.severity == Severity.ERROR
    assert r.rule == "proposition.polarity.aptitude"
    assert r.path == p


def test_sign_less_predicate_with_not_applicable_polarity_is_clean(tmp_path: Path) -> None:
    from science_tool.validate.checks.propositions import check_polarity_predicate_aptitude

    _write_proposition(tmp_path, "p1", predicate="binds", polarity="not_applicable")

    results = list(check_polarity_predicate_aptitude(_ctx(tmp_path)))

    assert results == []


# ---------------------------------------------------------------------------
# Sign-MEANINGFUL predicate (e.g. affects) with valid signed polarity → no error
# ---------------------------------------------------------------------------


def test_sign_meaningful_predicate_with_positive_polarity_is_clean(tmp_path: Path) -> None:
    from science_tool.validate.checks.propositions import check_polarity_predicate_aptitude

    _write_proposition(tmp_path, "p1", predicate="affects", polarity="positive")

    results = list(check_polarity_predicate_aptitude(_ctx(tmp_path)))

    assert results == []


def test_sign_meaningful_predicate_with_negative_polarity_is_clean(tmp_path: Path) -> None:
    from science_tool.validate.checks.propositions import check_polarity_predicate_aptitude

    _write_proposition(tmp_path, "p1", predicate="affects", polarity="negative")

    results = list(check_polarity_predicate_aptitude(_ctx(tmp_path)))

    assert results == []


def test_sign_meaningful_predicate_with_unsigned_polarity_is_clean(tmp_path: Path) -> None:
    from science_tool.validate.checks.propositions import check_polarity_predicate_aptitude

    _write_proposition(tmp_path, "p1", predicate="affects", polarity="unsigned")

    results = list(check_polarity_predicate_aptitude(_ctx(tmp_path)))

    assert results == []


# ---------------------------------------------------------------------------
# Sign-MEANINGFUL predicate with not_applicable or missing polarity → ERROR
# ---------------------------------------------------------------------------


def test_sign_meaningful_predicate_with_not_applicable_polarity_errors(tmp_path: Path) -> None:
    from science_tool.validate.checks.propositions import check_polarity_predicate_aptitude

    p = _write_proposition(tmp_path, "p1", predicate="affects", polarity="not_applicable")

    results = list(check_polarity_predicate_aptitude(_ctx(tmp_path)))

    assert len(results) == 1
    r = results[0]
    assert r.severity == Severity.ERROR
    assert r.rule == "proposition.polarity.aptitude"
    assert r.path == p


def test_sign_meaningful_predicate_with_missing_polarity_errors(tmp_path: Path) -> None:
    from science_tool.validate.checks.propositions import check_polarity_predicate_aptitude

    p = _write_proposition(tmp_path, "p1", predicate="affects", polarity=None)

    results = list(check_polarity_predicate_aptitude(_ctx(tmp_path)))

    assert len(results) == 1
    r = results[0]
    assert r.severity == Severity.ERROR
    assert r.rule == "proposition.polarity.aptitude"
    assert r.path == p


# ---------------------------------------------------------------------------
# Other sign-meaningful predicates (regulates, associates_with)
# ---------------------------------------------------------------------------


def test_regulates_with_positive_polarity_is_clean(tmp_path: Path) -> None:
    from science_tool.validate.checks.propositions import check_polarity_predicate_aptitude

    _write_proposition(tmp_path, "p1", predicate="regulates", polarity="positive")

    results = list(check_polarity_predicate_aptitude(_ctx(tmp_path)))

    assert results == []


def test_associates_with_with_not_applicable_polarity_errors(tmp_path: Path) -> None:
    from science_tool.validate.checks.propositions import check_polarity_predicate_aptitude

    p = _write_proposition(tmp_path, "p1", predicate="associates_with", polarity="not_applicable")

    results = list(check_polarity_predicate_aptitude(_ctx(tmp_path)))

    assert len(results) == 1
    r = results[0]
    assert r.severity == Severity.ERROR
    assert r.rule == "proposition.polarity.aptitude"
    assert r.path == p


# ---------------------------------------------------------------------------
# No predicate set → check is silent (nothing to validate)
# ---------------------------------------------------------------------------


def test_no_predicate_emits_no_results(tmp_path: Path) -> None:
    from science_tool.validate.checks.propositions import check_polarity_predicate_aptitude

    _write(
        tmp_path,
        "entities/propositions/p1.md",
        "---\nid: proposition:p1\nkind: proposition\n---\n",
    )

    results = list(check_polarity_predicate_aptitude(_ctx(tmp_path)))

    assert results == []


# ---------------------------------------------------------------------------
# Empty propositions directory → silent
# ---------------------------------------------------------------------------


def test_empty_propositions_dir_is_clean(tmp_path: Path) -> None:
    from science_tool.validate.checks.propositions import check_polarity_predicate_aptitude

    (tmp_path / "entities" / "propositions").mkdir(parents=True)

    results = list(check_polarity_predicate_aptitude(_ctx(tmp_path)))

    assert results == []


# ---------------------------------------------------------------------------
# No propositions directory at all → silent
# ---------------------------------------------------------------------------


def test_no_propositions_dir_is_clean(tmp_path: Path) -> None:
    from science_tool.validate.checks.propositions import check_polarity_predicate_aptitude

    results = list(check_polarity_predicate_aptitude(_ctx(tmp_path)))

    assert results == []

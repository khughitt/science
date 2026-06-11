"""Unit tests for science_tool.markers."""
from pathlib import Path

import pytest

from science_tool.markers import (
    DEFAULT_SEVERITY,
    LEGACY_ALIASES,
    TOKENS,
    MarkerHit,
    severity_for,
)


def test_tokens_are_the_four_canonical_names() -> None:
    assert TOKENS == ("UNVERIFIED", "MISSING_CITATION", "SPECULATION", "INACCESSIBLE")


def test_default_severity_table() -> None:
    assert DEFAULT_SEVERITY == {
        "UNVERIFIED": "warn",
        "MISSING_CITATION": "warn",
        "SPECULATION": "info",
        "INACCESSIBLE": "info",
    }


def test_legacy_alias_maps_needs_citation_to_missing_citation() -> None:
    assert LEGACY_ALIASES == {"NEEDS CITATION": "MISSING_CITATION"}


def test_severity_for_warn_token_default() -> None:
    assert severity_for("UNVERIFIED", strict=False) == "warn"
    assert severity_for("MISSING_CITATION", strict=False) == "warn"


def test_severity_for_info_token_default() -> None:
    assert severity_for("SPECULATION", strict=False) == "info"
    assert severity_for("INACCESSIBLE", strict=False) == "info"


def test_severity_for_strict_promotes_info_to_warn() -> None:
    assert severity_for("SPECULATION", strict=True) == "warn"
    assert severity_for("INACCESSIBLE", strict=True) == "warn"


def test_severity_for_strict_keeps_warn_as_warn() -> None:
    assert severity_for("UNVERIFIED", strict=True) == "warn"


def test_marker_hit_is_frozen_dataclass() -> None:
    hit = MarkerHit(
        file=Path("doc/x.md"),
        line=10,
        token="UNVERIFIED",
        severity="warn",
        in_documentation=False,
        legacy=False,
    )
    with pytest.raises(Exception):
        hit.line = 11  # type: ignore[misc]


from science_tool.markers import scan_text


def test_scan_text_finds_bare_unverified() -> None:
    hits = scan_text(Path("x.md"), "Some fact [UNVERIFIED] here.\n", strict=False)
    assert len(hits) == 1
    h = hits[0]
    assert h.token == "UNVERIFIED"
    assert h.severity == "warn"
    assert h.in_documentation is False
    assert h.legacy is False
    assert h.line == 1


def test_scan_text_excludes_backticked_token() -> None:
    text = "Mark the claim with `[UNVERIFIED]` per the convention.\n"
    hits = scan_text(Path("x.md"), text, strict=False)
    assert len(hits) == 1
    assert hits[0].in_documentation is True


def test_scan_text_excludes_fenced_code_block() -> None:
    text = "Prose [UNVERIFIED] one.\n```\nblock [UNVERIFIED]\n```\nprose [UNVERIFIED] two.\n"
    hits = scan_text(Path("x.md"), text, strict=False)
    bare = [h for h in hits if not h.in_documentation]
    fenced = [h for h in hits if h.in_documentation]
    assert len(bare) == 2
    assert len(fenced) == 1
    assert fenced[0].line == 3


def test_scan_text_strips_frontmatter() -> None:
    text = "---\ntitle: '[UNVERIFIED] in title'\n---\nbody [UNVERIFIED] here\n"
    hits = scan_text(Path("x.md"), text, strict=False)
    # Frontmatter token is excluded entirely; body token is kept.
    assert len(hits) == 1
    assert hits[0].line == 4


def test_scan_text_recognizes_all_four_tokens() -> None:
    text = "[UNVERIFIED] [MISSING_CITATION] [SPECULATION] [INACCESSIBLE]\n"
    hits = scan_text(Path("x.md"), text, strict=False)
    tokens = sorted(h.token for h in hits)
    assert tokens == ["INACCESSIBLE", "MISSING_CITATION", "SPECULATION", "UNVERIFIED"]


def test_scan_text_legacy_needs_citation_recognized() -> None:
    hits = scan_text(Path("x.md"), "Old style [NEEDS CITATION] here\n", strict=False)
    assert len(hits) == 1
    assert hits[0].token == "MISSING_CITATION"
    assert hits[0].legacy is True


def test_scan_text_strict_promotes_info_tokens() -> None:
    hits = scan_text(Path("x.md"), "[SPECULATION] [INACCESSIBLE]\n", strict=True)
    severities = {h.token: h.severity for h in hits}
    assert severities["SPECULATION"] == "warn"
    assert severities["INACCESSIBLE"] == "warn"


def test_scan_text_multiple_tokens_per_line() -> None:
    hits = scan_text(Path("x.md"), "Two on one line: [UNVERIFIED] and [SPECULATION].\n", strict=False)
    assert len(hits) == 2
    assert {h.token for h in hits} == {"UNVERIFIED", "SPECULATION"}
    assert {h.line for h in hits} == {1}


def test_scan_text_default_severity_for_speculation_is_info() -> None:
    hits = scan_text(Path("x.md"), "[SPECULATION]\n", strict=False)
    assert hits[0].severity == "info"


def test_scan_text_default_severity_for_inaccessible_is_info() -> None:
    hits = scan_text(Path("x.md"), "[INACCESSIBLE]\n", strict=False)
    assert hits[0].severity == "info"


def test_scan_text_skips_hash_headings() -> None:
    # Headings already excluded by refs.py for hypothesis matching; mirror that
    # for markers so an `## [INACCESSIBLE] section` heading isn't double-counted.
    # NB: bracketed token in a heading is unusual but should still be a marker
    # because headings can carry warning intent. Keep heading scanning ON.
    hits = scan_text(Path("x.md"), "## [UNVERIFIED] heading\n", strict=False)
    assert len(hits) == 1


from science_tool.markers import scan_markers


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_scan_markers_walks_doc_and_specs(tmp_path: Path) -> None:
    _write(tmp_path / "doc" / "a.md", "alpha [UNVERIFIED]\n")
    _write(tmp_path / "specs" / "b.md", "beta [SPECULATION]\n")
    _write(tmp_path / "RESEARCH_PLAN.md", "gamma [INACCESSIBLE]\n")
    hits = scan_markers(tmp_path, strict=False)
    files = sorted(h.file.name for h in hits)
    assert files == ["RESEARCH_PLAN.md", "a.md", "b.md"]


def test_scan_markers_walks_entities_v3_layout(tmp_path: Path) -> None:
    # v3 migration moves source-authored entities into entities/<kind>/; markers
    # in those bodies must still be scanned (regression: entities/ was unscanned).
    _write(tmp_path / "entities" / "papers" / "Foo2024.md", "claim [UNVERIFIED]\n")
    hits = scan_markers(tmp_path, strict=False)
    assert [h.file.name for h in hits] == ["Foo2024.md"]


def test_scan_markers_skips_templates_and_venv(tmp_path: Path) -> None:
    _write(tmp_path / "doc" / "templates" / "skip.md", "[UNVERIFIED]\n")
    _write(tmp_path / "doc" / ".venv" / "skip.md", "[UNVERIFIED]\n")
    _write(tmp_path / "doc" / "keep.md", "[UNVERIFIED]\n")
    hits = scan_markers(tmp_path, strict=False)
    assert {h.file.name for h in hits} == {"keep.md"}


def test_scan_markers_excludes_documentation_by_default(tmp_path: Path) -> None:
    _write(tmp_path / "doc" / "a.md", "Use the `[UNVERIFIED]` token. Bare [UNVERIFIED] flagged.\n")
    hits = scan_markers(tmp_path, strict=False)
    assert len(hits) == 1
    assert hits[0].in_documentation is False


def test_scan_markers_includes_documentation_when_requested(tmp_path: Path) -> None:
    _write(tmp_path / "doc" / "a.md", "Use the `[UNVERIFIED]` token. Bare [UNVERIFIED] flagged.\n")
    hits = scan_markers(tmp_path, strict=False, include_documentation=True)
    assert len(hits) == 2


def test_scan_markers_strict_promotes_info(tmp_path: Path) -> None:
    _write(tmp_path / "doc" / "a.md", "[SPECULATION]\n")
    hits = scan_markers(tmp_path, strict=True)
    assert hits[0].severity == "warn"

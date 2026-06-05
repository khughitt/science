from __future__ import annotations

from pathlib import Path

from science_tool.entity_layout_migration import LegacyEntity, discover_legacy_entities


def _write(root: Path, rel: str, text: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def test_discovers_specs_and_doc_legacy_locations(tmp_path: Path) -> None:
    _write(tmp_path, "specs/hypotheses/h01-x.md", '---\nid: "hypothesis:h01-x"\ntype: hypothesis\n---\n')
    _write(tmp_path, "doc/questions/q05-y.md", '---\nid: "question:q05-y"\ntype: question\n---\n')
    _write(tmp_path, "doc/background/papers/Adams2025.md", '---\nid: "paper:Adams2025"\ntype: paper\n---\n')
    found = {e.rel_path: e for e in discover_legacy_entities(tmp_path)}
    assert "specs/hypotheses/h01-x.md" in found
    assert found["specs/hypotheses/h01-x.md"].kind == "hypothesis"
    assert found["doc/questions/q05-y.md"].kind == "question"
    assert found["doc/background/papers/Adams2025.md"].kind == "paper"


def test_ignores_already_migrated_entities_dir(tmp_path: Path) -> None:
    _write(tmp_path, "entities/questions/0001-x.md", '---\nid: "question:0001-x"\ntype: question\n---\n')
    assert discover_legacy_entities(tmp_path) == []


def test_infers_synthesis_singleton_by_path(tmp_path: Path) -> None:
    # Frontmatterless legacy synthesis singleton: parent dir is "reports", which
    # the derived map would call `report`. The by-path override must classify it
    # as synthesis (matching discussions.py's legacy treatment).
    raw = tmp_path / "doc/reports/synthesis.md"
    raw.parent.mkdir(parents=True, exist_ok=True)
    raw.write_text("# Synthesis\n\nText.\n", encoding="utf-8")
    found = {e.rel_path: e for e in discover_legacy_entities(tmp_path)}
    assert found["doc/reports/synthesis.md"].kind == "synthesis"


def test_unrecognized_frontmatter_type_is_skipped(tmp_path: Path) -> None:
    # A file whose frontmatter type is not a known markdown entity kind (e.g.
    # "concept") must be silently excluded from discovery results.
    _write(tmp_path, "doc/concepts/foo.md", "---\ntype: concept\n---\nBody.\n")
    found = {e.rel_path: e for e in discover_legacy_entities(tmp_path)}
    assert "doc/concepts/foo.md" not in found


def test_frontmatterless_file_under_unknown_parent_dir_is_skipped(tmp_path: Path) -> None:
    # A frontmatterless file whose parent directory cannot be mapped to a known
    # entity kind must produce no discovery result.
    _write(tmp_path, "doc/misc/foo.md", "Some prose.\n")
    found = {e.rel_path: e for e in discover_legacy_entities(tmp_path)}
    assert "doc/misc/foo.md" not in found


from science_tool.entity_layout_migration import synthesize_frontmatter


from science_tool.entities import valid_statuses


def test_synthesize_from_prose_headers() -> None:
    body = "# h01 phase-1 results\n\n**Date:** 2026-05-23\n**Status:** First real-run\n\nText.\n"
    fm = synthesize_frontmatter(kind="interpretation", body=body, fallback_created="2026-01-01")
    assert fm["type"] == "interpretation"
    assert fm["created"] == "2026-05-23"   # parsed from **Date:**
    # "First real-run" is NOT a controlled interpretation status → falls back to
    # the per-kind default. Synthesized status must always be a valid value.
    assert fm["status"] in valid_statuses("interpretation")
    assert "title" in fm and fm["title"]


def test_synthesize_uses_controlled_default_status_per_kind() -> None:
    # Defaults are per-kind controlled values (NOT a blanket "active"):
    # hypothesis → "proposed", proposition → "draft".
    h = synthesize_frontmatter(kind="hypothesis", body="Just text.\n", fallback_created="2026-02-02")
    assert h["status"] in valid_statuses("hypothesis")
    assert h["status"] == "proposed"
    p = synthesize_frontmatter(kind="proposition", body="Just text.\n", fallback_created="2026-02-02")
    assert p["status"] == "draft"


def test_synthesize_uses_fallback_when_no_headers() -> None:
    fm = synthesize_frontmatter(kind="finding", body="Just text.\n", fallback_created="2026-02-02")
    assert fm["created"] == "2026-02-02"
    assert fm["type"] == "finding"
    assert fm["status"] in valid_statuses("finding")

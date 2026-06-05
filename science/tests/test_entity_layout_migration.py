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
from science_tool.entity_layout_migration import plan_migration


from science_tool.entities import valid_statuses


def test_plan_assigns_numeric_in_created_order(tmp_path: Path) -> None:
    _write(tmp_path, "doc/questions/q05-late.md",
           '---\nid: "question:q05-late"\ntype: question\ncreated: "2026-02-01"\n---\n')
    _write(tmp_path, "doc/questions/aging-early.md",
           '---\nid: "question:aging-early"\ntype: question\ncreated: "2026-01-01"\n---\n')
    plan = plan_migration(tmp_path)
    # earliest created gets 0001
    by_old = {m.old_id: m for m in plan.moves}
    assert by_old["question:aging-early"].new_id == "question:0001-aging-early"
    assert by_old["question:q05-late"].new_id == "question:0002-late"
    assert plan.id_map["question:aging-early"] == "question:0001-aging-early"


def test_plan_keeps_citekey_for_papers(tmp_path: Path) -> None:
    _write(tmp_path, "doc/background/papers/Adams2025.md", '---\nid: "paper:Adams2025"\ntype: paper\n---\n')
    plan = plan_migration(tmp_path)
    move = plan.moves[0]
    assert move.new_id == "paper:Adams2025"
    assert move.new_rel_path == "entities/papers/Adams2025.md"


def test_plan_preserves_already_conformant_numbers(tmp_path: Path) -> None:
    _write(tmp_path, "specs/hypotheses/0003-x.md", '---\nid: "hypothesis:0003-x"\ntype: hypothesis\n---\n')
    plan = plan_migration(tmp_path)
    assert plan.moves[0].new_id == "hypothesis:0003-x"


def test_plan_date_prefixed_slug_drops_the_date(tmp_path: Path) -> None:
    _write(tmp_path, "doc/interpretations/2026-05-23-foo-bar.md",
           '---\nid: "interpretation:2026-05-23-foo-bar"\ntype: interpretation\ncreated: "2026-05-23"\n---\n')
    plan = plan_migration(tmp_path)
    # slug is "foo-bar", NOT "05-23-foo-bar"
    assert plan.moves[0].new_id == "interpretation:0001-foo-bar"


def test_plan_uses_synthesized_created_for_frontmatterless(tmp_path: Path) -> None:
    # No frontmatter: created must come from the prose **Date:** header so ordering is right.
    _write_raw = (tmp_path / "doc/interpretations/early.md")
    _write_raw.parent.mkdir(parents=True, exist_ok=True)
    _write_raw.write_text("# Early result\n\n**Date:** 2026-01-01\n", encoding="utf-8")
    _write(tmp_path, "doc/interpretations/2026-12-31-late.md",
           '---\nid: "interpretation:2026-12-31-late"\ntype: interpretation\ncreated: "2026-12-31"\n---\n')
    plan = plan_migration(tmp_path)
    paths = {m.new_rel_path for m in plan.moves}
    # The prose-dated file (2026-01-01) sorts first → 0001.
    assert "entities/interpretations/0001-early-result.md" in paths


def test_plan_maps_frontmatterless_stem_alias(tmp_path: Path) -> None:
    # A prose-header file has no `old_id`. References to it use the old filename
    # stem (`interpretation:early`). The plan must map that stem alias to the new
    # id so rewrite_references can fix the link instead of reporting it unresolved.
    raw = tmp_path / "doc/interpretations/early.md"
    raw.parent.mkdir(parents=True, exist_ok=True)
    raw.write_text("# Early result\n\n**Date:** 2026-01-01\n", encoding="utf-8")
    plan = plan_migration(tmp_path)
    assert plan.id_map["interpretation:early"] == "interpretation:0001-early-result"


def test_plan_detects_duplicate_target_collision(tmp_path: Path) -> None:
    # Two papers with the same citekey from the two legacy paper homes.
    _write(tmp_path, "doc/papers/Adams2025.md", '---\nid: "paper:Adams2025"\ntype: paper\n---\n')
    _write(tmp_path, "doc/background/papers/Adams2025.md", '---\nid: "paper:Adams2025"\ntype: paper\n---\n')
    plan = plan_migration(tmp_path)
    assert plan.collisions  # non-empty: same new_rel_path / new_id


def test_plan_detects_duplicate_number_collision(tmp_path: Path) -> None:
    # Two already-conformant files share number 0003 → different ids/paths, but a
    # number-hygiene violation that path/id collision checks alone would miss.
    _write(tmp_path, "specs/hypotheses/0003-a.md", '---\nid: "hypothesis:0003-a"\ntype: hypothesis\n---\n')
    _write(tmp_path, "specs/hypotheses/0003-b.md", '---\nid: "hypothesis:0003-b"\ntype: hypothesis\n---\n')
    plan = plan_migration(tmp_path)
    assert any(c.get("kind") == "number" and c.get("number") == "0003" for c in plan.collisions)


def test_plan_relocates_singletons(tmp_path: Path) -> None:
    _write(tmp_path, "specs/research-question.md", '---\nid: "rq:x"\ntitle: RQ\nstatus: active\n---\n')
    (tmp_path / "specs/claim-registry.yaml").write_text("claims: []\n", encoding="utf-8")
    plan = plan_migration(tmp_path)
    targets = {s.new_rel_path for s in plan.singletons}
    assert "entities/research-question.md" in targets
    assert "entities/claim-registry.yaml" in targets


def test_plan_reserves_numbers_already_under_entities(tmp_path: Path) -> None:
    # Partial migration: entities/questions/0001-* already exists (created
    # additively). A new legacy question must take 0002, NOT collide on 0001.
    _write(tmp_path, "entities/questions/0001-existing.md",
           '---\nid: "question:0001-existing"\ntype: question\n---\n')
    _write(tmp_path, "doc/questions/new-one.md",
           '---\nid: "question:new-one"\ntype: question\ncreated: "2026-01-01"\n---\n')
    plan = plan_migration(tmp_path)
    move = next(m for m in plan.moves if m.old_id == "question:new-one")
    assert move.new_id == "question:0002-new-one"


def test_plan_reports_disk_collision_for_citekey(tmp_path: Path) -> None:
    # entities/papers/Adams2025.md already on disk; a legacy paper would land on
    # the same path → blocking disk collision.
    _write(tmp_path, "entities/papers/Adams2025.md", '---\nid: "paper:Adams2025"\ntype: paper\n---\n')
    _write(tmp_path, "doc/background/papers/Adams2025.md", '---\nid: "paper:Adams2025"\ntype: paper\n---\n')
    plan = plan_migration(tmp_path)
    assert any(c["kind"] == "disk" and c["target"] == "entities/papers/Adams2025.md" for c in plan.collisions)


def test_plan_reports_conformant_number_taken_under_entities(tmp_path: Path) -> None:
    # A conformant legacy hypothesis 0003-x wants to keep 0003, but entities/
    # already holds a different 0003 → blocking number collision.
    _write(tmp_path, "entities/hypotheses/0003-other.md",
           '---\nid: "hypothesis:0003-other"\ntype: hypothesis\n---\n')
    _write(tmp_path, "specs/hypotheses/0003-x.md",
           '---\nid: "hypothesis:0003-x"\ntype: hypothesis\n---\n')
    plan = plan_migration(tmp_path)
    assert any(c.get("kind") == "number" and c.get("number") == "0003"
               and c.get("occupied_by") == "entities/" for c in plan.collisions)


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

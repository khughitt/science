from __future__ import annotations

import subprocess
from pathlib import Path

import pytest as _pytest
import yaml

from science_tool.entities import valid_statuses
from science_tool.entity_layout_migration import (
    discover_legacy_entities,
    migrate_layout,
    plan_migration,
    rewrite_references,
    synthesize_frontmatter,
)


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


def test_plan_ambiguous_stem_alias_not_silently_mis_mapped(tmp_path: Path) -> None:
    # Two frontmatterless files with the same stem under the same kind but from
    # two different legacy scan roots (doc/ and specs/) both want alias
    # `interpretation:foo`.  The plan must NOT keep a wrong mapping; it must
    # remove the alias from id_map and record a blocking alias collision.
    body = "# Foo\n\n**Date:** 2026-01-01\n"
    _write(tmp_path, "doc/interpretations/foo.md", body)
    _write(tmp_path, "specs/interpretations/foo.md", body)
    plan = plan_migration(tmp_path)
    # The ambiguous alias must be absent from id_map.
    assert "interpretation:foo" not in plan.id_map
    # A blocking alias collision must be recorded.
    assert any(c.get("kind") == "alias" and c.get("alias") == "interpretation:foo"
               for c in plan.collisions)


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


def test_rewrite_replaces_full_ids_not_prefix_collisions() -> None:
    id_map = {"question:q1-a": "question:0001-a", "question:q10-b": "question:0010-b"}
    text = "See question:q1-a and question:q10-b and related: [question:q1-a]\n"
    out, unresolved = rewrite_references(text, id_map)
    assert "question:0001-a" in out and "question:0010-b" in out
    assert "question:q1-a" not in out  # q1 not corrupted by q10 replacement
    assert unresolved == []


def test_rewrite_reports_unmapped_legacy_tokens() -> None:
    # A legacy-shaped reference with no mapping must be reported, never silently kept.
    id_map = {"question:q1-a": "question:0001-a"}
    text = "Depends on hypothesis:h9-ghost which no longer exists.\n"
    out, unresolved = rewrite_references(text, id_map)
    assert "hypothesis:h9-ghost" in unresolved


def test_rewrite_reports_bare_wikilink() -> None:
    # A bare [[q01-foo]] (no kind prefix) cannot be auto-rewritten; it must be
    # surfaced as unresolved rather than silently left as a dead link.
    out, unresolved = rewrite_references("See [[q01-foo]] for context.\n", {})
    assert "[[q01-foo]]" in unresolved


def test_rewrite_reports_unmapped_plain_slug_reference() -> None:
    # A stale ref to a deleted entity by its OLD plain slug (no q##-/date shape).
    # It is unmapped and does not conform to the numeric policy, so it must be
    # reported — the legacy-shape-only heuristic would have silently kept it.
    id_map = {"question:aging-early": "question:0001-aging-early"}
    text = "Mapped question:aging-early. Dangling question:old-slug stays.\n"
    out, unresolved = rewrite_references(text, id_map)
    assert "question:0001-aging-early" in out
    assert "question:old-slug" in unresolved


def test_rewrite_leaves_external_and_conformant_tokens_alone() -> None:
    # A conformant id and an external/unmanaged prefix must NOT be flagged.
    id_map = {"question:q1-a": "question:0001-a"}
    text = "Canonical question:0002-keep and external doi:10.1/x and url https://e.org.\n"
    out, unresolved = rewrite_references(text, id_map)
    assert unresolved == []


def test_rewrite_handles_kind_qualified_wikilink() -> None:
    # A kind-qualified wikilink [[question:...]] is handled by token replacement /
    # branch (a), NOT the bare-wikilink branch. A MAPPED one is rewritten; an
    # UNMAPPED non-conformant one is reported as unresolved.
    id_map = {"question:q1-a": "question:0001-a"}
    out, unresolved = rewrite_references("See [[question:q1-a]] and [[question:q9-ghost]].\n", id_map)
    assert "[[question:0001-a]]" in out          # mapped wikilink rewritten in place
    assert "question:q9-ghost" in unresolved     # unmapped, non-conformant → reported
    assert "[[question:q9-ghost]]" not in unresolved  # reported as the token, not the bare-link form


# ---------------------------------------------------------------------------
# Task 5: migrate_layout orchestrator tests
# ---------------------------------------------------------------------------


def _git_init(root: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "seed"], cwd=root, check=True)


def test_migrate_dry_run_makes_no_changes(tmp_path: Path) -> None:
    _write(tmp_path, "science.yaml", "name: t\nlayout_version: 2\n")
    _write(tmp_path, "specs/hypotheses/h01-alpha.md", '---\nid: "hypothesis:h01-alpha"\ntype: hypothesis\ncreated: "2026-01-01"\ntitle: Alpha\nstatus: proposed\nupdated: "2026-01-01"\n---\nbody\n')
    _git_init(tmp_path)
    report = migrate_layout(tmp_path, apply=False)
    assert report["moves"]
    assert (tmp_path / "specs/hypotheses/h01-alpha.md").exists()  # untouched
    assert not (tmp_path / "entities/hypotheses").exists()


def test_migrate_apply_moves_and_rewrites(tmp_path: Path) -> None:
    _write(tmp_path, "science.yaml", "name: t\nlayout_version: 2\n")
    _write(tmp_path, "specs/hypotheses/h01-alpha.md", '---\nid: "hypothesis:h01-alpha"\ntype: hypothesis\ncreated: "2026-01-01"\ntitle: Alpha\nstatus: proposed\nupdated: "2026-01-01"\n---\nbody\n')
    _write(tmp_path, "doc/questions/q01-beta.md", '---\nid: "question:q01-beta"\ntype: question\ncreated: "2026-01-02"\ntitle: Beta\nstatus: active\nupdated: "2026-01-02"\nrelated: ["hypothesis:h01-alpha"]\n---\nSee hypothesis:h01-alpha.\n')
    _git_init(tmp_path)
    _ = migrate_layout(tmp_path, apply=True)
    assert (tmp_path / "entities/hypotheses/0001-alpha.md").is_file()
    q = (tmp_path / "entities/questions/0001-beta.md").read_text()
    assert "hypothesis:0001-alpha" in q          # related + inline ref rewritten
    assert "hypothesis:h01-alpha" not in q
    manifest = yaml.safe_load((tmp_path / "science.yaml").read_text())
    assert manifest["layout_version"] == 3


def test_migrate_apply_rewrites_tasks_inplace(tmp_path: Path) -> None:
    """(a) tasks/t001.md containing hypothesis:h01-alpha is rewritten to hypothesis:0001-alpha."""
    _write(tmp_path, "science.yaml", "name: t\nlayout_version: 2\n")
    _write(tmp_path, "specs/hypotheses/h01-alpha.md", '---\nid: "hypothesis:h01-alpha"\ntype: hypothesis\ncreated: "2026-01-01"\ntitle: Alpha\nstatus: proposed\nupdated: "2026-01-01"\n---\nbody\n')
    _write(tmp_path, "tasks/t001.md", "---\nid: task:t001\ntype: task\nstatus: active\ncreated: \"2026-01-03\"\ntitle: Check\nupdated: \"2026-01-03\"\n---\nDepends on hypothesis:h01-alpha.\n")
    _git_init(tmp_path)
    _ = migrate_layout(tmp_path, apply=True)
    task_text = (tmp_path / "tasks/t001.md").read_text()
    assert "hypothesis:0001-alpha" in task_text
    assert "hypothesis:h01-alpha" not in task_text


def test_migrate_apply_rewrites_singleton_yaml(tmp_path: Path) -> None:
    """(b) specs/claim-registry.yaml referencing hypothesis:h01-alpha lands at entities/claim-registry.yaml with ref rewritten."""
    _write(tmp_path, "science.yaml", "name: t\nlayout_version: 2\n")
    _write(tmp_path, "specs/hypotheses/h01-alpha.md", '---\nid: "hypothesis:h01-alpha"\ntype: hypothesis\ncreated: "2026-01-01"\ntitle: Alpha\nstatus: proposed\nupdated: "2026-01-01"\n---\nbody\n')
    (tmp_path / "specs/claim-registry.yaml").write_text(
        "claims:\n  - id: hypothesis:h01-alpha\n    note: tracked\n", encoding="utf-8"
    )
    _git_init(tmp_path)
    _ = migrate_layout(tmp_path, apply=True)
    assert (tmp_path / "entities/claim-registry.yaml").is_file()
    content = (tmp_path / "entities/claim-registry.yaml").read_text()
    assert "hypothesis:0001-alpha" in content
    assert "hypothesis:h01-alpha" not in content


def test_migrate_collision_blocks_apply(tmp_path: Path) -> None:
    """(c) A project with two Adams2025.md paper sources raises ValueError under apply=True and lists the collision in the dry-run report."""
    _write(tmp_path, "science.yaml", "name: t\nlayout_version: 2\n")
    _write(tmp_path, "doc/papers/Adams2025.md", '---\nid: "paper:Adams2025"\ntype: paper\ncreated: "2026-01-01"\ntitle: Adams 2025\nupdated: "2026-01-01"\n---\n')
    _write(tmp_path, "doc/background/papers/Adams2025.md", '---\nid: "paper:Adams2025"\ntype: paper\ncreated: "2026-01-01"\ntitle: Adams 2025\nupdated: "2026-01-01"\n---\n')
    _git_init(tmp_path)
    dry = migrate_layout(tmp_path, apply=False)
    assert dry["collisions"]
    with _pytest.raises(ValueError, match="collisions"):
        migrate_layout(tmp_path, apply=True)


def test_migrate_apply_rewrites_inplace_prose_doc(tmp_path: Path) -> None:
    """(d) A prose doc file containing hypothesis:h01-alpha and [[hypothesis:h01-alpha]] is rewritten in place.
    Uses doc/context/ — a directory not in _DIR_TO_KIND — so the file is not
    misclassified as a legacy entity; it exercises the in-place-text code path."""
    _write(tmp_path, "science.yaml", "name: t\nlayout_version: 2\n")
    _write(tmp_path, "specs/hypotheses/h01-alpha.md", '---\nid: "hypothesis:h01-alpha"\ntype: hypothesis\ncreated: "2026-01-01"\ntitle: Alpha\nstatus: proposed\nupdated: "2026-01-01"\n---\nbody\n')
    _write(tmp_path, "doc/context/summary.md", "See hypothesis:h01-alpha and [[hypothesis:h01-alpha]] for details.\n")
    _git_init(tmp_path)
    _ = migrate_layout(tmp_path, apply=True)
    summary = (tmp_path / "doc/context/summary.md").read_text()
    assert "hypothesis:0001-alpha" in summary
    assert "hypothesis:h01-alpha" not in summary


def test_migrate_unresolved_ref_blocks_apply(tmp_path: Path) -> None:
    """(e) A prose doc file containing a dead hypothesis:h99-ghost token causes apply=True to raise ValueError
    and dry-run lists it under unresolved_references.
    Uses doc/context/ — not in _DIR_TO_KIND — so it is not mis-discovered as an entity."""
    _write(tmp_path, "science.yaml", "name: t\nlayout_version: 2\n")
    _write(tmp_path, "specs/hypotheses/h01-alpha.md", '---\nid: "hypothesis:h01-alpha"\ntype: hypothesis\ncreated: "2026-01-01"\ntitle: Alpha\nstatus: proposed\nupdated: "2026-01-01"\n---\nbody\n')
    _write(tmp_path, "doc/context/summary.md", "See hypothesis:h99-ghost which is dead.\n")
    _git_init(tmp_path)
    dry = migrate_layout(tmp_path, apply=False)
    assert dry["unresolved_references"]
    assert any("hypothesis:h99-ghost" in tokens for tokens in dry["unresolved_references"].values())
    with _pytest.raises(ValueError, match="unresolved"):
        migrate_layout(tmp_path, apply=True)


# ---------------------------------------------------------------------------
# Fix A/B/C lock-in tests
# ---------------------------------------------------------------------------


def test_migrate_undated_entity_blocks_apply_and_is_reported(tmp_path: Path) -> None:
    """Fix A: a legacy entity with no **Date:** and no frontmatter created is
    reported under undated_entities in the dry-run and blocks apply=True BEFORE
    any mutation (the source file must still exist after the failed apply call)."""
    _write(tmp_path, "science.yaml", "name: t\nlayout_version: 2\n")
    # Frontmatterless entity with no **Date:** header — no date is derivable.
    _write(tmp_path, "doc/questions/no-date.md", "# No date question\n\nText.\n")
    _git_init(tmp_path)

    # Dry-run: undated_entities is populated.
    dry = migrate_layout(tmp_path, apply=False)
    assert "undated_entities" in dry
    assert dry["undated_entities"], "dry-run must list the undated entity"
    old_paths = [d["old_rel_path"] for d in dry["undated_entities"]]
    assert "doc/questions/no-date.md" in old_paths

    # apply=True: raises ValueError mentioning "undated" — no files moved.
    with _pytest.raises(ValueError, match="undated"):
        migrate_layout(tmp_path, apply=True)

    # Source file must still exist (no git mv happened).
    assert (tmp_path / "doc/questions/no-date.md").exists()
    assert not (tmp_path / "entities").exists()


def test_migrate_version_not_bumped_when_audit_fails(tmp_path: Path) -> None:
    """Fix B: when the graph audit fails post-move, layout_version must NOT be
    bumped to 3 and the error must carry rollback guidance.

    Audit failure mechanism: after migration the question's `related` list
    contains `hypothesis:9999-nope`, which conforms to the numeric local-part
    policy (so rewrite_references does NOT flag it as unresolved) but points at
    a nonexistent entity, causing audit_project_sources to return failed=True
    with an 'unresolved_reference' row."""
    _write(tmp_path, "science.yaml", "name: t\nlayout_version: 2\n")
    # The hypothesis has no related dangling ref — it migrates cleanly.
    _write(
        tmp_path,
        "specs/hypotheses/h01-alpha.md",
        '---\nid: "hypothesis:h01-alpha"\ntype: hypothesis\ncreated: "2026-01-01"\n'
        'title: Alpha\nstatus: proposed\nupdated: "2026-01-01"\n---\nbody\n',
    )
    # The question has a valid date (not blocked by Fix A) and a related ref that
    # is conformant-shaped but points to a nonexistent entity, triggering the
    # graph audit to fail after the files are moved.
    _write(
        tmp_path,
        "doc/questions/q01-myq.md",
        '---\nid: "question:q01-myq"\ntype: question\ncreated: "2026-01-02"\n'
        'title: My Q\nstatus: active\nupdated: "2026-01-02"\n'
        'related: ["hypothesis:9999-nope"]\n---\nBody.\n',
    )
    _git_init(tmp_path)

    with _pytest.raises(ValueError, match="working tree"):
        migrate_layout(tmp_path, apply=True)

    # layout_version must NOT have been bumped.
    manifest = yaml.safe_load((tmp_path / "science.yaml").read_text())
    assert manifest.get("layout_version") == 2


def test_plan_does_not_crash_on_typed_singleton(tmp_path: Path) -> None:
    # Real-project case: specs/research-question.md carries `type: research-question`
    # (a singleton kind with NO status vocabulary). It must be relocated via the
    # singleton path rule, NOT synthesized/numbered (which would KeyError).
    _write(tmp_path, "specs/research-question.md",
           '---\nid: "research-question:main"\ntype: research-question\ntitle: RQ\nstatus: active\n---\nBody.\n')
    plan = plan_migration(tmp_path)
    # relocated as a singleton, not a numbered move
    assert any(s.new_rel_path == "entities/research-question.md" for s in plan.singletons)
    assert all(m.kind != "research-question" for m in plan.moves)


def test_migrate_apply_is_idempotent(tmp_path: Path) -> None:
    """Fix C: running migrate_layout(apply=True) twice on a fully-migrated project
    is safe: the second call returns moves==[] and does not raise, and
    layout_version is still 3."""
    _write(tmp_path, "science.yaml", "name: t\nlayout_version: 2\n")
    _write(
        tmp_path,
        "specs/hypotheses/h01-alpha.md",
        '---\nid: "hypothesis:h01-alpha"\ntype: hypothesis\ncreated: "2026-01-01"\n'
        'title: Alpha\nstatus: proposed\nupdated: "2026-01-01"\n---\nbody\n',
    )
    _git_init(tmp_path)

    # First apply.
    report1 = migrate_layout(tmp_path, apply=True)
    assert report1["moves"]

    assert yaml.safe_load((tmp_path / "science.yaml").read_text())["layout_version"] == 3

    # Stage and commit the migrated state so git mv on the second run can succeed
    # (or, more precisely, so the second plan sees no legacy entities to move).
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "post-migrate"],
        cwd=tmp_path,
        check=True,
    )

    # Second apply — no legacy entities remain, so moves == [].
    report2 = migrate_layout(tmp_path, apply=True)
    assert report2["moves"] == []
    assert yaml.safe_load((tmp_path / "science.yaml").read_text())["layout_version"] == 3


# ---------------------------------------------------------------------------
# Pilot-driven fixes (FIX 1, FIX 2, FIX 3)
# ---------------------------------------------------------------------------


# FIX 1: rewrite numeric/prefixed shortform references -------------------


def test_plan_registers_numeric_shortform_alias(tmp_path: Path) -> None:
    """FIX 1: a question file with stem '01-foo-bar' (id question:01-foo-bar) must
    produce an id_map entry question:01 -> question:0001 so prose shortform
    references like 'question:01' are rewritten to the new number."""
    _write(tmp_path, "doc/questions/01-foo-bar.md",
           '---\nid: "question:01-foo-bar"\ntype: question\ncreated: "2026-01-01"\n---\n')
    plan = plan_migration(tmp_path)
    assert plan.id_map.get("question:01") == "question:0001", (
        f"expected question:01 -> question:0001 in id_map; got {plan.id_map}"
    )


def test_plan_registers_prefixed_shortform_alias(tmp_path: Path) -> None:
    """FIX 1: a hypothesis file with stem 'h03-baz' (id hypothesis:h03-baz) must
    produce id_map entry hypothesis:h03 -> hypothesis:0001 (the assigned number)."""
    _write(tmp_path, "specs/hypotheses/h03-baz.md",
           '---\nid: "hypothesis:h03-baz"\ntype: hypothesis\ncreated: "2026-01-01"\n'
           'status: proposed\ntitle: Baz\n---\n')
    plan = plan_migration(tmp_path)
    assert plan.id_map.get("hypothesis:h03") == "hypothesis:0001", (
        f"expected hypothesis:h03 -> hypothesis:0001 in id_map; got {plan.id_map}"
    )


def test_rewrite_rewrites_numeric_shortform(tmp_path: Path) -> None:
    """FIX 1: with id_map built from plan, rewrite_references rewrites both the
    shortform 'question:01' and the full id 'question:01-foo-bar' to the new form;
    no unresolved refs remain."""
    _write(tmp_path, "doc/questions/01-foo-bar.md",
           '---\nid: "question:01-foo-bar"\ntype: question\ncreated: "2026-01-01"\n---\n')
    plan = plan_migration(tmp_path)
    text = "See question:01 and question:01-foo-bar."
    out, unresolved = rewrite_references(text, plan.id_map)
    assert "question:0001" in out, f"shortform not rewritten in: {out!r}"
    assert "question:0001-foo-bar" in out, f"full id not rewritten in: {out!r}"
    assert "question:01" not in out, f"old shortform still present in: {out!r}"
    assert unresolved == [], f"unexpected unresolved: {unresolved}"


def test_plan_no_shortform_alias_for_non_shortform_topic(tmp_path: Path) -> None:
    """FIX 1 guard: a topic 'topic:foo-bar' must NOT produce a bogus alias
    'topic:foo' — the old_token 'foo' is pure letters, not a shortform shape."""
    _write(tmp_path, "doc/topics/foo-bar.md",
           '---\nid: "topic:foo-bar"\ntype: topic\ncreated: "2026-01-01"\n'
           'status: active\ntitle: Foo Bar\n---\n')
    plan = plan_migration(tmp_path)
    assert "topic:foo" not in plan.id_map, (
        f"spurious shortform alias 'topic:foo' must not appear; id_map={plan.id_map}"
    )


# FIX 2: scope unresolved policing to migrated kinds ----------------------


def test_migrate_does_not_flag_unmigrated_kind(tmp_path: Path) -> None:
    """FIX 2: a reference to 'observation:swan-foo' in a doc file must NOT appear
    in unresolved_references when there are no observation markdown files in the
    project (observation stored in YAML registry, not markdown).

    Contrast: a reference to a non-existent question 'question:99-ghost' (a kind
    that IS migrated as markdown) MUST still be reported."""
    _write(tmp_path, "science.yaml", "name: t\nlayout_version: 2\n")
    _write(tmp_path, "doc/questions/q01-myq.md",
           '---\nid: "question:q01-myq"\ntype: question\ncreated: "2026-01-01"\n'
           'title: My Q\nstatus: active\nupdated: "2026-01-01"\n---\nBody.\n')
    # doc/context/ is not in _DIR_TO_KIND, so this file is not mis-discovered as an entity.
    _write(tmp_path, "doc/context/notes.md",
           "See observation:swan-foo and question:99-ghost for context.\n")
    _git_init(tmp_path)
    report = migrate_layout(tmp_path, apply=False)
    all_unresolved_tokens: list[str] = [
        token
        for tokens in report["unresolved_references"].values()
        for token in tokens
    ]
    assert "observation:swan-foo" not in all_unresolved_tokens, (
        "observation:swan-foo must not be flagged (observation not a migrated markdown kind)"
    )
    assert "question:99-ghost" in all_unresolved_tokens, (
        "question:99-ghost must be flagged (question IS a migrated kind with no mapping)"
    )


# FIX 3: filename-date fallback for `created` -----------------------------


def test_plan_filename_date_fallback_for_plan_file(tmp_path: Path) -> None:
    """FIX 3: a plan file 'doc/plans/2026-05-30-paper-triage-manifest.md' with no
    frontmatter and no **Date:** header must use 2026-05-30 (from the filename) as
    its created date — NOT fall back to the undated sentinel."""
    _write(tmp_path, "science.yaml", "name: t\nlayout_version: 2\n")
    _write(tmp_path, "doc/plans/2026-05-30-paper-triage-manifest.md",
           "# Paper Triage Manifest\n\ntext\n")
    _git_init(tmp_path)
    report = migrate_layout(tmp_path, apply=False)
    assert report["undated_entities"] == [], (
        f"filename-dated plan must not appear in undated_entities; got {report['undated_entities']}"
    )


def test_plan_truly_undated_non_date_filename_is_still_reported(tmp_path: Path) -> None:
    """FIX 3 complement: a plan file 'doc/plans/misc-notes.md' with no frontmatter,
    no **Date:** header, and a non-date filename must still be reported as undated."""
    _write(tmp_path, "science.yaml", "name: t\nlayout_version: 2\n")
    _write(tmp_path, "doc/plans/misc-notes.md",
           "# Misc Notes\n\nSome prose with no date.\n")
    _git_init(tmp_path)
    report = migrate_layout(tmp_path, apply=False)
    old_paths = [d["old_rel_path"] for d in report["undated_entities"]]
    assert "doc/plans/misc-notes.md" in old_paths, (
        "truly undated file (no frontmatter, no **Date:**, non-date filename) must be reported undated"
    )


# ---------------------------------------------------------------------------
# YAML registry in-place rewrite (pilot: observations.yaml broke graph audit)
# ---------------------------------------------------------------------------


def test_migrate_rewrites_yaml_registry_inplace(tmp_path: Path) -> None:
    """A YAML file under doc/ containing an entity reference must have that
    reference rewritten in place after apply=True.

    Uses doc/notes.yaml (a plain YAML file, not a graph-audited registry) to
    isolate the in-place-yaml-rewrite behaviour without triggering the
    observations-schema graph loader.  The file stays at its original path; only
    its contents change.
    """
    _write(tmp_path, "science.yaml", "name: t\nlayout_version: 2\n")
    _write(
        tmp_path,
        "specs/hypotheses/h01-alpha.md",
        '---\nid: "hypothesis:h01-alpha"\ntype: hypothesis\ncreated: "2026-01-01"\n'
        'title: Alpha\nstatus: proposed\nupdated: "2026-01-01"\n---\nbody\n',
    )
    # A plain YAML file in doc/ that references the hypothesis by old id.
    _write(
        tmp_path,
        "doc/notes.yaml",
        "related:\n  - hypothesis:h01-alpha\n",
    )
    _git_init(tmp_path)
    migrate_layout(tmp_path, apply=True)
    content = (tmp_path / "doc/notes.yaml").read_text()
    assert "hypothesis:0001-alpha" in content, f"old id not rewritten; content: {content!r}"
    assert "hypothesis:h01-alpha" not in content, f"old id still present; content: {content!r}"


def test_migrate_rewrites_knowledge_yaml_inplace(tmp_path: Path) -> None:
    """A YAML file under knowledge/ containing an entity reference must be
    rewritten in place — confirms that the knowledge/ root is walked.
    """
    _write(tmp_path, "science.yaml", "name: t\nlayout_version: 2\n")
    _write(
        tmp_path,
        "specs/hypotheses/h01-alpha.md",
        '---\nid: "hypothesis:h01-alpha"\ntype: hypothesis\ncreated: "2026-01-01"\n'
        'title: Alpha\nstatus: proposed\nupdated: "2026-01-01"\n---\nbody\n',
    )
    # A plain YAML file in knowledge/sources/local/ that references the hypothesis.
    _write(
        tmp_path,
        "knowledge/sources/local/relations.yaml",
        "relations:\n  - source: hypothesis:h01-alpha\n    target: other:foo\n",
    )
    _git_init(tmp_path)
    migrate_layout(tmp_path, apply=True)
    content = (tmp_path / "knowledge/sources/local/relations.yaml").read_text()
    assert "hypothesis:0001-alpha" in content, f"old id not rewritten; content: {content!r}"
    assert "hypothesis:h01-alpha" not in content, f"old id still present; content: {content!r}"


def test_migrate_leaves_manifest_science_yaml_unrewritten_as_ref(tmp_path: Path) -> None:
    """science.yaml at the project root is NOT in the in-place walk; it is only
    touched by the version bump (layout_version: 3).  A value that resembles
    nothing like an entity id must survive unchanged; layout_version must be 3.
    """
    _write(
        tmp_path,
        "science.yaml",
        "name: my-project\nlayout_version: 2\ncustom_field: some-plain-value\n",
    )
    _write(
        tmp_path,
        "specs/hypotheses/h01-alpha.md",
        '---\nid: "hypothesis:h01-alpha"\ntype: hypothesis\ncreated: "2026-01-01"\n'
        'title: Alpha\nstatus: proposed\nupdated: "2026-01-01"\n---\nbody\n',
    )
    _git_init(tmp_path)
    migrate_layout(tmp_path, apply=True)
    manifest = yaml.safe_load((tmp_path / "science.yaml").read_text())
    assert manifest["layout_version"] == 3, "layout_version must be bumped to 3"
    assert manifest["name"] == "my-project", "name field must survive unchanged"
    assert manifest.get("custom_field") == "some-plain-value", "unrelated fields must survive"


# ---------------------------------------------------------------------------
# Task 5: local-kind discovery + id-prefix kind inference
# ---------------------------------------------------------------------------

_LOCAL_PROFILE = """\
name: t-local
imports:
  - core
strictness: typed-extension
entity_kinds:
  - name: design
    canonical_prefix: design
    layer: layer/local
    description: Design.
relation_kinds: []
"""


def _with_local_profile(root) -> None:
    _write(root, "science.yaml", "name: t\nknowledge_profiles:\n  local: local\n")
    _write(root, "knowledge/sources/local/manifest.yaml", _LOCAL_PROFILE)


def test_discovers_local_kind_by_type(tmp_path) -> None:
    _with_local_profile(tmp_path)
    _write(tmp_path, "doc/design/x.md",
           '---\nid: "design:x"\ntype: design\ncreated: "2026-01-01"\n---\nbody\n')
    found = {e.rel_path: e for e in discover_legacy_entities(tmp_path)}
    assert found["doc/design/x.md"].kind == "design"


def test_infers_local_kind_from_id_prefix_in_foreign_dir(tmp_path) -> None:
    # No `type:`, file lives under doc/plans/ — dir-name fallback would say "plan".
    # The `id:` prefix (design) must win.
    _with_local_profile(tmp_path)
    _write(tmp_path, "doc/plans/y.md",
           '---\nid: "design:y"\ncreated: "2026-01-01"\n---\nbody\n')
    found = {e.rel_path: e for e in discover_legacy_entities(tmp_path)}
    assert found["doc/plans/y.md"].kind == "design"


def test_explicit_type_wins_over_divergent_id_prefix(tmp_path) -> None:
    _with_local_profile(tmp_path)
    _write(tmp_path, "doc/plans/z.md",
           '---\nid: "design:z"\ntype: plan\ncreated: "2026-01-01"\n---\nbody\n')
    found = {e.rel_path: e for e in discover_legacy_entities(tmp_path)}
    assert found["doc/plans/z.md"].kind == "plan"


def test_unknown_id_prefix_does_not_classify(tmp_path) -> None:
    # No kind "widget" is registered — id "widget:w" must not win; the file falls
    # through to the dir-name fallback ("plan" for doc/plans/).
    _with_local_profile(tmp_path)
    _write(tmp_path, "doc/plans/w.md",
           '---\nid: "widget:w"\ncreated: "2026-01-01"\n---\nbody\n')
    found = {e.rel_path: e for e in discover_legacy_entities(tmp_path)}
    assert found["doc/plans/w.md"].kind == "plan"

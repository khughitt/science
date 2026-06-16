"""End-to-end: scaffold -> fill body -> apply -> graph + validate clean (P4)."""
from __future__ import annotations

from pathlib import Path

from science_tool.archive import load_archive_index, unarchive_entities, verify_archive
from science_tool.consolidate import apply_consolidation, scaffold_digest
from science_tool.entities import _parse_markdown_file, _render_markdown, create_entity
from science_tool.graph.materialize import materialize_graph
from science_tool.validate.checks.cross_references import check_archive_index, check_cross_references
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Severity


def _project(tmp_path: Path) -> Path:
    (tmp_path / "science.yaml").write_text("name: t\nknowledge_profiles:\n  local: local\n", encoding="utf-8")
    return tmp_path


def test_full_consolidation_lifecycle(tmp_path: Path) -> None:
    root = _project(tmp_path)
    create_entity(root, "finding", "Partition test A", entity_id="finding:0001-a")
    create_entity(root, "finding", "Partition test B", entity_id="finding:0002-b")

    # 1. scaffold
    rep = scaffold_digest(root, digest_id="synthesis:0001-d",
                          member_ids=["finding:0001-a", "finding:0002-b"], title="Partition tests digest")
    digest_path = Path(rep["digest_path"])

    # 2. a human/agent fills the digest body
    fm, body = _parse_markdown_file(digest_path)
    digest_path.write_text(_render_markdown(fm, body.rstrip() + "\n\nThe partition tests converge.\n"), encoding="utf-8")

    # 3. apply
    out = apply_consolidation(root, "synthesis:0001-d", apply=True, now="T1")
    assert set(out["applied"]) == {"finding:0001-a", "finding:0002-b"}

    # 4. members archived + indexed; archive index self-consistent
    idx = load_archive_index(root)
    assert set(idx.active_by_id) == {"finding:0001-a", "finding:0002-b"}
    live_space = {"synthesis:0001-d"}
    assert verify_archive(root, live_space) == []

    # 5. graph builds; digest still live, members are tombstones (not rehydrated)
    out_path = materialize_graph(root, strict=False)
    text = out_path.read_text(encoding="utf-8")
    assert "consolidates" in text and "ArchivedEntity" in text
    assert (root / "entities" / "synthesis" / "0001-d.md").exists()
    assert not (root / "entities" / "findings" / "0001-a.md").exists()

    # 6. validate is clean: archive index reconciles + no broken cross-references.
    #    (check_archive_index yields one INFO "consistent" when clean, ERROR on a problem.)
    ctx = ValidateContext.from_project_root(root, strict=True, verbose=False)
    arch_results = list(check_archive_index(ctx))
    assert not any(r.severity == Severity.ERROR for r in arch_results)
    assert any("consistent" in r.message for r in arch_results)
    xref_results = list(check_cross_references(ctx))
    assert not any(r.severity == Severity.ERROR for r in xref_results)

    # 7. reversibility: unarchive restores a member to its original path (location only)
    unarchive_entities(root, ["finding:0001-a"], apply=True, now="T2")
    assert (root / "entities" / "findings" / "0001-a.md").exists()
    assert "finding:0001-a" not in load_archive_index(root).active_by_id

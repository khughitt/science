# tests/test_p5_tier4_acceptance.py
"""P5 Tier-4 acceptance: consolidating a bridging interpretation family leaves
big-picture seeing ONE labeled digest with N descendable members, and the q<->h
bridge SURVIVES via the digest's authored related: edges (the residual-risk path)."""
from __future__ import annotations

from pathlib import Path

from science_tool.big_picture.digests import load_cluster_digests
from science_tool.big_picture.resolver import resolve_questions
from science_tool.consolidate import apply_consolidation, scaffold_digest
from science_tool.entities import _parse_markdown_file, _render_markdown, create_entity


def _set_related(path: Path, refs: list[str]) -> None:
    fm, body = _parse_markdown_file(path)
    fm["related"] = refs
    path.write_text(_render_markdown(fm, body), encoding="utf-8")


def test_bridge_survives_consolidation(tmp_path: Path) -> None:
    root = tmp_path
    (root / "science.yaml").write_text(
        "name: t\nknowledge_profiles:\n  local: local\n", encoding="utf-8")

    create_entity(root, "question", "Q one", entity_id="question:0001-q")
    create_entity(root, "hypothesis", "H one", entity_id="hypothesis:0001-h")
    create_entity(root, "interpretation", "Interp 1", entity_id="interpretation:0001-i1")
    create_entity(root, "interpretation", "Interp 2", entity_id="interpretation:0002-i2")
    # Both interpretations bridge q01 <-> h01.
    for stem in ("0001-i1", "0002-i2"):
        _set_related(root / "entities" / "interpretations" / f"{stem}.md",
                     ["question:0001-q", "hypothesis:0001-h"])

    # BEFORE: q resolves to h transitively, via the live interpretations.
    before = resolve_questions(root)
    assert before["question:0001-q"].primary_hypothesis == "hypothesis:0001-h"

    # Consolidate the family into a digest authored WITH the same q/h related: edges.
    scaffold_digest(root, digest_id="synthesis:0001-d",
                    member_ids=["interpretation:0001-i1", "interpretation:0002-i2"],
                    title="Interp digest")
    _set_related(root / "entities" / "synthesis" / "0001-d.md",
                 ["question:0001-q", "hypothesis:0001-h"])
    applied = apply_consolidation(root, "synthesis:0001-d", apply=True, now="T1")
    assert set(applied["applied"]) == {"interpretation:0001-i1", "interpretation:0002-i2"}

    # Members are gone from the live scan; the digest stands in as ONE entry with
    # N descendable members (index-only).
    assert not (root / "entities" / "interpretations" / "0001-i1.md").exists()
    digests = load_cluster_digests(root, deep=True)
    assert set(digests) == {"synthesis:0001-d"}
    d = digests["synthesis:0001-d"]
    assert d.member_count == 2
    assert {m.id for m in d.members} == {"interpretation:0001-i1", "interpretation:0002-i2"}
    assert all(m.archived for m in d.members)

    # AFTER: the q<->h bridge SURVIVES — now carried by the digest.
    after = resolve_questions(root)
    assert after["question:0001-q"].primary_hypothesis == "hypothesis:0001-h"
    m = next(x for x in after["question:0001-q"].hypotheses if x.id == "hypothesis:0001-h")
    assert m.confidence == "transitive"

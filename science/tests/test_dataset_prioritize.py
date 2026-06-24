# tests/test_dataset_prioritize.py
from __future__ import annotations

from science_tool.dataset_prioritize import readiness_for, readiness_weight


def _ext(level: str, verified: bool, availability: str = "available") -> dict:
    return {
        "id": "dataset:x", "type": "dataset", "title": "X", "status": "candidate",
        "origin": "external", "tier": "track",
        "access": {"level": level, "availability": availability, "verified": verified},
        "ontology_terms": [], "related": [],
    }


def test_readiness_for_reuses_canonical_states() -> None:
    assert readiness_for(_ext("public", False)).state == "public, unverified"
    assert readiness_for(_ext("controlled", True)).state == "available"
    assert readiness_for(_ext("public", False, availability="embargoed")).state == "embargoed"


def test_readiness_weight_ordering_and_flagged_default() -> None:
    # available > unverified-public > unverified-controlled > embargoed
    w_avail, f_avail = readiness_weight(_ext("controlled", True))
    w_pub, _ = readiness_weight(_ext("public", False))
    w_ctrl, _ = readiness_weight(_ext("controlled", False))
    w_emb, _ = readiness_weight(_ext("public", False, availability="embargoed"))
    assert w_avail == 1.0
    assert w_avail > w_pub > w_ctrl > w_emb
    assert f_avail == []
    # an unparseable / unknown-origin entity flags rather than silently bucketing
    w_unk, f_unk = readiness_weight({"id": "dataset:b", "type": "dataset", "title": "B"})
    assert w_unk == 0.1
    assert "readiness-unresolved" in f_unk


from pathlib import Path

from science_tool.dataset_prioritize import frontmatter_reach


def _write(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def test_frontmatter_reach_both_directions_excludes_source_refs(tmp_path: Path) -> None:
    # dataset A points outward to a question; question Q2 points back to dataset B.
    _write(tmp_path / "entities/datasets/a.md",
           '---\nid: "dataset:a"\ntype: "dataset"\ntitle: "A"\n'
           'related: ["question:q1", "topic:t1"]\n---\n')
    _write(tmp_path / "entities/datasets/b.md",
           '---\nid: "dataset:b"\ntype: "dataset"\ntitle: "B"\n'
           'source_refs: ["question:qX"]\n---\n')  # source_refs must NOT count
    _write(tmp_path / "entities/questions/q1.md",
           '---\nid: "question:q1"\ntype: "question"\ntitle: "Q1"\n---\n')
    _write(tmp_path / "entities/questions/q2.md",
           '---\nid: "question:q2"\ntype: "question"\ntitle: "Q2"\nrelated: ["dataset:b"]\n---\n')

    reach = frontmatter_reach(tmp_path)
    assert reach["dataset:a"] == {"question:q1"}          # outgoing; topic ignored
    assert reach["dataset:b"] == {"question:q2"}          # incoming back-edge only
    assert "dataset:b" not in reach.get("dataset:b", set()) or "question:qX" not in reach["dataset:b"]


def test_frontmatter_reach_reads_question_datasets_field(tmp_path: Path) -> None:
    _write(tmp_path / "entities/datasets/d.md",
           '---\nid: "dataset:d"\ntype: "dataset"\ntitle: "D"\nrelated: []\n---\n')
    _write(tmp_path / "entities/questions/q.md",
           '---\nid: "question:q"\ntype: "question"\ntitle: "Q"\n'
           'datasets: ["dataset:d"]\nrelated: []\n---\n')

    reach = frontmatter_reach(tmp_path)

    assert reach["dataset:d"] == {"question:q"}


def test_frontmatter_reach_bridges_consumer_dataset_usage_to_related_qh(tmp_path: Path) -> None:
    _write(tmp_path / "entities/datasets/d.md",
           '---\nid: "dataset:d"\ntype: "dataset"\ntitle: "D"\nrelated: []\n---\n')
    _write(tmp_path / "entities/hypotheses/h.md",
           '---\nid: "hypothesis:h"\ntype: "hypothesis"\ntitle: "H"\n---\n')
    _write(tmp_path / "entities/papers/p.md",
           '---\nid: "paper:p"\ntype: "paper"\ntitle: "P"\n'
           'related: ["hypothesis:h"]\n'
           'dataset_usage:\n'
           '  - ref: "dataset:d"\n'
           '    role: "analyzed"\n'
           '    overlap: "full"\n---\n')

    reach = frontmatter_reach(tmp_path)

    assert reach["dataset:d"] == {"hypothesis:h"}


from science_tool.dataset_prioritize import prioritize


def test_prioritize_sparse_no_graph_orders_by_accessibility_and_flags(tmp_path: Path) -> None:
    # available > unverified public; the unconnected one gets no-edge.
    # dataset:avail is controlled (gated) → include_gated=True keeps it visible so
    # the accessibility ordering can be asserted; the default-exclusion behavior is
    # covered separately by test_prioritize_excludes_gated_by_default.
    _write(tmp_path / "entities/datasets/avail.md",
           '---\nid: "dataset:avail"\ntype: "dataset"\ntitle: "Avail"\norigin: "external"\n'
           'related: ["question:q1"]\naccess: {level: "controlled", verified: true}\n---\n')
    _write(tmp_path / "entities/datasets/unv.md",
           '---\nid: "dataset:unv"\ntype: "dataset"\ntitle: "Unv"\norigin: "external"\n'
           'access: {level: "public", verified: false}\n---\n')
    _write(tmp_path / "entities/questions/q1.md",
           '---\nid: "question:q1"\ntype: "question"\ntitle: "Q1"\n---\n')

    rows = prioritize(tmp_path, include_gated=True)
    ids = [r["id"] for r in rows]
    assert ids[0] == "dataset:avail"                  # verified + reach=1 ranks first
    unv = next(r for r in rows if r["id"] == "dataset:unv")
    assert "unverified" in unv["gap_flags"]
    assert "no-edge" in unv["gap_flags"]              # reach 0
    assert rows[0]["score"] > unv["score"]


def test_prioritize_excludes_gated_by_default(tmp_path: Path) -> None:
    # registration/controlled/commercial are gated; public/mixed and derived (no
    # access block → level "") are actionable and stay. Default hides the gated set.
    _write(tmp_path / "entities/datasets/pub.md",
           '---\nid: "dataset:pub"\ntype: "dataset"\ntitle: "Pub"\norigin: "external"\n'
           'access: {level: "public", verified: false}\n---\n')
    _write(tmp_path / "entities/datasets/mix.md",
           '---\nid: "dataset:mix"\ntype: "dataset"\ntitle: "Mix"\norigin: "external"\n'
           'access: {level: "mixed", verified: false}\n---\n')
    _write(tmp_path / "entities/datasets/reg.md",
           '---\nid: "dataset:reg"\ntype: "dataset"\ntitle: "Reg"\norigin: "external"\n'
           'access: {level: "registration", verified: false}\n---\n')
    _write(tmp_path / "entities/datasets/ctrl.md",
           '---\nid: "dataset:ctrl"\ntype: "dataset"\ntitle: "Ctrl"\norigin: "external"\n'
           'access: {level: "controlled", verified: true}\n---\n')
    _write(tmp_path / "entities/datasets/com.md",
           '---\nid: "dataset:com"\ntype: "dataset"\ntitle: "Com"\norigin: "external"\n'
           'access: {level: "commercial", verified: true}\n---\n')
    _write(tmp_path / "entities/datasets/der.md",
           '---\nid: "dataset:der"\ntype: "dataset"\ntitle: "Der"\norigin: "derived"\n'
           'datapackage: "r/dp.yaml"\n---\n')

    default_ids = {r["id"] for r in prioritize(tmp_path)}
    assert default_ids == {"dataset:pub", "dataset:mix", "dataset:der"}

    # opt-out restores the full set
    all_ids = {r["id"] for r in prioritize(tmp_path, include_gated=True)}
    assert all_ids == {
        "dataset:pub", "dataset:mix", "dataset:der",
        "dataset:reg", "dataset:ctrl", "dataset:com",
    }

    # an explicit level overrides the default exclusion for that level
    ctrl_ids = {r["id"] for r in prioritize(tmp_path, level="controlled")}
    assert ctrl_ids == {"dataset:ctrl"}

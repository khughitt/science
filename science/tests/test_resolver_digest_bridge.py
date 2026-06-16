# tests/test_resolver_digest_bridge.py
from __future__ import annotations

from science_tool.big_picture.resolver import resolve_questions


def _mk(tmp_path):
    (tmp_path / "science.yaml").write_text("name: vis\n", encoding="utf-8")
    for sub in ("questions", "hypotheses", "synthesis"):
        (tmp_path / "entities" / sub).mkdir(parents=True)
    (tmp_path / "entities" / "questions" / "q01.md").write_text(
        '---\nid: "question:q01"\ntype: "question"\n---\nQ.\n', encoding="utf-8")
    (tmp_path / "entities" / "hypotheses" / "h01.md").write_text(
        '---\nid: "hypothesis:h01"\ntype: "hypothesis"\n---\nH.\n', encoding="utf-8")
    return tmp_path


def test_digest_bridges_question_to_hypothesis(tmp_path) -> None:
    root = _mk(tmp_path)
    (root / "entities" / "synthesis" / "0001-d.md").write_text(
        '---\nid: "synthesis:0001-d"\ntitle: "D"\nreport_kind: "cluster-digest"\n'
        'status: "active"\nrelated: ["question:q01", "hypothesis:h01"]\n'
        'relations:\n  - predicate: "sci:consolidates"\n    target: "interpretation:i01-old"\n---\nx\n',
        encoding="utf-8")
    out = resolve_questions(root)
    assert out["question:q01"].primary_hypothesis == "hypothesis:h01"
    m = next(x for x in out["question:q01"].hypotheses if x.id == "hypothesis:h01")
    assert m.confidence == "transitive" and m.score == 0.5


def test_no_digest_means_no_bridge(tmp_path) -> None:
    root = _mk(tmp_path)
    out = resolve_questions(root)
    assert out["question:q01"].hypotheses == []


def test_non_cluster_digest_synthesis_does_not_bridge(tmp_path) -> None:
    root = _mk(tmp_path)
    (root / "entities" / "synthesis" / "0001-r.md").write_text(
        '---\nid: "synthesis:0001-r"\nreport_kind: "synthesis-rollup"\nstatus: "active"\n'
        'related: ["question:q01", "hypothesis:h01"]\n---\nx\n', encoding="utf-8")
    out = resolve_questions(root)
    assert out["question:q01"].hypotheses == []  # only cluster-digests bridge


def test_digest_does_not_downgrade_a_direct_match(tmp_path) -> None:
    # q01 declares h01 directly (confidence=direct, score=1.0). A digest that also
    # bridges q01<->h01 must NOT overwrite/downgrade that to transitive — the digest
    # pass runs last and only fills gaps.
    root = _mk(tmp_path)
    (root / "entities" / "questions" / "q01.md").write_text(
        '---\nid: "question:q01"\ntype: "question"\nhypothesis: "hypothesis:h01"\n---\nQ.\n',
        encoding="utf-8")
    (root / "entities" / "synthesis" / "0001-d.md").write_text(
        '---\nid: "synthesis:0001-d"\ntitle: "D"\nreport_kind: "cluster-digest"\n'
        'status: "active"\nrelated: ["question:q01", "hypothesis:h01"]\n'
        'relations:\n  - predicate: "sci:consolidates"\n    target: "interpretation:i01-old"\n---\nx\n',
        encoding="utf-8")
    out = resolve_questions(root)
    matches = [m for m in out["question:q01"].hypotheses if m.id == "hypothesis:h01"]
    assert len(matches) == 1  # not duplicated by the digest pass
    assert matches[0].confidence == "direct" and matches[0].score == 1.0

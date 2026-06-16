# tests/test_knowledge_gaps_digest_bridge.py
from __future__ import annotations

from science_tool.big_picture.knowledge_gaps import compute_topic_gaps
from science_tool.big_picture.resolver import resolve_questions


def test_topic_gap_hypotheses_include_a_digest_bridged_hypothesis(tmp_path) -> None:
    (tmp_path / "science.yaml").write_text("name: vis\n", encoding="utf-8")

    def w(rel, txt):
        p = tmp_path / "entities" / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(txt, encoding="utf-8")

    # topic t01 has demand (q01 references it) and zero paper coverage -> a gap.
    w("topics/t01.md", '---\nid: "topic:t01"\ntype: "topic"\nrelated: []\n---\n')
    w("questions/q01.md", '---\nid: "question:q01"\ntype: "question"\nrelated: ["topic:t01"]\n---\n')
    w("hypotheses/h01.md", '---\nid: "hypothesis:h01"\ntype: "hypothesis"\n---\n')
    # q01 reaches h01 ONLY through the digest bridge (no live interpretation exists).
    w("synthesis/0001-d.md",
      '---\nid: "synthesis:0001-d"\ntitle: "D"\nreport_kind: "cluster-digest"\nstatus: "active"\n'
      'related: ["question:q01", "hypothesis:h01"]\n'
      'relations:\n  - predicate: "sci:consolidates"\n    target: "interpretation:i01-old"\n---\n')

    resolved = resolve_questions(tmp_path)
    assert resolved["question:q01"].primary_hypothesis == "hypothesis:h01"
    gaps = compute_topic_gaps(tmp_path, resolved, included_question_ids=set(resolved))
    t01 = next(g for g in gaps if g.topic_id == "topic:t01")
    assert t01.demand >= 1 and t01.gap_score >= 1
    assert "hypothesis:h01" in t01.hypotheses  # inherited from the resolver's digest bridge

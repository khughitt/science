# tests/test_dataset_prioritize_graph.py
from __future__ import annotations

from pathlib import Path

from science_tool.graph.materialize import materialize_graph
from science_tool.graph.store.dataset import _load_dataset
from science_tool.graph.store.identity import _graph_uri
from science_tool.dataset_prioritize import usage_reach


def _write(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def _seed_graph_project(root: Path) -> None:
    # Minimal connected graph: dataset → evidence-line(dataset_usage) → proposition
    # → hypothesis; question → proposition.
    # IMPORTANT: load_project_sources (graph/sources.py:305) scans entities/ for the
    # 21 layout kinds (questions/hypotheses/propositions/evidence-lines) and
    # doc/datasets/ for datasets. Q/H/P/evidence-lines under doc/ would NOT be
    # materialized — they MUST go under entities/.
    (root / "science.yaml").write_text('slug: "tp"\n', encoding="utf-8")
    _write(root / "doc/datasets/d.md",
           '---\nid: "dataset:d"\ntype: "dataset"\ntitle: "D"\norigin: "external"\n'
           'access: {level: "public", verified: true}\n---\n')
    _write(root / "entities/hypotheses/h.md",
           '---\nid: "hypothesis:h"\ntype: "hypothesis"\ntitle: "H"\n---\n')
    # question→proposition is the sci:addresses edge: author it via a `relations:`
    # block (flattened at sources.py:1047, emitted at materialize.py:1173). A plain
    # `related:` would materialize as skos:related, NOT sci:addresses.
    _write(root / "entities/questions/q.md",
           '---\nid: "question:q"\ntype: "question"\ntitle: "Q"\n'
           'relations:\n  - predicate: "sci:addresses"\n    target: "proposition:p"\n---\n')
    _write(root / "entities/propositions/p.md",
           '---\nid: "proposition:p"\ntype: "proposition"\ntitle: "P"\ndiscusses: ["hypothesis:h"]\n---\n')
    _write(root / "entities/evidence-lines/e.md",
           '---\nid: "evidence-line:e"\ntype: "evidence-line"\ntitle: "E"\n'
           'stance: "supports"\ntarget: "proposition:p"\nevidence_type: "empirical_data_evidence"\n'
           'dataset_usage:\n  - ref: "dataset:d"\n    role: "analyzed"\n    overlap: "full"\n---\n')


def test_usage_reach_traverses_to_question_and_hypothesis(tmp_path: Path) -> None:
    _seed_graph_project(tmp_path)
    graph_path = materialize_graph(tmp_path)
    ds = _load_dataset(graph_path)
    knowledge = ds.graph(_graph_uri("graph/knowledge"))
    provenance = ds.graph(_graph_uri("graph/provenance"))

    reach = usage_reach(knowledge, provenance, ["dataset:d"])
    assert reach["dataset:d"] == {"hypothesis:h", "question:q"}

# tests/test_dataset_prioritize_graph.py
from __future__ import annotations

from pathlib import Path

from science_tool.graph.materialize import materialize_graph
from science_tool.graph.store.dataset import _load_dataset, load_dataset
from science_tool.graph.store.identity import _graph_uri, graph_uri
from science_tool.dataset_prioritize import usage_reach, merged_reach
from science_tool.dataset_prioritize import leverage_tilt
from science_tool.dataset_prioritize import prioritize


def _write(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def _seed_graph_project(root: Path) -> None:
    # Minimal connected graph: dataset → evidence-line(dataset_usage) → proposition
    # → hypothesis; question → proposition.
    # IMPORTANT: load_project_sources (graph/sources.py) scans entities/ for every
    # layout kind — questions/hypotheses/propositions/evidence-lines AND datasets.
    # Anything under doc/ would NOT be materialized — they MUST go under entities/.
    (root / "science.yaml").write_text('slug: "tp"\n', encoding="utf-8")
    _write(
        root / "entities/datasets/d.md",
        '---\nid: "dataset:d"\nkind: "dataset"\ntitle: "D"\norigin: "external"\n'
        'access: {level: "public", verified: true}\n---\n',
    )
    _write(root / "entities/hypotheses/h.md", '---\nid: "hypothesis:h"\nkind: "hypothesis"\ntitle: "H"\n---\n')
    # question→proposition is the sci:addresses edge: author it via a `relations:`
    # block (flattened at sources.py:1047, emitted at materialize.py:1173). A plain
    # `related:` would materialize as skos:related, NOT sci:addresses.
    _write(
        root / "entities/questions/q.md",
        '---\nid: "question:q"\nkind: "question"\ntitle: "Q"\n'
        'relations:\n  - predicate: "sci:addresses"\n    target: "proposition:p"\n---\n',
    )
    _write(
        root / "entities/propositions/p.md",
        '---\nid: "proposition:p"\nkind: "proposition"\ntitle: "P"\ndiscusses: ["hypothesis:h"]\n---\n',
    )
    _write(
        root / "entities/evidence-lines/e.md",
        '---\nid: "evidence-line:e"\nkind: "evidence-line"\ntitle: "E"\n'
        'stance: "supports"\ntarget: "proposition:p"\nevidence_type: "empirical_data_evidence"\n'
        'dataset_usage:\n  - ref: "dataset:d"\n    role: "analyzed"\n    overlap: "full"\n---\n',
    )


def test_usage_reach_traverses_to_question_and_hypothesis(tmp_path: Path) -> None:
    _seed_graph_project(tmp_path)
    graph_path = materialize_graph(tmp_path)
    ds = _load_dataset(graph_path)
    knowledge = ds.graph(_graph_uri("graph/knowledge"))
    provenance = ds.graph(_graph_uri("graph/provenance"))

    reach = usage_reach(knowledge, provenance, ["dataset:d"])
    assert reach["dataset:d"] == {"hypothesis:h", "question:q"}


def test_usage_reach_collects_paper_related_qh(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text('slug: "tp"\n', encoding="utf-8")
    _write(
        tmp_path / "entities/datasets/d.md",
        '---\nid: "dataset:d"\nkind: "dataset"\ntitle: "D"\norigin: "external"\n'
        'access: {level: "public", verified: true}\n---\n',
    )
    _write(tmp_path / "entities/hypotheses/h.md", '---\nid: "hypothesis:h"\nkind: "hypothesis"\ntitle: "H"\n---\n')
    _write(
        tmp_path / "entities/papers/p.md",
        '---\nid: "paper:p"\nkind: "paper"\ntitle: "P"\n'
        'related: ["hypothesis:h"]\n'
        "dataset_usage:\n"
        '  - ref: "dataset:d"\n'
        '    role: "analyzed"\n'
        '    overlap: "full"\n---\n',
    )
    graph_path = materialize_graph(tmp_path)
    ds = _load_dataset(graph_path)
    knowledge = ds.graph(_graph_uri("graph/knowledge"))
    provenance = ds.graph(_graph_uri("graph/provenance"))

    reach = usage_reach(knowledge, provenance, ["dataset:d"])

    assert reach["dataset:d"] == {"hypothesis:h"}


def test_usage_reach_unions_consumer_related_qh_with_proposition_path(tmp_path: Path) -> None:
    _seed_graph_project(tmp_path)
    _write(
        tmp_path / "entities/hypotheses/h-related.md",
        '---\nid: "hypothesis:h-related"\nkind: "hypothesis"\ntitle: "H related"\n---\n',
    )
    (tmp_path / "entities/evidence-lines/e.md").write_text(
        '---\nid: "evidence-line:e"\nkind: "evidence-line"\ntitle: "E"\n'
        'stance: "supports"\ntarget: "proposition:p"\nevidence_type: "empirical_data_evidence"\n'
        'related: ["hypothesis:h-related"]\n'
        "dataset_usage:\n"
        '  - ref: "dataset:d"\n'
        '    role: "analyzed"\n'
        '    overlap: "full"\n---\n',
        encoding="utf-8",
    )
    graph_path = materialize_graph(tmp_path)
    ds = _load_dataset(graph_path)
    knowledge = ds.graph(_graph_uri("graph/knowledge"))
    provenance = ds.graph(_graph_uri("graph/provenance"))

    reach = usage_reach(knowledge, provenance, ["dataset:d"])

    assert reach["dataset:d"] == {"hypothesis:h", "hypothesis:h-related", "question:q"}


def test_merged_reach_unions_both_paths_and_dedups(tmp_path: Path) -> None:
    _seed_graph_project(tmp_path)
    # ALSO give dataset:d a frontmatter back-edge to the SAME question:q, while
    # keeping the sci:addresses edge so question:q is reachable via BOTH paths.
    (tmp_path / "entities/questions/q.md").write_text(
        '---\nid: "question:q"\nkind: "question"\ntitle: "Q"\n'
        'relations:\n  - predicate: "sci:addresses"\n    target: "proposition:p"\n'
        'related: ["dataset:d"]\n---\n',
        encoding="utf-8",
    )
    graph_path = materialize_graph(tmp_path)
    ds = _load_dataset(graph_path)
    knowledge = ds.graph(_graph_uri("graph/knowledge"))
    provenance = ds.graph(_graph_uri("graph/provenance"))

    reach = merged_reach(tmp_path, knowledge, provenance, ["dataset:d"])
    # question:q reachable via BOTH paths → counted once; hypothesis:h via usage only
    assert reach["dataset:d"] == {"hypothesis:h", "question:q"}


def test_merged_reach_frontmatter_only_when_no_graph(tmp_path: Path) -> None:
    _seed_graph_project(tmp_path)
    (tmp_path / "entities/questions/q.md").write_text(
        '---\nid: "question:q"\nkind: "question"\ntitle: "Q"\nrelated: ["dataset:d"]\n---\n', encoding="utf-8"
    )
    reach = merged_reach(tmp_path, None, None, ["dataset:d"])
    assert reach["dataset:d"] == {"question:q"}  # frontmatter path works with no graph


def test_leverage_tilt_neutral_when_no_props(tmp_path: Path) -> None:
    _seed_graph_project(tmp_path)
    graph_path = materialize_graph(tmp_path)
    ds = _load_dataset(graph_path)
    knowledge = ds.graph(_graph_uri("graph/knowledge"))
    provenance = ds.graph(_graph_uri("graph/provenance"))
    # a dataset with no usage edges reaches no propositions → tilt is exactly 1.0
    assert leverage_tilt(knowledge, provenance, "dataset:absent") == 1.0


def test_leverage_tilt_bounded_and_responsive(tmp_path: Path) -> None:
    _seed_graph_project(tmp_path)
    graph_path = materialize_graph(tmp_path)
    ds = _load_dataset(graph_path)
    knowledge = ds.graph(_graph_uri("graph/knowledge"))
    provenance = ds.graph(_graph_uri("graph/provenance"))
    tilt = leverage_tilt(knowledge, provenance, "dataset:d")
    assert 1.0 <= tilt <= 2.0  # single-source proposition raises tilt, capped at 2.0


def test_prioritize_mixed_graph_frontmatter_dataset_not_no_edge(tmp_path: Path) -> None:
    _seed_graph_project(tmp_path)  # dataset:d connected via usage
    # a second dataset connected ONLY by frontmatter to question:q (keep the
    # sci:addresses edge intact for dataset:d's usage path)
    (tmp_path / "entities/questions/q.md").write_text(
        '---\nid: "question:q"\nkind: "question"\ntitle: "Q"\n'
        'relations:\n  - predicate: "sci:addresses"\n    target: "proposition:p"\n'
        'related: ["dataset:fm_only"]\n---\n',
        encoding="utf-8",
    )
    (tmp_path / "entities/datasets/fm_only.md").write_text(
        '---\nid: "dataset:fm_only"\nkind: "dataset"\ntitle: "FM"\norigin: "external"\n'
        'access: {level: "public", verified: true}\n---\n',
        encoding="utf-8",
    )
    graph_path = materialize_graph(tmp_path)
    ds = _load_dataset(graph_path)
    knowledge = ds.graph(_graph_uri("graph/knowledge"))
    provenance = ds.graph(_graph_uri("graph/provenance"))

    rows = prioritize(tmp_path, knowledge=knowledge, provenance=provenance)
    fm_only = next(r for r in rows if r["id"] == "dataset:fm_only")
    assert fm_only["reach"] >= 1
    assert "no-edge" not in fm_only["gap_flags"]  # regression for the High review finding


def _seed_multihop_project(root: Path) -> None:
    # dataset:d --usage--> evidence-line:e --supports--> proposition:p
    # p --cito:supports--> p2 --cito:supports--> hypothesis:h2
    # => h2 is reachable from p ONLY via the transitive bearsOn closure at
    #    depth 2. p does NOT `cito:discusses` h2, and no question `sci:addresses`
    #    p, so the pre-upgrade direct-edge walk returns an empty set here.
    (root / "science.yaml").write_text('slug: "tp"\n', encoding="utf-8")
    _write(
        root / "entities/datasets/d.md",
        '---\nid: "dataset:d"\nkind: "dataset"\ntitle: "D"\norigin: "external"\n'
        'access: {level: "public", verified: true}\n---\n',
    )
    _write(root / "entities/hypotheses/h2.md", '---\nid: "hypothesis:h2"\nkind: "hypothesis"\ntitle: "H2"\n---\n')
    _write(
        root / "entities/propositions/p.md",
        '---\nid: "proposition:p"\nkind: "proposition"\ntitle: "P"\n'
        'relations:\n  - predicate: "cito:supports"\n    target: "proposition:p2"\n---\n',
    )
    _write(
        root / "entities/propositions/p2.md",
        '---\nid: "proposition:p2"\nkind: "proposition"\ntitle: "P2"\n'
        'relations:\n  - predicate: "cito:supports"\n    target: "hypothesis:h2"\n---\n',
    )
    _write(
        root / "entities/evidence-lines/e.md",
        '---\nid: "evidence-line:e"\nkind: "evidence-line"\ntitle: "E"\n'
        'stance: "supports"\ntarget: "proposition:p"\nevidence_type: "empirical_data_evidence"\n'
        'dataset_usage:\n  - ref: "dataset:d"\n    role: "analyzed"\n    overlap: "full"\n---\n',
    )


def test_usage_reach_follows_multihop_bearson_closure(tmp_path: Path) -> None:
    _seed_multihop_project(tmp_path)
    graph_path = materialize_graph(tmp_path)
    ds = _load_dataset(graph_path)
    knowledge = ds.graph(_graph_uri("graph/knowledge"))
    provenance = ds.graph(_graph_uri("graph/provenance"))
    # h2 is reachable from proposition:p only via a depth-2 bearsOn chain;
    # the pre-upgrade direct-edge-only walk returned set() for dataset:d.
    reach = usage_reach(knowledge, provenance, ["dataset:d"])
    assert reach["dataset:d"] == {"hypothesis:h2"}


def test_public_load_dataset_and_graph_uri_match_private(tmp_path: Path) -> None:
    """`load_dataset`/`graph_uri` are one-line delegations to `_load_dataset`/`_graph_uri`.

    dataset_prioritize (cli.py) must depend on these public names, never the
    `_`-private store internals, across the CLI/store module boundary.
    """
    _seed_graph_project(tmp_path)
    graph_path = materialize_graph(tmp_path)

    assert graph_uri("graph/knowledge") == _graph_uri("graph/knowledge")
    assert graph_uri("graph/provenance") == _graph_uri("graph/provenance")

    ds_public = load_dataset(graph_path)
    ds_private = _load_dataset(graph_path)
    knowledge_public = ds_public.graph(graph_uri("graph/knowledge"))
    knowledge_private = ds_private.graph(_graph_uri("graph/knowledge"))
    assert set(knowledge_public) == set(knowledge_private)
    assert set(knowledge_public) != set()  # sanity: fixture actually populated this layer

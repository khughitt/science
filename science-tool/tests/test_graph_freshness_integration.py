"""End-to-end integration: materialize_graph emits bears_on + freshness triples."""

from __future__ import annotations

import pytest
from pathlib import Path
from textwrap import dedent

from rdflib import Dataset, URIRef

from science_tool.graph.materialize import materialize_graph
from science_tool.graph.store import PROJECT_NS, SCI_NS


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dedent(content).lstrip("\n"))


def _build_min_project(tmp_path: Path) -> Path:
    """Minimal project with one hypothesis + one task that tests it.

    A task fixture is used (not workflow-run) because materialize.py converts
    `related: [hypothesis:foo]` to a `sci:tests` triple only when the source
    entity's kind is `task` (see `materialize.py:220`). Workflow-runs would
    need an explicit authored sci:tests relation, which is heavier to set up
    in a fixture; the bears_on derivation rule fires identically either way.
    """
    root = tmp_path / "demo"
    _write(root / "science.yaml", """
        name: demo
        knowledge_profiles:
          local: core
    """)
    _write(root / "knowledge" / "graph.trig", "")
    _write(root / "doc" / "hypotheses" / "h1.md", """
        ---
        id: "hypothesis:h1"
        kind: "hypothesis"
        title: "Demo hypothesis"
        created: "2026-04-01"
        updated: "2026-04-01"
        ---
        Body.
    """)
    _write(root / "doc" / "tasks" / "t1.md", """
        ---
        id: "task:t1"
        kind: "task"
        title: "Demo task"
        status: "active"
        created: "2026-05-01"
        updated: "2026-05-01"
        related: ["hypothesis:h1"]
        ---
        Body.
    """)
    return root


def _load_dataset(path: Path) -> Dataset:
    ds = Dataset()
    ds.parse(path, format="trig")
    return ds


def test_materialize_emits_bears_on_when_task_tests_hypothesis(tmp_path: Path):
    root = _build_min_project(tmp_path)
    trig = materialize_graph(root)
    ds = _load_dataset(trig)
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])

    pairs = {(str(s), str(o)) for s, _, o in knowledge.triples((None, SCI_NS.bearsOn, None))}
    task_uri = str(URIRef(PROJECT_NS["task/t1"]))
    h_uri = str(URIRef(PROJECT_NS["hypothesis/h1"]))
    assert (task_uri, h_uri) in pairs


def test_materialize_emits_freshness_state(tmp_path: Path):
    root = _build_min_project(tmp_path)
    trig = materialize_graph(root)
    ds = _load_dataset(trig)
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])

    h_uri = URIRef(PROJECT_NS["hypothesis/h1"])
    states = [str(o) for _, _, o in knowledge.triples((h_uri, SCI_NS.freshnessState, None))]
    # h1.created = 2026-04-01, last_reviewed unset, t1.updated = 2026-05-01 > created => needs-review.
    assert states == ["needs-review"]


def test_materialize_does_not_mutate_entity_files(tmp_path: Path):
    root = _build_min_project(tmp_path)
    h_path = root / "doc" / "hypotheses" / "h1.md"
    before = h_path.read_text()
    before_mtime = h_path.stat().st_mtime_ns

    materialize_graph(root)

    assert h_path.read_text() == before
    assert h_path.stat().st_mtime_ns == before_mtime


def test_materialize_rejects_hand_authored_bears_on_to_non_epistemic_target(tmp_path: Path):
    """A hand-authored sci:bearsOn pointing at a dataset (operational) is invalid."""
    root = _build_min_project(tmp_path)
    # Inject a structured relation that points bears_on at a dataset.
    (root / "doc" / "datasets").mkdir(parents=True, exist_ok=True)
    (root / "doc" / "datasets" / "d1.md").write_text(
        dedent(
            """
            ---
            id: "dataset:d1"
            kind: "dataset"
            title: "Demo"
            origin: "external"
            access:
              level: "public"
              verified: true
            created: "2026-04-01"
            updated: "2026-04-01"
            ---
            """
        ).lstrip()
    )
    # Relations go in knowledge/sources/{local_profile}/relations.yaml with a
    # top-level "relations:" key. The project uses local: core.
    relations_yaml = root / "knowledge" / "sources" / "core" / "relations.yaml"
    relations_yaml.parent.mkdir(parents=True, exist_ok=True)
    relations_yaml.write_text(
        "relations:\n"
        '  - subject: "task:t1"\n'
        '    predicate: "sci:bearsOn"\n'
        '    object: "dataset:d1"\n'
        '    graph_layer: "graph/knowledge"\n'
    )

    with pytest.raises(ValueError, match="bears_on"):
        materialize_graph(root)


def test_materialize_emits_closure_bears_on_through_observation(tmp_path: Path):
    """Closure end-to-end: workflow-run grounds observation supports proposition addresses hypothesis.

    Note: at materialize time, only the typed-edge bears_on rules fire directly
    (workflow-run grounds observation -> bears_on; observation supports proposition
    -> bears_on). Closure should then emit (workflow-run, bears_on, proposition)
    as a transitive triple.
    """
    root = tmp_path / "demo"
    _write(root / "science.yaml", """
        name: demo
        knowledge_profiles:
          local: core
    """)
    _write(root / "doc" / "propositions" / "p1.md", """
        ---
        id: "proposition:p1"
        kind: "proposition"
        title: "Demo prop"
        created: "2026-04-01"
        updated: "2026-04-01"
        ---
        Body.
    """)
    _write(root / "doc" / "observations" / "o1.md", """
        ---
        id: "observation:o1"
        kind: "observation"
        title: "Demo obs"
        created: "2026-04-01"
        updated: "2026-04-01"
        ---
        Body.
    """)
    # observation supports proposition (cito:supports edge via authored relations)
    _write(root / "knowledge" / "sources" / "core" / "relations.yaml", """
        relations:
          - subject: "observation:o1"
            predicate: "cito:supports"
            object: "proposition:p1"
            graph_layer: "graph/knowledge"
          - subject: "workflow-run:wfr1"
            predicate: "sci:grounds"
            object: "observation:o1"
            graph_layer: "graph/knowledge"
    """)
    _write(root / "doc" / "workflow-runs" / "wfr1.md", """
        ---
        id: "workflow-run:wfr1"
        kind: "workflow-run"
        title: "Demo run"
        status: "complete"
        created: "2026-04-01"
        updated: "2026-04-01"
        ---
        Body.
    """)

    trig = materialize_graph(root)
    ds = _load_dataset(trig)
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])

    pairs = {(str(s), str(o)) for s, _, o in knowledge.triples((None, SCI_NS.bearsOn, None))}
    wfr_uri = str(URIRef(PROJECT_NS["workflow-run/wfr1"]))
    o_uri = str(URIRef(PROJECT_NS["observation/o1"]))
    p_uri = str(URIRef(PROJECT_NS["proposition/p1"]))

    # Direct bears_on edges from typed-edge rules:
    assert (wfr_uri, o_uri) in pairs, "sci:grounds rule should produce bears_on"
    assert (o_uri, p_uri) in pairs, "cito:supports rule should produce bears_on"

    # Transitive closure should emit:
    assert (wfr_uri, p_uri) in pairs, "closure should produce wfr -> proposition"


def test_provenance_plus_closure_end_to_end(tmp_path: Path):
    """A paper cited via source_refs of a hypothesis flows through provenance
    derivation; if a story synthesizes that hypothesis, closure emits
    paper bears_on story as well.

    Chain:
      paper:p1  wasDerivedFrom->  hypothesis:h1   (source_refs / provenance)
      => paper:p1 bears_on hypothesis:h1           (depth 1, provenance rule)
      story:s1  sci:synthesizes -> hypothesis:h1
      => hypothesis:h1 bears_on story:s1           (depth 1, synthesizes inverse)
      closure => paper:p1 bears_on story:s1        (depth 2)

    Note: `paper` is OPERATIONAL (it is a reference artifact, not an epistemic
    claim), so it cannot be a closure *target* — but it can be a closure *source*.
    `story` is EPISTEMIC, so it is a valid closure target.
    """
    root = tmp_path / "demo"
    _write(root / "science.yaml", """
        name: demo
        knowledge_profiles:
          local: core
    """)
    # Paper entity — scanned automatically because markdown adapter covers doc/
    _write(root / "doc" / "papers" / "p1.md", """
        ---
        id: "paper:p1"
        kind: "paper"
        title: "Demo paper"
        created: "2026-03-01"
        updated: "2026-03-01"
        ---
        Body.
    """)
    # Hypothesis cites the paper via source_refs → provenance materialises
    # hypothesis:h1 prov:wasDerivedFrom paper:p1, which the freshness engine
    # converts to paper:p1 bears_on hypothesis:h1 (depth 1).
    _write(root / "specs" / "hypotheses" / "h1.md", """
        ---
        id: "hypothesis:h1"
        kind: "hypothesis"
        title: "Demo hypothesis"
        created: "2026-04-01"
        updated: "2026-04-01"
        source_refs: ["paper:p1"]
        ---
        Body.
    """)
    # Story entity — scanned automatically because markdown adapter covers doc/
    _write(root / "doc" / "stories" / "s1.md", """
        ---
        id: "story:s1"
        kind: "story"
        title: "Demo story"
        created: "2026-04-15"
        updated: "2026-04-15"
        ---
        Body.
    """)
    # sci:synthesizes is an inverse bears_on rule: story synthesizes hypothesis
    # => hypothesis bears_on story.  We author this as a structured relation
    # because the markdown frontmatter for generic ProjectEntity kinds does not
    # have a first-class `synthesizes` field (that field lives on the legacy
    # store API only).
    _write(root / "knowledge" / "sources" / "core" / "relations.yaml", """
        relations:
          - subject: "story:s1"
            predicate: "sci:synthesizes"
            object: "hypothesis:h1"
            graph_layer: "graph/knowledge"
    """)

    trig = materialize_graph(root)
    ds = _load_dataset(trig)
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])

    paper_uri = str(URIRef(PROJECT_NS["paper/p1"]))
    h_uri = str(URIRef(PROJECT_NS["hypothesis/h1"]))
    story_uri = str(URIRef(PROJECT_NS["story/s1"]))

    pairs = {(str(s), str(o)) for s, _, o in knowledge.triples((None, SCI_NS.bearsOn, None))}
    # Direct: paper -> hypothesis (provenance derivation)
    assert (paper_uri, h_uri) in pairs, "provenance rule: paper bears_on hypothesis"
    # Direct: hypothesis -> story (synthesizes inverse rule)
    assert (h_uri, story_uri) in pairs, "synthesizes inverse: hypothesis bears_on story"
    # Closure: paper -> story (transitive, depth 2)
    assert (paper_uri, story_uri) in pairs, "closure: paper bears_on story"


def test_propagate_and_materialize_agree(tmp_path: Path):
    """propagate_freshness_in_memory should produce the same needs-review/stale
    rows as materialize_graph + parse-trig, since they use the same underlying
    pipeline.
    """
    from science_tool.graph.freshness import propagate_freshness_in_memory
    from science_tool.graph.store import canonical_id_from_entity_uri

    root = _build_min_project(tmp_path)

    in_memory_rows = propagate_freshness_in_memory(root)
    in_memory_set = {(r["id"], r["kind"], r["state"]) for r in in_memory_rows}

    trig = materialize_graph(root)
    ds = _load_dataset(trig)
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])
    materialize_set = set()
    for s, _, o in knowledge.triples((None, SCI_NS.freshnessState, None)):
        state = str(o)
        if state == "fresh":
            continue
        cid = canonical_id_from_entity_uri(str(s))
        if cid is None:
            continue
        kind, _, _ = cid.partition(":")
        materialize_set.add((cid, kind, state))

    assert in_memory_set == materialize_set


def test_audit_gate_runs_even_when_freshness_disabled(tmp_path: Path):
    """`freshness.enabled: false` does NOT bypass the audit gate."""
    import pytest as _pytest
    from science_tool.graph.freshness import propagate_freshness_in_memory

    root = tmp_path / "demo"
    _write(root / "science.yaml", """
        name: demo
        knowledge_profiles:
          local: core
        freshness:
          enabled: false
    """)
    _write(root / "specs" / "hypotheses" / "h1.md", """
        ---
        id: "hypothesis:h1"
        kind: "hypothesis"
        title: "Demo"
        created: "2026-04-01"
        updated: "2026-04-01"
        source_refs: ["paper:does-not-exist"]
        ---
        Body.
    """)
    with _pytest.raises(ValueError, match="unresolved references"):
        propagate_freshness_in_memory(root)

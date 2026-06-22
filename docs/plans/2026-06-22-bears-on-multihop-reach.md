# Usage-path `sci:bearsOn` Multi-hop Reach — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop undercounting `reach` by expanding a usage-path proposition to its questions/hypotheses via the materialized transitive `sci:bearsOn` closure, unioned with the two existing direct edges.

**Architecture:** Single additive change to `_qh_for_proposition` in `dataset_prioritize.py`. It already returns Q/H via `cito:discusses` (prop→hypothesis) and `sci:addresses` (question→prop, backward); add a third source — `sci:bearsOn` closure targets typed Question/Hypothesis — and union them. `usage_reach` calls this function and inherits the upgrade with no other change. Validated by a synthetic multi-hop test (no live consumer: PAIS has 0 `dataset_usage` edges, so this lights up end-to-end only on an `mm30`-scale graph).

**Tech Stack:** Python, rdflib, pytest, `uv`. Repo: `~/d/science`, package dir `~/d/science/science`.

## Global Constraints

- Run all Python/test commands from `~/d/science/science` (the editable package dir) with `uv run --frozen`.
- The change must be **purely additive**: it may only *add* Q/H to a proposition's reach, never remove any — so no existing acceptance criterion or test in `tests/test_dataset_prioritize*.py` may regress.
- **Union, not replacement.** `cito:discusses` and `sci:addresses` are NOT `sci:bearsOn` deriver rules (see `graph/freshness.py` `derive_bears_on_from_typed_edges`), so the closure alone would drop those two sources. Keep all three.
- Do NOT touch `reached_proposition_uris` or `leverage_tilt` — that is the deferred candidate-aware-leverage item, explicitly out of scope.
- No "Co-Authored-By" trailer in commits.
- Imports needed (`URIRef`, `RDF`, `CITO_NS`, `SCI_NS`) are already present at the top of `dataset_prioritize.py`; add none.

---

### Task 1: Union the `sci:bearsOn` closure into usage-path Q/H reach

**Files:**
- Modify: `science/src/science_tool/dataset_prioritize.py` — function `_qh_for_proposition` (currently the two-direct-edge walk with a "Scope note (deferred)" docstring).
- Test: `science/tests/test_dataset_prioritize_graph.py` — add one seed helper + one test.

**Interfaces:**
- Consumes: `usage_reach(knowledge, provenance, dataset_ids)` (unchanged signature) which calls `_qh_for_proposition(knowledge, prop_uri)`; the materialized `sci:bearsOn` closure produced by `science graph build` / `materialize_graph` (transitive, via `graph/freshness.py` `close_bears_on`); `materialize_graph`, `_load_dataset`, `_graph_uri`, `_write` (already imported/defined in the test module).
- Produces: `_qh_for_proposition` now returns the **union** of direct-discusses hypotheses, backward-addresses questions, and `bearsOn`-closure Q/H targets — same return type (`set[URIRef]`). `usage_reach` returns canonical ids (e.g. `"hypothesis:h2"`).

- [ ] **Step 1: Write the failing test**

Append to `science/tests/test_dataset_prioritize_graph.py` (the `_write` helper, `Path`, `materialize_graph`, `_load_dataset`, `_graph_uri`, and `usage_reach` are already imported/defined at the top of this file):

```python
def _seed_multihop_project(root: Path) -> None:
    # dataset:d --usage--> evidence-line:e --supports--> proposition:p
    # p --cito:supports--> p2 --cito:supports--> hypothesis:h2
    # => h2 is reachable from p ONLY via the transitive bearsOn closure at
    #    depth 2. p does NOT `cito:discusses` h2, and no question `sci:addresses`
    #    p, so the pre-upgrade direct-edge walk returns an empty set here.
    (root / "science.yaml").write_text('slug: "tp"\n', encoding="utf-8")
    _write(root / "entities/datasets/d.md",
           '---\nid: "dataset:d"\ntype: "dataset"\ntitle: "D"\norigin: "external"\n'
           'access: {level: "public", verified: true}\n---\n')
    _write(root / "entities/hypotheses/h2.md",
           '---\nid: "hypothesis:h2"\ntype: "hypothesis"\ntitle: "H2"\n---\n')
    _write(root / "entities/propositions/p.md",
           '---\nid: "proposition:p"\ntype: "proposition"\ntitle: "P"\n'
           'relations:\n  - predicate: "cito:supports"\n    target: "proposition:p2"\n---\n')
    _write(root / "entities/propositions/p2.md",
           '---\nid: "proposition:p2"\ntype: "proposition"\ntitle: "P2"\n'
           'relations:\n  - predicate: "cito:supports"\n    target: "hypothesis:h2"\n---\n')
    _write(root / "entities/evidence-lines/e.md",
           '---\nid: "evidence-line:e"\ntype: "evidence-line"\ntitle: "E"\n'
           'stance: "supports"\ntarget: "proposition:p"\nevidence_type: "empirical_data_evidence"\n'
           'dataset_usage:\n  - ref: "dataset:d"\n    role: "analyzed"\n    overlap: "full"\n---\n')


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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_dataset_prioritize_graph.py::test_usage_reach_follows_multihop_bearson_closure -v`
Expected: FAIL — `assert set() == {'hypothesis:h2'}` (the direct-edge-only walk does not follow the bearsOn closure). The materialized graph genuinely contains `proposition:p sci:bearsOn hypothesis:h2` at depth 2; the assertion fails only because `_qh_for_proposition` does not yet read it.

- [ ] **Step 3: Implement the union upgrade**

In `science/src/science_tool/dataset_prioritize.py`, replace the entire `_qh_for_proposition` function (docstring + body) with:

```python
def _qh_for_proposition(knowledge, prop_uri: URIRef) -> set[URIRef]:
    """Questions/hypotheses a proposition reaches, as the UNION of three sources:

    1. direct ``prop cito:discusses hypothesis``,
    2. direct ``question sci:addresses prop`` (traversed backward),
    3. the materialized transitive ``sci:bearsOn`` closure targets typed
       Question/Hypothesis (graph/freshness.py ``close_bears_on``) — catches a
       Q/H reachable only via a multi-hop chain, e.g. ``P cito:supports P2
       cito:supports H`` yields ``P bearsOn H`` at depth 2.

    Union, NOT replacement: ``cito:discusses``/``sci:addresses`` are not bearsOn
    deriver rules, so the closure alone would drop sources 1-2. Purely additive —
    can only add Q/H, never remove.
    """
    out: set[URIRef] = set()
    for _, _, hyp in knowledge.triples((prop_uri, CITO_NS.discusses, None)):
        if isinstance(hyp, URIRef) and (hyp, RDF.type, SCI_NS.Hypothesis) in knowledge:
            out.add(hyp)
    for q in knowledge.subjects(SCI_NS.addresses, prop_uri):
        if isinstance(q, URIRef) and (q, RDF.type, SCI_NS.Question) in knowledge:
            out.add(q)
    for tgt in knowledge.objects(prop_uri, SCI_NS.bearsOn):
        if not isinstance(tgt, URIRef):
            continue
        if (tgt, RDF.type, SCI_NS.Hypothesis) in knowledge or (tgt, RDF.type, SCI_NS.Question) in knowledge:
            out.add(tgt)
    return out
```

- [ ] **Step 4: Run the new test to verify it passes**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_dataset_prioritize_graph.py::test_usage_reach_follows_multihop_bearson_closure -v`
Expected: PASS.

- [ ] **Step 5: Run the full prioritize suite for regressions**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_dataset_prioritize_graph.py tests/test_dataset_prioritize_cli.py -v`
Expected: all PASS, including the pre-existing `test_merged_reach_unions_both_paths_and_dedups`, `test_prioritize_mixed_graph_frontmatter_dataset_not_no_edge`, and the leverage tests — the change is additive, so none regress. (If a `tests/test_dataset_prioritize.py` also exists, include it in the path list.)

- [ ] **Step 6: Lint the changed file**

Run: `cd ~/d/science/science && uv run --frozen ruff check src/science_tool/dataset_prioritize.py tests/test_dataset_prioritize_graph.py`
Expected: `All checks passed!`

- [ ] **Step 7: Commit**

```bash
cd ~/d/science
git add science/src/science_tool/dataset_prioritize.py science/tests/test_dataset_prioritize_graph.py
git commit -m "feat(dataset): union sci:bearsOn closure into usage-path Q/H reach

_qh_for_proposition now expands a proposition to its questions/hypotheses
via the materialized transitive sci:bearsOn closure, unioned with the two
existing direct edges (cito:discusses, sci:addresses). Fixes the multi-hop
reach undercount flagged in the catalog-datasets design Open Questions.
Purely additive; usage_reach inherits the upgrade. Validated synthetically
(no live dataset_usage consumer yet)."
```

---

## Out of scope (deferred — do NOT implement)

- **Candidate-aware leverage** (borrowing claim-signals from a candidate's target-question bearsOn neighborhood). Deferred with an explicit un-defer trigger; see `docs/plans/2026-06-21-catalog-datasets-design.md` Open Questions. The required signal is unpopulated on the only current consumer.
- Any change to `reached_proposition_uris`, `leverage_tilt`, frontmatter reach, readiness weighting, or the CLI surface.

## Post-implementation (controller, outside the science git repo)

- Update the project memory `science-datasets-cli-direction.md`: note item 1 (bearsOn multi-hop) implemented on `~/d/science` (commit ref), item 2 still deferred with trigger.

## Self-Review

- **Spec coverage:** The design's resolution note (`2026-06-21-catalog-datasets-design.md` Open Questions, "Multi-hop usage reach … SCOPED FOR IMPLEMENTATION") maps to Task 1: union the closure into `_qh_for_proposition`, additive, `usage_reach` inherits it, synthetic multi-hop test. Candidate-aware leverage is explicitly out of scope. Covered.
- **Placeholder scan:** No TBD/TODO/"handle edge cases"; full code and exact commands given in every code step.
- **Type consistency:** `_qh_for_proposition(knowledge, prop_uri) -> set[URIRef]` unchanged; new loop uses `knowledge.objects(prop_uri, SCI_NS.bearsOn)` and the same `(node, RDF.type, SCI_NS.Hypothesis|Question) in knowledge` typing guard as the existing two loops; `usage_reach` already maps URIs → canonical ids, so the test asserts `"hypothesis:h2"`. Consistent.

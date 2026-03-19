# Phase 4b Gaps Fix — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Close the gaps identified in the Phase 4b review: edge-level provenance comments in exports, revision hash in headers, TODO sections for latent variables, inquiry type in list/show, `.get()` safety fix, and the three missing causal validation checks.

**Architecture:** Extend `_get_causal_edges_for_inquiry()` to collect claims and observability metadata alongside edges. Both export functions use this enriched data to emit provenance comments, revision hashes, and TODO sections. Validation checks for identifiability/adjustment_sets require pgmpy at runtime — they gracefully skip when pgmpy is not installed. `confounders_declared` is pure graph analysis (no external deps).

**Tech Stack:** Python 3.13, rdflib, click, pytest

**CLI prefix:** All commands use `uv run --frozen science-tool ...` from `science-tool/` directory.

**Test runner:** `cd science-tool && uv run --frozen pytest tests/<file>::<test> -v`

---

### Task 1: Enrich `_get_causal_edges_for_inquiry()` with provenance metadata

**Files:**
- Modify: `science-tool/src/science_tool/causal/export_pgmpy.py:40-82`
- Test: `science-tool/tests/test_causal.py`

This is the foundation for Tasks 2-3. We enrich the edge data returned by `_get_causal_edges_for_inquiry()` to include claims and variable observability.

**Data model context:** Claims and edges are separate entities. Claims are `sci:Claim` in `graph/knowledge` with `schema:text` content and `sci:confidence` + `prov:wasDerivedFrom` in `graph/provenance`. There is no direct edge→claim link. We use best-effort matching: for each causal edge (A→B), find claims whose `schema:text` mentions both variable names (case-insensitive substring match).

**Step 1: Write the failing tests**

Add to `test_causal.py` a new test class after `TestExportChirho`:

```python
class TestEdgeProvenance:
    """Tests for enriched edge metadata in causal exports."""

    def _build_dag_with_claims(self, graph_path: Path) -> str:
        """Build a DAG with claims supporting the causal edges."""
        add_concept(graph_path, "Drug", concept_type="sci:Variable", ontology_id=None,
                    properties=[("sci:observability", "observed")])
        add_concept(graph_path, "Recovery", concept_type="sci:Variable", ontology_id=None,
                    properties=[("sci:observability", "observed")])
        add_concept(graph_path, "Severity", concept_type="sci:Variable", ontology_id=None,
                    properties=[("sci:observability", "latent")])
        add_hypothesis(graph_path, "h1", "Test hypothesis", source="paper:doi_test")
        add_inquiry(graph_path, "prov-dag", "Provenance DAG", "hypothesis:h1", inquiry_type="causal")
        set_boundary_role(graph_path, "prov-dag", "concept/drug", "BoundaryIn")
        set_boundary_role(graph_path, "prov-dag", "concept/recovery", "BoundaryOut")
        set_boundary_role(graph_path, "prov-dag", "concept/severity", "BoundaryIn")
        set_treatment_outcome(graph_path, "prov-dag", treatment="concept/drug", outcome="concept/recovery")
        add_edge(graph_path, "concept/drug", "scic:causes", "concept/recovery", graph_layer="graph/causal")
        add_edge(graph_path, "concept/severity", "scic:causes", "concept/recovery", graph_layer="graph/causal")
        add_edge(graph_path, "concept/severity", "scic:causes", "concept/drug", graph_layer="graph/causal")
        # Add claims that mention both endpoints
        from science_tool.graph.store import add_claim
        add_claim(graph_path, "Drug treatment improves recovery time",
                  source="paper:doi_10.1234/drug_recovery", confidence=0.85)
        add_claim(graph_path, "Disease severity affects recovery outcomes",
                  source="paper:doi_10.5678/severity", confidence=0.90)
        return "prov-dag"

    def test_enriched_edges_contain_claims(self, graph_path: Path) -> None:
        """Edges returned by _get_causal_edges_for_inquiry include matched claims."""
        from science_tool.causal.export_pgmpy import _get_causal_edges_for_inquiry
        slug = self._build_dag_with_claims(graph_path)
        edges = _get_causal_edges_for_inquiry(graph_path, slug)
        # Find the drug->recovery edge
        drug_recovery = [e for e in edges if "drug" in e["subject"] and "recovery" in e["object"]]
        assert len(drug_recovery) == 1
        edge = drug_recovery[0]
        assert "claims" in edge
        assert len(edge["claims"]) >= 1
        claim = edge["claims"][0]
        assert "text" in claim
        assert "confidence" in claim
        assert "source" in claim

    def test_enriched_edges_contain_observability(self, graph_path: Path) -> None:
        """Edges include observability metadata for both endpoints."""
        from science_tool.causal.export_pgmpy import _get_causal_edges_for_inquiry
        slug = self._build_dag_with_claims(graph_path)
        edges = _get_causal_edges_for_inquiry(graph_path, slug)
        # Check that variable_meta is populated
        drug_recovery = [e for e in edges if "drug" in e["subject"] and "recovery" in e["object"]]
        edge = drug_recovery[0]
        assert "subject_observability" in edge
        assert "object_observability" in edge

    def test_edges_without_claims_have_empty_list(self, graph_path: Path) -> None:
        """Edges with no matching claims still have a 'claims' key with empty list."""
        from science_tool.causal.export_pgmpy import _get_causal_edges_for_inquiry
        # Build DAG without claims
        add_concept(graph_path, "A", concept_type="sci:Variable", ontology_id=None)
        add_concept(graph_path, "B", concept_type="sci:Variable", ontology_id=None)
        add_hypothesis(graph_path, "h1", "Test hypothesis", source="paper:doi_test")
        add_inquiry(graph_path, "no-claims", "No Claims", "hypothesis:h1", inquiry_type="causal")
        set_boundary_role(graph_path, "no-claims", "concept/a", "BoundaryIn")
        set_boundary_role(graph_path, "no-claims", "concept/b", "BoundaryOut")
        set_treatment_outcome(graph_path, "no-claims", treatment="concept/a", outcome="concept/b")
        add_edge(graph_path, "concept/a", "scic:causes", "concept/b", graph_layer="graph/causal")
        edges = _get_causal_edges_for_inquiry(graph_path, "no-claims")
        assert len(edges) == 1
        assert edges[0]["claims"] == []
```

Note: You'll also need to add `add_claim` to the imports at the top of `test_causal.py`.

**Step 2: Run tests to verify they fail**

Run: `cd science-tool && uv run --frozen pytest tests/test_causal.py::TestEdgeProvenance -v`
Expected: FAIL — `claims` key missing from edge dict, `subject_observability` missing.

**Step 3: Implement the enrichment in `_get_causal_edges_for_inquiry()`**

In `science-tool/src/science_tool/causal/export_pgmpy.py`, modify `_get_causal_edges_for_inquiry()`:

1. Add imports at the top of the file:
```python
from rdflib import Literal
from rdflib.namespace import PROV, RDF, XSD

from science_tool.graph.store import (
    SCIC_NS,
    SCI_NS,
    SCHEMA_NS,
    _graph_uri,
    _load_dataset,
    _slug,
    get_inquiry,
    shorten_uri,
)
```
(Add `SCHEMA_NS`, `Literal`, `PROV`, `RDF` to existing imports.)

2. Replace the function body to:
   - After collecting `members`, also collect observability for each member variable from `graph/knowledge`
   - After collecting edges, query all claims from `graph/knowledge` (type `sci:Claim`) and their provenance from `graph/provenance`
   - For each edge, match claims whose `schema:text` contains both endpoint variable names (case-insensitive)
   - Add `claims`, `subject_observability`, `object_observability` keys to each edge dict

```python
def _get_causal_edges_for_inquiry(graph_path: Path, slug: str) -> list[dict]:
    """Collect causal edges (scic:causes, scic:confounds) filtered to inquiry members.

    Returns a list of dicts with keys: subject, predicate, object, pred_type,
    claims (list of {text, confidence, source}), subject_observability, object_observability.
    """
    safe_slug = _slug(slug)
    inquiry_uri = URIRef(f"http://example.org/project/inquiry/{safe_slug}")

    dataset = _load_dataset(graph_path)
    inquiry_graph = dataset.graph(inquiry_uri)

    # Collect boundary nodes
    members: set[URIRef] = set()
    for s, _p, o in inquiry_graph.triples((None, SCI_NS.boundaryRole, None)):
        members.add(s)  # type: ignore[arg-type]

    # Collect flow nodes
    flow_predicates = {SCI_NS.feedsInto, SCI_NS.produces, SCIC_NS.causes}
    for s, p, o in inquiry_graph:
        if p in flow_predicates:
            members.add(s)  # type: ignore[arg-type]
            members.add(o)  # type: ignore[arg-type]

    # Collect observability metadata from knowledge graph
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))
    observability: dict[str, str] = {}
    for member_uri in members:
        obs_val = next(knowledge.objects(member_uri, SCI_NS.observability), None)
        if obs_val is not None:
            observability[str(member_uri)] = str(obs_val)

    # Collect all claims and their provenance
    provenance_graph = dataset.graph(_graph_uri("graph/provenance"))
    claims_data: list[dict[str, str]] = []
    for claim_uri in knowledge.subjects(RDF.type, SCI_NS.Claim):
        text = str(next(knowledge.objects(claim_uri, SCHEMA_NS.text), ""))
        confidence_val = next(provenance_graph.objects(claim_uri, SCI_NS.confidence), None)
        confidence = str(confidence_val) if confidence_val is not None else ""
        sources = [shorten_uri(str(src)) for src in provenance_graph.objects(claim_uri, PROV.wasDerivedFrom)]
        source = ", ".join(sources) if sources else ""
        claims_data.append({"text": text, "confidence": confidence, "source": source})

    causal_graph = dataset.graph(_graph_uri("graph/causal"))

    edges: list[dict] = []
    causal_predicates = {
        SCIC_NS.causes: "causes",
        SCIC_NS.confounds: "confounds",
    }
    for pred_uri, pred_type in causal_predicates.items():
        for s, _p, o in causal_graph.triples((None, pred_uri, None)):
            if s in members and o in members:
                s_name = _variable_name(str(s)).lower()
                o_name = _variable_name(str(o)).lower()
                # Best-effort claim matching: find claims mentioning both endpoints
                matched_claims = [
                    c for c in claims_data
                    if s_name in c["text"].lower() and o_name in c["text"].lower()
                ]
                edges.append(
                    {
                        "subject": str(s),
                        "predicate": str(pred_uri),
                        "object": str(o),
                        "pred_type": pred_type,
                        "claims": matched_claims,
                        "subject_observability": observability.get(str(s), ""),
                        "object_observability": observability.get(str(o), ""),
                    }
                )

    return edges
```

**Step 4: Run tests to verify they pass**

Run: `cd science-tool && uv run --frozen pytest tests/test_causal.py::TestEdgeProvenance -v`
Expected: PASS (3 tests)

Also run full causal test suite to check nothing broke:
Run: `cd science-tool && uv run --frozen pytest tests/test_causal.py tests/test_causal_cli.py -v`
Expected: All existing tests still pass.

**Step 5: Commit**

```bash
git add -f science-tool/src/science_tool/causal/export_pgmpy.py science-tool/tests/test_causal.py
git commit -m "feat: enrich causal edge data with claims and observability metadata"
```

---

### Task 2: Add provenance comments and revision hash to pgmpy export

**Files:**
- Modify: `science-tool/src/science_tool/causal/export_pgmpy.py:85-153`
- Test: `science-tool/tests/test_causal.py`

**Step 1: Write the failing tests**

Add tests to `TestExportPgmpy` class:

```python
    def test_export_pgmpy_edge_level_provenance(self, graph_path: Path) -> None:
        """Export includes claim text, confidence, and source as comments on edges."""
        # Build DAG with claims
        add_concept(graph_path, "Drug", concept_type="sci:Variable", ontology_id=None)
        add_concept(graph_path, "Recovery", concept_type="sci:Variable", ontology_id=None)
        add_hypothesis(graph_path, "h1", "Test", source="paper:doi_test")
        add_inquiry(graph_path, "prov-pgmpy", "Prov pgmpy", "hypothesis:h1", inquiry_type="causal")
        set_boundary_role(graph_path, "prov-pgmpy", "concept/drug", "BoundaryIn")
        set_boundary_role(graph_path, "prov-pgmpy", "concept/recovery", "BoundaryOut")
        set_treatment_outcome(graph_path, "prov-pgmpy", treatment="concept/drug", outcome="concept/recovery")
        add_edge(graph_path, "concept/drug", "scic:causes", "concept/recovery", graph_layer="graph/causal")
        from science_tool.graph.store import add_claim
        add_claim(graph_path, "Drug treatment improves recovery time",
                  source="paper:doi_10.1234/study", confidence=0.85)
        script = export_pgmpy_script(graph_path, "prov-pgmpy")
        # Edge line should have provenance comment
        assert "confidence: 0.85" in script
        assert "doi_10.1234/study" in script

    def test_export_pgmpy_revision_hash(self, graph_path: Path) -> None:
        """Export header includes graph revision hash when available."""
        slug = self._build_simple_dag(graph_path)
        script = export_pgmpy_script(graph_path, slug)
        # Should have a revision line (even if hash is empty/unavailable)
        assert "# Revision:" in script

    def test_export_pgmpy_todo_section(self, graph_path: Path) -> None:
        """Export includes TODO section noting latent variables."""
        add_concept(graph_path, "Hidden", concept_type="sci:Variable", ontology_id=None,
                    properties=[("sci:observability", "latent")])
        add_concept(graph_path, "Outcome", concept_type="sci:Variable", ontology_id=None,
                    properties=[("sci:observability", "observed")])
        add_hypothesis(graph_path, "h1", "Test", source="paper:doi_test")
        add_inquiry(graph_path, "latent-dag", "Latent DAG", "hypothesis:h1", inquiry_type="causal")
        set_boundary_role(graph_path, "latent-dag", "concept/hidden", "BoundaryIn")
        set_boundary_role(graph_path, "latent-dag", "concept/outcome", "BoundaryOut")
        set_treatment_outcome(graph_path, "latent-dag", treatment="concept/hidden", outcome="concept/outcome")
        add_edge(graph_path, "concept/hidden", "scic:causes", "concept/outcome", graph_layer="graph/causal")
        script = export_pgmpy_script(graph_path, "latent-dag")
        assert "TODO" in script
        assert "latent" in script.lower()
        assert "hidden" in script.lower()
```

**Step 2: Run tests to verify they fail**

Run: `cd science-tool && uv run --frozen pytest tests/test_causal.py::TestExportPgmpy::test_export_pgmpy_edge_level_provenance tests/test_causal.py::TestExportPgmpy::test_export_pgmpy_revision_hash tests/test_causal.py::TestExportPgmpy::test_export_pgmpy_todo_section -v`
Expected: FAIL

**Step 3: Implement the changes in `export_pgmpy_script()`**

Modify `export_pgmpy_script()` in `export_pgmpy.py`:

1. **Add revision hash query** — after getting `info`, query the provenance graph for `REVISION_URI`'s `schema:sha256`:
```python
    # Get revision hash
    dataset = _load_dataset(graph_path)
    provenance_graph = dataset.graph(_graph_uri("graph/provenance"))
    revision_uri = URIRef("http://example.org/project/graph_revision")
    revision_hash = str(next(provenance_graph.objects(revision_uri, SCHEMA_NS.sha256), "unknown"))
```

2. **Add revision line to header** — after the existing header lines:
```python
    lines.append(f"# Revision: {revision_hash}")
```

3. **Modify edge tuple generation** — for each cause edge, append provenance comment:
```python
    for e in cause_edges:
        s_name = _variable_name(e["subject"])
        o_name = _variable_name(e["object"])
        comment_parts: list[str] = []
        if e.get("claims"):
            claim = e["claims"][0]  # Use first matching claim
            comment_parts.append(f'claim: "{claim["text"]}"')
            if claim["confidence"]:
                comment_parts.append(f'confidence: {claim["confidence"]}')
            if claim["source"]:
                comment_parts.append(f'source: {claim["source"]}')
        comment = f"  # {', '.join(comment_parts)}" if comment_parts else ""
        edge_tuples.append(f'("{s_name}", "{o_name}"),{comment}')
```

4. **Add TODO section** — after the inference section, collect latent variables and unresolved assumptions:
```python
    # Collect latent variables and generate TODO section
    all_vars = {_variable_name(e["subject"]) for e in edges} | {_variable_name(e["object"]) for e in edges}
    latent_vars: list[str] = []
    for e in edges:
        if e.get("subject_observability") == "latent":
            latent_vars.append(_variable_name(e["subject"]))
        if e.get("object_observability") == "latent":
            latent_vars.append(_variable_name(e["object"]))
    latent_vars = sorted(set(latent_vars))

    edges_without_claims = [
        f'{_variable_name(e["subject"])} -> {_variable_name(e["object"])}'
        for e in cause_edges if not e.get("claims")
    ]

    if latent_vars or edges_without_claims:
        lines.append("# TODO:")
        for lv in latent_vars:
            lines.append(f"#   - Variable '{lv}' is latent (unobserved) — cannot be directly measured")
        for ec in edges_without_claims:
            lines.append(f"#   - Edge {ec} has no supporting claim — add provenance")
        lines.append("")
```

**Step 4: Run tests to verify they pass**

Run: `cd science-tool && uv run --frozen pytest tests/test_causal.py::TestExportPgmpy -v`
Expected: All tests PASS (including 4 existing + 3 new = 7 tests)

**Step 5: Commit**

```bash
git add -f science-tool/src/science_tool/causal/export_pgmpy.py science-tool/tests/test_causal.py
git commit -m "feat: add edge-level provenance, revision hash, and TODO section to pgmpy export"
```

---

### Task 3: Add provenance comments, revision hash, and TODO section to ChiRho export

**Files:**
- Modify: `science-tool/src/science_tool/causal/export_chirho.py:50-114`
- Test: `science-tool/tests/test_causal.py`

**Step 1: Write the failing tests**

Add tests to `TestExportChirho` class:

```python
    def test_export_chirho_edge_level_provenance(self, graph_path: Path) -> None:
        """Export includes claim provenance as comments on pyro.sample lines."""
        add_concept(graph_path, "Drug", concept_type="sci:Variable", ontology_id=None)
        add_concept(graph_path, "Recovery", concept_type="sci:Variable", ontology_id=None)
        add_hypothesis(graph_path, "h1", "Test", source="paper:doi_test")
        add_inquiry(graph_path, "prov-chirho", "Prov chirho", "hypothesis:h1", inquiry_type="causal")
        set_boundary_role(graph_path, "prov-chirho", "concept/drug", "BoundaryIn")
        set_boundary_role(graph_path, "prov-chirho", "concept/recovery", "BoundaryOut")
        set_treatment_outcome(graph_path, "prov-chirho", treatment="concept/drug", outcome="concept/recovery")
        add_edge(graph_path, "concept/drug", "scic:causes", "concept/recovery", graph_layer="graph/causal")
        from science_tool.graph.store import add_claim
        add_claim(graph_path, "Drug treatment improves recovery time",
                  source="paper:doi_10.1234/study", confidence=0.85)
        script = export_chirho_script(graph_path, "prov-chirho")
        assert "confidence: 0.85" in script
        assert "doi_10.1234/study" in script

    def test_export_chirho_revision_hash(self, graph_path: Path) -> None:
        """Export header includes graph revision hash."""
        slug = self._build_simple_dag(graph_path)
        script = export_chirho_script(graph_path, slug)
        assert "# Revision:" in script

    def test_export_chirho_todo_latent_variables(self, graph_path: Path) -> None:
        """Export TODO section flags latent variables."""
        add_concept(graph_path, "Hidden", concept_type="sci:Variable", ontology_id=None,
                    properties=[("sci:observability", "latent")])
        add_concept(graph_path, "Visible", concept_type="sci:Variable", ontology_id=None,
                    properties=[("sci:observability", "observed")])
        add_hypothesis(graph_path, "h1", "Test", source="paper:doi_test")
        add_inquiry(graph_path, "latent-chirho", "Latent ChiRho", "hypothesis:h1", inquiry_type="causal")
        set_boundary_role(graph_path, "latent-chirho", "concept/hidden", "BoundaryIn")
        set_boundary_role(graph_path, "latent-chirho", "concept/visible", "BoundaryOut")
        set_treatment_outcome(graph_path, "latent-chirho", treatment="concept/hidden", outcome="concept/visible")
        add_edge(graph_path, "concept/hidden", "scic:causes", "concept/visible", graph_layer="graph/causal")
        script = export_chirho_script(graph_path, "latent-chirho")
        assert "TODO" in script
        assert "latent" in script.lower()
        assert "hidden" in script.lower()
```

**Step 2: Run tests to verify they fail**

Run: `cd science-tool && uv run --frozen pytest tests/test_causal.py::TestExportChirho::test_export_chirho_edge_level_provenance tests/test_causal.py::TestExportChirho::test_export_chirho_revision_hash tests/test_causal.py::TestExportChirho::test_export_chirho_todo_latent_variables -v`
Expected: FAIL

**Step 3: Implement the changes in `export_chirho_script()`**

Modify `export_chirho_script()` in `export_chirho.py`:

1. **Add imports:**
```python
from rdflib import URIRef
from rdflib.namespace import PROV

from science_tool.graph.store import (
    SCHEMA_NS,
    _graph_uri,
    _load_dataset,
    get_inquiry,
)
```
(Merge with existing imports — `get_inquiry` is already imported.)

2. **Add revision hash query** — after getting `info`:
```python
    dataset = _load_dataset(graph_path)
    provenance_graph = dataset.graph(_graph_uri("graph/provenance"))
    revision_uri = URIRef("http://example.org/project/graph_revision")
    revision_hash = str(next(provenance_graph.objects(revision_uri, SCHEMA_NS.sha256), "unknown"))
```

3. **Add revision line to header** — after existing header lines:
```python
    lines.append(f"# Revision: {revision_hash}")
```

4. **Add provenance comments to pyro.sample lines** — build a lookup of claims per variable, then modify the sample line generation:
```python
    # Build per-variable claim lookup from edges
    var_claims: dict[str, list[dict[str, str]]] = {}
    for e in edges:
        if e["pred_type"] == "causes":
            o_name = _variable_name(e["object"])
            if e.get("claims"):
                var_claims.setdefault(o_name, []).extend(e["claims"])

    for var in sorted_vars:
        parents = _get_parents(var, edges)
        # Build provenance comment
        claims = var_claims.get(var, [])
        if claims:
            c = claims[0]
            prov_comment = f"  # confidence: {c['confidence']}, source: {c['source']}" if c.get("confidence") else ""
        else:
            prov_comment = ""
        # ... existing sample line logic, append prov_comment ...
```

For root variables, keep the existing `# root` comment. For caused variables, append the provenance comment after the existing `# caused by ...` comment.

5. **Add TODO section** — collect latent variables from edges and append after the existing TODO lines:
```python
    # Collect latent variables
    latent_vars: list[str] = set()
    for e in edges:
        if e.get("subject_observability") == "latent":
            latent_vars.add(_variable_name(e["subject"]))
        if e.get("object_observability") == "latent":
            latent_vars.add(_variable_name(e["object"]))
    latent_vars = sorted(latent_vars)

    if latent_vars:
        lines.append("# TODO: Latent (unobserved) variables — cannot condition on data directly:")
        for lv in latent_vars:
            lines.append(f"#   - {lv}")
```

Insert this after the existing TODO lines (lines 80-81) and before the imports section.

**Step 4: Run tests to verify they pass**

Run: `cd science-tool && uv run --frozen pytest tests/test_causal.py::TestExportChirho -v`
Expected: All tests PASS (5 existing + 3 new = 8 tests)

**Step 5: Run full test suite**

Run: `cd science-tool && uv run --frozen pytest tests/test_causal.py tests/test_causal_cli.py -v`
Expected: All tests pass.

**Step 6: Commit**

```bash
git add -f science-tool/src/science_tool/causal/export_chirho.py science-tool/tests/test_causal.py
git commit -m "feat: add edge-level provenance, revision hash, and TODO section to ChiRho export"
```

---

### Task 4: Add inquiry type to `list_inquiries()` and `inquiry show` text output

**Files:**
- Modify: `science-tool/src/science_tool/graph/store.py:472-514` (list_inquiries)
- Modify: `science-tool/src/science_tool/cli.py:645-701` (inquiry_list and inquiry_show commands)
- Test: `science-tool/tests/test_causal.py`
- Test: `science-tool/tests/test_causal_cli.py`

**Step 1: Write the failing tests**

Add a new test class to `test_causal.py`:

```python
class TestInquiryTypeDisplay:
    def test_list_inquiries_includes_type(self, graph_path: Path) -> None:
        """list_inquiries() returns inquiry_type in each dict."""
        from science_tool.graph.store import list_inquiries
        add_hypothesis(graph_path, "h1", "Test", source="paper:doi_test")
        add_inquiry(graph_path, "causal-1", "Causal", "hypothesis:h1", inquiry_type="causal")
        add_inquiry(graph_path, "general-1", "General", "hypothesis:h1")
        rows = list_inquiries(graph_path)
        causal_row = next(r for r in rows if r["slug"] == "causal-1")
        general_row = next(r for r in rows if r["slug"] == "general-1")
        assert causal_row["inquiry_type"] == "causal"
        assert general_row["inquiry_type"] == "general"
```

Add to `test_causal_cli.py`, a new class:

```python
class TestInquiryTypeInOutput:
    def test_show_displays_type(self, runner: CliRunner, graph_path: Path) -> None:
        """inquiry show text output includes the inquiry type."""
        p = str(graph_path)
        runner.invoke(main, ["graph", "add", "hypothesis", "h1", "--source", "paper:doi_test", "--path", p])
        runner.invoke(main, ["inquiry", "init", "dag1", "--label", "DAG",
                             "--target", "hypothesis:h1", "--type", "causal", "--path", p])
        result = runner.invoke(main, ["inquiry", "show", "dag1", "--path", p])
        assert result.exit_code == 0
        assert "Type: causal" in result.output

    def test_list_displays_type_column(self, runner: CliRunner, graph_path: Path) -> None:
        """inquiry list includes a Type column."""
        p = str(graph_path)
        runner.invoke(main, ["graph", "add", "hypothesis", "h1", "--source", "paper:doi_test", "--path", p])
        runner.invoke(main, ["inquiry", "init", "dag1", "--label", "DAG",
                             "--target", "hypothesis:h1", "--type", "causal", "--path", p])
        result = runner.invoke(main, ["inquiry", "list", "--path", p])
        assert result.exit_code == 0
        assert "causal" in result.output
```

**Step 2: Run tests to verify they fail**

Run: `cd science-tool && uv run --frozen pytest tests/test_causal.py::TestInquiryTypeDisplay tests/test_causal_cli.py::TestInquiryTypeInOutput -v`
Expected: FAIL

**Step 3: Implement the changes**

**In `store.py` `list_inquiries()`** (around line 490-511):

Add after the `created` variable extraction (around line 502):
```python
        inquiry_type = ""
        for obj in ctx.objects(inquiry_uri, SCI_NS.inquiryType):
            inquiry_type = str(obj)
        if not inquiry_type:
            inquiry_type = "general"
```

Add `"inquiry_type": inquiry_type` to the results dict (around line 510).

**In `cli.py` `inquiry_list()`** (around line 653-664):

Add the type column to the `columns` list:
```python
    columns=[
        ("slug", "Slug"),
        ("label", "Label"),
        ("inquiry_type", "Type"),
        ("status", "Status"),
        ("target", "Target"),
        ("created", "Created"),
    ],
```

**In `cli.py` `inquiry_show()`** (around line 686-688):

Add after `click.echo(f"  Slug: {info['slug']}")`:
```python
        click.echo(f"  Type: {info['inquiry_type']}")
```

**Step 4: Run tests to verify they pass**

Run: `cd science-tool && uv run --frozen pytest tests/test_causal.py::TestInquiryTypeDisplay tests/test_causal_cli.py::TestInquiryTypeInOutput -v`
Expected: PASS

Run: `cd science-tool && uv run --frozen pytest tests/test_causal.py tests/test_causal_cli.py -v`
Expected: All tests pass.

**Step 5: Commit**

```bash
git add -f science-tool/src/science_tool/graph/store.py science-tool/src/science_tool/cli.py science-tool/tests/test_causal.py science-tool/tests/test_causal_cli.py
git commit -m "feat: show inquiry type in list and show commands"
```

---

### Task 5: Fix `.get()` safety in pgmpy export type check

**Files:**
- Modify: `science-tool/src/science_tool/causal/export_pgmpy.py:96`

**Step 1: Write the failing test**

Add to `TestExportPgmpy`:

```python
    def test_export_pgmpy_safe_type_check(self, graph_path: Path) -> None:
        """Export handles missing inquiry_type gracefully (no KeyError)."""
        # This is a safety test — get_inquiry always returns inquiry_type,
        # but we verify the export code uses safe access.
        slug = self._build_simple_dag(graph_path)
        # Normal path should work fine
        script = export_pgmpy_script(graph_path, slug)
        assert "BayesianNetwork" in script
```

Actually, this is already covered by existing tests. The fix is a one-liner with no new test needed.

**Step 1: Make the fix**

Change line 96 in `export_pgmpy.py` from:
```python
    if info["inquiry_type"] != "causal":
```
to:
```python
    if info.get("inquiry_type", "general") != "causal":
```

**Step 2: Run tests to verify nothing broke**

Run: `cd science-tool && uv run --frozen pytest tests/test_causal.py tests/test_causal_cli.py -v`
Expected: All pass.

**Step 3: Commit**

```bash
git add -f science-tool/src/science_tool/causal/export_pgmpy.py
git commit -m "fix: use safe .get() for inquiry_type in pgmpy export"
```

---

### Task 6: Add `confounders_declared` validation check

**Files:**
- Modify: `science-tool/src/science_tool/graph/store.py:1043-1074` (validate_inquiry, causal section)
- Test: `science-tool/tests/test_causal.py`

This check has no external dependencies. For each pair of inquiry variables connected by `scic:causes`, check whether any variable has a path to both endpoints (common ancestor pattern). If so, warn unless there's an explicit `scic:confounds` edge declaring the confounder relationship.

**Step 1: Write the failing tests**

Add a new test class to `test_causal.py`:

```python
class TestConfoundersDeclared:
    def test_confounder_declared_passes(self, graph_path: Path) -> None:
        """When a common cause has scic:confounds declared, check passes."""
        add_concept(graph_path, "X", concept_type="sci:Variable", ontology_id=None)
        add_concept(graph_path, "Y", concept_type="sci:Variable", ontology_id=None)
        add_concept(graph_path, "Z", concept_type="sci:Variable", ontology_id=None)
        add_hypothesis(graph_path, "h1", "Test", source="paper:doi_test")
        add_inquiry(graph_path, "conf-ok", "Conf OK", "hypothesis:h1", inquiry_type="causal")
        set_boundary_role(graph_path, "conf-ok", "concept/x", "BoundaryIn")
        set_boundary_role(graph_path, "conf-ok", "concept/y", "BoundaryOut")
        set_boundary_role(graph_path, "conf-ok", "concept/z", "BoundaryIn")
        set_treatment_outcome(graph_path, "conf-ok", treatment="concept/x", outcome="concept/y")
        # Z causes both X and Y (common cause = confounder)
        add_edge(graph_path, "concept/z", "scic:causes", "concept/x", graph_layer="graph/causal")
        add_edge(graph_path, "concept/z", "scic:causes", "concept/y", graph_layer="graph/causal")
        add_edge(graph_path, "concept/x", "scic:causes", "concept/y", graph_layer="graph/causal")
        # Declare the confounding
        add_edge(graph_path, "concept/z", "scic:confounds", "concept/x", graph_layer="graph/causal")
        results = validate_inquiry(graph_path, "conf-ok")
        conf_check = next((r for r in results if r["check"] == "confounders_declared"), None)
        assert conf_check is not None
        assert conf_check["status"] == "pass"

    def test_undeclared_confounder_warns(self, graph_path: Path) -> None:
        """When a common cause exists but no scic:confounds edge, check warns."""
        add_concept(graph_path, "X", concept_type="sci:Variable", ontology_id=None)
        add_concept(graph_path, "Y", concept_type="sci:Variable", ontology_id=None)
        add_concept(graph_path, "Z", concept_type="sci:Variable", ontology_id=None)
        add_hypothesis(graph_path, "h1", "Test", source="paper:doi_test")
        add_inquiry(graph_path, "conf-warn", "Conf Warn", "hypothesis:h1", inquiry_type="causal")
        set_boundary_role(graph_path, "conf-warn", "concept/x", "BoundaryIn")
        set_boundary_role(graph_path, "conf-warn", "concept/y", "BoundaryOut")
        set_boundary_role(graph_path, "conf-warn", "concept/z", "BoundaryIn")
        set_treatment_outcome(graph_path, "conf-warn", treatment="concept/x", outcome="concept/y")
        # Z causes both X and Y but no confounds edge declared
        add_edge(graph_path, "concept/z", "scic:causes", "concept/x", graph_layer="graph/causal")
        add_edge(graph_path, "concept/z", "scic:causes", "concept/y", graph_layer="graph/causal")
        add_edge(graph_path, "concept/x", "scic:causes", "concept/y", graph_layer="graph/causal")
        results = validate_inquiry(graph_path, "conf-warn")
        conf_check = next((r for r in results if r["check"] == "confounders_declared"), None)
        assert conf_check is not None
        assert conf_check["status"] == "warn"

    def test_no_common_causes_passes(self, graph_path: Path) -> None:
        """When there are no common causes, check passes."""
        add_concept(graph_path, "X", concept_type="sci:Variable", ontology_id=None)
        add_concept(graph_path, "Y", concept_type="sci:Variable", ontology_id=None)
        add_hypothesis(graph_path, "h1", "Test", source="paper:doi_test")
        add_inquiry(graph_path, "no-conf", "No Conf", "hypothesis:h1", inquiry_type="causal")
        set_boundary_role(graph_path, "no-conf", "concept/x", "BoundaryIn")
        set_boundary_role(graph_path, "no-conf", "concept/y", "BoundaryOut")
        set_treatment_outcome(graph_path, "no-conf", treatment="concept/x", outcome="concept/y")
        add_edge(graph_path, "concept/x", "scic:causes", "concept/y", graph_layer="graph/causal")
        results = validate_inquiry(graph_path, "no-conf")
        conf_check = next((r for r in results if r["check"] == "confounders_declared"), None)
        assert conf_check is not None
        assert conf_check["status"] == "pass"

    def test_general_inquiry_skips_confounder_check(self, graph_path: Path) -> None:
        """General inquiries don't get confounders_declared check."""
        add_hypothesis(graph_path, "h1", "Test", source="paper:doi_test")
        add_inquiry(graph_path, "gen", "General", "hypothesis:h1")
        results = validate_inquiry(graph_path, "gen")
        check_names = [r["check"] for r in results]
        assert "confounders_declared" not in check_names
```

**Step 2: Run tests to verify they fail**

Run: `cd science-tool && uv run --frozen pytest tests/test_causal.py::TestConfoundersDeclared -v`
Expected: FAIL — `confounders_declared` check not found in results.

**Step 3: Implement the check**

In `store.py`, after the `causal_acyclicity` check (after line 1074), add the `confounders_declared` check inside the `if inquiry_type == "causal":` block:

```python
        # confounders_declared — check for common causes without scic:confounds
        # Build adjacency from scic:causes edges
        children: dict[str, set[str]] = {}
        for s_str, o_str in causal_edges:
            children.setdefault(s_str, set()).add(o_str)

        # Find common causes: variables that cause 2+ other inquiry variables
        all_causal_targets = set()
        for s_str, o_str in causal_edges:
            all_causal_targets.add(o_str)

        # For each variable, find its children among inquiry members
        common_causes: list[str] = []
        for parent_str in {s for s, _ in causal_edges}:
            targets = children.get(parent_str, set())
            if len(targets) >= 2:
                common_causes.append(parent_str)

        # Check if common causes have scic:confounds edges declared
        confound_sources: set[str] = set()
        for s, _p, o in causal_graph.triples((None, SCIC_NS.confounds, None)):
            if s in members:
                confound_sources.add(str(s))

        undeclared = [c for c in common_causes if c not in confound_sources]
        if undeclared:
            short_names = [shorten_uri(u) for u in undeclared]
            results.append(
                {
                    "check": "confounders_declared",
                    "status": "warn",
                    "message": f"Common cause(s) without scic:confounds declaration: {', '.join(short_names)}",
                }
            )
        else:
            results.append(
                {
                    "check": "confounders_declared",
                    "status": "pass",
                    "message": "All common causes have confounders declared"
                        if common_causes
                        else "No common causes found",
                }
            )
```

**Step 4: Run tests to verify they pass**

Run: `cd science-tool && uv run --frozen pytest tests/test_causal.py::TestConfoundersDeclared -v`
Expected: PASS (4 tests)

Run: `cd science-tool && uv run --frozen pytest tests/test_causal.py tests/test_causal_cli.py -v`
Expected: All pass.

**Step 5: Commit**

```bash
git add -f science-tool/src/science_tool/graph/store.py science-tool/tests/test_causal.py
git commit -m "feat: add confounders_declared validation check for causal inquiries"
```

---

### Task 7: Add `identifiability` and `adjustment_sets` validation checks (pgmpy-optional)

**Files:**
- Modify: `science-tool/src/science_tool/graph/store.py:1043-1074` (validate_inquiry, causal section)
- Test: `science-tool/tests/test_causal.py`

These checks require pgmpy at runtime. They gracefully skip (status: "skip") when pgmpy is not installed.

**Step 1: Write the failing tests**

Add a new test class to `test_causal.py`:

```python
class TestIdentifiabilityCheck:
    def _build_identifiable_dag(self, graph_path: Path) -> str:
        """Build a DAG where X->Y is identifiable by adjusting for Z."""
        add_concept(graph_path, "X", concept_type="sci:Variable", ontology_id=None)
        add_concept(graph_path, "Y", concept_type="sci:Variable", ontology_id=None)
        add_concept(graph_path, "Z", concept_type="sci:Variable", ontology_id=None)
        add_hypothesis(graph_path, "h1", "Test", source="paper:doi_test")
        add_inquiry(graph_path, "ident-dag", "Identifiable", "hypothesis:h1", inquiry_type="causal")
        set_boundary_role(graph_path, "ident-dag", "concept/x", "BoundaryIn")
        set_boundary_role(graph_path, "ident-dag", "concept/y", "BoundaryOut")
        set_boundary_role(graph_path, "ident-dag", "concept/z", "BoundaryIn")
        set_treatment_outcome(graph_path, "ident-dag", treatment="concept/x", outcome="concept/y")
        add_edge(graph_path, "concept/x", "scic:causes", "concept/y", graph_layer="graph/causal")
        add_edge(graph_path, "concept/z", "scic:causes", "concept/x", graph_layer="graph/causal")
        add_edge(graph_path, "concept/z", "scic:causes", "concept/y", graph_layer="graph/causal")
        return "ident-dag"

    def test_identifiability_check_present(self, graph_path: Path) -> None:
        """Causal inquiry validation includes identifiability check."""
        slug = self._build_identifiable_dag(graph_path)
        results = validate_inquiry(graph_path, slug)
        check_names = [r["check"] for r in results]
        assert "identifiability" in check_names

    def test_adjustment_sets_check_present(self, graph_path: Path) -> None:
        """Causal inquiry validation includes adjustment_sets check."""
        slug = self._build_identifiable_dag(graph_path)
        results = validate_inquiry(graph_path, slug)
        check_names = [r["check"] for r in results]
        assert "adjustment_sets" in check_names

    def test_identifiability_without_treatment_outcome_skips(self, graph_path: Path) -> None:
        """Without treatment/outcome set, identifiability check is skipped."""
        add_concept(graph_path, "X", concept_type="sci:Variable", ontology_id=None)
        add_concept(graph_path, "Y", concept_type="sci:Variable", ontology_id=None)
        add_hypothesis(graph_path, "h1", "Test", source="paper:doi_test")
        add_inquiry(graph_path, "no-est", "No Estimand", "hypothesis:h1", inquiry_type="causal")
        set_boundary_role(graph_path, "no-est", "concept/x", "BoundaryIn")
        set_boundary_role(graph_path, "no-est", "concept/y", "BoundaryOut")
        add_edge(graph_path, "concept/x", "scic:causes", "concept/y", graph_layer="graph/causal")
        results = validate_inquiry(graph_path, "no-est")
        ident_check = next((r for r in results if r["check"] == "identifiability"), None)
        assert ident_check is not None
        assert ident_check["status"] == "skip"

    def test_general_inquiry_skips_identifiability(self, graph_path: Path) -> None:
        """General inquiries don't get identifiability or adjustment_sets checks."""
        add_hypothesis(graph_path, "h1", "Test", source="paper:doi_test")
        add_inquiry(graph_path, "gen", "General", "hypothesis:h1")
        results = validate_inquiry(graph_path, "gen")
        check_names = [r["check"] for r in results]
        assert "identifiability" not in check_names
        assert "adjustment_sets" not in check_names
```

**Step 2: Run tests to verify they fail**

Run: `cd science-tool && uv run --frozen pytest tests/test_causal.py::TestIdentifiabilityCheck -v`
Expected: FAIL

**Step 3: Implement the checks**

In `store.py`, after the `confounders_declared` check (still inside `if inquiry_type == "causal":`), add:

```python
        # identifiability + adjustment_sets — requires pgmpy (optional)
        treatment_uri = next(inquiry_graph.objects(inquiry_uri, SCI_NS.treatment), None)
        outcome_uri = next(inquiry_graph.objects(inquiry_uri, SCI_NS.outcome), None)

        if not treatment_uri or not outcome_uri:
            results.append(
                {
                    "check": "identifiability",
                    "status": "skip",
                    "message": "Treatment or outcome not set — cannot check identifiability",
                }
            )
            results.append(
                {
                    "check": "adjustment_sets",
                    "status": "skip",
                    "message": "Treatment or outcome not set — cannot compute adjustment sets",
                }
            )
        else:
            treatment_name = shorten_uri(str(treatment_uri)).rsplit("/", 1)[-1]
            outcome_name = shorten_uri(str(outcome_uri)).rsplit("/", 1)[-1]

            try:
                from pgmpy.models import BayesianNetwork
                from pgmpy.inference import CausalInference

                edge_list = [
                    (shorten_uri(s).rsplit("/", 1)[-1], shorten_uri(o).rsplit("/", 1)[-1])
                    for s, o in causal_edges
                ]
                if edge_list:
                    model = BayesianNetwork(edge_list)
                    ci = CausalInference(model)
                    try:
                        adj_sets = ci.get_all_backdoor_adjustment_sets(treatment_name, outcome_name)
                        adj_list = [set(s) for s in adj_sets]
                        if adj_list:
                            results.append(
                                {
                                    "check": "identifiability",
                                    "status": "pass",
                                    "message": f"Causal effect {treatment_name} -> {outcome_name} is identifiable via back-door",
                                }
                            )
                            sets_str = "; ".join(str(s) for s in adj_list)
                            results.append(
                                {
                                    "check": "adjustment_sets",
                                    "status": "info",
                                    "message": f"Valid adjustment sets: {sets_str}",
                                }
                            )
                        else:
                            results.append(
                                {
                                    "check": "identifiability",
                                    "status": "warn",
                                    "message": f"No valid back-door adjustment set found for {treatment_name} -> {outcome_name}",
                                }
                            )
                            results.append(
                                {
                                    "check": "adjustment_sets",
                                    "status": "info",
                                    "message": "No valid adjustment sets found",
                                }
                            )
                    except Exception as exc:
                        results.append(
                            {
                                "check": "identifiability",
                                "status": "warn",
                                "message": f"Could not compute identifiability: {exc}",
                            }
                        )
                        results.append(
                            {
                                "check": "adjustment_sets",
                                "status": "skip",
                                "message": f"Could not compute adjustment sets: {exc}",
                            }
                        )
                else:
                    results.append(
                        {
                            "check": "identifiability",
                            "status": "skip",
                            "message": "No causal edges found — cannot assess identifiability",
                        }
                    )
                    results.append(
                        {
                            "check": "adjustment_sets",
                            "status": "skip",
                            "message": "No causal edges found",
                        }
                    )

            except ImportError:
                results.append(
                    {
                        "check": "identifiability",
                        "status": "skip",
                        "message": "pgmpy not installed — install with: uv add pgmpy",
                    }
                )
                results.append(
                    {
                        "check": "adjustment_sets",
                        "status": "skip",
                        "message": "pgmpy not installed — install with: uv add pgmpy",
                    }
                )
```

**Important:** Since pgmpy is an optional dependency, we must handle `ImportError`. Tests that verify pass/warn statuses need pgmpy installed. If pgmpy is NOT installed in the test environment, those specific tests should be marked with `@pytest.mark.skipif` — but since `[causal]` extras include pgmpy, this should be fine in dev. If the test environment doesn't have pgmpy, the tests should check for `skip` status instead. For robustness, use a conditional in tests:

```python
try:
    import pgmpy
    HAS_PGMPY = True
except ImportError:
    HAS_PGMPY = False
```

Then mark the pgmpy-dependent tests with `@pytest.mark.skipif(not HAS_PGMPY, reason="pgmpy not installed")` and add a separate test for the skip case.

**Step 4: Run tests to verify they pass**

Run: `cd science-tool && uv run --frozen pytest tests/test_causal.py::TestIdentifiabilityCheck -v`
Expected: PASS (4 tests)

Run: `cd science-tool && uv run --frozen pytest tests/test_causal.py tests/test_causal_cli.py -v`
Expected: All pass.

**Step 5: Commit**

```bash
git add -f science-tool/src/science_tool/graph/store.py science-tool/tests/test_causal.py
git commit -m "feat: add identifiability and adjustment_sets validation checks (pgmpy-optional)"
```

---

### Task 8: Run full test suite and verify

**Step 1: Run all tests**

Run: `cd science-tool && uv run --frozen pytest tests/ -v`
Expected: All tests pass.

**Step 2: Run linting**

Run: `cd science-tool && uv run --frozen ruff check .`
Expected: No errors.

Run: `cd science-tool && uv run --frozen ruff format --check .`
Expected: No formatting issues (or fix with `ruff format .`).

**Step 3: Run pyright**

Run: `cd science-tool && uv run --frozen pyright`
Expected: No new errors (pre-existing rdflib typing warnings are OK).

**Step 4: Commit any fixes**

If linting/formatting required changes:
```bash
git add -f science-tool/
git commit -m "style: fix linting and formatting"
```

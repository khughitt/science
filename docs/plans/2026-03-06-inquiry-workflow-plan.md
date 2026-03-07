# Inquiry Workflow Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add the inquiry abstraction (named subgraphs with boundary nodes) to `science-tool`, then build 4 new slash commands (`sketch-model`, `specify-model`, `plan-pipeline`, `review-pipeline`) that guide users from research questions to reproducible computational workflows with full evidence provenance.

**Architecture:** Extends the existing `science-tool` graph store with inquiry-specific methods and CLI subcommands. Slash commands are markdown files in `commands/` that orchestrate `science-tool inquiry *` calls conversationally. A new template (`templates/inquiry.md`) and validation checks (`validate.sh` section 14) complete the infrastructure.

**Tech Stack:** Python 3.11+, rdflib (TriG/named graphs), Click, Rich, pytest, existing `science-tool` infrastructure.

**Reference docs:**
- `docs/plans/2026-03-06-inquiry-workflow-design.md` — full design
- `science-tool/src/science_tool/graph/store.py` — graph store (extend)
- `science-tool/src/science_tool/cli.py` — CLI (extend)
- `.claude-plugin/skills/knowledge-graph/SKILL.md` — ontology reference (extend)
- `commands/create-graph.md` — example command structure
- `scripts/validate.sh` — validation script (extend)

**Existing code:**
- `science-tool/src/science_tool/graph/store.py` — `GraphStore` class with `add_concept`, `add_edge`, etc.
- `science-tool/src/science_tool/cli.py` — Click CLI with `graph` command group
- `science-tool/tests/test_graph_cli.py` — existing graph CLI tests (48 tests)
- `scripts/validate.sh` — 13 validation sections

---

## Task 1: Ontology extensions — new predicates and types in store.py

**Files:**
- Modify: `science-tool/src/science_tool/graph/store.py` (PREDICATE_REGISTRY, constants)
- Test: `science-tool/tests/test_inquiry.py`

**Step 1: Write failing test for new predicates**

```python
# science-tool/tests/test_inquiry.py
"""Tests for inquiry abstraction."""

from science_tool.graph.store import PREDICATE_REGISTRY, SCI_NS


class TestOntologyExtensions:
    def test_inquiry_predicates_registered(self) -> None:
        """New inquiry predicates appear in the registry."""
        pred_names = [p["predicate"] for p in PREDICATE_REGISTRY]
        for pred in [
            "sci:target",
            "sci:boundaryRole",
            "sci:inquiryStatus",
            "sci:feedsInto",
            "sci:assumes",
            "sci:produces",
            "sci:paramValue",
            "sci:paramSource",
            "sci:paramRef",
            "sci:paramNote",
            "sci:observability",
            "sci:validatedBy",
        ]:
            assert pred in pred_names, f"{pred} not in PREDICATE_REGISTRY"

    def test_inquiry_predicates_have_inquiry_layer(self) -> None:
        """Inquiry-specific predicates use 'inquiry' layer."""
        inquiry_preds = [
            p for p in PREDICATE_REGISTRY if p["predicate"].startswith("sci:") and p["layer"] == "inquiry"
        ]
        # At least the core inquiry predicates
        assert len(inquiry_preds) >= 8

    def test_boundary_role_constants(self) -> None:
        """BoundaryIn and BoundaryOut are defined as URIRefs."""
        assert SCI_NS.BoundaryIn is not None
        assert SCI_NS.BoundaryOut is not None
        assert str(SCI_NS.BoundaryIn).endswith("BoundaryIn")
        assert str(SCI_NS.BoundaryOut).endswith("BoundaryOut")

    def test_inquiry_type_constants(self) -> None:
        """Inquiry entity types are defined."""
        for type_name in ["Inquiry", "Variable", "Transformation", "Assumption", "Unknown", "ValidationCheck"]:
            attr = getattr(SCI_NS, type_name)
            assert str(attr).endswith(type_name)
```

**Step 2: Run test to verify it fails**

Run: `cd science-tool && uv run --frozen pytest tests/test_inquiry.py::TestOntologyExtensions -v`
Expected: FAIL (missing predicates in registry)

**Step 3: Add predicates and constants to store.py**

In `store.py`, add to `PREDICATE_REGISTRY` (after existing entries):

```python
# Inquiry predicates
{"predicate": "sci:target", "description": "Inquiry targets hypothesis/question", "layer": "inquiry"},
{"predicate": "sci:boundaryRole", "description": "Boundary classification within inquiry", "layer": "inquiry"},
{"predicate": "sci:inquiryStatus", "description": "Inquiry lifecycle status", "layer": "inquiry"},
{"predicate": "sci:feedsInto", "description": "Data/information flow", "layer": "inquiry"},
{"predicate": "sci:assumes", "description": "Dependency on assumption", "layer": "inquiry"},
{"predicate": "sci:produces", "description": "Transformation yields output", "layer": "inquiry"},
{"predicate": "sci:paramValue", "description": "Parameter value", "layer": "inquiry"},
{"predicate": "sci:paramSource", "description": "Parameter source type", "layer": "inquiry"},
{"predicate": "sci:paramRef", "description": "Parameter reference", "layer": "inquiry"},
{"predicate": "sci:paramNote", "description": "Parameter rationale", "layer": "inquiry"},
{"predicate": "sci:observability", "description": "Variable observability status", "layer": "graph/knowledge"},
{"predicate": "sci:validatedBy", "description": "Step validated by criterion", "layer": "inquiry"},
```

Add `"inquiry"` to `PROJECT_ENTITY_PREFIXES`:

```python
PROJECT_ENTITY_PREFIXES = [
    "paper", "concept", "claim", "hypothesis", "dataset", "question", "evidence", "inquiry",
]
```

**Step 4: Run test to verify it passes**

Run: `cd science-tool && uv run --frozen pytest tests/test_inquiry.py::TestOntologyExtensions -v`
Expected: PASS

**Step 5: Commit**

```bash
git add science-tool/src/science_tool/graph/store.py science-tool/tests/test_inquiry.py
git commit -m "feat: add inquiry ontology extensions to predicate registry"
```

---

## Task 2: GraphStore inquiry methods — init, boundary, edges

**Files:**
- Modify: `science-tool/src/science_tool/graph/store.py`
- Modify: `science-tool/tests/test_inquiry.py`

**Step 1: Write failing tests for inquiry creation and boundary roles**

```python
# Add to science-tool/tests/test_inquiry.py
from pathlib import Path

import pytest
from rdflib import RDF, RDFS, SKOS, Literal, URIRef

from science_tool.graph.store import DCTERMS_NS, SCI_NS, GraphStore, PROJECT_NS


@pytest.fixture
def store(tmp_path: Path) -> GraphStore:
    """Fresh graph store for testing."""
    graph_path = tmp_path / "knowledge" / "graph.trig"
    graph_path.parent.mkdir(parents=True)
    s = GraphStore(str(graph_path))
    s.init_graph()
    return s


class TestInquiryCreation:
    def test_add_inquiry(self, store: GraphStore) -> None:
        """Create a new inquiry with metadata."""
        uri = store.add_inquiry(
            slug="sp-geometry",
            label="Signal peptide geometry",
            target="hypothesis:h03",
            description="Test SP embedding geometry",
        )
        assert "inquiry/sp_geometry" in str(uri)

        # Check inquiry node exists with correct type and properties
        inquiry_graph = store.graph.get_context(URIRef(str(PROJECT_NS) + "inquiry/sp_geometry"))
        triples = list(inquiry_graph)
        assert len(triples) > 0

        # Check type
        assert (uri, RDF.type, SCI_NS.Inquiry) in inquiry_graph
        # Check label
        assert (uri, RDFS.label, Literal("Signal peptide geometry")) in inquiry_graph
        # Check status
        assert (uri, SCI_NS.inquiryStatus, Literal("sketch")) in inquiry_graph

    def test_add_inquiry_custom_status(self, store: GraphStore) -> None:
        """Create inquiry with non-default status."""
        uri = store.add_inquiry(
            slug="test-inq",
            label="Test",
            target="hypothesis:h01",
            status="specified",
        )
        inquiry_graph = store.graph.get_context(URIRef(str(PROJECT_NS) + "inquiry/test_inq"))
        assert (uri, SCI_NS.inquiryStatus, Literal("specified")) in inquiry_graph

    def test_add_inquiry_duplicate_raises(self, store: GraphStore) -> None:
        """Cannot create two inquiries with the same slug."""
        store.add_inquiry(slug="dup", label="First", target="hypothesis:h01")
        with pytest.raises(ValueError, match="already exists"):
            store.add_inquiry(slug="dup", label="Second", target="hypothesis:h01")


class TestBoundaryRoles:
    def test_set_boundary_in(self, store: GraphStore) -> None:
        """Set a node as BoundaryIn within an inquiry."""
        store.add_inquiry(slug="test", label="Test", target="hypothesis:h01")
        store.add_concept("uniprot_data", concept_type="sci:Variable")
        store.set_boundary_role("test", "concept:uniprot_data", "BoundaryIn")

        inquiry_graph = store.graph.get_context(URIRef(str(PROJECT_NS) + "inquiry/test"))
        concept_uri = PROJECT_NS["concept/uniprot_data"]
        assert (concept_uri, SCI_NS.boundaryRole, SCI_NS.BoundaryIn) in inquiry_graph

    def test_set_boundary_out(self, store: GraphStore) -> None:
        """Set a node as BoundaryOut within an inquiry."""
        store.add_inquiry(slug="test", label="Test", target="hypothesis:h01")
        store.add_concept("results", concept_type="sci:Variable")
        store.set_boundary_role("test", "concept:results", "BoundaryOut")

        inquiry_graph = store.graph.get_context(URIRef(str(PROJECT_NS) + "inquiry/test"))
        concept_uri = PROJECT_NS["concept/results"]
        assert (concept_uri, SCI_NS.boundaryRole, SCI_NS.BoundaryOut) in inquiry_graph

    def test_invalid_boundary_role_raises(self, store: GraphStore) -> None:
        """Only BoundaryIn and BoundaryOut are valid roles."""
        store.add_inquiry(slug="test", label="Test", target="hypothesis:h01")
        store.add_concept("node", concept_type="sci:Concept")
        with pytest.raises(ValueError, match="Invalid boundary role"):
            store.set_boundary_role("test", "concept:node", "Interior")

    def test_boundary_role_nonexistent_inquiry_raises(self, store: GraphStore) -> None:
        """Cannot set boundary role on non-existent inquiry."""
        store.add_concept("node", concept_type="sci:Concept")
        with pytest.raises(ValueError, match="does not exist"):
            store.set_boundary_role("nonexistent", "concept:node", "BoundaryIn")


class TestInquiryEdges:
    def test_add_inquiry_edge(self, store: GraphStore) -> None:
        """Add an edge within an inquiry subgraph."""
        store.add_inquiry(slug="test", label="Test", target="hypothesis:h01")
        store.add_concept("input_data")
        store.add_concept("output_data")
        store.add_inquiry_edge("test", "concept:input_data", "sci:feedsInto", "concept:output_data")

        inquiry_graph = store.graph.get_context(URIRef(str(PROJECT_NS) + "inquiry/test"))
        assert (
            PROJECT_NS["concept/input_data"],
            SCI_NS.feedsInto,
            PROJECT_NS["concept/output_data"],
        ) in inquiry_graph

    def test_add_assumption(self, store: GraphStore) -> None:
        """Add an assumption to an inquiry."""
        store.add_inquiry(slug="test", label="Test", target="hypothesis:h01")
        uri = store.add_assumption(
            label="Mean pooling sufficient",
            source="paper:doi_10_1234_test",
            inquiry_slug="test",
        )
        assert "concept/mean_pooling_sufficient" in str(uri)

        # Check it's typed as Assumption in knowledge layer
        knowledge = store._knowledge_graph()
        assert (uri, RDF.type, SCI_NS.Assumption) in knowledge

        # Check it's linked in inquiry graph
        inquiry_graph = store.graph.get_context(URIRef(str(PROJECT_NS) + "inquiry/test"))
        assert len(list(inquiry_graph.triples((uri, None, None)))) > 0
```

**Step 2: Run test to verify it fails**

Run: `cd science-tool && uv run --frozen pytest tests/test_inquiry.py::TestInquiryCreation tests/test_inquiry.py::TestBoundaryRoles tests/test_inquiry.py::TestInquiryEdges -v`
Expected: FAIL (methods don't exist)

**Step 3: Implement inquiry methods on GraphStore**

Add the following methods to `GraphStore` in `store.py`. Key implementation notes:
- Use `self.graph.get_context(graph_uri)` to get/create named graphs (rdflib `ConjunctiveGraph` supports this)
- Inquiry named graphs use URI pattern `PROJECT_NS["inquiry/<slugified>"]`
- Slugify the slug using the existing `_slugify()` helper
- `add_inquiry` creates the named graph and adds metadata triples
- `set_boundary_role` adds a `sci:boundaryRole` triple in the inquiry's named graph
- `add_inquiry_edge` adds a triple in the inquiry's named graph
- `add_assumption` creates a concept with type `sci:Assumption` in the knowledge layer, and adds a reference in the inquiry graph if `inquiry_slug` is provided
- All methods call `self.save()` at the end

```python
def add_inquiry(self, slug: str, label: str, target: str,
                description: str = "", status: str = "sketch") -> URIRef:
    """Create a new inquiry named graph with metadata."""
    safe_slug = _slugify(slug)
    graph_uri = PROJECT_NS[f"inquiry/{safe_slug}"]
    inquiry_uri = PROJECT_NS[f"inquiry/{safe_slug}"]

    # Check for duplicate
    existing = self.graph.get_context(graph_uri)
    if (inquiry_uri, RDF.type, SCI_NS.Inquiry) in existing:
        msg = f"Inquiry '{safe_slug}' already exists"
        raise ValueError(msg)

    ctx = self.graph.get_context(graph_uri)
    ctx.add((inquiry_uri, RDF.type, SCI_NS.Inquiry))
    ctx.add((inquiry_uri, RDFS.label, Literal(label)))
    ctx.add((inquiry_uri, SCI_NS.inquiryStatus, Literal(status)))
    ctx.add((inquiry_uri, DCTERMS_NS.created, Literal(datetime.now(UTC).strftime("%Y-%m-%d"))))

    # Resolve and link target
    target_uri = self._resolve_term(target)
    ctx.add((inquiry_uri, SCI_NS.target, target_uri))

    if description:
        ctx.add((inquiry_uri, RDFS.comment, Literal(description)))

    self.save()
    return inquiry_uri

def set_boundary_role(self, inquiry_slug: str, entity: str, role: str) -> None:
    """Assign BoundaryIn or BoundaryOut role to an entity within an inquiry."""
    safe_slug = _slugify(inquiry_slug)
    graph_uri = PROJECT_NS[f"inquiry/{safe_slug}"]
    inquiry_uri = PROJECT_NS[f"inquiry/{safe_slug}"]

    # Validate inquiry exists
    ctx = self.graph.get_context(graph_uri)
    if (inquiry_uri, RDF.type, SCI_NS.Inquiry) not in ctx:
        msg = f"Inquiry '{safe_slug}' does not exist"
        raise ValueError(msg)

    # Validate role
    valid_roles = {"BoundaryIn": SCI_NS.BoundaryIn, "BoundaryOut": SCI_NS.BoundaryOut}
    if role not in valid_roles:
        msg = f"Invalid boundary role '{role}'. Must be BoundaryIn or BoundaryOut"
        raise ValueError(msg)

    entity_uri = self._resolve_term(entity)
    ctx.add((entity_uri, SCI_NS.boundaryRole, valid_roles[role]))
    self.save()

def add_inquiry_edge(self, inquiry_slug: str, subject: str,
                     predicate: str, obj: str) -> None:
    """Add an edge within an inquiry subgraph."""
    safe_slug = _slugify(inquiry_slug)
    graph_uri = PROJECT_NS[f"inquiry/{safe_slug}"]
    inquiry_uri = PROJECT_NS[f"inquiry/{safe_slug}"]

    ctx = self.graph.get_context(graph_uri)
    if (inquiry_uri, RDF.type, SCI_NS.Inquiry) not in ctx:
        msg = f"Inquiry '{safe_slug}' does not exist"
        raise ValueError(msg)

    subj_uri = self._resolve_term(subject)
    pred_uri = self._resolve_term(predicate)
    obj_uri = self._resolve_term(obj)
    ctx.add((subj_uri, pred_uri, obj_uri))
    self.save()

def add_assumption(self, label: str, source: str,
                   inquiry_slug: str | None = None) -> URIRef:
    """Add an assumption entity, optionally within an inquiry."""
    # Add as concept with Assumption type in knowledge layer
    uri = self.add_concept(label, concept_type="sci:Assumption", source=source)

    # Also add type in knowledge layer
    knowledge = self._knowledge_graph()
    knowledge.add((uri, RDF.type, SCI_NS.Assumption))

    if inquiry_slug:
        safe_slug = _slugify(inquiry_slug)
        graph_uri = PROJECT_NS[f"inquiry/{safe_slug}"]
        ctx = self.graph.get_context(graph_uri)
        ctx.add((uri, RDF.type, SCI_NS.Assumption))

    self.save()
    return uri
```

**Step 4: Run tests to verify they pass**

Run: `cd science-tool && uv run --frozen pytest tests/test_inquiry.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add science-tool/src/science_tool/graph/store.py science-tool/tests/test_inquiry.py
git commit -m "feat: add inquiry methods to GraphStore (init, boundary, edges, assumptions)"
```

---

## Task 3: GraphStore inquiry methods — transformations, params, queries

**Files:**
- Modify: `science-tool/src/science_tool/graph/store.py`
- Modify: `science-tool/tests/test_inquiry.py`

**Step 1: Write failing tests**

```python
# Add to science-tool/tests/test_inquiry.py

class TestTransformations:
    def test_add_transformation(self, store: GraphStore) -> None:
        """Add a transformation step to an inquiry."""
        store.add_inquiry(slug="test", label="Test", target="hypothesis:h01")
        uri = store.add_transformation(
            label="Extract sequences",
            inquiry_slug="test",
            tool="BioPython",
        )
        assert "concept/extract_sequences" in str(uri)

        inquiry_graph = store.graph.get_context(URIRef(str(PROJECT_NS) + "inquiry/test"))
        assert (uri, RDF.type, SCI_NS.Transformation) in inquiry_graph

    def test_add_transformation_with_params(self, store: GraphStore) -> None:
        """Transformation with parameter metadata."""
        store.add_inquiry(slug="test", label="Test", target="hypothesis:h01")
        uri = store.add_transformation(
            label="Embed sequences",
            inquiry_slug="test",
            tool="seq-feats embed",
            params={
                "batch_size": {"value": "32", "source": "convention", "note": "GPU memory limit"},
            },
        )
        inquiry_graph = store.graph.get_context(URIRef(str(PROJECT_NS) + "inquiry/test"))
        # Check param metadata is attached
        assert (uri, SCI_NS.paramValue, None) in inquiry_graph or \
               len(list(inquiry_graph.triples((uri, None, None)))) > 3


class TestParamMetadata:
    def test_set_param_metadata(self, store: GraphStore) -> None:
        """Attach AnnotatedParam-style metadata to an entity."""
        store.add_concept("pooling_method")
        store.set_param_metadata(
            entity="concept:pooling_method",
            value="mean",
            source="design_decision",
            refs=["doc/04-approach.md"],
            note="Captures SP-relevant information",
        )
        # Check metadata exists in knowledge layer
        knowledge = store._knowledge_graph()
        entity_uri = PROJECT_NS["concept/pooling_method"]
        assert (entity_uri, SCI_NS.paramValue, Literal("mean")) in knowledge
        assert (entity_uri, SCI_NS.paramSource, Literal("design_decision")) in knowledge


class TestInquiryQueries:
    def test_list_inquiries_empty(self, store: GraphStore) -> None:
        """List inquiries returns empty list when none exist."""
        result = store.list_inquiries()
        assert result == []

    def test_list_inquiries(self, store: GraphStore) -> None:
        """List inquiries returns all inquiry metadata."""
        store.add_inquiry(slug="inq-1", label="First", target="hypothesis:h01")
        store.add_inquiry(slug="inq-2", label="Second", target="hypothesis:h02")
        result = store.list_inquiries()
        assert len(result) == 2
        labels = {r["label"] for r in result}
        assert labels == {"First", "Second"}

    def test_get_inquiry(self, store: GraphStore) -> None:
        """Get full inquiry details."""
        store.add_inquiry(slug="test", label="Test", target="hypothesis:h01",
                         description="Test inquiry")
        store.add_concept("data_in")
        store.set_boundary_role("test", "concept:data_in", "BoundaryIn")
        store.add_concept("result_out")
        store.set_boundary_role("test", "concept:result_out", "BoundaryOut")
        store.add_inquiry_edge("test", "concept:data_in", "sci:feedsInto", "concept:result_out")

        result = store.get_inquiry("test")
        assert result["label"] == "Test"
        assert result["status"] == "sketch"
        assert len(result["boundary_in"]) == 1
        assert len(result["boundary_out"]) == 1
        assert len(result["edges"]) >= 1

    def test_get_inquiry_nonexistent_raises(self, store: GraphStore) -> None:
        """Getting non-existent inquiry raises."""
        with pytest.raises(ValueError, match="does not exist"):
            store.get_inquiry("nonexistent")
```

**Step 2: Run tests to verify they fail**

Run: `cd science-tool && uv run --frozen pytest tests/test_inquiry.py::TestTransformations tests/test_inquiry.py::TestParamMetadata tests/test_inquiry.py::TestInquiryQueries -v`
Expected: FAIL

**Step 3: Implement methods**

Add to `GraphStore`:

```python
def add_transformation(self, label: str, inquiry_slug: str,
                       tool: str = "", params: dict | None = None) -> URIRef:
    """Add a transformation step within an inquiry."""
    safe_slug = _slugify(inquiry_slug)
    graph_uri = PROJECT_NS[f"inquiry/{safe_slug}"]
    inquiry_uri = PROJECT_NS[f"inquiry/{safe_slug}"]

    ctx = self.graph.get_context(graph_uri)
    if (inquiry_uri, RDF.type, SCI_NS.Inquiry) not in ctx:
        msg = f"Inquiry '{safe_slug}' does not exist"
        raise ValueError(msg)

    uri = self.add_concept(label, concept_type="sci:Transformation")
    ctx.add((uri, RDF.type, SCI_NS.Transformation))

    if tool:
        ctx.add((uri, SCI_NS["tool"], Literal(tool)))

    if params:
        for key, meta in params.items():
            param_node = PROJECT_NS[f"concept/{_slugify(label)}__param__{_slugify(key)}"]
            ctx.add((uri, SCI_NS.paramValue, Literal(meta.get("value", ""))))
            if "source" in meta:
                ctx.add((uri, SCI_NS.paramSource, Literal(meta["source"])))
            if "note" in meta:
                ctx.add((uri, SCI_NS.paramNote, Literal(meta["note"])))
            if "refs" in meta:
                for ref in meta["refs"]:
                    ctx.add((uri, SCI_NS.paramRef, Literal(ref)))

    self.save()
    return uri

def set_param_metadata(self, entity: str, value: str, source: str,
                       refs: list[str] | None = None, note: str = "") -> None:
    """Attach AnnotatedParam-style metadata to an entity."""
    entity_uri = self._resolve_term(entity)
    knowledge = self._knowledge_graph()
    knowledge.add((entity_uri, SCI_NS.paramValue, Literal(value)))
    knowledge.add((entity_uri, SCI_NS.paramSource, Literal(source)))
    if note:
        knowledge.add((entity_uri, SCI_NS.paramNote, Literal(note)))
    if refs:
        for ref in refs:
            knowledge.add((entity_uri, SCI_NS.paramRef, Literal(ref)))
    self.save()

def list_inquiries(self) -> list[dict]:
    """List all inquiry subgraphs with basic metadata."""
    results = []
    for ctx in self.graph.contexts():
        graph_uri = ctx.identifier
        if not str(graph_uri).startswith(str(PROJECT_NS) + "inquiry/"):
            continue
        inquiry_uri = graph_uri
        label = str(ctx.value(inquiry_uri, RDFS.label) or "")
        status = str(ctx.value(inquiry_uri, SCI_NS.inquiryStatus) or "")
        target = str(ctx.value(inquiry_uri, SCI_NS.target) or "")
        created = str(ctx.value(inquiry_uri, DCTERMS_NS.created) or "")
        results.append({
            "slug": str(graph_uri).split("inquiry/")[-1],
            "label": label,
            "status": status,
            "target": target,
            "created": created,
        })
    return results

def get_inquiry(self, slug: str) -> dict:
    """Return inquiry metadata, nodes, edges, and boundary roles."""
    safe_slug = _slugify(slug)
    graph_uri = PROJECT_NS[f"inquiry/{safe_slug}"]
    inquiry_uri = graph_uri

    ctx = self.graph.get_context(graph_uri)
    if (inquiry_uri, RDF.type, SCI_NS.Inquiry) not in ctx:
        msg = f"Inquiry '{safe_slug}' does not exist"
        raise ValueError(msg)

    label = str(ctx.value(inquiry_uri, RDFS.label) or "")
    status = str(ctx.value(inquiry_uri, SCI_NS.inquiryStatus) or "")
    target = str(ctx.value(inquiry_uri, SCI_NS.target) or "")
    description = str(ctx.value(inquiry_uri, RDFS.comment) or "")
    created = str(ctx.value(inquiry_uri, DCTERMS_NS.created) or "")

    # Collect boundary roles
    boundary_in = []
    boundary_out = []
    for s, _, _ in ctx.triples((None, SCI_NS.boundaryRole, SCI_NS.BoundaryIn)):
        boundary_in.append(str(s))
    for s, _, _ in ctx.triples((None, SCI_NS.boundaryRole, SCI_NS.BoundaryOut)):
        boundary_out.append(str(s))

    # Collect edges (excluding metadata predicates)
    metadata_preds = {RDF.type, RDFS.label, RDFS.comment, SCI_NS.inquiryStatus,
                      SCI_NS.target, SCI_NS.boundaryRole, DCTERMS_NS.created}
    edges = []
    for s, p, o in ctx:
        if p not in metadata_preds:
            edges.append({"subject": str(s), "predicate": str(p), "object": str(o)})

    return {
        "slug": safe_slug,
        "label": label,
        "status": status,
        "target": target,
        "description": description,
        "created": created,
        "boundary_in": boundary_in,
        "boundary_out": boundary_out,
        "edges": edges,
    }
```

**Step 4: Run tests to verify they pass**

Run: `cd science-tool && uv run --frozen pytest tests/test_inquiry.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add science-tool/src/science_tool/graph/store.py science-tool/tests/test_inquiry.py
git commit -m "feat: add transformation, param metadata, and query methods to GraphStore"
```

---

## Task 4: Inquiry validation — boundary reachability, cycles, unknowns

**Files:**
- Modify: `science-tool/src/science_tool/graph/store.py`
- Modify: `science-tool/tests/test_inquiry.py`

**Step 1: Write failing tests**

```python
# Add to science-tool/tests/test_inquiry.py

class TestInquiryValidation:
    def test_valid_inquiry_passes(self, store: GraphStore) -> None:
        """A well-formed inquiry passes all checks."""
        store.add_inquiry(slug="valid", label="Valid", target="hypothesis:h01")
        store.add_concept("data_in")
        store.add_concept("result_out")
        store.set_boundary_role("valid", "concept:data_in", "BoundaryIn")
        store.set_boundary_role("valid", "concept:result_out", "BoundaryOut")
        store.add_inquiry_edge("valid", "concept:data_in", "sci:feedsInto", "concept:result_out")

        results = store.validate_inquiry("valid")
        statuses = {r["check"]: r["status"] for r in results}
        assert statuses["boundary_reachability"] == "pass"
        assert statuses["no_cycles"] == "pass"

    def test_unreachable_boundary_out_fails(self, store: GraphStore) -> None:
        """BoundaryOut not reachable from any BoundaryIn fails validation."""
        store.add_inquiry(slug="unreach", label="Unreachable", target="hypothesis:h01")
        store.add_concept("data_in")
        store.add_concept("result_out")
        store.add_concept("disconnected_out")
        store.set_boundary_role("unreach", "concept:data_in", "BoundaryIn")
        store.set_boundary_role("unreach", "concept:result_out", "BoundaryOut")
        store.set_boundary_role("unreach", "concept:disconnected_out", "BoundaryOut")
        store.add_inquiry_edge("unreach", "concept:data_in", "sci:feedsInto", "concept:result_out")
        # disconnected_out has no incoming path

        results = store.validate_inquiry("unreach")
        statuses = {r["check"]: r["status"] for r in results}
        assert statuses["boundary_reachability"] == "fail"

    def test_cycle_in_feeds_into_fails(self, store: GraphStore) -> None:
        """Cycles in feedsInto edges fail validation."""
        store.add_inquiry(slug="cycle", label="Cycle", target="hypothesis:h01")
        store.add_concept("a")
        store.add_concept("b")
        store.set_boundary_role("cycle", "concept:a", "BoundaryIn")
        store.set_boundary_role("cycle", "concept:b", "BoundaryOut")
        store.add_inquiry_edge("cycle", "concept:a", "sci:feedsInto", "concept:b")
        store.add_inquiry_edge("cycle", "concept:b", "sci:feedsInto", "concept:a")

        results = store.validate_inquiry("cycle")
        statuses = {r["check"]: r["status"] for r in results}
        assert statuses["no_cycles"] == "fail"

    def test_unknown_in_specified_fails(self, store: GraphStore) -> None:
        """sci:Unknown nodes in a specified inquiry fail validation."""
        store.add_inquiry(slug="unk", label="Unknown", target="hypothesis:h01",
                         status="specified")
        store.add_concept("mystery", concept_type="sci:Unknown")
        store.add_concept("data_in")
        store.add_concept("result_out")
        store.set_boundary_role("unk", "concept:data_in", "BoundaryIn")
        store.set_boundary_role("unk", "concept:result_out", "BoundaryOut")
        store.add_inquiry_edge("unk", "concept:data_in", "sci:feedsInto", "concept:mystery")
        store.add_inquiry_edge("unk", "concept:mystery", "sci:feedsInto", "concept:result_out")

        results = store.validate_inquiry("unk")
        statuses = {r["check"]: r["status"] for r in results}
        assert statuses["unknown_resolution"] == "fail"

    def test_unknown_in_sketch_passes(self, store: GraphStore) -> None:
        """sci:Unknown nodes in a sketch are allowed."""
        store.add_inquiry(slug="sketch-unk", label="Sketch", target="hypothesis:h01",
                         status="sketch")
        store.add_concept("mystery", concept_type="sci:Unknown")
        store.add_concept("data_in")
        store.add_concept("result_out")
        store.set_boundary_role("sketch-unk", "concept:data_in", "BoundaryIn")
        store.set_boundary_role("sketch-unk", "concept:result_out", "BoundaryOut")
        store.add_inquiry_edge("sketch-unk", "concept:data_in", "sci:feedsInto", "concept:mystery")
        store.add_inquiry_edge("sketch-unk", "concept:mystery", "sci:feedsInto", "concept:result_out")

        results = store.validate_inquiry("sketch-unk")
        statuses = {r["check"]: r["status"] for r in results}
        assert statuses["unknown_resolution"] == "pass"
```

**Step 2: Run tests to verify they fail**

Run: `cd science-tool && uv run --frozen pytest tests/test_inquiry.py::TestInquiryValidation -v`
Expected: FAIL

**Step 3: Implement validate_inquiry**

Add to `GraphStore`:

```python
def validate_inquiry(self, slug: str) -> list[dict]:
    """Run inquiry-specific validation checks."""
    safe_slug = _slugify(slug)
    graph_uri = PROJECT_NS[f"inquiry/{safe_slug}"]
    inquiry_uri = graph_uri

    ctx = self.graph.get_context(graph_uri)
    if (inquiry_uri, RDF.type, SCI_NS.Inquiry) not in ctx:
        msg = f"Inquiry '{safe_slug}' does not exist"
        raise ValueError(msg)

    status = str(ctx.value(inquiry_uri, SCI_NS.inquiryStatus) or "sketch")
    results = []

    # Collect boundary nodes
    boundary_in = set()
    boundary_out = set()
    for s, _, _ in ctx.triples((None, SCI_NS.boundaryRole, SCI_NS.BoundaryIn)):
        boundary_in.add(s)
    for s, _, _ in ctx.triples((None, SCI_NS.boundaryRole, SCI_NS.BoundaryOut)):
        boundary_out.add(s)

    # Build adjacency from feedsInto + produces edges
    flow_preds = {SCI_NS.feedsInto, SCI_NS.produces}
    adjacency: dict[URIRef, set[URIRef]] = {}
    for s, p, o in ctx:
        if p in flow_preds and isinstance(o, URIRef):
            adjacency.setdefault(s, set()).add(o)

    # Check 1: boundary_reachability
    # BFS from all BoundaryIn nodes; every BoundaryOut must be reachable
    reachable = set()
    queue = list(boundary_in)
    while queue:
        node = queue.pop(0)
        if node in reachable:
            continue
        reachable.add(node)
        for neighbor in adjacency.get(node, set()):
            if neighbor not in reachable:
                queue.append(neighbor)

    unreachable = boundary_out - reachable
    if unreachable:
        results.append({
            "check": "boundary_reachability",
            "status": "fail",
            "message": f"{len(unreachable)} BoundaryOut node(s) not reachable from any BoundaryIn",
            "details": [str(u) for u in unreachable],
        })
    else:
        results.append({
            "check": "boundary_reachability",
            "status": "pass",
            "message": "All BoundaryOut nodes reachable from BoundaryIn",
        })

    # Check 2: no_cycles (in feedsInto/produces edges)
    # Topological sort attempt
    in_degree: dict[URIRef, int] = {}
    all_nodes_in_flow: set[URIRef] = set()
    for s, neighbors in adjacency.items():
        all_nodes_in_flow.add(s)
        in_degree.setdefault(s, 0)
        for n in neighbors:
            all_nodes_in_flow.add(n)
            in_degree[n] = in_degree.get(n, 0) + 1
            in_degree.setdefault(s, 0)

    queue_topo = [n for n in all_nodes_in_flow if in_degree.get(n, 0) == 0]
    sorted_count = 0
    while queue_topo:
        node = queue_topo.pop(0)
        sorted_count += 1
        for neighbor in adjacency.get(node, set()):
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue_topo.append(neighbor)

    if sorted_count < len(all_nodes_in_flow):
        results.append({
            "check": "no_cycles",
            "status": "fail",
            "message": "Cycle detected in feedsInto/produces edges",
        })
    else:
        results.append({
            "check": "no_cycles",
            "status": "pass",
            "message": "No cycles in data flow edges",
        })

    # Check 3: unknown_resolution (only enforced for specified+)
    knowledge = self._knowledge_graph()
    unknown_nodes = set()
    for s, _, _ in knowledge.triples((None, RDF.type, SCI_NS.Unknown)):
        # Check if this unknown is referenced in this inquiry
        if any(ctx.triples((s, None, None))) or any(ctx.triples((None, None, s))):
            unknown_nodes.add(s)

    # Also check inquiry graph directly for Unknown type
    for s, _, _ in ctx.triples((None, RDF.type, SCI_NS.Unknown)):
        unknown_nodes.add(s)

    if unknown_nodes and status != "sketch":
        results.append({
            "check": "unknown_resolution",
            "status": "fail",
            "message": f"{len(unknown_nodes)} sci:Unknown node(s) in {status} inquiry",
            "details": [str(u) for u in unknown_nodes],
        })
    else:
        results.append({
            "check": "unknown_resolution",
            "status": "pass",
            "message": "No unresolved unknowns" if not unknown_nodes else "Unknowns allowed in sketch",
        })

    # Check 4: target_exists
    target = ctx.value(inquiry_uri, SCI_NS.target)
    if target:
        target_exists = (
            any(knowledge.triples((target, RDF.type, SCI_NS.Hypothesis)))
            or any(knowledge.triples((target, RDF.type, SCI_NS.Question)))
            or any(knowledge.triples((target, RDF.type, None)))
        )
        results.append({
            "check": "target_exists",
            "status": "pass" if target_exists else "warn",
            "message": "Target exists" if target_exists else f"Target {target} not found in knowledge graph",
        })

    return results
```

**Step 4: Run tests to verify they pass**

Run: `cd science-tool && uv run --frozen pytest tests/test_inquiry.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add science-tool/src/science_tool/graph/store.py science-tool/tests/test_inquiry.py
git commit -m "feat: add inquiry validation (boundary reachability, cycles, unknowns)"
```

---

## Task 5: CLI subcommands — `science-tool inquiry *`

**Files:**
- Modify: `science-tool/src/science_tool/cli.py`
- Create: `science-tool/tests/test_inquiry_cli.py`

**Step 1: Write failing CLI tests**

```python
# science-tool/tests/test_inquiry_cli.py
"""CLI tests for inquiry subcommands."""

from pathlib import Path

import pytest
from click.testing import CliRunner

from science_tool.cli import cli


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def graph_dir(tmp_path: Path) -> Path:
    """Create a temp directory with initialized graph."""
    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir()
    runner = CliRunner()
    result = runner.invoke(cli, ["graph", "init", "--path", str(knowledge_dir / "graph.trig")])
    assert result.exit_code == 0
    # Add a hypothesis so we have a target
    runner.invoke(cli, [
        "graph", "add", "hypothesis", "H01",
        "--text", "Test hypothesis",
        "--source", "paper:doi_test",
        "--path", str(knowledge_dir / "graph.trig"),
    ])
    return knowledge_dir


class TestInquiryInit:
    def test_init_inquiry(self, runner: CliRunner, graph_dir: Path) -> None:
        result = runner.invoke(cli, [
            "inquiry", "init", "sp-geometry",
            "--label", "Signal peptide geometry",
            "--target", "hypothesis:h01",
            "--path", str(graph_dir / "graph.trig"),
        ])
        assert result.exit_code == 0
        assert "inquiry/sp_geometry" in result.output

    def test_init_duplicate_fails(self, runner: CliRunner, graph_dir: Path) -> None:
        path = str(graph_dir / "graph.trig")
        runner.invoke(cli, ["inquiry", "init", "dup", "--label", "A", "--target", "hypothesis:h01", "--path", path])
        result = runner.invoke(cli, ["inquiry", "init", "dup", "--label", "B", "--target", "hypothesis:h01", "--path", path])
        assert result.exit_code != 0


class TestInquiryAddNode:
    def test_add_boundary_in(self, runner: CliRunner, graph_dir: Path) -> None:
        path = str(graph_dir / "graph.trig")
        runner.invoke(cli, ["inquiry", "init", "test", "--label", "Test", "--target", "hypothesis:h01", "--path", path])
        runner.invoke(cli, ["graph", "add", "concept", "input_data", "--path", path])
        result = runner.invoke(cli, [
            "inquiry", "add-node", "test", "concept:input_data",
            "--role", "BoundaryIn",
            "--path", path,
        ])
        assert result.exit_code == 0


class TestInquiryAddEdge:
    def test_add_edge(self, runner: CliRunner, graph_dir: Path) -> None:
        path = str(graph_dir / "graph.trig")
        runner.invoke(cli, ["inquiry", "init", "test", "--label", "Test", "--target", "hypothesis:h01", "--path", path])
        runner.invoke(cli, ["graph", "add", "concept", "a", "--path", path])
        runner.invoke(cli, ["graph", "add", "concept", "b", "--path", path])
        result = runner.invoke(cli, [
            "inquiry", "add-edge", "test", "concept:a", "sci:feedsInto", "concept:b",
            "--path", path,
        ])
        assert result.exit_code == 0


class TestInquiryList:
    def test_list_empty(self, runner: CliRunner, graph_dir: Path) -> None:
        path = str(graph_dir / "graph.trig")
        result = runner.invoke(cli, ["inquiry", "list", "--path", path, "--format", "json"])
        assert result.exit_code == 0

    def test_list_with_inquiries(self, runner: CliRunner, graph_dir: Path) -> None:
        path = str(graph_dir / "graph.trig")
        runner.invoke(cli, ["inquiry", "init", "inq1", "--label", "First", "--target", "hypothesis:h01", "--path", path])
        runner.invoke(cli, ["inquiry", "init", "inq2", "--label", "Second", "--target", "hypothesis:h01", "--path", path])
        result = runner.invoke(cli, ["inquiry", "list", "--path", path, "--format", "json"])
        assert result.exit_code == 0
        assert "First" in result.output
        assert "Second" in result.output


class TestInquiryShow:
    def test_show_inquiry(self, runner: CliRunner, graph_dir: Path) -> None:
        path = str(graph_dir / "graph.trig")
        runner.invoke(cli, ["inquiry", "init", "test", "--label", "Test", "--target", "hypothesis:h01", "--path", path])
        result = runner.invoke(cli, ["inquiry", "show", "test", "--path", path, "--format", "json"])
        assert result.exit_code == 0
        assert "Test" in result.output


class TestInquiryValidate:
    def test_validate_valid(self, runner: CliRunner, graph_dir: Path) -> None:
        path = str(graph_dir / "graph.trig")
        runner.invoke(cli, ["inquiry", "init", "test", "--label", "Test", "--target", "hypothesis:h01", "--path", path])
        runner.invoke(cli, ["graph", "add", "concept", "din", "--path", path])
        runner.invoke(cli, ["graph", "add", "concept", "dout", "--path", path])
        runner.invoke(cli, ["inquiry", "add-node", "test", "concept:din", "--role", "BoundaryIn", "--path", path])
        runner.invoke(cli, ["inquiry", "add-node", "test", "concept:dout", "--role", "BoundaryOut", "--path", path])
        runner.invoke(cli, ["inquiry", "add-edge", "test", "concept:din", "sci:feedsInto", "concept:dout", "--path", path])
        result = runner.invoke(cli, ["inquiry", "validate", "test", "--path", path, "--format", "json"])
        assert result.exit_code == 0
```

**Step 2: Run tests to verify they fail**

Run: `cd science-tool && uv run --frozen pytest tests/test_inquiry_cli.py -v`
Expected: FAIL (no `inquiry` command group)

**Step 3: Implement CLI subcommands**

Add to `cli.py` — create a new Click group `inquiry` with subcommands: `init`, `add-node`, `add-edge`, `list`, `show`, `validate`. Follow the existing pattern from the `graph` command group. Each command takes `--path` and `--format` options matching the existing contract.

Key implementation notes:
- `inquiry` is a new top-level Click group (sibling to `graph`)
- All subcommands use the shared `format_output()` helper for `--format table|json`
- `init` echoes the created inquiry URI
- `add-node` echoes the entity URI and its boundary role
- `add-edge` echoes subject, predicate, object URIs
- `validate` uses non-zero exit code on failures

**Step 4: Run tests to verify they pass**

Run: `cd science-tool && uv run --frozen pytest tests/test_inquiry_cli.py -v`
Expected: PASS

**Step 5: Run full test suite to check for regressions**

Run: `cd science-tool && uv run --frozen pytest -v`
Expected: All tests pass (existing 49 + new inquiry tests)

**Step 6: Commit**

```bash
git add science-tool/src/science_tool/cli.py science-tool/tests/test_inquiry_cli.py
git commit -m "feat: add inquiry CLI subcommands (init, add-node, add-edge, list, show, validate)"
```

---

## Task 6: Inquiry template and document generation

**Files:**
- Create: `templates/inquiry.md`
- Modify: `science-tool/src/science_tool/graph/store.py` (add `render_inquiry_doc` method)
- Modify: `science-tool/tests/test_inquiry.py`

**Step 1: Create the inquiry template**

```markdown
# Inquiry: {{label}}

- **Slug:** {{slug}}
- **Target:** {{target_label}} ({{target_id}})
- **Status:** {{status}}
- **Created:** {{created}}

## Summary

{{description}}

## Variables

### Boundary In (Givens)

| Variable | Type | Provenance |
|---|---|---|
{{boundary_in_rows}}

### Boundary Out (Produces)

| Variable | Type | Validation |
|---|---|---|
{{boundary_out_rows}}

### Interior

| Variable | Type | Notes |
|---|---|---|
{{interior_rows}}

## Data Flow

{{edge_list}}

## Assumptions

| Assumption | Evidence |
|---|---|
{{assumption_rows}}

## Parameters

| Parameter | Value | Source | References | Note |
|---|---|---|---|---|
{{param_rows}}
```

**Step 2: Write failing test for render method**

```python
# Add to test_inquiry.py

class TestInquiryRender:
    def test_render_inquiry_doc(self, store: GraphStore) -> None:
        """Render inquiry as markdown document."""
        store.add_inquiry(slug="test", label="Test Inquiry", target="hypothesis:h01",
                         description="A test inquiry")
        store.add_concept("data_in", concept_type="sci:Variable")
        store.add_concept("result_out", concept_type="sci:Variable")
        store.set_boundary_role("test", "concept:data_in", "BoundaryIn")
        store.set_boundary_role("test", "concept:result_out", "BoundaryOut")
        store.add_inquiry_edge("test", "concept:data_in", "sci:feedsInto", "concept:result_out")

        doc = store.render_inquiry_doc("test")
        assert "# Inquiry: Test Inquiry" in doc
        assert "data_in" in doc
        assert "result_out" in doc
        assert "BoundaryIn" in doc or "Boundary In" in doc
```

**Step 3: Implement render_inquiry_doc**

Add to `GraphStore`:

```python
def render_inquiry_doc(self, slug: str) -> str:
    """Render an inquiry as a markdown document."""
    info = self.get_inquiry(slug)

    lines = [
        f"# Inquiry: {info['label']}",
        "",
        f"- **Slug:** {info['slug']}",
        f"- **Target:** {info['target']}",
        f"- **Status:** {info['status']}",
        f"- **Created:** {info['created']}",
        "",
        "## Summary",
        "",
        info.get("description", ""),
        "",
        "## Variables",
        "",
        "### Boundary In (Givens)",
        "",
        "| Variable | Type | Provenance |",
        "|---|---|---|",
    ]

    # Helper to shorten URIs for display
    def short(uri: str) -> str:
        for prefix_uri, prefix_name in [
            (str(PROJECT_NS), ""),
            (str(SCI_NS), "sci:"),
        ]:
            if uri.startswith(prefix_uri):
                return prefix_name + uri[len(prefix_uri):]
        return uri

    for node_uri in info["boundary_in"]:
        lines.append(f"| {short(node_uri)} | | |")

    lines.extend([
        "",
        "### Boundary Out (Produces)",
        "",
        "| Variable | Type | Validation |",
        "|---|---|---|",
    ])

    for node_uri in info["boundary_out"]:
        lines.append(f"| {short(node_uri)} | | |")

    lines.extend([
        "",
        "## Data Flow",
        "",
    ])

    for edge in info["edges"]:
        lines.append(f"- {short(edge['subject'])} --[{short(edge['predicate'])}]--> {short(edge['object'])}")

    lines.append("")
    return "\n".join(lines)
```

**Step 4: Run tests**

Run: `cd science-tool && uv run --frozen pytest tests/test_inquiry.py::TestInquiryRender -v`
Expected: PASS

**Step 5: Commit**

```bash
git add templates/inquiry.md science-tool/src/science_tool/graph/store.py science-tool/tests/test_inquiry.py
git commit -m "feat: add inquiry template and document rendering"
```

---

## Task 7: validate.sh section 14 — inquiry checks

**Files:**
- Modify: `scripts/validate.sh`

**Step 1: Add section 14 to validate.sh**

After section 13 (graph validation), add section 14 for inquiry-specific checks. The pattern follows section 13: shell out to `science-tool inquiry validate <slug>` for each inquiry, parse JSON output.

```bash
# ------------------------------------------------------------------
# 14. Inquiry validation
# ------------------------------------------------------------------
if [ -f "knowledge/graph.trig" ] && [ -n "$SCIENCE_TOOL" ]; then
  # Get list of inquiry slugs
  INQUIRY_LIST=$($SCIENCE_TOOL inquiry list --path knowledge/graph.trig --format json 2>/dev/null || echo "[]")
  INQUIRY_COUNT=$(echo "$INQUIRY_LIST" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")

  if [ "$INQUIRY_COUNT" -gt 0 ]; then
    log_section "Inquiry validation ($INQUIRY_COUNT inquiries)"

    INQUIRY_SLUGS=$(echo "$INQUIRY_LIST" | python3 -c "
import sys, json
for inq in json.load(sys.stdin):
    print(inq['slug'])
" 2>/dev/null)

    while IFS= read -r slug; do
      [ -z "$slug" ] && continue
      VALIDATE_OUT=$($SCIENCE_TOOL inquiry validate "$slug" --path knowledge/graph.trig --format json 2>/dev/null)
      if [ $? -ne 0 ]; then
        log_error "14" "Inquiry '$slug' validation command failed"
        continue
      fi

      echo "$VALIDATE_OUT" | python3 -c "
import sys, json
checks = json.load(sys.stdin)
for c in checks:
    status = c.get('status', 'unknown')
    check = c.get('check', '?')
    msg = c.get('message', '')
    if status == 'fail':
        print(f'ERROR|14|{check}: {msg}')
    elif status == 'warn':
        print(f'WARN|14|{check}: {msg}')
" 2>/dev/null | while IFS='|' read -r level section msg; do
        if [ "$level" = "ERROR" ]; then
          log_error "$section" "$msg"
        elif [ "$level" = "WARN" ]; then
          log_warn "$section" "$msg"
        fi
      done
    done <<< "$INQUIRY_SLUGS"
  fi
fi
```

**Step 2: Test manually**

Create a test project with an inquiry and run `bash validate.sh --verbose` to confirm section 14 runs correctly.

**Step 3: Commit**

```bash
git add scripts/validate.sh
git commit -m "feat: add inquiry validation checks to validate.sh (section 14)"
```

---

## Task 8: Knowledge-graph skill — add inquiry entity types and predicates

**Files:**
- Modify: `.claude-plugin/skills/knowledge-graph/SKILL.md`

**Step 1: Add inquiry section to the knowledge-graph skill**

After the existing entity type table, add:

```markdown
## Inquiry Entities

Inquiries are named subgraphs that represent self-contained investigations. They connect
data/observations to hypotheses through variables, assumptions, and transformations.

### Inquiry-Specific Entity Types

| Entity | Type | When to use |
|--------|------|-------------|
| Inquiry | `sci:Inquiry` | Named subgraph container for an investigation |
| Variable | `sci:Variable` | A quantity in the model (observed, latent, or computed) |
| Transformation | `sci:Transformation` | A computational/analytical step in the pipeline |
| Assumption | `sci:Assumption` | An explicit modeling assumption with provenance |
| Unknown | `sci:Unknown` | Placeholder for unidentified factors (sketch only) |
| ValidationCheck | `sci:ValidationCheck` | A criterion for verifying a step or result |

### Inquiry-Specific Predicates

| Predicate | Description | Layer |
|-----------|-------------|-------|
| `sci:target` | Links inquiry to its hypothesis/question | inquiry |
| `sci:boundaryRole` | Assigns BoundaryIn/BoundaryOut within an inquiry | inquiry |
| `sci:inquiryStatus` | Inquiry lifecycle status | inquiry |
| `sci:feedsInto` | Data/information flow (A provides input to B) | inquiry |
| `sci:assumes` | Dependency on an assumption | inquiry |
| `sci:produces` | Transformation yields output | inquiry |
| `sci:validatedBy` | Step validated by criterion | inquiry |

### Boundary Roles

- `sci:BoundaryIn` — Given/observable input (datasets, measurements, known facts)
- `sci:BoundaryOut` — Produced output (test results, predictions, artifacts)
- Interior nodes have no boundary role — they are latent variables, transformations, assumptions

### Parameter Provenance Predicates

For annotating parameters with their evidence source:

| Predicate | Description |
|-----------|-------------|
| `sci:paramValue` | The parameter value |
| `sci:paramSource` | Source type: `literature`, `empirical`, `design_decision`, `convention`, `data_derived` |
| `sci:paramRef` | BibTeX key or doc path reference |
| `sci:paramNote` | Rationale note |
```

**Step 2: Commit**

```bash
git add .claude-plugin/skills/knowledge-graph/SKILL.md
git commit -m "docs: add inquiry entity types and predicates to knowledge-graph skill"
```

---

## Task 9: Command — `/science:sketch-model`

**Files:**
- Create: `commands/sketch-model.md`

**Step 1: Write the command file**

```markdown
---
description: Sketch a research model interactively. Captures variables, relationships, data sources, and unknowns as an inquiry subgraph. Use when the user wants to explore what variables matter, how things connect, or how to approach a question computationally. Also use when the user says "sketch", "what variables", "how would I model", or "what affects what".
---

# Sketch a Research Model

> **Prerequisite:** Load the `knowledge-graph` skill for ontology reference before starting.

## Overview

This command helps the user sketch the shape of a research investigation: what variables matter, how they connect, what data is available, and what's unknown. The output is an inquiry subgraph in the knowledge graph — a rough model that can later be formalized with `/science:specify-model`.

Missing provenance, loose edge types, and `sci:Unknown` nodes are all fine at this stage. The goal is to capture the structure of the user's thinking, not to be precise.

## Tool invocation

All `science-tool` commands below use this pattern:

```bash
uv run --with ${CLAUDE_PLUGIN_ROOT}/science-tool science-tool <command>
```

For brevity, the examples below write just `science-tool <command>` — **always expand to the full `uv run --with ...` form when executing.**

## Rules

- **MUST** initialize the graph if it doesn't exist (`science-tool graph init`)
- **MUST** create the inquiry before adding nodes/edges (`science-tool inquiry init`)
- **MUST** add all entities to the knowledge graph (`graph add concept`) AND to the inquiry (`inquiry add-node`)
- **MUST** use `sci:feedsInto` for data flow edges, NOT `skos:related`
- **MAY** use `skos:related` for uncertain/associative relationships
- **MAY** use `sci:Unknown` type for unidentified variables
- **MUST NOT** require provenance — this is a sketch, not a specification
- **SHOULD** ask clarifying questions adaptively, not as a rigid questionnaire

## Workflow

### Step 1: Gather context

Read the following project files (skip any that don't exist):
- `specs/research-question.md` — project scope
- `specs/hypotheses/` — existing hypotheses
- `doc/08-open-questions.md` — open questions
- `knowledge/graph.trig` — existing graph (if any)
- `doc/inquiries/` — existing inquiries (if any)

If no graph exists, initialize one:
```bash
science-tool graph init
```

### Step 2: Interactive conversation

Have a natural, adaptive conversation. These questions are guidelines — skip ahead if the user provides enough context upfront.

1. **Target:** "What are you trying to test or answer?"
   - Identify the target hypothesis or question
   - If it doesn't exist yet, offer to create it with `/science:add-hypothesis`

2. **Variables:** "What variables or quantities matter here?"
   - What can you directly observe or measure?
   - What's latent — things you think matter but can't directly see?
   - What's computed — derived from other variables?

3. **Relationships:** "What do you think affects what?"
   - Don't worry about precision — rough arrows are fine
   - "Does A cause B, or are they just correlated? Don't know? That's fine too."

4. **Data:** "What data do you have or could get?"
   - Existing datasets, databases, measurements
   - What's available vs. what would need to be generated?

5. **Unknowns:** "What are you unsure about?"
   - Create `sci:Unknown` nodes for gaps
   - "Is there something that might affect the outcome but you're not sure what?"

### Step 3: Build the inquiry subgraph

From the conversation:

1. **Create the inquiry:**
```bash
science-tool inquiry init "<slug>" \
  --label "<descriptive label>" \
  --target "<hypothesis:hNN or question:qNN>" \
  --description "<one sentence summary>"
```

2. **Add entities to the knowledge graph** (if they don't already exist):
```bash
science-tool graph add concept "<variable name>" --type sci:Variable
science-tool graph add concept "<data source>" --type sci:Variable
science-tool graph add concept "<unknown factor>" --type sci:Unknown
```

3. **Add nodes to the inquiry with boundary roles:**
```bash
science-tool inquiry add-node "<slug>" "concept:<entity>" --role BoundaryIn
science-tool inquiry add-node "<slug>" "concept:<entity>" --role BoundaryOut
```

4. **Add edges within the inquiry:**
```bash
science-tool inquiry add-edge "<slug>" "concept:<from>" "sci:feedsInto" "concept:<to>"
```

5. **Add assumptions** (if the user mentions them):
```bash
science-tool inquiry add-edge "<slug>" "concept:<node>" "sci:assumes" "concept:<assumption>"
```

### Step 4: Visualize and summarize

```bash
science-tool inquiry show "<slug>" --format table
science-tool inquiry validate "<slug>" --format json
```

Generate the inquiry document:
- Save to `doc/inquiries/<slug>.md`
- Show the user the boundary nodes, data flow, and any unknowns
- Note which unknowns will need resolution in the specify step

### Step 5: Finalize

```bash
science-tool graph stamp-revision
```

Suggest next steps:
1. If the sketch looks good: `/science:specify-model <slug>` to add rigor
2. If more background needed: `/science:research-topic` or `/science:search-literature`
3. If hypotheses need work: `/science:add-hypothesis`

## Important Notes

- **Don't over-formalize.** A sketch with 5-10 nodes and rough edges is better than trying to capture everything. The specify step adds precision.
- **Unknown nodes are valuable.** They make gaps explicit rather than leaving them implicit in prose.
- **Multiple sketches are fine.** A project can have several inquiry sketches exploring different approaches to the same question.
- **Reuse existing entities.** Check the graph for existing concepts before creating duplicates. Use `graph neighborhood <term>` to see what's already there.
```

**Step 2: Commit**

```bash
git add commands/sketch-model.md
git commit -m "feat: add /science:sketch-model command"
```

---

## Task 10: Command — `/science:specify-model`

**Files:**
- Create: `commands/specify-model.md`

**Step 1: Write the command file**

```markdown
---
description: Formalize a research model with full evidence provenance. Every variable gets a type, every edge gets evidence, every parameter gets a source. Use when the user wants to make a sketch rigorous, add provenance, resolve unknowns, or formalize assumptions. Also use when the user says "specify", "formalize", "add evidence", "make rigorous", or "resolve unknowns".
---

# Specify a Research Model

> **Prerequisite:** Load the `knowledge-graph` skill for ontology reference before starting.

## Overview

This command takes an inquiry from sketch to specified status. Every variable gets a formal type, every edge gets evidence, every parameter gets provenance metadata (`AnnotatedParam`-style), and all `sci:Unknown` nodes are resolved or justified.

Can start from an existing sketch (preferred) or from scratch.

## Tool invocation

All `science-tool` commands below use this pattern:

```bash
uv run --with ${CLAUDE_PLUGIN_ROOT}/science-tool science-tool <command>
```

For brevity, the examples below write just `science-tool <command>` — **always expand to the full `uv run --with ...` form when executing.**

## Rules

- **MUST** read the existing inquiry before modifying it
- **MUST** assign formal types to all variables (not just `sci:Concept`)
- **MUST** replace `skos:related` edges with typed predicates where the relationship is known
- **MUST** add `--source` provenance to all assumptions and claims
- **MUST** resolve or justify all `sci:Unknown` nodes
- **MUST** run `inquiry validate` after specifying — all checks must pass
- **MUST** add `AnnotatedParam` metadata for all non-trivial parameter values
- **SHOULD** identify confounders for each causal/directional edge
- **SHOULD** justify edge direction (why A→B not B→A?)

## Workflow

### Step 1: Load and assess the inquiry

If `$ARGUMENTS` contains a slug:
```bash
science-tool inquiry show "<slug>" --format table
science-tool inquiry validate "<slug>" --format json
```

Identify gaps:
- Variables without formal types
- Edges using `skos:related` that should be more specific
- Nodes without provenance
- `sci:Unknown` nodes needing resolution
- Missing confounders
- Parameters without `AnnotatedParam` metadata

If no slug provided, ask which inquiry to specify, or offer to create one from scratch (run sketch inline).

### Step 2: Specify variables

For each variable in the inquiry, work through interactively:

1. **Type:** "What kind of thing is this?" → assign `biolink:*`, `sci:Variable`, `sci:Transformation`, etc.
```bash
science-tool graph add concept "<name>" --type <CURIE> --definition "<definition>"
```

2. **Observability:** Is this observed, latent, or computed?
```bash
science-tool graph add edge "concept:<name>" "sci:observability" "observed"
```

3. **Provenance:** Where does this come from?
```bash
# Add source to concept if not already present
science-tool graph add concept "<name>" --source "<ref>"
```

### Step 3: Specify edges

For each edge in the inquiry:

1. **Type:** Replace loose edges with typed predicates
   - `sci:feedsInto` → data/information flow (keep if correct)
   - `scic:causes` → causal claim (requires evidence)
   - `sci:assumes` → dependency on assumption
   - `sci:produces` → transformation output

2. **Evidence:** Create a claim justifying each non-obvious edge
```bash
science-tool graph add claim "X feeds into Y because..." --source "paper:doi_..." --confidence 0.8
science-tool graph add edge "claim:..." "cito:supports" "concept:<edge-subject>"
```

3. **Direction justification:** For causal/directional edges, note why A→B not B→A

4. **Confounders:** "What else could explain this relationship?"
```bash
science-tool graph add concept "<confounder>" --type sci:Variable
science-tool graph add edge "concept:<confounder>" "scic:confounds" "concept:<edge-subject>"
```

### Step 4: Specify parameters

For each parameter-bearing node, add `AnnotatedParam` metadata:

```bash
# Example: pooling method
science-tool graph add edge "concept:pooling_method" "sci:paramValue" "mean"
science-tool graph add edge "concept:pooling_method" "sci:paramSource" "design_decision"
science-tool graph add edge "concept:pooling_method" "sci:paramRef" "doc/04-approach.md"
science-tool graph add edge "concept:pooling_method" "sci:paramNote" "Captures SP-relevant info"
```

Source types: `literature`, `empirical`, `design_decision`, `convention`, `data_derived`

### Step 5: Resolve unknowns

For each `sci:Unknown` node:
- **Resolve:** Replace with a real entity (new concept with proper type and provenance)
- **Justify:** Document why it remains unknown and what would resolve it
- **Remove:** If the unknown is no longer relevant

### Step 6: Validate and finalize

```bash
science-tool inquiry validate "<slug>" --format json
```

All checks must pass for a specified inquiry:
- boundary_reachability: pass
- no_cycles: pass
- unknown_resolution: pass (no unresolved unknowns)
- provenance_completeness: pass (all assumptions sourced)
- target_exists: pass

Update the inquiry document:
```bash
# Regenerate doc/inquiries/<slug>.md from graph
```

```bash
science-tool graph stamp-revision
```

### Step 7: Suggest next steps

1. `/science:plan-pipeline <slug>` — generate computational implementation plan
2. `/science:review-pipeline <slug>` — get a critical review before implementation
3. `/science:discuss` with `focus_ref: inquiry:<slug>` — structured discussion of the model

## Important Notes

- **Evidence-driven.** Every edge should be justifiable. If you can't justify an edge, it might not belong in the model.
- **Parameters are first-class.** Every number in the eventual pipeline should trace back to a source: a paper, a dataset, a design decision, or a convention. This is the `AnnotatedParam` principle.
- **Confounders matter.** The specify step is where you catch missing variables. If A→B seems obvious, ask: "What else could explain this?"
- **Iterate with the user.** Don't specify everything silently — discuss non-obvious decisions. The user should understand and agree with every edge.
```

**Step 2: Commit**

```bash
git add commands/specify-model.md
git commit -m "feat: add /science:specify-model command"
```

---

## Task 11: Command — `/science:plan-pipeline`

**Files:**
- Create: `commands/plan-pipeline.md`

**Step 1: Write the command file**

```markdown
---
description: Generate a computational implementation plan from a specified inquiry. Translates the evidence-driven model into concrete pipeline steps with tools, configs, tests, and validation criteria. Use when the user wants to implement a model, build a pipeline, operationalize an inquiry, or make something computational. Also use when the user says "plan pipeline", "implement this", "build the pipeline", or "make this executable".
---

# Plan Pipeline from Inquiry

> **Prerequisites:**
> - Load the `knowledge-graph` skill for ontology reference
> - Load the `research-methodology` skill for evidence standards
> - Read `skills/pipelines/snakemake.md` if Snakemake orchestration is appropriate (optional)

## Overview

This command takes a specified inquiry and generates a concrete computational implementation plan. It adds `sci:Transformation` nodes to the inquiry subgraph, attaches tools and parameters, creates validation criteria, and writes an implementation plan document.

The plan bridges the evidence-driven model and code. Every transformation traces back through the inquiry to the data and assumptions that justify it.

## Tool invocation

All `science-tool` commands below use this pattern:

```bash
uv run --with ${CLAUDE_PLUGIN_ROOT}/science-tool science-tool <command>
```

## Rules

- **MUST** start from a specified inquiry (status=`specified`); warn if sketch
- **MUST** add `sci:Transformation` nodes for each computational step
- **MUST** connect transformations with `sci:feedsInto` edges
- **MUST** attach `sci:validatedBy` checks to each transformation
- **MUST** include `AnnotatedParam` metadata for all pipeline parameters
- **MUST** write the plan to `doc/plans/YYYY-MM-DD-<slug>-pipeline-plan.md`
- **SHOULD** reference tool-specific skills where applicable
- **SHOULD** suggest a pilot/phased approach for complex pipelines
- **MUST NOT** embed tool-specific logic (Snakemake rules, etc.) — reference skills instead

## Workflow

### Step 1: Load and verify the inquiry

```bash
science-tool inquiry show "<slug>" --format table
science-tool inquiry validate "<slug>" --format json
```

Verify status is `specified`. If it's `sketch`, warn the user and suggest `/science:specify-model` first.

### Step 2: Identify computational requirements

Walk the inquiry subgraph and identify:

**Data acquisition steps** — for each `BoundaryIn` node:
- How is this data obtained? (Download, query, extract from reference)
- What format is it in? What format does it need to be in?
- Are there preprocessing steps?

**Transformation steps** — for each interior edge:
- What computation does this edge imply?
- What tool/library performs it?
- What are the input/output formats?
- What parameters does it need?

**Output steps** — for each `BoundaryOut` node:
- What format should the output be in?
- How is it validated?
- What does "success" look like?

### Step 3: Add computational nodes to the inquiry

For each identified step:

```bash
# Add transformation to knowledge graph and inquiry
science-tool graph add concept "<step name>" --type sci:Transformation \
  --note "<what this step does>" \
  --property tool "<tool name>"

science-tool inquiry add-node "<slug>" "concept:<step>" --role interior

# Connect in the data flow
science-tool inquiry add-edge "<slug>" "concept:<input>" "sci:feedsInto" "concept:<step>"
science-tool inquiry add-edge "<slug>" "concept:<step>" "sci:produces" "concept:<output>"

# Add validation criterion
science-tool graph add concept "<check name>" --type sci:ValidationCheck \
  --note "<what to check>"
science-tool inquiry add-edge "<slug>" "concept:<step>" "sci:validatedBy" "concept:<check>"

# Add parameter provenance
science-tool graph add edge "concept:<step>" "sci:paramValue" "<value>"
science-tool graph add edge "concept:<step>" "sci:paramSource" "<source_type>"
science-tool graph add edge "concept:<step>" "sci:paramRef" "<reference>"
```

### Step 4: Write the implementation plan

Save to `doc/plans/YYYY-MM-DD-<slug>-pipeline-plan.md` using the standard plan format:

```markdown
# <Inquiry Label> Pipeline Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** <derived from inquiry target and description>

**Architecture:** <derived from transformation graph>

**Tech Stack:** <tools identified in step 3>

**Inquiry:** `<slug>` — see `doc/inquiries/<slug>.md` and knowledge graph

**Reference docs:**
- `doc/inquiries/<slug>.md` — inquiry specification
- <relevant project docs>

---

## Task N: <Transformation step>
...
```

Each task in the plan should:
- Reference the inquiry node it implements
- Include TDD steps (write test, verify fail, implement, verify pass)
- Include exact file paths
- Include commit messages
- Reference parameter provenance from the inquiry

### Step 5: Update inquiry status

Update the inquiry status to `planned`:
```bash
# Update status in graph (manual edit or future CLI support)
```

Regenerate `doc/inquiries/<slug>.md`.

```bash
science-tool graph stamp-revision
```

### Step 6: Suggest next steps

1. `/science:review-pipeline <slug>` — get critical review before implementation
2. Execute the plan using `superpowers:executing-plans`
3. `/science:discuss` — discuss specific aspects of the plan

## Important Notes

- **Plans are tool-agnostic by default.** Reference tool-specific skills (`snakemake.md`, `marimo.md`) rather than embedding their conventions.
- **Pilot first.** For complex pipelines, suggest a pilot phase with reduced scope before the full run.
- **Validation criteria are mandatory.** Every transformation must have a way to verify it worked. This is the computational equivalent of falsifiability.
- **The inquiry is the source of truth.** The plan document is a rendering of the inquiry's computational layer. If the inquiry changes, the plan should be regenerated.
```

**Step 2: Commit**

```bash
git add commands/plan-pipeline.md
git commit -m "feat: add /science:plan-pipeline command"
```

---

## Task 12: Command — `/science:review-pipeline`

**Files:**
- Create: `commands/review-pipeline.md`

**Step 1: Write the command file**

```markdown
---
description: Critically review a pipeline plan against an evidence rubric. Checks evidence coverage, assumption validity, data availability, identifiability, reproducibility, validation criteria, and scope. Use when the user wants to review, audit, or check a pipeline before implementation. Also use when the user says "review pipeline", "check my plan", "audit assumptions", or "is this ready".
---

# Review Pipeline

> **Prerequisites:**
> - Load the `knowledge-graph` skill
> - Load the `research-methodology` skill
> - Read the `discussant` role prompt from `prompts/roles/discussant.md` (if available)

## Overview

This command performs a systematic review of an inquiry and its pipeline plan. It operates as a critical discussant — looking for weaknesses, missing evidence, and unjustified assumptions.

The review is NOT a rubber stamp. It should surface problems the user hasn't considered.

## Tool invocation

All `science-tool` commands below use this pattern:

```bash
uv run --with ${CLAUDE_PLUGIN_ROOT}/science-tool science-tool <command>
```

## Rules

- **MUST** run structural validation first (`inquiry validate`)
- **MUST** evaluate all 7 rubric dimensions
- **MUST** be critical — surface weaknesses, don't just confirm the plan is good
- **MUST** provide specific, actionable recommendations for each issue
- **MUST** save review report to `doc/inquiries/<slug>-review.md`
- **SHOULD** cross-reference claims against existing literature (LLM knowledge + web search)
- **MUST NOT** change the inquiry or plan — only report findings

## Workflow

### Step 1: Load inquiry and plan

```bash
science-tool inquiry show "<slug>" --format table
science-tool inquiry validate "<slug>" --format json
```

Also read:
- `doc/inquiries/<slug>.md` — inquiry document
- `doc/plans/*<slug>*` — implementation plan (if exists)
- `specs/scope-boundaries.md` — project scope

### Step 2: Evaluate each rubric dimension

#### Dimension 1: Evidence Coverage

Check every edge and parameter in the inquiry:
- Does every non-trivial parameter have `sci:paramSource` and `sci:paramRef`?
- Are there `[UNVERIFIED]` markers in the inquiry doc?
- Do any `sci:Unknown` nodes remain?
- Are claim confidence levels reasonable?

**Scoring:** PASS (all params sourced), WARN (some missing refs), FAIL (unsourced causal claims)

#### Dimension 2: Assumption Audit

For each `sci:Assumption` and `scic:causes` edge:
- Is the assumption justified with evidence?
- Could confounders explain the relationship?
- Is the causal direction justified?
- Are there alternative explanations?

**Scoring:** PASS (all justified), WARN (minor gaps), FAIL (unjustified causal claims)

#### Dimension 3: Data Availability

For each `BoundaryIn` node:
- Is the data source specified (URL, database, access method)?
- Is the data actually accessible (public, requires application, restricted)?
- Is the format specified?
- Are there version/date stamps?

**Scoring:** PASS (all accessible), WARN (some unspecified), FAIL (inaccessible sources)

#### Dimension 4: Identifiability

Graph-structural check:
- Is every `BoundaryOut` reachable from `BoundaryIn` via directed edges?
- Are there disconnected components in the inquiry?
- Can the target hypothesis actually be tested given the available data flow?

**Scoring:** PASS (fully connected), FAIL (disconnected or unreachable)

#### Dimension 5: Reproducibility

Check each `sci:Transformation` node:
- Are random seeds specified?
- Are software versions pinned?
- Are environments reproducible (conda, uv, containers)?
- Is the pipeline deterministic (or is non-determinism acknowledged)?

**Scoring:** PASS (fully specified), WARN (partial), FAIL (no reproducibility measures)

#### Dimension 6: Validation Criteria

For each `sci:Transformation`:
- Does it have a `sci:validatedBy` check?
- Is the check specific enough to catch failures?
- Are there intermediate checks, or only final output validation?

**Scoring:** PASS (all steps validated), WARN (gaps), FAIL (no validation)

#### Dimension 7: Scope Check

Compare inquiry boundary nodes against `specs/scope-boundaries.md`:
- Does the inquiry stay within project scope?
- Are there scope-creep risks?
- Is the inquiry achievable with available resources?

**Scoring:** PASS (in scope), WARN (borderline), FAIL (out of scope)

### Step 3: Write review report

Save to `doc/inquiries/<slug>-review.md`:

```markdown
# Pipeline Review: {{label}}

- **Inquiry:** {{slug}}
- **Date:** {{date}}
- **Overall:** {{PASS|WARN|FAIL}}

## Summary

{{2-3 sentence assessment}}

## Rubric Results

| Dimension | Score | Issues |
|---|---|---|
| Evidence coverage | {{score}} | {{brief}} |
| Assumption audit | {{score}} | {{brief}} |
| Data availability | {{score}} | {{brief}} |
| Identifiability | {{score}} | {{brief}} |
| Reproducibility | {{score}} | {{brief}} |
| Validation criteria | {{score}} | {{brief}} |
| Scope check | {{score}} | {{brief}} |

## Detailed Findings

### {{Dimension with issues}}

{{Specific findings with actionable recommendations}}

## Recommendations

1. {{Highest priority action}}
2. {{Next priority}}
...

## Strengths

{{What's done well — acknowledge good work}}
```

### Step 4: Present to user

Show the summary table and top recommendations. Ask if they want to:
1. Address the findings (modify inquiry/plan)
2. Accept the risks and proceed
3. Discuss specific findings in more depth

## Important Notes

- **Be genuinely critical.** The value of this review is in finding problems before implementation. A review that passes everything is probably not thorough enough.
- **Cross-check claims.** Use LLM knowledge and web search to verify factual claims in the inquiry, especially around parameter values and data source availability.
- **Look for circular reasoning.** If A justifies B and B justifies A, flag it.
- **Consider failure modes.** For each transformation: what happens if it fails? Is there a fallback? Is the failure detectable?
```

**Step 2: Commit**

```bash
git add commands/review-pipeline.md
git commit -m "feat: add /science:review-pipeline command"
```

---

## Task 13: Update docs/plan.md — Phase 4 deliverables

**Files:**
- Modify: `docs/plan.md`

**Step 1: Update Phase 4 deliverables**

In the Phase 4 section, add the inquiry workflow deliverables:

```markdown
### Phase 4: Modeling + Operationalization (Stage B/C Optional Paths)

Support projects that need explicit models, datasets, or computational workflows.

**Deliverables (4a — Inquiry Workflow):**
- [ ] Ontology extensions: `sci:Inquiry`, `sci:Variable`, `sci:Transformation`, `sci:Assumption`, `sci:Unknown`, `sci:ValidationCheck` types + 12 new predicates
- [ ] `GraphStore` inquiry methods: `add_inquiry`, `set_boundary_role`, `add_inquiry_edge`, `add_assumption`, `add_transformation`, `set_param_metadata`, `get_inquiry`, `list_inquiries`, `validate_inquiry`, `render_inquiry_doc`
- [ ] CLI: `science-tool inquiry` command group (init, add-node, add-edge, list, show, validate)
- [ ] `validate.sh` section 14: inquiry validation checks
- [ ] Knowledge-graph skill updated with inquiry entity types and predicates
- [ ] `/science:sketch-model` command
- [ ] `/science:specify-model` command
- [ ] `/science:plan-pipeline` command
- [ ] `/science:review-pipeline` command
- [ ] `templates/inquiry.md` template
- [ ] Inquiry document rendering from graph
```

**Step 2: Commit**

```bash
git add docs/plan.md
git commit -m "docs: add inquiry workflow deliverables to Phase 4 plan"
```

---

## Task 14: Integration test — end-to-end inquiry workflow

**Files:**
- Create: `science-tool/tests/test_inquiry_e2e.py`

**Step 1: Write end-to-end test**

```python
# science-tool/tests/test_inquiry_e2e.py
"""End-to-end test for the inquiry workflow."""

from pathlib import Path

from click.testing import CliRunner

from science_tool.cli import cli


def test_full_inquiry_lifecycle(tmp_path: Path) -> None:
    """Test sketch → specify → validate lifecycle via CLI."""
    runner = CliRunner()
    graph_path = str(tmp_path / "knowledge" / "graph.trig")
    (tmp_path / "knowledge").mkdir()

    # 1. Init graph
    result = runner.invoke(cli, ["graph", "init", "--path", graph_path])
    assert result.exit_code == 0

    # 2. Add a hypothesis as target
    result = runner.invoke(cli, [
        "graph", "add", "hypothesis", "H01",
        "--text", "SP embeddings occupy distinct geometric regions",
        "--source", "paper:doi_test",
        "--path", graph_path,
    ])
    assert result.exit_code == 0

    # 3. Create inquiry (sketch)
    result = runner.invoke(cli, [
        "inquiry", "init", "sp-geometry",
        "--label", "Signal peptide embedding geometry",
        "--target", "hypothesis:h01",
        "--description", "Test whether SP embeddings form distinct clusters",
        "--path", graph_path,
    ])
    assert result.exit_code == 0

    # 4. Add concepts
    for concept in ["uniprot_sps", "esm2_model", "sp_embeddings", "distance_matrix", "t1_comparison"]:
        result = runner.invoke(cli, ["graph", "add", "concept", concept, "--path", graph_path])
        assert result.exit_code == 0, f"Failed to add {concept}: {result.output}"

    # 5. Set boundary roles
    for entity, role in [
        ("concept:uniprot_sps", "BoundaryIn"),
        ("concept:esm2_model", "BoundaryIn"),
        ("concept:distance_matrix", "BoundaryOut"),
        ("concept:t1_comparison", "BoundaryOut"),
    ]:
        result = runner.invoke(cli, [
            "inquiry", "add-node", "sp-geometry", entity, "--role", role, "--path", graph_path,
        ])
        assert result.exit_code == 0, f"Failed boundary role {entity}: {result.output}"

    # 6. Add data flow edges
    edges = [
        ("concept:uniprot_sps", "sci:feedsInto", "concept:sp_embeddings"),
        ("concept:esm2_model", "sci:feedsInto", "concept:sp_embeddings"),
        ("concept:sp_embeddings", "sci:feedsInto", "concept:distance_matrix"),
        ("concept:sp_embeddings", "sci:feedsInto", "concept:t1_comparison"),
    ]
    for s, p, o in edges:
        result = runner.invoke(cli, [
            "inquiry", "add-edge", "sp-geometry", s, p, o, "--path", graph_path,
        ])
        assert result.exit_code == 0, f"Failed edge {s}->{o}: {result.output}"

    # 7. List inquiries
    result = runner.invoke(cli, ["inquiry", "list", "--path", graph_path, "--format", "json"])
    assert result.exit_code == 0
    assert "sp_geometry" in result.output

    # 8. Show inquiry
    result = runner.invoke(cli, ["inquiry", "show", "sp-geometry", "--path", graph_path, "--format", "json"])
    assert result.exit_code == 0
    assert "Signal peptide" in result.output

    # 9. Validate — should pass (sketch allows loose edges)
    result = runner.invoke(cli, [
        "inquiry", "validate", "sp-geometry", "--path", graph_path, "--format", "json",
    ])
    assert result.exit_code == 0
    assert "fail" not in result.output.lower() or "pass" in result.output.lower()
```

**Step 2: Run end-to-end test**

Run: `cd science-tool && uv run --frozen pytest tests/test_inquiry_e2e.py -v`
Expected: PASS

**Step 3: Run full test suite**

Run: `cd science-tool && uv run --frozen pytest -v`
Expected: All tests pass

**Step 4: Commit**

```bash
git add science-tool/tests/test_inquiry_e2e.py
git commit -m "test: add end-to-end inquiry workflow test"
```

---

## Summary

| Task | What | Tests | Files |
|---|---|---|---|
| 1 | Ontology extensions (predicates, types) | 4 | store.py, test_inquiry.py |
| 2 | GraphStore: init, boundary, edges, assumptions | 10 | store.py, test_inquiry.py |
| 3 | GraphStore: transformations, params, queries | 7 | store.py, test_inquiry.py |
| 4 | GraphStore: inquiry validation | 5 | store.py, test_inquiry.py |
| 5 | CLI subcommands | 8 | cli.py, test_inquiry_cli.py |
| 6 | Template + doc rendering | 1 | inquiry.md, store.py, test_inquiry.py |
| 7 | validate.sh section 14 | manual | validate.sh |
| 8 | Knowledge-graph skill update | — | SKILL.md |
| 9 | `/science:sketch-model` command | — | sketch-model.md |
| 10 | `/science:specify-model` command | — | specify-model.md |
| 11 | `/science:plan-pipeline` command | — | plan-pipeline.md |
| 12 | `/science:review-pipeline` command | — | review-pipeline.md |
| 13 | plan.md Phase 4 update | — | plan.md |
| 14 | End-to-end integration test | 1 | test_inquiry_e2e.py |

**Total: 14 tasks, ~36 tests, 14 commits**

Estimated new code: ~400 lines in `store.py`, ~200 lines in `cli.py`, ~100 lines in `validate.sh`, 4 command files (~600 lines total), 1 template, skill updates.

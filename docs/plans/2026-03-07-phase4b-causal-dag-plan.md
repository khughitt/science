# Phase 4b: Causal DAG Inquiry — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add causal modeling as a typed inquiry, with ChiRho/pgmpy export, causal-specific validation, and two new slash commands (`build-dag`, `critique-approach`).

**Architecture:** Causal DAGs are typed inquiries (`sci:inquiryType "causal"`). Causal edges (`scic:causes`, `scic:confounds`) live in `graph/causal`. Export commands project an inquiry's variables + their causal edges into runnable pgmpy/ChiRho scaffold code. Two new predicates (`sci:treatment`, `sci:outcome`) mark the estimand within a causal inquiry.

**Tech Stack:** Python 3.13, rdflib, click, pgmpy (optional `[causal]`), chirho/pyro-ppl (optional `[causal]`), pytest

**Design doc:** `docs/plans/2026-03-07-phase4b-causal-dag-design.md`

**CLI prefix:** All commands use `uv run --frozen science-tool ...` from `science-tool/` directory.

**Test runner:** `cd science-tool && uv run --frozen pytest tests/<file>::<test> -v`

---

### Task 1: Add `--type` flag to `inquiry init` + ontology extensions

**Files:**
- Modify: `science-tool/src/science_tool/graph/store.py:258-289` (add_inquiry function)
- Modify: `science-tool/src/science_tool/graph/store.py:1068-1081` (PREDICATE_REGISTRY)
- Modify: `science-tool/src/science_tool/cli.py:524-543` (inquiry_init command)
- Test: `science-tool/tests/test_causal.py` (new file)

**Step 1: Write the failing tests**

Create `science-tool/tests/test_causal.py`:

```python
"""Tests for causal DAG inquiry type."""

from pathlib import Path

import pytest
from rdflib import Literal, URIRef

from science_tool.graph.store import (
    INITIAL_GRAPH_TEMPLATE,
    PREDICATE_REGISTRY,
    PROJECT_NS,
    SCI_NS,
    _graph_uri,
    _load_dataset,
    add_concept,
    add_hypothesis,
    add_inquiry,
    get_inquiry,
)


@pytest.fixture
def graph_path(tmp_path: Path) -> Path:
    """Fresh graph file for testing."""
    gp = tmp_path / "knowledge" / "graph.trig"
    gp.parent.mkdir(parents=True)
    gp.write_text(INITIAL_GRAPH_TEMPLATE, encoding="utf-8")
    return gp


class TestInquiryType:
    def test_add_inquiry_with_type_causal(self, graph_path: Path) -> None:
        """Inquiry init with --type causal stores sci:inquiryType."""
        add_concept(graph_path, "Outcome", entity_type="sci:Variable")
        add_hypothesis(graph_path, "test hyp", source="paper:doi_test")
        add_inquiry(
            graph_path, "test-dag", "Test DAG", "hypothesis:test_hyp",
            inquiry_type="causal",
        )
        info = get_inquiry(graph_path, "test-dag")
        assert info["inquiry_type"] == "causal"

    def test_add_inquiry_default_type_general(self, graph_path: Path) -> None:
        """Inquiry without --type defaults to 'general'."""
        add_concept(graph_path, "Outcome", entity_type="sci:Variable")
        add_hypothesis(graph_path, "test hyp", source="paper:doi_test")
        add_inquiry(
            graph_path, "test-general", "Test General", "hypothesis:test_hyp",
        )
        info = get_inquiry(graph_path, "test-general")
        assert info["inquiry_type"] == "general"

    def test_invalid_inquiry_type_rejected(self, graph_path: Path) -> None:
        """Invalid inquiry type raises ValueError."""
        add_hypothesis(graph_path, "test hyp", source="paper:doi_test")
        with pytest.raises(ValueError, match="Invalid inquiry type"):
            add_inquiry(
                graph_path, "bad", "Bad", "hypothesis:test_hyp",
                inquiry_type="invalid",
            )

    def test_causal_predicates_registered(self) -> None:
        """New causal predicates in registry."""
        pred_names = [p["predicate"] for p in PREDICATE_REGISTRY]
        assert "sci:inquiryType" in pred_names
        assert "sci:treatment" in pred_names
        assert "sci:outcome" in pred_names
```

**Step 2: Run tests to verify they fail**

Run: `cd science-tool && uv run --frozen pytest tests/test_causal.py -v`
Expected: FAIL — `add_inquiry()` doesn't accept `inquiry_type` parameter

**Step 3: Implement**

In `store.py`, modify `add_inquiry` signature to accept `inquiry_type: str = "general"`:

```python
VALID_INQUIRY_TYPES = ("general", "causal")

def add_inquiry(
    graph_path: Path,
    slug: str,
    label: str,
    target: str,
    description: str = "",
    status: str = "sketch",
    inquiry_type: str = "general",
) -> URIRef:
    """Create a new inquiry named graph with metadata triples."""
    if inquiry_type not in VALID_INQUIRY_TYPES:
        raise ValueError(f"Invalid inquiry type '{inquiry_type}'. Must be one of: {', '.join(VALID_INQUIRY_TYPES)}")

    safe_slug = _slug(slug)
    inquiry_uri = URIRef(PROJECT_NS[f"inquiry/{safe_slug}"])

    dataset = _load_dataset(graph_path)
    inquiry_graph = dataset.graph(inquiry_uri)

    if (inquiry_uri, RDF.type, SCI_NS.Inquiry) in inquiry_graph:
        raise ValueError(f"Inquiry 'inquiry/{safe_slug}' already exists")

    inquiry_graph.add((inquiry_uri, RDF.type, SCI_NS.Inquiry))
    inquiry_graph.add((inquiry_uri, SKOS.prefLabel, Literal(label)))
    inquiry_graph.add((inquiry_uri, SCI_NS.inquiryStatus, Literal(status)))
    inquiry_graph.add((inquiry_uri, SCI_NS.target, _resolve_term(target)))
    inquiry_graph.add((inquiry_uri, SCI_NS.inquiryType, Literal(inquiry_type)))

    created = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    inquiry_graph.add((inquiry_uri, DCTERMS_NS.created, Literal(created)))

    if description:
        inquiry_graph.add((inquiry_uri, SKOS.note, Literal(description)))

    _save_dataset(dataset, graph_path)
    return inquiry_uri
```

In `get_inquiry`, add `inquiry_type` to the returned dict. Find the line that reads `inquiryStatus` and add below it:

```python
inquiry_type = str(next(inquiry_graph.objects(inquiry_uri, SCI_NS.inquiryType), "general"))
```

And include `"inquiry_type": inquiry_type` in the returned dict.

Add to `PREDICATE_REGISTRY`:

```python
{"predicate": "sci:inquiryType", "description": "Inquiry type (general, causal)", "layer": "inquiry"},
{"predicate": "sci:treatment", "description": "Treatment/intervention variable in causal inquiry", "layer": "inquiry"},
{"predicate": "sci:outcome", "description": "Outcome variable in causal inquiry", "layer": "inquiry"},
```

In `cli.py`, update `inquiry_init`:

```python
@inquiry.command("init")
@click.argument("slug")
@click.option("--label", required=True)
@click.option("--target", required=True, help="Target hypothesis or question (e.g. hypothesis:h01)")
@click.option("--description", default="")
@click.option("--type", "inquiry_type", default="general", type=click.Choice(["general", "causal"]), show_default=True)
@click.option(
    "--status",
    default="sketch",
    type=click.Choice(["sketch", "specified", "planned", "in-progress", "complete"]),
)
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def inquiry_init(slug: str, label: str, target: str, description: str, inquiry_type: str, status: str, graph_path: Path) -> None:
    """Create a new inquiry subgraph."""
    try:
        uri = add_inquiry(graph_path, slug, label, target, description, status, inquiry_type=inquiry_type)
        click.echo(f"Created inquiry: {shorten_uri(str(uri))}")
    except ValueError as e:
        raise click.ClickException(str(e))
```

**Step 4: Run tests to verify they pass**

Run: `cd science-tool && uv run --frozen pytest tests/test_causal.py -v`
Expected: PASS (4 tests)

Also run existing tests to verify no regressions:
Run: `cd science-tool && uv run --frozen pytest tests/ -v`
Expected: All 116+ tests PASS

**Step 5: Commit**

```bash
cd science-tool && git add tests/test_causal.py src/science_tool/graph/store.py src/science_tool/cli.py
git commit -m "feat: add inquiry type system (general, causal) with --type flag on inquiry init"
```

---

### Task 2: Add `sci:treatment` and `sci:outcome` store methods

**Files:**
- Modify: `science-tool/src/science_tool/graph/store.py` (new function)
- Modify: `science-tool/src/science_tool/cli.py` (new subcommand)
- Test: `science-tool/tests/test_causal.py`

**Step 1: Write the failing tests**

Add to `test_causal.py`:

```python
from science_tool.graph.store import set_treatment_outcome


class TestTreatmentOutcome:
    def test_set_treatment_outcome(self, graph_path: Path) -> None:
        """Setting treatment and outcome stores predicates in inquiry graph."""
        add_concept(graph_path, "Drug", entity_type="sci:Variable")
        add_concept(graph_path, "Recovery", entity_type="sci:Variable")
        add_hypothesis(graph_path, "test hyp", source="paper:doi_test")
        add_inquiry(
            graph_path, "drug-effect", "Drug Effect", "hypothesis:test_hyp",
            inquiry_type="causal",
        )
        set_treatment_outcome(graph_path, "drug-effect", treatment="concept/drug", outcome="concept/recovery")
        info = get_inquiry(graph_path, "drug-effect")
        assert info["treatment"] == str(PROJECT_NS["concept/drug"])
        assert info["outcome"] == str(PROJECT_NS["concept/recovery"])

    def test_set_treatment_outcome_rejects_non_causal(self, graph_path: Path) -> None:
        """Setting treatment/outcome on a general inquiry raises error."""
        add_hypothesis(graph_path, "test hyp", source="paper:doi_test")
        add_inquiry(graph_path, "gen", "General", "hypothesis:test_hyp")
        with pytest.raises(ValueError, match="only supported for causal"):
            set_treatment_outcome(graph_path, "gen", treatment="concept/x", outcome="concept/y")
```

**Step 2: Run tests to verify they fail**

Run: `cd science-tool && uv run --frozen pytest tests/test_causal.py::TestTreatmentOutcome -v`
Expected: FAIL — `set_treatment_outcome` does not exist

**Step 3: Implement**

Add to `store.py`:

```python
def set_treatment_outcome(
    graph_path: Path,
    inquiry_slug: str,
    treatment: str,
    outcome: str,
) -> None:
    """Set treatment and outcome variables for a causal inquiry."""
    safe_slug = _slug(inquiry_slug)
    inquiry_uri = URIRef(PROJECT_NS[f"inquiry/{safe_slug}"])

    dataset = _load_dataset(graph_path)
    inquiry_graph = dataset.graph(inquiry_uri)

    if (inquiry_uri, RDF.type, SCI_NS.Inquiry) not in inquiry_graph:
        raise ValueError(f"Inquiry 'inquiry/{safe_slug}' does not exist")

    inquiry_type = str(next(inquiry_graph.objects(inquiry_uri, SCI_NS.inquiryType), "general"))
    if inquiry_type != "causal":
        raise ValueError(f"Treatment/outcome only supported for causal inquiries (got '{inquiry_type}')")

    treatment_uri = _resolve_term(treatment)
    outcome_uri = _resolve_term(outcome)

    # Remove any existing treatment/outcome
    inquiry_graph.remove((inquiry_uri, SCI_NS.treatment, None))
    inquiry_graph.remove((inquiry_uri, SCI_NS.outcome, None))

    inquiry_graph.add((inquiry_uri, SCI_NS.treatment, treatment_uri))
    inquiry_graph.add((inquiry_uri, SCI_NS.outcome, outcome_uri))

    _save_dataset(dataset, graph_path)
```

Update `get_inquiry` to include treatment/outcome in the returned dict:

```python
treatment = next(inquiry_graph.objects(inquiry_uri, SCI_NS.treatment), None)
outcome = next(inquiry_graph.objects(inquiry_uri, SCI_NS.outcome), None)
# ... in the return dict:
"treatment": str(treatment) if treatment else None,
"outcome": str(outcome) if outcome else None,
```

Add CLI subcommand in `cli.py` (after `inquiry_init`):

```python
@inquiry.command("set-estimand")
@click.argument("slug")
@click.option("--treatment", required=True, help="Treatment variable (e.g. concept/drug)")
@click.option("--outcome", required=True, help="Outcome variable (e.g. concept/recovery)")
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def inquiry_set_estimand(slug: str, treatment: str, outcome: str, graph_path: Path) -> None:
    """Set treatment and outcome variables for a causal inquiry."""
    try:
        set_treatment_outcome(graph_path, slug, treatment=treatment, outcome=outcome)
        click.echo(f"Set estimand for inquiry/{slug}: treatment={treatment}, outcome={outcome}")
    except ValueError as e:
        raise click.ClickException(str(e))
```

Update `cli.py` imports to include `set_treatment_outcome`.

**Step 4: Run tests to verify they pass**

Run: `cd science-tool && uv run --frozen pytest tests/test_causal.py -v`
Expected: PASS (6 tests)

**Step 5: Commit**

```bash
cd science-tool && git add src/science_tool/graph/store.py src/science_tool/cli.py tests/test_causal.py
git commit -m "feat: add treatment/outcome estimand for causal inquiries"
```

---

### Task 3: Causal-specific validation checks

**Files:**
- Modify: `science-tool/src/science_tool/graph/store.py` (validate_inquiry function, ~line 802)
- Test: `science-tool/tests/test_causal.py`

**Step 1: Write the failing tests**

Add to `test_causal.py`:

```python
from science_tool.graph.store import (
    add_edge,
    set_boundary_role,
    set_treatment_outcome,
    validate_inquiry,
)


class TestCausalValidation:
    def _setup_causal_inquiry(self, graph_path: Path) -> str:
        """Helper: create a causal inquiry with variables and edges."""
        add_concept(graph_path, "X", entity_type="sci:Variable", status="active",
                    properties={"observability": "observed"})
        add_concept(graph_path, "Y", entity_type="sci:Variable", status="active",
                    properties={"observability": "observed"})
        add_concept(graph_path, "Z", entity_type="sci:Variable", status="active",
                    properties={"observability": "observed"})
        add_hypothesis(graph_path, "test hyp", source="paper:doi_test")
        add_inquiry(
            graph_path, "causal-test", "Causal Test", "hypothesis:test_hyp",
            inquiry_type="causal",
        )
        # Add variables as boundary nodes
        set_boundary_role(graph_path, "causal-test", "concept/x", "BoundaryIn")
        set_boundary_role(graph_path, "causal-test", "concept/y", "BoundaryOut")
        set_boundary_role(graph_path, "causal-test", "concept/z", "BoundaryIn")
        # Set estimand
        set_treatment_outcome(graph_path, "causal-test", treatment="concept/x", outcome="concept/y")
        return "causal-test"

    def test_acyclic_causal_edges_pass(self, graph_path: Path) -> None:
        """Acyclic causal edges pass validation."""
        slug = self._setup_causal_inquiry(graph_path)
        add_edge(graph_path, "concept/x", "scic:causes", "concept/y", graph_layer="graph/causal")
        add_edge(graph_path, "concept/z", "scic:causes", "concept/y", graph_layer="graph/causal")
        results = validate_inquiry(graph_path, slug)
        acyclicity = next(r for r in results if r["check"] == "causal_acyclicity")
        assert acyclicity["status"] == "pass"

    def test_cyclic_causal_edges_fail(self, graph_path: Path) -> None:
        """Cyclic causal edges fail validation."""
        slug = self._setup_causal_inquiry(graph_path)
        add_edge(graph_path, "concept/x", "scic:causes", "concept/y", graph_layer="graph/causal")
        add_edge(graph_path, "concept/y", "scic:causes", "concept/x", graph_layer="graph/causal")
        results = validate_inquiry(graph_path, slug)
        acyclicity = next(r for r in results if r["check"] == "causal_acyclicity")
        assert acyclicity["status"] == "fail"

    def test_general_inquiry_skips_causal_checks(self, graph_path: Path) -> None:
        """General inquiries don't get causal validation checks."""
        add_hypothesis(graph_path, "test hyp", source="paper:doi_test")
        add_inquiry(graph_path, "gen", "General", "hypothesis:test_hyp")
        results = validate_inquiry(graph_path, "gen")
        check_names = [r["check"] for r in results]
        assert "causal_acyclicity" not in check_names
```

**Step 2: Run tests to verify they fail**

Run: `cd science-tool && uv run --frozen pytest tests/test_causal.py::TestCausalValidation -v`
Expected: FAIL — `causal_acyclicity` check not found in results

**Step 3: Implement**

In `validate_inquiry` (around line 960, after the existing checks), add a section gated on inquiry type:

```python
    # === Causal-specific checks (only for type=causal) ===
    inquiry_type = str(next(inquiry_graph.objects(inquiry_uri, SCI_NS.inquiryType), "general"))
    if inquiry_type == "causal":
        causal_graph = dataset.graph(_graph_uri("graph/causal"))

        # Collect inquiry member entities (boundary + flow nodes)
        members = boundary_in | boundary_out | all_flow_nodes

        # Filter causal edges to inquiry members
        causal_edges = [
            (str(s), str(o))
            for s, _, o in causal_graph.triples((None, SCIC_NS.causes, None))
            if s in members and o in members
        ]

        # 6. causal_acyclicity
        if _has_cycle(causal_edges):
            results.append({
                "check": "causal_acyclicity",
                "status": "fail",
                "message": "Cycle detected in scic:causes edges among inquiry variables",
            })
        else:
            results.append({
                "check": "causal_acyclicity",
                "status": "pass",
                "message": "Causal edges are acyclic",
            })
```

**Step 4: Run tests to verify they pass**

Run: `cd science-tool && uv run --frozen pytest tests/test_causal.py -v`
Expected: PASS (9 tests)

Run: `cd science-tool && uv run --frozen pytest tests/ -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
cd science-tool && git add src/science_tool/graph/store.py tests/test_causal.py
git commit -m "feat: add causal-specific validation (acyclicity check for causal inquiries)"
```

---

### Task 4: Add optional `[causal]` dependency group + export module scaffold

**Files:**
- Modify: `science-tool/pyproject.toml:44-49`
- Create: `science-tool/src/science_tool/causal/__init__.py`
- Create: `science-tool/src/science_tool/causal/export_pgmpy.py`
- Create: `science-tool/src/science_tool/causal/export_chirho.py`
- Test: `science-tool/tests/test_causal.py`

**Step 1: Add optional dependency group**

In `science-tool/pyproject.toml`, after the `[project.optional-dependencies]` `distill` section, add:

```toml
causal = [
    "pgmpy>=0.1.25",
    "chirho>=0.2.0",
    "pyro-ppl>=1.9.0",
    "torch>=2.0",
]
```

**Step 2: Create the causal package**

Create `science-tool/src/science_tool/causal/__init__.py`:

```python
"""Causal modeling exports for science-tool."""
```

**Step 3: Write the failing tests for pgmpy export**

Add to `test_causal.py`:

```python
from science_tool.causal.export_pgmpy import export_pgmpy_script


class TestExportPgmpy:
    def _build_simple_dag(self, graph_path: Path) -> str:
        """Helper: build a simple X->Y<-Z causal inquiry."""
        add_concept(graph_path, "X", entity_type="sci:Variable", status="active",
                    properties={"observability": "observed"})
        add_concept(graph_path, "Y", entity_type="sci:Variable", status="active",
                    properties={"observability": "observed"})
        add_concept(graph_path, "Z", entity_type="sci:Variable", status="active",
                    properties={"observability": "observed"})
        add_hypothesis(graph_path, "h1", source="paper:doi_test")
        add_inquiry(graph_path, "xy-dag", "XY DAG", "hypothesis:h1", inquiry_type="causal")
        set_boundary_role(graph_path, "xy-dag", "concept/x", "BoundaryIn")
        set_boundary_role(graph_path, "xy-dag", "concept/y", "BoundaryOut")
        set_boundary_role(graph_path, "xy-dag", "concept/z", "BoundaryIn")
        set_treatment_outcome(graph_path, "xy-dag", treatment="concept/x", outcome="concept/y")
        add_edge(graph_path, "concept/x", "scic:causes", "concept/y", graph_layer="graph/causal")
        add_edge(graph_path, "concept/z", "scic:causes", "concept/y", graph_layer="graph/causal")
        return "xy-dag"

    def test_export_pgmpy_generates_valid_script(self, graph_path: Path) -> None:
        """Export produces a Python script with BayesianNetwork constructor."""
        slug = self._build_simple_dag(graph_path)
        script = export_pgmpy_script(graph_path, slug)
        assert "from pgmpy.models import BayesianNetwork" in script
        assert "BayesianNetwork(" in script
        assert '("x", "y")' in script or '("X", "Y")' in script.upper()
        assert "CausalInference" in script

    def test_export_pgmpy_includes_provenance_comments(self, graph_path: Path) -> None:
        """Export includes provenance comments."""
        slug = self._build_simple_dag(graph_path)
        script = export_pgmpy_script(graph_path, slug)
        assert "# Generated from inquiry:" in script

    def test_export_pgmpy_rejects_non_causal(self, graph_path: Path) -> None:
        """Export rejects non-causal inquiries."""
        add_hypothesis(graph_path, "h1", source="paper:doi_test")
        add_inquiry(graph_path, "gen", "General", "hypothesis:h1")
        with pytest.raises(ValueError, match="only supported for causal"):
            export_pgmpy_script(graph_path, "gen")
```

**Step 4: Run tests to verify they fail**

Run: `cd science-tool && uv run --frozen pytest tests/test_causal.py::TestExportPgmpy -v`
Expected: FAIL — module does not exist

**Step 5: Implement pgmpy export**

Create `science-tool/src/science_tool/causal/export_pgmpy.py`:

```python
"""Export a causal inquiry to a pgmpy scaffold script."""

from __future__ import annotations

import re
from pathlib import Path

from science_tool.graph.store import (
    PROJECT_NS,
    SCI_NS,
    SCIC_NS,
    _graph_uri,
    _load_dataset,
    _slug,
    get_inquiry,
    shorten_uri,
)
from rdflib import URIRef
from rdflib.namespace import RDF, SKOS


def _variable_name(uri: str) -> str:
    """Convert a URI like 'http://.../concept/my_var' to 'my_var'."""
    short = shorten_uri(uri)
    # Remove prefix like 'concept/'
    if "/" in short:
        short = short.split("/", 1)[1]
    # Make valid Python identifier
    return re.sub(r"[^a-zA-Z0-9_]", "_", short)


def _get_causal_edges_for_inquiry(
    graph_path: Path, slug: str,
) -> list[dict[str, str]]:
    """Get causal edges from graph/causal filtered to inquiry members."""
    safe_slug = _slug(slug)
    inquiry_uri = URIRef(PROJECT_NS[f"inquiry/{safe_slug}"])

    dataset = _load_dataset(graph_path)
    inquiry_graph = dataset.graph(inquiry_uri)
    causal_graph = dataset.graph(_graph_uri("graph/causal"))
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))

    # Collect inquiry members (entities with boundary roles or in flow edges)
    members: set[URIRef] = set()
    for s, _, _ in inquiry_graph.triples((None, SCI_NS.boundaryRole, None)):
        members.add(s)
    for s, p, o in inquiry_graph:
        if p in (SCI_NS.feedsInto, SCI_NS.produces):
            members.add(s)
            members.add(o)

    # Get causal edges between members
    edges: list[dict[str, str]] = []
    for s, p, o in causal_graph.triples((None, SCIC_NS.causes, None)):
        if s in members and o in members:
            # Get labels
            s_label = str(next(knowledge.objects(s, SKOS.prefLabel), shorten_uri(str(s))))
            o_label = str(next(knowledge.objects(o, SKOS.prefLabel), shorten_uri(str(o))))
            edges.append({
                "source_uri": str(s),
                "target_uri": str(o),
                "source_name": _variable_name(str(s)),
                "target_name": _variable_name(str(o)),
                "source_label": s_label,
                "target_label": o_label,
                "predicate": "scic:causes",
            })

    for s, p, o in causal_graph.triples((None, SCIC_NS.confounds, None)):
        if s in members and o in members:
            s_label = str(next(knowledge.objects(s, SKOS.prefLabel), shorten_uri(str(s))))
            o_label = str(next(knowledge.objects(o, SKOS.prefLabel), shorten_uri(str(o))))
            edges.append({
                "source_uri": str(s),
                "target_uri": str(o),
                "source_name": _variable_name(str(s)),
                "target_name": _variable_name(str(o)),
                "source_label": s_label,
                "target_label": o_label,
                "predicate": "scic:confounds",
            })

    return edges


def export_pgmpy_script(graph_path: Path, slug: str) -> str:
    """Generate a pgmpy scaffold script from a causal inquiry."""
    info = get_inquiry(graph_path, slug)

    if info.get("inquiry_type", "general") != "causal":
        raise ValueError(f"pgmpy export only supported for causal inquiries (got '{info.get('inquiry_type')}')")

    edges = _get_causal_edges_for_inquiry(graph_path, slug)
    treatment = info.get("treatment")
    outcome = info.get("outcome")

    treatment_name = _variable_name(treatment) if treatment else "TREATMENT"
    outcome_name = _variable_name(outcome) if outcome else "OUTCOME"

    lines: list[str] = []
    lines.append(f'# Generated from inquiry: {slug}')
    lines.append(f'# Label: {info["label"]}')
    lines.append(f'# Target: {info["target"]}')
    lines.append(f'# Treatment: {treatment_name}')
    lines.append(f'# Outcome: {outcome_name}')
    lines.append("")
    lines.append("from pgmpy.models import BayesianNetwork")
    lines.append("from pgmpy.inference import CausalInference")
    lines.append("")

    # Build edge list
    edge_tuples: list[str] = []
    for edge in edges:
        if edge["predicate"] == "scic:causes":
            comment = f'  # {edge["source_label"]} causes {edge["target_label"]}'
            edge_tuples.append(f'    ("{edge["source_name"]}", "{edge["target_name"]}"),{comment}')

    lines.append("model = BayesianNetwork([")
    lines.extend(edge_tuples)
    lines.append("])")
    lines.append("")

    # Confounders as comments
    confounders = [e for e in edges if e["predicate"] == "scic:confounds"]
    if confounders:
        lines.append("# Confounding relationships (model as common causes):")
        for c in confounders:
            lines.append(f'# {c["source_label"]} confounds {c["target_label"]}')
        lines.append("")

    lines.append("inference = CausalInference(model)")
    lines.append(f'adjustment_sets = inference.get_all_backdoor_adjustment_sets("{treatment_name}", "{outcome_name}")')
    lines.append('print("Valid adjustment sets:", adjustment_sets)')
    lines.append("")

    return "\n".join(lines) + "\n"
```

**Step 6: Run tests to verify they pass**

Run: `cd science-tool && uv run --frozen pytest tests/test_causal.py -v`
Expected: PASS (12 tests)

**Step 7: Commit**

```bash
cd science-tool && git add pyproject.toml src/science_tool/causal/ tests/test_causal.py
git commit -m "feat: add pgmpy export for causal inquiries with [causal] optional deps"
```

---

### Task 5: ChiRho export

**Files:**
- Create: `science-tool/src/science_tool/causal/export_chirho.py`
- Test: `science-tool/tests/test_causal.py`

**Step 1: Write the failing tests**

Add to `test_causal.py`:

```python
from science_tool.causal.export_chirho import export_chirho_script


class TestExportChirho:
    def _build_simple_dag(self, graph_path: Path) -> str:
        """Same helper as TestExportPgmpy."""
        add_concept(graph_path, "X", entity_type="sci:Variable", status="active",
                    properties={"observability": "observed"})
        add_concept(graph_path, "Y", entity_type="sci:Variable", status="active",
                    properties={"observability": "observed"})
        add_concept(graph_path, "Z", entity_type="sci:Variable", status="active",
                    properties={"observability": "observed"})
        add_hypothesis(graph_path, "h1", source="paper:doi_test")
        add_inquiry(graph_path, "xy-dag", "XY DAG", "hypothesis:h1", inquiry_type="causal")
        set_boundary_role(graph_path, "xy-dag", "concept/x", "BoundaryIn")
        set_boundary_role(graph_path, "xy-dag", "concept/y", "BoundaryOut")
        set_boundary_role(graph_path, "xy-dag", "concept/z", "BoundaryIn")
        set_treatment_outcome(graph_path, "xy-dag", treatment="concept/x", outcome="concept/y")
        add_edge(graph_path, "concept/x", "scic:causes", "concept/y", graph_layer="graph/causal")
        add_edge(graph_path, "concept/z", "scic:causes", "concept/y", graph_layer="graph/causal")
        return "xy-dag"

    def test_export_chirho_generates_model_function(self, graph_path: Path) -> None:
        """Export produces a Python module with a Pyro model function."""
        slug = self._build_simple_dag(graph_path)
        script = export_chirho_script(graph_path, slug)
        assert "import pyro" in script
        assert "from chirho.interventional.handlers import do" in script
        assert "def causal_model(" in script
        assert "pyro.sample(" in script

    def test_export_chirho_includes_do_intervention(self, graph_path: Path) -> None:
        """Export includes a do() intervention example."""
        slug = self._build_simple_dag(graph_path)
        script = export_chirho_script(graph_path, slug)
        assert "do(actions=" in script

    def test_export_chirho_rejects_non_causal(self, graph_path: Path) -> None:
        """Export rejects non-causal inquiries."""
        add_hypothesis(graph_path, "h1", source="paper:doi_test")
        add_inquiry(graph_path, "gen", "General", "hypothesis:h1")
        with pytest.raises(ValueError, match="only supported for causal"):
            export_chirho_script(graph_path, "gen")
```

**Step 2: Run tests to verify they fail**

Run: `cd science-tool && uv run --frozen pytest tests/test_causal.py::TestExportChirho -v`
Expected: FAIL — module does not exist

**Step 3: Implement**

Create `science-tool/src/science_tool/causal/export_chirho.py`:

```python
"""Export a causal inquiry to a ChiRho/Pyro scaffold script."""

from __future__ import annotations

from pathlib import Path

from science_tool.causal.export_pgmpy import _get_causal_edges_for_inquiry, _variable_name
from science_tool.graph.store import (
    PROJECT_NS,
    SCI_NS,
    _graph_uri,
    _load_dataset,
    _slug,
    get_inquiry,
    shorten_uri,
)
from rdflib import URIRef
from rdflib.namespace import SKOS


def _topological_sort(edges: list[dict[str, str]]) -> list[str]:
    """Topological sort of variable names from causal edges."""
    from collections import deque

    graph: dict[str, list[str]] = {}
    in_degree: dict[str, int] = {}
    all_nodes: set[str] = set()

    for edge in edges:
        if edge["predicate"] != "scic:causes":
            continue
        s, t = edge["source_name"], edge["target_name"]
        all_nodes.add(s)
        all_nodes.add(t)
        graph.setdefault(s, []).append(t)
        in_degree.setdefault(s, 0)
        in_degree[t] = in_degree.get(t, 0) + 1

    queue = deque(n for n in all_nodes if in_degree.get(n, 0) == 0)
    result: list[str] = []
    while queue:
        node = queue.popleft()
        result.append(node)
        for neighbor in graph.get(node, []):
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    return result


def _get_parents(var_name: str, edges: list[dict[str, str]]) -> list[str]:
    """Get parent variable names (causes) for a variable."""
    return [
        e["source_name"]
        for e in edges
        if e["target_name"] == var_name and e["predicate"] == "scic:causes"
    ]


def export_chirho_script(graph_path: Path, slug: str) -> str:
    """Generate a ChiRho/Pyro scaffold script from a causal inquiry."""
    info = get_inquiry(graph_path, slug)

    if info.get("inquiry_type", "general") != "causal":
        raise ValueError(f"ChiRho export only supported for causal inquiries (got '{info.get('inquiry_type')}')")

    edges = _get_causal_edges_for_inquiry(graph_path, slug)
    treatment = info.get("treatment")
    outcome = info.get("outcome")

    treatment_name = _variable_name(treatment) if treatment else "TREATMENT"
    outcome_name = _variable_name(outcome) if outcome else "OUTCOME"

    sorted_vars = _topological_sort(edges)

    lines: list[str] = []
    lines.append(f'# Generated from inquiry: {slug}')
    lines.append(f'# Label: {info["label"]}')
    lines.append(f'# Target: {info["target"]}')
    lines.append(f'# Treatment: {treatment_name}')
    lines.append(f'# Outcome: {outcome_name}')
    lines.append("#")
    lines.append("# TODO: Replace placeholder distributions with appropriate priors")
    lines.append("# TODO: Add observed data conditioning")
    lines.append("")
    lines.append("import torch")
    lines.append("import pyro")
    lines.append("import pyro.distributions as dist")
    lines.append("from chirho.interventional.handlers import do")
    lines.append("from pyro.infer import Predictive")
    lines.append("")
    lines.append("")
    lines.append("def causal_model():")
    lines.append('    """Structural causal model."""')

    for var in sorted_vars:
        parents = _get_parents(var, edges)
        if not parents:
            # Root node — no parents
            lines.append(f'    {var} = pyro.sample("{var}", dist.Normal(0.0, 1.0))  # root')
        elif len(parents) == 1:
            lines.append(f'    {var} = pyro.sample("{var}", dist.Normal({parents[0]}, 1.0))  # caused by {parents[0]}')
        else:
            parent_sum = " + ".join(parents)
            parent_list = ", ".join(parents)
            lines.append(f'    {var} = pyro.sample("{var}", dist.Normal({parent_sum}, 1.0))  # caused by {parent_list}')

    lines.append(f"    return {outcome_name}")
    lines.append("")
    lines.append("")
    lines.append(f'# Interventional query: P({outcome_name} | do({treatment_name}=1.0))')
    lines.append(f'intervened_model = do(causal_model, actions={{"{treatment_name}": torch.tensor(1.0)}})')
    lines.append("predictive = Predictive(intervened_model, num_samples=1000)")
    lines.append("samples = predictive()")
    lines.append(f'print("{outcome_name} under intervention:", samples["{outcome_name}"].mean().item())')
    lines.append("")

    return "\n".join(lines) + "\n"
```

**Step 4: Run tests to verify they pass**

Run: `cd science-tool && uv run --frozen pytest tests/test_causal.py -v`
Expected: PASS (15 tests)

**Step 5: Commit**

```bash
cd science-tool && git add src/science_tool/causal/export_chirho.py tests/test_causal.py
git commit -m "feat: add ChiRho/Pyro export for causal inquiries"
```

---

### Task 6: CLI export commands

**Files:**
- Modify: `science-tool/src/science_tool/cli.py`
- Test: `science-tool/tests/test_causal_cli.py` (new file)

**Step 1: Write the failing tests**

Create `science-tool/tests/test_causal_cli.py`:

```python
"""CLI tests for causal DAG commands."""

from pathlib import Path

import pytest
from click.testing import CliRunner

from science_tool.cli import main
from science_tool.graph.store import INITIAL_GRAPH_TEMPLATE


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def graph_path(tmp_path: Path) -> Path:
    gp = tmp_path / "knowledge" / "graph.trig"
    gp.parent.mkdir(parents=True)
    gp.write_text(INITIAL_GRAPH_TEMPLATE, encoding="utf-8")
    return gp


def _setup_causal_inquiry(runner: CliRunner, graph_path: Path) -> None:
    """Set up a causal inquiry via CLI commands."""
    p = str(graph_path)
    runner.invoke(main, ["graph", "add", "concept", "X", "--type", "sci:Variable", "--status", "active", "--path", p])
    runner.invoke(main, ["graph", "add", "concept", "Y", "--type", "sci:Variable", "--status", "active", "--path", p])
    runner.invoke(main, ["graph", "add", "concept", "Z", "--type", "sci:Variable", "--status", "active", "--path", p])
    runner.invoke(main, ["graph", "add", "hypothesis", "test hyp", "--source", "paper:doi_test", "--path", p])
    runner.invoke(main, ["inquiry", "init", "test-dag", "--label", "Test DAG",
                         "--target", "hypothesis:test_hyp", "--type", "causal", "--path", p])
    runner.invoke(main, ["inquiry", "add-node", "test-dag", "concept/x", "--role", "BoundaryIn", "--path", p])
    runner.invoke(main, ["inquiry", "add-node", "test-dag", "concept/y", "--role", "BoundaryOut", "--path", p])
    runner.invoke(main, ["inquiry", "add-node", "test-dag", "concept/z", "--role", "BoundaryIn", "--path", p])
    runner.invoke(main, ["inquiry", "set-estimand", "test-dag",
                         "--treatment", "concept/x", "--outcome", "concept/y", "--path", p])
    runner.invoke(main, ["graph", "add", "edge", "concept/x", "scic:causes", "concept/y",
                         "--graph", "graph/causal", "--path", p])
    runner.invoke(main, ["graph", "add", "edge", "concept/z", "scic:causes", "concept/y",
                         "--graph", "graph/causal", "--path", p])


class TestInquiryInitType:
    def test_init_with_type_causal(self, runner: CliRunner, graph_path: Path) -> None:
        """CLI: inquiry init --type causal works."""
        p = str(graph_path)
        runner.invoke(main, ["graph", "add", "hypothesis", "h1", "--source", "paper:doi_test", "--path", p])
        result = runner.invoke(main, ["inquiry", "init", "dag1", "--label", "DAG",
                                      "--target", "hypothesis:h1", "--type", "causal", "--path", p])
        assert result.exit_code == 0
        assert "Created inquiry" in result.output


class TestExportCLI:
    def test_export_pgmpy_cli(self, runner: CliRunner, graph_path: Path, tmp_path: Path) -> None:
        """CLI: inquiry export-pgmpy produces a script file."""
        _setup_causal_inquiry(runner, graph_path)
        out_file = tmp_path / "dag.py"
        result = runner.invoke(main, ["inquiry", "export-pgmpy", "test-dag",
                                      "--output", str(out_file), "--path", str(graph_path)])
        assert result.exit_code == 0
        assert out_file.exists()
        content = out_file.read_text()
        assert "BayesianNetwork" in content

    def test_export_chirho_cli(self, runner: CliRunner, graph_path: Path, tmp_path: Path) -> None:
        """CLI: inquiry export-chirho produces a script file."""
        _setup_causal_inquiry(runner, graph_path)
        out_file = tmp_path / "model.py"
        result = runner.invoke(main, ["inquiry", "export-chirho", "test-dag",
                                      "--output", str(out_file), "--path", str(graph_path)])
        assert result.exit_code == 0
        assert out_file.exists()
        content = out_file.read_text()
        assert "pyro.sample" in content

    def test_export_pgmpy_stdout(self, runner: CliRunner, graph_path: Path) -> None:
        """CLI: inquiry export-pgmpy without --output prints to stdout."""
        _setup_causal_inquiry(runner, graph_path)
        result = runner.invoke(main, ["inquiry", "export-pgmpy", "test-dag", "--path", str(graph_path)])
        assert result.exit_code == 0
        assert "BayesianNetwork" in result.output

    def test_export_non_causal_errors(self, runner: CliRunner, graph_path: Path) -> None:
        """CLI: export on non-causal inquiry gives error."""
        p = str(graph_path)
        runner.invoke(main, ["graph", "add", "hypothesis", "h1", "--source", "paper:doi_test", "--path", p])
        runner.invoke(main, ["inquiry", "init", "gen", "--label", "General",
                             "--target", "hypothesis:h1", "--path", p])
        result = runner.invoke(main, ["inquiry", "export-pgmpy", "gen", "--path", p])
        assert result.exit_code != 0
```

**Step 2: Run tests to verify they fail**

Run: `cd science-tool && uv run --frozen pytest tests/test_causal_cli.py -v`
Expected: FAIL — `export-pgmpy` command doesn't exist

**Step 3: Implement**

Add to `cli.py`:

```python
from science_tool.causal.export_pgmpy import export_pgmpy_script
from science_tool.causal.export_chirho import export_chirho_script
```

```python
@inquiry.command("export-pgmpy")
@click.argument("slug")
@click.option("--output", "output_path", default=None, type=click.Path(path_type=Path))
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def inquiry_export_pgmpy(slug: str, output_path: Path | None, graph_path: Path) -> None:
    """Export a causal inquiry as a pgmpy scaffold script."""
    try:
        script = export_pgmpy_script(graph_path, slug)
    except ValueError as e:
        raise click.ClickException(str(e))

    if output_path:
        output_path.write_text(script, encoding="utf-8")
        click.echo(f"Wrote pgmpy script to {output_path}")
    else:
        click.echo(script)


@inquiry.command("export-chirho")
@click.argument("slug")
@click.option("--output", "output_path", default=None, type=click.Path(path_type=Path))
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def inquiry_export_chirho(slug: str, output_path: Path | None, graph_path: Path) -> None:
    """Export a causal inquiry as a ChiRho/Pyro scaffold script."""
    try:
        script = export_chirho_script(graph_path, slug)
    except ValueError as e:
        raise click.ClickException(str(e))

    if output_path:
        output_path.write_text(script, encoding="utf-8")
        click.echo(f"Wrote ChiRho script to {output_path}")
    else:
        click.echo(script)
```

**Step 4: Run tests to verify they pass**

Run: `cd science-tool && uv run --frozen pytest tests/test_causal_cli.py tests/test_causal.py -v`
Expected: PASS

Run: `cd science-tool && uv run --frozen pytest tests/ -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
cd science-tool && git add src/science_tool/cli.py tests/test_causal_cli.py
git commit -m "feat: add inquiry export-pgmpy and export-chirho CLI commands"
```

---

### Task 7: Causal DAG skill

**Files:**
- Create: `.claude-plugin/skills/models/causal-dag.md`

**Step 1: Write the skill**

Create `.claude-plugin/skills/models/causal-dag.md`:

The skill should cover:
- When to use causal vs general inquiries
- How to think about causal structure: treatment (intervention), outcome, confounders, mediators, colliders
- Common pitfalls: conditioning on colliders, M-bias, selection bias, reverse causation
- Provenance discipline: every `scic:causes` edge needs a claim with source + confidence
- Workflow: `build-dag` → `critique-approach` → `export-pgmpy` / `export-chirho`
- How to interpret pgmpy output (adjustment sets, identifiability)
- When to use ChiRho (interventional/counterfactual queries on probabilistic models) vs pgmpy (graph-theoretic analysis before writing any model code)
- CLI reference: `inquiry init --type causal`, `inquiry set-estimand`, `inquiry export-pgmpy`, `inquiry export-chirho`
- Example: building a simple 3-variable DAG step by step

**Step 2: Commit**

```bash
git add .claude-plugin/skills/models/causal-dag.md
git commit -m "feat: add causal DAG skill for agent-guided causal modeling"
```

---

### Task 8: `/science:build-dag` command

**Files:**
- Create: `.claude-plugin/commands/build-dag.md`

**Step 1: Write the command**

Create `.claude-plugin/commands/build-dag.md` with the command prompt that guides the agent through:

1. Read existing knowledge graph, hypotheses, inquiries
2. Ask: "What causal question are you investigating? What's the treatment/intervention? What's the outcome?"
3. Identify candidate variables from existing KG concepts
4. For each proposed causal edge, ask for justification — create claims with provenance
5. Ask about confounders: "What else could affect both X and Y?"
6. Add variables to `graph/knowledge`, causal edges to `graph/causal`
7. Create causal inquiry with `inquiry init --type causal`
8. Set boundary roles and estimand
9. Run `inquiry validate` and `graph viz`
10. Suggest running `/science:critique-approach`

Reference the `skills/models/causal-dag.md` skill.

**Step 2: Commit**

```bash
git add .claude-plugin/commands/build-dag.md
git commit -m "feat: add /science:build-dag command for guided causal DAG construction"
```

---

### Task 9: `/science:critique-approach` command

**Files:**
- Create: `.claude-plugin/commands/critique-approach.md`

**Step 1: Write the command**

Create `.claude-plugin/commands/critique-approach.md` with the command prompt that guides the agent through:

1. Load the specified causal inquiry (argument: slug)
2. Run `inquiry validate <slug>` to check structural validity
3. Export to pgmpy internally to analyze:
   - Identifiability of target effect
   - Valid adjustment sets
   - Testable implications (conditional independencies)
4. For each causal edge, challenge:
   - "Could this be reverse causation?"
   - "Is there selection bias?"
   - "Could this be mediated by an unmeasured variable?"
   - "What would you expect to see if this edge were absent?"
5. Check for missing confounders, collider bias, overadjustment
6. Write review report to `doc/inquiries/<slug>-critique.md`

Use the `discussant` role — be critical, not rubber-stamping.

**Step 2: Commit**

```bash
git add .claude-plugin/commands/critique-approach.md
git commit -m "feat: add /science:critique-approach command for causal DAG review"
```

---

### Task 10: Update `plan.md` with 4b/4c split

**Files:**
- Modify: `docs/plan.md`

**Step 1: Update Phase 4 section**

Split the existing `4b` deliverables into `4b` (causal modeling) and `4c` (operationalization):

**4b deliverables:**
- `--type causal` on `inquiry init` + `sci:inquiryType` predicate
- `sci:treatment` and `sci:outcome` predicates + `inquiry set-estimand` command
- Causal-specific validation checks (acyclicity for inquiry members)
- `science_tool/causal/export_pgmpy.py` and `export_chirho.py`
- `inquiry export-pgmpy` and `inquiry export-chirho` CLI commands
- `pgmpy` and `chirho` as optional `[causal]` extras
- `skills/models/causal-dag.md` skill
- `/science:build-dag` and `/science:critique-approach` commands
- Tests for all new functionality

**4c deliverables** (moved from old 4b):
- `find_datasets` capability + command surface
- Data validation tooling (Frictionless checks)
- `skills/data/frictionless.md`
- `skills/pipelines/snakemake.md`, `skills/pipelines/marimo.md`
- Snakefile template and templates
- PyMC export (if needed)
- Stage C capability set

**Step 2: Commit**

```bash
git add -f docs/plan.md
git commit -m "docs: split Phase 4 into 4b (causal modeling) and 4c (operationalization)"
```

---

### Task 11: Run on exemplar project + close Phase 4 gate

**Files:**
- Evidence outputs in `docs/exemplar-evidence/` (science repo)
- Knowledge graph updates in `~/d/3d-attention-bias/`

**Step 1: Build a causal DAG in the exemplar project**

In `~/d/3d-attention-bias/`, run:

```bash
# Add causal variables
science-tool graph add concept "3D Distance" --type sci:Variable --status active \
  --property observability computed --note "Pairwise 3D distance between nucleotide positions" \
  --source "paper:doi_..."
science-tool graph add concept "Attention Quality" --type sci:Variable --status active \
  --property observability computed --note "Measured by downstream task performance"
# ... (add 3-5 relevant causal variables)

# Add causal edges
science-tool graph add edge "concept/3d_distance" "scic:causes" "concept/attention_quality" --graph graph/causal
# ...

# Create causal inquiry
science-tool inquiry init "3d-attention-effect" --type causal --label "3D Distance → Attention Quality" \
  --target "hypothesis:h01_3d_attention_improves_performance"
science-tool inquiry set-estimand "3d-attention-effect" \
  --treatment "concept/3d_distance" --outcome "concept/attention_quality"
# Add boundary roles...

# Validate
science-tool inquiry validate "3d-attention-effect" --format json

# Export
science-tool inquiry export-pgmpy "3d-attention-effect" --output code/causal/dag_pgmpy.py
science-tool inquiry export-chirho "3d-attention-effect" --output code/causal/dag_chirho.py
```

**Step 2: Archive evidence**

Copy validation output and export scripts to `docs/exemplar-evidence/` in the science repo:
- `causal-validate.json`
- `causal-export-pgmpy.py`
- `causal-export-chirho.py`

**Step 3: Update `plan.md`**

Mark Phase 4b deliverables as done, update Phase 4 gate with evidence reference.

**Step 4: Commit**

```bash
git add -f docs/plan.md docs/exemplar-evidence/
git commit -m "feat: close Phase 4 gate — causal DAG exemplar with pgmpy/ChiRho exports"
```

---

Plan complete and saved to `docs/plans/2026-03-07-phase4b-causal-dag-plan.md`. Two execution options:

**1. Subagent-Driven (this session)** — I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** — Open new session with executing-plans, batch execution with checkpoints

Which approach?
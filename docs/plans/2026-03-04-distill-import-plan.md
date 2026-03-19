# Distillation & Import Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement snapshot distillation (OpenAlex + PyKEEN) and `graph import` to complete Slice A.

**Architecture:** Three new modules in `src/science_tool/distill/` (init helpers, openalex fetcher, pykeen distiller), plus a `graph import` CLI command that merges `.ttl` snapshots into the project graph. All distill deps are optional (`[distill]` extras).

**Tech Stack:** rdflib (Turtle serialization), httpx (OpenAlex API), pykeen (dataset loading), networkx (PageRank), click (CLI)

## Status

| Task | Description | Status |
|------|-------------|--------|
| 1 | `[distill]` deps + package skeleton | DONE |
| 2 | OpenAlex distiller | DONE |
| 3 | PyKEEN distiller | DONE |
| 4 | `graph import` command | DONE |
| 5 | `distill` CLI group | DONE |
| 6 | Lint, type-check, verification | DONE |

---

### Task 1: Add `[distill]` dependency group and `distill/` package skeleton

**Files:**
- Modify: `science-tool/pyproject.toml`
- Create: `science-tool/src/science_tool/distill/__init__.py`

**Step 1: Update pyproject.toml with optional distill dependencies**

Add the `[distill]` extras group after the existing `[dependency-groups]` section:

```toml
[project.optional-dependencies]
distill = [
    "pykeen",
    "networkx>=3.2",
    "httpx",
]
```

**Step 2: Create the distill package with shared helpers**

Create `science-tool/src/science_tool/distill/__init__.py`:

```python
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import PROV, RDF, SKOS, XSD

SCHEMA_NS = Namespace("https://schema.org/")
SCI_NS = Namespace("http://example.org/science/vocab/")
SNAPSHOT_NS = Namespace("http://example.org/science/snapshots/")

DEFAULT_SNAPSHOT_DIR = Path("data/snapshots")


def bind_common_prefixes(g: Graph) -> None:
    """Bind standard prefixes to a graph for clean Turtle output."""
    g.bind("rdf", RDF)
    g.bind("skos", SKOS)
    g.bind("prov", PROV)
    g.bind("schema", SCHEMA_NS)
    g.bind("sci", SCI_NS)
    g.bind("xsd", XSD)


def write_snapshot(
    g: Graph,
    *,
    output_path: Path,
    name: str,
    source_url: str,
    version: str,
    node_count: int,
    triple_count: int,
) -> Path:
    """Serialize graph to Turtle and update manifest.ttl alongside it."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    g.serialize(destination=str(output_path), format="turtle")

    _update_manifest(
        manifest_path=output_path.parent / "manifest.ttl",
        snapshot_stem=output_path.stem,
        name=name,
        source_url=source_url,
        version=version,
        node_count=node_count,
        triple_count=triple_count,
        snapshot_path=output_path,
    )

    return output_path


def _update_manifest(
    manifest_path: Path,
    snapshot_stem: str,
    name: str,
    source_url: str,
    version: str,
    node_count: int,
    triple_count: int,
    snapshot_path: Path,
) -> None:
    """Write or update a manifest.ttl entry for this snapshot."""
    if manifest_path.exists():
        manifest = Graph()
        manifest.parse(str(manifest_path), format="turtle")
    else:
        manifest = Graph()

    manifest.bind("prov", PROV)
    manifest.bind("schema", SCHEMA_NS)
    manifest.bind("xsd", XSD)
    manifest.bind("", SNAPSHOT_NS)

    entry = URIRef(SNAPSHOT_NS[snapshot_stem])

    # Remove old triples for this entry
    for triple in list(manifest.triples((entry, None, None))):
        manifest.remove(triple)

    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    file_hash = _sha256_file(snapshot_path)
    size_str = f"{node_count} nodes, {triple_count} triples"

    manifest.add((entry, RDF.type, PROV.Entity))
    manifest.add((entry, RDF.type, SCHEMA_NS.Dataset))
    manifest.add((entry, SCHEMA_NS.name, Literal(name)))
    manifest.add((entry, PROV.generatedAtTime, Literal(now, datatype=XSD.dateTime)))
    manifest.add((entry, PROV.wasDerivedFrom, URIRef(source_url)))
    manifest.add((entry, SCHEMA_NS.version, Literal(version)))
    manifest.add((entry, SCHEMA_NS.size, Literal(size_str)))
    manifest.add((entry, SCHEMA_NS.sha256, Literal(file_hash)))

    manifest.serialize(destination=str(manifest_path), format="turtle")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()
```

**Step 3: Install distill extras in dev environment**

Run: `cd science-tool && uv add --optional distill pykeen "networkx>=3.2" httpx`

**Step 4: Verify the package imports**

Run: `cd science-tool && uv run python -c "from science_tool.distill import write_snapshot; print('ok')"`
Expected: `ok`

**Step 5: Commit**

```bash
git add science-tool/pyproject.toml science-tool/src/science_tool/distill/__init__.py science-tool/uv.lock
git commit -m "feat: add distill package skeleton with shared helpers and [distill] extras"
```

---

### Task 2: OpenAlex distiller — test and implementation

**Files:**
- Create: `science-tool/tests/test_distill.py`
- Create: `science-tool/src/science_tool/distill/openalex.py`

**Step 1: Write the failing tests for OpenAlex distiller**

Create `science-tool/tests/test_distill.py`:

```python
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner
from rdflib import Graph, Namespace
from rdflib.namespace import RDF, SKOS

from science_tool.cli import main
from science_tool.distill.openalex import distill_openalex

SCI = Namespace("http://example.org/science/vocab/")
SCHEMA = Namespace("https://schema.org/")


def _mock_openalex_response(level: str) -> list[dict]:
    """Fixture: minimal OpenAlex API response for testing."""
    if level == "domains":
        return [
            {
                "id": "https://openalex.org/domains/1",
                "display_name": "Life Sciences",
                "works_count": 100000,
            },
        ]
    if level == "fields":
        return [
            {
                "id": "https://openalex.org/fields/11",
                "display_name": "Agricultural and Biological Sciences",
                "domain": {"id": "https://openalex.org/domains/1", "display_name": "Life Sciences"},
                "works_count": 50000,
            },
            {
                "id": "https://openalex.org/fields/12",
                "display_name": "Biochemistry, Genetics and Molecular Biology",
                "domain": {"id": "https://openalex.org/domains/1", "display_name": "Life Sciences"},
                "works_count": 60000,
            },
        ]
    if level == "subfields":
        return [
            {
                "id": "https://openalex.org/subfields/1101",
                "display_name": "Agricultural and Biological Sciences (miscellaneous)",
                "field": {"id": "https://openalex.org/fields/11", "display_name": "Agricultural and Biological Sciences"},
                "works_count": 5000,
            },
            {
                "id": "https://openalex.org/subfields/1201",
                "display_name": "Biochemistry",
                "field": {"id": "https://openalex.org/fields/12", "display_name": "Biochemistry, Genetics and Molecular Biology"},
                "works_count": 30000,
            },
        ]
    return []


def _mock_fetch_all(endpoint: str) -> list[dict]:
    """Mock for openalex._fetch_all_pages that returns fixture data."""
    level = endpoint.rstrip("/").rsplit("/", 1)[-1]
    return _mock_openalex_response(level)


def test_distill_openalex_subfields_produces_valid_turtle(tmp_path: Path) -> None:
    output = tmp_path / "openalex-science-map.ttl"

    with patch("science_tool.distill.openalex._fetch_all_pages", side_effect=_mock_fetch_all):
        result = distill_openalex(level="subfields", output_path=output)

    assert result.exists()
    g = Graph()
    g.parse(str(result), format="turtle")

    # Should have domain, field, and subfield nodes typed as sci:Concept
    concepts = set(g.subjects(RDF.type, SCI.Concept))
    assert len(concepts) == 5  # 1 domain + 2 fields + 2 subfields

    # All should have prefLabel
    for concept in concepts:
        assert any(g.triples((concept, SKOS.prefLabel, None)))

    # Should have broader/narrower links
    broader_count = len(list(g.triples((None, SKOS.broader, None))))
    assert broader_count >= 4  # 2 fields→domain + 2 subfields→field


def test_distill_openalex_writes_manifest(tmp_path: Path) -> None:
    output = tmp_path / "openalex-science-map.ttl"

    with patch("science_tool.distill.openalex._fetch_all_pages", side_effect=_mock_fetch_all):
        distill_openalex(level="subfields", output_path=output)

    manifest = tmp_path / "manifest.ttl"
    assert manifest.exists()

    g = Graph()
    g.parse(str(manifest), format="turtle")
    assert len(list(g.triples((None, SCHEMA.name, None)))) == 1
    assert len(list(g.triples((None, SCHEMA.sha256, None)))) == 1
```

**Step 2: Run tests to verify they fail**

Run: `cd science-tool && uv run pytest tests/test_distill.py -v`
Expected: FAIL (module not found)

**Step 3: Implement the OpenAlex distiller**

Create `science-tool/src/science_tool/distill/openalex.py`:

```python
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlencode

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDF, SKOS, XSD

from science_tool.distill import (
    DEFAULT_SNAPSHOT_DIR,
    SCHEMA_NS,
    SCI_NS,
    bind_common_prefixes,
    write_snapshot,
)

OPENALEX_BASE = "https://api.openalex.org"

# Hierarchy: domains → fields → subfields → topics
LEVELS = ("domains", "fields", "subfields", "topics")


def distill_openalex(
    *,
    level: str = "subfields",
    output_path: Path | None = None,
) -> Path:
    """Fetch OpenAlex science hierarchy up to the given level and write Turtle snapshot."""
    if level not in LEVELS:
        raise ValueError(f"Invalid level: {level}. Must be one of {LEVELS}")

    target_idx = LEVELS.index(level)
    levels_to_fetch = LEVELS[: target_idx + 1]

    all_items: dict[str, dict[str, list[dict]]] = {}
    for lvl in levels_to_fetch:
        all_items[lvl] = {item["id"]: item for item in _fetch_all_pages(lvl)}

    g = Graph()
    bind_common_prefixes(g)

    node_count = 0
    for lvl in levels_to_fetch:
        for item_id, item in all_items[lvl].items():
            node_uri = URIRef(item_id)
            g.add((node_uri, RDF.type, SCI_NS.Concept))
            g.add((node_uri, RDF.type, SKOS.Concept))
            g.add((node_uri, SKOS.prefLabel, Literal(item["display_name"])))

            works_count = item.get("works_count")
            if works_count is not None:
                g.add((node_uri, SCHEMA_NS.size, Literal(works_count, datatype=XSD.integer)))

            # Link to parent via skos:broader
            parent_key = _parent_level_key(lvl)
            if parent_key and parent_key in item and isinstance(item[parent_key], dict):
                parent_uri = URIRef(item[parent_key]["id"])
                g.add((node_uri, SKOS.broader, parent_uri))
                g.add((parent_uri, SKOS.narrower, node_uri))

            node_count += 1

    triple_count = len(g)

    if output_path is None:
        stem = "openalex-topics" if level == "topics" else "openalex-science-map"
        output_path = DEFAULT_SNAPSHOT_DIR / f"{stem}.ttl"

    return write_snapshot(
        g,
        output_path=output_path,
        name=f"OpenAlex Science Map ({level} level)",
        source_url=f"{OPENALEX_BASE}/{level}",
        version=f"openalex:{level}",
        node_count=node_count,
        triple_count=triple_count,
    )


def _parent_level_key(level: str) -> str | None:
    """Return the JSON key for the parent entity at a given hierarchy level."""
    return {
        "domains": None,
        "fields": "domain",
        "subfields": "field",
        "topics": "subfield",
    }.get(level)


def _fetch_all_pages(endpoint: str) -> list[dict]:
    """Fetch all pages from an OpenAlex API endpoint. Returns list of result dicts."""
    try:
        import httpx
    except ImportError as exc:
        raise ImportError("httpx is required for OpenAlex distillation. Install with: uv add --optional distill httpx") from exc

    url = f"{OPENALEX_BASE}/{endpoint}"
    items: list[dict] = []
    page = 1
    per_page = 200

    while True:
        params = {"per_page": per_page, "page": page}
        response = httpx.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        results = data.get("results", [])
        if not results:
            break

        items.extend(results)

        meta = data.get("meta", {})
        total = meta.get("count", 0)
        if len(items) >= total:
            break

        page += 1

    return items
```

**Step 4: Run tests to verify they pass**

Run: `cd science-tool && uv run pytest tests/test_distill.py -v`
Expected: PASS (2 tests)

**Step 5: Commit**

```bash
git add science-tool/src/science_tool/distill/openalex.py science-tool/tests/test_distill.py
git commit -m "feat: add OpenAlex distiller with SKOS hierarchy output"
```

---

### Task 3: PyKEEN-based distiller — test and implementation

**Files:**
- Modify: `science-tool/tests/test_distill.py` (append tests)
- Create: `science-tool/src/science_tool/distill/pykeen_source.py`

**Step 1: Write the failing tests for PyKEEN distiller**

Append to `science-tool/tests/test_distill.py`:

```python
import numpy as np

from science_tool.distill.pykeen_source import distill_pykeen


def _make_mock_triples_factory():
    """Create a mock TriplesFactory with small synthetic data."""
    from unittest.mock import MagicMock

    triples = np.array([
        ["GeneA", "interacts_with", "GeneB"],
        ["GeneA", "associated_with", "DiseaseX"],
        ["GeneB", "interacts_with", "GeneC"],
        ["DrugAlpha", "treats", "DiseaseX"],
        ["DiseaseX", "phenotype_present", "PhenotypeP"],
        ["GeneC", "associated_with", "DiseaseY"],
        ["DrugBeta", "treats", "DiseaseY"],
        ["GeneA", "interacts_with", "GeneC"],
    ], dtype=object)

    factory = MagicMock()
    factory.triples = triples
    factory.num_entities = 8
    factory.num_relations = 4
    factory.entity_to_id = {name: i for i, name in enumerate(
        ["GeneA", "GeneB", "GeneC", "DiseaseX", "DiseaseY", "DrugAlpha", "DrugBeta", "PhenotypeP"]
    )}
    factory.relation_to_id = {name: i for i, name in enumerate(
        ["interacts_with", "associated_with", "treats", "phenotype_present"]
    )}
    return factory


def test_distill_pykeen_no_budget_takes_all_triples(tmp_path: Path) -> None:
    output = tmp_path / "test-dataset.ttl"
    factory = _make_mock_triples_factory()

    with patch("science_tool.distill.pykeen_source._load_pykeen_dataset", return_value=factory):
        result = distill_pykeen(dataset_name="TestDataset", output_path=output)

    assert result.exists()
    g = Graph()
    g.parse(str(result), format="turtle")

    concepts = set(g.subjects(RDF.type, SCI.Concept))
    assert len(concepts) == 8  # all entities

    # All entities should have prefLabel
    for concept in concepts:
        assert any(g.triples((concept, SKOS.prefLabel, None)))


def test_distill_pykeen_with_budget_reduces_entities(tmp_path: Path) -> None:
    output = tmp_path / "test-budget.ttl"
    factory = _make_mock_triples_factory()

    with patch("science_tool.distill.pykeen_source._load_pykeen_dataset", return_value=factory):
        result = distill_pykeen(dataset_name="TestDataset", budget=4, output_path=output)

    assert result.exists()
    g = Graph()
    g.parse(str(result), format="turtle")

    concepts = set(g.subjects(RDF.type, SCI.Concept))
    # Budget=4 means at most 4 entities selected
    assert len(concepts) <= 4
    assert len(concepts) >= 1  # at least some survived


def test_distill_pykeen_writes_manifest(tmp_path: Path) -> None:
    output = tmp_path / "test-dataset.ttl"
    factory = _make_mock_triples_factory()

    with patch("science_tool.distill.pykeen_source._load_pykeen_dataset", return_value=factory):
        distill_pykeen(dataset_name="TestDataset", output_path=output)

    manifest = tmp_path / "manifest.ttl"
    assert manifest.exists()
```

**Step 2: Run tests to verify they fail**

Run: `cd science-tool && uv run pytest tests/test_distill.py::test_distill_pykeen_no_budget_takes_all_triples -v`
Expected: FAIL (module not found)

**Step 3: Implement the PyKEEN distiller**

Create `science-tool/src/science_tool/distill/pykeen_source.py`:

```python
from __future__ import annotations

import re
from pathlib import Path

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, SKOS

from science_tool.distill import (
    DEFAULT_SNAPSHOT_DIR,
    SCI_NS,
    bind_common_prefixes,
    write_snapshot,
)

DATASET_NS = Namespace("http://example.org/science/datasets/")


def distill_pykeen(
    *,
    dataset_name: str,
    budget: int | None = None,
    output_path: Path | None = None,
) -> Path:
    """Distill a PyKEEN dataset into a Turtle snapshot.

    If budget is given, select top-N entities by PageRank and retain
    only edges between selected entities. Otherwise, take all triples.
    """
    factory = _load_pykeen_dataset(dataset_name)
    triples = factory.triples  # numpy array of (head, relation, tail) strings

    if budget is not None and budget < len(factory.entity_to_id):
        selected_entities = _pagerank_select(triples, budget)
    else:
        selected_entities = set(factory.entity_to_id.keys())

    g = Graph()
    bind_common_prefixes(g)
    slug = _slug(dataset_name)
    ds_ns = Namespace(f"{DATASET_NS}{slug}/")
    g.bind("ds", ds_ns)

    # Add entity nodes
    for entity in sorted(selected_entities):
        entity_uri = URIRef(ds_ns[_slug(entity)])
        g.add((entity_uri, RDF.type, SCI_NS.Concept))
        g.add((entity_uri, SKOS.prefLabel, Literal(entity)))

    # Add edges between selected entities
    triple_count_before = len(g)
    for head, relation, tail in triples:
        if head in selected_entities and tail in selected_entities:
            head_uri = URIRef(ds_ns[_slug(head)])
            tail_uri = URIRef(ds_ns[_slug(tail)])
            rel_uri = URIRef(ds_ns[f"rel/{_slug(relation)}"])
            g.add((head_uri, rel_uri, tail_uri))

    node_count = len(selected_entities)
    total_triples = len(g)

    if output_path is None:
        output_path = DEFAULT_SNAPSHOT_DIR / f"{slug}-core.ttl"

    source_url = f"https://pykeen.readthedocs.io/en/stable/api/pykeen.datasets.{dataset_name}.html"

    return write_snapshot(
        g,
        output_path=output_path,
        name=f"{dataset_name} (PyKEEN distillation, budget={budget or 'all'})",
        source_url=source_url,
        version=f"pykeen:{slug}",
        node_count=node_count,
        triple_count=total_triples,
    )


def _pagerank_select(triples, budget: int) -> set[str]:
    """Select top-N entities by PageRank from the triple set."""
    try:
        import networkx as nx
    except ImportError as exc:
        raise ImportError(
            "networkx is required for budget-based distillation. Install with: uv add --optional distill 'networkx>=3.2'"
        ) from exc

    G = nx.DiGraph()
    for head, relation, tail in triples:
        G.add_edge(head, tail, relation=relation)

    pr = nx.pagerank(G)
    ranked = sorted(pr.items(), key=lambda x: x[1], reverse=True)
    return {entity for entity, _ in ranked[:budget]}


def _load_pykeen_dataset(dataset_name: str):
    """Load a PyKEEN dataset by name. Returns a TriplesFactory."""
    try:
        from pykeen.datasets import get_dataset
    except ImportError as exc:
        raise ImportError(
            "pykeen is required for KG distillation. Install with: uv add --optional distill pykeen"
        ) from exc

    dataset = get_dataset(dataset=dataset_name)
    return dataset.training


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
```

**Step 4: Run tests to verify they pass**

Run: `cd science-tool && uv run pytest tests/test_distill.py -v`
Expected: PASS (5 tests)

**Step 5: Commit**

```bash
git add science-tool/src/science_tool/distill/pykeen_source.py science-tool/tests/test_distill.py
git commit -m "feat: add PyKEEN-based distiller with PageRank budget selection"
```

---

### Task 4: `graph import` command — test and implementation

**Files:**
- Modify: `science-tool/tests/test_distill.py` (append import tests)
- Modify: `science-tool/src/science_tool/graph/store.py` (add `import_snapshot` function)
- Modify: `science-tool/src/science_tool/cli.py` (add `graph import` command)

**Step 1: Write the failing tests for graph import**

Append to `science-tool/tests/test_distill.py`:

```python
from rdflib.namespace import PROV


def _write_test_snapshot(path: Path) -> None:
    """Write a minimal Turtle snapshot for import testing."""
    g = Graph()
    g.bind("sci", SCI)
    g.bind("skos", SKOS)
    concept = URIRef("http://example.org/test/concept1")
    g.add((concept, RDF.type, SCI.Concept))
    g.add((concept, SKOS.prefLabel, Literal("TestConcept")))
    g.serialize(destination=str(path), format="turtle")


def test_graph_import_merges_into_knowledge_layer(tmp_path: Path) -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        assert runner.invoke(main, ["graph", "init"]).exit_code == 0

        snapshot = Path("snapshot.ttl")
        _write_test_snapshot(snapshot)

        result = runner.invoke(main, ["graph", "import", str(snapshot)])
        assert result.exit_code == 0

        from rdflib import Dataset as RdfDataset

        dataset = RdfDataset()
        dataset.parse(source="knowledge/graph.trig", format="trig")
        knowledge = dataset.graph(URIRef("http://example.org/project/graph/knowledge"))

        concept = URIRef("http://example.org/test/concept1")
        assert (concept, RDF.type, SCI.Concept) in knowledge
        assert (concept, SKOS.prefLabel, Literal("TestConcept")) in knowledge


def test_graph_import_records_provenance(tmp_path: Path) -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        assert runner.invoke(main, ["graph", "init"]).exit_code == 0

        snapshot = Path("snapshot.ttl")
        _write_test_snapshot(snapshot)

        result = runner.invoke(main, ["graph", "import", str(snapshot)])
        assert result.exit_code == 0

        from rdflib import Dataset as RdfDataset

        dataset = RdfDataset()
        dataset.parse(source="knowledge/graph.trig", format="trig")
        provenance = dataset.graph(URIRef("http://example.org/project/graph/provenance"))

        # Should have an import provenance record
        import_records = list(provenance.triples((None, PROV.generatedAtTime, None)))
        assert len(import_records) >= 1


def test_graph_import_reports_triple_count() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        assert runner.invoke(main, ["graph", "init"]).exit_code == 0

        snapshot = Path("snapshot.ttl")
        _write_test_snapshot(snapshot)

        result = runner.invoke(main, ["graph", "import", str(snapshot)])
        assert result.exit_code == 0
        assert "2" in result.output  # 2 triples imported
```

**Step 2: Run tests to verify they fail**

Run: `cd science-tool && uv run pytest tests/test_distill.py::test_graph_import_merges_into_knowledge_layer -v`
Expected: FAIL (no `import` command)

**Step 3: Add `import_snapshot` to store.py**

Add to `science-tool/src/science_tool/graph/store.py`, after the `add_edge` function:

```python
def import_snapshot(graph_path: Path, snapshot_path: Path) -> int:
    """Import a Turtle snapshot into :graph/knowledge and record provenance. Returns triple count."""
    if not snapshot_path.exists():
        raise click.ClickException(f"Snapshot file not found: {snapshot_path}")

    snapshot = Graph()
    snapshot.parse(str(snapshot_path), format="turtle")
    imported_count = len(snapshot)

    if imported_count == 0:
        raise click.ClickException(f"Snapshot contains no triples: {snapshot_path}")

    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))

    for triple in snapshot:
        knowledge.add(triple)

    # Record import provenance
    provenance = dataset.graph(_graph_uri("graph/provenance"))
    import_uri = URIRef(PROJECT_NS[f"import/{_slug(snapshot_path.stem)}"])
    import_time = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    for triple in list(provenance.triples((import_uri, None, None))):
        provenance.remove(triple)

    provenance.add((import_uri, RDF.type, PROV.Activity))
    provenance.add((import_uri, SCHEMA_NS.name, Literal(f"Import: {snapshot_path.name}")))
    provenance.add((import_uri, PROV.generatedAtTime, Literal(import_time, datatype=XSD.dateTime)))
    provenance.add((import_uri, SCHEMA_NS.size, Literal(imported_count, datatype=XSD.integer)))

    _save_dataset(dataset, graph_path)
    return imported_count
```

Note: requires adding these imports at the top of `store.py` if not already present:

```python
from datetime import datetime, timezone
from rdflib import Graph
```

Also add `import_snapshot` to the existing imports from `store.py` in both `cli.py` and `graph/__init__.py`.

**Step 4: Add `graph import` CLI command to cli.py**

Add to `science-tool/src/science_tool/cli.py`, after the `graph_viz` command:

```python
@graph.command("import")
@click.argument("snapshot_path", type=click.Path(exists=True, path_type=Path))
@click.option("--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path))
def graph_import(snapshot_path: Path, graph_path: Path) -> None:
    """Import a Turtle snapshot into the knowledge graph."""

    count = import_snapshot(graph_path=graph_path, snapshot_path=snapshot_path)
    click.echo(f"Imported {count} triples from {snapshot_path.name}")
```

Add `import_snapshot` to the imports from `science_tool.graph.store` at the top of `cli.py`.

**Step 5: Run tests to verify they pass**

Run: `cd science-tool && uv run pytest tests/test_distill.py -v`
Expected: PASS (8 tests)

**Step 6: Commit**

```bash
git add science-tool/src/science_tool/graph/store.py science-tool/src/science_tool/cli.py science-tool/src/science_tool/graph/__init__.py science-tool/tests/test_distill.py
git commit -m "feat: add graph import command with provenance recording"
```

---

### Task 5: CLI `distill` command group — test and implementation

**Files:**
- Modify: `science-tool/src/science_tool/cli.py` (add `distill` group with `openalex` and `pykeen` subcommands)
- Modify: `science-tool/tests/test_distill.py` (add CLI integration tests)

**Step 1: Write the failing CLI tests**

Append to `science-tool/tests/test_distill.py`:

```python
def test_distill_openalex_cli(tmp_path: Path) -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        with patch("science_tool.distill.openalex._fetch_all_pages", side_effect=_mock_fetch_all):
            result = runner.invoke(main, ["distill", "openalex", "--level", "subfields"])

        assert result.exit_code == 0
        assert "openalex" in result.output.lower()
        assert Path("data/snapshots/openalex-science-map.ttl").exists()
        assert Path("data/snapshots/manifest.ttl").exists()


def test_distill_pykeen_cli(tmp_path: Path) -> None:
    runner = CliRunner()
    factory = _make_mock_triples_factory()

    with runner.isolated_filesystem():
        with patch("science_tool.distill.pykeen_source._load_pykeen_dataset", return_value=factory):
            result = runner.invoke(main, ["distill", "pykeen", "TestDataset"])

        assert result.exit_code == 0
        assert Path("data/snapshots/testdataset-core.ttl").exists()
```

**Step 2: Run tests to verify they fail**

Run: `cd science-tool && uv run pytest tests/test_distill.py::test_distill_openalex_cli -v`
Expected: FAIL (no `distill` command group)

**Step 3: Add the `distill` CLI group to cli.py**

Add to `science-tool/src/science_tool/cli.py`:

```python
from science_tool.distill.openalex import distill_openalex
from science_tool.distill.pykeen_source import distill_pykeen


@main.group()
def distill() -> None:
    """Distill public knowledge graphs into Turtle snapshots."""


@distill.command("openalex")
@click.option("--level", type=click.Choice(("subfields", "topics")), default="subfields", show_default=True)
@click.option("--output", "output_path", default=None, type=click.Path(path_type=Path))
def distill_openalex_cmd(level: str, output_path: Path | None) -> None:
    """Fetch OpenAlex science hierarchy and write Turtle snapshot."""

    result = distill_openalex(level=level, output_path=output_path)
    click.echo(f"Wrote OpenAlex snapshot ({level}) to {result}")


@distill.command("pykeen")
@click.argument("dataset_name")
@click.option("--budget", type=int, default=None)
@click.option("--output", "output_path", default=None, type=click.Path(path_type=Path))
def distill_pykeen_cmd(dataset_name: str, budget: int | None, output_path: Path | None) -> None:
    """Distill a PyKEEN dataset into a Turtle snapshot."""

    result = distill_pykeen(dataset_name=dataset_name, budget=budget, output_path=output_path)
    click.echo(f"Wrote {dataset_name} snapshot to {result}")
```

**Step 4: Run all tests to verify they pass**

Run: `cd science-tool && uv run pytest tests/ -v`
Expected: PASS (all tests)

**Step 5: Commit**

```bash
git add science-tool/src/science_tool/cli.py science-tool/tests/test_distill.py
git commit -m "feat: add distill CLI group with openalex and pykeen subcommands"
```

---

### Task 6: Lint, type-check, and full verification

**Files:** None (verification only)

**Step 1: Run ruff check**

Run: `cd science-tool && uv run ruff check .`
Expected: No errors. Fix any issues found.

**Step 2: Run ruff format**

Run: `cd science-tool && uv run ruff format .`

**Step 3: Run pyright**

Run: `cd science-tool && uv run pyright .`
Expected: No errors. Fix any type issues found.

**Step 4: Run full test suite**

Run: `cd science-tool && uv run pytest tests/ -v`
Expected: All tests pass.

**Step 5: Update design doc progress note**

Update the progress note at line 759 in `docs/plans/2026-03-01-knowledge-graph-design.md` to reflect Slice A completion:

```markdown
Current progress note (2026-03-04): Slice A is complete. All query presets, snapshot distillation (OpenAlex + PyKEEN), graph import with provenance, and manifest generation are implemented with tests.
```

**Step 6: Commit**

```bash
git add -A
git commit -m "chore: lint, type-check, and update Slice A progress"
```

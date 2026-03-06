# Graph Enrichment Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enrich the knowledge graph CLI with CiTO/dcterms ontology support, entity property flags, an `add question` command, a `graph predicates` command, and updated skill documentation.

**Architecture:** Extend `store.py` with new namespace constants and updated `add_concept`/`add_hypothesis` signatures, add `add_question` and `query_predicates` functions, wire through `cli.py`, then update the three skill/command markdown files. All changes are additive -- no existing function signatures break.

**Tech Stack:** Python 3.12, rdflib, click, pytest, CliRunner

## Status

| Task | Description | Status | Commit |
|------|-------------|--------|--------|
| 1 | CiTO/dcterms namespace prefixes | DONE | `cd90010` |
| 2 | `--note` and `--definition` flags | DONE | `06daad6` |
| 3 | `--property` flag | DONE | `06daad6` |
| 4 | `--status` and `--source` flags | DONE | `06daad6` |
| 5 | `--status` on `add hypothesis` | DONE | `4839af2` |
| 6 | `add question` command | DONE | `4839af2` |
| 7 | `graph predicates` command | DONE | `8f7fcc3` |
| 8 | Update SKILL.md | DONE | `d1ec245`, refined in prompt iteration |
| 9 | Update create-graph.md | DONE | `d1ec245`, refined in prompt iteration |
| 10 | Lint, type-check, final tests | DONE | `f9627c4` |

**Post-implementation fixes** (not in original plan):
- Restored `pyyaml>=6.0` to `pyproject.toml` — incorrectly removed in `308e910`, broke CLI at import
- Added uv cache note to command files — `uv run --with` served stale builds missing new commands/flags
- Front-loaded Rules section in `create-graph.md` — agents ignored constraints buried at bottom
- Simplified `create-graph.md` workflow — removed useless scan-prose/stats steps for fresh graphs
- Added predicate rule to `update-graph.md` Important Notes
- Merged duplicate predicate sections in SKILL.md into single table with Deprecated column

See `2026-03-05-graph-enrichment-design.md` § "Post-Implementation Issues" for details.

---

### Task 1: Add CiTO and dcterms namespace prefixes

**Files:**
- Modify: `science-tool/src/science_tool/graph/store.py:11-37`
- Test: `science-tool/tests/test_graph_cli.py`

**Step 1: Write the failing test**

Add to `test_graph_cli.py`:

```python
def test_cito_prefix_resolves_in_add_edge() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        assert runner.invoke(main, ["graph", "init"]).exit_code == 0

        edge = runner.invoke(
            main,
            [
                "graph", "add", "edge",
                "claim/c1", "cito:supports", "hypothesis/h1",
                "--graph", "graph/knowledge",
            ],
        )
        assert edge.exit_code == 0

        dataset = Dataset()
        dataset.parse(source="knowledge/graph.trig", format="trig")
        knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
        cito_supports = Namespace("http://purl.org/spar/cito/")["supports"]
        assert (PROJECT_NS["claim/c1"], cito_supports, PROJECT_NS["hypothesis/h1"]) in knowledge


def test_dcterms_prefix_resolves_in_add_edge() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        assert runner.invoke(main, ["graph", "init"]).exit_code == 0

        edge = runner.invoke(
            main,
            [
                "graph", "add", "edge",
                "concept/brca1", "dcterms:identifier", "concept/ncbigene_672",
                "--graph", "graph/knowledge",
            ],
        )
        assert edge.exit_code == 0

        dataset = Dataset()
        dataset.parse(source="knowledge/graph.trig", format="trig")
        knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
        dcterms_id = Namespace("http://purl.org/dc/terms/")["identifier"]
        assert (PROJECT_NS["concept/brca1"], dcterms_id, PROJECT_NS["concept/ncbigene_672"]) in knowledge
```

**Step 2: Run tests to verify they fail**

Run: `cd science-tool && uv run --frozen pytest tests/test_graph_cli.py::test_cito_prefix_resolves_in_add_edge tests/test_graph_cli.py::test_dcterms_prefix_resolves_in_add_edge -v`
Expected: FAIL with "Unknown CURIE prefix"

**Step 3: Write minimal implementation**

In `store.py`, add to imports (after line 12):

```python
CITO_NS = Namespace("http://purl.org/spar/cito/")
DCTERMS_NS = Namespace("http://purl.org/dc/terms/")
```

Add to `CURIE_PREFIXES` dict (after line 36):

```python
    "cito": CITO_NS,
    "dcterms": DCTERMS_NS,
```

Also add `"evidence"` to `PROJECT_ENTITY_PREFIXES` (line 38-45) since evidence entities use this prefix in tests.

**Step 4: Run tests to verify they pass**

Run: `cd science-tool && uv run --frozen pytest tests/test_graph_cli.py::test_cito_prefix_resolves_in_add_edge tests/test_graph_cli.py::test_dcterms_prefix_resolves_in_add_edge -v`
Expected: PASS

**Step 5: Run full test suite**

Run: `cd science-tool && uv run --frozen pytest -v`
Expected: All tests pass

**Step 6: Commit**

```bash
git add science-tool/src/science_tool/graph/store.py science-tool/tests/test_graph_cli.py
git commit -m "feat: add CiTO and dcterms namespace prefixes to CURIE resolver"
```

---

### Task 2: Add --note and --definition flags to `add concept`

**Files:**
- Modify: `science-tool/src/science_tool/graph/store.py:89-103` (add_concept function)
- Modify: `science-tool/src/science_tool/cli.py:337-348` (graph_add_concept command)
- Test: `science-tool/tests/test_graph_cli.py`

**Step 1: Write the failing tests**

Add to `test_graph_cli.py`:

```python
def test_graph_add_concept_with_note_writes_skos_note() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        assert runner.invoke(main, ["graph", "init"]).exit_code == 0

        add = runner.invoke(
            main,
            ["graph", "add", "concept", "DNABERT-2", "--note", "12 layers; max context 2048 nt"],
        )
        assert add.exit_code == 0

        dataset = Dataset()
        dataset.parse(source="knowledge/graph.trig", format="trig")
        knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
        concept_uri = PROJECT_NS["concept/dnabert_2"]
        notes = list(knowledge.objects(concept_uri, SKOS.note))
        assert len(notes) == 1
        assert str(notes[0]) == "12 layers; max context 2048 nt"


def test_graph_add_concept_with_definition_writes_skos_definition() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        assert runner.invoke(main, ["graph", "init"]).exit_code == 0

        add = runner.invoke(
            main,
            ["graph", "add", "concept", "Epistasis", "--definition", "Nonadditive interactions between genetic variants"],
        )
        assert add.exit_code == 0

        dataset = Dataset()
        dataset.parse(source="knowledge/graph.trig", format="trig")
        knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
        concept_uri = PROJECT_NS["concept/epistasis"]
        defs = list(knowledge.objects(concept_uri, SKOS.definition))
        assert len(defs) == 1
        assert "Nonadditive" in str(defs[0])
```

**Step 2: Run tests to verify they fail**

Run: `cd science-tool && uv run --frozen pytest tests/test_graph_cli.py::test_graph_add_concept_with_note_writes_skos_note tests/test_graph_cli.py::test_graph_add_concept_with_definition_writes_skos_definition -v`
Expected: FAIL (no such option: --note / --definition)

**Step 3: Write minimal implementation**

In `store.py`, update `add_concept` signature and body:

```python
def add_concept(
    graph_path: Path,
    label: str,
    concept_type: str | None,
    ontology_id: str | None,
    note: str | None = None,
    definition: str | None = None,
) -> URIRef:
    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))

    concept_uri = URIRef(PROJECT_NS[f"concept/{_slug(label)}"])
    knowledge.add((concept_uri, RDF.type, SCI_NS.Concept))
    knowledge.add((concept_uri, SKOS.prefLabel, Literal(label)))

    if concept_type:
        knowledge.add((concept_uri, RDF.type, _resolve_term(concept_type)))
    if ontology_id:
        knowledge.add((concept_uri, SCHEMA_NS.identifier, Literal(ontology_id)))
    if note:
        knowledge.add((concept_uri, SKOS.note, Literal(note)))
    if definition:
        knowledge.add((concept_uri, SKOS.definition, Literal(definition)))

    _save_dataset(dataset, graph_path)
    return concept_uri
```

In `cli.py`, update `graph_add_concept`:

```python
@graph_add.command("concept")
@click.argument("label")
@click.option("--type", "concept_type", default=None)
@click.option("--ontology-id", default=None)
@click.option("--note", default=None, help="skos:note annotation")
@click.option("--definition", default=None, help="skos:definition annotation")
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def graph_add_concept(
    label: str,
    concept_type: str | None,
    ontology_id: str | None,
    note: str | None,
    definition: str | None,
    graph_path: Path,
) -> None:
    """Add a concept node to the knowledge graph."""

    concept_uri = add_concept(
        graph_path=graph_path, label=label, concept_type=concept_type,
        ontology_id=ontology_id, note=note, definition=definition,
    )
    click.echo(f"Added concept: {concept_uri}")
```

**Step 4: Run tests to verify they pass**

Run: `cd science-tool && uv run --frozen pytest tests/test_graph_cli.py::test_graph_add_concept_with_note_writes_skos_note tests/test_graph_cli.py::test_graph_add_concept_with_definition_writes_skos_definition -v`
Expected: PASS

**Step 5: Run full test suite**

Run: `cd science-tool && uv run --frozen pytest -v`
Expected: All tests pass

**Step 6: Commit**

```bash
git add science-tool/src/science_tool/graph/store.py science-tool/src/science_tool/cli.py science-tool/tests/test_graph_cli.py
git commit -m "feat: add --note and --definition flags to graph add concept"
```

---

### Task 3: Add --property flag to `add concept`

**Files:**
- Modify: `science-tool/src/science_tool/graph/store.py:89-103` (add_concept function)
- Modify: `science-tool/src/science_tool/cli.py:337-348` (graph_add_concept command)
- Test: `science-tool/tests/test_graph_cli.py`

**Step 1: Write the failing tests**

Add to `test_graph_cli.py`:

```python
def test_graph_add_concept_with_property_bare_key_uses_sci_namespace() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        assert runner.invoke(main, ["graph", "init"]).exit_code == 0

        add = runner.invoke(
            main,
            [
                "graph", "add", "concept", "DNABERT-2",
                "--property", "hasArchitecture", "BERT encoder",
                "--property", "hasParameters", "117M",
            ],
        )
        assert add.exit_code == 0

        dataset = Dataset()
        dataset.parse(source="knowledge/graph.trig", format="trig")
        knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
        concept_uri = PROJECT_NS["concept/dnabert_2"]
        assert (concept_uri, SCI["hasArchitecture"], None) in knowledge
        assert (concept_uri, SCI["hasParameters"], None) in knowledge
        arch_vals = [str(o) for o in knowledge.objects(concept_uri, SCI["hasArchitecture"])]
        assert "BERT encoder" in arch_vals


def test_graph_add_concept_with_property_curie_key_resolves_namespace() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        assert runner.invoke(main, ["graph", "init"]).exit_code == 0

        add = runner.invoke(
            main,
            [
                "graph", "add", "concept", "DNABERT-2",
                "--property", "schema:description", "A DNA foundation model",
            ],
        )
        assert add.exit_code == 0

        dataset = Dataset()
        dataset.parse(source="knowledge/graph.trig", format="trig")
        knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
        concept_uri = PROJECT_NS["concept/dnabert_2"]
        assert (concept_uri, SCHEMA["description"], None) in knowledge
```

**Step 2: Run tests to verify they fail**

Run: `cd science-tool && uv run --frozen pytest tests/test_graph_cli.py::test_graph_add_concept_with_property_bare_key_uses_sci_namespace tests/test_graph_cli.py::test_graph_add_concept_with_property_curie_key_resolves_namespace -v`
Expected: FAIL (no such option: --property)

**Step 3: Write minimal implementation**

In `store.py`, update `add_concept` to accept `properties`:

```python
def add_concept(
    graph_path: Path,
    label: str,
    concept_type: str | None,
    ontology_id: str | None,
    note: str | None = None,
    definition: str | None = None,
    properties: list[tuple[str, str]] | None = None,
) -> URIRef:
    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))

    concept_uri = URIRef(PROJECT_NS[f"concept/{_slug(label)}"])
    knowledge.add((concept_uri, RDF.type, SCI_NS.Concept))
    knowledge.add((concept_uri, SKOS.prefLabel, Literal(label)))

    if concept_type:
        knowledge.add((concept_uri, RDF.type, _resolve_term(concept_type)))
    if ontology_id:
        knowledge.add((concept_uri, SCHEMA_NS.identifier, Literal(ontology_id)))
    if note:
        knowledge.add((concept_uri, SKOS.note, Literal(note)))
    if definition:
        knowledge.add((concept_uri, SKOS.definition, Literal(definition)))
    if properties:
        for key, value in properties:
            pred = _resolve_term(key) if ":" in key else SCI_NS[key]
            knowledge.add((concept_uri, pred, Literal(value)))

    _save_dataset(dataset, graph_path)
    return concept_uri
```

In `cli.py`, add the `--property` option. Click's `multiple=True` with `nargs=2` handles repeatable key-value pairs:

```python
@graph_add.command("concept")
@click.argument("label")
@click.option("--type", "concept_type", default=None)
@click.option("--ontology-id", default=None)
@click.option("--note", default=None, help="skos:note annotation")
@click.option("--definition", default=None, help="skos:definition annotation")
@click.option("--property", "properties", type=(str, str), multiple=True, help="KEY VALUE property pair (repeatable)")
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def graph_add_concept(
    label: str,
    concept_type: str | None,
    ontology_id: str | None,
    note: str | None,
    definition: str | None,
    properties: tuple[tuple[str, str], ...],
    graph_path: Path,
) -> None:
    """Add a concept node to the knowledge graph."""

    concept_uri = add_concept(
        graph_path=graph_path, label=label, concept_type=concept_type,
        ontology_id=ontology_id, note=note, definition=definition,
        properties=list(properties) if properties else None,
    )
    click.echo(f"Added concept: {concept_uri}")
```

**Step 4: Run tests to verify they pass**

Run: `cd science-tool && uv run --frozen pytest tests/test_graph_cli.py::test_graph_add_concept_with_property_bare_key_uses_sci_namespace tests/test_graph_cli.py::test_graph_add_concept_with_property_curie_key_resolves_namespace -v`
Expected: PASS

**Step 5: Run full test suite**

Run: `cd science-tool && uv run --frozen pytest -v`
Expected: All tests pass

**Step 6: Commit**

```bash
git add science-tool/src/science_tool/graph/store.py science-tool/src/science_tool/cli.py science-tool/tests/test_graph_cli.py
git commit -m "feat: add --property KEY VALUE repeatable flag to graph add concept"
```

---

### Task 4: Add --status and --source flags to `add concept`

**Files:**
- Modify: `science-tool/src/science_tool/graph/store.py:89-103` (add_concept function)
- Modify: `science-tool/src/science_tool/cli.py:337-348` (graph_add_concept command)
- Test: `science-tool/tests/test_graph_cli.py`

**Step 1: Write the failing tests**

Add to `test_graph_cli.py`:

```python
def test_graph_add_concept_with_status_writes_project_status() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        assert runner.invoke(main, ["graph", "init"]).exit_code == 0

        add = runner.invoke(
            main,
            ["graph", "add", "concept", "DNABERT-2", "--status", "selected-primary"],
        )
        assert add.exit_code == 0

        dataset = Dataset()
        dataset.parse(source="knowledge/graph.trig", format="trig")
        knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
        concept_uri = PROJECT_NS["concept/dnabert_2"]
        statuses = [str(o) for o in knowledge.objects(concept_uri, SCI["projectStatus"])]
        assert "selected-primary" in statuses


def test_graph_add_concept_with_source_writes_provenance() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        assert runner.invoke(main, ["graph", "init"]).exit_code == 0

        add = runner.invoke(
            main,
            ["graph", "add", "concept", "DNABERT-2", "--source", "paper:doi_10_1234_test"],
        )
        assert add.exit_code == 0

        dataset = Dataset()
        dataset.parse(source="knowledge/graph.trig", format="trig")
        provenance = dataset.graph(PROJECT_NS["graph/provenance"])
        concept_uri = PROJECT_NS["concept/dnabert_2"]
        sources = list(provenance.objects(concept_uri, PROV.wasDerivedFrom))
        assert len(sources) == 1
        assert str(sources[0]).endswith("doi_10_1234_test")
```

**Step 2: Run tests to verify they fail**

Run: `cd science-tool && uv run --frozen pytest tests/test_graph_cli.py::test_graph_add_concept_with_status_writes_project_status tests/test_graph_cli.py::test_graph_add_concept_with_source_writes_provenance -v`
Expected: FAIL (no such option: --status / --source)

**Step 3: Write minimal implementation**

In `store.py`, update `add_concept` to accept `status` and `source`:

```python
def add_concept(
    graph_path: Path,
    label: str,
    concept_type: str | None,
    ontology_id: str | None,
    note: str | None = None,
    definition: str | None = None,
    properties: list[tuple[str, str]] | None = None,
    status: str | None = None,
    source: str | None = None,
) -> URIRef:
    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))

    concept_uri = URIRef(PROJECT_NS[f"concept/{_slug(label)}"])
    knowledge.add((concept_uri, RDF.type, SCI_NS.Concept))
    knowledge.add((concept_uri, SKOS.prefLabel, Literal(label)))

    if concept_type:
        knowledge.add((concept_uri, RDF.type, _resolve_term(concept_type)))
    if ontology_id:
        knowledge.add((concept_uri, SCHEMA_NS.identifier, Literal(ontology_id)))
    if note:
        knowledge.add((concept_uri, SKOS.note, Literal(note)))
    if definition:
        knowledge.add((concept_uri, SKOS.definition, Literal(definition)))
    if properties:
        for key, value in properties:
            pred = _resolve_term(key) if ":" in key else SCI_NS[key]
            knowledge.add((concept_uri, pred, Literal(value)))
    if status:
        knowledge.add((concept_uri, SCI_NS.projectStatus, Literal(status)))
    if source:
        provenance = dataset.graph(_graph_uri("graph/provenance"))
        provenance.add((concept_uri, PROV.wasDerivedFrom, _resolve_term(source)))

    _save_dataset(dataset, graph_path)
    return concept_uri
```

In `cli.py`, add `--status` and `--source` options to `graph_add_concept`:

```python
@graph_add.command("concept")
@click.argument("label")
@click.option("--type", "concept_type", default=None)
@click.option("--ontology-id", default=None)
@click.option("--note", default=None, help="skos:note annotation")
@click.option("--definition", default=None, help="skos:definition annotation")
@click.option("--property", "properties", type=(str, str), multiple=True, help="KEY VALUE property pair (repeatable)")
@click.option("--status", default=None, help="Project status (selected-primary, deferred, active, candidate, speculative)")
@click.option("--source", default=None, help="Provenance source reference (paper:doi_... or file path)")
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def graph_add_concept(
    label: str,
    concept_type: str | None,
    ontology_id: str | None,
    note: str | None,
    definition: str | None,
    properties: tuple[tuple[str, str], ...],
    status: str | None,
    source: str | None,
    graph_path: Path,
) -> None:
    """Add a concept node to the knowledge graph."""

    concept_uri = add_concept(
        graph_path=graph_path, label=label, concept_type=concept_type,
        ontology_id=ontology_id, note=note, definition=definition,
        properties=list(properties) if properties else None,
        status=status, source=source,
    )
    click.echo(f"Added concept: {concept_uri}")
```

**Step 4: Run tests to verify they pass**

Run: `cd science-tool && uv run --frozen pytest tests/test_graph_cli.py::test_graph_add_concept_with_status_writes_project_status tests/test_graph_cli.py::test_graph_add_concept_with_source_writes_provenance -v`
Expected: PASS

**Step 5: Run full test suite**

Run: `cd science-tool && uv run --frozen pytest -v`
Expected: All tests pass

**Step 6: Commit**

```bash
git add science-tool/src/science_tool/graph/store.py science-tool/src/science_tool/cli.py science-tool/tests/test_graph_cli.py
git commit -m "feat: add --status and --source flags to graph add concept"
```

---

### Task 5: Add --status flag to `add hypothesis`

**Files:**
- Modify: `science-tool/src/science_tool/graph/store.py:149-162` (add_hypothesis function)
- Modify: `science-tool/src/science_tool/cli.py:390-402` (graph_add_hypothesis command)
- Test: `science-tool/tests/test_graph_cli.py`

**Step 1: Write the failing test**

Add to `test_graph_cli.py`:

```python
def test_graph_add_hypothesis_with_status_writes_project_status() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        assert runner.invoke(main, ["graph", "init"]).exit_code == 0

        add = runner.invoke(
            main,
            [
                "graph", "add", "hypothesis", "H1",
                "--text", "Test hypothesis",
                "--source", "paper:doi_10_1111_a",
                "--status", "active",
            ],
        )
        assert add.exit_code == 0

        dataset = Dataset()
        dataset.parse(source="knowledge/graph.trig", format="trig")
        knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
        hyp_uri = PROJECT_NS["hypothesis/h1"]
        statuses = [str(o) for o in knowledge.objects(hyp_uri, SCI["projectStatus"])]
        assert "active" in statuses
```

**Step 2: Run test to verify it fails**

Run: `cd science-tool && uv run --frozen pytest tests/test_graph_cli.py::test_graph_add_hypothesis_with_status_writes_project_status -v`
Expected: FAIL (no such option: --status)

**Step 3: Write minimal implementation**

In `store.py`, update `add_hypothesis`:

```python
def add_hypothesis(graph_path: Path, hypothesis_id: str, text: str, source: str, status: str | None = None) -> URIRef:
    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))
    provenance = dataset.graph(_graph_uri("graph/provenance"))

    hypothesis_uri = URIRef(PROJECT_NS[f"hypothesis/{hypothesis_id.lower()}"])
    knowledge.add((hypothesis_uri, RDF.type, SCI_NS.Hypothesis))
    knowledge.add((hypothesis_uri, SCHEMA_NS.identifier, Literal(hypothesis_id)))
    knowledge.add((hypothesis_uri, SCHEMA_NS.text, Literal(text)))

    if status:
        knowledge.add((hypothesis_uri, SCI_NS.projectStatus, Literal(status)))

    provenance.add((hypothesis_uri, PROV.wasDerivedFrom, _resolve_term(source)))

    _save_dataset(dataset, graph_path)
    return hypothesis_uri
```

In `cli.py`, update `graph_add_hypothesis`:

```python
@graph_add.command("hypothesis")
@click.argument("hypothesis_id")
@click.option("--text", required=True)
@click.option("--source", required=True)
@click.option("--status", default=None, help="Project status (active, deferred, speculative)")
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def graph_add_hypothesis(hypothesis_id: str, text: str, source: str, status: str | None, graph_path: Path) -> None:
    """Add a hypothesis with provenance."""

    hypothesis_uri = add_hypothesis(
        graph_path=graph_path, hypothesis_id=hypothesis_id, text=text, source=source, status=status,
    )
    click.echo(f"Added hypothesis: {hypothesis_uri}")
```

**Step 4: Run test to verify it passes**

Run: `cd science-tool && uv run --frozen pytest tests/test_graph_cli.py::test_graph_add_hypothesis_with_status_writes_project_status -v`
Expected: PASS

**Step 5: Run full test suite**

Run: `cd science-tool && uv run --frozen pytest -v`
Expected: All tests pass

**Step 6: Commit**

```bash
git add science-tool/src/science_tool/graph/store.py science-tool/src/science_tool/cli.py science-tool/tests/test_graph_cli.py
git commit -m "feat: add --status flag to graph add hypothesis"
```

---

### Task 6: Add `add question` command

**Files:**
- Modify: `science-tool/src/science_tool/graph/store.py` (new add_question function)
- Modify: `science-tool/src/science_tool/graph/__init__.py` (export add_question)
- Modify: `science-tool/src/science_tool/cli.py` (new graph_add_question command)
- Test: `science-tool/tests/test_graph_cli.py`

**Step 1: Write the failing tests**

Add to `test_graph_cli.py`:

```python
def test_graph_add_question_creates_entity_with_provenance() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        assert runner.invoke(main, ["graph", "init"]).exit_code == 0

        add = runner.invoke(
            main,
            [
                "graph", "add", "question", "Q01",
                "--text", "Which tokenization strategy best preserves biological signals?",
                "--source", "paper:doi_10_1111_a",
            ],
        )
        assert add.exit_code == 0

        dataset = Dataset()
        dataset.parse(source="knowledge/graph.trig", format="trig")
        knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
        provenance = dataset.graph(PROJECT_NS["graph/provenance"])
        q_uri = PROJECT_NS["question/q01"]

        assert (q_uri, RDF.type, SCI["Question"]) in knowledge
        assert (q_uri, SCHEMA["text"], None) in knowledge
        assert (q_uri, SCHEMA["identifier"], None) in knowledge
        assert any(provenance.triples((q_uri, PROV.wasDerivedFrom, None)))

        # Default maturity is "open"
        maturity_vals = [str(o) for o in knowledge.objects(q_uri, SCI["maturity"])]
        assert "open" in maturity_vals


def test_graph_add_question_with_maturity_and_related_hypothesis() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        assert runner.invoke(main, ["graph", "init"]).exit_code == 0
        assert runner.invoke(
            main,
            ["graph", "add", "hypothesis", "H1", "--text", "Test hyp", "--source", "paper:doi_10_1111_a"],
        ).exit_code == 0

        add = runner.invoke(
            main,
            [
                "graph", "add", "question", "Q05",
                "--text", "How should models be selected?",
                "--source", "paper:doi_10_2222_b",
                "--maturity", "partially-resolved",
                "--related-hypothesis", "hypothesis/h1",
            ],
        )
        assert add.exit_code == 0

        dataset = Dataset()
        dataset.parse(source="knowledge/graph.trig", format="trig")
        knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
        q_uri = PROJECT_NS["question/q05"]

        maturity_vals = [str(o) for o in knowledge.objects(q_uri, SCI["maturity"])]
        assert "partially-resolved" in maturity_vals

        # Check skos:related edge to hypothesis
        related = [str(o) for o in knowledge.objects(q_uri, SKOS.related)]
        assert any("hypothesis/h1" in r for r in related)
```

**Step 2: Run tests to verify they fail**

Run: `cd science-tool && uv run --frozen pytest tests/test_graph_cli.py::test_graph_add_question_creates_entity_with_provenance tests/test_graph_cli.py::test_graph_add_question_with_maturity_and_related_hypothesis -v`
Expected: FAIL (no such command "question")

**Step 3: Write minimal implementation**

In `store.py`, add after `add_hypothesis`:

```python
def add_question(
    graph_path: Path,
    question_id: str,
    text: str,
    source: str,
    maturity: str = "open",
    related_hypotheses: list[str] | None = None,
) -> URIRef:
    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))
    provenance = dataset.graph(_graph_uri("graph/provenance"))

    question_uri = URIRef(PROJECT_NS[f"question/{question_id.lower()}"])
    knowledge.add((question_uri, RDF.type, SCI_NS.Question))
    knowledge.add((question_uri, SCHEMA_NS.identifier, Literal(question_id)))
    knowledge.add((question_uri, SCHEMA_NS.text, Literal(text)))
    knowledge.add((question_uri, SCI_NS.maturity, Literal(maturity)))

    provenance.add((question_uri, PROV.wasDerivedFrom, _resolve_term(source)))

    if related_hypotheses:
        for hyp_ref in related_hypotheses:
            knowledge.add((question_uri, SKOS.related, _resolve_term(hyp_ref)))

    _save_dataset(dataset, graph_path)
    return question_uri
```

In `graph/__init__.py`, add `add_question` to the import and `__all__`.

In `cli.py`, add import of `add_question` and the new command:

```python
@graph_add.command("question")
@click.argument("question_id")
@click.option("--text", required=True)
@click.option("--source", required=True)
@click.option("--maturity", default="open", show_default=True,
              type=click.Choice(("open", "partially-resolved", "resolved")))
@click.option("--related-hypothesis", "related_hypotheses", multiple=True,
              help="Hypothesis reference (repeatable)")
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def graph_add_question(
    question_id: str,
    text: str,
    source: str,
    maturity: str,
    related_hypotheses: tuple[str, ...],
    graph_path: Path,
) -> None:
    """Add an open question with provenance."""

    question_uri = add_question(
        graph_path=graph_path,
        question_id=question_id,
        text=text,
        source=source,
        maturity=maturity,
        related_hypotheses=list(related_hypotheses) if related_hypotheses else None,
    )
    click.echo(f"Added question: {question_uri}")
```

**Step 4: Run tests to verify they pass**

Run: `cd science-tool && uv run --frozen pytest tests/test_graph_cli.py::test_graph_add_question_creates_entity_with_provenance tests/test_graph_cli.py::test_graph_add_question_with_maturity_and_related_hypothesis -v`
Expected: PASS

**Step 5: Run full test suite**

Run: `cd science-tool && uv run --frozen pytest -v`
Expected: All tests pass

**Step 6: Commit**

```bash
git add science-tool/src/science_tool/graph/store.py science-tool/src/science_tool/graph/__init__.py science-tool/src/science_tool/cli.py science-tool/tests/test_graph_cli.py
git commit -m "feat: add graph add question command with maturity and hypothesis links"
```

---

### Task 7: Add `graph predicates` command

**Files:**
- Modify: `science-tool/src/science_tool/graph/store.py` (new query_predicates function)
- Modify: `science-tool/src/science_tool/graph/__init__.py` (export query_predicates)
- Modify: `science-tool/src/science_tool/cli.py` (new graph_predicates command)
- Test: `science-tool/tests/test_graph_cli.py`

**Step 1: Write the failing tests**

Add to `test_graph_cli.py`:

```python
def test_graph_predicates_outputs_table() -> None:
    runner = CliRunner()

    result = runner.invoke(main, ["graph", "predicates"])
    assert result.exit_code == 0
    assert "cito:supports" in result.output
    assert "skos:related" in result.output
    assert "sci:projectStatus" in result.output


def test_graph_predicates_outputs_json() -> None:
    runner = CliRunner()

    result = runner.invoke(main, ["graph", "predicates", "--format", "json"])
    assert result.exit_code == 0

    payload = json.loads(result.output)
    assert isinstance(payload["rows"], list)
    assert len(payload["rows"]) > 10
    predicates = {row["predicate"] for row in payload["rows"]}
    assert "cito:supports" in predicates
    assert "skos:related" in predicates
    assert "scic:causes" in predicates
```

**Step 2: Run tests to verify they fail**

Run: `cd science-tool && uv run --frozen pytest tests/test_graph_cli.py::test_graph_predicates_outputs_table tests/test_graph_cli.py::test_graph_predicates_outputs_json -v`
Expected: FAIL (no such command "predicates")

**Step 3: Write minimal implementation**

In `store.py`, add a constant and function:

```python
PREDICATE_REGISTRY: list[dict[str, str]] = [
    {"predicate": "skos:related", "description": "General association between concepts", "layer": "graph/knowledge"},
    {"predicate": "skos:broader", "description": "Broader concept hierarchy", "layer": "graph/knowledge"},
    {"predicate": "skos:narrower", "description": "Narrower concept hierarchy", "layer": "graph/knowledge"},
    {"predicate": "cito:supports", "description": "Evidence supports a claim/hypothesis", "layer": "graph/knowledge"},
    {"predicate": "cito:disputes", "description": "Evidence disputes a claim/hypothesis", "layer": "graph/knowledge"},
    {"predicate": "cito:discusses", "description": "Paper discusses a topic", "layer": "graph/knowledge"},
    {"predicate": "cito:extends", "description": "Work extends prior research", "layer": "graph/knowledge"},
    {"predicate": "cito:usesMethodIn", "description": "Uses method from another work", "layer": "graph/knowledge"},
    {"predicate": "cito:citesAsDataSource", "description": "Cites as data source", "layer": "graph/knowledge"},
    {"predicate": "sci:evaluates", "description": "Benchmark evaluates model/method", "layer": "graph/knowledge"},
    {"predicate": "sci:hasModality", "description": "Model/method operates on modality", "layer": "graph/knowledge"},
    {"predicate": "sci:detectedBy", "description": "Feature detected by method/tool", "layer": "graph/knowledge"},
    {"predicate": "sci:storedIn", "description": "Data stored in database/repository", "layer": "graph/knowledge"},
    {"predicate": "sci:measuredBy", "description": "Variable measured by dataset", "layer": "graph/datasets"},
    {"predicate": "sci:projectStatus", "description": "Project status of entity", "layer": "graph/knowledge"},
    {"predicate": "sci:confidence", "description": "Confidence score (0.0-1.0)", "layer": "graph/provenance"},
    {"predicate": "sci:epistemicStatus", "description": "Epistemic status of claim", "layer": "graph/provenance"},
    {"predicate": "sci:maturity", "description": "Maturity of open question", "layer": "graph/knowledge"},
    {"predicate": "scic:causes", "description": "Causal relationship", "layer": "graph/causal"},
    {"predicate": "scic:confounds", "description": "Confounding relationship", "layer": "graph/causal"},
    {"predicate": "prov:wasDerivedFrom", "description": "Provenance source", "layer": "graph/provenance"},
]


def query_predicates() -> list[dict[str, str]]:
    return list(PREDICATE_REGISTRY)
```

In `graph/__init__.py`, add `query_predicates` and `PREDICATE_REGISTRY` to import and `__all__`.

In `cli.py`, add the command (does not need `--path` since it's static data):

```python
@graph.command("predicates")
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
def graph_predicates(output_format: str) -> None:
    """List all supported predicates with descriptions and typical graph layers."""

    from science_tool.graph.store import query_predicates

    rows = query_predicates()
    emit_query_rows(
        output_format=output_format,
        title="Supported Predicates",
        columns=[("predicate", "Predicate"), ("description", "Description"), ("layer", "Layer")],
        rows=rows,
    )
```

**Step 4: Run tests to verify they pass**

Run: `cd science-tool && uv run --frozen pytest tests/test_graph_cli.py::test_graph_predicates_outputs_table tests/test_graph_cli.py::test_graph_predicates_outputs_json -v`
Expected: PASS

**Step 5: Run full test suite**

Run: `cd science-tool && uv run --frozen pytest -v`
Expected: All tests pass

**Step 6: Commit**

```bash
git add science-tool/src/science_tool/graph/store.py science-tool/src/science_tool/graph/__init__.py science-tool/src/science_tool/cli.py science-tool/tests/test_graph_cli.py
git commit -m "feat: add graph predicates command listing supported predicates"
```

---

### Task 8: Update knowledge-graph skill reference

**Files:**
- Modify: `.claude-plugin/skills/knowledge-graph/SKILL.md`

**Step 1: Rewrite the skill file**

Replace the content of `.claude-plugin/skills/knowledge-graph/SKILL.md` with the updated version incorporating:

1. Updated entity types table with `Question` row
2. Updated CURIE conventions with `cito:` and `dcterms:` prefixes
3. Updated relation selection guide with CiTO predicates replacing `sci:supports`/`sci:refutes`
4. New "Entity Properties" section documenting `--note`, `--definition`, `--property`, `--status`, `--source`
5. New "Preferred Predicates" guide: when to use `cito:` vs `skos:` vs `sci:`
6. `skos:related` replaces `sci:relatedTo` in the relation guide

Full replacement content:

```markdown
---
name: knowledge-graph
description: Reference guide for the science knowledge graph ontology, entity types, CURIE conventions, and provenance patterns. This skill is loaded by create-graph and update-graph as background context.
---

# Knowledge Graph Ontology Reference

## Entity Types

| Entity | CLI Command | When to use |
|--------|-------------|-------------|
| Concept | `graph add concept "<label>" --type <type> [flags]` | Any topic, gene, disease, drug, pathway, process, model, method, tool |
| Paper | `graph add paper --doi "<DOI>"` | Published papers referenced in prose |
| Claim | `graph add claim "<text>" --source <ref> --confidence <0-1>` | Factual assertions from literature |
| Hypothesis | `graph add hypothesis <ID> --text "<text>" --source <ref>` | Falsifiable claims under investigation |
| Question | `graph add question <ID> --text "<text>" --source <ref>` | Open research questions |
| Edge | `graph add edge <subj> <pred> <obj> --graph <layer>` | Any relation between entities |

## Entity Properties

Concepts support rich metadata beyond label and type:

```bash
graph add concept "DNABERT-2 117M" \
  --type biolink:GeneticModel \
  --ontology-id "DNABERT2" \
  --note "12 layers; max context 2048 nt" \
  --definition "BPE-tokenized DNA foundation model" \
  --status selected-primary \
  --source paper:doi_10_1234_test \
  --property hasArchitecture "BERT encoder" \
  --property hasParameters "117M" \
  --property hasEmbeddingDim "768" \
  --property hasTokenization "BPE"
```

| Flag | Predicate | Notes |
|------|-----------|-------|
| `--note TEXT` | `skos:note` | Freeform annotation |
| `--definition TEXT` | `skos:definition` | Formal definition |
| `--status STATUS` | `sci:projectStatus` | `selected-primary`, `deferred`, `active`, `candidate`, `speculative` |
| `--source REF` | `prov:wasDerivedFrom` | Provenance link (in provenance layer) |
| `--property KEY VALUE` | `sci:KEY` or resolved CURIE | Repeatable; bare key defaults to `sci:` namespace |

## CURIE Conventions

Prefix format: `prefix:localname`. Supported prefixes:

| Prefix | Namespace | Example |
|--------|-----------|---------|
| `sci:` | Science vocab | `sci:evaluates`, `sci:Concept`, `sci:Claim` |
| `scic:` | Causal vocab | `scic:causes`, `scic:Variable` |
| `cito:` | Citation Typing Ontology | `cito:supports`, `cito:disputes`, `cito:discusses` |
| `dcterms:` | Dublin Core Terms | `dcterms:identifier`, `dcterms:description` |
| `biolink:` | Biolink Model | `biolink:Gene`, `biolink:Disease` |
| `schema:` | schema.org | `schema:author`, `schema:identifier` |
| `skos:` | SKOS | `skos:broader`, `skos:narrower`, `skos:related` |
| `prov:` | PROV-O | `prov:wasDerivedFrom` |
| `rdf:` | RDF | `rdf:type` |

Project entity references: `paper:<slug>`, `concept:<slug>`, `claim:<slug>`, `hypothesis:<id>`, `question:<id>`, `dataset:<slug>`.

## Ontology Alignment Guidelines

1. **Always provide ontology IDs** for well-known entities (genes, diseases, drugs, pathways).
2. **Use Biolink types** for biomedical entities: `biolink:Gene`, `biolink:Disease`, `biolink:Drug`, `biolink:Pathway`, `biolink:BiologicalProcess`, `biolink:Phenotype`.
3. **Use `sci:Concept`** as the base type for all concepts; add domain-specific types as additional `rdf:type` values.
4. **Slugify labels** for entity URIs: lowercase, replace non-alphanumeric with `_`.

## Provenance Rules

- Every `sci:Claim` **must** have a `--source` pointing to a paper or document reference.
- Every `sci:Hypothesis` **must** have a `--source`.
- Every `sci:Question` **must** have a `--source`.
- Use `--confidence` (0.0-1.0) for claims where strength of evidence varies.
- Epistemic status values: `established`, `hypothesized`, `disputed`, `retracted`.
- Concepts **should** have `--source` when the source document is known.

## Preferred Predicates

Use standard predicates over custom ones where they exist:

| Use case | Preferred | Avoid |
|----------|-----------|-------|
| General association | `skos:related` | `sci:relatedTo` |
| Evidence supports claim | `cito:supports` | `sci:supports` |
| Evidence disputes claim | `cito:disputes` | `sci:refutes` |
| Paper discusses topic | `cito:discusses` | `sci:addresses` |
| Extends prior work | `cito:extends` | (none) |
| Uses method from work | `cito:usesMethodIn` | (none) |
| Cites as data source | `cito:citesAsDataSource` | (none) |

Keep `sci:` for domain-specific predicates: `sci:evaluates`, `sci:hasModality`, `sci:detectedBy`, `sci:storedIn`, `sci:measuredBy`, `sci:projectStatus`, `sci:confidence`, `sci:epistemicStatus`, `sci:maturity`.

Run `graph predicates` to see all supported predicates with descriptions.

## Relation Selection Guide

| Relationship | Predicate | Graph Layer |
|-------------|-----------|-------------|
| General association | `skos:related` | `graph/knowledge` |
| Hierarchy | `skos:broader` / `skos:narrower` | `graph/knowledge` |
| Evidence supports claim | `cito:supports` | `graph/knowledge` |
| Evidence disputes claim | `cito:disputes` | `graph/knowledge` |
| Paper discusses topic | `cito:discusses` | `graph/knowledge` |
| Extends prior work | `cito:extends` | `graph/knowledge` |
| Benchmark evaluates model | `sci:evaluates` | `graph/knowledge` |
| Model operates on modality | `sci:hasModality` | `graph/knowledge` |
| Feature detected by method | `sci:detectedBy` | `graph/knowledge` |
| Data stored in repository | `sci:storedIn` | `graph/knowledge` |
| Variable measured by dataset | `sci:measuredBy` | `graph/datasets` |
| Causal effect | `scic:causes` | `graph/causal` |
| Confounding | `scic:confounds` | `graph/causal` |

## Prose Annotation Format

**Frontmatter** -- add to research documents:

\`\`\`yaml
---
ontology_terms:
  - "biolink:Gene"
  - "NCBIGene:672"      # BRCA1
  - "MONDO:0016419"     # breast cancer
---
\`\`\`

**Inline** -- annotate key terms on first mention:

\`\`\`markdown
BRCA1 [`NCBIGene:672`] is a tumor suppressor gene associated with
breast cancer [`MONDO:0016419`].
\`\`\`

Rules:
- Annotate each entity on **first mention only**.
- Use the format: `term [\`CURIE\`]`.
- CURIEs should match ontology IDs used in `graph add concept --ontology-id`.
```

**Step 2: Commit**

```bash
git add .claude-plugin/skills/knowledge-graph/SKILL.md
git commit -m "docs: update knowledge-graph skill with CiTO predicates, entity properties, and question support"
```

---

### Task 9: Update create-graph command

**Files:**
- Modify: `commands/create-graph.md`

**Step 1: Update the command file**

Add the following changes to `commands/create-graph.md`:

1. In Step 3, after item 4 ("Identify claims"), add entity richness guidance:

```markdown
5. **Capture entity properties** using `--note`, `--property`, `--status`, and `--source` flags:
   - Add `--note` for contextual information (parameters, architecture, status notes)
   - Add `--property KEY VALUE` for structured metadata (hasArchitecture, hasParameters, hasTokenization, hasEmbeddingDim)
   - Add `--status` for project relevance (selected-primary, deferred, active, candidate, speculative)
   - Add `--source` for provenance on concepts, not just claims
```

2. After Step 3, add a new Step 3.5 for questions:

```markdown
### Step 3.5: Extract open questions

For each open question identified in prose:

1. **Add to graph**: `science-tool graph add question <ID> --text "<question>" --source <ref>`
2. Use `--maturity open|partially-resolved|resolved` to indicate resolution status.
3. Use `--related-hypothesis <hyp_ref>` to link questions to relevant hypotheses.
4. Number questions sequentially (Q01, Q02, ...).
```

3. Update Step 4 (Entity extraction checklist) to include new fields:

```markdown
- [ ] **Properties**: structured metadata (architecture, parameters, dimensions)
- [ ] **Note**: freeform contextual annotations
- [ ] **Status**: project relevance (selected-primary, deferred, active)
- [ ] **Source**: provenance document reference
```

4. After the "Important Notes" section, add deferred entities guidance:

```markdown
- **Track deferred entities.** If an entity is identified but peripheral to current work, add it to `knowledge/deferred-entities.md` with a brief description rather than cluttering the graph. Add to the graph later when it becomes relevant.
```

5. Update relation references: change `sci:relatedTo` to `skos:related`, `sci:supports` to `cito:supports`, `sci:refutes` to `cito:disputes`.

**Step 2: Commit**

```bash
git add commands/create-graph.md
git commit -m "docs: update create-graph command with entity properties, questions, and CiTO predicates"
```

---

### Task 10: Lint, type-check, and final test run

**Files:**
- All modified Python files

**Step 1: Run ruff check**

Run: `cd science-tool && uv run --frozen ruff check .`
Expected: No errors

**Step 2: Run ruff format**

Run: `cd science-tool && uv run --frozen ruff format .`
Expected: No changes (or format applied)

**Step 3: Run pyright**

Run: `cd science-tool && uv run --frozen pyright`
Expected: No errors

**Step 4: Run full test suite**

Run: `cd science-tool && uv run --frozen pytest -v`
Expected: All tests pass

**Step 5: Commit any formatting fixes**

```bash
git add -u
git commit -m "chore: fix lint and formatting"
```

(Skip if no changes.)

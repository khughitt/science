# Slice B: Graph Authoring — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enable agent-driven graph construction from prose documents, with a prose scanner CLI helper, revision stamping, and three plugin skills that guide the agent through create-graph and update-graph workflows.

**Architecture:** Three `.claude-plugin/skills/` markdown files define the agent workflows. A new `prose.py` module in `science-tool` provides a `graph scan-prose` CLI command that parses frontmatter `ontology_terms:` and inline `[CURIE]` annotations from markdown. A `graph stamp-revision` CLI command lets skills trigger revision metadata updates independently of entity writes. The skills orchestrate existing `graph add`, `graph diff`, `graph validate` commands.

**Tech Stack:** Python (click, rdflib, pyyaml for frontmatter parsing), markdown skill files

---

### Task 1: Add `pyyaml` dependency

**Files:**
- Modify: `science-tool/pyproject.toml`

**Step 1: Add pyyaml to project dependencies**

In `science-tool/pyproject.toml`, add `"pyyaml>=6.0"` to the `dependencies` list:

```toml
dependencies = [
  "click>=8.1",
  "rich>=13.0",
  "rdflib>=7.0",
  "pyyaml>=6.0",
]
```

**Step 2: Sync the environment**

Run: `cd science-tool && uv sync`
Expected: resolves and installs pyyaml

**Step 3: Commit**

```bash
git add science-tool/pyproject.toml science-tool/uv.lock
git commit -m "chore: add pyyaml dependency for prose frontmatter parsing"
```

---

### Task 2: Implement `scan_prose` in `prose.py`

**Files:**
- Create: `science-tool/src/science_tool/prose.py`
- Test: `science-tool/tests/test_prose.py`

**Step 1: Write the failing tests**

Create `science-tool/tests/test_prose.py`:

```python
from pathlib import Path

from science_tool.prose import scan_prose


def test_scan_prose_extracts_frontmatter_ontology_terms(tmp_path: Path) -> None:
    doc = tmp_path / "doc.md"
    doc.write_text(
        '---\nontology_terms:\n  - "biolink:Gene"\n  - "NCBIGene:672"\n---\n\nSome text.\n',
        encoding="utf-8",
    )

    result = scan_prose(tmp_path)

    assert len(result) == 1
    assert result[0]["path"] == "doc.md"
    assert result[0]["frontmatter_terms"] == ["biolink:Gene", "NCBIGene:672"]


def test_scan_prose_extracts_inline_curie_annotations(tmp_path: Path) -> None:
    doc = tmp_path / "doc.md"
    doc.write_text(
        "BRCA1 [`NCBIGene:672`] is a tumor suppressor gene associated with\n"
        "breast cancer [`MONDO:0016419`].\n",
        encoding="utf-8",
    )

    result = scan_prose(tmp_path)

    assert len(result) == 1
    annotations = result[0]["inline_annotations"]
    assert len(annotations) == 2
    assert annotations[0] == {"term": "BRCA1", "curie": "NCBIGene:672", "line": 1}
    assert annotations[1] == {"term": "breast cancer", "curie": "MONDO:0016419", "line": 2}


def test_scan_prose_handles_both_frontmatter_and_inline(tmp_path: Path) -> None:
    doc = tmp_path / "doc.md"
    doc.write_text(
        '---\nontology_terms:\n  - "biolink:Gene"\n---\n\nBRCA1 [`NCBIGene:672`] is important.\n',
        encoding="utf-8",
    )

    result = scan_prose(tmp_path)

    assert len(result) == 1
    assert result[0]["frontmatter_terms"] == ["biolink:Gene"]
    assert len(result[0]["inline_annotations"]) == 1


def test_scan_prose_skips_files_without_annotations(tmp_path: Path) -> None:
    doc = tmp_path / "plain.md"
    doc.write_text("Just plain text without any annotations.\n", encoding="utf-8")

    result = scan_prose(tmp_path)

    assert len(result) == 0


def test_scan_prose_recurses_into_subdirectories(tmp_path: Path) -> None:
    subdir = tmp_path / "sub"
    subdir.mkdir()
    doc = subdir / "nested.md"
    doc.write_text(
        '---\nontology_terms:\n  - "MONDO:0016419"\n---\n\nNested doc.\n',
        encoding="utf-8",
    )

    result = scan_prose(tmp_path)

    assert len(result) == 1
    assert result[0]["path"] == "sub/nested.md"


def test_scan_prose_ignores_non_markdown_files(tmp_path: Path) -> None:
    txt = tmp_path / "notes.txt"
    txt.write_text('---\nontology_terms:\n  - "biolink:Gene"\n---\n', encoding="utf-8")

    result = scan_prose(tmp_path)

    assert len(result) == 0


def test_scan_prose_empty_frontmatter_terms_not_reported(tmp_path: Path) -> None:
    doc = tmp_path / "doc.md"
    doc.write_text("---\nontology_terms: []\n---\n\nNo annotations.\n", encoding="utf-8")

    result = scan_prose(tmp_path)

    assert len(result) == 0
```

**Step 2: Run tests to verify they fail**

Run: `cd science-tool && uv run --frozen pytest tests/test_prose.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'science_tool.prose'`

**Step 3: Implement `prose.py`**

Create `science-tool/src/science_tool/prose.py`:

```python
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

# Pattern: `term [`CURIE`]` — captures the preceding word(s) and the CURIE
# The term is one or more words before the backtick-bracket annotation
_INLINE_CURIE_RE = re.compile(r"([\w][\w\s\-]*?)\s+\[`([A-Za-z][\w\-]*:[^\]`]+)`\]")


def scan_prose(root: Path) -> list[dict[str, Any]]:
    """Scan markdown files under *root* for ontology annotations.

    Returns a list of file records, each containing:
    - path: relative path from root
    - frontmatter_terms: list of CURIE strings from YAML frontmatter ``ontology_terms``
    - inline_annotations: list of {term, curie, line} dicts
    """
    results: list[dict[str, Any]] = []

    for md_path in sorted(root.rglob("*.md")):
        text = md_path.read_text(encoding="utf-8")
        frontmatter_terms = _extract_frontmatter_terms(text)
        inline_annotations = _extract_inline_annotations(text)

        if not frontmatter_terms and not inline_annotations:
            continue

        results.append(
            {
                "path": md_path.relative_to(root).as_posix(),
                "frontmatter_terms": frontmatter_terms,
                "inline_annotations": inline_annotations,
            }
        )

    return results


def _extract_frontmatter_terms(text: str) -> list[str]:
    """Extract ontology_terms from YAML frontmatter delimited by ``---``."""
    if not text.startswith("---"):
        return []

    end = text.find("---", 3)
    if end == -1:
        return []

    frontmatter_text = text[3:end]
    try:
        data = yaml.safe_load(frontmatter_text)
    except yaml.YAMLError:
        return []

    if not isinstance(data, dict):
        return []

    terms = data.get("ontology_terms", [])
    if not isinstance(terms, list):
        return []

    return [str(t) for t in terms if t]


def _extract_inline_annotations(text: str) -> list[dict[str, str | int]]:
    """Extract inline ``term [`CURIE`]`` annotations with line numbers."""
    annotations: list[dict[str, str | int]] = []

    for line_num, line in enumerate(text.splitlines(), start=1):
        for match in _INLINE_CURIE_RE.finditer(line):
            term = match.group(1).strip()
            curie = match.group(2)
            annotations.append({"term": term, "curie": curie, "line": line_num})

    return annotations
```

**Step 4: Run tests to verify they pass**

Run: `cd science-tool && uv run --frozen pytest tests/test_prose.py -v`
Expected: all 7 tests PASS

**Step 5: Run linters**

Run: `cd science-tool && uv run --frozen ruff check src/science_tool/prose.py tests/test_prose.py && uv run --frozen pyright src/science_tool/prose.py`
Expected: clean

**Step 6: Commit**

```bash
git add science-tool/src/science_tool/prose.py science-tool/tests/test_prose.py
git commit -m "feat: add prose scanner for ontology annotations (frontmatter + inline CURIEs)"
```

---

### Task 3: Add `graph scan-prose` CLI command

**Files:**
- Modify: `science-tool/src/science_tool/cli.py`
- Test: `science-tool/tests/test_graph_cli.py`

**Step 1: Write the failing test**

Append to `science-tool/tests/test_graph_cli.py`:

```python
def test_graph_scan_prose_returns_annotations_json() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        doc_dir = Path("doc")
        doc_dir.mkdir()
        (doc_dir / "01-overview.md").write_text(
            '---\nontology_terms:\n  - "biolink:Gene"\n---\n\nBRCA1 [`NCBIGene:672`] is important.\n',
            encoding="utf-8",
        )

        result = runner.invoke(main, ["graph", "scan-prose", "doc", "--format", "json"])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert len(payload["rows"]) == 1
        assert payload["rows"][0]["frontmatter_terms"] == "biolink:Gene"
        assert "NCBIGene:672" in payload["rows"][0]["inline_annotations"]


def test_graph_scan_prose_returns_empty_for_unannotated_dir() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        doc_dir = Path("doc")
        doc_dir.mkdir()
        (doc_dir / "plain.md").write_text("No annotations here.\n", encoding="utf-8")

        result = runner.invoke(main, ["graph", "scan-prose", "doc", "--format", "json"])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert len(payload["rows"]) == 0
```

**Step 2: Run tests to verify they fail**

Run: `cd science-tool && uv run --frozen pytest tests/test_graph_cli.py::test_graph_scan_prose_returns_annotations_json -v`
Expected: FAIL — `No such command 'scan-prose'`

**Step 3: Add the CLI command**

In `science-tool/src/science_tool/cli.py`, add the import at the top:

```python
from science_tool.prose import scan_prose
```

Then add the command after the existing `graph import` command:

```python
@graph.command("scan-prose")
@click.argument("directory", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
def graph_scan_prose(directory: Path, output_format: str) -> None:
    """Scan markdown files for ontology annotations (frontmatter + inline CURIEs)."""

    file_results = scan_prose(directory)
    rows: list[dict[str, str]] = []
    for entry in file_results:
        rows.append(
            {
                "path": entry["path"],
                "frontmatter_terms": "; ".join(entry["frontmatter_terms"]),
                "inline_annotations": "; ".join(
                    f"{a['term']} [{a['curie']}]" for a in entry["inline_annotations"]
                ),
            }
        )

    emit_query_rows(
        output_format=output_format,
        title="Prose Annotations",
        columns=[
            ("path", "Path"),
            ("frontmatter_terms", "Frontmatter Terms"),
            ("inline_annotations", "Inline Annotations"),
        ],
        rows=rows,
    )
```

**Step 4: Run tests to verify they pass**

Run: `cd science-tool && uv run --frozen pytest tests/test_graph_cli.py::test_graph_scan_prose_returns_annotations_json tests/test_graph_cli.py::test_graph_scan_prose_returns_empty_for_unannotated_dir -v`
Expected: PASS

**Step 5: Commit**

```bash
git add science-tool/src/science_tool/cli.py science-tool/tests/test_graph_cli.py
git commit -m "feat: add graph scan-prose CLI command"
```

---

### Task 4: Add `graph stamp-revision` CLI command

**Files:**
- Modify: `science-tool/src/science_tool/graph/store.py`
- Modify: `science-tool/src/science_tool/cli.py`
- Test: `science-tool/tests/test_graph_cli.py`

**Step 1: Write the failing test**

Append to `science-tool/tests/test_graph_cli.py`:

```python
def test_graph_stamp_revision_updates_revision_metadata() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        assert runner.invoke(main, ["graph", "init"]).exit_code == 0

        doc_dir = Path("doc")
        doc_dir.mkdir()
        (doc_dir / "notes.md").write_text("some notes", encoding="utf-8")

        result = runner.invoke(main, ["graph", "stamp-revision"])
        assert result.exit_code == 0
        assert "revision" in result.output.lower()

        # Verify the revision metadata was written by checking diff sees no stale files
        diff = runner.invoke(main, ["graph", "diff", "--mode", "hybrid", "--format", "json"])
        assert diff.exit_code == 0
        payload = json.loads(diff.output)
        assert len(payload["rows"]) == 0
```

**Step 2: Run test to verify it fails**

Run: `cd science-tool && uv run --frozen pytest tests/test_graph_cli.py::test_graph_stamp_revision_updates_revision_metadata -v`
Expected: FAIL — `No such command 'stamp-revision'`

**Step 3: Add `stamp_revision` function to store.py**

Add to `science-tool/src/science_tool/graph/store.py` (after `import_snapshot`):

```python
def stamp_revision(graph_path: Path) -> str:
    """Update graph revision metadata without adding entities. Returns the revision timestamp."""
    dataset = _load_dataset(graph_path)
    _save_dataset(dataset, graph_path)

    # Read back the stamped time
    dataset = _load_dataset(graph_path)
    provenance = dataset.graph(_graph_uri("graph/provenance"))
    time_obj = next(provenance.objects(REVISION_URI, SCHEMA_NS.dateModified), None)
    return str(time_obj) if time_obj else "unknown"
```

**Step 4: Add `stamp-revision` CLI command**

In `science-tool/src/science_tool/cli.py`, add the import of `stamp_revision` and the command:

Add `stamp_revision` to the import from `science_tool.graph.store`.

```python
@graph.command("stamp-revision")
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def graph_stamp_revision(graph_path: Path) -> None:
    """Update graph revision metadata to reflect current project state."""

    revision_time = stamp_revision(graph_path)
    click.echo(f"Stamped graph revision: {revision_time}")
```

**Step 5: Update `graph/__init__.py` exports**

Add `stamp_revision` to the import and `__all__` list in `science-tool/src/science_tool/graph/__init__.py`.

**Step 6: Run test to verify it passes**

Run: `cd science-tool && uv run --frozen pytest tests/test_graph_cli.py::test_graph_stamp_revision_updates_revision_metadata -v`
Expected: PASS

**Step 7: Commit**

```bash
git add science-tool/src/science_tool/graph/store.py science-tool/src/science_tool/graph/__init__.py science-tool/src/science_tool/cli.py science-tool/tests/test_graph_cli.py
git commit -m "feat: add graph stamp-revision CLI command"
```

---

### Task 5: Create plugin skills directory and `knowledge-graph.md` skill

**Files:**
- Create: `.claude-plugin/skills/knowledge-graph.md`

**Step 1: Create the skills directory and reference skill**

Create `.claude-plugin/skills/knowledge-graph.md`:

```markdown
---
name: knowledge-graph
description: Reference guide for the science knowledge graph ontology, entity types, CURIE conventions, and provenance patterns. This skill is loaded by create-graph and update-graph as background context.
---

# Knowledge Graph Ontology Reference

## Entity Types

When constructing graph entities from prose, use these types:

| Entity | CLI Command | When to use |
|--------|-------------|-------------|
| Concept | `science-tool graph add concept "<label>" --type <type> --ontology-id <CURIE>` | Any topic, gene, disease, drug, pathway, process |
| Paper | `science-tool graph add paper --doi "<DOI>"` | Published papers referenced in prose |
| Claim | `science-tool graph add claim "<text>" --source <source_ref> --confidence <0-1>` | Factual assertions from literature |
| Hypothesis | `science-tool graph add hypothesis <ID> --text "<text>" --source <source_ref>` | Falsifiable claims under investigation |
| Edge | `science-tool graph add edge <subj> <pred> <obj> --graph <layer>` | Any relation between entities |

## CURIE Conventions

Prefix format: `prefix:localname`. Supported prefixes:

| Prefix | Namespace | Example |
|--------|-----------|---------|
| `sci:` | Science vocab | `sci:relatedTo`, `sci:Concept`, `sci:Claim` |
| `scic:` | Causal vocab | `scic:causes`, `scic:Variable` |
| `biolink:` | Biolink Model | `biolink:Gene`, `biolink:Disease` |
| `schema:` | schema.org | `schema:author`, `schema:identifier` |
| `skos:` | SKOS | `skos:broader`, `skos:narrower` |
| `prov:` | PROV-O | `prov:wasDerivedFrom` |
| `rdf:` | RDF | `rdf:type` |

Project entity references: `paper:<slug>`, `concept:<slug>`, `claim:<slug>`, `hypothesis:<id>`, `dataset:<slug>`.

## Ontology Alignment Guidelines

1. **Always provide ontology IDs** for well-known entities (genes, diseases, drugs, pathways).
2. **Use Biolink types** for biomedical entities: `biolink:Gene`, `biolink:Disease`, `biolink:Drug`, `biolink:Pathway`, `biolink:BiologicalProcess`, `biolink:Phenotype`.
3. **Use `sci:Concept`** as the base type for all concepts; add domain-specific types as additional `rdf:type` values.
4. **Slugify labels** for entity URIs: lowercase, replace non-alphanumeric with `_`.

## Provenance Rules

- Every `sci:Claim` **must** have a `--source` pointing to a paper or document reference.
- Every `sci:Hypothesis` **must** have a `--source`.
- Use `--confidence` (0.0–1.0) for claims where strength of evidence varies.
- Epistemic status values: `established`, `hypothesized`, `disputed`, `retracted`.

## Relation Selection Guide

| Relationship | Predicate | Graph Layer |
|-------------|-----------|-------------|
| General association | `sci:relatedTo` | `graph/knowledge` |
| Hierarchy | `skos:broader` / `skos:narrower` | `graph/knowledge` |
| Evidence supports claim | `sci:supports` | `graph/knowledge` |
| Evidence refutes claim | `sci:refutes` | `graph/knowledge` |
| Paper addresses question | `sci:addresses` | `graph/knowledge` |
| Variable measured by dataset | `sci:measuredBy` | `graph/datasets` |
| Causal effect | `scic:causes` | `graph/causal` |
| Confounding | `scic:confounds` | `graph/causal` |

## Prose Annotation Format

**Frontmatter** — add to research documents:

```yaml
---
ontology_terms:
  - "biolink:Gene"
  - "NCBIGene:672"      # BRCA1
  - "MONDO:0016419"     # breast cancer
---
```

**Inline** — annotate key terms on first mention:

```markdown
BRCA1 [`NCBIGene:672`] is a tumor suppressor gene associated with
breast cancer [`MONDO:0016419`].
```

Rules:
- Annotate each entity on **first mention only**.
- Use the format: `term [`CURIE`]`.
- CURIEs should match ontology IDs used in `graph add concept --ontology-id`.
```

**Step 2: Commit**

```bash
git add .claude-plugin/skills/knowledge-graph.md
git commit -m "feat: add knowledge-graph reference skill for graph authoring"
```

---

### Task 6: Create `create-graph.md` skill

**Files:**
- Create: `.claude-plugin/skills/create-graph.md`

**Step 1: Create the skill file**

Create `.claude-plugin/skills/create-graph.md`:

```markdown
---
name: create-graph
description: Construct a knowledge graph from project prose documents. Reads research docs, extracts entities/relations/claims, populates the graph with provenance, and adds ontology annotations to source documents.
user_invocable: true
---

# Create Knowledge Graph from Prose

> **Prerequisite:** Load the `knowledge-graph` skill for ontology reference before starting.

## Overview

This skill walks through project prose documents (research notes, literature summaries, hypothesis documents) and constructs a knowledge graph with proper provenance and ontology alignment.

## Prerequisites

Before running this skill:
1. The project must have `knowledge/graph.trig` initialized. If not: `uv run science-tool graph init`
2. Research documents should exist in `doc/`, `specs/`, `notes/`, or `papers/summaries/`.

## Workflow

### Step 1: Scan for existing annotations

```bash
uv run science-tool graph scan-prose doc/
uv run science-tool graph scan-prose specs/
uv run science-tool graph scan-prose notes/
```

Review the output. Files with existing annotations already have entity groundwork.

### Step 2: Check current graph state

```bash
uv run science-tool graph stats --format json
```

If the graph already has entities, note what exists to avoid duplicates.

### Step 3: Process each document

For each research document, in order:

1. **Read the document** to understand its content.
2. **Identify entities**: concepts, genes, diseases, drugs, pathways, papers, datasets.
3. **Identify relations**: associations, hierarchies, causal claims, evidence links.
4. **Identify claims**: factual assertions with their sources and confidence levels.
5. **Add entities to the graph** using `science-tool graph add` commands.
6. **Add prose annotations** to the document:
   - Add `ontology_terms:` frontmatter with relevant CURIEs.
   - Add inline `[`CURIE`]` annotations on first mention of each entity.

### Step 4: Entity extraction checklist

For each entity found in prose, determine:

- [ ] **Label**: human-readable name
- [ ] **Type**: `sci:Concept` + domain type (e.g., `biolink:Gene`)
- [ ] **Ontology ID**: standard identifier (e.g., `NCBIGene:672`, `MONDO:0016419`)
- [ ] **Relations**: how it connects to other entities already in the graph

### Step 5: Claim extraction checklist

For each factual assertion:

- [ ] **Text**: the claim statement
- [ ] **Source**: which paper/document supports it (use `paper:doi_<slug>` format)
- [ ] **Confidence**: estimated strength (0.0–1.0)
- [ ] **ID**: optional explicit claim ID for cross-referencing

### Step 6: Finalize

After processing all documents:

```bash
uv run science-tool graph stamp-revision
uv run science-tool graph validate --format json
uv run science-tool graph stats --format json
```

All validation checks must pass. Report the final graph stats to the user.

## Output

At completion, the user should have:
1. A populated `knowledge/graph.trig` with entities, relations, and provenance.
2. Research documents annotated with frontmatter `ontology_terms:` and inline CURIEs.
3. A clean `graph validate` output.

## Important Notes

- **Do not invent claims.** Only add claims that are explicitly stated in the prose.
- **Always include provenance.** Every claim and hypothesis must have a `--source`.
- **Prefer existing ontology IDs** over invented ones. Use standard identifiers (NCBI Gene, MONDO, ChEBI, etc.).
- **Ask the user** if uncertain about entity types, confidence levels, or whether something is a claim vs. background knowledge.
```

**Step 2: Commit**

```bash
git add .claude-plugin/skills/create-graph.md
git commit -m "feat: add create-graph agent skill for graph construction from prose"
```

---

### Task 7: Create `update-graph.md` skill

**Files:**
- Create: `.claude-plugin/skills/update-graph.md`

**Step 1: Create the skill file**

Create `.claude-plugin/skills/update-graph.md`:

```markdown
---
name: update-graph
description: Detect stale areas in the knowledge graph and selectively update from changed documents. Uses graph diff to find changes, then re-processes affected documents.
user_invocable: true
---

# Update Knowledge Graph

> **Prerequisite:** Load the `knowledge-graph` skill for ontology reference before starting.

## Overview

This skill detects which project documents have changed since the last graph update, re-processes them, and updates the graph accordingly.

## Workflow

### Step 1: Run diff to find stale inputs

```bash
uv run science-tool graph diff --mode hybrid --format json
```

Review the output. Each row shows a file path, status (`stale`), and reason (`new_file`, `hash_changed`, `mtime_changed`, `removed_file`).

If no files are stale, report "Graph is up to date" and stop.

### Step 2: Triage changed files

Group stale files by type:

- **New files**: need full entity/claim extraction (same as create-graph Step 3).
- **Changed files**: re-read, compare against existing graph entities, add new/update existing.
- **Removed files**: flag to user — entities sourced from removed files may need review.

### Step 3: Process each stale file

For each stale file:

1. **Read the document** and understand what changed.
2. **Scan for annotations**: `uv run science-tool graph scan-prose <directory>`
3. **Check existing graph entities** related to this document:
   ```bash
   uv run science-tool graph claims --about "<relevant term>" --format json
   uv run science-tool graph neighborhood "<relevant entity>" --format json
   ```
4. **Add new entities/claims** that don't already exist.
5. **Update prose annotations** if new entities were added.

### Step 4: Handle removed files

For files with reason `removed_file`:
- List graph entities that were sourced from the removed file.
- Ask the user whether to keep or remove those entities.
- Do not silently delete graph entities.

### Step 5: Finalize

```bash
uv run science-tool graph stamp-revision
uv run science-tool graph validate --format json
uv run science-tool graph stats --format json
```

Report:
- Number of files processed
- New entities/claims added
- Validation status
- Updated graph stats

## Important Notes

- **Incremental updates only.** Do not re-process unchanged files.
- **Preserve existing entities.** Do not remove or modify entities unless the source document changed.
- **Ask before removing.** Never silently delete graph entities, even if their source was removed.
```

**Step 2: Commit**

```bash
git add .claude-plugin/skills/update-graph.md
git commit -m "feat: add update-graph agent skill for incremental graph updates"
```

---

### Task 8: Register skills in plugin.json

**Files:**
- Modify: `.claude-plugin/plugin.json`

**Step 1: Update plugin.json to declare skills**

Update `.claude-plugin/plugin.json`:

```json
{
  "name": "science",
  "version": "0.1.0",
  "description": "Science — an AI research assistant for hypothesis development, literature review, and reproducible computational pipelines. Named after the lab rat from Adventure Time.",
  "author": {
    "name": "Keith Hughitt"
  },
  "license": "MIT",
  "skills": [
    {
      "name": "knowledge-graph",
      "path": "skills/knowledge-graph.md",
      "description": "Reference guide for the science knowledge graph ontology and conventions"
    },
    {
      "name": "create-graph",
      "path": "skills/create-graph.md",
      "description": "Construct a knowledge graph from project prose documents"
    },
    {
      "name": "update-graph",
      "path": "skills/update-graph.md",
      "description": "Detect and update stale areas in the knowledge graph"
    }
  ]
}
```

**Step 2: Commit**

```bash
git add .claude-plugin/plugin.json
git commit -m "feat: register graph authoring skills in plugin.json"
```

---

### Task 9: Full test suite pass and linting

**Files:** none (verification only)

**Step 1: Run full test suite**

Run: `cd science-tool && uv run --frozen pytest tests/ -v`
Expected: all tests PASS (existing + new)

**Step 2: Run ruff**

Run: `cd science-tool && uv run --frozen ruff check .`
Expected: clean

**Step 3: Run pyright**

Run: `cd science-tool && uv run --frozen pyright`
Expected: clean

**Step 4: Run format check**

Run: `cd science-tool && uv run --frozen ruff format --check .`
Expected: clean (or format and commit)

---

### Task 10: Update design doc with Slice B completion note

**Files:**
- Modify: `docs/plans/2026-03-01-knowledge-graph-design.md`

**Step 1: Add Slice B completion note**

In `docs/plans/2026-03-01-knowledge-graph-design.md`, after the Slice A progress note (line 761), add:

```markdown
Current progress note (2026-03-04): Slice B is complete. Three plugin skills (knowledge-graph, create-graph, update-graph) implemented in .claude-plugin/skills/. Prose scanner (graph scan-prose) and revision stamper (graph stamp-revision) CLI commands added with tests. All tests passing, ruff clean, pyright clean.
```

**Step 2: Commit**

```bash
git add docs/plans/2026-03-01-knowledge-graph-design.md
git commit -m "docs: mark Slice B graph authoring as complete"
```

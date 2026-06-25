# Dataset Reach Authoring Surfaces Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `science dataset prioritize` count dataset reach from paper/consumer `dataset_usage` + `related:` links and from Q/H `datasets:` fields, including missing/stale graph CLI cases.

**Architecture:** Extend the pure reach core in `science/src/science_tool/dataset_prioritize.py`. The graph path will add direct typed `skos:related` Q/H targets for every dataset-usage consumer; the always-on frontmatter path will add Q/H `datasets:` back-edges and bridge authored `dataset_usage` + `related:` so missing or stale graphs still reflect source-authored paper links.

**Tech Stack:** Python 3, rdflib, Click CLI tests, pytest, existing Science entity frontmatter parser and graph materializer.

---

## Global Constraints

- Run all Python project commands from `~/d/science/science`. The repo root has no `pyproject.toml` or `uv.lock`; `uv run --frozen`, pytest, and ruff must use the package project in `science/`.
- Use package-relative paths for Python commands: `tests/...` and `src/...`, not `science/tests/...` or `science/src/...`.
- Run git commands from `~/d/science` with repo-root paths such as `science/tests/...`; those paths are correct for staging and diff review.
- Keep both question template copies in sync: `science/model/src/science_model/templates/question.md` is what `Renderer` loads, and root `templates/question.md` is a hand-maintained command/user template mirror.

---

## File Structure

- Modify `science/src/science_tool/dataset_prioritize.py`
  - Add small helpers for dataset refs in `dataset_usage` frontmatter and typed Q/H URI collection.
  - Extend `frontmatter_reach()` for Q/H `datasets:` and consumer `dataset_usage` + `related:`.
  - Extend `usage_reach()` for consumer `skos:related` Q/H.
- Modify `science/tests/test_dataset_prioritize.py`
  - Add pure frontmatter tests for Q/H `datasets:` and consumer `dataset_usage` + `related:`.
- Modify `science/tests/test_dataset_prioritize_graph.py`
  - Add graph tests for paper-mediated reach and additive/deduped consumer-related reach.
- Modify `science/tests/test_dataset_prioritize_cli.py`
  - Add CLI coverage tests for missing graph and stale graph behavior.
- Modify `science/model/src/science_model/templates/question.md`
  - Clarify that `datasets:` is the first-class dataset/QH authoring surface.
- Modify `templates/question.md`
  - Mirror the same text change in the root template copy.
- Modify `commands/catalog-datasets.md`
  - Point Step 4 at Q/H `datasets:` and paper/evidence-line `dataset_usage` instead of requiring `related:` back-edges.
- Modify `docs/plans/2026-06-21-catalog-datasets-plan.md`
  - Update the historical Step 4 wording so it no longer directs authors only to `related:` edges.

---

### Task 1: Frontmatter Reach Tests

**Files:**
- Modify: `science/tests/test_dataset_prioritize.py`
- Test: `science/tests/test_dataset_prioritize.py`

- [ ] **Step 1: Add failing tests for Q/H `datasets:` and consumer `dataset_usage` + `related:`**

Append these tests after `test_frontmatter_reach_both_directions_excludes_source_refs`:

```python
def test_frontmatter_reach_reads_question_datasets_field(tmp_path: Path) -> None:
    _write(tmp_path / "entities/datasets/d.md",
           '---\nid: "dataset:d"\ntype: "dataset"\ntitle: "D"\nrelated: []\n---\n')
    _write(tmp_path / "entities/questions/q.md",
           '---\nid: "question:q"\ntype: "question"\ntitle: "Q"\n'
           'datasets: ["dataset:d"]\nrelated: []\n---\n')

    reach = frontmatter_reach(tmp_path)

    assert reach["dataset:d"] == {"question:q"}


def test_frontmatter_reach_bridges_consumer_dataset_usage_to_related_qh(tmp_path: Path) -> None:
    _write(tmp_path / "entities/datasets/d.md",
           '---\nid: "dataset:d"\ntype: "dataset"\ntitle: "D"\nrelated: []\n---\n')
    _write(tmp_path / "entities/hypotheses/h.md",
           '---\nid: "hypothesis:h"\ntype: "hypothesis"\ntitle: "H"\n---\n')
    _write(tmp_path / "entities/papers/p.md",
           '---\nid: "paper:p"\ntype: "paper"\ntitle: "P"\n'
           'related: ["hypothesis:h"]\n'
           'dataset_usage:\n'
           '  - ref: "dataset:d"\n'
           '    role: "analyzed"\n'
           '    overlap: "full"\n---\n')

    reach = frontmatter_reach(tmp_path)

    assert reach["dataset:d"] == {"hypothesis:h"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd ~/d/science/science
rtk uv run --frozen python -m pytest tests/test_dataset_prioritize.py::test_frontmatter_reach_reads_question_datasets_field tests/test_dataset_prioritize.py::test_frontmatter_reach_bridges_consumer_dataset_usage_to_related_qh -q
```

Expected: both tests FAIL. The first should show `dataset:d` missing `question:q`; the second should show `dataset:d` missing `hypothesis:h`.

- [ ] **Step 3: Commit the failing tests**

```bash
rtk git add science/tests/test_dataset_prioritize.py
rtk git commit -m "test(dataset): cover frontmatter reach authoring surfaces"
```

---

### Task 2: Frontmatter Reach Implementation

**Files:**
- Modify: `science/src/science_tool/dataset_prioritize.py`
- Test: `science/tests/test_dataset_prioritize.py`

- [ ] **Step 1: Add a helper for authored dataset usage refs**

In `science/src/science_tool/dataset_prioritize.py`, add this helper after `_is_qh`:

```python
def _dataset_usage_refs(fm: dict) -> list[str]:
    usage = fm.get("dataset_usage") or []
    if not isinstance(usage, list):
        return []
    refs: list[str] = []
    for entry in usage:
        if not isinstance(entry, dict):
            continue
        ref = entry.get("ref")
        if isinstance(ref, str) and ref.startswith("dataset:"):
            refs.append(ref)
    return refs
```

- [ ] **Step 2: Replace `frontmatter_reach()` with the extended implementation**

Replace the current `frontmatter_reach()` function with:

```python
def frontmatter_reach(project_root: Path) -> dict[str, set[str]]:
    reach: dict[str, set[str]] = {}
    # Collect dataset ids and the Q/H ids; build every source-authored direction.
    for ent_id, fm in _iter_entity_frontmatter(project_root):
        kind = (fm.get("kind") or fm.get("type") or "")
        related = [r for r in (fm.get("related") or []) if isinstance(r, str)]
        if kind == "dataset":
            reach.setdefault(ent_id, set())
            reach[ent_id].update(r for r in related if _is_qh(r))
        elif _is_qh(ent_id):
            # back-edge: a Q/H listing dataset:x in its own related
            for r in related:
                if isinstance(r, str) and r.startswith("dataset:"):
                    reach.setdefault(r, set()).add(ent_id)
            # first-class Q/H surface: datasets: ["dataset:x", ...]
            datasets = [r for r in (fm.get("datasets") or []) if isinstance(r, str)]
            for dataset_id in datasets:
                if dataset_id.startswith("dataset:"):
                    reach.setdefault(dataset_id, set()).add(ent_id)

        # General source-authored usage bridge: papers are the motivating case,
        # but any entity carrying dataset_usage and related Q/H records the same
        # dataset-inquiry fact.
        qh_targets = {r for r in related if _is_qh(r)}
        if qh_targets:
            for dataset_ref in _dataset_usage_refs(fm):
                reach.setdefault(dataset_ref, set()).update(qh_targets)
    return reach
```

- [ ] **Step 3: Run focused tests**

Run:

```bash
cd ~/d/science/science
rtk uv run --frozen python -m pytest tests/test_dataset_prioritize.py::test_frontmatter_reach_reads_question_datasets_field tests/test_dataset_prioritize.py::test_frontmatter_reach_bridges_consumer_dataset_usage_to_related_qh -q
```

Expected: both tests PASS.

- [ ] **Step 4: Run frontmatter regression tests**

Run:

```bash
cd ~/d/science/science
rtk uv run --frozen python -m pytest tests/test_dataset_prioritize.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit implementation**

```bash
rtk git add science/src/science_tool/dataset_prioritize.py
rtk git commit -m "feat(dataset): count frontmatter dataset reach surfaces"
```

---

### Task 3: Graph Reach Tests

**Files:**
- Modify: `science/tests/test_dataset_prioritize_graph.py`
- Test: `science/tests/test_dataset_prioritize_graph.py`

- [ ] **Step 1: Add graph tests for consumer `skos:related` reach**

Append these tests after `test_usage_reach_traverses_to_question_and_hypothesis`:

```python
def test_usage_reach_collects_paper_related_qh(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text('slug: "tp"\n', encoding="utf-8")
    _write(tmp_path / "entities/datasets/d.md",
           '---\nid: "dataset:d"\ntype: "dataset"\ntitle: "D"\norigin: "external"\n'
           'access: {level: "public", verified: true}\n---\n')
    _write(tmp_path / "entities/hypotheses/h.md",
           '---\nid: "hypothesis:h"\ntype: "hypothesis"\ntitle: "H"\n---\n')
    _write(tmp_path / "entities/papers/p.md",
           '---\nid: "paper:p"\ntype: "paper"\ntitle: "P"\n'
           'related: ["hypothesis:h"]\n'
           'dataset_usage:\n'
           '  - ref: "dataset:d"\n'
           '    role: "analyzed"\n'
           '    overlap: "full"\n---\n')
    graph_path = materialize_graph(tmp_path)
    ds = _load_dataset(graph_path)
    knowledge = ds.graph(_graph_uri("graph/knowledge"))
    provenance = ds.graph(_graph_uri("graph/provenance"))

    reach = usage_reach(knowledge, provenance, ["dataset:d"])

    assert reach["dataset:d"] == {"hypothesis:h"}


def test_usage_reach_unions_consumer_related_qh_with_proposition_path(tmp_path: Path) -> None:
    _seed_graph_project(tmp_path)
    _write(tmp_path / "entities/hypotheses/h-related.md",
           '---\nid: "hypothesis:h-related"\ntype: "hypothesis"\ntitle: "H related"\n---\n')
    (tmp_path / "entities/evidence-lines/e.md").write_text(
        '---\nid: "evidence-line:e"\ntype: "evidence-line"\ntitle: "E"\n'
        'stance: "supports"\ntarget: "proposition:p"\nevidence_type: "empirical_data_evidence"\n'
        'related: ["hypothesis:h-related"]\n'
        'dataset_usage:\n'
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd ~/d/science/science
rtk uv run --frozen python -m pytest tests/test_dataset_prioritize_graph.py::test_usage_reach_collects_paper_related_qh tests/test_dataset_prioritize_graph.py::test_usage_reach_unions_consumer_related_qh_with_proposition_path -q
```

Expected: both tests FAIL. The first should have an empty reach set; the second should miss `hypothesis:h-related` until consumer `skos:related` traversal is implemented.

- [ ] **Step 3: Commit the graph tests**

```bash
rtk git add science/tests/test_dataset_prioritize_graph.py
rtk git commit -m "test(dataset): cover graph consumer related reach"
```

---

### Task 4: Graph Reach Implementation

**Files:**
- Modify: `science/src/science_tool/dataset_prioritize.py`
- Test: `science/tests/test_dataset_prioritize_graph.py`

- [ ] **Step 1: Import `SKOS`**

Change the rdflib namespace import at the top of `science/src/science_tool/dataset_prioritize.py` from:

```python
from rdflib.namespace import RDF
```

to:

```python
from rdflib.namespace import RDF, SKOS
```

- [ ] **Step 2: Add a helper for typed consumer-related Q/H targets**

Add this helper after `_qh_for_proposition()`:

```python
def _qh_for_consumer_related(knowledge, consumer: URIRef) -> set[URIRef]:
    out: set[URIRef] = set()
    for target in knowledge.objects(consumer, SKOS.related):
        if not isinstance(target, URIRef):
            continue
        if (target, RDF.type, SCI_NS.Hypothesis) in knowledge or (target, RDF.type, SCI_NS.Question) in knowledge:
            out.add(target)
    return out
```

- [ ] **Step 3: Extend `usage_reach()`**

Replace the body of `usage_reach()` with:

```python
def usage_reach(knowledge, provenance, dataset_ids: list[str]) -> dict[str, set[str]]:
    reach: dict[str, set[str]] = {ds_id: set() for ds_id in dataset_ids}
    for ds_id in dataset_ids:
        ds_uri = project_entity_uri(ds_id)
        # usage nodes referencing this dataset, then their consumers
        for usage_node in provenance.subjects(SCI_NS.dataset, ds_uri):
            for consumer in provenance.subjects(SCI_NS.hasDatasetUsage, usage_node):
                # consumer (usually evidence-line) supports/disputes a proposition
                props: set[URIRef] = set()
                for _, _, prop in knowledge.triples((consumer, CITO_NS.supports, None)):
                    props.add(prop)
                for _, _, prop in knowledge.triples((consumer, CITO_NS.disputes, None)):
                    props.add(prop)
                for prop in props:
                    if not isinstance(prop, URIRef):
                        continue
                    for qh in _qh_for_proposition(knowledge, prop):
                        ref = canonical_id_from_entity_uri(str(qh))
                        if ref is not None:  # skip non-entity URIs
                            reach[ds_id].add(ref)
                for qh in _qh_for_consumer_related(knowledge, consumer):
                    ref = canonical_id_from_entity_uri(str(qh))
                    if ref is not None:
                        reach[ds_id].add(ref)
    return reach
```

- [ ] **Step 4: Run focused graph tests**

Run:

```bash
cd ~/d/science/science
rtk uv run --frozen python -m pytest tests/test_dataset_prioritize_graph.py::test_usage_reach_collects_paper_related_qh tests/test_dataset_prioritize_graph.py::test_usage_reach_unions_consumer_related_qh_with_proposition_path -q
```

Expected: PASS.

- [ ] **Step 5: Run graph regression tests**

Run:

```bash
cd ~/d/science/science
rtk uv run --frozen python -m pytest tests/test_dataset_prioritize_graph.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit implementation**

```bash
rtk git add science/src/science_tool/dataset_prioritize.py
rtk git commit -m "feat(dataset): count graph consumer related reach"
```

---

### Task 5: CLI Missing/Stale Graph Tests

**Files:**
- Modify: `science/tests/test_dataset_prioritize_cli.py`
- Test: `science/tests/test_dataset_prioritize_cli.py`

- [ ] **Step 1: Add imports for stale graph setup**

At the top of `science/tests/test_dataset_prioritize_cli.py`, add `os` and `materialize_graph`:

```python
import json
import os
from pathlib import Path

from click.testing import CliRunner

from science_tool.cli import main as science_cli
from science_tool.graph.materialize import materialize_graph
```

- [ ] **Step 2: Add JSON parsing and fixture helpers**

Add these helpers after `_seed()`:

```python
def _json_rows(res) -> list[dict]:
    text = "\n".join(
        line for line in res.output.splitlines() if not line.startswith("warning:")
    )
    return json.loads(text)


def _seed_paper_reach(root: Path, *, include_paper: bool = True) -> None:
    (root / "science.yaml").write_text('slug: "tp"\n', encoding="utf-8")
    d = root / "entities" / "datasets"
    h = root / "entities" / "hypotheses"
    p = root / "entities" / "papers"
    d.mkdir(parents=True, exist_ok=True)
    h.mkdir(parents=True, exist_ok=True)
    (d / "d.md").write_text(
        '---\nid: "dataset:d"\ntype: "dataset"\ntitle: "D"\norigin: "external"\n'
        'access: {level: "public", verified: true}\n---\n',
        encoding="utf-8",
    )
    (h / "h.md").write_text(
        '---\nid: "hypothesis:h"\ntype: "hypothesis"\ntitle: "H"\n---\n',
        encoding="utf-8",
    )
    if include_paper:
        p.mkdir(parents=True, exist_ok=True)
        (p / "p.md").write_text(
            '---\nid: "paper:p"\ntype: "paper"\ntitle: "P"\n'
            'related: ["hypothesis:h"]\n'
            'dataset_usage:\n'
            '  - ref: "dataset:d"\n'
            '    role: "analyzed"\n'
            '    overlap: "full"\n---\n',
            encoding="utf-8",
        )
```

- [ ] **Step 3: Replace inline JSON parsing in existing tests**

In `test_prioritize_json()`, replace:

```python
    import json
    # Click 8 mixes stderr into output; strip any leading warning lines before parsing.
    json_text = "\n".join(
        line for line in res.output.splitlines() if not line.startswith("warning:")
    )
    rows = json.loads(json_text)
```

with:

```python
    rows = _json_rows(res)
```

In `test_prioritize_excludes_gated_by_default()`, replace the local `import json` and nested `_ids()` helper:

```python
    import json

    def _ids(*args: str) -> set[str]:
        res = _run(tmp_path, *args, "--format", "json")
        assert res.exit_code == 0
        text = "\n".join(
            ln for ln in res.output.splitlines() if not ln.startswith("warning:")
        )
        return {r["id"] for r in json.loads(text)}
```

with:

```python
    def _ids(*args: str) -> set[str]:
        res = _run(tmp_path, *args, "--format", "json")
        assert res.exit_code == 0
        return {r["id"] for r in _json_rows(res)}
```

In `test_prioritize_coverage_json_reports_per_target_gaps()`, replace:

```python
    text = "\n".join(
        line for line in res.output.splitlines() if not line.startswith("warning:")
    )
    rows = json.loads(text)
```

with:

```python
    rows = _json_rows(res)
```

- [ ] **Step 4: Add CLI tests for missing and stale graph behavior**

Append these tests after `test_prioritize_coverage_json_reports_per_target_gaps()`:

```python
def test_prioritize_coverage_uses_paper_usage_frontmatter_without_graph(tmp_path: Path) -> None:
    _seed_paper_reach(tmp_path)

    res = _run(tmp_path, "--coverage", "--format", "json")

    assert res.exit_code == 0
    assert "no materialized graph" in res.output.lower()
    rows = _json_rows(res)
    by_id = {row["target"]: row for row in rows}
    assert by_id["hypothesis:h"]["datasets"] == ["dataset:d"]
    assert by_id["hypothesis:h"]["coverage_state"] == "covered"


def test_prioritize_coverage_uses_current_frontmatter_when_graph_is_stale(tmp_path: Path) -> None:
    _seed_paper_reach(tmp_path, include_paper=False)
    graph_path = materialize_graph(tmp_path)
    _seed_paper_reach(tmp_path, include_paper=True)
    os.utime(graph_path, (1, 1))

    res = _run(tmp_path, "--coverage", "--format", "json")

    assert res.exit_code == 0
    assert "graph may be stale" in res.output.lower()
    rows = _json_rows(res)
    by_id = {row["target"]: row for row in rows}
    assert by_id["hypothesis:h"]["datasets"] == ["dataset:d"]
    assert by_id["hypothesis:h"]["coverage_state"] == "covered"
```

- [ ] **Step 5: Run CLI tests**

Run:

```bash
cd ~/d/science/science
rtk uv run --frozen python -m pytest tests/test_dataset_prioritize_cli.py -q
```

Expected: PASS. These pass after Task 2 because the CLI always merges `frontmatter_reach()`.

- [ ] **Step 6: Commit CLI tests**

```bash
rtk git add science/tests/test_dataset_prioritize_cli.py
rtk git commit -m "test(dataset): cover prioritize graph degraded modes"
```

---

### Task 6: Author-Facing Documentation

**Files:**
- Modify: `science/model/src/science_model/templates/question.md`
- Modify: `templates/question.md`
- Modify: `commands/catalog-datasets.md`
- Modify: `docs/plans/2026-06-21-catalog-datasets-plan.md`

- [ ] **Step 1: Update the package question template body**

In `science/model/src/science_model/templates/question.md`, replace:

```markdown
## Connections to Project

- Related hypotheses:
- Required data or analyses:
- Priority level:
```

with:

```markdown
## Connections to Project

- Related hypotheses:
- Required datasets: list dataset IDs in frontmatter `datasets:`.
- Required analyses:
- Priority level:
```

- [ ] **Step 2: Mirror the question template body change**

Apply the same replacement in `templates/question.md`:

```markdown
## Connections to Project

- Related hypotheses:
- Required datasets: list dataset IDs in frontmatter `datasets:`.
- Required analyses:
- Priority level:
```

- [ ] **Step 3: Update catalog command gap-scan wording**

In `commands/catalog-datasets.md`, replace the gap definition bullet that says:

```markdown
  - No dataset entity has a `related:` edge to it (frontmatter path, either direction), AND no evidence-line carries a `dataset_usage` block pointing to a dataset that reaches it; **or**
```

with:

```markdown
  - No dataset reaches it through any load-bearing authoring surface: dataset `related:`, Q/H `related:` back-edge, Q/H `datasets:`, evidence-line/paper `dataset_usage` + proposition reach, or paper/consumer `dataset_usage` + `related:`; **or**
```

- [ ] **Step 4: Update catalog command Step 2 dataset-add example**

In `commands/catalog-datasets.md`, replace:

```bash
science dataset add <slug> \
  --title "<Human-readable title>" \
  --level public \
  --source-url "<landing page or accession URL>" \
  --related "question:<id>"   # repeat for each related Q/H
```

with:

```bash
science dataset add <slug> \
  --title "<Human-readable title>" \
  --level public \
  --source-url "<landing page or accession URL>"
```

Then add this paragraph immediately after the example:

```markdown
Record the dataset/QH connection in the Q/H entity's `datasets:` field during Step 4. Use dataset `related:` only when the dataset entity is the clearer editing surface for the authoring session.
```

- [ ] **Step 5: Replace catalog command Step 4 connection instructions**

In `commands/catalog-datasets.md`, replace the Step 4 block from `**Add \`related:\` edges**` through the paragraph ending `once materialized.` with:

````markdown
**Prefer Q/H `datasets:` for direct dataset needs.** In each question or hypothesis entity, add the dataset IDs it needs or is informed by:

```yaml
datasets:
  - "dataset:<slug>"
```

This is now load-bearing for `science dataset prioritize` and works without a materialized graph.

**Use dataset `related:` when the dataset entity is the active editing surface.** This remains supported:

```yaml
related:
  - "question:q0001"
  - "hypothesis:h0002"
```

Do not add duplicate Q/H `related:` back-edges solely for prioritize reach when `datasets:` already records the fact.

**Author `dataset_usage` blocks** where a paper or evidence-line records how a dataset was used:

```yaml
dataset_usage:
  - ref: "dataset:<slug>"
    role: "analyzed"
    overlap: "full"
```

For papers, pair `dataset_usage` with `related:` Q/H links on the paper. For evidence-lines, pair `dataset_usage` with the existing proposition target. Both paths participate in the `reach` term of the prioritizer; graph materialization is still needed for proposition-derived reach and leverage.
````

- [ ] **Step 6: Update the historical catalog plan**

Update `docs/plans/2026-06-21-catalog-datasets-plan.md` Step 4 line:

```markdown
5. **Connect** — add `related:` edges between datasets and the Q/H they inform; where evidence-lines exist, author `dataset_usage` blocks.
```

to:

```markdown
5. **Connect** — prefer Q/H `datasets:` for direct dataset needs, use dataset `related:` when the dataset entity is the active editing surface, and author `dataset_usage` blocks on papers/evidence-lines where usage provenance exists.
```

- [ ] **Step 7: Commit documentation updates**

```bash
rtk git add science/model/src/science_model/templates/question.md templates/question.md commands/catalog-datasets.md docs/plans/2026-06-21-catalog-datasets-plan.md
rtk git commit -m "docs(dataset): document load-bearing reach authoring surfaces"
```

---

### Task 7: Final Verification

**Files:**
- Verify: `science/src/science_tool/dataset_prioritize.py`
- Verify: `science/tests/test_dataset_prioritize.py`
- Verify: `science/tests/test_dataset_prioritize_graph.py`
- Verify: `science/tests/test_dataset_prioritize_cli.py`
- Verify: `science/model/src/science_model/templates/question.md`
- Verify: `templates/question.md`
- Verify: `commands/catalog-datasets.md`
- Verify: `docs/plans/2026-06-21-catalog-datasets-plan.md`

- [ ] **Step 1: Run the dataset prioritize test suite**

Run:

```bash
cd ~/d/science/science
rtk uv run --frozen python -m pytest tests/test_dataset_prioritize.py tests/test_dataset_prioritize_graph.py tests/test_dataset_prioritize_cli.py -q
```

Expected: PASS.

- [ ] **Step 2: Run formatting check**

Run:

```bash
cd ~/d/science/science
rtk uv run --frozen ruff format --check src/science_tool/dataset_prioritize.py tests/test_dataset_prioritize.py tests/test_dataset_prioritize_graph.py tests/test_dataset_prioritize_cli.py
```

Expected: PASS. If it fails, run:

```bash
cd ~/d/science/science
rtk uv run --frozen ruff format src/science_tool/dataset_prioritize.py tests/test_dataset_prioritize.py tests/test_dataset_prioritize_graph.py tests/test_dataset_prioritize_cli.py
```

Then rerun the format check.

- [ ] **Step 3: Run lint check**

Run:

```bash
cd ~/d/science/science
rtk uv run --frozen ruff check src/science_tool/dataset_prioritize.py tests/test_dataset_prioritize.py tests/test_dataset_prioritize_graph.py tests/test_dataset_prioritize_cli.py
```

Expected: PASS.

- [ ] **Step 4: Inspect the diff for unrelated changes**

Run:

```bash
rtk git diff -- science/src/science_tool/dataset_prioritize.py science/tests/test_dataset_prioritize.py science/tests/test_dataset_prioritize_graph.py science/tests/test_dataset_prioritize_cli.py science/model/src/science_model/templates/question.md templates/question.md commands/catalog-datasets.md docs/plans/2026-06-21-catalog-datasets-plan.md
```

Expected: diff only contains dataset reach behavior, tests, and author-facing docs. Do not revert unrelated user changes outside these files.

- [ ] **Step 5: Commit final verification fixes**

If formatting or linting changed files, commit those changes:

```bash
rtk git add science/src/science_tool/dataset_prioritize.py science/tests/test_dataset_prioritize.py science/tests/test_dataset_prioritize_graph.py science/tests/test_dataset_prioritize_cli.py science/model/src/science_model/templates/question.md templates/question.md commands/catalog-datasets.md docs/plans/2026-06-21-catalog-datasets-plan.md
rtk git commit -m "chore(dataset): verify reach authoring surfaces"
```

If no files changed after Task 6, do not create an empty commit.

---

## Self-Review

- **Spec coverage:** Gap #1 graph path is implemented by Tasks 3-4. Gap #1 missing/stale graph behavior is covered by Tasks 1-2 and Task 5. Gap #2 Q/H `datasets:` is implemented by Tasks 1-2. Author docs and both question template copies are covered by Task 6. Regression and formatting checks are covered by Task 7.
- **Placeholder scan:** The plan contains no deferred implementation placeholders. Every code-changing step includes exact code or replacement text.
- **Type consistency:** Helper names are `_dataset_usage_refs()` and `_qh_for_consumer_related()` throughout. Existing public functions keep their signatures: `frontmatter_reach(project_root: Path)`, `usage_reach(knowledge, provenance, dataset_ids: list[str])`, and `merged_reach(...)`.

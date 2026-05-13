# Wander Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement `science wander` (CLI) and `/wander` (slash command) — a serendipitous, weighted-random review loop over epistemic graph entities, per the design spec at `docs/plans/2026-05-09-wander-design.md`.

**Architecture:** A new `science_tool.wander` package containing pure helpers (sampling wrapper, provenance lookups, neighbor extraction, stub-smell signals, skeleton renderer) plus a Click subcommand wired into `science_tool.cli`. The CLI does no LLM work — it gathers evidence and writes a markdown skeleton. The slash command (`commands/wander.md`) drives the agent loop on top of that skeleton.

**Tech Stack:** Python 3.x, Click, rdflib (Dataset / named graphs), pytest, existing `science_tool.graph.attention` (`compute_attention_candidates`, `weighted_sample_without_replacement`).

---

## Reference reading (read these before starting)

- **Design spec:** `docs/plans/2026-05-09-wander-design.md` — the source of truth. Every behavior in this plan should trace to a section there.
- **Existing sampler internals:** `science/src/science_tool/graph/attention.py` — particularly `AttentionCandidate` (lines ~20-33), `compute_attention_candidates` (lines ~36-102), `weighted_sample_without_replacement` (lines ~105-137), and the higher-level `query_attention_sample` (lines ~140-154) which we're **not** using because it discards URIs and components.
- **Existing test for sampler:** `science/tests/test_attention_sampling.py` — copy fixture-construction style and assertion style.
- **Provenance materialization:** `science/src/science_tool/graph/materialize.py` lines 213-219 — shows that source paths are stored in the `graph/provenance` named graph as `<entity_uri> prov:wasDerivedFrom <source_uri>` and `<source_uri> schema:identifier "path/to/file"`.
- **CLI conventions:** `science/src/science_tool/cli.py` — `@main.group()` for `graph` (line 692), `attention-sample` command (lines 1384-1434) is the closest analog. `OUTPUT_FORMATS` is `("table", "json")` from `science_tool.output`. `science wander` will define its own choice tuple `("markdown", "json")` because its markdown mode writes a file, not a table.
- **Slash-command style:** `commands/curate.md` — the closest functional analog (agent-led sweep with `--apply`-style flag).

## File structure

**New files:**

```
science/src/science_tool/wander/
├── __init__.py            # public re-exports
├── sampling.py            # sample_for_walk(): wraps compute_attention_candidates + weighted_sample_without_replacement
├── provenance.py          # source_path_for(uri, dataset), created_date_for(uri, dataset, path)
├── neighbors.py           # neighbors_for(uri, dataset) → NeighborSet
├── references.py          # active_references_for(uri, dataset) → list[Reference]
├── context.py             # ContextBundle dataclass + assemble_bundle()
├── stub_smell.py          # StubSignals dataclass + compute_stub_signals(bundle)
├── skeleton.py            # render_markdown_skeleton(walk_id, bundles, ...) and render_json(...)
└── cli.py                 # @click.command "wander" — registered from science_tool.cli

science/tests/
├── test_wander_sampling.py
├── test_wander_provenance.py
├── test_wander_neighbors_references.py
├── test_wander_context.py
├── test_wander_stub_smell.py
├── test_wander_skeleton.py
└── test_wander_cli.py

commands/wander.md         # slash command at repo root (sibling of curate.md)
```

**Modified files:**

- `science/src/science_tool/cli.py` — import and register the `wander` command on `main`.

**Why this split:** Each module has one job. Tests can target one helper without booting the whole CLI. `provenance.py`, `neighbors.py`, `references.py` could collapse into one `graph_lookups.py` later, but keeping them separate now makes the TDD loop tighter and tests focused.

---

## Task 1: Module scaffolding + sampling wrapper

**Files:**
- Create: `science/src/science_tool/wander/__init__.py`
- Create: `science/src/science_tool/wander/sampling.py`
- Create: `science/tests/test_wander_sampling.py`

The first thing the CLI does is sample. Build the wrapper that takes a graph path and returns a list of `AttentionCandidate` objects (not the dict-formatted rows that `query_attention_sample` returns), so downstream code keeps URIs and raw component values.

- [ ] **Step 1: Write the failing test**

Create `science/tests/test_wander_sampling.py`:

```python
from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from rdflib import Dataset, Literal, URIRef
from rdflib.namespace import RDF, SKOS, XSD

from science_tool.graph.io import PROJECT_NS, SCI_NS, save_canonical_graph_dataset
from science_tool.wander.sampling import WanderSamplerError, sample_for_walk


def _u(path: str) -> URIRef:
    return URIRef(PROJECT_NS[path])


def _two_hypothesis_dataset() -> Dataset:
    dataset = Dataset()
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
    for slug, label in (("h1", "First"), ("h2", "Second")):
        uri = _u(f"hypothesis/{slug}")
        knowledge.add((uri, RDF.type, SCI_NS.Hypothesis))
        knowledge.add((uri, SKOS.prefLabel, Literal(label)))
        knowledge.add((uri, SCI_NS.freshnessState, Literal("fresh")))
    return dataset


def _write_graph(tmp_path: Path, dataset: Dataset) -> Path:
    graph_path = tmp_path / "graph.trig"
    save_canonical_graph_dataset(dataset, graph_path)
    return graph_path


def test_sample_for_walk_returns_attention_candidates(tmp_path: Path) -> None:
    graph_path = _write_graph(tmp_path, _two_hypothesis_dataset())

    sample = sample_for_walk(graph_path=graph_path, n=2, seed=7, today=date(2026, 5, 9))

    assert len(sample) == 2
    ids = {candidate.entity_id for candidate in sample}
    assert ids == {"hypothesis:h1", "hypothesis:h2"}
    # We need URIs and raw component values downstream — verify they survive.
    for candidate in sample:
        assert candidate.uri.startswith(str(PROJECT_NS))
        assert "incoming_bears_on" in candidate.components
        assert candidate.weight > 0


def test_sample_for_walk_is_seeded(tmp_path: Path) -> None:
    graph_path = _write_graph(tmp_path, _two_hypothesis_dataset())

    first = sample_for_walk(graph_path=graph_path, n=1, seed=7, today=date(2026, 5, 9))
    second = sample_for_walk(graph_path=graph_path, n=1, seed=7, today=date(2026, 5, 9))

    assert [c.entity_id for c in first] == [c.entity_id for c in second]


def test_sample_for_walk_respects_kind_filter(tmp_path: Path) -> None:
    dataset = _two_hypothesis_dataset()
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
    proposition = _u("proposition/p1")
    knowledge.add((proposition, RDF.type, SCI_NS.Proposition))
    knowledge.add((proposition, SKOS.prefLabel, Literal("A claim")))
    knowledge.add((proposition, SCI_NS.freshnessState, Literal("fresh")))
    graph_path = _write_graph(tmp_path, dataset)

    sample = sample_for_walk(
        graph_path=graph_path, n=5, seed=7, today=date(2026, 5, 9), kinds={"proposition"}
    )

    assert {c.entity_id for c in sample} == {"proposition:p1"}


def test_sample_for_walk_errors_on_missing_graph(tmp_path: Path) -> None:
    missing = tmp_path / "no-such.trig"

    with pytest.raises(WanderSamplerError) as excinfo:
        sample_for_walk(graph_path=missing, n=3, seed=7, today=date(2026, 5, 9))

    assert "science graph build" in str(excinfo.value)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd science && uv run pytest tests/test_wander_sampling.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'science_tool.wander'`.

- [ ] **Step 3: Create empty package init**

Create `science/src/science_tool/wander/__init__.py`:

```python
from __future__ import annotations

from science_tool.wander.sampling import WanderSamplerError, sample_for_walk

__all__ = ["WanderSamplerError", "sample_for_walk"]
```

- [ ] **Step 4: Implement `sample_for_walk`**

Create `science/src/science_tool/wander/sampling.py`:

```python
from __future__ import annotations

from datetime import date
from pathlib import Path

from rdflib import Dataset

from science_tool.graph.attention import (
    AttentionCandidate,
    compute_attention_candidates,
    weighted_sample_without_replacement,
)


class WanderSamplerError(Exception):
    """Raised when a wander sample cannot be drawn."""


def sample_for_walk(
    *,
    graph_path: Path,
    n: int,
    seed: int | None,
    today: date | None,
    kinds: set[str] | None = None,
    epsilon: float = 0.05,
) -> list[AttentionCandidate]:
    """Draw `n` epistemic entities from the materialized graph.

    Wraps the existing attention machinery but preserves URI and raw
    weight components for downstream context-bundle assembly.
    """
    if not graph_path.exists():
        raise WanderSamplerError(
            f"Graph file not found at {graph_path}. "
            "Run `science graph build` first."
        )
    if n < 0:
        raise WanderSamplerError("n must be >= 0")

    dataset = Dataset()
    dataset.parse(source=str(graph_path), format="trig")
    candidates = compute_attention_candidates(
        dataset, today=today, kinds=kinds, epsilon=epsilon
    )
    return weighted_sample_without_replacement(candidates, limit=n, seed=seed)
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd science && uv run pytest tests/test_wander_sampling.py -v
```

Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/wander/__init__.py \
        science/src/science_tool/wander/sampling.py \
        science/tests/test_wander_sampling.py
git commit -m "feat(wander): add sampling wrapper preserving URIs and components"
```

---

## Task 2: Provenance lookups (source path + created date)

**Files:**
- Create: `science/src/science_tool/wander/provenance.py`
- Create: `science/tests/test_wander_provenance.py`

Resolve an entity URI to a source file path by querying the provenance graph for `prov:wasDerivedFrom` → `schema:identifier`. Resolve a created date with the spec's fallback chain: `dcterms:created` → git first-commit → `mtime`.

- [ ] **Step 1: Write the failing test**

Create `science/tests/test_wander_provenance.py`:

```python
from __future__ import annotations

import os
import subprocess
from datetime import date
from pathlib import Path

from rdflib import Dataset, Literal, URIRef
from rdflib.namespace import RDF, XSD

from science_tool.graph.io import PROJECT_NS

from science_tool.wander.provenance import created_date_for, source_path_for

PROV = URIRef("http://www.w3.org/ns/prov#wasDerivedFrom")
SCHEMA_IDENTIFIER = URIRef("https://schema.org/identifier")
DCTERMS_CREATED = URIRef("http://purl.org/dc/terms/created")


def _entity_uri(path: str) -> URIRef:
    return URIRef(PROJECT_NS[path])


def _add_provenance(dataset: Dataset, *, entity_uri: URIRef, source_path: str) -> URIRef:
    provenance = dataset.graph(PROJECT_NS["graph/provenance"])
    safe = source_path.replace("/", "_").replace(" ", "_").lower()
    source_uri = URIRef(PROJECT_NS[f"source/{safe}"])
    provenance.add((entity_uri, PROV, source_uri))
    provenance.add((source_uri, SCHEMA_IDENTIFIER, Literal(source_path)))
    return source_uri


def test_source_path_for_returns_relative_path() -> None:
    dataset = Dataset()
    entity = _entity_uri("hypothesis/h1")
    _add_provenance(dataset, entity_uri=entity, source_path="doc/hypotheses/h1.md")

    assert source_path_for(entity, dataset) == "doc/hypotheses/h1.md"


def test_source_path_for_returns_none_when_no_provenance() -> None:
    dataset = Dataset()
    assert source_path_for(_entity_uri("hypothesis/missing"), dataset) is None


def test_created_date_uses_dcterms_when_available() -> None:
    dataset = Dataset()
    entity = _entity_uri("hypothesis/h1")
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
    knowledge.add((entity, DCTERMS_CREATED, Literal("2026-01-15", datatype=XSD.date)))

    assert created_date_for(entity, dataset, source_path=None) == date(2026, 1, 15)


def test_created_date_falls_back_to_git_first_commit(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)
    file_path = repo / "doc" / "h1.md"
    file_path.parent.mkdir(parents=True)
    file_path.write_text("# H1\n")
    subprocess.run(["git", "add", "doc/h1.md"], cwd=repo, check=True)
    env = {**os.environ, "GIT_AUTHOR_DATE": "2026-02-10T12:00:00", "GIT_COMMITTER_DATE": "2026-02-10T12:00:00"}
    subprocess.run(["git", "commit", "-q", "-m", "add"], cwd=repo, check=True, env=env)

    dataset = Dataset()  # no dcterms:created in graph
    result = created_date_for(
        _entity_uri("hypothesis/h1"),
        dataset,
        source_path=str(file_path),
        repo_root=repo,
    )

    assert result == date(2026, 2, 10)


def test_created_date_falls_back_to_mtime_when_not_in_git(tmp_path: Path) -> None:
    file_path = tmp_path / "loose.md"
    file_path.write_text("hello")
    os.utime(file_path, (1717200000, 1717200000))  # 2024-06-01 UTC-ish; we don't care about exact day, only that we get a date

    dataset = Dataset()
    result = created_date_for(
        _entity_uri("hypothesis/h1"),
        dataset,
        source_path=str(file_path),
        repo_root=tmp_path,
    )

    assert isinstance(result, date)


def test_created_date_returns_none_with_no_inputs() -> None:
    assert created_date_for(_entity_uri("hypothesis/h1"), Dataset(), source_path=None) is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd science && uv run pytest tests/test_wander_provenance.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'science_tool.wander.provenance'`.

- [ ] **Step 3: Implement `provenance.py`**

Create `science/src/science_tool/wander/provenance.py`:

```python
from __future__ import annotations

import subprocess
from datetime import date, datetime, timezone
from pathlib import Path

from rdflib import Dataset, URIRef
from rdflib.namespace import Namespace

from science_tool.graph.io import PROJECT_NS

PROV_WAS_DERIVED_FROM = URIRef("http://www.w3.org/ns/prov#wasDerivedFrom")
SCHEMA_IDENTIFIER = URIRef("https://schema.org/identifier")
DCTERMS = Namespace("http://purl.org/dc/terms/")
SCI_CREATED_PRED = URIRef("https://w3id.org/science#created")


def source_path_for(entity_uri: URIRef, dataset: Dataset) -> str | None:
    """Return the source file path for an entity, or None if no provenance edge exists."""
    provenance = dataset.graph(PROJECT_NS["graph/provenance"])
    for source_uri in provenance.objects(entity_uri, PROV_WAS_DERIVED_FROM):
        for identifier in provenance.objects(source_uri, SCHEMA_IDENTIFIER):
            return str(identifier)
    return None


def created_date_for(
    entity_uri: URIRef,
    dataset: Dataset,
    *,
    source_path: str | None,
    repo_root: Path | None = None,
) -> date | None:
    """Resolve created date with fallback chain: graph → git first-commit → mtime."""
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
    for predicate in (DCTERMS.created, SCI_CREATED_PRED):
        for literal in knowledge.objects(entity_uri, predicate):
            parsed = _parse_iso_date(str(literal))
            if parsed is not None:
                return parsed

    if source_path is None:
        return None

    if repo_root is not None:
        git_date = _git_first_commit_date(repo_root, source_path)
        if git_date is not None:
            return git_date

    path = Path(source_path)
    if path.exists():
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).date()
    return None


def _parse_iso_date(text: str) -> date | None:
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
        except ValueError:
            return None


def _git_first_commit_date(repo_root: Path, source_path: str) -> date | None:
    rel = source_path
    try:
        rel = str(Path(source_path).resolve().relative_to(repo_root.resolve()))
    except ValueError:
        pass
    try:
        result = subprocess.run(
            ["git", "log", "--diff-filter=A", "--format=%aI", "--", rel],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return None
    if result.returncode != 0:
        return None
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if not lines:
        return None
    return _parse_iso_date(lines[-1])  # `git log` is reverse chronological; oldest is last
```

- [ ] **Step 4: Run tests**

```bash
cd science && uv run pytest tests/test_wander_provenance.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/wander/provenance.py \
        science/tests/test_wander_provenance.py
git commit -m "feat(wander): resolve source path and created date from provenance + git"
```

---

## Task 3: Neighbors and active references

**Files:**
- Create: `science/src/science_tool/wander/neighbors.py`
- Create: `science/src/science_tool/wander/references.py`
- Create: `science/tests/test_wander_neighbors_references.py`

Two read-only graph queries: neighbors (incoming + outgoing edges around an entity, with `sci:bearsOn` uncapped and other predicates capped at 10 each direction) and active references (subjects of kind `task` or `hypothesis` whose object is this entity, excluding archived/completed tasks).

- [ ] **Step 1: Write the failing test**

Create `science/tests/test_wander_neighbors_references.py`:

```python
from __future__ import annotations

from rdflib import Dataset, Literal, URIRef
from rdflib.namespace import RDF, SKOS

from science_tool.graph.io import PROJECT_NS, SCI_NS

from science_tool.wander.neighbors import neighbors_for
from science_tool.wander.references import active_references_for


def _u(path: str) -> URIRef:
    return URIRef(PROJECT_NS[path])


def test_neighbors_split_bears_on_from_other_predicates() -> None:
    dataset = Dataset()
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
    target = _u("hypothesis/h1")
    knowledge.add((target, RDF.type, SCI_NS.Hypothesis))
    a, b = _u("article/a"), _u("article/b")
    knowledge.add((a, SCI_NS.bearsOn, target))
    knowledge.add((b, SCI_NS.bearsOn, target))
    related = _u("hypothesis/h2")
    knowledge.add((target, SCI_NS.relatedTo, related))

    result = neighbors_for(target, dataset)

    assert sorted(result.bears_on_incoming) == ["article:a", "article:b"]
    assert result.bears_on_outgoing == []
    other_outgoing_ids = [edge.neighbor_id for edge in result.other_outgoing]
    assert "hypothesis:h2" in other_outgoing_ids


def test_neighbors_caps_other_predicates_at_10_each_direction() -> None:
    dataset = Dataset()
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
    target = _u("hypothesis/h1")
    knowledge.add((target, RDF.type, SCI_NS.Hypothesis))
    for i in range(15):
        knowledge.add((target, SCI_NS.relatedTo, _u(f"hypothesis/h{i + 100}")))

    result = neighbors_for(target, dataset)

    assert len(result.other_outgoing) == 10


def test_active_references_returns_referencing_tasks_and_hypotheses() -> None:
    dataset = Dataset()
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
    target = _u("proposition/p1")
    knowledge.add((target, RDF.type, SCI_NS.Proposition))
    referencing_task = _u("task/t1")
    knowledge.add((referencing_task, RDF.type, SCI_NS.Task))
    knowledge.add((referencing_task, SKOS.related, target))
    referencing_hyp = _u("hypothesis/h1")
    knowledge.add((referencing_hyp, RDF.type, SCI_NS.Hypothesis))
    knowledge.add((referencing_hyp, SCI_NS.bearsOn, target))
    unrelated_dataset = _u("dataset/d1")
    knowledge.add((unrelated_dataset, RDF.type, SCI_NS.Dataset))
    knowledge.add((unrelated_dataset, SCI_NS.bearsOn, target))

    refs = active_references_for(target, dataset)

    ids = sorted(ref.entity_id for ref in refs)
    assert ids == ["hypothesis:h1", "task:t1"]


def test_active_references_excludes_archived_or_completed_tasks() -> None:
    dataset = Dataset()
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
    target = _u("proposition/p1")
    archived_task = _u("task/old")
    knowledge.add((archived_task, RDF.type, SCI_NS.Task))
    knowledge.add((archived_task, SCI_NS.projectStatus, Literal("archived")))
    knowledge.add((archived_task, SKOS.related, target))
    completed_task = _u("task/done")
    knowledge.add((completed_task, RDF.type, SCI_NS.Task))
    knowledge.add((completed_task, SCI_NS.projectStatus, Literal("completed")))
    knowledge.add((completed_task, SKOS.related, target))

    assert active_references_for(target, dataset) == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd science && uv run pytest tests/test_wander_neighbors_references.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `neighbors.py`**

Create `science/src/science_tool/wander/neighbors.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field

from rdflib import Dataset, URIRef

from science_tool.addressing import canonical_id_from_entity_uri
from science_tool.graph.io import PROJECT_NS, SCI_NS

OTHER_PREDICATE_CAP = 10


@dataclass(frozen=True)
class NeighborEdge:
    predicate_short: str
    neighbor_id: str
    neighbor_uri: str


@dataclass
class NeighborSet:
    bears_on_incoming: list[str] = field(default_factory=list)
    bears_on_outgoing: list[str] = field(default_factory=list)
    other_incoming: list[NeighborEdge] = field(default_factory=list)
    other_outgoing: list[NeighborEdge] = field(default_factory=list)


def neighbors_for(entity_uri: URIRef, dataset: Dataset) -> NeighborSet:
    """Return neighbors split by direction and predicate, with capping per spec."""
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
    result = NeighborSet()

    for subj in knowledge.subjects(SCI_NS.bearsOn, entity_uri):
        eid = canonical_id_from_entity_uri(str(subj))
        if eid:
            result.bears_on_incoming.append(eid)
    for obj in knowledge.objects(entity_uri, SCI_NS.bearsOn):
        eid = canonical_id_from_entity_uri(str(obj))
        if eid:
            result.bears_on_outgoing.append(eid)

    for subj, pred, _obj in knowledge.triples((None, None, entity_uri)):
        if pred == SCI_NS.bearsOn:
            continue
        eid = canonical_id_from_entity_uri(str(subj))
        if eid is None:
            continue
        if len(result.other_incoming) >= OTHER_PREDICATE_CAP:
            break
        result.other_incoming.append(NeighborEdge(_short(pred), eid, str(subj)))

    for _subj, pred, obj in knowledge.triples((entity_uri, None, None)):
        if pred == SCI_NS.bearsOn:
            continue
        if not isinstance(obj, URIRef):
            continue
        eid = canonical_id_from_entity_uri(str(obj))
        if eid is None:
            continue
        if len(result.other_outgoing) >= OTHER_PREDICATE_CAP:
            break
        result.other_outgoing.append(NeighborEdge(_short(pred), eid, str(obj)))

    result.bears_on_incoming.sort()
    result.bears_on_outgoing.sort()
    return result


def _short(predicate_uri: URIRef) -> str:
    text = str(predicate_uri)
    for sep in ("#", "/"):
        idx = text.rfind(sep)
        if idx != -1:
            return text[idx + 1 :]
    return text
```

- [ ] **Step 4: Implement `references.py`**

Create `science/src/science_tool/wander/references.py`:

```python
from __future__ import annotations

from dataclasses import dataclass

from rdflib import Dataset, URIRef
from rdflib.namespace import RDF

from science_tool.addressing import canonical_id_from_entity_uri
from science_tool.graph.io import PROJECT_NS, SCI_NS

INACTIVE_TASK_STATUSES = frozenset({"archived", "completed", "retired", "deferred"})


@dataclass(frozen=True)
class Reference:
    entity_id: str
    kind: str  # "task" | "hypothesis"


def active_references_for(entity_uri: URIRef, dataset: Dataset) -> list[Reference]:
    """Return tasks/hypotheses that reference this entity (excluding inactive tasks)."""
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
    references: list[Reference] = []
    for subj, _pred, _obj in knowledge.triples((None, None, entity_uri)):
        if not isinstance(subj, URIRef):
            continue
        eid = canonical_id_from_entity_uri(str(subj))
        if eid is None:
            continue
        kind, _, _ = eid.partition(":")
        if kind not in ("task", "hypothesis"):
            continue
        if kind == "task" and _is_inactive_task(knowledge, subj):
            continue
        references.append(Reference(entity_id=eid, kind=kind))
    # Deduplicate (a referencing entity may appear via multiple predicates)
    seen: dict[str, Reference] = {}
    for ref in references:
        seen.setdefault(ref.entity_id, ref)
    return sorted(seen.values(), key=lambda r: r.entity_id)


def _is_inactive_task(knowledge, task_uri: URIRef) -> bool:
    for status_literal in knowledge.objects(task_uri, SCI_NS.projectStatus):
        if str(status_literal).lower() in INACTIVE_TASK_STATUSES:
            return True
    return False
```

- [ ] **Step 5: Run tests**

```bash
cd science && uv run pytest tests/test_wander_neighbors_references.py -v
```

Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/wander/neighbors.py \
        science/src/science_tool/wander/references.py \
        science/tests/test_wander_neighbors_references.py
git commit -m "feat(wander): extract neighbors and active references from graph"
```

---

## Task 4: ContextBundle assembly

**Files:**
- Create: `science/src/science_tool/wander/context.py`
- Create: `science/tests/test_wander_context.py`

Combine the candidate, the graph lookups (`source_path`, `created_date`, `neighbors`, `active_references`), and the filesystem reads (`mtime`, `content_length`) into one `ContextBundle` dataclass per sampled entity. This is the structure the skeleton renderer and the stub-smell logic both consume.

- [ ] **Step 1: Write the failing test**

Create `science/tests/test_wander_context.py`:

```python
from __future__ import annotations

from datetime import date
from pathlib import Path

from rdflib import Dataset, Literal, URIRef
from rdflib.namespace import RDF, SKOS, XSD

from science_tool.graph.io import PROJECT_NS, SCI_NS

from science_tool.wander.context import assemble_bundle
from science_tool.wander.sampling import sample_for_walk
from science_tool.wander.provenance import PROV_WAS_DERIVED_FROM, SCHEMA_IDENTIFIER


def _u(path: str) -> URIRef:
    return URIRef(PROJECT_NS[path])


def _build_dataset(tmp_path: Path) -> tuple[Dataset, Path]:
    dataset = Dataset()
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
    provenance = dataset.graph(PROJECT_NS["graph/provenance"])

    h1 = _u("hypothesis/h1")
    knowledge.add((h1, RDF.type, SCI_NS.Hypothesis))
    knowledge.add((h1, SKOS.prefLabel, Literal("First")))
    knowledge.add((h1, SCI_NS.freshnessState, Literal("fresh")))

    source_file = tmp_path / "doc" / "h1.md"
    source_file.parent.mkdir(parents=True)
    source_file.write_text("a" * 200)
    source_uri = URIRef(PROJECT_NS["source/doc_h1.md"])
    provenance.add((h1, PROV_WAS_DERIVED_FROM, source_uri))
    provenance.add((source_uri, SCHEMA_IDENTIFIER, Literal(str(source_file))))
    return dataset, source_file


def test_bundle_includes_candidate_components_neighbors_filesystem(tmp_path: Path) -> None:
    dataset, source_file = _build_dataset(tmp_path)

    candidates = sample_for_walk_from_dataset(dataset)  # tiny helper below
    bundle = assemble_bundle(candidates[0], dataset, repo_root=tmp_path)

    assert bundle.entity_id == "hypothesis:h1"
    assert bundle.label == "First"
    assert bundle.kind == "hypothesis"
    assert bundle.weight > 0
    assert bundle.components["incoming_bears_on"] == 0.0
    assert bundle.source_path == str(source_file)
    assert bundle.content_length == 200
    assert bundle.mtime is not None
    assert bundle.neighbors.bears_on_incoming == []
    assert bundle.active_references == []


def test_bundle_omits_filesystem_fields_when_no_source(tmp_path: Path) -> None:
    dataset = Dataset()
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
    h1 = _u("hypothesis/h1")
    knowledge.add((h1, RDF.type, SCI_NS.Hypothesis))
    knowledge.add((h1, SKOS.prefLabel, Literal("First")))
    knowledge.add((h1, SCI_NS.freshnessState, Literal("fresh")))

    candidates = sample_for_walk_from_dataset(dataset)
    bundle = assemble_bundle(candidates[0], dataset, repo_root=tmp_path)

    assert bundle.source_path is None
    assert bundle.mtime is None
    assert bundle.content_length is None


def sample_for_walk_from_dataset(dataset: Dataset):
    # Local helper: avoid file IO in unit tests by sampling directly from a Dataset.
    from science_tool.graph.attention import (
        compute_attention_candidates,
        weighted_sample_without_replacement,
    )
    candidates = compute_attention_candidates(dataset, today=date(2026, 5, 9))
    return weighted_sample_without_replacement(candidates, limit=len(candidates), seed=0)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd science && uv run pytest tests/test_wander_context.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `context.py`**

Create `science/src/science_tool/wander/context.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Mapping

from rdflib import Dataset, URIRef

from science_tool.graph.attention import AttentionCandidate

from science_tool.wander.neighbors import NeighborSet, neighbors_for
from science_tool.wander.provenance import created_date_for, source_path_for
from science_tool.wander.references import Reference, active_references_for


@dataclass
class ContextBundle:
    entity_id: str
    uri: str
    kind: str
    label: str
    freshness_state: str
    weight: float
    components: Mapping[str, float]
    source_path: str | None
    mtime: date | None
    content_length: int | None
    created_date: date | None
    neighbors: NeighborSet
    active_references: list[Reference]


def assemble_bundle(
    candidate: AttentionCandidate,
    dataset: Dataset,
    *,
    repo_root: Path | None = None,
) -> ContextBundle:
    """Combine an `AttentionCandidate` with graph + filesystem context."""
    entity_uri = URIRef(candidate.uri)
    source_path = source_path_for(entity_uri, dataset)
    mtime: date | None = None
    content_length: int | None = None
    if source_path is not None:
        path = Path(source_path)
        if path.exists():
            mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).date()
            content_length = len(path.read_text(errors="replace"))

    return ContextBundle(
        entity_id=candidate.entity_id,
        uri=candidate.uri,
        kind=candidate.kind,
        label=candidate.label,
        freshness_state=candidate.freshness_state,
        weight=candidate.weight,
        components=dict(candidate.components),
        source_path=source_path,
        mtime=mtime,
        content_length=content_length,
        created_date=created_date_for(
            entity_uri, dataset, source_path=source_path, repo_root=repo_root
        ),
        neighbors=neighbors_for(entity_uri, dataset),
        active_references=active_references_for(entity_uri, dataset),
    )
```

- [ ] **Step 4: Run tests**

```bash
cd science && uv run pytest tests/test_wander_context.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/wander/context.py \
        science/tests/test_wander_context.py
git commit -m "feat(wander): assemble ContextBundle from candidate + graph + disk"
```

---

## Task 5: Stub-smell signals

**Files:**
- Create: `science/src/science_tool/wander/stub_smell.py`
- Create: `science/tests/test_wander_stub_smell.py`

Pure function on a `ContextBundle`. Computes the four signals from the spec (§5.3) and a composite `is_stub_candidate` flag that is true only when all four hold. No I/O, no graph queries — everything is already in the bundle.

- [ ] **Step 1: Write the failing test**

Create `science/tests/test_wander_stub_smell.py`:

```python
from __future__ import annotations

from datetime import date

from science_tool.wander.context import ContextBundle
from science_tool.wander.neighbors import NeighborSet
from science_tool.wander.stub_smell import compute_stub_signals


def _bundle(**overrides) -> ContextBundle:
    base = dict(
        entity_id="hypothesis:h1",
        uri="https://example.org/hypothesis/h1",
        kind="hypothesis",
        label="x",
        freshness_state="fresh",
        weight=0.5,
        components={},
        source_path=None,
        mtime=None,
        content_length=None,
        created_date=None,
        neighbors=NeighborSet(),
        active_references=[],
    )
    base.update(overrides)
    return ContextBundle(**base)


def test_stub_candidate_when_all_four_signals_hold() -> None:
    bundle = _bundle(
        created_date=date(2026, 1, 1),
        content_length=120,
        mtime=date(2026, 1, 1),
    )

    signals = compute_stub_signals(bundle, today=date(2026, 5, 9))

    assert signals.older_than_60_days is True
    assert signals.no_incoming_bears_on is True
    assert signals.no_active_references is True
    assert signals.short_or_unchanged is True
    assert signals.is_stub_candidate is True


def test_not_a_candidate_when_recently_created() -> None:
    bundle = _bundle(created_date=date(2026, 5, 1), content_length=10)
    signals = compute_stub_signals(bundle, today=date(2026, 5, 9))
    assert signals.older_than_60_days is False
    assert signals.is_stub_candidate is False


def test_not_a_candidate_when_has_active_reference() -> None:
    from science_tool.wander.references import Reference
    bundle = _bundle(
        created_date=date(2026, 1, 1),
        active_references=[Reference(entity_id="task:t1", kind="task")],
        content_length=10,
    )
    signals = compute_stub_signals(bundle, today=date(2026, 5, 9))
    assert signals.no_active_references is False
    assert signals.is_stub_candidate is False


def test_not_a_candidate_when_has_incoming_bears_on() -> None:
    bundle = _bundle(
        created_date=date(2026, 1, 1),
        neighbors=NeighborSet(bears_on_incoming=["article:a"]),
        content_length=10,
    )
    signals = compute_stub_signals(bundle, today=date(2026, 5, 9))
    assert signals.no_incoming_bears_on is False
    assert signals.is_stub_candidate is False


def test_long_and_modified_content_is_not_short_or_unchanged() -> None:
    bundle = _bundle(
        created_date=date(2026, 1, 1),
        content_length=2000,
        mtime=date(2026, 4, 1),  # modified after creation
    )
    signals = compute_stub_signals(bundle, today=date(2026, 5, 9))
    assert signals.short_or_unchanged is False
    assert signals.is_stub_candidate is False


def test_missing_inputs_default_to_not_a_candidate() -> None:
    # No created_date, no content_length: cannot prove old/short, so not a candidate.
    bundle = _bundle()
    signals = compute_stub_signals(bundle, today=date(2026, 5, 9))
    assert signals.is_stub_candidate is False
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd science && uv run pytest tests/test_wander_stub_smell.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `stub_smell.py`**

Create `science/src/science_tool/wander/stub_smell.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from science_tool.wander.context import ContextBundle

STALE_THRESHOLD_DAYS = 60
SHORT_CONTENT_THRESHOLD = 500


@dataclass(frozen=True)
class StubSignals:
    older_than_60_days: bool
    no_incoming_bears_on: bool
    no_active_references: bool
    short_or_unchanged: bool

    @property
    def is_stub_candidate(self) -> bool:
        return (
            self.older_than_60_days
            and self.no_incoming_bears_on
            and self.no_active_references
            and self.short_or_unchanged
        )


def compute_stub_signals(bundle: ContextBundle, *, today: date) -> StubSignals:
    older = (
        bundle.created_date is not None
        and (today - bundle.created_date).days > STALE_THRESHOLD_DAYS
    )
    short_or_unchanged = False
    if bundle.content_length is not None and bundle.content_length < SHORT_CONTENT_THRESHOLD:
        short_or_unchanged = True
    elif bundle.created_date is not None and bundle.mtime is not None and bundle.mtime <= bundle.created_date:
        short_or_unchanged = True

    return StubSignals(
        older_than_60_days=older,
        no_incoming_bears_on=not bundle.neighbors.bears_on_incoming,
        no_active_references=not bundle.active_references,
        short_or_unchanged=short_or_unchanged,
    )
```

- [ ] **Step 4: Run tests**

```bash
cd science && uv run pytest tests/test_wander_stub_smell.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/wander/stub_smell.py \
        science/tests/test_wander_stub_smell.py
git commit -m "feat(wander): compute stub-smell signals from context bundle"
```

---

## Task 6: Skeleton renderers (markdown + JSON)

**Files:**
- Create: `science/src/science_tool/wander/skeleton.py`
- Create: `science/tests/test_wander_skeleton.py`

Render the markdown report skeleton from the spec's §6 template and a parallel JSON serialization. The markdown writes the per-entity context blocks inline (so the agent reads them without re-querying) and leaves review prose, pairwise, prune, spawned-tasks sections as empty headings ready to fill in.

- [ ] **Step 1: Write the failing test**

Create `science/tests/test_wander_skeleton.py`:

```python
from __future__ import annotations

import json
from datetime import date

import yaml

from science_tool.wander.context import ContextBundle
from science_tool.wander.neighbors import NeighborEdge, NeighborSet
from science_tool.wander.references import Reference
from science_tool.wander.skeleton import render_json, render_markdown_skeleton
from science_tool.wander.stub_smell import compute_stub_signals


def _bundle(entity_id: str = "hypothesis:h1", **overrides) -> ContextBundle:
    base = dict(
        entity_id=entity_id,
        uri=f"https://example.org/{entity_id.replace(':', '/')}",
        kind=entity_id.split(":")[0],
        label="Sample label",
        freshness_state="fresh",
        weight=1.25,
        components={"incoming_bears_on": 0.0, "days_since_last_review": 30.0},
        source_path="doc/h1.md",
        mtime=date(2026, 4, 1),
        content_length=412,
        created_date=date(2026, 1, 1),
        neighbors=NeighborSet(other_outgoing=[NeighborEdge("relatedTo", "hypothesis:h2", "u")]),
        active_references=[Reference(entity_id="task:t1", kind="task")],
    )
    base.update(overrides)
    return ContextBundle(**base)


def test_markdown_skeleton_has_required_sections_and_frontmatter() -> None:
    bundles = [_bundle("hypothesis:h1"), _bundle("hypothesis:h2"), _bundle("proposition:p1")]
    today = date(2026, 5, 9)
    bundles_with_signals = [(b, compute_stub_signals(b, today=today)) for b in bundles]

    text = render_markdown_skeleton(
        walk_id="2026-05-09-1430",
        walk_date=today,
        seed=42,
        n=3,
        bundles_with_signals=bundles_with_signals,
    )

    parts = text.split("---\n", 2)
    assert parts[0] == ""
    frontmatter = yaml.safe_load(parts[1])
    assert frontmatter["walk_id"] == "2026-05-09-1430"
    assert frontmatter["seed"] == 42
    assert frontmatter["n"] == 3
    assert frontmatter["sampled"] == ["hypothesis:h1", "hypothesis:h2", "proposition:p1"]

    body = parts[2]
    for heading in (
        "## Sample",
        "## Per-entity review",
        "## Pairwise connections",
        "## Prune candidates",
        "## Spawned tasks",
    ):
        assert heading in body
    # Pairwise headings: 3 pairs
    assert body.count("### hypothesis:h1 ↔ hypothesis:h2") == 1
    assert body.count("### hypothesis:h1 ↔ proposition:p1") == 1
    assert body.count("### hypothesis:h2 ↔ proposition:p1") == 1
    # Per-entity context block must surface the stub signals so the agent sees them
    assert "stub-smell signals" in body.lower()


def test_json_serialization_round_trips_bundle_fields() -> None:
    bundle = _bundle()
    today = date(2026, 5, 9)
    payload = render_json(
        walk_id="2026-05-09-1430",
        walk_date=today,
        seed=42,
        n=1,
        bundles_with_signals=[(bundle, compute_stub_signals(bundle, today=today))],
    )

    parsed = json.loads(payload)
    assert parsed["walk_id"] == "2026-05-09-1430"
    assert parsed["bundles"][0]["entity_id"] == "hypothesis:h1"
    assert parsed["bundles"][0]["stub_signals"]["is_stub_candidate"] is False
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd science && uv run pytest tests/test_wander_skeleton.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `skeleton.py`**

Create `science/src/science_tool/wander/skeleton.py`:

```python
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date
from itertools import combinations
from typing import Iterable

from science_tool.wander.context import ContextBundle
from science_tool.wander.stub_smell import StubSignals

BundleWithSignals = tuple[ContextBundle, StubSignals]


def render_markdown_skeleton(
    *,
    walk_id: str,
    walk_date: date,
    seed: int | None,
    n: int,
    bundles_with_signals: list[BundleWithSignals],
) -> str:
    sampled_ids = [b.entity_id for b, _ in bundles_with_signals]
    lines: list[str] = []
    lines.append("---")
    lines.append(f"date: {walk_date.isoformat()}")
    lines.append(f"walk_id: {walk_id}")
    lines.append(f"seed: {seed if seed is not None else 'null'}")
    lines.append(f"n: {n}")
    lines.append(f"sampled: [{', '.join(sampled_ids)}]")
    lines.append("---")
    lines.append("")
    lines.append(f"# Wander · {walk_date.isoformat()} ({walk_id})")
    lines.append("")
    lines.append("## Sample")
    lines.append("")
    lines.append("| ID | Kind | Weight | Last reviewed (days) |")
    lines.append("| --- | --- | --- | --- |")
    for bundle, _ in bundles_with_signals:
        days = bundle.components.get("days_since_last_review", "")
        lines.append(f"| {bundle.entity_id} | {bundle.kind} | {bundle.weight:.4f} | {days} |")
    lines.append("")
    lines.append("## Per-entity review")
    lines.append("")
    for bundle, signals in bundles_with_signals:
        lines.extend(_render_entity_block(bundle, signals))
        lines.append("")
    lines.append("## Pairwise connections")
    lines.append("")
    for left, right in combinations(bundles_with_signals, 2):
        lines.append(f"### {left[0].entity_id} ↔ {right[0].entity_id}")
        lines.append("")
        lines.append("_(agent: fill in — or note 'no obvious connection')_")
        lines.append("")
    lines.append("## Prune candidates")
    lines.append("")
    lines.append("_(agent: list flagged stubs from the per-entity review, or 'none')_")
    lines.append("")
    lines.append("## Spawned tasks")
    lines.append("")
    lines.append("_(populated only when --apply was passed)_")
    lines.append("")
    return "\n".join(lines)


def _render_entity_block(bundle: ContextBundle, signals: StubSignals) -> list[str]:
    out: list[str] = []
    out.append(f"### {bundle.entity_id} — {bundle.label}")
    out.append("")
    out.append("**Context:**")
    out.append(f"- kind: `{bundle.kind}`")
    out.append(f"- weight: {bundle.weight:.4f}")
    out.append(f"- freshness: `{bundle.freshness_state}`")
    if bundle.source_path:
        out.append(f"- source: `{bundle.source_path}`")
    if bundle.created_date:
        out.append(f"- created: {bundle.created_date.isoformat()}")
    if bundle.mtime:
        out.append(f"- mtime: {bundle.mtime.isoformat()}")
    if bundle.content_length is not None:
        out.append(f"- length: {bundle.content_length} chars")
    out.append(
        f"- bears_on (in/out): {len(bundle.neighbors.bears_on_incoming)}/{len(bundle.neighbors.bears_on_outgoing)}"
    )
    out.append(
        f"- active references: {', '.join(r.entity_id for r in bundle.active_references) or 'none'}"
    )
    out.append("")
    out.append("**Stub-smell signals:**")
    out.append(f"- older_than_60_days: {signals.older_than_60_days}")
    out.append(f"- no_incoming_bears_on: {signals.no_incoming_bears_on}")
    out.append(f"- no_active_references: {signals.no_active_references}")
    out.append(f"- short_or_unchanged: {signals.short_or_unchanged}")
    out.append(f"- **is_stub_candidate: {signals.is_stub_candidate}**")
    out.append("")
    out.append("**Gaps:** _(agent: fill in — text/code/epistemic; or 'none surfaced')_")
    out.append("")
    return out


def render_json(
    *,
    walk_id: str,
    walk_date: date,
    seed: int | None,
    n: int,
    bundles_with_signals: list[BundleWithSignals],
) -> str:
    payload = {
        "walk_id": walk_id,
        "date": walk_date.isoformat(),
        "seed": seed,
        "n": n,
        "bundles": [_bundle_to_dict(b, s) for b, s in bundles_with_signals],
    }
    return json.dumps(payload, indent=2, sort_keys=True, default=str)


def _bundle_to_dict(bundle: ContextBundle, signals: StubSignals) -> dict:
    return {
        "entity_id": bundle.entity_id,
        "uri": bundle.uri,
        "kind": bundle.kind,
        "label": bundle.label,
        "freshness_state": bundle.freshness_state,
        "weight": bundle.weight,
        "components": dict(bundle.components),
        "source_path": bundle.source_path,
        "mtime": bundle.mtime.isoformat() if bundle.mtime else None,
        "content_length": bundle.content_length,
        "created_date": bundle.created_date.isoformat() if bundle.created_date else None,
        "neighbors": {
            "bears_on_incoming": list(bundle.neighbors.bears_on_incoming),
            "bears_on_outgoing": list(bundle.neighbors.bears_on_outgoing),
            "other_incoming": [asdict(e) for e in bundle.neighbors.other_incoming],
            "other_outgoing": [asdict(e) for e in bundle.neighbors.other_outgoing],
        },
        "active_references": [asdict(r) for r in bundle.active_references],
        "stub_signals": {
            "older_than_60_days": signals.older_than_60_days,
            "no_incoming_bears_on": signals.no_incoming_bears_on,
            "no_active_references": signals.no_active_references,
            "short_or_unchanged": signals.short_or_unchanged,
            "is_stub_candidate": signals.is_stub_candidate,
        },
    }
```

- [ ] **Step 4: Run tests**

```bash
cd science && uv run pytest tests/test_wander_skeleton.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/wander/skeleton.py \
        science/tests/test_wander_skeleton.py
git commit -m "feat(wander): render markdown skeleton and JSON output"
```

---

## Task 7: CLI subcommand wiring

**Files:**
- Create: `science/src/science_tool/wander/cli.py`
- Modify: `science/src/science_tool/cli.py` (register the command)
- Create: `science/tests/test_wander_cli.py`

Register `science wander` as a top-level command. Compose the pieces from Tasks 1-6: sample → assemble bundles → compute signals → render skeleton or JSON → write or print.

- [ ] **Step 1: Write the failing test**

Create `science/tests/test_wander_cli.py`:

```python
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest
from click.testing import CliRunner
from rdflib import Dataset, Literal, URIRef
from rdflib.namespace import RDF, SKOS, XSD

from science_tool.cli import main
from science_tool.graph.io import PROJECT_NS, SCI_NS, save_canonical_graph_dataset
from science_tool.wander.provenance import PROV_WAS_DERIVED_FROM, SCHEMA_IDENTIFIER


def _build_fixture_graph(tmp_path: Path) -> Path:
    dataset = Dataset()
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
    provenance = dataset.graph(PROJECT_NS["graph/provenance"])
    for slug, label in (("h1", "First"), ("h2", "Second"), ("h3", "Third")):
        uri = URIRef(PROJECT_NS[f"hypothesis/{slug}"])
        knowledge.add((uri, RDF.type, SCI_NS.Hypothesis))
        knowledge.add((uri, SKOS.prefLabel, Literal(label)))
        knowledge.add((uri, SCI_NS.freshnessState, Literal("fresh")))
        source_path = tmp_path / "doc" / f"{slug}.md"
        source_path.parent.mkdir(exist_ok=True)
        source_path.write_text(f"# {label}\n")
        source_uri = URIRef(PROJECT_NS[f"source/doc_{slug}.md"])
        provenance.add((uri, PROV_WAS_DERIVED_FROM, source_uri))
        provenance.add((source_uri, SCHEMA_IDENTIFIER, Literal(str(source_path))))
    graph_path = tmp_path / "knowledge" / "graph.trig"
    graph_path.parent.mkdir()
    save_canonical_graph_dataset(dataset, graph_path)
    return graph_path


def test_wander_writes_markdown_skeleton(tmp_path: Path) -> None:
    graph_path = _build_fixture_graph(tmp_path)
    out_path = tmp_path / "walk.md"

    result = CliRunner().invoke(
        main,
        [
            "wander",
            "--n", "3",
            "--seed", "42",
            "--graph-path", str(graph_path),
            "--format", "markdown",
            "--out", str(out_path),
            "--today", "2026-05-09",
        ],
    )

    assert result.exit_code == 0, result.output
    text = out_path.read_text()
    assert text.startswith("---\n")
    assert "## Per-entity review" in text
    assert "## Pairwise connections" in text


def test_wander_json_output_is_well_formed(tmp_path: Path) -> None:
    graph_path = _build_fixture_graph(tmp_path)

    result = CliRunner().invoke(
        main,
        [
            "wander",
            "--n", "2",
            "--seed", "42",
            "--graph-path", str(graph_path),
            "--format", "json",
            "--today", "2026-05-09",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["seed"] == 42
    assert len(payload["bundles"]) == 2


def test_wander_seed_is_reproducible(tmp_path: Path) -> None:
    graph_path = _build_fixture_graph(tmp_path)

    runs = []
    for _ in range(2):
        result = CliRunner().invoke(
            main,
            [
                "wander",
                "--n", "2",
                "--seed", "42",
                "--graph-path", str(graph_path),
                "--format", "json",
                "--today", "2026-05-09",
            ],
        )
        runs.append([b["entity_id"] for b in json.loads(result.output)["bundles"]])

    assert runs[0] == runs[1]


def test_wander_kind_filter_restricts_sample(tmp_path: Path) -> None:
    graph_path = _build_fixture_graph(tmp_path)

    result = CliRunner().invoke(
        main,
        [
            "wander",
            "--n", "5",
            "--seed", "42",
            "--graph-path", str(graph_path),
            "--kind", "proposition",
            "--format", "json",
            "--today", "2026-05-09",
        ],
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["bundles"] == []


def test_wander_errors_with_actionable_message_when_graph_missing(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        main,
        [
            "wander",
            "--n", "1",
            "--graph-path", str(tmp_path / "missing.trig"),
            "--today", "2026-05-09",
        ],
    )

    assert result.exit_code != 0
    assert "science graph build" in result.output
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd science && uv run pytest tests/test_wander_cli.py -v
```

Expected: FAIL — the `wander` Click command does not exist on `main`.

- [ ] **Step 3: Implement `wander/cli.py`**

Create `science/src/science_tool/wander/cli.py`:

```python
from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import click
from rdflib import Dataset

from science_tool.graph.attention import (
    compute_attention_candidates,
    weighted_sample_without_replacement,
)
from science_tool.wander.context import assemble_bundle
from science_tool.wander.sampling import WanderSamplerError
from science_tool.wander.skeleton import render_json, render_markdown_skeleton
from science_tool.wander.stub_smell import compute_stub_signals

WANDER_FORMATS: tuple[str, ...] = ("markdown", "json")


@click.command("wander")
@click.option("--n", "n", type=int, default=3, show_default=True, help="Number of entities to sample.")
@click.option("--seed", type=int, default=None, help="Reproducibility seed.")
@click.option("--kind", "kinds", multiple=True, help="Restrict candidates to one or more entity kinds.")
@click.option("--epsilon", type=float, default=0.05, show_default=True, help="Positive weight floor.")
@click.option(
    "--graph-path",
    type=click.Path(path_type=Path),
    default=Path("knowledge/graph.trig"),
    show_default=True,
)
@click.option("--format", "output_format", type=click.Choice(WANDER_FORMATS), default="markdown", show_default=True)
@click.option("--out", "out_path", type=click.Path(path_type=Path), default=None, help="Output file (markdown). Defaults to doc/meta/walks/walk-<id>.md.")
@click.option("--today", type=click.DateTime(formats=["%Y-%m-%d"]), default=None, help="Override the date used for sampling and stub-smell.")
@click.option("--repo-root", type=click.Path(path_type=Path), default=Path("."), show_default=True, help="Repo root for git-based created-date fallback.")
def wander_command(
    n: int,
    seed: int | None,
    kinds: tuple[str, ...],
    epsilon: float,
    graph_path: Path,
    output_format: str,
    out_path: Path | None,
    today: datetime | None,
    repo_root: Path,
) -> None:
    """Draw a serendipitous sample of epistemic entities and write a walk skeleton."""
    if not graph_path.exists():
        raise click.ClickException(
            f"Graph file not found at {graph_path}. Run `science graph build` first."
        )
    if n < 0:
        raise click.ClickException("--n must be >= 0")

    walk_date: date = today.date() if today is not None else date.today()
    walk_id = walk_date.strftime("%Y-%m-%d") + "-" + datetime.now().strftime("%H%M")

    try:
        dataset = Dataset()
        dataset.parse(source=str(graph_path), format="trig")
        candidates = compute_attention_candidates(
            dataset, today=walk_date, kinds=set(kinds) if kinds else None, epsilon=epsilon
        )
        sample = weighted_sample_without_replacement(candidates, limit=n, seed=seed)
    except (WanderSamplerError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    bundles = [assemble_bundle(c, dataset, repo_root=repo_root) for c in sample]
    bundles_with_signals = [(b, compute_stub_signals(b, today=walk_date)) for b in bundles]

    if output_format == "json":
        click.echo(render_json(walk_id=walk_id, walk_date=walk_date, seed=seed, n=n, bundles_with_signals=bundles_with_signals))
        return

    text = render_markdown_skeleton(
        walk_id=walk_id,
        walk_date=walk_date,
        seed=seed,
        n=n,
        bundles_with_signals=bundles_with_signals,
    )
    target = out_path or Path("doc/meta/walks") / f"walk-{walk_id}.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text)
    click.echo(str(target))
```

- [ ] **Step 4: Register the command on `main`**

Modify `science/src/science_tool/cli.py`. Add to the imports section near the other `science_tool.*` imports:

```python
from science_tool.wander.cli import wander_command
```

Then near the other `main.add_command(...)` calls (or directly after the `@click.group()`-defined `main`), register:

```python
main.add_command(wander_command)
```

If the existing CLI uses `@main.command(...)` decorators inline rather than `add_command`, locate one of those (e.g., near `attention-sample` registration) and add the equivalent registration line at module top level after `main` is defined. The exact insertion point is below the line `from science_tool.entities import (` block and after `main` exists.

- [ ] **Step 5: Run tests**

```bash
cd science && uv run pytest tests/test_wander_cli.py -v
```

Expected: 5 passed.

- [ ] **Step 6: Run the full wander test set to catch regressions across modules**

```bash
cd science && uv run pytest tests/test_wander_*.py -v
```

Expected: all wander tests pass.

- [ ] **Step 7: Commit**

```bash
git add science/src/science_tool/wander/cli.py \
        science/src/science_tool/cli.py \
        science/tests/test_wander_cli.py
git commit -m "feat(wander): add `science wander` CLI command"
```

---

## Task 8: Re-export public API

**Files:**
- Modify: `science/src/science_tool/wander/__init__.py`

Make the public surface easy to import (used by future code, slash command tools, and any downstream consumers).

- [ ] **Step 1: Update `__init__.py`**

Replace `science/src/science_tool/wander/__init__.py` with:

```python
from __future__ import annotations

from science_tool.wander.cli import wander_command
from science_tool.wander.context import ContextBundle, assemble_bundle
from science_tool.wander.neighbors import NeighborEdge, NeighborSet, neighbors_for
from science_tool.wander.references import Reference, active_references_for
from science_tool.wander.sampling import WanderSamplerError, sample_for_walk
from science_tool.wander.skeleton import render_json, render_markdown_skeleton
from science_tool.wander.stub_smell import StubSignals, compute_stub_signals

__all__ = [
    "ContextBundle",
    "NeighborEdge",
    "NeighborSet",
    "Reference",
    "StubSignals",
    "WanderSamplerError",
    "active_references_for",
    "assemble_bundle",
    "compute_stub_signals",
    "neighbors_for",
    "render_json",
    "render_markdown_skeleton",
    "sample_for_walk",
    "wander_command",
]
```

- [ ] **Step 2: Verify imports still work**

```bash
cd science && uv run python -c "from science_tool.wander import sample_for_walk, assemble_bundle, render_markdown_skeleton, wander_command; print('OK')"
```

Expected: prints `OK`.

- [ ] **Step 3: Commit**

```bash
git add science/src/science_tool/wander/__init__.py
git commit -m "feat(wander): re-export public API from package init"
```

---

## Task 9: Slash command

**Files:**
- Create: `commands/wander.md`

The slash command drives the agent loop. It:
1. Parses `$ARGUMENTS` for `--apply` (consumed) and forwards every other flag to `science wander` verbatim.
2. Generates a walk path, runs `science wander` to materialize a markdown skeleton at that path.
3. Reads the skeleton and performs the per-entity review (text/code/epistemic gaps), the pairwise connection pass, and the prune-candidates pass.
4. Edits the same file in place to fill in the empty sections.
5. If `--apply` was passed, may invoke `science tasks add` per the spec's §7 and append resulting task IDs to the **Spawned tasks** section.

- [ ] **Step 1: Create `commands/wander.md`**

```markdown
---
description: Serendipitous random-sample review loop. Draws 2-5 epistemic entities from the project graph, reviews each for gaps, looks for unappreciated pairwise connections, and writes a short walk report. Read-only by default; --apply may create tasks. See docs/plans/2026-05-09-wander-design.md.
---

# Wander · Random-sample review loop

Run a small, serendipitous review pass across the project's epistemic
entities. Sampling is weighted by the existing attention machinery
(freshness, time since last review, evidence balance). The agent reviews
each sampled entity for gaps, looks for unappreciated pairwise connections,
flags stub candidates, and writes a short report.

Use `$ARGUMENTS` for optional flags. Recognized:

- `--apply` — consumed by this slash command; permits exactly one side
  effect (creating tasks via `science tasks add`). Without it: report-only.
- `--n N` — number of entities to sample (default 3). Forwarded to CLI.
- `--seed N` — reproducibility seed. Forwarded.
- `--kind K` — restrict to entity kind(s); may repeat. Forwarded.
- `--epsilon F` — sampler weight floor. Forwarded.
- `--graph-path PATH` — override default `knowledge/graph.trig`. Forwarded.

## Phase 1: Materialize the skeleton

Generate a walk path and run the CLI:

```bash
WALK_ID="$(date +%Y-%m-%d-%H%M)"
WALK_PATH="doc/meta/walks/walk-${WALK_ID}.md"
mkdir -p doc/meta/walks
uv run science wander --format markdown --out "${WALK_PATH}" \
  <forwarded flags from $ARGUMENTS, EXCLUDING --apply>
```

If `science wander` exits non-zero with the message about `science graph
build`, surface that to the user and stop — there is no graph to walk.

## Phase 2: Read the skeleton

Read `${WALK_PATH}`. The frontmatter lists the sampled entity IDs. Each
per-entity section already contains a **Context** block (kind, weight,
source path, created date, mtime, length, neighbor counts, active
references) and a **Stub-smell signals** block with four booleans plus
`is_stub_candidate`. Use these — do not re-query the graph.

For each sampled entity, also read its source file (if `source` is set) so
the per-entity review can reference actual content, not just metadata.

## Phase 3: Per-entity review

Fill in the **Gaps:** line under each entity. Categories:

- **Text gaps:** prose quality, missing citations or provenance, broken
  cross-refs, weak or disconnected annotation.
- **Code/data gaps:** *only when the entity references implementation*
  (e.g., a hypothesis pointing at a pipeline). Look for silent failures,
  magic numbers, drift from claimed behavior. Skip if not grounded in code.
- **Epistemic gaps:** unstated assumptions, claims without support edges,
  propositions with stale verdicts.

Brief is correct. If nothing surfaces, write "no gaps surfaced."

## Phase 4: Pairwise connections

For each pair (the skeleton has one heading per pair), write one paragraph
answering:

> Is there an unappreciated connection between these two? If so, what
> would tracking it look like?

Most pairs will be "no obvious connection." Say so in one line and move
on. **Do not invent connections to fill the section.**

## Phase 5: Prune candidates

Replace the **Prune candidates** placeholder with a list of every entity
where `is_stub_candidate: true` in its Stub-smell block. Format:

```
- <entity-id> — <one-line rationale> [first flagged YYYY-MM-DD]
```

If none qualify, write `- none`.

## Phase 6: --apply (only if passed)

If `--apply` is in `$ARGUMENTS`, you may make exactly one kind of side
effect: create tasks via `science tasks add`. Two cases:

1. For pairwise connections you judge worth tracking, add a task:
   `investigate connection: <id-a> ↔ <id-b> — <one-line summary>`.
2. For each prune candidate, add a task:
   `review for deprecation: <entity-id> — reconsider on YYYY-MM-DD`
   (where the date is `today + 30 days`).

Tag each task description with `source: wander/${WALK_ID}` so it traces
back to this walk. Append the resulting task IDs under
**Spawned tasks** in the walk file.

Without `--apply`: leave **Spawned tasks** empty.

## Phase 7: Verify and report

Re-read the walk file end-to-end. Confirm:

- Every per-entity section has a non-empty `Gaps:` line.
- Every pairwise heading has a paragraph.
- `Prune candidates` and `Spawned tasks` are filled (even if "none" or empty).

Print the path of the walk file to the user.
```

- [ ] **Step 2: Smoke-test the command end-to-end (manual)**

This step is for the executor — it cannot be automated since it involves an LLM-driven agent loop. From the project root, in a terminal session with this branch checked out:

1. Confirm `knowledge/graph.trig` exists for the current project (`ls knowledge/graph.trig`). If missing, run `uv run science graph build` first.
2. Invoke the slash command in Claude Code: `/wander --n 3 --seed 42`.
3. Verify a file appeared at `doc/meta/walks/walk-YYYY-MM-DD-HHMM.md`.
4. Open it and confirm: frontmatter parses, three sampled entities, per-entity context blocks present, pairwise headings present, Gaps/Pairwise/Prune sections all filled.
5. Run `/wander --n 2 --seed 7 --apply` and confirm at least one task got created with `source: wander/<walk-id>` in its body if the agent surfaced anything actionable. If nothing surfaced, confirm Spawned tasks is empty (this is expected behavior).

- [ ] **Step 3: Commit**

```bash
git add commands/wander.md
git commit -m "feat(wander): add /wander slash command"
```

---

## Task 10: Final verification

- [ ] **Step 1: Run the full project test suite**

```bash
cd science && uv run pytest -q
```

Expected: existing test suite still passes; new wander tests included in the totals.

- [ ] **Step 2: Run the type checker / linter the project uses**

The project uses ruff (caches present at `.ruff_cache/`). Run:

```bash
cd science && uv run ruff check src/science_tool/wander tests/test_wander_*.py
```

Fix any reported issues inline. If the project also runs mypy/pyright, run that too on the new package.

- [ ] **Step 3: Manual CLI smoke test**

```bash
cd ~/d/science  # project root that has knowledge/graph.trig
uv run science wander --n 2 --seed 11 --format json --today 2026-05-09 | head -40
```

Expected: well-formed JSON with 2 bundles. If you get a graph-missing error, the project hasn't built its graph yet — that's not a regression, run `uv run science graph build` first.

- [ ] **Step 4: Confirm slash command is discoverable**

```bash
ls commands/wander.md
```

Verify the file exists and that the frontmatter `description` is present (Claude Code reads this for skill listing).

- [ ] **Step 5: Final commit (only if previous steps surfaced fixes)**

If steps 1-3 required no changes, skip this step. Otherwise:

```bash
git add -p  # review hunks
git commit -m "fix(wander): address findings from final verification"
```

---

## Notes for the executor

- **Dependency on `compute_attention_candidates`:** Tasks 1 and 7 both call into `science_tool.graph.attention`. Do not modify that module — the design explicitly chose to wrap, not extend.
- **No agent-loop tests:** The slash command is exercised by interactive use in Task 9 Step 2. Do not invent fake LLM tests.
- **TDD discipline:** Each task starts with a failing test. Run it, see it fail with the expected message, *then* implement.
- **Commits per task:** One commit per task is the minimum. If a task's implementation step took multiple intermediate commits to get tests green, that's fine — keep them as long as each commit message is honest.

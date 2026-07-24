# `skills_loaded` Truth Path + Reified Materialization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the toolkit a single, validated truth path for a plan's `skills_loaded` and materialize it as reified `sci:hasSkillLoad` records in the project graph, mirroring the `dataset_usage` precedent.

**Architecture:** `skills_loaded` stays preserved-raw on `Entity` (`extra="allow"`). During project load — where the validated generation is in hand — a shared helper validates each gen-3 plan's `skills_loaded` (shape, canonical-id grammar, duplicate-canonical), canonicalizes ids through a packaged alias table, and produces `SkillLoadRecord`s that are stashed on `ProjectSources`. A dedicated materialization pass emits them into the `graph/provenance` layer. The coverage command, packaged skill inventory, `unmapped-skill-reference` diagnostic, and real downstream data migration are all out of scope (later sub-plans / the release).

**Tech Stack:** Python 3.13, Pydantic v2, rdflib, PyYAML, hatchling packaging, pytest. Design doc: [`2026-07-24-skill-coverage-skillsloaded-design.md`](2026-07-24-skill-coverage-skillsloaded-design.md).

## Global Constraints

- No AI-attribution trailers/footers on commits (no `Co-Authored-By`, no "Generated with Claude Code").
- Composition over inheritance; explicit over defensive; fail early — no silent fallbacks; no "legacy"/"compatibility" layers; no `Unified` prefix.
- All `uv`/pytest/ruff/pyright commands run from `science/` (never the repo root). Pyright is configured once by the repo-root `pyrightconfig.json`.
- Use `~/d/` (not `/home/keith/d/` or `/mnt/ssd/Dropbox/`) for any filepaths written into docs/code.
- Work happens in the existing isolated worktree on branch `skill-coverage-skillsloaded`. Commit after each task.
- Canonical skill-name grammar (verified against every corpus leaf): `^[a-z0-9]+(-[a-z0-9]+)*$`.
- Record identity excludes `reason`; `source` is the categorical constant `"authored"`; skill URIs use `sci:skill/<canonical-name>`; records/predicates live in layer `graph/provenance`.
- Anything `skills_loaded`-related is gen-3-gated; gen-≤2 plans are preserved-raw and ignored (no validation, no record).

---

### Task 1: `SkillLoadRecord` + deterministic identity

**Files:**
- Create: `science/src/science_tool/graph/skill_loads.py`
- Test: `science/tests/test_skill_loads.py`

**Interfaces:**
- Produces: `SkillLoadRecord(plan_id: str, canonical_skill_id: str, reason: str, source: str = "authored")` with `.identity_payload() -> dict[str, str]` (excludes `reason`) and `.payload() -> dict[str, str]` (includes `reason`); `skill_load_node_uri(record) -> rdflib.URIRef`.

- [ ] **Step 1: Write the failing test**

```python
# science/tests/test_skill_loads.py
from __future__ import annotations

from science_tool.graph.skill_loads import SkillLoadRecord, skill_load_node_uri


def test_identity_excludes_reason() -> None:
    a = SkillLoadRecord(plan_id="plan:0001-x", canonical_skill_id="driver-selection", reason="one")
    b = SkillLoadRecord(plan_id="plan:0001-x", canonical_skill_id="driver-selection", reason="two")
    assert skill_load_node_uri(a) == skill_load_node_uri(b)
    assert a.source == "authored"
    assert "reason" not in a.identity_payload()
    assert a.payload()["reason"] == "one"


def test_identity_distinguishes_plan_and_skill() -> None:
    base = SkillLoadRecord(plan_id="plan:0001-x", canonical_skill_id="driver-selection", reason="r")
    other_skill = SkillLoadRecord(plan_id="plan:0001-x", canonical_skill_id="mutational-signatures-qa", reason="r")
    other_plan = SkillLoadRecord(plan_id="plan:0002-y", canonical_skill_id="driver-selection", reason="r")
    assert skill_load_node_uri(base) != skill_load_node_uri(other_skill)
    assert skill_load_node_uri(base) != skill_load_node_uri(other_plan)


def test_node_uri_is_under_project_skill_load_namespace() -> None:
    rec = SkillLoadRecord(plan_id="plan:0001-x", canonical_skill_id="driver-selection", reason="r")
    assert "skill-load/" in str(skill_load_node_uri(rec))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_skill_loads.py -v`
Expected: FAIL — `ModuleNotFoundError: science_tool.graph.skill_loads`.

- [ ] **Step 3: Write minimal implementation**

```python
# science/src/science_tool/graph/skill_loads.py
"""Truth path for a plan's `skills_loaded`: validation, canonicalization, and
reified skill-load records materialized into the graph/provenance layer.

Mirrors `dataset_usage.py`: a frozen record with a deterministic content-hash URI.
The record's identity deliberately EXCLUDES `reason` (only `plan_id`,
`canonical_skill_id`, and the categorical `source` participate), so two loads of
the same skill under one plan collide instead of minting two nodes.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from rdflib import URIRef

from science_tool.graph.store import PROJECT_NS


@dataclass(frozen=True, slots=True)
class SkillLoadRecord:
    plan_id: str
    canonical_skill_id: str
    reason: str
    source: str = "authored"  # categorical projection source (the `UsageSource` "authored" value)

    def identity_payload(self) -> dict[str, str]:
        return {
            "plan_id": self.plan_id,
            "canonical_skill_id": self.canonical_skill_id,
            "source": self.source,
        }

    def payload(self) -> dict[str, str]:
        return {**self.identity_payload(), "reason": self.reason}


def skill_load_node_uri(record: SkillLoadRecord) -> URIRef:
    payload = json.dumps(record.identity_payload(), sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return URIRef(PROJECT_NS[f"skill-load/{digest}"])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science && uv run --frozen pytest tests/test_skill_loads.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/graph/skill_loads.py science/tests/test_skill_loads.py
git commit -m "feat(graph): add SkillLoadRecord with reason-excluding deterministic identity"
```

---

### Task 2: Alias table resource + loader + `canonicalize_skill_id`

**Files:**
- Create: `science/src/science_tool/graph/skill_aliases.yaml`
- Modify: `science/src/science_tool/graph/skill_loads.py`
- Test: `science/tests/test_skill_loads.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `SKILL_NAME_RE` (`re.Pattern`); `SkillLoadValidationError(ValueError)`; `validate_skill_aliases(data: object) -> dict[str, str]`; `load_skill_aliases() -> dict[str, str]` (reads the packaged `skill_aliases.yaml`); `canonicalize_skill_id(raw_id: str, aliases: dict[str, str]) -> str`.

- [ ] **Step 1: Write the failing tests**

Append to `science/tests/test_skill_loads.py`:

```python
import pytest

from science_tool.graph.skill_loads import (
    SkillLoadValidationError,
    canonicalize_skill_id,
    load_skill_aliases,
    validate_skill_aliases,
)


def test_packaged_alias_table_loads() -> None:
    # The shipped table must parse and validate (it may be empty).
    assert isinstance(load_skill_aliases(), dict)


def test_validate_aliases_accepts_valid_map() -> None:
    assert validate_skill_aliases({"old-skill-name": "driver-selection"}) == {
        "old-skill-name": "driver-selection"
    }


def test_validate_aliases_rejects_chain() -> None:
    # A target that is itself a key is a chain (a -> b -> c); prohibited.
    with pytest.raises(SkillLoadValidationError, match="chain"):
        validate_skill_aliases({"a": "b", "b": "c"})


@pytest.mark.parametrize("bad", ["", "Bad-Case", "has_underscore", "a/b", "sci:skill/x", "-leading"])
def test_validate_aliases_rejects_non_grammar(bad: str) -> None:
    with pytest.raises(SkillLoadValidationError):
        validate_skill_aliases({bad: "driver-selection"})
    with pytest.raises(SkillLoadValidationError):
        validate_skill_aliases({"old-name": bad})


def test_validate_aliases_rejects_duplicate_keys() -> None:
    with pytest.raises(SkillLoadValidationError, match="duplicate"):
        validate_skill_aliases_yaml("old-name: driver-selection\nold-name: mutational-signatures-qa\n")


def test_canonicalize_resolves_alias() -> None:
    assert canonicalize_skill_id("old-name", {"old-name": "driver-selection"}) == "driver-selection"


def test_canonicalize_passes_through_unknown() -> None:
    assert canonicalize_skill_id("driver-selection", {}) == "driver-selection"


@pytest.mark.parametrize("bad", ["", "  ", "a/b", "sci:skill/x", "Bad"])
def test_canonicalize_rejects_malformed_post_alias_id(bad: str) -> None:
    # A raw id absent from the table is treated as canonical -> must still be grammar-checked.
    with pytest.raises(SkillLoadValidationError):
        canonicalize_skill_id(bad, {})
```

Also add this import to the top of the test file (near the other imports):

```python
from science_tool.graph.skill_loads import validate_skill_aliases_yaml
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science && uv run --frozen pytest tests/test_skill_loads.py -v`
Expected: FAIL — the new symbols do not exist.

- [ ] **Step 3: Create the packaged alias table (minimal seed)**

```yaml
# science/src/science_tool/graph/skill_aliases.yaml
# Retired-skill-id -> canonical-skill-id map, honored by the skills_loaded truth path.
# Keys and values are bare kebab-case skill names (^[a-z0-9]+(-[a-z0-9]+)*$). No chains:
# a value may not also appear as a key. Seeded minimal; real retired->canonical entries
# are added alongside the deferred downstream analysis-plan migration.
{}
```

- [ ] **Step 4: Extend `skill_loads.py`**

Add these imports to the top of `skill_loads.py` (alongside the existing ones):

```python
import re
from importlib import resources

import yaml
```

Append to `skill_loads.py`:

```python
SKILL_NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


class SkillLoadValidationError(ValueError):
    """A `skills_loaded` declaration or the alias table is structurally invalid."""


def _reject_duplicate_keys(node: yaml.Node) -> None:
    # Duplicate detection at the NODE level: yaml.compose builds the node tree without
    # constructing any Python objects (no `!!python/object` risk), so this stays safe while
    # catching a dup key that yaml.safe_load would silently collapse to last-wins.
    if not isinstance(node, yaml.MappingNode):
        return
    seen: set[str] = set()
    for key_node, _ in node.value:
        key = getattr(key_node, "value", None)
        if key in seen:
            raise SkillLoadValidationError(f"duplicate alias key {key!r}")
        seen.add(key)


def _valid_name(value: object) -> bool:
    return isinstance(value, str) and SKILL_NAME_RE.match(value) is not None


def validate_skill_aliases(data: object) -> dict[str, str]:
    if not isinstance(data, dict):
        raise SkillLoadValidationError("skill alias table must be a mapping")
    aliases: dict[str, str] = {}
    for key, value in data.items():
        if not _valid_name(key):
            raise SkillLoadValidationError(f"invalid alias key {key!r} (expected bare skill name)")
        if not _valid_name(value):
            raise SkillLoadValidationError(f"invalid alias target {value!r} for {key!r}")
        aliases[key] = value
    keys = set(aliases)
    for key, value in aliases.items():
        if value in keys:
            raise SkillLoadValidationError(
                f"alias chain: target {value!r} of {key!r} is itself an alias key"
            )
    return aliases


def validate_skill_aliases_yaml(text: str) -> dict[str, str]:
    node = yaml.compose(text, Loader=yaml.SafeLoader)
    if node is not None:
        _reject_duplicate_keys(node)
    return validate_skill_aliases(yaml.safe_load(text) or {})


def load_skill_aliases() -> dict[str, str]:
    text = resources.files("science_tool.graph").joinpath("skill_aliases.yaml").read_text(encoding="utf-8")
    return validate_skill_aliases_yaml(text)


def canonicalize_skill_id(raw_id: str, aliases: dict[str, str]) -> str:
    canonical = aliases.get(raw_id, raw_id)
    if not _valid_name(canonical):
        raise SkillLoadValidationError(
            f"invalid skill id {raw_id!r} (post-alias {canonical!r} is not a bare skill name)"
        )
    return canonical
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_skill_loads.py -v`
Expected: PASS (all Task 1 + Task 2 tests).

- [ ] **Step 6: Lint**

Run: `cd science && uv run ruff check src/science_tool/graph/skill_loads.py tests/test_skill_loads.py`
Expected: no errors.

- [ ] **Step 7: Commit**

```bash
git add science/src/science_tool/graph/skill_aliases.yaml science/src/science_tool/graph/skill_loads.py science/tests/test_skill_loads.py
git commit -m "feat(graph): add packaged skill alias table with grammar/chain/dup validation and canonicalization"
```

---

### Task 3: `build_skill_load_records` (shape validation + duplicate detection)

**Files:**
- Modify: `science/src/science_tool/graph/skill_loads.py`
- Test: `science/tests/test_skill_loads.py`

**Interfaces:**
- Consumes: `canonicalize_skill_id`, `SkillLoadRecord`, `SkillLoadValidationError` (Tasks 1–2).
- Produces: `build_skill_load_records(plan_id: str, skills_loaded: object, *, aliases: dict[str, str]) -> list[SkillLoadRecord]`.

- [ ] **Step 1: Write the failing tests**

Append to `science/tests/test_skill_loads.py`:

```python
from science_tool.graph.skill_loads import build_skill_load_records


def test_build_records_well_formed() -> None:
    records = build_skill_load_records(
        "plan:0001-x",
        [{"id": "driver-selection", "reason": "selection modeling"}],
        aliases={},
    )
    assert [(r.plan_id, r.canonical_skill_id, r.reason) for r in records] == [
        ("plan:0001-x", "driver-selection", "selection modeling")
    ]


def test_build_records_canonicalizes_via_alias() -> None:
    records = build_skill_load_records(
        "plan:0001-x",
        [{"id": "old-name", "reason": "r"}],
        aliases={"old-name": "driver-selection"},
    )
    assert records[0].canonical_skill_id == "driver-selection"


@pytest.mark.parametrize(
    "value",
    [
        "not-a-list",
        ["not-a-mapping"],
        [{"reason": "missing id"}],
        [{"id": "driver-selection"}],
        [{"id": 5, "reason": "non-string id"}],
        [{"id": "driver-selection", "reason": 5}],
        [{"id": "driver-selection", "reason": ""}],
    ],
)
def test_build_records_rejects_malformed_shape(value: object) -> None:
    with pytest.raises(SkillLoadValidationError):
        build_skill_load_records("plan:0001-x", value, aliases={})


def test_build_records_rejects_literal_duplicate() -> None:
    with pytest.raises(SkillLoadValidationError, match="duplicate canonical"):
        build_skill_load_records(
            "plan:0001-x",
            [
                {"id": "driver-selection", "reason": "a"},
                {"id": "driver-selection", "reason": "b"},
            ],
            aliases={},
        )


def test_build_records_rejects_converging_aliases() -> None:
    # Two distinct raw ids that resolve to one canonical id collide.
    with pytest.raises(SkillLoadValidationError, match="duplicate canonical"):
        build_skill_load_records(
            "plan:0001-x",
            [
                {"id": "old-name", "reason": "a"},
                {"id": "driver-selection", "reason": "b"},
            ],
            aliases={"old-name": "driver-selection"},
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science && uv run --frozen pytest tests/test_skill_loads.py -k build_records -v`
Expected: FAIL — `build_skill_load_records` does not exist.

- [ ] **Step 3: Implement**

Append to `skill_loads.py`:

```python
def build_skill_load_records(
    plan_id: str, skills_loaded: object, *, aliases: dict[str, str]
) -> list[SkillLoadRecord]:
    """Validate a plan's `skills_loaded` and produce reified records.

    Raises `SkillLoadValidationError` (a structural error surfaced at the plan
    validation gate) for a malformed shape, a malformed post-alias skill id, or a
    duplicate canonical load. Canonicalization runs through the one shared helper.
    """
    if not isinstance(skills_loaded, list):
        raise SkillLoadValidationError(f"{plan_id}: skills_loaded must be a list")
    records: list[SkillLoadRecord] = []
    seen: dict[str, str] = {}  # canonical id -> the raw id that first produced it
    for item in skills_loaded:
        if not isinstance(item, dict):
            raise SkillLoadValidationError(f"{plan_id}: skills_loaded entry must be a mapping")
        raw_id = item.get("id")
        reason = item.get("reason")
        if not isinstance(raw_id, str) or not raw_id:
            raise SkillLoadValidationError(f"{plan_id}: skills_loaded entry needs a non-empty string id")
        if not isinstance(reason, str) or not reason:
            raise SkillLoadValidationError(
                f"{plan_id}: skills_loaded entry {raw_id!r} needs a non-empty string reason"
            )
        canonical = canonicalize_skill_id(raw_id, aliases)
        if canonical in seen:
            raise SkillLoadValidationError(
                f"{plan_id}: duplicate canonical skill load {canonical!r} "
                f"(from {seen[canonical]!r} and {raw_id!r})"
            )
        seen[canonical] = raw_id
        records.append(SkillLoadRecord(plan_id=plan_id, canonical_skill_id=canonical, reason=reason))
    return records
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_skill_loads.py -v`
Expected: PASS (all tests).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/graph/skill_loads.py science/tests/test_skill_loads.py
git commit -m "feat(graph): validate skills_loaded shape and reject duplicate canonical loads"
```

---

### Task 4: Emit reified triples + register predicates

**Files:**
- Modify: `science/src/science_tool/graph/skill_loads.py`
- Modify: `science/src/science_tool/graph/store/constants.py`
- Test: `science/tests/test_skill_loads.py`

**Interfaces:**
- Consumes: `SkillLoadRecord`, `skill_load_node_uri`, `project_entity_uri` (from `dataset_usage`).
- Produces: `add_skill_load_record_to_graph(record: SkillLoadRecord, graph: rdflib.Graph) -> None`. Registered predicates `sci:hasSkillLoad`, `sci:skill`, `sci:loadReason` (layer `graph/provenance`); `sci:loadReason` added to `GRAPH_EXPORT_EDGE_METADATA_PREDICATES`.

- [ ] **Step 1: Write the failing test**

Append to `science/tests/test_skill_loads.py`:

```python
from rdflib import Graph
from rdflib import Literal as RDFLiteral
from rdflib.namespace import RDF

from science_tool.graph.skill_loads import add_skill_load_record_to_graph
from science_tool.graph.store import PROJECT_NS, SCI_NS


def test_add_record_emits_reified_triples() -> None:
    rec = SkillLoadRecord(plan_id="plan:0001-x", canonical_skill_id="driver-selection", reason="why")
    graph = Graph()
    add_skill_load_record_to_graph(rec, graph)
    node = skill_load_node_uri(rec)
    plan = PROJECT_NS["plan:0001-x"]  # project_entity_uri form for a bare `kind:slug` id
    assert (plan, SCI_NS.hasSkillLoad, node) in graph
    assert (node, RDF.type, SCI_NS.SkillLoad) in graph
    assert (node, SCI_NS.skill, SCI_NS["skill/driver-selection"]) in graph
    assert (node, SCI_NS.loadReason, RDFLiteral("why")) in graph
    assert (node, SCI_NS.usageSource, RDFLiteral("authored")) in graph


def test_registry_declares_skill_load_predicates() -> None:
    from science_tool.graph.store.constants import (
        GRAPH_EXPORT_EDGE_METADATA_PREDICATES,
        PREDICATE_REGISTRY,
    )

    declared = {entry["predicate"]: entry["layer"] for entry in PREDICATE_REGISTRY}
    for pred in ("sci:hasSkillLoad", "sci:skill", "sci:loadReason"):
        assert declared.get(pred) == "graph/provenance"
    assert SCI_NS.loadReason in GRAPH_EXPORT_EDGE_METADATA_PREDICATES
```

Note: the `plan` URI in the assertion assumes `project_entity_uri("plan:0001-x")` resolves a `kind:slug` id under `PROJECT_NS`. Confirm against `dataset_usage.project_entity_uri` when implementing; if that helper renders the URI differently, assert against `project_entity_uri("plan:0001-x")` directly instead of `PROJECT_NS["plan:0001-x"]`.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_skill_loads.py -k "reified or registry" -v`
Expected: FAIL — `add_skill_load_record_to_graph` missing; predicates unregistered.

- [ ] **Step 3: Implement the emitter**

Add to the imports at the top of `skill_loads.py`:

```python
from rdflib import Graph
from rdflib import Literal as RDFLiteral
from rdflib.namespace import RDF

from science_tool.graph.dataset_usage import project_entity_uri
from science_tool.graph.store import SCI_NS
```

(Keep the existing `from science_tool.graph.store import PROJECT_NS`; combine into one import line `from science_tool.graph.store import PROJECT_NS, SCI_NS` to satisfy ruff.)

Append to `skill_loads.py`:

```python
def add_skill_load_record_to_graph(record: SkillLoadRecord, graph: Graph) -> None:
    node = skill_load_node_uri(record)
    plan = project_entity_uri(record.plan_id)
    skill = SCI_NS[f"skill/{record.canonical_skill_id}"]
    graph.add((plan, SCI_NS.hasSkillLoad, node))
    graph.add((node, RDF.type, SCI_NS.SkillLoad))
    graph.add((node, SCI_NS.skill, skill))
    graph.add((node, SCI_NS.loadReason, RDFLiteral(record.reason)))
    graph.add((node, SCI_NS.usageSource, RDFLiteral(record.source)))
```

- [ ] **Step 4: Register the predicates**

In `science/src/science_tool/graph/store/constants.py`, immediately after the `sci:usageSource` registry entry (the dict ending at line ~226), add:

```python
    {
        "predicate": "sci:hasSkillLoad",
        "description": "Links a plan to a reified skill-load record",
        "layer": "graph/provenance",
    },
    {
        "predicate": "sci:skill",
        "description": "Skill loaded by a reified skill-load record (sci:skill/<name> URI)",
        "layer": "graph/provenance",
    },
    {
        "predicate": "sci:loadReason",
        "description": "Author-declared reason a plan loaded a skill",
        "layer": "graph/provenance",
    },
```

In the same file, in the `GRAPH_EXPORT_EDGE_METADATA_PREDICATES` frozenset, immediately after `SCI_NS.usageSource,` (line ~77), add:

```python
        SCI_NS.loadReason,
```

(Only `sci:loadReason` is a literal edge-metadata predicate. `sci:skill` and `sci:hasSkillLoad` are node→node edges and are intentionally NOT added to the metadata set — matching how `sci:dataset`/`sci:hasDatasetUsage` are omitted.)

- [ ] **Step 5: Run test to verify it passes**

Run: `cd science && uv run --frozen pytest tests/test_skill_loads.py -v`
Expected: PASS (all tests).

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/graph/skill_loads.py science/src/science_tool/graph/store/constants.py science/tests/test_skill_loads.py
git commit -m "feat(graph): emit reified skill-load triples and register provenance predicates"
```

---

### Task 5: `collect_skill_loads` + `ProjectSources.skill_loads` + load wiring

**Files:**
- Modify: `science/src/science_tool/graph/skill_loads.py`
- Modify: `science/src/science_tool/graph/sources.py`
- Test: `science/tests/test_skill_loads.py`

**Interfaces:**
- Consumes: `build_skill_load_records`, `load_skill_aliases` (Tasks 2–3); `science_model.entities.Entity`.
- Produces: `collect_skill_loads(entities: Iterable[Entity], *, generation: int | None, aliases: dict[str, str]) -> list[SkillLoadRecord]`; new field `ProjectSources.skill_loads: list[SkillLoadRecord]` (default empty), populated by `load_project_sources`.

- [ ] **Step 1: Write the failing test**

Append to `science/tests/test_skill_loads.py`:

```python
from science_model.entities import Entity, EntityType

from science_tool.graph.skill_loads import collect_skill_loads


def _plan(skills_loaded: object | None) -> Entity:
    extra = {"skills_loaded": skills_loaded} if skills_loaded is not None else {}
    return Entity(
        id="plan:0001-x",
        canonical_id="plan:0001-x",
        kind="plan",
        type=EntityType.PLAN,
        title="Plan",
        project="demo",
        ontology_terms=[],
        related=[],
        source_refs=[],
        content_preview="",
        file_path="entities/plans/0001-x.md",
        **extra,
    )


def test_collect_gen3_plan_with_skills_loaded() -> None:
    entity = _plan([{"id": "driver-selection", "reason": "r"}])
    records = collect_skill_loads([entity], generation=3, aliases={})
    assert [r.canonical_skill_id for r in records] == ["driver-selection"]


def test_collect_gen2_ignores_skills_loaded() -> None:
    entity = _plan([{"id": "driver-selection", "reason": "r"}])
    assert collect_skill_loads([entity], generation=2, aliases={}) == []
    assert collect_skill_loads([entity], generation=None, aliases={}) == []


def test_collect_ignores_non_plan_and_plans_without_field() -> None:
    plan_without = _plan(None)
    dataset = Entity(
        id="dataset:d1",
        canonical_id="dataset:d1",
        kind="dataset",
        type=EntityType.DATASET,
        title="D",
        project="demo",
        ontology_terms=[],
        related=[],
        source_refs=[],
        content_preview="",
        file_path="entities/datasets/d1.md",
        skills_loaded=[{"id": "driver-selection", "reason": "r"}],
    )
    assert collect_skill_loads([plan_without, dataset], generation=3, aliases={}) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_skill_loads.py -k collect -v`
Expected: FAIL — `collect_skill_loads` does not exist.

- [ ] **Step 3: Implement `collect_skill_loads`**

Add to the imports at the top of `skill_loads.py`:

```python
from collections.abc import Iterable

from science_model.entities import Entity
```

Append to `skill_loads.py`:

```python
def collect_skill_loads(
    entities: Iterable[Entity], *, generation: int | None, aliases: dict[str, str]
) -> list[SkillLoadRecord]:
    """Produce skill-load records for every gen-3 plan carrying `skills_loaded`.

    Gen-≤2 (or unpinned) projects produce nothing — `skills_loaded` there is
    preserved-raw and ignored. Raises `SkillLoadValidationError` on a malformed
    declaration (the structural error surfaces at load, before materialization).
    """
    if generation != 3:
        return []
    records: list[SkillLoadRecord] = []
    for entity in entities:
        if getattr(entity, "kind", None) != "plan":
            continue
        raw = getattr(entity, "skills_loaded", None)
        if raw is None:
            continue
        records.extend(build_skill_load_records(entity.canonical_id, raw, aliases=aliases))
    return records
```

- [ ] **Step 4: Add the `ProjectSources` field**

In `science/src/science_tool/graph/sources.py`, add an import near the other `science_tool.graph` imports (top of file):

```python
from science_tool.graph.skill_loads import SkillLoadRecord, collect_skill_loads, load_skill_aliases
```

In the `ProjectSources` model (class at `sources.py:186`), add the field immediately after `strict_schema_kinds` (line ~234):

```python
    # Reified skill-load records produced during load from gen-3 plans' `skills_loaded`
    # (see graph/skill_loads.py). Empty for gen-<=2 / unpinned projects. Emitted into
    # graph/provenance by materialize._add_skill_load_edges.
    skill_loads: list[SkillLoadRecord] = Field(default_factory=list)
```

- [ ] **Step 5: Wire the load path**

In `load_project_sources` (function at `sources.py:335`), immediately before the `return ProjectSources(` statement (line ~684), add:

```python
    generation = project_schema._generation if project_schema is not None else None
    skill_loads = collect_skill_loads(
        entities,
        generation=generation,
        aliases=load_skill_aliases() if generation == 3 else {},
    )
```

Then add the field to the `ProjectSources(...)` construction (after `strict_schema_kinds=...,`):

```python
        skill_loads=skill_loads,
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_skill_loads.py -v`
Expected: PASS (all tests).

- [ ] **Step 7: Lint + type-check the touched code**

Run: `cd science && uv run ruff check src/science_tool/graph/skill_loads.py src/science_tool/graph/sources.py && uv run pyright src/science_tool/graph/skill_loads.py src/science_tool/graph/sources.py`
Expected: no errors.

- [ ] **Step 8: Commit**

```bash
git add science/src/science_tool/graph/skill_loads.py science/src/science_tool/graph/sources.py science/tests/test_skill_loads.py
git commit -m "feat(graph): collect gen-3 plan skill-loads at load onto ProjectSources"
```

---

### Task 6: Materialization pass + end-to-end graph test

**Files:**
- Modify: `science/src/science_tool/graph/materialize.py`
- Test: `science/tests/test_skill_load_materialize.py`

**Interfaces:**
- Consumes: `ProjectSources.skill_loads` (Task 5); `add_skill_load_record_to_graph` (Task 4); `load_project_sources`, `build_dataset_from_sources`.
- Produces: `_add_skill_load_edges(sources: ProjectSources, *, provenance) -> None`, invoked inside `build_dataset_from_sources`.

- [ ] **Step 1: Write the failing end-to-end test**

```python
# science/tests/test_skill_load_materialize.py
from __future__ import annotations

from rdflib.namespace import RDF

from science_tool.graph.sources import load_project_sources
from science_tool.graph.materialize import build_dataset_from_sources
from science_tool.graph.store import PROJECT_NS, SCI_NS


def _write_gen3_project(root, *, skills_block: str) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "science.yaml").write_text(
        "name: demo\nknowledge_profiles:\n  local: local\nentity_schema_version: 3\n",
        encoding="utf-8",
    )
    plans = root / "entities" / "plans"
    plans.mkdir(parents=True, exist_ok=True)
    (plans / "0001-demo.md").write_text(
        "---\n"
        "id: plan:0001-demo\n"
        "kind: plan\n"
        "title: Demo analysis plan\n"
        "status: active\n"
        f"{skills_block}"
        "---\n\nBody.\n",
        encoding="utf-8",
    )


_SKILLS = "skills_loaded:\n  - id: driver-selection\n    reason: selection modeling\n"


def _provenance(root):
    sources = load_project_sources(root)
    dataset = build_dataset_from_sources(sources)
    return sources, dataset.graph(PROJECT_NS["graph/provenance"])


def test_gen3_plan_materializes_skill_load_record(tmp_path) -> None:
    _write_gen3_project(tmp_path, skills_block=_SKILLS)
    sources, provenance = _provenance(tmp_path)
    plan = PROJECT_NS["plan:0001-demo"]
    loads = list(provenance.objects(plan, SCI_NS.hasSkillLoad))
    assert len(loads) == 1
    node = loads[0]
    assert (node, RDF.type, SCI_NS.SkillLoad) in provenance
    assert (node, SCI_NS.skill, SCI_NS["skill/driver-selection"]) in provenance


def test_materialization_is_idempotent(tmp_path) -> None:
    _write_gen3_project(tmp_path, skills_block=_SKILLS)
    sources, first = _provenance(tmp_path)
    second = build_dataset_from_sources(sources).graph(PROJECT_NS["graph/provenance"])
    assert set(first) == set(second)


def test_gen2_plan_emits_no_skill_load(tmp_path) -> None:
    _write_gen3_project(tmp_path, skills_block=_SKILLS)
    # Downgrade to gen 2: skills_loaded must be ignored end-to-end.
    sci = tmp_path / "science.yaml"
    sci.write_text(sci.read_text(encoding="utf-8").replace("entity_schema_version: 3", "entity_schema_version: 2"), encoding="utf-8")
    sources, provenance = _provenance(tmp_path)
    assert sources.skill_loads == []
    assert not list(provenance.subjects(SCI_NS.hasSkillLoad, None))
```

Note on the plan URI: assert against `project_entity_uri("plan:0001-demo")` if `PROJECT_NS["plan:0001-demo"]` does not match the emitter's plan URI (confirm against Task 4's finding). Adjust both assertions consistently.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_skill_load_materialize.py -v`
Expected: FAIL — no skill-load triples are emitted (pass not wired).

- [ ] **Step 3: Add the materialization pass**

In `science/src/science_tool/graph/materialize.py`, add to the imports (near the `dataset_usage` import):

```python
from science_tool.graph.skill_loads import add_skill_load_record_to_graph
```

Add the pass next to `_add_dataset_usage_edges` (after it, ~line 1457):

```python
def _add_skill_load_edges(sources: ProjectSources, *, provenance) -> None:
    for record in sources.skill_loads:
        add_skill_load_record_to_graph(record, provenance)
```

In `build_dataset_from_sources` (function at `materialize.py:292`), immediately after the `_add_dataset_usage_edges(sources, resolver=resolver, provenance=provenance)` call (line ~396), add:

```python
    _add_skill_load_edges(sources, provenance=provenance)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science && uv run --frozen pytest tests/test_skill_load_materialize.py -v`
Expected: PASS (3 tests). If the plan-URI assertion fails, fix per the Step 1 note (use `project_entity_uri`).

- [ ] **Step 5: Full verification gate**

Run:
```bash
cd science && uv run --frozen pytest && uv run ruff check && uv run pyright
```
Expected: all green. (Watch for any predicate-registry consistency guard that checks every emitted `sci:` predicate is registered — Task 4 covers `hasSkillLoad`/`skill`/`loadReason`.)

Then the model package (no changes expected, run for safety):
```bash
cd science/model && uv run --frozen pytest && uv run ruff check
```

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/graph/materialize.py science/tests/test_skill_load_materialize.py
git commit -m "feat(graph): materialize reified skill-load edges into graph/provenance"
```

---

## Self-review notes (for the executor)

- **Spec coverage:** T1 = record + reason-excluding identity; T2 = alias table (grammar, no-chains, no-dup-keys) + canonicalization; T3 = shape validation + duplicate-canonical structural errors; T4 = reified emission (`usageSource="authored"`, `sci:skill/<name>` URI) + predicate registration; T5 = gen-3-gated load-time production onto `ProjectSources`; T6 = materialization into `graph/provenance` + idempotence + gen-2 no-op. Every design §2–§4 requirement and every "Testing approach" bullet maps to a task.
- **Out of scope (do not implement):** `unmapped-skill-reference`, coverage states, the packaged skill inventory, real alias seeding, `plan_kind` typing, the downstream analysis-plan data migration, the `science skills coverage` command.
- **Type consistency:** `build_skill_load_records(plan_id, skills_loaded, *, aliases)` and `collect_skill_loads(entities, *, generation, aliases)` are used with exactly these signatures in T5/T6. `add_skill_load_record_to_graph(record, graph)` matches `dataset_usage`'s emitter signature.
- **Known verification point:** the plan-entity URI form (`PROJECT_NS["plan:..."]` vs `project_entity_uri(...)`) is confirmed empirically in T4/T6 rather than assumed — both note the fallback.

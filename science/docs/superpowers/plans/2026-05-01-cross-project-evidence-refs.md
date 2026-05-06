# Cross-Project Evidence Refs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `evidence_refs` frontmatter support so graph materialization can represent local and cross-project evidence provenance without relaxing `source_refs`.

**Architecture:** Extend markdown source loading to carry `evidence_refs` into project entities, teach the reference audit to allow cross-project addresses only in `evidence_refs`, and emit `prov:wasDerivedFrom` edges for local, external, and cross-project evidence refs. Keep `source_refs` behavior unchanged.

**Tech Stack:** Python 3.13, Pydantic science-model entities, rdflib graph materialization, pytest, uv.

---

## File Map

| Path | Action | Responsibility |
|---|---|---|
| `science/tests/test_graph_materialize.py` | Modify | Regression tests for `source_refs` strictness and `evidence_refs` graph output |
| `science-model/src/science_model/entities.py` | Modify | Add `evidence_refs` to the shared entity schema |
| `science/src/science_tool/graph/sources.py` | Modify | Normalize `evidence_refs` from markdown frontmatter into entity raw records |
| `science/src/science_tool/graph/migrate.py` | Modify | Audit `evidence_refs`, allowing cross-project addresses while preserving local unresolved failures |
| `science/src/science_tool/graph/materialize.py` | Modify | Emit provenance edges for local/external/cross-project evidence refs |
| `science/docs/superpowers/specs/2026-05-01-cross-project-evidence-refs-design.md` | Read | Source design |

## Task 1: Red Tests

**Files:**
- Modify: `science/tests/test_graph_materialize.py`

- [x] **Step 1: Add tests for the desired behavior.**

Add these imports near the existing rdflib imports:

```python
from rdflib import URIRef
```

Add these tests after the existing source-ref provenance test near the top of
`tests/test_graph_materialize.py`:

```python
def test_source_refs_with_cross_project_address_still_fails(tmp_path: Path) -> None:
    _write_demo_project(tmp_path)
    question = tmp_path / "doc" / "questions" / "q01-demo.md"
    question.write_text(
        question.read_text(encoding="utf-8").replace(
            'source_refs: ["hypothesis:h01-demo"]',
            'source_refs: ["cbioportal:doc/background/papers/Mina2020.md"]',
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unresolved references"):
        materialize_graph(tmp_path)


def test_evidence_refs_with_cross_project_address_materializes_provenance(tmp_path: Path) -> None:
    _write_demo_project(tmp_path)
    question = tmp_path / "doc" / "questions" / "q01-demo.md"
    question.write_text(
        question.read_text(encoding="utf-8").replace(
            'source_refs: ["hypothesis:h01-demo"]',
            "\n".join(
                [
                    'source_refs: ["hypothesis:h01-demo"]',
                    'evidence_refs: ["cbioportal:doc/background/papers/Mina2020.md"]',
                ]
            ),
        ),
        encoding="utf-8",
    )

    trig_path = materialize_graph(tmp_path)
    dataset = Dataset()
    dataset.parse(trig_path, format="trig")
    provenance = dataset.graph(PROJECT_NS["graph/provenance"])

    assert (
        PROJECT_NS["question/q01-demo"],
        PROV.wasDerivedFrom,
        URIRef("cancer://cbioportal/doc/background/papers/Mina2020.md"),
    ) in provenance


def test_evidence_refs_with_local_ref_materializes_provenance(tmp_path: Path) -> None:
    _write_demo_project(tmp_path)
    question = tmp_path / "doc" / "questions" / "q01-demo.md"
    question.write_text(
        question.read_text(encoding="utf-8").replace(
            'source_refs: ["hypothesis:h01-demo"]',
            "\n".join(
                [
                    "source_refs: []",
                    'evidence_refs: ["hypothesis:h01-demo"]',
                ]
            ),
        ),
        encoding="utf-8",
    )

    trig_path = materialize_graph(tmp_path)
    dataset = Dataset()
    dataset.parse(trig_path, format="trig")
    provenance = dataset.graph(PROJECT_NS["graph/provenance"])

    assert (
        PROJECT_NS["question/q01-demo"],
        PROV.wasDerivedFrom,
        PROJECT_NS["hypothesis/h01-demo"],
    ) in provenance
```

- [x] **Step 2: Run tests and verify red.**

Run:

```bash
uv run --frozen pytest tests/test_graph_materialize.py::test_source_refs_with_cross_project_address_still_fails tests/test_graph_materialize.py::test_evidence_refs_with_cross_project_address_materializes_provenance tests/test_graph_materialize.py::test_evidence_refs_with_local_ref_materializes_provenance -q
```

Expected:
- The `source_refs` strictness test passes.
- The two `evidence_refs` tests fail because no provenance edges are emitted yet.

## Task 2: Source Loading And Audit

**Files:**
- Modify: `science-model/src/science_model/entities.py`
- Modify: `science/src/science_tool/graph/sources.py`
- Modify: `science/src/science_tool/graph/migrate.py`

- [x] **Step 1: Add `evidence_refs` to the shared entity model.**

In `science-model/src/science_model/entities.py`, add this field after
`source_refs`:

```python
evidence_refs: list[str] = Field(default_factory=list)
```

- [x] **Step 2: Teach source loading to preserve `evidence_refs`.**

In `_enrich_raw()` in `sources.py`, add:

```python
raw.setdefault("evidence_refs", [])
```

and include `"evidence_refs"` in the canonicalization loop:

```python
for ref_field in ("related", "source_refs", "evidence_refs", "same_as", "blocked_by"):
```

- [x] **Step 3: Teach audit to check `evidence_refs`.**

In `migrate.py`, import address detection:

```python
from science_tool.addressing import is_address
from science_tool.graph.store import PROJECT_ENTITY_PREFIXES
```

In `_audit_entity()`, after the `source_refs` loop, add:

```python
    for target in getattr(entity, "evidence_refs", []) or []:
        rows.extend(
            _audit_reference(
                entity,
                "evidence_refs",
                target,
                resolver,
                ext_prefixes=ext_prefixes,
                allow_cross_kind_fallback=True,
                allow_cross_project_address=True,
            )
        )
```

Extend `_audit_reference()` with a keyword-only argument:

```python
    allow_cross_project_address: bool = False,
```

and after unresolved local resolver handling starts, allow only real cross-project
addresses:

```python
    if allow_cross_project_address and _is_cross_project_address(raw_target):
        return []
```

Add:

```python
def _is_cross_project_address(raw_target: str) -> bool:
    if not is_address(raw_target):
        return False
    prefix, _ = raw_target.split(":", 1)
    return prefix not in PROJECT_ENTITY_PREFIXES
```

- [x] **Step 4: Run red tests again.**

Run:

```bash
uv run --frozen pytest tests/test_graph_materialize.py::test_source_refs_with_cross_project_address_still_fails tests/test_graph_materialize.py::test_evidence_refs_with_cross_project_address_materializes_provenance tests/test_graph_materialize.py::test_evidence_refs_with_local_ref_materializes_provenance -q
```

Expected:
- `source_refs` strictness test passes.
- `evidence_refs` tests still fail until materialization emits edges.

## Task 3: Materialize Evidence Provenance

**Files:**
- Modify: `science/src/science_tool/graph/materialize.py`

- [x] **Step 1: Add imports.**

Add:

```python
from science_tool.addressing import is_address, parse_address
```

- [x] **Step 2: Add an address URI helper.**

Near `_external_uri()`, add:

```python
def _address_uri(raw_target: str) -> URIRef:
    address = parse_address(raw_target)
    return URIRef(f"cancer://{address.project_id}/{address.artifact_id}")


def _is_cross_project_address(raw_target: str) -> bool:
    if not is_address(raw_target):
        return False
    prefix, _ = raw_target.split(":", 1)
    return prefix not in PROJECT_ENTITY_PREFIXES
```

- [x] **Step 3: Emit evidence provenance edges.**

In `_add_relations()`, after the existing `source_refs` loop, add:

```python
    for raw_target in sorted(getattr(entity, "evidence_refs", []) or []):
        if is_external_reference(raw_target, known_prefixes=ext_prefixes):
            _link_external_term(entity_uri, raw_target, bridge=bridge, ontology_catalogs=ontology_catalogs)
            continue
        if is_metadata_reference(raw_target):
            continue
        resolution = resolver.resolve(raw_target, allow_cross_kind_fallback=True)
        if resolution.status == "resolved":
            assert resolution.canonical_id is not None
            target = entity_index.get(resolution.canonical_id)
            if target is None:
                continue
            provenance.add((entity_uri, PROV.wasDerivedFrom, _entity_uri(target.canonical_id)))
            continue
        if _is_cross_project_address(raw_target):
            provenance.add((entity_uri, PROV.wasDerivedFrom, _address_uri(raw_target)))
            continue
```

- [x] **Step 4: Run the focused tests and verify green.**

Run:

```bash
uv run --frozen pytest tests/test_graph_materialize.py::test_source_refs_with_cross_project_address_still_fails tests/test_graph_materialize.py::test_evidence_refs_with_cross_project_address_materializes_provenance tests/test_graph_materialize.py::test_evidence_refs_with_local_ref_materializes_provenance -q
```

Expected:
- All three tests pass.
- Add and run one more regression proving `evidence_refs: ["hypothesis:h99-missing"]`
  still fails materialization.

## Task 4: Regression Suite And Commit

**Files:**
- Modified files from Tasks 1-3

- [x] **Step 1: Run graph materialization tests.**

Run:

```bash
uv run --frozen pytest tests/test_graph_materialize.py tests/test_graph_migrate.py tests/test_health.py -q
```

Expected:
- Tests pass.

- [x] **Step 2: Run lint for touched files.**

Run:

```bash
uv run --frozen ruff check src/science_tool/graph/materialize.py src/science_tool/graph/migrate.py src/science_tool/graph/sources.py tests/test_graph_materialize.py
```

Expected:
- No lint errors.

- [ ] **Step 3: Commit.**

Run:

```bash
git add science-model/src/science_model/entities.py science/src/science_tool/graph/materialize.py science/src/science_tool/graph/migrate.py science/src/science_tool/graph/sources.py science/tests/test_graph_materialize.py science/docs/superpowers/plans/2026-05-01-cross-project-evidence-refs.md
git commit -m "feat(graph): support cross-project evidence refs"
```

Expected:
- Commit succeeds.

## Self-Review

- Spec coverage: The plan preserves `source_refs`, adds `evidence_refs`, allows
  cross-project evidence addresses, emits provenance edges, and tests local and
  cross-project cases.
- Scope: The plan does not implement federated resolution against child graph contents.
- TDD: The implementation starts with failing tests before production changes.

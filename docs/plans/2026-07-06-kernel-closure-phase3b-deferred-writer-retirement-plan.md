# Kernel Closure Phase 3b — Deferred-Writer Retirement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Retire the last four durable graph writers (`add_article`, `add_story`, `add_paper_entity`, `add_falsification`), driving `EXPECTED_DEFERRED_WRITERS` to empty so source declarations become the sole durable writer of `knowledge/graph.trig`.

**Architecture:** Three of the four writers retire as pure surface cleanup (message-only CLI retirement for `article`/`story`; outright deletion for `paper`). The fourth — `falsification` — needs a real source form first: a new first-class `FalsificationEntity` kind (parallel to `evidence-line`) with typed-model registration, a Renderer-format template, and compiler emitters that route every triple to the `graph/knowledge` named graph (matching the retired writer and its reader). The `story` kind gains create-scaffolding wiring. A static AST guard ratchets the ledger to zero.

**Tech Stack:** Python 3, Pydantic (`science-model`), Click, rdflib, pytest. Two nested uv packages: `science/` (the `science` CLI, code under `src/science_tool/`) and `science/model/` (the `science-model` Pydantic package). Run `uv` from the package dir, never the repo root.

**Design doc:** [`2026-07-06-kernel-closure-phase3b-deferred-writer-retirement-design.md`](2026-07-06-kernel-closure-phase3b-deferred-writer-retirement-design.md)

## Global Constraints

- **Worktree:** all work happens in `.worktrees/kernel-closure-phase3b` on branch `kernel-closure-phase3b`. Verify branch before every commit.
- **Run tests from the package dir:** `cd science && uv run --frozen pytest` (CLI) and `cd science/model && uv run --frozen pytest` (model). Lint/types from `science/`: `uv run ruff check`, `uv run pyright`. Never run `uv run` from the repo root.
- **No AI-attribution trailers** on commits/PRs/comments. No `Co-Authored-By`, no "Generated with Claude Code".
- **No "legacy"/"compatibility" layers; no `Unified` prefix.** Composition over inheritance; explicit over defensive; fail early — no silent fallbacks.
- **Docs/code filepaths use `~/d/`**, not `/home/keith/` or `/mnt/ssd/Dropbox/`.
- **Falsification metadata + relations route to `graph/knowledge`, NEVER the `provenance` graph.** This is the one place falsification must *not* copy evidence-line: the reader `_load_proposition_falsifications` reads from `knowledge`.
- **Byte-parity for falsification:** `sourceOfPrediction` a literal; `supersedesClaim` a URI resolved via `_resolve_term` (URLs/CURIEs/case-preserved project refs — NOT `_entity_uri`, which lowercases/mangles); only `falsifies` is proposition-validated; the four metadata fields are unvalidated literals, and a blank field emits no triple.
- **Templates are mirrored:** every template edit applies to BOTH the packaged copy `science/model/src/science_model/templates/<kind>.md` and the repo-root mirror `templates/<kind>.md`.
- **`story` keeps its existing lifecycle** `draft/developing/mature` — do NOT adopt evidence-line's `active/retired/archived`.

---

## File Structure

**Model package (`science/model/src/science_model/`):**
- `entities.py` — add `FalsificationEntity(ProjectEntity)`; add `EntityType.FALSIFICATION`.
- `__init__.py` — export `FalsificationEntity`.
- `frontmatter.py` — add the `parse_entity_file` `falsification` branch.
- `profiles/core.py` — add the `falsification` `EntityKind` descriptor; wire the `story` descriptor; delete the `comprises` `RelationKind`.
- `templates/falsification.md` — new Renderer-format template.
- `templates/story.md` — convert to Renderer format.

**Repo-root template mirror (`templates/`):**
- `falsification.md` (new), `story.md` (converted).

**CLI package (`science/src/science_tool/`):**
- `graph/entity_registry.py` — add `"falsification": FalsificationEntity` to `CORE_KIND_MODELS`.
- `graph/materialize.py` — add `_add_falsification_metadata` + `_add_falsification_relations` and their dispatches; import `FalsificationEntity`.
- `graph/store/mutations.py` — delete all four writer functions.
- `graph/store/constants.py` — delete the `comprises` predicate-manifest entry.
- `graph/store/__init__.py`, `graph/__init__.py` — prune re-exports.
- `cli.py` — retire `graph add article/story/falsification` (message-only), delete `graph add paper`, prune imports.

**Tests (`science/tests/`):**
- `graph/test_durable_write_boundary.py` — empty the ledger.
- `test_causal.py` — migrate two falsification tests to authored fixtures.
- `test_paper_model.py` — delete writer tests, trim composition chain.
- `test_graph_cli.py` — convert article/story tests, extend the retirement-surface parametrization, add `paper` "no such command".
- `test_kind_map_equivalence.py`, `test_kind_reconciliation_registry.py` — update frozen gate literals.
- `test_graph_materialize.py` (or focused new test) — falsification materialization parity + load-source `isinstance` + `entity create`/`entity sections` coverage.

---

## Task 1: Empty the durable-writer ledger (guard RED)

Flip the ledger to empty first, establishing the ratchet. The guard stays RED (reports 4 unexpected writer sites) until Tasks 8 and 10 delete the writer functions.

**Files:**
- Modify: `science/tests/graph/test_durable_write_boundary.py:46-52`

**Interfaces:**
- Produces: `EXPECTED_DEFERRED_WRITERS: set[str]` — now empty. The guard's contract is unchanged: `actual - EXPECTED_DEFERRED_WRITERS` must be empty (no unlisted writer) and `EXPECTED_DEFERRED_WRITERS - actual` must be empty (no stale entry).

- [ ] **Step 1: Empty the ledger and update the docstring**

Replace the ledger literal (lines 46-52):

```python
# Direct writers that are KNOWN and intentionally deferred to a later
# kernel-closure phase. Phase 3b retires the final four, so this ledger is now
# EMPTY: the allowlist (`graph/materialize.py`, `graph/store/dataset.py`) is the
# entire set of durable-writer sites. The guard now asserts kernel closure is
# complete — any new direct writer outside the allowlist is a boundary violation.
EXPECTED_DEFERRED_WRITERS: set[str] = set()
```

Also update the module docstring: replace the "Phase 3a intentionally starts RED …" paragraph (lines 15-17) with:

```
Phase 3b empties the ledger. Until the four Phase-3b writer functions are
deleted (add_article / add_story / add_paper_entity / add_falsification in
graph/store/mutations.py), the guard reports them as unexpected — the RED state
that the retirement tasks clear.
```

- [ ] **Step 2: Run the guard to verify it is RED with exactly the 4 known sites**

Run: `cd science && uv run --frozen pytest tests/graph/test_durable_write_boundary.py -v`
Expected: FAIL. The assertion message lists exactly:
`['graph/store/mutations.py:add_article', 'graph/store/mutations.py:add_falsification', 'graph/store/mutations.py:add_paper_entity', 'graph/store/mutations.py:add_story']`

- [ ] **Step 3: Commit**

```bash
git add science/tests/graph/test_durable_write_boundary.py
git commit -m "test(kernel-closure): empty durable-writer ledger (Phase 3b guard RED)"
```

---

## Task 2: `FalsificationEntity` model + parse registration

Add the Pydantic model, the `EntityType` member, the package export, and the `parse_entity_file` branch (the secondary, `plan_gate.py` path). The build-path registration (`CORE_KIND_MODELS`) lands in Task 3.

**Files:**
- Modify: `science/model/src/science_model/entities.py` (add `EntityType.FALSIFICATION` near line 132; add `FalsificationEntity` after `EvidenceLineEntity` at line 996)
- Modify: `science/model/src/science_model/__init__.py` (export)
- Modify: `science/model/src/science_model/frontmatter.py` (`parse_entity_file` branch near the `EVIDENCE_LINE` branch at line 424)
- Test: `science/model/tests/test_frontmatter.py`

**Interfaces:**
- Produces: `FalsificationEntity(ProjectEntity)` with fields `falsifies: str`, `predicted: str = ""`, `observed: str = ""`, `decision: str = ""`, `source_of_prediction: str = ""`, `supersedes_claim: str | None = None`. Field names match frontmatter keys so `model_validate(raw)` populates them.
- Produces: `EntityType.FALSIFICATION = "falsification"`.

- [ ] **Step 1: Write the failing parse test**

Add to the model frontmatter test module:

```python
def test_parse_entity_file_round_trips_falsification(tmp_path: Path) -> None:
    from science_model.entities import FalsificationEntity
    from science_model.frontmatter import parse_entity_file

    path = tmp_path / "f01.md"
    path.write_text(
        "---\n"
        'id: "falsification:f01"\n'
        'kind: "falsification"\n'
        'title: "Drug does not improve recovery"\n'
        'status: "active"\n'
        'falsifies: "proposition:drug_causes_recovery"\n'
        'predicted: "Drug improves recovery time"\n'
        'observed: "No improvement in randomized follow-up"\n'
        'decision: "Reject mechanistic interpretation"\n'
        'source_of_prediction: "topic:drug-mechanism"\n'
        "related: []\n"
        "source_refs: []\n"
        "---\n\n# Falsification\n",
        encoding="utf-8",
    )

    entity = parse_entity_file(path, project_slug="demo")

    assert isinstance(entity, FalsificationEntity)
    assert entity.falsifies == "proposition:drug_causes_recovery"
    assert entity.predicted == "Drug improves recovery time"
    assert entity.decision == "Reject mechanistic interpretation"
    assert entity.source_of_prediction == "topic:drug-mechanism"
    assert entity.supersedes_claim is None
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd science/model && uv run --frozen pytest tests/test_frontmatter.py::test_parse_entity_file_round_trips_falsification -v`
Expected: FAIL — `ImportError: cannot import name 'FalsificationEntity'`.

- [ ] **Step 3: Add the `EntityType` member**

In `entities.py`, in the `EntityType` StrEnum (after `EVIDENCE_LINE = "evidence-line"`, line 132):

```python
    FALSIFICATION = "falsification"
```

- [ ] **Step 4: Add the `FalsificationEntity` class**

In `entities.py`, after the `EvidenceLineEntity` class (ends line 995), before `class InquiryEntity`:

```python
class FalsificationEntity(ProjectEntity):
    """A structured record that a proposition-backed prediction was falsified.

    Parallel to EvidenceLineEntity: a first-class entity *about* a proposition.
    ``falsifies`` is the required target proposition ref (validated at
    materialization to resolve to a sci:Proposition). The four descriptive
    fields are free-text, emitted as RDF literals. ``supersedes_claim`` is an
    optional claim ref emitted as a resolved URI. Every triple lands in the
    graph/knowledge named graph (belief provenance is deliberately not involved).
    """

    falsifies: str
    predicted: str = ""
    observed: str = ""
    decision: str = ""
    source_of_prediction: str = ""
    supersedes_claim: str | None = None
```

- [ ] **Step 5: Export from `__init__.py`**

In `science/model/src/science_model/__init__.py`, add `FalsificationEntity` to the import block from `.entities` (near `EvidenceLineEntity`, line 12) and to `__all__` (near line 94), preserving alphabetical/existing order.

- [ ] **Step 6: Add the `parse_entity_file` branch**

In `frontmatter.py`, immediately before the `EVIDENCE_LINE` branch (line 424), add:

```python
    if kind == EntityType.FALSIFICATION.value:
        return FalsificationEntity(
            **entity_kwargs,
            falsifies=cast(str, fm.get("falsifies")),  # required; pydantic raises if missing
            predicted=str(fm.get("predicted") or ""),
            observed=str(fm.get("observed") or ""),
            decision=str(fm.get("decision") or ""),
            source_of_prediction=str(fm.get("source_of_prediction") or ""),
            supersedes_claim=fm.get("supersedes_claim"),
        )
```

Add `FalsificationEntity` to the `from .entities import (...)` block at the top of `frontmatter.py` (wherever `EvidenceLineEntity` is imported).

- [ ] **Step 7: Run the test to verify it passes**

Run: `cd science/model && uv run --frozen pytest tests/test_frontmatter.py::test_parse_entity_file_round_trips_falsification -v`
Expected: PASS.

- [ ] **Step 8: Run the full model suite**

Run: `cd science/model && uv run --frozen pytest`
Expected: PASS (no regressions).

- [ ] **Step 9: Commit**

```bash
git add science/model/src/science_model/entities.py science/model/src/science_model/__init__.py science/model/src/science_model/frontmatter.py science/model/tests/test_frontmatter.py
git commit -m "feat(model): add FalsificationEntity kind + parse_entity_file branch"
```

---

## Task 3: `falsification` descriptor, `CORE_KIND_MODELS` binding, and template

Wire falsification into the build-path registry, the descriptor SSOT, and a Renderer-format template. The load-source `isinstance` test is the real proof the build path is wired — a kind absent from `CORE_KIND_MODELS` loads as a bare `ProjectEntity` and the materializer branch would never fire.

**Files:**
- Modify: `science/model/src/science_model/profiles/core.py` (add descriptor after evidence-line, line 576)
- Modify: `science/src/science_tool/graph/entity_registry.py` (import + `CORE_KIND_MODELS` entry, lines 15-32, 55-72)
- Create: `science/model/src/science_model/templates/falsification.md`
- Create: `templates/falsification.md` (repo-root mirror, byte-identical)
- Test: `science/tests/test_entity_registry.py` (load-source binding) + `science/tests/test_entities_cli.py` (`entity create`/`entity sections`)

**Interfaces:**
- Consumes: `FalsificationEntity` (Task 2).
- Produces: `CORE_KIND_MODELS["falsification"] = FalsificationEntity`; a `falsification` `EntityKind` with `template_ready=True`, `home="entities/falsifications"`, `strategy="slug"`.

- [ ] **Step 1: Write the failing load-source integration test**

Add to `science/tests/test_entity_registry.py` (create the file if absent, mirroring an existing registry test's imports):

```python
def test_load_project_sources_binds_falsification_entity(tmp_path: Path) -> None:
    """A kind: falsification source file loads as a FalsificationEntity (not bare
    ProjectEntity) — proves the CORE_KIND_MODELS build-path binding."""
    from science_model.entities import FalsificationEntity

    from _fixtures.entity_helpers import seed_project, write_markdown_entity
    from science_tool.graph.sources import load_project_sources

    seed_project(tmp_path)
    write_markdown_entity(
        tmp_path,
        "entities/propositions/p1.md",
        {"id": "proposition:p1", "kind": "proposition", "title": "Drug improves recovery",
         "status": "active", "source_refs": []},
        "Drug improves recovery\n",
    )
    write_markdown_entity(
        tmp_path,
        "entities/falsifications/f01.md",
        {"id": "falsification:f01", "kind": "falsification", "title": "Refuted",
         "status": "active", "falsifies": "proposition:p1",
         "predicted": "improves", "observed": "no change", "decision": "reject",
         "source_of_prediction": "topic:x", "related": [], "source_refs": []},
        "Refuted\n",
    )

    sources = load_project_sources(tmp_path)

    loaded = [e for e in sources.entities if e.canonical_id == "falsification:f01"]
    assert len(loaded) == 1
    assert isinstance(loaded[0], FalsificationEntity)
    assert loaded[0].falsifies == "proposition:p1"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_entity_registry.py::test_load_project_sources_binds_falsification_entity -v`
Expected: FAIL — the loaded entity is a `ProjectEntity`, not `FalsificationEntity` (kind not yet in `CORE_KIND_MODELS`), or the descriptor is missing so the kind is unregistered.

- [ ] **Step 3: Add the `falsification` descriptor**

In `profiles/core.py`, after the `evidence-line` `EntityKind` (line 576, before the `unknown` sentinel at line 577):

```python
        EntityKind(
            name="falsification",
            canonical_prefix="falsification",
            layer="layer/core",
            description="A structured record that a proposition-backed prediction was falsified.",
            entity_class=EntityClass.EPISTEMIC,
            category=KindCategory.AUTHORED_CORE,
            template_ready=True,
            home="entities/falsifications",
            strategy="slug",
            default_status="draft",
            statuses=["draft", "active", "retired", "archived"],
        ),
```

- [ ] **Step 4: Bind `CORE_KIND_MODELS["falsification"]`**

In `graph/entity_registry.py`, add `FalsificationEntity` to the `from science_model.entities import (...)` block (lines 15-32, alphabetical near `EvidenceLineEntity`), and add to `CORE_KIND_MODELS` (after `"evidence-line": EvidenceLineEntity,`, line 68):

```python
    "falsification": FalsificationEntity,
```

- [ ] **Step 5: Create the Renderer-format template (packaged copy)**

Create `science/model/src/science_model/templates/falsification.md`:

```markdown
---
id: "falsification:{{slug}}"
kind: "falsification"
title: "{{title}}"
status: "{{status}}"
falsifies: "proposition:CHANGEME"
predicted: ""
observed: ""
decision: ""
source_of_prediction: ""
related: []
source_refs: []
created: "{{created}}"
updated: "{{updated}}"
_template:
  frontmatter:
    id: { from: entity_id }
    kind: { default: "falsification" }
    title: { from: title }
    status: { from: status }
    falsifies: { default: "proposition:CHANGEME" }
    predicted: { default: "" }
    observed: { default: "" }
    decision: { default: "" }
    source_of_prediction: { default: "" }
    supersedes_claim: { omit: true }
    related: { from: related }
    source_refs: { from: source_refs }
    created: { from: created }
    updated: { from: updated }
  sections:
    - { key: what-was-predicted, name: "What was predicted", required: true }
    - { key: what-was-observed, name: "What was observed", required: true }
    - { key: decision, name: "Decision", required: true }
    - { key: source-of-prediction, name: "Source of prediction", required: false }
---

# Falsification: {{title}}

## What was predicted

<!--
State the prediction that was tested, and the proposition it derives from
(set `falsifies:` to that proposition ref).
-->

## What was observed

<!--
State the observed result that contradicted the prediction.
-->

## Decision

<!--
What was decided in light of the falsification? (e.g. reject a mechanistic
interpretation, retire a claim). Set `supersedes_claim:` if this record
supersedes a specific prior claim ref.
-->

## Source of prediction

<!--
Optional. Where did the prediction come from — a topic, hypothesis, or paper ref.
-->
```

- [ ] **Step 6: Mirror the template to the repo root**

Copy the identical content to `templates/falsification.md`:

```bash
cp science/model/src/science_model/templates/falsification.md templates/falsification.md
```

- [ ] **Step 7: Run the load-source test to verify it passes**

Run: `cd science && uv run --frozen pytest tests/test_entity_registry.py::test_load_project_sources_binds_falsification_entity -v`
Expected: PASS.

- [ ] **Step 8: Write and run the `entity create` / `entity sections` coverage test**

Add to `science/tests/test_entities_cli.py` (this is where `entity create` is tested; it already imports `seed_project`, `write_markdown_entity`, `CliRunner`, and `main`):

```python
def test_entity_create_and_sections_falsification() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)

        created = runner.invoke(main, ["entity", "create", "falsification", "Refuted prediction"])
        assert created.exit_code == 0, created.output
        assert Path("entities/falsifications/refuted-prediction.md").is_file()

        sections = runner.invoke(main, ["entity", "sections", "falsification"])
        assert sections.exit_code == 0, sections.output
        assert "What was predicted" in sections.output
        assert "Decision" in sections.output
```

Run: `cd science && uv run --frozen pytest tests/test_entities_cli.py::test_entity_create_and_sections_falsification -v`
Expected: PASS (the `_template` block routes through the Renderer without the "missing the _template metadata block" hard-fail).

- [ ] **Step 9: Commit**

```bash
git add science/model/src/science_model/profiles/core.py science/src/science_tool/graph/entity_registry.py science/model/src/science_model/templates/falsification.md templates/falsification.md science/tests/test_entity_registry.py science/tests/test_entities_cli.py
git commit -m "feat(falsification): descriptor + CORE_KIND_MODELS binding + Renderer template"
```

---

## Task 4: Falsification compiler emission (routed to `graph/knowledge`)

Emit the falsification shape from the compiler into the `knowledge` graph, matching the retired writer term-for-term. Metadata literals dispatch from `_add_entity`; the `falsifies`/`supersedesClaim` edges dispatch from `_add_relations`.

**Files:**
- Modify: `science/src/science_tool/graph/materialize.py` (import `FalsificationEntity` at line 16; dispatch in `_add_entity` after line 661; dispatch in `_add_relations` after line 717; add the two emitter functions near `_add_evidence_line_metadata`, line 1050)
- Test: `science/tests/test_graph_materialize.py`

**Interfaces:**
- Consumes: `FalsificationEntity`, the generic `_add_entity` (already emits `rdf:type sci:Falsification` via `_kind_class_name("falsification") == "Falsification"`), `_entity_uri`, `SCI_NS`, `Literal`, the `ReferenceResolver`.
- Produces: `_add_falsification_metadata(*, uri: URIRef, knowledge, entity: FalsificationEntity) -> None` and `_add_falsification_relations(*, uri: URIRef, knowledge, entity: FalsificationEntity, entity_index: dict[str, Entity], resolver: ReferenceResolver) -> None`.

- [ ] **Step 1: Write the failing materialization parity test**

Add to `science/tests/test_graph_materialize.py`. The test covers two things the emitters must get right: (1) every falsification triple lands in `graph/knowledge` and nothing leaks to `provenance`; (2) `supersedesClaim` uses `_resolve_term` semantics — a full-URL claim ref must resolve to that exact URI (with `_entity_uri` it would be mangled into a lowercased project URI, so this case fails loud on the wrong resolver).

```python
def test_materialize_emits_falsification_into_knowledge_graph(tmp_path: Path) -> None:
    from rdflib import URIRef
    from rdflib.namespace import RDF

    from conftest import build_entity_graph
    from science_tool.graph.store import PROJECT_NS, SCI_NS, _graph_uri, _load_dataset

    graph_path = build_entity_graph(
        tmp_path,
        [
            {"kind": "proposition", "id": "drug_recovery",
             "frontmatter": {"title": "Drug improves recovery", "status": "active",
                             "confidence": 0.85, "source_refs": []},
             "body": "Drug improves recovery\n"},
            {"kind": "falsification", "id": "drug-recovery-null",
             "frontmatter": {"title": "Refuted", "status": "active",
                             "falsifies": "proposition:drug_recovery",
                             "predicted": "Drug improves recovery time",
                             "observed": "No improvement in randomized follow-up",
                             "decision": "Reject mechanistic interpretation",
                             "source_of_prediction": "topic:drug-mechanism",
                             # full URL — exercises _resolve_term (NOT _entity_uri) parity
                             "supersedes_claim": "https://example.org/claims/legacy-x",
                             "related": [], "source_refs": []},
             "body": "Refuted\n"},
        ],
    )
    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))
    fu = PROJECT_NS["falsification/drug-recovery-null"]
    pu = PROJECT_NS["proposition/drug_recovery"]

    assert (fu, RDF.type, SCI_NS.Falsification) in knowledge
    assert (fu, SCI_NS.falsifies, pu) in knowledge
    assert (fu, SCI_NS.predicted, None) in knowledge
    assert (fu, SCI_NS.observed, None) in knowledge
    assert (fu, SCI_NS.decision, None) in knowledge
    assert (fu, SCI_NS.sourceOfPrediction, None) in knowledge
    # _resolve_term parity: the full URL resolves verbatim, not to a project URI.
    assert (fu, SCI_NS.supersedesClaim, URIRef("https://example.org/claims/legacy-x")) in knowledge
    # Nothing falsification-specific leaked into the provenance graph.
    provenance = dataset.graph(PROJECT_NS["graph/provenance"])
    assert (fu, SCI_NS.predicted, None) not in provenance


def test_materialize_falsification_omits_blank_metadata_fields(tmp_path: Path) -> None:
    """Intentional source-form contract: a blank scaffold field emits NO triple.

    The retired writer took required non-empty CLI options, so all four literals
    always existed. In source form the template defaults them to "" — emitting an
    empty Literal would be noise. Blank fields are omitted; the reader
    `_load_proposition_falsifications` already defaults a missing predicate to "".
    """
    from conftest import build_entity_graph
    from science_tool.graph.store import PROJECT_NS, SCI_NS, _graph_uri, _load_dataset

    graph_path = build_entity_graph(
        tmp_path,
        [
            {"kind": "proposition", "id": "p1",
             "frontmatter": {"title": "P", "status": "active", "source_refs": []},
             "body": "P\n"},
            {"kind": "falsification", "id": "f-blank",
             "frontmatter": {"title": "Scaffold", "status": "draft",
                             "falsifies": "proposition:p1",
                             "predicted": "", "observed": "", "decision": "",
                             "source_of_prediction": "", "related": [], "source_refs": []},
             "body": "Scaffold\n"},
        ],
    )
    knowledge = _load_dataset(graph_path).graph(_graph_uri("graph/knowledge"))
    fu = PROJECT_NS["falsification/f-blank"]
    assert (fu, SCI_NS.falsifies, PROJECT_NS["proposition/p1"]) in knowledge
    assert (fu, SCI_NS.predicted, None) not in knowledge
    assert (fu, SCI_NS.decision, None) not in knowledge
```

- [ ] **Step 2: Run both to verify they fail**

Run: `cd science && uv run --frozen pytest "tests/test_graph_materialize.py::test_materialize_emits_falsification_into_knowledge_graph" "tests/test_graph_materialize.py::test_materialize_falsification_omits_blank_metadata_fields" -v`
Expected: FAIL — only `rdf:type sci:Falsification` is present (from generic `_add_entity`); the metadata predicates, `falsifies` edge, and `supersedesClaim` are missing.

- [ ] **Step 3: Import `FalsificationEntity` and `_resolve_term` in the materializer**

In `materialize.py` line 16, extend the entities import:

```python
from science_model.entities import Entity, EvidenceLineEntity, FalsificationEntity
```

`supersedes_claim` must resolve with the SAME semantics as the retired writer, which used `_resolve_term` (`graph/store/identity.py`) — it accepts full URLs, known CURIE prefixes, and project prefixes, and it **preserves** the project-ref suffix case. `_entity_uri`/`entity_uri_for_ref` does not (it lowercases and mangles any `prefix:suffix` into a project URI). `_resolve_term` is already re-exported from `graph.store` (which `materialize.py` imports at line 90 — no import cycle). Add `_resolve_term` to that existing `from science_tool.graph.store import (...)` block.

- [ ] **Step 4: Add the metadata emitter and dispatch it from `_add_entity`**

Add the emitter beside `_add_evidence_line_metadata` (after line 1087):

```python
def _add_falsification_metadata(*, uri: URIRef, knowledge, entity: FalsificationEntity) -> None:
    """Emit falsification descriptive literals into the KNOWLEDGE graph.

    Routed to `knowledge` — not `provenance` — to match the retired
    add_falsification writer and the reader `_load_proposition_falsifications`,
    which reads these predicates from graph/knowledge. The `falsifies` and
    `supersedesClaim` edges are emitted by _add_falsification_relations.

    Blank fields emit NO triple (source-form contract): the template scaffolds
    these to "", and an empty Literal would be noise — the reader defaults a
    missing predicate to "".
    """
    literal_predicates: dict[str, object] = {
        "predicted": SCI_NS.predicted,
        "observed": SCI_NS.observed,
        "decision": SCI_NS.decision,
        "source_of_prediction": SCI_NS.sourceOfPrediction,
    }
    for field, predicate in literal_predicates.items():
        value = getattr(entity, field, None)
        if value:
            knowledge.add((uri, predicate, Literal(str(value))))
```

In `_add_entity`, right after the `EvidenceLineEntity` metadata dispatch (lines 660-661), add:

```python
    if isinstance(entity, FalsificationEntity):
        _add_falsification_metadata(uri=uri, knowledge=knowledge, entity=entity)
```

(Note: `_add_entity` already has `knowledge` in scope, line 614.)

- [ ] **Step 5: Add the relations emitter and dispatch it from `_add_relations`**

Add the emitter after the metadata emitter:

```python
def _add_falsification_relations(
    *,
    uri: URIRef,
    knowledge,
    entity: FalsificationEntity,
    entity_index: dict[str, Entity],
    resolver: ReferenceResolver,
) -> None:
    """Emit sci:falsifies (validated proposition target) and optional
    sci:supersedesClaim into the KNOWLEDGE graph — mirroring the retired writer."""
    resolution = resolver.resolve(entity.falsifies, allow_cross_kind_fallback=True)
    if resolution.status != "resolved" or resolution.canonical_id is None:
        raise ValueError(
            f"{entity.canonical_id} falsifies {entity.falsifies!r}, which does not resolve "
            "to a known entity; a falsification target must resolve to a proposition."
        )
    target = entity_index.get(resolution.canonical_id)
    if target is None or target.kind != "proposition":
        raise ValueError(
            f"{entity.canonical_id} falsifies {resolution.canonical_id!r}, which is not a "
            "proposition; falsification targets must be propositions."
        )
    knowledge.add((uri, SCI_NS.falsifies, _entity_uri(target.canonical_id)))

    # supersedes_claim uses _resolve_term (not _entity_uri) for byte-parity with the
    # retired writer: full URLs, CURIEs, and case-preserved project refs all resolve
    # identically to the pre-retirement graph.
    if entity.supersedes_claim:
        knowledge.add((uri, SCI_NS.supersedesClaim, _resolve_term(entity.supersedes_claim)))
```

In `_add_relations`, right after the `EvidenceLineEntity` relations dispatch (lines 708-717), add:

```python
    if isinstance(entity, FalsificationEntity):
        _add_falsification_relations(
            uri=entity_uri,
            knowledge=knowledge,
            entity=entity,
            entity_index=entity_index,
            resolver=resolver,
        )
```

(Note: `_add_relations` binds `entity_uri = _entity_uri(entity.canonical_id)` at line 688 and has `resolver`, `entity_index`, `knowledge` in scope.)

- [ ] **Step 6: Run both parity tests to verify they pass**

Run: `cd science && uv run --frozen pytest "tests/test_graph_materialize.py::test_materialize_emits_falsification_into_knowledge_graph" "tests/test_graph_materialize.py::test_materialize_falsification_omits_blank_metadata_fields" -v`
Expected: PASS.

- [ ] **Step 7: Run the full graph-materialize + store test modules**

Run: `cd science && uv run --frozen pytest tests/test_graph_materialize.py tests/graph -v`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add science/src/science_tool/graph/materialize.py science/tests/test_graph_materialize.py
git commit -m "feat(falsification): compiler emitters route falsification triples to graph/knowledge"
```

---

## Task 5: Migrate `test_causal` falsification tests to authored fixtures

Replace the two `add_falsification(...)` calls with authored `falsification` source entities so the read-side overlay/export assertions run against a source-built graph.

**Files:**
- Modify: `science/tests/test_causal.py` (imports line 12-20; add a `_falsification` helper near line 84; edit the two tests at 659-712 and 714-761)

**Interfaces:**
- Consumes: `_author_entities` (line 93), `_build_compiled_inquiry_graph` (line 25). Both persist source files and re-materialize; the last materialize call (inside `_build_compiled_inquiry_graph`) picks up all previously-authored entity files.

- [ ] **Step 1: Drop the `add_falsification` import**

In `test_causal.py`, remove `add_falsification,` from the `from science_tool.graph.store import (...)` block (line 17).

- [ ] **Step 2: Add a `_falsification` entity helper**

After `_causal_relation` (line 90):

```python
def _falsification(entity_id: str, proposition_ref: str, *, predicted: str, observed: str,
                   decision: str, source_of_prediction: str) -> dict:
    return _entity(
        "falsification", entity_id, decision,
        falsifies=proposition_ref, predicted=predicted, observed=observed,
        decision=decision, source_of_prediction=source_of_prediction,
    )
```

- [ ] **Step 3: Rewrite `test_enriched_edges_include_linked_falsifications`**

Add the falsification to the `_author_entities` list (so it is a source file materialized by the later `_build_compiled_inquiry_graph`), and delete the trailing `add_falsification(...)` call. Replace lines 663-703 with:

```python
        _author_entities(
            graph_path,
            [
                _concept("drug", "Drug"),
                _concept("recovery", "Recovery"),
                _hypothesis("h1"),
                _proposition(
                    "drug_causes_recovery_falsified",
                    "Drug treatment improves recovery time",
                    confidence=0.85,
                ),
                _falsification(
                    "drug-recovery-null",
                    "proposition:drug_causes_recovery_falsified",
                    predicted="Drug treatment improves recovery time",
                    observed="Randomized follow-up showed no improvement",
                    decision="Reject mechanistic interpretation",
                    source_of_prediction="topic:drug-mechanism",
                ),
            ],
        )
        _build_compiled_inquiry_graph(
            graph_path,
            slug="fals-dag",
            profile="causal",
            boundary_roles=[
                {"ref": "concept:drug", "role": "BoundaryIn"},
                {"ref": "concept:recovery", "role": "BoundaryOut"},
            ],
            treatment="concept:drug",
            outcome="concept:recovery",
            flow_edges=[
                {
                    "subject": "concept:drug",
                    "predicate": "causes",
                    "object": "concept:recovery",
                    "claim_refs": ["proposition:drug_causes_recovery_falsified"],
                }
            ],
        )
```

The assertions (lines 705-712) are unchanged.

- [ ] **Step 4: Rewrite `test_export_pgmpy_includes_falsification_comments`**

Apply the same transformation: add the falsification to the `_author_entities` list and delete the `add_falsification(...)` call (lines 748-756). Use id `drug-recovery-null-export` and proposition `proposition:drug_causes_recovery_falsified_export`; keep the same predicted/observed/decision/source_of_prediction values. Assertions (lines 758-761) unchanged.

- [ ] **Step 5: Run both migrated tests**

Run: `cd science && uv run --frozen pytest "tests/test_causal.py::TestEdgeProvenance::test_enriched_edges_include_linked_falsifications" "tests/test_causal.py::TestEdgeProvenance::test_export_pgmpy_includes_falsification_comments" -v`

Expected: PASS.

- [ ] **Step 6: Run the full test_causal module**

Run: `cd science && uv run --frozen pytest tests/test_causal.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add science/tests/test_causal.py
git commit -m "test(causal): migrate falsification tests to authored source fixtures"
```

---

## Task 6: Wire the `story` kind for `entity create`

Add the create-scaffolding fields to the `story` descriptor and convert `story.md` to Renderer format, stripping the misleading `about:`/`interpretations:` keys and pointing authors at the `relations.yaml` edge path.

**Files:**
- Modify: `science/model/src/science_model/profiles/core.py` (story descriptor, lines 140-147)
- Modify: `science/model/src/science_model/templates/story.md` (convert)
- Modify: `templates/story.md` (repo-root mirror, byte-identical)
- Test: `science/tests/test_entities_cli.py`

**Interfaces:**
- Produces: `story` `EntityKind` with `template_ready=True`, `home="entities/stories"`, `strategy="slug"`, `default_status="draft"`, `statuses=["draft", "developing", "mature"]`.

- [ ] **Step 1: Write the failing `entity create story` test**

Add to `science/tests/test_entities_cli.py`:

```python
def test_entity_create_and_sections_story() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)

        created = runner.invoke(main, ["entity", "create", "story", "The X-Y regulation arc"])
        assert created.exit_code == 0, created.output
        assert Path("entities/stories/the-x-y-regulation-arc.md").is_file()

        sections = runner.invoke(main, ["entity", "sections", "story"])
        assert sections.exit_code == 0, sections.output
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_entities_cli.py::test_entity_create_and_sections_story -v`
Expected: FAIL — the `story` descriptor lacks `home`/`template_ready`/`strategy`, so `entity create` cannot scaffold (and the plain-frontmatter template lacks a `_template` block, so the Renderer hard-fails).

- [ ] **Step 3: Add the create-scaffolding fields to the descriptor**

In `profiles/core.py`, replace the `story` `EntityKind` (lines 140-147) with:

```python
        EntityKind(
            name="story",
            canonical_prefix="story",
            layer="layer/core",
            description="Coherent narrative arc synthesizing interpretations around a question or hypothesis.",
            entity_class=EntityClass.EPISTEMIC,
            category=KindCategory.AUTHORED_CORE,
            template_ready=True,
            home="entities/stories",
            strategy="slug",
            default_status="draft",
            statuses=["draft", "developing", "mature"],
        ),
```

- [ ] **Step 4: Convert `templates/story.md` to Renderer format (packaged copy)**

Replace the entire content of `science/model/src/science_model/templates/story.md` with:

```markdown
---
id: "story:{{slug}}"
kind: "story"
title: "{{title}}"
status: "{{status}}"
related: []
source_refs: []
created: "{{created}}"
updated: "{{updated}}"
_template:
  frontmatter:
    id: { from: entity_id }
    kind: { default: "story" }
    title: { from: title }
    status: { from: status }
    related: { from: related }
    source_refs: { from: source_refs }
    created: { from: created }
    updated: { from: updated }
  sections:
    - { key: summary, name: "Summary", required: true }
    - { key: synthesis, name: "Synthesis", required: true }
    - { key: relations, name: "Relations", required: false }
    - { key: gaps, name: "Gaps", required: false }
---

# Story: {{title}}

## Summary

<!--
What question does this story address, and what do the accumulated findings suggest?
-->

## Synthesis

<!--
Connective prose — the "so what" that ties the interpretations together.
What picture emerges? What patterns repeat? Where do the findings converge?
-->

## Relations

<!--
Story edges are NOT emitted from frontmatter. Author them in
knowledge/sources/<local>/relations.yaml:

relations:
  - { subject: "story:{{slug}}", predicate: "sci:organizedBy", object: "hypothesis:<h-id>" }
  - { subject: "story:{{slug}}", predicate: "sci:synthesizes", object: "interpretation:<interp-id>" }

Then run `science graph build`.
-->

## Gaps

<!-- What's missing? What findings would strengthen this story? -->

- [ ] {{Description of missing evidence or analysis}}
```

- [ ] **Step 5: Mirror the converted template to the repo root**

```bash
cp science/model/src/science_model/templates/story.md templates/story.md
```

- [ ] **Step 6: Classify story's new lifecycle statuses (status-visibility guard)**

Adding `statuses=["draft", "developing", "mature"]` to the story descriptor introduces two status tokens — `developing` and `mature` — that no core kind previously declared. The status-visibility guard `test_status_visibility.py::test_every_declared_status_is_classified_live_or_hidden` fails loud on any declared status that is in neither `_LIVE_STATUSES` nor `_HIDDEN_STATUSES` (`src/science_tool/entities.py`). Both are live work-in-progress states (a developing/mature story is active), so add them to `_LIVE_STATUSES`.

In `science/src/science_tool/entities.py`, in the `_LIVE_STATUSES` frozenset (after `"abandoned",`, ~line 224):

```python
        # Story lifecycle (Phase 3b: story kind wired for entity create).
        "developing",
        "mature",
```

Run: `cd science && uv run --frozen pytest tests/test_status_visibility.py -v`
Expected: PASS (previously RED on `developing`/`mature` once the descriptor landed).

- [ ] **Step 7: Run the create test to verify it passes**

Run: `cd science && uv run --frozen pytest tests/test_entities_cli.py::test_entity_create_and_sections_story -v`
Expected: PASS.

- [ ] **Step 8: Run the model suite (catches any template/snapshot guard)**

Run: `cd science/model && uv run --frozen pytest`
Expected: PASS. If a template-mirror or snapshot test flags the converted `story.md`, update the snapshot to the new content (the conversion is intended).

> Note: `test_kind_map_equivalence.py` (frozen markdown-policy / status / migrated-kind literals) is now RED for `story` — expected. Those frozen literals are reconciled together in Task 7. Do not run that module's assertions as a green gate here.

- [ ] **Step 9: Commit**

```bash
git add science/src/science_tool/entities.py science/model/src/science_model/profiles/core.py science/model/src/science_model/templates/story.md templates/story.md science/tests/test_entities_cli.py
git commit -m "feat(story): wire story kind for entity create + Renderer template"
```

---

## Task 7: Update reconciliation-gate literals

Adding `template_ready`/`home`/`strategy`/`default_status`/`statuses` to the `story` and `falsification` descriptors changes SIX field-presence-derived maps, all frozen in `test_kind_map_equivalence.py`: `MIGRATED_KINDS` (template_ready), the registry class map (new kind), `_BUILTIN_MARKDOWN_POLICIES` (home+strategy), `_DEFAULT_STATUS` (default_status), `_STATUS_VALUES` (statuses), plus `known_kinds()` (INTENDED_ADDITIONS). Reconcile every frozen copy.

**Files:**
- Modify: `science/tests/test_kind_map_equivalence.py` (`FROZEN_MARKDOWN_POLICIES` line 27, `FROZEN_DEFAULT_STATUS` line 63, `FROZEN_STATUS_VALUES` line 97, `FROZEN_MIGRATED_KINDS` line 161, `FROZEN_KIND_CLASSES` line 185)
- Modify: `science/tests/test_kind_reconciliation_registry.py` (`INTENDED_ADDITIONS` line 37)

**Interfaces:**
- Consumes: the live `_BUILTIN_MARKDOWN_POLICIES`, `_DEFAULT_STATUS`, `_STATUS_VALUES`, `MIGRATED_KINDS`, registry class map, and `known_kinds()` — now all including `story` (newly given home/strategy/statuses + template_ready) and `falsification` (new core kind).

- [ ] **Step 1: Run the gate tests to see the full RED set**

Run: `cd science && uv run --frozen pytest tests/test_kind_map_equivalence.py tests/test_kind_reconciliation_registry.py -v`
Expected: FAIL on `test_markdown_policies_equal_prior_literal` (story+falsification now have home/strategy), `test_default_status_equals_prior_literal` (both now have default_status), `test_status_values_equal_prior_literal` (both now declare statuses), `test_migrated_kinds_equal_prior_literal` (both template_ready), `test_registry_entity_class_equals_prior_literal` (falsification new), and `test_core_kind_recognition_delta_is_exactly_the_intended_additions` (falsification new).

- [ ] **Step 2: Add both kinds to `FROZEN_MARKDOWN_POLICIES`**

In `test_kind_map_equivalence.py`, add to the `FROZEN_MARKDOWN_POLICIES` dict (near the other `entities/...`/`slug` entries, ~line 38):

```python
    "story": EntityPathPolicy(Path("entities/stories"), "slug"),
    "falsification": EntityPathPolicy(Path("entities/falsifications"), "slug"),
```

- [ ] **Step 3: Add both kinds to `FROZEN_DEFAULT_STATUS`**

In the `FROZEN_DEFAULT_STATUS` dict (~line 63), add:

```python
    "story": "draft",
    "falsification": "draft",
```

- [ ] **Step 4: Add both kinds to `FROZEN_STATUS_VALUES`**

In the `FROZEN_STATUS_VALUES` dict (~line 97), add — note story's set is `draft/developing/mature`, falsification's mirrors evidence-line:

```python
    "story": frozenset({"draft", "developing", "mature"}),
    "falsification": frozenset({"draft", "active", "retired", "archived"}),
```

- [ ] **Step 5: Add `story` and `falsification` to `FROZEN_MIGRATED_KINDS`**

Add both entries to the frozenset (after `"mechanism",`, ~line 180):

```python
        "story",
        "falsification",
```

- [ ] **Step 6: Add `falsification` to `FROZEN_KIND_CLASSES`**

In the same file, add to the dict (alphabetical, after `"experiment": "operational",`):

```python
    "falsification": "epistemic",
```

(`"story": "epistemic"` is already present at line 221 — leave it.)

- [ ] **Step 7: Add `falsification` to `INTENDED_ADDITIONS`**

In `test_kind_reconciliation_registry.py`, add to the frozenset (line 37):

```python
        "falsification",
```

(`story` is already in `PRE_EXPANSION_CORE_KINDS` — do not touch it.)

- [ ] **Step 8: Run the gate tests to verify GREEN**

Run: `cd science && uv run --frozen pytest tests/test_kind_map_equivalence.py tests/test_kind_reconciliation_registry.py -v`
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add science/tests/test_kind_map_equivalence.py science/tests/test_kind_reconciliation_registry.py
git commit -m "test(gates): reconcile story + falsification into frozen kind/policy/status literals"
```

---

## Task 8: Delete `add_paper_entity` and the `comprises` relation

Outright deletion — no forward path. Remove the writer, the CLI command, the `comprises` `RelationKind` and its manifest entry, and the paper-model composition tests.

**Files:**
- Modify: `science/src/science_tool/graph/store/mutations.py` (delete `add_paper_entity`, lines 104-138)
- Modify: `science/src/science_tool/cli.py` (delete the `graph add paper` command, lines 2577-~2600; drop `add_paper_entity` from imports, line 62)
- Modify: `science/src/science_tool/graph/store/__init__.py`, `graph/__init__.py` (drop `add_paper_entity` re-export)
- Modify: `science/model/src/science_model/profiles/core.py` (delete the `comprises` `RelationKind`, lines 726-733)
- Modify: `science/src/science_tool/graph/store/constants.py` (delete the `comprises` manifest entry, line 374)
- Modify: `science/tests/test_paper_model.py` (delete/trim), `science/tests/test_graph_cli.py` (add "no such command" assertion)

**Interfaces:**
- Produces: `science graph add paper …` returns Click's "No such command 'paper'" (exit code 2).

- [ ] **Step 1: Write the failing "no such command" test**

In `test_graph_cli.py`, replace `test_graph_add_paper_warns_legacy_composition_not_literature_note` (line 451) with:

```python
def test_graph_add_paper_command_is_removed() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["graph", "add", "paper", "A title", "--story", "story:s01"])
    assert result.exit_code != 0
    assert "No such command 'paper'" in result.output
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_graph_cli.py::test_graph_add_paper_command_is_removed -v`
Expected: FAIL — the command still exists (exit 0 with the legacy warning).

- [ ] **Step 3: Delete the `graph add paper` CLI command**

In `cli.py`, delete the entire `@graph_add.command("paper")` block (decorators through the function body, lines 2577 to the end of `add_paper_cmd`). Remove `add_paper_entity,` from the import block (line 62).

- [ ] **Step 4: Delete the `add_paper_entity` writer**

In `graph/store/mutations.py`, delete the `add_paper_entity` function (lines 104-138).

- [ ] **Step 5: Prune re-exports**

Remove `add_paper_entity` from `graph/store/__init__.py` and `graph/__init__.py` (both the import and any `__all__` entry).

- [ ] **Step 6: Delete the `comprises` RelationKind + manifest entry**

In `profiles/core.py`, delete the `comprises` `RelationKind` block (lines 726-733). In `graph/store/constants.py`, delete the `comprises` manifest line (line 374).

- [ ] **Step 7: Delete/trim the paper-model tests**

In `test_paper_model.py`:
- Delete `test_add_paper_entity` (105-116) and `test_add_paper_entity_invalid_status` (119-121).
- Delete `test_add_story` (78-97) and `test_add_story_invalid_status` (100-102) — story write coverage moves to source (`test_graph_freshness_integration` / the create test).
- In `test_full_composition_chain` (124-171), delete the `# Story`, `# Paper`, and the `comprises`/`synthesizes`/`organizedBy` assertions (143-168); keep the entity-materialization assertions (169-171). Add a one-line pointer comment: `# Story/paper composition writers retired in Phase 3b; see test_graph_materialize falsification/story coverage.`
- Drop `add_paper_entity`, `add_story` from the imports (lines 12-13).

- [ ] **Step 8: Confirm no relation-enumeration gate freezes `comprises`**

Run: `cd science && uv run --frozen pytest tests/ -k "relation or predicate or manifest" -q`
Expected: PASS. If a frozen relation/predicate literal lists `comprises`, remove that entry (it is a genuine gate update, not a workaround).

- [ ] **Step 9: Run the affected suites**

Run: `cd science && uv run --frozen pytest tests/test_paper_model.py tests/test_graph_cli.py::test_graph_add_paper_command_is_removed -v`
and `cd science/model && uv run --frozen pytest`
Expected: PASS.

- [ ] **Step 10: Commit**

```bash
git add science/src/science_tool/graph/store/mutations.py science/src/science_tool/cli.py science/src/science_tool/graph/store/__init__.py science/src/science_tool/graph/__init__.py science/model/src/science_model/profiles/core.py science/src/science_tool/graph/store/constants.py science/tests/test_paper_model.py science/tests/test_graph_cli.py
git commit -m "refactor(kernel-closure): delete add_paper_entity writer + comprises relation"
```

---

## Task 9: Retire the `article`/`story`/`falsification` CLI surfaces (message-only)

Convert the three remaining `graph add` commands to message-only retirement (body raises `_retired_writer`), matching Phase 3a. The writer functions are still called nowhere after this — Task 10 deletes them.

**Files:**
- Modify: `science/src/science_tool/cli.py` (`add_article_cmd` 2218-2226, `add_falsification_cmd` 2490-2522, `add_story_cmd` 2525-2551)
- Modify: `science/tests/test_graph_cli.py` (convert article/story tests; extend the parametrized retirement test at 129)

**Interfaces:**
- Consumes: `_retired_writer(command: str, forward_path: str) -> click.ClickException` (cli.py line 2734).
- Produces: `graph add article/story/falsification` return non-zero with `"<command> is retired"` + a forward path + `"science graph build"`.

- [ ] **Step 1: Extend the parametrized retirement test**

In `test_graph_cli.py`, add three cases to the `test_retired_graph_writer_commands_report_forward_path` parametrize list (line 127, before the closing `]`):

```python
        (
            ["graph", "add", "article", "10.1038/s41586-023-06957-x"],
            "graph add article",
            "science entity create paper",
        ),
        (
            ["graph", "add", "story", "A story", "--summary", "s", "--about",
             "hypothesis:h1", "--interpretation", "interpretation:i1"],
            "graph add story",
            "science entity create story",
        ),
        (
            ["graph", "add", "falsification", "--predicted", "p", "--source-of-prediction",
             "topic:x", "--observed", "o", "--decision", "d", "--proposition", "proposition:p1"],
            "graph add falsification",
            "science entity create falsification",
        ),
```

- [ ] **Step 2: Delete the now-obsolete article/story CLI tests**

In `test_graph_cli.py`, delete `test_graph_add_article_records_reference` (404-421) and `test_graph_add_story_warns_graph_only_not_durable` (424-448) — their success-path behavior no longer exists; the parametrized test covers the retirement.

- [ ] **Step 3: Run the retirement test to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_graph_cli.py::test_retired_graph_writer_commands_report_forward_path -v`
Expected: FAIL for the three new cases — the commands still perform durable writes (exit 0), so `"is retired"` is absent.

- [ ] **Step 4: Retire `add_article_cmd`**

Replace the body of `add_article_cmd` (cli.py 2223-2226) with:

```python
def add_article_cmd(doi: str, graph_path: Path) -> None:
    """Add an external literature reference by DOI."""
    raise _retired_writer(
        "graph add article",
        "Run `science entity create paper <title>` (or edit entities/papers/<citekey>.md with a doi: field)",
    )
```

- [ ] **Step 5: Retire `add_falsification_cmd`**

Replace the body of `add_falsification_cmd` (cli.py 2511-2522) with:

```python
    """Add a falsification record linked to a proposition."""
    raise _retired_writer(
        "graph add falsification",
        "Run `science entity create falsification <title>` (set falsifies: to the proposition ref)",
    )
```

Keep the decorator/signature so the `--proposition`/`--predicted`/… options still parse (the parametrized test invokes with them).

- [ ] **Step 6: Retire `add_story_cmd`**

Replace the body of `add_story_cmd` (cli.py 2544-2551) with:

```python
    """Add a story — a narrative arc around a question or hypothesis."""
    raise _retired_writer(
        "graph add story",
        "Run `science entity create story <title>` (author synthesizes/organizedBy edges in relations.yaml)",
    )
```

- [ ] **Step 7: Run the retirement + CLI suite**

Run: `cd science && uv run --frozen pytest tests/test_graph_cli.py -v`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add science/src/science_tool/cli.py science/tests/test_graph_cli.py
git commit -m "refactor(kernel-closure): retire graph add article/story/falsification (message-only)"
```

---

## Task 10: Delete the three writer functions + prune imports (guard GREEN)

With every call site now a `_retired_writer` raise, delete the three remaining writer functions and prune their re-exports. This clears the guard's RED state.

**Files:**
- Modify: `science/src/science_tool/graph/store/mutations.py` (delete `add_article` 15-25, `add_falsification` 28-64, `add_story` 67-101 — leaving the file with only its imports, which then also prune)
- Modify: `science/src/science_tool/cli.py` (drop `add_article`, `add_falsification`, `add_story` from the import block, lines 60-63)
- Modify: `science/src/science_tool/graph/store/__init__.py`, `graph/__init__.py` (drop re-exports)

**Interfaces:**
- Produces: `EXPECTED_DEFERRED_WRITERS == set()` and the boundary guard GREEN.

- [ ] **Step 1: Delete the three writer functions**

In `mutations.py`, delete `add_article` (15-25), `add_falsification` (28-64), and `add_story` (67-101). After deletion, the module should have no writer functions left. Remove now-unused imports (`hashlib`, `click`, `Literal`, `URIRef`, `RDF`, `SKOS`, `_load_dataset`, `_save_dataset`, `_resolve_term`, `_slug`, namespace constants) — let ruff tell you which are unused.

> If `mutations.py` becomes empty of definitions, keep the module (empty) only if something still imports it by name; otherwise delete the file and remove its import from `graph/store/__init__.py`. Check with `grep -rn "store.mutations\|from .mutations\|import mutations" science/src`.

- [ ] **Step 2: Prune imports and re-exports**

Remove `add_article`, `add_falsification`, `add_story` from cli.py's import block (60-63) and from `graph/store/__init__.py` / `graph/__init__.py` (imports + `__all__`).

- [ ] **Step 3: Run ruff to catch stragglers**

Run: `cd science && uv run ruff check`
Expected: no unused-import / undefined-name errors. Fix any it reports.

- [ ] **Step 4: Run the boundary guard — expect GREEN**

Run: `cd science && uv run --frozen pytest tests/graph/test_durable_write_boundary.py -v`
Expected: PASS — `actual` writer sites now equal the allowlist; the empty ledger has no stale entries.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/graph/store/mutations.py science/src/science_tool/graph/store/__init__.py science/src/science_tool/graph/__init__.py science/src/science_tool/cli.py
git commit -m "refactor(kernel-closure): delete final durable writers — ledger empty, guard GREEN"
```

---

## Task 11: Docs/skills sweep + final full-suite gate

Repoint any live `graph add article/story/paper/falsification` guidance to source authoring, add `falsification` to CORE_PROFILE-generated kind docs, and run the complete gate.

**Files:**
- Modify: `docs/user-guide/` kind listings and any command-doc/skill that references the retired commands (grep-driven)

**Interfaces:** none (docs + validation).

- [ ] **Step 1: Find live references to the retired commands**

Run: `grep -rn "graph add article\|graph add story\|graph add paper\|graph add falsification" docs/ skills/ commands/ science/src`
Expected: a short list. For each, repoint to the source-authoring path (`science entity create paper/story/falsification`, or `relations.yaml` for story edges). Leave design/plan docs under `docs/plans/` historical.

- [ ] **Step 2: Add `falsification` to the kind docs**

Find the CORE_PROFILE-generated kind listing:

Run: `grep -rln "evidence-line\|story" docs/user-guide/`
Add a `falsification` row/entry alongside the other epistemic kinds, and note `story` is now `entity create`-scaffoldable. If the listing is generated by a script/command, regenerate it rather than hand-editing.

- [ ] **Step 3: Full CLI suite**

Run: `cd science && uv run --frozen pytest`
Expected: PASS.

- [ ] **Step 4: Full model suite**

Run: `cd science/model && uv run --frozen pytest`
Expected: PASS.

- [ ] **Step 5: Lint + types**

Run: `cd science && uv run ruff check && uv run pyright`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add docs/
git commit -m "docs(kernel-closure): repoint retired graph-add guidance to source authoring"
```

---

## Success Criteria

- `EXPECTED_DEFERRED_WRITERS == set()` and `tests/graph/test_durable_write_boundary.py` is GREEN — no durable writer outside the compiler allowlist.
- Authored `entities/falsifications/*.md` produces the `sci:Falsification` shape in `graph/knowledge` (type + four literals + `sci:falsifies` + optional `sci:supersedesClaim`); summary risk / belief overlay / causal exports unchanged for a source-built project (verified by the migrated `test_causal` tests).
- `science entity create story` and `science entity create falsification` scaffold valid entities via the Renderer `_template` path; the story template documents the `relations.yaml` step for `synthesizes`/`organizedBy`.
- `article` and `paper` kinds remain fully functional (citation classification; external-literature notes).
- Full CLI suite + model suite + ruff + pyright all green.

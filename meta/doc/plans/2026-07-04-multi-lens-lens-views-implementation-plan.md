# Multi-Lens `lens_views` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the analytical lens a first-class, multi-valued content dimension (`lens_views`) on epistemic entities, so convergent lenses preserve both framings instead of forcing keep-one.

**Architecture:** A packaged lens vocabulary (`science_model.lenses`) is the single source of truth for lens slugs. A new `LensView` model and an `Entity.lens_views` field carry per-lens framing as content, linked to (but separate from) the unchanged provenance `origins`. `explore-ideas apply` routes report `lens_views` into the entity; graph materialization reifies each view as a node preserving the lens↔origin link; a soft validate check nudges pre-`lens_views` entities toward backfill.

**Tech Stack:** Python 3.11, Pydantic v2, `rdflib` (graph materialization), `pytest`, `uv`, `click` (CLI). Monorepo `~/d/science`; work in worktree `~/d/science/.worktrees/multi-lens-lens-views` (branch `multi-lens-lens-views`).

## Global Constraints

- Run all `science` commands with `uv run --frozen`.
- Model tests run from `science/model/` (`cd science/model && uv run pytest tests/...`); tool tests run from `science/` (`cd science && uv run pytest tests/...`). Both packages set `testpaths = ["tests"]`.
- Commit-message rule (user global): **no AI-attribution trailer or footer** — no `Co-Authored-By`, no "Generated with" line.
- D-001 (meta project): commits touching **tool code** stay scoped to the repo root; commits touching **`meta/`** (this plan, `core/decisions.md`) stay scoped to `meta/`. In this single branch that means *separate commits per scope*, never one commit mixing `meta/` with tool code.
- Provenance invariant (from `science_model.entities.OriginRecord`): "Provenance metadata only; MUST NOT affect evidential weight." `OriginRecord` is **not modified**; lens rationale is content and lives only on `LensView`.
- Lens **slugs are stable identifiers**; `name`/`description` may evolve, but a slug change is an explicit migration, never silent aliasing.
- Paths in docs use `~/d/` (not `/home/keith/d/` or `/mnt/ssd/Dropbox/`).
- The six lens slugs and frames are fixed by `commands/explore-ideas.md`: `mechanism`, `methodology`, `population`, `contrarian`, `analogy`, `temporal`.

---

## File Structure

**Create:**
- `science/model/src/science_model/lenses.py` — packaged lens vocabulary.
- `science/model/tests/test_lenses.py` — vocabulary tests.
- `science/model/tests/test_lens_views.py` — `LensView` + `Entity.lens_views` model tests.
- `science/src/science_tool/validate/checks/lens_views.py` — migration-nudge check.
- `science/tests/test_lens_view_materialize.py` — graph reification tests.
- `science/tests/test_lens_view_backfill.py` — derivation + backfill tests.

**Modify:**
- `science/model/src/science_model/entities.py` — add `LensView`, `Entity.lens_views`, validator.
- `science/model/src/science_model/__init__.py` — export new symbols.
- `science/src/science_tool/explore_ideas.py` — parse/route `lens_views`; shared `derive_lens_views`; backfill.
- `science/src/science_tool/graph/materialize.py` — reify lens-views.
- `science/src/science_tool/validate/checks/__init__.py` — register `lens_views` check module.
- `science/src/science_tool/cli.py` — `explore-ideas backfill-lens-views` subcommand.
- `commands/explore-ideas.md` — report contract (Phase 4 emits one block per apply unit with `lens_views`).
- `science/tests/test_explore_ideas_apply.py` — apply routing tests.
- `meta/core/decisions.md` — record the schema decision.

---

## Task 1: Packaged lens vocabulary (`science_model.lenses`)

**Files:**
- Create: `science/model/src/science_model/lenses.py`
- Modify: `science/model/src/science_model/__init__.py`
- Test: `science/model/tests/test_lenses.py`

**Interfaces:**
- Produces: `Lens` (dataclass: `slug`, `name`, `description`, `kind`), `LENSES: tuple[Lens, ...]`, `LENS_BY_SLUG: dict[str, Lens]`, `LENS_SLUGS: frozenset[str]`, `is_valid_lens(slug: str) -> bool`.

- [ ] **Step 1: Write the failing test**

```python
# science/model/tests/test_lenses.py
from __future__ import annotations

from science_model.lenses import LENS_BY_SLUG, LENS_SLUGS, is_valid_lens


def test_six_canonical_lenses() -> None:
    assert LENS_SLUGS == {
        "mechanism", "methodology", "population", "contrarian", "analogy", "temporal",
    }


def test_is_valid_lens() -> None:
    assert is_valid_lens("mechanism")
    assert not is_valid_lens("holistic")


def test_lens_metadata() -> None:
    assert LENS_BY_SLUG["temporal"].description.startswith("temporal")
    assert LENS_BY_SLUG["mechanism"].kind == "generative-analytical"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science/model && uv run pytest tests/test_lenses.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'science_model.lenses'`

- [ ] **Step 3: Write the vocabulary module**

```python
# science/model/src/science_model/lenses.py
"""Packaged vocabulary of generative analytical lenses.

A lens is a *view* over a shared research idea — the analytical perspective the
idea was framed through. This module is the single source of truth for lens
slugs; schema validation, explore-ideas apply, graph materialization, and the
validation checks all read from here. Slugs are stable identifiers; names and
descriptions may evolve, but a slug change is an explicit migration, not silent
aliasing.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Lens:
    slug: str
    name: str
    description: str
    kind: str = "generative-analytical"


LENSES: tuple[Lens, ...] = (
    Lens("mechanism", "Mechanism", "causal/biological mechanism and pathway"),
    Lens("methodology", "Methodology", "measurement, assay, study-design, analysis method"),
    Lens("population", "Population", "population, context, subgroup, setting, boundary conditions"),
    Lens("contrarian", "Contrarian", "what if the dominant assumption is wrong; null/negative framing"),
    Lens("analogy", "Analogy", "cross-disciplinary analogy — how an adjacent field would frame it"),
    Lens("temporal", "Temporal", "temporal/longitudinal/dynamics dimension"),
)

LENS_BY_SLUG: dict[str, Lens] = {lens.slug: lens for lens in LENSES}
LENS_SLUGS: frozenset[str] = frozenset(LENS_BY_SLUG)


def is_valid_lens(slug: str) -> bool:
    return slug in LENS_SLUGS
```

- [ ] **Step 4: Export from the package**

Add to `science/model/src/science_model/__init__.py` (with the other `from science_model.<module> import ...` lines, keeping alphabetical grouping near `licenses`):

```python
from science_model.lenses import LENS_BY_SLUG, LENS_SLUGS, LENSES, Lens, is_valid_lens
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd science/model && uv run pytest tests/test_lenses.py -q`
Expected: PASS (3 passed)

- [ ] **Step 6: Commit**

```bash
git add science/model/src/science_model/lenses.py science/model/src/science_model/__init__.py science/model/tests/test_lenses.py
git commit -m "feat(model): packaged lens vocabulary (science_model.lenses)"
```

---

## Task 2: `LensView` model + `Entity.lens_views` + validator

**Files:**
- Modify: `science/model/src/science_model/entities.py` (add `LensView` after `OriginRecord` at line ~268; add field near `origins` at line ~293; the two model_validators)
- Modify: `science/model/src/science_model/__init__.py`
- Test: `science/model/tests/test_lens_views.py`

**Interfaces:**
- Consumes: `science_model.lenses.is_valid_lens`, `LENS_SLUGS` (Task 1).
- Produces: `LensView` (Pydantic model: `lens: str`, `rationale: str`, `origin_ref: str | None`); `Entity.lens_views: list[LensView]`.

**Invariants enforced in the model (fail-fast, hard):** lens ∈ vocabulary; non-empty rationale; when `lens_views` present, non-null `origins[].ref` are unique; every non-null `origin_ref` matches one of them; at most one view per lens.

- [ ] **Step 1: Write the failing test**

```python
# science/model/tests/test_lens_views.py
from __future__ import annotations

import pytest
from pydantic import ValidationError

from science_model.entities import LensView, OriginRecord
from science_model.provenance import ProvenanceType


def _entity(**overrides):
    from science_model.entities import Entity
    base = dict(
        id="question:0001-x", kind="question", title="X", project="p",
        ontology_terms=[], related=[], source_refs=[], content_preview="",
        file_path="entities/questions/0001-x.md",
    )
    base.update(overrides)
    return Entity(**base)


def test_lens_view_rejects_unknown_lens() -> None:
    with pytest.raises(ValidationError):
        LensView(lens="holistic", rationale="r")


def test_lens_view_requires_nonempty_rationale() -> None:
    with pytest.raises(ValidationError):
        LensView(lens="mechanism", rationale="  ")


def test_entity_accepts_convergent_lens_views() -> None:
    e = _entity(
        origins=[
            OriginRecord(type=ProvenanceType.ASSISTANT, ref="explore-ideas-mechanism"),
            OriginRecord(type=ProvenanceType.ASSISTANT, ref="explore-ideas-analogy", independent=True),
        ],
        lens_views=[
            LensView(lens="mechanism", rationale="m", origin_ref="explore-ideas-mechanism"),
            LensView(lens="analogy", rationale="a", origin_ref="explore-ideas-analogy"),
        ],
    )
    assert [v.lens for v in e.lens_views] == ["mechanism", "analogy"]


def test_entity_rejects_dangling_origin_ref() -> None:
    with pytest.raises(ValidationError):
        _entity(
            origins=[OriginRecord(type=ProvenanceType.ASSISTANT, ref="explore-ideas-mechanism")],
            lens_views=[LensView(lens="analogy", rationale="a", origin_ref="explore-ideas-analogy")],
        )


def test_entity_rejects_duplicate_lens() -> None:
    with pytest.raises(ValidationError):
        _entity(
            origins=[OriginRecord(type=ProvenanceType.ASSISTANT, ref="explore-ideas-mechanism")],
            lens_views=[
                LensView(lens="mechanism", rationale="a", origin_ref="explore-ideas-mechanism"),
                LensView(lens="mechanism", rationale="b"),
            ],
        )
```

> Note: confirm the `ProvenanceType`/`OriginType` enum member for assistant. `OriginRecord.type` is `OriginType`; in this codebase `OriginType` is re-exported via `science_model.provenance.ProvenanceType`. If the import fails, run `cd science/model && uv run python -c "from science_model.entities import OriginType; print(list(OriginType))"` and use the correct member (e.g. `OriginType.ASSISTANT`).

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science/model && uv run pytest tests/test_lens_views.py -q`
Expected: FAIL with `ImportError: cannot import name 'LensView'`

- [ ] **Step 3: Add the `LensView` model**

In `science/model/src/science_model/entities.py`, immediately after the `OriginRecord` class (after line ~268), add:

```python
class LensView(BaseModel):
    """One analytical-lens view that frames an entity.

    Content, not provenance: a lens-view records *how* a lens frames the idea
    (its rationale). It is distinct from ``OriginRecord``, which records
    *who/what* originated the entity. A lens-view may link back to the origin
    that produced it via ``origin_ref``; that link never affects belief.
    """

    model_config = ConfigDict(extra="forbid")

    lens: str
    rationale: str
    origin_ref: str | None = None

    @model_validator(mode="after")
    def _validate(self) -> "LensView":
        from science_model.lenses import LENS_SLUGS, is_valid_lens

        if not is_valid_lens(self.lens):
            raise ValueError(f"unknown lens {self.lens!r}; expected one of {sorted(LENS_SLUGS)}")
        if not self.rationale.strip():
            raise ValueError("lens-view rationale must be non-empty")
        return self
```

- [ ] **Step 4: Add the `lens_views` field to `Entity`**

In `science/model/src/science_model/entities.py`, directly after the `origins` field (line ~293), add:

```python
    # Content: analytical lens(es) that frame this entity (see LensView).
    lens_views: list[LensView] = Field(default_factory=list)
```

Then add this validator method to the `Entity` class (near the existing `_validate_review_state_kind` at line ~312):

```python
    @model_validator(mode="after")
    def _validate_lens_views(self) -> "Entity":
        if not self.lens_views:
            return self
        non_null_refs = [o.ref for o in self.origins if o.ref is not None]
        if len(non_null_refs) != len(set(non_null_refs)):
            raise ValueError("non-null origin refs must be unique when lens_views are present")
        ref_set = set(non_null_refs)
        seen: set[str] = set()
        for view in self.lens_views:
            if view.lens in seen:
                raise ValueError(f"duplicate lens_view for lens {view.lens!r} (at most one view per lens)")
            seen.add(view.lens)
            if view.origin_ref is not None and view.origin_ref not in ref_set:
                raise ValueError(
                    f"lens_view origin_ref {view.origin_ref!r} does not match any of the "
                    "entity's own non-null origin refs"
                )
        return self
```

- [ ] **Step 5: Export `LensView`**

Add `LensView` to the `from science_model.entities import (...)` block in `science/model/src/science_model/__init__.py` (keep the list alphabetical: after `EvidenceLineEntity`, before `MechanismEntity`).

- [ ] **Step 6: Run test to verify it passes**

Run: `cd science/model && uv run pytest tests/test_lens_views.py -q`
Expected: PASS (5 passed)

- [ ] **Step 7: Run the full model suite (no regressions)**

Run: `cd science/model && uv run pytest -q`
Expected: PASS (all)

- [ ] **Step 8: Commit**

```bash
git add science/model/src/science_model/entities.py science/model/src/science_model/__init__.py science/model/tests/test_lens_views.py
git commit -m "feat(model): LensView content field with lens/origin-ref invariants"
```

---

## Task 3: `explore-ideas apply` routes `lens_views`

**Files:**
- Modify: `science/src/science_tool/explore_ideas.py`
- Test: `science/tests/test_explore_ideas_apply.py`

**Interfaces:**
- Consumes: `science_model.entities.LensView` (Task 2); existing `CreatePlan`, `build_create_plan`, `apply_report`.
- Produces: `derive_lens_views(data: dict, origins: list[dict]) -> list[dict]`; `CreatePlan.lens_views: list[dict]`.

**Contract:** A block that carries `lens_views` must also carry the matching `origin_plan.origins`, and every `lens_views[].origin_ref` must equal one of those planned origin refs. A legacy block with no `lens_views` but a top-level `lens`+`rationale` synthesizes one view. Empty otherwise.

- [ ] **Step 1: Write the failing tests**

Add to `science/tests/test_explore_ideas_apply.py`:

```python
from science_tool.explore_ideas import derive_lens_views


def test_derive_lens_views_from_explicit_block() -> None:
    data = {
        "lens_views": [
            {"lens": "mechanism", "rationale": "m", "origin_ref": "explore-ideas-mechanism"},
            {"lens": "analogy", "rationale": "a", "origin_ref": "explore-ideas-analogy"},
        ],
    }
    origins = [
        {"type": "assistant", "ref": "explore-ideas-mechanism"},
        {"type": "assistant", "ref": "explore-ideas-analogy", "independent": True},
    ]
    views = derive_lens_views(data, origins)
    assert [v["lens"] for v in views] == ["mechanism", "analogy"]
    assert views[1]["origin_ref"] == "explore-ideas-analogy"


def test_derive_lens_views_synthesizes_from_legacy_single_lens() -> None:
    data = {"lens": "mechanism", "rationale": "the framing"}
    origins = [{"type": "assistant", "ref": "explore-ideas-mechanism"}]
    views = derive_lens_views(data, origins)
    assert views == [
        {"lens": "mechanism", "rationale": "the framing", "origin_ref": "explore-ideas-mechanism"}
    ]


def test_derive_lens_views_rejects_dangling_origin_ref() -> None:
    from science_tool.explore_ideas import ApplyValidationError
    data = {"lens_views": [{"lens": "analogy", "rationale": "a", "origin_ref": "explore-ideas-analogy"}]}
    origins = [{"type": "assistant", "ref": "explore-ideas-mechanism"}]
    with pytest.raises(ApplyValidationError):
        derive_lens_views(data, origins, candidate_id="cand-x")


def test_build_create_plan_carries_lens_views() -> None:
    data = {
        "proposed_kind": "question",
        "title": "T",
        "lens": "mechanism",
        "rationale": "framing",
        "origin_plan": {"origins": [{"type": "assistant", "ref": "explore-ideas-mechanism"}]},
    }
    plan = build_create_plan("cand-x", data, "model-1")
    assert plan.lens_views == [
        {"lens": "mechanism", "rationale": "framing", "origin_ref": "explore-ideas-mechanism"}
    ]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science && uv run pytest tests/test_explore_ideas_apply.py -q -k lens`
Expected: FAIL with `ImportError: cannot import name 'derive_lens_views'`

- [ ] **Step 3: Add `derive_lens_views` and route it**

In `science/src/science_tool/explore_ideas.py`:

Update the import (line 11):

```python
from science_model.entities import LensView, OriginRecord
```

Add the `lens_views` field to `CreatePlan` (after `source_refs` at line ~41):

```python
    lens_views: list[dict]
```

Add the derivation function (after `_normalize_origin`, ~line 143):

```python
def _normalize_lens_view(view: object, candidate_id: str, planned_refs: set[str]) -> dict:
    if not isinstance(view, dict):
        raise ApplyValidationError(f"{candidate_id}: lens_views entry must be a mapping")
    try:
        record = LensView.model_validate(dict(view))
    except ValidationError as exc:
        raise ApplyValidationError(f"{candidate_id}: invalid lens_view {view!r}: {exc}") from exc
    if record.origin_ref is not None and record.origin_ref not in planned_refs:
        raise ApplyValidationError(
            f"{candidate_id}: lens_view origin_ref {record.origin_ref!r} is not one of the "
            "block's planned origin refs"
        )
    return record.model_dump(mode="json", exclude_none=True, exclude_defaults=True)


def derive_lens_views(data: dict, origins: list[dict], candidate_id: str = "?") -> list[dict]:
    """Return the lens_views for a candidate block.

    Explicit ``lens_views`` are validated against the planned origin refs. A
    legacy block (no ``lens_views``) with a top-level ``lens``+``rationale``
    synthesizes one view, linked to the ``explore-ideas-<lens>`` origin when the
    block planned it. Returns ``[]`` when neither is present.
    """
    planned_refs = {o["ref"] for o in origins if o.get("ref")}
    raw = data.get("lens_views")
    if raw is not None:
        if not isinstance(raw, list):
            raise ApplyValidationError(f"{candidate_id}: 'lens_views' must be a list")
        return [_normalize_lens_view(v, candidate_id, planned_refs) for v in raw]

    lens = data.get("lens")
    rationale = data.get("rationale")
    if isinstance(lens, str) and isinstance(rationale, str) and rationale.strip():
        view: dict = {"lens": lens, "rationale": rationale}
        origin_ref = f"explore-ideas-{lens}"
        if origin_ref in planned_refs:
            view["origin_ref"] = origin_ref
        return [_normalize_lens_view(view, candidate_id, planned_refs)]
    return []
```

In `build_create_plan`, after the `origins` loop (after line ~160) and before the `anchors` block, add:

```python
    lens_views = derive_lens_views(data, origins, candidate_id)
```

Add `lens_views=lens_views,` to the `CreatePlan(...)` constructor (after `source_refs=source_refs,`).

In `apply_report`, extend the `extra_frontmatter` dict passed to `create_entity` (line ~331) so it includes lens_views when present:

```python
                extra_frontmatter={
                    "origins": create_plan.origins,
                    "added_by": create_plan.added_by,
                    **({"lens_views": create_plan.lens_views} if create_plan.lens_views else {}),
                },
```

- [ ] **Step 4: Run the lens tests to verify they pass**

Run: `cd science && uv run pytest tests/test_explore_ideas_apply.py -q -k lens`
Expected: PASS

- [ ] **Step 5: Run the full apply suite (no regressions)**

Run: `cd science && uv run pytest tests/test_explore_ideas_apply.py -q`
Expected: PASS (all)

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/explore_ideas.py science/tests/test_explore_ideas_apply.py
git commit -m "feat(explore-ideas): route lens_views into created entities"
```

---

## Task 4: Graph materialization reifies lens-views

**Files:**
- Modify: `science/src/science_tool/graph/materialize.py` (in the entity-emit function, immediately after the `for i, origin in enumerate(entity.origins)` loop, ~line 929, before `if entity.added_by:`)
- Test: `science/tests/test_lens_view_materialize.py`

**Interfaces:**
- Consumes: `entity.lens_views` (Task 2); existing `PROJECT_NS`, `SCI_NS`, `RDF`, `URIRef`, `quote`, `provenance` graph.
- Produces graph triples: `<entity> sci:hasLensView <view>`, `<view> a sci:LensView`, `<view> sci:viewedThroughLens <lens>`, `<lens> a sci:Lens`, and `<view> sci:fromOrigin <origin>` when linkable.

- [ ] **Step 1: Write the failing test**

Model the harness on `science/tests/test_composition_rule_materialize.py` (read it first for the `seed_project` / `materialize_graph` / graph-load pattern). Concretely:

```python
# science/tests/test_lens_view_materialize.py
from __future__ import annotations

from rdflib import Graph, URIRef

from _fixtures.entity_helpers import seed_project
from science_tool.graph.materialize import materialize_graph


_ENTITY = """\
---
id: question:0001-lens-demo
kind: question
title: Lens demo
status: open
project: testproj
ontology_terms: []
related: []
source_refs: []
origins:
  - type: assistant
    ref: explore-ideas-mechanism
  - type: assistant
    ref: explore-ideas-analogy
    independent: true
lens_views:
  - lens: mechanism
    rationale: mechanism framing
    origin_ref: explore-ideas-mechanism
  - lens: analogy
    rationale: analogy framing
    origin_ref: explore-ideas-analogy
created: '2026-07-04'
updated: '2026-07-04'
---
# Lens demo

## Summary

Body.
"""


def test_lens_views_reified_with_origin_link(tmp_path) -> None:
    root = seed_project(tmp_path)
    (root / "entities" / "questions").mkdir(parents=True, exist_ok=True)
    (root / "entities" / "questions" / "0001-lens-demo.md").write_text(_ENTITY, encoding="utf-8")

    trig = materialize_graph(root, strict=False)
    g = Graph()
    g.parse(trig, format="trig")

    sci = "https://schema.science.dev/"  # confirm actual SCI_NS base in Step 2
    has_lens_view = URIRef(sci + "hasLensView")
    viewed_through = URIRef(sci + "viewedThroughLens")
    from_origin = URIRef(sci + "fromOrigin")

    views = list(g.objects(None, has_lens_view))
    assert len(views) == 2
    # each view links a lens and an origin
    for v in views:
        assert list(g.objects(v, viewed_through)), "view missing viewedThroughLens"
        assert list(g.objects(v, from_origin)), "view missing fromOrigin"
```

- [ ] **Step 2: Confirm the `SCI_NS` base URI, then run the test to verify it fails**

Run: `cd science && uv run python -c "from science_tool.graph.materialize import SCI_NS; print(str(SCI_NS))"`
Use the printed base in the test's `sci = ...` line (replace the placeholder).
Run: `cd science && uv run pytest tests/test_lens_view_materialize.py -q`
Expected: FAIL (only 0 `hasLensView` objects — predicate not emitted yet)

- [ ] **Step 3: Emit the reified lens-view triples**

In `science/src/science_tool/graph/materialize.py`, immediately after the `for i, origin in enumerate(entity.origins):` loop (after line ~929), add:

```python
    origin_index_by_ref = {
        origin.ref: idx for idx, origin in enumerate(entity.origins) if origin.ref is not None
    }
    for j, view in enumerate(getattr(entity, "lens_views", []) or []):
        view_node = URIRef(PROJECT_NS[f"lensview/{quote(entity.canonical_id, safe='')}/{j}"])
        lens_node = URIRef(SCI_NS[f"lens/{view.lens}"])
        provenance.add((entity_uri, SCI_NS.hasLensView, view_node))
        provenance.add((view_node, RDF.type, SCI_NS.LensView))
        provenance.add((view_node, SCI_NS.viewedThroughLens, lens_node))
        provenance.add((lens_node, RDF.type, SCI_NS.Lens))
        if view.origin_ref is not None and view.origin_ref in origin_index_by_ref:
            origin_idx = origin_index_by_ref[view.origin_ref]
            origin_node = URIRef(PROJECT_NS[f"origin/{quote(entity.canonical_id, safe='')}/{origin_idx}"])
            provenance.add((view_node, SCI_NS.fromOrigin, origin_node))
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd science && uv run pytest tests/test_lens_view_materialize.py -q`
Expected: PASS

- [ ] **Step 5: Run the graph suite (no regressions)**

Run: `cd science && uv run pytest tests/test_graph_build_strict.py tests/test_composition_rule_materialize.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/graph/materialize.py science/tests/test_lens_view_materialize.py
git commit -m "feat(graph): reify lens-views with lens and origin edges"
```

---

## Task 5: Migration-nudge validation check

**Files:**
- Create: `science/src/science_tool/validate/checks/lens_views.py`
- Modify: `science/src/science_tool/validate/checks/__init__.py` (add `"lens_views"` to `CANONICAL_CHECK_MODULES`, after `"origins"` at line ~71)
- Test: `science/tests/test_lens_view_backfill.py` (shared file with Task 7; add the check test here)

**Interfaces:**
- Consumes: `science_model.lenses.LENS_SLUGS`; `ValidateContext`, `Result`, `Severity`, `Check`, `iter_entity_markdown` (existing).
- Produces: check `check_lens_view_backfill` registered under section `"lens_views"`.

**Rationale:** structural invariants are enforced at the model layer (Task 2) and surface as conformance errors. This check is advisory: WARN when an entity's origins encode a lens (`explore-ideas-<slug>`) but it carries no `lens_views`, so pre-`lens_views` entities are surfaced for backfill.

- [ ] **Step 1: Write the failing test**

```python
# science/tests/test_lens_view_backfill.py  (create; Task 7 appends to it)
from __future__ import annotations

from click.testing import CliRunner

from _fixtures.entity_helpers import seed_project
from science_tool.cli import main


def _write_entity(root, name, extra_fm) -> None:
    (root / "entities" / "questions").mkdir(parents=True, exist_ok=True)
    (root / "entities" / "questions" / name).write_text(
        "---\n"
        "id: question:0001-x\nkind: question\ntitle: X\nstatus: open\nproject: testproj\n"
        "ontology_terms: []\nrelated: []\nsource_refs: []\n"
        f"{extra_fm}"
        "created: '2026-07-04'\nupdated: '2026-07-04'\n"
        "---\n# X\n\n## Summary\n\nBody.\n",
        encoding="utf-8",
    )


def test_validate_warns_on_lens_origin_without_lens_views(tmp_path) -> None:
    root = seed_project(tmp_path)
    _write_entity(root, "0001-x.md", "origins:\n  - type: assistant\n    ref: explore-ideas-mechanism\n")
    result = CliRunner().invoke(main, ["validate", "--project-root", str(root)])
    assert "no lens_views" in result.output or "lens_views" in result.output
```

> Confirm the exact `validate` invocation/flags with `cd science && uv run science validate --help`; adjust `["validate", "--project-root", str(root)]` to match (some builds infer the project from cwd — then use `CliRunner().invoke(main, ["validate"], catch_exceptions=False)` after `monkeypatch.chdir(root)`).

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd science && uv run pytest tests/test_lens_view_backfill.py -q -k warns`
Expected: FAIL (no such warning yet)

- [ ] **Step 3: Write the check**

```python
# science/src/science_tool/validate/checks/lens_views.py
"""Migration-nudge check for lens_views.

Structural invariants (lens vocabulary membership, origin_ref resolution, one
view per lens) are enforced at the model layer and surface as conformance
errors. This check is advisory: it WARNs when an entity's origins encode a lens
in their ref (``explore-ideas-<slug>``) but the entity carries no ``lens_views``,
so pre-lens_views explore-ideas entities are surfaced for backfill.
"""

from __future__ import annotations

from collections.abc import Iterator

from science_model.lenses import LENS_SLUGS
from science_tool.entity_scan import iter_entity_markdown
from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity


@Check("lens_views", 0)
def check_lens_view_backfill(ctx: ValidateContext) -> Iterator[Result]:
    entities_dir = ctx.project_root / "entities"
    for path in iter_entity_markdown(entities_dir):
        fm = ctx.frontmatter(path)
        if fm.get("lens_views"):
            continue
        origins = fm.get("origins")
        if not isinstance(origins, list):
            continue
        lenses = sorted(
            {
                o["ref"].removeprefix("explore-ideas-")
                for o in origins
                if isinstance(o, dict)
                and isinstance(o.get("ref"), str)
                and o["ref"].startswith("explore-ideas-")
                and o["ref"].removeprefix("explore-ideas-") in LENS_SLUGS
            }
        )
        if lenses:
            yield Result(
                Severity.WARN,
                None,
                None,
                f"{path.name}: origins encode lens(es) {lenses} but no lens_views; run "
                "'science explore-ideas backfill-lens-views'",
                "lens_views",
                None,
            )
```

- [ ] **Step 4: Register the check module**

In `science/src/science_tool/validate/checks/__init__.py`, add `"lens_views",` to the `CANONICAL_CHECK_MODULES` tuple, immediately after `"origins",` (line ~71).

- [ ] **Step 5: Run the test to verify it passes**

Run: `cd science && uv run pytest tests/test_lens_view_backfill.py -q -k warns`
Expected: PASS

- [ ] **Step 6: Confirm the check is discovered**

Run: `cd science && uv run python -c "from science_tool.validate.checks import CANONICAL_CHECKS; print([c.section for c in CANONICAL_CHECKS if c.section=='lens_views'])"`
Expected: `['lens_views']`

- [ ] **Step 7: Commit**

```bash
git add science/src/science_tool/validate/checks/lens_views.py science/src/science_tool/validate/checks/__init__.py science/tests/test_lens_view_backfill.py
git commit -m "feat(validate): warn on lens-encoding origins without lens_views"
```

---

## Task 6: Report contract — update `explore-ideas` command doc

**Files:**
- Modify: `commands/explore-ideas.md`

**No automated test** (prose contract). Verification is a grep + manual re-read.

- [ ] **Step 1: Add `lens_views` to the candidate-block schema**

In the example block (lines ~173–198), after the `rationale:` field and before `literature_anchors:`, add:

```yaml
lens_views:
  - lens: mechanism
    rationale: >
      Same framing as the top-level rationale; one entry per lens that frames
      this idea. A single-lens candidate has one entry.
    origin_ref: explore-ideas-mechanism
```

- [ ] **Step 2: Add a convergent (multi-lens) example and the one-block rule**

After the single example block (after line ~198), insert:

````markdown
When two lenses independently converge on the **same idea**, emit **one block**
for the whole idea (not one per lens): carry every converged lens as a
`lens_views` entry and one `origin_plan.origins` entry per lens, each marked
`independent: true`. Every `lens_views[].origin_ref` MUST equal one of the
planned `origin_plan.origins[].ref`.

```yaml
candidate_id: cand-hspc-trained-immunity
proposed_kind: question
title: Progenitor imprinting sustains PAIS inflammation
question_or_claim: Does IL-6/STAT3 imprinting of HSPCs sustain PAIS inflammation independent of antigen?
lens_views:
  - lens: mechanism
    rationale: IL-6/STAT3 imprinting of progenitors as an antigen-independent driver.
    origin_ref: explore-ideas-mechanism
  - lens: analogy
    rationale: Read as a maladaptive trained-immunity set-point in progenitor epigenetic memory.
    origin_ref: explore-ideas-analogy
novelty_bucket: novel
related_existing: []
decision: defer
origin_plan:
  origins:
    - type: assistant
      ref: explore-ideas-mechanism
    - type: assistant
      ref: explore-ideas-analogy
      independent: true
```
````

- [ ] **Step 3: Replace the keep-one instruction and the Phase-3/4 framing**

Find the "keep only one of each convergent pair" guidance (search the file) and replace it with:

```markdown
Convergent lenses are **not** collapsed to one: keep the whole idea as a single
block carrying multiple `lens_views`. `convergence_group` (if used) is an
internal Phase-3 classification aid only; Phase 4 emits exactly one block per
apply unit.
```

- [ ] **Step 4: Add the origin-plan finalization rule for lens_views**

In the "Origin-plan finalization rules" list (line ~204+), add a bullet:

```markdown
- Every `lens_views[]` entry links to the origin that produced it via
  `origin_ref`, which MUST match one of this block's `origin_plan.origins[].ref`.
  Apply creates `origins` and `lens_views` together atomically; a legacy block
  with only a top-level `lens`+`rationale` (no `lens_views`) synthesizes a single
  view at apply time.
```

- [ ] **Step 5: Verify the keep-one phrasing is gone**

Run: `grep -n "keep only one" commands/explore-ideas.md`
Expected: no matches.

- [ ] **Step 6: Commit**

```bash
git add commands/explore-ideas.md
git commit -m "docs(explore-ideas): lens_views report contract; drop keep-one"
```

---

## Task 7: Backfill capability + PAIS follow-up

**Files:**
- Modify: `science/src/science_tool/explore_ideas.py` (add `backfill_lens_views`)
- Modify: `science/src/science_tool/cli.py` (add `explore-ideas backfill-lens-views` subcommand)
- Test: `science/tests/test_lens_view_backfill.py` (append)

**Interfaces:**
- Consumes: `parse_report` (Task-era existing), `derive_lens_views` (Task 3), `science_model.frontmatter.parse_frontmatter`, `science_model.lenses.LENS_BY_SLUG`, and the tool's canonical frontmatter renderer `science_tool.entities._render_markdown`.
- Produces: `backfill_lens_views(project_root: Path, from_value: str) -> list[tuple[str, int]]` returning `(entity_id, views_added)` per touched entity.

**Behavior:** for each applied block (`decision: applied`, with `applied_as: <id>`), load that entity; for each assistant origin whose `ref` is `explore-ideas-<lens>` and which has no matching `lens_views` entry, append a view. Rationale for the block's primary lens comes from the block's `rationale`/`lens_views`; a secondary lens-origin (e.g. a hand-added independent analogy origin) uses `LENS_BY_SLUG[lens].description` as an honest interim rationale. Writes the entity back via the canonical renderer.

- [ ] **Step 1: Write the failing test**

Append to `science/tests/test_lens_view_backfill.py`:

```python
from datetime import date

from science_tool.explore_ideas import backfill_lens_views


_APPLIED_REPORT = """\
---
id: explore-demo
---

```yaml
candidate_id: cand-hspc
proposed_kind: question
title: HSPC imprinting
lens: mechanism
rationale: mechanism framing
decision: applied
applied_as: question:0001-hspc
applied_at: '2026-07-04'
origin_plan:
  origins:
    - type: assistant
      ref: explore-ideas-mechanism
```
"""


def test_backfill_adds_views_for_lens_origins(tmp_path) -> None:
    root = seed_project(tmp_path)
    (root / "entities" / "meta" / "explorations").mkdir(parents=True, exist_ok=True)
    (root / "entities" / "meta" / "explorations" / "explore-demo.md").write_text(
        _APPLIED_REPORT, encoding="utf-8"
    )
    _write_entity(
        root, "0001-hspc.md",
        "origins:\n"
        "  - type: assistant\n    ref: explore-ideas-mechanism\n"
        "  - type: assistant\n    ref: explore-ideas-analogy\n    independent: true\n",
    )
    # rename id inside the file to match applied_as
    p = root / "entities" / "questions" / "0001-hspc.md"
    p.write_text(p.read_text().replace("question:0001-x", "question:0001-hspc"), encoding="utf-8")

    touched = backfill_lens_views(root, "explore-demo")
    assert ("question:0001-hspc", 2) in touched

    from science_model.frontmatter import parse_frontmatter
    fm, _ = parse_frontmatter(p)
    lenses = {v["lens"] for v in fm["lens_views"]}
    assert lenses == {"mechanism", "analogy"}
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd science && uv run pytest tests/test_lens_view_backfill.py -q -k backfill`
Expected: FAIL with `ImportError: cannot import name 'backfill_lens_views'`

- [ ] **Step 3: Implement `backfill_lens_views`**

Add to `science/src/science_tool/explore_ideas.py`:

```python
def backfill_lens_views(project_root: Path, from_value: str) -> list[tuple[str, int]]:
    """Backfill lens_views onto entities created by a prior applied report.

    For each applied block, add one lens_view per lens-encoding assistant origin
    on the created entity that has no matching view yet. Returns (entity_id,
    views_added) for each touched entity.
    """
    from science_model.frontmatter import parse_frontmatter
    from science_model.lenses import LENS_BY_SLUG
    from science_tool.entities import _render_markdown

    report_path = resolve_report_path(project_root, from_value)
    blocks = parse_report(report_path.read_text(encoding="utf-8"))
    by_applied_as = {
        str(b.data.get("applied_as")): b.data
        for b in blocks
        if b.data.get("decision") == "applied" and b.data.get("applied_as")
    }

    touched: list[tuple[str, int]] = []
    for entity_id, block in by_applied_as.items():
        matches = list((project_root / "entities").rglob("*.md"))
        target = next((p for p in matches if _file_id(p) == entity_id), None)
        if target is None:
            continue
        fm, body = parse_frontmatter(target) or ({}, "")
        existing = {v.get("lens") for v in (fm.get("lens_views") or []) if isinstance(v, dict)}
        primary_lens = block.get("lens")
        primary_rationale = block.get("rationale")
        added: list[dict] = []
        for origin in fm.get("origins") or []:
            ref = origin.get("ref") if isinstance(origin, dict) else None
            if not (isinstance(ref, str) and ref.startswith("explore-ideas-")):
                continue
            lens = ref.removeprefix("explore-ideas-")
            if lens not in LENS_BY_SLUG or lens in existing:
                continue
            if lens == primary_lens and isinstance(primary_rationale, str) and primary_rationale.strip():
                rationale = primary_rationale.strip()
            else:
                rationale = LENS_BY_SLUG[lens].description
            added.append({"lens": lens, "rationale": rationale, "origin_ref": ref})
            existing.add(lens)
        if not added:
            continue
        fm.setdefault("lens_views", [])
        fm["lens_views"].extend(added)
        target.write_text(_render_markdown(fm, body), encoding="utf-8")
        touched.append((entity_id, len(added)))
    return touched


def _file_id(path: Path) -> str | None:
    from science_model.frontmatter import parse_frontmatter

    parsed = parse_frontmatter(path)
    if not parsed:
        return None
    fm, _ = parsed
    value = fm.get("id")
    return value if isinstance(value, str) else None
```

> `_render_markdown(frontmatter, body)` is the same renderer `create_entity` uses (see `science/src/science_tool/entities.py:420`). Confirm its signature in Step 4; if it normalizes/reorders keys, that is acceptable (canonical form) — verify the diff on a real file is clean.

- [ ] **Step 4: Add the CLI subcommand**

In `science/src/science_tool/cli.py`, find the `explore-ideas` command group (search `explore-ideas` / `explore_ideas`) and add, mirroring the existing `apply` subcommand's option style:

```python
@explore_ideas.command("backfill-lens-views")
@click.option("--from", "from_value", required=True, help="Report path or id (entities/meta/explorations/<id>.md).")
@click.option("--project-root", "project_root", default=".", type=click.Path(file_okay=False))
def backfill_lens_views_cmd(from_value: str, project_root: str) -> None:
    """Backfill lens_views onto entities from a prior applied report."""
    from science_tool.explore_ideas import backfill_lens_views

    touched = backfill_lens_views(Path(project_root), from_value)
    for entity_id, n in touched:
        click.echo(f"{entity_id}: +{n} lens_view(s)")
    click.echo(f"backfilled {len(touched)} ent/ {sum(n for _, n in touched)} views")
```

> Confirm the group's decorator name (`@explore_ideas.command` vs a differently-named Click group) in `cli.py` before editing; match the surrounding option conventions (e.g. `--model-id` on `apply`).

- [ ] **Step 5: Run the backfill tests to verify they pass**

Run: `cd science && uv run pytest tests/test_lens_view_backfill.py -q`
Expected: PASS (all — warn test + backfill test)

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/explore_ideas.py science/src/science_tool/cli.py science/tests/test_lens_view_backfill.py
git commit -m "feat(explore-ideas): backfill-lens-views for prior applied reports"
```

- [ ] **Step 7: Record the PAIS follow-up (documentation only)**

This plan does **not** modify the PAIS repo. After this branch merges and the tool is available, run (from `~/d/health/processes/post-acute-infection`):

```bash
uv run science explore-ideas backfill-lens-views --from explore-2026-07-04
```

Then, for the two convergent entities (`question:0026`, `question:0036`), replace the interim analogy rationale (the lens-frame description) with the true framing recoverable from the report's `decision: drop` twin blocks (`cand-analogy-maladaptive-trained-immunity-hsc-setpoint`, `cand-analogy-critical-slowing-down-pais-chronification`). Re-run `uv run --frozen science validate` to confirm the lens_views nudge clears. File this as a PAIS task via `science tasks add`.

---

## Task 8: Record the design decision (meta scope)

**Files:**
- Modify: `meta/core/decisions.md`

**D-001 note:** this is a **meta/**-scoped commit — do not combine with tool-code changes.

- [ ] **Step 1: Append the decision entry**

Add to `meta/core/decisions.md` (match the file's existing entry format; read it first). Content:

```markdown
## D-00N: Lenses are first-class content (`lens_views`), separate from provenance

The analytical lens that frames an epistemic entity is modelled as a
multi-valued content field `lens_views` (one `LensView` per lens: `lens`,
`rationale`, optional `origin_ref`), not as a string smuggled into an origin
`ref`. The lens vocabulary is packaged in `science_model.lenses` (stable slugs;
slug changes are explicit migrations). `OriginRecord` is unchanged and remains
provenance-only ("MUST NOT affect evidential weight"); `lens_views[].origin_ref`
links a view to one of the entity's own non-null, unique origin refs. Convergence
is derived (≥2 lens-views backed by independent origins), materialized as reified
`sci:hasLensView`/`sci:viewedThroughLens`/`sci:fromOrigin` nodes.

Rationale: preserve complementary lens framings instead of forcing keep-one; see
`meta/doc/plans/2026-07-04-multi-lens-first-class-representation-design.md` and
upstream feedback `fb-2026-07-04-005`.
```

Replace `D-00N` with the next number in the file.

- [ ] **Step 2: Validate meta (no new warnings from the doc)**

Run: `cd meta && uv run --frozen science validate 2>&1 | tail -3`
Expected: `PASSED` (warning count unchanged aside from anything the curate tooling manages).

- [ ] **Step 3: Commit (meta scope)**

```bash
git add meta/core/decisions.md
git commit -m "decision: lens_views as first-class content, separate from provenance"
```

---

## Deferred from v1 (explicit, not overlooked)

- **Generated `## Lens Views` body section.** The design specifies a
  human-readable body section rendered from frontmatter (non-canonical, no
  bidirectional sync). It is a pure display affordance — `lens_views` frontmatter
  is already canonical and queryable, and the graph reification (Task 4) carries
  the machine-readable form. Deferred to a follow-up to keep v1's blast radius on
  the schema/pipeline/graph; when added it belongs in the entity body renderer
  (`science/src/science_tool/entities.py:_render_markdown` / the template layer),
  regenerated on write and never parsed back.
- **`theme`/`topic` lens_views.** Design §Scope makes the field extensible to
  `topic`/`theme`; v1 targets `question`/`hypothesis` only (the kinds
  `explore-ideas` produces). Ties to upstream `fb-2026-07-04-007`.

## Final verification

- [ ] **Full model suite:** `cd science/model && uv run pytest -q` → PASS
- [ ] **Full tool suite (touched areas):** `cd science && uv run pytest tests/test_explore_ideas_apply.py tests/test_lens_view_materialize.py tests/test_lens_view_backfill.py tests/test_graph_build_strict.py -q` → PASS
- [ ] **End-to-end apply smoke:** seed a report with one convergent block (two `lens_views`, two independent origins), run `uv run science explore-ideas apply --from <report> --model-id test`, confirm the created entity's frontmatter carries both `lens_views` and both `origins`, and `science graph build` emits `sci:hasLensView` with `sci:fromOrigin` on each view.
- [ ] **Branch review:** `git log --oneline main..HEAD` shows tool-code commits and meta-scoped commits are not mixed (D-001).

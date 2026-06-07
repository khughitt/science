# Scoped-Ref Resolution & `ambiguous_reference` (Substrate Phase 1.3) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make reference resolution **executable across owner scopes** (design §B3a): a bare id (`topic:bayesian`) that resolves to an `owner` in **more than one loaded scope** is an `ambiguous_reference` error, and a **scoped reference form** (`commons:topic:bayesian`, `<project>:topic:x`) is the disambiguating escape hatch. The scope prefix validates against that scope's owners; it does **not** change the canonical id (scope is not part of the id).

**Architecture:** Scope-awareness lives in the **shared** `ReferenceResolver` (the one resolution seam, design §C2), driven by the compiled `IdentityTable` from Phase 1.1 — not by re-walking disk. The resolver gains an *optional* scope index (`canonical_id → {owner_scopes}`) and the set of loaded scope names; with them it (a) parses a leading known-scope prefix and validates ownership, and (b) flags a bare id owned in >1 scope as a new `scope_ambiguous` resolution status. 1.3 also adds a **dormant** `_audit_reference` branch that turns `scope_ambiguous` into an additive `ambiguous_reference` audit row. Crucially, **1.3 wires neither consumer**: `audit_project_sources` (`migrate.py:168`) and `materialize` (`materialize.py:91`) both keep building scope-naive resolvers, so the new branch is exercised only by direct unit tests; both consumers are wired to the identity table **together in 1.4** (so audit and build go scope-aware in one change, with no audit/build fail-open). When no identity table is supplied the resolver behaves **exactly** as today (full backward compatibility) — which is the only way any consumer calls it in 1.3.

**Reachability / scope boundary (why this is the right slice — read carefully):** Today **no entry point can produce a two-scope-same-id identity table from disk** — not even the non-strict audit/diagnostic path. The commons loader *suppresses* loading a commons owner whose id is already locally owned: `_load_commons_referenced_entities` does `referenced_ids.difference_update(identity_table)` and `set(overlays) - set(identity_table)` (`commons_sources.py:87,89`), fed the local dedup `identity_table` from `sources.py:479`. So a project-owned `topic:bayesian` *prevents* the commons owner of `topic:bayesian` from ever loading, in strict **and** non-strict modes. (The build path additionally raises `EntityIdentityCollisionError` under `strict_identity=True` before materialization.) Therefore 1.3 delivers the **compiler-model mechanism** — the scope index, the scope-aware shared resolver, and the dormant `_audit_reference` → `ambiguous_reference` branch — that becomes **disk-reachable** only once **scope-aware loading/dedup** lets the loader retain *both* owner rows for one id (Phase 1.4, which then wires the resolver into both `audit_project_sources` and `materialize`). This is deliberately **foundation-first**, the same posture as Phase 1.1's compiled `IdentityTable` and 1.2's zero-blast-radius guard: build the executable §B3a mechanism now; the loader change that *feeds* it real two-scope tables, and the consumer wiring that *acts* on it, land in 1.4. The Task 3 unit tests therefore construct the two-scope `IdentityTable` **directly** and pass the resulting scope-aware resolver straight into `_audit_reference` (a purely direct unit test) — they do **not** wire `audit_project_sources` and do **not** claim disk production, neither of which is in scope here.

**No resolver wiring ships in 1.3 — neither audit nor build (this avoids a fail-open path).** If 1.3 wired only the *audit* resolver to be scope-aware, a scoped ref like `commons:topic:x` would *pass* audit (in any commons-*borrowing* project `commons` is a loaded scope, so the prefix resolves) while `materialize` — which `materialize_graph` runs **after** the `audit_project_sources` gate (`materialize.py:193`) using a still **scope-naive** resolver (`materialize.py:91`, skipping the edge at `:343`) — would silently **drop** that edge. Accepting at the gate what the build discards is a fail-open for new syntax. So the `audit_project_sources` resolver wiring **and** the `materialize` resolver wiring land **together** in 1.4 (atop scope-aware dedup), going scope-aware in one change. 1.3 ships only the **mechanism**: the scope index (Task 1), the scope-aware `ReferenceResolver` (Task 2, unit-tested in isolation), and the dormant `_audit_reference` → `ambiguous_reference` branch (Task 3, exercised only by direct unit tests that pass a hand-built scope-aware resolver). On real disk in 1.3, `audit_project_sources` stays scope-naive: it neither accepts scoped refs nor emits `ambiguous_reference`. (This mirrors the 1.2 discipline: implement the facet reachable today with known blast radius; defer the unreachable rest — here, *all* wiring, so audit and build never diverge.)

**Tech Stack:** Python 3, pytest. Library at `~/d/science/science/` (`src/science_tool/`, `tests/`). Run tests with `cd ~/d/science/science && uv run --frozen pytest`.

**Scope (this plan only):** the scope index on `IdentityTable`; the scope-aware `ReferenceResolver` (scoped-form parsing + `scope_ambiguous` detection); the dormant `_audit_reference` → `ambiguous_reference` row-emission branch (unit-tested via direct calls). **Out of scope** (later sub-plans / phases): wiring the scope-aware resolver into **either** consumer — both `audit_project_sources` (`migrate.py:168`) and `materialize` (`materialize.py:91`) stay scope-naive in 1.3 and are wired together in 1.4 to avoid an audit/build fail-open; scope-aware entity dedup (the loader change that makes two-scope tables producible from disk, 1.4); the migrator on the compiled model + masking-hack retirement (1.4); orphan datapackages + dataset dual-SSOT (1.5/§B4); the full validating cross-project reference syntax against a *remote* scope's loaded owners (federation primitive `t068`, design §D4) — §B3a is explicitly the **minimal compiler-scoped disambiguation form** only.

**Design source:** `~/d/science/docs/plans/2026-06-06-knowledge-meta-model-and-substrate-design.md` — §B3 (identity key `(owner_scope, canonical_id)`), §B3a (executable bare-ref resolution: fixed search chain that never shadows owner ambiguity; bare ids must be unique across loaded scopes; multi-scope owner → `ambiguous_reference`; scoped form required), §C2 (every consumer reads the compiled model).

---

## File Structure

| File | Responsibility | Action |
|---|---|---|
| `src/science_tool/graph/identity_table.py` | Add `IdentityTable.owner_scopes_by_id()` (canonical_id → frozenset of owning scopes) | **Modify** (one method; `defaultdict` already imported) |
| `src/science_tool/graph/reference_resolution.py` | Scope-aware resolver: new `owner_scopes`/`scope_names` fields, `from_entities(identity_table=…)`, scoped-form parsing + `scope_ambiguous` status, `_split_scope`/`_resolve_unscoped` helpers | **Modify** |
| `src/science_tool/graph/migrate.py` | Add the `scope_ambiguous` → `ambiguous_reference` branch in `_audit_reference` only. **Do NOT** touch the resolver construction at line 168 (audit stays scope-naive in 1.3 — wiring deferred to 1.4 with `materialize`) | **Modify** |
| `tests/test_graph_identity_table.py` | Unit test for `owner_scopes_by_id()` | **Modify** (append) |
| `tests/test_reference_resolution_scoped.py` | Unit tests for the scope-aware resolver (scoped resolve, ambiguity, backward-compat) | **Create** |
| `tests/test_graph_migrate_identity_audit.py` | Two direct `_audit_reference` tests (ambiguous_reference row + scoped-form-not-flagged), passing a hand-built scope-aware resolver | **Modify** (append) |

### Reference facts (verified against `main` @ `8a87e5b7`)

- **`ReferenceResolver`** (`reference_resolution.py`) is a `@dataclass(frozen=True)` with fields `alias_map: dict[str, str]`, `slug_index: dict[str, frozenset[str]]`, built via `from_entities(entities, *, manual_aliases=None)`. Its `resolve(raw, *, allow_cross_kind_fallback=False, allow_tag=False)` returns a `ReferenceResolution(status, raw, canonical_id=None, candidates=())` with `status ∈ {"resolved","unresolved","ambiguous","tag"}`. The current bare logic (lines 60-76) is: `tag:` → tag/unresolved; `normalize_alias` + alias-map hit → resolved; else if no cross-kind fallback or no `:` → unresolved; else slug-index lookup → resolved (1) / `ambiguous` (>1) / unresolved (0).
- **Both consumers** build the resolver via `from_entities`: `materialize.py:91` (build) and `migrate.py:168` (audit). **In 1.3 leave ALL THREE resolver constructions unchanged** (`materialize.py:91`, `migrate.py:168`, and `migrate.py:261` which only reads `.alias_map`); wiring the identity table into the consumers is deferred to 1.4 so audit and build go scope-aware together. The new optional `identity_table=` param on `from_entities` is exercised in 1.3 only by tests.
- **`materialize`** uniformly skips any non-resolved status (`if resolution.status != "resolved": continue`, e.g. `materialize.py:316,328,344,374`). It is **not** modified in this plan (build-path deferred); a future `scope_ambiguous` would auto-skip there harmlessly.
- **`IdentityTable`** (`identity_table.py`): `owners() -> dict[tuple[str,str], list[IdentityDeclaration]]` keyed by `(owner_scope, canonical_id)` over OWNER rows. `from collections import defaultdict` is already imported. `build_identity_table(sources) -> IdentityTable` compiles `sources.identity_declarations`.
- **`_audit_reference`** (`migrate.py:818-870`) maps resolution status → audit rows: `resolved`/`tag` → `[]`; `ambiguous` → one `ambiguous_cross_kind_reference` row; `unresolved` → one `unresolved_reference` row (with a cross-project-address escape). The `AuditRow` TypedDict shape is `{check, status, source, field, target, details}` (all `str`).
- **Audit loads non-strict; build loads strict** — `health.collect_unresolved_refs` / `materialization_audit` pass `strict_identity=False`; `materialize_graph` / `audit_project_graph` use the default `True`. (This is the reachability boundary above.)
- **Test idioms:** `tests/test_graph_migrate_identity_audit.py` already has `_owner(cid, adapter, path, deprecated=False)` building an `IdentityDeclaration` with `owner_scope="proj"`, and already imports `IdentityDeclaration`, `IdentityTable`, `ParticipationMode`, `SourceRef`. `tests/test_dataset_usage_materialize.py` shows direct `Entity(...)` construction; required `Entity` fields: `id, canonical_id, kind, type (EntityType.*), title, project, ontology_terms=[], related=[…], source_refs=[], content_preview="", file_path`. (No task in this plan constructs a `ProjectSources` — the audit is tested by calling `_audit_reference` directly.)
- **All new names are free** (`grep` confirms no current use): `owner_scopes_by_id`, `scope_ambiguous`, `ambiguous_reference`, `_split_scope`, `_resolve_unscoped`. No `tests/test_reference_resolution*.py` exists yet.

---

## Task 1: Scope index on `IdentityTable`

**Files:**
- Modify: `src/science_tool/graph/identity_table.py`
- Test: `tests/test_graph_identity_table.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_graph_identity_table.py`. First confirm the imports it already has (`IdentityDeclaration`, `IdentityTable`, `ParticipationMode`, `SourceRef`); add any missing. Use this helper-free, explicit construction:

```python
def test_owner_scopes_by_id_groups_scopes_per_canonical_id() -> None:
    def owner(cid: str, scope: str) -> IdentityDeclaration:
        return IdentityDeclaration(
            canonical_id=cid,
            participation_mode=ParticipationMode.OWNER,
            owner_scope=scope,
            adapter="markdown",
            source_ref=None,
        )

    table = IdentityTable(
        rows=[
            owner("topic:bayesian", "proj"),
            owner("topic:bayesian", "commons"),  # same id, two scopes
            owner("hypothesis:h1", "proj"),
            IdentityDeclaration(  # a borrower row must NOT count as an owning scope
                canonical_id="topic:bayesian",
                participation_mode=ParticipationMode.BORROWER,
                owner_scope="commons",
                adapter="overlay",
                source_ref=None,
            ),
        ]
    )
    index = table.owner_scopes_by_id()
    assert index["topic:bayesian"] == frozenset({"proj", "commons"})
    assert index["hypothesis:h1"] == frozenset({"proj"})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_graph_identity_table.py -q`
Expected: FAIL — `AttributeError: 'IdentityTable' object has no attribute 'owner_scopes_by_id'`.

- [ ] **Step 3: Implement the method**

Add to the `IdentityTable` dataclass in `identity_table.py`, immediately after `owners()` (reuses the already-imported `defaultdict`):

```python
    def owner_scopes_by_id(self) -> dict[str, frozenset[str]]:
        """canonical_id -> the owner scopes that own it across all loaded scopes.

        Derived from owner rows only (borrowers/external-refs do not own). Used by
        the reference resolver to detect a bare id owned in >1 loaded scope
        (design §B3a) and to enumerate valid scope-prefix names.
        """
        grouped: dict[str, set[str]] = defaultdict(set)
        for scope, cid in self.owners():
            grouped[cid].add(scope)
        return {cid: frozenset(scopes) for cid, scopes in grouped.items()}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_graph_identity_table.py -q`
Expected: PASS.

- [ ] **Step 5: ruff + Commit**

Run: `cd ~/d/science/science && uv run --frozen ruff check src/science_tool/graph/identity_table.py tests/test_graph_identity_table.py && uv run --frozen ruff format --check src/science_tool/graph/identity_table.py tests/test_graph_identity_table.py` (fix with `ruff format` on those files if needed). Then:

```bash
cd ~/d/science && git add science/src/science_tool/graph/identity_table.py science/tests/test_graph_identity_table.py
git commit -m "feat(substrate): IdentityTable.owner_scopes_by_id (scope index for ref resolution)"
```
Do NOT add any "Co-Authored-By" trailer.

---

## Task 2: Scope-aware `ReferenceResolver`

Adds the scope index + scope names to the resolver, scoped-form parsing, and the `scope_ambiguous` status. **Backward compatibility is a hard requirement:** with no `identity_table` the resolver must behave byte-for-byte as today (the existing suite proves this).

**Files:**
- Modify: `src/science_tool/graph/reference_resolution.py`
- Test (create): `tests/test_reference_resolution_scoped.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_reference_resolution_scoped.py`:

```python
from __future__ import annotations

from science_model.entities import Entity, EntityType

from science_tool.graph.identity_table import (
    IdentityDeclaration,
    IdentityTable,
    ParticipationMode,
)
from science_tool.graph.reference_resolution import ReferenceResolver


def _entity(cid: str, kind: str, etype: EntityType, *, related: list[str] | None = None) -> Entity:
    k, _slug = cid.split(":", 1)
    return Entity(
        id=cid,
        canonical_id=cid,
        kind=kind,
        type=etype,
        title=cid,
        project="proj",
        ontology_terms=[],
        related=related or [],
        source_refs=[],
        content_preview="",
        file_path=f"entities/{k}/{_slug}.md",
    )


def _owner(cid: str, scope: str) -> IdentityDeclaration:
    return IdentityDeclaration(
        canonical_id=cid,
        participation_mode=ParticipationMode.OWNER,
        owner_scope=scope,
        adapter="markdown",
        source_ref=None,
    )


def _resolver_two_scope() -> ReferenceResolver:
    # one entity (dedup keeps one) but the identity table records two owner scopes
    entities = [_entity("topic:bayesian", "topic", EntityType.TOPIC)]
    table = IdentityTable(rows=[_owner("topic:bayesian", "proj"), _owner("topic:bayesian", "commons")])
    return ReferenceResolver.from_entities(entities, identity_table=table)


def test_bare_ref_owned_in_two_scopes_is_scope_ambiguous() -> None:
    res = _resolver_two_scope().resolve("topic:bayesian")
    assert res.status == "scope_ambiguous"
    assert res.candidates == ("commons", "proj")  # sorted owning scopes


def test_scoped_ref_resolves_to_named_owner_scope() -> None:
    res = _resolver_two_scope().resolve("commons:topic:bayesian")
    assert res.status == "resolved"
    assert res.canonical_id == "topic:bayesian"  # scope is not part of the id


def test_unknown_scope_prefix_is_treated_as_bare_and_unresolved() -> None:
    # "other" is NOT a loaded scope name -> _split_scope leaves it bare -> a bare
    # lookup of the whole "other:topic:bayesian" string fails -> unresolved.
    res = _resolver_two_scope().resolve("other:topic:bayesian")
    assert res.status == "unresolved"


def test_scoped_ref_to_loaded_scope_that_does_not_own_is_unresolved() -> None:
    # "other" IS a loaded scope (it owns a different id), so the prefix is parsed as
    # a scope; but "other" does not own topic:bayesian, so the scoped form is
    # rejected (not silently resolved) -> unresolved.
    entities = [_entity("topic:bayesian", "topic", EntityType.TOPIC)]
    table = IdentityTable(
        rows=[
            _owner("topic:bayesian", "proj"),
            _owner("topic:bayesian", "commons"),
            _owner("decision:d1", "other"),  # makes "other" a known loaded scope name
        ]
    )
    resolver = ReferenceResolver.from_entities(entities, identity_table=table)
    assert "other" in resolver.scope_names  # precondition: prefix is parseable as a scope
    res = resolver.resolve("other:topic:bayesian")
    assert res.status == "unresolved"


def test_bare_ref_owned_in_one_scope_is_resolved_not_ambiguous() -> None:
    entities = [_entity("hypothesis:h1", "hypothesis", EntityType.HYPOTHESIS)]
    table = IdentityTable(rows=[_owner("hypothesis:h1", "proj")])
    res = ReferenceResolver.from_entities(entities, identity_table=table).resolve("hypothesis:h1")
    assert res.status == "resolved"
    assert res.canonical_id == "hypothesis:h1"


def test_kind_qualified_bare_ref_not_misparsed_as_scope() -> None:
    # A bare `kind:slug` must never be read as scope=`kind`, even if a scope shares
    # that name. Here scope "topic" exists, and "topic:bayesian" is a bare id whose
    # remainder ("bayesian") has no colon -> treated as bare, resolves normally.
    entities = [_entity("topic:bayesian", "topic", EntityType.TOPIC)]
    table = IdentityTable(rows=[_owner("topic:bayesian", "topic")])  # scope literally named "topic"
    res = ReferenceResolver.from_entities(entities, identity_table=table).resolve("topic:bayesian")
    assert res.status == "resolved"
    assert res.canonical_id == "topic:bayesian"


def test_backward_compatible_without_identity_table() -> None:
    # No identity_table -> no scope parsing, no ambiguity: identical to legacy behavior.
    entities = [_entity("topic:bayesian", "topic", EntityType.TOPIC)]
    resolver = ReferenceResolver.from_entities(entities)  # legacy call
    assert resolver.resolve("topic:bayesian").status == "resolved"
    assert resolver.resolve("commons:topic:bayesian").status == "unresolved"
    assert resolver.scope_names == frozenset()
    assert resolver.owner_scopes == {}
```

> If `EntityType.TOPIC` / `EntityType.HYPOTHESIS` are not the exact member names, open `science_model.entities` and use the real members (do not invent). The test only needs any two valid kinds.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_reference_resolution_scoped.py -q`
Expected: FAIL — `TypeError: from_entities() got an unexpected keyword argument 'identity_table'` (and/or missing `scope_names`/`owner_scopes`).

- [ ] **Step 3: Implement scope-awareness**

Edit `reference_resolution.py`. (a) Update imports at the top:

```python
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from science_model import normalize_alias
from science_model.entities import Entity

from science_tool.graph.sources import build_alias_map

if TYPE_CHECKING:
    from science_tool.graph.identity_table import IdentityTable
```

(b) Add the two new fields to the frozen dataclass (after the existing two; non-default fields stay first):

```python
@dataclass(frozen=True)
class ReferenceResolver:
    """Resolve authored entity references with optional fallback rules."""

    alias_map: dict[str, str]
    slug_index: dict[str, frozenset[str]]
    owner_scopes: dict[str, frozenset[str]] = field(default_factory=dict)
    scope_names: frozenset[str] = frozenset()
```

(c) Extend `from_entities` to accept and consume an optional identity table (duck-typed via `owner_scopes_by_id()`; no runtime import, so no import cycle):

```python
    @classmethod
    def from_entities(
        cls,
        entities: list[Entity],
        *,
        manual_aliases: dict[str, str] | None = None,
        identity_table: "IdentityTable | None" = None,
    ) -> "ReferenceResolver":
        alias_map = build_alias_map(entities, manual_aliases=manual_aliases)
        identity_map = _build_identity_map(entities, alias_map)
        slug_index: dict[str, set[str]] = {}

        for entity in entities:
            canonical_id = entity.canonical_id
            if ":" not in canonical_id:
                continue
            _, slug = canonical_id.split(":", 1)
            slug_index.setdefault(slug.lower(), set()).add(identity_map.get(canonical_id, canonical_id))

        owner_scopes: dict[str, frozenset[str]] = {}
        scope_names: frozenset[str] = frozenset()
        if identity_table is not None:
            owner_scopes = identity_table.owner_scopes_by_id()
            scope_names = frozenset(scope for scopes in owner_scopes.values() for scope in scopes)

        return cls(
            alias_map=alias_map,
            slug_index={slug: frozenset(sorted(ids)) for slug, ids in slug_index.items()},
            owner_scopes=owner_scopes,
            scope_names=scope_names,
        )
```

(d) Replace the body of `resolve` and add the two helpers. The legacy bare logic moves verbatim into `_resolve_unscoped`; `resolve` wraps it with scope handling:

```python
    def resolve(
        self,
        raw: str,
        *,
        allow_cross_kind_fallback: bool = False,
        allow_tag: bool = False,
    ) -> ReferenceResolution:
        if raw.startswith("tag:"):
            return ReferenceResolution(status="tag" if allow_tag else "unresolved", raw=raw)

        # Scoped reference form <scope>:<kind>:<slug> (design §B3a): a leading
        # known-scope prefix names which scope's owner is meant. It resolves to the
        # same canonical id (scope is not part of the id) but only if that scope
        # actually owns the id.
        scope, inner = self._split_scope(raw)
        if scope is not None:
            inner_res = self._resolve_unscoped(inner, allow_cross_kind_fallback=allow_cross_kind_fallback)
            if (
                inner_res.status == "resolved"
                and inner_res.canonical_id is not None
                and scope in self.owner_scopes.get(inner_res.canonical_id, frozenset())
            ):
                return ReferenceResolution(status="resolved", raw=raw, canonical_id=inner_res.canonical_id)
            return ReferenceResolution(status="unresolved", raw=raw)

        resolution = self._resolve_unscoped(raw, allow_cross_kind_fallback=allow_cross_kind_fallback)
        if resolution.status == "resolved" and resolution.canonical_id is not None:
            scopes = self.owner_scopes.get(resolution.canonical_id, frozenset())
            if len(scopes) > 1:
                # bare id owned by an owner in >1 loaded scope -> refuse; a scoped
                # form is required (the search chain never shadows owner ambiguity).
                return ReferenceResolution(status="scope_ambiguous", raw=raw, candidates=tuple(sorted(scopes)))
        return resolution

    def _split_scope(self, raw: str) -> tuple[str | None, str]:
        """Split <scope>:<kind>:<slug> into (scope, <kind>:<slug>); (None, raw) if bare.

        A prefix counts as a scope only when it is a known loaded scope name AND the
        remainder is itself kind-qualified (contains a colon), so a bare `kind:slug`
        is never misread as scope `kind`.
        """
        if not self.scope_names or ":" not in raw:
            return (None, raw)
        head, rest = raw.split(":", 1)
        if head in self.scope_names and ":" in rest:
            return (head, rest)
        return (None, raw)

    def _resolve_unscoped(self, raw: str, *, allow_cross_kind_fallback: bool) -> ReferenceResolution:
        resolved = normalize_alias(raw, self.alias_map)
        if raw in self.alias_map or raw.lower() in self.alias_map:
            return ReferenceResolution(status="resolved", raw=raw, canonical_id=resolved)

        if not allow_cross_kind_fallback or ":" not in raw:
            return ReferenceResolution(status="unresolved", raw=raw)

        _, slug = raw.split(":", 1)
        identities = tuple(self.slug_index.get(slug.lower(), ()))
        if len(identities) == 1:
            return ReferenceResolution(status="resolved", raw=raw, canonical_id=identities[0])
        if len(identities) > 1:
            return ReferenceResolution(status="ambiguous", raw=raw, candidates=identities)
        return ReferenceResolution(status="unresolved", raw=raw)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_reference_resolution_scoped.py -q`
Expected: PASS (all 7).

- [ ] **Step 5: Backward-compat regression — run the resolver's existing consumers**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_graph_migrate.py tests/test_commons_reference_graph.py tests/test_produced_by_materialize.py -q`
Expected: all PASS, unchanged. (These exercise `from_entities` without an identity table and the full `_audit_reference`/materialize resolution paths.) If any fail, the legacy path was not preserved — fix `_resolve_unscoped` to match the original lines exactly; do NOT change the tests.

- [ ] **Step 6: ruff + Commit**

Run: `cd ~/d/science/science && uv run --frozen ruff check src/science_tool/graph/reference_resolution.py tests/test_reference_resolution_scoped.py && uv run --frozen ruff format --check src/science_tool/graph/reference_resolution.py tests/test_reference_resolution_scoped.py` (fix with `ruff format` if needed). Then:

```bash
cd ~/d/science && git add science/src/science_tool/graph/reference_resolution.py science/tests/test_reference_resolution_scoped.py
git commit -m "feat(substrate): scope-aware ReferenceResolver (scoped form + scope_ambiguous)"
```
No "Co-Authored-By" trailer.

---

## Task 3: `ambiguous_reference` row-emission (mechanism only — NOT wired into `audit_project_sources`)

Add the `scope_ambiguous` → `ambiguous_reference` branch to `_audit_reference`, and prove it with **purely direct** unit tests that pass a hand-built scope-aware resolver into `_audit_reference`.

**Critical scope rule — do NOT wire `audit_project_sources`'s resolver to the identity table in this plan.** Doing so would make the audit *accept* a scoped ref (`commons:topic:x`) — reachable today in any commons-borrowing project, where `commons` is a loaded scope — while `materialize` (gated by `audit_project_sources` at `materialize.py:193`, then built with a **scope-naive** resolver at `materialize.py:91`/`:343`) silently **drops** that edge. That is a **fail-open** path for new syntax. To avoid it, the `audit_project_sources` resolver wiring **and** the `materialize` resolver wiring land **together** in 1.4 (atop scope-aware dedup), so audit and build go scope-aware in the same change. In 1.3, `audit_project_sources` stays scope-naive: it neither accepts scoped refs nor emits `ambiguous_reference` on real disk. The branch added here is dormant until 1.4 passes it a scope-aware resolver, and is exercised now only by the direct `_audit_reference` unit tests below.

**Files:**
- Modify: `src/science_tool/graph/migrate.py` (add the `_audit_reference` branch only — leave the `migrate.py:168` and `migrate.py:261` resolver constructions UNCHANGED)
- Test: `tests/test_graph_migrate_identity_audit.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_graph_migrate_identity_audit.py`. Add imports at the top of the file as needed (the file already imports `IdentityDeclaration`, `IdentityTable`, `ParticipationMode`, `SourceRef`, and has the `_owner(cid, adapter, path, deprecated=False)` helper with `owner_scope="proj"`):

```python
from science_model.entities import Entity, EntityType
from science_tool.graph.migrate import _audit_reference
from science_tool.graph.reference_resolution import ReferenceResolver
```

> If `EntityType.TOPIC` / `EntityType.HYPOTHESIS` are not the exact member names, open `science_model.entities` and use the real members (do not invent).

Then append:

```python
def _commons_owner(cid: str) -> IdentityDeclaration:
    return IdentityDeclaration(
        canonical_id=cid,
        participation_mode=ParticipationMode.OWNER,
        owner_scope="commons",
        adapter="commons-merged",
        source_ref=SourceRef(adapter_name="commons-merged", path="<commons>"),
    )


def _ref_entity(cid: str, kind: str, etype: EntityType, *, related: list[str] | None = None) -> Entity:
    k, slug = cid.split(":", 1)
    return Entity(
        id=cid,
        canonical_id=cid,
        kind=kind,
        type=etype,
        title=cid,
        project="proj",
        ontology_terms=[],
        related=related or [],
        source_refs=[],
        content_preview="",
        file_path=f"entities/{k}/{slug}.md",
    )


def _two_scope_resolver() -> ReferenceResolver:
    # one entity (dedup keeps one) but the identity table records two owner scopes;
    # supplied DIRECTLY because no disk loader produces a two-scope table yet (see
    # the Reachability boundary). This is a purely direct unit test of _audit_reference.
    entities = [_ref_entity("topic:bayesian", "topic", EntityType.TOPIC)]
    table = IdentityTable(
        rows=[_owner("topic:bayesian", "markdown", "entities/topics/bayesian.md"), _commons_owner("topic:bayesian")]
    )
    return ReferenceResolver.from_entities(entities, identity_table=table)


def test_audit_reference_emits_ambiguous_reference_row() -> None:
    referer = _ref_entity("hypothesis:h1", "hypothesis", EntityType.HYPOTHESIS, related=["topic:bayesian"])
    rows = _audit_reference(
        referer,
        "related",
        "topic:bayesian",
        _two_scope_resolver(),
        ext_prefixes=frozenset(),
        allow_cross_kind_fallback=True,
        allow_tag=True,
    )
    assert len(rows) == 1
    row = rows[0]
    assert row["check"] == "ambiguous_reference"
    assert row["status"] == "fail"
    assert row["source"] == "hypothesis:h1"
    assert row["field"] == "related"
    assert row["target"] == "topic:bayesian"
    assert "commons" in row["details"]
    assert "commons:topic:bayesian" in row["details"]  # suggested scoped form


def test_audit_reference_scoped_form_is_not_flagged() -> None:
    referer = _ref_entity("hypothesis:h1", "hypothesis", EntityType.HYPOTHESIS, related=["commons:topic:bayesian"])
    rows = _audit_reference(
        referer,
        "related",
        "commons:topic:bayesian",
        _two_scope_resolver(),
        ext_prefixes=frozenset(),
        allow_cross_kind_fallback=True,
        allow_tag=True,
    )
    assert rows == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_graph_migrate_identity_audit.py -q`
Expected: `test_audit_reference_emits_ambiguous_reference_row` FAILS — the scope-aware resolver (from Task 2) returns `scope_ambiguous`, but `_audit_reference` has no branch for it yet, so it falls through to the trailing `return []` and the test sees 0 rows instead of 1. (`test_audit_reference_scoped_form_is_not_flagged` already passes, since a scoped form resolves and yields `[]` regardless of the missing branch — it guards the no-false-positive direction.)

- [ ] **Step 3: Implement the `ambiguous_reference` branch**

In `_audit_reference` (`migrate.py`), add a branch for the new status, placed **after** the `ambiguous` branch and **before** the `unresolved` branch (no other change to `migrate.py` — in particular, do NOT touch the resolver construction at line 168):

```python
    if resolution.status == "scope_ambiguous":
        scopes = ", ".join(resolution.candidates)
        suggestion = f"{resolution.candidates[0]}:{raw_target}" if resolution.candidates else raw_target
        return [
            {
                "check": "ambiguous_reference",
                "status": "fail",
                "source": entity.canonical_id,
                "field": field_name,
                "target": raw_target,
                "details": (
                    f"{entity.file_path} reference '{raw_target}' is owned in multiple loaded scopes "
                    f"({scopes}); disambiguate with a scoped form, e.g. {suggestion}"
                ),
            }
        ]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_graph_migrate_identity_audit.py -q`
Expected: PASS (existing identity-audit tests + the 2 new).

- [ ] **Step 5: Confirm `audit_project_sources` is NOT scope-aware (no fail-open)**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_graph_migrate.py tests/test_identity_audit_entrypoints.py tests/test_entity_identity_health.py -q`
Expected: all PASS, unchanged. The line-168 resolver was deliberately left scope-naive, so no audit entry point newly accepts scoped refs or emits `ambiguous_reference` — there is no path where audit greenlights a ref that `materialize` would drop. (Verify the diff did not touch `migrate.py:168`: `cd ~/d/science && git diff -- science/src/science_tool/graph/migrate.py | grep -n "identity_table=" || echo "good: line-168 resolver unchanged"`.)

- [ ] **Step 6: ruff + Commit**

Run: `cd ~/d/science/science && uv run --frozen ruff check src/science_tool/graph/migrate.py tests/test_graph_migrate_identity_audit.py && uv run --frozen ruff format --check src/science_tool/graph/migrate.py tests/test_graph_migrate_identity_audit.py` (fix with `ruff format` if needed). Then:

```bash
cd ~/d/science && git add science/src/science_tool/graph/migrate.py science/tests/test_graph_migrate_identity_audit.py
git commit -m "feat(substrate): _audit_reference ambiguous_reference branch (dormant until 1.4 wiring)"
```
No "Co-Authored-By" trailer.

---

## Task 4: Full-suite green + ruff

**Files:** none (verification only).

- [ ] **Step 1: Run the full test suite**

Run: `cd ~/d/science/science && uv run --frozen pytest -q`
Expected: all PASS (baseline before this plan: 4641 passed, 6 skipped, 4 deselected; this plan adds tests and additive behavior only). New behavior fires only when an id is owned in >1 loaded scope, which is **not producible from disk** today (Reachability boundary) — so no real project/fixture exercises it. If a fixture now fails, it is a backward-compat regression in `_resolve_unscoped` → restore the original bare logic exactly (do NOT change the failing test).

- [ ] **Step 2: Lint/format (changed files)**

Run: `cd ~/d/science/science && uv run --frozen ruff check src/science_tool/graph/identity_table.py src/science_tool/graph/reference_resolution.py src/science_tool/graph/migrate.py tests/test_graph_identity_table.py tests/test_reference_resolution_scoped.py tests/test_graph_migrate_identity_audit.py && uv run --frozen ruff format --check src/science_tool/graph/identity_table.py src/science_tool/graph/reference_resolution.py src/science_tool/graph/migrate.py tests/test_graph_identity_table.py tests/test_reference_resolution_scoped.py tests/test_graph_migrate_identity_audit.py`
Expected: clean. (Do NOT attempt a repo-wide reformat; only the files this plan touches must be clean — the repo carries pre-existing ruff debt.)

- [ ] **Step 3: Commit any lint fixes**

Only if Step 2 required changes:
```bash
cd ~/d/science && git add science/src/science_tool/graph/ science/tests/
git commit -m "chore(substrate): ruff clean for scoped-ref resolution"
```

---

## Self-Review

**1. Spec coverage (§B3a, this plan's scope):**
- "Bare ids must be unambiguous across all loaded scopes; a bare id owned in >1 loaded scope is an `ambiguous_reference` error" → Task 2 `scope_ambiguous` status + Task 3 `ambiguous_reference` audit row. ◐ (the headline **mechanism** is built and consumer-tested; it becomes disk-reachable when 1.4's scope-aware dedup feeds it real two-scope tables — see Reachability boundary)
- "A scoped reference form (`commons:topic:x`) is required to disambiguate" → Task 2 `_split_scope` + scoped resolution validated against `owner_scopes`. ✓
- "The search chain never shadows owner ambiguity" → bare resolution returns `scope_ambiguous` instead of letting one scope win; the scoped form is the only escape. ✓
- "Minimal compiler-scoped form only; full cross-project validation deferred to `t068`" → only locally-loaded scopes are consulted; no remote scope verification. ✓ (explicitly out of scope)
- §C2 "every consumer reads the compiled model": 1.3 builds the scope-aware resolver that consumers will use, but wires **neither** consumer yet — both `audit_project_sources` and `materialize` are wired to the compiled `IdentityTable` together in 1.4, so they go scope-aware in one change and never diverge (no fail-open). Mechanism-only here — partial-by-design. ◐
- Backward compatibility: no `identity_table` ⇒ empty `scope_names`/`owner_scopes` ⇒ `_split_scope` returns `(None, raw)` and the bare path never reaches the `len(scopes) > 1` branch ⇒ legacy behavior. Asserted in `test_backward_compatible_without_identity_table` and the regression suites (Task 2 Step 5, Task 3 Step 6). ✓

**2. Placeholder scan:** No TBD/TODO. Every code step shows complete code; every test step shows assertions and exact commands. The one soft spot — exact `EntityType` member names — is flagged inline (Task 2 and Task 3) with the rule "use the real members from `science_model.entities`, do not invent." ✓

**3. Type/name consistency:** `owner_scopes_by_id` (Task 1) is consumed by `from_entities` (Task 2) and indirectly by Task 3. The new status string `scope_ambiguous` is produced in `resolve` (Task 2) and matched in `_audit_reference` (Task 3); the audit `check` string is `ambiguous_reference` (distinct from the pre-existing `ambiguous_cross_kind_reference`). `owner_scopes: dict[str, frozenset[str]]` and `scope_names: frozenset[str]` field names are identical across the dataclass, `from_entities`, `resolve`, `_split_scope`, and the backward-compat test. `candidates` carries the sorted owning scopes for `scope_ambiguous` (reusing the existing `ReferenceResolution.candidates` field). ✓

**4. Blast radius:** Effectively zero for production. No consumer is wired to the scope index in 1.3 — both `audit_project_sources` and `materialize` keep constructing scope-naive resolvers (`from_entities` with no `identity_table`), so neither the scoped-form parsing nor `scope_ambiguous` can fire on any real project; only the direct `_audit_reference` / resolver unit tests reach those paths. The single touch to a production code path is the new `_audit_reference` branch, which is unreachable until 1.4 passes it a scope-aware resolver. The new `from_entities(identity_table=…)` param and the `IdentityTable.owner_scopes_by_id()` method are purely additive (default off). ✓

---

## Where this sits (Phase 1 roadmap — NOT part of this plan)

Phase 1.1 (`e2b3a757`) built the compiled `IdentityTable` + non-strict reporting; Phase 1.2 (`8a87e5b7`) added the owner-root overlay conformance guard. **This is Phase 1.3**: executable scope-aware reference resolution (§B3a) in the shared resolver + the audit enforcement surface. Remaining Phase-1 sub-plans (each its own full plan):

- **1.4 — Migrator on the compiled model (§C4) + activate scope-aware resolution:** replace the alias-collision proxy + in-memory simulation/masking with `build_identity_table`-based detection (block apply on any `identity_collision`); renumber only non-transitional `this-project` owners. Introduces **scope-aware entity dedup** (so the loader retains both owner rows for one id, making two-scope tables producible from disk) and, in the *same* change, **wires the scope-aware resolver into both `audit_project_sources` (`migrate.py:168`) and `materialize` (`materialize.py:91`)** — activating the dormant 1.3 mechanism on both paths at once, with no audit/build fail-open window. Depends on 1.1–1.3.
- **1.5 — Migrate orphan datapackages (§B4):** synthesize/promote owners for datapackage-only datasets; dataset `doc/datasets/` dual-SSOT handling. Depends on 1.1.

Phases 2–4 (dataset reconciliation, `entities.yaml` retirement, external-reference resolver / `t068` federated scoped refs) follow Phase 1 and are out of scope here.

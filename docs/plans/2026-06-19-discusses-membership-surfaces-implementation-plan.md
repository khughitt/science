# Unifying `cito:discusses` Emission Across Authoring Surfaces — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Route every `cito:discusses` emission through one chokepoint that always writes the `BundleMembership` role node, and let the authored-relations store and the store-CLI bridge author non-`core` roles — so a membership role is honored regardless of which surface declares the edge.

**Architecture:** Extract a single `emit_discusses_membership(...)` into `graph/io.py` (the shared low-level vocabulary module). The frontmatter path (already role-aware) is refactored to call it; the authored-relations store (`_add_authored_relation`) and the store-CLI bridge (`bridge_between_refs`) are re-pointed at it, defaulting to `core`. Then `SourceRelation` gains an optional `role` field and the bridge command gains `--role`, both threaded into the chokepoint. The chokepoint loud-fails non-bundle frames uniformly. No new vocabulary, no new semantics — see the design doc.

**Tech Stack:** Python ≥3.11, Pydantic v2, rdflib, pytest, `uv`. Two packages: model (`science/model`, importable as `science_model`) and tool (`science/src`, importable as `science_tool`).

**Spec:** [`2026-06-19-discusses-membership-surfaces-design.md`](./2026-06-19-discusses-membership-surfaces-design.md). Parent feature: [`2026-06-19-contextual-structural-roles-design.md`](./2026-06-19-contextual-structural-roles-design.md).

## Global Constraints

- **Working directory:** all commands run from `~/d/science` (the repo root) unless a step says otherwise. Tests run from the nested `science/` and `science/model/` package dirs.
- **Test runner:** `uv run --frozen pytest <path> -v`. Validation: `uv run --frozen science validate`.
- **Authority boundary (design §0):** touch **only** the emission and authoring of the `cito:discusses` membership relation. Add **no** causal-edge vocabulary; do **not** make the membership node truth-apt; do **not** change the closed role vocabulary `core | rival | background`.
- **Annotate, never replace:** the plain `(prop, cito:discusses, frame)` triple MUST always be emitted exactly as today. The role rides on a separate `BundleMembership` node.
- **Migration default = `core`:** an unlabeled membership (bare string, missing `role`, or a forward `sci:hasProposition` member) means `core`. The conjunction result MUST be byte-for-byte unchanged on the existing corpus until a curator labels a member.
- **One emitter:** after this work, `graph.add((_, CITO_NS.discusses, _))` appears in exactly one place — inside `emit_discusses_membership`. A grep that finds it anywhere else is a defect.
- **Discusses targets are bundles:** a `cito:discusses` frame MUST resolve to a `hypothesis` or `mechanism`. The chokepoint loud-fails otherwise (design §3.4). Run the Task 6 corpus audit before relying on this in any non-`mm30` project.
- **Style:** explicit over defensive; fail loudly, no silent fallbacks. Follow existing module idioms.

---

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `science/src/science_tool/graph/io.py` | Graph vocabulary + the membership chokepoint | Add `membership_uri_for()` + `emit_discusses_membership()` |
| `science/src/science_tool/graph/materialize.py` | Frontmatter → RDF; authored relations | Repoint frontmatter loop (642–648) and `_add_authored_relation` (1208) at the chokepoint; remove the now-duplicated inline emit + `_membership_uri` |
| `science/src/science_tool/graph/sources.py` | Authored-relation model | Add `role: MembershipRole | None = None` to `SourceRelation` |
| `science/src/science_tool/graph/store/mutations.py` | Store CLI mutations | Repoint `bridge_between_refs` emit (228) at the chokepoint; add `role` param |
| `science/src/science_tool/cli.py` | CLI surface | Add `--role` to the `--bridge-between` command |
| `science/src/science_tool/validate/checks/propositions.py` (or relations check) | Frontmatter/relation QA | Validate `SourceRelation.role` (predicate, target, enum, cross-surface conflict) |
| `science/tests/test_membership_chokepoint.py` | Chokepoint unit tests | Create |
| `science/tests/test_membership_materialize.py` | Relations-store membership tests | Extend (exists) |
| `science/tests/test_membership_bridge.py` | Bridge-role tests | Create |
| `science/tests/test_membership_validation.py` | Cross-surface validation tests | Extend (exists) |

---

## Task 1: Extract the emission chokepoint; repoint the frontmatter path

Pure refactor — externally behavior-preserving. The frontmatter graph output must be byte-for-byte identical; the only change is that the triple + node are emitted by one shared function.

**Files:**
- Modify: `science/src/science_tool/graph/io.py`
- Modify: `science/src/science_tool/graph/materialize.py:632–648` (frontmatter emit) and `:107–110` (`_membership_uri`)
- Test: `science/tests/test_membership_chokepoint.py` (create)

**Interfaces:**
- Produces (in `science_tool.graph.io`):
  - `membership_uri_for(prop_cid: str, frame_cid: str) -> URIRef` — moved verbatim from `materialize._membership_uri`.
  - `emit_discusses_membership(knowledge, *, prop_uri: URIRef, frame_uri: URIRef, prop_cid: str, frame_cid: str, role: MembershipRole = MembershipRole.CORE) -> None` — loud-fails non-bundle `frame_cid`, emits the plain triple, emits the `BundleMembership` node.
- Consumes: `materialize.py` imports both from `io`; `_membership_uri` is deleted (or re-exported as a thin alias if other modules import it — grep first).

- [ ] **Step 1: Write the failing chokepoint unit test**

Create `science/tests/test_membership_chokepoint.py`:

```python
from __future__ import annotations

import pytest
from rdflib import Graph, Literal, RDF

from science_model.reasoning import MembershipRole
from science_tool.graph.io import (
    CITO_NS,
    PROJECT_NS,
    SCI_NS,
    emit_discusses_membership,
    membership_uri_for,
    entity_uri_for_ref,
)


def _emit(role=MembershipRole.CORE, frame_cid="hypothesis:0001-foo"):
    g = Graph()
    prop_cid = "proposition:0011-bar"
    emit_discusses_membership(
        g,
        prop_uri=entity_uri_for_ref(prop_cid),
        frame_uri=entity_uri_for_ref(frame_cid),
        prop_cid=prop_cid,
        frame_cid=frame_cid,
        role=role,
    )
    return g, prop_cid, frame_cid


def test_plain_triple_always_emitted():
    g, prop_cid, frame_cid = _emit()
    assert (
        entity_uri_for_ref(prop_cid),
        CITO_NS.discusses,
        entity_uri_for_ref(frame_cid),
    ) in g


def test_core_membership_node_emitted():
    g, prop_cid, frame_cid = _emit(role=MembershipRole.CORE)
    node = membership_uri_for(prop_cid, frame_cid)
    assert (node, RDF.type, SCI_NS.BundleMembership) in g
    assert (node, SCI_NS.membershipProposition, entity_uri_for_ref(prop_cid)) in g
    assert (node, SCI_NS.membershipFrame, entity_uri_for_ref(frame_cid)) in g
    assert (node, SCI_NS.membershipRole, Literal("core")) in g


def test_background_role_recorded():
    g, prop_cid, frame_cid = _emit(role=MembershipRole.BACKGROUND)
    node = membership_uri_for(prop_cid, frame_cid)
    assert (node, SCI_NS.membershipRole, Literal("background")) in g


def test_non_bundle_frame_loud_fails():
    with pytest.raises(ValueError, match="not a bundle"):
        _emit(frame_cid="topic:0003-context")
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_membership_chokepoint.py -v`
Expected: FAIL — `ImportError: cannot import name 'emit_discusses_membership'`.

- [ ] **Step 3: Add the chokepoint to `io.py`**

In `science/src/science_tool/graph/io.py`, ensure `RDF` and `Literal` are imported from `rdflib` and `MembershipRole` from `science_model.reasoning` (add imports if absent), then add:

```python
def membership_uri_for(prop_cid: str, frame_cid: str) -> URIRef:
    """Deterministic IRI for a (proposition, frame) BundleMembership node."""
    slug = f"{prop_cid}__{frame_cid}".replace(":", "_").replace("/", "_")
    return URIRef(PROJECT_NS[f"membership/{slug}"])


def emit_discusses_membership(
    knowledge,
    *,
    prop_uri: URIRef,
    frame_uri: URIRef,
    prop_cid: str,
    frame_cid: str,
    role: MembershipRole = MembershipRole.CORE,
) -> None:
    """The one place a cito:discusses triple is added to the knowledge graph.

    Always emits the plain (prop, cito:discusses, frame) triple, plus a
    non-truth-apt BundleMembership node carrying the role. Loud-fails a frame
    that is not a bundle (hypothesis/mechanism) — design §3.4, contextual-roles §5.
    """
    frame_kind = frame_cid.split(":", 1)[0]
    if frame_kind not in ("hypothesis", "mechanism"):
        raise ValueError(
            f"{prop_cid} discusses {frame_cid!r}, which is a {frame_kind!r}, not a "
            "bundle (hypothesis/mechanism); membership roles are only valid on bundle "
            "frames (spec §5)."
        )
    # 1) Plain triple, emitted verbatim — annotate, never replace.
    knowledge.add((prop_uri, CITO_NS.discusses, frame_uri))
    # 2) BundleMembership plumbing node carrying the role.
    node = membership_uri_for(prop_cid, frame_cid)
    knowledge.add((node, RDF.type, SCI_NS.BundleMembership))
    knowledge.add((node, SCI_NS.membershipProposition, prop_uri))
    knowledge.add((node, SCI_NS.membershipFrame, frame_uri))
    knowledge.add((node, SCI_NS.membershipRole, Literal(role.value)))
```

- [ ] **Step 4: Run the chokepoint test to verify it passes**

Run: `cd science && uv run --frozen pytest tests/test_membership_chokepoint.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Repoint the frontmatter path at the chokepoint**

In `materialize.py`, replace the inline block at `632–648` (the `frame_uri = …` resolution stays; the kind-check + 6 `knowledge.add` lines collapse into one call):

```python
        frame_uri = _entity_uri(target.canonical_id)
        emit_discusses_membership(
            knowledge,
            prop_uri=entity_uri,
            frame_uri=frame_uri,
            prop_cid=entity.canonical_id,
            frame_cid=resolution.canonical_id,
            role=role,
        )
```

Delete the now-unused `_membership_uri` (107–110) and import `emit_discusses_membership`, `membership_uri_for` from `.io`. Grep `_membership_uri` across the repo first; if any other module imports it, re-point those imports at `io.membership_uri_for` instead of leaving a shim (no compatibility layer — per user rules).

- [ ] **Step 6: Run the full materialize + belief suites to verify no behavior change**

Run: `cd science && uv run --frozen pytest tests/test_membership_materialize.py tests/test_bundle_belief_membership.py tests/test_membership_chokepoint.py -v`
Expected: PASS — all pre-existing frontmatter/belief tests green, output unchanged.

- [ ] **Step 7: Commit**

```bash
git add science/src/science_tool/graph/io.py science/src/science_tool/graph/materialize.py science/tests/test_membership_chokepoint.py
git commit -m "refactor(membership): extract single cito:discusses emission chokepoint"
```

---

## Task 2: Route the authored-relations store through the chokepoint

The relations.yaml surface begins emitting a `role: core` `BundleMembership` node for `cito:discusses` edges. Additive and benign (core = existing default), but it changes graph output.

**Files:**
- Modify: `science/src/science_tool/graph/materialize.py:1200–1208` (`_add_authored_relation`)
- Test: `science/tests/test_membership_materialize.py` (extend)

**Interfaces:**
- Consumes: `io.emit_discusses_membership` (Task 1), `CITO_NS` (already imported).
- Produces: a `cito:discusses` relation whose object resolves to a **live bundle entity** routes through the chokepoint; all other predicates and non-live-bundle objects keep the generic `graph.add` path.

- [ ] **Step 1: Write the failing test**

Add to `science/tests/test_membership_materialize.py` — mirror the existing relations-store fixture in that file (a tiny project with a `relations.yaml`), adding a `cito:discusses` relation `proposition:0011 → hypothesis:0001`:

```python
def test_relations_store_discusses_emits_core_membership_node(tmp_project_with_relation):
    knowledge = tmp_project_with_relation(  # fixture builds + returns the knowledge graph
        subject="proposition:0011-bar",
        predicate="cito:discusses",
        object="hypothesis:0001-foo",
    )
    from science_tool.graph.io import SCI_NS, membership_uri_for, entity_uri_for_ref, CITO_NS, Literal_  # adjust to file's imports
    node = membership_uri_for("proposition:0011-bar", "hypothesis:0001-foo")
    assert (entity_uri_for_ref("proposition:0011-bar"), CITO_NS.discusses,
            entity_uri_for_ref("hypothesis:0001-foo")) in knowledge
    assert (node, SCI_NS.membershipRole, Literal("core")) in knowledge
```

If the file has no reusable relations-store fixture, build the graph through the same `_build_dataset_from_sources` / `materialize` entry the existing materialize tests use; copy the smallest existing example in the file and add one relation. Do not invent a new harness.

- [ ] **Step 2: Run it to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_membership_materialize.py -k relations_store_discusses -v`
Expected: FAIL — no `BundleMembership` node (generic `graph.add` path took the edge).

- [ ] **Step 3: Special-case `cito:discusses` in `_add_authored_relation`**

Replace the unconditional emit at `materialize.py:1208`:

```python
    if predicate_uri == CITO_NS.discusses and isinstance(object_entity, Entity):
        emit_discusses_membership(
            graph,
            prop_uri=subject_uri,
            frame_uri=object_uri,
            prop_cid=subject_entity.canonical_id,
            frame_cid=object_entity.canonical_id,
            role=relation.role or MembershipRole.CORE,
        )
    else:
        graph.add((subject_uri, predicate_uri, object_uri))
```

`relation.role` does not exist until Task 4; until then this reads `getattr(relation, "role", None) or MembershipRole.CORE` — **but** prefer to land Task 4's field first if executing in order; if Tasks are executed strictly in number, use `MembershipRole.CORE` here and add `relation.role` in Task 4. Import `MembershipRole` and `emit_discusses_membership` at module top. The `isinstance(object_entity, Entity)` guard keeps external/archived discusses targets on the generic path (membership applies only to live bundle entities); the chokepoint then loud-fails if that live entity is not a bundle.

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd science && uv run --frozen pytest tests/test_membership_materialize.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/graph/materialize.py science/tests/test_membership_materialize.py
git commit -m "feat(membership): emit role node for relations-store cito:discusses edges"
```

---

## Task 3: Route the store-CLI bridge through the chokepoint

`--bridge-between` edges begin carrying an explicit `role: core` node; the `sci:bridgeBetween` provenance triple is unchanged.

**Files:**
- Modify: `science/src/science_tool/graph/store/mutations.py:114` (signature), `:225–229` (emit)
- Test: `science/tests/test_membership_bridge.py` (create)

**Interfaces:**
- Consumes: `io.emit_discusses_membership`.
- Produces: `mutations`'s proposition-creation function gains `bridge_role: MembershipRole = MembershipRole.CORE`; each bridge ref emits triple + node via the chokepoint **and** keeps `provenance.add((prop_uri, SCI_NS.bridgeBetween, bridge_uri))`.

- [ ] **Step 1: Write the failing test**

Create `science/tests/test_membership_bridge.py` — mirror the smallest existing `mutations` test that exercises a proposition mutation in the suite (find it with `grep -rln "bridge_between_refs\|def test_" science/tests | head`). Assert that creating a proposition with `bridge_between_refs=["hypothesis:0001-foo"]` produces both a `cito:discusses` triple **and** a `BundleMembership` node with `membershipRole "core"`, and still produces the `sci:bridgeBetween` provenance triple.

- [ ] **Step 2: Run it to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_membership_bridge.py -v`
Expected: FAIL — no `BundleMembership` node.

- [ ] **Step 3: Repoint the bridge emit**

In `mutations.py`, add `bridge_role: MembershipRole = MembershipRole.CORE` to the signature (near `bridge_between_refs`, line 114), and replace `225–229`:

```python
    if bridge_between_refs is not None:
        for bridge_ref in bridge_between_refs:
            bridge_uri = _resolve_term(bridge_ref)
            emit_discusses_membership(
                knowledge,
                prop_uri=prop_uri,
                frame_uri=bridge_uri,
                prop_cid=_canonical_for(prop_uri),
                frame_cid=_canonical_for(bridge_uri),
                role=bridge_role,
            )
            provenance.add((prop_uri, SCI_NS.bridgeBetween, bridge_uri))
```

`emit_discusses_membership` needs the **canonical id strings** (`proposition:…`, `hypothesis:…`) for `membership_uri_for`. If `mutations.py` works in URIs and has no ready canonicalizer, derive the canonical id from the bridge ref string directly (it is already a `kind:slug` ref) and from the proposition's source ref; reuse whatever canonical-id the function already holds for `prop_uri` rather than reversing the URI. Inspect the function head (mutations.py:90–130) for the proposition's canonical ref and pass it through. Import `emit_discusses_membership` and `MembershipRole`.

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd science && uv run --frozen pytest tests/test_membership_bridge.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/graph/store/mutations.py science/tests/test_membership_bridge.py
git commit -m "feat(membership): emit role node for store-CLI bridge cito:discusses edges"
```

---

## Task 4: Add `role` to `SourceRelation` and honor it from relations.yaml

**Files:**
- Modify: `science/src/science_tool/graph/sources.py:88–95` (`SourceRelation`)
- Modify: `science/src/science_tool/graph/materialize.py` (`_add_authored_relation`, use `relation.role`)
- Test: `science/tests/test_membership_materialize.py` (extend)

**Interfaces:**
- Produces: `SourceRelation.role: MembershipRole | None = None`. `_add_authored_relation` passes `role=relation.role or MembershipRole.CORE` to the chokepoint (replacing the Task-2 placeholder if one was used).

- [ ] **Step 1: Write the failing test**

Add to `test_membership_materialize.py`: a relations.yaml `cito:discusses` edge with `role: background` produces a node with `membershipRole "background"`, and (using the bundle-belief reader from `bundle_belief.py`) is **excluded** from `core_members` of that frame.

```python
def test_relations_store_role_background_excluded_from_core(tmp_project_with_relation):
    knowledge = tmp_project_with_relation(
        subject="proposition:0011-bar", predicate="cito:discusses",
        object="hypothesis:0001-foo", role="background",
    )
    from science_tool.graph.bundle_belief import core_members, membership_role
    from science_tool.graph.io import entity_uri_for_ref
    from science_model.reasoning import MembershipRole
    prop = entity_uri_for_ref("proposition:0011-bar")
    frame = entity_uri_for_ref("hypothesis:0001-foo")
    assert membership_role(knowledge, prop, frame) == MembershipRole.BACKGROUND
    assert prop not in core_members(knowledge, frame)
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_membership_materialize.py -k role_background -v`
Expected: FAIL — `SourceRelation` rejects unknown field `role`, or role is ignored (treated core).

- [ ] **Step 3: Add the field and thread it**

In `sources.py`, import `MembershipRole` and add to `SourceRelation`:

```python
    role: MembershipRole | None = None
```

In `_add_authored_relation`, ensure the chokepoint call passes `role=relation.role or MembershipRole.CORE` (finalize the Task-2 placeholder).

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd science && uv run --frozen pytest tests/test_membership_materialize.py -v`
Expected: PASS.

- [ ] **Step 5: Add cross-surface validation**

In the validation layer (extend `validate/checks/propositions.py` or the relations check that already iterates `SourceRelation`s), add `check`s, with loud-fail messages, for design §4:

1. `relation.role is not None and relation.predicate != "cito:discusses"` → error: role only valid on `cito:discusses`.
2. `relation.role` set and object does not resolve to a bundle → error.
3. The same `(subject, frame)` pair labeled with conflicting roles across frontmatter and relations.yaml → error (one role per pair).

(Enum membership is already enforced by the Pydantic `MembershipRole` type at load; rule 3 of design §4 is the value check and needs no separate validate code.)

- [ ] **Step 6: Write + run the validation tests**

Add to `science/tests/test_membership_validation.py` one test per rule above (a `role` on a `cito:supports` relation fails; a `role` to a `topic:` object fails; a frontmatter-`background` + relations-`core` conflict fails). Run:

`cd science && uv run --frozen pytest tests/test_membership_validation.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add science/src/science_tool/graph/sources.py science/src/science_tool/graph/materialize.py science/src/science_tool/validate/checks/propositions.py science/tests/test_membership_materialize.py science/tests/test_membership_validation.py
git commit -m "feat(membership): authored role on relations-store cito:discusses + validation"
```

---

## Task 5: Add `--role` to the `--bridge-between` CLI command

**Files:**
- Modify: `science/src/science_tool/cli.py:2367–2421` (the bridge command)
- Test: extend `science/tests/test_membership_bridge.py`

**Interfaces:**
- Produces: `--role <core|rival|background>` (default `core`) on the proposition-creation command; threaded to `mutations`'s `bridge_role`.

- [ ] **Step 1: Write the failing test**

Add a CliRunner test (mirror an existing `cli.py` proposition-creation test) invoking the command with `--bridge-between hypothesis:0001-foo --role background`, asserting the resulting graph has `membershipRole "background"` for that pair.

- [ ] **Step 2: Run it to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_membership_bridge.py -k cli_role -v`
Expected: FAIL — no such option `--role`.

- [ ] **Step 3: Add the option**

After `cli.py:2367`:

```python
@click.option(
    "--bridge-role",
    "bridge_role",
    type=click.Choice(["core", "rival", "background"]),
    default="core",
    show_default=True,
    help="Membership role for --bridge-between frames",
)
```

Add `bridge_role: str` to the command params (near line 2392) and pass `bridge_role=MembershipRole(bridge_role)` into the `mutations` call (near line 2421). Import `MembershipRole`.

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd science && uv run --frozen pytest tests/test_membership_bridge.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/cli.py science/tests/test_membership_bridge.py
git commit -m "feat(membership): --bridge-role on the bridge CLI command"
```

---

## Task 6: Corpus audit, graph rebuild, and docs reconciliation

**Files:**
- Modify: `skills/research/proposition-schema.md` ("Bundle Membership and Roles" section)
- (No new code; this is the safety + docs task.)

- [ ] **Step 1: Audit all projects for non-bundle relations-store discusses edges**

Run (from each project root, or across the project corpus the team tracks):

```bash
grep -rl "predicate: cito:discusses" */knowledge/sources/local/relations.yaml 2>/dev/null
```

For each hit, confirm the `object:` resolves to a `hypothesis:` or `mechanism:`. Any `topic:`/other target is now a hard error under the chokepoint (design §3.4) — reconcile it (retarget to a bundle, or move to `related`/a non-membership predicate). `mm30` already has none after the pilot cleanup (`mm30@1cfa2592`).

- [ ] **Step 2: Rebuild graphs for any project that authored relations-store discusses edges**

For each affected project: `science graph build` (regenerates `knowledge/graph.trig` + `composite.trig` with the new `role: core` nodes). Confirm `science validate` passes and bundle belief is unchanged (all new nodes are `core`).

- [ ] **Step 3: Reconcile the schema-skill caveat**

In `skills/research/proposition-schema.md`, update the "Bundle Membership and Roles" section: the caveat currently says a `cito:discusses` edge authored in `relations.yaml` is "always treated as `core`." Replace it with: relations.yaml now accepts an optional `role:` on a `cito:discusses` relation (absent = `core`), and the store-CLI bridge accepts `--bridge-role`. Keep the note that forward `sci:hasProposition` is authoritatively `core`.

- [ ] **Step 4: Verify the one-emitter invariant**

Run: `cd science && grep -rn "CITO_NS.discusses)" science/src | grep "add("`
Expected: a single hit, inside `io.emit_discusses_membership`. Any other hit is a regression.

- [ ] **Step 5: Full validation + commit**

Run: `cd science && uv run --frozen pytest -q && uv run --frozen science validate`
Expected: green (modulo the pre-existing, unrelated `test_templates.py::…[prose-source]` failure).

```bash
git add skills/research/proposition-schema.md
git commit -m "docs(membership): relations-store + bridge now carry roles; reconcile schema skill"
```

---

## Self-Review

**Spec coverage (design doc → tasks):**
- §1 three-emitter table → Tasks 1 (frontmatter), 2 (relations), 3 (bridge). ✅
- §2 single chokepoint → Task 1. ✅
- §3.2 `SourceRelation.role` → Task 4. ✅
- §3.3 `--bridge-role` → Tasks 3 (param) + 5 (CLI). ✅
- §3.4 non-bundle loud-fail uniform → Task 1 (chokepoint) + Task 6 audit. ✅
- §4 validation rules → Task 4 Step 5–6. ✅
- §6 migration/rebuild + docs → Task 6. ✅
- §7 "explicit after compile for every surface" → achieved by Tasks 1–3. ✅

**Type consistency:** `emit_discusses_membership(knowledge, *, prop_uri, frame_uri, prop_cid, frame_cid, role)` and `membership_uri_for(prop_cid, frame_cid)` are referenced identically in Tasks 1, 2, 3. `SourceRelation.role: MembershipRole | None` (Task 4) and `bridge_role: MembershipRole` (Tasks 3, 5) both feed the chokepoint's `role: MembershipRole` param.

**Known cross-task dependency:** Task 2 Step 3 uses `relation.role`, which is not added until Task 4. The step calls this out explicitly: when executing strictly in order, emit `role=MembershipRole.CORE` in Task 2 and finalize to `relation.role or MembershipRole.CORE` in Task 4 Step 3. A task reviewer should accept the Task-2 placeholder only with that Task-4 follow-up noted.

**Placeholder scan:** the two "mirror the existing test/fixture in this file" instructions (Tasks 2, 3, 5) are deliberate — the integration fixtures (materialize harness, mutations harness, CliRunner setup) already exist in the named test files and must not be re-invented. Each such step still specifies exact assertions. No `TBD`/`handle edge cases`/bare-prose code steps remain.

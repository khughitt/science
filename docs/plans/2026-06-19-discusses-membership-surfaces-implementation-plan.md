# Unifying Bundle-Membership Emission on `cito:discusses` — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Route every **bundle-membership** `cito:discusses` emission (the subtype whose object is a hypothesis/mechanism) through one chokepoint that always writes the `BundleMembership` role node, and let the authored-relations store and the store-CLI bridge author non-`core` roles — so a membership role is honored regardless of which surface declares the edge. General (non-bundle) `cito:discusses` edges are untouched.

**Architecture:** Extract a single `emit_discusses_membership(...)` into `graph/io.py`. The frontmatter path (already role-aware) is refactored to call it; the authored-relations store (`_add_authored_relation`) and the store-CLI bridge (`bridge_between_refs`) are re-pointed at it **only when the object resolves to a bundle**, defaulting to `core`. Then `SourceRelation` gains an optional `role` and the bridge command gains `--bridge-role`. See the design doc — especially §0.1 (policy) and §2.1 (invariant).

**Tech Stack:** Python ≥3.11, Pydantic v2, rdflib, pytest, `uv`. Two packages: model (`science/model`, `science_model`) and tool (`science/src`, `science_tool`).

**Spec:** [`2026-06-19-discusses-membership-surfaces-design.md`](./2026-06-19-discusses-membership-surfaces-design.md). Parent feature: [`2026-06-19-contextual-structural-roles-design.md`](./2026-06-19-contextual-structural-roles-design.md).

## Global Constraints

- **Working directory:** all commands run from `~/d/science`. Tests run from the nested `science/` and `science/model/` package dirs.
- **Test runner:** `uv run --frozen pytest <path> -v`. Validation: `uv run --frozen science validate`.
- **Authority boundary (design §0):** touch **only** the emission/authoring of the bundle-membership subtype of `cito:discusses`. Add **no** causal-edge vocabulary; do **not** make the membership node truth-apt; do **not** change the closed role vocabulary `core | rival | background`.
- **`cito:discusses` stays general (design §0.1):** bundle membership = the subtype whose **subject is a proposition** *and* whose **object resolves to a live `hypothesis`/`mechanism`**. Only that subtype gets a role node + the chokepoint (`bundle_members` admits only `sci:Proposition` subjects — `bundle_belief.py:47` — so a non-proposition membership node would be dead data). Everything else — `paper → question`, **`paper → hypothesis`**, `proposition → topic`, → external term, discusses to an *archived* bundle — keeps the generic `graph.add` path **unchanged**. The passing test `science/tests/test_graph_materialize.py:896` (`paper → discusses → question`) MUST stay green.
- **Annotate, never replace:** the plain `(prop, cito:discusses, frame)` triple MUST always be emitted exactly as today.
- **Migration default = `core`:** unlabeled membership (bare string, missing `role`, forward `sci:hasProposition`) means `core`. The conjunction MUST be byte-for-byte unchanged on the existing corpus until a curator labels a member.
- **Membership invariant (design §2.1):** every `(proposition, cito:discusses, bundle)` triple has a `BundleMembership` node minted only by `emit_discusses_membership`, and **no** membership node exists for a non-proposition subject. Verified by a graph-coverage assertion (Task 6), **not** a static grep.
- **Style:** explicit over defensive; fail loudly, no silent fallbacks. Follow existing module idioms.

---

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `science/src/science_tool/graph/io.py` | Graph vocabulary + the membership chokepoint | Add `membership_uri_for()` + `emit_discusses_membership()` |
| `science/src/science_tool/graph/materialize.py` | Frontmatter → RDF; authored relations | Repoint frontmatter (642–648) at chokepoint; route bundle-object discusses in `_add_authored_relation` (1208); delete duplicated inline emit + `_membership_uri` |
| `science/src/science_tool/graph/sources.py` | Authored-relation model | Add `role: MembershipRole | None = None` to `SourceRelation` |
| `science/src/science_tool/graph/store/mutations.py` | Store CLI mutations | Repoint `bridge_between_refs` emit (225–229) at chokepoint; add `bridge_role` param |
| `science/src/science_tool/cli.py` | CLI surface | Add `--bridge-role` to the `--bridge-between` command |
| `science/src/science_tool/validate/checks/propositions.py` (or relations check) | QA | Validate `SourceRelation.role` (predicate, target, cross-surface conflict) |
| `science/tests/test_membership_chokepoint.py` | Chokepoint unit tests | Create |
| `science/tests/test_membership_materialize.py` | Relations-store membership tests | Extend (exists) |
| `science/tests/test_membership_bridge.py` | Bridge-role tests | Create |
| `science/tests/test_membership_validation.py` | Cross-surface validation tests | Extend (exists) |

---

## Task 1: Extract the membership chokepoint; repoint the frontmatter path

Pure refactor — externally behavior-preserving. Frontmatter graph output must be byte-for-byte identical; the only change is that the triple + node are emitted by one shared function.

**Files:**
- Modify: `science/src/science_tool/graph/io.py`
- Modify: `science/src/science_tool/graph/materialize.py:632–648` (frontmatter emit) and `:107–110` (`_membership_uri`)
- Test: `science/tests/test_membership_chokepoint.py` (create)

**Interfaces:**
- Produces (in `science_tool.graph.io`):
  - `membership_uri_for(prop_cid: str, frame_cid: str) -> URIRef` — moved verbatim from `materialize._membership_uri`.
  - `emit_discusses_membership(knowledge, *, prop_uri: URIRef, frame_uri: URIRef, prop_cid: str, frame_cid: str, role: MembershipRole = MembershipRole.CORE) -> None` — precondition-guards non-bundle `frame_cid`, emits the plain triple, emits the `BundleMembership` node.
- Consumes: `materialize.py` imports both from `io`; `_membership_uri` is deleted.

- [ ] **Step 1: Write the failing chokepoint unit test**

Create `science/tests/test_membership_chokepoint.py`:

```python
from __future__ import annotations

import pytest
from rdflib import Graph, Literal, RDF

from science_model.reasoning import MembershipRole
from science_tool.graph.io import (
    CITO_NS,
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
    assert (entity_uri_for_ref(prop_cid), CITO_NS.discusses, entity_uri_for_ref(frame_cid)) in g


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

In `science/src/science_tool/graph/io.py`, ensure `RDF` and `Literal` are imported from `rdflib` and `MembershipRole` from `science_model.reasoning` (add imports if absent — `materialize.py:21` already imports `MembershipRole` from the graph layer, so the dependency is fine), then add:

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
    """The one place a bundle-membership cito:discusses edge is emitted.

    Always emits the plain (prop, cito:discusses, frame) triple, plus a
    non-truth-apt BundleMembership node carrying the role. Precondition guard:
    the frame must be a bundle (hypothesis/mechanism) — callers route only
    membership edges here; non-bundle discusses keeps the generic path (design
    §0.1, §3.4).
    """
    frame_kind = frame_cid.split(":", 1)[0]
    if frame_kind not in ("hypothesis", "mechanism"):
        raise ValueError(
            f"{prop_cid} discusses {frame_cid!r}, which is a {frame_kind!r}, not a "
            "bundle (hypothesis/mechanism); membership roles are only valid on bundle "
            "frames (spec §5)."
        )
    knowledge.add((prop_uri, CITO_NS.discusses, frame_uri))
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

In `materialize.py`, replace the inline block at `632–648` (keep the `frame_uri` resolution; the kind-check + 6 `knowledge.add` lines collapse into one call):

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

Delete `_membership_uri` (107–110) and import `emit_discusses_membership`, `membership_uri_for` from `.io`. Grep `_membership_uri` across the repo first; if any other module imports it, re-point those at `io.membership_uri_for` (no compatibility shim — per user rules).

- [ ] **Step 6: Run the full materialize + belief suites to verify no behavior change**

Run: `cd science && uv run --frozen pytest tests/test_membership_materialize.py tests/test_bundle_belief_membership.py tests/test_graph_materialize.py tests/test_membership_chokepoint.py -v`
Expected: PASS — all pre-existing frontmatter/belief tests green, including `paper → discusses → question` in `test_graph_materialize.py`.

- [ ] **Step 7: Commit**

```bash
git add science/src/science_tool/graph/io.py science/src/science_tool/graph/materialize.py science/tests/test_membership_chokepoint.py
git commit -m "refactor(membership): extract single bundle-membership emission chokepoint"
```

---

## Task 2: Route proposition→bundle relations-store discusses through the chokepoint

A `cito:discusses` edge in `relations.yaml` from a **proposition** to a **live bundle** begins emitting a `role: core` `BundleMembership` node. Every other discusses edge (`paper → question`, `paper → hypothesis`, discusses to an archived bundle) stays on the generic path, unchanged.

**Files:**
- Modify: `science/src/science_tool/graph/materialize.py:1200–1208` (`_add_authored_relation`)
- Test: `science/tests/test_membership_materialize.py` (extend)

**Interfaces:**
- Consumes: `io.emit_discusses_membership`, `CITO_NS`, `Entity`.
- Produces: routing in `_add_authored_relation` — `predicate == cito:discusses` **and** subject is a proposition **and** object is a live `Entity` bundle → chokepoint; everything else → generic `graph.add`.

- [ ] **Step 1: Write the failing tests (membership routes; non-bundle does not)**

Add to `science/tests/test_membership_materialize.py`, mirroring the existing relations-store fixture pattern in `test_graph_materialize.py` (`local_sources / "relations.yaml"` → `materialize_graph(project)` → parse the `graph/knowledge` graph):

```python
def test_relations_store_prop_to_bundle_emits_core_node(make_project_with_relation):
    knowledge = make_project_with_relation(
        subject="proposition:0011-bar", predicate="cito:discusses", object="hypothesis:0001-foo",
    )
    from science_tool.graph.io import SCI_NS, membership_uri_for
    from rdflib import Literal
    node = membership_uri_for("proposition:0011-bar", "hypothesis:0001-foo")
    assert (node, SCI_NS.membershipRole, Literal("core")) in knowledge


def test_relations_store_paper_to_question_has_no_membership_node(make_project_with_relation):
    knowledge = make_project_with_relation(
        subject="paper:legatiuk2021", predicate="cito:discusses", object="question:q01-demo",
    )
    from science_tool.graph.io import SCI_NS
    # The plain structural link still materializes; no BundleMembership node exists.
    assert not list(knowledge.triples((None, SCI_NS.membershipFrame, None)))


def test_relations_store_paper_to_bundle_has_no_membership_node(make_project_with_relation):
    # Subject is NOT a proposition: object is a bundle but this is not a membership.
    knowledge = make_project_with_relation(
        subject="paper:legatiuk2021", predicate="cito:discusses", object="hypothesis:0001-foo",
    )
    from science_tool.graph.io import CITO_NS, SCI_NS, entity_uri_for_ref
    # The plain structural link still materializes...
    assert (entity_uri_for_ref("paper:legatiuk2021"), CITO_NS.discusses,
            entity_uri_for_ref("hypothesis:0001-foo")) in knowledge
    # ...but no membership node is minted for a non-proposition subject.
    assert not list(knowledge.triples((None, SCI_NS.membershipFrame, None)))
```

`make_project_with_relation` builds a minimal project (entities for the subject/object + a `relations.yaml` with the one relation) and returns the parsed `graph/knowledge` graph — lift it from the existing `test_graph_materialize.py:884–913` fixture rather than inventing a harness.

- [ ] **Step 2: Run to verify the first fails, the second already passes**

Run: `cd science && uv run --frozen pytest tests/test_membership_materialize.py -k "prop_to_bundle or paper_to" -v`
Expected: `prop_to_bundle` FAILS (no node yet); `paper_to_question` and `paper_to_bundle` PASS (current generic path already correct — these are the regression guards for the proposition-subject rule).

- [ ] **Step 3: Add bundle-object routing in `_add_authored_relation`**

Replace the unconditional emit at `materialize.py:1208`. Membership requires a **proposition** subject and a **live** bundle object — the object must be an `Entity` (not an `_ArchivedEndpoint` or external URI), matching design §3.2:

```python
    subject_is_proposition = subject_entity.canonical_id.split(":", 1)[0] == "proposition"
    object_is_live_bundle = (
        isinstance(object_entity, Entity)
        and object_entity.canonical_id.split(":", 1)[0] in ("hypothesis", "mechanism")
    )
    is_membership = (
        predicate_uri == CITO_NS.discusses and subject_is_proposition and object_is_live_bundle
    )
    if is_membership:
        emit_discusses_membership(
            graph,
            prop_uri=subject_uri,
            frame_uri=object_uri,
            prop_cid=subject_entity.canonical_id,
            frame_cid=object_entity.canonical_id,
            role=MembershipRole.CORE,  # finalized to `relation.role or CORE` in Task 4
        )
    elif predicate_uri == CITO_NS.discusses and getattr(relation, "role", None) is not None:
        raise ValueError(
            f"relation {relation.subject} cito:discusses {relation.object}: role "
            f"{relation.role!r} set, but this is not a proposition→live-bundle membership "
            "(subject must be a proposition and object a live hypothesis/mechanism); "
            "membership roles are only valid on membership edges (design §4)."
        )
    else:
        graph.add((subject_uri, predicate_uri, object_uri))
```

`Entity` is already imported in `materialize.py` (the `object_entity: Entity | _ArchivedEndpoint` annotation). `getattr(relation, "role", None)` is forward-compatible: `None` until Task 4 adds the field, so the loud-fail branch is inert until then. Import `emit_discusses_membership` and `MembershipRole` at module top.

- [ ] **Step 4: Run the tests to verify both pass**

Run: `cd science && uv run --frozen pytest tests/test_membership_materialize.py tests/test_graph_materialize.py -v`
Expected: PASS — `prop_to_bundle` now emits a node; `paper_to_question` still has none.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/graph/materialize.py science/tests/test_membership_materialize.py
git commit -m "feat(membership): emit role node for bundle-object relations-store discusses"
```

---

## Task 3: Route the store-CLI bridge through the chokepoint

`--bridge-between` edges (always hypothesis refs, hence bundle memberships) begin carrying an explicit `role: core` node; the `sci:bridgeBetween` provenance triple is unchanged.

**Files:**
- Modify: `science/src/science_tool/graph/store/mutations.py:114` (signature), `:225–229` (emit)
- Test: `science/tests/test_membership_bridge.py` (create)

**Interfaces:**
- Consumes: `io.emit_discusses_membership`.
- Produces: the proposition-creation function gains `bridge_role: MembershipRole = MembershipRole.CORE`; each bridge ref emits triple + node via the chokepoint **and** keeps `provenance.add((prop_uri, SCI_NS.bridgeBetween, bridge_uri))`.

- [ ] **Step 1: Write the failing test**

Create `science/tests/test_membership_bridge.py`, mirroring the smallest existing `mutations` test that creates a proposition (find it: `grep -rln "bridge_between_refs\|def add_proposition\|def test_" science/tests | head`). Assert that creating a proposition with `bridge_between_refs=["hypothesis:0001-foo"]`:
- adds `(prop_uri, cito:discusses, hypothesis_uri)`,
- adds a `BundleMembership` node with `membershipRole "core"`,
- still adds `(prop_uri, sci:bridgeBetween, hypothesis_uri)` in the provenance graph.

- [ ] **Step 2: Run it to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_membership_bridge.py -v`
Expected: FAIL — no `BundleMembership` node.

- [ ] **Step 3: Repoint the bridge emit**

In `mutations.py`, add `bridge_role: MembershipRole = MembershipRole.CORE` to the signature near `bridge_between_refs` (line 114). The proposition's canonical id is `proposition:{token}` (built at `mutations.py:134–140`); the bridge ref is already a `kind:slug` ref. Replace `225–229`:

```python
    if bridge_between_refs is not None:
        prop_cid = f"proposition:{token}"
        for bridge_ref in bridge_between_refs:
            bridge_uri = _resolve_term(bridge_ref)
            emit_discusses_membership(
                knowledge,
                prop_uri=prop_uri,
                frame_uri=bridge_uri,
                prop_cid=prop_cid,
                frame_cid=bridge_ref,
                role=bridge_role,
            )
            provenance.add((prop_uri, SCI_NS.bridgeBetween, bridge_uri))
```

`frame_cid=bridge_ref` carries the authored `hypothesis:slug` ref; the chokepoint's bundle guard rejects a non-bundle bridge ref (a typo'd `--bridge-between topic:…`) with a loud error — desired. Import `emit_discusses_membership` and `MembershipRole`.

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd science && uv run --frozen pytest tests/test_membership_bridge.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/graph/store/mutations.py science/tests/test_membership_bridge.py
git commit -m "feat(membership): emit role node for store-CLI bridge discusses edges"
```

---

## Task 4: Add `role` to `SourceRelation` and honor it from relations.yaml

**Files:**
- Modify: `science/src/science_tool/graph/sources.py:88–95` (`SourceRelation`)
- Modify: `science/src/science_tool/graph/materialize.py` (`_add_authored_relation`, finalize `relation.role`)
- Test: `science/tests/test_membership_materialize.py`, `science/tests/test_membership_validation.py`

**Interfaces:**
- Produces: `SourceRelation.role: MembershipRole | None = None`. `_add_authored_relation` passes `role=relation.role or MembershipRole.CORE` to the chokepoint (finalizing the Task-2 `CORE` placeholder).

- [ ] **Step 1: Write the failing test**

Add to `test_membership_materialize.py`: a relations.yaml `cito:discusses` to a bundle with `role: background` produces a node with `membershipRole "background"`, and is excluded from `core_members`:

```python
def test_relations_store_role_background_excluded_from_core(make_project_with_relation):
    knowledge = make_project_with_relation(
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

(Extend `make_project_with_relation` to thread an optional `role` into the emitted `relations.yaml` entry.)

- [ ] **Step 2: Run it to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_membership_materialize.py -k role_background -v`
Expected: FAIL — `SourceRelation` rejects unknown field `role`, or role is ignored (treated core).

- [ ] **Step 3: Add the field and finalize threading**

In `sources.py`, import `MembershipRole` and add to `SourceRelation`:

```python
    role: MembershipRole | None = None
```

In `_add_authored_relation` (Task 2 Step 3), change the chokepoint call's `role=MembershipRole.CORE` to `role=relation.role or MembershipRole.CORE`. The role-on-non-bundle loud-fail branch (already added in Task 2) now becomes reachable.

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd science && uv run --frozen pytest tests/test_membership_materialize.py -v`
Expected: PASS.

- [ ] **Step 5: Add cross-surface validation (design §4)**

Extend the validation layer (`validate/checks/propositions.py` or the relations check that iterates `SourceRelation`s) with loud-fail checks:

1. `relation.role is not None and relation.predicate != "cito:discusses"` → error.
2. `relation.role` set and the `(subject, object)` is not a proposition→live-bundle membership pair → error.
3. The same `(subject, frame)` pair labeled with conflicting roles across frontmatter and relations.yaml → error.

- [ ] **Step 6: Write + run the validation tests**

Add to `science/tests/test_membership_validation.py` one test per rule (a `role` on a `cito:supports` relation fails; a `role` to a `topic:` object fails; a `role` on a `paper → hypothesis` edge — non-proposition subject — fails; a frontmatter-`background` + relations-`core` conflict for one pair fails). Run:

`cd science && uv run --frozen pytest tests/test_membership_validation.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add science/src/science_tool/graph/sources.py science/src/science_tool/graph/materialize.py science/src/science_tool/validate/checks/propositions.py science/tests/test_membership_materialize.py science/tests/test_membership_validation.py
git commit -m "feat(membership): authored role on relations-store discusses + validation"
```

---

## Task 5: Add `--bridge-role` to the `--bridge-between` CLI command

**Files:**
- Modify: `science/src/science_tool/cli.py:2367–2421` (the bridge command)
- Test: extend `science/tests/test_membership_bridge.py`

**Interfaces:**
- Produces: `--bridge-role <core|rival|background>` (default `core`) on the proposition-creation command; threaded to `mutations`'s `bridge_role`. Named `--bridge-role` (not `--role`) to scope it to bridge frames and avoid collision with any other `--role` option on the command (design §3.3).

- [ ] **Step 1: Write the failing test**

Add a CliRunner test (mirror an existing `cli.py` proposition-creation test) invoking the command with `--bridge-between hypothesis:0001-foo --bridge-role background`, asserting the resulting graph has `membershipRole "background"` for that pair.

- [ ] **Step 2: Run it to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_membership_bridge.py -k bridge_role -v`
Expected: FAIL — no such option `--bridge-role`.

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

## Task 6: Coverage-invariant check, graph rebuild, and docs reconciliation

**Files:**
- Create/extend: a coverage test asserting the membership invariant
- Modify: `skills/research/proposition-schema.md` ("Bundle Membership and Roles" section)

- [ ] **Step 1: Write the membership-coverage invariant test**

Add to `science/tests/test_membership_materialize.py` a test over a built graph asserting design §2.1 in **both directions**: every proposition→bundle discusses edge has a membership node, and no membership node exists for a non-proposition subject. Build a project carrying one of each edge (extend the lifted fixture to accept a list of relations — `make_project_with_relations`).

```python
def test_membership_coverage_invariant(make_project_with_relations):
    knowledge = make_project_with_relations([
        ("proposition:0011-bar", "cito:discusses", "hypothesis:0001-foo"),  # membership
        ("paper:legatiuk2021", "cito:discusses", "hypothesis:0001-foo"),    # NOT membership
    ])
    from rdflib import RDF
    from science_tool.graph.io import CITO_NS, SCI_NS, membership_uri_for

    def _cid(uri):  # PROJECT_NS["kind/slug"] -> "kind:slug"  (match io._entity_uri's scheme)
        tail = str(uri).rsplit("/project/", 1)[-1]
        kind, _, slug = tail.partition("/")
        return f"{kind}:{slug}"

    # Forward: every proposition→bundle discusses edge has a membership node.
    for s, _, o in knowledge.triples((None, CITO_NS.discusses, None)):
        o_kind = str(o).rsplit("/project/", 1)[-1].split("/", 1)[0]
        if o_kind in ("hypothesis", "mechanism") and (s, RDF.type, SCI_NS.Proposition) in knowledge:
            node = membership_uri_for(_cid(s), _cid(o))
            assert (node, SCI_NS.membershipFrame, o) in knowledge, f"missing membership node for {s} -> {o}"

    # Reverse: no membership node points at a non-proposition subject.
    for node in knowledge.subjects(RDF.type, SCI_NS.BundleMembership):
        prop = knowledge.value(node, SCI_NS.membershipProposition)
        assert (prop, RDF.type, SCI_NS.Proposition) in knowledge, f"membership node {node} on non-proposition {prop}"
```

(Adjust `_cid`/URI parsing to the project's actual IRI scheme — see `io.entity_uri_for_ref` / `_entity_uri`. The intent is the two assertions, not this exact string surgery.)

Run: `cd science && uv run --frozen pytest tests/test_membership_materialize.py -k coverage_invariant -v`
Expected: PASS.

- [ ] **Step 2: Rebuild graphs for projects with prop→bundle relations-store discusses**

Identify affected projects: `grep -rl "predicate: cito:discusses" */knowledge/sources/local/relations.yaml 2>/dev/null`, then for each whose object is a `hypothesis:`/`mechanism:`, run `science graph build`. Confirm `science validate` passes and bundle belief is unchanged (new nodes are all `core`). `mm30` has no prop→bundle relations-store discusses after the pilot cleanup (`mm30@1cfa2592`), so no rebuild is needed there.

- [ ] **Step 3: Reconcile the schema-skill caveat**

In `skills/research/proposition-schema.md`, update "Bundle Membership and Roles": the caveat currently says a `cito:discusses` edge in `relations.yaml` is "always treated as `core`." Replace with: relations.yaml now accepts an optional `role:` on a `cito:discusses` relation whose object is a bundle (absent = `core`), and the store-CLI bridge accepts `--bridge-role`. Keep the note that forward `sci:hasProposition` is authoritatively `core`, and that a `cito:discusses` to a non-bundle (e.g. a question/topic) is a plain structural link with no role.

- [ ] **Step 4: Full validation + commit**

Run: `cd science && uv run --frozen pytest -q && uv run --frozen science validate`
Expected: green (modulo the pre-existing, unrelated `test_templates.py::…[prose-source]` failure).

```bash
git add skills/research/proposition-schema.md science/tests/test_membership_materialize.py
git commit -m "docs+test(membership): coverage invariant; relations-store + bridge roles in schema skill"
```

---

## Self-Review

**Spec coverage (design doc → tasks):**
- §0.1 policy (discusses general; membership = proposition→bundle subtype) → Tasks 2 (proposition-subject + live-bundle gate), 6 (two-direction coverage test). ✅
- §1 three-emitter table → Tasks 1 (frontmatter), 2 (relations), 3 (bridge). ✅
- §2 + §2.1 chokepoint + narrowed invariant → Task 1 + Task 6 coverage test. ✅
- §3.2 `SourceRelation.role` + bundle routing → Tasks 2, 4. ✅
- §3.3 `--bridge-role` → Tasks 3 (param) + 5 (CLI). ✅
- §3.4 chokepoint guard (not corpus-wide) → Task 1 guard + Task 2 non-bundle stays generic. ✅
- §4 validation → Task 4 Steps 5–6. ✅
- §6 migration/rebuild + docs → Task 6. ✅

**Review findings addressed (review pass 1):**
- *High #1 (invariant vs generic path):* invariant narrowed to bundle-membership edges; verified by the Task 6 coverage assertion, not a grep that can't see object/subject kind. ✅
- *High #2 (non-bundle loud-fail breaks `paper→question`):* Task 2 gates routing, so `test_graph_materialize.py:896` stays green; it is an explicit regression-guard test (Task 2 Step 1) and is run in Tasks 1/2/6. No corpus audit deferral. ✅
- *Medium (CLI naming):* standardized on `--bridge-role` in overview, §3.3, Task 5 interface/test/snippet. ✅
- *Medium (`_canonical_for`):* replaced with `prop_cid = f"proposition:{token}"` and `frame_cid = bridge_ref` (Task 3 Step 3), grounded in `mutations.py:134–140`. ✅

**Review findings addressed (review pass 2 — subject typing):**
- *High (membership is proposition→bundle, not any→bundle):* `bundle_members` admits only `sci:Proposition` subjects (`bundle_belief.py:47`), so a `paper → hypothesis` node would be dead data. Task 2 routing now also requires `subject_is_proposition`; a `paper_to_bundle_has_no_membership_node` regression test is added (Task 2 Step 1). ✅
- *Medium (archived objects):* routing requires `isinstance(object_entity, Entity)`, so archived hypotheses/mechanisms stay on the generic path — matching design §3.2. ✅
- *Medium (coverage test scope):* Task 6's test asserts proposition→bundle edges have a node **and** that no membership node points at a non-proposition subject. ✅

**Type consistency:** `emit_discusses_membership(knowledge, *, prop_uri, frame_uri, prop_cid, frame_cid, role)` and `membership_uri_for(prop_cid, frame_cid)` are referenced identically in Tasks 1, 2, 3, 6. `SourceRelation.role: MembershipRole | None` (Task 4) and `bridge_role: MembershipRole` (Tasks 3, 5) both feed the chokepoint's `role: MembershipRole`.

**Known cross-task dependency:** Task 2 emits `role=MembershipRole.CORE` and references `getattr(relation, "role", None)` (inert until the field exists); Task 4 adds `SourceRelation.role` and finalizes the call to `relation.role or MembershipRole.CORE`. A task reviewer should accept the Task-2 placeholder only with the Task-4 follow-up noted.

**Placeholder scan:** the "mirror the existing fixture" instructions (Tasks 2, 3, 5) point at named, existing fixtures (`test_graph_materialize.py:884–913`, the `mutations`/CliRunner tests) and each still specifies exact assertions. No `TBD`/bare-prose code steps remain.

# Hypothesis-Bundle Membership Roles — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an authored `membership_role` (`core` | `rival` | `background`) to the proposition→bundle `cito:discusses` relation, and gate the bundle-belief conjunction to `core` members only — without changing any other `cito:discusses` consumer.

**Architecture:** A new closed `MembershipRole` enum and a `DiscussesMembership` value object widen `PropositionEntity.discusses` from `list[str]` to `list[str | DiscussesMembership]` (bare string = `core` sugar). Materialization **always** emits the existing plain `(prop, cito:discusses, frame)` triple and, alongside it, a non-truth-apt `BundleMembership` plumbing node carrying the role. Only the bundle-belief conjunction reads the role (filtering members to `core`); coverage and every other raw-triple consumer stay role-blind. Validation hard-fails on malformed membership.

**Tech Stack:** Python ≥3.11, Pydantic v2, rdflib, pytest, `uv`. Two packages: the model package (`science/model`, importable as `science_model`) and the tool package (`science/src`, importable as `science_tool`).

## Global Constraints

- **Working directory:** all commands run from `~/d/science` (the repo root) unless a step says otherwise.
- **Test runner:** `uv run --frozen pytest <path> -v`. Validation: `uv run --frozen science validate`.
- **Authority boundary (spec §0):** this work touches **only** the `cito:discusses` membership relation. It does **not** add any causal-edge vocabulary, does **not** author mediator/confounder/collider (those are derived), and does **not** make the membership node truth-apt. The `BundleMembership` node carries no belief and takes no evidence.
- **Role vocabulary is closed:** exactly `core`, `rival`, `background`. No other values.
- **Annotate, never replace:** the plain `(prop, cito:discusses, frame)` triple MUST always be emitted exactly as today. The role rides alongside on a separate node.
- **Migration default = `core`:** a bare-string `discusses` entry and any `sci:hasProposition` member both mean `core`. The conjunction result must be byte-for-byte unchanged on the existing corpus until a curator marks a member `rival`/`background`.
- **Out of scope (deferred, spec §7):** the rival-contrast display channel; making coverage role-aware. Coverage stays role-blind in v1.
- **Style:** follow existing module idioms. Explicit over defensive; fail loudly, no silent fallbacks.

---

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `science/model/src/science_model/reasoning.py` | Canonical enums | Add `MembershipRole` enum + `MEMBERSHIP_ROLE_VALUES` |
| `science/model/src/science_model/propositions.py` | Proposition entity model | Add `DiscussesMembership`; widen `discusses`; add `iter_memberships()` |
| `science/src/science_tool/graph/io.py` | Graph vocabulary/namespaces | Add `BundleMembership`, `membershipProposition`, `membershipFrame`, `membershipRole` terms (constants) |
| `science/src/science_tool/graph/materialize.py` | Frontmatter → RDF | Emit plain triple + `BundleMembership` node; loud-fail on non-bundle frame |
| `science/src/science_tool/graph/bundle_belief.py` | Bundle belief roll-up | Add `membership_role()` + `core_members()`; conjunction reads `core` only |
| `science/src/science_tool/validate/checks/propositions.py` | Frontmatter QA | Add `check_discusses_membership` |
| `science/src/science_tool/dag/workbench.py` | Workbench authoring | Widen `WorkbenchRow.discusses`; re-validate on stamp |
| `science/model/tests/test_proposition_membership.py` | Model tests | Create |
| `science/tests/test_membership_materialize.py` | Materialize tests | Create |
| `science/tests/test_bundle_belief_membership.py` | Roll-up gating + e2e tests | Create |
| `science/tests/test_membership_validation.py` | Validation tests | Create |
| `science/tests/test_workbench_membership_roles.py` | Workbench authoring tests | Create |

---

## Task 1: Model layer — `MembershipRole`, `DiscussesMembership`, widened `discusses`

**Files:**
- Modify: `science/model/src/science_model/reasoning.py`
- Modify: `science/model/src/science_model/propositions.py`
- Test: `science/model/tests/test_proposition_membership.py`

**Interfaces:**
- Produces:
  - `MembershipRole(StrEnum)` with members `CORE = "core"`, `RIVAL = "rival"`, `BACKGROUND = "background"` (in `science_model.reasoning`).
  - `MEMBERSHIP_ROLE_VALUES: frozenset[str]` (in `science_model.reasoning`).
  - `DiscussesMembership(BaseModel)` — `extra="forbid"`, fields `frame: str` (non-empty), `role: MembershipRole = MembershipRole.CORE` (in `science_model.propositions`).
  - `PropositionEntity.discusses: list[str | DiscussesMembership]`.
  - `PropositionEntity.iter_memberships() -> Iterator[tuple[str, MembershipRole]]` yielding de-duped `(frame_ref, role)` pairs, with bare strings mapped to `(string, MembershipRole.CORE)`.
  - **Load invariant:** a `@model_validator` rejects a proposition that lists the same frame twice with conflicting roles (identical-role duplicates are allowed and collapsed by `iter_memberships()`). This makes conflict a hard error at *every* load site (materialize included), not just `science validate`.

- [ ] **Step 1: Write the failing model test**

Create `science/model/tests/test_proposition_membership.py`:

```python
from __future__ import annotations

import pytest
from pydantic import ValidationError

from science_model.propositions import DiscussesMembership, PropositionEntity
from science_model.reasoning import MembershipRole


def _prop(discusses):
    return PropositionEntity(
        id="proposition:p1",
        type="proposition",
        title="P1",
        status="active",
        ontology_terms=[],
        source_refs=[],
        related=[],
        discusses=discusses,
    )


def test_bare_string_is_core():
    p = _prop(["hypothesis:h1"])
    assert list(p.iter_memberships()) == [("hypothesis:h1", MembershipRole.CORE)]


def test_object_form_carries_role():
    p = _prop([{"frame": "hypothesis:h1", "role": "rival"}])
    assert list(p.iter_memberships()) == [("hypothesis:h1", MembershipRole.RIVAL)]


def test_object_role_defaults_to_core():
    p = _prop([{"frame": "hypothesis:h1"}])
    assert list(p.iter_memberships()) == [("hypothesis:h1", MembershipRole.CORE)]


def test_mixed_string_and_object():
    p = _prop(["hypothesis:h1", {"frame": "mechanism:m1", "role": "background"}])
    assert list(p.iter_memberships()) == [
        ("hypothesis:h1", MembershipRole.CORE),
        ("mechanism:m1", MembershipRole.BACKGROUND),
    ]


def test_unknown_role_rejected_at_model_layer():
    with pytest.raises(ValidationError):
        _prop([{"frame": "hypothesis:h1", "role": "rebuttal"}])


def test_membership_requires_frame():
    with pytest.raises(ValidationError):
        DiscussesMembership(role="core")


def test_empty_frame_rejected():
    with pytest.raises(ValidationError):
        DiscussesMembership(frame="", role="core")


def test_extra_keys_forbidden():
    with pytest.raises(ValidationError):
        DiscussesMembership(frame="hypothesis:h1", role="core", note="oops")


def test_conflicting_duplicate_frame_rejected_at_model_layer():
    with pytest.raises(ValidationError):
        _prop(["hypothesis:h1", {"frame": "hypothesis:h1", "role": "rival"}])


def test_identical_duplicate_frame_allowed():
    p = _prop(["hypothesis:h1", "hypothesis:h1"])  # same role -> no conflict
    assert list(p.iter_memberships()) == [("hypothesis:h1", MembershipRole.CORE)]
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run --frozen pytest science/model/tests/test_proposition_membership.py -v`
Expected: FAIL — `ImportError: cannot import name 'DiscussesMembership'` / `MembershipRole`.

- [ ] **Step 3: Add the enum to `reasoning.py`**

In `science/model/src/science_model/reasoning.py`, after the `EvidenceRole` enum (near line 94), add:

```python
class MembershipRole(StrEnum):
    """How a proposition participates in a hypothesis/mechanism bundle (spec §3.2).

    Closed vocabulary. ``core`` members enter the weakest-link conjunction;
    ``rival`` and ``background`` are excluded from it (spec §3.3).
    """

    CORE = "core"
    RIVAL = "rival"
    BACKGROUND = "background"


MEMBERSHIP_ROLE_VALUES = frozenset(v.value for v in MembershipRole)
```

- [ ] **Step 4: Add `DiscussesMembership`, widen the field, add the helper in `propositions.py`**

In `science/model/src/science_model/propositions.py`:

First ensure the imports include `BaseModel`, `ConfigDict`, `Field`, `Iterator`, `model_validator`, and `MembershipRole`. `Field` and `model_validator` are already imported in this module; add the rest:

```python
from collections.abc import Iterator

from pydantic import BaseModel, ConfigDict

from .reasoning import MembershipRole
```

Above the `PropositionEntity` class definition add:

```python
class DiscussesMembership(BaseModel):
    """Object form of a `discusses` entry: a frame plus the proposition's role in it.

    `frame` is a bundle reference (hypothesis or mechanism). A bare string in the
    `discusses` list is sugar for `{frame: <string>, role: core}`.
    """

    model_config = ConfigDict(extra="forbid")  # malformed membership hard-fails (spec §5)

    frame: str = Field(min_length=1)
    role: MembershipRole = MembershipRole.CORE
```

Change the `discusses` field (currently at `science/model/src/science_model/propositions.py:52`) from:

```python
    discusses: list[str] = Field(default_factory=list)
```

to:

```python
    # Bundle membership: focal hypothesis/mechanism(s) this proposition discusses (→ cito:discusses).
    # A bare string means role=core; an object carries an explicit MembershipRole (spec §3).
    discusses: list[str | DiscussesMembership] = Field(default_factory=list)
```

Add this method inside `PropositionEntity` (after the existing validators):

```python
    def iter_memberships(self) -> Iterator[tuple[str, MembershipRole]]:
        """Yield de-duped (frame_ref, role) pairs; bare strings are core."""
        seen: set[tuple[str, MembershipRole]] = set()
        for item in self.discusses:
            if isinstance(item, str):
                pair = (item, MembershipRole.CORE)
            else:
                pair = (item.frame, item.role)
            if pair in seen:
                continue
            seen.add(pair)
            yield pair

    @model_validator(mode="after")
    def _validate_membership_roles(self) -> "PropositionEntity":
        """A proposition has exactly one role per bundle frame (spec §5 rule 3).

        Enforced here, at the model layer, so the invariant holds at EVERY load
        site — materialize, workbench compile, and `science validate` alike — not
        only in the standalone validator. Identical-role duplicates are harmless.
        """
        roles_by_frame: dict[str, set[MembershipRole]] = {}
        for frame, role in self.iter_memberships():
            roles_by_frame.setdefault(frame, set()).add(role)
        conflicts = {f: r for f, r in roles_by_frame.items() if len(r) > 1}
        if conflicts:
            detail = ", ".join(
                f"{f}: {sorted(x.value for x in r)}" for f, r in sorted(conflicts.items())
            )
            raise ValueError(
                f"discusses lists conflicting membership roles for the same frame ({detail}); "
                "a proposition has exactly one role per bundle"
            )
        return self
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `uv run --frozen pytest science/model/tests/test_proposition_membership.py -v`
Expected: PASS (10 passed).

- [ ] **Step 6: Commit**

```bash
git add science/model/src/science_model/reasoning.py science/model/src/science_model/propositions.py science/model/tests/test_proposition_membership.py
git commit -m "feat(model): add MembershipRole and DiscussesMembership for bundle membership"
```

---

## Task 2: Materialization — emit plain triple + `BundleMembership` plumbing node

**Files:**
- Modify: `science/src/science_tool/graph/io.py`
- Modify: `science/src/science_tool/graph/materialize.py:590-599` (the `discusses` loop)
- Test: `science/tests/test_membership_materialize.py`

**Interfaces:**
- Consumes: `PropositionEntity.iter_memberships()` (Task 1); `MembershipRole` (Task 1).
- Produces (graph vocabulary, in `science_tool.graph.io`):
  - `SCI_NS.BundleMembership` (rdf:type of the membership node)
  - `SCI_NS.membershipProposition`, `SCI_NS.membershipFrame`, `SCI_NS.membershipRole` (predicates)
- Produces: deterministic membership-node IRIs `PROJECT_NS["membership/<prop>__<frame>"]` (slug-sanitized). For every `discusses` entry the graph contains both `(prop, cito:discusses, frame)` and the four membership-node triples.

- [ ] **Step 1: Write the failing materialize test**

Create `science/tests/test_membership_materialize.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest
from rdflib import Dataset, Literal
from rdflib.namespace import RDF

from science_tool.graph.io import CITO_NS, PROJECT_NS, SCI_NS
from science_tool.graph.materialize import _entity_uri, materialize_graph


def _write_entity(path: Path, frontmatter: list[str], body: str = "Body.") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(["---", *frontmatter, "---", "", body, ""]), encoding="utf-8")


def _hyp(path: Path, hid: str) -> None:
    _write_entity(
        path / "entities" / "hypotheses" / f"{hid}.md",
        [
            f'id: "hypothesis:{hid}"',
            'type: "hypothesis"',
            f'title: "{hid}"',
            'status: "proposed"',
            "ontology_terms: []",
            "source_refs: []",
            "related: []",
        ],
    )


def _prop(path: Path, pid: str, discusses_yaml: str) -> None:
    _write_entity(
        path / "entities" / "propositions" / f"{pid}.md",
        [
            f'id: "proposition:{pid}"',
            'type: "proposition"',
            f'title: "{pid}"',
            'status: "active"',
            "ontology_terms: []",
            "source_refs: []",
            "related: []",
            f"discusses: {discusses_yaml}",
        ],
    )


def _knowledge(tmp_path: Path):
    """Build the graph and return its knowledge named-graph.

    materialize_graph returns the TriG Path (materialize.py:429); the knowledge
    triples live in the PROJECT_NS["graph/knowledge"] named graph (materialize.py:162).
    """
    (tmp_path / "science.yaml").write_text("name: demo\n", encoding="utf-8")
    trig_path = materialize_graph(tmp_path, strict=False)
    ds = Dataset()
    ds.parse(str(trig_path), format="trig")
    return ds.graph(PROJECT_NS["graph/knowledge"])


def test_plain_discusses_triple_always_emitted_for_object_form(tmp_path: Path):
    _hyp(tmp_path, "h1")
    _prop(tmp_path, "p1", '[{frame: "hypothesis:h1", role: "rival"}]')
    knowledge = _knowledge(tmp_path)
    prop, hyp = _entity_uri("proposition:p1"), _entity_uri("hypothesis:h1")
    # The plain triple is preserved verbatim (annotate, never replace).
    assert (prop, CITO_NS.discusses, hyp) in knowledge


def test_membership_node_carries_role(tmp_path: Path):
    _hyp(tmp_path, "h1")
    _prop(tmp_path, "p1", '[{frame: "hypothesis:h1", role: "rival"}]')
    knowledge = _knowledge(tmp_path)
    prop, hyp = _entity_uri("proposition:p1"), _entity_uri("hypothesis:h1")
    members = list(knowledge.subjects(SCI_NS.membershipProposition, prop))
    assert len(members) == 1
    m = members[0]
    assert (m, RDF.type, SCI_NS.BundleMembership) in knowledge
    assert (m, SCI_NS.membershipFrame, hyp) in knowledge
    assert (m, SCI_NS.membershipRole, Literal("rival")) in knowledge


def test_bare_string_emits_core_membership(tmp_path: Path):
    _hyp(tmp_path, "h1")
    _prop(tmp_path, "p1", '["hypothesis:h1"]')
    knowledge = _knowledge(tmp_path)
    prop = _entity_uri("proposition:p1")
    m = next(iter(knowledge.subjects(SCI_NS.membershipProposition, prop)))
    assert (m, SCI_NS.membershipRole, Literal("core")) in knowledge


def test_unresolved_frame_is_loud_fail(tmp_path: Path):
    # No hypothesis h99 exists; the frame must not be silently dropped.
    _prop(tmp_path, "p1", '[{frame: "hypothesis:h99", role: "rival"}]')
    with pytest.raises(Exception) as exc:  # ValueError surfaced through the compile
        _knowledge(tmp_path)
    assert "h99" in str(exc.value) or "resolve" in str(exc.value).lower()


def test_non_bundle_frame_is_loud_fail(tmp_path: Path):
    # discusses must point at a bundle (hypothesis/mechanism), never another proposition.
    _prop(tmp_path, "p1", '["proposition:p2"]')
    _prop(tmp_path, "p2", "[]")
    with pytest.raises(Exception) as exc:
        _knowledge(tmp_path)
    assert "bundle" in str(exc.value).lower()


def test_metadata_ref_in_discusses_is_skipped_not_membership(tmp_path: Path):
    # meta:/spec: are the global annotation escape hatch — skipped, never rejected,
    # and never producing a membership node.
    _prop(tmp_path, "p1", '["meta:see-also"]')
    knowledge = _knowledge(tmp_path)
    prop = _entity_uri("proposition:p1")
    assert list(knowledge.subjects(SCI_NS.membershipProposition, prop)) == []
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run --frozen pytest science/tests/test_membership_materialize.py -v`
Expected: FAIL — membership-node subjects not found (only the plain triple exists today).

- [ ] **Step 3: Add the vocabulary terms in `io.py`**

In `science/src/science_tool/graph/io.py`, the `SCI_NS` namespace already exists (`SCI_NS = Namespace("http://example.org/science/vocab/")`). rdflib namespaces mint terms by attribute access, so `SCI_NS.BundleMembership` etc. work with no declaration. To keep them discoverable and documented, add a comment block near the namespace definitions:

```python
# Bundle-membership plumbing (NON-truth-apt; carries no belief, takes no evidence).
# A BundleMembership node annotates a (proposition, frame) cito:discusses edge with its role.
#   SCI_NS.BundleMembership          -- rdf:type of the membership node
#   SCI_NS.membershipProposition     -- node -> proposition IRI
#   SCI_NS.membershipFrame           -- node -> bundle (hypothesis/mechanism) IRI
#   SCI_NS.membershipRole            -- node -> Literal(MembershipRole value)
```

(No code constant is strictly required; `SCI_NS.<term>` is used directly in `materialize.py` and `bundle_belief.py`.)

- [ ] **Step 4: Rewrite the `discusses` loop in `materialize.py`**

Replace the loop at `science/src/science_tool/graph/materialize.py:590-599`, currently:

```python
    for raw_target in sorted(getattr(entity, "discusses", []) or []):
        if is_metadata_reference(raw_target):
            continue
        resolution = resolver.resolve(raw_target, allow_cross_kind_fallback=True)
        if resolution.status != "resolved" or resolution.canonical_id is None:
            continue
        target = entity_index.get(resolution.canonical_id)
        if target is None:
            continue
        knowledge.add((entity_uri, CITO_NS.discusses, _entity_uri(target.canonical_id)))
```

with:

```python
    for raw_target, role in _iter_membership_refs(entity):
        # `meta:`/`spec:` are the project-wide annotation-only escape hatch
        # (is_metadata_reference, sources.py): intentional pointers excluded from
        # KG materialization everywhere, NOT bundle memberships. They are skipped,
        # not rejected — membership semantics apply only to real entity refs.
        if is_metadata_reference(raw_target):
            continue
        # Loud-fail: a discusses frame MUST resolve (spec §5). A typo'd or dangling
        # frame is a hard error, never a silently dropped membership, because graph
        # audit does not currently cover PropositionEntity.discusses.
        resolution = resolver.resolve(raw_target, allow_cross_kind_fallback=True)
        if resolution.status != "resolved" or resolution.canonical_id is None:
            raise ValueError(
                f"{entity.canonical_id} discusses {raw_target!r}, which does not resolve to a "
                "known entity; a discusses frame must resolve to a bundle (spec §5)."
            )
        target = entity_index.get(resolution.canonical_id)
        if target is None:
            raise ValueError(
                f"{entity.canonical_id} discusses {resolution.canonical_id!r}, which resolved but "
                "is missing from the entity index; cannot emit membership (spec §5)."
            )
        frame_uri = _entity_uri(target.canonical_id)
        # Loud-fail: a discusses frame must be a bundle (hypothesis/mechanism) (spec §5 rule 2).
        frame_kind = resolution.canonical_id.split(":", 1)[0]
        if frame_kind not in ("hypothesis", "mechanism"):
            raise ValueError(
                f"{entity.canonical_id} discusses {resolution.canonical_id!r}, which is a "
                f"{frame_kind!r}, not a bundle (hypothesis/mechanism); membership roles are "
                "only valid on bundle frames (spec §5)."
            )
        # 1) Plain triple, emitted verbatim — annotate, never replace (spec §5).
        knowledge.add((entity_uri, CITO_NS.discusses, frame_uri))
        # 3) BundleMembership plumbing node carrying the role.
        membership_uri = _membership_uri(entity.canonical_id, resolution.canonical_id)
        knowledge.add((membership_uri, RDF.type, SCI_NS.BundleMembership))
        knowledge.add((membership_uri, SCI_NS.membershipProposition, entity_uri))
        knowledge.add((membership_uri, SCI_NS.membershipFrame, frame_uri))
        knowledge.add((membership_uri, SCI_NS.membershipRole, Literal(role.value)))
```

Add two module-level helpers near the top of `materialize.py` (after imports). Confirm `RDF`, `Literal`, `PROJECT_NS` are imported in this module; add any that are missing to the existing rdflib/io imports.

```python
def _iter_membership_refs(entity):
    """Yield (frame_ref, MembershipRole) for an entity's discusses entries.

    Propositions expose iter_memberships(); any other entity with a plain
    `discusses` list is treated as all-core (defensive, no behavior change).
    """
    iter_memberships = getattr(entity, "iter_memberships", None)
    if callable(iter_memberships):
        yield from sorted(iter_memberships(), key=lambda pair: pair[0])
        return
    from science_model.reasoning import MembershipRole

    for raw in sorted(getattr(entity, "discusses", []) or []):
        yield raw, MembershipRole.CORE


def _membership_uri(prop_canonical: str, frame_canonical: str):
    """Deterministic IRI for a (proposition, frame) membership node."""
    slug = f"{prop_canonical}__{frame_canonical}".replace(":", "_").replace("/", "_")
    return PROJECT_NS[f"membership/{slug}"]
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `uv run --frozen pytest science/tests/test_membership_materialize.py -v`
Expected: PASS (6 passed).

- [ ] **Step 6: Run the existing materialize/patch-membership suites for regressions**

Run: `uv run --frozen pytest science/tests/test_patch_membership_materialize.py science/tests/test_graph_materialize.py -v`
Expected: PASS (plain `cito:discusses` triple behavior unchanged).

- [ ] **Step 7: Commit**

```bash
git add science/src/science_tool/graph/io.py science/src/science_tool/graph/materialize.py science/tests/test_membership_materialize.py
git commit -m "feat(graph): emit BundleMembership role node alongside cito:discusses"
```

---

## Task 3: Bundle belief — gate the conjunction to `core` members

**Files:**
- Modify: `science/src/science_tool/graph/bundle_belief.py` (add `membership_role`, `core_members`; change member assembly in `belief_for_entity`)
- Test: `science/tests/test_bundle_belief_membership.py`

**Interfaces:**
- Consumes: `bundle_members(knowledge, uri)` (existing, unchanged, role-blind); `SCI_NS.membership*` terms (Task 2); `MembershipRole` (Task 1).
- Produces:
  - `membership_role(knowledge, member: URIRef, frame: URIRef) -> MembershipRole` — defaults to `MembershipRole.CORE` when no membership node exists (covers `sci:hasProposition` mechanism steps).
  - `core_members(knowledge, uri: URIRef) -> list[URIRef]` — `bundle_members` filtered to `core`, with forward `sci:hasProposition` members treated as authoritatively core (precedence over any `discusses` membership node on the same pair).
- Behavior: `belief_for_entity` conjuncts over `core_members`. Dangling-bundle detection still uses `bundle_members` (all members). A bundle that has members but **zero core** members: hypothesis → falls back to direct-evidence belief on the bundle IRI; mechanism or authored-rule bundle → `UnresolvedBundleError`.

- [ ] **Step 1: Write the failing roll-up test**

Create `science/tests/test_bundle_belief_membership.py`:

```python
from __future__ import annotations

from rdflib import Graph, Literal, RDF, URIRef

from science_model.reasoning import MembershipRole
from science_tool.graph.bundle_belief import core_members, membership_role
from science_tool.graph.io import CITO_NS, PROJECT_NS, SCI_NS


def _membership(g, prop, frame, role):
    m = PROJECT_NS[f"membership/{str(prop)}__{str(frame)}".replace(":", "_").replace("/", "_")]
    g.add((m, RDF.type, SCI_NS.BundleMembership))
    g.add((m, SCI_NS.membershipProposition, prop))
    g.add((m, SCI_NS.membershipFrame, frame))
    g.add((m, SCI_NS.membershipRole, Literal(role)))


def _bundle_graph():
    g = Graph()
    hyp = URIRef("urn:h1")
    core, rival, bg = URIRef("urn:p_core"), URIRef("urn:p_rival"), URIRef("urn:p_bg")
    g.add((hyp, RDF.type, SCI_NS.Hypothesis))
    for p in (core, rival, bg):
        g.add((p, RDF.type, SCI_NS.Proposition))
        g.add((p, CITO_NS.discusses, hyp))
    _membership(g, core, hyp, "core")
    _membership(g, rival, hyp, "rival")
    _membership(g, bg, hyp, "background")
    return g, hyp, core, rival, bg


def test_membership_role_reads_node():
    g, hyp, core, rival, bg = _bundle_graph()
    assert membership_role(g, core, hyp) == MembershipRole.CORE
    assert membership_role(g, rival, hyp) == MembershipRole.RIVAL
    assert membership_role(g, bg, hyp) == MembershipRole.BACKGROUND


def test_membership_role_defaults_core_when_absent():
    g = Graph()
    p, hyp = URIRef("urn:p"), URIRef("urn:h")
    assert membership_role(g, p, hyp) == MembershipRole.CORE


def test_core_members_excludes_rival_and_background():
    g, hyp, core, rival, bg = _bundle_graph()
    assert core_members(g, hyp) == [core]


def test_has_proposition_is_authoritatively_core():
    # A proposition that is BOTH a mechanism step (hasProposition) AND discussed as a
    # rival of the same frame must stay core — forward membership wins (spec §3.3).
    g = Graph()
    mech, step = URIRef("urn:m1"), URIRef("urn:p_step")
    g.add((mech, RDF.type, SCI_NS.Mechanism))
    g.add((step, RDF.type, SCI_NS.Proposition))
    g.add((mech, SCI_NS.hasProposition, step))
    g.add((step, CITO_NS.discusses, mech))
    _membership(g, step, mech, "rival")  # contradictory authoring; forward wins
    assert membership_role(g, step, mech) == MembershipRole.RIVAL
    assert core_members(g, mech) == [step]
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run --frozen pytest science/tests/test_bundle_belief_membership.py -v`
Expected: FAIL — `ImportError: cannot import name 'core_members'`.

- [ ] **Step 3: Add `membership_role` and `core_members` to `bundle_belief.py`**

In `science/src/science_tool/graph/bundle_belief.py`, add `MembershipRole` to the existing `science_model.reasoning` import (the file already imports `RDF, URIRef` from rdflib — no new rdflib import is needed, and `Literal` would be flagged unused by Ruff). The line becomes:

```python
from science_model.reasoning import CompositionRule, MembershipRole, RESERVED_COMPOSITION_RULES
```

After the existing `bundle_members` function add:

```python
def membership_role(knowledge, member: URIRef, frame: URIRef) -> MembershipRole:
    """Role of `member` within `frame`'s bundle; CORE when no membership node exists.

    Absence-defaults to CORE so sci:hasProposition mechanism steps (which carry no
    membership node) and any pre-migration edge behave exactly as today.
    """
    for node in knowledge.subjects(SCI_NS.membershipProposition, member):
        if (node, SCI_NS.membershipFrame, frame) in knowledge:
            value = knowledge.value(node, SCI_NS.membershipRole)
            if value is not None:
                return MembershipRole(str(value))
    return MembershipRole.CORE


def core_members(knowledge, uri: URIRef) -> list[URIRef]:
    """bundle_members filtered to CORE — the conjunction's membership set (spec §3.3).

    Precedence: a member reached via forward sci:hasProposition is AUTHORITATIVELY
    core (a mechanism step is structurally core), regardless of any BundleMembership
    node. Only members reached via reverse cito:discusses consult their role. This
    makes "hasProposition means core" exact and deterministic even when a proposition
    is both a step of, and discussed (e.g. as a rival of) the same frame.
    """
    forward_core = set(knowledge.objects(uri, SCI_NS.hasProposition))
    result: list[URIRef] = []
    for m in bundle_members(knowledge, uri):
        if m in forward_core or membership_role(knowledge, m, uri) == MembershipRole.CORE:
            result.append(m)
    return result
```

- [ ] **Step 4: Gate the conjunction in `belief_for_entity`**

In `belief_for_entity` (`science/src/science_tool/graph/bundle_belief.py`), the current body computes `members = bundle_members(knowledge, uri)` then the dangling check then builds `member_beliefs`. Replace that region — from `members = bundle_members(knowledge, uri)` down to the start of the `member_beliefs` loop — with:

```python
    all_members = bundle_members(knowledge, uri)
    if not all_members:
        if authored_rule is not None or kind == "mechanism":
            raise UnresolvedBundleError(
                f"{uri} is a {kind} bundle with zero resolved member propositions "
                "(dangling has_proposition / discusses links?); refusing to collapse to "
                "direct-evidence belief."
            )
        return aggregate_belief(collect_evidence_units(knowledge, provenance, [uri]))

    members = core_members(knowledge, uri)
    if not members:
        # Has members, but none are core (all rival/background).
        if authored_rule is not None or kind == "mechanism":
            raise UnresolvedBundleError(
                f"{uri} is a {kind} bundle whose only members are rival/background "
                "(zero core members); a conjunction requires at least one core member."
            )
        # Forgiving hypothesis case: fall back to direct evidence on the bundle IRI.
        return aggregate_belief(collect_evidence_units(knowledge, provenance, [uri]))

    rule = authored_rule or _KIND_DEFAULT_RULE[kind]
    member_beliefs: list[MemberBelief] = []
```

(The `for member in members:` loop that follows is unchanged — it now iterates the core-only list.)

- [ ] **Step 5: Run the new test to verify it passes**

Run: `uv run --frozen pytest science/tests/test_bundle_belief_membership.py -v`
Expected: PASS (4 passed).

- [ ] **Step 6: Run the existing roll-up suite for regressions**

Run: `uv run --frozen pytest science/tests/test_bundle_belief_rollup.py science/tests/test_belief_policy_bundle.py -v`
Expected: PASS — with all members defaulting to `core`, results are unchanged.

- [ ] **Step 7: Commit**

```bash
git add science/src/science_tool/graph/bundle_belief.py science/tests/test_bundle_belief_membership.py
git commit -m "feat(belief): gate bundle conjunction to core members"
```

---

## Task 4: Validation — frontmatter structural checks for membership

**Files:**
- Modify: `science/src/science_tool/validate/checks/propositions.py`
- Test: `science/tests/test_membership_validation.py`

**Interfaces:**
- Consumes: `MEMBERSHIP_ROLE_VALUES` (Task 1); `ValidateContext.frontmatter` / the module's `_propositions(ctx)` helper; `Check`, `Result`, `Severity` (existing in module).
- Produces: `check_discusses_membership(ctx) -> Iterator[Result]`, registered `@Check(section="propositions", order=30)`. Rules (spec §5): (0) top-level `discusses`, when present, must be a list → ERROR; (1) unknown role → ERROR; (2) object entry missing/empty `frame` → ERROR; (3) two entries naming the same frame with conflicting roles → ERROR; (4) a bare string and an object naming the same frame is a same-frame duplicate (rule 3 applies). Note: "frame must resolve to a bundle kind" is enforced at graph-build time in Task 2; the conflict rule (3) is *also* enforced at the model layer (Task 1, the authoritative load-time gate). This frontmatter check is fast pre-build authoring feedback, not the sole enforcement point.

- [ ] **Step 1: Write the failing validation test**

Create `science/tests/test_membership_validation.py`:

```python
from __future__ import annotations

from pathlib import Path

from science_tool.validate.checks.propositions import check_discusses_membership
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Severity


def _project(tmp_path: Path, discusses_yaml: str) -> ValidateContext:
    (tmp_path / "science.yaml").write_text("name: demo\n", encoding="utf-8")
    pdir = tmp_path / "entities" / "propositions"
    pdir.mkdir(parents=True, exist_ok=True)
    (pdir / "p1.md").write_text(
        "\n".join(
            [
                "---",
                'id: "proposition:p1"',
                'type: "proposition"',
                'title: "P1"',
                'status: "active"',
                "ontology_terms: []",
                "source_refs: []",
                "related: []",
                f"discusses: {discusses_yaml}",
                "---",
                "",
                "Body.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return ValidateContext.from_project_root(tmp_path, strict=True, verbose=False)


def _errors(ctx):
    return [r for r in check_discusses_membership(ctx) if r.severity == Severity.ERROR]


def test_valid_membership_has_no_errors(tmp_path: Path):
    ctx = _project(tmp_path, '[{frame: "hypothesis:h1", role: "rival"}]')
    assert _errors(ctx) == []


def test_bare_string_has_no_errors(tmp_path: Path):
    ctx = _project(tmp_path, '["hypothesis:h1"]')
    assert _errors(ctx) == []


def test_unknown_role_is_error(tmp_path: Path):
    ctx = _project(tmp_path, '[{frame: "hypothesis:h1", role: "rebuttal"}]')
    errs = _errors(ctx)
    assert any(r.rule == "proposition.membership.role" for r in errs)


def test_missing_frame_is_error(tmp_path: Path):
    ctx = _project(tmp_path, '[{role: "core"}]')
    errs = _errors(ctx)
    assert any(r.rule == "proposition.membership.frame" for r in errs)


def test_top_level_scalar_discusses_is_error(tmp_path: Path):
    ctx = _project(tmp_path, '"hypothesis:h1"')
    errs = _errors(ctx)
    assert any(r.rule == "proposition.membership.shape" for r in errs)


def test_top_level_mapping_discusses_is_error(tmp_path: Path):
    ctx = _project(tmp_path, '{frame: "hypothesis:h1", role: "core"}')
    errs = _errors(ctx)
    assert any(r.rule == "proposition.membership.shape" for r in errs)


def test_conflicting_duplicate_frame_is_error(tmp_path: Path):
    ctx = _project(
        tmp_path,
        '[{frame: "hypothesis:h1", role: "core"}, {frame: "hypothesis:h1", role: "rival"}]',
    )
    errs = _errors(ctx)
    assert any(r.rule == "proposition.membership.duplicate" for r in errs)


def test_string_and_object_same_frame_conflict_is_error(tmp_path: Path):
    ctx = _project(tmp_path, '["hypothesis:h1", {frame: "hypothesis:h1", role: "rival"}]')
    errs = _errors(ctx)
    assert any(r.rule == "proposition.membership.duplicate" for r in errs)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run --frozen pytest science/tests/test_membership_validation.py -v`
Expected: FAIL — `cannot import name 'check_discusses_membership'`.

- [ ] **Step 3: Add the check to `propositions.py`**

In `science/src/science_tool/validate/checks/propositions.py`, extend the model import:

```python
from science_model.reasoning import (
    MEMBERSHIP_ROLE_VALUES,
    SIGN_MEANINGFUL_PREDICATES,
    ClaimLayer,
    IdentificationStrength,
    Polarity,
)
```

At the end of the file add:

```python
@Check(section="propositions", order=30)
def check_discusses_membership(ctx: ValidateContext) -> Iterator[Result]:
    """Structural QA for `discusses` membership entries (spec §5 rules 0, 1, 3, 4).

    Rule 2's "frame must be a bundle kind" is enforced at graph-build time
    (materialize), not here, since kind resolution needs the entity index.
    """
    for path, fm in _propositions(ctx):
        raw_discusses = fm.get("discusses")
        if raw_discusses is None:
            continue
        if not isinstance(raw_discusses, list):
            yield Result(
                severity=Severity.ERROR,
                path=path,
                line=None,
                message=f"{path.name}: discusses must be a list of strings or {{frame, role}} objects",
                rule="proposition.membership.shape",
                task=None,
            )
            continue
        discusses = raw_discusses
        roles_by_frame: dict[str, set[str]] = {}
        for entry in discusses:
            if isinstance(entry, str):
                frame, role = entry, "core"  # bare string => core
            elif isinstance(entry, dict):
                frame = entry.get("frame")
                role = entry.get("role", "core")
                if not frame:
                    yield Result(
                        severity=Severity.ERROR,
                        path=path,
                        line=None,
                        message=f"{path.name}: discusses entry missing required 'frame'",
                        rule="proposition.membership.frame",
                        task=None,
                    )
                    continue
                if str(role) not in MEMBERSHIP_ROLE_VALUES:
                    yield Result(
                        severity=Severity.ERROR,
                        path=path,
                        line=None,
                        message=(
                            f"{path.name}: discusses role '{role}' is not a canonical "
                            f"MembershipRole — must be one of {sorted(MEMBERSHIP_ROLE_VALUES)}"
                        ),
                        rule="proposition.membership.role",
                        task=None,
                    )
                    continue
            else:
                yield Result(
                    severity=Severity.ERROR,
                    path=path,
                    line=None,
                    message=f"{path.name}: discusses entry must be a string or a {{frame, role}} object",
                    rule="proposition.membership.shape",
                    task=None,
                )
                continue
            roles_by_frame.setdefault(str(frame), set()).add(str(role))

        for frame, roles in sorted(roles_by_frame.items()):
            if len(roles) > 1:
                yield Result(
                    severity=Severity.ERROR,
                    path=path,
                    line=None,
                    message=(
                        f"{path.name}: frame '{frame}' is listed with conflicting membership "
                        f"roles {sorted(roles)} — a proposition has exactly one role per bundle"
                    ),
                    rule="proposition.membership.duplicate",
                    task=None,
                )
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run --frozen pytest science/tests/test_membership_validation.py -v`
Expected: PASS (8 passed).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/validate/checks/propositions.py science/tests/test_membership_validation.py
git commit -m "feat(validate): structural checks for discusses membership roles"
```

---

## Task 5: Workbench authoring path — accept `{frame, role}` in `WorkbenchRow.discusses`

**Files:**
- Modify: `science/src/science_tool/dag/workbench.py` (`WorkbenchRow.discusses` field at `:153`; `_resolve_row_discusses` at `:213`; the stamp at `:342-344`)
- Test: `science/tests/test_workbench_membership_roles.py`

**Why:** `<patch>.workbench.yaml` is a supported proposition-authoring surface (`compile_workbench` mints proposition entities from rows). If only the entity-file path accepts `{frame, role}`, curators cannot mark `rival`/`background` on the workbench and the two surfaces carry incompatible `discusses` contracts. This task aligns them.

**Interfaces:**
- Consumes: `DiscussesMembership` (Task 1); the model-layer conflict validator (Task 1).
- Produces: `WorkbenchRow.discusses: list[str | DiscussesMembership] | None`; `_resolve_row_discusses(...) -> list[str | DiscussesMembership] | None`; `compile_workbench` stamps the role-bearing list onto the minted proposition **and re-validates** so a conflicting row fails at compile (not only at later load).

- [ ] **Step 1: Write the failing workbench test**

Create `science/tests/test_workbench_membership_roles.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from science_model.reasoning import MembershipRole
from science_tool.dag.workbench import (
    WorkbenchFile,
    WorkbenchRow,
    _resolve_row_discusses,
    compile_workbench,
)


def _row(discusses):
    # patch is a required WorkbenchRow field (workbench.py:134).
    return WorkbenchRow(
        subject="gene:x", predicate="affects", object="outcome:y",
        patch="patch:p1", discusses=discusses,
    )


def _seed(tmp_path: Path) -> Path:
    (tmp_path / "science.yaml").write_text(
        "name: demo\nknowledge_profiles:\n  local: local\n", encoding="utf-8"
    )
    return tmp_path


def test_row_accepts_object_form_discusses():
    row = _row([{"frame": "hypothesis:h1", "role": "rival"}])
    resolved = _resolve_row_discusses(row, None)
    # The membership object round-trips through resolution.
    assert resolved is not None and len(resolved) == 1
    item = resolved[0]
    assert getattr(item, "frame", None) == "hypothesis:h1"
    assert getattr(item, "role", None) == MembershipRole.RIVAL


def test_bare_string_row_still_works():
    row = _row(["hypothesis:h1"])
    assert _resolve_row_discusses(row, None) == ["hypothesis:h1"]


def test_compile_workbench_preserves_role(tmp_path: Path):
    # Drives the real compile path end-to-end (not a manual stamp).
    wb = WorkbenchFile(rows=[_row([{"frame": "hypothesis:h1", "role": "background"}])])
    result = compile_workbench(wb, project_root=_seed(tmp_path))
    prop = result.propositions[0]
    assert ("hypothesis:h1", MembershipRole.BACKGROUND) in list(prop.iter_memberships())


def test_compile_workbench_rejects_conflicting_roles(tmp_path: Path):
    # Same frame, two roles. This raises ONLY if compile re-validates (model_validate);
    # a model_copy stamp would skip the validator and silently pass — so this test is
    # what forces the Step 4 change.
    wb = WorkbenchFile(
        rows=[_row(["hypothesis:h1", {"frame": "hypothesis:h1", "role": "rival"}])]
    )
    with pytest.raises(ValidationError):
        compile_workbench(wb, project_root=_seed(tmp_path))
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run --frozen pytest science/tests/test_workbench_membership_roles.py -v`
Expected: FAIL — `WorkbenchRow` rejects the object form (`discusses` is `list[str] | None`).

- [ ] **Step 3: Widen the field and resolver in `workbench.py`**

Add the import near the other model imports at the top of `science/src/science_tool/dag/workbench.py`:

```python
from science_model.propositions import DiscussesMembership
```

Change the field at `science/src/science_tool/dag/workbench.py:153` from:

```python
    discusses: list[str] | None = None
```

to:

```python
    # A bare string means role=core; an object carries an explicit MembershipRole
    # (same contract as PropositionEntity.discusses — spec §5).
    discusses: list[str | DiscussesMembership] | None = None
```

Change the `_resolve_row_discusses` signature (`:213`) return annotation from `list[str] | None` to `list[str | DiscussesMembership] | None`. Its body is unchanged — `return list(row.discusses)` already passes the entries through verbatim.

- [ ] **Step 4: Re-validate when stamping (`:342-344`)**

Replace:

```python
        discusses = _resolve_row_discusses(row, wb.focal_hypothesis)
        if discusses is not None:
            prop = prop.model_copy(update={"discusses": discusses})
```

with:

```python
        discusses = _resolve_row_discusses(row, wb.focal_hypothesis)
        if discusses is not None:
            # model_validate (not model_copy) so the membership-conflict validator
            # runs at compile time, not only on later load (spec §5 rule 3).
            prop = PropositionEntity.model_validate({**prop.model_dump(), "discusses": discusses})
```

(`PropositionEntity` is already imported in this module — it is the return type of `_proposition_for_row`.)

- [ ] **Step 5: Run the test to verify it passes**

Run: `uv run --frozen pytest science/tests/test_workbench_membership_roles.py -v`
Expected: PASS (4 passed).

- [ ] **Step 6: Run the existing workbench suite for regressions**

Run: `uv run --frozen pytest science/tests/test_workbench_membership_wiring.py -v`
Expected: PASS (bare-string / `focal_hypothesis` routing unchanged).

- [ ] **Step 7: Commit**

```bash
git add science/src/science_tool/dag/workbench.py science/tests/test_workbench_membership_roles.py
git commit -m "feat(workbench): accept {frame, role} membership in discusses rows"
```

---

## Task 6: End-to-end migration safety + full suite

**Files:**
- Test: extend `science/tests/test_bundle_belief_membership.py` with an end-to-end case
- No production code changes (verification task)

**Interfaces:**
- Consumes: everything from Tasks 1–4.
- Produces: an e2e test proving (a) a corpus with only bare-string `discusses` yields an unchanged conjunction, and (b) marking a member `rival` removes it from the conjunction while the plain triple (coverage) is retained.

- [ ] **Step 1: Write the end-to-end test**

Append to `science/tests/test_bundle_belief_membership.py`:

```python
from pathlib import Path

from rdflib import Dataset

from science_tool.graph.bundle_belief import bundle_members, core_members
from science_tool.graph.io import PROJECT_NS
from science_tool.graph.materialize import _entity_uri, materialize_graph


def _write(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(["---", *lines, "---", "", "Body.", ""]), encoding="utf-8")


def _mini_project(tmp_path: Path, p2_discusses: str) -> Path:
    (tmp_path / "science.yaml").write_text("name: demo\n", encoding="utf-8")
    _write(
        tmp_path / "entities" / "hypotheses" / "h1.md",
        ['id: "hypothesis:h1"', 'type: "hypothesis"', 'title: "H1"', 'status: "proposed"',
         "ontology_terms: []", "source_refs: []", "related: []"],
    )
    for pid, disc in (("p1", '["hypothesis:h1"]'), ("p2", p2_discusses)):
        _write(
            tmp_path / "entities" / "propositions" / f"{pid}.md",
            [f'id: "proposition:{pid}"', 'type: "proposition"', f'title: "{pid}"',
             'status: "active"', "ontology_terms: []", "source_refs: []", "related: []",
             f"discusses: {disc}"],
        )
    return tmp_path


def _knowledge(tmp_path: Path):
    """materialize_graph returns the TriG Path; parse it and return the knowledge graph."""
    trig_path = materialize_graph(tmp_path, strict=False)
    ds = Dataset()
    ds.parse(str(trig_path), format="trig")
    return ds.graph(PROJECT_NS["graph/knowledge"])


def test_coverage_is_role_blind_but_conjunction_is_not(tmp_path: Path):
    k = _knowledge(_mini_project(tmp_path, '[{frame: "hypothesis:h1", role: "rival"}]'))
    hyp = _entity_uri("hypothesis:h1")
    p1, p2 = _entity_uri("proposition:p1"), _entity_uri("proposition:p2")
    # Coverage / linked claims (role-blind): both propositions still discuss h1.
    assert set(bundle_members(k, hyp)) == {p1, p2}
    # Conjunction membership (role-aware): the rival is excluded.
    assert core_members(k, hyp) == [p1]


def test_all_core_corpus_conjunction_membership_unchanged(tmp_path: Path):
    k = _knowledge(_mini_project(tmp_path, '["hypothesis:h1"]'))
    hyp = _entity_uri("hypothesis:h1")
    assert set(core_members(k, hyp)) == set(bundle_members(k, hyp))
```

- [ ] **Step 2: Run the e2e test**

Run: `uv run --frozen pytest science/tests/test_bundle_belief_membership.py -v`
Expected: PASS (all, including the two new e2e cases).

- [ ] **Step 3: Run the full belief + graph + validate test suites**

Run: `uv run --frozen pytest science/tests/ -k "belief or materialize or membership or proposition or graph or validate" -v`
Expected: PASS. Investigate any failure before proceeding — a regression here means an existing `cito:discusses` consumer changed behavior, which violates the annotate-never-replace constraint.

- [ ] **Step 4: Run validation on a real project to confirm no corpus breakage**

Run: `cd ~/d/health/processes/post-acute-infection && uv run --frozen science validate`
Expected: PASS (or the same pre-existing warnings as before this work). A new ERROR about a non-bundle `discusses` frame is a real latent bug in the corpus to be fixed separately, not a plan defect — report it.

- [ ] **Step 5: Commit**

```bash
git add science/tests/test_bundle_belief_membership.py
git commit -m "test: end-to-end membership-role migration safety"
```

---

## Self-Review

**Spec coverage (against `2026-06-19-contextual-structural-roles-design.md`):**

- §3.1 role-assignment `{proposition, frame, role}`, `frame` ranges over hypothesis/mechanism → Task 1 (`DiscussesMembership.frame`, `iter_memberships`), Task 2 (kind loud-fail accepts hypothesis+mechanism).
- §3.2 closed vocabulary `core`/`rival`/`background`, named distinctly from `evidence_role` → Task 1 (`MembershipRole`).
- §3.3 conjunction = core only; coverage stays role-blind; migration default core → Task 3 (`core_members` gates the conjunction; `bundle_members` untouched), Task 6 (e2e role-blind coverage vs role-aware conjunction). Forward `sci:hasProposition` members are authoritatively core (precedence over any contradictory `discusses` rival node) → Task 3 (`test_has_proposition_is_authoritatively_core`).
- §5 annotate-never-replace plain triple → Task 2 (Step 4 emits the plain triple for every valid frame; invalid frames abort the build, never half-emit). Membership node is plumbing, non-truth-apt, not edge-as-node → Task 2 (`BundleMembership`, no belief/evidence triples; vocabulary comment). `frame` field name → Task 1. Only `bundle_belief` consumes the role → Task 3. Migration lossless → Task 6. Validation rules 0/1/3/4 → Task 4 (frontmatter) **and** the model-layer conflict validator (Task 1, authoritative); rule 2 (bundle-kind) + unresolved-frame loud-fail → Task 2. Both authoring surfaces (entity files + workbench rows) accept `{frame, role}` → Tasks 1 + 5.
- §7 rival-contrast channel deferred → out of scope (Global Constraints).

**Loud-fail coverage (reviewer concern):** a typo'd/dangling frame raises at graph build (Task 2 Step 4); a non-bundle frame raises at graph build (Task 2); conflicting duplicate roles raise at *every* model load — materialize, workbench compile, validate (Task 1 validator) — plus fast frontmatter feedback (Task 4); top-level non-list `discusses` is a validation error (Task 4); malformed object (extra keys / empty frame) raises at the model layer (Task 1, `extra="forbid"` + `min_length=1`). No bad membership is silently dropped. The one intentional skip — `meta:`/`spec:` annotation refs — is the project-wide escape hatch, documented in the loop and covered by `test_metadata_ref_in_discusses_is_skipped_not_membership` (Task 2).

**Placeholder scan:** No TBD/TODO; every code step shows complete code. No deliberate artifacts remain.

**Type consistency:** `MembershipRole` (enum), `DiscussesMembership.frame: str` / `.role: MembershipRole`, `iter_memberships() -> Iterator[tuple[str, MembershipRole]]`, `membership_role(knowledge, member, frame) -> MembershipRole`, `core_members(knowledge, uri) -> list[URIRef]`, `WorkbenchRow.discusses: list[str | DiscussesMembership] | None` — names and signatures match across Tasks 1→2→3→5→6. Graph terms `SCI_NS.membershipProposition` / `membershipFrame` / `membershipRole` / `BundleMembership` are used identically in Tasks 2 and 3. `MEMBERSHIP_ROLE_VALUES` (Task 1) is consumed in Task 4 (no leading underscore — the name is exported across packages).

**Verified against source (no remaining static unknowns):** `materialize_graph()` returns a `Path` (`materialize.py:429`); the knowledge graph is `PROJECT_NS["graph/knowledge"]` (`materialize.py:162`); tests parse the TriG into a `Dataset()` and select that named graph (mirrors `test_patch_membership_materialize.py`). `WorkbenchRow.discusses` and the `compile_workbench` stamp site are confirmed (`workbench.py:153`, `:342-344`).
```

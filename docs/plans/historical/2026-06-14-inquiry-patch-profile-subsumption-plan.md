# Inquiry Patch Profile Subsumption Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `Patch` the single named-graph neighborhood substrate by reframing inquiry as an authored profile (`patch_type: inquiry`) on a `PatchDefinition`, compiling it to membership + legacy-equivalent `sci:Inquiry` view triples, and retiring direct graph mutation.

**Architecture:** A `PatchDefinitionEntity` gains `patch_type` and an authored `inquiry:` block (`InquiryProfile`, profiles `investigation`/`causal`). At `science graph build`, a new pure emitter renders the block into a dedicated `inquiry/<slug>` named graph (the layout all readers already expect), *before* membership derivation so minted assumption/transformation nodes are typed; the keystone deriver then pulls inquiry-referenced entities in as members with a new `derivationReason = "inquiry"`. The `science inquiry` CLI becomes scaffold + import + read-only; the five graph-writing mutators fail loudly.

**Tech Stack:** Python 3.13, Pydantic v2, rdflib, Click, pytest, uv workspace.

**Design:** `~/d/science/docs/plans/2026-06-14-inquiry-patch-profile-subsumption-design.md`. Builds on the shipped Patch Contract keystone now summarized in `~/d/science/docs/audits/plans-cleanup/2026-06-08-epistemic-model-checkpoint.md` and `~/d/science/docs/user-guide/graph-and-derived-state.md`.

---

## ⚠️ Conventions (read first — the keystone plan got these wrong)

This is a **uv workspace**. The tool package lives under `science/`; the model package is a path source at `science/model/`. The work happens in an isolated worktree (`superpowers:using-git-worktrees`).

- **All paths below are relative to the worktree root.**
- **Tests** run from the `science/` subdirectory; running from the worktree root fails with `ModuleNotFoundError: No module named 'science_model'`. Form: `cd science && uv run --frozen pytest <path> -v`.
- Model tests live in `science/model/tests/` (path `model/tests/...` once inside `science/`); tool tests in `science/tests/` (path `tests/...`).
- **Commits** run from the worktree root with worktree-relative paths: `git add science/<path>`. The implementing subagent MUST `cd` into the worktree and verify the branch before committing, or commits leak to `main`.

---

## File Structure

| File | Responsibility | Task |
|---|---|---|
| `science/model/src/science_model/patch_definition.py` (modify) | `patch_type` field; `InquiryProfile` + nested `BoundaryRole`/`FlowEdge`/`Assumption`/`Transformation`/`Param`; cross-field validation | 1 |
| `science/model/tests/test_inquiry_profile.py` (create) | Model validation tests | 1 |
| `science/src/science_tool/graph/inquiry_compile.py` (create) | Pure emitter: `InquiryProfile` → dedicated `inquiry/<slug>` graph (legacy triples); existing-ref + minted-node origin helpers | 2 |
| `science/src/science_tool/graph/store/inquiry.py` (modify) | Add `sci:focalEntity` to `get_inquiry`'s `metadata_predicates` exclusion set | 2 |
| `science/tests/test_inquiry_compile.py` (create) | Golden emission tests + focalEntity-not-an-edge | 2 |
| `science/src/science_tool/graph/patch_membership.py` (modify) | `DerivationReason` += `"inquiry"`; pull inquiry origins into membership | 3 |
| `science/tests/test_patch_membership_deriver.py` (modify) | Inquiry-origin derivation + hard-error + ordering tests | 3 |
| `science/src/science_tool/graph/materialize.py` (modify) | Emit inquiry views **before** membership derivation | 4 |
| `science/tests/test_inquiry_patch_materialize.py` (create) | End-to-end `materialize_graph` integration | 4 |
| `science/src/science_tool/cli.py` (modify) | `inquiry` group: `init` scaffold, `import` bridge, retire mutators, keep read-only | 5 |
| `science/tests/test_inquiry_cli_subsumption.py` (create) | CLI behavior tests | 5 |
| `science/model/src/science_model/templates.py` (modify) | Drop `"inquiry"` from `MIGRATED_KINDS` | 6 |
| `science/model/src/science_model/templates/inquiry.md` (delete) | Retire legacy inquiry entity-kind template | 6 |
| Existing `science/tests/test_inquiry*.py` (modify) | Re-point mutation tests → compile path; keep reader tests | 7 |

---

## Task 1: Authored model — `patch_type` + `InquiryProfile`

**Files:**
- Modify: `science/model/src/science_model/patch_definition.py`
- Test: `science/model/tests/test_inquiry_profile.py`

- [ ] **Step 1: Write the failing tests**

Create `science/model/tests/test_inquiry_profile.py`:

```python
import pytest
from pydantic import ValidationError

from science_model.patch_definition import PatchDefinitionEntity


def _base(**inquiry):
    return {
        "id": "patch-definition:p01-demo",
        "title": "Demo",
        "focal": "hypothesis:h01",
        "scope_set": [{"scope": "local"}],
        "neighborhood_policy": {},
        "patch_type": "inquiry",
        "inquiry": inquiry,
    }


def test_investigation_profile_minimal_valid():
    ent = PatchDefinitionEntity(**_base(profile="investigation", status="sketch"))
    assert ent.patch_type == "inquiry"
    assert ent.inquiry is not None
    assert ent.inquiry.profile == "investigation"


def test_causal_requires_treatment_and_outcome():
    with pytest.raises(ValidationError, match="causal profile requires"):
        PatchDefinitionEntity(**_base(profile="causal", status="specified"))


def test_causal_valid_with_estimand():
    ent = PatchDefinitionEntity(
        **_base(profile="causal", status="specified", treatment="concept:drug", outcome="concept:recovery")
    )
    assert ent.inquiry.treatment == "concept:drug"
    assert ent.inquiry.outcome == "concept:recovery"


def test_investigation_forbids_estimand():
    with pytest.raises(ValidationError, match="investigation profile must not"):
        PatchDefinitionEntity(**_base(profile="investigation", status="sketch", treatment="concept:drug"))


def test_inquiry_block_required_when_patch_type_inquiry():
    data = {
        "id": "patch-definition:p02-x",
        "title": "X",
        "focal": "hypothesis:h01",
        "scope_set": [{"scope": "local"}],
        "neighborhood_policy": {},
        "patch_type": "inquiry",
    }
    with pytest.raises(ValidationError, match="requires an inquiry block"):
        PatchDefinitionEntity(**data)


def test_inquiry_block_forbidden_for_plain_patch():
    data = {
        "id": "patch-definition:p03-x",
        "title": "X",
        "focal": "hypothesis:h01",
        "scope_set": [{"scope": "local"}],
        "neighborhood_policy": {},
        "inquiry": {"profile": "investigation", "status": "sketch"},
    }
    with pytest.raises(ValidationError, match="only allowed when patch_type"):
        PatchDefinitionEntity(**data)


def test_boundary_role_enum_enforced():
    with pytest.raises(ValidationError):
        PatchDefinitionEntity(
            **_base(profile="investigation", status="sketch", boundary_roles=[{"ref": "concept:x", "role": "Bogus"}])
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science && uv run --frozen pytest model/tests/test_inquiry_profile.py -v`
Expected: FAIL — `PatchDefinitionEntity` has no `patch_type`/`inquiry`.

- [ ] **Step 3: Add the nested models and fields**

In `science/model/src/science_model/patch_definition.py`, add these nested models after `LocalClosurePolicy` (the file already imports `BaseModel, ConfigDict, Field, ValidationInfo, field_validator, model_validator` and `Literal`):

```python
BoundaryRoleName = Literal["BoundaryIn", "BoundaryOut"]
FlowPredicate = Literal["feedsInto", "produces", "causes"]
InquiryProfileName = Literal["investigation", "causal"]
InquiryStatus = Literal["sketch", "specified", "planned", "in-progress", "complete"]


class BoundaryRole(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ref: str
    role: BoundaryRoleName


class FlowEdge(BaseModel):
    model_config = ConfigDict(extra="forbid")
    subject: str
    predicate: FlowPredicate
    object: str
    claim_refs: list[str] = Field(default_factory=list)


class Param(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: str
    source: str = ""
    ref: str = ""
    note: str = ""


class Assumption(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ref: str
    statement: str
    derived_from: str = ""


class Transformation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ref: str
    tool: str = ""
    params: list[Param] = Field(default_factory=list)
    validated_by: str = ""


class InquiryProfile(BaseModel):
    """Authored investigation design layered on a patch."""

    model_config = ConfigDict(extra="forbid")

    profile: InquiryProfileName
    status: InquiryStatus = "sketch"
    boundary_roles: list[BoundaryRole] = Field(default_factory=list)
    flow_edges: list[FlowEdge] = Field(default_factory=list)
    assumptions: list[Assumption] = Field(default_factory=list)
    transformations: list[Transformation] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    treatment: str | None = None
    outcome: str | None = None

    @model_validator(mode="after")
    def _estimand_rules(self) -> "InquiryProfile":
        if self.profile == "causal" and (not (self.treatment or "").strip() or not (self.outcome or "").strip()):
            raise ValueError("causal profile requires both treatment and outcome")
        if self.profile == "investigation" and (self.treatment or self.outcome):
            raise ValueError("investigation profile must not set treatment/outcome (estimand is causal-only)")
        return self
```

Then add the two fields to `PatchDefinitionEntity` (after `excludes`) plus a coherence validator:

```python
    patch_type: Literal["neighborhood", "inquiry"] = "neighborhood"
    inquiry: InquiryProfile | None = None

    @model_validator(mode="after")
    def _inquiry_block_coherence(self) -> "PatchDefinitionEntity":
        if self.patch_type == "inquiry" and self.inquiry is None:
            raise ValueError("patch_type 'inquiry' requires an inquiry block")
        if self.patch_type != "inquiry" and self.inquiry is not None:
            raise ValueError("inquiry block is only allowed when patch_type is 'inquiry'")
        return self
```

- [ ] **Step 4: Export the new public symbols**

In `science/model/src/science_model/__init__.py`, extend the existing `from science_model.patch_definition import (...)` block to also import and re-export `InquiryProfile`, `BoundaryRole`, `FlowEdge`, `Assumption`, `Transformation`, `Param`. Add the names to `__all__` if one is present (match the existing style).

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd science && uv run --frozen pytest model/tests/test_inquiry_profile.py model/tests/test_patch_definition.py -v`
Expected: PASS (new file all green; existing patch-definition tests still green).

- [ ] **Step 6: Commit** (from the worktree root)

```bash
git add science/model/src/science_model/patch_definition.py science/model/src/science_model/__init__.py science/model/tests/test_inquiry_profile.py
git commit -m "feat(model): add patch_type + InquiryProfile to PatchDefinition"
```

---

## Task 2: Inquiry-view compiler (pure emitter)

Emits the legacy-equivalent `sci:Inquiry` triples into a dedicated named graph whose identifier equals `PROJECT_NS["inquiry/<slug>"]` — the exact layout `_discover_inquiries`/`get_inquiry`/`export_pgmpy` require (design §4). Three reader-compatibility details verified against the code, **do not get these wrong**:

1. **Claim-backed flow edges** are read via `_edge_claims` (`graph/store/identity.py`): a reified `rdf:Statement` node carrying `rdf:subject`/`rdf:predicate`/`rdf:object` plus `sci:backedByClaim` *on the statement* — NOT `sci:backedByClaim` on the edge subject.
2. **Assumption provenance** is validated via `prov:wasDerivedFrom` in `graph/provenance` (or `graph/knowledge`) — `graph/store/inquiry.py` `provenance_completeness`. Emit it there, not as `sci:assumes` in the inquiry graph.
3. **Origins split:** boundary/flow/estimand refs are *existing project entities* (Task 3 hard-errors if unresolved); assumption/transformation nodes are *compiler-minted* and always typed.

**Files:**
- Create: `science/src/science_tool/graph/inquiry_compile.py`
- Test: `science/tests/test_inquiry_compile.py`

- [ ] **Step 1: Write the failing tests**

Create `science/tests/test_inquiry_compile.py`:

```python
from rdflib import Dataset, RDF, URIRef
from rdflib.namespace import PROV, SKOS

from science_model.patch_definition import PatchDefinitionEntity
from science_tool.graph.inquiry_compile import (
    emit_inquiry_views,
    inquiry_existing_refs,
    inquiry_minted_uris,
)
from science_tool.graph.io import PROJECT_NS, SCI_NS


def _inquiry_def(slug="i01-flow", **inquiry):
    return PatchDefinitionEntity(
        id=f"patch-definition:{slug}",
        title="Flow",
        focal="hypothesis:h01",
        scope_set=[{"scope": "local"}],
        neighborhood_policy={},
        patch_type="inquiry",
        inquiry={"profile": "investigation", "status": "specified", **inquiry},
    )


def test_emits_dedicated_inquiry_graph_with_core_metadata():
    ds = Dataset()
    emit_inquiry_views(ds, [_inquiry_def()])
    iu = URIRef(PROJECT_NS["inquiry/i01-flow"])
    g = ds.graph(iu)
    focal = URIRef(PROJECT_NS["hypothesis/h01"])
    assert (iu, RDF.type, SCI_NS.Inquiry) in g
    assert (iu, SCI_NS.target, focal) in g          # legacy reader vocab
    assert (iu, SCI_NS.focalEntity, focal) in g      # patch vocab
    assert str(g.identifier) == str(iu)              # graph id == inquiry uri (required by readers)


def test_investigation_maps_to_general_inquiry_type():
    ds = Dataset()
    emit_inquiry_views(ds, [_inquiry_def()])
    iu = URIRef(PROJECT_NS["inquiry/i01-flow"])
    g = ds.graph(iu)
    assert next(g.objects(iu, SCI_NS.inquiryType)).toPython() == "general"


def test_causal_emits_treatment_outcome_and_causal_type():
    ds = Dataset()
    ent = PatchDefinitionEntity(
        id="patch-definition:i02-causal", title="Causal", focal="hypothesis:h01",
        scope_set=[{"scope": "local"}], neighborhood_policy={}, patch_type="inquiry",
        inquiry={"profile": "causal", "status": "specified", "treatment": "concept:drug", "outcome": "concept:recovery"},
    )
    emit_inquiry_views(ds, [ent])
    iu = URIRef(PROJECT_NS["inquiry/i02-causal"])
    g = ds.graph(iu)
    assert next(g.objects(iu, SCI_NS.inquiryType)).toPython() == "causal"
    assert (iu, SCI_NS.treatment, URIRef(PROJECT_NS["concept/drug"])) in g
    assert (iu, SCI_NS.outcome, URIRef(PROJECT_NS["concept/recovery"])) in g


def test_boundary_and_flow_edges_emitted():
    ds = Dataset()
    ent = _inquiry_def(
        boundary_roles=[{"ref": "concept:x", "role": "BoundaryIn"}, {"ref": "concept:y", "role": "BoundaryOut"}],
        flow_edges=[{"subject": "concept:x", "predicate": "feedsInto", "object": "concept:y"}],
    )
    emit_inquiry_views(ds, [ent])
    g = ds.graph(URIRef(PROJECT_NS["inquiry/i01-flow"]))
    assert (URIRef(PROJECT_NS["concept/x"]), SCI_NS.boundaryRole, SCI_NS.BoundaryIn) in g
    assert (URIRef(PROJECT_NS["concept/y"]), SCI_NS.boundaryRole, SCI_NS.BoundaryOut) in g
    assert (URIRef(PROJECT_NS["concept/x"]), SCI_NS.feedsInto, URIRef(PROJECT_NS["concept/y"])) in g


def test_flow_edge_claims_emitted_as_reified_statement():
    # Reader contract: a Statement node with rdf:subject/predicate/object + sci:backedByClaim
    ds = Dataset()
    ent = _inquiry_def(
        flow_edges=[{"subject": "concept:x", "predicate": "feedsInto", "object": "concept:y",
                     "claim_refs": ["proposition:p1"]}],
    )
    emit_inquiry_views(ds, [ent])
    g = ds.graph(URIRef(PROJECT_NS["inquiry/i01-flow"]))
    s = URIRef(PROJECT_NS["concept/x"])
    stmts = [st for st in g.subjects(RDF.subject, s) if (st, RDF.object, URIRef(PROJECT_NS["concept/y"])) in g]
    assert stmts, "expected a reified rdf:Statement for the flow edge"
    claims = list(g.objects(stmts[0], SCI_NS.backedByClaim))
    assert URIRef(PROJECT_NS["proposition/p1"]) in claims


def test_assumption_minted_typed_with_provenance():
    ds = Dataset()
    ent = _inquiry_def(assumptions=[{"ref": "assumption:a1", "statement": "iid", "derived_from": "paper:doi_x"}])
    emit_inquiry_views(ds, [ent])
    g = ds.graph(URIRef(PROJECT_NS["inquiry/i01-flow"]))
    prov = ds.graph(URIRef(PROJECT_NS["graph/provenance"]))
    nodes = list(g.subjects(RDF.type, SCI_NS.Assumption))
    assert len(nodes) == 1
    # provenance lands where validate_inquiry reads it
    assert (nodes[0], PROV.wasDerivedFrom, URIRef(PROJECT_NS["paper/doi_x"])) in prov


def test_transformation_and_unknowns_emitted():
    ds = Dataset()
    ent = _inquiry_def(
        transformations=[{"ref": "transformation:t1", "tool": "pandas", "params": [{"value": "0.5", "source": "prior"}]}],
        unknowns=["concept:z"],
    )
    emit_inquiry_views(ds, [ent])
    g = ds.graph(URIRef(PROJECT_NS["inquiry/i01-flow"]))
    tnodes = list(g.subjects(RDF.type, SCI_NS.Transformation))
    assert len(tnodes) == 1
    assert (tnodes[0], SCI_NS.tool, None) in {(s, p, None) for s, p, _ in g}
    assert (tnodes[0], SCI_NS.paramValue, None) in {(s, p, None) for s, p, _ in g}
    assert (URIRef(PROJECT_NS["concept/z"]), RDF.type, SCI_NS.Unknown) in g


def test_get_inquiry_does_not_treat_focalentity_as_edge(tmp_path):
    # sci:focalEntity is patch vocab on the inquiry node; readers must not list it as a flow edge.
    from science_tool.graph.store.inquiry import get_inquiry

    ds = Dataset()
    emit_inquiry_views(
        ds, [_inquiry_def(flow_edges=[{"subject": "concept:x", "predicate": "feedsInto", "object": "concept:y"}])]
    )
    trig = tmp_path / "graph.trig"
    ds.serialize(destination=str(trig), format="trig")
    info = get_inquiry(trig, "i01-flow")
    preds = {e["predicate"] for e in info["edges"]}
    assert not any("focalEntity" in p for p in preds)
    assert any("feedsInto" in p for p in preds)


def test_origin_helpers_split_existing_and_minted():
    ent = _inquiry_def(
        boundary_roles=[{"ref": "concept:x", "role": "BoundaryIn"}],
        flow_edges=[{"subject": "concept:x", "predicate": "feedsInto", "object": "concept:y",
                     "claim_refs": ["proposition:p1"]}],
        assumptions=[{"ref": "assumption:a1", "statement": "iid"}],
    )
    existing = set(inquiry_existing_refs(ent))
    minted = set(inquiry_minted_uris(ent))
    assert {"concept:x", "concept:y", "proposition:p1"} <= existing  # backing claims are origins too
    assert any("assumption" in str(u) for u in minted)


def test_non_inquiry_definitions_emit_nothing():
    ds = Dataset()
    plain = PatchDefinitionEntity(
        id="patch-definition:plain", title="Plain", focal="hypothesis:h01",
        scope_set=[{"scope": "local"}], neighborhood_policy={},
    )
    emit_inquiry_views(ds, [plain])
    assert len(list(ds.graph(URIRef(PROJECT_NS["inquiry/plain"])))) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science && uv run --frozen pytest tests/test_inquiry_compile.py -v`
Expected: FAIL — module `inquiry_compile` does not exist.

- [ ] **Step 3: Implement the emitter**

Create `science/src/science_tool/graph/inquiry_compile.py`:

```python
"""Compile authored inquiry profiles into legacy-equivalent sci:Inquiry views.

A PatchDefinition with patch_type == "inquiry" authors an `inquiry:` block.
This module renders that block into a dedicated named graph whose identifier
equals the inquiry URI `PROJECT_NS["inquiry/<slug>"]` — the layout the existing
inquiry readers (`graph/store/inquiry.py`, `causal/export_pgmpy.py`) require.
Pure: mutates the provided Dataset in memory, never writes files.
"""

from __future__ import annotations

import hashlib

from rdflib import Dataset, Graph, Literal as RDFLiteral, URIRef
from rdflib.namespace import PROV, RDF, SKOS

from science_model.patch_definition import InquiryProfile, PatchDefinitionEntity
from science_tool.graph.io import DCTERMS_NS, PROJECT_NS, SCI_NS, SCIC_NS, entity_uri_for_ref

_PROFILE_TO_INQUIRY_TYPE = {"investigation": "general", "causal": "causal"}
_FLOW_PREDICATE = {"feedsInto": SCI_NS.feedsInto, "produces": SCI_NS.produces, "causes": SCIC_NS.causes}
_BOUNDARY_ROLE = {"BoundaryIn": SCI_NS.BoundaryIn, "BoundaryOut": SCI_NS.BoundaryOut}


def inquiry_slug(definition: PatchDefinitionEntity) -> str:
    """The inquiry/patch slug — the local part of the patch-definition id."""
    return definition.canonical_id.split(":", 1)[-1]


def inquiry_uri(definition: PatchDefinitionEntity) -> URIRef:
    return URIRef(PROJECT_NS[f"inquiry/{inquiry_slug(definition)}"])


def _node_uri(definition: PatchDefinitionEntity, kind: str, ref: str) -> URIRef:
    """Deterministic URI for an inquiry-internal minted node (assumption / transformation)."""
    local = ref.split(":", 1)[-1].lower()
    return URIRef(PROJECT_NS[f"inquiry/{inquiry_slug(definition)}/{kind}/{local}"])


def inquiry_existing_refs(definition: PatchDefinitionEntity) -> list[str]:
    """Refs the inquiry block contributes that MUST resolve to existing entities.

    Boundary nodes, flow-edge endpoints, flow-edge backing claims (propositions),
    treatment, outcome. The deriver hard-errors any of these that do not resolve
    (design §3) and records them as members with derivationReason "inquiry".
    """
    prof = definition.inquiry
    if prof is None:
        return []
    refs: list[str] = []
    for b in prof.boundary_roles:
        refs.append(b.ref)
    for e in prof.flow_edges:
        refs.append(e.subject)
        refs.append(e.object)
        refs.extend(e.claim_refs)  # propositions backing a flow edge are members too
    if prof.treatment:
        refs.append(prof.treatment)
    if prof.outcome:
        refs.append(prof.outcome)
    return sorted(dict.fromkeys(refs))  # de-dup, stable


def inquiry_minted_uris(definition: PatchDefinitionEntity) -> list[URIRef]:
    """Compiler-minted assumption/transformation node URIs (always typed by the emitter)."""
    prof = definition.inquiry
    if prof is None:
        return []
    uris = [_node_uri(definition, "assumption", a.ref) for a in prof.assumptions]
    uris += [_node_uri(definition, "transformation", t.ref) for t in prof.transformations]
    return sorted(set(uris), key=str)


def emit_inquiry_views(dataset: Dataset, patch_definitions: list[PatchDefinitionEntity]) -> None:
    for definition in sorted(patch_definitions, key=lambda d: d.canonical_id):
        if definition.patch_type != "inquiry" or definition.inquiry is None:
            continue
        _emit_one(dataset, definition, definition.inquiry)


def _emit_one(dataset: Dataset, definition: PatchDefinitionEntity, prof: InquiryProfile) -> None:
    iu = inquiry_uri(definition)
    g: Graph = dataset.graph(iu)
    provenance: Graph = dataset.graph(PROJECT_NS["graph/provenance"])
    focal = entity_uri_for_ref(definition.focal)

    g.add((iu, RDF.type, SCI_NS.Inquiry))
    g.add((iu, SKOS.prefLabel, RDFLiteral(definition.title or inquiry_slug(definition))))
    g.add((iu, SCI_NS.inquiryStatus, RDFLiteral(prof.status)))
    g.add((iu, SCI_NS.inquiryType, RDFLiteral(_PROFILE_TO_INQUIRY_TYPE[prof.profile])))
    g.add((iu, SCI_NS.target, focal))
    g.add((iu, SCI_NS.focalEntity, focal))
    if definition.created:
        g.add((iu, DCTERMS_NS.created, RDFLiteral(definition.created)))

    for b in prof.boundary_roles:
        g.add((entity_uri_for_ref(b.ref), SCI_NS.boundaryRole, _BOUNDARY_ROLE[b.role]))

    for e in prof.flow_edges:
        s = entity_uri_for_ref(e.subject)
        pred = _FLOW_PREDICATE[e.predicate]
        o = entity_uri_for_ref(e.object)
        g.add((s, pred, o))
        if e.claim_refs:
            _emit_edge_claims(g, iu, s, pred, o, e.claim_refs)

    if prof.treatment:
        g.add((iu, SCI_NS.treatment, entity_uri_for_ref(prof.treatment)))
    if prof.outcome:
        g.add((iu, SCI_NS.outcome, entity_uri_for_ref(prof.outcome)))

    for a in prof.assumptions:
        node = _node_uri(definition, "assumption", a.ref)
        g.add((node, RDF.type, SCI_NS.Assumption))
        g.add((node, SKOS.prefLabel, RDFLiteral(a.statement)))
        if a.derived_from:
            # validate_inquiry's provenance_completeness reads prov:wasDerivedFrom
            # from graph/provenance (or knowledge).
            provenance.add((node, PROV.wasDerivedFrom, entity_uri_for_ref(a.derived_from)))

    for t in prof.transformations:
        node = _node_uri(definition, "transformation", t.ref)
        g.add((node, RDF.type, SCI_NS.Transformation))
        if t.tool:
            g.add((node, SCI_NS.tool, RDFLiteral(t.tool)))
        if t.validated_by:
            g.add((node, SCI_NS.validatedBy, entity_uri_for_ref(t.validated_by)))
        for p in t.params:
            g.add((node, SCI_NS.paramValue, RDFLiteral(p.value)))
            if p.source:
                g.add((node, SCI_NS.paramSource, RDFLiteral(p.source)))
            if p.ref:
                g.add((node, SCI_NS.paramRef, RDFLiteral(p.ref)))
            if p.note:
                g.add((node, SCI_NS.paramNote, RDFLiteral(p.note)))

    for unknown in prof.unknowns:
        g.add((entity_uri_for_ref(unknown), RDF.type, SCI_NS.Unknown))


def _emit_edge_claims(
    g: Graph, inquiry: URIRef, subject: URIRef, predicate: URIRef, obj: URIRef, claim_refs: list[str]
) -> None:
    """Reify the edge as an rdf:Statement and attach backing claims.

    Matches the shape `graph/store/identity.py::_edge_claims` reads. The claim is
    a proposition reference; full subject/predicate/object cross-validation against
    the proposition (as the interactive mutator did) is deferred — see plan §11.
    """
    key = f"{inquiry}\x00{subject}\x00{predicate}\x00{obj}"
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
    statement = URIRef(PROJECT_NS[f"inquiry-edge/{digest}"])
    g.add((statement, RDF.type, RDF.Statement))
    g.add((statement, RDF.subject, subject))
    g.add((statement, RDF.predicate, predicate))
    g.add((statement, RDF.object, obj))
    for claim in dict.fromkeys(claim_refs):
        g.add((statement, SCI_NS.backedByClaim, entity_uri_for_ref(claim)))
```

> `SCI_NS.tool` / `SCI_NS.validatedBy` / `SCI_NS.backedByClaim` / `SCI_NS.boundaryRole` / `SCI_NS.feedsInto` etc. are all already used by `graph/store/inquiry.py` and `mutations.py`; reuse them verbatim. `SCIC_NS` (causal) is imported for `causes` flow edges.

**Required reader change (the one exception to "zero reader changes"):** the emitter writes `(inquiry, sci:focalEntity, focal)` onto the inquiry node, but `get_inquiry` builds its edge list by iterating every triple whose predicate is *not* in a `metadata_predicates` exclusion set (`graph/store/inquiry.py` ~line 126). `SCI_NS.focalEntity` is not in that set, so it would surface as a bogus flow edge (and Task 5 `import` would then render `predicate: focalEntity` and fail model validation). Add `SCI_NS.focalEntity` to that `metadata_predicates` set:

```python
        metadata_predicates = {
            RDF.type,
            RDF.subject,
            RDF.predicate,
            RDF.object,
            SKOS.prefLabel,
            SKOS.note,
            SKOS.related,
            SCI_NS.inquiryStatus,
            SCI_NS.inquiryType,
            SCI_NS.projectStatus,
            SCI_NS.target,
            SCI_NS.focalEntity,   # <-- add: patch vocab on the inquiry node, not a flow edge
            SCI_NS.boundaryRole,
            SCI_NS.treatment,
            SCI_NS.outcome,
            SCI_NS.tool,
            SCI_NS.paramValue,
            SCI_NS.paramSource,
            SCI_NS.paramNote,
            SCI_NS.paramRef,
            SCI_NS.backedByClaim,
            SCI_NS.validatedBy,
            DCTERMS_NS.created,
        }
```

(`test_get_inquiry_does_not_treat_focalentity_as_edge` covers this.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_inquiry_compile.py -v`
Expected: PASS.

- [ ] **Step 5: Commit** (from the worktree root)

```bash
git add science/src/science_tool/graph/inquiry_compile.py science/src/science_tool/graph/store/inquiry.py science/tests/test_inquiry_compile.py
git commit -m "feat(graph): compile inquiry profiles into legacy sci:Inquiry views"
```

---

## Task 3: Deriver — inquiry origins as members

Add `derivationReason = "inquiry"`. Existing refs (boundary/flow/estimand) MUST resolve — hard error via `_resolve_required`. Minted nodes (assumption/transformation) resolve `memberKind` from `rdf:type`, present because Task 4 emits the view *before* derivation.

**Files:**
- Modify: `science/src/science_tool/graph/patch_membership.py`
- Test: `science/tests/test_patch_membership_deriver.py` (add)

- [ ] **Step 1: Write the failing tests**

Append to `science/tests/test_patch_membership_deriver.py`:

```python
def test_inquiry_existing_refs_and_minted_nodes_become_members():
    from rdflib import Dataset, RDF, URIRef
    from science_model.patch_definition import PatchDefinitionEntity
    from science_tool.graph.inquiry_compile import emit_inquiry_views
    from science_tool.graph.io import PROJECT_NS, SCI_NS
    from science_tool.graph.patch_membership import derive_patch_memberships

    ds = Dataset()
    g = ds.graph(URIRef(PROJECT_NS["graph/knowledge"]))
    g.add((URIRef(PROJECT_NS["hypothesis/h01"]), RDF.type, SCI_NS.Hypothesis))
    g.add((URIRef(PROJECT_NS["concept/x"]), RDF.type, SCI_NS.Concept))
    g.add((URIRef(PROJECT_NS["concept/y"]), RDF.type, SCI_NS.Concept))
    g.add((URIRef(PROJECT_NS["proposition/p1"]), RDF.type, SCI_NS.Proposition))

    ent = PatchDefinitionEntity(
        id="patch-definition:i01", title="I", focal="hypothesis:h01",
        scope_set=[{"scope": "local"}], neighborhood_policy={}, patch_type="inquiry",
        inquiry={"profile": "investigation", "status": "sketch",
                 "boundary_roles": [{"ref": "concept:x", "role": "BoundaryIn"}],
                 "flow_edges": [{"subject": "concept:x", "predicate": "feedsInto",
                                 "object": "concept:y", "claim_refs": ["proposition:p1"]}],
                 "assumptions": [{"ref": "assumption:a1", "statement": "iid"}]},
    )
    emit_inquiry_views(ds, [ent])  # view first → minted assumption node typed
    result = derive_patch_memberships(ds, [ent], policy_version="local-closure-v1")

    by_member = {str(r.member): r for r in result.records}
    assert by_member[str(URIRef(PROJECT_NS["concept/x"]))].derivation_reason == "inquiry"
    # a proposition explicitly backing a flow edge is a member, not left to closure chance
    assert by_member[str(URIRef(PROJECT_NS["proposition/p1"]))].derivation_reason == "inquiry"
    assum = next(r for m, r in by_member.items() if "assumption" in m)
    assert assum.derivation_reason == "inquiry"
    assert assum.member_kind == "assumption"  # not "unknown" — ordering guard


def test_unresolved_inquiry_boundary_ref_is_hard_error():
    import pytest
    from rdflib import Dataset, RDF, URIRef
    from science_model.patch_definition import PatchDefinitionEntity
    from science_tool.graph.inquiry_compile import emit_inquiry_views
    from science_tool.graph.io import PROJECT_NS, SCI_NS
    from science_tool.graph.patch_membership import PatchMembershipError, derive_patch_memberships

    ds = Dataset()
    g = ds.graph(URIRef(PROJECT_NS["graph/knowledge"]))
    g.add((URIRef(PROJECT_NS["hypothesis/h01"]), RDF.type, SCI_NS.Hypothesis))
    ent = PatchDefinitionEntity(
        id="patch-definition:i02", title="I", focal="hypothesis:h01",
        scope_set=[{"scope": "local"}], neighborhood_policy={}, patch_type="inquiry",
        inquiry={"profile": "investigation", "status": "sketch",
                 "boundary_roles": [{"ref": "concept:ghost", "role": "BoundaryIn"}]},
    )
    emit_inquiry_views(ds, [ent])
    with pytest.raises(PatchMembershipError, match="unresolved inquiry"):
        derive_patch_memberships(ds, [ent], policy_version="local-closure-v1")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science && uv run --frozen pytest tests/test_patch_membership_deriver.py -k inquiry -v`
Expected: FAIL — `"inquiry"` not a valid reason / no hard error.

- [ ] **Step 3: Implement**

In `science/src/science_tool/graph/patch_membership.py`:

1. Extend the reason type and add the imports at the top (top-level import is safe — `inquiry_compile` imports only from `io` and `science_model`):

```python
DerivationReason = Literal["focal", "seed", "closure", "direct_relation", "inquiry"]
```

```python
from science_tool.graph.inquiry_compile import inquiry_existing_refs, inquiry_minted_uris
```

2. Update the sort order so `inquiry` (authored, depth 0) ranks just after seeds:

```python
def _record_sort_key(record: MembershipRecord) -> tuple[int, int, str]:
    reason_order = {"focal": 0, "seed": 1, "inquiry": 2, "closure": 3, "direct_relation": 4}
    return (
        record.depth,
        reason_order[record.derivation_reason],
        str(record.derivation_predicate or ""),
    )
```

3. In `derive_patch_memberships`, immediately after the `for seed_uri in seed_uris:` loop and before `origins = [focal_uri, *seed_uris]`, add inquiry origins. Existing refs hard-error; minted nodes are skipped only if (defensively) untyped:

```python
        inquiry_uris: list[URIRef] = []
        if definition.patch_type == "inquiry":
            for ref in inquiry_existing_refs(definition):
                member_uri = _resolve_required(
                    dataset, ref, label="inquiry", patch_id=definition.canonical_id
                )
                inquiry_uris.append(member_uri)
                _put_record(
                    by_member,
                    MembershipRecord(
                        patch=patch_uri,
                        patch_id=definition.canonical_id,
                        member=member_uri,
                        member_role="member",
                        member_kind=_member_kind(dataset, member_uri),
                        derivation_reason="inquiry",
                        depth=0,
                        policy_version=policy_version,
                        build_id=build_id,
                    ),
                )
            for member_uri in inquiry_minted_uris(definition):
                member_kind = _member_kind(dataset, member_uri)
                if member_kind == "unknown":
                    continue  # emitter always types these; defensive only
                inquiry_uris.append(member_uri)
                _put_record(
                    by_member,
                    MembershipRecord(
                        patch=patch_uri,
                        patch_id=definition.canonical_id,
                        member=member_uri,
                        member_role="member",
                        member_kind=member_kind,
                        derivation_reason="inquiry",
                        depth=0,
                        policy_version=policy_version,
                        build_id=build_id,
                    ),
                )
```

4. Include inquiry origins in the closure/direct-relation expansion set:

```python
        origins = [focal_uri, *seed_uris, *inquiry_uris]
```

> Note: `_resolve_required` raises `PatchMembershipError(f"{patch_id}: unresolved {label} {ref!r}")` — the test matches `"unresolved inquiry"`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_patch_membership_deriver.py -v`
Expected: PASS (new tests + all existing deriver tests).

- [ ] **Step 5: Commit** (from the worktree root)

```bash
git add science/src/science_tool/graph/patch_membership.py science/tests/test_patch_membership_deriver.py
git commit -m "feat(graph): derive inquiry-block entities as patch members (hard-error unresolved refs)"
```

---

## Task 4: Materialization wiring (view before derivation)

**Files:**
- Modify: `science/src/science_tool/graph/materialize.py` (`_derive_patch_membership_layer`, ~line 1260)
- Test: `science/tests/test_inquiry_patch_materialize.py`

- [ ] **Step 1: Write the failing test** (real `materialize_graph`, copied from `test_patch_membership_materialize.py`)

Create `science/tests/test_inquiry_patch_materialize.py`:

```python
from __future__ import annotations

from pathlib import Path

from rdflib import Dataset, URIRef
from rdflib.namespace import RDF

from science_tool.graph.io import PROJECT_NS, SCI_NS
from science_tool.graph.materialize import materialize_graph


def _write_entity(path: Path, frontmatter: list[str], body: str = "Body.") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(["---", *frontmatter, "---", "", body, ""]), encoding="utf-8")


def test_graph_build_emits_inquiry_view_and_membership(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text("name: demo\n", encoding="utf-8")
    _write_entity(
        tmp_path / "entities" / "hypotheses" / "h1.md",
        ['id: "hypothesis:h1"', 'type: "hypothesis"', 'title: "H1"', 'status: "proposed"',
         "ontology_terms: []", "source_refs: []", "related: []"],
    )
    _write_entity(
        tmp_path / "entities" / "concepts" / "x.md",
        ['id: "concept:x"', 'type: "concept"', 'title: "X"', 'status: "active"',
         "ontology_terms: []", "source_refs: []", "related: []"],
    )
    _write_entity(
        tmp_path / "entities" / "patches" / "i1.md",
        ['id: "patch-definition:i1"', 'type: "patch-definition"', 'title: "Inquiry one"',
         'status: "active"', "ontology_terms: []", "source_refs: []", "related: []",
         'focal: "hypothesis:h1"',
         "scope_set:", '  - scope: "local"',
         "neighborhood_policy:", '  name: "local-closure-v1"', '  version: "local-closure-v1"', "  max_depth: 2",
         "patch_type: inquiry",
         "inquiry:", "  profile: investigation", "  status: sketch",
         "  boundary_roles:", "    - ref: \"concept:x\"", "      role: BoundaryIn"],
    )

    trig_path = materialize_graph(tmp_path, strict=False)
    ds = Dataset()
    ds.parse(str(trig_path), format="trig")

    inquiry_uri = URIRef(PROJECT_NS["inquiry/i1"])
    assert (inquiry_uri, RDF.type, SCI_NS.Inquiry) in ds.graph(inquiry_uri)          # view emitted
    assert (URIRef(PROJECT_NS["concept/x"]), SCI_NS.boundaryRole, SCI_NS.BoundaryIn) in ds.graph(inquiry_uri)

    patch_uri = URIRef(PROJECT_NS["patch-definition/i1"])
    patch_graph = ds.graph(patch_uri)
    assert (patch_uri, RDF.type, SCI_NS.EpistemicPatch) in patch_graph               # membership context
    # concept:x is a member via derivationReason "inquiry"
    members = {str(o) for o in patch_graph.objects(patch_uri, SCI_NS.hasMember)}
    assert str(URIRef(PROJECT_NS["concept/x"])) in members
```

> If `concept` is not a recognized entity kind in this codebase, the implementer substitutes a kind that is (e.g. `proposition`) for `concept:x`, keeping the boundary ref pointing at it. Verify the kind list in `science/src/science_tool/entities.py` / `science_model` before finalizing the fixture.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_inquiry_patch_materialize.py -v`
Expected: FAIL — no `sci:Inquiry` triple emitted during build.

- [ ] **Step 3: Implement**

In `science/src/science_tool/graph/materialize.py`, add the import near the other graph imports:

```python
from science_tool.graph.inquiry_compile import emit_inquiry_views
```

Update `_derive_patch_membership_layer` to emit views **before** deriving:

```python
def _derive_patch_membership_layer(dataset: Dataset, *, sources: ProjectSources) -> None:
    """Emit inquiry views, then derive per-patch PatchMembership named graphs.

    Inquiry views are emitted FIRST so minted assumption/transformation nodes
    carry rdf:type before the deriver resolves memberKind (design §3/§7). Runs
    after `_derive_bears_on_layer` because patch closure reads the bears-on layer.
    No-ops when no PatchDefinitionEntity is present.
    """
    patch_definitions = [
        entity for entity in sources.entities if isinstance(entity, PatchDefinitionEntity)
    ]
    if not patch_definitions:
        return
    emit_inquiry_views(dataset, patch_definitions)
    result = derive_patch_memberships(
        dataset,
        patch_definitions,
        policy_version=PATCH_MEMBERSHIP_POLICY_VERSION,
    )
    emit_patch_memberships(dataset, patch_definitions, result.records)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_inquiry_patch_materialize.py tests/test_patch_membership_materialize.py -v`
Expected: PASS.

- [ ] **Step 5: Commit** (from the worktree root)

```bash
git add science/src/science_tool/graph/materialize.py science/tests/test_inquiry_patch_materialize.py
git commit -m "feat(graph): emit inquiry views before membership derivation in build"
```

---

## Task 5: CLI rework — scaffold, import, retire mutators

**Files:**
- Modify: `science/src/science_tool/cli.py` (`inquiry` group, lines ~2676–2940)
- Test: `science/tests/test_inquiry_cli_subsumption.py`

- [ ] **Step 1: Write the failing tests**

Create `science/tests/test_inquiry_cli_subsumption.py`:

```python
from pathlib import Path

from click.testing import CliRunner

from science_model.patch_definition import PatchDefinitionEntity
from science_tool.cli import main


def test_init_investigation_scaffolds_markdown_and_writes_no_graph(tmp_path: Path):
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["inquiry", "init", "i01-demo", "--label", "Demo", "--target", "hypothesis:h01",
         "--profile", "investigation", "--project-root", str(tmp_path)],
    )
    assert result.exit_code == 0, result.output
    md = tmp_path / "entities" / "patches" / "i01-demo.md"
    assert md.exists()
    text = md.read_text()
    assert "patch_type: inquiry" in text
    assert "profile: investigation" in text
    assert not (tmp_path / "knowledge" / "graph.trig").exists()


def test_init_causal_requires_estimand(tmp_path: Path):
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["inquiry", "init", "i02", "--label", "C", "--target", "hypothesis:h01",
         "--profile", "causal", "--project-root", str(tmp_path)],
    )
    assert result.exit_code != 0
    assert "treatment" in result.output.lower() and "outcome" in result.output.lower()


def test_init_causal_scaffold_is_valid_when_estimand_given(tmp_path: Path):
    import yaml
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["inquiry", "init", "i03", "--label", "C", "--target", "hypothesis:h01",
         "--profile", "causal", "--treatment", "concept:drug", "--outcome", "concept:recovery",
         "--project-root", str(tmp_path)],
    )
    assert result.exit_code == 0, result.output
    text = (tmp_path / "entities" / "patches" / "i03.md").read_text()
    fm = yaml.safe_load(text.split("---")[1])
    # scaffold round-trips through the model (estimand present → valid causal profile)
    PatchDefinitionEntity(**fm)


def test_add_node_is_retired():
    result = CliRunner().invoke(main, ["inquiry", "add-node", "i01-demo", "concept:x"])
    assert result.exit_code != 0
    assert "retired" in result.output.lower() and "graph build" in result.output.lower()


def test_set_estimand_is_retired():
    result = CliRunner().invoke(
        main, ["inquiry", "set-estimand", "i01", "--treatment", "concept:a", "--outcome", "concept:b"]
    )
    assert result.exit_code != 0 and "retired" in result.output.lower()


def test_import_writes_source_and_refuses_overwrite(tmp_path: Path):
    # Build a graph.trig containing an inquiry via the compiler, then import it.
    from rdflib import Dataset
    from science_tool.graph.inquiry_compile import emit_inquiry_views

    ds = Dataset()
    ent = PatchDefinitionEntity(
        id="patch-definition:i09", title="Imported", focal="hypothesis:h01",
        scope_set=[{"scope": "local"}], neighborhood_policy={}, patch_type="inquiry",
        inquiry={"profile": "investigation", "status": "specified",
                 "boundary_roles": [{"ref": "concept:x", "role": "BoundaryIn"}],
                 "flow_edges": [{"subject": "concept:x", "predicate": "feedsInto",
                                 "object": "concept:y", "claim_refs": ["proposition:p1"]}]},
    )
    emit_inquiry_views(ds, [ent])
    graph_dir = tmp_path / "knowledge"
    graph_dir.mkdir(parents=True)
    trig = graph_dir / "graph.trig"
    ds.serialize(destination=str(trig), format="trig")

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["inquiry", "import", "i09", "--project-root", str(tmp_path), "--path", str(trig)],
    )
    assert result.exit_code == 0, result.output
    dest = tmp_path / "entities" / "patches" / "i09.md"
    assert dest.exists()
    import yaml
    fm = yaml.safe_load(dest.read_text().split("---")[1])
    loaded = PatchDefinitionEntity(**fm)          # round-trips through the model
    assert loaded.patch_type == "inquiry"
    assert loaded.inquiry.profile == "investigation"
    # authored backing claims survive graph -> source import
    assert loaded.inquiry.flow_edges[0].claim_refs == ["proposition:p1"]

    # second import refuses without --force
    again = runner.invoke(main, ["inquiry", "import", "i09", "--project-root", str(tmp_path), "--path", str(trig)])
    assert again.exit_code != 0 and "force" in again.output.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science && uv run --frozen pytest tests/test_inquiry_cli_subsumption.py -v`
Expected: FAIL — `--profile` unknown / `init` mutates graph / no `import` command / mutators still mutate.

- [ ] **Step 3: Add a shared frontmatter renderer + ref helper**

Add near the top of the `inquiry` group in `cli.py` (these back both `init` and `import`):

```python
def _ref_from_uri(value: str) -> str:
    """Best-effort reverse of entity_uri_for_ref for the import bridge."""
    from science_tool.graph.io import PROJECT_NS

    if value.startswith(str(PROJECT_NS)):
        local = value[len(str(PROJECT_NS)):]
        if "/" in local:
            kind, slug = local.split("/", 1)
            return f"{kind}:{slug}"
    return value


def _render_inquiry_source(
    slug: str,
    *,
    title: str,
    focal_ref: str,
    profile: str,
    status: str,
    boundary_roles: list[tuple[str, str]] = (),     # (ref, "BoundaryIn"|"BoundaryOut")
    flow_edges: list[tuple[str, str, str, list[str]]] = (),   # (subject_ref, predicate, object_ref, claim_refs)
    treatment_ref: str | None = None,
    outcome_ref: str | None = None,
) -> str:
    import yaml

    inquiry: dict = {"profile": profile, "status": status}
    inquiry["boundary_roles"] = [{"ref": r, "role": role} for r, role in boundary_roles]
    inquiry["flow_edges"] = [
        {"subject": s, "predicate": p, "object": o, "claim_refs": list(claims)}
        for s, p, o, claims in flow_edges
    ]
    inquiry["assumptions"] = []
    inquiry["transformations"] = []
    if profile == "causal":
        inquiry["treatment"] = treatment_ref or ""
        inquiry["outcome"] = outcome_ref or ""

    frontmatter = {
        "id": f"patch-definition:{slug}",
        "type": "patch-definition",
        "title": title,
        "status": "active",
        "focal": focal_ref,
        "scope_set": [{"scope": "local"}],
        "neighborhood_policy": {"name": "local-closure-v1", "version": "local-closure-v1", "max_depth": 2},
        "patch_type": "inquiry",
        "inquiry": inquiry,
    }
    body = f"# Inquiry: {title}\n\n<!-- Edit the `inquiry:` block above, then run `science graph build`. -->\n"
    return "---\n" + yaml.safe_dump(frontmatter, sort_keys=False) + "---\n\n" + body
```

- [ ] **Step 4: Rework `inquiry init` (require estimand for causal)**

Replace `inquiry_init` (cli.py ~2695):

```python
@inquiry.command("init")
@click.argument("slug")
@click.option("--label", required=True)
@click.option("--target", required=True, help="Focal hypothesis or question (e.g. hypothesis:h01)")
@click.option("--profile", required=True, type=click.Choice(["investigation", "causal"]))
@click.option("--status", default="sketch",
              type=click.Choice(["sketch", "specified", "planned", "in-progress", "complete"]))
@click.option("--treatment", default=None, help="Treatment ref (required for --profile causal)")
@click.option("--outcome", default=None, help="Outcome ref (required for --profile causal)")
@click.option("--project-root", "project_root", default=".", type=click.Path(path_type=Path, file_okay=False))
def inquiry_init(slug, label, target, profile, status, treatment, outcome, project_root):
    """Scaffold an inquiry patch-definition source file (does not write the graph)."""
    if profile == "causal" and (not treatment or not outcome):
        raise click.ClickException("causal profile requires --treatment and --outcome")
    dest = Path(project_root) / "entities" / "patches" / f"{slug}.md"
    if dest.exists():
        raise click.ClickException(f"{dest} already exists")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        _render_inquiry_source(
            slug, title=label, focal_ref=target, profile=profile, status=status,
            treatment_ref=treatment, outcome_ref=outcome,
        ),
        encoding="utf-8",
    )
    click.echo(f"Scaffolded {dest}")
```

- [ ] **Step 5: Add `inquiry import` bridge**

Add a new command. It reads the graph inquiry via `get_inquiry`, maps `inquiry_type` → profile, renders source via `_render_inquiry_source`, validates the result loads as `PatchDefinitionEntity`, and refuses to overwrite without `--force`:

```python
@inquiry.command("import")
@click.argument("slug")
@click.option("--project-root", "project_root", default=".", type=click.Path(path_type=Path, file_okay=False))
@click.option("--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), type=click.Path(path_type=Path))
@click.option("--force", is_flag=True, help="Overwrite an existing source file")
def inquiry_import(slug, project_root, graph_path, force):
    """Bridge: write a patch-definition source from an existing graph inquiry."""
    import yaml
    from science_model.patch_definition import PatchDefinitionEntity
    from science_tool.graph.store.inquiry import get_inquiry

    dest = Path(project_root) / "entities" / "patches" / f"{slug}.md"
    if dest.exists() and not force:
        raise click.ClickException(f"{dest} exists; pass --force to overwrite")

    info = get_inquiry(graph_path, slug)
    profile = "causal" if info.get("inquiry_type") == "causal" else "investigation"
    boundary = [(_ref_from_uri(u), "BoundaryIn") for u in info.get("boundary_in", [])]
    boundary += [(_ref_from_uri(u), "BoundaryOut") for u in info.get("boundary_out", [])]
    flows = [(_ref_from_uri(e["subject"]), _local_predicate(e["predicate"]), _ref_from_uri(e["object"]),
              [_ref_from_uri(c) for c in e.get("claims", [])])
             for e in info.get("edges", [])]
    text = _render_inquiry_source(
        slug,
        title=info.get("label") or slug,
        focal_ref=_ref_from_uri(info.get("target", "")),
        profile=profile,
        status=info.get("status") or "sketch",
        boundary_roles=boundary,
        flow_edges=flows,
        treatment_ref=_ref_from_uri(info["treatment"]) if info.get("treatment") else None,
        outcome_ref=_ref_from_uri(info["outcome"]) if info.get("outcome") else None,
    )
    # fail loudly if the bridge produced an invalid source
    PatchDefinitionEntity(**yaml.safe_load(text.split("---")[1]))
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text, encoding="utf-8")
    click.echo(f"Imported inquiry/{slug} -> {dest}")
```

Add the small predicate-localizer helper next to `_ref_from_uri`:

```python
def _local_predicate(value: str) -> str:
    """Map a flow-edge predicate URI back to the authored short name."""
    for short in ("feedsInto", "produces", "causes"):
        if value.endswith(short):
            return short
    return value.rsplit("/", 1)[-1].rsplit("#", 1)[-1]
```

> Limitation (acceptable for a near-zero-target bridge, noted in plan §11): `import` does not reconstruct assumptions/transformations (minted nodes are hard to reverse-map). The validation `PatchDefinitionEntity(**...)` guarantees the emitted source is loadable.

- [ ] **Step 6: Retire the five mutators**

Add a helper near the `inquiry` group:

```python
def _retired_mutator(slug: str) -> click.ClickException:
    return click.ClickException(
        f"Inquiry graph mutation is retired. Edit entities/patches/{slug}.md and run `science graph build`."
    )
```

Replace the bodies of `inquiry_add_node`, `inquiry_add_edge`, `inquiry_add_assumption`, `inquiry_add_transformation`, `inquiry_set_estimand` — keep each existing signature/decorators, body becomes:

```python
    raise _retired_mutator(slug)
```

Drop the now-unused imports of `add_inquiry`, `set_boundary_role`, `add_inquiry_node`, `add_inquiry_edge`, `add_assumption`, `add_transformation`, `set_treatment_outcome` from `cli.py` if nothing else references them. Leave `graph/store/mutations.py` itself untouched in this task.

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_inquiry_cli_subsumption.py -v`
Expected: PASS.

- [ ] **Step 8: Commit** (from the worktree root)

```bash
git add science/src/science_tool/cli.py science/tests/test_inquiry_cli_subsumption.py
git commit -m "feat(cli): inquiry init scaffold + import bridge; retire graph mutators"
```

---

## Task 6: Retire the legacy inquiry entity-kind template

The markdown `inquiry` entity kind (`templates/inquiry.md` + `"inquiry"` in `MIGRATED_KINDS`) is superseded by `patch_type: inquiry`. Remove it.

**Files:**
- Modify: `science/model/src/science_model/templates.py` (`MIGRATED_KINDS`, ~line 14)
- Delete: `science/model/src/science_model/templates/inquiry.md`

- [ ] **Step 1: Write the failing test**

Create `science/model/tests/test_inquiry_kind_retired.py`:

```python
from science_model.templates import MIGRATED_KINDS


def test_inquiry_is_no_longer_a_migrated_kind():
    assert "inquiry" not in MIGRATED_KINDS
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd science && uv run --frozen pytest model/tests/test_inquiry_kind_retired.py -v`
Expected: FAIL — `"inquiry"` still present.

- [ ] **Step 3: Remove the kind and template**

- In `science/model/src/science_model/templates.py`, delete the `"inquiry",` line from the `MIGRATED_KINDS` frozenset.
- Delete the file `science/model/src/science_model/templates/inquiry.md`.

- [ ] **Step 4: Find and fix fallout**

```bash
rtk rg -n "['\"]inquiry['\"]" science/model/src/science_model science/src/science_tool -g '*.py' \
  | rg -v -e inquiry_type -e 'inquiry/' -e inquiryStatus -e inquiryType -e store/inquiry -e graph.inquiry -e patch_type
```

For each hit that treats `inquiry` as an entity *kind* (a path-policy entry in `src/science_tool/entities.py`, a status-vocab entry, or a template-section lookup), remove or redirect it. If an `EntityType.INQUIRY` enum member exists and is referenced widely, leave the enum member but remove its template/`MIGRATED_KINDS` wiring — do not chase a broad enum removal here (note it as a follow-up).

- [ ] **Step 5: Run the model + entity suites**

Run: `cd science && uv run --frozen pytest model/tests/ tests/test_entities.py -v`
Expected: PASS (fix or remove any test asserting an `inquiry` template exists).

- [ ] **Step 6: Commit** (from the worktree root)

```bash
git add science/model/src/science_model/templates.py science/model/tests/test_inquiry_kind_retired.py
git rm science/model/src/science_model/templates/inquiry.md
git commit -m "chore(model): retire legacy inquiry entity-kind template"
```

---

## Task 7: Re-point existing inquiry tests; full-suite green

`science/tests/test_inquiry.py`, `test_inquiry_cli.py`, `test_inquiry_e2e.py` exercise the now-retired mutation path. Reader behavior (discover/get/validate/render/export) must stay covered via the compile path.

**Files:**
- Modify: `science/tests/test_inquiry.py`, `science/tests/test_inquiry_cli.py`, `science/tests/test_inquiry_e2e.py`

- [ ] **Step 1: Triage**

Run: `cd science && uv run --frozen pytest tests/test_inquiry.py tests/test_inquiry_cli.py tests/test_inquiry_e2e.py -v`

Categorize each failure:
- **Mutation tests** (call `add_inquiry`/`set_boundary_role`/CLI `add-*`): rewrite to build the graph via `emit_inquiry_views` over a `PatchDefinitionEntity`, then assert the same triples.
- **Reader tests** (`get_inquiry`/`validate_inquiry`/`list_inquiries`/`export_pgmpy`): keep assertions; change only the *setup* to produce the inquiry graph via `emit_inquiry_views` (serialize to a temp `graph.trig` for path-based readers, or use the `*_dataset` variants).
- **CLI `add-*` tests**: replace with retirement assertions (mirror Task 5) or delete if duplicated.

- [ ] **Step 2: Add a shared fixture in `test_inquiry.py`**

```python
def _build_inquiry_dataset(slug="i01", **inquiry):
    from rdflib import Dataset
    from science_model.patch_definition import PatchDefinitionEntity
    from science_tool.graph.inquiry_compile import emit_inquiry_views
    ds = Dataset()
    ent = PatchDefinitionEntity(
        id=f"patch-definition:{slug}", title="I", focal="hypothesis:h01",
        scope_set=[{"scope": "local"}], neighborhood_policy={},
        patch_type="inquiry", inquiry={"profile": "investigation", "status": "sketch", **inquiry},
    )
    emit_inquiry_views(ds, [ent])
    return ds, ent
```

For path-based readers, serialize `ds` to `tmp_path / "knowledge" / "graph.trig"` (mirror how existing reader tests load fixtures) and pass that path. For provenance/causal-dependent assertions, recall the compiler writes assumption provenance into `graph/provenance` and does **not** write into `graph/causal`.

- [ ] **Step 3: Run the inquiry suites green**

Run: `cd science && uv run --frozen pytest tests/test_inquiry.py tests/test_inquiry_cli.py tests/test_inquiry_e2e.py -v`
Expected: PASS.

- [ ] **Step 4: Full suite**

Run: `cd science && uv run --frozen pytest -q`
Expected: PASS (0 failures). Investigate any regression in patch/graph/validate suites.

- [ ] **Step 5: Lint**

Run: `cd science && uv run --frozen ruff format && uv run --frozen ruff check`
Expected: clean.

- [ ] **Step 6: Commit** (from the worktree root)

```bash
git add science/tests/test_inquiry.py science/tests/test_inquiry_cli.py science/tests/test_inquiry_e2e.py
git commit -m "test(inquiry): re-point inquiry tests onto the compile path"
```

---

## Final review

After all tasks: dispatch a holistic code reviewer over the full diff (the keystone's strongest catch came from a final holistic pass that narrow per-task reviews missed). Verify:

- The view is emitted **before** derivation in `materialize.py` (finding-2 guard) — a minted assumption node has `member_kind != "unknown"`.
- `inquiry/<slug>` graph identifier equals the inquiry URI (finding-1) — `get_inquiry`/`export_pgmpy` resolve it; run an `export-pgmpy` smoke test on a causal inquiry built via the compiler.
- Flow-edge claims emit a reified `rdf:Statement` (`_edge_claims` shape); `get_inquiry(...)["edges"][...]["claims"]` is populated.
- Assumption `derived_from` lands as `prov:wasDerivedFrom` in `graph/provenance`; a `specified` inquiry passes `validate_inquiry` `provenance_completeness`.
- No emission into `graph/causal` (finding-3) — causal acyclicity/identifiability validation still reads proposition-authored causal edges only.
- No `graph.trig` is written by any `science inquiry` command; causal `init` scaffolds a model-valid file.

Then use `superpowers:finishing-a-development-branch` to land it (keystone convention: merge to local `main`, no push, remove worktree, update memory).

---

## §11 Deferred (carried from design + tightened here)

- Flow-edge claim cross-validation (proposition subject/predicate/object must match the edge), as the interactive mutator enforced. The compiler emits the correct reified shape but does not re-validate the proposition triple; defer to a follow-up.
- `inquiry import` does not reconstruct assumptions/transformations (minted nodes are hard to reverse-map). Bridge has near-zero real targets.
- Granular inquiry derivation reasons; unifying causal-edge homes (`graph/causal` vs inquiry block) — Spec 5 concern.

---

## Self-review (plan vs. spec)

- **§2 model:** Task 1 ✓ (patch_type, InquiryProfile, nested models, estimand + coherence validators; `unknowns` added for the validator). 
- **§3 derivation (single `inquiry` reason; existing-ref hard-error; minted-node ordering):** Task 3 ✓ + Task 4 ordering ✓.
- **§4 compat views (dedicated `inquiry/<slug>` graph; `investigation→general`; `sci:target`+`sci:focalEntity`; reified claims; assumption provenance to `graph/provenance`):** Task 2 ✓ (all three reader-compat shapes corrected per review).
- **§5 validation:** model-level in Task 1; graph-level reader *surface* preserved with one metadata-predicate exclusion added (`sci:focalEntity` in `get_inquiry`, Task 2) + Task 7 re-point + Final review provenance/export smoke; no `graph/causal` emission asserted in Final review.
- **§6 CLI (init requires causal estimand; import round-trips through the model; retire mutators; read-only kept):** Task 5 ✓.
- **§10 migration + template cleanup:** Task 6 + Task 7 ✓.
- **Type consistency:** `emit_inquiry_views`, `inquiry_existing_refs`, `inquiry_minted_uris`, `inquiry_uri`, `_node_uri`, `_emit_edge_claims`, `_render_inquiry_source`, `_ref_from_uri`, `_local_predicate`, `derivation_reason="inquiry"` referenced consistently across Tasks 2–5.
- **Executability:** Task 4 uses real `materialize_graph` + temp markdown (no placeholder `ProjectSources`); Task 5 fully specifies `import` + `_render_inquiry_source` with happy-path/overwrite/round-trip tests.
- **Paths:** worktree-relative throughout; `~/d/` used in prose references.

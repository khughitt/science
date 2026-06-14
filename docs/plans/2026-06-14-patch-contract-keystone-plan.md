# Patch Contract Keystone Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement v1 patch definitions as authored source declarations whose derived memberships are emitted into the single project `graph.trig` artifact.

**Architecture:** Add `PatchDefinitionEntity` as the authored source model, then add a pure `graph.patch_membership` derivation module that reads an in-memory `rdflib.Dataset` and emits reified `sci:PatchMembership` records into patch named graphs. Wire that module into `materialize_graph` after `close_bears_on`, and add diagnostic `science patch explain` / `science patch check` commands that call the same derivation code without writing a second artifact.

**Tech Stack:** Python 3, Pydantic v2, rdflib `Dataset`, Click, pytest, existing `science_model` / `science_tool` packages.

---

## File Structure

- Create `science/model/src/science_model/patch_definition.py`
  - Owns `PatchDefinitionEntity`, `PatchScope`, `PatchExclude`, and `LocalClosurePolicy`.
  - Contains only source-model validation, no RDF or graph traversal.
- Modify `science/model/src/science_model/entities.py`
  - Add `EntityType.PATCH_DEFINITION`.
- Modify `science/model/src/science_model/__init__.py`
  - Export patch-definition model classes.
- Modify `science/src/science_tool/graph/entity_registry.py`
  - Register `patch-definition` as an epistemic core kind.
- Modify `science/src/science_tool/entities.py`
  - Add path policy and status vocabulary for `entities/patches/<slug>.md`.
- Create `science/src/science_tool/graph/patch_membership.py`
  - Owns pure derivation, patch-membership records, Dataset emission, and validation helpers.
  - No filesystem writes.
- Modify `science/src/science_tool/graph/materialize.py`
  - Call patch membership derivation after `_derive_bears_on_layer(...)`.
- Create `science/src/science_tool/patch/cli.py`
  - Owns diagnostic-only `patch explain` and `patch check`.
- Modify `science/src/science_tool/cli.py`
  - Register the patch CLI group.
- Add tests:
  - `science/model/tests/test_patch_definition.py`
  - `science/tests/test_patch_membership_deriver.py`
  - `science/tests/test_patch_membership_emission.py`
  - `science/tests/test_patch_membership_materialize.py`
  - `science/tests/test_patch_cli.py`

## Contract Decisions To Preserve

- Authored source-of-truth is `PatchDefinitionEntity`, never a member list.
- Derived source-of-truth in graph output is the reified `sci:PatchMembership` node.
- `sci:hasMember` and `sci:inPatch` are generated convenience edges; orphan convenience edges are invalid.
- `policy_version` is mandatory on every membership record.
- `build_id` is optional until `SourceSnapshot` exists.
- Patch derivation is part of `science graph build` / `/science:update-graph`, not an independent writer.
- CLI diagnostics must not write `graph.trig`.

---

### Task 1: PatchDefinition Entity Model And Kind Registration

**Files:**
- Create: `science/model/src/science_model/patch_definition.py`
- Modify: `science/model/src/science_model/entities.py`
- Modify: `science/model/src/science_model/__init__.py`
- Modify: `science/src/science_tool/graph/entity_registry.py`
- Modify: `science/src/science_tool/entities.py`
- Test: `science/model/tests/test_patch_definition.py`
- Test: `science/tests/test_entity_registry.py`

- [ ] **Step 1: Write model validation tests**

Create `science/model/tests/test_patch_definition.py`:

```python
from __future__ import annotations

import pytest
from pydantic import ValidationError

from science_model.patch_definition import (
    LocalClosurePolicy,
    PatchDefinitionEntity,
    PatchExclude,
    PatchScope,
)


def _base_patch(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "id": "patch-definition:apoptosis-mcl1",
        "canonical_id": "patch-definition:apoptosis-mcl1",
        "kind": "patch-definition",
        "type": "patch-definition",
        "title": "Apoptosis MCL1 patch",
        "status": "active",
        "project": "",
        "ontology_terms": [],
        "related": [],
        "source_refs": [],
        "content_preview": "",
        "file_path": "entities/patches/apoptosis-mcl1.md",
        "focal": "hypothesis:h01-apoptosis",
        "scope_set": [{"scope": "local"}],
        "neighborhood_policy": {
            "name": "local-closure-v1",
            "version": "local-closure-v1",
            "max_depth": 2,
        },
    }
    data.update(overrides)
    return data


def test_patch_definition_valid_minimal() -> None:
    entity = PatchDefinitionEntity.model_validate(_base_patch())

    assert entity.kind == "patch-definition"
    assert entity.focal == "hypothesis:h01-apoptosis"
    assert entity.scope_set == [PatchScope(scope="local")]
    assert entity.neighborhood_policy == LocalClosurePolicy()
    assert entity.seeds == []
    assert entity.excludes == []


def test_patch_definition_requires_focal() -> None:
    data = _base_patch()
    data.pop("focal")

    with pytest.raises(ValidationError, match="focal"):
        PatchDefinitionEntity.model_validate(data)


def test_patch_definition_rejects_non_local_scope() -> None:
    with pytest.raises(ValidationError, match="remote scopes deferred"):
        PatchDefinitionEntity.model_validate(
            _base_patch(scope_set=[{"scope": "commons", "ref": "commons"}])
        )


def test_patch_definition_rejects_empty_scope_set() -> None:
    with pytest.raises(ValidationError, match="scope_set"):
        PatchDefinitionEntity.model_validate(_base_patch(scope_set=[]))


def test_patch_definition_exclude_reason_required_and_nonempty() -> None:
    with pytest.raises(ValidationError, match="reason"):
        PatchDefinitionEntity.model_validate(
            _base_patch(excludes=[{"ref": "proposition:p1"}])
        )

    with pytest.raises(ValidationError, match="reason must be non-empty"):
        PatchExclude.model_validate({"ref": "proposition:p1", "reason": "  "})


def test_patch_definition_rejects_unknown_policy() -> None:
    with pytest.raises(ValidationError, match="Input should be 'local-closure-v1'"):
        PatchDefinitionEntity.model_validate(
            _base_patch(neighborhood_policy={"name": "latent-v1", "version": "latent-v1"})
        )


def test_patch_definition_rejects_invalid_max_depth() -> None:
    with pytest.raises(ValidationError, match="max_depth"):
        PatchDefinitionEntity.model_validate(
            _base_patch(
                neighborhood_policy={
                    "name": "local-closure-v1",
                    "version": "local-closure-v1",
                    "max_depth": 0,
                }
            )
        )
```

- [ ] **Step 2: Run model validation tests to verify they fail**

Run:

```bash
uv run --frozen pytest science/model/tests/test_patch_definition.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'science_model.patch_definition'`.

- [ ] **Step 3: Add the PatchDefinition model**

Create `science/model/src/science_model/patch_definition.py`:

```python
"""Authored patch-definition source model.

Patch membership is derived compiled state. This module owns only the authored
intent: focal target, local scope, derivation policy, seeds, and excludes.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from science_model.entities import EntityType, ProjectEntity


class PatchScope(BaseModel):
    """A future-shaped scope entry.

    v1 supports only the local project scope. The shape is explicit so later
    remote/commons scopes can extend it without replacing the field.
    """

    model_config = ConfigDict(extra="forbid")

    scope: Literal["local", "commons", "remote"] = "local"
    ref: str | None = None


class PatchExclude(BaseModel):
    """Authored curation constraint that suppresses a derived member."""

    model_config = ConfigDict(extra="forbid")

    ref: str
    reason: str

    @field_validator("ref", "reason")
    @classmethod
    def _non_empty(cls, value: str, info) -> str:  # type: ignore[no-untyped-def]
        if not value.strip():
            raise ValueError(f"{info.field_name} must be non-empty")
        return value


class LocalClosurePolicy(BaseModel):
    """The v1 local patch derivation policy."""

    model_config = ConfigDict(extra="forbid")

    name: Literal["local-closure-v1"] = "local-closure-v1"
    version: Literal["local-closure-v1"] = "local-closure-v1"
    max_depth: int = Field(default=2, ge=1)


class PatchDefinitionEntity(ProjectEntity):
    """Authored patch intent.

    The derived patch membership set is emitted during graph materialization;
    this entity never owns an authored member list.
    """

    kind: str = "patch-definition"
    type: Literal[EntityType.PATCH_DEFINITION] = EntityType.PATCH_DEFINITION  # type: ignore[assignment]

    focal: str
    scope_set: list[PatchScope] = Field(min_length=1)
    neighborhood_policy: LocalClosurePolicy
    seeds: list[str] = Field(default_factory=list)
    excludes: list[PatchExclude] = Field(default_factory=list)

    @field_validator("focal")
    @classmethod
    def _focal_non_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("focal must be non-empty")
        return value

    @field_validator("seeds")
    @classmethod
    def _seed_refs_non_empty(cls, values: list[str]) -> list[str]:
        for value in values:
            if not value.strip():
                raise ValueError("seed refs must be non-empty")
        return values

    @model_validator(mode="after")
    def _v1_local_scope_only(self) -> "PatchDefinitionEntity":
        non_local = [entry for entry in self.scope_set if entry.scope != "local"]
        if non_local:
            raise ValueError("remote scopes deferred to a later spec")
        return self
```

- [ ] **Step 4: Add EntityType and exports**

Modify `science/model/src/science_model/entities.py`:

```python
class EntityType(StrEnum):
    """Known entity types across Science projects."""

    CONCEPT = "concept"
    HYPOTHESIS = "hypothesis"
    QUESTION = "question"
    PROPOSITION = "proposition"
    PATCH_DEFINITION = "patch-definition"
    OBSERVATION = "observation"
```

Modify `science/model/src/science_model/__init__.py`:

```python
from science_model.patch_definition import (
    LocalClosurePolicy,
    PatchDefinitionEntity,
    PatchExclude,
    PatchScope,
)
```

Add these names to `__all__`:

```python
    "LocalClosurePolicy",
    "PatchDefinitionEntity",
    "PatchExclude",
    "PatchScope",
```

- [ ] **Step 5: Register the core kind**

Modify imports in `science/src/science_tool/graph/entity_registry.py`:

```python
from science_model.patch_definition import PatchDefinitionEntity
```

Add to `_CORE_KIND_CLASSES`:

```python
    "patch-definition": EntityClass.EPISTEMIC,
```

Add to `EntityRegistry.with_core_types()` after proposition registration:

```python
        r.register_core_kind(
            "patch-definition",
            PatchDefinitionEntity,
            entity_class=_CORE_KIND_CLASSES["patch-definition"],
        )
```

- [ ] **Step 6: Add source file path and status policy**

Modify `science/src/science_tool/entities.py`.

Add to `_BUILTIN_MARKDOWN_POLICIES` near proposition/inquiry:

```python
    "patch-definition": EntityPathPolicy(Path("entities/patches"), "slug"),
```

Add to `_DEFAULT_STATUS`:

```python
    "patch-definition": "active",
```

Add to `_STATUS_VALUES`:

```python
    "patch-definition": frozenset({"active", "retired"}),
```

- [ ] **Step 7: Add registry coverage test**

Append to `science/tests/test_entity_registry.py`:

```python
def test_core_registry_resolves_patch_definition() -> None:
    from science_model.entities import EntityClass
    from science_model.patch_definition import PatchDefinitionEntity
    from science_tool.graph.entity_registry import EntityRegistry

    registry = EntityRegistry.with_core_types()

    assert registry.resolve("patch-definition") is PatchDefinitionEntity
    assert registry.kind_class("patch-definition") is EntityClass.EPISTEMIC
```

- [ ] **Step 8: Run model and registry tests**

Run:

```bash
uv run --frozen pytest science/model/tests/test_patch_definition.py science/tests/test_entity_registry.py -q
```

Expected: PASS.

- [ ] **Step 9: Commit Task 1**

```bash
git add science/model/src/science_model/entities.py science/model/src/science_model/patch_definition.py science/model/src/science_model/__init__.py science/src/science_tool/graph/entity_registry.py science/src/science_tool/entities.py science/model/tests/test_patch_definition.py science/tests/test_entity_registry.py
git commit -m "feat(patch): add patch definition entity"
```

---

### Task 2: Pure Patch Membership Deriver

**Files:**
- Create: `science/src/science_tool/graph/patch_membership.py`
- Test: `science/tests/test_patch_membership_deriver.py`

- [ ] **Step 1: Write failing deriver tests**

Create `science/tests/test_patch_membership_deriver.py`:

```python
from __future__ import annotations

import pytest
from rdflib import Dataset, Literal, URIRef
from rdflib.namespace import RDF, XSD

from science_model.patch_definition import PatchDefinitionEntity
from science_tool.graph.io import CITO_NS, PROJECT_NS, SCI_NS
from science_tool.graph.patch_membership import (
    PatchMembershipError,
    derive_patch_memberships,
)


def _uri(ref: str) -> URIRef:
    kind, slug = ref.split(":", 1)
    return URIRef(PROJECT_NS[f"{kind}/{slug.lower()}"])


def _patch(**overrides: object) -> PatchDefinitionEntity:
    data: dict[str, object] = {
        "id": "patch-definition:p1",
        "canonical_id": "patch-definition:p1",
        "kind": "patch-definition",
        "type": "patch-definition",
        "title": "Patch",
        "status": "active",
        "project": "",
        "ontology_terms": [],
        "related": [],
        "source_refs": [],
        "content_preview": "",
        "file_path": "entities/patches/p1.md",
        "focal": "hypothesis:h1",
        "scope_set": [{"scope": "local"}],
        "neighborhood_policy": {"name": "local-closure-v1", "version": "local-closure-v1", "max_depth": 2},
        "seeds": [],
        "excludes": [],
    }
    data.update(overrides)
    return PatchDefinitionEntity.model_validate(data)


def _dataset() -> Dataset:
    ds = Dataset()
    g = ds.graph(PROJECT_NS["graph/knowledge"])
    for ref, rdf_type in [
        ("hypothesis:h1", SCI_NS.Hypothesis),
        ("proposition:p1", SCI_NS.Proposition),
        ("proposition:p2", SCI_NS.Proposition),
        ("proposition:p3", SCI_NS.Proposition),
        ("evidence-line:e1", SCI_NS.EvidenceLine),
    ]:
        g.add((_uri(ref), RDF.type, rdf_type))

    def bears_edge(source: str, target: str, depth: int) -> None:
        edge = URIRef(PROJECT_NS[f"bears-on-edge/{source}-{target}-{depth}".replace(":", "-")])
        g.add((edge, RDF.type, SCI_NS.BearsOnEdge))
        g.add((edge, SCI_NS.bearsOnSource, _uri(source)))
        g.add((edge, SCI_NS.bearsOnTarget, _uri(target)))
        g.add((edge, SCI_NS.bearsOnDepth, Literal(depth, datatype=XSD.integer)))

    bears_edge("proposition:p1", "hypothesis:h1", 1)
    bears_edge("proposition:p2", "hypothesis:h1", 2)
    bears_edge("proposition:p3", "hypothesis:h1", 3)
    g.add((_uri("evidence-line:e1"), CITO_NS.supports, _uri("proposition:p1")))
    return ds


def test_deriver_uses_bears_on_depth_not_closed_edge_rewalk() -> None:
    result = derive_patch_memberships(_dataset(), [_patch()], policy_version="local-closure-v1")
    members = {record.member for record in result.records}

    assert _uri("hypothesis:h1") in members
    assert _uri("proposition:p1") in members
    assert _uri("proposition:p2") in members
    assert _uri("proposition:p3") not in members
    p2 = next(record for record in result.records if record.member == _uri("proposition:p2"))
    assert p2.derivation_reason == "closure"
    assert p2.depth == 2


def test_deriver_attaches_direct_relation_neighbors() -> None:
    result = derive_patch_memberships(_dataset(), [_patch()], policy_version="local-closure-v1")
    evidence = next(record for record in result.records if record.member == _uri("evidence-line:e1"))

    assert evidence.member_kind == "evidence"
    assert evidence.derivation_reason == "direct_relation"
    assert evidence.derivation_predicate == CITO_NS.supports
    assert evidence.depth == 2


def test_deriver_records_seeds_as_reason_not_role() -> None:
    result = derive_patch_memberships(
        _dataset(),
        [_patch(seeds=["proposition:p3"])],
        policy_version="local-closure-v1",
    )
    seed = next(record for record in result.records if record.member == _uri("proposition:p3"))

    assert seed.member_role == "member"
    assert seed.member_kind == "proposition"
    assert seed.derivation_reason == "seed"
    assert seed.depth == 0


def test_deriver_excludes_members_and_warns_when_unused() -> None:
    result = derive_patch_memberships(
        _dataset(),
        [
            _patch(
                excludes=[
                    {"ref": "proposition:p1", "reason": "too broad"},
                    {"ref": "proposition:missing", "reason": "stale curation"},
                ]
            )
        ],
        policy_version="local-closure-v1",
    )

    assert _uri("proposition:p1") not in {record.member for record in result.records}
    assert result.warnings == [
        "patch-definition:p1 exclude proposition:missing did not match any derived member"
    ]


def test_deriver_fails_unresolved_focal_or_seed() -> None:
    with pytest.raises(PatchMembershipError, match="unresolved focal"):
        derive_patch_memberships(_dataset(), [_patch(focal="hypothesis:missing")], policy_version="local-closure-v1")

    with pytest.raises(PatchMembershipError, match="unresolved seed"):
        derive_patch_memberships(_dataset(), [_patch(seeds=["proposition:missing"])], policy_version="local-closure-v1")


def test_deriver_requires_policy_version() -> None:
    with pytest.raises(PatchMembershipError, match="policy_version"):
        derive_patch_memberships(_dataset(), [_patch()], policy_version="")


def test_deriver_output_is_sorted_by_member_iri() -> None:
    result = derive_patch_memberships(_dataset(), [_patch(seeds=["proposition:p3"])], policy_version="local-closure-v1")

    assert [str(record.member) for record in result.records] == sorted(str(record.member) for record in result.records)
```

- [ ] **Step 2: Run deriver tests to verify they fail**

Run:

```bash
uv run --frozen pytest science/tests/test_patch_membership_deriver.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'science_tool.graph.patch_membership'`.

- [ ] **Step 3: Implement the pure deriver**

Create `science/src/science_tool/graph/patch_membership.py`:

```python
"""Patch membership derivation and graph emission.

PatchDefinition entities author intent. This module derives compiled
PatchMembership records from an in-memory Dataset and can emit them back into
patch named graphs. It never writes files.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Literal

from rdflib import Dataset, Literal as RDFLiteral, URIRef
from rdflib.namespace import RDF, XSD

from science_model.patch_definition import PatchDefinitionEntity
from science_tool.graph.io import CITO_NS, PROJECT_NS, SCI_NS

MemberRole = Literal["focal", "member"]
DerivationReason = Literal["focal", "seed", "closure", "direct_relation"]

DIRECT_RELATION_PREDICATES: tuple[URIRef, ...] = (
    CITO_NS.discusses,
    CITO_NS.supports,
    CITO_NS.disputes,
)


class PatchMembershipError(ValueError):
    """Raised when patch membership cannot be derived fail-loudly."""


@dataclass(frozen=True)
class MembershipRecord:
    patch: URIRef
    patch_id: str
    member: URIRef
    member_role: MemberRole
    member_kind: str
    derivation_reason: DerivationReason
    depth: int
    policy_version: str
    derivation_predicate: URIRef | None = None
    build_id: str | None = None


@dataclass(frozen=True)
class PatchDerivationResult:
    records: list[MembershipRecord]
    warnings: list[str]


def entity_uri_for_ref(ref: str) -> URIRef:
    if ":" not in ref:
        raise PatchMembershipError(f"invalid entity ref {ref!r}")
    kind, slug = ref.split(":", 1)
    if not kind or not slug:
        raise PatchMembershipError(f"invalid entity ref {ref!r}")
    return URIRef(PROJECT_NS[f"{kind}/{slug.lower()}"])


def derive_patch_memberships(
    dataset: Dataset,
    patch_definitions: list[PatchDefinitionEntity],
    *,
    policy_version: str,
    build_id: str | None = None,
) -> PatchDerivationResult:
    if not policy_version.strip():
        raise PatchMembershipError("policy_version must be non-empty")

    records: list[MembershipRecord] = []
    warnings: list[str] = []
    for definition in sorted(patch_definitions, key=lambda item: item.canonical_id):
        patch_uri = entity_uri_for_ref(definition.canonical_id)
        focal_uri = _resolve_required(dataset, definition.focal, label="focal", patch_id=definition.canonical_id)
        seed_uris = [
            _resolve_required(dataset, seed, label="seed", patch_id=definition.canonical_id)
            for seed in definition.seeds
        ]
        by_member: dict[URIRef, MembershipRecord] = {}

        _put_record(
            by_member,
            MembershipRecord(
                patch=patch_uri,
                patch_id=definition.canonical_id,
                member=focal_uri,
                member_role="focal",
                member_kind=_member_kind(dataset, focal_uri),
                derivation_reason="focal",
                depth=0,
                policy_version=policy_version,
                build_id=build_id,
            ),
        )
        for seed_uri in seed_uris:
            _put_record(
                by_member,
                MembershipRecord(
                    patch=patch_uri,
                    patch_id=definition.canonical_id,
                    member=seed_uri,
                    member_role="member",
                    member_kind=_member_kind(dataset, seed_uri),
                    derivation_reason="seed",
                    depth=0,
                    policy_version=policy_version,
                    build_id=build_id,
                ),
            )

        origins = [focal_uri, *seed_uris]
        anchors: dict[URIRef, int] = {origin: 0 for origin in origins}
        max_depth = definition.neighborhood_policy.max_depth
        for origin in origins:
            for member, depth in _bears_on_neighbors(dataset, origin, max_depth=max_depth):
                if member == origin:
                    continue
                anchors[member] = min(depth, anchors.get(member, depth))
                _put_record(
                    by_member,
                    MembershipRecord(
                        patch=patch_uri,
                        patch_id=definition.canonical_id,
                        member=member,
                        member_role="member",
                        member_kind=_member_kind(dataset, member),
                        derivation_reason="closure",
                        derivation_predicate=SCI_NS.bearsOn,
                        depth=depth,
                        policy_version=policy_version,
                        build_id=build_id,
                    ),
                )

        for anchor, anchor_depth in sorted(anchors.items(), key=lambda item: str(item[0])):
            for member, predicate in _direct_relation_neighbors(dataset, anchor):
                if member == anchor:
                    continue
                _put_record(
                    by_member,
                    MembershipRecord(
                        patch=patch_uri,
                        patch_id=definition.canonical_id,
                        member=member,
                        member_role="member",
                        member_kind=_member_kind(dataset, member),
                        derivation_reason="direct_relation",
                        derivation_predicate=predicate,
                        depth=anchor_depth + 1,
                        policy_version=policy_version,
                        build_id=build_id,
                    ),
                )

        derived_before_excludes = set(by_member)
        for exclude in definition.excludes:
            exclude_uri = entity_uri_for_ref(exclude.ref)
            if exclude_uri in by_member:
                del by_member[exclude_uri]
            elif exclude_uri not in derived_before_excludes:
                warnings.append(
                    f"{definition.canonical_id} exclude {exclude.ref} did not match any derived member"
                )

        records.extend(record for _, record in sorted(by_member.items(), key=lambda item: str(item[0])))

    return PatchDerivationResult(records=records, warnings=warnings)


def _resolve_required(dataset: Dataset, ref: str, *, label: str, patch_id: str) -> URIRef:
    uri = entity_uri_for_ref(ref)
    if any(next(graph.triples((uri, RDF.type, None)), None) is not None for graph in dataset.graphs()):
        return uri
    raise PatchMembershipError(f"{patch_id}: unresolved {label} {ref!r}")


def _bears_on_neighbors(dataset: Dataset, origin: URIRef, *, max_depth: int) -> list[tuple[URIRef, int]]:
    found: dict[URIRef, int] = {}
    for graph in dataset.graphs():
        for edge, _, _ in graph.triples((None, RDF.type, SCI_NS.BearsOnEdge)):
            source = next(graph.objects(edge, SCI_NS.bearsOnSource), None)
            target = next(graph.objects(edge, SCI_NS.bearsOnTarget), None)
            depth_lit = next(graph.objects(edge, SCI_NS.bearsOnDepth), None)
            if not isinstance(source, URIRef) or not isinstance(target, URIRef) or depth_lit is None:
                continue
            depth = int(depth_lit)
            if depth > max_depth:
                continue
            if source == origin:
                found[target] = min(depth, found.get(target, depth))
            if target == origin:
                found[source] = min(depth, found.get(source, depth))
    return sorted(found.items(), key=lambda item: (item[1], str(item[0])))


def _direct_relation_neighbors(dataset: Dataset, anchor: URIRef) -> list[tuple[URIRef, URIRef]]:
    found: set[tuple[URIRef, URIRef]] = set()
    for graph in dataset.graphs():
        for predicate in DIRECT_RELATION_PREDICATES:
            for subject, _, _ in graph.triples((None, predicate, anchor)):
                if isinstance(subject, URIRef):
                    found.add((subject, predicate))
            for _, _, obj in graph.triples((anchor, predicate, None)):
                if isinstance(obj, URIRef):
                    found.add((obj, predicate))
    return sorted(found, key=lambda item: (str(item[1]), str(item[0])))


def _member_kind(dataset: Dataset, member: URIRef) -> str:
    type_values = sorted(
        str(obj)
        for graph in dataset.graphs()
        for obj in graph.objects(member, RDF.type)
    )
    for type_value in type_values:
        if type_value.startswith(str(SCI_NS)):
            local = type_value.removeprefix(str(SCI_NS))
            if local == "EvidenceLine":
                return "evidence"
            return _camel_to_kebab(local)
    return "unknown"


def _camel_to_kebab(value: str) -> str:
    chars: list[str] = []
    for index, char in enumerate(value):
        if char.isupper() and index > 0:
            chars.append("-")
        chars.append(char.lower())
    return "".join(chars)


def _put_record(by_member: dict[URIRef, MembershipRecord], record: MembershipRecord) -> None:
    existing = by_member.get(record.member)
    if existing is None or _record_sort_key(record) < _record_sort_key(existing):
        by_member[record.member] = record


def _record_sort_key(record: MembershipRecord) -> tuple[int, int, str]:
    reason_order = {"focal": 0, "seed": 1, "closure": 2, "direct_relation": 3}
    return (
        record.depth,
        reason_order[record.derivation_reason],
        str(record.derivation_predicate or ""),
    )
```

- [ ] **Step 4: Run deriver tests**

Run:

```bash
uv run --frozen pytest science/tests/test_patch_membership_deriver.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 2**

```bash
git add science/src/science_tool/graph/patch_membership.py science/tests/test_patch_membership_deriver.py
git commit -m "feat(patch): derive local patch memberships"
```

---

### Task 3: Patch Membership Emission And Validation

**Files:**
- Modify: `science/src/science_tool/graph/patch_membership.py`
- Test: `science/tests/test_patch_membership_emission.py`

- [ ] **Step 1: Write failing emission tests**

Create `science/tests/test_patch_membership_emission.py`:

```python
from __future__ import annotations

from rdflib import Dataset, Literal, URIRef
from rdflib.namespace import RDF, XSD

from science_model.patch_definition import PatchDefinitionEntity
from science_tool.graph.io import PROJECT_NS, SCI_NS
from science_tool.graph.patch_membership import (
    MembershipRecord,
    emit_patch_memberships,
    validate_patch_membership_convenience,
)


def _uri(ref: str) -> URIRef:
    kind, slug = ref.split(":", 1)
    return URIRef(PROJECT_NS[f"{kind}/{slug.lower()}"])


def _patch() -> PatchDefinitionEntity:
    return PatchDefinitionEntity.model_validate(
        {
            "id": "patch-definition:p1",
            "canonical_id": "patch-definition:p1",
            "kind": "patch-definition",
            "type": "patch-definition",
            "title": "Patch",
            "status": "active",
            "project": "",
            "ontology_terms": [],
            "related": [],
            "source_refs": [],
            "content_preview": "",
            "file_path": "entities/patches/p1.md",
            "focal": "hypothesis:h1",
            "scope_set": [{"scope": "local"}],
            "neighborhood_policy": {"name": "local-closure-v1", "version": "local-closure-v1", "max_depth": 2},
            "seeds": ["proposition:p1"],
            "excludes": [{"ref": "proposition:p2", "reason": "out of scope"}],
        }
    )


def test_emit_patch_membership_context_and_authoritative_nodes() -> None:
    ds = Dataset()
    patch = _patch()
    patch_uri = _uri("patch-definition:p1")
    member_uri = _uri("proposition:p1")
    records = [
        MembershipRecord(
            patch=patch_uri,
            patch_id=patch.canonical_id,
            member=member_uri,
            member_role="member",
            member_kind="proposition",
            derivation_reason="seed",
            depth=0,
            policy_version="local-closure-v1",
            build_id="build-1",
        )
    ]

    emit_patch_memberships(ds, [patch], records)
    graph = ds.graph(patch_uri)
    membership_nodes = list(graph.subjects(RDF.type, SCI_NS.PatchMembership))

    assert (patch_uri, RDF.type, SCI_NS.EpistemicPatch) in graph
    assert (patch_uri, SCI_NS.focalEntity, _uri("hypothesis:h1")) in graph
    assert (patch_uri, SCI_NS.hasMember, member_uri) in graph
    assert (member_uri, SCI_NS.inPatch, patch_uri) in graph
    assert len(membership_nodes) == 1
    node = membership_nodes[0]
    assert (node, SCI_NS.patch, patch_uri) in graph
    assert (node, SCI_NS.member, member_uri) in graph
    assert (node, SCI_NS.memberRole, Literal("member")) in graph
    assert (node, SCI_NS.memberKind, Literal("proposition")) in graph
    assert (node, SCI_NS.derivationReason, Literal("seed")) in graph
    assert (node, SCI_NS.policyVersion, Literal("local-closure-v1")) in graph
    assert (node, SCI_NS.buildId, Literal("build-1")) in graph
    assert (node, SCI_NS.derivationDepth, Literal(0, datatype=XSD.integer)) in graph


def test_emit_patch_metadata_includes_seeds_and_exclusions() -> None:
    ds = Dataset()
    patch = _patch()
    patch_uri = _uri("patch-definition:p1")

    emit_patch_memberships(ds, [patch], [])
    graph = ds.graph(patch_uri)

    assert (patch_uri, SCI_NS.patchSeed, _uri("proposition:p1")) in graph
    exclusion_nodes = list(graph.subjects(RDF.type, SCI_NS.PatchExclusion))
    assert len(exclusion_nodes) == 1
    exclusion = exclusion_nodes[0]
    assert (exclusion, SCI_NS.patch, patch_uri) in graph
    assert (exclusion, SCI_NS.excludedEntity, _uri("proposition:p2")) in graph
    assert (exclusion, SCI_NS.excludeReason, Literal("out of scope")) in graph


def test_validate_patch_membership_rejects_orphan_convenience_edges() -> None:
    ds = Dataset()
    patch_uri = _uri("patch-definition:p1")
    member_uri = _uri("proposition:p1")
    graph = ds.graph(patch_uri)
    graph.add((patch_uri, SCI_NS.hasMember, member_uri))

    errors = validate_patch_membership_convenience(ds)

    assert errors == [
        "http://example.org/project/patch-definition/p1 has sci:hasMember http://example.org/project/proposition/p1 without a sci:PatchMembership node"
    ]
```

- [ ] **Step 2: Run emission tests to verify they fail**

Run:

```bash
uv run --frozen pytest science/tests/test_patch_membership_emission.py -q
```

Expected: FAIL with `ImportError` for `emit_patch_memberships`.

- [ ] **Step 3: Add emitter and validation helper**

Append to `science/src/science_tool/graph/patch_membership.py`:

```python
def emit_patch_memberships(
    dataset: Dataset,
    patch_definitions: list[PatchDefinitionEntity],
    records: list[MembershipRecord],
) -> None:
    records_by_patch: dict[str, list[MembershipRecord]] = {}
    for record in records:
        records_by_patch.setdefault(record.patch_id, []).append(record)

    for definition in sorted(patch_definitions, key=lambda item: item.canonical_id):
        patch_uri = entity_uri_for_ref(definition.canonical_id)
        graph = dataset.graph(patch_uri)
        graph.add((patch_uri, RDF.type, SCI_NS.EpistemicPatch))
        graph.add((patch_uri, SCI_NS.focalEntity, entity_uri_for_ref(definition.focal)))
        graph.add((patch_uri, SCI_NS.neighborhoodPolicy, RDFLiteral(definition.neighborhood_policy.name)))
        graph.add((patch_uri, SCI_NS.policyVersion, RDFLiteral(definition.neighborhood_policy.version)))
        graph.add((patch_uri, SCI_NS.patchScope, RDFLiteral("local")))
        for seed in sorted(definition.seeds):
            graph.add((patch_uri, SCI_NS.patchSeed, entity_uri_for_ref(seed)))
        for exclude in sorted(definition.excludes, key=lambda item: item.ref):
            exclusion = _exclusion_uri(definition.canonical_id, exclude.ref)
            graph.add((exclusion, RDF.type, SCI_NS.PatchExclusion))
            graph.add((exclusion, SCI_NS.patch, patch_uri))
            graph.add((exclusion, SCI_NS.excludedEntity, entity_uri_for_ref(exclude.ref)))
            graph.add((exclusion, SCI_NS.excludeReason, RDFLiteral(exclude.reason)))

        for record in sorted(records_by_patch.get(definition.canonical_id, []), key=lambda item: str(item.member)):
            node = _membership_uri(record)
            graph.add((node, RDF.type, SCI_NS.PatchMembership))
            graph.add((node, SCI_NS.patch, record.patch))
            graph.add((node, SCI_NS.member, record.member))
            graph.add((node, SCI_NS.memberRole, RDFLiteral(record.member_role)))
            graph.add((node, SCI_NS.memberKind, RDFLiteral(record.member_kind)))
            graph.add((node, SCI_NS.derivationReason, RDFLiteral(record.derivation_reason)))
            graph.add((node, SCI_NS.derivationDepth, RDFLiteral(record.depth, datatype=XSD.integer)))
            graph.add((node, SCI_NS.policyVersion, RDFLiteral(record.policy_version)))
            if record.derivation_predicate is not None:
                graph.add((node, SCI_NS.derivationPredicate, record.derivation_predicate))
            if record.build_id:
                graph.add((node, SCI_NS.buildId, RDFLiteral(record.build_id)))
            graph.add((record.patch, SCI_NS.hasMember, record.member))
            graph.add((record.member, SCI_NS.inPatch, record.patch))


def patch_membership_pairs(dataset: Dataset) -> set[tuple[str, str]]:
    return {
        (str(patch), str(member))
        for graph in dataset.graphs()
        for node in graph.subjects(RDF.type, SCI_NS.PatchMembership)
        for patch in graph.objects(node, SCI_NS.patch)
        for member in graph.objects(node, SCI_NS.member)
    }


def validate_patch_membership_convenience(dataset: Dataset) -> list[str]:
    errors: list[str] = []
    membership_pairs = patch_membership_pairs(dataset)
    for graph in dataset.graphs():
        for patch, _, member in graph.triples((None, SCI_NS.hasMember, None)):
            if (str(patch), str(member)) not in membership_pairs:
                errors.append(f"{patch} has sci:hasMember {member} without a sci:PatchMembership node")
        for member, _, patch in graph.triples((None, SCI_NS.inPatch, None)):
            if (str(patch), str(member)) not in membership_pairs:
                errors.append(f"{member} has sci:inPatch {patch} without a sci:PatchMembership node")
    return sorted(errors)


def _membership_uri(record: MembershipRecord) -> URIRef:
    key = f"{record.patch}\x00{record.member}\x00{record.policy_version}"
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
    return URIRef(PROJECT_NS[f"patch-membership/{digest}"])


def _exclusion_uri(patch_id: str, ref: str) -> URIRef:
    key = f"{patch_id}\x00{ref}"
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
    return URIRef(PROJECT_NS[f"patch-exclusion/{digest}"])
```

- [ ] **Step 4: Run emission and deriver tests**

Run:

```bash
uv run --frozen pytest science/tests/test_patch_membership_deriver.py science/tests/test_patch_membership_emission.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 3**

```bash
git add science/src/science_tool/graph/patch_membership.py science/tests/test_patch_membership_emission.py
git commit -m "feat(patch): emit patch membership graphs"
```

---

### Task 4: Wire Patch Derivation Into Graph Materialization

**Files:**
- Modify: `science/src/science_tool/graph/materialize.py`
- Test: `science/tests/test_patch_membership_materialize.py`

- [ ] **Step 1: Write failing materialization integration test**

Create `science/tests/test_patch_membership_materialize.py`:

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


def test_graph_build_emits_patch_membership_context(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text("name: demo\n", encoding="utf-8")
    _write_entity(
        tmp_path / "entities" / "hypotheses" / "h1.md",
        [
            'id: "hypothesis:h1"',
            'type: "hypothesis"',
            'title: "H1"',
            'status: "proposed"',
            "ontology_terms: []",
            "source_refs: []",
            "related: []",
        ],
    )
    _write_entity(
        tmp_path / "entities" / "propositions" / "p1.md",
        [
            'id: "proposition:p1"',
            'type: "proposition"',
            'title: "P1"',
            'status: "active"',
            "ontology_terms: []",
            "source_refs: []",
            "related: []",
            'discusses: ["hypothesis:h1"]',
        ],
    )
    _write_entity(
        tmp_path / "entities" / "patches" / "local-demo.md",
        [
            'id: "patch-definition:local-demo"',
            'type: "patch-definition"',
            'title: "Local demo patch"',
            'status: "active"',
            "ontology_terms: []",
            "source_refs: []",
            "related: []",
            'focal: "hypothesis:h1"',
            "scope_set:",
            '  - scope: "local"',
            "neighborhood_policy:",
            '  name: "local-closure-v1"',
            '  version: "local-closure-v1"',
            "  max_depth: 2",
        ],
    )

    trig_path = materialize_graph(tmp_path, strict=False)
    ds = Dataset()
    ds.parse(str(trig_path), format="trig")
    patch_uri = URIRef(PROJECT_NS["patch-definition/local-demo"])
    proposition_uri = URIRef(PROJECT_NS["proposition/p1"])
    patch_graph = ds.graph(patch_uri)

    assert (patch_uri, RDF.type, SCI_NS.EpistemicPatch) in patch_graph
    assert (patch_uri, SCI_NS.hasMember, proposition_uri) in patch_graph
    assert (proposition_uri, SCI_NS.inPatch, patch_uri) in patch_graph
    assert list(patch_graph.subjects(RDF.type, SCI_NS.PatchMembership))
```

- [ ] **Step 2: Run materialization test to verify it fails**

Run:

```bash
uv run --frozen pytest science/tests/test_patch_membership_materialize.py -q
```

Expected: FAIL because `materialize_graph` does not emit a patch context yet.

- [ ] **Step 3: Wire the materialization phase**

Modify imports in `science/src/science_tool/graph/materialize.py`:

```python
from science_model.patch_definition import PatchDefinitionEntity
from science_tool.graph.patch_membership import (
    derive_patch_memberships,
    entity_uri_for_ref,
    emit_patch_memberships,
)
```

Add this helper near `_derive_bears_on_layer(...)`:

```python
PATCH_MEMBERSHIP_POLICY_VERSION = "local-closure-v1"


def _derive_patch_membership_layer(dataset: Dataset, *, sources: ProjectSources) -> None:
    patch_definitions = [
        entity for entity in sources.entities if isinstance(entity, PatchDefinitionEntity)
    ]
    if not patch_definitions:
        return
    result = derive_patch_memberships(
        dataset,
        patch_definitions,
        policy_version=PATCH_MEMBERSHIP_POLICY_VERSION,
    )
    emit_patch_memberships(dataset, patch_definitions, result.records)
```

In the existing `_entity_uri(...)` helper, delegate to the same minter used by
patch membership so the URI scheme has one implementation after Task 4:

```python
def _entity_uri(canonical_id: str) -> URIRef:
    return entity_uri_for_ref(canonical_id)
```

Call it at the call site inside `_build_dataset_from_sources(...)`, immediately
after `_derive_bears_on_layer(...)` returns and before
`emit_dataset_independence_records(...)`:

```python
    _derive_bears_on_layer(
        dataset,
        kind_class=kind_class,
        pre_registration_targets=pre_registration_targets,
        eligible_code_files=_eligible_code_files(sources),
    )
    _derive_patch_membership_layer(dataset, sources=sources)
    emit_dataset_independence_records(
        provenance,
        derive_dataset_independence_records(knowledge, provenance),
    )
```

- [ ] **Step 4: Run integration and focused graph tests**

Run:

```bash
uv run --frozen pytest science/tests/test_patch_membership_materialize.py science/tests/test_graph_materialize.py::test_materialize_graph_is_deterministic_for_identical_inputs -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 4**

```bash
git add science/src/science_tool/graph/materialize.py science/tests/test_patch_membership_materialize.py
git commit -m "feat(patch): materialize patch memberships"
```

---

### Task 5: Diagnostic Patch CLI

**Files:**
- Create: `science/src/science_tool/patch/__init__.py`
- Create: `science/src/science_tool/patch/cli.py`
- Modify: `science/src/science_tool/cli.py`
- Test: `science/tests/test_patch_cli.py`

- [ ] **Step 1: Write failing CLI tests**

Create `science/tests/test_patch_cli.py`:

```python
from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner
from rdflib import Dataset, URIRef

from science_tool.cli import main
from science_tool.graph.io import PROJECT_NS, SCI_NS
from science_tool.graph.materialize import materialize_graph


def _write_entity(path: Path, frontmatter: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(["---", *frontmatter, "---", "", "Body.", ""]), encoding="utf-8")


def _project(root: Path) -> None:
    (root / "science.yaml").write_text("name: demo\n", encoding="utf-8")
    _write_entity(
        root / "entities" / "hypotheses" / "h1.md",
        [
            'id: "hypothesis:h1"',
            'type: "hypothesis"',
            'title: "H1"',
            'status: "proposed"',
            "ontology_terms: []",
            "source_refs: []",
            "related: []",
        ],
    )
    _write_entity(
        root / "entities" / "propositions" / "p1.md",
        [
            'id: "proposition:p1"',
            'type: "proposition"',
            'title: "P1"',
            'status: "active"',
            "ontology_terms: []",
            "source_refs: []",
            "related: []",
            'discusses: ["hypothesis:h1"]',
        ],
    )
    _write_entity(
        root / "entities" / "patches" / "local-demo.md",
        [
            'id: "patch-definition:local-demo"',
            'type: "patch-definition"',
            'title: "Local demo patch"',
            'status: "active"',
            "ontology_terms: []",
            "source_refs: []",
            "related: []",
            'focal: "hypothesis:h1"',
            "scope_set:",
            '  - scope: "local"',
            "neighborhood_policy:",
            '  name: "local-closure-v1"',
            '  version: "local-closure-v1"',
            "  max_depth: 2",
            'seeds: ["proposition:p1"]',
        ],
    )


def test_patch_explain_reports_members(tmp_path: Path) -> None:
    _project(tmp_path)
    materialize_graph(tmp_path, strict=False)
    runner = CliRunner()

    result = runner.invoke(main, ["patch", "explain", "patch-definition:local-demo", "--project-root", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert "patch-definition:local-demo" in result.output
    assert "proposition:p1" in result.output
    assert "seed" in result.output


def test_patch_check_detects_orphan_convenience_edge(tmp_path: Path) -> None:
    _project(tmp_path)
    graph_path = materialize_graph(tmp_path, strict=False)
    ds = Dataset()
    ds.parse(str(graph_path), format="trig")
    patch_uri = URIRef(PROJECT_NS["patch-definition/local-demo"])
    orphan = URIRef(PROJECT_NS["proposition/orphan"])
    ds.graph(patch_uri).add((patch_uri, SCI_NS.hasMember, orphan))
    ds.serialize(destination=str(graph_path), format="trig")
    runner = CliRunner()

    result = runner.invoke(main, ["patch", "check", "--project-root", str(tmp_path)])

    assert result.exit_code == 1
    assert "without a sci:PatchMembership node" in result.output


def test_patch_check_detects_stale_graph_after_source_edit(tmp_path: Path) -> None:
    _project(tmp_path)
    materialize_graph(tmp_path, strict=False)
    patch_file = tmp_path / "entities" / "patches" / "local-demo.md"
    text = patch_file.read_text(encoding="utf-8")
    patch_file.write_text(
        text.replace(
            'seeds: ["proposition:p1"]',
            'excludes:\n  - ref: "proposition:p1"\n    reason: "out of scope"',
        ),
        encoding="utf-8",
    )
    runner = CliRunner()

    result = runner.invoke(main, ["patch", "check", "--project-root", str(tmp_path)])

    assert result.exit_code == 1
    assert "stale patch membership" in result.output
```

- [ ] **Step 2: Run CLI tests to verify they fail**

Run:

```bash
uv run --frozen pytest science/tests/test_patch_cli.py -q
```

Expected: FAIL because `science patch` is not registered.

- [ ] **Step 3: Add patch CLI package**

Create `science/src/science_tool/patch/__init__.py`:

```python
"""Patch contract CLI and helpers."""
```

Create `science/src/science_tool/patch/cli.py`:

```python
from __future__ import annotations

from pathlib import Path

import click
from rdflib import Dataset

from science_model.patch_definition import PatchDefinitionEntity
from science_tool.graph.io import PROJECT_NS
from science_tool.graph.materialize import PATCH_MEMBERSHIP_POLICY_VERSION, _build_dataset_from_sources
from science_tool.graph.patch_membership import (
    derive_patch_memberships,
    patch_membership_pairs,
    validate_patch_membership_convenience,
)
from science_tool.graph.sources import load_project_sources
from science_tool.graph.store import DEFAULT_GRAPH_PATH, canonical_id_from_entity_uri


@click.group("patch")
def patch_group() -> None:
    """Patch definition diagnostics."""


@patch_group.command("explain")
@click.argument("patch_id")
@click.option("--project-root", default=".", show_default=True, type=click.Path(path_type=Path, file_okay=False))
def patch_explain(patch_id: str, project_root: Path) -> None:
    """Explain derived patch membership without writing graph.trig."""
    root = project_root.resolve()
    dataset = _load_graph(root)
    definitions = _patch_definitions(root)
    selected = [definition for definition in definitions if definition.canonical_id == patch_id]
    if not selected:
        raise click.ClickException(f"patch definition not found: {patch_id}")
    result = derive_patch_memberships(dataset, selected, policy_version=PATCH_MEMBERSHIP_POLICY_VERSION)
    click.echo(patch_id)
    for warning in result.warnings:
        click.echo(f"warning: {warning}")
    for record in result.records:
        member = canonical_id_from_entity_uri(str(record.member)) or str(record.member)
        predicate = str(record.derivation_predicate) if record.derivation_predicate is not None else ""
        click.echo(
            f"{member}\trole={record.member_role}\tkind={record.member_kind}"
            f"\treason={record.derivation_reason}\tdepth={record.depth}\tpredicate={predicate}"
        )


@patch_group.command("check")
@click.option("--project-root", default=".", show_default=True, type=click.Path(path_type=Path, file_okay=False))
def patch_check(project_root: Path) -> None:
    """Re-derive patch membership and diff it against graph.trig."""
    root = project_root.resolve()
    actual_dataset = _load_graph(root)
    expected_dataset = _expected_graph(root)
    errors = validate_patch_membership_convenience(actual_dataset)
    actual_pairs = patch_membership_pairs(actual_dataset)
    expected_pairs = patch_membership_pairs(expected_dataset)
    for pair in sorted(expected_pairs - actual_pairs):
        errors.append(f"stale patch membership: missing {_format_pair(pair)}")
    for pair in sorted(actual_pairs - expected_pairs):
        errors.append(f"stale patch membership: unexpected {_format_pair(pair)}")
    if errors:
        for error in errors:
            click.echo(error)
        raise click.exceptions.Exit(1)
    click.echo("patch check: OK")


def _load_graph(project_root: Path) -> Dataset:
    graph_path = project_root / DEFAULT_GRAPH_PATH
    if not graph_path.is_file():
        raise click.ClickException(f"Graph file not found at {graph_path}. Run `science graph build` first.")
    dataset = Dataset()
    dataset.parse(str(graph_path), format="trig")
    return dataset


def _expected_graph(project_root: Path) -> Dataset:
    sources = load_project_sources(project_root, strict_identity=False)
    return _build_dataset_from_sources(sources)


def _patch_definitions(project_root: Path) -> list[PatchDefinitionEntity]:
    sources = load_project_sources(project_root, strict_identity=False)
    return [entity for entity in sources.entities if isinstance(entity, PatchDefinitionEntity)]


def _format_pair(pair: tuple[str, str]) -> str:
    patch_uri, member_uri = pair
    patch = canonical_id_from_entity_uri(patch_uri) or patch_uri
    member = canonical_id_from_entity_uri(member_uri) or member_uri
    return f"{patch} -> {member}"
```

- [ ] **Step 4: Register the CLI group**

Modify `science/src/science_tool/cli.py`.

Add import:

```python
from science_tool.patch.cli import patch_group
```

Add registration near the other top-level groups:

```python
main.add_command(patch_group)
```

- [ ] **Step 5: Run CLI tests**

Run:

```bash
uv run --frozen pytest science/tests/test_patch_cli.py -q
```

Expected: PASS.

- [ ] **Step 6: Run full focused patch suite**

Run:

```bash
uv run --frozen pytest science/model/tests/test_patch_definition.py science/tests/test_patch_membership_deriver.py science/tests/test_patch_membership_emission.py science/tests/test_patch_membership_materialize.py science/tests/test_patch_cli.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit Task 5**

```bash
git add science/src/science_tool/patch/__init__.py science/src/science_tool/patch/cli.py science/src/science_tool/cli.py science/tests/test_patch_cli.py
git commit -m "feat(patch): add patch diagnostics CLI"
```

---

### Task 6: Final Verification And Documentation Sweep

**Files:**
- Modify if needed: `docs/plans/2026-06-14-patch-contract-keystone-design.md`
- Modify if needed: `docs/plans/2026-06-14-patch-contract-keystone-plan.md`

- [ ] **Step 1: Run formatting and lint checks for touched Python files**

Run:

```bash
uv run --frozen ruff format science/model/src/science_model/patch_definition.py science/model/tests/test_patch_definition.py science/src/science_tool/graph/patch_membership.py science/tests/test_patch_membership_deriver.py science/tests/test_patch_membership_emission.py science/tests/test_patch_membership_materialize.py science/src/science_tool/patch/cli.py science/tests/test_patch_cli.py
uv run --frozen ruff check science/model/src/science_model/patch_definition.py science/model/tests/test_patch_definition.py science/src/science_tool/graph/patch_membership.py science/tests/test_patch_membership_deriver.py science/tests/test_patch_membership_emission.py science/tests/test_patch_membership_materialize.py science/src/science_tool/patch/cli.py science/tests/test_patch_cli.py
```

Expected: both commands exit 0.

- [ ] **Step 2: Run focused test suite**

Run:

```bash
uv run --frozen pytest science/model/tests/test_patch_definition.py science/tests/test_entity_registry.py science/tests/test_patch_membership_deriver.py science/tests/test_patch_membership_emission.py science/tests/test_patch_membership_materialize.py science/tests/test_patch_cli.py -q
```

Expected: PASS.

- [ ] **Step 3: Run graph materialization regression subset**

Run:

```bash
uv run --frozen pytest science/tests/test_graph_materialize.py science/tests/test_graph_freshness_integration.py -q
```

Expected: PASS.

- [ ] **Step 4: Check docs/spec wording**

Run:

```bash
rg -n 'update-graph|missing keystone|memberRole|BearsOnEdge|second writer' docs/plans/2026-06-14-patch-contract-keystone-design.md docs/plans/2026-06-14-patch-contract-keystone-plan.md
```

Expected:
- `update-graph` appears only as a harness alias or has been replaced with `science graph build`.
- `missing keystone` does not appear.
- `memberRole`, `BearsOnEdge`, and `second writer` references match the approved spec.

- [ ] **Step 5: Commit any verification-only doc corrections**

If Step 4 requires wording fixes, commit them:

```bash
git add docs/plans/2026-06-14-patch-contract-keystone-design.md docs/plans/2026-06-14-patch-contract-keystone-plan.md
git commit -m "docs(patch): align patch contract implementation wording"
```

If no wording fixes are needed, do not create an empty commit.

- [ ] **Step 6: Final status check**

Run:

```bash
git status --short
git log --oneline -6
```

Expected:
- `git status --short` shows no uncommitted implementation changes.
- Recent commits show the task commits on `patch-contract-keystone`.

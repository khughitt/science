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
from science_tool.graph.io import CITO_NS, PROJECT_NS, SCI_NS, entity_uri_for_ref

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
        patch_uri = _entity_uri_for_ref(definition.canonical_id)
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
            exclude_uri = _entity_uri_for_ref(exclude.ref)
            if exclude_uri in by_member:
                del by_member[exclude_uri]
            elif exclude_uri not in derived_before_excludes:
                warnings.append(f"{definition.canonical_id} exclude {exclude.ref} did not match any derived member")

        records.extend(record for _, record in sorted(by_member.items(), key=lambda item: str(item[0])))

    return PatchDerivationResult(records=records, warnings=warnings)


def _resolve_required(dataset: Dataset, ref: str, *, label: str, patch_id: str) -> URIRef:
    uri = _entity_uri_for_ref(ref)
    if any((uri, RDF.type, None) in graph for graph in dataset.graphs()):
        return uri
    raise PatchMembershipError(f"{patch_id}: unresolved {label} {ref!r}")


def _entity_uri_for_ref(ref: str) -> URIRef:
    try:
        return entity_uri_for_ref(ref)
    except ValueError as exc:
        raise PatchMembershipError(str(exc)) from exc


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
    type_values = sorted(str(obj) for graph in dataset.graphs() for obj in graph.objects(member, RDF.type))
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


def emit_patch_memberships(
    dataset: Dataset,
    patch_definitions: list[PatchDefinitionEntity],
    records: list[MembershipRecord],
) -> None:
    records_by_patch: dict[str, list[MembershipRecord]] = {}
    for record in records:
        records_by_patch.setdefault(record.patch_id, []).append(record)

    for definition in sorted(patch_definitions, key=lambda item: item.canonical_id):
        patch_uri = _entity_uri_for_ref(definition.canonical_id)
        graph = dataset.graph(patch_uri)
        graph.add((patch_uri, RDF.type, SCI_NS.EpistemicPatch))
        graph.add((patch_uri, SCI_NS.focalEntity, _entity_uri_for_ref(definition.focal)))
        graph.add((patch_uri, SCI_NS.neighborhoodPolicy, RDFLiteral(definition.neighborhood_policy.name)))
        graph.add((patch_uri, SCI_NS.policyVersion, RDFLiteral(definition.neighborhood_policy.version)))
        graph.add((patch_uri, SCI_NS.patchScope, RDFLiteral("local")))
        for seed in sorted(definition.seeds):
            graph.add((patch_uri, SCI_NS.patchSeed, _entity_uri_for_ref(seed)))
        for exclude in sorted(definition.excludes, key=lambda item: item.ref):
            exclusion = _exclusion_uri(definition.canonical_id, exclude.ref)
            graph.add((exclusion, RDF.type, SCI_NS.PatchExclusion))
            graph.add((exclusion, SCI_NS.patch, patch_uri))
            graph.add((exclusion, SCI_NS.excludedEntity, _entity_uri_for_ref(exclude.ref)))
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

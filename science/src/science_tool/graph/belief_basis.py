"""Belief-basis capture and comparison — the observable the autonomy semantic gate compares.

The basis is deliberately the *inputs* to belief, not the aggregated verdict: a run
whose evidence units change but happen to cancel leaves the ordinal magnitude intact
and must still be detected.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import asdict

from pydantic import BaseModel, ConfigDict
from rdflib import Graph, URIRef
from rdflib.namespace import RDF

from science_tool.graph.belief import EvidenceUnit, collect_evidence_units
from science_tool.graph.belief_policy import DEFAULT_BELIEF_POLICY, BeliefPolicy
from science_tool.instruments import InstrumentResult

# `_evidence_targets_for_uri` is private to the store package but has no public
# equivalent; the attention instrument imports it by this same path
# (graph/attention.py:22). Do NOT "fix" this to a public path — none exists, and
# the basis must expand targets exactly as attention does or the two disagree
# about what an entity's evidence is.
from science_tool.graph.store import _evidence_targets_for_uri, canonical_id_from_entity_uri


def unit_key(unit: EvidenceUnit) -> str:
    """Canonical, comparable key for one evidence unit.

    Derived from `asdict` so a NEW field on EvidenceUnit enters the key automatically.
    Never rewrite this against an explicit field list: an unrecognized belief input
    must change the basis rather than be silently dropped from it.

    No `default=` fallback: a future field whose type is not JSON-native must raise
    here rather than be coerced to a string, which could collapse distinct values.
    """
    return json.dumps(asdict(unit), sort_keys=True)


#: The sole precondition of basis capture. With no typed project entity in
#: graph/knowledge, NO entity has been assessed and the basis is not a basis.
NO_TYPED_ENTITIES = "no_typed_entities"


class EntityBasis(BaseModel):
    """The belief inputs for one entity, in comparable canonical form."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    entity_id: str
    uri: str
    target_uris: tuple[str, ...]
    unit_keys: tuple[str, ...]
    policy_id: str
    policy_version: str


def capture_basis(
    knowledge: Graph,
    provenance: Graph,
    *,
    policy: BeliefPolicy = DEFAULT_BELIEF_POLICY,
) -> InstrumentResult[EntityBasis]:
    """Capture the belief basis of every typed project entity in `knowledge`.

    Uses the same per-entity recipe as the attention instrument
    (`graph/attention.py:350-353`), but stops at the units: the basis compares
    belief INPUTS, never the aggregated magnitude.
    """
    entity_uris = sorted({str(s) for s in knowledge.subjects(RDF.type, None) if canonical_id_from_entity_uri(str(s))})
    if not entity_uris:
        return InstrumentResult.unwired(
            code=NO_TYPED_ENTITIES,
            reason=(
                "graph/knowledge carries no typed project entities; no belief basis "
                "was computed. Run `science graph build` first."
            ),
        )

    rows: list[EntityBasis] = []
    for uri in entity_uris:
        targets = _evidence_targets_for_uri(knowledge, URIRef(uri))
        units = collect_evidence_units(knowledge, provenance, targets)
        canonical = canonical_id_from_entity_uri(uri)
        assert canonical is not None  # filtered above
        rows.append(
            EntityBasis(
                entity_id=canonical,
                uri=uri,
                target_uris=tuple(sorted(str(t) for t in targets)),
                unit_keys=tuple(sorted(unit_key(u) for u in units)),
                policy_id=policy.policy_id,
                policy_version=policy.version,
            )
        )
    return InstrumentResult.from_rows(rows)


def basis_digest(bases: Iterable[EntityBasis]) -> str:
    """Order-independent sha256 over a whole capture.

    Persisted in the snapshot envelope and in the run record so a later
    validation can prove it compared against the same starting state.
    """
    payload = json.dumps(
        [b.model_dump(mode="json") for b in sorted(bases, key=lambda b: (b.uri, b.entity_id))],
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


#: Bump when the shape of EntityBasis or the snapshot envelope changes.
BASIS_SNAPSHOT_SCHEMA_VERSION = 1


class SnapshotIntegrityError(ValueError):
    """A snapshot could not be trusted: bad digest, or a schema version this code cannot read."""


class BasisSnapshot(BaseModel):
    """A sealed capture. The digest is verified on load, never merely carried."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: int
    digest: str
    rows: tuple[EntityBasis, ...]


def build_snapshot(rows: Iterable[EntityBasis]) -> BasisSnapshot:
    sealed = tuple(rows)
    return BasisSnapshot(
        schema_version=BASIS_SNAPSHOT_SCHEMA_VERSION,
        digest=basis_digest(sealed),
        rows=sealed,
    )


def load_snapshot(payload: object) -> BasisSnapshot:
    """Parse and VERIFY a snapshot. Raises rather than returning something untrustworthy.

    Takes `object` and validates: a top-level array or scalar must raise
    pydantic's ValidationError (a ValueError), not a TypeError from `**` unpacking
    that the CLI handler would let through as a belief movement.
    """
    snapshot = BasisSnapshot.model_validate(payload)
    if snapshot.schema_version != BASIS_SNAPSHOT_SCHEMA_VERSION:
        raise SnapshotIntegrityError(
            f"snapshot schema_version {snapshot.schema_version} != {BASIS_SNAPSHOT_SCHEMA_VERSION}; "
            "this snapshot was written by a different version of the basis format"
        )
    recomputed = basis_digest(snapshot.rows)
    if recomputed != snapshot.digest:
        raise SnapshotIntegrityError(f"snapshot digest mismatch: stored {snapshot.digest}, recomputed {recomputed}")
    return snapshot


class BasisDelta(BaseModel):
    """One pre-existing entity whose belief basis moved."""

    model_config = ConfigDict(frozen=True)

    entity_id: str
    changed: tuple[str, ...]
    detail: str


def compare_bases(before: Iterable[EntityBasis], after: Iterable[EntityBasis]) -> list[BasisDelta]:
    """Deltas for PRE-EXISTING entities only.

    An entity present only in `after` is new and yields no delta — it had no
    before-value. Its effect on any existing entity surfaces as a delta on that
    entity. An entity present only in `before` was removed, which can move belief
    elsewhere and is reported.
    """
    before_by_id = {b.entity_id: b for b in before}
    after_by_id = {a.entity_id: a for a in after}

    deltas: list[BasisDelta] = []
    for entity_id in sorted(before_by_id):
        old = before_by_id[entity_id]
        new = after_by_id.get(entity_id)
        if new is None:
            deltas.append(
                BasisDelta(
                    entity_id=entity_id,
                    changed=("removed",),
                    detail="entity present before the run, absent after",
                )
            )
            continue
        changed: list[str] = []
        if old.target_uris != new.target_uris:
            changed.append("targets")
        if old.unit_keys != new.unit_keys:
            changed.append("units")
        if (old.policy_id, old.policy_version) != (new.policy_id, new.policy_version):
            changed.append("policy")
        if changed:
            deltas.append(
                BasisDelta(
                    entity_id=entity_id,
                    changed=tuple(changed),
                    detail=(
                        f"targets {len(old.target_uris)}->{len(new.target_uris)}, "
                        f"units {len(old.unit_keys)}->{len(new.unit_keys)}, "
                        f"policy {old.policy_id}/{old.policy_version}->{new.policy_id}/{new.policy_version}"
                    ),
                )
            )
    return deltas

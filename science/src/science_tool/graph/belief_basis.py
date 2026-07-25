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

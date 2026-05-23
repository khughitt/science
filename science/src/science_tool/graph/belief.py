"""Independence-aware evidence aggregation -> ordinal belief (design §2/§3, Phase 1)."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from rdflib import Graph, RDF, URIRef
from rdflib.namespace import PROV

from .belief_weights import (
    CIRCULAR, DIAGNOSTIC_ROLES, EVIDENCE_ROLE_RANK, EVIDENCE_TYPE_RANK,
    GATED_PROXY, INDEPENDENT, ROLE_DIRECT_TEST, SCOPE_WHOLE_CLAIM, SHARED_SOURCE,
    STRENGTH_RANK, normalize_evidence_type,
)
from .io import CITO_NS, SCI_NS

EVIDENCE_LINE_CLASS = SCI_NS.EvidenceLine  # rdf:type minted by materialize.py _kind_class_name("evidence-line")


@dataclass(frozen=True)
class EvidenceUnit:
    line_uri: str
    stance: str                       # "supports" | "disputes"
    strength: str | None
    independence: str | None
    independence_group: str | None
    evidence_role: str | None
    evidence_type: str | None
    dispute_scope: str | None
    proxy_directness: str | None
    has_measurement_model: bool
    source: str | None
    observability_keys: tuple[str, ...]


_OBSERVABILITY = {
    "shared_dataset": SCI_NS.sharedDataset,
    "shared_lab": SCI_NS.sharedLab,
    "shared_platform": SCI_NS.sharedPlatform,
    "shared_cohort": SCI_NS.sharedCohort,
}


def _lit(graph: Graph, subject: URIRef, predicate: URIRef) -> str | None:
    for _, _, value in graph.triples((subject, predicate, None)):
        return str(value)
    return None


def _read_unit(provenance: Graph, line: URIRef, stance: str) -> EvidenceUnit:
    obs = tuple(name for name, pred in _OBSERVABILITY.items() if _lit(provenance, line, pred))
    return EvidenceUnit(
        line_uri=str(line),
        stance=stance,
        strength=_lit(provenance, line, SCI_NS.evidenceStrength),
        independence=_lit(provenance, line, SCI_NS.evidenceIndependence),
        independence_group=_lit(provenance, line, SCI_NS.independenceGroup),
        evidence_role=_lit(provenance, line, SCI_NS.evidenceRole),
        evidence_type=_lit(provenance, line, SCI_NS.evidenceType),
        dispute_scope=_lit(provenance, line, SCI_NS.disputeScope),
        proxy_directness=_lit(provenance, line, SCI_NS.proxyDirectness),
        has_measurement_model=_lit(provenance, line, SCI_NS.measurementModel) is not None,
        # Informational only; NOT consumed by Phase 1 aggregation. A line has multiple
        # prov:wasDerivedFrom objects (its source file AND source entity); first wins.
        source=_lit(provenance, line, PROV.wasDerivedFrom),
        observability_keys=obs,
    )


def collect_evidence_units(
    knowledge: Graph, provenance: Graph, targets: Iterable[URIRef]
) -> list[EvidenceUnit]:
    """Counted units are ONLY cito edges whose subject is an evidence-line (design §Prerequisite).

    Edge + rdf:type are read from `knowledge`; per-line metadata from `provenance`.
    `targets` is the expanded target set; callers pass `_evidence_targets_for_uri(...)` so a
    hypothesis sees its linked claims' evidence. Lines are de-duped by URI so a line bearing on
    multiple targets counts once.
    """
    units: list[EvidenceUnit] = []
    seen: set[str] = set()
    for target in targets:
        for predicate, stance in ((CITO_NS.supports, "supports"), (CITO_NS.disputes, "disputes")):
            for subject, _, _ in knowledge.triples((None, predicate, target)):
                if (subject, RDF.type, EVIDENCE_LINE_CLASS) not in knowledge:
                    continue
                if str(subject) in seen:
                    continue
                seen.add(str(subject))
                units.append(_read_unit(provenance, subject, stance))
    return units


def quality_key(u: EvidenceUnit) -> tuple[int, int, int]:
    return (
        EVIDENCE_TYPE_RANK.get(normalize_evidence_type(u.evidence_type), 0),
        EVIDENCE_ROLE_RANK.get(u.evidence_role or "", 0),
        STRENGTH_RANK.get(u.strength or "", 0),
    )


@dataclass
class ReducedUnits:
    kept: list[EvidenceUnit]            # per (group, stance) winner + each ungrouped line
    collapsed: list[EvidenceUnit]       # per (group, stance) losers dropped (any independence type)
    excluded_circular: list[EvidenceUnit]
    flagged_ungrouped: list[EvidenceUnit]
    contested_groups: set[str]          # real groups holding BOTH a support and a dispute winner


def reduce_units(units: list[EvidenceUnit]) -> ReducedUnits:
    excluded_circular: list[EvidenceUnit] = []
    flagged_ungrouped: list[EvidenceUnit] = []
    collapsed: list[EvidenceUnit] = []
    winners: dict[tuple[str, str], EvidenceUnit] = {}      # (group_or_line_token, stance) -> winner
    real_groups_by_stance: dict[str, set[str]] = {"supports": set(), "disputes": set()}

    for u in units:
        if u.independence in (SHARED_SOURCE, CIRCULAR) and not u.independence_group:
            flagged_ungrouped.append(u)                    # "collapse to what?" undefined (QA #2b)
            continue
        if u.independence == CIRCULAR:
            excluded_circular.append(u)
            continue
        if u.independence_group:
            key = (u.independence_group, u.stance)
            real_groups_by_stance[u.stance].add(u.independence_group)
        else:
            key = (f"__line__:{u.line_uri}", u.stance)      # ungrouped lines never merge
        if key not in winners:
            winners[key] = u
        elif quality_key(u) > quality_key(winners[key]):
            collapsed.append(winners[key])
            winners[key] = u
        else:
            collapsed.append(u)

    contested_groups = real_groups_by_stance["supports"] & real_groups_by_stance["disputes"]
    return ReducedUnits(
        kept=list(winners.values()),
        collapsed=collapsed,
        excluded_circular=excluded_circular,
        flagged_ungrouped=flagged_ungrouped,
        contested_groups=contested_groups,
    )


def is_diagnostic(u: EvidenceUnit) -> bool:
    """negative_control / model_criticism: separate ledger rows, never FOR/AGAINST mass."""
    return (u.evidence_role or "") in DIAGNOSTIC_ROLES


def is_proxy_gated(u: EvidenceUnit) -> bool:
    """Rule 5: indirect/derived proxy with no measurement_model cannot contribute at full weight."""
    return (u.proxy_directness or "") in GATED_PROXY and not u.has_measurement_model


def is_qualifying_direct_test(u: EvidenceUnit) -> bool:
    return u.evidence_role == ROLE_DIRECT_TEST and not is_proxy_gated(u)


def is_decisive_refutation(u: EvidenceUnit) -> bool:
    """Rule 3: ONLY an independent strong direct_test whole_claim dispute caps belief.

    whole_claim is the default when scope is unset; model_criticism and scoped disputes
    (generalization/mechanism/boundary) set `contested` but never eliminate. The proxy gate
    (rule 5) applies symmetrically: an ungated indirect/derived proxy direct-test cannot be
    decisive either (`is_qualifying_direct_test` already encodes role + proxy gate).
    """
    return (
        u.stance == "disputes"
        and u.independence == INDEPENDENT
        and u.strength == "strong"
        and is_qualifying_direct_test(u)
        and (u.dispute_scope or SCOPE_WHOLE_CLAIM) == SCOPE_WHOLE_CLAIM
    )


class BeliefMagnitude(StrEnum):
    SPECULATIVE = "speculative"
    FRAGILE = "fragile"
    SUPPORTED = "supported"
    WELL_SUPPORTED = "well_supported"


_MAG_ORDER = [
    BeliefMagnitude.SPECULATIVE,
    BeliefMagnitude.FRAGILE,
    BeliefMagnitude.SUPPORTED,
    BeliefMagnitude.WELL_SUPPORTED,
]


@dataclass
class BeliefResult:
    magnitude: BeliefMagnitude
    contested: bool
    capped_by_refutation: bool
    support_units: list[EvidenceUnit]
    dispute_units: list[EvidenceUnit]
    diagnostics: list[EvidenceUnit]
    contested_groups: set[str]
    excluded: list[EvidenceUnit]
    flagged_ungrouped: list[EvidenceUnit]

    def display(self) -> str:
        return f"{self.magnitude.value} (contested)" if self.contested else self.magnitude.value


def aggregate_belief(units: list[EvidenceUnit]) -> BeliefResult:
    reduced = reduce_units(units)
    cg = reduced.contested_groups

    support = [u for u in reduced.kept if u.stance == "supports" and not is_diagnostic(u)]
    dispute = [u for u in reduced.kept if u.stance == "disputes" and not is_diagnostic(u)]
    diagnostics = [u for u in reduced.kept if is_diagnostic(u)]

    n_support = len(support)
    # A support unit in a contested group is not clean corroboration (stance-aware-collapse
    # decision): well_supported needs >=2 *clean* units, one of which is a qualifying direct test.
    clean_support = [u for u in support if u.independence_group not in cg]
    clean_direct_test = any(is_qualifying_direct_test(u) for u in clean_support)
    decisive = any(is_decisive_refutation(u) for u in dispute)

    if n_support == 0:
        magnitude = BeliefMagnitude.SPECULATIVE
    elif n_support == 1:
        magnitude = BeliefMagnitude.FRAGILE
    elif clean_direct_test and len(clean_support) >= 2:
        magnitude = BeliefMagnitude.WELL_SUPPORTED
    else:
        magnitude = BeliefMagnitude.SUPPORTED

    capped = False
    if decisive and _MAG_ORDER.index(magnitude) > _MAG_ORDER.index(BeliefMagnitude.FRAGILE):
        magnitude = BeliefMagnitude.FRAGILE
        capped = True

    contested = (
        bool(dispute)
        or any(u.stance == "disputes" for u in diagnostics)
        or bool(cg)
    )

    return BeliefResult(
        magnitude=magnitude,
        contested=contested,
        capped_by_refutation=capped,
        support_units=support,
        dispute_units=dispute,
        diagnostics=diagnostics,
        contested_groups=cg,
        excluded=reduced.excluded_circular,
        flagged_ungrouped=reduced.flagged_ungrouped,
    )

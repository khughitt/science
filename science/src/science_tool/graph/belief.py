"""Independence-aware evidence aggregation -> ordinal belief (design §2/§3, Phase 1)."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field, replace
from enum import StrEnum

from rdflib import RDF, Graph, Literal, URIRef
from rdflib.namespace import PROV

from .belief_policy import DEFAULT_BELIEF_POLICY, BeliefPolicy
from .belief_weights import CIRCULAR, INDEPENDENT, SHARED_SOURCE, normalize_evidence_type
from .dataset_independence import DerivedCommitmentMetadata, committed_metadata_by_line
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
    is_reference_dataset: bool = False
    # Oriented posterior (Task 3a). `target_polarity` is the AUTHORED sign of the
    # target proposition this line bears on (None when the target has no polarity);
    # `quant_beta`/`quant_prob_sign` are the fitted posterior summary. All default
    # to None so the ordinal magnitude path (aggregate_belief) is untouched.
    target_polarity: str | None = None
    quant_beta: float | None = None
    quant_prob_sign: float | None = None
    # Authored confidence (Spec 5 Slice B). The materialized SCI_NS.confidence value, read
    # for authored assertions. LAST field so the many positional EvidenceUnit(...) test
    # constructors (12 positional args through observability_keys) stay behavior-neutral.
    confidence: float | None = None
    # Dataset-QA seam (Spec 5). Dependence-role datasets this EMPIRICAL line rests on whose
    # structural QA failed (populated only for empirical lines at materialization). LAST field
    # for positional stability of the many EvidenceUnit(...) test constructors.
    qa_failed_datasets: tuple[str, ...] = ()


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


def _float_lit(provenance: Graph, subject: URIRef, predicate: URIRef) -> float | None:
    value = _lit(provenance, subject, predicate)
    return None if value is None else float(value)


def _read_unit(
    provenance: Graph,
    line: URIRef,
    stance: str,
    reference_dataset_uris: frozenset[str],
    target_polarity: str | None,
) -> EvidenceUnit:
    obs = tuple(name for name, pred in _OBSERVABILITY.items() if _lit(provenance, line, pred))
    derived_from = {str(o) for _, _, o in provenance.triples((line, PROV.wasDerivedFrom, None))}
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
        # Reference detection scans ALL wasDerivedFrom objects (the set above), unlike the
        # first-wins `source` field — the reference dataset URI need not be the first object.
        is_reference_dataset=bool(derived_from & reference_dataset_uris),
        target_polarity=target_polarity,
        quant_beta=_float_lit(provenance, line, SCI_NS.quantBeta),
        quant_prob_sign=_float_lit(provenance, line, SCI_NS.quantProbSign),
        confidence=_float_lit(provenance, line, SCI_NS.confidence),
        qa_failed_datasets=tuple(
            sorted(str(o) for o in provenance.objects(line, SCI_NS.qaFailedDataset))
        ),
    )


def _with_derived_commitment(
    unit: EvidenceUnit,
    derived: dict[URIRef, DerivedCommitmentMetadata],
) -> EvidenceUnit:
    metadata = derived.get(URIRef(unit.line_uri))
    if metadata is None:
        return unit
    if unit.independence in (CIRCULAR, SHARED_SOURCE, INDEPENDENT):
        return unit
    return replace(
        unit,
        independence=metadata.independence,
        independence_group=metadata.independence_group,
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
    reference_dataset_uris = frozenset(
        str(s) for s, _, _ in knowledge.triples((None, SCI_NS.sourceClass, Literal("reference")))
    )
    units: list[EvidenceUnit] = []
    seen: set[str] = set()
    target_set = frozenset(targets)
    for target in target_set:
        # Authored sign of THIS target (materialized on the proposition URI). A line
        # de-dupes to the first target that claims it, so it inherits that target's
        # polarity for the oriented quant contribution.
        target_polarity = _lit(provenance, target, SCI_NS.polarity)
        for predicate, stance in ((CITO_NS.supports, "supports"), (CITO_NS.disputes, "disputes")):
            for subject, _, _ in knowledge.triples((None, predicate, target)):
                if (subject, RDF.type, EVIDENCE_LINE_CLASS) not in knowledge:
                    continue
                if str(subject) in seen:
                    continue
                seen.add(str(subject))
                units.append(
                    _read_unit(provenance, subject, stance, reference_dataset_uris, target_polarity)
                )
    derived = committed_metadata_by_line(provenance, target_set)
    return [_with_derived_commitment(unit, derived) for unit in units]


def quality_key(u: EvidenceUnit, *, policy: BeliefPolicy = DEFAULT_BELIEF_POLICY) -> tuple[int, int, int, int]:
    # A-D4: the curation discount also routes through winner-selection. It is the LAST
    # (least-significant) component, so a reference-backed unit loses only to an otherwise
    # equal (type/role/strength) non-reference unit — it never crosses those axes.
    return (
        policy.evidence_type_rank.get(normalize_evidence_type(u.evidence_type), 0),
        policy.evidence_role_rank.get(u.evidence_role or "", 0),
        policy.strength_rank.get(u.strength or "", 0),
        -policy.curation_step_penalty if u.is_reference_dataset else 0,
    )


@dataclass
class ReducedUnits:
    kept: list[EvidenceUnit]            # per (group, stance) winner + each ungrouped line
    collapsed: list[EvidenceUnit]       # per (group, stance) losers dropped (any independence type)
    excluded_circular: list[EvidenceUnit]
    flagged_ungrouped: list[EvidenceUnit]
    contested_groups: set[str]          # real groups holding BOTH a support and a dispute winner


def reduce_units(units: list[EvidenceUnit], *, policy: BeliefPolicy = DEFAULT_BELIEF_POLICY) -> ReducedUnits:
    excluded_circular: list[EvidenceUnit] = []
    flagged_ungrouped: list[EvidenceUnit] = []
    collapsed: list[EvidenceUnit] = []
    winners: dict[tuple[str, str], EvidenceUnit] = {}      # (group_or_line_token, stance) -> winner
    real_groups_by_stance: dict[str, set[str]] = {"supports": set(), "disputes": set()}

    for u in units:
        if u.independence in (policy.shared_source_token, policy.circular_token) and not u.independence_group:
            flagged_ungrouped.append(u)                    # "collapse to what?" undefined (QA #2b)
            continue
        if u.independence == policy.circular_token:
            excluded_circular.append(u)
            continue
        if u.independence_group:
            key = (u.independence_group, u.stance)
            real_groups_by_stance[u.stance].add(u.independence_group)
        else:
            key = (f"__line__:{u.line_uri}", u.stance)      # ungrouped lines never merge
        if key not in winners:
            winners[key] = u
        elif quality_key(u, policy=policy) > quality_key(winners[key], policy=policy):
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


def is_diagnostic(u: EvidenceUnit, *, policy: BeliefPolicy = DEFAULT_BELIEF_POLICY) -> bool:
    """negative_control / model_criticism: separate ledger rows, never FOR/AGAINST mass."""
    return (u.evidence_role or "") in policy.diagnostic_roles


def is_authored_assertion(u: EvidenceUnit, *, policy: BeliefPolicy = DEFAULT_BELIEF_POLICY) -> bool:
    """Pure type contract: a unit is an authored assertion iff its normalized evidence_type
    equals policy.authored_assertion_type (default 'expert_judgment'). dataset_usage is NOT
    inspected — recognition keys solely on the type (design §Goal)."""
    return normalize_evidence_type(u.evidence_type) == policy.authored_assertion_type


def is_qa_failed(u: EvidenceUnit) -> bool:
    """Pre-computed fact (set at materialization, empirical-only): the unit rests on >=1
    structurally-QA-failed dependence dataset. Belief reads it; it does not recompute QA."""
    return bool(u.qa_failed_datasets)


def _authored_assertion_counts(u: EvidenceUnit, *, policy: BeliefPolicy = DEFAULT_BELIEF_POLICY) -> bool:
    """Range-validated confidence gate. Confidence is a GATE not a dial: it admits/rejects a
    unit but never scales it. Range check precedes the threshold so confidence=1.2 cannot
    slip past authored_min_confidence."""
    c = u.confidence
    return c is not None and 0.0 <= c <= 1.0 and c >= policy.authored_min_confidence


def is_proxy_gated(u: EvidenceUnit, *, policy: BeliefPolicy = DEFAULT_BELIEF_POLICY) -> bool:
    """Rule 5: indirect/derived proxy with no measurement_model cannot contribute at full weight."""
    return (u.proxy_directness or "") in policy.gated_proxy and not u.has_measurement_model


def is_qualifying_direct_test(u: EvidenceUnit, *, policy: BeliefPolicy = DEFAULT_BELIEF_POLICY) -> bool:
    # Refutation symmetry (Slice B): an authored assertion is never a qualifying direct test,
    # so it can neither satisfy WELL_SUPPORTED's direct-test gate nor be a decisive refutation.
    return (
        u.evidence_role == policy.direct_test_role
        and not is_proxy_gated(u, policy=policy)
        and not is_authored_assertion(u, policy=policy)
        and not is_qa_failed(u)
    )


def is_decisive_refutation(u: EvidenceUnit, *, policy: BeliefPolicy = DEFAULT_BELIEF_POLICY) -> bool:
    """Rule 3: ONLY an independent strong direct_test whole_claim dispute caps belief.

    whole_claim is the default when scope is unset; model_criticism and scoped disputes
    (generalization/mechanism/boundary) set `contested` but never eliminate. The proxy gate
    (rule 5) applies symmetrically: an ungated indirect/derived proxy direct-test cannot be
    decisive either (`is_qualifying_direct_test` already encodes role + proxy gate).
    """
    return (
        u.stance == "disputes"
        and u.independence == policy.independent_token
        and u.strength == policy.decisive_strength
        and is_qualifying_direct_test(u, policy=policy)
        and (u.dispute_scope or policy.scope_whole_claim) == policy.scope_whole_claim
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


def _contested_groups_for(support: list[EvidenceUnit], dispute: list[EvidenceUnit]) -> set[str]:
    """Independence groups present on BOTH a support and a dispute unit (None/empty ignored)."""
    sup_groups = {u.independence_group for u in support if u.independence_group}
    dis_groups = {u.independence_group for u in dispute if u.independence_group}
    return sup_groups & dis_groups


def _base_magnitude(
    support: list[EvidenceUnit],
    contested_groups: set[str],
    *,
    policy: BeliefPolicy = DEFAULT_BELIEF_POLICY,
) -> BeliefMagnitude:
    """Ordinal magnitude from clean support alone (SPECULATIVE→FRAGILE→SUPPORTED→WELL_SUPPORTED),
    before any refutation/authored/QA cap. Units in a contested group are not clean corroboration."""
    n_support = len(support)
    # A support unit in a contested group is not clean corroboration (stance-aware-collapse
    # decision): well_supported needs >=N *clean* units, one of which is a qualifying direct test.
    clean_support = [u for u in support if u.independence_group not in contested_groups]
    clean_direct_test = any(is_qualifying_direct_test(u, policy=policy) for u in clean_support)
    if n_support == 0:
        return BeliefMagnitude.SPECULATIVE
    if n_support == 1:
        return BeliefMagnitude.FRAGILE
    if (not policy.well_supported_requires_direct_test or clean_direct_test) and len(
        clean_support
    ) >= policy.well_supported_min_clean_support:
        return BeliefMagnitude.WELL_SUPPORTED
    return BeliefMagnitude.SUPPORTED


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
    policy_id: str = DEFAULT_BELIEF_POLICY.policy_id
    policy_version: str = DEFAULT_BELIEF_POLICY.version
    authored_capped: bool = False
    excluded_authored_confidence: list[EvidenceUnit] = field(default_factory=list)
    qa_dataset_capped: bool = False
    qa_failed_datasets: tuple[str, ...] = ()

    def display(self) -> str:
        return f"{self.magnitude.value} (contested)" if self.contested else self.magnitude.value


def aggregate_belief(units: list[EvidenceUnit], *, policy: BeliefPolicy = DEFAULT_BELIEF_POLICY) -> BeliefResult:
    # Gate authored assertions on the RAW units list, BEFORE reduce_units (design §Pipeline
    # ordering). A gate-failing authored unit must have zero downstream effect — it must not
    # win a collapse, perturb contested_groups, or flip contested — so it never enters reduction.
    admitted: list[EvidenceUnit] = []
    excluded_authored_confidence: list[EvidenceUnit] = []
    for u in units:
        if is_authored_assertion(u, policy=policy) and not _authored_assertion_counts(u, policy=policy):
            excluded_authored_confidence.append(u)
        else:
            admitted.append(u)

    reduced = reduce_units(admitted, policy=policy)
    cg = reduced.contested_groups

    support = [u for u in reduced.kept if u.stance == "supports" and not is_diagnostic(u, policy=policy)]
    dispute = [u for u in reduced.kept if u.stance == "disputes" and not is_diagnostic(u, policy=policy)]
    diagnostics = [u for u in reduced.kept if is_diagnostic(u, policy=policy)]

    decisive = any(is_decisive_refutation(u, policy=policy) for u in dispute)
    magnitude = _base_magnitude(support, cg, policy=policy)

    capped = False
    if decisive and _MAG_ORDER.index(magnitude) > _MAG_ORDER.index(BeliefMagnitude.FRAGILE):
        magnitude = BeliefMagnitude.FRAGILE
        capped = True

    # Authored-only ceiling (design §The ceiling): when EVERY counted support unit is an
    # authored assertion, belief cannot exceed authored_only_ceiling. Applied after the
    # refutation cap; a no-op when the magnitude is already at/below the ceiling.
    authored_capped = False
    if support and all(is_authored_assertion(u, policy=policy) for u in support):
        ceiling = BeliefMagnitude(policy.authored_only_ceiling)
        if _MAG_ORDER.index(magnitude) > _MAG_ORDER.index(ceiling):
            magnitude = ceiling
            authored_capped = True

    # Dataset-QA ceiling (design §The QA ceiling). When counted empirical support rests on a
    # structurally-QA-failed dataset and the QA-clean support cannot reach the achieved
    # magnitude alone, hard-cap to qa_failed_dataset_ceiling. Applied after the refutation and
    # authored caps.
    qa_dataset_capped = False
    qa_failed_datasets: tuple[str, ...] = ()
    qa_failed_support = [u for u in support if is_qa_failed(u)]
    if qa_failed_support:
        clean_support_units = [u for u in support if not is_qa_failed(u)]
        clean_cg = _contested_groups_for(clean_support_units, dispute)
        clean_only = _base_magnitude(clean_support_units, clean_cg, policy=policy)
        if _MAG_ORDER.index(clean_only) < _MAG_ORDER.index(magnitude):
            ceiling = BeliefMagnitude(policy.qa_failed_dataset_ceiling)
            if _MAG_ORDER.index(magnitude) > _MAG_ORDER.index(ceiling):
                magnitude = ceiling
                qa_dataset_capped = True
                qa_failed_datasets = tuple(
                    sorted({d for u in qa_failed_support for d in u.qa_failed_datasets})
                )

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
        policy_id=policy.policy_id,
        policy_version=policy.version,
        authored_capped=authored_capped,
        excluded_authored_confidence=excluded_authored_confidence,
        qa_dataset_capped=qa_dataset_capped,
        qa_failed_datasets=qa_failed_datasets,
    )

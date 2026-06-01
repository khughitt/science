# science:code
# status: library
# task_ids: [t065]
# science:end
"""Build EvidenceUnits for the L1 patch from the real q14 slice.

Two evidence routes per gene→disease edge (RFC §3.5, prior↔posterior duality):

  * ELICITED / editorial — the curated panel asserts "gene G is a causal gene of
    disease D". Provenance: ProvenanceType.EDITORIAL, ai-drafted/human-ratified.
    Modelled as `evidence_type=expert_judgment`, `evidence_role=background_constraint`
    (an asserted prior, never a direct empirical test), `is_reference_dataset=True`
    so the shipped CURATION_STEP_PENALTY gives it structurally lower status.
  * DISCOVERED / empirical — PubTator literature co-occurrence. Modelled as
    `evidence_type=literature`, `evidence_role=proxy_support`,
    `proxy_directness=indirect` + no measurement model → a gated proxy
    (PROXY_STEP_PENALTY). High-ubiquity genes (co-occur with ~every disease) are
    pure publication gravity → `independence=shared-source`, one shared group.

Only the FIXTURE numbers are real; the mapping to evidence-schema fields is the
prototype's modelling choice (documented here, contestable — that is the point of
a prototype feeding RFC fork §12.3).
"""
from __future__ import annotations

import json
from pathlib import Path

from science_tool.graph.belief import EvidenceUnit

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "q14_slice.json"

# All genes that co-occur with (about) every disease share ONE source mechanism —
# corpus-wide publication gravity — so their literature evidence is not
# independent corroboration. They route through a single shared-source group.
PUBGRAV_GROUP = "publication-gravity"


def load_fixture(path: Path = FIXTURE) -> dict:
    return json.loads(Path(path).read_text())


def pubgravity_threshold(fixture: dict) -> int:
    """Ubiquity at/above which literature co-occurrence is treated as pub-gravity.

    Default = the slice's 99th ubiquity percentile. The universal genes in the
    slice sit at ubiquity == n_diseases (co-occur with every disease) and clear
    this comfortably; no curated panel gene does.
    """
    return int(fixture["ubiquity_quantiles"]["0.99"])


def _tier_strength(disease: dict) -> str:
    """ClinGen-strict-eligible panels assert at 'strong'; OMIM/GeneReviews-broad
    (e.g. HSP) assert only at 'moderate' — the provenance-qualified weaker panel."""
    return "strong" if disease.get("clingen_strict_eligible") else "moderate"


def _editorial_unit(disease: dict, gene: dict, idx: int) -> EvidenceUnit:
    return EvidenceUnit(
        line_uri=f"edge/{gene['symbol']}/editorial#{idx}",
        stance="supports",
        strength=_tier_strength(disease),
        independence="independent",
        independence_group=None,
        evidence_role="background_constraint",   # an asserted prior, not a test
        evidence_type="expert_judgment",
        dispute_scope=None,
        proxy_directness=None,
        has_measurement_model=False,
        source=disease["panel_source"],
        observability_keys=(),
        is_reference_dataset=True,                # curated/editorial -> step penalty
    )


def _literature_unit(gene: dict, idx: int, pubgrav: int) -> EvidenceUnit:
    is_pubgrav = gene["ubiquity"] >= pubgrav
    return EvidenceUnit(
        line_uri=f"edge/{gene['symbol']}/literature#{idx}",
        stance="supports",
        strength="moderate",
        independence="shared-source" if is_pubgrav else "independent",
        independence_group=PUBGRAV_GROUP if is_pubgrav else None,
        evidence_role="proxy_support",
        evidence_type="literature",
        dispute_scope=None,
        proxy_directness="indirect",              # co-occurrence is an indirect proxy
        has_measurement_model=False,              # -> gated proxy (PROXY_STEP_PENALTY)
        source="pubtator-cooccurrence",
        observability_keys=(),
        is_reference_dataset=False,
    )


def build_edge_units(disease: dict, gene: dict, pubgrav: int) -> list[EvidenceUnit]:
    """Per gene→disease EDGE: the two provenance routes that bear on this edge.

    Panel genes carry both an editorial assertion and literature co-occurrence;
    universal (non-panel) genes carry only literature co-occurrence.
    """
    units: list[EvidenceUnit] = []
    if gene["in_panel"]:
        units.append(_editorial_unit(disease, gene, 0))
    if gene["cooc"] > 0:
        units.append(_literature_unit(gene, 0, pubgrav))
    return units


def build_signature_units(disease: dict, pubgrav: int) -> list[EvidenceUnit]:
    """PATCH-level claim: "D's PubTator gene profile reflects D-specific biology".

    One literature support unit per co-occurring gene. Specific genes are
    independent supports; universal genes all share the publication-gravity group
    and collapse under the reduction — the independence-discounted-fusion demo.
    """
    units: list[EvidenceUnit] = []
    for i, gene in enumerate(disease["genes"]):
        if gene["cooc"] > 0:
            units.append(_literature_unit(gene, i, pubgrav))
    return units

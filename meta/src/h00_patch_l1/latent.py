# science:code
# status: library
# task_ids: [t066]
# science:end
"""Latent-construct / measurement-model bias CORRECTION (RFC §8.1 / R3).

t065 *discounted* publication gravity — it collapsed the shared-source
double-count so one corpus-wide mechanism could not be counted N times. It never
*subtracted* the latent attention axis: each surviving co-occurrence signal was
still biased by how much its gene is studied at all. This module subtracts it.

Generative measurement model. Observed literature co-occurrence ``C_gd`` is a
biased measurement of the latent biological association ``A_gd``, the bias being
publication ATTENTION — how much gene ``g`` and disease ``d`` are studied at all:

    log E[C_gd]  =  log N + α_g + β_d + A_gd
    α_g = log(C_g. / N)      gene attention    (publication gravity, gene axis)
    β_d = log(C_.d / N)      disease attention (publication gravity, disease axis)

The two-way independence expectation (the null ``A_gd = 0``) is
``E0[C_gd] = C_g.·C_.d / N``. The corrected association is the residual on the
log scale — exactly pointwise mutual information, with the latent attention axes
SUBTRACTED OFF:

    PMI(g,d) = log( C_gd / E0[C_gd] ) = log( C_gd·N / (C_g.·C_.d) )
             = log(C_gd / N) − α_g − β_d

    PMI > 0 : co-occurs MORE than attention alone predicts → specific association
    PMI ≈ 0 : fully explained by attention
    PMI < 0 : co-occurs LESS than attention predicts (a universal gene "diluted")

``PPMI = max(PMI, 0)`` is the established debiased co-occurrence measure. ``α_g``
(the per-gene attention vector) IS the data-driven latent nuisance axis; a
low-rank factorization of the PPMI matrix would be the shared latent COMMON
coordinate (RFC §2 glue) — the L2/glue successor, noted, not built here.

This module reuses the shipped belief machinery (D-005): the correction decides
*whether a literature unit is specific support at all*, then the existing
`aggregate_belief` / `belief_scalar` / opinion view run unchanged on the survivors.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from science_tool.graph.belief import EvidenceUnit, aggregate_belief
from science_tool.graph.belief_scalar import belief_scalar

from .opinion import opinion_from_scores


def gene_attention(gene_marginal: int, grand_total: int) -> float:
    """α_g = log(C_g./N): the gene's publication-attention axis (log share)."""
    return math.log(gene_marginal / grand_total)


def disease_attention(disease_marginal: int, grand_total: int) -> float:
    """β_d = log(C_.d/N): the disease's publication-attention axis (log share)."""
    return math.log(disease_marginal / grand_total)


def pmi(cooc: int, gene_marginal: int, disease_marginal: int, grand_total: int) -> float | None:
    """Attention-subtracted association (PMI). None when there is no co-occurrence."""
    if cooc <= 0:
        return None
    return math.log((cooc * grand_total) / (gene_marginal * disease_marginal))


@dataclass(frozen=True)
class CorrectedAssociation:
    gene: str
    in_panel: bool
    raw_cooc: int
    gene_attention: float       # α_g (log gene-attention share)
    pmi: float | None
    specific: bool              # PMI > 0 : survives attention subtraction

    @property
    def ppmi(self) -> float:
        return max(self.pmi, 0.0) if self.pmi is not None else 0.0


def correct_gene(disease: dict, gene: dict, grand_total: int) -> CorrectedAssociation:
    p = pmi(gene["cooc"], gene["gene_marginal"], disease["disease_marginal"], grand_total)
    return CorrectedAssociation(
        gene=gene["symbol"],
        in_panel=gene["in_panel"],
        raw_cooc=gene["cooc"],
        gene_attention=gene_attention(gene["gene_marginal"], grand_total),
        pmi=p,
        specific=(p is not None and p > 0.0),
    )


def correct_disease(disease: dict, grand_total: int) -> list[CorrectedAssociation]:
    """Attention-corrected association for every gene in the disease's slice."""
    return [correct_gene(disease, g, grand_total) for g in disease["genes"]]


def _corrected_literature_unit(gene: dict, idx: int) -> EvidenceUnit:
    """A literature support unit that SURVIVED attention subtraction.

    No `publication-gravity` independence group: the correction has already
    removed the universal genes, so what remains is genuinely independent,
    attention-corrected co-occurrence. It is still a gated proxy — co-occurrence
    is an indirect proxy for biology even once the attention bias is gone (a
    deliberately conservative choice; see the interpretation's carry-forward on
    whether the correction earns measurement-model status).
    """
    return EvidenceUnit(
        line_uri=f"edge/{gene['symbol']}/literature-corrected#{idx}",
        stance="supports",
        strength="moderate",
        independence="independent",
        independence_group=None,
        evidence_role="proxy_support",
        evidence_type="literature",
        dispute_scope=None,
        proxy_directness="indirect",
        has_measurement_model=False,
        source="pubtator-cooccurrence-pmi-corrected",
        observability_keys=(),
        is_reference_dataset=False,
    )


def build_corrected_signature_units(disease: dict, grand_total: int) -> list[EvidenceUnit]:
    """Corrected patch claim: only genes whose co-occurrence SURVIVES attention
    subtraction (PMI>0) count as specific literature support.

    Contrast with the t065 discount, which collapsed the universal genes into a
    single shared-source unit but still *counted* it. Here the attention-only
    genes contribute no specific support at all — they are not emitted.
    """
    units: list[EvidenceUnit] = []
    for i, gene in enumerate(disease["genes"]):
        if correct_gene(disease, gene, grand_total).specific:
            units.append(_corrected_literature_unit(gene, i))
    return units


def corrected_fusion(disease: dict, grand_total: int) -> dict:
    """Patch-level fusion after attention subtraction (the t066 view)."""
    corrected = correct_disease(disease, grand_total)
    units = build_corrected_signature_units(disease, grand_total)
    result = aggregate_belief(units)
    scalar = belief_scalar(result)
    specific = [c for c in corrected if c.specific]
    return {
        "n_specific": len(specific),
        "n_attention_only": sum(1 for c in corrected if c.pmi is not None and not c.specific),
        "corrected_support_count": len(result.support_units),
        "corrected_support_score": scalar.massed_support_score,
        "magnitude": result.magnitude.value,
        "corrected_opinion": opinion_from_scores(scalar.massed_support_score, 0).as_dict(),
        "mean_specific_ppmi": (
            round(sum(c.ppmi for c in specific) / len(specific), 3) if specific else 0.0
        ),
    }


def three_way_report(disease: dict, pubgrav: int, grand_total: int) -> dict:
    """Naive → discounted (t065) → corrected (t066), side by side.

    `naive` counts every co-occurring gene; `discounted` collapses the
    publication-gravity group (t065); `corrected` subtracts the attention axis
    and keeps only PMI>0 genes (t066).
    """
    from .patch import build_patch_report  # local import avoids a module cycle

    fusion = build_patch_report(disease, pubgrav)["fusion"]
    corrected = corrected_fusion(disease, grand_total)
    return {
        "naive": {
            "support_count": fusion["naive_support_count"],
            "support_score": fusion["naive_support_score"],
            "opinion": fusion["naive_opinion"],
        },
        "discounted": {
            "support_count": fusion["discounted_support_count"],
            "support_score": fusion["discounted_support_score"],
            "opinion": fusion["discounted_opinion"],
        },
        "corrected": {
            "support_count": corrected["corrected_support_count"],
            "support_score": corrected["corrected_support_score"],
            "opinion": corrected["corrected_opinion"],
            "n_specific": corrected["n_specific"],
            "n_attention_only": corrected["n_attention_only"],
        },
    }

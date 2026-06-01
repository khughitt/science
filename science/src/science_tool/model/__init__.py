"""The science working model — a federated patchwork of epistemic neighborhoods.

Reusable machinery for the ``h00`` working model (RFC: meta
``doc/plans/2026-05-31-epistemic-causal-probabilistic-graph-model-design.md``),
built on the :mod:`science_tool.graph.belief` primitives:

  * :mod:`~science_tool.model.patch` — the epistemic-neighborhood **patch** as a TriG
    named graph (L1: belief + provenance), with independence-aware signature fusion;
  * :mod:`~science_tool.model.opinion` — the subjective-logic **opinion** view (an
    explicit, uncertainty-bearing derived read of belief scores);
  * :mod:`~science_tool.model.correction` — the latent-construct **measurement-model
    correction** (PMI/PPMI subtracts the attention axis, not merely flags it);
  * :mod:`~science_tool.model.federation` — patch **federation** via the data-driven
    bias-corrected latent common axis (the §2 GLUE).

The framework owns the *semantics and serialization* (pure-Python + rdflib). The
*data processing* that feeds these — building evidence units from a dataset, computing
a PPMI matrix, factorizing it into embeddings — belongs to the consuming project.
"""
from science_tool.model.correction import (
    CorrectedAssociation,
    attention,
    is_specific,
    pmi,
    ppmi,
)
from science_tool.model.federation import (
    FederationLink,
    cosine,
    emit_federation_trig,
    federation_link,
    glue_kind,
    nearest,
)
from science_tool.model.opinion import Opinion, opinion_from_scores
from science_tool.model.patch import (
    FusionResult,
    PatchEdge,
    PatchNode,
    emit_patch_trig,
    signature_fusion,
)

__all__ = [
    # patch
    "PatchNode",
    "PatchEdge",
    "FusionResult",
    "signature_fusion",
    "emit_patch_trig",
    # opinion
    "Opinion",
    "opinion_from_scores",
    # correction
    "attention",
    "pmi",
    "ppmi",
    "is_specific",
    "CorrectedAssociation",
    # federation
    "cosine",
    "glue_kind",
    "nearest",
    "FederationLink",
    "federation_link",
    "emit_federation_trig",
]

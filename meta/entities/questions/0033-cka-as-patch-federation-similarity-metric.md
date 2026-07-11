---
id: question:0033-cka-as-patch-federation-similarity-metric
kind: question
title: Can CKA (centered kernel alignment) serve as the operational similarity metric
  for the Science working model's latent-common-axis patch federation?
status: active
ontology_terms: []
datasets: []
source_refs:
- cite:Kornblith2019
related:
- hypothesis:0007-working-model
created: '2026-07-10'
updated: '2026-07-10'
---

# Can CKA (centered kernel alignment) serve as the operational similarity metric for the Science working model's latent-common-axis patch federation?

## Summary

The Science working model (`hypothesis:0007-working-model`) describes a "latent common axis" — a data-driven, bias-corrected embedding coordinate — as one of two glue mechanisms connecting epistemic patches.
This question asks whether **Centered Kernel Alignment (CKA)** [@Kornblith2019] is the right operational metric to quantify similarity between those latent axes: i.e., whether two patches (or projects) have learned commensurable latent representations.

## Why It Matters

- **Patch-federation implementation decision**: the `latent_common_axis` GLUE block in `h07` currently describes the concept without specifying a similarity metric; CKA is the leading candidate, but adopting it constrains the downstream federation implementation (`task:t067` successor work).
- **Invariance requirements**: CKA is invariant to orthogonal transformation and isotropic scaling but not invertible linear transformation; this is the principled choice for embedding spaces, but the toolkit must commit to this invariance class before implementing cross-patch comparison.
- **Risk if unanswered**: without an operational metric, patch federation remains conceptual; two projects could share a latent axis in theory but have no computable criterion for whether their axes are commensurable enough to support evidence exchange.

## Current Evidence

- CKA achieves 99.3% layer-correspondence accuracy on CNNs trained from different random initializations, far outperforming CCA (1.4%) and SVCCA (9.9–15.1%), establishing it as the state-of-the-art scalar representational similarity index [@Kornblith2019].
- The paper proves (Theorem 1) that invariance to invertible linear transformation is pathological when `p >= n` — a likely scenario in Science patches where the number of evidence items (data points) is small relative to the embedding dimensionality; this rules out CCA for this use case.
- The current patch-federation prototype (`task:t067`, `interpretation:0004`) uses SVD-based cosine similarity on PPMI-corrected embeddings — a method that is a special case of linear CKA when the representations are already normalized, suggesting conceptual alignment with CKA.
- No evidence yet that CKA has been applied to graph-structured or symbolic-plus-continuous mixed representations of the kind the Science toolkit produces; generalization requires additional justification.

## Thoughts

- **Best current interpretation**: CKA's invariance properties (orthogonal + isotropic-scaling invariance) match the intuitive requirements for comparing latent axes in a federated knowledge graph — two patches' embeddings should be considered similar if they agree on which examples are close, up to rotation and global scale, not up to arbitrary linear distortion. CKA formalizes this.
- **Major uncertainty**: CKA is defined for activation matrices `R^{n×p}`; it is not immediately clear how to apply it to the heterogeneous objects in the Science knowledge graph (propositions, evidence nodes, hypotheses with varying provenance types). An adaption step — mapping Science entities to a fixed embedding space — would be needed before CKA could be applied.
- A practical test would be: embed two patch-level entity graphs (e.g., the CMT and HSP patches from `task:t067`) using the existing SVD/PPMI representations and compute linear CKA; if CKA exceeds 0.7 and the patches are known to be biologically related, that supports adoption.

## Connections to Project

- Related hypotheses: `hypothesis:0007-working-model` (the GLUE block's `latent_common_axis` component)
- Required data or analyses: PPMI embedding matrices from the `task:t067` patch-federation prototype; a CKA computation over those matrices as a proof-of-concept.
- Priority level: Medium — depends on the pace of patch-federation development; actionable once `task:t067` successor work resumes.

## Related

- Topic notes: `hypothesis:0007-working-model` (patch-federation model), `question:0013-robustness-reproducibility-evaluation` (CKA as a reproducibility diagnostic)
- Article notes: `paper:Kornblith2019`; follow-up: Raghu et al. (2017) SVCCA; Kriegeskorte et al. (2008) RSA neuroscience
- Methods/Datasets: PPMI-corrected embedding matrices from the pan-disease prototype (`task:t067`)

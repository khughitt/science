---
kind: paper
title: Similarity of Neural Network Representations Revisited
status: active
created: '2026-07-10'
updated: '2026-07-10'
id: paper:Kornblith2019
ontology_terms: []
source_refs:
- cite:Kornblith2019
related:
- hypothesis:0007-working-model
- question:0013-robustness-reproducibility-evaluation
---

# Similarity of Neural Network Representations Revisited

- **Authors:** Simon Kornblith, Mohammad Norouzi, Honglak Lee, Geoffrey Hinton
- **Year:** 2019
- **Venue:** Proceedings of the 36th International Conference on Machine Learning (ICML), PMLR 97, pp. 3519–3529
- **DOI/URL:** https://doi.org/10.48550/arxiv.1905.00414
- **BibTeX key:** Kornblith2019
- **Source:** PDF

## Key Contribution

Kornblith et al. introduce **Centered Kernel Alignment (CKA)** as a principled similarity index for comparing neural network representations, demonstrating it is substantially more reliable than prior methods (CCA, SVCCA, PWCCA) at identifying layer correspondences across networks trained from different random initializations, different widths, and different architectures [@Kornblith2019].
The paper provides a unified theoretical framework for multivariate similarity statistics, formalizes invariance requirements (orthogonal transformation and isotropic scaling, but not invertible linear transformation), and proves that invariance to invertible linear transformation is pathological when representational dimensionality exceeds the number of data points.

## Methods

**Theoretical framework.** The paper analyzes a family of scalar similarity indexes `s(X, Y)` where `X ∈ R^{n×p1}` and `Y ∈ R^{n×p2}` are activation matrices for `n` examples.
It establishes that invariance to full invertible linear transformation collapses all full-rank representations to identical scores when `p >= n` (Theorem 1), ruling out CCA-family indexes for typical deep networks with wide layers.
The preferred invariance is to orthogonal transformations and isotropic scaling.

**CKA definition.** CKA normalizes the Hilbert-Schmidt Independence Criterion (HSIC):

```
CKA(K, L) = HSIC(K, L) / sqrt(HSIC(K,K) * HSIC(L,L))
```

where `K_ij = k(x_i, x_j)` and `L_ij = l(y_i, y_j)` are kernel matrices evaluated on examples.
For linear kernels this reduces to `||Y^T X||^2_F / (||X^T X||_F ||Y^T Y||_F)`, computable without matrix decomposition.
The paper also provides an RBF-kernel variant with bandwidth set as a fraction of the median pairwise distance, ensuring isotropic-scaling invariance.

**Compared methods.** CKA is systematically compared to CCA, SVCCA (Raghu et al., 2017), PWCCA (Morcos et al., 2018), linear regression (R^2), and linear HSIC, covering their invariance properties and behavior on a "sanity check" task: correctly identifying corresponding layers across independently-trained copies of the same architecture.

**Experiments.** VGG-like CNNs and ResNets on CIFAR-10/CIFAR-100; 10-layer All-CNN-C; Transformer encoder networks; networks of varying depth (1x–8x) and width (4–4096 channels). Layer-correspondence accuracy is measured over 10 independently trained networks.

## Key Findings

- CKA achieves **99.3% layer-correspondence accuracy** for linear CKA and RBF variants on CNNs trained from different initializations; CCA achieves 1.4%, SVCCA 9.9–15.1%, and linear regression 45.4% [@Kornblith2019].
- CKA reveals that **wider networks learn more similar representations**, with similarity approaching 1 as width increases; **early layers saturate first** (require fewer channels to converge) while later layers require more width.
- **Early layers, but not later layers**, develop similar representations when networks are trained on different datasets (CIFAR-10 vs. CIFAR-100); later layers are task-specific.
- CKA can identify architectural pathology: in an 8x-depth network with degraded accuracy (91.9%), CKA shows that more than half the layers have collapsed to near-identical representations of the final layer.
- For ResNets, CKA reveals a grid pattern matching the architecture: post-residual activations cluster with other post-residual activations; block interiors form a separate cluster.
- Analysis of the shared subspace shows that the shared subspace dimensionality in the penultimate layer approximates the number of classes (10 for CIFAR-10), not the ambient activation dimension.
- CKA is closely related to CCA: `R^2_CCA = CKA(Q_X Q_X^T, Q_Y Q_Y^T) * sqrt(p2/p1)` after orthonormalization; CKA symmetrically weights eigenvectors by their eigenvalues (variance explained), whereas CCA weights all directions equally.

## Relevance

CKA is methodologically central to the **latent common axis** concept in the Science working model (`hypothesis:0007-working-model`).
The working model describes "data-driven, bias-corrected latent axes" as one of the two glue mechanisms connecting epistemic patches; CKA provides a concrete, theoretically justified method for measuring how similar learned embedding spaces are, enabling a principled answer to whether two patches' latent coordinates are commensurable.

The paper's invariance analysis is directly relevant to the toolkit's representation design: the choice between orthogonal-invariance (shape-preserving) and invertible-linear-invariance (direction-agnostic) determines what counts as "same representation" when comparing patches or projects.
This constraint should inform the latent-axis design described in the working model's GLUE block.

The RSM (representational similarity matrix) paradigm underpinning CKA connects to the broader neuroscience and ML representation-analysis literature (Kriegeskorte et al., 2008), which the toolkit may want to adopt for evaluating whether evidence from different sources lands in structurally similar knowledge neighborhoods.

For robustness evaluation (`question:0013-robustness-reproducibility-evaluation`), CKA provides an operational definition of "representations are reproducible": two runs of the same pipeline should have CKA near 1 across corresponding layers; adversarial perturbations that shift CKA substantially signal representational fragility.

## Project Framework Mapping

| Paper Concept | Project Concept | Notes |
|---|---|---|
| Representational similarity matrix (RSM) | Latent common axis / patch embedding | RSMs are the objects that CKA compares; the Science working model's latent axis is an embedding that should support RSM-level comparison |
| CKA as a scalar similarity index | Patch-federation similarity score | A concretely computable glue metric for the `latent_common_axis` GLUE component in `h07` |
| Invariance to orthogonal transformation | Representation-invariant evidence comparison | Evidence from two probes/sources should be compared up to rotation/permutation, not arbitrary rescaling |
| Invariance to isotropic scaling | Scale-normalized belief comparison | Belief strengths need not be on the same absolute scale to be comparable |
| Invertible-linear-invariance pathology (`p >= n`) | Collapse risk in low-data settings | When patch datasets are small (few data points), a similarity index invariant to full linear transform assigns identical scores to all full-rank representations — a degenerate case |
| Layer correspondence sanity check | Pipeline reproducibility evaluation | Same methodology applies to checking whether two runs of a Science pipeline produce similar internal representations |
| Early vs. late layer similarity (dataset-invariance vs. task-specificity) | Evidence generalizability vs. specificity | Early-layer universality ↔ dataset-agnostic structural patterns; late-layer specificity ↔ claim-specific evidence nodes |

## Limitations

- CKA is a scalar summary that collapses the full structure of two representation spaces to one number; it can be high even when the shared subspace is low-dimensional (the penultimate-layer case shows shared subspace ~ 10 out of 64 dimensions).
- The paper focuses on classification networks with fixed architectures; applicability to arbitrary graph-structured or symbolic representations (as used in the Science toolkit's knowledge graph) requires additional justification.
- The choice of kernel (linear vs. RBF) and the bandwidth selection heuristic for RBF can affect results; no principled kernel-selection criterion is given beyond empirical similarity of outcomes.
- CKA is not directly interpretable as a probability or a calibrated distance; mapping CKA values to actionable thresholds (e.g., "representations are sufficiently similar to federate") requires empirical calibration in each domain.
- The paper does not address directed or causal representations; it compares activation matrices as undirected similarity structures, leaving open how to adapt the framework for causal DAGs or directed graph embeddings.

## Model / Tool Availability

The paper is a methods/theory paper from Google Brain.
No standalone CKA package was released with the paper itself, but CKA has been independently re-implemented widely (e.g., in `torch`, `jax`, and `tensorflow`).
The arXiv preprint is freely available at https://arxiv.org/abs/1905.00414.

## Follow-up

- Investigate how CKA could serve as the operational implementation of the `latent_common_axis` glue in `hypothesis:0007-working-model`, particularly in the context of patch-federation (`task:t067`).
- Read Raghu et al. (2017) "SVCCA: Singular Vector Canonical Correlation Analysis" as the predecessor method that CKA supersedes.
- Read Morcos et al. (2018) "Insights on representational similarity in neural networks with canonical correlation" for PWCCA context.
- Read Kriegeskorte et al. (2008) "Representational similarity analysis — connecting the branches of systems neuroscience" for the neuroscience RSM framework that CKA generalizes.
- Consider whether CKA's RSM paradigm could ground the "variety and concordance of independent measurements" argument in `question:0029-scientific-representation-grounding-in-graph` — concordant RSMs across probes as a practical grounding mechanism.

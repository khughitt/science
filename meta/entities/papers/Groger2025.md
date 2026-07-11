---
id: paper:Groger2025
kind: paper
title: With Limited Data for Multimodal Alignment, Let the STRUCTURE Guide You
status: active
paper_kind: ''
ontology_terms: []
dataset_usage: []
source_refs:
- cite:Groger2025
related:
- hypothesis:0007-working-model
- question:0034-structure-guided-cross-source-alignment
created: '2026-07-10'
updated: '2026-07-10'
---
# With Limited Data for Multimodal Alignment, Let the STRUCTURE Guide You

- **Authors:** Fabian Gröger, Shuo Wen, Huyen Le, and Maria Brbić (EPFL, University of Basel, HSLU)
- **Year:** 2025
- **Journal/Venue:** NeurIPS 2025
- **DOI/URL:** https://brbiclab.epfl.ch/projects/structure [UNVERIFIED — proceedings DOI not confirmed]
- **BibTeX key:** Groger2025
- **Source:** PDF

## Key Contribution

Gröger et al. show that high-quality multimodal alignment is achievable with as few as tens of thousands of paired samples — less than 1% of data used by standard methods — by combining two components that can be plugged into any existing alignment pipeline [@Groger2025].
The first component, STRUCTURE, is a regularization term that preserves multi-scale neighborhood geometry of each modality's pretrained latent space during alignment, using Jensen-Shannon divergence between hierarchical softmax-normalized similarity matrices.
The second component selects intermediate encoder layers with the highest cross-modal representational similarity (via mutual kNN) rather than defaulting to last layers, exploiting the Platonic Representation Hypothesis that independently trained encoders converge to similar internal representations.

## Methods

The framework freezes pretrained unimodal encoders and learns lightweight alignment functions (linear projections, MLPs, or CSA decomposition) that map each modality's latent space into a shared embedding space.

**STRUCTURE regularizer.** For each modality, the method computes normalized and centered similarity matrices at multiple hierarchical levels by taking successive matrix powers of a softmax-normalized Gram matrix. The regularization loss is a weighted average of Jensen-Shannon divergences between the pretrained and aligned similarity distributions across levels, downweighting higher levels to counteract concentration. This ensures the aligned space preserves the relational neighborhood geometry of the pretrained space at every scale.

**Layer selection.** Before training, mutual kNN similarity is computed between all layer pairs from the two encoders on a small set (~5,000) of paired samples. The pair with the highest similarity is selected. This corrects the common assumption that last layers are always best for alignment.

**Training data.** MS COCO train split (80,000 image–text pairs) as the primary low-data regime. Ablations scale down to 1,000 samples and scale up by adding LAION-15M subsets.

**Evaluation.** 22 zero-shot image classification datasets from the CLIP benchmark plus Flickr30K and MS COCO retrieval (text-to-image and image-to-text R@1). Default encoder pair: RoBERTa (text) + DINOv2 ViT-Giant (vision).

## Key Findings

- Average relative improvement of **51.6%** in zero-shot classification and **91.8%** in cross-modal retrieval versus the corresponding baseline (most-similar-layer alignment without regularization) across 24 datasets [@Groger2025].
- Layer selection alone contributes ~2–5% relative classification gains and ~3–18% retrieval gains across alignment methods; adding STRUCTURE on top gives the largest combined boost.
- Label efficiency of approximately **23x** on several tasks: the method achieves the same accuracy as unregularized last-layer alignment using roughly 1/23 the paired samples.
- On CIFAR10, the approach outperforms CLIP (trained on 400M pairs) while using 0.02% of that data.
- Adding as few as **3 in-domain labeled examples per class** to the 80K COCO training set closes the performance gap to CLIP on fine-grained benchmarks (e.g., Flowers accuracy rises from ~24% to >95%, exceeding CLIP's 93%).
- The neighborhood preservation metrics (Trustworthiness and Continuity at k=100) remain above 0.99 throughout training with STRUCTURE, versus steady decline without it.
- The framework generalizes to text–audio alignment and biological domain tasks (reported in appendix) [UNVERIFIED — appendix not fully reviewed].
- A generalization bound shows the empirical STRUCTURE regularizer approximates its population expectation at rate O(1/√N).

## Relevance

This paper is directly relevant to the Science working model's (h00) GLUE layer, specifically the `latent_common_axis` — the data-driven, bias-corrected shared coordinate that connects patches across heterogeneous sources.

The STRUCTURE principle offers a concrete answer to a design tension in h00: when only limited cross-source pairing examples exist (a common situation when aligning literature evidence, database records, and experimental observations), how do you prevent the alignment function from destroying the informative relational structure already present in each source's pretrained or derived representation? Preserving multi-scale neighborhood geometry during alignment is directly analogous to the Science requirement that the latent common axis faithfully reflects structural relationships within each patch, not just instance-level pairing.

The layer-selection insight (align layers with highest representational similarity, not the last layers) supports the Platonic Representation Hypothesis framing already invoked in h00: independently trained domain-specific encoders can share latent structure, and the alignment procedure should exploit that overlap rather than fighting it.

Connection to `question:0034-structure-guided-cross-source-alignment` (added with this paper): whether and how STRUCTURE-style geometry preservation can be applied to the Science toolkit's own multi-source alignment problem (cross-evidence, cross-project federation).

## Project Framework Mapping

| Paper Concept | Project Concept | Notes |
|---|---|---|
| STRUCTURE regularizer (multi-scale neighborhood preservation) | latent_common_axis quality constraint | Prevents alignment from destroying intra-source relational structure |
| Unimodal pretrained encoders (frozen) | Domain-specific representation spaces (papers, databases, experiments) | Each source has its own rich structure; alignment should not erase it |
| Layer selection via mutual kNN | Representational similarity probe for patch federation | The most-similar intermediate representations are the right alignment targets |
| Low-data multimodal alignment | Cross-source alignment with sparse pairing | Direct cross-source pairing examples are expensive; structural priors substitute |
| Shared embedding space A | Latent common axis / GLUE layer | The dual common space that connects patches in the federated model |
| In-domain few-shot supplement | Domain coverage > data volume | A few in-domain examples per class beat massive generic pairs — matches h00's patch-level elicitation logic |
| Platonic Representation Hypothesis | Structural convergence of independently trained models | Independently trained domain models may already share relational geometry |

## Limitations

- A performance gap remains on the most challenging tasks relative to CLIP and other models trained on hundreds of millions of pairs; the in-domain supplement closes this for most benchmarks but requires labeled examples [@Groger2025].
- Only two-modality alignment is evaluated (image–text primary; text–audio and bio in appendix). Extension to three or more modalities is proposed but not empirically validated beyond the theoretical extension of the loss.
- The STRUCTURE regularizer operates on an N×N similarity matrix, which scales quadratically with batch/subset size; the paper uses ~5,000 samples for layer selection and trains on 80K pairs, but large-scale adaptation would require approximations [UNVERIFIED].
- Training data is COCO-centric; distribution shift to specialized scientific domains (healthcare, biology) is real and requires in-domain supplement data — which may itself be scarce in the Science toolkit's target settings.
- The layer selection procedure requires a small set of paired samples from both modalities even for the probing step, so truly zero-supervision alignment is not achieved.

## Model / Tool Availability

Project website: https://brbiclab.epfl.ch/projects/structure [UNVERIFIED — code/checkpoint release status not confirmed as of 2026-07-10; the NeurIPS 2025 paper lists the project URL but a public repository URL is not stated in the PDF].

## Follow-up

- Check the project website and any associated GitHub repository for released code, pretrained alignment functions, and benchmark scripts.
- Design experiment: apply STRUCTURE-style regularization to the Science toolkit's own cross-source alignment problem — e.g., aligning literature-evidence embeddings with experimental-data embeddings for the same propositions, using COCO as a structural analogue.
- Read: Platonic Representation Hypothesis paper (Huh et al., ICML 2024, ref [24]) — already cited in h00 context but not yet summarized as a meta paper; directly underpins the layer-selection rationale.
- Read: FuseMix (Vouitsis et al., CVPR 2024, ref [22]) — complementary data-efficient alignment strategy using latent space augmentations; the authors show combining FuseMix with STRUCTURE yields further gains.
- Read: CSA (ref [29] in paper) — the matrix-decomposition alignment method used as a baseline; performs better than linear/MLP on retrieval tasks.
- Cross-link to natural-systems project: structure-guided alignment is relevant wherever heterogeneous multi-modal biological representations (gene expression, protein structure, pathology images) need to be aligned with limited cross-modal pairing data.

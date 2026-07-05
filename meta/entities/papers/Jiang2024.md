---
kind: paper
title: 'DiffKG: Knowledge Graph Diffusion Model for Recommendation'
status: active
created: '2026-05-06'
updated: '2026-05-06'
id: paper:Jiang2024
ontology_terms: []
source_refs:
- cite:Jiang2024
related:
- question:0004-source-and-pipeline-provenance
- question:0011-graph-valued-synthesis-artifacts
---

# DiffKG: Knowledge Graph Diffusion Model for Recommendation

- **Authors:** Yangqin Jiang, Yuhao Yang, Lianghao Xia, and Chao Huang
- **Year:** 2024
- **Journal/Venue:** WSDM 2024
- **DOI/URL:** https://doi.org/10.1145/3616855.3635850
- **BibTeX key:** Jiang2024
- **Source:** PDF

## Key Contribution

Jiang et al. propose DiffKG, a knowledge graph diffusion model for recommendation that filters noisy KG information and aligns task-relevant KG semantics with collaborative signals [@Jiang2024].
For Science, the important idea is that KG edges are not uniformly useful for every downstream task.

## Methods

The model uses heterogeneous knowledge aggregation, a diffusion process that corrupts and reconstructs KG relations, and collaborative KG convolution.
The diffusion model generates a recommendation-relevant KG subgraph used for data augmentation and contrastive learning.

## Key Findings

The paper reports improved recommendation performance over competitive baselines across three public datasets [@Jiang2024].
It argues that filtering irrelevant KG relations improves robustness under noise and sparsity.

## Relevance

Science should represent task-specific KG filtering and subgraph extraction as provenance.
If an agent uses a KG for retrieval, attention, or graph reasoning, the selected subgraph reflects a task-conditioned evidence view, not the whole knowledge state.

## Project Framework Mapping

| Paper Concept | Project Concept | Notes |
|---|---|---|
| KG diffusion / denoising | graph transformation artifact | Creates a task-conditioned KG view. |
| Recommendation-relevant subgraph | retrieval/attention context | Useful but potentially biased by task loss. |
| Collaborative signals | downstream objective | Shapes what KG edges are preserved. |
| Noisy KG filtering | source/pipeline provenance | Removed edges need traceability. |

## Limitations

The paper targets recommendation, not scientific belief updating.
Task-optimized KG filtering can remove scientifically relevant but task-irrelevant edges.
Science should store filtered-subgraph provenance and avoid silently replacing the source KG.

## Model / Tool Availability

The PDF reports code at `https://github.com/HKUDS/DiffKG`.

## Follow-up

Add task-conditioned KG view metadata: `kg_filter_objective`, `subgraph_selection_method`, `removed_edge_policy`, and `source_graph_ref`.

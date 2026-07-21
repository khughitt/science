---
kind: paper
title: Large-Scale Hierarchical Causal Discovery via Weak Prior Knowledge
status: active
created: '2026-05-06'
updated: '2026-07-08'
id: paper:Wang2025
ontology_terms: []
source_refs:
- cite:Wang2025
related:
- question:0003-causal-synthesis-guardrails
---

# Large-Scale Hierarchical Causal Discovery via Weak Prior Knowledge

- **Authors:** Xiangyu Wang, Taiyu Ban, Lyuzhou Chen, Derui Lyu, Qinrui Zhu, and Huanhuan Chen
- **Year:** 2025
- **Journal:** IEEE Transactions on Knowledge and Data Engineering
- **DOI/URL:** https://doi.org/10.1109/TKDE.2025.3537832
- **BibTeX key:** Wang2025
- **Source:** PDF

## Key Contribution

Wang et al. propose a divide-and-conquer causal discovery method that uses weak prior knowledge, derived with LLM assistance, to divide large variable sets into subproblems [@Wang2025].
The central contribution is using weak priors for stable decomposition rather than as definitive causal edges.

## Methods

The method asks an LLM to infer potential causes for each variable, constructs a prior structure, recursively divides variables into overlapping subsets, learns substructures with causal structure learning algorithms, and merges them with score-based local refinement.
The approach is evaluated on large-scale real-world causal structures.

## Key Findings

The paper reports improved accuracy and efficiency over existing large-scale causal discovery methods across datasets with 27 to 413 nodes [@Wang2025].
It argues that extra edges in weak priors mostly reduce efficiency, while missing prior edges are less harmful when connected nodes remain in the same subproblem.
Score-based merging is presented as more effective than CI-test-based merging under data scarcity.

## Relevance

Science may need hierarchical causal graph construction as projects scale.
Weak prior knowledge can guide decomposition without being treated as truth.
This supports schema fields for `prior_role`, `decomposition_strategy`, `subgraph_overlap`, `merge_operator`, and `refinement_diagnostics`.

## Project Framework Mapping

| Paper Concept | Project Concept | Notes |
|---|---|---|
| Weak prior structure | graph decomposition aid | Not a belief update by itself. |
| Divide and conquer | hierarchical graph workflow | Useful for large project graphs. |
| Substructure merging | synthesis operator | Needs provenance and diagnostics. |
| Score-based refinement | edge pruning transformation | Can remove false links from subgraphs. |

## Limitations

The method relies on useful weak priors and faithfulness assumptions for theoretical claims.
LLM-derived priors can be incomplete or biased.
Large-scale benchmark gains do not prove causal validity in arbitrary scientific domains.

## Model / Tool Availability

Code availability was checked on 2026-07-08.
Searches for the exact title, DOI `10.1109/TKDE.2025.3537832`, and author/code terms did not identify a matching public implementation repository.
A search result snippet pointed to `https://github.com/YXNTU/CausalHGNN`, but the GitHub API metadata for that repository describes it as official code for "Are Heterogeneous Graph Neural Networks Truly Effective? A Causal Perspective", so it was not recorded as this paper's implementation.

## Follow-up

Represent weak-prior graph uses separately from direct evidence, especially for graph decomposition and workflow planning.

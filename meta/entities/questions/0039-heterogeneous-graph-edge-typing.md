---
id: question:0039-heterogeneous-graph-edge-typing
kind: question
title: Should Science's knowledge graph support typed edge semantics analogous to
  heterogeneous GNN architectures for multi-type entity relationships?
status: active
ontology_terms: []
datasets: []
source_refs:
- cite:Besharatifard2024
related:
- hypothesis:0007-working-model
created: '2026-07-10'
updated: '2026-07-10'
---

# Should Science's knowledge graph support typed edge semantics analogous to heterogeneous GNN architectures for multi-type entity relationships?

## Summary

The drug-synergy GNN literature reviewed in Besharatifard2024 routinely constructs heterogeneous graphs with multiple node types (drug, protein, cell line, disease, tissue) and multiple edge types (drug-target interaction, protein-protein interaction, drug-drug synergy, drug-disease association).
The expressivity of these models depends critically on the ability to assign distinct propagation rules and attention mechanisms per edge type (e.g., via Heterogeneous Graph Attention Networks or R-GCN).
This question asks whether Science's current knowledge graph model supports — or should support — analogous typed-edge semantics, enabling different query/propagation behaviors depending on edge type.

## Why It Matters

- Affects the graph model design: whether edges are typed in the schema and whether downstream queries can filter or weight by type.
- If left unresolved, Science's knowledge graph may conflate semantically distinct relationships (supports, causes, associates-with, co-occurs-with) under a single undifferentiated edge type, reducing expressivity and query precision.

## Current Evidence

- Science's current model has typed edges via provenance and epistemic tags (lit-assertion, causal-edge, etc.), so some typed-edge semantics already exist.
- The patch-contract keystone (shipped 2026) adds typed edge semantics for causal claims; the extent to which this covers non-causal relationship types is unclear.
- Heterogeneous GNN reviews (Besharatifard2024, Dai2024GraphAttention) show that typed edges with per-type propagation rules significantly improve model expressivity for complex biological knowledge graphs.

## Thoughts

- Best current interpretation: Science has some typed-edge infrastructure but it is focused on epistemic/causal edges; general biological or multi-domain relationship types may not be fully expressible.
- Major uncertainty: whether the Science graph model's current edge typing is expressive enough for multi-domain knowledge, or whether a more general relation-type vocabulary is needed.

## Connections to Project

- Related hypotheses: hypothesis:0007-working-model (the federated patchwork model's edges need clear semantic types)
- Required data or analyses: audit current Science graph schema for edge typing coverage against the relation types used in heterogeneous GNN models.
- Priority level: low-medium — relevant when Science is applied to multi-domain knowledge graphs.

## Related

- Topic notes:
- Article notes: paper:Besharatifard2024, paper:Dai2024GraphAttention
- Methods/Datasets:

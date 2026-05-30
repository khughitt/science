---
id: paper:Dugourd2021
type: paper
title: Causal Integration of Multi-Omics Data with Prior Knowledge to Generate Mechanistic
  Hypotheses
status: active
ontology_terms: []
source_refs:
- cite:Dugourd2021
related:
- question:01-evidence-payload-schema
- question:02-causal-synthesis-guardrails
created: '2026-05-06'
updated: '2026-05-06'
---

# Causal Integration of Multi-Omics Data with Prior Knowledge to Generate Mechanistic Hypotheses

- **Authors:** Aurelien Dugourd et al.
- **Year:** 2021
- **Journal:** Molecular Systems Biology
- **DOI/URL:** https://doi.org/10.15252/msb.20209730
- **BibTeX key:** Dugourd2021
- **Source:** PDF

## Key Contribution

Dugourd et al. introduce COSMOS, a causal reasoning workflow that integrates transcriptomics, phosphoproteomics, and metabolomics with prior biological knowledge to generate mechanistic hypotheses [@Dugourd2021].
The key Science contribution is a concrete example of graph-oriented causal synthesis where prior knowledge networks, omics measurements, and optimization jointly produce candidate mechanisms.

## Methods

COSMOS estimates transcription-factor and kinase/phosphatase activities with footprint methods, links metabolites and regulators through a signed directed prior knowledge network, and uses causal network reasoning to extract coherent subnetworks.
The study applies COSMOS to matched tumor and healthy tissue from clear cell renal cell carcinoma patients.
The prior network integrates signaling, transcriptional regulation, and metabolism.

## Key Findings

COSMOS recovered cross-omics mechanistic hypotheses and known ccRCC-relevant signals, including hypoxia, inflammatory, and oncogenic activity patterns [@Dugourd2021].
The method explicitly treats omics layers as different observation modalities that must be connected through prior mechanistic knowledge.
The output is hypothesis-generating, not a definitive causal proof.

## Relevance

This paper directly informs Science's causal graph construction model.
It suggests that prior knowledge should be represented as a graph artifact with provenance and confidence, then contextualized by evidence rather than silently merged with measurements.
It also supports typed synthesis nodes for `mechanistic-network-synthesis` and reason codes for `prior-network-dependent` and `mechanism-hypothesis-only`.

## Project Framework Mapping

| Paper Concept | Project Concept | Notes |
|---|---|---|
| Prior knowledge network | background causal graph | Needs provenance and update policy. |
| Footprint activity estimate | derived evidence payload | Depends on regulator-target assumptions. |
| Causal network reasoning | typed synthesis operator | Produces mechanistic hypotheses. |
| Multi-omics layers | heterogeneous evidence views | Each layer has distinct measurement model. |

## Limitations

The method depends on curated prior knowledge, which may be incomplete or biased.
The case study is domain-specific and hypothesis-generating.
Network coherence does not by itself establish intervention-valid causal effects.

## Model / Tool Availability

The paper states that COSMOS is freely available as an R package [@Dugourd2021].
Exact repository status and version are [UNVERIFIED].

## Follow-up

Use COSMOS as an example in `t023` for mechanistic-network synthesis and in `t024` for prior-knowledge bias mechanisms.

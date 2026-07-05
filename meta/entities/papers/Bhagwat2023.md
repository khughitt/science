---
kind: paper
title: Causal Data Integration
status: active
created: '2026-05-06'
updated: '2026-05-06'
id: paper:Bhagwat2023
ontology_terms: []
source_refs:
- cite:Bhagwat2023
related:
- question:0003-causal-synthesis-guardrails
- question:0004-source-and-pipeline-provenance
---

# Causal Data Integration

- **Authors:** Brit Youngmann, Michael Cafarella, Babak Salimi, and Anna Zeng
- **Year:** 2023
- **Venue:** arXiv
- **DOI/URL:** https://arxiv.org/abs/2305.08741
- **BibTeX key:** Bhagwat2023
- **Source:** PDF

## Key Contribution

Youngmann et al. introduce the Causal Data Integration problem: augment an input dataset with missing causal variables from external sources and construct a causal DAG sufficient for causal analysis [@Bhagwat2023].
The key Science contribution is treating data discovery, attribute extraction, data cleaning, and causal DAG construction as one causal-analysis pipeline.

## Methods

The proposed CDI architecture includes a knowledge extractor, data organizer, and causal DAG builder.
The system mines unobserved confounding attributes, handles data-quality issues, and builds a clustered causal DAG to keep high-dimensional causal analysis interpretable.
The paper frames success as discovering relevant unobserved variables and the correct adjustment set, not merely producing a unified table.

## Key Findings

The paper argues that missing confounders and missing causal background knowledge are two core data-management threats to valid causal inference [@Bhagwat2023].
It identifies completeness, robustness, and conciseness as central CDI challenges.
Preliminary experiments suggest the system direction is feasible, but the paper is primarily a vision and architecture paper.

## Relevance

This paper is almost a direct design sketch for Science's causal graph agent.
It says the agent should not only estimate causal effects from available columns; it should search for missing confounders, record external-source provenance, manage data quality, and preserve clustered/abstract causal views when full DAGs are too large.

## Project Framework Mapping

| Paper Concept | Project Concept | Notes |
|---|---|---|
| Causal Data Integration | causal graph construction workflow | Data discovery plus DAG construction. |
| Missing confounder mining | source/pipeline expansion task | Could trigger H01 revisiting. |
| Data organizer | evidence transformation node | Handles quality issues before causal inference. |
| Cluster causal DAG | abstraction layer | Reduces cognitive overhead. |
| Adjustment set success | causal guardrail diagnostic | Output should include adjustment-set status. |

## Limitations

Completeness cannot be guaranteed because relevant variables may not exist in provided external sources.
The paper is early-stage and does not fully validate a mature CDI system.
Automatically building causal DAGs from mined attributes remains fragile.

## Model / Tool Availability

No mature reusable package is reported in the PDF.

## Follow-up

Add `missing-confounder-risk`, `external-variable-source`, `clustered-dag-level`, and `adjustment-set-status` to causal evidence payload design.

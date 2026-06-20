---
type: paper
title: 'gCastle: A Python Toolbox for Causal Discovery'
status: active
created: '2026-05-06'
updated: '2026-05-06'
id: paper:Zhang2021gCastle
ontology_terms: []
source_refs:
- cite:Zhang2021gCastle
related:
- question:0003-causal-synthesis-guardrails
---

# gCastle: A Python Toolbox for Causal Discovery

- **Authors:** Keli Zhang, Shengyu Zhu, Marcus Kalander, Ignavier Ng, Junjian Ye, Zhitang Chen, and Lujia Pan
- **Year:** 2021
- **Venue:** arXiv
- **DOI/URL:** https://arxiv.org/abs/2111.15155
- **BibTeX key:** Zhang2021gCastle
- **Source:** PDF

## Key Contribution

Zhang et al. present gCastle, an end-to-end Python toolbox for causal structure learning with simulators, algorithms, evaluation metrics, prior-knowledge insertion, post-processing, and real-world datasets [@Zhang2021gCastle].
The paper is useful for Science because it shows the operational surface required for practical causal discovery workflows, not just a single algorithm.

## Methods

The toolbox implements classic and gradient-based causal discovery algorithms, data simulators, real-world telecommunication datasets, graph evaluation metrics, and a GUI.
It supports workflow stages for data generation, graph learning, graph evaluation, prior insertion, neighborhood selection, and false-discovery removal.

## Key Findings

The main result is software coverage and workflow consolidation rather than a new causal discovery theorem.
gCastle emphasizes that causal discovery tools need data generation, algorithm selection, evaluation, and expert/prior-knowledge handling in one pipeline [@Zhang2021gCastle].

## Relevance

Science should treat causal discovery outputs as workflow artifacts with algorithm, assumptions, simulator/evaluation context, post-processing, prior constraints, and ground-truth status.
This reinforces H04: a learned graph should be a candidate graph unless the evidence payload records causal assumptions and validation.

## Project Framework Mapping

| Paper Concept | Project Concept | Notes |
|---|---|---|
| Causal discovery toolbox | workflow/tool node | Tool identity and version matter. |
| Prior knowledge insertion | guardrail / constraint payload | Should be explicit. |
| Evaluation metrics | diagnostic payload | SHD/FDR/TPR require ground truth or simulation. |
| Post-processing | transformation provenance | Can change edge claims. |

## Limitations

The paper is primarily a toolbox paper.
Many causal discovery methods rely on assumptions that may fail in scientific data.
Synthetic or domain-specific benchmark performance does not automatically transfer to general Science graph construction.

## Model / Tool Availability

The paper reports Apache-2.0 code at `https://github.com/huawei-noah/trustworthyAI/tree/master/gcastle` [@Zhang2021gCastle].

## Follow-up

Use gCastle and causal-learn as candidate backends only after representing algorithm assumptions and output semantics in the evidence payload.

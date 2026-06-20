---
type: paper
title: 'Causal-learn: Causal Discovery in Python'
status: active
created: '2026-05-06'
updated: '2026-05-06'
id: paper:Zheng2024
ontology_terms: []
source_refs:
- cite:Zheng2024
related:
- question:0003-causal-synthesis-guardrails
---

# Causal-learn: Causal Discovery in Python

- **Authors:** Yujia Zheng et al.
- **Year:** 2024
- **Journal:** Journal of Machine Learning Research
- **DOI/URL:** https://jmlr.org/papers/v25/23-0970.html
- **BibTeX key:** Zheng2024
- **Source:** PDF

## Key Contribution

Zheng et al. describe causal-learn, an open-source Python library that implements a broad set of causal discovery methods and utilities [@Zheng2024].
The paper is relevant as a practical backend candidate for Science's causal graph tooling.

## Methods

The library covers constraint-based, score-based, functional causal model-based, and latent-variable methods.
It provides conditional independence tests, score functions, graph operations, evaluation metrics, APIs, demos, and benchmark datasets.
It is implemented in Python and designed for extensibility and embedding in causal pipelines.

## Key Findings

The paper's contribution is software breadth and accessibility rather than a new discovery algorithm.
It argues that pure Python tooling helps practitioners, learners, and researchers build causal discovery workflows and extend existing methods [@Zheng2024].

## Relevance

Science should not treat causal-learn outputs as direct causal truth.
Instead, a causal-learn run should produce a workflow-run artifact with method class, assumptions, independence tests or score functions, graph object type, hyperparameters, and diagnostics.
This supports `t026` and future implementation of causal-discovery evidence payloads.

## Project Framework Mapping

| Paper Concept | Project Concept | Notes |
|---|---|---|
| Causal discovery library | tool backend | Candidate integration point. |
| Method families | synthesis/operator types | Constraint, score, FCM, latent-variable. |
| Graph operations | graph transformation provenance | CPDAG/PAG/DAG distinctions matter. |
| Metrics | diagnostics | Usually require ground truth or simulation. |

## Limitations

Tool availability does not resolve method assumptions.
Different algorithms return different graph semantics, including equivalence classes and latent-confounder-aware graphs.
Users can easily overinterpret outputs without schema guardrails.

## Model / Tool Availability

The library is available at `https://github.com/py-why/causal-learn` [@Zheng2024].

## Follow-up

Represent `graph_object_type` and `method_assumption_set` before integrating causal-learn into Science commands.

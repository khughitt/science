---
type: paper
title: 'Self-Compatibility: Evaluating Causal Discovery without Ground Truth'
status: active
created: '2026-05-06'
updated: '2026-05-06'
id: paper:Faller2024
ontology_terms: []
source_refs:
- cite:Faller2024
related:
- question:0003-causal-synthesis-guardrails
- hypothesis:0003-reason-coded-revisiting-beats-posterior-only-revisiting
---

# Self-Compatibility: Evaluating Causal Discovery without Ground Truth

- **Authors:** Philipp M. Faller, Leena Chennuru Vankadara, Francesco Locatello, Atalanti A. Mastakouri, and Dominik Janzing
- **Year:** 2024
- **Venue:** AISTATS / PMLR
- **DOI/URL:** https://proceedings.mlr.press/v238/faller24a.html
- **BibTeX key:** Faller2024
- **Source:** PDF

## Key Contribution

Faller et al. propose self-compatibility as a way to falsify causal discovery outputs without causal ground truth [@Faller2024].
The central idea is that causal discovery should be stable across subsets of variables, not only across subsets of data points.

## Methods

The paper defines interventional and graphical compatibility notions between causal graphs learned on overlapping variable subsets.
It proves that incompatibilities can falsify outputs when algorithm assumptions are met in the population limit.
It introduces an incompatibility score and evaluates whether it can aid model selection.

## Key Findings

The paper argues that causal-discovery evaluation based only on simulated data is inadequate because simulations encode researcher preconceptions [@Faller2024].
Compatibility checks provide a necessary, not sufficient, criterion for credible causal discovery.
Experiments show the incompatibility score can correlate with structural Hamming distance and aid model selection in some settings.

## Relevance

Science needs causal graph diagnostics when ground truth is absent.
Self-compatibility is a good candidate diagnostic payload for causal-discovery synthesis nodes.
It also supports H03: incompatible marginal graphs are a reason-coded revisit signal even when no external ground truth exists.

## Project Framework Mapping

| Paper Concept | Project Concept | Notes |
|---|---|---|
| Self-compatibility | causal graph diagnostic | Tests internal consistency across variable subsets. |
| Incompatibility score | uncertainty feature | Can feed attention sampling. |
| Ground-truth-free falsification | validation role | Stronger than no diagnostic. |
| Marginal causal models | graph slices | Need subset provenance. |

## Limitations

Passing compatibility checks does not prove a causal graph is correct.
The method depends on the compatibility notion and causal model class.
It can detect some assumption violations or finite-sample failures, not all causal errors.

## Model / Tool Availability

The paper is methodological; code availability was not verified from the PDF [UNVERIFIED].

## Follow-up

Add `self_compatibility_score` and `variable_subset_stability` as candidate diagnostics for causal-discovery outputs.

---
id: "paper:Deleu2023"
type: "paper"
title: "Joint Bayesian Inference of Graphical Structure and Parameters with a Single Generative Flow Network"
status: "active"
ontology_terms: []
datasets: []
source_refs:
  - "cite:Deleu2023"
related:
  - "question:01-evidence-payload-schema"
  - "question:10-causal-graph-construction-pipeline"
created: "2026-05-06"
updated: "2026-05-06"
---

# Joint Bayesian Inference of Graphical Structure and Parameters with a Single Generative Flow Network

- **Authors:** Tristan Deleu, Mizu Nishikawa-Toomey, Jithendaraa Subramanian, Nikolay Malkin, Laurent Charlin, and Yoshua Bengio
- **Year:** 2023
- **Journal/Venue:** NeurIPS 2023
- **DOI/URL:** https://arxiv.org/abs/2302.01436
- **BibTeX key:** Deleu2023
- **Source:** PDF

## Key Contribution

Deleu et al. propose JSP-GFN, a Generative Flow Network for approximating the joint posterior over Bayesian network DAG structures and conditional-distribution parameters [@Deleu2023].
The important project-level contribution is explicit posterior uncertainty over both graph structure and parameters, rather than a single learned graph.

## Methods

The GFlowNet samples in two phases: first constructing a DAG edge by edge, then sampling parameters conditioned on the completed graph.
The learned sampler targets a reward proportional to the joint posterior over graph and parameters.
The method is evaluated on simulated and real data and is designed to support flexible conditional models, including nonlinear neural parameterizations.

## Key Findings

The paper reports that JSP-GFN can approximate joint structure-parameter posterior distributions accurately and compare favorably against existing methods [@Deleu2023].
It argues that modeling parameters jointly avoids reliance on closed-form marginal likelihoods available only for restricted model classes.

## Relevance

Science should treat graph posterior evidence differently from a point graph.
A graph-valued evidence artifact may contain posterior mass over structures, parameter uncertainty, and local conditional models.
This supports payload fields such as `graph_posterior`, `parameter_posterior`, `posterior_sampler`, `reward_definition`, and `conditional_model_family`.

## Project Framework Mapping

| Paper Concept | Project Concept | Notes |
|---|---|---|
| Joint posterior over DAG and parameters | graph posterior artifact | Better than a single edge set for uncertainty-aware updates. |
| GFlowNet sampler | inference operator | Sampling model is part of provenance. |
| Two-phase construction | graph-construction pipeline | Structure and parameter stages should remain distinct. |
| Flexible CPDs | model-family payload | Local conditional models affect interpretation. |

## Limitations

The output is a Bayesian network posterior, not automatically a causal graph without causal assumptions.
The approximation quality depends on training, reward specification, and sample-space construction.
For Science, posterior graph mass should influence attention and uncertainty, not be collapsed prematurely to scalar support.

## Model / Tool Availability

The PDF reports code at `https://github.com/tristandeleu/jax-jsp-gfn`.

## Follow-up

Add `graph_posterior` as a first-class graph-valued synthesis output type rather than forcing posterior graph uncertainty into edge-level confidence scores.

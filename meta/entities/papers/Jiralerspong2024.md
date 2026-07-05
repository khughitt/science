---
kind: paper
title: Efficient Causal Graph Discovery Using Large Language Models
status: active
created: '2026-05-06'
updated: '2026-05-06'
id: paper:Jiralerspong2024
ontology_terms: []
source_refs:
- cite:Jiralerspong2024
related:
- question:0003-causal-synthesis-guardrails
---

# Efficient Causal Graph Discovery Using Large Language Models

- **Authors:** Thomas Jiralerspong, Yash More, Xiaoyin Chen, Vedant Shah, and Yoshua Bengio
- **Year:** 2024
- **Venue:** arXiv
- **DOI/URL:** https://arxiv.org/abs/2402.01207
- **BibTeX key:** Jiralerspong2024
- **Source:** PDF

## Key Contribution

Jiralerspong et al. propose a breadth-first LLM causal graph discovery framework that reduces query complexity from quadratic pairwise prompting to linear node-expansion prompting [@Jiralerspong2024].
The paper contributes an efficiency pattern for LLM-assisted graph construction.

## Methods

The framework asks an LLM to identify root-like variables, then expands nodes in BFS order by asking which variables each current node causes.
Proposed edges are inserted only if they preserve acyclicity.
The method can optionally incorporate observational data to improve performance.

## Key Findings

The paper reports competitive or state-of-the-art results on real-world causal graphs while requiring fewer LLM queries than pairwise approaches [@Jiralerspong2024].
It emphasizes that LLM causal graph discovery can use metadata rather than numerical observations, making it closer to expert graph elicitation.

## Relevance

This paper is useful for Science's command/agent design.
If Science uses LLMs to propose causal graph structure, graph construction should record prompt strategy, query complexity, variable descriptions, acyclicity checks, and whether observational data was used.
It also suggests that LLM-generated graph edges should be weak hypotheses, not final causal edges.

## Project Framework Mapping

| Paper Concept | Project Concept | Notes |
|---|---|---|
| BFS causal prompting | graph elicitation workflow | Lower-cost alternative to pairwise prompts. |
| Variable metadata | LLM evidence input | Needs provenance and source text. |
| Cycle check | graph constraint | Structural validity is not causal validity. |
| Optional observational data | mixed evidence mode | Should be flagged separately. |

## Limitations

The method depends on LLM internal knowledge and variable descriptions.
Guaranteeing acyclicity does not guarantee causal correctness.
The PDF is an arXiv version updated in 2026, so final publication status is [UNVERIFIED].

## Model / Tool Availability

Code availability was not verified from the PDF [UNVERIFIED].

## Follow-up

Track LLM graph-prompting strategy as a transformation node when Science agents generate candidate causal graphs.

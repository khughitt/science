---
kind: paper
title: Discovery of the Hidden World with Large Language Models
status: active
created: '2026-05-06'
updated: '2026-05-06'
id: paper:Liu2024HiddenWorld
ontology_terms: []
source_refs:
- cite:Liu2024HiddenWorld
related:
- question:0004-source-and-pipeline-provenance
- hypothesis:0003-reason-coded-revisiting-beats-posterior-only-revisiting
---

# Discovery of the Hidden World with Large Language Models

- **Authors:** Chenxi Liu et al.
- **Year:** 2024
- **Venue:** NeurIPS
- **DOI/URL:** https://causalcoat.github.io
- **BibTeX key:** Liu2024HiddenWorld
- **Source:** PDF

## Key Contribution

Liu et al. introduce COAT, a framework that uses LLMs to propose high-level variables and measurements from unstructured observations, then uses causal discovery feedback to refine those variables [@Liu2024HiddenWorld].
The core insight is that causal discovery often fails before graph learning begins because the relevant variables have not been represented.

## Methods

COAT starts with a target variable, prompts LLMs to propose candidate high-level factors and annotation criteria, uses LLMs to annotate unstructured data into structured variables, and applies causal discovery to reveal structure among factors.
The causal discovery results then provide feedback by selecting observations not well explained by current factors, prompting the LLM to propose additional factors.

## Key Findings

The paper argues that LLMs and causal discovery can be mutually beneficial [@Liu2024HiddenWorld].
LLMs help propose variables from unstructured data; causal discovery helps identify gaps in the proposed representation.
The framework is evaluated on synthetic and real-world benchmarks including reviews and medical diagnosis settings.

## Relevance

This is highly relevant to Science's graph-oriented research approach.
It shifts attention from "which edges connect known nodes?" to "what are the right causal variables and measurement functions?"
Science should therefore represent variable proposal, annotation criteria, annotator/model provenance, and causal-discovery feedback as first-class pipeline artifacts.

## Project Framework Mapping

| Paper Concept | Project Concept | Notes |
|---|---|---|
| Factor proposal | candidate variable creation | LLM-generated, needs validation. |
| Factor annotation | measurement model | Converts raw observations to graph variables. |
| CD feedback | representation gap signal | Can drive H01 revisiting. |
| Markov blanket target | local causal graph goal | Useful for focused discovery. |

## Limitations

LLM-proposed variables can encode bias, omissions, or unstable annotation criteria.
The framework depends on the target variable and feedback design.
The causal validity of discovered factors depends on both annotation quality and causal discovery assumptions.

## Model / Tool Availability

The PDF lists the project site `https://causalcoat.github.io`.
Repository and license status were not checked during the initial summary pass; tracked by task:t074.

## Follow-up

Add `variable-proposal-provenance`, `annotation-criteria`, and `representation-gap` reason codes to H03 and evidence-pipeline design.

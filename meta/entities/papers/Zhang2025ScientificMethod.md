---
kind: paper
title: 'Exploring the Role of Large Language Models in the Scientific Method: From
  Hypothesis to Discovery'
status: active
created: '2026-05-06'
updated: '2026-05-06'
id: paper:Zhang2025ScientificMethod
ontology_terms: []
source_refs:
- cite:Zhang2025ScientificMethod
related:
- question:0008-llm-agents-as-fallible-sources
- question:0004-source-and-pipeline-provenance
---

# Exploring the Role of Large Language Models in the Scientific Method: From Hypothesis to Discovery

- **Authors:** Yanbo Zhang, Sumeer A. Khan, Adnan Mahmud, Huck Yang, Alexander Lavin, Michael Levin, Jeremy Frey, Jared Dunnmon, James Evans, Alan Bundy, Saso Dzeroski, Jesper Tegner, and Hector Zenil
- **Year:** 2025
- **Journal/Venue:** npj Artificial Intelligence
- **DOI/URL:** https://doi.org/10.1038/s44387-025-00019-5
- **BibTeX key:** Zhang2025ScientificMethod
- **Source:** PDF

## Key Contribution

Zhang et al. review how LLMs may reshape the scientific method across hypothesis generation, literature synthesis, experimental design, data analysis, agentic tool use, and discovery [@Zhang2025ScientificMethod].
The key project implication is that LLMs should be integrated into science with explicit human goals, evaluation metrics, and workflow roles.

## Methods

The paper is a perspective/review.
It surveys LLM prompting, retrieval-augmented generation, agent frameworks, scientific copilots, foundation models for science, and the potential for LLMs as creative engines.

## Key Findings

The paper concludes that LLMs can be productivity enhancers and potentially creative engines, but only with deep integration into scientific workflows, alignment with human scientific goals, and clear evaluation metrics [@Zhang2025ScientificMethod].
It emphasizes that current LLM use still faces reliability, safety, evaluation, and interpretability challenges.

## Relevance

Science should represent LLM participation by scientific-method stage: literature review, hypothesis generation, experiment planning, tool execution, result interpretation, synthesis, and critique.
Each stage has different evidence semantics and validation needs.

## Project Framework Mapping

| Paper Concept | Project Concept | Notes |
|---|---|---|
| LLM scientific copilot | agent role | Helpful but fallible source/operator. |
| RAG and agents | pipeline provenance | Retrieval and tools shape output. |
| Foundation models for science | model source | Requires domain/version/validation metadata. |
| Creative engine | hypothesis generator | Should produce hypotheses, not direct belief updates. |

## Limitations

As a perspective, it provides conceptual synthesis rather than direct benchmark evidence.
The phrase "scientific discovery" spans many risk levels; Science should type agent outputs by stage and validation role.

## Model / Tool Availability

Not applicable as a review/perspective.

## Follow-up

Add an agent-output role taxonomy aligned to the scientific method: literature-search, extraction, synthesis, hypothesis-generation, experiment-design, tool-execution, critique, and validation.

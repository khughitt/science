---
id: "paper:{{nn}}-{{slug}}"
kind: "paper"
title: "{{title}}"
status: "active"
# Optional: literature-survey | literature-review | review | survey
paper_kind: ""
ontology_terms: []
dataset_usage: []
# Transition input only; prefer dataset_usage above.
datasets: []
source_refs: []
related: []
created: "{{YYYY-MM-DD}}"
updated: "{{YYYY-MM-DD}}"
_template:
  frontmatter:
    id: { from: entity_id }
    kind: { default: "paper" }
    title: { from: title }
    status: { from: status }
    paper_kind: { default: "" }
    ontology_terms: { default: [] }
    dataset_usage: { default: [] }
    datasets: { default: [] }
    source_refs: { from: source_refs }
    related: { from: related }
    created: { from: created }
    updated: { from: updated }
  sections:
    - { key: key-contribution, name: "Key Contribution", required: true }
    - { key: methods, name: "Methods", required: true }
    - { key: key-findings, name: "Key Findings", required: true }
    - { key: relevance, name: "Relevance", required: true }
    - { key: project-framework-mapping, name: "Project Framework Mapping", required: true }
    - { key: limitations, name: "Limitations", required: true }
    - { key: model-tool-availability, name: "Model / Tool Availability", required: true }
    - { key: follow-up, name: "Follow-up", required: true }
---

# {{title}}

<!--
- **Authors:** <authors>
- **Year:** <year>
- **Journal:** <journal>
- **DOI/URL:** <url>
- **BibTeX key:** <bibtex-key>
- **Source:** LLM knowledge | web search | PDF
-->

## Key Contribution

<!-- 2-3 sentences: what is the main claim or result? -->

## Methods

<!-- What approach did they use? What data? What key assumptions? -->

## Key Findings

<!-- The specific results that matter for our project -->

## Relevance

<!-- How does this connect to our research questions/hypotheses? Reference hypothesis IDs. -->

## Project Framework Mapping

<!-- If the project has an existing ontology, schema, or classification framework,
map the paper's concepts to the project's vocabulary:

| Paper Concept | Project Concept | Notes |
|---|---|---|
| <their term> | <our term> | <correspondence notes> |

Omit if no structured framework exists to map against. -->

## Limitations

<!-- What did they NOT address? Questionable assumptions? Known weaknesses? -->

## Model / Tool Availability

<!-- If the paper describes a model, tool, or dataset intended for reuse:
- Available checkpoints / versions
- Hardware requirements
- License
- Quantization options (if applicable)
- Access restrictions

Omit for papers that don't release artifacts. -->

## Follow-up

<!-- Papers to read next. Questions this raises for our project. -->

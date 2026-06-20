---
type: paper
title: An International Consensus on Core Reproducibility Items in Research
status: active
created: '2026-05-06'
updated: '2026-05-06'
id: paper:Banzi2026
ontology_terms: []
source_refs:
- cite:Banzi2026
related:
- question:0013-robustness-reproducibility-evaluation
- question:0002-evidence-payload-schema
- topic:analytic-flexibility-and-replication
---

# An International Consensus on Core Reproducibility Items in Research

- **Authors:** Rita Banzi, Monika Varga, Yuri Andrei Gelsleichter, Constant Vinatier, David Moher, Florian Naudet, and the OSIRIS-Delphi Study Group
- **Year:** 2026
- **Journal/Venue:** PLOS Biology
- **DOI/URL:** https://doi.org/10.1371/journal.pbio.3003726
- **BibTeX key:** Banzi2026
- **Source:** PDF

## Key Contribution

Banzi et al. present an international Delphi consensus list of core reproducibility items for research [@Banzi2026].
The paper turns reproducibility from a post-publication judgment into a lifecycle checklist covering planning, materials and methods, data collection/management/analysis, and dissemination.

## Methods

The OSIRIS-Delphi study used two online surveys and an online consensus meeting with a multidisciplinary panel.
The preliminary item list was informed by reproducibility literature and the OSIRIS reproducibility metrics review.
Items were rated against predefined consensus criteria and refined through the Delphi process.

## Key Findings

The final checklist includes 32 core items across four sections:
planning research; materials and methods; data collection, management, and analysis; and dissemination.
Items include hypotheses, rationale and prior evidence, study questions/objectives, data and statistical analysis plans, population and sample descriptions, bias-mitigation measures, sample-size estimation, data management, software/code descriptions, deviations from planned design, failed/negative/null results, limitations, data availability, and persistent identifiers for data and code.
Pre-registration did not reach consensus as a universal core item because of disagreements about applicability across exploratory and confirmatory research.

## Relevance

This is directly useful for Science's authoring and validation layers.
The paper suggests that reproducibility is partly an evidence property and partly an artifact-quality property distributed across a research lifecycle.
Science can encode these items as checklist-backed evaluation artifacts: missing data dictionaries, absent code identifiers, unreported deviations, or omitted null results should become reason-coded uncertainty and graph attention signals.

## Project Framework Mapping

| Paper Concept | Project Concept | Notes |
|---|---|---|
| Planning items | pre-evidence provenance | Hypotheses, rationale, questions, objectives, DMP, and SAP. |
| Materials/methods items | method payload completeness | Population, sample, variables, bias mitigation, sample size. |
| Data/analysis items | pipeline provenance | Data management, software, code, model development, validation. |
| Dissemination items | reporting completeness | Deviations, null results, limitations, data/code availability, persistent IDs. |

## Limitations

Consensus does not prove effectiveness.
The authors explicitly note that implementation studies are needed to test whether the core items identify reproducibility issues or improve research practices.
Some checklist items remain hard to judge without pre-registration or equivalent planning records.

## Model / Tool Availability

The OSIRIS checklist and supporting materials are described as implementation-oriented resources, but Science should still verify any machine-readable version before depending on it.

## Follow-up

Represent reproducibility checklist results as typed evaluation artifacts that can attach to papers, workflows, datasets, code, and evidence updates.

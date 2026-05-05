---
id: "paper:Mulder2026"
type: "paper"
title: "Bayes Factor Hypothesis Testing in Meta-Analyses: Practical Advantages and Methodological Considerations"
status: "active"
ontology_terms: []
datasets: []
source_refs:
  - "cite:Mulder2026"
related:
  - "topic:bayesian-methods-continuous-belief"
created: "2026-05-05"
updated: "2026-05-05"
---

# Bayes Factor Hypothesis Testing in Meta-Analyses: Practical Advantages and Methodological Considerations

- **Authors:** Joris Mulder and Robbie C. M. van Aert
- **Year:** 2026
- **Journal:** Research Synthesis Methods
- **DOI/URL:** https://doi.org/10.1017/rsm.2025.10060
- **BibTeX key:** Mulder2026
- **Source:** PDF

## Key Contribution

Mulder and van Aert review Bayes-factor hypothesis testing for meta-analysis, emphasizing its value for cumulative evidence monitoring, evidence for or against null effects, and coherent sequential updating [@Mulder2026].
The paper gives practical model choices, prior-specification guidance, and tool support through `BFpack`.

## Methods

The article compares Bayes-factor testing with classical p-value testing, presents five Bayes-factor meta-analytic models in a standard normal-effect-size framework, and discusses priors for global effects and between-study heterogeneity.
It also connects Bayes factors to e-value theory as a route to frequentist Type I error control in cumulative meta-analysis.
Two applications illustrate statistical learning in language impairment and seroma incidence after post-operative exercise.

## Key Findings

Bayes factors quantify graded relative evidence and can support either the null or the alternative, distinguishing absence of evidence from evidence of absence.
They are well suited to cumulative meta-analysis because evidence can be monitored as studies accrue.
Prior specification for the tested effect is load-bearing: extremely vague priors can bias evidence toward the null through Bartlett's paradox.
The paper argues that prior sensitivity is a methodological responsibility rather than a fatal flaw, because classical tests also require substantive choices such as equivalence margins or plausible effect sizes for power analysis.

## Relevance

This paper gives Science a principled language for cumulative evidence updates in a graph.
It supports storing evidence as a continuous quantity that can move toward or away from a proposition as studies accumulate.
It also argues for first-class prior metadata and sensitivity analysis on evidence edges or synthesis nodes, especially when an edge's support comes from a Bayes factor.
The e-value connection is relevant if Science needs anytime-valid monitoring while iteratively adding literature evidence.

## Project Framework Mapping

| Paper Concept | Project Concept | Notes |
|---|---|---|
| Bayes factor hypothesis test | proposition evidence update | Supports both null and alternative propositions. |
| Cumulative meta-analysis | graph evidence stream | Evidence can update as new studies arrive. |
| Prior sensitivity | evidence-model assumption | Must be stored and audited. |
| e-value link | anytime-valid monitoring | Useful for iterative evidence ingestion. |

## Limitations

The paper focuses on conventional meta-analytic effect-size settings and does not solve highly heterogeneous conceptual-replication cases by itself.
The guidance still requires domain-specific prior choices, which Science would need to expose rather than hide.

## Model / Tool Availability

The methods are implemented in the open-source R package `BFpack` according to the paper.

## Follow-up

Science should add prior provenance and sensitivity-analysis fields for Bayesian evidence updates.
It should also distinguish "evidence for no effect" from "insufficient evidence" in proposition states and UI summaries.

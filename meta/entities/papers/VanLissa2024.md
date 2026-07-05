---
kind: paper
title: A Tutorial on Aggregating Evidence from Conceptual Replication Studies Using
  the Product Bayes Factor
status: active
created: '2026-05-05'
updated: '2026-05-05'
id: paper:VanLissa2024
ontology_terms: []
source_refs:
- cite:VanLissa2024
related:
- topic:bayesian-methods-continuous-belief
---

# A Tutorial on Aggregating Evidence from Conceptual Replication Studies Using the Product Bayes Factor

- **Authors:** Caspar J. Van Lissa, Eli-Boaz Clapper, and Rebecca Kuiper
- **Year:** 2024
- **Journal:** Research Synthesis Methods
- **DOI/URL:** https://doi.org/10.1002/jrsm.1765
- **BibTeX key:** VanLissa2024
- **Source:** PDF

## Key Contribution

Van Lissa, Clapper, and Kuiper present the product Bayes factor (PBF) as a practical method for aggregating support for an informative hypothesis across heterogeneous conceptual replication studies [@VanLissa2024].
The tutorial contribution is a user-facing implementation in the `bain` R package, with reproducible examples and simulation validation.

## Methods

The paper explains informative hypotheses, Bayes-factor testing, and product aggregation across independent studies.
It benchmarks PBF against random-effects meta-analysis, individual participant data meta-analysis, and vote counting in simulation, then demonstrates use cases with meta-analytic and individual-participant data.
The method answers whether all included studies support a common informative hypothesis rather than estimating a pooled effect size.

## Key Findings

PBF is positioned for cases where fixed- or random-effects meta-analysis is inappropriate because effect sizes are incomparable or studies differ strongly in populations, designs, measures, or covariates.
The simulation reported favorable overall accuracy for PBF, with greater sensitivity and lower specificity relative to the comparison methods.
The paper stresses that PBF answers a different question than meta-analysis: support for a common hypothesis across studies, not the magnitude of a population effect.

## Relevance

This is a concrete tool-facing version of Bayesian evidence synthesis and maps naturally onto Science's proposition graph.
It suggests that Science could aggregate evidence over a proposition even when the underlying studies use incompatible estimands, provided each study-specific test maps cleanly to the same informative proposition.
It also reinforces the need to mark whether a synthesis result is an effect-size estimate, a hypothesis-support measure, or a conceptual-replication consistency measure.

## Project Framework Mapping

| Paper Concept | Project Concept | Notes |
|---|---|---|
| Product Bayes factor | aggregated evidence edge | Requires independence assumptions. |
| Informative hypothesis | explicit proposition | The target must be specified before aggregation. |
| Conceptual replication | heterogeneous evidence set | Useful for graph nodes supported by varied operationalizations. |
| `bain` implementation | possible external backend | Could be linked from analysis/research-package workflows. |

## Limitations

PBF depends on independent study evidence and on the quality of the study-specific informative hypotheses.
It does not estimate effect sizes or heterogeneity.
Its lower specificity relative to some comparison methods is important if Science uses it to prioritize rather than conclude.

## Model / Tool Availability

The method is implemented in the `bain` R package, with example datasets included according to the PDF.

## Follow-up

Science should distinguish "all studies support the same informative hypothesis" from "the pooled average effect is nonzero."
The graph schema may need separate synthesis nodes for evidence-consistency and effect-size estimation.

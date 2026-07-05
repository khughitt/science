---
kind: paper
title: 'A Scoping Review on Metrics to Quantify Reproducibility: A Multitude of Questions
  Leads to a Multitude of Metrics'
status: active
created: '2026-05-06'
updated: '2026-05-06'
id: paper:Heyard2025
ontology_terms: []
source_refs:
- cite:Heyard2025
related:
- question:0013-robustness-reproducibility-evaluation
- question:0002-evidence-payload-schema
- topic:analytic-flexibility-and-replication
---

# A Scoping Review on Metrics to Quantify Reproducibility

- **Authors:** Rachel Heyard, Samuel Pawel, Joris Frese, Bernhard Voelkl, Hanno Wuerbel, Sarah McCann, Leonhard Held, Kimberley E. Wever, Helena Hartmann, Louise Townsin, and Stephanie Zellers
- **Year:** 2025
- **Journal/Venue:** Royal Society Open Science
- **DOI/URL:** https://doi.org/10.1098/rsos.242076
- **BibTeX key:** Heyard2025
- **Source:** PDF

## Key Contribution

Heyard et al. review metrics used or proposed to quantify reproducibility [@Heyard2025].
Their central finding is that reproducibility has no single universally appropriate metric.
Metric choice depends on the question being asked, the replication design, the type of reproducibility, and the input data available.

## Methods

The authors conducted a scoping review.
They compiled large-scale reproducibility projects and systematically searched Scopus, MedLine, PsycINFO, and EconLit for methodological papers about reproducibility metrics.
They extracted information about each metric's type, purpose, required input, implementation state, assumptions, limitations, and application scenario.

## Key Findings

The review identified 49 large-scale reproducibility projects, 97 methodological papers, and 50 distinct metrics.
Metrics included formulas or statistical models, frameworks, graphical representations, studies or questionnaires, and algorithms.
Common applied metrics include agreement in statistical significance, agreement in effect size, meta-analytic summaries, subjective assessment, prediction markets, Bayes-factor-based replication measures, and framework/checklist scores.
The paper emphasizes that each metric answers a distinct question, so metric selection should be aligned with project goals rather than treated as a default.

## Relevance

This paper is highly relevant to Science's graph calibration agenda.
If reproducibility is an evaluation signal for H02, the graph needs to know which reproducibility metric was used and which question it answered.
A replication "success" label is not enough: the payload should include replication design, original and replication targets, effect-size relation, metric family, threshold or tolerance, uncertainty treatment, heterogeneity treatment, and whether the metric was designed to assess a study, finding, field, method, or analysis.

## Project Framework Mapping

| Paper Concept | Project Concept | Notes |
|---|---|---|
| Reproducibility metric | evaluation artifact | Should be typed by metric family and question. |
| Application scenario | evidence role / validation role | Determines whether the metric bears on calibration, attention, or reporting quality. |
| Metric assumptions | payload diagnostics | Prevents treating significance agreement, effect-size agreement, and Bayes factors as interchangeable. |
| Live metric table | method registry | Suggests a Science registry for reproducibility and robustness metrics. |

## Limitations

The review inventories metrics but does not determine which metrics are best in practice.
The authors also note that the literature is broad enough that some relevant metrics may be missing, and that effectiveness of metrics requires further empirical evaluation.

## Model / Tool Availability

The paper reports a live interactive metric table, OSF materials, and GitHub code/data resources.

## Follow-up

Science should represent reproducibility metrics as typed evaluation nodes with explicit metric purpose, required inputs, assumptions, and interpretation guidance.

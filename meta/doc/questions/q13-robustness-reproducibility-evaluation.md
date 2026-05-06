---
id: question:13-robustness-reproducibility-evaluation
type: question
title: How should Science represent robustness, reproducibility, and replication evaluation
  claims?
status: active
ontology_terms: []
datasets: []
source_refs:
- cite:Freiesleben2023
- cite:Heyard2025
- cite:Banzi2026
related:
- question:01-evidence-payload-schema
- hypothesis:h02-rich-evidence-payloads-improve-graph-calibration
- hypothesis:h03-reason-coded-revisiting-beats-posterior-only-revisiting
- topic:analytic-flexibility-and-replication
created: '2026-05-06'
updated: '2026-05-06'
---

# How should Science represent robustness, reproducibility, and replication evaluation claims?

## Summary

Batch 6 shows that robustness, reproducibility, and replication success should not be represented as scalar quality labels.
Freiesleben and Grote define robustness as relative stability of a target under interventions on a modifier [@Freiesleben2023].
Heyard et al. show that reproducibility metrics answer distinct questions and require different inputs, assumptions, and interpretation rules [@Heyard2025].
Banzi et al. provide a lifecycle checklist of core reproducibility items spanning planning, methods, data/analysis, and dissemination [@Banzi2026].
This question asks how Science should represent those evaluation claims so they can support graph calibration, evidence-quality warnings, and reason-coded revisiting.

## Why It Matters

- Affects H02 because "later validation outcome" needs typed reproducibility and robustness semantics before it can score calibration.
- Affects H03 because incomplete reproducibility checks create actionable revisit reasons: missing analysis plan, unavailable code/data, unreported deviations, omitted null results, ambiguous metric, and unspecified robustness target.
- Affects Q01 because evidence payloads need evaluation-target, metric, tolerance, and lifecycle-stage metadata.
- Affects research-paper commands because paper summaries should record whether reproducibility-relevant information is present, missing, or not applicable.
- Risk if unanswered: Science will treat "robust", "replicated", "reproducible", and "not reproducible" as comparable labels even when they were evaluated with different targets, perturbations, metrics, and thresholds.

## Current Evidence

- Freiesleben and Grote identify the minimum conceptual parts of a robustness claim: target, modifier, modifier domain, and target tolerance [@Freiesleben2023].
- Heyard et al. identify 50 reproducibility metrics from 49 large-scale projects and 97 methodological papers, showing that metric choice is goal-dependent [@Heyard2025].
- Banzi et al. identify 32 core reproducibility items through Delphi consensus, organized across planning, materials/methods, data/analysis, and dissemination [@Banzi2026].
- The existing analytic-flexibility topic shows why these evaluations matter: reproducibility failures often arise from analyst choices, missing plans, underreported methods, and inaccessible data/code.

## Thoughts

- Best current interpretation: Science should create typed evaluation artifacts for robustness tests, replication studies, reproducibility metrics, and checklist audits.
- Minimum fields should include `evaluation_target`, `evaluation_artifact_type`, `robustness_modifier`, `modifier_domain`, `replication_design`, `reproducibility_dimension`, `metric_family`, `metric_question`, `success_threshold`, `target_tolerance`, `uncertainty_treatment`, `checklist_ref`, `lifecycle_stage`, and `evaluation_result`.
- These evaluations should update belief only when their target and metric match the proposition being updated.
  Otherwise they should update attention, provenance quality, or reporting completeness.
- The major uncertainty is implementation shape: payload fields are easier to author, but first-class evaluation nodes are better for reuse across many propositions.

## Connections to Project

- Related hypotheses: `hypothesis:h02-rich-evidence-payloads-improve-graph-calibration`, `hypothesis:h03-reason-coded-revisiting-beats-posterior-only-revisiting`.
- Related tasks: `[t022]`, `[t025]`, `[t030]`, `[t040]`, `[t041]`.
- Required data or analyses: define evaluation artifact schema, map checklist failures to H03 reason codes, and choose a small set of replication metrics for H02 replay scoring.
- Priority level: high for calibration; medium-high for authoring workflow.

## Related

- Topic notes: `topic:analytic-flexibility-and-replication`.
- Article notes: `paper:Freiesleben2023`, `paper:Heyard2025`, `paper:Banzi2026`.
- Methods/Datasets: robustness analysis, replication metrics, reproducibility checklists, Delphi consensus, meta-research.

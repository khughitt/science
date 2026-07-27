---
id: t040
project: ''
title: Design robustness/reproducibility evaluation schema
type: ''
aspects:
- software-development
- framework-design
- hypothesis-testing
- research
priority: P1
status: proposed
blocked_by: []
related:
- task:t021
- task:t022
- task:t025
- task:t030
- question:0013-robustness-reproducibility-evaluation
- question:0002-evidence-payload-schema
- hypothesis:0002-rich-evidence-payloads-improve-graph-calibration
- hypothesis:0003-reason-coded-revisiting-beats-posterior-only-revisiting
- topic:analytic-flexibility-and-replication
parent: ''
group: evidence-payload-schema
artifacts: []
findings: []
created: '2026-05-06'
completed: null
---

Design how Science represents robustness tests, replication studies, reproducibility metrics, and checklist audits.

Candidate artifact types:
- `robustness_test`;
- `replication_study`;
- `reproducibility_metric_result`;
- `reproducibility_checklist_audit`;
- `reporting_completeness_audit`;
- `code_data_availability_check`;
- `deviation_report_check`.

Deliverables:
- an evaluation-artifact taxonomy with strict enum candidates for `evaluation_artifact_type`, `reproducibility_dimension`, `metric_family`, and `lifecycle_stage`;
- a payload schema covering `evaluation_target`, `robustness_target`, `robustness_modifier`, `modifier_domain`, `intervention_type`, `target_tolerance`, `replication_design`, `metric_question`, `metric_assumptions`, `success_threshold`, `uncertainty_treatment`, `checklist_ref`, `evaluation_result`, and `validation_role`;
- rules for whether each evaluation artifact updates belief, updates attention, records reporting quality, or blocks a causal/evidence update;
- H03 reason-code mapping for `robustness-target-ambiguous`, `modifier-domain-missing`, `tolerance-unspecified`, `replication-metric-mismatch`, `reproducibility-dimension-ambiguous`, `checklist-incomplete`, `analysis-plan-missing`, `deviation-unreported`, `code-or-data-unavailable`, and `null-results-omitted`;
- alignment notes with `[t030]` so H02 calibration benchmarks use typed validation outcomes rather than binary replication-success labels.

Start from Batch 6 synthesis: `entities/synthesis/0005-synthesis-robustness-and-reproducibility-evaluation.md`.
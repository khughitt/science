---
kind: synthesis
title: 'Synthesis: Robustness and Reproducibility Evaluation'
status: active
created: '2026-05-06'
updated: '2026-05-06'
id: synthesis:0005-synthesis-robustness-and-reproducibility-evaluation
report_kind: paper-batch-synthesis
generated_at: '2026-05-06T00:00:00-04:00'
source_commit: 2b27eae
source_refs:
- paper:Freiesleben2023
- paper:Heyard2025
- paper:Banzi2026
related:
- question:0002-evidence-payload-schema
- question:0013-robustness-reproducibility-evaluation
- hypothesis:0002-rich-evidence-payloads-improve-graph-calibration
- hypothesis:0003-reason-coded-revisiting-beats-posterior-only-revisiting
- topic:analytic-flexibility-and-replication
---

# Synthesis: Robustness and Reproducibility Evaluation

## TL;DR

Batch 6 adds an evaluation semantics layer.
Robustness, reproducibility, replication success, and checklist completeness are not scalar labels.
They are typed evaluation claims whose meaning depends on target, modifier or replication design, metric, tolerance, lifecycle stage, assumptions, and validation role [@Freiesleben2023; @Heyard2025; @Banzi2026].

## Key Contribution

The batch makes one design claim: Science needs first-class robustness and reproducibility evaluation artifacts.
These artifacts should say what was evaluated, what was perturbed or replicated, which metric or checklist was used, which threshold or tolerance defined success, and what kind of graph update the result is allowed to support.

## Methods

This synthesis compares three papers: a conceptual theory of robustness in ML, a scoping review of reproducibility metrics, and an international Delphi consensus checklist for core reproducibility items.

## Key Findings

**Robustness is a relation, not a label.**
Freiesleben and Grote define robustness through a target, modifier, modifier domain, and target tolerance [@Freiesleben2023].
Science should not store "robust" without those fields.

**Reproducibility metrics are question-specific.**
Heyard et al. identify 50 metrics across 49 large-scale projects and 97 methodological papers, with metric families ranging from significance agreement and effect-size agreement to Bayes factors, frameworks, plots, surveys, prediction markets, and algorithms [@Heyard2025].
No single metric is universally appropriate.

**Reproducibility is a lifecycle property.**
Banzi et al. provide 32 core reproducibility items across planning, methods, data/analysis, and dissemination [@Banzi2026].
The checklist is not just reporting hygiene; it records whether a future researcher can inspect the assumptions, methods, software, data, deviations, and null results needed to evaluate evidence.

## Relevance

Batch 6 turns validation from an afterthought into a graph object.
Science's evidence graph should be able to represent that a claim is robust to a specified perturbation, reproducible under a specified replication design, incomplete under a specified checklist, or evaluated by a specified metric family.
Those states should affect H02 calibration and H03 attention.

## Implications for Science

**1. Add typed evaluation nodes.**
Represent robustness tests, replication studies, reproducibility metrics, and checklist audits as first-class artifacts rather than prose annotations.

**2. Separate target, perturbation, metric, and result.**
Fields should include `evaluation_target`, `robustness_modifier`, `modifier_domain`, `intervention_type`, `replication_design`, `reproducibility_dimension`, `metric_family`, `metric_question`, `success_threshold`, `target_tolerance`, `uncertainty_treatment`, and `evaluation_result`.

**3. Treat checklist failures as evidence-quality reasons.**
Missing data dictionaries, missing analysis plans, unreported deviations, inaccessible code/data, or omitted null results should produce H03 reason codes and possibly validation warnings.

**4. Preserve metric assumptions.**
A replication success result based on same-direction statistical significance is not equivalent to one based on effect-size agreement, prediction intervals, sceptical Bayes factors, or expert judgment.

**5. Add lifecycle provenance to evidence payloads.**
For research artifacts, Science should record which lifecycle stage the evaluation concerns: planning, methods, data/analysis, dissemination, or post-publication replication.

## Open Questions

1. Should robustness/reproducibility evaluations be payload fields, standalone entities, or both?
2. Which reproducibility dimensions should be core enums: methods reproducibility, results reproducibility, inferential reproducibility, computational reproducibility, replicability, robustness, generalizability, and translatability?
3. How should checklist incompleteness influence graph belief versus graph attention?
4. Which replication metrics should Science support first for replay experiments and H02 calibration scoring?
5. How can these evaluations avoid punishing exploratory work while still recording uncertainty from missing plans?

## Prioritized Follow-ups

**P1: Create a robustness/reproducibility evaluation schema task.**
Define typed evaluation artifacts, fields, allowed graph updates, and H03 reason codes.

**P2: Extend the analytic-flexibility topic.**
Connect many-analysts and replication-crisis evidence to metric-specific reproducibility evaluation.

**P3: Add checklist-backed validation ideas to command feedback.**
Paper summaries and synthesis artifacts could report missing methods, data, code, deviation, and null-result information in a structured way.

## Post-Batch-6 Synthesis Decisions

**New question.**
Batch 6 warrants a distinct evaluation-semantics question:
- `question:0013-robustness-reproducibility-evaluation` asks how Science represents robustness, reproducibility, and replication evaluation claims.

**New tasks.**
Create two follow-up tasks:
- `[t040]` robustness/reproducibility evaluation schema;
- `[t041]` follow-up literature on replication metrics, robustness, and reproducibility standards.

**No new hypothesis yet.**
Batch 6 strengthens H02 and H03 by clarifying what later validation outcomes and reason-coded review signals should look like.
It may later motivate a hypothesis like: "Typed reproducibility evaluations improve graph calibration over binary replication-success labels."
Hold this until H02's benchmark design has clearer validation targets.

**Schema update.**
Batch 6 adds:
- `evaluation_target`;
- `evaluation_artifact_type`;
- `robustness_target`;
- `robustness_modifier`;
- `modifier_domain`;
- `intervention_type`;
- `target_tolerance`;
- `replication_design`;
- `reproducibility_dimension`;
- `metric_family`;
- `metric_question`;
- `metric_assumptions`;
- `success_threshold`;
- `uncertainty_treatment`;
- `checklist_ref`;
- `lifecycle_stage`;
- `evaluation_result`;
- `validation_role`.

**Reason-code update.**
Batch 6 extends H03 with:
- `robustness-target-ambiguous`;
- `modifier-domain-missing`;
- `tolerance-unspecified`;
- `replication-metric-mismatch`;
- `reproducibility-dimension-ambiguous`;
- `checklist-incomplete`;
- `analysis-plan-missing`;
- `deviation-unreported`;
- `code-or-data-unavailable`;
- `null-results-omitted`.

## Related Papers and Topics to Consider

Highest-value additions:

- Goodman, Fanelli, and Ioannidis on reproducibility terminology.
- National Academies 2019 report on reproducibility and replicability in science.
- Nosek et al. on preregistration, registered reports, and transparency reforms.
- Anderson and Maxwell on replication goals and metrics.
- Hedges and Schauer / Pawel and Held / Mathur and VanderWeele on replication success and heterogeneous effects.
- Munafo et al. 2017 manifesto for reproducible science.
- WILDS, robustness benchmark, and distribution-shift evaluation papers for ML robustness.

## Command and Skill Feedback

Batch 6 suggests concrete command/skill improvements:

- Add a reproducibility-checklist extraction section to paper summaries.
- Add structured fields for whether the PDF reports analysis plans, deviations, null results, data/code availability, and persistent identifiers.
- Add metric-family fields when a paper reports replication or robustness results.
- Add validation warnings when a summary says "robust" or "reproducible" without target, modifier/design, metric, and tolerance.
- Add a later command to run a checklist audit across paper summaries and evidence artifacts.

---
type: synthesis
title: Reason-coded revisiting beats posterior-only revisiting
status: active
created: '2026-05-06'
updated: '2026-05-06'
report_kind: hypothesis-synthesis
id: synthesis:0011-reason-coded-revisiting-beats-posterior-only-revisiting
hypothesis: hypothesis:0003-reason-coded-revisiting-beats-posterior-only-revisiting
generated_at: '2026-05-06T03:57:33Z'
source_commit: 591956fe223318a92c9b36ba01afefcfb1246b10
provenance_coverage: thin
---

## State

H03 is in `proposed` status with no simulation results and no interpretations. The central claim — that an attention policy guided by typed uncertainty reason codes outperforms one guided by posterior magnitude alone — is logically motivated but not yet empirically tested in this project.

The proposition bundle distinguishes three levels of the claim. P1 asserts attention improvement (better recall, calibration, or contradiction discovery at equal review budget). P2 asserts that reason codes are actionable — they identify a *next useful action* rather than merely flagging low confidence. P3 asserts non-equivalence: different reasons with identical posterior magnitude carry different expected value of review, so posterior-only revisiting discards available information.

Six question tracks define the representation prerequisite: the evidence payload must capture typed reason codes before any attention policy can consume them. Those tracks are `question:0002-evidence-payload-schema`, `question:0004-source-and-pipeline-provenance`, `question:0010-causal-graph-construction-pipeline`, `question:0011-graph-valued-synthesis-artifacts`, `question:0012-agent-tool-kg-operations`, and `question:0013-robustness-reproducibility-evaluation`.

Key unresolved uncertainties noted in the hypothesis spec itself: the right objective function is undecided (recall, calibration, contradiction discovery, researcher-time efficiency); reason codes from Batches 3–6 may overlap in ways that require consolidation rather than enumeration; and no annotation audit has yet confirmed that codes can be assigned consistently from documented evidence fields.

## Arc

Arc reconstruction is limited because no interpretations cite H03 and no `prior_interpretations` chains exist. What follows is grounded only in task creation dates and the hypothesis spec.

H03 was created on 2026-05-05, the same date as the t021 evidence-payload schema task group — a direct consequence of the Batch 1–6 literature synthesis pass that produced that group. The hypothesis spec's proposition bundle (P4–P9) grew through six batches, each batch adding a new reason-code family: Batch 1 contributed statistical-quality reasons (`underpowered-evidence`, `high-heterogeneity`, `prior-sensitive`); Batch 2 added source and pipeline reasons (`source-unreliable`, `source-dependent`, `cleaning-unvalidated`); Batch 3 added causal-graph-construction reasons (`causal-sufficiency-assumption`, `latent-variable-risk`, `self-incompatible`); Batch 4 added graph-valued integration reasons (`graph-posterior-uncertain`, `edge-inclusion-unstable`, `view-scope-mismatch`); Batch 5 added agent and KG operational reasons (`kg-view-derived`, `graph-version-stale`, `agent-bias-risk`); Batch 6 added evaluation reasons (`replication-metric-mismatch`, `checklist-incomplete`, `code-or-data-unavailable`).

The current epistemic position is that the hypothesis is well-motivated by literature but sits at the design frontier: it depends on a payload schema (`t021`, `t022`) that does not yet exist, and on a simulator extension (`t025`) that has not been started.

## Research fronts

**Live questions.** All six linked questions remain open at the representation level. `question:0002-evidence-payload-schema` is the bottleneck: reason codes cannot be assigned or consumed until the payload schema is designed. `question:0004-source-and-pipeline-provenance`, `question:0010-causal-graph-construction-pipeline`, `question:0011-graph-valued-synthesis-artifacts`, `question:0012-agent-tool-kg-operations`, and `question:0013-robustness-reproducibility-evaluation` each define a reason-code family that feeds the H03 policy.

**Open tasks.** The highest-priority path runs through `t021` (schema parent, P1) and `t022` (minimum quantitative payload, P1) as prerequisites, then `t025` (reason-coded uncertainty features for H01 attention, P2) as the direct H03 implementation task. Supporting design tasks include `t034` (causal graph construction pipeline artifacts, P1), `t035` (graph-valued synthesis artifact schema, P1), `t037` (agent/tool operations schema, P1), `t038` (graph evolution and KG view provenance, P1), and `t040` (robustness/reproducibility evaluation schema, P1). Literature follow-up tasks `t028`, `t036`, `t039`, and `t041` may surface methods that sharpen the reason-code taxonomy or the simulation design. Detection infrastructure for source-dependence patterns (`t031`) and sequential evidence (`t032`) will interact with specific reason codes once the schema is in place.

**Critical validation gap.** No comparison between reason-coded and posterior-only policies exists yet. An annotation audit (`t030`) over existing paper summaries is needed to test whether reason codes can be assigned consistently before the H01 simulator is extended with heterogeneous failure modes.

---
type: synthesis
title: Project synthesis - science meta
status: active
created: '2026-05-06'
updated: '2026-05-06'
id: synthesis:0007-project-synthesis-science-meta
report_kind: synthesis-rollup
generated_at: '2026-05-06T03:57:33Z'
source_commit: 591956fe223318a92c9b36ba01afefcfb1246b10
synthesized_from:
- hypothesis: hypothesis:0001-stochastic-revisiting
  file: doc/reports/synthesis/h01-stochastic-revisiting.md
  sha: b6945313780f416dce599a687c2cc462ed625178
- hypothesis: hypothesis:0002-rich-evidence-payloads-improve-graph-calibration
  file: doc/reports/synthesis/h02-rich-evidence-payloads-improve-graph-calibration.md
  sha: 903891c24097cecf5b72eef55b315a59189d2b36
- hypothesis: hypothesis:0003-reason-coded-revisiting-beats-posterior-only-revisiting
  file: doc/reports/synthesis/h03-reason-coded-revisiting-beats-posterior-only-revisiting.md
  sha: b24f07d5c6f3c71516ed4ddcaf37b9f8994ffe89
- hypothesis: hypothesis:0004-causal-estimand-guardrails-reduce-false-causal-edge-strengthening
  file: doc/reports/synthesis/h04-causal-estimand-guardrails-reduce-false-causal-edge-strengthening.md
  sha: 200f9cf12ed578ad95fd70a9a801771d8ceff7f3
- hypothesis: hypothesis:0005-sequential-evidence-improves-attention
  file: doc/reports/synthesis/h05-sequential-evidence-improves-attention.md
  sha: 81585d2806161772623e4170230f618e4b1efccc
emergent_threads_sha: 62f632e36ace3c85a00006298969efbb335bd4e4
orphan_question_count: 1
---

# Project Synthesis

## TL;DR

- The H01 simulator sweep (`interpretation:0001-simulator-2026-04-24`) is the only empirical anchor in the project; H02, H03, H04 are literature-grounded and pre-empirical, and H05 is speculative.
- That sweep refined H01's mechanistic claim: the load-bearing factor is *uncertainty-guided exploration* (UCB > Thompson on both recall and Brier), not stochasticity per se — a narrowing of the literal hypothesis.
- The post-Batch-1–6 design surface (`task:t021` parent group) is dominated by one question: how rich must an evidence payload be to fix calibration without collapsing under authoring burden — `task:t030`'s authoring-cost audit is the nearest test.
- Three of four active hypotheses (`hypothesis:0002-rich-evidence-payloads-improve-graph-calibration`, `hypothesis:0003-reason-coded-revisiting-beats-posterior-only-revisiting`, `hypothesis:0004-causal-estimand-guardrails-reduce-false-causal-edge-strengthening`) all gate on `task:t022` (minimum quantitative payload schema) — it is the project bottleneck.
- `task:t011` already lifted H01's exploration finding into the tool's attention layer (weighted graph sampling), so the project's critical path is now schema-first, not simulator-first.
- One orphan question (`question:0009-mcda-bayesian-interoperability`) and one knowledge gap (`topic:structured-scientific-knowledge`, demand 3 vs coverage 0) suggest a missing candidate hypothesis at the MCDA/Bayesian interface.
- H01's untested boundary (continuous-signal generalization, `task:t005`) and H05's graduation gate (`task:t032`) bound how far current findings can be claimed to generalize.

## State

The project's collective belief is that *some* form of exploration-based revisiting beats hard-gating under noisy evidence — this is the only empirically supported claim, established in `interpretation:0001-simulator-2026-04-24` across 144 000 simulator rows. Every other active hypothesis (H02, H03, H04) and the speculative H05 are at the design-frontier stage: they have literature motivation across six paper batches but no benchmark, replay, or simulation data. Strength of belief therefore concentrates sharply on H01 and dilutes across H02–H05.

The strongest evidence sits in two places. First, the H01 sweep's mechanistic refinement (UCB outperforming Thompson) tightens the H01 family's design implication: graph-layer attention should be *uncertainty-weighted* rather than randomly stochastic, which `task:t011` already implements. Second, the literature backing H02–H04 is broad and consistent across batches — six independent paper batches all surface the same pattern that scalar support/dispute edges lose epistemically load-bearing distinctions.

What is contested is the *minimum viable* schema. H02's P3 (minimality) holds that calibration gains are achievable with a compact core, but the project has no authoring-cost evidence yet; `question:0005-authoring-cost-audit` and `task:t030` are the nearest test. The H02–H04 hypotheses agree on direction but disagree implicitly on scope: H04's causal guardrails are a strict superset of H02's calibration fields, and H03's reason codes overlap both. Reconciliation will happen at `task:t022`.

## Arc

The active hypotheses form a stack. **H01** sits at the bottom: a falsifiable, simulator-validated claim about budget allocation under noise. The H01 simulator interpretation drove the project's single load-bearing design refinement — that uncertainty-guided rather than stochastic exploration is the operative mechanism. Open work is the Gaussian-signal generalization (`task:t005`), the r-curve extension to resolve P5 (`task:t004`), and reason-coded uncertainty features (`task:t025`) that bridge H01 to H03.

**H02** sits one layer up: it claims that storing structured evidence payloads improves graph calibration. It was drafted alongside H03 and H04 in `task:t027` after Batch 2 synthesis, then expanded across Batches 3–6 to cover causal graph construction, graph-valued integration, agent/KG operations, and robustness/reproducibility evaluation. Its falsifiability hinges on a replay benchmark and on the authoring-cost audit (`task:t030`).

**H03** sits parallel to H02 at the attention layer: it claims that revisiting policies guided by typed *reason codes* beat policies guided by posterior magnitude alone. It depends on the H02 schema work (`task:t021`/`task:t022`) and on a simulator extension (`task:t025`) that has not started. Its evaluation will likely require an annotation audit before any simulator comparison is meaningful.

**H04** narrows H02 to causal targets: requiring estimand, contrast, transport, and identification metadata before synthesized evidence can strengthen a causal edge. Its theoretical grounding is one-source per claim (Petersen2014, Berenfeld2026, Majumdar2022), and no audit of false-causal-strengthening rates has been run.

The four active hypotheses are best understood as one schema-design programme with four falsifiable lenses. H01 supplies the empirical anchor; H02, H03, H04 each define a distinct calibration target the schema must hit (calibration error, attention quality, causal-edge precision). They are co-bottlenecked on `task:t022`.

## Research fronts

Across the four active hypotheses, the highest-leverage fronts in priority order:

1. **`task:t022` — Design minimum quantitative evidence payload schema (P1).** Bottleneck for H02, H03, H04. Source: `synthesis:0010-rich-evidence-payloads-improve-graph-calibration`, `synthesis:0011-reason-coded-revisiting-beats-posterior-only-revisiting`, `synthesis:0012-causal-estimand-guardrails-reduce-false-causal-edge-strengthening`.
2. **`task:t030` — Audit authoring cost of the proposed schema (P1).** First empirical test of H02's P3 minimality claim. Blocks claims about practical viability. Source: `synthesis:0010-rich-evidence-payloads-improve-graph-calibration`.
3. **`task:t026` — Causal synthesis guardrails (P2).** H04's primary implementation surface; downstream of `task:t022`. Source: `synthesis:0012-causal-estimand-guardrails-reduce-false-causal-edge-strengthening`.
4. **`task:t025` — Reason-coded uncertainty features for H01 attention (P2).** H03's primary implementation surface; bridges H01 simulator findings to H03 attention claim. Source: `synthesis:0009-stochastic-revisiting`, `synthesis:0011-reason-coded-revisiting-beats-posterior-only-revisiting`.
5. **`task:t034` / `task:t035` — Causal graph construction pipeline artifacts and graph-valued synthesis artifact schema (P1).** Define the artifact taxonomies H02/H03/H04 all reference. Source: `synthesis:0010-rich-evidence-payloads-improve-graph-calibration`, `synthesis:0012-causal-estimand-guardrails-reduce-false-causal-edge-strengthening`.
6. **`task:t005` — Gaussian effect-size variant of the H01 simulator (P3).** Tests whether H01's recall finding generalizes beyond Beta-Bernoulli signals; bounds the strength of D-003's continuous-belief commitment. Source: `synthesis:0009-stochastic-revisiting`.
7. **`task:t004` — Extend H01 r-curve to resolve P5 (P2).** Cleanup; resolves the only H01 proposition that was not testable in the current sweep. Source: `synthesis:0009-stochastic-revisiting`.
8. **`task:t040` — Robustness/reproducibility evaluation schema (P1).** Defines the typed validation outcomes H02 calibration needs as ground truth. Source: `synthesis:0010-rich-evidence-payloads-improve-graph-calibration`.

## Candidate frames

`hypothesis:0005-sequential-evidence-improves-attention` is the only candidate (phase: speculative). The conjecture is that anytime-valid procedures (e-values, test martingales, confidence sequences) produce better-calibrated attention and stopping than fixed-N Bayesian aggregation when evidence arrives sequentially with optional stopping and unbounded revisiting. Support is architectural only, drawn from three external sources (Mulder2026, Aitken2024, Maier2022) plus reading leads in `task:t028`. The hypothesis was deliberately registered speculative so that its design question (`question:0007-sequential-anytime-valid-evidence`) had a formal home and the graduate-or-retire decision could be made explicitly. The graduation gate is `task:t032`: ingest the queued references, audit project graph state for optional-stopping prevalence, propose an H01-simulator extension that models sequential arrival, and issue a verdict. Until then H05 remains conjecture; see `synthesis:0013-sequential-evidence-improves-attention` for full bundle. The motivating concern is real — H01 already assumes a fixed budget and H02 already assumes scoring against held-out validation outcomes — both of which strain when evidence accrues sequentially with optional stopping.

## Knowledge Gaps (rollup)

| Topic | Coverage | Demand | Gap | Hypotheses |
|---|---|---|---|---|
| topic:structured-scientific-knowledge | 0 | 3 | 3 | hypothesis:0002-rich-evidence-payloads-improve-graph-calibration |

The single registered gap reflects a literature shortfall in structured-scientific-knowledge representation that is demanded by `question:0005-authoring-cost-audit`, `question:0006-source-dependence-detection`, and `question:0008-llm-agents-as-fallible-sources` but has no covering paper batch yet. `task:t028`, `task:t036`, `task:t039`, and `task:t041` are the literature follow-up tracks that would close it.

## Emergent threads

See `doc/reports/synthesis/_emergent-threads.md` for the cross-cutting analysis. Six questions resolve against two or more hypotheses (`question:0002-evidence-payload-schema`, `question:0010-causal-graph-construction-pipeline`, `question:0011-graph-valued-synthesis-artifacts`, `question:0004-source-and-pipeline-provenance`, `question:0012-agent-tool-kg-operations`, `question:0013-robustness-reproducibility-evaluation`), confirming that the H02/H03/H04 stack is one programme with three lenses. One orphan question remains: `question:0009-mcda-bayesian-interoperability`. The emergent-threads file proposes two candidate hypotheses to fill the gaps — an MCDA/Bayesian interface hypothesis and an operational-provenance-as-first-class-tier hypothesis.

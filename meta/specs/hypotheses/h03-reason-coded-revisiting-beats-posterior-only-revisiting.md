---
id: hypothesis:h03-reason-coded-revisiting-beats-posterior-only-revisiting
type: hypothesis
title: Reason-coded revisiting beats posterior-only revisiting
status: proposed
phase: active
source_refs:
- paper:Zhao2012
- paper:Li2016
- paper:Allen2017
- paper:Maier2022
- paper:Volker2023
- paper:VanWonderen2024
- paper:Semochkina2025
- paper:Han2026
- paper:Dong2023
- paper:Faller2024
- paper:Jiralerspong2024
- paper:Liu2024HiddenWorld
- paper:Zheng2024
- paper:Zhang2021JointGraphical
- paper:Vahabi2022
- paper:Deleu2023
- paper:Mohammadi2025
- paper:Alnajjar2026
- paper:Ding2025
- paper:Jin2025
- paper:Si2025
- paper:Yu2026
related:
- question:01-evidence-payload-schema
- question:03-source-and-pipeline-provenance
- question:10-causal-graph-construction-pipeline
- question:11-graph-valued-synthesis-artifacts
- question:12-agent-tool-kg-operations
- hypothesis:h01-stochastic-revisiting
- hypothesis:h02-rich-evidence-payloads-improve-graph-calibration
created: '2026-05-05'
updated: '2026-05-06'
---
# Hypothesis H03: Reason-coded revisiting beats posterior-only revisiting

## Organizing Conjecture

An attention policy that revisits uncertain propositions using reason-coded uncertainty signals will outperform a policy that revisits based only on posterior magnitude or scalar support.
The key claim is that "low confidence" is not one state.
A proposition down-weighted because evidence is underpowered, prior-sensitive, heterogeneous, source-dependent, missing a view, cleaned by an unvalidated pipeline, mismatched to the target population, hidden-variable-sensitive, self-incompatible, or supported only by weak LLM priors should be sampled differently from a proposition down-weighted by strong independent counterevidence [@Maier2022; @Volker2023; @VanWonderen2024; @Zhao2012; @Li2016; @Semochkina2025; @Han2026; @Dong2023; @Faller2024; @Jiralerspong2024; @Liu2024HiddenWorld].

## Proposition Bundle

### Core Propositions

**P1 (attention improvement).**
Reason-coded revisiting produces better final recall, calibration, or contradiction discovery than posterior-only revisiting at the same review budget.

**P2 (actionability).**
Reason codes improve attention because they identify the next useful action: seek independent sources, inspect priors, search for moderators, review cleaning provenance, check missingness, test transport assumptions, or request validation evidence.

**P3 (non-equivalence).**
Different uncertainty reasons with the same posterior magnitude have different expected value of review.
Posterior-only revisiting therefore loses information that is visible in the evidence payload.

### Supporting Or Auxiliary Propositions

**P4 (Batch 1 reasons).**
Underpowered evidence, high heterogeneity, publication-bias risk, prior sensitivity, imperfect labels, complex-hypothesis penalties, and estimand mismatch are useful attention features.

**P5 (Batch 2 reasons).**
Source unreliability, source dependence, ambiguous omission, missing view, source-target mismatch, prior-resolved non-identifiability, unvalidated cleaning, repair uncertainty, shared-structure assumptions, and missing debiased inference are useful attention features.

**P6 (Batch 3 reasons).**
Causal-sufficiency assumptions, latent-variable risk, unvalidated LLM priors, prior/data disagreement, ambiguous graph objects, self-incompatible discovery outputs, missing identification, and weak-prior-only support are useful attention features.

**P7 (Batch 4 reasons).**
Graph posterior uncertainty, unstable edge inclusion, shared-structure dependence, view-scope mismatch, approximation risk, unvalidated clustering, selected-feature instability, and exploratory-integration-only status are useful attention features.

**P8 (Batch 5 reasons).**
Unvalidated agent sources, unvalidated tool chains, missing safety checks, uncertain context retrieval, undetected information absence, derived KG views, stale graph versions, agent bias risk, and attention-not-evidence status are useful attention features.

**P9 (observable-state constraint).**
Reason-coded attention can be implemented from explicit graph state and evidence payload fields without relying on LLM-estimated probabilities.

## Current Uncertainty

- H01 is already supported in a Beta-Bernoulli simulator, but H03 has not been simulated.
- The value of reason codes depends on whether the payload schema captures them consistently enough.
- The right objective function is unresolved: recall of true propositions, calibration, correction of stale conclusions, discovery of contradictions, or researcher-time efficiency.
- Some reasons may overlap heavily. For example, source dependence and shared pipeline bias may require one representation, not two.
- Batch 3 adds a stronger granularity problem: graph-object ambiguity, prior/data disagreement, and identification-missing may be separate reasons or different severities of one causal-discovery guardrail failure.
- Batch 4 adds another granularity problem: graph-posterior uncertainty, edge-inclusion instability, and selected-feature instability may be separate reason codes or shared variants of posterior-uncertainty reason codes.

## Predictions

- At equal review budget, reason-coded policies will recover more initially down-weighted true propositions than posterior-only policies in settings with heterogeneous failure modes.
- Reason-coded policies will spend less effort rechecking claims whose low support came from strong independent counterevidence.
- When shared pipeline bias or source copying is present, reason-coded policies will prioritize independent provenance checks more often than posterior-only policies.
- When causal-discovery outputs are present, reason-coded policies will prioritize hidden-variable checks, self-compatibility diagnostics, identification review, and independent validation more often than posterior-only policies.
- When graph-valued integration outputs are present, reason-coded policies will prioritize posterior graph review, independent-view validation, cluster validation, selected-feature stability checks, and shared-structure sensitivity more often than posterior-only policies.
- The gain over posterior-only revisiting will shrink in simple simulations where all uncertainty comes from identical independent noise.

## Falsifiability

- **P1 disconfirmed:** reason-coded policies fail to improve recall, calibration, or contradiction detection over posterior-only revisiting in realistic heterogeneous simulations.
- **P2 disconfirmed:** reason codes do not reliably map to different useful actions.
- **P3 disconfirmed:** posterior magnitude already captures the relevant expected value of review once evidence count and freshness are included.
- **P9 disconfirmed:** the necessary reason codes cannot be derived from explicit graph state and require subjective LLM judgment.

## Supporting Evidence

- `simulation_evidence` - H01's existing simulator shows that exploration-based policies beat hard-gating when early evidence is noisy, motivating richer attention rules.
- `literature_evidence` - Batch 1 papers show multiple non-equivalent reasons for uncertain or misleading evidence, including heterogeneity, publication bias, prior sensitivity, low power, and estimand mismatch [@Maier2022; @Volker2023; @VanWonderen2024].
- `literature_evidence` - Batch 2 papers add source and pipeline reasons: source reliability, source dependence, omissions, missing views, non-identifiability, and cleaning provenance [@Zhao2012; @Li2016; @Allen2017; @Semochkina2025; @Han2026].
- `literature_evidence` - Batch 3 papers add causal-graph-construction reasons: hidden-variable sensitivity, self-incompatibility, ambiguous graph object type, unvalidated LLM priors, prior/data disagreement, and missing identification [@Dong2023; @Faller2024; @Jiralerspong2024; @Liu2024HiddenWorld; @Zheng2024].
- `literature_evidence` - Batch 4 papers add graph-valued integration reasons: graph posterior uncertainty, edge inclusion instability, shared-structure dependence, view-scope mismatch, approximation risk, unvalidated clustering, and unstable selected features [@Zhang2021JointGraphical; @Vahabi2022; @Deleu2023; @Mohammadi2025; @Alnajjar2026].
- `literature_evidence` - Batch 5 papers add operational reasons: unvalidated agent/tool chains, missing safety checks, context retrieval uncertainty, information-absence failures, derived KG views, stale graph versions, and agent bias risk [@Ding2025; @Jin2025; @Si2025; @Yu2026].

## Disputing Evidence

- No direct comparison between reason-coded and posterior-only revisiting exists in this project yet.
- A simpler posterior-only policy may be enough if graph freshness, evidence count, and support/dispute imbalance already proxy for the same failure modes.
- Too many reason codes could make attention noisy unless the code set is compact and tied to clear actions.

## Evidence Needed To Shift Belief

- Extend the H01 simulator with heterogeneous failure modes: low power, shared source copying, publication bias, missingness, source-target mismatch, prior sensitivity, hidden-variable risk, weak-prior-only support, self-incompatible graph output, missing identification, graph posterior uncertainty, view-scope mismatch, clustering instability, selected-feature instability, stale graph versions, unvalidated agents, and failed abstention.
- Compare posterior-only, freshness-weighted, and reason-coded attention policies at equal review budget.
- Run an annotation audit over existing paper summaries to test whether reason codes can be assigned consistently from documented evidence fields.
- Measure whether reason-coded sampling produces different and better next actions in real curation sessions.

## Related Work

- `hypothesis:h01-stochastic-revisiting` is the parent attention hypothesis.
- `hypothesis:h02-rich-evidence-payloads-improve-graph-calibration` supplies the payload fields needed to derive reason codes.
- `question:01-evidence-payload-schema`, `question:03-source-and-pipeline-provenance`, `question:10-causal-graph-construction-pipeline`, `question:11-graph-valued-synthesis-artifacts`, and `question:12-agent-tool-kg-operations` define the representation problem.

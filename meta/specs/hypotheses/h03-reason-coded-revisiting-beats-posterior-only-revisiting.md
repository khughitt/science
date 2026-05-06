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
related:
- question:01-evidence-payload-schema
- question:03-source-and-pipeline-provenance
- hypothesis:h01-stochastic-revisiting
- hypothesis:h02-rich-evidence-payloads-improve-graph-calibration
created: '2026-05-05'
updated: '2026-05-05'
---
# Hypothesis H03: Reason-coded revisiting beats posterior-only revisiting

## Organizing Conjecture

An attention policy that revisits uncertain propositions using reason-coded uncertainty signals will outperform a policy that revisits based only on posterior magnitude or scalar support.
The key claim is that "low confidence" is not one state.
A proposition down-weighted because evidence is underpowered, prior-sensitive, heterogeneous, source-dependent, missing a view, cleaned by an unvalidated pipeline, or mismatched to the target population should be sampled differently from a proposition down-weighted by strong independent counterevidence [@Maier2022; @Volker2023; @VanWonderen2024; @Zhao2012; @Li2016; @Semochkina2025; @Han2026].

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

**P6 (observable-state constraint).**
Reason-coded attention can be implemented from explicit graph state and evidence payload fields without relying on LLM-estimated probabilities.

## Current Uncertainty

- H01 is already supported in a Beta-Bernoulli simulator, but H03 has not been simulated.
- The value of reason codes depends on whether the payload schema captures them consistently enough.
- The right objective function is unresolved: recall of true propositions, calibration, correction of stale conclusions, discovery of contradictions, or researcher-time efficiency.
- Some reasons may overlap heavily. For example, source dependence and shared pipeline bias may require one representation, not two.

## Predictions

- At equal review budget, reason-coded policies will recover more initially down-weighted true propositions than posterior-only policies in settings with heterogeneous failure modes.
- Reason-coded policies will spend less effort rechecking claims whose low support came from strong independent counterevidence.
- When shared pipeline bias or source copying is present, reason-coded policies will prioritize independent provenance checks more often than posterior-only policies.
- The gain over posterior-only revisiting will shrink in simple simulations where all uncertainty comes from identical independent noise.

## Falsifiability

- **P1 disconfirmed:** reason-coded policies fail to improve recall, calibration, or contradiction detection over posterior-only revisiting in realistic heterogeneous simulations.
- **P2 disconfirmed:** reason codes do not reliably map to different useful actions.
- **P3 disconfirmed:** posterior magnitude already captures the relevant expected value of review once evidence count and freshness are included.
- **P6 disconfirmed:** the necessary reason codes cannot be derived from explicit graph state and require subjective LLM judgment.

## Supporting Evidence

- `simulation_evidence` - H01's existing simulator shows that exploration-based policies beat hard-gating when early evidence is noisy, motivating richer attention rules.
- `literature_evidence` - Batch 1 papers show multiple non-equivalent reasons for uncertain or misleading evidence, including heterogeneity, publication bias, prior sensitivity, low power, and estimand mismatch [@Maier2022; @Volker2023; @VanWonderen2024].
- `literature_evidence` - Batch 2 papers add source and pipeline reasons: source reliability, source dependence, omissions, missing views, non-identifiability, and cleaning provenance [@Zhao2012; @Li2016; @Allen2017; @Semochkina2025; @Han2026].

## Disputing Evidence

- No direct comparison between reason-coded and posterior-only revisiting exists in this project yet.
- A simpler posterior-only policy may be enough if graph freshness, evidence count, and support/dispute imbalance already proxy for the same failure modes.
- Too many reason codes could make attention noisy unless the code set is compact and tied to clear actions.

## Evidence Needed To Shift Belief

- Extend the H01 simulator with heterogeneous failure modes: low power, shared source copying, publication bias, missingness, source-target mismatch, and prior sensitivity.
- Compare posterior-only, freshness-weighted, and reason-coded attention policies at equal review budget.
- Run an annotation audit over existing paper summaries to test whether reason codes can be assigned consistently from documented evidence fields.
- Measure whether reason-coded sampling produces different and better next actions in real curation sessions.

## Related Work

- `hypothesis:h01-stochastic-revisiting` is the parent attention hypothesis.
- `hypothesis:h02-rich-evidence-payloads-improve-graph-calibration` supplies the payload fields needed to derive reason codes.
- `question:01-evidence-payload-schema` and `question:03-source-and-pipeline-provenance` define the representation problem.

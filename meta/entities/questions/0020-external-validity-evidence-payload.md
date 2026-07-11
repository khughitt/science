---
id: question:0020-external-validity-evidence-payload
kind: question
title: How should Science represent external validity metadata (generalizability vs.
  transportability, M-STOUT scope) in evidence payloads?
status: active
ontology_terms: []
datasets: []
source_refs:
- cite:Findley2021
related:
- hypothesis:0004-causal-estimand-guardrails-reduce-false-causal-edge-strengthening
- hypothesis:0002-rich-evidence-payloads-improve-graph-calibration
- question:0001-bioinformatics-generalizability
- question:0003-causal-synthesis-guardrails
created: '2026-07-10'
updated: '2026-07-10'
---

# How should Science represent external validity metadata (generalizability vs. transportability, M-STOUT scope) in evidence payloads?

## Summary

Science evidence payloads currently record source population, study design, and estimand fields but do not distinguish whether an inference is a generalizability claim (sample drawn from the same population; S ⊆ P) or a transportability claim (sample from a different population than the target; S ⊄ P_target).
Findley et al. [@Findley2021] show that these two inference types require different assumptions, carry different bias structures (sample selection bias bP vs. variable selection bias bV), and should target different estimands (PATE vs. TATE).
This question asks how Science should extend its evidence-payload schema and causal-guardrail checks to represent M-STOUT scope dimensions (mechanisms, settings, treatments, outcomes, units, time) and to require an explicit generalizability-vs-transportability declaration before evidence from one context can strengthen a proposition about another.

## Why It Matters

- Affects H04 (causal-estimand guardrails): the current guardrail requires transport or exchangeability assumptions but does not distinguish sample-selection bias paths from variable-selection bias paths, and does not require an explicit M-STOUT scope declaration. A missing scope declaration allows cross-context evidence to strengthen causal propositions silently.
- Affects H02 (rich evidence payloads): M-STOUT dimensions (mechanism invariance, temporal scope, treatment construct validity, unit representativeness) are evidence quality axes that belong in the payload schema.
- Affects Q01 (bioinformatics generalizability): the formal transportability framework provides the conceptual apparatus for asking whether replication-crisis findings transport to genomics — but only if Science payloads record the source-study M-STOUT profile and the required transport assumptions.
- Risk if unanswered: Science will continue treating same-population and cross-population evidence equivalently, allowing variable-selection bias (operationalization mismatch) and sample-selection bias (non-representative source studies) to silently inflate belief in causal propositions that do not hold for the target population.

## Current Evidence

- Findley et al. [@Findley2021] formalize external validity bias as SATE = PATE + bP (sample selection bias) + bV (variable selection bias when operationalizations differ), showing that each bias component requires different remediation (representativeness vs. construct validity respectively).
- The M-STOUT framework (mechanisms, settings, treatments, outcomes, units, time) extends UTOS and provides the six axes along which scope must be declared and causal interaction must be assessed before external validity inferences are credible [@Findley2021].
- H04's guardrail already partially addresses this: it requires target population, source population, transport or exchangeability assumptions, and covariate coverage — but does not enforce the generalizability-vs-transportability distinction or mechanism-invariance claims.
- Q15 (claim-operationalization drift) addresses a related failure mode — construct validity drift over time within a project — which overlaps with variable-selection bias when the operationalization used in a source study does not match the theoretical construct in the target proposition.
- No existing Science payload schema fields cover temporal scope of source evidence or mechanism-invariance claims, both required for M-STOUT completeness.

## Thoughts

- Best current interpretation: extend H04's required transport-assumption field set to include: (a) `inference_type` (generalizability | transportability), (b) `mstout_scope` covering mechanism invariance claim, source-study setting, treatment construct match, outcome construct match, unit population match, and temporal scope, and (c) `bias_risk` flags for sample-selection and variable-selection bias paths. This makes the guardrail's transport assumptions explicit rather than free-text.
- The generalizability/transportability distinction could also drive different guardrail thresholds: transportability claims (S ⊄ P_target) should require stronger justification than same-population generalizability claims.
- The major uncertainty is authoring cost: adding six M-STOUT fields to every evidence payload would be burdensome. A pragmatic initial design might require only `inference_type` and flag the M-STOUT fields as recommended rather than required, blocking only when `transportability` is declared without any transport-assumption text.

## Connections to Project

- Related hypotheses: `hypothesis:0004-causal-estimand-guardrails-reduce-false-causal-edge-strengthening`, `hypothesis:0002-rich-evidence-payloads-improve-graph-calibration`.
- Required data or analyses: audit a sample of existing evidence payloads to estimate the proportion that are transportability-type and whether transport assumptions are currently recorded; prototype the `inference_type` field and check whether authoring cost is acceptable.
- Priority level: medium — important for correctness of cross-study evidence aggregation, but lower urgency than the core guardrail P1/P2 fields already specified in H04.

## Related

- Topic notes: see `topic:analytic-flexibility-and-replication` for the replication-crisis context that motivates external validity concerns.
- Article notes: `paper:Findley2021`.
- Methods/Datasets: external validity, generalizability, transportability, M-STOUT, causal estimand, sample selection bias, variable selection bias.

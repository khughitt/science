---
id: question:0022-mechanism-perspective-evidence-typing
kind: question
title: Should the evidence payload schema carry a mechanism-perspective field to distinguish
  interventionist, contextual, and constitutive evidence?
status: active
ontology_terms: []
datasets: []
source_refs:
- cite:Cornelissen2025
related:
- question:0002-evidence-payload-schema
- question:0003-causal-synthesis-guardrails
- hypothesis:0004-causal-estimand-guardrails-reduce-false-causal-edge-strengthening
created: '2026-07-10'
updated: '2026-07-10'
---

# Should the evidence payload schema carry a mechanism-perspective field to distinguish interventionist, contextual, and constitutive evidence?

## Summary

Cornelissen and Werner (2025) identify three epistemologically distinct ways that researchers conceptualize and study causal mechanisms: interventionist (mechanism as mediating variable identified via experiment or quasi-experiment), contextual (mechanism as situated causal process inferred from case data), and constitutive (mechanism as integrative analytical model bridging micro and macro levels).
Each perspective produces different kinds of evidence, involves different inference procedures, and carries different inferential challenges.
This question asks whether Science's evidence payload schema should include a `mechanism_perspective` field (or equivalent typing vocabulary) so that evidence from these three traditions is not treated as interchangeable when updating causal propositions or causal graph edges.

## Why It Matters

- If all mechanism-bearing evidence is stored under the same schema fields regardless of perspective, then interventionist mediation estimates, contextual process-tracing inferences, and constitutive model-derivations will be lumped into the same update pathway — with no way to apply perspective-appropriate guardrails or to flag when a proposition is supported by only one kind of mechanism evidence.
- Interventionist evidence requires estimand, effect measure, and target population metadata before it can safely strengthen a causal edge (H04 guardrail); contextual evidence requires process-tracing provenance and abductive inference record; constitutive evidence requires specification of the micro-macro bridging assumptions and component-part decomposition.
- Risk if unanswered: Science's evidence synthesis may conflate rhetorical mechanism labels (gerundive constructions with no operational content) with substantive mechanism evidence, weakening causal graph calibration and making the H04 guardrail incomplete.

## Current Evidence

- Cornelissen and Werner (2025) demonstrate empirically that all three perspectives are prevalent in management research and are often used without clearly distinguishing the epistemological assumptions involved [@Cornelissen2025].
- The "gerundive mechanism" critique (Stinchcombe, 1991, cited in the paper) identifies a specific quality failure mode: nominalizations that sound mechanistic but merely redescribe observed contingencies — exactly the kind of label that an untyped evidence field would accept without challenge.
- The existing evidence payload schema (`question:0002-evidence-payload-schema`) currently addresses effect-measure, estimand, and transport assumptions for quantitative evidence but does not distinguish mechanism-level evidence by epistemological tradition.
- The H04 guardrail (causal-estimand guardrails) already addresses the interventionist pathway; contextual and constitutive pathways remain unguarded.

## Thoughts

- Best current interpretation: a `mechanism_perspective` field with values {interventionist, contextual, constitutive, mixed} would allow perspective-appropriate validation rules and would make the evidence type explicit in the graph, supporting more nuanced synthesis queries.
- The field need not block updates — it could serve as a classification that routes evidence through the right subset of guardrail checks (estimand completeness for interventionist; process-tracing provenance for contextual; micro-macro bridging assumption record for constitutive).
- Major uncertainty: it is unclear whether a three-way vocabulary is fine enough. Contextual studies in the corpus span critical-realist generative mechanism inference and constructivist process models, which have different epistemic standing. The vocabulary may need to be extensible or mapped to a controlled ontology.

## Connections to Project

- Related hypotheses: `hypothesis:0004-causal-estimand-guardrails-reduce-false-causal-edge-strengthening` (the interventionist guardrail is already partially specified; this question asks whether to extend the type system to all three perspectives).
- Required data or analyses: audit a sample of mechanism-bearing evidence entries in the project for their implied methodological tradition; assess coverage by the existing schema fields.
- Priority level: medium — the interventionist pathway is the highest-frequency case and already guarded by H04; contextual and constitutive pathways become higher priority once the toolkit is used for qualitative evidence or multi-level modeling tasks.

## Related

- Topic notes: causal evidence typing, mechanism ontology.
- Article notes: `paper:Cornelissen2025`, `paper:Fedak2015`.
- Methods/Datasets: none yet.

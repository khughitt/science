---
id: question:0024-cross-perspective-mechanism-triangulation
kind: question
title: How should convergence of interventionist, contextual, and constitutive mechanism
  evidence update causal belief in the toolkit?
status: active
ontology_terms: []
datasets: []
source_refs:
- cite:Cornelissen2025
related:
- question:0022-mechanism-perspective-evidence-typing
- question:0003-causal-synthesis-guardrails
- hypothesis:0007-working-model
created: '2026-07-10'
updated: '2026-07-10'
---

# How should convergence of interventionist, contextual, and constitutive mechanism evidence update causal belief in the toolkit?

## Summary

Cornelissen and Werner (2025) argue that the three methodological perspectives on mechanisms — interventionist, contextual, constitutive — are epistemologically distinct and each has characteristic inferential strengths and blind spots [@Cornelissen2025].
Epistemological pluralism suggests that convergence across perspectives constitutes stronger mechanistic evidence than convergence within a single perspective.
Cornelissen and Kaandorp (2023) formalize this as "causal triangulation."
This question asks how the Science toolkit should represent and weight cross-perspective convergence: whether converging interventionist + contextual + constitutive evidence for the same causal mechanism should receive higher belief or a different propagation treatment than evidence from a single perspective.

## Why It Matters

- Affects how multi-evidence belief updates are computed when evidence sources carry different `mechanism_perspective` labels (question:0022-mechanism-perspective-evidence-typing).
- If convergence across perspectives is treated identically to convergence within a single perspective, the epistemic bonus of cross-perspective triangulation is invisible to the toolkit.
- Risk if unanswered: the toolkit may assign high confidence to a causal mechanism supported by many interventionist mediation estimates but zero contextual or constitutive evidence, without flagging the one-perspective concentration as a calibration risk — exactly the microscopic-bias failure mode Cornelissen and Werner identify.

## Current Evidence

- Cornelissen and Werner (2025) argue that cross-perspective perspective taking can offset each perspective's characteristic inferential challenges, suggesting that convergence across perspectives is stronger than within-perspective replication [@Cornelissen2025].
- Cornelissen and Kaandorp (2023) propose causal triangulation as a formal alternative to causal identification: seeking convergence from multiple methods, designs, and perspectives rather than the "gold standard" of a single identified RCT.
- The h00 working model's evidence moves prior to posterior within a patch; the current model does not distinguish evidence by mechanism perspective when computing the posterior.
- H02 (rich evidence payloads improve graph calibration) is the parent hypothesis; this question asks for a mechanism-perspective extension of the payload enrichment argument.

## Thoughts

- Best current interpretation: cross-perspective convergence should at minimum be surfaced as a metadata signal (e.g., a `mechanism_perspective_coverage` annotation on a causal proposition); whether it should affect the belief scalar directly or only the confidence / uncertainty interval is an open modeling question.
- A conservative approach: use perspective-type diversity as a bias-resistance signal rather than a direct belief update — propositions with only interventionist evidence are flagged for contextual or constitutive corroboration, without automatically inflating the posterior.
- Major uncertainty: the mapping between perspective diversity and epistemic independence is not straightforward; two interventionist studies from different labs may be more independent than one interventionist and one constitutive study by the same research group.

## Connections to Project

- Related hypotheses: `hypothesis:0007-working-model` (the patchwork model must accommodate evidence from all three perspectives); `hypothesis:0002-rich-evidence-payloads-improve-graph-calibration` (richer payload types improve calibration, and perspective diversity is a payload dimension).
- Required data or analyses: design a controlled comparison between same-perspective and cross-perspective evidence bundles for a set of causal propositions; evaluate whether cross-perspective convergence correlates with downstream validity metrics.
- Priority level: low in the near term (question:0022-mechanism-perspective-evidence-typing is a prerequisite); medium once mechanism-perspective typing is implemented.

## Related

- Topic notes: causal triangulation, epistemological pluralism, evidence independence.
- Article notes: `paper:Cornelissen2025`, `paper:Fedak2015`.
- Methods/Datasets: none yet.

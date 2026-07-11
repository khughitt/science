---
id: question:0040-ame-persistence-audit-for-evidence-streams
kind: question
title: "Does the toolkit's evidence-stream model expose an isolation bias \u2014 and\
  \ should AME-style persistence auditing be applied to patch maturation claims?"
status: active
ontology_terms: []
datasets: []
source_refs:
- cite:Rey2025
related:
- hypothesis:0007-working-model
- question:0013-robustness-reproducibility-evaluation
- question:0036-nomological-machine-patch-enabling-conditions
created: '2026-07-11'
updated: '2026-07-11'
---

# Does the toolkit's evidence-stream model expose an isolation bias — and should AME-style persistence auditing be applied to patch maturation claims?

## Summary

Rey (2025) argues that mechanistic explanation, ABM, and robustness analysis all share an
"isolation bias" — they presuppose that the systems they describe persist under realistic
open-system coupling, rather than explaining or testing persistence. Active Memory Engineering
(AME) is introduced as a fourth meta-methodological audit that earns persistence-entitlement
through three criteria: alignment (temporal-environmental synchronization), memory utilization
(sensitivity beyond Markovian sufficiency), and stability under non-Markovian perturbations.

The analogous question for the Science toolkit is whether the patchwork model and its robustness
evaluation machinery expose the same isolation bias at the epistemic level. Specifically: (i) does
the toolkit treat evidence items as temporally independent (i.i.d.) when real evidence streams have
temporal correlation structure (citation waves, topic drift, sequential lab batches), constituting an
isolation presupposition? (ii) when the toolkit claims a patch has "matured" to a higher ladder
level by accumulating evidence, is that maturation claim licensed at the trajectory level (does it
persist under temporal perturbation of the evidence stream?), or is it a snapshot success? (iii)
should AME-style mechanism-breaking tests be added to the toolkit's robustness evaluation
protocol — targeting the stabilization pathway from evidence → stable belief, not merely the
invariance of the model parameters?

## Why It Matters

- **Affects `hypothesis:0007-working-model` patch maturation design**: if patch maturation
  claims are only snapshot successes, the working model over-claims. The ladder rungs (L0–L4)
  encode increasing causal warrant; that warrant needs to be trajectory-stable, not merely
  snapshot-valid.
- **Affects `question:0013-robustness-reproducibility-evaluation`**: the existing robustness
  schema (evaluation_target, modifier, modifier_domain) maps to AME's stability dimension but
  omits the temporal correlation structure of the perturbations. Whitened-noise robustness is
  necessary-but-not-sufficient for persistence-entitlement.
- **Affects evidence-payload schema design**: if evidence streams have non-i.i.d. temporal
  structure, payloads may need temporal-dependency metadata (batch identifier, citation wave,
  arrival order) to support correcting for the isolation bias at inference time.
- **Risk if unanswered**: the toolkit may assert patch maturation or belief stability based on
  evidence accumulation that is itself temporally correlated (literature topic drift inflating apparent
  support). This is the isolation-bias failure mode applied to epistemic model management.

## Current Evidence

- Rey (2025) establishes the diagnosis: the standard methodological triad presupposes persistence;
  AME specifies when persistence is earned vs. assumed [@Rey2025].
- `question:0013` already notes that robustness evaluation needs typed perturbation targets and
  explicit modifier domains — but the temporal structure of perturbations is not yet included.
- `question:0036` asks about encoding enabling conditions for patches; AME extends this to require
  that enabling conditions specify the temporal coupling regime (Markovian vs. non-Markovian),
  not only static domain context.
- The working model (`hypothesis:0007-working-model`) describes evidence dynamics as
  "evidence moves a patch prior → posterior" and "patch matures up the ladder as evidence
  accrues" — both are persistence claims. No explicit temporal-robustness check is currently
  specified.
- The double-counting discount in the t065/t066 pipeline is a special case: correcting for
  correlated co-occurrence is analogous to the memory-utilization audit. This suggests the
  toolkit already handles one non-i.i.d. evidence structure case, but without a general framework.

## Thoughts

- **Best current interpretation**: the toolkit's evidence model does expose a mild isolation bias.
  The most tractable fix is to add temporal-dependency metadata to evidence payloads (batch,
  arrival-period, citation-wave flag) and to extend the robustness evaluation schema in question:0013
  to include a `perturbation_temporal_structure` field (i.i.d. | coloured | non-Markovian | delay-
  structured). Full AME-style mechanism-breaking tests are aspirational for now.
- A minimal version of the persistence-entitlement check for patches would be: does the patch's
  posterior remain stable when the evidence is reordered or when the most recently-arrived batch
  is removed? This is closer to a leave-one-out stability check than a full trajectory audit, but it
  is feasible with current machinery.
- **Major uncertainty**: whether the isolation bias is a practical problem for the toolkit at its
  current scale (small evidence sets, carefully curated literature) or only becomes critical at scale
  (large automated literature ingestion with topic drift). Deferring to when automated ingestion
  is deployed may be pragmatically reasonable.

## Connections to Project

- Related hypotheses: `hypothesis:0007-working-model` (patch maturation as persistence claim),
  `hypothesis:0002-rich-evidence-payloads-improve-graph-calibration` (calibration under
  temporally correlated evidence).
- Required data or analyses: (1) audit existing evidence payloads for temporal-dependency
  metadata; (2) extend robustness evaluation schema to include perturbation temporal structure;
  (3) design a minimal trajectory-level stability check for patch maturation claims.
- Priority level: Medium — the isolation bias is real but the practical consequence is low at
  current scale. Becomes higher priority when automated literature ingestion (batched, topic-
  drifting) is implemented.

## Related

- Topic notes: `hypothesis:0007-working-model`, `question:0013-robustness-reproducibility-evaluation`,
  `question:0036-nomological-machine-patch-enabling-conditions`
- Article notes: `paper:Rey2025` (primary source for AME and isolation-bias diagnosis);
  `paper:Freiesleben2023` (robustness as stability under modifier interventions — needs temporal extension)
- Methods/Datasets: AME audit criteria (alignment, memory utilization, stability); leave-one-out
  evidence stability checks; temporal-dependency metadata for literature evidence payloads

---
id: proposition:richer-payloads-improve-calibration-non-additively
kind: proposition
title: Richer evidence payloads improve calibration non-additively via a cross-task
  help/harm profile
status: active
claim_layer: empirical_regularity
identification_strength: observational
proxy_directness: direct
supports_scope: local_proposition
discusses:
- hypothesis:0002-rich-evidence-payloads-improve-graph-calibration
related: []
source_refs:
- paper:Liu2025
created: '2026-07-10'
updated: '2026-07-10'
---
# Proposition: Richer evidence payloads improve calibration non-additively via a cross-task help/harm profile

## Claim

Richer evidence payloads improve calibration (`hypothesis:0002`), but the
improvement is **non-additive**: the marginal value of any added payload field
depends on a cross-task help/harm profile, so a signal that helps one objective can
*harm* a jointly-optimized one. Payload fields should therefore be selected by
*measured* cross-task improvement, not assumed to be uniformly beneficial. This
qualifies `hypothesis:0002` — "rich payloads improve calibration" holds on average
but must not be operationalized as "more fields are always better."

## Evidence Summary

*Evidence type: benchmark_evidence + literature_evidence.*
Liu et al. (BAITSAO) treat LLMs as fallible embedding engines with measurable
fidelity (GPT-3.5 ≈ GPT-4 ≈ Claude 3.5 on the task, validated against curated
DrugBank) and demonstrate that added information is *not* uniformly beneficial: a
Help-Harm matrix shows some signals hurt joint objectives [@Liu2025]. This is
direct evidence that payload enrichment interacts across tasks rather than summing,
and it motivates two design consequences: (a) select payload fields by measured
cross-task improvement rather than assumed additivity, and (b) represent
LLM-derived fields as sources with measurable fidelity, not infallible extractors,
with a minimal validation protocol against a curated reference (question:0038).

## Caveats

The Help-Harm evidence is from a single drug-synergy/embedding domain; whether the
non-additivity generalizes to Science's heterogeneous literature/database/experiment
payloads is untested and is itself the kind of cross-task measurement the claim
demands. BAITSAO measures task *performance* interaction, not calibration
interaction directly, so mapping "hurts a joint objective" onto "worsens belief
calibration" is a proxy step. The claim does not deny `hypothesis:0002`; it narrows
its operationalization from "add payloads" to "add payloads selected by measured
cross-task profile."

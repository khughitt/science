---
id: evidence-line:richer-payloads-liu2025
kind: evidence-line
title: BAITSAO's Help-Harm matrix shows added signals are non-additive
status: active
stance: supports
target: proposition:richer-payloads-improve-calibration-non-additively
source: paper:Liu2025
strength: moderate
independence: independent
independence_group: ''
evidence_role: background_constraint
evidence_type: literature
related: []
source_refs:
- paper:Liu2025
created: '2026-07-10'
updated: '2026-07-10'
---
# Evidence Line: BAITSAO's Help-Harm matrix shows added signals are non-additive

## What this line shows

Liu et al. (BAITSAO) treat LLMs as fallible embedding engines with measurable
fidelity (GPT-3.5 ≈ GPT-4 ≈ Claude 3.5, validated against curated DrugBank) and
demonstrate that added information is *not* uniformly beneficial: a Help-Harm matrix
shows some signals hurt joint objectives [@Liu2025]. This supports the proposition
that payload enrichment interacts across tasks rather than summing, so fields should
be selected by measured cross-task improvement.

## Why it is independent

A single primary source; there is one evidence line on this proposition, so no
independence conflict arises.

## Caveats / scope

Moderate strength: the Help-Harm evidence is from a single drug-synergy/embedding
domain, and BAITSAO measures task *performance* interaction, not belief calibration
directly — so mapping "hurts a joint objective" onto "worsens calibration" is a
proxy step. Whether the non-additivity generalizes to Science's heterogeneous
payloads is untested.

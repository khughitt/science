---
id: t112
project: ''
title: PHF19 survival effect stratified by t(4;14) status
type: ''
aspects:
- hypothesis-testing
- causal-modeling
- computational-analysis
priority: P2
status: proposed
blocked_by: []
related:
- hypothesis:h1-epigenetic-commitment
- inquiry:h1-prognosis
- question:nsd2-phf19-mirror-polycomb
- topic:PHF19
- topic:t414
- topic:NSD2
- topic:confounding
- topic:stratification
parent: ''
group: h1-phf19-mechanism
artifacts: []
findings: []
created: '2026-04-11'
completed: null
---

The mirror-image Polycomb test showed NSD2 and PHF19 operate at different genomic
loci (question:nsd2-phf19-mirror-polycomb, resolved). But the population-level
confound (t(4;14) -> survival via non-PHF19 mechanisms) is not yet tested.

**Approach:** Repeat t082-style Cox model (PHF19 ~ survival) stratified by virtual
FISH t(4;14) status. If PHF19 retains significance in t(4;14)- patients, the
other_high_risk_lesions backdoor is closed at both locus and population levels.

# ── DAG-Derived Tasks (2026-04-11 H2 model formalization) ─────────────────────
# Source: doc/discussions/2026-04-11-h2-dag-implications.md

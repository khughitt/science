---
id: t251
project: ''
title: Create H6 positive-selection DAG scaffold with 4 sub-claim branches (S1 pre-treatment
  selection / S2 treatment regime-change / S3 transcriptomic convergence / S4 niche-MGUS)
type: ''
aspects:
- causal-modeling
priority: P1
status: proposed
blocked_by: []
related:
- discussion:2026-04-19-dag-iteration-and-refinement
- article:Diamond2021
- article:Persi2025
- article:Cooperrider2025
- article:Misund2022
- article:Henry2025
parent: ''
group: dag-refresh
artifacts: []
findings: []
created: '2026-04-20'
completed: null
---

Per discussion:2026-04-19-dag-iteration-and-refinement Q4. Literature anchors: Diamond 2021 (98.2% non-neutral MM), Persi 2025 (dN/dS stable MGUS->MM, post-treatment shift toward neutrality), Cooperrider 2025 (LEN->TP53 selection), Misund 2022 (pathway convergence on proliferation), Henry 2025 (adaptive oncogenesis). Depends on t216 creating specs/hypotheses/h6-positive-selection-mm-progression.md. Scope: build the proposition-backed `doc/figures/dags/h6-positive-selection.dot` DAG exposing the 4 sub-claims as branches.

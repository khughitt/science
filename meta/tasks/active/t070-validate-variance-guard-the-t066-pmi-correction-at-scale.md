---
id: t070
project: ''
title: Validate + variance-guard the t066 PMI correction at scale
type: ''
aspects: []
priority: P2
status: proposed
blocked_by: []
related: []
parent: ''
group: ''
artifacts: []
findings: []
created: '2026-06-01'
completed: null
---

t066 demonstrated the latent-construct (PMI) correction subtracts the publication-attention axis cleanly at BOTH ends of the slice (7 panel genes positive, 10 universal genes negative, for CMT + HSP) and flips raw-ranking errors. Two things it did NOT establish: (1) behavior on the ambiguous MIDDLE — the clean step is partly a property of a slice built to contrast extremes, so PPMI>0 is a correction, not a calibrated classifier; needs the full 18206x3831 matrix + held-out-panel validation (overlaps pan-disease recall@K / cluster-mate-AUC, the cross-project proving ground). (2) a sampling-variance guard — rare cells have high-variance PMI (e.g. CYP7B1 cooc=39); add shrinkage / Poisson-significance before any fine ranking or near-zero threshold. Code: meta/src/h00_patch_l1/latent.py. Interpretation: interpretation:0003-t066-latent-correction-2026-06-01.
---
id: t203
project: ''
title: Ledergor 2018 scRNA-seq replication of t174 Q1/Q2/Q3 — cohort independence
  for PC-maturity findings
type: ''
aspects:
- hypothesis-testing
- causal-modeling
- computational-analysis
priority: P1
status: active
blocked_by: []
related:
- task:t174
- task:t172
- task:t204
- task:t214
- hypothesis:h1-epigenetic-commitment
- hypothesis:h2-cytogenetic-distinct-entities
- question:ribosome-axis-pc-continuum-vs-nucleolar-stress
- report:2026-04-16-scrna-replication-shortlist
- interpretation:2026-04-17-t203-ledergor-replication
parent: ''
group: causal-dag-validation
artifacts: []
findings: []
created: '2026-04-14'
completed: null
---

**Panel executed 2026-04-17** (`interpretation:2026-04-17-t203-ledergor-replication`).
Formal verdict = `inconclusive_protocol_failure` (Q1/Q2 student-t continuous fits
fail PPC shape statistics). Face-value Q3 (NB, PPC pass) does **not** replicate
the t174 per-cell collapse: β\_ribosome = +0.544 under PC-maturity + phase +
library-size adjustment, P(β > 0) = 0.983. Q1 tumor-vs-healthy sign-flip does
not replicate: both Ledergor cohorts give positive β\_pc\_mature. Q2 face-value
nucleolar-stress signal positive, but RPL-removal sensitivity not fit.

**Narrow follow-ups queued:** refit Q1/Q2 with NB likelihood on raw ribosome-gene
counts (PPC-fix without changing sign/magnitude story), and add the
`sens_no_rpl` Q2 variant on the existing cache. Both are cheap reruns on the
staged infrastructure.

t174 used Boiarsky 2022 scRNA-seq (17 tumor + 8 NBM). Replication in an independent
MM scRNA-seq cohort is pre-committed (pre-reg §8.6 queued action) and tests whether:

(i) Q3 Full collapse replicates (PC-maturity + phase sufficient per-cell adjuster)
(ii) Tumor/NBM β_pc_mature sign-flip (t174 P7; tumor −0.31 vs NBM +0.51) replicates
(iii) Q2 RPL-corrected nucleolar-stress signal (β_ns ≈ +0.18) replicates

**Data source:** Ledergor et al. 2018 *Nat Med* (GSE117156, ~40 patients incl.
MGUS/SMM/MM/plasma-cell-leukemia + healthy BM); access patterns as in t173 scope.

**Approach:** reuse the t174 orchestrator infrastructure verbatim — the loader
module (boiarsky_loader) can be generalized or cloned for Ledergor. Signatures
are already locked in data/signatures/. Full-precision wall-clock estimate ~4-6
hrs based on t174 timings.

**Dataset triage (2026-04-16):** from `archive/mm_singlecell_datasets.tsv`, use
Ledergor2018 as the **primary low-friction replication cohort**. Processed counts
are available via HCA / CELLxGENE, it includes healthy + MM, and it is genuinely
independent of Boiarsky. Keep DeJong2021 as the first backup if Ledergor is
inconclusive for protocol reasons; defer EGA/dbGaP cohorts (Walker2024, Dang2023,
John2023, Landau2020) unless the low-friction path fails. See
`report:2026-04-16-scrna-replication-shortlist`.

**Output:** independent verdict JSON + interpretation doc. If (ii) replicates,
upgrade P7 to 'well-supported'. If (ii) fails, cohort-specific; downgrade to
'Boiarsky-specific' until a third cohort.

# numeric-anchor cross-project audit — 2026-07-18

Empirical grounding for the numeric-claim provenance-check redesign
(`docs/plans/2026-07-18-numeric-provenance-check-design.md`). Answers: *what kinds
of numbers does the `numeric-anchor` prose lint actually flag, and how many are
genuine?*

## Method

1. Discovered every science project (`science.yaml` marker) under `~/d`.
2. Swept `science validate --strict --all --format json` per project; counted
   `numeric-anchor` findings. Range: 0 (MM30, cbioportal, therapeutics — inline
   approach already applied) to 1416 (seq-feats).
3. Seeded-random sampled **40 flagged findings** from each of **8 flagged-heavy,
   domain-diverse projects** (320 total). For each finding, extracted the
   paragraph + entity frontmatter refs + doc-level anchor flags (`extract.py`
   logic; sampler seed 20260718).
4. One classifier sub-agent per project labeled each finding on four axes
   (`origin`, `category`, `traceability`, `handwavy`) against a shared schema.

`samples/*.jsonl` = the 320 findings (self-contained: number + paragraph + refs).
`results/*.json` = per-project classifications. `aggregate.json` = totals.

These double as the **regression oracle** for the redesign: the new check must
clear every `frontmatter-source-covers` / `cited-elsewhere-in-doc` / structural /
stipulated-param case and still flag every `truly-orphaned` one.

## Headline results (n=320)

**Origin:** internal-result 45% · external-cite 23% · stipulated-param 22% ·
structural 11% · ambiguous <1%.

**Traceability:** cited-elsewhere-in-doc 58% · frontmatter-source-covers 25% ·
**truly-orphaned ≤17%** (upper bound — the sampler under-captured `source_refs`,
so the real orphan rate is lower; two projects had 0–1/40).

**Hand-wavy: 3%.** Genuinely vague quantitative claims are rare.

## What it means

- **~83% of flags are false positives** — provenance exists at doc/frontmatter
  scope, just not in the flagged paragraph.
- **~33% are exempt-by-nature** — structural tokens (11%) + stipulated design
  params (22%) need no external source at all.
- **The genuine signal (~10%) is small and clustered** — narrative/manuscript
  docs restating the project's own computed statistics with no task ref, plus a
  few uncited domain facts. That is the residue the redesigned check should keep.

Three mechanical mis-fire patterns, found independently by every classifier:
paragraph-scope (provenance lives at entity scope); narrow anchor vocabulary
(misses `cite:`, `paper:`, bare author-year, inline `tNNN`, title-declared task,
config knobs); no claim-type awareness (structural + stipulated flagged anyway).

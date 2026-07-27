---
title: "Prose-lint baselines: natural-systems and multiple-myeloma"
date: 2026-05-10
related:
  - "docs/conventions/prose-lints.md"
  - "docs/conventions/annotation-tokens.md"
---

# Prose-lint baselines (2026-05-10)

First-run baselines for the four `science prose lint` checks against two real
Science projects, captured at branch `worktree-prose-lint-group` HEAD
(commit `b4b7c41`).

## Per-project totals

| Check | natural-systems | multiple-myeloma |
|---|---:|---:|
| `bare-author-year`        |    384 |   4,057 |
| `short-form-ids`          |  7,649 |  19,722 |
| `frontmatter-inline-gap`  |  2,540 |   3,294 |
| `numeric-anchor`          | 17,114 |  29,962 |
| **Total**                 | **27,687** | **57,035** |

## Top 10 per-file offenders (across all checks)

### natural-systems

```
   483  doc/reports/t132-full-cka-matrix-report.md
   475  doc/reports/structural-claims-audit.md
   463  doc/interpretations/2026-04-26-parameter-derivation-dag-v6.md
   439  doc/interpretations/2026-04-26-parameter-derivation-dag-v5.md
   429  doc/interpretations/2026-04-26-parameter-derivation-dag-v4.md
   423  doc/interpretations/2026-04-26-parameter-derivation-dag-v3.md
   413  doc/interpretations/2026-04-25-parameter-derivation-dag-v2.md
   412  doc/interpretations/2026-04-26-parameter-derivation-dag-v7.md
   399  doc/reports/parameter-overlap-report.md
   353  doc/interpretations/2026-04-13-parameter-derivation-dag.md
```

### multiple-myeloma

```
   652  doc/inquiries/h4-attractor-convergence.md
   552  doc/pre-registrations/2026-04-24-t280-bulk-vs-sc-pr-unimodality.md
   544  doc/meta/next-steps-2026-05-03.md
   533  doc/meta/next-steps-2026-04-24.md
   479  doc/meta/next-steps-2026-05-02.md
   454  doc/pre-registrations/2026-04-18-t204-bulk-composition-beyond-pc-maturity.md
   412  doc/pre-registrations/2026-04-18-t214-healthy-pc-maturation-signature.md
   400  doc/pre-registrations/2026-04-24-t278-dwell-time-cox.md
   390  doc/pre-registrations/2026-05-03-t469-hd-ap1-pc-maturity.md
   383  doc/inquiries/h-jun-hyperdiploidy-ap1.md
```

## Key observation: short-form-ids top tokens are mostly legitimate project refs

The `short-form-ids` regex `\b([qQhHtTdDiI])(\d{1,4})\b` is intended to catch
bare project-internal entity refs (e.g., `Q1`, `t088`) that should be
`question:q01-…` / `task:t088`. The initial concern was that biology shorthand
(histone `H3`, cyclin `D1`, T1-weighted MRI) would inflate counts with
false positives. Sampling the top 20 flagged tokens in multiple-myeloma reveals
a different picture:

```
  1715  H4
  1537  H1
  1443  H2
   567  t174
   414  H6
   352  t205
   345  t172
   303  t055
   287  Q1
   264  t197
   254  D2
   247  Q3
   242  t140
   230  h1
   225  t277
   199  Q2
   197  t204
   180  h2
   178  t412
   171  t214
```

Spot-checking confirms that the high-frequency `H1`–`H6` tokens in
multiple-myeloma are genuine project hypothesis short forms (the MM project
labels its hypotheses `H1`, `H2`, … `H6` in README and discussions), not
histone references. Similarly, `Q1`–`Q4` resolve to project question refs in
audit and discussion files, not statistical quartiles. The `t*` tokens are
unambiguously task short forms. `D2` in natural-systems points to discussion
refs (`D1`, `D2`) in a data-fitting review.

The false-positive concern is therefore **lower severity than originally
anticipated**: the regex is catching real violations at high volume, not
primarily incidental biology identifiers. The high counts for `H1`–`H4` in MM
reflect genuine adoption of short-form hypothesis refs throughout that project's
prose.

That said, the pattern remains a latent risk in biology projects that use terms
like `D1 cyclin`, `H3K27me3`, or `T1-weighted` frequently in their prose.
Should such a project be onboarded, the tuning options below apply.

### Tuning options (for genuinely affected projects)

1. **Per-project deny list** in `science.yaml`:
   ```yaml
   prose_lint:
     short_form_ids_deny:
       - D1   # cyclin D1
       - D2
       - D3
       - H1
       - H2
       - H3
       - H4   # histone family
       - T1   # T1-weighted MRI / T1 bacteriophage
       - T2
       - T3
       - T4
       - Q1   # quartile
       - Q2
       - Q3
       - Q4
       - I1   # immunoglobulin class notation
   ```
   Cleanest path; requires implementing the deny-list option.

2. **Stricter regex requiring a kind-prefix qualifier on lowercase forms** —
   only flag `q`/`h`/`t` short forms when followed by 2+ digits with a leading
   zero (`q01`, `t050`), which is the canonical Science project pattern. This
   reduces false positives at the cost of missing some legitimate `t1`/`q5`
   violations.

3. **Disable `short-form-ids` per project** by setting
   `prose_lint.enabled_checks` in `science.yaml` to exclude it. Appropriate
   only when the project's naming conventions genuinely collide with the
   regex and a deny list would be impractically long.

## Other observations

- **Numeric-anchor** produces the largest absolute counts in both projects
  (17,114 and 29,962). This is expected — `numeric-anchor` is `info`-severity
  by default and reflects how prose routinely discusses numeric findings without
  inline anchors. The signal is more useful per-file (which files cluster many
  unanchored numerics) than as a project-wide headline number. The top-offender
  lists above are dominated by this check; report and interpretation files
  naturally accumulate the most hits.

- **Frontmatter-inline-gap** counts (2,540 and 3,294) indicate genuine
  structural drift: each hit is a `related:` entry whose target path is never
  mentioned in the prose body. These are worth tackling file-by-file as part of
  the citation-audit pilot's gap-F follow-up. Unlike numeric-anchor, every hit
  represents a concrete actionable item (either add a mention or remove the
  stale `related:` entry).

- **Bare-author-year** is the highest-quality `warn` signal in both projects
  (384 and 4,057 hits). Each hit is a real candidate for either `[@key]`
  BibTeX-style annotation or promotion of the cited paper to
  `papers/<key>.md`. The large MM count relative to NS reflects the heavier
  literature-citation density in cancer biology projects.

## Pointers

- Lint catalog and severity rules: `docs/conventions/prose-lints.md`
- Origin (statement-citation gap analysis): `~/d/natural-systems/doc/interpretations/2026-05-06-citation-audit-pilot.md`
- Companion marker triage in MM (per-file UNVERIFIED disposition): `~/d/cancer/cancer-types/multiple-myeloma/doc/audits/2026-05-09-unverified-marker-triage.md`
- Current prose-lint convention: `docs/conventions/prose-lints.md`

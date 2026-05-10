---
title: "Refs body-scan baselines: natural-systems and multiple-myeloma"
date: 2026-05-10
related:
  - "docs/conventions/prose-lints.md"
  - "docs/audits/2026-05-10-prose-lint-baselines.md"
---

# Refs body-scan baselines (2026-05-10)

First-run baselines for `science refs check --include-body` against the same
two projects audited in the prose-lint baselines doc, captured at branch
`worktree-refs-body-and-deny` HEAD (commit `2cbc726`).

## Per-project ref_type totals

| ref_type          | natural-systems | multiple-myeloma |
|-------------------|----------------:|-----------------:|
| `body-entity-ref` |           1,410 |              134 |
| `task`            |               — |              448 |
| `pmid`            |               — |              410 |
| `doi`             |               — |              194 |
| `hypothesis`      |               — |               91 |
| `link`            |               — |                5 |
| **Total**         |       **1,410** |        **1,282** |

Notes:
- natural-systems had only `body-entity-ref` violations (no broken task/pmid/doi
  refs in its existing ref graph).
- multiple-myeloma's `task`, `pmid`, `doi`, `hypothesis`, and `link` counts come
  from the standard (non-body) ref check; `body-entity-ref` is the incremental
  addition from `--include-body`.

## body-entity-ref top file offenders

### natural-systems

```
   394  doc/reports/2026-05-08-visual-semantic-surface-inventory.md
    60  doc/meta/next-steps-2026-03-11.md
    48  doc/meta/next-steps-2026-03-11b.md
    42  doc/meta/skill-feedback.md
    30  doc/interpretations/2026-03-10-t30-t31-registry-corrections.md
    29  doc/discussions/2026-03-10-dimensionless-constituent-decomposition.md
    26  doc/reports/synthesis.md
    24  doc/discussions/2026-03-10-diffusion-ratio-audit-and-priorities.md
    24  doc/discussions/2026-03-11-lens-design-review.md
    20  doc/interpretations/2026-03-09-t08-matching-engine-expansion.md
```

The single largest contributor (394 hits, 28% of total) is a recent visual
semantic surface inventory report — a wide-ranging synthesis that naturally
references many entities by their `kind:id` form. The remaining high-count files
are meta and interpretation docs that were written before the frontmatter `id:`
index existed.

### multiple-myeloma

```
    44  doc/reports/synthesis/_emergent-threads.md
    15  doc/meta/topic-migration/canonical-topic-ledger-2026-04-22.md
    14  doc/reports/synthesis/h4-attractor-convergence.md
     8  doc/plans/2026-04-26-t304-myc-r-virtual-fish-pipeline-plan.md
     3  doc/inquiries/h2-hyperdiploid-novel-state-leads.md
     3  doc/inquiries/telomerase-prognosis-axis.md
     3  doc/plans/2026-04-24-t278-dwell-time-pipeline-plan.md
     3  doc/pre-registrations/2026-04-24-t278-dwell-time-cox.md
     2  doc/inquiries/proteostasis-myc-cin-modules.md
     2  doc/interpretations/2026-04-19-t219-mm30-hopfield-basins.md
```

Counts are much lower in MM (134 total, max 44 per file) reflecting a younger
project with fewer cross-entity refs embedded in prose.

## Comparison to natural-systems's `audit-citations.ts`

natural-systems already runs `audit-citations.ts` (tracked as task t469) which
validates body `<kind>:<id>` refs against `knowledge/graph.trig`. A fresh
`npm run audit:citations` run reports:

```
[audit-citations] ✗ 208 unresolved reference(s) in 108 file(s)
[audit-citations] scanned 823 files; 315 bib keys, 4310 entity ids
```

Filtering to entity-id violations only (the portion that overlaps with our
`body-entity-ref` check — lines matching `"entity id not registered"`):
**208 unresolved entity refs** (all 208 of audit-citations.ts's issues are
entity-id violations; the bib-key check found no broken `[@bibkey]` refs in
this run).

`science refs check --include-body` reports **1,410 `body-entity-ref`** issues
for natural-systems — approximately **6.8x more** than audit-citations.ts.

### Why the counts diverge

The gap reflects differences in truth sources and coverage:

1. **Truth source**: audit-citations.ts validates against `knowledge/graph.trig`
   (the compiled RDF graph of registered entities). `science refs check` uses a
   frontmatter `id:` sweep across all YAML front matter in the project tree.
   These two indexes overlap substantially but are not identical — entities that
   exist in the graph but lack a `id:` frontmatter field (or vice versa) will
   land differently in each count.

2. **Kind coverage**: audit-citations.ts matches a hardcoded 10-kind list when
   scanning body text. `science refs check --include-body` uses the full
   27-kind `_LOCAL_ENTITY_KINDS` registry, so it catches `<kind>:<id>` patterns
   that audit-citations.ts silently skips.

3. **File scope**: audit-citations.ts scans 823 files and finds 4,310 entity
   ids in the index. The frontmatter sweep covers a different file set (both
   the `doc/` tree and `specs/` hierarchy); discrepancies in which files are
   indexed explain additional divergence.

The directional story: `science refs check --include-body` is **more sensitive**
(wider kind coverage, different index) but uses a **weaker truth source**
(frontmatter `id:` vs. compiled RDF graph). For a project like natural-systems
that maintains `knowledge/graph.trig`, audit-citations.ts is currently the more
precise tool. Once the shared tool reaches feature parity on truth-source quality,
natural-systems can retire the custom TS script.

## Deny-list diagnostic

The new `prose_lint.short_form_ids_deny` config knob can suppress false-positive
short-form-IDs hits from biology shorthand. To diagnose whether a project needs
the knob, count how many top-token hits would be suppressed by a candidate
deny-list:

For multiple-myeloma with deny `[H1, H2, H3, H4, H5, H6, D1, D2, D3, T1, T2, T3]`:
- **5,879 of 19,764 short-form-IDs hits** would be suppressed (**29.7% of total**).

Note: per the prior prose-lint baselines audit, MM's `H1`–`H6` are **genuine
project hypothesis refs**, not biology shorthand — so applying this deny-list to
MM would wrongly suppress real signal. The diagnostic confirms what we already
knew: MM does not need a short-form-ids deny-list. These numbers serve as a
calibration reference: a project that legitimately needed to deny `H1`–`H6`
(e.g., a histone-biology project) would see a ~30% reduction in short-form-ids
noise for MM-sized prose corpora.

## Migration note

Once `science refs check --include-body` reaches feature parity with
`audit-citations.ts`, natural-systems can retire its custom TS script in favor
of the shared tool. The key open question is whether the frontmatter `id:` sweep
matches the breadth of the `knowledge/graph.trig` index in practice. The 6.8x
discrepancy above is the first directional evidence: more hits but using a
different (and currently weaker) truth source. Priority work before migration:

1. Validate that the frontmatter sweep covers all 4,310 entity ids that
   audit-citations.ts draws from graph.trig.
2. Extend `_LOCAL_ENTITY_KINDS` coverage in audit-citations.ts or confirm the
   10-kind list is intentional.
3. Assess whether the 1,202 hits that audit-citations.ts misses (1,410 − 208)
   are genuine violations or index gaps.

## Pointers

- `--include-body` flag implementation: `science/refs.py` (`_scan_body_typed_refs`)
- Lint catalog and severity rules: `docs/conventions/prose-lints.md`
- Deny-list config field: `prose_lint.short_form_ids_deny` in `science.yaml`
- Companion prose-lint baselines: `docs/audits/2026-05-10-prose-lint-baselines.md`
- natural-systems existing audit: `~/d/natural-systems/scripts/audit-citations.ts`

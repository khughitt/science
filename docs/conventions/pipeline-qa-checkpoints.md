# Pipeline QA Checkpoint Convention

This doc describes a concrete, reusable shape for the data-QA step the
`computational-analysis` aspect already calls for conceptually (see `plan-pipeline` →
*QA Checkpoints* and `review-pipeline` → *QA Coverage*). Those sections say *what* to
check; this one says *how to build the check* so it runs every pipeline invocation and
fails loudly when integrity breaks.

It is a deliberately-promoted single-project pattern (health-cycles) with a clear
cross-project rationale: in two separate pipelines the QA step caught source-level bugs
that every other check missed — a therapeutic-category code that was a silent superset of
another, and SAS XPORT special-missing values that survived as tiny denormal floats and
would have entered models as near-zero measurements. Any project whose pipeline produces a
processed analysis table feeding models or statistics should adopt it.

## The shape

A QA checkpoint is **one script + one workflow rule** that reads a processed table and
writes a markdown report — nothing more exotic:

- It is its own pipeline stage (e.g. a Snakemake rule), wired into the default target so
  it runs on every build, *after* the table it validates is produced.
- It reads the already-built table (`*.parquet` / `*.csv`), never the raw inputs — it
  validates the substrate analysis actually consumes.
- It writes a single `results/<workflow>/qa_report.md`: a header with row/entity counts,
  the flagged issues split by severity, and a per-variable distribution table. The report
  is a small text artifact — git-track it; it regenerates with the pipeline.

## Two severities

Every flag is one of two severities. This split is the load-bearing part of the pattern.

| Severity | Meaning | Failure mode |
| --- | --- | --- |
| **Structural** | A schema or integrity invariant is violated — the table is *wrong*, indicating an ingest/derive bug. | **Build-fatal.** The script exits non-zero (fail early), halting the pipeline. |
| **Distribution** | A value is *suspicious but possibly real* — an extreme assay value, a rare category, a heavy tail. | **Surfaced, not fatal.** Written to the report for analyst judgement; never auto-corrected. |

Structural checks encode things that must be true if the code is correct: unique primary
key, required columns present and complete, categorical values within an allowed set,
cross-field invariants (e.g. two flags that must be mutually exclusive), and guards against
known decode artifacts. Distribution checks encode physiological/domain plausibility:
value ranges, surviving missing-sentinels, outlier counts, survey-weight and design-variable
sanity.

## Principles

- **Report, don't correct (distribution).** A QA step surfaces suspicious values; it does
  not silently winsorize or drop them. The analyst decides at model time. (Explicit over
  defensive; no silent fallback.)
- **Fix structural problems at the source, then guard them.** When QA reveals a real
  defect, fix it at the boundary where it enters (the decode/ingest step), not in the QA
  script — then add a *structural* check so the fixed bug cannot silently return. A QA step
  that regression-guards a fix you already shipped is the highest-value check you can write.
- **Config-driven thresholds, single source of truth.** Plausibility ranges, allowed
  categorical codes, missing-sentinels, and invariant pairs live in the workflow config,
  not hardcoded in the script. Tightening a bound is a config edit, not a code change, and
  the same list (e.g. missing-sentinels) can be shared by both the cleaning step and the QA
  step so they cannot drift.

## Minimal skeleton

Config block (lives beside the rest of the workflow config):

```yaml
qa:
  unique_key: SUBJECT_ID
  required_complete: [stratum, psu]        # structural: present AND non-missing
  categoricals:
    stage: {allowed: [1, 2, 3, 4, 5]}      # structural: illegal code => bug
  exclusive_flags: [[on_drug_a, on_drug_b]]  # structural: must not co-occur
  ranges:                                   # distribution: flagged, not fatal
    age:    {min: 0,   max: 120}
    glucose:{min: 30,  max: 500}
  missing_sentinels: [-1, -7, -8, -9]       # coerce upstream; QA guards survivors
```

Report skeleton:

```markdown
# <table> — QA / sanity-check report

- Rows checked: N · Entities: M
- Structural flags: **0** · Distribution flags: **K**

## Flagged issues
### 🔴 Structural (ingest/derive bugs — build-fatal)
### 🟡 Distribution (domain review — not fatal)

## Per-variable distribution
| variable | n | % miss | min | median | p99 | max | outliers |
```

Script contract: read the table, run the checks, write the report, then
`sys.exit(...)` if any structural flag fired (unless an explicit `--no-strict` escape is
passed for inspection).

## When to use / when not

- **Use** when a pipeline produces a processed analysis table consumed by models or
  statistics — i.e. wherever a silent data defect would corrupt a result.
- A light project may start with structural checks only (key uniqueness, required columns,
  allowed codes) and add distribution checks as domain bounds become known.
- **Skip** for pure-visualization or throwaway exploratory scripts with no downstream
  consumer, and for raw-data ingestion where schema is still being discovered (decode
  first, then add the QA step over the decoded table).

## Non-rules

- Not validator-enforced upstream. `science validate` does not require a QA step; this is a
  project-side discipline the `computational-analysis` aspect encourages.
- One report per validated table is the norm; multi-table pipelines may emit one QA step
  per substrate rather than one mega-report.
- The two-severity split is the contract; the exact check list is per-project and grows
  from real bugs caught.

## See also

- [`../../aspects/computational-analysis/computational-analysis.md`](../../aspects/computational-analysis/computational-analysis.md)
  — `plan-pipeline` (QA Checkpoints) and `review-pipeline` (QA Coverage) sections this
  pattern realizes.
- [`validate.md`](validate.md) — `science validate` (project-structure validation; distinct
  from pipeline data-QA).
- [`README.md`](README.md) — directory scope and entry bar.

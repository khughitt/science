# Pipeline QA Checkpoint Convention

This doc describes a concrete, reusable shape for the data-QA step the
`computational-analysis` aspect already calls for conceptually (see `plan-pipeline` →
*QA Checkpoints* and `review-pipeline` → *QA Coverage*). Those sections say *what* to
check; this one says *how to build the check* so it runs every pipeline invocation and
fails loudly when integrity breaks.

It is a deliberately-promoted single-project pattern (health-cycles) with a clear
cross-project rationale: in two separate pipelines within that project the QA step caught
source-level bugs that every other check missed — a therapeutic-category code that was a silent superset of
another, and SAS XPORT special-missing values that survived as tiny denormal floats and
would have entered models as near-zero measurements. Any project whose pipeline produces a
processed analysis table feeding models or statistics should adopt it.

## The shape

A QA checkpoint is **one script + one workflow rule** that reads a processed table and
writes a markdown report — nothing more exotic:

- It is its own pipeline stage (e.g. a Snakemake rule), wired into the default target so
  it runs on every build, *after* the table it validates is produced. Note that a
  build-fatal exit interacts with output cleanup — see the script contract below.
- It reads the already-built table (`*.parquet` / `*.csv`), never the raw inputs — it
  validates the substrate analysis actually consumes.
- It writes a single `results/<workflow>/qa_report.md`: a header with row/entity counts,
  the flagged issues split by severity, and a per-variable distribution table. The report
  is a small text artifact — git-track it; it regenerates with the pipeline.

This end-table QA step **complements, does not replace**, the per-stage assertions and
inter-stage invariants `plan-pipeline` already calls for (row-count conservation, referential
integrity, cardinality between stages). A single script reading the processed end table
cannot see between-stage conservation; keep those checks at the transformations and use this
step to validate the substrate analysis finally consumes.

## Two severities

Every flag is one of two severities. This split is the load-bearing part of the pattern.

| Severity | Meaning | Failure mode |
| --- | --- | --- |
| **Structural** | A schema or integrity invariant is violated — the table is *wrong*, indicating an ingest/derive bug. | **Build-fatal.** The script exits non-zero (fail early), halting the pipeline. |
| **Distribution** | A value is *suspicious but possibly real* — an extreme assay value, a rare category, a heavy tail. | **Surfaced, not fatal.** Written to the report for analyst judgement; never auto-corrected. |

Structural checks encode things that must be true if the code is correct: unique primary
key, required columns present and complete, categorical values within an allowed set — or,
when that allowed set is a *shared data registry* the pipeline also consumes (e.g. a contrast or
code registry), the table's values validated as a subset of that registry so a single source of
truth governs both, cross-field invariants (e.g. two flags that must be mutually exclusive), and
guards against
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
    stage:    {allowed: [1, 2, 3, 4, 5]}                       # structural: illegal code => bug
    contrast: {allowed_from: "registries/contrasts.csv#name"}  # structural: subset of a shared registry
    # worked example (cancer-evolution t006): scale / cancer_type validated as a subset of a list
    # the pipeline itself also consumes — one registry governs both, and an out-of-set value is
    # build-fatal. This is the canonical realization of the allowed_from clause.
  exclusive_flags: [[on_drug_a, on_drug_b]]  # structural: must not co-occur
  ranges:                                   # distribution: flagged, not fatal
    age:    {min: 0,   max: 120}
    glucose: {min: 30, max: 500}
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
passed for local inspection — never wire `--no-strict` into the default target).

**Mind the failed-job output cleanup.** Most build tools delete a failed job's declared
outputs by default — Snakemake removes the rule's `output:` files on non-zero exit (recover
with `--keep-incomplete`). That collides with "write the report, then exit non-zero": the
report you most need is deleted on exactly the build-fatal path. Avoid it by *not* declaring
`qa_report.md` as the strict rule's output. Either write the report to a path outside that
rule's `output:` set, or split into two rules — one that always writes the report (its
output), and a downstream strict-gate rule that reads the report and fails the build. The
gate's failure never touches the report.

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
- **A side-output counts file does NOT satisfy the convention.** A transform script that writes
  a summary `*_qa.json` (or any counts/stats sidecar) as one of its own outputs looks like QA but
  is not: it has no structural/distribution split, is never build-fatal, has no config-driven
  thresholds, is not its own rule, and is not in the default target. A QA checkpoint is a
  **separate rule that re-reads the built table** and applies the two-severity split — not a
  byproduct of the transform that produced the table. *Worked counter-example (cancer-evolution
  t015):* `observed_switches_qa.json` / `simulated_events_qa.json` are unconditional summary
  side-outputs of the transform — they count, but they cannot fail a build and govern nothing, so
  they do not discharge axis-1 QA for that table.

## Reference implementation

The `science-qa` distribution (`science/qa/`, command `python -m science_qa run`) executes the
structural/distribution severity split above. It accepts a schema-driven datapackage resource with
`--datapackage ... --resource ...`. Datapackage mode compiles the resource's typed Table Schema into
the generic `tabular` program; optional `--config ...` run-knobs overlay operational choices such as
soft ranges, polarity, project-local checks, aspect parameters, and program choice.

The runner also formalizes the "analyst decides at model time" step for distribution flags: it
emits `qa_report.json` (an immutable flag ledger) and scaffolds an analyst-owned
`qa_dispositions.yaml`. Like the report, the disposition file **must not** be a strict rule's
declared output — it holds hand-entered data a failed-job cleanup would delete. Write it outside the
strict gate's output set and reference it as a manifest resource (`qa_dispositions`).

### Composable aspects & programs (baseline library + project extensions)

`science_qa` composes checks as **aspects** (`general`, `tabular`, `numeric-column`,
`gene-expression-qc-table`, `scrna-qc-table`, `project-local`) into a named **program**. A program is
an ordered baseline library of type-appropriate checks bound to a substrate, currently a pandas
table. The shipped programs are:

| Program | Use |
| --- | --- |
| `tabular` | Generic table QA: general, tabular, and numeric-column aspects. This is the default for schema-driven datapackage QA. |
| `scrna-qc-table` | Post-QC single-cell table QA: the generic table aspects plus gene-expression and scRNA gates. |

Aspects are flat named check sets, and programs compose them; there is no inherited pack layer.
`project-local` is the append-only extension point for project-specific bug-driven checks.
Parameterized families such as `ranges`, `categoricals`, `unique_key`, `exclusive_flags`,
`polarity`, `missing_sentinels`, and schema-derived `bounds` expand from config or typed resource
schemas. Required checks run unconditionally for the program, using documented defaults or failing
early when the program/substrate contract is invalid.

Breadth is reported as a coverage block in `qa_report.json`: each invocation records `ran`, `empty`,
`blocked`, or `not-applicable`, and declared-but-unconfigured families are listed separately. Coverage
is advisory; structural flags remain the build-fatal gate.

Typed resource schemas are the preferred source of truth for ordinary datapackage QA. Native
Frictionless declarations map to structural checks: field types, required fields, uniqueness,
primary keys, unique keys, hard bounds, enum domains, missing sentinels, and single-column
foreign-key categoricals. The Science `qa:` extension is small and distribution-oriented:
field-level `low_variance` and `zero_fraction`, plus table-level `exclusive_flags`. Composite
foreign keys are rejected rather than weakened to per-column checks. `science datasets infer-schema`
can scaffold only the safe `fields[].name` and `fields[].type` portion from a produced table; keys,
constraints, foreign keys, and `qa:` declarations remain authored decisions.

## See also

- [`../process/pipeline-audit-and-refactor.md`](../process/pipeline-audit-and-refactor.md) — the
  three-axis pipeline audit/refactor playbook; this convention is its axis-1 (data-QA) target.
- [`../user-guide/project-layout.md`](../user-guide/project-layout.md) — current profile/aspect
  boundary for research, computation, and software project roots.
- [`../../aspects/computational-analysis/computational-analysis.md`](../../aspects/computational-analysis/computational-analysis.md)
  — `plan-pipeline` (QA Checkpoints) and `review-pipeline` (QA Coverage) sections this
  pattern realizes.
- [`validate.md`](validate.md) — `science validate` (project-structure validation; distinct
  from pipeline data-QA).
- [`README.md`](README.md) — directory scope and entry bar.

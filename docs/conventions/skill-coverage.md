# Skill coverage

`science skills coverage` scans the registered project portfolio and reports, per
enrolled project, where analyses touch a data-product term that no skill covers
(`uncovered`), where a covering skill exists but the plan did not load it
(`covered-not-loaded`), and where analysis touches a dataset tagged against no term
(`unmapped`). It emits evidence-backed skill candidates for uncovered terms.

## Enrolling a project

Enrollment is a closed declaration in `science.yaml`:

```yaml
skill_coverage:
  domains:
    molecular-measurement: enrolled   # or: out-of-domain
```

- The only domain in v1 is `molecular-measurement`. An unknown domain key is a hard
  config error.
- Absence of the block, or of a domain key, means **undeclared** for that domain — it
  is never inferred as `out-of-domain`, which a project must author explicitly.
- `molecular-measurement: enrolled` **requires** `entity_schema_version: 3` (coverage
  reads the generation-3 capability shape); enrolling without it is a config error.

## Running the scan

```bash
science skills coverage                 # portfolio scan -> coverage-report JSON on stdout
science skills coverage --output report.json
science skills coverage --project mm30  # restrict to one registered project
```

A registered path that is missing or has no `science.yaml` is skipped and listed under
`skipped_projects`; a path that exists with invalid config aborts the scan (nonzero
exit, no partial report). Coverage findings are not failures — a scan that surfaces
`uncovered` occurrences still exits 0.

## The report

`coverage-report` is a JSON object: `scope`, `coverage_occurrences[]` (a discriminated
union keyed by `state`), `skill_reference_diagnostics[]`,
`dataset_reference_diagnostics[]`, `candidates[]`, and `skipped_projects[]`. See the
design doc `docs/plans/2026-07-25-skill-coverage-command-design.md` for the field-level
schema.

## Curating gaps into feedback

`science skills curate` turns the scan's `uncovered` candidates into tracked
`science feedback` entries. It is report-first: with no flag it prints a filing
plan and writes nothing; `--apply` files the plan.

```bash
science skills curate                        # print the plan (report-only)
science skills curate --apply                # file every new/recur row
science skills curate --apply --term <term>  # file only the named term(s)
science skills curate --project mm30         # scope the scan to one project
science skills curate --format json --output plan.json   # report-only; not with --apply
```

Each accepted gap becomes a feedback entry with `target: skill-coverage:<term>`,
`category: gap`, `concern: tooling`, `project: science`. A term already carrying
an **open**, matching `concern: tooling` entry records a recurrence instead of a
duplicate; a term whose matching `concern: tooling` entries are all resolved
(`wontfix`/`addressed`/`deferred`) is reported but not re-filed. More than one
matching open `concern: tooling` entry for a term is a hard error — merge them
first. Entries under other concerns are ignored for recurrence, skip, and
conflict decisions. Only `uncovered` gaps are filed; `covered-not-loaded` and
`unmapped` appear in the report's context counts as project-side follow-ups.

`--output` is **report-only** — it cannot be combined with `--apply`. This keeps a
committed feedback write from ever being followed by a failing report-write (which a
retry would double-record); to capture an apply run, redirect its stdout instead
(`science skills curate --apply --format json > applied.json`).

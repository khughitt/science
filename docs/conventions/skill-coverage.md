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

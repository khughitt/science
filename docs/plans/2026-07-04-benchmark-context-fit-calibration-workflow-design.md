# Benchmark Context-Fit Calibration Workflow Design

## Context

The context-fit actionability slice added `context_fit`,
`context_fit_reasons`, and `context_fit_warnings` to benchmark gap/test rows,
plus `--context-fit` filters on the benchmark reports. The first post-merge
smoke report (`docs/reports/benchmark-context-fit-calibration-2026-07-04.md`)
showed useful separation:

- multiple myeloma and cBioPortal retain plausible `direct-fit` rows;
- natural systems is no longer dominated by direct-fit biology rows;
- full triage output remains dominated by `generic-fallback` rows in several
  projects.

The next step is calibration, not another matcher change. We need a repeatable
read-only workflow that records what the existing commands say across active
projects, highlights suspicious rows, and points to the next benchmark action
slice.

## Decision

Use a durable audit/report workflow first. Do not add a new CLI command in this
slice.

The workflow reuses existing commands:

- `science benchmark gap-calibration`
- `science benchmark gaps --context-fit ...`
- `science benchmark test-triage`
- `science benchmark tests --context-fit ...`

It writes a dated report under `docs/reports/` and may keep raw JSON snapshots
in the session scratchpad during execution. Only the summarized report is
committed unless a raw snapshot exposes a specific regression that needs review
context.

If the same report shape is useful after two or more calibration passes, a later
slice can promote it into a maintained command.

## Goals

- Make context-fit calibration repeatable across the active benchmark projects.
- Distinguish three outcomes:
  - classifier tuning needed;
  - benchmark metadata/staging cleanup needed;
  - report workflow is stable enough to promote into a command.
- Surface generic fallback concentration without hiding raw fallback rows.
- Identify suspicious direct/adjacent fits, especially rows whose positive
  score depends on broad or cross-context cues.
- Keep the workflow local-first and deterministic.

## Non-Goals

- Do not change matching, scoring, `context_fit` classification, or metadata.
- Do not add a new command yet.
- Do not call network services, embeddings, model APIs, or external ontologies.
- Do not write review files into project roots.
- Do not commit generated raw JSON snapshots by default.

## Project Set

The default calibration set is the current active benchmark set:

- `~/d/cancer/cancer-types/multiple-myeloma`
- `~/d/health/processes/post-acute-infection`
- `~/d/natural-systems`
- `~/d/cancer/data-sources/cbioportal`

All commands run with `--commons` so shared benchmark entities are included.
The report records the exact project list used.

## Context-Fit Classes

`context_fit` is a six-value enum (`CONTEXT_FITS` in
`benchmark_opportunities.py`). Every table, count, and reconciliation check in
this workflow must carry all six columns, in this order:

`direct-fit`, `adjacent-fit`, `method-fit`, `blocked-fit`, `generic-fallback`,
`out-of-context`.

`method-fit` and `out-of-context` are easy to omit but material: in the seed
report `method-fit` is the single largest concrete category in multiple-myeloma
(77 rows) and appears in every project, and `out-of-context` is non-empty in
multiple-myeloma. Dropping either class would also break the count-reconciliation
check in Testing and Verification, because per-class totals would no longer sum
to the row counts they summarize.

## Data Capture

The workflow captures four surfaces. The prior smoke report
(`docs/reports/benchmark-context-fit-calibration-2026-07-04.md`) exercised only
surfaces 3 and 4; surfaces 1 and 2 are new to this contract, so the first pass
will not be directly comparable to the seed report on the gap surfaces. That is
expected — the seed report establishes the test/triage baseline, and this pass
extends it.

1. `benchmark gap-calibration`

   Purpose: aggregate gap candidate counts, fallback ratios, fallback
   concentration, suggested facets, matched facets, and top fallback benchmark
   rows across projects.

   Because every command runs with `--commons`, commons-shared benchmark rows
   appear in all four projects. When aggregating "top fallback benchmarks across
   projects," mark whether a dominant benchmark id is commons-shared or
   project-local. A commons-shared id appearing in all four projects is expected
   and is not by itself evidence of a cross-cutting problem.

2. `benchmark gaps --context-fit direct-fit` and selected complementary filters

   Purpose: inspect whether high-actionability gap candidates are plausible and
   whether filtered rows keep consistent `candidate_mode`,
   `candidate_context_fit_counts`, and candidate evidence.

3. `benchmark tests --exclude-fallback --state concrete`

   Purpose: measure concrete non-fallback test rows by context-fit class. This
   is the closest view to "what could a project run or stage next?"

4. `benchmark test-triage`

   Purpose: measure full actionability distribution, including fallback
   diagnostics, blocked task support, readiness labels, and context-fit counts
   by triage bucket.

Raw command output should be generated as JSON during the pass so the report is
computed from machine-readable data rather than hand-filled cells.

## Report Contract

Write a dated Markdown report:

`docs/reports/benchmark-context-fit-calibration-pass-N-YYYY-MM-DD.md`

The `pass-N` segment avoids colliding with the seed report
(`benchmark-context-fit-calibration-2026-07-04.md`), which is not a pass under
this contract and must not be overwritten. The first pass under this contract is
`pass-1`.

The report contains:

- command block with exact commands or script invocation;
- project list;
- aggregate gap-calibration summary;
- per-project concrete non-fallback test counts across all six `context_fit`
  classes;
- per-project full triage counts across all six `context_fit` classes;
- per-project fallback share and fallback concentration warning;
- suspicious rows (each labeled computed vs reviewer-judged):
  - computed: rows with non-empty `context_fit_warnings`;
  - computed: rows where `blocked-fit` dominates a high-priority benchmark;
  - reviewer-judged: rows whose benchmark/project pairing reads as cross-context
    (there is no cross-context field; this is a human read of the warnings and
    benchmark id, not a machine verdict);
- top generic fallback benchmarks and reasons;
- next-action recommendation.

The recommendation must choose one primary next slice:

- **metadata/staging cleanup** when direct/adjacent rows look plausible but are
  blocked by access, task support, or staging;
- **classifier tuning** when direct/adjacent rows look noisy or cross-context;
- **workflow promotion** when repeated reports show stable, useful fields and
  the report is being run often enough to justify a command.

## Decision Rules

The report does not need a hard pass/fail result, but it should apply these
rules consistently. "Dominant" means a class is the plurality of a project's
rows or exceeds half the non-fallback rows; the pass should record the actual
counts next to each verdict so two passes are comparable rather than resting on
an unstated threshold.

- If `natural-systems` has any `direct-fit` biology/cancer benchmark rows,
  prefer classifier tuning. (The seed report has zero; a nonzero count is a
  regression signal, not a threshold judgment.)
- If `generic-fallback` rows dominate triage while direct/concrete rows are
  plausible, prefer presentation/report tuning or metadata cleanup over matcher
  changes.
- If one or two benchmark ids dominate fallback rows across projects, prefer
  task-support annotation or dataset-class/readiness cleanup for those records —
  but first confirm the id is project-local, not commons-shared (a shared id in
  all projects is expected, not a dominance signal).
- If multiple `direct-fit` rows carry cross-context warnings, prefer
  classifier tuning before metadata edits.
- If `blocked-fit` rows are concentrated around known task-support blockers,
  prefer explicit task-support metadata over staging work.
- If `method-fit` dominates the concrete non-fallback rows (as in the
  multiple-myeloma seed), treat that as expected actionable output, not a
  defect: prefer no matcher change and confirm those rows point at runnable
  method benchmarks. Only escalate to classifier tuning if `method-fit` rows
  carry cross-context warnings.
- `out-of-context` rows are the intended reject bucket. A small nonzero count is
  healthy; investigate only if it grows relative to the seed or captures rows
  that look plausibly in-context.

## Error Handling

- Command failures fail the calibration pass. Do not silently skip projects.
  (Every command runs with `--commons`, so any hard command failure already
  fails the pass — there is no separate "commons-backed" failure mode.)
- Non-fatal commons notices (e.g. a warning that a commons source was skipped)
  are captured verbatim in the report, not treated as failures.
- Empty result sets are valid only when the command exits successfully; the
  report should state that the project had zero rows for that surface.
- Raw JSON parse failures fail the pass. The report must not be hand-filled from
  partial text output.

## Testing and Verification

Implementation should be a plan-driven audit slice. Verification should include:

- run all selected commands successfully on the four active projects;
- verify the report tables are generated from JSON payloads;
- verify `context_fit_counts` totals match the row counts they summarize,
  summing across all six classes (a four-class table will fail this check);
- verify at least one table distinguishes concrete non-fallback rows from full
  triage rows;
- commit only the design/plan/report artifacts unless a code bug is found and
  fixed deliberately.

## Alternatives Considered

### Add `science benchmark context-fit-calibration`

Rejected for now. The report shape is still being calibrated. Adding a command
would freeze an interface before the fields and decisions have been exercised
over multiple passes.

### Directly edit benchmark metadata from current output

Rejected. Current output can identify likely next actions, but it cannot yet
separate classifier false positives from true metadata gaps reliably enough to
justify immediate metadata edits.

### Keep using ad hoc one-off scripts only

Rejected. The first one-off report was useful, but without a documented report
contract each pass risks measuring a different surface. A lightweight workflow
keeps the evidence comparable without committing to a new CLI.

## Follow-Up

After one complete calibration pass, decide whether the next benchmark slice is:

- focused metadata/staging cleanup for specific benchmark records;
- context-fit classifier tuning;
- or a small command promotion for this report.

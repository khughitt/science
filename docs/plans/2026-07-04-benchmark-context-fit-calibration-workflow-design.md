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
under `/tmp` during execution. Only the summarized report is committed unless a
raw snapshot exposes a specific regression that needs review context.

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

## Data Capture

The workflow captures four surfaces.

1. `benchmark gap-calibration`

   Purpose: aggregate gap candidate counts, fallback ratios, fallback
   concentration, suggested facets, matched facets, and top fallback benchmark
   rows across projects.

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

`docs/reports/benchmark-context-fit-calibration-YYYY-MM-DD.md`

The report contains:

- command block with exact commands or script invocation;
- project list;
- aggregate gap-calibration summary;
- per-project concrete non-fallback test counts by `context_fit`;
- per-project full triage counts by `context_fit`;
- per-project fallback share and fallback concentration warning;
- suspicious direct/adjacent rows:
  - rows with non-empty `context_fit_warnings`;
  - rows whose benchmark/project pairing appears cross-context;
  - rows where `blocked-fit` dominates a high-priority benchmark;
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
rules consistently:

- If `natural-systems` has many `direct-fit` biology/cancer benchmark rows,
  prefer classifier tuning.
- If `generic-fallback` rows dominate triage while direct/concrete rows are
  plausible, prefer presentation/report tuning or metadata cleanup over matcher
  changes.
- If one or two benchmark ids dominate fallback rows across projects, prefer
  task-support annotation or dataset-class/readiness cleanup for those records.
- If multiple `direct-fit` rows carry cross-context warnings, prefer
  classifier tuning before metadata edits.
- If `blocked-fit` rows are concentrated around known task-support blockers,
  prefer explicit task-support metadata over staging work.

## Error Handling

- Command failures fail the calibration pass. Do not silently skip projects.
- Commons notices are captured in the report rather than treated as fatal unless
  all commons-backed commands fail.
- Empty result sets are valid only when the command exits successfully; the
  report should state that the project had zero rows for that surface.
- Raw JSON parse failures fail the pass. The report must not be hand-filled from
  partial text output.

## Testing and Verification

Implementation should be a plan-driven audit slice. Verification should include:

- run all selected commands successfully on the four active projects;
- verify the report tables are generated from JSON payloads;
- verify `context_fit_counts` totals match the row counts they summarize;
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

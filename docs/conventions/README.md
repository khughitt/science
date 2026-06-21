# Conventions

This directory holds cross-cutting convention references — short, prescriptive docs describing recurring shapes that aren't a fit for `plans/`, `specs/`, or `process/`.

Bar for entries: each doc should describe a pattern observed in two or more downstream projects (or a deliberately-promoted single-project pattern with a clear cross-project rationale), be self-contained, and be linkable from the relevant chapter under `docs/user-guide/`.

## Index

- [`code-task-backlinks.md`](code-task-backlinks.md) — sanctioned patterns for linking code/notebooks back to tasks, questions, hypotheses, and interpretations.
- [`pipeline-qa-checkpoints.md`](pipeline-qa-checkpoints.md) — concrete shape for a pipeline data-QA step (structural vs distribution severity, config-driven bounds including shared registry/enum validation, markdown report, fail-early on structural).
- [`reproducible-manifest-dates.md`](reproducible-manifest-dates.md) — workflow-run / derived-dataset manifest `created`/`updated` must derive from run identity (run-slug date / `--produced-at` / commit time), not regeneration wall-clock, so manifests stay date-honest and byte-reproducible.
- [`validate.md`](validate.md) — `science validate` CLI reference, including Python sidecar and output contracts.

New entries (datapackage extension, status-enum schema, multi-axis profile axis labels) will be appended as their design passes complete.

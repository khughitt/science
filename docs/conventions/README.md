# Conventions

This directory holds cross-cutting convention references — short, prescriptive docs describing recurring shapes that aren't a fit for `plans/`, `specs/`, or `process/`.

Bar for entries: each doc should describe a pattern observed in two or more downstream projects (or a deliberately-promoted single-project pattern with a clear cross-project rationale), be self-contained, and be linkable from the relevant chapter under `docs/user-guide/`.

## Index

- [`code-task-backlinks.md`](code-task-backlinks.md) — sanctioned patterns for linking code/notebooks back to tasks, questions, hypotheses, and interpretations.
- [`pipeline-qa-checkpoints.md`](pipeline-qa-checkpoints.md) — concrete shape for a pipeline data-QA step (structural vs distribution severity, config-driven bounds including shared registry/enum validation, markdown report, fail-early on structural).
- [`reproducible-manifest-dates.md`](reproducible-manifest-dates.md) — workflow-run / derived-dataset manifest `created`/`updated` must derive from run identity (run-slug date / `--produced-at` / commit time), not regeneration wall-clock, so manifests stay date-honest and byte-reproducible.
- [`validate.md`](validate.md) — `science validate` CLI reference, including Python sidecar and output contracts.

## Deferred Convention Backlog

The downstream conventions audit still contains design candidates that are not
stable conventions yet. Keep them in the audit synthesis until their replacement
designs land:

| Candidate | Current home |
|---|---|
| Multi-axis profile / archetype labels | [`../audits/downstream-project-conventions/synthesis.md`](../audits/downstream-project-conventions/synthesis.md) §11.2 |
| Per-type status enums and structured qualifiers | [`../audits/downstream-project-conventions/synthesis.md`](../audits/downstream-project-conventions/synthesis.md) §6.1 and §11 |
| Datapackage project-extension block and descriptor sidecar schema | [`../audits/downstream-project-conventions/synthesis.md`](../audits/downstream-project-conventions/synthesis.md) §7 |

Project-local entity-kind extension is no longer just backlog: the current
loader supports `knowledge/sources/<profile>/manifest.yaml` with
`strictness: typed-extension`, documented in
[`../user-guide/entities.md`](../user-guide/entities.md).

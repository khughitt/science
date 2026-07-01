# Documentation Coherence Review

## Scope

Reviewed:

- `docs/user-guide/`
- `docs/conventions/`
- `docs/process/`
- recent durable docs under `meta/core/`

## What Is Working

The user guide now has a coherent reading path:

1. Introduction and conceptual model.
2. Project layout and entities.
3. Epistemic model and evidence.
4. Graph/derived state, validation, agent workflows, feedback, benchmarking,
   packaging, and cross-project work.

That structure is good. The guide is no longer just a set of migrated plan
fragments; it reads like a manual for the framework.

The conventions directory also has a clear stated bar: cross-cutting patterns
observed in multiple projects or deliberately promoted from one project. That is
the right rule.

## Gaps

### Missing CLI/workflow Reference

`docs/user-guide/agent-workflows.md` is useful, but it is an intent-to-agent map,
not a CLI reference. It does not answer:

- Which command families are canonical for new work?
- Which commands are migration-only or legacy?
- Which commands write source files, generated state, reports, or external
  registries?
- Which commands are safe read-only diagnostics?
- Which commands are report-then-apply?

Given the current 46 top-level commands, this should be a first-class user-guide
chapter or a major section of `agent-workflows.md`.

### Convention Docs Sometimes Carry Guide Material

Some convention docs are appropriately short and prescriptive, for example
`docs/conventions/data-boundary.md` and `docs/conventions/reproducible-manifest-dates.md`.

Other docs, especially `docs/conventions/annotation-tokens.md`, now carry
workflow-level guidance for full annotation phases. That material is useful, but
it may belong partly in the user guide because it explains how users move through
annotation workflows, not only what a stable convention is.

### Process Docs Need Stronger Placement Rules

`docs/process/adding-a-domain.md`, `docs/process/entity-creation-cookbook.md`,
and `docs/process/pipeline-audit-and-refactor.md` are practical and valuable.
The boundary between process docs and user-guide chapters should be explicit:

- User guide: normal operation and concepts.
- Conventions: stable cross-project rules.
- Process: repeatable procedures for maintainers or project-specific audits.

This boundary should be stated in `docs/user-guide/index.md` or
`docs/conventions/README.md`.

### Legacy Guidance Is Scattered

The docs correctly mention legacy topics, legacy `article:` refs, legacy
`data-package` surfaces, legacy entity layouts, legacy task blockers, and legacy
annotation tokens. The issue is not that these references exist. The issue is
that a new agent has to learn the current surface by reading many local caveats.

A short "Legacy and migration surfaces" section in the command map would reduce
the chance that old commands are selected for new work.

## Curation Opportunities

1. Add `docs/user-guide/cli-and-workflows.md` with command taxonomy, command
   family statuses, and examples of the core loops.
2. Update `docs/user-guide/index.md` to include that chapter near
   `agent-workflows.md`.
3. Keep `agent-workflows.md` focused on Claude/Codex intent mapping, and link to
   the new CLI taxonomy for command semantics.
4. Split workflow-level annotation prose out of `docs/conventions/annotation-tokens.md`
   only if the resulting user-guide chapter has a clear home. Do not split it
   just to make the convention file shorter.
5. Add a one-paragraph placement rule to `docs/conventions/README.md`: concepts
   go in the guide, stable rules go in conventions, repeatable maintenance
   recipes go in process.

## Durable Documentation Targets

| Target | Proposed role |
|---|---|
| `docs/user-guide/cli-and-workflows.md` | Canonical command taxonomy and workflow map. |
| `docs/user-guide/agent-workflows.md` | Agent intent mapping; link out to CLI taxonomy. |
| `docs/conventions/README.md` | Directory scope and placement rule. |
| `docs/conventions/annotation-tokens.md` | Keep token vocabulary and stable annotation conventions; consider moving long workflow phase guidance later. |
| `docs/process/` | Maintenance and audit recipes, not everyday user reference. |

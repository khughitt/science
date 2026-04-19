# Entity-Level Aspects

**Date:** 2026-04-19
**Status:** Draft

## Motivation

The Science framework's `science.yaml` already defines `aspects:` as composable behavioral mixins at the project level (`causal-modeling`, `hypothesis-testing`, `computational-analysis`, `software-development`). Entities inside a project — tasks, questions, interpretations, hypotheses — currently carry no aspect metadata of their own, despite the fact that individual entities often have clearer aspect alignment than the project as a whole.

Two observed problems motivate entity-level aspects:

1. **Research synthesis pulls in software-oriented entities it shouldn't.** `/science:big-picture` can't distinguish research work from software/infrastructure work in projects that mix both. Software-focused tasks (e.g., mm30's pipeline-QA tasks), questions (e.g., natural-systems `q14-data-quality-lens-design`), and interpretations surface as part of research synthesis or as orphans that shouldn't be there. The synthesizer sees an undifferentiated pool.
2. **Two overlapping systems express the same distinction.** Tasks already carry a `type: research | dev` field. That field captures exactly the research/software split, but in a local and idiosyncratic vocabulary that doesn't compose with the richer project-level aspects. Keeping both invites drift; dropping `type` in favor of a unified `aspects:` field resolves the redundancy.

## Goal

Introduce an `aspects:` field on all primary entity types (tasks, questions, interpretations, hypotheses). The field uses the same vocabulary as `science.yaml`'s `aspects:`, inherits from the project when unset, and acts as an override when explicit. Downstream commands — starting with `/science:big-picture` — filter on the resolved aspects so research synthesis excludes software-oriented entities (and vice versa).

## Design Principles

- **One vocabulary, one resolution rule**. Entity-level and project-level aspects must use the same registry and resolve through one shared helper, not ad hoc command-specific logic.
- **Inheritance is the default; explicit fields are only for exceptions**. Most entities should continue to inherit from `science.yaml`. Explicit entity `aspects:` exists to mark the minority case that differs from the project default.
- **No silent fallback from invalid explicit data**. If an entity explicitly declares invalid aspects, aspect-aware commands fail with a clear error; `science-tool health` also surfaces the issue proactively.
- **Filtering and association are separate concerns**. Aspect filtering decides whether an entity participates in a synthesis view. Resolver/orphan logic continues to answer structural questions inside that filtered set.

## Scope

### In scope (v1)

- Add `aspects:` to entity schemas and templates for: tasks, questions, interpretations, hypotheses.
- Vocabulary: identical to project-level aspects (the set defined in `science.yaml`'s `aspects:`).
- Inheritance semantics: entity's resolved aspects = `entity.aspects` if set, else `project.aspects`.
- Introduce a shared aspect utility in `science-tool` / `science-model` for validation, resolution, and filtering predicates. Commands consume that utility rather than reimplementing aspect logic.
- Migration: one-shot mandatory migration for tasks carrying legacy `type: research | dev`. Non-task entities inherit by default; no bulk-rewrite required.
- `science-tool aspects migrate` CLI that performs task migration with dry-run-by-default semantics.
- `/science:big-picture` bundle assembly and resolver consume entity aspects; research synthesis excludes entities whose resolved aspects are `[software-development]` only.
- `science-tool tasks add` drops `--type`, adds `--aspects`.
- `science-tool health` flags tasks still carrying the legacy `type:` field as "migration pending".

### Out of scope (v1)

- Propagating `aspects:` filtering beyond tasks/questions/interpretations/hypotheses into other entity types (concepts, topics, papers, discussions). Extend only when evidence of real misclassification accumulates.
- Optional "bulk-assign" of explicit aspects to existing non-task entities. Inheritance handles this class; no opt-in bulk-rewrite needed. Users refine individual entities when they find miscategorizations.
- Entity-type-specific default aspects (e.g., "hypotheses are always research"). Rejected during brainstorm as hidden magic. Keep the rule explicit: project-level `aspects:` is the sole inheritance source.
- Propagating aspects into the knowledge graph (RDF) layer. The graph's existing typing is sufficient for v1; adding aspect triples can come later if a query consumer needs it.
- Retroactive `aspects:` values on legacy `doc/reports/` or `core/` documents. Those documents are synthesis artifacts, not entities; filtering doesn't apply.

## Data Model

### Field on every supported entity

Every entity (task, question, interpretation, hypothesis) gains an optional `aspects:` field:

```yaml
---
id: "question:q14-data-quality-lens-design"
type: "question"
aspects: ["software-development"]   # explicit override
---
```

Semantics:

- **Absent** (field not declared): the entity inherits `project.aspects` from `science.yaml`.
- **Present and non-empty list**: full override — the entity's resolved aspects are exactly this list, regardless of project aspects.
- **Present and empty list (`aspects: []`)**: invalid. Reject at parse/validation time with a clear message. "No aspects" is not a meaningful steady state for primary entities because it silently drops them from every aspect-aware command and is almost always an editing mistake.

### Vocabulary

Same as `science.yaml`'s `aspects:` vocabulary, validated against the same registry:

- `causal-modeling`
- `hypothesis-testing`
- `computational-analysis`
- `software-development`

Entity aspects are validated against `project.aspects`: an entity may not declare an aspect the project hasn't enabled. This prevents typos and aspect drift. `science-tool health` reports violations.

Additional normalization rules:

- Aspect lists are treated as sets for semantics: duplicates are invalid and should be rejected.
- Order is canonicalized to project-vocabulary order when written by tools. This keeps diffs stable.
- Hand-edited files may use any order, but resolution utilities normalize before comparison/output.

### Resolved-aspects function

For any entity `E` in project `P`:

```
resolve_aspects(E, P) =
  E.aspects       if "aspects" in E
  P.aspects       otherwise
```

This one-line rule governs every downstream consumer.

Implementation note: commands should call a shared helper such as `resolve_entity_aspects(entity_aspects, project_aspects)` rather than reproducing this inline.

### Validation behavior

Validation must be deterministic:

- **Tool-authored writes** (`tasks add`, `aspects migrate`, future create/edit commands): hard error if an explicit aspect is not in `project.aspects`, if the list is empty, or if duplicates are present.
- **File parsing for aspect-aware commands** (`big-picture`, `tasks list --aspect`, future aspect-aware surfaces): hard error on invalid explicit aspect metadata. Failing early is preferable to silently producing a misleading synthesis.
- **`science-tool health`**: reports the same invalidities as structured findings so users can detect and fix them before hitting a command failure.

This resolves the ambiguity between warning-vs-error: health is the early warning surface; commands that depend on aspect semantics do not continue past invalid explicit data.

## Filter Semantics

Define one shared predicate:

```
matches_aspect_filter(E, P, filter_set) =
  resolve_aspects(E, P) ∩ filter_set is non-empty
```

Commands choose `filter_set`; they do not invent their own resolution semantics.

For `/science:big-picture` specifically:

- **"Research synthesis"** (the default mode for research-capable projects): include entity `E` iff `resolve_aspects(E, P) ∩ (P.aspects \ {software-development})` is non-empty.
  - In plain language: include the entity if any of its resolved aspects is something other than `software-development`.
  - Entities whose resolved aspects are exactly `[software-development]` are excluded from research-oriented bundles and emergent-threads analysis.
- **"Software synthesis"** (future, out of scope for this spec): symmetric — include entities whose resolved aspects intersect `{software-development}`. Deferred until there's demand for software-oriented big-picture runs.

Project-level precondition:

- If `project.aspects \ {software-development}` is empty, research synthesis is undefined for that project. `science-tool big-picture` should fail fast with a message explaining that v1 only supports research synthesis for projects with at least one non-software aspect. This is clearer than producing an empty or misleading report.

For `science-tool tasks list`:

- New `--aspect <name>` flag (repeatable): include only tasks whose resolved aspects intersect the given set.
- Default behavior (no `--aspect`): include all tasks (no filtering). Preserves current UX for listing.

For `science-tool health`:

- New check: flag tasks whose markdown entry still carries the legacy `type:` field (research or dev). Category: `legacy_task_type_field`. Severity: warning. Remediation hint: "Run `science-tool aspects migrate` to convert."
- New check: flag explicit entity `aspects:` values that are empty, contain duplicates, or are not a subset of `project.aspects`. Category: `invalid_entity_aspects`. Severity: error. Remediation hint names the file/entity and the invalid values.
- Existing checks unaffected.

## Migration

### Task migration (mandatory, one-shot)

Implemented as `science-tool aspects migrate`:

```
science-tool aspects migrate [--apply] [--project-root <path>]
```

Behavior:

1. Walk `tasks/active.md` and `tasks/done/*.md`. Parse each `## [tNNN]` heading and its inline `- type: research | dev` field.
2. For each task:
   - `type: dev` → add `- aspects: [software-development]`, remove the `- type:` line.
   - `type: research` → add `- aspects: <project-research-aspects>`, remove the `- type:` line.
     - `<project-research-aspects>` = `project.aspects \ {software-development}` as a YAML list. If that set is empty (project has only `software-development` as an aspect, which would be unusual), fall back to the full `project.aspects`.
     - This is intentionally coarse. Legacy `type: research` never distinguished among the non-software aspects, so migration preserves the old "research-scoped" meaning rather than inventing finer-grained specificity.
3. Without `--apply`: print a unified diff of proposed changes. Exit code 0.
4. With `--apply`: write the changes in place. Preserve all other formatting (whitespace, surrounding prose). Exit code 0 on success.

Idempotency: a task already carrying `aspects:` and no `type:` is skipped. Re-running migration is safe.

Failure behavior:

- If the project has no `science.yaml` `aspects:` field, migration fails with a clear error; there is no sound default vocabulary to infer from.
- If a task already contains both `type:` and `aspects:`, migration does not rewrite that task automatically. It reports the task as a conflict for manual cleanup, because the user's explicit `aspects:` may intentionally diverge from the legacy `type:`.

### Non-task entity migration

No bulk rewrite. Inheritance handles the common case automatically. Users introduce explicit `aspects:` only when they want to override — typically for software-oriented questions or interpretations in an otherwise research-focused project.

### Transitional state

During the window between `/science:big-picture` gaining aspect-awareness and a project running migration:

- Tasks still carrying `type: dev` will incorrectly inherit research aspects and appear in research synthesis.
- `science-tool health` flags the unmigrated state (see Filter Semantics above).
- Users run `science-tool aspects migrate --apply` once; project is correct thereafter.

The spec does **not** auto-run migration on first big-picture invocation. That would be too surprising given the destructive nature of rewriting task files. Migration is always user-initiated.

## Template Updates

### File-per-entity types (hypothesis, question, interpretation)

These entities have standalone markdown files with YAML frontmatter, one file per entity. Each template gains a commented, optional `aspects:` slot:

```yaml
# templates/question.md
---
id: "question:<slug>"
type: "question"
# aspects: ["hypothesis-testing"]  # optional override; omitted entities inherit project aspects
...
---
```

`templates/hypothesis.md` and `templates/interpretation.md` follow the same pattern.

The comment explicitly names the default behavior (inheritance) so template readers aren't surprised when an omitted field works.

### Tasks (inline in aggregated files)

Tasks are not individual markdown files; they are `## [tNNN]`-headed entries inside `tasks/active.md` and `tasks/done/YYYY-MM.md`, each followed by inline markdown-style fields:

```markdown
## [t082] PHF19 residualization
- priority: P2
- status: active
- aspects: [hypothesis-testing, computational-analysis]
- related: [hypothesis:h1-epigenetic-commitment, question:epigenetic-ratcheting-in-mm]
- created: 2026-04-08
```

No `templates/task.md` file exists or is introduced by this spec; task creation happens through `science-tool tasks add`, which writes the inline form. That CLI is updated as described below.

Post-migration, new tasks either declare explicit `- aspects: [...]` (when user passes `--aspects`) or omit the line (inheriting from project aspects). The old `- type: research | dev` line no longer appears.

## CLI Updates

### `science-tool tasks add`

- Remove `--type` flag.
- Add `--aspects <name>` (repeatable). Validated against `project.aspects`.
- Repeated flags are deduplicated and stored in canonical vocabulary order.
- If the user supplies neither, the task is stored without an `aspects:` field (inherits from project). No interactive prompt required; the default is correct for the most common case (research tasks in a research-focused project).

### `science-tool tasks list`

- Add `--aspect <name>` (repeatable) filter as described in Filter Semantics.

### `science-tool aspects migrate`

- New subcommand, described in Migration above.
- Lives in a new `science_tool.aspects` module alongside the other migration helpers (`science_tool.graph.migrate`, etc.).

### `science-tool big-picture resolve-questions`

- Output schema gains a `resolved_aspects` field per question:

```json
{
  "question:q01": {
    "hypotheses": [...],
    "primary_hypothesis": "...",
    "resolved_aspects": ["hypothesis-testing", "computational-analysis"]
  }
}
```

- The resolver reads `entity.aspects` if present, else `project.aspects`, and returns the resolved list. Downstream consumers (bundle assembly in `commands/big-picture.md`) no longer need to reproduce the resolution rule.
- `resolve-questions` remains a structural association tool, not a filter. It returns hypothesis matches plus `resolved_aspects` for every question. Whether a matched or unmatched question participates in "orphans" or synthesis output is decided later by the caller's filter set.

## `/science:big-picture` Updates

Phase 1 bundle assembly:

- For each hypothesis, include only entities whose resolved aspects intersect the non-software-development project aspects. Software-only entities are excluded from the per-hypothesis bundles AND from orphan-question accounting.
- This tightens bundles measurably for projects with mixed research/software work. On natural-systems, the expected effect is that questions like `q14-data-quality-lens-design` no longer appear in hypothesis bundles or as orphan questions once they're tagged `[software-development]`.

Orphan-question counting:

- Orphans are now defined as questions that (a) have no resolved hypothesis association AND (b) have at least one non-software-development aspect in their resolved aspects. A question whose resolved aspects are `[software-development]` only is not an orphan — it's simply out of scope for research synthesis.
- This is a filtered notion of orphanhood. A software-only question may still have `primary_hypothesis: null` in resolver output; it just does not count as a research orphan and does not appear in `_emergent-threads.md`.

Phase 4 validator integration:

- `science-tool big-picture validate` continues to work unchanged; its existing checks are aspect-agnostic.

## Testing

### Unit tests (Python)

In `science-tool/tests/test_aspects_migration.py`:

- Migration correctly rewrites a sample `tasks/active.md` containing `type: research` and `type: dev` entries.
- Dry-run emits a diff without mutating the file.
- Idempotency: running migration twice yields no second-round changes.
- Project with only `software-development` in its aspects: research-task migration falls back to the full project aspects.

In `science-tool/tests/test_big_picture_resolver.py` (extended):

- A question with explicit `aspects: [software-development]` still resolves structurally as usual, and its `resolved_aspects` field is `[software-development]`.
- A question with no `aspects:` field in a research project inherits and is included.
- Invalid explicit `aspects:` values (`[]`, duplicates, or values outside `project.aspects`) raise a clear resolver/load error.

In `science-tool/tests/test_big_picture_validator.py` (extended):

- Orphan-count calculation excludes software-only questions.

### Integration test

Extend the existing minimal_project fixture at `tests/fixtures/big_picture/minimal_project/` with one explicitly software-tagged question (`q06-software-pipeline-concern.md`, `aspects: [software-development]`). Confirm:

- Resolver output shows the question's `resolved_aspects` as `[software-development]`.
- `big-picture resolve-questions --project-root` output may still show `primary_hypothesis: null` if the question has no structural match.
- Research bundle assembly and emergent-threads generation exclude the question.
- Orphan count for the project excludes this question from the "research orphans" tally.

## Relationship to Existing Specs

- **2026-04-18 big-picture spec**: aspect filtering slots into Phase 1 (bundle assembly) and Phase 3 (orphan count) exactly where the spec already calls out those computations. No conflict.
- **2026-04-15 layered-claims-and-causal-methodology spec**: independent. Claim-layer metadata is orthogonal to entity aspects; both can coexist.
- **Project-level `aspects:` in `science.yaml`**: this spec extends, not replaces. Project aspects remain the source of inheritance defaults.

## Resolved Decisions

- **Validation strictness**: explicit invalid entity `aspects:` is a hard error for aspect-aware commands and a proactive error finding in `science-tool health`.
- **Software-profile projects**: v1 does not silently repurpose `/science:big-picture` for software-only projects. If the project has no non-software aspect, research synthesis fails fast and directs the user toward future software-synthesis support.
- **Aspects on discussions, topics, papers**: omitted from v1. Expand only after observing concrete synthesis pollution from those entity classes.

## Follow-on Work

- **Propagate aspect filtering to `/science:status` and `/science:health`** if and when software-focused entities start cluttering those outputs. Not required by the current pain.
- **`science-tool aspects audit`** — reverse of migration: surface entities whose explicit `aspects:` don't align with their content (e.g., a hypothesis file tagged `[software-development]`, which is almost certainly a mistake). Heuristic-based; deferred until patterns emerge.
- **Big-picture `--aspects <name>` flag** — explicit user control over filter mode (research vs software vs custom subset). v1 defaults to "research synthesis" (everything except `software-development`); flag support can land alongside software-mode big-picture.

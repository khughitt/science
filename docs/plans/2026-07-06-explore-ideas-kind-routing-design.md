# explore-ideas kind routing — design

**Date:** 2026-07-06
**Targets:** `fb-2026-07-04-007`, audit coverage for `fb-2026-07-04-005`
**Surface:** `command:explore-ideas`, `science explore-ideas apply`

This is a narrow follow-up to the first `explore-ideas apply` implementation.
The goal is to let the report format's valid `proposed_kind: topic|theme`
candidates flow through the same tested apply validator as questions and
hypotheses, while confirming that convergent candidates produced independently
by multiple lenses are already represented without forcing keep-one.

## Problem

`explore-ideas` generation can propose `topic` and `theme` candidates, and the
apply validator already recognizes those kinds as valid. It then routes them to
`manual`, so a report can pass validation yet still leave the user hand-creating
the entity stub.

The lower-level entity scaffolder already supports `topic` and `theme`; the
blocker is the `explore_ideas.py` routing policy:

- `question` and `hypothesis` are routable.
- `topic` and `theme` are valid but manual.
- `build_create_plan` rejects any kept block outside the routable set.

Separately, `fb-2026-07-04-005` reported that independent generation by two
lenses had no representation. The current command text and apply code now carry
`origin_plan.origins` plus `lens_views`, including multiple lens views for one
converged candidate. This slice should verify that behavior is tested and
documented, not invent another convergence model.

## Decision

Make `topic` and `theme` first-class routable apply kinds.

`science explore-ideas apply` will create kept candidates whose
`proposed_kind` is one of:

- `question`
- `hypothesis`
- `topic`
- `theme`

All four kinds use the same apply-time contract:

- non-empty `title`
- non-empty, model-validated `origin_plan.origins`
- optional `literature_anchors` converted to `source_refs`
- optional `related_existing` resolved through the existing project ref index
- optional `lens_views` validated against planned origins
- `origins`, `added_by`, and `lens_views` written as extra frontmatter

There is no new topic/theme-specific schema in this slice. The existing entity
templates supply kind defaults, including `theme_kind` and `theme_scope` for
themes. If a later run needs richer theme typing, that should be a separate
report-format extension rather than a hidden special case in apply.

## CLI and output contract

The CLI shape does not change:

```bash
uv run science explore-ideas apply --from <report> --model-id <id>
uv run science explore-ideas apply --from <report> --model-id <id> --check
```

The visible behavior changes only when a kept candidate is `topic` or `theme`:

- it appears under `to_create` in `--check` instead of `manual`;
- it appears under `created` after apply instead of `manual`;
- the report block is marked `decision: applied` with `applied_as` and
  `applied_at`, the same as question/hypothesis blocks.

The `manual` result list remains in the dataclasses and JSON output because it
is still useful for future valid-but-not-routable decisions, but this slice
should leave no current `proposed_kind` routed there.

## Convergence representation audit

The existing representation remains:

- one candidate block for a converged idea;
- one `origin_plan.origins[]` entry per independently-producing lens;
- one `lens_views[]` entry per lens, each optionally linked with `origin_ref`;
- no keep-one rewrite when two lenses produce the same substantive idea.

Implementation should add or tighten tests that prove an applied multi-lens
candidate persists all `lens_views` and origins on the created entity. If the
current test already covers that fully, update command/skill docs only where the
manual-topic/theme wording is stale.

## Error handling

The existing fail-early apply semantics stay intact:

- unknown `proposed_kind` is still an `ApplyValidationError`;
- a kept block for any routable kind missing `title` or `origin_plan.origins`
  fails before writes;
- malformed origins, anchors, `related_existing`, or `lens_views` fail before
  writes;
- write-back failure after create remains fatal and non-resumable without manual
  repair.

No silent fallback should create a partial topic/theme with dropped provenance.

## Non-goals

- No post-apply gap-closure workflow. `fb-2026-07-04-006` needs a separate
  design because it is a follow-on workflow, not just apply routing.
- No topic/theme-specific report fields such as `theme_kind` or `theme_scope`.
- No migration or backfill of already-manually-created topic/theme entities.
- No new convergence entity kind or duplicate-candidate merge command.

## Testing

Focused tests should cover:

- `build_create_plan` accepts `proposed_kind: topic` and `proposed_kind: theme`.
- `plan_report` routes kept topic/theme candidates into `to_create`, not
  `manual`.
- `check_report` reports topic/theme candidates in `to_create`.
- `apply_report` creates topic and theme files and writes back `applied_as`.
- multi-lens `lens_views` and origins survive apply on a created entity.
- existing invalid-kind, malformed-origin, duplicate-lens, and write-back tests
  remain green.

Verification before merge should include the focused explore-ideas tests,
command/skill documentation tests, `ruff check`, and `pyright` on the touched
modules.

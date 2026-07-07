# Plan-Pipeline Decision Related Refs

**Feedback:** `fb-2026-07-04-001`
**Status:** Implemented

## Issue

The `plan-pipeline` frontmatter guidance treated `decision:<id>` like a valid
`related:` ref for project plans. That is unsafe for projects where decisions
still live only as sections in `core/decisions.md`: those section IDs are not
entity owners, so graph audit can report a hard unresolved-ref error.

## Decision

Keep core decision-log sections out of graph frontmatter. Pipeline plans should
cite load-bearing `core/decisions.md` sections in prose or a non-graph header
note such as `Decision context: core/decisions.md#<section>`.

`decision:<id>` remains valid only when it resolves to a real promoted owner
file under `entities/decision/*.md`. The guidance names that distinction
explicitly instead of claiming that `decision` is categorically not an entity
kind, because current Science layouts can promote decision owners.

## Validation

- Command-doc regression: `plan-pipeline` must document that core-log decisions
  are not graph refs.
- Codex-skill regression: generated `science-plan-pipeline` guidance must carry
  the same distinction.

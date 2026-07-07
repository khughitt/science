# explore-ideas first-run frictions — audit

**Date:** 2026-07-07
**Target:** `fb-2026-07-04-008`
**Surface:** `command:explore-ideas`, `science explore-ideas`, prose lint

This feedback bundled several first-run issues from the initial
`explore-ideas` run. The right response is an audit plus small confirmed fixes,
not a broad redesign.

## Classification

### meta-kind unregistered

Status: already addressed.

Current `commands/explore-ideas.md` says generated reports are process
artifacts, not graph entities, and must have a plain human header with no
`kind:` or entity frontmatter. The committed Codex skill mirrors that wording.

### report prose-lint

Status: fixed in this branch.

Exploration reports live under `doc/explorations/` and are process artifacts,
not durable graph prose. `science prose lint` previously scanned them because it
scanned all markdown under `doc/`. This branch excludes `doc/explorations/` from
the default prose-lint scan and documents the convention in the command and
Codex skill.

### empty DOI anchors

Status: fixed in this branch.

The resolver already tolerated empty DOI values by marking them unresolved, but
that produced noisy rows for placeholder anchors. This branch skips
`literature_anchors[]` entries that have no usable `ref`, DOI, citekey, title,
or `openalex_id`, and the command now tells authors to omit unknown identifier
fields rather than write `doi: ""` or `doi: null`.

### id-slug truncation

Status: already addressed.

Entity creation now emits a warning when title-derived id slugs are truncated,
and `explore-ideas apply` relays create warnings in both text and JSON paths.
Existing tests cover this behavior.

### stale Phase-1 path

Status: already addressed.

Current Phase 1 guidance reads `science.yaml`, `specs/research-question.md`,
`specs/scope-boundaries.md`, and `entities/topics/`. Existing command and Codex
skill tests assert that stale legacy path wording is absent.

## Verification Scope

This branch adds focused tests for the two live issues:

- prose lint excludes `doc/explorations/`;
- anchor resolution skips structurally empty placeholder anchors.

It also adds command and Codex skill tests for the first-run guardrail wording.

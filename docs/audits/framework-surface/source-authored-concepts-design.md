# Source-Authored Concepts Design

**Date:** 2026-07-02

**Status:** Draft for review

## Goal

Enable routine source-authored project concepts through the existing entity
creation path, so `concept` matches the core model contract and no longer
requires guidance to route around a CLI/model mismatch.

This is the behavior-changing follow-up to
`docs/audits/framework-surface/concept-source-ownership-design.md`. That audit
established the ownership contract for inquiry refs, unknown markers,
assumptions, transformations, and concept-like refs. This design narrows the
next slice to one question: should `science entity create concept ...` create a
normal Markdown owner under `entities/concepts/`?

## Current Evidence

The current system already treats `concept` as a source-owned markdown-capable
kind in every layer except the writer.

| Layer | Evidence |
|---|---|
| Core model | `concept` is an `AUTHORED_CORE` reference kind with `home="entities/concepts"`, slug identity, default status `active`, and statuses `active` / `deprecated`. |
| Path policy | `resolve_path_policy("concept")` returns `entities/concepts` with `slug` strategy; slug validation and path generation are already tested. |
| Source loading | `entities/concepts/*.md`, `knowledge/sources/<profile>/terms.yaml`, and aggregate `entities.yaml` concept rows already load as `concept:*` sources. |
| Graph materialization | Hand-authored `entities/concepts/*.md` records already materialize and resolve as owned concept refs in tests. |
| Sibling behavior | `construct` is also an authored-core reference kind with a slug home, and it is not blocked by the entity writer. |
| Current writer | `create_entity()` special-cases only `kind == "concept"` and raises `EntityCommandError("Source-authored concepts are not supported; use graph add concept instead")`. |

The block sends users toward `science graph add concept`, but that command
writes generated graph state in `knowledge/graph.trig`. `science graph build`
regenerates that file from source records, so direct graph mutation is
exploratory and not a durable authoring substitute.

## Decision

Support `science entity create concept ...` as the durable Markdown authoring
path for project-local concepts that need prose, lifecycle status, source refs,
aliases, same-as links, or relationships.

Keep `terms.yaml` as the lightweight source path for simple semantic terms that
only need a resolvable `concept:*` identity and short metadata. Keep
`science graph add concept` as exploratory graph mutation unless a later design
deprecates or relabels it more aggressively.

This changes guidance from:

- `concept` is a known CLI/model mismatch; use a domain kind, `terms.yaml`, or
  prose deferral.

to:

- use the most specific registered kind when one exists (a domain kind such as
  `gene` or `dataset`, or a core reference kind such as `construct` or `outcome`);
- use `terms.yaml` for lightweight local semantic terms;
- use `science entity create concept ...` when the local concept needs a normal
  entity owner;
- do not use `science graph add concept` for durable source authoring.

## Target Contract

| Need | Source owner |
|---|---|
| Domain-backed thing | Most specific registered kind, such as `gene`, `protein`, `disease`, `pathway`, `dataset`, or `method`. |
| Lightweight project concept | `knowledge/sources/<profile>/terms.yaml` row. |
| Full project concept | `entities/concepts/<slug>.md` created by `science entity create concept ...`. |
| Inquiry boundary ref or flow endpoint | Existing source ref; concept entities may be used when they already exist. |
| Causal treatment/outcome | Existing source ref, often a domain kind, concept entity, construct, or lightweight term. |
| Unknown marker | Marker on a ref in the inquiry source; not a standalone concept owner. |
| Assumption/transformation | Inquiry-local record in `entities/patches/<slug>.md` unless promoted to a normal entity kind. |

The concept entity path should follow the same generic `entity create` contract
as other markdown entity kinds:

- slug identity derived from the title unless `--slug` or `--id` is supplied;
- file path `entities/concepts/<slug>.md`;
- default status `active`;
- status validation against `active` and `deprecated`;
- standard frontmatter fields and generic Summary/Notes body;
- prospective validation warnings for unresolved refs, without suppressing the
  write;
- normal source loading, graph materialization, health, archive, and review
  behavior.

## Implementation Shape

The likely code change is deliberately small: remove the `kind == "concept"`
guard from `science/src/science_tool/entities.py:create_entity()`. The rest of
the generic entity writer should already handle concept path policy, slug IDs,
status defaults, frontmatter, destination collision checks, and prospective
validation.

The implementation should prove that assumption rather than broadening the
change:

1. Add a CLI test that `science entity create concept "Treatment Response"`
   writes `entities/concepts/treatment-response.md` with
   `id: concept:treatment-response`, `type: concept`, `status: active`, and
   the expected title.
2. Add a status test that `--status deprecated` is accepted for concepts, and
   an invalid status is rejected through the existing validation path.
   (`deprecated` is already classified LIVE in the `_LIVE_STATUSES` allowlist in
   `entities.py`, so no new status is introduced and the `test_status_visibility.py`
   guard does not need to change.)
3. Add an end-to-end test that a concept created through the CLI can be loaded
   and then used as a resolvable inquiry boundary/treatment/outcome or related
   ref during graph build.
4. Keep existing slug/path-policy tests as contract coverage rather than
   duplicating them.
5. Update docs and generated Codex mirrors only after the behavior test is
   green.

## Documentation Updates

Update source docs first, then regenerate mirrors:

- `docs/user-guide/entities.md`: replace "Current Concept Ownership Mismatch"
  with the supported concept entity contract and the distinction between
  `terms.yaml` and `entities/concepts/*.md`.
- `docs/user-guide/epistemic-model.md`: replace "future supported concept
  entity" / "CLI does not support" wording with current supported concept
  entity language.
- `commands/sketch-model.md`: allow `science entity create concept ...` as the
  durable path when the model genuinely needs a reusable project-local concept,
  while still preferring domain kinds and term rows for lighter cases.
- `commands/specify-model.md`: keep direct `science graph add concept` framed
  as exploratory and non-durable; point specified-model endpoints at existing
  source refs, including concept entities.
- `commands/create-graph.md` and `commands/health.md`: align concept triage
  language with the supported entity path plus lightweight term rows.
- `codex-skills/science-*`: regenerate from the source command docs; do not edit
  generated mirrors by hand.

Existing guard tests that assert the mismatch text should be intentionally
replaced, not loosened. New guards should assert the supported behavior and
continue to forbid direct graph mutation as durable concept authoring.

## Non-Goals

This slice should not:

- add a `terms.yaml` authoring helper;
- rename, remove, or deprecate `science graph add concept`;
- change inquiry unknown semantics;
- turn inquiry blocks into an entity-authoring surface;
- migrate existing aggregate concept rows into markdown owners;
- invent new concept subtypes or schemas beyond the existing generic entity
  markdown contract.

## Risks And Checks

| Risk | Check |
|---|---|
| A hidden downstream path still assumes concepts are aggregate-only. | Run concept-specific entity, source-load, graph-materialization, and docs guard tests. |
| Docs start recommending concept entities where a domain kind is better. | Keep the entity guide and command docs explicit: domain kind first, concept only for project-local semantic owners. |
| `terms.yaml` becomes redundant or confusing. | Document it as the lightweight tier, not a deprecated tier. |
| A `terms.yaml` (or aggregate) row and a new markdown owner both mint the same `concept:*` id. | The destination check (`entities.py`) only tests file existence, so it cannot see a same-id row in another source. Confirm the existing identity-collision path covers the two-tier case: `load_project_sources()` loads markdown owners before the structured/`terms.yaml` loader, so the markdown owner deterministically wins the id, and a competing row raises `EntityIdentityCollisionError` under `strict_identity` or is dropped-and-surfaced by the `entity_identity` health check otherwise. Add a test that asserts this rather than assuming it. |
| Existing generated skill guards still forbid `science entity create concept`. | Replace those guards with behavior-aware assertions and regenerate mirrors. |
| `graph add concept` remains easy to misuse. | Keep negative docs guards that prevent it from appearing as a durable authoring path; consider a later CLI warning/deprecation design. |

## Acceptance Criteria

- `science entity create concept "Treatment Response"` succeeds and writes
  `entities/concepts/treatment-response.md`.
- Created concept markdown reloads through `load_project_sources()` with
  canonical id `concept:treatment-response`.
- A created concept can be referenced by a graph-build path that currently
  requires resolvable refs.
- `science entity create construct ...` and existing non-concept entity create
  behavior remain unchanged.
- A `concept:*` id already declared by a `terms.yaml` (or aggregate) row does not
  silently produce two owners: the markdown owner wins deterministically, and the
  duplicate is either rejected (`strict_identity`) or reported by the
  `entity_identity` health check.
- User guide, command docs, and generated Codex skills no longer describe
  concept authoring as a CLI/model mismatch.
- Docs still state that `science graph add concept` is exploratory and
  non-durable.

## Follow-Ups

After this slice, the next useful designs are:

1. A `terms.yaml` authoring helper for lightweight local semantic terms.
2. A help-text or warning pass for `science graph add concept` so the CLI itself
   says the command writes derived graph state.
3. Sharper inquiry validation diagnostics that distinguish missing endpoint
   owners from sketch-only unknown markers and optional validation refs.

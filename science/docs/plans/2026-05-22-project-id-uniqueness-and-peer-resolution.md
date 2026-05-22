# Project `id` uniqueness and peer resolution

- **Date:** 2026-05-22
- **Status:** proposal (no code/config changes yet)
- **Scope:** registry `id` semantics + `commons promote --from` resolution; affects every project family, not just `~/d/health/`.
- **Trigger:** `science commons promote --from meta` fails with an ambiguity error because three registered projects share `id: meta`.

## Problem

`id` is overloaded. It is used simultaneously as:

1. a **global identifier** — what `commons promote --from <id>` resolves against (`resolve_project_by_id` in `src/science_tool/commons/config.py`), and
2. a **family-local handle** — `peers: - id: meta` inside a child's `science.yaml` means "the meta project of *my* family".

These two needs are in direct tension: an identifier must be globally unique, but the family-local handle is deliberately reused (`meta` recurs once per family). The collision is structural, not a data-entry mistake.

### Evidence (current registry)

From `~/.config/science/config.yaml`, three projects register `id: meta`:

| path | `name` | `id` | `role` |
|---|---|---|---|
| `~/d/cancer/meta` | `cancer-meta` | `meta` | `meta` |
| `~/d/health/meta` | `health-meta` | `meta` | `meta` |
| `~/d/science/meta` | `science-meta` | `meta` | `standalone` |

Two facts the fix can lean on:

- **`name` is already globally unique** (`cancer-meta`, `health-meta`, `science-meta`).
- **Relationships already resolve by path, not id.** `parent:` is path-based (`parent: ~/d/health/meta`). And every `peers[]` entry already carries **both** `id` *and* `path`:

  ```yaml
  # ~/d/health/comparisons/pan-disease/science.yaml
  peers:
    - id: meta
      path: ~/d/health/meta      # <- already unambiguous
    - id: cycles
      path: ~/d/health/processes/cycles
  ```

So the only place the collision actually bites is the *global, context-free* selector `--from <id>`. Relationship edges already have the disambiguating `path`.

## The fix already in place (and why it's only half the story)

`resolve_project_by_id` now **fails loudly** on an ambiguous id rather than silently returning the first match (which would have promoted the wrong corpus). That is correct defensive behavior, but it is a *guard*, not a *resolution*: promoting from any meta project still errors. We want a model where the guard becomes dormant — present, never firing in normal operation.

## Options

### A. Unique `id`; relationships resolve by `path`/`role` (recommended)

Make `id` a true globally-unique identifier. Set the three metas' `id` to their already-unique names (`cancer-meta`, `health-meta`, `science-meta`). The family-local "which one is my meta" need is a **relationship**, already expressible by:

- `role: meta` scoped to family membership (one meta per family — `role` uniquely identifies it within a family), and/or
- `peers[].path`, which is already present.

The `id` field inside `peers[]` then becomes redundant and can be dropped (consistent with `parent:`, which carries only a path today).

- **Pros:** `id` means what the word says; `--from cancer-meta` just works; the ambiguity guard becomes a dormant safety net; no new grammar for consumers to learn; aligns with *explicit > defensive* (a non-unique "identifier" is the smell being removed).
- **Cons:** multi-repo migration (configs + each child's `peers`); loses the generic `meta` token as a *handle* (but `role: meta` recovers it, more correctly).

### B. Family-namespaced ids (`health/meta`)

Keep the reused short id but namespace it by family; require global selectors to qualify (`--from health/meta` or `--family health --from meta`).

- **Pros:** preserves the generic `meta` token verbatim.
- **Cons:** introduces an id grammar every consumer (CLI, resolution, peers) must learn and parse; `id` is still not globally unique, just unique-within-namespace; more surface area than A for the same outcome.

### C. Path/family-scoped `--from` only (band-aid)

Leave ids colliding; add a path- or family-scoped `--from`.

- **Cons:** leaves `id` permanently non-unique, so the ambiguity error stays a live failure mode and **every future id-keyed feature re-hits this wall**. Rejected as a long-term answer.

## Recommendation

**Option A.** Separate identity from relationship: `id` globally unique (canonical), `role` + `path` carry the family-local relationship. Concretely:

1. Tool: confirm `resolve_project_by_id` requires global uniqueness (already does, via the fail-loud guard).
2. Tool: prefer `path` for peer resolution wherever peers are consumed; treat `peers[].id` as advisory, not the resolution key. (Audit consumers before dropping the field.)
3. Config/data migration (separate, reviewed change): set the three metas' `id` to their unique `name`; update or drop `peers[].id` references to them.

`name` vs `id` being two near-duplicate fields is itself worth a follow-up: long-term there should be **one** canonical unique identifier, with the other reserved for display.

## Migration scope (when approved)

- `~/.config/science/config.yaml`: 3 entries (`id: meta` → unique).
- The 3 metas' own `science.yaml` `id:` field.
- Children with `peers: - id: meta`: at least `pan-disease`, `cycles`, `pre-cancer`, `cbioportal` (full scan needed).
- **No entity-file churn:** entity ids are `paper:` / `hypothesis:` / etc. — they do not embed the *project* id, so summaries, questions, and knowledge graphs are unaffected. (Confirm with a grep before executing.)

## Open questions

1. Drop `peers[].id` entirely (path-only, like `parent:`), or keep it as a human-readable annotation that is *not* the resolution key?
2. Should `--from` also accept `name` during a transition, or cut straight to unique `id`?
3. Resolve the broader `name`-vs-`id` duplication, or leave `name` as display-only for now?

## Relation to the commons-promote work (2026-05-22)

This is the last deferred blocker from the commons-promote unblocking. The other four non-meta projects (`pan-disease`, `multiple-myeloma`, `evolution`, …) already plan cleanly; only the two `id: meta` projects (`cancer-meta`, `health-meta`) are gated by this. Resolving A makes them promotable without weakening the uniqueness contract.

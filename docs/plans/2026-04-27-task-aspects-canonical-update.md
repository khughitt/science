# Canonical validate.sh task-field update: `type:` → `aspects:`

**Status:** Draft. Targets canonical version bump `2026.04.26.2 → 2026.04.26.3`.

**Builds on:** `2026-04-19-entity-aspects-design.md` (the `aspects:` migration spec) and the managed-artifacts rollout. Surfaced as a real cross-project regression during the four-project migration pilot.

## Problem

`docs/specs/2026-04-19-entity-aspects-design.md` decided that all primary-entity types (tasks included) drop `type:` in favor of `aspects:`. Project-side migrations executed this — all four reference projects (`mm30`, `cbioportal`, `natural-systems`, `protein-landscape`) carry tasks with `aspects:` and zero with `type:`.

The canonical `validate.sh`'s task-field check still requires `type:`. Result: every task in every project fails validation with `task ${tid} missing required field: type`. mm30 emitted 250+ such errors immediately after migrating to canonical v2026.04.26.2.

This is canonical lag, not project-side legacy shape. Fix: update the canonical's required-field list to match the framework convention.

## Solution

In `science-tool/src/science_tool/project_artifacts/data/validate.sh` (around line 844), replace:

```bash
for field in type priority status created; do
    if ! echo "$block" | grep -qP "^- ${field}:" 2>/dev/null; then
        error "task ${tid} missing required field: ${field}"
    fi
done
```

with:

```bash
for field in aspects priority status created; do
    if ! echo "$block" | grep -qP "^- ${field}:" 2>/dev/null; then
        error "task ${tid} missing required field: ${field}"
    fi
done
```

One word changed. No new logic; no legacy-`type:`-detection branch (the 2026-04-19 spec assigns that responsibility to `science-tool health`, not `validate.sh`).

## Versioning

Canonical bump `2026.04.26.2 → 2026.04.26.3`. `byte_replace` migration. Existing previous_hashes preserved; the .2 hash slots in.

Changelog: "Replace deprecated `type:` task-field check with `aspects:` per docs/specs/2026-04-19-entity-aspects-design.md."

## Cross-project propagation

The three projects already at v2026.04.26.2 (`mm30`, `cbioportal`, `natural-systems`) become `stale` after this bump. Each runs `science-tool project artifacts update validate.sh --force --yes --project-root .` to refresh. Expected outcome: each project's error count drops by ~the number of tasks it has (no more spurious "missing type:" errors).

This dogfoods the *update* workflow end-to-end across multiple projects — until now we'd only exercised *install*. Useful proof point.

## Acceptance criteria

1. Canonical's task-field check uses `aspects` instead of `type`.
2. Body hash matches registry's `current_hash` for `2026.04.26.3`.
3. Previous hash for `2026.04.26.2` (`9d6a3486...`) preserved in `previous_hashes`.
4. `byte_replace` migration `.2 → .3` recorded with empty `steps`.
5. Changelog has `2026.04.26.3` entry.
6. All existing managed-artifact tests pass.
7. The three already-migrated projects update cleanly to .3 via the update verb and report a reduced error count on smoke-run.

## What this does NOT do

- Does not add legacy-`type:` migration-pending detection (that's `science-tool health`'s job per the 2026-04-19 spec).
- Does not change the `priority`, `status`, `created` requirements.
- Does not touch `workflow/Snakefile` or `meta:` xref handling — those are separate questions per the migration analysis.

## Cross-references

- Implementation plan: `docs/superpowers/plans/2026-04-27-task-aspects-canonical-update-implementation.md`
- Surfaced by: `docs/migration/projects/{mm30,cbioportal,natural-systems}.md` smoke runs
- Underlying convention: `docs/specs/2026-04-19-entity-aspects-design.md`

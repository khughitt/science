# Managed-Artifacts Rollout — Handoff

**As of:** 2026-04-27 (end of session).
**Status of main goal:** ✅ Complete. Managed-artifact system landed; canonical at v2026.04.26.3; all four reference projects migrated; migration template validated against 4 project shapes.

This doc captures what's left to do — none of it blocks the system; all of it's normal post-rollout cleanup and lint-debt resolution.

---

## What landed

Framework (`~/d/science`):
- Managed-artifact subsystem: registry, schema, install/check/diff/update/pin/unpin/exec verbs, drift classifier, declarative migrations, transaction snapshots, hook contract.
- Canonical `validate.sh` v2026.04.26.3 (initial port + Plan #7 fixes + hook dispatch points + task-aspects fix).
- Migration template + 4 per-project specs.
- Specs: `docs/superpowers/specs/2026-04-{26,27}-*.md`. Plans alongside.

Projects (each repo):
- All 4 migrated to v2026.04.26.3.
- protein-landscape carries a `validate.local.sh` sidecar (the only project needing one).
- Per-project migration spec in each project's `doc/plans/2026-04-27-managed-artifacts-migration.md`.

---

## Follow-ups

### Progress update — 2026-04-26

Completed in `managed-artifacts-followups`:

- **(1)** Canonical `validate.sh` warning counter now keeps xref warning increments in the parent shell. Bumped `validate.sh` to v2026.04.26.4 with a byte-replace migration record.
- **(4)** Updated the TempCommitSnapshot implementation-plan literal to match shipped `restore()` / `discard()` behavior, including idempotent restore.
- **(5)** Added `*.pre-update*.bak` to create/import `.gitignore` guidance and matching Codex skill copies.

### Framework-side

1. **`warn`-inside-`while`-subshell counter loss in canonical.** The xref-result loop pipes into `while IFS=: read ...; do warn "..."; done`. The subshell increments `WARNINGS`, but the value is lost when the subshell exits. Effect: the summary undercounts (e.g., protein-landscape's run shows `10 warnings` but ~224 `meta:` warns are emitted to stdout). Exit code is unaffected. Fix: rework the loop with process substitution `done < <(echo "$xref_result")` to keep the increment in the parent shell. Single canonical bump (v2026.04.26.4); same byte_replace migration shape as the prior bumps.

2. **Whether `meta:` should be a canonical xref-skip prefix.** protein-landscape uses `meta:` as a project-level semantic-category prefix (e.g., `meta:methodological`, `meta:purity`). Canonical's xref check doesn't recognize it. Decision needed: (a) add `meta:` to canonical's skip list (treats it as a recognized framework concept) OR (b) leave canonical alone and have protein-landscape drop the convention OR (c) add a project-side xref-allowlist mechanism in the sidecar (would require a new hook point or a config knob in `science.yaml`). Recommend: discuss whether `meta:` is broadly useful as a framework concept before deciding.

3. **`science-tool health` legacy-`type:` flag.** `docs/specs/2026-04-19-entity-aspects-design.md` says `science-tool health` should flag tasks still carrying legacy `type:` as "migration pending." Not implemented yet. None of the 4 reference projects have any `type:` tasks left, so no urgency, but the spec line is unfilled.

4. **TempCommitSnapshot's plan literal vs. shipped version.** The implementation plan `docs/superpowers/plans/2026-04-26-managed-artifacts-implementation.md` has example code for `TempCommitSnapshot.restore()` and `.discard()` that does not pass the plan's own tests. The shipped version (commit `5b5eeb5`, refined further by `fb9c1cd` for idempotency) is correct. Plan should be updated to match shipped behavior so future readers don't re-litigate. Pure documentation fix.

5. **`.pre-update.bak` cleanup convention.** Each `update` invocation leaves `validate.sh.pre-update.bak` in the project root. Currently untracked, accumulates over upgrades. Decision: (a) `.gitignore` it framework-wide (template addition), (b) auto-clean N versions back, (c) prompt the user. Recommend (a) — simplest and rollback-friendly.

6. **Migration template empirical update.** After the 4 pilots, three of four cases that were initially classified as Path 2 collapsed to Path 1 (config-bucket items already in `science.yaml`). Only protein-landscape exercised Path 3. Worth folding back into the template as a "common pattern" note: most config-bucket items are already correctly set in `science.yaml` from prior `import-project` flows; the validate.sh hardcoding was just shadowing.

### Project-side (lint debt surfaced by canonical)

Each is the project's call. The migration was deliberately scoped to NOT fix these in the migration commit — they're real findings, not migration failures.

7. **mm30** — 18 errors / 183 warnings post-v.3. Mostly broken cross-references in `doc/`. Fix or accept.

8. **cbioportal** — 5 errors / 14 warnings. Smallest debt; quick to clean.

9. **natural-systems** — 5 errors / 82 warnings, plus a "Duplicate document roots" warning (has both `doc/` and `docs/`). Decide which is canonical and consolidate.

10. **protein-landscape** — 1 error / 10+ warnings:
    - **Real ERROR**: `graph audit produced unparseable output`. The pre-migration `extract_json_payload` workaround was masking this. Triage: probably science-tool's graph-audit emitting deprecation warnings before JSON. Either fix science-tool's stdout cleanliness (framework-side, would benefit all projects) OR re-add a defensive parser as a hook (project-side workaround).
    - **`meta:` xref decision** (~224 warns, see follow-up 2 above).
    - **`workflow/Snakefile` decision**: framework convention says collapse `workflow/` into `code/`. Either restructure to `code/workflow/Snakefile` (clean, follows convention) or accept the warn (legitimate Snakemake convention divergence).

### Cross-cutting / observability

11. **Per-project migration specs aren't quite in sync with what landed.** Each project's `doc/plans/2026-04-27-managed-artifacts-migration.md` was written before the v.3 bump; it documents a v.2 migration. After the cascade refresh, there's a second commit on each project (`refresh validate.sh to 2026.04.26.3`) that the spec doesn't mention. Optional: append a "v2026.04.26.3 update" decision-log entry to each spec (the project-side commit is self-documenting; the spec edit is documentation-completeness only).

12. **Skipped-by-design**: per-section hook points (`pre_section_<N>`, `post_section_<N>`). Not in v1; YAGNI until concrete demand. Adding them later is a non-breaking version bump.

---

## Recommended ordering if resuming

If picking up later, suggested priority:

1. **(7)** mm30 lint cleanup — smallest project, exercises post-migration lint-fixing flow.
2. **(1)** Fix `warn`-in-subshell counter loss — cheap, broadly impactful (every project's summary becomes accurate).
3. **(10a)** Investigate and fix the science-tool graph-audit dirty-JSON issue — protein-landscape's only real ERROR; likely benefits all projects.
4. **(2)** Decide on `meta:` xref handling.
5. **(8, 9, 10b, 10c)** Other project-side lint cleanup, on each project's own schedule.
6. **(4, 5, 6, 11)** Documentation and convention follow-ups; low-priority polish.

The system itself doesn't need any of this to function. Migration is complete; everything below this point is steady-state maintenance.

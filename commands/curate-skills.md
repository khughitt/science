---
description: Triage portfolio skill-coverage gaps into science feedback. Runs `science skills curate`, presents ranked uncovered gaps, and on --apply files (or records recurrence of) a feedback entry per accepted gap. Report-first; writes no skill files.
---

# Curate skills · Coverage-gap triage

Surface the skill-*corpus* gaps the portfolio's analyses reveal — data-product
terms that project plans use but no skill covers — and record the accepted ones
as `science feedback` entries for later authoring. This command writes **no skill
files**; the only side effect (under `--apply`) is feedback.

Follow `${CLAUDE_PLUGIN_ROOT}/references/command-preamble.md` before executing this command.

Use `$ARGUMENTS` for optional flags. Recognized:

- `--apply` — consumed by this slash command; permits exactly one side effect
  (filing feedback via `science skills curate --apply`). Without it: report-only.
- `--project P` — restrict the scan to one registered project. Forwarded.

## Steps

1. Run the report-only plan (forward `--project` when the user passed it):

   ```bash
   uv run science skills curate --format json [--project <project>]
   ```

2. Present the `rows` to the user, ranked by `score`. For each, name the
   `term`, `likely_archetype`, `n_plans`/`n_projects`, and its `disposition`
   (`new`, `recur`, or a `skip`/`skip-addressed-conflict` against existing
   feedback — surface these but do not re-file them). Subject-folder placement is
   an authoring-time decision, not something to record now.

3. Report the `context` counts (`covered_not_loaded`, `unmapped`) as **project-side
   follow-ups only** — this command never files them.

4. If the user provided `--apply`, ask which gaps to accept, then file exactly
   those:

   ```bash
   uv run science skills curate --apply --term <term> [--term <term> …] [--project <project>]
   ```

   Forward the same `--project` value used in step 1, so the accepted terms and
   the filed feedback come from one scope. Bare `--apply` (no `--term`) files
   every `new`/`recur` row. Report the resulting feedback ids from each row's
   `result`.

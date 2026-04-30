# Decouple AGENTS.md from `core/` includes

**Date:** 2026-04-30
**Status:** approved (design)

## Problem

Projects scaffolded by `/science:create-project` end up with `AGENTS.md` that begins with:

```
@core/overview.md
@core/decisions.md
```

Those files routinely run hundreds of lines (e.g. mm30: `core/overview.md` 581 lines + `core/decisions.md` 317 lines = 898 lines), and Claude Code injects them into context every turn. AGENTS.md is supposed to be the agent's compact operational guide; the inclusion mechanism turns it into a context bloat point. `core/` is also the wrong place to *enforce* terseness — it is deliberately the long-form, append-only record.

A second smaller issue: at least one downstream project (mm30) has a legacy `CLAUDE.md` shape with the `@core/*` lines duplicated into `CLAUDE.md` itself, so the bloat lands twice.

## Goals

1. AGENTS.md never `@`-includes `core/*.md`.
2. AGENTS.md remains useful as a standalone operational guide *and* surfaces the load-bearing constraints an agent needs every turn.
3. Drift between `core/decisions.md` and AGENTS.md's constraint digest is detected and proposed for repair on a normal curation cadence — no new top-level command.
4. Existing projects can adopt the new shape without manual archaeology.

## Non-goals

- Removing the `core/` convention itself. `core/overview.md` and `core/decisions.md` stay, with their current length caps and append-only semantics.
- Auto-applying AGENTS.md edits silently. Curate proposes; user approves.
- Rewriting historical AGENTS.md content unrelated to the constraint digest.

## Design

### 1. AGENTS.md shape (template)

The canonical AGENTS.md becomes:

```markdown
# <project> — Agent Guide

## What this is
<1-2 sentence project description>

## Profile
<software | research>, with <one-line elaboration if useful>

## Validation
\`\`\`bash
bash validate.sh --verbose
\`\`\`

## Conventions
- <bullets — operational rules an agent will need every turn>

## Task execution
- <bullets — how tasks are run, where commits go, etc.>

## Known issues / nuances
- <bullets — gotchas not derivable from the code>

<!-- BEGIN: load-bearing-constraints (managed by /science:curate; edit core/decisions.md instead) -->
## Load-bearing constraints

- **D-001:** <one-line constraint phrased as a rule>
- **D-002:** <one-line constraint>
- ...
<!-- END: load-bearing-constraints -->

## Pointers
- Decisions: `core/decisions.md`
- Project overview: `core/overview.md`
- Active tasks: `tasks/active.md`
- Hypotheses: `specs/hypotheses/`
```

The `core/` files are referenced via the Pointers section, never `@`-included.

### 2. Load-bearing constraints digest

Curate regenerates the content *between the BEGIN/END markers* when drift is detected. Each entry is one line: `**D-NNN:** <imperative-phrased rule>`. The "why" stays in `core/decisions.md`. Markers make regeneration deterministic and protect free-form sections above.

The digest contains **only decisions whose `Status:` is `active`**. Superseded and abandoned decisions are dropped (their constraint no longer binds). When a decision is superseded, the new entry replaces the old one in the digest and the rule wording reflects the new decision.

If markers are absent (older AGENTS.md), curate proposes inserting them with the digest. User approves before the edit is applied.

### 3. Drift detection (in `/science:curate`)

Add an `agents-md` curation theme. Phase 1 evidence gathering adds:

- `mtime(AGENTS.md)` vs `mtime(core/decisions.md)`, `mtime(core/overview.md)`
- parse `core/decisions.md` for `## D-NNN` headings and read each entry's `Status:` line; the **active set** is the IDs whose status is `active` (not `superseded by ...` or `abandoned`)
- the digest's set of `**D-NNN:**` entries inside the markers
- presence/absence of the `BEGIN/END` markers
- presence/absence of legacy `@core/overview.md` / `@core/decisions.md` directives at the top of AGENTS.md
- shape of `CLAUDE.md`: whether it contains anything beyond `@AGENTS.md` and legacy `@core/*` directives (whitespace and blank lines tolerated)

Phase 2 produces candidates:

- `mtime(core/decisions.md) > mtime(AGENTS.md)` **or** the active-decision set differs from the digest's ID set → propose digest refresh (agent reads `core/decisions.md`, drafts one-line rules per **active** decision, shows diff). The mtime trigger covers the common case where an existing decision's status, implications, or wording changes without the ID set changing.
- legacy `@core/*` directives present in AGENTS.md → propose removal.
- legacy `@core/*` directives present in CLAUDE.md → propose normalization to a single `@AGENTS.md`.
- markers missing in AGENTS.md → propose inserting them with a freshly-generated digest.

`--apply-obvious` eligibility is narrow:

- Removing legacy `@core/*` directives from AGENTS.md is always eligible (purely structural deletion).
- Normalizing CLAUDE.md to `@AGENTS.md` is eligible **only** when the file's content (after stripping whitespace and blank lines) consists exclusively of `@AGENTS.md` and legacy `@core/*` directives. If CLAUDE.md carries any other content (project-specific guidance, comments, additional includes), the proposal is shown as a diff for user approval — silent deletion of project-specific instructions is the failure mode this guards against.

Initial marker insertion, digest generation, and edits to existing digest entries always require user approval, since they involve drafting one-line summaries from `core/decisions.md`.

### 4. Doc/template updates

- `commands/create-project.md` §"AGENTS.md" — drop the instruction to insert `@core/overview.md` / `@core/decisions.md`. Replace with: "Use the AGENTS.md template at `templates/agents-md.md` as a starting point. Pointers (not `@`-includes) reference `core/`."
- `commands/import-project.md` §"AGENTS.md" / "CLAUDE.md" — same change; explicitly call out: "If the existing AGENTS.md begins with `@core/*` directives, remove them; the constraint digest is maintained by `/science:curate` instead."
- `references/project-structure.md` §`core/` — change "`AGENTS.md` should `@core/overview.md` and `@core/decisions.md` when they exist" to "`AGENTS.md` references `core/` via the Pointers section and carries a managed digest of load-bearing constraints; it does not `@`-include `core/`."
- New file: `templates/agents-md.md` — the canonical scaffold above. `commands/create-project.md` now points to it instead of inlining a description.
- `codex-skills/` — regenerate after the `commands/` edits land. `codex-skills/science-create-project/SKILL.md` currently mirrors the old guidance (lines 305–312) and must be updated by re-running `scripts/generate_codex_skills.py` per `codex-skills/INSTALL.codex.md`. The implementation plan must include this regeneration step *and* a verification check that no generated `codex-skills/**/SKILL.md` contains the literal strings `@core/overview.md` or `@core/decisions.md`.

### 5. Live example: `meta/AGENTS.md`

Update `meta/AGENTS.md` to the new shape: drop the two `@core/` lines, insert the BEGIN/END markers with a digest of D-001–D-004, leave the existing operational content as-is (it is already well-shaped). Serves as the worked example for the convention.

## Components & data flow

```
core/decisions.md         curate (drift check)        AGENTS.md
   |  (mtime, D-NNN count)    |  (proposes diff)         |
   +--------------------------+--------------------------+
                              |
                              v
                    user approves edit
                              |
                              v
                  AGENTS.md digest section
                  refreshed between markers
```

No new tool subcommands. Curate's existing inventory + ledger machinery carries the new theme.

## Testing

- Update existing curate tests (if any) to cover the `agents-md` theme: drift detected, no-drift skipped, marker-insertion proposal, legacy `@core/*` removal proposal, CLAUDE.md normalization gated on "no semantic content beyond `@AGENTS.md` and legacy `@core/*`."
- Add a smoke test that `templates/agents-md.md` does not contain `@core/`.
- Add a smoke test that no generated `codex-skills/**/SKILL.md` contains `@core/overview.md` or `@core/decisions.md`.
- No tests required for `meta/AGENTS.md` (one-time content edit).

## Migration

- For mm30 and any other downstream projects with the legacy shape, the next `/science:curate` run will surface the legacy `@core/*` directives as a finding. With `--apply-obvious`, the directive removal + CLAUDE.md normalization happens unattended; the digest insertion gets staged for review.
- No breaking change. Old AGENTS.md files keep working until curate proposes the cleanup.

## Risks

- **Marker collisions** — unlikely, but the marker strings are explicit enough (`load-bearing-constraints (managed by /science:curate ...)`) to avoid clashing with anything natural.
- **Bad digest summaries** — agent might over-condense a decision into a misleading rule. Mitigation: digest entries always show `**D-NNN:**` so the user can cross-reference; first generation is never `--apply-obvious`.
- **Curate becomes too "chatty"** — adding another theme could noise up sweeps. Mitigation: drift signal is cheap (mtime + integer count); themes only fire when the signal trips.

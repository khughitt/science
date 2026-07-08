---
description: Create a durable theme entity interactively. Use when the user wants to add a cross-cutting organizing frame for questions, hypotheses, tasks, reports, concepts, methods, or guardrails.
---

# Add a Theme

Develop a structured theme from the user's input in `$ARGUMENTS`.

In this project, a theme is a durable organizing frame, not a synonym for any
interesting term. Use it when several entities, tasks, reports, or project
decisions need a shared lens that should be discoverable and linkable.

## Setup

Follow `${CLAUDE_PLUGIN_ROOT}/references/command-preamble.md` (role:
`research-assistant`).

Additionally:
1. Read existing themes in `entities/themes/` to avoid duplication.
2. Check `entities/questions/`, `entities/hypotheses/`, `entities/tasks/`,
   and recent project summaries when present; a theme should organize real
   project material.
3. Run `science entity sections theme --format json` and use the effective
   schema rows as the source of truth for frontmatter constraints. In
   particular, read the `theme_kind` enum and `theme_scope` enum from the
   `area: "frontmatter"` rows instead of copying values from prose.
4. Read `.ai/templates/theme.md` first; if not found, read
   `${CLAUDE_PLUGIN_ROOT}/templates/theme.md`. Use theme templates only after
   creation, as body-writing references.

If `science entity sections theme --format json` fails, stop and show the
error. Do not invent a theme schema from memory.

## Interactive Refinement

Have a natural conversation with the user to define the theme. Ask only for
information that is not already clear from `$ARGUMENTS` or the current project
state.

### 1. Clarify The Organizing Frame

- What project material should this theme organize?
- What decision, synthesis, or repeated review becomes easier if this theme
  exists?
- Is this a durable cross-cutting frame, or would a `concept`, `method`,
  `question`, `hypothesis`, `task`, or prose note be more precise?

Do not create a theme for a single isolated entity unless the user is
intentionally establishing a future organizing frame.

### 2. Choose Schema Values

Use the `science entity sections theme --format json` output to present valid
options.

- Choose `theme_kind` from the effective `theme_kind` enum.
- Choose `theme_scope` from the effective `theme_scope` enum.

Default to:

- `theme_kind: methodological` only when the theme concerns research process,
  evidence handling, tooling, or review practice.
- `theme_scope: project` unless the theme is intentionally shared across a
  federation or should be promoted to commons later.

For `theme_scope: cross-project`, ask which peer projects or federation-scope
themes it should relate to. Cross-link only when there is a concrete existing
or intended relationship; do not add vague cross-project links.

### 3. Identify Links

Collect initial `related` refs from existing durable entities:

- questions and hypotheses organized by the theme;
- tasks or task groups motivated by the theme;
- concepts, methods, stories, discussions, reports, or interpretations that
  the theme should connect;
- federation-scope themes that this theme specializes, overlaps, or should be
  reconciled with.

Use typed refs such as `question:q01-example`, `hypothesis:h02-example`, or
`task:t061`. If a related item is not a durable entity yet, mention it in the
body instead of inventing a ref.

### 4. Define Boundaries

Before creating the file, state the boundary in plain language:

- what belongs inside the theme;
- what should remain outside;
- what would make the theme too broad or misleading.

If the boundary is unclear, refine it before creation.

## Writing

Create first, then draft. `science entity create theme` owns ID sequencing,
frontmatter, file placement, and prospective validation.

```bash
uv run science entity create theme "<short title>" \
  --related <question-or-hypothesis-or-task-ref> \
  --related <theme-or-method-or-concept-ref> \
  --source-ref <paper-or-dataset-or-report-ref>
```

The command prints the chosen ID and file path. Do NOT pre-write the file or
hand-pick the ID; let the tool sequence and validate. If the user wants a
specific slug, pass `--slug <slug>`; if they need a literal ID, pass `--id
theme:<local-part>`.

`science entity create theme` currently renders the template defaults for
`theme_kind` and `theme_scope`. After creation, open the new file and edit only
these two frontmatter fields when the user chose values different from the
defaults. Preserve the rest of the frontmatter produced by `science`.

After any frontmatter adjustment, run:

```bash
uv run science validate --strict
```

Then fill in the body using `.ai/templates/theme.md` first, then
`${CLAUDE_PLUGIN_ROOT}/templates/theme.md` as the writing reference. Keep the
template's canonical sections:

- `## Definition`
- `## Why It Matters`
- `## Boundaries`
- `## Current Project Links`
- `## Guardrails`
- `## Downstream Work`
- `## Open Questions`
- `## Update Triggers`

Write the theme as:

- a concise organizing frame;
- explicit inclusion and exclusion boundaries;
- links to current project material;
- guardrails against over-generalization or layer mixing;
- concrete update triggers.

Do not frame the theme as evidence. A theme organizes evidence-bearing work; it
does not itself support or dispute a proposition.

## After Writing

1. If the theme should organize existing questions, hypotheses, or tasks, add
   reciprocal links with `science entity edit <ref> --related <theme-ref>` when
   the target kind supports it. Otherwise, update the target body in place.
2. If the theme is `cross-project`, note candidate commons promotion or
   federation reconciliation work, but do not promote it automatically.
3. Run `uv run science validate --strict`.
4. Commit: `git add -A && git commit -m "theme: add <short title>"`

## Process Reflection

Reflect on the **template** and **workflow** used above.

If you have feedback (friction, gaps, suggestions, or things that worked well),
report each item via:

```bash
science feedback add \
  --target "command:add-theme" \
  --category <friction|gap|guidance|suggestion|positive> \
  --summary "<one-line summary>" \
  --detail "<optional prose>"
```

Guidelines:
- One entry per distinct issue.
- If the same issue has occurred before, the tool will detect it and increment
  recurrence automatically.
- Skip if everything worked smoothly.
- For template-specific issues, use `--target "template:theme"` instead.

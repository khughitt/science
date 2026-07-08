---
name: science-add-theme
description: "Create a durable theme entity interactively. Use when the user wants to add a cross-cutting organizing frame for questions, hypotheses, tasks, reports, concepts, methods, or guardrails."
---

# Add a Theme

Converted from Claude command `/science:add-theme`.

## Science Codex Command Preamble

Before executing any research command:

1. **Resolve project profile:** Read `science.yaml` and identify the project's `profile`.
   Use the canonical layout for that profile:
   - `research` → `doc/`, `specs/`, `tasks/`, `knowledge/`, `papers/`, `models/`, `data/`, `code/`
   - `software` → `doc/`, `specs/`, `tasks/`, `knowledge/`, plus native implementation roots such as `src/` and `tests/`
2. Load role prompt: `.ai/prompts/<role>.md` if present, else `references/role-prompts/<role>.md`.
3. Load the `science-research-methodology` and `science-scientific-writing` Codex skills. If native skill loading is unavailable, use `codex-skills/INDEX.md` to map canonical Science skill names to generated skill files and source paths.
4. Read project context from current entity roots:
   - `entities/questions/` for active research questions.
   - `entities/hypotheses/` for hypotheses.
5. **Load project aspects:** Read `aspects` from `science.yaml` (default: empty list).
   For each declared aspect, resolve the aspect file in this order:
   1. `aspects/<name>/<name>.md` — canonical Science aspects
   2. `.ai/aspects/<name>.md` — project-local aspect override or addition

   If neither path exists (the project declares an aspect that isn't shipped with
   Science and has no project-local definition), do not block: log a single line
   like `aspect "<name>" declared in science.yaml but no definition found —
   proceeding without it` and continue. Suggest the user either (a) drop the
   aspect from `science.yaml`, (b) author it under `.ai/aspects/<name>.md`, or
   (c) align the name with one shipped under `aspects/`.

   When executing command steps, incorporate the additional sections, guidance,
   and signal categories from loaded aspects. Aspect-contributed sections are
   whole sections inserted at the placement indicated in each aspect file.
6. **Check for missing aspects:** Scan for structural signals that suggest aspects
   the project could benefit from but hasn't declared:

   | Signal | Suggests |
   |---|---|
   | Files in `entities/hypotheses/` | `hypothesis-testing` |
   | Files in `models/` (`.dot`, `.json` DAG files) | `causal-modeling` |
   | Workflow files, notebooks, or benchmark scripts in `code/` | `computational-analysis` |
   | Package manifests (`pyproject.toml`, `package.json`, `Cargo.toml`) at project root with project source code (not just tool dependencies) | `software-development` |

   If a signal is detected and the corresponding aspect is not in the `aspects` list,
   briefly note it to the user before proceeding:
   > "This project has [signal] but the `[aspect]` aspect isn't enabled.
   > This would add [brief description of what the aspect contributes].
   > Want me to add it to `science.yaml`?"

   If the user agrees, add the aspect to `science.yaml` and load the aspect file
   before continuing. If they decline, proceed without it.

   Only check once per command invocation — do not re-prompt for the same aspect
   if the user has previously declined it in this session.
7. **Resolve templates:** When a command says "Read `.ai/templates/<name>.md`",
   check the project's `.ai/templates/` directory first. If not found, read from
   `templates/<name>.md`. If neither exists, warn the
   user and proceed without a template — the command's Writing section provides
   sufficient structure.
8. **Resolve science CLI invocation:** When a command says to run `science`,
   prefer the project-local install path: `uv run science <command>`.
   This assumes the root `pyproject.toml` includes `science` as a dev
   dependency installed via `uv add --dev --editable "$SCIENCE_TOOL_PATH"`
   (the distribution is `science`; the entry point it installs is `science`).
   If you are operating from a git worktree and `uv run --frozen science ...`
   fails because a relative editable `tool.uv.sources` path resolves to a
   nonexistent checkout, use the main checkout's synced environment while
   keeping the worktree as the current directory:
   `$MAIN/.venv/bin/science <command>`. For wrappers or rules that shell out to
   nested `uv run --frozen ...`, export `UV_PROJECT=$MAIN` so dependencies
   resolve from the main checkout while cwd-relative project files still come
   from the worktree.
   If that fails (no root `pyproject.toml` or science not in dependencies),
   fall back to:
   `uv run --with <science-plugin-root>/science science <command>`

Develop a structured theme from the user's input in the user input.

In this project, a theme is a durable organizing frame, not a synonym for any
interesting term. Use it when several entities, tasks, reports, or project
decisions need a shared lens that should be discoverable and linkable.

## Setup

Follow `references/command-preamble.md` (role:
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
   `templates/theme.md`. Use theme templates only after
   creation, as body-writing references.

If `science entity sections theme --format json` fails, stop and show the
error. Do not invent a theme schema from memory.

## Interactive Refinement

Have a natural conversation with the user to define the theme. Ask only for
information that is not already clear from the user input or the current project
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
`templates/theme.md` as the writing reference. Keep the
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

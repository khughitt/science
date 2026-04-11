# Downstream Feedback Fixes Design

## Goal

Address the open downstream feedback that still reflects real product problems:

1. command docs imply project-local framework files that are not actually scaffolded
2. `science-tool graph question-summary` looks incomplete by default because it truncates to 25 rows
3. new and imported projects do not explicitly install `science-tool`, even though core workflows depend on it

## Decisions

### 1. Keep framework defaults centralized

Framework templates, references, and role prompts remain plugin-owned defaults.
Downstream projects should only add overrides in `.ai/`.

That means command docs must stop saying things like:

- `Follow references/command-preamble.md`
- `Read templates/interpretation.md`
- `Read docs/claim-and-evidence-model.md`

as if those files are expected to exist in the downstream repo.

Instead, command docs should use one of two patterns:

- explicit framework path: `${CLAUDE_PLUGIN_ROOT}/references/...`
- override-aware path: `.ai/templates/<name>.md` first, then `${CLAUDE_PLUGIN_ROOT}/templates/<name>.md`

This aligns the command text with the existing model described in `references/command-preamble.md`
and `references/project-structure.md`.

### 2. `question-summary` should return all rows unless the caller asks for truncation

The current default of `--top 25` is reasonable for dashboards, but it is the wrong default for
workflow-driving commands and downstream debugging. The command should return all questions by default
and let callers opt into truncation with `--top`.

This removes the main source of confusion behind the downstream report that some valid
`sci:addresses` edges were being ignored.

### 3. Every Science-managed project gets a project-local `science-tool` install

`science-tool` is not optional glue. It is used for tasks, feedback, graph summaries, and validation.
New and imported projects should therefore install it immediately.

Implementation choice:

- if the project already has a root `pyproject.toml`, add `science-tool` there as a dev dependency
- if not, create a minimal root `pyproject.toml` that exists specifically to host Science tooling
- install with `uv add --dev --editable <resolved-science-tool-path>`

This applies even to non-Python projects. A root `pyproject.toml` used only for tooling is acceptable.
It should be documented as a tool manifest, not as evidence that the product itself is Python-based.

### 4. Validate the contract, not just the docs

The create/import command docs are the primary bootstrap mechanism, but they are not sufficient by
themselves. `validate.sh` should fail when `science-tool` is unavailable, because task management,
feedback, and graph operations are now part of the baseline project contract.

## Scope

In scope:

- command doc path-resolution fixes
- create/import/bootstrap/install guidance
- project-structure documentation for tool manifests
- validation behavior for required `science-tool`
- `question-summary` default behavior and tests

Out of scope:

- broader reasoning-model doc migration away from `docs/claim-and-evidence-model.md`
- changing graph ranking logic beyond the `--top` default
- copying framework defaults into downstream repos

## Expected Outcome

After these changes:

- downstream command execution no longer expects nonexistent project-local framework files
- `question-summary` no longer hides rows by default
- every new or imported project gets a usable `science-tool` install from the start
- validation catches missing tool setup early instead of allowing partial project setups to drift

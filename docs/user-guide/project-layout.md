# Project Layout

Science-managed projects use a small set of stable roots. The exact research or
software stack can vary, but the Science-managed context should remain easy for
agents and humans to find.

## Common Roots

| Path | Purpose |
|---|---|
| `science.yaml` | Science project manifest: profile, aspects, ontologies, peers, and knowledge-profile configuration. |
| `pyproject.toml` | Project-local Python/tooling manifest so `uv run science ...` and validation resolve consistently. |
| `AGENTS.md` / `CLAUDE.md` | Operational instructions for agents. |
| `README.md` | Project front door. |
| `doc/` | Research notes, background, interpretations, reports, discussions, and other prose. |
| `specs/` | Hypotheses, propositions, plans, and structured project specifications when a project keeps them there. |
| `tasks/` | Active, blocked, deferred, retired, and completed work. |
| `knowledge/` | Generated graph files, summaries, snapshots, and other derived knowledge artifacts. |
| `papers/references.bib` | Bibliography entries for cited literature. |
| `.ai/` | Optional project-specific prompts, templates, and overrides. |

## `science.yaml` And `pyproject.toml`

`science.yaml` tells Science what kind of project this is and which knowledge
profiles, aspects, ontologies, and peers are active.

Example:

```yaml
profile: research
layout_version: 2
aspects:
  - computational-analysis
ontologies: [biolink]
knowledge_profiles:
  local: local
```

`pyproject.toml` is the local tooling manifest. Managed projects use it so
commands such as `uv run science validate` and `uv run science graph build`
resolve the same `science` tooling in the same environment.

## Source And Generated Artifacts

Authored source files are where durable project meaning lives. Generated files
are rebuilt from source.

Common generated artifacts include:

- `knowledge/graph.trig`
- dashboard summaries
- belief snapshots
- migration or health reports
- prose grounding and health artifacts

Do not hand-edit generated graph state as the durable fix. Fix the source entity,
source document, bibliography entry, or project manifest, then rebuild.

## Profiles And Aspects

Science supports research-first and software-first projects. A project's
`profile` selects the broad layout expectations. `aspects` are explicit behavior
or domain modifiers such as `hypothesis-testing`, `computational-analysis`, or
`software-development`.

Use the profile for layout. Use aspects for workflow behavior.

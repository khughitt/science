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
| `entities/` | Typed entity **owners**, one subdirectory per kind (`entities/datasets/`, `entities/papers/`, `entities/topics/`, `entities/hypotheses/`, `entities/questions/`, `entities/workflows/`, …). The single structural home for everything the project *owns*. |
| `overlays/` | Project-local **overlays** — files carrying `overlay_of:` that borrow and extend a commons-canonical entity. One subdirectory per type (`overlays/datasets/`, `overlays/papers/`, `overlays/topics/`, `overlays/themes/`). |
| `doc/` | Prose **only**: research notes, background, interpretations, reports, discussions, figures. No typed entity owners live here. |
| `specs/` | Hypotheses, propositions, plans, and structured project specifications when a legacy project keeps them there. |
| `tasks/` | Active, blocked, deferred, retired, and completed work. |
| `knowledge/` | Generated graph files, summaries, snapshots, and other derived knowledge artifacts. |
| `papers/references.bib` | Bibliography entries for cited literature. |
| `.ai/` | Optional project-specific prompts, templates, and overrides. |

## Three-Root Entity Layout (`layout_version: 3`)

At `layout_version: 3` every markdown entity has exactly one structural home, and
a reader can locate anything by *what it is*:

- **`entities/<kind>/`** — owners. A thing the project itself defines lives here,
  in the subdirectory for its kind. Filenames follow the entity `id` (e.g.
  `dataset:ctrpv2` → `entities/datasets/ctrpv2.md`).
- **`overlays/<type>/`** — borrows. When the project extends a commons-canonical
  entity rather than owning it, the `overlay_of:` file lives here, never under
  `entities/` (which would mint a competing owner) and never under `doc/`.
- **`doc/`** — prose. Background, interpretations, reports, discussions, figures —
  no typed entity owners.

This replaces the older v2 arrangement where dataset, paper, topic, and theme
files were scattered under `doc/<type>/`. See
`docs/user-guide/entities.md` for the entity model and source entity CLI
contract.

The v2-to-v3 migration path is still available for legacy projects through
`science entities migrate`. A dry run plans moves, rewrites resolvable full-id
references, and reports blockers without changing files. `--apply` performs the
tracked moves, writes any synthesized frontmatter, runs the graph-audit-equivalent
post-move check, and only then bumps `layout_version: 3`.

Migration blockers are structural project-state problems, not every prose token.
References in graph-audited fields block when they would be unresolved after the
move. Leftover entity-looking tokens in prose bodies are reported as warnings, so
examples, code snippets, wikilinks, cross-project mentions, and stale prose notes
do not block a mechanical layout move. Files under a known legacy entity root
that lack an explicit `id`, `type`, or `kind` are skipped with a warning instead
of being silently treated as entities.

Project-local markdown kinds declared in the active local profile participate in
this migration. By default a local kind lives at `entities/<kind>/`, uses numeric
filenames, defaults to `status: active`, and accepts an open status vocabulary.
The profile may declare `home`, `strategy`, `default_status`, and `statuses` to
override those defaults. Malformed local-kind declarations are skipped with
warnings during migration and conformance checks, rather than aborting unrelated
core-kind migration work.

## `science.yaml` And `pyproject.toml`

`science.yaml` tells Science what kind of project this is and which knowledge
profiles, aspects, ontologies, and peers are active.

Example:

```yaml
profile: research
layout_version: 3
aspects:
  - computational-analysis
ontologies: [biology]
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

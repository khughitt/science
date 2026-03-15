# Project KG Migration Guide

This guide summarizes how Science project knowledge graphs changed and what a project should look like after migration.

## What Changed

| Area | Old Form | New Form |
|---|---|---|
| IDs | Mixed short IDs, aliases, and RDF-local IDs | One canonical ID scheme used verbatim across docs, tasks, RDF, and UI |
| KG structure | Implicit or fragmented graph | Layered graph: `core` -> optional curated profiles -> `project_specific` |
| Tasks | Outside the KG or weakly linked | First-class graph entities |
| `graph.trig` | Could drift from docs/tasks | Generated artifact only |
| Project-local knowledge | Ad hoc RDF nodes or prose-only mentions | Structured sources under `knowledge/sources/<local-profile>/` |
| Validation | Mostly file-structure checks | Canonical graph audit, graph build, graph validate, graph/prose sync |
| Web/tooling assumptions | Hardcoded entity handling | Profile-aware and task-inclusive |

## New Project Shape

Every project now has:

```yaml
knowledge_profiles:
  curated: [bio]
  local: project_specific
```

`core` is always present.

`curated` is a list and may include multiple profiles, for example:

```yaml
knowledge_profiles:
  curated: [bio, physics]
  local: project_specific
```

`local` names the project extension layer. Use `project_specific` unless there is a strong reason not to.
That same value controls the directory name under `knowledge/sources/`.

## Canonical Sources

Author graph knowledge in these places:

- typed markdown docs under `doc/` and `specs/`
- task files under `tasks/`
- project-local structured sources under:
  - `knowledge/sources/<local-profile>/entities.yaml`
  - `knowledge/sources/<local-profile>/relations.yaml`
  - `knowledge/sources/<local-profile>/mappings.yaml`

Do not hand-edit `knowledge/graph.trig`.

## Canonical ID Rules

Use full canonical IDs everywhere, not short aliases.

Examples:

- `hypothesis:h01-raw-feature-embedding-informativeness`
- `question:q60-does-formalized-pipeline-reproduce-phase3b-results`
- `task:t127`
- `bias-audit:2026-03-11-phase3b`

Avoid forms like:

- `hypothesis:h01`
- `hypothesis:H01`
- `question:Q60`
- `hypothesis/h01` in project-authored source files

Aliases may still exist for migration support, but they should not be the normal authoring form.

## New Build Workflow

After editing canonical sources:

```bash
science-tool graph migrate --project-root . --format json
science-tool graph audit --project-root . --format json
science-tool graph build --project-root .
science-tool graph validate --format json --path knowledge/graph.trig
./validate.sh --verbose
```

`graph migrate` is the optional cleanup step that rewrites alias-resolvable references, writes
`knowledge/reports/kg-migration-audit.json`, and scaffolds local-profile source files for unresolved
project-local entities before the final audit/build cycle.

Expected end state:

- `graph audit` returns no unresolved canonical references
- `graph validate` passes
- `validate.sh` reports graph/prose sync and clean frontmatter cross-references

## Migration Checklist

1. Add `knowledge_profiles` to `science.yaml`.
2. Canonicalize IDs in frontmatter and task `related:` fields.
3. Move project-local entities and mappings into `knowledge/sources/<local-profile>/`.
4. Ensure tasks are represented with canonical `task:*` references.
5. Rebuild `knowledge/graph.trig`.
6. Fix any unresolved refs reported by `graph audit`.
7. Fix any stale-input or cross-reference issues reported by `validate.sh`.

## Practical Mapping

| If you previously used... | Replace it with... |
|---|---|
| Short hypothesis/question refs in frontmatter | Full canonical IDs |
| Direct TriG edits | Markdown/task/YAML source edits |
| One-off local nodes in RDF | local-profile entities or relations |
| Hidden ontology links | Explicit bridge links through canonical source fields |
| Task metadata outside the graph | Canonical task refs and task materialization |

## Notes For Tooling

Tooling now assumes:

- canonical IDs are the authority
- `graph.trig` is derived state
- projects may compose multiple curated profiles
- tasks belong in the KG
- project-specific extensions follow the same schema discipline as shared profiles

If a project needs manual curation that does not fit existing docs or tasks, add a structured upstream source for it instead of patching the materialized graph.

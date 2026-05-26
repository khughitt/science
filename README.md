# Science

![Science](extra/Science.webp)

Science helps Claude and Codex users develop research questions, refine
hypotheses, represent uncertain propositions, track evidence, and build
reproducible computational workflows.

## What Science Is

Science is both an agent workflow package and local project tooling for
research work. Claude and Codex workflows are the primary interface; the
`science` CLI supports validation, source-authored entities, graph
materialization, evidence summaries, synchronization, and project health.

Science is skeptical by default:

- hypotheses are organizing conjectures
- propositions are the main belief-bearing assertions
- evidence supports or disputes propositions rather than proving them outright
- uncertainty, contestation, and fragility stay visible
- literature, data, and causal provenance should be explicit

## Start Here

For Claude plugin installation:

```text
/plugin marketplace add <marketplace-url>
/plugin install science@<marketplace>
```

For local Claude development:

```bash
claude --plugin-dir /path/to/science
```

For Codex, see [docs/README.codex.md](docs/README.codex.md). Codex support uses
generated `science-*` skills from `codex-skills/`.

The main manual is [docs/user-guide.md](docs/user-guide.md).

## Core Model

Science uses a layered reasoning model:

- `question`: what the project wants to learn
- `hypothesis`: an organizing conjecture
- `proposition`: a belief-bearing assertion
- `observation`: a concrete empirical finding
- `evidence-line`: durable support or dispute with provenance
- `inquiry`: a graph-backed work program connecting variables, assumptions,
  propositions, datasets, transformations, and decisions
- graph summaries and belief snapshots: derived views over authored sources

For field-level detail, see
[docs/proposition-and-evidence-model.md](docs/proposition-and-evidence-model.md).
For workflow teaching, see [docs/user-guide.md](docs/user-guide.md).

## Fast Start

One possible research loop:

```text
create/import project -> status -> research-topic/search-literature ->
add-hypothesis -> proposition/evidence lines -> graph build ->
dashboard summary -> validate/health -> next-steps
```

Research is usually nonlinear. You may start from a paper, dataset, failed
analysis, causal concern, or project-health warning, then loop through the same
concepts in a different order.

For durable evidence, prefer source-authored files such as propositions and
evidence lines. If the graph is wrong, fix the source artifact and rebuild the
graph rather than patching generated TriG directly.

## Command Map

| Intent | Claude | Codex | CLI |
|---|---|---|---|
| Start a project | `/science:create-project` | `science-create-project` | project scaffold workflows |
| Adopt a project | `/science:import-project` | `science-import-project` | project scaffold workflows |
| Orient | `/science:status` | `science-status` | `science graph dashboard-summary` |
| Plan next work | `/science:next-steps` | `science-next-steps` | `science tasks list`, `science tasks summary` |
| Research a topic | `/science:research-topic` | `science-research-topic` | source-authored docs |
| Search literature | `/science:search-literature` | `science-search-literature` | `science bib add` |
| Summarize papers | `/science:research-papers` | `science-research-papers` | source-authored docs |
| Add hypotheses | `/science:add-hypothesis` | `science-add-hypothesis` | `science hypothesis create` |
| Pre-register | `/science:pre-register` | `science-pre-register` | source-authored docs |
| Compare alternatives | `/science:compare-hypotheses` | `science-compare-hypotheses` | source-authored docs |
| Discuss critically | `/science:discuss` | `science-discuss` | `science discussion create` |
| Audit bias | `/science:bias-audit` | `science-bias-audit` | source-authored docs |
| Create propositions | workflow-guided | workflow-guided | `science proposition create` |
| Add evidence lines | workflow-guided | workflow-guided | `science entity create evidence-line ...` |
| Sketch a model | `/science:sketch-model` | `science-sketch-model` | `science inquiry init` |
| Specify a model | `/science:specify-model` | `science-specify-model` | `science inquiry add-node`, `science inquiry add-edge` |
| Critique approach | `/science:critique-approach` | `science-critique-approach` | `science inquiry validate` |
| Plan analysis | `/science:plan-analysis` | `science-plan-analysis` | source-authored plans |
| Plan pipeline | `/science:plan-pipeline` | `science-plan-pipeline` | source-authored plans |
| Review pipeline | `/science:review-pipeline` | `science-review-pipeline` | validation and review docs |
| Interpret results | `/science:interpret-results` | `science-interpret-results` | source-authored interpretations |
| Build/update graph | `/science:create-graph`, `/science:update-graph` | `science-create-graph`, `science-update-graph` | `science graph build` |
| Validate health | `/science:health` | `science-health` | `science validate`, `science health` |
| Sync projects | `/science:sync` | `science-sync` | `science peers list`, `science sync status`, `science sync run` |

## Canonical References

- [docs/user-guide.md](docs/user-guide.md): end-user workflow guide
- [docs/proposition-and-evidence-model.md](docs/proposition-and-evidence-model.md): reasoning model and field-level detail
- [docs/project-organization-profiles.md](docs/project-organization-profiles.md): project profiles and layout
- [docs/federation.md](docs/federation.md): peers, composite graphs, and cross-project references
- [docs/conventions/validate.md](docs/conventions/validate.md): validation conventions
- [docs/README.codex.md](docs/README.codex.md): Codex skill generation and installation

## Development

Science includes two Python packages:

| Package | Description |
|---|---|
| `science-model` | Shared Pydantic models for entities, relations, tasks, profiles, ontologies, and project config |
| `science` | CLI and graph/project tooling for validation, graph operations, sync, datasets, feedback, and task management |

Both require Python >= 3.11.

## License

MIT

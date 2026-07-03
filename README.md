# Science

![Science](extra/Science.webp)

Science is an agent workflow package and local project tooling for research
work. Claude and Codex workflows are the primary interface; the `science` CLI
handles validation, source-authored entities, graph materialization, evidence
and belief summaries, cross-project sync, and project health. Its job is not to
turn every claim green, but to keep support, dispute, fragility, and missing
evidence honest and inspectable.

## Philosophy

Science is skeptical and data-driven by default. The creed:

- Open data is preferred over closed data; open literature over closed
  literature.
- Believe nothing until we have re-analyzed the data ourselves.
- Support from multiple independent datasets outweighs single-dataset support.
- Literature claims are *hints*, not facts. Belief updates from our own
  analyses, not from what a paper concluded.
- Uncertainty, contestation, and fragility stay visible. Fail early, prefer
  explicit over defensive, and never bury a weak result to make a dashboard
  look green.

See [Big Picture](docs/user-guide/big-picture.md) for the full stance.

## Substrate & Epistemic Model

Authored project files are the source of truth — mostly Markdown entity files
with YAML frontmatter, plus the bibliography, source records, annotations, and
manifests. The knowledge graph, dashboard summaries, belief snapshots, and
health reports are all *derived views*. When a derived view is wrong, fix the
source and rebuild the graph rather than hand-patching generated TriG.

The working model is a heterogeneous **patchwork** of small epistemic
neighborhoods rather than one undifferentiated graph, and a **commons** holds
reusable canonical owners — shared datasets and reference graphs — that peer
projects synchronize without flattening away local context. Belief flows along
a spine of typed players:

```text
question → hypothesis → proposition → observation / evidence-line →
belief → snapshot
```

Evidence *supports* or *disputes* a proposition; it never *proves* it. See
[Big Picture](docs/user-guide/big-picture.md) and
[Epistemic Model](docs/user-guide/epistemic-model.md) for the full model.

## Data Model

An `Entity` is a typed `kind:id` record — for example `hypothesis:h01-example`
or `dataset:gtex-v8` — stored as Markdown with YAML frontmatter, where the
frontmatter carries machine-readable identity and relations and the body
carries human context. Datasets are described as a Frictionless Data Package:
the runtime surface is `datapackage.yaml` (a JSON `datapackage.json` is also
accepted), and each tabular resource can carry a typed schema that is the
source of truth for its shape and QA inputs. See
[Entities](docs/user-guide/entities.md) for the full data model.

## Commands

A few of the commands you will reach for most:

- `/science:create-project` — scaffold a new managed project
- `/science:status` — orient on active hypotheses, open questions, and gaps
- `/science:next-steps` — synthesize progress and suggest what to work on
- `science graph build` — materialize the knowledge graph from sources
- `science evidence-lines create` — author a durable evidence line
- [`science validate`](docs/conventions/validate.md) — check a project against the conventions

Full command map in the [user guide](docs/user-guide/agent-workflows.md).

project-local tooling is installed through each project's `pyproject.toml` so
agents run the `science` CLI from the managed project environment. Validation
also supports Python sidecar hooks for project-specific checks.

## Skills

Science ships domain skills — research methodology, statistics, data handling,
scientific writing, and pipeline orchestration — that Claude loads on demand as
the work calls for them. See the [user guide](docs/user-guide/index.md) for how
they fit into the research workflow.

## Start Here

For the Claude plugin:

```text
/plugin marketplace add <marketplace-url>
/plugin install science@<marketplace>
```

For local Claude development:

```bash
claude --plugin-dir /path/to/science
```

For Codex, see [Codex](docs/user-guide/codex.md); support uses generated
`science-*` skills from `codex-skills/`. The main manual is the
[user guide](docs/user-guide/index.md).

## Development

Science includes two Python packages:

| Package | Description |
|---|---|
| `science-model` | Shared Pydantic models for entities, relations, tasks, profiles, ontologies, and project config |
| `science` | CLI and graph/project tooling for validation, graph operations, sync, datasets, feedback, and tasks |

Both require Python >= 3.11.

## License

MIT

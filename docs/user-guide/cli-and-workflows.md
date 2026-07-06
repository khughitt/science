# CLI And Workflows

The `science` CLI is the durable tooling layer under the agent workflows. It
creates source files, validates project state, builds derived graph views, and
reads project summaries. Prefer commands that write source-authored records for
durable project knowledge; treat generated graph files and reports as derived
state unless a command explicitly says otherwise.

This chapter is a command-family map, not an exhaustive reference. Use
`science --help` and `science <group> --help` for exact options.

## Command Classes

| Class | Meaning |
|---|---|
| Canonical | Preferred for new durable Science work. |
| Specialized | Correct for a specific advanced workflow, but not part of the everyday path. |
| Derived-state | Reads or writes generated views, reports, indexes, or summaries. |
| Migration-only | Exists to move old project state into the current model. |
| Exploratory | Useful for experiments or manual diagnostics; avoid as normal durable authoring. |
| Legacy | Kept for compatibility or cleanup; avoid in new workflows. |

## Write Classes

| Write class | Meaning |
|---|---|
| Read-only | Prints diagnostics, summaries, or plans without modifying project files. |
| Source-write | Writes source-authored project records that should be committed. |
| Generated-write | Writes derived files that can be rebuilt from source records. |
| External-write | Writes outside the current project, such as a global registry or commons store. |
| Mixed | Contains subcommands with different write classes; inspect subcommand help. |

Prefer read-only commands for orientation, source-write commands for durable
knowledge, and generated-write commands for materialization or reports.

## Core Loop

| Step | Preferred commands | Notes |
|---|---|---|
| Author questions and hypotheses | `science questions create`, `science hypotheses create`, `science entity create ...` | Typed wrappers call the same source-authoring path as `science entity`. |
| Author propositions and evidence | `science propositions create`, `science evidence-lines create` | Use source files for project knowledge that should survive graph rebuilds. |
| Build derived state | `science graph build`, `science belief snapshot` | These commands materialize views from authored sources. |
| Inspect state | `science graph dashboard-summary`, `science graph evidence`, `science entity show`, `science entity list` | Most inspection commands are read-only. |
| Validate and triage | `science validate`, `science health`, `science refs check`, `science prose lint` | Use validation output as the project health contract. |
| Plan next work | `science tasks list`, `science tasks summary`, `science graph attention-rank` | Task and attention commands help choose review work. |

## Command Families

| Family | Class | Write class | Use |
|---|---|---|---|
| `entity` | Canonical | Source-write / Read-only | Generic source-authored entity creation, editing, notes, listing, and inspection. |
| `questions`, `hypotheses`, `propositions`, `evidence-lines`, `discussions`, `interpretations` | Canonical | Source-write / Read-only | Typed wrappers for common entity kinds. Prefer them when they expose kind-specific options. |
| `graph` | Derived-state | Mixed | Build, validate, query, import, export, and inspect graph-derived state. |
| `graph add` | Exploratory | Generated-write | Direct graph mutation. Avoid for durable project knowledge because graph builds can overwrite these writes. |
| `dag` | Derived-state | Mixed | Render, number, validate, and audit DAG views. This is an older family-local surface and uses `--project` for project roots. |
| `belief` | Derived-state | Generated-write / Read-only | Belief snapshots and derived belief profiles. |
| `inquiry` | Canonical / specialized | Source-write / Read-only | Source-first inquiry patch profiles and causal inquiry exports. |
| `patch` | Derived-state | Read-only | Explain or check derived patch membership. |
| `validate`, `health`, `refs`, `prose`, `markers`, `search` | Canonical | Mixed | Project health, references, prose linting, annotation-token checks, and archive-index search. |
| `tasks` | Canonical | Source-write / Read-only | Project task lifecycle. `tasks fix-blockers` is migration-oriented. |
| `feedback`, `telemetry` | Specialized | Source-write / Read-only | Agent feedback records and local operational telemetry. |
| `explore-ideas` | Specialized | Source-write | Apply reviewed exploration report candidates into source-authored question and hypothesis entities. |
| `benchmark` | Specialized | Read-only | Benchmark metadata reports, opportunities, gaps, and test triage. |
| `annotate` | Specialized | Mixed | Annotation sidecars, prose decomposition, PubTator seeding, proposition reconciliation, promotion, and synthesis. |
| `verdict` | Specialized | Read-only | Parse and roll up verdict interpretation frontmatter. |
| `data` | Canonical | Mixed | Audit tracked-source vs payload data boundary. |
| `dataset` | Canonical | Source-write / Read-only | Local dataset entity lifecycle. |
| `datasets` | Specialized | Mixed | External dataset discovery, download, datapackage validation, schema inference, and QA. |
| `commons` | Specialized | External-write / Read-only | Shared commons store, overlays, promotion, and commons-born dataset packages. |
| `peers`, `sync` | Specialized | External-write / Read-only | Peer declarations and global cross-project registry sync. |
| `project`, `research-package`, `labnote` | Specialized | Generated-write / Read-only | Project bundles, verification, managed artifacts, research packages, and public app exports. |
| `curate`, `big-picture`, `wander`, `qa-audit` | Specialized | Read-only | Curation support, generated synthesis checks, serendipitous review queues, and advisory QA audits. |
| `bib`, `doi`, `paper`, `paper-fetch`, `book-split`, `distill` | Specialized | Mixed | Literature metadata, source text, book outlines, and public knowledge graph snapshots. |
| `entities` | Canonical / migration-only | Mixed | Inventory, archive, consolidation, migration, and local-kind registration. |
| `skills` | Specialized | Read-only | Skills tree linting. |

## Dataset Commands

Dataset-related command names encode distinct layers:

| Command | Use |
|---|---|
| `science data audit` | Check whether tracked source records and ignored payload data are separated correctly. |
| `science dataset ...` | Manage local dataset entity records under the Science entity lifecycle. |
| `science datasets ...` | Search external repositories, inspect/download files, validate datapackages, infer schema, run package-level QA, or hydrate worktree data. |
| `science commons dataset ...` | Build and validate commons-born dataset packages in the shared commons store. |

Use singular `dataset` when the subject is a Science dataset entity. Use plural
`datasets` when the subject is external discovery or datapackage-level tooling.

## Source-Authored vs Graph-Authored

Science treats the graph as a queryable view over authored project sources. For
durable work, create or edit source files:

```bash
science propositions create "..."
science evidence-lines create "..."
science entity create <kind> "..."
science graph build
```

Use `science graph add ...` only for exploratory graph surgery or a graph-level
experiment. Several `graph add` commands write directly to `knowledge/graph.trig`
and can be overwritten by the next `science graph build`.

## Generic Entity Commands vs Typed Wrappers

Use typed wrappers when they match the entity you are creating:

```bash
science questions create "..."
science hypotheses create "..."
science propositions create "..."
science evidence-lines create "..."
```

Use the generic command when working with a less common kind or when the
operation is generic:

```bash
science entity create <kind> "..."
science entity show <ref>
science entity edit <ref> --set status=active
science entity note <ref> "..."
```

The generic and typed authoring commands share the same source-file model. The
choice is ergonomic, not a separate data model.

## Annotation Workflow Shape

The `annotate` group is a full subsystem. Think of it as phases:

| Phase | Representative commands |
|---|---|
| Inspect and verify sidecars | `science annotate list`, `science annotate stats`, `science annotate verify` |
| Lift mechanical signals | `science annotate audit`, `science annotate lift-tokens` |
| Decompose and promote prose | `science annotate ingest-prose-decomposition`, `science annotate check-prose-decomposition`, `science annotate plan-prose-promotions`, `science annotate apply-prose-promotion-plan` |
| Seed and extract paper annotations | `science annotate pubtator`, `science annotate extract` |
| Promote statements | `science annotate promote`, `science annotate synthesize` |
| Reconcile propositions | `science annotate reconcile-propositions`, `science annotate validate-proposition-reconciliation`, `science annotate plan-proposition-reconciliation`, `science annotate apply-proposition-reconciliation` |
| Manage annotation state | `science annotate ack`, `science annotate dismiss`, `science annotate fix` |

The stable token vocabulary lives in
[`../conventions/annotation-tokens.md`](../conventions/annotation-tokens.md).

## Shared CLI Behavior

Prefer these conventions when adding or using commands. The durable convention
lives in [`../conventions/cli-behavior.md`](../conventions/cli-behavior.md).

- Read-only planning commands should say when they do not modify files.
- Mutating commands should make the write target clear: source files, generated
  files, the global registry, or the commons store.
- Risky mutations should use report-then-apply or dry-run/apply semantics.
- JSON output is for automation; table or text output is for human review.
- Prefer `--project-root` for commands that operate on a Science project root.
  Existing commands may still use shorter legacy names such as `--root`.
- Migration-only and exploratory commands should be labeled in docs and help
  text so agents do not select them for new durable workflows.

## Migration And Retired Surfaces

Migration-only commands are temporary. Retired commands are removed after the
registered project set no longer needs them; do not use command names from old
plans or audit notes as durable workflow guidance. For current project data,
prefer canonical authoring surfaces directly and run `science validate` plus
`science graph build` to catch retired fields.

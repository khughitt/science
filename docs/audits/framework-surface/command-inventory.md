# Command Inventory

## Method

Inventory was generated from the installed Click tree with a one-off Click
introspection script run through `rtk uv run --frozen --project science python`.

Source registration points were checked with:

```bash
rtk rg -n 'add_command|@main\.group|@main\.command|@.*\.group|@.*\.command' science/src/science_tool
```

## Totals

| Metric | Count |
|---|---:|
| Top-level commands | 46 |
| Command groups, including root | 48 |
| Leaf commands | 253 |
| Maximum command depth | 3 |

## Top-Level Shape

The top-level commands mix several categories:

| Category | Examples | Observation |
|---|---|---|
| Core source authoring | `entity`, `questions`, `hypotheses`, `propositions`, `evidence-lines`, `discussions`, `interpretations` | Canonical for day-to-day project work, but split between generic and typed wrappers. |
| Derived state and inspection | `graph`, `belief`, `health`, `validate`, `refs`, `prose`, `markers` | Strong core surface; documentation should clarify which commands write source, generated state, or reports. |
| Data and datasets | `data`, `dataset`, `datasets`, `data-package`, `commons dataset` | Highest naming ambiguity. Singular/plural distinction is documented in `docs/user-guide/entities.md`, but top-level help does not make the lifecycle boundaries obvious. |
| Annotation/prose workflows | `annotate`, `verdict`, `paper`, `paper-fetch`, `book-split` | Rich but specialized. `annotate` alone has 25 leaf commands and needs a workflow map. |
| Cross-project/federation | `peers`, `sync`, `commons`, `project`, `research-package`, `labnote` | Useful but conceptually adjacent. The user guide should state the order: local project first, peers/sync second, commons third. |
| Migration/legacy | `data-package`, parts of `graph add`, `entities migrate`, `tasks fix-blockers` | Necessary surfaces, but should be labeled as migration or exploratory so agents do not choose them for new durable work. |
| Agent support | `feedback`, `telemetry`, `skills`, `curate`, `big-picture`, `wander`, `qa-audit` | Valuable operational tooling, but partly hidden in workflow docs rather than in a command taxonomy. |

## Largest Command Families

| Family | Leaf commands | Notes |
|---|---:|---|
| `graph` | 30 direct leaves plus `graph add` with 15 more | Includes durable derived-state commands, query commands, migrations, imports, and direct graph mutation experiments. |
| `annotate` | 25 | Covers token lifting, prose decomposition, proposition reconciliation, PubTator seeding, extraction, promotion, synthesis, status transitions, and stats. |
| `tasks` | 14 | Cohesive operational task surface. Includes migration helper `fix-blockers`. |
| `commons` | 12 direct/grouped surfaces | Has internal grouping (`index`, `dataset`, `data`, `promote`, `reference-graph`) and is better structured than the root CLI. |
| `inquiry` | 12 | Source-first now, but still adjacent to graph and patch terminology. |
| `dataset` | 10 | Local dataset entity lifecycle. Needs sharper contrast with `datasets`. |
| `datasets` | 9 | External discovery/download/package QA surface. Needs sharper contrast with `dataset`. |
| `project artifacts` | 9 | Well-scoped managed-artifact lifecycle. |

## Naming And Semantics Risks

### `dataset` vs `datasets`

`docs/user-guide/entities.md` explains that singular `science dataset` is for
local dataset entity lifecycle, while plural `science datasets` is for external
dataset discovery, download, datapackage validation, schema inference, and QA.
This is reasonable, but the top-level CLI help presents both as peers:

- `dataset`: "Dataset entity lifecycle commands"
- `datasets`: "Dataset discovery and download commands"

The distinction is easy for a human to forget and easy for an agent to misuse.
The framework should either strengthen help text and docs, or introduce aliases
that make the lifecycle explicit.

### `data-package`

The legacy `science data-package` command has been retired from the active CLI.

### `graph add`

Several `graph add` commands warn that they write directly to `graph.trig` and
will be wiped on the next `science graph build`. That is a good warning, but the
command family remains prominent. The user guide already says durable project
knowledge should use source-authored entities instead. The command map should
label `graph add` as exploratory/manual graph surgery, not a normal authoring
path.

### `entity` vs typed plural wrappers

`science entity create <kind> <title>` is the generic authoring surface, while
typed wrappers such as `science questions create` and `science hypotheses create`
call the same writer path. This is good, but it creates two possible "right"
answers in agent workflows. The command map should define when wrappers are
preferred and when generic `entity` is preferred.

## Internal Organization Evidence

`science/src/science_tool/cli.py` is the largest Python file in the framework:

| File | Approx. lines |
|---|---:|
| `science/src/science_tool/cli.py` | 7,987 |
| `science/src/science_tool/commons/promote.py` | 3,544 |
| `science/src/science_tool/benchmark_opportunities.py` | 3,132 |
| `science/src/science_tool/annotation/cli.py` | 2,244 |
| `science/src/science_tool/graph/health.py` | 2,032 |
| `science/src/science_tool/graph/materialize.py` | 1,687 |
| `science/src/science_tool/entities.py` | 1,496 |
| `science/src/science_tool/entity_layout_migration.py` | 1,379 |
| `science/src/science_tool/commons/cli.py` | 1,197 |

This does not prove a defect by itself, but it does identify where future
changes will be most context-heavy. Existing split-out modules show the preferred
direction: move cohesive command families out of the root CLI only when their
domain logic and tests can move with them cleanly.

## Proposed Command Taxonomy

Use this taxonomy in documentation before changing commands:

| Status | Meaning |
|---|---|
| Canonical | Preferred for new durable Science work. |
| Specialized | Correct for a specific advanced workflow, but not part of the everyday path. |
| Derived-state | Reads or writes generated state; not an authoring source. |
| Migration-only | Exists to move old projects/data into the current model. |
| Exploratory | Useful for experiments or diagnostics, but not durable authoring. |
| Legacy | Kept for compatibility or cleanup; avoid in new workflows. |

Each top-level command family should get one status plus notes for exceptional
subcommands.

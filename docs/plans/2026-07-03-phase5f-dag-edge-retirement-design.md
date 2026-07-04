# Phase 5f Design: DAG Edge Retirement Default Surface

## Context

Phase 5 moved DAG edge authorship away from `doc/figures/dags/*.edges.yaml`
and toward relational propositions compiled from workbench rows. The current
code already marks `*.edges.yaml` as retired:

- `science_tool.dag.proposition_edges` projects compiled `PropositionEntity`
  records into channel-mode render edges.
- `science_tool.dag.schema.load_legacy_edges_yaml` emits a retirement warning
  on every parse.
- `science_tool.dag.render` can render proposition-sourced channel edges.
- `science_tool.dag.number` skips writing `*.edges.yaml` when proposition edges
  are supplied.

The retirement is incomplete. Several default workflows still discover, read,
validate, or write `*.edges.yaml`:

- `dag render` falls back to retired YAML when no proposition edges are loaded.
- `dag number` still creates or resets retired YAML stubs when no proposition
  edges are supplied.
- `dag validate` validates retired YAML files as the primary DAG object.
- `dag staleness` and `dag audit` compute edge drift from retired YAML refs.
- DAG inventory creates `dag-edge:<slug>:<id>` graph addresses from retired YAML.
- `dag init` still scaffolds a `.dot` plus `.edges.yaml` pair.
- User-facing docs still name `*.edges.yaml` as a structured input surface.

This creates warning noise and, more importantly, leaves a retired projection as
an operational source in normal command paths. Phase 5f finishes the default
surface migration: normal DAG commands must operate from compiled propositions
and DOT topology, not from `*.edges.yaml`.

## Goal

Make `*.edges.yaml` non-authoritative and non-default everywhere. Normal DAG
commands should not silently fall back to retired YAML. If a command needs
semantic edge data and no compiled proposition edge exists, it should fail
loudly with an actionable message.

Retired YAML may still be readable through one explicitly named migration /
inspection surface. That surface exists only to help authors find remaining
curation content that has not yet been moved into propositions, evidence lines,
or workbench rows.

## Non-goals

- Do not delete every `*.edges.yaml` fixture in the first implementation.
  Tests can keep retired YAML only where they exercise the explicit retired
  inspection path.
- Do not auto-convert every retired YAML edge into propositions. A future
  migration assistant can propose rows, but Phase 5f is about default command
  semantics.
- Do not add authored `edge_status` anywhere else. `edge_status` remains a
  derived compatibility projection over orthogonal channels.
- Do not wire belief aggregates into render-time proposition edges. The current
  proposition projection can keep its safe floor values; belief-enriched
  rendering is separate work.
- Do not preserve default behavior through another fallback path. Default paths
  should stop reading retired YAML.

## Approaches Considered

### A. Mute the warnings

Suppress or filter the retirement warnings while leaving fallback behavior
unchanged.

Rejected. This would reduce test noise but preserve the wrong source-of-truth
boundary. Retired YAML would remain an operational input.

### B. Hard delete the adapter

Remove `EdgesYamlFile`, `edges.schema.json`, all retired YAML fixtures, and every
YAML reader in one pass.

Rejected for Phase 5f. It is a clean final state, but too much migration
information still lives in old fixtures and downstream project files. We need an
explicit read path for auditing what remains.

### C. Staged default-surface retirement

Remove implicit YAML reads and writes from default commands. Keep a narrow,
explicit retired-edge inspection command for migration diagnostics.

Chosen. This removes the active epistemic ambiguity while keeping enough tooling
to inspect and migrate old content deliberately.

## Source Model

Default DAG commands use two sources:

1. DOT topology from `doc/figures/dags/<slug>.dot`.
2. Semantic edge records projected from compiled relational propositions via
   `load_proposition_edges(project_root)`.

The DOT file is the view topology. A relational proposition is the semantic
edge. The renderer matches proposition edges to DOT edges by `(subject, object)`.

`*.edges.yaml` is not consulted in this source model. If it is present beside a
DOT file, default commands ignore it. The existence of retired YAML should not
change output, validation results, inventory, or staleness reports.

## Command Behavior

### `science dag render`

Render discovers DAG slugs from DOT files or explicit config, not from
`*.edges.yaml`.

For each DOT edge, render expects at least one compiled proposition edge with
the same `(source, target)` pair. If no proposition edge exists for a DOT edge,
render fails before writing derived output. The error should name the DAG slug,
the missing DOT edge, and the likely fix: compile a workbench row or inspect
retired edges for migration content.

Retired YAML fallback is removed. A project with `foo.dot` and
`foo.edges.yaml`, but no compiled proposition edge for `foo.dot`, fails. It does
not render from `foo.edges.yaml`.

The fallback trigger changes, not just the fallback body. Today the legacy read
is selected on *emptiness*: `_source_proposition_edges` returns `None` when
`load_proposition_edges` yields an empty list, and `render_one` treats
`proposition_edges is None` as "load legacy YAML." Phase 5f retires that
sentinel collapse. A project with zero compiled relational propositions must hit
the actionable per-edge error, not silently fall back with only a
`DeprecationWarning`. "No propositions compiled" and "no proposition matches
this DOT edge" both fail loudly.

Discovery moves from a `*.edges.yaml` glob to a `*.dot` glob (or explicit
config). A DAG that has an `.edges.yaml` but no `.dot` sibling must not silently
vanish from discovery — the retired-edge inspection command reports it as an
orphan so migration can create the DOT topology.

### `science dag number`

Numbering remains a DOT-only operation. It writes `<slug>-numbered.dot` from the
DOT topology and never writes or resets `<slug>.edges.yaml`.

The `--force-stubs` option should be removed or converted into a hard error
with a migration message. Resetting retired edge curation is no longer a valid
normal operation.

### `science dag init`

Initialization creates only the DOT scaffold. It should not create an empty
`*.edges.yaml` sibling.

The next-step message should point authors to workbench/proposition authoring,
not to YAML stub generation.

### `science dag validate`

Validation becomes a DOT plus proposition-edge validation surface:

- DOT files must parse.
- DOT topology must be acyclic.
- DOT nodes should not be orphaned under strict mode.
- Every DOT edge in an active DAG must be backed by at least one compiled
  relational proposition with matching `(subject, object)`.
- A proposition edge that claims a migrated DAG identity via `legacy_patch` /
  `legacy_edge_id` must resolve to a real DOT edge if the referenced DOT exists.
- `*.edges.yaml` files are ignored by default validation.

The old YAML shape, JSON Schema, ref-list, posterior, `identification_missing`,
and `description_nonempty` checks move out of default validation. They can be
retained only under the explicit retired inspection path.

An active DAG is a requested or discovered DOT file: either the `--dag` target,
an explicit slug from project configuration, or a `doc/figures/dags/<slug>.dot`
file discovered by the command. Retired YAML files do not make a DAG active.

### `science dag staleness`

The current staleness algorithm is tied to retired YAML support lists and
`edge_status`. Phase 5f should stop running that algorithm in default mode.

In Phase 5f, `dag staleness` should fail with a clear "YAML edge staleness is
retired" message and point to the explicit retired-edge inspection command for
migration diagnostics. A future phase can introduce proposition-review
freshness as a separate design.

### `science dag audit`

Audit should no longer compose YAML validation, YAML staleness, or YAML-backed
task mutation. The normal audit path should be read-only and should compose:

- proposition-backed DAG validation;
- render regeneration from proposition edges;
- any non-YAML topology checks already available.

Note this is a wiring change, not only a deletion. `run_audit` currently calls
`render_all(paths)` with no `proposition_edges` argument, so audit's
regeneration always takes the retired-YAML fallback even when propositions
exist — unlike the `render` / `number` CLI paths, which already source
proposition edges. Phase 5f must thread `load_proposition_edges` into the audit
render path.

`--fix` should not open edge-review tasks from retired YAML drift. If retained,
it must only perform mutations backed by the new proposition-edge model.

### Inventory

`load_dag_inventory_records` should stop scanning retired YAML and stop
emitting `dag-edge:<slug>:<id>` addresses from it.

Claim-bearing inventory should come from propositions and evidence entities,
not from retired edge `interpretation`, `finding`, or `claim` fields. A DOT-only
view address such as `dag-view:<slug>` may be added later if needed, but Phase
5f does not need it to finish edge retirement.

### `science dag schema`

The `dag schema` subcommand serializes `EdgesYamlFile.model_json_schema()` — it
exists only to regenerate the retired `edges.schema.json`. Since the schema now
describes a retired surface, `dag schema` must not present itself as an active
authoring aid. Fold it under the retired-inspection surface: hide it from normal
help, or keep it only as a migration guard for the explicit inspection path, and
have it state that its output describes the retired YAML shape. It must not read
as the schema for a live DAG input.

## Explicit Retired-Edge Inspection

Add or reserve one explicit command for migration diagnostics, for example:

```bash
science dag retired-edges --project-root <project> [--dag <slug>] [--format table|json]
```

This command is the only normal CLI path that reads `*.edges.yaml`.

It should report:

- retired files found;
- edge counts by DAG;
- authored `edge_status` distribution;
- entries containing claim-bearing text (`interpretation`, `finding`, `claim`,
  `description`);
- support refs still present in `data_support`, `lit_support`, or
  `eliminated_by`;
- rows that look migration-worthy because they have curation content but no
  compiled proposition with the same `(source, target)`.

It must not make retired YAML authoritative. Its output is a migration report,
not a validation pass. It may parse with the existing retired YAML model, but
the command itself should state that the input is retired rather than relying on
warning spam.

### Implementation sequencing

The fail-loud defaults must not land before the migration debt is sized. The
whole reason to stage retirement (approach C) rather than hard-delete (approach
B) is that unmigrated curation still lives in downstream `.edges.yaml`
(`mm30`, `protein-landscape`, `natural-systems`). Ship `dag retired-edges`
first and run it across those real projects to quantify remaining content and
orphan YAML (edges files with no `.dot` sibling). Only then flip the default
render / validate / audit paths to fail loudly. Flipping first would break live
downstream DAG commands with no prior inventory of what they still depend on.

## Test Strategy

The implementation should first add RED tests that prove default commands do not
read retired YAML:

- `dag render` with both compiled proposition edges and a contradictory
  `.edges.yaml` renders from propositions and emits no YAML retirement warning.
- `dag render` with DOT plus only `.edges.yaml` fails instead of falling back.
- `dag number` writes numbered DOT and does not create `.edges.yaml`.
- `dag init` creates DOT only.
- `dag validate` flags a DOT edge with no matching proposition edge.
- `dag validate` ignores a malformed `.edges.yaml` when the DOT/proposition
  model is valid.
- inventory ignores `.edges.yaml` and emits no `dag-edge:` addresses from it.
- `dag retired-edges` reads retired YAML and reports its migration summary.

Existing YAML-heavy render/validate/number tests should be split:

- default command tests move to proposition-backed fixtures;
- retired YAML parser tests stay near the retired inspection command;
- schema tests stay only if the explicit inspection command still uses the
  schema as a migration guard.

The focused DAG test suite should pass without retirement warnings in default
command tests. Warning assertions should appear only in tests that deliberately
exercise the retired adapter.

## Documentation Updates

Update user-facing docs that still list `*.edges.yaml` as a normal input:

- `docs/user-guide/big-picture-synthesis.md`
- downstream project convention notes that describe DOT plus `edges.yaml` as the
  active DAG convention
- command help for `dag render`, `dag number`, `dag init`, `dag validate`,
  `dag staleness`, and `dag audit`

The new docs should say:

- DOT owns figure topology.
- Relational propositions own semantic edges.
- Workbenches are the editable projection for authoring proposition edges.
- `edge_status` is derived, not authored.
- `*.edges.yaml` is retired and only readable through explicit migration
  inspection.

## Acceptance Criteria

- Running normal DAG commands on proposition-backed fixtures produces no
  `*.edges.yaml` retirement warnings.
- A project with only `*.edges.yaml` semantic data fails loudly in default
  render/validate/audit paths.
- No default command writes a new `*.edges.yaml` file.
- `dag init` creates no `*.edges.yaml`.
- Inventory no longer creates `dag-edge:` addresses from retired YAML.
- The explicit retired-edge inspection command can still find and summarize
  remaining YAML curation content.
- A project with zero compiled propositions fails render loudly instead of
  silently falling back to retired YAML (the `None`/empty sentinel no longer
  selects the legacy read).
- A DAG with an `.edges.yaml` but no `.dot` sibling is reported as an orphan by
  the inspection command, not silently dropped from discovery.
- `dag audit` regenerates from proposition edges, not from the retired-YAML
  fallback.
- `dag schema` no longer presents itself as an active DAG input schema.
- User-facing docs no longer present `*.edges.yaml` as an active source of DAG
  truth.

## Follow-up Work

- A migration assistant can propose workbench rows from retired YAML records.
- Proposition-backed staleness can be redesigned around proposition source refs,
  evidence lines, and reviewed decision records.
- Render-time belief enrichment can add actual belief aggregate channels to
  proposition edges instead of the current safe floor values.
- Once retired inspection reports zero production content, the YAML schema and
  parser can be deleted.

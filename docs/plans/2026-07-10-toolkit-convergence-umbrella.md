# Toolkit Convergence — Umbrella

Date: 2026-07-10
Status: proposed

This note names a through-line found by an audit of `science/` and points at the
two design docs that act on it. It is an umbrella, not a plan.

## The finding

Nearly every structural problem in the toolkit is a **half-applied pattern**, not
a missing one. The right abstraction usually exists, is used in the easy cases,
and is bypassed in the hard ones:

| Canonical thing that exists | Adoption | Bypass |
|---|---|---|
| `output.emit_query_rows` | 55 call sites | 89 inline `== "json"` branches across 23 files; 37 hand-built `Table(` in `cli.py` |
| `science_model.frontmatter.parse_frontmatter` | 12 importing modules | 28 other non-test modules touch the `"---"`/`"---\n"` delimiter directly (70 sites); a namesake in `markdown_utils.py:205` returns a *different type* |
| `data_root.discover_project_root` | 1 call site | 4 other root-finders; 44 files reference `science.yaml` directly |
| `graph.health.HEALTH_CHECKS` registry | 16 checks | all 16 bodies inline in one 1,976-line file, vs 50 files under `validate/checks/` |
| `<domain>/cli.py` + `main.add_command` | 24 groups | 22 groups still inline in `cli.py` (7,386 lines) |

There is one place with **no** canonical form at all: entity **writing**. Twelve
modules independently re-emit the `---`/`yaml.safe_dump`/`---`/body sandwich —
enumerated structurally (`yaml.safe_dump` adjacent to a `---` literal), because
every hand-list drafted for the convergence spec undercounted by keying on one
delimiter spelling. `entities.py`, `datasets_identity.py`, `datasets_catalog.py`,
`datasets_register.py`, `commons/promote.py`,
`commons/reference_graph_promotion.py`, `commons/dataset_lifecycle.py`,
`dag/workbench_apply.py`, `annotation/source_text.py`, `graph/decision_log.py`,
`cli.py`, and `model/templates.py`.

## Why the patterns decayed

Nothing stopped the next author from hand-rolling. Each canonical helper is a
convention, not a constraint. Fixing the call sites without adding a constraint
resets the clock rather than stopping it.

## The response: canonicalize → migrate → guard

The kernel-closure work already established this repo's answer. It did not merely
delete competing `graph.trig` writers; it added
`tests/graph/test_durable_write_boundary.py`, an AST guard that fails when a new
writer appears, and `tests/test_store_package_structure.py`, a structural guard.
Both design docs below adopt that three-beat shape. **A phase that migrates call
sites without landing its guard is not done.** The one exception is a pure
deletion, which has no call site left to regrow — the convergence track's Phase 0
ships an abandonment ledger instead, and is numbered 0 to mark it as outside the
invariant.

Two rules learned the hard way, both from review of this doc's first draft:

- **Write the guard against the migrated tree, not against the design doc.** A
  guard drafted from prose reliably out-scopes its migration and lands red.
- **Guards must key on structure, not on text shape.** A guard that greps for
  `graph.trig` misses `root / DEFAULT_GRAPH_PATH`; a guard that greps for
  `json.dumps` misses `_json.dumps`. Both bypasses already exist in the tree.

## The two tracks

They are separated because they have different risk profiles and want different
reviewers.

- **[Half-applied pattern convergence](2026-07-10-half-applied-pattern-convergence-design.md)**
  — mechanical, high-volume, concept-preserving. Deletes dead code, canonicalizes
  the leaf primitives, then extracts the CLI. Changes no concepts; removes several
  thousand lines.

- **[Patch as a first-class object](2026-07-10-patch-first-class-model-alignment-design.md)**
  — conceptual, low-volume. Gives the working model's central noun a single home
  in the schema layer, hoists domain vocabulary out of emission code, and repairs
  the layering faults that currently make that impossible.

The two tracks share no prerequisite in either direction. The convergence track's
frontmatter work (its Phase 2) is needed by nothing in the model track, and the
model track's layering repairs (its Phases 1–2) are needed by nothing in
convergence. Run them in either order, or concurrently.

## What the audit did *not* find

Three claims that would have been reasonable to expect, and are false:

- **`benchmark_opportunities.py` (4,239 lines) is not a cohesion problem.** It is
  a pure functional core with a ~3% I/O rim and zero rendering. It is merely
  large. Splitting it is optional and low-value; it is scheduled last, and may be
  dropped.
- **`science_tool/model/` is not dead code.** It has no in-repo importer by
  design. It is a public surface consumed by the `meta` project (D-007, three
  interpretations) and by pan-disease's `h00_patch_demo.py`. It must not be
  deleted; it needs an export test so it cannot rot silently.
- **The two `entities.py` files are a principled split**, not duplication.
  `science_model/entities.py` owns the Pydantic data model;
  `science_tool/entities.py` owns on-disk path policy, id/slug rules, and file
  CRUD. The only leak is that the latter re-implements serialization instead of
  using the former's.

## Confirmed dead code

`plan_gate.py` (196 lines) and `synthesis_payload.py` (324 lines) have tests and
design docs but zero production importers anywhere in `src/`, `model/`, or
`scripts/`. Note `codex_skills.py` looks identical but *is* live — it is imported
by `scripts/generate_codex_skills.py`.

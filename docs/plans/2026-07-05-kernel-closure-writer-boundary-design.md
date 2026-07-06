# Kernel Closure Design: Durable-Writer Boundary

Date: 2026-07-05

## 1. Context

The patchwork-kernel architecture
([`docs/plans/historical/2026-06-14-patchwork-kernel-architecture-design.md`](historical/2026-06-14-patchwork-kernel-architecture-design.md))
defines the target as "the existing Science direction with the keystone
primitives made explicit and the parallel copies removed." The four load-bearing
keystones are done: Kind Descriptor (Spec 2), Source Compiler (Spec 3), Patch
Contract (Spec 4), and Proposition/Evidence/Belief semantics (Spec 5). The
Phase 5f–5k retired-edge arc delivered proposition-as-edge and retired
`*.edges.yaml` as an epistemic source.

What remains before the kernel can be declared closed is the last band of
"parallel copies removed": several code paths still write authoritative graph
state directly, bypassing the source-declaration → `science graph build`
pipeline that is supposed to be the only durable write path. The invariant is
documented but not enforced, which is why the surface accreted ~29 direct
writers.

North-star success criteria this work closes
(from the kernel architecture doc):

- "no CLI, workbench, renderer, or cache path can write authoritative belief,
  identity, or patch membership outside the compiler-owned source path";
- "legacy views such as DAG edge status can still be generated without becoming
  source-of-truth";
- "patch and inquiry-style neighborhoods use one patch contract rather than two
  independent named-graph abstractions" (the `sci:Inquiry` compat view).

## 2. Goal

Make the durable-write boundary **enforceable, not merely documented**. After
this work:

- Source declarations (markdown entity files + manifests) are the only durable
  write path for authoritative graph, identity, and patch state.
- `science graph build` / materialize is the single owner of
  `knowledge/graph.trig`; `graph/composite.py` is the single owner of
  `knowledge/composite.trig`.
- Every other writer is either retired, or explicitly classified as
  bootstrap/cache/scratch and named in an allowlist.
- A guard test fails the build if any disallowed module writes the durable
  graph, so the boundary cannot silently regrow.

## 3. Non-Goals

- Do not repoint `sci:Inquiry` consumers in the cleanup sweep. That is real
  design work with six-plus live readers and belongs in its own later phase
  (Section 8, Phase 4).
- Do not open Spec 6 (provenance/agents) or full Spec 7 (federation) here. A
  scoped scope/identity audit may follow if commons/benchmark usage keeps
  surfacing identity pain, but not as part of this boundary work.
- Do not change belief, materialize output, or any derived view. This is a
  write-path boundary cleanup; the compiled graph is behavior-neutral.
- Do not preserve retired mutators behind a compatibility shim. Retirement uses
  the existing `_retired_mutator` pattern (a hard, actionable error), not a
  silent fallback.

## 4. The Writer Inventory

All paths relative to `science/src/science_tool/`. Every direct writer bottoms
out in `_save_dataset(dataset, graph_path)` → `knowledge/graph.trig`
(`graph/store/dataset.py`).

### Legitimate durable writers (the allowlist)

- **Compiler durable write**: `graph/materialize.py` write phase
  (`build_dataset_from_sources` → `_write_phase` → `save_graph_dataset`). Sole
  owner of `graph.trig`.
- **Derived projection write**: `graph/composite.py` `assemble_composite_graph`
  → `knowledge/composite.trig` (composite.py:35). Sole owner of `composite.trig`.
- **Bootstrap/scaffold (named)**: `init_graph_file` (`graph/store/dataset.py`),
  notebook scaffolding (`graph/store/notebooks.py`), belief-snapshot cache
  (`graph/belief_snapshot.py`). Allowed only because explicitly named.

### Tier 1 — repo-dead / CLI-orphaned (retire now)

The CLI is already retired for these; only tests keep them reachable.

| function | location | exposure |
|---|---|---|
| `add_data_package` | `graph/store/mutations.py:1016` | fully dead; not in top-level `graph.__all__` |
| `add_inquiry` | `mutations.py:813` | `graph.store` only |
| `add_inquiry_node` | `mutations.py:878` | `graph.store` only |
| `add_inquiry_edge` | `mutations.py:906` | `graph.store` only |
| `set_boundary_role` | `mutations.py:852` | `graph.store` only |
| `add_assumption` | `mutations.py:950` | `graph.store` only |
| `add_transformation` | `mutations.py:976` | `graph.store` only |
| `set_param_metadata` | `mutations.py:1039` | `graph.store` only |
| `set_treatment_outcome` | `graph/store/inquiry.py:177` | `graph.store` only |

Their CLI commands already `raise _retired_mutator(slug)` (`cli.py:3013`,
raised at 3186/3207/3219/3231/3243), pointing users to edit
`entities/patches/<slug>.md` and run `science graph build`. No production
consumer breaks; only `tests/test_inquiry.py`, `tests/test_causal.py`,
`tests/test_graph_export.py`, and `tests/test_meta_reference.py` import them.

### Tier 2 — live `graph add *` entity mutators (retire via migration)

Fifteen live subcommands under `graph_add` (`cli.py:2361`), all writing
non-durable graph state, but only six admitting it in a warning:

`add_proposition`, `add_observation`, `add_evidence_edge`, `add_finding`,
`add_story`, `add_paper_entity` **warn**; `add_concept`, `add_article`,
`add_hypothesis`, `add_question`, `add_edge`, `add_interpretation`,
`add_discussion`, `add_falsification`, `add_mechanism` mutate **silently**.

Most are re-exported in `graph/__init__.py` `__all__`, so their removal is an
internal-API change (Section 6).

`add_edge` is the special case: it may have **no one-to-one source-authoring
command** (arbitrary predicate between arbitrary entities). It must either become
an explicitly scratch/debug surface or be retired outright — not silently
migrated.

### Tier 3 — other direct writers needing an explicit call

| writer | location | disposition |
|---|---|---|
| `migrate_addresses_direction` (`graph migrate-addresses --apply`) | `mutations.py:772` | completed one-shot migration; retire or quarantine as a named build tool |
| `import_snapshot` (`graph import`) | `graph/store/snapshot.py` | writes raw knowledge triples with **no backing source**; reclassify as an explicit import-provenance path or retire |
| `stamp_revision` (`graph stamp-revision`) | `graph/store/snapshot.py` | low-risk metadata-only writer; classify as named build tool or retire |

Both `import_snapshot` and `stamp_revision` are in top-level `graph.__all__`.

### Tier 4 — `sci:Inquiry` compatibility view (own phase)

Emitted at `graph/inquiry_compile.py:88` inside `emit_inquiry_views`, called
only from the compiler (`graph/materialize.py`). Retiring the emission is
**blocked** on repointing live readers — at least: `inquiry show/list/validate`
(`graph/store/inquiry.py:44`), causal exports (`causal/export_pgmpy.py:268`,
`causal/export_chirho.py:68`), `graph inquiry-summary`
(`graph/store/summary.py:611,699`), the validate check
(`validate/checks/graph.py:237`), and probable graph-export / viz-template
adjacency (`graph/store/export.py:321`). Each must read
`PatchDefinitionEntity.inquiry` profiles directly before the emission can drop.

## 5. The Guard Test (keystone)

The enforcement mechanism, matching how the repo already build-gates the
convenience-edge and entity-scan invariants. Phrased as an allowlist over
production code (tests excluded):

- **Allowed durable graph write**: `graph/materialize.py` write phase.
- **Allowed derived projection write**: `graph/composite.py` →
  `knowledge/composite.trig`.
- **Allowed bootstrap/scratch, only if explicitly named**: `init_graph_file`,
  notebook scaffolding, belief-snapshot cache, and any command deliberately
  classified as scratch/debug.
- **Disallowed**: any `_save_dataset` / `save_graph_dataset` call reachable from
  `graph/store/mutations.py`, `graph/store/inquiry.py`, `graph/store/snapshot.py`,
  or a CLI mutation path.

Implementation options (decided in the Phase 1 plan): a static AST/import check
over the named modules, or a runtime guard that asserts the caller module of
`save_graph_dataset` is in the allowlist. The static form is preferred — it
cannot be bypassed at runtime and reads as documentation. The allowlist is data,
so classifying a new scratch command is a one-line, reviewed change.

## 6. Internal-API Cleanup Framing

`science_tool.graph` and `science_tool.graph.store` re-export many mutators via
`__all__` (e.g. `add_proposition`, `add_edge`, `import_snapshot`,
`stamp_revision`). The supported product surface is the `science` CLI, not
`import science_tool` — `science_tool` is an internal implementation package.
This work therefore treats mutator removal as an **internal-API cleanup**, with
two required guards per phase:

1. **External-importer preflight**: grep sibling repos that might import the
   package (`~/d/science-commons`, the `meta/` project, any project that imports
   `science_tool` rather than shelling out to the CLI) for the names being
   removed. If an external importer exists, the phase escalates to a documented
   breaking change with a deprecation note; if not, deletion is clean.
2. **Same-commit `__all__` pruning**: every removed name is dropped from
   `graph/__init__.py` and `graph/store/__init__.py` `__all__` in the same
   change, so the exported surface never lists a missing symbol.

## 7. Test-Migration Strategy

Tier 1 deletion requires rewriting four test files that construct graph state
through the retired mutators. `tests/test_causal.py` in particular has
substantial setup built on `add_inquiry*` / `set_treatment_outcome`.

To keep the rewrite centralized rather than hand-converting dozens of call
sites, add one shared fixture/helper that authors a `PatchDefinitionEntity`
inquiry source (`entities/patches/<slug>.md`) and runs `graph build` /
`materialize_graph`, returning the materialized dataset. Tests then assert
against the honestly-compiled graph — the same path users take — instead of a
runtime-mutated one. This converts the test debt into coverage of the real
source→build pipeline.

## 8. Phased Sequence

1. **Tier 1 + writer-boundary guard.** Delete the dead/orphaned writers, land the
   centralized inquiry-source test fixture, migrate the four test files, prune
   `__all__`, and add the guard test. The guard immediately freezes the boundary
   at its post-Tier-1 state so nothing regrows while Tier 2 proceeds.
2. **Global retired-edge debt sweep.** Independent of Tier 2 — can run
   immediately after Phase 1 or in parallel. Audit every managed project for
   active (non-closed) `*.edges.yaml` files so the "edges.yaml retired" criterion
   holds project-wide, not just for `protein-landscape`. Uses the Phase 5g–5k
   surface; queues per-project migrations individually.
3. **Tier 2 `graph add` retirement + Tier 3 decisions.** Retire the 15 mutators
   via the `_retired_mutator` pattern (after confirming each kind has a
   source-authoring path; `add_edge` gets its explicit scratch-or-retire call),
   and resolve `migrate_addresses_direction`, `import_snapshot`, and
   `stamp_revision` per Tier 3. Each retirement extends the guard allowlist's
   disallowed set.
4. **`sci:Inquiry` consumer repoint.** Its own phase. Repoint the six-plus live
   readers to `PatchDefinitionEntity.inquiry` profiles, then drop
   `emit_inquiry_views` and the `sci:Inquiry` emission.

## 9. Approaches Considered

### A. Enforce the boundary with a guard, retire incrementally

Chosen. A single static guard test makes the invariant executable; retirement
then proceeds tier by tier behind it. Each phase is independently shippable and
behavior-neutral for the compiled graph.

### B. One big-bang removal of all direct writers

Rejected. The 15 `graph add` commands are live CLI surface and `sci:Inquiry` has
live readers; removing everything at once couples an internal cleanup to a
user-facing CLI change and a consumer rewrite, with no intermediate safe state.

### C. Document the invariant without enforcement

Rejected. This is the current state and is exactly why 29 writers accreted. The
value of this work is the guard, not the enumeration.

## 10. Success Criteria

- The guard test fails if any disallowed module writes `graph.trig`.
- `add_data_package` and the orphaned inquiry mutators are gone; the four test
  files build state through the source→`graph build` fixture.
- The 15 `graph add` mutators are retired (or, for `add_edge`, explicitly
  scratch-classified); no removed name remains in any `__all__`.
- `migrate_addresses_direction`, `import_snapshot`, and `stamp_revision` each
  carry an explicit classification (named build tool, import-provenance path, or
  retired).
- Every managed project's `*.edges.yaml` debt is either closed-and-archived or
  queued with a per-project migration.
- The compiled `graph.trig` and `composite.trig` are byte-identical before and
  after each phase (behavior-neutral).
- `sci:Inquiry` retirement is scoped to its own phase with a live-reader
  repoint, not bundled into the sweep.

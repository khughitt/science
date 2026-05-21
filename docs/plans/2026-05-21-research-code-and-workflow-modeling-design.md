# Research code & workflow modeling — umbrella design

**Status:** design
**Date:** 2026-05-21
**Scope:** parent / umbrella design for three coupled sub-specs (Spec 1 = A+B, Spec 2 = C)
**Informed by:** MM30 reproducibility remediation (`~/d/cancer/cancer-types/multiple-myeloma`) and the natural-systems code-as-entity exporter (`~/d/natural-systems`)

---

## 1. Goal

Make research code **first-class** in science. Every research code artifact is a registered science entity, bound to the workflow structure that runs it, so that provenance and uncertainty propagate from a code change all the way through to the findings that depend on it. Be opinionated about organization and metadata; leave workflow *execution*, dependency resolution, and scheduling to the underlying engine.

The concrete failure this addresses: a finding's reasoning is only as trustworthy as our ability to enumerate everything upstream of it. Today, decision-bearing scripts and datasets routinely live *outside* the reproducible pipeline, unregistered and unlinked, so the upstream set is silently incomplete.

**Program scope:** three coupled sub-specs, sequenced foundation-first.

- **Spec 1 (A + B)** — code-entity model & topology, plus registration & validation.
- **Spec 2 (C)** — the workflow adapter/backend that binds the real DAG to the graph.

**Non-goals (program level):**

- Rewriting science's epistemic engine. `bears_on`, freshness, `evidence_payload`, and typed relations already exist and are reused as-is.
- Commons promotion of *reusable cross-project workflows*. A workflow that multiple projects share could someday get a promotion path via the JSON-schema mixin layer; that is a deferred, separate question.
- Workflow backends beyond Snakemake in v1. The adapter is designed for extensibility, but only Snakemake ships first.
- Fixing the unresolved-reference hard-fail brittleness in `graph materialize`. Related and worth doing, but out of scope here (see §9).

---

## 2. Context & motivation

**What science has today.** The `workflow` / `workflow-run` / `workflow-step` entity kinds already exist and are classed `OPERATIONAL` (they carry no continuous belief). The `evidence_payload` schema already ships `ValidationRole.prioritize-attention` and a `PropagationPolicy` enum, and the `bears_on` freshness engine already propagates `needs-review` across epistemic dependencies. The gaps are narrower than they look:

- **No enforcement that code maps to entities.** Code↔task linkage is explicitly documentation-only and non-enforced (`2026-04-25-code-task-backlink-convention.md`).
- **No filesystem-orphan detection.** `validate/checks/directory_structure.py` checks that directories *exist* and warns on legacy roots, but never walks the code tree to flag files lacking metadata. The existing "orphaned" check is graph-node-level, not filesystem-level.
- **Code↔graph links are free text.** MM30 writes `workflow_run: "opentargets_all / ..."` as an unresolved string, not a resolved edge.
- **Topology rides on the wrong axis.** `code/` vs `src/` is selected by the legacy `profile: research|software` enum (`paths.py`), while the aspects system (`computational-analysis`, `software-development`) is orthogonal and only injects doc sections.

**Convergent evolution downstream.** Two projects independently built most of what this program proposes, and neither pushed it upstream:

- **MM30** built `MM30_SCRIPT_METADATA` (a per-file comment block: `task_ids`, `workflow`, `decision_bearing`, `status`) and `script_workflow_audit.py` (classification, orphan/hardcoded-path/metadata-gap detection, a `--fail-on` ladder, and hard-won Snakemake path-indirection parsing). Current state: 172 orphaned executables, 393 metadata gaps, 535 hardcoded-path findings; only 2 of 565 scripts carry the block.
- **natural-systems** built a working code-as-entity chain — `analysis → workflow → data_package → web_route` (37 `analysis:` entities carrying `script_path` + `sci:implements`, 20 `workflow:` entities) — materialized by `export_kg_model_sources.py`. But 54 one-off scripts remain unregistered, and `pipeline/` (hand-run task outputs) coexists with `workflows/` (Snakemake).

The program's job is therefore to **reconcile two proven prototypes into one opinionated model**, not to invent one.

---

## 3. Locked decisions

These constrain all three sub-specs and are settled by this umbrella.

1. **Binding — co-located in the code file.** The authored source of truth for an artifact's entity metadata is a block at the top of the file (generalizing MM30's `MM30_SCRIPT_METADATA`). Walking the tree directly yields ghost detection: a file with no valid block *is* the violation. Graph entities are materialized from these blocks.
2. **Topology — explicit roots in `science.yaml`.** A declaration (e.g. `code_roots` / `app_roots`) makes topology data rather than inference, resolving the legacy-profile inconsistency.
3. **Enforcement — staged, default-on, non-gating first.** A `--fail-on` ladder (§6) that defaults to report-only on adoption; projects advance the gate explicitly.
4. **Schema layer — pydantic first-class entity model.** Code entities extend `EntityType` like the existing workflow kinds, *not* the JSON-schema mixin/commons layer (which is the dataset/paper/topic/theme promotion path).
5. **Harvest, don't clean-room.** B generalizes MM30's metadata block + auditor; A and C generalize NS's entity chain + exporter. **MM30 and NS are the two acceptance tests** — the design is not done until both migrate cleanly and delete their bespoke machinery.
6. **Sequencing — foundation-first.** A and B ship as one spec (the schema is meaningless without the walk and vice versa); C is designed afterward on a model already proven by the migrations.
7. **Lifecycle — status-driven, not directory-driven.** Stage lives in a `status` field, not a dedicated directory.
8. **Dataset logical role — emergent, not declared.** input/intermediate/result is derived from `origin` + `consumed_by` + DAG position, never an enum.

---

## 4. Conceptual model

**Principle:** every file under a declared code root is a registered science entity. No ghosts. A code artifact's identity, purpose, lifecycle, and bindings to the rest of the graph are declared in its co-located metadata block; validation walks the roots, and a file without a valid block is the violation.

**Code entities are OPERATIONAL conduits of provenance.** Like the existing workflow kinds, they carry no continuous belief. Their value is sitting on the paths that propagate belief and uncertainty to epistemic entities. The target chain, once resolved:

```
code-file --implements--> workflow-step --(part of)--> workflow
workflow-run --executes--> workflow --produces--> dataset (derived)
dataset --consumed_by--> ... --> finding / proposition   (bears_on)
```

**The epistemic half already works.** Once that chain resolves, science's existing `bears_on`/freshness engine does the rest: edit a code file → its workflow-step → its run → the dataset it produced → any finding that bears on that dataset flips to `needs-review`. The missing piece is rigorously wiring `code → run → dataset` as resolved edges instead of free text — which is precisely what the adapter (C) exists to do.

**Reconciling the three sources:**

- MM30's per-file comment block → the co-located metadata schema (B).
- NS's `analysis → workflow → data_package → web_route` chain → the materialized graph shape (A's taxonomy & relations, C's materialization).
- science's existing kinds + `evidence_payload` + `bears_on` → the substrate everything plugs into.

Exact type names (e.g. `code-file` vs `script`), the relation vocabulary additions (generalizing `sci:implements`), and how a Snakefile is simultaneously a code-file *and* a workflow definition are deferred to Spec 1/A.

---

## 5. Decomposition & roadmap

### Spec 1 = A + B (model + enforcement, one unit)

**A — model & topology**

- The code-entity kind(s) and their required/optional fields.
- The relation vocabulary (`implements`, `defines`, …) generalizing NS's `sci:implements`.
- How a Snakefile is both a code-file and a workflow definition (relations, not duplication).
- The `code_roots` / `app_roots` declaration in `science.yaml`.
- Which existing kinds (`workflow`, `workflow-step`, `workflow-run`) get enriched.

**B — registration & validation**

- The co-located block format and parser.
- The tree-walk `@Check` integrated into the existing validation runner.
- Classification (workflow-owned / orphaned / library / test / package-marker), generalizing MM30's auditor and its Snakemake path-indirection parsing.
- Ghost detection; hardcoded-path and metadata-gap detection.
- The staged `--fail-on` ladder wired into the runner.

### Spec 2 = C (workflow adapter / backend)

- A backend protocol (Snakemake first) that extracts the real DAG.
- Materialization of `workflow-run --executes--> workflow --produces--> dataset` and `code-file --implements--> workflow-step` as resolved edges.
- The uncertainty-propagation wiring that lights up once the chain resolves.
- Second-backend extensibility (interface only; no second backend in v1).

**Dependency:** C is designed only after A's model has survived the MM30 + NS migrations (§7).

---

## 6. Cross-cutting policies

### Enforcement ladder

| Tier | Gate | Rationale |
|------|------|-----------|
| 0 | report only | baseline; never blocks |
| 1 | **ghost files** (file in a code root with no/invalid block) | cheapest, most defensible — the core "no orphans" guarantee |
| 2 | decision-bearing orphans (executable, decision-bearing, unreachable from a workflow) | the reproducibility guarantee |
| 3 | hardcoded paths / metadata completeness | hygiene, last |

The default entry point is **Tier 0 (report)**, so adopting the system never breaks an existing project on day one; greenfield projects can opt straight to Tier 1, and every project advances the ladder explicitly in `science.yaml`. **Fail-closed:** an un-annotated executable is *treated as* decision-bearing — its output could feed a claim, finding, report, figure, or task closure — until a human downgrades it.

### Lifecycle vocabulary

Generalizing MM30's `status`: `exploratory`, `workflow-owned`, `library`, `retired`.

`exploratory` is the pressure-release valve. Prototype code is **exempt from workflow-ownership gating (Tier 2) but never from registration (Tier 1)** — so quick exploration is fast to author yet never a ghost, and is visibly flagged as not-yet-reproducible. Lifecycle is status-driven: a `code/exploratory/` directory is *allowed* but not required, because the status already carries the signal and a dedicated directory only creates churn when code graduates.

### Dataset logical role — emergent

input / intermediate / result is computed from `origin` + `consumed_by` + DAG position, not declared. Examples: `origin: external` with nothing producing it ⇒ input; `origin: derived` with non-empty `consumed_by` ⇒ intermediate; `origin: derived` with nothing consuming it ⇒ result. Declaring it would duplicate, and risk contradicting, the graph.

### Fragility firewall

A single unresolved reference currently hard-fails the *entire* `graph materialize`. Code-registration findings must therefore travel as validation `Result`s (severity-tagged, gateable via the ladder), **not** as materialization preconditions. This is *why* B is a `@Check` rather than a materialize-time hard-fail: requiring registration must not widen the build-blocking surface.

---

## 7. Migration story (the acceptance tests)

**MM30.** Map `MM30_SCRIPT_METADATA` → the science block (near 1:1, mostly mechanical); delete `script_workflow_audit.py` in favor of the science check; triage the 172 orphans / 393 gaps using the lifecycle vocabulary; retire the `legacy_dirs_allowlist` entry for `scripts/` by declaring it a code root (or migrating to `code/`). MM30's in-flight remediation plan becomes a *consumer* of the science feature rather than bespoke work.

**natural-systems.** Replace `export_kg_model_sources.py`'s code-entity emission with co-located blocks materialized by science; register the 54 unregistered one-off scripts (`exploratory`, or migrate into a workflow); the `analysis → workflow → data_package` chain becomes the standard shape.

The design is complete only when both projects migrate cleanly and delete their parallel machinery.

---

## 8. Deferred to sub-specs (not decided here)

- **A:** exact entity type names and full field lists; the relation-vocabulary additions; the Snakefile-as-both-code-file-and-workflow model; the precise `science.yaml` roots grammar.
- **B:** validator classification heuristics; the port of MM30's Snakemake path-indirection parsing; merge-preserving triage tables (machine-owned vs reviewer-owned columns).
- **C:** the backend protocol interface; DAG-extraction mechanics; the exact uncertainty-propagation wiring; second-backend extensibility.

---

## 9. Related, but out of scope

- **Unresolved-reference brittleness.** `graph materialize` hard-fails on a single unresolved reference, with no short-form aliasing (`Q01`, `t35`). The §6 fragility firewall *routes around* this; it does not fix it. A separate effort should make resolution staged/aliased.
- **Commons promotion of reusable workflows.** When a workflow is genuinely shared across projects, it may warrant a JSON-schema mixin promotion path. Deferred until a concrete cross-project workflow exists.

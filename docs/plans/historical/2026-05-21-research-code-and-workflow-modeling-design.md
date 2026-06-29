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
- **Spec 2 (C)** — the artifact-level **provenance propagation contract**: a first-class `produced_by` edge from a data artifact to the decision-bearing code that produced it, deriving `bears_on` so a code change reaches downstream findings. Engine-agnostic; workflow-DAG binding is demoted to a deferred, optional accelerant (§5).

**Non-goals (program level):**

- Rewriting science's epistemic engine. `bears_on`, freshness, `evidence_payload`, and typed relations already exist and are reused as-is.
- Commons promotion of *reusable cross-project workflows*. A workflow that multiple projects share could someday get a promotion path via the JSON-schema mixin layer; that is a deferred, separate question.
- Workflow-DAG extraction in Spec 2 v1. The epistemic propagation contract is engine-agnostic and authored at the artifact. Binding a workflow engine's DAG (Snakemake first) is demoted to a deferred, optional adapter that *populates* the `produced_by` edge for engine-managed artifacts — the propagation guarantee never depends on it (§5).
- Fixing the unresolved-reference hard-fail brittleness in `graph materialize`. Related and worth doing, but out of scope here (see §9).

---

## 2. Context & motivation

**What science has today.** The `workflow` / `workflow-run` / `workflow-step` entity kinds already exist and are classed `OPERATIONAL` (they carry no continuous belief). The `evidence_payload` schema already ships `ValidationRole.prioritize-attention` and a `PropagationPolicy` enum, and the `bears_on` freshness engine already propagates `needs-review` across epistemic dependencies. The gaps are narrower than they look:

- **No enforcement that code maps to entities.** Code↔task linkage is explicitly documentation-only and non-enforced (`2026-04-25-code-task-backlink-convention.md`).
- **No filesystem-orphan detection.** `validate/checks/directory_structure.py` checks that directories *exist* and warns on legacy roots, but never walks the code tree to flag files lacking metadata. The existing "orphaned" check is graph-node-level, not filesystem-level.
- **Code↔graph links are free text.** MM30 writes `workflow_run: "opentargets_all / ..."` as an unresolved string, not a resolved edge.
- **Topology rides on the wrong axis.** `code/` vs `src/` is selected by the legacy `profile: research|software` enum (`paths.py`), while the aspects system (`computational-analysis`, `software-development`) is orthogonal and only injects doc sections.

**Convergent evolution downstream.** Two projects independently built most of what this program proposes, and neither pushed it upstream:

- **MM30** built `MM30_SCRIPT_METADATA` (a per-file comment block: `task_ids`, `workflow`, `decision_bearing`, `status`) and `script_workflow_audit.py` (classification, orphan/hardcoded-path/metadata-gap detection, a `--fail-on` ladder, and hard-won Snakemake path-indirection parsing). Current state: 172 orphaned executables, 393 metadata gaps, 535 hardcoded-path findings; only 2 of 566 scripts carry the block.
- **natural-systems** built a working code-as-entity chain — `analysis → workflow → data_package → web_route` (37 `analysis:` entities carrying `script_path` + `sci:implements`, 20 `workflow:` entities) — materialized by `export_kg_model_sources.py`. But 54 one-off scripts remain unregistered, and `pipeline/` (hand-run task outputs) coexists with `workflows/` (Snakemake).

The program's job is therefore to **reconcile two proven prototypes into one opinionated model**, not to invent one.

---

## 3. Locked decisions

These constrain all three sub-specs and are settled by this umbrella.

1. **Binding — co-located in the code file.** The authored source of truth for an artifact's entity metadata is a block at the top of the file (generalizing MM30's `MM30_SCRIPT_METADATA`). Walking the tree directly yields ghost detection: a code artifact with no valid block *is* the violation (bounded by decision 10). Graph entities are materialized from these blocks.
2. **Topology — explicit roots in `science.yaml`.** A declaration (e.g. `code_roots` / `app_roots`) makes topology data rather than inference, resolving the legacy-profile inconsistency.
3. **Enforcement — staged, default-on, non-gating first.** A `--fail-on` ladder (§6) that defaults to report-only on adoption; projects advance the gate explicitly.
4. **Schema layer — pydantic first-class entity model.** Code entities extend `EntityType` like the existing workflow kinds, *not* the JSON-schema mixin/commons layer (which is the dataset/paper/topic/theme promotion path).
5. **Harvest, don't clean-room.** B generalizes MM30's metadata block + auditor; A and C generalize NS's entity chain + exporter. **MM30 and NS are the two acceptance tests** — the design is not done until both migrate cleanly and delete their bespoke machinery.
6. **Sequencing — foundation-first.** A and B ship as one spec (the schema is meaningless without the walk and vice versa); C is designed afterward on a model already proven by the migrations.
7. **Lifecycle — status-driven, not directory-driven.** Stage lives in a `status` field, not a dedicated directory.
8. **Dataset logical role — emergent, not declared.** input/intermediate/result is derived from `origin` + `consumed_by` + DAG position, never an enum.
9. **Change propagation — content-derived signal + explicit closure contract.** For a code edit to actually reach a downstream finding, two things must hold, and the umbrella locks both. (a) Code entities derive their freshness signal from *content*, **not** from the metadata block's dates or file mtime — otherwise a body-only edit with unchanged metadata is invisible. A bare hash cannot plug into the existing date/order-based freshness comparison, so A must pick one of two concrete plumbings: derive an `updated_at` from the **last commit that changed the file's content** (reuses the comparison unchanged — preferred), or extend the freshness model with a **reviewed-content-hash baseline** (compare the current blob hash against the hash at last review — more robust to commit-date noise, but a freshness-engine change). Final choice deferred to A. (b) The minimal provenance edge that closes the loop is `produced_by` (**data artifact → the decision-bearing code that produced it**), authored at the artifact and materialized so it derives `bears_on` (decision-bearing, fail-closed) — because today only a fixed set of epistemic edges plus `prov:wasDerivedFrom` derive `bears_on`, and a code→data link does not exist at all. The propagation is engine-agnostic: a code edit reaches a finding via `code-file → data artifact → finding`, with no workflow/run nodes required on the path. The richer workflow predicates (`implements` / `executes` / `feeds_into`) and `OPERATIONAL`-node traversal are *not* required for the guarantee and are deferred to the optional workflow adapter (§5). (a) constrains A's model; (b) is C's headline deliverable.
10. **Code-artifact boundary & exclusions.** "No ghosts" means *no unclassified code artifacts*, not "every file." An exclusion mechanism (leaning `science.yaml` excludes, optionally a `.scienceignore`; exact form deferred to A) removes generated, vendored, asset, and config files; recognized non-artifact classes (tests, package markers) are *classified* rather than required to carry full metadata blocks. What counts as a block-bearing "code artifact" is defined in A.

---

## 4. Conceptual model

**Principle:** every *code artifact* under a declared code root is a registered science entity — "no ghosts" means no *unclassified* artifacts (decision 10 fixes the boundary and exclusions). A code artifact's identity, purpose, lifecycle, and bindings to the rest of the graph are declared in its co-located metadata block; validation walks the roots, and an in-scope artifact with no valid block is the violation.

**Code entities are OPERATIONAL conduits of provenance.** Like the existing workflow kinds, they carry no continuous belief. Their value is sitting on the paths that propagate belief and uncertainty to epistemic entities. The **minimal, engine-agnostic chain** that closes the loop is short:

```
code-file <--produced_by-- data artifact --grounds / cited-by--> finding / proposition   (bears_on)
```

The data artifact declares the decision-bearing code that produced it (`produced_by`, authored at the artifact); the finding already declares the data it rests on (`grounded_by` / `source_refs`). No workflow, workflow-step, or workflow-run node is required on the propagation path. A fuller orchestration model — `code-file --implements--> workflow-step --(part of)--> workflow`, `workflow-run --executes--> workflow` — is an *optional elaboration* a project may add, and the deferred workflow adapter can auto-populate `produced_by` from a real DAG; but it is never a precondition for propagation.

**Why disentangle from the DAG.** Both prototypes author `code → data` provenance *at the artifact* (MM30's `datapackage.provenance.tool`, NS's `analysis → data_package`) and use the workflow only for orchestration. Reconstructing that fact by parsing an execution-DAG is lossy, brittle, and — fatally — invisible to the decision-bearing code that lives *outside* any pipeline, which is the exact gap this program exists to close. So the epistemic layer owns the `produced_by` edge directly; the workflow DAG is a separate, optional accelerant.

**What's reused vs. what's new.** The freshness *machinery* — `bears_on` transitive closure and the `needs-review` > `stale` > `fresh` precedence — is reused unchanged, as is the data→finding side. Making `edit code file → downstream finding flips to needs-review` work requires only:

1. A **content-derived change signal** on code entities, so a body-only edit is visible at all (decision 9a, owned by A — *shipped*: `code-file.updated` = last content-changing commit).
2. The **`produced_by` (data → code) edge** materialized so it derives `bears_on`, decision-bearing and fail-closed (decision 9b, owned by C). The data→finding hop already derives `bears_on` today.

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
- The staged `--fail-on` ladder — which requires a **validation-API change**, since `validate` today has only `--strict`, `Result.severity`, and exit-nonzero-on-error. Either a gate config maps findings → severity, or the runner/CLI grows a first-class gate dimension (choice deferred to B; a gate dimension is the cleaner option, since severity describes a finding's nature while the tier describes project-maturity policy).

### Spec 2 = C (artifact-level provenance propagation contract)

- The **`produced_by` edge** (decision 9b): a data artifact (a `dataset`) declares the decision-bearing `code-file`(s) that produced it, authored at the artifact. This is the one new graph edge C adds.
- A **deriver** that turns `produced_by` into `bears_on` (`code-file bears_on dataset`), filtered to propagation-eligible (decision-bearing, fail-closed) code files and exempting `exploratory` / `retired`.
- The **uncertainty-propagation wiring that lights up** once that edge exists: reusing the shipped content-derived `code-file.updated` (9a) and the existing data→finding `bears_on` derivers, so `edit code file → downstream finding flips to needs-review` works engine-agnostically.
- **Acceptance on fixtures**, then on a migrated MM30 artifact (the t214 derived dataset + the script in its provenance).

**Deferred from Spec 2 (optional, later):** a *workflow-DAG adapter* (Snakemake first, behind a backend protocol) that **auto-populates** `produced_by` for engine-managed artifacts, plus richer workflow/workflow-step/workflow-run materialization. The epistemic guarantee does not depend on it.

**Dependency:** C builds on A's shipped model (`code-file`, `code-file.updated`) and the existing data→finding derivers; no DAG extraction is on the critical path.

---

## 6. Cross-cutting policies

### Enforcement ladder

| Tier | Gate | Rationale |
|------|------|-----------|
| 0 | report only | baseline; never blocks |
| 1 | **ghost files** (in-scope code artifact under a declared code root with no/invalid block) | cheapest, most defensible — the core "no orphans" guarantee |
| 2 | decision-bearing orphans (executable, decision-bearing, unreachable from a workflow) | the reproducibility guarantee |
| 3 | hardcoded paths / metadata completeness | hygiene, last |

The default entry point is **Tier 0 (report)**, so adopting the system never breaks an existing project on day one; greenfield projects can opt straight to Tier 1, and every project advances the ladder explicitly in `science.yaml`. **Fail-closed:** an un-annotated executable is *treated as* decision-bearing — its output could feed a claim, finding, report, figure, or task closure — until a human downgrades it.

*The ladder is not expressible in `validate` today (only `--strict`, `Result.severity`, exit-nonzero), so the gate dimension is itself a Spec 1/B deliverable — see §5.*

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

**natural-systems.** Two-stage, because the exporter does more than emit code entities. *With Spec 1 (A+B):* replace `export_kg_model_sources.py`'s **code-entity block authoring** with co-located blocks materialized by science, and register the 54 unregistered one-off scripts (`exploratory`, or migrate into a workflow). *With Spec 2 (C):* author `produced_by` on NS's `data_package` entities (the code→data edge C derives `bears_on` from), retiring the exporter's hand-rolled `analysis → workflow → data_package` provenance materialization; NS-specific concerns (`web_route`, the morphism edges) remain project-local and are out of scope. The exporter's provenance materialization can be deleted once NS authors `produced_by` and C ships; the optional workflow-DAG adapter (later) can further auto-populate it.

**Acceptance is therefore split:** A+B is done when both projects delete their bespoke **metadata-block + auditor** machinery and migrate cleanly. C is done when a migrated data artifact's `produced_by` edge propagates a code edit to a downstream finding — exercised on MM30 (the t214 derived dataset); NS's exporter-provenance retirement follows the same edge.

---

## 8. Deferred to sub-specs (not decided here)

- **A:** exact entity type names and full field lists; the relation-vocabulary additions; the Snakefile-as-both-code-file-and-workflow model; the precise `science.yaml` roots grammar.
- **B:** validator classification heuristics; the port of MM30's Snakemake path-indirection parsing; merge-preserving triage tables (machine-owned vs reviewer-owned columns).
- **C:** the `produced_by` edge's authoring surface (frontmatter field vs structured relation) and exact schema; the `bears_on` deriver and its eligibility filter; the MM30 artifact migration that exercises it. The workflow-DAG adapter (backend protocol, DAG-extraction mechanics, second-backend extensibility) is deferred *past* C, not part of it.

---

## 9. Related, but out of scope

- **Unresolved-reference brittleness.** `graph materialize` hard-fails on a single unresolved reference, with no short-form aliasing (`Q01`, `t35`). The §6 fragility firewall *routes around* this; it does not fix it. A separate effort should make resolution staged/aliased.
- **Commons promotion of reusable workflows.** When a workflow is genuinely shared across projects, it may warrant a JSON-schema mixin promotion path. Deferred until a concrete cross-project workflow exists.

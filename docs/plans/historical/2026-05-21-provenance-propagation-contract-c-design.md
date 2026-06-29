# Provenance propagation contract (Spec 2 / Plan C) — design

**Status:** design (rev 3 — implementation contract hardened over three rounds of code-grounded review)
**Date:** 2026-05-21
**Parent:** `docs/plans/historical/2026-05-21-research-code-and-workflow-modeling-design.md` (umbrella, Spec 2 = C; reframed to artifact-level provenance)
**Predecessor:** Spec 1 / Plan B (code-file registration & validation) — complete; B1 + B2 merged to local `main`.
**Acceptance test (v1):** synthetic fixtures + MM30's `t214` derived dataset (`~/d/cancer/cancer-types/multiple-myeloma`).

---

## 1. Goal

Make a **decision-bearing code edit propagate to the downstream findings that depend on its outputs**, via a first-class provenance edge authored *at the data artifact* — independent of any workflow engine.

The chain that closes the loop is short and engine-agnostic. The data artifact is a **`dataset`** entity (science's only datapackage entity profile is `science-pkg-entity-1.0`, which is dataset-typed):

```
dataset --produced_by--> code-file               [NEW: authored on the dataset, derives bears_on]
finding --source_refs / evidence_refs--> dataset [EXISTING: authored on the finding]

  ⇒ (new deriver, eligibility-filtered)  code-file bears_on dataset
  ⇒ (existing prov deriver)              dataset bears_on finding
  ⇒ (closure)                            code-file bears_on finding
```

A code edit bumps `code-file.updated` (last content-changing commit date — already shipped by `CodeAdapter`, decision 9a), which the existing freshness comparison sees as `> finding.baseline`, flipping the finding to `needs-review` with `triggeredBy` the code file. **No workflow, workflow-step, or workflow-run node is on the path.**

### Why this shape (not a workflow-DAG adapter)

Both acceptance prototypes author the `code → data` fact *at the artifact* — MM30 in `datapackage.provenance.tool` (`"script.py::fn"`), natural-systems in its `analysis → data_package` chain — and use the workflow only for orchestration. Reconstructing that fact by statically parsing a Snakemake DAG is lossy and brittle (path indirection, wildcards, no output paths on derived datasets), and — fatally — blind to decision-bearing code that lives *outside* any pipeline, which is the exact gap this program exists to close. So the epistemic layer owns the `produced_by` edge directly; the workflow DAG is a deferred, optional accelerant that may later auto-populate the same edge.

## 2. What already exists (reused unchanged)

- **`code-file` entities** with content-derived `updated` — `CodeAdapter.load_raw` sets `updated = last_content_change_date(...)` (`graph/storage_adapters/code.py:66`). Decision 9a is shipped.
- **The freshness engine** — `bears_on` transitive closure (`close_bears_on`), the `needs-review > stale > fresh` precedence, and the `change_at = upstream.updated > baseline` comparison (`graph/freshness.py`). Reused as-is.
- **The data→finding `bears_on` hop** — `derive_bears_on_from_provenance` (`freshness.py:181`): a finding's `source_refs`/`evidence_refs` are materialized as `prov:wasDerivedFrom`, and the rule `?d prov:wasDerivedFrom ?s → ?s bears_on ?d  (iff ?d epistemic)` yields `dataset bears_on finding`. Reused as-is. (`grounded_by` is *not* usable here: it targets `data-package`/`workflow-run`, never `dataset` — `profiles/core.py:246`.)
- **The materialize derivation seam** — `_build_dataset_from_sources` builds `kind_class` and `pre_registration_targets`, calls `_derive_bears_on_layer(dataset, kind_class=, pre_registration_targets=)`, then `close_bears_on` (`materialize.py:102-138, 897-917`). C adds one deriver here, threading one new argument in the same style as `pre_registration_targets`.

## 3. What C adds (the implementation contract)

### 3.1 The `produced_by` edge — authored as a modeled field, materialized leniently

**Model.** Add a modeled field `produced_by: list[str]` to `DatasetEntity` (`science_model/entities.py`), **code-only** — every entry is a `code-file:` ref. A *bare top-level key would be silently dropped* — entities only preserve modeled fields, and only `entity.relations` is flattened into `SourceRelation` (`sources.py:676`). So `produced_by` must be a real field, not free-form frontmatter. (The pre-existing `data-package → workflow-run` `produced_by` provenance is unaffected: it is authored via the structured `relations:` path and materialized as today. The code→data field and the run→data relation are deliberately separate surfaces.)

**Schema.** Add `produced_by` (array of strings, each matching `^code-file:`, `minItems: 1` when present) to `schemas/science-pkg-entity-1.0.json`, and add it to `DatapackageAdapter._ENTITY_FIELDS` (`graph/storage_adapters/datapackage.py:15`) so datapackage-authored datasets surface it. Markdown-authored dataset frontmatter reads the same field. A `workflow-run:` value in this field is a validation error (use the `relations:` path for run-producers).

**Relation kind.** Extend `produced_by` in `profiles/core.py:302` to `source_kinds = [data-package, dataset]`, `target_kinds = [workflow-run, code-file]`, so both the run-producer relation (existing) and the code→data triple this field emits are valid and queryable.

**Materialization (lenient, firewall-safe — see §4).** A dedicated step in `_build_dataset_from_sources` reads each dataset's `produced_by` field, resolves each `code-file:` ref against the in-memory code-file index, and emits a `sci:producedBy` triple for each *hit*. This step does **not** go through `_add_authored_relation`/`audit_project_sources` (which hard-fail on a dangling ref); a miss is skipped and surfaced by a validate check (§4).

### 3.2 Derived datasets may use code-provenance instead of a workflow-run block

Today a `derived` dataset is *required* to carry a `derivation` block with `workflow` + `workflow_run` refs (schema `allOf`, lines 45-48; `entities.py` invariant #8). That mandates the run machinery we are disentangling from. **C relaxes the `origin: derived` requirement to accept *either* a `derivation` block *or* a non-empty `produced_by` code-file provenance.** Because the field is code-only (§3.1), "non-empty `produced_by`" *is* code provenance — there is no way to satisfy the no-derivation path with an empty list or a run ref. Concretely:

- **JSON schema:** the `origin: derived` `allOf` branch becomes `anyOf: [ {required: [derivation]}, {required: [produced_by]} ]`, with `produced_by` declared `minItems: 1` and `items.pattern: ^code-file:`. (Belt-and-suspenders: the `produced_by` branch also `contains` a `^code-file:` item.) The `origin: external` branch additionally **forbids `produced_by`** (`not: {required: [produced_by]}`), beside its existing `not: {required: [derivation]}`.
- **Pydantic invariant:** `origin == "derived"` requires `derivation is not None` **or** `produced_by` non-empty (#8); `origin == "external"` must carry neither `derivation` nor `produced_by` (#7) — an external/raw-input dataset cannot claim code produced it, so a code edit can never propagate through it. The existing "derived must not carry access/accessions/local_path" guards are retained.

**Readiness.** Relaxing the invariant is not enough: `DatasetEntity._derived_readiness` (`entities.py:597`) returns `missing-derivation-block` whenever `derivation is None`, then resolves `derivation.workflow_run`. It must branch: `derivation` present → existing run-backed readiness (unchanged); else `produced_by` non-empty → a code-provenance ready state (e.g. `Readiness(ready=True, state="derived-via-code")`, no resolver/run needed); else → `missing-provenance`. This is the load-bearing change that lets a derived dataset declare *what code produced it* without inventing a workflow-run.

### 3.3 The bears_on deriver + a concrete eligibility carrier

Add `derive_bears_on_from_produced_by_code(dataset, *, eligible_code_files: set[URIRef])` (`graph/provenance_edges.py`): for each `(?dataset, sci:producedBy, ?code_file)` triple where `?code_file ∈ eligible_code_files`, emit `(?code_file, sci:bearsOn, ?dataset)`.

**Eligibility carrier (the concrete data path the review flagged):** mirror `pre_registration_targets`. The materializer builds `eligible_code_files: set[URIRef]` from `sources.entities` and threads it through `_derive_bears_on_layer(...)` into the deriver. To compute it without re-opening files, `CodeAdapter` records two values on each code-file entity at load time (it already has the block text + path):

- `decision_bearing: bool | None` — **`None` when the block omits it** (today coerced to `False`, `code.py:64`). The one Plan-B-adjacent change; additive, preserves B2's validate behavior.
- `executable: bool` — from B2's `is_executable(rel_path, text)` (`code/classification.py`).

The materializer then computes, per code-file entity:

```
eligible = (decision_bearing if decision_bearing is not None else executable)
           and status not in ORPHAN_GATING_EXEMPT_STATUSES      # {exploratory, retired}
```

reusing B2's exemption set (`code/lifecycle.py`). Decision-bearing only, fail-closed.

## 4. Fragility firewall + the observable surface

`produced_by → code-file` resolution is **lenient: skip-on-miss, never a hard-fail** — it is *not* added to `audit_project_sources`. This honors the umbrella's firewall (registration must not widen the build-blocking surface): a dataset naming a producing script that has no `science:code` block (a ghost, owned by B2) cannot break `graph materialize`.

The **observable surface** (the review's High-3) is a new validate `@Check`, `code.produced-by-unresolved` (severity `WARN`): for each dataset `produced_by` ref that does not resolve to a registered code-file, emit a `Result(path=<dataset>, message=…, rule="code.produced-by-unresolved")`. It slots into the existing gate ladder at the **hygiene** tier — which requires **adding `"code.produced-by-unresolved"` to `_TIER_RULES["hygiene"]` in `validate/gates.py:27`** (without that, it would report but never gate). A provenance-completeness signal, never blocking by default. So a missing edge is *visible and gateable*, not silent, and *non-fatal* to materialize.

## 5. Canonical-id normalization for `produced_by` targets

`produced_by` targets are **code-file canonical ids**, `code-file:<local_id>`, where `<local_id>` is the path **relative to the declared code root** — `CodeAdapter._local_id` strips the root (`code.py:74`), so a script at `scripts/signatures/build.py` under code root `scripts/` is `code-file:signatures/build.py` (not `code-file:scripts/signatures/build.py`). Authors (and the MM30 migration) must:

1. Drop any `::function` suffix from a `provenance[].tool` value.
2. Strip the declared code-root prefix from the path.
3. Prefix with `code-file:`.

The plan includes one mapping helper + tests for this path→id rule.

## 6. Testing strategy (TDD)

- **Schema/model:** a `derived` dataset validates with non-empty code-only `produced_by` and **no** `derivation` block; one with neither (and one with `produced_by: []`) fails; a `workflow-run:` value in `produced_by` is rejected; an `external` dataset carrying `produced_by` is rejected.
- **Readiness:** a code-provenance-only derived dataset reports `ready=True, state="derived-via-code"` (no resolver needed); a derivation-backed one is unchanged; one with neither reports `missing-provenance`.
- **Relation kind:** `produced_by` validates `dataset/data-package → code-file` (and still `→ workflow-run`); rejects disallowed kinds.
- **Adapter:** a `datapackage.yaml` (and a markdown dataset) with `produced_by: [code-file:x]` surfaces the field; a dataset without it is unaffected.
- **Eligibility:** the materializer's `eligible_code_files` set includes an un-annotated executable code-file and a `decision_bearing: true` one; excludes `decision_bearing: false`, `exploratory`, `retired`, and non-executable library/test files.
- **Deriver:** `dataset producedBy code-file` yields `code-file bears_on dataset` **only** for code-files in `eligible_code_files`.
- **Closure / conduit semantics (the review's Medium-4):** on `code-file ← produced_by ← dataset` and `finding --source_refs--> dataset`, assert `code-file bears_on finding` after closure; assert the **dataset is a direct `bears_on` conduit target (operational), traversed by closure but assigned no freshness *state* and never emitted as a *closure* target** — only the epistemic finding gets a state.
- **Freshness integration:** editing the code file (newer `updated`) flips the finding to `needs-review` with `triggeredBy` the code file.
- **Firewall:** a dataset whose `produced_by` names a non-existent code-file does not fail `graph materialize`, and `code.produced-by-unresolved` reports it (`WARN`).
- **Id normalization:** `scripts/signatures/build.py::fn` under root `scripts/` → `code-file:signatures/build.py`.

## 7. MM30 acceptance (the real-world exercise)

C's own correctness is proven on the synthetic fixtures above. The real-world exercise is MM30's `t214` derived dataset. The MM30-side steps are **prerequisites, out of C's code scope**, but they define the acceptance:

1. Migrate `data/derived/pc_maturity_healthy_reference_t214/datapackage.json` to a `science-pkg-entity-1.0` `datapackage.yaml` so science ingests it as a `dataset` entity (`origin: derived`).
2. Author `produced_by: [code-file:signatures/build_pc_maturity_healthy_reference.py]` on it (the `provenance[].tool` script, normalized per §5), **using §3.2's code-provenance path so no `workflow_run` is required**.
3. Add a `science:code` block (decision-bearing) to that script; declare `scripts/` a code root.
4. Ensure `interpretation:2026-04-18-t214-…` cites the dataset via `source_refs`/`evidence_refs` (not bare `relatedTo`, which is `skos:related` and does not propagate).

**Acceptance:** editing the script → `graph materialize` → freshness flips the t214 interpretation to `needs-review`, `triggeredBy` the code file. natural-systems' exporter-provenance retirement follows the same edge, later.

## 8. File structure

**New:**

- `science/src/science_tool/graph/provenance_edges.py` — `derive_bears_on_from_produced_by_code` + the `produced_by → code-file` lenient resolution/materialization helper + the path→id normalizer.
- `science/src/science_tool/validate/checks/…` — the `code.produced-by-unresolved` `@Check` (extend the existing code-files check or a sibling).
- `science/tests/graph/test_provenance_edges.py`, plus schema/adapter/validate tests.

**Modify:**

- `science/model/src/science_model/entities.py` — `DatasetEntity.produced_by: list[str]` (code-only); relax invariant #8 (derivation **or** non-empty produced_by); branch `_derived_readiness` for code-provenance-only datasets; `CodeFileEntity.decision_bearing: bool | None` + `executable: bool`.
- `science/model/src/science_model/schemas/science-pkg-entity-1.0.json` — add `produced_by` (`items.pattern ^code-file:`, `minItems: 1`); relax the `origin: derived` branch to `anyOf [{required:[derivation]}, {required:[produced_by]}]`.
- `science/src/science_tool/validate/gates.py` — add `code.produced-by-unresolved` to `_TIER_RULES["hygiene"]`.
- `science/src/science_tool/graph/storage_adapters/datapackage.py` — read `produced_by`.
- `science/src/science_tool/graph/storage_adapters/code.py` — `decision_bearing` `None`-when-absent + `executable` flag.
- `science/src/science_tool/graph/materialize.py` — lenient `produced_by → code-file` materialization (skip-on-miss); build `eligible_code_files`; thread it through `_derive_bears_on_layer`; call the new deriver before `close_bears_on`.
- `science/model/src/science_model/profiles/core.py` — extend `produced_by` source/target kinds.
- `docs/conventions/` — document the `produced_by` code→data edge, the code-provenance derived-dataset path, the id-normalization rule, and `code.produced-by-unresolved`.

## 9. Non-goals / deferred

- The **workflow-DAG adapter** (Snakemake-first backend protocol that auto-populates `produced_by` from a real DAG) — deferred *past* C, a separate spec.
- `workflow` / `workflow-step` / `workflow-run` materialization and the `implements` / `feeds_into` chain.
- natural-systems migration (sequenced after MM30).
- Auto-promoting `relatedTo`→`source_refs`; expanding `grounded_by` to target `dataset`; triage TSVs; imported-by-owned library tracing.

---

## Appendix — resolutions to the code-grounded review

| # | Finding | Resolution |
|---|---------|------------|
| High-1 | `produced_by` authoring path not connected | §3.1 — modeled `DatasetEntity.produced_by` field + schema + adapter `_ENTITY_FIELDS` + a dedicated lenient materialization step (not the dropped/never-flattened bare-key path). |
| High-2 | eligibility filter has no data path into the deriver | §3.3 — `CodeAdapter` records `decision_bearing: bool\|None` + `executable`; materializer builds `eligible_code_files: set[URIRef]` and threads it through `_derive_bears_on_layer`, mirroring `pre_registration_targets`. |
| High-3 | firewall "skip-on-miss + Result" had no surface | §4 — resolution is lenient (not audited, no hard-fail); the surface is a new validate `@Check` `code.produced-by-unresolved` (`WARN`, hygiene tier). |
| Med-4 | test contract contradicted the edge contract | §6 — restated: the dataset is a **direct** `bears_on` conduit target (operational), traversed by closure, **assigned no freshness state and never a closure target**; only epistemic findings get states. |
| Med-5 | MM30 step would miss canonical ids | §5 — explicit path→id normalization (drop `::fn`, strip code root, prefix `code-file:`), with a helper + tests; applied in §7 step 2. |
| Med-6 | `dataset produced_by` under-specified downstream | §1/§2 — `grounded_by` can't target `dataset`; the downstream hop is the finding's `source_refs`/`evidence_refs` → `prov:wasDerivedFrom` (existing). Documented; `grounded_by` expansion left as a non-goal. |
| (verification) | derived datasets mandate `workflow`/`workflow_run` | §3.2 — relax `origin: derived` to accept `produced_by` code-provenance as an alternative to the `derivation` block (schema `allOf`→`anyOf` + invariant #8). |

**Rev 2 → rev 3** (second code-grounded review):

| # | Finding | Resolution |
|---|---------|------------|
| High | `produced_by` field allowed `workflow-run:` but materializer only emits for `code-file:` (dead path) | §3.1 — field is **code-only** (`^code-file:`); run-producers stay on the existing `relations:` path, untouched. |
| High | relaxed derived invariant could be satisfied by `produced_by: []` / a run ref | §3.2 — schema `minItems: 1` + `^code-file:` (+`contains`) and the Pydantic invariant require **non-empty code** provenance. |
| Med | `DatasetEntity._derived_readiness` still returns `missing-derivation-block` | §3.2 — branch readiness: derivation → run-backed; else non-empty `produced_by` → `derived-via-code`; else `missing-provenance`. |
| Med | `code.produced-by-unresolved` gateable but `gates.py` not in the file list | §4 + §8 — add the rule to `_TIER_RULES["hygiene"]` (`validate/gates.py`). |
| Low | umbrella still said `data-package` / "t214 derived data-package" | umbrella §5/§7 reworded to `dataset` / "data artifact" to match C's dataset-only path. |

**Rev 3 polish** (third review round):

| # | Finding | Resolution |
|---|---------|------------|
| Med | `produced_by` not forbidden on `origin: external` datasets | §3.2 — invariant #7 and the schema `external` branch now forbid `produced_by` (raw input can't claim code produced it; code edits can't propagate through it); test added in §6. |
| Low | status header said rev 2 while appendix said rev 3 | header bumped to rev 3. |

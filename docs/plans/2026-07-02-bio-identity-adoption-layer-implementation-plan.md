# Bio Identity Adoption Layer — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax. TDD: write the failing test first, then the code.

**Goal:** Make declaring an organism + reference-genome identity a cheap, mandatory, enforced part of authoring a dataset and writing a workflow, resolvable to Pillar C's canonical seqcol/namespace identity — and prove it end-to-end by making MM30 the first fully-resolved consumer (unblocking t665's TAD / A-B-compartment axes).

**Architecture:** The entity `identity_context` stays the source of truth; a profile-scoped declaration gate makes it strict-by-default; the datapackage carries a derived read-only `science.identity_context` stamp checked against the entity; a `science dataset identity resolve` engine resolves labels against pinned commons artifacts (degrading to `declared_unresolved`); `entities/workflows/<slug>.md outputs[].identity` is the contract that `register-run` propagates into derived datasets, with tier-general `transform` and a discriminated cross-build `proxy`, both provenance-checked. See the companion design: `docs/plans/2026-07-02-bio-identity-adoption-layer-design.md`.

**Tech Stack:** Python ≥3.11, Pydantic v2, pytest ≥9, ruff (line-length 120), uv workspace; `science` tool suite + `science_model` suite; `science-commons` recipes; MM30 (Snakemake 9) as the consumer.

## Global Constraints

- Python `>=3.11`; Pydantic **v2** (`@model_validator(mode="after")`, `@field_validator` + `@classmethod`, inline `Literal[...]`, not `enum.Enum`).
- ruff line-length **120**; run `uv run ruff format` + `uv run ruff check` before each commit.
- Tool suite lives in `~/d/science/science/`; model suite in `~/d/science/science/model/`. Each has its own pytest config (`testpaths = ["tests"]`). Run `uv run --frozen pytest ...` **from the suite directory**.
- **Resolution is offline.** The resolver reads pinned, hash-verified commons artifacts only — no live MyGene / Ensembl-REST / refgenieserver / UniProt in a reproducible path. Missing artifact ⇒ degrade to `declared_unresolved` with a message, never a network fallback, never a silent pass.
- **Two-level strictness:** declaration is mandatory always for identity-bearing profiles; resolution is required only at the promote/publish boundary. `declared_unresolved` is a legal, non-blocking authoring state.
- **The datapackage stamp is derived, never authoritative.** A hand-authored stamp that disagrees with the entity is an error; an absent stamp is not.
- **Identity-bearingness is read from the composed `schema_profile` token, not the `profiles:` list** (see P1.3). Register-run-derived entities lack a bio token today; P3 stamps one.
- **Reference artifacts are never data ancestors** (Key decision 9): `transform.dataset` / `proxy.via` route to `derivation.transformations[]` as a non-dependence `reference` usage role; only `proxy.sources[]` enter `derivation.inputs`. Do not add reference artifacts to `inputs:` — it pollutes `consumed_by`, the plan access/reproducibility closure, and B2 independence.
- Branch `bio-identity-adoption-layer` in `~/d/science` (and matching topic branches in `~/d/science-commons`, MM30). One commit per task. No AI-attribution trailers.
- MMRF CoMMpass raw data is access-controlled; the MM30 retrofit touches only entity metadata / public cell-line datasets, never raw MMRF files.

## File Structure

**`~/d/science` (framework):**
- `science/model/src/science_model/schemas/extension-bio-identity_context-1.0.json` — **Modify**: add `assembly.proxy`, tier-level `transform`; relax `assembly_identity.additionalProperties`; make `seqcol_digest` optional when `resolution_status: declared_unresolved`.
- `science/model/src/science_model/packages/schema.py` — **Modify**: Pydantic `AssemblyIdentity`, `IdentityProxy`, `MolecularTierIdentity`, `IdentityTransform`; profile-scoped requiredness.
- `science/model/src/science_model/frontmatter.py` — **Modify**: coerce the `identity_context` sub-blocks (proxy, transform, sources).
- `science/src/science_tool/commons/identity_resolve.py` — **Create**: `resolve_identity(ctx, *, registries, mode)` → resolved-or-`declared_unresolved`; `resolve_assembly_label()`, `resolve_namespace()`.
- `science/src/science_tool/commons/identity_stamp.py` — **Create**: `derive_stamp(entity_identity)`, `stamp_agrees(entity_identity, datapackage)`. (The two writers that emit the stamp are named in P1.4, not here.)
- `science/src/science_tool/datasets_identity.py` — **Create**: `dataset identity resolve|show|suggest` command bodies; registered as a `dataset identity` subgroup in `cli.py` (`dataset_group`, `cli.py:6696`).
- `science/src/science_tool/datasets_register.py` — **Modify**: `write_per_output_datapackages` (`:55`), `write_derived_dataset_entities` (`:148`) / `_entity_yaml_block` (`:107`), `write_symmetric_edges` (`:257`), `_read_workflow_outputs` (`:13`) — read `outputs[].identity`; propagate into the derived entity's `identity_context` + a bio `schema_profile` token; route reference machinery to `derivation.transformations[]` and data sources to `derivation.inputs`; stamp the per-output datapackage; check the run sidecar.
- `science/src/science_tool/datasets_catalog.py` — **Modify**: `add_dataset` (`:81`) requires identity for identity-bearing profiles.
- `science/src/science_tool/commons/dataset_lifecycle.py` — **Modify**: `scaffold_dataset_package` (`:275`) requires identity for identity-bearing profiles (the `commons dataset init` path; CLI in `commons/cli.py`).
- `science/src/science_tool/commons/datapackage.py` — **Modify**: `render_canonical_datapackage_yaml` (`:207`) must **preserve** the framework-blessed `science.identity_context` key (today it strips project-only keys `{id, conformsTo, mm30, derivedFrom}` at `:26`).
- `science/src/science_tool/validate/checks/identity_context.py` — **Modify**: declaration gate (schema_profile-keyed), stamp agreement, proxy/transform provenance, strict `inherit`.
- `science/src/science_tool/graph/dataset_usage.py` + `graph/dataset_independence.py` — **Modify**: add a non-dependence `reference` usage role (excluded from `DEPENDENCE_ROLES`) for `derivation.transformations[]` reference artifacts.
- `science/src/science_tool/project_config.py` — **Modify**: `identity_policy` (declaration strictness, resolution-at-publish, migration window).
- `templates/dataset.md`, `templates/workflow.md`, `docs/user-guide/entities.md`, `commands/plan-pipeline.md`, `commands/plan-analysis.md` — **Modify**.
- Tests: `science/model/tests/test_identity_context_models.py`, `science/tests/test_identity_resolve.py`, `science/tests/test_identity_stamp.py`, `science/tests/test_identity_cli.py`, `science/tests/test_register_run_identity.py`, `science/tests/test_check_identity_context.py`.

**`~/d/science-commons` (P4):** build entrypoints under `datasets/assembly-registry/`, `datasets/gene-crosswalk-hgnc/`; `datasets/cytoband-hg19/` (new proxy `via` reference).

**MM30 (P5):** `scripts/shared/datapackage.py`, `entities/datasets/*.md`, `entities/workflows/*.md`, `scripts/analyses/t665_gse131651_3d_locus_ledger.py` + t665 entities.

---

## Phase P1 — Declaration + profile-scoped gate + datapackage stamp

### Task P1.1: Schema — proxy + tier transform + optional seqcol under declared_unresolved

**Files:** Modify `extension-bio-identity_context-1.0.json`; Test `science/model/tests/test_identity_context_models.py`.

**Interfaces:** `assembly_identity` gains an optional `proxy` object `{type ∈ (cytoband_proxy|interval_overlap_proxy|symbol_space_proxy), via: dataset:*, sources: [{dataset: dataset:*, assembly: inherit|{label}|{seqcol_digest}}] (minItems 1)}` and an optional `transform` object `{type ∈ (liftover|symbol_remap|namespace_map), from, method?, dataset: dataset:*}`; `molecular_ids.<tier>` gains the same `transform`. `seqcol_digest` becomes optional when `resolution_status: declared_unresolved` (sentinel `UNKNOWN` allowed). `additionalProperties` relaxed to admit `proxy`/`transform` only.

- [ ] **Step 1:** Failing schema tests — a proxy block validates; a proxy with empty `sources` fails; a tier `transform` validates; `declared_unresolved` without `seqcol_digest` validates; an unknown `proxy.type` fails.
- [ ] **Step 2:** Edit the JSON schema; re-run model tests.

### Task P1.2: Pydantic models + coercion

**Files:** Modify `schema.py`, `frontmatter.py`; Test `test_identity_context_models.py`.

**Interfaces:** `AssemblyIdentity(label?, seqcol_digest?, registry, resolution_status, proxy?)`, `IdentityProxy(type, via, sources)`, `ProxySource(dataset, assembly)`, `MolecularTierIdentity(namespace, canonical?, registry?, resolution_status, transform?)`, `IdentityTransform(type, from_, method?, dataset)`. `@model_validator`: `resolution_status: resolved` ⇒ `seqcol_digest` present and ≠ `UNKNOWN`; `proxy` ⇒ `resolution_status == declared_unresolved`.

- [ ] **Step 1:** Failing model tests (round-trip; the resolved-requires-digest validator; proxy-requires-unresolved validator).
- [ ] **Step 2:** Implement models + `_coerce_identity_context`.

### Task P1.3: Profile-scoped declaration gate

**Files:** Modify `validate/checks/identity_context.py`, `project_config.py`; Test `test_check_identity_context.py`.

**Detection surface (grounded in current code):** identity-bearingness is read from the composed **`schema_profile:`** token string, **not** the `profiles:` list. `identity_context.py:56` defines `_COORDINATE_EXTENSIONS = ("bio.rnaseq","bio.scrna","bio.cna")` and `_is_coordinate_bearing` (`:63`) substring-tests `schema_profile`; genesets key on `+bio.geneset/` (`commons/geneset.py:19`); crosswalk tiers on `+bio.gene_crosswalk/` / `+bio.protein_crosswalk/` (`genesets.py:43-51`); variant keys on the **presence** of `identity_context.molecular_ids.variant` (`variant_identity.py:36`), not on `schema_profile`. The `profiles:` list is consulted only for promotion candidacy + orphan-owner scans, never by the bio checks.

**Profile → required identity tiers (P1.3 lookup table):**

| `schema_profile` contains (or condition) | Required identity | Notes |
|---|---|---|
| `+bio.rnaseq/`, `+bio.scrna/`, `+bio.cna/` | `assembly` + `taxon` | coordinate-bearing assays |
| `+bio.geneset/` | `gene` tier + `taxon` | gene-set collection |
| `+bio.gene_crosswalk/` | `gene` tier + `taxon` | |
| `+bio.protein_crosswalk/` | `protein` tier + `taxon` | |
| `identity_context.molecular_ids.variant` present | `variant` tier + `taxon` | detected by key presence, not profile |
| base only (`science-pkg-entity-1.0`, no `bio.*` token) | none | not identity-bearing *by structure* — see the derived-dataset gap |

**Derived-dataset gap (must be handled, not silently passed):** `register-run` emits derived entities with `profiles: ["science-pkg-entity-1.0"]` and **no** `schema_profile` bio token (`datasets_register.py:127`), so `_is_coordinate_bearing("") → False` and today they are invisible to the gate. P3 (register-run propagation) must stamp the derived entity's `schema_profile` with the appropriate bio extension token so this gate can see it. Until P3 lands, a coordinate-emitting *derived* dataset is a known, logged gap — P1.3 does not pretend to cover it.

**Interfaces:** `required_identity_tiers(schema_profile, identity_context) -> set[str]` returns which of `{assembly, gene, protein, variant}` are mandatory (+ `taxon` whenever any is). The check errors when a required tier / `taxon` is absent; a present tier with `resolution_status: declared_unresolved` passes the *declaration* gate. `identity_policy` (project + plan) controls declaration strictness and the migration window.

- [ ] **Step 1:** Failing check tests — one row per table entry: `+bio.cna/` without `assembly` errors; with `declared_unresolved` passes; `+bio.geneset/` without a `gene` tier errors; a base-profile clinical table needs nothing; missing `taxon` on any identity-bearing profile errors; a variant-key entity requires the `variant` tier.
- [ ] **Step 2:** Implement `required_identity_tiers` (reading `schema_profile` + variant-key presence) + the check; wire `identity_policy`; log the derived-dataset gap.

### Task P1.4: Datapackage stamp — derive, write, agreement-check

**Files:** Create `commons/identity_stamp.py`; Modify the two named writers; Modify `commons/datapackage.py` (preserve rule); Modify `validate/checks/identity_context.py` (agreement); Test `test_identity_stamp.py`.

**The exact writers (there is no single "the datapackage renderer"):**
- `datasets_register.py::write_per_output_datapackages` (`:55`) — the per-output runtime datapackages. **This is the P1/P3 stamp writer**: it emits the derived `science.identity_context` stamp from the output's propagated identity.
- `commons/datapackage.py::render_canonical_datapackage_yaml` (`:207`) — the commons canonicalizer. Today it **strips** the project-only keys `{id, conformsTo, mm30, derivedFrom}` (`:26`). **Add `science.identity_context` to a preserve-list** so the framework-blessed stamp survives canonicalization (it is *not* a project-only key). No other renderer emits a namespaced block; MM30's `scripts/shared/datapackage.py` is retrofitted in P5, not here.

**Missing-stamp rule (prevents P1 from failing pre-existing runnable datasets):**
- Datapackage stamp **absent** ⇒ **not an error** (at most an advisory NOTE during the migration window). A dataset that predates the stamp writer must not suddenly fail.
- Datapackage stamp **present and disagrees** with the owning entity's `identity_context` ⇒ **error**. This is the only integrity check P1 enforces on the stamp.
- The stamp is **derived, never hand-authored as authority** — an author writing a stamp is opting into the agreement check, not declaring identity.
- Resolution presence in the stamp (`seqcol_digest` ≠ `UNKNOWN`) is required only at the promote/publish boundary (P2/P4), not by P1.

**Interfaces:** `derive_stamp(entity_identity) -> dict`; `stamp_agrees(entity_identity, datapackage) -> bool` (absent stamp ⇒ `True`/skip, not failure).

- [ ] **Step 1:** Failing tests — derived stamp equals entity identity; a mutated present stamp fails agreement; an **absent** stamp does **not** fail; `render_canonical_datapackage_yaml` preserves `science.identity_context` while still stripping `mm30`.
- [ ] **Step 2:** Implement `derive_stamp` / `stamp_agrees`; wire into `write_per_output_datapackages` + the canonicalizer preserve-list + the check.

### Task P1.5: Template + entities.md authoring block

**Files:** Modify `templates/dataset.md`, `docs/user-guide/entities.md`.

- [ ] **Step 1:** Add the `identity_context` block (resolved + `declared_unresolved` examples) to the template and an authoring section to `entities.md`.
- [ ] **Step 2:** `uv run --frozen science validate --verbose` on a fixture project; confirm P1 gate fires.

---

## Phase P2 — Resolver engine + lifecycle integration

### Task P2.1: Resolver engine (offline, degrading)

**Files:** Create `commons/identity_resolve.py`; Test `test_identity_resolve.py`.

**Interfaces:** `resolve_identity(ctx, *, registries, mode="declare") -> ResolvedIdentity`. `resolve_assembly_label(label, registry) -> seqcol_digest | None`; `resolve_namespace(namespace, registry) -> resolution_status`. Missing/absent registry artifact ⇒ `declared_unresolved` + a structured message; **never** a network call.

- [ ] **Step 1:** Failing tests — with a fixture assembly-registry, `hg38`→its seqcol; without it, `declared_unresolved` + message; idempotent (resolving an already-resolved ctx is a no-op); no-network invariant (monkeypatch socket to assert no egress).
- [ ] **Step 2:** Implement using the existing `commons` assembly/crosswalk readers.

### Task P2.2: `science dataset identity` CLI

**Files:** Create `datasets/identity_cli.py`; register in the CLI app; Test `test_identity_cli.py`.

**Interfaces:** `science dataset identity resolve dataset:x [--taxon N] [--assembly LABEL] [--gene-namespace NS]` (idempotent, non-interactive, batch over a glob); `... show dataset:x`; `... suggest dataset:x` (from inputs). Writes/updates entity `identity_context`; `--stamp` also writes the datapackage stamp.

- [ ] **Step 1:** Failing CLI tests — resolve writes `identity_context`; re-run is a no-op; `--assembly UNKNOWN` writes `declared_unresolved`; batch over two fixtures.
- [ ] **Step 2:** Implement; wire the engine.

### Task P2.3: Lifecycle integration — `add` / `init` refuse; `register-run` propagates

**Files:** Modify `datasets/lifecycle.py`, `commons/cli.py` (`dataset init`), the `register-run` module; Test `test_register_run_identity.py`.

**Interfaces:** `dataset add` / `commons dataset init` refuse an identity-bearing profile without identity or explicit `--assembly UNKNOWN`. `register-run` for derived datasets calls the propagation path (P3) — here just the wiring + the refuse-without-identity behavior for new external datasets.

- [ ] **Step 1:** Failing tests — `add` of a coordinate-assay profile without identity errors; with `--assembly UNKNOWN` succeeds as `declared_unresolved`.
- [ ] **Step 2:** Implement.

---

## Phase P3 — Workflow output contract + propagation + transform/proxy

### Task P3.1: `outputs[].identity` schema + workflow template

**Files:** Modify the workflow-entity schema/model + `templates/workflow.md`; Test the workflow-output model.

**Interfaces:** `outputs[].identity` accepts `taxon/assembly/molecular_ids` with `inherit`, `inherit.from`, literal values, `transform`, and `proxy` (reusing the P1 models). `inherit` sentinel modeled explicitly.

- [ ] **Step 1:** Failing tests — the four design examples (pass-through, symbol_remap, liftover, cytoband proxy) parse; a proxy with empty sources fails.
- [ ] **Step 2:** Implement + update the template.

### Task P3.2: `register-run` resolution/propagation

**Files:** Modify `datasets_register.py` (`write_derived_dataset_entities` `:148`, `_entity_yaml_block` `:107`, `write_symmetric_edges` `:257`); Test `test_register_run_identity.py`.

**Interfaces:** given a workflow output's `identity` contract + resolved input identities, produce the derived dataset's `identity_context`: `inherit` ⇒ the shared input identity (error if inputs disagree); `inherit.from` ⇒ the named input; literals ⇒ as-declared; `transform`/`proxy` ⇒ carried through with `declared_unresolved` where appropriate. Additionally:
- **Stamp the derived entity's `schema_profile`** with the bio extension token implied by the output profile (e.g. a coordinate-emitting output ⇒ a `+bio.*` coordinate token), so the P1.3 gate can see it (closes the derived-dataset gap).
- **Route lineage correctly (Key decision 9):** `proxy.sources[].dataset` (data ancestors) go into `derivation.inputs` (existing fan-out + `consumed_by`). `transform.dataset` / `proxy.via` (reference machinery) go into `derivation.transformations[].dataset` — **never** `derivation.inputs` — matching the surface `identity_context.py:199-226` already reads.
- Write the per-output datapackage stamp (P1.4 writer).

- [ ] **Step 1:** Failing tests — pass-through inherits; disagreeing inputs under bare `inherit` error; `inherit.from` selects; proxy output yields `declared_unresolved` + structured `proxy`; a `transform.dataset` lands in `derivation.transformations[]` and is **absent** from `derivation.inputs`/`consumed_by`; `proxy.sources[]` land in `derivation.inputs`; the derived entity acquires a `+bio.*` `schema_profile` token.
- [ ] **Step 2:** Implement.

### Task P3.2b: `reference` usage role (non-dependence)

**Files:** Modify `graph/dataset_usage.py` (role vocab + `usage_records_for_entity`), `graph/dataset_independence.py` (`DEPENDENCE_ROLES`), `validate/checks/dataset_taxonomy.py` (`_USAGE_ROLES`); Test the usage/independence materialization.

**Interfaces:** add a `reference` value to the usage-role vocab; `usage_records_for_entity` emits `derivation.transformations[].dataset` as `role="reference"`; `reference ∉ DEPENDENCE_ROLES` (mirrors `cited`/`validation_source`), so a reference artifact is a reified `sci:DatasetUsage` node but is **not** a data ancestor and never triggers B2 shared-source independence or the transitive plan access/reproducibility closure.

- [ ] **Step 1:** Failing tests — a `derivation.transformations[]` chain materializes as a `reference` usage; two evidence lines sharing that chain are **not** flagged non-independent; the chain does not enter the plan-gate reproducibility closure.
- [ ] **Step 2:** Implement.

### Task P3.3: Provenance checks + strict inherit + sidecar assertion

**Files:** Modify `validate/checks/identity_context.py` (+ the register-run path); Test `test_check_identity_context.py`.

**Interfaces:** the provenance check is **split by lineage role** (Key decision 9): every `transform.dataset` / `proxy.via` must resolve to a real dataset entity and appear in the derived entity's `derivation.transformations[]` (reference-role), and every `proxy.sources[].dataset` must appear in the run's data `inputs` (`derivation.inputs`); either missing ⇒ error. Neither reference artifact is required in `derivation.inputs`. A mixed-build output with neither `proxy` nor `transform` errors (strict warning during the migration window). An optional run sidecar (`identity_context.yaml`) is checked against the contract and errors on disagreement. `from: input` under multiple inputs errors (requires `from: dataset:X`).

- [ ] **Step 1:** Failing tests for each truth-table row (design §Validation truth-table) — including that a `transform.dataset` present only in `derivation.inputs` (not `transformations[]`) is rejected, and vice-versa for a data source.
- [ ] **Step 2:** Implement.

### Task P3.4: Planning-surface + docs

**Files:** Modify `commands/plan-pipeline.md`, `commands/plan-analysis.md`, `docs/user-guide/entities.md`.

- [ ] **Step 1:** Add identity to the data-availability gate prose (declaration required for identity-bearing inputs; resolution at the publish boundary).
- [ ] **Step 2:** Full-suite green + ruff clean across both suites; `science validate` on a fixture workflow project.

---

## Phase P4 — MM30-critical pinned artifact builders (enabling)

> **Re-plan gate:** author the step-level detail for P4 once P2 lands (the resolver contract fixes the exact artifact shapes the resolver reads). The work packages below are the owned scope and definitions of done, not silently dropped.

- **WP P4.1 — assembly-registry build entrypoint.** Wire the existing `assembly_registry_build` logic to a `science-commons` recipe/entrypoint producing the seqcol-keyed registry (`GRCh38`, `GRCh37`/`hg19` at minimum) as a pinned, hash-verified datapackage. **DoD:** `resolve hg38`/`hg19` → seqcol digests offline.
- **WP P4.2 — gene-crosswalk-hgnc build entrypoint.** Same for the HGNC/NCBI/Ensembl gene crosswalk. **DoD:** `map GRCh37-symbol → GRCh38-symbol` resolves offline; `namespace: hgnc_symbol` resolves.
- **WP P4.3 — liftover chains consumption.** Confirm the resolver/`transform: liftover` path consumes the already-pinned `assembly-liftover-grch37-grch38`. **DoD:** `lift hg19 → hg38` runs offline against pinned chains.
- **WP P4.4 — cytoband-hg19 proxy reference.** Promote the UCSC hg19 cytoBand as a commons reference dataset usable as `proxy.via` (or resolve to keep it MM30-local — see design Open Questions). **DoD:** the t665 proxy `via` resolves to a real dataset entity.

---

## Phase P5 — MM30 as first fully-resolved consumer

> **Re-plan gate:** author the step-level detail for P5 once P3 + P4 land. Owned scope + DoD below.

- **WP P5.1 — retire the hardcoded species constant.** MM30 `scripts/shared/datapackage.py`: derive the `science.identity_context` stamp from entity identity instead of the literal `Homo sapiens/9606`. **DoD:** a non-human dataset can flow through the shared emitter with a correct stamp.
- **WP P5.2 — declaration-level backfill (batch).** `science dataset identity resolve` over the 255 entities: `taxon` + assembly label (or explicit `UNKNOWN`) for every identity-bearing entity; a batch report lists anything left `declared_unresolved` so nothing is silently exempt. **DoD:** strict declaration gate passes repo-wide.
- **WP P5.3 — resolve coordinate/gene datasets.** Resolve the datasets where P4 artifacts exist (GSE131651 hg38, GSE87585 hg19, the annotables/symbol path). **DoD:** those entities carry `resolution_status: resolved`.
- **WP P5.4 — workflow contracts.** Add `outputs[].identity` to coordinate-emitting workflows (expression normalization = `symbol_remap` gene transform; the 3D-genome ledger = cytoband `proxy`). **DoD:** `register-run` propagates; stamps checked.
- **WP P5.5 — t665 structural proxy + unblock.** Replace the t665 prose build caveat with the structured cytoband `proxy`; unblock the TAD / A-B-compartment axes previously deferred behind this effort. **DoD:** the t665 output declares a machine-visible proxy and the deferred axes are actionable.

---

## Final validation task

- [ ] Full test suite green in `science/` and `science/model/`; ruff format + check clean in both.
- [ ] `uv run --frozen science validate --verbose` clean on a fixture project exercising: declaration gate, stamp agreement, proxy/transform provenance, strict inherit.
- [ ] **Scale/real-data check:** run the resolver batch over MM30's 255 entities (real corpus); observe wall-clock + confirm graceful `declared_unresolved` where artifacts are absent; the batch report lists every unresolved entity (no silent exemptions).
- [ ] MM30: hardcoded species constant removed; t665 proxy structural; TAD/compartment axes unblocked.
- [ ] Commit per task; no AI-attribution trailers.

## Self-review checklist

- [ ] Resolution never touches the network in a reproducible path (socket-monkeypatch test present).
- [ ] `declared_unresolved` is always a legal, non-blocking authoring state; only the publish boundary requires resolution.
- [ ] The datapackage stamp is never treated as authoritative; disagreement is an error.
- [ ] Every `transform.dataset` / `proxy.via` / `proxy.sources[]` is provenance-checked against real workflow/run inputs.
- [ ] P4/P5 re-plan gates honored — no P4/P5 step executed before its P1–P3 dependency lands.
- [ ] Exact commons slugs (`assembly-registry`, `gene-crosswalk-hgnc`, `assembly-liftover-grch37-grch38`, `cytoband-hg19`) confirmed against `science-commons` before wiring.

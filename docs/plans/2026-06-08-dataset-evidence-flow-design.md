# Dataset Evidence Flow — Facet Design

**Date:** 2026-06-08
**Status:** Design (planning only — implementation held until `layout_version: 3`, per umbrella §7)
**Kind:** Facet design. Elaborates the dataset-grounding region of the umbrella
[`2026-06-08-epistemic-data-model-design.md`](./2026-06-08-epistemic-data-model-design.md).
**Sibling facet:** `epistemic-edges` ([`2026-06-08-epistemic-edges-design.md`](./2026-06-08-epistemic-edges-design.md)) — creates the evidence-lines this facet grounds.

> **Authority boundary.** Subordinate to the umbrella (itself subordinate to `h00`, beside the
> substrate). Reuses without replacing: `h00`; D-005/D-006; `docs/proposition-and-evidence-model.md`;
> and — critically for this facet — the **already-built A1/A2/B1/B2 dataset/independence machinery**
> (see §1.1). Where this doc and a reused authority disagree, the authority wins.

---

## 1. Framing: wire + populate + migrate (not build)

Issue 1 (umbrella) — *"can't resolve epistemic flow from single datasets"* — is **not** an
engine-building problem. The dataset taxonomy, structured usage model, usage materialization, and
independence derivation already exist and are merged. This facet's job is to **make the evidence-line
the carrier of dataset usage, populate that usage for the task-keyed MM30 corpus, and bring datasets
into the v3 entity layout** — then the existing machinery does the rest.

### 1.1 Reused (already-built) machinery — verified in code

| Piece | What it does | Where |
|---|---|---|
| **A1** `DatasetUsage` model | `{ref, role∈{analyzed,set_definition_source,validation_source,cited,upstream,training}, overlap∈{full,partial,unknown}}`; `Entity.dataset_usage: list[DatasetUsage]` on the base entity | `science_model/packages/schema.py:202`; `science_model/entities.py:333` |
| **A1** `source_class` / `derived_kind` | dataset taxonomy `observational`/`derived`/`reference` (+ `aggregate`/`transform`/`model_output`) | `science_model/entities.py:331–332`, validator `:274` |
| **A2** reference down-weight | reference-class evidence loses one ordinal step in winner selection | `belief.py:124–133`, `belief_weights.py:47` |
| **B1** usage materialization | emits `consumer → sci:hasDatasetUsage → node{dataset,role,overlap,source}` | `graph/dataset_usage.py`; `materialize.py:124,650` |
| **B2** independence derivation | reduces usage facts → commitment/candidate independence records → `independence_group` | `graph/dataset_independence.py` |
| **B2** belief reduction | collapses N-analyses-of-one-dataset to one winner per `independence_group`; excludes circular | `belief.py:reduce_units` ~145–179 |
| `dataset` entity | first-class **operational** `DatasetEntity` (`origin ∈ {external, derived}`) | `entity_registry.py:111`; `science_model/entities.py:594` |

**The only gaps** (this facet's scope):
1. `EvidenceLineEntity` does not yet carry `dataset_usage` (it has only `shared_dataset`/`shared_lab`/…
   observability tokens); the current convention authors usage on *paper* entities and derives line
   independence post-hoc. The umbrella locks the **line** as the carrier (§2).
2. No `task → dataset` mapping exists anywhere — `data_support` is `{task, description}`, datasets live
   only in prose (§3).
3. The 30 `mm30.v8.yml` datasets are not yet `entities/datasets/` files (no path policy; §4).

### 1.2 The seam to `epistemic-edges`

`epistemic-edges` migration creates each empirical evidence-line in a **staged** state
(`compiled=False`), excluded from the compiled graph/belief, precisely *because* `dataset_usage` is
unresolved. **This facet resolves `dataset_usage`, which flips those lines to `compiled=True` and
admits them to belief.** The two facets divide at the evidence-line: `epistemic-edges` owns the
proposition + the line's stance/type/quantitative-result; this facet owns the line's dataset grounding.

---

## 2. Evidence-line `dataset_usage` — first-class & required

- **The evidence-line is the durable carrier.** Empirical evidence-lines carry
  `dataset_usage: list[DatasetUsage]` **directly** (reusing the A1 model on the base entity; surfaced
  on `EvidenceLineEntity`). The line — not a paper, not a task — is the single subject whose dataset
  usage grounds belief. This makes MM30 the first project to author line-level `dataset_usage`, which
  the framework already supports.
- **Required for compilation of empirical lines.** An empirical evidence-line
  (`evidence_type == empirical_data_evidence`) with empty `dataset_usage` is a **staging artifact,
  excluded from the compiled graph/belief** (the `compiled=False` gate from `epistemic-edges` §8.4).
  Resolving `dataset_usage` is the precondition that compiles it. Literature/expert lines need no
  `dataset_usage` and compile immediately.
- **`role` defaults to `analyzed`**; non-`analyzed` roles (`validation_source`, `set_definition_source`,
  `cited`) are curated exceptions recorded in the resolution table (§3). `overlap` defaults to
  `unknown` unless the resolver can establish `full`/`partial`.
- **Reuse, don't fork.** B1 materializes the line's `dataset_usage`; B2 derives `independence_group`;
  A2 down-weights reference-backed lines — all **verbatim**. No new aggregation logic.

---

## 3. `task → dataset` — a migration resolution table (input, not authority)

`data_support` items are `{task, description}` with **no structured dataset field**; ~90 distinct
tasks are cited across the 15 DAGs; datasets appear only in prose (`"GSE19784, GSE24080, … MMRF"`).
Resolution is a **migration concern**, modeled as an input transcript — never a model authority.

**The abstraction (normative):**
- **Task key = migration handle.** It explains *where legacy evidence came from*. It is **not** the
  epistemic carrier.
- **`task → dataset` map = curated migration input.** A workflow-owned, checked-in artifact —
  *reviewable provenance for the migration process*, treated like a lockfile / input transcript. It is
  **not** consumed by belief, the renderer, or any future epistemic query.
- **`evidence-line.dataset_usage` = durable truth.** After migration every empirical line owns its
  dataset usage directly; B1/B2 read **only** this field.

**Mechanics:**
- **Auto-seeded** from task prose, edge `data_support`/`lit_support` prose, `GSE\d+` / `MMRF` / external
  identifiers, and `mm30.v8.yml` registry hints — then **human-curated**.
- **Loud-fail gate 1:** any empirical `data_support` task that does not resolve to ≥1 dataset usage
  halts migration for curation (no silent drop of the dataset grain).
- **Loud-fail gate 2:** any resolved dataset that does not map to a canonical `dataset:` entity (§4)
  halts — forcing the dataset entity to exist (incl. externals, §4).
- **Write path:** the resolver writes durable `dataset_usage` onto each empirical evidence-line, and
  records the originating task key as **provenance** — `evidence-line prov:wasDerivedFrom task:<id>` in
  the **PROV-O provenance graph** (reusing `materialize.py`'s existing `prov:wasDerivedFrom` emission),
  *never* as a `cito:` belief edge. The task key is audit/debug trace, structurally incapable of
  entering belief.
- **DRY:** a task cited by N edges resolves once; the N lines reference the same resolved usage.
- **Escape hatch:** per-line override (umbrella option-3, restricted) for genuinely ambiguous cases
  where one task analyzed different datasets for different claims.
- **Post-migration:** consumers must not consult the table; it remains only as an auditable artifact.

---

## 4. Dataset entities — generated projection + externals

`dataset_usage` refs point at `dataset:<slug>` entities; gate 2 (§3) requires they exist. Today the 30
datasets live only in `mm30.v8.yml` (operational SSOT: paths, phenotypes, identifiers), and there is no
`entities/datasets/` path policy.

- **Generated projection (the 30 pipeline datasets).** `mm30.v8.yml` stays the operational SSOT.
  `entities/datasets/<slug>.md` `DatasetEntity` files are **generated from it** (a compile step), with:
  - **identity** `dataset:<config-key slug>` (`GSE19784 → dataset:gse19784`; `MMRF → dataset:mmrf`);
  - **`source_class`** (+ `derived_kind`) added **minimally to the registry** (or a sibling) and
    projected onto each entity — GEO/MMRF cohorts → `observational`; pipeline-derived artifacts
    (fmap/meta/coex) → `derived` + `derived_kind`; external reference sets (MSigDB/annotables) →
    `reference`;
  - a **drift-check gate** (the workbench fixpoint pattern): committed `entities/datasets/` must equal
    the projection of the registry; CI regenerates and diffs.
  This adds the missing `dataset` entry to `_BUILTIN_MARKDOWN_POLICIES` (`slug` strategy). One
  operational SSOT, one generated epistemic projection — no parallel dataset registry.
- **External datasets (beyond the 30).** Evidence that re-analyzes a dataset *not* in `mm30.v8.yml`
  (e.g. `t124`'s Ren-2019 `GSE136410`) gets a `DatasetEntity` with **`origin: external`**, registered
  as needed (not generated from the registry). Gate 2 forces their creation rather than letting the
  dataset grain vanish. The dataset-entity universe = **30 generated pipeline datasets + externals
  analyzed by evidence**.

---

## 5. Independence — derived, the Issue-1 payoff

No design here; it falls out once §2 is populated:
- Lines sharing a dataset → B2 derives a shared-source `independence_group` → `reduce_units` keeps one
  winner (down-weighting N-analyses-of-one-dataset).
- Lines across distinct datasets → stay independent → each contributes.
- Reference-backed lines → A2 ordinal down-weight.

This is exactly the *N-independent-datasets vs N-analyses-of-one* distinction Issue 1 demanded, and the
per-dataset breadth the paused web-app viewer needs — produced by populated `dataset_usage`, not by
counting task-keyed items as a dataset proxy.

**Consideration (not a mechanism this facet invents):** a single line may analyze multiple datasets
(`t091`'s 5-dataset replication → one line, `dataset_usage` length 5). That intra-line breadth is
captured in the list; whether/how it *lifts the line's strength* is belief-engine territory — flagged,
not designed here (see §9).

---

## 6. Framework vs MM30 split (mirrors `epistemic-edges`)

- **Framework (`~/d/science`):** surface `dataset_usage` on `EvidenceLineEntity` + the
  required-for-compiled-empirical rule; add the `dataset` path policy; generic dataset-from-registry
  **generation + drift-check** tooling; the two **resolver loud-fail gates** as validation checks; the
  `prov:wasDerivedFrom` task-trace wiring. (Much of the staging/compiled plumbing is shared with the
  `epistemic-edges` framework plan — see that plan's Tasks 1c/2c/3b; this facet's framework plan adds
  the dataset-specific pieces and avoids duplicating them.)
- **MM30 (`~/d/r/mm30`):** the curated `task → dataset` resolution table data; the `source_class`
  registry extension + generated `entities/datasets/`; external-dataset registration; and **filling
  the staged evidence-lines** `epistemic-edges` created. Deferred to the MM30 migration plan, gated on
  this facet's framework plan **and** the `epistemic-edges` framework plan landing on v3.

---

## 7. Migration (design-level; gates the `-plan` must enforce)

1. **Generate dataset entities** from `mm30.v8.yml` (+ `source_class` extension); drift-check gate.
2. **Seed** the `task → dataset` table automatically; **curate**; enforce loud-fail gate 1 (every
   empirical `data_support` task resolves) and gate 2 (every resolved dataset has a canonical entity,
   registering externals with `origin: external`).
3. **Write** `dataset_usage` onto each empirical evidence-line + the `prov:wasDerivedFrom task:<id>`
   trace; flip resolved lines `compiled=False → True`.
4. **Materialize + derive** (B1/B2 automatic); verify independence grouping on a spot-check set
   (e.g. all MMRF-only lines collapse to one winner; cross-GEO lines stay independent).
5. **No silent drops**; subagent-driven; the resolution table committed as an auditable lockfile.

---

## 8. Conformance summary

- **Umbrella:** one grounding path `dataset →(dataset_usage)→ evidence-line →(cito)→ proposition`; no
  direct dataset→proposition edge; datasets are operational (no belief).
- **A1/A2/B1/B2:** reused verbatim; this facet only *populates* their inputs and *surfaces*
  `dataset_usage` on the line.
- **Prime directive:** the resolution table is a migration input (lockfile-like), not a parallel store;
  `mm30.v8.yml` stays the single operational dataset SSOT with one generated projection; the task key
  is provenance, never belief.
- **`epistemic-edges` seam:** this facet flips staged empirical lines to compiled; the mandatory-
  `dataset_usage`-for-compiled invariant holds at all times.

---

## 9. Risks & open questions

1. **Resolution coverage / curation cost.** ~90 tasks, many multi-dataset; prose seeding helps but
   curation is real. Loud-fail gate 1 prevents silent grain loss but means migration blocks until every
   empirical task resolves. Budget curation explicitly in the MM30 plan.
2. **External-dataset sprawl.** Re-analyses cite external datasets (`GSE136410`, …) needing `origin:
   external` entities; the count is unknown until seeding runs. Gate 2 surfaces them; ensure the plan
   has a lightweight external-registration path so they don't become a bottleneck.
3. **`role`/`overlap` accuracy.** Defaulting `role=analyzed`, `overlap=unknown` is safe but coarse;
   wrong `overlap`/`role` mis-feeds B2 (e.g. a `set_definition_source` mis-tagged `analyzed` could
   fabricate independence). Curate roles for non-`analyzed` cases; spot-check B2 output (§7.4).
4. **Intra-line multi-dataset breadth → strength** (§5) is unresolved at the belief-engine level: a
   5-dataset single line and a 1-dataset single line currently differ only in `dataset_usage` length,
   which B2 (inter-line) does not reward. If single-line breadth should raise strength, that is a
   belief-engine change — out of this facet's scope; record for the engine owners.
5. **Registry `source_class` extension.** Adding `source_class`/`derived_kind` to `mm30.v8.yml` (or a
   sibling) must not perturb the pipeline that reads the registry; prefer an additive sibling/section
   the pipeline ignores. Confirm against the config loader before implementing.
6. **v3 timing.** Like `epistemic-edges`, implementation is gated on v3 (entity layout for
   `entities/datasets/`, compiled-graph contract for staging). Planning proceeds; implementation holds.

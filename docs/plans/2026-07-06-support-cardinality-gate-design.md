# Derived-Dataset Support-Cardinality Gate — Design

- **Status:** Draft (from MM30 t840/thread-C post-mortem, 2026-07-06)
- **Date:** 2026-07-06
- **Scope:** `science` framework only (contract field + produced stamp + one `validate` check + docs). No `science-commons` work, no backfill of existing datasets, no CLI surfacing.
- **Depends on:** the `workflow outputs[].identity` contract and its derived-datapackage stamp (bio-identity adoption layer), the capability-fit gate (`datasets/capabilities.py`, `validate/checks/dataset_capabilities.py`), and the two-level-strictness precedent set by both.
- **Sibling of:** `2026-07-01-reproducibility-gate-v1-design.md`. Same shape: the framework already answers one readiness question and silently conflates it with a different one; this design adds the missing distinction and makes it bite.

## Purpose — the invariant

> A derived dataset that **aggregates over multiple upstream contributors** must declare a
> **support floor**, and must not pass validation (or the plan gate) when its
> producer-stamped **observed support** falls below that floor — or when an output declared as
> aggregating ships **no support stamp at all**. "One of N" and "zero rows" become loud,
> declared outcomes, never silent successes.

Everything here serves that one sentence. The framework already answers *"does this dataset
**provide** the capability this analysis needs"* (capability-fit) and *"can an independent third
party **regenerate** it"* (reproducibility gate). It does **not** answer *"did this aggregation
actually rest on the number of contributors it is supposed to."* Those are different questions,
and conflating "the rule produced an output" with "the output aggregates what it claims to" is
what let a k=1 meta-analysis pass every automated check.

## Motivating failure

MM30 runs cross-cohort meta-analysis over ~30 transcriptomic datasets. An incomplete registry
migration — a phenotype-category enum split (`survival` → `survival_os` / `survival_pfs`) — left
five cohorts declaring the *old, now-unregistered* category value. The manifest builder treated
"unregistered category" as **skip**, not **error**, so those five cohorts' survival associations
never reached the merge. The overall-survival meta-analysis silently collapsed to **k=1** (a
single cohort, GSE24080).

Nothing failed. Every stage ran green:
- the fassoc merge produced its feather;
- the meta-stage survival scores produced theirs;
- the standardized-metafor tables produced theirs;
- downstream rankings, benchmarks, and reports all consumed a "survival meta-analysis" that was
  really one cohort wearing a meta-analysis's clothes.

The collapse surfaced **only** because an unrelated feature (a prediction-interval replication
gate) happened to compute and report per-gene contributor counts (`num_present`, `k`). A human
noticed `k=1` where `k=5` was expected. Absent that incidental instrumentation, single-cohort
"meta-analysis" rankings would have propagated into interpretations and claims. Worse, the same
semantic filter was implemented **twice** in independent code paths (a config category-map and a
string heuristic), so the two paths could — and did — disagree about membership, and the
regeneration had to touch both.

The framework had no representation of the property that actually mattered: **expected support
cardinality**. This design adds exactly that, and makes it bite at validate/plan time.

## The gap in the current model

`capability_fit(required, provided)` is **binary and presence-only**: does *some* provided
capability set satisfy *some* required set. It cannot express "and the aggregation must draw on at
least N sources that provide it." The capability check (`evaluate_dataset_capabilities`) walks
reachability and warns when a reached dataset declares no `provided_capabilities` — but a dataset
that provides everything and an aggregation that used one of thirty both read as fully "fit."

Support cardinality is a property of the **produced data**, not of entity frontmatter, so the gate
cannot be a pure graph check — the framework does not (and should not) read parquet. The design
resolves this the same way the identity layer already does: **the producer stamps it, the framework
verifies the stamp against a declared floor.**

## Recommended approach

Three pieces, each riding rails that already exist.

### 1. Declared support floor (contract)

Add a new optional `support` field to `WorkflowOutput` (`packages/schema.py`), a sibling of the
existing `identity` field. `WorkflowOutput` is `extra="forbid"`, so this is a real schema addition
(a `WorkflowOutputSupport` model, itself `extra="forbid"`), not a free-form key — exactly how
`identity: WorkflowOutputIdentity | None` was added. The declaration mirrors the real
`outputs[]` shape (required `slug`/`title`, `resource_names`):

```yaml
outputs:
  - slug: survival-os-combined
    title: Survival OS combined meta-analysis scores
    resource_names:
      - survival_os_combined_gene
      - survival_os_combined_gene_set
    identity: { ... }              # existing WorkflowOutputIdentity
    support:                        # new WorkflowOutputSupport
      unit: dataset                # Literal[dataset|cohort|sample|source]; schema-validated
      min: 3                       # int >= 1; fail-closed floor; below this the output is untrustworthy
      expected: 5                  # optional int >= min; below expected but >= min → advisory WARN
```

`min` is the hard floor (blocks). `expected` is an optional soft target (advisory), which catches
"we lost two cohorts but stayed above the floor" — the near-miss a hard floor alone misses. Because
`unit` is a schema `Literal`, an unknown *declared* unit is a model-validation error, not a check
finding (a stamped unit that disagrees is a check finding — see below).

### 2. Produced support stamp (observation) — explicit handoff

Observed support is a **runtime fact only the producing run knows**, so — unlike
`identity_context`, which `register-run` *derives* from the `outputs[]` declaration plus run
frontmatter — it cannot be resolved from declarations. It must be **emitted by the run and carried
through `register-run`**. Current identity stamping happens in
`datasets_register.py::write_per_output_datapackages`, which reads the **run-aggregate
datapackage** (`_read_run_aggregate_datapackage` → `by_name = {r["name"]: r ...}`) and writes each
per-output view, attaching identity as `out_dp["science"] = {"identity_context": derive_stamp(...)}`.
The producer writes neither.

The handoff therefore has two hops:

1. **Producer → run-aggregate.** When the workflow writes the run-aggregate datapackage, each
   aggregating resource carries an observed-support field in its resource custom metadata under the
   existing `science` namespace:

   ```yaml
   # run-aggregate datapackage resource
   - name: survival_os_combined_gene
     path: meta/scores/combined/survival_os/gene.feather
     science:
       support: { unit: dataset, observed: 5 }
   ```

2. **`register-run` → per-output datapackage.** `write_per_output_datapackages` copies the
   resource(s)' `science.support` onto the per-output datapackage, merged into the same `science`
   block it already writes for identity — **nested under `science`, not top-level** (aligning with
   finding: current shape is `science.identity_context`, so this is `science.support`):

   ```yaml
   # per-output datapackage.yaml written by register-run
   science:
     identity_context: { ... }        # existing
     support: { unit: dataset, observed: 5 }
   ```

   **Multi-resource rule (no main/ancillary marker exists).** `outputs[].resource_names` is a flat
   list with no way to distinguish a main aggregating resource from an ancillary one, so v1 takes the
   fail-closed reading: for an **opted-in** output (one declaring a `support` block), **every** listed
   resource must carry `science.support`, and the output's observation is the **min** of their
   `observed`. If **any** resource in an opted-in output carries no `support`, `register-run` records
   `science.support: { observed: null }` for the output, which the check treats as `stamp-missing`
   (loud). This over-requires — an ancillary, non-aggregating resource bundled into an opted-in output
   must also stamp support — but over-requiring fails safe; the alternative (min over only the
   stamped resources) reintroduces exactly the silent-collapse hole this gate exists to close. A
   later refinement can add an explicit scoped resource list to exempt ancillaries (Non-goals);
   until then, split ancillary resources into a non-opted-in output.

The framework never inspects parquet; it trusts the producer's stamp, exactly as it trusts the
identity stamp. A run that declares a floor but emits no observation is the loud-failure case, which
is what turns "silent k=1" into "blocked build."

### 3. Verification (`validate` check: `aggregation-support`)

**Join path (floor ↔ observation).** The floor lives on `workflow.outputs[].support`; the
observation lives on a derived dataset's per-output `datapackage.yaml` (`science.support`). The check
associates them per derived dataset:

1. Take each derived dataset whose `derivation.workflow` (`DerivationBlock.workflow`,
   `packages/schema.py`) resolves to a workflow entity.
2. Resolve its **output slug** — the per-output datapackage is written at `<run>/<slug>/datapackage.yaml`
   by `write_per_output_datapackages`, so the slug is the datapackage's parent-dir name (equivalently
   the dataset's declared output-slug reference).
3. Look up `workflow.outputs[slug].support` for the floor; read `science.support` from that
   datapackage for the observation; compare.

A derived dataset whose workflow output declares no `support` block is simply not evaluated.

The check is a sibling of `evaluate_dataset_capabilities`. Severities map to the confirmed exit rule
(`validate/cli.py`: `if result.errors or result.gated: ctx.exit(1)`) — "block" means **emit
`Severity.ERROR`**, unconditionally once the output opts in (the declared `support` block *is* the
opt-in; blocking does **not** depend on `ctx.strict`). Malformed and mismatched stamps get their own
named `ERROR` codes rather than falling through to a generic `validate.check-error`:

| Code | Condition | Severity |
|---|---|---|
| `aggregation-support.below-floor` | `observed < min` | **ERROR** (exit 1) |
| `aggregation-support.stamp-missing` | `support` block declared; propagated `observed` is null/absent (incl. any resource unstamped) | **ERROR** (exit 1) |
| `aggregation-support.malformed-stamp` | stamped `observed` is not a non-negative integer (`"5"`, `true`, `-1`, float) | **ERROR** (exit 1) |
| `aggregation-support.unit-mismatch` | stamped `unit` ≠ declared `unit` (incl. an unknown stamped unit) | **ERROR** (exit 1) |
| `aggregation-support.below-expected` | `min <= observed < expected` | `WARN` |

### Strictness = opt-in (do not break existing projects)

The gate is **fail-closed only for outputs that opt in by declaring a `support` block** — that
declaration is the sole strictness control, so no `--strict` coupling and no flag day. Outputs with
no `support` block are never evaluated and never blocked. This is the same adopt-when-ready posture
that let the capability gate ship. (There is deliberately **no** auto-`undeclared` nudge in v1 — see
Non-goals for why and what a future signal would need.)

### What `observed` counts (and what it does not)

`observed` is the count of **distinct contributing units actually incorporated into the
artifact after all semantic filters** — e.g. the number of cohort columns present in the merged
effects for that category. It is an **artifact-level structural invariant** ("this meta-analysis was
built from N cohorts"), deliberately **not** a per-row statistic.

In particular, do **not** stamp `max(num_present)` over rows: a single gene present in all cohorts
would let the artifact claim `observed = 5` while most genes rest on one cohort. The correct artifact
claim is the contributing-unit count wired into the aggregation; per-row sparsity (a gene backed by
`k=1` even though the artifact spans five cohorts) is a **distinct, row-level invariant** out of
scope here (see Non-goals). If a producer wants to claim a stronger row-level guarantee, the honest
artifact stamp for that is a row-quantile (e.g. `observed = min` or a low percentile of per-row
contributor counts), and the design permits that — but it must reflect the invariant actually being
claimed, never the best-case row.

### Zero is first-class

`observed: 0` (and, at the row level, an empty result table) is a declared, loud outcome under this
gate — never a crash and never a green pass. This subsumes a second MM30 lesson (an audit script
that *crashed* on an empty input table): "empty" should be representable and reportable, not
exceptional.

## Non-goals (deferred fast-follows)

Each only *reads* the contract this design introduces, so it slots in later without reopening the
schema:

- **The `aggregation-support.undeclared` auto-nudge.** Deferred deliberately: there is no
  machine-detectable definition of "this output *looks* aggregating," so an auto-nudge would be
  either noisy or silently ineffective. A future demand-gated nudge must key on an **explicit
  producer signal**, not a heuristic — e.g. an `outputs[].aggregates: true` marker (or a
  reduction-op token in the transformation record) that says "this output reduces over contributors,"
  at which point a *missing* `support` block becomes a demand-gated WARN. Until such a signal exists,
  v1 is purely opt-in.
- **Row-level per-contributor completeness.** The artifact stamp claims a structural
  contributing-unit count, not that every row is backed by that many contributors. A per-row support
  distribution check (how many genes rest on `k=1`) is a separate, finer instrument — likely a
  project-level Snakemake assertion or a later row-quantile stamp, not this gate.
- **Scoped resource list on an output.** v1 requires *every* resource in an opted-in output to carry
  a support stamp (§ Multi-resource rule), which over-requires ancillary resources. A later
  `outputs[].support.resources: [...]` (or a per-resource `aggregating: true` marker) could scope the
  requirement to the genuinely-aggregating resources. Deferred so v1 needs no new resource-level
  marker; the workaround is to keep ancillary resources in a separate, non-opted-in output.
- `dataset list` / `dataset prioritize` columns showing observed vs declared support.
- Backfill / auto-inference of floors for existing outputs (they stay undeclared → non-blocking).
- Auto-deriving `observed` by the framework reading data (violates the entity/data boundary; the
  producer stamps it, `register-run` propagates it).
- Cross-output *staleness* enforcement (a fresh merge with stale downstream scores). Related and
  real — see Aligned Observations — but it belongs with `graph/freshness.py`, not here.

## Alternatives considered

**A. Pure graph check (count reached contributor entities).** Rejected: reachability counts
*declared* upstreams, not what the run *actually aggregated*. The MM30 failure had all five cohorts
reachable in the graph; only the data collapsed. A graph count would have read k=5 and passed.

**B. Framework reads the produced data to count support.** Rejected: breaks the standing boundary
that `validate` operates on entities/graph/stamps, not parquet contents; also couples the framework
to every producer's file schema. The stamp indirection keeps the producer authoritative.

**C. Leave it to each project's Snakemake assertions.** Rejected as the *primary* answer: that is
exactly the status quo that failed — the check existed only by luck in one project. A first-class
contract makes "caught by luck" into "caught by construction," and every aggregation-heavy consumer
(MM30, the therapeutics child, health/meta) inherits it. Project-level assertions remain useful for
row-level invariants below the framework's resolution.

## Aligned observations (secondary lessons — not v1 scope)

Captured so they are not lost; each is a separate, smaller piece.

- **Single-resolution of registry partitions.** The MM30 bug spanned two code paths because "which
  columns are `survival_os`" was defined twice (a config map and a `grepl` heuristic). The
  framework already champions single-SSOT; a cheap `validate` lint could flag "a registry category
  is filtered by ad-hoc string match rather than resolved membership." Discipline + optional lint,
  not a new primitive.
- **Fail-closed migration triage for *value*-level enums.** The substrate/v3 work already fails
  closed on unclassified *entities* (triage classifier, lone-stub/shadow WARNs). The same rigor
  should extend to config/registry **enum value** migrations: no member may silently fall through
  to an unregistered value and be dropped as "skip." This reuses existing muscle at a new level.
- **Input-declaration completeness (hard problem, name it).** A downstream rule read survival
  scores it did not *declare* as inputs, so mtime triggers never fired and it silently served stale
  output. Detecting "declared inputs ⊇ actually-read inputs" generally needs static analysis or
  runtime I/O tracing. Worth flagging as a known gap; not worth a speculative build now.

## Testing

The check logic is only one of three surfaces; the contract and the stamp handoff each need their
own coverage (the original draft tested only the check):

**Contract parsing** (`WorkflowOutputSupport` on `WorkflowOutput`, `extra="forbid"`): `unit`
(`Literal`)/`min`/`expected` accepted; `min` required when the block is present; `min >= 1`;
`expected < min` rejected; an unknown declared `unit` is a model-validation error; a stray key is
rejected by `extra="forbid"`; absent block → output not evaluated.

**`register-run` propagation** (`write_per_output_datapackages`): a run-aggregate resource carrying
`science.support.observed` lands as `science.support` on the per-output datapackage; a multi-resource
output reduces to **min**; if **any** resource lacks `support`, the output propagates `observed: null`
(not a silent drop); identity and support coexist in the same `science` block.

**Join path** (floor ↔ observation): a derived dataset with `derivation.workflow` resolves to its
workflow and output slug (datapackage parent dir); floor read from `outputs[slug].support`,
observation from that datapackage. A dataset whose output declares no floor is skipped; a floor whose
datapackage is absent → `stamp-missing`.

**Check logic** (`aggregation-support`): `observed < min` → `below-floor` `ERROR`; declared floor with
null/absent observation → `stamp-missing` `ERROR`; `observed` = `"5"`/`true`/`-1`/float →
`malformed-stamp` `ERROR`; stamped `unit` ≠ declared `unit` → `unit-mismatch` `ERROR`;
`min <= observed < expected` → `below-expected` `WARN`; `observed >= expected` → clean; `observed: 0`
→ `below-floor` `ERROR` loudly; output with no `support` block → no finding.

**CLI exit behavior** (`validate/cli.py`): a project with a below-floor opted-in output exits **1**
(via `result.errors`); a below-expected-only project exits **0** with a WARN; a project with no
opted-in outputs is unaffected. Confirms blocking is opt-in-driven, not `--strict`-driven.

**End-to-end fixture** reproducing the MM30 shape: an output declaring `min: 3` whose run stamps
`observed: 1` → `aggregation-support.below-floor` `ERROR`, exit 1 — i.e. the k=1 collapse fails at
validate time.

## Success criteria

- An aggregating output that collapses below its declared floor **cannot** pass `validate` (strict)
  — the MM30 k=1 collapse would have failed at validate time, before any downstream consumption.
- Zero new blocking findings for existing projects until they declare a `support` block.
- The contract, stamp, and check reuse the identity-stamp and capability-fit rails; no parallel
  mechanism, no data reads in the framework.

## Implementation notes

- **Contract:** add `support: WorkflowOutputSupport | None = None` to `WorkflowOutput`
  (`packages/schema.py`), beside the existing `identity` field; `WorkflowOutputSupport` is
  `extra="forbid"` with `unit: Literal["dataset","cohort","sample","source"]`, `min: int (ge=1)`,
  `expected: int | None (ge=min)`. Distinct from the stamp: the declaration is the floor, the stamp
  is the observation.
- **Stamp namespace:** the per-output datapackage carries it as `science.support` — nested in the
  same `science` block `write_per_output_datapackages` already writes `identity_context` into
  (`datasets_register.py`), **not** a top-level key. Producer emits it on the run-aggregate
  resource under `science.support`; `register-run` reduces (min over resources) and copies it.
- **Check:** lands as `validate/checks/aggregation_support.py`, registered next to
  `dataset_capabilities.py`; codes namespaced `aggregation-support.*`; below-floor / stamp-missing
  emit `Severity.ERROR` (validate exits on `result.errors`), below-expected emits `WARN`.
- **MM30 first consumer:** the survival meta outputs already know their contributing-cohort set. The
  producing rule stamps `observed =` the **count of contributing cohort columns wired into the
  category aggregation** (5 for OS, 4 for PFS) — *not* `max(num_present)`, which would report the
  best-case gene and mask sparse rows (see "What `observed` counts"). Declared floors: OS
  `min: 3, expected: 5`; PFS `min: 3, expected: 4`. Under this gate, the original k=1 collapse
  stamps `observed: 1 < min: 3` → `ERROR` at validate time, before any downstream consumption.

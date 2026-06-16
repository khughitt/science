# Dataset-QA Seam — Design (Patchwork Kernel Spec 5)

**Status:** proposed
**Slice:** Spec 5 (Proposition, Evidence, and Belief Semantics) — "dataset-QA seam"
**Predecessors:** BeliefPolicy keystone (Slice A), authored-confidence-as-input (Slice B),
typed-evidence-vocabularies. This slice plugs into the same `BeliefPolicy` socket and
mirrors Slice B's gate/ceiling/refutation-symmetry shape.

## Goal

Make schema-driven QA outcomes inform belief. When an empirical evidence line rests on a
dataset whose **structural** QA failed, belief in the proposition that line supports cannot
exceed a configured ceiling — *unless* QA-clean support stands on its own.

## Governing principle

> *Consume the typed dataset/data-resource schemas and schema-driven QA outputs rather than
> defining a parallel dataset model.* (Spec 5 key decision, kernel architecture §Subsystem specs)

The dataset entity **points at** the QA report produced by `science datasets qa`; it never
re-authors the verdict. The QA layer (`science_qa`, the typed `ResourceDescriptor` schema)
stays the single source of truth. Belief consumes the verdict; it computes no checks of its own.

## Current state — the seam is missing

- `DatasetEntity` (`model/src/science_model/entities.py:684`) has **no link** to its
  data-resource schema or to any QA outcome.
- Evidence lines declare `dataset_usage: [{ref: dataset:<slug>, role, overlap}]`
  (`model/.../packages/schema.py` `DatasetUsage`).
- Belief reads `dataset_usage` only **indirectly** — `dataset_independence.py` turns shared
  datasets into `independence_group`s for shared-source collapse. Dataset *quality* is never
  inspected (`belief.py` comment: "dataset_usage is NOT inspected").
- `science datasets qa` produces a clean `PackageRunResult` (per-resource `status` ∈
  ok/fail/blocked/skipped/not-applicable, plus `package_structural_failed`, plus structural
  and distribution `Flag`s) and can persist it to `qa_report.json` via `--report-dir`. That
  output is never read back into the graph.

## Scope decisions (locked with the user)

1. **QA sourcing — reference a persisted report.** The dataset entity references the
   `qa_report.json` that `science datasets qa --report-dir` already writes. The build reads
   the structural verdict cheaply; QA stays an on-demand step (no heavy tabular reads during
   every `validate`/graph build); works when data lives outside the repo
   (commons / `~/d/science-commons-data`, remote).
2. **Belief mechanism — ceiling** (not gate, not penalty). A structural QA failure caps
   belief magnitude; the evidence still corroborates but cannot manufacture high-grade belief.
   Mirrors `authored_only_ceiling`.
3. **Signal grain — structural verdict only.** Structural flags are deterministic and
   build-fatal (contract violations: bounds, uniqueness, required columns). Distribution
   flags are dispositionable/noisier and would pull in disposition-state modeling — **deferred**.

## The two-sided contract

```
evidence-line ──dataset_usage.ref──▶ dataset:<slug> ──qa_report──▶ qa_report.json
     │  (dependence role)                  │
     │                                      └─ package_structural_failed ──▶ SCI_NS.qaStructuralFailed (bool on dataset node)
     │
     └─ build stamps SCI_NS.qaFailedDataset on the line for each dependence-role
        dataset it rests on whose verdict is failed
                              │
                              ▼
        EvidenceUnit.qa_failed_datasets ──▶ ceiling + refutation symmetry in aggregate_belief
```

## Data-model changes

### 1. `DatasetEntity.qa_report` (model)
New optional field on `DatasetEntity`:

```python
qa_report: str = ""   # project-root-relative path to a qa_report.json from `science datasets qa`
```

Empty (default) → dataset has no consumed verdict; no QA effect anywhere. This keeps the
slice behavior-neutral until a dataset opts in.

### 2. `EvidenceUnit.qa_failed_datasets` (tool, `graph/belief.py`)
New **last** field for positional stability (after `confidence`, exactly as Slice B added
`confidence` last):

```python
qa_failed_datasets: tuple[str, ...] = ()   # dependence-role datasets this unit rests on whose structural QA failed
```

Recognition predicate:
```python
def is_qa_failed(u: EvidenceUnit) -> bool:
    return bool(u.qa_failed_datasets)
```

### 3. `BeliefResult` diagnostics (`graph/belief.py`)
Mirror the authored fields:
```python
qa_dataset_capped: bool = False
qa_failed_datasets: tuple[str, ...] = ()   # union over capped support units, sorted — names the failed dataset(s)
```

### 4. `BundleBeliefResult.qa_dataset_capped` (`graph/bundle_belief.py`)
OR-rollup across members, exactly as `authored_capped`.

## Materialization (`graph/materialize.py`, new `graph/dataset_qa.py`)

A new layer runs in `_derive_*` orchestration immediately **after**
`emit_dataset_independence_records` (`materialize.py:291`):

```python
emit_dataset_qa_layer(knowledge, provenance, sources)
```

`graph/dataset_qa.py` does two things:

**(a) Materialize each dataset's verdict.** For every `DatasetEntity` with a non-empty
`qa_report`:
- Resolve the path relative to the project root.
- **Fail-loud** if declared but missing/unreadable/not valid JSON — `raise` a clear error
  naming the dataset slug and path (no silent fallback to "clean").
- Read `package_structural_failed` (bool) from the report.
- Stamp the dataset node:
  - `dataset ──SCI_NS.qaStructuralFailed──▶ Literal(bool)`
  - `dataset ──SCI_NS.qaReport──▶ Literal(path)` (audit: which report was consumed)
  - `dataset ──SCI_NS.qaReportHash──▶ Literal(sha256-of-report-file)` (audit: exact verdict consumed)
  - `dataset ──SCI_NS.qaFailedResource──▶ Literal(name)` for each resource whose `status == "fail"` (diagnostics)

**(b) Stamp evidence lines.** Reusing the existing usage machinery
(`read_dataset_usage_facts` / `reduce_usage_facts` / `DEPENDENCE_ROLES` from
`dataset_independence.py`), for each evidence line find the **dependence-role** datasets it
rests on via **direct/virtual** ancestry (`_ancestor_path` ∈ {"direct","virtual"}), intersect
with structurally-failed datasets, and stamp:
```
line ──SCI_NS.qaFailedDataset──▶ dataset   (one per failed dependence dataset)
```
`_read_unit` reads these into `EvidenceUnit.qa_failed_datasets`.

> **Path scope:** only direct (the line, or a paper it `prov:wasDerivedFrom`, analyzed the
> dataset) and virtual gene-set members count. `indirect-bears-on` linkage is **deferred** —
> too tenuous for a quality ceiling in a first slice. Only **dependence** roles
> (`analyzed`/`set_definition_source`/`training`/`upstream`) trigger the ceiling; a merely
> `cited`/`validation_source` dataset failing QA does not cap belief.

## Belief mechanism (`graph/belief.py`)

### Refutation symmetry — `is_qualifying_direct_test`
Add a `qa_failed` exclusion exactly parallel to Slice B's authored exclusion:

```python
def is_qualifying_direct_test(u, *, policy=DEFAULT_BELIEF_POLICY) -> bool:
    return (
        u.evidence_role == policy.direct_test_role
        and not is_proxy_gated(u, policy=policy)
        and not is_authored_assertion(u, policy=policy)
        and not is_qa_failed(u)          # NEW
    )
```

Because `is_qualifying_direct_test` feeds both `clean_direct_test` (the WELL_SUPPORTED gate)
and `is_decisive_refutation`, this single change delivers what the user asked for: a
failed-QA empirical dispute cannot be a decisive refutation, and a failed-QA support unit
cannot be the direct test that earns WELL_SUPPORTED. (Backed-by-QA-clean = `is_qa_failed`
False, so a clean direct test still qualifies.)

### The ceiling — applied after the refutation cap and after the authored ceiling

```python
qa_dataset_capped = False
qa_failed_support = [u for u in support if is_qa_failed(u)]
if qa_failed_support:
    clean_support_units = [u for u in support if not is_qa_failed(u)]
    clean_only = _magnitude_for(clean_support_units, cg, policy)   # same magnitude rules, clean subset only
    if _MAG_ORDER.index(clean_only) < _MAG_ORDER.index(magnitude):
        ceiling = BeliefMagnitude(policy.qa_failed_dataset_ceiling)
        if _MAG_ORDER.index(magnitude) > _MAG_ORDER.index(ceiling):
            magnitude = ceiling
            qa_dataset_capped = True
            qa_failed_datasets = tuple(sorted({d for u in qa_failed_support for d in u.qa_failed_datasets}))
```

`_magnitude_for(...)` is the existing magnitude computation (n_support / clean_support /
clean_direct_test rules, lines 315–331) refactored into a small helper so it can be evaluated
on the clean-only subset without duplicating logic.

**Semantics:**
- No counted support rests on failed QA → no cap.
- Clean support alone reaches the achieved magnitude ("stands on its own") → no cap; the
  failed-QA units were not load-bearing.
- Otherwise the belief *depends on* failed-QA data → capped to `qa_failed_dataset_ceiling`
  (default `fragile`).

> **⚠ Open decision for spec review — hard ceiling vs. clean-floor.** The rule above is the
> literal reading ("capped to the ceiling unless clean stands on its own"). It has a sharp
> edge: if clean support alone reaches `supported` but failed-QA data pushed the headline to
> `well_supported`, the belief is capped all the way to `fragile` — *below* what clean data
> independently earns. The softer alternative is
> `magnitude = max(ceiling, clean_only)` when capping, so the belief keeps whatever the
> QA-clean subset earns and only loses the failed-QA "lift". **Recommendation: the literal
> hard ceiling** (matches the user's "capped to `qa_failed_dataset_ceiling`" wording and the
> "disciplined, structural failure is serious" intent). Please confirm or pick the clean-floor
> variant before planning.

## BeliefPolicy knob (`graph/belief_policy.py`)

```python
qa_failed_dataset_ceiling: str = "fragile"
```

Frozen/immutable like the rest; built into `DEFAULT_BELIEF_POLICY`. Validated against
`MAGNITUDE_NAMES` (the cycle-free string tuple in `belief_weights.py`) in `__post_init__`,
exactly as `authored_only_ceiling` is validated today.

## Persistence (mirror `authored_capped` — same four sites)

- `graph/belief_snapshot.py`: persist `qa_dataset_capped` on snapshot JSONL rows in **both**
  branches; legacy/pre-slice rows normalize to `False`; **not** part of the dedup `_key`.
- `graph/bundle_belief.py`: OR-rollup `qa_dataset_capped` onto `BundleBeliefResult` + persist.
- `graph/belief.py`: the `BeliefResult` fields above.
- `validate/checks/evidence_lines.py`: the nonreproducible matcher compares
  `qa_dataset_capped` (default `False`) alongside `authored_capped` so a cross-run flip is
  caught, not silently accepted.

No patch RDF surface (authored_capped has none either — keep the blast radius identical).

## Validators (`validate/checks/`)

- **Build-time fail-loud** handles the missing-report case (the materialization `raise`),
  consistent with "fail early / avoid silent fallbacks".
- The existing `check_belief_eligible_empirical_has_dataset_usage` is unchanged.
- Nonreproducible matcher updated as above.

## Non-goals (explicitly deferred)

- Distribution-flag consumption and `.qa_disposition.yaml` disposition state.
- `indirect-bears-on` line→dataset linkage for the ceiling.
- Deep report **freshness** (is the report stale vs. the underlying data/schema?). This slice
  records *which* report verdict was consumed (path + file hash) for audit; it does not
  recompute QA or diff against data content. Freshness ties into the Source Compiler
  snapshot machinery and is a later concern.
- Inline QA execution at build time (the rejected sourcing option).
- Gate or penalty mechanisms (rejected in favor of ceiling).

## Behavior-neutrality

Every new field defaults to the inert value (`qa_report=""`, `qa_failed_datasets=()`,
`qa_dataset_capped=False`). No existing dataset declares `qa_report`, so no line is stamped,
no unit is `qa_failed`, and `aggregate_belief` is bit-for-bit unchanged on the current
corpus. The new `is_qualifying_direct_test` clause is a no-op when `qa_failed_datasets` is
empty. The one intended behavior change appears only once a dataset opts in by referencing a
report whose `package_structural_failed` is true.

## Testing strategy

- **Model:** `DatasetEntity.qa_report` parses; default empty.
- **dataset_qa materialization:** report read → `qaStructuralFailed` stamped; failed
  resources listed; missing/unreadable report raises with a clear message; line stamped with
  `qaFailedDataset` only for failed dependence datasets via direct/virtual paths (not cited,
  not indirect).
- **belief unit tests:** `is_qa_failed`; refutation symmetry (failed-QA strong direct-test
  dispute is **not** decisive); ceiling fires when belief depends on failed QA; **no** cap
  when clean support stands on its own; `qa_dataset_capped` + `qa_failed_datasets` populated;
  policy ceiling validated against `MAGNITUDE_NAMES`.
- **bundle:** `qa_dataset_capped` OR-rollup.
- **snapshot:** both branches persist; legacy→False; not in `_key`.
- **e2e:** a dataset:slug with a failing `qa_report.json`, an empirical line analyzing it,
  proposition belief capped to fragile; flip the report to clean → uncapped.
- **regression:** full belief suite green, byte-identical on the current corpus.
```
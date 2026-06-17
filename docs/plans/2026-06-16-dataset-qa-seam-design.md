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

This field is populated **only for empirical lines** — the empirical restriction is enforced
once, at the materialization stamping step (§Materialization (b)), so the field's meaning is
unambiguous (`qa_failed_datasets` non-empty ⟺ empirical line backed by a failed dependence
dataset) and `is_qa_failed` needs no second type check. This mirrors the user's stated
semantics ("a counted **empirical** support unit backed by a structurally-QA-failed dataset").

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

**(b) Stamp empirical evidence lines.** Reusing the existing usage machinery
(`read_dataset_usage_facts` / `reduce_usage_facts` / `DEPENDENCE_ROLES` from
`dataset_independence.py`), for each evidence line whose **normalized `evidence_type` is
`empirical_data`** find the **dependence-role** datasets it rests on via **direct/virtual**
ancestry (`_ancestor_path` ∈ {"direct","virtual"}), intersect with structurally-failed
datasets, and stamp:
```
line ──SCI_NS.qaFailedDataset──▶ dataset   (one per failed dependence dataset)
```
`_read_unit` reads these into `EvidenceUnit.qa_failed_datasets`.

> **Empirical-only is the single chokepoint.** Non-empirical lines (literature, simulation,
> etc.) that happen to carry dependence-role `dataset_usage` are **not** stamped, so they are
> never `is_qa_failed` and never capped. This is the *only* place the empirical restriction
> lives — `is_qa_failed` and the ceiling below stay type-agnostic, reading the pre-computed
> fact (the same way belief reads the pre-computed `independence_group` from
> `dataset_independence`). The normalized evidence type is read from `SCI_NS.evidenceType` on
> the line (`normalize_evidence_type(...) == EvidenceType.EMPIRICAL_DATA`).

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

### Magnitude as a reusable helper — `_base_magnitude`

The magnitude computation (current `belief.py:315–331`) is refactored into a pure helper so
the "stands on its own" check evaluates the *same rules* on the clean-only subset, and — this
is the fix for the contested-group concern — **recomputes contested groups from its own
inputs** rather than reusing the full-set `cg`:

```python
def _base_magnitude(support: list[EvidenceUnit], dispute: list[EvidenceUnit], *,
                    policy: BeliefPolicy) -> BeliefMagnitude:
    # Contested groups recomputed from THESE support/dispute units only. On the kept lists
    # this reproduces reduce_units.contested_groups exactly (every group with any member has a
    # winner), so the main-path call is behavior-neutral; on the clean-only subset a group
    # contested ONLY because of a now-removed failed-QA support unit correctly drops out.
    sup_groups = {u.independence_group for u in support if u.independence_group}
    dis_groups = {u.independence_group for u in dispute if u.independence_group}
    cg = sup_groups & dis_groups
    n_support = len(support)
    clean_support = [u for u in support if u.independence_group not in cg]
    clean_direct_test = any(is_qualifying_direct_test(u, policy=policy) for u in clean_support)
    if n_support == 0:
        return BeliefMagnitude.SPECULATIVE
    if n_support == 1:
        return BeliefMagnitude.FRAGILE
    if (not policy.well_supported_requires_direct_test or clean_direct_test) and \
            len(clean_support) >= policy.well_supported_min_clean_support:
        return BeliefMagnitude.WELL_SUPPORTED
    return BeliefMagnitude.SUPPORTED
```

The main path becomes `magnitude = _base_magnitude(support, dispute, policy=policy)` (the
inline block is deleted; `contested` still uses `reduced.contested_groups` as today). A
regression test pins byte-identical output on the current corpus.

### The QA ceiling — applied after the refutation cap and after the authored ceiling

```python
qa_dataset_capped = False
qa_failed_datasets: tuple[str, ...] = ()
qa_failed_support = [u for u in support if is_qa_failed(u)]
if qa_failed_support:
    clean_support_units = [u for u in support if not is_qa_failed(u)]
    clean_only = _base_magnitude(clean_support_units, dispute, policy=policy)
    if _MAG_ORDER.index(clean_only) < _MAG_ORDER.index(magnitude):   # belief DEPENDS on failed QA
        ceiling = BeliefMagnitude(policy.qa_failed_dataset_ceiling)
        if _MAG_ORDER.index(magnitude) > _MAG_ORDER.index(ceiling):
            magnitude = ceiling
            qa_dataset_capped = True
            qa_failed_datasets = tuple(sorted({d for u in qa_failed_support for d in u.qa_failed_datasets}))
```

**Semantics (hard ceiling — resolved):**
- No counted support rests on failed QA → no cap.
- Clean support alone reaches the achieved magnitude ("stands on its own") → no cap; the
  failed-QA units were not load-bearing.
- Otherwise the belief *depends on* failed-QA data → **hard-capped to
  `qa_failed_dataset_ceiling`** (default `fragile`), even when the QA-clean subset alone would
  earn something above the ceiling. This is the deliberate, disciplined reading: if a
  conclusion's headline magnitude leans on structurally-broken data at all, it is not trusted
  beyond the ceiling. (The softer `max(ceiling, clean_only)` variant was considered and
  rejected.) The contested-group edge — a group contested only via a removed failed-QA unit —
  is handled by `_base_magnitude` recomputing `cg` on the clean subset, and is covered by a
  dedicated test.

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
- **empirical scope:** a **non-empirical** line (e.g. `simulation`/`literature`) with a
  dependence-role usage of a failed dataset is **not** stamped → not `qa_failed`, not capped.
- **`_base_magnitude`:** reproduces the current magnitude on representative kept lists
  (behavior-neutral); and the contested-group edge — a group contested only via a failed-QA
  support unit — drops out of `cg` on the clean-only subset so clean support can stand on its
  own.
- **belief unit tests:** `is_qa_failed`; refutation symmetry (failed-QA strong direct-test
  dispute is **not** decisive); ceiling fires when belief depends on failed QA; **no** cap
  when clean support stands on its own; hard-ceiling edge (clean alone reaches `supported`,
  failed-QA lifts to `well_supported` → capped to `fragile`); `qa_dataset_capped` +
  `qa_failed_datasets` populated; policy ceiling validated against `MAGNITUDE_NAMES`.
- **bundle:** `qa_dataset_capped` OR-rollup.
- **snapshot:** both branches persist; legacy→False; not in `_key`.
- **e2e:** a dataset:slug with a failing `qa_report.json`, an empirical line analyzing it,
  proposition belief capped to fragile; flip the report to clean → uncapped.
- **regression:** full belief suite green, byte-identical on the current corpus.
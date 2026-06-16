# Dataset-QA Seam Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make schema-driven QA outcomes inform belief — an empirical evidence line resting
on a dataset whose **structural** QA failed cannot push belief above a configured ceiling
unless QA-clean support stands on its own.

**Architecture:** A `DatasetEntity` references its persisted `qa_report.json`. At graph build a
new `graph/dataset_qa.py` layer reads the structural verdict, stamps it on the dataset node,
and stamps `SCI_NS.qaFailedDataset` on each **empirical** line resting on a failed
**dependence-role** dataset (direct/virtual paths). `aggregate_belief` consumes that via a new
`qa_failed_dataset_ceiling` policy knob (ceiling + refutation symmetry), mirroring Slice B's
authored-confidence shape. Design: `docs/plans/2026-06-16-dataset-qa-seam-design.md`.

**Tech Stack:** Python 3.13, pydantic (model), rdflib (graph), pytest. `science_model` owns
the vocabulary; `science_tool` consumes it (never the reverse).

**Conventions for every task:**
- All commands run from the **`science/` member dir** of the worktree
  (`~/d/science/.worktrees/dataset-qa-seam/science`).
- Tests: `PYTHONPATH=src:model/src rtk proxy uv run --frozen pytest <path> -v`
  (the `PYTHONPATH` prefix is REQUIRED — a main-installed `science_model` otherwise shadows
  the worktree's model edits).
- Lint after each implementation: `rtk proxy uv run --frozen ruff check <files>`.
- Git via `rtk git`. Commit messages **must not** contain `Co-Authored-By`.
- Verify the branch is `dataset-qa-seam` before every commit.

---

### Task 1: Model field `DatasetEntity.qa_report`

**Files:**
- Modify: `model/src/science_model/entities.py` (class `DatasetEntity`, ~line 684-692)
- Test: `model/tests/test_dataset_models.py`

- [ ] **Step 1: Write the failing test**

Append to `model/tests/test_dataset_models.py`:

```python
def test_dataset_qa_report_field_defaults_empty_and_parses():
    from science_model.entities import DatasetEntity

    bare = DatasetEntity(id="dataset:ds-noqa", type="dataset", title="No QA",
                         origin="external", access={"level": "public", "verified": False})
    assert bare.qa_report == ""

    withqa = DatasetEntity(id="dataset:ds-qa", type="dataset", title="With QA",
                           origin="external", access={"level": "public", "verified": False},
                           qa_report="knowledge/qa/ds-qa/qa_report.json")
    assert withqa.qa_report == "knowledge/qa/ds-qa/qa_report.json"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src:model/src rtk proxy uv run --frozen pytest model/tests/test_dataset_models.py::test_dataset_qa_report_field_defaults_empty_and_parses -v`
Expected: FAIL — `DatasetEntity` has no `qa_report` (pydantic ignores/errors on the kwarg).

- [ ] **Step 3: Write minimal implementation**

In `entities.py`, add the field alongside `tier`/`update_cadence`:

```python
    tier: str = ""
    update_cadence: str = ""
    qa_report: str = ""   # project-root-relative path to a qa_report.json from `science datasets qa`
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src:model/src rtk proxy uv run --frozen pytest model/tests/test_dataset_models.py -v`
Expected: PASS (new test + existing dataset tests).

- [ ] **Step 5: Commit**

```bash
rtk git add model/src/science_model/entities.py model/tests/test_dataset_models.py
rtk git commit -m "feat(datasets): add DatasetEntity.qa_report (Spec 5 dataset-QA seam)"
```

---

### Task 2: BeliefPolicy knob `qa_failed_dataset_ceiling`

**Files:**
- Modify: `src/science_tool/graph/belief_policy.py`
- Test: `tests/test_belief_policy.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_belief_policy.py`:

```python
def test_default_policy_has_qa_failed_dataset_ceiling():
    from science_tool.graph.belief_policy import DEFAULT_BELIEF_POLICY
    assert DEFAULT_BELIEF_POLICY.qa_failed_dataset_ceiling == "fragile"


def test_policy_rejects_out_of_vocab_qa_ceiling():
    import dataclasses
    import pytest
    from science_tool.graph.belief_policy import DEFAULT_BELIEF_POLICY
    with pytest.raises(ValueError):
        dataclasses.replace(DEFAULT_BELIEF_POLICY, qa_failed_dataset_ceiling="bogus")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src:model/src rtk proxy uv run --frozen pytest tests/test_belief_policy.py -v`
Expected: FAIL — no such field.

- [ ] **Step 3: Write minimal implementation**

In `belief_policy.py`, add the field after `authored_only_ceiling` (line 57):

```python
    authored_only_ceiling: str
    # Dataset-QA seam (Spec 5). When counted empirical support rests on a structurally-QA-failed
    # dataset and QA-clean support cannot reach the achieved magnitude alone, belief is hard-capped
    # to this ceiling. Magnitude STRING (validated against MAGNITUDE_NAMES, no belief.py import).
    qa_failed_dataset_ceiling: str
```

Add validation in `__post_init__` after the `authored_only_ceiling` check (line 77):

```python
        if self.qa_failed_dataset_ceiling not in MAGNITUDE_NAMES:
            raise ValueError(
                f"qa_failed_dataset_ceiling must be one of {MAGNITUDE_NAMES}, "
                f"got {self.qa_failed_dataset_ceiling!r}"
            )
```

Add to `DEFAULT_BELIEF_POLICY` (after `authored_only_ceiling="fragile",`, line 99):

```python
    qa_failed_dataset_ceiling="fragile",
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src:model/src rtk proxy uv run --frozen pytest tests/test_belief_policy.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
rtk git add src/science_tool/graph/belief_policy.py tests/test_belief_policy.py
rtk git commit -m "feat(belief): add qa_failed_dataset_ceiling policy knob"
```

---

### Task 3: `EvidenceUnit.qa_failed_datasets` + `is_qa_failed` + `_read_unit`

**Files:**
- Modify: `src/science_tool/graph/belief.py` (`EvidenceUnit` ~line 44, `_read_unit` ~line 96, new `is_qa_failed`)
- Test: `tests/test_belief_collect.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_belief_collect.py` (reuse the module's existing graph fixtures/helpers
for building an evidence line; if it builds graphs inline, follow that pattern). Minimal
standalone version:

```python
def test_read_unit_reads_qa_failed_datasets_and_predicate():
    from rdflib import Graph, Literal, RDF, URIRef
    from science_tool.graph.belief import (
        EVIDENCE_LINE_CLASS, EvidenceUnit, _read_unit, is_qa_failed,
    )
    from science_tool.graph.io import SCI_NS

    line = URIRef("https://example.org/p/evidence-line/ev1")
    prov = Graph()
    ds_a = URIRef("https://example.org/p/dataset/a")
    ds_b = URIRef("https://example.org/p/dataset/b")
    prov.add((line, SCI_NS.qaFailedDataset, ds_b))
    prov.add((line, SCI_NS.qaFailedDataset, ds_a))

    unit = _read_unit(prov, line, "supports", frozenset(), None)
    assert unit.qa_failed_datasets == (str(ds_a), str(ds_b))   # sorted
    assert is_qa_failed(unit) is True
    assert is_qa_failed(EvidenceUnit(line_uri="x", stance="supports", strength=None,
        independence=None, independence_group=None, evidence_role=None, evidence_type=None,
        dispute_scope=None, proxy_directness=None, has_measurement_model=False, source=None,
        observability_keys=())) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src:model/src rtk proxy uv run --frozen pytest tests/test_belief_collect.py::test_read_unit_reads_qa_failed_datasets_and_predicate -v`
Expected: FAIL — no `qa_failed_datasets` field / no `is_qa_failed`.

- [ ] **Step 3: Write minimal implementation**

In `belief.py`, add the field as the **last** `EvidenceUnit` field (after `confidence`, line 44):

```python
    confidence: float | None = None
    # Dataset-QA seam (Spec 5). Dependence-role datasets this EMPIRICAL line rests on whose
    # structural QA failed (populated only for empirical lines at materialization). LAST field
    # for positional stability of the many EvidenceUnit(...) test constructors.
    qa_failed_datasets: tuple[str, ...] = ()
```

In `_read_unit`, add to the returned `EvidenceUnit(...)` (after `confidence=...`, line 96):

```python
        confidence=_float_lit(provenance, line, SCI_NS.confidence),
        qa_failed_datasets=tuple(
            sorted(str(o) for o in provenance.objects(line, SCI_NS.qaFailedDataset))
        ),
```

Add the predicate near `is_authored_assertion` (after line 218):

```python
def is_qa_failed(u: EvidenceUnit) -> bool:
    """Pre-computed fact (set at materialization, empirical-only): the unit rests on >=1
    structurally-QA-failed dependence dataset. Belief reads it; it does not recompute QA."""
    return bool(u.qa_failed_datasets)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src:model/src rtk proxy uv run --frozen pytest tests/test_belief_collect.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
rtk git add src/science_tool/graph/belief.py tests/test_belief_collect.py
rtk git commit -m "feat(belief): EvidenceUnit.qa_failed_datasets + is_qa_failed + read predicate"
```

---

### Task 4: Refutation symmetry + `_base_magnitude` refactor (behavior-neutral)

**Files:**
- Modify: `src/science_tool/graph/belief.py` (`is_qualifying_direct_test` ~line 234; magnitude block ~line 315-331; new `_base_magnitude`, `_contested_groups_for`)
- Test: `tests/test_belief_reduce.py` (or `tests/test_belief_aggregate.py`)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_belief_aggregate.py` (use the module's existing `EvidenceUnit` builder
helper if present; else construct directly):

```python
def test_base_magnitude_matches_inline_and_qa_failed_not_qualifying():
    from science_tool.graph.belief import (
        BeliefMagnitude, _base_magnitude, is_qualifying_direct_test,
    )
    from science_tool.graph.belief_policy import DEFAULT_BELIEF_POLICY as P

    def unit(group=None, role="direct_test", strength="strong", qa=()):
        from science_tool.graph.belief import EvidenceUnit
        return EvidenceUnit(line_uri=f"u{id(group)}{role}{strength}{qa}", stance="supports",
            strength=strength, independence="independent", independence_group=group,
            evidence_role=role, evidence_type="empirical_data", dispute_scope=None,
            proxy_directness=None, has_measurement_model=False, source=None,
            observability_keys=(), qa_failed_datasets=qa)

    two_clean = [unit(role="direct_test"), unit(role="proxy_support")]
    assert _base_magnitude(two_clean, set(), policy=P) == BeliefMagnitude.WELL_SUPPORTED

    # A QA-failed direct test is NOT a qualifying direct test.
    assert is_qualifying_direct_test(unit(qa=("dataset:bad",)), policy=P) is False
    assert is_qualifying_direct_test(unit(), policy=P) is True


def test_contested_groups_for_intersects_support_and_dispute_groups():
    from science_tool.graph.belief import EvidenceUnit, _contested_groups_for

    def u(stance, group):
        return EvidenceUnit(line_uri=f"{stance}-{group}", stance=stance, strength="strong",
            independence="independent", independence_group=group, evidence_role="direct_test",
            evidence_type="empirical_data", dispute_scope=None, proxy_directness=None,
            has_measurement_model=False, source=None, observability_keys=())

    support = [u("supports", "g1"), u("supports", "g2"), u("supports", None)]
    dispute = [u("disputes", "g1"), u("disputes", "g3")]
    assert _contested_groups_for(support, dispute) == {"g1"}   # only the shared group; None ignored
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src:model/src rtk proxy uv run --frozen pytest tests/test_belief_aggregate.py::test_base_magnitude_matches_inline_and_qa_failed_not_qualifying tests/test_belief_aggregate.py::test_contested_groups_for_intersects_support_and_dispute_groups -v`
Expected: FAIL — `_base_magnitude`/`_contested_groups_for` undefined; `is_qualifying_direct_test` lacks the QA clause.

- [ ] **Step 3: Write minimal implementation**

In `belief.py` add the QA clause to `is_qualifying_direct_test` (line 237-241):

```python
    return (
        u.evidence_role == policy.direct_test_role
        and not is_proxy_gated(u, policy=policy)
        and not is_authored_assertion(u, policy=policy)
        and not is_qa_failed(u)
    )
```

Add the two helpers (place them just before `class BeliefMagnitude` or just after `_MAG_ORDER`):

```python
def _contested_groups_for(support: list[EvidenceUnit], dispute: list[EvidenceUnit]) -> set[str]:
    sup_groups = {u.independence_group for u in support if u.independence_group}
    dis_groups = {u.independence_group for u in dispute if u.independence_group}
    return sup_groups & dis_groups


def _base_magnitude(
    support: list[EvidenceUnit], contested_groups: set[str], *, policy: BeliefPolicy
) -> BeliefMagnitude:
    n_support = len(support)
    clean_support = [u for u in support if u.independence_group not in contested_groups]
    clean_direct_test = any(is_qualifying_direct_test(u, policy=policy) for u in clean_support)
    if n_support == 0:
        return BeliefMagnitude.SPECULATIVE
    if n_support == 1:
        return BeliefMagnitude.FRAGILE
    if (not policy.well_supported_requires_direct_test or clean_direct_test) and len(
        clean_support
    ) >= policy.well_supported_min_clean_support:
        return BeliefMagnitude.WELL_SUPPORTED
    return BeliefMagnitude.SUPPORTED
```

Replace the inline magnitude block in `aggregate_belief` (current lines 315-331) with:

```python
    decisive = any(is_decisive_refutation(u, policy=policy) for u in dispute)
    magnitude = _base_magnitude(support, cg, policy=policy)
```

(Delete the now-unused `n_support`, `clean_support`, and `clean_direct_test` locals — they were
inputs to the inline block, now encapsulated in `_base_magnitude`. `decisive` stays; it feeds
the refutation cap below. `cg` is `reduced.contested_groups`, already bound at line 309.)

- [ ] **Step 4: Run test to verify it passes + full regression neutrality**

Run: `PYTHONPATH=src:model/src rtk proxy uv run --frozen pytest tests/test_belief_aggregate.py tests/test_belief_reduce.py tests/test_belief_classify.py tests/test_belief_policy_aggregate.py -v`
Expected: PASS — the refactor is behavior-neutral (main path passes `reduced.contested_groups`,
identical to before).

- [ ] **Step 5: Commit**

```bash
rtk git add src/science_tool/graph/belief.py tests/test_belief_aggregate.py
rtk git commit -m "refactor(belief): extract _base_magnitude; QA-failed never a qualifying direct test"
```

---

### Task 5: The QA ceiling in `aggregate_belief` + `BeliefResult` fields

**Files:**
- Modify: `src/science_tool/graph/belief.py` (`BeliefResult` ~line 289-290; `aggregate_belief` after the authored-ceiling block ~line 347)
- Test: `tests/test_belief_aggregate.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_belief_aggregate.py` (reuse the `unit` builder from Task 4's test or the
module helper):

```python
def test_qa_ceiling_caps_when_belief_depends_on_failed_qa():
    from science_tool.graph.belief import BeliefMagnitude, EvidenceUnit, aggregate_belief
    from science_tool.graph.belief_policy import DEFAULT_BELIEF_POLICY as P

    def sup(uri, role="direct_test", qa=()):
        return EvidenceUnit(line_uri=uri, stance="supports", strength="strong",
            independence="independent", independence_group=None, evidence_role=role,
            evidence_type="empirical_data", dispute_scope=None, proxy_directness=None,
            has_measurement_model=False, source=None, observability_keys=(),
            qa_failed_datasets=qa)

    # Two units, both reach WELL_SUPPORTED; one rests on failed QA and the clean remainder
    # (1 unit) cannot stand on its own -> hard-capped to fragile.
    res = aggregate_belief([sup("a", "direct_test", qa=("dataset:bad",)), sup("b", "proxy_support")], policy=P)
    assert res.magnitude == BeliefMagnitude.FRAGILE
    assert res.qa_dataset_capped is True
    assert res.qa_failed_datasets == ("dataset:bad",)


def test_qa_ceiling_no_cap_when_clean_support_stands_on_its_own():
    from science_tool.graph.belief import BeliefMagnitude, EvidenceUnit, aggregate_belief
    from science_tool.graph.belief_policy import DEFAULT_BELIEF_POLICY as P

    def sup(uri, role, qa=()):
        return EvidenceUnit(line_uri=uri, stance="supports", strength="strong",
            independence="independent", independence_group=None, evidence_role=role,
            evidence_type="empirical_data", dispute_scope=None, proxy_directness=None,
            has_measurement_model=False, source=None, observability_keys=(),
            qa_failed_datasets=qa)

    # Two clean units already reach WELL_SUPPORTED; a third failed-QA unit is not load-bearing.
    res = aggregate_belief(
        [sup("a", "direct_test"), sup("b", "proxy_support"), sup("c", "proxy_support", qa=("dataset:bad",))],
        policy=P)
    assert res.magnitude == BeliefMagnitude.WELL_SUPPORTED
    assert res.qa_dataset_capped is False
    assert res.qa_failed_datasets == ()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src:model/src rtk proxy uv run --frozen pytest tests/test_belief_aggregate.py::test_qa_ceiling_caps_when_belief_depends_on_failed_qa -v`
Expected: FAIL — no `qa_dataset_capped` field / no ceiling.

- [ ] **Step 3: Write minimal implementation**

Add `BeliefResult` fields (after `excluded_authored_confidence`, line 290):

```python
    excluded_authored_confidence: list[EvidenceUnit] = field(default_factory=list)
    qa_dataset_capped: bool = False
    qa_failed_datasets: tuple[str, ...] = ()
```

In `aggregate_belief`, after the authored-ceiling block (after line 346) and before
`contested = ...`:

```python
    # Dataset-QA ceiling (design §The QA ceiling). When counted empirical support rests on a
    # structurally-QA-failed dataset and the QA-clean support cannot reach the achieved
    # magnitude alone, hard-cap to qa_failed_dataset_ceiling. Applied after the refutation and
    # authored caps.
    qa_dataset_capped = False
    qa_failed_datasets: tuple[str, ...] = ()
    qa_failed_support = [u for u in support if is_qa_failed(u)]
    if qa_failed_support:
        clean_support_units = [u for u in support if not is_qa_failed(u)]
        clean_cg = _contested_groups_for(clean_support_units, dispute)
        clean_only = _base_magnitude(clean_support_units, clean_cg, policy=policy)
        if _MAG_ORDER.index(clean_only) < _MAG_ORDER.index(magnitude):
            ceiling = BeliefMagnitude(policy.qa_failed_dataset_ceiling)
            if _MAG_ORDER.index(magnitude) > _MAG_ORDER.index(ceiling):
                magnitude = ceiling
                qa_dataset_capped = True
                qa_failed_datasets = tuple(
                    sorted({d for u in qa_failed_support for d in u.qa_failed_datasets})
                )
```

Add both to the returned `BeliefResult(...)` (after `excluded_authored_confidence=...`):

```python
        excluded_authored_confidence=excluded_authored_confidence,
        qa_dataset_capped=qa_dataset_capped,
        qa_failed_datasets=qa_failed_datasets,
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src:model/src rtk proxy uv run --frozen pytest tests/test_belief_aggregate.py -v`
Expected: PASS (both new tests + existing).

- [ ] **Step 5: Add the hard-ceiling-edge + contested-group-edge tests**

Append two more tests, then re-run:

```python
def test_qa_hard_ceiling_edge_clean_supported_failed_lifts_to_well_supported():
    # Clean alone -> SUPPORTED (2 proxy_support, no direct test); failed-QA direct test lifts
    # the headline to WELL_SUPPORTED -> hard-capped all the way to fragile.
    from science_tool.graph.belief import BeliefMagnitude, EvidenceUnit, aggregate_belief
    from science_tool.graph.belief_policy import DEFAULT_BELIEF_POLICY as P
    def sup(uri, role, qa=()):
        return EvidenceUnit(line_uri=uri, stance="supports", strength="strong",
            independence="independent", independence_group=None, evidence_role=role,
            evidence_type="empirical_data", dispute_scope=None, proxy_directness=None,
            has_measurement_model=False, source=None, observability_keys=(), qa_failed_datasets=qa)
    res = aggregate_belief(
        [sup("a", "proxy_support"), sup("b", "proxy_support"), sup("c", "direct_test", qa=("dataset:bad",))],
        policy=P)
    # clean-only = SUPPORTED (>= ceiling), achieved with failed = WELL_SUPPORTED, depends-on -> fragile.
    assert res.magnitude == BeliefMagnitude.FRAGILE
    assert res.qa_dataset_capped is True
```

Then append the **required** contested-group clean-only test (locks the `_contested_groups_for`
recomputation in the stands-on-its-own branch — a contested group is present, and the QA-clean
support must still stand on its own):

```python
def test_qa_no_cap_with_contested_group_present_clean_stands_on_its_own():
    from science_tool.graph.belief import BeliefMagnitude, EvidenceUnit, aggregate_belief
    from science_tool.graph.belief_policy import DEFAULT_BELIEF_POLICY as P

    def u(uri, stance, role, group=None, qa=()):
        return EvidenceUnit(line_uri=uri, stance=stance, strength="strong",
            independence="independent", independence_group=group, evidence_role=role,
            evidence_type="empirical_data", dispute_scope=None, proxy_directness=None,
            has_measurement_model=False, source=None, observability_keys=(), qa_failed_datasets=qa)

    units = [
        u("s1", "supports", "direct_test"),                 # ungrouped clean direct test
        u("s2", "supports", "proxy_support"),               # ungrouped clean -> clean pair reaches WELL_SUPPORTED
        u("s3", "supports", "proxy_support", qa=("dataset:bad",)),  # failed-QA, not load-bearing
        u("s4", "supports", "direct_test", group="g1"),     # support winner of contested g1
        u("d1", "disputes", "proxy_support", group="g1"),   # dispute winner of g1 -> g1 contested
    ]
    res = aggregate_belief(units, policy=P)
    # clean-only support (s1,s2,s4) recomputes g1 as still contested, excludes s4, leaving
    # s1+s2 which reach WELL_SUPPORTED on their own -> no cap.
    assert res.magnitude == BeliefMagnitude.WELL_SUPPORTED
    assert res.qa_dataset_capped is False
```

Run: `PYTHONPATH=src:model/src rtk proxy uv run --frozen pytest tests/test_belief_aggregate.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
rtk git add src/science_tool/graph/belief.py tests/test_belief_aggregate.py
rtk git commit -m "feat(belief): dataset-QA ceiling on belief that depends on failed-QA data"
```

---

### Task 6: `dependence_datasets_by_line` helper

**Files:**
- Modify: `src/science_tool/graph/dataset_independence.py` (new public function)
- Test: `tests/test_dataset_independence.py` (create if absent)

- [ ] **Step 1: Write the failing test**

Add to `tests/test_dataset_independence.py`:

```python
def test_dependence_datasets_by_line_direct_dependence_only():
    from rdflib import Graph, Literal, RDF, URIRef
    from science_tool.graph.dataset_independence import dependence_datasets_by_line
    from science_tool.graph.io import CITO_NS, SCI_NS

    k, p = Graph(), Graph()
    line = URIRef("https://example.org/p/evidence-line/ev1")
    target = URIRef("https://example.org/p/proposition/c1")
    ds = URIRef("https://example.org/p/dataset/good")
    k.add((line, RDF.type, SCI_NS.EvidenceLine))
    k.add((line, CITO_NS.supports, target))

    usage = URIRef("https://example.org/p/usage/1")
    p.add((line, SCI_NS.hasDatasetUsage, usage))
    p.add((usage, RDF.type, SCI_NS.DatasetUsage))
    p.add((usage, SCI_NS.dataset, ds))
    p.add((usage, SCI_NS.usageRole, Literal("analyzed")))   # a DEPENDENCE role
    p.add((usage, SCI_NS.usageOverlap, Literal("full")))

    out = dependence_datasets_by_line(k, p)
    assert out[line] == {ds}


def test_dependence_datasets_by_line_excludes_cited_role():
    from rdflib import Graph, Literal, RDF, URIRef
    from science_tool.graph.dataset_independence import dependence_datasets_by_line
    from science_tool.graph.io import CITO_NS, SCI_NS

    k, p = Graph(), Graph()
    line = URIRef("https://example.org/p/evidence-line/ev2")
    target = URIRef("https://example.org/p/proposition/c2")
    ds = URIRef("https://example.org/p/dataset/cited")
    k.add((line, RDF.type, SCI_NS.EvidenceLine))
    k.add((line, CITO_NS.supports, target))
    usage = URIRef("https://example.org/p/usage/2")
    p.add((line, SCI_NS.hasDatasetUsage, usage))
    p.add((usage, RDF.type, SCI_NS.DatasetUsage))
    p.add((usage, SCI_NS.dataset, ds))
    p.add((usage, SCI_NS.usageRole, Literal("cited")))      # NOT a dependence role
    p.add((usage, SCI_NS.usageOverlap, Literal("unknown")))

    assert dependence_datasets_by_line(k, p).get(line, set()) == set()


def test_dependence_datasets_by_line_includes_virtual_member():
    from rdflib import Graph, Literal, RDF, URIRef
    from rdflib.namespace import PROV
    from science_tool.graph.dataset_independence import dependence_datasets_by_line
    from science_tool.graph.io import CITO_NS, SCI_NS

    k, p = Graph(), Graph()
    line = URIRef("https://example.org/p/evidence-line/ev-v")
    target = URIRef("https://example.org/p/proposition/cv")
    consumer = URIRef("https://example.org/p/virtual/geneset-member/m1")   # virtual member URI
    ds = URIRef("https://example.org/p/dataset/vds")
    k.add((line, RDF.type, SCI_NS.EvidenceLine))
    k.add((line, CITO_NS.supports, target))
    p.add((line, PROV.wasDerivedFrom, consumer))                          # line derives from it
    usage = URIRef("https://example.org/p/usage/v")
    p.add((consumer, SCI_NS.hasDatasetUsage, usage))
    p.add((usage, RDF.type, SCI_NS.DatasetUsage))
    p.add((usage, SCI_NS.dataset, ds))
    p.add((usage, SCI_NS.usageRole, Literal("analyzed")))
    p.add((usage, SCI_NS.usageOverlap, Literal("full")))

    assert dependence_datasets_by_line(k, p).get(line, set()) == {ds}     # virtual path INCLUDED


def test_dependence_datasets_by_line_excludes_indirect_bears_on():
    from rdflib import Graph, Literal, RDF, URIRef
    from science_tool.graph.dataset_independence import dependence_datasets_by_line
    from science_tool.graph.io import CITO_NS, SCI_NS

    k, p = Graph(), Graph()
    line = URIRef("https://example.org/p/evidence-line/ev-i")
    target = URIRef("https://example.org/p/proposition/ci")
    consumer = URIRef("https://example.org/p/entity/other")               # reaches target only via bears_on
    ds = URIRef("https://example.org/p/dataset/ids")
    k.add((line, RDF.type, SCI_NS.EvidenceLine))
    k.add((line, CITO_NS.supports, target))
    k.add((consumer, SCI_NS.bearsOn, target))                            # indirect-bears-on path
    usage = URIRef("https://example.org/p/usage/i")
    p.add((consumer, SCI_NS.hasDatasetUsage, usage))
    p.add((usage, RDF.type, SCI_NS.DatasetUsage))
    p.add((usage, SCI_NS.dataset, ds))
    p.add((usage, SCI_NS.usageRole, Literal("analyzed")))
    p.add((usage, SCI_NS.usageOverlap, Literal("full")))

    assert dependence_datasets_by_line(k, p).get(line, set()) == set()   # indirect EXCLUDED
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src:model/src rtk proxy uv run --frozen pytest tests/test_dataset_independence.py -v`
Expected: FAIL — function does not exist.

- [ ] **Step 3: Write minimal implementation**

In `dataset_independence.py`, add (reuses existing `read_dataset_usage_facts`,
`reduce_usage_facts`, `_evidence_line_targets`, `_line_ancestors`; `defaultdict` already
imported):

```python
def dependence_datasets_by_line(knowledge: Graph, provenance: Graph) -> dict[URIRef, set[URIRef]]:
    """Per evidence line, the datasets it rests on via a direct/virtual DEPENDENCE-role usage.

    Reuses the line-ancestor resolution that drives B2 independence; `indirect-bears-on`
    linkage is deliberately excluded (too tenuous for the QA quality ceiling)."""
    reduced = reduce_usage_facts(read_dataset_usage_facts(provenance))
    line_targets = _evidence_line_targets(knowledge)
    out: dict[URIRef, set[URIRef]] = defaultdict(set)
    for ancestor in _line_ancestors(knowledge, provenance, reduced, line_targets):
        if ancestor.path in ("direct", "virtual") and ancestor.usage.interpretation == "dependence":
            out[ancestor.line].add(ancestor.dataset)
    return dict(out)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src:model/src rtk proxy uv run --frozen pytest tests/test_dataset_independence.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
rtk git add src/science_tool/graph/dataset_independence.py tests/test_dataset_independence.py
rtk git commit -m "feat(graph): dependence_datasets_by_line helper (direct/virtual dependence join)"
```

---

### Task 7: `graph/dataset_qa.py` materialization layer

**Files:**
- Create: `src/science_tool/graph/dataset_qa.py`
- Test: `tests/test_dataset_qa.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_dataset_qa.py`:

```python
import json
from pathlib import Path

import pytest
from rdflib import Graph, Literal, RDF, URIRef

from science_tool.graph.dataset_qa import DatasetQaReportError, emit_dataset_qa_layer
from science_tool.graph.dataset_usage import project_entity_uri
from science_tool.graph.io import CITO_NS, SCI_NS


class _Ent:
    def __init__(self, canonical_id, kind="dataset", qa_report=""):
        self.canonical_id = canonical_id
        self.kind = kind
        self.qa_report = qa_report


class _Sources:
    def __init__(self, project_root, entities):
        self.project_root = str(project_root)
        self.entities = entities


def _write_report(path: Path, *, failed: bool, fail_resources=()):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "package": "p", "package_structural_failed": failed,
        "resources": [{"resource": r, "status": "fail"} for r in fail_resources],
    }))


def _empirical_line(k, p, line, target, dataset, role="analyzed", etype="empirical_data_evidence"):
    k.add((line, RDF.type, SCI_NS.EvidenceLine))
    k.add((line, CITO_NS.supports, target))
    p.add((line, SCI_NS.evidenceType, Literal(etype)))
    usage = URIRef(str(line) + "/usage")
    p.add((line, SCI_NS.hasDatasetUsage, usage))
    p.add((usage, RDF.type, SCI_NS.DatasetUsage))
    p.add((usage, SCI_NS.dataset, dataset))
    p.add((usage, SCI_NS.usageRole, Literal(role)))
    p.add((usage, SCI_NS.usageOverlap, Literal("full")))


def test_failed_report_stamps_dataset_and_empirical_line(tmp_path):
    _write_report(tmp_path / "qa" / "bad" / "qa_report.json", failed=True, fail_resources=["t1"])
    ds_uri = project_entity_uri("dataset:bad")
    k, p = Graph(), Graph()
    line = URIRef("https://example.org/p/evidence-line/ev1")
    target = URIRef("https://example.org/p/proposition/c1")
    _empirical_line(k, p, line, target, ds_uri)   # dataset URI must match project_entity_uri
    sources = _Sources(tmp_path, [_Ent("dataset:bad", qa_report="qa/bad/qa_report.json")])

    emit_dataset_qa_layer(k, p, sources)

    assert (ds_uri, SCI_NS.qaStructuralFailed, Literal(True)) in p
    assert (ds_uri, SCI_NS.qaFailedResource, Literal("t1")) in p
    assert (line, SCI_NS.qaFailedDataset, ds_uri) in p


def test_clean_report_stamps_verdict_but_no_line_flag(tmp_path):
    _write_report(tmp_path / "qa" / "ok" / "qa_report.json", failed=False)
    ds_uri = project_entity_uri("dataset:ok")
    k, p = Graph(), Graph()
    line = URIRef("https://example.org/p/evidence-line/ev2")
    _empirical_line(k, p, line, URIRef("https://example.org/p/proposition/c2"), ds_uri)
    sources = _Sources(tmp_path, [_Ent("dataset:ok", qa_report="qa/ok/qa_report.json")])

    emit_dataset_qa_layer(k, p, sources)
    assert (ds_uri, SCI_NS.qaStructuralFailed, Literal(False)) in p
    assert len(list(p.triples((line, SCI_NS.qaFailedDataset, None)))) == 0


def test_non_empirical_line_not_stamped(tmp_path):
    _write_report(tmp_path / "qa" / "bad" / "qa_report.json", failed=True)
    ds_uri = project_entity_uri("dataset:bad")
    k, p = Graph(), Graph()
    line = URIRef("https://example.org/p/evidence-line/ev3")
    _empirical_line(k, p, line, URIRef("https://example.org/p/proposition/c3"), ds_uri,
                    etype="simulation_evidence")
    sources = _Sources(tmp_path, [_Ent("dataset:bad", qa_report="qa/bad/qa_report.json")])
    emit_dataset_qa_layer(k, p, sources)
    assert len(list(p.triples((line, SCI_NS.qaFailedDataset, None)))) == 0


def test_missing_report_raises(tmp_path):
    sources = _Sources(tmp_path, [_Ent("dataset:gone", qa_report="qa/gone/qa_report.json")])
    with pytest.raises(DatasetQaReportError):
        emit_dataset_qa_layer(Graph(), Graph(), sources)


def test_non_boolean_verdict_raises_not_coerced(tmp_path):
    # bool("false") is True — must fail loud, not silently invert the verdict.
    path = tmp_path / "qa" / "weird" / "qa_report.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"package": "p", "package_structural_failed": "false", "resources": []}))
    sources = _Sources(tmp_path, [_Ent("dataset:weird", qa_report="qa/weird/qa_report.json")])
    with pytest.raises(DatasetQaReportError):
        emit_dataset_qa_layer(Graph(), Graph(), sources)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src:model/src rtk proxy uv run --frozen pytest tests/test_dataset_qa.py -v`
Expected: FAIL — module does not exist.

- [ ] **Step 3: Write minimal implementation**

Create `src/science_tool/graph/dataset_qa.py`:

```python
"""Dataset-QA seam: consume schema-driven QA verdicts into the graph (Spec 5).

Reads each opted-in dataset's persisted `qa_report.json` (the artifact `science datasets qa
--report-dir` writes), stamps the structural verdict on the dataset node, and stamps
SCI_NS.qaFailedDataset on each EMPIRICAL evidence line resting on a structurally-failed
dependence dataset. Belief consumes those triples; QA itself is never recomputed here.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from rdflib import Graph, Literal as RDFLiteral, URIRef

from science_model.reasoning import EvidenceType

from .belief_weights import normalize_evidence_type
from .dataset_independence import dependence_datasets_by_line
from .dataset_usage import project_entity_uri
from .io import SCI_NS


class DatasetQaReportError(ValueError):
    """A dataset declares a qa_report that is missing, unreadable, or malformed (fail early)."""


def _read_structural_verdict(report_path: Path, dataset_id: str) -> tuple[bool, list[str], str]:
    try:
        raw = report_path.read_text(encoding="utf-8")
        report = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        raise DatasetQaReportError(
            f"{dataset_id}: qa_report {report_path} is missing or unreadable: {exc}"
        ) from exc
    if not isinstance(report, dict) or "package_structural_failed" not in report:
        raise DatasetQaReportError(
            f"{dataset_id}: qa_report {report_path} has no 'package_structural_failed' field"
        )
    failed = report["package_structural_failed"]
    if not isinstance(failed, bool):
        # Fail loud: do NOT coerce. bool("false") is True, which would silently invert intent.
        raise DatasetQaReportError(
            f"{dataset_id}: qa_report {report_path} 'package_structural_failed' must be a JSON "
            f"boolean, got {failed!r}"
        )
    failed_resources = sorted(
        str(r.get("resource", ""))
        for r in report.get("resources", [])
        if isinstance(r, dict) and r.get("status") == "fail"
    )
    report_hash = "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return failed, failed_resources, report_hash


def emit_dataset_qa_layer(knowledge: Graph, provenance: Graph, sources) -> None:
    project_root = Path(sources.project_root)
    failed_datasets: set[URIRef] = set()
    for entity in sources.entities:
        if entity.kind != "dataset":
            continue
        qa_report = getattr(entity, "qa_report", "") or ""
        if not qa_report:
            continue
        dataset_uri = project_entity_uri(entity.canonical_id)
        failed, failed_resources, report_hash = _read_structural_verdict(
            project_root / qa_report, entity.canonical_id
        )
        provenance.add((dataset_uri, SCI_NS.qaStructuralFailed, RDFLiteral(failed)))
        provenance.add((dataset_uri, SCI_NS.qaReport, RDFLiteral(qa_report)))
        provenance.add((dataset_uri, SCI_NS.qaReportHash, RDFLiteral(report_hash)))
        for resource in failed_resources:
            provenance.add((dataset_uri, SCI_NS.qaFailedResource, RDFLiteral(resource)))
        if failed:
            failed_datasets.add(dataset_uri)

    if not failed_datasets:
        return
    for line, datasets in dependence_datasets_by_line(knowledge, provenance).items():
        evidence_type = next(provenance.objects(line, SCI_NS.evidenceType), None)
        token = normalize_evidence_type(str(evidence_type) if evidence_type is not None else None)
        if token != EvidenceType.EMPIRICAL_DATA:
            continue
        for dataset in sorted(datasets & failed_datasets, key=str):
            provenance.add((line, SCI_NS.qaFailedDataset, dataset))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src:model/src rtk proxy uv run --frozen pytest tests/test_dataset_qa.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
rtk git add src/science_tool/graph/dataset_qa.py tests/test_dataset_qa.py
rtk git commit -m "feat(graph): dataset_qa layer — stamp structural verdict + empirical line flags"
```

---

### Task 8: Wire `emit_dataset_qa_layer` into materialize + e2e

**Files:**
- Modify: `src/science_tool/graph/materialize.py` (import ~line 41-42; call after `emit_dataset_independence_records` ~line 294)
- Test: `tests/test_belief_e2e.py` (or `tests/test_dataset_evidence_flow_e2e.py`)

- [ ] **Step 1: Write the failing test**

Add an e2e to `tests/test_belief_e2e.py` modeled on the existing fixtures there (a project dir
with `entities/`, then materialize → load graph → belief). It must: author a `dataset:` entity
with `qa_report` pointing at a failing `qa_report.json`, an empirical evidence-line analyzing
it that supports a proposition with a second clean support line, build the graph via the
project's materialize entrypoint, and assert the proposition's belief is `fragile` with
`qa_dataset_capped`. Then rewrite the report to `package_structural_failed: false`, rebuild,
and assert the belief rises (uncapped). Follow the exact harness already used by the other
tests in that file (fixture builder, `materialize_graph`, belief query helper). Keep the two
support lines and dataset usage minimal.

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src:model/src rtk proxy uv run --frozen pytest tests/test_belief_e2e.py -k qa -v`
Expected: FAIL — the QA layer is not yet wired, so no line is stamped and belief is not capped.

- [ ] **Step 3: Write minimal implementation**

In `materialize.py` imports (with the other graph-layer imports, ~line 41-42):

```python
from .dataset_qa import emit_dataset_qa_layer
```

In `_derive_phase`, immediately after the `emit_dataset_independence_records(...)` call
(after line 294):

```python
    emit_dataset_independence_records(
        provenance,
        derive_dataset_independence_records(knowledge, provenance),
    )
    emit_dataset_qa_layer(knowledge, provenance, sources)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src:model/src rtk proxy uv run --frozen pytest tests/test_belief_e2e.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
rtk git add src/science_tool/graph/materialize.py tests/test_belief_e2e.py
rtk git commit -m "feat(graph): wire dataset_qa layer into materialize _derive_phase + e2e"
```

---

### Task 9: `BundleBeliefResult.qa_dataset_capped` OR-rollup

**Files:**
- Modify: `src/science_tool/graph/bundle_belief.py` (field ~line 91; rollup ~line 135)
- Test: `tests/test_belief_policy_bundle.py` (or `tests/test_bundle_belief.py` if present)

- [ ] **Step 1: Write the failing test**

Add a test that builds a bundle from two member `BeliefResult`s where one has
`qa_dataset_capped=True`, and asserts `roll_up_weakest_link(...).qa_dataset_capped is True`;
and `False` when neither member is capped. Mirror the existing `authored_capped` bundle test
in that file (copy its construction, flip the field).

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src:model/src rtk proxy uv run --frozen pytest tests/test_belief_policy_bundle.py -v`
Expected: FAIL — no `qa_dataset_capped` on `BundleBeliefResult`.

- [ ] **Step 3: Write minimal implementation**

In `bundle_belief.py`, add the field after `authored_capped: bool` (line 91):

```python
    authored_capped: bool
    qa_dataset_capped: bool
```

Add to the `BundleBeliefResult(...)` constructed in `roll_up_weakest_link` after
`authored_capped=...` (line 135):

```python
        authored_capped=any(m.belief.authored_capped for m in ordered),
        qa_dataset_capped=any(m.belief.qa_dataset_capped for m in ordered),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src:model/src rtk proxy uv run --frozen pytest tests/test_belief_policy_bundle.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
rtk git add src/science_tool/graph/bundle_belief.py tests/test_belief_policy_bundle.py
rtk git commit -m "feat(belief): BundleBeliefResult.qa_dataset_capped OR-rollup"
```

---

### Task 10: Snapshot persistence

**Files:**
- Modify: `src/science_tool/graph/belief_snapshot.py` (both row dicts ~line 61/90; `_with_policy_defaults` ~line 132)
- Test: `tests/test_belief_policy_persistence.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_belief_policy_persistence.py`:

```python
def test_snapshot_persists_qa_dataset_capped_and_legacy_normalizes(tmp_path):
    from science_tool.graph.belief_snapshot import _with_policy_defaults, _key

    # Legacy row (pre-slice) normalizes to False, and qa_dataset_capped is NOT part of _key.
    legacy = _with_policy_defaults({"as_of": "x", "claim": "c", "input_hashes": [],
        "config_version": "v", "scalar_enabled": False, "policy_id": "core-default",
        "policy_version": "1"})
    assert legacy["qa_dataset_capped"] is False
    with_flag = dict(legacy); with_flag["qa_dataset_capped"] = True
    assert _key(legacy) == _key(with_flag)   # derived flag, not identity
```

(If the file has a fuller round-trip snapshot harness, add an assertion there that a real
capped `BeliefResult` writes `"qa_dataset_capped": true`.)

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src:model/src rtk proxy uv run --frozen pytest tests/test_belief_policy_persistence.py -v`
Expected: FAIL — `_with_policy_defaults` does not add `qa_dataset_capped`.

- [ ] **Step 3: Write minimal implementation**

In `belief_snapshot.py`, add to **both** row dicts (after `"authored_capped": result.authored_capped,`
at lines 61 and 90):

```python
                "authored_capped": result.authored_capped,
                "qa_dataset_capped": result.qa_dataset_capped,
```

(bundle branch — line 61, indent matches; plain branch — line 90.)

In `_with_policy_defaults`, after the `authored_capped` normalization (line 133):

```python
    if "authored_capped" not in row:
        row["authored_capped"] = False
    if "qa_dataset_capped" not in row:
        row["qa_dataset_capped"] = False
    return row
```

Leave `_key` unchanged (the flag is derived, not identity).

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src:model/src rtk proxy uv run --frozen pytest tests/test_belief_policy_persistence.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
rtk git add src/science_tool/graph/belief_snapshot.py tests/test_belief_policy_persistence.py
rtk git commit -m "feat(belief): persist qa_dataset_capped on snapshot rows (legacy->False, not in _key)"
```

---

### Task 11: Nonreproducible matcher compares `qa_dataset_capped`

**Files:**
- Modify: `src/science_tool/validate/checks/evidence_lines.py` (after the `authored_capped` diff ~line 553-554)
- Test: `tests/validate/test_checks_evidence_lines.py`

- [ ] **Step 1: Write the failing test**

Add a test mirroring the existing `authored_capped` nonreproducible test in that file: a stored
snapshot row with `qa_dataset_capped: false` vs a recomputed result with `True` (same inputs)
yields a `belief.nonreproducible` ERROR whose diffs include `qa_dataset_capped`. If that file
drives the check through a built fixture, follow the same fixture pattern; otherwise unit-test
the diff branch by constructing `prior`/`now` dicts if the helper is reachable.

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src:model/src rtk proxy uv run --frozen pytest tests/validate/test_checks_evidence_lines.py -k nonreproducible -v`
Expected: FAIL — `qa_dataset_capped` not compared.

- [ ] **Step 3: Write minimal implementation**

In `evidence_lines.py`, after the `authored_capped` comparison (line 553-554):

```python
        if prior.get("authored_capped", False) != now.get("authored_capped", False):
            diffs.append("authored_capped")
        if prior.get("qa_dataset_capped", False) != now.get("qa_dataset_capped", False):
            diffs.append("qa_dataset_capped")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src:model/src rtk proxy uv run --frozen pytest tests/validate/test_checks_evidence_lines.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
rtk git add src/science_tool/validate/checks/evidence_lines.py tests/validate/test_checks_evidence_lines.py
rtk git commit -m "feat(validate): nonreproducible matcher compares qa_dataset_capped"
```

---

### Task 12: Full regression + lint sweep

**Files:** none (verification only)

- [ ] **Step 1: Run the full belief + dataset + validate suites**

Run:
```bash
PYTHONPATH=src:model/src rtk proxy uv run --frozen pytest \
  tests/ -k "belief or dataset or workbench or evidence or snapshot" -q
```
Expected: PASS, no regressions. Then a broader sweep:
```bash
PYTHONPATH=src:model/src rtk proxy uv run --frozen pytest tests/ model/tests/ -q
```
Expected: green (same baseline count + new tests).

- [ ] **Step 2: Lint the touched files**

Run:
```bash
rtk proxy uv run --frozen ruff check \
  src/science_tool/graph/belief.py src/science_tool/graph/belief_policy.py \
  src/science_tool/graph/belief_snapshot.py src/science_tool/graph/bundle_belief.py \
  src/science_tool/graph/dataset_independence.py src/science_tool/graph/dataset_qa.py \
  src/science_tool/graph/materialize.py src/science_tool/validate/checks/evidence_lines.py \
  model/src/science_model/entities.py
```
Expected: no errors (fix any inline, amend the relevant commit).

- [ ] **Step 3: No commit needed unless lint fixes were made.**

---

## Self-review notes

- **Spec coverage:** model field (T1), policy knob (T2), EvidenceUnit+predicate (T3),
  refutation symmetry + `_base_magnitude` (T4), ceiling + BeliefResult fields (T5), dependence
  helper (T6), materialization layer (T7), wiring + e2e (T8), bundle rollup (T9), snapshot
  persistence (T10), validator (T11), regression/lint (T12). All design sections map to a task.
- **Behavior-neutrality** is pinned by T4's regression run and T12's full sweep; the only
  intended behavior change appears once a dataset opts in (T8 e2e).
- **Type consistency:** `qa_dataset_capped: bool` and `qa_failed_datasets: tuple[str, ...]`
  used identically across `BeliefResult`/`BundleBeliefResult`/snapshot; `is_qa_failed(u)` takes
  only the unit (no policy); `_base_magnitude(support, contested_groups, *, policy)` and
  `_contested_groups_for(support, dispute)` signatures are fixed in T4 and reused in T5.
- **No patch RDF surface** (matches `authored_capped`).
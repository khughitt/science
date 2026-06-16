# Authored-Confidence-as-Input Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give an authored assertion (the `expert_judgment` evidence type) a disciplined path into `aggregate_belief` — admitted by a range-validated confidence *gate* (run before independence reduction), bounded by an authored-only *ceiling*, and barred from being a qualifying direct test on either side — all keyed off new `BeliefPolicy` knobs.

**Architecture:** Extends the Slice-A `BeliefPolicy` socket (`graph/belief_policy.py`). Three new policy knobs (`authored_assertion_type`, `authored_min_confidence`, `authored_only_ceiling`) drive (1) a confidence gate that partitions raw units *before* `reduce_units`, (2) an authored-only ceiling applied after the existing magnitude + refutation-cap logic, and (3) exclusion of authored assertions from `is_qualifying_direct_test`. New derived flag `authored_capped` is stamped on `BeliefResult`, rolled up onto `BundleBeliefResult`, persisted on both snapshot branches (legacy rows normalized to `False`), and compared by the reproducibility check.

**Tech Stack:** Python 3.12, frozen dataclasses, `rdflib`, pytest. Belief engine lives in `science/src/science_tool/graph/`.

---

## Conventions (read once before starting)

- **Canonical working directory:** all commands run from the **`science/` member dir** (the one holding `pyproject.toml`). In an execution worktree this is `~/d/science/.worktrees/authored-confidence/science`; verify with `rtk git rev-parse --abbrev-ref HEAD` and `pwd` before any commit, and confirm you are NOT on `main`.
- **Tests / lint:** `rtk proxy uv run --frozen pytest <args>` and `rtk proxy uv run --frozen ruff check <path>`. (`rtk` has no `uv`/`pytest`/`ruff` subcommand; `rtk proxy` passes the raw command through.)
- **Git:** `rtk git add ...` / `rtk git commit ...`. **No `Co-Authored-By` trailers.**
- **`science_model` must never import `science_tool`.** This slice touches only `science_tool` belief/validate code plus tests; the `EvidenceLineEntity.confidence` field already exists in `science_model` and is **not** modified.
- **Design reference:** `docs/plans/2026-06-16-authored-confidence-design.md`. The Slice-A keystone it builds on: `docs/plans/2026-06-16-belief-policy-keystone-{design,plan}.md`.

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `src/science_tool/graph/belief_weights.py` | Canonical ordinal constants | **Modify**: add `MAGNITUDE_NAMES` |
| `src/science_tool/graph/belief_policy.py` | Frozen versioned policy object | **Modify**: 3 new knobs + `__post_init__` validation |
| `src/science_tool/graph/belief.py` | `EvidenceUnit`, helpers, `aggregate_belief`, `BeliefResult` | **Modify**: `confidence` field, 2 helpers, gate-before-reduce, ceiling, `is_qualifying_direct_test` exclusion, 2 new `BeliefResult` fields |
| `src/science_tool/graph/bundle_belief.py` | Bundle rollup | **Modify**: `BundleBeliefResult.authored_capped` + OR-rollup |
| `src/science_tool/graph/belief_snapshot.py` | Append-only JSONL belief history | **Modify**: persist `authored_capped` both branches + legacy default |
| `src/science_tool/validate/checks/evidence_lines.py` | Evidence-line validators | **Modify**: unscored-line authored branch + nonreproducible `authored_capped` |
| `tests/test_belief_weights.py` | weights/constants tests | **Modify**: reconciliation test |
| `tests/test_authored_confidence_policy.py` | policy-knob validation | **Create** |
| `tests/test_authored_confidence.py` | gate/ceiling/symmetry/ordering/recognition | **Create** |
| `tests/test_bundle_belief_rollup.py` | bundle rollup tests | **Modify**: `authored_capped` rollup |
| `tests/test_belief_snapshot.py` | single-claim snapshot tests | **Modify**: single-row persistence + legacy normalization |
| `tests/test_bundle_belief_snapshot.py` | bundle snapshot tests | **Modify**: bundle-row persistence |
| `tests/validate/test_checks_evidence_lines.py` | `check_evidence_unscored_line` tests | **Modify**: authored-assertion branch |
| `tests/validate/test_checks_belief_sensitivity.py` | `belief.nonreproducible` tests | **Modify**: legacy `authored_capped` reproducibility |

Tasks are ordered by dependency: 1 → 2 → 3 → 4 → 5 → 6 → 7. Do them in order.

---

## Task 1: `MAGNITUDE_NAMES` canonical tuple

**Files:**
- Modify: `src/science_tool/graph/belief_weights.py`
- Test: `tests/test_belief_weights.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_belief_weights.py`:

```python
def test_magnitude_names_reconcile_with_enum():
    from science_tool.graph.belief import BeliefMagnitude
    from science_tool.graph.belief_weights import MAGNITUDE_NAMES

    # MAGNITUDE_NAMES is the cycle-free home for the magnitude strings (belief_weights
    # imports nothing internal); it must stay in lock-step with the BeliefMagnitude enum.
    assert set(MAGNITUDE_NAMES) == {m.value for m in BeliefMagnitude}
    # Ordering matches the ordinal ladder used by aggregate_belief.
    assert MAGNITUDE_NAMES == ("speculative", "fragile", "supported", "well_supported")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `rtk proxy uv run --frozen pytest tests/test_belief_weights.py::test_magnitude_names_reconcile_with_enum -v`
Expected: FAIL with `ImportError: cannot import name 'MAGNITUDE_NAMES'`.

- [ ] **Step 3: Add the constant**

In `src/science_tool/graph/belief_weights.py`, after the `STRENGTH_RANK` definition (the line `STRENGTH_RANK = {"strong": 3, "moderate": 2, "weak": 1}`), add:

```python
# Canonical belief-magnitude names, lowest→highest. belief_weights imports nothing
# internal, so this is the cycle-free home for the magnitude strings that belief_policy
# validates against (BeliefMagnitude itself lives in belief.py, which would form a cycle).
# A reconciliation test (tests/test_belief_weights.py) keeps this in lock-step with the enum.
MAGNITUDE_NAMES = ("speculative", "fragile", "supported", "well_supported")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `rtk proxy uv run --frozen pytest tests/test_belief_weights.py::test_magnitude_names_reconcile_with_enum -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
rtk git add src/science_tool/graph/belief_weights.py tests/test_belief_weights.py
rtk git commit -m "feat(belief): add MAGNITUDE_NAMES canonical magnitude tuple (Slice B t1)"
```

---

## Task 2: Three `BeliefPolicy` knobs + construction-time validation

**Files:**
- Modify: `src/science_tool/graph/belief_policy.py`
- Test: `tests/test_authored_confidence_policy.py` (create)
- Test: `tests/test_belief_policy.py` (modify — the one direct `BeliefPolicy(...)` constructor)

- [ ] **Step 1: Write the failing test**

Create `tests/test_authored_confidence_policy.py`:

```python
from dataclasses import replace

import pytest

from science_tool.graph.belief_policy import DEFAULT_BELIEF_POLICY, BeliefPolicy


def test_default_policy_authored_knobs():
    assert DEFAULT_BELIEF_POLICY.authored_assertion_type == "expert_judgment"
    assert DEFAULT_BELIEF_POLICY.authored_min_confidence == 0.5
    assert DEFAULT_BELIEF_POLICY.authored_only_ceiling == "fragile"


def test_min_confidence_out_of_range_rejected():
    with pytest.raises(ValueError):
        replace(DEFAULT_BELIEF_POLICY, policy_id="bad", version="1", authored_min_confidence=1.5)
    with pytest.raises(ValueError):
        replace(DEFAULT_BELIEF_POLICY, policy_id="bad", version="1", authored_min_confidence=-0.1)


def test_unknown_ceiling_rejected():
    with pytest.raises(ValueError):
        replace(DEFAULT_BELIEF_POLICY, policy_id="bad", version="1", authored_only_ceiling="bogus")


def test_valid_ceiling_accepted():
    p = replace(DEFAULT_BELIEF_POLICY, policy_id="ok", version="1", authored_only_ceiling="supported")
    assert p.authored_only_ceiling == "supported"


def test_authored_knobs_immutable():
    with pytest.raises(Exception):
        DEFAULT_BELIEF_POLICY.authored_min_confidence = 0.9  # frozen dataclass
```

- [ ] **Step 2: Run test to verify it fails**

Run: `rtk proxy uv run --frozen pytest tests/test_authored_confidence_policy.py -v`
Expected: FAIL — `TypeError: __init__() got an unexpected keyword argument 'authored_assertion_type'` (or `AttributeError` on the missing attribute).

- [ ] **Step 3: Add the knobs + validation**

In `src/science_tool/graph/belief_policy.py`:

3a. Extend the `belief_weights` import (the existing `from .belief_weights import (...)` block) to also import `MAGNITUDE_NAMES`:

```python
from .belief_weights import (
    CIRCULAR, CURATION_STEP_PENALTY, DIAGNOSTIC_ROLES, EVIDENCE_ROLE_RANK,
    EVIDENCE_TYPE_RANK, GATED_PROXY, INDEPENDENT, MAGNITUDE_NAMES, ROLE_DIRECT_TEST,
    SCOPE_WHOLE_CLAIM, SHARED_SOURCE, STRENGTH_RANK,
)
```

3b. Add three fields to the `BeliefPolicy` dataclass, immediately after `well_supported_requires_direct_test: bool` (the last existing field):

```python
    # Authored-confidence knobs (Spec 5 Slice B). An authored assertion is a unit whose
    # normalized evidence_type == authored_assertion_type; it is admitted by a confidence
    # gate (authored_min_confidence) and, when support is authored-only, capped at
    # authored_only_ceiling. Ceiling is a magnitude STRING (not BeliefMagnitude) so this
    # module keeps importing only belief_weights — no cycle with belief.py.
    authored_assertion_type: str
    authored_min_confidence: float
    authored_only_ceiling: str
```

3c. Extend `__post_init__` (after the existing `object.__setattr__(... "diagnostic_roles" ...)` line) with fail-early validation:

```python
        # Fail early on out-of-discipline authored knobs (Spec 5 Slice B). Validated against
        # MAGNITUDE_NAMES rather than BeliefMagnitude to avoid importing belief.py (cycle).
        if not 0.0 <= self.authored_min_confidence <= 1.0:
            raise ValueError(
                f"authored_min_confidence must be in [0, 1], got {self.authored_min_confidence!r}"
            )
        if self.authored_only_ceiling not in MAGNITUDE_NAMES:
            raise ValueError(
                f"authored_only_ceiling must be one of {MAGNITUDE_NAMES}, "
                f"got {self.authored_only_ceiling!r}"
            )
```

3d. Add the three values to the `DEFAULT_BELIEF_POLICY` constructor, after `well_supported_requires_direct_test=True,`:

```python
    authored_assertion_type="expert_judgment",
    authored_min_confidence=0.5,
    authored_only_ceiling="fragile",
```

3e. The new fields are **required** (no defaults — matching the keystone's all-fields-required discipline). Exactly one direct `BeliefPolicy(...)` constructor exists outside `DEFAULT_BELIEF_POLICY`: `tests/test_belief_policy.py` `test_constructor_normalizes_mutable_containers` (~line 41). Add the three kwargs to that constructor, after `well_supported_min_clean_support=2, well_supported_requires_direct_test=True,`:

```python
        authored_assertion_type="expert_judgment",
        authored_min_confidence=0.5,
        authored_only_ceiling="fragile",
```

(All other `BeliefPolicy` instances are built via `DEFAULT_BELIEF_POLICY` or `dataclasses.replace(DEFAULT_BELIEF_POLICY, ...)`, which already carry the new fields — no other call site changes.)

- [ ] **Step 4: Run test to verify it passes**

Run: `rtk proxy uv run --frozen pytest tests/test_authored_confidence_policy.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Run the Slice-A policy suite to confirm no regression**

Run: `rtk proxy uv run --frozen pytest tests/test_belief_policy.py tests/test_belief_policy_aggregate.py -v`
Expected: PASS (all existing policy tests still green — `test_belief_policy.py`'s direct constructor was updated in Step 3e; every other call site builds from `DEFAULT_BELIEF_POLICY`).

- [ ] **Step 6: Commit**

```bash
rtk git add src/science_tool/graph/belief_policy.py tests/test_authored_confidence_policy.py tests/test_belief_policy.py
rtk git commit -m "feat(belief): add authored-confidence knobs to BeliefPolicy with construction validation (Slice B t2)"
```

---

## Task 3: `EvidenceUnit.confidence` + recognition/gate helpers

**Files:**
- Modify: `src/science_tool/graph/belief.py`
- Test: `tests/test_authored_confidence.py` (create)

- [ ] **Step 1: Write the failing test**

Create `tests/test_authored_confidence.py`:

```python
from science_tool.graph.belief import (
    EvidenceUnit,
    _authored_assertion_counts,
    is_authored_assertion,
)
from science_tool.graph.belief_policy import DEFAULT_BELIEF_POLICY


def _u(**kw) -> EvidenceUnit:
    base = dict(
        line_uri="a", stance="supports", strength=None, independence="independent",
        independence_group=None, evidence_role=None, evidence_type="expert_judgment",
        dispute_scope=None, proxy_directness=None, has_measurement_model=False,
        source=None, observability_keys=(), is_reference_dataset=False,
    )
    base.update(kw)
    return EvidenceUnit(**base)


def test_confidence_defaults_none():
    assert _u().confidence is None


def test_positional_constructor_still_builds():
    # 12 positional args (through observability_keys) — the historical call shape. Adding
    # confidence as the LAST field must not break it.
    u = EvidenceUnit("a", "supports", "medium", None, None, None, None, None, None, False, None, ())
    assert u.confidence is None


def test_is_authored_assertion_by_type():
    assert is_authored_assertion(_u(evidence_type="expert_judgment"))
    assert is_authored_assertion(_u(evidence_type="expert_judgment_evidence"))  # suffix normalized
    assert not is_authored_assertion(_u(evidence_type="empirical_data"))
    assert not is_authored_assertion(_u(evidence_type=None))


def test_gate_admits_at_or_above_threshold():
    assert _authored_assertion_counts(_u(confidence=0.5), policy=DEFAULT_BELIEF_POLICY)
    assert _authored_assertion_counts(_u(confidence=0.9), policy=DEFAULT_BELIEF_POLICY)


def test_gate_rejects_below_threshold_none_and_out_of_range():
    p = DEFAULT_BELIEF_POLICY
    assert not _authored_assertion_counts(_u(confidence=0.3), policy=p)
    assert not _authored_assertion_counts(_u(confidence=None), policy=p)
    assert not _authored_assertion_counts(_u(confidence=1.2), policy=p)   # range-rejected
    assert not _authored_assertion_counts(_u(confidence=-0.1), policy=p)  # range-rejected
```

- [ ] **Step 2: Run test to verify it fails**

Run: `rtk proxy uv run --frozen pytest tests/test_authored_confidence.py -v`
Expected: FAIL — `ImportError: cannot import name '_authored_assertion_counts'` (and `is_authored_assertion`).

- [ ] **Step 3: Add the field + helpers**

In `src/science_tool/graph/belief.py`:

3a. Add `confidence` as the **last** field of `EvidenceUnit` (immediately after `quant_prob_sign: float | None = None`):

```python
    # Authored confidence (Spec 5 Slice B). The materialized SCI_NS.confidence value, read
    # for authored assertions. LAST field so the many positional EvidenceUnit(...) test
    # constructors (12 positional args through observability_keys) stay behavior-neutral.
    confidence: float | None = None
```

3b. In `_read_unit`, add to the `EvidenceUnit(...)` constructor (after the `quant_prob_sign=...` keyword line):

```python
        confidence=_float_lit(provenance, line, SCI_NS.confidence),
```

3c. Add the two helpers immediately after the existing `is_diagnostic` function (before `is_proxy_gated`):

```python
def is_authored_assertion(u: EvidenceUnit, *, policy: BeliefPolicy = DEFAULT_BELIEF_POLICY) -> bool:
    """Pure type contract: a unit is an authored assertion iff its normalized evidence_type
    equals policy.authored_assertion_type (default 'expert_judgment'). dataset_usage is NOT
    inspected — recognition keys solely on the type (design §Goal)."""
    return normalize_evidence_type(u.evidence_type) == policy.authored_assertion_type


def _authored_assertion_counts(u: EvidenceUnit, *, policy: BeliefPolicy = DEFAULT_BELIEF_POLICY) -> bool:
    """Range-validated confidence gate. Confidence is a GATE not a dial: it admits/rejects a
    unit but never scales it. Range check precedes the threshold so confidence=1.2 cannot
    slip past authored_min_confidence."""
    c = u.confidence
    return c is not None and 0.0 <= c <= 1.0 and c >= policy.authored_min_confidence
```

Note: `normalize_evidence_type` is already imported at the top of `belief.py` (`from .belief_weights import ... normalize_evidence_type`), and `BeliefPolicy`/`DEFAULT_BELIEF_POLICY` are already imported.

- [ ] **Step 4: Run test to verify it passes**

Run: `rtk proxy uv run --frozen pytest tests/test_authored_confidence.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Run the full belief unit suite for behavior-neutrality**

Run: `rtk proxy uv run --frozen pytest tests/test_belief_aggregate.py tests/test_belief_collect.py tests/test_belief_reduce.py tests/test_belief_refutation.py tests/test_belief_policy_aggregate.py -v`
Expected: PASS — adding a defaulted trailing field and read-only helpers changes no existing behavior.

- [ ] **Step 6: Commit**

```bash
rtk git add src/science_tool/graph/belief.py tests/test_authored_confidence.py
rtk git commit -m "feat(belief): EvidenceUnit.confidence + authored-assertion recognition/gate helpers (Slice B t3)"
```

---

## Task 4: Gate-before-reduce, authored-only ceiling, refutation symmetry

**Files:**
- Modify: `src/science_tool/graph/belief.py`
- Test: `tests/test_authored_confidence.py` (extend)

This is the core task. `aggregate_belief` currently (verbatim, `belief.py` lines 268-317):

```python
def aggregate_belief(units: list[EvidenceUnit], *, policy: BeliefPolicy = DEFAULT_BELIEF_POLICY) -> BeliefResult:
    reduced = reduce_units(units, policy=policy)
    cg = reduced.contested_groups
    ...
    if n_support == 0:
        magnitude = BeliefMagnitude.SPECULATIVE
    ...
    capped = False
    if decisive and _MAG_ORDER.index(magnitude) > _MAG_ORDER.index(BeliefMagnitude.FRAGILE):
        magnitude = BeliefMagnitude.FRAGILE
        capped = True
    ...
    return BeliefResult(... )
```

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_authored_confidence.py`:

```python
from science_tool.graph.belief import BeliefMagnitude, aggregate_belief


def _empirical(**kw) -> EvidenceUnit:
    base = dict(
        line_uri="e", stance="supports", strength="strong", independence="independent",
        independence_group=None, evidence_role="direct_test", evidence_type="empirical_data",
        dispute_scope=None, proxy_directness=None, has_measurement_model=False,
        source=None, observability_keys=(), is_reference_dataset=False, confidence=None,
    )
    base.update(kw)
    return EvidenceUnit(**base)


def test_single_authored_assertion_is_fragile():
    r = aggregate_belief([_u(line_uri="a", confidence=0.9)])
    assert r.magnitude == BeliefMagnitude.FRAGILE
    assert r.authored_capped is False  # n_support==1 -> FRAGILE already; ceiling is a no-op


def test_two_authored_assertions_capped_to_fragile():
    r = aggregate_belief([_u(line_uri="a", confidence=0.9), _u(line_uri="b", confidence=0.9)])
    # Two clean supports would compute SUPPORTED; authored-only ceiling caps to FRAGILE.
    assert r.magnitude == BeliefMagnitude.FRAGILE
    assert r.authored_capped is True


def test_sub_threshold_authored_excluded_and_speculative():
    r = aggregate_belief([_u(line_uri="a", confidence=0.3)])
    assert r.magnitude == BeliefMagnitude.SPECULATIVE
    assert [u.line_uri for u in r.excluded_authored_confidence] == ["a"]
    assert r.support_units == []


def test_out_of_range_authored_excluded():
    r = aggregate_belief([_u(line_uri="a", confidence=1.2)])
    assert r.magnitude == BeliefMagnitude.SPECULATIVE
    assert [u.line_uri for u in r.excluded_authored_confidence] == ["a"]


def test_authored_corroborates_but_empirical_path_untouched():
    # Two clean empirical direct tests -> WELL_SUPPORTED; an authored assertion alongside
    # must NOT cap it (mixed support is not authored-only).
    units = [
        _empirical(line_uri="e1", independence_group="g1"),
        _empirical(line_uri="e2", independence_group="g2"),
        _u(line_uri="a", confidence=0.9),
    ]
    r = aggregate_belief(units)
    assert r.magnitude == BeliefMagnitude.WELL_SUPPORTED
    assert r.authored_capped is False


def test_authored_dispute_is_not_decisive_refutation():
    # An authored dispute with role=direct_test, strong, independent, whole_claim would be a
    # decisive refutation IF it were a qualifying direct test — refutation symmetry bars it.
    support = [
        _empirical(line_uri="e1", independence_group="g1"),
        _empirical(line_uri="e2", independence_group="g2"),
    ]
    authored_dispute = _u(
        line_uri="d", stance="disputes", strength="strong", evidence_role="direct_test",
        evidence_type="expert_judgment", confidence=0.9, dispute_scope="whole_claim",
    )
    r = aggregate_belief([*support, authored_dispute])
    assert r.capped_by_refutation is False        # authored dispute cannot decisively cap
    assert r.magnitude == BeliefMagnitude.WELL_SUPPORTED
    assert r.contested is True                     # but it IS recorded as a dispute


def test_gate_failing_authored_dispute_has_zero_downstream_effect():
    # A gate-failing authored dispute sharing a group must NOT reach reduce_units: contested,
    # contested_groups, winners and clean_support must equal the same scenario without it.
    base = [
        _empirical(line_uri="e1", independence_group="g1"),
        _empirical(line_uri="e2", independence_group="g2"),
    ]
    rejected = _u(
        line_uri="d", stance="disputes", evidence_type="expert_judgment",
        independence_group="g1", confidence=0.3,  # below threshold -> rejected
    )
    r_without = aggregate_belief(base)
    r_with = aggregate_belief([*base, rejected])
    assert r_with.magnitude == r_without.magnitude
    assert r_with.contested == r_without.contested
    assert r_with.contested_groups == r_without.contested_groups
    assert {u.line_uri for u in r_with.support_units} == {u.line_uri for u in r_without.support_units}
    assert [u.line_uri for u in r_with.excluded_authored_confidence] == ["d"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `rtk proxy uv run --frozen pytest tests/test_authored_confidence.py -k "authored or gate_failing or corroborates or capped or speculative or out_of_range" -v`
Expected: FAIL — `AttributeError: 'BeliefResult' object has no attribute 'authored_capped'` (and `excluded_authored_confidence`).

- [ ] **Step 3: Add the two `BeliefResult` fields**

In `src/science_tool/graph/belief.py`, add to the `BeliefResult` dataclass after `policy_version: str = DEFAULT_BELIEF_POLICY.version` (the current last two fields are `policy_id` / `policy_version`):

```python
    authored_capped: bool = False
    excluded_authored_confidence: list[EvidenceUnit] = field(default_factory=list)
```

Ensure `field` is imported: the top of `belief.py` imports `from dataclasses import dataclass, replace` — change it to `from dataclasses import dataclass, field, replace`.

- [ ] **Step 4: Exclude authored assertions from `is_qualifying_direct_test`**

Replace the existing one-line body of `is_qualifying_direct_test`:

```python
def is_qualifying_direct_test(u: EvidenceUnit, *, policy: BeliefPolicy = DEFAULT_BELIEF_POLICY) -> bool:
    return u.evidence_role == policy.direct_test_role and not is_proxy_gated(u, policy=policy)
```

with the authored-exclusion variant:

```python
def is_qualifying_direct_test(u: EvidenceUnit, *, policy: BeliefPolicy = DEFAULT_BELIEF_POLICY) -> bool:
    # Refutation symmetry (Slice B): an authored assertion is never a qualifying direct test,
    # so it can neither satisfy WELL_SUPPORTED's direct-test gate nor be a decisive refutation.
    return (
        u.evidence_role == policy.direct_test_role
        and not is_proxy_gated(u, policy=policy)
        and not is_authored_assertion(u, policy=policy)
    )
```

- [ ] **Step 5: Gate before reduce + apply ceiling in `aggregate_belief`**

Replace the head of `aggregate_belief` — the single line:

```python
    reduced = reduce_units(units, policy=policy)
```

with the gate-first partition:

```python
    # Gate authored assertions on the RAW units list, BEFORE reduce_units (design §Pipeline
    # ordering). A gate-failing authored unit must have zero downstream effect — it must not
    # win a collapse, perturb contested_groups, or flip contested — so it never enters reduction.
    admitted: list[EvidenceUnit] = []
    excluded_authored_confidence: list[EvidenceUnit] = []
    for u in units:
        if is_authored_assertion(u, policy=policy) and not _authored_assertion_counts(u, policy=policy):
            excluded_authored_confidence.append(u)
        else:
            admitted.append(u)

    reduced = reduce_units(admitted, policy=policy)
```

Then, immediately **after** the decisive-refutation cap block (the `if decisive and ...: magnitude = BeliefMagnitude.FRAGILE; capped = True` block) and **before** the `contested = (...)` assignment, insert the authored-only ceiling:

```python
    # Authored-only ceiling (design §The ceiling): when EVERY counted support unit is an
    # authored assertion, belief cannot exceed authored_only_ceiling. Applied after the
    # refutation cap; a no-op when the magnitude is already at/below the ceiling.
    authored_capped = False
    if support and all(is_authored_assertion(u, policy=policy) for u in support):
        ceiling = BeliefMagnitude(policy.authored_only_ceiling)
        if _MAG_ORDER.index(magnitude) > _MAG_ORDER.index(ceiling):
            magnitude = ceiling
            authored_capped = True
```

Finally, add the two new fields to the `return BeliefResult(...)` call, after `policy_version=policy.version,`:

```python
        authored_capped=authored_capped,
        excluded_authored_confidence=excluded_authored_confidence,
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `rtk proxy uv run --frozen pytest tests/test_authored_confidence.py -v`
Expected: PASS (all tests in the file, ~12).

- [ ] **Step 7: Run the full belief + downstream suite for empirical behavior-neutrality**

Run: `rtk proxy uv run --frozen pytest tests/test_belief_aggregate.py tests/test_belief_collect.py tests/test_belief_reduce.py tests/test_belief_refutation.py tests/test_belief_e2e.py tests/test_belief_classify.py tests/test_belief_policy_aggregate.py tests/test_evidence_line_belief_checks.py -v`
Expected: PASS — empirical-only belief is unchanged (no fixture uses `expert_judgment`).

- [ ] **Step 8: Commit**

```bash
rtk git add src/science_tool/graph/belief.py tests/test_authored_confidence.py
rtk git commit -m "feat(belief): authored confidence gate-before-reduce, authored-only ceiling, refutation symmetry (Slice B t4)"
```

---

## Task 5: Bundle rollup of `authored_capped`

**Files:**
- Modify: `src/science_tool/graph/bundle_belief.py`
- Test: `tests/test_bundle_belief_rollup.py` (extend)

- [ ] **Step 1: Write the failing test**

The file already imports (at module scope) `CompositionRule` from `science_model.reasoning`, plus `BeliefMagnitude`, `BeliefResult`, `MemberBelief`, `member_rank_key`, `roll_up_weakest_link`. It uses `rule=CompositionRule.ALL_STEPS` in its existing rollup tests. Append a test that builds members whose `BeliefResult` carries `authored_capped` (build `BeliefResult` directly so you can set the new flag — the file's `_belief` helper does not accept it):

```python
def test_bundle_rolls_up_authored_capped_as_or():
    def _capped_member(uri: str, *, authored_capped: bool) -> MemberBelief:
        belief = BeliefResult(
            magnitude=BeliefMagnitude.FRAGILE, contested=False, capped_by_refutation=False,
            support_units=[], dispute_units=[], diagnostics=[], contested_groups=set(),
            excluded=[], flagged_ungrouped=[], authored_capped=authored_capped,
        )
        return MemberBelief(member_uri=uri, belief=belief, scalar=None,
                            rank_key=member_rank_key(belief, None, uri))

    none_capped = roll_up_weakest_link(
        [_capped_member("p:a", authored_capped=False), _capped_member("p:b", authored_capped=False)],
        rule=CompositionRule.ALL_STEPS,
    )
    assert none_capped.authored_capped is False

    one_capped = roll_up_weakest_link(
        [_capped_member("p:a", authored_capped=False), _capped_member("p:b", authored_capped=True)],
        rule=CompositionRule.ALL_STEPS,
    )
    assert one_capped.authored_capped is True  # OR across members, mirroring capped_by_refutation
```

- [ ] **Step 2: Run test to verify it fails**

Run: `rtk proxy uv run --frozen pytest tests/test_bundle_belief_rollup.py::test_bundle_rolls_up_authored_capped_as_or -v`
Expected: FAIL — `TypeError: __init__() got an unexpected keyword argument 'authored_capped'` (BundleBeliefResult has no such field).

- [ ] **Step 3: Add the field + rollup**

In `src/science_tool/graph/bundle_belief.py`:

3a. Add to the `BundleBeliefResult` dataclass after `policy_version: str` (the current last field):

```python
    authored_capped: bool
```

3b. In `roll_up_weakest_link`, add to the `return BundleBeliefResult(...)` call after `policy_version=ordered[0].belief.policy_version,`:

```python
        authored_capped=any(m.belief.authored_capped for m in ordered),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `rtk proxy uv run --frozen pytest tests/test_bundle_belief_rollup.py::test_bundle_rolls_up_authored_capped_as_or -v`
Expected: PASS.

- [ ] **Step 5: Run the full bundle suite for no regression**

Run: `rtk proxy uv run --frozen pytest tests/test_bundle_belief_rollup.py tests/test_bundle_belief_snapshot.py -v`
Expected: PASS — every existing `BundleBeliefResult(...)` construction is via `roll_up_weakest_link`, which now supplies the new required field.

- [ ] **Step 6: Commit**

```bash
rtk git add src/science_tool/graph/bundle_belief.py tests/test_bundle_belief_rollup.py
rtk git commit -m "feat(belief): roll up authored_capped onto BundleBeliefResult as OR over members (Slice B t5)"
```

---

## Task 6: Persist `authored_capped` (both branches) + legacy normalization

**Files:**
- Modify: `src/science_tool/graph/belief_snapshot.py`
- Test: `tests/test_belief_snapshot.py` (extend — single-claim row + normalizer)
- Test: `tests/test_bundle_belief_snapshot.py` (extend — bundle row)

- [ ] **Step 1: Write the failing tests**

1a. Append to `tests/test_belief_snapshot.py`. The first test proves the **single-claim** row branch persists the flag (`_graphs()` builds one empirical support line → FRAGILE, single-claim branch); the other two cover the legacy normalizer:

```python
def test_snapshot_single_row_persists_authored_capped():
    k, p = _graphs()
    row = snapshot_records(k, p, scalar_enabled=False, as_of="2026-05-24")[0]
    assert row["is_bundle"] is False
    assert row["authored_capped"] is False  # empirical support -> ceiling never fires


def test_with_policy_defaults_backfills_authored_capped():
    from science_tool.graph.belief_snapshot import _with_policy_defaults

    legacy = {"as_of": "x", "claim": "c", "belief_state": "fragile"}  # pre-Slice-B row
    out = _with_policy_defaults(legacy)
    assert out["authored_capped"] is False
    # Slice-A policy identity still backfilled too.
    assert out["policy_id"] == "core-default"
    assert out["policy_version"] == "1"


def test_existing_authored_capped_is_preserved():
    from science_tool.graph.belief_snapshot import _with_policy_defaults

    row = {"as_of": "x", "claim": "c", "policy_id": "p", "policy_version": "2",
           "authored_capped": True}
    out = _with_policy_defaults(row)
    assert out["authored_capped"] is True
```

1b. Append to `tests/test_bundle_belief_snapshot.py` a test proving the **bundle** row branch persists the flag. The file already provides module-level `_strong(k, prov, target, gid)`, `MECH`, `PA`, `PB`, and imports `Graph`, `snapshot_records`, `SCI_NS`, `RDF` — reuse them directly (this is the exact graph `test_snapshot_emits_mechanism_bundle_row` builds):

```python
def test_snapshot_bundle_row_persists_authored_capped():
    k, prov = Graph(), Graph()
    k.add((MECH, RDF.type, SCI_NS.Mechanism))
    for p in (PA, PB):
        k.add((p, RDF.type, SCI_NS.Proposition))
        k.add((MECH, SCI_NS.hasProposition, p))
    _strong(k, prov, PA, "g1")
    _strong(k, prov, PA, "g2")
    _strong(k, prov, PB, "g3")
    rows = snapshot_records(k, prov, scalar_enabled=False, as_of="2026-06-11")
    row = next(r for r in rows if r["is_bundle"])
    assert row["authored_capped"] is False  # strong empirical members -> ceiling never fires
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `rtk proxy uv run --frozen pytest tests/test_belief_snapshot.py -k authored_capped tests/test_bundle_belief_snapshot.py -k authored_capped -v`
Expected: FAIL — `KeyError: 'authored_capped'` on the row dicts (snapshot_records does not persist it yet) and on `_with_policy_defaults` (normalizer does not add it yet).

- [ ] **Step 3: Persist + normalize**

In `src/science_tool/graph/belief_snapshot.py`:

3a. In `snapshot_records`, add `authored_capped` to the **bundle** row dict (after `"capped_by_refutation": result.capped_by_refutation,`):

```python
                "authored_capped": result.authored_capped,
```

3b. Add `authored_capped` to the **plain** row dict (after `"contested": result.contested,` in the `is_bundle=False` branch — the second `rows.append({...})`):

```python
            "authored_capped": result.authored_capped,
```

3c. Extend `_with_policy_defaults` to backfill `authored_capped` for legacy rows:

```python
def _with_policy_defaults(row: dict) -> dict:
    # Pre-policy snapshot rows predate Spec 5 Slice A; they were computed by the
    # core-default policy. Stamp that identity explicitly so dedup and reproducibility
    # checks are policy-aware without rejecting or KeyError-ing on legacy history.
    if "policy_id" not in row:
        row["policy_id"] = DEFAULT_BELIEF_POLICY.policy_id
        row["policy_version"] = DEFAULT_BELIEF_POLICY.version
    # Pre-Slice-B rows have no authored-only ceiling: False is the semantically correct
    # value, not a silent fallback. NOT added to _key (a derived flag, like
    # capped_by_refutation, not part of belief identity).
    if "authored_capped" not in row:
        row["authored_capped"] = False
    return row
```

Note: do **not** touch `_key` — `authored_capped` is a derived flag, not part of belief identity.

- [ ] **Step 4: Run tests to verify they pass**

Run: `rtk proxy uv run --frozen pytest tests/test_belief_snapshot.py tests/test_bundle_belief_snapshot.py -k "authored_capped or persists_authored" -v`
Expected: PASS (single-claim row + bundle row + 2 normalizer tests).

- [ ] **Step 5: Run the full snapshot suite for no regression**

Run: `rtk proxy uv run --frozen pytest tests/test_belief_snapshot.py tests/test_bundle_belief_snapshot.py tests/test_belief_cli.py -v`
Expected: PASS. (If `tests/test_belief_cli.py` has a canned snapshot-row fixture that is compared field-for-field, add `"authored_capped": False` to it — mirror what the Slice-A change did for `policy_id`/`policy_version`.)

- [ ] **Step 6: Commit**

```bash
rtk git add src/science_tool/graph/belief_snapshot.py tests/test_belief_snapshot.py tests/test_bundle_belief_snapshot.py tests/test_belief_cli.py
rtk git commit -m "feat(belief): persist authored_capped on both snapshot branches + legacy default normalization (Slice B t6)"
```

---

## Task 7: Validator wiring — unscored-line authored branch + nonreproducible `authored_capped`

**Files:**
- Modify: `src/science_tool/validate/checks/evidence_lines.py`
- Test: `tests/validate/test_checks_evidence_lines.py` (extend — `check_evidence_unscored_line` lives here)
- Test: `tests/validate/test_checks_belief_sensitivity.py` (extend — `belief.nonreproducible` lives here)

> The two validator suites are **split** by check. Put the unscored-line tests beside the existing unscored-line tests in `tests/validate/test_checks_evidence_lines.py` (harness: module-level `_write(root, rel, body)` writes a `.md` under the temp project, `_ctx(root)` builds the `ValidateContext`). Put the nonreproducible test beside the existing golden tests in `tests/validate/test_checks_belief_sensitivity.py` (harness: `_write_two_support_graph(root)` + `_ctx(root)` + `make_snapshots(...)`).

- [ ] **Step 1: Write the failing unscored-line tests**

Append to `tests/validate/test_checks_evidence_lines.py`, mirroring the existing `test_unscored_line_*` tests (which use `_write(...)` + `_ctx(...)`):

```python
def test_unscored_line_skips_authored_assertion_with_valid_confidence(tmp_path: Path):
    from science_tool.validate.checks.evidence_lines import check_evidence_unscored_line

    # An authored assertion (expert_judgment) with valid confidence and NO role/strength is
    # admitted by confidence -> not flagged unscored, not flagged invalid-confidence.
    _write(tmp_path, "entities/evidence-lines/el01.md",
           "---\nstance: supports\ntarget: proposition:p1\n"
           "evidence_type: expert_judgment\nconfidence: 0.8\n---\n")
    rules = {r.rule for r in check_evidence_unscored_line(_ctx(tmp_path))}
    assert "evidence.unscored-line" not in rules
    assert "evidence.authored-confidence-invalid" not in rules


def test_authored_assertion_missing_confidence_warned(tmp_path: Path):
    from science_tool.validate.checks.evidence_lines import check_evidence_unscored_line

    _write(tmp_path, "entities/evidence-lines/el01.md",
           "---\nstance: supports\ntarget: proposition:p1\nevidence_type: expert_judgment\n---\n")
    results = list(check_evidence_unscored_line(_ctx(tmp_path)))
    assert any(r.rule == "evidence.authored-confidence-invalid" for r in results)
    assert all(r.severity is Severity.WARN for r in results)


def test_authored_assertion_out_of_range_confidence_warned(tmp_path: Path):
    from science_tool.validate.checks.evidence_lines import check_evidence_unscored_line

    _write(tmp_path, "entities/evidence-lines/el01.md",
           "---\nstance: supports\ntarget: proposition:p1\n"
           "evidence_type: expert_judgment\nconfidence: 1.4\n---\n")
    rules = {r.rule for r in check_evidence_unscored_line(_ctx(tmp_path))}
    assert "evidence.authored-confidence-invalid" in rules
```

- [ ] **Step 2: Run unscored-line tests to verify they fail**

Run: `rtk proxy uv run --frozen pytest tests/validate/test_checks_evidence_lines.py -k authored -v`
Expected: FAIL — the authored assertion with valid confidence is currently flagged `evidence.unscored-line` (missing role/strength), and the `evidence.authored-confidence-invalid` rule does not exist yet.

- [ ] **Step 3: Add the authored branch to `check_evidence_unscored_line`**

3a. Import `DEFAULT_BELIEF_POLICY` in `src/science_tool/validate/checks/evidence_lines.py`. Add near the other `science_tool.graph` imports (e.g. after the `from science_tool.graph.io import SCHEMA_NS, SCI_NS` line):

```python
from science_tool.graph.belief_policy import DEFAULT_BELIEF_POLICY
```

3b. In `check_evidence_unscored_line`, insert the authored branch immediately after the `stance` guard and before the diagnostic-role / `missing` logic. The current body starts:

```python
    for path, fm in _ev_lines(ctx):
        stance = fm.get("stance")
        if stance not in ("supports", "disputes"):
            continue
        role = fm.get("evidence_role") or ""
```

Insert between the `continue` and the `role = ...` line:

```python
        # Authored assertions (Slice B) are ADMITTED by confidence, not scored by role/strength
        # — exempt them from the unscored-line requirement. Instead, flag a missing or
        # out-of-range confidence, which is the un-gateable authoring error.
        if normalize_evidence_type(fm.get("evidence_type")) == DEFAULT_BELIEF_POLICY.authored_assertion_type:
            conf = fm.get("confidence")
            if not isinstance(conf, (int, float)) or isinstance(conf, bool) or not (0.0 <= conf <= 1.0):
                yield Result(
                    severity=Severity.WARN,
                    path=path,
                    line=None,
                    message=(
                        f"{path.name}: authored assertion (expert_judgment) has missing or "
                        f"out-of-range confidence — set confidence in [0, 1] so it can be scored"
                    ),
                    rule="evidence.authored-confidence-invalid",
                    task=None,
                )
            continue
```

- [ ] **Step 4: Run unscored-line tests to verify they pass**

Run: `rtk proxy uv run --frozen pytest tests/validate/test_checks_evidence_lines.py -k authored -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Add `authored_capped` to the nonreproducible comparison**

In `check_belief_nonreproducible`, the `diffs` computation is:

```python
        diffs = [
            f for f in ("belief_state", "contested", "diagnostic_dispute_count")
            if prior.get(f) != now.get(f)
        ]
        if now["scalar_enabled"]:
            diffs += [f for f in _GOLDEN_SCALAR_FIELDS if prior.get(f) != now.get(f)]
```

Insert, immediately after the first `diffs = [...]` list comprehension:

```python
        # authored_capped compared with an explicit False default so a pre-Slice-B prior row
        # (read_snapshots already normalizes it to False) never produces a spurious
        # belief.nonreproducible error against a current authored_capped == False result.
        if prior.get("authored_capped", False) != now.get("authored_capped", False):
            diffs.append("authored_capped")
```

- [ ] **Step 6: Write + run the legacy-normalization reproducibility test**

Append to `tests/validate/test_checks_belief_sensitivity.py`, mirroring the existing `test_nonreproducible_*` tests (harness: `_write_two_support_graph` + `_ctx` + `make_snapshots`, then write a corrupted/stale JSONL row and assert). This proves a pre-Slice-B row lacking `authored_capped` does NOT trip `belief.nonreproducible`:

```python
def test_nonreproducible_silent_when_authored_capped_absent(tmp_path: Path):
    import json

    from science_tool.graph.belief_snapshot import make_snapshots
    from science_tool.validate.checks.evidence_lines import check_belief_nonreproducible

    _write_two_support_graph(tmp_path)
    ctx = _ctx(tmp_path)
    rows = make_snapshots(tmp_path / "knowledge" / "graph.trig", as_of="2026-05-24")
    snap = tmp_path / "knowledge" / "belief-snapshots.jsonl"
    # Simulate a pre-Slice-B history line: strip authored_capped from the (otherwise correct)
    # row. read_snapshots normalizes it back to False, matching the current empirical result.
    legacy = {k: v for k, v in rows[0].items() if k != "authored_capped"}
    snap.write_text(json.dumps(legacy) + "\n", encoding="utf-8")
    assert list(check_belief_nonreproducible(ctx)) == []
```

Run: `rtk proxy uv run --frozen pytest tests/validate/test_checks_belief_sensitivity.py -v`
Expected: PASS (existing golden tests + the new legacy test).

- [ ] **Step 7: Lint the touched source files**

Run: `rtk proxy uv run --frozen ruff check src/science_tool/graph/belief_weights.py src/science_tool/graph/belief_policy.py src/science_tool/graph/belief.py src/science_tool/graph/bundle_belief.py src/science_tool/graph/belief_snapshot.py src/science_tool/validate/checks/evidence_lines.py`
Expected: PASS (no errors).

- [ ] **Step 8: Commit**

```bash
rtk git add src/science_tool/validate/checks/evidence_lines.py \
  tests/validate/test_checks_evidence_lines.py tests/validate/test_checks_belief_sensitivity.py
rtk git commit -m "feat(belief): validator authored-confidence branch + nonreproducible authored_capped comparison (Slice B t7)"
```

---

## Final verification (after all tasks)

Run the entire belief + evidence + validate regression net:

```bash
rtk proxy uv run --frozen pytest \
  tests/test_belief_weights.py \
  tests/test_belief_policy.py \
  tests/test_belief_policy_aggregate.py \
  tests/test_belief_policy_bundle.py \
  tests/test_belief_policy_persistence.py \
  tests/test_authored_confidence_policy.py \
  tests/test_authored_confidence.py \
  tests/test_belief_aggregate.py \
  tests/test_belief_collect.py \
  tests/test_belief_reduce.py \
  tests/test_belief_refutation.py \
  tests/test_belief_classify.py \
  tests/test_belief_e2e.py \
  tests/test_belief_scalar.py \
  tests/test_belief_snapshot.py \
  tests/test_bundle_belief_rollup.py \
  tests/test_bundle_belief_snapshot.py \
  tests/test_belief_cli.py \
  tests/test_evidence_line_belief_checks.py \
  tests/test_evidence_line_e2e.py \
  tests/test_dataset_evidence_flow_e2e.py \
  tests/validate/test_checks_evidence_lines.py \
  tests/validate/test_checks_belief_sensitivity.py \
  -v
```

Expected: ALL PASS. This is the real regression net — empirical-only belief unchanged, authored confidence now a disciplined input.

Then finish the branch with **superpowers:finishing-a-development-branch**.

---

## Plan Self-Review

**Spec coverage:**
- Core rule (recognition by type; range-validated gate) → Tasks 2, 3, 4.
- Confidence is a gate not a dial → Task 3 (`_authored_assertion_counts`), Task 4 (ceiling does not read the value).
- Authored-only ceiling → Task 4.
- Refutation symmetry → Task 4 (`is_qualifying_direct_test` exclusion; authored-dispute-not-decisive test).
- Pipeline ordering (gate before `reduce_units`) → Task 4 (`test_gate_failing_authored_dispute_has_zero_downstream_effect`).
- `MAGNITUDE_NAMES` + reconciliation → Task 1; policy `__post_init__` validation → Task 2.
- `EvidenceUnit.confidence` positional stability → Task 3 (`test_positional_constructor_still_builds`).
- Bundle `authored_capped` OR-rollup → Task 5.
- Snapshot persistence both branches + legacy default → Task 6.
- Validator unscored-line authored branch + nonreproducible `authored_capped` (default-False) → Task 7.
- Behavior-neutral for empirical evidence → Steps 5/7 regression runs throughout + final net.

**Placeholder scan:** every code step shows complete, runnable code against the verified harnesses — `_write`/`_ctx` in `tests/validate/test_checks_evidence_lines.py` (unscored-line), `_write_two_support_graph`/`_ctx`/`make_snapshots` in `tests/validate/test_checks_belief_sensitivity.py` (nonreproducible), `_graphs()` in `tests/test_belief_snapshot.py` (single-claim row), and the mechanism-bundle builder in `tests/test_bundle_belief_snapshot.py` (bundle row). The only delegated detail is reusing/inlining the existing bundle-graph construction in Task 6 Step 1b (the file may or may not expose a named helper); the assertion is fully specified.

**Validator suites correctly targeted:** `check_evidence_unscored_line` tests → `tests/validate/test_checks_evidence_lines.py`; `belief.nonreproducible` test → `tests/validate/test_checks_belief_sensitivity.py`; both included in the final regression net.

**Type consistency:** `is_authored_assertion` / `_authored_assertion_counts` signatures `(u, *, policy)` are identical across Tasks 3, 4, 7. `authored_capped: bool` and `excluded_authored_confidence: list[EvidenceUnit]` names match across `BeliefResult` (Task 4), bundle rollup (Task 5), snapshot rows (Task 6), and validator (Task 7). `authored_only_ceiling` is a magnitude **string** everywhere; `BeliefMagnitude(policy.authored_only_ceiling)` is the only string→enum conversion (Task 4). Rule string `evidence.authored-confidence-invalid` matches between Task 7 implementation and tests.

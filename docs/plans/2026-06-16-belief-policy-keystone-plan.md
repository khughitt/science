# BeliefPolicy Keystone Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract today's implicit belief-aggregation knobs into one explicit, versioned, deeply-immutable `BeliefPolicy`; thread it through `aggregate_belief`; stamp every `BeliefResult` and persisted belief record with the policy identity; and refuse to combine results computed under different policies — all behavior-neutral via a single built-in default.

**Architecture:** A new `graph/belief_policy.py` holds `BeliefPolicy` (frozen dataclass, container fields deep-frozen via `MappingProxyType`/`frozenset`) and `DEFAULT_BELIEF_POLICY`, built **from** the existing `belief_weights.py` constants (one source of truth). `aggregate_belief` and its ordinal helpers gain a keyword-only `policy` parameter defaulting to `DEFAULT_BELIEF_POLICY`, so all ~9 external call sites are untouched. `BeliefResult`/`BundleBeliefResult` carry `policy_id`/`policy_version`; the weakest-link rollup rejects mixed identities; snapshot JSONL and patch RDF record the identity.

**Tech Stack:** Python 3.13, rdflib, dataclasses, `types.MappingProxyType`; pytest; ruff.

---

## Conventions (read first)

- **Canonical working directory for every command:** `~/d/science/.worktrees/belief-semantics/science` (the uv workspace member dir — it holds `pyproject.toml`). There is **no** root `pyproject.toml`. `~/d/science` is a symlink to the Dropbox checkout; the worktree branch is `feat/belief-semantics`.
- All file paths below are **relative to that `science/` directory** (e.g. `src/science_tool/graph/belief.py`, `tests/test_belief_policy.py`).
- **Tests/lint** run through the rtk proxy: `rtk proxy uv run --frozen pytest …` and `rtk proxy uv run --frozen ruff …`. (`rtk` has no `uv`/`pytest`/`ruff` subcommand of its own; `rtk proxy` passes the raw command through.)
- **Git** is agent-facing via `rtk git …`. Commit only as the steps say. Do **not** push (this is a Dropbox-synced local-only main; merge happens later via finishing-a-development-branch). Do **not** add `Co-Authored-By` trailers.
- `science_model` must never import `science_tool`. (This slice only touches `science_tool`, plus reads `science_model.reasoning.CompositionRule` which already exists.)
- **Behavior-neutral contract:** after every task the belief regression net stays green:
  ```
  rtk proxy uv run --frozen pytest \
    tests/test_belief_aggregate.py tests/test_belief_reduce.py tests/test_belief_refutation.py \
    tests/test_belief_collect.py tests/test_belief_scalar.py tests/test_belief_scalar_quant_result.py \
    tests/test_belief_e2e.py tests/test_bundle_belief_rollup.py tests/test_bundle_belief_snapshot.py \
    tests/test_belief_snapshot.py tests/test_belief_cli.py tests/test_evidence_line_belief_checks.py \
    tests/test_epistemic_edges_e2e.py tests/test_model_patch.py \
    tests/validate/test_checks_belief_sensitivity.py -q
  ```
  This is referred to below as **the regression net**.

---

## File structure

| File | Responsibility | Task |
|---|---|---|
| `src/science_tool/graph/belief_policy.py` | **New.** `BeliefPolicy` + `DEFAULT_BELIEF_POLICY`. Imports only `belief_weights` (one-way; no cycle). | 1 |
| `src/science_tool/graph/belief.py` | Thread `policy` through `aggregate_belief` + ordinal helpers; stamp `BeliefResult`. | 2 |
| `src/science_tool/graph/bundle_belief.py` | `MixedBeliefPolicyError`; comparability guard + policy stamp on `BundleBeliefResult`. | 3 |
| `src/science_tool/graph/belief_snapshot.py` | Add `policy_id`/`policy_version` to rows **and to `_key`**; normalize pre-policy rows on read. | 4 |
| `src/science_tool/model/patch.py` | Emit `sci:beliefPolicyId`/`beliefPolicyVersion` (unconditional default stamp). | 4 |
| `tests/test_belief_cli.py` | Update canned `make_snapshots` fixture to carry policy fields. | 4 |
| `src/science_tool/validate/checks/evidence_lines.py` | Make `belief.nonreproducible` matcher policy-aware. | 5 |
| `tests/test_belief_policy.py` | Policy object: identity, default values, deep immutability. | 1 |
| `tests/test_belief_policy_aggregate.py` | Stamping, explicit==implicit default, seam proof. | 2 |
| `tests/test_belief_policy_bundle.py` | Rollup stamp + mixed-policy rejection. | 3 |
| `tests/test_belief_policy_persistence.py` | Snapshot row+`_key`; pre-policy normalization; patch RDF identity. | 4 |
| `tests/validate/test_checks_belief_sensitivity.py` | Policy identity gates reproducibility comparison. | 5 |

---

## Task 1: `BeliefPolicy` object + `DEFAULT_BELIEF_POLICY`

**Files:**
- Create: `src/science_tool/graph/belief_policy.py`
- Test: `tests/test_belief_policy.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_belief_policy.py`:

```python
from types import MappingProxyType

import pytest

from science_tool.graph.belief_policy import BeliefPolicy, DEFAULT_BELIEF_POLICY
from science_tool.graph.belief_weights import (
    CURATION_STEP_PENALTY, DIAGNOSTIC_ROLES, EVIDENCE_ROLE_RANK,
    EVIDENCE_TYPE_RANK, GATED_PROXY, STRENGTH_RANK,
)


def test_default_policy_identity():
    assert DEFAULT_BELIEF_POLICY.policy_id == "core-default"
    assert DEFAULT_BELIEF_POLICY.version == "1"


def test_default_policy_values_match_belief_weights():
    p = DEFAULT_BELIEF_POLICY
    assert dict(p.evidence_type_rank) == EVIDENCE_TYPE_RANK
    assert dict(p.evidence_role_rank) == EVIDENCE_ROLE_RANK
    assert dict(p.strength_rank) == STRENGTH_RANK
    assert p.curation_step_penalty == CURATION_STEP_PENALTY
    assert p.gated_proxy == GATED_PROXY
    assert p.diagnostic_roles == DIAGNOSTIC_ROLES
    assert p.well_supported_min_clean_support == 2
    assert p.well_supported_requires_direct_test is True


def test_rank_tables_are_read_only_mappings():
    assert isinstance(DEFAULT_BELIEF_POLICY.evidence_type_rank, MappingProxyType)
    with pytest.raises(TypeError):
        DEFAULT_BELIEF_POLICY.evidence_type_rank["empirical_data"] = 99


def test_token_sets_are_frozen():
    assert isinstance(DEFAULT_BELIEF_POLICY.gated_proxy, frozenset)
    assert isinstance(DEFAULT_BELIEF_POLICY.diagnostic_roles, frozenset)


def test_constructor_normalizes_mutable_containers():
    p = BeliefPolicy(
        policy_id="x", version="1",
        evidence_type_rank={"a": 1}, evidence_role_rank={}, strength_rank={},
        curation_step_penalty=1, gated_proxy={"indirect"}, diagnostic_roles=set(),
        direct_test_role="direct_test", independent_token="independent",
        shared_source_token="shared-source", circular_token="circular",
        scope_whole_claim="whole_claim", decisive_strength="strong",
        well_supported_min_clean_support=2, well_supported_requires_direct_test=True,
    )
    assert isinstance(p.evidence_type_rank, MappingProxyType)
    assert isinstance(p.gated_proxy, frozenset)
    with pytest.raises(TypeError):
        p.evidence_type_rank["b"] = 2
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `rtk proxy uv run --frozen pytest tests/test_belief_policy.py -q`
Expected: collection/import error — `No module named 'science_tool.graph.belief_policy'`.

- [ ] **Step 3: Create the policy module**

Create `src/science_tool/graph/belief_policy.py`:

```python
"""Explicit, versioned belief policy (patchwork kernel Spec 5, Slice A).

A `BeliefPolicy` bundles the previously-implicit ordinal aggregation knobs — rank
tables, the curation step penalty, the reduction/vocabulary constants, the
magnitude thresholds, and the refutation-cap conditions — into one frozen,
deeply-immutable object with a recorded identity. `DEFAULT_BELIEF_POLICY` is the
single built-in policy and is constructed FROM the `belief_weights` constants, so
there is one source of truth for the values and the default reproduces today's
`aggregate_belief` output exactly.

This module imports only `belief_weights` (which imports nothing internal), so it
sits below `belief.py` in the import graph — there is no cycle.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from .belief_weights import (
    CIRCULAR, CURATION_STEP_PENALTY, DIAGNOSTIC_ROLES, EVIDENCE_ROLE_RANK,
    EVIDENCE_TYPE_RANK, GATED_PROXY, INDEPENDENT, ROLE_DIRECT_TEST,
    SCOPE_WHOLE_CLAIM, SHARED_SOURCE, STRENGTH_RANK,
)


@dataclass(frozen=True)
class BeliefPolicy:
    """An explicit, versioned, deeply-immutable belief-aggregation policy."""

    policy_id: str
    version: str
    # Ordinal scoring knobs (consumed by quality_key).
    evidence_type_rank: Mapping[str, int]
    evidence_role_rank: Mapping[str, int]
    strength_rank: Mapping[str, int]
    curation_step_penalty: int
    # Reduction / vocabulary constants.
    gated_proxy: frozenset[str]
    diagnostic_roles: frozenset[str]
    direct_test_role: str
    independent_token: str
    shared_source_token: str
    circular_token: str
    scope_whole_claim: str
    # Refutation-cap + magnitude-threshold knobs.
    decisive_strength: str
    well_supported_min_clean_support: int
    well_supported_requires_direct_test: bool

    def __post_init__(self) -> None:
        # A frozen dataclass does not stop a caller mutating a dict/set it was handed.
        # Deep-freeze the container fields into read-only Mappings and frozensets.
        object.__setattr__(self, "evidence_type_rank", MappingProxyType(dict(self.evidence_type_rank)))
        object.__setattr__(self, "evidence_role_rank", MappingProxyType(dict(self.evidence_role_rank)))
        object.__setattr__(self, "strength_rank", MappingProxyType(dict(self.strength_rank)))
        object.__setattr__(self, "gated_proxy", frozenset(self.gated_proxy))
        object.__setattr__(self, "diagnostic_roles", frozenset(self.diagnostic_roles))


DEFAULT_BELIEF_POLICY = BeliefPolicy(
    policy_id="core-default",
    version="1",
    evidence_type_rank=EVIDENCE_TYPE_RANK,
    evidence_role_rank=EVIDENCE_ROLE_RANK,
    strength_rank=STRENGTH_RANK,
    curation_step_penalty=CURATION_STEP_PENALTY,
    gated_proxy=GATED_PROXY,
    diagnostic_roles=DIAGNOSTIC_ROLES,
    direct_test_role=ROLE_DIRECT_TEST,
    independent_token=INDEPENDENT,
    shared_source_token=SHARED_SOURCE,
    circular_token=CIRCULAR,
    scope_whole_claim=SCOPE_WHOLE_CLAIM,
    decisive_strength="strong",
    well_supported_min_clean_support=2,
    well_supported_requires_direct_test=True,
)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `rtk proxy uv run --frozen pytest tests/test_belief_policy.py -q`
Expected: 5 passed.

- [ ] **Step 5: Lint**

Run: `rtk proxy uv run --frozen ruff check src/science_tool/graph/belief_policy.py tests/test_belief_policy.py`
Expected: `All checks passed!`

- [ ] **Step 6: Commit**

```bash
rtk git add src/science_tool/graph/belief_policy.py tests/test_belief_policy.py
rtk git commit -m "feat(belief): add explicit versioned BeliefPolicy + DEFAULT_BELIEF_POLICY (Spec 5 Slice A)"
```

---

## Task 2: Thread `policy` through `aggregate_belief`; stamp `BeliefResult`

**Files:**
- Modify: `src/science_tool/graph/belief.py` (imports; `quality_key`, `reduce_units`, `is_diagnostic`, `is_proxy_gated`, `is_qualifying_direct_test`, `is_decisive_refutation`, `BeliefResult`, `aggregate_belief`)
- Test: `tests/test_belief_policy_aggregate.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_belief_policy_aggregate.py`:

```python
from dataclasses import replace

from science_tool.graph.belief import BeliefMagnitude, EvidenceUnit, aggregate_belief
from science_tool.graph.belief_policy import DEFAULT_BELIEF_POLICY


def _u(**kw) -> EvidenceUnit:
    base = dict(
        line_uri="a", stance="supports", strength="strong", independence="independent",
        independence_group="g1", evidence_role="direct_test", evidence_type="empirical_data",
        dispute_scope=None, proxy_directness=None, has_measurement_model=False,
        source=None, observability_keys=(), is_reference_dataset=False,
    )
    base.update(kw)
    return EvidenceUnit(**base)


def _two_clean_direct_tests() -> list[EvidenceUnit]:
    return [_u(line_uri="a", independence_group="g1"), _u(line_uri="b", independence_group="g2")]


def test_result_is_stamped_with_default_policy():
    r = aggregate_belief([_u()])
    assert r.policy_id == "core-default"
    assert r.policy_version == "1"


def test_explicit_default_equals_implicit_default():
    units = _two_clean_direct_tests()
    assert aggregate_belief(units) == aggregate_belief(units, policy=DEFAULT_BELIEF_POLICY)


def test_default_two_clean_direct_tests_is_well_supported():
    assert aggregate_belief(_two_clean_direct_tests()).magnitude == BeliefMagnitude.WELL_SUPPORTED


def test_seam_proof_raising_min_clean_support_demotes_to_supported():
    # A stricter policy that demands 3 clean supports must demote the SAME unit set
    # from well_supported to supported — proving the knob is actually read, not decorative.
    strict = replace(DEFAULT_BELIEF_POLICY, policy_id="strict", version="1",
                     well_supported_min_clean_support=3)
    units = _two_clean_direct_tests()
    assert aggregate_belief(units, policy=strict).magnitude == BeliefMagnitude.SUPPORTED
    assert aggregate_belief(units, policy=strict).policy_id == "strict"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `rtk proxy uv run --frozen pytest tests/test_belief_policy_aggregate.py -q`
Expected: FAIL — `TypeError: aggregate_belief() got an unexpected keyword argument 'policy'` (and `BeliefResult` has no `policy_id`).

- [ ] **Step 3: Update the `belief.py` imports**

In `src/science_tool/graph/belief.py`, replace the `belief_weights` import block (lines 11-15) — most of those constants now live on the policy; only the four still used by the unchanged `_with_derived_commitment` path and `normalize_evidence_type` remain — and add the policy import:

```python
from .belief_policy import BeliefPolicy, DEFAULT_BELIEF_POLICY
from .belief_weights import CIRCULAR, INDEPENDENT, SHARED_SOURCE, normalize_evidence_type
```

- [ ] **Step 4: Thread `policy` through the ordinal helpers**

Replace `quality_key` (currently lines 149-158):

```python
def quality_key(u: EvidenceUnit, *, policy: BeliefPolicy = DEFAULT_BELIEF_POLICY) -> tuple[int, int, int, int]:
    # A-D4: the curation discount also routes through winner-selection. It is the LAST
    # (least-significant) component, so a reference-backed unit loses only to an otherwise
    # equal (type/role/strength) non-reference unit — it never crosses those axes.
    return (
        policy.evidence_type_rank.get(normalize_evidence_type(u.evidence_type), 0),
        policy.evidence_role_rank.get(u.evidence_role or "", 0),
        policy.strength_rank.get(u.strength or "", 0),
        -policy.curation_step_penalty if u.is_reference_dataset else 0,
    )
```

Replace the `reduce_units` signature line and the three constant reads inside it (currently lines 170, 178, 181, 191). The signature becomes:

```python
def reduce_units(units: list[EvidenceUnit], *, policy: BeliefPolicy = DEFAULT_BELIEF_POLICY) -> ReducedUnits:
```

Inside the loop, change the flagged/circular checks and the winner comparison to read from the policy:

```python
        if u.independence in (policy.shared_source_token, policy.circular_token) and not u.independence_group:
            flagged_ungrouped.append(u)                    # "collapse to what?" undefined (QA #2b)
            continue
        if u.independence == policy.circular_token:
            excluded_circular.append(u)
            continue
```

and:

```python
        if key not in winners:
            winners[key] = u
        elif quality_key(u, policy=policy) > quality_key(winners[key], policy=policy):
            collapsed.append(winners[key])
            winners[key] = u
        else:
            collapsed.append(u)
```

Replace `is_diagnostic`, `is_proxy_gated`, `is_qualifying_direct_test`, `is_decisive_refutation` (currently lines 207-235):

```python
def is_diagnostic(u: EvidenceUnit, *, policy: BeliefPolicy = DEFAULT_BELIEF_POLICY) -> bool:
    """negative_control / model_criticism: separate ledger rows, never FOR/AGAINST mass."""
    return (u.evidence_role or "") in policy.diagnostic_roles


def is_proxy_gated(u: EvidenceUnit, *, policy: BeliefPolicy = DEFAULT_BELIEF_POLICY) -> bool:
    """Rule 5: indirect/derived proxy with no measurement_model cannot contribute at full weight."""
    return (u.proxy_directness or "") in policy.gated_proxy and not u.has_measurement_model


def is_qualifying_direct_test(u: EvidenceUnit, *, policy: BeliefPolicy = DEFAULT_BELIEF_POLICY) -> bool:
    return u.evidence_role == policy.direct_test_role and not is_proxy_gated(u, policy=policy)


def is_decisive_refutation(u: EvidenceUnit, *, policy: BeliefPolicy = DEFAULT_BELIEF_POLICY) -> bool:
    """Rule 3: ONLY an independent strong direct_test whole_claim dispute caps belief.

    whole_claim is the default when scope is unset; model_criticism and scoped disputes
    (generalization/mechanism/boundary) set `contested` but never eliminate. The proxy gate
    (rule 5) applies symmetrically: an ungated indirect/derived proxy direct-test cannot be
    decisive either (`is_qualifying_direct_test` already encodes role + proxy gate).
    """
    return (
        u.stance == "disputes"
        and u.independence == policy.independent_token
        and u.strength == policy.decisive_strength
        and is_qualifying_direct_test(u, policy=policy)
        and (u.dispute_scope or policy.scope_whole_claim) == policy.scope_whole_claim
    )
```

- [ ] **Step 5: Add policy fields to `BeliefResult`**

In `BeliefResult` (currently lines 253-266), append two defaulted fields after `flagged_ungrouped` and before `display`:

```python
    flagged_ungrouped: list[EvidenceUnit]
    policy_id: str = DEFAULT_BELIEF_POLICY.policy_id
    policy_version: str = DEFAULT_BELIEF_POLICY.version

    def display(self) -> str:
        return f"{self.magnitude.value} (contested)" if self.contested else self.magnitude.value
```

(Defaults cover direct constructors — e.g. `tests/test_bundle_belief_rollup.py:21` — so they need no edit and are stamped with the default identity.)

- [ ] **Step 6: Thread `policy` through `aggregate_belief` and stamp the result**

Replace `aggregate_belief` (currently lines 269-314):

```python
def aggregate_belief(units: list[EvidenceUnit], *, policy: BeliefPolicy = DEFAULT_BELIEF_POLICY) -> BeliefResult:
    reduced = reduce_units(units, policy=policy)
    cg = reduced.contested_groups

    support = [u for u in reduced.kept if u.stance == "supports" and not is_diagnostic(u, policy=policy)]
    dispute = [u for u in reduced.kept if u.stance == "disputes" and not is_diagnostic(u, policy=policy)]
    diagnostics = [u for u in reduced.kept if is_diagnostic(u, policy=policy)]

    n_support = len(support)
    # A support unit in a contested group is not clean corroboration (stance-aware-collapse
    # decision): well_supported needs >=N *clean* units, one of which is a qualifying direct test.
    clean_support = [u for u in support if u.independence_group not in cg]
    clean_direct_test = any(is_qualifying_direct_test(u, policy=policy) for u in clean_support)
    decisive = any(is_decisive_refutation(u, policy=policy) for u in dispute)

    if n_support == 0:
        magnitude = BeliefMagnitude.SPECULATIVE
    elif n_support == 1:
        magnitude = BeliefMagnitude.FRAGILE
    elif (not policy.well_supported_requires_direct_test or clean_direct_test) and len(
        clean_support
    ) >= policy.well_supported_min_clean_support:
        magnitude = BeliefMagnitude.WELL_SUPPORTED
    else:
        magnitude = BeliefMagnitude.SUPPORTED

    capped = False
    if decisive and _MAG_ORDER.index(magnitude) > _MAG_ORDER.index(BeliefMagnitude.FRAGILE):
        magnitude = BeliefMagnitude.FRAGILE
        capped = True

    contested = (
        bool(dispute)
        or any(u.stance == "disputes" for u in diagnostics)
        or bool(cg)
    )

    return BeliefResult(
        magnitude=magnitude,
        contested=contested,
        capped_by_refutation=capped,
        support_units=support,
        dispute_units=dispute,
        diagnostics=diagnostics,
        contested_groups=cg,
        excluded=reduced.excluded_circular,
        flagged_ungrouped=reduced.flagged_ungrouped,
        policy_id=policy.policy_id,
        policy_version=policy.version,
    )
```

- [ ] **Step 7: Run the new tests, then the regression net**

Run: `rtk proxy uv run --frozen pytest tests/test_belief_policy_aggregate.py -q`
Expected: 4 passed.

Run the regression net (the multi-file command in Conventions).
Expected: all passed (behavior-neutral — the default reproduces prior output).

- [ ] **Step 8: Lint**

Run: `rtk proxy uv run --frozen ruff check src/science_tool/graph/belief.py tests/test_belief_policy_aggregate.py`
Expected: `All checks passed!` (the trimmed `belief_weights` import removes the now-unused names; if ruff reports any remaining unused import, delete that name).

- [ ] **Step 9: Commit**

```bash
rtk git add src/science_tool/graph/belief.py tests/test_belief_policy_aggregate.py
rtk git commit -m "feat(belief): thread BeliefPolicy through aggregate_belief and stamp BeliefResult (behavior-neutral)"
```

---

## Task 3: Bundle comparability guard + policy stamp on `BundleBeliefResult`

**Files:**
- Modify: `src/science_tool/graph/bundle_belief.py` (`BundleBeliefResult` fields; `MixedBeliefPolicyError`; `roll_up_weakest_link`)
- Test: `tests/test_belief_policy_bundle.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_belief_policy_bundle.py`:

```python
import pytest

from science_model.reasoning import CompositionRule
from science_tool.graph.belief import BeliefMagnitude, BeliefResult
from science_tool.graph.bundle_belief import (
    MemberBelief, MixedBeliefPolicyError, member_rank_key, roll_up_weakest_link,
)


def _result(mag, *, policy_id="core-default", policy_version="1") -> BeliefResult:
    return BeliefResult(
        magnitude=mag, contested=False, capped_by_refutation=False,
        support_units=[], dispute_units=[], diagnostics=[],
        contested_groups=set(), excluded=[], flagged_ungrouped=[],
        policy_id=policy_id, policy_version=policy_version,
    )


def _member(uri, result) -> MemberBelief:
    return MemberBelief(member_uri=uri, belief=result, scalar=None,
                        rank_key=member_rank_key(result, None, uri))


def test_rollup_stamps_shared_policy_identity():
    members = [_member("p:a", _result(BeliefMagnitude.SUPPORTED)),
               _member("p:b", _result(BeliefMagnitude.FRAGILE))]
    bundle = roll_up_weakest_link(members, rule=CompositionRule.CONJUNCTIVE)
    assert bundle.policy_id == "core-default"
    assert bundle.policy_version == "1"
    assert bundle.magnitude == BeliefMagnitude.FRAGILE  # weakest-link semantics unchanged


def test_rollup_rejects_mixed_policy_identities():
    members = [_member("p:a", _result(BeliefMagnitude.SUPPORTED, policy_id="core-default")),
               _member("p:b", _result(BeliefMagnitude.FRAGILE, policy_id="strict"))]
    with pytest.raises(MixedBeliefPolicyError):
        roll_up_weakest_link(members, rule=CompositionRule.CONJUNCTIVE)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `rtk proxy uv run --frozen pytest tests/test_belief_policy_bundle.py -q`
Expected: FAIL — `ImportError: cannot import name 'MixedBeliefPolicyError'`.

- [ ] **Step 3: Add the two policy fields to `BundleBeliefResult`**

In `src/science_tool/graph/bundle_belief.py`, append to the `BundleBeliefResult` dataclass (currently ends at line 88 with `unresolved_members`):

```python
    contested_members: list[str]
    unresolved_members: list[str]
    policy_id: str
    policy_version: str
```

- [ ] **Step 4: Define `MixedBeliefPolicyError` and add the guard + stamp**

Add the error class next to `UnresolvedBundleError` (currently lines 128-129):

```python
class MixedBeliefPolicyError(ValueError):
    """Refuse to combine belief results computed under different BeliefPolicy identities."""
```

In `roll_up_weakest_link`, insert the guard at the top of the body (before `ordered = sorted(...)`, currently line 112) and stamp the result. The function body becomes:

```python
    identities = {(m.belief.policy_id, m.belief.policy_version) for m in members}
    if len(identities) > 1:
        raise MixedBeliefPolicyError(
            f"cannot combine belief results computed under different policies: {sorted(identities)}"
        )
    ordered = sorted(members, key=lambda m: m.rank_key)
    bottleneck = ordered[0]
    bundle_magnitude = bottleneck.belief.magnitude
    return BundleBeliefResult(
        composition_rule=rule.value,
        magnitude=bundle_magnitude,
        capped_by_refutation=any(m.belief.capped_by_refutation for m in ordered),
        contested=any(m.belief.contested for m in ordered),
        scalar=bottleneck.scalar,
        member_results=ordered,
        bottleneck_members=[m.member_uri for m in ordered if m.belief.magnitude == bundle_magnitude],
        contested_members=[m.member_uri for m in ordered if m.belief.contested],
        unresolved_members=[m.member_uri for m in ordered if m.belief.magnitude == BeliefMagnitude.SPECULATIVE],
        policy_id=ordered[0].belief.policy_id,
        policy_version=ordered[0].belief.policy_version,
    )
```

- [ ] **Step 5: Run the new tests, then the regression net**

Run: `rtk proxy uv run --frozen pytest tests/test_belief_policy_bundle.py -q`
Expected: 2 passed.

Run the regression net.
Expected: all passed (existing bundle tests build members from default-stamped `BeliefResult`s, so the guard sees one identity and never fires).

- [ ] **Step 6: Lint**

Run: `rtk proxy uv run --frozen ruff check src/science_tool/graph/bundle_belief.py tests/test_belief_policy_bundle.py`
Expected: `All checks passed!`

- [ ] **Step 7: Commit**

```bash
rtk git add src/science_tool/graph/bundle_belief.py tests/test_belief_policy_bundle.py
rtk git commit -m "feat(belief): reject mixed-policy bundle rollups; stamp policy identity on BundleBeliefResult"
```

---

## Task 4: Persist policy identity (snapshot JSONL `_key` + rows; pre-policy normalization; patch RDF)

**Files:**
- Modify: `src/science_tool/graph/belief_snapshot.py` (import; `snapshot_records` both row branches; `read_snapshots` normalization; `_key`)
- Modify: `src/science_tool/model/patch.py` (import + `emit_patch_trig`)
- Modify: `tests/test_belief_cli.py` (canned `make_snapshots` fixture)
- Test: `tests/test_belief_policy_persistence.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_belief_policy_persistence.py`:

```python
from pathlib import Path

from rdflib import Dataset, Literal, RDF, URIRef

from science_tool.graph.belief_policy import DEFAULT_BELIEF_POLICY
from science_tool.graph.belief_snapshot import (
    append_snapshots, read_snapshots, snapshot_records,
)
from science_tool.graph.io import CITO_NS, SCI_NS
from science_tool.graph.store import _graph_uri

PROP = URIRef("https://example.org/prop/p1")
LINE = URIRef("https://example.org/el/yang")


def _graphs():
    ds = Dataset()
    k = ds.graph(_graph_uri("graph/knowledge"))
    p = ds.graph(_graph_uri("graph/provenance"))
    k.add((PROP, RDF.type, SCI_NS.Proposition))
    k.add((LINE, RDF.type, SCI_NS.EvidenceLine))
    k.add((LINE, CITO_NS.supports, PROP))
    p.add((LINE, SCI_NS.evidenceStrength, Literal("strong")))
    p.add((LINE, SCI_NS.evidenceRole, Literal("direct_test")))
    p.add((LINE, SCI_NS.evidenceType, Literal("empirical_data_evidence")))
    return k, p


def test_snapshot_row_carries_policy_identity():
    k, p = _graphs()
    row = snapshot_records(k, p, scalar_enabled=False, as_of="2026-06-16")[0]
    assert row["policy_id"] == "core-default"
    assert row["policy_version"] == "1"


def test_policy_version_bump_is_not_deduped(tmp_path: Path):
    base = {
        "as_of": "2026-06-16", "claim": "c", "input_hashes": ["sha256:x"],
        "config_version": "belief-logodds-v3", "scalar_enabled": False,
        "policy_id": "core-default", "policy_version": "1",
    }
    bumped = {**base, "policy_version": "2"}
    out = tmp_path / "knowledge" / "belief-snapshots.jsonl"
    assert append_snapshots(out, [base]) == 1
    assert append_snapshots(out, [base]) == 0      # idempotent
    assert append_snapshots(out, [bumped]) == 1    # version bump -> distinct _key -> new row
    assert {r["policy_version"] for r in read_snapshots(out)} == {"1", "2"}


def test_read_snapshots_normalizes_pre_policy_rows(tmp_path: Path):
    # A pre-Slice-A artifact row has no policy fields; it was produced by the core-default
    # policy, so read normalizes it to that identity (no KeyError downstream in _key/matcher).
    import json

    out = tmp_path / "knowledge" / "belief-snapshots.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    legacy = {
        "as_of": "2026-05-24", "claim": "prop:p1", "belief_state": "fragile",
        "contested": False, "scalar_enabled": False,
        "input_hashes": ["sha256:abc"], "config_version": "belief-logodds-v3",
    }
    out.write_text(json.dumps(legacy) + "\n", encoding="utf-8")
    row = read_snapshots(out)[0]
    assert row["policy_id"] == "core-default"
    assert row["policy_version"] == "1"
    # And append remains idempotent against the normalized legacy row.
    normalized = {**legacy, "policy_id": "core-default", "policy_version": "1"}
    assert append_snapshots(out, [normalized]) == 0


def test_patch_trig_emits_policy_identity(tmp_path: Path):
    from science_tool.model.patch import PatchEdge, PatchNode, emit_patch_trig

    sci = "http://example.org/science/vocab/"
    patch_iri = URIRef("http://example.org/project/patch/demo")
    focal = PatchNode(URIRef("http://example.org/world/disease/D1"), "Demo", URIRef(sci + "Disease"))
    edge = PatchEdge(
        iri=URIRef("http://example.org/project/patch/demo/assoc/G1"),
        subject=PatchNode(URIRef("http://example.org/world/gene/G1"), "G1", URIRef(sci + "Gene")),
        edge_type=URIRef(sci + "GeneDiseaseAssociation"),
        belief_magnitude="supported",
    )
    out = emit_patch_trig(patch_iri, focal, "L1", [edge], tmp_path / "patch.trig")
    ds = Dataset()
    ds.parse(str(out), format="trig")
    g = ds.graph(patch_iri)
    ids = [str(o) for o in g.objects(edge.iri, URIRef(sci + "beliefPolicyId"))]
    vers = [str(o) for o in g.objects(edge.iri, URIRef(sci + "beliefPolicyVersion"))]
    assert ids == [DEFAULT_BELIEF_POLICY.policy_id]
    assert vers == [DEFAULT_BELIEF_POLICY.version]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `rtk proxy uv run --frozen pytest tests/test_belief_policy_persistence.py -q`
Expected: FAIL — snapshot rows lack `policy_id`; the normalization test sees no defaults; the patch test finds no `beliefPolicyId` objects.

- [ ] **Step 3: Import the default policy into `belief_snapshot.py`**

In `src/science_tool/graph/belief_snapshot.py`, add the import beside the existing belief imports (currently lines 10-15):

```python
from .belief import collect_evidence_units
from .belief_policy import DEFAULT_BELIEF_POLICY
from .belief_scalar import belief_scalar, belief_scalar_enabled
```

- [ ] **Step 4: Stamp policy identity in both snapshot row branches**

Add two keys to the **bundle** row dict (currently the dict ending at line 71 with `"config_version": CONFIG_VERSION,`):

```python
                "input_hashes": input_hashes,
                "config_version": CONFIG_VERSION,
                "policy_id": result.policy_id,
                "policy_version": result.policy_version,
            })
```

and to the **plain proposition** row dict (currently ending at line 96):

```python
            "input_hashes": input_hashes,
            "config_version": CONFIG_VERSION,
            "policy_id": result.policy_id,
            "policy_version": result.policy_version,
        })
```

- [ ] **Step 5: Normalize pre-policy rows on read, then add policy to the dedup `_key`**

Pre-Slice-A `belief-snapshots.jsonl` rows have no policy fields. They were produced by what is now the built-in core-default policy, so stamp that identity explicitly on read — this is the correct semantic, not a silent fallback, and it keeps the new `_key` (and the Task 5 matcher) from raising `KeyError` on real history. Add a normalizer and route `read_snapshots` through it; replace `read_snapshots` and `_key` (currently lines 109-121):

```python
def _key(row: dict):
    return (row["as_of"], row["claim"], tuple(row["input_hashes"]),
            row["config_version"], row["scalar_enabled"],
            row["policy_id"], row["policy_version"])


def _with_policy_defaults(row: dict) -> dict:
    # Pre-policy snapshot rows predate Spec 5 Slice A; they were computed by the
    # core-default policy. Stamp that identity explicitly so dedup and reproducibility
    # checks are policy-aware without rejecting or KeyError-ing on legacy history.
    if "policy_id" not in row:
        row["policy_id"] = DEFAULT_BELIEF_POLICY.policy_id
        row["policy_version"] = DEFAULT_BELIEF_POLICY.version
    return row


def _dump(row: dict) -> str:
    return json.dumps(row, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def read_snapshots(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    return [
        _with_policy_defaults(json.loads(line))
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
```

(Note: `_dump` is unchanged but shown because it sits between `_key` and `read_snapshots`; keep it as-is when replacing the block. Incoming `rows` passed to `append_snapshots` are NOT normalized — they come from `snapshot_records`, which always stamps them. The only un-stamped source is the CLI test's canned fixture, fixed in Step 7.)

- [ ] **Step 6: Emit policy identity in the patch TriG**

In `src/science_tool/model/patch.py`, add the import beside the existing belief imports (currently line 27-29):

```python
from science_tool.graph.belief_policy import DEFAULT_BELIEF_POLICY
```

In `emit_patch_trig`, immediately after the `beliefMagnitude` triple (currently line 141), add the two identity triples. For this default-only slice they are stamped unconditionally — there is a single policy and `belief_magnitude` was computed under it:

```python
        g.add((edge.iri, SCI_NS.beliefMagnitude, Literal(edge.belief_magnitude)))
        g.add((edge.iri, SCI_NS.beliefPolicyId, Literal(DEFAULT_BELIEF_POLICY.policy_id)))
        g.add((edge.iri, SCI_NS.beliefPolicyVersion, Literal(DEFAULT_BELIEF_POLICY.version)))
```

- [ ] **Step 7: Update the CLI test's canned `make_snapshots` fixture**

The new `_key` requires `policy_id`/`policy_version` on every incoming row. `tests/test_belief_cli.py` monkeypatches `make_snapshots` with a canned row that predates these fields, so `append_snapshots` would `KeyError`. Make the fixture mirror real `make_snapshots` output — add the two keys to the `canned` dict (currently lines 14-21, the dict ending with `"input_hashes": ["sha256:abc"], "config_version": "belief-logodds-v3",`):

```python
    canned = [{
        "as_of": "2026-05-24", "claim": "prop:p1", "belief_state": "fragile",
        "contested": False, "diagnostic_dispute_count": 0, "scalar_enabled": False,
        "massed_support_score": None, "massed_dispute_score": None,
        "massed_support_band": None, "massed_dispute_band": None,
        "net_band": None, "net_robust": None,
        "input_hashes": ["sha256:abc"], "config_version": "belief-logodds-v3",
        "policy_id": "core-default", "policy_version": "1",
    }]
```

- [ ] **Step 8: Run the new tests, then the regression net**

Run: `rtk proxy uv run --frozen pytest tests/test_belief_policy_persistence.py tests/test_belief_cli.py -q`
Expected: 4 passed in the persistence file + the CLI test green.

Run the regression net.
Expected: all passed (`test_belief_snapshot.py` / `test_bundle_belief_snapshot.py` still green — new row keys are additive and `_key` gains fields every row now has after normalization; `test_model_patch.py` still green — the new triples are additive; `test_checks_belief_sensitivity.py` still green — its stored rows come from `make_snapshots`, so they carry matching policy fields).

- [ ] **Step 9: Lint**

Run: `rtk proxy uv run --frozen ruff check src/science_tool/graph/belief_snapshot.py src/science_tool/model/patch.py tests/test_belief_policy_persistence.py tests/test_belief_cli.py`
Expected: `All checks passed!`

- [ ] **Step 10: Commit**

```bash
rtk git add src/science_tool/graph/belief_snapshot.py src/science_tool/model/patch.py tests/test_belief_policy_persistence.py tests/test_belief_cli.py
rtk git commit -m "feat(belief): persist policy identity in snapshots (rows + _key), normalize pre-policy rows, stamp patch RDF"
```

---

## Task 5: Make the `belief.nonreproducible` validator policy-aware

The golden reproducibility matcher defines "same inputs" as `claim + input_hashes + config_version + scalar_enabled`. Without policy identity it would compare a stored row from one policy against a recomputed row from another and report a **false** `belief.nonreproducible` ERROR. Add policy identity to the match criteria. (Task 4's `read_snapshots` normalization guarantees stored rows always carry the fields, and `make_snapshots` stamps the recomputed rows.)

**Files:**
- Modify: `src/science_tool/validate/checks/evidence_lines.py` (`check_belief_nonreproducible`)
- Test: `tests/validate/test_checks_belief_sensitivity.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/validate/test_checks_belief_sensitivity.py`:

```python
def test_nonreproducible_silent_when_policy_identity_differs(tmp_path: Path):
    import json

    from science_tool.graph.belief_snapshot import make_snapshots
    from science_tool.validate.checks.evidence_lines import check_belief_nonreproducible

    _write_two_support_graph(tmp_path)
    ctx = _ctx(tmp_path)
    rows = make_snapshots(tmp_path / "knowledge" / "graph.trig", as_of="2026-05-24")
    snap = tmp_path / "knowledge" / "belief-snapshots.jsonl"
    # Same inputs, WRONG belief, but a different policy_version -> not comparable, no error.
    other_policy = rows[0] | {"belief_state": "speculative", "policy_version": "2"}
    snap.write_text(json.dumps(other_policy) + "\n", encoding="utf-8")
    assert list(check_belief_nonreproducible(ctx)) == []


def test_nonreproducible_normalizes_pre_policy_stored_row(tmp_path: Path):
    import json

    from science_tool.graph.belief_snapshot import make_snapshots
    from science_tool.validate.checks.evidence_lines import check_belief_nonreproducible

    _write_two_support_graph(tmp_path)
    ctx = _ctx(tmp_path)
    rows = make_snapshots(tmp_path / "knowledge" / "graph.trig", as_of="2026-05-24")
    snap = tmp_path / "knowledge" / "belief-snapshots.jsonl"
    # A legacy stored row (no policy fields) with corrupted belief. read_snapshots normalizes
    # it to core-default/1 == the recomputed identity, so corruption is still caught.
    legacy = {k: v for k, v in rows[0].items() if k not in ("policy_id", "policy_version")}
    legacy["belief_state"] = "speculative"
    snap.write_text(json.dumps(legacy) + "\n", encoding="utf-8")
    results = list(check_belief_nonreproducible(ctx))
    assert any(r.severity is Severity.ERROR for r in results)
```

- [ ] **Step 2: Run the tests to verify the first one fails**

Run: `rtk proxy uv run --frozen pytest tests/validate/test_checks_belief_sensitivity.py::test_nonreproducible_silent_when_policy_identity_differs -q`
Expected: FAIL — the matcher ignores policy, so the differing-policy row matches and a false ERROR is raised. (`test_nonreproducible_normalizes_pre_policy_stored_row` already passes given Task 4's normalization.)

- [ ] **Step 3: Add policy identity to the matcher**

In `src/science_tool/validate/checks/evidence_lines.py`, in `check_belief_nonreproducible`, extend the `matches` comprehension (currently lines 526-533) with two clauses, and update the docstring/comment to name policy identity:

```python
    matches = [
        r for r in stored
        if r["claim"] == now["claim"]
        and sorted(r["input_hashes"]) == sorted(now["input_hashes"])
        and r["config_version"] == now["config_version"]
        and r["scalar_enabled"] == now["scalar_enabled"]
        and r["policy_id"] == now["policy_id"]
        and r["policy_version"] == now["policy_version"]
    ]
```

Update the function docstring (currently lines 518-519) to:

```python
    """#8 golden: equal inputs (input_hashes + config_version + scalar_enabled + policy identity)
    must reproduce the stored belief. Differing inputs OR a different BeliefPolicy are a
    legitimate change, not flagged."""
```

- [ ] **Step 4: Run the new tests, then the regression net**

Run: `rtk proxy uv run --frozen pytest tests/validate/test_checks_belief_sensitivity.py -q`
Expected: all passed (the existing corruption-detection tests stay green — their stored rows come from `make_snapshots` under the default policy, matching the recomputed default identity).

Run the regression net.
Expected: all passed.

- [ ] **Step 5: Lint**

Run: `rtk proxy uv run --frozen ruff check src/science_tool/validate/checks/evidence_lines.py tests/validate/test_checks_belief_sensitivity.py`
Expected: `All checks passed!`

- [ ] **Step 6: Commit**

```bash
rtk git add src/science_tool/validate/checks/evidence_lines.py tests/validate/test_checks_belief_sensitivity.py
rtk git commit -m "fix(belief): make belief.nonreproducible matcher policy-aware (no cross-policy false errors)"
```

---

## Final verification

- [ ] **Step 1: Full belief regression net**

Run the regression net one final time. Expected: all passed.

- [ ] **Step 2: Targeted full run of touched areas**

Run: `rtk proxy uv run --frozen pytest tests/test_belief_policy.py tests/test_belief_policy_aggregate.py tests/test_belief_policy_bundle.py tests/test_belief_policy_persistence.py tests/validate/test_checks_belief_sensitivity.py -q`
Expected: the new policy tests (5 + 4 + 2 + 4 = 15) plus the full sensitivity suite (existing + 2 new) all pass.

- [ ] **Step 3: Lint the whole change set**

Run: `rtk proxy uv run --frozen ruff check src/science_tool/graph/belief_policy.py src/science_tool/graph/belief.py src/science_tool/graph/bundle_belief.py src/science_tool/graph/belief_snapshot.py src/science_tool/model/patch.py src/science_tool/validate/checks/evidence_lines.py tests/test_belief_policy.py tests/test_belief_policy_aggregate.py tests/test_belief_policy_bundle.py tests/test_belief_policy_persistence.py tests/test_belief_cli.py tests/validate/test_checks_belief_sensitivity.py`
Expected: `All checks passed!`

After all tasks pass, hand off to **superpowers:finishing-a-development-branch** (the 6 pre-existing unrelated `tests/test_codex_skills.py` failures are out of scope and not caused by this slice).

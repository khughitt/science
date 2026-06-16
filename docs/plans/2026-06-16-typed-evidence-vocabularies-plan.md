# Typed Evidence Vocabularies Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Collapse the duplicated evidence vocabularies onto one typed SSOT — the model owns the vocabulary (`EvidenceType` enum + the existing `EvidenceRole`/`EvidenceStrength`), `EvidenceLineEntity.evidence_type` becomes typed and enforced at parse, and the tool's ordinal ranks reconcile against the enums via a build gate — without changing belief scoring.

**Architecture:** Add `EvidenceType` (6 members incl. valid-but-unranked `negative_result`) and a `canonical_evidence_type_token` suffix-normalizer to `science_model.reasoning`. Type `EvidenceLineEntity.evidence_type` with a `field_validator(mode="before")` that strips the `_evidence` suffix (both authored spellings accepted, canonicalized; unknown raises). `belief_weights` imports the enums, re-keys its rank dicts off enum members, sources its role constants from the enum, adds `UNRANKED_EVIDENCE_TYPES`, delegates suffix-normalization to the model, and enforces a reconciliation gate. Six consumers that compared the suffixed literal directly are made canonical-safe; one taxonomy doc paragraph is reconciled.

**Tech Stack:** Python 3.12/3.13, Pydantic v2 (`StrEnum` model enums, `field_validator`), `rdflib`, `click`, pytest. Model lives in `model/src/science_model/`; belief/validate/CLI in `src/science_tool/`.

---

## Conventions (read once before starting)

- **Canonical working directory:** all commands run from the **`science/` member dir** inside the execution worktree: `~/d/science/.worktrees/typed-evidence-vocabularies/science` (absolute: `/mnt/ssd/Dropbox/science/.worktrees/typed-evidence-vocabularies/science`). Prefix every bash command with `cd` to that dir. Before any commit, run `rtk git rev-parse --abbrev-ref HEAD` and confirm it prints `typed-evidence-vocabularies` (NOT `main`).
- **Tests / lint:** `rtk proxy uv run --frozen pytest <args>` and `rtk proxy uv run --frozen ruff check <path>`. (`rtk` has no `uv`/`pytest`/`ruff` subcommand; `rtk proxy` passes the raw command through.) Model tests live under `model/tests/` and are discoverable from the `science/` dir.
- **Git:** `rtk git add ...` / `rtk git commit ...`. **No `Co-Authored-By` trailers.**
- **`science_model` must NEVER import `science_tool`.** This slice adds code to `science_model` (`reasoning.py`, `entities.py`) that depends on nothing in `science_tool`. The tool→model direction (`belief_weights` importing `reasoning`) is allowed and is how the reconciliation works.
- **Lint hygiene:** only import what you use (avoid F401). Run ruff on touched files before each commit.
- **Design reference:** `docs/plans/2026-06-16-typed-evidence-vocabularies-design.md`. Builds on `docs/plans/2026-06-16-authored-confidence-design.md` (Slice B) and `docs/plans/2026-06-16-belief-policy-keystone-design.md` (Slice A).

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `model/src/science_model/reasoning.py` | Reasoning vocab enums | **Modify**: add `EvidenceType` + `canonical_evidence_type_token` |
| `model/src/science_model/entities.py` | Typed entities | **Modify**: type `EvidenceLineEntity.evidence_type` + suffix validator |
| `src/science_tool/graph/belief_weights.py` | Ordinal ranks + token constants | **Modify**: import enums; re-key ranks; source role constants; `UNRANKED_EVIDENCE_TYPES`; delegate normalize; reconciliation gate |
| `src/science_tool/validate/checks/evidence_lines.py` | Evidence-line validators | **Modify**: normalize before the dataset-usage empirical comparison |
| `src/science_tool/graph/store/summary.py` | Claim summaries / dashboards | **Modify**: normalize before `has_empirical_data` membership |
| `src/science_tool/dag/workbench.py` | Workbench inline evidence | **Modify**: type `EvidenceStub.evidence_type` + validator; canonical staging comparison |
| `src/science_tool/cli.py` | CLI ingress | **Modify**: wire `--evidence-type` to `click.Choice(EVIDENCE_TYPES)` |
| `docs/proposition-and-evidence-model.md` | User-facing taxonomy | **Modify**: reconcile the `negative_result` paragraph |
| `model/tests/test_evidence_type.py` | EvidenceType + normalizer tests | **Create** |
| `model/tests/test_evidence_line_entity.py` | Entity field tests | **Modify**: typed `evidence_type` cases |
| `tests/test_evidence_vocab_reconciliation.py` | Rank↔enum reconciliation | **Create** |
| `tests/validate/test_checks_evidence_lines.py` | dataset-usage check tests | **Modify**: both-spelling cases |
| `tests/test_store_summary.py` (or existing summary test) | `has_empirical_data` tests | **Modify**: both-spelling cases |
| `tests/test_workbench_schema.py` | Workbench stub schema | **Modify**: fix invalid fixture + add rejection test |
| `tests/test_cli_*.py` (evidence-type ingress) | CLI choice gate | **Modify/Create**: reject out-of-vocab |

Tasks are ordered by dependency: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8.

---

## Task 1: `EvidenceType` enum + `canonical_evidence_type_token` (model)

**Files:**
- Modify: `model/src/science_model/reasoning.py`
- Test: `model/tests/test_evidence_type.py` (create)

- [ ] **Step 1: Write the failing test**

Create `model/tests/test_evidence_type.py`:

```python
"""Tests for EvidenceType vocabulary + suffix normalization."""
from __future__ import annotations

import pytest

from science_model.reasoning import EvidenceType, canonical_evidence_type_token


def test_evidence_type_members():
    assert {m.value for m in EvidenceType} == {
        "empirical_data", "benchmark", "simulation",
        "literature", "expert_judgment", "negative_result",
    }


@pytest.mark.parametrize("raw,expected", [
    ("empirical_data_evidence", "empirical_data"),
    ("empirical_data", "empirical_data"),
    ("simulation_evidence", "simulation"),
    ("expert_judgment", "expert_judgment"),        # no suffix -> unchanged
    ("expert_judgment_evidence", "expert_judgment"),
    ("negative_result", "negative_result"),
    ("differential_expression", "differential_expression"),  # unknown token passes through unchanged
])
def test_canonical_token_strips_suffix(raw, expected):
    assert canonical_evidence_type_token(raw) == expected


def test_canonical_token_none_passthrough():
    assert canonical_evidence_type_token(None) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `rtk proxy uv run --frozen pytest model/tests/test_evidence_type.py -v`
Expected: FAIL — `ImportError: cannot import name 'EvidenceType'` (and `canonical_evidence_type_token`).

- [ ] **Step 3: Add the enum + normalizer**

In `model/src/science_model/reasoning.py`, add the enum immediately after the `EvidenceStrength` class (the block ending `WEAK = "weak"`):

```python
class EvidenceType(StrEnum):
    """Category of evidence backing an evidence line (normalized token form).

    Values are the canonical NORMALIZED tokens (no ``_evidence`` suffix). The authored
    suffix variant (e.g. ``empirical_data_evidence``) is accepted and stripped by
    ``canonical_evidence_type_token``. ``negative_result`` is a valid-but-unranked member
    kept for compatibility with cli.py's authored vocabulary (see the belief_weights
    reconciliation gate); a future semantics slice may re-model it.
    """

    EMPIRICAL_DATA = "empirical_data"
    BENCHMARK = "benchmark"
    SIMULATION = "simulation"
    LITERATURE = "literature"
    EXPERT_JUDGMENT = "expert_judgment"
    NEGATIVE_RESULT = "negative_result"
```

Then add the normalizer near the bottom of the module (module-level function, after the enum/class definitions):

```python
_EVIDENCE_TYPE_SUFFIX = "_evidence"


def canonical_evidence_type_token(value: str | None) -> str | None:
    """Strip the authored ``_evidence`` suffix to the canonical EvidenceType token.

    Pure string→string (does NOT validate membership): ``"x_evidence"`` → ``"x"``,
    ``None`` → ``None``, an already-canonical or unknown token → unchanged. Membership
    enforcement happens where the result is coerced to ``EvidenceType`` (the model
    validator raises on unknown); graph-literal readers in the tool degrade unknowns to
    rank 0 instead.
    """
    if value is None:
        return None
    if value.endswith(_EVIDENCE_TYPE_SUFFIX):
        return value[: -len(_EVIDENCE_TYPE_SUFFIX)]
    return value
```

- [ ] **Step 4: Run test to verify it passes**

Run: `rtk proxy uv run --frozen pytest model/tests/test_evidence_type.py -v`
Expected: PASS (9 tests).

- [ ] **Step 5: Lint**

Run: `rtk proxy uv run --frozen ruff check model/src/science_model/reasoning.py model/tests/test_evidence_type.py`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
rtk git add model/src/science_model/reasoning.py model/tests/test_evidence_type.py
rtk git commit -m "feat(model): add EvidenceType enum + canonical_evidence_type_token (typed-evidence-vocab t1)"
```

---

## Task 2: Type `EvidenceLineEntity.evidence_type` + canonicalize at parse (model)

**Files:**
- Modify: `model/src/science_model/entities.py`
- Test: `model/tests/test_evidence_line_entity.py`

- [ ] **Step 1: Write the failing test**

Append to `model/tests/test_evidence_line_entity.py` (the file already provides `_minimal_evidence_line()` and imports `ValidationError`, `EvidenceLineEntity`; add the `EvidenceType` import to the existing `from science_model.reasoning import (...)` block):

```python
def test_evidence_type_canonicalizes_suffixed_spelling():
    from science_model.reasoning import EvidenceType
    el = EvidenceLineEntity(**{**_minimal_evidence_line(), "evidence_type": "empirical_data_evidence"})
    assert el.evidence_type is EvidenceType.EMPIRICAL_DATA


def test_evidence_type_accepts_normalized_spelling():
    from science_model.reasoning import EvidenceType
    el = EvidenceLineEntity(**{**_minimal_evidence_line(), "evidence_type": "empirical_data"})
    assert el.evidence_type is EvidenceType.EMPIRICAL_DATA


def test_evidence_type_expert_judgment_both_spellings():
    from science_model.reasoning import EvidenceType
    for spelling in ("expert_judgment", "expert_judgment_evidence"):
        el = EvidenceLineEntity(**{**_minimal_evidence_line(), "evidence_type": spelling})
        assert el.evidence_type is EvidenceType.EXPERT_JUDGMENT


def test_evidence_type_negative_result_is_valid():
    from science_model.reasoning import EvidenceType
    el = EvidenceLineEntity(**{**_minimal_evidence_line(), "evidence_type": "negative_result"})
    assert el.evidence_type is EvidenceType.NEGATIVE_RESULT


def test_evidence_type_none_allowed():
    el = EvidenceLineEntity(**_minimal_evidence_line())
    assert el.evidence_type is None


def test_evidence_type_unknown_rejected():
    with pytest.raises(ValidationError):
        EvidenceLineEntity(**{**_minimal_evidence_line(), "evidence_type": "differential_expression"})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `rtk proxy uv run --frozen pytest model/tests/test_evidence_line_entity.py -k evidence_type -v`
Expected: FAIL — `test_evidence_type_canonicalizes_suffixed_spelling` returns the raw string `"empirical_data_evidence"` (field is still `str`), and `test_evidence_type_unknown_rejected` does NOT raise.

- [ ] **Step 3: Type the field + add the validator**

In `model/src/science_model/entities.py`:

3a. Add `EvidenceType` and `canonical_evidence_type_token` to the existing `from science_model.reasoning import (...)` block (alphabetical: `EvidenceType` after `EvidenceStrength`; add `canonical_evidence_type_token` too):

```python
from science_model.reasoning import (
    ClaimLayer,
    CompositionRule,
    DisputeScope,
    EvidenceRole,
    EvidenceStance,
    EvidenceStrength,
    EvidenceType,
    IdentificationStrength,
    IndependenceTag,
    MeasurementModel,
    ProxyDirectness,
    RESERVED_COMPOSITION_RULES,
    RivalModelPacket,
    SupportScope,
    canonical_evidence_type_token,
)
```

3b. Change the field declaration in `EvidenceLineEntity` from:

```python
    evidence_type: str | None = None
```

to:

```python
    evidence_type: EvidenceType | None = None
```

3c. Add a `field_validator` to the `EvidenceLineEntity` class body (place it after the field block, mirroring the `@field_validator(..., mode="before")` + `@classmethod` style already used elsewhere in this file):

```python
    @field_validator("evidence_type", mode="before")
    @classmethod
    def _canonicalize_evidence_type(cls, value: object) -> object:
        # Strip the authored ``_evidence`` suffix so both spellings parse to the same
        # EvidenceType member; an unknown token falls through to enum coercion, which raises.
        if isinstance(value, str):
            return canonical_evidence_type_token(value)
        return value
```

(`field_validator` is already imported at the top of `entities.py`.)

- [ ] **Step 4: Run test to verify it passes**

Run: `rtk proxy uv run --frozen pytest model/tests/test_evidence_line_entity.py -k evidence_type -v`
Expected: PASS (all 6 new cases).

- [ ] **Step 5: Run the full model entity + reasoning suite for no regression**

Run: `rtk proxy uv run --frozen pytest model/tests/test_evidence_line_entity.py model/tests/test_evidence_type.py -v`
Expected: PASS.

- [ ] **Step 6: Lint**

Run: `rtk proxy uv run --frozen ruff check model/src/science_model/entities.py model/tests/test_evidence_line_entity.py`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
rtk git add model/src/science_model/entities.py model/tests/test_evidence_line_entity.py
rtk git commit -m "feat(model): type EvidenceLineEntity.evidence_type as EvidenceType, canonicalize at parse (typed-evidence-vocab t2)"
```

---

## Task 3: `belief_weights` reconciliation (tool)

**Files:**
- Modify: `src/science_tool/graph/belief_weights.py`
- Test: `tests/test_evidence_vocab_reconciliation.py` (create)

The current `belief_weights.py` (verbatim, the relevant parts):

```python
ROLE_DIRECT_TEST = "direct_test"
ROLE_PROXY_SUPPORT = "proxy_support"
ROLE_BACKGROUND = "background_constraint"
ROLE_NEGATIVE_CONTROL = "negative_control"
ROLE_MODEL_CRITICISM = "model_criticism"
...
DIAGNOSTIC_ROLES = frozenset({ROLE_NEGATIVE_CONTROL, ROLE_MODEL_CRITICISM})

_EVIDENCE_SUFFIX = "_evidence"

EVIDENCE_TYPE_RANK = {
    "empirical_data": 4, "benchmark": 3, "simulation": 3, "literature": 2, "expert_judgment": 1,
}
EVIDENCE_ROLE_RANK = {ROLE_DIRECT_TEST: 3, ROLE_PROXY_SUPPORT: 2, ROLE_BACKGROUND: 1}
STRENGTH_RANK = {"strong": 3, "moderate": 2, "weak": 1}
...
def normalize_evidence_type(value: str | None) -> str:
    if not value:
        return ""
    return value[: -len(_EVIDENCE_SUFFIX)] if value.endswith(_EVIDENCE_SUFFIX) else value
```

- [ ] **Step 1: Write the failing test**

Create `tests/test_evidence_vocab_reconciliation.py`:

```python
from science_model.reasoning import EvidenceRole, EvidenceStrength, EvidenceType
from science_tool.graph.belief_weights import (
    DIAGNOSTIC_ROLES,
    EVIDENCE_ROLE_RANK,
    EVIDENCE_TYPE_RANK,
    STRENGTH_RANK,
    UNRANKED_EVIDENCE_TYPES,
    normalize_evidence_type,
)


def test_type_rank_reconciles_with_enum():
    # Every EvidenceType is either ranked or explicitly unranked-by-design; no orphan ranks.
    assert set(EVIDENCE_TYPE_RANK) | UNRANKED_EVIDENCE_TYPES == set(EvidenceType)
    assert set(EVIDENCE_TYPE_RANK).isdisjoint(UNRANKED_EVIDENCE_TYPES)


def test_negative_result_is_unranked():
    assert EvidenceType.NEGATIVE_RESULT in UNRANKED_EVIDENCE_TYPES
    assert EvidenceType.NEGATIVE_RESULT not in EVIDENCE_TYPE_RANK


def test_role_rank_reconciles_excluding_diagnostic():
    # Exactly the non-diagnostic roles are ranked; diagnostic roles are valid but unranked.
    assert set(EVIDENCE_ROLE_RANK) == set(EvidenceRole) - DIAGNOSTIC_ROLES
    assert DIAGNOSTIC_ROLES <= set(EvidenceRole)


def test_strength_rank_reconciles_with_enum():
    assert set(STRENGTH_RANK) == set(EvidenceStrength)


def test_normalize_evidence_type_parity():
    # Behavior identical to the pre-slice normalizer for known + unknown + empty tokens.
    assert normalize_evidence_type("empirical_data_evidence") == "empirical_data"
    assert normalize_evidence_type("empirical_data") == "empirical_data"
    assert normalize_evidence_type("expert_judgment") == "expert_judgment"
    assert normalize_evidence_type("differential_expression") == "differential_expression"
    assert normalize_evidence_type(None) == ""
    assert normalize_evidence_type("") == ""


def test_rank_lookup_by_string_value_still_works():
    # StrEnum keys resolve by their string value -> no call-site churn.
    assert EVIDENCE_TYPE_RANK["empirical_data"] == 4
    assert EVIDENCE_ROLE_RANK["direct_test"] == 3
    assert STRENGTH_RANK["strong"] == 3


def test_is_authored_assertion_recognizes_both_expert_judgment_spellings():
    # Slice B contract preserved through the relocated normalizer.
    from science_tool.graph.belief import EvidenceUnit, is_authored_assertion

    def _u(et):
        return EvidenceUnit(
            line_uri="a", stance="supports", strength=None, independence="independent",
            independence_group=None, evidence_role=None, evidence_type=et,
            dispute_scope=None, proxy_directness=None, has_measurement_model=False,
            source=None, observability_keys=(),
        )
    assert is_authored_assertion(_u("expert_judgment"))
    assert is_authored_assertion(_u("expert_judgment_evidence"))
    assert not is_authored_assertion(_u("empirical_data"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `rtk proxy uv run --frozen pytest tests/test_evidence_vocab_reconciliation.py -v`
Expected: FAIL — `ImportError: cannot import name 'UNRANKED_EVIDENCE_TYPES'`.

- [ ] **Step 3: Rewrite the vocab section of `belief_weights.py`**

3a. Add the import near the top (after `from __future__ import annotations`):

```python
from science_model.reasoning import (
    EvidenceRole,
    EvidenceStrength,
    EvidenceType,
    canonical_evidence_type_token,
)
```

3b. Replace the five `ROLE_* = "…"` string-literal constants with enum-sourced ones (single source of truth; importers keep working because `StrEnum` members are `str`):

```python
ROLE_DIRECT_TEST = EvidenceRole.DIRECT_TEST
ROLE_PROXY_SUPPORT = EvidenceRole.PROXY_SUPPORT
ROLE_BACKGROUND = EvidenceRole.BACKGROUND_CONSTRAINT
ROLE_NEGATIVE_CONTROL = EvidenceRole.NEGATIVE_CONTROL
ROLE_MODEL_CRITICISM = EvidenceRole.MODEL_CRITICISM
```

(`DIAGNOSTIC_ROLES = frozenset({ROLE_NEGATIVE_CONTROL, ROLE_MODEL_CRITICISM})` is unchanged in source text — it now holds enum members. `STANCE_*`, `INDEPENDENT`/`SHARED_SOURCE`/`CIRCULAR`, `SCOPE_WHOLE_CLAIM`, `GATED_PROXY` are OUT OF SCOPE — leave them exactly as-is.)

3c. Remove the `_EVIDENCE_SUFFIX = "_evidence"` line (the suffix logic now lives in the model).

3d. Re-key the three rank dicts off enum members and add `UNRANKED_EVIDENCE_TYPES`:

```python
# Keyed on EvidenceType members. StrEnum keys resolve by string value too, so
# lookups like EVIDENCE_TYPE_RANK.get("empirical_data") still work unchanged.
EVIDENCE_TYPE_RANK = {
    EvidenceType.EMPIRICAL_DATA: 4,
    EvidenceType.BENCHMARK: 3,
    EvidenceType.SIMULATION: 3,
    EvidenceType.LITERATURE: 2,
    EvidenceType.EXPERT_JUDGMENT: 1,
}
# Valid-but-unranked-by-design types (rank 0), parallel to diagnostic roles.
UNRANKED_EVIDENCE_TYPES = frozenset({EvidenceType.NEGATIVE_RESULT})
EVIDENCE_ROLE_RANK = {
    EvidenceRole.DIRECT_TEST: 3,
    EvidenceRole.PROXY_SUPPORT: 2,
    EvidenceRole.BACKGROUND_CONSTRAINT: 1,
}
STRENGTH_RANK = {EvidenceStrength.STRONG: 3, EvidenceStrength.MODERATE: 2, EvidenceStrength.WEAK: 1}
```

3e. Replace `normalize_evidence_type` to delegate to the model (single suffix-normalization SSOT):

```python
def normalize_evidence_type(value: str | None) -> str:
    # Delegate suffix-stripping to the model SSOT; degrade gracefully (rank 0 via .get)
    # for empty/unknown graph literals — this reader must never raise.
    return canonical_evidence_type_token(value) or ""
```

3f. Add an explicit reconciliation gate at module load (after the dicts + `MAGNITUDE_NAMES`). Use explicit `raise` (not `assert`, which `python -O` strips) since this is a hard invariant:

```python
def _reconcile_evidence_vocab() -> None:
    """Fail-early gate: rank tables must stay in lock-step with the model enums."""
    if set(EVIDENCE_TYPE_RANK) | UNRANKED_EVIDENCE_TYPES != set(EvidenceType):
        raise ValueError(
            "EVIDENCE_TYPE_RANK | UNRANKED_EVIDENCE_TYPES must cover every EvidenceType; "
            f"got ranked={set(EVIDENCE_TYPE_RANK)} unranked={set(UNRANKED_EVIDENCE_TYPES)}"
        )
    if not set(EVIDENCE_TYPE_RANK).isdisjoint(UNRANKED_EVIDENCE_TYPES):
        raise ValueError("an unranked-by-design EvidenceType must not also be ranked")
    if set(EVIDENCE_ROLE_RANK) != set(EvidenceRole) - DIAGNOSTIC_ROLES:
        raise ValueError("EVIDENCE_ROLE_RANK must rank exactly the non-diagnostic EvidenceRoles")
    if set(STRENGTH_RANK) != set(EvidenceStrength):
        raise ValueError("STRENGTH_RANK must cover every EvidenceStrength")


_reconcile_evidence_vocab()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `rtk proxy uv run --frozen pytest tests/test_evidence_vocab_reconciliation.py -v`
Expected: PASS (7 tests).

- [ ] **Step 5: Run the full belief + policy suite for behavior-neutrality**

Run: `rtk proxy uv run --frozen pytest tests/test_belief_weights.py tests/test_belief_aggregate.py tests/test_belief_reduce.py tests/test_belief_refutation.py tests/test_belief_policy.py tests/test_belief_policy_aggregate.py tests/test_authored_confidence.py tests/test_authored_confidence_policy.py -v`
Expected: PASS — ranks are identical, only re-keyed; `is_authored_assertion` preserved.

- [ ] **Step 6: Lint**

Run: `rtk proxy uv run --frozen ruff check src/science_tool/graph/belief_weights.py tests/test_evidence_vocab_reconciliation.py`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
rtk git add src/science_tool/graph/belief_weights.py tests/test_evidence_vocab_reconciliation.py
rtk git commit -m "feat(belief): reconcile belief_weights ranks against model evidence enums + UNRANKED_EVIDENCE_TYPES (typed-evidence-vocab t3)"
```

---

## Task 4: `check_belief_eligible_empirical_has_dataset_usage` normalize-before-compare

**Files:**
- Modify: `src/science_tool/validate/checks/evidence_lines.py`
- Test: `tests/validate/test_checks_evidence_lines.py`

The current check (verbatim, `evidence_lines.py:582-583`):

```python
        # Only applies to empirical evidence lines.
        if fm.get("evidence_type") != "empirical_data_evidence":
            continue
```

- [ ] **Step 1: Write the failing test**

Append to `tests/validate/test_checks_evidence_lines.py` (harness: module-level `_write(root, rel, body)` writes a `.md`, `_ctx(root)` builds the `ValidateContext`; `Severity` is imported):

```python
def test_dataset_usage_check_flags_canonical_empirical_spelling(tmp_path: Path):
    from science_tool.validate.checks.evidence_lines import (
        check_belief_eligible_empirical_has_dataset_usage,
    )
    # Canonical 'empirical_data' (no _evidence suffix), belief-eligible, NO dataset_usage -> must flag.
    _write(tmp_path, "entities/evidence-lines/el01.md",
           "---\nstance: supports\ntarget: proposition:p1\nevidence_type: empirical_data\n---\n")
    rules = {r.rule for r in check_belief_eligible_empirical_has_dataset_usage(_ctx(tmp_path))}
    assert "evidence.empirical.requires_dataset_usage" in rules


def test_dataset_usage_check_flags_suffixed_empirical_spelling(tmp_path: Path):
    from science_tool.validate.checks.evidence_lines import (
        check_belief_eligible_empirical_has_dataset_usage,
    )
    # Suffixed 'empirical_data_evidence' (un-re-materialized graph) still flagged.
    _write(tmp_path, "entities/evidence-lines/el01.md",
           "---\nstance: supports\ntarget: proposition:p1\nevidence_type: empirical_data_evidence\n---\n")
    rules = {r.rule for r in check_belief_eligible_empirical_has_dataset_usage(_ctx(tmp_path))}
    assert "evidence.empirical.requires_dataset_usage" in rules


def test_dataset_usage_check_ignores_non_empirical(tmp_path: Path):
    from science_tool.validate.checks.evidence_lines import (
        check_belief_eligible_empirical_has_dataset_usage,
    )
    _write(tmp_path, "entities/evidence-lines/el01.md",
           "---\nstance: supports\ntarget: proposition:p1\nevidence_type: literature_evidence\n---\n")
    rules = {r.rule for r in check_belief_eligible_empirical_has_dataset_usage(_ctx(tmp_path))}
    assert "evidence.empirical.requires_dataset_usage" not in rules
```

- [ ] **Step 2: Run test to verify it fails**

Run: `rtk proxy uv run --frozen pytest tests/validate/test_checks_evidence_lines.py -k "canonical_empirical or suffixed_empirical or non_empirical" -v`
Expected: FAIL — `test_dataset_usage_check_flags_canonical_empirical_spelling` does NOT flag (the check only matches the suffixed literal).

- [ ] **Step 3: Normalize before the comparison**

In `src/science_tool/validate/checks/evidence_lines.py`. `normalize_evidence_type` is already imported (line 30); add `EvidenceType` to the imports — append it to the existing `from science_model.reasoning import (...)` block if present, otherwise add a new import line near the other model imports:

```python
from science_model.reasoning import EvidenceType
```

Replace the comparison:

```python
        # Only applies to empirical evidence lines.
        if fm.get("evidence_type") != "empirical_data_evidence":
            continue
```

with:

```python
        # Only applies to empirical evidence lines. Normalize first so both the canonical
        # ('empirical_data') and authored-suffixed ('empirical_data_evidence') spellings match.
        if normalize_evidence_type(fm.get("evidence_type")) != EvidenceType.EMPIRICAL_DATA:
            continue
```

- [ ] **Step 4: Run test to verify it passes**

Run: `rtk proxy uv run --frozen pytest tests/validate/test_checks_evidence_lines.py -k "canonical_empirical or suffixed_empirical or non_empirical" -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Run the full evidence-lines validator suite for no regression**

Run: `rtk proxy uv run --frozen pytest tests/validate/test_checks_evidence_lines.py -v`
Expected: PASS.

- [ ] **Step 6: Lint**

Run: `rtk proxy uv run --frozen ruff check src/science_tool/validate/checks/evidence_lines.py tests/validate/test_checks_evidence_lines.py`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
rtk git add src/science_tool/validate/checks/evidence_lines.py tests/validate/test_checks_evidence_lines.py
rtk git commit -m "fix(validate): normalize evidence_type before the empirical dataset-usage gate (typed-evidence-vocab t4)"
```

---

## Task 5: `has_empirical_data` normalize-before-membership

**Files:**
- Modify: `src/science_tool/graph/store/summary.py`
- Test: `tests/test_store_summary.py` (create if absent; otherwise append)

The current code (verbatim, `summary.py:58-61`):

```python
    evidence_types = sorted(_collect_evidence_types(knowledge, provenance, uri))
    has_empirical_data = any(
        evidence_type in {"empirical_data_evidence", "benchmark_evidence"} for evidence_type in evidence_types
    )
```

`_collect_evidence_types(knowledge, provenance, uri) -> set[str]` returns the raw evidence_type literal strings attached to a claim's evidence lines.

- [ ] **Step 1: Write the failing test**

We test the classification predicate directly via a small helper so the test does not need a full graph. Add a module-level pure helper in `summary.py` (Step 3a) named `_is_empirical_type`, then test it. Create `tests/test_store_summary.py`:

```python
from science_tool.graph.store.summary import _is_empirical_type


def test_is_empirical_type_canonical():
    assert _is_empirical_type("empirical_data")
    assert _is_empirical_type("benchmark")


def test_is_empirical_type_suffixed():
    assert _is_empirical_type("empirical_data_evidence")
    assert _is_empirical_type("benchmark_evidence")


def test_is_empirical_type_negatives():
    assert not _is_empirical_type("literature")
    assert not _is_empirical_type("simulation_evidence")
    assert not _is_empirical_type("expert_judgment")
    assert not _is_empirical_type("")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `rtk proxy uv run --frozen pytest tests/test_store_summary.py -v`
Expected: FAIL — `ImportError: cannot import name '_is_empirical_type'`.

- [ ] **Step 3: Add the helper + use it**

In `src/science_tool/graph/store/summary.py`:

3a. Add imports near the existing `from science_tool.graph.belief import ...` (line 11):

```python
from science_tool.graph.belief_weights import normalize_evidence_type
from science_model.reasoning import EvidenceType
```

3b. Add a module-level helper (place it above `_claim_summary_data`):

```python
_EMPIRICAL_TYPES = frozenset({EvidenceType.EMPIRICAL_DATA, EvidenceType.BENCHMARK})


def _is_empirical_type(evidence_type: str) -> bool:
    """True iff the (possibly suffixed) evidence_type literal is empirical-grade data.

    Normalizes first so canonical ('empirical_data') and authored-suffixed
    ('empirical_data_evidence') literals both classify identically.
    """
    return normalize_evidence_type(evidence_type) in _EMPIRICAL_TYPES
```

3c. Replace the `has_empirical_data` expression:

```python
    has_empirical_data = any(
        evidence_type in {"empirical_data_evidence", "benchmark_evidence"} for evidence_type in evidence_types
    )
```

with:

```python
    has_empirical_data = any(_is_empirical_type(evidence_type) for evidence_type in evidence_types)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `rtk proxy uv run --frozen pytest tests/test_store_summary.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Run the store/summary regression for no regression**

Run: `rtk proxy uv run --frozen pytest tests/ -k "summary or claim_summary" -v`
Expected: PASS (existing summary tests unaffected). If no such tests exist, this run reports only the 3 new tests — that is acceptable.

- [ ] **Step 6: Lint**

Run: `rtk proxy uv run --frozen ruff check src/science_tool/graph/store/summary.py tests/test_store_summary.py`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
rtk git add src/science_tool/graph/store/summary.py tests/test_store_summary.py
rtk git commit -m "fix(summary): normalize evidence_type in has_empirical_data classification (typed-evidence-vocab t5)"
```

---

## Task 6: Workbench `EvidenceStub` typing + canonical staging + fixture fix

**Files:**
- Modify: `src/science_tool/dag/workbench.py`
- Test: `tests/test_workbench_schema.py`

The current code (verbatim): `EvidenceStub.evidence_type: str | None = None` (`workbench.py:95`); staging at `workbench.py:263`:

```python
    is_staged_empirical = stub.evidence_type == "empirical_data_evidence" and not stub.dataset_usage
```

- [ ] **Step 1: Fix the now-invalid fixture + write failing tests**

1a. In `tests/test_workbench_schema.py`, change the `test_row_with_evidence_stubs` fixture's invalid type (line ~105) from:

```python
                    "evidence_type": "differential_expression",
```

to a valid authored type:

```python
                    "evidence_type": "empirical_data_evidence",
```

1b. Append two tests to `tests/test_workbench_schema.py` (it imports `EvidenceStub`/`WorkbenchRow`, `pytest`; add `ValidationError` from `pydantic` and `EvidenceType` from `science_model.reasoning` if not already imported):

```python
def test_evidence_stub_canonicalizes_evidence_type() -> None:
    from science_model.reasoning import EvidenceType
    stub = EvidenceStub.model_validate({"stance": "supports", "evidence_type": "empirical_data_evidence"})
    assert stub.evidence_type is EvidenceType.EMPIRICAL_DATA


def test_evidence_stub_rejects_unknown_evidence_type() -> None:
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        EvidenceStub.model_validate({"stance": "supports", "evidence_type": "differential_expression"})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `rtk proxy uv run --frozen pytest tests/test_workbench_schema.py -k "evidence_stub or evidence_stubs" -v`
Expected: FAIL — `test_evidence_stub_canonicalizes_evidence_type` returns the raw string (field still `str`), and `test_evidence_stub_rejects_unknown_evidence_type` does NOT raise.

- [ ] **Step 3: Type the stub field + validator + canonical staging**

In `src/science_tool/dag/workbench.py`:

3a. Ensure `field_validator` is imported from pydantic (line 29 currently `from pydantic import BaseModel, ConfigDict, Field`):

```python
from pydantic import BaseModel, ConfigDict, Field, field_validator
```

3b. Add `EvidenceType` + `canonical_evidence_type_token` imports from the model (near line 31-32 model imports):

```python
from science_model.reasoning import EvidenceType, canonical_evidence_type_token
```

3c. Change the `EvidenceStub` field from:

```python
    evidence_type: str | None = None
```

to:

```python
    evidence_type: EvidenceType | None = None
```

and add a validator in the `EvidenceStub` class body:

```python
    @field_validator("evidence_type", mode="before")
    @classmethod
    def _canonicalize_evidence_type(cls, value: object) -> object:
        if isinstance(value, str):
            return canonical_evidence_type_token(value)
        return value
```

3d. Replace the staging comparison at `workbench.py:263`:

```python
    is_staged_empirical = stub.evidence_type == "empirical_data_evidence" and not stub.dataset_usage
```

with the canonical-member comparison (the field is now canonical for both authored spellings):

```python
    is_staged_empirical = stub.evidence_type == EvidenceType.EMPIRICAL_DATA and not stub.dataset_usage
```

(Line ~280 `evidence_type=stub.evidence_type` needs no change: the `EvidenceLineEntity` validator is idempotent on an already-canonical `EvidenceType`.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `rtk proxy uv run --frozen pytest tests/test_workbench_schema.py -v`
Expected: PASS (the fixed `test_row_with_evidence_stubs` + the 2 new tests + the rest of the file).

- [ ] **Step 5: Run the workbench suite for no regression**

Run: `rtk proxy uv run --frozen pytest tests/ -k workbench -v`
Expected: PASS.

- [ ] **Step 6: Lint**

Run: `rtk proxy uv run --frozen ruff check src/science_tool/dag/workbench.py tests/test_workbench_schema.py`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
rtk git add src/science_tool/dag/workbench.py tests/test_workbench_schema.py
rtk git commit -m "feat(workbench): type EvidenceStub.evidence_type + canonical staging; fix invalid fixture (typed-evidence-vocab t6)"
```

---

## Task 7: Wire `cli.py --evidence-type` to `click.Choice` + reconciliation gate

**Files:**
- Modify: `src/science_tool/cli.py`
- Test: `tests/test_cli_evidence_type_choice.py` (create)

The current code: `EVIDENCE_TYPES` tuple (`cli.py:2203`, defined but unused) and `@click.option("--evidence-type", default=None)` (`cli.py:2272`).

- [ ] **Step 1: Write the failing test**

Create `tests/test_cli_evidence_type_choice.py`:

```python
from click.testing import CliRunner

from science_tool.cli import EVIDENCE_TYPES, cli


def test_evidence_types_reconciles_with_enum():
    from science_model.reasoning import EvidenceType, canonical_evidence_type_token

    assert {canonical_evidence_type_token(t) for t in EVIDENCE_TYPES} == {m.value for m in EvidenceType}


def test_cli_rejects_out_of_vocab_evidence_type(tmp_path):
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["graph", "add", "proposition", "P text", "--source", "t1",
         "--evidence-type", "differential_expression"],
        catch_exceptions=False,
    )
    # click.Choice rejects before any graph work -> usage error (exit code 2).
    assert result.exit_code == 2
    assert "differential_expression" in result.output
```

Note on harness: `cli` is the root Click group exported by `science_tool.cli`. If the existing CLI tests import the group under a different name, mirror their import. The `graph add proposition` invocation only needs to reach option parsing (which is where `click.Choice` rejects), so it does not need a real project on disk.

- [ ] **Step 2: Run test to verify it fails**

Run: `rtk proxy uv run --frozen pytest tests/test_cli_evidence_type_choice.py -v`
Expected: FAIL — `test_cli_rejects_out_of_vocab_evidence_type` gets a non-2 exit code (the plain option accepts any string).

- [ ] **Step 3: Wire the choice**

In `src/science_tool/cli.py`, change the option declaration at line 2272 from:

```python
@click.option("--evidence-type", default=None)
```

to:

```python
@click.option("--evidence-type", default=None, type=click.Choice(EVIDENCE_TYPES))
```

(`EVIDENCE_TYPES` is module-level above this command; no import needed. Keep `EVIDENCE_TYPES` exactly as the authored-alias tuple — do NOT regenerate it from the enum, so the suffixed authoring spellings remain valid choices. The command still writes the chosen alias literal to RDF via `mutations.py`; graph readers normalize it.)

- [ ] **Step 4: Run test to verify it passes**

Run: `rtk proxy uv run --frozen pytest tests/test_cli_evidence_type_choice.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Run the CLI graph-add suite for no regression**

Run: `rtk proxy uv run --frozen pytest tests/ -k "cli and (proposition or evidence or graph_add)" -v`
Expected: PASS. (If a pre-existing test invokes `graph add proposition --evidence-type <X>` with a value not in `EVIDENCE_TYPES`, that is a latent bad value — update it to a valid alias and note it in the commit.)

- [ ] **Step 6: Lint**

Run: `rtk proxy uv run --frozen ruff check src/science_tool/cli.py tests/test_cli_evidence_type_choice.py`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
rtk git add src/science_tool/cli.py tests/test_cli_evidence_type_choice.py
rtk git commit -m "feat(cli): gate --evidence-type with click.Choice(EVIDENCE_TYPES) + enum reconciliation (typed-evidence-vocab t7)"
```

---

## Task 8: Reconcile the taxonomy doc + final regression net

**Files:**
- Modify: `docs/proposition-and-evidence-model.md`

- [ ] **Step 1: Update the contradicting paragraph**

In `docs/proposition-and-evidence-model.md`, the current text (around line 59) reads:

```
`negative_result` is not a separate evidence type.
It is a result or interpretation pattern: an observation can report no observed effect, and the resulting evidence edge will usually have `stance: disputes` or weaken support for the target proposition.
```

Replace it with:

```
`negative_result` is accepted as a valid-but-unranked `evidence_type` token (it contributes no ordinal weight, i.e. rank 0), kept for compatibility with the authored CLI vocabulary. Semantically it remains a result or interpretation pattern rather than a true evidence category: an observation can report no observed effect, and the resulting evidence edge will usually have `stance: disputes` or weaken support for the target proposition. Re-modeling it (e.g. as `stance: disputes` plus role/scope metadata) is deferred to a future semantics cleanup.
```

- [ ] **Step 2: Commit the doc**

```bash
rtk git add docs/proposition-and-evidence-model.md
rtk git commit -m "doc: reconcile negative_result paragraph with typed EvidenceType vocabulary (typed-evidence-vocab t8)"
```

- [ ] **Step 3: Run the final regression net**

```bash
rtk proxy uv run --frozen pytest \
  model/tests/test_evidence_type.py \
  model/tests/test_evidence_line_entity.py \
  tests/test_evidence_vocab_reconciliation.py \
  tests/test_belief_weights.py \
  tests/test_belief_aggregate.py \
  tests/test_belief_collect.py \
  tests/test_belief_reduce.py \
  tests/test_belief_refutation.py \
  tests/test_belief_classify.py \
  tests/test_belief_e2e.py \
  tests/test_belief_policy.py \
  tests/test_belief_policy_aggregate.py \
  tests/test_authored_confidence.py \
  tests/test_authored_confidence_policy.py \
  tests/test_belief_snapshot.py \
  tests/test_bundle_belief_rollup.py \
  tests/test_bundle_belief_snapshot.py \
  tests/test_evidence_line_belief_checks.py \
  tests/test_store_summary.py \
  tests/test_workbench_schema.py \
  tests/test_cli_evidence_type_choice.py \
  tests/validate/test_checks_evidence_lines.py \
  tests/validate/test_checks_belief_sensitivity.py \
  -q
```

Expected: ALL PASS — empirical belief scoring unchanged; evidence vocabulary now typed, enforced at parse, and reconciled.

- [ ] **Step 4: Final lint sweep**

```bash
rtk proxy uv run --frozen ruff check \
  model/src/science_model/reasoning.py \
  model/src/science_model/entities.py \
  src/science_tool/graph/belief_weights.py \
  src/science_tool/validate/checks/evidence_lines.py \
  src/science_tool/graph/store/summary.py \
  src/science_tool/dag/workbench.py \
  src/science_tool/cli.py
```

Expected: PASS.

Then finish the branch with **superpowers:finishing-a-development-branch**.

---

## Plan Self-Review

**Spec coverage:**
- §1 `EvidenceType` enum (6 members incl. `NEGATIVE_RESULT`) → Task 1.
- §1 `canonical_evidence_type_token` (model normalization SSOT, `None`→`None`) → Task 1.
- §2 type field + canonicalize-at-parse (both spellings accepted, unknown raises) → Task 2.
- §3 normalization API (model raises at coercion; tool `normalize_evidence_type` degrades to `""`/rank 0) → Tasks 1 (model helper) + 3 (tool delegation).
- §4 rank reconciliation (enum-keyed dicts, role constants from enum, `UNRANKED_EVIDENCE_TYPES`, the three precise invariants incl. diagnostic-role exclusion) → Task 3.
- §4b consumer sweep: dataset-usage check → Task 4; `has_empirical_data` → Task 5; workbench staging + `EvidenceStub` typing + fixture → Task 6; `cli.py --evidence-type` ingress + reconciliation → Task 7.
- §5 behavior-neutrality (ranks identical; `negative_result` rank 0; `is_authored_assertion` both spellings) → Tasks 3 (parity + Slice-B contract tests) + final net.
- §6 docs reconciliation → Task 8.
- §7 testing: model validator parametrized, reconciliation asserts, both-spelling consumer tests, CLI choice test → Tasks 1–7; final regression net → Task 8.

**Placeholder scan:** every code step shows complete, runnable code against verified harnesses — `_minimal_evidence_line()` (model), `_write`/`_ctx` (validate), `EvidenceStub`/`WorkbenchRow` (workbench), `CliRunner`/`cli` (CLI). The two delegated, explicitly-bounded details: (a) the exact import name of the root Click group in Task 7 (mirror existing CLI tests if it is not `cli`); (b) whether `tests/test_store_summary.py` exists already (append vs create) — the assertion content is fully specified either way.

**Type consistency:** `EvidenceType`, `canonical_evidence_type_token`, `normalize_evidence_type`, `UNRANKED_EVIDENCE_TYPES`, `_is_empirical_type`, and the validator name `_canonicalize_evidence_type` are used identically across tasks. The field type `EvidenceType | None` matches between `EvidenceLineEntity` (Task 2) and `EvidenceStub` (Task 6). Rank dicts are keyed by enum members in Task 3 and asserted as member-sets in the reconciliation test. `EVIDENCE_TYPES` stays an authored-alias tuple (suffixed spellings) everywhere; the enum is the normalized-token set, reconciled under `canonical_evidence_type_token`.

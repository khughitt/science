# Core Reproducibility Gate v1 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a third-party-reproducibility axis to the dataset `access` block and enforce it at the plan data-access gate, so a non-reproducible dataset can no longer silently pass as a plan input.

**Architecture:** A canonical `access.reproducibility` block (three Five-Safes controls) is the source of truth; a pure `reproducibility_class_for()` derives a verdict + gap_reason; a `reproducibility_policy` (project + plan, plan wins) sets the bar; and a new `check_reproducibility()` gate enforces the bar over the transitive external-input closure, with plan-level waivers as the only escape.

**Tech Stack:** Python ≥3.11, Pydantic v2, pytest ≥9, ruff (line-length 120), uv workspace.

## Global Constraints

- Python `>=3.11`; Pydantic **v2** (`@model_validator(mode="after")`, `@field_validator` + `@classmethod`, inline `Literal[...]`, not `enum.Enum`).
- ruff line-length **120**; run `uv run ruff format` + `uv run ruff check` before each commit.
- Tool suite lives in `~/d/science/science/`; model suite in `~/d/science/science/model/`. Each has its own `pytest` config with `testpaths = ["tests"]`. Run tests with `uv run --frozen pytest ...` **from the suite's directory**.
- The class is **derived, never stored**. `unknown` is off-lattice (not "below bar"). `insider-only` is checked **before** `trust-based-output`.
- Branch: `reproducibility-gate-v1` in `~/d/science`. No `science-commons`, no CLI surfacing, no backfill in v1.
- No AI-attribution trailers in commit messages.

---

## File Structure

- `science/model/src/science_model/packages/schema.py` — **Modify**: add `AccessReproducibility` model; attach `reproducibility` field to `AccessBlock`.
- `science/model/src/science_model/frontmatter.py` — **Modify**: `_coerce_access` passes the `reproducibility` sub-block.
- `science/src/science_tool/datasets/semantics.py` — **Modify**: add `ReproClass`/`OrdinalReproClass` aliases, the lattice, `reproducibility_class_for()`, `repro_class_rank()`, `repro_meets_bar()`.
- `science/src/science_tool/project_config.py` — **Modify**: `ReproducibilityPolicyConfig`, `ReproducibilityWaiver`, `PlanReproducibilityPolicy`, `effective_reproducibility_policy()`, `load_plan_reproducibility_policy()`; add `reproducibility_policy` field to `ProjectConfig`.
- `science/src/science_tool/plan_gate.py` — **Modify**: `check_reproducibility()` + `_effective_repro_class()` (derived closure) + `_weakest_class()`; `check_plan_data_gate()` (the integrated access-then-reproducibility Step-2b entry point).
- `commands/plan-pipeline.md` — **Modify**: Step 2b reproducibility enforcement prose.
- `templates/dataset.md` — **Modify**: add the `reproducibility:` block.
- `docs/user-guide/entities.md` — **Modify**: authoring section for reproducibility.
- Tests: `science/model/tests/test_dataset_models.py`, `science/tests/test_dataset_semantics.py`, `science/tests/test_project_config.py`, `science/tests/test_plan_reproducibility_gate.py`.

---

### Task 1: `access.reproducibility` schema block + coercion

**Files:**
- Modify: `science/model/src/science_model/packages/schema.py`
- Modify: `science/model/src/science_model/frontmatter.py` (the `_coerce_access` helper)
- Test: `science/model/tests/test_dataset_models.py`

**Interfaces:**
- Produces: `AccessReproducibility(obtainability, execution, extractability, notes)` Pydantic model with all-`unknown`/`""` defaults; `AccessBlock.reproducibility: AccessReproducibility` (default_factory). Parsing an `access:` dict with a `reproducibility:` sub-block round-trips it; an absent sub-block yields all-`unknown`.

- [ ] **Step 1: Write the failing tests**

Add to `science/model/tests/test_dataset_models.py`:

```python
import pytest
from pydantic import ValidationError

from science_model.packages.schema import AccessBlock, AccessReproducibility


def test_access_reproducibility_defaults_to_unknown():
    block = AccessBlock(level="controlled", verified=True)
    assert block.reproducibility.obtainability == "unknown"
    assert block.reproducibility.execution == "unknown"
    assert block.reproducibility.extractability == "unknown"
    assert block.reproducibility.notes == ""


def test_access_reproducibility_accepts_valid_controls():
    block = AccessBlock(
        level="controlled",
        verified=True,
        reproducibility=AccessReproducibility(
            obtainability="approved-project",
            execution="trusted-environment",
            extractability="aggregate-reviewed",
            notes="Only reviewed aggregates leave the enclave.",
        ),
    )
    assert block.reproducibility.extractability == "aggregate-reviewed"


def test_access_reproducibility_rejects_bad_enum():
    with pytest.raises(ValidationError):
        AccessReproducibility(obtainability="downloadable-somehow")
```

- [ ] **Step 2: Run tests to verify they fail**

Run from `~/d/science/science/model/`: `uv run --frozen pytest tests/test_dataset_models.py -k reproducibility -v`
Expected: FAIL with `ImportError: cannot import name 'AccessReproducibility'`.

- [ ] **Step 3: Add the model and field**

In `schema.py`, add immediately after the `AccessException` class:

```python
class AccessReproducibility(BaseModel):
    """Third-party reproducibility controls (Five Safes) for an external dataset.

    Canonical source of truth. The reproducibility *class* is DERIVED from these
    (see science_tool.datasets.semantics.reproducibility_class_for), never stored.
    """

    obtainability: Literal[
        "public",
        "registration",
        "self-service-dua",
        "approved-researcher",
        "approved-project",
        "named-collaboration",
        "unavailable",
        "unknown",
    ] = "unknown"
    execution: Literal[
        "local",
        "hosted-workspace",
        "trusted-environment",
        "federated-code-to-data",
        "custodian-run",
        "unknown",
    ] = "unknown"
    extractability: Literal[
        "full-dataset",
        "analysis-dataset",
        "synthetic-dataset",
        "aggregate-unreviewed",
        "aggregate-reviewed",
        "none",
        "unknown",
    ] = "unknown"
    notes: str = ""
```

Then, in the `AccessBlock` class, add one field after the `exception` field:

```python
    reproducibility: AccessReproducibility = Field(default_factory=AccessReproducibility)
```

- [ ] **Step 4: Wire coercion in `frontmatter.py`**

In `_coerce_access`, where the `AccessBlock(...)` is constructed from the dict, add a `reproducibility` kwarg mirroring the `exception` handling:

```python
    if isinstance(raw, dict):
        ex_raw = raw.get("exception") or {}
        repro_raw = raw.get("reproducibility") or {}
        return AccessBlock(
            level=cast(_AccessLevel, raw.get("level", "public")),
            # ... existing fields unchanged ...
            exception=AccessException(**ex_raw) if ex_raw else AccessException(),
            reproducibility=AccessReproducibility(**repro_raw) if repro_raw else AccessReproducibility(),
        )
```

Add `AccessReproducibility` to the existing `from science_model.packages.schema import ...` line in `frontmatter.py`.

- [ ] **Step 5: Add a real coercion round-trip test (through `parse_entity_file`)**

A direct `AccessReproducibility(...)` construction does **not** prove `_coerce_access` passes the
nested block — it would pass even if coercion dropped it. Test the real parse path instead. Add to
`test_dataset_models.py`:

```python
from pathlib import Path

from science_model.frontmatter import parse_entity_file


def test_access_reproducibility_round_trips_through_parse_entity_file(tmp_path: Path):
    d = tmp_path / "entities" / "datasets"
    d.mkdir(parents=True)
    (d / "ds.md").write_text(
        '---\nid: "dataset:ds"\ntype: "dataset"\ntitle: "DS"\norigin: "external"\n'
        "access:\n"
        '  level: "controlled"\n'
        "  verified: true\n"
        "  reproducibility:\n"
        '    obtainability: "approved-project"\n'
        '    execution: "trusted-environment"\n'
        '    extractability: "aggregate-reviewed"\n'
        '    notes: "enclave"\n---\n',
        encoding="utf-8",
    )
    entity = parse_entity_file(d / "ds.md", tmp_path.name)
    assert entity is not None
    assert entity.access.reproducibility.obtainability == "approved-project"
    assert entity.access.reproducibility.extractability == "aggregate-reviewed"
    assert entity.access.reproducibility.notes == "enclave"
```

Run from `~/d/science/science/model/`: `uv run --frozen pytest tests/test_dataset_models.py -k reproducibility -v`
Expected: PASS (4 tests).

- [ ] **Step 6: Confirm the JSON schema stays permissive (documented decision)**

v1 leaves both JSON schemas (`schemas/mixin-dataset-1.0.json`, `schemas/science-pkg-entity-1.0.json`)
**unchanged**: neither sets `additionalProperties: false` on `access`, so an `access.reproducibility`
sub-key is already silently allowed — exactly as the existing `access.exception` block is (it is not in
the JSON mixin either). Pydantic is the authoritative enum enforcer. Add a confirming test that the
repo's Draft-2020-12 `EntityValidator` accepts a dataset carrying the block. **Mirror the existing
`EntityValidator(...)` construction in `science/tests/test_commons_promote_validation.py`** (do not
invent constructor args); build a minimal external-dataset dict with an `access.reproducibility` block
and assert `list(validator.validate(entity)) == []` (no schema errors).

Run from `~/d/science/science/`: `uv run --frozen pytest tests/test_commons_promote_validation.py -k reproducib -v`
Expected: PASS (block validates; JSON layer permissive as intended).

- [ ] **Step 7: Format, lint, commit**

```bash
cd ~/d/science
uv run --directory science/model ruff format src/science_model/packages/schema.py src/science_model/frontmatter.py
uv run --directory science/model ruff check src/science_model
git add science/model/src/science_model/packages/schema.py science/model/src/science_model/frontmatter.py science/model/tests/test_dataset_models.py science/tests/test_commons_promote_validation.py
git commit -m "feat(model): add access.reproducibility block (Five Safes controls)"
```

---

### Task 2: `reproducibility_class_for()` classifier + lattice helpers

**Files:**
- Modify: `science/src/science_tool/datasets/semantics.py`
- Test: `science/tests/test_dataset_semantics.py`

**Interfaces:**
- Consumes: raw frontmatter `Mapping` (same shape `runtime_state_for` takes); reads `fm["access"]["reproducibility"]`.
- Produces:
  - `ReproClass = Literal["third-party-reproducible","credentialed-reproducible","trust-based-output","insider-only","unknown"]`
  - `OrdinalReproClass` = the same minus `"unknown"`.
  - `reproducibility_class_for(fm: Mapping[str, object]) -> tuple[ReproClass, str]` → `(class, gap_reason)`.
  - `repro_class_rank(cls: str) -> int` (higher = more reproducible; raises on `unknown`).
  - `repro_meets_bar(cls: str, bar: str) -> bool`.

- [ ] **Step 1: Write the failing tests**

Add to `science/tests/test_dataset_semantics.py`:

```python
from science_tool.datasets.semantics import (
    reproducibility_class_for,
    repro_meets_bar,
)


def _fm(obtain, execution, extract):
    return {"access": {"reproducibility": {
        "obtainability": obtain, "execution": execution, "extractability": extract,
    }}}


def test_public_download_is_third_party_reproducible():
    cls, _ = reproducibility_class_for(_fm("public", "local", "full-dataset"))
    assert cls == "third-party-reproducible"


def test_self_service_dua_download_is_credentialed():
    cls, _ = reproducibility_class_for(_fm("self-service-dua", "local", "analysis-dataset"))
    assert cls == "credentialed-reproducible"


def test_n3c_shape_is_trust_based_output():
    cls, gap = reproducibility_class_for(_fm("approved-project", "trusted-environment", "aggregate-reviewed"))
    assert cls == "trust-based-output"
    assert "aggregate-reviewed" in gap


def test_custodian_run_is_insider_only_before_trust_based():
    # custodian-run + aggregate outputs must NOT be credited as trust-based
    cls, _ = reproducibility_class_for(_fm("named-collaboration", "custodian-run", "aggregate-reviewed"))
    assert cls == "insider-only"


def test_any_unknown_control_yields_unknown():
    cls, _ = reproducibility_class_for(_fm("public", "unknown", "full-dataset"))
    assert cls == "unknown"


def test_absent_reproducibility_block_is_unknown():
    assert reproducibility_class_for({"access": {"level": "public", "verified": True}})[0] == "unknown"
    assert reproducibility_class_for({})[0] == "unknown"


def test_repro_meets_bar_ordering():
    assert repro_meets_bar("third-party-reproducible", "trust-based-output") is True
    assert repro_meets_bar("insider-only", "trust-based-output") is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run from `~/d/science/science/`: `uv run --frozen pytest tests/test_dataset_semantics.py -k "repro or third_party or n3c or custodian or unknown_control or absent_repro" -v`
Expected: FAIL with `ImportError: cannot import name 'reproducibility_class_for'`.

- [ ] **Step 3: Implement the classifier**

Add to `semantics.py` (after the `_access` helper; reuse it and `_nonempty_str`):

```python
OrdinalReproClass = Literal[
    "third-party-reproducible",
    "credentialed-reproducible",
    "trust-based-output",
    "insider-only",
]
ReproClass = Literal[
    "third-party-reproducible",
    "credentialed-reproducible",
    "trust-based-output",
    "insider-only",
    "unknown",
]

# Known classes, strongest -> weakest. `unknown` is OFF-lattice.
_REPRO_LATTICE: tuple[str, ...] = (
    "third-party-reproducible",
    "credentialed-reproducible",
    "trust-based-output",
    "insider-only",
)
_LOCAL_RERUNNABLE = {"full-dataset", "analysis-dataset", "synthetic-dataset"}
_CREDENTIALED_OBTAIN = {"registration", "self-service-dua", "approved-researcher"}
_TRE_EXECUTION = {"trusted-environment", "federated-code-to-data"}
_AGGREGATE_EXTRACT = {"aggregate-reviewed", "aggregate-unreviewed"}


def _repro(access: Mapping[str, object]) -> Mapping[str, object]:
    repro = access.get("reproducibility")
    return repro if isinstance(repro, Mapping) else {}


def reproducibility_class_for(fm: Mapping[str, object]) -> tuple[ReproClass, str]:
    """Derive (class, gap_reason) from access.reproducibility controls.

    Returns 'unknown' if any decision-relevant control is unknown or the block is
    absent. gap_reason lists the controls that determined a non-top class.
    Ordered rules; first match wins. insider-only is checked before trust-based-output.
    """
    repro = _repro(_access(fm))
    obtain = _nonempty_str(repro.get("obtainability")) or "unknown"
    execution = _nonempty_str(repro.get("execution")) or "unknown"
    extract = _nonempty_str(repro.get("extractability")) or "unknown"
    gap = f"{obtain} + {execution} + {extract}"

    if "unknown" in (obtain, execution, extract):
        return "unknown", "unassessed: " + gap
    if extract in _LOCAL_RERUNNABLE and obtain == "public":
        return "third-party-reproducible", ""
    if extract in _LOCAL_RERUNNABLE and obtain in _CREDENTIALED_OBTAIN:
        return "credentialed-reproducible", gap
    if obtain == "named-collaboration" or execution == "custodian-run" or extract == "none":
        return "insider-only", gap
    if execution in _TRE_EXECUTION and extract in _AGGREGATE_EXTRACT:
        return "trust-based-output", gap
    return "insider-only", gap  # conservative fail-safe for unmatched fully-known combos


def repro_class_rank(cls: str) -> int:
    """Rank a KNOWN class; higher = more reproducible. Raises on off-lattice 'unknown'."""
    try:
        return len(_REPRO_LATTICE) - _REPRO_LATTICE.index(cls)
    except ValueError as exc:
        raise ValueError(f"{cls!r} is not an ordinal reproducibility class") from exc


def repro_meets_bar(cls: str, bar: str) -> bool:
    """True if KNOWN class `cls` meets or exceeds `bar`. Both must be on the lattice."""
    return repro_class_rank(cls) >= repro_class_rank(bar)
```

Confirm `Literal` and `Mapping` are already imported at the top of `semantics.py` (they are — `runtime_state_for` uses both).

- [ ] **Step 4: Run tests to verify they pass**

Run from `~/d/science/science/`: `uv run --frozen pytest tests/test_dataset_semantics.py -k "repro or third_party or n3c or custodian or unknown_control or absent_repro" -v`
Expected: PASS (7 tests).

- [ ] **Step 5: Format, lint, commit**

```bash
cd ~/d/science/science
uv run --frozen ruff format src/science_tool/datasets/semantics.py
uv run --frozen ruff check src/science_tool/datasets/semantics.py
git add src/science_tool/datasets/semantics.py tests/test_dataset_semantics.py
git commit -m "feat(datasets): derive reproducibility class from access controls"
```

---

### Task 3: `reproducibility_policy` in project + plan config

**Files:**
- Modify: `science/src/science_tool/project_config.py`
- Test: `science/tests/test_project_config.py` (create if it does not exist; check with `ls science/tests | grep project_config`)

**Interfaces:**
- Consumes: `OrdinalReproClass` from `science_tool.datasets.semantics`.
- Produces:
  - `ReproducibilityPolicyConfig(bar: OrdinalReproClass = "third-party-reproducible", unknown: Literal["halt","warn"] = "halt", below_bar: Literal["halt","warn"] = "halt")`.
  - `ReproducibilityWaiver(dataset, accepted_class: OrdinalReproClass, decision_date, rationale, mitigation)`.
  - `PlanReproducibilityPolicy(bar: OrdinalReproClass | None, unknown, below_bar, waivers: list[ReproducibilityWaiver])`.
  - `ProjectConfig.reproducibility_policy: ReproducibilityPolicyConfig | None = None`.
  - `effective_reproducibility_policy(project, plan) -> ReproducibilityPolicyConfig | None` — plan over project; `None` only when both absent.
  - `load_plan_reproducibility_policy(plan_path) -> PlanReproducibilityPolicy | None` — parse a plan file's frontmatter `reproducibility_policy` (raw route via `parse_frontmatter`) into the model.

- [ ] **Step 1: Write the failing tests**

Add to `science/tests/test_project_config.py`:

```python
from pathlib import Path

from science_tool.project_config import (
    ProjectConfig,
    ReproducibilityPolicyConfig,
    PlanReproducibilityPolicy,
    ReproducibilityWaiver,
    effective_reproducibility_policy,
    load_plan_reproducibility_policy,
)


def test_load_plan_reproducibility_policy_from_frontmatter(tmp_path: Path):
    p = tmp_path / "plan.md"
    p.write_text(
        '---\nid: "plan:x"\ntype: "plan"\ntitle: "X"\n'
        "reproducibility_policy:\n"
        '  bar: "trust-based-output"\n'
        "  waivers:\n"
        '    - dataset: "dataset:n3c"\n'
        '      accepted_class: "trust-based-output"\n'
        '      decision_date: "2026-07-01"\n---\n',
        encoding="utf-8",
    )
    pol = load_plan_reproducibility_policy(p)
    assert pol is not None and pol.bar == "trust-based-output"
    assert pol.waivers[0].dataset == "dataset:n3c"


def test_load_plan_policy_absent_is_none(tmp_path: Path):
    p = tmp_path / "plain.md"
    p.write_text('---\nid: "plan:y"\ntype: "plan"\ntitle: "Y"\n---\n', encoding="utf-8")
    assert load_plan_reproducibility_policy(p) is None


def test_project_config_parses_reproducibility_policy():
    cfg = ProjectConfig.model_validate({
        "name": "demo",
        "reproducibility_policy": {"bar": "credentialed-reproducible", "unknown": "warn"},
    })
    assert cfg.reproducibility_policy.bar == "credentialed-reproducible"
    assert cfg.reproducibility_policy.unknown == "warn"
    assert cfg.reproducibility_policy.below_bar == "halt"  # default


def test_absent_policy_is_none():
    cfg = ProjectConfig.model_validate({"name": "demo"})
    assert cfg.reproducibility_policy is None


def test_effective_policy_plan_overrides_project():
    project = ReproducibilityPolicyConfig(bar="third-party-reproducible")
    plan = PlanReproducibilityPolicy(bar="trust-based-output")
    eff = effective_reproducibility_policy(project, plan)
    assert eff.bar == "trust-based-output"
    assert eff.unknown == "halt"  # inherited from project default


def test_effective_policy_plan_only_opts_in():
    plan = PlanReproducibilityPolicy(bar="third-party-reproducible")
    eff = effective_reproducibility_policy(None, plan)
    assert eff is not None and eff.bar == "third-party-reproducible"


def test_effective_policy_none_when_both_absent():
    assert effective_reproducibility_policy(None, None) is None


def test_waiver_requires_dataset_and_class():
    w = ReproducibilityWaiver(dataset="dataset:x", accepted_class="trust-based-output")
    assert w.dataset == "dataset:x"
```

- [ ] **Step 2: Run tests to verify they fail**

Run from `~/d/science/science/`: `uv run --frozen pytest tests/test_project_config.py -k reproducib -v`
Expected: FAIL with `ImportError: cannot import name 'ReproducibilityPolicyConfig'`.

- [ ] **Step 3: Implement the models + resolver**

In `project_config.py`, add near `DataPolicyConfig` (import `OrdinalReproClass`):

```python
from science_tool.datasets.semantics import OrdinalReproClass


class ReproducibilityPolicyConfig(BaseModel):
    """Project reproducibility gate policy (science.yaml)."""

    model_config = ConfigDict(extra="forbid")

    bar: OrdinalReproClass = "third-party-reproducible"
    unknown: Literal["halt", "warn"] = "halt"
    below_bar: Literal["halt", "warn"] = "halt"


class ReproducibilityWaiver(BaseModel):
    """A dated, scoped plan-level acceptance of one below-bar dataset."""

    model_config = ConfigDict(extra="forbid")

    dataset: str
    accepted_class: OrdinalReproClass
    decision_date: str = ""
    rationale: str = ""
    mitigation: str = ""


class PlanReproducibilityPolicy(BaseModel):
    """Plan-frontmatter reproducibility_policy: bar override + waivers."""

    model_config = ConfigDict(extra="forbid")

    bar: OrdinalReproClass | None = None
    unknown: Literal["halt", "warn"] | None = None
    below_bar: Literal["halt", "warn"] | None = None
    waivers: list[ReproducibilityWaiver] = Field(default_factory=list)


def effective_reproducibility_policy(
    project: ReproducibilityPolicyConfig | None,
    plan: PlanReproducibilityPolicy | None,
) -> ReproducibilityPolicyConfig | None:
    """Merge plan policy over project policy. Returns None only when BOTH are absent."""
    if project is None and plan is None:
        return None
    base = project or ReproducibilityPolicyConfig()
    if plan is None:
        return base
    return ReproducibilityPolicyConfig(
        bar=plan.bar or base.bar,
        unknown=plan.unknown or base.unknown,
        below_bar=plan.below_bar or base.below_bar,
    )


def load_plan_reproducibility_policy(plan_path: Path) -> PlanReproducibilityPolicy | None:
    """Parse a plan file's frontmatter `reproducibility_policy` into a model, or None."""
    result = parse_frontmatter(plan_path)
    if result is None:
        return None
    fm, _ = result
    raw = fm.get("reproducibility_policy")
    if not isinstance(raw, dict):
        return None
    return PlanReproducibilityPolicy.model_validate(raw)
```

Add the field to `ProjectConfig`, beside `data_policy`:

```python
    reproducibility_policy: ReproducibilityPolicyConfig | None = None
```

Confirm `Literal` is imported in `project_config.py`; add it to the `typing` import if missing. Add
`from pathlib import Path` and `from science_model.frontmatter import parse_frontmatter` if not already
present.

- [ ] **Step 4: Run tests to verify they pass**

Run from `~/d/science/science/`: `uv run --frozen pytest tests/test_project_config.py -k "reproducib or plan_policy or plan_reproducibility" -v`
Expected: PASS (8 tests).

- [ ] **Step 5: Format, lint, commit**

```bash
cd ~/d/science/science
uv run --frozen ruff format src/science_tool/project_config.py
uv run --frozen ruff check src/science_tool/project_config.py
git add src/science_tool/project_config.py tests/test_project_config.py
git commit -m "feat(config): reproducibility_policy on project + plan config"
```

---

### Task 4: `check_reproducibility()` gate with derived-input closure

**Files:**
- Modify: `science/src/science_tool/plan_gate.py`
- Test: `science/tests/test_plan_reproducibility_gate.py` (create)

**Interfaces:**
- Consumes: `_load_dataset`, raw frontmatter via `parse_frontmatter`, `reproducibility_class_for`, `repro_meets_bar`, `repro_class_rank`, `ReproducibilityPolicyConfig`, `ReproducibilityWaiver`, `DerivationBlock`.
- Produces:
  - `check_reproducibility(project_root, dataset_ids, *, policy, waivers=None) -> tuple[bool, list[str], list[str]]` → `(pass, halts, warns)`. Every id in `dataset_ids` **is** a declared plan input (the caller passes the declared set); non-input catalog discovery is deferred CLI-surfacing scope, so there is no `declared_inputs` parameter. When `policy is None` and `dataset_ids` is non-empty: returns `(True, [], ["reproducibility-policy-missing: ..."])`.
  - `_effective_repro_class(project_root, ds_id) -> tuple[str, str]` — derived-closure class (weakest external upstream).

- [ ] **Step 1: Write the failing tests**

Create `science/tests/test_plan_reproducibility_gate.py`. Use a tmp-path project builder:

```python
from pathlib import Path

import pytest

from science_tool.plan_gate import check_reproducibility
from science_tool.project_config import ReproducibilityPolicyConfig, ReproducibilityWaiver


def _write_dataset(root: Path, slug: str, reproducibility: dict | None, *, origin="external"):
    d = root / "entities" / "datasets"
    d.mkdir(parents=True, exist_ok=True)
    access = {"level": "controlled", "verified": True}
    if reproducibility is not None:
        access["reproducibility"] = reproducibility
    lines = [
        "---",
        f"id: dataset:{slug}",
        "type: dataset",
        f"title: {slug}",
        f"origin: {origin}",
        "access:",
        f"  level: {access['level']}",
        f"  verified: {str(access['verified']).lower()}",
    ]
    if reproducibility is not None:
        lines.append("  reproducibility:")
        for k, v in reproducibility.items():
            lines.append(f"    {k}: {v}")
    lines += ["---", "", "body", ""]
    (d / f"{slug}.md").write_text("\n".join(lines), encoding="utf-8")


N3C = {"obtainability": "approved-project", "execution": "trusted-environment", "extractability": "aggregate-reviewed"}
OPEN = {"obtainability": "public", "execution": "local", "extractability": "full-dataset"}
BAR = ReproducibilityPolicyConfig(bar="third-party-reproducible", unknown="halt", below_bar="halt")


def test_absent_policy_emits_nudge_no_enforcement(tmp_path):
    _write_dataset(tmp_path, "n3c", N3C)
    ok, halts, warns = check_reproducibility(tmp_path, ["dataset:n3c"], policy=None)
    assert ok is True and halts == []
    assert any("reproducibility-policy-missing" in w for w in warns)


def test_below_bar_halts(tmp_path):
    _write_dataset(tmp_path, "n3c", N3C)
    ok, halts, _ = check_reproducibility(tmp_path, ["dataset:n3c"], policy=BAR)
    assert ok is False and any("trust-based-output" in h for h in halts)


def test_meets_bar_passes(tmp_path):
    _write_dataset(tmp_path, "geo", OPEN)
    ok, halts, _ = check_reproducibility(tmp_path, ["dataset:geo"], policy=BAR)
    assert ok is True and halts == []


def test_unknown_halts_by_default(tmp_path):
    _write_dataset(tmp_path, "bare", None)
    ok, halts, _ = check_reproducibility(tmp_path, ["dataset:bare"], policy=BAR)
    assert ok is False and any("unknown" in h for h in halts)


def test_matching_waiver_passes(tmp_path):
    _write_dataset(tmp_path, "n3c", N3C)
    waiver = ReproducibilityWaiver(dataset="dataset:n3c", accepted_class="trust-based-output")
    ok, halts, _ = check_reproducibility(tmp_path, ["dataset:n3c"], policy=BAR, waivers=[waiver])
    assert ok is True and halts == []


def test_waiver_for_wrong_class_does_not_apply(tmp_path):
    _write_dataset(tmp_path, "n3c", N3C)
    waiver = ReproducibilityWaiver(dataset="dataset:n3c", accepted_class="insider-only")
    ok, halts, _ = check_reproducibility(tmp_path, ["dataset:n3c"], policy=BAR, waivers=[waiver])
    assert ok is False  # derived class is trust-based-output, waiver accepted insider-only
```

- [ ] **Step 2: Run tests to verify they fail**

Run from `~/d/science/science/`: `uv run --frozen pytest tests/test_plan_reproducibility_gate.py -v`
Expected: FAIL with `ImportError: cannot import name 'check_reproducibility'`.

- [ ] **Step 3: Implement the gate**

Add to `plan_gate.py` (imports at top; reuse the existing `_load_dataset`):

```python
from science_model.frontmatter import parse_frontmatter
from science_model.packages.schema import DerivationBlock
from science_tool.datasets.semantics import reproducibility_class_for, repro_meets_bar
from science_tool.project_config import ReproducibilityPolicyConfig, ReproducibilityWaiver


def _load_dataset_fm(project_root: Path, ds_id: str) -> dict:
    slug = ds_id.removeprefix("dataset:")
    md = project_root / "entities" / "datasets" / f"{slug}.md"
    if not md.exists():
        return {}
    result = parse_frontmatter(md)
    return result[0] if result else {}


def _weakest_class(classes: list[tuple[str, str]]) -> tuple[str, str]:
    """Weakest = unknown if any, else lowest lattice rank."""
    if not classes:
        return "unknown", "no upstreams"
    for cls, gap in classes:
        if cls == "unknown":
            return "unknown", gap
    from science_tool.datasets.semantics import repro_class_rank

    return min(classes, key=lambda c: repro_class_rank(c[0]))


def _effective_repro_class(project_root: Path, ds_id: str, _seen: set[str] | None = None) -> tuple[str, str]:
    """Derived-closure class: weakest external upstream for a derived dataset."""
    _seen = _seen or set()
    if ds_id in _seen:
        return "insider-only", "cycle"
    _seen.add(ds_id)
    e = _load_dataset(project_root, ds_id)
    if e is None:
        return "unknown", "missing entity"
    if e.origin == "derived" and isinstance(e.derivation, DerivationBlock):
        upstream_classes = [_effective_repro_class(project_root, up, set(_seen)) for up in e.derivation.inputs]
        return _weakest_class(upstream_classes)
    return reproducibility_class_for(_load_dataset_fm(project_root, ds_id))


def check_reproducibility(
    project_root: Path,
    dataset_ids: list[str],
    *,
    policy: ReproducibilityPolicyConfig | None,
    waivers: list[ReproducibilityWaiver] | None = None,
) -> tuple[bool, list[str], list[str]]:
    """Reproducibility Step-2b enforcement over declared plan inputs.

    Every id in `dataset_ids` is a declared plan input. Returns (pass, halts, warns).
    policy=None => opt-out: nudge, no enforcement.
    """
    waivers = waivers or []
    halts: list[str] = []
    warns: list[str] = []

    if policy is None:
        if dataset_ids:
            warns.append(
                "reproducibility-policy-missing: plan has dataset inputs but no "
                "reproducibility_policy; reproducibility gate not enforced."
            )
        return True, halts, warns

    for ds_id in dataset_ids:
        cls, gap = _effective_repro_class(project_root, ds_id)
        if cls == "unknown":
            msg = f"{ds_id}: reproducibility class unknown ({gap})"
            (halts if policy.unknown == "halt" else warns).append(msg)
            continue
        if repro_meets_bar(cls, policy.bar):
            continue
        waived = any(w.dataset == ds_id and w.accepted_class == cls for w in waivers)
        if waived:
            warns.append(f"{ds_id}: below bar ({cls}) accepted via waiver")
            continue
        msg = f"{ds_id}: reproducibility {cls} below bar {policy.bar} ({gap})"
        (halts if policy.below_bar == "halt" else warns).append(msg)

    return (not halts, halts, warns)
```

- [ ] **Step 4: Run tests to verify they pass**

Run from `~/d/science/science/`: `uv run --frozen pytest tests/test_plan_reproducibility_gate.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Add the derived-closure test**

Append to `test_plan_reproducibility_gate.py`:

A derived dataset needs a **valid** `DerivationBlock` — all six required fields
(`workflow`, `workflow_run`, `git_commit`, `config_snapshot`, `produced_at`, `inputs`) — plus a
matching `workflow-run` entity, or `parse_entity_file` returns `None` and the class silently
collapses to `unknown` (masking the behavior under test). Mirror the repo's existing
`_seed_mixed_inputs` fixture from `tests/test_plan_pipeline_data_gate.py`. Note: `origin: derived`
entities carry `datapackage:` and **must not** carry an `access:` block.

```python
def _write_derived(root: Path, slug: str, upstreams: str | list[str]):
    """Write a VALID origin:derived dataset (full DerivationBlock) + its workflow-run."""
    upstream_slugs = [upstreams] if isinstance(upstreams, str) else upstreams
    upstream_ids = [f"dataset:{upstream}" for upstream in upstream_slugs]
    upstreams_yaml = "[" + ", ".join(f'"{upstream_id}"' for upstream_id in upstream_ids) + "]"
    ds = root / "entities" / "datasets"
    wr = root / "entities" / "workflow-runs"
    ds.mkdir(parents=True, exist_ok=True)
    wr.mkdir(parents=True, exist_ok=True)
    run_slug = f"{slug}-r1"
    (wr / f"{run_slug}.md").write_text(
        f'---\nid: "workflow-run:{run_slug}"\ntype: "workflow-run"\ntitle: "WF {slug}"\n'
        f'workflow: "workflow:wf"\nproduces: ["dataset:{slug}"]\ninputs: {upstreams_yaml}\n---\n',
        encoding="utf-8",
    )
    (ds / f"{slug}.md").write_text(
        f'---\nid: "dataset:{slug}"\ntype: "dataset"\ntitle: "{slug}"\norigin: "derived"\n'
        'datapackage: "results/wf/r1/out/datapackage.yaml"\n'
        "derivation:\n"
        '  workflow: "workflow:wf"\n'
        f'  workflow_run: "workflow-run:{run_slug}"\n'
        '  git_commit: "abc"\n'
        '  config_snapshot: "c"\n'
        '  produced_at: "2026-04-19T00:00:00Z"\n'
        f"  inputs: {upstreams_yaml}\n---\n",
        encoding="utf-8",
    )


def test_derived_input_inherits_weakest_upstream(tmp_path):
    _write_dataset(tmp_path, "n3c", N3C)
    _write_derived(tmp_path, "derived_ok", "n3c")
    ok, halts, _ = check_reproducibility(tmp_path, ["dataset:derived_ok"], policy=BAR)
    assert ok is False and any("trust-based-output" in h for h in halts)


def test_convergent_derived_graph_does_not_treat_shared_upstream_as_cycle(tmp_path):
    _write_dataset(tmp_path, "n3c", N3C)
    _write_derived(tmp_path, "branch_a", "n3c")
    _write_derived(tmp_path, "branch_b", "n3c")
    _write_derived(tmp_path, "merged", ["branch_a", "branch_b"])

    ok, halts, _ = check_reproducibility(tmp_path, ["dataset:merged"], policy=BAR)

    assert ok is False
    assert any("trust-based-output" in h for h in halts)
    assert not any("cycle" in h for h in halts)
```

Run from `~/d/science/science/`: `uv run --frozen pytest tests/test_plan_reproducibility_gate.py -v`
Expected: PASS (8 tests).

- [ ] **Step 6: Format, lint, commit**

```bash
cd ~/d/science/science
uv run --frozen ruff format src/science_tool/plan_gate.py
uv run --frozen ruff check src/science_tool/plan_gate.py
git add src/science_tool/plan_gate.py tests/test_plan_reproducibility_gate.py
git commit -m "feat(gate): enforce reproducibility over derived-input closure with plan waivers"
```

---

### Task 5: Integrated `check_plan_data_gate()` + Step 2b wiring

**Files:**
- Modify: `science/src/science_tool/plan_gate.py` (new combined entry point)
- Modify: `commands/plan-pipeline.md` (Step 2b: Data-access gate)
- Test: `science/tests/test_plan_reproducibility_gate.py` (integration + e2e)

**Interfaces:**
- Consumes: `check_inputs`, `check_reproducibility`, `load_project_config`, `load_plan_reproducibility_policy`, `effective_reproducibility_policy`, `ReproducibilityPolicyConfig`, `ReproducibilityWaiver`.
- Produces:
  - `check_plan_data_gate(project_root, dataset_ids, *, planned_retrieval=None, reproducibility_policy=None, waivers=None) -> tuple[bool, list[str], list[str]]` — runs the existing access gate THEN reproducibility; `halts` is the union. This is the single Step-2b entry point, so a `verified: true` but non-reproducible dataset cannot slip through an access-only check.

Task 4's `check_reproducibility` is standalone; callers of `check_inputs` enforce access **only**. This task composes both into one gate and proves the composition end-to-end, including plan-frontmatter policy/waiver resolution.

- [ ] **Step 1: Write the failing integration + e2e tests**

Append to `test_plan_reproducibility_gate.py`:

```python
from science_tool.plan_gate import check_inputs, check_plan_data_gate
from science_tool.project_config import (
    effective_reproducibility_policy,
    load_plan_reproducibility_policy,
    load_project_config,
)


def test_verified_but_nonreproducible_passes_access_fails_combined(tmp_path):
    _write_dataset(tmp_path, "n3c", N3C)  # access.verified=True, class trust-based-output
    access_ok, _ = check_inputs(tmp_path, ["dataset:n3c"])
    assert access_ok is True  # access gate ALONE passes a verified dataset
    ok, halts, _ = check_plan_data_gate(tmp_path, ["dataset:n3c"], reproducibility_policy=BAR)
    assert ok is False and any("trust-based-output" in h for h in halts)  # combined gate FAILS


def test_combined_gate_passes_when_reproducible(tmp_path):
    _write_dataset(tmp_path, "geo", OPEN)
    ok, halts, _ = check_plan_data_gate(tmp_path, ["dataset:geo"], reproducibility_policy=BAR)
    assert ok is True and halts == []


def test_end_to_end_plan_waiver_from_frontmatter(tmp_path):
    (tmp_path / "science.yaml").write_text(
        "name: demo\nreproducibility_policy:\n  bar: third-party-reproducible\n",
        encoding="utf-8",
    )
    _write_dataset(tmp_path, "n3c", N3C)
    plans = tmp_path / "entities" / "plans"
    plans.mkdir(parents=True)
    (plans / "p.md").write_text(
        '---\nid: "plan:p"\ntype: "plan"\ntitle: "P"\n'
        "reproducibility_policy:\n"
        "  waivers:\n"
        '    - dataset: "dataset:n3c"\n'
        '      accepted_class: "trust-based-output"\n'
        '      decision_date: "2026-07-01"\n'
        '      rationale: "prototype only"\n'
        '      mitigation: "no interpretable estimate"\n---\n',
        encoding="utf-8",
    )
    project_pol = load_project_config(tmp_path).reproducibility_policy
    plan_pol = load_plan_reproducibility_policy(plans / "p.md")
    eff = effective_reproducibility_policy(project_pol, plan_pol)
    ok, halts, warns = check_plan_data_gate(
        tmp_path, ["dataset:n3c"], reproducibility_policy=eff, waivers=plan_pol.waivers
    )
    assert ok is True and halts == []           # waiver rescues the below-bar input
    assert any("waiver" in w for w in warns)
```

- [ ] **Step 2: Run to verify they fail**

Run from `~/d/science/science/`: `uv run --frozen pytest tests/test_plan_reproducibility_gate.py -k "combined or end_to_end" -v`
Expected: FAIL with `ImportError: cannot import name 'check_plan_data_gate'`.

- [ ] **Step 3: Implement the combined gate**

Add to `plan_gate.py`:

```python
def check_plan_data_gate(
    project_root: Path,
    dataset_ids: list[str],
    *,
    planned_retrieval: set[str] | None = None,
    reproducibility_policy: ReproducibilityPolicyConfig | None = None,
    waivers: list[ReproducibilityWaiver] | None = None,
) -> tuple[bool, list[str], list[str]]:
    """Single Step-2b gate: existing access checks THEN reproducibility enforcement.

    `halts` is the union of access + reproducibility halts. This is the entry point
    Step 2b uses, so a verified-but-non-reproducible input cannot pass an access-only path.
    """
    access_ok, access_halts = check_inputs(project_root, dataset_ids, planned_retrieval=planned_retrieval)
    repro_ok, repro_halts, warns = check_reproducibility(
        project_root, dataset_ids, policy=reproducibility_policy, waivers=waivers
    )
    return (access_ok and repro_ok, access_halts + repro_halts, warns)
```

- [ ] **Step 4: Run to verify they pass**

Run from `~/d/science/science/`: `uv run --frozen pytest tests/test_plan_reproducibility_gate.py -v`
Expected: PASS (10 tests total).

- [ ] **Step 5: Wire the Step 2b prose to the combined gate**

In `commands/plan-pipeline.md`, inside "Step 2b: Data-access gate", after the origin `external`/`derived` bullets, add:

```markdown
3. **Reproducibility gate (transparency-bound plans).** Step 2b runs the combined
   `check_plan_data_gate` — the access checks above **then** reproducibility enforcement. Resolve
   the effective `reproducibility_policy` (plan frontmatter merged over `science.yaml`, plan wins).
   - If **neither** project nor plan declares a policy: emit `reproducibility-policy-missing` as a
     WARN and do not enforce.
   - Otherwise, for each declared dataset input, derive its class over the transitive
     external-input closure (derived inputs inherit the weakest upstream class):
     - `class: unknown` → resolve by `policy.unknown` (default HALT).
     - class ≥ `policy.bar` → PASS (surface class + gap_reason).
     - class < `bar` with a matching plan waiver (same dataset **and** `accepted_class == derived class`)
       → PASS-with-recorded-exception.
     - class < `bar` with no matching waiver → resolve by `policy.below_bar` (default HALT).
```

- [ ] **Step 6: Full suites green + lint**

```bash
cd ~/d/science/science && uv run --frozen pytest -q
cd ~/d/science/science/model && uv run --frozen pytest -q
cd ~/d/science && uv run --directory science ruff check src/science_tool && uv run --directory science/model ruff check src/science_model
```
Expected: PASS both suites (tool default `-m 'not snapshot and not real_projects'`); no lint errors.

- [ ] **Step 7: Format + commit**

```bash
cd ~/d/science/science && uv run --frozen ruff format src/science_tool/plan_gate.py
cd ~/d/science
git add science/src/science_tool/plan_gate.py science/tests/test_plan_reproducibility_gate.py commands/plan-pipeline.md
git commit -m "feat(gate): integrated check_plan_data_gate (access + reproducibility) + Step 2b"
```

---

### Task 6: Author-facing template + user guide

**Files:**
- Modify: `templates/dataset.md`
- Modify: `docs/user-guide/entities.md`

**Interfaces:**
- Consumes: the enum names + classes finalized in Tasks 1–2. No code.

- [ ] **Step 1: Add the block to the dataset template**

In `templates/dataset.md`, inside the `access:` block, after the `exception:` sub-block, add:

```yaml
  reproducibility:                # can an INDEPENDENT party regenerate the analysis?
    obtainability: unknown        # public | registration | self-service-dua | approved-researcher | approved-project | named-collaboration | unavailable | unknown
    execution: unknown            # local | hosted-workspace | trusted-environment | federated-code-to-data | custodian-run | unknown
    extractability: unknown       # full-dataset | analysis-dataset | synthetic-dataset | aggregate-unreviewed | aggregate-reviewed | none | unknown
    notes: ""                     # free-form, e.g. "Only reviewed aggregates leave the enclave."
```

- [ ] **Step 2: Add an authoring section to the user guide**

In `docs/user-guide/entities.md`, near the dataset `access:` documentation, add a subsection:

```markdown
#### Reproducibility (`access.reproducibility`)

`access.level` says *how gated the source is*; `access.reproducibility` says *whether an
independent third party can regenerate the analysis*. Three controls, mapped to the
[Five Safes](https://fivesafes.org/):

- `obtainability` — safe people/projects (who can get in).
- `execution` — safe setting (where compute runs).
- `extractability` — safe outputs (what can leave).

The **class** is derived, never stored: `third-party-reproducible` > `credentialed-reproducible`
> `trust-based-output` > `insider-only`; `unknown` is unassessed (not "low"). Worked examples:

| Dataset shape | obtainability / execution / extractability | class |
|---|---|---|
| Public GEO download | public / local / full-dataset | third-party-reproducible |
| Self-serve DUA extract | self-service-dua / local / analysis-dataset | credentialed-reproducible |
| N3C / OpenSAFELY enclave | approved-project / trusted-environment / aggregate-reviewed | trust-based-output |

A transparency-bound project sets `reproducibility_policy` in `science.yaml`; a plan may lower the
bar or waive one dataset explicitly (dated, scoped, with rationale + mitigation).
```

- [ ] **Step 3: Verify the template still parses**

Run from `~/d/science/science/`: `uv run --frozen pytest tests/test_datasets_schema.py -q` (the schema/template test suite).
Expected: PASS. If the template is not covered by a test, manually confirm `AccessReproducibility(**{"obtainability":"unknown","execution":"unknown","extractability":"unknown"})` constructs without error.

- [ ] **Step 4: Commit**

```bash
cd ~/d/science
git add templates/dataset.md docs/user-guide/entities.md
git commit -m "docs: author-facing reproducibility block in dataset template + user guide"
```

---

## Self-Review

**Spec coverage:**
- `access.reproducibility` block + enums + real `parse_entity_file` coercion test + JSON-permissive decision → Task 1. ✓
- Derived `reproducibility_class_for()` + gap_reason + lattice + insider-before-trust-based + row-6 fail-safe + absent-block→unknown → Task 2. ✓
- `reproducibility_policy` (project + plan, plan-over-project, plan-only opt-in) + waivers + plan-frontmatter loader → Task 3. ✓
- Enforcement (unknown/meets-bar/below-bar/waiver/derived-closure/absent-policy nudge) → Task 4. ✓
- **Integrated `check_plan_data_gate` (access THEN reproducibility)** + end-to-end plan-frontmatter waiver resolution + Step 2b prose + no-regression → Task 5. ✓
- Template + user-guide authoring → Task 6. ✓

**Review findings closed (this revision):**
- Wiring gap: Task 5 adds `check_plan_data_gate` and a test proving a verified-but-non-reproducible dataset passes access yet fails the combined gate. ✓
- Plan-frontmatter never parsed: Task 3 adds `load_plan_reproducibility_policy`; Task 5's e2e test drives it from a real `science.yaml` + plan `.md`. ✓
- Invalid derived fixture: Task 4 now writes a full six-field `DerivationBlock` + matching workflow-run, mirroring `_seed_mixed_inputs`. ✓
- JSON-schema surfaces: Task 1 Step 6 documents the permissive decision + a confirming `EntityValidator` test. ✓
- Fake coercion test: replaced with a `parse_entity_file` round-trip (Task 1 Step 5). ✓
- Unused `declared_inputs`: removed from `check_reproducibility` (Task 4). ✓

**Placeholder scan:** No TBD/TODO; every code step shows full code; every run step shows command + expected result.

**Type consistency:** `ReproClass`/`OrdinalReproClass` defined in Task 2, imported by Tasks 3–5. `check_reproducibility` returns `(bool, list, list)`; `check_plan_data_gate` returns the same shape and unions the halt lists. `reproducibility_class_for` returns `(class, gap)` everywhere. `ReproducibilityPolicyConfig`/`ReproducibilityWaiver`/`PlanReproducibilityPolicy`/`effective_reproducibility_policy`/`load_plan_reproducibility_policy` names match across Tasks 3–5.

**Notes for the implementer:**
- `check_plan_data_gate` (Task 5) is the single Step-2b entry point (access **then** reproducibility); `check_reproducibility` (Task 4) is the reproducibility half, reusable in isolation.
- The classifier reads **raw frontmatter dicts** (like `runtime_state_for`), while the Pydantic block enforces enums at parse time — two surfaces, intentionally.
- `origin: derived` datasets carry `datapackage:` and must **not** carry `access:`; their reproducibility class comes from the transitive external-input closure.
- If `science/tests/test_project_config.py` already exists, append; otherwise create it with the tool-suite import style.

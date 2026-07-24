# Skill-Coverage Enrollment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the closed `skill_coverage` enrollment declaration to `science.yaml`, owned by a single closed domain vocabulary in `science-model`, with the cross-field rule that enrolling a capability-reading domain requires `entity_schema_version: 3`.

**Architecture:** `science-model` owns the closed domain vocabulary AND the enrollment-status type (the single authority for both). `science_tool`'s `ProjectConfig` gains a typed, closed `skill_coverage` block that imports both, rejects unknown domain keys, rejects null and structurally incomplete declarations, and enforces `enrolled ⇒ generation 3`. A read helper (`domain_enrollment`) resolves each domain to `enrolled` / `out-of-domain` / `undeclared` for the future coverage command. No `science.yaml` field is inferred: absence always means `undeclared`, never `out-of-domain`, and an authored-but-malformed declaration fails loudly rather than collapsing to `undeclared`.

**Tech Stack:** Python, Pydantic v2, pytest, uv.

This is **sub-plan 1** of Plan 2 (the skill-coverage layer). It follows the approved design `docs/plans/2026-07-23-data-product-vocabulary-and-skill-coverage-design.md` (Rev 4), specifically the "Enrollment as a closed declaration" section and its invariants. Plan 1 (the data-product vocabulary + gen-3 schema foundation) is already merged to local main. This sub-plan touches **only** enrollment config — not the write-path gap, `skills_loaded`, the overlay, or the coverage command (each a later sub-plan).

## Global Constraints

- **Single authority for BOTH the domain keys and the status values:** the closed set of domain keys AND the enrollment-status type live in `science-model` (`science_model.skill_coverage`); `science_tool` imports them and never re-declares either. Copied verbatim from the design invariant: "Domain keys are drawn from a **closed vocabulary** with a single registered authority (the coverage module in `science-model`)." A status literal hard-coded a second time in `science_tool` is exactly the drift this forbids.
- **Value carries status:** each domain maps to a value in `{enrolled, out-of-domain}`; the `out-of-domain` sentinel is a value, never a domain key.
- **Absence = `undeclared`:** absence of the `skill_coverage` block, or of a given domain key within it, means `undeclared` for that domain — **never** inferred as `out-of-domain`.
- **Malformed = hard failure, never `undeclared`:** an authored declaration that is `null`, or a block missing its `domains` mapping, is a config error — it must **not** collapse into the same state as absence. `skill_coverage: {domains: {}}` is the way to declare an intentionally empty block.
- **Unknown domain key = hard config error;** the block is closed (`extra="forbid"` — only `domains:` is permitted inside it).
- **Cross-field rule:** a domain that is `enrolled` **and** reads the generation-3 capability shape (`molecular-measurement`) requires `entity_schema_version: 3`; enrolling it without the gen-3 pin is a **config validation error**.
- Project rules: composition over inheritance; explicit over defensive; fail early instead of silent fallbacks; no legacy/compatibility layers; no `Unified` prefix; no AI-attribution trailers on commits.
- **Test commands:** `science_tool` tests run from `science/` (`uv run --frozen pytest`); `science-model` tests run from `science/model/` (`cd science/model && uv run --frozen pytest`). Lint from the package you changed (`uv run ruff check`); types via `uv run pyright` from `science/`.

## File Structure

- **Create** `science/model/src/science_model/skill_coverage/__init__.py` — the closed domain vocabulary + `EnrollmentStatus` type (constants + one StrEnum). Single responsibility: name the domains and the enrollment statuses, and mark which domains require generation 3.
- **Create** `science/model/tests/test_skill_coverage_vocab.py` — vocab consistency tests.
- **Modify** `science/src/science_tool/project_config.py` — add `SkillCoverageConfig`, the `skill_coverage` field on `ProjectConfig`, the null-rejection before-validator, the cross-field after-validator, and the `domain_enrollment` read helper.
- **Modify** `science/tests/test_project_config.py` — enrollment parse / validation / helper tests, including end-to-end YAML through `load_project_config`.

## Documentation deferral (explicit)

The user-facing conventions/manual entry for the `skill_coverage` block is **assigned to sub-plan 4 (the `science skills coverage` command)**, not written here. Rationale: enrollment is inert until the coverage command consumes it, there is no project-config conventions doc today to extend, and documenting the field beside the command it feeds avoids a stub that predates its own meaning. The field is fully validated and tested here; only its prose home is deferred, and it is named to a specific later sub-plan rather than left open.

---

### Task 1: Closed domain vocabulary + `EnrollmentStatus` type in `science-model`

**Files:**
- Create: `science/model/src/science_model/skill_coverage/__init__.py`
- Test: `science/model/tests/test_skill_coverage_vocab.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `science_model.skill_coverage.EnrollmentStatus` — a `StrEnum` with members `ENROLLED = "enrolled"` and `OUT_OF_DOMAIN = "out-of-domain"`. This is the SOLE definition of the status vocabulary; `science_tool` consumes it directly rather than re-spelling a `Literal`.
  - `science_model.skill_coverage.DOMAIN_KEYS: frozenset[str]` — the closed set of enrollable domain keys (v1: exactly `{"molecular-measurement"}`).
  - `science_model.skill_coverage.ENROLLMENT_STATUSES: frozenset[str]` — **derived from** `EnrollmentStatus`, never hand-listed.
  - `science_model.skill_coverage.GENERATION_3_DOMAINS: frozenset[str]` — domains whose coverage analysis reads the gen-3 capability shape and therefore require `entity_schema_version: 3` when enrolled (v1: `{"molecular-measurement"}`); a subset of `DOMAIN_KEYS`.

- [ ] **Step 1: Write the failing test**

Create `science/model/tests/test_skill_coverage_vocab.py`:

```python
from science_model.skill_coverage import (
    DOMAIN_KEYS,
    ENROLLMENT_STATUSES,
    GENERATION_3_DOMAINS,
    EnrollmentStatus,
)


def test_domain_keys_are_exactly_the_v1_set():
    # Exact equality, not membership: the closed set is the contract, and a silently-added key
    # would change coverage behavior without a test noticing.
    assert DOMAIN_KEYS == frozenset({"molecular-measurement"})


def test_enrollment_status_members():
    assert EnrollmentStatus.ENROLLED == "enrolled"
    assert EnrollmentStatus.OUT_OF_DOMAIN == "out-of-domain"


def test_enrollment_statuses_are_derived_from_the_enum():
    # The set constant must track the enum -- not a second, drift-prone hand-list.
    assert ENROLLMENT_STATUSES == frozenset(status.value for status in EnrollmentStatus)


def test_generation_3_domains_are_a_subset_of_domain_keys():
    assert GENERATION_3_DOMAINS <= DOMAIN_KEYS


def test_molecular_measurement_requires_generation_3():
    assert "molecular-measurement" in GENERATION_3_DOMAINS
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science/model && uv run --frozen pytest tests/test_skill_coverage_vocab.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'science_model.skill_coverage'`.

- [ ] **Step 3: Write minimal implementation**

Create `science/model/src/science_model/skill_coverage/__init__.py`:

```python
"""The closed vocabulary of skill-coverage enrollment domains and statuses.

This module is the SINGLE authority on which domains a project may enroll in for skill-coverage
analysis AND on the enrollment-status values. `science_tool`'s project config imports these and never
re-declares them: a status or domain that is legal here and nowhere else is what "one registered
authority" means. Adding a domain is a change here (and, if it reads the generation-3 capability
shape, in GENERATION_3_DOMAINS); the two status values live only in EnrollmentStatus.
"""

from __future__ import annotations

from enum import StrEnum


class EnrollmentStatus(StrEnum):
    """The two authored enrollment statuses. `undeclared` is NOT here: it is an ABSENCE state, never
    an authored value, so it is resolved by the reader, not selected in science.yaml."""

    ENROLLED = "enrolled"
    OUT_OF_DOMAIN = "out-of-domain"


# Enrollable domain keys. Closed: a `skill_coverage.domains` key outside this set is a hard config
# error, never a silently-preserved unknown. v1 ships exactly the molecular-measurement domain.
DOMAIN_KEYS: frozenset[str] = frozenset({"molecular-measurement"})

# The enrollment status VALUES, DERIVED from EnrollmentStatus so the set can never drift from the
# type. Consumers that need the values as a set read this; consumers that validate a field type read
# EnrollmentStatus directly.
ENROLLMENT_STATUSES: frozenset[str] = frozenset(status.value for status in EnrollmentStatus)

# Domains whose coverage analysis reads the generation-3 capability shape. Enrolling one of these
# requires the project to be pinned `entity_schema_version: 3`; the cross-field rule that enforces
# this lives with the config that also owns the pin (science_tool ProjectConfig). Subset of
# DOMAIN_KEYS by construction.
GENERATION_3_DOMAINS: frozenset[str] = frozenset({"molecular-measurement"})

__all__ = ["DOMAIN_KEYS", "ENROLLMENT_STATUSES", "GENERATION_3_DOMAINS", "EnrollmentStatus"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science/model && uv run --frozen pytest tests/test_skill_coverage_vocab.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add science/model/src/science_model/skill_coverage/__init__.py science/model/tests/test_skill_coverage_vocab.py
git commit -m "feat(model): add closed skill-coverage domain vocabulary and status type"
```

---

### Task 2: `SkillCoverageConfig` block + `skill_coverage` field, with malformed-declaration rejection

**Files:**
- Modify: `science/src/science_tool/project_config.py`
- Test: `science/tests/test_project_config.py`

**Interfaces:**
- Consumes: `science_model.skill_coverage.DOMAIN_KEYS`, `EnrollmentStatus` (Task 1).
- Produces:
  - `SkillCoverageConfig` — closed Pydantic model (`extra="forbid"`) with a **required** `domains: dict[str, EnrollmentStatus]` (no default; a block without `domains` is an error); a field validator rejecting any key not in `DOMAIN_KEYS`.
  - `ProjectConfig.skill_coverage: SkillCoverageConfig | None = None` (`None` reachable only via absence — see the null-rejection validator).
  - A `model_validator(mode="before")` on `ProjectConfig` rejecting an explicit `skill_coverage: null`.

**Notes for the implementer:**
- `project_config.py` already imports `Literal`, `BaseModel`, `ConfigDict`, `Field`, and `model_validator`. Add `field_validator` to the `pydantic` import line. Add `from science_model.skill_coverage import DOMAIN_KEYS, EnrollmentStatus` near the other `science_model` imports.
- `ProjectConfig` sets `model_config = ConfigDict(extra="allow")` and already has `reject_near_miss_keys`, so declaring the `skill_coverage` field automatically makes a mistyped `skill_coverge:` a near-miss error — no extra work for that.
- **Test-import discipline:** `science/tests/test_project_config.py` already imports `Path`, `pytest`, `ValidationError`, `ProjectConfig`, and `load_project_config` at the top. Do **not** add mid-file imports. Extend the existing `from science_tool.project_config import (...)` block to also import `SkillCoverageConfig` (and, in later tasks, `domain_enrollment`).

- [ ] **Step 1: Write the failing test**

Fold `SkillCoverageConfig` into the existing top-of-file `from science_tool.project_config import (...)` block, then add these tests to `science/tests/test_project_config.py`:

```python
def test_skill_coverage_absent_leaves_field_none():
    config = ProjectConfig.model_validate({"name": "demo"})
    assert config.skill_coverage is None


def test_skill_coverage_null_is_rejected():
    # Authored null must NOT collapse to the absence state (undeclared).
    with pytest.raises(ValidationError, match="present but null"):
        ProjectConfig.model_validate({"name": "demo", "skill_coverage": None})


def test_skill_coverage_block_without_domains_is_rejected():
    # An empty block `{}` is a malformed declaration -- `domains` is required.
    with pytest.raises(ValidationError):
        ProjectConfig.model_validate({"name": "demo", "skill_coverage": {}})


def test_skill_coverage_intentional_empty_domains_is_accepted():
    # The way to declare an intentionally empty block: domains present but empty.
    config = ProjectConfig.model_validate(
        {"name": "demo", "skill_coverage": {"domains": {}}}
    )
    assert config.skill_coverage is not None
    assert config.skill_coverage.domains == {}


def test_skill_coverage_parses_enrolled_domain():
    config = ProjectConfig.model_validate(
        {
            "name": "demo",
            "entity_schema_version": 3,
            "skill_coverage": {"domains": {"molecular-measurement": "enrolled"}},
        }
    )
    assert isinstance(config.skill_coverage, SkillCoverageConfig)
    assert config.skill_coverage.domains == {"molecular-measurement": EnrollmentStatus.ENROLLED}


def test_skill_coverage_rejects_unknown_domain_key():
    with pytest.raises(ValidationError, match="unknown domain key"):
        ProjectConfig.model_validate(
            {
                "name": "demo",
                "entity_schema_version": 3,
                "skill_coverage": {"domains": {"proteomics-measurement": "enrolled"}},
            }
        )


def test_skill_coverage_rejects_unknown_status_value():
    with pytest.raises(ValidationError):
        ProjectConfig.model_validate(
            {
                "name": "demo",
                "entity_schema_version": 3,
                "skill_coverage": {"domains": {"molecular-measurement": "maybe"}},
            }
        )


def test_skill_coverage_block_is_closed():
    with pytest.raises(ValidationError):
        ProjectConfig.model_validate(
            {
                "name": "demo",
                "entity_schema_version": 3,
                "skill_coverage": {
                    "domains": {"molecular-measurement": "enrolled"},
                    "notes": "oops",
                },
            }
        )
```

Import `EnrollmentStatus` directly from `science_model.skill_coverage` at the top of `test_project_config.py` (add one line to the existing import group).

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_project_config.py -k skill_coverage -v`
Expected: FAIL with `ImportError: cannot import name 'SkillCoverageConfig'`.

- [ ] **Step 3: Write minimal implementation**

In `science/src/science_tool/project_config.py`:

1. Change the pydantic import line to include `field_validator`:

```python
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
```

2. Add the vocabulary import near the other `science_model` imports:

```python
from science_model.skill_coverage import DOMAIN_KEYS, EnrollmentStatus
```

3. Add the `SkillCoverageConfig` model immediately **above** the `class ProjectConfig(BaseModel):` definition:

```python
class SkillCoverageConfig(BaseModel):
    """The `skill_coverage:` block of science.yaml -- a CLOSED enrollment declaration.

    `domains` maps a closed domain key to its enrollment STATUS as the value. `domains` is REQUIRED:
    a block present without it is malformed, not an empty declaration -- an intentionally empty block
    is `{domains: {}}`. Absence of a KEY within `domains` means `undeclared` for that domain, never
    `out-of-domain` (an explicit value a project must author). The block is closed (`extra="forbid"`):
    the only key inside it is `domains`.
    """

    model_config = ConfigDict(extra="forbid")

    domains: dict[str, EnrollmentStatus]

    @field_validator("domains")
    @classmethod
    def _known_domains(cls, value: dict[str, EnrollmentStatus]) -> dict[str, EnrollmentStatus]:
        unknown = sorted(set(value) - DOMAIN_KEYS)
        if unknown:
            raise ValueError(
                f"skill_coverage.domains has unknown domain key(s) {unknown!r}; "
                f"known domains: {sorted(DOMAIN_KEYS)}. An unknown domain is refused rather than "
                "preserved: a misnamed domain would silently drop a project out of coverage."
            )
        return value
```

4. Add the field to `ProjectConfig`, next to the other optional-config fields (e.g. right after `reproducibility_policy`):

```python
    skill_coverage: SkillCoverageConfig | None = None
```

5. Add a `model_validator(mode="before")` to `ProjectConfig` (alongside the existing `_reject_removed_fields` / `_reject_near_miss_keys` before-validators) that refuses an explicit null:

```python
    @model_validator(mode="before")
    @classmethod
    def _reject_null_skill_coverage(cls, raw: Any) -> Any:
        if isinstance(raw, dict) and "skill_coverage" in raw and raw["skill_coverage"] is None:
            raise ValueError(
                "science.yaml: skill_coverage is present but null. An authored-but-empty declaration "
                "is `skill_coverage: {domains: {}}`, not null -- null would collapse to the same state "
                "as absence (undeclared), hiding a malformed declaration."
            )
        return raw
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science && uv run --frozen pytest tests/test_project_config.py -k skill_coverage -v`
Expected: PASS (8 tests).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/project_config.py science/tests/test_project_config.py
git commit -m "feat(config): parse the closed skill_coverage block; reject malformed declarations"
```

---

### Task 3: Cross-field rule — `enrolled` capability-reading domain requires generation 3

**Files:**
- Modify: `science/src/science_tool/project_config.py`
- Test: `science/tests/test_project_config.py`

**Interfaces:**
- Consumes: `science_model.skill_coverage.GENERATION_3_DOMAINS`, `EnrollmentStatus` (Task 1); `ProjectConfig.skill_coverage` (Task 2); `ProjectConfig.entity_schema_version` (existing).
- Produces: a `model_validator(mode="after")` on `ProjectConfig` enforcing the rule.

**Notes for the implementer:** `entity_schema_version` is `Literal[1, 2, 3] | None`; absence is `None`. The rule requires the pin to be exactly `3`. Only domains that are BOTH `EnrollmentStatus.ENROLLED` AND in `GENERATION_3_DOMAINS` trigger it — an `out-of-domain` declaration never requires a pin. Add `GENERATION_3_DOMAINS` to the existing `from science_model.skill_coverage import ...` line from Task 2.

- [ ] **Step 1: Add integration/regression tests**

Add to `science/tests/test_project_config.py`:

```python
def test_enrolled_domain_requires_generation_3():
    with pytest.raises(ValidationError, match="entity_schema_version: 3"):
        ProjectConfig.model_validate(
            {
                "name": "demo",
                "entity_schema_version": 2,
                "skill_coverage": {"domains": {"molecular-measurement": "enrolled"}},
            }
        )


def test_enrolled_domain_without_any_pin_is_rejected():
    # Absent pin == generation 1; enrolling a gen-3 domain still requires the explicit 3.
    with pytest.raises(ValidationError, match="entity_schema_version: 3"):
        ProjectConfig.model_validate(
            {
                "name": "demo",
                "skill_coverage": {"domains": {"molecular-measurement": "enrolled"}},
            }
        )


def test_enrolled_domain_with_generation_3_is_accepted():
    config = ProjectConfig.model_validate(
        {
            "name": "demo",
            "entity_schema_version": 3,
            "skill_coverage": {"domains": {"molecular-measurement": "enrolled"}},
        }
    )
    assert config.entity_schema_version == 3


def test_out_of_domain_does_not_require_generation_3():
    # A project can declare itself out-of-domain without migrating to generation 3.
    config = ProjectConfig.model_validate(
        {
            "name": "demo",
            "skill_coverage": {"domains": {"molecular-measurement": "out-of-domain"}},
        }
    )
    assert config.skill_coverage.domains == {"molecular-measurement": EnrollmentStatus.OUT_OF_DOMAIN}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_project_config.py -k "generation_3 or out_of_domain" -v`
Expected: FAIL — the two `pytest.raises` tests fail because no error is raised (the rule does not exist yet).

- [ ] **Step 3: Write minimal implementation**

Extend the Task-2 import to include `GENERATION_3_DOMAINS`:

```python
from science_model.skill_coverage import DOMAIN_KEYS, GENERATION_3_DOMAINS, EnrollmentStatus
```

Add a `model_validator(mode="after")` inside `ProjectConfig` (after the existing `mode="before"` validators):

```python
    @model_validator(mode="after")
    def _enrolled_requires_generation_3(self) -> ProjectConfig:
        coverage = self.skill_coverage
        if coverage is None:
            return self
        needs_generation_3 = sorted(
            domain
            for domain, status in coverage.domains.items()
            if status is EnrollmentStatus.ENROLLED and domain in GENERATION_3_DOMAINS
        )
        if needs_generation_3 and self.entity_schema_version != 3:
            raise ValueError(
                f"skill_coverage: domain(s) {needs_generation_3!r} are enrolled but require "
                f"entity_schema_version: 3 (currently {self.entity_schema_version!r}). Coverage reads "
                "the generation-3 capability shape, so enrolling without the gen-3 pin is refused "
                "rather than run against a shape the project does not speak."
            )
        return self
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science && uv run --frozen pytest tests/test_project_config.py -k "generation_3 or out_of_domain" -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/project_config.py science/tests/test_project_config.py
git commit -m "feat(config): require generation 3 when enrolling a capability-reading domain"
```

---

### Task 4: `domain_enrollment` read helper

**Files:**
- Modify: `science/src/science_tool/project_config.py`
- Test: `science/tests/test_project_config.py`

**Interfaces:**
- Consumes: `ProjectConfig.skill_coverage` (Task 2); `science_model.skill_coverage.DOMAIN_KEYS`, `EnrollmentStatus` (Task 1).
- Produces: `domain_enrollment(config: ProjectConfig, domain: str) -> EnrollmentStatus | Literal["undeclared"]` — the resolution the future `science skills coverage` portfolio scan reads per project. Absence of the block or of the key resolves to `"undeclared"`. A `domain` argument outside `DOMAIN_KEYS` is a programming error (`ValueError`), not `"undeclared"`.

**Notes for the implementer:** fold `domain_enrollment` into the existing top-of-file import block of `test_project_config.py` — no mid-file import.

- [ ] **Step 1: Write the failing test**

Add to `science/tests/test_project_config.py`:

```python
def test_domain_enrollment_undeclared_when_block_absent():
    config = ProjectConfig.model_validate({"name": "demo"})
    assert domain_enrollment(config, "molecular-measurement") == "undeclared"


def test_domain_enrollment_undeclared_when_key_absent():
    config = ProjectConfig.model_validate(
        {"name": "demo", "skill_coverage": {"domains": {}}}
    )
    assert domain_enrollment(config, "molecular-measurement") == "undeclared"


def test_domain_enrollment_returns_declared_status():
    config = ProjectConfig.model_validate(
        {
            "name": "demo",
            "entity_schema_version": 3,
            "skill_coverage": {"domains": {"molecular-measurement": "enrolled"}},
        }
    )
    assert domain_enrollment(config, "molecular-measurement") is EnrollmentStatus.ENROLLED


def test_domain_enrollment_rejects_unknown_domain_argument():
    config = ProjectConfig.model_validate({"name": "demo"})
    with pytest.raises(ValueError, match="unknown skill-coverage domain"):
        domain_enrollment(config, "proteomics-measurement")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_project_config.py -k domain_enrollment -v`
Expected: FAIL with `ImportError: cannot import name 'domain_enrollment'`.

- [ ] **Step 3: Write minimal implementation**

Add a module-level function in `science/src/science_tool/project_config.py` (near `load_project_config`):

```python
def domain_enrollment(
    config: ProjectConfig, domain: str
) -> EnrollmentStatus | Literal["undeclared"]:
    """Resolve a project's enrollment status for one coverage domain.

    Absence of the `skill_coverage` block, or of this domain key within it, is `undeclared` -- never
    `out-of-domain`, which a project must author explicitly. A `domain` outside the closed vocabulary
    is a programming error at the call site, not a project state, so it raises rather than returning
    `undeclared`.
    """
    if domain not in DOMAIN_KEYS:
        raise ValueError(
            f"unknown skill-coverage domain {domain!r}; known domains: {sorted(DOMAIN_KEYS)}"
        )
    if config.skill_coverage is None:
        return "undeclared"
    status = config.skill_coverage.domains.get(domain)
    if status is None:
        return "undeclared"
    return status
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science && uv run --frozen pytest tests/test_project_config.py -k domain_enrollment -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/project_config.py science/tests/test_project_config.py
git commit -m "feat(config): add domain_enrollment status resolver"
```

---

### Task 5: End-to-end YAML boundary tests + full verification gate

**Files:**
- Test: `science/tests/test_project_config.py`

**Interfaces:**
- Consumes: `load_project_config` (existing), all of Tasks 1–4.
- Produces: tests exercising the **real** public surface (YAML → `load_project_config`), not just `model_validate` on dicts.

**Notes for the implementer:** `load_project_config(project_root)` reads `science.yaml` under `project_root` and calls `ProjectConfig.model_validate`. Mirror the existing `test_loads_minimal_existing_yaml` style: create `project_root = tmp_path / "<name>"`, `project_root.mkdir()`, write `science.yaml`, then call `load_project_config(project_root)`. `load_project_config`, `pytest`, `ValidationError`, and `Path` are already imported at the top of the test file.

- [ ] **Step 1: Write the failing test**

Add to `science/tests/test_project_config.py`:

```python
def _write_yaml(project_root: Path, body: str) -> None:
    project_root.mkdir()
    (project_root / "science.yaml").write_text(body, encoding="utf-8")


def test_yaml_enrolled_domain_loads(tmp_path: Path) -> None:
    root = tmp_path / "enrolled"
    _write_yaml(
        root,
        "name: enrolled\n"
        "entity_schema_version: 3\n"
        "skill_coverage:\n"
        "  domains:\n"
        "    molecular-measurement: enrolled\n",
    )
    config = load_project_config(root)
    assert domain_enrollment(config, "molecular-measurement") is EnrollmentStatus.ENROLLED


def test_yaml_out_of_domain_loads(tmp_path: Path) -> None:
    root = tmp_path / "outofdomain"
    _write_yaml(
        root,
        "name: outofdomain\n"
        "skill_coverage:\n"
        "  domains:\n"
        "    molecular-measurement: out-of-domain\n",
    )
    config = load_project_config(root)
    assert domain_enrollment(config, "molecular-measurement") is EnrollmentStatus.OUT_OF_DOMAIN


def test_yaml_absent_block_is_undeclared(tmp_path: Path) -> None:
    root = tmp_path / "absent"
    _write_yaml(root, "name: absent\n")
    config = load_project_config(root)
    assert config.skill_coverage is None
    assert domain_enrollment(config, "molecular-measurement") == "undeclared"


def test_yaml_null_block_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "nullblock"
    _write_yaml(root, "name: nullblock\nskill_coverage:\n")  # `skill_coverage:` with no value == null
    with pytest.raises(ValidationError, match="present but null"):
        load_project_config(root)


def test_yaml_unknown_domain_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "unknowndomain"
    _write_yaml(
        root,
        "name: unknowndomain\n"
        "entity_schema_version: 3\n"
        "skill_coverage:\n"
        "  domains:\n"
        "    proteomics-measurement: enrolled\n",
    )
    with pytest.raises(ValidationError, match="unknown domain key"):
        load_project_config(root)
```

- [ ] **Step 2: Run the integration/regression tests**

Run: `cd science && uv run --frozen pytest tests/test_project_config.py -k yaml -v`
Expected: all five YAML tests PASS immediately — the behavior they assert was built in Tasks 1–4; this task adds coverage of the real load path. (If any fails, it exposes a boundary gap in an earlier task — fix there, not by loosening the test.)

- [ ] **Step 3: Full verification — both package suites, lint, and types**

```bash
cd science/model
uv run --frozen pytest
uv run ruff check

cd ..
uv run --frozen pytest
uv run ruff check
uv run pyright
```

Expected: all green. (`cd ..` moves from `science/model` back to `science/`.)

- [ ] **Step 4: Commit**

```bash
git add science/tests/test_project_config.py
git commit -m "test(config): cover the skill_coverage YAML load boundary end-to-end"
```

---

## Self-Review

- **Spec coverage.** Design "Enrollment as a closed declaration" requirements → tasks:
  - closed domain vocab, single authority → Task 1 (`DOMAIN_KEYS`, exact-equality tested).
  - status vocabulary single authority (no second hard-coded literal) → Task 1 (`EnrollmentStatus`), consumed directly in Task 2; `ENROLLMENT_STATUSES` derived from it.
  - value carries status `{enrolled, out-of-domain}` → Task 2 (`domains: dict[str, EnrollmentStatus]`).
  - unknown domain key = hard config error → Task 2 (`_known_domains`).
  - **malformed ≠ undeclared** (null and missing-`domains` rejected; `{domains: {}}` retained) → Task 2 (`_reject_null_skill_coverage` + required `domains`).
  - absence = `undeclared`, never inferred out-of-domain → Task 4 + Task 2 (field default `None`, reachable only via absence).
  - `enrolled` (capability-reading) ⇒ `entity_schema_version: 3` → Task 3.
  - block is closed → Task 2 (`extra="forbid"`).
  - near-miss `skill_coverge:` key rejected → automatic via existing `reject_near_miss_keys` once the field is declared (Task 2 note).
  - real public surface (YAML through `load_project_config`) exercised → Task 5.
  - portfolio-scan states (`enrolled`/`out-of-domain`/`undeclared`) → `domain_enrollment` (Task 4) is exactly the per-project read the scan consumes.
- **Documentation.** User-facing conventions entry explicitly assigned to sub-plan 4 (see "Documentation deferral" above) — a named later sub-plan, not left open.
- **Out of scope (deferred to later sub-plans, correctly absent here):** the write-path gap, `skills_loaded`, the packaged inventory, `covers:`, the overlay, and the `science skills coverage` command.
- **Type consistency.** `SkillCoverageConfig`, `skill_coverage`, `domain_enrollment`, `DOMAIN_KEYS`, `GENERATION_3_DOMAINS`, `ENROLLMENT_STATUSES`, `EnrollmentStatus` are spelled identically across every task. The helper's return `EnrollmentStatus | Literal["undeclared"]` composes the authored statuses with the single absence state; equality assertions in tests hold because `EnrollmentStatus` is a `StrEnum` (`EnrollmentStatus.ENROLLED == "enrolled"`).
- **Placeholder scan:** none — every code step carries complete code.

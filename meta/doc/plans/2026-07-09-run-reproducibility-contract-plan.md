# Analysis-Run Reproducibility Contract — Implementation Plan (t077, P1+P2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the existing `workflow-run` entity a captured reproducibility fingerprint, and make belief-eligible `empirical_data` evidence resolve to such a run.

**Architecture:** A tri-state `FingerprintComponent` (`captured` / `attested` / `unknown`) makes `""` unrepresentable. A frozen, versioned obligation table keyed on *declared* `executor.kind` × *declared* artifact locality decides which components must be captured — never a disk probe. Enforcement splits across two layers: fingerprint well-formedness is frontmatter-local (`validate`), while evidence→dataset→run resolution is a graph traversal (`graph/store/validation.py`) reusing `dependence_datasets_by_line` so it cannot diverge from the dataset-QA ceiling.

**Tech Stack:** Python 3.12+, Pydantic v2, rdflib, click, pytest, uv.

**Spec:** [`2026-07-09-run-reproducibility-contract-design.md`](2026-07-09-run-reproducibility-contract-design.md). Read it first.

## Global Constraints

- **Two packages, two working directories.** Model work runs from `science/model/`; CLI/tool work runs from `science/`. There is **no root `pyproject.toml`** — never run `uv run` from the repo root.
- Model tests: `cd science/model && uv run --frozen pytest`. Tool tests: `cd science && uv run --frozen pytest`.
- Lint/types from `science/`: `uv run ruff check` and `uv run pyright`.
- **`graph/belief.py` MUST NOT be modified by this plan.** A missing run is absent required structure, not a weak epistemic verdict.
- **P1 (Tasks 1–6b) is behavior-neutral**: no new finding may fire on an existing project. P2 (Tasks 7–11) introduces findings at WARN except the two day-1 errors.
- **The contract must fail CLOSED.** Naming a `workflow-run` is not the same as resolving to a *fingerprinted* one. Any code path that admits a run without checking for a fingerprint is a bug, not a shortcut.
- **Out of scope:** P3 (`DerivationBlock.git_commit` removal, schema bump to `1.1`, commons sweep) and P4 (WARN→ERROR flip). Do not touch `packages/schema.py:173`, `frontmatter.py:327`, or `schemas/science-pkg-entity-1.0.json`.
- Conventions: composition over inheritance; explicit over defensive; fail early, no silent fallbacks; no "legacy"/"compatibility" layers; no `Unified` prefix.
- **Commit messages carry no AI-attribution trailer or footer.** No `Co-Authored-By`, no "Generated with" line.
- Policy identity string is exactly `science-run-fingerprint/v1`.

## Known limitation (do not try to "fix" it in code)

`validate` **cannot** distinguish a hand-typed `provenance: captured` from one written by `register-run` — nothing in the file records the observer. Therefore `run.fingerprint-authored-capturable` fires only when a MUST-captured component is declared `attested`. Hand-typing `captured` is unfalsifiable from the file alone; that is precisely why capture lives in `register-run` (Task 6) and why `CaptureOrigin` names an observer for imported commons facts. Do not add a disk probe or a git lookup to try to detect it — that would reintroduce the non-determinism the spec forbids.

## File Structure

**Create:**
- `science/model/src/science_model/run_fingerprint.py` — leaf module: enums + `FingerprintComponent`, `CaptureOrigin`, `SeedPolicy`, `RunFingerprint`. Leaf so `entities.py` imports it without cycles (mirrors the `digests.py` precedent).
- `science/src/science_tool/run_fingerprint_policy.py` — `Obligation` enum, the frozen obligation table, the import-time reconciliation gate, `evaluate_fingerprint()`.
- `science/src/science_tool/graph/run_resolution.py` — `own_derivation_run()`, `resolved_empirical_runs()`, `NoRunReason`, `MemberOfCycleError`. (The per-line union `_runs_for_line` lives with its only caller in `graph/store/validation.py`.)
- `science/model/tests/test_run_fingerprint.py`
- `science/tests/test_run_fingerprint_policy.py`
- `science/tests/test_run_resolution.py`
- `science/tests/test_graph_validate_run_resolution.py`

**Modify:**
- `science/model/src/science_model/entities.py` — `WorkflowRunEntity.fingerprint`; `EvidenceLineEntity.run_refs`.
- `science/src/science_tool/datasets_register.py` — capture and persist the fingerprint.
- `science/src/science_tool/cli.py:7291-7314` — `register-run` calls `persist_run_fingerprint`.
- `science/src/science_tool/validate/checks/workflow_runs.py` *(create)* — the `run.*` checks.
- `science/src/science_tool/graph/store/validation.py` — the `empirical_run_resolution` row.
- `science/src/science_tool/graph/store/constants.py` — register `sci:runRef`, `sci:fingerprintPolicy`, `sci:derivationKind`, `sci:workflowRun`, `sci:memberOfParent`.
- `science/src/science_tool/graph/materialize.py` — emit all five (evidence-line `run_refs`, run fingerprint marker, dataset derivation union).

---

## P1 — Model, policy table, capture

### Task 1: `FingerprintComponent` tri-state

**Files:**
- Create: `science/model/src/science_model/run_fingerprint.py`
- Test: `science/model/tests/test_run_fingerprint.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `ComponentProvenance` (StrEnum: `CAPTURED="captured"`, `ATTESTED="attested"`, `UNKNOWN="unknown"`), `FingerprintComponent(value: str|None, provenance: ComponentProvenance, attested_by: str|None, attested_at: datetime|None, evidence_ref: str|None)`.

- [ ] **Step 1: Write the failing test**

```python
# science/model/tests/test_run_fingerprint.py
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from science_model.run_fingerprint import ComponentProvenance, FingerprintComponent

WHEN = datetime(2026, 7, 9, 12, 0, tzinfo=UTC)


def test_captured_requires_non_empty_value():
    ok = FingerprintComponent(value="abc123", provenance=ComponentProvenance.CAPTURED)
    assert ok.value == "abc123"
    for bad in ("", "   ", None):
        with pytest.raises(ValidationError):
            FingerprintComponent(value=bad, provenance=ComponentProvenance.CAPTURED)


def test_unknown_forbids_value_and_attestation():
    ok = FingerprintComponent(provenance=ComponentProvenance.UNKNOWN)
    assert ok.value is None
    with pytest.raises(ValidationError):
        FingerprintComponent(value="x", provenance=ComponentProvenance.UNKNOWN)
    with pytest.raises(ValidationError):
        FingerprintComponent(provenance=ComponentProvenance.UNKNOWN, attested_by="bob")


def test_attested_requires_attested_by_and_at():
    ok = FingerprintComponent(
        value="sha256:1", provenance=ComponentProvenance.ATTESTED,
        attested_by="nextflow", attested_at=WHEN,
    )
    assert ok.attested_by == "nextflow"
    with pytest.raises(ValidationError):
        FingerprintComponent(value="sha256:1", provenance=ComponentProvenance.ATTESTED, attested_by="nextflow")
    with pytest.raises(ValidationError):
        FingerprintComponent(value="sha256:1", provenance=ComponentProvenance.ATTESTED, attested_at=WHEN)


def test_captured_forbids_attestation_fields():
    with pytest.raises(ValidationError):
        FingerprintComponent(
            value="abc", provenance=ComponentProvenance.CAPTURED,
            attested_by="bob", attested_at=WHEN,
        )


def test_extra_fields_forbidden():
    with pytest.raises(ValidationError):
        FingerprintComponent(value="a", provenance=ComponentProvenance.CAPTURED, bogus=1)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science/model && uv run --frozen pytest tests/test_run_fingerprint.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'science_model.run_fingerprint'`

- [ ] **Step 3: Write minimal implementation**

```python
# science/model/src/science_model/run_fingerprint.py
"""Analysis-run reproducibility fingerprint (science-run-fingerprint/v1).

Leaf module: imports nothing from `science_model.entities`, so `entities.py`
may import it without a cycle.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, model_validator


class ComponentProvenance(StrEnum):
    CAPTURED = "captured"
    ATTESTED = "attested"
    UNKNOWN = "unknown"


class FingerprintComponent(BaseModel):
    """One fingerprint fact plus how it was obtained.

    `""` is unrepresentable: a captured/attested component must carry a
    non-empty value, and an unknown component must carry none.
    """

    model_config = ConfigDict(extra="forbid")

    value: str | None = None
    provenance: ComponentProvenance
    attested_by: str | None = None
    attested_at: datetime | None = None
    evidence_ref: str | None = None

    @model_validator(mode="after")
    def _validate_tristate(self) -> "FingerprintComponent":
        if self.provenance is ComponentProvenance.UNKNOWN:
            if self.value is not None:
                raise ValueError("unknown component must not carry a value")
            if self.attested_by is not None or self.attested_at is not None:
                raise ValueError("unknown component must not carry attestation fields")
            return self

        if self.value is None or not self.value.strip():
            raise ValueError(f"{self.provenance.value} component requires a non-empty value")

        if self.provenance is ComponentProvenance.ATTESTED:
            if self.attested_by is None or self.attested_at is None:
                raise ValueError("attested component requires attested_by and attested_at")
        else:  # CAPTURED
            if self.attested_by is not None or self.attested_at is not None:
                raise ValueError("captured component must not carry attested_by/attested_at")
        return self
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science/model && uv run --frozen pytest tests/test_run_fingerprint.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add science/model/src/science_model/run_fingerprint.py science/model/tests/test_run_fingerprint.py
git commit -m "Add tri-state FingerprintComponent (t077 P1)"
```

---

### Task 2: Executor, locality, seed policy, capture origin

**Files:**
- Modify: `science/model/src/science_model/run_fingerprint.py`
- Test: `science/model/tests/test_run_fingerprint.py`

**Interfaces:**
- Consumes: Task 1's `ComponentProvenance`, `FingerprintComponent`.
- Produces: `ExecutorKind` (`LOCAL="local"`, `COMMONS="commons"`, `EXTERNAL="external"`), `ArtifactLocality` (`SCIENCE_MANAGED="science-managed"`, `EXTERNAL="external"`), `SeedPolicy(kind, seeds, rationale)`, `CaptureOrigin(origin_project, origin_run_ref, captured_at, captured_by, capture_policy, source_ref, source_digest)`.

- [ ] **Step 1: Write the failing test**

```python
# append to science/model/tests/test_run_fingerprint.py
from science_model.run_fingerprint import (
    ArtifactLocality, CaptureOrigin, ExecutorKind, SeedPolicy,
)


def test_seed_policy_seeded_requires_seeds():
    ok = SeedPolicy(kind="seeded", seeds={"numpy": 7})
    assert ok.seeds == {"numpy": 7}
    with pytest.raises(ValidationError):
        SeedPolicy(kind="seeded")


def test_seed_policy_stochastic_unseeded_requires_rationale():
    ok = SeedPolicy(kind="stochastic-unseeded", rationale="vendor binary exposes no seed")
    assert ok.rationale
    with pytest.raises(ValidationError):
        SeedPolicy(kind="stochastic-unseeded")


def test_seed_policy_deterministic_takes_neither():
    ok = SeedPolicy(kind="deterministic")
    assert ok.seeds is None and ok.rationale is None
    with pytest.raises(ValidationError):
        SeedPolicy(kind="deterministic", seeds={"numpy": 1})


def test_capture_origin_requires_run_ref_prefix():
    ok = CaptureOrigin(
        origin_project="project:pan-disease", origin_run_ref="workflow-run:r1",
        captured_at=WHEN, captured_by="science", capture_policy="science-run-fingerprint/v1",
    )
    assert ok.origin_run_ref == "workflow-run:r1"
    with pytest.raises(ValidationError):
        CaptureOrigin(
            origin_project="project:pan-disease", origin_run_ref="r1",
            captured_at=WHEN, captured_by="science", capture_policy="science-run-fingerprint/v1",
        )


def test_enum_values():
    assert ExecutorKind.LOCAL == "local"
    assert ArtifactLocality.SCIENCE_MANAGED == "science-managed"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science/model && uv run --frozen pytest tests/test_run_fingerprint.py -v`
Expected: FAIL — `ImportError: cannot import name 'ExecutorKind'`

- [ ] **Step 3: Write minimal implementation**

```python
# append to science/model/src/science_model/run_fingerprint.py
from typing import Literal

from pydantic import field_validator

FINGERPRINT_POLICY_V1 = "science-run-fingerprint/v1"


class ExecutorKind(StrEnum):
    LOCAL = "local"
    COMMONS = "commons"
    EXTERNAL = "external"


class ArtifactLocality(StrEnum):
    SCIENCE_MANAGED = "science-managed"
    EXTERNAL = "external"


class SeedPolicy(BaseModel):
    """An assertion about how the code behaves — not an observation of a run."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["seeded", "deterministic", "stochastic-unseeded"]
    seeds: dict[str, int] | None = None
    rationale: str | None = None

    @model_validator(mode="after")
    def _validate_kind(self) -> "SeedPolicy":
        if self.kind == "seeded":
            if not self.seeds:
                raise ValueError("seed_policy kind='seeded' requires a non-empty seeds mapping")
            if self.rationale is not None:
                raise ValueError("seed_policy kind='seeded' must not carry a rationale")
        elif self.kind == "stochastic-unseeded":
            if not self.rationale:
                raise ValueError("seed_policy kind='stochastic-unseeded' requires a rationale")
            if self.seeds is not None:
                raise ValueError("seed_policy kind='stochastic-unseeded' must not carry seeds")
        else:  # deterministic
            if self.seeds is not None or self.rationale is not None:
                raise ValueError("seed_policy kind='deterministic' takes neither seeds nor rationale")
        return self


class CaptureOrigin(BaseModel):
    """Who captured the fingerprint, when, and under which policy version.

    Required when `executor == commons`: the producing Science project captured
    these facts; the consuming project imports a verifiable record.
    """

    model_config = ConfigDict(extra="forbid")

    origin_project: str
    origin_run_ref: str
    captured_at: datetime
    captured_by: str  # tool/agent/system — not necessarily a person
    capture_policy: str  # the ORIGIN's policy version
    source_ref: str | None = None
    source_digest: str | None = None

    @field_validator("origin_run_ref")
    @classmethod
    def _run_ref_prefix(cls, v: str) -> str:
        if not v.startswith("workflow-run:"):
            raise ValueError(f"origin_run_ref must be a workflow-run:<slug> reference, got {v!r}")
        return v
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science/model && uv run --frozen pytest tests/test_run_fingerprint.py -v`
Expected: PASS (10 tests)

- [ ] **Step 5: Commit**

```bash
git add science/model/src/science_model/run_fingerprint.py science/model/tests/test_run_fingerprint.py
git commit -m "Add executor/locality/seed-policy/capture-origin models (t077 P1)"
```

---

### Task 3: `RunFingerprint` and `WorkflowRunEntity.fingerprint`

**Files:**
- Modify: `science/model/src/science_model/run_fingerprint.py`
- Modify: `science/model/src/science_model/entities.py:895-904` (`WorkflowRunEntity`)
- Test: `science/model/tests/test_run_fingerprint.py`

**Interfaces:**
- Consumes: Tasks 1–2.
- Produces: `RunFingerprint` with component fields `code_sha`, `code_dirty`, `environment_digest`, `container_digest` (`| None`), `parameters_digest`, `input_manifest_digest`, `output_manifest_digest`; scalars `fingerprint_policy`, `executor`, `input_artifact_locality`, `output_artifact_locality`, `capture_origin`, `input_manifest_ref`, `output_manifest_ref`, `seed_policy`. Also `WorkflowRunEntity.fingerprint: RunFingerprint | None = None`.

- [ ] **Step 1: Write the failing test**

```python
# append to science/model/tests/test_run_fingerprint.py
from science_model.run_fingerprint import FINGERPRINT_POLICY_V1, RunFingerprint


def _cap(v: str) -> FingerprintComponent:
    return FingerprintComponent(value=v, provenance=ComponentProvenance.CAPTURED)


def _fp(**over) -> RunFingerprint:
    base = dict(
        fingerprint_policy=FINGERPRINT_POLICY_V1,
        executor=ExecutorKind.LOCAL,
        input_artifact_locality=ArtifactLocality.SCIENCE_MANAGED,
        output_artifact_locality=ArtifactLocality.SCIENCE_MANAGED,
        code_sha=_cap("a" * 40),
        code_dirty=_cap("false"),
        environment_digest=_cap("sha256:env"),
        parameters_digest=_cap("sha256:params"),
        input_manifest_digest=_cap("sha256:in"),
        output_manifest_digest=_cap("sha256:out"),
        seed_policy=SeedPolicy(kind="seeded", seeds={"numpy": 7}),
    )
    base.update(over)
    return RunFingerprint(**base)


def test_code_dirty_must_be_true_or_false_token():
    assert _fp().code_dirty.value == "false"
    with pytest.raises(ValidationError):
        _fp(code_dirty=_cap("False"))
    with pytest.raises(ValidationError):
        _fp(code_dirty=_cap("yes"))


def test_code_dirty_may_be_unknown():
    fp = _fp(executor=ExecutorKind.EXTERNAL,
             code_dirty=FingerprintComponent(provenance=ComponentProvenance.UNKNOWN))
    assert fp.code_dirty.value is None


def test_commons_requires_capture_origin():
    with pytest.raises(ValidationError):
        _fp(executor=ExecutorKind.COMMONS)
    ok = _fp(
        executor=ExecutorKind.COMMONS,
        capture_origin=CaptureOrigin(
            origin_project="project:pan-disease", origin_run_ref="workflow-run:r1",
            captured_at=WHEN, captured_by="science", capture_policy=FINGERPRINT_POLICY_V1,
        ),
    )
    assert ok.capture_origin is not None


def test_non_commons_forbids_capture_origin():
    with pytest.raises(ValidationError):
        _fp(capture_origin=CaptureOrigin(
            origin_project="p", origin_run_ref="workflow-run:r1", captured_at=WHEN,
            captured_by="science", capture_policy=FINGERPRINT_POLICY_V1,
        ))


def test_workflow_run_entity_carries_optional_fingerprint():
    from science_model.entities import WorkflowRunEntity

    e = WorkflowRunEntity(id="workflow-run:r1", kind="workflow-run", title="R1")
    assert e.fingerprint is None
    e2 = WorkflowRunEntity(id="workflow-run:r2", kind="workflow-run", title="R2", fingerprint=_fp())
    assert e2.fingerprint.code_sha.value == "a" * 40
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science/model && uv run --frozen pytest tests/test_run_fingerprint.py -v`
Expected: FAIL — `ImportError: cannot import name 'RunFingerprint'`

- [ ] **Step 3: Write minimal implementation**

```python
# append to science/model/src/science_model/run_fingerprint.py
class RunFingerprint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fingerprint_policy: str
    executor: ExecutorKind
    input_artifact_locality: ArtifactLocality
    output_artifact_locality: ArtifactLocality
    capture_origin: CaptureOrigin | None = None

    code_sha: FingerprintComponent
    code_dirty: FingerprintComponent
    environment_digest: FingerprintComponent
    container_digest: FingerprintComponent | None = None
    parameters_digest: FingerprintComponent
    input_manifest_digest: FingerprintComponent
    output_manifest_digest: FingerprintComponent

    input_manifest_ref: str | None = None
    output_manifest_ref: str | None = None

    seed_policy: SeedPolicy

    @field_validator("code_dirty")
    @classmethod
    def _dirty_token(cls, v: FingerprintComponent) -> FingerprintComponent:
        if v.value is not None and v.value not in ("true", "false"):
            raise ValueError(f'code_dirty.value must be "true" or "false", got {v.value!r}')
        return v

    @model_validator(mode="after")
    def _capture_origin_iff_commons(self) -> "RunFingerprint":
        is_commons = self.executor is ExecutorKind.COMMONS
        if is_commons and self.capture_origin is None:
            raise ValueError("executor='commons' requires capture_origin")
        if not is_commons and self.capture_origin is not None:
            raise ValueError(f"capture_origin is only valid for executor='commons', not {self.executor.value!r}")
        return self
```

Then in `science/model/src/science_model/entities.py`, add the import near the other model imports and extend `WorkflowRunEntity` (currently lines 895-904):

```python
from science_model.run_fingerprint import RunFingerprint  # near other imports


class WorkflowRunEntity(ProjectEntity):
    """Workflow run — readiness is `complete` when status == 'complete'."""

    manifest_path: str = ""
    resources: list[dict[str, Any]] = Field(default_factory=list)
    fingerprint: RunFingerprint | None = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science/model && uv run --frozen pytest tests/test_run_fingerprint.py -v && uv run --frozen pytest tests/test_entities.py -q`
Expected: PASS (15 new tests; `test_entities.py` unchanged and green)

- [ ] **Step 5: Commit**

```bash
git add science/model/src/science_model/run_fingerprint.py science/model/src/science_model/entities.py science/model/tests/test_run_fingerprint.py
git commit -m "Add RunFingerprint and hang it off WorkflowRunEntity (t077 P1)"
```

---

### Task 4: Obligation table and import-time reconciliation gate

**Files:**
- Create: `science/src/science_tool/run_fingerprint_policy.py`
- Test: `science/tests/test_run_fingerprint_policy.py`

**Interfaces:**
- Consumes: Task 3's `RunFingerprint`, `ExecutorKind`, `ArtifactLocality`.
- Produces: `Obligation` (`MUST_CAPTURED`, `MAY_ATTESTED`, `MAY_UNKNOWN`, `NOT_APPLICABLE`, `BY_LOCALITY`), `OBLIGATIONS: Mapping[ExecutorKind, Mapping[str, Obligation]]`, `LOCALITY_OBLIGATION: Mapping[ArtifactLocality, Obligation]`, `COMPONENT_FIELDS: tuple[str, ...]`, `obligation_for(executor, component, fingerprint) -> Obligation`.

- [ ] **Step 1: Write the failing test**

```python
# science/tests/test_run_fingerprint_policy.py
import pytest
from science_model.run_fingerprint import ArtifactLocality, ExecutorKind, RunFingerprint

from science_tool.run_fingerprint_policy import (
    COMPONENT_FIELDS, LOCALITY_OBLIGATION, OBLIGATIONS, Obligation, obligation_for,
)


def test_every_executor_declares_every_component():
    """The import-time reconciliation gate's property, asserted explicitly."""
    for executor in ExecutorKind:
        assert set(OBLIGATIONS[executor]) == set(COMPONENT_FIELDS), executor


def test_component_fields_match_the_model():
    from science_model.run_fingerprint import FingerprintComponent

    expected = set()
    for name, field in RunFingerprint.model_fields.items():
        ann = str(field.annotation)
        if "FingerprintComponent" in ann:
            expected.add(name)
    assert set(COMPONENT_FIELDS) == expected


def test_local_must_capture_code_and_env_and_forbids_container():
    assert OBLIGATIONS[ExecutorKind.LOCAL]["code_sha"] is Obligation.MUST_CAPTURED
    assert OBLIGATIONS[ExecutorKind.LOCAL]["environment_digest"] is Obligation.MUST_CAPTURED
    assert OBLIGATIONS[ExecutorKind.LOCAL]["container_digest"] is Obligation.NOT_APPLICABLE


def test_external_may_attest_env_but_still_must_capture_code_sha():
    assert OBLIGATIONS[ExecutorKind.EXTERNAL]["code_sha"] is Obligation.MUST_CAPTURED
    assert OBLIGATIONS[ExecutorKind.EXTERNAL]["environment_digest"] is Obligation.MAY_ATTESTED
    assert OBLIGATIONS[ExecutorKind.EXTERNAL]["code_dirty"] is Obligation.MAY_UNKNOWN


def test_manifest_obligation_resolves_by_its_own_locality(local_fingerprint):
    fp = local_fingerprint(
        input_artifact_locality=ArtifactLocality.EXTERNAL,
        output_artifact_locality=ArtifactLocality.SCIENCE_MANAGED,
    )
    assert obligation_for(fp.executor, "input_manifest_digest", fp) is Obligation.MAY_ATTESTED
    assert obligation_for(fp.executor, "output_manifest_digest", fp) is Obligation.MUST_CAPTURED


def test_by_locality_never_leaks_to_callers(local_fingerprint):
    fp = local_fingerprint()
    for component in COMPONENT_FIELDS:
        assert obligation_for(fp.executor, component, fp) is not Obligation.BY_LOCALITY


def test_locality_obligation_table():
    assert LOCALITY_OBLIGATION[ArtifactLocality.SCIENCE_MANAGED] is Obligation.MUST_CAPTURED
    assert LOCALITY_OBLIGATION[ArtifactLocality.EXTERNAL] is Obligation.MAY_ATTESTED
```

Add this fixture to `science/tests/conftest.py`:

```python
import pytest
from datetime import UTC, datetime
from science_model.run_fingerprint import (
    ArtifactLocality, ComponentProvenance, ExecutorKind, FingerprintComponent,
    FINGERPRINT_POLICY_V1, RunFingerprint, SeedPolicy,
)


@pytest.fixture
def local_fingerprint():
    def _cap(v: str) -> FingerprintComponent:
        return FingerprintComponent(value=v, provenance=ComponentProvenance.CAPTURED)

    def _make(**over) -> RunFingerprint:
        base = dict(
            fingerprint_policy=FINGERPRINT_POLICY_V1,
            executor=ExecutorKind.LOCAL,
            input_artifact_locality=ArtifactLocality.SCIENCE_MANAGED,
            output_artifact_locality=ArtifactLocality.SCIENCE_MANAGED,
            code_sha=_cap("a" * 40),
            code_dirty=_cap("false"),
            environment_digest=_cap("sha256:env"),
            parameters_digest=_cap("sha256:params"),
            input_manifest_digest=_cap("sha256:in"),
            output_manifest_digest=_cap("sha256:out"),
            seed_policy=SeedPolicy(kind="deterministic"),
        )
        base.update(over)
        return RunFingerprint(**base)

    return _make
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_run_fingerprint_policy.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'science_tool.run_fingerprint_policy'`

- [ ] **Step 3: Write minimal implementation**

```python
# science/src/science_tool/run_fingerprint_policy.py
"""Obligation table for `science-run-fingerprint/v1`.

The model owns the vocabulary; this module owns the obligations — mirroring the
`belief_weights` / `_reconcile_evidence_vocab` split.

Obligation is a pure function of the DECLARED executor kind and the DECLARED
artifact locality. It is never a function of what validate can observe on disk.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType

from science_model.run_fingerprint import (
    ArtifactLocality,
    ExecutorKind,
    RunFingerprint,
)


class Obligation(StrEnum):
    MUST_CAPTURED = "must-captured"
    MAY_ATTESTED = "may-attested"
    MAY_UNKNOWN = "may-unknown"
    NOT_APPLICABLE = "not-applicable"
    BY_LOCALITY = "by-locality"  # resolved by `obligation_for`; never returned


COMPONENT_FIELDS: tuple[str, ...] = (
    "code_sha",
    "code_dirty",
    "environment_digest",
    "container_digest",
    "parameters_digest",
    "input_manifest_digest",
    "output_manifest_digest",
)

#: Which fingerprint scalar decides a locality-scoped component's obligation.
_LOCALITY_FIELD: Mapping[str, str] = MappingProxyType(
    {
        "input_manifest_digest": "input_artifact_locality",
        "output_manifest_digest": "output_artifact_locality",
    }
)

LOCALITY_OBLIGATION: Mapping[ArtifactLocality, Obligation] = MappingProxyType(
    {
        ArtifactLocality.SCIENCE_MANAGED: Obligation.MUST_CAPTURED,
        ArtifactLocality.EXTERNAL: Obligation.MAY_ATTESTED,
    }
)

OBLIGATIONS: Mapping[ExecutorKind, Mapping[str, Obligation]] = MappingProxyType(
    {
        ExecutorKind.LOCAL: MappingProxyType(
            {
                "code_sha": Obligation.MUST_CAPTURED,
                "code_dirty": Obligation.MUST_CAPTURED,
                "environment_digest": Obligation.MUST_CAPTURED,
                "container_digest": Obligation.NOT_APPLICABLE,
                "parameters_digest": Obligation.MUST_CAPTURED,
                "input_manifest_digest": Obligation.BY_LOCALITY,
                "output_manifest_digest": Obligation.BY_LOCALITY,
            }
        ),
        ExecutorKind.COMMONS: MappingProxyType(
            {
                "code_sha": Obligation.MUST_CAPTURED,
                "code_dirty": Obligation.MUST_CAPTURED,
                "environment_digest": Obligation.MUST_CAPTURED,
                "container_digest": Obligation.MAY_ATTESTED,
                "parameters_digest": Obligation.MUST_CAPTURED,
                "input_manifest_digest": Obligation.BY_LOCALITY,
                "output_manifest_digest": Obligation.BY_LOCALITY,
            }
        ),
        ExecutorKind.EXTERNAL: MappingProxyType(
            {
                "code_sha": Obligation.MUST_CAPTURED,
                "code_dirty": Obligation.MAY_UNKNOWN,
                "environment_digest": Obligation.MAY_ATTESTED,
                "container_digest": Obligation.MAY_ATTESTED,
                "parameters_digest": Obligation.MAY_ATTESTED,
                "input_manifest_digest": Obligation.BY_LOCALITY,
                "output_manifest_digest": Obligation.BY_LOCALITY,
            }
        ),
    }
)


def obligation_for(
    executor: ExecutorKind, component: str, fingerprint: RunFingerprint
) -> Obligation:
    """Resolve a component's obligation, collapsing BY_LOCALITY to a concrete one."""
    declared = OBLIGATIONS[executor][component]
    if declared is not Obligation.BY_LOCALITY:
        return declared
    locality: ArtifactLocality = getattr(fingerprint, _LOCALITY_FIELD[component])
    return LOCALITY_OBLIGATION[locality]


def _reconcile_obligation_table() -> None:
    """Fail at import if the table and the model have drifted apart."""
    model_components = {
        name
        for name, field in RunFingerprint.model_fields.items()
        if "FingerprintComponent" in str(field.annotation)
    }
    if set(COMPONENT_FIELDS) != model_components:
        raise RuntimeError(
            "run-fingerprint drift: COMPONENT_FIELDS "
            f"{sorted(COMPONENT_FIELDS)} != RunFingerprint components {sorted(model_components)}"
        )
    for executor in ExecutorKind:
        declared = set(OBLIGATIONS[executor])
        if declared != model_components:
            missing = sorted(model_components - declared)
            extra = sorted(declared - model_components)
            raise RuntimeError(
                f"run-fingerprint drift for executor={executor.value}: missing={missing} extra={extra}"
            )
    if set(LOCALITY_OBLIGATION) != set(ArtifactLocality):
        raise RuntimeError("run-fingerprint drift: LOCALITY_OBLIGATION must cover every ArtifactLocality")


_reconcile_obligation_table()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science && uv run --frozen pytest tests/test_run_fingerprint_policy.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/run_fingerprint_policy.py science/tests/test_run_fingerprint_policy.py science/tests/conftest.py
git commit -m "Add science-run-fingerprint/v1 obligation table with import-time gate (t077 P1)"
```

---

### Task 5: `evaluate_fingerprint()` — obligations to findings

**Files:**
- Modify: `science/src/science_tool/run_fingerprint_policy.py`
- Test: `science/tests/test_run_fingerprint_policy.py`

**Interfaces:**
- Consumes: Task 4's `obligation_for`, `COMPONENT_FIELDS`.
- Produces: `FingerprintFinding(rule: str, message: str)` (frozen dataclass) and `evaluate_fingerprint(fingerprint: RunFingerprint) -> list[FingerprintFinding]`. Rules emitted: `run.fingerprint-incomplete`, `run.fingerprint-authored-capturable`.

Rule semantics (implement exactly):

| resolved obligation | component state | outcome |
|---|---|---|
| `MUST_CAPTURED` | `captured` | ok |
| `MUST_CAPTURED` | `attested` | `run.fingerprint-authored-capturable` |
| `MUST_CAPTURED` | `unknown` or field is `None` | `run.fingerprint-incomplete` |
| `MAY_ATTESTED` | `captured` or `attested` | ok |
| `MAY_ATTESTED` | `unknown` or `None` | `run.fingerprint-incomplete` |
| `MAY_UNKNOWN` | any present state | ok |
| `MAY_UNKNOWN` | field is `None` | `run.fingerprint-incomplete` |
| `NOT_APPLICABLE` | field is `None` | ok |
| `NOT_APPLICABLE` | field present | `run.fingerprint-incomplete` |

- [ ] **Step 1: Write the failing test**

```python
# append to science/tests/test_run_fingerprint_policy.py
from science_model.run_fingerprint import ComponentProvenance, FingerprintComponent
from science_tool.run_fingerprint_policy import evaluate_fingerprint

from datetime import UTC, datetime
WHEN = datetime(2026, 7, 9, 12, 0, tzinfo=UTC)
UNKNOWN = FingerprintComponent(provenance=ComponentProvenance.UNKNOWN)


def _attested(v: str) -> FingerprintComponent:
    return FingerprintComponent(
        value=v, provenance=ComponentProvenance.ATTESTED,
        attested_by="nextflow", attested_at=WHEN,
    )


def test_clean_local_fingerprint_has_no_findings(local_fingerprint):
    assert evaluate_fingerprint(local_fingerprint()) == []


def test_attested_where_capture_required_is_authored_capturable(local_fingerprint):
    fp = local_fingerprint(environment_digest=_attested("sha256:env"))
    rules = [f.rule for f in evaluate_fingerprint(fp)]
    assert rules == ["run.fingerprint-authored-capturable"]
    assert "environment_digest" in evaluate_fingerprint(fp)[0].message


def test_unknown_where_capture_required_is_incomplete(local_fingerprint):
    fp = local_fingerprint(parameters_digest=UNKNOWN)
    assert [f.rule for f in evaluate_fingerprint(fp)] == ["run.fingerprint-incomplete"]


def test_container_digest_present_on_local_is_incomplete(local_fingerprint):
    fp = local_fingerprint(container_digest=_attested("sha256:img"))
    findings = evaluate_fingerprint(fp)
    assert [f.rule for f in findings] == ["run.fingerprint-incomplete"]
    assert "not applicable" in findings[0].message


def test_external_may_attest_environment_digest(local_fingerprint):
    fp = local_fingerprint(
        executor=ExecutorKind.EXTERNAL,
        environment_digest=_attested("sha256:env"),
        parameters_digest=_attested("sha256:params"),
        code_dirty=UNKNOWN,
    )
    assert evaluate_fingerprint(fp) == []


def test_external_still_cannot_attest_code_sha(local_fingerprint):
    fp = local_fingerprint(
        executor=ExecutorKind.EXTERNAL, code_sha=_attested("b" * 40),
        environment_digest=_attested("sha256:env"),
        parameters_digest=_attested("sha256:params"), code_dirty=UNKNOWN,
    )
    assert [f.rule for f in evaluate_fingerprint(fp)] == ["run.fingerprint-authored-capturable"]


def test_external_input_locality_allows_attested_manifest(local_fingerprint):
    fp = local_fingerprint(
        executor=ExecutorKind.EXTERNAL,
        input_artifact_locality=ArtifactLocality.EXTERNAL,
        input_manifest_digest=_attested("sha256:in"),
        environment_digest=_attested("sha256:env"),
        parameters_digest=_attested("sha256:params"), code_dirty=UNKNOWN,
    )
    assert evaluate_fingerprint(fp) == []


def test_findings_are_deterministically_ordered(local_fingerprint):
    fp = local_fingerprint(environment_digest=UNKNOWN, parameters_digest=UNKNOWN)
    messages = [f.message for f in evaluate_fingerprint(fp)]
    assert messages == sorted(messages)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_run_fingerprint_policy.py -v`
Expected: FAIL — `ImportError: cannot import name 'evaluate_fingerprint'`

- [ ] **Step 3: Write minimal implementation**

```python
# append to science/src/science_tool/run_fingerprint_policy.py
from dataclasses import dataclass

from science_model.run_fingerprint import ComponentProvenance, FingerprintComponent

RULE_INCOMPLETE = "run.fingerprint-incomplete"
RULE_AUTHORED_CAPTURABLE = "run.fingerprint-authored-capturable"


@dataclass(frozen=True, slots=True)
class FingerprintFinding:
    rule: str
    message: str


def _evaluate_component(
    name: str, component: FingerprintComponent | None, obligation: Obligation
) -> FingerprintFinding | None:
    if obligation is Obligation.NOT_APPLICABLE:
        if component is not None:
            return FingerprintFinding(
                RULE_INCOMPLETE, f"{name} is not applicable for this executor but is present"
            )
        return None

    if component is None:
        return FingerprintFinding(RULE_INCOMPLETE, f"{name} is required but absent")

    if obligation is Obligation.MUST_CAPTURED:
        if component.provenance is ComponentProvenance.CAPTURED:
            return None
        if component.provenance is ComponentProvenance.ATTESTED:
            return FingerprintFinding(
                RULE_AUTHORED_CAPTURABLE,
                f"{name} must be captured for this executor but is attested",
            )
        return FingerprintFinding(RULE_INCOMPLETE, f"{name} must be captured but is unknown")

    if obligation is Obligation.MAY_ATTESTED:
        if component.provenance is ComponentProvenance.UNKNOWN:
            return FingerprintFinding(
                RULE_INCOMPLETE, f"{name} must be captured or attested but is unknown"
            )
        return None

    # MAY_UNKNOWN — any present state is acceptable.
    return None


def evaluate_fingerprint(fingerprint: RunFingerprint) -> list[FingerprintFinding]:
    """Findings for one run's fingerprint. Pure; reads no disk state."""
    findings: list[FingerprintFinding] = []
    for name in COMPONENT_FIELDS:
        obligation = obligation_for(fingerprint.executor, name, fingerprint)
        finding = _evaluate_component(name, getattr(fingerprint, name), obligation)
        if finding is not None:
            findings.append(finding)
    return sorted(findings, key=lambda f: f.message)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science && uv run --frozen pytest tests/test_run_fingerprint_policy.py -v`
Expected: PASS (15 tests)

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/run_fingerprint_policy.py science/tests/test_run_fingerprint_policy.py
git commit -m "Evaluate run fingerprints against the obligation table (t077 P1)"
```

---

### Task 6: Capture the fingerprint at `dataset register-run`

**Files:**
- Modify: `science/src/science_tool/datasets_register.py`
- Test: `science/tests/test_datasets_register_fingerprint.py` *(create)*

**Interfaces:**
- Consumes: Task 3's `RunFingerprint` and components; Task 5's `evaluate_fingerprint`.
- Produces: `capture_fingerprint(project_root, run_fm, *, executor, input_locality, output_locality, code_sha, code_dirty, environment_digest, parameters_digest, input_manifest_digest, output_manifest_digest) -> RunFingerprint` and a `FingerprintCaptureError` raised when the run frontmatter hand-authors a MUST-captured component.

Capture sources (each written with `provenance=captured`): `code_sha` ← `git rev-parse HEAD`; `code_dirty` ← `git status --porcelain` non-empty; `environment_digest` ← `sha256` of `uv.lock`; `parameters_digest` ← `sha256` of the run's `config_snapshot`; `input_manifest_digest` / `output_manifest_digest` ← `sha256` of the canonical sorted per-file manifest.

- [ ] **Step 1: Write the failing test**

```python
# science/tests/test_datasets_register_fingerprint.py
import pytest

from science_model.run_fingerprint import ArtifactLocality, ComponentProvenance, ExecutorKind
from science_tool.datasets_register import FingerprintCaptureError, capture_fingerprint


def _kwargs(**over):
    base = dict(
        executor=ExecutorKind.LOCAL,
        input_locality=ArtifactLocality.SCIENCE_MANAGED,
        output_locality=ArtifactLocality.SCIENCE_MANAGED,
        code_sha="a" * 40,
        code_dirty=False,
        environment_digest="sha256:env",
        parameters_digest="sha256:params",
        input_manifest_digest="sha256:in",
        output_manifest_digest="sha256:out",
    )
    base.update(over)
    return base


def test_capture_marks_every_component_captured():
    fp = capture_fingerprint(run_fm={}, **_kwargs())
    for name in ("code_sha", "code_dirty", "environment_digest",
                 "parameters_digest", "input_manifest_digest", "output_manifest_digest"):
        assert getattr(fp, name).provenance is ComponentProvenance.CAPTURED
    assert fp.code_dirty.value == "false"
    assert fp.container_digest is None
    assert fp.fingerprint_policy == "science-run-fingerprint/v1"


def test_capture_encodes_dirty_as_lowercase_token():
    fp = capture_fingerprint(run_fm={}, **_kwargs(code_dirty=True))
    assert fp.code_dirty.value == "true"


def test_hand_authored_capturable_component_is_rejected():
    run_fm = {"fingerprint": {"code_sha": {"value": "dead" * 10, "provenance": "captured"}}}
    with pytest.raises(FingerprintCaptureError, match="code_sha"):
        capture_fingerprint(run_fm=run_fm, **_kwargs())


def test_hand_authored_seed_policy_is_preserved():
    run_fm = {"fingerprint": {"seed_policy": {"kind": "seeded", "seeds": {"numpy": 7}}}}
    fp = capture_fingerprint(run_fm=run_fm, **_kwargs())
    assert fp.seed_policy.kind == "seeded" and fp.seed_policy.seeds == {"numpy": 7}


def test_missing_seed_policy_defaults_to_stochastic_unseeded_is_rejected():
    """Seed policy is authored, never invented. Absent => fail loud."""
    with pytest.raises(FingerprintCaptureError, match="seed_policy"):
        capture_fingerprint(run_fm={"fingerprint": {}}, **_kwargs())


def test_captured_fingerprint_evaluates_clean():
    from science_tool.run_fingerprint_policy import evaluate_fingerprint

    run_fm = {"fingerprint": {"seed_policy": {"kind": "deterministic"}}}
    assert evaluate_fingerprint(capture_fingerprint(run_fm=run_fm, **_kwargs())) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_datasets_register_fingerprint.py -v`
Expected: FAIL — `ImportError: cannot import name 'FingerprintCaptureError'`

- [ ] **Step 3: Write minimal implementation**

```python
# append to science/src/science_tool/datasets_register.py
from science_model.run_fingerprint import (
    ArtifactLocality,
    ComponentProvenance,
    ExecutorKind,
    FINGERPRINT_POLICY_V1,
    FingerprintComponent,
    RunFingerprint,
    SeedPolicy,
)
from science_tool.run_fingerprint_policy import COMPONENT_FIELDS


class FingerprintCaptureError(Exception):
    """The run frontmatter conflicts with what `register-run` must capture."""


def _captured(value: str) -> FingerprintComponent:
    return FingerprintComponent(value=value, provenance=ComponentProvenance.CAPTURED)


def capture_fingerprint(
    *,
    run_fm: dict,
    executor: ExecutorKind,
    input_locality: ArtifactLocality,
    output_locality: ArtifactLocality,
    code_sha: str,
    code_dirty: bool,
    environment_digest: str,
    parameters_digest: str,
    input_manifest_digest: str,
    output_manifest_digest: str,
) -> RunFingerprint:
    """Build a captured fingerprint. Only `seed_policy` may be authored."""
    authored = run_fm.get("fingerprint") or {}

    hand_authored = sorted(set(authored) & set(COMPONENT_FIELDS))
    if hand_authored:
        raise FingerprintCaptureError(
            "these fingerprint components are captured by register-run and must not be "
            f"hand-authored in the workflow-run frontmatter: {', '.join(hand_authored)}"
        )

    raw_seed = authored.get("seed_policy")
    if not raw_seed:
        raise FingerprintCaptureError(
            "workflow-run frontmatter must declare fingerprint.seed_policy — it asserts how "
            "the code behaves and is never inferred"
        )

    return RunFingerprint(
        fingerprint_policy=FINGERPRINT_POLICY_V1,
        executor=executor,
        input_artifact_locality=input_locality,
        output_artifact_locality=output_locality,
        code_sha=_captured(code_sha),
        code_dirty=_captured("true" if code_dirty else "false"),
        environment_digest=_captured(environment_digest),
        parameters_digest=_captured(parameters_digest),
        input_manifest_digest=_captured(input_manifest_digest),
        output_manifest_digest=_captured(output_manifest_digest),
        seed_policy=SeedPolicy.model_validate(raw_seed),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science && uv run --frozen pytest tests/test_datasets_register_fingerprint.py -v && uv run --frozen pytest tests/ -q -k register`
Expected: PASS (6 new tests; existing register tests green)

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/datasets_register.py science/tests/test_datasets_register_fingerprint.py
git commit -m "Capture the run fingerprint at dataset register-run (t077 P1)"
```

---

### Task 6b: Wire `register-run` to persist the captured fingerprint

**Files:**
- Modify: `science/src/science_tool/datasets_register.py`
- Modify: `science/src/science_tool/cli.py:7291-7314` (`dataset_register_run`)
- Test: `science/tests/test_datasets_register_fingerprint.py`

**Interfaces:**
- Consumes: Task 6's `capture_fingerprint`, `FingerprintCaptureError`.
- Produces: `persist_run_fingerprint(project_root: Path, run_id: str) -> RunFingerprint` — reads the workflow-run entity, captures every capturable component, writes the `fingerprint` block back into its frontmatter, and returns it. Called by `dataset_register_run` after `preflight_register_run_identity`.

**Declared vs captured, restated:** `executor`, `input_artifact_locality`, `output_artifact_locality`, and `seed_policy` are **authored** in the run's frontmatter (they are declarations, not observations) and are the only `fingerprint.*` keys a human may write. Every `COMPONENT_FIELDS` entry is captured here. Task 6's `capture_fingerprint` already rejects a hand-authored component.

**Fail loud** (no silent fallbacks): missing `uv.lock`, absent `git`, a run frontmatter with no `fingerprint.executor`, or a `config_snapshot` path that does not exist each raise `FingerprintCaptureError`.

**`persist_run_fingerprint` is deliberately NOT idempotent, and there is no bug here.** `code_dirty` records the worktree state *at capture time*, and the command's own frontmatter write leaves the tree dirty — so a second call captures `code_dirty=true`. `code_sha` and the digests are stable; only `code_dirty` moves. Making it idempotent would require excluding the run entity's own path from the dirty check, which silently narrows what "dirty" means. **Do not add that exclusion in this plan.** If it is ever wanted, it needs its own design; the honest semantics is: commit the run entity, then the recorded `code_dirty` describes the tree that produced the run.

`register-run` continues to copy `git_commit` down onto `DerivationBlock` during P1/P2; P3 removes that copy-down. The two coexist for now — this task adds the fingerprint, it does not remove the denormalized field.

- [ ] **Step 1: Write the failing test**

```python
# append to science/tests/test_datasets_register_fingerprint.py
import subprocess
from pathlib import Path

import pytest
import yaml

from science_tool.datasets_register import persist_run_fingerprint


@pytest.fixture
def git_project(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / "uv.lock").write_text("lock", encoding="utf-8")
    (tmp_path / "config.yaml").write_text("alpha: 1\n", encoding="utf-8")
    runs = tmp_path / "entities" / "workflow-runs"
    runs.mkdir(parents=True)
    (runs / "r1.md").write_text(
        "---\n"
        "id: workflow-run:r1\nkind: workflow-run\ntitle: R1\n"
        "config_snapshot: config.yaml\n"
        "fingerprint:\n"
        "  executor: local\n"
        "  input_artifact_locality: science-managed\n"
        "  output_artifact_locality: science-managed\n"
        "  seed_policy: {kind: deterministic}\n"
        "---\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init"],
        cwd=tmp_path, check=True,
    )
    return tmp_path


def test_persist_writes_captured_components_into_frontmatter(git_project):
    fp = persist_run_fingerprint(git_project, "workflow-run:r1")
    assert fp.code_sha.provenance == "captured" and len(fp.code_sha.value) == 40
    assert fp.code_dirty.value == "false"

    written = yaml.safe_load(
        (git_project / "entities" / "workflow-runs" / "r1.md").read_text().split("---")[1]
    )
    assert written["fingerprint"]["code_sha"]["provenance"] == "captured"
    assert written["fingerprint"]["seed_policy"]["kind"] == "deterministic"


def test_dirty_worktree_is_captured_as_true(git_project):
    (git_project / "config.yaml").write_text("alpha: 2\n", encoding="utf-8")
    assert persist_run_fingerprint(git_project, "workflow-run:r1").code_dirty.value == "true"


def test_persisted_fingerprint_evaluates_clean(git_project):
    from science_tool.run_fingerprint_policy import evaluate_fingerprint

    assert evaluate_fingerprint(persist_run_fingerprint(git_project, "workflow-run:r1")) == []


def test_missing_lockfile_fails_loud(git_project):
    (git_project / "uv.lock").unlink()
    with pytest.raises(FingerprintCaptureError, match="uv.lock"):
        persist_run_fingerprint(git_project, "workflow-run:r1")


def test_missing_executor_declaration_fails_loud(git_project):
    run = git_project / "entities" / "workflow-runs" / "r1.md"
    run.write_text(run.read_text().replace("  executor: local\n", ""), encoding="utf-8")
    with pytest.raises(FingerprintCaptureError, match="executor"):
        persist_run_fingerprint(git_project, "workflow-run:r1")


def test_persist_is_not_idempotent_because_its_own_write_dirties_the_tree(git_project):
    """`code_dirty` is the worktree state AT CAPTURE TIME — including the previous
    run's uncommitted fingerprint write. This is the honest semantics; commit the
    run entity before re-registering.
    """
    first = persist_run_fingerprint(git_project, "workflow-run:r1")
    assert first.code_dirty.value == "false"

    second = persist_run_fingerprint(git_project, "workflow-run:r1")
    assert second.code_dirty.value == "true"  # the first call's write is uncommitted
    assert second.code_sha.value == first.code_sha.value


def test_code_sha_is_stable_across_repeated_capture(git_project):
    """Only `code_dirty` moves; the commit identity does not."""
    first = persist_run_fingerprint(git_project, "workflow-run:r1")
    second = persist_run_fingerprint(git_project, "workflow-run:r1")
    assert first.code_sha.value == second.code_sha.value
    assert first.environment_digest.value == second.environment_digest.value
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_datasets_register_fingerprint.py -k persist -v`
Expected: FAIL — `ImportError: cannot import name 'persist_run_fingerprint'`

- [ ] **Step 3: Write minimal implementation**

```python
# append to science/src/science_tool/datasets_register.py
import hashlib
import subprocess
from pathlib import Path


def _sha256_file(path: Path, label: str) -> str:
    if not path.is_file():
        raise FingerprintCaptureError(f"cannot capture {label}: {path} does not exist")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(project_root: Path, *args: str) -> str:
    try:
        done = subprocess.run(
            ["git", *args], cwd=project_root, capture_output=True, text=True, check=True
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise FingerprintCaptureError(f"cannot capture git state: {exc}") from exc
    return done.stdout.strip()


def _manifest_digest(entries: list[str]) -> str:
    """sha256 over a canonical, sorted, newline-joined manifest."""
    canonical = "\n".join(sorted(entries)).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def persist_run_fingerprint(project_root: Path, run_id: str) -> RunFingerprint:
    """Capture the fingerprint for `run_id` and write it into the run entity."""
    run_path, run_fm = _read_run(project_root, run_id)
    declared = run_fm.get("fingerprint") or {}

    for key in ("executor", "input_artifact_locality", "output_artifact_locality"):
        if key not in declared:
            raise FingerprintCaptureError(
                f"{run_path.name}: fingerprint.{key} must be declared before register-run "
                f"(it is a declaration, not an observation)"
            )

    config_snapshot = run_fm.get("config_snapshot") or ""
    if not config_snapshot:
        raise FingerprintCaptureError(f"{run_path.name}: config_snapshot is required to capture parameters_digest")

    fingerprint = capture_fingerprint(
        run_fm=run_fm,
        executor=ExecutorKind(declared["executor"]),
        input_locality=ArtifactLocality(declared["input_artifact_locality"]),
        output_locality=ArtifactLocality(declared["output_artifact_locality"]),
        code_sha=_git(project_root, "rev-parse", "HEAD"),
        code_dirty=bool(_git(project_root, "status", "--porcelain")),
        environment_digest=_sha256_file(project_root / "uv.lock", "uv.lock"),
        parameters_digest=_sha256_file(project_root / config_snapshot, "config_snapshot"),
        input_manifest_digest=_manifest_digest(_run_input_manifest(project_root, run_fm)),
        output_manifest_digest=_manifest_digest(_run_output_manifest(project_root, run_fm)),
    )

    payload = fingerprint.model_dump(mode="json", exclude_none=True)
    _rewrite_run_frontmatter(run_path, {**run_fm, "fingerprint": payload})
    return fingerprint
```

Then in `science/src/science_tool/cli.py`, inside `dataset_register_run` (currently `:7299-7314`), immediately after `preflight_register_run_identity(root, workflow_run_id)`:

```python
        from science_tool.datasets_register import persist_run_fingerprint

        fingerprint = persist_run_fingerprint(root, workflow_run_id)
        click.echo(f"captured fingerprint {fingerprint.fingerprint_policy} for {workflow_run_id}")
```

> **Implementer:** `_run_input_manifest` / `_run_output_manifest` / `_rewrite_run_frontmatter` are three seams. The run entity already carries `manifest_path` and `resources` (`entities.py:898-899`); derive the per-file entries from `resources`, and set `input_manifest_ref` / `output_manifest_ref` on the fingerprint to `manifest_path` when present. For the frontmatter rewrite, reuse whatever writer `datasets_register.py` already uses to emit dataset markdown (see the `git_commit` emission at `:253`) rather than introducing a new YAML dumper. Fail loud if `resources` is empty and the declared locality is `science-managed`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science && uv run --frozen pytest tests/test_datasets_register_fingerprint.py -v && uv run --frozen pytest tests/ -q -k register`
Expected: PASS (6 seams-free tests from Task 6 + 6 new; existing register tests green)

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/datasets_register.py science/src/science_tool/cli.py science/tests/test_datasets_register_fingerprint.py
git commit -m "Persist the captured fingerprint from dataset register-run (t077 P1)"
```

---

## P2 — Validate check and graph-phase resolution

### Task 7: `validate` check for run-fingerprint obligations

**Files:**
- Create: `science/src/science_tool/validate/checks/workflow_runs.py`
- Test: `science/tests/validate/test_checks_workflow_runs.py`

**Interfaces:**
- Consumes: Task 5's `evaluate_fingerprint`, `FingerprintFinding`.
- Produces: `check_run_fingerprint_obligations(ctx) -> Iterator[Result]` emitting `run.fingerprint-incomplete` (WARN), `run.fingerprint-authored-capturable` (ERROR), `run.fingerprint-origin-unverified` (ERROR).

A run without a `fingerprint` block emits nothing — P1/P2 are behavior-neutral for existing projects; the *evidence* side (Task 10) is what notices a missing run.

`run.fingerprint-origin-unverified` fires when `executor: commons` and `capture_origin.source_ref` names a file that does not exist under the project root, or whose `source_digest` disagrees with that file's `sha256`. This is a file **read**, never a probe of the run's data.

- [ ] **Step 1: Write the failing test**

```python
# science/tests/validate/test_checks_workflow_runs.py
import hashlib

from science_tool.validate.checks.workflow_runs import check_run_fingerprint_obligations
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Severity


def _ctx(tmp_path) -> ValidateContext:
    (tmp_path / "science.yaml").write_text("name: t\nprofile: software\n", encoding="utf-8")
    (tmp_path / "entities" / "workflow-runs").mkdir(parents=True)
    return ValidateContext.from_project_root(tmp_path, strict=False, verbose=False)


def _write_run(tmp_path, name: str, fingerprint_yaml: str) -> None:
    (tmp_path / "entities" / "workflow-runs" / f"{name}.md").write_text(
        f"---\nid: workflow-run:{name}\nkind: workflow-run\ntitle: {name}\n{fingerprint_yaml}---\n",
        encoding="utf-8",
    )


CLEAN = """fingerprint:
  fingerprint_policy: science-run-fingerprint/v1
  executor: local
  input_artifact_locality: science-managed
  output_artifact_locality: science-managed
  code_sha: {value: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa, provenance: captured}
  code_dirty: {value: "false", provenance: captured}
  environment_digest: {value: "sha256:env", provenance: captured}
  parameters_digest: {value: "sha256:params", provenance: captured}
  input_manifest_digest: {value: "sha256:in", provenance: captured}
  output_manifest_digest: {value: "sha256:out", provenance: captured}
  seed_policy: {kind: deterministic}
"""


def test_run_without_fingerprint_emits_nothing(tmp_path):
    _write_run(tmp_path, "r1", "")
    assert list(check_run_fingerprint_obligations(_ctx(tmp_path))) == []


def test_clean_fingerprint_emits_nothing(tmp_path):
    _write_run(tmp_path, "r1", CLEAN)
    assert list(check_run_fingerprint_obligations(_ctx(tmp_path))) == []


def test_attested_capturable_component_is_error(tmp_path):
    bad = CLEAN.replace(
        '  environment_digest: {value: "sha256:env", provenance: captured}',
        '  environment_digest: {value: "sha256:env", provenance: attested, '
        'attested_by: bob, attested_at: "2026-07-09T12:00:00Z"}',
    )
    _write_run(tmp_path, "r1", bad)
    results = list(check_run_fingerprint_obligations(_ctx(tmp_path)))
    assert [r.rule for r in results] == ["run.fingerprint-authored-capturable"]
    assert results[0].severity is Severity.ERROR


def test_unknown_capturable_component_is_warn(tmp_path):
    bad = CLEAN.replace(
        '  parameters_digest: {value: "sha256:params", provenance: captured}',
        "  parameters_digest: {provenance: unknown}",
    )
    _write_run(tmp_path, "r1", bad)
    results = list(check_run_fingerprint_obligations(_ctx(tmp_path)))
    assert [r.rule for r in results] == ["run.fingerprint-incomplete"]
    assert results[0].severity is Severity.WARN


def test_commons_origin_digest_mismatch_is_error(tmp_path):
    src = tmp_path / "imported.md"
    src.write_text("real content", encoding="utf-8")
    commons = CLEAN.replace("  executor: local", "  executor: commons") + (
        "  capture_origin:\n"
        "    origin_project: project:pan-disease\n"
        "    origin_run_ref: workflow-run:r0\n"
        "    captured_at: '2026-07-09T12:00:00Z'\n"
        "    captured_by: science\n"
        "    capture_policy: science-run-fingerprint/v1\n"
        "    source_ref: imported.md\n"
        "    source_digest: deadbeef\n"
    )
    _write_run(tmp_path, "r1", commons)
    results = list(check_run_fingerprint_obligations(_ctx(tmp_path)))
    assert [r.rule for r in results] == ["run.fingerprint-origin-unverified"]
    assert results[0].severity is Severity.ERROR


def test_commons_origin_matching_digest_passes(tmp_path):
    src = tmp_path / "imported.md"
    src.write_text("real content", encoding="utf-8")
    digest = hashlib.sha256(b"real content").hexdigest()
    commons = CLEAN.replace("  executor: local", "  executor: commons") + (
        "  capture_origin:\n"
        "    origin_project: project:pan-disease\n"
        "    origin_run_ref: workflow-run:r0\n"
        "    captured_at: '2026-07-09T12:00:00Z'\n"
        "    captured_by: science\n"
        "    capture_policy: science-run-fingerprint/v1\n"
        "    source_ref: imported.md\n"
        f"    source_digest: {digest}\n"
    )
    _write_run(tmp_path, "r1", commons)
    assert list(check_run_fingerprint_obligations(_ctx(tmp_path))) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run --frozen pytest tests/validate/test_checks_workflow_runs.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'science_tool.validate.checks.workflow_runs'`

- [ ] **Step 3: Write minimal implementation**

```python
# science/src/science_tool/validate/checks/workflow_runs.py
"""Structural checks for workflow-run reproducibility fingerprints.

Frontmatter-local: a run's fingerprint is well-formed or not, independently of
any evidence line. Evidence -> run RESOLUTION is graph-phase; see
`science_tool.graph.store.validation`.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from pathlib import Path

from pydantic import ValidationError
from science_model.run_fingerprint import ExecutorKind, RunFingerprint

from science_tool.entities import resolve_path_policy
from science_tool.run_fingerprint_policy import RULE_AUTHORED_CAPTURABLE, evaluate_fingerprint
from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity

RULE_ORIGIN_UNVERIFIED = "run.fingerprint-origin-unverified"


def _runs(ctx: ValidateContext) -> list[tuple[Path, dict]]:
    root = ctx.project_root / resolve_path_policy("workflow-run").root
    if not root.is_dir():
        return []
    return [(p, ctx.frontmatter(p)) for p in sorted(root.glob("*.md"))]


def _verify_origin(ctx: ValidateContext, path: Path, fp: RunFingerprint) -> Result | None:
    if fp.executor is not ExecutorKind.COMMONS:
        return None
    origin = fp.capture_origin
    assert origin is not None  # model invariant: commons => capture_origin
    if origin.source_ref is None:
        return None
    source = ctx.project_root / origin.source_ref
    if not source.is_file():
        return Result(
            severity=Severity.ERROR, path=path, line=None,
            message=f"{path.name}: capture_origin.source_ref {origin.source_ref!r} does not exist",
            rule=RULE_ORIGIN_UNVERIFIED, task=None,
        )
    if origin.source_digest is None:
        return None
    actual = hashlib.sha256(source.read_bytes()).hexdigest()
    if actual != origin.source_digest:
        return Result(
            severity=Severity.ERROR, path=path, line=None,
            message=(
                f"{path.name}: capture_origin.source_digest {origin.source_digest!r} does not "
                f"match sha256 of {origin.source_ref!r} ({actual!r})"
            ),
            rule=RULE_ORIGIN_UNVERIFIED, task=None,
        )
    return None


@Check(section="workflow runs", order=10)
def check_run_fingerprint_obligations(ctx: ValidateContext) -> Iterator[Result]:
    """A workflow-run fingerprint must satisfy science-run-fingerprint/v1.

    Capturable components may not be attested (ERROR). Missing required components
    warn until the P4 flip. A run with no fingerprint block emits nothing.
    """
    for path, fm in _runs(ctx):
        raw = fm.get("fingerprint")
        if not raw:
            continue
        try:
            fingerprint = RunFingerprint.model_validate(raw)
        except ValidationError as exc:
            yield Result(
                severity=Severity.ERROR, path=path, line=None,
                message=f"{path.name}: malformed fingerprint: {exc.errors()[0]['msg']}",
                rule="run.fingerprint-incomplete", task=None,
            )
            continue

        for finding in evaluate_fingerprint(fingerprint):
            severity = (
                Severity.ERROR if finding.rule == RULE_AUTHORED_CAPTURABLE else Severity.WARN
            )
            yield Result(
                severity=severity, path=path, line=None,
                message=f"{path.name}: {finding.message}", rule=finding.rule, task=None,
            )

        origin_result = _verify_origin(ctx, path, fingerprint)
        if origin_result is not None:
            yield origin_result
```

Register the module wherever `validate/checks/__init__.py` imports its sibling check modules (follow the existing import list; add `workflow_runs`).

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science && uv run --frozen pytest tests/validate/test_checks_workflow_runs.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/validate/checks/workflow_runs.py science/src/science_tool/validate/checks/__init__.py science/tests/validate/test_checks_workflow_runs.py
git commit -m "Validate workflow-run fingerprints against the obligation table (t077 P2)"
```

---

### Task 8: `EvidenceLineEntity.run_refs`

**Files:**
- Modify: `science/model/src/science_model/entities.py:975-987` (`EvidenceLineEntity`)
- Test: `science/model/tests/test_run_fingerprint.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `EvidenceLineEntity.run_refs: list[str]`, each entry validated to the `workflow-run:` prefix. Added as the **last** field, following the codebase's additive-field convention.

- [ ] **Step 1: Write the failing test**

```python
# append to science/model/tests/test_run_fingerprint.py
def test_evidence_line_run_refs_require_workflow_run_prefix():
    from science_model.entities import EvidenceLineEntity

    ok = EvidenceLineEntity(
        id="evidence-line:e1", kind="evidence-line", title="E1",
        stance="supports", target="hypothesis:h1", run_refs=["workflow-run:r1"],
    )
    assert ok.run_refs == ["workflow-run:r1"]

    with pytest.raises(ValidationError):
        EvidenceLineEntity(
            id="evidence-line:e2", kind="evidence-line", title="E2",
            stance="supports", target="hypothesis:h1", run_refs=["r1"],
        )


def test_evidence_line_run_refs_default_empty():
    from science_model.entities import EvidenceLineEntity

    e = EvidenceLineEntity(
        id="evidence-line:e3", kind="evidence-line", title="E3",
        stance="supports", target="hypothesis:h1",
    )
    assert e.run_refs == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science/model && uv run --frozen pytest tests/test_run_fingerprint.py -k run_refs -v`
Expected: FAIL — `ValidationError: Extra inputs are not permitted [run_refs]` (or `AttributeError`)

- [ ] **Step 3: Write minimal implementation**

In `science/model/src/science_model/entities.py`, add to `EvidenceLineEntity` after `belief_eligible`:

```python
    belief_eligible: bool = True
    #: Supplemental workflow-run references. These WIDEN the resolved-run set for
    #: t077 but never substitute for `dataset_usage`, which stays mandatory.
    run_refs: list[str] = Field(default_factory=list)

    @field_validator("run_refs")
    @classmethod
    def _run_ref_ids(cls, v: list[str]) -> list[str]:
        for ref in v:
            if not ref.startswith("workflow-run:"):
                raise ValueError(f"run_refs entries must be workflow-run:<slug> references, got {ref!r}")
        return v
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science/model && uv run --frozen pytest tests/test_run_fingerprint.py -v && uv run --frozen pytest tests/test_entities.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add science/model/src/science_model/entities.py science/model/tests/test_run_fingerprint.py
git commit -m "Add supplemental EvidenceLineEntity.run_refs (t077 P2)"
```

---

### Task 8b: Emit `run_refs` into the graph as `sci:runRef`

**Files:**
- Modify: `science/src/science_tool/graph/store/constants.py` (register `SCI_NS.runRef` in `PREDICATE_REGISTRY`, beside `sci:evidenceType` at `:229`)
- Modify: `science/src/science_tool/graph/materialize.py` (emit alongside the other evidence-line edges, near `:1034-1071`)
- Test: `science/tests/test_materialize_run_refs.py`

**Interfaces:**
- Consumes: Task 8's `EvidenceLineEntity.run_refs`.
- Produces: `(<line-uri>, SCI_NS.runRef, <workflow-run-uri>)` triples in the knowledge graph — one per `run_refs` entry — which Task 10's `_runs_for_line` unions into the resolved-run set.

**Why this task exists:** `materialize.py` emits evidence-line fields *explicitly*; there is no generic field→triple pass and no `sci:runRef` predicate today. Without this task, `run_refs` would be authored, validated, and then silently dropped at the graph boundary — an inert field that can never affect any verdict, which is precisely the failure mode this design rejects.

Staged lines (`belief_eligible: false`) are skipped, exactly as the neighbouring emitters do at `:1037` and `:1071`.

- [ ] **Step 1: Write the failing test**

```python
# science/tests/test_materialize_run_refs.py
from rdflib import URIRef

from science_tool.graph.io import SCI_NS


def test_run_refs_emit_sci_run_ref_triples(materialized_knowledge_for_evidence_line):
    """run_refs must reach the graph, or the field is inert."""
    knowledge, line_uri = materialized_knowledge_for_evidence_line(
        run_refs=["workflow-run:r1", "workflow-run:r2"], belief_eligible=True
    )
    targets = {str(o) for o in knowledge.objects(line_uri, SCI_NS.runRef)}
    assert len(targets) == 2
    assert any(t.endswith("workflow-run/r1") or t.endswith("r1") for t in targets)


def test_staged_line_emits_no_run_refs(materialized_knowledge_for_evidence_line):
    knowledge, line_uri = materialized_knowledge_for_evidence_line(
        run_refs=["workflow-run:r1"], belief_eligible=False
    )
    assert list(knowledge.objects(line_uri, SCI_NS.runRef)) == []


def test_no_run_refs_emits_nothing(materialized_knowledge_for_evidence_line):
    knowledge, line_uri = materialized_knowledge_for_evidence_line(run_refs=[], belief_eligible=True)
    assert list(knowledge.objects(line_uri, SCI_NS.runRef)) == []


def test_run_ref_predicate_is_registered():
    from science_tool.graph.store.constants import PREDICATE_REGISTRY

    assert any(entry["predicate"] == "sci:runRef" for entry in PREDICATE_REGISTRY)
```

> **Implementer:** write the `materialized_knowledge_for_evidence_line` fixture in `science/tests/conftest.py` by following how the existing evidence-line materialization tests build a `ProjectSources` and call the emitter. Reuse the project's `project_entity_uri` for the expected run URI rather than hard-coding a URI shape.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_materialize_run_refs.py -v`
Expected: FAIL — `AttributeError: runRef` / no matching `PREDICATE_REGISTRY` entry

- [ ] **Step 3: Write minimal implementation**

Register the predicate in `science/src/science_tool/graph/store/constants.py`, following the `sci:evidenceType` entry's exact dict shape at `:229`:

```python
    {
        "predicate": "sci:runRef",
        "domain": "sci:EvidenceLine",
        "range": "sci:WorkflowRun",
        "description": "Supplemental workflow-run reference widening the line's resolved-run set",
    },
```

Then, in `science/src/science_tool/graph/materialize.py`, beside the other evidence-line emitters:

```python
def _add_run_ref_edges(entity, line_uri, *, resolver, knowledge) -> None:
    """Emit sci:runRef for each authored run_refs entry.

    Staged lines (belief_eligible=False) are skipped — they must not enter the
    belief substrate, and run resolution is part of that substrate.
    """
    if not entity.belief_eligible:
        return
    for ref in entity.run_refs:
        knowledge.add((line_uri, SCI_NS.runRef, project_entity_uri(resolver.resolve_ref(ref))))
```

Call it from the same place the sibling evidence-line emitters are called.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science && uv run --frozen pytest tests/test_materialize_run_refs.py -v && uv run --frozen pytest tests/ -q -k materialize`
Expected: PASS (4 new tests; existing materialize tests green)

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/graph/store/constants.py science/src/science_tool/graph/materialize.py science/tests/test_materialize_run_refs.py science/tests/conftest.py
git commit -m "Emit evidence-line run_refs as sci:runRef (t077 P2)"
```

---

### Task 8c: Emit a graph-visible fingerprint marker (`sci:fingerprintPolicy`)

**Files:**
- Modify: `science/src/science_tool/graph/store/constants.py` (register `SCI_NS.fingerprintPolicy`)
- Modify: `science/src/science_tool/graph/materialize.py` (emit on workflow-run nodes)
- Test: `science/tests/test_materialize_run_fingerprint.py`

**Interfaces:**
- Consumes: Task 3's `WorkflowRunEntity.fingerprint`.
- Produces: `(<run-uri>, SCI_NS.fingerprintPolicy, Literal(fingerprint.fingerprint_policy))` for every workflow-run entity bearing a fingerprint. Task 10 builds its `is_fingerprinted` predicate from exactly this triple.

**Why this task exists:** run-resolution is graph-phase, so "does this run have a fingerprint?" must be answerable *from the graph*. Nothing else in the graph reveals it. And Task 7 deliberately emits **no** `validate` finding for a run with no fingerprint block. Without this marker the contract fails **open**: an unfingerprinted run would satisfy resolution, and no check anywhere would object. Emitting the *policy identity* rather than a bare boolean also lets a later `science-run-fingerprint/v2` be distinguished in-graph at no extra cost.

- [ ] **Step 1: Write the failing test**

```python
# science/tests/test_materialize_run_fingerprint.py
from rdflib import Literal

from science_tool.graph.io import SCI_NS


def test_fingerprinted_run_emits_policy_marker(materialized_knowledge_for_run):
    knowledge, run_uri = materialized_knowledge_for_run(with_fingerprint=True)
    assert list(knowledge.objects(run_uri, SCI_NS.fingerprintPolicy)) == [
        Literal("science-run-fingerprint/v1")
    ]


def test_unfingerprinted_run_emits_no_marker(materialized_knowledge_for_run):
    knowledge, run_uri = materialized_knowledge_for_run(with_fingerprint=False)
    assert list(knowledge.objects(run_uri, SCI_NS.fingerprintPolicy)) == []


def test_fingerprint_policy_predicate_is_registered():
    from science_tool.graph.store.constants import PREDICATE_REGISTRY

    assert any(entry["predicate"] == "sci:fingerprintPolicy" for entry in PREDICATE_REGISTRY)
```

> **Implementer:** write `materialized_knowledge_for_run` in `science/tests/conftest.py`, reusing the `local_fingerprint` fixture from Task 4 to build the `WorkflowRunEntity`.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_materialize_run_fingerprint.py -v`
Expected: FAIL — no `sci:fingerprintPolicy` triple; no matching `PREDICATE_REGISTRY` entry

- [ ] **Step 3: Write minimal implementation**

Register in `science/src/science_tool/graph/store/constants.py`, matching the `sci:evidenceType` dict shape at `:229`:

```python
    {
        "predicate": "sci:fingerprintPolicy",
        "domain": "sci:WorkflowRun",
        "range": "xsd:string",
        "description": "Policy version of the run's reproducibility fingerprint; presence means fingerprinted",
    },
```

Emit in `science/src/science_tool/graph/materialize.py` where workflow-run entities are projected:

```python
def _add_run_fingerprint_marker(entity, run_uri, *, knowledge) -> None:
    """Make fingerprint presence visible in the graph.

    Run resolution is graph-phase; without this triple an unfingerprinted run
    would silently satisfy the empirical-run invariant.
    """
    if entity.fingerprint is None:
        return
    knowledge.add((run_uri, SCI_NS.fingerprintPolicy, Literal(entity.fingerprint.fingerprint_policy)))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science && uv run --frozen pytest tests/test_materialize_run_fingerprint.py -v && uv run --frozen pytest tests/ -q -k materialize`
Expected: PASS (3 new tests; existing materialize tests green)

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/graph/store/constants.py science/src/science_tool/graph/materialize.py science/tests/test_materialize_run_fingerprint.py science/tests/conftest.py
git commit -m "Emit sci:fingerprintPolicy so run resolution cannot fail open (t077 P2)"
```

---

### Task 8d: Emit dataset derivation provenance into the graph

**Files:**
- Modify: `science/src/science_tool/graph/store/constants.py` (register `sci:derivationKind`, `sci:workflowRun`, `sci:memberOfParent`)
- Modify: `science/src/science_tool/graph/materialize.py` (emit beside `_add_produced_by_edges`, `:1183-1197`)
- Test: `science/tests/test_materialize_dataset_derivation.py`

**Interfaces:**
- Consumes: the `derivation` discriminated union on dataset entities.
- Produces, per dataset carrying a `derivation`:
  - `(<ds>, SCI_NS.derivationKind, Literal("workflow-run" | "workflow-recipe" | "member_of"))` — always;
  - `(<ds>, SCI_NS.workflowRun, <run-uri>)` — `DerivationBlock` only;
  - `(<ds>, SCI_NS.memberOfParent, <parent-ds-uri>)` — `MemberOfDerivationBlock` only.

**Why this task exists:** run-resolution is graph-phase and sees RDF nodes, not `DatasetEntity` objects. `materialize.py` emits only `sci:producedBy` today (`:1183-1197`); the `derivation` union never reaches the graph. Without these triples `_runs_for_line` has dataset URIs and no way to reach a run — hand-built TriG fixtures would pass while every real materialized graph failed to resolve a `DerivationBlock`. `derivationKind` is emitted as an explicit discriminator so `recipe-only` is *positively* distinguishable from "no derivation at all", rather than inferred from an absence.

- [ ] **Step 1: Write the failing test**

```python
# science/tests/test_materialize_dataset_derivation.py
from rdflib import Literal

from science_tool.graph.io import SCI_NS


def test_workflow_run_derivation_emits_kind_and_run_edge(materialized_knowledge_for_dataset):
    knowledge, ds_uri, run_uri = materialized_knowledge_for_dataset(kind="workflow-run")
    assert list(knowledge.objects(ds_uri, SCI_NS.derivationKind)) == [Literal("workflow-run")]
    assert list(knowledge.objects(ds_uri, SCI_NS.workflowRun)) == [run_uri]


def test_recipe_derivation_emits_kind_but_no_run_edge(materialized_knowledge_for_dataset):
    knowledge, ds_uri, _ = materialized_knowledge_for_dataset(kind="workflow-recipe")
    assert list(knowledge.objects(ds_uri, SCI_NS.derivationKind)) == [Literal("workflow-recipe")]
    assert list(knowledge.objects(ds_uri, SCI_NS.workflowRun)) == []


def test_member_of_derivation_emits_parent_edge(materialized_knowledge_for_dataset):
    knowledge, ds_uri, parent_uri = materialized_knowledge_for_dataset(kind="member_of")
    assert list(knowledge.objects(ds_uri, SCI_NS.derivationKind)) == [Literal("member_of")]
    assert list(knowledge.objects(ds_uri, SCI_NS.memberOfParent)) == [parent_uri]
    assert list(knowledge.objects(ds_uri, SCI_NS.workflowRun)) == []


def test_dataset_without_derivation_emits_no_kind(materialized_knowledge_for_dataset):
    knowledge, ds_uri, _ = materialized_knowledge_for_dataset(kind=None)
    assert list(knowledge.objects(ds_uri, SCI_NS.derivationKind)) == []


def test_derivation_predicates_are_registered():
    from science_tool.graph.store.constants import PREDICATE_REGISTRY

    names = {entry["predicate"] for entry in PREDICATE_REGISTRY}
    assert {"sci:derivationKind", "sci:workflowRun", "sci:memberOfParent"} <= names
```

> **Implementer:** write `materialized_knowledge_for_dataset` in `science/tests/conftest.py`, returning `(knowledge, dataset_uri, related_uri)` where `related_uri` is the run URI, the parent-dataset URI, or `None` depending on `kind`.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_materialize_dataset_derivation.py -v`
Expected: FAIL — `AttributeError: derivationKind` / missing `PREDICATE_REGISTRY` entries

- [ ] **Step 3: Write minimal implementation**

Register three predicates in `science/src/science_tool/graph/store/constants.py`, matching the existing dict shape:

```python
    {
        "predicate": "sci:derivationKind",
        "domain": "sci:Dataset",
        "range": "xsd:string",
        "description": "Discriminator for the dataset's derivation union (workflow-run|workflow-recipe|member_of)",
    },
    {
        "predicate": "sci:workflowRun",
        "domain": "sci:Dataset",
        "range": "sci:WorkflowRun",
        "description": "The workflow-run that produced this dataset (workflow-run derivations only)",
    },
    {
        "predicate": "sci:memberOfParent",
        "domain": "sci:Dataset",
        "range": "sci:Dataset",
        "description": "Parent collection for a member_of derivation; membership is not run-produced",
    },
```

Emit in `science/src/science_tool/graph/materialize.py`, beside `_add_produced_by_edges`:

```python
def _add_derivation_edges(entity, *, resolver, knowledge) -> None:
    """Make the dataset derivation union visible in the graph.

    Run resolution is graph-phase; without these triples a DerivationBlock's
    workflow_run is unreachable and recipe-only state is indistinguishable from
    having no derivation at all.
    """
    derivation = entity.derivation
    if derivation is None:
        return

    ds_uri = _entity_uri(entity.canonical_id)

    if isinstance(derivation, DerivationBlock):
        knowledge.add((ds_uri, SCI_NS.derivationKind, Literal("workflow-run")))
        knowledge.add((ds_uri, SCI_NS.workflowRun, _entity_uri(resolver.resolve_ref(derivation.workflow_run))))
    elif isinstance(derivation, WorkflowRecipeDerivationBlock):
        knowledge.add((ds_uri, SCI_NS.derivationKind, Literal("workflow-recipe")))
    elif isinstance(derivation, MemberOfDerivationBlock):
        knowledge.add((ds_uri, SCI_NS.derivationKind, Literal("member_of")))
        knowledge.add((ds_uri, SCI_NS.memberOfParent, _entity_uri(resolver.resolve_ref(derivation.parent_dataset))))
    else:
        raise TypeError(f"unhandled derivation shape {type(derivation).__name__} on {entity.canonical_id}")
```

The `else: raise` is deliberate — a new derivation arm must fail loudly here rather than silently resolve to nothing.

Call it from the same loop that calls `_add_produced_by_edges`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science && uv run --frozen pytest tests/test_materialize_dataset_derivation.py -v && uv run --frozen pytest tests/ -q -k "materialize or dataset"`
Expected: PASS (5 new tests; existing materialize/dataset tests green)

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/graph/store/constants.py science/src/science_tool/graph/materialize.py science/tests/test_materialize_dataset_derivation.py science/tests/conftest.py
git commit -m "Emit dataset derivation provenance so run resolution is graph-decidable (t077 P2)"
```

---

### Task 9: Resolution helpers — `own_derivation_run` and `resolved_empirical_runs`

**Files:**
- Create: `science/src/science_tool/graph/run_resolution.py`
- Test: `science/tests/test_run_resolution.py`

**Interfaces:**
- Consumes: Task 8d's `sci:derivationKind` / `sci:workflowRun` / `sci:memberOfParent` triples and the pre-existing `sci:producedBy`.
- Produces:
  - `class MemberOfCycleError(Exception)`
  - `class NoRunReason(StrEnum)`: `RECIPE_ONLY="recipe-only"`, `RUN_UNFINGERPRINTED="run-unfingerprinted"`, `CODE_ONLY_NO_RUN="code-only-no-run"`, `NO_PROVENANCE="no-provenance"`
  - `own_derivation_run(knowledge: Graph, dataset: URIRef) -> URIRef | None` — the dataset's *own* derivation edge; `None` for `member_of`.
  - `resolved_empirical_runs(knowledge: Graph, dataset: URIRef, is_fingerprinted: Callable[[URIRef], bool]) -> tuple[list[URIRef], list[NoRunReason]]` — walks `sci:memberOfParent` to the parent chain; raises `MemberOfCycleError` on a repeat.

**These operate on the graph, not on entity objects.** Resolution runs graph-phase, where `DatasetEntity` instances do not exist — only RDF nodes. An entity-object signature would be unusable by its only caller.

Two helpers, deliberately. A single one would smuggle the edge-level `member_of` exemption into evidence resolution.

**A run is not a fingerprinted run.** `is_fingerprinted` is not optional and has no default. A `workflow-run` derivation naming a run that bears no fingerprint contributes **nothing**, with reason `run-unfingerprinted`. Task 7 deliberately emits no `validate` finding for a run with no fingerprint block, so if this helper admitted bare run names the whole contract would fail open — an unfingerprinted run would satisfy resolution and nothing anywhere would object.

- [ ] **Step 1: Write the failing test**

```python
# science/tests/test_run_resolution.py
import pytest
from rdflib import Graph, Literal, URIRef

from science_tool.graph.io import SCI_NS
from science_tool.graph.run_resolution import (
    MemberOfCycleError, NoRunReason, own_derivation_run, resolved_empirical_runs,
)

DS = lambda n: URIRef(f"http://example.org/dataset/{n}")   # noqa: E731
RUN = lambda n: URIRef(f"http://example.org/workflow-run/{n}")  # noqa: E731

ALL_FINGERPRINTED = lambda _run: True    # noqa: E731
NONE_FINGERPRINTED = lambda _run: False  # noqa: E731


def _run_derived(g: Graph, ds: URIRef, run: URIRef) -> None:
    g.add((ds, SCI_NS.derivationKind, Literal("workflow-run")))
    g.add((ds, SCI_NS.workflowRun, run))


def _recipe_derived(g: Graph, ds: URIRef) -> None:
    g.add((ds, SCI_NS.derivationKind, Literal("workflow-recipe")))


def _member_of(g: Graph, ds: URIRef, parent: URIRef) -> None:
    g.add((ds, SCI_NS.derivationKind, Literal("member_of")))
    g.add((ds, SCI_NS.memberOfParent, parent))


def test_own_derivation_run_returns_the_run():
    g = Graph()
    _run_derived(g, DS("a"), RUN("r1"))
    assert own_derivation_run(g, DS("a")) == RUN("r1")


def test_own_derivation_run_is_none_for_member_of():
    g = Graph()
    _member_of(g, DS("m"), DS("a"))
    assert own_derivation_run(g, DS("m")) is None


def test_resolved_runs_recurse_through_member_of_to_parent():
    g = Graph()
    _run_derived(g, DS("a"), RUN("r1"))
    _member_of(g, DS("m"), DS("a"))
    runs, reasons = resolved_empirical_runs(g, DS("m"), ALL_FINGERPRINTED)
    assert runs == [RUN("r1")] and reasons == []


def test_run_without_a_fingerprint_contributes_nothing():
    """A run is not a fingerprinted run. Failing open here would void the contract."""
    g = Graph()
    _run_derived(g, DS("a"), RUN("r1"))
    runs, reasons = resolved_empirical_runs(g, DS("a"), NONE_FINGERPRINTED)
    assert runs == [] and reasons == [NoRunReason.RUN_UNFINGERPRINTED]


def test_member_of_parent_run_must_also_be_fingerprinted():
    g = Graph()
    _run_derived(g, DS("a"), RUN("r1"))
    _member_of(g, DS("m"), DS("a"))
    runs, reasons = resolved_empirical_runs(g, DS("m"), NONE_FINGERPRINTED)
    assert runs == [] and reasons == [NoRunReason.RUN_UNFINGERPRINTED]


def test_member_of_cycle_raises():
    g = Graph()
    _member_of(g, DS("a"), DS("b"))
    _member_of(g, DS("b"), DS("a"))
    with pytest.raises(MemberOfCycleError, match="dataset/a"):
        resolved_empirical_runs(g, DS("a"), ALL_FINGERPRINTED)


def test_recipe_only_contributes_nothing_with_reason():
    g = Graph()
    _recipe_derived(g, DS("c"))
    runs, reasons = resolved_empirical_runs(g, DS("c"), ALL_FINGERPRINTED)
    assert runs == [] and reasons == [NoRunReason.RECIPE_ONLY]


def test_produced_by_only_is_code_only_no_run():
    g = Graph()
    g.add((DS("d"), SCI_NS.producedBy, URIRef("http://example.org/code-file/x")))
    runs, reasons = resolved_empirical_runs(g, DS("d"), ALL_FINGERPRINTED)
    assert runs == [] and reasons == [NoRunReason.CODE_ONLY_NO_RUN]


def test_raw_external_dataset_is_no_provenance():
    runs, reasons = resolved_empirical_runs(Graph(), DS("e"), ALL_FINGERPRINTED)
    assert runs == [] and reasons == [NoRunReason.NO_PROVENANCE]


def test_unknown_derivation_kind_fails_loud():
    g = Graph()
    g.add((DS("x"), SCI_NS.derivationKind, Literal("teleportation")))
    with pytest.raises(ValueError, match="teleportation"):
        resolved_empirical_runs(g, DS("x"), ALL_FINGERPRINTED)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_run_resolution.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'science_tool.graph.run_resolution'`

- [ ] **Step 3: Write minimal implementation**

```python
# science/src/science_tool/graph/run_resolution.py
"""Resolve a dataset NODE to the fingerprinted workflow-run(s) that produced it.

Operates on the materialized graph, not on entity objects: run resolution is
graph-phase, where `DatasetEntity` instances do not exist. Reads the derivation
triples emitted by `materialize._add_derivation_edges`.

Two helpers, deliberately:

* `own_derivation_run` answers "does THIS dataset's own derivation edge name a
  run?" and returns None for `member_of`, because a membership edge is not
  run-produced.
* `resolved_empirical_runs` walks `member_of` to the parent chain and is what
  evidence validation uses.

Collapsing them would smuggle the edge-level exemption into evidence resolution.
Neither reads the disk. Recipe provenance is not a run; code provenance is not a
run either; and a run without a fingerprint is not a fingerprinted run.
"""

from __future__ import annotations

from collections.abc import Callable
from enum import StrEnum

from rdflib import Graph, URIRef

from science_tool.graph.io import SCI_NS

KIND_WORKFLOW_RUN = "workflow-run"
KIND_WORKFLOW_RECIPE = "workflow-recipe"
KIND_MEMBER_OF = "member_of"


class MemberOfCycleError(Exception):
    """A member_of parent chain revisits a dataset."""


class NoRunReason(StrEnum):
    RECIPE_ONLY = "recipe-only"
    RUN_UNFINGERPRINTED = "run-unfingerprinted"
    CODE_ONLY_NO_RUN = "code-only-no-run"
    NO_PROVENANCE = "no-provenance"


def _derivation_kind(knowledge: Graph, dataset: URIRef) -> str | None:
    value = knowledge.value(dataset, SCI_NS.derivationKind)
    return None if value is None else str(value)


def own_derivation_run(knowledge: Graph, dataset: URIRef) -> URIRef | None:
    """The run named by this dataset's OWN derivation edge, or None."""
    if _derivation_kind(knowledge, dataset) != KIND_WORKFLOW_RUN:
        return None
    return knowledge.value(dataset, SCI_NS.workflowRun)


def resolved_empirical_runs(
    knowledge: Graph,
    dataset: URIRef,
    is_fingerprinted: Callable[[URIRef], bool],
) -> tuple[list[URIRef], list[NoRunReason]]:
    """Fingerprinted runs this dataset resolves to, walking member_of to the parent.

    `is_fingerprinted` is required and has no default: naming a workflow-run is
    not the same as resolving to a *fingerprinted* one.
    """
    visited: set[URIRef] = set()
    current = dataset

    while True:
        if current in visited:
            raise MemberOfCycleError(f"member_of cycle revisits {current}")
        visited.add(current)

        kind = _derivation_kind(knowledge, current)

        if kind == KIND_WORKFLOW_RUN:
            run = knowledge.value(current, SCI_NS.workflowRun)
            if run is None:
                return [], [NoRunReason.NO_PROVENANCE]
            if not is_fingerprinted(run):
                return [], [NoRunReason.RUN_UNFINGERPRINTED]
            return [run], []

        if kind == KIND_WORKFLOW_RECIPE:
            return [], [NoRunReason.RECIPE_ONLY]

        if kind == KIND_MEMBER_OF:
            parent = knowledge.value(current, SCI_NS.memberOfParent)
            if parent is None:
                return [], [NoRunReason.NO_PROVENANCE]
            current = parent
            continue

        if kind is not None:
            raise ValueError(f"unknown sci:derivationKind {kind!r} on {current}")

        # No derivation. Code-only provenance is not a run.
        if (current, SCI_NS.producedBy, None) in knowledge:
            return [], [NoRunReason.CODE_ONLY_NO_RUN]
        return [], [NoRunReason.NO_PROVENANCE]
```

> **Verified:** `MemberOfDerivationBlock.parent_dataset` is a `dataset:<slug>` reference (`science/model/src/science_model/packages/schema.py:245`), validated by `_parent_id` at `:248-253`. No seam here.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science && uv run --frozen pytest tests/test_run_resolution.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/graph/run_resolution.py science/tests/test_run_resolution.py
git commit -m "Resolve datasets to producing runs; code and recipe are not runs (t077 P2)"
```

---

### Task 10: Graph-phase `empirical_run_resolution` row

**Files:**
- Modify: `science/src/science_tool/graph/store/validation.py:137` (beside `patch_membership_convenience`)
- Test: `science/tests/test_graph_validate_run_resolution.py`

**Interfaces:**
- Consumes: Task 9's `resolved_empirical_runs`, `NoRunReason`, `MemberOfCycleError`; `graph.dataset_independence.dependence_datasets_by_line`.
- Produces: `validate_empirical_run_resolution(dataset: Dataset) -> list[str]` returning sorted error strings; a `{"check": "empirical_run_resolution", "status": ..., "details": ...}` row in `validate_graph_dataset`.

Status mapping for the P2 (warn-only) phase: unresolved / recipe-only → `warn`; a `member_of` cycle → `fail`. Task 11's P4 flip changes the first to `fail`; do **not** do that here.

Resolution reuses `dependence_datasets_by_line` on the **same** graphs the dataset-QA ceiling uses, which is what makes substrate parity structural.

- [ ] **Step 1: Write the failing test**

```python
# science/tests/test_graph_validate_run_resolution.py
from science_tool.graph.store.validation import validate_graph_dataset


def _dataset_from_trig(trig: str):
    from rdflib import Dataset
    ds = Dataset()
    ds.parse(data=trig, format="trig")
    return ds


def _row(rows, name):
    return next(r for r in rows if r["check"] == name)


def test_row_is_always_present_even_with_no_evidence_lines():
    rows, _ = validate_graph_dataset(_dataset_from_trig("@prefix ex: <http://e/> . ex:a ex:b ex:c ."))
    assert _row(rows, "empirical_run_resolution")["status"] == "pass"


def test_unresolved_empirical_line_warns_in_p2(empirical_line_without_run_trig):
    rows, has_failures = validate_graph_dataset(_dataset_from_trig(empirical_line_without_run_trig))
    row = _row(rows, "empirical_run_resolution")
    assert row["status"] == "warn"
    assert not has_failures  # P2 is warn-only; P4 flips this


def test_resolved_empirical_line_passes(empirical_line_with_run_trig):
    rows, has_failures = validate_graph_dataset(_dataset_from_trig(empirical_line_with_run_trig))
    assert _row(rows, "empirical_run_resolution")["status"] == "pass"
    assert not has_failures


def test_member_of_cycle_fails(member_of_cycle_trig):
    rows, has_failures = validate_graph_dataset(_dataset_from_trig(member_of_cycle_trig))
    row = _row(rows, "empirical_run_resolution")
    assert row["status"] == "fail"
    assert "dataset.member-of-cycle" in row["details"]
    assert has_failures


def test_derivation_run_without_fingerprint_still_warns(empirical_line_with_unfingerprinted_run_trig):
    """The contract must fail CLOSED: naming a run is not bearing a fingerprint."""
    rows, _ = validate_graph_dataset(_dataset_from_trig(empirical_line_with_unfingerprinted_run_trig))
    row = _row(rows, "empirical_run_resolution")
    assert row["status"] == "warn"
    assert "run-unfingerprinted" in row["details"]


def test_run_refs_to_unfingerprinted_run_still_warns(line_with_unfingerprinted_run_ref_trig):
    """run_refs must not be a back door around the fingerprint requirement."""
    rows, _ = validate_graph_dataset(_dataset_from_trig(line_with_unfingerprinted_run_ref_trig))
    row = _row(rows, "empirical_run_resolution")
    assert row["status"] == "warn"
    assert "run-unfingerprinted" in row["details"]


def test_run_refs_to_fingerprinted_run_resolves_a_code_only_dataset(
    line_with_produced_by_dataset_and_fingerprinted_run_ref_trig,
):
    """The rescue case: sound dataset provenance that cannot itself name a run."""
    rows, _ = validate_graph_dataset(
        _dataset_from_trig(line_with_produced_by_dataset_and_fingerprinted_run_ref_trig)
    )
    assert _row(rows, "empirical_run_resolution")["status"] == "pass"
```

> **Implementer:** build the three `*_trig` fixtures in `science/tests/conftest.py` by copying the graph-construction style used in `science/tests/test_dataset_independence.py:338-360` (which builds `knowledge` / `provenance` graphs and an evidence line with a `dependence` dataset usage). Each fixture returns a TriG string. Do not invent predicates — reuse `SCI_NS` terms from `science_tool.graph.io`.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_graph_validate_run_resolution.py -v`
Expected: FAIL — `StopIteration` (no `empirical_run_resolution` row)

- [ ] **Step 3: Write minimal implementation**

Add to `science/src/science_tool/graph/store/validation.py`, importing at the top and inserting the row immediately after the `patch_membership_convenience` block (currently `:137-155`):

```python
from science_tool.graph.run_resolution import MemberOfCycleError

...

def _is_fingerprinted(knowledge, run_uri: URIRef) -> bool:
    """A run bears a fingerprint iff it carries sci:fingerprintPolicy (Task 8c)."""
    return (run_uri, SCI_NS.fingerprintPolicy, None) in knowledge


def validate_empirical_run_resolution(dataset: Dataset) -> tuple[list[str], bool]:
    """Belief-eligible empirical lines must resolve to a FINGERPRINTED run.

    Returns (messages, is_fatal). A member_of cycle is fatal; unresolved lines
    warn during P2 and become fatal at the P4 flip.

    `MemberOfCycleError` originates inside `_runs_for_line` (which calls
    `resolved_empirical_runs`), NOT inside `dependence_datasets_by_line`. The
    try/except must therefore wrap the per-line loop, and a cycle short-circuits
    the whole check as fatal.
    """
    from science_tool.graph.dataset_independence import dependence_datasets_by_line

    knowledge, provenance = _knowledge_and_provenance(dataset)
    by_line = dependence_datasets_by_line(knowledge, provenance)

    messages: list[str] = []
    for line, datasets in sorted(by_line.items()):
        try:
            runs, reasons = _runs_for_line(knowledge, line, datasets)
        except MemberOfCycleError as exc:
            return [f"{line}: dataset.member-of-cycle ({exc})"], True
        if runs:
            continue
        if NoRunReason.RECIPE_ONLY in reasons:
            messages.append(f"{line}: evidence.empirical-run-recipe-only")
        else:
            detail = ", ".join(sorted({r.value for r in reasons})) or "no-provenance"
            messages.append(f"{line}: evidence.empirical-run-unresolved ({detail})")
    return sorted(messages), False
```

and the row, mirroring the `patch_membership_convenience` shape exactly:

```python
    run_messages, run_fatal = validate_empirical_run_resolution(dataset)
    if run_messages:
        rows.append(
            {
                "check": "empirical_run_resolution",
                "status": "fail" if run_fatal else "warn",
                "details": f"{len(run_messages)} empirical line(s) without a fingerprinted run: {run_messages[0]}",
            }
        )
    else:
        rows.append(
            {
                "check": "empirical_run_resolution",
                "status": "pass",
                "details": "all belief-eligible empirical lines resolve to a fingerprinted run",
            }
        )
```

> **Implementer:** `_knowledge_and_provenance(dataset)` and `_runs_for_line(...)` are the two seams you must write. Follow `graph/dataset_qa.py:60-91` for how it obtains the knowledge/provenance graphs from a materialized dataset and reads `SCI_NS.evidenceType` off a line; restrict to `EvidenceType.EMPIRICAL_DATA` exactly as `dataset_qa.py:88` does.
>
> `_runs_for_line(knowledge, line, datasets) -> tuple[list[URIRef], list[NoRunReason]]` must:
> 1. build `is_fingerprinted = partial(_is_fingerprinted, knowledge)`;
> 2. for each dataset URI, call `resolved_empirical_runs(knowledge, ds, is_fingerprinted)` and accumulate runs + reasons (letting `MemberOfCycleError` propagate to the caller). All three arguments are graph values — there is no entity lookup and no disk access;
> 3. union in the line's `SCI_NS.runRef` objects **filtered through the same `is_fingerprinted` predicate** — a `run_refs` entry naming an unfingerprinted run contributes nothing and adds `NoRunReason.RUN_UNFINGERPRINTED`;
> 4. return `([], reasons)` when the union is empty.
>
> Filtering `run_refs` through the same predicate is what stops `run_refs` from becoming a back door around the fingerprint requirement.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science && uv run --frozen pytest tests/test_graph_validate_run_resolution.py -v && uv run --frozen pytest tests/test_graph_validate_patch_convenience.py -q`
Expected: PASS (4 new tests; the existing convenience-edge row still green)

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/graph/store/validation.py science/tests/test_graph_validate_run_resolution.py science/tests/conftest.py
git commit -m "Add graph-phase empirical_run_resolution check (t077 P2)"
```

---

### Task 11: Determinism and substrate-parity regression tests

**Files:**
- Test: `science/tests/test_run_fingerprint_policy.py`, `science/tests/test_graph_validate_run_resolution.py`, `science/tests/validate/test_checks_evidence_lines.py`

**Interfaces:**
- Consumes: everything above. Produces no new source.

These are the tests that pin the design's two hardest-won properties. They must exist even though no production code changes.

- [ ] **Step 1: Write the failing test**

```python
# append to science/tests/test_graph_validate_run_resolution.py
def test_verdict_is_identical_with_and_without_data_files_on_disk(
    tmp_path, empirical_line_with_run_trig
):
    """THE load-bearing test: obligations derive from DECLARED facts, never a disk probe.

    Validate must return the same rows whether or not the run's data files exist.
    """
    ds = _dataset_from_trig(empirical_line_with_run_trig)
    before, _ = validate_graph_dataset(ds)

    data = tmp_path / "results" / "w1" / "r1"
    data.mkdir(parents=True)
    (data / "out.csv").write_text("x,y\n1,2\n", encoding="utf-8")
    after_present, _ = validate_graph_dataset(_dataset_from_trig(empirical_line_with_run_trig))

    (data / "out.csv").unlink()
    after_absent, _ = validate_graph_dataset(_dataset_from_trig(empirical_line_with_run_trig))

    assert before == after_present == after_absent
```

```python
# append to science/tests/validate/test_checks_evidence_lines.py
def test_run_refs_only_line_still_fails_dataset_usage_check(tmp_path):
    """run_refs must NEVER open a bypass around the dataset-QA substrate.

    A belief-eligible empirical line with run_refs but no dataset_usage stays
    invalid: it would otherwise skip dependence_datasets_by_line, and with it the
    dataset-QA ceiling.
    """
    from science_tool.validate.checks.evidence_lines import (
        check_belief_eligible_empirical_has_dataset_usage,
    )

    ctx = _evidence_ctx(  # existing helper in this module
        tmp_path,
        frontmatter=(
            "id: evidence-line:e1\nkind: evidence-line\ntitle: E1\n"
            "stance: supports\ntarget: hypothesis:h1\n"
            "evidence_type: empirical_data\nbelief_eligible: true\n"
            "run_refs: [workflow-run:r1]\n"
        ),
    )
    results = list(check_belief_eligible_empirical_has_dataset_usage(ctx))
    assert [r.rule for r in results] == ["evidence.empirical.requires_dataset_usage"]
```

```python
# append to science/tests/test_run_fingerprint_policy.py
def test_obligation_never_consults_the_filesystem(local_fingerprint, monkeypatch):
    """Obligation resolution must not touch the disk."""
    import pathlib

    def _boom(*a, **k):
        raise AssertionError("obligation resolution touched the filesystem")

    monkeypatch.setattr(pathlib.Path, "exists", _boom)
    monkeypatch.setattr(pathlib.Path, "is_file", _boom)
    fp = local_fingerprint()
    assert evaluate_fingerprint(fp) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_graph_validate_run_resolution.py::test_verdict_is_identical_with_and_without_data_files_on_disk tests/test_run_fingerprint_policy.py::test_obligation_never_consults_the_filesystem -v`
Expected: FAIL initially only if a disk probe crept in. If they pass immediately, that is the correct outcome — commit them as regression guards.

- [ ] **Step 3: Write minimal implementation**

No production code. If `test_obligation_never_consults_the_filesystem` fails, remove the offending filesystem call from `run_fingerprint_policy.py` — the obligation table must be a pure function of declared facts.

- [ ] **Step 4: Run the full suites**

Run:
```bash
cd science/model && uv run --frozen pytest
cd ../ && uv run --frozen pytest
uv run ruff check && uv run pyright
```
Expected: all green, no new lint or type errors.

- [ ] **Step 5: Commit**

```bash
git add science/tests/
git commit -m "Pin determinism and substrate-parity invariants (t077 P2)"
```

---

## Self-review notes

**Spec coverage.** §A → Tasks 1–3. §B obligation table + reconciliation gate → Task 4; evaluation → Task 5. §C resolution rule, two helpers, `member_of` recursion + cycle, reason tokens → Tasks 9–10; `run_refs` → Tasks 8 and 8b. §D layer split, findings, capture chokepoint → Tasks 6, 7, 10. §E migration → **deliberately excluded** (P3, out of scope). Testing section → distributed, with the two load-bearing tests isolated in Task 11.

**Three gaps found in review and closed — all of them ways the contract could have shipped hollow:**

1. **`run_refs` would never reach the graph.** `materialize.py` emits evidence-line fields explicitly and no `sci:runRef` predicate exists, so `run_refs` would be authored, validated, then dropped at the graph boundary — an inert field that could never affect a verdict. → **Task 8b**.
2. **Resolution would have failed OPEN.** `resolved_empirical_runs` returned any `DerivationBlock.workflow_run`, and nothing made fingerprint presence visible in the graph. Since Task 7 deliberately emits no finding for a run with no fingerprint block, an entirely unfingerprinted run would have satisfied the whole contract. → **Task 8c** (`sci:fingerprintPolicy`), a required `is_fingerprinted` predicate on `resolved_empirical_runs`, the `run-unfingerprinted` reason, and `run_refs` filtered through the same predicate so it cannot become a back door.
3. **Nothing would ever write a fingerprint.** Deferring the CLI wiring left P1+P2 with a model, a validator, and a pure function, but no normal path producing captured fingerprints. → **Task 6b** wires `cli.py:7291` now; only `git_commit` removal stays in P3.

4. **Resolution had nothing to walk.** `materialize.py` emits only `sci:producedBy`; the `derivation` union never reached the graph, and `resolved_empirical_runs` took `DatasetEntity` objects that **do not exist graph-phase**. Hand-built TriG fixtures would have gone green while every real materialized graph failed to resolve a `DerivationBlock`. → **Task 8d** emits `sci:derivationKind` / `sci:workflowRun` / `sci:memberOfParent`, and Task 9 was rewritten to walk triples (`knowledge: Graph, dataset: URIRef`), with an unknown `derivationKind` raising rather than silently resolving to nothing.

**Also corrected:**
- `MemberOfCycleError` originates in `resolved_empirical_runs` (inside `_runs_for_line`), not in `dependence_datasets_by_line`. Task 10's try/except wraps the per-line loop and maps the cycle to a `fail` row carrying `dataset.member-of-cycle`.
- `persist_run_fingerprint` is **not** idempotent: its own frontmatter write dirties the tree, so a second capture sees `code_dirty=true`. The plan pins that as the documented behavior rather than asserting a false idempotence, and explicitly forbids "fixing" it by excluding the run file from the dirty check.

**Deferred to P3/P4, tracked, not forgotten:**
- `DerivationBlock.git_commit` removal + `science-pkg-entity-1.1.json` + commons sweep. `register-run` keeps copying `git_commit` down during P1/P2; the two coexist.
- WARN→ERROR flip for `empirical_run_resolution` and `run.fingerprint-incomplete`.

**Seams the implementer must resolve against real code** (flagged inline, not hand-waved):
- `_knowledge_and_provenance` / `_runs_for_line` in Task 10 must mirror `graph/dataset_qa.py:60-91`, restricting to `EvidenceType.EMPIRICAL_DATA` exactly as `dataset_qa.py:88` does.
- `_run_input_manifest` / `_run_output_manifest` / `_rewrite_run_frontmatter` in Task 6b, derived from the run entity's existing `manifest_path` / `resources`.
- The TriG and materialization fixtures (`empirical_line_*_trig`, `member_of_cycle_trig`, `line_with_unfingerprinted_run_ref_trig`, `line_with_produced_by_dataset_and_fingerprinted_run_ref_trig`, `materialized_knowledge_for_evidence_line`, `materialized_knowledge_for_run`), built from the existing graph-construction style in `tests/test_dataset_independence.py:338-360`.

**Verified against the code while planning** (no longer seams): `MemberOfDerivationBlock.parent_dataset` (`packages/schema.py:245`); `resolve_path_policy("workflow-run") → entities/workflow-runs`; `science_model` resolves to the worktree's own `model/src`, so no `PYTHONPATH` override is needed.

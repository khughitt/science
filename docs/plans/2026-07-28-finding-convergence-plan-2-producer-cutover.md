# AuditFinding Convergence — Plan 2: Producer Cutover

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox
> (`- [ ]`) syntax for tracking.

**Goal:** Atomically converge every deterministic issue producer onto
`FindingProducerResult`, publish `AuditReport` from `science health`, preserve the
current acceptance boundary, and remove the heterogeneous health schema.

**Architecture:** Three preparatory tasks add generic producer execution, validation
declaration helpers, and report/acceptance assembly while the real producer registry
remains empty. Task 4 is the one atomic cutover: validation checks, health checks, and
`data_audit` all begin returning the composed channel; health switches to `AuditReport`;
the old report/count/render paths are deleted; and the phase-boundary ratchet is replaced
by filesystem-derived completeness guards in that same commit. No reader accepts both
the old and new producer shapes.

**Tech Stack:** Python 3.12+, Pydantic v2, Click, Rich, pytest. `science-model` remains
independent of `science_tool`.

**Design:** [`2026-07-27-finding-convergence-design.md`](2026-07-27-finding-convergence-design.md),
revision 20 (`2f9e5eef`). Section references below are to that document.

## Global Constraints

- **Run package commands from `science/`.** There is no root `pyproject.toml`.
- **Treat each command block as starting at the worktree root.** Do not carry a prior
  block's `cd` into the next block.
- **Do not run two test suites concurrently in this worktree.** Health and validation
  tests share generated-output paths.
- **Run scoped tests inside tasks.** Reserve the full tool suite for Task 5 with an
  explicit long timeout.
- **One real producer shape only:** `FindingProducerResult`. Never add a passthrough for
  `InstrumentResult`, tuples, row lists, mappings, or the old `HealthReport`.
- **One public health schema only:** `AuditReport` schema version 2. Do not retain a
  compatibility serializer or a `--legacy` output option.
- **Composition, not inheritance:** `FindingProducerResult` contains
  `InstrumentResult[AuditFinding]` plus `ProducerMetrics`; `InstrumentResult` itself is
  unchanged.
- **Metrics are validated at the generic producer boundary.** A wired producer with no
  declared metrics schema emits no metrics; an unwired producer emits no metrics, skips
  schema validation, and is omitted from `report.metrics`.
- **Project configuration selects active kind instances only.** Severity functions,
  sections, visibility, subject contracts, identity qualifiers, and all other family
  policy remain toolkit-owned.
- **Every ordinary validation issue has explicit semantic identity.** Its closed
  qualifier schema requires `key: list[str]`; the key contains stable predicate
  components, never message text, severity, line, or list position. Rules whose
  specialized identity is frozen in the design keep that schema instead.
- **Validation acceptance in Plan 2 is current-shape only.** Health offers only canonical
  producer `validate`, at `warn` and `error`, to `entry_suppresses`; wildcard severity
  keeps its current behavior. `science validate` remains warn-only. Plan 3 removes the
  current-shape health matcher when it installs fingerprint-keyed entries.
- **No autonomous behavior, migration command, review quorum, remediation execution, or
  finding-to-task promotion** belongs in this plan.
- **`archive_lag` stays retired.** Commit `4162196f` removed it before this plan's
  baseline; do not reconstruct it.
- **Conventional commits only.** No AI-attribution trailers, no compatibility layers, no
  `Unified` prefix.

## File Structure

### New focused modules

| File | Responsibility |
|---|---|
| `science/src/science_tool/findings/catalog.py` | Late-import the three producer namespaces and build one project-scoped registry from the canonical active entity registry. |
| `science/src/science_tool/findings/reporting.py` | Deterministic ordering and construction of the frozen `AuditReport`; no producer execution. |
| `science/src/science_tool/validate/findings.py` | Validation-only rule helpers, subject/evidence conversion, qualifier schemas, and internal result-to-`AuditFinding` conversion. |
| `science/src/science_tool/validate/observations.py` | Frozen one-pass batch partitioning finding candidates, metrics, and command-only notices before the exact producer projection. |
| `science/src/science_tool/validate/runtime.py` | Toolkit-owned declarations for runner failures and sidecar-removal findings; the producer for observations not owned by one canonical check module. |
| `science/src/science_tool/graph/health_checks/schema_invalid.py` | Explicit producer for core entities skipped during non-strict health loading; replaces report-reader synthesis. |
| `science/tests/test_findings_execution.py` | Uniform-channel, metrics, duplicate-identity, and active-kind registry tests. |
| `science/tests/test_findings_reporting.py` | Report ordering, totals, unwired omission, and acceptance-channel tests. |
| `science/tests/test_finding_convergence.py` | Cross-namespace count ledger, namespace guards, renderer refusal, and retired-surface assertions. |
| `science/tests/validate/test_finding_families.py` | Dynamic-family expansion, gate/severity preservation, prose split, and emitted/declaration binding. |

### Existing modules changed at the atomic cutover

- `science/src/science_tool/validate/result.py`, `checks/__init__.py`, `runner.py`,
  `gates.py`, `acceptance.py`, `cli.py`, and every registered module under
  `validate/checks/`.
- `science/src/science_tool/graph/health.py`, `health_count.py`,
  `health_projection.py`, `health_cli.py`, `health_checks/base.py`,
  `health_checks/__init__.py`, and every registered producer under `health_checks/`.
- `science/src/science_tool/data_audit.py`, `data_cli.py`.
- `science/src/science_tool/findings/producers.py`, `findings/cli.py`.
- The existing health, validation, data-audit, registry, projection, budget, acceptance,
  telemetry, and CLI tests named in Task 4.

## Design-test accountability

Plan 1 already owns design tests 2–3 and 6–23 at the model/storage/ingestion layer; this
plan keeps those suites green and adds the runtime integration half of tests 4 and 15.
Plan 2 directly lands:

| Design test | Plan step |
|---|---|
| 1 uniform channel | Task 1 step 1; Task 4 steps 1, 3, 6, 9 |
| 4 project selects instances, not policy | Task 1 step 4; Task 4 family tests |
| 5 renderer clean refusal | Task 4 steps 1 and 8 |
| 15 producer metrics | Task 1 step 1; Task 4 prose/health/data paths |
| 24 Plan 2 wildcard half | Task 3 steps 1–2 |
| 26 count ledger | Task 4 step 11 |
| 27 presentation order | Task 3 step 3; Task 4 steps 6 and 8 |
| 28 metrics are not findings | Task 2; Task 4 prose and health ledger |
| 29 namespace completeness | Task 4 steps 1 and 10 |
| 30 dataset declaration equality | Task 4 steps 6 and 11 |
| 31 validation families and grammar | Task 4 step 4 |
| 32 acceptance scope | Task 3 step 2; Task 4 step 7 |

Plan 3 owns the duplicate/stale half of test 24 and all of test 25. This plan must not
pre-build their replacement entry reader.

---

### Task 1: Generic producer execution and project-scoped registry

**Files:**
- Create: `science/src/science_tool/findings/catalog.py`
- Modify: `science/src/science_tool/findings/producers.py`
- Modify: `science/src/science_tool/findings/cli.py`
- Modify: `science/tests/test_findings_registry.py`
- Modify: `science/tests/test_findings_ingest.py`
- Modify: `science/tests/test_findings_isolation.py`
- Create: `science/tests/test_findings_execution.py`
- Test: `science/tests/test_findings_cli.py`

**Interfaces:**
- Produces:
  - `FindingProducerResult`
  - `validate_producer_result(registry, producer_id, value) -> FindingProducerResult`
  - `KindRuleFactory`
  - `build_registry(producers, *, active_kinds) -> FindingRegistry`
  - `build_project_registry(project_root) -> FindingRegistry`
- Consumes:
  - `registry_for_project(project_root).registered_kinds()` — the existing canonical
    profile/catalog/core authority.
  - `FindingRule.build`, `FindingRule.identity_subset`, and `finding_fingerprint`.

- [ ] **Step 1: Write the failing execution-boundary tests**

```python
# science/tests/test_findings_execution.py
from pathlib import Path

import pytest
from pydantic import BaseModel, ConfigDict, ValidationError
from science_model.audit import (
    AuditFinding,
    FindingRule,
    FindingSection,
    ProducerMetrics,
    ProjectSubject,
)

from science_tool.findings.producers import (
    FindingProducer,
    FindingProducerResult,
    RegistryError,
    build_registry,
    validate_producer_result,
)
from science_tool.instruments import InstrumentResult


class EmptyQ(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CountMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")
    count: int


SECTION = FindingSection(id="test", title="Test", section_order=1)
RULE = FindingRule(
    id="test.problem",
    severities={"warn"},
    subject_types={"project"},
    qualifier_schema=EmptyQ,
    title="Problem",
    section=SECTION.id,
    display_order=1,
)
PRODUCER = FindingProducer(
    producer_id="test-producer",
    namespace="health_checks",
    source_module="graph/health_checks/test_producer.py",
    rules=(RULE,),
    sections=(SECTION,),
    metrics_schema=CountMetrics,
)


def _registry():
    return build_registry([PRODUCER], active_kinds=frozenset())


def _finding(message="m"):
    return RULE.build(
        subject=ProjectSubject(),
        severity="warn",
        qualifiers={},
        message=message,
    )


@pytest.mark.parametrize(
    "wrong",
    [
        InstrumentResult.ok([_finding()]),
        (_finding(), {}),
        [_finding()],
        {"instrument": InstrumentResult.ok([_finding()]), "metrics": {}},
    ],
)
def test_registered_boundary_rejects_every_noncomposed_shape(wrong):
    with pytest.raises(TypeError, match="FindingProducerResult"):
        validate_producer_result(_registry(), "test-producer", wrong)


def test_wired_metrics_cross_the_declared_schema_strictly():
    valid = FindingProducerResult(
        instrument=InstrumentResult.ok([_finding()]),
        metrics=ProducerMetrics(count=2),
    )
    assert validate_producer_result(_registry(), "test-producer", valid) is valid
    invalid = FindingProducerResult(
        instrument=InstrumentResult.empty(),
        metrics=ProducerMetrics(count="2"),
    )
    with pytest.raises(RegistryError, match="metrics invalid"):
        validate_producer_result(_registry(), "test-producer", invalid)


def test_unwired_omits_metrics_even_when_schema_has_required_fields():
    result = FindingProducerResult(
        instrument=InstrumentResult.unwired(code="not-connected", reason="no source"),
    )
    assert validate_producer_result(_registry(), "test-producer", result) is result
    with pytest.raises(ValidationError, match="unwired producer cannot report metrics"):
        FindingProducerResult(
            instrument=InstrumentResult.unwired(code="not-connected"),
            metrics=ProducerMetrics(count=1),
        )


def test_same_identity_with_different_prose_is_rejected_at_the_producer():
    result = FindingProducerResult(
        instrument=InstrumentResult.ok([_finding("first"), _finding("second")]),
    )
    with pytest.raises(RegistryError, match="duplicate finding identity"):
        validate_producer_result(_registry(), "test-producer", result)
```

- [ ] **Step 2: Run the tests and confirm the missing boundary**

Run:

```bash
cd science
uv run --frozen pytest tests/test_findings_execution.py tests/test_findings_registry.py -q
```

Expected: FAIL because `FindingProducerResult`, `validate_producer_result`, and the
required `active_kinds` registry contract do not exist.

- [ ] **Step 3: Implement the composed result and the one validation boundary**

```python
# science/src/science_tool/findings/producers.py
# Add Field, AuditFinding, ProducerMetrics, finding_fingerprint, and
# InstrumentResult to this module's existing imports. Insert this model before
# FindingRegistry and the validator function after build_registry.


class FindingProducerResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    instrument: InstrumentResult[AuditFinding]
    metrics: ProducerMetrics = Field(default_factory=ProducerMetrics)

    @model_validator(mode="after")
    def _unwired_has_no_metrics(self) -> "FindingProducerResult":
        if self.instrument.status == "unwired" and self.metrics.model_dump(mode="json"):
            raise ValueError("an unwired producer cannot report metrics")
        return self


def validate_producer_result(
    registry: FindingRegistry,
    producer_id: str,
    value: object,
) -> FindingProducerResult:
    if type(value) is not FindingProducerResult:
        raise TypeError(
            f"registered producer {producer_id!r} must return FindingProducerResult, "
            f"got {type(value).__name__}"
        )
    result = value
    producer = registry.producers_by_id.get(producer_id)
    if producer is None:
        raise RegistryError(f"unregistered producer {producer_id!r}")
    if result.instrument.status == "unwired":
        return result

    registry.validate_metrics(
        producer_id,
        result.metrics.model_dump(mode="json"),
    )
    seen: set[str] = set()
    for finding in result.instrument.rows:
        rule = registry.rule(finding.rule_id)
        rebuilt = rule.build(
            subject=finding.subject,
            severity=finding.severity,
            qualifiers=finding.qualifiers,
            message=finding.message,
            evidence=list(finding.evidence),
        )
        if rebuilt != finding:
            raise RegistryError(
                f"{producer_id!r} emitted a noncanonical {finding.rule_id!r} finding"
            )
        finding_id = finding_fingerprint(
            rule_id=finding.rule_id,
            subject=finding.subject,
            identity_qualifiers=rule.identity_subset(finding.qualifiers),
        )
        if finding_id in seen:
            raise RegistryError(
                f"{producer_id!r} emitted duplicate finding identity {finding_id}"
            )
        seen.add(finding_id)
    return result
```

Do not add any coercing constructor around `value`. Exact runtime type is the uniform
channel ratchet.

- [ ] **Step 4: Make registry expansion explicit and project-scoped**

In `findings/producers.py`, add:

```python
from collections.abc import Callable

KindRuleFactory = Callable[[frozenset[str]], tuple[FindingRule, ...]]


class FindingProducer(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    producer_id: str
    namespace: str
    source_module: str
    rules: tuple[FindingRule, ...]
    sections: tuple[FindingSection, ...] = ()
    metrics_schema: type[BaseModel] | None = None
    remediators: frozenset[str] = frozenset()
    kind_rule_factory: KindRuleFactory | None = None

    def expanded_rules(self, active_kinds: frozenset[str]) -> tuple[FindingRule, ...]:
        derived = (
            self.kind_rule_factory(active_kinds)
            if self.kind_rule_factory is not None
            else ()
        )
        return (*self.rules, *derived)
```

Change `build_registry` to require the keyword-only
`active_kinds: frozenset[str]`. Keep its existing duplicate producer, namespace,
section, remediation, and presentation-order checks unchanged; replace only the
`for rule in producer.rules` loop with
`for rule in producer.expanded_rules(active_kinds)`.

Every caller, including tests, must pass `active_kinds` explicitly. Do not default it to
empty: an omitted project context must not silently produce a smaller registry.
`source_module` is a required repo-relative POSIX path and has no default; update every
Plan 1 test producer fixture in this task. It is registration provenance used by the
filesystem equality guards, not report provenance. Its validator refuses absolute paths,
backslashes, NUL, `.` / `..` segments, and non-`.py` leaves. Update the module docstring:
project configuration selects the active kind set, while all producer and family policy
remains toolkit code.

Replace the old “registry reads no project configuration” test with:

```python
def test_project_selects_kind_instances_but_cannot_author_family_policy():
    def family(kinds: frozenset[str]) -> tuple[FindingRule, ...]:
        return tuple(
            FindingRule(
                id=f"{kind.replace('_', '-')}.status-vocabulary",
                severities={"warn"},
                subject_types={"path"},
                qualifier_schema=EmptyQ,
                title=f"{kind} status",
                section=SECTION.id,
                display_order=100 + index,
            )
            for index, kind in enumerate(sorted(kinds))
        )

    producer = PRODUCER.model_copy(
        update={"rules": (), "kind_rule_factory": family}
    )
    registry = build_registry(
        [producer],
        active_kinds=frozenset({"canonical_parameter", "paper", "project-kind"}),
    )
    assert set(registry.rules_by_id) == {
        "canonical-parameter.status-vocabulary",
        "paper.status-vocabulary",
        "project-kind.status-vocabulary",
    }
```

The active set is data; `family` is toolkit code. There is no argument through which a
project supplies a `FindingRule`.

- [ ] **Step 5: Add the project catalog without registering real producers yet**

```python
# science/src/science_tool/findings/catalog.py
from __future__ import annotations

from pathlib import Path

from science_tool.findings.producers import FindingProducer, FindingRegistry, build_registry
from science_tool.graph.sources import registry_for_project


def registered_producers() -> tuple[FindingProducer, ...]:
    """Plan 2's atomic cutover replaces the empty tuple with all three namespaces."""
    return ()


def build_project_registry(project_root: Path) -> FindingRegistry:
    active = frozenset(registry_for_project(project_root).registered_kinds())
    return build_registry(list(registered_producers()), active_kinds=active)
```

Change `findings.cli._registry` to accept the strict source load's registry and delegate:

```python
def _registry(entity_registry: EntityRegistry):
    from science_tool.findings.catalog import build_registry_for_entity_registry
    return build_registry_for_entity_registry(entity_registry)
```

Pass `sources.registry` from the same strict load that constructs
`IngestionContext`. Retain the phase-boundary ratchet in
`test_findings_producer_namespaces.py`: the catalog is still empty in this task.

Also expose
`build_registry_for_entity_registry(entity_registry: EntityRegistry) -> FindingRegistry`
and implement both entry points through it. Health already has
`ProjectSources.registry` whenever any selected check needs sources; pass that same
object instead of resolving profiles/catalogs a second time. A health selection that
needs no sources may call `registry_for_project(project_root)`. In trusted ingestion,
change `_load_ingestion_context` to return both `IngestionContext` and the strict
`ProjectSources.registry`, then build the finding registry from that exact object before
calling `ingest_report`. This is the §6 same-context requirement, not a caching
optimization.

- [ ] **Step 6: Run scoped tests**

Run:

```bash
cd science
uv run --frozen pytest \
  tests/test_findings_execution.py \
  tests/test_findings_registry.py \
  tests/test_findings_cli.py \
  tests/test_findings_ingest.py \
  tests/test_findings_isolation.py \
  tests/test_findings_producer_namespaces.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add science/src/science_tool/findings science/tests/test_findings_execution.py \
  science/tests/test_findings_registry.py science/tests/test_findings_cli.py \
  science/tests/test_findings_ingest.py science/tests/test_findings_isolation.py
git commit -m "feat(findings): add producer execution boundary"
```

---

### Task 2: Validation finding declarations and conversion primitives

**Files:**
- Create: `science/src/science_tool/validate/findings.py`
- Create: `science/src/science_tool/validate/observations.py`
- Test: `science/tests/validate/test_finding_primitives.py`

**Interfaces:**
- Produces:
  - closed qualifier schemas used by validation rules;
  - `validation_subject(project_root, path) -> FindingSubject`;
  - `validation_evidence(project_root, path, line) -> tuple[Evidence, ...]`;
  - `build_validation_finding(...) -> AuditFinding`;
  - `rule_kind_segment(kind) -> str`;
  - `ValidationMetricObservation`, `ValidationNotice`, and
    `ValidationObservationBatch`;
  - `ValidationObservationBatch.producer_result() -> FindingProducerResult`.
- Does not modify `Result`, `Check`, `runner`, or any real producer yet.

- [ ] **Step 1: Write the failing primitive tests**

```python
# science/tests/validate/test_finding_primitives.py
from pathlib import Path

import pytest
from pydantic import BaseModel, ConfigDict, ValidationError
from science_model.audit import (
    FindingRule,
    FindingSection,
    PathSubject,
    ProducerMetrics,
    ProjectSubject,
)

from science_tool.validate.findings import (
    CorrespondenceQualifiers,
    ProseAdvisoryQualifiers,
    ProseHitQualifiers,
    ValidationQualifiers,
    rule_kind_segment,
    validation_evidence,
    validation_subject,
)
from science_tool.validate.observations import (
    ValidationMetricObservation,
    ValidationNotice,
    ValidationObservationBatch,
)


class EmptyQualifiers(BaseModel):
    model_config = ConfigDict(extra="forbid")


SECTION = FindingSection(id="test", title="Test", section_order=1)
RULE = FindingRule(
    id="test.problem",
    severities={"warn"},
    subject_types={"path"},
    qualifier_schema=EmptyQualifiers,
    title="Problem",
    section=SECTION.id,
    display_order=1,
)


def test_validation_path_is_the_subject_and_line_is_evidence_only(tmp_path):
    absolute = tmp_path / "entities" / "papers" / "1.md"
    assert validation_subject(tmp_path, absolute) == PathSubject(
        path="entities/papers/1.md"
    )
    evidence = validation_evidence(tmp_path, absolute, 7)
    assert evidence[0].path == "entities/papers/1.md"
    assert evidence[0].line == 7


def test_pathless_validation_result_is_project_scoped(tmp_path):
    assert validation_subject(tmp_path, None) == ProjectSubject()
    assert validation_evidence(tmp_path, None, None) == ()


def test_prose_advisory_count_is_not_an_identity_field():
    assert ProseAdvisoryQualifiers.model_fields.keys() == {"check", "count"}
    assert ProseHitQualifiers.model_fields.keys() == {"check"}
    assert ValidationQualifiers.model_fields.keys() == {"key", "task"}
    assert CorrespondenceQualifiers.model_fields.keys() == {
        "task",
        "evidence_signature",
    }
    assert rule_kind_segment("canonical_parameter") == "canonical-parameter"
    assert rule_kind_segment("paper") == "paper"


def test_ordinary_validation_identity_key_is_required_explicitly():
    with pytest.raises(ValidationError):
        ValidationQualifiers.model_validate({"task": None})
    assert ValidationQualifiers.model_validate(
        {"key": ["missing-field", "summary"], "task": None}
    ).key == ["missing-field", "summary"]


def test_observation_batch_projects_findings_and_metrics_but_retains_notices():
    finding = RULE.build(
        subject=PathSubject(path="science.yaml"),
        severity="warn",
        qualifiers={},
        message="problem",
    )
    metrics = ValidationMetricObservation(metrics=ProducerMetrics(count=1))
    notice = ValidationNotice(path=None, line=None, message="checked one thing")
    batch = ValidationObservationBatch.from_observations(
        (finding, metrics, notice)
    )
    result = batch.producer_result()
    assert len(result.instrument.rows) == 1
    assert result.metrics.model_dump(mode="json") == {"count": 1}
    assert batch.notices == (notice,)


def test_observation_batch_rejects_two_metrics_observations():
    metric = ValidationMetricObservation(metrics=ProducerMetrics(count=1))
    with pytest.raises(ValueError, match="multiple metrics observations"):
        ValidationObservationBatch.from_observations((metric, metric))
```

- [ ] **Step 2: Run and confirm the module is missing**

Run:

```bash
cd science
uv run --frozen pytest tests/validate/test_finding_primitives.py -q
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement the closed schemas and path conversion**

```python
# science/src/science_tool/validate/findings.py
from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field
from science_model.audit import (
    AuditFinding,
    FindingRule,
    FindingSubject,
    LocationEvidence,
    PathSubject,
    ProjectSubject,
)

from science_tool.findings.paths import project_relative


class EmptyQualifiers(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ValidationQualifiers(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: list[str]
    task: str | None = None


class ProseHitQualifiers(BaseModel):
    model_config = ConfigDict(extra="forbid")
    check: str


class ProseAdvisoryQualifiers(BaseModel):
    model_config = ConfigDict(extra="forbid")
    check: str
    count: int = Field(ge=1)


class CorrespondenceQualifiers(BaseModel):
    model_config = ConfigDict(extra="forbid")
    task: str | None = None
    evidence_signature: str


class NumericVerificationMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")
    verified: int = Field(ge=0)
    unverifiable: int = Field(ge=0)
    mismatch: int = Field(ge=0)
    error: int = Field(ge=0)


def rule_kind_segment(kind: str) -> str:
    return kind.replace("_", "-")


def validation_subject(project_root: Path, path: Path | None) -> FindingSubject:
    if path is None:
        return ProjectSubject()
    return PathSubject(path=project_relative(project_root, path))


def validation_evidence(
    project_root: Path,
    path: Path | None,
    line: int | None,
) -> tuple[LocationEvidence, ...]:
    if path is None or line is None:
        return ()
    return (
        LocationEvidence(
            path=project_relative(project_root, path),
            line=line,
        ),
    )


def build_validation_finding(
    *,
    project_root: Path,
    rule: FindingRule,
    severity: str,
    path: Path | None,
    line: int | None,
    message: str,
    qualifiers: dict[str, object],
) -> AuditFinding:
    return rule.build(
        subject=validation_subject(project_root, path),
        severity=severity,
        qualifiers=qualifiers,
        message=message,
        evidence=list(validation_evidence(project_root, path, line)),
    )
```

Do not add a generic “arbitrary qualifiers” schema. `ValidationQualifiers` is the closed
schema for ordinary validation predicates and its `key` is required even when the value
is `[]`; specialized rules declare their narrower schema beside their producer.
`project_relative` is required because current validators carry both relative paths and
absolute `ctx.project_root / ...` paths; calling `Path.as_posix()` directly would make
valid current findings fail `PathSubject`.

In `validate/observations.py`, implement:

```python
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, ConfigDict
from science_model.audit import AuditFinding, ProducerMetrics

from science_tool.findings.producers import FindingProducerResult
from science_tool.instruments import InstrumentResult


class ValidationMetricObservation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    metrics: ProducerMetrics


class ValidationNotice(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    path: Path | None
    line: int | None
    message: str


@dataclass(frozen=True)
class ValidationObservationBatch:
    findings: tuple[AuditFinding, ...]
    metrics: ProducerMetrics
    notices: tuple[ValidationNotice, ...]

    @classmethod
    def from_observations(
        cls,
        observations: Iterable[
            AuditFinding | ValidationMetricObservation | ValidationNotice
        ],
    ) -> "ValidationObservationBatch":
        findings: list[AuditFinding] = []
        metrics: list[ValidationMetricObservation] = []
        notices: list[ValidationNotice] = []
        for observation in observations:
            if isinstance(observation, AuditFinding):
                findings.append(observation)
            elif isinstance(observation, ValidationMetricObservation):
                metrics.append(observation)
            elif isinstance(observation, ValidationNotice):
                notices.append(observation)
            else:
                raise TypeError(
                    f"unsupported validation observation "
                    f"{type(observation).__name__}"
                )
        if len(metrics) > 1:
            raise ValueError("multiple metrics observations")
        return cls(
            findings=tuple(findings),
            metrics=metrics[0].metrics if metrics else ProducerMetrics(),
            notices=tuple(notices),
        )

    def producer_result(self) -> FindingProducerResult:
        return FindingProducerResult(
            instrument=InstrumentResult.from_rows(list(self.findings)),
            metrics=self.metrics,
        )
```

This batch is the explicit single-pass composition. It does not cross the registered
producer boundary: `producer_result` does, and its exact return type is the Task 1
ratchet. Do not store notices in metrics or a mutable context.

- [ ] **Step 4: Run, lint, and commit**

Run:

```bash
cd science
uv run --frozen pytest tests/validate/test_finding_primitives.py -q
uv run --frozen ruff check src/science_tool/validate/findings.py \
  src/science_tool/validate/observations.py \
  tests/validate/test_finding_primitives.py
```

Expected: PASS.

Commit:

```bash
git add science/src/science_tool/validate/findings.py \
  science/src/science_tool/validate/observations.py \
  science/tests/validate/test_finding_primitives.py
git commit -m "feat(validate): add finding conversion primitives"
```

---

### Task 3: Audit report assembly and Plan 2 acceptance partition

**Files:**
- Modify: `science/model/src/science_model/audit/report.py`
- Modify: `science/model/src/science_model/audit/__init__.py`
- Modify: `science/model/tests/test_audit_report.py`
- Create: `science/src/science_tool/findings/reporting.py`
- Modify: `science/src/science_tool/validate/acceptance.py`
- Create: `science/tests/test_findings_reporting.py`
- Modify: `science/tests/test_acceptance_authority.py`
- Test: `science/tests/test_health_acceptance_parity.py`

**Interfaces:**
- Produces:
  - `pre_migration_acceptance_key(entry) -> str`
  - `partition_health_acceptances(project_root, reported_findings) ->
    (remaining_reported, accepted)`
  - `build_audit_report(...) -> AuditReport`
  - `ProducerCaveat`
- The partition operates only on findings already labeled with producer `validate`;
  non-validation findings never enter it.

- [ ] **Step 1: Pin the pre-migration key semantics**

Add tests covering the exact matcher fields:

```python
import pytest


def test_pre_migration_key_encodes_matcher_semantics_not_raw_yaml():
    from science_tool.validate.acceptance import pre_migration_acceptance_key

    absent = {
        "rule": "paper.status-vocabulary",
        "reason": "known",
    }
    malformed_wildcard = {
        "rule": "paper.status-vocabulary",
        "severity": 7,
        "reason": "another explanation",
    }
    assert pre_migration_acceptance_key(absent) == pre_migration_acceptance_key(
        malformed_wildcard
    )


def test_pre_migration_key_includes_every_match_discriminator():
    from science_tool.validate.acceptance import pre_migration_acceptance_key

    base = {
        "rule": "plan.correspondence-drift",
        "severity": "warning",
        "path": "entities/plans/1.md",
        "task": "t001",
        "message_contains": ["evidence-signature: v1:" + "a" * 64],
        "reason": "known",
    }
    keys = {
        pre_migration_acceptance_key(base),
        pre_migration_acceptance_key({**base, "path": "entities/plans/2.md"}),
        pre_migration_acceptance_key({**base, "task": "t002"}),
        pre_migration_acceptance_key({**base, "severity": "error"}),
        pre_migration_acceptance_key({**base, "message_contains": ["different"]}),
    }
    assert len(keys) == 5


@pytest.mark.parametrize("malformed", [7, ["valid", 7]])
def test_pre_migration_key_refuses_message_matchers_that_can_never_match(
    malformed,
):
    with pytest.raises(ValueError, match="malformed message_contains"):
        pre_migration_acceptance_key(
            {
                "rule": "paper.status-vocabulary",
                "message_contains": malformed,
                "reason": "dead entry",
            }
        )
```

Implement the frozen key using `canonical_json`:

```python
def _pre_migration_key_fields(entry: dict[str, Any]) -> dict[str, object]:
    rule = entry.get("rule")
    if not isinstance(rule, str):
        raise ValueError("acceptance entry has no string rule")
    fields: dict[str, object] = {"rule": rule}
    severity = entry.get("severity")
    if isinstance(severity, str):
        fields["severity"] = "warn" if severity in {"warn", "warning"} else severity
    for name in ("path", "task"):
        value = entry.get(name)
        if isinstance(value, str):
            fields[name] = value
    needles = entry.get("message_contains")
    if isinstance(needles, str):
        fields["message_contains"] = [needles]
    elif isinstance(needles, list):
        if not all(isinstance(value, str) for value in needles):
            raise ValueError(
                "malformed message_contains cannot acquire an acceptance key"
            )
        fields["message_contains"] = list(needles)
    elif needles is not None:
        raise ValueError("malformed message_contains cannot acquire an acceptance key")
    return fields


def pre_migration_acceptance_key(entry: dict[str, Any]) -> str:
    payload = b"science.acceptance.v1\n" + canonical_json(
        _pre_migration_key_fields(entry)
    )
    return hashlib.sha256(payload).hexdigest()[:32]
```

`reason` remains a validity prerequisite, not key material.

- [ ] **Step 2: Write acceptance-partition tests against `AuditFinding`**

Cover the Plan 2 scope with concrete fixtures and these assertions:

| Entry severity | Finding severity | Health accepted? |
|---|---:|---:|
| `warning` | `warn` | yes |
| `warning` | `error` | no |
| absent | `warn` | yes |
| absent | `error` | yes |

In the same test module, create one identical finding under producer
`dataset-anomalies` and assert it is never offered to the matcher. Retain the existing
`filter_accepted_warnings` test over legacy `Result` in this preparatory task and assert
only the WARN is removed by `science validate`. Task 4 moves that function and its test
to `AuditFinding` in the same atomic cutover as `RunResult`.

The helper that exposes legacy matcher fields must be explicit:

```python
def legacy_validation_fields(finding: AuditFinding) -> dict[str, object]:
    path = finding.subject.path if finding.subject.type == "path" else None
    task = finding.qualifiers.get("task")
    return {
        "rule": finding.rule_id,
        "severity": finding.severity,
        "path": path,
        "task": task if isinstance(task, str) else None,
        "message": finding.message,
    }
```

`partition_health_acceptances` accepts `ReportedFinding` envelopes, offers only envelopes
whose `producer_id == "validate"` to the matcher, and returns `AcceptedFinding` objects
with that same producer id, the frozen key, and the trimmed reason. It never changes
finding severity or lifecycle.

- [ ] **Step 3: Write deterministic report-assembly tests**

In `test_findings_reporting.py`, build two sections, three rules, and wired/unwired
producer results, then assert all four contracts directly:

1. row order is section order, display order, severity rank, canonical subject, and
   fingerprint;
2. a wired producer with a metrics schema appears in `report.metrics`, while an unwired
   producer does not;
3. `findings_total` and `findings_by_severity` describe only unsuppressed findings, while
   accepted and unwired counts use their own channels; and
4. `meta.producers_run` contains wired producers, `unwired` contains unwired producers,
   and the sets do not overlap.

In `model/tests/test_audit_report.py`, add exact tests that one wired caveat round-trips,
while duplicate producer caveats, a caveat whose producer is absent from
`meta.producers_run`, and a caveat with neither a nonblank code nor reason fail.

Add frozen `ProducerCaveat(producer_id, code, reason)` to `audit/report.py`, with a model
validator requiring at least one trimmed nonblank `code` / `reason`. Add
`caveats: tuple[ProducerCaveat, ...] = ()` to `AuditReport`, export the type, reject
duplicate caveat producer IDs, and include caveat producers in the existing
`output_producers <= meta.producers_run` invariant. Do not add a caveat total: caveats are
not findings or failed instruments.

Implement:

```python
def build_audit_report(
    *,
    producer_results: Mapping[str, FindingProducerResult],
    registry: FindingRegistry,
    ingestion_ref: str,
    generated_at: str,
    total_duration_seconds: float,
    accepted: tuple[AcceptedFinding, ...] = (),
    timings: tuple[Mapping[str, object], ...] = (),
) -> AuditReport:
    findings: list[ReportedFinding] = []
    metrics: dict[str, ProducerMetrics] = {}
    caveats: list[ProducerCaveat] = []
    unwired: list[UnwiredProducer] = []
    producers_run: list[str] = []
    for producer_id, raw in producer_results.items():
        result = validate_producer_result(registry, producer_id, raw)
        if result.instrument.status == "unwired":
            code = result.instrument.code
            if code is None:
                raise RegistryError(
                    f"{producer_id!r} returned unwired without a code"
                )
            unwired.append(
                UnwiredProducer(
                    producer_id=producer_id,
                    code=code,
                    reason=result.instrument.reason,
                )
            )
            continue
        producers_run.append(producer_id)
        if result.instrument.code is not None or result.instrument.reason is not None:
            caveats.append(
                ProducerCaveat(
                    producer_id=producer_id,
                    code=result.instrument.code,
                    reason=result.instrument.reason,
                )
            )
        producer = registry.producers_by_id[producer_id]
        if producer.metrics_schema is not None:
            metrics[producer_id] = result.metrics
        findings.extend(
            ReportedFinding(producer_id=producer_id, finding=finding)
            for finding in result.instrument.rows
        )
    findings.sort(key=lambda item: report_sort_key(registry, item.finding))
    accepted = tuple(sorted(accepted, key=lambda item: report_sort_key(registry, item.finding)))
    severity = Counter(item.finding.severity for item in findings)
    return AuditReport(
        schema_version=2,
        fingerprint_version=1,
        ingestion_ref=ingestion_ref,
        generated_at=generated_at,
        findings=tuple(findings),
        accepted=accepted,
        metrics={key: metrics[key] for key in sorted(metrics)},
        caveats=tuple(sorted(caveats, key=lambda item: item.producer_id)),
        unwired=tuple(sorted(unwired, key=lambda item: item.producer_id)),
        totals=ReportTotals(
            findings_total=len(findings),
            findings_by_severity=dict(severity),
            accepted_total=len(accepted),
            unwired_total=len(unwired),
        ),
        meta=ReportMeta(
            producers_run=tuple(sorted(producers_run)),
            total_duration_seconds=total_duration_seconds,
            timings=timings,
        ),
    )
```

`report_sort_key` must append the complete design key after
`registry.sort_key(rule_id)`: severity rank (`error`, `warn`, `info`), canonical subject
JSON, then v1 `finding_id`.

- [ ] **Step 4: Run scoped tests and commit**

Run:

```bash
cd science
uv run --frozen pytest \
  tests/test_findings_reporting.py \
  tests/test_acceptance_authority.py \
  tests/test_health_acceptance_parity.py -q
```

Run the model contract separately:

```bash
cd science/model
uv run --frozen pytest tests/test_audit_report.py -q
```

Expected: both commands PASS.

Commit:

```bash
git add science/src/science_tool/findings/reporting.py \
  science/src/science_tool/validate/acceptance.py \
  science/model/src/science_model/audit/report.py \
  science/model/src/science_model/audit/__init__.py \
  science/model/tests/test_audit_report.py \
  science/tests/test_findings_reporting.py \
  science/tests/test_acceptance_authority.py \
  science/tests/test_health_acceptance_parity.py
git commit -m "feat(findings): assemble audit reports"
```

---

### Task 4: Atomic convergence of validation, health, and data audit

> **Atomicity rule for this task:** This is one reviewer unit and one commit. Do not
> commit after a namespace conversion, and do not make an intermediate suite green by
> accepting both shapes. The registered catalog, real producer return types, health
> schema, renderer, count semantics, and namespace guard switch together.

**Files:**
- Modify: every Python module under
  `science/src/science_tool/validate/checks/` named by `CANONICAL_CHECK_MODULES`
- Modify: `science/src/science_tool/validate/result.py`
- Modify: `science/src/science_tool/validate/checks/__init__.py`
- Modify: `science/src/science_tool/validate/runner.py`
- Create: `science/src/science_tool/validate/runtime.py`
- Modify: `science/src/science_tool/validate/gates.py`
- Modify: `science/src/science_tool/validate/acceptance.py`
- Modify: `science/src/science_tool/validate/cli.py`
- Modify: every producer module under
  `science/src/science_tool/graph/health_checks/`
- Create: `science/src/science_tool/graph/health_checks/schema_invalid.py`
- Modify: `science/src/science_tool/graph/health_checks/base.py`
- Modify: `science/src/science_tool/graph/health_checks/__init__.py`
- Rewrite: `science/src/science_tool/graph/health.py`
- Rewrite: `science/src/science_tool/graph/health_projection.py`
- Delete: `science/src/science_tool/graph/health_count.py`
- Rewrite: `science/src/science_tool/graph/health_cli.py`
- Modify: `science/src/science_tool/data_audit.py`
- Modify: `science/src/science_tool/data_cli.py`
- Modify: `science/src/science_tool/findings/catalog.py`
- Modify: `science/src/science_tool/findings/cli.py`
- Modify: `docs/user-guide/health-and-validation.md`
- Modify or replace: all health/validation/data-audit tests affected by the public schema
- Create: `science/tests/test_finding_convergence.py`
- Create: `science/tests/validate/test_finding_families.py`

**Interfaces after this task:**
- Every registered namespace returns `FindingProducerResult` at its execution boundary.
- `build_health_report(..., ingestion_ref, generated_at) -> AuditReport`.
- `science health --format json` serializes `AuditReport.model_dump(mode="json")`.
- Validation's internal `Result` carries a `FindingRule` object and can convert only
  through that declaration.
- `science data audit` read-only detection crosses the generic producer boundary;
  its existing command-specific text/JSON contract remains unchanged, and `Violation`
  plus fixer affordances remain internal.

- [ ] **Step 1: Write the convergence ratchets before changing producers**

Create `test_finding_convergence.py` with executable fixtures and these named
assertions:

- `test_every_registered_health_module_has_one_catalog_producer`
- `test_every_registered_validation_module_contributes_a_producer`
- `test_data_audit_file_contributes_its_one_producer`
- `test_every_namespace_execution_crosses_validate_producer_result`
- `test_renderer_never_calls_an_unwired_report_clean`
- `test_renderer_shows_a_wired_caveat_without_reclassifying_true_zero`
- `test_health_report_has_only_the_audit_report_v2_fields`
- `test_retired_archive_lag_is_not_reintroduced`

The schema assertion compares `set(AuditReport.model_fields)` exactly with
`schema_version`, `fingerprint_version`, `ingestion_ref`, `generated_at`, `findings`,
`accepted`, `metrics`, `caveats`, `unwired`, `totals`, and `meta`. The archive assertion
checks both the registered producer IDs and rule IDs, and refuses `archive_lag` and
`tasks.archive-lag`.

Replace, rather than merely delete, the Plan 1 phase-boundary test in
`test_findings_producer_namespaces.py`. The filesystem guard must:

1. derive health module names from `graph/health_checks/*.py`, excluding only
   `__init__.py` and `base.py`;
2. derive validation names from `validate/checks/*.py`, excluding only `__init__.py`;
3. add the explicit filesystem path `validate/runtime.py` to the validation scope;
4. treat `data_audit.py` as one exact scope;
5. compare discovered module names with the registered producer source modules; and
6. assert equality in both directions.

- [ ] **Step 2: Change validation's internal result to require declarations**

Keep `Result` as a producer-internal issue object, but change `rule` from
`str | None` to `FindingRule` and add closed qualifiers:

```python
@dataclass(frozen=True)
class Result:
    severity: Severity
    path: Path | None
    line: int | None
    message: str
    rule: FindingRule
    task: str | None
    qualifiers: Mapping[str, object]

    @property
    def rule_id(self) -> str:
        return self.rule.id

    def to_finding(self, project_root: Path) -> AuditFinding:
        observed = dict(self.qualifiers)
        if self.task is not None and "task" not in observed:
            observed["task"] = self.task
        return build_validation_finding(
            project_root=project_root,
            rule=self.rule,
            severity=self.severity.value,
            path=self.path,
            line=self.line,
            message=self.message,
            qualifiers=observed,
        )
```

There is no `rule=None`, no default rule string, and no default qualifiers mapping.
Every emission must state its identity inputs explicitly; for an ordinary predicate
with only one possible row per subject that is `qualifiers={"key": []}`. Focused
raw-check tests read `result.rule.id`; gates, telemetry, acceptance, projection, and
renderers receive the validated `AuditFinding` and read `finding.rule_id`.

- [ ] **Step 3: Make `Check` the registered wrapper**

Extend `CheckEntry` with its `FindingProducer` and an exact producer projection. The
decorated observation function remains directly callable by focused unit tests. Runner
executes it once, converts `Result` objects through declarations, freezes the
`ValidationObservationBatch`, and invokes only `entry.produce(batch)` at the registered
boundary.

```python
CheckObservation = Result | ValidationMetricObservation | ValidationNotice
InternalCheckFn = Callable[[ValidateContext], Iterable[CheckObservation]]
RegisteredCheckFn = Callable[
    [ValidationObservationBatch],
    FindingProducerResult,
]


@dataclass(frozen=True)
class CheckEntry:
    section: str
    order: int
    fn: InternalCheckFn
    produce: RegisteredCheckFn
    producer: FindingProducer


class Check:
    def __init__(
        self,
        section: FindingSection,
        order: int,
        *,
        producer_id: str,
        rules: tuple[FindingRule, ...],
        metrics_schema: type[BaseModel] | None = None,
        kind_rule_factory: KindRuleFactory | None = None,
    ) -> None:
        self.section = section
        self.order = order
        self.producer_id = producer_id
        self.rules = rules
        self.metrics_schema = metrics_schema
        self.kind_rule_factory = kind_rule_factory

    def __call__(self, fn: InternalCheckFn) -> InternalCheckFn:
        producer = FindingProducer(
            producer_id=self.producer_id,
            namespace="validate_checks",
            source_module=(
                fn.__module__
                .removeprefix("science_tool.")
                .replace(".", "/")
                + ".py"
            ),
            rules=self.rules,
            sections=(self.section,),
            metrics_schema=self.metrics_schema,
            kind_rule_factory=self.kind_rule_factory,
        )

        def produce(
            batch: ValidationObservationBatch,
        ) -> FindingProducerResult:
            return batch.producer_result()

        CANONICAL_CHECKS.append(
            CheckEntry(
                section=self.section.title,
                order=self.order,
                fn=fn,
                produce=produce,
                producer=producer,
            )
        )
        CANONICAL_CHECKS.sort(key=lambda entry: entry.order)
        return fn
```

Runner's common executor performs this exact sequence:

1. call `entry.fn(ctx)` once;
2. turn each `Result` into `item.to_finding(ctx.project_root)`, pass metrics/notices
   through unchanged, and refuse any fourth type;
3. call `ValidationObservationBatch.from_observations`;
4. call `entry.produce(batch)` and then `validate_producer_result` immediately;
5. append `batch.notices` to `RunResult.notices`.

Its check-exception finding uses a declared `validate.check-error` rule with identity
qualifier `check`; it does not construct a rule string in the exception handler.

Change `RunResult.results` to `list[AuditFinding]`, add
`producer_results: Mapping[str, FindingProducerResult]`,
`notices: tuple[ValidationNotice, ...]`, and the project-scoped `FindingRegistry`.
The runner stores every already-validated per-check result and derives the flat results
list directly from their instrument rows; it never reconstructs a `Result`. The health
`validate` producer reads numeric-verification coverage from
`producer_results["validate.prose-lints"].metrics`; it must not parse an INFO row or run
prose lints again.

`validate/runtime.py` declares one `VALIDATION_RUNTIME_PRODUCER` owning
`validate.check-error` and `validate.sidecar-removed`. Runner exceptions and the existing
legacy-sidecar warning are accumulated into one runtime `FindingProducerResult` and
validated once. Python sidecar hooks may return only `Result` objects carrying an
already-registered toolkit `FindingRule`; wrapping them under the runtime producer does
not authorize a project-created declaration, because registry lookup still rejects it.
Include the runtime producer in the catalog and in the validation namespace guard as the
explicit `validate/runtime.py` path.

- [ ] **Step 4: Convert every validation module mechanically and fail on omissions**

For every module in `CANONICAL_CHECK_MODULES`:

1. declare `FindingSection` and every `FindingRule` beside the emitting function;
2. pass those objects to `@Check`;
3. change every `Result(..., rule=<string>)` and every helper parameter `rule: str` to a
   `FindingRule` object;
4. delete any defaulted rule argument;
5. keep line numbers only in `LocationEvidence`;
6. give every ordinary issue a semantic `key` assembled from the stable predicate
   components named in design §6; use `[]` only when the rule can produce at most one
   row for that subject, and never use message text, severity, line, or list position;
7. keep `task` as a non-identity qualifier unless a rule explicitly says otherwise; and
8. convert every non-policy `Severity.INFO` site to `ValidationNotice`, preserving its
   path, line, and message for verbose rendering. Only `prose-lints.config` and
   `prose-lints.advisory` remain INFO `Result` findings; numeric coverage is metrics.

Use this exact ordinary-rule pattern for a rule that already has a conforming external
ID:

```python
SECTION = FindingSection(
    id="commons-owner-collision",
    title="commons owner collision",
    section_order=35,
)
RULE_OWNER_COLLISION = FindingRule(
    id="commons.owner-collision",
    severities={"error"},
    subject_types={"path"},
    qualifier_schema=ValidationQualifiers,
    identity_qualifiers=("key",),
    title="Commons owner collision",
    section=SECTION.id,
    display_order=3500,
    default_visibility="visible",
)


@Check(
    section=SECTION,
    order=35,
    producer_id="validate.commons-owner-collision",
    rules=(RULE_OWNER_COLLISION,),
)
def check_commons_owner_collision(ctx: ValidateContext) -> Iterator[Result]:
    for path, message in find_owner_collisions(ctx):
        yield Result(
            severity=Severity.ERROR,
            path=path,
            line=None,
            message=message,
            rule=RULE_OWNER_COLLISION,
            task=None,
            qualifiers={"key": []},
        )
```

`find_owner_collisions` above stands for the module's existing typed domain helper; do
not create a second detector. The existing rule spelling is externally visible and
remains exact unless §6 explicitly renames it. INFO progress/pass rows such as the
current `papers` observation become `ValidationNotice` and therefore require no
replacement rule. Apply the complete static mapping from design §6:

| Current ID | Plan 2 ID |
|---|---|
| `autonomous-runs` | `autonomous-runs.check` |
| `bias_audits` | `bias-audits.check` |
| `cross-references` | `cross-references.check` |
| `directory_structure` | `directory-structure.check` |
| `discussions` | `discussions.check` |
| `document_structure` | `document-structure.check` |
| `entity-conformance` | `entity-conformance.check` |
| `evidence.empirical.requires_dataset_usage` | `evidence.empirical.requires-dataset-usage` |
| `gap_analysis` | `gap-analysis.check` |
| `graph` | `graph.check` |
| `hypotheses` | `hypotheses.check` |
| `hypothesis_comparisons` | `hypothesis-comparisons.check` |
| `id-prefixes` | `id-prefixes.check` |
| `forbidden-second-declaration` | `identity.forbidden-second-declaration` |
| `lens_views` | `lens-views.check` |
| `manifest` | `manifest.check` |
| `non-materializing-field` | `materialization.non-materializing-field` |
| `notes` | `notes.check` |
| `origins` | `origins.check` |
| `orphan-datapackage-owner` | `dataset.orphan-datapackage-owner` |
| `papers` | no rule; INFO notice only |
| `prereg` | `prereg.check` |
| `project_readme` | `project-readme.check` |
| `proposition.claim_layer.canonical` | `proposition.claim-layer.canonical` |
| `references` | `references.check` |
| `registration` | `registration.check` |
| `research_scope` | `research-scope.check` |
| `tasks` | `tasks.check` |
| `tooling` | `tooling.check` |
| `unresolved_markers` | `unresolved-markers.check` |
| `validate.sidecar.legacy_removed` | `validate.sidecar-removed` |

Do not infer more normalizations and do not add aliases.

Special policy that must not be inferred mechanically:

| Current source | Required declaration/output |
|---|---|
| `status_vocabulary.py` | One derived `{rule_kind_segment(kind)}.status-vocabulary` rule per active kind; each permits exactly `severity_for_kind(original_kind)`. |
| `supersession.py` | One derived `{rule_kind_segment(kind)}.unbacked-inverse` rule per active kind; each permits exactly `severity_for_kind(original_kind)`. |
| `correspondence_drift.py` | Fixed `plan.correspondence-drift`; `CorrespondenceQualifiers.evidence_signature` is identity-bearing; override and delete the old future-kind f-string comment. |
| `hypotheses.py` dangling lineage | One literal `hypothesis.dangling-lineage`, never a family; severity remains `severity_for_kind("hypothesis")`. |
| `annotations.py` | Exactly `annotations.{kind}` for every member of `ISSUE_KINDS`; declared set equals `ISSUE_KINDS`. |
| `prose_lints.py` WARN hits | `prose-lints.hit`, `PathSubject`, identity qualifier `check`, line as evidence, visible. |
| `prose_lints.py` INFO configured severity | `prose-lints.advisory`, `ProjectSubject`, identity qualifier `check`, non-identity `count`, hidden. |
| `prose_lints.py` config | `prose-lints.config`, `ProjectSubject`, visible INFO. |
| `prose_lints.py` numeric coverage | No rule. Yield one `ValidationMetricObservation` containing the exact four tallies; declare `NumericVerificationMetrics`. |
| `benchmark_metadata.py` | Replace the support-field f-string with an explicit `{"evidence": rule, "notes": rule}` map; test equality with the exact supported list fields. |
| `identity_context.py` | Replace tier/spec f-strings with explicit maps for the four required tiers and the 2 × 5 molecular-spec product from design §6; missing keys fail. |
| `relations.py` | Replace `f"relation.{defect.code}"` with an explicit map for `unknown-subject`, `unknown-object`, `unknown-predicate`, `unsupported-graph-layer`, `external-target`, `self-referential`, `illegal-kind-pair`, `membership-role`, and `cycle`; an AST test compares this set with all `RelationRejection` literals plus the audit's corpus-level cycle code. |
| `workflow_runs.py` | Map `RULE_INCOMPLETE` and `RULE_AUTHORED_CAPTURABLE` from `run_fingerprint_policy.py` to explicit rule objects; no `finding.rule` string crosses the boundary. |
| validation sidecar hooks | A hook may emit only `Result` objects carrying toolkit `FindingRule` objects. Project-authored strings fail at construction; project code cannot register rules. |

Create `validate/test_finding_families.py` with the following executable tests:

- declared status/inverse IDs equal active-kind expansion;
- underscore kinds map to kebab rule segments and two active kinds colliding after that
  mapping fail before registry construction;
- sparse emitted status/inverse IDs are subsets of those declarations;
- every emission kind belongs to the active registry;
- annotation suffixes equal `ISSUE_KINDS`;
- correspondence drift remains exactly `plan.correspondence-drift` and evidence-scoped;
- the three hypothesis gate IDs remain exact;
- prose WARN/advisory rules retain distinct visibility;
- numeric verification coverage appears only in metrics;
- all emitted validation IDs satisfy the `FindingRule` grammar, declared mappings equal
  the complete 31-row table above, and every old nonconforming ID is absent;
- each fixture's old WARN/ERROR rows correspond one-to-one with distinct
  `(rule_id, subject, qualifiers["key"])` tuples for ordinary rules; metamorphic tests
  vary message, severity, line, and input-list position without changing `key`, while
  changing a declared semantic component changes it;
- every non-policy INFO site yields `ValidationNotice`, while the two policy INFO rules
  remain findings;
- one raw check invocation supplies its findings, metrics, and notices (the test fails if
  the wrapper calls it twice); and
- benchmark, identity-context, relation, and workflow finite-dispatch map keys equal
  their upstream authorities/exact frozen sets; and
- an AST walk across `validate/checks/`, `validate/runner.py`, and `validate/runtime.py`
  finds no string literal or f-string passed as a `Result` rule argument.

The last test refuses `Result`/helper calls whose rule argument is a string literal or
f-string anywhere on that emission surface. Runtime `Result.__post_init__` also refuses
anything that is not a `FindingRule`.

- [ ] **Step 5: Preserve validation CLI behavior over declared results**

Update:

- `gated_findings` to compare `finding.rule_id`;
- telemetry to emit `finding.rule_id`;
- `filter_accepted_warnings` to remain WARN-only;
- `_is_visible_info` to resolve `finding.rule_id` through `RunResult.registry`, use
  `default_visibility == "visible"`, and remove `_VISIBLE_INFO_RULES`;
- validation JSON serialization to use the explicit legacy-field projection
  (`rule_id`, `PathSubject.path`, first `LocationEvidence.line`, message, and string task
  qualifier), preserving its current shape without retaining `Result.to_dict`;
- normal text to show the two explicit policy INFO findings according to rule
  visibility;
- text findings to render subject/evidence/qualifiers from `AuditFinding`;
- verbose text to append `RunResult.notices` in check order with path/line/message but no
  bracketed rule label;
- summary/gated exit behavior to remain based on the full result, never the projection.

Do not add an `AuditReport` wrapper to `science validate`; its command-specific summary
remains a validation runner surface. The shared producer contract is enforced inside the
runner before the CLI receives results.

- [ ] **Step 6: Convert health producers using the §9 ledger**

Change `HealthCheck.run` to return `FindingProducerResult`, add a
`producer: FindingProducer` field, and delete `HealthCheck.empty`. Under `AuditReport`,
an unselected check is absent from `meta.producers_run`; it does not need a fabricated
old-schema empty value. Each module owns its rules, closed qualifier schema, metrics
schema, and section. Preserve the current `HEALTH_CHECKS` tuple order by assigning
monotonic `section_order`; rule `display_order` handles multiple rules in one section.

The conversion ledger is exhaustive:

| Producer | Finding identity and subject | Metrics |
|---|---|---|
| `unresolved_refs` | `refs.unresolved`; `IdentifierSubject("reference", target)`; citing files become evidence; `mention_count` and `looks_like` are non-identity qualifiers. | none |
| `unregistered_ref_kinds` | `refs.unregistered-kind`; `IdentifierSubject("reference-kind", kind)`; `field` identity-bearing; refs/sources/count non-identity/evidence. | none |
| `lingering_tags` | `tags.lingering`; `PathSubject(file)`; tag values non-identity. | none |
| `agent_context` | one explicit `agent-context.*` rule per current code; `PathSubject(source_file)`. | none |
| `identity_policy` | `identity.policy-violation`; valid entity refs use `EntitySubject`, relation stubs use `PathSubject(source_file)`; `check` identity-bearing. | none |
| `entity_identity` | `identity.entity`; `EntitySubject` when canonical id is valid, otherwise `PathSubject`; warning code identity-bearing. | none |
| `layered_claim_migration` | `layered-claim.migration`, `layered-claim.rival-model-gap`, and one `layered-claim.coverage-incomplete` per incomplete coverage axis. | both complete coverage metrics |
| `cross_paper_evidence` | `cross-paper.{reason}`; `PathSubject(sidecar)`; annotation identity-bearing. | status, empty state, summary, propositions |
| `managed_artifacts` | only rows whose `counts_as_issue` is true become explicit `managed-artifact.*` findings with `IdentifierSubject("managed-artifact", artifact key)`. | complete inventory, including unflagged rows |
| `tooling_scaffold` | one explicit `tooling.scaffold` rule with code identity-bearing and `ProjectSubject` or `PathSubject("pyproject.toml")`. | none |
| `validate` | aggregate already-validated WARN/ERROR rows from the validation runner and relabel the report producer as canonical `validate`; policy INFO and notices stay out of health findings; numeric coverage remains metrics. Its health `FindingProducer` declares no duplicate rules: canonical validation producers own the declarations, while cross-producer emission is validated through the global registry. | validation numeric coverage |
| `prose_epistemics` | explicit `prose-epistemics.*` rule for each flagged artifact condition; `PathSubject`. | applicable, summary, coverage, sources |
| `dataset_anomalies` | exactly the twelve §9 rules; `EntitySubject(dataset)`; `field`, `invariant`, and `counterpart` identity exactly as declared. | none |
| `legacy_task_type` | `task.legacy-type`; `EntitySubject(ref=f"task:{task_id}")`; legacy type non-identity. | none |
| `invalid_entity_aspects` | `entity.invalid-aspects`; valid entity ref subject, path fallback only when the malformed record cannot supply one. | none |
| skipped core schemas | `entity.schema-invalid`; `PathSubject`; produced by `health_checks/schema_invalid.py`, not synthesized in the report reader. It is a source-load producer rather than a selectable check: run it whenever health loads `ProjectSources`, exactly when the current report reader surfaces these rows. | none |

`dataset_anomalies` must replace `DATASET_ANOMALY_CODES` with rule declarations and its
test must assert emitted rule IDs equal the twelve declared IDs. Each producer returns
the composed model directly; `_drain_instrument_results` is deleted, not rewritten.

- [ ] **Step 7: Rewrite health assembly to `AuditReport`**

`build_health_report` requires actor claims:

```text
def build_health_report(
    project_root: Path,
    *,
    ingestion_ref: str,
    generated_at: str,
    collect_timings: bool = False,
    checks: set[str] | frozenset[str] | None = None,
    skip_checks: set[str] | frozenset[str] | None = None,
    fast: bool = False,
) -> AuditReport:
```

Execution order:

1. select checks;
2. load project sources once when required;
3. build the project registry from that same active `EntityRegistry`;
4. when sources were loaded, run and validate `SCHEMA_INVALID_PRODUCER` against
   `sources.skipped_entities` even if a focused check selection did not name it;
5. run every selected check;
6. call `validate_producer_result` immediately for each;
7. envelope the `validate` rows, partition current-shape acceptances, and replace that
   producer result with a new `FindingProducerResult` containing only the remaining rows
   and the unchanged validated metrics;
8. call `build_audit_report`.

Delete:

- `HealthReport`, its twenty-one fields, and all check-specific report casts;
- `_drain_instrument_results`;
- `_partition_accepted_validation_findings`;
- `count_issues` and `health_count.py`;
- nested-reader issue derivation; and
- any special case that counts a metric by value.

`layered-claim.coverage-incomplete` replaces the two metric-derived increments, so
`AuditReport.totals.findings_total` is always a row count. `legacy_task_type` and
`invalid_entity_aspects` now count, as approved.

- [ ] **Step 8: Rewrite projection and rendering generically**

`health_projection.py` projects only:

- visible `findings`, preserving full totals;
- accepted findings;
- metrics by producer;
- complete wired caveats (never capped away);
- complete `unwired` (never capped away); and
- timings.

The renderer groups findings by registry section, orders with `report_sort_key`, and
renders severity, subject, rule id, and message. It may render producer-specific metric
tables, but it must never reconstruct findings from metrics.

The clean branch is exactly:

```python
if report.totals.findings_total == 0 and not report.unwired:
    sink.echo("Project is clean.")
elif report.unwired:
    sink.echo("Project is not clean: one or more diagnostics could not run.")
```

Render every caveat as a note before this summary. A caveat does not forbid the first
branch; an unwired producer still does.

`science health --format json` emits `report.model_dump(mode="json")`. The CLI creates a
fresh `health:<uuid4().hex>` invocation ref and
`datetime.now(timezone.utc).isoformat(timespec="microseconds")` timestamp; direct library
callers must supply both because `build_health_report` has no defaults.

Update budget fixtures to schema v2. `displayed_issues` becomes
`len(projected.findings)` while `report.totals.findings_total` remains the full count.

- [ ] **Step 9: Convert `data_audit` without exposing fix affordances**

Keep `Violation` and `AuditNote` internal because `data_audit_fix.py` consumes them.
Make the one observation pass explicit so the producer and the command renderer consume
the same facts:

```python
@dataclass(frozen=True)
class DataAuditSnapshot:
    violations: tuple[Violation, ...]
    notes: tuple[AuditNote, ...]


def collect_data_audit(
    project_root: Path,
    policy: DataPolicy = DEFAULT_DATA_POLICY,
    data_dirs: tuple[Path, ...] = DEFAULT_DATA_DIRS,
) -> DataAuditSnapshot:
    return DataAuditSnapshot(
        violations=tuple(audit_project(project_root, policy, data_dirs)),
        notes=tuple(audit_project_notes(project_root)),
    )


def data_audit_result(snapshot: DataAuditSnapshot) -> FindingProducerResult:
    findings = [
        DATA_RULES[violation.quadrant].build(
            subject=PathSubject(path=violation.path),
            severity="warn",
            qualifiers={
                "quadrant": violation.quadrant.value,
                "file_class": violation.file_class.value,
            },
            message=_violation_message(violation),
        )
        for violation in snapshot.violations
    ]
    findings.extend(
        DATA_AUDIT_NOTE_RULE.build(
            subject=ProjectSubject(),
            severity="warn",
            qualifiers={"code": note.code},
            message=note.message,
        )
        for note in snapshot.notes
        if note.severity == "warning"
    )
    return FindingProducerResult(
        instrument=InstrumentResult.from_rows(findings),
    )


def run_data_audit(
    project_root: Path,
    policy: DataPolicy = DEFAULT_DATA_POLICY,
    data_dirs: tuple[Path, ...] = DEFAULT_DATA_DIRS,
) -> FindingProducerResult:
    return data_audit_result(collect_data_audit(project_root, policy, data_dirs))
```

Rules:

- `data.violation.stranded-record`
- `data.violation.leaked-payload`
- `data.violation.tracked-payload`
- `data.violation.flag`
- `data.audit-note`

The four `data.violation.*` declarations use `remediation="producer"` and
`remediator="data-audit"`; `DATA_AUDIT_PRODUCER.remediators` contains exactly that
capability. `data.audit-note` declares no remediation. This advertises that a trusted
producer can recompute a current plan without storing `proposed_target`.
`data.audit-note` uses `code` as an identity qualifier; otherwise two simultaneous
warning notes would collide on `ProjectSubject`.

The finding carries no `proposed_target`. In read-only mode, `data_cli.py` calls
`collect_data_audit` once, validates `data_audit_result(snapshot)` through the project
registry, and then renders the existing text/JSON contract from that same snapshot.
Informational notes therefore remain notes and the public data-audit JSON does not
silently become `AuditReport`. In fix mode, re-run `collect_data_audit` immediately
before computing actions, preserving Plan D's fresh-derived-state doctrine and today's
operational move report.

- [ ] **Step 10: Populate the catalog and replace the phase ratchet**

`registered_producers()` late-imports:

```python
def registered_producers() -> tuple[FindingProducer, ...]:
    from science_tool.data_audit import DATA_AUDIT_PRODUCER
    from science_tool.graph.health_checks import HEALTH_CHECKS
    from science_tool.graph.health_checks.schema_invalid import SCHEMA_INVALID_PRODUCER
    from science_tool.validate.checks import CANONICAL_CHECKS
    from science_tool.validate.runtime import VALIDATION_RUNTIME_PRODUCER

    return (
        *(check.producer for check in HEALTH_CHECKS),
        SCHEMA_INVALID_PRODUCER,
        *(entry.producer for entry in CANONICAL_CHECKS),
        VALIDATION_RUNTIME_PRODUCER,
        DATA_AUDIT_PRODUCER,
    )
```

Duplicate producer and rule IDs fail during registry construction. Ingestion calls
`build_project_registry(project_root)` after its strict source/context load; a stored case
whose kind-derived rule is inactive still loads through storage, while re-ingestion
refuses the now-undeclared rule before any write.

Delete `test_phase_boundary_ratchet_no_producers_are_registered_yet` and replace it in
the same diff with the three filesystem equality guards from Step 1.

- [ ] **Step 11: Update existing tests to assert semantics, not old field names**

Rewrite affected tests rather than introducing adapters. At minimum:

- `test_health.py`: query `report.findings`, `report.metrics`, `report.accepted`,
  `report.unwired`, and `report.totals`.
- `test_health_count_issues.py`: replace with the §9 count-ledger fixture; delete tests
  for the retired `count_issues` parser.
- `test_health_projection*.py`: assert projected row counts never rewrite full totals.
- `test_health_cli_budget.py`: use a real `AuditReport` fixture.
- `test_health_preconditions.py`: assert unwired is separate and rendered non-clean.
- `test_correspondence_drift_health_integration.py`: assert accepted channel,
  acceptance key, exact fixed rule, and evidence identity.
- `test_health_schema_invalid.py`: assert `entity.schema-invalid` path finding.
- focused raw-check tests: compare producer-internal `result.rule.id`; runner/CLI tests:
  compare validated `finding.rule_id` and assert command notices through
  `RunResult.notices`.
- snapshot/schema fixtures: update once to the new validation rule IDs and health v2
  report; do not preserve both snapshots.
- data-audit read-only CLI tests: assert the existing notes/violations JSON and text
  rendering after the composed producer result crosses validation; fix-mode tests
  continue asserting fresh `Violation`-based actions.
- `docs/user-guide/health-and-validation.md`: replace `health.total_issues` and
  `accepted_validation` output wording with `totals.findings_total` and `accepted`;
  document findings/accepted/metrics/caveats/unwired as separate channels while leaving
  the current `science.yaml` acceptance example unchanged for Plan 2.

Add the count-ledger test with one fixture case per §9 row. It must assert:

```python
assert report.totals.findings_total == len(report.findings)
assert sum(report.totals.findings_by_severity.values()) == len(report.findings)
assert not (set(accepted_ids) & set(unsuppressed_ids))
```

and specifically assert that `legacy_task_type` and `invalid_entity_aspects` each add one
where their old omission added zero. No producer may reduce a current count.

- [ ] **Step 12: Run the atomic scoped suite**

Run serially:

```bash
cd science
uv run --frozen pytest \
  tests/test_findings_execution.py \
  tests/test_findings_registry.py \
  tests/test_findings_reporting.py \
  tests/test_findings_producer_namespaces.py \
  tests/test_finding_convergence.py \
  tests/test_findings_ingest.py \
  tests/test_health.py \
  tests/test_health_acceptance_parity.py \
  tests/test_health_checks_base.py \
  tests/test_health_checks_package.py \
  tests/test_health_cli_budget.py \
  tests/test_health_managed_artifacts.py \
  tests/test_health_preconditions.py \
  tests/test_health_projection.py \
  tests/test_health_projection_caps.py \
  tests/test_health_schema_invalid.py \
  tests/test_correspondence_drift_health_integration.py \
  tests/test_data_audit.py \
  tests/test_data_audit_cli.py \
  tests/test_data_audit_scope.py \
  tests/test_data_audit_symlink.py \
  tests/test_acceptance_authority.py \
  tests/validate -q
```

Expected: PASS. Do not weaken a failing guard into a subset assertion.

- [ ] **Step 13: Run lint and types**

Run:

```bash
cd science
uv run --frozen ruff check
uv run --frozen pyright
```

Expected: both PASS.

- [ ] **Step 14: Commit the atomic cutover**

```bash
git add science/src/science_tool science/tests \
  docs/user-guide/health-and-validation.md
git commit -m "refactor(findings): converge deterministic producers"
```

Before committing, inspect `git diff --cached` and confirm it includes all of:
producer registrations, namespace equality guards, report v2, renderer refusal,
acceptance parity, metrics schemas, removal of `_drain_instrument_results`, removal of
`health_count.py`, and no dual reader.

---

### Task 5: Final verification and implementation record

**Files:**
- Modify: `docs/plans/2026-07-28-finding-convergence-plan-2-producer-cutover.md`
  (append implementation record only after verification)
- `docs/user-guide/health-and-validation.md` is already changed in Task 4; verify its
  field names against the shipped schema.

**Interfaces:** none; this task proves the landing and records exact evidence.

- [ ] **Step 1: Search for retired shapes and forbidden fallbacks**

Run:

```bash
rg -n "HealthReport|total_issues|accepted_validation|unwired_checks|_drain_instrument_results|counts_as_issue" \
  science/src/science_tool science/tests
```

Expected:

- no `HealthReport`, `total_issues`, `_drain_instrument_results`, or `unwired_checks`;
- `accepted_validation` remains only in the Plan 2 current-shape acceptance reader,
  its hygiene check/tests, and migration-facing documentation;
- `counts_as_issue` remains only in producer-internal source artifact parsing if the
  upstream artifact still contains it, never in report counting.

Run:

```bash
rg -n "return InstrumentResult|return \\(|return \\{|pass through untouched|not \\(yet\\)" \
  science/src/science_tool/graph/health_checks \
  science/src/science_tool/validate/checks \
  science/src/science_tool/data_audit.py
```

Inspect every match. Registered wrappers must return `FindingProducerResult`; internal
domain helpers may return their own typed values only behind that wrapper.

- [ ] **Step 2: Run the model suite**

Run:

```bash
cd science/model
uv run --frozen pytest
```

Expected: PASS.

- [ ] **Step 3: Run the full tool suite with a long timeout**

Run:

```bash
cd science
uv run --frozen pytest
```

Expected: PASS. Allow at least 15 minutes; the suite is roughly 10k tests.

- [ ] **Step 4: Run final lint, formatting check, and types**

Run:

```bash
cd science
uv run --frozen ruff check
uv run --frozen ruff format --check
uv run --frozen pyright
```

Expected: all PASS.

- [ ] **Step 5: Exercise both CLIs against a temporary fixture**

Run `science health --format json` against a fixture project, then verify:

```python
assert payload["schema_version"] == 2
assert payload["fingerprint_version"] == 1
assert payload["totals"]["findings_total"] == len(payload["findings"])
assert isinstance(payload["caveats"], list)
assert "total_issues" not in payload
assert "unwired_checks" not in payload
```

Run `science data audit --format json` against a fixture with one informational note and
one violation; assert its existing `notes` and `violations` keys remain present and no
fix-only field is introduced. Also run text health against an unwired fixture and assert
the output does not contain `Project is clean`.

- [ ] **Step 6: Append the implementation record**

Append a short `## Implementation record` containing:

- cutover commit id;
- exact scoped/full/lint/type commands and pass counts;
- confirmed public schema version;
- the two approved count increases;
- confirmation that archive lag remains absent; and
- any user-guide files updated.

Do not mark a failed or skipped command as passing.

- [ ] **Step 7: Commit verification documentation**

```bash
git add docs/plans/2026-07-28-finding-convergence-plan-2-producer-cutover.md \
  docs/user-guide/health-and-validation.md
git commit -m "docs(findings): record producer convergence"
```

## Plan 3 boundary

This plan deliberately leaves the current `health.accepted_validation` entry shape in
the health path. Plan 3 must, in one landing:

1. ship `science findings migrate-acceptances`;
2. implement all four migration outcomes;
3. switch health to `{finding_id, severity_scope}` entries;
4. remove Plan 2's current-shape health matcher; and
5. retain the old reader only inside the explicit migration command.

No Task in Plan 2 may pre-build a permanent dual matcher.

# AuditFinding Convergence — Plan 3: Acceptance Migration

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox
> (`- [ ]`) syntax for tracking.

**Goal:** Replace prose-keyed validation acceptances with fingerprint-keyed entries,
ship the dry-run/apply migration, make health and validate consume the replacement shape,
and migrate every surveyed consumer without changing observable counts.

**Architecture:** Task 1 builds the replacement entry model, total raw-entry
classification, and an idempotent pure migration engine while Plan 2 health remains live.
Valid replacement entries pass through as `already-current`; only legacy entries need
producer matching. Task 2 adds the migration CLI, round-trip YAML rewrite, and per-check
completeness proof. Task 3 is the atomic toolkit cutover: health and validate switch to
fingerprint matching, the old health matcher moves behind the migration-only boundary,
the evidence-scope machinery disappears, validation aggregation becomes honest about
every unwired check, the narrow acceptance-configuration exit gate lands, and the
in-repo `meta` consumer migrates in the same commit. Task 4 updates each external
consumer's configuration and exact toolkit pin together. Task 5 runs the full
verification and records the landing.

**Tech Stack:** Python 3.12+, Pydantic v2, Click, Rich, PyYAML for the existing raw
reader, ruamel.yaml round-trip mode for the targeted config rewrite, pytest, uv.
`science-model` remains unchanged.

**Design:**
[`2026-07-27-finding-convergence-design.md`](2026-07-27-finding-convergence-design.md),
revision 26 in this worktree (revision-24 base `cc675a7a`). Section references below are
to §10 and design tests 24–25 and 33–37 unless stated otherwise.

## Global Constraints

- **Run toolkit commands from `science/`.** There is no root `pyproject.toml`.
- **Treat every command block as starting at the worktree root.** Do not carry a prior
  block's `cd` into the next block.
- **Do not run two test suites concurrently in one worktree.** Validation and health
  share generated-output paths.
- **Run scoped tests inside Tasks 1–3.** Reserve the full model/tool suites for Task 5
  with an explicit long timeout.
- **One steady-state acceptance reader only.** After Task 3, health and `science
  validate` accept only `{finding_id, fingerprint_version, severity_scope, reason,
  accepted_on?}`. The old reader remains only in
  `findings/acceptance_migration.py`, which exists solely for the explicit migration
  command.
- **No compatibility layer.** Do not retain dual health matchers, aliases for the old
  fields, a `--legacy` option, or a fallback from invalid current shape to legacy shape.
- **Classification is positive and total.** A mapping with `finding_id` is current; a
  mapping without `finding_id` and with a string `rule` is legacy; every other raw entry
  is invalid. A current-model validation failure is always invalid. The migration
  preserves that distinction as verdict `invalid`; it never relabels a parse failure
  `stale`.
- **Severity scope is canonical.** Store it as a non-empty tuple in fixed `warn`,
  `error` order after deduplication. Reject every other member.
- **One entry per fingerprint.** Duplicate migration detection keys on `finding_id`
  alone, regardless of severity scope or whether the entry was migrated or already
  current.
- **The fingerprint algorithm is unchanged.** Registry membership determines whether a
  rule may be validated; it never enters the digest.
- **Migration is idempotent and all-or-nothing.** `migrated` and `already-current` are
  successful verdicts. Any blocking verdict leaves `science.yaml` byte-identical; an
  all-current `--apply` is also a byte-identical no-op.
- **Legacy matching requires every canonical validation producer to be wired.** An
  all-current run needs no producer execution. When any legacy entry exists, aggregate
  `validate` status is not sufficient evidence; inspect `RunResult.producer_results`.
- **Health remains diagnostic, not a severity gate.** Ordinary ERROR findings continue
  to exit 0. Only an unapplied acceptance configuration
  (`accepted-validation.legacy-shape` or `accepted-validation.invalid-entry`) exits 2.
- **Preserve YAML outside `health.accepted_validation`.** Use ruamel.yaml round-trip
  mode, preserve quotes/comments/order, render in memory, re-check the original bytes,
  then commit through `atomic_write_text`.
- **No stored case migration.** Re-verify that no surveyed consumer has
  `doc/audits/cases/` before applying configuration changes.
- **Consumer atomicity is per repository.** A Git-sourced consumer commit contains the
  migrated `science.yaml`, the Plan 3 toolkit pin, and regenerated `uv.lock` together.
  The in-repo `meta` project uses its existing editable `../science` source and lands its
  `science.yaml` in the toolkit cutover commit.
- **Use `~/d/` paths in documentation and commands.** Do not write host-specific
  `/mnt/ssd/Dropbox/` or `/home/keith/d/` paths.
- **Conventional commits only.** No AI-attribution trailer, compatibility layer, or
  `Unified` prefix.

## File Structure

### New focused modules

| File | Responsibility |
|---|---|
| `science/src/science_tool/findings/acceptance_migration.py` | Idempotent current-entry pass-through, old-shape matching, immutable migration results, per-check indeterminacy, duplicate-fingerprint detection across current/migrated entries, and replacement entry construction. No filesystem I/O. |
| `science/tests/test_acceptance_schema.py` | Replacement model, canonical severity scope, positive classification, total diagnostic identity, and fingerprint matcher tests. |
| `science/tests/test_acceptance_migration.py` | Pure seven-verdict migration, invalid-error preservation, idempotent current-entry pass-through, wildcard preservation, duplicate fingerprint, per-check indeterminacy, count-neutrality, and no-mutation CLI tests. |
| `science/tests/test_acceptance_migration_real_projects.py` | Opt-in staged dry-run over the four surveyed projects. |

### Existing modules changed

| File | Responsibility in Plan 3 |
|---|---|
| `science/src/science_tool/validate/acceptance.py` | Replacement entry model, raw entry loading/classification, raw diagnostic digest, fingerprint matcher, and warn-only validate filtering. |
| `science/src/science_tool/findings/cli.py` | `science findings migrate-acceptances`, rendering, exit behavior, and the one atomic config write. |
| `science/src/science_tool/validate/result.py` | Adds an explicit canonical-subject override while retaining `Result` as the one finding observation shape. |
| `science/src/science_tool/validate/findings.py` | Threads the optional subject override through `validation_observation`. |
| `science/src/science_tool/graph/health_checks/validate.py` | Exposes one shared validation-health execution result for health and migration; propagates aggregate `unwired` when any canonical validation producer is unwired. |
| `science/src/science_tool/graph/health.py` | Applies only valid current fingerprint acceptances using the exact report registry. |
| `science/src/science_tool/validate/checks/accepted_validation.py` | Replaces evidence-scope lint with the `legacy-shape` and `invalid-entry` ERROR findings. |
| `science/src/science_tool/validate/checks/correspondence_drift.py` | Removes old evidence-scoped-acceptance wording; the existing signature identity qualifier remains unchanged. |
| `science/src/science_tool/validate/cli.py` | Uses the replacement matcher with `RunResult.registry`, remaining warn-only. |
| `science/src/science_tool/graph/health_cli.py` | Exits 2 after complete emission when the report contains an acceptance-configuration finding; ordinary ERROR findings still exit 0. |
| `docs/user-guide/health-and-validation.md` | Documents the new schema, migration command, fingerprint semantics, and exit-2 configuration gate. |
| `meta/science.yaml` | In-repo consumer migration in the atomic cutover commit. |

### Existing tests updated or retired

- `science/tests/test_acceptance_authority.py`
- `science/tests/test_health_acceptance_parity.py`
- `science/tests/test_correspondence_drift_health_integration.py`
- `science/tests/test_health.py`
- `science/tests/test_health_cli_budget.py`
- `science/tests/validate/test_checks_accepted_validation.py`
- `science/tests/validate/test_finding_families.py`
- `science/tests/validate/test_runner.py`
- `science/tests/validate/test_validate_cli.py`

## Interfaces

The following names are fixed for all tasks:

```python
# science_tool.validate.acceptance
AcceptanceSeverity = Literal["warn", "error"]

class AcceptedValidationEntry(BaseModel): ...

@dataclass(frozen=True)
class CurrentAcceptance:
    raw_digest: str
    entry: AcceptedValidationEntry

@dataclass(frozen=True)
class LegacyAcceptance:
    raw_digest: str
    raw: Mapping[str, object]

@dataclass(frozen=True)
class InvalidAcceptance:
    raw_digest: str
    error: str

ClassifiedAcceptance = CurrentAcceptance | LegacyAcceptance | InvalidAcceptance

def raw_acceptance_digest(raw: object) -> str: ...
def classify_acceptance_entry(raw: object) -> ClassifiedAcceptance: ...
def accepted_validation_entries(project_root: Path) -> list[object]: ...
def partition_accepted_findings(
    entries: Sequence[object],
    findings: Sequence[ReportedFinding],
    *,
    registry: FindingRegistry,
) -> tuple[list[ReportedFinding], list[AcceptedFinding]]: ...
def filter_accepted_warnings(
    project_root: Path,
    results: list[AuditFinding],
    *,
    registry: FindingRegistry,
) -> list[AuditFinding]: ...

# science_tool.findings.acceptance_migration
InstrumentStatus = Literal["ok", "empty", "unwired"]

@dataclass(frozen=True)
class MigrationRow:
    finding: AuditFinding
    finding_id: str

MigrationVerdict = Literal[
    "migrated",
    "already-current",
    "invalid",
    "stale",
    "ambiguous",
    "duplicate",
    "indeterminate",
]

@dataclass(frozen=True)
class EntryMigration:
    entry_index: int
    verdict: MigrationVerdict
    replacement: AcceptedValidationEntry | None
    detail: str

@dataclass(frozen=True)
class AcceptanceMigration:
    entries: tuple[EntryMigration, ...]
    indeterminate_producers: tuple[str, ...]

    @property
    def can_apply(self) -> bool: ...

    @property
    def needs_write(self) -> bool: ...

    @property
    def output_entries(self) -> tuple[AcceptedValidationEntry, ...]: ...

def classify_migration(
    entries: Sequence[object],
    rows: Sequence[MigrationRow],
    producer_statuses: Mapping[str, InstrumentStatus],
) -> AcceptanceMigration: ...
```

`MigrationRow` is the pure boundary that lets the CLI compute fingerprints once with
`validate_finding(run_result.registry, "validate", finding)` and keeps the migration
engine independent of registry construction and I/O.

## Design-test Accountability

| Design test | Plan step |
|---|---|
| 24 acceptance-key wildcards, malformed text, duplicate collapse | Task 1 steps 5–8; Task 2 steps 1–4 |
| 25 all migration outcomes and all-or-nothing apply | Task 1 steps 5–8; Task 2 steps 1–8 |
| 33 per-check indeterminacy, idempotent pass-through, and every verdict | Task 1 steps 5–8; Task 2 steps 1–8 |
| 34 count neutrality | Task 1 step 5; Task 4 count comparison |
| 35 complete report plus narrow exit 2 | Task 3 steps 1–8 |
| 36 positive total classification and canonical scope | Task 1 steps 1–4; Task 3 steps 1–5 |
| 37 four live corpora dry-run cleanly | Task 2 step 7; Task 4 |

---

### Task 1: Replacement acceptance schema and pure migration core

**Files:**

- Create: `science/src/science_tool/findings/acceptance_migration.py`
- Modify: `science/src/science_tool/validate/acceptance.py`
- Create: `science/tests/test_acceptance_schema.py`
- Create: `science/tests/test_acceptance_migration.py`
- Modify: `science/tests/test_acceptance_authority.py`

**Interfaces:** Produce every interface listed above except filesystem rewrite and CLI
entry points. Plan 2 health remains wired through its existing partition until Task 3.

- [ ] **Step 1: Write failing replacement-schema and classification tests**

```python
# science/tests/test_acceptance_schema.py
from datetime import date

import pytest
from pydantic import ValidationError

from science_tool.validate.acceptance import (
    AcceptedValidationEntry,
    CurrentAcceptance,
    InvalidAcceptance,
    LegacyAcceptance,
    classify_acceptance_entry,
    raw_acceptance_digest,
)


BASE = {
    "finding_id": "a" * 64,
    "fingerprint_version": 1,
    "severity_scope": ["warn"],
    "reason": "reviewed",
}


@pytest.mark.parametrize(
    ("raw_scope", "expected"),
    [
        (["warn"], ("warn",)),
        (["error", "warn"], ("warn", "error")),
        (["warn", "warn"], ("warn",)),
        (["warn", "error"], ("warn", "error")),
    ],
)
def test_severity_scope_is_a_canonical_nonempty_set(raw_scope, expected):
    entry = AcceptedValidationEntry.model_validate({**BASE, "severity_scope": raw_scope})
    assert entry.severity_scope == expected
    assert entry.model_dump(mode="json")["severity_scope"] == list(expected)


@pytest.mark.parametrize("bad", [[], ["info"], "warn", [1], None])
def test_severity_scope_refuses_every_other_shape(bad):
    with pytest.raises(ValidationError):
        AcceptedValidationEntry.model_validate({**BASE, "severity_scope": bad})


def test_current_shape_is_selected_by_presence_of_finding_id():
    classified = classify_acceptance_entry(BASE)
    assert isinstance(classified, CurrentAcceptance)
    assert classified.entry.finding_id == "a" * 64


@pytest.mark.parametrize(
    "raw",
    [
        {**BASE, "fingerprint_version": 2},
        {**BASE, "severity_scope": ["info"]},
        {**BASE, "reason": " "},
        {**BASE, "typo": True},
    ],
)
def test_invalid_current_shape_never_falls_back_to_legacy(raw):
    classified = classify_acceptance_entry(raw)
    assert isinstance(classified, InvalidAcceptance)
    assert "legacy" not in classified.error.lower()


def test_old_shape_is_positive_legacy_classification():
    classified = classify_acceptance_entry(
        {"rule": "manifest.check", "severity": "warning", "reason": "reviewed"}
    )
    assert isinstance(classified, LegacyAcceptance)


@pytest.mark.parametrize("raw", ["scalar", 42, None, {"reason": "missing identity"}])
def test_every_other_yaml_entry_is_invalid_with_a_stable_subject_digest(raw):
    classified = classify_acceptance_entry(raw)
    assert isinstance(classified, InvalidAcceptance)
    assert classified.raw_digest == raw_acceptance_digest(raw)
    assert len(classified.raw_digest) == 32


def test_optional_accepted_on_is_an_iso_date():
    entry = AcceptedValidationEntry.model_validate(
        {**BASE, "accepted_on": "2026-07-29"}
    )
    assert entry.accepted_on == date(2026, 7, 29)
```

Keep the digest vector independent:

```python
def test_raw_acceptance_digest_has_a_literal_oracle():
    assert raw_acceptance_digest("scalar") == "1cf2462dbf783967e4408e886e4569a7"
```

The literal is the first 32 hex characters produced independently by:

```bash
printf '"scalar"' | sha256sum
```

The production helper must not compute its own expected value in the test.

- [ ] **Step 2: Run the schema tests and confirm the new interface is absent**

```bash
cd science
uv run --frozen pytest tests/test_acceptance_schema.py -q
```

Expected: collection fails because `AcceptedValidationEntry`,
`classify_acceptance_entry`, and `raw_acceptance_digest` do not exist.

- [ ] **Step 3: Implement the replacement model and positive classifier**

Add to `validate/acceptance.py`:

```python
from dataclasses import dataclass
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

AcceptanceSeverity = Literal["warn", "error"]
_SEVERITY_ORDER = {"warn": 0, "error": 1}


class AcceptedValidationEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    finding_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    fingerprint_version: Literal[1]
    severity_scope: tuple[AcceptanceSeverity, ...]
    reason: str
    accepted_on: date | None = None

    @field_validator("severity_scope", mode="before")
    @classmethod
    def _canonical_scope(cls, value: object) -> tuple[str, ...]:
        if not isinstance(value, list) or not value:
            raise ValueError("severity_scope must be a non-empty list")
        if any(item not in _SEVERITY_ORDER for item in value):
            raise ValueError("severity_scope members must be 'warn' or 'error'")
        return tuple(sorted(set(value), key=_SEVERITY_ORDER.__getitem__))

    @field_validator("reason")
    @classmethod
    def _nonblank_reason(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("reason must be nonblank")
        return normalized

    @property
    def acceptance_key(self) -> str:
        fields = {
            "finding_id": self.finding_id,
            "severity_scope": list(self.severity_scope),
        }
        payload = b"science.acceptance.v1\n" + canonical_json(fields)
        return hashlib.sha256(payload).hexdigest()[:32]


@dataclass(frozen=True)
class CurrentAcceptance:
    raw_digest: str
    entry: AcceptedValidationEntry


@dataclass(frozen=True)
class LegacyAcceptance:
    raw_digest: str
    raw: Mapping[str, object]


@dataclass(frozen=True)
class InvalidAcceptance:
    raw_digest: str
    error: str
```

Implement `raw_acceptance_digest(raw)` as the first 32 hex characters of SHA-256 over
`canonical_json(raw)`. Do not incorporate the acceptance list position, the model parse
result, or registry state.

Implement the classifier in this order:

```python
def classify_acceptance_entry(raw: object) -> ClassifiedAcceptance:
    digest = raw_acceptance_digest(raw)
    if isinstance(raw, Mapping) and "finding_id" in raw:
        try:
            entry = AcceptedValidationEntry.model_validate(dict(raw))
        except ValidationError as exc:
            return InvalidAcceptance(digest, str(exc))
        return CurrentAcceptance(digest, entry)
    if isinstance(raw, Mapping) and isinstance(raw.get("rule"), str):
        return LegacyAcceptance(digest, dict(raw))
    return InvalidAcceptance(
        digest,
        "entry must be a current finding_id mapping or a legacy mapping with string rule",
    )
```

Do not catch current-model failure and retry legacy parsing.

- [ ] **Step 4: Run the replacement-schema tests**

```bash
cd science
uv run --frozen pytest tests/test_acceptance_schema.py -q
```

Expected: PASS.

- [ ] **Step 5: Write failing pure migration tests**

```python
# science/tests/test_acceptance_migration.py
from datetime import date

import pytest
from science_model.audit import PathSubject

from science_tool.findings.acceptance_migration import (
    MigrationRow,
    classify_migration,
)
from science_tool.validate.acceptance import (
    InvalidAcceptance,
    classify_acceptance_entry,
)
from science_tool.validate.checks.manifest import RULES


def _finding(message: str, *, key: list[str] | None = None):
    return RULES["manifest.check"].build(
        subject=PathSubject(path="science.yaml"),
        severity="warn",
        qualifiers={"key": key or ["profile"]},
        message=message,
    )


def _legacy(**overrides):
    return {
        "rule": "manifest.check",
        "severity": "warning",
        "path": "science.yaml",
        "message_contains": ["missing profile"],
        "reason": "reviewed",
        **overrides,
    }


def _current(finding_id: str = "c" * 64, **overrides):
    return {
        "finding_id": finding_id,
        "fingerprint_version": 1,
        "severity_scope": ["warn"],
        "reason": "already reviewed",
        "accepted_on": "2026-07-01",
        **overrides,
    }


def test_unique_match_migrates_and_preserves_warning_scope():
    row = MigrationRow(_finding("missing profile"), "a" * 64)
    result = classify_migration([_legacy()], [row], {"validate.manifest": "ok"})
    assert result.can_apply
    assert result.needs_write
    assert result.entries[0].verdict == "migrated"
    assert result.entries[0].replacement.severity_scope == ("warn",)


def test_wildcard_severity_preserves_warn_and_error_scope():
    row = MigrationRow(_finding("missing profile"), "a" * 64)
    entry = _legacy()
    del entry["severity"]
    result = classify_migration([entry], [row], {"validate.manifest": "ok"})
    assert result.entries[0].replacement.severity_scope == ("warn", "error")


def test_current_entry_is_idempotent_without_producer_evidence():
    result = classify_migration(
        [_current()],
        [],
        {"validate.references": "unwired"},
    )
    assert result.indeterminate_producers == ()
    assert result.can_apply
    assert not result.needs_write
    assert result.entries[0].verdict == "already-current"
    assert result.entries[0].replacement.accepted_on == date(2026, 7, 1)
    assert result.output_entries == (result.entries[0].replacement,)


@pytest.mark.parametrize(
    "raw",
    [
        _current(fingerprint_version=2),
        "scalar",
    ],
)
def test_invalid_entry_is_not_stale_and_preserves_classifier_error(raw):
    classified = classify_acceptance_entry(raw)
    assert isinstance(classified, InvalidAcceptance)

    result = classify_migration([raw], [], {})

    assert not result.can_apply
    assert result.entries[0].verdict == "invalid"
    assert result.entries[0].replacement is None
    assert result.entries[0].detail == classified.error


def test_mixed_current_and_legacy_entries_preserve_order():
    row = MigrationRow(_finding("missing profile"), "a" * 64)
    result = classify_migration(
        [_current(), _legacy()],
        [row],
        {"validate.manifest": "ok"},
    )
    assert [item.verdict for item in result.entries] == [
        "already-current",
        "migrated",
    ]
    assert [entry.finding_id for entry in result.output_entries] == [
        "c" * 64,
        "a" * 64,
    ]
    assert result.can_apply
    assert result.needs_write


def test_zero_and_multiple_matches_are_stale_and_ambiguous():
    rows = [
        MigrationRow(_finding("missing profile", key=["profile"]), "a" * 64),
        MigrationRow(_finding("missing profile", key=["name"]), "b" * 64),
    ]
    assert classify_migration(
        [_legacy(message_contains=["absent"])], rows, {"validate.manifest": "ok"}
    ).entries[0].verdict == "stale"
    assert classify_migration(
        [_legacy(message_contains=["missing"])], rows, {"validate.manifest": "ok"}
    ).entries[0].verdict == "ambiguous"


def test_duplicate_finding_id_rejects_even_different_scopes():
    row = MigrationRow(_finding("missing profile"), "a" * 64)
    wildcard = _legacy()
    del wildcard["severity"]
    result = classify_migration(
        [_legacy(), wildcard], [row], {"validate.manifest": "ok"}
    )
    assert [item.verdict for item in result.entries] == ["duplicate", "duplicate"]
    assert not result.can_apply


def test_duplicate_detection_spans_current_and_migrated_entries():
    row = MigrationRow(_finding("missing profile"), "a" * 64)
    result = classify_migration(
        [_current("a" * 64), _legacy()],
        [row],
        {"validate.manifest": "ok"},
    )
    assert [item.verdict for item in result.entries] == ["duplicate", "duplicate"]
    assert not result.can_apply


def test_any_unwired_check_is_indeterminate_before_matching():
    result = classify_migration(
        [_legacy()],
        [],
        {"validate.manifest": "ok", "validate.references": "unwired"},
    )
    assert result.indeterminate_producers == ("validate.references",)
    assert result.entries[0].verdict == "indeterminate"
    assert "validate.references" in result.entries[0].detail
```

Add the two malformed `message_contains` cases from design test 24 and assert `stale`.
Add a count-neutrality test that constructs old and migrated matchers over the same
synthetic warn/error rows and compares the suppressed `(finding_id, severity)` sets.

- [ ] **Step 6: Run the migration tests and confirm the engine is absent**

```bash
cd science
uv run --frozen pytest tests/test_acceptance_migration.py -q
```

Expected: collection fails because `acceptance_migration.py` and its interfaces do not
exist.

- [ ] **Step 7: Implement the pure migration engine without moving the live matcher**

Import these existing Plan 2 functions from `validate/acceptance.py`:

- `canonical_acceptance_severity`
- `entry_matches`
- `legacy_validation_fields`

Leave those functions and their `_text_matches` / `_severity_matches` helpers in
`validate/acceptance.py` through Tasks 1–2. Its live
`_pre_migration_key_fields`, `partition_health_acceptances`, `_severity_matches`,
`entry_suppresses`, and `filter_accepted_warnings` callers make moving them now cyclic:
`acceptance.py` would import the migration module while the migration module imports the
replacement model and `AcceptanceSeverity` from `acceptance.py`. The dependency is one
way instead: migration imports acceptance. Task 3 moves the old matcher only after
deleting the final health/validate callers.

Implement immutable migration result dataclasses and `classify_migration`:

1. Classify every raw value through `classify_acceptance_entry`.
2. A `CurrentAcceptance` becomes `already-current` with its validated
   `AcceptedValidationEntry` as `replacement`; it does not require producer evidence.
3. An `InvalidAcceptance` becomes `invalid` with no replacement and
   `detail=classified.error`. Never retry a current-shaped model failure as legacy, and
   never describe an entry that was not interpreted as `stale`.
4. Sort producer IDs whose status is `unwired`. If any legacy entry exists and that set
   is non-empty, mark each legacy entry `indeterminate` naming those producers before
   calling `entry_matches`; leave current entries `already-current`.
5. Otherwise match each `LegacyAcceptance` against all `MigrationRow.finding` values
   using the imported exact old matcher and `legacy_validation_fields`.
6. Zero matches → `stale`; more than one → `ambiguous`; one → construct an
   `AcceptedValidationEntry` replacement, omitting `accepted_on`.
7. Group every non-`None` replacement by `finding_id`; replace every member of a repeated
   group with `duplicate`, regardless of severity scope or source shape.
8. `can_apply` is true only when every verdict is `migrated` or `already-current`.
   `needs_write` is true only when `can_apply` and at least one verdict is `migrated`.
   `output_entries` preserves input order and raises `ValueError` when `can_apply` is
   false.

Do not silently deduplicate, choose the first match, or narrow wildcard severity to the
currently observed row. Do not rewrite an all-current config.

- [ ] **Step 8: Run pure schema/migration and preserved Plan 2 tests**

```bash
cd science
uv run --frozen pytest \
  tests/test_acceptance_schema.py \
  tests/test_acceptance_migration.py \
  tests/test_acceptance_authority.py \
  tests/test_health_acceptance_parity.py \
  tests/test_correspondence_drift_health_integration.py -q
```

Expected: PASS. Plan 2 health behavior remains unchanged at this checkpoint.

- [ ] **Step 9: Commit the acceptance core**

```bash
git add \
  science/src/science_tool/findings/acceptance_migration.py \
  science/src/science_tool/validate/acceptance.py \
  science/tests/test_acceptance_schema.py \
  science/tests/test_acceptance_migration.py \
  science/tests/test_acceptance_authority.py
git commit -m "feat(findings): define acceptance migration core"
```

---

### Task 2: Migration CLI, atomic YAML rewrite, and real-corpus dry run

**Files:**

- Modify: `science/src/science_tool/findings/cli.py`
- Modify: `science/src/science_tool/findings/acceptance_migration.py`
- Modify: `science/src/science_tool/graph/health_checks/validate.py`
- Modify: `science/tests/test_findings_cli.py`
- Modify: `science/tests/test_acceptance_migration.py`
- Modify: `science/tests/validate/test_runner.py`
- Create: `science/tests/test_acceptance_migration_real_projects.py`

**Interfaces:**

- Consumes Task 1's `classify_migration`, `MigrationRow`, and result dataclasses.
- Produces:

```python
def run_acceptance_migration(project_root: Path) -> AcceptanceMigration: ...
def render_migrated_config(
    original_text: str,
    entries: Sequence[AcceptedValidationEntry],
) -> str: ...
def apply_migrated_config(
    project_root: Path,
    *,
    expected_original: str,
    rendered: str,
) -> None: ...

# science_tool.graph.health_checks.validate
@dataclass(frozen=True)
class ValidationHealthRun:
    run_result: RunResult
    producer_result: FindingProducerResult

def execute_validation(project_root: Path) -> ValidationHealthRun: ...
```

- [ ] **Step 1: Write failing CLI dry-run tests**

Extend `test_findings_cli.py` with a fixture that monkeypatches
`run_acceptance_migration` to return one migrated entry. Assert:

```python
def test_migrate_acceptances_is_dry_run_by_default(tmp_path, monkeypatch):
    original = _legacy_config()
    path = tmp_path / "science.yaml"
    path.write_text(original, encoding="utf-8")
    monkeypatch.setattr(findings_cli, "run_acceptance_migration", _successful_result)

    result = CliRunner().invoke(
        findings_group,
        ["migrate-acceptances", "--project-root", str(tmp_path), "--format", "json"],
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["can_apply"] is True
    assert path.read_text(encoding="utf-8") == original
```

Add parameterized failing outcomes for `invalid`, `stale`, `ambiguous`, `duplicate`, and
`indeterminate`; each exits 2 and leaves the file byte-identical. For `invalid`, assert
the JSON/table detail is the exact `InvalidAcceptance.error` produced by positive
classification. Assert dry-run reports every problem entry rather than stopping at the
first.

Add an all-current `--apply` case. Its fixture returns one `already-current` entry with
`can_apply=True` and `needs_write=False`; assert exit 0, JSON `applied` is false, and
`science.yaml` is byte-identical. Add a mixed current/legacy success case and assert
`accepted_on` from the current entry survives while the migrated entry omits it.

In `validate/test_runner.py`, add a focused test that monkeypatches
`validate_runner.run` to one fixed `RunResult`, calls `execute_validation`, and asserts
the returned `producer_result.instrument.rows` are exactly that result's non-INFO rows
in order while `ValidationHealthRun.run_result` is the identical object. This prevents
the migration path from constructing a second validation stream.

- [ ] **Step 2: Write failing apply/round-trip tests**

Use a config containing comments, quoted scalars, unrelated top-level keys, and fields
before and after `health.accepted_validation`. Assert `--apply`:

- replaces only the list entries;
- emits `finding_id`, `fingerprint_version`, canonical `severity_scope`, and `reason`;
- omits `accepted_on` for migrated entries;
- preserves `accepted_on` for already-current entries in a mixed rewrite;
- removes `rule`, `severity`, `path`, `task`, and `message_contains`;
- preserves comments, quotes, key order, and all unrelated values;
- writes once atomically;
- refuses if the bytes change between planning and write.

The expected acceptance fragment is:

```yaml
health:
  accepted_validation:
    - finding_id: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
      fingerprint_version: 1
      severity_scope:
        - warn
      reason: reviewed
```

- [ ] **Step 3: Run the CLI tests and verify the command is absent**

```bash
cd science
uv run --frozen pytest \
  tests/test_findings_cli.py \
  tests/test_acceptance_migration.py \
  tests/validate/test_runner.py -q
```

Expected: new tests fail because `migrate-acceptances` and the write helpers do not
exist.

- [ ] **Step 4: Share the exact validation-health execution with migration**

Refactor `graph/health_checks/validate.py` so `execute_validation(project_root)` calls:

```python
run_result = validate_runner.run(
    project_root,
    strict=False,
    verbose=False,
    enable_python_sidecar=False,
)
```

It must project the non-INFO `run_result.results` into the same
`FindingProducerResult` that `run_check` returns today, package both objects in
`ValidationHealthRun`, and make `run_check(context)` return only
`execute_validation(context.project_root).producer_result`. At this checkpoint preserve
the Plan 2 aggregate-status behavior exactly; Task 3 changes its unwired propagation.

In `findings/cli.py`, add `run_acceptance_migration(project_root)`. Load the raw entries
first and classify each with `classify_acceptance_entry`. If none is a
`LegacyAcceptance`, call `classify_migration(entries, (), {})` without running
validation; this is the idempotent all-current path.

If at least one legacy entry exists, call `execute_validation(project_root)` once.
Construct the per-check status map from `execution.run_result.producer_results` and the
migration rows from `execution.producer_result.instrument.rows`:

```python
producer_statuses = {
    producer_id: result.instrument.status
    for producer_id, result in execution.run_result.producer_results.items()
}
rows = [
    MigrationRow(
        finding=finding,
        finding_id=validate_finding(
            execution.run_result.registry,
            "validate",
            finding,
        ),
    )
    for finding in execution.producer_result.instrument.rows
]
```

Call `classify_migration(entries, rows, producer_statuses)`. This path must use
`RunResult.producer_results`; never infer completeness from the aggregate health
producer. It must also use the shared health projection's rows rather than independently
filtering `RunResult.results`.

- [ ] **Step 5: Implement round-trip rendering and compare-before-write**

Use `YAML(typ="rt")`, `preserve_quotes = True`, and `io.StringIO`. Parse the original
text, navigate to the existing `health.accepted_validation` list, and replace that list
with plain ordered mappings built from each `AcceptedValidationEntry` in
`migration.output_entries` via
`entry.model_dump(mode="json", exclude_none=True)`. This emits canonical scope lists and
an ISO date while omitting absent `accepted_on`. Render the full document in memory.

Import the shared writer explicitly:

```python
from science_model.frontmatter import atomic_write_text
```

Implement the write guard with that import:

```python
def apply_migrated_config(
    project_root: Path,
    *,
    expected_original: str,
    rendered: str,
) -> None:
    path = project_config_path(project_root)
    if path.read_text(encoding="utf-8") != expected_original:
        raise ValueError("science.yaml changed after migration classification")
    atomic_write_text(path, rendered)
```

The comparison prevents a concurrent authored edit from being overwritten. The atomic
replace prevents a partial file. Neither permits partial entry migration.

- [ ] **Step 6: Implement `science findings migrate-acceptances`**

Add Click options:

```python
@findings_group.command("migrate-acceptances")
@click.option(
    "--project-root",
    type=click.Path(path_type=Path, file_okay=False),
    default=Path("."),
    show_default=True,
)
@click.option("--apply", is_flag=True, help="Atomically rewrite science.yaml.")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(OUTPUT_FORMATS),
    default="table",
    show_default=True,
)
def migrate_acceptances_command(
    project_root: Path,
    apply: bool,
    output_format: str,
) -> None:
    ...
```

The JSON payload contains:

```json
{
  "applied": false,
  "can_apply": true,
  "needs_write": true,
  "indeterminate_producers": [],
  "entries": [
    {
      "entry_index": 0,
      "verdict": "migrated",
      "finding_id": "...",
      "severity_scope": ["warn"],
      "detail": "matched exactly one current finding"
    }
  ]
}
```

Render every entry in table mode. Exit 2 after rendering when `can_apply` is false.
An `invalid` row renders its classifier error verbatim in `detail`; do not replace it
with a generic no-match message.
With `--apply`, write only when `can_apply` and `needs_write`; after a successful write
report `applied: true`. When `can_apply` is true and `needs_write` is false, report
`applied: false`, exit 0, and do not render or write the config. Build and emit the final
payload once, after any requested write succeeds. Catch YAML, Pydantic, filesystem, and
compare-before-write errors as refusals with exit 2. Do not convert a failure into a
partial write.

- [ ] **Step 7: Add the opt-in four-project dry-run test**

Create `test_acceptance_migration_real_projects.py` with these authorities:

```python
PROJECTS = (
    Path(__file__).resolve().parents[2] / "meta",
    Path("~/d/natural-systems").expanduser(),
    Path("~/d/cancer/cancer-types/multiple-myeloma").expanduser(),
    Path("~/d/health/processes/post-acute-infection").expanduser(),
)
```

Mark the test `@pytest.mark.real_projects`. Copy each existing project to `tmp_path`
before running. For each staged copy:

1. assert there is no `doc/audits/cases/`;
2. call `run_acceptance_migration`;
3. assert every entry verdict is either `migrated` or `already-current`;
4. assert `can_apply`;
5. never call the writer.

If a configured project is absent, skip with its `~/d/` path named. Do not mutate the
source project from the test.

- [ ] **Step 8: Run the CLI, migration, and real-project tests**

```bash
cd science
uv run --frozen pytest \
  tests/test_findings_cli.py \
  tests/test_acceptance_schema.py \
  tests/test_acceptance_migration.py \
  tests/validate/test_runner.py -q
uv run --frozen pytest -m real_projects \
  tests/test_acceptance_migration_real_projects.py -q
```

Expected: both commands PASS; all 50 surveyed entries have nonblocking `migrated` or
`already-current` verdicts. Before rollout they are all `migrated`; after Task 4 the same
test remains green with `already-current`.

- [ ] **Step 9: Commit the migration command**

```bash
git add \
  science/src/science_tool/findings/cli.py \
  science/src/science_tool/findings/acceptance_migration.py \
  science/src/science_tool/graph/health_checks/validate.py \
  science/tests/test_findings_cli.py \
  science/tests/test_acceptance_migration.py \
  science/tests/validate/test_runner.py \
  science/tests/test_acceptance_migration_real_projects.py
git commit -m "feat(findings): add acceptance migration command"
```

---

### Task 3: Atomic health/validate cutover and in-repo migration

**Files:**

- Modify: `science/src/science_tool/findings/acceptance_migration.py`
- Modify: `science/src/science_tool/validate/acceptance.py`
- Modify: `science/src/science_tool/validate/checks/accepted_validation.py`
- Modify: `science/src/science_tool/validate/checks/correspondence_drift.py`
- Modify: `science/src/science_tool/validate/result.py`
- Modify: `science/src/science_tool/validate/findings.py`
- Modify: `science/src/science_tool/validate/cli.py`
- Modify: `science/src/science_tool/graph/health_checks/validate.py`
- Modify: `science/src/science_tool/graph/health.py`
- Modify: `science/src/science_tool/graph/health_cli.py`
- Modify: `science/tests/test_health_acceptance_parity.py`
- Modify: `science/tests/test_correspondence_drift_health_integration.py`
- Modify: `science/tests/test_health.py`
- Modify: `science/tests/test_health_cli_budget.py`
- Modify: `science/tests/validate/test_checks_accepted_validation.py`
- Modify: `science/tests/validate/test_finding_families.py`
- Modify: `science/tests/validate/test_runner.py`
- Modify: `science/tests/validate/test_validate_cli.py`
- Modify: `docs/user-guide/health-and-validation.md`
- Modify: `meta/science.yaml`

**Interfaces:**

- Consumes Tasks 1–2 in full.
- Replaces the Plan 2 partition with `partition_accepted_findings(..., registry=...)`.
- Adds `Result.subject: FindingSubject | None = None`; `CheckObservation` remains
  `Result | ValidationMetricObservation | ValidationNotice`.
- Adds:

```python
ACCEPTANCE_CONFIGURATION_RULES = frozenset(
    {
        "accepted-validation.legacy-shape",
        "accepted-validation.invalid-entry",
    }
)

def report_has_invalid_acceptance_configuration(report: AuditReport) -> bool: ...
```

- [ ] **Step 1: Capture the in-repo pre-cutover baseline**

Before changing health behavior, verify `meta` has no stored cases and capture its old
configured counts:

```bash
test ! -d meta/doc/audits/cases
mkdir -p /tmp/finding-convergence-plan3-baselines
cd meta
uv run --frozen science health --format json \
  --output /tmp/finding-convergence-plan3-baselines/meta-before.json
```

Record `findings_total`, `accepted_total`, and `findings_by_severity`:

```bash
cd science
uv run --frozen python -c \
  'import json; p=json.load(open("/tmp/finding-convergence-plan3-baselines/meta-before.json")); print(p["totals"])'
```

Do not modify `meta/science.yaml` yet.

- [ ] **Step 2: Write failing positive-classification hygiene tests**

Replace the evidence-scope tests in
`validate/test_checks_accepted_validation.py` with:

```python
def test_legacy_entry_emits_migration_error(tmp_path):
    _write_entries(
        tmp_path,
        [{"rule": "manifest.check", "severity": "warning", "reason": "reviewed"}],
    )
    findings = _run_check(tmp_path)
    assert [item.rule_id for item in findings] == [
        "accepted-validation.legacy-shape"
    ]
    assert findings[0].severity == "error"
    assert findings[0].subject.type == "identifier"
    assert "migrate-acceptances" in findings[0].message


@pytest.mark.parametrize(
    "raw",
    [
        "scalar",
        {"reason": "missing identity"},
        {
            "finding_id": "a" * 64,
            "fingerprint_version": 2,
            "severity_scope": ["warn"],
            "reason": "reviewed",
        },
    ],
)
def test_invalid_entry_emits_invalid_not_legacy(tmp_path, raw):
    _write_entries(tmp_path, [raw])
    findings = _run_check(tmp_path)
    assert [item.rule_id for item in findings] == [
        "accepted-validation.invalid-entry"
    ]
    assert findings[0].subject.type == "identifier"


def test_valid_current_entry_emits_no_hygiene_finding(tmp_path):
    _write_entries(tmp_path, [_current_entry()])
    assert _run_check(tmp_path) == []
```

Add a duplicate-identical-raw-entry case and assert the check groups it into one finding
rather than violating the producer duplicate-identity boundary.

In `validate/test_runner.py`, add a focused `Result.to_finding` test using an
`IdentifierSubject`. Assert the subject is preserved exactly and that constructing a
`Result` with both a subject override and a non-`None` path raises `ValueError`.

- [ ] **Step 3: Write failing fingerprint matcher and validate-CLI tests**

Replace prose/path matching tests with fingerprints computed through the exact registry:

```python
finding_id = validate_finding(registry, "validate", finding)
entry = {
    "finding_id": finding_id,
    "fingerprint_version": 1,
    "severity_scope": ["warn"],
    "reason": "reviewed",
}
```

Assert:

- health moves exactly that warn finding to `accepted`;
- the accepted envelope carries `entry.acceptance_key` and stripped reason;
- a later error with the same fingerprint is not accepted by warn-only scope;
- wildcard-migrated `["warn", "error"]` accepts either;
- no validation entry accepts a non-`validate` producer;
- `science validate` still suppresses warn only and leaves error;
- legacy/invalid entries suppress nothing.

- [ ] **Step 4: Write failing per-check aggregation tests**

In `validate/test_runner.py`, force one non-prose-lints canonical check to raise and
assert its exact producer result is `unwired`. In the health validate producer test,
provide a `RunResult` where:

```python
producer_results = {
    "validate.manifest": FindingProducerResult(
        instrument=InstrumentResult.unwired(
            code="check-error",
            reason="manifest failed",
        )
    ),
    "validate.prose-lints": _wired_numeric_result(),
}
```

Assert `graph.health_checks.validate.run_check` returns aggregate `unwired`, with code
`validation-checks-unwired`, a reason naming `validate.manifest`, no rows, and no
metrics. Add a two-failure case and assert producer IDs are sorted in the reason.

- [ ] **Step 5: Write failing health exit-gate tests in all output modes**

Add parameterized coverage for:

```python
@pytest.mark.parametrize(
    "args",
    [
        [],
        ["--format", "json"],
        ["--format", "json", "--output", "health.json"],
    ],
)
def test_unapplied_acceptance_configuration_exits_2_after_complete_output(...):
    ...
```

For table mode, assert the legacy/invalid finding and unrelated findings are printed.
For JSON stdout, parse the complete `AuditReport`. For `--output`, parse the complete
file and assert the fixed control notice is still printed. All three exit 2.

Add the inverse:

```python
def test_ordinary_error_finding_does_not_gate_health(...):
    ...
    assert result.exit_code == 0
    assert report.totals.findings_by_severity["error"] == 1
```

This is the guard against accidentally converting all ERROR findings into a health gate.

- [ ] **Step 6: Run the cutover tests and verify old behavior is still present**

```bash
cd science
uv run --frozen pytest \
  tests/test_health_acceptance_parity.py \
  tests/test_correspondence_drift_health_integration.py \
  tests/test_health.py \
  tests/test_health_cli_budget.py \
  tests/validate/test_checks_accepted_validation.py \
  tests/validate/test_runner.py \
  tests/validate/test_validate_cli.py -q
```

Expected: the new tests fail against the Plan 2 health matcher, evidence-scope check,
single-producer unwired propagation, and exit-0-only CLI.

- [ ] **Step 7: Implement the atomic cutover**

Perform these changes in one commit:

1. `accepted_validation_entries` returns every raw list element; it no longer filters to
   mappings.
2. Implement `partition_accepted_findings` over valid `CurrentAcceptance` values only.
   Compute every candidate fingerprint with
   `validate_finding(registry, reported.producer_id, reported.finding)`.
3. Update `graph/health.py` to pass the exact `HealthExecution.registry`; delete
   `partition_health_acceptances`, `_pre_migration_key_fields`, and
   `pre_migration_acceptance_key` from `validate/acceptance.py`.
4. Update `filter_accepted_warnings` to require `registry` and use the same current
   matcher while retaining its explicit `finding.severity != "warn"` guard.
5. Add `subject: FindingSubject | None = None` to `Result` and to
   `validation_observation`. Fail early when both `subject` and `path` are non-`None`.
   `Result.to_finding` builds directly through its declared rule when the override is
   present; otherwise it retains the current path/project conversion. This keeps one
   finding observation shape instead of making `Result` and `AuditFinding` two
   interchangeable spellings; metrics and notices remain distinct observation kinds.
6. Rewrite `accepted_validation.py` with two direct `FindingRule` declarations using
   `validation_observation(..., subject=IdentifierSubject(
   namespace="accepted-validation", value=raw_digest))`. Deduplicate identical raw
   digests within one check pass.
7. After deleting the final steady-state callers, move
   `canonical_acceptance_severity`, `_text_matches`, `_severity_matches`,
   `entry_matches`, and `legacy_validation_fields` from `validate/acceptance.py` into
   `findings/acceptance_migration.py`. Update migration imports in the same edit.
   `validate/acceptance.py` must not import or re-export them.
8. Delete `entry_suppresses`, `EVIDENCE_SCOPED_RULES`, `SIGNATURE_TOKEN_SPEC`,
   `_message_contains_values`, `entry_is_evidence_scoped`,
   `entry_path_is_project_relative`, and `entry_is_well_scoped`.
9. Update correspondence-drift text to tell the operator to accept the fingerprinted
   finding; retain `evidence_signature` as the declared identity qualifier and do not
   change the fingerprint algorithm.
10. In `health_checks/validate.py`, collect every unwired entry from
   `run_result.producer_results`, sort producer IDs, and return aggregate unwired when the
   set is non-empty.
11. Add `report_has_invalid_acceptance_configuration` and call `sys.exit(2)` only after
    `emit`, `sink.flush`, and any `--output` control notice have completed. Base the
    decision on rule IDs in the complete report, not on displayed severity-filtered rows.

- [ ] **Step 8: Migrate `meta` inside the cutover**

Run the newly implemented command against the in-repo consumer:

```bash
cd science
uv run --frozen science findings migrate-acceptances \
  --project-root ../meta --format json
uv run --frozen science findings migrate-acceptances \
  --project-root ../meta --apply --format json
```

Expected: dry-run and apply both report every entry `migrated`; apply rewrites exactly
two entries. Then verify the new config:

```bash
cd meta
uv sync --frozen
uv run --frozen science health --format json \
  --output /tmp/finding-convergence-plan3-baselines/meta-after.json
```

Compare the before/after `findings_total`, `accepted_total`, and
`findings_by_severity`; they must be equal. `meta/uv.lock` must remain unchanged because
its existing source is the editable in-repo `../science`.

- [ ] **Step 9: Update the user guide**

Replace the old prose-key example with:

```yaml
health:
  accepted_validation:
    - finding_id: "<64-lowercase-hex>"
      fingerprint_version: 1
      severity_scope: ["warn"]
      reason: Reviewed residual risk; the project is intentionally retaining it.
```

Document:

- `science findings migrate-acceptances` is dry-run by default;
- `--apply` is all-or-nothing;
- migrated entries omit `accepted_on` because their historical acceptance date is
  unknown;
- rerunning the command reports valid replacement entries as `already-current`; an
  all-current `--apply` exits 0 without rewriting the file;
- migration reports syntax/model failures as `invalid` with the classifier error, while
  `stale` is reserved for a valid legacy matcher that found no current finding;
- `warn` and `error` are canonical spellings;
- only validation findings are eligible and `science validate` remains warn-only;
- legacy or invalid entries suppress nothing and make `science health` exit 2 after
  producing its complete output;
- ordinary ERROR findings do not change health's exit code.

- [ ] **Step 10: Run the complete scoped cutover suite**

```bash
cd science
uv run --frozen pytest \
  tests/test_acceptance_schema.py \
  tests/test_acceptance_migration.py \
  tests/test_findings_cli.py \
  tests/test_acceptance_authority.py \
  tests/test_health_acceptance_parity.py \
  tests/test_correspondence_drift_health_integration.py \
  tests/test_health.py \
  tests/test_health_cli_budget.py \
  tests/test_finding_convergence.py \
  tests/validate/test_checks_accepted_validation.py \
  tests/validate/test_finding_families.py \
  tests/validate/test_runner.py \
  tests/validate/test_validate_cli.py -q
```

Expected: PASS.

- [ ] **Step 11: Prove the old health surface is gone**

```bash
rg -n \
  "partition_health_acceptances|pre_migration_acceptance_key|_pre_migration_key_fields|EVIDENCE_SCOPED_RULES|entry_is_evidence_scoped|entry_path_is_project_relative|entry_is_well_scoped|evidence-scope-required" \
  science/src/science_tool science/tests docs/user-guide
```

Expected: no matches. The old matcher functions may appear only in
`science_tool/findings/acceptance_migration.py` under their unprefixed migration-only
names.

```bash
rg -n "message_contains|canonical_acceptance_severity|legacy_validation_fields|entry_matches" \
  science/src/science_tool
```

Expected: matches only in `findings/acceptance_migration.py` and its explicit CLI call
path; no health or validate steady-state reader imports them.

- [ ] **Step 12: Commit the cutover and in-repo migration**

```bash
git add \
  science/src/science_tool/findings/acceptance_migration.py \
  science/src/science_tool/validate/acceptance.py \
  science/src/science_tool/validate/checks/accepted_validation.py \
  science/src/science_tool/validate/checks/correspondence_drift.py \
  science/src/science_tool/validate/result.py \
  science/src/science_tool/validate/findings.py \
  science/src/science_tool/validate/cli.py \
  science/src/science_tool/graph/health_checks/validate.py \
  science/src/science_tool/graph/health.py \
  science/src/science_tool/graph/health_cli.py \
  science/tests/test_health_acceptance_parity.py \
  science/tests/test_correspondence_drift_health_integration.py \
  science/tests/test_health.py \
  science/tests/test_health_cli_budget.py \
  science/tests/validate/test_checks_accepted_validation.py \
  science/tests/validate/test_finding_families.py \
  science/tests/validate/test_runner.py \
  science/tests/validate/test_validate_cli.py \
  docs/user-guide/health-and-validation.md \
  meta/science.yaml
git commit -m "refactor(findings): cut over fingerprint acceptances"
```

Do not stage `meta/uv.lock` unless `uv sync --frozen` proves the existing lock is
incorrect; a path-editable source does not acquire a Git pin.

---

### Task 4: External consumer migration and exact-pin rollout

**Repositories:**

- `~/d/natural-systems`
- `~/d/cancer/cancer-types/multiple-myeloma`
- `~/d/health/processes/post-acute-infection`

**Files per consumer:**

- Modify: `science.yaml`
- Modify: `uv.lock`
- Modify `pyproject.toml` only where it contains an explicit `rev` that must advance.

**Interfaces:** Consumes the reachable Task 3 cutover commit and the shipped migration
command. Produces one internally consistent commit per consumer.

- [ ] **Step 1: Obtain explicit authorization to publish the toolkit cutover**

From the toolkit worktree, inspect the exact unpublished state without changing the
remote:

```bash
git status --short
git log -1 --oneline
git branch --show-current
```

Use the configured `ohai` notification to tell the operator that the next step must
publish the Task 3 cutover through the public Science repository's default branch because
two consumers use unqualified Git sources. Wait for explicit authorization to cross that
external publication boundary. Do not treat permission to edit local consumer worktrees
as permission to push or integrate the toolkit.

- [ ] **Step 2: Publish and verify the authorized cutover**

After authorization, push the reviewed feature branch:

```bash
git push origin finding-convergence-plan-3
git fetch origin
```

Record the exact commit:

```bash
science_plan3_sha="$(git rev-parse HEAD)"
git ls-remote origin | rg "$science_plan3_sha"
git merge-base --is-ancestor "$science_plan3_sha" origin/main
```

Expected: the SHA is reachable from the public Science remote and is contained in
`origin/main` before any consumer lock is regenerated. Natural-systems and
multiple-myeloma use an unqualified Git source, so merely pushing the feature branch is
insufficient: `uv lock` resolves their source from the remote default branch. If branch
policy requires a PR or local merge first, stop here and resume after the cutover commit
is on `origin/main`; do not rewrite a consumer config against an unreachable or
non-resolving toolkit revision.

- [ ] **Step 3: Create isolated consumer worktrees**

Use the `superpowers:using-git-worktrees` skill at execution time. Preserve every
existing dirty main checkout. Create:

```text
~/d/natural-systems/.worktrees/finding-convergence-plan-3
~/d/cancer/cancer-types/multiple-myeloma/.worktrees/finding-convergence-plan-3
~/d/health/processes/post-acute-infection/.worktrees/finding-convergence-plan-3
```

Create one branch named `finding-convergence-plan-3` in each repository. Confirm each
worktree starts clean. Do not stash, reset, or absorb unrelated main-checkout changes.

- [ ] **Step 4: Capture old-pin/old-config baselines**

For each isolated consumer, before editing any file:

```bash
mkdir -p /tmp/finding-convergence-plan3-baselines

cd ~/d/natural-systems/.worktrees/finding-convergence-plan-3
uv sync --frozen
uv run --frozen science health --format json \
  --output /tmp/finding-convergence-plan3-baselines/natural-systems-before.json

cd ~/d/cancer/cancer-types/multiple-myeloma/.worktrees/finding-convergence-plan-3
uv sync --frozen
uv run --frozen science health --format json \
  --output /tmp/finding-convergence-plan3-baselines/multiple-myeloma-before.json

cd ~/d/health/processes/post-acute-infection/.worktrees/finding-convergence-plan-3
uv sync --frozen
uv run --frozen science health --format json \
  --output /tmp/finding-convergence-plan3-baselines/post-acute-infection-before.json
```

Record the toolkit source SHA from each `uv.lock` and the complete `totals` object.
Assert no project contains `doc/audits/cases/`.

- [ ] **Step 5: Dry-run and apply the migration from the Plan 3 toolkit**

Run from `~/d/science/science` (or the Plan 3 toolkit worktree's `science/` directory),
not from the consumer's old pinned environment:

```bash
uv run --frozen science findings migrate-acceptances \
  --project-root ~/d/natural-systems/.worktrees/finding-convergence-plan-3 \
  --format json
uv run --frozen science findings migrate-acceptances \
  --project-root ~/d/natural-systems/.worktrees/finding-convergence-plan-3 \
  --apply --format json
uv run --frozen science findings migrate-acceptances \
  --project-root ~/d/cancer/cancer-types/multiple-myeloma/.worktrees/finding-convergence-plan-3 \
  --format json
uv run --frozen science findings migrate-acceptances \
  --project-root ~/d/cancer/cancer-types/multiple-myeloma/.worktrees/finding-convergence-plan-3 \
  --apply --format json
uv run --frozen science findings migrate-acceptances \
  --project-root ~/d/health/processes/post-acute-infection/.worktrees/finding-convergence-plan-3 \
  --format json
uv run --frozen science findings migrate-acceptances \
  --project-root ~/d/health/processes/post-acute-infection/.worktrees/finding-convergence-plan-3 \
  --apply --format json
```

Expected entry counts are 3 for natural-systems, 24 for multiple-myeloma, and 21 for
post-acute-infection. Every dry-run and apply result must be `migrated`; any other
verdict stops the rollout with that consumer uncommitted.

- [ ] **Step 6: Advance each consumer to the exact reachable Plan 3 revision**

For natural-systems and multiple-myeloma, retain the canonical Git source in
`pyproject.toml` and regenerate only the exact lock selection:

```bash
cd ~/d/natural-systems/.worktrees/finding-convergence-plan-3
uv lock --upgrade-package science
uv sync --frozen

cd ~/d/cancer/cancer-types/multiple-myeloma/.worktrees/finding-convergence-plan-3
uv lock --upgrade-package science
uv sync --frozen
```

Verify both lockfiles contain the cutover SHA:

```bash
science_plan3_sha="$(git -C ~/d/science/.worktrees/finding-convergence-plan-3 rev-parse HEAD)"
rg -n "$science_plan3_sha" \
  ~/d/natural-systems/.worktrees/finding-convergence-plan-3/uv.lock \
  ~/d/cancer/cancer-types/multiple-myeloma/.worktrees/finding-convergence-plan-3/uv.lock
```

Expected: each lockfile has Science and science-model source records at that SHA.

Post-acute-infection carries an explicit `rev` in `pyproject.toml`. Resolve the SHA with
`git -C ~/d/science/.worktrees/finding-convergence-plan-3 rev-parse HEAD` and use
`apply_patch` to replace the old revision with that exact 40-hex value, then:

```bash
cd ~/d/health/processes/post-acute-infection/.worktrees/finding-convergence-plan-3
uv lock --upgrade-package science
uv sync --frozen
```

Verify both files name the same exact Plan 3 revision:

```bash
science_plan3_sha="$(git -C ~/d/science/.worktrees/finding-convergence-plan-3 rev-parse HEAD)"
rg -n "$science_plan3_sha" \
  ~/d/health/processes/post-acute-infection/.worktrees/finding-convergence-plan-3/pyproject.toml \
  ~/d/health/processes/post-acute-infection/.worktrees/finding-convergence-plan-3/uv.lock
```

Do not leave the old rev in one file and the new rev in the other.

- [ ] **Step 7: Capture new-pin/new-config reports and compare counts**

In each consumer worktree:

```bash
cd ~/d/natural-systems/.worktrees/finding-convergence-plan-3
uv run --frozen science health --format json \
  --output /tmp/finding-convergence-plan3-baselines/natural-systems-after.json

cd ~/d/cancer/cancer-types/multiple-myeloma/.worktrees/finding-convergence-plan-3
uv run --frozen science health --format json \
  --output /tmp/finding-convergence-plan3-baselines/multiple-myeloma-after.json

cd ~/d/health/processes/post-acute-infection/.worktrees/finding-convergence-plan-3
uv run --frozen science health --format json \
  --output /tmp/finding-convergence-plan3-baselines/post-acute-infection-after.json
```

Compare every `totals` object in one pass:

```bash
uv run --frozen python -c '
import json
from pathlib import Path
root = Path("/tmp/finding-convergence-plan3-baselines")
for name in ("natural-systems", "multiple-myeloma", "post-acute-infection"):
    before = json.loads((root / f"{name}-before.json").read_text())["totals"]
    after = json.loads((root / f"{name}-after.json").read_text())["totals"]
    assert before == after, (name, before, after)
    print(name, before)
'
```

Equality must cover `findings_total`, `accepted_total`, `findings_by_severity`, and
`unwired_total`.

- [ ] **Step 8: Run each consumer's frozen validation**

For each consumer:

```bash
uv run --frozen science validate
uv run --frozen science health --format json
```

Expected: no `accepted-validation.legacy-shape`,
`accepted-validation.invalid-entry`, or exit 2. Preserve each project's pre-existing
validation outcome; this migration does not authorize unrelated fixes.

- [ ] **Step 9: Prove the installed migration is an idempotent no-op**

Run the installed command under each new consumer pin:

```bash
set -e
for science_consumer_root in \
  ~/d/natural-systems/.worktrees/finding-convergence-plan-3 \
  ~/d/cancer/cancer-types/multiple-myeloma/.worktrees/finding-convergence-plan-3 \
  ~/d/health/processes/post-acute-infection/.worktrees/finding-convergence-plan-3
do
  cd "$science_consumer_root"
  science_config_hash_before="$(sha256sum science.yaml)"
  science_migration_json="$(
    uv run --frozen science findings migrate-acceptances --apply --format json
  )"
  printf '%s\n' "$science_migration_json" |
    uv run --frozen python -c '
import json
import sys
payload = json.load(sys.stdin)
assert payload["applied"] is False
assert payload["can_apply"] is True
assert payload["needs_write"] is False
assert payload["entries"]
assert all(entry["verdict"] == "already-current" for entry in payload["entries"])
'
  science_config_hash_after="$(sha256sum science.yaml)"
  test "$science_config_hash_before" = "$science_config_hash_after"
done
```

Expected: every invocation exits 0, reports only `already-current`, and leaves
`science.yaml` byte-identical.

- [ ] **Step 10: Commit exact files in each consumer**

Natural-systems and multiple-myeloma:

```bash
git add science.yaml uv.lock
git diff --cached --check
git commit -m "chore(science): migrate validation acceptances"
```

Post-acute-infection:

```bash
git add pyproject.toml science.yaml uv.lock
git diff --cached --check
git commit -m "chore(science): migrate validation acceptances"
```

Inspect `git status --short` after each commit. No unrelated file belongs in these
commits. Push only repositories with a configured remote; record local commit SHAs for
repositories without one.

---

### Task 5: Full verification and implementation record

**Files:**

- Modify: `docs/plans/2026-07-27-finding-convergence-design.md`
- Modify: `docs/plans/2026-07-29-finding-convergence-plan-3-acceptance-migration.md`

**Interfaces:** None. This task proves the completed landing and records exact evidence.

- [ ] **Step 1: Re-run the Plan 3 scoped suite**

```bash
cd science
uv run --frozen pytest \
  tests/test_acceptance_schema.py \
  tests/test_acceptance_migration.py \
  tests/test_acceptance_migration_real_projects.py \
  tests/test_findings_cli.py \
  tests/test_acceptance_authority.py \
  tests/test_health_acceptance_parity.py \
  tests/test_correspondence_drift_health_integration.py \
  tests/test_health.py \
  tests/test_health_cli_budget.py \
  tests/test_finding_convergence.py \
  tests/validate/test_checks_accepted_validation.py \
  tests/validate/test_finding_families.py \
  tests/validate/test_runner.py \
  tests/validate/test_validate_cli.py -q
```

Expected: PASS. Run the real-project test explicitly too because the default marker
expression excludes it:

```bash
cd science
uv run --frozen pytest -m real_projects \
  tests/test_acceptance_migration_real_projects.py -q
```

Expected: all four staged corpora have only `migrated` or `already-current` verdicts and
`can_apply` is true. At this post-rollout checkpoint, all entries should be
`already-current`.

- [ ] **Step 2: Run the model suite**

```bash
cd science/model
uv run --frozen pytest
```

Expected: PASS. Plan 3 does not modify `science-model`; this is the frozen fingerprint
and report regression gate.

- [ ] **Step 3: Run the full toolkit suite with a long timeout**

```bash
cd science
uv run --frozen pytest
```

Expected: PASS. Allow at least 15 minutes.

- [ ] **Step 4: Run lint, changed-file formatting, and types**

```bash
cd science
uv run --frozen ruff check
uv run --frozen pyright
```

Expected: PASS.

Run package-local formatting only over Python files changed from `cc675a7a`:

```bash
cd science
git diff --name-only --diff-filter=ACMR cc675a7a..HEAD -- '*.py' |
  sed 's#^science/##' |
  xargs uv run --frozen ruff format --check
```

Expected: PASS. Do not claim the unrelated repository-wide formatting baseline passes
unless it was actually run and returned zero.

- [ ] **Step 5: Re-run forbidden-surface searches**

```bash
rg -n \
  "partition_health_acceptances|pre_migration_acceptance_key|_pre_migration_key_fields|EVIDENCE_SCOPED_RULES|entry_is_evidence_scoped|entry_path_is_project_relative|entry_is_well_scoped|evidence-scope-required" \
  science/src/science_tool science/tests docs/user-guide
```

Expected: no matches.

```bash
rg -n "message_contains|canonical_acceptance_severity|legacy_validation_fields|entry_matches" \
  science/src/science_tool
```

Expected: migration-only matches in
`science/src/science_tool/findings/acceptance_migration.py`; no steady-state health or
validate reader.

- [ ] **Step 6: Verify every consumer commit is internally consistent**

For `meta` and each external consumer:

- no old-shape entry contains `rule` or `message_contains`;
- every current entry has 64 lowercase hex `finding_id`, fingerprint version 1,
  canonical non-empty severity scope, and nonblank reason;
- no duplicate `finding_id`;
- no stored case existed before migration;
- before/after totals are identical;
- the config and the toolkit revision that reads it are in the same repository commit
  (or the same toolkit commit for editable in-repo `meta`).

Record the toolkit cutover SHA and all four consumer commit SHAs.

- [ ] **Step 7: Update design status and append the implementation record**

Change the design header from “Plan 3 outstanding” to “Plans 1–3 implemented.” Do not
rewrite revision history.

Append `## Implementation record` to this plan containing:

- Task 1–3 toolkit commit SHAs;
- Task 3 cutover SHA;
- `meta` migration count;
- three external consumer commit SHAs and remote/local status;
- exact before/after totals for all four consumers;
- post-rollout dry-run evidence that all four consumers report only
  `already-current`, and all-current `--apply` performs no write;
- scoped, real-project, model, full-tool, Ruff, formatting, and Pyright outputs;
- confirmation that the old matcher survives only in the explicit migration module;
- confirmation that ordinary health ERROR findings still exit 0 while legacy/invalid
  acceptance configuration exits 2.

Do not record a skipped or failing command as passing.

- [ ] **Step 8: Commit verification documentation**

```bash
git add \
  docs/plans/2026-07-27-finding-convergence-design.md \
  docs/plans/2026-07-29-finding-convergence-plan-3-acceptance-migration.md
git diff --cached --check
git commit -m "docs(findings): record acceptance migration"
```

## Execution Handoff

Implement this plan in the existing `finding-convergence-plan-3` worktree. Tasks 1–3
are toolkit work and should use one reviewer gate per task. Task 4 crosses repository
boundaries and starts only after the Task 3 cutover SHA is contained in the public
Science repository's default branch. Task 5 is top-level verification; do not delegate
its full-suite run.

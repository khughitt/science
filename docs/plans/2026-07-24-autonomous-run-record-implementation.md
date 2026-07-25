# Autonomous Run Record — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the autonomy envelope its "who acted" layer — a durable, supervisor-attested run record on disk, loaded as a project source, materialized exclusively into `graph/provenance`, and referable from any entity through one validated field.

**Architecture:** Two new modules and one new field. `science_model/autonomous_runs.py` holds the persisted shape (`AutonomousRunRecord`, its enums, and its validation) with no dependency on anything above it. `science_tool/graph/autonomous_runs.py` holds the disk loader and the rdflib emission. Wiring follows the freshest in-repo precedent for a reified non-entity record — `graph/skill_loads.py` + `ProjectSources.skill_loads` + `materialize._add_skill_load_edges` — because a run record has exactly that shape: collected at load, emitted into provenance, never an entity.

**Tech Stack:** Python 3.12+, pydantic v2, rdflib, PyYAML, pytest. Two independently managed packages: `science/` (`science/pyproject.toml`) and `science/model/` (`science/model/pyproject.toml`). There is no root `pyproject.toml`.

**Design source:** [`docs/plans/2026-07-24-autonomy-envelope-design.md`](2026-07-24-autonomy-envelope-design.md) §2 (run record), §3 (attribution / the entity field), and testing items 9, 10, and 11. This is Plan B of four; Plan A (`graph/belief_basis.py`) shipped.

---

## Scope boundary — read this before Task 1

This plan ships the **record and its bindings**. It ships **no writer and no gate**:

| In scope | Out of scope (later plan) |
|---|---|
| The persisted `AutonomousRunRecord` shape and its validation | `science run start` / `finalize` — the supervisor writes records (Plan D) |
| Loading `runs/*.md` into `ProjectSources` | Deciding a run's `disposition` (Plan D) |
| Materializing run records into `graph/provenance` | The default-deny path gate (Plan C) |
| The `autonomous_run` entity field, end to end | Comparing belief bases across a run (Plan D) |
| `refs-check` detection of a dangling `autonomous_run` | `science validate` wiring of the semantic gate (Plan D) |
| — | Commit attribution: the bot author and the `Science-Run:` trailer (design §3, first half) are things the *supervisor* does to commits, so they land with the supervisor (Plan D) |

Run records in this plan's tests are **hand-authored fixtures**. That is the correct input shape: this plan defines what a valid record *is*, so Plan D's writer has something to be checked against.

---

## Two corrections to the design, discovered while grounding

Both were found by reading the code the design refers to. Implement the plan as written here; Task 8 records the corrections back into the design doc.

**1. The field is `autonomous_run`, not `run_ref`.** The design §3 proposes a new entity field named `run_ref`. That name is already taken and is **belief-bearing**:

- `EvidenceLineEntity.run_refs` (`science/model/src/science_model/entities.py:1175`) is a validated list of `workflow-run:<slug>` references.
- It materializes to `SCI_NS.runRef` in **`graph/knowledge`**, not provenance (`graph/materialize.py:1218`).
- `graph/store/validation.py:220-224` reads it: `run_refs` *widens the run set* for evidence validation.

A provenance field spelled `run_ref` next to a belief-bearing field spelled `run_refs` is a trap: one dropped `s` moves a value across the belief boundary in silence. The predicate `sci:runRef` is likewise taken. This plan uses field `autonomous_run`, predicate `sci:autonomousRun`, node type `sci:AutonomousRun`.

**2. The model is `AutonomousRunRecord`, not `RunRecord`.** `science/src/science_tool/qa_audit/runs.py:10` already defines `RunRecord` for fingerprinted *workflow* runs. Same reasoning. The `run:` **id prefix** from the design is genuinely unused and is kept as designed.

Neither correction changes the design's substance — the record, its fields, its layer placement, and its authority model are all implemented exactly as §2 specifies.

---

## Global Constraints

Every task's requirements implicitly include this section.

- **Provenance only.** Run records and `sci:autonomousRun` edges are written to `graph/provenance` and nowhere else. No triple whose subject or object is a run node may appear in `graph/knowledge`. This is load-bearing: at weekly cadences run records would otherwise become one of the largest node populations in the graph and would skew attention rankings (`graph/attention.py`).
- **Records on disk are FINALIZED records.** Every attested field is required — there is no partial or in-flight record shape. `triggered_by` is the single exception, and only because the design marks it "Optional until S2; omitted, not blank, when absent". A supervisor that crashes mid-run leaves no record, and its branch therefore reads as *unattested* rather than *clean*. Do not add optionality to make an in-flight write easier; that is the fail-open this whole slice exists to prevent.
- **A run record is an attestation, so its parse must be strict.** `parse_frontmatter` uses `yaml.safe_load`, which collapses duplicate keys **last-wins before pydantic ever sees them** — so `extra="forbid"` provides no protection against a file declaring `tier:` twice. Run records get their own composing parser (Task 2). Never route a run record through the ordinary entity frontmatter path.
- **`autonomous_run` names the LAST run that wrote the file, not every run that ever touched it.** It is a scalar and it is overwritten. Full attribution history lives in git, in the run's `base_commit..head_commit` range — which is the authoritative binding anyway (design §0). Task 8 corrects the design's claim that run→entities is fully derivable by querying this field; with last-writer-wins it is derivable only for each entity's current state.
- **`autonomous_run` is entity-authored in this plan and therefore NOT yet an attested binding.** Materialization checks that the named run *exists*, not that this run wrote this file — so an actor can still attribute its work to an unrelated prior run. Closing that is Plan D's job and is recorded in Task 8: the supervisor must stamp the field itself, or verify every value it finds against the run's own `base_commit..head_commit`. Do not describe this field as attested anywhere in code comments or docs until that lands.
- **Fail early at load.** A malformed record, or an id that disagrees with its filename, raises. A run record is an attestation; an attestation that cannot be read is not one that can be skipped.
- **Commit shas are full 40-character lowercase hex.** An abbreviated sha is not a stable binding.
- **`extra="forbid"` and `frozen=True` on every persisted model.** An unrecognized key in a run record is an error, never a silently dropped field.
- **`belief_scalar` / `belief_scalar_enabled` must not be consulted anywhere in this plan.** They return `False` when unconfigured, so anything defined over them fails open.
- **`added_by` semantics are untouched.** It records how an idea *entered the project* (`entities.py:362`, `docs/user-guide/entities.md:722`), and the corpus contains values like `user` that no run record could explain. `autonomous_run` answers a different question — which execution wrote this file. Do not narrow, migrate, or deprecate `added_by`.
- Commands run from the package you changed: `cd science && uv run --frozen pytest`, `uv run ruff check`, `uv run pyright`; `cd science/model && uv run --frozen pytest`.
- Pyright is configured once by the repo-root `pyrightconfig.json`. Do not add a `[tool.pyright]` block to any `pyproject.toml`.
- Ruff here runs close to the default rule set — **`E501` is not enforced, so a clean `ruff check` says nothing about line length.** Keep lines under 100 characters by hand.
- Conventional commits. **No AI-attribution trailer or footer on any commit.**
- Composition over inheritance; explicit over defensive; fail early rather than silent fallback. No compatibility layers. No `Unified` prefix.

---

## File Structure

| File | Responsibility |
|---|---|
| `science/model/src/science_model/autonomous_runs.py` | **Create.** The persisted shape: `RUN_ID_PREFIX`, `RunTier`, `RunDisposition`, `PolicyIdentity`, `RunBudget`, `AutonomousRunRecord`, `RunRecordError`. Pure — pydantic, `re`, `datetime`, `enum` only. |
| `science/model/src/science_model/entities.py` | **Modify.** Add `autonomous_run` to `Entity` with a shape validator. |
| `science/model/src/science_model/frontmatter.py` | **Modify.** Map `autonomous_run` from frontmatter into entity kwargs. |
| `science/model/src/science_model/schemas/mixin-hypothesis-1.0.json` and `-2.0.json` | **Modify.** Declare `autonomous_run` in **both** — hypothesis is the one project mixin validated strictly, and generations 2 and 3 resolve it through different files. |
| `science/src/science_tool/graph/autonomous_runs.py` | **Create.** `RUNS_DIRNAME`, the strict frontmatter parser, `load_run_records`, `run_node_uri`, `add_run_record_to_graph`. |
| `science/src/science_tool/graph/store/constants.py` | **Modify.** Register the new `sci:run*` and `sci:autonomousRun` predicates in `PREDICATE_REGISTRY` under `graph/provenance`. |
| `science/src/science_tool/graph/sources.py` | **Modify.** `ProjectSources.run_records` + collection in `load_project_sources`. |
| `science/src/science_tool/graph/materialize.py` | **Modify.** `_add_run_record_edges` and `_add_autonomous_run_edges`, both provenance-only. |
| `science/src/science_tool/refs.py` | **Modify.** Report a dangling `autonomous_run` as a `RefIssue`. |
| `science/src/science_tool/project_package/serialize.py` | **Modify.** Add `runs` to `SOURCE_ROOTS`. |
| `science/model/tests/test_autonomous_run_record.py` | **Create.** Model shape and validation. |
| `science/model/tests/test_autonomous_run_field.py` | **Create.** `Entity.autonomous_run` shape validation and the frontmatter round trip. |
| `science/tests/test_autonomous_run_schema.py` | **Create.** The gen-3 strict-mixin gate for `autonomous_run`. |
| `science/tests/test_autonomous_runs.py` | **Create.** Loader (including the strict-YAML and filesystem boundaries) + node URI + graph emission. |
| `science/tests/test_autonomous_run_predicates.py` | **Create.** Every emitted predicate is registered, to the provenance layer. |
| `science/tests/test_autonomous_run_materialize.py` | **Create.** End-to-end through `load_project_sources` + `build_dataset_from_sources`, including layer isolation. |
| `science/tests/test_refs_autonomous_run.py` | **Create.** Dangling-reference detection. |
| `docs/user-guide/entities.md`, `docs/user-guide/project-layout.md` | **Modify.** Document the field and the `runs/` root. |

**Why the model splits across two packages:** `Entity`'s validator needs `RUN_ID_PREFIX`, and `science_model` cannot import `science_tool`. Putting the whole module in `science_model` would be a cycle — the loader needs `parse_frontmatter`, and `frontmatter.py` imports `entities.py`. So the *shape* (no imports from within `science_model`) lives in `science_model`, and the *loader plus rdflib emission* lives in `science_tool`. Keep `science_model/autonomous_runs.py` free of any `science_model` import; that is what makes it safe for `entities.py` to import.

---

### Task 1: The persisted run-record shape

**Files:**
- Create: `science/model/src/science_model/autonomous_runs.py`
- Test: `science/model/tests/test_autonomous_run_record.py`

**Interfaces:**
- Consumes: nothing from this repo.
- Produces: `RUN_ID_PREFIX: str` (`"run:"`), `RunTier`, `RunDisposition` (`StrEnum`), `PolicyIdentity`, `RunBudget`, `AutonomousRunRecord` (all pydantic `BaseModel`, `extra="forbid"`, `frozen=True`), `RunRecordError(ValueError)`, and the property `AutonomousRunRecord.slug -> str` (the id with `run:` stripped).

Field names and meanings come from design §2 verbatim; the only rename is the model's own name. A field literally named `model` is safe in pydantic v2 — the protected namespace is the prefix `model_`, and `"model".startswith("model_")` is `False`. Do not rename it.

The id check is **constructive, not a parse**. `run:2026-07-24-curation-sweep-a3f1` cannot be split into date/agent/short-id by pattern alone, because the agent slug contains hyphens. But the record carries `agent`, so validation rebuilds what the id must be and compares. That is why `agent: curation` with short id `sweep-a3f1` is rejected rather than silently accepted as a second reading of the same string.

Run this task from `science/model/`.

- [ ] **Step 1: Write the failing tests**

```python
# science/model/tests/test_autonomous_run_record.py
from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from science_model.autonomous_runs import (
    RUN_ID_PREFIX,
    AutonomousRunRecord,
    RunBudget,
    RunDisposition,
    RunTier,
)

_BASE = "a" * 40
_HEAD = "b" * 40
_TOOLKIT = "c" * 40
_DIGEST = "d" * 64


def _payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "id": "run:2026-07-24-curation-sweep-a3f1",
        "agent": "curation-sweep",
        "model": "claude-opus-5",
        "tier": "belief-neutral",
        "branch": "auto/2026-07-24-curation-sweep-a3f1",
        "base_commit": _BASE,
        "head_commit": _HEAD,
        "toolkit_revision": _TOOLKIT,
        "policy_identity": {"id": "core-default", "version": "1"},
        "basis_digest": _DIGEST,
        "started": datetime(2026, 7, 24, 9, 0, tzinfo=UTC),
        "ended": datetime(2026, 7, 24, 9, 30, tzinfo=UTC),
        "budget": {"tokens": 12000, "wall_clock_seconds": 1800.5},
        "disposition": "clean",
    }
    payload.update(overrides)
    return payload


def test_valid_record_round_trips() -> None:
    record = AutonomousRunRecord.model_validate(_payload())
    assert record.id == "run:2026-07-24-curation-sweep-a3f1"
    assert record.slug == "2026-07-24-curation-sweep-a3f1"
    assert record.tier is RunTier.BELIEF_NEUTRAL
    assert record.disposition is RunDisposition.CLEAN
    assert record.policy_identity.id == "core-default"
    assert record.budget == RunBudget(tokens=12000, wall_clock_seconds=1800.5)
    assert record.triggered_by is None


def test_record_is_frozen() -> None:
    record = AutonomousRunRecord.model_validate(_payload())
    with pytest.raises(ValidationError):
        record.disposition = RunDisposition.QUARANTINED  # type: ignore[misc]


def test_unknown_field_is_refused() -> None:
    with pytest.raises(ValidationError):
        AutonomousRunRecord.model_validate(_payload(entities_written=["hypothesis:h01"]))


def test_id_must_carry_the_run_prefix() -> None:
    with pytest.raises(ValidationError, match=RUN_ID_PREFIX):
        AutonomousRunRecord.model_validate(_payload(id="2026-07-24-curation-sweep-a3f1"))


def test_id_must_name_its_own_agent() -> None:
    # The id says `curation-sweep`; the record claims a different agent. Accepting this
    # would let one run present two identities to `git log` and to the graph.
    with pytest.raises(ValidationError, match="must name its agent"):
        AutonomousRunRecord.model_validate(_payload(agent="drift-sweep"))


def test_id_must_begin_with_a_real_calendar_date() -> None:
    with pytest.raises(ValidationError, match="YYYY-MM-DD"):
        AutonomousRunRecord.model_validate(
            _payload(
                id="run:2026-07-32-curation-sweep-a3f1",
                branch="auto/2026-07-32-curation-sweep-a3f1",
            )
        )


def test_short_id_may_not_absorb_a_hyphen() -> None:
    # `agent: curation` + short id `sweep-a3f1` is the second reading of the same string.
    # Constructive validation must refuse it rather than pick a reading.
    with pytest.raises(ValidationError, match="short suffix"):
        AutonomousRunRecord.model_validate(_payload(agent="curation"))


def test_branch_must_match_the_id() -> None:
    with pytest.raises(ValidationError, match="branch must be"):
        AutonomousRunRecord.model_validate(_payload(branch="auto/some-other-branch"))


@pytest.mark.parametrize("field_name", ["base_commit", "head_commit", "toolkit_revision"])
def test_abbreviated_sha_is_refused(field_name: str) -> None:
    with pytest.raises(ValidationError, match="40-character"):
        AutonomousRunRecord.model_validate(_payload(**{field_name: "a1b2c3d"}))


@pytest.mark.parametrize("field_name", ["base_commit", "head_commit", "toolkit_revision"])
def test_uppercase_sha_is_refused(field_name: str) -> None:
    with pytest.raises(ValidationError, match="40-character"):
        AutonomousRunRecord.model_validate(_payload(**{field_name: "A" * 40}))


def test_head_may_equal_base() -> None:
    # A report-only run legitimately commits nothing. Requiring movement would make
    # the honest no-op case unrepresentable.
    record = AutonomousRunRecord.model_validate(_payload(head_commit=_BASE))
    assert record.head_commit == record.base_commit


def test_basis_digest_must_be_a_sha256() -> None:
    with pytest.raises(ValidationError, match="64-character"):
        AutonomousRunRecord.model_validate(_payload(basis_digest="d" * 40))


def test_ended_may_not_precede_started() -> None:
    with pytest.raises(ValidationError, match="precedes"):
        AutonomousRunRecord.model_validate(
            _payload(ended=datetime(2026, 7, 24, 8, 0, tzinfo=UTC))
        )


@pytest.mark.parametrize("field_name", ["started", "ended"])
def test_naive_timestamps_are_refused(field_name: str) -> None:
    with pytest.raises(ValidationError, match="timezone"):
        AutonomousRunRecord.model_validate(
            _payload(**{field_name: datetime(2026, 7, 24, 9, 15)})
        )


def test_triggered_by_must_be_omitted_not_blank() -> None:
    with pytest.raises(ValidationError, match="omitted, not blank"):
        AutonomousRunRecord.model_validate(_payload(triggered_by="   "))


def test_triggered_by_is_kept_when_present() -> None:
    record = AutonomousRunRecord.model_validate(_payload(triggered_by="schedule:weekly-curation"))
    assert record.triggered_by == "schedule:weekly-curation"


def test_budget_is_required() -> None:
    # The design marks only `triggered_by` optional. A run that reports no cost is a run
    # whose cost nobody can audit, and S4's estimates are built from exactly this field.
    payload = _payload()
    del payload["budget"]
    with pytest.raises(ValidationError):
        AutonomousRunRecord.model_validate(payload)


def test_budget_requires_at_least_one_measure() -> None:
    with pytest.raises(ValidationError, match="tokens"):
        AutonomousRunRecord.model_validate(_payload(budget={}))


@pytest.mark.parametrize("measure", ["tokens", "wall_clock_seconds"])
def test_budget_refuses_negative_values(measure: str) -> None:
    with pytest.raises(ValidationError, match="negative"):
        AutonomousRunRecord.model_validate(_payload(budget={measure: -1}))


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_budget_refuses_non_finite_wall_clock(value: float) -> None:
    # `nan < 0` and `inf < 0` are both False, so a bare sign check lets these through.
    with pytest.raises(ValidationError, match="finite"):
        AutonomousRunRecord.model_validate(_payload(budget={"wall_clock_seconds": value}))


def test_budget_accepts_either_measure() -> None:
    record = AutonomousRunRecord.model_validate(_payload(budget={"tokens": 12000}))
    assert record.budget == RunBudget(tokens=12000)


@pytest.mark.parametrize("field_name", ["model", "agent"])
def test_blank_identity_strings_are_refused(field_name: str) -> None:
    with pytest.raises(ValidationError):
        AutonomousRunRecord.model_validate(_payload(**{field_name: "   "}))


@pytest.mark.parametrize("part", ["id", "version"])
def test_blank_policy_identity_parts_are_refused(part: str) -> None:
    identity = {"id": "core-default", "version": "1"} | {part: "  "}
    with pytest.raises(ValidationError, match="may not be blank"):
        AutonomousRunRecord.model_validate(_payload(policy_identity=identity))


def test_tier_vocabulary_is_closed() -> None:
    # There is deliberately no `full` tier: changing belief is human work by definition.
    with pytest.raises(ValidationError):
        AutonomousRunRecord.model_validate(_payload(tier="full"))
    assert {tier.value for tier in RunTier} == {"report-only", "belief-neutral"}


def test_disposition_vocabulary_is_closed() -> None:
    with pytest.raises(ValidationError):
        AutonomousRunRecord.model_validate(_payload(disposition="passed"))
    assert {d.value for d in RunDisposition} == {"clean", "quarantined", "unwired"}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd science/model && uv run --frozen pytest tests/test_autonomous_run_record.py -v`
Expected: collection error — `ModuleNotFoundError: No module named 'science_model.autonomous_runs'`.

- [ ] **Step 3: Write the implementation**

```python
# science/model/src/science_model/autonomous_runs.py
"""The persisted shape of one FINALIZED autonomous run (autonomy envelope §2).

A run record is a supervisor-written attestation: who acted, under which tier and
policy, over which exact commit range, and how it was dispositioned. It is
deliberately NOT an entity kind -- it is provenance about an execution, never a
belief bearer, freshness subject, attention candidate, or `rdf:type` hub member.

Named `AutonomousRunRecord`, not `RunRecord`: `science_tool/qa_audit/runs.py`
already owns that name for fingerprinted *workflow* runs, which model compute
reproducibility rather than agent authority.

This module imports nothing from `science_model`. `entities.py` imports
RUN_ID_PREFIX from here, and the loader that needs `parse_frontmatter` lives in
`science_tool.graph.autonomous_runs` -- keeping this module import-free is what
makes that safe.
"""

from __future__ import annotations

import math
import re
from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, model_validator

RUN_ID_PREFIX = "run:"

_AGENT_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_SHORT_ID_RE = re.compile(r"^[a-z0-9]{4,}$")
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")
_DATE_LENGTH = len("YYYY-MM-DD")


class RunRecordError(ValueError):
    """A run record file is unreadable, malformed, or misfiled."""


class RunTier(StrEnum):
    """The write surface a run was granted. Attested by the supervisor.

    There is deliberately no `full` tier. A tier reserved "for later" is a tier
    something will eventually be granted.
    """

    REPORT_ONLY = "report-only"
    BELIEF_NEUTRAL = "belief-neutral"


class RunDisposition(StrEnum):
    """The verdict rendered on a finished run. Attested, never self-declared.

    `unwired` is not a weaker `clean`: it means the basis was not computable, and
    a guard that cannot see must not report clean.
    """

    CLEAN = "clean"
    QUARANTINED = "quarantined"
    UNWIRED = "unwired"


class PolicyIdentity(BaseModel):
    """The frozen `(policy_id, policy_version)` pair in force for a run.

    One model rather than two flat fields because the pair IS the identity --
    `bundle_belief` already refuses to mix records across it.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    version: str

    @model_validator(mode="after")
    def _validate(self) -> "PolicyIdentity":
        for field_name in ("id", "version"):
            value: str = getattr(self, field_name)
            if not value.strip():
                raise ValueError(f"policy_identity {field_name} may not be blank")
        return self


class RunBudget(BaseModel):
    """What the run consumed. Slice S4 turns these into estimates."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    tokens: int | None = None
    wall_clock_seconds: float | None = None

    @model_validator(mode="after")
    def _validate(self) -> "RunBudget":
        if self.tokens is None and self.wall_clock_seconds is None:
            raise ValueError("budget must record tokens, wall_clock_seconds, or both")
        if self.tokens is not None and self.tokens < 0:
            raise ValueError(f"budget tokens may not be negative, got {self.tokens}")
        if self.wall_clock_seconds is not None:
            # Order matters: `nan < 0` and `inf < 0` are both False, so a sign check alone
            # admits both. Finiteness is checked first and separately.
            if not math.isfinite(self.wall_clock_seconds):
                raise ValueError(
                    f"budget wall_clock_seconds must be finite, got {self.wall_clock_seconds}"
                )
            if self.wall_clock_seconds < 0:
                raise ValueError(
                    f"budget wall_clock_seconds may not be negative, got {self.wall_clock_seconds}"
                )
        return self


class AutonomousRunRecord(BaseModel):
    """One finalized unattended run.

    Every attested field is required. There is no in-flight shape: a supervisor
    that dies mid-run leaves no record, so its branch reads as unattested rather
    than clean. That is the intended failure direction.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    agent: str
    model: str
    tier: RunTier
    branch: str
    base_commit: str
    head_commit: str
    toolkit_revision: str
    policy_identity: PolicyIdentity
    basis_digest: str
    started: datetime
    ended: datetime
    budget: RunBudget
    disposition: RunDisposition
    # The ONLY optional field, and only because the design marks it
    # "Optional until S2; omitted, not blank, when absent".
    triggered_by: str | None = None

    @property
    def slug(self) -> str:
        """The id without its `run:` prefix — the filename stem and branch suffix."""
        return self.id[len(RUN_ID_PREFIX) :]

    @model_validator(mode="after")
    def _validate(self) -> "AutonomousRunRecord":
        self._validate_identity()
        if not self.model.strip():
            raise ValueError("model may not be blank")
        for field_name in ("base_commit", "head_commit", "toolkit_revision"):
            value: str = getattr(self, field_name)
            if not _SHA_RE.fullmatch(value):
                raise ValueError(
                    f"{field_name} must be a full 40-character lowercase hex sha, got {value!r}"
                )
        if not _DIGEST_RE.fullmatch(self.basis_digest):
            raise ValueError(
                f"basis_digest must be a 64-character lowercase sha256, got {self.basis_digest!r}"
            )
        for field_name in ("started", "ended"):
            stamp: datetime = getattr(self, field_name)
            if stamp.tzinfo is None or stamp.utcoffset() is None:
                raise ValueError(f"{field_name} must carry a timezone offset")
        if self.ended < self.started:
            raise ValueError(
                f"ended {self.ended.isoformat()} precedes started {self.started.isoformat()}"
            )
        if self.triggered_by is not None and not self.triggered_by.strip():
            raise ValueError("triggered_by must be omitted, not blank")
        return self

    def _validate_identity(self) -> None:
        """Check id, agent, and branch against each other.

        Constructive, not a parse: the agent slug contains hyphens, so
        `<date>-<agent>-<short>` has more than one reading. The record names its
        own agent, so validation rebuilds the id it must have and compares.
        """
        if not self.id.startswith(RUN_ID_PREFIX):
            raise ValueError(f"run id must start with {RUN_ID_PREFIX!r}, got {self.id!r}")
        if not _AGENT_RE.fullmatch(self.agent):
            raise ValueError(f"agent must be a kebab-case slug, got {self.agent!r}")
        slug = self.slug
        if len(slug) <= _DATE_LENGTH or slug[_DATE_LENGTH] != "-":
            raise ValueError(f"run id must begin with a YYYY-MM-DD date, got {self.id!r}")
        day_text = slug[:_DATE_LENGTH]
        try:
            date.fromisoformat(day_text)
        except ValueError as exc:
            raise ValueError(
                f"run id must begin with a real YYYY-MM-DD date, got {day_text!r}"
            ) from exc
        remainder = slug[_DATE_LENGTH + 1 :]
        agent_prefix = f"{self.agent}-"
        if not remainder.startswith(agent_prefix):
            raise ValueError(f"run id {self.id!r} must name its agent {self.agent!r}")
        short_id = remainder[len(agent_prefix) :]
        if not _SHORT_ID_RE.fullmatch(short_id):
            raise ValueError(
                f"run id short suffix must be at least 4 lowercase alphanumerics, got {short_id!r}"
            )
        expected_branch = f"auto/{slug}"
        if self.branch != expected_branch:
            raise ValueError(f"branch must be {expected_branch!r}, got {self.branch!r}")
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd science/model && uv run --frozen pytest tests/test_autonomous_run_record.py -v`
Expected: all pass.

- [ ] **Step 5: Run the model suite and lint**

```bash
cd science/model && uv run --frozen pytest
cd science/model && uv run ruff check
cd science && uv run pyright
```

- [ ] **Step 6: Commit**

```bash
git add science/model/src/science_model/autonomous_runs.py science/model/tests/test_autonomous_run_record.py
git commit -m "feat(model): add the autonomous run record shape"
```

---

### Task 2: Load run records from `runs/`

**Files:**
- Create: `science/src/science_tool/graph/autonomous_runs.py`
- Test: `science/tests/test_autonomous_runs.py`

**Interfaces:**
- Consumes: `AutonomousRunRecord`, `RunRecordError` from `science_model.autonomous_runs`; `parse_frontmatter` from `science_model.frontmatter`.
- Produces: `RUNS_DIRNAME: str` (`"runs"`), `load_run_records(project_root: Path) -> list[AutonomousRunRecord]`.

**There is deliberately no duplicate-id check.** Every record's `slug` must equal its filename stem, and a directory cannot hold two files with the same stem — so within one `runs/` directory duplicate ids are impossible by construction. Adding a duplicate check would create a branch no test can reach, which is worse than no check: it reads as a guarantee while proving nothing.

The scan is flat, and a nested directory **raises** rather than being skipped. A supervisor that wrote `runs/2026/foo.md` would otherwise be silently unattested, which is exactly the fail-open direction this slice forbids.

Run this task from `science/`.

- [ ] **Step 1: Write the failing tests**

```python
# science/tests/test_autonomous_runs.py
from __future__ import annotations

from pathlib import Path

import pytest

from science_model.autonomous_runs import RunRecordError
from science_tool.graph.autonomous_runs import load_run_records

_RECORD = """---
id: run:2026-07-24-curation-sweep-a3f1
agent: curation-sweep
model: claude-opus-5
tier: belief-neutral
branch: auto/2026-07-24-curation-sweep-a3f1
base_commit: {base}
head_commit: {head}
toolkit_revision: {toolkit}
policy_identity:
  id: core-default
  version: "1"
basis_digest: {digest}
started: 2026-07-24T09:00:00+00:00
ended: 2026-07-24T09:30:00+00:00
budget:
  tokens: 12000
  wall_clock_seconds: 1800.5
disposition: clean
---

Swept stale status lines in conventions/.
"""


def _write_record(root: Path, stem: str = "2026-07-24-curation-sweep-a3f1") -> Path:
    """Write the canonical valid record. Tests that need a variant edit the text after."""
    runs = root / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    path = runs / f"{stem}.md"
    path.write_text(
        _RECORD.format(base="a" * 40, head="b" * 40, toolkit="c" * 40, digest="d" * 64),
        encoding="utf-8",
    )
    return path


def test_no_runs_directory_yields_no_records(tmp_path: Path) -> None:
    assert load_run_records(tmp_path) == []


def test_empty_runs_directory_yields_no_records(tmp_path: Path) -> None:
    (tmp_path / "runs").mkdir()
    assert load_run_records(tmp_path) == []


def test_one_record_loads(tmp_path: Path) -> None:
    _write_record(tmp_path)
    records = load_run_records(tmp_path)
    assert [record.id for record in records] == ["run:2026-07-24-curation-sweep-a3f1"]
    assert records[0].agent == "curation-sweep"


def test_records_load_in_filename_order(tmp_path: Path) -> None:
    _write_record(tmp_path)
    second = _write_record(tmp_path, stem="2026-07-25-curation-sweep-b7c2")
    second.write_text(
        second.read_text(encoding="utf-8")
        .replace("2026-07-24-curation-sweep-a3f1", "2026-07-25-curation-sweep-b7c2")
        .replace("2026-07-24T09", "2026-07-25T09"),
        encoding="utf-8",
    )
    assert [record.slug for record in load_run_records(tmp_path)] == [
        "2026-07-24-curation-sweep-a3f1",
        "2026-07-25-curation-sweep-b7c2",
    ]


def test_filename_must_agree_with_the_id(tmp_path: Path) -> None:
    _write_record(tmp_path, stem="2026-07-24-curation-sweep-zzzz")
    with pytest.raises(RunRecordError, match="disagrees with filename"):
        load_run_records(tmp_path)


def test_malformed_record_raises(tmp_path: Path) -> None:
    path = _write_record(tmp_path)
    path.write_text(
        path.read_text(encoding="utf-8").replace("disposition: clean", "disposition: passed"),
        encoding="utf-8",
    )
    with pytest.raises(RunRecordError, match="invalid run record"):
        load_run_records(tmp_path)


def test_record_without_frontmatter_raises(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    runs.mkdir()
    (runs / "2026-07-24-curation-sweep-a3f1.md").write_text("just prose\n", encoding="utf-8")
    with pytest.raises(RunRecordError, match="no frontmatter"):
        load_run_records(tmp_path)


def test_nested_directory_raises_rather_than_being_skipped(tmp_path: Path) -> None:
    # A record filed one level down would otherwise be silently unattested.
    _write_record(tmp_path)
    (tmp_path / "runs" / "2026").mkdir()
    with pytest.raises(RunRecordError, match="flat"):
        load_run_records(tmp_path)


def test_runs_as_a_regular_file_raises(tmp_path: Path) -> None:
    # `is_dir()` is False here, so a plain "no runs directory -> []" would report a
    # project with a broken runs path as a project that never ran unattended.
    (tmp_path / "runs").write_text("not a directory\n", encoding="utf-8")
    with pytest.raises(RunRecordError, match="not a directory"):
        load_run_records(tmp_path)


def test_symlinked_runs_directory_raises(tmp_path: Path) -> None:
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (tmp_path / "runs").symlink_to(elsewhere, target_is_directory=True)
    with pytest.raises(RunRecordError, match="symlink"):
        load_run_records(tmp_path)


def test_symlinked_record_raises(tmp_path: Path) -> None:
    # An out-of-tree file must not be able to become an accepted attestation.
    outside = tmp_path / "outside.md"
    outside.write_text(
        _RECORD.format(base="a" * 40, head="b" * 40, toolkit="c" * 40, digest="d" * 64),
        encoding="utf-8",
    )
    runs = tmp_path / "runs"
    runs.mkdir()
    (runs / "2026-07-24-curation-sweep-a3f1.md").symlink_to(outside)
    with pytest.raises(RunRecordError, match="symlink"):
        load_run_records(tmp_path)


def test_non_markdown_child_raises(tmp_path: Path) -> None:
    # Including README.md's absence of a run shape: runs/ holds run records only.
    _write_record(tmp_path)
    (tmp_path / "runs" / "notes.txt").write_text("scratch\n", encoding="utf-8")
    with pytest.raises(RunRecordError, match="flat"):
        load_run_records(tmp_path)


def test_duplicate_top_level_key_raises(tmp_path: Path) -> None:
    # yaml.safe_load collapses this to the LAST value, so `extra="forbid"` never sees it.
    # A record that declares two tiers must not be read as declaring one.
    path = _write_record(tmp_path)
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "tier: belief-neutral", "tier: report-only\ntier: belief-neutral"
        ),
        encoding="utf-8",
    )
    with pytest.raises(RunRecordError, match="duplicate key"):
        load_run_records(tmp_path)


def test_duplicate_nested_key_raises(tmp_path: Path) -> None:
    path = _write_record(tmp_path)
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "  version: \"1\"", "  version: \"1\"\n  version: \"2\""
        ),
        encoding="utf-8",
    )
    with pytest.raises(RunRecordError, match="duplicate key"):
        load_run_records(tmp_path)


def test_yaml_merge_key_raises(tmp_path: Path) -> None:
    path = _write_record(tmp_path)
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "disposition: clean", "disposition: clean\n<<: {tier: report-only}"
        ),
        encoding="utf-8",
    )
    with pytest.raises(RunRecordError, match="merge key"):
        load_run_records(tmp_path)


def test_undecodable_record_raises(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    runs.mkdir()
    (runs / "2026-07-24-curation-sweep-a3f1.md").write_bytes(b"---\n\xff\xfe\n---\n")
    with pytest.raises(RunRecordError):
        load_run_records(tmp_path)


def test_unparseable_yaml_raises(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    runs.mkdir()
    (runs / "2026-07-24-curation-sweep-a3f1.md").write_text(
        "---\nid: [unclosed\n---\n\nBody.\n", encoding="utf-8"
    )
    with pytest.raises(RunRecordError):
        load_run_records(tmp_path)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd science && uv run --frozen pytest tests/test_autonomous_runs.py -v`
Expected: collection error — `ModuleNotFoundError: No module named 'science_tool.graph.autonomous_runs'`.

- [ ] **Step 3: Write the implementation**

```python
# science/src/science_tool/graph/autonomous_runs.py
"""Load autonomous run records from `runs/` and emit them into graph/provenance.

The disk and rdflib half of the run record; the persisted shape itself lives in
`science_model.autonomous_runs`. Mirrors `graph/skill_loads.py`: a reified
non-entity record collected at load and emitted into the provenance layer.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError
from science_model.autonomous_runs import AutonomousRunRecord, RunRecordError
import yaml

RUNS_DIRNAME = "runs"


def _reject_duplicate_and_merge_keys(node: yaml.Node, path: Path) -> None:
    """Refuse duplicate keys and YAML merge keys anywhere in the document.

    Recursive, unlike `skill_loads._reject_duplicate_keys`: a run record nests
    `policy_identity` and `budget`, and a duplicate inside either is exactly as
    silent as one at the top level.

    Operates on the NODE tree from `yaml.compose`, which builds no Python objects
    (so no `!!python/object` exposure) while still seeing what `safe_load` would
    collapse to last-wins.
    """
    if isinstance(node, yaml.MappingNode):
        seen: set[object] = set()
        for key_node, value_node in node.value:
            if key_node.tag == "tag:yaml.org,2002:merge":
                raise RunRecordError(f"{path}: YAML merge keys are not allowed in a run record")
            key = getattr(key_node, "value", None)
            if key in seen:
                raise RunRecordError(f"{path}: duplicate key {key!r} in run record")
            seen.add(key)
            _reject_duplicate_and_merge_keys(value_node, path)
    elif isinstance(node, yaml.SequenceNode):
        for item in node.value:
            _reject_duplicate_and_merge_keys(item, path)


def _parse_run_record_frontmatter(path: Path) -> dict[str, object]:
    """Parse one run record's frontmatter under attestation-grade rules.

    Deliberately NOT `science_model.frontmatter.parse_frontmatter`: that reaches
    `yaml.safe_load`, which silently collapses a duplicate `tier:` to last-wins
    BEFORE pydantic runs, so `extra="forbid"` never sees the conflict. An
    attestation that says two things must not be read as saying one.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise RunRecordError(f"{path}: run record is unreadable: {exc}") from exc
    if not text.startswith("---"):
        raise RunRecordError(f"{path}: run record has no frontmatter")
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise RunRecordError(f"{path}: run record frontmatter is unterminated")
    block = parts[1]
    try:
        node = yaml.compose(block, Loader=yaml.SafeLoader)
        if node is not None:
            _reject_duplicate_and_merge_keys(node, path)
        # Parse the SAME text again rather than constructing from the node tree: the two
        # passes must agree, and safe_load is the parser whose result pydantic validates.
        data = yaml.safe_load(block)
    except yaml.YAMLError as exc:
        raise RunRecordError(f"{path}: run record frontmatter is not valid YAML: {exc}") from exc
    if not isinstance(data, dict) or not data:
        raise RunRecordError(f"{path}: run record has no frontmatter")
    return data


def load_run_records(project_root: Path) -> list[AutonomousRunRecord]:
    """Every finalized run record under `<project_root>/runs/`, in filename order.

    A genuinely absent directory yields no records -- most projects never run
    unattended. Everything else fails loudly, and the distinctions matter:

    * `runs` present but not a directory is a broken project, not an empty one.
    * A symlink -- on the directory or on any record -- is refused, so an
      out-of-tree file can never become an accepted attestation.
    * Any child that is not a flat regular `*.md` file raises, so a record filed
      one level down is never silently unscanned.

    No duplicate-id check: `slug == path.stem` plus filesystem uniqueness already
    makes duplicates impossible within one directory, so such a check would be a
    branch no test can reach.
    """
    runs_dir = project_root / RUNS_DIRNAME
    # Symlink first: a symlink to a missing target reports `exists() is False`, so an
    # existence check would return "no records" for a redirected runs directory.
    if runs_dir.is_symlink():
        raise RunRecordError(f"{runs_dir}: runs must not be a symlink")
    if not runs_dir.exists():
        return []
    if not runs_dir.is_dir():
        raise RunRecordError(f"{runs_dir}: runs exists but is not a directory")
    records: list[AutonomousRunRecord] = []
    for child in sorted(runs_dir.iterdir()):
        if child.is_symlink():
            raise RunRecordError(f"{child}: run records must not be symlinks")
        if not child.is_file() or child.suffix != ".md":
            raise RunRecordError(f"{child}: runs/ holds only flat *.md run records")
        frontmatter = _parse_run_record_frontmatter(child)
        try:
            record = AutonomousRunRecord.model_validate(frontmatter)
        except ValidationError as exc:
            raise RunRecordError(f"{child}: invalid run record: {exc}") from exc
        if record.slug != child.stem:
            raise RunRecordError(
                f"{child}: run id {record.id!r} disagrees with filename stem {child.stem!r}"
            )
        records.append(record)
    return records
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_autonomous_runs.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/graph/autonomous_runs.py science/tests/test_autonomous_runs.py
git commit -m "feat(graph): load autonomous run records from runs/"
```

---

### Task 3: Node URI and provenance emission

**Files:**
- Modify: `science/src/science_tool/graph/autonomous_runs.py`
- Test: `science/tests/test_autonomous_runs.py`

**Interfaces:**
- Consumes: `PROJECT_NS`, `SCI_NS` from `science_tool.graph.store`; `PROV`, `RDF`, `XSD` from `rdflib.namespace`.
- Produces: `run_node_uri(run_id: str) -> URIRef`, `add_run_record_to_graph(record: AutonomousRunRecord, graph: Graph) -> None`.

`run_node_uri` takes the **id string**, not the record, so the entity-edge pass in Task 6 and the record pass in Task 4 cannot drift into two spellings of the same URI.

The node is dual-typed `sci:AutonomousRun` + `prov:Activity`. The entity→run edge in Task 6 uses a Science-owned predicate rather than `prov:wasGeneratedBy`: a run that *edits* an entity did not generate it, and asserting generation would license a false PROV inference.

- [ ] **Step 1: Write the failing tests**

Append to `science/tests/test_autonomous_runs.py`:

```python
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import PROV, RDF, XSD

from science_tool.graph.autonomous_runs import add_run_record_to_graph, run_node_uri
from science_tool.graph.store import PROJECT_NS, SCI_NS


def _record(tmp_path: Path):
    _write_record(tmp_path)
    return load_run_records(tmp_path)[0]


def test_node_uri_is_derived_from_the_slug(tmp_path: Path) -> None:
    record = _record(tmp_path)
    assert run_node_uri(record.id) == URIRef(PROJECT_NS["run/2026-07-24-curation-sweep-a3f1"])


def test_node_uri_accepts_the_id_string_directly(tmp_path: Path) -> None:
    record = _record(tmp_path)
    assert run_node_uri("run:2026-07-24-curation-sweep-a3f1") == run_node_uri(record.id)


def test_emission_writes_the_attested_fields(tmp_path: Path) -> None:
    record = _record(tmp_path)
    graph = Graph()
    add_run_record_to_graph(record, graph)
    node = run_node_uri(record.id)
    assert (node, RDF.type, SCI_NS.AutonomousRun) in graph
    assert (node, RDF.type, PROV.Activity) in graph
    assert (node, SCI_NS.runId, Literal(record.id)) in graph
    assert (node, SCI_NS.runAgent, Literal("curation-sweep")) in graph
    assert (node, SCI_NS.runModel, Literal("claude-opus-5")) in graph
    assert (node, SCI_NS.runTier, Literal("belief-neutral")) in graph
    assert (node, SCI_NS.runBranch, Literal("auto/2026-07-24-curation-sweep-a3f1")) in graph
    assert (node, SCI_NS.runBaseCommit, Literal("a" * 40)) in graph
    assert (node, SCI_NS.runHeadCommit, Literal("b" * 40)) in graph
    assert (node, SCI_NS.runToolkitRevision, Literal("c" * 40)) in graph
    assert (node, SCI_NS.runPolicyId, Literal("core-default")) in graph
    assert (node, SCI_NS.runPolicyVersion, Literal("1")) in graph
    assert (node, SCI_NS.runBasisDigest, Literal("d" * 64)) in graph
    assert (node, SCI_NS.runDisposition, Literal("clean")) in graph
    assert (node, SCI_NS.runBudgetTokens, Literal(12000)) in graph
    assert (node, SCI_NS.runBudgetWallClockSeconds, Literal(1800.5)) in graph
    assert (
        node,
        PROV.startedAtTime,
        Literal("2026-07-24T09:00:00+00:00", datatype=XSD.dateTime),
    ) in graph
    assert (
        node,
        PROV.endedAtTime,
        Literal("2026-07-24T09:30:00+00:00", datatype=XSD.dateTime),
    ) in graph


def test_absent_triggered_by_emits_no_triple(tmp_path: Path) -> None:
    record = _record(tmp_path)
    graph = Graph()
    add_run_record_to_graph(record, graph)
    assert (run_node_uri(record.id), SCI_NS.runTriggeredBy, None) not in graph


def test_triggered_by_emits_when_present(tmp_path: Path) -> None:
    path = _write_record(tmp_path)
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "disposition: clean",
            "disposition: clean\ntriggered_by: schedule:weekly-curation",
        ),
        encoding="utf-8",
    )
    record = load_run_records(tmp_path)[0]
    graph = Graph()
    add_run_record_to_graph(record, graph)
    node = run_node_uri(record.id)
    assert (node, SCI_NS.runTriggeredBy, Literal("schedule:weekly-curation")) in graph


def test_budget_with_one_measure_emits_only_that_measure(tmp_path: Path) -> None:
    path = _write_record(tmp_path)
    path.write_text(
        path.read_text(encoding="utf-8").replace("  wall_clock_seconds: 1800.5\n", ""),
        encoding="utf-8",
    )
    record = load_run_records(tmp_path)[0]
    graph = Graph()
    add_run_record_to_graph(record, graph)
    node = run_node_uri(record.id)
    assert (node, SCI_NS.runBudgetTokens, Literal(12000)) in graph
    assert (node, SCI_NS.runBudgetWallClockSeconds, None) not in graph


def test_emission_is_idempotent(tmp_path: Path) -> None:
    record = _record(tmp_path)
    once, twice = Graph(), Graph()
    add_run_record_to_graph(record, once)
    add_run_record_to_graph(record, twice)
    add_run_record_to_graph(record, twice)
    assert set(once) == set(twice)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd science && uv run --frozen pytest tests/test_autonomous_runs.py -v`
Expected: `ImportError: cannot import name 'run_node_uri'`.

- [ ] **Step 3: Write the implementation**

Add to `science/src/science_tool/graph/autonomous_runs.py` (extend the imports at the top with the rdflib names and `RUN_ID_PREFIX`):

```python
from rdflib import Graph, URIRef
from rdflib import Literal as RDFLiteral
from rdflib.namespace import PROV, RDF, XSD
from science_model.autonomous_runs import RUN_ID_PREFIX

from science_tool.graph.store import PROJECT_NS, SCI_NS


def run_node_uri(run_id: str) -> URIRef:
    """The provenance node for a run id.

    Takes the id string, not the record, so the record pass and the entity-edge
    pass cannot drift into two spellings of one URI. The slug is already
    constrained to lowercase alphanumerics, hyphens, and the leading date, so no
    escaping is needed.
    """
    if not run_id.startswith(RUN_ID_PREFIX):
        raise RunRecordError(f"run id must start with {RUN_ID_PREFIX!r}, got {run_id!r}")
    return URIRef(PROJECT_NS[f"run/{run_id[len(RUN_ID_PREFIX):]}"])


def add_run_record_to_graph(record: AutonomousRunRecord, graph: Graph) -> None:
    """Write one run record's triples. Caller supplies the PROVENANCE graph.

    Dual-typed `sci:AutonomousRun` + `prov:Activity`: the PROV type makes the run
    legible to any PROV reader, and the Science type is what our own queries key on.
    """
    node = run_node_uri(record.id)
    graph.add((node, RDF.type, SCI_NS.AutonomousRun))
    graph.add((node, RDF.type, PROV.Activity))
    graph.add((node, SCI_NS.runId, RDFLiteral(record.id)))
    graph.add((node, SCI_NS.runAgent, RDFLiteral(record.agent)))
    graph.add((node, SCI_NS.runModel, RDFLiteral(record.model)))
    graph.add((node, SCI_NS.runTier, RDFLiteral(record.tier.value)))
    graph.add((node, SCI_NS.runBranch, RDFLiteral(record.branch)))
    graph.add((node, SCI_NS.runBaseCommit, RDFLiteral(record.base_commit)))
    graph.add((node, SCI_NS.runHeadCommit, RDFLiteral(record.head_commit)))
    graph.add((node, SCI_NS.runToolkitRevision, RDFLiteral(record.toolkit_revision)))
    graph.add((node, SCI_NS.runPolicyId, RDFLiteral(record.policy_identity.id)))
    graph.add((node, SCI_NS.runPolicyVersion, RDFLiteral(record.policy_identity.version)))
    graph.add((node, SCI_NS.runBasisDigest, RDFLiteral(record.basis_digest)))
    graph.add(
        (node, PROV.startedAtTime, RDFLiteral(record.started.isoformat(), datatype=XSD.dateTime))
    )
    graph.add(
        (node, PROV.endedAtTime, RDFLiteral(record.ended.isoformat(), datatype=XSD.dateTime))
    )
    graph.add((node, SCI_NS.runDisposition, RDFLiteral(record.disposition.value)))
    if record.triggered_by is not None:
        graph.add((node, SCI_NS.runTriggeredBy, RDFLiteral(record.triggered_by)))
    if record.budget.tokens is not None:
        graph.add((node, SCI_NS.runBudgetTokens, RDFLiteral(record.budget.tokens)))
    if record.budget.wall_clock_seconds is not None:
        graph.add(
            (node, SCI_NS.runBudgetWallClockSeconds, RDFLiteral(record.budget.wall_clock_seconds))
        )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_autonomous_runs.py -v`
Expected: all pass.

- [ ] **Step 5: Write the failing registry test**

This task mints sixteen new `sci:` predicates. `PREDICATE_REGISTRY`
(`science/src/science_tool/graph/store/constants.py:177`) is the public answer to
"what predicates does this graph use", read by `science graph predicates` — and the
skill-load precedent this plan follows *does* register its predicates
(`sci:hasSkillLoad`, `sci:loadReason`, `sci:usageSource`). An unregistered vocabulary
leaves that command quietly incomplete.

The test derives the expected set from the emitter rather than from a second hand-written
list, so a predicate added to `add_run_record_to_graph` later cannot slip past it.

```python
# science/tests/test_autonomous_run_predicates.py
from __future__ import annotations

from pathlib import Path

from rdflib import Graph

from science_tool.graph.autonomous_runs import add_run_record_to_graph, load_run_records
from science_tool.graph.store import SCI_NS
from science_tool.graph.store.constants import PREDICATE_REGISTRY
# Bare module name, not `tests.…`: pytest puts `science/tests/` on sys.path directly.
# `test_graph_origins.py:19` imports across test modules the same way.
from test_autonomous_runs import _write_record


def _emitted_sci_predicates(tmp_path: Path) -> set[str]:
    _write_record(tmp_path)
    graph = Graph()
    add_run_record_to_graph(load_run_records(tmp_path)[0], graph)
    return {
        f"sci:{str(p).removeprefix(str(SCI_NS))}"
        for _s, p, _o in graph
        if str(p).startswith(str(SCI_NS))
    }


def test_every_emitted_run_predicate_is_registered(tmp_path: Path) -> None:
    registered = {row["predicate"] for row in PREDICATE_REGISTRY}
    missing = sorted(_emitted_sci_predicates(tmp_path) - registered)
    assert missing == [], f"unregistered run predicates: {missing}"


def test_run_predicates_are_registered_to_the_provenance_layer(tmp_path: Path) -> None:
    emitted = _emitted_sci_predicates(tmp_path)
    layers = {
        row["predicate"]: row["layer"] for row in PREDICATE_REGISTRY if row["predicate"] in emitted
    }
    assert layers, "no run predicates found in the registry"
    assert set(layers.values()) == {"graph/provenance"}
```

> If importing `_write_record` across test modules is awkward in this suite, copy the
> record fixture into this file instead — do **not** weaken the test by hand-listing the
> predicate names.

Run it and confirm it fails listing all sixteen predicates as unregistered.

- [ ] **Step 6: Register the predicates**

Add one `PREDICATE_REGISTRY` entry per emitted predicate, all with
`"layer": "graph/provenance"`: `sci:runId`, `sci:runAgent`, `sci:runModel`, `sci:runTier`,
`sci:runBranch`, `sci:runBaseCommit`, `sci:runHeadCommit`, `sci:runToolkitRevision`,
`sci:runPolicyId`, `sci:runPolicyVersion`, `sci:runBasisDigest`, `sci:runDisposition`,
`sci:runTriggeredBy`, `sci:runBudgetTokens`, `sci:runBudgetWallClockSeconds`. Follow the
existing row shape, e.g.:

```python
    {
        "predicate": "sci:runTier",
        "description": "Autonomous run write tier (report-only | belief-neutral)",
        "layer": "graph/provenance",
    },
```

`sci:autonomousRun` is minted in Task 6, not here; register it there.

Re-run: both registry tests pass.

- [ ] **Step 7: Commit**

```bash
git add science/src/science_tool/graph/autonomous_runs.py science/src/science_tool/graph/store/constants.py science/tests/test_autonomous_runs.py science/tests/test_autonomous_run_predicates.py
git commit -m "feat(graph): emit autonomous run records into provenance"
```

---

### Task 4: Wire run records through load and materialization

**Files:**
- Modify: `science/src/science_tool/graph/sources.py`
- Modify: `science/src/science_tool/graph/materialize.py`
- Create: `science/tests/test_autonomous_run_materialize.py`

**Interfaces:**
- Consumes: `load_run_records`, `add_run_record_to_graph`, `run_node_uri` from Tasks 2-3.
- Produces: `ProjectSources.run_records: list[AutonomousRunRecord]`; `materialize._add_run_record_edges(sources, *, provenance)`.

Follow `skill_loads` exactly — it is the same shape one step earlier in the codebase's history. Unlike skill loads, run records are **not** gated on the entity-schema generation: `runs/` is a new directory with no legacy spelling, so there is nothing to be backward-compatible with.

The layer-isolation test is design testing item 9 and is the point of the whole task: assert that **no** triple in `graph/knowledge` mentions the run node, in either subject or object position. Asserting only "not an attention candidate" would pass for a run node that reached knowledge but happened to lack `sci:freshnessState`.

- [ ] **Step 1: Write the failing tests**

```python
# science/tests/test_autonomous_run_materialize.py
from __future__ import annotations

from pathlib import Path

from rdflib.namespace import RDF

from science_tool.graph.autonomous_runs import run_node_uri
from science_tool.graph.dataset_usage import project_entity_uri
from science_tool.graph.materialize import build_dataset_from_sources
from science_tool.graph.sources import load_project_sources
from science_tool.graph.store import PROJECT_NS, SCI_NS

RUN_ID = "run:2026-07-24-curation-sweep-a3f1"

_RECORD = f"""---
id: {RUN_ID}
agent: curation-sweep
model: claude-opus-5
tier: belief-neutral
branch: auto/2026-07-24-curation-sweep-a3f1
base_commit: {"a" * 40}
head_commit: {"b" * 40}
toolkit_revision: {"c" * 40}
policy_identity:
  id: core-default
  version: "1"
basis_digest: {"d" * 64}
started: 2026-07-24T09:00:00+00:00
ended: 2026-07-24T09:30:00+00:00
budget:
  tokens: 12000
  wall_clock_seconds: 1800.5
disposition: clean
---

Swept stale status lines.
"""


def write_project(root: Path, *, with_run: bool = True, entity_extra: str = "") -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "science.yaml").write_text(
        "name: demo\nknowledge_profiles:\n  local: local\n", encoding="utf-8"
    )
    topics = root / "entities" / "topics"
    topics.mkdir(parents=True, exist_ok=True)
    (topics / "demo.md").write_text(
        "---\n"
        "id: topic:demo\n"
        "kind: topic\n"
        "title: Demo topic\n"
        "status: active\n"
        f"{entity_extra}"
        "---\n\nBody.\n",
        encoding="utf-8",
    )
    if with_run:
        runs = root / "runs"
        runs.mkdir(parents=True, exist_ok=True)
        (runs / "2026-07-24-curation-sweep-a3f1.md").write_text(_RECORD, encoding="utf-8")


def graphs(root: Path):
    sources = load_project_sources(root)
    dataset = build_dataset_from_sources(sources)
    return (
        sources,
        dataset.graph(PROJECT_NS["graph/knowledge"]),
        dataset.graph(PROJECT_NS["graph/provenance"]),
    )


def test_run_records_reach_project_sources(tmp_path: Path) -> None:
    write_project(tmp_path)
    sources = load_project_sources(tmp_path)
    assert [record.id for record in sources.run_records] == [RUN_ID]


def test_project_without_runs_dir_loads_clean(tmp_path: Path) -> None:
    write_project(tmp_path, with_run=False)
    sources = load_project_sources(tmp_path)
    assert sources.run_records == []


def test_run_record_materializes_into_provenance(tmp_path: Path) -> None:
    write_project(tmp_path)
    _, _knowledge, provenance = graphs(tmp_path)
    node = run_node_uri(RUN_ID)
    assert (node, RDF.type, SCI_NS.AutonomousRun) in provenance
    assert (node, SCI_NS.runDisposition, None) in provenance


def test_no_run_triple_reaches_knowledge(tmp_path: Path) -> None:
    # Design testing item 9. Checked over the WHOLE knowledge graph in both subject and
    # object position: a run node that leaked into knowledge without a freshness state
    # would still pass a narrower "not an attention candidate" assertion.
    write_project(tmp_path)
    _, knowledge, _provenance = graphs(tmp_path)
    node = run_node_uri(RUN_ID)
    assert (node, None, None) not in knowledge
    assert (None, None, node) not in knowledge
    assert (None, RDF.type, SCI_NS.AutonomousRun) not in knowledge


def test_run_materialization_is_idempotent(tmp_path: Path) -> None:
    write_project(tmp_path)
    sources = load_project_sources(tmp_path)
    first = build_dataset_from_sources(sources).graph(PROJECT_NS["graph/provenance"])
    second = build_dataset_from_sources(sources).graph(PROJECT_NS["graph/provenance"])
    assert set(first) == set(second)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd science && uv run --frozen pytest tests/test_autonomous_run_materialize.py -v`
Expected: `AttributeError: 'ProjectSources' object has no attribute 'run_records'`.

- [ ] **Step 3: Add the field and collect it at load**

In `science/src/science_tool/graph/sources.py`, add the import beside the existing `skill_loads` import:

```python
from science_model.autonomous_runs import AutonomousRunRecord

from science_tool.graph.autonomous_runs import load_run_records
```

Add the field to `ProjectSources`, directly after `skill_loads`:

```python
    # Finalized autonomous run records loaded from `runs/` (see graph/autonomous_runs.py).
    # Empty for every project that has never run unattended. Emitted into graph/provenance
    # by materialize._add_run_record_edges, and NEVER into graph/knowledge.
    run_records: list[AutonomousRunRecord] = Field(default_factory=list)
```

In `load_project_sources`, beside the existing `skill_loads = collect_skill_loads(...)` call:

```python
    run_records = load_run_records(project_root)
```

and pass it in the `ProjectSources(...)` construction, after `skill_loads=skill_loads,`:

```python
        run_records=run_records,
```

- [ ] **Step 4: Materialize the records**

In `science/src/science_tool/graph/materialize.py`, add the import:

```python
from science_tool.graph.autonomous_runs import add_run_record_to_graph, run_node_uri
```

Add the pass beside `_add_skill_load_edges`:

```python
def _add_run_record_edges(sources: ProjectSources, *, provenance) -> None:
    for record in sources.run_records:
        add_run_record_to_graph(record, provenance)
```

and call it immediately after `_add_skill_load_edges(sources, provenance=provenance)`:

```python
    _add_run_record_edges(sources, provenance=provenance)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_autonomous_run_materialize.py -v`
Expected: all pass.

- [ ] **Step 6: Run the full suite**

```bash
cd science && uv run --frozen pytest > /tmp/pytest-task4.log 2>&1; echo "EXIT=$?"; tail -3 /tmp/pytest-task4.log
```

Expected: `EXIT=0`. (Redirect and check `$?` — a piped `pytest | tail` reports `tail`'s status, not pytest's.)

- [ ] **Step 7: Commit**

```bash
git add science/src/science_tool/graph/sources.py science/src/science_tool/graph/materialize.py science/tests/test_autonomous_run_materialize.py
git commit -m "feat(graph): materialize run records into the provenance layer"
```

---

### Task 5: The `autonomous_run` entity field

**Files:**
- Modify: `science/model/src/science_model/entities.py`
- Modify: `science/model/src/science_model/frontmatter.py:524` (the `entity_kwargs` dict)
- Modify: `science/model/src/science_model/schemas/mixin-hypothesis-1.0.json` **and** `mixin-hypothesis-2.0.json`
- Test: `science/model/tests/test_autonomous_run_field.py` (create) — run from `science/model/`
- Test: `science/tests/test_autonomous_run_schema.py` (create) — run from `science/`

**Interfaces:**
- Consumes: `RUN_ID_PREFIX` from `science_model.autonomous_runs`.
- Produces: `Entity.autonomous_run: str | None`.

A field only reaches the graph if it is wired at every layer. Miss the `frontmatter.py` mapping and the value is silently dropped at `model_validate` time; miss the schema and a gen-3 pinned project rejects the file. Both are required here.

The validator checks **shape only** — `run:` prefix, non-empty remainder. Whether a run record with that id exists is a *resolution* question answered in Tasks 6 and 7, exactly as `OriginRecord` validates a `paper:` prefix at the model layer and leaves resolution to the graph.

`hypothesis` is the only project mixin validated strictly (`PROJECT_MIXIN_NAMES = frozenset({"hypothesis"})`, `entity_schema/profile.py:24`); other kinds carry the key as a preserved extra with no schema gate.

**Both hypothesis mixins need the property.** `ARMED_SCHEMA_GENERATIONS = frozenset({2, 3})` and `_MIXIN_VERSION_BY_GENERATION` (`entity_schema/profile.py:92-95`) maps hypothesis to `1.0` at generation 2 and `2.0` at generation 3. I verified both generations currently reject `autonomous_run` with `Unevaluated properties are not allowed`, so touching only `2.0` would leave every pinned gen-2 project unable to carry the field. The schema test below is parameterized over both.

Run this task from `science/model/`.

- [ ] **Step 1: Write the failing tests**

```python
# science/model/tests/test_autonomous_run_field.py
from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from science_model.entities import Entity
from science_model.frontmatter import parse_entity_file

RUN_ID = "run:2026-07-24-curation-sweep-a3f1"


def _entity(**overrides: object) -> Entity:
    # Entity's required fields, verified against `Entity.model_fields`:
    # id, kind, title, project, ontology_terms, related, source_refs,
    # content_preview, file_path.
    payload: dict[str, object] = {
        "id": "topic:demo",
        "kind": "topic",
        "title": "Demo",
        "project": "demo",
        "ontology_terms": [],
        "related": [],
        "source_refs": [],
        "content_preview": "",
        "file_path": "entities/topics/demo.md",
    }
    payload.update(overrides)
    return Entity.model_validate(payload)


def test_field_defaults_to_none() -> None:
    assert _entity().autonomous_run is None


def test_valid_reference_is_kept() -> None:
    assert _entity(autonomous_run=RUN_ID).autonomous_run == RUN_ID


def test_reference_without_the_run_prefix_is_refused() -> None:
    with pytest.raises(ValidationError, match="run:<id>"):
        _entity(autonomous_run="2026-07-24-curation-sweep-a3f1")


def test_bare_prefix_is_refused() -> None:
    with pytest.raises(ValidationError, match="run:<id>"):
        _entity(autonomous_run="run:")


def test_whitespace_only_reference_is_refused() -> None:
    with pytest.raises(ValidationError, match="run:<id>"):
        _entity(autonomous_run="run:   ")


def test_workflow_run_reference_is_refused() -> None:
    # `run_refs` (workflow runs, belief-bearing) and `autonomous_run` (provenance) are
    # different fields with different targets. Neither accepts the other's values.
    with pytest.raises(ValidationError, match="run:<id>"):
        _entity(autonomous_run="workflow-run:wf-r1")


def test_added_by_is_unaffected() -> None:
    entity = _entity(added_by="user", autonomous_run=RUN_ID)
    assert entity.added_by == "user"
    assert entity.autonomous_run == RUN_ID


def test_field_survives_the_frontmatter_round_trip(tmp_path: Path) -> None:
    # The layer that silently drops an unwired field: without the entity_kwargs mapping
    # this returns an Entity whose autonomous_run is None, with no error anywhere.
    path = tmp_path / "demo.md"
    path.write_text(
        "---\n"
        "id: topic:demo\n"
        "kind: topic\n"
        "title: Demo\n"
        "status: active\n"
        f"autonomous_run: {RUN_ID}\n"
        "---\n\nBody.\n",
        encoding="utf-8",
    )
    entity = parse_entity_file(path, "demo")
    assert entity is not None
    assert entity.autonomous_run == RUN_ID
```

`parse_entity_file(path, project_slug)` (`frontmatter.py:483`) is the function that builds
the `entity_kwargs` dict this task modifies — verified to load a minimal topic file and
return an `Entity` with `added_by` populated.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd science/model && uv run --frozen pytest tests/test_autonomous_run_field.py -v`
Expected: failures on `autonomous_run` being rejected as an unknown attribute or returning `None`.

- [ ] **Step 3: Add the field to `Entity`**

In `science/model/src/science_model/entities.py`, immediately after the `added_by` declaration (line 362):

```python
    # Execution stamp: the autonomous run that wrote this entity's file. Distinct from
    # `added_by`, which records how the IDEA entered the project ("user" is a legitimate
    # value there and no run record could explain it), and from EvidenceLineEntity.run_refs,
    # which names fingerprinted WORKFLOW runs and IS belief-bearing. Provenance metadata
    # only; MUST NOT affect evidential weight.
    autonomous_run: str | None = None
```

And the shape validator (place it beside the other `field_validator`s on this model):

```python
    @field_validator("autonomous_run")
    @classmethod
    def _validate_autonomous_run(cls, value: str | None) -> str | None:
        # Shape only. Whether a run record with this id exists is a resolution question,
        # answered by the graph build and by `refs-check`.
        if value is None:
            return value
        # `.strip()` on the remainder, not just a length check: `"run:   "` clears a bare
        # length test while naming nothing. `triggered_by` guards the same way.
        if not value.startswith(RUN_ID_PREFIX) or not value[len(RUN_ID_PREFIX) :].strip():
            raise ValueError(f"autonomous_run must be a 'run:<id>' reference, got {value!r}")
        return value
```

with the import at the top of the module:

```python
from science_model.autonomous_runs import RUN_ID_PREFIX
```

- [ ] **Step 4: Wire the frontmatter layer**

In `science/model/src/science_model/frontmatter.py`, in the `entity_kwargs` dict, directly after the `"added_by"` line:

```python
        "autonomous_run": fm.get("autonomous_run"),
```

- [ ] **Step 5: Write the failing schema test**

This step runs from `science/`, not `science/model/` — it exercises the schema through the
loader that consumes it, which is stronger than validating the JSON in isolation.

```python
# science/tests/test_autonomous_run_schema.py
from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.graph.sources import load_project_sources

RUN_ID = "run:2026-07-24-curation-sweep-a3f1"

# Both armed generations, and they resolve hypotheses through DIFFERENT mixin files:
# generation 2 -> mixin-hypothesis-1.0.json, generation 3 -> mixin-hypothesis-2.0.json.
ARMED_GENERATIONS = (2, 3)


def _write_project(root: Path, *, generation: int, extra: str = "") -> None:
    (root / "science.yaml").write_text(
        "name: demo\nknowledge_profiles:\n  local: local\n"
        f"entity_schema_version: {generation}\n",
        encoding="utf-8",
    )
    hypotheses = root / "entities" / "hypotheses"
    hypotheses.mkdir(parents=True, exist_ok=True)
    # `created`/`updated` MUST be quoted. Unquoted, YAML yields `datetime.date`, the
    # string-typed subschema fails, and `unevaluatedProperties` then reports the field
    # as unexpected -- a confusing error with a simple cause. Verified against the loader.
    (hypotheses / "h01.md").write_text(
        "---\n"
        "id: hypothesis:h01\n"
        "kind: hypothesis\n"
        "title: Demo hypothesis\n"
        "status: active\n"
        'created: "2026-07-24"\n'
        'updated: "2026-07-24"\n'
        f"{extra}"
        "---\n\nBody.\n",
        encoding="utf-8",
    )


@pytest.mark.parametrize("generation", ARMED_GENERATIONS)
def test_pinned_hypothesis_accepts_autonomous_run(tmp_path: Path, generation: int) -> None:
    # `hypothesis` is the one project mixin validated strictly
    # (PROJECT_MIXIN_NAMES, entity_schema/profile.py:24), so an undeclared key here is a
    # hard load failure -- not a preserved extra as on every other kind.
    _write_project(tmp_path, generation=generation, extra=f"autonomous_run: {RUN_ID}\n")
    sources = load_project_sources(tmp_path)
    entity = next(e for e in sources.entities if e.canonical_id == "hypothesis:h01")
    assert entity.autonomous_run == RUN_ID


@pytest.mark.parametrize("generation", ARMED_GENERATIONS)
def test_pinned_hypothesis_without_the_field_still_loads(tmp_path: Path, generation: int) -> None:
    _write_project(tmp_path, generation=generation)
    sources = load_project_sources(tmp_path)
    assert sources.entities[0].autonomous_run is None
```

Run: `cd science && uv run --frozen pytest tests/test_autonomous_run_schema.py -v`
Expected: `test_pinned_hypothesis_accepts_autonomous_run` fails for **both** generations with
`Unevaluated properties are not allowed ('autonomous_run' was unexpected)`. Verified: this is
the current behaviour at both 2 and 3.

- [ ] **Step 6: Declare it in BOTH strict hypothesis mixins**

In `science/model/src/science_model/schemas/mixin-hypothesis-1.0.json` **and**
`mixin-hypothesis-2.0.json`, add to `properties`, beside `added_by`:

```json
    "autonomous_run": { "type": "string" },
```

Re-run the schema test; all four parameterized cases must now pass.

- [ ] **Step 7: Run the tests to verify they pass**

```bash
cd science/model && uv run --frozen pytest tests/test_autonomous_run_field.py -v
cd science/model && uv run --frozen pytest > /tmp/pytest-model-task5.log 2>&1; echo "EXIT=$?"; tail -3 /tmp/pytest-model-task5.log
cd science && uv run --frozen pytest tests/test_autonomous_run_schema.py -v
```

Expected: `EXIT=0` and all schema tests pass.

- [ ] **Step 8: Commit**

```bash
git add science/model/src/science_model/entities.py science/model/src/science_model/frontmatter.py science/model/src/science_model/schemas/mixin-hypothesis-2.0.json science/model/tests/test_autonomous_run_field.py science/tests/test_autonomous_run_schema.py
git commit -m "feat(model): add the autonomous_run provenance field to Entity"
```

---

### Task 6: Materialize the entity→run edge

**Files:**
- Modify: `science/src/science_tool/graph/materialize.py`
- Test: `science/tests/test_autonomous_run_materialize.py`

**Interfaces:**
- Consumes: `ProjectSources.run_records`, `run_node_uri`, `Entity.autonomous_run`.
- Produces: `materialize._add_autonomous_run_edges(sources, *, provenance)` emitting `sci:autonomousRun`.

**A separate pass, not a line inside `_add_relations`.** The check needs the set of loaded run ids, which is a property of the whole source bundle, not of one entity — and `_add_relations` already takes ten parameters. This mirrors `_add_skill_load_edges`.

**An unknown run id raises.** The nearest precedent is `_add_run_ref_edges` (`materialize.py:1215`), which raises on an unresolved `workflow-run` reference. Emitting the edge anyway would put a reference to a nonexistent attestation into the graph — the precise shape of the fabrication hazard that motivated `InstrumentResult`.

- [ ] **Step 1: Write the failing tests**

Append to `science/tests/test_autonomous_run_materialize.py`:

```python
import pytest


def test_entity_links_to_its_run(tmp_path: Path) -> None:
    write_project(tmp_path, entity_extra=f"autonomous_run: {RUN_ID}\n")
    _, _knowledge, provenance = graphs(tmp_path)
    topic = project_entity_uri("topic:demo")
    assert (topic, SCI_NS.autonomousRun, run_node_uri(RUN_ID)) in provenance


def test_the_entity_run_edge_stays_out_of_knowledge(tmp_path: Path) -> None:
    write_project(tmp_path, entity_extra=f"autonomous_run: {RUN_ID}\n")
    _, knowledge, _provenance = graphs(tmp_path)
    assert (None, SCI_NS.autonomousRun, None) not in knowledge


def test_unknown_run_id_raises(tmp_path: Path) -> None:
    write_project(
        tmp_path, entity_extra="autonomous_run: run:2026-07-24-curation-sweep-ffff\n"
    )
    with pytest.raises(ValueError, match="unknown run record"):
        graphs(tmp_path)


def test_entity_without_the_field_emits_no_edge(tmp_path: Path) -> None:
    write_project(tmp_path)
    _, _knowledge, provenance = graphs(tmp_path)
    assert (None, SCI_NS.autonomousRun, None) not in provenance


def test_added_by_still_materializes_alongside(tmp_path: Path) -> None:
    write_project(
        tmp_path, entity_extra=f"added_by: user\nautonomous_run: {RUN_ID}\n"
    )
    _, _knowledge, provenance = graphs(tmp_path)
    topic = project_entity_uri("topic:demo")
    assert (topic, SCI_NS.addedBy, None) in provenance
    assert (topic, SCI_NS.autonomousRun, None) in provenance
```

`project_entity_uri("topic:demo")` and `materialize._entity_uri("topic:demo")` both produce
`http://example.org/project/topic/demo` — verified. Use the public helper, as
`test_skill_load_materialize.py` does.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd science && uv run --frozen pytest tests/test_autonomous_run_materialize.py -v`
Expected: the four new edge tests fail; `test_unknown_run_id_raises` fails because nothing raises.

- [ ] **Step 3: Write the implementation**

In `science/src/science_tool/graph/materialize.py`, beside `_add_run_record_edges`:

```python
def _add_autonomous_run_edges(sources: ProjectSources, *, provenance) -> None:
    """Link every entity carrying `autonomous_run` to its run node.

    A separate pass rather than a line in `_add_relations`: the check needs the set
    of run ids the whole bundle loaded, not anything about one entity.

    An unknown id RAISES. Emitting the edge anyway would put a reference to a
    nonexistent attestation into the graph, which is the fabrication shape the
    `InstrumentResult` work exists to prevent.
    """
    known = {record.id for record in sources.run_records}
    for entity in sources.entities:
        ref = entity.autonomous_run
        if not ref:
            continue
        if ref not in known:
            raise ValueError(
                f"{entity.canonical_id}: autonomous_run names unknown run record {ref!r}"
            )
        provenance.add((_entity_uri(entity.canonical_id), SCI_NS.autonomousRun, run_node_uri(ref)))
```

and call it immediately after `_add_run_record_edges(sources, provenance=provenance)`:

```python
    _add_autonomous_run_edges(sources, provenance=provenance)
```

Register the predicate this task mints, alongside Task 3's entries in
`science/src/science_tool/graph/store/constants.py`:

```python
    {
        "predicate": "sci:autonomousRun",
        "description": "Entity was last written by this autonomous run",
        "layer": "graph/provenance",
    },
```

The description says **last written by** deliberately: the field is a scalar and is
overwritten, so it names the most recent run, not every run that ever touched the file.

- [ ] **Step 4: Run the tests to verify they pass**

```bash
cd science && uv run --frozen pytest tests/test_autonomous_run_materialize.py -v
cd science && uv run --frozen pytest > /tmp/pytest-task6.log 2>&1; echo "EXIT=$?"; tail -3 /tmp/pytest-task6.log
```

Expected: `EXIT=0`.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/graph/materialize.py science/tests/test_autonomous_run_materialize.py
git commit -m "feat(graph): link entities to their autonomous run in provenance"
```

---

### Task 7: `refs-check` detects a dangling `autonomous_run`

**Files:**
- Modify: `science/src/science_tool/refs.py`
- Test: `science/tests/test_refs_autonomous_run.py` (create)

**Interfaces:**
- Consumes: `load_run_records` from `science_tool.graph.autonomous_runs`; `RefIssue`, `check_refs` from `science_tool.refs`.
- Produces: a `RefIssue` with `ref_type="autonomous-run"`.

This is design testing item 10. It is a **second surface, not a second rule**: both this check and Task 6's raise derive the valid set from the same `load_run_records`, so they cannot drift about which run ids exist. `refs-check` earns its place by needing no graph build — a curator can catch a dangling reference before materialization ever runs.

**Do not add `autonomous_run` to `_extract_frontmatter_refs`'s key tuple.** That routes values through `classify_entity_ref` against `_LOCAL_ENTITY_KINDS`, and `run` is not an entity kind — every valid reference would be reported as `unknown-namespace`. For the same reason, do not add `run` to `_LOCAL_ENTITY_KINDS`.

A malformed run record propagates its `RunRecordError` out of `check_refs`. That is intended: silently treating an unreadable `runs/` as empty would report every valid reference as dangling, which is a worse diagnosis than the real one.

`_extract_autonomous_run_ref` parses each file's frontmatter a second time, since
`_extract_frontmatter_refs` already parsed it. That is an accepted cost — `refs.py` already
re-parses per check, and matching that style beats threading a parsed-frontmatter cache
through this function for a corpus of this size. Worth revisiting only if `check_refs`
becomes hot.

- [ ] **Step 1: Write the failing tests**

```python
# science/tests/test_refs_autonomous_run.py
from __future__ import annotations

from pathlib import Path

import pytest

from science_model.autonomous_runs import RunRecordError
from science_tool.refs import check_refs

RUN_ID = "run:2026-07-24-curation-sweep-a3f1"

_RECORD = f"""---
id: {RUN_ID}
agent: curation-sweep
model: claude-opus-5
tier: belief-neutral
branch: auto/2026-07-24-curation-sweep-a3f1
base_commit: {"a" * 40}
head_commit: {"b" * 40}
toolkit_revision: {"c" * 40}
policy_identity:
  id: core-default
  version: "1"
basis_digest: {"d" * 64}
started: 2026-07-24T09:00:00+00:00
ended: 2026-07-24T09:30:00+00:00
budget:
  tokens: 12000
  wall_clock_seconds: 1800.5
disposition: clean
---

Body.
"""


def _write(root: Path, *, run_ref: str | None, with_record: bool = True) -> None:
    (root / "science.yaml").write_text(
        "name: demo\nknowledge_profiles:\n  local: local\n", encoding="utf-8"
    )
    topics = root / "entities" / "topics"
    topics.mkdir(parents=True, exist_ok=True)
    extra = f"autonomous_run: {run_ref}\n" if run_ref else ""
    (topics / "demo.md").write_text(
        f"---\nid: topic:demo\nkind: topic\ntitle: Demo\nstatus: active\n{extra}---\n\nBody.\n",
        encoding="utf-8",
    )
    if with_record:
        runs = root / "runs"
        runs.mkdir(parents=True, exist_ok=True)
        (runs / "2026-07-24-curation-sweep-a3f1.md").write_text(_RECORD, encoding="utf-8")


def _run_issues(root: Path):
    return [issue for issue in check_refs(root) if issue.ref_type == "autonomous-run"]


def test_resolvable_reference_reports_nothing(tmp_path: Path) -> None:
    _write(tmp_path, run_ref=RUN_ID)
    assert _run_issues(tmp_path) == []


def test_dangling_reference_is_reported(tmp_path: Path) -> None:
    _write(tmp_path, run_ref="run:2026-07-24-curation-sweep-ffff")
    issues = _run_issues(tmp_path)
    assert len(issues) == 1
    assert issues[0].ref_value == "run:2026-07-24-curation-sweep-ffff"
    assert "no run record" in issues[0].message
    assert issues[0].file == "entities/topics/demo.md"


def test_reference_with_no_runs_directory_is_reported(tmp_path: Path) -> None:
    _write(tmp_path, run_ref=RUN_ID, with_record=False)
    assert len(_run_issues(tmp_path)) == 1


def test_entity_without_the_field_reports_nothing(tmp_path: Path) -> None:
    _write(tmp_path, run_ref=None)
    assert _run_issues(tmp_path) == []


def test_added_by_is_never_treated_as_a_run_reference(tmp_path: Path) -> None:
    # Design testing item 10, second half: `user` and `explore-ideas:...` stay valid.
    (tmp_path / "science.yaml").write_text(
        "name: demo\nknowledge_profiles:\n  local: local\n", encoding="utf-8"
    )
    topics = tmp_path / "entities" / "topics"
    topics.mkdir(parents=True, exist_ok=True)
    (topics / "demo.md").write_text(
        "---\nid: topic:demo\nkind: topic\ntitle: Demo\nstatus: active\n"
        "added_by: user\n---\n\nBody.\n",
        encoding="utf-8",
    )
    assert _run_issues(tmp_path) == []


def test_malformed_run_record_propagates(tmp_path: Path) -> None:
    _write(tmp_path, run_ref=RUN_ID)
    record = tmp_path / "runs" / "2026-07-24-curation-sweep-a3f1.md"
    record.write_text(
        record.read_text(encoding="utf-8").replace("disposition: clean", "disposition: passed"),
        encoding="utf-8",
    )
    with pytest.raises(RunRecordError):
        check_refs(tmp_path)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd science && uv run --frozen pytest tests/test_refs_autonomous_run.py -v`
Expected: `test_dangling_reference_is_reported` and `test_reference_with_no_runs_directory_is_reported` fail with an empty issue list; `test_malformed_run_record_propagates` fails with `DID NOT RAISE`.

- [ ] **Step 3: Write the implementation**

In `science/src/science_tool/refs.py`, add the helper beside `_extract_frontmatter_refs`:

```python
def _extract_autonomous_run_ref(path: Path) -> str | None:
    """The file's `autonomous_run` value, or None.

    Deliberately not folded into `_extract_frontmatter_refs`: those values are
    classified against `_LOCAL_ENTITY_KINDS`, and `run` is not an entity kind, so
    every valid reference would come back as `unknown-namespace`.
    """
    parsed = parse_frontmatter(path)
    if parsed is None:
        return None
    frontmatter, _body = parsed
    value = frontmatter.get("autonomous_run")
    return value if isinstance(value, str) and value else None
```

In `check_refs`, beside the other corpus loads (after `pmid_corpus = _load_pmid_corpus(root)`):

```python
    # Raises on a malformed record rather than reporting an empty set: treating an
    # unreadable runs/ as "no runs" would report every valid reference as dangling.
    run_ids = {record.id for record in load_run_records(root)}
```

and inside the per-file loop, immediately after `frontmatter_lines = _frontmatter_line_numbers(file_path)`:

```python
        run_ref = _extract_autonomous_run_ref(file_path)
        if run_ref is not None and run_ref not in run_ids:
            issues.append(
                RefIssue(
                    file=rel_path,
                    line=1,
                    ref_type="autonomous-run",
                    ref_value=run_ref,
                    message=f"{run_ref} — no run record in runs/",
                )
            )
```

with the import at the top of the module:

```python
from science_tool.graph.autonomous_runs import load_run_records
```

A module-level import is safe here — verified: no module under `science_tool/graph/`
imports `science_tool.refs`, and `graph.autonomous_runs` imports only `science_model` plus
`graph.store`, so there is no cycle to create. Confirm with
`cd science && uv run python -c "import science_tool.refs"` after the edit.

- [ ] **Step 4: Run the tests to verify they pass**

```bash
cd science && uv run --frozen pytest tests/test_refs_autonomous_run.py -v
cd science && uv run --frozen pytest > /tmp/pytest-task7.log 2>&1; echo "EXIT=$?"; tail -3 /tmp/pytest-task7.log
```

Expected: `EXIT=0`.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/refs.py science/tests/test_refs_autonomous_run.py
git commit -m "feat(refs): report a dangling autonomous_run reference"
```

---

### Task 8: Serialization root and documentation

**Files:**
- Modify: `science/src/science_tool/project_package/serialize.py:36`
- Modify: `docs/user-guide/project-layout.md`
- Modify: `docs/user-guide/entities.md`
- Modify: `docs/plans/2026-07-24-autonomy-envelope-design.md`
- Test: `science/tests/test_project_serialize_runs_root.py` (create)

**Interfaces:**
- Consumes: `SOURCE_ROOTS` from `science_tool.project_package.serialize`.
- Produces: no new public API.

`SOURCE_ROOTS = ("entities", "results")` is an explicit list, so `runs/` would be omitted from a serialized project — producing an archive whose entities carry `autonomous_run` references with no run records to resolve them. An archive that drops the attestations while keeping the claims is worse than one that drops both.

- [ ] **Step 1: Write the failing test**

```python
# science/tests/test_project_serialize_runs_root.py
from __future__ import annotations

from science_tool.project_package.serialize import SOURCE_ROOTS


def test_runs_is_a_serialize_source_root() -> None:
    # Without this, a serialized project keeps entities whose `autonomous_run`
    # references nothing — the claims travel and the attestations do not.
    assert "runs" in SOURCE_ROOTS
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_project_serialize_runs_root.py -v`
Expected: FAIL — `assert 'runs' in ('entities', 'results')`.

- [ ] **Step 3: Add the root**

In `science/src/science_tool/project_package/serialize.py`:

```python
SOURCE_ROOTS = ("entities", "results", "runs")
```

- [ ] **Step 4: Run the serialize tests**

```bash
cd science && uv run --frozen pytest tests/test_project_serialize_runs_root.py -v
cd science && uv run --frozen pytest -k serialize -v
```

Expected: all pass. If a snapshot or manifest test now differs, update the expectation — the new root is intended.

- [ ] **Step 5: Document the `runs/` root**

In `docs/user-guide/project-layout.md`, add a row to the **Common Roots** table, directly after the `results/` row:

```markdown
| `runs/` | Supervisor-written **autonomous-run records**, one flat `<date>-<agent>-<short-id>.md` per finished unattended run. Not an entity root: run records materialize only into `graph/provenance` and never become belief bearers. Distinct from `results/`, which holds fingerprinted *workflow*-run records (compute reproducibility, not agent authority). |
```

- [ ] **Step 6: Document the field**

In `docs/user-guide/entities.md`, in the section that describes `added_by` (around line 722), add:

```markdown
### Autonomous Run Provenance

An entity written by an unattended agent run carries `autonomous_run`, a
reference to a record in `runs/`:

```yaml
autonomous_run: run:2026-07-24-curation-sweep-a3f1
```

This answers a different question from `added_by`. `added_by` records how an
*idea* entered the project and legitimately holds values like `user` that no run
could explain; `autonomous_run` records which *execution* wrote the file. Neither
counts as evidence, and neither updates belief.

It is also distinct from an evidence line's `run_refs`, which names fingerprinted
workflow runs and *does* bear on belief. A dangling `autonomous_run` — one naming
a run with no record in `runs/` — is reported by `science refs check` and fails
the graph build.

The field is a scalar and is overwritten, so it names the **last** run that wrote
the file. Full attribution history lives in git, under each run record's
`base_commit..head_commit` range.
```

- [ ] **Step 7: Correct the design document**

In `docs/plans/2026-07-24-autonomy-envelope-design.md` §3, replace the `run_ref` entity paragraph with the corrected name and record why:

```markdown
**Entities.** A new field `autonomous_run` carries a validated reference to a run
record, materialized into `graph/provenance` alongside `added_by`. `added_by`
**keeps its existing discovery semantics unchanged** — it answers "how did this
idea enter the project", which is a different question from "which execution
wrote this file", and the corpus already contains values (`user`) that no run
record could ever explain.

> **Revised during implementation (Plan B).** This field was originally specified
> as `run_ref`. That name was already taken by `EvidenceLineEntity.run_refs`, which
> names fingerprinted workflow runs, materializes to `sci:runRef` in
> `graph/knowledge`, and **bears on belief** through `graph/store/validation.py`. A
> provenance field spelled `run_ref` beside a belief-bearing field spelled
> `run_refs` is a one-character path across the belief boundary. The predicate is
> `sci:autonomousRun` and the node type `sci:AutonomousRun` for the same reason;
> the persisted model is `AutonomousRunRecord`, since `qa_audit/runs.py` already
> owns `RunRecord`. The `run:` id prefix is unused and is kept as designed.
```

**Then sweep the remaining occurrences.** `run_ref` survives in four places in the design;
verify with `grep -n 'run_ref' docs/plans/2026-07-24-autonomy-envelope-design.md` and fix
all of them:

- **line 146**, the §2 field table: "referent of `run_ref` and the commit trailer" →
  `autonomous_run`.
- **line 167**, the derivability paragraph. This one needs more than a rename — the claim
  itself is now weaker. Replace with:

  ```markdown
  The record deliberately does **not** index the entities it wrote. Each entity's *current*
  writer is derivable by querying `autonomous_run` in the provenance graph, and full
  history is derivable from the run's own `base_commit..head_commit` range — which is the
  authoritative binding in any case (§0). A maintained list would be a second spelling that
  drifts.
  ```

- **line 197**, §3 — replaced by the block above.
- **line 339**, testing item 10 — rename, and change `refs-check` to `refs check` (the CLI
  is a `refs` group with a `check` subcommand, `refs_cli.py:16,68`).

- [ ] **Step 7b: Record what Plan B did NOT close**

Add to §3, after the corrected entity paragraph:

```markdown
> **Not yet an attested binding (Plan B ships the field only).** Materialization checks
> that the run a value names *exists*; it does not check that this run wrote this file. An
> actor can therefore still attribute its work to an unrelated prior run. Plan D must close
> this by having the supervisor stamp `autonomous_run` itself, or by verifying every value
> it finds against the run's own recorded `base_commit..head_commit` range. Until then the
> field is a convenience for humans reading the corpus, and the commit range remains the
> only authoritative binding (§0).
```

- [ ] **Step 8: Run everything**

```bash
cd science && uv run --frozen pytest > /tmp/pytest-final.log 2>&1; echo "EXIT=$?"; tail -3 /tmp/pytest-final.log
cd science/model && uv run --frozen pytest > /tmp/pytest-model-final.log 2>&1; echo "EXIT=$?"; tail -3 /tmp/pytest-model-final.log
cd science && uv run ruff check
cd science/model && uv run ruff check
cd science && uv run pyright
```

Expected: both `EXIT=0`, ruff clean in both packages, pyright `0 errors`.

- [ ] **Step 9: Commit**

```bash
git add science/src/science_tool/project_package/serialize.py science/tests/test_project_serialize_runs_root.py docs/
git commit -m "docs: document the runs/ root and the autonomous_run field"
```

---

## Verification checklist

Run after Task 8, before finishing the branch:

- [ ] `cd science && uv run --frozen pytest` — exit 0 (check `$?`, not a pipe's status)
- [ ] `cd science/model && uv run --frozen pytest` — exit 0
- [ ] `cd science && uv run ruff check` and `cd science/model && uv run ruff check` — clean
- [ ] `cd science && uv run pyright` — 0 errors
- [ ] `git log --format='%B' main..HEAD | grep -iE 'co-authored-by|generated with|claude'` — **no output**
- [ ] No line in a new or modified file exceeds 100 characters (ruff does not check this)
- [ ] `grep -rn 'run_ref' science/src science/model/src` returns only the pre-existing
      `run_refs` (workflow-run) hits — this plan introduced no new `run_ref` spelling
- [ ] `grep -n 'run_ref' docs/plans/2026-07-24-autonomy-envelope-design.md` returns nothing
- [ ] `cd science && uv run science graph predicates` lists every new `sci:run*` predicate
      and `sci:autonomousRun`
- [ ] A project with no `runs/` directory still loads, builds, and validates unchanged
- [ ] A run record declaring `tier:` twice is refused, not silently read as its last value

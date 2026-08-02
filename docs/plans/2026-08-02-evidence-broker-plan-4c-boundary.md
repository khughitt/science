# Evidence Broker Plan 4c — The Boundary

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give `check_correspondence` a trusted caller — a review-append boundary that computes a
review's correspondence rather than accepting one, refuses what cannot be attested, and makes an
uncounted agent confirmation visible instead of silently absent from a number.

**Architecture:** Three layers, landed bottom-up. The model (`science_model/audit/record.py`) gains
the submission/attestation split and the stored-`Review` invariants, so no write path anywhere can
store a `violated` correspondence or an agent review without one. The boundary
(`science_tool/findings/reviews.py`) is the only function that builds a `Review`: it revalidates its
arguments, resolves the attested run record, cross-checks identity against sealed run state, calls
`check_correspondence`, and writes under the case-store lock. A non-gating `validate` check reports
every agent confirmation the eligibility rule excludes. There is no CLI command — the producer
arrives in spec 2c, and §4.2's zero-migration argument holds until it does.

**Tech Stack:** Python 3.13, Pydantic v2, `uv` workspaces, pytest. Two packages:
`science/model/` (the `science-model` package) and `science/` (the `science` CLI package).

## Global Constraints

- **Design of record:** `docs/plans/2026-07-30-agent-evidence-broker-design.md` at **revision 36**.
  Where this plan and the design disagree, the design governs — raise the conflict, do not silently
  deviate.
- **Exact file boundary (design §2.2, 4c column).** Create only `science/src/science_tool/findings/reviews.py`
  and `science/src/science_tool/validate/checks/review_confirmations.py`. Modify only
  `science/model/src/science_model/audit/record.py`, `science/model/src/science_model/audit/__init__.py`,
  `science/src/science_tool/findings/storage.py`, `science/src/science_tool/findings/ingest.py`,
  `science/src/science_tool/validate/checks/__init__.py`, `science/src/science_tool/validate/findings.py`.
- **Must not touch:** `science/src/science_tool/evidence_broker/serve.py`,
  `science/src/science_tool/evidence_broker/correspondence.py`,
  `science/src/science_tool/evidence_broker/hits.py`,
  `science/model/src/science_model/correspondence.py`. 4c consumes the checker; it does not adjust it.
- **`science/src/science_tool/findings/cli.py` is NOT modified.** Its line 317 calls
  `record.confirmation_count()`; what that returns changes, the call site does not.
- `MAX_EVIDENCE_ENTRIES = 100`, imported from `science_model.audit.evidence`. `MAX_UNCERTAINTY_ENTRIES`
  is **defined as** `MAX_EVIDENCE_ENTRIES` — one number, honest name at each use.
- `ReviewerKind = Literal["human", "agent", "deterministic"]`;
  `ReviewOutcome = Literal["confirms", "refutes", "abstains"]`. Both already exist in
  `audit/record.py`. Never re-spell either as a hand-written list.
- Conventional commits. **No AI-attribution trailer or footer** on any commit, PR, or comment.
- Composition over inheritance; explicit over defensive; fail early rather than silent fallback; no
  "legacy"/"compatibility" layers; no `Unified` prefix.
- **Run tests from the package directory** — there is no root `pyproject.toml`:
  `cd science && uv run --frozen pytest ...` and `cd science/model && uv run --frozen pytest ...`.
- Use scoped test selections. Do **not** run the full CLI suite (~12k tests, 6:42–7:24) during
  tasks; Task 8 owns the one full run, with an explicit long timeout.
- Lint and types from `science/`: `uv run ruff check` and `uv run pyright`.

---

## File Structure

| File | Responsibility |
|---|---|
| `science/model/src/science_model/audit/record.py` | `Uncertainty`, `ReviewAttestation`, `ReviewSubmission`, `MAX_UNCERTAINTY_ENTRIES`; three new `Review` fields and two invariants; `Review.counts_as_support()`; `confirmation_count` delegating to it |
| `science/model/src/science_model/audit/__init__.py` | re-export the three new types beside `Review` |
| `science/src/science_tool/findings/storage.py` | public `locked_store`, moved from `ingest.py`, converting `flock`/`close` `OSError` to `CaseStorageError` |
| `science/src/science_tool/findings/ingest.py` | drops `_locked_store`; `ingest_report` translates `CaseStorageError` to `IngestError` at its own boundary |
| `science/src/science_tool/findings/reviews.py` | **NEW** — `append_review` and nothing else |
| `science/src/science_tool/validate/checks/review_confirmations.py` | **NEW** — rule `review.uncounted-confirmation` |
| `science/src/science_tool/validate/checks/__init__.py` | register the new check module |
| `science/src/science_tool/validate/findings.py` | add the rule id to `_POLICY_INFO_RULE_IDS` |

Test files (flat, matching the repo's existing convention):

| Test file | Covers |
|---|---|
| `science/tests/conftest.py` | **modified** — the shared fixtures Tasks 5–7 all use (`stored_case`, `human_attestation`, `agent_attestation`, `unbrokered_run`, `sealed_agent_run`, `case_files`). `science/tests/` is not a package, so fixtures are the only sharing mechanism that works |
| `science/model/tests/test_audit_review_contract.py` | Tasks 2–4 (model types, invariants, eligibility) |
| `science/model/tests/test_audit_import_cycle.py` | the two subprocess cycle rows (Task 3). The leaf-loads-no-audit guard is 4b's and already lives in `test_correspondence.py` — do not restate it |
| `science/tests/test_findings_locked_store.py` | Task 1 |
| `science/tests/test_findings_reviews.py` | Tasks 5–6 |
| `science/tests/test_review_confirmations_check.py` | Task 7 |

---

## Task 1: Extract `locked_store` into the storage layer

**Files:**
- Modify: `science/src/science_tool/findings/storage.py`
- Modify: `science/src/science_tool/findings/ingest.py:237-261` (delete `_locked_store`), `:562` (call site)
- Test: `science/tests/test_findings_locked_store.py` (create)

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `@contextmanager def locked_store(project_root: Path) -> Iterator[CaseStore]` in
  `science_tool.findings.storage`, raising `CaseStorageError` for lock acquisition, release, and
  close failures. Task 5 uses it.

**Background the implementer needs.** `_locked_store` currently lives in `ingest.py`, has one caller,
and raises `IngestError` — an error type defined in `ingest.py`, which already imports `case_store`
from `storage.py`. Moving it as-is would invert that dependency, so the error translation moves to
the callers instead. Two facts, both **measured**, that decide the shape:

1. `case_store` (`storage.py:255-261`) keeps its `try` **active across its own `yield`**. A
   `PathSafetyError` raised by `store.lock()` inside the caller's `with` body is thrown back into
   that generator and converted to `CaseStorageError` there. `locked_store` therefore needs **no**
   `PathSafetyError` clause — that conversion already happens one layer down.
2. The `fcntl.flock` and `os.close` calls raise `OSError` that nothing catches. Those are what
   `locked_store` adds, and the contract covers **acquisition, release and close**.

`locked_store` must **not** widen its `try` across its own `yield`.

- [ ] **Step 1: Write the failing tests**

Create `science/tests/test_findings_locked_store.py`:

```python
from __future__ import annotations

import errno
import fcntl
import os
from pathlib import Path

import pytest

from science_tool.findings.storage import CaseStorageError, locked_store


def _project(tmp_path: Path) -> Path:
    (tmp_path / "doc" / "audits" / "cases").mkdir(parents=True)
    return tmp_path


def test_locked_store_yields_a_store(tmp_path: Path) -> None:
    with locked_store(_project(tmp_path)) as store:
        assert store.names() == []


def test_flock_acquisition_failure_becomes_case_storage_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(fd: int, operation: int) -> None:
        raise OSError(errno.ENOLCK, "no locks available")

    monkeypatch.setattr(fcntl, "flock", boom)
    with pytest.raises(CaseStorageError, match="lock"):
        with locked_store(_project(tmp_path)):
            pass


def test_flock_release_failure_becomes_case_storage_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = fcntl.flock
    calls: list[int] = []

    def flaky(fd: int, operation: int) -> None:
        calls.append(operation)
        if operation == fcntl.LOCK_UN:
            raise OSError(errno.EIO, "release failed")
        real(fd, operation)

    monkeypatch.setattr(fcntl, "flock", flaky)
    with pytest.raises(CaseStorageError, match="lock"):
        with locked_store(_project(tmp_path)):
            pass
    assert fcntl.LOCK_UN in calls


def test_close_failure_becomes_case_storage_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = os.close
    state = {"armed": False}

    def flaky(fd: int) -> None:
        if state["armed"]:
            state["armed"] = False
            raise OSError(errno.EIO, "close failed")
        real(fd)

    monkeypatch.setattr(os, "close", flaky)
    project = _project(tmp_path)
    with pytest.raises(CaseStorageError, match="lock"):
        with locked_store(project):
            state["armed"] = True


def test_body_exception_is_not_relabelled(tmp_path: Path) -> None:
    """`locked_store` adds NO catch spanning its body.

    An OSError that is neither FileNotFoundError nor PathSafetyError is not
    intercepted by `case_store`'s pre-existing clauses either, so it must arrive
    at the caller as itself.
    """
    sentinel = OSError(errno.EIO, "sentinel from the body")
    with pytest.raises(OSError) as caught:
        with locked_store(_project(tmp_path)):
            raise sentinel
    assert caught.value is sentinel
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd science && uv run --frozen pytest tests/test_findings_locked_store.py -q
```

Expected: collection error — `ImportError: cannot import name 'locked_store' from
'science_tool.findings.storage'`.

- [ ] **Step 3: Add `locked_store` to `storage.py`**

Append after `case_store` (which ends at line 261). `fcntl` must be added to the module's imports;
`os` and `contextmanager` are already imported.

```python
@contextmanager
def locked_store(project_root: Path) -> Iterator[CaseStore]:
    """Serialize case writes per project and hand back the SAME anchored store.

    The lock and every case operation act through ONE directory descriptor. Taking the
    lock and then obtaining a store from a second walk would reintroduce exactly the
    check/use gap the descriptor exists to close -- the lock would be held on one
    directory while the writes went to whatever the pathname named by then.

    This function adds ONE conversion, over `flock` and `close`, which otherwise raise
    a bare `OSError`. It deliberately adds NO catch spanning its own `yield`: a
    contextmanager whose `try` covers the caller's body relabels the caller's
    exceptions as its own. (`case_store` does have that shape, so a body-raised
    `PathSafetyError` or `FileNotFoundError` is still converted one layer down -- that
    is its behaviour, not a promise this function makes.)
    """
    with case_store(project_root, create=True) as store:
        # NO try around `store.lock()`. `open_lock_at` already converts its `OSError` to
        # `PathSafetyError` (paths.py:556-563), and `case_store`'s own `try` — which
        # stays active across its `yield` — converts that to `CaseStorageError`. A clause
        # here would be unreachable, and an unreachable clause reads as a guard.
        descriptor = store.lock()
        try:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX)
            except OSError as exc:
                raise CaseStorageError(f"could not acquire the case store lock: {exc}") from exc
            try:
                yield store
            finally:
                try:
                    fcntl.flock(descriptor, fcntl.LOCK_UN)
                except OSError as exc:
                    raise CaseStorageError(
                        f"could not release the case store lock: {exc}"
                    ) from exc
        finally:
            try:
                os.close(descriptor)
            except OSError as exc:
                raise CaseStorageError(f"could not close the case store lock: {exc}") from exc
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
cd science && uv run --frozen pytest tests/test_findings_locked_store.py -q
```

Expected: 5 passed.

- [ ] **Step 5: Delete `_locked_store` from `ingest.py` and translate at the boundary**

Delete `ingest.py:237-261` in full (the `@contextmanager def _locked_store(...)` block and its
decorator). Remove the now-unused `fcntl` import if nothing else in the module uses it — check with
`grep -n fcntl science/src/science_tool/findings/ingest.py` before removing.

Add `locked_store` to the existing `from science_tool.findings.storage import ...` block, and change
the call site at what is currently line 562 from `with _locked_store(project_root) as store:` to
wrap the whole locked region so the translation covers everything the lock covers:

```python
    try:
        with locked_store(project_root) as store:
            writes, written, appended, skipped = _classify_writes(
                # ... body unchanged ...
            )
    except (CaseStorageError, PathSafetyError) as exc:
        raise IngestError(str(exc)) from exc
```

`PathSafetyError` stays in the tuple: `_classify_writes` and the record operations inside the body
can raise it, and `ingest_report` converted it before this change.

- [ ] **Step 6: Verify `ingest_report`'s observable behaviour is unchanged**

```bash
cd science && uv run --frozen pytest tests/test_findings_ingest.py tests/test_findings_storage.py tests/test_findings_isolation.py -q
```

Expected: all pass, no change in counts from before this task.

- [ ] **Step 7: Lint and commit**

```bash
cd science && uv run ruff check && uv run pyright
git add science/src/science_tool/findings/storage.py science/src/science_tool/findings/ingest.py science/tests/test_findings_locked_store.py
git commit -m "refactor(findings): move the anchored store lock into storage"
```

---

## Task 2: The submission/attestation types

**Files:**
- Modify: `science/model/src/science_model/audit/record.py`
- Modify: `science/model/src/science_model/audit/__init__.py`
- Test: `science/model/tests/test_audit_review_contract.py` (create)

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces, all importable from `science_model.audit`:
  - `MAX_UNCERTAINTY_ENTRIES: int`
  - `Uncertainty(field: str, what: str, why: str)`
  - `ReviewAttestation(reviewer_kind, reviewer_ref, lens=None, model=None, run_ref, at)`
  - `ReviewSubmission(outcome, note, evidence=(), uncertainty=())`

**Background.** `_Base` in `record.py:162` is `extra="forbid", frozen=True,
revalidate_instances="always"`. `AuthoredProvenance` (`:107`) rejects blank/padded strings;
`AuthoredHashComponent` (`:108`) adds NUL rejection and is used for the fields `review_id` hashes.
`Instant` is the datetime alias `Review.at` already uses. The design (§4.2) requires
`ReviewAttestation` to carry the **same** agent invariant as `Review` — an agent needs `lens` and
`model` — so a bad attestation fails at the argument rather than three steps later at the record.

- [ ] **Step 1: Write the failing tests**

Create `science/model/tests/test_audit_review_contract.py`:

```python
from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from science_model.audit import ReviewAttestation, ReviewSubmission, Uncertainty
from science_model.audit.evidence import MAX_EVIDENCE_ENTRIES, TextEvidence
from science_model.audit.record import MAX_UNCERTAINTY_ENTRIES

AT = datetime(2026, 8, 2, tzinfo=UTC)


def _attestation(**overrides: object) -> ReviewAttestation:
    fields: dict[str, object] = {
        "reviewer_kind": "agent",
        "reviewer_ref": "curation-sweep",
        "lens": "instrument:review-v1",
        "model": "test-model",
        "run_ref": "run:2026-08-02-curation-sweep-a3f1",
        "at": AT,
    }
    fields.update(overrides)
    return ReviewAttestation(**fields)  # type: ignore[arg-type]


def test_max_uncertainty_entries_is_the_evidence_bound() -> None:
    assert MAX_UNCERTAINTY_ENTRIES == MAX_EVIDENCE_ENTRIES


def test_submission_cannot_express_a_reviewer_kind() -> None:
    with pytest.raises(ValidationError):
        ReviewSubmission(outcome="confirms", note="n", reviewer_kind="human")  # type: ignore[call-arg]


def test_submission_cannot_express_a_correspondence() -> None:
    with pytest.raises(ValidationError):
        ReviewSubmission(outcome="confirms", note="n", correspondence={"status": "verified"})  # type: ignore[call-arg]


def test_submission_bounds_evidence() -> None:
    entry = TextEvidence(type="text", text="x")
    ReviewSubmission(outcome="confirms", note="n", evidence=(entry,) * MAX_EVIDENCE_ENTRIES)
    with pytest.raises(ValidationError):
        ReviewSubmission(
            outcome="confirms", note="n", evidence=(entry,) * (MAX_EVIDENCE_ENTRIES + 1)
        )


def test_submission_bounds_uncertainty() -> None:
    item = Uncertainty(field="severity", what="unsure", why="thin evidence")
    ReviewSubmission(outcome="confirms", note="n", uncertainty=(item,) * MAX_UNCERTAINTY_ENTRIES)
    with pytest.raises(ValidationError):
        ReviewSubmission(
            outcome="confirms", note="n", uncertainty=(item,) * (MAX_UNCERTAINTY_ENTRIES + 1)
        )


def test_agent_attestation_requires_a_lens() -> None:
    with pytest.raises(ValidationError, match="lens"):
        _attestation(lens=None)


def test_agent_attestation_requires_a_model() -> None:
    """`lens` present, so this can only fail on `model`."""
    with pytest.raises(ValidationError, match="model"):
        _attestation(model=None)


def test_non_agent_attestation_needs_neither() -> None:
    assert _attestation(reviewer_kind="human", lens=None, model=None).lens is None
    assert _attestation(reviewer_kind="deterministic", lens=None, model=None).model is None


def test_uncertainty_rejects_a_blank_field() -> None:
    with pytest.raises(ValidationError):
        Uncertainty(field="  ", what="unsure", why="thin evidence")
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd science/model && uv run --frozen pytest tests/test_audit_review_contract.py -q
```

Expected: collection error — `ImportError: cannot import name 'MAX_UNCERTAINTY_ENTRIES' from
'science_model.audit'`.

- [ ] **Step 3: Add the types to `record.py`**

Insert immediately before `class Review(_Base):` (currently line 281). `MAX_EVIDENCE_ENTRIES` and
`Evidence` are already imported at line 28; `Field` is already imported from pydantic.

```python
#: The same number as the evidence bound, by an honest name. Both tuples arrive on one
#: submission from one untrusted producer, and there is no reason for them to differ; a
#: second literal would be a second thing to drift.
MAX_UNCERTAINTY_ENTRIES = MAX_EVIDENCE_ENTRIES


class Uncertainty(_Base):
    """One thing a reviewer declined to be sure about.

    `field` names what the reviewer was unsure of. It enters no digest -- so it is
    `AuthoredProvenance`, not `AuthoredHashComponent`, whatever the shape of the
    neighbouring identity fields suggests.
    """

    field: AuthoredProvenance
    what: AuthoredProvenance
    why: AuthoredProvenance


class ReviewAttestation(_Base):
    """Who is reviewing and WHEN, asserted by the caller that KNOWS -- never by the
    reviewer. The exact counterpart of `IngestionProvenance` at `ingest_report`.

    `at` is attested rather than clocked for the same reason `ingest_report` takes
    `observed_at` from `provenance.generated_at`: when a thing happened is part of what
    the trusted caller attests.
    """

    reviewer_kind: ReviewerKind
    reviewer_ref: AuthoredHashComponent
    lens: AuthoredHashComponent | None = None
    model: AuthoredProvenance | None = None
    run_ref: AuthoredHashComponent
    at: Instant

    @model_validator(mode="after")
    def _agent_provenance(self) -> ReviewAttestation:
        if self.reviewer_kind == "agent":
            if not self.lens:
                raise RecordError("an agent attestation requires a lens (design §4.2)")
            if not self.model:
                raise RecordError("an agent attestation requires model provenance (design §4.2)")
        return self


class ReviewSubmission(_Base):
    """What a producer offers: its FINDINGS, and nothing about its own identity.

    Carries no correspondence field and no identity field -- not fields a producer may
    leave blank, fields it cannot express. A Pydantic invariant can constrain a value's
    shape but can never establish its provenance, so the submitted type is made
    structurally incapable of carrying either.
    """

    outcome: ReviewOutcome
    note: AuthoredProvenance
    evidence: tuple[Evidence, ...] = Field(default=(), max_length=MAX_EVIDENCE_ENTRIES)
    uncertainty: tuple[Uncertainty, ...] = Field(default=(), max_length=MAX_UNCERTAINTY_ENTRIES)
```

Check that `Instant` is imported in `record.py`; `Review.at: Instant` already uses it, so it is.

- [ ] **Step 4: Re-export from `audit/__init__.py`**

Add `ReviewAttestation`, `ReviewSubmission`, `Uncertainty` to the
`from science_model.audit.record import (...)` block at line 10, and add each name to `__all__`,
keeping both lists in their existing alphabetical order.

**Only those three.** Design §2 names exactly `Uncertainty, ReviewAttestation, ReviewSubmission` for
this file. `MAX_UNCERTAINTY_ENTRIES` stays importable from `science_model.audit.record`, beside
`MAX_EVIDENCE_ENTRIES` which is likewise not re-exported here — a bound is not part of the package's
public type surface, and widening the re-export list beyond the contract is how a cell stops
describing the diff.

- [ ] **Step 5: Run the tests to verify they pass**

```bash
cd science/model && uv run --frozen pytest tests/test_audit_review_contract.py -q
```

Expected: 9 passed.

- [ ] **Step 6: Commit**

```bash
git add science/model/src/science_model/audit/record.py science/model/src/science_model/audit/__init__.py science/model/tests/test_audit_review_contract.py
git commit -m "feat(audit): add the review submission and attestation types"
```

---

## Task 3: Stored-`Review` fields and invariants

**Files:**
- Modify: `science/model/src/science_model/audit/record.py`
- Test: `science/model/tests/test_audit_review_contract.py` (extend)
- Test: `science/model/tests/test_audit_import_cycle.py` (create)

**Interfaces:**
- Consumes: Task 2's types.
- Produces: `Review.evidence`, `Review.uncertainty`, `Review.correspondence`; the two invariants.
  Task 4 reads all three.

**Background.** This task adds the import that closes a potential cycle:
`science_model/audit/record.py` importing `Correspondence` from `science_model/correspondence.py`.
That leaf was shipped by plan 4b and **deliberately imports nothing from `science_model`** — it uses
plain `BaseModel`, not `_Base`. Two mutations must break loudly, and both need a **fresh
interpreter**: under pytest, `sys.modules` will already hold one side of the cycle and an in-process
import proves only the runner's import order.

Also measured, and worth knowing before writing the invariant: a `Correspondence` built past its own
validator with `model_construct(status="verified", code="X")` **is** refused when a `Review`
carrying it is constructed, because `Review` inherits `_Base`'s `revalidate_instances="always"`.

- [ ] **Step 1: Write the failing tests**

Append to `science/model/tests/test_audit_review_contract.py`:

```python
from science_model.audit import Review, review_id
from science_model.audit.evidence import LocationEvidence
from science_model.correspondence import Correspondence

FINDING_ID = "0" * 64


def _review(**overrides: object) -> Review:
    fields: dict[str, object] = {
        "reviewer_kind": "agent",
        "reviewer_ref": "curation-sweep",
        "lens": "instrument:review-v1",
        "model": "test-model",
        "run_ref": "run:2026-08-02-curation-sweep-a3f1",
        "at": AT,
        "outcome": "confirms",
        "note": "n",
        "correspondence": Correspondence(status="verified"),
    }
    fields.update(overrides)
    fields["review_id"] = review_id(
        reviewer_kind=fields["reviewer_kind"],  # type: ignore[arg-type]
        reviewer_ref=fields["reviewer_ref"],  # type: ignore[arg-type]
        lens=fields["lens"],  # type: ignore[arg-type]
        run_ref=fields["run_ref"],  # type: ignore[arg-type]
        finding_id=FINDING_ID,
    )
    return Review(**fields)  # type: ignore[arg-type]


def test_agent_review_requires_a_correspondence() -> None:
    with pytest.raises(ValidationError, match="correspondence"):
        _review(correspondence=None)


def test_non_agent_review_needs_no_correspondence() -> None:
    assert _review(reviewer_kind="human", lens=None, model=None, correspondence=None).correspondence is None


def test_violated_is_unstorable() -> None:
    with pytest.raises(ValidationError, match="violated"):
        _review(correspondence=Correspondence(status="violated", code="CITATION_UNSERVED"))


def test_unwired_is_storable() -> None:
    stored = _review(correspondence=Correspondence(status="unwired", code="NO_EXPOSURE"))
    assert stored.correspondence is not None
    assert stored.correspondence.status == "unwired"


def test_review_bounds_evidence() -> None:
    entry = LocationEvidence(type="location", path="a.txt")
    _review(evidence=(entry,) * MAX_EVIDENCE_ENTRIES)
    with pytest.raises(ValidationError):
        _review(evidence=(entry,) * (MAX_EVIDENCE_ENTRIES + 1))


def test_review_bounds_uncertainty() -> None:
    item = Uncertainty(field="severity", what="unsure", why="thin evidence")
    _review(uncertainty=(item,) * MAX_UNCERTAINTY_ENTRIES)
    with pytest.raises(ValidationError):
        _review(uncertainty=(item,) * (MAX_UNCERTAINTY_ENTRIES + 1))


def test_a_forged_nested_correspondence_is_refused() -> None:
    """Measured behaviour, asserted so it cannot regress silently.

    `Review` inherits `_Base.revalidate_instances="always"`, so a Correspondence
    built past its own validator is re-validated when the Review is constructed.
    """
    forged = Correspondence.model_construct(status="verified", code="SHOULD_BE_FORBIDDEN")
    with pytest.raises(ValidationError):
        _review(correspondence=forged)
```

Create `science/model/tests/test_audit_import_cycle.py`:

```python
"""Import-cycle guards.

Every assertion here runs in a FRESH interpreter. Written as an in-process import,
each would probe the safe direction -- and under pytest would be worse than useless,
since collection has almost certainly imported one side already and `sys.modules`
returns a hit without executing anything. A cycle test that shares a process with
its own test runner tests the runner's import order.
"""

from __future__ import annotations

import subprocess
import sys


def _fresh(code: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=False
    )


def test_evidence_broker_imports_in_a_fresh_interpreter() -> None:
    result = _fresh("import science_model.evidence_broker")
    assert result.returncode == 0, result.stderr


def test_correspondence_leaf_imports_in_a_fresh_interpreter() -> None:
    result = _fresh("import science_model.correspondence")
    assert result.returncode == 0, result.stderr
```

> **Do NOT add a third test here asserting the leaf loads no `audit` module.** That guard is plan
> 4b's and already exists, as `test_running_correspondence_leaf_does_not_load_audit` in
> `science/model/tests/test_correspondence.py:32`. It resolves the leaf's path from `__file__` of
> the *test* and hands it to `runpy.run_path` in a subprocess — never importing
> `science_model.correspondence` first. A version that imports the module to find its path (to get
> `m.__file__`) loads the whole eager package, `science_model.audit.*` included, and so **fails on a
> healthy tree**. Measured. Reuse the existing test; do not restate it.

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd science/model && uv run --frozen pytest tests/test_audit_review_contract.py tests/test_audit_import_cycle.py -q
```

Expected: the contract tests fail on `Review` having no `correspondence` field
(`ValidationError: Extra inputs are not permitted`); the two cycle tests pass already (the import
does not exist yet) — that is correct, they guard Step 3's change and are certified by mutation in
Step 5.

- [ ] **Step 3: Add the fields and invariants**

Add the import at the top of `record.py`, beside the existing `science_model.audit.evidence` import:

```python
from science_model.correspondence import Correspondence
```

Add three fields to `Review`, after `note`:

```python
    evidence: tuple[Evidence, ...] = Field(default=(), max_length=MAX_EVIDENCE_ENTRIES)
    uncertainty: tuple[Uncertainty, ...] = Field(default=(), max_length=MAX_UNCERTAINTY_ENTRIES)
    correspondence: Correspondence | None = None
```

Extend the existing `_agent_provenance` validator and add the second invariant:

```python
    @model_validator(mode="after")
    def _agent_provenance(self) -> Review:
        if self.reviewer_kind == "agent":
            if not self.lens:
                raise RecordError("an agent review requires a lens (design §4)")
            if not self.model:
                raise RecordError(
                    "an agent review requires model provenance, so the correlation "
                    "caution stays measurable (design §4)"
                )
            # Absent reads as clean. `unwired` is permitted; missing is not.
            if self.correspondence is None:
                raise RecordError(
                    "an agent review requires a correspondence; it may be 'unwired', "
                    "it may not be absent (design §4.2)"
                )
        # A MODEL invariant, not a gate: `append_review` refuses `violated` too, and
        # putting it here means every other write path inherits the refusal instead of
        # each gate having to remember it.
        if self.correspondence is not None and self.correspondence.status == "violated":
            raise RecordError(
                "a review with a 'violated' correspondence may not be stored (design §4.2)"
            )
        return self
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
cd science/model && uv run --frozen pytest tests/test_audit_review_contract.py tests/test_audit_import_cycle.py -q
```

Expected: all pass (16 in the contract file, 2 in the cycle file).

- [ ] **Step 5: Certify the two cycle mutations by hand**

This is the mutation check for the rows the design assigns to 4c. Do it now, while the code is fresh.

1. In `science_model/correspondence.py`, temporarily add `from science_model.audit.record import _Base`
   and make `Correspondence` inherit it. Run
   `cd science/model && uv run --frozen pytest tests/test_audit_import_cycle.py tests/test_correspondence.py -q`.
   **Expected: `test_correspondence_leaf_imports_in_a_fresh_interpreter` FAILS** (the new guard) **and
   `test_running_correspondence_leaf_does_not_load_audit` FAILS** (4b's existing guard). Revert.
2. Temporarily move the `Correspondence` class into `science_model/evidence_broker.py` and import it
   from there in `record.py`. Run the same file.
   **Expected: `test_evidence_broker_imports_in_a_fresh_interpreter` FAILS.** Revert.

If either mutation leaves the suite green, the guard is not guarding — stop and report it rather
than proceeding.

- [ ] **Step 6: Run the model suite and commit**

The model suite is in scope here: schema code changed.

```bash
cd science/model && uv run --frozen pytest -q
git add science/model/src/science_model/audit/record.py science/model/tests/
git commit -m "feat(audit): store a review's correspondence, evidence and uncertainty"
```

---

## Task 4: Eligibility — `counts_as_support` and `confirmation_count`

**Files:**
- Modify: `science/model/src/science_model/audit/record.py:559-561` (`confirmation_count`)
- Test: `science/model/tests/test_audit_review_contract.py` (extend)

**Interfaces:**
- Consumes: Task 3's `Review` fields.
- Produces: `Review.counts_as_support() -> bool` and a `confirmation_count` that delegates to it.
  Task 7's validate check calls `counts_as_support()` — **not** a second copy of the condition.

**Background.** The eligibility rule has **five independent conditions**: outcome, reviewer kind,
correspondence present, status `verified`, every entry a location. It moves onto `Review` because
the Task 7 check reports exactly the reviews it excludes; a second copy of the condition would be a
second thing to update when §5.3 gains a code, with a silent disagreement between the count and the
report as the failure mode.

`!= "agent"`, never `== "human"` — `ReviewerKind` has three members and the rule is that brokering is
required of the kind that can confabulate. `all`, never `any` — a review pairing one honest citation
with three prose exhibits is not a checked review.

- [ ] **Step 1: Write the failing tests**

Append to `science/model/tests/test_audit_review_contract.py`:

```python
from science_model.audit.evidence import TextEvidence as _Text

LOCATION = LocationEvidence(type="location", path="a.txt")
PROSE = _Text(type="text", text="looks right to me")
VERIFIED = Correspondence(status="verified")
UNWIRED = Correspondence(status="unwired", code="NO_EXPOSURE")


def test_a_checked_agent_confirmation_counts() -> None:
    assert _review(evidence=(LOCATION,), correspondence=VERIFIED).counts_as_support()


def test_outcome_must_be_confirms() -> None:
    for outcome in ("refutes", "abstains"):
        assert not _review(
            reviewer_kind="human", lens=None, model=None, correspondence=None, outcome=outcome
        ).counts_as_support()


def test_human_and_deterministic_count_regardless() -> None:
    for kind in ("human", "deterministic"):
        assert _review(
            reviewer_kind=kind, lens=None, model=None, correspondence=None
        ).counts_as_support()


def test_unwired_does_not_count_even_with_location_evidence() -> None:
    assert not _review(evidence=(LOCATION,), correspondence=UNWIRED).counts_as_support()


def test_a_vacuous_verified_confirmation_does_not_count() -> None:
    assert not _review(evidence=(), correspondence=VERIFIED).counts_as_support()


def test_one_location_mixed_with_prose_does_not_count() -> None:
    """`all`, not `any`: the single real citation must not launder the prose."""
    assert not _review(evidence=(LOCATION, PROSE), correspondence=VERIFIED).counts_as_support()


def test_prose_only_does_not_count() -> None:
    assert not _review(evidence=(PROSE,), correspondence=VERIFIED).counts_as_support()


def test_every_reviewer_kind_is_covered() -> None:
    """Asserted against the Literal, so a kind added later fails loudly here."""
    from typing import get_args

    from science_model.audit.record import ReviewerKind

    assert set(get_args(ReviewerKind)) == {"human", "agent", "deterministic"}
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd science/model && uv run --frozen pytest tests/test_audit_review_contract.py -q
```

Expected: the eight tests added above fail with `AttributeError: 'Review' object has no attribute
'counts_as_support'`; the sixteen from Tasks 2–3 still pass. Do **not** narrow this with
`-k counts_as_support` — no test name contains that substring, so the selection would be empty and
pytest would exit "no tests ran", which is not a red test.

- [ ] **Step 3: Add the method and rewrite the aggregate**

Add to `Review`, after the validator:

```python
    def counts_as_support(self) -> bool:
        """Whether THIS review counts as support, independent of the record holding it.

        An agent confirmation counts only when EVERYTHING it cited was mechanically
        checkable and was checked against what the agent was shown. `unwired` is not a
        weaker `verified`: a guard that cannot see must not report clean, and free
        support is what it would be. A vacuous `verified` -- a review that cited no path
        at all -- is not evidence of anything either. Prose belongs in `note`, which
        every review already has, and costs nothing there.

        Lifted out of `confirmation_count` because the `review.uncounted-confirmation`
        validate check reports exactly the reviews this excludes. One definition, two
        callers: a second copy would drift the moment §5.3 gains a code.
        """
        if self.outcome != "confirms":
            return False
        # `!= "agent"`, NOT `== "human"`: brokering is required of the kind that can
        # confabulate, and the exclusion list is one entry long.
        if self.reviewer_kind != "agent":
            return True
        return (
            self.correspondence is not None
            and self.correspondence.status == "verified"
            and bool(self.evidence)
            and all(entry.type == "location" for entry in self.evidence)
        )
```

Replace `confirmation_count` (currently `record.py:559-561`) with:

```python
    def confirmation_count(self) -> int:
        """Distinct confirming reviews that COUNT AS SUPPORT.

        NEVER a confidence, NEVER aggregated. Eligibility, not a threshold: spec 1
        reserves the confirmation threshold and promotion authority for spec 3.
        """
        return len({r.review_id for r in self.reviews if r.counts_as_support()})
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
cd science/model && uv run --frozen pytest tests/test_audit_review_contract.py -q
```

Expected: 24 passed.

- [ ] **Step 5: Check the one non-test consumer still behaves**

```bash
cd science && uv run --frozen pytest tests/test_findings_cli.py tests/test_findings_reporting.py -q
```

Expected: pass. `findings/cli.py:317` is unmodified; only what it receives changed. If a test here
fails, it is asserting a count over agent reviews and needs its fixture updated — report it rather
than weakening the rule.

- [ ] **Step 6: Commit**

```bash
git add science/model/src/science_model/audit/record.py science/model/tests/test_audit_review_contract.py
git commit -m "feat(audit): make agent confirmation eligibility a review-level predicate"
```

---

## Task 5: `append_review` — the non-agent path

**Files:**
- Create: `science/src/science_tool/findings/reviews.py`
- Test: `science/tests/test_findings_reviews.py` (create)

**Interfaces:**
- Consumes: `locked_store` (Task 1); `ReviewAttestation`, `ReviewSubmission` (Task 2); `Review`
  (Task 3).
- Produces:
  ```python
  def append_review(
      project_root: Path, finding_id: str, submission: ReviewSubmission,
      *, attestation: ReviewAttestation,
  ) -> Review: ...
  ```
  Every refusal is an `IngestError`, imported from `science_tool.findings.ingest` — this boundary
  defines **no error type of its own**. Task 6 extends the same function with the agent branch, and
  Tasks 6–7 consume the `conftest.py` fixtures added in Step 1.

**Background.** This task builds steps 0, 1, 6 and 7 of the design's executable order. The agent
branch (steps 2–5) is Task 6, and until then a `reviewer_kind == "agent"` attestation raises
`NotImplementedError` — a deliberate, visible hole that Task 6 fills, never a silent `None`.

Three mechanisms that the natural spelling gets wrong, all **measured**:

1. **Step 0's revalidation must dump first.** `ReviewSubmission.model_validate(submission)` does
   **not** recurse into a member built with `model_construct` — measured: a `LocationEvidence` whose
   `path` holds a `..` segment survives it unchanged. `revalidate_instances="always"` governs
   instances appearing *as fields of something being built*, which is not this case. Dumping to
   `mode="python"` and validating strictly is what forces every member back through its validators.
2. **Do not copy `_snapshot_report` literally.** It dumps in JSON mode, which renders
   `ReviewAttestation.at` as a string that `strict=True` then refuses. `mode="python"` keeps the
   `datetime`.
3. **`CaseStore` has no load-by-id.** Its API is `names()`, `has()`, `read()`, `write()`, `lock()`.
   The boundary scans, through the held descriptor, so the read is inside the lock.

And one ordering rule: **derive `review_id` only after the case scan matches.** `review_id` hashes
`finding_id` through `_components`, which rejects a NUL — so an unknown *and* NUL-bearing
`finding_id` would raise `RecordError` out of `review_id()` before the scan could return the
`IngestError` this boundary promises.

- [ ] **Step 1: Add the shared fixtures to `science/tests/conftest.py`**

`science/tests/` has **no `__init__.py`** — it is not a package, so Task 6 and Task 7 cannot
`import` helpers out of `test_findings_reviews.py`. Shared setup goes in `conftest.py` as fixtures,
which is how pytest shares across non-package test modules.

Append to `science/tests/conftest.py`:

```python
# --- plan 4c: review-append fixtures -----------------------------------------

REVIEW_AT = datetime(2026, 8, 2, tzinfo=UTC)
REVIEW_RUN_ID = "run:2026-07-25-lifecycle-agent-a3f1"


@pytest.fixture
def stored_case(tmp_path: Path):
    """A project holding exactly one stored case, ready to review.

    Built through `AuditFindingRecord`'s own constructor and written with `write_case`,
    so every derived value is the one the model computes. Read
    `science/tests/test_findings_storage.py` for the canonical construction and mirror
    it here rather than inventing a second shape.
    """
    from science_tool.findings.storage import write_case

    record = _build_audit_finding_record()   # see the note below
    write_case(tmp_path, record)
    return record


@pytest.fixture
def human_attestation():
    from science_model.audit import ReviewAttestation

    def build(**overrides):
        fields = {
            "reviewer_kind": "human",
            "reviewer_ref": "keith",
            "run_ref": "manual-review-2026-08-02",
            "at": REVIEW_AT,
        }
        fields.update(overrides)
        return ReviewAttestation(**fields)

    return build


@pytest.fixture
def agent_attestation():
    from science_model.audit import ReviewAttestation

    def build(**overrides):
        fields = {
            "reviewer_kind": "agent",
            "reviewer_ref": "lifecycle-agent",
            "lens": "rubric.md",
            "model": "test-model",
            "run_ref": REVIEW_RUN_ID,
            "at": REVIEW_AT,
        }
        fields.update(overrides)
        return ReviewAttestation(**fields)

    return build


@pytest.fixture
def case_files():
    """Snapshot the CANONICAL case files only.

    Not every file in the directory: entering `locked_store` creates `.ingest.lock`, so
    a whole-directory snapshot changes on a legitimately refused append and the
    "byte-identical" assertion would reject the correct implementation. Measured:
    ['case.md'] becomes ['.ingest.lock', 'case.md'].
    """

    def snapshot(project_root: Path) -> dict[str, bytes]:
        cases = project_root / "doc" / "audits" / "cases"
        return {p.name: p.read_bytes() for p in sorted(cases.glob("*.md"))}

    return snapshot
```

Everything shared is a **fixture**, deliberately. `science/tests/` is not a package, and while
pytest's `prepend` import mode usually leaves `conftest` importable by name, a test suite that
depends on that is depending on an import-mode default rather than on an interface.

> **Implementer note — `_build_audit_finding_record`.** `AuditFindingRecord` requires a real
> `finding_id`, a `rule_id`, at least one `Occurrence` with a matching `idempotency_key`, and a
> genesis `Transition`. That construction already exists in
> `science/tests/test_findings_storage.py`; lift it verbatim into `conftest.py` as
> `_build_audit_finding_record()`. Do **not** invent a second way to build a case — a fixture that
> disagrees with the storage tests' shape will pass here and fail in the suite.

- [ ] **Step 2: Write the failing tests**

Create `science/tests/test_findings_reviews.py`:

```python
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from science_model.audit import ReviewAttestation, ReviewSubmission
from science_model.audit.evidence import LocationEvidence

from science_tool.findings.ingest import IngestError
from science_tool.findings.reviews import append_review
from science_tool.findings.storage import load_cases

def test_a_human_review_is_stored_with_no_correspondence(
    tmp_path: Path, stored_case, human_attestation
) -> None:
    attestation = human_attestation()
    review = append_review(
        tmp_path, stored_case.finding_id,
        ReviewSubmission(outcome="confirms", note="looks right"),
        attestation=attestation,
    )
    assert review.correspondence is None
    assert review.at == attestation.at
    stored = load_cases(tmp_path)[0]
    assert [r.review_id for r in stored.reviews] == [review.review_id]


def test_a_human_review_needs_no_control_plane(
    tmp_path: Path, stored_case, human_attestation
) -> None:
    """No run lookup, no git, no control plane on the non-agent path."""
    assert not (tmp_path / "runs").exists()
    append_review(
        tmp_path, stored_case.finding_id,
        ReviewSubmission(outcome="confirms", note="n"),
        attestation=human_attestation(),
    )


def test_a_deterministic_review_is_stored(
    tmp_path: Path, stored_case, human_attestation
) -> None:
    review = append_review(
        tmp_path, stored_case.finding_id,
        ReviewSubmission(outcome="confirms", note="n"),
        attestation=human_attestation(reviewer_kind="deterministic", reviewer_ref="linter"),
    )
    assert review.reviewer_kind == "deterministic"


def test_the_stored_at_is_the_attested_instant(
    tmp_path: Path, stored_case, human_attestation
) -> None:
    past = datetime(2020, 1, 1, tzinfo=UTC)
    review = append_review(
        tmp_path, stored_case.finding_id,
        ReviewSubmission(outcome="confirms", note="n"),
        attestation=human_attestation(at=past),
    )
    assert review.at == past


def test_an_unknown_finding_id_is_refused(
    tmp_path: Path, stored_case, human_attestation, case_files
) -> None:
    before = case_files(tmp_path)
    with pytest.raises(IngestError):
        append_review(
            tmp_path, "f" * 64,
            ReviewSubmission(outcome="confirms", note="n"),
            attestation=human_attestation(),
        )
    assert case_files(tmp_path) == before


def test_an_unknown_nul_bearing_finding_id_is_an_ingest_error(
    tmp_path: Path, stored_case, human_attestation
) -> None:
    """`review_id` must be derived AFTER the scan: hashing a NUL-bearing id first
    would raise RecordError and break the boundary's own totality rule."""
    with pytest.raises(IngestError):
        append_review(
            tmp_path, "abc\0def",
            ReviewSubmission(outcome="confirms", note="n"),
            attestation=human_attestation(),
        )


def test_a_duplicate_review_is_refused_and_writes_nothing(
    tmp_path: Path, stored_case, human_attestation, case_files
) -> None:
    submission = ReviewSubmission(outcome="confirms", note="n")
    append_review(tmp_path, stored_case.finding_id, submission,
                  attestation=human_attestation())
    before = case_files(tmp_path)
    with pytest.raises(IngestError, match="already"):
        append_review(tmp_path, stored_case.finding_id, submission,
                      attestation=human_attestation())
    assert case_files(tmp_path) == before


def test_a_forged_submission_raises_ingest_error_not_validation_error(
    tmp_path: Path, stored_case, human_attestation
) -> None:
    """Step 0, on the path where it is observable without a run record.

    Skip step 0 and the forged member survives to `Review(...)`, which revalidates it
    (`_Base.revalidate_instances="always"`) and raises a ValidationError — a different
    exception type, leaking out of a boundary that promises IngestError. The
    "checker never ran" half of this row needs an agent attestation and lives in Task 6.
    """
    forged = ReviewSubmission.model_construct(
        outcome="confirms", note="n",
        evidence=(LocationEvidence.model_construct(
            type="location", path="a/../b.txt", pointer=None, line=None, span=None
        ),),
        uncertainty=(),
    )
    with pytest.raises(IngestError):
        append_review(tmp_path, stored_case.finding_id, forged,
                      attestation=human_attestation())


def test_step_zero_accepts_a_well_formed_pair(
    tmp_path: Path, stored_case, human_attestation
) -> None:
    """Guards the mode="json" mutation: a JSON dump renders the attestation's `at` as a
    string that strict validation then refuses, so a correct pair must still round-trip."""
    append_review(
        tmp_path, stored_case.finding_id,
        ReviewSubmission(outcome="confirms", note="n",
                         evidence=(LocationEvidence(type="location", path="a.txt"),)),
        attestation=human_attestation(),
    )
```

- [ ] **Step 3: Run the tests to verify they fail**

```bash
cd science && uv run --frozen pytest tests/test_findings_reviews.py -q
```

Expected: collection error — `ModuleNotFoundError: No module named 'science_tool.findings.reviews'`.

- [ ] **Step 4: Write `reviews.py`**

```python
"""The trusted review-append boundary (design §5.4).

The ONLY function that builds a stored `Review`. A review's correspondence is
COMPUTED here and cannot be supplied: `ReviewSubmission` has no field for it, and the
reviewer's identity comes from a `ReviewAttestation` the caller asserts rather than
from anything the producer says about itself.
"""

from __future__ import annotations

from pathlib import Path
from typing import TypeVar

from pydantic import ValidationError
from science_model.audit import (
    AuditFindingRecord,
    Review,
    ReviewAttestation,
    ReviewSubmission,
    review_id,
)

from science_tool.evidence_broker.correspondence import check_correspondence
from science_tool.findings.ingest import IngestError
from science_tool.findings.storage import CaseStorageError, locked_store

_Model = TypeVar("_Model", ReviewSubmission, ReviewAttestation)


def _revalidated(value: _Model) -> _Model:
    """Rebuild an argument through its own validators, recursively.

    `type(value).model_validate(value)` does NOT do this: passing an instance skips
    every member built with `model_construct`. `revalidate_instances="always"` governs
    instances appearing as FIELDS of something being built, which is not this case.
    Dumping first is what forces each member back through its own validators.

    `mode="python"` rather than `mode="json"`, because a JSON dump renders
    `ReviewAttestation.at` as a string and `strict=True` then refuses it.
    `warnings="error"` turns a forged field whose value does not match its declared
    type into a failure rather than a silently coerced dump.
    """
    try:
        dumped = value.model_dump(mode="python", warnings="error")
        return type(value).model_validate(dumped, strict=True)
    except (ValidationError, ValueError, TypeError) as exc:
        raise IngestError(f"{type(value).__name__} is not valid: {exc}") from exc


def append_review(
    project_root: Path,
    finding_id: str,
    submission: ReviewSubmission,
    *,
    attestation: ReviewAttestation,
) -> Review:
    """Append one review to a stored case, computing its correspondence.

    `attestation` is the reviewer identity and is the ONLY source of one. There is no
    `actor` parameter: `ingest_report` persists its actor in the genesis transition,
    this function writes no transition, and a validated-then-discarded argument would
    advertise a record of the writer that the stored record does not contain.
    """
    # Step 0 -- revalidate BOTH arguments before reading either.
    submission = _revalidated(submission)
    attestation = _revalidated(attestation)

    # Step 1 -- not an agent: nothing further runs.
    if attestation.reviewer_kind != "agent":
        correspondence = None
    else:
        raise NotImplementedError("the agent branch lands in plan 4c task 6")

    try:
        with locked_store(project_root) as store:
            # Step 6 -- find the case by SCANNING. `CaseStore` has no load-by-id, and
            # doing this through the held descriptor keeps the read inside the lock.
            record: AuditFindingRecord | None = None
            for name in store.names():
                candidate = store.read(name)
                if candidate.finding_id == finding_id:
                    record = candidate
                    break
            if record is None:
                raise IngestError(f"no stored case has finding_id {finding_id!r}")

            # Step 7 -- ONLY NOW derive the id, from the matched record's own
            # finding_id. Hashing the argument first would let a NUL-bearing unknown id
            # raise RecordError out of `review_id()` before this boundary could answer.
            identity = review_id(
                reviewer_kind=attestation.reviewer_kind,
                reviewer_ref=attestation.reviewer_ref,
                lens=attestation.lens,
                run_ref=attestation.run_ref,
                finding_id=record.finding_id,
            )
            if any(existing.review_id == identity for existing in record.reviews):
                raise IngestError(f"review {identity!r} is already stored on this case")

            review = Review(
                review_id=identity,
                reviewer_kind=attestation.reviewer_kind,
                reviewer_ref=attestation.reviewer_ref,
                lens=attestation.lens,
                model=attestation.model,
                run_ref=attestation.run_ref,
                at=attestation.at,
                outcome=submission.outcome,
                note=submission.note,
                evidence=submission.evidence,
                uncertainty=submission.uncertainty,
                correspondence=correspondence,
            )
            store.write(record.with_review(review))
            return review
    except CaseStorageError as exc:
        raise IngestError(str(exc)) from exc
```

Note the `except CaseStorageError` sits **outside** the `with`, so it catches storage faults without
spanning anything `locked_store` yields into.

- [ ] **Step 5: Run the tests to verify they pass**

```bash
cd science && uv run --frozen pytest tests/test_findings_reviews.py -q
```

Expected: all pass.

- [ ] **Step 6: Certify the lock conversions through this boundary**

Task 1 proved `locked_store` raises `CaseStorageError`. The design's rows are about what
`append_review` raises, and the translation between them is code this task wrote. Append to
`tests/test_findings_reviews.py`:

```python
def test_a_lock_acquisition_failure_surfaces_as_ingest_error(
    tmp_path: Path, stored_case, human_attestation, monkeypatch: pytest.MonkeyPatch
) -> None:
    import errno
    import fcntl

    monkeypatch.setattr(
        fcntl, "flock",
        lambda fd, op: (_ for _ in ()).throw(OSError(errno.ENOLCK, "no locks")),
    )
    with pytest.raises(IngestError):
        append_review(
            tmp_path, stored_case.finding_id,
            ReviewSubmission(outcome="confirms", note="n"),
            attestation=human_attestation(),
        )


def test_a_lock_release_failure_surfaces_as_ingest_error(
    tmp_path: Path, stored_case, human_attestation, monkeypatch: pytest.MonkeyPatch
) -> None:
    import errno
    import fcntl

    real = fcntl.flock

    def flaky(fd: int, op: int) -> None:
        if op == fcntl.LOCK_UN:
            raise OSError(errno.EIO, "release failed")
        real(fd, op)

    monkeypatch.setattr(fcntl, "flock", flaky)
    with pytest.raises(IngestError):
        append_review(
            tmp_path, stored_case.finding_id,
            ReviewSubmission(outcome="confirms", note="n"),
            attestation=human_attestation(),
        )


def test_a_lock_close_failure_surfaces_as_ingest_error(
    tmp_path: Path, stored_case, human_attestation, monkeypatch: pytest.MonkeyPatch
) -> None:
    import errno
    import os

    real = os.close
    state = {"armed": False}

    def flaky(fd: int) -> None:
        if state["armed"]:
            state["armed"] = False
            raise OSError(errno.EIO, "close failed")
        real(fd)

    monkeypatch.setattr(os, "close", flaky)
    state["armed"] = True
    with pytest.raises(IngestError):
        append_review(
            tmp_path, stored_case.finding_id,
            ReviewSubmission(outcome="confirms", note="n"),
            attestation=human_attestation(),
        )
```

All three use a **non-agent** attestation, so no run resolution or git precedes the lock and the
failure has exactly one possible source.

Run: `cd science && uv run --frozen pytest tests/test_findings_reviews.py -q`. Expected: all pass.

- [ ] **Step 7: Lint and commit**

```bash
cd science && uv run ruff check && uv run pyright
git add science/src/science_tool/findings/reviews.py science/tests/test_findings_reviews.py science/tests/conftest.py
git commit -m "feat(findings): add the review-append boundary for unbrokered reviewers"
```

---

## Task 6: `append_review` — the agent path

**Files:**
- Modify: `science/src/science_tool/findings/reviews.py`
- Test: `science/tests/test_findings_reviews.py` (extend)

**Interfaces:**
- Consumes: Task 5's `append_review` and its `conftest.py` fixtures.
- Produces: the completed boundary, plus the `unbrokered_run` and `sealed_agent_run` fixtures Task 7
  uses. No signature change to `append_review`.

**Background — the executable order for steps 2 through 5.**

2. `load_run_records(project_root)`, matching `record.id == attestation.run_ref`. **No match is an
   `IngestError`**, not a stored `unwired`: there is no record, so neither cross-check can run and no
   sealed exposure provenance exists, and a stored review's `run_ref` would point at nothing.
   `load_run_records` raises `RunRecordError` for a broken `runs/` — and **also raw `OSError`**,
   because `Path.exists()` swallows only the not-found family and `iterdir()` swallows nothing.
   Catch **both**.
3. The cross-checks, **before** the checker, because they refuse:
   - `attestation.reviewer_ref != run.agent` → `IngestError`
   - `attestation.model != run.model` → `IngestError`
   - **only when `run.evidence is not None`**: `attestation.lens != run.evidence.instrument.ref` →
     `IngestError`. Applying this unconditionally would demand an instrument in the one situation
     defined by its absence — an unbrokered run, which §5.3 requires be stored as `unwired`.
4. `check_correspondence(submission.evidence, run.evidence, repo=project_root)`. `repo` is
   `project_root` because `EvidenceSession` binds `_project_root = repo_root` and `start_run` passes
   `project_root`, so the exposure's commit is a commit of this repository by construction.
5. `status == "violated"` → `IngestError`.

- [ ] **Step 1: Add the run fixtures, then write the failing tests**

**First, add two more fixtures to `science/tests/conftest.py`.** The unbrokered one writes a bare run
record; the sealed one drives the real lifecycle.

```python
@pytest.fixture
def unbrokered_run(tmp_path: Path):
    """A finalized run record with `evidence=None` — a run that was never brokered.

    Read `science/tests/test_autonomy_validate_check.py` for the canonical
    `AutonomousRunRecord` field set and mirror it; write with
    `science_tool.autonomy.record_writer.write_run_record`.
    """
    from science_tool.autonomy.record_writer import write_run_record

    def build(*, agent: str = "lifecycle-agent", model: str = "test-model"):
        record = _build_run_record(id=REVIEW_RUN_ID, agent=agent, model=model, evidence=None)
        write_run_record(tmp_path, record)
        return record

    return build


@pytest.fixture
def sealed_agent_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """A project with a REAL sealed exposure, plus one stored case to review.

    The recipe is `test_autonomy_lifecycle.py::test_a_brokered_run_seals_its_exposure`
    (lines 484-499). Do not reinvent it — that module's `project` fixture commits
    `knowledge/graph.trig` on purpose, because `start_run` materializes and an
    uncommitted graph makes every dirty-tree assertion pass for the wrong reason. Its
    `pinned_toolkit` autouse fixture is also required: `assert_toolkit_matches` refuses a
    dirty judging toolkit, and this checkout is dirty exactly while 4c is being built.

    The run's instrument ref is `rubric.md` and its agent is that module's `AGENT`, so
    the `agent_attestation` fixture's `lens` and `reviewer_ref` must match both.
    """
    from science_tool.evidence_broker.policy import EvidenceOp, EvidenceRequest
    from science_tool.evidence_broker.session import Session
    from science_tool.findings.storage import write_case

    project = _seeded_git_project(tmp_path)          # mirrors lifecycle's `project`
    monkeypatch.setattr(_toolkit_module, "toolkit_is_clean", lambda root=None: True)
    baseline = _start_brokered_run(project, tmp_path, monkeypatch)
    Session(project, baseline.evidence).request(
        EvidenceRequest(op=EvidenceOp.READ, target="science.yaml")
    )
    outcome = _finish_run(project, baseline.evidence.journal_path.parent / "baseline.json")
    assert outcome.record is not None and outcome.record.evidence is not None

    record = _build_audit_finding_record()
    write_case(project, record)
    return project, record, baseline.evidence.journal_path.parent
```

> **Implementer note.** `_seeded_git_project`, `_start_brokered_run` and `_finish_run` are
> `_seed_science_project` + the `project` fixture, `_start_brokered`, and `_finish` from
> `science/tests/test_autonomy_lifecycle.py:50-140`. Lift them into `conftest.py` verbatim, renamed
> as above. They need `monkeypatch` (for `SCIENCE_CONTROL_PLANE` and the toolkit pin), which is why
> `sealed_agent_run` takes it. Note this fixture returns **its own** `project` root, not `tmp_path` —
> every test using it must pass that root to `append_review`.

Now append the tests to `science/tests/test_findings_reviews.py`:

```python
def test_an_agent_review_of_an_unbrokered_run_is_unwired(
    tmp_path: Path, stored_case, unbrokered_run, agent_attestation
) -> None:
    unbrokered_run()
    review = append_review(
        tmp_path, stored_case.finding_id,
        ReviewSubmission(outcome="confirms", note="n"),
        attestation=agent_attestation(),
    )
    assert review.correspondence is not None
    assert review.correspondence.status == "unwired"
    assert review.correspondence.code == "NO_EXPOSURE"


def test_the_lens_check_is_skipped_when_the_run_has_no_exposure(
    tmp_path: Path, stored_case, unbrokered_run, agent_attestation
) -> None:
    """Applied unconditionally, this would refuse the one case §5.3 defines as unwired."""
    unbrokered_run()
    review = append_review(
        tmp_path, stored_case.finding_id,
        ReviewSubmission(outcome="confirms", note="n"),
        attestation=agent_attestation(lens="something-else.md"),
    )
    assert review.correspondence is not None
    assert review.correspondence.status == "unwired"


def test_a_lens_mismatch_against_an_EXPOSED_run_is_refused(
    sealed_agent_run, agent_attestation
) -> None:
    """The other half of the conditional. Without a run that HAS an exposure, the lens
    comparison never executes and 'skip the lens cross-check' cannot be certified."""
    project, case, _control = sealed_agent_run
    with pytest.raises(IngestError, match="lens|instrument"):
        append_review(
            project, case.finding_id,
            ReviewSubmission(outcome="confirms", note="n"),
            attestation=agent_attestation(lens="not-the-instrument.md"),
        )


def test_a_reviewer_ref_mismatch_is_refused(
    tmp_path: Path, stored_case, unbrokered_run, agent_attestation
) -> None:
    """`model` AGREES, so this can only fail on reviewer_ref."""
    unbrokered_run(agent="lifecycle-agent", model="test-model")
    with pytest.raises(IngestError, match="reviewer_ref|agent"):
        append_review(
            tmp_path, stored_case.finding_id,
            ReviewSubmission(outcome="confirms", note="n"),
            attestation=agent_attestation(reviewer_ref="someone-else", model="test-model"),
        )


def test_a_model_mismatch_is_refused(
    tmp_path: Path, stored_case, unbrokered_run, agent_attestation
) -> None:
    """`reviewer_ref` AGREES, so this can only fail on model."""
    unbrokered_run(agent="lifecycle-agent", model="test-model")
    with pytest.raises(IngestError, match="model"):
        append_review(
            tmp_path, stored_case.finding_id,
            ReviewSubmission(outcome="confirms", note="n"),
            attestation=agent_attestation(
                reviewer_ref="lifecycle-agent", model="a-different-model"
            ),
        )


def test_a_run_ref_with_no_record_is_refused_and_writes_nothing(
    tmp_path: Path, stored_case, agent_attestation, case_files
) -> None:
    before = case_files(tmp_path)
    with pytest.raises(IngestError):
        append_review(
            tmp_path, stored_case.finding_id,
            ReviewSubmission(outcome="confirms", note="n"),
            attestation=agent_attestation(run_ref="run:2020-01-01-nobody-0000"),
        )
    assert case_files(tmp_path) == before


def test_a_symlinked_runs_directory_is_refused(
    tmp_path: Path, stored_case, agent_attestation
) -> None:
    elsewhere = tmp_path.parent / "elsewhere"
    elsewhere.mkdir()
    (tmp_path / "runs").symlink_to(elsewhere)
    with pytest.raises(IngestError):
        append_review(
            tmp_path, stored_case.finding_id,
            ReviewSubmission(outcome="confirms", note="n"),
            attestation=agent_attestation(),
        )


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores directory permissions")
def test_an_unreadable_runs_directory_is_an_ingest_error(
    tmp_path: Path, stored_case, agent_attestation
) -> None:
    """`load_run_records` emits a raw OSError here, not RunRecordError -- catching only
    RunRecordError leaks a PermissionError out of a boundary promising IngestError."""
    runs = tmp_path / "runs"
    runs.mkdir()
    runs.chmod(0o000)
    try:
        with pytest.raises(IngestError):
            append_review(
                tmp_path, stored_case.finding_id,
                ReviewSubmission(outcome="confirms", note="n"),
                attestation=agent_attestation(),
            )
    finally:
        runs.chmod(0o755)


def test_a_forged_attestation_is_refused_before_the_run_lookup(
    tmp_path: Path, stored_case, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Step 0 for the attestation. Without it, `lens=None` is refused later by the
    cross-check or by Review construction -- same IngestError, wrong reason. The
    load-bearing assertion is that the run lookup never ran."""
    monkeypatch.setattr(
        "science_tool.findings.reviews.load_run_records",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("run lookup ran")),
    )
    forged = ReviewAttestation.model_construct(
        reviewer_kind="agent", reviewer_ref="lifecycle-agent", lens=None,
        model="test-model", run_ref="run:2026-07-25-lifecycle-agent-a3f1",
        at=datetime(2026, 8, 2, tzinfo=UTC),
    )
    with pytest.raises(IngestError):
        append_review(
            tmp_path, stored_case.finding_id,
            ReviewSubmission(outcome="confirms", note="n"),
            attestation=forged,
        )


def test_a_forged_submission_is_refused_before_the_checker(
    tmp_path: Path, stored_case, unbrokered_run, agent_attestation,
    monkeypatch: pytest.MonkeyPatch
) -> None:
    """The other half of the step-0 submission row, on the AGENT path.

    A human attestation would make "the checker never ran" true regardless of step 0,
    since the non-agent branch never calls it -- the assertion would hold for a reason
    unrelated to the guard.
    """
    unbrokered_run()
    monkeypatch.setattr(
        "science_tool.findings.reviews.check_correspondence",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("checker ran")),
    )
    forged = ReviewSubmission.model_construct(
        outcome="confirms", note="n",
        evidence=(LocationEvidence.model_construct(
            type="location", path="a/../b.txt", pointer=None, line=None, span=None
        ),),
        uncertainty=(),
    )
    with pytest.raises(IngestError):
        append_review(tmp_path, stored_case.finding_id, forged,
                      attestation=agent_attestation())


def test_the_cross_checks_run_before_the_checker(
    tmp_path: Path, stored_case, unbrokered_run, agent_attestation,
    monkeypatch: pytest.MonkeyPatch
) -> None:
    """Against an unreachable repository the checker RETURNS unwired rather than
    raising, so both orders end in the same IngestError and the order is invisible.
    It is observable only where the checker would raise."""
    from science_tool.evidence_broker.serve import ServeError

    unbrokered_run(agent="lifecycle-agent", model="test-model")
    monkeypatch.setattr(
        "science_tool.findings.reviews.check_correspondence",
        lambda *a, **k: (_ for _ in ()).throw(ServeError("replay exploded")),
    )
    with pytest.raises(IngestError, match="model"):
        append_review(
            tmp_path, stored_case.finding_id,
            ReviewSubmission(outcome="confirms", note="n"),
            attestation=agent_attestation(model="a-different-model"),
        )
```

Add `import os` to the test module's imports for the `skipif`.

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd science && uv run --frozen pytest tests/test_findings_reviews.py -q -k agent
```

Expected: `NotImplementedError: the agent branch lands in plan 4c task 6`.

- [ ] **Step 3: Replace the `NotImplementedError` branch**

Add to the imports. `RunRecordError` is defined in `science_model/autonomous_runs.py:37` and merely
imported into `science_tool.graph.autonomous_runs` — take it from its home, not from the module that
happens to re-expose it:

```python
from science_model.autonomous_runs import RunRecordError

from science_tool.graph.autonomous_runs import load_run_records
```

Replace `raise NotImplementedError(...)` with:

```python
    else:
        try:
            records = load_run_records(project_root)
        except (RunRecordError, OSError) as exc:
            # BOTH: `Path.exists()` swallows only the not-found family and `iterdir()`
            # swallows nothing, so an unreadable runs/ arrives as a raw OSError from a
            # function whose documented channel is RunRecordError.
            raise IngestError(f"could not resolve {attestation.run_ref!r}: {exc}") from exc
        run = next((r for r in records if r.id == attestation.run_ref), None)
        if run is None:
            # NOT a stored `unwired`: with no record, neither cross-check can run and no
            # sealed exposure provenance exists, so the stored review's run_ref would
            # point at nothing. §6 already calls the lost-journal branch retryable.
            raise IngestError(f"no run record has id {attestation.run_ref!r}")

        # The cross-checks run BEFORE the checker: they refuse, so there is no reason to
        # replay git for a review that will be rejected.
        if attestation.reviewer_ref != run.agent:
            raise IngestError(
                f"attested reviewer_ref {attestation.reviewer_ref!r} is not the run's "
                f"agent {run.agent!r}"
            )
        if attestation.model != run.model:
            raise IngestError(
                f"attested model {attestation.model!r} is not the run's model {run.model!r}"
            )
        # Conditional: an unbrokered run has no instrument, and §5.3 requires exactly
        # that case be stored as `unwired`.
        if run.evidence is not None and attestation.lens != run.evidence.instrument.ref:
            raise IngestError(
                f"attested lens {attestation.lens!r} is not the exposure's instrument "
                f"{run.evidence.instrument.ref!r}"
            )

        correspondence = check_correspondence(
            submission.evidence, run.evidence, repo=project_root
        )
        if correspondence.status == "violated":
            raise IngestError(
                f"review does not correspond to what the run was shown: "
                f"{correspondence.code} — {correspondence.reason}"
            )
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
cd science && uv run --frozen pytest tests/test_findings_reviews.py -q
```

Expected: all pass.

- [ ] **Step 5: Add the sealed-run end-to-end guard**

This is §5.4's stated regression test — the one that catches a boundary working only on the path
nobody takes. It uses the `sealed_agent_run` fixture from Step 1. The served request in that fixture
is `READ science.yaml`, so that is the one path a citation can correspond to.

```python
def test_a_sealed_run_replays_with_the_control_plane_deleted(
    sealed_agent_run, agent_attestation
) -> None:
    """Revision 5's version of this guard passed while production still resolved a
    baseline. `append_review` resolves the run record and NOTHING else."""
    import shutil

    project, case, control_plane_dir = sealed_agent_run
    shutil.rmtree(control_plane_dir)
    review = append_review(
        project, case.finding_id,
        ReviewSubmission(outcome="confirms", note="n",
                         evidence=(LocationEvidence(type="location", path="science.yaml"),)),
        attestation=agent_attestation(),
    )
    assert review.correspondence is not None
    assert review.correspondence.status == "verified"


def test_a_citation_the_run_was_never_shown_is_refused(
    sealed_agent_run, agent_attestation, case_files
) -> None:
    project, case, _control = sealed_agent_run
    before = case_files(project)
    with pytest.raises(IngestError, match="CITATION_UNSERVED"):
        append_review(
            project, case.finding_id,
            ReviewSubmission(outcome="confirms", note="n",
                             evidence=(LocationEvidence(type="location", path="never-read.txt"),)),
            attestation=agent_attestation(),
        )
    assert case_files(project) == before


def test_a_verified_agent_confirmation_counts(sealed_agent_run, agent_attestation) -> None:
    """End-to-end: the whole point of the slice, asserted through the real path."""
    project, case, _control = sealed_agent_run
    append_review(
        project, case.finding_id,
        ReviewSubmission(outcome="confirms", note="n",
                         evidence=(LocationEvidence(type="location", path="science.yaml"),)),
        attestation=agent_attestation(),
    )
    assert load_cases(project)[0].confirmation_count() == 1
```

- [ ] **Step 6: Run, lint, commit**

```bash
cd science && uv run --frozen pytest tests/test_findings_reviews.py -q && uv run ruff check && uv run pyright
git add science/src/science_tool/findings/reviews.py science/tests/test_findings_reviews.py
git commit -m "feat(findings): broker agent reviews at the append boundary"
```

---

## Task 7: The `review.uncounted-confirmation` check

**Files:**
- Create: `science/src/science_tool/validate/checks/review_confirmations.py`
- Modify: `science/src/science_tool/validate/checks/__init__.py` (the module-name tuple ending at
  line ~105)
- Modify: `science/src/science_tool/validate/findings.py:100-105` (`_POLICY_INFO_RULE_IDS`)
- Test: `science/tests/test_review_confirmations_check.py` (create)

**Interfaces:**
- Consumes: `Review.counts_as_support()` (Task 4); `append_review` (Task 6) for fixtures.
- Produces: `check_review_confirmations(ctx: ValidateContext) -> Iterator[CheckObservation]` and
  `RULE_UNCOUNTED_CONFIRMATION`.

**Background.** §4.2.1 excludes agent confirmations two ways and only one was ever visible. A review
whose correspondence is `verified` while its evidence is empty or mixed with `TextEvidence` is
stored, renders as a confirming review, is excluded from `confirmation_count`, and is reported by
nothing — §4.2.1's own "cheapest possible fabrication".

**The rule id MUST be added to `_POLICY_INFO_RULE_IDS`.** Otherwise `validation_observation`
(`validate/findings.py:113-127`) degrades every `info` result to a bare `ValidationNotice`, which
carries no rule, no qualifiers, no fingerprint and therefore no suppression.

Read `science/src/science_tool/validate/checks/correspondence_drift.py` for the `FindingSection` /
`FindingRule` / `@Check` pattern, and `science/tests/test_autonomy_validate_check.py` for the
`ValidateContext` construction a check test needs.

- [ ] **Step 1: Write the failing tests**

Create `science/tests/test_review_confirmations_check.py`, using the same `conftest.py` fixtures
Task 5 added — `stored_case`, `human_attestation`, `agent_attestation`, `unbrokered_run`,
`sealed_agent_run`. They are fixtures precisely so this file needs no import from
`test_findings_reviews.py`; `science/tests/` is not a package and such an import would not resolve.

```python
from __future__ import annotations

from pathlib import Path

from science_model.audit.evidence import LocationEvidence, TextEvidence
from science_model.audit import ReviewSubmission

from science_tool.findings.reviews import append_review
from science_tool.findings.storage import case_path
from science_tool.validate.checks.review_confirmations import (
    RULE_UNCOUNTED_CONFIRMATION,
    check_review_confirmations,
)
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Severity


def _ctx(project_root: Path) -> ValidateContext:
    return ValidateContext(
        project_root=project_root,
        doc_dir=project_root / "doc",
        specs_dir=project_root / "entities" / "specs",
        manifest={},
        strict=False,
        verbose=False,
    )


def test_an_unwired_agent_confirmation_is_reported(
    tmp_path: Path, stored_case, unbrokered_run, agent_attestation
) -> None:
    unbrokered_run()
    append_review(tmp_path, stored_case.finding_id,
                  ReviewSubmission(outcome="confirms", note="n"),
                  attestation=agent_attestation())
    observations = list(check_review_confirmations(_ctx(tmp_path)))
    assert len(observations) == 1
    assert observations[0].severity == Severity.INFO
    assert "NO_EXPOSURE" in observations[0].message
    assert observations[0].path == case_path(tmp_path, stored_case)


def test_a_vacuously_verified_agent_confirmation_is_reported(
    sealed_agent_run, agent_attestation
) -> None:
    """The case revision 26's `review.correspondence-unwired` could not see."""
    project, case, _control = sealed_agent_run
    append_review(project, case.finding_id,
                  ReviewSubmission(outcome="confirms", note="n"),
                  attestation=agent_attestation())
    observations = list(check_review_confirmations(_ctx(project)))
    assert len(observations) == 1
    assert "no location evidence" in observations[0].message


def test_a_mixed_evidence_confirmation_is_reported(
    sealed_agent_run, agent_attestation
) -> None:
    project, case, _control = sealed_agent_run
    append_review(
        project, case.finding_id,
        ReviewSubmission(outcome="confirms", note="n", evidence=(
            LocationEvidence(type="location", path="science.yaml"),
            TextEvidence(type="text", text="p"),
        )),
        attestation=agent_attestation(),
    )
    observations = list(check_review_confirmations(_ctx(project)))
    assert len(observations) == 1
    assert "non-location" in observations[0].message


def test_a_counted_agent_confirmation_is_not_reported(
    sealed_agent_run, agent_attestation
) -> None:
    project, case, _control = sealed_agent_run
    append_review(
        project, case.finding_id,
        ReviewSubmission(outcome="confirms", note="n",
                         evidence=(LocationEvidence(type="location", path="science.yaml"),)),
        attestation=agent_attestation(),
    )
    assert list(check_review_confirmations(_ctx(project))) == []


def test_human_and_deterministic_reviews_are_not_reported(
    tmp_path: Path, stored_case, human_attestation
) -> None:
    append_review(tmp_path, stored_case.finding_id,
                  ReviewSubmission(outcome="confirms", note="n"),
                  attestation=human_attestation())
    append_review(tmp_path, stored_case.finding_id,
                  ReviewSubmission(outcome="confirms", note="n"),
                  attestation=human_attestation(reviewer_kind="deterministic",
                                                reviewer_ref="linter"))
    assert list(check_review_confirmations(_ctx(tmp_path))) == []


def test_a_non_confirming_agent_review_is_not_reported(
    tmp_path: Path, stored_case, unbrokered_run, agent_attestation
) -> None:
    unbrokered_run()
    append_review(tmp_path, stored_case.finding_id,
                  ReviewSubmission(outcome="abstains", note="n"),
                  attestation=agent_attestation())
    assert list(check_review_confirmations(_ctx(tmp_path))) == []


def test_the_finding_keeps_its_rule_and_fingerprint(tmp_path: Path) -> None:
    """Fails if the rule id is missing from `_POLICY_INFO_RULE_IDS`, which degrades
    every info result to a bare ValidationNotice with no suppression."""
    from science_tool.validate.findings import is_policy_info_rule

    assert is_policy_info_rule(RULE_UNCOUNTED_CONFIRMATION)


def test_no_cases_yields_nothing(tmp_path: Path) -> None:
    (tmp_path / "doc").mkdir()
    assert list(check_review_confirmations(_ctx(tmp_path))) == []
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd science && uv run --frozen pytest tests/test_review_confirmations_check.py -q
```

Expected: `ModuleNotFoundError: No module named
'science_tool.validate.checks.review_confirmations'`.

- [ ] **Step 3: Write the check module**

```python
"""Report agent confirmations that do not count as support (design §4.2.1, §5.4).

Non-gating and INFO. §4.2.1 excludes an agent confirmation two ways -- an `unwired`
correspondence, and a `verified` one whose evidence is empty or mixed with prose -- and
only the first was ever visible. A reader seeing three confirming reviews above
`confirmations: 2` deserves an account of the difference.

The predicate is `Review.counts_as_support()` itself, NOT a list of the correspondence
codes this module knows about: a roster would have a hole the day §5.3 gains a code.
"""

from __future__ import annotations

from collections.abc import Iterator

from pydantic import BaseModel, ConfigDict
from science_model.audit import FindingRule, FindingSection

from science_tool.findings.storage import case_path, load_cases
from science_tool.validate.checks import Check, CheckObservation
from science_tool.validate.context import ValidateContext
from science_tool.validate.findings import validation_observation
from science_tool.validate.result import Severity

SECTION = FindingSection(
    id="review-confirmations",
    title="uncounted agent confirmations",
    section_order=161,
)


class UncountedConfirmationQualifiers(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    review_id: str
    reason: str


RULE_UNCOUNTED_CONFIRMATION = FindingRule(
    id="review.uncounted-confirmation",
    severities=frozenset({"info"}),
    subject_types=frozenset({"path"}),
    qualifier_schema=UncountedConfirmationQualifiers,
    identity_qualifiers=("review_id",),
    title="Agent confirmation that does not count as support",
    section=SECTION.id,
    display_order=16101,
)


def _reason(review: object) -> str:
    """Why this confirmation did not count. Derived, never authored."""
    correspondence = getattr(review, "correspondence", None)
    if correspondence is None:
        return "no correspondence was recorded"
    if correspondence.status != "verified":
        return f"correspondence is {correspondence.status} ({correspondence.code})"
    if not review.evidence:  # type: ignore[attr-defined]
        return "no location evidence"
    return "evidence mixes non-location entries"


@Check(
    section=SECTION,
    order=206,
    producer_id="validate.review-confirmations",
    rules=(RULE_UNCOUNTED_CONFIRMATION,),
)
def check_review_confirmations(ctx: ValidateContext) -> Iterator[CheckObservation]:
    for record in load_cases(ctx.project_root):
        for review in record.reviews:
            if review.reviewer_kind != "agent" or review.outcome != "confirms":
                continue
            if review.counts_as_support():
                continue
            reason = _reason(review)
            yield validation_observation(
                severity=Severity.INFO,
                # The individual case FILE, not the directory (design §5.4). A finding
                # whose subject is the store as a whole cannot be located, and every
                # finding on this rule would share one subject.
                path=case_path(ctx.project_root, record),
                line=None,
                message=(
                    f"agent confirmation {review.review_id} on {record.rule_id} does not "
                    f"count as support: {reason}"
                ),
                rule=RULE_UNCOUNTED_CONFIRMATION,
                task=None,
                qualifiers={"review_id": review.review_id, "reason": reason},
            )
```

> **Implementer note.** `validation_observation`'s exact keyword set is at
> `validate/findings.py:113-127` — check it and match, including whether `subject` is required for a
> `path` subject type. `load_cases` propagates read failures; do not catch them, the validation
> runner already converts them into `validate.check-error`.

- [ ] **Step 4: Register the check and the policy-info rule**

In `validate/checks/__init__.py`, add `"review_confirmations",` to the module-name tuple after
`"correspondence_drift",`.

In `validate/findings.py`, extend `_POLICY_INFO_RULE_IDS`:

```python
_POLICY_INFO_RULE_IDS = frozenset(
    {
        "prose-lints.config",
        "prose-lints.advisory",
        "review.uncounted-confirmation",
    }
)
```

- [ ] **Step 5: Run the tests to verify they pass**

```bash
cd science && uv run --frozen pytest tests/test_review_confirmations_check.py -q
```

Expected: 8 passed.

- [ ] **Step 6: Check registration did not disturb the validate surface**

```bash
cd science && uv run --frozen pytest tests/test_findings_producer_namespaces.py tests/test_findings_registry.py -q
```

Expected: pass. A new producer id and section may need registering in a fixture — if one of these
fails asking for the new id, add it there; do not remove the check from the registry.

- [ ] **Step 7: Lint and commit**

```bash
cd science && uv run ruff check && uv run pyright
git add science/src/science_tool/validate/ science/tests/test_review_confirmations_check.py
git commit -m "feat(validate): report agent confirmations that do not count as support"
```

---

## Task 8: Certify every §7 mutation row

**Files:** no production changes expected. Add tests where a row has no test that can fail.

**Background.** The design's §7 carries **38 rows tagged `4c`**. A row is certified when you break
what it guards and watch a **named** test fail. This is not a review pass — it is a mechanical sweep,
and it has repeatedly found rows that certified nothing.

Three traps this design has hit, all live here:

1. **The mutant reaches the same outcome by a longer road.** A forged `LocationEvidence` that
   survives step 0 cites a path the served map cannot cover, so the checker returns `violated` and
   step 5 raises `IngestError` anyway. Rows about *where* a refusal happens must assert the later
   stage never ran — `check_correspondence` not called, `load_run_records` not called.
2. **The fixture proves a neighbour's guard.** `case_store` converts `PathSafetyError` across its own
   `yield`, so any lock fixture built on an unsafe path certifies `case_store`, not `locked_store`.
   The lock rows reach `flock` and `close` by injection.
3. **The mutation is not distinct from the original.** "Give the check its own predicate" is
   satisfied by a faithful copy. The row names a concrete wrong implementation — *report only
   non-`verified` correspondence*.

**Rows that must NOT be added** (the design records why): treating a broken `runs/` as a missing run,
since both refuse identically; "give the check its own predicate instead of
`counts_as_support()`"; and raising `CaseStorageError` rather than `IngestError` on a case-scan
no-match, since the enclosing translation makes their public behaviour identical.

- [ ] **Step 1: Confirm the row list still has 38 entries**

From the repository root:

```bash
grep -c "^| 4c |" docs/plans/2026-07-30-agent-evidence-broker-design.md
```

Expected: `38`. If the count differs, the design moved and this table is stale — reconcile before
continuing.

- [ ] **Step 2: Certify each row against its named test**

Every row already has a test written in Tasks 1–7. For each: apply the mutation to the production
code, run the **named** node, confirm it FAILS, revert, confirm green.

Model-package nodes run from `science/model/`, CLI nodes from `science/`.

| # | Mutation | Test node that must fail |
|---|---|---|
| 1 | Import `Correspondence` from `evidence_broker.py` | `test_audit_import_cycle.py::test_evidence_broker_imports_in_a_fresh_interpreter` |
| 2 | Leaf imports `_Base` from `audit.subjects` | `test_audit_import_cycle.py::test_correspondence_leaf_imports_in_a_fresh_interpreter` **and** `test_correspondence.py::test_running_correspondence_leaf_does_not_load_audit` |
| 3 | Re-add `reviewer_kind` to `ReviewSubmission` | `test_audit_review_contract.py::test_submission_cannot_express_a_reviewer_kind` |
| 4 | Skip the `reviewer_ref` cross-check | `test_findings_reviews.py::test_a_reviewer_ref_mismatch_is_refused` |
| 5 | Skip the `model` cross-check | `test_findings_reviews.py::test_a_model_mismatch_is_refused` |
| 6 | Skip the lens cross-check | `test_findings_reviews.py::test_a_lens_mismatch_against_an_EXPOSED_run_is_refused` |
| 7 | Apply the lens cross-check unconditionally | `test_findings_reviews.py::test_the_lens_check_is_skipped_when_the_run_has_no_exposure` |
| 8 | Store an unresolvable `run_ref` as a correspondence | `test_findings_reviews.py::test_a_run_ref_with_no_record_is_refused_and_writes_nothing` |
| 9 | Resolve a baseline / open the control plane | `test_findings_reviews.py::test_a_sealed_run_replays_with_the_control_plane_deleted` |
| 10 | Stamp `Review.at` from a clock | `test_findings_reviews.py::test_the_stored_at_is_the_attested_instant` |
| 11 | Drop the stored-`violated` invariant | `test_audit_review_contract.py::test_violated_is_unstorable` |
| 12 | Drop agent-requires-`correspondence` | `test_audit_review_contract.py::test_agent_review_requires_a_correspondence` |
| 13 | Drop `max_length` from `ReviewSubmission.uncertainty` | `test_audit_review_contract.py::test_submission_bounds_uncertainty` |
| 14 | Drop `max_length` from `Review.uncertainty` | `test_audit_review_contract.py::test_review_bounds_uncertainty` |
| 15 | `== "human"` instead of `!= "agent"` | `test_audit_review_contract.py::test_human_and_deterministic_count_regardless` |
| 16 | Drop the `status == "verified"` clause | `test_audit_review_contract.py::test_unwired_does_not_count_even_with_location_evidence` |
| 17 | Drop the non-empty `evidence` clause | `test_audit_review_contract.py::test_a_vacuous_verified_confirmation_does_not_count` |
| 18 | `any` instead of `all` | `test_audit_review_contract.py::test_one_location_mixed_with_prose_does_not_count` |
| 19 | Check reports only non-`verified` correspondence | `test_review_confirmations_check.py::test_a_vacuously_verified_agent_confirmation_is_reported` |
| 20 | Omit the rule from `_POLICY_INFO_RULE_IDS` | `test_review_confirmations_check.py::test_the_finding_keeps_its_rule_and_fingerprint` |
| 21 | Drop the `outcome == "confirms"` clause | `test_audit_review_contract.py::test_outcome_must_be_confirms` |
| 22 | Drop `max_length` from `ReviewSubmission.evidence` | `test_audit_review_contract.py::test_submission_bounds_evidence` |
| 23 | Drop `max_length` from `Review.evidence` | `test_audit_review_contract.py::test_review_bounds_evidence` |
| 24 | Drop the attestation's agent-requires-`lens` | `test_audit_review_contract.py::test_agent_attestation_requires_a_lens` |
| 25 | Drop the attestation's agent-requires-`model` | `test_audit_review_contract.py::test_agent_attestation_requires_a_model` |
| 26 | `ReviewSubmission` accepts a `correspondence` key | `test_audit_review_contract.py::test_submission_cannot_express_a_correspondence` |
| 27 | Skip step 0 for `submission` | `test_findings_reviews.py::test_a_forged_submission_raises_ingest_error_not_validation_error` **and** `::test_a_forged_submission_is_refused_before_the_checker` |
| 28 | Skip step 0 for `attestation` | `test_findings_reviews.py::test_a_forged_attestation_is_refused_before_the_run_lookup` |
| 29 | Step 0 as `T.model_validate(arg)`, no dump | `test_findings_reviews.py::test_a_forged_submission_is_refused_before_the_checker` |
| 30 | Dump in `mode="json"` at step 0 | `test_findings_reviews.py::test_step_zero_accepts_a_well_formed_pair` |
| 31 | Run `check_correspondence` before the cross-checks | `test_findings_reviews.py::test_the_cross_checks_run_before_the_checker` |
| 32 | Rely on `_validate_reviews` for the duplicate | `test_findings_reviews.py::test_a_duplicate_review_is_refused_and_writes_nothing` |
| 33 | Catch only `RunRecordError` | `test_findings_reviews.py::test_an_unreadable_runs_directory_is_an_ingest_error` |
| 34 | `OSError` from `flock` acquisition escapes | `test_findings_locked_store.py::test_flock_acquisition_failure_becomes_case_storage_error` **and** `test_findings_reviews.py::test_a_lock_acquisition_failure_surfaces_as_ingest_error` |
| 35 | `OSError` from `flock` release escapes | `test_findings_locked_store.py::test_flock_release_failure_becomes_case_storage_error` **and** `test_findings_reviews.py::test_a_lock_release_failure_surfaces_as_ingest_error` |
| 36 | `OSError` from `os.close` escapes | `test_findings_locked_store.py::test_close_failure_becomes_case_storage_error` **and** `test_findings_reviews.py::test_a_lock_close_failure_surfaces_as_ingest_error` |
| 37 | Widen `locked_store`'s `try` across its `yield` | `test_findings_locked_store.py::test_body_exception_is_not_relabelled` |
| 38 | Derive `review_id` before the case scan | `test_findings_reviews.py::test_an_unknown_nul_bearing_finding_id_is_an_ingest_error` |

**Rows 34–36 are certified twice on purpose.** The `locked_store` node proves the conversion to
`CaseStorageError`; the `append_review` node proves the translation to `IngestError`, which is
different code in a different task. A row satisfied only at the storage layer says nothing about
what the boundary raises.

- [ ] **Step 3: Record and commit the ledger**

Write the 38-row table above to `docs/plans/2026-08-02-plan-4c-mutation-ledger.md` with a fourth column
holding the observed result (`FAILED as required` / an explanation).

A row whose mutation leaves everything green is a **defect in the guard, not a formality**. Stop,
work out which fixture cannot distinguish the mutant, and either fix the fixture or — if nothing can
distinguish it — move the row to the design's "must not be added" list with the reasoning. Do not
weaken a test to make a row pass.

```bash
git add docs/plans/2026-08-02-plan-4c-mutation-ledger.md
git commit -m "test(evidence-broker): certify plan 4c's mutation rows"
```

- [ ] **Step 4: Run both full suites**

Shared model/schema code changed and this prepares the slice for integration, so the full-suite
trigger applies. **The top-level agent owns this run** and must pass an explicit long timeout; a
subagent that yields waiting on it will not reliably resume. Never run two suites concurrently in
one worktree.

```bash
cd science/model && uv run --frozen pytest -q
```

then, separately, with `timeout: 900000`:

```bash
cd science && uv run --frozen pytest -q
```

Expected: both green.

- [ ] **Step 5: Final lint and types**

```bash
cd science && uv run ruff check && uv run pyright
```

- [ ] **Step 6: Update the design's status table**

In `docs/plans/2026-07-30-agent-evidence-broker-design.md`, change plan 4c's State cell from
`designed at revision 26, settled against the merged tree at revisions 34–36, not implemented` to
`merged at <commit>` once the branch lands. Commit with the merge, not before.

---

## Self-Review

**Spec coverage.** §4.2's types → Tasks 2–3. §4.2's two stored invariants → Task 3. §4.2.1 →
Task 4. §5.4's executable order → Tasks 5–6 (steps 0–1, 6–7 in Task 5; steps 2–5 in Task 6). §5.4's
`locked_store` extraction → Task 1. §5.4's two backstops → Task 3 (model invariant) and Task 7
(validate check). §7's 39 rows → Task 8, with the certifying tests written in Tasks 1–7. §2.2's file
boundary → Global Constraints.

**Known gaps, stated rather than hidden.** Three places send the implementer to read rather than
handing them code, each because a second copy would be a second thing to drift:

- **`_build_audit_finding_record`** — lift verbatim from `tests/test_findings_storage.py`. A case
  fixture that disagrees with the storage tests' shape passes here and fails in the suite.
- **`_seeded_git_project` / `_start_brokered_run` / `_finish_run`** — lift from
  `tests/test_autonomy_lifecycle.py:50-140`. That module's `project` fixture commits
  `knowledge/graph.trig` deliberately (`start_run` materializes, so an uncommitted graph makes every
  dirty-tree assertion pass for the supervisor's own write), and its `pinned_toolkit` fixture is
  required because `assert_toolkit_matches` refuses a dirty judging toolkit. Both properties are
  easy to lose by reimplementing.
- **`validation_observation`'s signature** — referenced at `validate/findings.py:113-127` rather
  than reproduced, because a stale copy of a signature is worse than a pointer to the live one.

**Fixture identity constraints, since they bind across tasks.** `sealed_agent_run` uses
`test_autonomy_lifecycle.py`'s run: agent `lifecycle-agent`, model `test-model`, instrument ref
`rubric.md`, run id `run:2026-07-25-lifecycle-agent-a3f1`, and one served request —
`READ science.yaml`. `agent_attestation`'s defaults must match all four, and `science.yaml` is the
only path a citation can correspond to.

**Type consistency.** `counts_as_support()` is spelled identically in Tasks 4, 7 and 8.
`locked_store` (public, no underscore) in Tasks 1, 5. `append_review(project_root, finding_id,
submission, *, attestation)` — no `actor` — in Tasks 5, 6, 7. `MAX_UNCERTAINTY_ENTRIES` in Tasks 2, 3.
`RULE_UNCOUNTED_CONFIRMATION` and `check_review_confirmations` in Task 7 only.

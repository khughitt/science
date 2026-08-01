# Evidence broker plan 4b — checker

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replay a sealed evidence exposure and classify whether every location citation corresponds
to bytes the reviewer was shown, without changing a stored-review model or adding a production caller.

**Architecture:** A dependency-neutral `Correspondence` model crosses the future 4c boundary. A pure
hit parser turns canonical `git grep -n -z` bytes into `(path, line)` pairs; a local coverage algebra
merges replayed `read`, `search`, `history`, and inline contributions; and `check_correspondence`
performs the ordered protocol/environment checks before replaying through the already-merged
`serve.py`. Replay faults propagate except for the one narrowly scoped `serve.verify_commit` check
and the shared ancestry diagnostic.

**Tech Stack:** Python 3.11+, pydantic v2 (`science-model`), frozen dataclasses and standard-library
collections, pytest, real git through the existing hardened `run_git`/`serve` path.

**Design:** [`2026-07-30-agent-evidence-broker-design.md`](2026-07-30-agent-evidence-broker-design.md)
at revision 29 through `3093e05d` — §2.2 (authoritative slice contract), §5.1 (coverage), §5.2
(replay), §5.3 (classification order), and §7 (mutation pairs).

## Global Constraints

- Run model commands from `science/model/` and CLI-package commands from `science/`; the repository
  has no root `pyproject.toml`.
- Plan 4b creates exactly three production files:
  `science/model/src/science_model/correspondence.py`,
  `science/src/science_tool/evidence_broker/hits.py`, and
  `science/src/science_tool/evidence_broker/correspondence.py`.
- **Do not modify any stored-record model.** In particular, do not touch
  `science_model/audit/record.py`; `Review.evidence`, `Review.correspondence`, `ReviewAttestation`,
  `ReviewSubmission`, `append_review`, eligibility, and validate registration are plan 4c.
- **Do not modify `evidence_broker/serve.py`.** Replay imports and calls its canonical `serve` and
  `verify_commit`; a second serving implementation would check itself rather than the broker.
- `check_correspondence` has no production caller in this slice. Tests call it directly with
  constructible `Sequence[Evidence]` and `EvidenceExposure | None` values.
- Replay adds no NFC scan and no path normalization. Authored and journalled paths are already
  normalized; search-hit paths inherit plan 4a's UTF-8/NFC tree guarantee. A search target is a regex
  and must never be normalized.
- Error order is exact: no exposure; protocol mismatch; `serve.verify_commit`; ancestry diagnostic;
  replay integrity; citations. The first two checks are decided before any git call; protocol
  mismatch must not consult the repository.
- The checker contains exactly one `except ServeError`, around `verify_commit`. Every `ServeError` or
  `GitError` after that propagates and produces no `Correspondence` value.
- Coverage is derived only after every entry reproduces both `sha256(payload)` and `outcome`.
- `Outcome.REFUSED`, search misses, and history misses contribute no coverage. Only a read miss
  contributes `Absent`.
- `line_count` is LF-only: `payload.count(b"\n")` plus one when trailing bytes follow the final LF.
  Do not use `splitlines()`.
- Memoization is local to one `check_correspondence` call. Do not add cross-exposure state or caching.
- No compatibility shims, no `Unified` prefix, no new dependency, and no AI-attribution commit trailer.
- Use relative paths or `~/d/` in docs and code, never machine-specific absolute paths.

---

## File Structure

| File | Change | Responsibility after this slice |
|---|---|---|
| `science/model/src/science_model/correspondence.py` | create | The durable `Correspondence` result only. Imports pydantic and standard library; imports no `science_model` module. |
| `science/model/tests/test_correspondence.py` | create | Result invariants and the fresh-interpreter audit-import guard. |
| `science/src/science_tool/evidence_broker/hits.py` | create | Pure parser for canonical grep payloads; no git, policy, exposure, or review dependency. |
| `science/tests/test_evidence_broker_hits.py` | create | Synthetic edge cases plus one real-git format contract. |
| `science/src/science_tool/evidence_broker/correspondence.py` | create | Local coverage types, total merge, citation matching, replay, and `check_correspondence`. |
| `science/tests/test_evidence_broker_correspondence.py` | create | Coverage algebra, all §5.3 outcomes, replay ordering, propagation, memoization, and real-git integration. |

No package `__init__.py` re-export is needed. 4c imports `Correspondence` from its leaf module and
`check_correspondence` from its checker module directly; adding convenience exports now only creates
more import edges for the cycle tests to police.

## Interfaces

```python
# science_model/correspondence.py
class Correspondence(BaseModel):
    status: Literal["verified", "violated", "unwired"]
    code: str | None = None
    reason: str | None = None

# science_tool/evidence_broker/hits.py
def parse_hits(payload: bytes, commit: str) -> tuple[tuple[str, int], ...]: ...

# science_tool/evidence_broker/correspondence.py
@dataclass(frozen=True)
class Full:
    line_count: int

@dataclass(frozen=True)
class Lines:
    numbers: frozenset[int]

@dataclass(frozen=True)
class PathOnly: ...

@dataclass(frozen=True)
class Absent: ...

Coverage = Full | Lines | PathOnly | Absent

def check_correspondence(
    evidence: Sequence[Evidence], exposure: EvidenceExposure | None, *, repo: Path
) -> Correspondence: ...
```

The coverage vocabulary is module-local implementation detail even though its classes are named: it
is not re-exported and is never serialized. Tests import it from the defining module to certify the
ten-pair algebra directly.

---

### Task 1: Add the dependency-neutral `Correspondence` model

**Files:**
- Create: `science/model/src/science_model/correspondence.py`
- Create: `science/model/tests/test_correspondence.py`

**Interfaces:**
- Consumes: pydantic `BaseModel`, `ConfigDict`, `model_validator`; `typing.Literal`.
- Produces: `Correspondence`, imported by Task 4 and later by plan 4c.

Run this task from `science/model/`.

- [ ] **Step 1: Write the failing model and import-isolation tests**

Create `tests/test_correspondence.py`:

```python
from __future__ import annotations

import subprocess
import sys

import pytest
from pydantic import ValidationError

from science_model.correspondence import Correspondence


def test_nonverified_correspondence_requires_a_code() -> None:
    for status in ("violated", "unwired"):
        with pytest.raises(ValidationError, match="code"):
            Correspondence(status=status)


def test_verified_correspondence_has_no_code() -> None:
    with pytest.raises(ValidationError, match="verified"):
        Correspondence(status="verified", code="NOT_CLEAN")


def test_correspondence_is_frozen_and_forbids_extras() -> None:
    result = Correspondence(status="verified")
    with pytest.raises(ValidationError):
        result.status = "violated"
    with pytest.raises(ValidationError):
        Correspondence(status="verified", correspondence=True)


def test_importing_correspondence_does_not_load_audit() -> None:
    script = """
import sys
import science_model.correspondence
assert "science_model.audit" not in sys.modules
"""
    completed = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
```

- [ ] **Step 2: Run the tests to verify the module is absent**

```bash
uv run --frozen pytest tests/test_correspondence.py -v
```

Expected: collection fails with `ModuleNotFoundError: science_model.correspondence`.

- [ ] **Step 3: Add the minimal leaf model**

Create `src/science_model/correspondence.py`:

```python
"""Evidence-broker correspondence results.

This leaf deliberately imports no ``science_model`` module. ``CorrespondenceQualifiers`` in the
toolkit's validate package is an unrelated spec-1 finding identity and is not this result.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator


class Correspondence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["verified", "violated", "unwired"]
    code: str | None = None
    reason: str | None = None

    @model_validator(mode="after")
    def _code_matches_status(self) -> "Correspondence":
        if self.status == "verified":
            if self.code is not None:
                raise ValueError("verified correspondence must not carry a code")
        elif not self.code:
            raise ValueError(f"{self.status} correspondence requires a code")
        return self
```

Do not import `_Base`, `Evidence`, `Outcome`, or anything else from `science_model`. Repeating the
two-line pydantic base configuration is the import-cycle boundary, not duplication to refactor.

- [ ] **Step 4: Run the focused model checks**

```bash
uv run --frozen pytest tests/test_correspondence.py -q
uv run --frozen ruff check src/science_model/correspondence.py tests/test_correspondence.py
```

Expected: 4 tests pass; Ruff reports no findings.

- [ ] **Step 5: Prove the 4b import mutation**

Temporarily add `from science_model.audit.subjects import _Base` to
`science_model/correspondence.py` without using it, then run:

```bash
uv run --frozen pytest tests/test_correspondence.py::test_importing_correspondence_does_not_load_audit -q
```

Expected: FAIL because `science_model.audit` appears in the fresh interpreter's `sys.modules`.
Restore the leaf import before continuing. Do not test either full cycle yet; both require 4c's future
`audit.record -> Correspondence` edge and are therefore 4c mutation rows.

- [ ] **Step 6: Commit**

```bash
git add science/model/src/science_model/correspondence.py science/model/tests/test_correspondence.py
git commit -m "feat(evidence-broker): add correspondence result"
```

---

### Task 2: Parse canonical grep hits

**Files:**
- Create: `science/src/science_tool/evidence_broker/hits.py`
- Create: `science/tests/test_evidence_broker_hits.py`

**Interfaces:**
- Consumes: canonical payload bytes from `serve(... EvidenceOp.SEARCH ...)`; the pinned full commit.
- Produces: `parse_hits(payload, commit) -> tuple[(path, line), ...]`, imported by Task 4.

Run this task from `science/`.

- [ ] **Step 1: Write synthetic parser tests**

Create `tests/test_evidence_broker_hits.py` with these cases:

```python
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from science_model.evidence_broker import Outcome, SurfacePolicy

from science_tool.evidence_broker.hits import parse_hits
from science_tool.evidence_broker.policy import EvidenceOp, EvidenceRequest
from science_tool.evidence_broker.serve import serve

COMMIT = "a" * 40
OPEN = SurfacePolicy(notice="withheld")


def test_parse_hits_preserves_colons_and_nuls_in_content() -> None:
    payload = f"{COMMIT}:a:b.txt".encode() + b"\0" + b"7\0before\0after\n"
    assert parse_hits(payload, COMMIT) == (("a:b.txt", 7),)


def test_parse_hits_uses_lf_not_splitlines() -> None:
    payload = f"{COMMIT}:a.txt".encode() + b"\0" + b"1\0left\rright\n"
    assert parse_hits(payload, COMMIT) == (("a.txt", 1),)


@pytest.mark.parametrize(
    "payload",
    [
        b"missing-nuls\n",
        f"{'b' * 40}:a.txt\0".encode() + b"1\0hit\n",
        f"{COMMIT}:a.txt\0zero\0hit\n".encode(),
        f"{COMMIT}:a.txt".encode() + b"\x000\x00hit\n",
    ],
)
def test_parse_hits_refuses_noncanonical_records(payload: bytes) -> None:
    with pytest.raises(ValueError):
        parse_hits(payload, COMMIT)
```

- [ ] **Step 2: Add a real-git format contract to the same file**

Append a minimal repository helper and test:

```python
def _repo(tmp_path: Path) -> tuple[Path, str]:
    root = tmp_path / "repo"
    root.mkdir()
    for args in (
        ("init", "-q"),
        ("config", "user.email", "p@example.invalid"),
        ("config", "user.name", "P"),
    ):
        subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)
    (root / "a:b.bin").write_bytes(b"first\nneedle\0tail\n")
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(root), "commit", "-q", "-m", "seed"],
        check=True,
        capture_output=True,
    )
    commit = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"], check=True, capture_output=True
    ).stdout.decode().strip()
    return root, commit


def test_parse_hits_accepts_the_real_canonical_git_payload(tmp_path: Path) -> None:
    root, commit = _repo(tmp_path)
    result = serve(
        root,
        commit,
        EvidenceRequest(op=EvidenceOp.SEARCH, target="needle"),
        OPEN,
    )
    assert result.outcome is Outcome.SERVED
    assert b"\0tail" in result.payload  # proves the maxsplit fixture condition exists
    assert parse_hits(result.payload, commit) == (("a:b.bin", 2),)
```

The assertion on `b"\0tail"` is load-bearing: without it, the test stays green if the fixture ceases
to contain the NUL that distinguishes `maxsplit=2` from splitting the whole payload.

- [ ] **Step 3: Run the tests to verify the parser is absent**

```bash
uv run --frozen pytest tests/test_evidence_broker_hits.py -v
```

Expected: collection fails with `ModuleNotFoundError: science_tool.evidence_broker.hits`.

- [ ] **Step 4: Implement the pure parser**

Create `src/science_tool/evidence_broker/hits.py`:

```python
"""Pure parsing of the canonical ``git grep -n -z`` payload."""

from __future__ import annotations


def parse_hits(payload: bytes, commit: str) -> tuple[tuple[str, int], ...]:
    prefix = f"{commit}:".encode()
    hits: list[tuple[str, int]] = []
    for record in payload.split(b"\n"):
        if not record:
            continue
        try:
            descriptor, raw_line, _content = record.split(b"\0", 2)
        except ValueError as exc:
            raise ValueError("git grep record does not contain two NUL separators") from exc
        if not descriptor.startswith(prefix):
            raise ValueError("git grep record does not carry the pinned commit prefix")
        raw_path = descriptor.removeprefix(prefix)
        if not raw_path:
            raise ValueError("git grep record carries an empty path")
        try:
            path = raw_path.decode("utf-8")
            line = int(raw_line)
        except (UnicodeDecodeError, ValueError) as exc:
            raise ValueError("git grep record has an invalid UTF-8 path or line number") from exc
        if line < 1:
            raise ValueError("git grep line numbers are one-based")
        hits.append((path, line))
    return tuple(hits)
```

Do not normalize `path`: these bytes came from the plan-4a-validated tree. Do not add a custom parser
exception; malformed canonical output is an implementation/runtime fault and must propagate.

- [ ] **Step 5: Run the focused tests and lint**

```bash
uv run --frozen pytest tests/test_evidence_broker_hits.py -q
uv run --frozen ruff check src/science_tool/evidence_broker/hits.py tests/test_evidence_broker_hits.py
```

- [ ] **Step 6: Prove the NUL mutation**

Temporarily replace `record.split(b"\0", 2)` with `record.split(b"\0")`, then run:

```bash
uv run --frozen pytest tests/test_evidence_broker_hits.py::test_parse_hits_accepts_the_real_canonical_git_payload -q
```

Expected: FAIL while parsing the real binary hit. Restore `maxsplit=2`.

- [ ] **Step 7: Commit**

```bash
git add science/src/science_tool/evidence_broker/hits.py science/tests/test_evidence_broker_hits.py
git commit -m "feat(evidence-broker): parse canonical grep hits"
```

---

### Task 3: Implement the coverage algebra and citation predicate

**Files:**
- Create: `science/src/science_tool/evidence_broker/correspondence.py`
- Create: `science/tests/test_evidence_broker_correspondence.py`

**Interfaces:**
- Consumes: merged `LocationEvidence` and `Span` models.
- Produces: `Full`, `Lines`, `PathOnly`, `Absent`, `Coverage`, `_line_count`,
  `_merge_coverage`, `_add_coverage`, and `_corresponds`; Task 4 extends the same module.

Run this task from `science/`.

- [ ] **Step 1: Write the total merge table tests**

Create `tests/test_evidence_broker_correspondence.py` and add:

```python
from __future__ import annotations

import pytest
from science_model.audit import LocationEvidence, Span

from science_tool.evidence_broker.correspondence import (
    Absent,
    Full,
    Lines,
    PathOnly,
    _corresponds,
    _line_count,
    _merge_coverage,
)


@pytest.mark.parametrize(
    "left,right,expected",
    [
        (Full(8), Full(5), Full(5)),
        (Full(8), Lines(frozenset({9})), Full(8)),
        (Full(8), PathOnly(), Full(8)),
        (Full(8), Absent(), Full(8)),
        (Lines(frozenset({1})), Lines(frozenset({3})), Lines(frozenset({1, 3}))),
        (Lines(frozenset({1})), PathOnly(), Lines(frozenset({1}))),
        (PathOnly(), PathOnly(), PathOnly()),
        (PathOnly(), Absent(), Absent()),
        (Absent(), Absent(), Absent()),
    ],
)
def test_merge_coverage_is_total_over_reachable_pairs(left, right, expected) -> None:
    assert _merge_coverage(left, right) == expected
    assert _merge_coverage(right, left) == expected


def test_lines_and_absent_is_rejected_as_unreachable() -> None:
    with pytest.raises(ValueError, match="both matched and absent"):
        _merge_coverage(Lines(frozenset({1})), Absent())
```

- [ ] **Step 2: Add LF-count and citation tests**

Append:

```python
@pytest.mark.parametrize(
    "payload,expected",
    [(b"", 0), (b"a\n", 1), (b"a", 1), (b"a\nb", 2), (b"a\rb\n", 1)],
)
def test_line_count_uses_lf_only(payload: bytes, expected: int) -> None:
    assert _line_count(payload) == expected


def test_full_bounds_lines_but_allows_a_pointer() -> None:
    assert _corresponds(LocationEvidence(path="a", line=2), Full(2))
    assert not _corresponds(LocationEvidence(path="a", line=3), Full(2))
    assert _corresponds(LocationEvidence(path="a", pointer="heading"), Full(0))


def test_lines_requires_every_line_of_a_span_and_forbids_a_pointer() -> None:
    coverage = Lines(frozenset({2, 3, 4}))
    assert _corresponds(LocationEvidence(path="a", span=Span(start_line=2, end_line=4)), coverage)
    endpoints_only = Lines(frozenset({2, 4}))
    assert not _corresponds(LocationEvidence(path="a", span=Span(start_line=2, end_line=4)), endpoints_only)
    assert not _corresponds(LocationEvidence(path="a", pointer="heading"), coverage)


@pytest.mark.parametrize("coverage", [PathOnly(), Absent()])
def test_path_only_coverages_accept_only_a_bare_path(coverage) -> None:
    assert _corresponds(LocationEvidence(path="a"), coverage)
    assert not _corresponds(LocationEvidence(path="a", line=1), coverage)
    assert not _corresponds(LocationEvidence(path="a", pointer="heading"), coverage)
```

- [ ] **Step 3: Run the tests to verify the module is absent**

```bash
uv run --frozen pytest tests/test_evidence_broker_correspondence.py -v
```

Expected: collection fails with `ModuleNotFoundError`.

- [ ] **Step 4: Implement the local coverage types and pure functions**

Create `src/science_tool/evidence_broker/correspondence.py` with:

```python
"""Replay an evidence exposure and check location citations against its coverage."""

from __future__ import annotations

from dataclasses import dataclass

from science_model.audit import LocationEvidence


@dataclass(frozen=True)
class Full:
    line_count: int


@dataclass(frozen=True)
class Lines:
    numbers: frozenset[int]


@dataclass(frozen=True)
class PathOnly:
    pass


@dataclass(frozen=True)
class Absent:
    pass


Coverage = Full | Lines | PathOnly | Absent


def _line_count(payload: bytes) -> int:
    return payload.count(b"\n") + int(bool(payload) and not payload.endswith(b"\n"))


def _merge_coverage(left: Coverage, right: Coverage) -> Coverage:
    if isinstance(left, Full) and isinstance(right, Full):
        return Full(min(left.line_count, right.line_count))
    if isinstance(left, Full):
        return left
    if isinstance(right, Full):
        return right
    if isinstance(left, Lines) and isinstance(right, Lines):
        return Lines(left.numbers | right.numbers)
    if (isinstance(left, Lines) and isinstance(right, Absent)) or (
        isinstance(left, Absent) and isinstance(right, Lines)
    ):
        raise ValueError("a path cannot be both matched and absent at one commit")
    if isinstance(left, Lines):
        return left
    if isinstance(right, Lines):
        return right
    if isinstance(left, Absent):
        return left
    if isinstance(right, Absent):
        return right
    return PathOnly()


def _add_coverage(served: dict[str, Coverage], path: str, coverage: Coverage) -> None:
    current = served.get(path)
    served[path] = coverage if current is None else _merge_coverage(current, coverage)


def _cited_lines(citation: LocationEvidence) -> range | tuple[int, ...]:
    if citation.line is not None:
        return (citation.line,)
    if citation.span is not None:
        return range(citation.span.start_line, citation.span.end_line + 1)
    return ()


def _corresponds(citation: LocationEvidence, coverage: Coverage) -> bool:
    cited = _cited_lines(citation)
    if citation.pointer is not None and not isinstance(coverage, Full):
        return False
    if isinstance(coverage, Full):
        return all(line <= coverage.line_count for line in cited)
    if isinstance(coverage, Lines):
        return all(line in coverage.numbers for line in cited)
    return not cited and citation.pointer is None
```

This is composition, not a base-class hierarchy. Do not add methods to the coverage values or serialize
them; they are transient data carried only inside one check.

- [ ] **Step 5: Run the focused checks**

```bash
uv run --frozen pytest tests/test_evidence_broker_correspondence.py -q
uv run --frozen ruff check src/science_tool/evidence_broker/correspondence.py tests/test_evidence_broker_correspondence.py
```

- [ ] **Step 6: Prove the two non-rank merge mutations**

First change `min` to `max`; run the merge test selecting `Full`:

```bash
uv run --frozen pytest tests/test_evidence_broker_correspondence.py::test_merge_coverage_is_total_over_reachable_pairs -q
```

Expected: FAIL on `Full(8) + Full(5)`. Restore it. Then replace the `Lines` union with `return right`;
run the same test and expect failure on `{1} + {3}`. Restore it before committing.

- [ ] **Step 7: Commit**

```bash
git add science/src/science_tool/evidence_broker/correspondence.py \
  science/tests/test_evidence_broker_correspondence.py
git commit -m "feat(evidence-broker): define citation coverage"
```

---

### Task 4: Replay exposures and classify correspondence

**Files:**
- Modify: `science/src/science_tool/evidence_broker/correspondence.py`
- Modify: `science/tests/test_evidence_broker_correspondence.py`

**Interfaces:**
- Consumes: Task 1 `Correspondence`; Task 2 `parse_hits`; Task 3 coverage helpers; merged
  `REPLAY_PROTOCOL_VERSION`, `serve`, `verify_commit`, and `history_traversal_error`.
- Produces: `check_correspondence(evidence, exposure, *, repo) -> Correspondence` for plan 4c.

Run this task from `science/`.

- [ ] **Step 1: Add reusable real-replay fixtures to the test module**

Replace the test module's import block with:

```python
from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

import pytest
from science_model.audit import LocationEvidence, Span, TextEvidence
from science_model.evidence_broker import (
    REPLAY_PROTOCOL_VERSION,
    EvidenceExposure,
    ExposureEntry,
    InlineInput,
    InstrumentIdentity,
    Outcome,
    SurfacePolicy,
)

import science_tool.evidence_broker.correspondence as correspondence_module
from science_tool.evidence_broker.correspondence import (
    Absent,
    Full,
    Lines,
    PathOnly,
    _corresponds,
    _line_count,
    _merge_coverage,
    check_correspondence,
)
from science_tool.evidence_broker.policy import EvidenceOp, EvidenceRequest
from science_tool.evidence_broker.serve import ServeError, serve
```

Then add:

```python
OPEN = SurfacePolicy(notice="withheld")
INSTRUMENT = InstrumentIdentity(ref="rubric.md", sha256="c" * 64, prompt_hash="d" * 64)


def _repo(tmp_path: Path) -> tuple[Path, str]:
    root = tmp_path / "repo"
    root.mkdir()
    for args in (
        ("init", "-q"),
        ("config", "user.email", "p@example.invalid"),
        ("config", "user.name", "P"),
    ):
        subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)
    (root / "a.txt").write_text("alpha\nbeta\ngamma\n", encoding="utf-8")
    (root / "cr.txt").write_bytes(b"left\rright\n")
    (root / "empty.txt").write_bytes(b"")
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(root), "commit", "-q", "-m", "seed"],
        check=True,
        capture_output=True,
    )
    (root / "head.txt").write_text("second commit\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(root), "commit", "-q", "-m", "head"],
        check=True,
        capture_output=True,
    )
    commit = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"], check=True, capture_output=True
    ).stdout.decode().strip()
    return root, commit


def _entry(root: Path, commit: str, request: EvidenceRequest, policy=OPEN) -> ExposureEntry:
    replayed = serve(root, commit, request, policy)
    return ExposureEntry(
        op=request.op.value,
        target=replayed.target,
        pathspec=replayed.pathspec,
        commit=commit,
        sha256=hashlib.sha256(replayed.payload).hexdigest(),
        outcome=replayed.outcome,
    )


def _exposure(commit: str, entries=(), *, inline=(), protocol=REPLAY_PROTOCOL_VERSION, policy=OPEN):
    return EvidenceExposure(
        commit=commit,
        budget=10,
        requests_used=len([entry for entry in entries if entry.op != "inline"]),
        instrument=INSTRUMENT,
        surface_policy=policy,
        inline=inline,
        replay_protocol=protocol,
        entries=entries,
    )
```

- [ ] **Step 2: Write the six §5.3 classification tests in their executable order**

Add one test for each row:

```python
def test_no_exposure_is_unwired_without_touching_git(tmp_path: Path) -> None:
    result = check_correspondence((), None, repo=tmp_path / "not-a-repository")
    assert (result.status, result.code) == ("unwired", "NO_EXPOSURE")


def test_protocol_mismatch_precedes_every_git_call(tmp_path: Path) -> None:
    exposure = _exposure("a" * 40, protocol=REPLAY_PROTOCOL_VERSION - 1)
    result = check_correspondence((), exposure, repo=tmp_path / "not-a-repository")
    assert (result.status, result.code) == ("unwired", "REPLAY_PROTOCOL_MISMATCH")


def test_an_absent_commit_is_unwired(tmp_path: Path) -> None:
    root, _commit = _repo(tmp_path)
    result = check_correspondence((), _exposure("a" * 40), repo=root)
    assert (result.status, result.code) == ("unwired", "EXPOSURE_UNREACHABLE")


def test_a_replay_mismatch_is_violated(tmp_path: Path) -> None:
    root, commit = _repo(tmp_path)
    entry = _entry(root, commit, EvidenceRequest(EvidenceOp.READ, "a.txt"))
    forged = entry.model_copy(update={"sha256": "0" * 64})
    result = check_correspondence((), _exposure(commit, (forged,)), repo=root)
    assert (result.status, result.code) == ("violated", "EXPOSURE_UNREPRODUCIBLE")


def test_an_unserved_citation_is_violated(tmp_path: Path) -> None:
    root, commit = _repo(tmp_path)
    result = check_correspondence(
        (LocationEvidence(path="a.txt", line=1),), _exposure(commit), repo=root
    )
    assert (result.status, result.code) == ("violated", "CITATION_UNSERVED")


def test_a_served_citation_is_verified(tmp_path: Path) -> None:
    root, commit = _repo(tmp_path)
    entry = _entry(root, commit, EvidenceRequest(EvidenceOp.READ, "a.txt"))
    result = check_correspondence(
        (LocationEvidence(path="a.txt", line=2),), _exposure(commit, (entry,)), repo=root
    )
    assert result.status == "verified"
    assert result.code is None
```

- [ ] **Step 3: Add replay-integrity and contribution tests**

Add these tests. They use `_entry` for honest non-inline entries and construct inline state directly;
none reads a baseline, journal, or control-plane path.

```python
def test_a_refusal_contributes_no_coverage(tmp_path: Path) -> None:
    root, commit = _repo(tmp_path)
    closed = SurfacePolicy(deny_prefixes=("a.txt",), notice="withheld")
    entry = _entry(root, commit, EvidenceRequest(EvidenceOp.READ, "a.txt"), closed)
    result = check_correspondence(
        (LocationEvidence(path="a.txt"),),
        _exposure(commit, (entry,), policy=closed),
        repo=root,
    )
    assert (result.status, result.code) == ("violated", "CITATION_UNSERVED")


def test_an_empty_file_is_full_zero_coverage(tmp_path: Path) -> None:
    root, commit = _repo(tmp_path)
    entry = _entry(root, commit, EvidenceRequest(EvidenceOp.READ, "empty.txt"))
    exposure = _exposure(commit, (entry,))
    assert check_correspondence((LocationEvidence(path="empty.txt"),), exposure, repo=root).status == "verified"
    assert check_correspondence(
        (LocationEvidence(path="empty.txt", line=1),), exposure, repo=root
    ).code == "CITATION_UNSERVED"


def test_a_read_miss_covers_only_the_bare_path(tmp_path: Path) -> None:
    root, commit = _repo(tmp_path)
    entry = _entry(root, commit, EvidenceRequest(EvidenceOp.READ, "absent.txt"))
    exposure = _exposure(commit, (entry,))
    assert check_correspondence((LocationEvidence(path="absent.txt"),), exposure, repo=root).status == "verified"
    assert check_correspondence(
        (LocationEvidence(path="absent.txt", line=1),), exposure, repo=root
    ).code == "CITATION_UNSERVED"


def test_search_exposes_only_hit_lines_and_unites_two_searches(tmp_path: Path) -> None:
    root, commit = _repo(tmp_path)
    first = _entry(root, commit, EvidenceRequest(EvidenceOp.SEARCH, "alpha"))
    last = _entry(root, commit, EvidenceRequest(EvidenceOp.SEARCH, "gamma"))
    exposure = _exposure(commit, (first, last))
    result = check_correspondence(
        (LocationEvidence(path="a.txt", line=1), LocationEvidence(path="a.txt", line=3)),
        exposure,
        repo=root,
    )
    assert result.status == "verified"
    assert check_correspondence(
        (LocationEvidence(path="a.txt", line=2),), exposure, repo=root
    ).code == "CITATION_UNSERVED"


def test_a_search_miss_contributes_no_coverage(tmp_path: Path) -> None:
    root, commit = _repo(tmp_path)
    entry = _entry(root, commit, EvidenceRequest(EvidenceOp.SEARCH, "not-present"))
    result = check_correspondence(
        (LocationEvidence(path="a.txt"),), _exposure(commit, (entry,)), repo=root
    )
    assert result.code == "CITATION_UNSERVED"


def test_history_covers_a_bare_path_but_not_a_line(tmp_path: Path) -> None:
    root, commit = _repo(tmp_path)
    entry = _entry(root, commit, EvidenceRequest(EvidenceOp.HISTORY, "a.txt"))
    exposure = _exposure(commit, (entry,))
    assert check_correspondence((LocationEvidence(path="a.txt"),), exposure, repo=root).status == "verified"
    assert check_correspondence(
        (LocationEvidence(path="a.txt", line=1),), exposure, repo=root
    ).code == "CITATION_UNSERVED"


def test_empty_history_contributes_no_coverage(tmp_path: Path) -> None:
    root, commit = _repo(tmp_path)
    entry = _entry(root, commit, EvidenceRequest(EvidenceOp.HISTORY, "absent.txt"))
    result = check_correspondence(
        (LocationEvidence(path="absent.txt"),), _exposure(commit, (entry,)), repo=root
    )
    assert result.code == "CITATION_UNSERVED"


def test_a_read_supersedes_search_lines(tmp_path: Path) -> None:
    root, commit = _repo(tmp_path)
    read = _entry(root, commit, EvidenceRequest(EvidenceOp.READ, "a.txt"))
    search = _entry(root, commit, EvidenceRequest(EvidenceOp.SEARCH, "alpha"))
    result = check_correspondence(
        (LocationEvidence(path="a.txt", line=3),),
        _exposure(commit, (read, search)),
        repo=root,
    )
    assert result.status == "verified"


def test_read_line_count_is_lf_only(tmp_path: Path) -> None:
    root, commit = _repo(tmp_path)
    entry = _entry(root, commit, EvidenceRequest(EvidenceOp.READ, "cr.txt"))
    result = check_correspondence(
        (LocationEvidence(path="cr.txt", line=2),), _exposure(commit, (entry,)), repo=root
    )
    assert result.code == "CITATION_UNSERVED"


def _inline(commit: str, *, target: str = "prompt.md", digest: str = "e" * 64):
    # Overrides alter only the entry; the fixed manifest makes each disagreement deliberate.
    manifest = InlineInput(target="prompt.md", sha256="e" * 64, lines=2)
    entry = ExposureEntry(
        op="inline",
        target=target,
        commit=commit,
        sha256=digest,
        outcome=Outcome.SERVED,
    )
    return manifest, entry


def test_inline_coverage_uses_the_sealed_line_count(tmp_path: Path) -> None:
    root, commit = _repo(tmp_path)
    manifest, entry = _inline(commit)
    result = check_correspondence(
        (LocationEvidence(path="prompt.md", line=2),),
        _exposure(commit, (entry,), inline=(manifest,)),
        repo=root,
    )
    assert result.status == "verified"


def test_inline_and_read_full_coverage_takes_the_smaller_count(tmp_path: Path) -> None:
    root, commit = _repo(tmp_path)
    manifest = InlineInput(target="a.txt", sha256="e" * 64, lines=4)
    inline_entry = ExposureEntry(
        op="inline",
        target="a.txt",
        commit=commit,
        sha256=manifest.sha256,
        outcome=Outcome.SERVED,
    )
    read_entry = _entry(root, commit, EvidenceRequest(EvidenceOp.READ, "a.txt"))
    result = check_correspondence(
        (LocationEvidence(path="a.txt", line=4),),
        _exposure(commit, (inline_entry, read_entry), inline=(manifest,)),
        repo=root,
    )
    assert result.code == "CITATION_UNSERVED"


@pytest.mark.parametrize(
    "target,digest",
    [("other.md", "e" * 64), ("prompt.md", "f" * 64)],
)
def test_inline_disagreement_is_unreproducible(
    tmp_path: Path, target: str, digest: str
) -> None:
    root, commit = _repo(tmp_path)
    manifest, entry = _inline(commit, target=target, digest=digest)
    result = check_correspondence(
        (LocationEvidence(path=target),),
        _exposure(commit, (entry,), inline=(manifest,)),
        repo=root,
    )
    assert (result.status, result.code) == ("violated", "EXPOSURE_UNREPRODUCIBLE")


def test_outcome_is_replayed_beside_the_digest(tmp_path: Path) -> None:
    root, commit = _repo(tmp_path)
    closed = SurfacePolicy(deny_prefixes=("a.txt",), notice="withheld")
    refused = _entry(root, commit, EvidenceRequest(EvidenceOp.READ, "a.txt"), closed)
    relabelled = refused.model_copy(update={"outcome": Outcome.SERVED})
    result = check_correspondence(
        (), _exposure(commit, (relabelled,), policy=closed), repo=root
    )
    assert (result.status, result.code) == ("violated", "EXPOSURE_UNREPRODUCIBLE")


def test_a_narrowed_policy_is_unreproducible_not_silently_uncovered(tmp_path: Path) -> None:
    root, commit = _repo(tmp_path)
    served_open = _entry(root, commit, EvidenceRequest(EvidenceOp.READ, "a.txt"), OPEN)
    narrowed = SurfacePolicy(deny_prefixes=("a.txt",), notice="withheld")
    result = check_correspondence(
        (), _exposure(commit, (served_open,), policy=narrowed), repo=root
    )
    assert (result.status, result.code) == ("violated", "EXPOSURE_UNREPRODUCIBLE")


def test_replay_integrity_precedes_citations(tmp_path: Path) -> None:
    root, commit = _repo(tmp_path)
    entry = _entry(root, commit, EvidenceRequest(EvidenceOp.READ, "a.txt"))
    forged = entry.model_copy(update={"sha256": "0" * 64})
    result = check_correspondence(
        (LocationEvidence(path="never-served.txt"),),
        _exposure(commit, (forged,)),
        repo=root,
    )
    assert result.code == "EXPOSURE_UNREPRODUCIBLE"


def test_text_only_and_empty_evidence_are_vacuously_verified(tmp_path: Path) -> None:
    root, commit = _repo(tmp_path)
    for evidence in ((), (TextEvidence(text="prose belongs in the note"),)):
        result = check_correspondence(evidence, _exposure(commit), repo=root)
        assert result.status == "verified"
        assert result.reason
```

- [ ] **Step 4: Add the ordering, helper, propagation, and memoization guards**

Add these exact tests:

```python
def test_verify_commit_rejects_a_present_noncommit_oid(tmp_path: Path) -> None:
    root, _commit = _repo(tmp_path)
    tree_oid = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD^{tree}"],
        check=True,
        capture_output=True,
    ).stdout.decode().strip()
    entry = ExposureEntry(
        op="read",
        target="a.txt",
        commit=tree_oid,
        sha256="0" * 64,
        outcome=Outcome.SERVED,
    )
    result = check_correspondence((), _exposure(tree_oid, (entry,)), repo=root)
    assert (result.status, result.code) == ("unwired", "EXPOSURE_UNREACHABLE")


def test_a_serve_error_after_environment_checks_propagates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, commit = _repo(tmp_path)
    entry = _entry(root, commit, EvidenceRequest(EvidenceOp.READ, "a.txt"))

    def fail(*args, **kwargs):
        raise ServeError("runtime format changed")

    monkeypatch.setattr(correspondence_module, "serve", fail)
    with pytest.raises(ServeError, match="runtime format changed"):
        check_correspondence((), _exposure(commit, (entry,)), repo=root)


def test_identical_requests_replay_once_within_one_exposure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, commit = _repo(tmp_path)
    entry = _entry(root, commit, EvidenceRequest(EvidenceOp.READ, "a.txt"))
    real_serve = correspondence_module.serve
    calls = 0

    def counted(*args, **kwargs):
        nonlocal calls
        calls += 1
        return real_serve(*args, **kwargs)

    monkeypatch.setattr(correspondence_module, "serve", counted)
    result = check_correspondence((), _exposure(commit, (entry, entry)), repo=root)
    assert result.status == "verified"
    assert calls == 1


def test_replay_cache_does_not_cross_exposures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, commit = _repo(tmp_path)
    entry = _entry(root, commit, EvidenceRequest(EvidenceOp.READ, "a.txt"))
    real_serve = correspondence_module.serve
    calls = 0

    def counted(*args, **kwargs):
        nonlocal calls
        calls += 1
        return real_serve(*args, **kwargs)

    monkeypatch.setattr(correspondence_module, "serve", counted)
    check_correspondence((), _exposure(commit, (entry,), policy=OPEN), repo=root)
    check_correspondence(
        (),
        _exposure(commit, (entry,), policy=SurfacePolicy(notice="a different sealed policy")),
        repo=root,
    )
    assert calls == 2
```

Add the genuine shallow-clone guard; the second commit in `_repo` makes depth one incomplete, and the
`file://` URL makes git honor `--depth` for a local source:

```python
def test_a_shallow_replay_repository_is_unwired(tmp_path: Path) -> None:
    root, commit = _repo(tmp_path)
    entry = _entry(root, commit, EvidenceRequest(EvidenceOp.HISTORY, "a.txt"))
    clone = tmp_path / "shallow"
    subprocess.run(
        ["git", "clone", "-q", "--depth", "1", root.as_uri(), str(clone)],
        check=True,
        capture_output=True,
    )
    result = check_correspondence((), _exposure(commit, (entry,)), repo=clone)
    assert (result.status, result.code) == ("unwired", "EXPOSURE_UNREACHABLE")
```

- [ ] **Step 5: Run the new tests to verify `check_correspondence` is absent**

```bash
uv run --frozen pytest tests/test_evidence_broker_correspondence.py -k "no_exposure or protocol_mismatch or absent_commit or replay_mismatch or unserved_citation or served_citation" -v
```

Expected: collection/import fails because `check_correspondence` is not defined.

- [ ] **Step 6: Add replay and served-map construction**

Replace `correspondence.py`'s import block with:

```python
from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from science_model.audit import Evidence, LocationEvidence
from science_model.correspondence import Correspondence
from science_model.evidence_broker import (
    REPLAY_PROTOCOL_VERSION,
    EvidenceExposure,
    ExposureEntry,
    InlineInput,
    Outcome,
)

from science_tool.autonomy.git import history_traversal_error
from science_tool.evidence_broker.hits import parse_hits
from science_tool.evidence_broker.policy import EvidenceOp, EvidenceRequest
from science_tool.evidence_broker.serve import ServeError, Served, serve, verify_commit
```

Implement these private helpers:

```python
def _request(entry: ExposureEntry) -> EvidenceRequest:
    return EvidenceRequest(EvidenceOp(entry.op), target=entry.target, pathspec=entry.pathspec)


def _build_served_map(
    replayed: list[tuple[ExposureEntry, Served | InlineInput]], commit: str
) -> dict[str, Coverage]:
    served_map: dict[str, Coverage] = {}
    for entry, answer in replayed:
        if isinstance(answer, InlineInput):
            _add_coverage(served_map, answer.target, Full(answer.lines))
        elif answer.outcome is Outcome.REFUSED:
            continue
        elif entry.op == "read":
            if answer.outcome is Outcome.SERVED:
                _add_coverage(served_map, answer.target, Full(_line_count(answer.payload)))
            elif answer.outcome is Outcome.MISS_ABSENT:
                _add_coverage(served_map, answer.target, Absent())
        elif entry.op == "search" and answer.outcome is Outcome.SERVED:
            for path, line in parse_hits(answer.payload, commit):
                _add_coverage(served_map, path, Lines(frozenset({line})))
        elif entry.op == "history" and answer.outcome is Outcome.SERVED:
            _add_coverage(served_map, answer.target, PathOnly())
    return served_map
```

Search and history misses fall through deliberately. Do not infer coverage from an empty payload.

- [ ] **Step 7: Implement the ordered checker**

Add:

```python
def check_correspondence(
    evidence: Sequence[Evidence], exposure: EvidenceExposure | None, *, repo: Path
) -> Correspondence:
    if exposure is None:
        return Correspondence(
            status="unwired", code="NO_EXPOSURE", reason="run record carries no evidence exposure"
        )
    if exposure.replay_protocol != REPLAY_PROTOCOL_VERSION:
        return Correspondence(
            status="unwired",
            code="REPLAY_PROTOCOL_MISMATCH",
            reason=(
                f"exposure protocol {exposure.replay_protocol} differs from "
                f"checker protocol {REPLAY_PROTOCOL_VERSION}"
            ),
        )
    try:
        verify_commit(repo, exposure.commit)
    except ServeError as exc:
        return Correspondence(status="unwired", code="EXPOSURE_UNREACHABLE", reason=str(exc))
    traversal_error = history_traversal_error(repo, exposure.commit)
    if traversal_error is not None:
        return Correspondence(
            status="unwired", code="EXPOSURE_UNREACHABLE", reason=traversal_error
        )

    inline = {(item.target, item.sha256): item for item in exposure.inline}
    cache: dict[EvidenceRequest, Served] = {}
    replayed: list[tuple[ExposureEntry, Served | InlineInput]] = []
    for entry in exposure.entries:
        if entry.op == "inline":
            item = inline.get((entry.target, entry.sha256))
            if item is None:
                return Correspondence(
                    status="violated",
                    code="EXPOSURE_UNREPRODUCIBLE",
                    reason=f"inline entry {entry.target!r} disagrees with the sealed manifest",
                )
            replayed.append((entry, item))
            continue

        request = _request(entry)
        answer = cache.get(request)
        if answer is None:
            answer = serve(repo, exposure.commit, request, exposure.surface_policy)
            cache[request] = answer
        if hashlib.sha256(answer.payload).hexdigest() != entry.sha256 or answer.outcome is not entry.outcome:
            return Correspondence(
                status="violated",
                code="EXPOSURE_UNREPRODUCIBLE",
                reason=f"{entry.op} entry {entry.target!r} did not replay identically",
            )
        replayed.append((entry, answer))

    served_map = _build_served_map(replayed, exposure.commit)
    locations = [item for item in evidence if isinstance(item, LocationEvidence)]
    for citation in locations:
        coverage = served_map.get(citation.path)
        if coverage is None or not _corresponds(citation, coverage):
            return Correspondence(
                status="violated",
                code="CITATION_UNSERVED",
                reason=f"citation to {citation.path!r} was not covered by the replayed exposure",
            )
    return Correspondence(
        status="verified",
        reason=None if locations else "review carries no path-bearing citations",
    )
```

The `except ServeError` must remain exactly where shown. Do not wrap `history_traversal_error`, the
entry loop, `serve`, `parse_hits`, or `_build_served_map`.

- [ ] **Step 8: Run the complete checker tests and adjacent contracts**

```bash
uv run --frozen pytest \
  tests/test_evidence_broker_hits.py \
  tests/test_evidence_broker_correspondence.py \
  tests/test_evidence_broker_serve.py \
  tests/test_autonomy_git_canonical.py -q
uv run --frozen ruff check \
  src/science_tool/evidence_broker/hits.py \
  src/science_tool/evidence_broker/correspondence.py \
  tests/test_evidence_broker_hits.py \
  tests/test_evidence_broker_correspondence.py
uv run --frozen pyright
```

- [ ] **Step 9: Commit**

```bash
git add science/src/science_tool/evidence_broker/correspondence.py \
  science/tests/test_evidence_broker_correspondence.py
git commit -m "feat(evidence-broker): replay and check correspondence"
```

---

### Task 5: Certify every plan-4b mutation pair

**Files:**
- Modify only if a test is found vacuous:
  `science/model/tests/test_correspondence.py`,
  `science/tests/test_evidence_broker_hits.py`, or
  `science/tests/test_evidence_broker_correspondence.py`

**Interfaces:**
- Consumes: Tasks 1–4 complete.
- Produces: mutation evidence that every §7 plan-4b guard and the plan's additional parser/replay
  guards turn red for the defect they name.

Run one mutation at a time, run only its named test, and restore production immediately. Stop and
repair the test if any mutation stays green; a green mutation is not certification.

- [ ] **Step 1: Run the structural/model pairs**

| Mutation | Test that must fail |
|---|---|
| Import anything from `science_model.audit` in the leaf model | `test_importing_correspondence_does_not_load_audit` |
| Remove the protocol comparison | `test_protocol_mismatch_precedes_every_git_call` |
| Move protocol comparison after `verify_commit` | `test_protocol_mismatch_precedes_every_git_call` |
| Replace `verify_commit` with bare `rev-parse --verify` | `test_verify_commit_rejects_a_present_noncommit_oid` |

For the last row retain the request entry in the fixture. Measured on the planning tree: bare
`rev-parse` accepts the tree OID and `history_traversal_error` returns `None`, so replay is the first
line that distinguishes the mutation; an absent OID would make both implementations return
`EXPOSURE_UNREACHABLE` and certify nothing.

- [ ] **Step 2: Run parser and coverage pairs**

| Mutation | Test that must fail |
|---|---|
| Split each hit on every NUL | `test_parse_hits_accepts_the_real_canonical_git_payload` |
| Split parser records with `splitlines()` | `test_parse_hits_uses_lf_not_splitlines` |
| Remove the one-based line-number guard | `test_parse_hits_refuses_noncanonical_records` (`b"\x000\x00hit\n"`) |
| Compute line count with `splitlines()` | `test_line_count_uses_lf_only` (`b"a\rb\n"`) |
| Drop the trailing-bytes clause | `test_line_count_uses_lf_only` (`b"a"` or `b"a\nb"`) |
| Merge `Full` with maximum/last-write-wins | `test_merge_coverage_is_total_over_reachable_pairs` (`Full(8), Full(5)`) |
| Replace rather than unite two `Lines` | the two-search integration test and the direct merge row |
| Let `REFUSED` contribute `Full(0)` | refused-read citation test |
| Drop `Full` superseding `Lines` | read-plus-search test with a citation outside the hit set |
| Permit a pointer under `Lines` | `test_lines_requires_every_line_of_a_span_and_forbids_a_pointer` |
| Check only a span's endpoints | `test_lines_requires_every_line_of_a_span_and_forbids_a_pointer`, where both endpoints are covered and an interior line is not |

- [ ] **Step 3: Run replay/order pairs**

| Mutation | Test that must fail |
|---|---|
| Compare digest but not outcome | relabelled-refusal test |
| Evaluate citations before replay integrity | mismatch-plus-unserved-citation test, expecting `EXPOSURE_UNREPRODUCIBLE` |
| Drop `history_traversal_error` | genuine shallow-clone test |
| Catch a replay-time `ServeError` as unwired | `test_a_serve_error_after_environment_checks_propagates` |
| Treat a missing inline manifest match as uncovered | inline-target mismatch test |
| Memoize outside `check_correspondence` | `test_replay_cache_does_not_cross_exposures` |

- [ ] **Step 4: Confirm the forbidden/vacuous rows were not added**

- No test claims that pre-normalizing a replay target is distinguishable; path normalization is
  idempotent and the journal stores the authorized path spelling.
- No plan-4b test claims to close either final import cycle. Those cycles exist only after plan 4c
  adds `audit.record -> Correspondence`.
- No test reaches for a baseline, journal, control-plane directory, `Review`, or case store.

- [ ] **Step 5: Run final verification**

The model suite is small and a new durable model was added, so run it in full. The CLI package adds
two isolated modules with no production caller; AGENTS.md does not call for the ~12k full CLI suite.
Run the new modules plus their serving/git contracts instead.

```bash
cd science/model && uv run --frozen pytest
cd science && uv run --frozen pytest \
  tests/test_evidence_broker_hits.py \
  tests/test_evidence_broker_correspondence.py \
  tests/test_evidence_broker_serve.py \
  tests/test_autonomy_git_canonical.py -q
cd science/model && uv run --frozen ruff check src/science_model/correspondence.py tests/test_correspondence.py
cd science && uv run --frozen ruff check \
  src/science_tool/evidence_broker/hits.py \
  src/science_tool/evidence_broker/correspondence.py \
  tests/test_evidence_broker_hits.py \
  tests/test_evidence_broker_correspondence.py
cd science && uv run --frozen pyright
```

Run sequentially; do not overlap pytest invocations in one worktree.

- [ ] **Step 6: Commit any test repairs made during certification**

If every mutation already turned red, make no empty commit. Otherwise:

```bash
git add science/model/tests/test_correspondence.py \
  science/tests/test_evidence_broker_hits.py \
  science/tests/test_evidence_broker_correspondence.py
git commit -m "test(evidence-broker): certify checker guards"
```

---

## Final Review Gate

Review the cumulative diff against these questions before declaring plan 4b implemented:

1. Does `git diff --name-only d5bf01e2...HEAD` show only the three new production files, their three
   test files, this plan, and any explicit design-status update?
2. Can `science_model.correspondence` import in a fresh interpreter without loading
   `science_model.audit`?
3. Does `check_correspondence` accept `Sequence[Evidence]`, not `Review`, and
   `EvidenceExposure | None`, not a live session?
4. Is protocol mismatch returned before any git call?
5. Is `verify_commit` the existing helper, with the only `except ServeError` wrapped immediately
   around it?
6. Do replay-time `ServeError`, `GitError`, and parser failures propagate?
7. Are replay integrity and outcome checked before any citation?
8. Is the merge total over all ten unordered coverage pairs, with `Full(min)` and `Lines(union)`?
9. Are search-hit paths used directly, without normalization, and search regex targets replayed raw?
10. Is there no production caller, stored-record change, eligibility logic, validate registration,
    or `serve.py` modification?

## Self-review Notes

**Spec coverage.** §5's signature and `None` outcome → Task 4. Dependency-neutral `Correspondence`
and its import row → Task 1. Canonical hit parsing → Task 2. §5.1's line count, ten-pair merge, and
citation predicate → Task 3. §5.2 replay, inline agreement, local cache, propagation, and no
normalization → Task 4. §5.3's six verdict rows and exact order → Task 4. Every §7 plan-4b mutation
row, plus the parser's LF-record and one-based-line guards → Task 5.

**Out of scope deliberately.** Plan 4c owns every `Review`/case-store change, `append_review`, agent
attestation, eligibility, and validate notice. The existing permissive `InlineInput.lines` count on
CR-bearing files remains the design's recorded follow-up; 4b uses the sealed value and does not edit
plan 4a's lifecycle/model surface. Plan 4c also owes §7's end-to-end refusal guard through
`append_review`; Task 4's refused-read test certifies only the checker layer and does not discharge
that production-path obligation.

**No speculative API.** Coverage stays local, the package exports stay unchanged, parser errors use
`ValueError`, and the checker has no wrapper/facade or production registration before a caller exists.

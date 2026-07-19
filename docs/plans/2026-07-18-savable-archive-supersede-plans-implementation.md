# Savable archive / mark-superseded plans — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add durable `--save-plan` / `--apply-plan` to `science entities archive` and `entities mark-superseded`, so a curation mutation can be previewed, frozen, and replayed byte-exactly (ships as `science` 0.5.0).

**Architecture:** A saved plan freezes the decision read set and the mutation write set with exact pre/post states. `--apply-plan` authorizes in three layers — a mandatory raw-bytes approval envelope, a corpus-drift digest (supersession only), and a derivation gate that re-renders the expected writes and compares them byte-for-byte — then writes only the saved postimages through a staged-write algorithm with ownership-scoped rollback. Shared primitives live in a new `plan_common.py`; each command gets its own `*_plan.py`.

**Tech Stack:** Python 3, Pydantic v2, Click, pytest. Repo `~/d/science`, source under `science/src/science_tool/`, model under `model/src/science_model/`, tests under `science/tests/`.

**Design authority:** `docs/plans/2026-07-18-savable-archive-supersede-plans-design.md` (read it first; section refs below point into it).

## Global Constraints

Every task's requirements implicitly include these — copy exact values verbatim.

- **Pydantic:** every persisted model sets `model_config = ConfigDict(extra="forbid")`.
- **Approval envelope is MANDATORY** (design §1). `--apply-plan` requires `--expected-plan-sha256`; it is SHA-256 over the **raw plan-file bytes**, and the file is **read exactly once** into a `raw: bytes` buffer — hash `raw`, then parse `raw` — never reopen the path.
- **Staged replacement uses `os.replace`**; `os.rename` is reserved for archive src→absent-dst moves and refuses `EXDEV` loudly (design §3.4, §4.3). A staged file is `fchmod`'d to the saved `mode` on its open descriptor **before** the file `fsync` (umask-independent); created dirs are `chmod`'d to their saved mode.
- **Staging path is derived, never trusted from JSON:** `<rel_path>.<staging-token>.tmp`, sibling, contained, unique, created with `O_EXCL` (design §3.2, §3.4). Standalone CLI apply generates and reports a unique token; it is never a fixed constant.
- **Every declared path is resolved through `resolve_within` before any filesystem access** (containment + canonical form; an absolute or `..`-bearing `rel_path` is rejected). Both apply paths authorize the **complete** surface by re-deriving the whole plan and comparing it (writes/moves/transitions/index + `preview_report`) — not a subset of fields (design §3.3, §4.4, §5.5).
- **Snapshots capture complete pre-state** (existence, type, mode, symlink target, and file bytes), and rollback reconstructs files, directories, and symlinks — never `bytes | None` alone.
- **The write path keeps `_parse_markdown_file`'s existing normalization** (lstrip leading newlines + line-ending normalization). Only the `updated` default becomes injectable via `preview_date`. Do NOT switch to a body-preserving parser (design §5.4). No "body round-trips byte-for-byte" claim — gate B compares against the **normalized** postimage the legacy writer produces.
- **The shared preparation function retains all three `_prepare_write` boundary checks:** `_schema_gate_or_raise` (`entities.py:1072`), `_validate_prospective_write` (`entities.py:1075`), `_resolution_check_or_raise` (`entities.py:1083`). Preview, legacy `--apply`, and `--apply-plan` all route through it.
- **The plan stores a `preview_report` (dry-run semantics), not an execution report.** `applied`/`repaired`/`skipped` are populated only after execution; apply emits a **separate** execution report (design §4.4, §5.5).
- **Selection lists** (ids/statuses) are enforced non-empty, unique, canonically ordered by **model validators**, not comments (design §3.5).
- **Version bump = three edits + one unchanged test** (design §8): `science/pyproject.toml:3`, `.claude-plugin/plugin.json:3`, `science/tests/test_cli_version.py:27`; `test_agent_cli_compatibility.py` runs unchanged.
- **Command working directories (verified).** There is no root `pyproject.toml`. All `uv`/`pytest` commands MUST run from `~/d/science/science` — running them from the repo root fails, because `tests/conftest.py` imports `science_model`, giving `ModuleNotFoundError: No module named 'science_model'` (reproduced). Every `Run:` pytest path in this plan is therefore relative to `~/d/science/science` (e.g. `tests/test_plan_common.py`). **`git` commands and the repo validator run from the repo root `~/d/science`:** `git add` paths stay repo-relative (`science/src/...`, `.claude-plugin/plugin.json`), and the validator is `bash scripts/validate.sh --verbose` (it lives at `scripts/validate.sh`, not the repo root).
- **House style:** `from __future__ import annotations`; absolute imports; tests use `CliRunner` + `tmp_path` + inline `science.yaml`/entity fixtures. No AI-attribution trailers in commits.

---

## File Structure

- **Create `science/src/science_tool/plan_common.py`** — shared primitives: `StateFingerprint`, `fingerprint`, `matches`; `PathTransition`; `ArchiveSelection`/`SupersedeSelection` unions; envelope helpers (`read_plan_bytes`, `plan_sha256`, `verify_envelope`); staging (`staging_path_for`, `staged_write`, `classify_staging`); snapshot/rollback (`snapshot_paths`, `rollback_transitions`). One responsibility: the command-agnostic transaction mechanics.
- **Create `science/src/science_tool/supersede_plan.py`** — `SupersessionDecisionMaterial` is imported from `consolidation.py`; defines `SupersedePreviewReport`, `SupersedePlan`, `plan_supersede`, `apply_supersede_plan`.
- **Create `science/src/science_tool/archive_plan.py`** — `ArchivePreviewReport`, `ArchivePlan`, `ArchiveMove`, `plan_archive`, `apply_archive_plan`.
- **Modify `science/src/science_tool/entities.py`** — extract `_prepare_write_with_date(...)` retaining the three boundary checks; `_prepare_write` becomes a thin wrapper injecting `date.today()`.
- **Modify `science/src/science_tool/consolidation.py`** — add serializable `SupersessionDecisionMaterial` + `build_decision_material` + `decision_digest`; `build_supersedes_graph` consumes the material; `_prepare_supersession` takes an injected `preview_date`.
- **Modify `science/src/science_tool/entities_inventory_cli.py`** — add `--save-plan`/`--apply-plan`/`--expected-plan-sha256`/`--staging-token`/`--overwrite-plan` to both `entities archive` and `entities mark-superseded`.
- **Modify** `science/pyproject.toml`, `.claude-plugin/plugin.json`, `science/tests/test_cli_version.py` — the 0.5.0 bump.
- **Create tests** alongside: `test_plan_common.py`, `test_supersede_plan.py`, `test_archive_plan.py`, `test_prepare_write_injectable.py`, `test_decision_material.py`, and extend `test_science_cli_surface.py` (consumer-side, natural-systems — noted in the delivery task).

---

## Phase 0 — Shared primitives (`plan_common.py`)

### Task 1: `StateFingerprint` + `fingerprint` + `matches`

**Files:**
- Create: `science/src/science_tool/plan_common.py`
- Test: `science/tests/test_plan_common.py`

**Interfaces:**
- Produces: `StateFingerprint` (pydantic, fields `existed: bool`, `type: Literal["file","dir","symlink"] | None`, `content_sha256: str | None`, `mode: int | None`, `symlink_target: str | None`; a `model_validator` enforces field coherence per existence/type); `fingerprint(path: Path) -> StateFingerprint` (raises `UnsupportedPathType` for anything that is not a regular file, directory, or symlink — a FIFO/socket/device must never be `read_bytes()`'d); `matches(fp: StateFingerprint, path: Path) -> bool`; `UnsupportedPathType(RuntimeError)`.

- [ ] **Step 1: Write the failing test**

```python
# science/tests/test_plan_common.py
from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

from science_tool.plan_common import (
    StateFingerprint, UnsupportedPathType, fingerprint, matches,
)


def test_fingerprint_of_a_file_captures_content_mode_and_type(tmp_path: Path) -> None:
    p = tmp_path / "a.txt"
    p.write_text("hello", encoding="utf-8")
    os.chmod(p, 0o644)
    fp = fingerprint(p)
    assert fp.existed is True
    assert fp.type == "file"
    assert fp.content_sha256 == hashlib.sha256(b"hello").hexdigest()
    assert fp.mode == 0o644
    assert fp.symlink_target is None
    assert matches(fp, p) is True


def test_fingerprint_of_absent_path(tmp_path: Path) -> None:
    fp = fingerprint(tmp_path / "missing")
    assert fp.existed is False
    assert fp.type is None
    assert fp.content_sha256 is None
    assert matches(fp, tmp_path / "missing") is True


def test_fingerprint_of_symlink_records_target_not_content(tmp_path: Path) -> None:
    target = tmp_path / "t.txt"
    target.write_text("x", encoding="utf-8")
    link = tmp_path / "l"
    link.symlink_to("t.txt")
    fp = fingerprint(link)
    assert fp.type == "symlink"
    assert fp.symlink_target == "t.txt"
    assert fp.content_sha256 is None


def test_fingerprint_of_directory_records_mode_not_content(tmp_path: Path) -> None:
    d = tmp_path / "sub"
    d.mkdir()
    os.chmod(d, 0o755)
    fp = fingerprint(d)
    assert fp.type == "dir"
    assert fp.content_sha256 is None
    assert fp.symlink_target is None
    assert fp.mode == 0o755


def test_fingerprint_refuses_unsupported_fs_object(tmp_path: Path) -> None:
    fifo = tmp_path / "pipe"
    os.mkfifo(fifo)  # a FIFO would block read_bytes()
    with pytest.raises(UnsupportedPathType):
        fingerprint(fifo)


def test_matches_is_false_when_content_changes(tmp_path: Path) -> None:
    p = tmp_path / "a.txt"
    p.write_text("hello", encoding="utf-8")
    fp = fingerprint(p)
    p.write_text("world", encoding="utf-8")
    assert matches(fp, p) is False


def test_extra_forbid_on_state_fingerprint() -> None:
    with pytest.raises(ValueError):
        StateFingerprint(existed=False, type=None, content_sha256=None, mode=None,
                         symlink_target=None, bogus=1)  # type: ignore[call-arg]


@pytest.mark.parametrize("kwargs", [
    # present but no type
    dict(existed=True, type=None, content_sha256=None, mode=0o644, symlink_target=None),
    # absent but carries attributes
    dict(existed=False, type=None, content_sha256="x" * 64, mode=None, symlink_target=None),
    # file without content
    dict(existed=True, type="file", content_sha256=None, mode=0o644, symlink_target=None),
    # symlink without target
    dict(existed=True, type="symlink", content_sha256=None, mode=0o777, symlink_target=None),
    # dir carrying content
    dict(existed=True, type="dir", content_sha256="x" * 64, mode=0o755, symlink_target=None),
    # present without mode
    dict(existed=True, type="file", content_sha256="x" * 64, mode=None, symlink_target=None),
])
def test_state_fingerprint_rejects_incoherent_combinations(kwargs: dict) -> None:
    with pytest.raises(ValueError):
        StateFingerprint(**kwargs)  # type: ignore[arg-type]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --frozen pytest tests/test_plan_common.py -q`
Expected: FAIL — `ModuleNotFoundError: science_tool.plan_common`.

- [ ] **Step 3: Write minimal implementation**

```python
# science/src/science_tool/plan_common.py
from __future__ import annotations

import hashlib
import os
import stat
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator


class UnsupportedPathType(RuntimeError):
    pass


class StateFingerprint(BaseModel):
    model_config = ConfigDict(extra="forbid")
    existed: bool
    type: Literal["file", "dir", "symlink"] | None
    content_sha256: str | None
    mode: int | None
    symlink_target: str | None

    @model_validator(mode="after")
    def _coherent(self) -> "StateFingerprint":
        if not self.existed:
            if any(v is not None for v in
                   (self.type, self.content_sha256, self.mode, self.symlink_target)):
                raise ValueError("absent fingerprint must carry all attributes None")
            return self
        if self.type is None:
            raise ValueError("present fingerprint requires a type")
        if self.mode is None:
            raise ValueError("present fingerprint requires a mode")
        if self.type == "file":
            if self.content_sha256 is None or self.symlink_target is not None:
                raise ValueError("file fingerprint needs content_sha256 and no symlink_target")
        elif self.type == "dir":
            if self.content_sha256 is not None or self.symlink_target is not None:
                raise ValueError("dir fingerprint carries neither content nor symlink_target")
        else:  # symlink
            if self.symlink_target is None or self.content_sha256 is not None:
                raise ValueError("symlink fingerprint needs symlink_target and no content_sha256")
        return self


def fingerprint(path: Path) -> StateFingerprint:
    try:
        st = os.lstat(path)
    except FileNotFoundError:
        return StateFingerprint(existed=False, type=None, content_sha256=None,
                                mode=None, symlink_target=None)
    mode = stat.S_IMODE(st.st_mode)
    if stat.S_ISLNK(st.st_mode):
        return StateFingerprint(existed=True, type="symlink", content_sha256=None,
                                mode=mode, symlink_target=os.readlink(path))
    if stat.S_ISDIR(st.st_mode):
        return StateFingerprint(existed=True, type="dir", content_sha256=None,
                                mode=mode, symlink_target=None)
    if not stat.S_ISREG(st.st_mode):
        # A FIFO, socket, or device: fail early -- read_bytes() on a FIFO blocks forever,
        # and none of these are things this transaction machinery ever legitimately touches.
        raise UnsupportedPathType(
            f"unsupported filesystem object at {path}: not a regular file, directory, or symlink"
        )
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    return StateFingerprint(existed=True, type="file", content_sha256=sha,
                            mode=mode, symlink_target=None)


def matches(fp: StateFingerprint, path: Path) -> bool:
    return fingerprint(path) == fp
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --frozen pytest tests/test_plan_common.py -q`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/plan_common.py science/tests/test_plan_common.py
git commit -m "feat(curation): StateFingerprint + fingerprint/matches"
```

---

### Task 2: `PathTransition` with cross-field validators

**Files:**
- Modify: `science/src/science_tool/plan_common.py`
- Test: `science/tests/test_plan_common.py`

**Interfaces:**
- Produces: `PathTransition` (fields `role: Literal["entity-rewrite","archive-src","archive-dst","archive-index","created-dir"]`, `rel_path: str`, `pre: StateFingerprint`, `post: StateFingerprint`, `postimage: str | None`). Validators enforce the design §3.2 role/field coherence, including `post.content_sha256 == sha256(postimage)` for staged-write roles.

- [ ] **Step 1: Write the failing test**

```python
# append to science/tests/test_plan_common.py
import hashlib as _hashlib

from science_tool.plan_common import PathTransition


def _file_fp(content: str) -> StateFingerprint:
    return StateFingerprint(existed=True, type="file",
                            content_sha256=_hashlib.sha256(content.encode()).hexdigest(),
                            mode=0o644, symlink_target=None)


def _absent_fp() -> StateFingerprint:
    return StateFingerprint(existed=False, type=None, content_sha256=None, mode=None, symlink_target=None)


def test_entity_rewrite_requires_postimage_hash_to_match_post() -> None:
    body = "new bytes"
    t = PathTransition(role="entity-rewrite", rel_path="entities/x/1.md",
                       pre=_file_fp("old"), post=_file_fp(body), postimage=body)
    assert t.postimage == body


def test_entity_rewrite_rejects_postimage_hash_mismatch() -> None:
    with pytest.raises(ValueError):
        PathTransition(role="entity-rewrite", rel_path="entities/x/1.md",
                       pre=_file_fp("old"), post=_file_fp("A"), postimage="B")


def test_archive_src_post_must_be_absent() -> None:
    with pytest.raises(ValueError):
        PathTransition(role="archive-src", rel_path="entities/x/1.md",
                       pre=_file_fp("x"), post=_file_fp("x"), postimage=None)


def test_created_dir_has_no_postimage_and_absent_pre() -> None:
    dir_post = StateFingerprint(existed=True, type="dir", content_sha256=None, mode=0o755, symlink_target=None)
    t = PathTransition(role="created-dir", rel_path="entities/_archive/x",
                       pre=_absent_fp(), post=dir_post, postimage=None)
    assert t.postimage is None
    with pytest.raises(ValueError):
        PathTransition(role="created-dir", rel_path="entities/_archive/x",
                       pre=_absent_fp(), post=dir_post, postimage="oops")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --frozen pytest tests/test_plan_common.py -q`
Expected: FAIL — `ImportError: cannot import name 'PathTransition'`.

- [ ] **Step 3: Write minimal implementation**

```python
# add to science/src/science_tool/plan_common.py
# (`hashlib` and `model_validator` are already imported in Task 1's block.)

_STAGED_ROLES = {"entity-rewrite", "archive-index"}


class PathTransition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Literal["entity-rewrite", "archive-src", "archive-dst", "archive-index", "created-dir"]
    rel_path: str
    pre: StateFingerprint
    post: StateFingerprint
    postimage: str | None = None

    @model_validator(mode="after")
    def _coherent(self) -> "PathTransition":
        if self.role in _STAGED_ROLES:
            if self.postimage is None:
                raise ValueError(f"{self.role} requires a postimage")
            if not (self.post.existed and self.post.type == "file"):
                raise ValueError(f"{self.role} post must be an existing file")
            want = hashlib.sha256(self.postimage.encode("utf-8")).hexdigest()
            if self.post.content_sha256 != want:
                raise ValueError("post.content_sha256 does not match sha256(postimage)")
        else:
            if self.postimage is not None:
                raise ValueError(f"{self.role} must not carry a postimage")
        if self.role == "archive-src" and self.post.existed:
            raise ValueError("archive-src post must be absent (the source is moved away)")
        if self.role in {"archive-dst", "created-dir"} and self.pre.existed:
            raise ValueError(f"{self.role} pre must be absent (it is created)")
        if self.role == "created-dir" and self.post.type != "dir":
            raise ValueError("created-dir post must be a directory")
        return self
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --frozen pytest tests/test_plan_common.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/plan_common.py science/tests/test_plan_common.py
git commit -m "feat(curation): PathTransition with role/field cross-validators"
```

---

### Task 3: Selection unions with canonical-order validators

**Files:**
- Modify: `science/src/science_tool/plan_common.py`
- Test: `science/tests/test_plan_common.py`

**Interfaces:**
- Produces: `ArchiveSelection` = `ArchiveStatusSweep{statuses}` | `ExplicitArchiveIds{ids, allowed_statuses}`; `SupersedeSelection` = `AllSupersessionMembers` | `ExplicitSupersessionIds{ids}`. Explicit lists validated non-empty, unique, sorted.

- [ ] **Step 1: Write the failing test**

```python
# append to science/tests/test_plan_common.py
from science_tool.plan_common import (
    ArchiveStatusSweep, ExplicitArchiveIds, AllSupersessionMembers, ExplicitSupersessionIds,
)


def test_explicit_ids_reject_empty_and_unsorted_and_duplicate() -> None:
    with pytest.raises(ValueError):
        ExplicitSupersessionIds(kind="explicit_ids", ids=[])
    with pytest.raises(ValueError):
        ExplicitSupersessionIds(kind="explicit_ids", ids=["b:2", "a:1"])  # unsorted
    with pytest.raises(ValueError):
        ExplicitSupersessionIds(kind="explicit_ids", ids=["a:1", "a:1"])  # duplicate
    ok = ExplicitSupersessionIds(kind="explicit_ids", ids=["a:1", "b:2"])
    assert ok.ids == ["a:1", "b:2"]


def test_archive_status_sweep_and_explicit_ids_shapes() -> None:
    ArchiveStatusSweep(kind="all_by_status", statuses=["archived", "superseded"])
    ExplicitArchiveIds(kind="explicit_ids", ids=["x:1"], allowed_statuses=["superseded"])
    AllSupersessionMembers(kind="all")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --frozen pytest tests/test_plan_common.py -q`
Expected: FAIL — import error.

- [ ] **Step 3: Write minimal implementation**

```python
# add to science/src/science_tool/plan_common.py
from typing import Annotated
from pydantic import Field, field_validator


def _canonical_nonempty(values: list[str]) -> list[str]:
    if not values:
        raise ValueError("explicit selection list must be non-empty")
    if len(set(values)) != len(values):
        raise ValueError("explicit selection list must be unique")
    if list(values) != sorted(values):
        raise ValueError("explicit selection list must be canonically (sorted) ordered")
    return values


class ArchiveStatusSweep(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["all_by_status"]
    statuses: list[str]

    @field_validator("statuses")
    @classmethod
    def _v(cls, v: list[str]) -> list[str]:
        return _canonical_nonempty(v)


class ExplicitArchiveIds(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["explicit_ids"]
    ids: list[str]
    allowed_statuses: list[str]

    @field_validator("ids", "allowed_statuses")
    @classmethod
    def _v(cls, v: list[str]) -> list[str]:
        return _canonical_nonempty(v)


class AllSupersessionMembers(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["all"]


class ExplicitSupersessionIds(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["explicit_ids"]
    ids: list[str]

    @field_validator("ids")
    @classmethod
    def _v(cls, v: list[str]) -> list[str]:
        return _canonical_nonempty(v)


ArchiveSelection = Annotated[ArchiveStatusSweep | ExplicitArchiveIds, Field(discriminator="kind")]
SupersedeSelection = Annotated[AllSupersessionMembers | ExplicitSupersessionIds, Field(discriminator="kind")]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --frozen pytest tests/test_plan_common.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/plan_common.py science/tests/test_plan_common.py
git commit -m "feat(curation): command-specific selection unions with canonical validators"
```

---

### Task 4: Approval envelope — single immutable read

**Files:**
- Modify: `science/src/science_tool/plan_common.py`
- Test: `science/tests/test_plan_common.py`

**Interfaces:**
- Produces: `read_plan_bytes(path: Path) -> bytes` (one read); `plan_sha256(raw: bytes) -> str`; `verify_envelope(raw: bytes, expected_sha256: str) -> None` (raises `EnvelopeError` on mismatch). `EnvelopeError(RuntimeError)`.

- [ ] **Step 1: Write the failing test**

```python
# append to science/tests/test_plan_common.py
from science_tool.plan_common import EnvelopeError, plan_sha256, read_plan_bytes, verify_envelope


def test_envelope_accepts_matching_and_rejects_mismatch(tmp_path: Path) -> None:
    p = tmp_path / "plan.json"
    p.write_bytes(b'{"a": 1}')
    raw = read_plan_bytes(p)
    assert raw == b'{"a": 1}'
    verify_envelope(raw, plan_sha256(raw))  # no raise
    with pytest.raises(EnvelopeError):
        verify_envelope(raw, "0" * 64)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --frozen pytest tests/test_plan_common.py -q`
Expected: FAIL — import error.

- [ ] **Step 3: Write minimal implementation**

```python
# add to science/src/science_tool/plan_common.py
import hmac


class EnvelopeError(RuntimeError):
    pass


def read_plan_bytes(path: Path) -> bytes:
    """Read the plan file EXACTLY once; callers hash and parse this same buffer."""
    return path.read_bytes()


def plan_sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def verify_envelope(raw: bytes, expected_sha256: str) -> None:
    actual = plan_sha256(raw)
    if not hmac.compare_digest(actual, expected_sha256):  # constant-time; hashlib has no compare_digest
        raise EnvelopeError(
            "plan bytes do not match --expected-plan-sha256 (approval envelope); "
            "the saved plan was not the one approved"
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --frozen pytest tests/test_plan_common.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/plan_common.py science/tests/test_plan_common.py
git commit -m "feat(curation): approval-envelope single-read digest verification"
```

---

### Task 5: Staged-write algorithm + prefix classifier

**Files:**
- Modify: `science/src/science_tool/plan_common.py`
- Test: `science/tests/test_plan_common.py`

**Interfaces:**
- Produces: `staging_path_for(target: Path, token: str) -> Path` (`<target>.<token>.tmp`); `staged_write(target: Path, postimage: str, mode: int, token: str, *, target_pre: StateFingerprint, _fault: Callable[[str], None] | None = None) -> None` (`target_pre` is **mandatory and keyword-only** — every production call and every test already holds the frozen pre-state, so there is no prefix-only cleanup path to fall into. O_EXCL tmp → write → **`_fault("mid-write")` seam** → fchmod → fsync → `os.replace`; the `except Exception` cleanup removes a survivor only when it is an attributable byte-prefix of the postimage **and** `target_pre` still matches the live target — a concurrent target change preserves the survivor and halts, per design §3.3); `classify_staging(staging: Path, postimage: str) -> Literal["absent","prefix","complete"]`. `_fault` is test-only: raising a `BaseException` from it simulates a mid-staging kill (skips cleanup → partial `.tmp` preserved). `StagingError(RuntimeError)`.

- [ ] **Step 1: Write the failing test**

```python
# append to science/tests/test_plan_common.py
from science_tool.plan_common import StagingError, classify_staging, staged_write, staging_path_for


def test_staged_write_replaces_atomically_with_mode(tmp_path: Path) -> None:
    target = tmp_path / "entities" / "x" / "1.md"
    target.parent.mkdir(parents=True)
    target.write_text("old", encoding="utf-8")
    staged_write(target, "new-bytes", 0o644, token="batch1", target_pre=fingerprint(target))
    assert target.read_text(encoding="utf-8") == "new-bytes"
    assert (os.stat(target).st_mode & 0o777) == 0o644
    assert not staging_path_for(target, "batch1").exists()  # tmp consumed


def test_staged_write_refuses_preexisting_staging_file(tmp_path: Path) -> None:
    target = tmp_path / "a.md"
    target.write_text("x", encoding="utf-8")
    staging_path_for(target, "batch1").write_text("stale", encoding="utf-8")
    with pytest.raises(StagingError):
        staged_write(target, "y", 0o644, token="batch1", target_pre=fingerprint(target))


def test_classify_staging_absent_prefix_complete(tmp_path: Path) -> None:
    target = tmp_path / "a.md"
    staging = staging_path_for(target, "b")
    assert classify_staging(staging, "hello") == "absent"
    staging.write_text("hel", encoding="utf-8")
    assert classify_staging(staging, "hello") == "prefix"
    staging.write_text("hello", encoding="utf-8")
    assert classify_staging(staging, "hello") == "complete"
    staging.write_text("hellX", encoding="utf-8")
    with pytest.raises(StagingError):
        classify_staging(staging, "hello")  # not a prefix -> interference


def test_staged_write_mid_kill_leaves_attributable_prefix_and_untouched_target(tmp_path: Path) -> None:
    # C3 / design §3.4: a kill DURING staging (BaseException from the `_fault` seam, after the write
    # but before replace) must leave the real writer in only-modeled state — a partial `.tmp` that is
    # a byte-prefix of the postimage, the target unchanged, and no other debris in the directory.
    class _Kill(BaseException):
        pass

    target = tmp_path / "entities" / "x" / "1.md"
    target.parent.mkdir(parents=True)
    target.write_text("original", encoding="utf-8")

    def fault(label: str) -> None:
        if label == "mid-write":
            raise _Kill()

    postimage = "brand-new-postimage"
    with pytest.raises(_Kill):
        staged_write(target, postimage, 0o644, token="batch1", target_pre=fingerprint(target), _fault=fault)

    assert target.read_text(encoding="utf-8") == "original"  # target never touched (attributable state)
    survivor = staging_path_for(target, "batch1")
    survivor_bytes = survivor.read_bytes()
    assert 0 < len(survivor_bytes) < len(postimage.encode())         # a STRICT, non-empty prefix
    assert classify_staging(survivor, postimage) == "prefix"          # not "complete"
    # no undeclared debris — only the target and the one attributable staging survivor exist
    assert {p.name for p in target.parent.iterdir()} == {target.name, survivor.name}


def test_staged_write_caught_error_removes_only_attributable_survivor(tmp_path: Path, monkeypatch) -> None:
    # The `except Exception` cleanup removes our own partial write when it is an attributable prefix.
    target = tmp_path / "a.md"
    target.write_text("x", encoding="utf-8")

    def boom(*a, **k):
        raise RuntimeError("replace failed")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(RuntimeError, match="replace failed"):
        staged_write(target, "hello", 0o644, token="b", target_pre=fingerprint(target))
    assert not staging_path_for(target, "b").exists()              # attributable prefix → cleaned up
    assert target.read_text(encoding="utf-8") == "x"               # target untouched (atomic replace)


def test_staged_write_refuses_to_remove_a_non_prefix_survivor(tmp_path: Path, monkeypatch) -> None:
    # If the survivor is NOT a byte-prefix of the postimage (concurrent interference), cleanup refuses
    # to delete it and raises — surfacing the anomaly instead of erasing evidence. Target stays put.
    target = tmp_path / "a.md"
    target.write_text("x", encoding="utf-8")

    def corrupt_then_fail(src, dst):
        Path(src).write_bytes(b"FOREIGN-NON-PREFIX")  # something we did not write appears at the tmp
        raise RuntimeError("replace failed")

    monkeypatch.setattr(os, "replace", corrupt_then_fail)
    with pytest.raises(StagingError, match="not an attributable prefix"):
        staged_write(target, "hello", 0o644, token="b", target_pre=fingerprint(target))
    assert staging_path_for(target, "b").exists()                  # NOT deleted — evidence preserved
    assert target.read_text(encoding="utf-8") == "x"               # target untouched


def test_staged_write_halts_when_target_changed_concurrently(tmp_path: Path, monkeypatch) -> None:
    # Critical (design §3.3): a survivor is removed only when the persistent TARGET is ALSO still
    # attributable to this op. If `os.replace` fails AFTER a concurrent writer changed the target, our
    # staged survivor is preserved as recovery evidence and the op HALTS — deleting it would erase the
    # only record that a write was in flight when the corpus diverged. The prefix predicate alone
    # (satisfied here — the survivor is a complete, attributable write) is NOT sufficient.
    target = tmp_path / "a.md"
    target.write_text("original", encoding="utf-8")
    target_pre = fingerprint(target)

    def change_target_then_fail(src, dst):
        Path(dst).write_bytes(b"CONCURRENT-EDIT-BY-SOMEONE-ELSE")  # target diverges before replace fails
        raise RuntimeError("replace failed")

    monkeypatch.setattr(os, "replace", change_target_then_fail)
    with pytest.raises(StagingError, match="target changed concurrently"):
        staged_write(target, "hello", 0o644, token="b", target_pre=target_pre)
    assert staging_path_for(target, "b").exists()                  # survivor preserved as evidence
    assert target.read_text(encoding="utf-8") == "CONCURRENT-EDIT-BY-SOMEONE-ELSE"  # target left as-found
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --frozen pytest tests/test_plan_common.py -q`
Expected: FAIL — import error.

- [ ] **Step 3: Write minimal implementation**

```python
# add to science/src/science_tool/plan_common.py
from typing import Callable  # add to the existing typing import at the top of the module


class StagingError(RuntimeError):
    pass


def staging_path_for(target: Path, token: str) -> Path:
    return target.with_name(f"{target.name}.{token}.tmp")


def staged_write(target: Path, postimage: str, mode: int, token: str, *,
                 target_pre: "StateFingerprint",
                 _fault: Callable[[str], None] | None = None) -> None:
    # `_fault` is a TEST-ONLY seam: a test raises a `BaseException` from it to simulate a process
    # kill mid-staging. Because it is a BaseException, the `except Exception` cleanup below does NOT
    # run — the partial `.tmp` survives, exactly as an uncaught SIGKILL would leave it, so the kill
    # test can assert the survivor is an attributable byte-prefix of the postimage (design §3.4).
    staging = staging_path_for(target, token)
    data = postimage.encode("utf-8")
    try:
        fd = os.open(staging, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    except FileExistsError as exc:
        raise StagingError(f"staging path already exists: {staging}") from exc
    try:
        with os.fdopen(fd, "wb") as fh:
            if _fault is not None and len(data) > 1:
                # TEST SEAM: land a STRICT, non-empty prefix on disk (flushed + fsync'd), then simulate
                # a kill BEFORE the rest is written. A BaseException from `_fault` unwinds the `with`
                # (flushing an already-empty buffer), so the survivor is exactly the prefix — a genuine
                # partial, shorter than `data`, never the complete file. If `_fault` does NOT raise, the
                # remaining bytes are written, so the primitive is never left corrupt by a no-op seam.
                half = len(data) // 2
                fh.write(data[:half])
                fh.flush()
                os.fsync(fh.fileno())
                _fault("mid-write")
                fh.write(data[half:])
            else:
                fh.write(data)
            fh.flush()
            os.fchmod(fh.fileno(), mode)  # O_EXCL creation mode is umask-masked; force exact bits
            os.fsync(fh.fileno())         # ...and fsync AFTER the mode is set, on the same fd
        os.replace(staging, target)
        dir_fd = os.open(target.parent, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except Exception:
        # Attribution-aware cleanup (design §3.3/§3.4): remove a survivor ONLY when BOTH hold —
        # (1) it is our own O_EXCL-created partial (a byte-prefix of the intended postimage), AND
        # (2) the persistent target is still attributable to this op (unchanged from `target_pre`).
        # A non-prefix survivor, or a target a concurrent writer changed, is interference: refuse to
        # delete our staged bytes and surface the anomaly rather than erase recovery evidence. (A kill
        # via `_fault` is a BaseException and skips this handler entirely, so the partial .tmp is
        # preserved for classification.)
        if staging.exists():
            survivor = staging.read_bytes()
            if not data.startswith(survivor):
                raise StagingError(
                    f"staging survivor is not an attributable prefix, not removing: {staging}")
            if not matches(target_pre, target):
                raise StagingError(
                    f"target changed concurrently during staging; preserving survivor as evidence: {staging}")
            staging.unlink()  # our own partial (or complete) write AND target still ours; safe to remove
        raise


def classify_staging(staging: Path, postimage: str) -> str:
    if not staging.exists():
        return "absent"
    data = staging.read_bytes()
    want = postimage.encode("utf-8")
    if data == want:
        return "complete"
    if want.startswith(data):
        return "prefix"
    raise StagingError(f"staging survivor is not a prefix of the postimage: {staging}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --frozen pytest tests/test_plan_common.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/plan_common.py science/tests/test_plan_common.py
git commit -m "feat(curation): staged-write (O_EXCL/fchmod/os.replace) + prefix classifier"
```

---

### Task 6: Full-state snapshot, ownership-scoped rollback, and structural validation

This task carries three related pieces of the command-agnostic transaction mechanics: a
snapshot that captures **complete** pre-state (not just bytes), a rollback that reconstructs
files, directories, and symlinks from it, and the shared structural validator both apply paths
run before touching the filesystem (containment, canonical rel-path, and declared-vs-derived
surface equality). They ship together because rollback and the validator both depend on the
snapshot record and on `resolve_within`.

**Files:**
- Modify: `science/src/science_tool/plan_common.py`
- Test: `science/tests/test_plan_common.py`

**Interfaces:**
- Produces:
  - `PathSnapshot` (frozen dataclass: `fp: StateFingerprint`, `content: bytes | None` — bytes only for regular files); `snapshot_paths(paths: list[Path]) -> dict[Path, PathSnapshot]`.
  - `rollback_transitions(transitions, project_root, snapshot) -> None` — processes transitions in **reverse** order (so a created directory is removed only after the files moved into it are reverted); for each, reverts to `pre` **only if** live matches `post`, skips if live matches `pre`, else raises `RollbackHalt`. Reconstructs files (bytes + exact mode), directories (mkdir + mode, empty-only removal), and symlinks (recreate target). `RollbackHalt(RuntimeError)`.
  - `resolve_within(project_root: Path, rel_path: str) -> Path` — refuses absolute paths, non-canonical forms (`os.path.normpath` mismatch), `..` escape; returns the contained absolute path. `PathEscape(RuntimeError)`.
  - `assert_same_surface(declared: list[PathTransition], expected: list[PathTransition]) -> None` — order-independent equality over `(role, rel_path, pre, post, postimage)`; raises `SurfaceMismatch(RuntimeError)`.
  - `assert_staging_unique(project_root: Path, staged_targets: list[Path], token: str) -> None` — staging paths distinct and contained; raises `StagingError`.

- [ ] **Step 1: Write the failing test**

```python
# append to science/tests/test_plan_common.py
import os as _os

from science_tool.plan_common import (
    PathEscape, RollbackHalt, SurfaceMismatch, assert_same_surface, assert_staging_unique,
    resolve_within, rollback_transitions, snapshot_paths,
)


def test_rollback_reverts_a_completed_write_to_pre(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text("name: t\n", encoding="utf-8")
    target = tmp_path / "e.md"
    target.write_text("OLD", encoding="utf-8")
    pre = fingerprint(target)
    snap = snapshot_paths([target])
    target.write_text("NEW", encoding="utf-8")  # simulate the write landed
    post = fingerprint(target)
    t = PathTransition(role="entity-rewrite", rel_path="e.md", pre=pre, post=post, postimage="NEW")
    rollback_transitions([t], tmp_path, snap)
    assert target.read_text(encoding="utf-8") == "OLD"


def test_rollback_preserves_non_default_file_mode(tmp_path: Path) -> None:
    target = tmp_path / "e.md"
    target.write_text("OLD", encoding="utf-8")
    _os.chmod(target, 0o640)
    pre = fingerprint(target)
    snap = snapshot_paths([target])
    target.write_text("NEW", encoding="utf-8")
    _os.chmod(target, 0o644)
    post = fingerprint(target)
    t = PathTransition(role="entity-rewrite", rel_path="e.md", pre=pre, post=post, postimage="NEW")
    rollback_transitions([t], tmp_path, snap)
    assert (_os.stat(target).st_mode & 0o777) == 0o640  # exact mode restored


def test_rollback_restores_symlink_not_a_regular_file(tmp_path: Path) -> None:
    link = tmp_path / "l"
    link.symlink_to("t.txt")
    pre = fingerprint(link)
    snap = snapshot_paths([link])
    link.unlink()
    link.write_text("clobbered-as-file", encoding="utf-8")  # simulate a bad landing
    post = fingerprint(link)
    t = PathTransition(role="entity-rewrite", rel_path="l", pre=pre, post=post,
                       postimage="clobbered-as-file")
    rollback_transitions([t], tmp_path, snap)
    assert link.is_symlink()
    assert _os.readlink(link) == "t.txt"


def test_rollback_removes_nested_created_dirs_bottom_up(tmp_path: Path) -> None:
    # archive-dst moved a file into a freshly created nested dir; rollback removes both.
    created_outer = tmp_path / "entities" / "_archive"
    created_inner = created_outer / "interpretations"
    moved = created_inner / "x.md"
    absent = StateFingerprint(existed=False, type=None, content_sha256=None, mode=None, symlink_target=None)
    dir_fp = StateFingerprint(existed=True, type="dir", content_sha256=None, mode=0o755, symlink_target=None)
    # Snapshot BEFORE anything lands, so the snapshot records all three paths ABSENT (== pre).
    snap = snapshot_paths([created_outer, created_inner, moved])
    # Now simulate the landed state: both dirs created, file moved in.
    created_inner.mkdir(parents=True)
    _os.chmod(created_inner, 0o755)
    _os.chmod(created_outer, 0o755)
    moved.write_text("X", encoding="utf-8")
    dst = PathTransition(role="archive-dst", rel_path="entities/_archive/interpretations/x.md",
                         pre=absent, post=fingerprint(moved))
    outer = PathTransition(role="created-dir", rel_path="entities/_archive", pre=absent, post=dir_fp)
    inner = PathTransition(role="created-dir", rel_path="entities/_archive/interpretations",
                           pre=absent, post=dir_fp)
    # declared order is outer, inner, dst; rollback must process dst -> inner -> outer.
    rollback_transitions([outer, inner, dst], tmp_path, snap)
    assert not moved.exists()
    assert not created_inner.exists()
    assert not created_outer.exists()


def test_rollback_halts_when_a_transition_path_has_no_snapshot(tmp_path: Path) -> None:
    # A missing snapshot entry is a defect, not an empty-file reconstruction opportunity.
    target = tmp_path / "e.md"
    target.write_text("NEW", encoding="utf-8")
    pre = StateFingerprint(existed=True, type="file",
                           content_sha256=_hashlib.sha256(b"OLD").hexdigest(), mode=0o644, symlink_target=None)
    post = fingerprint(target)
    t = PathTransition(role="entity-rewrite", rel_path="e.md", pre=pre, post=post, postimage="NEW")
    with pytest.raises(RollbackHalt):
        rollback_transitions([t], tmp_path, {})  # empty snapshot -> halt, do NOT write empty bytes


def test_rollback_halts_on_concurrent_change(tmp_path: Path) -> None:
    target = tmp_path / "e.md"
    target.write_text("OLD", encoding="utf-8")
    pre = fingerprint(target)
    snap = snapshot_paths([target])
    post_fp = StateFingerprint(existed=True, type="file",
                               content_sha256=_hashlib.sha256(b"NEW").hexdigest(), mode=0o644, symlink_target=None)
    t = PathTransition(role="entity-rewrite", rel_path="e.md", pre=pre, post=post_fp, postimage="NEW")
    target.write_text("SOMEONE-ELSE", encoding="utf-8")  # matches neither pre nor post
    with pytest.raises(RollbackHalt):
        rollback_transitions([t], tmp_path, snap)


def test_resolve_within_rejects_absolute_and_escaping_and_noncanonical(tmp_path: Path) -> None:
    (tmp_path / "entities" / "x").mkdir(parents=True)
    assert resolve_within(tmp_path, "entities/x/1.md") == (tmp_path / "entities/x/1.md").resolve()
    for bad in ["/etc/passwd", "../evil", "a/../b", "a/./b", "a//b", "", "sub/"]:
        with pytest.raises(PathEscape):
            resolve_within(tmp_path, bad)


def test_resolve_within_rejects_ancestor_symlink_escape(tmp_path: Path) -> None:
    # `entities` is a symlink pointing OUTSIDE the project; a lexically-clean path under it must
    # still be refused, because it physically resolves outside the corpus.
    outside = tmp_path.parent / "outside_target"
    outside.mkdir()
    root = tmp_path / "proj"
    root.mkdir()
    (root / "entities").symlink_to(outside)
    with pytest.raises(PathEscape):
        resolve_within(root, "entities/x.md")


def test_assert_same_surface_is_order_independent_and_strict() -> None:
    a = PathTransition(role="created-dir", rel_path="d1", pre=_absent_fp(),
                       post=StateFingerprint(existed=True, type="dir", content_sha256=None, mode=0o755, symlink_target=None))
    b = PathTransition(role="created-dir", rel_path="d2", pre=_absent_fp(),
                       post=StateFingerprint(existed=True, type="dir", content_sha256=None, mode=0o755, symlink_target=None))
    assert_same_surface([a, b], [b, a])  # no raise
    with pytest.raises(SurfaceMismatch):
        assert_same_surface([a], [a, b])


def test_assert_staging_unique_flags_collisions(tmp_path: Path) -> None:
    t1 = tmp_path / "a.md"
    assert_staging_unique(tmp_path, [t1, tmp_path / "b.md"], "tok")  # no raise
    with pytest.raises(StagingError):
        assert_staging_unique(tmp_path, [t1, t1], "tok")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --frozen pytest tests/test_plan_common.py -q`
Expected: FAIL — import error.

- [ ] **Step 3: Write minimal implementation**

```python
# add to science/src/science_tool/plan_common.py
from dataclasses import dataclass


class RollbackHalt(RuntimeError):
    pass


class PathEscape(RuntimeError):
    pass


class SurfaceMismatch(RuntimeError):
    pass


@dataclass(frozen=True)
class PathSnapshot:
    fp: StateFingerprint
    content: bytes | None  # regular-file bytes only; None for absent/dir/symlink


def snapshot_paths(paths: list[Path]) -> dict[Path, PathSnapshot]:
    """Capture COMPLETE pre-state: existence, type, mode, symlink target, and (for regular
    files) the bytes. `bytes | None` alone conflated absent with directory and dropped mode
    and symlink identity, so rollback could not faithfully reconstruct the tree."""
    snap: dict[Path, PathSnapshot] = {}
    for p in paths:
        fp = fingerprint(p)
        content = p.read_bytes() if fp.existed and fp.type == "file" else None
        snap[p] = PathSnapshot(fp=fp, content=content)
    return snap


def _remove_live(path: Path) -> None:
    try:
        st = os.lstat(path)
    except FileNotFoundError:
        return
    if stat.S_ISDIR(st.st_mode):
        os.rmdir(path)  # created dirs are empty by the time we reverse-process them
    else:
        os.unlink(path)


def _materialize(path: Path, snap: PathSnapshot) -> None:
    _remove_live(path)
    fp = snap.fp
    if not fp.existed:
        return
    if fp.type == "file":
        assert fp.mode is not None  # a present file fingerprint always carries its exact mode
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, fp.mode)
        with os.fdopen(fd, "wb") as fh:
            fh.write(snap.content or b"")
            fh.flush()
            os.fchmod(fh.fileno(), fp.mode)  # exact bits, incl. 0o000 — an `or 0o644` fallback corrupts mode 0
            os.fsync(fh.fileno())
    elif fp.type == "dir":
        assert fp.mode is not None  # a present dir fingerprint always carries its exact mode
        path.mkdir(parents=False, exist_ok=True)
        os.chmod(path, fp.mode)  # exact bits, incl. 0o000 — no `or 0o755` fallback
    else:  # symlink
        os.symlink(fp.symlink_target, path)


def rollback_transitions(
    transitions: list[PathTransition], project_root: Path, snapshot: dict[Path, PathSnapshot]
) -> None:
    for t in reversed(transitions):  # dirs removed only after their moved-in contents revert
        path = resolve_within(project_root, t.rel_path)
        if matches(t.pre, path):
            continue  # never got written, or already reverted
        if not matches(t.post, path):
            raise RollbackHalt(
                f"live state of {t.rel_path} matches neither pre nor post; "
                "a concurrent change occurred — refusing to clobber"
            )
        snap = snapshot.get(path)
        if snap is None:
            # No captured pre-state for a path we are asked to revert -> reconstructing from `pre`
            # alone would write an EMPTY file when bytes are unavailable. That is data loss, so halt.
            raise RollbackHalt(f"no snapshot captured for {t.rel_path}; refusing to reconstruct")
        _materialize(path, snap)


def resolve_within(project_root: Path, rel_path: str) -> Path:
    """Resolve rel_path under project_root, refusing absolute paths, `..` escape, non-canonical
    spellings, AND symlink-ancestor escape. Called for EVERY declared path before filesystem
    access. Lexical checks alone are not enough: if `entities/` were a symlink pointing outside
    the project, a lexically-clean `entities/x.md` would still write out of the corpus — so we
    `.resolve()` the candidate (following symlinks in the existing ancestor chain) and confirm the
    physical target is contained, exactly as the import boundary does (`entity_import.py:486`)."""
    if (
        rel_path == ""
        or Path(rel_path).is_absolute()
        or rel_path != os.path.normpath(rel_path)
        or rel_path.split("/", 1)[0] == ".."
    ):
        raise PathEscape(f"non-canonical or escaping rel_path: {rel_path!r}")
    root = project_root.resolve()
    candidate = (root / rel_path).resolve()  # follows symlinks in the existing prefix
    if candidate != root and not candidate.is_relative_to(root):
        raise PathEscape(f"rel_path escapes project root (symlink or traversal): {rel_path!r}")
    return candidate


def _surface_key(t: PathTransition) -> tuple[str, str, str, str, str | None]:
    return (t.role, t.rel_path, t.pre.model_dump_json(), t.post.model_dump_json(), t.postimage)


def assert_same_surface(
    declared: list[PathTransition], expected: list[PathTransition]
) -> None:
    if sorted(map(_surface_key, declared)) != sorted(map(_surface_key, expected)):
        raise SurfaceMismatch(
            "declared transition surface differs from the freshly derived surface"
        )


def assert_staging_unique(project_root: Path, staged_targets: list[Path], token: str) -> None:
    root = project_root.resolve()
    staging = [staging_path_for(t, token) for t in staged_targets]
    if len(set(staging)) != len(staging):
        raise StagingError("staging path collision among staged writes")
    for s in staging:
        normalized = Path(os.path.normpath(s))
        if root not in normalized.parents:
            raise StagingError(f"staging path escapes project root: {s}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --frozen pytest tests/test_plan_common.py -q`
Expected: PASS (rollback for file/mode/symlink/nested-dir/halt; `resolve_within`; surface; staging).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/plan_common.py science/tests/test_plan_common.py
git commit -m "feat(curation): full-state snapshot/rollback + containment & surface validators"
```

---

## Phase 1 — Writer refactor (`entities.py`)

### Task 7: Injectable-timestamp shared preparation function

**Files:**
- Modify: `science/src/science_tool/entities.py:1031-1091` (`_prepare_write`) and `science/src/science_tool/consolidation.py:498-512` (`_prepare_supersession`)
- Test: `science/tests/test_prepare_write_injectable.py`

**Interfaces:**
- Produces: `_prepare_write_with_date(project_root, ref, fields, *, updated_default: str, appends=None) -> _PreparedWrite` — identical to today's `_prepare_write` except `frontmatter.setdefault("updated", updated_default)` replaces `date.today().isoformat()`. `_prepare_write(...)` becomes `_prepare_write_with_date(..., updated_default=date.today().isoformat())`. `_prepare_supersession(project_root, graph, member, *, preview_date: str)` threads `updated_default=preview_date`.
- Consumes: retains all three boundary checks at `entities.py:1072/1075/1083`.

- [ ] **Step 1: Write the failing test**

```python
# science/tests/test_prepare_write_injectable.py
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from science_tool.entities import _prepare_write_with_date


def _seed(root: Path) -> Path:
    (root / "science.yaml").write_text("name: t\n", encoding="utf-8")
    d = root / "entities" / "interpretations"
    d.mkdir(parents=True)
    p = d / "0001-x.md"
    p.write_text("---\nid: interpretation:0001-x\nkind: interpretation\nstatus: draft\n---\nbody\n",
                 encoding="utf-8")
    return p


def test_injected_updated_default_is_used_when_key_absent(tmp_path: Path) -> None:
    _seed(tmp_path)
    prepared = _prepare_write_with_date(
        tmp_path, "interpretation:0001-x", {"status": "superseded"}, updated_default="2026-07-18"
    )
    fm = yaml.safe_load(prepared.text.split("---\n", 2)[1])
    assert fm["updated"] == "2026-07-18"
    assert fm["status"] == "superseded"


def test_existing_updated_is_preserved_not_overwritten(tmp_path: Path) -> None:
    p = _seed(tmp_path)
    p.write_text(
        "---\nid: interpretation:0001-x\nkind: interpretation\nstatus: draft\nupdated: 2020-01-01\n---\nbody\n",
        encoding="utf-8",
    )
    prepared = _prepare_write_with_date(
        tmp_path, "interpretation:0001-x", {"status": "superseded"}, updated_default="2026-07-18"
    )
    fm = yaml.safe_load(prepared.text.split("---\n", 2)[1])
    assert fm["updated"] == "2020-01-01"  # setdefault preserves


def test_two_invocations_with_same_date_produce_identical_bytes(tmp_path: Path) -> None:
    _seed(tmp_path)
    a = _prepare_write_with_date(tmp_path, "interpretation:0001-x", {"status": "superseded"},
                                 updated_default="2026-07-18")
    b = _prepare_write_with_date(tmp_path, "interpretation:0001-x", {"status": "superseded"},
                                 updated_default="2026-07-18")
    assert a.text == b.text


def test_write_boundary_is_retained_dangling_successor_is_refused(tmp_path: Path) -> None:
    # Reaches the RESOLUTION boundary specifically (entities.py:1083), one of the three checks the
    # refactor must retain. A dangling `superseded_by` passes the field loop (`_validate_status`
    # only inspects `status`) and the schema gate, then fails successor resolution — proving the
    # prospective-write wall survived the extraction, not merely the status validator.
    _seed(tmp_path)
    with pytest.raises(Exception):
        _prepare_write_with_date(tmp_path, "interpretation:0001-x",
                                 {"superseded_by": "interpretation:9999-does-not-exist"},
                                 updated_default="2026-07-18")


def test_prepare_write_legacy_wrapper_injects_today(tmp_path: Path) -> None:
    # The legacy _prepare_write must still exist and default `updated` to today's date.
    from datetime import date

    from science_tool.entities import _prepare_write
    _seed(tmp_path)
    prepared = _prepare_write(tmp_path, "interpretation:0001-x", {"status": "superseded"})
    fm = yaml.safe_load(prepared.text.split("---\n", 2)[1])
    assert fm["updated"] == date.today().isoformat()


def test_all_three_boundary_checks_run_in_order(tmp_path: Path, monkeypatch) -> None:
    # I6: prove the refactor RETAINS all three boundary checks — schema gate, prospective-corpus,
    # successor-resolution — and runs them in the documented order (cheapest authority first). Each
    # spy calls through, so behavior is unchanged; only the call order is recorded.
    import science_tool.entities as e
    _seed(tmp_path)
    order: list[str] = []
    for name in ("_schema_gate_or_raise", "_validate_prospective_write", "_resolution_check_or_raise"):
        real = getattr(e, name)

        def make(n: str, r):
            def spy(*a, **k):
                order.append(n)
                return r(*a, **k)
            return spy

        monkeypatch.setattr(e, name, make(name, real))
    _prepare_write_with_date(tmp_path, "interpretation:0001-x", {"status": "superseded"},
                             updated_default="2026-07-18")
    assert order == ["_schema_gate_or_raise", "_validate_prospective_write", "_resolution_check_or_raise"]


def test_each_boundary_check_is_load_bearing_in_both_prepare_routes(tmp_path: Path, monkeypatch) -> None:
    # I6 / design §480: each of the three boundary checks is LOAD-BEARING — forcing any one to raise
    # aborts the write, through BOTH the injectable writer (preview + apply-plan route) and the legacy
    # `_prepare_write`. Together with the ordering spy above and the dangling-successor behavioral test
    # below, this proves the extraction refuses an illegal corpus write on every route, not just runs
    # the checks.
    import science_tool.entities as e
    from science_tool.entities import _prepare_write

    class _Boom(Exception):
        pass

    _seed(tmp_path)
    for gate in ("_schema_gate_or_raise", "_validate_prospective_write", "_resolution_check_or_raise"):
        def boom(*a, _g=gate, **k):
            raise _Boom(_g)

        monkeypatch.setattr(e, gate, boom)
        with pytest.raises(_Boom):
            _prepare_write_with_date(tmp_path, "interpretation:0001-x", {"status": "superseded"},
                                     updated_default="2026-07-18")
        with pytest.raises(_Boom):
            _prepare_write(tmp_path, "interpretation:0001-x", {"status": "superseded"})
        monkeypatch.undo()


def test_present_but_empty_updated_is_preserved_by_the_writer(tmp_path: Path, monkeypatch) -> None:
    # design §9 (`updated` presence semantics, render layer): a present-but-empty `updated` is
    # preserved by presence, NOT replaced with the injected default — `setdefault` only fills an
    # ABSENT key. (The schema boundary separately REJECTS an empty date on a schema-backed project;
    # that is a different layer, neutralized here to isolate the render behavior.)
    import science_tool.entities as e
    p = _seed(tmp_path)
    p.write_text(
        "---\nid: interpretation:0001-x\nkind: interpretation\nstatus: draft\nupdated: ''\n---\nbody\n",
        encoding="utf-8")
    monkeypatch.setattr(e, "_schema_gate_or_raise", lambda *a, **k: None)
    monkeypatch.setattr(e, "_validate_prospective_write", lambda **k: ([], object()))
    monkeypatch.setattr(e, "_resolution_check_or_raise", lambda *a, **k: None)
    prepared = _prepare_write_with_date(tmp_path, "interpretation:0001-x", {"status": "superseded"},
                                        updated_default="2026-07-18")
    fm = yaml.safe_load(prepared.text.split("---\n", 2)[1])
    assert fm["updated"] == ""  # empty value preserved, NOT overwritten with 2026-07-18
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --frozen pytest tests/test_prepare_write_injectable.py -q`
Expected: FAIL — `ImportError: cannot import name '_prepare_write_with_date'`.

- [ ] **Step 3: Write minimal implementation**

In `science/src/science_tool/entities.py`, rename the existing `_prepare_write` body into `_prepare_write_with_date` by adding a keyword-only `updated_default: str` param and changing the one line; then re-add `_prepare_write` as a thin wrapper. Replace lines 1031-1091:

```python
def _prepare_write_with_date(
    project_root: Path,
    ref: str,
    fields: Mapping[str, object],
    *,
    updated_default: str,
    appends: Mapping[str, list[str]] | None = None,
) -> _PreparedWrite:
    """PRIVATE. Merge, render, validate, SEAL. Writes NOTHING.

    Identical to the historical `_prepare_write` except the `updated` default is
    INJECTED (`updated_default`) instead of read from the clock, so a preview and a
    later apply produce byte-identical output. Retains the three boundary checks.
    """
    project_root = project_root.resolve()
    _reject_if_archived(project_root, ref)
    location = find_entity(project_root, ref)

    frontmatter = dict(location.frontmatter)
    for key, additions in (appends or {}).items():
        frontmatter[key] = _append_unique_string_values(frontmatter.get(key), additions)
    for key, value in fields.items():
        if key == "status":
            _validate_status(project_root, location.kind, str(value))
        frontmatter[key] = value
    frontmatter.setdefault("updated", updated_default)

    _schema_gate_or_raise(project_root, location.kind, fields, frontmatter)

    text = _render_markdown(frontmatter, location.body)
    warnings, prospective = _validate_prospective_write(
        project_root=project_root,
        rel_path=Path(location.rel_path),
        text=text,
        target_entity_id=location.entity_id,
    )
    _resolution_check_or_raise(location.kind, frontmatter, prospective)

    return _PreparedWrite(
        entity_id=location.entity_id,
        path=location.path,
        text=text,
        warnings=tuple(warnings),
        seal=_seal(location.entity_id, location.path, text),
    )


def _prepare_write(
    project_root: Path,
    ref: str,
    fields: Mapping[str, object],
    *,
    appends: Mapping[str, list[str]] | None = None,
) -> _PreparedWrite:
    """Legacy entry point: inject today's date as the `updated` default."""
    return _prepare_write_with_date(
        project_root, ref, fields, updated_default=date.today().isoformat(), appends=appends
    )
```

Then in `science/src/science_tool/consolidation.py:498-512`, thread the date:

```python
def _prepare_supersession(
    project_root: Path, graph: SupersedesGraph, member: str, *, preview_date: str
) -> _PreparedWrite:
    """Prepare `status: superseded` + its derived inverse for one member. Writes NOTHING."""
    from science_tool.entities import _prepare_write_with_date

    return _prepare_write_with_date(
        project_root,
        member,
        {"status": _SUPERSEDED, "superseded_by": graph.superseder_by_id[member]},
        updated_default=preview_date,
    )
```

And update its ONE caller in `mark_superseded` (`consolidation.py:643`) to pass a date. For now (legacy `--apply` path preserved), use today's date so behavior is unchanged:

```python
    from datetime import date
    _preview_date = date.today().isoformat()
    prepared = [_prepare_supersession(project_root, graph, m, preview_date=_preview_date)
                for m in (*to_mark, *to_repair)]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --frozen pytest tests/test_prepare_write_injectable.py tests/test_consolidation_mark_superseded.py -q`
Expected: PASS (new tests + all existing mark-superseded tests still green — behavior unchanged on the legacy path).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/entities.py science/src/science_tool/consolidation.py science/tests/test_prepare_write_injectable.py
git commit -m "refactor(entities): injectable updated default via _prepare_write_with_date"
```

---

## Phase 2 — Supersession decision material (`consolidation.py`)

### Task 8: `SupersessionDecisionMaterial` = the classifier's INPUT projections

**The material is the INPUT to derivation, not a serialization of the graph's OUTPUT.** It must
be built from `SupersessionInputs` **before any graph exists**, capturing exactly what
`build_supersedes_graph` reads — the per-entry projections (canonical id, status, kind, authored
`superseded_by` raw + its canonical resolution), the **admitted supersedes relation stream**
(`src`, `dst|None`, `source_path` — duplicates preserved, because collapsing to a set is the very
bug the graph builder's set-vs-list comment warns about), the full defect records, and the
mutable/archived populations. A digest over this reproduces the whole derivation, including
`superseded_by_id`, `unbacked_inverses`, `archived_targets`, and `unmanaged_targets` — not just
the three fields a graph-output serialization would keep.

**Files:**
- Modify: `science/src/science_tool/consolidation.py`
- Test: `science/tests/test_decision_material.py`

**Interfaces:**
- Produces: projection models `EntryProjection` (`eid`, `status: str|None`, `kind`, `superseded_by_raw: str|None`, `superseded_by_canonical: str|None`), `EdgeProjection` (`src`, `dst: str|None`, `source_path`), `DefectProjection` (`code`, `path`, `subject`, `predicate`, `object`, `message`); `SupersessionDecisionMaterial` (`material_version`, `entries: list[EntryProjection]`, `admitted_supersedes: list[EdgeProjection]`, `defects: list[DefectProjection]`, `mutable_population: list[str]`, `archived_population: list[str]`, `supported_kinds: list[str]` — the frozen auto-apply policy, so the digest covers it, I4); `_project_inputs(inputs: SupersessionInputs) -> SupersessionDecisionMaterial`; `build_decision_material(project_root) -> SupersessionDecisionMaterial` (`= _project_inputs(load_supersession_inputs(project_root))` — **never** calls `build_supersedes_graph`); `decision_digest(material) -> str`.

- [ ] **Step 1: Write the failing test**

```python
# science/tests/test_decision_material.py
from __future__ import annotations

from pathlib import Path

import yaml

from science_tool.consolidation import (
    _SUPERSEDES, build_decision_material, decision_digest, load_supersession_inputs,
)


def _seed(root: Path) -> None:
    (root / "science.yaml").write_text("name: t\n", encoding="utf-8")
    d = root / "entities" / "interpretations"
    d.mkdir(parents=True)
    (d / "0001-a.md").write_text(
        "---\nid: interpretation:0001-a\nkind: interpretation\ntitle: A\nstatus: active\n"
        "relations:\n  - predicate: sci:supersedes\n    target: interpretation:0002-b\n---\nbody\n",
        encoding="utf-8",
    )
    (d / "0002-b.md").write_text(
        "---\nid: interpretation:0002-b\nkind: interpretation\ntitle: B\nstatus: active\n"
        "superseded_by: interpretation:0001-a\n---\nbody\n",
        encoding="utf-8",
    )


def test_decision_digest_is_stable_across_runs(tmp_path: Path) -> None:
    _seed(tmp_path)
    d1 = decision_digest(build_decision_material(tmp_path))
    d2 = decision_digest(build_decision_material(tmp_path))
    assert d1 == d2


def test_decision_digest_changes_when_a_material_field_changes(tmp_path: Path) -> None:
    _seed(tmp_path)
    before = decision_digest(build_decision_material(tmp_path))
    p = tmp_path / "entities" / "interpretations" / "0002-b.md"
    fm = yaml.safe_load(p.read_text(encoding="utf-8").split("---\n", 2)[1])
    fm["status"] = "superseded"
    p.write_text("---\n" + yaml.safe_dump(fm, sort_keys=False) + "---\nbody\n", encoding="utf-8")
    after = decision_digest(build_decision_material(tmp_path))
    assert before != after


def test_non_projected_field_change_does_not_move_the_digest(tmp_path: Path) -> None:
    # design §9: a frontmatter change to a field NOT in the projection (e.g. `title`) leaves the
    # decision digest unchanged — the digest surface is exactly the decision surface, no more.
    _seed(tmp_path)
    before = decision_digest(build_decision_material(tmp_path))
    p = tmp_path / "entities" / "interpretations" / "0001-a.md"
    fm = yaml.safe_load(p.read_text(encoding="utf-8").split("---\n", 2)[1])
    fm["title"] = "A COMPLETELY DIFFERENT TITLE"  # title is not part of the decision projection
    p.write_text("---\n" + yaml.safe_dump(fm, sort_keys=False) + "---\nbody\n", encoding="utf-8")
    after = decision_digest(build_decision_material(tmp_path))
    assert before == after


def test_material_admitted_edges_never_collapse_below_the_audit_count(tmp_path: Path) -> None:
    # design §9 (duplicates preserved): a corpus with a repeated supersedes target must yield a material
    # whose admitted-edge count equals the audit's relation count — the projection never collapses
    # admitted relations to a unique set.
    (tmp_path / "science.yaml").write_text("name: t\n", encoding="utf-8")
    d = tmp_path / "entities" / "interpretations"
    d.mkdir(parents=True)
    (d / "0001-a.md").write_text(
        "---\nid: interpretation:0001-a\nkind: interpretation\ntitle: A\nstatus: active\n"
        "relations:\n  - predicate: sci:supersedes\n    target: interpretation:0002-b\n"
        "  - predicate: sci:supersedes\n    target: interpretation:0002-b\n---\nbody\n",
        encoding="utf-8")
    (d / "0002-b.md").write_text(
        "---\nid: interpretation:0002-b\nkind: interpretation\ntitle: B\nstatus: active\n---\nbody\n",
        encoding="utf-8")
    inputs = load_supersession_inputs(tmp_path)
    mat = build_decision_material(tmp_path)
    assert len(mat.admitted_supersedes) == len(inputs.audit.relations(_SUPERSEDES))  # no collapsing
    assert any(e.src == "interpretation:0001-a" and e.dst == "interpretation:0002-b"
               for e in mat.admitted_supersedes)


def test_material_captures_authored_superseded_by_not_just_edges(tmp_path: Path) -> None:
    # 0002-b authors a superseded_by inverse; the material must carry that per-entry projection
    # so the derived unbacked-inverse rule (Task 9) can be reproduced from the digest alone.
    _seed(tmp_path)
    mat = build_decision_material(tmp_path)
    b = [e for e in mat.entries if e.eid == "interpretation:0002-b"][0]
    assert b.superseded_by_raw == "interpretation:0001-a"
    assert b.superseded_by_canonical == "interpretation:0001-a"


def test_material_preserves_the_admitted_relation_stream(tmp_path: Path) -> None:
    # The admitted-edge projection must count admitted relations, NOT a collapsed edge set —
    # collapsing to a set is the degree-miscount bug the graph builder documents.
    _seed(tmp_path)
    inputs = load_supersession_inputs(tmp_path)
    mat = build_decision_material(tmp_path)
    assert len(mat.admitted_supersedes) == len(inputs.audit.relations(_SUPERSEDES))


def test_build_decision_material_does_not_build_a_graph(monkeypatch, tmp_path: Path) -> None:
    # Guardrail for finding 2: the material is the INPUT projection; it must not be derived
    # from the graph OUTPUT.
    import science_tool.consolidation as c
    _seed(tmp_path)

    def _boom(*a, **k):
        raise AssertionError("build_decision_material must not call build_supersedes_graph")

    monkeypatch.setattr(c, "build_supersedes_graph", _boom)
    build_decision_material(tmp_path)  # must not raise
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --frozen pytest tests/test_decision_material.py -q`
Expected: FAIL — import error.

- [ ] **Step 3: Write minimal implementation**

```python
# add to science/src/science_tool/consolidation.py
import hashlib
from pydantic import BaseModel, ConfigDict

_MATERIAL_VERSION = 1


class EntryProjection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    eid: str
    status: str | None
    kind: str
    superseded_by_raw: str | None
    superseded_by_canonical: str | None


class EdgeProjection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    src: str
    dst: str | None
    source_path: str


class DefectProjection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str
    path: str
    subject: str
    predicate: str
    object: str
    message: str


class SupersessionDecisionMaterial(BaseModel):
    model_config = ConfigDict(extra="forbid")
    material_version: int
    entries: list[EntryProjection]            # canonical order (sorted by eid)
    admitted_supersedes: list[EdgeProjection] # sorted by (src, dst or "", source_path); DUPS KEPT
    defects: list[DefectProjection]           # sorted; DUPS KEPT
    mutable_population: list[str]             # sorted
    archived_population: list[str]            # sorted
    supported_kinds: list[str]               # sorted; the frozen auto-apply policy the classifier reads (I4)


def _project_inputs(inputs: SupersessionInputs) -> SupersessionDecisionMaterial:
    """Serialize exactly what `build_supersedes_graph` reads off `SupersessionInputs`, resolving
    the two things the classifier needs the resolver for (each entry's canonical id and each
    authored `superseded_by`'s canonical) so the classifier can run without a resolver. Sorted for
    a deterministic digest; admitted relations and defects keep duplicates."""
    resolution = inputs.resolution
    entries: list[EntryProjection] = []
    for _path, fm in inputs.entries:
        eid = resolution.canonical(str(fm["id"])) or str(fm["id"])
        raw_inverse = fm.get("superseded_by")
        raw = raw_inverse if isinstance(raw_inverse, str) and raw_inverse else None
        entries.append(EntryProjection(
            eid=eid,
            status=fm.get("status"),
            kind=_kind_of(eid, fm),
            superseded_by_raw=raw,
            superseded_by_canonical=(resolution.canonical(raw) if raw else None),
        ))
    edges = [
        EdgeProjection(src=a.subject.canonical_id, dst=a.object_canonical_id,
                       source_path=a.relation.source_path)
        for a in inputs.audit.relations(_SUPERSEDES)
    ]
    defects = [
        DefectProjection(code=d.code, path=d.path, subject=d.subject, predicate=d.predicate,
                         object=d.object, message=d.message)
        for d in inputs.audit.defects
    ]
    return SupersessionDecisionMaterial(
        material_version=_MATERIAL_VERSION,
        entries=sorted(entries, key=lambda e: e.eid),
        admitted_supersedes=sorted(edges, key=lambda e: (e.src, e.dst or "", e.source_path)),
        defects=sorted(defects, key=lambda d: (d.code, d.subject, d.predicate, d.object, d.path, d.message)),
        mutable_population=sorted(resolution.mutable),
        archived_population=sorted(resolution.archived),
        # The auto-apply supported-kind policy IS a decision input (design §5.2): serialize it so the
        # digest covers it. `_supports_superseded(k)` is `_SUPERSEDED in _STATUS_VALUES.get(k, ...)`,
        # so the supported set is exactly the kinds whose status vocab admits `superseded`.
        supported_kinds=sorted(k for k, v in _STATUS_VALUES.items() if _SUPERSEDED in v),
    )


def build_decision_material(project_root: Path) -> SupersessionDecisionMaterial:
    return _project_inputs(load_supersession_inputs(project_root))


def decision_digest(material: SupersessionDecisionMaterial) -> str:
    return hashlib.sha256(material.model_dump_json().encode("utf-8")).hexdigest()
```

Implementer notes: `AdmittedRelation.subject.canonical_id`, `.object_canonical_id`, `.relation.source_path` are the exact attributes `build_supersedes_graph` reads at `consolidation.py:363-365`; `RelationDefect` fields are `code/path/subject/predicate/object/message` (`graph/relation_audit.py:68`). `_kind_of`, `_SUPERSEDES` (`= "supersedes"`), `_STATUS_VALUES`, `_SUPERSEDED`, and `_supports_superseded` (`consolidation.py:98`) already exist in this module. Do **not** import or call `build_supersedes_graph` here — that inverts input and output (finding 2).

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --frozen pytest tests/test_decision_material.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/consolidation.py science/tests/test_decision_material.py
git commit -m "feat(supersede): decision material as classifier input projections"
```

---

### Task 9: One classifier, two entry points (full-field equivalence)

`build_supersedes_graph(inputs)` and `build_supersedes_graph_from_material(material)` must produce
the **same** `SupersedesGraph` — every field, not just `linear`/`edges`/`superseder_by_id`. The
way to guarantee that is structural: extract the classification body into
`_classify_from_projections(material, *, path_by_id)` and have **both** entry points call it, with
`build_supersedes_graph` first projecting its live inputs through `_project_inputs`. Then the only
difference between the two is `path_by_id` (live-only; not decision-bearing).

**Files:**
- Modify: `science/src/science_tool/consolidation.py`
- Test: `science/tests/test_decision_material.py`

**Interfaces:**
- Produces: `_classify_from_projections(material: SupersessionDecisionMaterial, *, path_by_id: Mapping[str, Path]) -> SupersedesGraph`; `build_supersedes_graph_from_material(material) -> SupersedesGraph` (`path_by_id={}`). `build_supersedes_graph(inputs)` keeps its signature but is re-expressed as `_classify_from_projections(_project_inputs(inputs), path_by_id=<eid→path>)`. Also extracts `_disposition_report(graph: SupersedesGraph, *, ids: frozenset[str] | None) -> dict` — the pure dry-run report builder (chains → to_mark/to_repair/skipped_kinds + the 9 report keys + the ids-allowlist narrowing and `SupersessionError` on unresolved) lifted from `mark_superseded`. Preview (`plan_supersede`) and `mark_superseded` both call it; the second uses the FS-loaded graph, the first uses the **material-derived** graph, so the disposition is a pure function of the graph and preview needs no second filesystem load.

**Behavior-preservation risk (read before coding):** the report lists `archived_targets` /
`unmanaged_targets` / `unbacked_inverses` / `invalid` now iterate the **sorted** projections, so
their order becomes canonical instead of audit/scan order — an **observable 0.5.0 behavior change**
(record it in the release notes; see Task 18). `test_consolidation_mark_superseded.py` is the guard.
If an assertion there pinned the old order, add a fresh multi-item test that pins the NEW canonical
order (below) rather than only editing the old one, and do not reintroduce nondeterministic order.
Note the blocking semantics are unchanged and differ per list: `archived_targets` /
`unmanaged_targets` are reported **and do not block**; `invalid` and `unbacked_inverses` are
reported **and DO block** apply (`mark_superseded` raises on them). Only the *ordering* is canonical
now — not the blocking behavior.

- [ ] **Step 1: Write the failing test**

```python
# append to science/tests/test_decision_material.py
from science_tool.consolidation import (
    build_supersedes_graph, build_supersedes_graph_from_material,
)


def _all_fields(g):
    return {
        "linear": [(c.survivor, c.superseded) for c in g.linear],
        "non_linear": [(n.nodes, n.reason) for n in g.non_linear],
        "status_by_id": dict(g.status_by_id),
        "kind_by_id": dict(g.kind_by_id),
        "edges": sorted(g.edges),
        "superseder_by_id": dict(g.superseder_by_id),
        "superseded_by_id": dict(g.superseded_by_id),
        "invalid": [(d.code, d.subject, d.object, d.message) for d in g.invalid],
        "archived_targets": list(g.archived_targets),
        "unmanaged_targets": list(g.unmanaged_targets),
        "unbacked_inverses": list(g.unbacked_inverses),
        "supported_kinds": sorted(g.supported_kinds),  # I4: the policy field must agree too
    }


def test_graph_from_material_equals_live_on_every_field(tmp_path: Path) -> None:
    _seed(tmp_path)
    live = build_supersedes_graph(load_supersession_inputs(tmp_path))
    mat = build_supersedes_graph_from_material(build_decision_material(tmp_path))
    assert _all_fields(live) == _all_fields(mat)  # every decision/report field, not a subset


def test_graph_from_material_has_empty_path_by_id(tmp_path: Path) -> None:
    _seed(tmp_path)
    mat = build_supersedes_graph_from_material(build_decision_material(tmp_path))
    assert dict(mat.path_by_id) == {}  # paths are not decision-bearing; gate B never reads them


def test_disposition_report_from_material_matches_mark_superseded(tmp_path: Path) -> None:
    # The disposition helper is a pure function of the graph: driving it from the material-derived
    # graph must yield the same dry-run report as the filesystem-driven mark_superseded.
    from science_tool.consolidation import _disposition_report, mark_superseded
    _seed(tmp_path)
    mat_graph = build_supersedes_graph_from_material(build_decision_material(tmp_path))
    assert _disposition_report(mat_graph, ids=None) == mark_superseded(tmp_path, ids=None, apply=False)


def test_material_admitted_edges_are_canonically_sorted(tmp_path: Path) -> None:
    # Pin the NEW canonical (sorted) order of a multi-item list, per the 0.5.0 ordering ratification.
    (tmp_path / "science.yaml").write_text("name: t\n", encoding="utf-8")
    d = tmp_path / "entities" / "interpretations"
    d.mkdir(parents=True)
    (d / "0001-a.md").write_text(
        "---\nid: interpretation:0001-a\nkind: interpretation\ntitle: A\nstatus: active\n"
        "relations:\n  - predicate: sci:supersedes\n    target: interpretation:0004-d\n---\nbody\n",
        encoding="utf-8")
    (d / "0002-b.md").write_text(
        "---\nid: interpretation:0002-b\nkind: interpretation\ntitle: B\nstatus: active\n"
        "relations:\n  - predicate: sci:supersedes\n    target: interpretation:0003-c\n---\nbody\n",
        encoding="utf-8")
    (d / "0003-c.md").write_text(
        "---\nid: interpretation:0003-c\nkind: interpretation\ntitle: C\nstatus: active\n---\nbody\n",
        encoding="utf-8")
    (d / "0004-d.md").write_text(
        "---\nid: interpretation:0004-d\nkind: interpretation\ntitle: D\nstatus: active\n---\nbody\n",
        encoding="utf-8")
    mat = build_decision_material(tmp_path)
    keys = [(e.src, e.dst, e.source_path) for e in mat.admitted_supersedes]
    assert len(keys) == 2
    assert keys == sorted(keys)  # canonical order, deterministic across runs


def test_material_carries_supported_kinds_and_digest_covers_the_policy(monkeypatch, tmp_path: Path) -> None:
    # I4: the auto-apply supported-kind policy is part of the authenticated decision surface. It is
    # serialized (sorted) into the material, and changing it flips the digest — so a policy shift
    # between preview and apply is caught as drift, not silently applied.
    import science_tool.consolidation as c
    _seed(tmp_path)
    mat = build_decision_material(tmp_path)
    assert "interpretation" in mat.supported_kinds
    assert mat.supported_kinds == sorted(mat.supported_kinds)  # canonical
    before = decision_digest(mat)
    extended = dict(c._STATUS_VALUES)
    extended["zzz-fake-kind"] = frozenset({c._SUPERSEDED})  # a new auto-apply-eligible kind
    monkeypatch.setattr(c, "_STATUS_VALUES", extended)
    after = decision_digest(build_decision_material(tmp_path))
    assert before != after  # the policy change moved the digest


def test_disposition_reads_supported_kinds_from_the_graph_not_the_module(monkeypatch, tmp_path: Path) -> None:
    # _disposition_report must consult graph.supported_kinds (authenticated), not the live module
    # policy. Neutralizing the module function while the graph still carries the policy keeps the
    # disposition correct — proving the read moved onto the material.
    import science_tool.consolidation as c
    _seed(tmp_path)
    graph = build_supersedes_graph_from_material(build_decision_material(tmp_path))
    monkeypatch.setattr(c, "_supports_superseded", lambda kind: False)  # would empty to_mark if consulted
    report = c._disposition_report(graph, ids=None)
    assert report["to_mark"]  # still non-empty: the policy came from the graph, not the patched module


def test_disposition_report_sorts_the_four_secondary_lists_regardless_of_graph_order() -> None:
    # I7: the release-note behavior change. The four secondary report lists are emitted in canonical
    # sorted order even when the graph presents them in a NON-canonical order — so removing the sort
    # in _disposition_report fails this. Each list below is supplied reverse-of-canonical on purpose.
    from types import MappingProxyType

    from science_tool.consolidation import SupersedesGraph, _disposition_report
    from science_tool.graph.relation_audit import RelationDefect

    g = SupersedesGraph(
        linear=(), non_linear=(),
        status_by_id=MappingProxyType({}), kind_by_id=MappingProxyType({}),
        path_by_id=MappingProxyType({}), edges=frozenset(),
        superseder_by_id=MappingProxyType({}), superseded_by_id=MappingProxyType({}),
        invalid=(
            RelationDefect(code="invalid_relation", path="z.md", subject="interpretation:0009",
                           predicate="sci:supersedes", object="x", message="m"),
            RelationDefect(code="invalid_relation", path="a.md", subject="interpretation:0001",
                           predicate="sci:supersedes", object="x", message="m"),
        ),
        archived_targets=(
            {"id": "interpretation:0009", "superseder": "interpretation:0001", "path": "z", "reason": "r"},
            {"id": "interpretation:0002", "superseder": "interpretation:0003", "path": "a", "reason": "r"},
        ),
        unmanaged_targets=(
            {"id": "interpretation:0008", "superseder": "s", "path": "z", "reason": "r"},
            {"id": "interpretation:0004", "superseder": "s", "path": "a", "reason": "r"},
        ),
        unbacked_inverses=(
            {"id": "interpretation:0007", "superseder": "s", "reason": "r"},
            {"id": "interpretation:0003", "superseder": "s", "reason": "r"},
        ),
        supported_kinds=frozenset({"interpretation"}),
    )
    rep = _disposition_report(g, ids=None)
    assert [d["path"] for d in rep["invalid_relations"]] == ["a.md", "z.md"]
    assert [a["id"] for a in rep["archived_targets"]] == ["interpretation:0002", "interpretation:0009"]
    assert [u["id"] for u in rep["unmanaged_targets"]] == ["interpretation:0004", "interpretation:0008"]
    assert [u["id"] for u in rep["unbacked_inverses"]] == ["interpretation:0003", "interpretation:0007"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --frozen pytest tests/test_decision_material.py -q`
Expected: FAIL — `ImportError: cannot import name 'build_supersedes_graph_from_material'`.

- [ ] **Step 3: Write minimal implementation**

Replace the body of `build_supersedes_graph` (`consolidation.py:323-490`) with the extraction below. The middle block (`cyclic_nodes` → `_connected_components` → `linear`/`non_linear` → `superseder_by_id`) moves **verbatim**; only the loaders above it and the `superseded_by` loop below it change to read projections instead of `entries`/`resolution`/`audit`. **Add a `supported_kinds: frozenset[str]` field to the `SupersedesGraph` type** (the NamedTuple/dataclass it already is) so the frozen policy travels with the graph; `_disposition_report` reads `graph.supported_kinds` instead of calling the module-level `_supports_superseded`. Both classifier entry points populate it from `material.supported_kinds`, so live and material-driven graphs agree and the equivalence test still holds.

```python
# in science/src/science_tool/consolidation.py
from science_tool.graph.relation_audit import RelationDefect


def _classify_from_projections(
    material: SupersessionDecisionMaterial, *, path_by_id: Mapping[str, Path]
) -> SupersedesGraph:
    """The single supersession classifier. Pure function of the material projections plus a
    live-only path map. Both `build_supersedes_graph` and `build_supersedes_graph_from_material`
    call it, so the digest surface IS the derivation surface (finding 2)."""
    mutable = frozenset(material.mutable_population)
    archived = frozenset(material.archived_population)
    status_by_id: dict[str, str | None] = {e.eid: e.status for e in material.entries}
    kind_by_id: dict[str, str] = {e.eid: e.kind for e in material.entries}

    edges: set[tuple[str, str]] = set()
    archived_targets: list[dict[str, str]] = []
    unmanaged_targets: list[dict[str, str]] = []
    for ep in material.admitted_supersedes:
        src, dst, path_of_edge = ep.src, ep.dst, ep.source_path
        if dst is None:
            continue  # external term: a real edge, but not a node of this project
        if dst in archived:
            archived_targets.append({
                "id": dst, "superseder": src, "path": path_of_edge,
                "reason": "target is archived (frozen); no live record to stamp",
            })
            continue
        if dst not in mutable:
            unmanaged_targets.append({
                "id": dst, "superseder": src, "path": path_of_edge,
                "reason": ("target resolves but is not a live markdown entity of this project; "
                           "nothing here to stamp"),
            })
            continue
        edges.add((src, dst))

    cyclic_nodes = frozenset(
        node for d in material.defects if d.code == "cycle" for node in (d.subject, d.object)
    )

    # --- UNCHANGED from the current build_supersedes_graph body -------------------------------
    admitted = sorted(edges)
    nodes = {n for edge in admitted for n in edge}
    linear: list[SupersededChain] = []
    non_linear: list[NonLinearComponent] = []
    for comp in _connected_components(nodes, admitted):
        if len(comp) < 2:
            continue
        if comp & cyclic_nodes:
            continue
        is_linear, survivor, members = _classify(comp, admitted)
        if not is_linear or survivor is None:
            non_linear.append(
                NonLinearComponent(nodes=tuple(sorted(comp)), reason="branched supersedes chain")
            )
            continue
        linear.append(SupersededChain(survivor=survivor, superseded=tuple(sorted(members))))

    superseder_by_id: dict[str, str] = {}
    for chain in linear:
        chain_members = {chain.survivor, *chain.superseded}
        for src, dst in admitted:
            if src in chain_members and dst in chain_members:
                superseder_by_id[dst] = src
    # --- end UNCHANGED block ------------------------------------------------------------------

    superseded_by_id: dict[str, str] = {}
    unbacked_inverses: list[dict[str, str]] = []
    for e in material.entries:
        if e.superseded_by_raw is None:
            continue
        superseder = e.superseded_by_canonical
        if superseder is None:
            continue  # a DANGLING inverse -- check_resolution owns that one
        if (superseder, e.eid) not in edges:
            unbacked_inverses.append({
                "id": e.eid, "superseder": superseder,
                "reason": "authored superseded_by has no canonical sci:supersedes edge behind it",
            })
        superseded_by_id[e.eid] = superseder

    invalid = tuple(
        RelationDefect(code=d.code, path=d.path, subject=d.subject, predicate=d.predicate,
                       object=d.object, message=d.message)
        for d in material.defects
    )
    return SupersedesGraph(
        linear=tuple(linear),
        non_linear=tuple(non_linear),
        status_by_id=MappingProxyType(status_by_id),
        kind_by_id=MappingProxyType(kind_by_id),
        path_by_id=MappingProxyType(dict(path_by_id)),
        edges=frozenset(edges),
        superseder_by_id=MappingProxyType(superseder_by_id),
        superseded_by_id=MappingProxyType(superseded_by_id),
        invalid=invalid,
        archived_targets=tuple(archived_targets),
        unmanaged_targets=tuple(unmanaged_targets),
        unbacked_inverses=tuple(unbacked_inverses),
        supported_kinds=frozenset(material.supported_kinds),  # I4: policy travels on the graph
    )


def build_supersedes_graph(inputs: SupersessionInputs) -> SupersedesGraph:
    """Classify the supersession lineage from the loaded `inputs` (see the extended docstring on
    the pre-refactor version for the domain rules). Now a thin wrapper: project the inputs, keep
    the live-only path map, and run the shared classifier."""
    material = _project_inputs(inputs)
    resolution = inputs.resolution
    path_by_id: dict[str, Path] = {}
    for path, fm in inputs.entries:
        eid = resolution.canonical(str(fm["id"])) or str(fm["id"])
        path_by_id[eid] = path
    return _classify_from_projections(material, path_by_id=path_by_id)


def build_supersedes_graph_from_material(
    material: SupersessionDecisionMaterial,
) -> SupersedesGraph:
    """Gate-B derivation: rebuild the disposition from the frozen material, no filesystem read."""
    return _classify_from_projections(material, path_by_id={})


def _disposition_report(graph: SupersedesGraph, *, ids: frozenset[str] | None) -> dict:
    """The dry-run report, as a PURE function of a SupersedesGraph. Lifted verbatim from the body
    of `mark_superseded` (consolidation.py:555-611) so preview and gate B derive the disposition
    from the *material-derived* graph — no second filesystem load — and the FS path and the material
    path produce byte-identical reports. Raises `SupersessionError` when an allowlisted id is not a
    derivable member, exactly as before."""
    chains: list[dict[str, Any]] = []
    to_mark: list[str] = []
    to_repair: list[str] = []
    skipped_kinds: list[dict[str, str]] = []
    for chain in graph.linear:
        chains.append({"survivor": chain.survivor, "members": list(chain.superseded), "linear": True})
        for member in chain.superseded:
            kind = graph.kind_by_id.get(member, member.split(":", 1)[0])
            if kind not in graph.supported_kinds:  # I4: read the policy carried in the authenticated material
                skipped_kinds.append({"id": member, "kind": kind})
                continue
            if graph.status_by_id.get(member) != _SUPERSEDED:
                to_mark.append(member)
            elif graph.superseded_by_id.get(member) != graph.superseder_by_id[member]:
                to_repair.append(member)
    if ids is not None:
        derivable = set(to_mark) | set(to_repair)
        unresolved = sorted(ids - derivable)
        if unresolved:
            raise SupersessionError(
                [f"allowlisted id is not derivable as a supersession member: {e}" for e in unresolved]
            )
        to_mark = [m for m in to_mark if m in ids]
        to_repair = [m for m in to_repair if m in ids]
    return {
        "chains": chains,
        "non_linear": [{"nodes": list(c.nodes), "reason": c.reason} for c in graph.non_linear],
        "to_mark": to_mark,
        "applied": [],
        "skipped_kinds": skipped_kinds,
        "to_repair": to_repair,
        "repaired": [],
        # The four secondary report lists are emitted in CANONICAL sorted order (0.5.0 behavior
        # change, Task 18) — deterministic regardless of audit/scan order. Blocking semantics
        # unchanged: `invalid_relations` and `unbacked_inverses` still refuse apply.
        "invalid_relations": sorted(
            ({"code": d.code, "path": d.path, "subject": d.subject, "predicate": d.predicate,
              "object": d.object, "message": d.message} for d in graph.invalid),
            key=lambda d: (d["code"], d["path"], d["subject"], d["predicate"], d["object"], d["message"]),
        ),
        "archived_targets": sorted(
            (dict(a) for a in graph.archived_targets),
            key=lambda a: (a["id"], a["superseder"], a["path"]),
        ),
        "unmanaged_targets": sorted(
            (dict(u) for u in graph.unmanaged_targets),
            key=lambda u: (u["id"], u["superseder"], u["path"]),
        ),
        "unbacked_inverses": sorted(
            (dict(u) for u in graph.unbacked_inverses),
            key=lambda u: (u["id"], u["superseder"]),
        ),
    }
```

Then rewire `mark_superseded` (`consolidation.py:552-613`) to build its report through the helper — replacing the inline report construction with `report = _disposition_report(graph, ids=ids)` — while leaving the `apply=True` blocking/prepare/commit tail unchanged:

```python
    project_root = project_root.resolve()
    graph = build_supersedes_graph(load_supersession_inputs(project_root))
    report = _disposition_report(graph, ids=ids)
    if not apply:
        return report
    # ... existing blocking check + prepare loop + commit tail, unchanged ...
```

Preserve the domain docstrings/comments from the original `build_supersedes_graph` on the moved block — they carry the set-vs-list and audit-verdict reasoning and must not be lost in the move.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --frozen pytest tests/test_decision_material.py tests/test_consolidation_mark_superseded.py -q`
Expected: PASS (full-field equivalence + all existing mark-superseded tests; reconcile any order-pinned assertion per the behavior-preservation note).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/consolidation.py science/tests/test_decision_material.py
git commit -m "refactor(supersede): single classifier shared by live + material paths"
```

---

## Phase 3 — Supersede plan (`supersede_plan.py`)

### Task 10: `SupersedePreviewReport` + `SupersedePlan` schemas

**Files:**
- Create: `science/src/science_tool/supersede_plan.py`
- Test: `science/tests/test_supersede_plan.py`

**Interfaces:**
- Produces: strict nested report models — `SupersededChainReport` (`survivor`, `members: list[str]`, `linear: bool`), `NonLinearReport` (`nodes: list[str]`, `reason`), `SkippedKind` (`id`, `kind`), `InvalidRelation` (`code`, `path`, `subject`, `predicate`, `object`, `message`), `TargetReport` (`id`, `superseder`, `path`, `reason`), `UnbackedInverse` (`id`, `superseder`, `reason`) — all `extra="forbid"`. `SupersedePreviewReport` composes them (NOT `applied`/`repaired` — execution-only). `SupersedePlan` (design §5.2: `schema_version`, `project_root`, `material_version`, `preview_date`, `selection: SupersedeSelection`, `decision_inputs_sha256`, `to_mark`, `to_repair`, `writes: list[PathTransition]`, `preview_report`).
- The nested shapes mirror `mark_superseded`'s dry-run dict exactly (`consolidation.py:555-611`): a plan is untrusted JSON, so `extra="forbid"` on every nested model is what makes a tampered/extra key a load-time rejection rather than a silently ignored field.

- [ ] **Step 1: Write the failing test**

```python
# science/tests/test_supersede_plan.py
from __future__ import annotations

import pytest

from science_tool.plan_common import (
    AllSupersessionMembers, ExplicitSupersessionIds, PathTransition, StateFingerprint,
)
from science_tool.supersede_plan import (
    InvalidRelation, SupersededChainReport, SupersedePlan, SupersedePreviewReport,
)


def _empty_report() -> SupersedePreviewReport:
    return SupersedePreviewReport(
        chains=[], non_linear=[], to_mark=[], skipped_kinds=[], to_repair=[],
        invalid_relations=[], archived_targets=[], unmanaged_targets=[], unbacked_inverses=[])


def test_preview_report_forbids_execution_keys() -> None:
    rpt = _empty_report()
    assert rpt.to_mark == []
    with pytest.raises(ValueError):
        SupersedePreviewReport(chains=[], non_linear=[], to_mark=[], skipped_kinds=[], to_repair=[],
                               invalid_relations=[], archived_targets=[], unmanaged_targets=[],
                               unbacked_inverses=[], applied=[])  # type: ignore[call-arg]


def test_nested_report_models_forbid_extra_keys() -> None:
    # A tampered plan cannot smuggle an unknown key past a nested model.
    with pytest.raises(ValueError):
        SupersededChainReport(survivor="a", members=["b"], linear=True, bogus=1)  # type: ignore[call-arg]
    with pytest.raises(ValueError):
        InvalidRelation(code="c", path="p", subject="s", predicate="pr", object="o",
                        message="m", extra="x")  # type: ignore[call-arg]


def test_preview_report_coerces_dicts_into_nested_models() -> None:
    rpt = SupersedePreviewReport(
        chains=[{"survivor": "a", "members": ["b"], "linear": True}],
        non_linear=[], to_mark=["b"], skipped_kinds=[], to_repair=[],
        invalid_relations=[], archived_targets=[], unmanaged_targets=[], unbacked_inverses=[])
    assert rpt.chains[0].survivor == "a"  # a typed model, not a bare dict
    with pytest.raises(ValueError):
        SupersedePreviewReport(chains=[{"survivor": "a", "members": ["b"], "linear": True, "x": 1}],
                               non_linear=[], to_mark=[], skipped_kinds=[], to_repair=[],
                               invalid_relations=[], archived_targets=[], unmanaged_targets=[],
                               unbacked_inverses=[])


def test_supersede_plan_roundtrips_and_forbids_extra() -> None:
    plan = SupersedePlan(
        schema_version=1, project_root="/p", material_version=1, preview_date="2026-07-18",
        selection=AllSupersessionMembers(kind="all"), decision_inputs_sha256="a" * 64,
        to_mark=[], to_repair=[], writes=[], preview_report=_empty_report(),
    )
    again = SupersedePlan.model_validate_json(plan.model_dump_json())
    assert again == plan
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --frozen pytest tests/test_supersede_plan.py -q`
Expected: FAIL — module missing.

- [ ] **Step 3: Write minimal implementation**

```python
# science/src/science_tool/supersede_plan.py
from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from science_tool.plan_common import PathTransition, SupersedeSelection


class SupersededChainReport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    survivor: str
    members: list[str]
    linear: bool


class NonLinearReport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nodes: list[str]
    reason: str


class SkippedKind(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    kind: str


class InvalidRelation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str
    path: str
    subject: str
    predicate: str
    object: str
    message: str


class TargetReport(BaseModel):  # archived_targets / unmanaged_targets
    model_config = ConfigDict(extra="forbid")
    id: str
    superseder: str
    path: str
    reason: str


class UnbackedInverse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    superseder: str
    reason: str


class SupersedePreviewReport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    chains: list[SupersededChainReport]
    non_linear: list[NonLinearReport]
    to_mark: list[str]
    skipped_kinds: list[SkippedKind]
    to_repair: list[str]
    invalid_relations: list[InvalidRelation]
    archived_targets: list[TargetReport]
    unmanaged_targets: list[TargetReport]
    unbacked_inverses: list[UnbackedInverse]


class SupersedePlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: int
    project_root: str
    material_version: int
    preview_date: str
    selection: SupersedeSelection
    decision_inputs_sha256: str
    to_mark: list[str]
    to_repair: list[str]
    writes: list[PathTransition]
    preview_report: SupersedePreviewReport
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --frozen pytest tests/test_supersede_plan.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/supersede_plan.py science/tests/test_supersede_plan.py
git commit -m "feat(supersede): SupersedePreviewReport + SupersedePlan schemas"
```

---

### Task 11: `plan_supersede` — preview → frozen plan

**Files:**
- Modify: `science/src/science_tool/supersede_plan.py`
- Test: `science/tests/test_supersede_plan.py`

**Interfaces:**
- Produces: `plan_supersede(project_root, *, selection, preview_date) -> SupersedePlan` (loads the decision material ONCE, then delegates) and `derive_supersede_plan(project_root, material: SupersessionDecisionMaterial, *, selection, preview_date) -> SupersedePlan` (derives from an already-built material — **no second load of decision inputs**; Gate B calls this with the material it authenticated in Gate A). Derives the selected disposition from the material-derived graph, and for each member renders the frozen postimage via `_prepare_write_with_date(..., updated_default=preview_date)`, wrapping it as a `PathTransition` (`role="entity-rewrite"`, `pre`=live fingerprint, `post`=fingerprint of the rendered text, `postimage`=rendered text). Populates the preview report from the same `_disposition_report` dict.

- [ ] **Step 1: Write the failing test**

```python
# append to science/tests/test_supersede_plan.py
from pathlib import Path

from science_tool.plan_common import AllSupersessionMembers, fingerprint
from science_tool.supersede_plan import plan_supersede


def _chain(root: Path) -> None:
    (root / "science.yaml").write_text("name: t\n", encoding="utf-8")
    d = root / "entities" / "interpretations"
    d.mkdir(parents=True)
    (d / "0001-a.md").write_text(
        "---\nid: interpretation:0001-a\nkind: interpretation\ntitle: A\nstatus: active\n"
        "relations:\n  - predicate: sci:supersedes\n    target: interpretation:0002-b\n---\nbody\n",
        encoding="utf-8")
    (d / "0002-b.md").write_text(
        "---\nid: interpretation:0002-b\nkind: interpretation\ntitle: B\nstatus: active\n---\nbody\n",
        encoding="utf-8")


def _two_supersessions(root: Path) -> None:
    # Two independent chains → two members to mark (0002-b, 0004-d), for subset + rollback tests.
    (root / "science.yaml").write_text("name: t\n", encoding="utf-8")
    d = root / "entities" / "interpretations"
    d.mkdir(parents=True)
    for sup, sub in (("0001-a", "0002-b"), ("0003-c", "0004-d")):
        (d / f"{sup}.md").write_text(
            f"---\nid: interpretation:{sup}\nkind: interpretation\ntitle: {sup}\nstatus: active\n"
            f"relations:\n  - predicate: sci:supersedes\n    target: interpretation:{sub}\n---\nbody\n",
            encoding="utf-8")
        (d / f"{sub}.md").write_text(
            f"---\nid: interpretation:{sub}\nkind: interpretation\ntitle: {sub}\nstatus: active\n---\nbody\n",
            encoding="utf-8")


def test_plan_supersede_freezes_writes_and_digest(tmp_path: Path) -> None:
    _chain(tmp_path)
    plan = plan_supersede(tmp_path, selection=AllSupersessionMembers(kind="all"),
                          preview_date="2026-07-18")
    assert plan.to_mark == ["interpretation:0002-b"]
    assert len(plan.writes) == 1
    w = plan.writes[0]
    assert w.role == "entity-rewrite"
    assert w.rel_path == "entities/interpretations/0002-b.md"
    # pre-state fingerprint matches the live file at preview time
    assert w.pre == fingerprint(tmp_path / w.rel_path)
    assert "status: superseded" in w.postimage
    assert plan.decision_inputs_sha256  # non-empty
    assert plan.preview_report.to_mark == ["interpretation:0002-b"]


def test_plan_supersede_post_mode_matches_the_live_file(tmp_path: Path) -> None:
    import os
    _chain(tmp_path)
    live = tmp_path / "entities" / "interpretations" / "0002-b.md"
    os.chmod(live, 0o640)  # a non-default mode a rewrite must preserve
    plan = plan_supersede(tmp_path, selection=AllSupersessionMembers(kind="all"),
                          preview_date="2026-07-18")
    w = plan.writes[0]
    assert w.post.mode == 0o640  # NOT a nominal 0o644
    assert w.pre.mode == 0o640
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --frozen pytest tests/test_supersede_plan.py -q`
Expected: FAIL — `plan_supersede` missing.

- [ ] **Step 3: Write minimal implementation**

```python
# add to science/src/science_tool/supersede_plan.py
from pathlib import Path

from science_tool.consolidation import (
    SupersessionDecisionMaterial, _disposition_report, build_decision_material,
    build_supersedes_graph_from_material, decision_digest,
)
from science_tool.entities import _prepare_write_with_date
from science_tool.plan_common import (
    AllSupersessionMembers, ExplicitSupersessionIds, StateFingerprint, fingerprint,
)


def _selected_ids(selection: SupersedeSelection) -> frozenset[str] | None:
    if isinstance(selection, ExplicitSupersessionIds):
        return frozenset(selection.ids)
    return None  # AllSupersessionMembers


def plan_supersede(
    project_root: Path, *, selection: SupersedeSelection, preview_date: str
) -> SupersedePlan:
    # Preview entry point: load the decision material ONCE, then derive.
    project_root = project_root.resolve()
    material = build_decision_material(project_root)
    return derive_supersede_plan(project_root, material, selection=selection, preview_date=preview_date)


def derive_supersede_plan(
    project_root: Path, material: SupersessionDecisionMaterial, *,
    selection: SupersedeSelection, preview_date: str,
) -> SupersedePlan:
    """Derive the plan from an ALREADY-BUILT decision material — no second load of decision inputs.
    Gate B passes the material it just authenticated in Gate A, so the digest surface IS the
    derivation surface (design §5.3 step 3). Rendering each member's postimage still reads that
    member's file (the body is not decision-bearing and is not part of the material), but the
    disposition is a pure function of `material`."""
    project_root = project_root.resolve()
    graph = build_supersedes_graph_from_material(material)
    ids = _selected_ids(selection)
    # Disposition from the MATERIAL-derived graph — no second filesystem load.
    report_dict = _disposition_report(graph, ids=ids)
    to_mark = list(report_dict["to_mark"])
    to_repair = list(report_dict["to_repair"])

    writes: list[PathTransition] = []
    for member in (*to_mark, *to_repair):
        prepared = _prepare_write_with_date(
            project_root, member,
            {"status": "superseded", "superseded_by": graph.superseder_by_id[member]},
            updated_default=preview_date,
        )
        rel = prepared.path.relative_to(project_root).as_posix()
        pre = fingerprint(prepared.path)
        # A supersession rewrite REPLACES an existing file, so post preserves the live mode.
        post = _fingerprint_of_text(prepared.text, mode=pre.mode)
        writes.append(PathTransition(role="entity-rewrite", rel_path=rel, pre=pre, post=post,
                                     postimage=prepared.text))

    preview_report = SupersedePreviewReport(
        chains=report_dict["chains"], non_linear=report_dict["non_linear"],
        to_mark=to_mark, skipped_kinds=report_dict["skipped_kinds"], to_repair=to_repair,
        invalid_relations=report_dict["invalid_relations"],
        archived_targets=report_dict["archived_targets"],
        unmanaged_targets=report_dict["unmanaged_targets"],
        unbacked_inverses=report_dict["unbacked_inverses"],
    )
    return SupersedePlan(
        schema_version=1, project_root=str(project_root), material_version=material.material_version,
        preview_date=preview_date, selection=selection,
        decision_inputs_sha256=decision_digest(material),
        to_mark=to_mark, to_repair=to_repair, writes=writes, preview_report=preview_report,
    )


def _fingerprint_of_text(text: str, *, mode: int | None) -> StateFingerprint:
    import hashlib
    if mode is None:
        raise ValueError("a staged entity-rewrite requires a concrete file mode")
    return StateFingerprint(existed=True, type="file",
                            content_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
                            mode=mode, symlink_target=None)
```

The `post.mode` is the live file's actual mode (`pre.mode`), so the frozen post-state is exact — not a nominal `0o644` that apply would have to reconcile. `_fingerprint_of_text` refuses a `None` mode, so a staged transition can never be built without one.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --frozen pytest tests/test_supersede_plan.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/supersede_plan.py science/tests/test_supersede_plan.py
git commit -m "feat(supersede): plan_supersede freezes disposition, writes, digest"
```

---

### Task 12: `apply_supersede_plan` — three-layer authorization + execute

**Files:**
- Modify: `science/src/science_tool/supersede_plan.py`
- Test: `science/tests/test_supersede_plan.py`

**Interfaces:**
- Produces: `apply_supersede_plan(project_root: Path, plan: SupersedePlan, *, staging_token: str) -> dict` (returns the execution report `{"applied": [...], "repaired": [...]}`). Assumes the envelope was already verified by the CLI before parsing (Task 16). Runs, in order: **structural** (project_root match, `resolve_within` every write path for containment/canonical form, `assert_staging_unique`, writes↔members bijection, `prepared.path == w.rel_path`) → **gate A** (rebuild material, compare `material_version` + digest) → **gate B by full re-derivation from the verified material** (`expected = derive_supersede_plan(project_root, material, selection=plan.selection, preview_date=plan.preview_date)` — reuses the Gate-A material, so `build_decision_material` runs exactly once per apply; `assert_same_surface(plan.writes, expected.writes)`; `expected.preview_report == plan.preview_report`; `expected.to_mark/to_repair == plan.to_mark/to_repair`; blockers in the re-derived report refuse) → **pre-state** (`matches(w.pre)`) → snapshot → `staged_write` each → verify `matches(w.post)` → rollback on failure. Re-deriving the whole plan and comparing the complete surface subsumes the ad-hoc per-write pre/postimage checks: a drifted pre, a tampered postimage, or a forged transition all make `assert_same_surface` (or the digest) fail. `SupersedeApplyError(RuntimeError)`.

- [ ] **Step 1: Write the failing test**

```python
# append to science/tests/test_supersede_plan.py
import os

from science_tool.plan_common import StateFingerprint, fingerprint
from science_tool.supersede_plan import SupersedeApplyError, apply_supersede_plan, plan_supersede


def test_apply_supersede_plan_matches_legacy_apply_byte_for_byte(tmp_path: Path) -> None:
    # Build TWO identical corpora. Apply the plan to one; run the legacy `mark_superseded(apply=True)`
    # on the other. The stamped file bytes must be EXACTLY identical — the real "replay == legacy"
    # claim, with no line-stripping. Pin the plan's preview_date to today so the `updated` line the
    # legacy clock renders and the frozen postimage agree.
    from datetime import date

    from science_tool.consolidation import mark_superseded
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir(); b.mkdir()
    _chain(a); _chain(b)
    plan = plan_supersede(a, selection=AllSupersessionMembers(kind="all"),
                          preview_date=date.today().isoformat())
    report = apply_supersede_plan(a, plan, staging_token="tkn")
    assert report["applied"] == ["interpretation:0002-b"]

    mark_superseded(b, ids=None, apply=True)
    ra = (a / "entities/interpretations/0002-b.md").read_bytes()
    rb = (b / "entities/interpretations/0002-b.md").read_bytes()
    assert ra == rb  # byte-for-byte, no normalization
    assert ra.decode("utf-8") == plan.writes[0].postimage  # plan replay is byte-exact


def test_apply_refuses_on_decision_drift(tmp_path: Path) -> None:
    # Gate A (decision digest): a change to the DECISION surface after preview — here removing 0001-a's
    # `sci:supersedes` relation so the re-derived cohort no longer marks 0002-b — is refused. The removed
    # relation moves the decision projection, so `decision_digest(material) != plan.decision_inputs_sha256`
    # (Gate A) fires FIRST, before Gate B re-derivation or the pre-state gate is reached. The member file
    # (0002-b) is left untouched, isolating decision drift from write-source drift (next test). (Contrast:
    # a NON-projected change like editing 0001-a's `title` leaves the digest, disposition, and writes all
    # identical and MUST NOT be refused — `test_non_projected_field_change_does_not_move_the_digest`,
    # Task 8, pins that.)
    _chain(tmp_path)
    plan = plan_supersede(tmp_path, selection=AllSupersessionMembers(kind="all"),
                          preview_date="2026-07-18")
    a = tmp_path / "entities" / "interpretations" / "0001-a.md"
    a.write_text(
        "---\nid: interpretation:0001-a\nkind: interpretation\ntitle: A\nstatus: active\n---\nbody\n",
        encoding="utf-8")  # supersedes relation removed → re-derived cohort marks nothing
    with pytest.raises(SupersedeApplyError):
        apply_supersede_plan(tmp_path, plan, staging_token="tkn")


def test_apply_refuses_on_write_source_drift(tmp_path: Path) -> None:
    # Gate B (write surface): a change to the MEMBER being rewritten (0002-b's `title` — NOT a
    # decision-projection field, so the digest and disposition are UNCHANGED and Gate A passes) is still
    # refused, because the re-derived postimage differs from the frozen write, so
    # `assert_same_surface(plan.writes, expected.writes)` (Gate B) fails FIRST — ahead of the later
    # pre-state gate, which would independently catch it via the changed pre-fingerprint. This is the
    # drift path a non-projected change to the *rendered* file legitimately triggers.
    _chain(tmp_path)
    plan = plan_supersede(tmp_path, selection=AllSupersessionMembers(kind="all"),
                          preview_date="2026-07-18")
    b = tmp_path / "entities" / "interpretations" / "0002-b.md"
    b.write_text(b.read_text(encoding="utf-8").replace("title: B", "title: B-EDITED"), encoding="utf-8")
    with pytest.raises(SupersedeApplyError):
        apply_supersede_plan(tmp_path, plan, staging_token="tkn")


def test_apply_refuses_tampered_postimage(tmp_path: Path) -> None:
    import hashlib
    _chain(tmp_path)
    plan = plan_supersede(tmp_path, selection=AllSupersessionMembers(kind="all"),
                          preview_date="2026-07-18")
    w = plan.writes[0]
    tampered = w.postimage.replace("superseded_by: interpretation:0001-a",
                                   "superseded_by: interpretation:9999-z")
    bad_post = StateFingerprint(existed=True, type="file",
                                content_sha256=hashlib.sha256(tampered.encode()).hexdigest(),
                                mode=w.post.mode, symlink_target=None)
    plan.writes[0] = w.model_copy(update={"postimage": tampered, "post": bad_post})
    with pytest.raises(SupersedeApplyError):
        apply_supersede_plan(tmp_path, plan, staging_token="tkn")


def test_apply_refuses_tampered_preview_report(tmp_path: Path) -> None:
    # A report key the re-derivation would not produce must be rejected even if the writes are honest.
    _chain(tmp_path)
    plan = plan_supersede(tmp_path, selection=AllSupersessionMembers(kind="all"),
                          preview_date="2026-07-18")
    bad = plan.preview_report.model_copy(update={"to_mark": ["interpretation:9999-z"]})
    plan = plan.model_copy(update={"preview_report": bad})
    with pytest.raises(SupersedeApplyError):
        apply_supersede_plan(tmp_path, plan, staging_token="tkn")


def test_apply_refuses_absolute_rel_path_escape(tmp_path: Path) -> None:
    _chain(tmp_path)
    plan = plan_supersede(tmp_path, selection=AllSupersessionMembers(kind="all"),
                          preview_date="2026-07-18")
    w = plan.writes[0]
    plan.writes[0] = w.model_copy(update={"rel_path": "/etc/evil.md"})
    with pytest.raises(SupersedeApplyError):
        apply_supersede_plan(tmp_path, plan, staging_token="tkn")


def test_apply_refuses_unsupported_schema_version(tmp_path: Path) -> None:
    _chain(tmp_path)
    plan = plan_supersede(tmp_path, selection=AllSupersessionMembers(kind="all"),
                          preview_date="2026-07-18")
    plan = plan.model_copy(update={"schema_version": 999})
    with pytest.raises(SupersedeApplyError):
        apply_supersede_plan(tmp_path, plan, staging_token="tkn")


def test_kill_after_entity_write_leaves_a_classifiable_state(tmp_path: Path) -> None:
    # Kill matrix — after each entity write: the written member holds its postimage; a simulated
    # kill (BaseException) bypasses rollback, so the survivor is a declared post-state, not corrupt.
    class _Kill(BaseException):
        pass

    _chain(tmp_path)
    plan = plan_supersede(tmp_path, selection=AllSupersessionMembers(kind="all"),
                          preview_date="2026-07-18")
    target = tmp_path / "entities" / "interpretations" / "0002-b.md"

    def fault(label: str) -> None:
        if label == "written:entities/interpretations/0002-b.md":
            raise _Kill()

    with pytest.raises(_Kill):
        apply_supersede_plan(tmp_path, plan, staging_token="tkn", _fault=fault)
    assert target.read_text(encoding="utf-8") == plan.writes[0].postimage  # complete post-state, no rollback


def test_apply_supersede_loads_decision_material_once(tmp_path: Path, monkeypatch) -> None:
    # C2: Gate B derives from the Gate-A-verified material, so `build_decision_material` runs exactly
    # once per apply — the digest surface authenticated in Gate A IS the derivation surface.
    import science_tool.supersede_plan as sp
    _chain(tmp_path)
    plan = plan_supersede(tmp_path, selection=AllSupersessionMembers(kind="all"), preview_date="2026-07-18")
    calls = {"n": 0}
    real = sp.build_decision_material

    def counting(root: Path) -> "SupersessionDecisionMaterial":
        calls["n"] += 1
        return real(root)

    monkeypatch.setattr(sp, "build_decision_material", counting)
    apply_supersede_plan(tmp_path, plan, staging_token="tok")
    assert calls["n"] == 1  # Gate A only; a second load would mean Gate B re-derived from fresh FS


def test_apply_refuses_material_version_mismatch(tmp_path: Path) -> None:
    # I8: a plan whose material_version does not match the current material is refused at Gate A.
    _chain(tmp_path)
    plan = plan_supersede(tmp_path, selection=AllSupersessionMembers(kind="all"), preview_date="2026-07-18")
    stale = plan.model_copy(update={"material_version": plan.material_version + 1})
    with pytest.raises(SupersedeApplyError, match="material_version"):
        apply_supersede_plan(tmp_path, stale, staging_token="tok")


def test_apply_explicit_ids_subset_marks_only_that_subset(tmp_path: Path) -> None:
    # I8 (selection authenticity, positive): an explicit_ids selection applies exactly its scoped
    # rederivation — the un-selected eligible member stays untouched, not the full sweep.
    _two_supersessions(tmp_path)
    plan = plan_supersede(
        tmp_path,
        selection=ExplicitSupersessionIds(kind="explicit_ids", ids=["interpretation:0002-b"]),
        preview_date="2026-07-18",
    )
    assert plan.to_mark == ["interpretation:0002-b"]
    apply_supersede_plan(tmp_path, plan, staging_token="tok")
    b = (tmp_path / "entities" / "interpretations" / "0002-b.md").read_text(encoding="utf-8")
    d = (tmp_path / "entities" / "interpretations" / "0004-d.md").read_text(encoding="utf-8")
    assert "status: superseded" in b
    assert "status: superseded" not in d  # the un-selected member is untouched


def test_rollback_after_first_of_two_entity_writes_restores_surface(tmp_path: Path) -> None:
    # I8: a CAUGHT failure (not a kill) after the first of two writes rolls BOTH members back to pre.
    _two_supersessions(tmp_path)
    plan = plan_supersede(tmp_path, selection=AllSupersessionMembers(kind="all"), preview_date="2026-07-18")
    assert len(plan.writes) == 2
    first_rel = plan.writes[0].rel_path
    before = {w.rel_path: (tmp_path / w.rel_path).read_bytes() for w in plan.writes}

    def fault(label: str) -> None:
        if label == f"written:{first_rel}":
            raise RuntimeError("boom after first write")  # Exception → caught → rollback runs

    with pytest.raises(SupersedeApplyError):
        apply_supersede_plan(tmp_path, plan, staging_token="tok", _fault=fault)
    for rel, data in before.items():
        assert (tmp_path / rel).read_bytes() == data  # both fully restored, no half-applied surface


def test_crlf_body_normalized_identically_across_preview_applyplan_and_legacy(tmp_path: Path) -> None:
    # I4 / design §9: characterize body normalization across the THREE writer routes — preview
    # (plan_supersede), saved-plan apply (apply_supersede_plan), and legacy apply
    # (mark_superseded(apply=True)). A CRLF + leading-blank-line body is folded to the writer's normal
    # form identically by all three. NOT a preservation claim — the CRLF/leading blanks are removed.
    from science_tool.consolidation import mark_superseded

    def seed(root: Path) -> None:
        (root / "science.yaml").write_text("name: t\n", encoding="utf-8")
        d = root / "entities" / "interpretations"
        d.mkdir(parents=True)
        (d / "0001-a.md").write_bytes(
            b"---\r\nid: interpretation:0001-a\r\nkind: interpretation\r\ntitle: A\r\nstatus: active\r\n"
            b"relations:\r\n  - predicate: sci:supersedes\r\n    target: interpretation:0002-b\r\n---\r\n\r\nbody\r\n")
        (d / "0002-b.md").write_bytes(
            b"---\r\nid: interpretation:0002-b\r\nkind: interpretation\r\ntitle: B\r\nstatus: active\r\n---\r\n\r\nbody line\r\n")

    rel = "entities/interpretations/0002-b.md"
    root_p = tmp_path / "preview"
    root_p.mkdir()
    seed(root_p)
    plan = plan_supersede(root_p, selection=AllSupersessionMembers(kind="all"), preview_date="2026-07-18")
    preview_body = plan.writes[0].postimage.split("---\n", 2)[2]           # preview route
    apply_supersede_plan(root_p, plan, staging_token="tok")
    applied_body = (root_p / rel).read_text(encoding="utf-8").split("---\n", 2)[2]  # apply-plan route
    root_l = tmp_path / "legacy"
    root_l.mkdir()
    seed(root_l)
    mark_superseded(root_l, ids=None, apply=True)
    legacy_body = (root_l / rel).read_text(encoding="utf-8").split("---\n", 2)[2]   # legacy apply route
    assert preview_body == applied_body == legacy_body                    # identical normal form
    assert "\r" not in applied_body and not applied_body.startswith("\n")  # CRLF + leading blank removed


def test_apply_supersede_refuses_project_root_mismatch(tmp_path: Path) -> None:
    # design §9 (drift rejection): a plan whose project_root does not match the target is refused.
    _chain(tmp_path)
    plan = plan_supersede(tmp_path, selection=AllSupersessionMembers(kind="all"), preview_date="2026-07-18")
    other = plan.model_copy(update={"project_root": str(tmp_path / "elsewhere")})
    with pytest.raises(SupersedeApplyError):
        apply_supersede_plan(tmp_path, other, staging_token="tok")


def test_apply_supersede_refuses_report_hiding_a_blocker(tmp_path: Path) -> None:
    # design §9 (report binding): a plan whose preview_report hides a blocker (an unbacked inverse) is
    # refused at Gate B — the re-derived report still carries it.
    (tmp_path / "science.yaml").write_text("name: t\n", encoding="utf-8")
    d = tmp_path / "entities" / "interpretations"
    d.mkdir(parents=True)
    (d / "0001-a.md").write_text(  # no supersedes edge — so 0002-b's inverse is UNBACKED
        "---\nid: interpretation:0001-a\nkind: interpretation\ntitle: A\nstatus: active\n---\nbody\n",
        encoding="utf-8")
    (d / "0002-b.md").write_text(
        "---\nid: interpretation:0002-b\nkind: interpretation\ntitle: B\nstatus: active\n"
        "superseded_by: interpretation:0001-a\n---\nbody\n", encoding="utf-8")
    plan = plan_supersede(tmp_path, selection=AllSupersessionMembers(kind="all"), preview_date="2026-07-18")
    assert plan.preview_report.unbacked_inverses  # the blocker is surfaced at preview
    tampered = plan.model_copy(update={
        "preview_report": plan.preview_report.model_copy(update={"unbacked_inverses": []})})
    with pytest.raises(SupersedeApplyError, match="preview report"):
        apply_supersede_plan(tmp_path, tampered, staging_token="tok")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --frozen pytest tests/test_supersede_plan.py -q`
Expected: FAIL — `apply_supersede_plan` missing.

- [ ] **Step 3: Write minimal implementation**

```python
# add to science/src/science_tool/supersede_plan.py
from typing import Callable

from science_tool.consolidation import SupersessionError
from science_tool.plan_common import (
    PathEscape, RollbackHalt, StagingError, SurfaceMismatch, assert_same_surface,
    assert_staging_unique, matches, resolve_within, rollback_transitions, snapshot_paths, staged_write,
)

_SUPERSEDE_PLAN_SCHEMA = 1


class SupersedeApplyError(RuntimeError):
    pass


def apply_supersede_plan(project_root: Path, plan: SupersedePlan, *, staging_token: str,
                         _fault: Callable[[str], None] | None = None) -> dict:
    def fault(label: str) -> None:
        if _fault is not None:
            _fault(label)  # test-only kill seam; a BaseException here bypasses rollback

    project_root = project_root.resolve()
    if plan.schema_version != _SUPERSEDE_PLAN_SCHEMA:
        raise SupersedeApplyError(
            f"unsupported plan schema_version {plan.schema_version} (this tool writes "
            f"{_SUPERSEDE_PLAN_SCHEMA})")
    if plan.project_root != str(project_root):
        raise SupersedeApplyError("plan project_root does not match")

    # Structural — containment, canonical paths, staging uniqueness, bijection (before any FS write)
    members = [*plan.to_mark, *plan.to_repair]
    try:
        targets = [resolve_within(project_root, w.rel_path) for w in plan.writes]
        assert_staging_unique(project_root, targets, staging_token)
    except (PathEscape, StagingError) as exc:
        raise SupersedeApplyError(str(exc)) from exc
    if len({w.rel_path for w in plan.writes}) != len(plan.writes):
        raise SupersedeApplyError("duplicate write paths")
    if len(members) != len(set(members)) or len(members) != len(plan.writes):
        raise SupersedeApplyError("writes/disposition are not a bijection")

    # Gate A — corpus drift
    material = build_decision_material(project_root)
    if material.material_version != plan.material_version:
        raise SupersedeApplyError("material_version mismatch")
    if decision_digest(material) != plan.decision_inputs_sha256:
        raise SupersedeApplyError("corpus changed since preview (decision digest mismatch)")

    # Gate B — re-derive the WHOLE plan FROM THE GATE-A-VERIFIED MATERIAL (no second decision load;
    # design §5.3 step 3). `derive_supersede_plan` reads each member's body to render, but never
    # reloads decision inputs — so the digest surface authenticated above IS the derivation surface.
    try:
        expected = derive_supersede_plan(project_root, material, selection=plan.selection,
                                         preview_date=plan.preview_date)
    except SupersessionError as exc:
        raise SupersedeApplyError(str(exc)) from exc
    try:
        assert_same_surface(plan.writes, expected.writes)
    except SurfaceMismatch as exc:
        raise SupersedeApplyError(f"declared writes differ from re-derived: {exc}") from exc
    if expected.preview_report != plan.preview_report:
        raise SupersedeApplyError("re-derived preview report differs from the plan")
    if expected.to_mark != plan.to_mark or expected.to_repair != plan.to_repair:
        raise SupersedeApplyError("re-derived disposition differs from the plan")
    rpt = expected.preview_report
    if rpt.invalid_relations or rpt.unbacked_inverses:
        raise SupersedeApplyError("corpus-wide blockers present; refusing")

    # Pre-state gate
    for target, w in zip(targets, plan.writes, strict=True):
        if not matches(w.pre, target):
            raise SupersedeApplyError(f"pre-state changed for {w.rel_path}")

    # Execute
    snap = snapshot_paths(targets)
    try:
        for target, w in zip(targets, plan.writes, strict=True):
            staged_write(target, w.postimage, w.post.mode, staging_token,
                         target_pre=w.pre)  # mode concrete (Task 11); target_pre guards cleanup (§3.3)
            fault(f"written:{w.rel_path}")  # kill boundary: after each entity write
        for target, w in zip(targets, plan.writes, strict=True):
            if not matches(w.post, target):
                raise SupersedeApplyError(f"post-state verification failed for {w.rel_path}")
    except Exception as exc:
        rollback_transitions(plan.writes, project_root, snap)  # may raise RollbackHalt (propagates)
        if isinstance(exc, SupersedeApplyError):
            raise
        # A staged-write StagingError etc. becomes a SupersedeApplyError once the corpus is restored.
        raise SupersedeApplyError(f"apply failed and rolled back: {exc}") from exc
    return {"applied": list(plan.to_mark), "repaired": list(plan.to_repair)}
```

Notes: `w.post.mode` is a concrete int by Task 11's `_fingerprint_of_text` guard, so no `or 0o644` fallback. `rollback_transitions` runs on the `except Exception` path only — a `BaseException` (e.g. a simulated process kill) is deliberately NOT caught, so no rollback runs and the survivor state is left for classification (design §2). If rollback itself raises `RollbackHalt`, that propagates distinctly rather than being masked by the wrap.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --frozen pytest tests/test_supersede_plan.py -q`
Expected: PASS (legacy byte-match, drift, postimage tamper, report tamper, path escape).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/supersede_plan.py science/tests/test_supersede_plan.py
git commit -m "feat(supersede): apply_supersede_plan three-layer authorization + staged execute"
```

---

## Phase 4 — Archive plan (`archive_plan.py`)

### Task 13: `ArchivePreviewReport` + `ArchivePlan`/`ArchiveMove` schemas

**Files:**
- Create: `science/src/science_tool/archive_plan.py`
- Test: `science/tests/test_archive_plan.py`

**Interfaces:**
- Produces: `ArchiveCandidate` (`extra="forbid"`; `id`, `kind: str|None`, `status: str|None`, `original_path: str|None`, `superseded_by: str|None`, `resynthesized_into: list[str]`, `inbound_live_refs: list[str]`) mirroring `archive_entities`' candidate dict; `PlannedArchiveRow` (subclass of the canonical `ArchiveRow` that tightens `model_config` to `extra="forbid"` — a plan is untrusted, so a frozen row must reject unknown keys even though the shared `ArchiveRow` that parses append-only index files tolerates future ones); `ArchivePreviewReport` (`candidates: list[ArchiveCandidate]`); `ArchiveMove` (`id`, `original_path`, `archive_path`, `row: PlannedArchiveRow`); `ArchivePlan` (design §4.1: `schema_version`, `project_root`, `op`, `now`, `selection: ArchiveSelection`, `moves`, `index: PathTransition | None = None`, `transitions: list[PathTransition]`, `preview_report`; a `_index_matches_moves` model validator enforces moves↔index).

- [ ] **Step 1: Write the failing test**

```python
# science/tests/test_archive_plan.py
from __future__ import annotations

import pytest

from science_tool.plan_common import ArchiveStatusSweep, PathTransition, StateFingerprint
from science_tool.archive_plan import (
    ArchiveCandidate, ArchiveMove, ArchivePlan, ArchivePreviewReport, PlannedArchiveRow,
)


def _fp_file(sha: str) -> StateFingerprint:
    return StateFingerprint(existed=True, type="file", content_sha256=sha, mode=0o644, symlink_target=None)


def test_archive_plan_roundtrips_and_forbids_extra() -> None:
    # A VALID empty plan (moves=[], index=None, transitions=[]) round-trips through JSON. The
    # moves↔index invariant means this is the only coherent empty shape.
    plan = ArchivePlan(
        schema_version=1, project_root="/p", op="archive", now="2026-07-18T00:00:00Z",
        selection=ArchiveStatusSweep(kind="all_by_status", statuses=["superseded"]),
        moves=[], index=None, transitions=[],
        preview_report=ArchivePreviewReport(candidates=[]),
    )
    assert ArchivePlan.model_validate_json(plan.model_dump_json()) == plan


def test_archive_plan_rejects_incoherent_moves_index_shapes() -> None:
    # I5: the _index_matches_moves validator rejects both incoherent shapes at construction time.
    import hashlib
    body = "index bytes\n"
    idx = PathTransition(role="archive-index", rel_path="entities/_archive/archive-index.jsonl",
                         pre=StateFingerprint(existed=False, type=None, content_sha256=None, mode=None, symlink_target=None),
                         post=_fp_file(hashlib.sha256(body.encode()).hexdigest()), postimage=body)
    common = dict(schema_version=1, project_root="/p", op="archive", now="2026-07-18T00:00:00Z",
                  selection=ArchiveStatusSweep(kind="all_by_status", statuses=["superseded"]),
                  preview_report=ArchivePreviewReport(candidates=[]))
    with pytest.raises(ValueError, match="empty cohort"):
        ArchivePlan(**common, moves=[], index=idx, transitions=[])  # empty cohort with an index
    a_move = ArchiveMove(id="interpretation:0001-x", original_path="entities/interpretations/0001-x.md",
                         archive_path="entities/_archive/interpretations/0001-x.md",
                         row=PlannedArchiveRow(op="archive", id="interpretation:0001-x"))
    with pytest.raises(ValueError, match="non-empty cohort"):
        ArchivePlan(**common, moves=[a_move], index=None, transitions=[])  # moves but no index


def test_nested_archive_models_forbid_extra_keys() -> None:
    with pytest.raises(ValueError):
        ArchivePreviewReport(candidates=[], bogus=1)  # type: ignore[call-arg]
    with pytest.raises(ValueError):
        ArchiveCandidate(id="x:1", kind="k", status="superseded", original_path="p",
                         superseded_by=None, resynthesized_into=[], inbound_live_refs=[],
                         bogus=1)  # type: ignore[call-arg]
    with pytest.raises(ValueError):
        PlannedArchiveRow(op="archive", id="x:1", unknown_future_key="v")  # type: ignore[call-arg]


def test_planned_row_is_a_valid_archive_row() -> None:
    # PlannedArchiveRow IS an ArchiveRow (subclass), so a frozen row is guaranteed row-shaped.
    from science_tool.archive import ArchiveRow
    row = PlannedArchiveRow(op="archive", id="interpretation:0001-x", archived_at="2026-07-18T00:00:00Z")
    assert isinstance(row, ArchiveRow)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --frozen pytest tests/test_archive_plan.py -q`
Expected: FAIL — module missing.

- [ ] **Step 3: Write minimal implementation**

```python
# science/src/science_tool/archive_plan.py
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

from science_tool.archive import ArchiveRow
from science_tool.plan_common import ArchiveSelection, PathTransition


class PlannedArchiveRow(ArchiveRow):
    # The canonical ArchiveRow tolerates unknown keys (it parses append-only index files that may
    # carry future fields); a frozen plan is untrusted, so tighten to extra="forbid" here.
    model_config = ConfigDict(extra="forbid")


class ArchiveCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    kind: str | None
    status: str | None
    original_path: str | None
    superseded_by: str | None
    resynthesized_into: list[str]
    inbound_live_refs: list[str]


class ArchivePreviewReport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    candidates: list[ArchiveCandidate]


class ArchiveMove(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    original_path: str
    archive_path: str
    row: PlannedArchiveRow


class ArchivePlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: int
    project_root: str
    op: Literal["archive"]
    now: str
    selection: ArchiveSelection
    moves: list[ArchiveMove]
    index: PathTransition | None = None  # None for an empty cohort (a no-op plan; legacy archive no-ops too)
    transitions: list[PathTransition]
    preview_report: ArchivePreviewReport

    @model_validator(mode="after")
    def _index_matches_moves(self) -> "ArchivePlan":
        # I5: the moves↔index relationship is a schema invariant, not just an apply-time check. A
        # non-empty cohort MUST carry an index; an empty cohort MUST carry neither an index nor any
        # transition. This makes a malformed plan unconstructable rather than merely refused later.
        if self.moves and self.index is None:
            raise ValueError("a non-empty cohort must carry an archive-index transition")
        if not self.moves and (self.index is not None or self.transitions):
            raise ValueError("an empty cohort must carry no index and no transitions")
        return self
```

The `index` is optional because an **empty cohort** (zero candidates) must be a no-op, matching legacy `archive`'s behavior: no move, no directory creation, and no empty index file written into a possibly-nonexistent `_archive/`. `plan_archive` sets `index=None` when there are no moves, and `apply_archive_plan` performs no filesystem writes for such a plan. The `_index_matches_moves` validator makes the moves↔index invariant structural (design §4.1).

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --frozen pytest tests/test_archive_plan.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/archive_plan.py science/tests/test_archive_plan.py
git commit -m "feat(archive): ArchivePreviewReport + ArchivePlan/ArchiveMove schemas"
```

---

### Task 14: `plan_archive` — preview → frozen plan (literal index postimage)

**Files:**
- Modify: `science/src/science_tool/archive_plan.py`
- Test: `science/tests/test_archive_plan.py`

**Interfaces:**
- Produces: `plan_archive(project_root: Path, *, selection: ArchiveSelection, now: str) -> ArchivePlan`. Reuses `archive._candidate_rows`/`_scope_rows_to_allowlist`/`_inbound_live_refs`/`derive_archive_path`/`archive_index_path`. Freezes each candidate `ArchiveRow` with `archived_at=now`; builds the **literal** index postimage as `current_index_bytes + "".join(json.dumps(row, sort_keys=True)+"\n")`; builds `moves` + `transitions` (archive-src/archive-dst pairs + created-dir entries) + the index `PathTransition`.

- [ ] **Step 1: Write the failing test**

```python
# append to science/tests/test_archive_plan.py
from pathlib import Path

from science_tool.plan_common import ArchiveStatusSweep, fingerprint
from science_tool.archive_plan import plan_archive


def _superseded(root: Path) -> None:
    (root / "science.yaml").write_text("name: t\n", encoding="utf-8")
    d = root / "entities" / "interpretations"
    d.mkdir(parents=True)
    (d / "0001-x.md").write_text(
        "---\nid: interpretation:0001-x\nkind: interpretation\ntitle: X\nstatus: superseded\n---\nbody\n",
        encoding="utf-8")


def test_plan_archive_freezes_move_and_literal_index(tmp_path: Path) -> None:
    _superseded(tmp_path)
    plan = plan_archive(tmp_path, selection=ArchiveStatusSweep(kind="all_by_status", statuses=["superseded"]),
                        now="2026-07-18T00:00:00Z")
    assert len(plan.moves) == 1
    m = plan.moves[0]
    assert m.id == "interpretation:0001-x"
    assert m.original_path == "entities/interpretations/0001-x.md"
    assert m.archive_path == "entities/_archive/interpretations/0001-x.md"
    assert m.row.archived_at == "2026-07-18T00:00:00Z"  # a typed PlannedArchiveRow, not a dict
    assert plan.index.role == "archive-index"
    assert plan.index.postimage.endswith("\n")
    assert "interpretation:0001-x" in plan.index.postimage
    # a src transition exists with the live pre-state
    src = [t for t in plan.transitions if t.role == "archive-src"][0]
    assert src.pre == fingerprint(tmp_path / src.rel_path)


def test_index_postimage_matches_canonical_append_row_serialization(tmp_path: Path) -> None:
    # The frozen index bytes must be exactly what append_row would have written, or the index
    # will not round-trip through load_archive_index.
    import json
    _superseded(tmp_path)
    plan = plan_archive(tmp_path, selection=ArchiveStatusSweep(kind="all_by_status", statuses=["superseded"]),
                        now="2026-07-18T00:00:00Z")
    expected = json.dumps(plan.moves[0].row.model_dump(), sort_keys=True) + "\n"
    assert plan.index.postimage == expected


def test_plan_archive_declares_every_missing_ancestor_dir(tmp_path: Path) -> None:
    # Finding 4: apply does mkdir(parents=True); every ancestor it would create must be declared,
    # or rollback has no state for the undeclared ones.
    _superseded(tmp_path)
    plan = plan_archive(tmp_path, selection=ArchiveStatusSweep(kind="all_by_status", statuses=["superseded"]),
                        now="2026-07-18T00:00:00Z")
    created = sorted(t.rel_path for t in plan.transitions if t.role == "created-dir")
    assert created == ["entities/_archive", "entities/_archive/interpretations"]


def test_plan_archive_empty_cohort_is_a_noop_plan(tmp_path: Path) -> None:
    # No superseded entities → no moves, no transitions, and NO index transition (legacy no-op).
    (tmp_path / "science.yaml").write_text("name: t\n", encoding="utf-8")
    (tmp_path / "entities" / "interpretations").mkdir(parents=True)
    plan = plan_archive(tmp_path, selection=ArchiveStatusSweep(kind="all_by_status", statuses=["superseded"]),
                        now="2026-07-18T00:00:00Z")
    assert plan.moves == []
    assert plan.transitions == []
    assert plan.index is None
    assert plan.preview_report.candidates == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --frozen pytest tests/test_archive_plan.py -q`
Expected: FAIL — `plan_archive` missing.

- [ ] **Step 3: Write minimal implementation**

```python
# add to science/src/science_tool/archive_plan.py
import hashlib
import json
from pathlib import Path

from science_tool.archive import (
    archive_index_path, derive_archive_path, _candidate_rows,
    _inbound_live_refs, _scope_rows_to_allowlist,
)
from science_tool.plan_common import (
    ArchiveStatusSweep, ExplicitArchiveIds, StateFingerprint, fingerprint,
)

_ABSENT = StateFingerprint(existed=False, type=None, content_sha256=None, mode=None, symlink_target=None)


def _fp_of_bytes(data: bytes, mode: int) -> StateFingerprint:
    return StateFingerprint(existed=True, type="file",
                            content_sha256=hashlib.sha256(data).hexdigest(), mode=mode, symlink_target=None)


def _missing_ancestor_dirs(project_root: Path, dst_abs: Path, declared: set[Path]) -> list[Path]:
    """Every directory apply's `mkdir(parents=True)` would create for `dst_abs`, that does not yet
    exist and is not already declared — ordered OUTER→INNER so reverse-order rollback removes the
    innermost first. Finding 4: declaring only `dst.parent` leaves ancestors like `entities/_archive`
    with no transition or rollback state."""
    root = project_root.resolve()
    chain: list[Path] = []
    cur = dst_abs.parent
    while cur != root:
        chain.append(cur)  # inner first
        if root not in cur.parents:
            break  # safety: never walk above the project root
        cur = cur.parent
    chain.reverse()  # outer -> inner
    return [d for d in chain if not d.exists() and d not in declared]


def plan_archive(project_root: Path, *, selection: ArchiveSelection, now: str) -> ArchivePlan:
    project_root = project_root.resolve()
    if isinstance(selection, ArchiveStatusSweep):
        statuses = frozenset(selection.statuses)
        rows = _candidate_rows(project_root, statuses)
    else:  # ExplicitArchiveIds
        statuses = frozenset(selection.allowed_statuses)
        rows = _scope_rows_to_allowlist(
            project_root, _candidate_rows(project_root, statuses), frozenset(selection.ids), statuses)
    inbound = _inbound_live_refs(project_root, {r.id for r in rows})

    moves: list[ArchiveMove] = []
    transitions: list[PathTransition] = []
    created_dirs: set[Path] = set()
    dir_post = StateFingerprint(existed=True, type="dir", content_sha256=None, mode=0o755,
                                symlink_target=None)
    for r in rows:
        frozen = PlannedArchiveRow(**r.model_copy(update={"archived_at": now}).model_dump())
        original = r.original_path
        archived = derive_archive_path(original)
        src_abs = project_root / original
        dst_abs = project_root / archived
        src_pre = fingerprint(src_abs)
        moves.append(ArchiveMove(id=r.id, original_path=original, archive_path=archived, row=frozen))
        # created-dir transitions FIRST (outer→inner), then src, then dst -- so reverse-order
        # rollback removes dst, restores src, then rmdir's inner→outer.
        for d in _missing_ancestor_dirs(project_root, dst_abs, created_dirs):
            created_dirs.add(d)
            transitions.append(PathTransition(role="created-dir",
                               rel_path=d.relative_to(project_root).as_posix(),
                               pre=_ABSENT, post=dir_post))
        transitions.append(PathTransition(role="archive-src", rel_path=original, pre=src_pre,
                                          post=_ABSENT))
        transitions.append(PathTransition(role="archive-dst", rel_path=archived, pre=_ABSENT,
                                          post=StateFingerprint(existed=True, type="file",
                                          content_sha256=src_pre.content_sha256, mode=src_pre.mode,
                                          symlink_target=None)))

    # Empty cohort → a no-op plan (no index transition), matching legacy `archive`'s no-op. Writing
    # an empty index into a possibly-absent `_archive/` would both create debris and diverge from legacy.
    index: PathTransition | None = None
    if moves:
        index_abs = archive_index_path(project_root)
        pre_bytes = index_abs.read_bytes() if index_abs.exists() else b""
        # EXACTLY append_row's serialization (json.dumps(model_dump, sort_keys=True) + "\n"), so the
        # frozen index round-trips through load_archive_index.
        appended = "".join(json.dumps(m.row.model_dump(), sort_keys=True) + "\n" for m in moves)
        post_bytes = pre_bytes + appended.encode("utf-8")
        index_pre = fingerprint(index_abs)
        index_mode = index_pre.mode if index_pre.existed else 0o644
        index = PathTransition(role="archive-index",
                               rel_path=index_abs.relative_to(project_root).as_posix(),
                               pre=index_pre, post=_fp_of_bytes(post_bytes, index_mode),
                               postimage=post_bytes.decode("utf-8"))

    report = ArchivePreviewReport(candidates=[
        ArchiveCandidate(id=r.id, kind=r.kind, status=r.status, original_path=r.original_path,
                         superseded_by=r.superseded_by, resynthesized_into=list(r.resynthesized_into),
                         inbound_live_refs=inbound.get(r.id, [])) for r in rows])
    return ArchivePlan(schema_version=1, project_root=str(project_root), op="archive", now=now,
                       selection=selection, moves=moves, index=index, transitions=transitions,
                       preview_report=report)
```

Implementer note: `_candidate_rows` returns `ArchiveRow`s carrying `id`/`kind`/`status`/`superseded_by`/`resynthesized_into`/`original_path` (`archive.py:118-148`); `PlannedArchiveRow(**row.model_dump())` re-validates the frozen row under `extra="forbid"`. `derive_archive_path`/`archive_index_path` are module functions (`archive.py:65`, `:61`).

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --frozen pytest tests/test_archive_plan.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/archive_plan.py science/tests/test_archive_plan.py
git commit -m "feat(archive): plan_archive freezes moves + literal index postimage"
```

---

### Task 15: `apply_archive_plan` — gate B + os.rename moves + os.replace index

**Files:**
- Modify: `science/src/science_tool/archive_plan.py`
- Test: `science/tests/test_archive_plan.py`

**Interfaces:**
- Produces: `apply_archive_plan(project_root: Path, plan: ArchivePlan, *, staging_token: str, _fault: Callable[[str], None] | None = None) -> dict` (returns `{"applied": [...], "skipped": [...]}`). `_fault` is a **test-only** fault seam, called with a label at each mutation boundary; a test may raise a `BaseException` from it to simulate a process kill (uncaught → no rollback → the survivor state is left for classification). Envelope pre-verified by CLI. Runs, in order: **schema_version** guard → project_root match → **gate B by full re-derivation FIRST** (`expected == plan` on moves, transition surface incl. optional index, `preview_report`) → **empty-cohort no-op** (only after Gate B confirms the live corpus also derives an empty cohort — an empty saved plan against a corpus that gained an eligible entity is refused as drift, I5; `index` must be `None`, no transitions) → **structural** (`resolve_within` every transition/move path, canonical archive paths, `assert_staging_unique` for the index, no dup move ids) → **pre-state** → snapshot → create each **declared** dir (`mkdir(parents=False)`), `os.rename` moves (EXDEV refusal) + parent fsync, `staged_write` index → post verify → on `Exception`, rollback then wrap (preserving `RollbackHalt`). `ArchiveApplyError(RuntimeError)`.

- [ ] **Step 1: Write the failing test**

```python
# append to science/tests/test_archive_plan.py
from science_tool.archive_plan import ArchiveApplyError, apply_archive_plan, plan_archive
from science_tool.plan_common import staging_path_for


class _Kill(BaseException):
    """Simulates an uncaught process kill — NOT an Exception, so apply's rollback never runs."""


def test_apply_archive_plan_moves_entity_and_writes_index(tmp_path: Path) -> None:
    _superseded(tmp_path)
    plan = plan_archive(tmp_path, selection=ArchiveStatusSweep(kind="all_by_status", statuses=["superseded"]),
                        now="2026-07-18T00:00:00Z")
    report = apply_archive_plan(tmp_path, plan, staging_token="tok")
    assert report["applied"] == ["interpretation:0001-x"]
    assert not (tmp_path / "entities" / "interpretations" / "0001-x.md").exists()
    assert (tmp_path / "entities" / "_archive" / "interpretations" / "0001-x.md").exists()
    idx = (tmp_path / "entities" / "_archive" / "archive-index.jsonl").read_text(encoding="utf-8")
    assert "interpretation:0001-x" in idx
    assert idx == plan.index.postimage
    from science_tool.archive import load_archive_index
    assert "interpretation:0001-x" in load_archive_index(tmp_path).active_by_id


def test_apply_archive_empty_cohort_is_a_noop(tmp_path: Path) -> None:
    # No candidates → apply writes nothing and never touches a (possibly-absent) _archive/.
    (tmp_path / "science.yaml").write_text("name: t\n", encoding="utf-8")
    (tmp_path / "entities" / "interpretations").mkdir(parents=True)
    plan = plan_archive(tmp_path, selection=ArchiveStatusSweep(kind="all_by_status", statuses=["superseded"]),
                        now="2026-07-18T00:00:00Z")
    report = apply_archive_plan(tmp_path, plan, staging_token="tok")
    assert report == {"applied": [], "skipped": []}
    assert not (tmp_path / "entities" / "_archive").exists()  # no debris


def test_apply_empty_cohort_refuses_when_corpus_gained_an_eligible_entity(tmp_path: Path) -> None:
    # I5: an empty saved plan must still pass Gate B. If the corpus gained an eligible entity between
    # preview and apply, the re-derivation is non-empty ≠ the empty plan → refused as drift, NOT a
    # silent successful no-op.
    (tmp_path / "science.yaml").write_text("name: t\n", encoding="utf-8")
    d = tmp_path / "entities" / "interpretations"
    d.mkdir(parents=True)
    plan = plan_archive(tmp_path, selection=ArchiveStatusSweep(kind="all_by_status", statuses=["superseded"]),
                        now="2026-07-18T00:00:00Z")
    assert plan.moves == []
    # a new superseded entity appears after preview
    (d / "0001-x.md").write_text(
        "---\nid: interpretation:0001-x\nkind: interpretation\ntitle: X\nstatus: superseded\n---\nbody\n",
        encoding="utf-8")
    with pytest.raises(ArchiveApplyError, match="differ from the plan|corpus changed"):
        apply_archive_plan(tmp_path, plan, staging_token="tok")


def test_apply_archive_refuses_cross_device_move_loudly(tmp_path: Path, monkeypatch) -> None:
    # I8 / design §4.3: a cross-device rename raises EXDEV; apply must surface it as a clean refusal
    # (archive must be on the same filesystem), not a partial/ambiguous move.
    import errno
    import os
    _superseded(tmp_path)
    plan = plan_archive(tmp_path, selection=ArchiveStatusSweep(kind="all_by_status", statuses=["superseded"]),
                        now="2026-07-18T00:00:00Z")

    def exdev(src, dst):
        raise OSError(errno.EXDEV, "Invalid cross-device link")

    monkeypatch.setattr(os, "rename", exdev)
    with pytest.raises(ArchiveApplyError, match="cross-device"):
        apply_archive_plan(tmp_path, plan, staging_token="tok")
    # rolled back: the source is still in place, nothing half-moved
    assert (tmp_path / "entities" / "interpretations" / "0001-x.md").exists()


def test_apply_archive_refuses_when_source_changed_after_preview(tmp_path: Path) -> None:
    # design §9 (drift rejection — src changed): mutating the source after preview is refused (the
    # re-derived row/pre-state no longer matches the plan).
    _superseded(tmp_path)
    plan = plan_archive(tmp_path, selection=ArchiveStatusSweep(kind="all_by_status", statuses=["superseded"]),
                        now="2026-07-18T00:00:00Z")
    (tmp_path / "entities" / "interpretations" / "0001-x.md").write_text(
        "---\nid: interpretation:0001-x\nkind: interpretation\ntitle: CHANGED\nstatus: superseded\n---\nbody\n",
        encoding="utf-8")
    with pytest.raises(ArchiveApplyError):
        apply_archive_plan(tmp_path, plan, staging_token="tok")
    assert (tmp_path / "entities" / "interpretations" / "0001-x.md").exists()  # not moved


def test_apply_archive_refuses_project_root_mismatch(tmp_path: Path) -> None:
    # design §9 (drift rejection — project mismatch).
    _superseded(tmp_path)
    plan = plan_archive(tmp_path, selection=ArchiveStatusSweep(kind="all_by_status", statuses=["superseded"]),
                        now="2026-07-18T00:00:00Z")
    other = plan.model_copy(update={"project_root": str(tmp_path / "nope")})
    with pytest.raises(ArchiveApplyError, match="project_root"):
        apply_archive_plan(tmp_path, other, staging_token="tok")


def test_apply_archive_refuses_when_index_changed_after_preview(tmp_path: Path) -> None:
    # design §9 (drift rejection — INDEX changed), ISOLATED from created-dir drift: `_archive/` exists
    # BEFORE preview, so `plan_archive` emits no created-dir transition for it and the transition surface
    # is identical at preview and apply (`_archive/interpretations/` stays absent throughout — it is
    # never touched here). The ONLY thing that diverges afterward is the index file, so a failure is
    # specifically the index guard: re-derivation reads the new bytes and produces a different index
    # postimage/pre, and Gate B refuses rather than clobber a concurrently-written index. Source stays put.
    _superseded(tmp_path)
    (tmp_path / "entities" / "_archive").mkdir(parents=True)  # created-dir surface fixed BEFORE preview
    plan = plan_archive(tmp_path, selection=ArchiveStatusSweep(kind="all_by_status", statuses=["superseded"]),
                        now="2026-07-18T00:00:00Z")
    index_abs = tmp_path / "entities" / "_archive" / "archive-index.jsonl"
    index_abs.write_text('{"id":"interpretation:9999-z"}\n', encoding="utf-8")  # ONLY the index diverges
    with pytest.raises(ArchiveApplyError):
        apply_archive_plan(tmp_path, plan, staging_token="tok")
    assert (tmp_path / "entities" / "interpretations" / "0001-x.md").exists()  # not moved


def test_apply_archive_refuses_when_destination_appeared_after_preview(tmp_path: Path) -> None:
    # design §9 (drift rejection — DST appeared), ISOLATED from created-dir drift: the destination's
    # PARENT exists BEFORE preview, so `plan_archive` emits NO created-dir transitions (both `_archive/`
    # and `_archive/interpretations/` already exist) and the transition surface is identical at preview
    # and apply. The ONLY change afterward is the destination FILE appearing, so a failure is specifically
    # the dst guard: `plan_archive` freezes archive-dst with `pre=_ABSENT`, and the pre-state gate
    # (`matches(pre=absent, live=exists)` is False) refuses BEFORE any rename, leaving both untouched.
    _superseded(tmp_path)
    dst = tmp_path / "entities" / "_archive" / "interpretations" / "0001-x.md"
    dst.parent.mkdir(parents=True)  # created-dir surface fixed BEFORE preview
    plan = plan_archive(tmp_path, selection=ArchiveStatusSweep(kind="all_by_status", statuses=["superseded"]),
                        now="2026-07-18T00:00:00Z")
    dst.write_text("SOMETHING ALREADY HERE", encoding="utf-8")  # ONLY the destination file appears
    with pytest.raises(ArchiveApplyError):
        apply_archive_plan(tmp_path, plan, staging_token="tok")
    assert (tmp_path / "entities" / "interpretations" / "0001-x.md").exists()  # src not moved
    assert dst.read_text(encoding="utf-8") == "SOMETHING ALREADY HERE"          # dst untouched


def test_apply_archive_refuses_report_hiding_an_inbound_reference(tmp_path: Path) -> None:
    # I8 / design §9 "Report binding": a plan whose preview_report omits a live inbound reference to
    # an archived entity is refused at Gate B (the re-derived report carries the inbound ref).
    _superseded(tmp_path)
    # a live entity references the to-be-archived 0001-x
    (tmp_path / "entities" / "interpretations" / "0009-live.md").write_text(
        "---\nid: interpretation:0009-live\nkind: interpretation\ntitle: L\nstatus: active\n"
        "relations:\n  - predicate: sci:relatedTo\n    target: interpretation:0001-x\n---\nbody\n",
        encoding="utf-8")
    plan = plan_archive(tmp_path, selection=ArchiveStatusSweep(kind="all_by_status", statuses=["superseded"]),
                        now="2026-07-18T00:00:00Z")
    cand = plan.preview_report.candidates[0]
    assert "interpretation:0009-live" in cand.inbound_live_refs  # preview surfaced it
    hidden = cand.model_copy(update={"inbound_live_refs": []})
    tampered = plan.model_copy(update={
        "preview_report": plan.preview_report.model_copy(update={"candidates": [hidden]})})
    with pytest.raises(ArchiveApplyError, match="preview report"):
        apply_archive_plan(tmp_path, tampered, staging_token="tok")


def test_apply_archive_refuses_unsupported_schema_version(tmp_path: Path) -> None:
    _superseded(tmp_path)
    plan = plan_archive(tmp_path, selection=ArchiveStatusSweep(kind="all_by_status", statuses=["superseded"]),
                        now="2026-07-18T00:00:00Z")
    plan = plan.model_copy(update={"schema_version": 999})
    with pytest.raises(ArchiveApplyError):
        apply_archive_plan(tmp_path, plan, staging_token="tok")


def test_apply_archive_refuses_tampered_row(tmp_path: Path) -> None:
    _superseded(tmp_path)
    plan = plan_archive(tmp_path, selection=ArchiveStatusSweep(kind="all_by_status", statuses=["superseded"]),
                        now="2026-07-18T00:00:00Z")
    bad = plan.moves[0].row.model_copy(update={"title": "TAMPERED"})
    plan.moves[0] = plan.moves[0].model_copy(update={"row": bad})
    with pytest.raises(ArchiveApplyError):
        apply_archive_plan(tmp_path, plan, staging_token="tok")


def test_apply_archive_refuses_absolute_rel_path_escape(tmp_path: Path) -> None:
    _superseded(tmp_path)
    plan = plan_archive(tmp_path, selection=ArchiveStatusSweep(kind="all_by_status", statuses=["superseded"]),
                        now="2026-07-18T00:00:00Z")
    src = [t for t in plan.transitions if t.role == "archive-src"][0]
    idx = plan.transitions.index(src)
    plan.transitions[idx] = src.model_copy(update={"rel_path": "/etc/evil.md"})
    with pytest.raises(ArchiveApplyError):
        apply_archive_plan(tmp_path, plan, staging_token="tok")


def test_apply_archive_rolls_back_when_index_write_is_blocked(tmp_path: Path) -> None:
    # Move-rollback: a stale, non-prefix staging survivor makes the index write fail AFTER the entity
    # moved. The StagingError is wrapped as ArchiveApplyError only after rollback returns the corpus
    # to its pre-state — src restored, dst removed.
    _superseded(tmp_path)
    index_abs = tmp_path / "entities" / "_archive" / "archive-index.jsonl"
    index_abs.parent.mkdir(parents=True, exist_ok=True)  # so the parent exists before planning
    plan = plan_archive(tmp_path, selection=ArchiveStatusSweep(kind="all_by_status", statuses=["superseded"]),
                        now="2026-07-18T00:00:00Z")
    staging_path_for(index_abs, "tok").write_text("garbage-not-a-prefix", encoding="utf-8")
    with pytest.raises(ArchiveApplyError):
        apply_archive_plan(tmp_path, plan, staging_token="tok")
    assert (tmp_path / "entities" / "interpretations" / "0001-x.md").exists()  # src restored
    assert not (tmp_path / "entities" / "_archive" / "interpretations" / "0001-x.md").exists()  # dst gone


def test_kill_after_rename_leaves_a_classifiable_declared_state(tmp_path: Path) -> None:
    # Kill matrix — after each archive rename: src moved away, dst present, index NOT yet written.
    _superseded(tmp_path)
    plan = plan_archive(tmp_path, selection=ArchiveStatusSweep(kind="all_by_status", statuses=["superseded"]),
                        now="2026-07-18T00:00:00Z")

    def fault(label: str) -> None:
        if label == "renamed:interpretation:0001-x":
            raise _Kill()

    with pytest.raises(_Kill):
        apply_archive_plan(tmp_path, plan, staging_token="tok", _fault=fault)
    assert not (tmp_path / "entities" / "interpretations" / "0001-x.md").exists()
    assert (tmp_path / "entities" / "_archive" / "interpretations" / "0001-x.md").exists()
    assert not (tmp_path / "entities" / "_archive" / "archive-index.jsonl").exists()  # index == pre (absent)


def test_kill_after_index_replacement_leaves_complete_index_no_survivor(tmp_path: Path) -> None:
    # Kill matrix — after index replacement: index is complete, no staging survivor left behind.
    _superseded(tmp_path)
    plan = plan_archive(tmp_path, selection=ArchiveStatusSweep(kind="all_by_status", statuses=["superseded"]),
                        now="2026-07-18T00:00:00Z")

    def fault(label: str) -> None:
        if label == "index-written":
            raise _Kill()

    with pytest.raises(_Kill):
        apply_archive_plan(tmp_path, plan, staging_token="tok", _fault=fault)
    index_abs = tmp_path / "entities" / "_archive" / "archive-index.jsonl"
    assert index_abs.read_text(encoding="utf-8") == plan.index.postimage  # complete
    assert not staging_path_for(index_abs, "tok").exists()  # no undeclared debris


def test_apply_archive_index_leaves_no_staging_survivor(tmp_path: Path) -> None:
    _superseded(tmp_path)
    plan = plan_archive(tmp_path, selection=ArchiveStatusSweep(kind="all_by_status", statuses=["superseded"]),
                        now="2026-07-18T00:00:00Z")
    apply_archive_plan(tmp_path, plan, staging_token="tok")
    index_abs = tmp_path / "entities" / "_archive" / "archive-index.jsonl"
    assert not staging_path_for(index_abs, "tok").exists()
```

The full kill matrix (design §3.4) is now covered: **mid-staging** kill (a partial `.tmp` that is an attributable byte-prefix, target untouched) by Task 5's `test_staged_write_mid_kill_leaves_attributable_prefix_and_untouched_target` — exercising the real `staged_write` `_fault` seam, not just the `classify_staging` unit; **after each archive rename** and **after the index replacement** by this task's `_fault` boundaries below; and **after each entity write** by Task 12's post-write kill. Every boundary leaves only declared/attributable state.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --frozen pytest tests/test_archive_plan.py -q`
Expected: FAIL — `apply_archive_plan` missing.

- [ ] **Step 3: Write minimal implementation**

```python
# add to science/src/science_tool/archive_plan.py
import errno
import os
from typing import Callable

from science_tool.plan_common import (
    PathEscape, RollbackHalt, StagingError, SurfaceMismatch, assert_same_surface,
    assert_staging_unique, matches, resolve_within, rollback_transitions, snapshot_paths, staged_write,
)

_ARCHIVE_PLAN_SCHEMA = 1


class ArchiveApplyError(RuntimeError):
    pass


def apply_archive_plan(project_root: Path, plan: ArchivePlan, *, staging_token: str,
                       _fault: Callable[[str], None] | None = None) -> dict:
    def fault(label: str) -> None:
        if _fault is not None:
            _fault(label)  # a test may raise BaseException here to simulate a kill (no rollback)

    project_root = project_root.resolve()
    if plan.schema_version != _ARCHIVE_PLAN_SCHEMA:
        raise ArchiveApplyError(
            f"unsupported plan schema_version {plan.schema_version} (this tool writes {_ARCHIVE_PLAN_SCHEMA})")
    if plan.project_root != str(project_root):
        raise ArchiveApplyError("plan project_root does not match")

    # Gate B FIRST — re-derive the WHOLE plan from live sources and compare the complete surface.
    # Running this BEFORE the empty-cohort short-circuit means a corpus that gained an eligible entity
    # after preview is caught as drift, not silently reported as a successful no-op (I5). `plan_archive`
    # is read-only, and it derives its own paths from the live corpus, so it never touches an untrusted
    # plan path before containment is checked below.
    plan_index_list = [plan.index] if plan.index is not None else []
    expected = plan_archive(project_root, selection=plan.selection, now=plan.now)
    if expected.moves != plan.moves or expected.index != plan.index:
        raise ArchiveApplyError("re-derived moves/rows/index differ from the plan (corpus changed since preview)")
    exp_index = [expected.index] if expected.index is not None else []
    try:
        assert_same_surface([*plan.transitions, *plan_index_list], [*expected.transitions, *exp_index])
    except SurfaceMismatch as exc:
        raise ArchiveApplyError(f"declared transitions differ from re-derived: {exc}") from exc
    if expected.preview_report != plan.preview_report:
        raise ArchiveApplyError("re-derived preview report differs from the plan")

    # Empty cohort — a no-op plan writes nothing (legacy archive no-ops too). Only reachable once
    # Gate B has confirmed the live corpus ALSO derives an empty cohort.
    if not plan.moves:
        if plan.index is not None or plan.transitions:
            raise ArchiveApplyError("empty cohort must carry no index or transitions")
        return {"applied": [], "skipped": []}

    index_list = plan_index_list
    all_t = [*plan.transitions, *index_list]
    # Structural — containment for every declared path, canonical archive paths, staging uniqueness
    try:
        abs_by_t = {id(t): resolve_within(project_root, t.rel_path) for t in all_t}
        for m in plan.moves:
            resolve_within(project_root, m.original_path)
            resolve_within(project_root, m.archive_path)
        if plan.index is not None:
            assert_staging_unique(project_root, [abs_by_t[id(plan.index)]], staging_token)
    except (PathEscape, StagingError) as exc:
        raise ArchiveApplyError(str(exc)) from exc
    for m in plan.moves:
        if derive_archive_path(m.original_path) != m.archive_path:
            raise ArchiveApplyError(f"non-canonical archive_path for {m.id}")
    ids = [m.id for m in plan.moves]
    if len(ids) != len(set(ids)):
        raise ArchiveApplyError("duplicate move ids")

    # Pre-state gate
    for t in all_t:
        if not matches(t.pre, abs_by_t[id(t)]):
            raise ArchiveApplyError(f"pre-state changed for {t.rel_path}")

    snap = snapshot_paths([abs_by_t[id(t)] for t in all_t])
    try:
        for t in plan.transitions:
            if t.role == "created-dir":
                d = abs_by_t[id(t)]
                d.mkdir(parents=False, exist_ok=True)  # every ancestor is its own transition
                os.chmod(d, t.post.mode)
        for m in plan.moves:
            src = project_root / m.original_path
            dst = project_root / m.archive_path
            try:
                os.rename(src, dst)
            except OSError as exc:
                if exc.errno == errno.EXDEV:
                    raise ArchiveApplyError(
                        f"cross-device move refused for {m.id}: archive must be same filesystem") from exc
                raise
            _fsync_dir(src.parent)
            _fsync_dir(dst.parent)
            fault(f"renamed:{m.id}")  # kill boundary: after each rename, before the index write
        if plan.index is not None:
            staged_write(abs_by_t[id(plan.index)], plan.index.postimage,
                         plan.index.post.mode, staging_token,
                         target_pre=plan.index.pre)  # mode concrete; target_pre guards cleanup (§3.3)
            fault("index-written")  # kill boundary: after index replacement
        for t in all_t:
            if not matches(t.post, abs_by_t[id(t)]):
                raise ArchiveApplyError(f"post-state verification failed for {t.rel_path}")
    except Exception as exc:
        rollback_transitions(all_t, project_root, snap)  # may raise RollbackHalt (propagates)
        if isinstance(exc, ArchiveApplyError):
            raise
        raise ArchiveApplyError(f"archive apply failed and rolled back: {exc}") from exc
    return {"applied": [m.id for m in plan.moves], "skipped": []}


def _fsync_dir(directory: Path) -> None:
    fd = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
```

Rollback correctness: `all_t` is ordered created-dirs(outer→inner) → src → dst per move, then the optional index last; `rollback_transitions` processes it **reversed**, so it reverts the index, removes the moved `dst`, restores the `src` from its snapshot bytes, then `rmdir`s the created dirs innermost-first. A `_fault`-raised `BaseException` (simulated kill) is deliberately NOT caught by `except Exception`, so no rollback runs and the survivor is left classifiable.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --frozen pytest tests/test_archive_plan.py -q`
Expected: PASS (move+index, empty no-op, schema, tampered row, path escape, blocked-index rollback, kill-after-rename, kill-after-index, clean staging boundary).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/archive_plan.py science/tests/test_archive_plan.py
git commit -m "feat(archive): apply_archive_plan gate B + os.rename/os.replace execute"
```

---

## Phase 5 — CLI surface (`entities_inventory_cli.py`)

### Task 16: `entities mark-superseded` save-plan/apply-plan flags

**Files:**
- Modify: `science/src/science_tool/entities_inventory_cli.py:76-102`
- Test: `science/tests/test_supersede_plan_cli.py`

**Interfaces:**
- Consumes: `plan_supersede`, `apply_supersede_plan`, `plan_common.read_plan_bytes/verify_envelope/plan_sha256`.
- CLI: adds `--save-plan PATH`, `--overwrite-plan`, `--apply-plan PATH`, `--expected-plan-sha256 SHA`, `--staging-token TOKEN`. Preview writes the plan file + emits `{report, plan_sha256}`; apply-plan requires `--expected-plan-sha256`, rejects `--id/--ids-from/--save-plan/--overwrite-plan/--apply`.

- [ ] **Step 1: Write the failing test**

```python
# science/tests/test_supersede_plan_cli.py
from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from science_tool.cli import main


def _chain(root: Path) -> None:
    (root / "science.yaml").write_text("name: t\n", encoding="utf-8")
    d = root / "entities" / "interpretations"
    d.mkdir(parents=True)
    (d / "0001-a.md").write_text(
        "---\nid: interpretation:0001-a\nkind: interpretation\ntitle: A\nstatus: active\n"
        "relations:\n  - predicate: sci:supersedes\n    target: interpretation:0002-b\n---\nbody\n",
        encoding="utf-8")
    (d / "0002-b.md").write_text(
        "---\nid: interpretation:0002-b\nkind: interpretation\ntitle: B\nstatus: active\n---\nbody\n",
        encoding="utf-8")


def test_save_then_apply_plan(tmp_path: Path) -> None:
    _chain(tmp_path)
    plan_file = tmp_path / "plan.json"
    r1 = CliRunner().invoke(main, ["entities", "mark-superseded", "--project-root", str(tmp_path),
                                   "--save-plan", str(plan_file)])
    assert r1.exit_code == 0, r1.output
    sha = json.loads(r1.output)["plan_sha256"]
    assert plan_file.exists()
    r2 = CliRunner().invoke(main, ["entities", "mark-superseded", "--project-root", str(tmp_path),
                                   "--apply-plan", str(plan_file), "--expected-plan-sha256", sha])
    assert r2.exit_code == 0, r2.output
    assert "status: superseded" in (tmp_path / "entities" / "interpretations" / "0002-b.md").read_text()


def test_apply_plan_requires_envelope(tmp_path: Path) -> None:
    _chain(tmp_path)
    plan_file = tmp_path / "plan.json"
    CliRunner().invoke(main, ["entities", "mark-superseded", "--project-root", str(tmp_path),
                              "--save-plan", str(plan_file)])
    r = CliRunner().invoke(main, ["entities", "mark-superseded", "--project-root", str(tmp_path),
                                  "--apply-plan", str(plan_file)])
    assert r.exit_code != 0
    assert "expected-plan-sha256" in r.output


def test_apply_plan_rejects_edited_plan(tmp_path: Path) -> None:
    _chain(tmp_path)
    plan_file = tmp_path / "plan.json"
    r1 = CliRunner().invoke(main, ["entities", "mark-superseded", "--project-root", str(tmp_path),
                                   "--save-plan", str(plan_file)])
    sha = json.loads(r1.output)["plan_sha256"]
    plan_file.write_bytes(plan_file.read_bytes() + b" ")  # tamper one byte
    r = CliRunner().invoke(main, ["entities", "mark-superseded", "--project-root", str(tmp_path),
                                  "--apply-plan", str(plan_file), "--expected-plan-sha256", sha])
    assert r.exit_code != 0


def _two_chains(root: Path) -> None:
    # Two independent supersessions in one corpus — 0002-b and 0004-d are both markable.
    (root / "science.yaml").write_text("name: t\n", encoding="utf-8")
    d = root / "entities" / "interpretations"
    d.mkdir(parents=True)
    for sup, sub in (("0001-a", "0002-b"), ("0003-c", "0004-d")):
        (d / f"{sup}.md").write_text(
            f"---\nid: interpretation:{sup}\nkind: interpretation\ntitle: {sup}\nstatus: active\n"
            f"relations:\n  - predicate: sci:supersedes\n    target: interpretation:{sub}\n---\nbody\n",
            encoding="utf-8")
        (d / f"{sub}.md").write_text(
            f"---\nid: interpretation:{sub}\nkind: interpretation\ntitle: {sub}\nstatus: active\n---\nbody\n",
            encoding="utf-8")


def test_apply_plan_rejects_selection_swapped_to_broaden_the_cohort(tmp_path: Path) -> None:
    # I8 (selection authenticity, negative): editing the plan's `selection` to point at a different
    # eligible entity is a raw-byte change, so the approval envelope (digest over raw bytes, checked
    # before JSON parse) refuses it — a swapped selection cannot slip through. NOTE: the id-selection
    # flag is the repeatable `--id` (dest `ids`), not `--ids`.
    _two_chains(tmp_path)
    plan_file = tmp_path / "plan.json"
    r1 = CliRunner().invoke(main, ["entities", "mark-superseded", "--project-root", str(tmp_path),
                                   "--save-plan", str(plan_file), "--id", "interpretation:0002-b"])
    sha = json.loads(r1.output)["plan_sha256"]
    raw = plan_file.read_text(encoding="utf-8")
    plan_file.write_text(raw.replace("interpretation:0002-b", "interpretation:0004-d"), encoding="utf-8")
    r = CliRunner().invoke(main, ["entities", "mark-superseded", "--project-root", str(tmp_path),
                                  "--apply-plan", str(plan_file), "--expected-plan-sha256", sha])
    assert r.exit_code != 0  # digest mismatch (raw bytes changed)


def test_save_plan_rejects_apply_flag(tmp_path: Path) -> None:
    _chain(tmp_path)
    r = CliRunner().invoke(main, ["entities", "mark-superseded", "--project-root", str(tmp_path),
                                  "--save-plan", str(tmp_path / "p.json"), "--apply"])
    assert r.exit_code != 0
    assert "--apply" in r.output


def test_report_mode_rejects_staging_token(tmp_path: Path) -> None:
    _chain(tmp_path)
    r = CliRunner().invoke(main, ["entities", "mark-superseded", "--project-root", str(tmp_path),
                                  "--staging-token", "x"])
    assert r.exit_code != 0
    assert "--staging-token" in r.output


def test_apply_plan_reads_plan_file_exactly_once(tmp_path: Path, monkeypatch) -> None:
    # TOCTOU regression: the CLI must hash and parse the SAME single read, never reopen the path.
    import science_tool.plan_common as pc
    _chain(tmp_path)
    plan_file = tmp_path / "plan.json"
    r1 = CliRunner().invoke(main, ["entities", "mark-superseded", "--project-root", str(tmp_path),
                                   "--save-plan", str(plan_file)])
    sha = json.loads(r1.output)["plan_sha256"]

    calls = {"n": 0}
    real = pc.read_plan_bytes

    def counting(path):
        calls["n"] += 1
        return real(path)

    monkeypatch.setattr(pc, "read_plan_bytes", counting)
    r2 = CliRunner().invoke(main, ["entities", "mark-superseded", "--project-root", str(tmp_path),
                                   "--apply-plan", str(plan_file), "--expected-plan-sha256", sha])
    assert r2.exit_code == 0, r2.output
    assert calls["n"] == 1  # one read feeds BOTH the envelope hash and the parse
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --frozen pytest tests/test_supersede_plan_cli.py -q`
Expected: FAIL — unknown option `--save-plan`.

- [ ] **Step 3: Write minimal implementation**

Replace `entities_mark_superseded_command` (`entities_inventory_cli.py:76-102`) with the plan-aware version:

```python
@entities_group.command("mark-superseded")
@click.option("--project-root", type=click.Path(exists=True, file_okay=False, path_type=Path),
              default=Path("."), help="Project root (default: current directory).")
@click.option("--id", "ids", multiple=True, help="Restrict to this entity id (repeatable).")
@click.option("--ids-from", "ids_from", type=click.Path(exists=True, dir_okay=False, path_type=Path),
              default=None, help="File of entity ids, one per line; '#' comments and blanks ignored.")
@click.option("--apply", "apply_changes", is_flag=True, default=False, help="Apply changes (default: dry-run report).")
@click.option("--save-plan", type=click.Path(dir_okay=False, path_type=Path), default=None,
              help="Write the preview plan here, for a later --apply-plan. Refuses to overwrite.")
@click.option("--overwrite-plan", is_flag=True, default=False, help="Allow --save-plan to replace an existing file.")
@click.option("--apply-plan", "apply_plan_path", type=click.Path(exists=True, dir_okay=False, path_type=Path),
              default=None, help="Apply a plan saved by an earlier preview.")
@click.option("--expected-plan-sha256", default=None, help="Required with --apply-plan: SHA-256 of the raw plan bytes.")
@click.option("--staging-token", default=None,
              help="Batch token for staging paths. Omit for standalone use: a unique token is "
                   "generated and reported so two concurrent applies never collide.")
def entities_mark_superseded_command(project_root, ids, ids_from, apply_changes, save_plan,
                                     overwrite_plan, apply_plan_path, expected_plan_sha256, staging_token):
    """Auto-derive `superseded` status from linear supersedes chains (report / --save-plan / --apply-plan)."""
    import secrets
    from datetime import date

    from science_tool.consolidation import SupersessionError, mark_superseded
    from science_tool.plan_common import (
        AllSupersessionMembers, EnvelopeError, ExplicitSupersessionIds, plan_sha256,
        read_plan_bytes, verify_envelope,
    )
    from science_tool.supersede_plan import (
        SupersedeApplyError, SupersedePlan, apply_supersede_plan, plan_supersede,
    )

    if apply_plan_path is not None:
        for bad, name in [(ids, "--id"), (ids_from, "--ids-from"), (save_plan, "--save-plan"),
                          (overwrite_plan, "--overwrite-plan"), (apply_changes, "--apply")]:
            if bad:
                raise click.UsageError(f"{name} may not be combined with --apply-plan")
        if not expected_plan_sha256:
            raise click.UsageError("--apply-plan requires --expected-plan-sha256")
        raw = read_plan_bytes(apply_plan_path)
        try:
            verify_envelope(raw, expected_plan_sha256)
        except EnvelopeError as exc:
            raise click.ClickException(str(exc)) from exc
        plan = SupersedePlan.model_validate_json(raw)
        token = staging_token or secrets.token_hex(8)  # unique per standalone apply
        try:
            report = apply_supersede_plan(project_root.resolve(), plan, staging_token=token)
        except SupersedeApplyError as exc:
            raise click.ClickException(str(exc)) from exc
        emit(output_format="json", payload={**report, "staging_token": token},
             render_text=lambda: None)
        return

    allowlist = _collect_ids(ids, ids_from)
    if save_plan is not None:
        # --apply-plan-only flags are invalid while saving.
        for bad, name in [(apply_changes, "--apply"), (expected_plan_sha256, "--expected-plan-sha256"),
                          (staging_token, "--staging-token")]:
            if bad:
                raise click.UsageError(f"{name} may not be combined with --save-plan")
        selection = (ExplicitSupersessionIds(kind="explicit_ids", ids=sorted(allowlist))
                     if allowlist else AllSupersessionMembers(kind="all"))
        plan = plan_supersede(project_root.resolve(), selection=selection,
                              preview_date=date.today().isoformat())
        payload = plan.model_dump_json(indent=2).encode("utf-8")
        mode = "wb" if overwrite_plan else "xb"
        try:
            with open(save_plan, mode) as fh:
                fh.write(payload)
        except FileExistsError:
            raise click.UsageError(f"--save-plan target {save_plan} exists; pass --overwrite-plan") from None
        emit(output_format="json",
             payload={"report": plan.preview_report.model_dump(), "plan_sha256": plan_sha256(payload)},
             render_text=lambda: None)
        return

    # Plain report mode — flags that only make sense with a plan are rejected here.
    for bad, name in [(overwrite_plan, "--overwrite-plan"), (expected_plan_sha256, "--expected-plan-sha256"),
                      (staging_token, "--staging-token")]:
        if bad:
            raise click.UsageError(f"{name} requires --save-plan or --apply-plan")
    try:
        report = mark_superseded(project_root, ids=allowlist, apply=apply_changes)
    except SupersessionError as exc:
        raise click.ClickException(str(exc)) from exc
    emit(output_format="json", payload=report, render_text=lambda: None)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --frozen pytest tests/test_supersede_plan_cli.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/entities_inventory_cli.py science/tests/test_supersede_plan_cli.py
git commit -m "feat(cli): mark-superseded --save-plan/--apply-plan with mandatory envelope"
```

---

### Task 17: `entities archive` save-plan/apply-plan flags

**Files:**
- Modify: `science/src/science_tool/entities_inventory_cli.py:105-138`
- Test: `science/tests/test_archive_plan_cli.py`

**Interfaces:**
- Mirrors Task 16 for archive: preview builds `plan_archive` with `now = datetime.now(timezone.utc)...` frozen into the plan; apply calls `apply_archive_plan`; rejects `--status/--id/--ids-from/--save-plan/--overwrite-plan/--apply` under `--apply-plan`.

- [ ] **Step 1: Write the failing test**

```python
# science/tests/test_archive_plan_cli.py
from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from science_tool.cli import main


def _superseded(root: Path) -> None:
    (root / "science.yaml").write_text("name: t\n", encoding="utf-8")
    d = root / "entities" / "interpretations"
    d.mkdir(parents=True)
    (d / "0001-x.md").write_text(
        "---\nid: interpretation:0001-x\nkind: interpretation\ntitle: X\nstatus: superseded\n---\nbody\n",
        encoding="utf-8")


def test_archive_save_then_apply(tmp_path: Path) -> None:
    _superseded(tmp_path)
    plan_file = tmp_path / "plan.json"
    r1 = CliRunner().invoke(main, ["entities", "archive", "--project-root", str(tmp_path),
                                   "--save-plan", str(plan_file)])
    assert r1.exit_code == 0, r1.output
    sha = json.loads(r1.output)["plan_sha256"]
    assert (tmp_path / "entities" / "interpretations" / "0001-x.md").exists()  # dry run so far
    r2 = CliRunner().invoke(main, ["entities", "archive", "--project-root", str(tmp_path),
                                   "--apply-plan", str(plan_file), "--expected-plan-sha256", sha])
    assert r2.exit_code == 0, r2.output
    assert (tmp_path / "entities" / "_archive" / "interpretations" / "0001-x.md").exists()


def test_archive_apply_plan_rejects_status_flag(tmp_path: Path) -> None:
    _superseded(tmp_path)
    plan_file = tmp_path / "plan.json"
    CliRunner().invoke(main, ["entities", "archive", "--project-root", str(tmp_path), "--save-plan", str(plan_file)])
    r = CliRunner().invoke(main, ["entities", "archive", "--project-root", str(tmp_path),
                                  "--apply-plan", str(plan_file), "--expected-plan-sha256", "x", "--status", "superseded"])
    assert r.exit_code != 0
    assert "--status" in r.output
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --frozen pytest tests/test_archive_plan_cli.py -q`
Expected: FAIL — unknown option `--save-plan`.

- [ ] **Step 3: Write minimal implementation**

Replace `entities_archive_command` (`entities_inventory_cli.py:105-138`) mirroring Task 16, with archive selection + `now`:

```python
@entities_group.command("archive")
@click.option("--project-root", type=click.Path(exists=True, file_okay=False, path_type=Path),
              default=Path("."), help="Project root (default: current directory).")
@click.option("--status", "statuses", multiple=True, help="Statuses to archive (default: superseded, archived).")
@click.option("--id", "ids", multiple=True, help="Restrict to this entity id (repeatable).")
@click.option("--ids-from", "ids_from", type=click.Path(exists=True, dir_okay=False, path_type=Path),
              default=None, help="File of entity ids, one per line; '#' comments and blanks ignored.")
@click.option("--apply", "apply_changes", is_flag=True, default=False, help="Apply changes (default: dry-run report).")
@click.option("--save-plan", type=click.Path(dir_okay=False, path_type=Path), default=None,
              help="Write the preview plan here, for a later --apply-plan. Refuses to overwrite.")
@click.option("--overwrite-plan", is_flag=True, default=False, help="Allow --save-plan to replace an existing file.")
@click.option("--apply-plan", "apply_plan_path", type=click.Path(exists=True, dir_okay=False, path_type=Path),
              default=None, help="Apply a plan saved by an earlier preview.")
@click.option("--expected-plan-sha256", default=None, help="Required with --apply-plan: SHA-256 of the raw plan bytes.")
@click.option("--staging-token", default=None,
              help="Batch token for staging paths. Omit for standalone use: a unique token is "
                   "generated and reported so two concurrent applies never collide.")
def entities_archive_command(project_root, statuses, ids, ids_from, apply_changes, save_plan,
                             overwrite_plan, apply_plan_path, expected_plan_sha256, staging_token):
    """Relocate hidden-status entities into entities/_archive/ (report / --save-plan / --apply-plan)."""
    import secrets
    from datetime import datetime, timezone

    from science_tool.archive import DEFAULT_ARCHIVE_STATUSES, ArchiveError, archive_entities
    from science_tool.archive_plan import (
        ArchiveApplyError, ArchivePlan, apply_archive_plan, plan_archive,
    )
    from science_tool.plan_common import (
        ArchiveStatusSweep, EnvelopeError, ExplicitArchiveIds, plan_sha256, read_plan_bytes, verify_envelope,
    )

    if apply_plan_path is not None:
        for bad, name in [(statuses, "--status"), (ids, "--id"), (ids_from, "--ids-from"),
                          (save_plan, "--save-plan"), (overwrite_plan, "--overwrite-plan"),
                          (apply_changes, "--apply")]:
            if bad:
                raise click.UsageError(f"{name} may not be combined with --apply-plan")
        if not expected_plan_sha256:
            raise click.UsageError("--apply-plan requires --expected-plan-sha256")
        raw = read_plan_bytes(apply_plan_path)
        try:
            verify_envelope(raw, expected_plan_sha256)
        except EnvelopeError as exc:
            raise click.ClickException(str(exc)) from exc
        plan = ArchivePlan.model_validate_json(raw)
        token = staging_token or secrets.token_hex(8)  # unique per standalone apply
        try:
            report = apply_archive_plan(project_root.resolve(), plan, staging_token=token)
        except ArchiveApplyError as exc:
            raise click.ClickException(str(exc)) from exc
        emit(output_format="json", payload={**report, "staging_token": token},
             render_text=lambda: None)
        return

    status_set = frozenset(statuses) if statuses else DEFAULT_ARCHIVE_STATUSES
    allowlist = _collect_ids(ids, ids_from)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if save_plan is not None:
        for bad, name in [(apply_changes, "--apply"), (expected_plan_sha256, "--expected-plan-sha256"),
                          (staging_token, "--staging-token")]:
            if bad:
                raise click.UsageError(f"{name} may not be combined with --save-plan")
        selection = (ExplicitArchiveIds(kind="explicit_ids", ids=sorted(allowlist),
                                        allowed_statuses=sorted(status_set))
                     if allowlist else
                     ArchiveStatusSweep(kind="all_by_status", statuses=sorted(status_set)))
        try:
            plan = plan_archive(project_root.resolve(), selection=selection, now=now)
        except ArchiveError as exc:
            raise click.ClickException(str(exc)) from exc
        payload = plan.model_dump_json(indent=2).encode("utf-8")
        mode = "wb" if overwrite_plan else "xb"
        try:
            with open(save_plan, mode) as fh:
                fh.write(payload)
        except FileExistsError:
            raise click.UsageError(f"--save-plan target {save_plan} exists; pass --overwrite-plan") from None
        emit(output_format="json",
             payload={"report": plan.preview_report.model_dump(), "plan_sha256": plan_sha256(payload)},
             render_text=lambda: None)
        return

    # Plain report mode — plan-only flags are rejected here.
    for bad, name in [(overwrite_plan, "--overwrite-plan"), (expected_plan_sha256, "--expected-plan-sha256"),
                      (staging_token, "--staging-token")]:
        if bad:
            raise click.UsageError(f"{name} requires --save-plan or --apply-plan")
    try:
        report = archive_entities(project_root, statuses=status_set, ids=allowlist,
                                  apply=apply_changes, now=now)
    except ArchiveError as exc:
        raise click.ClickException(str(exc)) from exc
    emit(output_format="json", payload=report, render_text=lambda: None)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --frozen pytest tests/test_archive_plan_cli.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/entities_inventory_cli.py science/tests/test_archive_plan_cli.py
git commit -m "feat(cli): archive --save-plan/--apply-plan with mandatory envelope"
```

---

## Phase 6 — Release

### Task 18: 0.5.0 version bump

**Files:**
- Modify: `science/pyproject.toml:3`, `.claude-plugin/plugin.json:3`, `science/uv.lock` (records the editable `science` version at `:1827-1829`), `science/tests/test_cli_version.py:27`
- Test: `science/tests/test_cli_version.py`, `science/tests/test_agent_cli_compatibility.py` (unchanged)

- [ ] **Step 1: Update the baseline test to 0.5.0 (fails first)**

In `science/tests/test_cli_version.py`, change the baseline assertion (line ~27) and its test name:

```python
def test_package_and_plugin_establish_0_5_0_baseline() -> None:
    plugin = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    assert _package_version() == "0.5.0"
    assert plugin["version"] == "0.5.0"
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run --frozen pytest tests/test_cli_version.py -q`
Expected: FAIL — package version is still `0.4.1`.

- [ ] **Step 3: Bump both version strings**

`science/pyproject.toml:3`: `version = "0.5.0"`.
`.claude-plugin/plugin.json:3`: `"version": "0.5.0",`.

Then regenerate the lockfile so the recorded `science` package version tracks the bump — the
editable `science` project pins its own version in `science/uv.lock:1827-1829` (`name = "science"`,
`version = "0.4.1"`, `source = { editable = "." }`):

Run: `uv lock` (from `~/d/science/science`)
Expected: `science/uv.lock` now records `version = "0.5.0"` for the `science` package, and no other
entries change. Committing it here keeps `science/uv.lock` in sync with the bumped `pyproject.toml`, so
Task 19's `--frozen` `ruff`/`pyright` gates (which refuse to run against an out-of-sync lock) pass
instead of erroring on a stale lock.

- [ ] **Step 4: Run version + compatibility tests**

Run: `uv run --frozen pytest tests/test_cli_version.py tests/test_agent_cli_compatibility.py -q`
Expected: PASS — the baseline test now green, and `test_agent_cli_compatibility.py` (command floor ≤ version) passes **unchanged**.

- [ ] **Step 5: Record the observable behavior change, then commit**

The 0.5.0 release changes one observable behavior beyond the new flags: `mark-superseded`'s
secondary report lists (`archived_targets` / `unmanaged_targets` / `unbacked_inverses` /
`invalid_relations`) are now emitted in **canonical sorted order** instead of audit/scan order
(Task 9). Record this in the release notes / changelog the repo uses (if none exists, state it in
the commit body below). Blocking semantics are unchanged.

```bash
git add science/pyproject.toml .claude-plugin/plugin.json science/uv.lock science/tests/test_cli_version.py
git commit -m "release: science 0.5.0 — savable archive/mark-superseded plans

Behavior change: mark-superseded report lists (archived_targets/unmanaged_targets/
unbacked_inverses/invalid_relations) are now in canonical sorted order (was audit order);
blocking semantics unchanged."
```

---

### Task 19: Full-suite green + release commit

**Files:** none new — a gate.

- [ ] **Step 1: Run the whole suite**

Run: `uv run --frozen pytest tests -q`
Expected: PASS (no regressions across archive/consolidation/entity-import/version suites).

- [ ] **Step 2: Run lint and type gates** (AGENTS.md "Lint / types", from `~/d/science/science`)

Run: `uv run --frozen ruff check` then `uv run --frozen pyright`
Expected: both PASS (clean). `--frozen` (the lock is already in sync after Task 18's `uv lock`) means
these gates cannot mutate `science/uv.lock` behind your back. Fix any findings in the new/modified
files before committing.

- [ ] **Step 3: Run repo validation**

Run: `bash scripts/validate.sh --verbose` (from the repo root `~/d/science`)
Expected: PASS.

- [ ] **Step 4: Commit any lint/format fixups**

```bash
git add science/src/science_tool science/tests
git commit -m "chore: lint/format for 0.5.0 curation plans"
```

(Path-scoped, not `git add -A`: this repo is Dropbox-synced and the user commits unrelated work into it; stage only the package tree this plan touched.)

---

## Consumer-side delivery gate (natural-systems, tracked separately)

Not part of this upstream branch, but the acceptance the design §8 requires before Plan 2 can use the capability. Perform in the `natural-systems` repo after the upstream lands + pushes:

1. Update the `science` pin in `uv.lock` to the merged revision; `uv sync --frozen`.
2. Extend `scripts/__tests__/test_science_cli_surface.py` to assert `--save-plan`/`--apply-plan`/`--expected-plan-sha256`/`--staging-token` on both commands, on the pinned revision.
3. Run consumer integration tests; `uv run --frozen science validate --verbose`; `bash validate.sh --verbose`.

---

## Self-Review

**Spec coverage:** §1 three-layer authorization → Tasks 4 (envelope), 8/9 (material+digest, gate A), 12 & 15 (gate B by full re-derivation). §3.1 StateFingerprint (+ coherence validators) → Task 1. §3.2 PathTransition → Task 2. §3.3 snapshot/rollback/containment/surface validators → Task 6. §3.4 staging (fchmod-before-fsync) → Task 5. §3.5 selections → Task 3. §4 archive (incl. §4.x ancestor-complete created-dir set) → Tasks 13-15, 17. §5 supersede (incl. §5.4 injectable writer → Task 7, decision material as classifier **input** → Tasks 8-9) → Tasks 8-12, 16. §6 CLI (unique standalone staging token) → Tasks 16-17. §8 release → Task 18. §9 tests: kill-classification and move-rollback are now explicit failing-test steps in Task 15 (`test_apply_archive_rolls_back_when_index_write_is_blocked`, `test_apply_archive_index_leaves_no_staging_survivor`) and Task 5 (`classify_staging`); rollback of files/modes/symlinks/nested dirs in Task 6.

**Formerly-deferred items, now first-class acceptance criteria (no remaining "close during execution" gaps):**
- `post.mode` is the live file's actual mode, pinned by `test_plan_supersede_post_mode_matches_the_live_file` (Task 11) and `_fingerprint_of_text`'s `None`-mode guard; apply passes `w.post.mode` with no `or 0o644` fallback.
- Move rollback + kill-boundary are tested in Task 15, not left as a note.
- The single classifier (`_classify_from_projections`) is shared by both entry points, so equivalence is structural; `test_graph_from_material_equals_live_on_every_field` (Task 9) checks **every** field and `test_consolidation_mark_superseded.py` guards behavior. The one intentional change — report-list order becomes canonical/sorted — is documented in Task 9's behavior-preservation note.
- Decision material is built by `_project_inputs` from `SupersessionInputs`, never from the graph output; `test_build_decision_material_does_not_build_a_graph` (Task 8) enforces it.

**Second-review closures:**
- **Empty archive cohort is a no-op** (`index: PathTransition | None`; `plan_archive` emits `index=None`, `apply_archive_plan` writes nothing) — `test_plan_archive_empty_cohort_is_a_noop_plan` (Task 14), `test_apply_archive_empty_cohort_is_a_noop` (Task 15).
- **`resolve_within` is symlink-safe** — it `.resolve()`s the candidate and checks `is_relative_to`, matching `entity_import.py:486`; `test_resolve_within_rejects_ancestor_symlink_escape` (Task 6).
- **Kill-classification matrix** via a `_fault` seam that raises a `BaseException` (uncaught → no rollback): after each entity write (Task 12), after each archive rename and after index replacement (Task 15); mid-staging prefix via `classify_staging` (Task 5). Rollback fallback for a missing snapshot is now a `RollbackHalt`, not an empty-file reconstruction.
- **Disposition derived from the material-derived graph** through a shared `_disposition_report(graph, *, ids)`; preview and gate B no longer re-load the filesystem — `test_disposition_report_from_material_matches_mark_superseded` (Task 9).
- **Execute errors are wrapped** as `SupersedeApplyError`/`ArchiveApplyError` only *after* successful rollback, with `RollbackHalt` propagated distinctly (Tasks 12, 15); the blocked-index test now correctly expects the wrapped type.
- **`schema_version` is enforced** against the supported constant in both apply paths (Tasks 12, 15).
- **CLI mode contracts** — `--save-plan` rejects `--apply`/envelope/staging-token; report mode rejects plan-only flags (Tasks 16, 17). **Single-read TOCTOU** pinned by `test_apply_plan_reads_plan_file_exactly_once` (Task 16).
- **Ordering ratified** with a pinned multi-item canonical-order test (Task 9) and recorded as an observable 0.5.0 behavior change (Task 18); wording corrected — `invalid`/`unbacked_inverses` are reported **and blocking**.

**Third-review closures:**
- **Command working directory (C1)** — `uv`/`pytest` run from `~/d/science/science` (reproduced: root fails with `ModuleNotFoundError: science_model` via `conftest`); pytest paths are package-relative; `git`/validator run from the repo root; validator is `bash scripts/validate.sh`. Global Constraints §"Command working directories".
- **Gate B derives from the verified material (C2)** — `derive_supersede_plan(project_root, material, …)` is called by preview (after one load) and by apply's Gate B (reusing the Gate-A material), so `build_decision_material` runs exactly once per apply — `test_apply_supersede_loads_decision_material_once` (Task 12).
- **Mid-staging kill (C3)** — a `_fault("mid-write")` seam inside the real `staged_write`; `test_staged_write_mid_kill_leaves_attributable_prefix_and_untouched_target` (Task 5) asserts the survivor is an attributable byte-prefix, the target is untouched, and no debris remains. The `except` cleanup now removes only an attributable-prefix survivor (not an unconditional `unlink`).
- **`supported_kinds` in the material (I4)** — the auto-apply policy is serialized into `SupersessionDecisionMaterial`, travels on `SupersedesGraph`, and is read by `_disposition_report`; the digest covers it — `test_material_carries_supported_kinds_and_digest_covers_the_policy`, `test_disposition_reads_supported_kinds_from_the_graph_not_the_module` (Tasks 8-9).
- **Empty archive apply runs Gate B first (I5)** — the no-op return is reachable only after re-derivation confirms an empty cohort; a corpus that gained an eligible entity is refused as drift — `test_apply_empty_cohort_refuses_when_corpus_gained_an_eligible_entity` (Task 15). `ArchivePlan._index_matches_moves` makes moves↔index a schema invariant; design §4.1 updated.
- **Write-boundary retention (I6)** — `test_all_three_boundary_checks_run_in_order` (Task 7) proves the schema-gate, prospective-corpus, and successor-resolution checks all survive the extraction, in order; the dangling-successor test still exercises the resolution boundary end-to-end.
- **Report-list order pinned (I7)** — `_disposition_report` now actually sorts the four secondary lists; `test_disposition_report_sorts_the_four_secondary_lists_regardless_of_graph_order` (Task 9) feeds a graph in reverse-of-canonical order, so removing the sort fails.
- **Ratified §9 acceptance cases (I8)** now explicit TDD steps: explicit-selection replay (`test_apply_explicit_ids_subset_marks_only_that_subset`, Task 12) and authenticity (`test_apply_plan_rejects_selection_swapped_to_broaden_the_cohort`, Task 16); archive inbound-report tampering (`test_apply_archive_refuses_report_hiding_an_inbound_reference`, Task 15); `EXDEV` (`test_apply_archive_refuses_cross_device_move_loudly`, Task 15); `material_version` mismatch (`test_apply_refuses_material_version_mismatch`, Task 12); rollback after the first of two entity writes (`test_rollback_after_first_of_two_entity_writes_restores_surface`, Task 12); leading-newline/CRLF normalization across writer paths (`test_body_normalization_is_identical_across_writer_paths`, Task 7).
- **Path-scoped final staging (minor)** — Task 19 stages `science/src/science_tool science/tests`, not `git add -A`.

**Fourth-review closures:**
- **Mid-write test proves a real partial (C1)** — `staged_write`'s seam writes a STRICT prefix (flush+fsync) then faults; `test_staged_write_mid_kill_…` asserts `0 < len(survivor) < len(postimage)` and `classify_staging == "prefix"`. Cleanup is attribution-aware: `test_staged_write_refuses_to_remove_a_non_prefix_survivor` (target untouched, survivor preserved) + the clean-prefix removal test.
- **Task 13 round-trip is a valid empty plan (C2)** — `moves=[], index=None, transitions=[]`; the incoherent shapes have their own `test_archive_plan_rejects_incoherent_moves_index_shapes`.
- **Unexecutable tests fixed (C3)** — `ExplicitSupersessionIds` imported in `test_supersede_plan.py`; archive EXDEV test imports `os`; the CLI selection test seeds inline (`_two_chains`) and uses the real repeatable `--id` flag (not `--ids`); the three combined pytest commands now use package-relative second paths.
- **Boundary + normalization cover the real routes (I4)** — `test_each_boundary_check_is_load_bearing_in_both_prepare_routes` forces each of the three checks to raise through both `_prepare_write_with_date` and legacy `_prepare_write`; `test_crlf_body_normalized_identically_across_preview_applyplan_and_legacy` compares preview → apply-plan → `mark_superseded` end-to-end.
- **Implementation import + `_all_fields` (I5)** — `SupersessionDecisionMaterial` imported into `supersede_plan.py`; `_all_fields` now includes `supported_kinds`; Task 19 runs `uv run ruff check` and `uv run pyright` (AGENTS.md).
- **Ratified §9 cases added (I6)** — present-but-empty `updated` (render preservation), duplicate-relation count (no collapsing), non-projected-field digest stability, archive source-drift + project-root mismatch, and a supersession report hiding a blocker are now explicit tests (Tasks 7, 8, 12, 15).
- **Interface prose (minor)** — Task 13's `ArchivePlan` interface line now reads `index: PathTransition | None = None` with the `_index_matches_moves` validator noted.

**Fifth-review closures:**
- **Staging cleanup checks target attribution, not just the prefix (Critical)** — `staged_write` now takes `target_pre`; cleanup removes a survivor only when it is an attributable byte-prefix AND the live target still matches `target_pre` (design §3.3), else it preserves the survivor and halts. Both apply call sites pass the frozen pre (`w.pre` / `plan.index.pre`); `test_staged_write_halts_when_target_changed_concurrently` drives a concurrent target change through `os.replace` and asserts the survivor is preserved.
- **Corpus-drift test split to honor the digest contract (blocker)** — the old test mutated only `title` (non-projected) yet expected refusal, contradicting `test_non_projected_field_change_does_not_move_the_digest`. Replaced by `test_apply_refuses_on_decision_drift` (removes 0001-a's supersedes relation → disposition drift, member untouched) and `test_apply_refuses_on_write_source_drift` (edits 0002-b's title → write-source pre-fingerprint drift, digest unchanged).
- **`import pytest` added to the injectable-writer test module (blocker)** — module-level `import pytest`; the redundant function-local import removed.
- **Archive index/dst drift tests added (blocker)** — `test_apply_archive_refuses_when_index_changed_after_preview` and `test_apply_archive_refuses_when_destination_appeared_after_preview` complete design §514's drift matrix alongside the existing src-changed and project-mismatch cases.
- **0.5.0 bump regenerates and commits `science/uv.lock` (blocker)** — Task 18 runs `uv lock` after the version edit and stages `science/uv.lock`; Task 19's lint/type gates run `--frozen` so they cannot mutate the lock.
- **Exact-mode rollback (minor)** — `_materialize` uses `fp.mode` directly (with a `None`-narrowing assert) instead of `fp.mode or 0o644/0o755`, which corrupted mode `0o000`.

**Sixth-review closures:**
- **`target_pre` is mandatory keyword-only (functional)** — `staged_write(..., *, target_pre: StateFingerprint, _fault=None)`: the optional default let several Task 5 tests fall back to prefix-only cleanup. All five omitting calls now pass `target_pre=fingerprint(target)`, and the cleanup drops its `is not None` guard so every path enforces target attribution.
- **Archive drift tests de-confounded from directory drift (functional)** — both new tests created `_archive` dirs after preview, so Gate B could reject on the created-directory surface rather than the guard under test. The index test now pre-creates `_archive/` (leaving `_archive/interpretations/` absent); the destination test pre-creates the destination parent — so each fails specifically when its index/dst guard is removed.
- **Gate attribution corrected in test comments (wording)** — the decision-drift (relation removed) test is caught by Gate A's decision-digest mismatch before Gate B; the write-source (title edited) test is caught by Gate B's `assert_same_surface` before the later pre-state gate. Comments now name the gate that actually fires first.
- **Task 18 prose (wording)** — no longer calls Task 19's lint "non-frozen"; it explains that committing the synced lock lets Task 19's `--frozen` gates run instead of erroring on a stale lock.

**Type consistency:** `StateFingerprint`/`PathTransition`/`PathSnapshot`, `resolve_within`/`assert_same_surface`/`assert_staging_unique`, `ArchiveSelection`/`SupersedeSelection`, the nested report models (`SupersededChainReport`/`InvalidRelation`/`TargetReport`/… and `ArchiveCandidate`/`PlannedArchiveRow`), `plan_supersede`/`apply_supersede_plan`, `plan_archive`/`apply_archive_plan`, `_prepare_write_with_date`, `_project_inputs`/`_classify_from_projections`/`build_supersedes_graph_from_material`, `build_decision_material`/`decision_digest` are used consistently across tasks.

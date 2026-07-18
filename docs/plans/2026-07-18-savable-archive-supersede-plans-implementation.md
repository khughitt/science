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
- **Staged replacement uses `os.replace`**; `os.rename` is reserved for archive src→absent-dst moves and refuses `EXDEV` loudly (design §3.4, §4.3). New files/dirs are `fchmod`/`chmod`'d to the saved `mode` (umask-independent).
- **Staging path is derived, never trusted from JSON:** `<rel_path>.<staging-token>.tmp`, sibling, contained, unique, created with `O_EXCL` (design §3.2, §3.4).
- **The write path keeps `_parse_markdown_file`'s existing normalization** (lstrip leading newlines + line-ending normalization). Only the `updated` default becomes injectable via `preview_date`. Do NOT switch to a body-preserving parser (design §5.4). No "body round-trips byte-for-byte" claim — gate B compares against the **normalized** postimage the legacy writer produces.
- **The shared preparation function retains all three `_prepare_write` boundary checks:** `_schema_gate_or_raise` (`entities.py:1072`), `_validate_prospective_write` (`entities.py:1075`), `_resolution_check_or_raise` (`entities.py:1083`). Preview, legacy `--apply`, and `--apply-plan` all route through it.
- **The plan stores a `preview_report` (dry-run semantics), not an execution report.** `applied`/`repaired`/`skipped` are populated only after execution; apply emits a **separate** execution report (design §4.4, §5.5).
- **Selection lists** (ids/statuses) are enforced non-empty, unique, canonically ordered by **model validators**, not comments (design §3.5).
- **Version bump = three edits + one unchanged test** (design §8): `science/pyproject.toml:3`, `.claude-plugin/plugin.json:3`, `science/tests/test_cli_version.py:27`; `test_agent_cli_compatibility.py` runs unchanged.
- **House style:** `from __future__ import annotations`; absolute imports; tests use `CliRunner` + `tmp_path` + inline `science.yaml`/entity fixtures. Run tests with `uv run --frozen pytest science/tests/<file> -q` from `~/d/science`. No AI-attribution trailers in commits.

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
- Produces: `StateFingerprint` (pydantic, fields `existed: bool`, `type: Literal["file","dir","symlink"] | None`, `content_sha256: str | None`, `mode: int | None`, `symlink_target: str | None`); `fingerprint(path: Path) -> StateFingerprint`; `matches(fp: StateFingerprint, path: Path) -> bool`.

- [ ] **Step 1: Write the failing test**

```python
# science/tests/test_plan_common.py
from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

from science_tool.plan_common import StateFingerprint, fingerprint, matches


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --frozen pytest science/tests/test_plan_common.py -q`
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

from pydantic import BaseModel, ConfigDict


class StateFingerprint(BaseModel):
    model_config = ConfigDict(extra="forbid")
    existed: bool
    type: Literal["file", "dir", "symlink"] | None
    content_sha256: str | None
    mode: int | None
    symlink_target: str | None


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
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    return StateFingerprint(existed=True, type="file", content_sha256=sha,
                            mode=mode, symlink_target=None)


def matches(fp: StateFingerprint, path: Path) -> bool:
    return fingerprint(path) == fp
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --frozen pytest science/tests/test_plan_common.py -q`
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

Run: `uv run --frozen pytest science/tests/test_plan_common.py -q`
Expected: FAIL — `ImportError: cannot import name 'PathTransition'`.

- [ ] **Step 3: Write minimal implementation**

```python
# add to science/src/science_tool/plan_common.py
import hashlib
from pydantic import model_validator

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

Run: `uv run --frozen pytest science/tests/test_plan_common.py -q`
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

Run: `uv run --frozen pytest science/tests/test_plan_common.py -q`
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

Run: `uv run --frozen pytest science/tests/test_plan_common.py -q`
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

Run: `uv run --frozen pytest science/tests/test_plan_common.py -q`
Expected: FAIL — import error.

- [ ] **Step 3: Write minimal implementation**

```python
# add to science/src/science_tool/plan_common.py
class EnvelopeError(RuntimeError):
    pass


def read_plan_bytes(path: Path) -> bytes:
    """Read the plan file EXACTLY once; callers hash and parse this same buffer."""
    return path.read_bytes()


def plan_sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def verify_envelope(raw: bytes, expected_sha256: str) -> None:
    actual = plan_sha256(raw)
    if not hashlib.compare_digest(actual, expected_sha256):
        raise EnvelopeError(
            "plan bytes do not match --expected-plan-sha256 (approval envelope); "
            "the saved plan was not the one approved"
        )
```

Note: `hashlib.compare_digest` is an alias of `hmac.compare_digest`; if the linter objects, `import hmac` and use `hmac.compare_digest`.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --frozen pytest science/tests/test_plan_common.py -q`
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
- Produces: `staging_path_for(target: Path, token: str) -> Path` (`<target>.<token>.tmp`); `staged_write(target: Path, postimage: str, mode: int, token: str) -> None` (O_EXCL tmp → write → fchmod → fsync → `os.replace`); `classify_staging(staging: Path, postimage: str) -> Literal["absent","prefix","complete"]`. `StagingError(RuntimeError)`.

- [ ] **Step 1: Write the failing test**

```python
# append to science/tests/test_plan_common.py
from science_tool.plan_common import StagingError, classify_staging, staged_write, staging_path_for


def test_staged_write_replaces_atomically_with_mode(tmp_path: Path) -> None:
    target = tmp_path / "entities" / "x" / "1.md"
    target.parent.mkdir(parents=True)
    target.write_text("old", encoding="utf-8")
    staged_write(target, "new-bytes", 0o644, token="batch1")
    assert target.read_text(encoding="utf-8") == "new-bytes"
    assert (os.stat(target).st_mode & 0o777) == 0o644
    assert not staging_path_for(target, "batch1").exists()  # tmp consumed


def test_staged_write_refuses_preexisting_staging_file(tmp_path: Path) -> None:
    target = tmp_path / "a.md"
    target.write_text("x", encoding="utf-8")
    staging_path_for(target, "batch1").write_text("stale", encoding="utf-8")
    with pytest.raises(StagingError):
        staged_write(target, "y", 0o644, token="batch1")


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --frozen pytest science/tests/test_plan_common.py -q`
Expected: FAIL — import error.

- [ ] **Step 3: Write minimal implementation**

```python
# add to science/src/science_tool/plan_common.py
class StagingError(RuntimeError):
    pass


def staging_path_for(target: Path, token: str) -> Path:
    return target.with_name(f"{target.name}.{token}.tmp")


def staged_write(target: Path, postimage: str, mode: int, token: str) -> None:
    staging = staging_path_for(target, token)
    data = postimage.encode("utf-8")
    try:
        fd = os.open(staging, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    except FileExistsError as exc:
        raise StagingError(f"staging path already exists: {staging}") from exc
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.chmod(staging, mode)  # O_EXCL mode is umask-masked; force exact bits
        os.replace(staging, target)
        dir_fd = os.open(target.parent, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except Exception:
        if staging.exists():
            staging.unlink()
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

Run: `uv run --frozen pytest science/tests/test_plan_common.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/plan_common.py science/tests/test_plan_common.py
git commit -m "feat(curation): staged-write (O_EXCL/fchmod/os.replace) + prefix classifier"
```

---

### Task 6: Snapshot + ownership-scoped rollback

**Files:**
- Modify: `science/src/science_tool/plan_common.py`
- Test: `science/tests/test_plan_common.py`

**Interfaces:**
- Produces: `snapshot_paths(paths: list[Path]) -> dict[Path, bytes | None]` (bytes, or None if absent); `rollback_transitions(transitions: list[PathTransition], project_root: Path, snapshot: dict[Path, bytes | None]) -> None`. Rollback reverts a path only if live matches its `post`; skips if it matches `pre`; raises `RollbackHalt` otherwise. `RollbackHalt(RuntimeError)`.

- [ ] **Step 1: Write the failing test**

```python
# append to science/tests/test_plan_common.py
from science_tool.plan_common import RollbackHalt, rollback_transitions, snapshot_paths


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --frozen pytest science/tests/test_plan_common.py -q`
Expected: FAIL — import error.

- [ ] **Step 3: Write minimal implementation**

```python
# add to science/src/science_tool/plan_common.py
class RollbackHalt(RuntimeError):
    pass


def snapshot_paths(paths: list[Path]) -> dict[Path, bytes | None]:
    snap: dict[Path, bytes | None] = {}
    for p in paths:
        snap[p] = p.read_bytes() if p.exists() and not p.is_dir() else None
    return snap


def rollback_transitions(
    transitions: list[PathTransition], project_root: Path, snapshot: dict[Path, bytes | None]
) -> None:
    for t in transitions:
        path = project_root / t.rel_path
        if matches(t.pre, path):
            continue  # never got written, or already reverted
        if not matches(t.post, path):
            raise RollbackHalt(
                f"live state of {t.rel_path} matches neither pre nor post; "
                "a concurrent change occurred — refusing to clobber"
            )
        saved = snapshot.get(path)
        if saved is None:
            path.unlink(missing_ok=True)
        else:
            path.write_bytes(saved)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --frozen pytest science/tests/test_plan_common.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/plan_common.py science/tests/test_plan_common.py
git commit -m "feat(curation): ownership-scoped rollback with halt-on-concurrent-change"
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --frozen pytest science/tests/test_prepare_write_injectable.py -q`
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

Run: `uv run --frozen pytest science/tests/test_prepare_write_injectable.py science/tests/test_consolidation_mark_superseded.py -q`
Expected: PASS (new tests + all existing mark-superseded tests still green — behavior unchanged on the legacy path).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/entities.py science/src/science_tool/consolidation.py science/tests/test_prepare_write_injectable.py
git commit -m "refactor(entities): injectable updated default via _prepare_write_with_date"
```

---

## Phase 2 — Supersession decision material (`consolidation.py`)

### Task 8: `SupersessionDecisionMaterial` + `build_decision_material` + `decision_digest`

**Files:**
- Modify: `science/src/science_tool/consolidation.py`
- Test: `science/tests/test_decision_material.py`

**Interfaces:**
- Produces: `SupersessionDecisionMaterial` (pydantic, `extra="forbid"`, `material_version: int`, plus serialized projections of `SupersessionInputs` — entries as `list[tuple[str, str]]` of `(posix_path, canonical_json_of_frontmatter)`, and a stable serialization of `resolution`/`audit` sufficient to rebuild the graph); `build_decision_material(project_root) -> SupersessionDecisionMaterial`; `decision_digest(material) -> str`.
- Design note (§5.2): the material must be what `build_supersedes_graph` consumes (Task 9 wires that). For this task, capture entries + the admitted supersedes edges + statuses/kinds + archived/mutable populations + invalid defects — everything `build_supersedes_graph` reads off `SupersessionInputs`. Serialize deterministically (sorted, duplicates preserved).

- [ ] **Step 1: Write the failing test**

```python
# science/tests/test_decision_material.py
from __future__ import annotations

from pathlib import Path

import yaml

from science_tool.consolidation import build_decision_material, decision_digest


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
        "---\nid: interpretation:0002-b\nkind: interpretation\ntitle: B\nstatus: active\n---\nbody\n",
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --frozen pytest science/tests/test_decision_material.py -q`
Expected: FAIL — import error.

- [ ] **Step 3: Write minimal implementation**

```python
# add to science/src/science_tool/consolidation.py
import hashlib
import json
from pydantic import BaseModel, ConfigDict

_MATERIAL_VERSION = 1


class SupersessionDecisionMaterial(BaseModel):
    model_config = ConfigDict(extra="forbid")
    material_version: int
    entries: list[tuple[str, str]]        # (posix_path, canonical_json(frontmatter)), sorted
    admitted_supersedes: list[tuple[str, str]]  # (superseder, superseded) canonical, sorted, dups kept
    status_by_id: list[tuple[str, str]]   # (canonical_id, status_or_""), sorted
    kind_by_id: list[tuple[str, str]]     # (canonical_id, kind), sorted
    mutable_population: list[str]         # sorted
    archived_population: list[str]        # sorted
    invalid: list[str]                    # defect messages, sorted


def build_decision_material(project_root: Path) -> SupersessionDecisionMaterial:
    inputs = load_supersession_inputs(project_root)
    resolution = inputs.resolution
    graph = build_supersedes_graph(inputs)
    entries = sorted(
        (path.relative_to(project_root).as_posix(), json.dumps(fm, sort_keys=True, default=str))
        for path, fm in inputs.entries
    )
    admitted = sorted(list(graph.edges))
    return SupersessionDecisionMaterial(
        material_version=_MATERIAL_VERSION,
        entries=entries,
        admitted_supersedes=[(a, b) for a, b in admitted],
        status_by_id=sorted((k, v or "") for k, v in graph.status_by_id.items()),
        kind_by_id=sorted(graph.kind_by_id.items()),
        mutable_population=sorted(resolution.mutable),
        archived_population=sorted(resolution.archived),
        invalid=sorted(d.message for d in graph.invalid),
    )


def decision_digest(material: SupersessionDecisionMaterial) -> str:
    return hashlib.sha256(
        material.model_dump_json().encode("utf-8")
    ).hexdigest()
```

Note for the implementer: `resolution.mutable`/`.archived` and `graph.edges`/`.status_by_id`/`.kind_by_id`/`.invalid` are all real attributes (see `IdResolution` `consolidation.py:116` and `SupersedesGraph` `consolidation.py:290`). This material is intentionally a superset of the graph inputs; Task 9 makes `build_supersedes_graph` able to consume it so the digest surface and the derivation surface are provably the same.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --frozen pytest science/tests/test_decision_material.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/consolidation.py science/tests/test_decision_material.py
git commit -m "feat(supersede): serializable SupersessionDecisionMaterial + decision_digest"
```

---

### Task 9: `build_supersedes_graph` consumes the material (equivalence-preserving)

**Files:**
- Modify: `science/src/science_tool/consolidation.py`
- Test: `science/tests/test_decision_material.py`

**Interfaces:**
- Produces: `build_supersedes_graph_from_material(material: SupersessionDecisionMaterial) -> SupersedesGraph`, deriving the same `SupersedesGraph` fields the existing `build_supersedes_graph(inputs)` produces for the linear/non-linear/disposition data `mark_superseded` reads. Existing `build_supersedes_graph(inputs)` stays (Task 8 uses it to build the material); this task proves a material round-trips to the same disposition.

**Design intent:** gate B (Task 13) re-derives the disposition from the *material*, not from live `SupersessionInputs`. This task provides that pure function and pins its equivalence to the live derivation.

- [ ] **Step 1: Write the failing test**

```python
# append to science/tests/test_decision_material.py
from science_tool.consolidation import (
    build_decision_material, build_supersedes_graph, build_supersedes_graph_from_material,
    load_supersession_inputs,
)


def test_graph_from_material_matches_live_disposition(tmp_path: Path) -> None:
    _seed(tmp_path)
    live = build_supersedes_graph(load_supersession_inputs(tmp_path))
    mat = build_supersedes_graph_from_material(build_decision_material(tmp_path))
    live_chains = [(c.survivor, c.superseded) for c in live.linear]
    mat_chains = [(c.survivor, c.superseded) for c in mat.linear]
    assert live_chains == mat_chains
    assert dict(live.superseder_by_id) == dict(mat.superseder_by_id)
    assert sorted(live.edges) == sorted(mat.edges)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --frozen pytest science/tests/test_decision_material.py -q`
Expected: FAIL — `ImportError: cannot import name 'build_supersedes_graph_from_material'`.

- [ ] **Step 3: Write minimal implementation**

The cleanest equivalence-preserving move is to refactor the *topology* half of `build_supersedes_graph` into a helper that operates on the plain projections the material carries (edges, status_by_id, kind_by_id, populations, invalid), and have both entry points call it. Add:

```python
# add to science/src/science_tool/consolidation.py
def build_supersedes_graph_from_material(
    material: SupersessionDecisionMaterial,
) -> SupersedesGraph:
    """Rebuild the disposition from the frozen material — the pure projection
    `build_supersedes_graph` computes, minus any filesystem read. Used by
    apply-plan gate B so the digest surface IS the derivation surface."""
    edges = frozenset((a, b) for a, b in material.admitted_supersedes)
    status_by_id = {k: (v or None) for k, v in material.status_by_id}
    kind_by_id = dict(material.kind_by_id)
    return _classify_supersedes_topology(
        edges=edges,
        status_by_id=status_by_id,
        kind_by_id=kind_by_id,
        mutable=frozenset(material.mutable_population),
        archived=frozenset(material.archived_population),
        invalid_messages=tuple(material.invalid),
    )
```

Then extract `_classify_supersedes_topology(...)` from the existing `build_supersedes_graph` body (`consolidation.py:352-490`) — the part after it has read `entries`/`resolution`/`audit` into `edges`/`status_by_id`/`kind_by_id`/populations/invalid — and have `build_supersedes_graph(inputs)` call it too. This keeps ONE topology classifier. The extraction must preserve the exact `SupersedesGraph` fields the existing tests assert; run `test_consolidation_mark_superseded.py` to prove it.

Implementer note: if the existing `build_supersedes_graph` builds `path_by_id` (live-only, `SupersedesGraph.path_by_id`), the material path cannot populate it (paths are not decision-bearing for the disposition). Have `build_supersedes_graph_from_material` pass `path_by_id={}`; gate B never reads `path_by_id` (it uses each write's `rel_path`), so this is safe. Assert that in the test if practical.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --frozen pytest science/tests/test_decision_material.py science/tests/test_consolidation_mark_superseded.py -q`
Expected: PASS (equivalence test + all existing mark-superseded tests — the topology extraction changed no behavior).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/consolidation.py science/tests/test_decision_material.py
git commit -m "refactor(supersede): shared topology classifier; graph-from-material"
```

---

## Phase 3 — Supersede plan (`supersede_plan.py`)

### Task 10: `SupersedePreviewReport` + `SupersedePlan` schemas

**Files:**
- Create: `science/src/science_tool/supersede_plan.py`
- Test: `science/tests/test_supersede_plan.py`

**Interfaces:**
- Produces: `SupersedePreviewReport` (pydantic, `extra="forbid"`) mirroring the dry-run keys `mark_superseded` returns — `chains`, `non_linear`, `to_mark`, `skipped_kinds`, `to_repair`, `invalid_relations`, `archived_targets`, `unmanaged_targets`, `unbacked_inverses` (NOT `applied`/`repaired` — those are execution-only). `SupersedePlan` (fields per design §5.2: `schema_version`, `project_root`, `material_version`, `preview_date`, `selection: SupersedeSelection`, `decision_inputs_sha256`, `to_mark`, `to_repair`, `writes: list[PathTransition]`, `preview_report`).

- [ ] **Step 1: Write the failing test**

```python
# science/tests/test_supersede_plan.py
from __future__ import annotations

import pytest

from science_tool.plan_common import AllSupersessionMembers, PathTransition, StateFingerprint
from science_tool.supersede_plan import SupersedePlan, SupersedePreviewReport


def test_preview_report_forbids_execution_keys() -> None:
    rpt = SupersedePreviewReport(
        chains=[], non_linear=[], to_mark=[], skipped_kinds=[], to_repair=[],
        invalid_relations=[], archived_targets=[], unmanaged_targets=[], unbacked_inverses=[],
    )
    assert rpt.to_mark == []
    with pytest.raises(ValueError):
        SupersedePreviewReport(chains=[], non_linear=[], to_mark=[], skipped_kinds=[], to_repair=[],
                               invalid_relations=[], archived_targets=[], unmanaged_targets=[],
                               unbacked_inverses=[], applied=[])  # type: ignore[call-arg]


def test_supersede_plan_roundtrips_and_forbids_extra() -> None:
    plan = SupersedePlan(
        schema_version=1, project_root="/p", material_version=1, preview_date="2026-07-18",
        selection=AllSupersessionMembers(kind="all"), decision_inputs_sha256="a" * 64,
        to_mark=[], to_repair=[], writes=[],
        preview_report=SupersedePreviewReport(
            chains=[], non_linear=[], to_mark=[], skipped_kinds=[], to_repair=[],
            invalid_relations=[], archived_targets=[], unmanaged_targets=[], unbacked_inverses=[]),
    )
    again = SupersedePlan.model_validate_json(plan.model_dump_json())
    assert again == plan
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --frozen pytest science/tests/test_supersede_plan.py -q`
Expected: FAIL — module missing.

- [ ] **Step 3: Write minimal implementation**

```python
# science/src/science_tool/supersede_plan.py
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from science_tool.plan_common import PathTransition, SupersedeSelection


class SupersedePreviewReport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    chains: list[dict[str, Any]]
    non_linear: list[dict[str, Any]]
    to_mark: list[str]
    skipped_kinds: list[dict[str, str]]
    to_repair: list[str]
    invalid_relations: list[dict[str, Any]]
    archived_targets: list[dict[str, str]]
    unmanaged_targets: list[dict[str, str]]
    unbacked_inverses: list[dict[str, str]]


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

Run: `uv run --frozen pytest science/tests/test_supersede_plan.py -q`
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
- Produces: `plan_supersede(project_root: Path, *, selection: SupersedeSelection, preview_date: str) -> SupersedePlan`. Builds the decision material + digest, derives the selected disposition, and for each member renders the frozen postimage via `_prepare_write_with_date(..., updated_default=preview_date)`, wrapping it as a `PathTransition` (`role="entity-rewrite"`, `pre`=live fingerprint, `post`=fingerprint of the rendered text, `postimage`=rendered text). Populates the preview report from `mark_superseded(project_root, ids=..., apply=False)`.

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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --frozen pytest science/tests/test_supersede_plan.py -q`
Expected: FAIL — `plan_supersede` missing.

- [ ] **Step 3: Write minimal implementation**

```python
# add to science/src/science_tool/supersede_plan.py
from pathlib import Path

from science_tool.consolidation import (
    build_decision_material, build_supersedes_graph_from_material, decision_digest, mark_superseded,
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
    project_root = project_root.resolve()
    material = build_decision_material(project_root)
    graph = build_supersedes_graph_from_material(material)
    ids = _selected_ids(selection)
    report_dict = mark_superseded(project_root, ids=ids, apply=False)
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
        post = _fingerprint_of_text(prepared.text)
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


def _fingerprint_of_text(text: str) -> StateFingerprint:
    import hashlib
    return StateFingerprint(existed=True, type="file",
                            content_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
                            mode=0o644, symlink_target=None)
```

Implementer note: the `post.mode` here is a nominal `0o644`; apply (Task 13) realizes the live file's actual mode via the staged write. If a member's live file has a non-default mode you want preserved, read `fingerprint(prepared.path).mode` for `post.mode` — but a supersession rewrite keeps the existing file, so match its current mode: set `post` mode to `fingerprint(prepared.path).mode`. Update `_fingerprint_of_text` to take the live mode; a test in Task 13 will pin mode preservation.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --frozen pytest science/tests/test_supersede_plan.py -q`
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
- Produces: `apply_supersede_plan(project_root: Path, plan: SupersedePlan, *, staging_token: str) -> dict` (returns the execution report `{"applied": [...], "repaired": [...]}`). Assumes the envelope was already verified by the CLI before parsing (Task 19). Runs: structural checks → gate A (rebuild material, compare digest + material_version) → gate B disposition (graph-from-material, apply selection, equal to `to_mark`/`to_repair`; blockers refuse) → gate B postimage (read live source, assert `matches(w.pre)`, re-render via `_prepare_write_with_date(..., updated_default=plan.preview_date)`, assert equals `w.postimage`) → snapshot → `staged_write` each → verify `matches(w.post)` → rollback on failure. `SupersedeApplyError(RuntimeError)`.

- [ ] **Step 1: Write the failing test**

```python
# append to science/tests/test_supersede_plan.py
from science_tool.plan_common import fingerprint
from science_tool.supersede_plan import SupersedeApplyError, apply_supersede_plan, plan_supersede


def test_apply_supersede_plan_matches_legacy_apply(tmp_path: Path) -> None:
    _chain(tmp_path)
    plan = plan_supersede(tmp_path, selection=AllSupersessionMembers(kind="all"),
                          preview_date="2026-07-18")
    report = apply_supersede_plan(tmp_path, plan, staging_token="tkn")
    assert report["applied"] == ["interpretation:0002-b"]
    text = (tmp_path / "entities" / "interpretations" / "0002-b.md").read_text(encoding="utf-8")
    assert "status: superseded" in text
    assert "superseded_by: interpretation:0001-a" in text
    assert text == plan.writes[0].postimage  # byte-exact replay


def test_apply_refuses_when_corpus_drifted(tmp_path: Path) -> None:
    _chain(tmp_path)
    plan = plan_supersede(tmp_path, selection=AllSupersessionMembers(kind="all"),
                          preview_date="2026-07-18")
    # mutate an unrelated-but-material-bearing field after freezing the plan
    a = tmp_path / "entities" / "interpretations" / "0001-a.md"
    a.write_text(a.read_text(encoding="utf-8").replace("title: A", "title: A2"), encoding="utf-8")
    with pytest.raises(SupersedeApplyError):
        apply_supersede_plan(tmp_path, plan, staging_token="tkn")


def test_apply_refuses_tampered_postimage(tmp_path: Path) -> None:
    _chain(tmp_path)
    plan = plan_supersede(tmp_path, selection=AllSupersessionMembers(kind="all"),
                          preview_date="2026-07-18")
    w = plan.writes[0]
    tampered = w.postimage.replace("superseded_by: interpretation:0001-a",
                                   "superseded_by: interpretation:9999-z")
    from science_tool.plan_common import StateFingerprint
    import hashlib
    bad_post = StateFingerprint(existed=True, type="file",
                                content_sha256=hashlib.sha256(tampered.encode()).hexdigest(),
                                mode=w.post.mode, symlink_target=None)
    plan.writes[0] = w.model_copy(update={"postimage": tampered, "post": bad_post})
    with pytest.raises(SupersedeApplyError):
        apply_supersede_plan(tmp_path, plan, staging_token="tkn")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --frozen pytest science/tests/test_supersede_plan.py -q`
Expected: FAIL — `apply_supersede_plan` missing.

- [ ] **Step 3: Write minimal implementation**

```python
# add to science/src/science_tool/supersede_plan.py
from science_tool.consolidation import SupersessionError
from science_tool.plan_common import (
    matches, rollback_transitions, snapshot_paths, staged_write,
)


class SupersedeApplyError(RuntimeError):
    pass


def apply_supersede_plan(project_root: Path, plan: SupersedePlan, *, staging_token: str) -> dict:
    project_root = project_root.resolve()
    if plan.project_root != str(project_root):
        raise SupersedeApplyError("plan project_root does not match")
    # bijection: writes <-> to_mark ∪ to_repair
    members = [*plan.to_mark, *plan.to_repair]
    write_paths = {w.rel_path for w in plan.writes}
    if len(write_paths) != len(plan.writes):
        raise SupersedeApplyError("duplicate write paths")
    if len(members) != len(set(members)) or len(members) != len(plan.writes):
        raise SupersedeApplyError("writes/disposition are not a bijection")

    # Gate A — corpus drift
    material = build_decision_material(project_root)
    if material.material_version != plan.material_version:
        raise SupersedeApplyError("material_version mismatch")
    if decision_digest(material) != plan.decision_inputs_sha256:
        raise SupersedeApplyError("corpus changed since preview (decision digest mismatch)")

    # Gate B — disposition from material
    graph = build_supersedes_graph_from_material(material)
    ids = _selected_ids(plan.selection)
    try:
        re_report = mark_superseded(project_root, ids=ids, apply=False)
    except SupersessionError as exc:
        raise SupersedeApplyError(str(exc)) from exc
    if list(re_report["to_mark"]) != plan.to_mark or list(re_report["to_repair"]) != plan.to_repair:
        raise SupersedeApplyError("re-derived disposition differs from the plan")
    if re_report["invalid_relations"] or re_report["unbacked_inverses"]:
        raise SupersedeApplyError("corpus-wide blockers present; refusing")

    # Gate B — postimage from live source (bound by pre fingerprint)
    by_member = dict(zip(members, plan.writes, strict=True))
    for member, w in by_member.items():
        target = project_root / w.rel_path
        if not matches(w.pre, target):
            raise SupersedeApplyError(f"pre-state changed for {w.rel_path}")
        prepared = _prepare_write_with_date(
            project_root, member,
            {"status": "superseded", "superseded_by": graph.superseder_by_id[member]},
            updated_default=plan.preview_date,
        )
        if prepared.text != w.postimage:
            raise SupersedeApplyError(f"re-rendered postimage differs for {w.rel_path}")

    # Execute
    targets = [project_root / w.rel_path for w in plan.writes]
    snap = snapshot_paths(targets)
    try:
        for w in plan.writes:
            staged_write(project_root / w.rel_path, w.postimage, w.post.mode or 0o644, staging_token)
        for w in plan.writes:
            if not matches(w.post, project_root / w.rel_path):
                raise SupersedeApplyError(f"post-state verification failed for {w.rel_path}")
    except Exception:
        rollback_transitions(plan.writes, project_root, snap)
        raise
    return {"applied": list(plan.to_mark), "repaired": list(plan.to_repair)}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --frozen pytest science/tests/test_supersede_plan.py -q`
Expected: PASS (legacy-match, drift-refusal, tamper-refusal).

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
- Produces: `ArchivePreviewReport` (`extra="forbid"`; `candidates: list[dict]` — the dry-run candidate list `archive_entities` returns, each `{id, kind, status, original_path, superseded_by, resynthesized_into, inbound_live_refs}`). `ArchiveMove` (`id`, `original_path`, `archive_path`, `row: dict` — the frozen ArchiveRow as a dict). `ArchivePlan` (design §4.1: `schema_version`, `project_root`, `op`, `now`, `selection: ArchiveSelection`, `moves`, `index: PathTransition`, `transitions: list[PathTransition]`, `preview_report`).

- [ ] **Step 1: Write the failing test**

```python
# science/tests/test_archive_plan.py
from __future__ import annotations

import pytest

from science_tool.plan_common import ArchiveStatusSweep, PathTransition, StateFingerprint
from science_tool.archive_plan import ArchiveMove, ArchivePlan, ArchivePreviewReport


def _fp_file(sha: str) -> StateFingerprint:
    return StateFingerprint(existed=True, type="file", content_sha256=sha, mode=0o644, symlink_target=None)


def test_archive_plan_roundtrips_and_forbids_extra() -> None:
    import hashlib
    body = "index bytes\n"
    idx = PathTransition(role="archive-index", rel_path="entities/_archive/archive-index.jsonl",
                         pre=StateFingerprint(existed=False, type=None, content_sha256=None, mode=None, symlink_target=None),
                         post=_fp_file(hashlib.sha256(body.encode()).hexdigest()), postimage=body)
    plan = ArchivePlan(
        schema_version=1, project_root="/p", op="archive", now="2026-07-18T00:00:00Z",
        selection=ArchiveStatusSweep(kind="all_by_status", statuses=["superseded"]),
        moves=[], index=idx, transitions=[],
        preview_report=ArchivePreviewReport(candidates=[]),
    )
    assert ArchivePlan.model_validate_json(plan.model_dump_json()) == plan
    with pytest.raises(ValueError):
        ArchivePreviewReport(candidates=[], bogus=1)  # type: ignore[call-arg]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --frozen pytest science/tests/test_archive_plan.py -q`
Expected: FAIL — module missing.

- [ ] **Step 3: Write minimal implementation**

```python
# science/src/science_tool/archive_plan.py
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from science_tool.plan_common import ArchiveSelection, PathTransition


class ArchivePreviewReport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    candidates: list[dict[str, Any]]


class ArchiveMove(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    original_path: str
    archive_path: str
    row: dict[str, Any]


class ArchivePlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: int
    project_root: str
    op: Literal["archive"]
    now: str
    selection: ArchiveSelection
    moves: list[ArchiveMove]
    index: PathTransition
    transitions: list[PathTransition]
    preview_report: ArchivePreviewReport
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --frozen pytest science/tests/test_archive_plan.py -q`
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
    assert m.row["archived_at"] == "2026-07-18T00:00:00Z"
    assert plan.index.role == "archive-index"
    assert plan.index.postimage.endswith("\n")
    assert "interpretation:0001-x" in plan.index.postimage
    # a src transition exists with the live pre-state
    src = [t for t in plan.transitions if t.role == "archive-src"][0]
    assert src.pre == fingerprint(tmp_path / src.rel_path)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --frozen pytest science/tests/test_archive_plan.py -q`
Expected: FAIL — `plan_archive` missing.

- [ ] **Step 3: Write minimal implementation**

```python
# add to science/src/science_tool/archive_plan.py
import hashlib
import json
from pathlib import Path

from science_tool.archive import (
    DEFAULT_ARCHIVE_STATUSES, archive_index_path, derive_archive_path, _candidate_rows,
    _inbound_live_refs, _scope_rows_to_allowlist,
)
from science_tool.plan_common import (
    ArchiveStatusSweep, ExplicitArchiveIds, StateFingerprint, fingerprint,
)


def _fp_of_bytes(data: bytes, mode: int) -> StateFingerprint:
    return StateFingerprint(existed=True, type="file",
                            content_sha256=hashlib.sha256(data).hexdigest(), mode=mode, symlink_target=None)


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
    for r in rows:
        frozen = r.model_copy(update={"archived_at": now})
        original = r.original_path
        archived = derive_archive_path(original)
        src_abs = project_root / original
        dst_abs = project_root / archived
        src_pre = fingerprint(src_abs)
        moves.append(ArchiveMove(id=r.id, original_path=original, archive_path=archived,
                                 row=frozen.model_dump()))
        transitions.append(PathTransition(role="archive-src", rel_path=original, pre=src_pre,
                                          post=StateFingerprint(existed=False, type=None,
                                          content_sha256=None, mode=None, symlink_target=None)))
        transitions.append(PathTransition(role="archive-dst", rel_path=archived,
                                          pre=StateFingerprint(existed=False, type=None,
                                          content_sha256=None, mode=None, symlink_target=None),
                                          post=StateFingerprint(existed=True, type="file",
                                          content_sha256=src_pre.content_sha256, mode=src_pre.mode,
                                          symlink_target=None)))
        parent = dst_abs.parent
        if not parent.exists() and parent not in created_dirs:
            created_dirs.add(parent)
            transitions.append(PathTransition(role="created-dir",
                               rel_path=parent.relative_to(project_root).as_posix(),
                               pre=StateFingerprint(existed=False, type=None, content_sha256=None,
                                                    mode=None, symlink_target=None),
                               post=StateFingerprint(existed=True, type="dir", content_sha256=None,
                                                     mode=0o755, symlink_target=None)))

    index_abs = archive_index_path(project_root)
    pre_bytes = index_abs.read_bytes() if index_abs.exists() else b""
    appended = "".join(json.dumps(m.row, sort_keys=True) + "\n" for m in moves)
    post_bytes = pre_bytes + appended.encode("utf-8")
    index_pre = fingerprint(index_abs)
    index_mode = index_pre.mode if index_pre.existed else 0o644
    index = PathTransition(role="archive-index",
                           rel_path=index_abs.relative_to(project_root).as_posix(),
                           pre=index_pre, post=_fp_of_bytes(post_bytes, index_mode),
                           postimage=post_bytes.decode("utf-8"))

    report = ArchivePreviewReport(candidates=[
        {"id": r.id, "kind": r.kind, "status": r.status, "original_path": r.original_path,
         "superseded_by": r.superseded_by, "resynthesized_into": r.resynthesized_into,
         "inbound_live_refs": inbound.get(r.id, [])} for r in rows])
    return ArchivePlan(schema_version=1, project_root=str(project_root), op="archive", now=now,
                       selection=selection, moves=moves, index=index, transitions=transitions,
                       preview_report=report)
```

Implementer note: confirm `ArchiveRow` has a `.model_copy`/`.model_dump` (it is a pydantic `BaseModel`, `archive.py:25`) and that `_candidate_rows` returns rows carrying `original_path`, `kind`, `status`, `superseded_by`, `resynthesized_into`. `derive_archive_path` and `archive_index_path` are module functions (`archive.py:65`, `archive.py:61`).

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --frozen pytest science/tests/test_archive_plan.py -q`
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
- Produces: `apply_archive_plan(project_root: Path, plan: ArchivePlan, *, staging_token: str) -> dict` (returns `{"applied": [...], "skipped": [...]}`). Envelope pre-verified by CLI. Runs: structural (containment via `plan_common` containment helper, `archive_path == derive_archive_path(original_path)`, move↔transition bijection, no dup ids/paths) → gate B (re-derive selected rows + literal index from live sources; compare each `row` and `index.postimage` byte-for-byte) → pre-state assert → snapshot → create dirs, `os.rename` moves (EXDEV refusal) + parent fsync, `os.replace` index via `staged_write` → post verify → rollback on failure. `ArchiveApplyError(RuntimeError)`.

- [ ] **Step 1: Write the failing test**

```python
# append to science/tests/test_archive_plan.py
from science_tool.archive_plan import ArchiveApplyError, apply_archive_plan, plan_archive


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


def test_apply_archive_refuses_tampered_row(tmp_path: Path) -> None:
    _superseded(tmp_path)
    plan = plan_archive(tmp_path, selection=ArchiveStatusSweep(kind="all_by_status", statuses=["superseded"]),
                        now="2026-07-18T00:00:00Z")
    plan.moves[0].row["title"] = "TAMPERED"
    with pytest.raises(ArchiveApplyError):
        apply_archive_plan(tmp_path, plan, staging_token="tok")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --frozen pytest science/tests/test_archive_plan.py -q`
Expected: FAIL — `apply_archive_plan` missing.

- [ ] **Step 3: Write minimal implementation**

```python
# add to science/src/science_tool/archive_plan.py
import errno
import os

from science_tool.plan_common import (
    matches, rollback_transitions, snapshot_paths, staged_write,
)


class ArchiveApplyError(RuntimeError):
    pass


def apply_archive_plan(project_root: Path, plan: ArchivePlan, *, staging_token: str) -> dict:
    project_root = project_root.resolve()
    if plan.project_root != str(project_root):
        raise ArchiveApplyError("plan project_root does not match")

    # Structural: canonical archive paths + bijection
    for m in plan.moves:
        if derive_archive_path(m.original_path) != m.archive_path:
            raise ArchiveApplyError(f"non-canonical archive_path for {m.id}")
    ids = [m.id for m in plan.moves]
    if len(ids) != len(set(ids)):
        raise ArchiveApplyError("duplicate move ids")

    # Gate B: re-derive rows + index from live sources, compare byte-for-byte
    expected = plan_archive(project_root, selection=plan.selection, now=plan.now)
    if [m.model_dump() for m in expected.moves] != [m.model_dump() for m in plan.moves]:
        raise ArchiveApplyError("re-derived moves/rows differ from the plan")
    if expected.index.postimage != plan.index.postimage:
        raise ArchiveApplyError("re-derived index postimage differs from the plan")

    # Pre-state gate
    all_t = [*plan.transitions, plan.index]
    for t in all_t:
        if not matches(t.pre, project_root / t.rel_path):
            raise ArchiveApplyError(f"pre-state changed for {t.rel_path}")

    snap = snapshot_paths([project_root / t.rel_path for t in all_t])
    try:
        for t in plan.transitions:
            if t.role == "created-dir":
                d = project_root / t.rel_path
                d.mkdir(parents=True, exist_ok=True)
                os.chmod(d, t.post.mode or 0o755)
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
        staged_write(project_root / plan.index.rel_path, plan.index.postimage,
                     plan.index.post.mode or 0o644, staging_token)
        for t in all_t:
            if not matches(t.post, project_root / t.rel_path):
                raise ArchiveApplyError(f"post-state verification failed for {t.rel_path}")
    except Exception:
        rollback_transitions(all_t, project_root, snap)
        raise
    return {"applied": [m.id for m in plan.moves], "skipped": []}


def _fsync_dir(directory: Path) -> None:
    fd = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
```

Implementer note: `rollback_transitions` handles `entity-rewrite`/file transitions; for `archive-src` (post absent) and `archive-dst` (pre absent) it reverts correctly given `snapshot_paths` captured both. Verify the move rollback restores the src and removes the dst in a dedicated test (add one mirroring `test_rollback_*`).

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --frozen pytest science/tests/test_archive_plan.py -q`
Expected: PASS.

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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --frozen pytest science/tests/test_supersede_plan_cli.py -q`
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
@click.option("--staging-token", default="apply", help="Batch token for staging paths (default: apply).")
def entities_mark_superseded_command(project_root, ids, ids_from, apply_changes, save_plan,
                                     overwrite_plan, apply_plan_path, expected_plan_sha256, staging_token):
    """Auto-derive `superseded` status from linear supersedes chains (report / --save-plan / --apply-plan)."""
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
        try:
            report = apply_supersede_plan(project_root.resolve(), plan, staging_token=staging_token)
        except SupersedeApplyError as exc:
            raise click.ClickException(str(exc)) from exc
        emit(output_format="json", payload=report, render_text=lambda: None)
        return

    allowlist = _collect_ids(ids, ids_from)
    if save_plan is not None:
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

    try:
        report = mark_superseded(project_root, ids=allowlist, apply=apply_changes)
    except SupersessionError as exc:
        raise click.ClickException(str(exc)) from exc
    emit(output_format="json", payload=report, render_text=lambda: None)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --frozen pytest science/tests/test_supersede_plan_cli.py -q`
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

Run: `uv run --frozen pytest science/tests/test_archive_plan_cli.py -q`
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
@click.option("--staging-token", default="apply", help="Batch token for staging paths (default: apply).")
def entities_archive_command(project_root, statuses, ids, ids_from, apply_changes, save_plan,
                             overwrite_plan, apply_plan_path, expected_plan_sha256, staging_token):
    """Relocate hidden-status entities into entities/_archive/ (report / --save-plan / --apply-plan)."""
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
        try:
            report = apply_archive_plan(project_root.resolve(), plan, staging_token=staging_token)
        except ArchiveApplyError as exc:
            raise click.ClickException(str(exc)) from exc
        emit(output_format="json", payload=report, render_text=lambda: None)
        return

    status_set = frozenset(statuses) if statuses else DEFAULT_ARCHIVE_STATUSES
    allowlist = _collect_ids(ids, ids_from)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if save_plan is not None:
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

    try:
        report = archive_entities(project_root, statuses=status_set, ids=allowlist,
                                  apply=apply_changes, now=now)
    except ArchiveError as exc:
        raise click.ClickException(str(exc)) from exc
    emit(output_format="json", payload=report, render_text=lambda: None)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --frozen pytest science/tests/test_archive_plan_cli.py -q`
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
- Modify: `science/pyproject.toml:3`, `.claude-plugin/plugin.json:3`, `science/tests/test_cli_version.py:27`
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

Run: `uv run --frozen pytest science/tests/test_cli_version.py -q`
Expected: FAIL — package version is still `0.4.1`.

- [ ] **Step 3: Bump both version strings**

`science/pyproject.toml:3`: `version = "0.5.0"`.
`.claude-plugin/plugin.json:3`: `"version": "0.5.0",`.

- [ ] **Step 4: Run version + compatibility tests**

Run: `uv run --frozen pytest science/tests/test_cli_version.py science/tests/test_agent_cli_compatibility.py -q`
Expected: PASS — the baseline test now green, and `test_agent_cli_compatibility.py` (command floor ≤ version) passes **unchanged**.

- [ ] **Step 5: Commit**

```bash
git add science/pyproject.toml .claude-plugin/plugin.json science/tests/test_cli_version.py
git commit -m "release: science 0.5.0 — savable archive/mark-superseded plans"
```

---

### Task 19: Full-suite green + release commit

**Files:** none new — a gate.

- [ ] **Step 1: Run the whole suite**

Run: `uv run --frozen pytest science/tests -q`
Expected: PASS (no regressions across archive/consolidation/entity-import/version suites).

- [ ] **Step 2: Run repo validation**

Run: `bash validate.sh --verbose` (from `~/d/science`, if present)
Expected: PASS.

- [ ] **Step 3: Commit any lint/format fixups**

```bash
git add -A
git commit -m "chore: lint/format for 0.5.0 curation plans"
```

---

## Consumer-side delivery gate (natural-systems, tracked separately)

Not part of this upstream branch, but the acceptance the design §8 requires before Plan 2 can use the capability. Perform in the `natural-systems` repo after the upstream lands + pushes:

1. Update the `science` pin in `uv.lock` to the merged revision; `uv sync --frozen`.
2. Extend `scripts/__tests__/test_science_cli_surface.py` to assert `--save-plan`/`--apply-plan`/`--expected-plan-sha256`/`--staging-token` on both commands, on the pinned revision.
3. Run consumer integration tests; `uv run --frozen science validate --verbose`; `bash validate.sh --verbose`.

---

## Self-Review

**Spec coverage:** §1 three-layer authorization → Tasks 4 (envelope), 8/9 (gate A material+digest), 11/12 & 14/15 (gate B). §3.1 StateFingerprint → Task 1. §3.2 PathTransition → Task 2. §3.3 rollback → Task 6. §3.4 staging → Task 5. §3.5 selections → Task 3. §4 archive → Tasks 13-15, 17. §5 supersede → Tasks 8-12, 16, incl. §5.4 injectable writer → Task 7. §6 CLI → Tasks 16-17. §8 release → Task 18. §9 tests are distributed across the task tests; the kill-classification characterization tests (§9 last bullet) should be added as a dedicated test in Task 15/12 follow-up — **add them during execution** where `staged_write`/`os.rename` boundaries exist.

**Known decomposition gaps for the executor to close (not placeholders — explicit follow-ups):**
- Task 11 `post.mode`: set to the live file's mode, not a nominal `0o644` (noted inline).
- Task 15: add a move-rollback test and the §9 kill-classification tests (kill mid-staging leaves a prefix `.tmp`, kill after rename leaves classifiable state).
- Task 9: the topology extraction must be behavior-preserving; the existing `test_consolidation_mark_superseded.py` is the guard.

**Type consistency:** `PathTransition`, `StateFingerprint`, `ArchiveSelection`/`SupersedeSelection`, `plan_supersede`/`apply_supersede_plan`, `plan_archive`/`apply_archive_plan`, `_prepare_write_with_date`, `build_supersedes_graph_from_material`, `build_decision_material`/`decision_digest` names are used consistently across tasks.

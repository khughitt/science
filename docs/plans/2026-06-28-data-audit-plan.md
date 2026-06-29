# `science data audit` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a data-policy SSOT and a `science data audit` command that makes the tracked/ignored boundary legible by location — payloads stay in ignored `data/`, lightweight records move to tracked `results/`.

**Architecture:** A pure classifier (`data_policy.py`) is the single source of truth for RECORD/PAYLOAD/FLAG. A detection pass (`data_audit.py`) cross-checks classification × location × git-tracked state into violation quadrants and emits a `--json` contract. A conservative fixer (`data_audit_fix.py`) relocates stranded records `data/` → `results/`, rewrites moved datapackage resource paths (preserving `basepath`), and FLAGs everything risky or ambiguous. A new `data` CLI group wires it up.

**Tech Stack:** Python 3.13, `click`, `pydantic` (config block), `pyyaml` (datapackage rewrite), `subprocess` for git, `pytest` + `click.testing.CliRunner`.

## Global Constraints

- All package code lives under `science/src/science_tool/`; tests under `science/tests/`. This spec/plan lives at the repo root.
- Run tests with: `cd ~/d/science/science && uv run --no-sync pytest <path> -v` (system python lacks `pydantic`; `.venv` is uv-managed).
- Commit message style: no `Co-Authored-By` trailers.
- `DEFAULT_DATA_DIRS` (`science/src/science_tool/data_worktree.py:7` = `(data/raw, data/processed, data/external)`) is the authoritative payload-territory signal; read it, never hard-code.
- `size_threshold` default = `150_000` bytes.
- `--fix` **stages** results (target under `results/…`) but **never commits**.
- `--fix` automatic moves go in ONE direction only: stranded RECORD `data/` → `results/`. Leaked payloads and all ambiguity → FLAG, never move.
- Datapackage resource resolution contract that must be preserved: `descriptor.parent / basepath / resources[].path` (per-output uses `basepath: ".."`; aggregate has none).
- Pattern matching everywhere uses `fnmatch.fnmatch(rel.as_posix(), pat) or fnmatch.fnmatch(rel.name, pat)`.

Reference spec: `docs/plans/2026-06-28-data-audit-design.md`.

---

### Task 1: `data_policy.py` — the classifier SSOT

**Files:**
- Create: `science/src/science_tool/data_policy.py`
- Test: `science/tests/test_data_policy.py`

**Interfaces:**
- Consumes: nothing (standalone, no internal imports → no cycles).
- Produces:
  - `class FileClass(StrEnum)` with members `RECORD = "record"`, `PAYLOAD = "payload"`, `FLAG = "flag"`.
  - `@dataclass(frozen=True) class DataPolicy` with fields `record_patterns: tuple[str, ...]`, `payload_extensions: tuple[str, ...]`, `size_threshold: int`.
  - `DEFAULT_DATA_POLICY: DataPolicy`.
  - `def classify(rel_path: Path, size_bytes: int, policy: DataPolicy = DEFAULT_DATA_POLICY) -> FileClass`.

- [ ] **Step 1: Write the failing tests**

```python
# science/tests/test_data_policy.py
"""Tests for the data-policy classifier SSOT."""
from pathlib import Path

from science_tool.data_policy import (
    DEFAULT_DATA_POLICY,
    DataPolicy,
    FileClass,
    classify,
)

KB = 1024


def test_payload_extension_is_payload_regardless_of_size():
    # A tiny .feather is still a payload — extension wins over size.
    assert classify(Path("data/processed/exp1/m.feather"), 10) is FileClass.PAYLOAD
    assert classify(Path("data/processed/exp1/big.feather"), 5_000_000) is FileClass.PAYLOAD


def test_known_record_under_threshold_is_record():
    assert classify(Path("data/processed/exp1/RESULTS.md"), 2 * KB) is FileClass.RECORD
    assert classify(Path("data/processed/exp1/datapackage.yaml"), 1 * KB) is FileClass.RECORD
    assert classify(Path("data/processed/exp1/qa/precision.json"), 500) is FileClass.RECORD


def test_known_record_over_threshold_is_flag():
    # Large record → FLAG (irreplaceable hand-authored? author decides).
    assert classify(Path("data/processed/exp1/RESULTS.md"), 300_000) is FileClass.FLAG


def test_unknown_large_is_payload():
    assert classify(Path("data/processed/exp1/dump.bin"), 5_000_000) is FileClass.PAYLOAD


def test_unknown_small_is_flag():
    # Bare .csv matching no record pattern is NOT auto-tracked — surfaced for decision.
    assert classify(Path("data/processed/exp1/scratch.csv"), 1 * KB) is FileClass.FLAG


def test_threshold_boundary_is_inclusive_record():
    # size == threshold counts as "under" (≤) → RECORD for a known record.
    pol = DEFAULT_DATA_POLICY
    assert classify(Path("notes-notes.md"), pol.size_threshold) is FileClass.RECORD
    assert classify(Path("notes-notes.md"), pol.size_threshold + 1) is FileClass.FLAG


def test_default_policy_values():
    assert DEFAULT_DATA_POLICY.size_threshold == 150_000
    assert ".feather" in DEFAULT_DATA_POLICY.payload_extensions


def test_custom_policy_overrides_threshold():
    pol = DataPolicy(
        record_patterns=("RESULTS*.md",),
        payload_extensions=(".feather",),
        size_threshold=10,
    )
    assert classify(Path("RESULTS.md"), 5, pol) is FileClass.RECORD
    assert classify(Path("RESULTS.md"), 20, pol) is FileClass.FLAG
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/d/science/science && uv run --no-sync pytest tests/test_data_policy.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'science_tool.data_policy'`.

- [ ] **Step 3: Write the implementation**

```python
# science/src/science_tool/data_policy.py
"""The data-policy SSOT: classify a project file as a tracked RECORD, an ignored
PAYLOAD, or a FLAG (ambiguous — surfaced for an explicit human decision).

This is the single place the COMMIT-vs-KEEP-IGNORED rule is expressed; the audit
(and any future size-guard hook) consume `classify`. Pure and deterministic: no
filesystem mutation, no git calls. See docs/plans/2026-06-28-data-audit-design.md.
"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class FileClass(StrEnum):
    RECORD = "record"    # lightweight, durable → belongs tracked
    PAYLOAD = "payload"  # large/regenerable → belongs ignored under data/
    FLAG = "flag"        # ambiguous → never auto-acted, surfaced for a decision


@dataclass(frozen=True)
class DataPolicy:
    record_patterns: tuple[str, ...]
    payload_extensions: tuple[str, ...]
    size_threshold: int


# Name/path-based record globs only — size is the classifier's job, never encoded
# into a pattern. A bare .csv/.json matching none of these falls to unknown-small
# → FLAG (the intended conservative behavior).
_DEFAULT_RECORD_PATTERNS: tuple[str, ...] = (
    "datapackage.json",
    "datapackage.yaml",
    "RESULTS*.md",
    "*-report.md",
    "*-report.json",
    "**/qa/*.json",
    "README.md",
    "RUBRIC.md",
    "validate_*.py",
    "*worksheet*.jsonl",
    "*verdict*",
    "*label*",
    "*-notes.md",
    "*majority*",
    "*.datapackage.json",  # dataset metadata sidecars
    "*interpretation*.md",
)

_DEFAULT_PAYLOAD_EXTENSIONS: tuple[str, ...] = (
    ".parquet", ".feather", ".pkl", ".pdf", ".npy", ".npz",
    ".tar", ".tar.gz", ".tgz", ".zip", ".mp4", ".mat",
)

DEFAULT_DATA_POLICY = DataPolicy(
    record_patterns=_DEFAULT_RECORD_PATTERNS,
    payload_extensions=_DEFAULT_PAYLOAD_EXTENSIONS,
    size_threshold=150_000,
)


def _matches_any(rel_path: Path, patterns: tuple[str, ...]) -> bool:
    posix = rel_path.as_posix()
    name = rel_path.name
    return any(
        fnmatch.fnmatch(posix, pat) or fnmatch.fnmatch(name, pat) for pat in patterns
    )


def classify(
    rel_path: Path, size_bytes: int, policy: DataPolicy = DEFAULT_DATA_POLICY
) -> FileClass:
    """Classify a repo-relative path + size. Conservative; first match wins."""
    name = rel_path.name.lower()
    if any(name.endswith(ext) for ext in policy.payload_extensions):
        return FileClass.PAYLOAD
    is_record = _matches_any(rel_path, policy.record_patterns)
    if is_record:
        return FileClass.RECORD if size_bytes <= policy.size_threshold else FileClass.FLAG
    if size_bytes > policy.size_threshold:
        return FileClass.PAYLOAD  # large unknown → safe to ignore
    return FileClass.FLAG          # small unknown → never auto-track
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/d/science/science && uv run --no-sync pytest tests/test_data_policy.py -v`
Expected: PASS (all 8 tests).

- [ ] **Step 5: Commit**

```bash
cd ~/d/science/science
git add src/science_tool/data_policy.py tests/test_data_policy.py
git commit -m "feat(data): add data-policy classifier SSOT"
```

---

### Task 2: `DataPolicyConfig` — per-project override in `science.yaml`

**Files:**
- Modify: `science/src/science_tool/project_config.py` (add `DataPolicyConfig` near `RefsConfig`; add `data_policy` field on `ProjectConfig`)
- Test: `science/tests/test_data_policy_config.py`

**Interfaces:**
- Consumes: `DataPolicy`, `DEFAULT_DATA_POLICY` from Task 1.
- Produces:
  - `class DataPolicyConfig(BaseModel)` with fields `record_patterns: list[str]`, `payload_extensions: list[str]`, `size_threshold: int` (defaults mirror `DEFAULT_DATA_POLICY`), `model_config = ConfigDict(extra="forbid")`, and method `def to_policy(self) -> DataPolicy`.
  - `ProjectConfig.data_policy: DataPolicyConfig | None = None`.
  - `def resolve_data_policy(config: ProjectConfig) -> DataPolicy` (module-level: returns `config.data_policy.to_policy()` or `DEFAULT_DATA_POLICY`).

- [ ] **Step 1: Write the failing tests**

```python
# science/tests/test_data_policy_config.py
"""science.yaml data_policy block → DataPolicy resolution."""
from pathlib import Path

import pytest
import yaml

from science_tool.data_policy import DEFAULT_DATA_POLICY
from science_tool.project_config import (
    ProjectConfig,
    load_project_config,
    resolve_data_policy,
)


def _write_yaml(tmp_path: Path, body: dict) -> Path:
    body.setdefault("name", "Demo")
    (tmp_path / "science.yaml").write_text(yaml.safe_dump(body), encoding="utf-8")
    return tmp_path


def test_absent_block_resolves_to_default(tmp_path: Path):
    _write_yaml(tmp_path, {})
    cfg = load_project_config(tmp_path)
    assert cfg.data_policy is None
    assert resolve_data_policy(cfg) == DEFAULT_DATA_POLICY


def test_override_threshold_and_patterns(tmp_path: Path):
    _write_yaml(tmp_path, {
        "data_policy": {
            "record_patterns": ["RESULTS*.md"],
            "payload_extensions": [".feather"],
            "size_threshold": 256000,
        }
    })
    cfg = load_project_config(tmp_path)
    pol = resolve_data_policy(cfg)
    assert pol.size_threshold == 256000
    assert pol.record_patterns == ("RESULTS*.md",)
    assert pol.payload_extensions == (".feather",)


def test_unknown_field_rejected(tmp_path: Path):
    _write_yaml(tmp_path, {"data_policy": {"bogus": 1}})
    with pytest.raises(Exception):
        load_project_config(tmp_path)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/d/science/science && uv run --no-sync pytest tests/test_data_policy_config.py -v`
Expected: FAIL — `ImportError: cannot import name 'resolve_data_policy'`.

- [ ] **Step 3: Add the config block**

In `science/src/science_tool/project_config.py`, add the import near the top (after the existing imports):

```python
from science_tool.data_policy import DataPolicy, DEFAULT_DATA_POLICY
```

Add this class immediately after `class RefsConfig(BaseModel):` block (before `class ProjectConfig`):

```python
class DataPolicyConfig(BaseModel):
    """Per-project override of the data-tracking policy (`science data audit`)."""

    model_config = ConfigDict(extra="forbid")

    record_patterns: list[str] = Field(
        default_factory=lambda: list(DEFAULT_DATA_POLICY.record_patterns)
    )
    payload_extensions: list[str] = Field(
        default_factory=lambda: list(DEFAULT_DATA_POLICY.payload_extensions)
    )
    size_threshold: int = DEFAULT_DATA_POLICY.size_threshold

    def to_policy(self) -> DataPolicy:
        return DataPolicy(
            record_patterns=tuple(self.record_patterns),
            payload_extensions=tuple(self.payload_extensions),
            size_threshold=self.size_threshold,
        )
```

Add the field to `ProjectConfig` (next to `refs: RefsConfig | None = None`):

```python
    data_policy: DataPolicyConfig | None = None
```

Add this module-level helper after `load_project_config`:

```python
def resolve_data_policy(config: ProjectConfig) -> DataPolicy:
    """Return the effective DataPolicy: the project override or the framework default."""
    if config.data_policy is not None:
        return config.data_policy.to_policy()
    return DEFAULT_DATA_POLICY
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/d/science/science && uv run --no-sync pytest tests/test_data_policy_config.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Run the broader config suite (no regressions)**

Run: `cd ~/d/science/science && uv run --no-sync pytest tests/ -k project_config -v`
Expected: PASS (existing config tests still green).

- [ ] **Step 6: Commit**

```bash
cd ~/d/science/science
git add src/science_tool/project_config.py tests/test_data_policy_config.py
git commit -m "feat(data): add data_policy science.yaml override block"
```

---

### Task 3: `data_audit.py` — detection + `--json` contract (read-only)

**Files:**
- Create: `science/src/science_tool/data_audit.py`
- Test: `science/tests/test_data_audit.py`

**Interfaces:**
- Consumes: `FileClass`, `DataPolicy`, `DEFAULT_DATA_POLICY`, `classify` (Task 1); `DEFAULT_DATA_DIRS` from `science_tool.data_worktree`.
- Produces:
  - `class Quadrant(StrEnum)`: `STRANDED_RECORD = "stranded_record"`, `LEAKED_PAYLOAD = "leaked_payload"`, `FLAG = "flag"`.
  - `@dataclass(frozen=True) class Violation` with `quadrant: Quadrant`, `path: str` (repo-relative posix), `file_class: FileClass`, `proposed_target: str | None`.
  - `def git_tracked_set(project_root: Path) -> set[str]` (posix paths; empty set if not a git repo).
  - `def location(rel_path: Path, data_dirs: tuple[Path, ...]) -> str` → one of `"DATA"`, `"RESULTS"`, `"ENTITIES"`, `"TRACKED_OTHER"`.
  - `def propose_results_target(project_root: Path, rel_path: Path, data_dirs: tuple[Path, ...]) -> str | None`.
  - `def audit_project(project_root: Path, policy: DataPolicy = DEFAULT_DATA_POLICY, data_dirs: tuple[Path, ...] = DEFAULT_DATA_DIRS) -> list[Violation]`.
  - `def render_json(violations: list[Violation], outcomes: "list | None" = None) -> str`.

- [ ] **Step 1: Write the failing tests**

```python
# science/tests/test_data_audit.py
"""Detection pass for `science data audit`."""
import json
import subprocess
from pathlib import Path

from science_tool.data_audit import (
    Quadrant,
    audit_project,
    location,
    propose_results_target,
    render_json,
)
from science_tool.data_worktree import DEFAULT_DATA_DIRS


def _init_repo(root: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=root, check=True)


def _write(root: Path, rel: str, content: bytes = b"x") -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(content)
    return p


def test_location_classification():
    assert location(Path("data/processed/x/a.md"), DEFAULT_DATA_DIRS) == "DATA"
    assert location(Path("results/exp/a.md"), DEFAULT_DATA_DIRS) == "RESULTS"
    assert location(Path("entities/datasets/a.md"), DEFAULT_DATA_DIRS) == "ENTITIES"
    assert location(Path("doc/x.md"), DEFAULT_DATA_DIRS) == "TRACKED_OTHER"


def test_propose_target_uses_first_segment(tmp_path: Path):
    target = propose_results_target(
        tmp_path, Path("data/processed/exp1/RESULTS.md"), DEFAULT_DATA_DIRS
    )
    assert target == "results/exp1/RESULTS.md"


def test_propose_target_prefers_datapackage_workflow(tmp_path: Path):
    _write(tmp_path, "data/processed/exp1/datapackage.yaml",
           b"workflow: workflow:myflow\nname: x\n")
    target = propose_results_target(
        tmp_path, Path("data/processed/exp1/RESULTS.md"), DEFAULT_DATA_DIRS
    )
    assert target == "results/myflow/RESULTS.md"


def test_stranded_record_detected(tmp_path: Path):
    _init_repo(tmp_path)
    _write(tmp_path, "data/processed/exp1/RESULTS.md", b"# results\n")  # untracked
    violations = audit_project(tmp_path)
    stranded = [v for v in violations if v.quadrant is Quadrant.STRANDED_RECORD]
    assert len(stranded) == 1
    assert stranded[0].path == "data/processed/exp1/RESULTS.md"
    assert stranded[0].proposed_target == "results/exp1/RESULTS.md"


def test_leaked_payload_detected_only_when_tracked(tmp_path: Path):
    _init_repo(tmp_path)
    _write(tmp_path, "entities/x/big.feather", b"\x00" * 32)
    # Untracked → not yet a violation.
    assert not [v for v in audit_project(tmp_path)
                if v.quadrant is Quadrant.LEAKED_PAYLOAD]
    subprocess.run(["git", "add", "-f", "entities/x/big.feather"], cwd=tmp_path, check=True)
    leaked = [v for v in audit_project(tmp_path) if v.quadrant is Quadrant.LEAKED_PAYLOAD]
    assert len(leaked) == 1
    assert leaked[0].path == "entities/x/big.feather"


def test_unknown_small_is_flag_quadrant(tmp_path: Path):
    _init_repo(tmp_path)
    _write(tmp_path, "data/processed/exp1/scratch.csv", b"a,b\n1,2\n")
    flags = [v for v in audit_project(tmp_path) if v.quadrant is Quadrant.FLAG]
    assert any(v.path.endswith("scratch.csv") for v in flags)


def test_compliant_files_yield_no_violation(tmp_path: Path):
    _init_repo(tmp_path)
    _write(tmp_path, "results/exp1/RESULTS.md", b"# ok\n")          # record, tracked-side
    _write(tmp_path, "data/processed/exp1/m.feather", b"\x00" * 16)  # payload, ignored-side
    assert audit_project(tmp_path) == []


def test_render_json_shape(tmp_path: Path):
    _init_repo(tmp_path)
    _write(tmp_path, "data/processed/exp1/RESULTS.md", b"# r\n")
    payload = json.loads(render_json(audit_project(tmp_path)))
    assert payload["version"] == 1
    v = payload["violations"][0]
    assert v["quadrant"] == "stranded_record"
    assert v["target"] == "results/exp1/RESULTS.md"
    assert v["action"] == "move"  # planned action reported in read-only mode
    assert v["performed"] is False


def test_render_json_datapackage_planned_action(tmp_path: Path):
    _init_repo(tmp_path)
    _write(tmp_path, "data/processed/exp1/matrix.feather", b"\x00" * 8)
    _write(tmp_path, "data/processed/exp1/datapackage.yaml",
           b"name: x\nresources:\n- {name: m, path: matrix.feather}\n")
    payload = json.loads(render_json(audit_project(tmp_path)))
    dp_row = [r for r in payload["violations"] if r["path"].endswith("datapackage.yaml")][0]
    assert dp_row["action"] == "move+rewrite-resources"
    assert dp_row["performed"] is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/d/science/science && uv run --no-sync pytest tests/test_data_audit.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'science_tool.data_audit'`.

- [ ] **Step 3: Write the implementation**

```python
# science/src/science_tool/data_audit.py
"""Detection pass for `science data audit`.

Cross-checks each project file's (class × location × git-tracked) into violation
quadrants and renders the stable `--json` contract. Read-only — the fixer lives in
data_audit_fix.py. See docs/plans/2026-06-28-data-audit-design.md.
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import yaml

from science_tool.data_policy import (
    DEFAULT_DATA_POLICY,
    DataPolicy,
    FileClass,
    classify,
)
from science_tool.data_worktree import DEFAULT_DATA_DIRS


class Quadrant(StrEnum):
    STRANDED_RECORD = "stranded_record"
    LEAKED_PAYLOAD = "leaked_payload"
    FLAG = "flag"


@dataclass(frozen=True)
class Violation:
    quadrant: Quadrant
    path: str  # repo-relative posix
    file_class: FileClass
    proposed_target: str | None


def git_tracked_set(project_root: Path) -> set[str]:
    """Posix paths of all git-tracked files. Empty set if not a git repo."""
    try:
        out = subprocess.run(
            ["git", "-C", str(project_root), "ls-files", "-z"],
            capture_output=True, check=True,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return set()
    return {p for p in out.decode("utf-8").split("\0") if p}


def location(rel_path: Path, data_dirs: tuple[Path, ...]) -> str:
    for d in data_dirs:
        if rel_path == d or d in rel_path.parents:
            return "DATA"
    top = rel_path.parts[0] if rel_path.parts else ""
    if top == "results":
        return "RESULTS"
    if top == "entities":
        return "ENTITIES"
    return "TRACKED_OTHER"


def _data_subpath(rel_path: Path, data_dirs: tuple[Path, ...]) -> Path | None:
    """The path *relative to* the matching data dir, e.g. data/processed/exp/a → exp/a."""
    for d in data_dirs:
        if d in rel_path.parents:
            return rel_path.relative_to(d)
    return None


def _workflow_slug_from_siblings(project_root: Path, rel_path: Path) -> str | None:
    """Inspect a sibling datapackage for an explicit `workflow:` field only.

    Resolution step 1. The `name` field (`<workflow-slug>-<run>-<out>`) is NOT parsed:
    workflow slugs themselves contain hyphens, so the segment boundaries are ambiguous
    from the string alone. Without an explicit `workflow:` field we fall back to the
    first path segment (step 2 in the caller).
    """
    sib_dir = (project_root / rel_path).parent
    for name in ("datapackage.yaml", "datapackage.json"):
        dp_path = sib_dir / name
        if not dp_path.is_file():
            continue
        try:
            dp = yaml.safe_load(dp_path.read_text(encoding="utf-8")) or {}
        except (yaml.YAMLError, OSError):
            continue
        if isinstance(dp, dict):
            wf = dp.get("workflow")
            if isinstance(wf, str) and wf:
                return wf.removeprefix("workflow:")
    return None


def propose_results_target(
    project_root: Path, rel_path: Path, data_dirs: tuple[Path, ...]
) -> str | None:
    """results/<nearest-exp-or-workflow>/<substructure-beneath-segment>."""
    sub = _data_subpath(rel_path, data_dirs)
    if sub is None or not sub.parts:
        return None
    slug = _workflow_slug_from_siblings(project_root, rel_path) or sub.parts[0]
    beneath = Path(*sub.parts[1:]) if len(sub.parts) > 1 else Path(sub.name)
    return (Path("results") / slug / beneath).as_posix()


def _iter_project_files(project_root: Path, data_dirs: tuple[Path, ...]):
    """Yield (abs_path, rel_path) for project files.

    The real tree is walked without following symlinks; symlinked dirs whose realpath
    escapes project_root are pruned (avoids scanning arbitrary external trees / loops).
    A *DEFAULT_DATA_DIRS* entry that is itself a symlink (the data_worktree hydration
    case) is a known, bounded payload dir, so it gets a supplementary follow-links scan
    — its records must still be *reported* (the fixer FLAGs rather than moves them)."""
    seen: set[str] = set()
    for dirpath, dirnames, filenames in os.walk(project_root):
        dirnames[:] = [
            d for d in dirnames
            if d != ".git" and not _escapes_root(project_root, Path(dirpath) / d)
        ]
        for fn in filenames:
            abs_path = Path(dirpath) / fn
            if abs_path.is_symlink():
                continue
            rel = abs_path.relative_to(project_root)
            seen.add(rel.as_posix())
            yield abs_path, rel
    # Supplementary: symlinked known data dirs (not descended above).
    for d in data_dirs:
        entry = project_root / d
        if not (entry.is_symlink() and entry.is_dir()):
            continue
        for dirpath, _dirnames, filenames in os.walk(entry, followlinks=True):
            for fn in filenames:
                abs_path = Path(dirpath) / fn
                rel = abs_path.relative_to(project_root)
                if rel.as_posix() in seen:
                    continue
                seen.add(rel.as_posix())
                yield abs_path, rel


def audit_project(
    project_root: Path,
    policy: DataPolicy = DEFAULT_DATA_POLICY,
    data_dirs: tuple[Path, ...] = DEFAULT_DATA_DIRS,
) -> list[Violation]:
    tracked = git_tracked_set(project_root)
    violations: list[Violation] = []
    for abs_path, rel in _iter_project_files(project_root, data_dirs):
        try:
            size = abs_path.stat().st_size
        except OSError:
            continue
        cls = classify(rel, size, policy)
        loc = location(rel, data_dirs)
        is_tracked = rel.as_posix() in tracked
        v = _violation_for(project_root, rel, cls, loc, is_tracked, data_dirs)
        if v is not None:
            violations.append(v)
    violations.sort(key=lambda v: v.path)
    return violations


def _violation_for(project_root, rel, cls, loc, is_tracked, data_dirs) -> Violation | None:
    if cls is FileClass.RECORD and loc == "DATA":
        return Violation(
            Quadrant.STRANDED_RECORD, rel.as_posix(), cls,
            propose_results_target(project_root, rel, data_dirs),
        )
    if cls is FileClass.PAYLOAD and is_tracked and loc != "DATA":
        return Violation(
            Quadrant.LEAKED_PAYLOAD, rel.as_posix(), cls, "data/processed/" + rel.name,
        )
    if cls is FileClass.FLAG:
        return Violation(Quadrant.FLAG, rel.as_posix(), cls, None)
    return None


def _escapes_root(project_root: Path, candidate: Path) -> bool:
    """True if candidate is a symlink whose realpath is outside project_root."""
    if not candidate.is_symlink():
        return False
    try:
        real = candidate.resolve()
        root = project_root.resolve()
        return root != real and root not in real.parents
    except OSError:
        return True


_DATAPACKAGE_NAMES = ("datapackage.yaml", "datapackage.json")


def _planned_action(v: Violation) -> str:
    """The action the fixer *would* take, for read-only report parity with --fix."""
    if v.quadrant is Quadrant.STRANDED_RECORD:
        if Path(v.path).name in _DATAPACKAGE_NAMES:
            return "move+rewrite-resources"
        return "move"
    return "flag"  # leaked_payload, flag → never auto-acted


def render_json(violations: list[Violation], outcomes: "list | None" = None) -> str:
    """Stable contract. In read-only mode (outcomes is None) performed is always False
    and `action` reports the *planned* action, matching what --fix would attempt."""
    by_path = {o.violation.path: o for o in (outcomes or [])}
    rows = []
    for v in violations:
        o = by_path.get(v.path)
        row = {
            "quadrant": v.quadrant.value,
            "path": v.path,
            "class": v.file_class.value,
            "action": (o.action if o else _planned_action(v)),
            "target": v.proposed_target,
            "performed": bool(o.performed) if o else False,
        }
        if o is not None and o.basepath is not None:
            row["basepath"] = o.basepath
        if o is not None and o.rewritten_resources is not None:
            row["rewritten_resources"] = o.rewritten_resources
        rows.append(row)
    return json.dumps({"version": 1, "violations": rows}, indent=2) + "\n"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/d/science/science && uv run --no-sync pytest tests/test_data_audit.py -v`
Expected: PASS (9 tests).

- [ ] **Step 5: Commit**

```bash
cd ~/d/science/science
git add src/science_tool/data_audit.py tests/test_data_audit.py
git commit -m "feat(data): add data-audit detection pass and --json contract"
```

---

### Task 4: `data_audit_fix.py` — move semantics (no datapackage rewrite yet)

**Files:**
- Create: `science/src/science_tool/data_audit_fix.py`
- Test: `science/tests/test_data_audit_fix.py`

**Interfaces:**
- Consumes: `Violation`, `Quadrant` (Task 3).
- Produces:
  - `@dataclass class FixOutcome` with `violation: Violation`, `performed: bool`, `action: str`, `rewritten_resources: list[dict] | None = None`, `basepath: str | None = None`, `reason: str | None = None`.
  - `def apply_fixes(project_root: Path, violations: list[Violation]) -> list[FixOutcome]`.

  Move semantics: tracked source → `git mv`; untracked source → filesystem move + `git add <target>`; end state = target staged, source gone, **no commit**. Collision (destination exists, different content) → FLAG. `LEAKED_PAYLOAD` and `FLAG` quadrants → never moved (action `"flag"`, performed `False`).

- [ ] **Step 1: Write the failing tests**

```python
# science/tests/test_data_audit_fix.py
"""Conservative fixer for `science data audit --fix`."""
import subprocess
from pathlib import Path

from science_tool.data_audit import Quadrant, audit_project
from science_tool.data_audit_fix import apply_fixes


def _init_repo(root: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=root, check=True)


def _write(root: Path, rel: str, content: bytes = b"x") -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(content)
    return p


def _staged(root: Path) -> set[str]:
    out = subprocess.run(
        ["git", "diff", "--cached", "--name-only"], cwd=root,
        capture_output=True, text=True, check=True,
    ).stdout
    return {ln for ln in out.splitlines() if ln}


def test_untracked_stranded_record_moves_and_stages(tmp_path: Path):
    _init_repo(tmp_path)
    _write(tmp_path, "data/processed/exp1/RESULTS.md", b"# r\n")
    outcomes = apply_fixes(tmp_path, audit_project(tmp_path))
    moved = [o for o in outcomes if o.violation.quadrant is Quadrant.STRANDED_RECORD]
    assert moved and moved[0].performed and moved[0].action == "move"
    assert not (tmp_path / "data/processed/exp1/RESULTS.md").exists()
    assert (tmp_path / "results/exp1/RESULTS.md").read_text() == "# r\n"
    assert "results/exp1/RESULTS.md" in _staged(tmp_path)


def test_fix_does_not_commit(tmp_path: Path):
    _init_repo(tmp_path)
    _write(tmp_path, "data/processed/exp1/RESULTS.md", b"# r\n")
    apply_fixes(tmp_path, audit_project(tmp_path))
    log = subprocess.run(["git", "log", "--oneline"], cwd=tmp_path,
                         capture_output=True, text=True)
    assert log.stdout.strip() == ""  # nothing committed


def test_tracked_stranded_record_uses_git_mv(tmp_path: Path):
    _init_repo(tmp_path)
    _write(tmp_path, "data/processed/exp1/RESULTS.md", b"# r\n")
    subprocess.run(["git", "add", "-f", "data/processed/exp1/RESULTS.md"],
                   cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "seed"], cwd=tmp_path, check=True)
    apply_fixes(tmp_path, audit_project(tmp_path))
    assert (tmp_path / "results/exp1/RESULTS.md").exists()
    assert "results/exp1/RESULTS.md" in _staged(tmp_path)


def test_collision_different_content_flags(tmp_path: Path):
    _init_repo(tmp_path)
    _write(tmp_path, "data/processed/exp1/RESULTS.md", b"NEW\n")
    _write(tmp_path, "results/exp1/RESULTS.md", b"EXISTING\n")
    outcomes = apply_fixes(tmp_path, audit_project(tmp_path))
    o = [o for o in outcomes if o.violation.quadrant is Quadrant.STRANDED_RECORD][0]
    assert o.performed is False and o.action == "flag"
    assert (tmp_path / "data/processed/exp1/RESULTS.md").exists()  # not moved


def test_leaked_payload_never_moved(tmp_path: Path):
    _init_repo(tmp_path)
    _write(tmp_path, "entities/x/big.feather", b"\x00" * 8)
    subprocess.run(["git", "add", "-f", "entities/x/big.feather"], cwd=tmp_path, check=True)
    outcomes = apply_fixes(tmp_path, audit_project(tmp_path))
    o = [o for o in outcomes if o.violation.quadrant is Quadrant.LEAKED_PAYLOAD][0]
    assert o.performed is False and o.action == "flag"
    assert (tmp_path / "entities/x/big.feather").exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/d/science/science && uv run --no-sync pytest tests/test_data_audit_fix.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'science_tool.data_audit_fix'`.

- [ ] **Step 3: Write the implementation**

```python
# science/src/science_tool/data_audit_fix.py
"""Conservative fixer for `science data audit --fix`.

Only one automatic move direction: a stranded RECORD out of ignored data/ into
tracked results/. Leaked payloads and anything ambiguous → FLAG (never moved).
End state of a performed move: the target exists under results/ and is staged; the
source is gone; nothing is committed. See docs/plans/2026-06-28-data-audit-design.md.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from science_tool.data_audit import Quadrant, Violation


@dataclass
class FixOutcome:
    violation: Violation
    performed: bool
    action: str  # "move" | "move+rewrite-resources" | "flag"
    rewritten_resources: list[dict] | None = None
    basepath: str | None = None
    reason: str | None = None


def _git(project_root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(project_root), *args], check=True,
                   capture_output=True)


def _is_tracked(project_root: Path, rel: str) -> bool:
    res = subprocess.run(
        ["git", "-C", str(project_root), "ls-files", "--error-unmatch", rel],
        capture_output=True,
    )
    return res.returncode == 0


def _flag(v: Violation, reason: str) -> FixOutcome:
    return FixOutcome(v, performed=False, action="flag", reason=reason)


def _move_record(project_root: Path, v: Violation) -> FixOutcome:
    if v.proposed_target is None:
        return _flag(v, "no target could be proposed")
    src = project_root / v.path
    dst = project_root / v.proposed_target
    if dst.exists():
        if dst.read_bytes() == src.read_bytes():
            # Identical content already present; drop the stranded copy. If the source
            # was force-added (tracked), stage the deletion via git rm so we don't leave
            # an unstaged delete; otherwise a plain unlink suffices.
            if _is_tracked(project_root, v.path):
                _git(project_root, "rm", "-q", "-f", v.path)
            else:
                src.unlink()
            return FixOutcome(v, performed=True, action="move", reason="deduped")
        return _flag(v, f"destination exists with different content: {v.proposed_target}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    if _is_tracked(project_root, v.path):
        _git(project_root, "mv", v.path, v.proposed_target)
    else:
        shutil.move(str(src), str(dst))
        _git(project_root, "add", v.proposed_target)
    return FixOutcome(v, performed=True, action="move")


def apply_fixes(project_root: Path, violations: list[Violation]) -> list[FixOutcome]:
    outcomes: list[FixOutcome] = []
    for v in violations:
        if v.quadrant is Quadrant.STRANDED_RECORD:
            outcomes.append(_move_record(project_root, v))
        else:  # LEAKED_PAYLOAD, FLAG → never auto-acted
            outcomes.append(_flag(v, "reported only; author decides"))
    return outcomes
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/d/science/science && uv run --no-sync pytest tests/test_data_audit_fix.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
cd ~/d/science/science
git add src/science_tool/data_audit_fix.py tests/test_data_audit_fix.py
git commit -m "feat(data): add conservative --fix move semantics"
```

---

### Task 5: datapackage resource-path rewrite (preserve `basepath`)

**Files:**
- Modify: `science/src/science_tool/data_audit_fix.py` (special-case `datapackage.{yaml,json}` inside `_move_record`)
- Test: `science/tests/test_data_audit_fix_datapackage.py`

**Interfaces:**
- Consumes: `FixOutcome`, `_move_record` plumbing (Task 4).
- Produces: when the moved record is a `datapackage.{yaml,json}`, the written target has each `resources[].path` recomputed so `new_descriptor.parent / basepath / path` resolves to the original payload; `action="move+rewrite-resources"`, `basepath` and `rewritten_resources` populated. FLAG (descriptor not moved) if any resource `path`/`basepath` is absolute, escapes the repo, or the target payload is missing.
- Add helper `def _rewrite_datapackage(project_root, src_rel, dst_rel) -> tuple[str, str | None, list[dict]] | None` returning `(yaml_text, basepath, rewritten)` or `None` to signal FLAG.

- [ ] **Step 1: Write the failing tests**

```python
# science/tests/test_data_audit_fix_datapackage.py
"""Datapackage resource-path rewrite on relocation."""
import os
import subprocess
from pathlib import Path

import yaml

from science_tool.data_audit import audit_project
from science_tool.data_audit_fix import apply_fixes


def _init_repo(root: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=root, check=True)


def _write(root: Path, rel: str, content: bytes) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(content)
    return p


def _resolves_to(root: Path, descriptor_rel: str, dp: dict, payload_rel: str) -> bool:
    base = (root / descriptor_rel).parent / dp.get("basepath", ".")
    target = (base / dp["resources"][0]["path"]).resolve()
    return target == (root / payload_rel).resolve()


def test_rewrite_preserves_resolution_no_basepath(tmp_path: Path):
    _init_repo(tmp_path)
    _write(tmp_path, "data/processed/exp1/matrix.feather", b"\x00" * 8)  # payload stays
    _write(tmp_path, "data/processed/exp1/datapackage.yaml",
           yaml.safe_dump({
               "name": "exp1-pkg",
               "resources": [{"name": "matrix", "path": "matrix.feather"}],
           }).encode())
    apply_fixes(tmp_path, audit_project(tmp_path))
    moved = tmp_path / "results/exp1/datapackage.yaml"
    assert moved.exists()
    dp = yaml.safe_load(moved.read_text())
    # payload did NOT move; descriptor now reaches back into data/.
    assert (tmp_path / "data/processed/exp1/matrix.feather").exists()
    assert _resolves_to(tmp_path, "results/exp1/datapackage.yaml", dp,
                        "data/processed/exp1/matrix.feather")


def test_rewrite_preserves_existing_basepath(tmp_path: Path):
    _init_repo(tmp_path)
    _write(tmp_path, "data/processed/exp1/matrix.feather", b"\x00" * 8)
    _write(tmp_path, "data/processed/exp1/out/datapackage.yaml",
           yaml.safe_dump({
               "name": "exp1-r1-out",
               "basepath": "..",
               "resources": [{"name": "matrix", "path": "matrix.feather"}],
           }).encode())
    apply_fixes(tmp_path, audit_project(tmp_path))
    moved = tmp_path / "results/exp1/out/datapackage.yaml"
    assert moved.exists()
    dp = yaml.safe_load(moved.read_text())
    assert dp["basepath"] == ".."  # preserved
    assert _resolves_to(tmp_path, "results/exp1/out/datapackage.yaml", dp,
                        "data/processed/exp1/matrix.feather")


def test_absolute_resource_path_flags(tmp_path: Path):
    _init_repo(tmp_path)
    _write(tmp_path, "data/processed/exp1/datapackage.yaml",
           yaml.safe_dump({
               "name": "x",
               "resources": [{"name": "m", "path": "/abs/matrix.feather"}],
           }).encode())
    outcomes = apply_fixes(tmp_path, audit_project(tmp_path))
    o = [o for o in outcomes if o.violation.path.endswith("datapackage.yaml")][0]
    assert o.performed is False and o.action == "flag"
    assert (tmp_path / "data/processed/exp1/datapackage.yaml").exists()  # not moved


def test_json_descriptor_stays_json(tmp_path: Path):
    import json as _json
    _init_repo(tmp_path)
    _write(tmp_path, "data/processed/exp1/matrix.feather", b"\x00" * 8)
    _write(tmp_path, "data/processed/exp1/datapackage.json",
           _json.dumps({"name": "x",
                        "resources": [{"name": "m", "path": "matrix.feather"}]}).encode())
    apply_fixes(tmp_path, audit_project(tmp_path))
    moved = tmp_path / "results/exp1/datapackage.json"
    assert moved.exists()
    dp = _json.loads(moved.read_text())  # still valid JSON, not YAML
    assert _resolves_to(tmp_path, "results/exp1/datapackage.json", dp,
                        "data/processed/exp1/matrix.feather")


def test_malformed_resource_entry_flags(tmp_path: Path):
    _init_repo(tmp_path)
    _write(tmp_path, "data/processed/exp1/datapackage.yaml",
           b"name: x\nresources:\n- just-a-string\n")
    outcomes = apply_fixes(tmp_path, audit_project(tmp_path))
    o = [o for o in outcomes if o.violation.path.endswith("datapackage.yaml")][0]
    assert o.performed is False and o.action == "flag"  # FLAG, did not crash


def test_basepath_escaping_repo_flags(tmp_path: Path):
    # Descriptor one level under data/processed; basepath "../../../.." escapes the repo.
    _init_repo(tmp_path)
    _write(tmp_path, "data/processed/exp1/datapackage.yaml",
           yaml.safe_dump({
               "name": "x",
               "basepath": "../../../..",
               "resources": [{"name": "m", "path": "matrix.feather"}],
           }).encode())
    outcomes = apply_fixes(tmp_path, audit_project(tmp_path))
    o = [o for o in outcomes if o.violation.path.endswith("datapackage.yaml")][0]
    assert o.performed is False and o.action == "flag"
    assert (tmp_path / "data/processed/exp1/datapackage.yaml").exists()  # not moved
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/d/science/science && uv run --no-sync pytest tests/test_data_audit_fix_datapackage.py -v`
Expected: FAIL — `move+rewrite-resources` not implemented; descriptor moved without rewrite, resolution assert fails.

- [ ] **Step 3: Write the implementation**

In `science/src/science_tool/data_audit_fix.py`, add imports at the top:

```python
import json
import os
import yaml
```

Add this helper (after `_flag`):

```python
def _norm(*parts: str) -> str:
    return os.path.normpath(os.path.join(*parts))


def _rewrite_datapackage(
    project_root: Path, src_rel: str, dst_rel: str
) -> tuple[str, str | None, list[dict]] | None:
    """Return (text, basepath, rewritten) for the relocated descriptor, or None to
    signal FLAG (unresolvable / malformed). Preserves basepath AND the source
    serialization format (.json stays JSON, .yaml stays YAML); recomputes
    resources[].path against the effective resource base so resolution is invariant
    under the move."""
    is_json = src_rel.endswith(".json")
    try:
        raw = (project_root / src_rel).read_text(encoding="utf-8")
        dp = (json.loads(raw) if is_json else yaml.safe_load(raw)) or {}
    except (yaml.YAMLError, ValueError, OSError):
        return None
    if not isinstance(dp, dict):
        return None
    basepath = dp.get("basepath")
    if basepath is not None and (not isinstance(basepath, str) or os.path.isabs(basepath)):
        return None
    resources = dp.get("resources")
    if resources is not None and not isinstance(resources, list):
        return None
    src_dir = os.path.dirname(src_rel)
    dst_dir = os.path.dirname(dst_rel)
    old_base = _norm(src_dir, basepath or ".")
    new_base = _norm(dst_dir, basepath or ".")
    # A relative basepath can still resolve outside the repo (e.g. "../.." from a
    # shallow descriptor). Both effective bases must stay within project_root, else FLAG.
    if old_base.startswith("..") or new_base.startswith(".."):
        return None
    rewritten: list[dict] = []
    for res in resources or []:
        if not isinstance(res, dict):
            return None  # malformed resource entry → FLAG, never crash
        path = res.get("path")
        if not isinstance(path, str) or os.path.isabs(path):
            return None
        payload_rel = _norm(old_base, path)             # repo-relative payload
        if payload_rel.startswith(".."):                # escapes repo
            return None
        if not (project_root / payload_rel).exists():   # payload missing
            return None
        new_path = os.path.relpath(payload_rel, new_base)
        # Round-trip safety: resolution must be invariant under the move.
        if _norm(new_base, new_path) != payload_rel:
            return None
        res["path"] = new_path
        rewritten.append({"name": res.get("name"), "from": path, "to": new_path})
    text = (json.dumps(dp, indent=2) + "\n") if is_json else yaml.safe_dump(dp, sort_keys=False)
    return text, basepath, rewritten
```

Replace the move body of `_move_record` (after the collision check, where it currently does the `git mv` / `shutil.move`) so a datapackage is rewritten before staging. Change the final block of `_move_record` to:

```python
    dst.parent.mkdir(parents=True, exist_ok=True)
    is_dp = src.name in ("datapackage.yaml", "datapackage.json")
    if is_dp:
        rewrite = _rewrite_datapackage(project_root, v.path, v.proposed_target)
        if rewrite is None:
            return _flag(v, "datapackage resources not structurally rewritable")
        text, basepath, rewritten = rewrite
        if _is_tracked(project_root, v.path):
            _git(project_root, "rm", "-q", "--cached", v.path)
            (project_root / v.path).unlink()
        else:
            src.unlink()
        dst.write_text(text, encoding="utf-8")
        _git(project_root, "add", v.proposed_target)
        return FixOutcome(v, performed=True, action="move+rewrite-resources",
                          rewritten_resources=rewritten, basepath=basepath)
    if _is_tracked(project_root, v.path):
        _git(project_root, "mv", v.path, v.proposed_target)
    else:
        shutil.move(str(src), str(dst))
        _git(project_root, "add", v.proposed_target)
    return FixOutcome(v, performed=True, action="move")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/d/science/science && uv run --no-sync pytest tests/test_data_audit_fix_datapackage.py tests/test_data_audit_fix.py -v`
Expected: PASS (6 datapackage tests + Task 4's 5 move tests, all green).

- [ ] **Step 5: Commit**

```bash
cd ~/d/science/science
git add src/science_tool/data_audit_fix.py tests/test_data_audit_fix_datapackage.py
git commit -m "feat(data): rewrite datapackage resource paths on relocation"
```

---

### Task 6: symlink-hydrated `data/` fix guard

**Files:**
- Modify: `science/src/science_tool/data_audit_fix.py` (`_move_record` refuses moves through symlinked data dirs)
- Test: `science/tests/test_data_audit_symlink.py`

**Interfaces:**
- Consumes: `_move_record` (Tasks 4-5).
- Produces: a stranded record whose source path traverses a symlinked `DEFAULT_DATA_DIRS` entry (or whose real path escapes `project_root`) → FLAG, not moved. `apply_fixes` gains a `data_dirs: tuple[Path, ...] = DEFAULT_DATA_DIRS` parameter passed through to the guard.

- [ ] **Step 1: Write the failing test**

```python
# science/tests/test_data_audit_symlink.py
"""--fix must not move records out of a symlink-hydrated data dir."""
import subprocess
from pathlib import Path

from science_tool.data_audit import Quadrant, audit_project
from science_tool.data_audit_fix import apply_fixes


def _init_repo(root: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=root, check=True)


def test_record_under_symlinked_data_dir_is_flagged(tmp_path: Path):
    _init_repo(tmp_path)
    # External shared source root (outside the project) holds the real file.
    external = tmp_path.parent / "external_source"
    (external / "processed" / "exp1").mkdir(parents=True, exist_ok=True)
    (external / "processed" / "exp1" / "RESULTS.md").write_text("# r\n")
    # data/processed is a symlink into the external source (data_worktree hydration).
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "processed").symlink_to(external / "processed")

    violations = audit_project(tmp_path)
    stranded = [v for v in violations if v.quadrant is Quadrant.STRANDED_RECORD]
    # Reported: the record under the symlinked data dir IS surfaced.
    assert any(v.path == "data/processed/exp1/RESULTS.md" for v in stranded)
    # Fixed: but --fix FLAGs it (never moves through the symlink).
    outcomes = apply_fixes(tmp_path, violations)
    moved = [o for o in outcomes
             if o.violation.path == "data/processed/exp1/RESULTS.md"][0]
    assert moved.performed is False and moved.action == "flag"
    assert "symlink" in (moved.reason or "")
    # The real external file is untouched; no results/ copy was created.
    assert (external / "processed" / "exp1" / "RESULTS.md").exists()
    assert not (tmp_path / "results" / "exp1" / "RESULTS.md").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/d/science/science && uv run --no-sync pytest tests/test_data_audit_symlink.py -v`
Expected: FAIL — `apply_fixes()` has no `data_dirs` parameter / the record is moved.

- [ ] **Step 3: Write the implementation**

In `science/src/science_tool/data_audit_fix.py`, add the import:

```python
from science_tool.data_worktree import DEFAULT_DATA_DIRS
```

Add this guard helper (after `_norm`):

```python
def _traverses_symlinked_data_dir(
    project_root: Path, rel: str, data_dirs: tuple[Path, ...]
) -> bool:
    """True if any ancestor of rel within a data dir is a symlink, or rel's real path
    escapes project_root — i.e. moving it would mutate a shared/external source."""
    rel_path = Path(rel)
    in_data = any(d in rel_path.parents for d in data_dirs)
    if not in_data:
        return False
    cur = project_root
    for part in rel_path.parts[:-1]:
        cur = cur / part
        if cur.is_symlink():
            return True
    try:
        real = (project_root / rel_path).resolve()
        root = project_root.resolve()
        if root != real and root not in real.parents:
            return True
    except OSError:
        return True
    return False
```

Thread `data_dirs` through and guard at the top of `_move_record`. Replace the **entire**
`_move_record` function (from Tasks 4-5) with this final version — it adds the `data_dirs`
parameter and the symlink guard, and keeps the dedupe, collision, datapackage-rewrite, and
move branches intact:

```python
def _move_record(
    project_root: Path, v: Violation, data_dirs: tuple[Path, ...]
) -> FixOutcome:
    if _traverses_symlinked_data_dir(project_root, v.path, data_dirs):
        return _flag(v, "source is under a symlinked data dir; move would mutate shared source")
    if v.proposed_target is None:
        return _flag(v, "no target could be proposed")
    src = project_root / v.path
    dst = project_root / v.proposed_target
    if dst.exists():
        if dst.read_bytes() == src.read_bytes():
            if _is_tracked(project_root, v.path):
                _git(project_root, "rm", "-q", "-f", v.path)
            else:
                src.unlink()
            return FixOutcome(v, performed=True, action="move", reason="deduped")
        return _flag(v, f"destination exists with different content: {v.proposed_target}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    is_dp = src.name in ("datapackage.yaml", "datapackage.json")
    if is_dp:
        rewrite = _rewrite_datapackage(project_root, v.path, v.proposed_target)
        if rewrite is None:
            return _flag(v, "datapackage resources not structurally rewritable")
        text, basepath, rewritten = rewrite
        if _is_tracked(project_root, v.path):
            _git(project_root, "rm", "-q", "--cached", v.path)
            (project_root / v.path).unlink()
        else:
            src.unlink()
        dst.write_text(text, encoding="utf-8")
        _git(project_root, "add", v.proposed_target)
        return FixOutcome(v, performed=True, action="move+rewrite-resources",
                          rewritten_resources=rewritten, basepath=basepath)
    if _is_tracked(project_root, v.path):
        _git(project_root, "mv", v.path, v.proposed_target)
    else:
        shutil.move(str(src), str(dst))
        _git(project_root, "add", v.proposed_target)
    return FixOutcome(v, performed=True, action="move")
```

Update `apply_fixes`:

```python
def apply_fixes(
    project_root: Path,
    violations: list[Violation],
    data_dirs: tuple[Path, ...] = DEFAULT_DATA_DIRS,
) -> list[FixOutcome]:
    outcomes: list[FixOutcome] = []
    for v in violations:
        if v.quadrant is Quadrant.STRANDED_RECORD:
            outcomes.append(_move_record(project_root, v, data_dirs))
        else:
            outcomes.append(_flag(v, "reported only; author decides"))
    return outcomes
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/d/science/science && uv run --no-sync pytest tests/test_data_audit_symlink.py tests/test_data_audit_fix.py tests/test_data_audit_fix_datapackage.py -v`
Expected: PASS (all fixer tests green; the new `data_dirs` default keeps Task 4-5 callers working).

- [ ] **Step 5: Commit**

```bash
cd ~/d/science/science
git add src/science_tool/data_audit_fix.py tests/test_data_audit_symlink.py
git commit -m "feat(data): guard --fix against symlink-hydrated data dirs"
```

---

### Task 7: CLI wiring — `science data audit`

**Files:**
- Modify: `science/src/science_tool/cli.py` (new `data` group + `audit` command; register with `main.add_command` or `@main.group`)
- Test: `science/tests/test_data_audit_cli.py`

**Interfaces:**
- Consumes: `audit_project`, `render_json`, `Quadrant` (Task 3); `apply_fixes` (Tasks 4-6); `load_project_config`, `resolve_data_policy` (Task 2).
- Produces: `science data audit [--project PATH] [--fix] [--json]`. Read-only: human report (or `--json`), exit code `1` when violations exist, `0` when clean. `--fix`: applies fixes, prints performed/flagged summary (or `--json` with `performed` flags), exit code `0`. Honors `SCIENCE_PROJECT_ROOT` env like sibling commands (via the default project path).

- [ ] **Step 1: Write the failing tests**

```python
# science/tests/test_data_audit_cli.py
"""CLI surface for `science data audit`."""
import json
import subprocess
from pathlib import Path

from click.testing import CliRunner

from science_tool.cli import main as science_cli


def _init_repo(root: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=root, check=True)


def _write(root: Path, rel: str, content: bytes = b"x") -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(content)


def _run(tmp_path: Path, *args: str):
    return CliRunner().invoke(
        science_cli, ["data", "audit", "--project", str(tmp_path), *args],
        catch_exceptions=False,
    )


def test_audit_reports_violation_nonzero_exit(tmp_path: Path):
    _init_repo(tmp_path)
    _write(tmp_path, "data/processed/exp1/RESULTS.md", b"# r\n")
    res = _run(tmp_path)
    assert res.exit_code == 1
    assert "stranded_record" in res.output or "RESULTS.md" in res.output


def test_audit_clean_zero_exit(tmp_path: Path):
    _init_repo(tmp_path)
    _write(tmp_path, "results/exp1/RESULTS.md", b"# r\n")
    res = _run(tmp_path)
    assert res.exit_code == 0


def test_audit_json_contract(tmp_path: Path):
    _init_repo(tmp_path)
    _write(tmp_path, "data/processed/exp1/RESULTS.md", b"# r\n")
    res = _run(tmp_path, "--json")
    payload = json.loads(res.output)
    assert payload["version"] == 1
    assert payload["violations"][0]["target"] == "results/exp1/RESULTS.md"
    assert payload["violations"][0]["performed"] is False


def test_fix_moves_and_reports_performed(tmp_path: Path):
    _init_repo(tmp_path)
    _write(tmp_path, "data/processed/exp1/RESULTS.md", b"# r\n")
    res = _run(tmp_path, "--fix", "--json")
    assert res.exit_code == 0
    payload = json.loads(res.output)
    assert payload["violations"][0]["performed"] is True
    assert (tmp_path / "results/exp1/RESULTS.md").exists()


def test_honors_science_project_root_env(tmp_path: Path):
    _init_repo(tmp_path)
    _write(tmp_path, "data/processed/exp1/RESULTS.md", b"# r\n")
    # No --project flag; resolution comes from the env var.
    res = CliRunner().invoke(
        science_cli, ["data", "audit", "--json"],
        env={"SCIENCE_PROJECT_ROOT": str(tmp_path)}, catch_exceptions=False,
    )
    payload = json.loads(res.output)
    assert payload["violations"][0]["target"] == "results/exp1/RESULTS.md"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/d/science/science && uv run --no-sync pytest tests/test_data_audit_cli.py -v`
Expected: FAIL — `Error: No such command 'data'`.

- [ ] **Step 3: Write the implementation**

In `science/src/science_tool/cli.py`, add imports near the other `science_tool` imports:

```python
from science_tool.data_audit import audit_project, render_json
from science_tool.data_audit_fix import apply_fixes
from science_tool.project_config import load_project_config, resolve_data_policy
```

Add the group + command (place near the `entities` group definitions):

```python
@main.group("data")
def data_group() -> None:
    """Audit the data/results/entities tracking boundary."""


@data_group.command("audit")
@click.option("--project", "project_path", type=click.Path(path_type=Path),
              default=None, envvar="SCIENCE_PROJECT_ROOT",
              help="Project root (defaults to $SCIENCE_PROJECT_ROOT or cwd).")
@click.option("--fix", is_flag=True, default=False,
              help="Relocate stranded records data/ → results/ (stages, never commits).")
@click.option("--json", "as_json", is_flag=True, default=False,
              help="Emit the machine-readable move report.")
def data_audit_command(project_path: Path | None, fix: bool, as_json: bool) -> None:
    """Report (and optionally fix) data/results/entities boundary violations."""
    project_path = project_path or Path.cwd()  # runtime default; honors the env var above
    try:
        policy = resolve_data_policy(load_project_config(project_path))
    except FileNotFoundError:
        from science_tool.data_policy import DEFAULT_DATA_POLICY
        policy = DEFAULT_DATA_POLICY
    violations = audit_project(project_path, policy)

    if fix:
        outcomes = apply_fixes(project_path, violations)
        if as_json:
            click.echo(render_json(violations, outcomes), nl=False)
        else:
            performed = sum(1 for o in outcomes if o.performed)
            flagged = sum(1 for o in outcomes if not o.performed)
            for o in outcomes:
                mark = "moved" if o.performed else "FLAG"
                tgt = o.violation.proposed_target or "-"
                click.echo(f"  [{mark}] {o.violation.path} → {tgt}"
                           + (f"  ({o.reason})" if o.reason else ""))
            click.echo(f"\n{performed} moved (staged, not committed), {flagged} flagged.")
        return

    if as_json:
        click.echo(render_json(violations), nl=False)
    else:
        if not violations:
            click.echo("clean: no data/results boundary violations.")
        for v in violations:
            tgt = v.proposed_target or "-"
            click.echo(f"  [{v.quadrant.value}] {v.path} → {tgt}")
    if violations and not fix:
        raise SystemExit(1)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/d/science/science && uv run --no-sync pytest tests/test_data_audit_cli.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Run the full new-module suite together**

Run: `cd ~/d/science/science && uv run --no-sync pytest tests/test_data_policy.py tests/test_data_policy_config.py tests/test_data_audit.py tests/test_data_audit_fix.py tests/test_data_audit_fix_datapackage.py tests/test_data_audit_symlink.py tests/test_data_audit_cli.py -v`
Expected: PASS (all green).

- [ ] **Step 6: Lint the new modules (catch unused imports / F401)**

Run: `cd ~/d/science/science && uv run --no-sync ruff check src/science_tool/data_policy.py src/science_tool/data_audit.py src/science_tool/data_audit_fix.py src/science_tool/project_config.py src/science_tool/cli.py`
Expected: no errors (`All checks passed!`). Fix any `F401` unused-import / other ruff findings before committing.

- [ ] **Step 7: Commit**

```bash
cd ~/d/science/science
git add src/science_tool/cli.py tests/test_data_audit_cli.py
git commit -m "feat(data): wire science data audit CLI command"
```

---

## Self-Review

**Spec coverage:**
- Boundary model (data/entities/results) → enforced by `location()` (Task 3) + move direction (Tasks 4-6). ✔
- `data_policy.py` SSOT + conservative decision table → Task 1. ✔
- `data_policy:` science.yaml override → Task 2. ✔
- New top-level `data` group (not under `datasets`) → Task 7. ✔
- Quadrants (STRANDED_RECORD / LEAKED_PAYLOAD / FLAG) → Task 3. ✔
- `--json` stable contract incl. `basepath`/`rewritten_resources` → Task 3 (`render_json`) + Task 5. ✔ Read-only mode reports the *planned* action (`_planned_action`: stranded→`move`, datapackage→`move+rewrite-resources`), not a blanket `flag`. ✔
- `--fix` move semantics (tracked git mv / untracked fs-move+add, staged, no commit) → Task 4. ✔
- `<nearest-exp-or-workflow>` ordered resolution → Task 3 (`propose_results_target`). ✔
- Datapackage rewrite preserving basepath + round-trip + FLAG → Task 5. ✔
- LEAKED_PAYLOAD → FLAG only → Task 4. ✔
- Symlink behaviour → Task 3: general escaping symlinks pruned (`_escapes_root`), but a symlinked `DEFAULT_DATA_DIRS` entry gets a supplementary scan so its records are **reported** (`_iter_project_files`); Task 6 fix **refuses** to move them (FLAG). Reported-not-fixed, per the design footnote. ✔
- Datapackage format preserved on rewrite (`.json` stays JSON, `.yaml` stays YAML) + malformed `resources` → FLAG not crash → Task 5. ✔
- `<nearest-exp-or-workflow>` = explicit `workflow:` field → first path segment (the hyphen-ambiguous `name`-prefix heuristic was dropped) → Task 3. ✔
- CLI honors `SCIENCE_PROJECT_ROOT` (envvar + runtime cwd default) → Task 7. ✔
- Nonzero exit on violations → Task 7. ✔
- Deferred items (size-guard hook, validate-warn, health orphan check, migrate-payloads, project-root-relative paths) → not implemented (correct). ✔

**Placeholder scan:** No TBD/TODO; every code step shows full code. ✔

**Type consistency:** `Violation`/`Quadrant`/`FileClass`/`FixOutcome`/`DataPolicy` names and signatures are consistent across Tasks 1-7; `apply_fixes` gains `data_dirs` in Task 6 with a default so Task 4-5 call sites stay valid; `_move_record` signature change in Task 6 is internal. ✔

## Notes for the implementer
- `resolve_data_policy` is imported in the CLI from `project_config`; if `science.yaml` is absent (bare test dirs), the CLI falls back to `DEFAULT_DATA_POLICY`.
- All git calls run with `-C <project_root>` (or `cwd=`); tests `git init` their `tmp_path`.
- The audit treats a RECORD under `data/` as stranded whether or not it is tracked — this also cleans up old `git add -f` force-added evidence by relocating it to `results/`.

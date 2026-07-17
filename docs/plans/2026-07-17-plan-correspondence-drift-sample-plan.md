# Plan Correspondence-Drift Sample Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and run the pre-registered measurement that decides whether `plan`
entities drift from reality often enough to justify admitting them to curation
scope — a gate that can equally rule the existing epistemic-only restriction
correct.

**Architecture:** A small library under `science/src/science_tool/drift_sample/`,
composed of independently testable stages: freeze → blind → extract → probe →
score → draw → adjudicate. Stages are pure functions over explicit inputs; the
only I/O boundaries are git (frame/pins) and the filesystem (probes). Blinding,
extraction, probing, and scoring are all built and tested **before** the draw is
committed, so no threshold can be tuned to a result.

**Tech Stack:** Python 3.14, pydantic v2, pytest, `scipy.stats.beta` for exact
Clopper–Pearson bounds, `git worktree --detach` for pinned read-only checkouts.

**Design:** [`2026-07-17-plan-correspondence-drift-sample-design.md`](2026-07-17-plan-correspondence-drift-sample-design.md).
Read it first. This plan implements it and adds nothing to it.

## Global Constraints

- **Work from `science/`.** `cd science && uv run --frozen pytest`. There is no
  root `pyproject.toml`; running `uv run` from the repo root is the single most
  common orientation mistake here.
- **No CLI registration.** Nothing in this plan is wired into `cli.py`. The gate
  may withdraw the whole program; building CLI surface for it now is premature.
  Promotion is a later, separate decision.
- **No transient SHAs in this document.** Pins are captured at execution time by
  Task 1 and recorded in the pre-registration artifact. Any sha written into a
  plan is stale before it is read — natural-systems' branches move under Dropbox
  sync.
- **Pre-registration is immutable after Task 7 begins.** Tasks 1–6 build
  instruments; Task 7 commits the pre-registration; Task 8 reads the first plan.
  Nothing from Tasks 1–6 may change after Task 8 starts without a fresh draw.
- **Evidence vs claim.** Only artefacts *outside* a plan (files, symbols, task
  records, commits) are evidence. Anything the plan's author asserted about its
  own progress — `status`, checkboxes, "SHIPPED" — is a claim (design §6.1).
- **Lint/types:** `uv run ruff check` and `uv run pyright` from `science/`.
  Pyright is configured once at the repo root and covers `science/src`.
- **Commit messages:** no AI-attribution trailers.

## File Structure

| File | Responsibility |
|---|---|
| `science/src/science_tool/drift_sample/__init__.py` | Public re-exports only |
| `science/src/science_tool/drift_sample/frame.py` | Clean-tree assertion, pin capture, detached worktrees, frame enumeration |
| `science/src/science_tool/drift_sample/blind.py` | Remove all three claim channels from a plan |
| `science/src/science_tool/drift_sample/extract.py` | Pull candidate deliverables + task refs from a normalized body |
| `science/src/science_tool/drift_sample/probe.py` | Tri-state deliverable probe; task-state resolution |
| `science/src/science_tool/drift_sample/normalize.py` | Predeclared claim-normalization table (design §6.2a) |
| `science/src/science_tool/drift_sample/score.py` | Adjudicated status, mismatch, Manski bounds, CP gate, κ |
| `science/src/science_tool/drift_sample/draw.py` | Seeded SRS without replacement |
| `science/tests/test_drift_sample_*.py` | One test module per stage |
| `docs/plans/2026-07-17-drift-sample/prereg.json` | Execution artifact — pins, seed, frame, drawn ids, rubric version |

Split by stage, not by layer: each file is one step of the pipeline, holds one
responsibility, and is testable without the others.

---

### Task 1: Freeze the frame

**This is the execution gate.** Nothing downstream is meaningful against an
unpinned tree. multiple-myeloma is dirty and is 48% of the frame; its working copy
is Dropbox-synced and its HEAD can move mid-session.

**Files:**
- Create: `science/src/science_tool/drift_sample/__init__.py`
- Create: `science/src/science_tool/drift_sample/frame.py`
- Test: `science/tests/test_drift_sample_frame.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `class DirtyTreeError(RuntimeError)`
  - `Pin` — frozen dataclass `(project: str, root: Path, commit: str)`
  - `FrameRow` — frozen dataclass `(plan_id: str, project: str, rel_path: str, claimed_status: str, source_sha256: str)`
  - `assert_clean(root: Path) -> None`
  - `pin_project(project: str, root: Path) -> Pin`
  - `pinned_worktree(pin: Pin, base: Path) -> ContextManager[Path]`
  - `enumerate_frame(pin: Pin, worktree: Path) -> list[FrameRow]`

- [ ] **Step 1: Write the failing tests**

```python
# science/tests/test_drift_sample_frame.py
import subprocess
from pathlib import Path

import pytest

from science_tool.drift_sample.frame import (
    DirtyTreeError,
    assert_clean,
    enumerate_frame,
    pin_project,
    pinned_worktree,
)


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True, check=True
    ).stdout.strip()


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    (root / "entities" / "plans").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    _git(root, "config", "user.email", "t@t")
    _git(root, "config", "user.name", "t")
    return root


def _write_plan(root: Path, num: str, status: str) -> None:
    (root / "entities" / "plans" / f"{num}-x-plan.md").write_text(
        f"---\nkind: plan\ntitle: X\nstatus: {status}\nid: plan:{num}-x-plan\n---\n\nbody\n"
    )


def test_assert_clean_raises_on_dirty_tree(tmp_path: Path):
    root = _repo(tmp_path)
    _write_plan(root, "0001", "draft")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "init")
    (root / "entities" / "plans" / "0001-x-plan.md").write_text("dirtied")
    with pytest.raises(DirtyTreeError):
        assert_clean(root)


def test_assert_clean_raises_on_untracked_file(tmp_path: Path):
    """Untracked files are dirt too -- they can change what a probe sees."""
    root = _repo(tmp_path)
    _write_plan(root, "0001", "draft")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "init")
    (root / "stray.txt").write_text("x")
    with pytest.raises(DirtyTreeError):
        assert_clean(root)


def test_pin_project_returns_head_of_clean_tree(tmp_path: Path):
    root = _repo(tmp_path)
    _write_plan(root, "0001", "draft")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "init")
    pin = pin_project("proj", root)
    assert pin.commit == _git(root, "rev-parse", "HEAD")
    assert len(pin.commit) == 40


def test_worktree_shows_pinned_content_not_later_commits(tmp_path: Path):
    """The whole point of the pin: later commits must be invisible."""
    root = _repo(tmp_path)
    _write_plan(root, "0001", "draft")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "init")
    pin = pin_project("proj", root)
    _write_plan(root, "0002", "active")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "later")
    with pinned_worktree(pin, tmp_path / "wt") as wt:
        rows = enumerate_frame(pin, wt)
    assert [r.plan_id for r in rows] == ["plan:0001-x-plan"]


def test_worktree_is_removed_on_exit(tmp_path: Path):
    root = _repo(tmp_path)
    _write_plan(root, "0001", "draft")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "init")
    pin = pin_project("proj", root)
    with pinned_worktree(pin, tmp_path / "wt") as wt:
        assert wt.exists()
    assert not wt.exists()


def test_enumerate_frame_records_status_and_content_hash(tmp_path: Path):
    root = _repo(tmp_path)
    _write_plan(root, "0001", "draft")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "init")
    pin = pin_project("proj", root)
    with pinned_worktree(pin, tmp_path / "wt") as wt:
        rows = enumerate_frame(pin, wt)
    assert len(rows) == 1
    assert rows[0].claimed_status == "draft"
    assert rows[0].project == "proj"
    assert rows[0].rel_path == "entities/plans/0001-x-plan.md"
    assert len(rows[0].source_sha256) == 64


def test_enumerate_frame_skips_files_without_frontmatter(tmp_path: Path):
    root = _repo(tmp_path)
    _write_plan(root, "0001", "draft")
    (root / "entities" / "plans" / "README.md").write_text("# not a plan\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "init")
    pin = pin_project("proj", root)
    with pinned_worktree(pin, tmp_path / "wt") as wt:
        rows = enumerate_frame(pin, wt)
    assert [r.plan_id for r in rows] == ["plan:0001-x-plan"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science && uv run --frozen pytest tests/test_drift_sample_frame.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'science_tool.drift_sample'`

- [ ] **Step 3: Write the implementation**

```python
# science/src/science_tool/drift_sample/__init__.py
"""Instruments for the plan correspondence-drift sample (pre-registered).

See docs/plans/2026-07-17-plan-correspondence-drift-sample-design.md.
Deliberately not wired into the CLI: the gate this serves may withdraw the
program it belongs to.
"""
```

```python
# science/src/science_tool/drift_sample/frame.py
"""Pin projects at a commit and enumerate the plan-entity frame.

A probe run against an unpinned tree measures nothing reproducible, so every
stage downstream reads from a detached worktree at a recorded commit.
"""

from __future__ import annotations

import hashlib
import re
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

_STATUS_RE = re.compile(r"^status:\s*['\"]?([\w-]+)", re.M)
_ID_RE = re.compile(r"^id:\s*['\"]?([\w:.-]+)", re.M)


class DirtyTreeError(RuntimeError):
    """The working tree has uncommitted or untracked changes."""


@dataclass(frozen=True)
class Pin:
    project: str
    root: Path
    commit: str


@dataclass(frozen=True)
class FrameRow:
    plan_id: str
    project: str
    rel_path: str
    claimed_status: str
    source_sha256: str


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True, check=True
    ).stdout.strip()


def assert_clean(root: Path) -> None:
    # --porcelain reports untracked files too; they are dirt for our purposes
    # because they can change what a probe sees without appearing in history.
    out = _git(root, "status", "--porcelain")
    if out:
        raise DirtyTreeError(f"{root} is not clean:\n{out}")


def pin_project(project: str, root: Path) -> Pin:
    assert_clean(root)
    return Pin(project=project, root=root, commit=_git(root, "rev-parse", "HEAD"))


@contextmanager
def pinned_worktree(pin: Pin, base: Path) -> Iterator[Path]:
    wt = base / pin.project
    wt.parent.mkdir(parents=True, exist_ok=True)
    _git(pin.root, "worktree", "add", "--detach", "-f", str(wt), pin.commit)
    try:
        yield wt
    finally:
        _git(pin.root, "worktree", "remove", "--force", str(wt))


def _frontmatter(text: str) -> str | None:
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---", 4)
    return None if end < 0 else text[4:end]


def enumerate_frame(pin: Pin, worktree: Path) -> list[FrameRow]:
    rows: list[FrameRow] = []
    plans_dir = worktree / "entities" / "plans"
    if not plans_dir.is_dir():
        return rows
    for path in sorted(plans_dir.glob("*.md")):
        raw = path.read_bytes()
        fm = _frontmatter(raw.decode("utf-8", errors="replace"))
        if fm is None:
            continue
        id_m = _ID_RE.search(fm)
        status_m = _STATUS_RE.search(fm)
        if id_m is None:
            continue
        rows.append(
            FrameRow(
                plan_id=id_m.group(1),
                project=pin.project,
                rel_path=str(path.relative_to(worktree)),
                claimed_status=status_m.group(1) if status_m else "",
                source_sha256=hashlib.sha256(raw).hexdigest(),
            )
        )
    return rows
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_drift_sample_frame.py -q`
Expected: `7 passed`

- [ ] **Step 5: Lint and typecheck**

Run: `cd science && uv run ruff check src/science_tool/drift_sample/ && uv run pyright src/science_tool/drift_sample/`
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/drift_sample/ science/tests/test_drift_sample_frame.py
git commit -m "feat(drift-sample): pin projects and enumerate the plan frame"
```

- [ ] **Step 7: HUMAN GATE — clear multiple-myeloma**

**Stop here and hand back to the user.** This step is not automatable and must
not be worked around.

`~/d/cancer/cancer-types/multiple-myeloma` has uncommitted changes and is 48% of
the frame. Ask the user to commit or stash them. Do **not** stash on their behalf:
the tree is Dropbox-synced, the changes are theirs, and a stash is a
hard-to-notice mutation of someone else's work.

Then verify all four projects are clean:

```bash
cd science && uv run --frozen python -c "
from pathlib import Path
from science_tool.drift_sample.frame import assert_clean, pin_project
roots = {
    'multiple-myeloma': Path.home()/'d/cancer/cancer-types/multiple-myeloma',
    'natural-systems': Path.home()/'d/natural-systems',
    'protein-landscape': Path.home()/'d/protein-landscape',
    'post-acute-infection': Path.home()/'d/health/processes/post-acute-infection',
}
for name, root in roots.items():
    assert_clean(root)
    print(name, pin_project(name, root).commit)
"
```

Expected: four shas, no `DirtyTreeError`. **Do not record these shas anywhere
yet** — they are captured atomically in Task 7. A sha noted here and reused later
is exactly the staleness this gate exists to prevent.

---

### Task 2: Blind the plan

Three claim channels, all removed (design §6.1). This is the task that makes the
measurement honest: an adjudicator that sees any authored progress claim anchors
on it, and the resulting rate is indistinguishable from "no drift".

**Files:**
- Create: `science/src/science_tool/drift_sample/blind.py`
- Test: `science/tests/test_drift_sample_blind.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `PROGRESS_PATTERNS: tuple[re.Pattern[str], ...]` — the predeclared list
  - `blind_plan(text: str) -> str` — frontmatter stripped, body normalized

- [ ] **Step 1: Write the failing tests**

```python
# science/tests/test_drift_sample_blind.py
from science_tool.drift_sample.blind import blind_plan


def test_frontmatter_is_stripped_entirely():
    out = blind_plan("---\nkind: plan\nstatus: complete\nid: plan:1-x\n---\n\nbody text\n")
    assert "status" not in out
    assert "complete" not in out
    assert "body text" in out


def test_checked_boxes_are_normalized_to_unchecked():
    """62% of mm plans carry these; all-checked reads as `complete` to any reader."""
    out = blind_plan("---\nstatus: draft\n---\n\n- [x] did it\n- [X] also did it\n- [ ] not yet\n")
    assert "[x]" not in out and "[X]" not in out
    assert out.count("[ ]") == 3


def test_checkbox_text_survives_normalization():
    out = blind_plan("---\nstatus: draft\n---\n\n- [x] build `foo/bar.py`\n")
    assert "build `foo/bar.py`" in out


def test_progress_annotations_are_redacted():
    body = (
        "---\nstatus: draft\n---\n\n"
        "**Status:** SHIPPED -- merged to local main at `abc1234`.\n"
        "Design approved 2026-07-16.\n"
        "- [x] DONE: wire it up\n"
        "Everything works. ✅\n"
    )
    out = blind_plan(body)
    for leak in ("SHIPPED", "merged to local main", "approved", "DONE", "✅"):
        assert leak not in out, f"claim channel leaked: {leak}"


def test_ordinary_prose_is_not_redacted():
    """Over-redaction destroys the evidence the adjudicator needs."""
    out = blind_plan("---\nstatus: draft\n---\n\nAdd `src/foo.py` to complete the parser.\n")
    assert "`src/foo.py`" in out
    assert "parser" in out


def test_plan_without_frontmatter_is_returned_normalized():
    out = blind_plan("- [x] a thing\n")
    assert out.strip() == "- [ ] a thing"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science && uv run --frozen pytest tests/test_drift_sample_blind.py -q`
Expected: FAIL — `ModuleNotFoundError: ... 'science_tool.drift_sample.blind'`

- [ ] **Step 3: Write the implementation**

```python
# science/src/science_tool/drift_sample/blind.py
"""Remove every authored progress claim from a plan.

Design §6.1. Three channels, not one: `status` is the obvious claim, but a
checked box and a "SHIPPED" banner are the same class of assertion, written by
the same hand. Scoring `status` against a checkbox is claim-vs-claim, not
correspondence.

PROGRESS_PATTERNS is PREDECLARED: it is fixed before the draw. A channel
discovered mid-run invalidates the affected adjudications (they are redrawn
after this list is amended and re-registered) -- it is never quietly extended.
"""

from __future__ import annotations

import re

_CHECKBOX_RE = re.compile(r"^(\s*[-*] )\[[ xX]\]", re.M)

PROGRESS_PATTERNS: tuple[re.Pattern[str], ...] = (
    # "**Status:** SHIPPED -- merged at abc1234." (a whole banner line)
    re.compile(r"^\s*\*\*Status:?\*\*.*$", re.M | re.I),
    # bare verdict words, whole-word so "completeness"/"draft parser" survive
    re.compile(r"\b(SHIPPED|DONE|COMPLETE|COMPLETED|MERGED|LANDED)\b"),
    # "merged to local main at `abc1234`", "landed in main"
    re.compile(r"\b(merged|landed)\s+(to|in|into)\b[^.\n]*", re.I),
    # "Design approved 2026-07-16", "approved by ..."
    re.compile(r"\bapproved\b[^.\n]*", re.I),
    # status emoji
    re.compile(r"[✅✔☑❌✖]"),
)

_REDACTED = "[REDACTED]"


def _strip_frontmatter(text: str) -> str:
    if not text.startswith("---\n"):
        return text
    end = text.find("\n---", 4)
    if end < 0:
        return text
    rest = text[end + 4 :]
    return rest.lstrip("\n")


def blind_plan(text: str) -> str:
    """Return the plan body with all three claim channels removed."""
    body = _strip_frontmatter(text)
    body = _CHECKBOX_RE.sub(r"\1[ ]", body)
    for pattern in PROGRESS_PATTERNS:
        body = pattern.sub(_REDACTED, body)
    return body
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_drift_sample_blind.py -q`
Expected: `6 passed`

- [ ] **Step 5: Measure the leak rate on the real corpus**

Blinding that silently fails is worse than no blinding. Measure **both** channels
separately across the actual frame — they are distinct operations and only one
inserts `[REDACTED]`. Checkbox normalization rewrites `[x]` → `[ ]` and never
produces `[REDACTED]`, so the redaction count reflects the *prose* channel alone;
count checked boxes independently.

```bash
cd science && uv run --frozen python -c "
import pathlib, re
from science_tool.drift_sample.blind import blind_plan
box_chk = re.compile(r'^\s*[-*] \[[xX]\]', re.M)
roots = {
  'mm': pathlib.Path.home()/'d/cancer/cancer-types/multiple-myeloma',
  'ns': pathlib.Path.home()/'d/natural-systems',
  'pl': pathlib.Path.home()/'d/protein-landscape',
  'pa': pathlib.Path.home()/'d/health/processes/post-acute-infection',
}
for name, root in roots.items():
    d = root/'entities'/'plans'
    n = prose = chk = 0
    for f in sorted(d.glob('*.md')):
        n += 1
        raw = f.read_text(errors='replace')
        if box_chk.search(raw): chk += 1
        if '[REDACTED]' in blind_plan(raw): prose += 1
    print(f'{name}: prose redacted {prose}/{n}; checked-box normalized {chk}/{n}')
"
```

Record the output in the commit message. This is descriptive — there is no
threshold to pass.

**On the two rates.** 62% of multiple-myeloma plans carry checkbox *syntax*, but a
*checked* box — the only checkbox that asserts a claim — appears in roughly 5%.
The 62% justifies normalizing the format wherever it appears; it does **not**
predict the redaction rate, and a low checked-box count is expected, not
suspicious. A **0% prose-redaction** rate on multiple-myeloma would still be worth
investigating, since progress banners are common there.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/drift_sample/blind.py science/tests/test_drift_sample_blind.py
git commit -m "feat(drift-sample): blind all three authored claim channels"
```

---

### Task 3: Extract deliverables and task references

No plan declares deliverables — 0 of 264 (design §6.2). They are extracted from
the body, where 98% of multiple-myeloma and natural-systems plans name code paths.

**Files:**
- Create: `science/src/science_tool/drift_sample/extract.py`
- Test: `science/tests/test_drift_sample_extract.py`

**Interfaces:**
- Consumes: `blind_plan` output (a normalized body string).
- Produces:
  - `extract_deliverables(body: str) -> list[str]` — ordered, de-duplicated
  - `extract_task_refs(body: str) -> list[str]` — e.g. `["t254"]`

- [ ] **Step 1: Write the failing tests**

```python
# science/tests/test_drift_sample_extract.py
from science_tool.drift_sample.extract import extract_deliverables, extract_task_refs


def test_extracts_backticked_code_paths():
    body = "Add `src/foo/bar.py` and `tests/test_bar.py`.\n"
    assert extract_deliverables(body) == ["src/foo/bar.py", "tests/test_bar.py"]


def test_deduplicates_preserving_first_occurrence_order():
    body = "`b/y.py` then `a/x.py` then `b/y.py` again\n"
    assert extract_deliverables(body) == ["b/y.py", "a/x.py"]


def test_ignores_bare_filenames_without_a_directory():
    """`foo.py` cannot be resolved to a location -- it is ambiguous, not absent."""
    assert extract_deliverables("see `foo.py` somewhere\n") == []


def test_ignores_prose_in_backticks():
    assert extract_deliverables("the `status` field and `--apply` flag\n") == []


def test_extracts_supported_extensions_only():
    body = "`a/b.py` `c/d.ts` `e/f.md` `g/h.yaml` `i/j.json` `k/l.png` `m/n.exe`\n"
    assert extract_deliverables(body) == [
        "a/b.py", "c/d.ts", "e/f.md", "g/h.yaml", "i/j.json",
    ]


def test_extracts_task_refs():
    assert extract_task_refs("closes `task:t254` and task:t007\n") == ["t254", "t007"]


def test_task_refs_deduplicated():
    assert extract_task_refs("task:t1 task:t1 task:t2\n") == ["t1", "t2"]


def test_no_task_refs_returns_empty():
    assert extract_task_refs("no tasks here\n") == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science && uv run --frozen pytest tests/test_drift_sample_extract.py -q`
Expected: FAIL — `ModuleNotFoundError: ... 'science_tool.drift_sample.extract'`

- [ ] **Step 3: Write the implementation**

```python
# science/src/science_tool/drift_sample/extract.py
"""Extract probeable claims from a plan body.

Design §6.2: 0 of 264 plan entities declare a `deliverables:` key, so they are
extracted rather than read. Extraction is auditable because probe.py records
exactly what was tested.

Conservative by construction: a token that cannot be resolved to a location is
not extracted at all, so it becomes an absent deliverable rather than a spurious
`absent` probe. Under-extraction shows up as `indeterminate` (honest); over-
extraction would manufacture mismatches (not).
"""

from __future__ import annotations

import re

_EXTENSIONS = "py|ts|tsx|js|jsx|md|yaml|yml|json|sh|R|toml|cfg|ini|sql|trig"

# Requires at least one "/" -- a bare `foo.py` names no location.
_PATH_RE = re.compile(rf"`([\w.-]+(?:/[\w.-]+)+\.(?:{_EXTENSIONS}))`")
_TASK_RE = re.compile(r"task:(t\d+)")


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def extract_deliverables(body: str) -> list[str]:
    return _dedupe(_PATH_RE.findall(body))


def extract_task_refs(body: str) -> list[str]:
    return _dedupe(_TASK_RE.findall(body))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_drift_sample_extract.py -q`
Expected: `8 passed`

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/drift_sample/extract.py science/tests/test_drift_sample_extract.py
git commit -m "feat(drift-sample): extract deliverables and task refs from plan bodies"
```

---

### Task 4: Probe deliverables and tasks (tri-state)

**Files:**
- Create: `science/src/science_tool/drift_sample/probe.py`
- Test: `science/tests/test_drift_sample_probe.py`

**Interfaces:**
- Consumes: `extract_deliverables`, `extract_task_refs`, a pinned worktree `Path`.
- Produces:
  - `class ProbeResult(StrEnum)` — `PRESENT`/`ABSENT`/`UNKNOWN`
  - `class TaskState(StrEnum)` — `DONE`/`ACTIVE`/`MISSING`
  - `Probe` — frozen dataclass `(target: str, result: ProbeResult, detail: str)`
  - `probe_path(worktree: Path, rel: str) -> Probe`
  - `resolve_task(worktree: Path, task_id: str) -> TaskState`

- [ ] **Step 1: Write the failing tests**

```python
# science/tests/test_drift_sample_probe.py
from pathlib import Path

from science_tool.drift_sample.probe import (
    ProbeResult,
    TaskState,
    probe_path,
    resolve_task,
)


def test_present_when_file_exists(tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("x")
    assert probe_path(tmp_path, "src/a.py").result is ProbeResult.PRESENT


def test_absent_when_file_missing(tmp_path: Path):
    assert probe_path(tmp_path, "src/a.py").result is ProbeResult.ABSENT


def test_unknown_for_escaping_path(tmp_path: Path):
    """`../` cannot be evidence about this project -- it is not absent, it is unprobeable."""
    assert probe_path(tmp_path, "../secrets.py").result is ProbeResult.UNKNOWN


def test_unknown_for_absolute_path(tmp_path: Path):
    assert probe_path(tmp_path, "/etc/passwd").result is ProbeResult.UNKNOWN


def test_probe_records_what_was_tested(tmp_path: Path):
    probe = probe_path(tmp_path, "src/a.py")
    assert probe.target == "src/a.py"
    assert "src/a.py" in probe.detail


def test_directory_counts_as_present(tmp_path: Path):
    (tmp_path / "src" / "pkg").mkdir(parents=True)
    assert probe_path(tmp_path, "src/pkg").result is ProbeResult.PRESENT


def test_task_done_when_in_done_dir(tmp_path: Path):
    (tmp_path / "tasks" / "done").mkdir(parents=True)
    (tmp_path / "tasks" / "done" / "t254-thing.md").write_text("x")
    assert resolve_task(tmp_path, "t254") is TaskState.DONE


def test_task_active_when_named_in_active_file(tmp_path: Path):
    (tmp_path / "tasks").mkdir()
    (tmp_path / "tasks" / "active.md").write_text("- task:t254 do the thing\n")
    assert resolve_task(tmp_path, "t254") is TaskState.ACTIVE


def test_task_missing_when_nowhere(tmp_path: Path):
    (tmp_path / "tasks").mkdir()
    (tmp_path / "tasks" / "active.md").write_text("- task:t999\n")
    assert resolve_task(tmp_path, "t254") is TaskState.MISSING


def test_done_wins_over_active(tmp_path: Path):
    """A task both filed done and left in active.md is done; the file is the record."""
    (tmp_path / "tasks" / "done").mkdir(parents=True)
    (tmp_path / "tasks" / "done" / "t254-x.md").write_text("x")
    (tmp_path / "tasks" / "active.md").write_text("- task:t254\n")
    assert resolve_task(tmp_path, "t254") is TaskState.DONE


def test_task_id_is_matched_whole(tmp_path: Path):
    """t25 must not match t254."""
    (tmp_path / "tasks" / "done").mkdir(parents=True)
    (tmp_path / "tasks" / "done" / "t254-x.md").write_text("x")
    assert resolve_task(tmp_path, "t25") is TaskState.MISSING
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science && uv run --frozen pytest tests/test_drift_sample_probe.py -q`
Expected: FAIL — `ModuleNotFoundError: ... 'science_tool.drift_sample.probe'`

- [ ] **Step 3: Write the implementation**

```python
# science/src/science_tool/drift_sample/probe.py
"""Tri-state probes against a pinned worktree.

Design §5.2/§6.3: `unknown` is not `absent`. Only `absent` is evidence of
deadness; a probe that could not run is a fact about the instrument, and
collapsing the two is exactly how absence of evidence becomes evidence of
absence.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path, PurePosixPath


class ProbeResult(StrEnum):
    PRESENT = "present"
    ABSENT = "absent"
    UNKNOWN = "unknown"


class TaskState(StrEnum):
    DONE = "done"
    ACTIVE = "active"
    MISSING = "missing"


@dataclass(frozen=True)
class Probe:
    target: str
    result: ProbeResult
    detail: str


def probe_path(worktree: Path, rel: str) -> Probe:
    pure = PurePosixPath(rel)
    if pure.is_absolute() or ".." in pure.parts:
        return Probe(rel, ProbeResult.UNKNOWN, f"{rel}: outside the project, unprobeable")
    target = worktree / rel
    if target.exists():
        return Probe(rel, ProbeResult.PRESENT, f"{rel}: exists at {target}")
    return Probe(rel, ProbeResult.ABSENT, f"{rel}: not found at {target}")


def resolve_task(worktree: Path, task_id: str) -> TaskState:
    done_dir = worktree / "tasks" / "done"
    if done_dir.is_dir():
        # Whole-id match: `t25-*.md` must not be satisfied by `t254-*.md`.
        for path in done_dir.glob(f"{task_id}*.md"):
            stem = path.stem
            if stem == task_id or stem.startswith(f"{task_id}-"):
                return TaskState.DONE
    active = worktree / "tasks" / "active.md"
    if active.is_file():
        if re.search(rf"\b{re.escape(task_id)}\b", active.read_text(errors="replace")):
            return TaskState.ACTIVE
    return TaskState.MISSING
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_drift_sample_probe.py -q`
Expected: `11 passed`

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/drift_sample/probe.py science/tests/test_drift_sample_probe.py
git commit -m "feat(drift-sample): tri-state deliverable and task probes"
```

---

### Task 5: Claim normalization and scoring

**Built before the draw, deliberately.** A gate implemented after seeing data is a
gate tuned to data.

**Files:**
- Create: `science/src/science_tool/drift_sample/normalize.py`
- Create: `science/src/science_tool/drift_sample/score.py`
- Test: `science/tests/test_drift_sample_score.py`

**Interfaces:**
- Consumes: `ProbeResult`, `TaskState`.
- Produces:
  - `CLAIM_MAP: dict[str, str]`
  - `normalize_claim(claimed: str) -> str | None` — `None` = unmappable
  - `class Adjudicated(StrEnum)` — the six legal values plus `INDETERMINATE`
  - `adjudicate(deliverables: list[ProbeResult], tasks: list[TaskState], superseded: bool) -> Adjudicated`
  - `verdict(claimed: str, adjudicated: Adjudicated) -> bool | None` — `True` = mismatch, `None` = indeterminate
  - `manski(verdicts: list[bool | None]) -> tuple[int, int]`
  - `cp_lower(k: int, n: int, alpha: float) -> float` / `cp_upper(...)`
  - `class GateOutcome(StrEnum)` — `RULE_OUT`/`DEMONSTRATE`/`CONTINUE`
  - `gate(k: int, n: int) -> GateOutcome`
  - `LADDER: tuple[int, ...]`, `THETA: float`, `ALPHA: float`

- [ ] **Step 1: Write the failing tests**

```python
# science/tests/test_drift_sample_score.py
import pytest

from science_tool.drift_sample.normalize import normalize_claim
from science_tool.drift_sample.probe import ProbeResult, TaskState
from science_tool.drift_sample.score import (
    Adjudicated,
    GateOutcome,
    adjudicate,
    cp_upper,
    gate,
    manski,
    verdict,
)

P, A, U = ProbeResult.PRESENT, ProbeResult.ABSENT, ProbeResult.UNKNOWN


# --- claim normalization (design §6.2a) ---

@pytest.mark.parametrize("claimed,expected", [
    ("draft", "draft"), ("active", "active"), ("complete", "complete"),
    ("superseded", "superseded"), ("retired", "retired"), ("archived", "archived"),
    ("proposed", "draft"), ("design", "draft"),
    ("implemented", "complete"), ("completed", "complete"),
    ("in-progress", "active"), ("current", "active"), ("agreed", "active"),
])
def test_normalize_maps_prescribed_synonyms(claimed: str, expected: str):
    assert normalize_claim(claimed) == expected


@pytest.mark.parametrize("claimed", ["approved", "draft-for-review", "ready-with-caveats", "not-ready"])
def test_unmappable_claims_return_none(claimed: str):
    """These are S4's open question. Mapping them would decide S4 inside S1's evidence."""
    assert normalize_claim(claimed) is None


def test_unknown_claim_value_is_unmappable_not_an_error():
    assert normalize_claim("something-nobody-predeclared") is None


# --- adjudication (design §6.2) ---

def test_all_present_and_tasks_done_is_complete():
    assert adjudicate([P, P], [TaskState.DONE], superseded=False) is Adjudicated.COMPLETE


def test_all_present_and_no_tasks_referenced_is_complete():
    """Task linkage is ~48% at best -- absence of a task ref must not block `complete`."""
    assert adjudicate([P, P], [], superseded=False) is Adjudicated.COMPLETE


def test_all_present_but_task_active_is_active():
    assert adjudicate([P, P], [TaskState.ACTIVE], superseded=False) is Adjudicated.ACTIVE


def test_partial_deliverables_is_active():
    assert adjudicate([P, A], [], superseded=False) is Adjudicated.ACTIVE


def test_nothing_present_and_no_tasks_started_is_draft():
    assert adjudicate([A, A], [], superseded=False) is Adjudicated.DRAFT


def test_any_unknown_probe_is_indeterminate():
    assert adjudicate([P, U], [], superseded=False) is Adjudicated.INDETERMINATE


def test_no_deliverables_extracted_is_indeterminate():
    """Nothing was probed, so nothing was established."""
    assert adjudicate([], [], superseded=False) is Adjudicated.INDETERMINATE


def test_superseded_dominates():
    assert adjudicate([A, A], [], superseded=True) is Adjudicated.SUPERSEDED


# --- verdict ---

def test_match_is_not_a_mismatch():
    assert verdict("draft", Adjudicated.DRAFT) is False


def test_stale_under_claim_is_a_mismatch():
    """The S1 §2.2 hypothesis: claims draft, everything shipped."""
    assert verdict("draft", Adjudicated.COMPLETE) is True


def test_over_claim_is_a_mismatch():
    assert verdict("complete", Adjudicated.DRAFT) is True


def test_synonym_claim_matches_after_normalization():
    """`implemented` vs COMPLETE is a vocabulary issue (S4), not drift."""
    assert verdict("implemented", Adjudicated.COMPLETE) is False


def test_indeterminate_adjudication_is_indeterminate():
    assert verdict("draft", Adjudicated.INDETERMINATE) is None


def test_unmappable_claim_is_indeterminate():
    assert verdict("approved", Adjudicated.COMPLETE) is None


# --- Manski bounds (design §6.3) ---

def test_manski_bounds_bracket_the_indeterminates():
    # 2 mismatches, 3 matches, 2 indeterminate
    v = [True, True, False, False, False, None, None]
    assert manski(v) == (2, 4)


def test_manski_bounds_coincide_when_nothing_indeterminate():
    assert manski([True, False, False]) == (1, 1)


# --- gate (design §7) ---

def test_gate_rules_out_only_at_zero_errors_at_40():
    assert gate(0, 40) is GateOutcome.RULE_OUT
    assert gate(1, 40) is GateOutcome.CONTINUE


def test_gate_demonstrates_at_40():
    assert gate(9, 40) is GateOutcome.DEMONSTRATE
    assert gate(8, 40) is GateOutcome.CONTINUE


def test_gate_at_80():
    assert gate(2, 80) is GateOutcome.RULE_OUT
    assert gate(3, 80) is GateOutcome.CONTINUE
    assert gate(15, 80) is GateOutcome.DEMONSTRATE


def test_gate_at_census_compares_directly():
    """At n = N the rate is observed, not estimated."""
    assert gate(26, 264) is GateOutcome.RULE_OUT     # 9.8% < 10%
    assert gate(27, 264) is GateOutcome.DEMONSTRATE  # 10.2% > 10%


def test_rule_out_is_unreachable_below_the_ladder_floor():
    """At n = 29 even zero errors cannot clear theta -- why the ladder starts at 40."""
    assert cp_upper(0, 29, 0.05 / 3) > 0.10
    assert cp_upper(0, 39, 0.05 / 3) < 0.10


def test_gate_rejects_an_unregistered_sample_size():
    """Only the predeclared looks exist; an ad-hoc n is optional stopping."""
    with pytest.raises(ValueError, match="not a predeclared look"):
        gate(1, 55)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science && uv run --frozen pytest tests/test_drift_sample_score.py -q`
Expected: FAIL — `ModuleNotFoundError: ... 'science_tool.drift_sample.normalize'`

- [ ] **Step 3: Write the implementations**

```python
# science/src/science_tool/drift_sample/normalize.py
"""Predeclared claim normalization (design §6.2a). FIXED BEFORE THE DRAW.

`mismatch = adjudicated != claimed` is ill-defined against an illegal claim.
21 of natural-systems' 109 plans claim an illegal status and multiple-myeloma
claims zero, so comparing raw would make NS look drifty from S4's vocabulary
problem rather than its own drift.

Upstream-prescribed where upstream has spoken; refuses to invent where it has
not. `approved` / `draft-for-review` / `ready-with-caveats` / `not-ready` are
S4's open question -- mapping them here would decide S4 silently inside S1's
evidence and would move S1's answer.
"""

from __future__ import annotations

LEGAL: frozenset[str] = frozenset(
    {"draft", "active", "complete", "superseded", "retired", "archived"}
)

CLAIM_MAP: dict[str, str] = {
    **{value: value for value in LEGAL},
    "proposed": "draft",      # upstream-prescribed: core.py calls it drift toward `draft`
    "design": "draft",        # lifecycle position
    "implemented": "complete",
    "completed": "complete",
    "in-progress": "active",
    "current": "active",
    "agreed": "active",
}


def normalize_claim(claimed: str) -> str | None:
    """Return the legal status this claim means, or None if unmappable."""
    return CLAIM_MAP.get(claimed.strip().lower())
```

```python
# science/src/science_tool/drift_sample/score.py
"""Adjudication, Manski bounds, and the pre-registered gate (design §6-§7).

Written BEFORE the draw. A gate implemented after seeing data is tuned to data.
"""

from __future__ import annotations

from enum import StrEnum

from scipy.stats import beta

from science_tool.drift_sample.normalize import normalize_claim
from science_tool.drift_sample.probe import ProbeResult, TaskState

THETA: float = 0.10        # materiality; predeclared convention, not a derived optimum
ALPHA: float = 0.05 / 3    # Bonferroni over exactly three looks
LADDER: tuple[int, ...] = (40, 80, 264)
CENSUS: int = 264


class Adjudicated(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    COMPLETE = "complete"
    SUPERSEDED = "superseded"
    RETIRED = "retired"
    ARCHIVED = "archived"
    INDETERMINATE = "indeterminate"


class GateOutcome(StrEnum):
    RULE_OUT = "rule_out"
    DEMONSTRATE = "demonstrate"
    CONTINUE = "continue"


def adjudicate(
    deliverables: list[ProbeResult],
    tasks: list[TaskState],
    *,
    superseded: bool,
) -> Adjudicated:
    if superseded:
        return Adjudicated.SUPERSEDED
    if not deliverables or ProbeResult.UNKNOWN in deliverables:
        # Nothing probed, or a probe could not run: the instrument established
        # nothing. That is not evidence of deadness (design §6.3).
        return Adjudicated.INDETERMINATE
    all_present = all(d is ProbeResult.PRESENT for d in deliverables)
    none_present = all(d is ProbeResult.ABSENT for d in deliverables)
    tasks_settled = all(t is TaskState.DONE for t in tasks)  # vacuously true if empty
    tasks_unstarted = not tasks or all(t is TaskState.MISSING for t in tasks)
    if all_present and tasks_settled:
        return Adjudicated.COMPLETE
    if none_present and tasks_unstarted:
        return Adjudicated.DRAFT
    return Adjudicated.ACTIVE


def verdict(claimed: str, adjudicated: Adjudicated) -> bool | None:
    """True = mismatch, False = match, None = indeterminate."""
    if adjudicated is Adjudicated.INDETERMINATE:
        return None
    normalized = normalize_claim(claimed)
    if normalized is None:
        return None
    return normalized != adjudicated.value


def manski(verdicts: list[bool | None]) -> tuple[int, int]:
    """(k_lo, k_hi): indeterminates counted as matches, then as mismatches."""
    k = sum(1 for v in verdicts if v is True)
    unknown = sum(1 for v in verdicts if v is None)
    return k, k + unknown


def cp_lower(k: int, n: int, alpha: float) -> float:
    return 0.0 if k == 0 else float(beta.ppf(alpha, k, n - k + 1))


def cp_upper(k: int, n: int, alpha: float) -> float:
    return 1.0 if k == n else float(beta.ppf(1 - alpha, k + 1, n - k))


def gate(k: int, n: int) -> GateOutcome:
    if n not in LADDER:
        raise ValueError(f"n={n} is not a predeclared look; looks are {LADDER}")
    if n == CENSUS:
        # The population is observed, not estimated: no interval applies.
        return GateOutcome.RULE_OUT if k / n < THETA else GateOutcome.DEMONSTRATE
    if cp_upper(k, n, ALPHA) < THETA:
        return GateOutcome.RULE_OUT
    if cp_lower(k, n, ALPHA) > THETA:
        return GateOutcome.DEMONSTRATE
    return GateOutcome.CONTINUE
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_drift_sample_score.py -q`
Expected: `40 passed`

- [ ] **Step 5: Confirm `scipy` is available**

Run: `cd science && uv run --frozen python -c "import scipy; print(scipy.__version__)"`
If it fails, add it: `cd science && uv add scipy` and commit the lockfile change
with this task. Do **not** hand-roll a Clopper–Pearson approximation — the gate's
correctness at the zero-error boundary is the whole reason for an exact interval.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/drift_sample/normalize.py science/src/science_tool/drift_sample/score.py science/tests/test_drift_sample_score.py
git commit -m "feat(drift-sample): claim normalization and the pre-registered gate"
```

---

### Task 6: Seeded draw

**Files:**
- Create: `science/src/science_tool/drift_sample/draw.py`
- Test: `science/tests/test_drift_sample_draw.py`

**Interfaces:**
- Consumes: `FrameRow` from Task 1.
- Produces: `draw(frame: list[FrameRow], n: int, seed: int) -> list[FrameRow]`

- [ ] **Step 1: Write the failing tests**

```python
# science/tests/test_drift_sample_draw.py
import pytest

from science_tool.drift_sample.draw import draw
from science_tool.drift_sample.frame import FrameRow


def _frame(size: int) -> list[FrameRow]:
    return [
        FrameRow(f"plan:{i:04d}-x", "proj", f"entities/plans/{i:04d}-x.md", "draft", "0" * 64)
        for i in range(size)
    ]


def test_draw_is_deterministic_given_a_seed():
    frame = _frame(100)
    assert [r.plan_id for r in draw(frame, 10, seed=42)] == [
        r.plan_id for r in draw(frame, 10, seed=42)
    ]


def test_different_seeds_give_different_draws():
    frame = _frame(100)
    assert [r.plan_id for r in draw(frame, 10, seed=1)] != [
        r.plan_id for r in draw(frame, 10, seed=2)
    ]


def test_draw_is_without_replacement():
    ids = [r.plan_id for r in draw(_frame(100), 40, seed=7)]
    assert len(ids) == len(set(ids)) == 40


def test_draw_is_independent_of_frame_order():
    """Selection must not depend on how the frame happened to be enumerated."""
    frame = _frame(100)
    shuffled = list(reversed(frame))
    assert sorted(r.plan_id for r in draw(frame, 10, seed=3)) == sorted(
        r.plan_id for r in draw(shuffled, 10, seed=3)
    )


def test_draw_larger_than_frame_is_a_census():
    assert len(draw(_frame(10), 40, seed=1)) == 10


def test_draw_rejects_a_duplicate_frame():
    dup = _frame(3) + _frame(3)
    with pytest.raises(ValueError, match="duplicate"):
        draw(dup, 2, seed=1)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science && uv run --frozen pytest tests/test_drift_sample_draw.py -q`
Expected: FAIL — `ModuleNotFoundError: ... 'science_tool.drift_sample.draw'`

- [ ] **Step 3: Write the implementation**

```python
# science/src/science_tool/drift_sample/draw.py
"""Seeded simple random sample without replacement (design §5).

Equal inclusion probability for every plan. This is what makes the mismatch
count `k` a sufficient statistic, and therefore what makes score.gate()'s
count-based thresholds valid. Any move to unequal `pi` invalidates the gate.
"""

from __future__ import annotations

import random

from science_tool.drift_sample.frame import FrameRow


def draw(frame: list[FrameRow], n: int, seed: int) -> list[FrameRow]:
    ids = [row.plan_id for row in frame]
    if len(ids) != len(set(ids)):
        raise ValueError("frame contains duplicate plan_ids")
    # Sort first so the draw depends only on the seed and the frame's CONTENT,
    # never on enumeration order (filesystem order is not reproducible).
    ordered = sorted(frame, key=lambda r: r.plan_id)
    if n >= len(ordered):
        return ordered
    return random.Random(seed).sample(ordered, n)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_drift_sample_draw.py -q`
Expected: `6 passed`

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/drift_sample/draw.py science/tests/test_drift_sample_draw.py
git commit -m "feat(drift-sample): seeded equal-probability draw"
```

---

### Task 7: Capture pins and commit the pre-registration

**Everything before this builds instruments. This task freezes them.** After it
lands, nothing in Tasks 1–6 may change without a fresh draw.

**Files:**
- Create: `docs/plans/2026-07-17-drift-sample/prereg.json`
- Create: `science/scripts/drift_sample_prereg.py`

**Interfaces:**
- Consumes: `pin_project`, `pinned_worktree`, `enumerate_frame`, `draw`.
- Produces: `prereg.json` — the immutable record.

- [ ] **Step 1: Re-verify all four trees are clean**

Run the Task 1 Step 7 snippet again. If multiple-myeloma is dirty, **stop** and
return to the human gate. Its HEAD may have moved since Task 1 — Dropbox sync and
branch volatility are exactly why pins are captured here and not earlier.

- [ ] **Step 2: Write the pre-registration script**

```python
# science/scripts/drift_sample_prereg.py
"""Capture pins, enumerate the frame, draw, and emit the pre-registration.

Run once. Its output is committed and hashed before any plan is adjudicated.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path

from science_tool.drift_sample.draw import draw
from science_tool.drift_sample.frame import enumerate_frame, pin_project, pinned_worktree
from science_tool.drift_sample.score import ALPHA, LADDER, THETA

SEED = 20260717
ROOTS = {
    "multiple-myeloma": Path.home() / "d/cancer/cancer-types/multiple-myeloma",
    "natural-systems": Path.home() / "d/natural-systems",
    "protein-landscape": Path.home() / "d/protein-landscape",
    "post-acute-infection": Path.home() / "d/health/processes/post-acute-infection",
}
OUT = Path("docs/plans/2026-07-17-drift-sample/prereg.json")


def main() -> int:
    pins = {name: pin_project(name, root) for name, root in ROOTS.items()}
    frame = []
    with tempfile.TemporaryDirectory() as tmp:
        for pin in pins.values():
            with pinned_worktree(pin, Path(tmp)) as wt:
                frame.extend(enumerate_frame(pin, wt))
    drawn = draw(frame, LADDER[0], seed=SEED)
    rubric = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()
    record = {
        "schema": 1,
        "seed": SEED,
        "theta": THETA,
        "alpha": ALPHA,
        "ladder": list(LADDER),
        "rubric_commit": rubric,
        "pins": {name: pin.commit for name, pin in pins.items()},
        "frame_size": len(frame),
        "frame": [asdict(r) | {"root": None} for r in frame],
        "drawn_ids": [r.plan_id for r in drawn],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    print(f"frame={len(frame)} drawn={len(drawn)}")
    print("pins:", json.dumps(record["pins"], indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

Note `asdict(r) | {"root": None}`: `FrameRow` carries no `Path`, but guard
against ever serializing an absolute machine path into a committed artifact.

- [ ] **Step 3: Run it**

Run: `cd science && uv run --frozen python scripts/drift_sample_prereg.py`
Expected: `frame=264 drawn=40`, plus four shas.

- [ ] **Step 4: Reconcile the frame against the design**

If `frame_size != 264`, the corpus moved since 2026-07-17. **This is expected and
must be handled, not ignored:**

- Update the design's §3 table to the observed `N` and status distribution.
- **If `N` changed enough to move the ladder** — the census rung is literally `N`
  — update `CENSUS` in `score.py`, re-run its tests, and amend §7.
- Commit the design amendment **in the same commit** as `prereg.json`.

A frame that disagrees with the design and is used anyway is an unregistered
change to a pre-registration.

- [ ] **Step 5: Commit the pre-registration**

```bash
git add docs/plans/2026-07-17-drift-sample/prereg.json science/scripts/drift_sample_prereg.py docs/plans/2026-07-17-plan-correspondence-drift-sample-design.md
git commit -m "chore(drift-sample): pre-registration -- pins, seed, frame, draw

Frozen before adjudication. Records the four pinned commits, the seed, the
full frame, the drawn ids, theta, alpha, the ladder, and the rubric commit.
Nothing in the instruments may change after this without a fresh draw."
```

- [ ] **Step 6: Record the hash**

```bash
git rev-parse HEAD && sha256sum docs/plans/2026-07-17-drift-sample/prereg.json
```

Paste both into the design doc's §4 as the pre-registration record. This is what
makes "fixed before the draw" checkable by someone who was not here.

---

### Task 8: Run the blinded adjudication

**Files:**
- Create: `docs/plans/2026-07-17-drift-sample/resolve.py`
- Create: `docs/plans/2026-07-17-drift-sample/bundles.json`
- Create: `docs/plans/2026-07-17-drift-sample/verdicts.json`

**Interfaces:**
- Consumes: `prereg.json`, all instruments from Tasks 1–6.
- Produces: `resolve(rec) -> (rows, errs)` — the drawn-id → frame-row join, reused
  by Step 2 so bundles are built from verified rows only.
- Produces: one `{plan_id, adjudicator, deliverables[], tasks[], adjudicated}` per
  (plan × adjudicator).

- [ ] **Step 1: Resolve each drawn id to exactly one frame row, and verify its hash**

`prereg.json` already stores the complete frame (`project`, `rel_path`,
`source_sha256` per row) plus `drawn_ids`. Join them — do **not** re-enumerate the
corpus and do not copy the rows into a second record that could diverge.

Before blinding anything, resolve and verify:

Create `docs/plans/2026-07-17-drift-sample/resolve.py`:

```python
"""Resolve drawn ids to frame rows and verify pinned bytes. Fails loudly."""

import hashlib
import json
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

from science_tool.drift_sample.frame import Pin, pinned_worktree

# Roots are machine paths and are deliberately absent from prereg.json
# (Task 7 writes `root: None`). They are re-supplied here, never committed
# into the record. The commits come from the pre-registration; only the
# location is local.
ROOTS = {
    "multiple-myeloma": Path.home() / "d/cancer/cancer-types/multiple-myeloma",
    "natural-systems": Path.home() / "d/natural-systems",
    "protein-landscape": Path.home() / "d/protein-landscape",
    "post-acute-infection": Path.home() / "d/health/processes/post-acute-infection",
}
PREREG = Path("docs/plans/2026-07-17-drift-sample/prereg.json")


def resolve(rec: dict) -> tuple[list[dict], list[str]]:
    """Join drawn_ids to frame rows; exactly one row per id."""
    by_id: dict[str, list[dict]] = defaultdict(list)
    for row in rec["frame"]:
        by_id[row["plan_id"]].append(row)

    rows, errs = [], []
    for pid in rec["drawn_ids"]:
        hits = by_id.get(pid, [])
        if len(hits) != 1:
            errs.append(f"{pid}: resolved to {len(hits)} frame rows, expected exactly 1")
            continue
        rows.append(hits[0])
    return rows, errs


def main() -> int:
    rec = json.loads(PREREG.read_text())
    rows, errs = resolve(rec)

    by_project: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_project[row["project"]].append(row)

    with tempfile.TemporaryDirectory() as tmp:
        for project, prows in sorted(by_project.items()):
            pin = Pin(project=project, root=ROOTS[project], commit=rec["pins"][project])
            with pinned_worktree(pin, Path(tmp)) as wt:
                for row in prows:
                    path = wt / row["rel_path"]
                    if not path.exists():
                        errs.append(f"{row['plan_id']}: {row['rel_path']} missing at pin")
                        continue
                    got = hashlib.sha256(path.read_bytes()).hexdigest()
                    if got != row["source_sha256"]:
                        errs.append(
                            f"{row['plan_id']}: sha256 {got} != pinned {row['source_sha256']}"
                        )

    print("RESOLUTION ERRORS:", errs or "none")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
```

Run it:

```bash
cd science && uv run --frozen python ../docs/plans/2026-07-17-drift-sample/resolve.py
```

Expected: `RESOLUTION ERRORS: none`, exit 0.

Note the worktree is opened **once per project**, not once per plan: `pinned_worktree`
adds and removes a git worktree, so per-plan would do 40 add/remove cycles against
the same commit.

**Fail immediately on any of the three** — a missing row, multiple rows, or a hash
mismatch. Each means the pre-registration no longer describes the corpus being
read, so the sample it authorises is not the sample being run. Do not repair a row
by hand and do not fall back to re-enumeration: return to Task 7, re-register, and
redraw.

This is the only reader of `source_sha256`. Without it the field is written and
never checked, and a plan edited between registration and adjudication would be
adjudicated silently under a pre-registration that describes different bytes.

- [ ] **Step 2: Build the blinded bundles**

Step 1's worktrees are removed when `resolve.py` exits, so re-open one per project
here — grouping by project as `resolve.py` does, and reusing its `resolve()` to get
the rows. Build bundles **only** from rows that resolved and verified; if Step 1
reported any error, stop, because a bundle built from an unverified row is not the
artifact the pre-registration authorises.

For each resolved row: read the plan at `wt / row["rel_path"]`, run `blind_plan`,
then `extract_deliverables` / `extract_task_refs`. Write one bundle per plan to
`bundles.json` as `{plan_id, project, body, deliverables, tasks}` — the blinded body
and the extracted lists, and **no `claimed_status`**.

**Verify no bundle contains a claim** before dispatching any adjudicator:

```bash
cd science && uv run --frozen python -c "
import json, pathlib, re
bundles = json.loads(pathlib.Path('docs/plans/2026-07-17-drift-sample/bundles.json').read_text())
bad = [b['plan_id'] for b in bundles
       if re.search(r'\b(status:|SHIPPED|DONE|MERGED|\[x\])', b['body'], re.I)]
print('LEAKS:', bad or 'none')
"
```

Expected: `LEAKS: none`. Any leak is a blinding failure — fix `PROGRESS_PATTERNS`,
re-register (Task 7), and redraw. Do not hand-edit the bundle.

- [ ] **Step 3: Dispatch two independent adjudicators per plan**

Every plan is double-adjudicated (design §6.4). Each adjudicator receives one
bundle and returns only `{deliverables: [{target, result}], tasks: [{id, state}],
superseded: bool}` — **raw probe outcomes, not a status.** The status is computed
by `adjudicate()`, so a lenient adjudicator cannot shortcut to a verdict.

Dispatch them as parallel subagents with the bundle inline. The prompt must state:
the body may be truncated or redacted; report `unknown` when a probe cannot be
resolved; **`unknown` is a valid and expected answer, not a failure.**

- [ ] **Step 4: Resolve disagreements**

Where the two adjudicators differ on any probe, dispatch a third. Record all
three. Report Cohen's κ descriptively — it characterises the instrument and does
**not** gate.

- [ ] **Step 5: Commit the verdicts**

```bash
git add docs/plans/2026-07-17-drift-sample/verdicts.json
git commit -m "chore(drift-sample): blinded adjudication verdicts (n=40)"
```

---

### Task 9: Score and rule

**Files:**
- Create: `docs/plans/2026-07-17-drift-sample/result.md`
- Modify: `docs/plans/2026-07-17-curation-scope-certification-design.md`

- [ ] **Step 1: Compute the result**

Join verdicts to `claimed_status` from `prereg.json` (the first time the two meet),
then compute: the confusion matrix, `manski()` bounds, `gate(k_lo, 40)` and
`gate(k_hi, 40)`, the indeterminate rate, κ, and the realised composition by
project and claimed status.

- [ ] **Step 2: Apply the gate**

| Condition | Outcome |
|---|---|
| indeterminate rate > 20% | **inconclusive** — regardless of bounds (design §6.3); the instrument was measured, not the corpus. Improve probes; do not just sample more. |
| `gate(k_lo, 40)` and `gate(k_hi, 40)` disagree | **inconclusive** — go to n = 80 |
| both `RULE_OUT` | **drift ruled out** |
| both `DEMONSTRATE` | **drift demonstrated** |
| both `CONTINUE` | go to n = 80 |

- [ ] **Step 3: Write `result.md`**

Report the confusion matrix, both bounds, the indeterminate rate, κ, and the
per-project rates **marked descriptive, never gating**. State the outcome in one
sentence at the top.

- [ ] **Step 4: Apply the ruling to S1**

- **Demonstrated** → S1 §2.2's precondition is met. Update S1's status; admit
  `plan`; the roster ratification (§5 item 5) is now unblocked.
- **Ruled out** → **withdraw S1 §5.** Rewrite S1 to record that epistemic-only is
  **certified correct**, with this result as the evidence. Then S2 and S3 have
  lost their S1 dependency and must re-justify themselves independently — say so
  explicitly in the program table (S1 §7).
- **Inconclusive** → record it; go to n = 80 with the *same* pre-registration.

- [ ] **Step 5: Commit**

```bash
git add docs/plans/2026-07-17-drift-sample/result.md docs/plans/2026-07-17-curation-scope-certification-design.md
git commit -m "docs(drift-sample): result and the S1 ruling"
```

---

## Self-Review

**Spec coverage.**

| Design section | Task |
|---|---|
| §3 population, pins, mm gate | 1 (+7 re-verify) |
| §4 pre-registration | 7 |
| §5 SRS, no substitution | 6 |
| §6.1 blinding, three channels | 2 |
| §6.2 extraction, tri-state probes | 3, 4 |
| §6.2a claim normalization | 5 |
| §6.3 Manski, 20% ceiling | 5 (bounds), 9 (ceiling) |
| §6.4 double-review, κ | 8 |
| §7 gate, ladder, θ, α | 5 |
| §8 deliverables | 7, 8, 9 |

**Known gaps, accepted:**

- **§7's finite-population correction is not implemented.** The design permits
  hypergeometric bounds but requires the choice be predeclared. It is hereby
  predeclared **not used**: Clopper–Pearson is conservative (it ignores the FPC),
  so this can only make `RULE_OUT` harder, never easier — it cannot manufacture a
  false negative for drift. Revisit only if rung 2 is reached.
- **`superseded` detection is left to the adjudicator** rather than derived from a
  `supersedes` scan of the whole corpus. Only 1 of 264 plans claims `superseded`,
  so a dedicated instrument is not worth its cost; a missed supersession surfaces
  as `indeterminate` or a recorded mismatch, both honest.
- **Task 8 is not TDD-able.** It runs agents against real data. Its guard is the
  Step 1 leak check plus the fact that adjudicators return probe outcomes rather
  than statuses.

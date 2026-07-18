# Plan Correspondence-Drift Screen — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a deterministic, advisory `science validate` check that flags a `plan` entity whose `status` under-claims its real progress (e.g. `draft` while its deliverables exist on disk), feeding `science entity review`; never gates.

**Architecture:** Extract the reusable status-vs-reality core (`probe`, `extract`, `adjudicate`, plus a new `evidence_signature`) out of the frozen study package `drift_sample/` into a production package `science_tool/correspondence/`. Add a `validate` check that compares each plan's claimed lifecycle rank against a deterministic adjudication of its extracted deliverables, emitting a permanent-WARN, ungated, evidence-signed finding on under-claim only. Centralize `accepted_validation` handling in `validate.acceptance` (both `validate` and `graph.health` delegate) and make suppression of this rule require an exact evidence-signature token, enforced fail-closed by a second canonical check.

**Tech Stack:** Python 3.12+, `uv` (run from `science/`), pytest, pydantic (`science-model`), the existing `science_tool.validate` check framework.

**Design:** `docs/plans/2026-07-17-plan-correspondence-drift-screen-design.md`.

## Global Constraints

- **Permanent WARN, never gates.** `plan.correspondence-drift` and `accepted-validation.evidence-scope-required` emit `Severity.WARN` unconditionally and appear in **no** gate tier (`validate/gates.py`). Never call `severity_for_kind` for these rules.
- **`Result.path` is project-relative** on every finding this plan emits (validation contract).
- **Evidence-signature bytes are exact:** `json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")`, hashed with SHA-256, formatted `v1:<64-hex>`. Versioned; persisted into committed `science.yaml`.
- **One acceptance authority:** `science_tool.validate.acceptance`. `graph.health` imports it (the reverse import is forbidden). No duplicate matcher survives.
- **No compatibility shims / legacy layers.** Relocations retarget imports; they do not leave re-export stubs.
- **Frozen study stays reproducible and executable.** `adjudicate`/`probe`/`extract` logic is byte-for-byte unchanged by relocation; `drift_sample/` study scripts retarget their imports.
- **No AI-attribution trailers** on any commit (no `Co-Authored-By`, no "Generated with" footer).
- **Run tests from `science/`:** `cd science && uv run --frozen pytest …`. Lint/types: `uv run ruff check`, `uv run pyright`.

---

### Task 1: Relocate the correspondence core (behavior-neutral)

Move `probe`/`extract`/`adjudicate` out of the study package into a production package. Pure refactor — the full suite must stay green and the frozen-study scripts must still import.

**Files:**
- Create: `science/src/science_tool/correspondence/__init__.py`
- Create: `science/src/science_tool/correspondence/probe.py` (from `drift_sample/probe.py`, verbatim)
- Create: `science/src/science_tool/correspondence/extract.py` (from `drift_sample/extract.py`, verbatim)
- Create: `science/src/science_tool/correspondence/adjudicate.py` (`Adjudicated` + `adjudicate`, lifted from `drift_sample/score.py`)
- Delete: `science/src/science_tool/drift_sample/probe.py`, `science/src/science_tool/drift_sample/extract.py`
- Modify: `science/src/science_tool/drift_sample/score.py` (drop moved code; import from `correspondence`)
- Modify: `docs/plans/2026-07-17-drift-sample/build_bundles.py:14-16`, `docs/plans/2026-07-17-drift-sample/score_run.py:15-18`
- Test (create): `science/tests/test_correspondence_adjudicate.py`
- Test (modify): `science/tests/test_drift_sample_probe.py`, `science/tests/test_drift_sample_extract.py`, `science/tests/test_drift_sample_score.py`

**Interfaces:**
- Produces: `science_tool.correspondence.probe` → `probe_path(worktree: Path, rel: str) -> Probe`, `resolve_task(worktree: Path, task_id: str) -> TaskState`, `ProbeResult` (StrEnum: PRESENT/ABSENT/UNKNOWN), `TaskState` (StrEnum: DONE/ACTIVE/MISSING), `Probe(target: str, result: ProbeResult, detail: str)`.
- Produces: `science_tool.correspondence.extract` → `extract_deliverables(body: str) -> list[str]`, `extract_task_refs(body: str) -> list[str]`.
- Produces: `science_tool.correspondence.adjudicate` → `Adjudicated` (StrEnum: DRAFT/ACTIVE/COMPLETE/SUPERSEDED/RETIRED/ARCHIVED/INDETERMINATE), `adjudicate(deliverables: list[ProbeResult], tasks: list[TaskState], *, superseded: bool) -> Adjudicated`.

- [ ] **Step 1: Create the package `__init__`**

Create `science/src/science_tool/correspondence/__init__.py`:

```python
"""Reusable status-vs-reality core: probe a record's promised deliverables against
the tree, adjudicate a lifecycle state deterministically, and sign the evidence.

Extracted from the frozen `drift_sample` study so production checks and the study
share ONE definition (design §4.1). The study's statistics stay in `drift_sample`.
"""
```

- [ ] **Step 2: Move `probe.py` and `extract.py` verbatim**

```bash
cd /mnt/ssd/Dropbox/science/.worktrees/plan-correspondence-drift-screen/science
git mv src/science_tool/drift_sample/probe.py src/science_tool/correspondence/probe.py
git mv src/science_tool/drift_sample/extract.py src/science_tool/correspondence/extract.py
```

No content edits — the modules have no intra-`drift_sample` imports.

- [ ] **Step 3: Create `correspondence/adjudicate.py`**

Create `science/src/science_tool/correspondence/adjudicate.py` (lift the enum + function from `score.py`; import `ProbeResult`/`TaskState` from the new location):

```python
"""Deterministic lifecycle adjudication from probe results (design §2, §4.1)."""

from __future__ import annotations

from enum import StrEnum

from science_tool.correspondence.probe import ProbeResult, TaskState


class Adjudicated(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    COMPLETE = "complete"
    SUPERSEDED = "superseded"
    RETIRED = "retired"
    ARCHIVED = "archived"
    INDETERMINATE = "indeterminate"


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
```

- [ ] **Step 4: Trim `drift_sample/score.py` to statistics, importing the moved symbols**

Replace the top of `science/src/science_tool/drift_sample/score.py` (the module docstring stays) — remove the `Adjudicated` class and the `adjudicate` function, and fix imports. After trimming, `score.py` no longer references `ProbeResult`/`TaskState` (they lived only in `adjudicate`'s signature, which moved out) and never calls `adjudicate`; the only moved symbol it still uses is `Adjudicated`, in `verdict`. The final import block reads:

```python
from __future__ import annotations

from enum import StrEnum

from scipy.stats import beta

from science_tool.correspondence.adjudicate import Adjudicated
from science_tool.drift_sample.normalize import normalize_claim

THETA: float = 0.10        # materiality; predeclared convention, not a derived optimum
ALPHA: float = 0.05 / 3    # Bonferroni over exactly three looks
LADDER: tuple[int, ...] = (40, 80, 264)
CENSUS: int = 264


class GateOutcome(StrEnum):
    RULE_OUT = "rule_out"
    DEMONSTRATE = "demonstrate"
    CONTINUE = "continue"
```

Keep `verdict`, `manski`, `cp_lower`, `cp_upper`, `gate` exactly as they are. No re-export shim: `score_run.py` (Step 5) imports `adjudicate`/`Adjudicated` from `correspondence` directly, and `test_drift_sample_score.py` is updated in Step 7.

- [ ] **Step 5: Retarget the study scripts**

In `docs/plans/2026-07-17-drift-sample/build_bundles.py`, change line 15:

```python
from science_tool.correspondence.extract import extract_deliverables, extract_task_refs
```

In `docs/plans/2026-07-17-drift-sample/score_run.py`, change lines 16 and 18:

```python
from science_tool.correspondence.probe import probe_path, resolve_task
from science_tool.correspondence.adjudicate import Adjudicated, adjudicate
from science_tool.drift_sample.score import verdict, manski, gate
```

(Line 15's `from science_tool.drift_sample.frame import Pin, pinned_worktree` and line 17's `normalize` import are unchanged.)

- [ ] **Step 6: Retarget the moved-module tests**

In `science/tests/test_drift_sample_probe.py` and `science/tests/test_drift_sample_extract.py`, replace every `science_tool.drift_sample.probe` / `science_tool.drift_sample.extract` import path with `science_tool.correspondence.probe` / `science_tool.correspondence.extract`. Rename the files to match their new home:

```bash
git mv tests/test_drift_sample_probe.py tests/test_correspondence_probe.py
git mv tests/test_drift_sample_extract.py tests/test_correspondence_extract.py
```

- [ ] **Step 7: Split the adjudication tests out of the score test**

Move the eight adjudication tests (`test_drift_sample_score.py` lines 43–73: `test_all_present_and_tasks_done_is_complete` through `test_superseded_dominates`) into a new `science/tests/test_correspondence_adjudicate.py`. Header:

```python
"""Deterministic lifecycle adjudication (design §2)."""

from __future__ import annotations

from science_tool.correspondence.adjudicate import Adjudicated, adjudicate
from science_tool.correspondence.probe import ProbeResult, TaskState
```

Paste the eight test functions verbatim. In `test_drift_sample_score.py`, delete those eight functions and fix its imports so the surviving `normalize`/`verdict`/`manski`/`gate` tests still resolve `Adjudicated`:

```python
from science_tool.correspondence.adjudicate import Adjudicated
from science_tool.drift_sample.score import (
    CENSUS, GateOutcome, cp_lower, cp_upper, gate, manski, verdict,
)
from science_tool.drift_sample.normalize import normalize_claim
```

The surviving `normalize`/`verdict`/`manski`/`gate` tests reference `Adjudicated`, `normalize_claim`, and the statistics — not `ProbeResult`/`TaskState`. If pyright/ruff flags any of the above as unused after the split, delete that name from the import.

- [ ] **Step 8: Run the full suite + type-check to prove behavior-neutral**

Run: `cd science && uv run --frozen pytest -q`
Expected: PASS (same count as before the task, minus zero — tests moved, not removed).
Run: `uv run pyright && uv run ruff check`
Expected: 0 errors.

- [ ] **Step 9: Prove the frozen-study scripts still import**

Run: `cd science && uv run --frozen python -c "import ast, pathlib; [ast.parse(pathlib.Path(p).read_text()) for p in ['../docs/plans/2026-07-17-drift-sample/build_bundles.py','../docs/plans/2026-07-17-drift-sample/score_run.py']]; import science_tool.drift_sample.score, science_tool.correspondence.adjudicate, science_tool.correspondence.probe, science_tool.correspondence.extract; print('ok')"`
Expected: `ok`

- [ ] **Step 10: Commit**

```bash
git add -A
git commit -m "refactor(correspondence): extract probe/extract/adjudicate from drift_sample"
```

---

### Task 2: Evidence signature

Add the deterministic, versioned signature over a plan's evidence. Its byte encoding is a persisted contract, so it gets an isolated test.

**Files:**
- Create: `science/src/science_tool/correspondence/signature.py`
- Test: `science/tests/test_correspondence_signature.py`

**Interfaces:**
- Consumes: `Probe`, `TaskState` (Task 1).
- Produces: `evidence_signature(*, claimed: str, probes: list[Probe], task_states: list[tuple[str, TaskState]], adjudicated: str) -> str` → `"v1:<64-hex>"`.

- [ ] **Step 1: Write the failing test**

Create `science/tests/test_correspondence_signature.py`:

```python
from __future__ import annotations

import hashlib
import json

from science_tool.correspondence.probe import Probe, ProbeResult, TaskState
from science_tool.correspondence.signature import evidence_signature


def _probe(target: str, result: ProbeResult) -> Probe:
    return Probe(target, result, "")


def test_signature_is_versioned_full_sha256_of_canonical_json():
    probes = [_probe("b.py", ProbeResult.PRESENT), _probe("a.py", ProbeResult.ABSENT)]
    tasks = [("t2", TaskState.DONE), ("t1", TaskState.MISSING)]
    payload = {
        "v": 1,
        "claimed": "draft",
        "deliverables": [["a.py", "absent"], ["b.py", "present"]],
        "tasks": [["t1", "missing"], ["t2", "done"]],
        "adjudicated": "active",
    }
    expected_bytes = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    expected = "v1:" + hashlib.sha256(expected_bytes).hexdigest()
    assert evidence_signature(claimed="draft", probes=probes, task_states=tasks, adjudicated="active") == expected


def test_signature_is_order_independent_in_inputs():
    a = evidence_signature(
        claimed="draft",
        probes=[_probe("a.py", ProbeResult.PRESENT), _probe("b.py", ProbeResult.PRESENT)],
        task_states=[("t1", TaskState.DONE)],
        adjudicated="complete",
    )
    b = evidence_signature(
        claimed="draft",
        probes=[_probe("b.py", ProbeResult.PRESENT), _probe("a.py", ProbeResult.PRESENT)],
        task_states=[("t1", TaskState.DONE)],
        adjudicated="complete",
    )
    assert a == b


def test_signature_changes_when_a_probe_result_changes():
    base = dict(claimed="draft", task_states=[], adjudicated="active")
    present = evidence_signature(probes=[_probe("a.py", ProbeResult.PRESENT)], **base)
    absent = evidence_signature(probes=[_probe("a.py", ProbeResult.ABSENT)], **base)
    assert present != absent
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_correspondence_signature.py -q`
Expected: FAIL (`ModuleNotFoundError: science_tool.correspondence.signature`).

- [ ] **Step 3: Implement**

Create `science/src/science_tool/correspondence/signature.py`:

```python
"""Deterministic, versioned evidence signature (design §5.5).

Persisted into committed `science.yaml` via `accepted_validation`, so the byte
encoding is pinned exactly and the format is versioned: any change to what the
evidence covers is a NEW version, never a silent reinterpretation of old entries.
"""

from __future__ import annotations

import hashlib
import json

from science_tool.correspondence.probe import Probe, TaskState


def evidence_signature(
    *,
    claimed: str,
    probes: list[Probe],
    task_states: list[tuple[str, TaskState]],
    adjudicated: str,
) -> str:
    payload = {
        "v": 1,
        "claimed": claimed,
        "deliverables": sorted([p.target, p.result.value] for p in probes),
        "tasks": sorted([ref, state.value] for ref, state in task_states),
        "adjudicated": adjudicated,
    }
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return "v1:" + hashlib.sha256(canonical).hexdigest()
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd science && uv run --frozen pytest tests/test_correspondence_signature.py -q`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add src/science_tool/correspondence/signature.py tests/test_correspondence_signature.py
git commit -m "feat(correspondence): versioned evidence signature"
```

---

### Task 3: `ValidateContext.body()` via the canonical splitter

Give checks the plan body through one cached `(frontmatter, body)` parse built on `split_frontmatter`; re-back `frontmatter()` on the same parse so there is no second splitter.

**Files:**
- Modify: `science/src/science_tool/validate/context.py:78-142`
- Test: `science/tests/validate/test_context_body.py`

**Interfaces:**
- Produces: `ValidateContext.body(path: Path) -> str` (verbatim body after frontmatter); `ValidateContext.frontmatter(path)` unchanged in behavior.

- [ ] **Step 1: Write the failing test**

Create `science/tests/validate/test_context_body.py`:

```python
from __future__ import annotations

from pathlib import Path

from science_tool.validate.context import ValidateContext


def _ctx(root: Path) -> ValidateContext:
    (root / "science.yaml").write_text("name: fixture\nprofile: research\n", encoding="utf-8")
    return ValidateContext.from_project_root(root, strict=False, verbose=False)


def test_body_returns_content_after_frontmatter(tmp_path: Path):
    p = tmp_path / "e.md"
    p.write_text('---\nkind: plan\nstatus: "draft"\n---\n\nHello `src/a.py`.\n', encoding="utf-8")
    assert _ctx(tmp_path).body(p) == "\nHello `src/a.py`.\n"


def test_body_of_a_file_without_frontmatter_is_the_whole_text(tmp_path: Path):
    p = tmp_path / "e.md"
    p.write_text("no frontmatter here\n", encoding="utf-8")
    assert _ctx(tmp_path).body(p) == "no frontmatter here\n"


def test_frontmatter_still_parses(tmp_path: Path):
    p = tmp_path / "e.md"
    p.write_text('---\nkind: plan\nstatus: "draft"\n---\n\nBody\n', encoding="utf-8")
    assert _ctx(tmp_path).frontmatter(p) == {"kind": "plan", "status": "draft"}
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd science && uv run --frozen pytest tests/validate/test_context_body.py -q`
Expected: FAIL (`AttributeError: 'ValidateContext' object has no attribute 'body'`).

- [ ] **Step 3: Implement the shared parse + `body()`**

In `science/src/science_tool/validate/context.py`, add the import at the top:

```python
from science_model.frontmatter import split_frontmatter
```

Add a cached split field to the dataclass (next to the other caches, ~line 39):

```python
    _split_cache: dict[tuple[Path, int], tuple[dict[str, Any], str]] = field(default_factory=dict, init=False, repr=False)
```

Add the shared parse and re-back both accessors (replace the existing `frontmatter` method body and the `_parse_frontmatter` staticmethod):

```python
    def _split(self, path: Path) -> tuple[dict[str, Any], str]:
        key = self._cache_key(path)
        if key not in self._split_cache:
            fm, body = split_frontmatter(self.read_text_cached(key[0]))
            self._split_cache[key] = (fm if isinstance(fm, dict) else {}, body)
        return self._split_cache[key]

    def frontmatter(self, path: Path) -> dict[str, Any]:
        return self._split(path)[0]

    def body(self, path: Path) -> str:
        return self._split(path)[1]
```

Delete the now-unused `_frontmatter_cache` field and the `_parse_frontmatter` staticmethod.

- [ ] **Step 4: Run the new test + the full validate suite (the `frontmatter()` guard)**

Run: `cd science && uv run --frozen pytest tests/validate/test_context_body.py tests/validate -q`
Expected: PASS.
Run: `cd science && uv run --frozen pytest -q`
Expected: PASS (whole suite — this is the guard that unifying `frontmatter()` regressed nothing).

- [ ] **Step 5: Commit**

```bash
git add src/science_tool/validate/context.py tests/validate/test_context_body.py
git commit -m "feat(validate): ValidateContext.body via canonical split_frontmatter"
```

---

### Task 4: The `plan.correspondence-drift` check

The screen itself: under-claim only, permanent WARN, ungated, evidence-signed, project-relative path. Registered and covered by a registry test and a never-gates test.

**Files:**
- Create: `science/src/science_tool/validate/checks/correspondence_drift.py`
- Modify: `science/src/science_tool/validate/checks/__init__.py:25-80` (register `"correspondence_drift"`)
- Test: `science/tests/validate/test_checks_correspondence_drift.py`

**Interfaces:**
- Consumes: `ValidateContext.body` (Task 3); `extract_deliverables`/`extract_task_refs`, `probe_path`/`resolve_task`, `adjudicate`/`Adjudicated`, `ProbeResult` (Task 1); `evidence_signature` (Task 2); `Result`, `Severity`; `iter_entity_markdown`.
- Produces: `check_correspondence_drift(ctx: ValidateContext) -> Iterator[Result]`; rule `plan.correspondence-drift`.

- [ ] **Step 1: Write the failing tests**

Create `science/tests/validate/test_checks_correspondence_drift.py`:

```python
from __future__ import annotations

from pathlib import Path

from science_tool.validate.checks.correspondence_drift import check_correspondence_drift
from science_tool.validate.context import ValidateContext
from science_tool.validate.gates import cumulative_rules


def _plan(root: Path, rel: str, *, entity_id: str, status: str, body: str) -> None:
    p = root / "entities" / "plans" / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f'---\nid: "{entity_id}"\nkind: plan\ntitle: "T"\nstatus: "{status}"\n---\n\n{body}\n', encoding="utf-8")


def _run(root: Path):
    (root / "science.yaml").write_text("name: fixture\nprofile: research\n", encoding="utf-8")
    ctx = ValidateContext.from_project_root(root, strict=False, verbose=False)
    return list(check_correspondence_drift(ctx))


def test_draft_with_present_deliverable_fires_under_claim(tmp_path: Path):
    # One named deliverable, present, no task refs -> adjudicate() returns COMPLETE
    # (tasks_settled is vacuously true), and draft(0) < complete(2) is under-claim.
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("x = 1\n", encoding="utf-8")
    _plan(tmp_path, "0001-x.md", entity_id="plan:0001", status="draft", body="Builds `src/a.py`.")
    results = _run(tmp_path)
    assert len(results) == 1
    r = results[0]
    assert r.rule == "plan.correspondence-drift"
    assert r.severity.value == "warn"
    assert not r.path.is_absolute()  # project-relative
    assert "plan:0001" in r.message and "draft" in r.message and "complete" in r.message
    assert "evidence-signature: v1:" in r.message


def test_draft_with_partial_deliverables_fires_as_active(tmp_path: Path):
    # One present, one absent -> adjudicate() returns ACTIVE; draft(0) < active(1) is under-claim.
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("x = 1\n", encoding="utf-8")
    _plan(
        tmp_path, "0005-x.md", entity_id="plan:0005", status="draft",
        body="Builds `src/a.py` and `src/b.py`.",
    )
    results = _run(tmp_path)
    assert len(results) == 1
    assert "active" in results[0].message
    assert "src/a.py" in results[0].message and "src/b.py" in results[0].message


def test_draft_with_absent_deliverable_is_silent(tmp_path: Path):
    _plan(tmp_path, "0002-x.md", entity_id="plan:0002", status="draft", body="Will build `src/missing.py`.")
    assert not _run(tmp_path)


def test_complete_with_present_deliverable_is_silent(tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("x = 1\n", encoding="utf-8")
    _plan(tmp_path, "0003-x.md", entity_id="plan:0003", status="complete", body="Built `src/a.py`.")
    assert not _run(tmp_path)


def test_plan_naming_no_probeable_file_is_silent(tmp_path: Path):
    _plan(tmp_path, "0004-x.md", entity_id="plan:0004", status="draft", body="Some prose, no paths.")
    assert not _run(tmp_path)


def test_non_plan_kind_is_ignored(tmp_path: Path):
    p = tmp_path / "entities" / "hypotheses" / "0001-x.md"
    p.parent.mkdir(parents=True)
    p.write_text('---\nid: "hypothesis:0001"\nkind: hypothesis\ntitle: "T"\nstatus: "draft"\n---\n\nBuilds `src/a.py`.\n', encoding="utf-8")
    assert not _run(tmp_path)


def test_rule_is_never_gated(tmp_path: Path):
    assert "plan.correspondence-drift" not in cumulative_rules("hygiene")
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd science && uv run --frozen pytest tests/validate/test_checks_correspondence_drift.py -q`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implement the check**

Create `science/src/science_tool/validate/checks/correspondence_drift.py`:

```python
"""Screen a plan whose `status` UNDER-claims its real progress (design §4.3, §5).

Deterministic, advisory, and PERMANENT WARN: a screen that gates defeats its own
imperfect-but-cheap contract, so this never uses `severity_for_kind` and never
joins a gate tier. Findings feed `science entity review`; a confirmed false
positive is suppressed with an evidence-scoped `accepted_validation` entry (§5.5).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from science_tool.correspondence.adjudicate import Adjudicated, adjudicate
from science_tool.correspondence.extract import extract_deliverables, extract_task_refs
from science_tool.correspondence.probe import Probe, ProbeResult, TaskState, probe_path, resolve_task
from science_tool.correspondence.signature import evidence_signature
from science_tool.entity_scan import iter_entity_markdown
from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity

# draft < active < complete. Anything else (terminal, unknown) is off-axis: silent.
_LIFECYCLE_RANK = {"draft": 0, "active": 1, "complete": 2}

_RULE = "plan.correspondence-drift"


def _names(probes: list[Probe], result: ProbeResult) -> str:
    return ", ".join(p.target for p in probes if p.result is result) or "none"


def _drift_result(
    rel_path: Path,
    entity_id: str,
    claimed: str,
    adjudicated: Adjudicated,
    probes: list[Probe],
    task_states: list[tuple[str, TaskState]],
) -> Result:
    signature = evidence_signature(
        claimed=claimed, probes=probes, task_states=task_states, adjudicated=adjudicated.value
    )
    tasks_text = ", ".join(f"{ref}={state.value}" for ref, state in task_states) or "none"
    message = (
        f"{entity_id}: status {claimed!r} under-claims progress "
        f"(adjudicated {adjudicated.value!r}). "
        f"present: {_names(probes, ProbeResult.PRESENT)}; "
        f"absent: {_names(probes, ProbeResult.ABSENT)}; tasks: {tasks_text}. "
        f"Fix the status to {adjudicated.value!r}, or accept with an evidence-scoped "
        f"health.accepted_validation entry. evidence-signature: {signature}"
    )
    return Result(Severity.WARN, rel_path, None, message, _RULE, None)


@Check(section="plan correspondence drift", order=205)
def check_correspondence_drift(ctx: ValidateContext) -> Iterator[Result]:
    entities_root = ctx.project_root / "entities"
    if not entities_root.is_dir():
        return
    for path in iter_entity_markdown(entities_root):
        fm = ctx.frontmatter(path)
        kind, status = fm.get("kind"), fm.get("status")
        if kind != "plan" or not isinstance(status, str) or not status:
            continue
        claimed_rank = _LIFECYCLE_RANK.get(status)
        if claimed_rank is None:
            continue  # terminal / off-axis claimed status
        deliverables = extract_deliverables(ctx.body(path))
        if not deliverables:
            continue  # nothing probeable -> indeterminate -> silent
        probes = [probe_path(ctx.project_root, d) for d in deliverables]
        task_states = [(t, resolve_task(ctx.project_root, t)) for t in extract_task_refs(ctx.body(path))]
        adjudicated = adjudicate(
            [p.result for p in probes],
            [state for _ref, state in task_states],
            superseded=False,
        )
        adjudicated_rank = _LIFECYCLE_RANK.get(adjudicated.value)
        if adjudicated_rank is None:
            continue  # indeterminate / off-axis
        if claimed_rank < adjudicated_rank:  # UNDER-CLAIM
            entity_id = fm.get("id") if isinstance(fm.get("id"), str) else path.stem
            yield _drift_result(
                path.relative_to(ctx.project_root), entity_id, status, adjudicated, probes, task_states
            )
```

- [ ] **Step 4: Register the check**

In `science/src/science_tool/validate/checks/__init__.py`, add `"correspondence_drift"` to the `CANONICAL_CHECK_MODULES` tuple (append after `"materialization"`).

- [ ] **Step 5: Add the registry test**

Append to `science/tests/validate/test_checks_correspondence_drift.py`:

```python
def test_check_is_registered_canonically():
    from science_tool.validate.checks import CANONICAL_CHECKS, _load_canonical_checks

    _load_canonical_checks()
    fns = {entry.fn.__name__ for entry in CANONICAL_CHECKS}
    assert "check_correspondence_drift" in fns
```

- [ ] **Step 6: Run tests + types**

Run: `cd science && uv run --frozen pytest tests/validate/test_checks_correspondence_drift.py -q`
Expected: PASS (8 tests, including the registry test from Step 5).
Run: `cd science && uv run pyright && uv run ruff check`
Expected: 0 errors.

- [ ] **Step 7: Commit**

```bash
git add src/science_tool/validate/checks/correspondence_drift.py src/science_tool/validate/checks/__init__.py tests/validate/test_checks_correspondence_drift.py
git commit -m "feat(validate): plan.correspondence-drift screen (under-claim, advisory)"
```

---

### Task 5: Acceptance authority + evidence-scope policy

Make `validate.acceptance` the single authority: a field-based match predicate, `EVIDENCE_SCOPED_RULES`, an exact-token evidence-scope check, and a fail-closed `entry_suppresses`. `filter_accepted_warnings` delegates. (`graph.health` is wired in Task 7.)

**Files:**
- Modify: `science/src/science_tool/validate/acceptance.py` (whole file)
- Test: `science/tests/test_acceptance_authority.py`

**Interfaces:**
- Produces: `accepted_validation_entries(project_root: Path) -> list[dict[str, Any]]`; `entry_matches(entry, *, rule, severity, path, task, message) -> bool`; `entry_is_evidence_scoped(entry) -> bool`; `entry_suppresses(entry, *, rule, severity, path, task, message) -> bool`; `EVIDENCE_SCOPED_RULES: frozenset[str]`; `filter_accepted_warnings(project_root, results)` (unchanged signature).

- [ ] **Step 1: Write the failing tests**

Create `science/tests/test_acceptance_authority.py`:

```python
from __future__ import annotations

from pathlib import Path

from science_tool.validate.acceptance import (
    EVIDENCE_SCOPED_RULES,
    entry_is_evidence_scoped,
    entry_suppresses,
    filter_accepted_warnings,
)
from science_tool.validate.result import Result, Severity

_SIG = "v1:" + "a" * 64


def _warn(rule: str, path: str, message: str) -> Result:
    return Result(Severity.WARN, Path(path), None, message, rule, None)


def test_evidence_scoped_rule_is_declared():
    assert "plan.correspondence-drift" in EVIDENCE_SCOPED_RULES


def test_path_only_entry_does_not_suppress_the_scoped_rule():
    entry = {"rule": "plan.correspondence-drift", "path": "entities/plans/0001-x.md", "reason": "checked"}
    assert not entry_suppresses(
        entry, rule="plan.correspondence-drift", severity="warn",
        path="entities/plans/0001-x.md", task=None, message=f"... evidence-signature: {_SIG}",
    )


def test_valid_signature_entry_suppresses():
    entry = {
        "rule": "plan.correspondence-drift", "path": "entities/plans/0001-x.md",
        "reason": "input file, not a deliverable", "message_contains": f"evidence-signature: {_SIG}",
    }
    assert entry_suppresses(
        entry, rule="plan.correspondence-drift", severity="warn",
        path="entities/plans/0001-x.md", task=None, message=f"... evidence-signature: {_SIG}",
    )


def test_stale_signature_entry_does_not_suppress():
    entry = {
        "rule": "plan.correspondence-drift", "path": "entities/plans/0001-x.md",
        "reason": "was accepted", "message_contains": "evidence-signature: v1:" + "b" * 64,
    }
    assert not entry_suppresses(
        entry, rule="plan.correspondence-drift", severity="warn",
        path="entities/plans/0001-x.md", task=None, message=f"live evidence-signature: {_SIG}",
    )


def test_entry_is_evidence_scoped_requires_a_complete_token():
    assert not entry_is_evidence_scoped({"message_contains": "evidence-signature:"})
    assert not entry_is_evidence_scoped({"message_contains": "v1:short"})
    assert entry_is_evidence_scoped({"message_contains": f"x {_SIG} y"})


def test_other_rules_are_unaffected_by_evidence_scoping(tmp_path: Path):
    (tmp_path / "science.yaml").write_text(
        'name: f\nprofile: research\nhealth:\n  accepted_validation:\n'
        '    - rule: "code.metadata-gap"\n      path: "x.py"\n      reason: "ok"\n',
        encoding="utf-8",
    )
    kept = filter_accepted_warnings(tmp_path, [_warn("code.metadata-gap", "x.py", "gap")])
    assert kept == []  # a non-scoped rule still suppresses with a path-only entry
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_acceptance_authority.py -q`
Expected: FAIL (`ImportError` for the new names).

- [ ] **Step 3: Rewrite `acceptance.py` as the authority**

Replace `science/src/science_tool/validate/acceptance.py` with:

```python
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from science_tool.data_root import project_config_path
from science_tool.validate.result import Result, Severity

EVIDENCE_SCOPED_RULES: frozenset[str] = frozenset({"plan.correspondence-drift"})

# A complete, well-formed signature token — never the bare `evidence-signature:` prefix (§5.5).
_SIGNATURE_RE = re.compile(r"\bv1:[0-9a-f]{64}\b")


def accepted_validation_entries(project_root: Path) -> list[dict[str, Any]]:
    manifest_path = project_config_path(project_root)
    try:
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    except OSError:
        return []
    if not isinstance(manifest, dict):
        return []
    health = manifest.get("health")
    if not isinstance(health, dict):
        return []
    entries = health.get("accepted_validation")
    if not isinstance(entries, list):
        return []
    return [entry for entry in entries if isinstance(entry, dict)]


def _message_contains_values(needles: object) -> list[str]:
    if isinstance(needles, str):
        return [needles]
    if isinstance(needles, list):
        return [n for n in needles if isinstance(n, str)]
    return []


def _text_matches(value: str, needles: object) -> bool:
    if needles is None:
        return True
    if isinstance(needles, str):
        return needles in value
    if isinstance(needles, list):
        return all(isinstance(needle, str) and needle in value for needle in needles)
    return False


def _severity_matches(entry_severity: object, finding_severity: str) -> bool:
    if not isinstance(entry_severity, str):
        return True
    norm = "warn" if entry_severity in {"warn", "warning"} else entry_severity
    fnorm = "warn" if finding_severity in {"warn", "warning"} else finding_severity
    return norm == fnorm


def entry_matches(
    entry: dict[str, Any],
    *,
    rule: str | None,
    severity: str,
    path: str | None,
    task: str | None,
    message: str,
) -> bool:
    reason = entry.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        return False
    e_rule = entry.get("rule")
    if not isinstance(e_rule, str) or rule != e_rule:
        return False
    if not _severity_matches(entry.get("severity"), severity):
        return False
    e_path = entry.get("path")
    if isinstance(e_path, str) and path != e_path:
        return False
    e_task = entry.get("task")
    if isinstance(e_task, str) and task != e_task:
        return False
    return _text_matches(message, entry.get("message_contains"))


def entry_is_evidence_scoped(entry: dict[str, Any]) -> bool:
    return any(_SIGNATURE_RE.search(v) for v in _message_contains_values(entry.get("message_contains")))


def entry_suppresses(
    entry: dict[str, Any],
    *,
    rule: str | None,
    severity: str,
    path: str | None,
    task: str | None,
    message: str,
) -> bool:
    if not entry_matches(entry, rule=rule, severity=severity, path=path, task=task, message=message):
        return False
    if rule in EVIDENCE_SCOPED_RULES and not entry_is_evidence_scoped(entry):
        return False  # fail closed: an unscoped entry for this rule never suppresses
    return True


def filter_accepted_warnings(project_root: Path, results: list[Result]) -> list[Result]:
    entries = accepted_validation_entries(project_root)
    if not entries:
        return results
    kept: list[Result] = []
    for result in results:
        if result.severity is not Severity.WARN:
            kept.append(result)
            continue
        suppressed = any(
            entry_suppresses(
                entry,
                rule=result.rule,
                severity=result.severity.value,
                path=str(result.path) if result.path is not None else None,
                task=result.task,
                message=result.message,
            )
            for entry in entries
        )
        if not suppressed:
            kept.append(result)
    return kept
```

- [ ] **Step 4: Run the new tests + the existing acceptance callers**

Run: `cd science && uv run --frozen pytest tests/test_acceptance_authority.py -q`
Expected: PASS (6 tests).
Run: `cd science && uv run --frozen pytest tests/test_consolidate_acceptance.py tests/test_archive_acceptance.py -q`
Expected: PASS (no regression in existing `accepted_validation` users).

- [ ] **Step 5: Commit**

```bash
git add src/science_tool/validate/acceptance.py tests/test_acceptance_authority.py
git commit -m "feat(validate): acceptance authority with fail-closed evidence-scope policy"
```

---

### Task 6: Malformed-acceptance canonical check

A path-only (unscoped) acceptance entry for an evidence-scoped rule is itself a WARN — emitted as a canonical check, not appended inside the filter (which `cli.py` treats as removal-only).

**Files:**
- Create: `science/src/science_tool/validate/checks/accepted_validation.py`
- Modify: `science/src/science_tool/validate/checks/__init__.py` (register `"accepted_validation"`)
- Test: `science/tests/validate/test_checks_accepted_validation.py`

**Interfaces:**
- Consumes: `accepted_validation_entries`, `EVIDENCE_SCOPED_RULES`, `entry_is_evidence_scoped` (Task 5).
- Produces: `check_accepted_validation(ctx) -> Iterator[Result]`; rule `accepted-validation.evidence-scope-required`.

- [ ] **Step 1: Write the failing tests**

Create `science/tests/validate/test_checks_accepted_validation.py`:

```python
from __future__ import annotations

from pathlib import Path

from science_tool.validate.checks.accepted_validation import check_accepted_validation
from science_tool.validate.context import ValidateContext
from science_tool.validate.gates import cumulative_rules

_SIG = "v1:" + "a" * 64


def _ctx(root: Path, manifest_health: str) -> ValidateContext:
    (root / "science.yaml").write_text(f"name: f\nprofile: research\n{manifest_health}", encoding="utf-8")
    return ValidateContext.from_project_root(root, strict=False, verbose=False)


def test_unscoped_entry_for_scoped_rule_warns(tmp_path: Path):
    ctx = _ctx(
        tmp_path,
        'health:\n  accepted_validation:\n    - rule: "plan.correspondence-drift"\n'
        '      path: "entities/plans/0001-x.md"\n      reason: "x"\n',
    )
    results = list(check_accepted_validation(ctx))
    assert len(results) == 1
    assert results[0].rule == "accepted-validation.evidence-scope-required"
    assert results[0].severity.value == "warn"
    assert not results[0].path.is_absolute()


def test_scoped_entry_with_valid_signature_is_silent(tmp_path: Path):
    ctx = _ctx(
        tmp_path,
        'health:\n  accepted_validation:\n    - rule: "plan.correspondence-drift"\n'
        '      path: "entities/plans/0001-x.md"\n      reason: "x"\n'
        f'      message_contains: "evidence-signature: {_SIG}"\n',
    )
    assert not list(check_accepted_validation(ctx))


def test_unrelated_rule_entry_is_silent(tmp_path: Path):
    ctx = _ctx(
        tmp_path,
        'health:\n  accepted_validation:\n    - rule: "code.metadata-gap"\n'
        '      path: "x.py"\n      reason: "x"\n',
    )
    assert not list(check_accepted_validation(ctx))


def test_rule_is_never_gated(tmp_path: Path):
    assert "accepted-validation.evidence-scope-required" not in cumulative_rules("hygiene")
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd science && uv run --frozen pytest tests/validate/test_checks_accepted_validation.py -q`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implement the check**

Create `science/src/science_tool/validate/checks/accepted_validation.py`:

```python
"""Fail-closed guard: an `accepted_validation` entry for an evidence-scoped rule
must carry a complete evidence-signature token (design §5.5). This is a canonical
CHECK, not a filter side effect, because `validate/cli.py` treats acceptance
filtering as removal-only (`len(filtered) == len(original)`).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from science_tool.validate.acceptance import (
    EVIDENCE_SCOPED_RULES,
    accepted_validation_entries,
    entry_is_evidence_scoped,
)
from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity

_RULE = "accepted-validation.evidence-scope-required"


@Check(section="accepted-validation hygiene", order=206)
def check_accepted_validation(ctx: ValidateContext) -> Iterator[Result]:
    for entry in accepted_validation_entries(ctx.project_root):
        rule = entry.get("rule")
        if rule in EVIDENCE_SCOPED_RULES and not entry_is_evidence_scoped(entry):
            yield Result(
                Severity.WARN,
                Path("science.yaml"),
                None,
                f"accepted_validation entry for {rule!r} (path={entry.get('path')!r}) must be "
                f"evidence-scoped: message_contains needs a complete 'evidence-signature: v1:<64-hex>' "
                f"token, else it would blind that path even after the plan's deliverables change.",
                _RULE,
                None,
            )
```

- [ ] **Step 4: Register the check**

In `science/src/science_tool/validate/checks/__init__.py`, add `"accepted_validation"` to `CANONICAL_CHECK_MODULES` (after `"correspondence_drift"`).

- [ ] **Step 5: Run tests + types**

Run: `cd science && uv run --frozen pytest tests/validate/test_checks_accepted_validation.py -q`
Expected: PASS (4 tests).
Run: `cd science && uv run pyright && uv run ruff check`
Expected: 0 errors.

- [ ] **Step 6: Commit**

```bash
git add src/science_tool/validate/checks/accepted_validation.py src/science_tool/validate/checks/__init__.py tests/validate/test_checks_accepted_validation.py
git commit -m "feat(validate): accepted-validation evidence-scope guard check"
```

---

### Task 7: `graph.health` delegates to the acceptance authority

Remove health's independent copy of the matcher and route it through `validate.acceptance`, closing the hole where a path-only entry fails closed in `validate` but still suppresses in `health`.

**Files:**
- Modify: `science/src/science_tool/graph/health.py:135-173` (remove `_text_matches`, `_accepted_validation_entries`, `_accepts_validation_finding`; rewrite `_partition_accepted_validation_findings`)
- Test: `science/tests/test_health_acceptance_parity.py`

**Interfaces:**
- Consumes: `accepted_validation_entries`, `entry_suppresses` (Task 5).

- [ ] **Step 1: Write the failing parity test**

Create `science/tests/test_health_acceptance_parity.py`:

```python
from __future__ import annotations

from pathlib import Path

from science_tool.graph.health import _partition_accepted_validation_findings

_SIG = "v1:" + "a" * 64


def _finding(rule: str, path: str, message: str) -> dict:
    return {"severity": "warn", "path": path, "line": None, "message": message, "rule": rule, "task": None}


def _manifest(root: Path, health: str) -> None:
    (root / "science.yaml").write_text(f"name: f\nprofile: research\n{health}", encoding="utf-8")


def test_path_only_entry_does_not_suppress_scoped_rule_in_health(tmp_path: Path):
    _manifest(
        tmp_path,
        'health:\n  accepted_validation:\n    - rule: "plan.correspondence-drift"\n'
        '      path: "entities/plans/0001-x.md"\n      reason: "x"\n',
    )
    finding = _finding("plan.correspondence-drift", "entities/plans/0001-x.md", f"... evidence-signature: {_SIG}")
    remaining, accepted = _partition_accepted_validation_findings(tmp_path, [finding])
    assert remaining == [finding] and accepted == []


def test_valid_signature_entry_suppresses_in_health(tmp_path: Path):
    _manifest(
        tmp_path,
        'health:\n  accepted_validation:\n    - rule: "plan.correspondence-drift"\n'
        '      path: "entities/plans/0001-x.md"\n      reason: "input not deliverable"\n'
        f'      message_contains: "evidence-signature: {_SIG}"\n',
    )
    finding = _finding("plan.correspondence-drift", "entities/plans/0001-x.md", f"... evidence-signature: {_SIG}")
    remaining, accepted = _partition_accepted_validation_findings(tmp_path, [finding])
    assert remaining == [] and len(accepted) == 1
    assert accepted[0]["accepted_reason"] == "input not deliverable"
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_health_acceptance_parity.py -q`
Expected: FAIL (path-only currently suppresses in health → first test fails).

- [ ] **Step 3: Rewrite health's partition to delegate**

In `science/src/science_tool/graph/health.py`, delete `_text_matches` (135-142), `_accepted_validation_entries` (145-157), and `_accepts_validation_finding` (160-173). Add the import near the other `science_tool.validate` imports:

```python
from science_tool.validate.acceptance import accepted_validation_entries, entry_suppresses
```

Replace `_partition_accepted_validation_findings` with:

```python
def _partition_accepted_validation_findings(
    project_root: Path,
    findings: list[ValidationFinding],
) -> tuple[list[ValidationFinding], list[AcceptedValidationFinding]]:
    entries = accepted_validation_entries(project_root)
    if not entries:
        return findings, []
    remaining: list[ValidationFinding] = []
    accepted: list[AcceptedValidationFinding] = []
    for finding in findings:
        match = next(
            (
                entry
                for entry in entries
                if entry_suppresses(
                    entry,
                    rule=finding.get("rule"),
                    severity=finding.get("severity") or "",
                    path=finding.get("path"),
                    task=finding.get("task"),
                    message=finding.get("message") or "",
                )
            ),
            None,
        )
        if match is None:
            remaining.append(finding)
            continue
        reason = match.get("reason")
        accepted.append({**finding, "accepted_reason": str(reason).strip()})
    return remaining, accepted
```

Then remove the two imports that only the deleted helpers used — `import yaml as _yaml` (line 14) and `from science_tool.data_root import project_config_path` (line 16). Both are dead after this change (their sole uses were the deleted `_accepted_validation_entries` at lines 146/148); `ruff` will flag them if any live use remains, so re-run lint before committing.

- [ ] **Step 4: Run the parity test + the health suite**

Run: `cd science && uv run --frozen pytest tests/test_health_acceptance_parity.py -q`
Expected: PASS.
Run: `cd science && uv run --frozen pytest -k health -q && uv run pyright`
Expected: PASS, 0 type errors.

- [ ] **Step 5: Commit**

```bash
git add src/science_tool/graph/health.py tests/test_health_acceptance_parity.py
git commit -m "refactor(health): delegate accepted_validation to validate.acceptance authority"
```

---

### Task 8: Downstream verification (CLI exit-code + real project)

Two separated concerns; never assert on the full downstream suite's exit code.

**Files:**
- Test: `science/tests/test_correspondence_drift_cli.py`
- Test: `science/tests/test_correspondence_drift_real_projects.py`

**Interfaces:**
- Consumes: the `validate` CLI (`science validate`), the check (Task 4).

- [ ] **Step 1: Write the synthetic CLI exit-code test**

Create `science/tests/test_correspondence_drift_cli.py`:

```python
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _project(root: Path) -> None:
    (root / "science.yaml").write_text("name: fixture\nprofile: research\n", encoding="utf-8")
    (root / "src").mkdir()
    (root / "src" / "a.py").write_text("x = 1\n", encoding="utf-8")
    p = root / "entities" / "plans" / "0001-x.md"
    p.parent.mkdir(parents=True)
    p.write_text('---\nid: "plan:0001"\nkind: plan\ntitle: "T"\nstatus: "draft"\n---\n\nBuilds `src/a.py`.\n', encoding="utf-8")


def test_drift_warn_exits_zero_even_at_top_fail_on_tier(tmp_path: Path):
    _project(tmp_path)
    proc = subprocess.run(
        [sys.executable, "-m", "science_tool", "validate", "--fail-on", "hygiene", "--format", "json"],
        cwd=tmp_path, capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    rules = [r["rule"] for r in payload["results"]]
    assert "plan.correspondence-drift" in rules
```

(`python -m science_tool` is a valid entrypoint — `src/science_tool/__main__.py` exists and `pyproject.toml` declares `science = "science_tool.cli:main"`. `subprocess` here runs the CLI in a real process so the `--fail-on` exit code is exercised end to end, not just the check function.)

- [ ] **Step 2: Run it**

Run: `cd science && uv run --frozen pytest tests/test_correspondence_drift_cli.py -q`
Expected: PASS. If it fails on the entrypoint, fix the argv per the note and re-run.

- [ ] **Step 3: Write the `real_projects`-marked test**

Create `science/tests/test_correspondence_drift_real_projects.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.validate.checks.correspondence_drift import check_correspondence_drift
from science_tool.validate.context import ValidateContext

_MM = Path.home() / "d" / "cancer" / "cancer-types" / "multiple-myeloma"


@pytest.mark.real_projects
def test_detector_fires_on_multiple_myeloma():
    if not (_MM / "science.yaml").is_file():
        pytest.skip(f"multiple-myeloma not present at {_MM}")
    ctx = ValidateContext.from_project_root(_MM, strict=False, verbose=False)
    results = [r for r in check_correspondence_drift(ctx) if r.rule == "plan.correspondence-drift"]
    assert len(results) >= 1
    assert all(r.severity.value == "warn" for r in results)
    assert all(not r.path.is_absolute() for r in results)
```

- [ ] **Step 4: Run it (opt-in marker)**

Run: `cd science && uv run --frozen pytest tests/test_correspondence_drift_real_projects.py -m real_projects -q`
Expected: PASS (calibration expects ≈70 candidates; the assertion is a floor of ≥1). If multiple-myeloma is absent, the test skips — that is acceptable.

- [ ] **Step 5: Commit**

```bash
git add tests/test_correspondence_drift_cli.py tests/test_correspondence_drift_real_projects.py
git commit -m "test(validate): correspondence-drift CLI exit-0 and real-project firing"
```

---

### Task 9: `result.md` label correction (label-only)

Correct the confusion-matrix label and the dominant-cell narrative. The pre-registered numbers, Manski bounds, θ, and DEMONSTRATE gate are unchanged.

**Files:**
- Modify: `docs/plans/2026-07-17-drift-sample/result.md:36,41`

- [ ] **Step 1: Fix the matrix label**

In `docs/plans/2026-07-17-drift-sample/result.md`, the confusion-matrix row for `active → complete` currently reads `over-claim`. Change its label to `**mismatch** (stale under-claim)` so it matches the `draft → …` under-claim rows. Leave the `complete → active` row as over-claim.

- [ ] **Step 2: Fix the dominant-cell sentence**

Change line 41 from "The mass is **stale under-claim**: 19 plans assert `draft` while their promised deliverables already exist." to:

```
The mass is **stale under-claim**: 20 under-claims — 19 `draft` claims plus one `active` claim —
while their promised deliverables already exist.
```

- [ ] **Step 3: Sanity-check nothing else moved**

Run: `cd /mnt/ssd/Dropbox/science/.worktrees/plan-correspondence-drift-screen && git diff --stat docs/plans/2026-07-17-drift-sample/result.md`
Expected: one file changed, a small line delta (labels + one sentence). No change to the headline table (n, k_lo, k_hi, θ, gate).

- [ ] **Step 4: Commit**

```bash
git add docs/plans/2026-07-17-drift-sample/result.md
git commit -m "docs(drift-sample): correct active->complete as under-claim (label-only)"
```

---

## Final verification

- [ ] Run the whole suite + lint + types from a clean tree:

```bash
cd science && uv run --frozen pytest -q && uv run ruff check && uv run pyright
```
Expected: all pass, 0 lint, 0 type errors.

- [ ] Confirm both new rules gate nothing:

```bash
cd science && uv run --frozen python -c "from science_tool.validate.gates import cumulative_rules; g=cumulative_rules('hygiene'); assert 'plan.correspondence-drift' not in g and 'accepted-validation.evidence-scope-required' not in g; print('ungated ok')"
```
Expected: `ungated ok`

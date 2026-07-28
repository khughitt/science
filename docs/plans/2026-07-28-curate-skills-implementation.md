# `/curate-skills` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship `science skills curate` (a deterministic report-only/`--apply` CLI that triages `uncovered` skill-coverage gaps into `science feedback`) and the `/curate-skills` agent command that wraps it.

**Architecture:** A pure correlation core in `science_tool/skills_coverage/curate.py` (candidates × feedback entries → a filing plan), an apply executor that writes feedback, a text/JSON serializer, a Click command on the existing `skills` group, and a generated agent command. No new `science_model` types — it reuses `science_model.skill_coverage` and `science_tool.feedback`.

**Tech Stack:** Python 3.11+, Click, Pydantic (via existing `feedback` models), pytest.

## Global Constraints

- All `uv`/`pytest`/`ruff`/`pyright` commands run from **`science/`**, never the repo root (`cd science && uv run --frozen …`).
- Conventional commits; **no AI-attribution trailer or footer** on any commit.
- Only **`uncovered`** candidates are filed. Feedback field values are fixed: `target = "skill-coverage:<term>"`, `project = "science"`, `category = "gap"`, `concern = "tooling"`.
- Correlation match key is **`(normalize_target(entry.target), entry.concern == "tooling")`** — never a raw `fnmatch` namespace glob, never target-only.
- **Fail early** on more than one *open* match for a term (raise, nonzero exit, no writes).
- A match's `status` must be `open` or a known resolved status (`addressed`, `deferred`, `wontfix`). `FeedbackEntry.status` is an unvalidated `str`; any other value is a hard error, never silently treated as resolved/SKIP.
- When `--output` is set, its parent directory is verified **before** any feedback write, so a failed report-write can never follow a committed `--apply` (which would double-record on retry).
- `recurrence_after` is **always present** in a result = the entry's `recurrence` after the write. `FeedbackEntry` seeds one occurrence for every entry (validator floor 1), so a NEW entry is `recurrence_after: 1` and a RECUR is prior + 1.
- Default is report-only (writes nothing). `--term` is `--apply`-only. An unknown `--term` is a hard error.
- No skill files are authored; the only side effect is under `~/.config/science/feedback` (or `$SCIENCE_FEEDBACK_DIR`).
- After the command file lands, regenerate agent assets (`science agents generate`) and the committed-mirror equality test must pass.
- Design of record: [`2026-07-28-curate-skills-design.md`](2026-07-28-curate-skills-design.md).

---

### Task 1: Pure correlation core — types, `build_curate_plan`, context helper

**Files:**
- Create: `science/src/science_tool/skills_coverage/curate.py`
- Test: `science/tests/skills_coverage/test_curate_plan.py`

**Interfaces:**
- Consumes: `science_model.skill_coverage.coverage.Candidate` (`.proposed_scope`, `.likely_archetype`, `.score`, `.evidence[]` of `EvidenceTriple{project, plan_ref, dataset_ref}`) and `.CoverageReport`; `science_tool.feedback.FeedbackEntry`, `normalize_target`.
- Produces: `ExistingMatch`, `CurateRow`, `CurateContext`, `CuratePlan`, `CurateConflictError`, `CurateStatusError`; `build_curate_plan(candidates, entries, context, scope) -> CuratePlan`; `coverage_context(report) -> CurateContext`. Later tasks rely on these exact names.

- [ ] **Step 1: Write the failing test**

```python
# science/tests/skills_coverage/test_curate_plan.py
from __future__ import annotations

import pytest

from science_model.skill_coverage.coverage import Candidate, EvidenceTriple
from science_tool.feedback import FeedbackEntry
from science_tool.skills_coverage.curate import (
    CurateConflictError,
    CurateContext,
    CurateStatusError,
    build_curate_plan,
)


def _cand(term: str, *, score: float = 0.5, projects=(("p1", "plan:a"),)) -> Candidate:
    evidence = tuple(
        EvidenceTriple(project=proj, plan_ref=plan, dataset_ref="dataset:d")
        for proj, plan in projects
    )
    return Candidate(proposed_scope=term, likely_archetype="measurement-qa", score=score, evidence=evidence)


def _entry(target: str, *, status: str = "open", concern: str = "tooling", n: int = 0) -> FeedbackEntry:
    # `n` gives each fixture entry a distinct id; two entries that share a target
    # must still be two rows, so the conflict/status paths get real, non-colliding ids.
    return FeedbackEntry(id=f"fb-2026-07-28-{100 + n:03d}",
                         target=target, summary="s", concern=concern, status=status, category="gap")


_CTX = CurateContext(covered_not_loaded=0, unmapped=0, skipped_projects=())
_SCOPE = {"mode": "portfolio"}


def test_new_when_no_match() -> None:
    plan = build_curate_plan([_cand("data-product:x")], [], _CTX, _SCOPE)
    assert plan.mode == "report"
    assert [(r.term, r.disposition) for r in plan.rows] == [("data-product:x", "new")]
    assert plan.rows[0].existing == ()


def test_recur_when_open_match() -> None:
    entries = [_entry("skill-coverage:data-product:x", status="open")]
    plan = build_curate_plan([_cand("data-product:x")], entries, _CTX, _SCOPE)
    assert plan.rows[0].disposition == "recur"
    assert [m.status for m in plan.rows[0].existing] == ["open"]


def test_normalized_target_dedup() -> None:
    entries = [_entry("Skill-Coverage:data-product:x", status="open")]
    plan = build_curate_plan([_cand("data-product:x")], entries, _CTX, _SCOPE)
    assert plan.rows[0].disposition == "recur"  # case variant still matches


def test_cross_concern_is_not_a_match() -> None:
    entries = [
        _entry("skill-coverage:data-product:x", status="open", concern="methodology:qa", n=0),
        _entry("skill-coverage:data-product:x", status="open", concern="methodology:qa", n=1),
    ]
    plan = build_curate_plan([_cand("data-product:x")], entries, _CTX, _SCOPE)
    assert plan.rows[0].disposition == "new"  # different concern ignored, no conflict


def test_multiple_open_fails_early() -> None:
    entries = [
        _entry("skill-coverage:data-product:x", status="open", n=0),
        _entry("skill-coverage:data-product:x", status="open", n=1),
    ]
    with pytest.raises(CurateConflictError) as exc:
        build_curate_plan([_cand("data-product:x")], entries, _CTX, _SCOPE)
    assert exc.value.ids == ["fb-2026-07-28-100", "fb-2026-07-28-101"]  # both, sorted
    assert "merge" in str(exc.value)


def test_unknown_status_fails_early() -> None:
    # status is an unvalidated str on FeedbackEntry; an unexpected value must not
    # silently bucket as resolved/SKIP.
    entries = [_entry("skill-coverage:data-product:x", status="bogus")]
    with pytest.raises(CurateStatusError):
        build_curate_plan([_cand("data-product:x")], entries, _CTX, _SCOPE)


def test_skip_addressed_conflict_lists_all_resolved() -> None:
    entries = [
        _entry("skill-coverage:data-product:x", status="wontfix"),
        _entry("skill-coverage:data-product:x", status="addressed"),
    ]
    plan = build_curate_plan([_cand("data-product:x")], entries, _CTX, _SCOPE)
    row = plan.rows[0]
    assert row.disposition == "skip-addressed-conflict"
    assert sorted(m.status for m in row.existing) == ["addressed", "wontfix"]


def test_open_plus_resolved_is_recur_listing_both() -> None:
    entries = [
        _entry("skill-coverage:data-product:x", status="open"),
        _entry("skill-coverage:data-product:x", status="wontfix"),
    ]
    plan = build_curate_plan([_cand("data-product:x")], entries, _CTX, _SCOPE)
    row = plan.rows[0]
    assert row.disposition == "recur"
    assert sorted(m.status for m in row.existing) == ["open", "wontfix"]


def test_counts_and_ordering() -> None:
    cands = [
        _cand("data-product:a", score=0.2, projects=(("p1", "plan:a"),)),
        _cand("data-product:b", score=0.9, projects=(("p1", "plan:a"), ("p2", "plan:b"))),
    ]
    plan = build_curate_plan(cands, [], _CTX, _SCOPE)
    assert [r.term for r in plan.rows] == ["data-product:b", "data-product:a"]  # score desc
    assert (plan.rows[0].n_plans, plan.rows[0].n_projects) == (2, 2)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run --frozen pytest tests/skills_coverage/test_curate_plan.py -q`
Expected: FAIL (`ModuleNotFoundError: science_tool.skills_coverage.curate`).

- [ ] **Step 3: Write the implementation**

```python
# science/src/science_tool/skills_coverage/curate.py
"""Correlate uncovered coverage candidates against the feedback store into a filing plan.

Pure over its inputs (candidates + already-loaded feedback entries): no I/O, no
scan. The apply executor and serializer live in this module too, but this section
never writes.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from science_tool.feedback import normalize_target

if TYPE_CHECKING:
    from science_model.skill_coverage.coverage import Candidate, CoverageReport
    from science_tool.feedback import FeedbackEntry

CONCERN = "tooling"
CATEGORY = "gap"
PROJECT = "science"
RESOLVED_STATUSES = ("addressed", "deferred", "wontfix")  # mirrors feedback.VALID_STATUSES minus "open"


def target_for(term: str) -> str:
    return f"skill-coverage:{term}"


class CurateConflictError(Exception):
    """More than one open feedback entry shares a term — the store must be merged first."""

    def __init__(self, term: str, ids: list[str]) -> None:
        self.term = term
        self.ids = ids
        super().__init__(
            f"{term}: {len(ids)} open skill-coverage entries ({', '.join(ids)}); "
            "merge them before curating"
        )


class CurateStatusError(Exception):
    """A matched feedback entry carries a status outside the known vocabulary."""

    def __init__(self, term: str, offenders: list[tuple[str, str]]) -> None:
        self.term = term
        self.offenders = offenders
        detail = ", ".join(f"{eid}={status!r}" for eid, status in offenders)
        super().__init__(
            f"{term}: feedback entries with unknown status ({detail}); "
            f"expected open or one of {', '.join(RESOLVED_STATUSES)}"
        )


class CurateSelectionError(Exception):
    """A --term value names no row in the current plan."""

    def __init__(self, unknown: list[str]) -> None:
        self.unknown = unknown
        super().__init__(f"--term names no candidate in the current plan: {', '.join(unknown)}")


@dataclass(frozen=True, slots=True)
class ExistingMatch:
    id: str
    status: str

    def to_dict(self) -> dict[str, str]:
        return {"id": self.id, "status": self.status}


@dataclass
class CurateRow:
    term: str
    disposition: str  # new | recur | skip | skip-addressed-conflict
    score: float
    likely_archetype: str
    n_plans: int
    n_projects: int
    existing: tuple[ExistingMatch, ...]
    applied: bool | None = None
    result: dict[str, object] | None = None
    candidate: "Candidate | None" = field(default=None, repr=False, compare=False)

    def to_dict(self) -> dict[str, object]:
        out: dict[str, object] = {
            "term": self.term,
            "disposition": self.disposition,
            "score": self.score,
            "likely_archetype": self.likely_archetype,
            "n_plans": self.n_plans,
            "n_projects": self.n_projects,
            "existing": [m.to_dict() for m in self.existing],
        }
        if self.applied is not None:
            out["applied"] = self.applied
        if self.result is not None:
            out["result"] = self.result
        return out


@dataclass(frozen=True, slots=True)
class CurateContext:
    covered_not_loaded: int
    unmapped: int
    skipped_projects: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "covered_not_loaded": self.covered_not_loaded,
            "unmapped": self.unmapped,
            "skipped_projects": list(self.skipped_projects),
        }


@dataclass
class CuratePlan:
    mode: str  # report | apply
    scope: dict[str, object]
    rows: list[CurateRow]
    context: CurateContext

    def to_dict(self) -> dict[str, object]:
        return {
            "mode": self.mode,
            "scope": self.scope,
            "rows": [r.to_dict() for r in self.rows],
            "context": self.context.to_dict(),
        }


def coverage_context(report: "CoverageReport") -> CurateContext:
    cnl = sum(1 for o in report.coverage_occurrences if o.to_dict().get("state") == "covered-not-loaded")
    unmapped = sum(1 for o in report.coverage_occurrences if o.to_dict().get("state") == "unmapped")
    return CurateContext(cnl, unmapped, tuple(s.path for s in report.skipped_projects))


def build_curate_plan(
    candidates: "Sequence[Candidate]",
    entries: "Sequence[FeedbackEntry]",
    context: CurateContext,
    scope: "Mapping[str, object]",
) -> CuratePlan:
    by_norm: dict[str, list[FeedbackEntry]] = defaultdict(list)
    for entry in entries:
        if entry.concern != CONCERN:
            continue
        by_norm[normalize_target(entry.target)].append(entry)

    rows: list[CurateRow] = []
    for cand in sorted(candidates, key=lambda c: (-c.score, c.proposed_scope)):
        term = cand.proposed_scope
        matches = by_norm.get(normalize_target(target_for(term)), [])
        opens = [m for m in matches if m.status == "open"]
        resolved = [m for m in matches if m.status in RESOLVED_STATUSES]
        unknown = [m for m in matches if m.status != "open" and m.status not in RESOLVED_STATUSES]
        if unknown:
            raise CurateStatusError(term, sorted((m.id, m.status) for m in unknown))
        if len(opens) > 1:
            raise CurateConflictError(term, sorted(m.id for m in opens))
        if opens:
            disposition = "recur"
        elif any(m.status == "addressed" for m in resolved):
            disposition = "skip-addressed-conflict"
        elif resolved:
            disposition = "skip"
        else:
            disposition = "new"
        existing = tuple(
            ExistingMatch(m.id, m.status) for m in sorted(matches, key=lambda m: m.id)
        )
        rows.append(
            CurateRow(
                term=term,
                disposition=disposition,
                score=cand.score,
                likely_archetype=cand.likely_archetype,
                n_plans=len({(t.project, t.plan_ref) for t in cand.evidence}),
                n_projects=len({t.project for t in cand.evidence}),
                existing=existing,
                candidate=cand,
            )
        )
    return CuratePlan(mode="report", scope=dict(scope), rows=rows, context=context)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/skills_coverage/test_curate_plan.py -q`
Expected: PASS (9 tests).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/skills_coverage/curate.py science/tests/skills_coverage/test_curate_plan.py
git commit -m "feat(skills-curate): correlate uncovered candidates into a filing plan"
```

---

### Task 2: Apply executor — write NEW / RECUR, honor selection and skip

**Files:**
- Modify: `science/src/science_tool/skills_coverage/curate.py`
- Test: `science/tests/skills_coverage/test_curate_apply.py`

**Interfaces:**
- Consumes: `science_tool.feedback` (`FeedbackEntry`, `record_occurrence`, `save_entry`, `next_feedback_id`, `load_entry`); Task 1 `CuratePlan`, `CurateRow`, `CurateSelectionError`, constants.
- Produces: `apply_plan(plan, feedback_dir, *, today, selected_terms=None) -> CuratePlan` (mutates rows: sets `applied` and `result`, `plan.mode = "apply"`).

- [ ] **Step 1: Write the failing test**

```python
# science/tests/skills_coverage/test_curate_apply.py
from __future__ import annotations

from pathlib import Path

import pytest

from science_model.skill_coverage.coverage import Candidate, EvidenceTriple
from science_tool.feedback import FeedbackEntry, list_entries, load_all_entries, save_entry
from science_tool.skills_coverage.curate import (
    CurateContext,
    CurateSelectionError,
    apply_plan,
    build_curate_plan,
)

_CTX = CurateContext(0, 0, ())
_SCOPE = {"mode": "portfolio"}


def _cand(term: str, *, projects=(("p1", "plan:a"),)) -> Candidate:
    return Candidate(
        proposed_scope=term,
        likely_archetype="measurement-qa",
        score=0.5,
        evidence=tuple(EvidenceTriple(project=p, plan_ref=pl, dataset_ref="dataset:d") for p, pl in projects),
    )


def _open_entry(term: str) -> FeedbackEntry:
    return FeedbackEntry(id="fb-2026-07-28-500", target=f"skill-coverage:{term}",
                         summary="s", concern="tooling", category="gap", status="open")


def test_apply_new_creates_entry_with_fixed_fields(tmp_path: Path) -> None:
    plan = build_curate_plan([_cand("data-product:x", projects=(("p1", "plan:a"), ("p2", "plan:b")))], [], _CTX, _SCOPE)
    apply_plan(plan, tmp_path, today="2026-07-28")
    assert plan.mode == "apply"
    row = plan.rows[0]
    assert row.applied is True
    assert row.result["action"] == "created"
    assert row.result["recurrence_after"] == 1  # validator seeds one occurrence
    [entry] = load_all_entries(tmp_path)
    assert entry.target == "skill-coverage:data-product:x"
    assert (entry.project, entry.category, entry.concern) == ("science", "gap", "tooling")
    assert "2 plans / 2 projects" in entry.summary


def test_apply_recur_records_occurrence_with_metadata(tmp_path: Path) -> None:
    save_entry(tmp_path, _open_entry("data-product:x"))  # persisted -> recurrence 1 (seeded)
    plan = build_curate_plan([_cand("data-product:x")], list_entries(tmp_path, status=None), _CTX, _SCOPE)
    apply_plan(plan, tmp_path, today="2026-07-28")
    row = plan.rows[0]
    assert row.result == {"action": "recurred", "id": "fb-2026-07-28-500", "recurrence_after": 2}
    [entry] = load_all_entries(tmp_path)
    assert entry.recurrence == 2  # seeded 1 + one recurrence
    occ = entry.occurrences[-1]
    assert (occ.project, occ.category) == ("science", "gap")
    assert occ.detail is not None
    assert "score:" in occ.detail and "p1 / plan:a" in occ.detail  # evidence snapshot recorded


def test_apply_recur_targets_the_open_entry_when_resolved_also_present(tmp_path: Path) -> None:
    # A term with one open + one resolved entry recurs against the OPEN id, not the resolved one.
    save_entry(tmp_path, _open_entry("data-product:x"))  # id fb-2026-07-28-500, open
    save_entry(tmp_path, FeedbackEntry(id="fb-2026-07-28-400", target="skill-coverage:data-product:x",
                                       summary="s", concern="tooling", category="gap", status="wontfix"))
    plan = build_curate_plan([_cand("data-product:x")], list_entries(tmp_path, status=None), _CTX, _SCOPE)
    apply_plan(plan, tmp_path, today="2026-07-28")
    assert plan.rows[0].result == {"action": "recurred", "id": "fb-2026-07-28-500", "recurrence_after": 2}


def test_apply_twice_from_empty_is_new_then_recur(tmp_path: Path) -> None:
    # First apply on an empty store -> NEW (recurrence 1); second -> RECUR (recurrence 2).
    plan1 = build_curate_plan([_cand("data-product:x")], list_entries(tmp_path, status=None), _CTX, _SCOPE)
    apply_plan(plan1, tmp_path, today="2026-07-28")
    assert plan1.rows[0].result["action"] == "created"
    plan2 = build_curate_plan([_cand("data-product:x")], list_entries(tmp_path, status=None), _CTX, _SCOPE)
    apply_plan(plan2, tmp_path, today="2026-07-28")
    assert plan2.rows[0].result == {
        "action": "recurred",
        "id": plan1.rows[0].result["id"],
        "recurrence_after": 2,
    }
    [entry] = load_all_entries(tmp_path)  # one entry, never a duplicate
    assert entry.recurrence == 2


def test_scoped_apply_writes_only_selected(tmp_path: Path) -> None:
    cands = [_cand("data-product:a"), _cand("data-product:b")]
    plan = build_curate_plan(cands, [], _CTX, _SCOPE)
    apply_plan(plan, tmp_path, today="2026-07-28", selected_terms={"data-product:a"})
    by_term = {r.term: r for r in plan.rows}
    assert by_term["data-product:a"].applied is True
    assert by_term["data-product:b"].applied is False and by_term["data-product:b"].result is None
    assert {e.target for e in load_all_entries(tmp_path)} == {"skill-coverage:data-product:a"}


def test_unknown_selected_term_raises(tmp_path: Path) -> None:
    plan = build_curate_plan([_cand("data-product:a")], [], _CTX, _SCOPE)
    with pytest.raises(CurateSelectionError):
        apply_plan(plan, tmp_path, today="2026-07-28", selected_terms={"data-product:zzz"})


def test_skip_row_writes_nothing(tmp_path: Path) -> None:
    resolved = FeedbackEntry(id="fb-2026-07-28-600", target="skill-coverage:data-product:x",
                             summary="s", concern="tooling", category="gap", status="wontfix")
    save_entry(tmp_path, resolved)
    plan = build_curate_plan([_cand("data-product:x")], list_entries(tmp_path, status=None), _CTX, _SCOPE)
    apply_plan(plan, tmp_path, today="2026-07-28")
    row = plan.rows[0]
    assert row.disposition == "skip" and row.applied is False and row.result is None
    entries = load_all_entries(tmp_path)
    assert len(entries) == 1 and entries[0].id == "fb-2026-07-28-600" and entries[0].recurrence == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run --frozen pytest tests/skills_coverage/test_curate_apply.py -q`
Expected: FAIL (`ImportError: cannot import name 'apply_plan'`).

- [ ] **Step 3: Add the implementation to `curate.py`**

Append to `science/src/science_tool/skills_coverage/curate.py`. First, replace the
Task 1 header line `from science_tool.feedback import normalize_target` with the
full runtime import below, and **remove `FeedbackEntry` from the `TYPE_CHECKING`
block** (it is now imported at runtime; `normalize_target` must not be listed
twice):

```python
from science_tool.feedback import (
    FeedbackEntry,
    load_entry,
    next_feedback_id,
    normalize_target,
    record_occurrence,
    save_entry,
)
```

```python
# append at end of module

def _summary(row: CurateRow) -> str:
    return f"skill corpus lacks coverage for {row.term} ({row.n_plans} plans / {row.n_projects} projects)"


def _detail(row: CurateRow) -> str:
    cand = row.candidate
    assert cand is not None  # rows created by build_curate_plan always carry their candidate
    lines = [
        f"score: {cand.score}",
        f"likely_archetype: {cand.likely_archetype}",
        "evidence:",
    ]
    for triple in cand.evidence:
        lines.append(f"  - {triple.project} / {triple.plan_ref} / {triple.dataset_ref}")
    return "\n".join(lines)


def _open_id(row: CurateRow) -> str:
    return next(m.id for m in row.existing if m.status == "open")


def apply_plan(
    plan: CuratePlan,
    feedback_dir: Path,
    *,
    today: str,
    selected_terms: set[str] | None = None,
) -> CuratePlan:
    if selected_terms is not None:
        unknown = sorted(selected_terms - {row.term for row in plan.rows})
        if unknown:
            raise CurateSelectionError(unknown)

    plan.mode = "apply"
    for row in plan.rows:
        if row.disposition in ("skip", "skip-addressed-conflict"):
            row.applied = False
            continue
        if selected_terms is not None and row.term not in selected_terms:
            row.applied = False
            continue
        if row.disposition == "recur":
            entry = load_entry(feedback_dir / f"{_open_id(row)}.yaml")
            record_occurrence(entry, date=today, project=PROJECT, category=CATEGORY, detail=_detail(row))
            save_entry(feedback_dir, entry)
            row.result = {"action": "recurred", "id": entry.id, "recurrence_after": entry.recurrence}
        else:  # new
            entry = FeedbackEntry(
                id=next_feedback_id(feedback_dir, today),
                created=today,
                project=PROJECT,
                target=target_for(row.term),
                category=CATEGORY,
                summary=_summary(row),
                detail=_detail(row),
                concern=CONCERN,
            )
            save_entry(feedback_dir, entry)
            row.result = {"action": "created", "id": entry.id, "recurrence_after": entry.recurrence}
        row.applied = True
    return plan
```

`Path` needs importing — add `from pathlib import Path` to the module header.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/skills_coverage/test_curate_apply.py tests/skills_coverage/test_curate_plan.py -q`
Expected: PASS (16 tests: 7 apply + 9 plan).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/skills_coverage/curate.py science/tests/skills_coverage/test_curate_apply.py
git commit -m "feat(skills-curate): apply plan to feedback (create/recur, scoped, skip)"
```

---

### Task 3: Serialize the plan — text and canonical JSON

**Files:**
- Modify: `science/src/science_tool/skills_coverage/curate.py`
- Test: `science/tests/skills_coverage/test_curate_serialize.py`

**Interfaces:**
- Produces: `serialize_curate_plan(plan, fmt) -> str` (`fmt in {"text", "json"}`).

- [ ] **Step 1: Write the failing test**

```python
# science/tests/skills_coverage/test_curate_serialize.py
from __future__ import annotations

import json

from science_model.skill_coverage.coverage import Candidate, EvidenceTriple
from science_tool.skills_coverage.curate import (
    CurateContext,
    apply_plan,
    build_curate_plan,
    serialize_curate_plan,
)


def _plan(context=None):
    cand = Candidate(proposed_scope="data-product:x", likely_archetype="measurement-qa", score=0.5,
                     evidence=(EvidenceTriple(project="p1", plan_ref="plan:a", dataset_ref="dataset:d"),))
    ctx = context or CurateContext(covered_not_loaded=4, unmapped=2, skipped_projects=("/gone",))
    return build_curate_plan([cand], [], ctx, {"mode": "portfolio"})


def test_json_report_is_parseable_with_context() -> None:
    obj = json.loads(serialize_curate_plan(_plan(), "json"))
    assert obj["mode"] == "report"
    assert obj["context"] == {"covered_not_loaded": 4, "unmapped": 2, "skipped_projects": ["/gone"]}
    assert obj["rows"][0]["disposition"] == "new"
    assert "applied" not in obj["rows"][0] and "result" not in obj["rows"][0]


def test_json_apply_reports_result(tmp_path) -> None:
    plan = _plan()
    apply_plan(plan, tmp_path, today="2026-07-28")
    obj = json.loads(serialize_curate_plan(plan, "json"))
    assert obj["mode"] == "apply"
    assert obj["rows"][0]["applied"] is True
    assert obj["rows"][0]["result"]["action"] == "created"


def test_text_render_names_gaps_counts_and_archetype() -> None:
    text = serialize_curate_plan(_plan(), "text")
    assert "data-product:x" in text
    assert "new" in text
    assert "measurement-qa" in text  # likely_archetype is decision-critical for the reviewer
    assert "covered-not-loaded: 4" in text and "unmapped: 2" in text


def test_text_render_header_names_scoped_project() -> None:
    cand = Candidate(proposed_scope="data-product:x", likely_archetype="measurement-qa", score=0.5,
                     evidence=(EvidenceTriple(project="p1", plan_ref="plan:a", dataset_ref="dataset:d"),))
    plan = build_curate_plan([cand], [], CurateContext(0, 0, ()), {"mode": "project", "project": "mm30"})
    assert "project mm30" in serialize_curate_plan(plan, "text")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run --frozen pytest tests/skills_coverage/test_curate_serialize.py -q`
Expected: FAIL (`ImportError: cannot import name 'serialize_curate_plan'`).

- [ ] **Step 3: Add the implementation to `curate.py`**

Add `import json` to the header, then append:

```python
def serialize_curate_plan(plan: CuratePlan, fmt: str) -> str:
    if fmt == "json":
        return json.dumps(plan.to_dict(), indent=2, sort_keys=True) + "\n"
    return _render_text(plan)


def _render_text(plan: CuratePlan) -> str:
    header = f"skill-coverage curate ({plan.mode}) — scope {plan.scope.get('mode', '?')}"
    project = plan.scope.get("project")
    if project:
        header += f" · project {project}"
    lines = [header]
    if not plan.rows:
        lines.append("  no uncovered gaps")
    for row in plan.rows:
        tag = row.disposition
        if row.applied is not None:
            tag += " [applied]" if row.applied else " [not applied]"
        line = (f"  {tag}: {row.term}  [{row.likely_archetype}]  score={row.score}  "
                f"{row.n_plans} plans / {row.n_projects} projects")
        if row.existing:
            line += "  existing=" + ",".join(f"{m.id}:{m.status}" for m in row.existing)
        if row.result is not None:
            line += f"  -> {row.result}"
        lines.append(line)
    ctx = plan.context
    lines.append(f"context: covered-not-loaded: {ctx.covered_not_loaded}  unmapped: {ctx.unmapped}")
    if ctx.skipped_projects:
        lines.append("  skipped: " + ", ".join(ctx.skipped_projects))
    return "\n".join(lines) + "\n"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/skills_coverage/test_curate_serialize.py -q`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/skills_coverage/curate.py science/tests/skills_coverage/test_curate_serialize.py
git commit -m "feat(skills-curate): serialize the plan as text and canonical JSON"
```

---

### Task 4: CLI command `science skills curate` + feedback-dir helper

**Files:**
- Modify: `science/src/science_tool/feedback_cli.py` (rename `_get_feedback_dir` → public `resolve_feedback_dir`; migrate its 10 internal call sites)
- Modify: `science/src/science_tool/autonomy/cli.py` (migrate the import + call at ~218/243)
- Modify: `science/tests/test_autonomy_lifecycle_cli.py` (docstring reference at ~58)
- Modify: `science/src/science_tool/skills_coverage/cli.py` (add `curate_command`)
- Modify: `science/src/science_tool/skills_lint/cli.py` (register on `skills_group`)
- Test: `science/tests/skills_coverage/test_curate_cli.py`

**Interfaces:**
- Consumes: `scan_portfolio`, `write_report_atomically`; Task 1–3 `build_curate_plan`, `apply_plan`, `serialize_curate_plan`, `coverage_context`, `CurateConflictError`, `CurateSelectionError`; `science_tool.feedback.load_all_entries`, `resolve_feedback_dir`.
- Produces: `science skills curate [--apply] [--term T]… [--project P] [--format text|json] [--output PATH]`; public `resolve_feedback_dir()` (replaces the private `_get_feedback_dir`).

- [ ] **Step 1: Rename the feedback-dir helper and migrate every caller atomically**

`_get_feedback_dir` is a private helper with callers in three files. Rename it to
the public `resolve_feedback_dir` and update all callers in the same commit — the
project forbids compatibility/delegating shims, so the private name is removed, not
kept alongside.

In `science/src/science_tool/feedback_cli.py`, rename the definition (the body is
unchanged from the private version):

```python
def resolve_feedback_dir() -> Path:
    import os

    from science_tool.registry.config import get_science_config_dir

    return Path(os.environ.get("SCIENCE_FEEDBACK_DIR", str(get_science_config_dir() / "feedback")))
```

Then replace all ten internal `_get_feedback_dir()` call sites in that same file
(they read `fb_dir = _get_feedback_dir()`) with `resolve_feedback_dir()`. A blanket
replace is safe — the only definition and all uses live in this one file plus the
two callers below:

```bash
sed -i 's/_get_feedback_dir/resolve_feedback_dir/g' \
  src/science_tool/feedback_cli.py \
  src/science_tool/autonomy/cli.py \
  tests/test_autonomy_lifecycle_cli.py
```

`autonomy/cli.py` (the `from science_tool.feedback_cli import _get_feedback_dir`
import at ~218 and its use at ~243) and the docstring at
`tests/test_autonomy_lifecycle_cli.py:58` are the only sites outside `feedback_cli.py`.

Verify the old name is fully gone before committing:
`grep -rn _get_feedback_dir science/` must return nothing.

- [ ] **Step 2: Write the failing CLI test**

```python
# science/tests/skills_coverage/test_curate_cli.py
from __future__ import annotations

import json
from pathlib import Path

import yaml
from click.testing import CliRunner

from science_tool.feedback import load_all_entries
from science_tool.skills_lint.cli import skills_group


def _enrolled_project(root: Path) -> None:
    from _fixtures.entity_helpers import seed_project

    root.mkdir()
    seed_project(root)
    cfg = root / "science.yaml"
    cfg.write_text(
        cfg.read_text()
        + "\nentity_schema_version: 3\nskill_coverage:\n  domains:\n    molecular-measurement: enrolled\n",
        encoding="utf-8",
    )


def _registry(tmp_path: Path, entries: list[dict]) -> None:
    (tmp_path / "config.yaml").write_text(yaml.safe_dump({"projects": entries}), encoding="utf-8")


def _an_uncovered_term() -> str:
    """A real catalog term that no leaf skill covers (guarantees a candidate)."""
    from science_model.data_products import load_catalog
    from science_model.skill_coverage import LeafSkill, build_skill_overlay
    from science_tool.graph.skill_inventory import load_skill_inventory

    catalog = load_catalog()
    overlay = build_skill_overlay(load_skill_inventory(), catalog)
    covered = {term for skill in overlay if isinstance(skill, LeafSkill) for term in skill.covers}
    return next(term for term in catalog.by_id if term not in covered)


def _seed_gap(root: Path, term: str) -> None:
    from _fixtures.entity_helpers import write_markdown_entity

    write_markdown_entity(root, "entities/datasets/tagged.md", {
        "id": "dataset:tagged", "kind": "dataset", "title": "Tagged",
        "provided_capabilities": [{"data_product": term}],
    }, "A tagged dataset.")
    write_markdown_entity(root, "entities/plans/0001-p.md", {
        "id": "plan:0001-p", "kind": "plan", "title": "Plan p",
        "related": ["dataset:tagged"],
    }, "A plan that uses the tagged dataset.")


def _setup(tmp_path: Path, monkeypatch, *, seed_gap: bool = True) -> tuple[Path, str]:
    enrolled = tmp_path / "enrolled"
    _enrolled_project(enrolled)
    term = _an_uncovered_term()
    if seed_gap:
        _seed_gap(enrolled, term)
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(tmp_path))
    fb = tmp_path / "feedback"
    monkeypatch.setenv("SCIENCE_FEEDBACK_DIR", str(fb))
    _registry(tmp_path, [{"path": str(enrolled), "name": "enrolled", "id": "enrolled", "registered": "2026-07-25"}])
    return fb, term


def test_report_run_writes_no_feedback(tmp_path: Path, monkeypatch) -> None:
    fb, _ = _setup(tmp_path, monkeypatch)
    result = CliRunner().invoke(skills_group, ["curate", "--format", "json"])
    assert result.exit_code == 0, result.output
    obj = json.loads(result.output)
    assert obj["mode"] == "report"
    assert set(obj["context"]) == {"covered_not_loaded", "unmapped", "skipped_projects"}  # context extracted
    assert not fb.exists() or load_all_entries(fb) == []  # no writes


def test_apply_files_feedback(tmp_path: Path, monkeypatch) -> None:
    fb, term = _setup(tmp_path, monkeypatch)
    result = CliRunner().invoke(skills_group, ["curate", "--apply", "--format", "json"])
    assert result.exit_code == 0, result.output
    obj = json.loads(result.output)
    assert obj["mode"] == "apply"
    row = next(r for r in obj["rows"] if r["term"] == term)
    assert row["applied"] is True and row["result"]["action"] == "created"
    entries = load_all_entries(fb)
    assert any(e.target == f"skill-coverage:{term}" and e.project == "science" for e in entries)


def test_term_requires_apply(tmp_path: Path, monkeypatch) -> None:
    _setup(tmp_path, monkeypatch)
    result = CliRunner().invoke(skills_group, ["curate", "--term", "data-product:x"])
    assert result.exit_code != 0
    assert "requires --apply" in result.output


def test_output_untouched_on_failure(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(tmp_path))
    _registry(tmp_path, [])  # empty registry -> hard error
    out = tmp_path / "plan.json"
    out.write_text("PRIOR", encoding="utf-8")
    result = CliRunner().invoke(skills_group, ["curate", "--output", str(out)])
    assert result.exit_code != 0
    assert out.read_text(encoding="utf-8") == "PRIOR"


def test_output_writes_full_payload_not_stdout(tmp_path: Path, monkeypatch) -> None:
    fb, term = _setup(tmp_path, monkeypatch)
    out = tmp_path / "plan.json"
    result = CliRunner().invoke(skills_group, ["curate", "--format", "json", "--output", str(out)])
    assert result.exit_code == 0, result.output
    assert result.output.strip() == ""  # payload went to the file, not stdout
    obj = json.loads(out.read_text(encoding="utf-8"))
    assert obj["mode"] == "report" and any(r["term"] == term for r in obj["rows"])


def test_apply_output_failure_writes_no_feedback(tmp_path: Path, monkeypatch) -> None:
    # A real gap exists, so apply WOULD write — but a bad --output parent must be
    # caught first, leaving the feedback store untouched (no half-commit on retry).
    fb, _ = _setup(tmp_path, monkeypatch)
    out = tmp_path / "missing-dir" / "plan.json"  # parent does not exist
    result = CliRunner().invoke(skills_group, ["curate", "--apply", "--output", str(out)])
    assert result.exit_code != 0
    assert not out.exists()
    assert not fb.exists() or load_all_entries(fb) == []  # apply never ran
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd science && uv run --frozen pytest tests/skills_coverage/test_curate_cli.py -q`
Expected: FAIL (`No such command 'curate'`).

- [ ] **Step 4: Implement `curate_command`**

Append to `science/src/science_tool/skills_coverage/cli.py`:

```python
from datetime import date

from science_tool.feedback import load_all_entries
from science_tool.feedback_cli import resolve_feedback_dir
from science_tool.skills_coverage.curate import (
    CurateConflictError,
    CurateSelectionError,
    apply_plan,
    build_curate_plan,
    coverage_context,
    serialize_curate_plan,
)


@click.command(name="curate")
@click.option("--apply", "apply_", is_flag=True, help="File feedback for the plan (default: report only, no writes).")
@click.option("--term", "terms", multiple=True, help="With --apply, file only these term(s). Repeatable.")
@click.option("--project", "project", default=None, help="Restrict the scan to one registered project.")
@click.option("--format", "fmt", type=click.Choice(["text", "json"]), default="text")
@click.option("--output", type=click.Path(dir_okay=False, path_type=Path), default=None,
              help="Write the complete report to PATH (atomically) instead of stdout.")
def curate_command(apply_: bool, terms: tuple[str, ...], project: str | None, fmt: str, output: Path | None) -> None:
    """Triage uncovered skill-coverage gaps into `science feedback` (report-first)."""
    if terms and not apply_:
        raise click.ClickException("--term requires --apply")
    # Preflight the output destination BEFORE any feedback write, so an unwritable
    # --output can never follow a committed --apply (which a retry would double-record).
    if output is not None and not output.parent.is_dir():
        raise click.ClickException(f"--output parent directory does not exist: {output.parent}")
    try:
        report = scan_portfolio(only=project)
    except (SkillCoverageScanError, SkillCoverageError) as exc:
        raise click.ClickException(str(exc)) from exc

    feedback_dir = resolve_feedback_dir()
    entries = load_all_entries(feedback_dir)
    try:
        plan = build_curate_plan(report.candidates, entries, coverage_context(report), report.scope.to_dict())
    except CurateConflictError as exc:
        raise click.ClickException(str(exc)) from exc

    if apply_:
        try:
            plan = apply_plan(plan, feedback_dir, today=date.today().isoformat(),
                              selected_terms=set(terms) or None)
        except CurateSelectionError as exc:
            raise click.ClickException(str(exc)) from exc

    text = serialize_curate_plan(plan, fmt)
    if output is not None:
        write_report_atomically(output, text)
    else:
        click.echo(text, nl=False)
```

Then register it in `science/src/science_tool/skills_lint/cli.py`, next to the coverage registration:

```python
from science_tool.skills_coverage.cli import coverage_command, curate_command
# ...
skills_group.add_command(coverage_command)
skills_group.add_command(curate_command)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/skills_coverage/test_curate_cli.py -q`
Expected: PASS (6 tests).

- [ ] **Step 6: Lint, type-check, commit**

```bash
cd science && uv run --frozen ruff check src/science_tool/skills_coverage src/science_tool/feedback_cli.py src/science_tool/autonomy/cli.py && uv run --frozen pyright src/science_tool/skills_coverage src/science_tool/feedback_cli.py src/science_tool/autonomy/cli.py
git add science/src/science_tool/skills_coverage/cli.py science/src/science_tool/skills_lint/cli.py science/src/science_tool/feedback_cli.py science/src/science_tool/autonomy/cli.py science/tests/test_autonomy_lifecycle_cli.py science/tests/skills_coverage/test_curate_cli.py
git commit -m "feat(skills-curate): science skills curate CLI command; rename feedback-dir helper"
```

---

### Task 5: `/curate-skills` command + regenerate agent assets

**Files:**
- Create: `commands/curate-skills.md`
- Regenerate (committed): `skills/generated/science-curate-skills/**`, `commands/opencode/science-curate-skills.md`
- Verify: `science/tests/test_agent_assets.py` (committed-mirror equality — run, do not edit)

**Interfaces:** none (docs + generated mirror).

- [ ] **Step 1: Write the command definition**

```markdown
<!-- commands/curate-skills.md -->
---
description: Triage portfolio skill-coverage gaps into science feedback. Runs `science skills curate`, presents ranked uncovered gaps, and on --apply files (or records recurrence of) a feedback entry per accepted gap. Report-first; writes no skill files.
---

# Curate skills · Coverage-gap triage

Surface the skill-*corpus* gaps the portfolio's analyses reveal — data-product
terms that project plans use but no skill covers — and record the accepted ones
as `science feedback` entries for later authoring. This command writes **no skill
files**; the only side effect (under `--apply`) is feedback.

Follow `${CLAUDE_PLUGIN_ROOT}/references/command-preamble.md` before executing this command.

Use `$ARGUMENTS` for optional flags. Recognized:

- `--apply` — consumed by this slash command; permits exactly one side effect
  (filing feedback via `science skills curate --apply`). Without it: report-only.
- `--project P` — restrict the scan to one registered project. Forwarded.

## Steps

1. Run the report-only plan (forward `--project` when the user passed it):

   ```bash
   uv run science skills curate --format json [--project <project>]
   ```

2. Present the `rows` to the user, ranked by `score`. For each, name the
   `term`, `likely_archetype`, `n_plans`/`n_projects`, and its `disposition`
   (`new`, `recur`, or a `skip`/`skip-addressed-conflict` against existing
   feedback — surface these but do not re-file them). Subject-folder placement is
   an authoring-time decision, not something to record now.

3. Report the `context` counts (`covered_not_loaded`, `unmapped`) as **project-side
   follow-ups only** — this command never files them.

4. If the user provided `--apply`, ask which gaps to accept, then file exactly
   those:

   ```bash
   uv run science skills curate --apply --term <term> [--term <term> …] [--project <project>]
   ```

   Forward the same `--project` value used in step 1, so the accepted terms and
   the filed feedback come from one scope. Bare `--apply` (no `--term`) files
   every `new`/`recur` row. Report the resulting feedback ids from each row's
   `result`.
```

- [ ] **Step 2: Regenerate the committed agent-assets mirror**

Run: `cd science && uv run --frozen science agents generate`
Expected: creates `skills/generated/science-curate-skills/SKILL.md` and `commands/opencode/science-curate-skills.md` (and refreshes `skills/generated/INDEX.md`).

- [ ] **Step 3: Verify the committed mirror matches fresh generation**

Run: `cd science && uv run --frozen pytest tests/test_agent_assets.py -q`
Expected: PASS (committed bytes equal fresh generation; the new command appears in the generated index; canonical command discovery is non-recursive and excludes `commands/opencode/`).

- [ ] **Step 4: Commit**

```bash
git add commands/curate-skills.md commands/opencode/science-curate-skills.md skills/generated/
git commit -m "feat(skills-curate): /curate-skills command and generated agent assets"
```

---

### Task 6: Document `curate` in the skill-coverage convention

**Files:**
- Modify: `docs/conventions/skill-coverage.md`

**Interfaces:** none.

- [ ] **Step 1: Append a `curate` section**

Add to `docs/conventions/skill-coverage.md`:

```markdown
## Curating gaps into feedback

`science skills curate` turns the scan's `uncovered` candidates into tracked
`science feedback` entries. It is report-first: with no flag it prints a filing
plan and writes nothing; `--apply` files the plan.

```bash
science skills curate                        # print the plan (report-only)
science skills curate --apply                # file every new/recur row
science skills curate --apply --term <term>  # file only the named term(s)
science skills curate --project mm30         # scope the scan to one project
science skills curate --format json --output plan.json
```

Each accepted gap becomes a feedback entry with `target: skill-coverage:<term>`,
`category: gap`, `concern: tooling`, `project: science`. A term already carrying
an **open** entry records a recurrence instead of a duplicate; a term whose only
matches are resolved (`wontfix`/`addressed`/`deferred`) is reported but not
re-filed. More than one open entry for a term is a hard error — merge them first.
Only `uncovered` gaps are filed; `covered-not-loaded` and `unmapped` appear in the
report's context counts as project-side follow-ups.
```

- [ ] **Step 2: Commit**

```bash
git add docs/conventions/skill-coverage.md
git commit -m "docs(skills-curate): document science skills curate in the coverage convention"
```

---

## Final verification

After all tasks, from `science/`, run these exact commands in order:

```bash
# 1. The feature's own tests + the generated-mirror guard
uv run --frozen pytest tests/skills_coverage tests/test_agent_assets.py -q

# 2. Command-doc + agent-adapter guards that Task 5's new command feeds
uv run --frozen pytest tests/test_command_docs.py tests/test_agent_cli_compatibility.py -q

# 3. Autonomy CLI tests — Task 4 renamed the feedback-dir helper they depend on
uv run --frozen pytest tests -k autonomy -q

# 4. Lint the packages touched (ruff is per-package; run from science/)
uv run --frozen ruff check src/science_tool/skills_coverage src/science_tool/feedback_cli.py src/science_tool/autonomy/cli.py

# 5. Types repo-wide — the single pyrightconfig governs all trees; catches the
#    cross-module break the helper rename could cause (e.g. autonomy)
uv run --frozen pyright
```

Then the **top-level agent** (never a subagent — the full suite runs ~2-3 min and
auto-backgrounds past the 120s timeout) runs the whole suite once:

```bash
uv run --frozen pytest -q
```

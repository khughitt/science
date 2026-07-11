# InstrumentResult Convergence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make it structurally impossible for an instrument to report a clean empty result when it never actually ran.

**Architecture:** Canonicalize one `InstrumentResult` type whose Pydantic validator makes the invalid states unconstructable (`ok` with no rows, `empty` with rows, `unwired` with rows or without a machine code). Migrate the ~30 bare-collection helpers in the instrument namespace onto it. Ratchet with an AST guard in the shape of the five existing boundary guards, whose module list *is* the migration query — one expression, imported by both, so they cannot drift.

**Tech Stack:** Python 3.12, Pydantic v2, Click, rdflib, pytest, ruff, pyright. Package: `science/` (uv, `pyproject.toml`).

**Design doc:** [`2026-07-11-instrument-result-convergence-design.md`](2026-07-11-instrument-result-convergence-design.md). Read it before Task 1; it carries the rulings this plan implements.

## Global Constraints

- All commands run from `science/` — **never** the repo root. There is no root `pyproject.toml`.
- Tests: `cd science && uv run --frozen pytest`. Lint: `uv run ruff check`. Types: `uv run pyright`.
- Pyright is configured once, by `pyrightconfig.json` at the **repo root**; do not add a `[tool.pyright]` block to any `pyproject.toml` (it is silently ignored).
- Branch: `instrument-result-convergence`, in the worktree `.claude/worktrees/instrument-result`. **Verify with `git branch --show-current` before every commit** — this checkout is Dropbox-synced and HEAD can move.
- No AI-attribution trailers on commits.
- No "legacy"/"compatibility" layers. A v1 manifest is reported as `unwired`, not silently accommodated (design §4).
- Composition over inheritance; explicit over defensive; fail early over silent fallback.

## File Structure

| File | Responsibility |
|---|---|
| `science/src/science_tool/instruments.py` | **Create.** `InstrumentResult`, its validator, its constructors, and `INSTRUMENT_MODULES` — the single namespace expression. |
| `science/tests/test_instruments.py` | **Create.** Validator unit tests: every invalid construction must raise. |
| `science/tests/test_instrument_boundary.py` | **Create.** AST ratchet guard. Imports `INSTRUMENT_MODULES`. |
| `science/src/science_tool/big_picture/knowledge_gaps.py` | **Modify.** `compute_topic_gaps` → `InstrumentResult[TopicGap]`; add the topic-ref scan; four-state precondition. |
| `science/src/science_tool/big_picture/validator.py` | **Modify.** Delete `count_research_orphans`; add `list_research_orphans`. |
| `science/src/science_tool/graph/io.py` | **Modify.** Manifest envelope v2 (`schema`/`walked`/`files`); walk `entities_dir`. |
| `science/src/science_tool/graph/store/validation.py` | **Modify.** `diff_graph_inputs*` → `InstrumentResult`; v1 baseline ⇒ `unwired`. |
| `science/src/science_tool/validate/checks/materialization.py` | **Create.** Lint: a frontmatter field that materializes nothing is an error. |
| `science/src/science_tool/graph/{health,attention}.py`, `graph/store/{summary,queries,inquiry}.py`, `curate/inventory.py`, `benchmark_catalog.py`, `datasets_catalog.py` | **Modify.** Bulk migration (Tasks 7–10). |
| `commands/big-picture.md` | **Modify.** Renderer contract: `unwired` ≠ `empty`. |

---

### Task 1: The `InstrumentResult` type

**Files:**
- Create: `science/src/science_tool/instruments.py`
- Test: `science/tests/test_instruments.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `InstrumentResult[RowT]` with fields `status: Literal["ok","empty","unwired"]`, `rows: list[RowT]`, `reason: str | None`, `code: str | None`; constructors `InstrumentResult.ok(rows, *, code=None, reason=None)`, `.empty(*, code=None, reason=None)`, `.unwired(*, code, reason=None)`. Also `INSTRUMENT_MODULES: tuple[str, ...]` (project-relative paths under `science/src/science_tool/`).

- [ ] **Step 1: Write the failing test**

```python
# science/tests/test_instruments.py
from __future__ import annotations

import pytest
from pydantic import ValidationError

from science_tool.instruments import InstrumentResult


def test_ok_requires_rows() -> None:
    with pytest.raises(ValidationError, match="requires non-empty rows"):
        InstrumentResult[int](status="ok", rows=[])


def test_empty_forbids_rows() -> None:
    with pytest.raises(ValidationError, match="forbids rows"):
        InstrumentResult[int](status="empty", rows=[1])


def test_unwired_forbids_rows() -> None:
    with pytest.raises(ValidationError, match="forbids rows"):
        InstrumentResult[int](status="unwired", rows=[1], code="x")


def test_unwired_requires_code() -> None:
    with pytest.raises(ValidationError, match="requires a machine-readable code"):
        InstrumentResult[int](status="unwired", rows=[])


def test_valid_constructions() -> None:
    assert InstrumentResult.ok([1, 2]).rows == [1, 2]
    assert InstrumentResult[int].empty().rows == []
    unwired = InstrumentResult[int].unwired(code="no_resolvable_topics", reason="none resolve")
    assert unwired.status == "unwired"
    assert unwired.code == "no_resolvable_topics"


def test_ok_may_carry_a_caveat() -> None:
    """A successful run can still have dropped part of its input (design: partial resolution)."""
    result = InstrumentResult.ok([1], code="partial_topic_resolution", reason="7 of 10 refs unresolved")
    assert result.status == "ok"
    assert result.reason == "7 of 10 refs unresolved"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_instruments.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'science_tool.instruments'`

- [ ] **Step 3: Write the implementation**

```python
# science/src/science_tool/instruments.py
"""Canonical instrument result type — the silent-instrument ruling.

An *instrument* is a helper whose empty return is rendered to a user as a
finding. The failure this type exists to stop: an instrument returns a
clean-looking empty result when it never actually ran, and the caller reports
that as "nothing found".

The invariant, enforced below rather than merely documented:

    ``empty`` and ``unwired`` are different, and the result cannot be
    constructed without choosing between them.

- ``ok``      — ran, found rows. Requires non-empty ``rows``.
- ``empty``   — ran, genuinely found nothing. A TRUE finding. Requires no rows.
- ``unwired`` — could not run. ``rows`` is meaningless. Requires no rows AND a
  machine-readable ``code``.

``reason``/``code`` are NOT exclusive to ``unwired``: a run that succeeded while
silently dropping part of its input carries them as a caveat on an ``ok``/``empty``
result. A renderer must surface a ``reason`` whatever the status.

See docs/plans/2026-07-11-instrument-result-convergence-design.md.
"""

from __future__ import annotations

from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, Field, model_validator

RowT = TypeVar("RowT")

InstrumentStatus = Literal["ok", "empty", "unwired"]

#: Modules whose public helpers must return ``InstrumentResult``.
#:
#: This tuple is the SINGLE definition of the instrument namespace. The AST guard
#: (tests/test_instrument_boundary.py) imports it, and any migration query must
#: import it too. Written twice, the guard and the query would drift — which is
#: the class of failure this whole module exists to prevent.
INSTRUMENT_MODULES: tuple[str, ...] = (
    "big_picture/knowledge_gaps.py",
    "big_picture/validator.py",
    "graph/health.py",
    "graph/attention.py",
    "graph/store/summary.py",
    "graph/store/queries.py",
    "graph/store/inquiry.py",
    "graph/store/validation.py",
    "curate/inventory.py",
    "benchmark_catalog.py",
    "datasets_catalog.py",
)


class InstrumentResult(BaseModel, Generic[RowT]):
    status: InstrumentStatus
    rows: list[RowT] = Field(default_factory=list)
    reason: str | None = None
    code: str | None = None

    @model_validator(mode="after")
    def _enforce_status_invariant(self) -> "InstrumentResult[RowT]":
        if self.status == "ok" and not self.rows:
            raise ValueError("status='ok' requires non-empty rows; use status='empty'")
        if self.status == "empty" and self.rows:
            raise ValueError("status='empty' forbids rows")
        if self.status == "unwired":
            if self.rows:
                raise ValueError("status='unwired' forbids rows; they are meaningless")
            if not self.code:
                raise ValueError("status='unwired' requires a machine-readable code")
        return self

    @classmethod
    def ok(
        cls,
        rows: list[RowT],
        *,
        code: str | None = None,
        reason: str | None = None,
    ) -> "InstrumentResult[RowT]":
        return cls(status="ok", rows=rows, code=code, reason=reason)

    @classmethod
    def empty(
        cls,
        *,
        code: str | None = None,
        reason: str | None = None,
    ) -> "InstrumentResult[RowT]":
        return cls(status="empty", rows=[], code=code, reason=reason)

    @classmethod
    def unwired(cls, *, code: str, reason: str | None = None) -> "InstrumentResult[RowT]":
        return cls(status="unwired", rows=[], code=code, reason=reason)

    @classmethod
    def from_rows(
        cls,
        rows: list[RowT],
        *,
        code: str | None = None,
        reason: str | None = None,
    ) -> "InstrumentResult[RowT]":
        """Ran successfully; ``ok`` if it found anything, ``empty`` if it truly did not.

        Use this ONLY where the instrument definitely ran. If it may not have run,
        the caller must decide and call ``unwired`` explicitly — that decision is
        the entire point of this type and must not be inferred from row count.
        """
        if rows:
            return cls.ok(rows, code=code, reason=reason)
        return cls.empty(code=code, reason=reason)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science && uv run --frozen pytest tests/test_instruments.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: Lint and typecheck**

Run: `cd science && uv run ruff check && uv run pyright`
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/instruments.py science/tests/test_instruments.py
git commit -m "feat(instruments): add InstrumentResult with an enforced status invariant"
```

---

### Task 2: The AST ratchet guard

**Files:**
- Create: `science/tests/test_instrument_boundary.py`

**Interfaces:**
- Consumes: `INSTRUMENT_MODULES` from Task 1.
- Produces: `_ALLOWLIST: frozenset[tuple[str, str]]` of `(module_relpath, function_name)` pairs, which Tasks 3–10 remove entries from. When it is empty, the migration is done.

**Why an allowlist and not a big-bang:** ~30 helpers cannot migrate in one reviewable commit. The ratchet blocks *new* violations immediately while the existing set drains. Per the convergence design: an allowlist entry the guard would still flag means the migration is incomplete — **not** a carve-out to add.

- [ ] **Step 1: Write the guard**

This test is *both* the guard and the migration query. It fails on any un-migrated, un-allowlisted helper.

```python
# science/tests/test_instrument_boundary.py
"""Instrument-result boundary guard (silent-instrument ruling).

Additive ratchet: a public helper in the instrument namespace must return
``InstrumentResult[...]``. It may not return a bare ``list``/``dict``/``int``,
nor the ``tuple[list[T], str | None]`` precursor form that two catalog helpers
grew independently before this type existed.

The namespace is ``science_tool.instruments.INSTRUMENT_MODULES`` — imported, not
restated, so the guard and the migration query cannot drift.

Detection: a module-level ``def`` whose name does not start with ``_`` and whose
return annotation is a bare collection or the tuple precursor. Matched on the
ANNOTATION, structurally.

Known gap, stated rather than hidden: an un-annotated helper, or one annotated
``Any``, evades this guard. So does a helper that returns a bare collection from
a module outside INSTRUMENT_MODULES. This is a ratchet against the bare-collection
return that recurred across the tree, not a sandbox — the same class of limit the
output and durable-write guards document candidly.
"""

from __future__ import annotations

import ast
from pathlib import Path

from science_tool.instruments import INSTRUMENT_MODULES

_SCIENCE_SRC = Path(__file__).resolve().parents[1] / "src" / "science_tool"

# (module_relpath, function_name) pairs not yet migrated.
# DRAIN THIS TO EMPTY. Do not add to it.
_ALLOWLIST: frozenset[tuple[str, str]] = frozenset(
    {
        ("big_picture/knowledge_gaps.py", "compute_topic_gaps"),
        ("big_picture/validator.py", "count_research_orphans"),
        ("graph/health.py", "collect_unresolved_refs"),
        ("graph/health.py", "collect_unregistered_ref_kinds"),
        ("graph/health.py", "collect_lingering_tags"),
        ("graph/health.py", "collect_validation_findings"),
        ("graph/attention.py", "compute_attention_candidates"),
        ("graph/attention.py", "query_attention_sample"),
        ("graph/attention.py", "query_attention_ranked"),
        ("graph/store/summary.py", "query_dashboard_summary"),
        ("graph/store/summary.py", "query_neighborhood_summary"),
        ("graph/store/summary.py", "query_question_summary"),
        ("graph/store/summary.py", "query_inquiry_summary"),
        ("graph/store/summary.py", "query_gaps"),
        ("graph/store/queries.py", "query_neighborhood"),
        ("graph/store/queries.py", "query_claims"),
        ("graph/store/queries.py", "query_evidence"),
        ("graph/store/inquiry.py", "list_inquiries"),
        ("graph/store/inquiry.py", "list_inquiries_dataset"),
        ("graph/store/validation.py", "query_predicates"),
        ("graph/store/validation.py", "diff_graph_inputs"),
        ("graph/store/validation.py", "diff_graph_inputs_dataset"),
        ("benchmark_catalog.py", "list_benchmarks"),
        ("datasets_catalog.py", "list_datasets"),
    }
)

_BARE_COLLECTIONS = {"list", "dict", "int", "set"}


def _annotation_root(node: ast.expr) -> str | None:
    """Return the root name of an annotation: list[X] -> 'list', dict -> 'dict'."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Subscript):
        return _annotation_root(node.value)
    return None


def _is_tuple_precursor(node: ast.expr) -> bool:
    """Match ``tuple[list[T], ...]`` — the ad-hoc reason channel."""
    if not isinstance(node, ast.Subscript):
        return False
    if _annotation_root(node) != "tuple":
        return False
    inner = node.slice
    if not isinstance(inner, ast.Tuple) or not inner.elts:
        return False
    return _annotation_root(inner.elts[0]) == "list"


def _violations(module_rel: str) -> list[str]:
    path = _SCIENCE_SRC / module_rel
    tree = ast.parse(path.read_text(encoding="utf-8"))
    bad: list[str] = []
    for node in tree.body:  # module-level defs only
        if not isinstance(node, ast.FunctionDef):
            continue
        if node.name.startswith("_"):
            continue
        if node.returns is None:
            continue
        if _is_tuple_precursor(node.returns) or _annotation_root(node.returns) in _BARE_COLLECTIONS:
            bad.append(node.name)
    return bad


def test_instrument_namespace_returns_instrument_result() -> None:
    offenders: list[str] = []
    for module_rel in INSTRUMENT_MODULES:
        for fn in _violations(module_rel):
            if (module_rel, fn) not in _ALLOWLIST:
                offenders.append(f"{module_rel}::{fn}")
    assert not offenders, (
        "These instrument helpers return a bare collection. They must return "
        "InstrumentResult[...] — an empty list cannot say whether the instrument "
        "ran:\n  " + "\n  ".join(sorted(offenders))
    )


def test_allowlist_has_no_stale_entries() -> None:
    """An allowlisted helper that no longer violates must be REMOVED from the allowlist.

    This is what forces the ratchet to drain instead of rotting.
    """
    stale = [
        f"{module_rel}::{fn}"
        for (module_rel, fn) in _ALLOWLIST
        if fn not in _violations(module_rel)
    ]
    assert not stale, (
        "These helpers are allowlisted but no longer violate the boundary. "
        "Delete them from _ALLOWLIST:\n  " + "\n  ".join(sorted(stale))
    )
```

- [ ] **Step 2: Run the guard — it must PASS (everything is allowlisted)**

Run: `cd science && uv run --frozen pytest tests/test_instrument_boundary.py -v`
Expected: PASS (2 passed). If `test_allowlist_has_no_stale_entries` fails, the allowlist above does not match reality — **fix the allowlist to match the code, do not weaken the test.**

- [ ] **Step 3: Prove the ratchet bites**

Temporarily add to `science/src/science_tool/graph/health.py`:

```python
def collect_bogus_probe() -> list[str]:
    return []
```

Run: `cd science && uv run --frozen pytest tests/test_instrument_boundary.py -v`
Expected: FAIL — `graph/health.py::collect_bogus_probe`.
Then **delete the probe** and re-run. Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add science/tests/test_instrument_boundary.py
git commit -m "test(instruments): ratchet guard for the instrument-result boundary"
```

---

### Task 3: `compute_topic_gaps` — the four-state precondition

**Files:**
- Modify: `science/src/science_tool/big_picture/knowledge_gaps.py:207-251`
- Modify: `commands/big-picture.md:194` (the renderer contract)
- Test: `science/tests/test_knowledge_gaps.py`

**Interfaces:**
- Consumes: `InstrumentResult` (Task 1).
- Produces: `compute_topic_gaps(project_root, resolved_questions, included_question_ids) -> InstrumentResult[TopicGap]`.

**The ruling being implemented (design §2).** The precondition is on the **declared-vs-resolved** axis, not resolved-vs-nothing. Four states:

| Input | Status |
|---|---|
| Included questions declare topic refs; **none** resolve | `unwired`, `code="no_resolvable_topics"` |
| Included questions declare **no** topic refs | `empty` — a TRUE zero-gap finding |
| **No** question survives the aspect filter | `empty` — nothing was asked |
| **Some** refs resolve, some do not | `ok`/`empty` **carrying** `code="partial_topic_resolution"` |

Note the current code re-globs every question once per topic inside `_compute_demand` (O(topics × questions)). Hoisting the scan fixes the precondition and the quadratic scan together.

- [ ] **Step 1: Write the failing tests**

Append to `science/tests/test_knowledge_gaps.py`:

```python
def _write_question(project: Path, qid: str, related: list[str]) -> None:
    import yaml

    qdir = project / "entities" / "questions"
    qdir.mkdir(parents=True, exist_ok=True)
    fm = {"id": qid, "kind": "question", "status": "open", "related": related}
    (qdir / f"{qid.split(':', 1)[1]}.md").write_text(
        f"---\n{yaml.safe_dump(fm, sort_keys=False)}---\n\n# {qid}\n", encoding="utf-8"
    )


def _write_topic(project: Path, tid: str) -> None:
    import yaml

    tdir = project / "entities" / "topics"
    tdir.mkdir(parents=True, exist_ok=True)
    fm = {"id": tid, "kind": "topic", "status": "active", "title": tid}
    (tdir / f"{tid.split(':', 1)[1]}.md").write_text(
        f"---\n{yaml.safe_dump(fm, sort_keys=False)}---\n\n# {tid}\n", encoding="utf-8"
    )


def test_topic_gaps_unwired_when_no_declared_ref_resolves(tmp_path: Path) -> None:
    """The reported defect (fb-2026-07-11-004): demand exists but was silently discarded."""
    from science_tool.big_picture.knowledge_gaps import compute_topic_gaps

    project = tmp_path / "p"
    _write_topic(project, "topic:real-one")
    _write_question(project, "question:0001", ["topic:ghost-a"])
    _write_question(project, "question:0002", ["topic:ghost-b"])

    result = compute_topic_gaps(project, {}, {"question:0001", "question:0002"})

    assert result.status == "unwired"
    assert result.code == "no_resolvable_topics"
    assert result.rows == []
    assert "ghost" in (result.reason or "") or "2" in (result.reason or "")


def test_topic_gaps_empty_when_no_question_declares_a_topic_ref(tmp_path: Path) -> None:
    """No demand expressed => zero gaps is a TRUE finding, not a failure."""
    from science_tool.big_picture.knowledge_gaps import compute_topic_gaps

    project = tmp_path / "p"
    _write_topic(project, "topic:real-one")
    _write_question(project, "question:0001", [])

    result = compute_topic_gaps(project, {}, {"question:0001"})

    assert result.status == "empty"
    assert result.code is None


def test_topic_gaps_empty_when_aspect_filter_excludes_everything(tmp_path: Path) -> None:
    """Nothing was asked of the instrument => empty, not unwired."""
    from science_tool.big_picture.knowledge_gaps import compute_topic_gaps

    project = tmp_path / "p"
    _write_topic(project, "topic:real-one")
    _write_question(project, "question:0001", ["topic:real-one"])

    result = compute_topic_gaps(project, {}, set())  # nothing included

    assert result.status == "empty"


def test_topic_gaps_partial_resolution_carries_a_caveat(tmp_path: Path) -> None:
    """Ran, but silently dropped part of its input => ok/empty WITH a caveat."""
    from science_tool.big_picture.knowledge_gaps import compute_topic_gaps

    project = tmp_path / "p"
    _write_topic(project, "topic:real-one")
    _write_question(project, "question:0001", ["topic:real-one"])
    _write_question(project, "question:0002", ["topic:ghost"])

    result = compute_topic_gaps(project, {}, {"question:0001", "question:0002"})

    assert result.status in {"ok", "empty"}
    assert result.code == "partial_topic_resolution"
    assert "ghost" in (result.reason or "")
```

Also update the three existing tests (`:168`, `:187`, `:211`) — they assert on a bare list. Change `gaps = compute_topic_gaps(...)` to `gaps = compute_topic_gaps(...).rows`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science && uv run --frozen pytest tests/test_knowledge_gaps.py -v`
Expected: FAIL — `AttributeError: 'list' object has no attribute 'status'`

- [ ] **Step 3: Implement the scan and the precondition**

In `knowledge_gaps.py`, add the imports and the scan helper **above** `compute_topic_gaps`:

```python
from dataclasses import dataclass

from science_tool.instruments import InstrumentResult


@dataclass(frozen=True)
class _TopicRefScan:
    """Topic refs declared by included questions, and which of them resolve."""

    declared: set[str]
    unresolved: set[str]

    @property
    def resolved(self) -> set[str]:
        return self.declared - self.unresolved


def _scan_question_topic_refs(
    project_root: Path,
    included_question_ids: set[str],
    known_topic_ids: set[str],
) -> _TopicRefScan:
    """Scan included questions ONCE for their ``topic:`` refs.

    Hoisted out of ``_compute_demand`` (which ran once per topic) so the
    declared-vs-resolved precondition can be evaluated before any gap is computed.
    """
    questions_dir = entity_dir(project_root, "question")
    declared: set[str] = set()
    if questions_dir.is_dir():
        for md in sorted(questions_dir.glob("*.md")):
            fm = read_frontmatter(md) or {}
            qid = fm.get("id")
            if not qid or qid not in included_question_ids:
                continue
            for ref in fm.get("related", []) or []:
                if isinstance(ref, str) and ref.startswith("topic:"):
                    declared.add(ref)
    return _TopicRefScan(declared=declared, unresolved=declared - known_topic_ids)
```

Now replace the body of `compute_topic_gaps` (keep the existing docstring's first line, extend it):

```python
def compute_topic_gaps(
    project_root: Path,
    resolved_questions: dict[str, ResolverOutput],
    included_question_ids: set[str],
) -> InstrumentResult[TopicGap]:
    """Return legacy topic docs with demand > 0 and coverage < demand.

    Returns ``unwired`` when included questions DECLARE topic refs and NONE of
    them resolve: demand exists but was silently discarded, so a zero-gap result
    would be a lie (fb-2026-07-11-004). Zero gaps with no declared demand is
    ``empty`` — a true finding. Partial resolution runs, but carries a caveat.

    Sorted by ``gap_score`` descending; ties broken by ``topic_id`` ascending.
    """
    topics = _load_topics(project_root)
    papers = _load_papers(project_root)
    scan = _scan_question_topic_refs(project_root, included_question_ids, set(topics))

    if scan.declared and not scan.resolved:
        return InstrumentResult.unwired(
            code="no_resolvable_topics",
            reason=(
                f"{len(scan.declared)} topic ref(s) declared by included questions, "
                f"none resolve to a topic entity "
                f"({', '.join(sorted(scan.declared)[:5])}); topic demand cannot be computed"
            ),
        )

    caveat_code: str | None = None
    caveat_reason: str | None = None
    if scan.unresolved:
        caveat_code = "partial_topic_resolution"
        caveat_reason = (
            f"{len(scan.unresolved)} of {len(scan.declared)} declared topic ref(s) "
            f"do not resolve and their demand is excluded "
            f"({', '.join(sorted(scan.unresolved)[:5])})"
        )

    gaps: list[TopicGap] = []
    for topic_id in topics:
        demand, demanders = _compute_demand(
            project_root,
            topic_id,
            included_question_ids,
            known_topic_ids=set(topics),
        )
        if demand == 0:
            continue
        coverage = _compute_coverage(topic_id, topics, papers)
        if coverage >= demand:
            continue
        hypotheses = _hypotheses_for(demanders, resolved_questions)
        gaps.append(
            TopicGap(
                topic_id=topic_id,
                coverage=coverage,
                demand=demand,
                gap_score=max(0, demand - coverage),
                demanding_questions=demanders,
                hypotheses=hypotheses,
            )
        )

    gaps.sort(key=lambda g: (-g.gap_score, g.topic_id))
    return InstrumentResult.from_rows(gaps, code=caveat_code, reason=caveat_reason)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_knowledge_gaps.py -v`
Expected: PASS (all, including the four new ones)

- [ ] **Step 5: Fix the renderer contract**

The rollup renderer is **prose executed by the LLM orchestrator**, not Python — so it cannot be unit-tested, and it is where the bug actually surfaces to the user. In `commands/big-picture.md:194`, replace the sentence `If all_gaps is empty, emit the one-liner: "No knowledge gaps detected this run." and skip the table.` with:

```markdown
`compute_topic_gaps` returns an `InstrumentResult`. Branch on `status` — an empty
`rows` list does NOT mean "no gaps":
- `status: ok` — render the table.
- `status: empty` — emit the one-liner: "No knowledge gaps detected this run."
- `status: unwired` — the instrument DID NOT RUN. Emit, verbatim and prefixed:
  "KNOWLEDGE GAPS NOT COMPUTED: <reason>". Never emit the no-gaps one-liner in
  this case; doing so reports a lie.
Independently of status: if `reason` is set, surface it as a caveat beneath the
section (a successful run may still have dropped part of its input).
```

- [ ] **Step 6: Drain the allowlist**

Remove `("big_picture/knowledge_gaps.py", "compute_topic_gaps")` from `_ALLOWLIST` in `science/tests/test_instrument_boundary.py`.

Run: `cd science && uv run --frozen pytest tests/test_instrument_boundary.py -v`
Expected: PASS (2 passed — including `test_allowlist_has_no_stale_entries`).

- [ ] **Step 7: Full suite, lint, types**

Run: `cd science && uv run --frozen pytest && uv run ruff check && uv run pyright`
Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add science/src/science_tool/big_picture/knowledge_gaps.py \
        science/tests/test_knowledge_gaps.py \
        science/tests/test_instrument_boundary.py \
        commands/big-picture.md
git commit -m "fix(big-picture): compute_topic_gaps reports unwired instead of zero gaps

Included questions that declare topic refs none of which resolve produced an
empty gap list, rendered as 'No knowledge gaps detected this run.' -- identical
to genuine full coverage. The precondition is declared-vs-resolved, not
resolved-vs-nothing: no declared demand is still a TRUE empty."
```

---

### Task 4: Delete `count_research_orphans`, add `list_research_orphans`

**Files:**
- Modify: `science/src/science_tool/big_picture/validator.py:116-136` (delete), `:146` (caller)
- Modify: `science/tests/test_big_picture_validator.py:190-197`
- Modify: `commands/big-picture.md:206`

**Interfaces:**
- Consumes: `InstrumentResult` (Task 1).
- Produces: `list_research_orphans(resolved, project_root) -> InstrumentResult[str]` — rows are orphan question IDs, sorted. **`count_research_orphans` no longer exists.**

**The ruling (design §2):** the scalar counter is *prohibited*, not wrapped. fb-2026-07-11-014 reported the count and a hand-derived ID list disagreeing (40 vs 31). The surest way for two functions not to disagree is for there to be one function. Callers take `len(result.rows)`.

- [ ] **Step 1: Write the failing test**

Replace the existing test at `science/tests/test_big_picture_validator.py:190-197`:

```python
def test_list_research_orphans_rows_and_count_cannot_drift() -> None:
    from science_tool.big_picture.validator import list_research_orphans
    from science_tool.big_picture.resolver import resolve_questions

    resolved = resolve_questions(FIXTURE)
    result = list_research_orphans(resolved, project_root=FIXTURE)

    assert result.status in {"ok", "empty"}
    assert result.rows == sorted(result.rows)
    # The count IS the list. There is no second definition to drift from.
    assert len(result.rows) == len([
        qid for qid, out in resolved.items()
        if out.primary_hypothesis is None and qid in result.rows
    ])


def test_count_research_orphans_is_gone() -> None:
    """The scalar counter is prohibited, not wrapped (fb-2026-07-11-014)."""
    import science_tool.big_picture.validator as validator

    assert not hasattr(validator, "count_research_orphans")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_big_picture_validator.py -v -k orphan`
Expected: FAIL — `ImportError: cannot import name 'list_research_orphans'`

- [ ] **Step 3: Implement**

In `validator.py`, **delete** `count_research_orphans` (`:116-136`) entirely and replace with:

```python
def list_research_orphans(
    resolved: dict[str, ResolverOutput],
    project_root: Path,
) -> InstrumentResult[str]:
    """Return the research orphans — question IDs with no hypothesis match.

    A question is a research orphan iff it has no hypothesis match AND at least
    one of its resolved aspects is not ``software-development``. Pure-software
    questions without hypothesis matches are out of scope for research synthesis.

    There is deliberately NO ``count_research_orphans``: the count is
    ``len(result.rows)``. A separate counter is a second definition of the
    predicate, and it drifted from this one in practice (fb-2026-07-11-014).
    """
    project_aspects = load_project_aspects(project_root)
    research_filter = {a for a in project_aspects if a != SOFTWARE_ASPECT}
    orphans = [
        qid
        for qid, output in resolved.items()
        if output.primary_hypothesis is None
        and matches_aspect_filter(output.resolved_aspects, research_filter)
    ]
    return InstrumentResult.from_rows(sorted(orphans))
```

Add `from science_tool.instruments import InstrumentResult` to the imports.

Update the caller at `:146`:

```python
        actual = len(list_research_orphans(resolved, project_root).rows)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_big_picture_validator.py -v`
Expected: PASS

- [ ] **Step 5: Update the command doc**

In `commands/big-picture.md:206`, replace the `count_research_orphans(...)` reference with:

```markdown
- Compute via `list_research_orphans(resolved, project_root)` from `science_tool.big_picture.validator`. `orphan_question_count` is `len(result.rows)` and `orphan_ids` is `result.rows` — **the same call**, so the count and the ID list cannot disagree. The predicate excludes questions whose resolved aspects are only `[software-development]`. Do not re-derive either value by hand.
```

- [ ] **Step 6: Verify nothing still references the deleted function**

Run: `cd science && grep -rn "count_research_orphans" src/ tests/ ../commands/ ../skills/ ../agents/`
Expected: **no matches.**

- [ ] **Step 7: Drain the allowlist, full suite**

Remove `("big_picture/validator.py", "count_research_orphans")` from `_ALLOWLIST`.

Run: `cd science && uv run --frozen pytest && uv run ruff check && uv run pyright`
Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add science/src/science_tool/big_picture/validator.py \
        science/tests/test_big_picture_validator.py \
        science/tests/test_instrument_boundary.py \
        commands/big-picture.md
git commit -m "refactor(big-picture): replace count_research_orphans with list_research_orphans

The count and a hand-derived orphan_ids list disagreed downstream (40 vs 31).
The count is now len(rows) of the same call, so there is no second definition
of the predicate to drift from."
```

---

### Task 5: Manifest envelope v2 — walked-but-empty vs never-walked

**Files:**
- Modify: `science/src/science_tool/graph/io.py:133-143` (write), `:258-262` (timestamp), `:271-295` (read), `:298-347` (build)
- Modify: `science/src/science_tool/graph/store/validation.py:285-327`
- Modify: `science/src/science_tool/validate/checks/graph.py:218`
- Test: `science/tests/test_graph_io_revision_manifest.py`

**Interfaces:**
- Consumes: `InstrumentResult` (Task 1).
- Produces:
  - `build_input_manifest(graph_path) -> RevisionManifest` where `RevisionManifest` is a `TypedDict` `{"schema": int, "walked": list[str], "files": dict[str, dict[str, int | str]]}`.
  - `read_revision_manifest(dataset) -> RevisionManifest | None` — **`None`** for an absent or v1 (envelope-less) manifest.
  - `diff_graph_inputs_dataset(dataset, *, graph_path, mode) -> InstrumentResult[dict[str, str]]`.

**The two bugs (design §4).** `build_input_manifest` hard-codes an include list omitting `pp.entities_dir` (`:305-312`), and its `except` fallback omits it too (`:317`). Appending it closes the reported bug but **not the class** — the next directory added to the layout reintroduces the identical silence. So the manifest also records **which directories it walked**.

**This needs an envelope, not an extra key.** Today the manifest is `path → {sha256, mtime_ns}`, and both `read_revision_manifest` and `_revision_timestamp_from_manifest` iterate `.values()` expecting a file record — a top-level `walked` key would be parsed **as a file**.

**A v1 baseline is an unwired instrument.** It records no walk set, so `graph diff` cannot know what its baseline covered. It reports `unwired` / `baseline_predates_walk_set` and demands a rebuild. This is *not* a compatibility layer (the repo forbids those): it is the ruling applied to itself. It costs nothing — the first rebuild is mandatory regardless (~2,600 new entries in MM30, every entity reporting `new_file` once).

- [ ] **Step 1: Write the failing tests**

Append to `science/tests/test_graph_io_revision_manifest.py`. That module already
defines `_seed_project(root: Path, science_yaml: str) -> None` (it writes
`science.yaml`, `doc/`, and `knowledge/`) — **reuse it; do not add a new scaffold.**

```python
_SCIENCE_YAML = "name: fixture\nprofile: research\n"


def test_manifest_walks_entities_dir(tmp_path: Path) -> None:
    """fb-2026-07-11-016: entities/ was never in the include list."""
    _seed_project(tmp_path, _SCIENCE_YAML)
    qdir = tmp_path / "entities" / "questions"
    qdir.mkdir(parents=True)
    (qdir / "0001-q.md").write_text("---\nid: question:0001\n---\n", encoding="utf-8")

    manifest = build_input_manifest(tmp_path / "knowledge" / "graph.trig")

    assert "entities" in manifest["walked"]
    assert any(p.startswith("entities/") for p in manifest["files"])


def test_manifest_records_walked_dirs_even_when_empty(tmp_path: Path) -> None:
    """Walked-but-empty must be distinguishable from never-walked.

    This is the CLASS fix. A test asserting only that entity files go stale passes
    on the one-line include-list change WITHOUT the walk-set contract -- which is
    exactly the false-confidence this design exists to stop.
    """
    _seed_project(tmp_path, _SCIENCE_YAML)
    (tmp_path / "entities").mkdir(parents=True)  # exists, but empty

    manifest = build_input_manifest(tmp_path / "knowledge" / "graph.trig")

    assert "entities" in manifest["walked"]
    assert not any(p.startswith("entities/") for p in manifest["files"])


def test_v1_baseline_reports_unwired(tmp_path: Path) -> None:
    """A pre-envelope manifest cannot say what it covered => must not claim 'up to date'."""
    import json

    from rdflib import Dataset, Literal

    from science_tool.graph.io import REVISION_URI, SCHEMA_NS, _graph_uri
    from science_tool.graph.store.validation import diff_graph_inputs_dataset

    _seed_project(tmp_path, _SCIENCE_YAML)
    graph_path = tmp_path / "knowledge" / "graph.trig"

    # The OLD bare-mapping form: no "schema", no "walked".
    dataset = Dataset()
    provenance = dataset.graph(_graph_uri("graph/provenance"))
    provenance.add(
        (
            REVISION_URI,
            SCHEMA_NS.text,
            Literal(json.dumps({"doc/notes.md": {"sha256": "abc", "mtime_ns": 1}})),
        )
    )

    result = diff_graph_inputs_dataset(dataset, graph_path=graph_path, mode="hybrid")

    assert result.status == "unwired"
    assert result.code == "baseline_predates_walk_set"
    assert result.rows == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science && uv run --frozen pytest tests/test_graph_io_revision_manifest.py -v`
Expected: FAIL — `TypeError: string indices must be integers` (manifest is still a bare mapping).

- [ ] **Step 3: Implement the envelope in `graph/io.py`**

Add near the top:

```python
from typing import TypedDict

MANIFEST_SCHEMA_VERSION = 2


class RevisionManifest(TypedDict):
    schema: int
    walked: list[str]
    files: dict[str, dict[str, int | str]]
```

Rewrite `build_input_manifest` (`:298`). The include list gains `pp.entities_dir`, the fallback gains `"entities"`, and both record what they walked:

```python
def build_input_manifest(graph_path: Path) -> RevisionManifest:
    project_root = project_root_from_graph_path(graph_path)

    try:
        from science_tool.paths import resolve_paths

        pp = resolve_paths(project_root)
        include_dirs: list[Path] = [
            pp.doc_dir,
            pp.specs_dir,
            pp.entities_dir,
            pp.papers_dir / "summaries",
            pp.code_dir,
            pp.tasks_dir,
            pp.knowledge_dir / "sources",
        ]
        notes_dir = project_root / "notes"
        if notes_dir.is_dir():
            include_dirs.append(notes_dir)
    except Exception:
        include_dirs = [
            project_root / d
            for d in ("doc", "specs", "entities", "notes", "papers/summaries", "code")
        ]

    # ... existing include_files / files-walk body, unchanged, producing `files` ...

    walked = sorted(
        {
            base.relative_to(project_root).as_posix()
            for base in include_dirs
            if base.is_dir()
        }
    )
    return RevisionManifest(
        schema=MANIFEST_SCHEMA_VERSION,
        walked=walked,
        files=files_map,
    )
```

(Rename the local `manifest` accumulator to `files_map`; the per-file loop body is unchanged.)

Rewrite `read_revision_manifest` (`:271`) to detect v1 and refuse it:

```python
def read_revision_manifest(dataset: Dataset) -> RevisionManifest | None:
    """Return the envelope, or None if absent / pre-envelope (v1).

    A v1 manifest is a bare ``{path: {...}}`` mapping with no walk set. It cannot
    say which directories it covered, so it cannot be diffed against — the caller
    must report ``unwired``, NOT "up to date".
    """
    provenance = dataset.graph(_graph_uri("graph/provenance"))
    manifest_literal = next(provenance.objects(REVISION_URI, SCHEMA_NS.text), None)
    if manifest_literal is None:
        return None

    try:
        loaded = json.loads(str(manifest_literal))
    except json.JSONDecodeError:
        return None
    if not isinstance(loaded, dict):
        return None
    if loaded.get("schema") != MANIFEST_SCHEMA_VERSION:
        return None  # v1 or unknown: refuse, do not guess

    raw_files = loaded.get("files")
    raw_walked = loaded.get("walked")
    if not isinstance(raw_files, dict) or not isinstance(raw_walked, list):
        return None

    files: dict[str, dict[str, int | str]] = {}
    for key, value in raw_files.items():
        if not isinstance(key, str) or not isinstance(value, dict):
            continue
        sha = value.get("sha256")
        mtime = value.get("mtime_ns")
        if not isinstance(sha, str) or not isinstance(mtime, int):
            continue
        files[key] = {"sha256": sha, "mtime_ns": mtime}

    return RevisionManifest(
        schema=MANIFEST_SCHEMA_VERSION,
        walked=[w for w in raw_walked if isinstance(w, str)],
        files=files,
    )
```

Update `_revision_timestamp_from_manifest` (`:258`) to read the envelope:

```python
def _revision_timestamp_from_manifest(manifest: RevisionManifest) -> str:
    latest_mtime_ns = max(
        (
            int(metadata["mtime_ns"])
            for metadata in manifest["files"].values()
            if isinstance(metadata, dict) and isinstance(metadata.get("mtime_ns"), int)
        ),
        default=0,
    )
    revision_time = datetime.fromtimestamp(latest_mtime_ns / 1_000_000_000, tz=timezone.utc)
    return revision_time.replace(microsecond=0).isoformat().replace("+00:00", "Z")
```

The write site at `:133-143` needs no change — `json.dumps(manifest, sort_keys=True, ...)` serializes the envelope as-is.

- [ ] **Step 4: Implement the diff in `graph/store/validation.py:285`**

```python
def diff_graph_inputs(graph_path: Path, mode: str) -> InstrumentResult[dict[str, str]]:
    dataset = _load_dataset(graph_path)
    return diff_graph_inputs_dataset(dataset, graph_path=graph_path, mode=mode)


def diff_graph_inputs_dataset(
    dataset: Dataset, *, graph_path: Path, mode: str
) -> InstrumentResult[dict[str, str]]:
    baseline = _read_revision_manifest(dataset)
    current = _build_input_manifest(graph_path=graph_path)

    if baseline is None:
        return InstrumentResult.unwired(
            code="baseline_predates_walk_set",
            reason=(
                "the persisted revision manifest has no recorded walk set "
                "(pre-envelope), so staleness cannot be determined; rebuild the graph"
            ),
        )

    unwalked = sorted(set(current["walked"]) - set(baseline["walked"]))
    if unwalked:
        return InstrumentResult.unwired(
            code="baseline_missing_directories",
            reason=(
                "the baseline manifest never walked "
                f"{', '.join(unwalked)}; staleness for those paths is unknown. "
                "Rebuild the graph."
            ),
        )

    rows: list[dict[str, str]] = []
    for rel_path, current_meta in current["files"].items():
        baseline_meta = baseline["files"].get(rel_path)
        if baseline_meta is None:
            rows.append({"path": rel_path, "status": "stale", "reason": "new_file"})
            continue

        mtime_changed = current_meta["mtime_ns"] != baseline_meta.get("mtime_ns")
        hash_changed = current_meta["sha256"] != baseline_meta.get("sha256")

        reason: str | None = None
        if mode == "mtime":
            if mtime_changed:
                reason = "mtime_changed"
        elif mode == "hash":
            if hash_changed:
                reason = "hash_changed"
        elif mode == "hybrid":
            if hash_changed:
                reason = "hash_changed"
            elif mtime_changed:
                reason = "mtime_changed"
        else:
            raise click.ClickException(f"Unsupported diff mode: {mode}")

        if reason is not None:
            rows.append({"path": rel_path, "status": "stale", "reason": reason})

    for removed in sorted(set(baseline["files"]) - set(current["files"])):
        rows.append({"path": removed, "status": "stale", "reason": "removed_file"})

    rows.sort(key=lambda row: row["path"])
    return InstrumentResult.from_rows(rows)
```

Add `from science_tool.instruments import InstrumentResult` to that module's imports.

- [ ] **Step 5: Update the consumer at `validate/checks/graph.py:218`**

```python
        diff = diff_graph_inputs_dataset(dataset, graph_path=graph_path, mode="hybrid")
        if diff.status == "unwired":
            yield Result(
                Severity.ERROR,
                None,
                None,
                f"graph-prose sync: staleness could not be determined — {diff.reason}",
                "graph",
                None,
            )
        elif diff.status == "empty":
            yield Result(Severity.INFO, None, None, "graph-prose sync: all inputs up to date", "graph", None)
        else:
            # ... existing stale-row reporting over diff.rows ...
```

Update the CLI consumer of `diff_graph_inputs` the same way — find it with
`cd science && grep -rn "diff_graph_inputs" src/science_tool/cli.py`.

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_graph_io_revision_manifest.py tests/ -k "manifest or diff" -v`
Expected: PASS

- [ ] **Step 7: Drain the allowlist, full suite**

Remove `("graph/store/validation.py", "diff_graph_inputs")` and `("graph/store/validation.py", "diff_graph_inputs_dataset")` from `_ALLOWLIST`.

Run: `cd science && uv run --frozen pytest && uv run ruff check && uv run pyright`
Expected: all pass. Snapshot tests may need `-m snapshot` regeneration; if a snapshot of `graph.trig` embeds the manifest literal, update it — the envelope is the intended change.

- [ ] **Step 8: Commit**

```bash
git add science/src/science_tool/graph/io.py \
        science/src/science_tool/graph/store/validation.py \
        science/src/science_tool/validate/checks/graph.py \
        science/src/science_tool/cli.py \
        science/tests/test_graph_io_revision_manifest.py \
        science/tests/test_instrument_boundary.py
git commit -m "fix(graph): manifest records its walk set; entities/ was never walked

build_input_manifest omitted entities_dir, so an entities-only commit reported
'all inputs up to date' and /science:update-graph would wrongly stop. The
manifest is now an envelope recording WHICH directories it walked, so
walked-but-empty is distinguishable from never-walked; a pre-envelope baseline
reports unwired and demands a rebuild rather than guessing."
```

---

### Task 6: The materialization lint — a field that materializes nothing is an error

**Files:**
- Create: `science/src/science_tool/validate/checks/materialization.py`
- Modify: `science/src/science_tool/validate/checks/__init__.py` (register in `CANONICAL_CHECK_MODULES`)
- Test: `science/tests/test_validate_materialization.py`

**Interfaces:**
- Consumes: the `@Check` decorator, `ValidateContext`, `Result`, `Severity`, `iter_entity_markdown`.
- Produces: check `check_non_materializing_fields`.

**The bug (fb-2026-07-11-017).** The graph source of truth for supersession is a `relations:` entry with predicate `sci:supersedes` — **not** a top-level `supersedes:` field (`consolidation.py:8-9`). MM30 has two interpretations that authored the top-level form; they materialize **zero** triples, with no warning. The graph has 0 `sci:supersedes` triples project-wide. Because `big-picture` derives `provenance_coverage` from these chains, the silent drop produces a wrong `thin` rating.

- [ ] **Step 1: Write the failing test**

```python
# science/tests/test_validate_materialization.py
from __future__ import annotations

from pathlib import Path

from science_tool.validate.result import Severity


def _interpretation(project: Path, name: str, extra: str) -> None:
    """Seed a minimal project with one interpretation entity.

    ValidateContext.from_project_root requires a real project root, so science.yaml
    must exist. Mirror the seeding form used by the other validate-check tests.
    """
    project.mkdir(parents=True, exist_ok=True)
    (project / "science.yaml").write_text("name: fixture\nprofile: research\n", encoding="utf-8")
    d = project / "entities" / "interpretations"
    d.mkdir(parents=True, exist_ok=True)
    (d / name).write_text(
        f"---\nid: interpretation:0001-x\nkind: interpretation\nstatus: active\n{extra}---\n\n# x\n",
        encoding="utf-8",
    )


def test_top_level_supersedes_is_an_error(tmp_path: Path) -> None:
    from science_tool.validate.checks.materialization import check_non_materializing_fields
    from science_tool.validate.context import ValidateContext

    project = tmp_path / "p"
    _interpretation(project, "0001-x.md", "supersedes: interpretation:0000-y\n")

    ctx = ValidateContext.from_project_root(project, strict=False, verbose=False)
    results = list(check_non_materializing_fields(ctx))

    assert [r.severity for r in results] == [Severity.ERROR]
    assert "supersedes" in results[0].message
    assert "relations:" in results[0].message


def test_relations_form_is_accepted(tmp_path: Path) -> None:
    from science_tool.validate.checks.materialization import check_non_materializing_fields
    from science_tool.validate.context import ValidateContext

    project = tmp_path / "p"
    _interpretation(
        project,
        "0001-x.md",
        "relations:\n  - predicate: sci:supersedes\n    object: interpretation:0000-y\n",
    )

    ctx = ValidateContext.from_project_root(project, strict=False, verbose=False)
    results = list(check_non_materializing_fields(ctx))

    assert results == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_validate_materialization.py -v`
Expected: FAIL — `ModuleNotFoundError: ...checks.materialization`

- [ ] **Step 3: Implement**

```python
# science/src/science_tool/validate/checks/materialization.py
"""Validation check: a frontmatter field that materializes nothing is an error.

The authoring-side face of the silent-instrument ruling. A top-level
``supersedes:`` / ``amends:`` key looks authoritative and produces ZERO triples —
the graph source of truth is a ``relations:`` entry with the corresponding
predicate (see graph/consolidation.py). A pure no-op field is worse than a wrong
one: nothing surfaces, and downstream metrics computed from the missing chains
(``provenance_coverage`` in big-picture) silently take a wrong value.

Severity is ERROR, not WARN: the author's intent was recorded nowhere.
"""

from __future__ import annotations

from collections.abc import Iterator

from science_tool.entity_scan import iter_entity_markdown
from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity

#: Top-level frontmatter keys that materialize NOTHING and must be authored as
#: a ``relations:`` entry with the given predicate instead.
_NON_MATERIALIZING: dict[str, str] = {
    "supersedes": "sci:supersedes",
    "amends": "sci:amends",
}


@Check(section="non-materializing frontmatter fields", order=23)
def check_non_materializing_fields(ctx: ValidateContext) -> Iterator[Result]:
    for entity in iter_entity_markdown(ctx.project_root):
        fm = entity.frontmatter or {}
        for field, predicate in _NON_MATERIALIZING.items():
            if field not in fm:
                continue
            yield Result(
                Severity.ERROR,
                entity.path,
                fm.get("id"),
                (
                    f"top-level '{field}:' materializes no triples and is silently "
                    f"ignored by the graph. Author it as a relations: entry with "
                    f"predicate '{predicate}' instead."
                ),
                "materialization",
                None,
            )
```

Register it: add `"materialization"` to `CANONICAL_CHECK_MODULES` in
`science/src/science_tool/validate/checks/__init__.py`, after `"origins"`.

> **Note for the implementer:** `iter_entity_markdown` and `ValidateContext`'s
> attribute names must match the existing checks. Read
> `science/src/science_tool/validate/checks/origins.py` first and mirror its exact
> import and iteration form — do not invent an API.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_validate_materialization.py -v`
Expected: PASS

- [ ] **Step 5: Full suite, lint, types**

Run: `cd science && uv run --frozen pytest && uv run ruff check && uv run pyright`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/validate/checks/materialization.py \
        science/src/science_tool/validate/checks/__init__.py \
        science/tests/test_validate_materialization.py
git commit -m "feat(validate): error on frontmatter fields that materialize no triples

A top-level supersedes:/amends: key is a pure no-op -- the graph reads a
relations: entry with the predicate. MM30 authored two and got zero triples,
no warning, and a wrong provenance_coverage rating downstream."
```

---

### Task 7: Bulk migration — `graph/store/{summary,queries,inquiry}.py`

**Files:**
- Modify: `science/src/science_tool/graph/store/summary.py` (8 helpers), `queries.py` (3), `inquiry.py` (2)
- Modify: their CLI consumers and tests.

**Interfaces:**
- Consumes: `InstrumentResult` (Task 1).
- Produces: each listed helper returns `InstrumentResult[dict[str, str]]`.

**Method.** These are graph read helpers over an rdflib `Dataset`. Each one's precondition is the same question: *can this instrument fail to run, as opposed to genuinely finding nothing?* For most, the honest answer is **no** — a query over a well-formed graph that matches nothing genuinely found nothing. Those use `InstrumentResult.from_rows(rows)` and are `ok`/`empty` only. **Do not invent an `unwired` state where none exists** — a spurious `unwired` is as dishonest as a spurious `empty`.

The one that *does* have a precondition is `query_gaps`: it resolves a `center` argument. If the center does not resolve to an entity in the graph, the instrument did not run.

- [ ] **Step 1: Write the failing test for the one real precondition**

Append to `science/tests/test_query_gaps_contested.py` — the module that already
covers `query_gaps`. Reuse whatever graph fixture that module already builds; do
**not** invent a new one.

```python
def test_query_gaps_unresolvable_center_is_unwired(tmp_path: Path) -> None:
    """A bogus center mints a URI that appears in no triple, so the BFS returns [].
    That empty list is indistinguishable from 'no gaps' -- it must be unwired."""
    from science_tool.graph.store.summary import query_gaps

    graph_path = _build_graph(tmp_path)  # <- the fixture helper THIS module already defines

    result = query_gaps(graph_path, center="hypothesis:does-not-exist", hops=2, limit=10)

    assert result.status == "unwired"
    assert result.code == "center_not_in_graph"
    assert result.rows == []
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_query_gaps_contested.py -v`
Expected: FAIL — `AttributeError: 'list' object has no attribute 'status'`

- [ ] **Step 3: Migrate the thirteen helpers**

For each of the 13, change the return annotation to `InstrumentResult[dict[str, str]]` and wrap the final `return rows` as `return InstrumentResult.from_rows(rows)`.

`query_gaps` (`summary.py:754`) additionally guards its center. `_resolve_center_entity` currently raises or returns a URI; make the non-resolution path explicit:

```python
def query_gaps(
    graph_path: Path,
    center: str,
    hops: int,
    limit: int,
) -> InstrumentResult[dict[str, str]]:
    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))
    provenance = dataset.graph(_graph_uri("graph/provenance"))

    center_uri = _resolve_center_entity(center)
    # NOTE: _resolve_center_entity (graph/store/identity.py:126) ALWAYS returns a
    # URIRef -- it never returns None and never raises. A bogus center silently
    # mints a URI that appears nowhere in the graph, and the BFS then starts from
    # an isolated node and returns []. That empty list is precisely the lie this
    # design exists to stop, so the membership test below is the whole fix.
    if (center_uri, None, None) not in knowledge and (None, None, center_uri) not in knowledge:
        return InstrumentResult.unwired(
            code="center_not_in_graph",
            reason=f"center {center!r} resolves to {center_uri}, which appears in no triple",
        )

    # ... existing BFS body, unchanged, producing `rows` ...

    return InstrumentResult.from_rows(rows)
```

Update every CLI consumer: `cd science && grep -rn "query_dashboard_summary\|query_neighborhood_summary\|query_question_summary\|query_inquiry_summary\|query_gaps\|query_neighborhood\|query_claims\|query_evidence\|list_inquiries\|query_predicates" src/science_tool/cli.py` and change each `rows = query_x(...)` to `result = query_x(...)`, emitting `result.reason` when set and branching on `result.status == "unwired"` before rendering.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/graph/ -v`
Expected: PASS

- [ ] **Step 5: Drain the allowlist**

Remove all 13 `graph/store/*` entries from `_ALLOWLIST` (leave `graph/health.py` and `graph/attention.py` — Tasks 8 and 9).

- [ ] **Step 6: Full suite, lint, types**

Run: `cd science && uv run --frozen pytest && uv run ruff check && uv run pyright`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add science/src/science_tool/graph/store/ science/src/science_tool/cli.py \
        science/tests/graph/ science/tests/test_instrument_boundary.py
git commit -m "refactor(graph): migrate store query helpers to InstrumentResult

query_gaps gains a real precondition: an unresolvable center means the
instrument did not run. The rest genuinely cannot be unwired and are ok/empty
only -- a spurious unwired is as dishonest as a spurious empty."
```

---

### Task 8: Bulk migration — `graph/health.py`

**Files:**
- Modify: `science/src/science_tool/graph/health.py` (10 `collect_*` helpers)
- Modify: their consumers (`science health` CLI) and tests.

**Interfaces:**
- Consumes: `InstrumentResult` (Task 1).
- Produces: each `collect_*` returns `InstrumentResult[<its existing row type>]` — e.g. `collect_unresolved_refs -> InstrumentResult[UnresolvedRef]`. **Row types are unchanged.**

**Precondition analysis (do this before writing code).** These are the health instruments, and they are the ones most likely to have a real `unwired` state — a check that scans a directory that does not exist has not "found no problems", it has not run. For each of the 10, ask: *is there an input whose absence makes an empty result meaningless?* A directory that does not exist, a graph layer that is missing, a registry that failed to load — those are `unwired`. A directory that exists and is clean is `empty`.

- [ ] **Step 1: Enumerate the helpers and their preconditions**

Run: `cd science && grep -n "^def collect_" src/science_tool/graph/health.py`

For each, write one line in a scratch note: helper → precondition (or "none — cannot be unwired"). This is the actual intellectual work of the task; the code that follows is mechanical.

- [ ] **Step 2: Write the failing tests**

For each helper with a real precondition, add a test asserting `status == "unwired"` and a specific `code` when that precondition is absent. For each helper without one, add a test asserting a clean project yields `status == "empty"` (not `unwired`).

Run: `cd science && uv run --frozen pytest tests/ -k health -v`
Expected: FAIL

- [ ] **Step 3: Migrate**

Change each return annotation to `InstrumentResult[...]`; return `InstrumentResult.unwired(code=..., reason=...)` on an absent precondition and `InstrumentResult.from_rows(rows)` otherwise.

- [ ] **Step 4: Update consumers**

Run: `cd science && grep -rn "collect_unresolved_refs\|collect_unregistered_ref_kinds\|collect_lingering_tags\|collect_validation_findings" src/`

The `science health` renderer must surface `unwired` distinctly — this is the command that fb-2026-07-10-021 says currently "spams skip warnings", so an unwired health check must read as a *failure to check*, not a clean bill.

- [ ] **Step 5: Run tests, drain allowlist, full suite**

Remove the four `graph/health.py` entries from `_ALLOWLIST`.

Run: `cd science && uv run --frozen pytest && uv run ruff check && uv run pyright`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/graph/health.py science/tests/ science/tests/test_instrument_boundary.py
git commit -m "refactor(health): migrate collect_* helpers to InstrumentResult

A health check that could not scan its input has not found zero problems."
```

---

### Task 9: `graph/attention.py` — return shape ONLY

**Files:**
- Modify: `science/src/science_tool/graph/attention.py` (3 helpers)

**Interfaces:**
- Produces: `compute_attention_candidates -> InstrumentResult[AttentionCandidate]`, `query_attention_sample -> InstrumentResult[dict[str, Any]]`, `query_attention_ranked -> InstrumentResult[dict[str, Any]]`.

> **SCOPE FENCE — read this before touching the file.**
> **Do NOT change the scoring model.** `days_since_last_review` is a *multiplicative*
> term (`attention.py:110`): at its constant fallback of `365` it is a uniform
> 13.17× factor on every candidate, so it currently cancels out of the ranking
> entirely. Fixing that is a scoring decision — it needs per-row component
> availability and a ruling on mixed stamped/unstamped candidates, and naively
> "omitting the term" would make unstamped entities dominate the ranking the moment
> review events start being stamped. That work is **fb-2026-07-10-023 + fb-2026-07-11-005**
> and has its own design. **This task migrates the return shape and nothing else.**
> If you find yourself editing the `weight = (...)` expression, stop.

- [ ] **Step 1: Migrate the three signatures**

Change each return annotation to `InstrumentResult[...]` and wrap the final return in `InstrumentResult.from_rows(...)`. Leave every arithmetic expression byte-for-byte unchanged.

- [ ] **Step 2: Verify the scoring is untouched**

Run: `cd science && git diff src/science_tool/graph/attention.py | grep -E "^[+-].*(weight|days_since|multiplier|factor)"`
Expected: **no output.** Any hit means the scope fence was crossed — revert those lines.

- [ ] **Step 3: Update consumers, run tests**

Run: `cd science && grep -rn "compute_attention_candidates\|query_attention_sample\|query_attention_ranked" src/ && uv run --frozen pytest -k attention -v`
Expected: PASS

- [ ] **Step 4: Drain allowlist, full suite, commit**

Remove the three `graph/attention.py` entries from `_ALLOWLIST`.

```bash
cd science && uv run --frozen pytest && uv run ruff check && uv run pyright
git add science/src/science_tool/graph/attention.py science/tests/test_instrument_boundary.py
git commit -m "refactor(attention): migrate return shape to InstrumentResult

Return shape only. The days_since_last_review scoring defect is a separate
design (it is multiplicative, so the 365 constant is inert -- and the naive
repair would make unstamped entities dominate the ranking)."
```

---

### Task 10: The tuple precursors and `curate/inventory.py`

**Files:**
- Modify: `science/src/science_tool/benchmark_catalog.py` (`list_benchmarks`), `datasets_catalog.py` (`list_datasets`), `curate/inventory.py`

**Interfaces:**
- Produces: `list_benchmarks -> InstrumentResult[BenchmarkRow]`, `list_datasets -> InstrumentResult[dict]`.

These two independently grew `tuple[list[T], str | None]` — an ad-hoc reason channel, invented twice, before this type existed. That second element **is** `InstrumentResult.reason`. Converge them.

- [ ] **Step 1: Migrate the two catalogs**

```python
def list_benchmarks(...) -> InstrumentResult[BenchmarkRow]:
    # ... existing body producing `rows` and `warning: str | None` ...
    return InstrumentResult.from_rows(rows, reason=warning)
```

Same shape for `list_datasets`. Update every caller: `cd science && grep -rn "list_benchmarks\|list_datasets" src/` — each currently unpacks a 2-tuple (`rows, warning = list_x(...)`) and must become `result = list_x(...)`.

- [ ] **Step 2: `curate/inventory.py`**

`collect_inventory -> CurationInventory` already returns a typed payload, so it does **not** violate the guard. It is in `INSTRUMENT_MODULES` because fb-2026-07-10-017 reports its payload diverging from the command spec (missing `unresolved-ref` / `stale-task` / `long_idle` keys) — **that is the curate spec's problem, not this one.** Leave the behavior alone; confirm only that the guard passes for this module.

Run: `cd science && uv run --frozen pytest tests/test_instrument_boundary.py -v`

- [ ] **Step 3: Drain the allowlist, run everything**

Remove the two catalog entries from `_ALLOWLIST`. The allowlist should now be **empty** — replace it with `frozenset()`.

Run: `cd science && uv run --frozen pytest && uv run ruff check && uv run pyright`
Expected: all pass, with an empty allowlist.

- [ ] **Step 4: Commit**

```bash
git add science/src/science_tool/benchmark_catalog.py \
        science/src/science_tool/datasets_catalog.py \
        science/tests/test_instrument_boundary.py science/tests/
git commit -m "refactor(catalogs): converge the ad-hoc tuple reason channel onto InstrumentResult

list_benchmarks and list_datasets each independently grew a
tuple[list, str|None] reason channel. That second element was InstrumentResult
.reason all along. The allowlist is now empty: the migration is complete."
```

---

### Task 11: Close out — the guard is the definition of done

**Files:**
- Modify: `science/tests/test_instrument_boundary.py` (assert the allowlist is empty)
- Modify: `docs/plans/2026-07-11-instrument-result-convergence-design.md` (Status → Implemented)

- [ ] **Step 1: Make the empty allowlist permanent**

Add to the guard:

```python
def test_allowlist_is_empty() -> None:
    """The migration is complete. A new entry here is a regression, not a carve-out.

    Per the convergence design: an allowlist entry the guard would still flag means
    the migration is incomplete -- NOT a carve-out to add.
    """
    assert _ALLOWLIST == frozenset(), (
        "The instrument-result migration is finished. Do not re-open the allowlist; "
        "migrate the helper instead."
    )
```

- [ ] **Step 2: Run the full acceptance set from the design**

```bash
cd science && uv run --frozen pytest && uv run ruff check && uv run pyright
cd science/model && uv run --frozen pytest
cd science && grep -rn "count_research_orphans" src/ tests/ ../commands/ ../skills/ ../agents/
```

Expected: all tests pass; the `grep` returns **no matches**.

- [ ] **Step 3: Update the design doc status**

Change `## Status` from `Decision-ready.` to `Implemented on branch `instrument-result-convergence`.` and note the two carve-outs that remain open (attention-ranking correctness; curate inventory payload).

- [ ] **Step 4: Commit**

```bash
git add science/tests/test_instrument_boundary.py \
        docs/plans/2026-07-11-instrument-result-convergence-design.md
git commit -m "test(instruments): lock the allowlist empty; the convergence is complete"
```

---

## Self-Review

**Spec coverage.** Design §1 (the type + enforced invariant) → Task 1. §1 renderer contract → Task 3 Step 5. §2 structural query → Task 2 (`INSTRUMENT_MODULES`, imported by the guard so the two cannot drift). §2 four-state precondition → Task 3. §2 partial-resolution caveat channel → Task 1 (`ok` may carry `reason`) + Task 3. §2 scalar counters prohibited → Task 4. §2 attention out-of-scope → Task 9's scope fence. §2 tuple precursors → Task 10. §3 guard + additive ratchet + known gaps → Task 2. §4 walk-side (graph diff, envelope, v1-as-unwired) → Task 5. §4 authoring-side (`supersedes:` lint) → Task 6. Bulk namespace → Tasks 7–10. Acceptance criteria → Task 11 Step 2.

**APIs verified against the tree** (a first draft of this plan invented all four;
they are corrected above and listed so a reader can re-check them cheaply):

- `ValidateContext.from_project_root(root, strict=False, verbose=False)` — it is a
  dataclass with six+ required fields, so `ValidateContext(project_root=...)` does
  **not** construct.
- `test_graph_io_revision_manifest.py` defines `_seed_project(root, science_yaml)`.
  There is no `_scaffold_project`.
- `query_gaps` is covered by `tests/test_query_gaps_contested.py`. There is no
  `tests/graph/test_store_summary.py`.
- `_resolve_center_entity` (`graph/store/identity.py:126`) returns `URIRef`
  **unconditionally** — never `None`, never raising. This is *why* a bogus center
  currently yields a silent `[]`, and why the fix is a graph-membership test rather
  than a null check.

**Known gaps in this plan, stated rather than hidden:**

1. **Task 8's preconditions are not pre-written.** I did not enumerate the 10 `graph/health.py` helpers' individual preconditions, because determining them requires reading each one's body and the honest answer differs per helper. Step 1 of that task makes the enumeration the explicit first deliverable. This is the one place the plan hands real judgment to the implementer rather than pre-deciding it — by design, but worth knowing.

2. **The renderer contract cannot be unit-tested.** `commands/big-picture.md` is prose executed by an LLM orchestrator. Task 3 Step 5 fixes the instruction, but nothing enforces that the orchestrator obeys it. The Python guarantees the *data* is honest; only review guarantees the *prose* is.

3. **Task 5's blast radius is real.** The first graph rebuild in any consuming project stamps every entity file as `new_file` once (~2,600 in MM30). This is expected, not a bug — but it will look alarming, and any downstream project pinning a `graph.trig` snapshot in a test will need it regenerated.

4. **Two feedback items in `INSTRUMENT_MODULES` are deliberately NOT fixed here** — `curate/inventory.py`'s payload divergence (fb-2026-07-10-017) and the attention scoring model (fb-2026-07-10-023). They are in the namespace so the guard covers their *shape*; their *behavior* belongs to other specs.

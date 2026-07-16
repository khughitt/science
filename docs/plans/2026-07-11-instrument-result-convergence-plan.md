# InstrumentResult Convergence Implementation Plan

> **UPDATE 2026-07-15 — item 3 IMPLEMENTED (pending merge).** The attention-ranking
> follow-on pair (fb-2026-07-10-023 + fb-2026-07-11-005) is implemented on branch
> `attention-recency-correctness` — see `docs/plans/2026-07-15-attention-recency-correctness-design.md`.
> The redundant `days_since_last_review` term was deleted; fb-2026-07-11-005 was already
> handled by the `_is_closed` terminal drop. **This banner supersedes every statement below
> that describes the attention-ranking pair as open or still-live.**

> **VALIDATOR-PAYLOAD STATUS UPDATE (2026-07-15) — supersedes every "open", "live",
> "deferred", and "out of scope" statement about follow-on item 2 below.** The validator-
> and-audit payload convergence is **SHIPPED** — merged to local `main` at `c4aa77c7`.
> `ValidationVerdict[RowT]` now carries passed/failed/unwired explicitly,
> all consumers fail closed on unwired, and the boundary guard rejects both tuple precursor
> families. The deferred implementation account below is retained as historical rationale;
> its explanation of why `InstrumentResult` could not absorb the orthogonal `has_failures`
> channel remains valid. See
> [`2026-07-15-validation-verdict-convergence-design.md`](2026-07-15-validation-verdict-convergence-design.md).

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make it structurally impossible for an instrument to report a clean empty result when it never actually ran.

**Architecture:** Canonicalize one `InstrumentResult` type whose Pydantic validator makes the invalid states unconstructable (`ok` with no rows, `empty` with rows, `unwired` with rows or without a machine code). Migrate the ~30 bare-collection helpers in the instrument namespace onto it. Ratchet with an AST guard in the shape of the five existing boundary guards, whose module list *is* the migration query — one expression, imported by both, so they cannot drift.

**Tech Stack:** Python 3.12, Pydantic v2, Click, rdflib, pytest, ruff, pyright. Package: `science/` (uv, `pyproject.toml`).

**Design doc:** [`2026-07-11-instrument-result-convergence-design.md`](2026-07-11-instrument-result-convergence-design.md). Read it before Task 1; it carries the rulings this plan implements.

> **fb-2026-07-11-017 STATUS UPDATE (2026-07-15) — supersedes every "open"/"live"
> statement about it below.** The materialization lint is now **SHIPPED** — merged to local
> `main` at `8e5e4709`; fb-2026-07-11-017 is CLOSED.
> The per-kind key vocabulary this design deferred it for proved unnecessary: legitimacy is
> one **semantic** top-level reader (`qa_audit/runs.py:47`, the QA-audit chain), encoded as
> an explicit `(workflow-run, supersedes)` exception — not a schema derivation, and not the
> generic entity-deletion reference cleanup, which reads the key but assigns it no
> supersession semantics. See
> [`2026-07-15-non-materializing-fields-design.md`](2026-07-15-non-materializing-fields-design.md)
> and [`2026-07-15-non-materializing-fields-plan.md`](2026-07-15-non-materializing-fields-plan.md).
> Everything below about fb-2026-07-11-017 is retained as the historical *withdrawn* record.

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
- Produces: `_ALLOWLIST: frozenset[tuple[str, str]]` — un-migrated **instruments**, drained to empty by Tasks 3–10. And `_NOT_INSTRUMENTS: frozenset[tuple[str, str]]` — pure/total helpers in the namespace that **cannot be unwired** and must never be wrapped (design non-goals). Permanent, one justification each.

**Why an allowlist and not a big-bang:** the helpers cannot migrate in one reviewable commit. The ratchet blocks *new* violations immediately while the existing set drains. Per the convergence design: an allowlist entry the guard would still flag means the migration is incomplete — **not** a carve-out to add.

> **DO NOT HAND-WRITE THE ALLOWLIST.** The design's central lesson (its line 189)
> is: *"Do not migrate from this list. Regenerate the set with that structural query
> at implementation time."* A hand-transcribed seed in an earlier draft of this plan
> was wrong by more than 2× (it listed 24 entries; the tree has 49) and silently
> omitted whole helpers, which would have let the allowlist "empty out" while real
> violations remained. **Generate it. Step 1 below is the generation step.**

- [ ] **Step 1: Write the guard with an EMPTY allowlist, then generate the seed**

Write the guard file exactly as below, leaving `_ALLOWLIST` and `_NOT_INSTRUMENTS`
empty. The test will fail, listing every violation — **that output is the seed.**

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

# Un-migrated INSTRUMENTS. DRAIN THIS TO EMPTY. Do not add to it.
# GENERATED in Step 2 -- do not hand-write.
_ALLOWLIST: frozenset[tuple[str, str]] = frozenset()

# Pure/total helpers that live in the namespace but are NOT instruments: they
# cannot fail to run, so a status surface would be ceremony without safety (see
# the design's Non-goals). PERMANENT. Every entry carries a justification.
# An entry here is a claim that the function cannot be unwired. If that is false,
# the entry is a bug, not a carve-out.
_NOT_INSTRUMENTS: frozenset[tuple[str, str]] = frozenset()

# Helpers that ARE instruments but are NOT migrated by this pass -- because the type
# cannot express their shape (see coverage_summary, Task 2b) or their payload (see the
# validator has_failures channel, Task 7).
#
# This set exists so that "deferred" can never be spelled "_NOT_INSTRUMENTS". An entry
# here is an ADMISSION OF INCOMPLETENESS, not an exoneration: the defect is still live.
# test_migration_is_complete (Task 11) asserts this set is EMPTY, so a deferral cannot
# be parked here quietly -- it must be paid off, or the design's completion criteria
# must be explicitly amended to bless it. Silence is not an option the guard offers.
_DEFERRED_INSTRUMENTS: frozenset[tuple[str, str]] = frozenset()

_BARE_COLLECTIONS = {"list", "dict", "int", "set"}


def _annotation_root(node: ast.expr) -> str | None:
    """Return the root name of an annotation: list[X] -> 'list', dict -> 'dict'."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Subscript):
        return _annotation_root(node.value)
    return None


def _is_str_or_none(node: ast.expr) -> bool:
    """Match ``str | None`` (and ``Optional[str]``)."""
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        sides = {ast.unparse(node.left), ast.unparse(node.right)}
        return sides == {"str", "None"}
    if isinstance(node, ast.Subscript) and _annotation_root(node) == "Optional":
        return ast.unparse(node.slice) == "str"
    return False


def _is_tuple_precursor(node: ast.expr) -> bool:
    """Match ``tuple[list[T], str | None]`` — the ad-hoc REASON channel, precisely.

    Deliberately NOT ``tuple[list[T], ...]``. The validator family returns
    ``tuple[list[...], bool]``, where the bool is ``has_failures`` — an independent
    pass/fail channel, not a reason string (validation.py:187 computes it as
    ``any(row["status"] == "fail" ...)``, so it is NOT ``bool(rows)``). Sweeping
    those in would force them through a type whose ``status`` cannot carry them:
    for a validator, ``ok`` means "found rows", i.e. found PROBLEMS — orthogonal to
    pass/fail, not a synonym for it. See "Deferred: the validator payload" below.
    """
    if not isinstance(node, ast.Subscript):
        return False
    if _annotation_root(node) != "tuple":
        return False
    inner = node.slice
    if not isinstance(inner, ast.Tuple) or len(inner.elts) != 2:
        return False
    return _annotation_root(inner.elts[0]) == "list" and _is_str_or_none(inner.elts[1])


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


def _known(module_rel: str, fn: str) -> bool:
    return (module_rel, fn) in _ALLOWLIST | _NOT_INSTRUMENTS | _DEFERRED_INSTRUMENTS


def test_instrument_namespace_returns_instrument_result() -> None:
    offenders: list[str] = []
    for module_rel in INSTRUMENT_MODULES:
        for fn in _violations(module_rel):
            if not _known(module_rel, fn):
                offenders.append(f'        ("{module_rel}", "{fn}"),')
    assert not offenders, (
        "These namespace helpers return a bare collection. Each is EITHER an\n"
        "instrument (-> migrate it to InstrumentResult, or park it in _ALLOWLIST)\n"
        "OR a pure/total helper that cannot be unwired (-> _NOT_INSTRUMENTS, with a\n"
        "justification). An empty list cannot say whether an instrument ran:\n"
        + "\n".join(sorted(offenders))
    )


def test_allowlist_has_no_stale_entries() -> None:
    """A listed helper that no longer violates must be REMOVED from its set.

    This is what forces the ratchet to drain instead of rotting.
    """
    stale = [
        f"{module_rel}::{fn}"
        for (module_rel, fn) in _ALLOWLIST | _NOT_INSTRUMENTS | _DEFERRED_INSTRUMENTS
        if fn not in _violations(module_rel)
    ]
    assert not stale, (
        "These helpers are listed but no longer violate the boundary. "
        "Delete them:\n  " + "\n  ".join(sorted(stale))
    )


def test_sets_are_disjoint() -> None:
    """A helper is an instrument, or it is not. It cannot be filed as both.

    _NOT_INSTRUMENTS asserts "cannot be unwired". _DEFERRED_INSTRUMENTS asserts
    "can be unwired, and still is". An entry in both is a contradiction on its face.
    """
    for a, b, names in (
        (_ALLOWLIST, _NOT_INSTRUMENTS, "_ALLOWLIST/_NOT_INSTRUMENTS"),
        (_ALLOWLIST, _DEFERRED_INSTRUMENTS, "_ALLOWLIST/_DEFERRED_INSTRUMENTS"),
        (_NOT_INSTRUMENTS, _DEFERRED_INSTRUMENTS, "_NOT_INSTRUMENTS/_DEFERRED_INSTRUMENTS"),
    ):
        assert not (a & b), f"{names} overlap: {sorted(a & b)}"
```

- [ ] **Step 2: GENERATE the seed — do not transcribe it**

Run: `cd science && uv run --frozen pytest tests/test_instrument_boundary.py -v`

Expected: **FAIL**, with the assertion message printing every violation as a
paste-ready `("module", "function"),` line. That output *is* the seed.

Paste all of it into `_ALLOWLIST`. Re-run; the guard now passes. (At the time of
writing the tree yields **49** violations across the 11 modules — but do not trust
that number: use whatever the guard prints, since it is generated from the code and
this plan is not.)

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

### Task 2b: Triage the seed — instrument vs. pure helper

**Files:**
- Modify: `science/tests/test_instrument_boundary.py` (`_ALLOWLIST` → `_NOT_INSTRUMENTS` moves)
- Create: `docs/plans/2026-07-11-instrument-triage.md` (the classification, with one justification per non-instrument)

**This is the intellectual core of the migration and it is deliberately its own task.** The generated seed conflates two very different things:

- **Instruments** — a helper whose empty return renders to a user as a finding. `query_gaps`, `collect_unresolved_refs`, `diff_graph_inputs`, `query_predicates`. These **migrate**.
- **Pure/total helpers** — cannot fail to run; an empty return means the input was empty, full stop. `weighted_sample_without_replacement` (a sampling utility), `format_attention_candidate`, `format_show`. Wrapping these is *"ceremony without safety"* and it **dilutes what the guard means** — the design's non-goals forbid it explicitly.

The `validate_*` family (`validate_graph`, `validate_inquiry`, `validate_synthesis_file`, `validate_empirical_run_resolution`) is the interesting middle. **They are instruments.** A validator that returns `[]` because it could not load the graph has not found zero problems — that is precisely this design's failure, wearing a different name. Classify them as instruments unless you can show the check cannot fail to run.

- [ ] **Step 1: Classify every seeded entry**

For each entry the guard printed, decide **instrument** or **not-instrument**, and write one line of justification. Record the table in `docs/plans/2026-07-11-instrument-triage.md`.

The bar for **not-instrument** is high and specific: *there is no input whose absence would make an empty return meaningless.* "It probably always works" does not clear that bar. When in doubt, classify as an instrument — a needless `ok`/`empty` result is harmless; a missed `unwired` is the bug this whole design exists to stop.

#### `InstrumentResult` is ROW-shaped. It cannot carry a mapping.

`rows` is `list[RowT]`. Two flagged helpers return a `dict`, and **neither can be wrapped as-is** — `InstrumentResult.from_rows(some_dict)` is meaningless. Rule on each explicitly; do **not** paper over it:

- **`graph/attention.py::format_attention_candidate -> dict[str, Any]`** — a formatter for **one** candidate. It is not a collection at all, and it cannot be unwired. → `_NOT_INSTRUMENTS`. (It is flagged only because `dict` is in `_BARE_COLLECTIONS`; that is the detector being coarse, not a finding.)
- **`benchmark_catalog.py::coverage_summary -> dict[str, dict[str, int]]`** — a genuine mapping-shaped *summary*, and it can plausibly be unwired (a summary over zero resolvable benchmarks is not "zero coverage"). It needs a real ruling, and there are exactly two honest options:
  1. **Reshape to rows** (preferred) — return `InstrumentResult[CoverageRow]` where the mapping's key becomes a field on each row. This is an API change; its consumers must be updated. Take this option unless the consumer count makes it a separate project.
  2. **Defer explicitly** — put it in **`_DEFERRED_INSTRUMENTS`**, never `_NOT_INSTRUMENTS`.

  **The distinction is load-bearing, and an earlier draft of this plan got it wrong.** `_NOT_INSTRUMENTS` means *"cannot be unwired"* — filing a known instrument there is a **false statement in the guard's own vocabulary**, and it would let Task 11's empty-`_ALLOWLIST` assertion report the migration complete while the defect is still live. That is this design's exact failure — an instrument reporting a clean result it did not earn — committed by the guard built to prevent it. `_DEFERRED_INSTRUMENTS` exists precisely so "deferred" cannot be spelled "not an instrument": Task 11 asserts it is **empty**, so choosing option 2 **blocks the closeout** until either the helper is migrated or the design's completion criteria are explicitly amended to bless the carve-out. That is the intended friction. Do not route around it.

  Decide with the code in front of you. What you may **not** do is `from_rows(list(summary.items()))` or any similar reshaping smuggled in without updating the consumers — that is a silent API change.

- [ ] **Step 2: Move the non-instruments**

Move those entries from `_ALLOWLIST` to `_NOT_INSTRUMENTS`, each with its justification as a trailing comment:

```python
_NOT_INSTRUMENTS: frozenset[tuple[str, str]] = frozenset(
    {
        # Pure sampling utility over a caller-supplied list. No I/O, no resolution
        # step: an empty return means the caller passed an empty list.
        ("graph/attention.py", "weighted_sample_without_replacement"),
        # ... one justified entry per line
    }
)
```

- [ ] **Step 3: Confirm the guard still passes and the drain list is now real**

Run: `cd science && uv run --frozen pytest tests/test_instrument_boundary.py -v`
Expected: PASS, including `test_sets_are_disjoint`. Every seeded entry now sits in exactly one of three sets, and each set is a **claim**:

| Set | The claim it makes | Task 11 |
|---|---|---|
| `_ALLOWLIST` | "An instrument. Not migrated **yet**." | must be **empty** |
| `_NOT_INSTRUMENTS` | "**Cannot** be unwired." (permanent, justified per entry) | may be non-empty |
| `_DEFERRED_INSTRUMENTS` | "An instrument. **Still broken.** The type cannot express it." | must be **empty** |

`_ALLOWLIST` now contains **only** things that genuinely must migrate — that set, not any number written in this plan, is the work Tasks 3–10 drain.

- [ ] **Step 4: Commit**

```bash
git add science/tests/test_instrument_boundary.py docs/plans/2026-07-11-instrument-triage.md
git commit -m "docs(instruments): triage the boundary seed into instruments vs pure helpers

A pure sampling utility cannot be unwired; wrapping it is ceremony without safety
and dilutes what the guard means. The validate_* family ARE instruments: a check
that returned [] because it could not load the graph has not found zero problems."
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

**Scope note, stated precisely:** the current code re-globs every question once per topic inside `_compute_demand` (O(topics × questions)). The new `_scan_question_topic_refs` is hoisted and runs **once** — but `_compute_demand` is still called per-topic and still re-globs. **This task does not fix the quadratic scan**, and no step below should claim it does. Removing it means deriving per-topic demand from the single scan, which is a worthwhile follow-up but is *behavior-adjacent* and does not belong in a task whose job is the `unwired` precondition. Leave `_compute_demand` alone.

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

### Task 4: `big_picture/validator.py` — delete the counter, migrate the module

**Scope: every `_ALLOWLIST` entry for `big_picture/validator.py`.** That is the counter **and** `validate_synthesis_file` / `validate_rollup_file` (both `-> list[ValidationIssue]`). Read the allowlist; do not work from the function names in this plan.

The two `validate_*` helpers are instruments with real, **verified** `unwired` states — and one of them has a worse bug than a silent empty. They return a bare `list`, so unlike `validate_graph` they carry no `has_failures` channel and migrate cleanly (see *Deferred: the validator payload* in Task 7 for why that distinction matters).

**`validate_synthesis_file` (`:38`) — the unwired state emits confident garbage, not a clean empty.** It checks every `kind:id` reference in the text against `_collect_project_ids(project_root)` (`:74`), which scans `entities/` and `tasks/`. If **neither** directory yields a single ID, `known_ids` is empty — and then the loop at `:44-54` flags **every reference in the file** as `nonexistent_reference`. The check did not run, and instead of returning `[]` it returns a full sheet of false positives. Same disease, opposite symptom: an instrument reporting findings it did not earn. → `unwired`, `code="no_project_ids"`, when `known_ids` is empty.

**`validate_rollup_file` (`:138`) — a silent `or {}` swallow.** Line `:141` is `fm = read_frontmatter(path) or {}`. A rollup whose frontmatter is **missing or unparseable** yields `fm = {}` → `claimed is None` → the orphan-count check is skipped → the function returns `[]`, which the CLI renders as *validated clean*. A rollup that could not be parsed has not passed validation. Two distinct states hide behind that `or {}`:

| Condition | Status |
|---|---|
| `read_frontmatter(path)` returns `None` (absent/unparseable) | `unwired`, `code="frontmatter_unreadable"` |
| Frontmatter parses; no `orphan_question_count` key | `empty`, `code="no_orphan_claim"` — the check ran and there was nothing claimed to contradict |
| Frontmatter parses; count present and matches | `empty` — a TRUE clean bill |
| Count present and mismatched | `ok` — one `orphan_count_mismatch` row |

Delete the `or {}` fallback. It is exactly the "silent fallback" the repo's conventions forbid.

**Files:**
- Modify: `science/src/science_tool/big_picture/validator.py` — `count_research_orphans` (delete, `:116-136`), its caller (`:146`), `validate_synthesis_file`, `validate_rollup_file`
- Modify: `science/tests/test_big_picture_validator.py:190-197`
- Modify: `commands/big-picture.md:206`

Note the internal chain: `validate_rollup_file` **calls** `count_research_orphans` (`:146`). It becomes `len(list_research_orphans(...).rows)` — and since `validate_rollup_file` is itself migrating, make sure its own `unwired` path is distinct from the orphan-count path.

**Interfaces:**
- Consumes: `InstrumentResult` (Task 1).
- Produces:
  - `list_research_orphans(resolved, project_root) -> InstrumentResult[str]` — rows are orphan question IDs, sorted. **`count_research_orphans` no longer exists.**
  - `validate_synthesis_file(path, project_root) -> InstrumentResult[ValidationIssue]`
  - `validate_rollup_file(path, project_root) -> InstrumentResult[ValidationIssue]`
- Consumer: `big_picture/cli.py:68-81` (`validate_cmd`) — the **only** production caller of both validators.

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

And the two validator preconditions — **add these, do not skip them**; they are the reason this task owns the module and not just the counter:

```python
def test_synthesis_validation_is_unwired_when_no_project_ids(tmp_path: Path) -> None:
    """No entities/ and no tasks/ means the reference check has no corpus.

    Without this, known_ids is empty and EVERY reference in the file is reported
    as nonexistent -- a full sheet of false positives from a check that never ran.
    """
    synth = _write(
        tmp_path,
        "h1.md",
        """---
id: "synthesis:h1"
---

## Arc

Work in task:t082 and question:q01 showed a result.
""",
    )
    result = validate_synthesis_file(synth, project_root=tmp_path)

    assert result.status == "unwired"
    assert result.code == "no_project_ids"
    # The point of the ruling: it must NOT invent findings it did not earn.
    assert result.rows == []


def test_rollup_validation_is_unwired_when_frontmatter_unreadable(tmp_path: Path) -> None:
    """`fm = read_frontmatter(path) or {}` rendered an unparseable rollup as clean."""
    rollup = tmp_path / "synthesis.md"
    rollup.write_text("no frontmatter here at all\n", encoding="utf-8")

    result = validate_rollup_file(rollup, project_root=tmp_path)

    assert result.status == "unwired"
    assert result.code == "frontmatter_unreadable"


def test_rollup_with_no_orphan_claim_is_empty_not_unwired(tmp_path: Path) -> None:
    """A parseable rollup that claims no count HAS been checked -- there was
    simply nothing to contradict. That is `empty`, not `unwired`."""
    rollup = _write(tmp_path, "synthesis.md", '---\nid: "synthesis:rollup"\n---\n\nBody.\n')

    result = validate_rollup_file(rollup, project_root=tmp_path)

    assert result.status == "empty"
    assert result.code == "no_orphan_claim"
```

Update the five existing call sites (`:36`, `:55`, `:70`, `:87`, `:111`, `:130`, `:181`) to read `.rows` — e.g. `issues = validate_synthesis_file(synth, project_root=FIXTURE).rows`. That is a mechanical change and expected, not a regression.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science && uv run --frozen pytest tests/test_big_picture_validator.py -v`
Expected: FAIL — `ImportError: cannot import name 'list_research_orphans'`, and the three new precondition tests fail on `AttributeError: 'list' object has no attribute 'status'`.

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

- [ ] **Step 4: Migrate `validate_synthesis_file` (`:38`)**

Change the annotation to `-> InstrumentResult[ValidationIssue]`, and gate the reference
loop on a corpus actually existing:

```python
def validate_synthesis_file(path: Path, project_root: Path) -> InstrumentResult[ValidationIssue]:
    """Return structural issues with a generated synthesis file.

    ``unwired`` when the project yields no IDs at all: the reference check has no
    corpus, and reporting every reference as nonexistent would be a sheet of false
    positives from a check that never ran.
    """
    issues: list[ValidationIssue] = []
    text = path.read_text(encoding="utf-8")

    known_ids = _collect_project_ids(project_root)
    if not known_ids:
        return InstrumentResult.unwired(
            code="no_project_ids",
            reason=(
                f"No entity or task IDs found under {project_root}. Reference "
                "validation cannot run; every reference would be flagged nonexistent."
            ),
        )

    for match in REFERENCE_PATTERN.finditer(text):
        ...  # unchanged

    fm = read_frontmatter(path) or {}
    if fm.get("provenance_coverage") == "thin":
        ...  # unchanged

    return InstrumentResult.from_rows(issues)
```

The `or {}` on the `provenance_coverage` read stays: a synthesis file with no
frontmatter is not *unvalidatable* — the reference check, which is the bulk of this
function, still ran. Only the rollup's `or {}` (Step 5) hides a real failure.

- [ ] **Step 5: Migrate `validate_rollup_file` (`:138`) — delete the silent `or {}`**

```python
def validate_rollup_file(path: Path, project_root: Path) -> InstrumentResult[ValidationIssue]:
    """Return structural issues with a generated rollup (synthesis.md).

    ``unwired`` when the frontmatter cannot be read: a rollup that did not parse has
    not passed validation. It previously returned [] here -- rendered as a clean bill.
    """
    fm = read_frontmatter(path)
    if fm is None:
        return InstrumentResult.unwired(
            code="frontmatter_unreadable",
            reason=f"{path.name} has no readable frontmatter; nothing could be checked.",
        )

    claimed = fm.get("orphan_question_count")
    if claimed is None:
        return InstrumentResult.from_rows(
            [],
            code="no_orphan_claim",
            reason=f"{path.name} claims no orphan_question_count; nothing to reconcile.",
        )

    resolved = resolve_questions(project_root)
    orphans = list_research_orphans(resolved, project_root)
    if orphans.status == "unwired":
        # Propagate: we cannot contradict a claim we could not compute.
        return InstrumentResult.unwired(code=orphans.code, reason=orphans.reason)

    actual = len(orphans.rows)
    issues: list[ValidationIssue] = []
    if int(claimed) != actual:
        issues.append(
            ValidationIssue(
                kind="orphan_count_mismatch",
                message=f"Rollup claims {claimed} orphans but resolver expected {actual}.",
                path=path,
            )
        )
    return InstrumentResult.from_rows(issues)
```

Note the propagation branch: this is the **wrapper-downgrade trap** (Self-Review §7) in
miniature. `len(list_research_orphans(...).rows)` alone would turn an unwired orphan
computation into `actual = 0` and then *report a mismatch against it* — a fabricated
finding. Branch first.

- [ ] **Step 6: Update the CLI consumer (`big_picture/cli.py:68-81`)**

`validate_cmd` is the only production caller. It must surface `unwired` as a **failure
to check**, distinct from both "clean" and "found issues" — today an unwired validator
contributes nothing to `issues` and the command exits 0:

```python
    issues: list[ValidationIssue] = []
    unchecked: list[tuple[Path, str]] = []
    if synthesis_dir.is_dir():
        for path in sorted(synthesis_dir.glob("*.md")):
            fm = read_frontmatter(path) or {}
            if fm.get("report_kind") == "synthesis-rollup":
                result = validate_rollup_file(path, project_root=project_root)
            else:
                result = validate_synthesis_file(path, project_root=project_root)
            if result.status == "unwired":
                unchecked.append((path, result.reason or result.code or "unknown"))
            else:
                issues.extend(result.rows)

    for issue in issues:
        click.echo(f"[{issue.kind}] {issue.path.name}: {issue.message}")
    for path, reason in unchecked:
        click.echo(f"[not-checked] {path.name}: {reason}", err=True)

    if issues or unchecked:
        raise click.exceptions.Exit(code=1)
```

**A file that could not be checked exits non-zero.** Silence here would mean `science
big-picture validate` passing green over a rollup it never read.

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_big_picture_validator.py -v`
Expected: PASS

- [ ] **Step 8: Update the command doc**

In `commands/big-picture.md:206`, replace the `count_research_orphans(...)` reference with:

```markdown
- Compute via `list_research_orphans(resolved, project_root)` from `science_tool.big_picture.validator`. `orphan_question_count` is `len(result.rows)` and `orphan_ids` is `result.rows` — **the same call**, so the count and the ID list cannot disagree. The predicate excludes questions whose resolved aspects are only `[software-development]`. Do not re-derive either value by hand.
```

- [ ] **Step 9: Verify nothing still *references* the deleted function**

A bare `grep count_research_orphans` can never come back clean — it matches the
deliberate-absence test `test_count_research_orphans_is_gone` written in Step 1.
Grep for a **definition, call, or import**, not the bare name:

Run:
```bash
cd science && grep -rnE "(def |import |\.)count_research_orphans|count_research_orphans\(" \
  src/ tests/ ../commands/ ../skills/ ../agents/ | grep -v "test_count_research_orphans_is_gone"
```
Expected: **no matches.**

- [ ] **Step 10: Drain EVERY `big_picture/validator.py` entry, full suite**

Remove **every** `("big_picture/validator.py", ...)` entry from `_ALLOWLIST` — not just
the counter. At the time of writing that is the counter plus `validate_synthesis_file`
and `validate_rollup_file`, but **read the allowlist, not this sentence**:

```bash
cd science && grep -n 'big_picture/validator.py' tests/test_instrument_boundary.py
```

Every line that prints must be gone before you commit. `test_allowlist_has_no_stale_entries`
catches a leftover, and `test_instrument_namespace_returns_instrument_result` catches a
helper you migrated the annotation of but forgot to drain — between them the module is
either fully done or the suite is red. There is no in-between state to ship.

Run: `cd science && uv run --frozen pytest && uv run ruff check && uv run pyright`
Expected: all pass.

- [ ] **Step 11: Commit**

```bash
git add science/src/science_tool/big_picture/validator.py \
        science/src/science_tool/big_picture/cli.py \
        science/tests/test_big_picture_validator.py \
        science/tests/test_instrument_boundary.py \
        commands/big-picture.md
git commit -m "refactor(big-picture): migrate validator.py to InstrumentResult

Replaces count_research_orphans with list_research_orphans: the count and a
hand-derived orphan_ids list disagreed downstream (40 vs 31), and the count is
now len(rows) of the same call, so there is no second definition to drift from.

Both validators gain a real unwired state. validate_synthesis_file with no
project IDs was flagging EVERY reference as nonexistent -- false findings from
a check that never ran. validate_rollup_file swallowed unreadable frontmatter
via 'or {}' and reported a clean bill on a file it never parsed."
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

### Task 6: The materialization lint — NOT BUILT (design amended)

> **This task was attempted, measured, and withdrawn. Do not execute it as written below.**
>
> The defect is real and confirmed: an authored `supersedes:` on a hypothesis is silently
> dropped at load. But the lint cannot be built as a **flat** key vocabulary, and two
> derivations were implemented and measured before that became clear:
>
> - **From the entity loader alone** → flags `provenance_coverage`, `report_kind`,
>   `generated_at`, … on ~40 real entities in `meta/`. Those keys *are* read, just by other
>   modules. A lint that cries wolf gets turned off.
> - **Tree-wide** → legitimizes `supersedes` itself, because `qa_audit/runs.py:47` reads
>   `fm.get("supersedes")` for QA-audit **run** entities. The lint stops flagging its own
>   founding bug.
>
> The key is **live on one kind and dead on another**, so a correct lint needs a per-kind
> authored-key vocabulary — the Kind Descriptor keystone's job, not this design's. The
> design has been amended accordingly: the lint is moved to Follow-on work and struck from
> the acceptance set. **`fb-2026-07-11-017` is open and its defect is live.**
>
> The original task text is kept below for whoever picks this up under Kind Descriptor.

#### (withdrawn) A field that materializes nothing is an error

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
    # API note: iter_entity_markdown(entities_root) yields PLAIN Paths -- it does not
    # yield an object with .frontmatter/.path, and it takes the entities/ root, not
    # the project root. Frontmatter comes from ctx.frontmatter(path). This mirrors
    # origins.py:38-39 exactly; an earlier draft of this plan invented the other API.
    entities_dir = ctx.project_root / "entities"
    for path in iter_entity_markdown(entities_dir):
        fm = ctx.frontmatter(path)
        for field, predicate in _NON_MATERIALIZING.items():
            if field not in fm:
                continue
            yield Result(
                Severity.ERROR,
                path,
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

### Task 7: Bulk migration — every remaining `graph/store/` instrument

**Files:**
- Modify: `science/src/science_tool/graph/store/{summary,queries,inquiry,validation}.py`
- Modify: their CLI consumers and tests.

**Scope: every `_ALLOWLIST` entry whose module starts with `graph/store/`.** Read the
allowlist; do not work from a count in this plan. It includes `query_predicates` and
the `validate_*` family in `validation.py` — Task 5 drained only the two
`diff_graph_inputs*` entries, and everything else under `graph/store/` is this task's.

**Interfaces:**
- Consumes: `InstrumentResult` (Task 1), the triaged allowlist (Task 2b).
- Produces: each migrated helper returns `InstrumentResult[<its existing row type>]`. **Row types are unchanged.**

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

- [ ] **Step 3: Migrate every `graph/store/` allowlist entry**

For each, change the return annotation to `InstrumentResult[...]` and wrap the final `return rows` as `return InstrumentResult.from_rows(rows)`.

**`validate_inquiry` / `validate_inquiry_dataset` migrate and have a real `unwired` state:** an unresolvable `slug` means the check never ran, exactly as an unresolvable `center` does for `query_gaps`. Returning `[]` for a slug that does not exist is "no problems found" about a thing that was never looked at. Give them `code="inquiry_not_found"`.

#### Thin wrappers must propagate the result VERBATIM

Three helpers are thin wrappers that load a dataset and delegate:

```
list_inquiries      -> list_inquiries_dataset
validate_inquiry    -> validate_inquiry_dataset
diff_graph_inputs   -> diff_graph_inputs_dataset      (Task 5)
```

**Return the inner `InstrumentResult` unchanged:**

```python
def list_inquiries(graph_path: Path) -> InstrumentResult[dict[str, str]]:
    dataset = _load_dataset(graph_path)
    return list_inquiries_dataset(dataset)          # <- verbatim
```

**Never** re-wrap: `return InstrumentResult.from_rows(list_inquiries_dataset(ds).rows)` **silently downgrades `unwired` to `empty`** — it throws away the status, the code, and the reason, and hands the caller a clean empty result from an instrument that did not run. That is this design's bug, reintroduced at the wrapper, and it would pass the AST guard (the annotation is right) and every row-count test. Watch for it in review.

#### Deferred: the validator payload (`validate_graph*`, `validate_empirical_run_resolution`)

These three return `tuple[list[...], bool]` and are **deliberately out of scope**. The narrowed tuple detector (Task 2) does not flag them, so they will not appear in the seed and need no carve-out.

The reason is semantic, not convenience. Their `bool` is `has_failures`, computed as `any(row["status"] == "fail" ...)` (`validation.py:187`) — rows carry mixed severities, so **it is not `bool(rows)`**; `validation.py:272` returns non-empty rows with `False`. `InstrumentResult.status` cannot absorb it: for a validator, `ok` means *rows were found*, which means *problems were found* — orthogonal to pass/fail, not a synonym. Forcing them through this type would silently reinterpret a pass/fail signal as a row-count signal, which is a new instance of the very bug this design exists to kill.

They do still have the underlying disease (`validate_graph` catches an exception and returns rows + `True` at `:35`; a graph that fails to load must not read as "clean"). Designing a payload that carries rows **and** `has_failures` **and** an unwired state is real work. It is recorded in the design's *Follow-on work*, not smuggled in here.

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

Remove **every** `graph/store/*` entry from `_ALLOWLIST`. After this task no
`graph/store/` entry may remain — `test_allowlist_has_no_stale_entries` will tell you
if you missed one. (Leave `graph/health.py` and `graph/attention.py` — Tasks 8, 9.)

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
- Modify: `science/src/science_tool/graph/health.py` — **every `_ALLOWLIST` entry for this module.** Read the allowlist; do not work from a count in this plan (an earlier draft said 10; the tree has more, including `list_health_checks` and `check_dataset_anomalies`).
- Modify: their consumers (`science health` CLI) and tests.

**Interfaces:**
- Consumes: `InstrumentResult` (Task 1).
- Produces: **each allowlisted helper in this module** — whatever its name prefix — returns `InstrumentResult[<its existing row type>]`, e.g. `collect_unresolved_refs -> InstrumentResult[UnresolvedRef]`, `list_health_checks -> InstrumentResult[<its row type>]`. **Row types are unchanged.**

**Precondition analysis (do this before writing code).** These are the health instruments, and they are the ones most likely to have a real `unwired` state — a check that scans a directory that does not exist has not "found no problems", it has not run. For **each entry the allowlist names for this module**, ask: *is there an input whose absence makes an empty result meaningless?* A directory that does not exist, a graph layer that is missing, a registry that failed to load — those are `unwired`. A directory that exists and is clean is `empty`.

- [ ] **Step 1: Enumerate the helpers from the ALLOWLIST — not from a name prefix**

```bash
cd science && grep -n 'graph/health.py' tests/test_instrument_boundary.py
```

**That output is the work list.** Do **not** use `grep "^def collect_"` — an earlier draft
of this plan did exactly that, and the `collect_` prefix silently excludes real instruments
in this module such as `list_health_checks` and `check_dataset_anomalies`. This is the same
list-vs-query error the design warns about (Self-Review, "the list-vs-query lesson"), and it
is worth naming twice because it has now been made twice: **a naming convention is not a
boundary.** The allowlist is generated from the code; a prefix is a guess about the code.

For each entry, write one line in a scratch note: helper → precondition (or "none — cannot be unwired"). This is the actual intellectual work of the task; the code that follows is mechanical.

- [ ] **Step 2: Write the failing tests**

For each helper with a real precondition, add a test asserting `status == "unwired"` and a specific `code` when that precondition is absent. For each helper without one, add a test asserting a clean project yields `status == "empty"` (not `unwired`).

Run: `cd science && uv run --frozen pytest tests/ -k health -v`
Expected: FAIL

- [ ] **Step 3: Migrate**

Change each return annotation to `InstrumentResult[...]`; return `InstrumentResult.unwired(code=..., reason=...)` on an absent precondition and `InstrumentResult.from_rows(rows)` otherwise.

- [ ] **Step 4: Update consumers — search for EVERY migrated helper, generated from the allowlist**

Build the pattern from the allowlist entries you enumerated in Step 1, not from a
hand-typed list of four names (an earlier draft hard-coded exactly that, and it missed
the helpers the `collect_` prefix had already dropped):

```bash
cd science
FNS=$(grep 'graph/health.py' tests/test_instrument_boundary.py \
      | sed -E 's/.*, *"([a-zA-Z_]+)".*/\1/' | paste -sd'|')
grep -rnE "\b(${FNS})\b" src/ tests/
```

Every hit outside `health.py` itself is a consumer that must take `.rows` or branch on
`unwired`. The `science health` renderer must surface `unwired` distinctly — this is the command that fb-2026-07-10-021 says currently "spams skip warnings", so an unwired health check must read as a *failure to check*, not a clean bill.

- [ ] **Step 5: Run tests, drain allowlist, full suite**

Remove **every** `graph/health.py` entry from `_ALLOWLIST`. `test_allowlist_has_no_stale_entries` will tell you if you missed one.

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

**This task has two possible shapes. Task 2b decides which one you execute — read its
recorded ruling for `compute_attention_candidates` in `docs/plans/2026-07-11-instrument-triage.md`
BEFORE touching any file.** Everything below is written twice, once per branch, because
pre-deciding it is exactly the mistake this plan keeps catching itself making.

**Files (branch A — `compute_attention_candidates` ruled an INSTRUMENT):**
- Modify: `science/src/science_tool/graph/attention.py` (all three allowlisted helpers)
- Modify: `science/src/science_tool/wander/sampling.py`, `science/src/science_tool/wander/cli.py`
- Modify: `science/tests/test_attention_sampling.py`, `science/tests/test_wander_context.py`

**Files (branch B — ruled `_NOT_INSTRUMENTS`):**
- Modify: `science/src/science_tool/graph/attention.py` (the two `query_*` helpers **only**)
- The `wander` consumers and their tests are **untouched** — that is the whole point of branch B.

**Interfaces:**
- Produces (both branches): `query_attention_sample -> InstrumentResult[dict[str, Any]]`, `query_attention_ranked -> InstrumentResult[dict[str, Any]]`.
- Produces (**branch A only**): `compute_attention_candidates -> InstrumentResult[AttentionCandidate]`. Under branch B it **keeps** its `Sequence[AttentionCandidate]` contract and moves to `_NOT_INSTRUMENTS`.

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

**Task 2b decides whether `compute_attention_candidates` is an instrument. Do not pre-decide it here.** It is the *internal* producer feeding the two user-facing query helpers, and it is consumed by `wander/sampling.py`, `wander/cli.py`, `tests/test_attention_sampling.py`, and `tests/test_wander_context.py` — all expecting a `Sequence[AttentionCandidate]`. Wrapping it breaks every one of them, so the wrapper must **buy** something.

Apply Task 2b's bar: *is there an input whose absence makes an empty return meaningless?*

- **If yes** (e.g. a graph with no freshness layer means the computation did not run): it is an instrument. Define and **test** that precondition, return `unwired`, and do the propagation in Step 2 below.
- **If no** (an empty graph genuinely means no candidates): classify it `_NOT_INSTRUMENTS`, **leave its `Sequence[AttentionCandidate]` contract intact**, and migrate only `query_attention_sample` / `query_attention_ranked`. The wander propagation then largely disappears.

A `from_rows`-only wrapper — `ok`/`empty` with no reachable `unwired` — is the worst of both: it adds **no** safety and buys the whole wander blast radius. If that is where you land, the honest answer is `_NOT_INSTRUMENTS`.

- [ ] **Step 1: Map the consumers before editing anything**

Run: `cd science && grep -rn "compute_attention_candidates\|query_attention_sample\|query_attention_ranked" src/ tests/`

Expected: hits in `graph/attention.py`, `wander/sampling.py`, `wander/cli.py`, `tests/test_attention_sampling.py`, `tests/test_wander_context.py`. These are in the blast radius **only if Task 2b classified `compute_attention_candidates` as an instrument.**

- [ ] **Step 2: Define the propagation rule — ONLY if it is an instrument**

If Task 2b ruled it an instrument, it returns `InstrumentResult[AttentionCandidate]` and its two in-module consumers must **branch, not unwrap blindly**:

```python
def query_attention_sample(...) -> InstrumentResult[dict[str, Any]]:
    candidates = compute_attention_candidates(...)
    if candidates.status == "unwired":
        # Propagate: a sample of an instrument that did not run is not a sample.
        return InstrumentResult.unwired(code=candidates.code or "no_candidates",
                                        reason=candidates.reason)
    rows = _sample(candidates.rows, ...)          # <- .rows, never the result object
    return InstrumentResult.from_rows(rows, code=candidates.code, reason=candidates.reason)
```

The same shape for `query_attention_ranked`. The rule: **`unwired` propagates; the caveat (`code`/`reason`) rides along; sampling and ranking always receive `.rows`.**

Sampling/ranking helpers (`weighted_sample_without_replacement`, `reason_aware_sample_candidates`) keep taking `Sequence[AttentionCandidate]` — they are pure, and Task 2b should have classified them `_NOT_INSTRUMENTS`. **Do not wrap them.**

- [ ] **Step 3: Update the `wander` consumers — BRANCH A ONLY**

**Under branch B, skip this step entirely.** `compute_attention_candidates` still returns
`Sequence[AttentionCandidate]`, so `wander/sampling.py` and `wander/cli.py` compile and
pass unchanged — and *not touching them* is precisely the payoff of that ruling. Do not
"tidy" them into `.rows` anyway; there would be no `.rows` to take.

Under branch A: `wander/sampling.py` and `wander/cli.py` call into these. Pass `.rows` at the boundary, and surface `unwired` in the wander CLI rather than presenting an empty walk as a completed one.

- [ ] **Step 4: Verify the scoring is untouched**

Run: `cd science && git diff src/science_tool/graph/attention.py | grep -E "^[+-].*(weight|days_since|multiplier|factor)"`
Expected: **no output.** Any hit means the scope fence was crossed — revert those lines.

- [ ] **Step 5: Run tests**

Run: `cd science && uv run --frozen pytest -k "attention or wander" -v`
Expected: PASS.

- Branch A: `tests/test_attention_sampling.py` and `tests/test_wander_context.py` need updating to `.rows` — expected, not a regression.
- Branch B: **both test files should pass untouched.** If either needs editing, you have crossed into branch A by accident — stop and re-read the Task 2b ruling.

- [ ] **Step 6: Drain allowlist, full suite, commit**

Remove from `_ALLOWLIST` every `graph/attention.py` entry **that this task migrated**. Under
branch B, `compute_attention_candidates` is not one of them — it belongs in `_NOT_INSTRUMENTS`
(moved there by Task 2b), and the pure helpers stay there too.

```bash
cd science && uv run --frozen pytest && uv run ruff check && uv run pyright
```

Stage the files for **your branch** — under branch B the four `wander`/test paths are not
in the diff at all:

```bash
# Branch A:
git add science/src/science_tool/graph/attention.py \
        science/src/science_tool/wander/sampling.py \
        science/src/science_tool/wander/cli.py \
        science/tests/test_attention_sampling.py \
        science/tests/test_wander_context.py \
        science/tests/test_instrument_boundary.py

# Branch B:
git add science/src/science_tool/graph/attention.py \
        science/tests/test_instrument_boundary.py
```

Commit message — **branch A**:

```
refactor(attention): migrate return shape to InstrumentResult

Return shape only -- but it propagates: wander/sampling and wander/cli consume
these candidates, so unwired now propagates through sampling instead of
presenting an empty walk as a completed one.

The days_since_last_review scoring defect is deliberately NOT fixed here. It is
multiplicative, so the 365 constant is inert -- and the naive repair would make
unstamped entities dominate the ranking. Separate design.
```

Commit message — **branch B**:

```
refactor(attention): migrate the query helpers to InstrumentResult

query_attention_sample and query_attention_ranked are the user-facing surfaces
and gain a status. compute_attention_candidates is NOT an instrument: <the Task 2b
justification, in one line>. It keeps its Sequence contract, so wander is untouched.

The days_since_last_review scoring defect is deliberately NOT fixed here. It is
multiplicative, so the 365 constant is inert -- and the naive repair would make
unstamped entities dominate the ranking. Separate design.
```

---

### Task 10: The catalog modules and `curate/inventory.py`

**Scope: every `_ALLOWLIST` entry for `benchmark_catalog.py` and `datasets_catalog.py`.** Read the allowlist. It is **not** just the two tuple precursors — it also includes `benchmark_sources`, `coverage_summary`, `reconcile_dataset_links`, `format_show`, and `consumers_of`. An earlier draft of this task named only `list_benchmarks` and `list_datasets`, which would have left five helpers stranded and Task 11's empty-allowlist assertion failing.

**Files:**
- Modify: `science/src/science_tool/benchmark_catalog.py`, `datasets_catalog.py`, `curate/inventory.py`
- Modify: **`science/src/science_tool/benchmark_opportunities.py`** — an external consumer of `benchmark_sources`, outside the instrument namespace and easy to miss.
- Modify: `science/src/science_tool/cli.py` (consumes `list_benchmarks`, `list_datasets`)

**Interfaces:**
- Produces: `list_benchmarks -> InstrumentResult[BenchmarkRow]`, `list_datasets -> InstrumentResult[dict]`, `benchmark_sources -> InstrumentResult[BenchmarkSource]`, and per Task 2b's ruling for the rest.

**Triage first.** `format_show -> list[str]` and `consumers_of -> list[str]` are likely pure/total (`_NOT_INSTRUMENTS`); `coverage_summary` is the mapping-shaped case Task 2b must rule on. Apply Task 2b's decisions here — do not re-litigate them.

Three helpers carry the `tuple[list[T], str | None]` precursor (`benchmark_sources`, `list_benchmarks`, `list_datasets`) — an ad-hoc reason channel, invented independently before this type existed. That second element **is** `InstrumentResult.reason`. Converge them.

- [ ] **Step 1: Migrate the catalog allowlist entries**

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

Remove **every** remaining `_ALLOWLIST` entry for `benchmark_catalog.py` and `datasets_catalog.py`. `_ALLOWLIST` should now be **empty** — replace it with `frozenset()`. (`_NOT_INSTRUMENTS` remains populated and is permanent.) If anything is left, a prior task under-drained; find it, do not weaken the guard.

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
- Modify: `science/tests/test_instrument_boundary.py` (assert `_ALLOWLIST` **and** `_DEFERRED_INSTRUMENTS` are both empty)
- Modify: `docs/plans/2026-07-11-instrument-result-convergence-design.md` (Status → Implemented)

- [ ] **Step 1: Make the completion permanent — BOTH sets**

Add to the guard:

```python
def test_migration_is_complete() -> None:
    """The migration is complete. A new entry in EITHER set is a regression.

    Per the convergence design: an allowlist entry the guard would still flag means
    the migration is incomplete -- NOT a carve-out to add.

    _DEFERRED_INSTRUMENTS is asserted empty for the same reason, and it is the more
    important of the two: a deferred entry is a KNOWN instrument that still lies to
    its callers. Draining _ALLOWLIST while _DEFERRED_INSTRUMENTS quietly holds one
    would let this guard certify a completion it did not earn -- which is precisely
    the failure the whole design exists to stop.
    """
    assert _ALLOWLIST == frozenset(), (
        "The instrument-result migration is finished. Do not re-open the allowlist; "
        "migrate the helper instead."
    )
    assert _DEFERRED_INSTRUMENTS == frozenset(), (
        "A known instrument is still unmigrated. This test is the intended blocker: "
        "either migrate it, or amend the design's completion criteria to bless the "
        "carve-out explicitly. Moving it to _NOT_INSTRUMENTS is NOT the fix -- that "
        "set means 'cannot be unwired', which is a false claim about this helper."
    )
```

**If `_DEFERRED_INSTRUMENTS` is non-empty when you reach this step** (the live candidate is `coverage_summary`, ruled on in Task 2b), you have exactly two ways forward and neither is silent:

1. **Migrate it** — reshape to rows, update consumers, drain the entry. Preferred.
2. **Amend the design** — add a *Deferred* subsection to `docs/plans/2026-07-11-instrument-result-convergence-design.md` naming the helper, why the type cannot express it, and what would resolve it; then relax this assertion to permit **exactly** that entry, by name, citing the design section. A bare `assert True` or a quiet deletion of the assertion is a plan violation.

- [ ] **Step 2: Run the full acceptance set from the design**

```bash
cd science && uv run --frozen pytest && uv run ruff check && uv run pyright
cd science/model && uv run --frozen pytest

# Same expression as Task 4 Step 6 -- a BARE grep for the name can never come back
# clean, because it matches the deliberate-absence test.
cd science && grep -rnE "(def |import |\.)count_research_orphans|count_research_orphans\(" \
  src/ tests/ ../commands/ ../skills/ ../agents/ | grep -v "test_count_research_orphans_is_gone"
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

**Spec coverage.** Design §1 (the type + enforced invariant) → Task 1. §1 renderer contract → Task 3 Step 5. §2 structural query → Task 2 (`INSTRUMENT_MODULES`, imported by the guard so the two cannot drift). §2 four-state precondition → Task 3. §2 partial-resolution caveat channel → Task 1 (`ok` may carry `reason`) + Task 3. §2 scalar counters prohibited → Task 4. §2 attention out-of-scope → Task 9's scope fence. §2 tuple precursors → Task 10. §3 guard + additive ratchet + known gaps → Task 2. §4 walk-side (graph diff, envelope, v1-as-unwired) → Task 5. §4 authoring-side (`supersedes:` lint) → **Task 6, WITHDRAWN** — needs a per-kind key vocabulary; the design was amended to move it to Follow-on work and strike it from the acceptance set, and `fb-2026-07-11-017` remains open with its defect live. Bulk namespace → Tasks 7–10. Acceptance criteria → Task 11 Step 2 (minus the struck `supersedes:` criterion).

**Task scope is a MODULE, never a function list.** Every migration task (4, 5, 7, 8, 9, 10) owns *every `_ALLOWLIST` entry for its module*. Two separate review rounds found helpers stranded because a task named specific functions instead: first `query_predicates`, then `validate_synthesis_file`, `validate_rollup_file`, `benchmark_sources`, `coverage_summary`, `reconcile_dataset_links`, `format_show`, `consumers_of`. The failure mode is identical to the list-vs-query one below — an enumeration in prose drifts from the code. **The allowlist is the work order.** Task 11's empty-allowlist assertion is the backstop that catches an under-drained module, but it catches it *late*; owning the module up front catches it early.

**The list-vs-query lesson, learned the hard way.** The first draft of this plan
hand-transcribed the guard's allowlist — 24 entries, against a tree that actually has
49 — while the design doc it implements says, in as many words, *"Do not migrate from
this list. Regenerate the set with that structural query at implementation time."*
The transcription omitted whole helpers (`list_health_checks`, `query_predicates`,
`query_coverage`, `query_uncertainty`, the entire `validate_*` family), which would
have let the allowlist drain to empty while real violations remained — the guard
reporting "done" without having checked. **That is the very failure this design
exists to stop, committed inside the plan to fix it.** Task 2 Step 2 now *generates*
the seed from the guard's own predicate, and no task quotes a count.

**APIs verified against the tree** (a first draft of this plan invented all five;
they are corrected above and listed so a reader can re-check them cheaply):

- `iter_entity_markdown(entities_root)` yields **plain `Path` objects** and takes the
  `entities/` root — not the project root, and not an object with `.frontmatter`/`.path`.
  Frontmatter comes from `ctx.frontmatter(path)`. Mirror `origins.py:38-39`.

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

1. **Preconditions are not pre-written, by design.** Neither Task 2b's instrument/pure-helper triage nor Task 8's per-helper preconditions are decided in this plan. Determining them requires reading each body, and the honest answer differs per helper. Those two tasks make the judgment the explicit first deliverable. This is where the plan hands real thinking to the implementer rather than pre-deciding it badly — which is exactly what a hand-transcribed list did in the first draft.

2. **The renderer contract cannot be unit-tested.** `commands/big-picture.md` is prose executed by an LLM orchestrator. Task 3 Step 5 fixes the instruction, but nothing enforces that the orchestrator obeys it. The Python guarantees the *data* is honest; only review guarantees the *prose* is.

3. **Task 5's blast radius is real.** The first graph rebuild in any consuming project stamps every entity file as `new_file` once (~2,600 in MM30). This is expected, not a bug — but it will look alarming, and any downstream project pinning a `graph.trig` snapshot in a test will need it regenerated.

4. **Two feedback items in `INSTRUMENT_MODULES` are deliberately NOT fixed here** — `curate/inventory.py`'s payload divergence (fb-2026-07-10-017) and the attention scoring model (fb-2026-07-10-023). They are in the namespace so the guard covers their *shape*; their *behavior* belongs to other specs.

5. **Task 9 propagates further than "attention".** `compute_attention_candidates` feeds `wander/sampling.py` and `wander/cli.py`. Wrapping its return breaks the `wander` command, so Task 9 owns those consumers and their tests. The scope fence is on the *scoring model*, not on the call graph — those are different things and conflating them would strand `wander` broken.

6. **`InstrumentResult` cannot express two shapes in the namespace.** It is row-shaped
   (`rows: list[RowT]`), so it cannot carry (a) a **mapping** — `coverage_summary ->
   dict[str, dict[str, int]]`, ruled on in Task 2b — or (b) a **second semantic
   channel** — the `validate_graph*` family's `has_failures`, deferred in Task 7.
   Both are recorded, neither is smuggled. The type's applicability has a boundary and
   this plan states where it is.

7. **The wrapper-downgrade trap.** `list_inquiries`, `validate_inquiry`, and
   `diff_graph_inputs` are thin wrappers over `*_dataset` twins. Re-wrapping
   (`from_rows(inner(...).rows)`) instead of returning the inner result verbatim
   silently downgrades `unwired` to `empty` — and it would pass the AST guard *and*
   every row-count test, because the annotation is correct and the rows match. It is
   the design's own bug, reachable through the migration meant to fix it. Task 7 calls
   it out; **review for it explicitly.**

8. **The quadratic scan in `compute_topic_gaps` is NOT fixed.** `_compute_demand` still re-globs every question once per topic. Task 3 hoists a separate single-pass scan for the precondition and leaves the existing demand loop alone. A first draft of this plan claimed the task removed the quadratic scan; it does not, and the claim has been withdrawn rather than the scope enlarged.

9. **"Deferred" cannot be spelled "not an instrument."** An earlier draft let Task 2b park
   `coverage_summary` in `_NOT_INSTRUMENTS` with a comment saying it was deferred. But that
   set's entries are *claims* — "this helper cannot be unwired" — so filing a known instrument
   there is a **false statement in the guard's own vocabulary**, and it would let Task 11's
   empty-`_ALLOWLIST` assertion certify the migration complete while the defect stayed live.
   The guard would have reported a clean result it did not earn: **this design's exact bug,
   committed by the guard built to prevent it** — the same shape as the wrapper-downgrade trap
   (§7) and the transcribed allowlist. Hence a third set, `_DEFERRED_INSTRUMENTS`, which Task 11
   asserts is **empty**: a deferral now *blocks the closeout* until it is paid off or the design's
   completion criteria are explicitly amended. Three sets, three distinct claims, no silent
   third state. `test_sets_are_disjoint` keeps them from being blurred.

10. **A naming convention is not a boundary.** Task 8 owned its whole module in the header but
    then enumerated `def collect_` in its steps — which silently drops `list_health_checks` and
    `check_dataset_anomalies`. That is the list-vs-query error above in miniature, made *after*
    the lesson was written down, inside the very task the lesson was written for. Every
    enumeration step in every migration task now greps `_ALLOWLIST` for its module. If you find
    yourself typing a function name into a `grep` while executing this plan, stop: **the
    allowlist is the work order**, and anything else is a guess about the code rather than a
    query against it.

11. **Task 9 has two shapes and the plan does not pick one.** Whether
    `compute_attention_candidates` is an instrument decides whether `wander/` is in the blast
    radius at all. Task 2b rules; Task 9 is written as branch A / branch B throughout — files,
    steps, tests, staged paths, and commit message. An earlier draft delegated the *decision*
    while its metadata quietly assumed the *outcome*, which is a decision made by accident.

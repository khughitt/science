# S2 Adaptive Rotation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic, stateless `science entity rotation` command that ranks a project's reviewable corpus least-recently-reviewed first and prints the adaptive per-sweep budget `n(N)` as the work-list.

**Architecture:** A pure-logic budget function plus a disk-reading selection core in the existing `science_tool/curate/` package (`rotation.py`), composed by `select_rotation`, surfaced by a thin `entity rotation` CLI command in `entities_cli.py`, and wired into `/science:curate` as the coverage floor. The corpus is exactly `entity review`'s resolution domain via `load_markdown_entities`; ordering is a total order on `(last_reviewed, created, id)`; a best-effort graph read enriches **epistemic-scoped** rows with freshness (correspondence rows never carry it). No graph writes, no git.

**Tech Stack:** Python ≥3.11, Click, rdflib, pytest. Package `science/` (`cd science` before any `uv run`).

## Global Constraints

- Command is `science entity rotation`; core lives in `science_tool/curate/rotation.py` (the **existing** `curate` package — do **not** create a `curation/` package).
- **Stateless.** Reads entity frontmatter via `load_markdown_entities(project_root)`. No durable state, no sweep-id, no git-history reads, no file writes.
- **Budget:** `n(0)=0`; `n(N)=N` for `1 ≤ N ≤ N_FULL`; else `min(N, max(1, ceil(ROTATION_B·ln(N) − ROTATION_A)))`. A **negative** `pool_size` is a caller bug — raise `ValueError`, never return `0`. Constants: `ROTATION_A = 12.57`, `ROTATION_B = 11.53`, `N_FULL = 25`. Verified anchors: `n(25)=25`, `n(26)=25`, `n(100)=41`, `n(389)=57`.
- **Order:** ascending `(last_reviewed or DATE_MIN, created or DATE_MIN, id)` where `DATE_MIN = date.min`; never-reviewed and missing-`created` sort first. Total order.
- **Corpus eligibility (all must hold):** returned by `load_markdown_entities` (registered policy homes routed through the archived-excluding canonical scanner, so `_archive/` files are never eligible); `curation_scope_for_kind(kind) != CurationScope.NONE`; `status` not in `CLOSED_LIFECYCLE_STATUSES`. The resolved `CurationScope` is preserved on each row (needed by the freshness scope guard).
- **Date coercion (canonical only):** accept a YAML `date` **object** or a canonical `YYYY-MM-DD` **string** for which `date.fromisoformat(value).isoformat() == value` (round-trip). Reject a `datetime`, and reject noncanonical strings that `date.fromisoformat` happens to accept (`"20260718"`, `"2026-W29-6"`). Missing → `None`; malformed/noncanonical → raise `RotationError` naming entity id, **path**, and field. Never silently coerce a malformed value to `None`.
- **Graph enrichment (best-effort):** single payload-level `meta.graph_source` with first-match precedence `absent → invalid → stale → current`, reusing `graph_is_stale`. Only the file-existence check may raise `absent`; **every** step after it (parse, staleness, triple extraction) is wrapped so that any exception yields `("invalid", {})`. Per-row `freshness` populated **only** when `graph_source == "current"` **and** the row's `scope is CurationScope.EPISTEMIC`, else `null`; correspondence rows are always `null`.
- **Curation wiring:** `/science:curate` uses `science entity rotation` as its coverage-*floor* reading set (the least-recently-reviewed entities are always read *this* sweep), with the weighted attention sample retained as enrichment/alarm input. Rotation selects but never reviews: advancing state requires an `science entity review <ref> --note ...` stamp per reviewed row, and under `--dry-run`/`--no-write` state does not advance. The command doc and user guide must reflect this.
- **Output:** via `emit_query_rows`; payload `{"format":"json","meta":{...},"rows":[...]}`. Row keys `id`, `last_reviewed`, `age_days`, `rank`, `selected`, `freshness`. Meta keys `pool_size`, `budget`, `displayed`, `coverage_rounds`, `graph_source`. `coverage_rounds = 0` when `N = 0`. Dynamic table title states `budget of pool_size` plus a coverage clause omitted when `coverage_rounds == 0`. Null dates render `never` in the table; JSON keeps raw `null`.
- **No `--with-drift` in v1.**
- Project rules: composition over inheritance; explicit over defensive; fail early; no AI-attribution trailers on commits; **never `git add` `science/uv.lock`** (it drifts on `uv run` and must stay out of every commit).
- Run tests from `science/`: `cd science && uv run --frozen pytest <path> -v`.

---

### Task 1: Budget formula

**Files:**
- Create: `science/src/science_tool/curate/rotation.py`
- Test: `science/tests/test_curate_rotation_budget.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `ROTATION_A: float`, `ROTATION_B: float`, `N_FULL: int`, `DATE_MIN: date`, and `rotation_budget(pool_size: int) -> int`.

- [ ] **Step 1: Write the failing test**

Create `science/tests/test_curate_rotation_budget.py`:

```python
"""Budget-formula boundary tests for adaptive rotation."""

from __future__ import annotations

import pytest

from science_tool.curate.rotation import rotation_budget


@pytest.mark.parametrize(
    ("pool_size", "expected"),
    [
        (0, 0),
        (1, 1),
        (25, 25),   # N_FULL: full read
        (26, 25),   # first tapered value, < 26
        (100, 41),
        (389, 57),  # calibration anchor; ceil(389/57) == 7 sweeps
    ],
)
def test_rotation_budget_anchors(pool_size: int, expected: int) -> None:
    assert rotation_budget(pool_size) == expected


def test_rotation_budget_never_exceeds_pool() -> None:
    for n in range(0, 400):
        assert 0 <= rotation_budget(n) <= n or n == 0


def test_rotation_budget_monotone_nondecreasing() -> None:
    values = [rotation_budget(n) for n in range(1, 400)]
    assert all(b <= a for b, a in zip(values, values[1:]))


def test_rotation_budget_negative_raises() -> None:
    with pytest.raises(ValueError):
        rotation_budget(-5)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_curate_rotation_budget.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'science_tool.curate.rotation'`.

- [ ] **Step 3: Write minimal implementation**

Create `science/src/science_tool/curate/rotation.py`:

```python
"""Adaptive rotation: rank a project's reviewable corpus least-recently-reviewed
first and compute this sweep's adaptive budget. Stateless and read-only."""

from __future__ import annotations

import math
from datetime import date

ROTATION_A = 12.57
ROTATION_B = 11.53
N_FULL = 25

DATE_MIN = date.min


def rotation_budget(pool_size: int) -> int:
    """Per-sweep budget n(N). Full-read up to N_FULL, then a sublinear taper,
    clamped to [1, pool_size]; 0 for an empty corpus."""
    if pool_size < 0:
        raise ValueError(f"pool_size must be non-negative, got {pool_size}")
    if pool_size <= N_FULL:
        return pool_size  # covers 0..N_FULL, so n(0)=0
    raw = math.ceil(ROTATION_B * math.log(pool_size) - ROTATION_A)
    return min(pool_size, max(1, raw))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science && uv run --frozen pytest tests/test_curate_rotation_budget.py -v`
Expected: PASS (4 tests / 6 parametrized cases).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/curate/rotation.py science/tests/test_curate_rotation_budget.py
git commit -m "feat(curate): adaptive rotation budget formula"
```

---

### Task 2: Date coercion + eligible corpus

**Files:**
- Modify: `science/src/science_tool/curate/rotation.py`
- Test: `science/tests/test_curate_rotation_corpus.py`

**Interfaces:**
- Consumes: `DATE_MIN` (Task 1).
- Produces: `class RotationError(Exception)`; `@dataclass(frozen=True) class EligibleEntity` with fields `id: str`, `kind: str`, `scope: CurationScope`, `last_reviewed: date | None`, `created: date | None`; and `eligible_corpus(project_root: Path) -> list[EligibleEntity]`. Also re-exports `CurationScope` (imported here) for Task 4's freshness scope guard.

- [ ] **Step 1: Write the failing test**

Create `science/tests/test_curate_rotation_corpus.py`:

```python
"""Corpus-eligibility and date-coercion tests for adaptive rotation."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import pytest
from _fixtures.entity_helpers import write_markdown_entity

from science_tool.curate.rotation import RotationError, eligible_corpus


def _make_project(tmp_path: Path, files: list[tuple[str, dict[str, object]]]) -> Path:
    root = tmp_path / "proj"
    (root / "entities").mkdir(parents=True)
    (root / "science.yaml").write_text("name: demo\nknowledge_profiles:\n  local: core\n", encoding="utf-8")
    for rel, frontmatter in files:
        write_markdown_entity(root, rel, frontmatter)
    return root


def test_eligible_includes_plan_excludes_dataset(tmp_path: Path) -> None:
    root = _make_project(
        tmp_path,
        [
            ("entities/plans/0001.md", {"id": "plan:0001", "kind": "plan", "title": "P", "status": "active"}),
            ("entities/datasets/d1.md", {"id": "dataset:d1", "kind": "dataset", "title": "D", "status": "active"}),
        ],
    )
    ids = {e.id for e in eligible_corpus(root)}
    assert ids == {"plan:0001"}  # dataset is curation_scope none


def test_eligible_excludes_closed_lifecycle_statuses(tmp_path: Path) -> None:
    files = [
        (f"entities/plans/{i}.md", {"id": f"plan:{i}", "kind": "plan", "title": "P", "status": s})
        for i, s in enumerate(["complete", "superseded", "retired", "archived", "abandoned", "deprecated", "active"])
    ]
    root = _make_project(tmp_path, files)
    ids = {e.id for e in eligible_corpus(root)}
    assert ids == {"plan:6"}  # only the active plan survives


def test_eligible_excludes_unregistered_directory(tmp_path: Path) -> None:
    root = _make_project(
        tmp_path,
        [("entities/plans/0001.md", {"id": "plan:0001", "kind": "plan", "title": "P", "status": "active"})],
    )
    # A markdown file under a directory that is not a registered policy home.
    write_markdown_entity(root, "entities/random/x.md", {"id": "plan:x", "kind": "plan", "title": "X", "status": "active"})
    ids = {e.id for e in eligible_corpus(root)}
    assert ids == {"plan:0001"}


def test_eligible_excludes_archive(tmp_path: Path) -> None:
    root = _make_project(
        tmp_path,
        [("entities/plans/0001.md", {"id": "plan:0001", "kind": "plan", "title": "P", "status": "active"})],
    )
    # An archived plan under the reserved _archive/ subtree must never be eligible.
    write_markdown_entity(
        root,
        "entities/plans/_archive/old.md",
        {"id": "plan:old", "kind": "plan", "title": "Old", "status": "active"},
    )
    ids = {e.id for e in eligible_corpus(root)}
    assert ids == {"plan:0001"}


def test_eligible_reads_dates(tmp_path: Path) -> None:
    root = _make_project(
        tmp_path,
        [
            (
                "entities/plans/0001.md",
                {
                    "id": "plan:0001",
                    "kind": "plan",
                    "title": "P",
                    "status": "active",
                    "created": "2026-01-02",
                    "review_state": {"last_reviewed": "2026-05-06"},
                },
            )
        ],
    )
    (entity,) = eligible_corpus(root)
    assert entity.created == date(2026, 1, 2)
    assert entity.last_reviewed == date(2026, 5, 6)


def test_eligible_accepts_yaml_date_object(tmp_path: Path) -> None:
    # An unquoted YAML date deserializes to a Python date object, not a string.
    root = _make_project(
        tmp_path,
        [
            (
                "entities/plans/0001.md",
                {"id": "plan:0001", "kind": "plan", "title": "P", "status": "active", "created": date(2026, 3, 4)},
            )
        ],
    )
    (entity,) = eligible_corpus(root)
    assert entity.created == date(2026, 3, 4)


def test_eligible_rejects_datetime(tmp_path: Path) -> None:
    # A YAML timestamp deserializes to a datetime; the date-only contract rejects it.
    root = _make_project(
        tmp_path,
        [
            (
                "entities/plans/0001.md",
                {
                    "id": "plan:0001",
                    "kind": "plan",
                    "title": "P",
                    "status": "active",
                    "created": datetime(2026, 3, 4, 10, 0, 0),
                },
            )
        ],
    )
    with pytest.raises(RotationError) as excinfo:
        eligible_corpus(root)
    assert "plan:0001" in str(excinfo.value)


@pytest.mark.parametrize("bad", ["20260718", "2026-W29-6", "2026-7-8"])
def test_eligible_rejects_noncanonical_date_strings(tmp_path: Path, bad: str) -> None:
    root = _make_project(
        tmp_path,
        [
            (
                "entities/plans/0001.md",
                {"id": "plan:0001", "kind": "plan", "title": "P", "status": "active", "created": bad},
            )
        ],
    )
    with pytest.raises(RotationError) as excinfo:
        eligible_corpus(root)
    assert "plan:0001" in str(excinfo.value)


def test_eligible_missing_dates_are_none(tmp_path: Path) -> None:
    root = _make_project(
        tmp_path,
        [("entities/plans/0001.md", {"id": "plan:0001", "kind": "plan", "title": "P", "status": "active"})],
    )
    (entity,) = eligible_corpus(root)
    assert entity.created is None
    assert entity.last_reviewed is None


def test_eligible_malformed_date_raises_with_context(tmp_path: Path) -> None:
    root = _make_project(
        tmp_path,
        [
            (
                "entities/plans/0001.md",
                {"id": "plan:0001", "kind": "plan", "title": "P", "status": "active", "created": "not-a-date"},
            )
        ],
    )
    with pytest.raises(RotationError) as excinfo:
        eligible_corpus(root)
    message = str(excinfo.value)
    # All three context fields: entity id, path, and field name.
    assert "plan:0001" in message
    assert "created" in message
    assert "0001.md" in message  # path fragment
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_curate_rotation_corpus.py -v`
Expected: FAIL — `ImportError: cannot import name 'RotationError'` / `'eligible_corpus'`.

- [ ] **Step 3: Write minimal implementation**

Edit `science/src/science_tool/curate/rotation.py`. Replace the import block and append the new code. The full file after this step:

```python
"""Adaptive rotation: rank a project's reviewable corpus least-recently-reviewed
first and compute this sweep's adaptive budget. Stateless and read-only."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from science_model.identity import CurationScope

from science_tool.entities import CLOSED_LIFECYCLE_STATUSES, load_markdown_entities
from science_tool.graph.sources import registry_for_project

ROTATION_A = 12.57
ROTATION_B = 11.53
N_FULL = 25

DATE_MIN = date.min


class RotationError(Exception):
    """A rotation input could not be interpreted (e.g. a malformed date)."""


@dataclass(frozen=True)
class EligibleEntity:
    id: str
    kind: str
    scope: CurationScope
    last_reviewed: date | None
    created: date | None


def rotation_budget(pool_size: int) -> int:
    """Per-sweep budget n(N). Full-read up to N_FULL, then a sublinear taper,
    clamped to [1, pool_size]; 0 for an empty corpus."""
    if pool_size < 0:
        raise ValueError(f"pool_size must be non-negative, got {pool_size}")
    if pool_size <= N_FULL:
        return pool_size  # covers 0..N_FULL, so n(0)=0
    raw = math.ceil(ROTATION_B * math.log(pool_size) - ROTATION_A)
    return min(pool_size, max(1, raw))


def _coerce_date(value: object, *, entity_id: str, path: Path, field: str) -> date | None:
    """Accept only a YAML date object or a canonical YYYY-MM-DD string. A datetime,
    or a noncanonical string that date.fromisoformat happens to accept (basic
    "20260718", week "2026-W29-6"), fails early with entity/path/field context."""
    if value is None:
        return None
    if isinstance(value, date):
        # datetime is a subclass of date; reject it explicitly (fail early).
        if type(value) is not date:
            raise RotationError(
                f"{entity_id} ({path}): field {field!r} must be a date, not a datetime: {value!r}"
            )
        return value
    if isinstance(value, str):
        try:
            parsed = date.fromisoformat(value)
        except ValueError as exc:
            raise RotationError(
                f"{entity_id} ({path}): field {field!r} is not a valid YYYY-MM-DD date: {value!r}"
            ) from exc
        if parsed.isoformat() != value:
            raise RotationError(
                f"{entity_id} ({path}): field {field!r} must be canonical YYYY-MM-DD, got {value!r}"
            )
        return parsed
    raise RotationError(
        f"{entity_id} ({path}): field {field!r} must be a date or YYYY-MM-DD string, got {type(value).__name__}"
    )


def eligible_corpus(project_root: Path) -> list[EligibleEntity]:
    """Every locally reviewable, source-authored entity: the load_markdown_entities
    domain, minus none-scoped kinds and terminal-lifecycle statuses."""
    registry = registry_for_project(project_root)
    corpus: list[EligibleEntity] = []
    for record in load_markdown_entities(project_root):
        kind = record["kind"]
        scope = registry.curation_scope_for_kind(kind)
        if scope is CurationScope.NONE:
            continue
        frontmatter = record["frontmatter"]
        status = frontmatter.get("status")
        if isinstance(status, str) and status in CLOSED_LIFECYCLE_STATUSES:
            continue
        entity_id = record["id"]
        path = record["path"]
        review_state = frontmatter.get("review_state")
        last_reviewed_raw = review_state.get("last_reviewed") if isinstance(review_state, dict) else None
        corpus.append(
            EligibleEntity(
                id=entity_id,
                kind=kind,
                scope=scope,
                last_reviewed=_coerce_date(
                    last_reviewed_raw, entity_id=entity_id, path=path, field="review_state.last_reviewed"
                ),
                created=_coerce_date(frontmatter.get("created"), entity_id=entity_id, path=path, field="created"),
            )
        )
    return corpus
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science && uv run --frozen pytest tests/test_curate_rotation_corpus.py -v`
Expected: PASS (10 test functions / 12 cases, counting the 3 parametrized noncanonical-string cases).

- [ ] **Step 5: Run ruff + pyright on the module**

Run: `cd science && uv run ruff check src/science_tool/curate/rotation.py && uv run pyright src/science_tool/curate/rotation.py`
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/curate/rotation.py science/tests/test_curate_rotation_corpus.py
git commit -m "feat(curate): rotation corpus eligibility and date coercion"
```

---

### Task 3: Graph freshness enrichment reader

**Files:**
- Modify: `science/src/science_tool/curate/rotation.py`
- Test: `science/tests/test_curate_rotation_freshness.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `graph_freshness(project_root: Path) -> tuple[str, dict[str, str]]` returning `(graph_source, {canonical_id: freshness_state})`, where `graph_source` is one of `"absent" | "invalid" | "stale" | "current"` and the map is non-empty only when `graph_source == "current"`.

- [ ] **Step 1: Write the failing test**

Create `science/tests/test_curate_rotation_freshness.py`:

```python
"""graph_source precedence tests for adaptive rotation enrichment."""

from __future__ import annotations

import os
from pathlib import Path
from textwrap import dedent

from science_tool.curate.rotation import graph_freshness
from science_tool.graph.materialize import materialize_graph


def _project_with_hypothesis_and_task(tmp_path: Path) -> Path:
    root = tmp_path / "demo"
    (root / "entities" / "hypotheses").mkdir(parents=True)
    (root / "entities" / "tasks").mkdir(parents=True)
    (root / "science.yaml").write_text("name: demo\nknowledge_profiles:\n  local: core\n", encoding="utf-8")
    (root / "entities" / "hypotheses" / "h1.md").write_text(
        dedent(
            """
            ---
            id: "hypothesis:h1"
            kind: "hypothesis"
            title: "Demo"
            created: "2026-04-01"
            updated: "2026-04-01"
            ---
            Body.
            """
        ).lstrip(),
        encoding="utf-8",
    )
    (root / "entities" / "tasks" / "t1.md").write_text(
        dedent(
            """
            ---
            id: "task:t1"
            kind: "task"
            title: "Demo task"
            status: "active"
            created: "2026-05-01"
            updated: "2026-05-01"
            related: ["hypothesis:h1"]
            ---
            Body.
            """
        ).lstrip(),
        encoding="utf-8",
    )
    return root


def test_graph_source_absent(tmp_path: Path) -> None:
    root = _project_with_hypothesis_and_task(tmp_path)  # no materialize
    source, states = graph_freshness(root)
    assert source == "absent"
    assert states == {}


def test_graph_source_invalid(tmp_path: Path) -> None:
    root = _project_with_hypothesis_and_task(tmp_path)
    graph_path = root / "knowledge" / "graph.trig"
    graph_path.parent.mkdir(parents=True, exist_ok=True)
    graph_path.write_text("this is not valid trig {{{", encoding="utf-8")
    source, states = graph_freshness(root)
    assert source == "invalid"
    assert states == {}


def test_graph_source_stale(tmp_path: Path) -> None:
    root = _project_with_hypothesis_and_task(tmp_path)
    materialize_graph(root)
    graph_path = root / "knowledge" / "graph.trig"
    os.utime(graph_path, (1000, 1000))  # force the graph older than every source
    source, states = graph_freshness(root)
    assert source == "stale"
    assert states == {}


def test_graph_source_current_yields_states(tmp_path: Path) -> None:
    root = _project_with_hypothesis_and_task(tmp_path)
    materialize_graph(root)
    graph_path = root / "knowledge" / "graph.trig"
    os.utime(graph_path, (2_000_000_000, 2_000_000_000))  # force the graph newer than every source
    source, states = graph_freshness(root)
    assert source == "current"
    assert states.get("hypothesis:h1") == "needs-review"


def test_graph_source_invalid_on_staleness_failure(tmp_path: Path, monkeypatch) -> None:
    """A parseable graph whose staleness check raises degrades to invalid, not a crash."""
    root = _project_with_hypothesis_and_task(tmp_path)
    materialize_graph(root)

    def _boom(*_args: object, **_kwargs: object) -> bool:
        raise OSError("simulated read failure")

    # Patch the name as bound inside the rotation module (best-effort must catch this).
    monkeypatch.setattr("science_tool.curate.rotation.graph_is_stale", _boom)
    source, states = graph_freshness(root)
    assert source == "invalid"
    assert states == {}


def test_graph_source_invalid_on_probe_failure(tmp_path: Path, monkeypatch) -> None:
    """Even the existence probe is best-effort: if Path.exists raises, degrade to invalid."""
    root = _project_with_hypothesis_and_task(tmp_path)  # no materialize; probe raises before parse

    def _boom(_self: Path) -> bool:
        raise OSError("simulated stat failure")

    monkeypatch.setattr(Path, "exists", _boom)
    source, states = graph_freshness(root)
    assert source == "invalid"
    assert states == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_curate_rotation_freshness.py -v`
Expected: FAIL — `ImportError: cannot import name 'graph_freshness'`.

- [ ] **Step 3: Write minimal implementation**

Edit `science/src/science_tool/curate/rotation.py`. Add these imports to the existing import block (below the `registry_for_project` import):

```python
from rdflib import Dataset

from science_tool.entities import graph_is_stale
from science_tool.graph.store import (
    DEFAULT_GRAPH_PATH,
    PROJECT_NS,
    SCI_NS,
    canonical_id_from_entity_uri,
)
```

Then append this function to the end of the file:

```python
def graph_freshness(project_root: Path) -> tuple[str, dict[str, str]]:
    """Best-effort read of freshness states from the materialized graph.

    Returns (graph_source, states). graph_source has first-match precedence
    absent -> invalid -> stale -> current. states maps canonical entity id to its
    freshnessState literal, and is non-empty only when graph_source == "current".

    Every step is best-effort: a successful `exists()` returning False yields
    "absent", but if ANY operation raises — including the existence probe itself,
    the parse, the staleness check, or triple extraction — the result degrades to
    ("invalid", {}) rather than blocking selection. A stale graph is a normal
    result, not a failure, so it returns before the extraction block.
    """
    graph_path = project_root / DEFAULT_GRAPH_PATH
    try:
        if not graph_path.exists():
            return "absent", {}
        dataset = Dataset()
        dataset.parse(graph_path, format="trig")
        if graph_is_stale(project_root, graph_path):
            return "stale", {}
        knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
        states: dict[str, str] = {}
        for subject, _, obj in knowledge.triples((None, SCI_NS.freshnessState, None)):
            canonical_id = canonical_id_from_entity_uri(str(subject))
            if canonical_id is not None:
                states[canonical_id] = str(obj)
        return "current", states
    except Exception:
        return "invalid", {}
```

Note: the broad `except Exception` is intentional — any parse/staleness/read failure means the graph cannot be trusted, which is exactly the `"invalid"` verdict. Ruff's default rule set does not flag it (BLE001 is not enabled; see `entities.py:932` for the same pattern).

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science && uv run --frozen pytest tests/test_curate_rotation_freshness.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Run ruff + pyright**

Run: `cd science && uv run ruff check src/science_tool/curate/rotation.py && uv run pyright src/science_tool/curate/rotation.py`
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/curate/rotation.py science/tests/test_curate_rotation_freshness.py
git commit -m "feat(curate): rotation graph-freshness enrichment reader"
```

---

### Task 4: select_rotation core

**Files:**
- Modify: `science/src/science_tool/curate/rotation.py`
- Test: `science/tests/test_curate_rotation_select.py`

**Interfaces:**
- Consumes: `rotation_budget`, `eligible_corpus`, `EligibleEntity` (with `.scope`), `CurationScope`, `DATE_MIN` (Tasks 1-2, all module-level in `rotation.py`); `graph_freshness` (Task 3).
- Produces: `@dataclass(frozen=True) class RotationResult` with fields `rows: list[dict]`, `pool_size: int`, `budget: int`, `coverage_rounds: int`, `graph_source: str`; and `select_rotation(project_root: Path, *, today: date) -> RotationResult`. Each row dict has keys `id: str`, `last_reviewed: str | None` (ISO), `age_days: int | None`, `rank: int` (1-based), `selected: bool`, `freshness: str | None`. `rows` is the full ranked queue (length `pool_size`).

- [ ] **Step 1: Write the failing test**

Create `science/tests/test_curate_rotation_select.py`:

```python
"""select_rotation ordering, budgeting, and coverage tests."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from _fixtures.entity_helpers import write_markdown_entity

from science_tool.curate.rotation import select_rotation

TODAY = date(2026, 7, 18)


def _make_project(tmp_path: Path, files: list[tuple[str, dict[str, object]]]) -> Path:
    root = tmp_path / "proj"
    (root / "entities").mkdir(parents=True)
    (root / "science.yaml").write_text("name: demo\nknowledge_profiles:\n  local: core\n", encoding="utf-8")
    for rel, frontmatter in files:
        write_markdown_entity(root, rel, frontmatter)
    return root


def _plan(pid: str, *, status: str = "active", created: str | None = None, last_reviewed: str | None = None) -> dict:
    frontmatter: dict[str, object] = {"id": f"plan:{pid}", "kind": "plan", "title": "P", "status": status}
    if created is not None:
        frontmatter["created"] = created
    if last_reviewed is not None:
        frontmatter["review_state"] = {"last_reviewed": last_reviewed}
    return frontmatter


def test_total_order_never_and_tiebreaks(tmp_path: Path) -> None:
    root = _make_project(
        tmp_path,
        [
            ("entities/plans/0001.md", _plan("0001", created="2026-01-01", last_reviewed="2026-05-01")),
            ("entities/plans/0002.md", _plan("0002", created="2026-01-01", last_reviewed="2026-05-01")),
            ("entities/plans/0003.md", _plan("0003", created="2026-02-01")),           # never reviewed
            ("entities/plans/0004.md", _plan("0004", created="2026-01-01")),           # never reviewed, older created
            ("entities/plans/0005.md", _plan("0005")),                                  # never reviewed, no created
        ],
    )
    result = select_rotation(root, today=TODAY)
    order = [row["id"] for row in result.rows]
    # never-reviewed first: missing created (DATE_MIN) < 2026-01-01 < 2026-02-01;
    # then the 2026-05-01 pair broken by id.
    assert order == ["plan:0005", "plan:0004", "plan:0003", "plan:0001", "plan:0002"]


def test_rank_and_selected_flags(tmp_path: Path) -> None:
    files = [
        (f"entities/plans/{i:04d}.md", _plan(f"{i:04d}", created="2026-01-01", last_reviewed=f"2026-05-{i:02d}"))
        for i in range(1, 6)
    ]
    root = _make_project(tmp_path, files)  # N=5 <= N_FULL, so budget == 5
    result = select_rotation(root, today=TODAY)
    assert result.pool_size == 5
    assert result.budget == 5
    assert result.coverage_rounds == 1
    assert all(row["rank"] == i + 1 for i, row in enumerate(result.rows))
    assert all(row["selected"] for row in result.rows)


def test_age_days_and_iso_and_never(tmp_path: Path) -> None:
    root = _make_project(
        tmp_path,
        [
            ("entities/plans/0001.md", _plan("0001", created="2026-01-01", last_reviewed="2026-07-08")),
            ("entities/plans/0002.md", _plan("0002", created="2026-01-01")),  # never
        ],
    )
    result = select_rotation(root, today=TODAY)
    by_id = {row["id"]: row for row in result.rows}
    assert by_id["plan:0001"]["last_reviewed"] == "2026-07-08"
    assert by_id["plan:0001"]["age_days"] == 10
    assert by_id["plan:0002"]["last_reviewed"] is None
    assert by_id["plan:0002"]["age_days"] is None


def test_empty_corpus_coverage_rounds_zero(tmp_path: Path) -> None:
    root = _make_project(
        tmp_path,
        [("entities/datasets/d1.md", {"id": "dataset:d1", "kind": "dataset", "title": "D", "status": "active"})],
    )
    result = select_rotation(root, today=TODAY)
    assert result.pool_size == 0
    assert result.budget == 0
    assert result.coverage_rounds == 0
    assert result.rows == []


def test_freshness_null_without_graph(tmp_path: Path) -> None:
    root = _make_project(
        tmp_path,
        [("entities/plans/0001.md", _plan("0001", created="2026-01-01"))],
    )
    result = select_rotation(root, today=TODAY)
    assert result.graph_source == "absent"
    assert result.rows[0]["freshness"] is None


def test_correspondence_row_never_gets_freshness(tmp_path: Path, monkeypatch) -> None:
    """Scope guard: even when the graph is current AND carries a freshnessState for a
    plan, a correspondence-scoped row's freshness stays null."""
    root = _make_project(
        tmp_path,
        [("entities/plans/0001.md", _plan("0001", created="2026-01-01"))],
    )
    monkeypatch.setattr(
        "science_tool.curate.rotation.graph_freshness",
        lambda _root: ("current", {"plan:0001": "needs-review"}),
    )
    result = select_rotation(root, today=TODAY)
    assert result.graph_source == "current"
    assert result.rows[0]["id"] == "plan:0001"
    assert result.rows[0]["freshness"] is None  # plan is correspondence-scoped


def test_epistemic_row_gets_freshness_when_current(tmp_path: Path, monkeypatch) -> None:
    """An epistemic row is enriched with its freshnessState when the graph is current."""
    root = _make_project(
        tmp_path,
        [
            (
                "entities/hypotheses/h1.md",
                {"id": "hypothesis:h1", "kind": "hypothesis", "title": "H", "status": "active", "created": "2026-01-01"},
            )
        ],
    )
    monkeypatch.setattr(
        "science_tool.curate.rotation.graph_freshness",
        lambda _root: ("current", {"hypothesis:h1": "needs-review"}),
    )
    result = select_rotation(root, today=TODAY)
    assert result.rows[0]["freshness"] == "needs-review"


def test_coverage_invariant_ordering(tmp_path: Path) -> None:
    """The n=1 coverage counterexample as an ordering property.

    A reviewed yesterday, B today, created(A) < created(B) so A wins the tie-break.
    Stamping A *today* leaves A at rank 1 (a budget-1 sweep re-selects A, starving
    B). Stamping A strictly after the corpus's pre-round maximum moves A behind B,
    so a budget-1 sweep would then reach B.
    """
    yesterday = "2026-07-17"
    today = "2026-07-18"
    root = _make_project(
        tmp_path,
        [
            ("entities/plans/000a.md", _plan("000a", created="2026-01-01", last_reviewed=yesterday)),
            ("entities/plans/000b.md", _plan("000b", created="2026-02-01", last_reviewed=today)),
        ],
    )
    # Round 0: A (yesterday) sorts ahead of B (today).
    assert select_rotation(root, today=TODAY).rows[0]["id"] == "plan:000a"

    # Stamp A "today" (what `entity review` does) -> A and B tie at today, A wins
    # created tie-break, so A is STILL rank 1: B is starved.
    write_markdown_entity(
        root, "entities/plans/000a.md", _plan("000a", created="2026-01-01", last_reviewed=today)
    )
    assert select_rotation(root, today=TODAY).rows[0]["id"] == "plan:000a"

    # Stamp A strictly after the pre-round maximum (tomorrow) -> A now sorts after
    # B, so B becomes rank 1 and is covered.
    tomorrow = "2026-07-19"
    write_markdown_entity(
        root, "entities/plans/000a.md", _plan("000a", created="2026-01-01", last_reviewed=tomorrow)
    )
    assert select_rotation(root, today=TODAY).rows[0]["id"] == "plan:000b"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_curate_rotation_select.py -v`
Expected: FAIL — `ImportError: cannot import name 'select_rotation'`.

- [ ] **Step 3: Write minimal implementation**

Edit `science/src/science_tool/curate/rotation.py`. `import math`, `from dataclasses import dataclass`, and `from datetime import date` are already present (from Task 2); no new imports are needed. Append:

```python
@dataclass(frozen=True)
class RotationResult:
    rows: list[dict]
    pool_size: int
    budget: int
    coverage_rounds: int
    graph_source: str


def select_rotation(project_root: Path, *, today: date) -> RotationResult:
    """Rank the eligible corpus least-recently-reviewed first and mark this sweep's
    budget. Rows are the full ranked queue; the CLI slices to the budget for display."""
    corpus = eligible_corpus(project_root)
    ordered = sorted(
        corpus,
        key=lambda entity: (entity.last_reviewed or DATE_MIN, entity.created or DATE_MIN, entity.id),
    )
    pool_size = len(ordered)
    budget = rotation_budget(pool_size)
    coverage_rounds = math.ceil(pool_size / budget) if budget else 0
    graph_source, states = graph_freshness(project_root)
    rows: list[dict] = []
    for index, entity in enumerate(ordered):
        rank = index + 1
        rows.append(
            {
                "id": entity.id,
                "last_reviewed": entity.last_reviewed.isoformat() if entity.last_reviewed else None,
                "age_days": (today - entity.last_reviewed).days if entity.last_reviewed else None,
                "rank": rank,
                "selected": rank <= budget,
                "freshness": (
                    states.get(entity.id)
                    if graph_source == "current" and entity.scope is CurationScope.EPISTEMIC
                    else None
                ),
            }
        )
    return RotationResult(
        rows=rows, pool_size=pool_size, budget=budget, coverage_rounds=coverage_rounds, graph_source=graph_source
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science && uv run --frozen pytest tests/test_curate_rotation_select.py -v`
Expected: PASS (8 tests).

- [ ] **Step 5: Run ruff + pyright**

Run: `cd science && uv run ruff check src/science_tool/curate/rotation.py && uv run pyright src/science_tool/curate/rotation.py`
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/curate/rotation.py science/tests/test_curate_rotation_select.py
git commit -m "feat(curate): select_rotation ranking and budgeting core"
```

---

### Task 5: `entity rotation` CLI command

**Files:**
- Modify: `science/src/science_tool/entities_cli.py` (add a command to the existing `entity_group`; it is registered by the decorator — no other wiring needed)
- Test: `science/tests/test_curate_rotation_cli.py`

**Interfaces:**
- Consumes: `select_rotation`, `RotationError`, `RotationResult` (Task 4); the module already imports `click`, `Path`, `OUTPUT_FORMATS`, `emit_query_rows`, `EntityCommandError`.
- Produces: the `science entity rotation` CLI command.

- [ ] **Step 1: Write the failing test**

Create `science/tests/test_curate_rotation_cli.py`:

```python
"""CLI tests for `entity rotation`."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner
from _fixtures.entity_helpers import write_markdown_entity

from science_tool.cli import main as cli_main


def _make_project(tmp_path: Path, count: int) -> Path:
    root = tmp_path / "proj"
    (root / "entities").mkdir(parents=True)
    (root / "science.yaml").write_text("name: demo\nknowledge_profiles:\n  local: core\n", encoding="utf-8")
    for i in range(1, count + 1):
        write_markdown_entity(
            root,
            f"entities/plans/{i:04d}.md",
            {
                "id": f"plan:{i:04d}",
                "kind": "plan",
                "title": "P",
                "status": "active",
                "review_state": {"last_reviewed": f"2026-05-{i:02d}"},
            },
        )
    return root


def test_rotation_json_shape(tmp_path: Path, monkeypatch) -> None:
    root = _make_project(tmp_path, 3)
    monkeypatch.chdir(root)
    result = CliRunner().invoke(cli_main, ["entity", "rotation", "--format", "json"])
    assert result.exit_code == 0, result.output

    payload = json.loads(result.output)
    assert payload["format"] == "json"
    assert payload["meta"] == {
        "pool_size": 3,
        "budget": 3,
        "displayed": 3,
        "coverage_rounds": 1,
        "graph_source": "absent",
    }
    rows = payload["rows"]
    assert [row["id"] for row in rows] == ["plan:0001", "plan:0002", "plan:0003"]
    assert set(rows[0]) == {"id", "last_reviewed", "age_days", "rank", "selected", "freshness"}
    assert rows[0]["selected"] is True
    assert rows[0]["freshness"] is None


def test_rotation_all_shows_full_queue_but_budgets_prefix(tmp_path: Path, monkeypatch) -> None:
    root = _make_project(tmp_path, 30)  # N=30 > N_FULL -> budget < 30
    monkeypatch.chdir(root)
    result = CliRunner().invoke(cli_main, ["entity", "rotation", "--all", "--format", "json"])
    assert result.exit_code == 0, result.output

    payload = json.loads(result.output)
    assert payload["meta"]["pool_size"] == 30
    assert payload["meta"]["budget"] < 30
    assert payload["meta"]["displayed"] == 30  # --all shows every row
    rows = payload["rows"]
    assert len(rows) == 30
    selected = [row for row in rows if row["selected"]]
    assert len(selected) == payload["meta"]["budget"]  # only the prefix is selected


def test_rotation_default_displays_only_budget(tmp_path: Path, monkeypatch) -> None:
    root = _make_project(tmp_path, 30)
    monkeypatch.chdir(root)
    result = CliRunner().invoke(cli_main, ["entity", "rotation", "--format", "json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert len(payload["rows"]) == payload["meta"]["budget"]
    assert payload["meta"]["displayed"] == payload["meta"]["budget"]


def test_rotation_table_renders_never(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "proj"
    (root / "entities").mkdir(parents=True)
    (root / "science.yaml").write_text("name: demo\nknowledge_profiles:\n  local: core\n", encoding="utf-8")
    write_markdown_entity(
        root, "entities/plans/0001.md", {"id": "plan:0001", "kind": "plan", "title": "P", "status": "active"}
    )
    monkeypatch.chdir(root)
    result = CliRunner().invoke(cli_main, ["entity", "rotation"])
    assert result.exit_code == 0, result.output
    assert "never" in result.output
    assert "1 of 1" in result.output  # dynamic title carries budget/pool
    assert "coverage:" in result.output  # nonempty output carries the coverage clause


def test_rotation_empty_corpus_table_omits_coverage_clause(tmp_path: Path, monkeypatch) -> None:
    """Table output only: the coverage clause is omitted when coverage_rounds == 0.

    (JSON never renders a title, so clause omission can only be asserted on the table.)
    """
    root = tmp_path / "proj"
    (root / "entities").mkdir(parents=True)
    (root / "science.yaml").write_text("name: demo\nknowledge_profiles:\n  local: core\n", encoding="utf-8")
    write_markdown_entity(
        root, "entities/datasets/d1.md", {"id": "dataset:d1", "kind": "dataset", "title": "D", "status": "active"}
    )
    monkeypatch.chdir(root)
    result = CliRunner().invoke(cli_main, ["entity", "rotation"])  # table
    assert result.exit_code == 0, result.output
    assert "0 of 0" in result.output  # dynamic title still carries budget/pool
    assert "coverage:" not in result.output  # clause omitted when coverage_rounds == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_curate_rotation_cli.py -v`
Expected: FAIL — `Error: No such command 'rotation'.` (non-zero exit).

- [ ] **Step 3: Write minimal implementation**

Edit `science/src/science_tool/entities_cli.py`. Add the following command function immediately after the `entity_needs_review` command (after its function body, near line 584). Do not add new module-level imports — everything used is already imported except `date` and the rotation symbols, which are imported locally inside the function (matching the `entity_review`/`entity_needs_review` pattern of local imports):

```python
@entity_group.command("rotation")
@click.option(
    "--all",
    "show_all",
    is_flag=True,
    default=False,
    help="Show the whole ranked queue, not just this sweep's budget.",
)
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
def entity_rotation(show_all: bool, output_format: str) -> None:
    """Rank the reviewable corpus least-recently-reviewed first, printing this sweep's budget.

    Advisory and stateless: it reviews nothing. Review a listed entity with
    `science entity review <ref> --note ...`. Rotation reaches full coverage in a
    bounded number of sweeps only when each sweep both completes its budget AND stamps
    its reviews with a date strictly later than the corpus's current maximum
    last_reviewed; completing the budget alone does not guarantee coverage.
    """
    from datetime import date

    from science_tool.curate.rotation import RotationError, select_rotation

    try:
        result = select_rotation(Path.cwd(), today=date.today())
    except (EntityCommandError, RotationError) as exc:
        raise click.ClickException(str(exc)) from exc

    shown = result.rows if show_all else result.rows[: result.budget]
    coverage_clause = f" (coverage: {result.coverage_rounds} sweeps)" if result.coverage_rounds else ""
    title = f"rotation — {result.budget} of {result.pool_size}{coverage_clause}"

    def _never(value: object, _row: object) -> str:
        return "never" if value is None else str(value)

    def _selected(value: object, _row: object) -> str:
        return "✓" if value else ""

    emit_query_rows(
        output_format=output_format,
        title=title,
        columns=[
            ("rank", "#"),
            ("id", "ID"),
            ("last_reviewed", "Last reviewed"),
            ("age_days", "Age (days)"),
            ("selected", "Sweep"),
            ("freshness", "Freshness"),
        ],
        rows=shown,
        meta={
            "pool_size": result.pool_size,
            "budget": result.budget,
            "displayed": len(shown),
            "coverage_rounds": result.coverage_rounds,
            "graph_source": result.graph_source,
        },
        renderers={"last_reviewed": _never, "age_days": _never, "selected": _selected},
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science && uv run --frozen pytest tests/test_curate_rotation_cli.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Full checks (module lint/types + whole suite)**

Run: `cd science && uv run ruff check && uv run pyright && uv run --frozen pytest -q`
Expected: ruff clean, pyright 0 errors, full suite green (grep the tail for `failed` — a background detach reports the shell's exit code, not pytest's).

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/entities_cli.py science/tests/test_curate_rotation_cli.py
git commit -m "feat(curate): add `science entity rotation` CLI command"
```

---

### Task 6: Wire rotation into `/science:curate` and the user guide

Rotation is the coverage *floor* for the curation sweep; the weighted attention
sample stays as enrichment/alarm input. This task is documentation only — no
Python, no tests — but its deliverable is verifiable: the command it references
must exist (Task 5) and both docs must name it.

**Files:**
- Modify: `commands/curate.md` (Phase 1 evidence list; Phase 2 triage)
- Modify: `docs/user-guide/health-and-validation.md` ("Needs Review And Freshness")

**Interfaces:**
- Consumes: the `science entity rotation` command (Task 5).
- Produces: nothing importable.

- [ ] **Step 1: Add rotation to the Phase 1 evidence commands in `commands/curate.md`**

In the "gather deterministic evidence" fenced block (the one containing
`uv run science curate inventory ...`), add this line immediately after the
`uv run science curate inventory --project-root . --format json` line:

```bash
uv run science entity rotation --format json
```

(No `--project-root` flag: like `science tasks list` and `science entity
needs-review`, rotation reads the current working directory, which the command
preamble has already set to the project root.)

- [ ] **Step 2: Rewrite the Phase 2 triage reading-set paragraph in `commands/curate.md`**

Replace this paragraph:

```markdown
Group findings into curation themes and choose a bounded reading set. Use the
weighted attention sample as the default way to choose epistemic entities for
close reading; do not collapse the pass to deterministic top-N priority rows.
Read targeted source artifacts, not the entire corpus.
```

with:

```markdown
Group findings into curation themes and choose a bounded reading set in two
layers:

1. **Coverage floor — `science entity rotation`.** This is the default reading
   set. It ranks the reviewable corpus least-recently-reviewed first and prints
   an adaptive per-sweep budget. Read every row it marks `selected`. For each
   selected row you actually review, record a reasoned review artifact and
   advance its state with
   `science entity review <ref> --note "<what you inspected and changed>"`. That
   stamp is what moves the entity out of the least-recently-reviewed prefix;
   without it the same prefix recurs on the next sweep. Rotation drives the
   corpus toward full coverage in a bounded number of sweeps only when each sweep
   completes its budget **and** its review stamps carry a date strictly later
   than the corpus's current maximum `last_reviewed`. Under `--dry-run` or
   `--no-write`, do **not** call `entity review`: rotation state does not advance
   and the same rows reappear on the next real sweep.
2. **Enrichment / alarm — the weighted attention sample.** Use
   `science graph attention-sample` to pull *additional* high-attention
   epistemic entities into the pass beyond the rotation floor. Attention biases
   toward what changed or is contested; rotation, once its stamps land, drives
   floor coverage. They are complementary, not alternatives — do not drop the
   rotation floor in favor of attention alone.

Read targeted source artifacts, not the entire corpus.
```

- [ ] **Step 3: Document rotation in `docs/user-guide/health-and-validation.md`**

In the "Needs Review And Freshness" section, immediately after the
`science graph attention-rank` fenced example block (the one containing
`science graph attention-rank --kind proposition --limit 20`) and before the
paragraph beginning `` `science entity review` requires a review artifact ``,
insert:

````markdown
`science entity rotation` is the coverage *floor* that complements
`attention-rank`'s weighted queue. It ranks the reviewable corpus — the same
domain `entity review` resolves — least-recently-reviewed first and prints an
adaptive per-sweep budget, so the least-recently-touched entities are read first.
It is stateless and read-only, advisory like the other attention surfaces: it
selects but never reviews, so a selected row only leaves the least-recently-
reviewed prefix once you stamp it with `science entity review <ref> --note ...`.
It reaches full coverage in a bounded number of sweeps only when each sweep both
completes its budget and stamps reviews with a date strictly later than the
corpus's current maximum `last_reviewed`; the two tools are complementary —
attention biases toward what changed, rotation drives floor coverage.

```bash
science entity rotation
science entity rotation --all --format json
```
````

- [ ] **Step 4: Verify the referenced command exists and both docs name it**

Run:

```bash
cd science && uv run science entity rotation --help
cd .. && rg -n "entity rotation" commands/curate.md docs/user-guide/health-and-validation.md
```

Expected: the `--help` prints the command's usage (exit 0), and `rg` shows the
new references in both files.

- [ ] **Step 5: Commit**

```bash
git add commands/curate.md docs/user-guide/health-and-validation.md
git commit -m "doc(curate): make adaptive rotation the curation coverage floor"
```

---

## Notes for the executor

- **`science/uv.lock` drifts** `0.3.0 → 0.4.1` whenever `uv run` executes (the main checkout is Dropbox-synced). It will appear modified in `git status`. **Never stage it.** Each `git add` above names exact paths, so follow them literally rather than `git add -A`.
- **Background detach:** any foreground command that exceeds the 120s tool timeout auto-backgrounds; the completion notification then reflects a trailing shell command's exit code, not pytest's. Always confirm suite results by grepping the captured output for `failed` / `passed`, never by the reported exit code alone.
- **pyright does not type-check `tests/`** — IDE type diagnostics on test files are non-gating; `uv run pyright` (which covers `src/`) is authoritative.
- All logic lives in `curate/rotation.py`; `entities_cli.py` only parses arguments and renders. Keep it that way.

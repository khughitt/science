# Entity Consolidation P1 — Lifecycle Visibility Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make entity-consuming read/listing paths (big-picture resolver/bundles, knowledge-gaps, `entities list`) hide `superseded`/`archived` entities by default (removing v3…v12 snapshot noise), and ship a report-then-apply command that auto-derives `superseded` status from linear `sci:supersedes` relation chains — without touching KG ingestion.

**Architecture:** A single pure predicate `is_default_visible(status)` plus two module-level status sets in `science_tool/entities.py` become the source of truth for visibility. View/consumer layers (big-picture resolver, knowledge-gaps loaders) filter through it; KG ingestion (`MarkdownAdapter.discover` / `load_project_sources`) and the nonexistent-reference known-id set are deliberately left unfiltered so lineage and reference resolution survive. A new `consolidation.py` module walks the canonical `relations:` `sci:supersedes` edges (not a top-level `supersedes:` field, not `sci:amends`), classifies chains as linear or non-linear, and (report-then-apply) stamps `status: superseded` on superseded members via the existing `edit_entity` helper, surfaced as `science entities mark-superseded`.

**Tech Stack:** Python 3.12+, Pydantic v2 (entity models / profiles), Click (CLI), pytest (`-q`, markers `snapshot`/`real_projects` excluded by default), `rdflib` (graph; not needed here), YAML frontmatter.

---

## Scope & deliberate deviations from design §10 P1

This plan implements **P1 only**. P2 (curate detector), P3 (archive tier + shared iterator + `search --archived`), and P4 (apply command + digest consumption) are separate plans. Three scoping refinements vs the design's P1 bullet, made at plan time and called out so a reviewer sees them:

1. **`archived` is NOT added to any kind's `statuses` vocabulary in P1 (YAGNI).** Nothing in P1 *writes* `status: archived` — that first happens in P3/P4 (relocation/apply). P1 only needs `archived` in the hidden-set so the predicate and filters are forward-compatible. Adding the vocab value to kinds will ship in the phase that first sets it, alongside its parity-test update. This keeps P1's diff off the 26-kind status literals and the frozen parity dicts entirely.
2. **Most supersedes-eligible kinds already declare `superseded`, but three do not — P1 skips those gracefully rather than adding vocab to them.** The `sci:supersedes` relation permits `workflow-run` and all `_CONCLUSION_KINDS` = `interpretation`, `finding`, `discussion`, `report`, `validation-report`, `story`. The first four declare `superseded`; but `validation-report`, `story`, and `workflow-run` carry **no `statuses` declaration at all** (`category=AUTHORED_CORE` with no `home`/`strategy`/`statuses`), so `valid_statuses(kind)` raises `KeyError` and `edit_entity`'s `_validate_status` would `KeyError` on `_STATUS_VALUES[kind]`. The auto-derive therefore must **defensively skip any member whose kind does not declare `superseded`** (catch `KeyError`), recording it in the report's `skipped_kinds` instead of crashing. Adding status vocab to operational/statusless kinds is a deliberate non-goal of P1 (these are not the motivating interpretation-chain case); revisit when/if those kinds need archival. `hypothesis`/`question` lack `superseded` but are not supersedes-eligible, so the auto-derive never targets them. **Project-local kinds are likewise skipped from auto-apply in P1** even if their vocab includes `superseded`: `edit_entity`'s `find_entity` lookup and `_validate_status` honor built-in markdown policies only, so a local-kind member would pass a vocab check then fail at write. The eligibility gate (`_supports_superseded`) therefore restricts to built-in `_STATUS_VALUES`-backed kinds; honoring project-local policies in `edit_entity` is deferred.
3. **The nonexistent-reference known-id set (`validator._collect_project_ids`) is intentionally left unfiltered, and entity lookup (`find_entity`) is not filtered.** In P1, hidden entities are *not relocated* — they remain on disk and reachable. Filtering the known-id set would turn every `related:` pointer to a superseded entity into a false "nonexistent reference" error; filtering `find_entity` would break mutating a superseded entity. Status filtering applies to *aggregation/view/listing* surfaces only: bundle assembly via the resolver (Task 3), knowledge-gaps demand (Task 7), and `entities list` / typed-list commands via `list_entities` (Task 8, with an `--include-hidden` escape hatch). **Deferred and documented (not silently dropped):** `attention`/`next-steps` read the materialized graph (status is not on the freshness surface); and `entities inventory` / `build_inventory` (`entities_inventory.py`) is a curate-oriented surface owned by P2's curate-inventory migration — neither is filtered in P1.

---

## File structure

**Modify:**
- `science/src/science_tool/entities.py` — add `_HIDDEN_STATUSES`, `_LIVE_STATUSES`, `is_default_visible()`; add default-hidden filtering + `include_hidden` param to `list_entities()`. One clear responsibility: status vocabulary + visibility is already this module's job.
- `science/src/science_tool/big_picture/resolver.py` — filter hidden statuses in `_load_entities`.
- `science/src/science_tool/big_picture/knowledge_gaps.py` — filter hidden statuses in `_load_topics`.
- `science/src/science_tool/cli.py` — add `entities mark-superseded` subcommand; add `--include-hidden` to the generic `entity list` command. Typed per-kind list commands hide by default (they call `list_entities`, which now defaults to hiding) and still accept explicit `--status`; a typed-command `--include-hidden` flag is deferred (noted in Task 8).

**Create:**
- `science/src/science_tool/consolidation.py` — supersedes-chain scan + classification + `mark_superseded()` report/apply helper.
- `science/tests/test_status_visibility.py` — predicate unit tests + the two classification guard tests.
- `science/tests/test_consolidation_mark_superseded.py` — chain scan, report, apply, and CLI tests.

**Touch (assertions only):**
- `science/tests/test_big_picture_resolver.py` — add a status-filtering test.

---

### Task 1: Visibility predicate + hidden/live status sets

**Files:**
- Modify: `science/src/science_tool/entities.py` (insert after `_ALLOWED_EXPLICIT_ROOTS = (Path("entities"),)` at line 186, and the function after `valid_statuses` ends at line 224, before the `EntityWriteResult` dataclass at line 227)
- Test: `science/tests/test_status_visibility.py` (new)

- [ ] **Step 1: Write the failing test**

Create `science/tests/test_status_visibility.py`:

```python
"""Lifecycle-visibility predicate and classification guards (consolidation P1)."""

from __future__ import annotations

from science_tool.entities import (
    _HIDDEN_STATUSES,
    _LIVE_STATUSES,
    _STATUS_VALUES,
    is_default_visible,
)


def test_hidden_statuses_are_not_default_visible() -> None:
    assert is_default_visible("superseded") is False
    assert is_default_visible("archived") is False


def test_live_statuses_are_default_visible() -> None:
    assert is_default_visible("active") is True
    assert is_default_visible("proposed") is True
    assert is_default_visible("retired") is True  # retired stays visible in this slice
    assert is_default_visible("deprecated") is True
    assert is_default_visible("abandoned") is True


def test_missing_or_empty_status_is_default_visible() -> None:
    assert is_default_visible(None) is True
    assert is_default_visible("") is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && pytest tests/test_status_visibility.py -v`
Expected: FAIL with `ImportError: cannot import name '_HIDDEN_STATUSES'` (and `_LIVE_STATUSES`, `is_default_visible`).

- [ ] **Step 3: Add the status sets**

In `science/src/science_tool/entities.py`, immediately after the line `_ALLOWED_EXPLICIT_ROOTS = (Path("entities"),)` (line 186), add:

```python
# Lifecycle states hidden from default view/consumer surfaces (consolidation P1).
# `archived` is reserved here for forward-compatibility; nothing sets it until the
# archive/apply phases. Filtering happens at consumer layers ONLY — never at the
# KG ingestion layer (MarkdownAdapter.discover / load_project_sources), so
# `sci:supersedes` lineage survives materialization.
_HIDDEN_STATUSES: frozenset[str] = frozenset({"superseded", "archived"})

# Human-curated allowlist of statuses that remain default-visible. This is the
# source of truth the EntityKind schema lacks (it carries only `statuses` /
# `default_status`, no live/terminal metadata). Every status declared by any core
# kind must appear here or in `_HIDDEN_STATUSES`; the guard tests in
# test_status_visibility.py fail loud on an unclassified status, forcing a
# deliberate live-or-hidden decision when a new status is introduced. Per design
# open-question #5, `retired`/`deprecated`/`abandoned` stay LIVE (visible) in this
# slice — no regression vs today.
_LIVE_STATUSES: frozenset[str] = frozenset(
    {
        "draft",
        "active",
        "retired",
        "partially-answered",
        "answered",
        "deferred",
        "proposed",
        "under-investigation",
        "partially-supported",
        "supported",
        "weakened",
        "refuted",
        "complete",
        "contested",
        "amended",
        "deprecated",
        "abandoned",
    }
)
```

- [ ] **Step 4: Add the predicate**

In the same file, after `valid_statuses` ends (line 224) and before the `@dataclass(frozen=True)` / `class EntityWriteResult` block (line 227), add:

```python
def is_default_visible(status: str | None) -> bool:
    """Whether an entity with ``status`` is shown by default on view/consumer
    surfaces. A missing/empty status is visible; only explicitly hidden lifecycle
    states (`_HIDDEN_STATUSES`) are excluded. This is NOT ``status == "active"`` —
    live statuses such as `proposed`, `answered`, `complete`, `retired` stay
    visible.
    """
    return status not in _HIDDEN_STATUSES
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd science && pytest tests/test_status_visibility.py -v`
Expected: PASS (3 passed) — except the two guard tests added in Task 2 do not exist yet; only the three predicate tests run here.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/entities.py science/tests/test_status_visibility.py
git commit -m "feat(consolidation): add is_default_visible predicate + hidden/live status sets"
```

---

### Task 2: Status-classification guard tests

**Files:**
- Test: `science/tests/test_status_visibility.py` (append to the file from Task 1)

These guards make the design's visibility invariant implementable without schema lifecycle metadata: (1) no kind is born hidden; (2) every declared status is consciously classified.

- [ ] **Step 1: Write the failing guard tests**

Append to `science/tests/test_status_visibility.py`:

```python
def test_no_core_kind_defaults_to_a_hidden_status() -> None:
    """Guard 1: a hidden state can never be the status an entity is born with."""
    from science_tool.entities import _DEFAULT_STATUS

    offenders = {
        kind: status
        for kind, status in _DEFAULT_STATUS.items()
        if status in _HIDDEN_STATUSES
    }
    assert offenders == {}, f"kinds defaulting to a hidden status: {offenders}"


def test_every_declared_status_is_classified_live_or_hidden() -> None:
    """Guard 2: every status any kind declares must be in the live allowlist or the
    hidden set. An unclassified status would silently stay default-visible (since
    is_default_visible is a pure hidden-set check), so this fails loud to force a
    deliberate live-or-hidden decision."""
    classified = _LIVE_STATUSES | _HIDDEN_STATUSES
    declared = {status for statuses in _STATUS_VALUES.values() for status in statuses}
    unclassified = declared - classified
    assert unclassified == set(), (
        f"unclassified statuses (add to _LIVE_STATUSES or _HIDDEN_STATUSES): {sorted(unclassified)}"
    )


def test_live_and_hidden_sets_are_disjoint() -> None:
    assert _LIVE_STATUSES.isdisjoint(_HIDDEN_STATUSES)
```

- [ ] **Step 2: Run the guard tests**

Run: `cd science && pytest tests/test_status_visibility.py -v`
Expected: PASS (6 passed total). If `test_every_declared_status_is_classified_live_or_hidden` FAILS, the failure message lists the missing status(es) — add each to `_LIVE_STATUSES` (if it is a live/visible state) or `_HIDDEN_STATUSES` (if terminal-and-hidden) in `entities.py`, then re-run. The expected current declared-status union is fully covered by the `_LIVE_STATUSES` literal in Task 1 plus `{superseded}`.

- [ ] **Step 3: Commit**

```bash
git add science/tests/test_status_visibility.py
git commit -m "test(consolidation): guard hidden-status invariant (no hidden default, all statuses classified)"
```

---

### Task 3: Filter hidden statuses in the big-picture resolver

**Files:**
- Modify: `science/src/science_tool/big_picture/resolver.py:107-115` (`_load_entities`)
- Test: `science/tests/test_big_picture_resolver.py` (append)

`_load_entities` is the single load point for questions, hypotheses, and interpretations feeding bundle assembly. Filtering here removes superseded interpretation snapshots from bundles (the motivating H01/H05 noise) while leaving files on disk.

- [ ] **Step 1: Write the failing test**

Append to `science/tests/test_big_picture_resolver.py`:

```python
def test_superseded_interpretation_is_excluded_from_resolution(tmp_path) -> None:
    (tmp_path / "entities" / "questions").mkdir(parents=True)
    (tmp_path / "entities" / "hypotheses").mkdir(parents=True)
    (tmp_path / "entities" / "interpretations").mkdir(parents=True)
    (tmp_path / "science.yaml").write_text("name: vis\n")
    (tmp_path / "entities" / "questions" / "q01.md").write_text(
        '---\nid: "question:q01"\ntype: "question"\nrelated: ["interpretation:i01-old", "interpretation:i02-new"]\n---\nQ.\n'
    )
    (tmp_path / "entities" / "hypotheses" / "h01.md").write_text(
        '---\nid: "hypothesis:h01"\ntype: "hypothesis"\n---\nH.\n'
    )
    (tmp_path / "entities" / "interpretations" / "i01-old.md").write_text(
        '---\nid: "interpretation:i01-old"\ntype: "interpretation"\nstatus: "superseded"\nrelated: ["question:q01", "hypothesis:h01"]\n---\nold.\n'
    )
    (tmp_path / "entities" / "interpretations" / "i02-new.md").write_text(
        '---\nid: "interpretation:i02-new"\ntype: "interpretation"\nstatus: "active"\nrelated: ["question:q01", "hypothesis:h01"]\n---\nnew.\n'
    )

    from science_tool.big_picture.resolver import _load_entities
    from science_tool.big_picture.layout import entity_dir

    loaded = _load_entities(entity_dir(tmp_path, "interpretation"))
    assert "interpretation:i02-new" in loaded
    assert "interpretation:i01-old" not in loaded  # superseded: hidden by default


def test_load_entities_can_include_hidden_when_requested(tmp_path) -> None:
    (tmp_path / "entities" / "interpretations").mkdir(parents=True)
    (tmp_path / "science.yaml").write_text("name: vis\n")
    (tmp_path / "entities" / "interpretations" / "i01-old.md").write_text(
        '---\nid: "interpretation:i01-old"\ntype: "interpretation"\nstatus: "superseded"\n---\nold.\n'
    )

    from science_tool.big_picture.resolver import _load_entities
    from science_tool.big_picture.layout import entity_dir

    loaded = _load_entities(entity_dir(tmp_path, "interpretation"), include_hidden=True)
    assert "interpretation:i01-old" in loaded
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && pytest tests/test_big_picture_resolver.py::test_superseded_interpretation_is_excluded_from_resolution tests/test_big_picture_resolver.py::test_load_entities_can_include_hidden_when_requested -v`
Expected: FAIL — first test fails on `assert ... not in loaded` (currently included); second fails with `TypeError: _load_entities() got an unexpected keyword argument 'include_hidden'`.

- [ ] **Step 3: Implement the filter**

In `science/src/science_tool/big_picture/resolver.py`, add to the imports block (after `from science_tool.big_picture.layout import entity_dir`):

```python
from science_tool.entities import is_default_visible
```

Replace `_load_entities` (lines 107-115):

```python
def _load_entities(directory: Path) -> dict[str, dict]:
    if not directory.is_dir():
        return {}
    out: dict[str, dict] = {}
    for path in sorted(directory.glob("*.md")):
        fm = read_frontmatter(path)
        if fm and "id" in fm:
            out[str(fm["id"])] = fm
    return out
```

with:

```python
def _load_entities(directory: Path, *, include_hidden: bool = False) -> dict[str, dict]:
    if not directory.is_dir():
        return {}
    out: dict[str, dict] = {}
    for path in sorted(directory.glob("*.md")):
        fm = read_frontmatter(path)
        if not fm or "id" not in fm:
            continue
        if not include_hidden and not is_default_visible(fm.get("status")):
            continue
        out[str(fm["id"])] = fm
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science && pytest tests/test_big_picture_resolver.py -v`
Expected: PASS (all resolver tests, including the two new ones).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/big_picture/resolver.py science/tests/test_big_picture_resolver.py
git commit -m "feat(consolidation): hide superseded/archived entities from big-picture resolver"
```

---

### Task 4: Supersedes-chain scan + report (`consolidation.py`)

**Files:**
- Create: `science/src/science_tool/consolidation.py`
- Test: `science/tests/test_consolidation_mark_superseded.py` (new)

The report walks the canonical supersession edges — `relations:` entries with `predicate: "sci:supersedes"` (`S supersedes T` ⇒ edge `S→T`, T is the older/superseded one; `sci:amends` is ignored) — groups them into connected components, classifies each as a linear path or non-linear (branched/cyclic), and lists which entities a linear chain would mark `superseded`. No mutation in this task.

- [ ] **Step 1: Write the failing test**

Create `science/tests/test_consolidation_mark_superseded.py`:

```python
"""Auto-derive `superseded` from supersedes chains (consolidation P1)."""

from __future__ import annotations

from pathlib import Path

import yaml


def _write(root: Path, kind_dir: str, name: str, fm: dict) -> None:
    d = root / "entities" / kind_dir
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{name}.md").write_text(
        "---\n" + yaml.safe_dump(fm, sort_keys=False) + "---\nbody\n", encoding="utf-8"
    )


def _seed(root: Path) -> None:
    (root / "science.yaml").write_text("name: chain-test\n", encoding="utf-8")


def _supersedes(target: str) -> dict:
    """A canonical supersedes relation entry, as authored in `relations:`."""
    return {"predicate": "sci:supersedes", "target": target}


def test_report_linear_chain_lists_members(tmp_path: Path) -> None:
    _seed(tmp_path)
    # v3 <- v4 <- v5 : v5 supersedes v4, v4 supersedes v3. Survivor = v5.
    _write(tmp_path, "interpretations", "i-v3", {"id": "interpretation:i-v3", "type": "interpretation"})
    _write(tmp_path, "interpretations", "i-v4", {"id": "interpretation:i-v4", "type": "interpretation", "relations": [_supersedes("interpretation:i-v3")]})
    _write(tmp_path, "interpretations", "i-v5", {"id": "interpretation:i-v5", "type": "interpretation", "relations": [_supersedes("interpretation:i-v4")]})

    from science_tool.consolidation import mark_superseded

    report = mark_superseded(tmp_path, apply=False)
    assert report["applied"] == []
    assert len(report["chains"]) == 1
    chain = report["chains"][0]
    assert chain["survivor"] == "interpretation:i-v5"
    assert chain["linear"] is True
    assert set(chain["members"]) == {"interpretation:i-v3", "interpretation:i-v4"}
    assert set(report["to_mark"]) == {"interpretation:i-v3", "interpretation:i-v4"}
    assert report["non_linear"] == []
    assert report["skipped_kinds"] == []


def test_amends_relation_does_not_mark_superseded(tmp_path: Path) -> None:
    _seed(tmp_path)
    # sci:amends is a revision, NOT a replacement — it must not mark the target.
    _write(tmp_path, "interpretations", "i-v3", {"id": "interpretation:i-v3", "type": "interpretation"})
    _write(tmp_path, "interpretations", "i-v4", {"id": "interpretation:i-v4", "type": "interpretation", "relations": [{"predicate": "sci:amends", "target": "interpretation:i-v3"}]})

    from science_tool.consolidation import mark_superseded

    report = mark_superseded(tmp_path, apply=False)
    assert report["chains"] == []
    assert report["to_mark"] == []


def test_report_skips_already_superseded_members(tmp_path: Path) -> None:
    _seed(tmp_path)
    _write(tmp_path, "interpretations", "i-v3", {"id": "interpretation:i-v3", "type": "interpretation", "status": "superseded"})
    _write(tmp_path, "interpretations", "i-v4", {"id": "interpretation:i-v4", "type": "interpretation", "relations": [_supersedes("interpretation:i-v3")]})

    from science_tool.consolidation import mark_superseded

    report = mark_superseded(tmp_path, apply=False)
    assert report["to_mark"] == []  # i-v3 is already superseded


def test_report_flags_non_linear_chain_and_skips_it(tmp_path: Path) -> None:
    _seed(tmp_path)
    # Branched: both v4a and v4b supersede v3 (v3 has in-degree 2). Ambiguous.
    _write(tmp_path, "interpretations", "i-v3", {"id": "interpretation:i-v3", "type": "interpretation"})
    _write(tmp_path, "interpretations", "i-v4a", {"id": "interpretation:i-v4a", "type": "interpretation", "relations": [_supersedes("interpretation:i-v3")]})
    _write(tmp_path, "interpretations", "i-v4b", {"id": "interpretation:i-v4b", "type": "interpretation", "relations": [_supersedes("interpretation:i-v3")]})

    from science_tool.consolidation import mark_superseded

    report = mark_superseded(tmp_path, apply=False)
    assert report["chains"] == []
    assert report["to_mark"] == []
    assert len(report["non_linear"]) == 1
    assert set(report["non_linear"][0]["nodes"]) == {
        "interpretation:i-v3",
        "interpretation:i-v4a",
        "interpretation:i-v4b",
    }


def test_member_whose_kind_lacks_superseded_vocab_is_skipped_not_crashed(tmp_path: Path) -> None:
    _seed(tmp_path)
    # workflow-run is supersedes-eligible but declares NO status vocabulary.
    # The member must be reported under skipped_kinds, never crash.
    _write(tmp_path, "workflow-runs", "wr-old", {"id": "workflow-run:wr-old", "type": "workflow-run"})
    _write(tmp_path, "workflow-runs", "wr-new", {"id": "workflow-run:wr-new", "type": "workflow-run", "relations": [_supersedes("workflow-run:wr-old")]})

    from science_tool.consolidation import mark_superseded

    report = mark_superseded(tmp_path, apply=False)
    assert report["to_mark"] == []
    assert {entry["id"] for entry in report["skipped_kinds"]} == {"workflow-run:wr-old"}
    assert report["skipped_kinds"][0]["kind"] == "workflow-run"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && pytest tests/test_consolidation_mark_superseded.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'science_tool.consolidation'`.

- [ ] **Step 3: Implement the scan + report**

Create `science/src/science_tool/consolidation.py`:

```python
"""Entity consolidation — auto-derive `superseded` from supersedes chains (P1).

Read-only by default (report); `--apply` stamps `status: superseded` on the
superseded members of *linear* chains only. Non-linear (branched/cyclic) chains
are reported and skipped — their survivor is ambiguous and needs human review.

The canonical machine-readable supersession edge is a `relations:` entry with
`predicate: "sci:supersedes"` (the graph source of truth per the conclusion
templates) — NOT a top-level `supersedes:` field, and NOT `sci:amends` (which
revises, not replaces). This module reads those relation entries directly from
entity markdown under `entities/`. It is a CONSUMER surface, not the KG ingestion
path; it never mutates KG materialization behaviour.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from science_tool.big_picture.frontmatter import read_frontmatter
from science_tool.entities import _STATUS_VALUES, edit_entity

_SUPERSEDED = "superseded"
_SUPERSEDES_PREDICATE = "sci:supersedes"


def _iter_entity_frontmatter(project_root: Path) -> list[tuple[Path, dict[str, Any]]]:
    """All entity markdown frontmatter under entities/, as (path, frontmatter)."""
    entities_root = project_root / "entities"
    out: list[tuple[Path, dict[str, Any]]] = []
    if not entities_root.is_dir():
        return out
    for path in sorted(entities_root.rglob("*.md")):
        fm = read_frontmatter(path)
        if fm and "id" in fm:
            out.append((path, fm))
    return out


def _supersedes_targets(fm: dict[str, Any]) -> list[str]:
    """Targets this entity supersedes, from canonical `relations:` entries with
    `predicate: "sci:supersedes"`. Ignores `sci:amends` and any other predicate."""
    relations = fm.get("relations")
    if not isinstance(relations, list):
        return []
    targets: list[str] = []
    for rel in relations:
        if not isinstance(rel, dict):
            continue
        if rel.get("predicate") != _SUPERSEDES_PREDICATE:
            continue
        target = rel.get("target")
        if isinstance(target, str) and target:
            targets.append(target)
    return targets


def _kind_of(entity_id: str, fm: dict[str, Any]) -> str:
    return str(fm.get("type") or fm.get("kind") or entity_id.split(":", 1)[0])


def _supports_superseded(kind: str) -> bool:
    """Whether `kind` is a BUILT-IN markdown kind that declares the `superseded`
    status. P1 auto-apply is restricted to built-in policy-backed kinds: a
    project-local kind would pass a naive vocab check but then fail inside
    `edit_entity`, whose `find_entity` lookup iterates `_BUILTIN_MARKDOWN_POLICIES`
    only and whose `_validate_status` indexes `_STATUS_VALUES[kind]` (KeyError for
    a local kind). Checking `_STATUS_VALUES` membership directly covers both the
    status-less eligible kinds (`workflow-run`/`story`/`validation-report`, absent
    from the map) and all local kinds — every one is skipped, never crashed.
    Honoring project-local policies in `edit_entity` is deferred past P1."""
    return _SUPERSEDED in _STATUS_VALUES.get(kind, frozenset())


def _connected_components(nodes: set[str], edges: list[tuple[str, str]]) -> list[set[str]]:
    adj: dict[str, set[str]] = {n: set() for n in nodes}
    for src, dst in edges:
        adj[src].add(dst)
        adj[dst].add(src)
    seen: set[str] = set()
    components: list[set[str]] = []
    for start in sorted(nodes):
        if start in seen:
            continue
        stack = [start]
        comp: set[str] = set()
        while stack:
            node = stack.pop()
            if node in seen:
                continue
            seen.add(node)
            comp.add(node)
            stack.extend(adj[node] - seen)
        components.append(comp)
    return components


def _classify(comp: set[str], edges: list[tuple[str, str]]) -> tuple[bool, str | None, set[str]]:
    """Return (linear, survivor, members). For a linear simple path S supersedes T,
    survivor = the node nothing supersedes (in-degree 0); members = every node with
    in-degree >= 1. Non-linear when any node has in/out-degree > 1 or there is not
    exactly one survivor (cycle / branch)."""
    comp_edges = [(s, d) for s, d in edges if s in comp and d in comp]
    out_deg: dict[str, int] = {n: 0 for n in comp}
    in_deg: dict[str, int] = {n: 0 for n in comp}
    for src, dst in comp_edges:
        out_deg[src] += 1
        in_deg[dst] += 1
    survivors = [n for n in comp if in_deg[n] == 0]
    sinks = [n for n in comp if out_deg[n] == 0]
    linear = (
        all(out_deg[n] <= 1 for n in comp)
        and all(in_deg[n] <= 1 for n in comp)
        and len(survivors) == 1
        and len(sinks) == 1
    )
    survivor = survivors[0] if len(survivors) == 1 else None
    members = {n for n in comp if in_deg[n] >= 1}
    return linear, survivor, members


def mark_superseded(project_root: Path, *, apply: bool) -> dict[str, Any]:
    project_root = project_root.resolve()
    entries = _iter_entity_frontmatter(project_root)
    status_by_id: dict[str, str | None] = {}
    kind_by_id: dict[str, str] = {}
    known: set[str] = set()
    edges: list[tuple[str, str]] = []
    for _path, fm in entries:
        eid = str(fm["id"])
        known.add(eid)
        status_by_id[eid] = fm.get("status")
        kind_by_id[eid] = _kind_of(eid, fm)
    for _path, fm in entries:
        src = str(fm["id"])
        for dst in _supersedes_targets(fm):
            if dst in known:  # ignore edges to unknown ids
                edges.append((src, dst))

    nodes = {n for edge in edges for n in edge}
    chains: list[dict[str, Any]] = []
    non_linear: list[dict[str, Any]] = []
    to_mark: list[str] = []
    skipped_kinds: list[dict[str, str]] = []
    for comp in _connected_components(nodes, edges):
        if len(comp) < 2:
            continue
        linear, survivor, members = _classify(comp, edges)
        if not linear:
            non_linear.append({"nodes": sorted(comp), "reason": "branched or cyclic supersedes chain"})
            continue
        chains.append({"survivor": survivor, "members": sorted(members), "linear": True})
        for member in sorted(members):
            if status_by_id.get(member) == _SUPERSEDED:
                continue  # already superseded
            kind = kind_by_id.get(member, member.split(":", 1)[0])
            if not _supports_superseded(kind):
                skipped_kinds.append({"id": member, "kind": kind})
                continue  # not a built-in 'superseded'-capable kind; can't stamp it
            to_mark.append(member)

    report: dict[str, Any] = {
        "chains": chains,
        "non_linear": non_linear,
        "to_mark": to_mark,
        "applied": [],
        "skipped_kinds": skipped_kinds,
    }
    if apply:
        for member in to_mark:
            edit_entity(project_root, member, status=_SUPERSEDED)
            report["applied"].append(member)
    return report
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science && pytest tests/test_consolidation_mark_superseded.py -v`
Expected: PASS (5 passed: linear chain, amends-ignored, already-superseded, non-linear, statusless-kind-skipped). The apply and CLI tests are added in Tasks 5–6.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/consolidation.py science/tests/test_consolidation_mark_superseded.py
git commit -m "feat(consolidation): scan supersedes chains and report superseded candidates"
```

---

### Task 5: Apply path — stamp `status: superseded`

**Files:**
- Test: `science/tests/test_consolidation_mark_superseded.py` (append)
- (Implementation already present from Task 4's `_apply`; this task proves it end-to-end and via the real `edit_entity` write path.)

- [ ] **Step 1: Write the failing test**

Append to `science/tests/test_consolidation_mark_superseded.py`:

```python
def test_apply_sets_superseded_status_on_members(tmp_path: Path) -> None:
    _seed(tmp_path)
    _write(tmp_path, "interpretations", "i-v3", {"id": "interpretation:i-v3", "type": "interpretation", "title": "v3"})
    _write(tmp_path, "interpretations", "i-v4", {"id": "interpretation:i-v4", "type": "interpretation", "title": "v4", "relations": [_supersedes("interpretation:i-v3")]})

    from science_tool.consolidation import mark_superseded

    report = mark_superseded(tmp_path, apply=True)
    assert report["applied"] == ["interpretation:i-v3"]

    fm = read_frontmatter(tmp_path / "entities" / "interpretations" / "i-v3.md")
    assert fm is not None and fm["status"] == "superseded"
    # survivor untouched
    fm_v4 = read_frontmatter(tmp_path / "entities" / "interpretations" / "i-v4.md")
    assert fm_v4 is not None and fm_v4.get("status") in (None, "active")
```

Add this import at the top of the test file (next to `import yaml`):

```python
from science_tool.big_picture.frontmatter import read_frontmatter
```

- [ ] **Step 2: Run test to verify it fails or passes**

Run: `cd science && pytest tests/test_consolidation_mark_superseded.py::test_apply_sets_superseded_status_on_members -v`
Expected: PASS (the `_apply` implementation from Task 4 already does this). If it FAILS with an `EntityCommandError` about an unresolved ref, it means `find_entity` could not resolve the id — verify the entity files carry a `title` (some write paths require it); the test includes `title`, which is sufficient.

- [ ] **Step 3: Commit**

```bash
git add science/tests/test_consolidation_mark_superseded.py
git commit -m "test(consolidation): prove --apply stamps superseded via edit_entity"
```

---

### Task 6: CLI command `science entities mark-superseded`

**Files:**
- Modify: `science/src/science_tool/cli.py` (add after the `entities_migrate_identifiers_command` at lines 261-269; mirror its structure)
- Test: `science/tests/test_consolidation_mark_superseded.py` (append)

- [ ] **Step 1: Write the failing CLI test**

Append to `science/tests/test_consolidation_mark_superseded.py`:

```python
def test_cli_mark_superseded_dry_run_emits_json(tmp_path: Path) -> None:
    import json

    from click.testing import CliRunner

    from science_tool.cli import main

    _seed(tmp_path)
    _write(tmp_path, "interpretations", "i-v3", {"id": "interpretation:i-v3", "type": "interpretation", "title": "v3"})
    _write(tmp_path, "interpretations", "i-v4", {"id": "interpretation:i-v4", "type": "interpretation", "title": "v4", "relations": [_supersedes("interpretation:i-v3")]})

    runner = CliRunner()
    result = runner.invoke(
        main, ["entities", "mark-superseded", "--project-root", str(tmp_path)]
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["applied"] == []  # dry run
    assert payload["to_mark"] == ["interpretation:i-v3"]

    # The dry run must not have mutated anything.
    fm = read_frontmatter(tmp_path / "entities" / "interpretations" / "i-v3.md")
    assert fm is not None and fm.get("status") in (None, "active")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && pytest tests/test_consolidation_mark_superseded.py::test_cli_mark_superseded_dry_run_emits_json -v`
Expected: FAIL — Click reports `No such command 'mark-superseded'` and a non-zero exit code.

- [ ] **Step 3: Implement the CLI command**

In `science/src/science_tool/cli.py`, immediately after the `entities_migrate_identifiers_command` function (ends at line 269), add:

```python
@entities_group.command("mark-superseded")
@click.option(
    "--project-root",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=Path("."),
    help="Project root (default: current directory).",
)
@click.option("--apply", "apply_changes", is_flag=True, default=False, help="Apply changes (default: dry-run report).")
def entities_mark_superseded_command(project_root: Path, apply_changes: bool) -> None:
    """Auto-derive `superseded` status from linear supersedes chains (report, then --apply)."""
    from science_tool.consolidation import mark_superseded

    report = mark_superseded(project_root, apply=apply_changes)
    click.echo(json.dumps(report, indent=2))
```

(`json`, `click`, and `Path` are already imported at the top of `cli.py`.)

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science && pytest tests/test_consolidation_mark_superseded.py -v`
Expected: PASS (all consolidation tests).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/cli.py science/tests/test_consolidation_mark_superseded.py
git commit -m "feat(consolidation): add 'science entities mark-superseded' report/apply command"
```

---

### Task 7: Filter hidden statuses in knowledge-gaps topic loading

**Files:**
- Modify: `science/src/science_tool/big_picture/knowledge_gaps.py:58-77` (`_load_topics`)
- Test: `science/tests/test_consolidation_mark_superseded.py` is for the command; create a focused test in `science/tests/test_status_visibility.py` is wrong scope — instead append to a knowledge-gaps test if one exists, else add a small standalone test here.

`_load_topics` feeds knowledge-gap demand computation; superseded topics should not count as live gaps. `topic` declares `superseded` in its vocab, so this is the one knowledge-gaps loader where hidden status can occur. `_load_papers` (papers use only `active`/`retired`) and `_compute_demand` (questions have no `superseded`) need no change in P1.

- [ ] **Step 1: Write the failing test**

Create `science/tests/test_knowledge_gaps_visibility.py`:

```python
"""Knowledge-gaps loaders honor default visibility (consolidation P1)."""

from __future__ import annotations

from pathlib import Path


def test_superseded_topic_is_excluded_from_topic_load(tmp_path: Path) -> None:
    (tmp_path / "entities" / "topics").mkdir(parents=True)
    (tmp_path / "science.yaml").write_text("name: kg\n")
    (tmp_path / "entities" / "topics" / "t01.md").write_text(
        '---\nid: "topic:t01"\ntype: "topic"\nstatus: "active"\n---\nlive.\n'
    )
    (tmp_path / "entities" / "topics" / "t02.md").write_text(
        '---\nid: "topic:t02"\ntype: "topic"\nstatus: "superseded"\n---\nold.\n'
    )

    from science_tool.big_picture.knowledge_gaps import _load_topics

    topics = _load_topics(tmp_path)
    assert "topic:t01" in topics
    assert "topic:t02" not in topics
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && pytest tests/test_knowledge_gaps_visibility.py -v`
Expected: FAIL on `assert "topic:t02" not in topics` (currently included).

- [ ] **Step 3: Implement the filter**

In `science/src/science_tool/big_picture/knowledge_gaps.py`, add to the imports (alongside the existing `science_tool` imports near the top of the file):

```python
from science_tool.entities import is_default_visible
```

In `_load_topics` (lines 58-77), after the `eid = fm.get("id")` / `if not eid: continue` guard and before the duplicate check, add a visibility guard. The loop becomes:

```python
        for md in sorted(root.glob("*.md")):
            fm = read_frontmatter(md) or {}
            eid = fm.get("id")
            if not eid:
                continue
            if not is_default_visible(fm.get("status")):
                continue
            if eid in topics:
                raise ValueError(f"Duplicate topic id {eid!r}: {origins[eid]} vs {md}")
            topics[eid] = fm
            origins[eid] = md
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science && pytest tests/test_knowledge_gaps_visibility.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/big_picture/knowledge_gaps.py science/tests/test_knowledge_gaps_visibility.py
git commit -m "feat(consolidation): hide superseded topics from knowledge-gaps demand"
```

---

### Task 8: Default-hidden filtering in `list_entities` + `--include-hidden` escape hatch

**Files:**
- Modify: `science/src/science_tool/entities.py:672-700` (`list_entities`)
- Modify: `science/src/science_tool/cli.py` (`entity_list` command, ~line 621)
- Test: `science/tests/test_entities.py` (append, next to the existing `test_list_entities_*` tests)

`list_entities` backs `science entities list` and the typed per-kind list commands (and the project index). Default-hiding here covers all of them at once. An explicit `--status` request must still return exact matches (including hidden ones), and `--include-hidden` is the escape hatch.

- [ ] **Step 1: Write the failing test**

Append to `science/tests/test_entities.py` (the file already imports `list_entities`, `seed_project`, `write_markdown_entity`):

```python
def test_list_entities_hides_superseded_by_default(tmp_path: Path) -> None:
    seed_project(tmp_path)
    write_markdown_entity(
        tmp_path,
        "entities/interpretations/0001-active.md",
        {"id": "interpretation:0001-active", "type": "interpretation", "title": "Active", "status": "active"},
    )
    write_markdown_entity(
        tmp_path,
        "entities/interpretations/0002-old.md",
        {"id": "interpretation:0002-old", "type": "interpretation", "title": "Old", "status": "superseded"},
    )

    ids = {row["id"] for row in list_entities(tmp_path)}
    assert "interpretation:0001-active" in ids
    assert "interpretation:0002-old" not in ids  # hidden by default

    all_ids = {row["id"] for row in list_entities(tmp_path, include_hidden=True)}
    assert "interpretation:0002-old" in all_ids


def test_list_entities_explicit_status_returns_hidden(tmp_path: Path) -> None:
    seed_project(tmp_path)
    write_markdown_entity(
        tmp_path,
        "entities/interpretations/0002-old.md",
        {"id": "interpretation:0002-old", "type": "interpretation", "title": "Old", "status": "superseded"},
    )
    # An explicit status request is honored even though the status is hidden.
    rows = list_entities(tmp_path, status="superseded")
    assert [row["id"] for row in rows] == ["interpretation:0002-old"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && pytest tests/test_entities.py::test_list_entities_hides_superseded_by_default tests/test_entities.py::test_list_entities_explicit_status_returns_hidden -v`
Expected: FAIL — first test fails (`interpretation:0002-old` currently listed; and `include_hidden=` is an unexpected keyword argument). The second test passes already but is included to lock in the explicit-status behavior across the change.

- [ ] **Step 3: Implement the filter**

In `science/src/science_tool/entities.py`, change the `list_entities` signature (line 678) to add `include_hidden`:

```python
def list_entities(
    project_root: Path,
    kind: str | None = None,
    status: str | None = None,
    related: str | None = None,
    *,
    include_hidden: bool = False,
) -> list[dict[str, str]]:
```

Then in the per-entity loop, replace this block:

```python
        entity_status = entity.status or ""
        if status is not None and entity_status != status:
            continue
```

with:

```python
        entity_status = entity.status or ""
        if status is not None:
            if entity_status != status:
                continue
        elif not include_hidden and not is_default_visible(entity.status):
            continue
```

(`is_default_visible` is defined in this same module — no import needed.)

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science && pytest tests/test_entities.py -k list_entities -v`
Expected: PASS (all four `list_entities` tests, including the two new ones).

- [ ] **Step 5: Add the CLI escape hatch + a CLI test**

In `science/src/science_tool/cli.py`, update the `entity_list` command (~line 621). Add the option decorator and thread the flag:

```python
@entity_group.command("list")
@click.option("--kind")
@click.option("--status")
@click.option("--related")
@click.option("--include-hidden", is_flag=True, default=False, help="Include superseded/archived entities (hidden by default).")
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
def entity_list(kind: str | None, status: str | None, related: str | None, include_hidden: bool, output_format: str) -> None:
    """List source-authored entities."""

    try:
        rows = list_entities(Path.cwd(), kind=kind, status=status, related=related, include_hidden=include_hidden)
    except EntityCommandError as exc:
        raise click.ClickException(str(exc)) from exc
```

(Leave the rest of `entity_list` unchanged.) Note: the typed per-kind list commands (`_list_typed_entities`) call `list_entities` without `include_hidden`, so they now hide superseded/archived by default for free; adding a per-typed-command `--include-hidden` flag is a trivial follow-up, deferred and noted here.

Append a CLI test to `science/tests/test_entities.py`:

```python
def test_cli_entities_list_include_hidden_flag(tmp_path: Path, monkeypatch) -> None:
    import json

    from click.testing import CliRunner

    from science_tool.cli import main

    seed_project(tmp_path)
    write_markdown_entity(
        tmp_path,
        "entities/interpretations/0002-old.md",
        {"id": "interpretation:0002-old", "type": "interpretation", "title": "Old", "status": "superseded"},
    )
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()

    default = runner.invoke(main, ["entities", "list", "--format", "json"])
    assert default.exit_code == 0, default.output
    assert "interpretation:0002-old" not in default.output

    shown = runner.invoke(main, ["entities", "list", "--include-hidden", "--format", "json"])
    assert shown.exit_code == 0, shown.output
    assert "interpretation:0002-old" in shown.output
```

- [ ] **Step 6: Run the CLI test**

Run: `cd science && pytest tests/test_entities.py::test_cli_entities_list_include_hidden_flag -v`
Expected: PASS. (If `--format json` is not a valid choice for this command, inspect `OUTPUT_FORMATS` and use a supported value such as `table`, asserting on substring presence/absence in the table output instead.)

- [ ] **Step 7: Commit**

```bash
git add science/src/science_tool/entities.py science/src/science_tool/cli.py science/tests/test_entities.py
git commit -m "feat(consolidation): hide superseded/archived from entities list (--include-hidden to show)"
```

---

### Task 9: Full-suite regression gate

**Files:** none (verification only)

- [ ] **Step 1: Run the full default suite**

Run: `cd science && pytest`
Expected: PASS — the default config excludes `snapshot`/`real_projects`. Confirm no existing big-picture/entities tests regressed from the resolver and knowledge-gaps filters. Pay attention to fixture-backed big-picture tests under `tests/fixtures/big_picture/` — if any fixture entity carries `status: superseded`/`archived` and a test asserted it appears, that test now needs updating (the new behavior is correct; adjust the assertion and note it in the commit).

- [ ] **Step 2: Run the model suite**

Run: `cd science/model && pytest` (if `science/model` has its own test config) — otherwise the root `pytest` already covered `tests/`. Confirm the descriptor parity tests in `science/tests/test_kind_map_equivalence.py` still pass unchanged (P1 deliberately did not touch status vocabularies).

- [ ] **Step 3: Commit any test adjustments**

```bash
git add -A
git commit -m "test(consolidation): adjust fixtures/assertions for default lifecycle visibility"
```

(Skip this commit if Step 1 produced no changes.)

---

## Self-review

**Spec coverage (design §10 P1):**
- "Tier 1 visibility predicate" → Task 1 (`is_default_visible` + sets).
- "hidden-set-disjoint guard test" → Task 2 (made implementable as two guards: hidden∉default; every declared status classified; plus disjointness).
- "default-hidden filtering in entity consumers" → Task 3 (resolver / bundle assembly), Task 7 (knowledge-gaps topics), Task 8 (`list_entities` → `entities list` + typed lists, with `--include-hidden`). Lookup/`find_entity`, the nonexistent-ref known-id set, and KG ingestion deliberately excluded (Scope #3). `attention`/`next-steps` (graph-layer) and `entities inventory`/`build_inventory` (P2 curate surface) deferred — documented, not silently dropped.
- "auto-derive superseded from linear chains (report-then-apply)" → Tasks 4–6. The scan reads the **canonical** `relations:` entries with `predicate: "sci:supersedes"` (not a top-level `supersedes:` field, not `sci:amends`); non-linear chains are reported-and-skipped; members whose kind lacks a `superseded` vocab (`workflow-run`/`story`/`validation-report`) are reported under `skipped_kinds` rather than crashing.
- "CORE_PROFILE status-vocab updates (archived; superseded where missing)" → intentionally deferred (Scope #1/#2): nothing in P1 sets `archived`; supersedes-eligible conclusion kinds already have `superseded`; status-less supersedes-eligible kinds are skipped rather than given new vocab. Documented.

**Placeholder scan:** No TBD/TODO; every code step shows full code; every command has an expected result.

**Type consistency:** `is_default_visible(status: str | None) -> bool` used identically in resolver, knowledge_gaps, and `list_entities`. `mark_superseded(project_root, *, apply) -> dict` keys (`chains`, `non_linear`, `to_mark`, `applied`, `skipped_kinds`) consistent across Tasks 4–6, the CLI test, and the skipped-kind test. The supersedes edge is read via `_supersedes_targets(fm)` (relations/predicate), and `_supports_superseded(kind)` checks built-in `_STATUS_VALUES` membership directly (no `valid_statuses` call), so status-less eligible kinds and all local kinds are skipped — never crashed — at report time, keeping auto-apply on built-in policy-backed kinds only. `edit_entity(project_root, ref, *, status=...)` matches its verified signature. `_load_entities(directory, *, include_hidden=False)` and `list_entities(..., *, include_hidden=False)` consistent between implementation and tests. Test fixtures author supersession only via `relations: [{"predicate": "sci:supersedes", "target": ...}]`.

# P1 — Source-agnostic core (SourceAdapter) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce a `SourceAdapter` abstraction (capability profile + registry) and re-seat
the paper annotation pipeline as `PaperSourceAdapter`, so the text→graph machinery is
source-agnostic — with **zero behavior change** for papers.

**Architecture:** A new `annotation/source_adapter.py` declares a `LocatorRegime` enum and a
`SourceAdapter` ABC mirroring the existing `StorageAdapter` "declared-policy, no-isinstance"
pattern. `PaperSourceAdapter` captures today's two source-coupled seams — the `paper:<citekey>`
**source-ref scheme** (used by `promote`) and the **offset-anchored locator/extract path**
(used by `extract`) — by delegating to the existing functions. The `extract` and `promote` CLI
commands resolve their adapter from a registry and call through it. `fetch`/`seed` are *declared*
capabilities (for P2's dispatch) but `persist-source`/`pubtator` remain paper-specific in P1.

**Tech Stack:** Python 3, `click` CLI, `pytest`. No new third-party deps.

---

## Scope, decisions locked, and the one refinement to confirm

This plan implements **only P1** from the umbrella
(`docs/plans/2026-06-17-prose-epistemics-umbrella-design.md`). P2–P4 and the natural-systems
plan are separate.

**Locked design decisions (the umbrella deferred these to "the P1 spec"; this plan IS that spec):**

1. **Where it lives:** one new module `science/src/science_tool/annotation/source_adapter.py`
   (all annotation source-side commands already live under `annotation/`).
2. **Interface shape:** `SourceAdapter` mirrors `StorageAdapter`
   (`graph/storage_adapters/base.py`) — capabilities are **class attributes** (`name`,
   `locator_regime`, `can_fetch`, `can_seed`) and **polymorphic methods** (`handles`,
   `source_ref`, `extract`); dispatch is a registry list + first-match, **no `isinstance`/name
   branching**.
3. **Registry + dispatch:** a module-level `SOURCE_ADAPTERS: list[SourceAdapter]` and
   `resolve_adapter(source_md) -> SourceAdapter` (first whose `handles()` is True; fail-loud
   otherwise) — the same shape as the `adapters: list[StorageAdapter]` loop in
   `graph/sources.py`.
4. **Source-ref resolvability (umbrella §4.1):** in P1 the only adapter is `PaperSourceAdapter`,
   whose `source_ref` returns `paper:<citekey>` — already resolvable to the existing paper
   entity. No new source-entity machinery is built here; the *contract* (an adapter guarantees
   its ref resolves) is declared, and P2's `InternalProseAdapter` will satisfy it by
   mint-or-linking a source entity.

**⚠️ Refinement to confirm before implementing — narrows the umbrella's P1 wording.**
The umbrella P1 row says "generalize the locator/annotation artifact to support
offset-anchored *and* regenerable regimes." On contact with the code, the YAGNI-correct split
is: **P1 delivers the polymorphic interface that admits both regimes** (`SourceAdapter.extract`
+ the `LocatorRegime` enum), with `offset_anchored` fully implemented (delegating to today's
`extract_candidates`) and `regenerable`/`none` **declared but unimplemented** (the base
`extract` raises `NotImplementedError`). The regenerable *planner and its sidecar
representation* are P2 work — there is no consumer in P1, and the regenerable sidecar schema is
a genuine P2 design question. If you want P1 to instead build a speculative regenerable artifact
now, stop and revise this plan; otherwise the tasks below proceed on the interface-only reading.

**Behavior-neutral contract (the safety net):** the full existing annotation suite must pass
**unchanged** after every task —
`test_annotate_extract_cli.py`, `test_annotate_promote_cli.py`, `test_annotate_cli.py`,
`test_annotation_*.py`. No existing test file is edited by this plan.

## File structure

| File | Responsibility | Action |
|---|---|---|
| `science/src/science_tool/annotation/source_adapter.py` | `LocatorRegime`, `SourceAdapter` ABC, `PaperSourceAdapter`, `SOURCE_ADAPTERS`, `resolve_adapter`, `SourceAdapterError` | **Create** |
| `science/src/science_tool/annotation/cli.py` | `promote_cmd` derives `paper_ref` via the adapter; `extract_cmd` extracts via the adapter | **Modify** (`promote_cmd` ~1180-1183; `extract_cmd` ~1119-1125) |
| `science/tests/test_source_adapter.py` | Unit tests for the adapter, registry, and behavior-neutral re-wiring | **Create** |

## Running tests (worktree gotcha)

Run from the worktree root `/mnt/ssd/Dropbox/science/.worktrees/prose-epistemics`. `PYTHONPATH`
**must** list the worktree's `science/src` and `science/model/src` first — `science_model` is
editable-installed from the main checkout and otherwise shadows worktree edits:

```bash
PYTHONPATH=science/src:science/model/src ~/d/science/science/.venv/bin/pytest -q <targets>
```

---

## Task 1: `LocatorRegime` enum

**Files:**
- Create: `science/src/science_tool/annotation/source_adapter.py`
- Test: `science/tests/test_source_adapter.py`

- [ ] **Step 1: Write the failing test**

```python
# science/tests/test_source_adapter.py
from science_tool.annotation.source_adapter import LocatorRegime


def test_locator_regime_values():
    assert {r.value for r in LocatorRegime} == {
        "offset_anchored",
        "regenerable",
        "none",
    }
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=science/src:science/model/src ~/d/science/science/.venv/bin/pytest -q science/tests/test_source_adapter.py::test_locator_regime_values`
Expected: FAIL — `ModuleNotFoundError: No module named 'science_tool.annotation.source_adapter'`

- [ ] **Step 3: Write minimal implementation**

```python
# science/src/science_tool/annotation/source_adapter.py
"""Source adapters — turn a specific kind of text source into source-neutral
annotation candidates (the text-layer side of the prose-epistemics seam).

Mirrors the StorageAdapter "declared-policy, no-isinstance" pattern
(graph/storage_adapters/base.py): capabilities are class attributes and
polymorphic methods; dispatch is a registry list + first-match.
"""

from __future__ import annotations

from enum import Enum


class LocatorRegime(Enum):
    """How an adapter locates spans in its source.

    - OFFSET_ANCHORED: oa:TextQuoteSelector + offsets + content-hash re-audit
      (the "anchoring stack"); for immutable sources (papers, books).
    - REGENERABLE: cheap heading/section + quoted-text locators, no offset/hash
      machinery; for mutable internal prose (arrives in P2).
    - NONE: candidates carry no span provenance.
    """

    OFFSET_ANCHORED = "offset_anchored"
    REGENERABLE = "regenerable"
    NONE = "none"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=science/src:science/model/src ~/d/science/science/.venv/bin/pytest -q science/tests/test_source_adapter.py::test_locator_regime_values`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/annotation/source_adapter.py science/tests/test_source_adapter.py
git commit -m "feat(source-adapter): add LocatorRegime enum"
```

---

## Task 2: `SourceAdapter` ABC + capability profile

**Files:**
- Modify: `science/src/science_tool/annotation/source_adapter.py`
- Test: `science/tests/test_source_adapter.py`

- [ ] **Step 1: Write the failing test**

```python
# append to science/tests/test_source_adapter.py
from pathlib import Path
import pytest
from science_tool.annotation.source_adapter import SourceAdapter, LocatorRegime


class _DummyAdapter(SourceAdapter):
    name = "dummy"
    locator_regime = LocatorRegime.NONE

    def handles(self, source_md: Path) -> bool:
        return source_md.name == "dummy.md"

    def source_ref(self, source_md: Path) -> str:
        return "doc:dummy"


def test_capability_defaults_are_false():
    a = _DummyAdapter()
    assert a.can_fetch is False
    assert a.can_seed is False
    assert a.name == "dummy"
    assert a.locator_regime is LocatorRegime.NONE


def test_handles_and_source_ref_dispatch():
    a = _DummyAdapter()
    assert a.handles(Path("dummy.md")) is True
    assert a.handles(Path("other.md")) is False
    assert a.source_ref(Path("dummy.md")) == "doc:dummy"


def test_base_extract_raises_not_implemented():
    a = _DummyAdapter()
    with pytest.raises(NotImplementedError, match="does not implement extract"):
        a.extract(
            source_md=Path("dummy.md"),
            model="m",
            candidates=[],
            now=None,
            actor="t",
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=science/src:science/model/src ~/d/science/science/.venv/bin/pytest -q science/tests/test_source_adapter.py -k "capability or dispatch or base_extract"`
Expected: FAIL — `ImportError: cannot import name 'SourceAdapter'`

- [ ] **Step 3: Write minimal implementation**

Append to `source_adapter.py` (after the `LocatorRegime` enum; add the two imports at the top of the file):

```python
# add to the top-of-file imports
from abc import ABC
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from science_tool.annotation.statement_extract import (
        ExtractReport,
        FigurativeCandidate,
        StatementCandidate,
    )
```

```python
# append after LocatorRegime
class SourceAdapter(ABC):
    """Turn one kind of text source into source-neutral annotation candidates.

    Subclasses MUST override `handles()` and `source_ref()`, and SHOULD override
    `extract()` for whatever locator regime they declare. Capabilities are
    declared as class attributes so the CLI reads them instead of branching on
    adapter type (mirrors StorageAdapter, Spec 3 Slice A).
    """

    name: str  # human-readable adapter name
    locator_regime: LocatorRegime

    # Declared capabilities. P1 dispatches `extract`/`source_ref` through the
    # adapter; `fetch`/`seed` are declared for P2 (persist-source / pubtator stay
    # paper-specific until a second source needs them).
    can_fetch: bool = False
    can_seed: bool = False

    def handles(self, source_md: Path) -> bool:
        """Return True if this adapter owns `source_md`."""
        raise NotImplementedError

    def source_ref(self, source_md: Path) -> str:
        """The resolvable provenance ref recorded in minted entities' source_refs.

        The adapter guarantees this ref resolves to a materializable entity
        (umbrella §4.1).
        """
        raise NotImplementedError

    def extract(
        self,
        *,
        source_md: Path,
        model: str,
        candidates: "list[StatementCandidate | FigurativeCandidate]",
        now: datetime,
        actor: str,
    ) -> "ExtractReport":
        """Persist agent-extracted candidates as located annotations.

        Base raises: an adapter must implement extraction for its regime.
        """
        raise NotImplementedError(
            f"adapter {self.name!r} does not implement extract "
            f"(locator_regime={self.locator_regime.value})"
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=science/src:science/model/src ~/d/science/science/.venv/bin/pytest -q science/tests/test_source_adapter.py -k "capability or dispatch or base_extract"`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/annotation/source_adapter.py science/tests/test_source_adapter.py
git commit -m "feat(source-adapter): add SourceAdapter ABC with declared capabilities"
```

---

## Task 3: `PaperSourceAdapter`

**Files:**
- Modify: `science/src/science_tool/annotation/source_adapter.py`
- Test: `science/tests/test_source_adapter.py`

The `source_ref` logic is moved **verbatim** from `promote_cmd` (`cli.py:1180-1183`):
`citekey = name[:-len(".source.md")] if name.endswith(".source.md") else stem`, then
`paper:<citekey>`.

- [ ] **Step 1: Write the failing test**

```python
# append to science/tests/test_source_adapter.py
from science_tool.annotation.source_adapter import PaperSourceAdapter


def test_paper_adapter_capabilities():
    a = PaperSourceAdapter()
    assert a.name == "paper"
    assert a.locator_regime is LocatorRegime.OFFSET_ANCHORED
    assert a.can_fetch is True
    assert a.can_seed is True


def test_paper_adapter_handles_source_md():
    a = PaperSourceAdapter()
    assert a.handles(Path("/x/smith2020.source.md")) is True
    assert a.handles(Path("/x/smith2020.v1.source.md")) is True
    assert a.handles(Path("/x/notes.md")) is False


def test_paper_adapter_source_ref_matches_legacy_derivation():
    a = PaperSourceAdapter()
    # legacy promote_cmd behavior: strip ".source.md", else .stem
    assert a.source_ref(Path("/x/smith2020.source.md")) == "paper:smith2020"
    assert a.source_ref(Path("/x/smith2020.v1.source.md")) == "paper:smith2020.v1"
    assert a.source_ref(Path("/x/plain.md")) == "paper:plain"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=science/src:science/model/src ~/d/science/science/.venv/bin/pytest -q science/tests/test_source_adapter.py -k "paper_adapter"`
Expected: FAIL — `ImportError: cannot import name 'PaperSourceAdapter'`

- [ ] **Step 3: Write minimal implementation**

Append to `source_adapter.py`:

```python
_SOURCE_MD_SUFFIX = ".source.md"


class PaperSourceAdapter(SourceAdapter):
    """The shipped paper pipeline as a SourceAdapter — behavior-neutral.

    Sources are `<citekey>.source.md`; locators are offset-anchored
    (oa:TextQuoteSelector); the provenance ref is `paper:<citekey>`, resolvable
    to the existing paper entity persist-source already resolved.
    """

    name = "paper"
    locator_regime = LocatorRegime.OFFSET_ANCHORED
    can_fetch = True
    can_seed = True

    def handles(self, source_md: Path) -> bool:
        return source_md.name.endswith(_SOURCE_MD_SUFFIX)

    def source_ref(self, source_md: Path) -> str:
        name = source_md.name
        citekey = (
            name[: -len(_SOURCE_MD_SUFFIX)]
            if name.endswith(_SOURCE_MD_SUFFIX)
            else source_md.stem
        )
        return f"paper:{citekey}"

    def extract(
        self,
        *,
        source_md: Path,
        model: str,
        candidates: "list[StatementCandidate | FigurativeCandidate]",
        now: datetime,
        actor: str,
    ) -> "ExtractReport":
        # Delegate to the offset-anchored implementation; behavior-neutral.
        from science_tool.annotation.statement_extract import extract_candidates

        return extract_candidates(
            source_md=source_md,
            model=model,
            candidates=candidates,
            now=now,
            actor=actor,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=science/src:science/model/src ~/d/science/science/.venv/bin/pytest -q science/tests/test_source_adapter.py -k "paper_adapter"`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/annotation/source_adapter.py science/tests/test_source_adapter.py
git commit -m "feat(source-adapter): add PaperSourceAdapter (behavior-neutral paper seams)"
```

---

## Task 4: registry + `resolve_adapter`

**Files:**
- Modify: `science/src/science_tool/annotation/source_adapter.py`
- Test: `science/tests/test_source_adapter.py`

- [ ] **Step 1: Write the failing test**

```python
# append to science/tests/test_source_adapter.py
from science_tool.annotation.source_adapter import (
    SOURCE_ADAPTERS,
    SourceAdapterError,
    resolve_adapter,
)


def test_registry_contains_paper_adapter():
    assert any(isinstance(a, PaperSourceAdapter) for a in SOURCE_ADAPTERS)


def test_resolve_adapter_returns_paper_for_source_md():
    adapter = resolve_adapter(Path("/x/smith2020.source.md"))
    assert isinstance(adapter, PaperSourceAdapter)


def test_resolve_adapter_fails_loud_when_unhandled():
    with pytest.raises(SourceAdapterError, match="no source adapter handles"):
        resolve_adapter(Path("/x/unknown.txt"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=science/src:science/model/src ~/d/science/science/.venv/bin/pytest -q science/tests/test_source_adapter.py -k "registry or resolve_adapter"`
Expected: FAIL — `ImportError: cannot import name 'resolve_adapter'`

- [ ] **Step 3: Write minimal implementation**

Append to `source_adapter.py`:

```python
class SourceAdapterError(ValueError):
    """Raised when no adapter handles a source (fail-loud)."""


# Ordered registry; first match wins (mirrors graph/sources.py adapter list).
SOURCE_ADAPTERS: list[SourceAdapter] = [PaperSourceAdapter()]


def resolve_adapter(source_md: Path) -> SourceAdapter:
    """Return the first registered adapter that handles `source_md`."""
    for adapter in SOURCE_ADAPTERS:
        if adapter.handles(source_md):
            return adapter
    raise SourceAdapterError(f"no source adapter handles {source_md}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=science/src:science/model/src ~/d/science/science/.venv/bin/pytest -q science/tests/test_source_adapter.py -k "registry or resolve_adapter"`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/annotation/source_adapter.py science/tests/test_source_adapter.py
git commit -m "feat(source-adapter): add registry + resolve_adapter (fail-loud)"
```

---

## Task 5: route `promote_cmd` source-ref through the adapter

**Files:**
- Modify: `science/src/science_tool/annotation/cli.py:1166-1183` (`promote_cmd`)
- Test: `science/tests/test_source_adapter.py`

Replace the inline `paper:` derivation with the adapter's `source_ref`. **Behavior-neutral**:
`PaperSourceAdapter.source_ref` returns the identical string for `.source.md` inputs.

This is a **behavior-neutral refactor guarded by the existing suite**, not new-behavior TDD —
`source_ref` parity is already unit-tested in Task 3, and `test_annotate_promote_cli.py` already
exercises promote both with and without `--paper-ref`. So the discipline here is
baseline-green → edit → still-green, plus one unit test that `promote_cmd` actually routes
through `resolve_adapter` (so the seam can't silently regress to the inline string).

- [ ] **Step 1: Record the baseline (existing suite is the spec)**

Run: `PYTHONPATH=science/src:science/model/src ~/d/science/science/.venv/bin/pytest -q science/tests/test_annotate_promote_cli.py`
Expected: PASS (all existing promote tests). This green run is the behavior-neutral baseline the
edit must preserve.

- [ ] **Step 2: Write the seam-guard test**

```python
# append to science/tests/test_source_adapter.py
import science_tool.annotation.source_adapter as sa


def test_promote_cmd_routes_through_resolve_adapter(monkeypatch):
    """promote_cmd must derive its default ref via resolve_adapter, not inline."""
    calls = {}
    real_resolve = sa.resolve_adapter

    def spy_resolve(source_md):
        calls["source_md"] = source_md
        return real_resolve(source_md)

    monkeypatch.setattr(sa, "resolve_adapter", spy_resolve)

    from click.testing import CliRunner
    from science_tool.annotation.cli import annotate_group

    # A nonexistent .source.md: click rejects the path arg before promote logic,
    # OR promote runs and calls resolve_adapter. We only assert the seam is wired:
    # invoke read-only against any existing promote fixture is heavier than needed,
    # so assert at import-edge — resolve_adapter is imported into cli at call time.
    # Minimal proof: the symbol promote_cmd imports is sa.resolve_adapter.
    import inspect
    src = inspect.getsource(annotate_group.commands["promote"].callback)
    assert "resolve_adapter(source_md)" in src
    assert "adapter.source_ref(source_md)" in src
```

> Implementer note: the `inspect.getsource` assertion is a lightweight guard that the inline
> derivation was actually replaced by the adapter call (it would fail today, pass after Step 3).
> The real integration guarantee is the unchanged `test_annotate_promote_cli.py` suite in Step 4.
> If you prefer a stronger behavioral test, copy the fixture from
> `test_annotate_promote_cli.py::test_promote_apply_mints_and_backlinks`, drop `--paper-ref`, and
> assert the minted entity body contains `paper:<citekey>` — but do not invent a new fixture from
> scratch; reuse that file's existing helper verbatim.

- [ ] **Step 3: Run the guard test to verify it fails**

Run: `PYTHONPATH=science/src:science/model/src ~/d/science/science/.venv/bin/pytest -q science/tests/test_source_adapter.py -k "routes_through_resolve_adapter"`
Expected: FAIL — the source still contains the inline `citekey = ...` derivation, not
`resolve_adapter(source_md)`.

- [ ] **Step 4: Write the implementation**

In `cli.py`, add to `promote_cmd`'s local imports (the block at lines 1169-1174):

```python
    from science_tool.annotation.source_adapter import resolve_adapter
```

Replace the current default-derivation block (`cli.py:1180-1183`):

```python
    if paper_ref is None:
        # citekey = <citekey>.source.md → <citekey>; the owning paper entity is paper:<citekey>.
        citekey = source_md.name[: -len(".source.md")] if source_md.name.endswith(".source.md") else source_md.stem
        paper_ref = f"paper:{citekey}"
```

with:

```python
    adapter = resolve_adapter(source_md)
    if paper_ref is None:
        paper_ref = adapter.source_ref(source_md)
```

- [ ] **Step 5: Run guard + full promote suite to verify green**

Run: `PYTHONPATH=science/src:science/model/src ~/d/science/science/.venv/bin/pytest -q science/tests/test_source_adapter.py -k "routes_through_resolve_adapter" science/tests/test_annotate_promote_cli.py`
Expected: PASS (the guard test now passes, and **all** existing promote tests are unchanged-green)

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/annotation/cli.py science/tests/test_source_adapter.py
git commit -m "refactor(promote): derive source ref via resolve_adapter (behavior-neutral)"
```

---

## Task 6: route `extract_cmd` through the adapter

**Files:**
- Modify: `science/src/science_tool/annotation/cli.py:1119-1125` (`extract_cmd`)
- Test: `science/tests/test_source_adapter.py`

Replace the direct `extract_candidates(...)` call with `resolve_adapter(source_md).extract(...)`.
**Behavior-neutral**: `PaperSourceAdapter.extract` delegates to the same `extract_candidates`.
Like Task 5, this is a refactor guarded by the existing `test_annotate_extract_cli.py` suite,
plus two new guards: a delegation unit test and a CLI seam test.

- [ ] **Step 1: Record the baseline**

Run: `PYTHONPATH=science/src:science/model/src ~/d/science/science/.venv/bin/pytest -q science/tests/test_annotate_extract_cli.py`
Expected: PASS (all existing extract tests) — the behavior-neutral baseline.

- [ ] **Step 2: Write the delegation + seam guard tests**

The delegation test proves `PaperSourceAdapter.extract` forwards identical kwargs to
`extract_candidates` (so it already passes after Task 3); the seam test proves `extract_cmd` was
re-wired to call the adapter (fails until Step 4).

```python
# append to science/tests/test_source_adapter.py
def test_paper_adapter_extract_delegates(monkeypatch):
    import science_tool.annotation.statement_extract as se

    captured = {}

    def fake_extract_candidates(*, source_md, model, candidates, now, actor):
        captured.update(
            source_md=source_md, model=model, candidates=candidates, now=now, actor=actor
        )
        return "SENTINEL_REPORT"

    monkeypatch.setattr(se, "extract_candidates", fake_extract_candidates)

    now = datetime.now(timezone.utc)
    out = PaperSourceAdapter().extract(
        source_md=Path("/x/p.source.md"), model="m", candidates=[], now=now, actor="paper-annotate"
    )
    assert out == "SENTINEL_REPORT"
    assert captured == {
        "source_md": Path("/x/p.source.md"),
        "model": "m",
        "candidates": [],
        "now": now,
        "actor": "paper-annotate",
    }


def test_extract_cmd_routes_through_resolve_adapter():
    import inspect
    from science_tool.annotation.cli import annotate_group

    src = inspect.getsource(annotate_group.commands["extract"].callback)
    assert "resolve_adapter(source_md)" in src
    assert "adapter.extract(" in src
```

- [ ] **Step 3: Run the new tests — delegation passes, seam fails**

Run: `PYTHONPATH=science/src:science/model/src ~/d/science/science/.venv/bin/pytest -q science/tests/test_source_adapter.py -k "extract_delegates or extract_cmd_routes"`
Expected: `extract_delegates` PASSES (Task 3 already implemented `extract`); `extract_cmd_routes`
FAILS (the CLI still calls `extract_candidates` directly). If `extract_delegates` fails, the
Task-3 `extract` method is wrong — fix it before proceeding.

- [ ] **Step 4: Write the implementation**

In `cli.py` `extract_cmd`, after `candidates = parse_candidates(...)` succeeds, replace the
extract call block (`cli.py:1119-1125`):

```python
    try:
        report = extract_candidates(
            source_md=source_md, model=model, candidates=candidates,
            now=datetime.now(timezone.utc), actor=actor,
        )
    except SourceTextError as exc:
        raise click.ClickException(str(exc)) from exc
```

with:

```python
    from science_tool.annotation.source_adapter import resolve_adapter

    adapter = resolve_adapter(source_md)
    try:
        report = adapter.extract(
            source_md=source_md, model=model, candidates=candidates,
            now=datetime.now(timezone.utc), actor=actor,
        )
    except SourceTextError as exc:
        raise click.ClickException(str(exc)) from exc
```

(The `extract_candidates` import in `extract_cmd`'s local import block at lines 1095-1100 may
remain; it is still used for the `check_source_changed`/`parse_candidates` siblings. Leaving an
unused import is acceptable but prefer dropping `extract_candidates` from that block since the
adapter now owns the call. `check_source_changed` and `parse_candidates` stay.)

- [ ] **Step 5: Run guards + full extract suite to verify green**

Run: `PYTHONPATH=science/src:science/model/src ~/d/science/science/.venv/bin/pytest -q science/tests/test_source_adapter.py -k "extract_delegates or extract_cmd_routes" science/tests/test_annotate_extract_cli.py`
Expected: PASS (both guard tests now pass + **all** existing extract CLI tests unchanged-green)

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/annotation/cli.py science/tests/test_source_adapter.py
git commit -m "refactor(extract): extract via resolve_adapter (behavior-neutral)"
```

---

## Task 7: full-suite behavior-neutrality gate + module docstring

**Files:**
- Modify: `science/src/science_tool/annotation/source_adapter.py` (docstring only, if needed)
- Test: (no new test — this is the regression gate)

- [ ] **Step 1: Run the full annotation suite**

Run:
```bash
PYTHONPATH=science/src:science/model/src ~/d/science/science/.venv/bin/pytest -q \
  science/tests/test_annotate_extract_cli.py \
  science/tests/test_annotate_promote_cli.py \
  science/tests/test_annotate_cli.py \
  science/tests/test_annotate_audit_cli.py \
  science/tests/test_annotate_list_cli.py \
  science/tests/test_annotate_stats_cli.py \
  science/tests/test_annotate_ack_dismiss_fix_cli.py \
  science/tests/test_annotate_lift_tokens_cli.py \
  science/tests/test_annotate_p33_integration.py \
  science/tests/test_annotation_model.py \
  science/tests/test_annotation_io.py \
  science/tests/test_annotation_promote.py \
  science/tests/test_source_adapter.py
```
Expected: ALL PASS, zero failures. This is the behavior-neutral proof.

- [ ] **Step 2: If any existing test changed behavior, STOP and fix the wiring**

Do not edit existing test files to make them pass. A failure here means the re-wiring is not
behavior-neutral — revert to the offending task and correct the delegation.

- [ ] **Step 3: Confirm the module docstring states the P1/P2 boundary**

Ensure `source_adapter.py`'s top docstring notes: `offset_anchored` implemented; `regenerable`
declared-but-unimplemented until P2; `fetch`/`seed` declared but `persist-source`/`pubtator`
remain paper-specific in P1.

- [ ] **Step 4: Commit (if the docstring changed)**

```bash
git add science/src/science_tool/annotation/source_adapter.py
git commit -m "docs(source-adapter): record P1/P2 regime + capability boundary"
```

---

## Self-review checklist (run after implementation, before finishing the branch)

1. **Behavior-neutral:** the full annotation suite (Task 7) passes with **no edits** to existing
   test files.
2. **No isinstance dispatch:** `resolve_adapter` selects by `handles()`, not type checks; the CLI
   reads `adapter.locator_regime`/capabilities, never `isinstance`.
3. **Source-ref parity:** `PaperSourceAdapter.source_ref` returns byte-identical strings to the
   old inline derivation for every `.source.md` and fallback case (Task 3 tests).
4. **Seam completeness for P2:** `extract` and `source_ref` go through the adapter; `LocatorRegime`
   and `can_fetch`/`can_seed` are declared so P2's `InternalProseAdapter` is an additive change
   (new adapter + registry entry), touching no CLI command body.

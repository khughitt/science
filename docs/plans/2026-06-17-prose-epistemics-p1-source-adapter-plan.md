# P1 — Source-agnostic core (TextSourceAdapter) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce a `TextSourceAdapter` abstraction (capability profile + registry) and re-seat
the paper annotation pipeline as `PaperSourceAdapter`, so the text→graph machinery is
source-agnostic — with **zero behavior change** for papers.

**Architecture:** A new `annotation/text_source_adapter.py` declares a `LocatorRegime` enum and a
`TextSourceAdapter` ABC mirroring the existing `StorageAdapter` "declared-policy, no-isinstance"
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

1. **Where it lives:** one new module `science/src/science_tool/annotation/text_source_adapter.py`
   (all annotation source-side commands already live under `annotation/`).
2. **Interface shape:** `TextSourceAdapter` mirrors `StorageAdapter`
   (`graph/storage_adapters/base.py`) — capabilities are **class attributes** (`name`,
   `locator_regime`, `can_fetch`, `can_seed`) and **polymorphic methods** (`handles`,
   `source_ref`, `extract`); dispatch is a registry list + first-match, **no `isinstance`/name
   branching**.
3. **Registry + dispatch:** a module-level `TEXT_SOURCE_ADAPTERS: list[TextSourceAdapter]` and
   `resolve_adapter(source_md) -> TextSourceAdapter` (first whose `handles()` is True; fail-loud
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
is: **P1 delivers the polymorphic interface that admits both regimes** (`TextSourceAdapter.extract`
+ the `LocatorRegime` enum), with `offset_anchored` fully implemented (delegating to today's
`extract_candidates`) and `regenerable`/`none` **declared but unimplemented** (the base
`extract` raises `NotImplementedError`). The regenerable *planner and its sidecar
representation* are P2 work — there is no consumer in P1, and the regenerable sidecar schema is
a genuine P2 design question. If you want P1 to instead build a speculative regenerable artifact
now, stop and revise this plan; otherwise the tasks below proceed on the interface-only reading.

**What P1 does NOT make additive for P2 (honest scope).** P1 routes only the **`extract`** and
**`source_ref`** seams through the adapter. Two other paper-coupled paths remain untouched and
P2 will own extending them when `InternalProseAdapter` lands:
- **`--check` / source-change detection** (`extract_cmd` `check_source_changed`, `cli.py:1102`) is
  built on `.source.md` text-hash re-audit — meaningless for the `regenerable` regime, so P2 must
  add a regime-appropriate change-check (likely a new adapter method).
- **Promotion's sidecar read** (`promote_cmd` `sidecar_for_markdown` + `read_sidecar_strict`,
  `cli.py:1185`) assumes the offset-anchored `.anno.trig` shape; P2's regenerable artifact may
  need its own read path.

So P2 is **not** merely "new adapter + registry entry": it adds the regenerable locator artifact
*and* the `--check`/promotion wiring above. P1 deliberately does not pre-build those extension
points (YAGNI — no second source exists yet).

**Behavior-neutral contract (the safety net):** the full existing annotation suite must pass
**unchanged** after every task —
`test_annotate_extract_cli.py`, `test_annotate_promote_cli.py`, `test_annotate_cli.py`,
`test_annotation_*.py`. No existing test file is edited by this plan.

## File structure

| File | Responsibility | Action |
|---|---|---|
| `science/src/science_tool/annotation/text_source_adapter.py` | `LocatorRegime`, `TextSourceAdapter` ABC, `PaperSourceAdapter`, `TEXT_SOURCE_ADAPTERS`, `resolve_adapter`, `TextSourceAdapterError` | **Create** |
| `science/src/science_tool/annotation/cli.py` | `promote_cmd` derives `paper_ref` via the adapter; `extract_cmd` extracts via the adapter | **Modify** (`promote_cmd` ~1180-1183; `extract_cmd` ~1119-1125) |
| `science/tests/test_text_source_adapter.py` | Unit tests for the adapter, registry, and delegation | **Create** |
| `science/tests/test_annotate_promote_cli.py` | **Add** two runtime tests (default-ref + explicit-ref-bypass), reusing `_setup`. Existing tests untouched. | **Modify (append-only)** |
| `science/tests/test_annotate_extract_cli.py` | **Add** one runtime seam test, reusing `_make_source_md`. Existing tests untouched. | **Modify (append-only)** |

> "Behavior-neutral / no editing existing tests" means **existing test assertions are never
> changed**; appending *new* test functions to these files (reusing their fixtures) is allowed and
> is how the runtime seam tests get real fixtures without duplication.

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
- Create: `science/src/science_tool/annotation/text_source_adapter.py`
- Test: `science/tests/test_text_source_adapter.py`

- [ ] **Step 1: Write the failing test**

```python
# science/tests/test_text_source_adapter.py
from science_tool.annotation.text_source_adapter import LocatorRegime


def test_locator_regime_values():
    assert {r.value for r in LocatorRegime} == {
        "offset_anchored",
        "regenerable",
        "none",
    }
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=science/src:science/model/src ~/d/science/science/.venv/bin/pytest -q science/tests/test_text_source_adapter.py::test_locator_regime_values`
Expected: FAIL — `ModuleNotFoundError: No module named 'science_tool.annotation.text_source_adapter'`

- [ ] **Step 3: Write minimal implementation**

```python
# science/src/science_tool/annotation/text_source_adapter.py
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

Run: `PYTHONPATH=science/src:science/model/src ~/d/science/science/.venv/bin/pytest -q science/tests/test_text_source_adapter.py::test_locator_regime_values`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/annotation/text_source_adapter.py science/tests/test_text_source_adapter.py
git commit -m "feat(source-adapter): add LocatorRegime enum"
```

---

## Task 2: `TextSourceAdapter` ABC + capability profile

**Files:**
- Modify: `science/src/science_tool/annotation/text_source_adapter.py`
- Test: `science/tests/test_text_source_adapter.py`

- [ ] **Step 1: Write the failing test**

```python
# append to science/tests/test_text_source_adapter.py
from pathlib import Path
import pytest
from science_tool.annotation.text_source_adapter import TextSourceAdapter, LocatorRegime


class _DummyAdapter(TextSourceAdapter):
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

Run: `PYTHONPATH=science/src:science/model/src ~/d/science/science/.venv/bin/pytest -q science/tests/test_text_source_adapter.py -k "capability or dispatch or base_extract"`
Expected: FAIL — `ImportError: cannot import name 'TextSourceAdapter'`

- [ ] **Step 3: Write minimal implementation**

Append to `text_source_adapter.py` (after the `LocatorRegime` enum; add the two imports at the top of the file):

```python
# add to the top-of-file imports
from abc import ABC, abstractmethod
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

> **Naming note (intentional, do not "simplify" to `SourceAdapter`):** the audit subsystem
> already defines a *different* `SourceAdapter` Protocol in
> `science_tool/annotation/sources/base.py` (a per-file lint scanner that emits
> `PlannedAnnotation` rows). This class is a distinct concept — a *text source* (paper, book,
> internal prose) feeding the extract→promote pipeline — so it is named `TextSourceAdapter` to
> avoid two `SourceAdapter` names in the same package.

```python
# append after LocatorRegime
class TextSourceAdapter(ABC):
    """Turn one kind of text source into source-neutral annotation candidates.

    Distinct from the audit-subsystem `SourceAdapter` Protocol in
    `annotation/sources/base.py` (a lint scanner). This is the adapter for a *text
    source* (paper, book, internal prose) feeding the extract→promote pipeline.

    Subclasses MUST implement `handles()` and `source_ref()` (abstract), and SHOULD
    override `extract()` for whatever locator regime they declare. Capabilities are
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

    @abstractmethod
    def handles(self, source_md: Path) -> bool:
        """Return True if this adapter owns `source_md`."""
        raise NotImplementedError

    @abstractmethod
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

Run: `PYTHONPATH=science/src:science/model/src ~/d/science/science/.venv/bin/pytest -q science/tests/test_text_source_adapter.py -k "capability or dispatch or base_extract"`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/annotation/text_source_adapter.py science/tests/test_text_source_adapter.py
git commit -m "feat(source-adapter): add TextSourceAdapter ABC with declared capabilities"
```

---

## Task 3: `PaperSourceAdapter`

**Files:**
- Modify: `science/src/science_tool/annotation/text_source_adapter.py`
- Test: `science/tests/test_text_source_adapter.py`

The `source_ref` logic is moved **verbatim** from `promote_cmd` (`cli.py:1180-1183`):
`citekey = name[:-len(".source.md")] if name.endswith(".source.md") else stem`, then
`paper:<citekey>`.

- [ ] **Step 1: Write the failing test**

```python
# append to science/tests/test_text_source_adapter.py
from science_tool.annotation.text_source_adapter import PaperSourceAdapter


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


def test_paper_adapter_source_ref_strips_source_suffix():
    a = PaperSourceAdapter()
    assert a.source_ref(Path("/x/smith2020.source.md")) == "paper:smith2020"
    assert a.source_ref(Path("/x/smith2020.v1.source.md")) == "paper:smith2020.v1"


def test_paper_adapter_source_ref_rejects_non_source_md():
    # source_ref is only ever reached via resolve_adapter, which gates on handles();
    # so a non-.source.md path can never reach it in practice. The old `.stem`
    # fallback was therefore dead code — make the contract explicit and fail loud
    # (matches sidecar_for_markdown, which raises on a non-.md path).
    a = PaperSourceAdapter()
    with pytest.raises(ValueError, match=r"expects a \.source\.md path"):
        a.source_ref(Path("/x/plain.md"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=science/src:science/model/src ~/d/science/science/.venv/bin/pytest -q science/tests/test_text_source_adapter.py -k "paper_adapter"`
Expected: FAIL — `ImportError: cannot import name 'PaperSourceAdapter'`

- [ ] **Step 3: Write minimal implementation**

Append to `text_source_adapter.py`:

```python
_SOURCE_MD_SUFFIX = ".source.md"


class PaperSourceAdapter(TextSourceAdapter):
    """The shipped paper pipeline as a TextSourceAdapter — behavior-neutral.

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
        if not name.endswith(_SOURCE_MD_SUFFIX):
            raise ValueError(
                f"PaperSourceAdapter.source_ref expects a {_SOURCE_MD_SUFFIX} path: {source_md}"
            )
        return f"paper:{name[: -len(_SOURCE_MD_SUFFIX)]}"

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

Run: `PYTHONPATH=science/src:science/model/src ~/d/science/science/.venv/bin/pytest -q science/tests/test_text_source_adapter.py -k "paper_adapter"`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/annotation/text_source_adapter.py science/tests/test_text_source_adapter.py
git commit -m "feat(source-adapter): add PaperSourceAdapter (behavior-neutral paper seams)"
```

---

## Task 4: registry + `resolve_adapter`

**Files:**
- Modify: `science/src/science_tool/annotation/text_source_adapter.py`
- Test: `science/tests/test_text_source_adapter.py`

- [ ] **Step 1: Write the failing test**

```python
# append to science/tests/test_text_source_adapter.py
from science_tool.annotation.text_source_adapter import (
    TEXT_SOURCE_ADAPTERS,
    TextSourceAdapterError,
    resolve_adapter,
)


def test_registry_contains_paper_adapter():
    assert any(isinstance(a, PaperSourceAdapter) for a in TEXT_SOURCE_ADAPTERS)


def test_resolve_adapter_returns_paper_for_source_md():
    adapter = resolve_adapter(Path("/x/smith2020.source.md"))
    assert isinstance(adapter, PaperSourceAdapter)


def test_resolve_adapter_fails_loud_when_unhandled():
    with pytest.raises(TextSourceAdapterError, match="no text source adapter handles"):
        resolve_adapter(Path("/x/unknown.txt"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=science/src:science/model/src ~/d/science/science/.venv/bin/pytest -q science/tests/test_text_source_adapter.py -k "registry or resolve_adapter"`
Expected: FAIL — `ImportError: cannot import name 'resolve_adapter'`

- [ ] **Step 3: Write minimal implementation**

Append to `text_source_adapter.py`:

```python
class TextSourceAdapterError(ValueError):
    """Raised when no adapter handles a source (fail-loud)."""


# Ordered registry; first match wins (mirrors graph/sources.py adapter list).
TEXT_SOURCE_ADAPTERS: list[TextSourceAdapter] = [PaperSourceAdapter()]


def resolve_adapter(source_md: Path) -> TextSourceAdapter:
    """Return the first registered adapter that handles `source_md`."""
    for adapter in TEXT_SOURCE_ADAPTERS:
        if adapter.handles(source_md):
            return adapter
    raise TextSourceAdapterError(f"no text source adapter handles {source_md}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=science/src:science/model/src ~/d/science/science/.venv/bin/pytest -q science/tests/test_text_source_adapter.py -k "registry or resolve_adapter"`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/annotation/text_source_adapter.py science/tests/test_text_source_adapter.py
git commit -m "feat(source-adapter): add registry + resolve_adapter (fail-loud)"
```

---

## Task 5: route `promote_cmd` source-ref through the adapter

**Files:**
- Modify: `science/src/science_tool/annotation/cli.py:1166-1183` (`promote_cmd`)
- Test: `science/tests/test_annotate_promote_cli.py` (add new tests, reusing the existing `_setup` fixture)

This is a **behavior-neutral refactor guarded by the existing suite** plus two new *runtime*
tests that reuse the real `_setup` fixture in `test_annotate_promote_cli.py`. The discipline is
baseline-green → write runtime tests → edit → green.

**Critical detail (High-severity fix):** `resolve_adapter` must be called **only inside** the
`if paper_ref is None:` branch. `PaperSourceAdapter.handles()` rejects non-`.source.md` paths, so
resolving unconditionally would make an explicit `--paper-ref` on a non-`.source.md` source fail
before the ref is even used. Keeping the call inside the `None` branch means an explicit
`--paper-ref` never touches the adapter — fully behavior-neutral.

**Sanctioned deviation:** for the *no*-`--paper-ref` + *non*-`.source.md` case, the old code
silently derived `paper:<stem>`; the new code routes through `resolve_adapter`, which fails loud
(`TextSourceAdapterError`). No existing test exercises that case (every promote test uses
`p.source.md`), and fail-loud is the intended behavior (avoid silent fallbacks). Recorded here so
it is not mistaken for an accidental regression.

- [ ] **Step 1: Record the baseline (existing suite is the spec)**

Run: `PYTHONPATH=science/src:science/model/src ~/d/science/science/.venv/bin/pytest -q science/tests/test_annotate_promote_cli.py`
Expected: PASS (all existing promote tests). This green run is the behavior-neutral baseline the
edit must preserve.

- [ ] **Step 2: Write the runtime tests**

Append to `science/tests/test_annotate_promote_cli.py` (it already imports `CliRunner`,
`annotate_group`, `json`, `Path`, and defines `_setup`):

```python
def test_promote_apply_without_paper_ref_uses_adapter_default(tmp_path):
    # No --paper-ref: the default must come from PaperSourceAdapter.source_ref,
    # i.e. p.source.md -> paper:p, recorded in the minted proposition body.
    md, sp = _setup(tmp_path)
    r = CliRunner().invoke(annotate_group, ["promote", str(md), "--root", str(tmp_path), "--apply"])
    assert r.exit_code == 0, r.output
    text = (tmp_path / "entities" / "propositions" / "genes-encode-proteins.md").read_text(encoding="utf-8")
    assert "paper:p" in text


def test_promote_explicit_paper_ref_does_not_touch_adapter(tmp_path, monkeypatch):
    # An explicit --paper-ref must bypass resolve_adapter entirely (High-severity guard):
    # if the code wrongly resolves an adapter, this raises and the command fails.
    import science_tool.annotation.text_source_adapter as sa

    def boom(_source_md):
        raise sa.TextSourceAdapterError("resolve_adapter must not be called when --paper-ref is given")

    monkeypatch.setattr(sa, "resolve_adapter", boom)
    md, sp = _setup(tmp_path)
    r = CliRunner().invoke(annotate_group, ["promote", str(md), "--root", str(tmp_path),
                                            "--paper-ref", "paper:x", "--apply"])
    assert r.exit_code == 0, r.output
    text = (tmp_path / "entities" / "propositions" / "genes-encode-proteins.md").read_text(encoding="utf-8")
    assert "paper:x" in text


def test_promote_unhandled_source_fails_loud(tmp_path):
    # No adapter handles a non-.source.md file and no --paper-ref given:
    # the TextSourceAdapterError must surface as a clean CLI error, not a traceback.
    (tmp_path / "entities" / "propositions").mkdir(parents=True)
    notes = tmp_path / "notes.md"
    notes.write_text("Some prose.\n", encoding="utf-8")
    r = CliRunner().invoke(annotate_group, ["promote", str(notes), "--root", str(tmp_path)])
    assert r.exit_code != 0
    assert "no text source adapter handles" in r.output
```

> Why `monkeypatch.setattr(sa, "resolve_adapter", ...)` works: `promote_cmd` does
> `from science_tool.annotation.text_source_adapter import resolve_adapter` *inside* the function, so
> the name is rebound from the (patched) module attribute on every invocation.

- [ ] **Step 3: Run the new tests (behavior-lock guards — expected green)**

Run: `PYTHONPATH=science/src:science/model/src ~/d/science/science/.venv/bin/pytest -q science/tests/test_annotate_promote_cli.py -k "without_paper_ref or does_not_touch_adapter"`
Expected: PASS already. These are **behavior-lock guards**, not red-first TDD: the legacy `.stem`
default also yields `paper:p`, and before the edit `promote_cmd` never calls `resolve_adapter` (so
the explicit-ref monkeypatch is inert). Their job is to stay green *through* the edit and catch a
regression where `resolve_adapter` is wrongly called outside the `None` branch (which would break
`does_not_touch_adapter`) or the default ref changes (which would break `without_paper_ref`).
Proceed to Step 4 — the edit must keep both green.

- [ ] **Step 4: Write the implementation**

In `cli.py`, add to `promote_cmd`'s local imports (the block at lines 1169-1174):

```python
    from science_tool.annotation.text_source_adapter import (
        TextSourceAdapterError,
        resolve_adapter,
    )
```

Replace the current default-derivation block (`cli.py:1180-1183`):

```python
    if paper_ref is None:
        # citekey = <citekey>.source.md → <citekey>; the owning paper entity is paper:<citekey>.
        citekey = source_md.name[: -len(".source.md")] if source_md.name.endswith(".source.md") else source_md.stem
        paper_ref = f"paper:{citekey}"
```

with (note `resolve_adapter` is called **only** when no explicit ref was passed, and its
fail-loud error is converted to a clean CLI error):

```python
    if paper_ref is None:
        try:
            paper_ref = resolve_adapter(source_md).source_ref(source_md)
        except TextSourceAdapterError as exc:
            raise click.ClickException(str(exc)) from exc
```

- [ ] **Step 5: Run new + full promote suite to verify green**

Run: `PYTHONPATH=science/src:science/model/src ~/d/science/science/.venv/bin/pytest -q science/tests/test_annotate_promote_cli.py`
Expected: PASS (new runtime tests + **all** existing promote tests unchanged-green)

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/annotation/cli.py science/tests/test_annotate_promote_cli.py
git commit -m "refactor(promote): derive default source ref via resolve_adapter (behavior-neutral)"
```

---

## Task 6: route `extract_cmd` through the adapter

**Files:**
- Modify: `science/src/science_tool/annotation/cli.py:1119-1125` (`extract_cmd`)
- Test: `science/tests/test_text_source_adapter.py` (delegation unit test) and
  `science/tests/test_annotate_extract_cli.py` (runtime seam test, reuses `_make_source_md`)

Replace the direct `extract_candidates(...)` call with `resolve_adapter(source_md).extract(...)`.
**Behavior-neutral**: `PaperSourceAdapter.extract` delegates to the same `extract_candidates`.
Guarded by the existing `test_annotate_extract_cli.py` suite, a delegation unit test, and a
runtime seam test that proves the CLI actually routes through `resolve_adapter`.

- [ ] **Step 1: Record the baseline**

Run: `PYTHONPATH=science/src:science/model/src ~/d/science/science/.venv/bin/pytest -q science/tests/test_annotate_extract_cli.py`
Expected: PASS (all existing extract tests) — the behavior-neutral baseline.

- [ ] **Step 2: Write the delegation unit test**

Append to `science/tests/test_text_source_adapter.py`. **Add the imports** `from datetime import
datetime, timezone` at the top of that file if not already present (the delegation test needs
them):

```python
# (ensure at top of science/tests/test_text_source_adapter.py)
from datetime import datetime, timezone


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
```

- [ ] **Step 3: Write the runtime seam test**

Append to `science/tests/test_annotate_extract_cli.py` (it already imports `json`, `Path`,
`CliRunner`, `annotate_group`, and defines `_make_source_md` + `_MODEL`). A spy on
`resolve_adapter` that the CLI must actually call, asserting both that it was invoked **and** that
the command produced the real result (`written == 1`):

```python
def test_extract_cmd_routes_through_resolve_adapter(tmp_path: Path, monkeypatch):
    import science_tool.annotation.text_source_adapter as sa

    calls = {}
    real_resolve = sa.resolve_adapter

    def spy_resolve(source_md):
        calls["source_md"] = source_md
        return real_resolve(source_md)

    monkeypatch.setattr(sa, "resolve_adapter", spy_resolve)

    src = _make_source_md(tmp_path)
    cand = tmp_path / "candidates.json"
    cand.write_text(json.dumps({"candidates": [{
        "type": "proposition",
        "exact": "BRCA1 loss drives genomic instability",
        "prefix": "", "suffix": " in tumors", "stance": "asserted",
    }]}), encoding="utf-8")

    r = CliRunner().invoke(annotate_group, [
        "extract", "--source-md", str(src), "--model", _MODEL,
        "--input", str(cand), "--format", "json",
    ])
    assert r.exit_code == 0, r.output
    assert calls.get("source_md") == src          # the CLI actually called resolve_adapter
    assert json.loads(r.output)["written"] == 1   # and produced the real result


def test_extract_unhandled_source_fails_loud(tmp_path: Path):
    # A source no adapter handles must surface as a clean CLI error, not a traceback.
    notes = tmp_path / "notes.md"
    notes.write_text("Some prose.\n", encoding="utf-8")
    cand = tmp_path / "candidates.json"
    cand.write_text(json.dumps({"candidates": [{
        "type": "proposition", "exact": "x", "prefix": "", "suffix": "", "stance": "asserted",
    }]}), encoding="utf-8")
    r = CliRunner().invoke(annotate_group, [
        "extract", "--source-md", str(notes), "--model", _MODEL, "--input", str(cand),
    ])
    assert r.exit_code != 0
    assert "no text source adapter handles" in r.output
```

> `monkeypatch.setattr(sa, "resolve_adapter", ...)` is picked up because `extract_cmd` does
> `from science_tool.annotation.text_source_adapter import resolve_adapter` *inside* the function.

- [ ] **Step 4: Run the new tests — delegation passes, seam fails**

Run: `PYTHONPATH=science/src:science/model/src ~/d/science/science/.venv/bin/pytest -q science/tests/test_text_source_adapter.py::test_paper_adapter_extract_delegates science/tests/test_annotate_extract_cli.py::test_extract_cmd_routes_through_resolve_adapter`
Expected: `test_paper_adapter_extract_delegates` PASSES (Task 3 implemented `extract`);
`test_extract_cmd_routes_through_resolve_adapter` FAILS — `calls` is empty because the CLI still
calls `extract_candidates` directly. If the delegation test fails, the Task-3 `extract` method is
wrong — fix it before proceeding.

- [ ] **Step 5: Write the implementation**

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

with (the `TextSourceAdapterError` from an unhandled source is converted to a clean CLI error):

```python
    from science_tool.annotation.text_source_adapter import (
        TextSourceAdapterError,
        resolve_adapter,
    )

    try:
        adapter = resolve_adapter(source_md)
    except TextSourceAdapterError as exc:
        raise click.ClickException(str(exc)) from exc
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

- [ ] **Step 6: Run guards + full extract suite to verify green**

Run: `PYTHONPATH=science/src:science/model/src ~/d/science/science/.venv/bin/pytest -q science/tests/test_text_source_adapter.py::test_paper_adapter_extract_delegates science/tests/test_annotate_extract_cli.py`
Expected: PASS (delegation unit test + the runtime seam test now pass + **all** existing extract CLI tests unchanged-green)

- [ ] **Step 7: Commit**

```bash
git add science/src/science_tool/annotation/cli.py science/tests/test_text_source_adapter.py science/tests/test_annotate_extract_cli.py
git commit -m "refactor(extract): extract via resolve_adapter (behavior-neutral)"
```

---

## Task 7: full-suite behavior-neutrality gate + module docstring

**Files:**
- Modify: `science/src/science_tool/annotation/text_source_adapter.py` (docstring only, if needed)
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
  science/tests/test_text_source_adapter.py
```
Expected: ALL PASS, zero failures. This is the behavior-neutral proof.

- [ ] **Step 2: If any existing test changed behavior, STOP and fix the wiring**

Do not edit existing test files to make them pass. A failure here means the re-wiring is not
behavior-neutral — revert to the offending task and correct the delegation.

- [ ] **Step 3: Confirm the module docstring states the P1/P2 boundary**

Ensure `text_source_adapter.py`'s top docstring notes: `offset_anchored` implemented; `regenerable`
declared-but-unimplemented until P2; `fetch`/`seed` declared but `persist-source`/`pubtator`
remain paper-specific in P1.

- [ ] **Step 4: Commit (if the docstring changed)**

```bash
git add science/src/science_tool/annotation/text_source_adapter.py
git commit -m "docs(source-adapter): record P1/P2 regime + capability boundary"
```

---

## Self-review checklist (run after implementation, before finishing the branch)

1. **Behavior-neutral:** the full annotation suite (Task 7) passes with **no edits** to existing
   test files.
2. **No isinstance dispatch:** `resolve_adapter` selects by `handles()`, not type checks; the CLI
   reads `adapter.locator_regime`/capabilities, never `isinstance`.
3. **Source-ref parity:** `PaperSourceAdapter.source_ref` returns byte-identical strings to the
   old inline derivation for every `.source.md` input (Task 3 tests), and `resolve_adapter` is
   called **only** inside `if paper_ref is None:` so an explicit `--paper-ref` is untouched. The
   one sanctioned deviation (no-ref + non-`.source.md` → fail-loud instead of silent `paper:<stem>`)
   is documented in Task 5 and exercised by `test_promote_explicit_paper_ref_does_not_touch_adapter`.
4. **Seam scope for P2 (honest):** `extract` and `source_ref` go through the adapter, and
   `LocatorRegime`/`can_fetch`/`can_seed` are declared. P2's `InternalProseAdapter` reuses those
   two seams *without* editing the extract/promote ref-derivation bodies — but P2 is **not** purely
   additive: it must also build the regenerable locator artifact and extend the still-paper-coupled
   `--check` and promotion sidecar-read paths (see "What P1 does NOT make additive for P2" above).

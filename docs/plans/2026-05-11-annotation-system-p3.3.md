# Annotation System P3.3 — Author CRUD Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the read/triage surface for the annotation system —
`science annotate list / ack / dismiss / fix / stats` — built on the
sidecar I/O (P3.0), verify (P3.1), and audit/lift-tokens (P3.2)
already in place. Folds in four mechanical follow-ups from the P3.2
final review where they touch shared code paths.

**Architecture:** Two new modules under `annotation/`:
`query.py` (project walk, ID resolution, filter, stats) and
`crud.py` (one orchestrator function powering `ack`/`dismiss`/`fix`).
Five new Click subcommands on the existing `science annotate` group.
A new `text_segmentation.py` module replaces three near-duplicate
sentence-splitting code blocks. Path-derivation helpers move to
`io.py` (explicit, fail-loud, multi-dot-safe). One-line tightening
of `lifecycle.mutate_status` enforces the spec's intent that
`ack`/`fixed`/`dismissed` are author-set only from `open`.

**Tech Stack:** Python 3.11, click, rdflib (already in P3.0), pytest.
No new dependencies.

---

## Spec references

This plan implements the approved spec at
`docs/plans/2026-05-11-annotation-system-p3.3-spec.md`. Quick map
from spec sections to plan tasks:

| Spec section | Tasks |
|---|---|
| §"Path-derivation helpers in `io.py`" | Task 1 |
| §"Helper migration into `io.py`" (atomic_write_text + serialize_sidecar) | Task 2 |
| §"Folded follow-ups 1 + 7 — `text_segmentation.py`" | Task 3 |
| §"Folded follow-up 2 — `merge_planned` invariant" + §"Folded follow-up 3 — `mint_id` O(N²)→O(N)" | Task 4 |
| §"Decision 12 — tighten `lifecycle.mutate_status`" | Task 5 |
| §"`query.iter_sidecars` + `SidecarParseError`" | Task 6 |
| §"`query.resolve_id` algorithm" | Task 7 |
| §"`query.filter_annotations` + `git_changed_markdown`" | Task 8 |
| §"`query.compute_stats` + `StatsReport`" | Task 9 |
| §"`crud.apply_status_change`" + §"Error handling matrix" | Task 10 |
| §"CLI surface — `list [PATH]`" | Task 11 |
| §"CLI surface — `ack` / `dismiss` / `fix`" | Task 12 |
| §"CLI surface — `stats`" | Task 13 |
| §"Integration test" | Task 14 |
| §Acceptance criteria | Task 15 |

Out of scope (per spec §Non-goals): `render` (P3.4), `--type` filter,
top-N entity stats, batch CRUD, `fix` selector re-resolution,
persistent ID index, `prose lint` deprecation. A subagent that finds
itself adding any of these should stop and escalate.

---

## File Structure

**Create (source):**

- `science/src/science_tool/annotation/text_segmentation.py` —
  sentence boundaries, sentence-range lookup (col-known +
  literal-anchored), `build_quote_selector`.
- `science/src/science_tool/annotation/query.py` — `iter_sidecars`,
  `resolve_id`, `filter_annotations`, `compute_stats`,
  `git_changed_markdown`, error classes (`AnnotationLookupError`,
  `AnnotationNotFound`, `AmbiguousAnnotationId`, `SidecarParseError`),
  result dataclasses (`ResolvedAnnotation`, `StatsReport`).
- `science/src/science_tool/annotation/crud.py` —
  `apply_status_change`, `_resolve_actor`, `_sidecar_is_dirty`,
  `CrudResult`, `CrudRefusedDirty`.

**Modify (source):**

- `science/src/science_tool/annotation/io.py` — add
  `sidecar_for_markdown`, `markdown_for_sidecar`, `atomic_write_text`,
  `serialize_sidecar`. Last two move from `cli.py:664-693` (made
  public).
- `science/src/science_tool/annotation/cli.py` — drop the moved
  `_atomic_write_text` / `_serialize_sidecar` (import from `io.py`
  instead). Add five new commands (`list_cmd`, `ack_cmd`,
  `dismiss_cmd`, `fix_cmd`, `stats_cmd`). Switch `_replan_for_remove`
  to use `text_segmentation` helpers.
- `science/src/science_tool/annotation/sources/marker_token.py` —
  replace local `_sentence_range_at` and `_build_selector` with
  `text_segmentation.sentence_range_containing_literal` and
  `text_segmentation.build_quote_selector`. Both `scan` and
  `scan_text` use the same helpers.
- `science/src/science_tool/annotation/sources/lint.py` — replace
  local `_selector_for_issue` with
  `text_segmentation.sentence_range_at` (col known) +
  `text_segmentation.build_quote_selector`.
- `science/src/science_tool/annotation/audit.py` — replace `assert`
  invariants with explicit `ValueError` raises; hoist
  `existing_by_id` map construction out of `mint_id` so
  `merge_planned` builds it once and `mint_id` becomes O(1) per call.
- `science/src/science_tool/annotation/lifecycle.py` — tighten
  `mutate_status` to require `OPEN` source for any non-`SUPERSEDED`
  target status (Decision 12).

**Create (tests):**

- `science/tests/test_io_path_helpers.py`
- `science/tests/test_io_atomic_write_serialize.py`
- `science/tests/test_text_segmentation.py`
- `science/tests/test_audit_invariant_value_error.py`
- `science/tests/test_audit_mint_id_set_hoist.py`
- `science/tests/test_lifecycle_open_source_guard.py`
- `science/tests/test_query_iter_sidecars.py`
- `science/tests/test_query_resolve_id.py`
- `science/tests/test_query_filter.py`
- `science/tests/test_query_stats.py`
- `science/tests/test_crud_apply.py`
- `science/tests/test_annotate_list_cli.py`
- `science/tests/test_annotate_ack_dismiss_fix_cli.py`
- `science/tests/test_annotate_stats_cli.py`
- `science/tests/test_annotate_p33_integration.py`

**Modify (tests):**

- `science/tests/test_annotation_audit_merge.py` — switch
  `pytest.raises(AssertionError)` to `pytest.raises(ValueError)` for
  the cross-source-contamination test (Task 4).
- `science/tests/test_annotation_sources_marker_token.py` — no test
  changes expected (helpers swap is behavior-preserving), but rerun.
- `science/tests/test_annotation_sources_lint.py` — same.
- `science/tests/test_annotate_lift_tokens_cli.py` — same.

**Fixtures:** All test fixtures are constructed programmatically via
`tmp_path` (mirrors P3.1 / P3.2 test style for sidecars). No new
files under `science/tests/_fixtures/`.

---

## Tasks

### Task 1: `io.sidecar_for_markdown` + `io.markdown_for_sidecar`

**Files:**
- Modify: `science/src/science_tool/annotation/io.py`
- Test: `science/tests/test_io_path_helpers.py`

Foundation for Tasks 8 (`--since`) and 11 (`list [PATH]`). Pure
utility — explicit, fail-loud, handles multi-dotted names like
`paper.v1.md` that `Path.with_suffix` chains misbehave on.

- [ ] **Step 1: Write the failing tests**

Create `science/tests/test_io_path_helpers.py`:

```python
"""sidecar_for_markdown / markdown_for_sidecar are explicit and fail loudly."""

from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.annotation.io import (
    markdown_for_sidecar,
    sidecar_for_markdown,
)


def test_sidecar_for_markdown_simple() -> None:
    assert sidecar_for_markdown(Path("foo.md")) == Path("foo.anno.trig")


def test_sidecar_for_markdown_multi_dotted() -> None:
    assert (
        sidecar_for_markdown(Path("paper.v1.md"))
        == Path("paper.v1.anno.trig")
    )


def test_sidecar_for_markdown_keeps_parent() -> None:
    assert (
        sidecar_for_markdown(Path("notes/foo.md"))
        == Path("notes/foo.anno.trig")
    )


def test_sidecar_for_markdown_rejects_non_md() -> None:
    with pytest.raises(ValueError):
        sidecar_for_markdown(Path("foo.txt"))


def test_sidecar_for_markdown_rejects_no_extension() -> None:
    with pytest.raises(ValueError):
        sidecar_for_markdown(Path("README"))


def test_markdown_for_sidecar_simple() -> None:
    assert (
        markdown_for_sidecar(Path("foo.anno.trig"))
        == Path("foo.md")
    )


def test_markdown_for_sidecar_multi_dotted() -> None:
    assert (
        markdown_for_sidecar(Path("paper.v1.anno.trig"))
        == Path("paper.v1.md")
    )


def test_markdown_for_sidecar_keeps_parent() -> None:
    assert (
        markdown_for_sidecar(Path("notes/foo.anno.trig"))
        == Path("notes/foo.md")
    )


def test_markdown_for_sidecar_rejects_wrong_suffix() -> None:
    with pytest.raises(ValueError):
        markdown_for_sidecar(Path("foo.trig"))


def test_round_trip_simple() -> None:
    p = Path("foo.md")
    assert markdown_for_sidecar(sidecar_for_markdown(p)) == p


def test_round_trip_multi_dotted() -> None:
    p = Path("paper.v1.md")
    assert markdown_for_sidecar(sidecar_for_markdown(p)) == p
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science && uv run pytest tests/test_io_path_helpers.py -v`
Expected: FAIL — `cannot import name 'sidecar_for_markdown' from
'science_tool.annotation.io'`.

- [ ] **Step 3: Add the helpers**

Edit `science/src/science_tool/annotation/io.py`. Add at module level
(after the existing imports, before any other public function):

```python
_MD_SUFFIX = ".md"
_SIDECAR_SUFFIX = ".anno.trig"


def sidecar_for_markdown(md_path: Path) -> Path:
    """Return the sidecar Path for a markdown file.

    `foo.md` → `foo.anno.trig`; `paper.v1.md` → `paper.v1.anno.trig`.

    Raises ValueError if `md_path` does not end with `.md`.
    """
    name = md_path.name
    if not name.endswith(_MD_SUFFIX):
        raise ValueError(
            f"not a markdown path (expected '.md' suffix): {md_path}"
        )
    base = name[: -len(_MD_SUFFIX)]
    return md_path.with_name(base + _SIDECAR_SUFFIX)


def markdown_for_sidecar(sidecar_path: Path) -> Path:
    """Return the markdown Path for a sidecar file.

    `foo.anno.trig` → `foo.md`; `paper.v1.anno.trig` → `paper.v1.md`.

    Raises ValueError if `sidecar_path` does not end with `.anno.trig`.
    """
    name = sidecar_path.name
    if not name.endswith(_SIDECAR_SUFFIX):
        raise ValueError(
            f"not a sidecar path (expected '.anno.trig' suffix): {sidecar_path}"
        )
    base = name[: -len(_SIDECAR_SUFFIX)]
    return sidecar_path.with_name(base + _MD_SUFFIX)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && uv run pytest tests/test_io_path_helpers.py -v`
Expected: PASS (10 tests).

- [ ] **Step 5: Confirm no regressions**

Run: `cd science && uv run pytest tests/ -q -k "annotation or annotate"`
Expected: all annotation tests green; this is purely additive.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/annotation/io.py \
        science/tests/test_io_path_helpers.py
git commit -m "feat(annotation): explicit md↔sidecar path helpers in io.py (P3.3 prep)"
```

---

### Task 2: Move `serialize_sidecar` + `atomic_write_text` into `io.py`

**Files:**
- Modify: `science/src/science_tool/annotation/io.py`
- Modify: `science/src/science_tool/annotation/cli.py`
- Test: `science/tests/test_io_atomic_write_serialize.py`

The two helpers `lift_tokens_cmd` already uses
(`cli.py:_atomic_write_text` and `cli.py:_serialize_sidecar`) need to
be public and reusable from `crud.py`. Move them to `io.py`,
re-export under public names, update `cli.py` to import from `io.py`.

- [ ] **Step 1: Write the failing tests**

Create `science/tests/test_io_atomic_write_serialize.py`:

```python
"""atomic_write_text and serialize_sidecar are public io.py helpers."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from science_tool.annotation.io import (
    atomic_write_text,
    read_sidecar,
    serialize_sidecar,
)
from science_tool.annotation.model import (
    Annotation,
    Motivation,
    Sidecar,
    SpecificResource,
    Status,
    TextQuoteSelector,
    TextualBody,
)


def _ann() -> Annotation:
    return Annotation(
        id="a-abc123",
        target=SpecificResource(
            source="example.md",
            selector=TextQuoteSelector(
                exact="Sample sentence.",
                prefix="Before. ",
                suffix=" After.",
            ),
        ),
        bodies=(TextualBody(value="msg"),),
        motivation=Motivation.CLASSIFYING,
        annotation_type="bare-author-year",
        source="lint:bare-author-year-v2026-05-11",
        status=Status.OPEN,
        creator="test",
        created=datetime(2026, 5, 11, tzinfo=timezone.utc),
        content_hash="sha256:dead",
        match_text="x",
    )


def test_atomic_write_text_writes_and_replaces(tmp_path: Path) -> None:
    target = tmp_path / "x.txt"
    target.write_text("old", encoding="utf-8")
    atomic_write_text(target, "new")
    assert target.read_text(encoding="utf-8") == "new"


def test_atomic_write_text_no_orphan_temp_on_success(tmp_path: Path) -> None:
    target = tmp_path / "x.txt"
    atomic_write_text(target, "hello")
    leftovers = [p.name for p in tmp_path.iterdir() if p.name != "x.txt"]
    assert leftovers == [], f"unexpected temp leftovers: {leftovers!r}"


def test_serialize_sidecar_round_trips(tmp_path: Path) -> None:
    original = Sidecar(annotations=(_ann(),))
    text = serialize_sidecar(original)
    target = tmp_path / "x.anno.trig"
    target.write_text(text, encoding="utf-8")
    loaded = read_sidecar(target)
    assert loaded.annotations[0].id == "a-abc123"


def test_serialize_sidecar_returns_str() -> None:
    text = serialize_sidecar(Sidecar(annotations=(_ann(),)))
    assert isinstance(text, str)
    assert "@prefix" in text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science && uv run pytest tests/test_io_atomic_write_serialize.py -v`
Expected: FAIL — `cannot import name 'atomic_write_text'`.

- [ ] **Step 3: Add public helpers in `io.py`**

Edit `science/src/science_tool/annotation/io.py`. Append at the end
of the file:

```python
def atomic_write_text(path: Path, text: str) -> None:
    """Write `text` to `path` atomically via temp + os.replace.

    Same semantics as P3.2's `cli._atomic_write_text` (which calls
    this helper now).
    """
    import os
    import tempfile

    fd, tmp_name = tempfile.mkstemp(
        prefix=path.name, dir=str(path.parent), text=True,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp_name, str(path))
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def serialize_sidecar(sidecar: Sidecar) -> str:
    """Serialize a Sidecar to its TriG textual form.

    Mirrors `write_sidecar`'s emission to a string buffer (via temp
    file) so callers that need the textual representation don't have
    to write to disk first.
    """
    import os
    import tempfile

    fd, tmp = tempfile.mkstemp(suffix=".anno.trig")
    os.close(fd)
    try:
        write_sidecar(Path(tmp), sidecar)
        return Path(tmp).read_text(encoding="utf-8")
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass
```

- [ ] **Step 4: Update `cli.py` to import from `io.py`**

Edit `science/src/science_tool/annotation/cli.py`. Find and DELETE the
existing definitions (currently around lines 664–693):

```python
def _atomic_write_text(path: Path, text: str) -> None:
    ...

def _serialize_sidecar(sidecar: Sidecar) -> str:
    ...
```

In the existing import block at the top of the file, add the two
public names to the existing `from science_tool.annotation.io import …`:

```python
from science_tool.annotation.io import (
    atomic_write_text,
    read_sidecar,
    serialize_sidecar,
    write_sidecar,
)
```

Now find every call site in `cli.py` that uses the deleted helpers
and rename:

```bash
# These two patterns must be updated:
grep -n "_atomic_write_text\|_serialize_sidecar" \
    science/src/science_tool/annotation/cli.py
```

For each match, replace `_atomic_write_text(` → `atomic_write_text(`
and `_serialize_sidecar(` → `serialize_sidecar(` (the call sites
inside `lift_tokens_cmd`).

- [ ] **Step 5: Run new tests to verify they pass**

Run: `cd science && uv run pytest tests/test_io_atomic_write_serialize.py -v`
Expected: PASS (4 tests).

- [ ] **Step 6: Run lift-tokens tests to confirm no regression**

Run: `cd science && uv run pytest tests/test_annotate_lift_tokens_cli.py -v`
Expected: all P3.2 lift-tokens tests still pass.

- [ ] **Step 7: Commit**

```bash
git add science/src/science_tool/annotation/io.py \
        science/src/science_tool/annotation/cli.py \
        science/tests/test_io_atomic_write_serialize.py
git commit -m "refactor(annotation): hoist atomic_write_text + serialize_sidecar into io.py"
```

---

### Task 3: Extract `text_segmentation.py` (Follow-ups 1 + 7)

**Files:**
- Create: `science/src/science_tool/annotation/text_segmentation.py`
- Modify: `science/src/science_tool/annotation/sources/marker_token.py`
- Modify: `science/src/science_tool/annotation/sources/lint.py`
- Modify: `science/src/science_tool/annotation/cli.py`
- Test: `science/tests/test_text_segmentation.py`

Replaces three near-duplicate sentence-splitting code blocks with one
canonical module. Provides two sibling lookup functions
(`sentence_range_at` requires col; `sentence_range_containing_literal`
anchors via the literal token) so callers without column info don't
silently default to col=1 and mis-anchor.

- [ ] **Step 1: Write the failing tests**

Create `science/tests/test_text_segmentation.py`:

```python
"""text_segmentation: sentence boundaries + selector building."""

from __future__ import annotations

import pytest

from science_tool.annotation.model import TextQuoteSelector
from science_tool.annotation.text_segmentation import (
    build_quote_selector,
    sentence_range_at,
    sentence_range_containing_literal,
    split_sentences_with_offsets,
)


# ---- split_sentences_with_offsets -------------------------------------

def test_split_sentences_simple() -> None:
    text = "First sentence. Second sentence. Third."
    ranges = split_sentences_with_offsets(text)
    assert len(ranges) == 3
    assert text[ranges[0][0] : ranges[0][1]] == "First sentence."
    assert text[ranges[1][0] : ranges[1][1]] == "Second sentence."
    assert text[ranges[2][0] : ranges[2][1]] == "Third."


def test_split_sentences_empty_text() -> None:
    assert split_sentences_with_offsets("") == []


def test_split_sentences_no_terminator() -> None:
    text = "Just a fragment with no period"
    ranges = split_sentences_with_offsets(text)
    assert ranges == [(0, len(text))]


def test_split_sentences_across_lines() -> None:
    text = "Line one ends.\nLine two ends.\nLine three."
    ranges = split_sentences_with_offsets(text)
    assert len(ranges) == 3


# ---- sentence_range_at (col REQUIRED) ---------------------------------

def test_sentence_range_at_picks_correct_sentence_on_multi_sent_line() -> None:
    text = "First. Second. Third."
    # col 8 (1-based) lands inside "Second."
    rng = sentence_range_at(text, line=1, col=8)
    assert rng is not None
    assert text[rng[0] : rng[1]] == "Second."


def test_sentence_range_at_picks_first_when_col_inside_first() -> None:
    text = "First sentence here. Second sentence."
    rng = sentence_range_at(text, line=1, col=3)
    assert rng is not None
    assert text[rng[0] : rng[1]] == "First sentence here."


def test_sentence_range_at_inter_sentence_whitespace_falls_back() -> None:
    text = "First.  Second."
    # Column 7 lands in the inter-sentence whitespace; algorithm
    # falls back to the nearest preceding sentence ("First.").
    rng = sentence_range_at(text, line=1, col=7)
    assert rng is not None
    assert text[rng[0] : rng[1]] == "First."


def test_sentence_range_at_line_out_of_range_returns_none() -> None:
    text = "One sentence."
    assert sentence_range_at(text, line=99, col=1) is None


# ---- sentence_range_containing_literal --------------------------------

def test_sentence_range_containing_literal_picks_second_sentence() -> None:
    """Regression for marker-token mis-anchoring on multi-sentence lines."""
    text = "Some text. A claim [UNVERIFIED] sits here. Trailing text."
    rng = sentence_range_containing_literal(text, line=1, literal="[UNVERIFIED]")
    assert rng is not None
    assert text[rng[0] : rng[1]] == "A claim [UNVERIFIED] sits here."


def test_sentence_range_containing_literal_picks_first_sentence() -> None:
    text = "[UNVERIFIED] starts the line. Next sentence here."
    rng = sentence_range_containing_literal(text, line=1, literal="[UNVERIFIED]")
    assert rng is not None
    assert text[rng[0] : rng[1]] == "[UNVERIFIED] starts the line."


def test_sentence_range_containing_literal_not_on_line() -> None:
    text = "Line one has nothing.\nLine two has [UNVERIFIED]."
    assert sentence_range_containing_literal(
        text, line=1, literal="[UNVERIFIED]",
    ) is None


def test_sentence_range_containing_literal_finds_on_correct_line() -> None:
    text = "Line one has nothing.\nLine two has [UNVERIFIED]."
    rng = sentence_range_containing_literal(
        text, line=2, literal="[UNVERIFIED]",
    )
    assert rng is not None
    assert text[rng[0] : rng[1]] == "Line two has [UNVERIFIED]."


# ---- build_quote_selector ---------------------------------------------

def test_build_quote_selector_full_window_in_middle() -> None:
    text = "x" * 100 + "Target sentence." + "y" * 100
    sent_start = 100
    sent_end = sent_start + len("Target sentence.")
    sel = build_quote_selector(text, sent_start, sent_end, context=60)
    assert isinstance(sel, TextQuoteSelector)
    assert sel.exact == "Target sentence."
    assert sel.prefix == "x" * 60
    assert sel.suffix == "y" * 60


def test_build_quote_selector_truncates_prefix_near_start() -> None:
    text = "Pre " + "Target sentence." + "y" * 100
    sent_start = 4
    sent_end = sent_start + len("Target sentence.")
    sel = build_quote_selector(text, sent_start, sent_end, context=60)
    assert sel.exact == "Target sentence."
    assert sel.prefix == "Pre "  # truncated to text[0:sent_start]
    assert sel.suffix == "y" * 60


def test_build_quote_selector_truncates_suffix_near_eof() -> None:
    text = "x" * 100 + "Target sentence." + " End"
    sent_start = 100
    sent_end = sent_start + len("Target sentence.")
    sel = build_quote_selector(text, sent_start, sent_end, context=60)
    assert sel.exact == "Target sentence."
    assert sel.prefix == "x" * 60
    assert sel.suffix == " End"  # truncated to text[sent_end:]


def test_sentence_range_at_requires_col_no_default() -> None:
    """`col` MUST be required; defaulting silently mis-anchors markers."""
    with pytest.raises(TypeError):
        sentence_range_at("x.", line=1)  # type: ignore[call-arg]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science && uv run pytest tests/test_text_segmentation.py -v`
Expected: FAIL — `No module named 'science_tool.annotation.text_segmentation'`.

- [ ] **Step 3: Create `text_segmentation.py`**

Create `science/src/science_tool/annotation/text_segmentation.py`:

```python
# science/src/science_tool/annotation/text_segmentation.py
"""Sentence segmentation + TextQuoteSelector construction.

Single source of truth for sentence-boundary detection and selector
windowing across all annotation sources. See spec
docs/plans/2026-05-11-annotation-system-p3.3-spec.md §"Folded
follow-ups 1 + 7" for the consolidation rationale.

Two sentence-lookup functions are intentionally provided:
- `sentence_range_at(text, line, col)` for callers with both line
  and col (e.g. lint findings).
- `sentence_range_containing_literal(text, line, literal)` for
  callers that have a line and an anchoring substring but no col
  (e.g. marker tokens).

A single `sentence_range_at(text, line, col=1)` would silently
mis-anchor marker tokens that appear after the first sentence on a
line. `col` is REQUIRED on `sentence_range_at` to surface the
column-less use case as a distinct call site.
"""

from __future__ import annotations

import re
from typing import Optional

from science_tool.annotation.model import TextQuoteSelector


_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def split_sentences_with_offsets(text: str) -> list[tuple[int, int]]:
    """Return (start, end) char ranges of each sentence in `text`.

    Naive split on `[.!?]\\s+`; matches the segmentation strategy used
    by P3.2's marker_token / lint sources. Sentences that lack a
    terminator extend to the end of `text`.
    """
    if not text:
        return []
    out: list[tuple[int, int]] = []
    cursor = 0
    for sent in _SENTENCE_SPLIT_RE.split(text):
        if not sent:
            continue
        start = text.find(sent, cursor)
        if start == -1:
            continue
        end = start + len(sent)
        out.append((start, end))
        cursor = end
    return out


def _line_offsets(text: str) -> list[int]:
    """Return the char offset of each 1-based line start."""
    offsets = [0]
    for i, ch in enumerate(text):
        if ch == "\n":
            offsets.append(i + 1)
    return offsets


def sentence_range_at(
    text: str, line: int, col: int,
) -> Optional[tuple[int, int]]:
    """Return the (start, end) range of the sentence covering (line, col).

    - `line` and `col` are 1-based.
    - If (line, col) lands in inter-sentence whitespace, falls back to
      the nearest preceding sentence on the same or earlier line.
    - Returns None if `line` is past the last line of `text`.

    `col` is REQUIRED — see module docstring for rationale.
    """
    offsets = _line_offsets(text)
    if line < 1 or line > len(offsets):
        return None
    line_start = offsets[line - 1]
    cursor = line_start + (col - 1)
    if cursor < 0:
        cursor = 0
    if cursor > len(text):
        cursor = len(text)
    sentences = split_sentences_with_offsets(text)
    if not sentences:
        return None
    for start, end in sentences:
        if start <= cursor < end:
            return (start, end)
    # Fallback: nearest preceding sentence.
    for start, end in reversed(sentences):
        if start <= cursor:
            return (start, end)
    return None


def sentence_range_containing_literal(
    text: str, line: int, literal: str,
) -> Optional[tuple[int, int]]:
    """Return the sentence range of `literal` on the given 1-based `line`.

    Searches `line` (only) for `literal`; if found, maps the literal's
    char offset to the enclosing sentence range. Returns None if the
    literal is not on that line.

    Designed for callers without column info (e.g. MarkerHit, which
    carries `line` and `token` but no `col`). Picking the right
    sentence even when the line contains multiple sentences is
    load-bearing — a token in the second sentence on a line must NOT
    anchor to the first sentence.
    """
    offsets = _line_offsets(text)
    if line < 1 or line > len(offsets):
        return None
    line_start = offsets[line - 1]
    line_end = offsets[line] if line < len(offsets) else len(text)
    line_text = text[line_start:line_end]
    rel = line_text.find(literal)
    if rel == -1:
        return None
    abs_pos = line_start + rel
    sentences = split_sentences_with_offsets(text)
    for start, end in sentences:
        if start <= abs_pos < end:
            return (start, end)
    return None


def build_quote_selector(
    text: str,
    sent_start: int,
    sent_end: int,
    *,
    context: int = 60,
) -> TextQuoteSelector:
    """Build a TextQuoteSelector with `context`-char prefix/suffix windows.

    Windows are clipped at file boundaries (no padding).
    """
    prefix_start = max(0, sent_start - context)
    suffix_end = min(len(text), sent_end + context)
    return TextQuoteSelector(
        exact=text[sent_start:sent_end],
        prefix=text[prefix_start:sent_start],
        suffix=text[sent_end:suffix_end],
    )
```

- [ ] **Step 4: Run new tests to verify they pass**

Run: `cd science && uv run pytest tests/test_text_segmentation.py -v`
Expected: PASS (15 tests).

- [ ] **Step 5: Switch `marker_token.py` to use the new helpers**

Edit `science/src/science_tool/annotation/sources/marker_token.py`.
At the top of the file, add the import:

```python
from science_tool.annotation.text_segmentation import (
    build_quote_selector,
    sentence_range_containing_literal,
)
```

Find the current local `_sentence_range_at` (or `_sentence_range_for_token`)
and `_build_selector` definitions and DELETE them. Find every call
site that uses them — likely inside `scan` and `scan_text` — and
rewrite to use the imported helpers. The marker case uses the
literal-anchored variant:

```python
# inside scan / scan_text, for each MarkerHit `hit`:
literal = f"[{hit.token}]"
rng = sentence_range_containing_literal(text, hit.line, literal)
if rng is None:
    continue
sent_start, sent_end = rng
selector = build_quote_selector(text, sent_start, sent_end, context=60)
```

Confirm both `scan` and `scan_text` route through the same two
helpers (closes Follow-up 7).

- [ ] **Step 6: Switch `lint.py` to use the new helpers**

Edit `science/src/science_tool/annotation/sources/lint.py`. At the top:

```python
from science_tool.annotation.text_segmentation import (
    build_quote_selector,
    sentence_range_at,
)
```

Find the current local `_selector_for_issue` (or equivalent) and
DELETE it. Rewrite its sole call site to:

```python
# inside scan, for each LintIssue `issue`:
rng = sentence_range_at(text, issue.line, issue.col)
if rng is None:
    continue
sent_start, sent_end = rng
selector = build_quote_selector(text, sent_start, sent_end, context=60)
```

- [ ] **Step 7: Switch `cli._replan_for_remove` to use the helpers**

Edit `science/src/science_tool/annotation/cli.py`. The existing
`_replan_for_remove` function (around line 577) has local helpers
`_split_sentences_with_offsets` and `_sentence_ordinal_for_line`.

Replace the two local helpers with imports at the top of `cli.py`:

```python
from science_tool.annotation.text_segmentation import (
    build_quote_selector,
    sentence_range_containing_literal,
    split_sentences_with_offsets,
)
```

DELETE the module-level `_SENTENCE_SPLIT_RE`,
`_split_sentences_with_offsets`, and `_sentence_ordinal_for_line`
(currently around lines 622–661).

Inside `_replan_for_remove`, rewrite the per-hit loop to use the
literal-anchored helper on `original_text`, then map to
`cleaned_text` by sentence ordinal:

```python
def _replan_for_remove(
    source: MarkerTokenSource,
    md: Path,
    original_text: str,
    cleaned_text: str,
    original_hits,
) -> list:
    """Build planned rows whose selectors anchor to cleaned_text but whose
    `match_text`/`lifted_from` retain the original bracketed token."""
    from science_tool.annotation.model import (  # noqa: PLC0415
        Motivation, SpecificResource, TextualBody,
    )
    from science_tool.annotation.sources.base import (  # noqa: PLC0415
        PlannedAnnotation,
    )
    plans: list = []
    cleaned_sentences = split_sentences_with_offsets(cleaned_text)
    original_sentences = split_sentences_with_offsets(original_text)
    for hit in original_hits:
        literal = f"[{hit.token}]"
        rng = sentence_range_containing_literal(
            original_text, hit.line, literal,
        )
        if rng is None:
            continue
        # Find the ordinal of (rng) within original_sentences.
        try:
            ordinal = next(
                i for i, (s, _e) in enumerate(original_sentences)
                if s == rng[0]
            )
        except StopIteration:
            continue
        if ordinal >= len(cleaned_sentences):
            continue
        sent_start, sent_end = cleaned_sentences[ordinal]
        atype, body_msg = TOKEN_TYPE_MAP[hit.token]
        sel = build_quote_selector(
            cleaned_text, sent_start, sent_end, context=60,
        )
        plans.append(PlannedAnnotation(
            target=SpecificResource(source=md.name, selector=sel),
            annotation_type=atype,
            motivation=Motivation.CLASSIFYING,
            body=TextualBody(value=f"{body_msg} (lifted from {literal})"),
            match_text=literal,
            source_name=source.name,
            lifted_from=literal,
        ))
    return plans
```

- [ ] **Step 8: Run all annotation tests to confirm no regression**

Run: `cd science && uv run pytest tests/ -q -k "annotation or annotate"`
Expected: all pre-existing tests (P3.0 / P3.1 / P3.2) still green.
The marker-token and lint tests in particular are the regression
sentinels for the swap.

- [ ] **Step 9: Commit**

```bash
git add science/src/science_tool/annotation/text_segmentation.py \
        science/src/science_tool/annotation/sources/marker_token.py \
        science/src/science_tool/annotation/sources/lint.py \
        science/src/science_tool/annotation/cli.py \
        science/tests/test_text_segmentation.py
git commit -m "refactor(annotation): extract text_segmentation helpers (P3.2 follow-ups 1+7)"
```

---

### Task 4: `audit.py` invariant + `mint_id` follow-ups

**Files:**
- Modify: `science/src/science_tool/annotation/audit.py`
- Modify: `science/tests/test_annotation_audit_merge.py`
- Test: `science/tests/test_audit_invariant_value_error.py`
- Test: `science/tests/test_audit_mint_id_set_hoist.py`

Two micro-changes folded together (Follow-ups 2 + 3):
- `assert` invariants in `merge_planned` and `mint_id` become explicit
  `ValueError` raises so the guards survive `python -O`.
- `existing_by_id: dict[str, Annotation]` map construction hoists
  out of `mint_id` into `merge_planned`. Replaces both the per-call
  `next(...)` scan over `sidecar.annotations` (was O(N) per call)
  and the `existing_ids` set used for `-N` suffix probing — one map
  serves both purposes. K planned rows now share one O(N) build
  instead of doing K × O(N) scans.

- [ ] **Step 1: Write the failing tests for the invariant change**

Create `science/tests/test_audit_invariant_value_error.py`:

```python
"""merge_planned cross-source contamination raises ValueError, not AssertionError."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from science_tool.annotation.audit import merge_planned
from science_tool.annotation.model import (
    Motivation,
    Sidecar,
    SpecificResource,
    TextQuoteSelector,
    TextualBody,
)
from science_tool.annotation.sources.base import PlannedAnnotation


def _planned(source_name: str, exact: str = "x") -> PlannedAnnotation:
    return PlannedAnnotation(
        target=SpecificResource(
            source="example.md",
            selector=TextQuoteSelector(exact=exact, prefix="", suffix=""),
        ),
        annotation_type="bare-author-year",
        motivation=Motivation.CLASSIFYING,
        body=TextualBody(value="msg"),
        match_text="m",
        source_name=source_name,
    )


def test_merge_planned_rejects_mixed_sources_with_value_error() -> None:
    sidecar = Sidecar()
    planned = [
        _planned("lint:foo-v1", exact="a"),
        _planned("lint:bar-v1", exact="b"),
    ]
    with pytest.raises(ValueError, match="single-source"):
        merge_planned(
            sidecar, planned,
            actor="test", now=datetime(2026, 5, 11, tzinfo=timezone.utc),
        )
```

- [ ] **Step 2: Write the failing tests for the set-hoist refactor**

Create `science/tests/test_audit_mint_id_set_hoist.py`:

```python
"""mint_id accepts existing_by_id map; merge_planned scales O(planned + existing)."""

from __future__ import annotations

import inspect
import time
from datetime import datetime, timezone

import pytest

from science_tool.annotation.audit import merge_planned, mint_id
from science_tool.annotation.model import (
    Annotation,
    Motivation,
    Sidecar,
    SpecificResource,
    Status,
    TextQuoteSelector,
    TextualBody,
)
from science_tool.annotation.sources.base import PlannedAnnotation


def _planned(i: int) -> PlannedAnnotation:
    return PlannedAnnotation(
        target=SpecificResource(
            source="x.md",
            selector=TextQuoteSelector(
                exact=f"sentence number {i}.",
                prefix="", suffix="",
            ),
        ),
        annotation_type="bare-author-year",
        motivation=Motivation.CLASSIFYING,
        body=TextualBody(value="msg"),
        match_text=f"m{i}",
        source_name="lint:foo-v1",
    )


def test_mint_id_signature_takes_existing_by_id() -> None:
    """Signature change is the load-bearing API contract."""
    sig = inspect.signature(mint_id)
    assert "existing_by_id" in sig.parameters, (
        "mint_id must accept existing_by_id: dict[str, Annotation] "
        "(set-only is insufficient: base_id lookup also needs the map)"
    )


def test_merge_planned_handles_large_batch_in_reasonable_time() -> None:
    """Soft performance assertion: O(planned + existing), not O(planned × existing).

    With 500 existing rows and 500 fresh planned rows (no collisions),
    merge_planned should complete well under 1 second on commodity
    hardware. The threshold has a generous 10× margin to absorb CI
    variance; the goal is to catch regressions to O(N²) behavior, not
    to micro-benchmark.
    """
    now = datetime(2026, 5, 11, tzinfo=timezone.utc)
    initial_planned = [_planned(i) for i in range(500)]
    sidecar0, _ = merge_planned(
        Sidecar(), initial_planned, actor="t", now=now,
    )
    new_planned = [_planned(500 + i) for i in range(500)]
    start = time.perf_counter()
    sidecar1, written = merge_planned(
        sidecar0, new_planned, actor="t", now=now,
    )
    elapsed = time.perf_counter() - start
    assert len(written) == 500
    assert len(sidecar1.annotations) == 1000
    assert elapsed < 1.0, (
        f"merge_planned took {elapsed:.2f}s for 500+500 rows "
        "(suggests O(N²) regression in mint_id)"
    )
```

The signature test pins the API contract; the performance test
catches a future regression that re-introduces a per-call O(N) scan
inside `mint_id`.

- [ ] **Step 3: Run tests to verify they fail**

Run:
```bash
cd science && uv run pytest \
    tests/test_audit_invariant_value_error.py \
    tests/test_audit_mint_id_set_hoist.py -v
```
Expected: FAIL on both — current `merge_planned` raises
`AssertionError`; current `mint_id` lacks `existing_by_id` parameter.

- [ ] **Step 4: Convert `assert` to `ValueError` in `audit.py`**

Edit `science/src/science_tool/annotation/audit.py`. Find the two
existing `assert` statements:

(a) Inside `mint_id`, around line 87:
```python
        assert existing_at_base.status is Status.SUPERSEDED, (
            "merge_planned should have skipped a non-superseded match"
        )
```

Replace with:
```python
        if existing_at_base.status is not Status.SUPERSEDED:
            raise ValueError(
                "merge_planned should have skipped a non-superseded match "
                f"(annotation {existing_at_base.id!r} is "
                f"{existing_at_base.status.value!r})"
            )
```

(b) Inside `merge_planned`, around line 113:
```python
    assert all(p.source_name == source_name for p in planned), (
        "merge_planned requires single-source planned rows"
    )
```

Replace with:
```python
    if not all(p.source_name == source_name for p in planned):
        raise ValueError(
            "merge_planned requires single-source planned rows; got "
            f"{sorted({p.source_name for p in planned})!r}"
        )
```

- [ ] **Step 5: Hoist `existing_by_id` map construction**

Still in `audit.py`. Change `mint_id`'s signature and body to accept
the precomputed `id → Annotation` map. The map subsumes the set
(`.keys()` gives O(1) membership) and replaces the per-call O(N)
`next(...)` scan over `sidecar.annotations`:

```python
def mint_id(
    sidecar: Sidecar,
    p: PlannedAnnotation,
    *,
    existing_by_id: dict[str, Annotation],
) -> str:
    """Mint the on-disk ID for a planned row.

    `existing_by_id` is `{a.id: a for a in sidecar.annotations}` built
    once by the caller. Used for both the base-ID lookup and the `-N`
    suffix probe so a single mint_id call is O(1) regardless of
    sidecar size.

    Note: `sidecar` is no longer scanned by mint_id itself, but is
    retained in the signature for the IdCollisionError message and
    forward-compat (e.g. P3.5 LLM source may want sidecar metadata).
    """
    base_id = _mint_base_id(p)
    existing_at_base = existing_by_id.get(base_id)
    if existing_at_base is None:
        return base_id

    if (
        _annotation_tuple(existing_at_base)[:3] == _planned_tuple(p)[:3]
        and existing_at_base.match_text == p.match_text
    ):
        if existing_at_base.status is not Status.SUPERSEDED:
            raise ValueError(
                "merge_planned should have skipped a non-superseded match "
                f"(annotation {existing_at_base.id!r} is "
                f"{existing_at_base.status.value!r})"
            )
        n = 2
        while f"{base_id}-{n}" in existing_by_id:
            n += 1
        return f"{base_id}-{n}"

    raise IdCollisionError(
        f"base_id {base_id!r} occupied by unrelated 4-tuple "
        f"(existing source={existing_at_base.source!r}, "
        f"planned source={p.source_name!r}); bump hash slice length"
    )
```

In `merge_planned`, build `existing_by_id` once and add each newly
constructed Annotation to it as the loop iterates. This keeps the
map consistent for both the `.get(base_id)` semantic check (needs a
real Annotation to read `.status`, `.source`, etc.) and the
`f"{base_id}-{n}" in existing_by_id` suffix-probe membership test:

```python
    existing_by_id: dict[str, Annotation] = {
        a.id: a for a in sidecar.annotations
    }
    out_annotations = list(sidecar.annotations)
    written: list[Annotation] = []
    for p in planned:
        # ... existing 4-tuple skip / dedupe logic unchanged ...
        new_id = mint_id(sidecar, p, existing_by_id=existing_by_id)
        new_ann = _build_annotation(new_id, p, actor=actor, now=now)
        existing_by_id[new_id] = new_ann   # <-- real Annotation, not a sentinel
        out_annotations.append(new_ann)
        written.append(new_ann)
    new_sidecar = replace(sidecar, annotations=tuple(out_annotations))
    return new_sidecar, written
```

The exact placement: locate the existing per-planned-row body inside
`merge_planned`, insert the `existing_by_id` initialisation before
the loop, and add `existing_by_id[new_id] = new_ann` immediately
after the new annotation is built. No sentinel values; the map only
ever contains real Annotation instances.

- [ ] **Step 6: Update the existing audit-merge test**

Edit `science/tests/test_annotation_audit_merge.py`. Find the
`pytest.raises(AssertionError)` for the mixed-sources case (search
for `AssertionError` in the file) and change to
`pytest.raises(ValueError)`. The expected message now contains
`"single-source"` rather than the old assertion text.

```bash
grep -n "AssertionError" science/tests/test_annotation_audit_merge.py
```

For each match, update from:
```python
with pytest.raises(AssertionError, match="single-source"):
```
to:
```python
with pytest.raises(ValueError, match="single-source"):
```

- [ ] **Step 7: Run new + updated tests to verify they pass**

Run:
```bash
cd science && uv run pytest \
    tests/test_audit_invariant_value_error.py \
    tests/test_audit_mint_id_set_hoist.py \
    tests/test_annotation_audit_merge.py -v
```
Expected: PASS on all.

- [ ] **Step 8: Run full annotation suite to confirm no regressions**

Run: `cd science && uv run pytest tests/ -q -k "annotation or annotate"`
Expected: green.

- [ ] **Step 9: Commit**

```bash
git add science/src/science_tool/annotation/audit.py \
        science/tests/test_annotation_audit_merge.py \
        science/tests/test_audit_invariant_value_error.py \
        science/tests/test_audit_mint_id_set_hoist.py
git commit -m "refactor(annotation/audit): assert→ValueError; hoist existing_by_id map (O(1) mint_id)"
```

---

### Task 5: Tighten `lifecycle.mutate_status` (Decision 12)

**Files:**
- Modify: `science/src/science_tool/annotation/lifecycle.py`
- Test: `science/tests/test_lifecycle_open_source_guard.py`

Per spec Decision 12, author transitions to `ack`/`fixed`/`dismissed`
require the source status to be `OPEN`. Current behavior permits
`SUPERSEDED → ack/fixed/dismissed` which contradicts the source spec
(superseded means "the prose moved on"; resurrecting via author CRUD
is wrong). The auto `* → SUPERSEDED` transition stays unchanged.

- [ ] **Step 1: Write the failing tests**

Create `science/tests/test_lifecycle_open_source_guard.py`:

```python
"""mutate_status: author transitions require source==OPEN; auto→SUPERSEDED is free."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

import pytest

from science_tool.annotation.lifecycle import mutate_status
from science_tool.annotation.model import (
    Annotation,
    Motivation,
    SpecificResource,
    Status,
    TextQuoteSelector,
    TextualBody,
)


def _ann(status: Status) -> Annotation:
    base = Annotation(
        id="a-abc",
        target=SpecificResource(
            source="x.md",
            selector=TextQuoteSelector(exact="x", prefix="", suffix=""),
        ),
        bodies=(TextualBody(value="msg"),),
        motivation=Motivation.CLASSIFYING,
        annotation_type="bare-author-year",
        source="lint:bare-author-year-v2026-05-11",
        status=Status.OPEN,
        creator="test",
        created=datetime(2026, 5, 11, tzinfo=timezone.utc),
        content_hash="sha256:dead",
        match_text="m",
    )
    if status is Status.OPEN:
        return base
    return replace(
        base,
        status=status,
        modified=datetime(2026, 5, 11, 1, tzinfo=timezone.utc),
        modified_by="test",
    )


_NOW = datetime(2026, 5, 11, 12, tzinfo=timezone.utc)


# ---- OPEN → terminal: allowed ---------------------------------------

@pytest.mark.parametrize("target", [Status.ACK, Status.FIXED, Status.DISMISSED])
def test_open_to_terminal_allowed(target: Status) -> None:
    a = _ann(Status.OPEN)
    out = mutate_status(a, target, actor="alice", now=_NOW)
    assert out.status is target


# ---- SUPERSEDED → terminal: refused (the new guard) -----------------

@pytest.mark.parametrize("target", [Status.ACK, Status.FIXED, Status.DISMISSED])
def test_superseded_to_terminal_refused(target: Status) -> None:
    a = _ann(Status.SUPERSEDED)
    with pytest.raises(ValueError, match="only 'open'"):
        mutate_status(a, target, actor="alice", now=_NOW)


# ---- Existing terminal-state refusals: still raise ------------------

@pytest.mark.parametrize("source", [Status.ACK, Status.FIXED, Status.DISMISSED])
@pytest.mark.parametrize("target", [Status.ACK, Status.FIXED, Status.DISMISSED])
def test_terminal_to_terminal_refused(source: Status, target: Status) -> None:
    a = _ann(source)
    with pytest.raises(ValueError, match="terminal status"):
        mutate_status(a, target, actor="alice", now=_NOW)


# ---- * → SUPERSEDED: always allowed --------------------------------

@pytest.mark.parametrize(
    "source",
    [Status.OPEN, Status.ACK, Status.FIXED, Status.DISMISSED, Status.SUPERSEDED],
)
def test_any_to_superseded_allowed(source: Status) -> None:
    a = _ann(source)
    out = mutate_status(a, Status.SUPERSEDED, actor="auto", now=_NOW)
    assert out.status is Status.SUPERSEDED


# ---- Transition to OPEN always refused ------------------------------

def test_transition_to_open_refused() -> None:
    a = _ann(Status.ACK)
    with pytest.raises(ValueError, match="status flows forward only"):
        mutate_status(a, Status.OPEN, actor="alice", now=_NOW)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science && uv run pytest tests/test_lifecycle_open_source_guard.py -v`
Expected: the `test_superseded_to_terminal_refused` parametrized cases
all FAIL (current code allows the transition); other tests pass.

- [ ] **Step 3: Tighten `mutate_status`**

Edit `science/src/science_tool/annotation/lifecycle.py`. Replace the
current guard block:

```python
    if new_status is Status.OPEN:
        raise ValueError("cannot transition to 'open'; status flows forward only")
    if new_status is not Status.SUPERSEDED and annotation.status in _TERMINAL_STATES:
        raise ValueError(
            f"annotation {annotation.id!r} is already in terminal status "
            f"{annotation.status.value!r}"
        )
```

with:

```python
    if new_status is Status.OPEN:
        raise ValueError("cannot transition to 'open'; status flows forward only")
    if new_status is not Status.SUPERSEDED:
        if annotation.status in _TERMINAL_STATES:
            raise ValueError(
                f"annotation {annotation.id!r} is already in terminal status "
                f"{annotation.status.value!r}"
            )
        if annotation.status is not Status.OPEN:
            # Only superseded reaches here (terminals handled above).
            raise ValueError(
                f"cannot {new_status.value} annotation {annotation.id!r} "
                f"in status {annotation.status.value!r}; only 'open' "
                "annotations accept author transitions"
            )
```

The terminal-specific message is preserved (more informative for the
common case); the new "only 'open'" message is reserved for
SUPERSEDED-source attempts.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && uv run pytest tests/test_lifecycle_open_source_guard.py -v`
Expected: PASS (all parametrized cases).

- [ ] **Step 5: Confirm pre-existing lifecycle tests still pass**

Run: `cd science && uv run pytest tests/ -q -k "lifecycle"`
Expected: green. (P3.0 lifecycle tests cover OPEN→* and terminal
refusal; both branches survive the change.)

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/annotation/lifecycle.py \
        science/tests/test_lifecycle_open_source_guard.py
git commit -m "feat(annotation/lifecycle): require OPEN source for author transitions"
```

---

### Task 6: `query.iter_sidecars` + `SidecarParseError`

**Files:**
- Create: `science/src/science_tool/annotation/query.py`
- Test: `science/tests/test_query_iter_sidecars.py`

Bootstrap the new query module with the project walk and the parse-
error wrapping. Subsequent tasks (7, 8, 9) extend this same file.

- [ ] **Step 1: Write the failing tests**

Create `science/tests/test_query_iter_sidecars.py`:

```python
"""iter_sidecars walks *.anno.trig; wraps parse failures in SidecarParseError."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from science_tool.annotation.io import write_sidecar
from science_tool.annotation.model import (
    Annotation,
    Motivation,
    Sidecar,
    SpecificResource,
    Status,
    TextQuoteSelector,
    TextualBody,
)
from science_tool.annotation.query import (
    SidecarParseError,
    iter_sidecars,
)


def _ann(id_: str = "a-abc") -> Annotation:
    return Annotation(
        id=id_,
        target=SpecificResource(
            source="x.md",
            selector=TextQuoteSelector(exact="x", prefix="", suffix=""),
        ),
        bodies=(TextualBody(value="m"),),
        motivation=Motivation.CLASSIFYING,
        annotation_type="bare-author-year",
        source="lint:bare-author-year-v2026-05-11",
        status=Status.OPEN,
        creator="t",
        created=datetime(2026, 5, 11, tzinfo=timezone.utc),
        content_hash="sha256:d",
        match_text="m",
    )


def test_iter_sidecars_yields_each_file(tmp_path: Path) -> None:
    a = tmp_path / "a.anno.trig"
    write_sidecar(a, Sidecar(annotations=(_ann("a-1"),)))
    sub = tmp_path / "sub"
    sub.mkdir()
    b = sub / "b.anno.trig"
    write_sidecar(b, Sidecar(annotations=(_ann("a-2"),)))

    paths = sorted(p for p, _s in iter_sidecars(tmp_path))
    assert paths == sorted([a, b])


def test_iter_sidecars_skips_non_sidecar_files(tmp_path: Path) -> None:
    write_sidecar(
        tmp_path / "a.anno.trig", Sidecar(annotations=(_ann("a-1"),)),
    )
    (tmp_path / "junk.txt").write_text("nope")
    (tmp_path / "x.trig").write_text("@prefix x: <x> .")  # wrong suffix
    paths = [p for p, _s in iter_sidecars(tmp_path)]
    assert [p.name for p in paths] == ["a.anno.trig"]


def test_iter_sidecars_empty_root_yields_nothing(tmp_path: Path) -> None:
    assert list(iter_sidecars(tmp_path)) == []


def test_iter_sidecars_wraps_parse_error(tmp_path: Path) -> None:
    bad = tmp_path / "bad.anno.trig"
    bad.write_text("THIS IS NOT VALID TRIG", encoding="utf-8")
    with pytest.raises(SidecarParseError) as excinfo:
        list(iter_sidecars(tmp_path))
    assert excinfo.value.sidecar_path == bad
    assert excinfo.value.cause is not None
    # `cause` carries the underlying rdflib / ValueError / etc.
    assert isinstance(excinfo.value.cause, Exception)


def test_iter_sidecars_returns_parsed_sidecar(tmp_path: Path) -> None:
    p = tmp_path / "x.anno.trig"
    write_sidecar(p, Sidecar(annotations=(_ann("a-xyz"),)))
    results = list(iter_sidecars(tmp_path))
    assert len(results) == 1
    _path, sidecar = results[0]
    assert sidecar.annotations[0].id == "a-xyz"


def test_read_sidecar_strict_wraps_parse_error(tmp_path: Path) -> None:
    """Single-file read goes through the same SidecarParseError wrap."""
    from science_tool.annotation.query import read_sidecar_strict

    bad = tmp_path / "bad.anno.trig"
    bad.write_text("THIS IS NOT VALID TRIG", encoding="utf-8")
    with pytest.raises(SidecarParseError) as excinfo:
        read_sidecar_strict(bad)
    assert excinfo.value.sidecar_path == bad
    assert isinstance(excinfo.value.cause, Exception)


def test_read_sidecar_strict_returns_parsed(tmp_path: Path) -> None:
    from science_tool.annotation.query import read_sidecar_strict

    p = tmp_path / "x.anno.trig"
    write_sidecar(p, Sidecar(annotations=(_ann("a-good"),)))
    sidecar = read_sidecar_strict(p)
    assert sidecar.annotations[0].id == "a-good"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science && uv run pytest tests/test_query_iter_sidecars.py -v`
Expected: FAIL — `No module named 'science_tool.annotation.query'`.

- [ ] **Step 3: Create `query.py` with `iter_sidecars` + `SidecarParseError`**

Create `science/src/science_tool/annotation/query.py`:

```python
# science/src/science_tool/annotation/query.py
"""Read-side annotation query module.

Public surface (built up across P3.3 tasks 6–9):
- iter_sidecars(root)        — Task 6 (this file)
- resolve_id(root, id_arg)   — Task 7
- filter_annotations(...)    — Task 8
- compute_stats(sidecars)    — Task 9
- git_changed_markdown(...)  — Task 8

See spec docs/plans/2026-05-11-annotation-system-p3.3-spec.md
§"Read concerns: query.py".
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional

from science_tool.annotation.io import read_sidecar
from science_tool.annotation.model import Sidecar


# ---- Errors ----------------------------------------------------------

class SidecarParseError(Exception):
    """Raised by iter_sidecars when a sidecar fails to parse.

    Carries the offending file path and the underlying exception so
    the CLI can produce a useful ClickException message.
    """

    def __init__(self, sidecar_path: Path, cause: Exception) -> None:
        self.sidecar_path = sidecar_path
        self.cause = cause
        super().__init__(
            f"failed to parse sidecar {sidecar_path}: "
            f"{type(cause).__name__}: {cause}"
        )


# ---- Single-sidecar read with parse-error wrapping -----------------

def read_sidecar_strict(path: Path) -> Sidecar:
    """Read one sidecar; wrap any parse exception in SidecarParseError.

    Used by every code path in this module that loads a sidecar
    (iter_sidecars, resolve_id qualified lookups, etc.) and by
    cli._scope_to_sidecars when PATH names a single .md or
    .anno.trig file. Centralising the wrap means callers only ever
    need to catch SidecarParseError, not the underlying rdflib /
    ValueError / FileNotFoundError zoo.
    """
    try:
        return read_sidecar(path)
    except Exception as exc:
        raise SidecarParseError(path, exc) from exc


# ---- Walk ------------------------------------------------------------

def iter_sidecars(root: Path) -> Iterator[tuple[Path, Sidecar]]:
    """Yield (sidecar_path, parsed Sidecar) for every *.anno.trig under root.

    Walks recursively. Parse failures propagate as SidecarParseError
    via `read_sidecar_strict`; iteration stops at the first failure.
    """
    for path in sorted(root.rglob("*.anno.trig")):
        yield path, read_sidecar_strict(path)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && uv run pytest tests/test_query_iter_sidecars.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/annotation/query.py \
        science/tests/test_query_iter_sidecars.py
git commit -m "feat(annotation/query): iter_sidecars + SidecarParseError"
```

---

### Task 7: `query.resolve_id` + ID resolution algorithm

**Files:**
- Modify: `science/src/science_tool/annotation/query.py`
- Test: `science/tests/test_query_resolve_id.py`

Adds the ID resolution machinery: bare frag, bare-stem qualifier,
rel-path qualifier. `AmbiguousAnnotationId.candidates` always
populated with rel-path-qualified IDs.

- [ ] **Step 1: Write the failing tests**

Create `science/tests/test_query_resolve_id.py`:

```python
"""resolve_id covers bare frag, bare-stem qualifier, rel-path qualifier."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from science_tool.annotation.io import write_sidecar
from science_tool.annotation.model import (
    Annotation,
    Motivation,
    Sidecar,
    SpecificResource,
    Status,
    TextQuoteSelector,
    TextualBody,
)
from science_tool.annotation.query import (
    AmbiguousAnnotationId,
    AnnotationNotFound,
    ResolvedAnnotation,
    resolve_id,
)


def _ann(id_: str) -> Annotation:
    return Annotation(
        id=id_,
        target=SpecificResource(
            source="x.md",
            selector=TextQuoteSelector(exact="x", prefix="", suffix=""),
        ),
        bodies=(TextualBody(value="m"),),
        motivation=Motivation.CLASSIFYING,
        annotation_type="bare-author-year",
        source="lint:bare-author-year-v2026-05-11",
        status=Status.OPEN,
        creator="t",
        created=datetime(2026, 5, 11, tzinfo=timezone.utc),
        content_hash="sha256:d",
        match_text="m",
    )


def _make(root: Path, relpath: str, ann_ids: list[str]) -> Path:
    p = root / relpath
    p.parent.mkdir(parents=True, exist_ok=True)
    write_sidecar(p, Sidecar(annotations=tuple(_ann(i) for i in ann_ids)))
    return p


# ---- Bare frag ------------------------------------------------------

def test_bare_frag_unique(tmp_path: Path) -> None:
    sidecar = _make(tmp_path, "foo.anno.trig", ["a-aaa"])
    resolved = resolve_id(tmp_path, "a-aaa")
    assert isinstance(resolved, ResolvedAnnotation)
    assert resolved.sidecar_path == sidecar
    assert resolved.annotation.id == "a-aaa"
    assert resolved.entity_stem == "foo"
    assert resolved.entity_relpath == "foo"


def test_bare_frag_ambiguous_lists_relpath_candidates(tmp_path: Path) -> None:
    _make(tmp_path, "notes/foo.anno.trig", ["a-aaa"])
    _make(tmp_path, "appendix/foo.anno.trig", ["a-aaa"])
    with pytest.raises(AmbiguousAnnotationId) as excinfo:
        resolve_id(tmp_path, "a-aaa")
    assert sorted(excinfo.value.candidates) == [
        "appendix/foo:a-aaa",
        "notes/foo:a-aaa",
    ]


def test_bare_frag_not_found(tmp_path: Path) -> None:
    _make(tmp_path, "foo.anno.trig", ["a-aaa"])
    with pytest.raises(AnnotationNotFound):
        resolve_id(tmp_path, "a-zzz")


# ---- Bare-stem qualifier --------------------------------------------

def test_bare_stem_qualifier_unique(tmp_path: Path) -> None:
    _make(tmp_path, "foo.anno.trig", ["a-aaa"])
    resolved = resolve_id(tmp_path, "foo:a-aaa")
    assert resolved.annotation.id == "a-aaa"
    assert resolved.entity_stem == "foo"


def test_bare_stem_qualifier_ambiguous_lists_relpaths(tmp_path: Path) -> None:
    _make(tmp_path, "notes/foo.anno.trig", ["a-bbb"])
    _make(tmp_path, "appendix/foo.anno.trig", ["a-bbb"])
    with pytest.raises(AmbiguousAnnotationId) as excinfo:
        resolve_id(tmp_path, "foo:a-bbb")
    assert sorted(excinfo.value.candidates) == [
        "appendix/foo:a-bbb",
        "notes/foo:a-bbb",
    ]


def test_bare_stem_qualifier_missing_sidecar(tmp_path: Path) -> None:
    _make(tmp_path, "foo.anno.trig", ["a-aaa"])
    with pytest.raises(AnnotationNotFound):
        resolve_id(tmp_path, "missing:a-aaa")


def test_bare_stem_qualifier_missing_frag(tmp_path: Path) -> None:
    _make(tmp_path, "foo.anno.trig", ["a-aaa"])
    with pytest.raises(AnnotationNotFound):
        resolve_id(tmp_path, "foo:a-zzz")


# ---- Rel-path qualifier ---------------------------------------------

def test_rel_path_qualifier_hit(tmp_path: Path) -> None:
    sidecar = _make(tmp_path, "notes/foo.anno.trig", ["a-aaa"])
    resolved = resolve_id(tmp_path, "notes/foo:a-aaa")
    assert resolved.sidecar_path == sidecar
    assert resolved.entity_relpath == "notes/foo"


def test_rel_path_qualifier_disambiguates(tmp_path: Path) -> None:
    _make(tmp_path, "notes/foo.anno.trig", ["a-bbb"])
    _make(tmp_path, "appendix/foo.anno.trig", ["a-bbb"])
    # Bare-stem form is ambiguous; rel-path picks one.
    resolved = resolve_id(tmp_path, "notes/foo:a-bbb")
    assert resolved.entity_relpath == "notes/foo"


def test_rel_path_qualifier_missing_sidecar(tmp_path: Path) -> None:
    with pytest.raises(AnnotationNotFound):
        resolve_id(tmp_path, "notes/missing:a-aaa")


# ---- Returned sidecar is the parsed sidecar (not a re-read) ---------

def test_resolved_carries_full_sidecar(tmp_path: Path) -> None:
    _make(tmp_path, "foo.anno.trig", ["a-aaa", "a-bbb"])
    resolved = resolve_id(tmp_path, "a-aaa")
    # crud.apply_status_change relies on this.
    assert {a.id for a in resolved.sidecar.annotations} == {"a-aaa", "a-bbb"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science && uv run pytest tests/test_query_resolve_id.py -v`
Expected: FAIL — symbols don't yet exist in `query.py`.

- [ ] **Step 3: Add types and `resolve_id` to `query.py`**

Edit `science/src/science_tool/annotation/query.py`. Add the
following imports near the top (after existing imports):

```python
from science_tool.annotation.model import Annotation
```

Append (after `iter_sidecars`):

```python
# ---- Lookup result + errors -----------------------------------------

@dataclass(frozen=True)
class ResolvedAnnotation:
    sidecar_path: Path
    sidecar: Sidecar
    annotation: Annotation
    entity_stem: str       # bare markdown stem ("foo")
    entity_relpath: str    # rel-to-root, no suffix ("notes/foo")


class AnnotationLookupError(Exception):
    """Base class for resolve_id errors."""


class AnnotationNotFound(AnnotationLookupError):
    """No annotation matched the given handle."""


class AmbiguousAnnotationId(AnnotationLookupError):
    """Bare frag or bare-stem qualifier matched more than one sidecar.

    `candidates` is always populated with rel-path-qualified IDs so
    the user has unambiguous handles to retry with.
    """

    def __init__(self, message: str, candidates: tuple[str, ...]) -> None:
        super().__init__(message)
        self.candidates = candidates


# ---- Resolution -----------------------------------------------------

def entity_relpath_for_sidecar(sidecar_path: Path, root: Path) -> str:
    """Public helper: rel-path-without-suffix for a sidecar under `root`.

    `<root>/notes/foo.anno.trig`, `<root>` → `"notes/foo"`. Used by
    `cli.py:list_cmd` to render qualified IDs in table/JSON output.
    """
    rel = sidecar_path.resolve().relative_to(root.resolve())
    name = rel.name
    if name.endswith(".anno.trig"):
        name = name[: -len(".anno.trig")]
    return rel.with_name(name).as_posix()


def entity_stem_for_sidecar(sidecar_path: Path) -> str:
    """Public helper: bare stem for a sidecar (filename minus .anno.trig)."""
    name = sidecar_path.name
    if name.endswith(".anno.trig"):
        return name[: -len(".anno.trig")]
    return sidecar_path.stem


def _qualified(sidecar_path: Path, root: Path, frag: str) -> str:
    return f"{entity_relpath_for_sidecar(sidecar_path, root)}:{frag}"


def _build_resolved(
    sidecar_path: Path,
    sidecar: Sidecar,
    annotation: Annotation,
    root: Path,
) -> ResolvedAnnotation:
    return ResolvedAnnotation(
        sidecar_path=sidecar_path,
        sidecar=sidecar,
        annotation=annotation,
        entity_stem=entity_stem_for_sidecar(sidecar_path),
        entity_relpath=entity_relpath_for_sidecar(sidecar_path, root),
    )


def resolve_id(root: Path, id_arg: str) -> ResolvedAnnotation:
    """Resolve `a-7f3a`, `foo:a-7f3a`, or `notes/foo:a-7f3a` to a sidecar+row.

    See spec §"ID resolution algorithm" for the full contract.
    """
    if ":" in id_arg:
        entity_key, frag = id_arg.split(":", 1)
        if "/" in entity_key:
            return _resolve_rel_path(root, entity_key, frag)
        return _resolve_bare_stem(root, entity_key, frag)
    return _resolve_bare_frag(root, id_arg)


def _resolve_rel_path(
    root: Path, entity_key: str, frag: str,
) -> ResolvedAnnotation:
    sidecar_path = (root / f"{entity_key}.anno.trig").resolve()
    if not sidecar_path.exists():
        raise AnnotationNotFound(
            f"no sidecar at {sidecar_path}"
        )
    sidecar = read_sidecar_strict(sidecar_path)
    for ann in sidecar.annotations:
        if ann.id == frag:
            return _build_resolved(sidecar_path, sidecar, ann, root)
    raise AnnotationNotFound(
        f"sidecar {sidecar_path.name} has no annotation {frag!r}"
    )


def _resolve_bare_stem(
    root: Path, entity_key: str, frag: str,
) -> ResolvedAnnotation:
    matches: list[Path] = sorted(
        root.rglob(f"{entity_key}.anno.trig"),
    )
    if not matches:
        raise AnnotationNotFound(
            f"no sidecar with stem {entity_key!r} under {root}"
        )
    if len(matches) > 1:
        candidates = tuple(
            sorted(_qualified(p, root, frag) for p in matches)
        )
        raise AmbiguousAnnotationId(
            f"ambiguous: {entity_key!r}:{frag} matches multiple sidecars; "
            "retry with one of the rel-path-qualified forms in .candidates",
            candidates=candidates,
        )
    sidecar_path = matches[0]
    sidecar = read_sidecar_strict(sidecar_path)
    for ann in sidecar.annotations:
        if ann.id == frag:
            return _build_resolved(sidecar_path, sidecar, ann, root)
    raise AnnotationNotFound(
        f"sidecar {sidecar_path.name} has no annotation {frag!r}"
    )


def _resolve_bare_frag(root: Path, frag: str) -> ResolvedAnnotation:
    hits: list[tuple[Path, Sidecar, Annotation]] = []
    for path, sidecar in iter_sidecars(root):
        for ann in sidecar.annotations:
            if ann.id == frag:
                hits.append((path, sidecar, ann))
    if not hits:
        raise AnnotationNotFound(
            f"no annotation matching {frag!r} under {root}"
        )
    if len(hits) > 1:
        candidates = tuple(
            sorted(_qualified(p, root, frag) for p, _s, _a in hits)
        )
        raise AmbiguousAnnotationId(
            f"ambiguous: {frag!r} matches multiple sidecars; "
            "retry with one of the rel-path-qualified forms in .candidates",
            candidates=candidates,
        )
    path, sidecar, ann = hits[0]
    return _build_resolved(path, sidecar, ann, root)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && uv run pytest tests/test_query_resolve_id.py -v`
Expected: PASS (11 tests).

- [ ] **Step 5: Run prior query tests to confirm no regression**

Run: `cd science && uv run pytest tests/test_query_iter_sidecars.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/annotation/query.py \
        science/tests/test_query_resolve_id.py
git commit -m "feat(annotation/query): resolve_id with bare/stem/rel-path qualifiers"
```

---

### Task 8: `query.filter_annotations` + `git_changed_markdown`

**Files:**
- Modify: `science/src/science_tool/annotation/query.py`
- Test: `science/tests/test_query_filter.py`

Adds the predicate-AND filter used by `list` and the
`--since <git-ref>` plumbing. Source patterns support trailing `*`
glob via `fnmatch`.

- [ ] **Step 1: Write the failing tests**

Create `science/tests/test_query_filter.py`:

```python
"""filter_annotations: status / source-glob / since predicates AND together."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pytest

from science_tool.annotation.io import write_sidecar
from science_tool.annotation.model import (
    Annotation,
    Motivation,
    Sidecar,
    SpecificResource,
    Status,
    TextQuoteSelector,
    TextualBody,
)
from science_tool.annotation.query import (
    filter_annotations,
    iter_sidecars,
)


def _ann(
    id_: str,
    *,
    status: Status = Status.OPEN,
    source: str = "lint:bare-author-year-v2026-05-11",
) -> Annotation:
    base = Annotation(
        id=id_,
        target=SpecificResource(
            source="x.md",
            selector=TextQuoteSelector(exact="x", prefix="", suffix=""),
        ),
        bodies=(TextualBody(value="m"),),
        motivation=Motivation.CLASSIFYING,
        annotation_type="bare-author-year",
        source=source,
        status=Status.OPEN,
        creator="t",
        created=datetime(2026, 5, 11, tzinfo=timezone.utc),
        content_hash="sha256:d",
        match_text="m",
    )
    if status is Status.OPEN:
        return base
    return replace(
        base,
        status=status,
        modified=datetime(2026, 5, 11, 1, tzinfo=timezone.utc),
        modified_by="t",
    )


def _setup(tmp_path: Path) -> None:
    write_sidecar(tmp_path / "a.anno.trig", Sidecar(annotations=(
        _ann("a-1", status=Status.OPEN),
        _ann("a-2", status=Status.ACK),
        _ann("a-3", status=Status.SUPERSEDED),
        _ann("a-4", source="marker-scanner:phase-2"),
        _ann("a-5", source="lint:short-form-ids-v2026-05-11"),
    )))


# ---- status filter --------------------------------------------------

def test_status_filter_default_open_only(tmp_path: Path) -> None:
    _setup(tmp_path)
    sidecars = list(iter_sidecars(tmp_path))
    rows = list(filter_annotations(sidecars, statuses=frozenset({Status.OPEN})))
    ids = sorted(a.id for _p, a in rows)
    # a-1 is OPEN; a-4 + a-5 are also default-OPEN (created without
    # explicit status arg)
    assert ids == ["a-1", "a-4", "a-5"]


def test_status_filter_multi(tmp_path: Path) -> None:
    _setup(tmp_path)
    sidecars = list(iter_sidecars(tmp_path))
    rows = list(filter_annotations(
        sidecars, statuses=frozenset({Status.OPEN, Status.ACK}),
    ))
    assert sorted(a.id for _p, a in rows) == ["a-1", "a-2", "a-4", "a-5"]


def test_status_filter_none_means_all(tmp_path: Path) -> None:
    _setup(tmp_path)
    sidecars = list(iter_sidecars(tmp_path))
    rows = list(filter_annotations(sidecars, statuses=None))
    assert sorted(a.id for _p, a in rows) == [
        "a-1", "a-2", "a-3", "a-4", "a-5",
    ]


# ---- source filter (glob) -------------------------------------------

def test_source_filter_exact(tmp_path: Path) -> None:
    _setup(tmp_path)
    sidecars = list(iter_sidecars(tmp_path))
    rows = list(filter_annotations(
        sidecars,
        statuses=None,
        sources=("marker-scanner:phase-2",),
    ))
    assert [a.id for _p, a in rows] == ["a-4"]


def test_source_filter_glob(tmp_path: Path) -> None:
    _setup(tmp_path)
    sidecars = list(iter_sidecars(tmp_path))
    rows = list(filter_annotations(
        sidecars, statuses=None, sources=("lint:*",),
    ))
    assert sorted(a.id for _p, a in rows) == ["a-1", "a-2", "a-3", "a-5"]


def test_source_filter_multi_pattern_or(tmp_path: Path) -> None:
    _setup(tmp_path)
    sidecars = list(iter_sidecars(tmp_path))
    rows = list(filter_annotations(
        sidecars,
        statuses=None,
        sources=("marker-scanner:*", "lint:short-form-ids-*"),
    ))
    assert sorted(a.id for _p, a in rows) == ["a-4", "a-5"]


# ---- since_changed filter -------------------------------------------

def test_since_filter_excludes_unchanged(tmp_path: Path) -> None:
    _setup(tmp_path)
    sidecars = list(iter_sidecars(tmp_path))
    rows = list(filter_annotations(
        sidecars,
        statuses=None,
        since_changed=frozenset(),  # nothing changed → no rows
    ))
    assert rows == []


def test_since_filter_includes_changed_md(tmp_path: Path) -> None:
    _setup(tmp_path)
    md_path = (tmp_path / "a.md").resolve()
    sidecars = list(iter_sidecars(tmp_path))
    rows = list(filter_annotations(
        sidecars,
        statuses=None,
        since_changed=frozenset({md_path}),
    ))
    assert len(rows) == 5  # all 5 from a.anno.trig included


# ---- AND across predicates ------------------------------------------

def test_and_across_predicates(tmp_path: Path) -> None:
    _setup(tmp_path)
    md_path = (tmp_path / "a.md").resolve()
    sidecars = list(iter_sidecars(tmp_path))
    rows = list(filter_annotations(
        sidecars,
        statuses=frozenset({Status.OPEN}),
        sources=("lint:bare-author-year-*",),
        since_changed=frozenset({md_path}),
    ))
    assert [a.id for _p, a in rows] == ["a-1"]
```

- [ ] **Step 2: Write the failing test for `git_changed_markdown`**

Create the helper test inside the same file (append):

```python
def test_git_changed_markdown_returns_paths(tmp_path: Path, monkeypatch) -> None:
    """git_changed_markdown shells out and returns absolute markdown paths."""
    from science_tool.annotation import query

    captured = {}

    def fake_run(args, **kwargs):
        captured["args"] = args
        captured["cwd"] = kwargs.get("cwd")

        class R:
            returncode = 0
            stdout = "notes/foo.md\nappendix/bar.md\nREADME\n"
            stderr = ""

        return R()

    monkeypatch.setattr(query, "_run_git", fake_run)
    out = query.git_changed_markdown(tmp_path, "main")
    assert out == frozenset({
        (tmp_path / "notes/foo.md").resolve(),
        (tmp_path / "appendix/bar.md").resolve(),
    })
    assert captured["args"][0:5] == [
        "git", "diff", "--name-only", "main...", "--",
    ]


def test_git_changed_markdown_non_repo_raises(tmp_path: Path, monkeypatch) -> None:
    from science_tool.annotation import query

    def fake_run(args, **kwargs):
        class R:
            returncode = 128
            stdout = ""
            stderr = "fatal: not a git repository"

        return R()

    monkeypatch.setattr(query, "_run_git", fake_run)
    with pytest.raises(RuntimeError, match="not a git repository"):
        query.git_changed_markdown(tmp_path, "main")
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd science && uv run pytest tests/test_query_filter.py -v`
Expected: FAIL — `filter_annotations` and `git_changed_markdown` not
defined.

- [ ] **Step 4: Add `filter_annotations` + `git_changed_markdown`**

Edit `science/src/science_tool/annotation/query.py`. Add to imports
near the top:

```python
import fnmatch
import subprocess
from typing import Iterable

from science_tool.annotation.io import markdown_for_sidecar
from science_tool.annotation.model import Status
```

Append to the end of the file:

```python
# ---- Filter ---------------------------------------------------------

def filter_annotations(
    sidecars: Iterable[tuple[Path, Sidecar]],
    *,
    statuses: Optional[frozenset[Status]] = None,
    sources: tuple[str, ...] = (),
    since_changed: Optional[frozenset[Path]] = None,
) -> Iterator[tuple[Path, Annotation]]:
    """Yield (sidecar_path, annotation) tuples matching all predicates.

    - `statuses`: None means no filter; otherwise membership test.
    - `sources`: empty tuple means no filter; otherwise OR of
      `fnmatch.fnmatchcase` patterns (supports `lint:*`).
    - `since_changed`: None means no filter; otherwise the sidecar's
      paired markdown (via `io.markdown_for_sidecar`) must be in the
      set (paths compared after `.resolve()`).
    """
    for sidecar_path, sidecar in sidecars:
        if since_changed is not None:
            md_path = markdown_for_sidecar(sidecar_path).resolve()
            if md_path not in since_changed:
                continue
        for ann in sidecar.annotations:
            if statuses is not None and ann.status not in statuses:
                continue
            if sources and not _source_matches(ann.source, sources):
                continue
            yield sidecar_path, ann


def _source_matches(source: str, patterns: tuple[str, ...]) -> bool:
    return any(fnmatch.fnmatchcase(source, pat) for pat in patterns)


# ---- --since plumbing ----------------------------------------------

def _run_git(args: list[str], *, cwd: Path) -> subprocess.CompletedProcess:
    """Indirection seam for tests to monkeypatch."""
    return subprocess.run(
        args, cwd=str(cwd), capture_output=True, text=True, check=False,
    )


def git_changed_markdown(root: Path, ref: str) -> frozenset[Path]:
    """Return absolute paths of *.md files changed since `ref` (`<ref>...HEAD`).

    Shells out to `git diff --name-only <ref>... -- '*.md'`. Empty
    git output → empty set. Non-zero git exit → RuntimeError carrying
    git's stderr (CLI layer converts to ClickException).
    """
    args = [
        "git", "diff", "--name-only", f"{ref}...", "--", "*.md",
    ]
    proc = _run_git(args, cwd=root)
    if proc.returncode != 0:
        raise RuntimeError(
            f"git diff failed (rc={proc.returncode}): {proc.stderr.strip()}"
        )
    out: set[Path] = set()
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line.endswith(".md"):
            continue
        out.add((root / line).resolve())
    return frozenset(out)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd science && uv run pytest tests/test_query_filter.py -v`
Expected: PASS (11 tests).

- [ ] **Step 6: Run prior query tests to confirm no regression**

Run: `cd science && uv run pytest tests/test_query_iter_sidecars.py science/tests/test_query_resolve_id.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add science/src/science_tool/annotation/query.py \
        science/tests/test_query_filter.py
git commit -m "feat(annotation/query): filter_annotations + git_changed_markdown"
```

---

### Task 9: `query.compute_stats` + `StatsReport`

**Files:**
- Modify: `science/src/science_tool/annotation/query.py`
- Test: `science/tests/test_query_stats.py`

Aggregates by status, source, and annotation type. Each row
contributes to all three dimensions independently. Output dicts are
descending-sorted (by count, then by key for stability).

- [ ] **Step 1: Write the failing tests**

Create `science/tests/test_query_stats.py`:

```python
"""compute_stats: three independent axes, one row contributes to all three."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from science_tool.annotation.io import write_sidecar
from science_tool.annotation.model import (
    Annotation,
    Motivation,
    Sidecar,
    SpecificResource,
    Status,
    TextQuoteSelector,
    TextualBody,
)
from science_tool.annotation.query import (
    StatsReport,
    compute_stats,
    iter_sidecars,
)


def _ann(
    id_: str,
    *,
    status: Status = Status.OPEN,
    source: str = "lint:bare-author-year-v2026-05-11",
    annotation_type: str = "bare-author-year",
) -> Annotation:
    base = Annotation(
        id=id_,
        target=SpecificResource(
            source="x.md",
            selector=TextQuoteSelector(exact="x", prefix="", suffix=""),
        ),
        bodies=(TextualBody(value="m"),),
        motivation=Motivation.CLASSIFYING,
        annotation_type=annotation_type,
        source=source,
        status=Status.OPEN,
        creator="t",
        created=datetime(2026, 5, 11, tzinfo=timezone.utc),
        content_hash="sha256:d",
        match_text="m",
    )
    if status is Status.OPEN:
        return base
    return replace(
        base,
        status=status,
        modified=datetime(2026, 5, 11, 1, tzinfo=timezone.utc),
        modified_by="t",
    )


def test_empty_corpus_returns_zero_report(tmp_path: Path) -> None:
    sidecars = list(iter_sidecars(tmp_path))
    report = compute_stats(sidecars)
    assert isinstance(report, StatsReport)
    assert report.total_annotations == 0
    assert report.total_sidecars == 0
    assert report.by_status == {}
    assert report.by_source == {}
    assert report.by_type == {}


def test_three_axes_independent(tmp_path: Path) -> None:
    write_sidecar(tmp_path / "a.anno.trig", Sidecar(annotations=(
        _ann("a-1", status=Status.OPEN, source="lint:foo-v1", annotation_type="bare-author-year"),
        _ann("a-2", status=Status.OPEN, source="lint:foo-v1", annotation_type="bare-author-year"),
        _ann("a-3", status=Status.ACK, source="marker-scanner:phase-2", annotation_type="unverified"),
    )))
    sidecars = list(iter_sidecars(tmp_path))
    report = compute_stats(sidecars)
    assert report.total_annotations == 3
    assert report.total_sidecars == 1
    assert report.by_status == {Status.OPEN: 2, Status.ACK: 1}
    assert report.by_source == {"lint:foo-v1": 2, "marker-scanner:phase-2": 1}
    assert report.by_type == {"bare-author-year": 2, "unverified": 1}


def test_descending_sort_within_each_axis(tmp_path: Path) -> None:
    write_sidecar(tmp_path / "a.anno.trig", Sidecar(annotations=(
        _ann("a-1", source="lint:c-v1"),
        _ann("a-2", source="lint:b-v1"),
        _ann("a-3", source="lint:b-v1"),
        _ann("a-4", source="lint:a-v1"),
        _ann("a-5", source="lint:a-v1"),
        _ann("a-6", source="lint:a-v1"),
    )))
    sidecars = list(iter_sidecars(tmp_path))
    report = compute_stats(sidecars)
    # by_source must iterate in descending count order (and key
    # tiebreak is alphabetical for stability).
    assert list(report.by_source.items()) == [
        ("lint:a-v1", 3),
        ("lint:b-v1", 2),
        ("lint:c-v1", 1),
    ]


def test_total_sidecars_counts_files(tmp_path: Path) -> None:
    write_sidecar(tmp_path / "a.anno.trig", Sidecar(annotations=(_ann("a-1"),)))
    write_sidecar(tmp_path / "b.anno.trig", Sidecar(annotations=(_ann("a-2"),)))
    sidecars = list(iter_sidecars(tmp_path))
    report = compute_stats(sidecars)
    assert report.total_sidecars == 2
    assert report.total_annotations == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science && uv run pytest tests/test_query_stats.py -v`
Expected: FAIL — `compute_stats` and `StatsReport` not defined.

- [ ] **Step 3: Add `StatsReport` + `compute_stats`**

Edit `science/src/science_tool/annotation/query.py`. Append:

```python
# ---- Stats ----------------------------------------------------------

@dataclass(frozen=True)
class StatsReport:
    by_status: dict[Status, int]
    by_source: dict[str, int]
    by_type: dict[str, int]
    total_annotations: int
    total_sidecars: int


def compute_stats(
    sidecars: Iterable[tuple[Path, Sidecar]],
) -> StatsReport:
    """Three independent aggregations; one row contributes to all three.

    Each output dict iterates in descending-count order (key
    tiebroken alphabetically) for stable display.
    """
    by_status: dict[Status, int] = {}
    by_source: dict[str, int] = {}
    by_type: dict[str, int] = {}
    sidecar_count = 0
    annotation_count = 0
    for _path, sidecar in sidecars:
        sidecar_count += 1
        for ann in sidecar.annotations:
            annotation_count += 1
            by_status[ann.status] = by_status.get(ann.status, 0) + 1
            by_source[ann.source] = by_source.get(ann.source, 0) + 1
            by_type[ann.annotation_type] = by_type.get(ann.annotation_type, 0) + 1
    return StatsReport(
        by_status=_sorted_desc(by_status, key_to_str=lambda s: s.value),
        by_source=_sorted_desc(by_source, key_to_str=lambda s: s),
        by_type=_sorted_desc(by_type, key_to_str=lambda s: s),
        total_annotations=annotation_count,
        total_sidecars=sidecar_count,
    )


def _sorted_desc(d: dict, *, key_to_str) -> dict:
    items = sorted(d.items(), key=lambda kv: (-kv[1], key_to_str(kv[0])))
    return dict(items)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && uv run pytest tests/test_query_stats.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Run all query tests to confirm green**

Run: `cd science && uv run pytest tests/test_query_*.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/annotation/query.py \
        science/tests/test_query_stats.py
git commit -m "feat(annotation/query): compute_stats + StatsReport"
```

---

### Task 10: `crud.apply_status_change`

**Files:**
- Create: `science/src/science_tool/annotation/crud.py`
- Test: `science/tests/test_crud_apply.py`

The single orchestrator function powering `ack`, `dismiss`, and
`fix`. Handles dirty-tree guard, lifecycle invocation, atomic
rewrite. `_resolve_actor` helper centralises the
`flag → git config user.email → fail` chain.

- [ ] **Step 1: Write the failing tests**

Create `science/tests/test_crud_apply.py`:

```python
"""crud.apply_status_change: orchestrator for ack/dismiss/fix."""

from __future__ import annotations

import subprocess
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pytest

from science_tool.annotation.crud import (
    CrudRefusedDirty,
    CrudResult,
    apply_status_change,
)
from science_tool.annotation.io import read_sidecar, write_sidecar
from science_tool.annotation.model import (
    Annotation,
    Motivation,
    Sidecar,
    SpecificResource,
    Status,
    TextQuoteSelector,
    TextualBody,
)


def _ann(id_: str, status: Status = Status.OPEN) -> Annotation:
    base = Annotation(
        id=id_,
        target=SpecificResource(
            source="x.md",
            selector=TextQuoteSelector(exact="x", prefix="", suffix=""),
        ),
        bodies=(TextualBody(value="m"),),
        motivation=Motivation.CLASSIFYING,
        annotation_type="bare-author-year",
        source="lint:bare-author-year-v2026-05-11",
        status=Status.OPEN,
        creator="t",
        created=datetime(2026, 5, 11, tzinfo=timezone.utc),
        content_hash="sha256:d",
        match_text="m",
    )
    if status is Status.OPEN:
        return base
    return replace(
        base,
        status=status,
        modified=datetime(2026, 5, 11, 1, tzinfo=timezone.utc),
        modified_by="t",
    )


_NOW = datetime(2026, 5, 11, 12, tzinfo=timezone.utc)


def _git_init(root: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=root, check=True)


def _setup_clean(tmp_path: Path) -> Path:
    _git_init(tmp_path)
    sidecar_path = tmp_path / "foo.anno.trig"
    write_sidecar(sidecar_path, Sidecar(annotations=(_ann("a-aaa"),)))
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "init"], cwd=tmp_path, check=True,
    )
    return sidecar_path


# ---- happy paths ----------------------------------------------------

def test_open_to_ack(tmp_path: Path) -> None:
    _setup_clean(tmp_path)
    result = apply_status_change(
        tmp_path, "a-aaa", Status.ACK,
        actor="alice", now=_NOW,
    )
    assert isinstance(result, CrudResult)
    assert result.qualified_id == "foo:a-aaa"
    assert result.prior_status is Status.OPEN
    assert result.new_status is Status.ACK


def test_open_to_fixed(tmp_path: Path) -> None:
    _setup_clean(tmp_path)
    result = apply_status_change(
        tmp_path, "a-aaa", Status.FIXED,
        actor="alice", now=_NOW,
    )
    assert result.new_status is Status.FIXED


def test_open_to_dismissed_with_reason_persists(tmp_path: Path) -> None:
    sidecar_path = _setup_clean(tmp_path)
    apply_status_change(
        tmp_path, "a-aaa", Status.DISMISSED,
        actor="alice", now=_NOW, reason="not actionable",
    )
    sidecar = read_sidecar(sidecar_path)
    ann = sidecar.annotations[0]
    assert ann.status is Status.DISMISSED
    assert ann.description == "not actionable"


def test_prov_was_revision_of_records_prior_status(tmp_path: Path) -> None:
    sidecar_path = _setup_clean(tmp_path)
    apply_status_change(
        tmp_path, "a-aaa", Status.ACK, actor="alice", now=_NOW,
    )
    sidecar = read_sidecar(sidecar_path)
    ann = sidecar.annotations[0]
    assert len(ann.prior_states) == 1
    assert ann.prior_states[0].status is Status.OPEN


# ---- terminal-state refusals ---------------------------------------

@pytest.mark.parametrize(
    "source_status,target",
    [
        (Status.ACK, Status.FIXED),
        (Status.FIXED, Status.DISMISSED),
        (Status.DISMISSED, Status.ACK),
    ],
)
def test_terminal_state_refused(
    tmp_path: Path, source_status: Status, target: Status,
) -> None:
    _git_init(tmp_path)
    sidecar_path = tmp_path / "foo.anno.trig"
    write_sidecar(
        sidecar_path,
        Sidecar(annotations=(_ann("a-aaa", status=source_status),)),
    )
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=tmp_path, check=True)
    with pytest.raises(ValueError, match="terminal status"):
        apply_status_change(
            tmp_path, "a-aaa", target, actor="alice", now=_NOW,
        )


# ---- non-OPEN-source (superseded) refusal --------------------------

@pytest.mark.parametrize("target", [Status.ACK, Status.FIXED, Status.DISMISSED])
def test_superseded_source_refused(tmp_path: Path, target: Status) -> None:
    _git_init(tmp_path)
    sidecar_path = tmp_path / "foo.anno.trig"
    write_sidecar(
        sidecar_path,
        Sidecar(annotations=(_ann("a-aaa", status=Status.SUPERSEDED),)),
    )
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=tmp_path, check=True)
    with pytest.raises(ValueError, match="only 'open'"):
        apply_status_change(
            tmp_path, "a-aaa", target, actor="alice", now=_NOW,
        )


# ---- dirty-tree guard ----------------------------------------------

def test_dirty_sidecar_refused(tmp_path: Path) -> None:
    sidecar_path = _setup_clean(tmp_path)
    # Make sidecar dirty by editing without committing.
    sidecar_path.write_text(
        sidecar_path.read_text(encoding="utf-8") + "\n# dirty\n",
        encoding="utf-8",
    )
    with pytest.raises(CrudRefusedDirty) as excinfo:
        apply_status_change(
            tmp_path, "a-aaa", Status.ACK, actor="alice", now=_NOW,
        )
    assert excinfo.value.sidecar_path == sidecar_path


def test_dirty_sidecar_force_dirty_bypass(tmp_path: Path) -> None:
    sidecar_path = _setup_clean(tmp_path)
    sidecar_path.write_text(
        sidecar_path.read_text(encoding="utf-8") + "\n# dirty\n",
        encoding="utf-8",
    )
    result = apply_status_change(
        tmp_path, "a-aaa", Status.ACK, actor="alice", now=_NOW,
        force_dirty=True,
    )
    assert result.new_status is Status.ACK


def test_dirty_other_sidecar_does_not_refuse(tmp_path: Path) -> None:
    sidecar_path = _setup_clean(tmp_path)
    other = tmp_path / "other.anno.trig"
    write_sidecar(other, Sidecar(annotations=(_ann("a-bbb"),)))
    # `other` is untracked → dirty in git; but it's not the target.
    result = apply_status_change(
        tmp_path, "a-aaa", Status.ACK, actor="alice", now=_NOW,
    )
    assert result.new_status is Status.ACK


# ---- round-trip -----------------------------------------------------

def test_round_trip_after_mutation(tmp_path: Path) -> None:
    sidecar_path = _setup_clean(tmp_path)
    apply_status_change(
        tmp_path, "a-aaa", Status.ACK, actor="alice", now=_NOW,
    )
    reloaded = read_sidecar(sidecar_path)
    ann = reloaded.annotations[0]
    assert ann.status is Status.ACK
    assert ann.modified is not None
    assert ann.modified_by == "alice"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science && uv run pytest tests/test_crud_apply.py -v`
Expected: FAIL — `science_tool.annotation.crud` module does not exist.

- [ ] **Step 3: Create `crud.py`**

Create `science/src/science_tool/annotation/crud.py`:

```python
# science/src/science_tool/annotation/crud.py
"""CRUD orchestrator powering ack/dismiss/fix.

See spec docs/plans/2026-05-11-annotation-system-p3.3-spec.md
§"Write concerns: crud.py".
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Optional

import click

from science_tool.annotation import lifecycle, query
from science_tool.annotation.io import (
    atomic_write_text,
    serialize_sidecar,
)
from science_tool.annotation.model import Sidecar, Status


# ---- Result + error -------------------------------------------------

@dataclass(frozen=True)
class CrudResult:
    sidecar_path: Path
    qualified_id: str       # rel-path-qualified, e.g. "notes/foo:a-7f3a"
    prior_status: Status
    new_status: Status


class CrudRefusedDirty(Exception):
    """Raised when the target sidecar has uncommitted changes (no force-dirty)."""

    def __init__(self, sidecar_path: Path) -> None:
        self.sidecar_path = sidecar_path
        super().__init__(
            f"refusing: {sidecar_path} has uncommitted changes; "
            "commit/stash or use --force-dirty"
        )


# ---- Public API -----------------------------------------------------

def apply_status_change(
    root: Path,
    id_arg: str,
    new_status: Status,
    *,
    actor: str,
    now: datetime,
    reason: Optional[str] = None,
    force_dirty: bool = False,
) -> CrudResult:
    """Resolve → guard dirty tree → mutate via lifecycle → atomic rewrite.

    Propagates query errors (AnnotationNotFound, AmbiguousAnnotationId)
    and lifecycle errors (ValueError) to the caller; CLI layer
    converts each to a ClickException with the right exit code.
    """
    resolved = query.resolve_id(root, id_arg)
    if not force_dirty and _sidecar_is_dirty(root, resolved.sidecar_path):
        raise CrudRefusedDirty(resolved.sidecar_path)

    mutated = lifecycle.mutate_status(
        resolved.annotation, new_status,
        actor=actor, now=now, reason=reason,
    )
    new_annotations = tuple(
        mutated if a.id == resolved.annotation.id else a
        for a in resolved.sidecar.annotations
    )
    new_sidecar = replace(resolved.sidecar, annotations=new_annotations)
    atomic_write_text(
        resolved.sidecar_path, serialize_sidecar(new_sidecar),
    )
    return CrudResult(
        sidecar_path=resolved.sidecar_path,
        qualified_id=f"{resolved.entity_relpath}:{resolved.annotation.id}",
        prior_status=resolved.annotation.status,
        new_status=new_status,
    )


# ---- Helpers --------------------------------------------------------

def _sidecar_is_dirty(root: Path, sidecar_path: Path) -> bool:
    """Return True if `sidecar_path` shows uncommitted changes under `root`.

    Returns False on non-git roots (the dirty-tree guard is a
    convenience, not a hard correctness requirement; verify uses the
    same convention).
    """
    try:
        proc = subprocess.run(
            ["git", "status", "--porcelain", "--", str(sidecar_path)],
            cwd=str(root),
            capture_output=True, text=True, check=False,
        )
    except (OSError, FileNotFoundError):
        return False
    if proc.returncode != 0:
        return False
    return bool(proc.stdout.strip())


def _resolve_actor(actor_opt: Optional[str], root: Path) -> str:
    """Resolve --actor: explicit flag → git config user.email → fail.

    No silent fallbacks. Raises ClickException when the chain fails
    so the CLI surface produces a friendly error.
    """
    if actor_opt:
        return actor_opt
    try:
        proc = subprocess.run(
            ["git", "config", "user.email"],
            cwd=str(root),
            capture_output=True, text=True, check=False,
        )
    except (OSError, FileNotFoundError) as exc:
        raise click.ClickException(
            "--actor required (no git available to read user.email)"
        ) from exc
    email = proc.stdout.strip()
    if proc.returncode != 0 or not email:
        raise click.ClickException(
            "--actor required (no git user.email available)"
        )
    return email
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && uv run pytest tests/test_crud_apply.py -v`
Expected: PASS (≈12 tests).

- [ ] **Step 5: Confirm no regression in adjacent tests**

Run: `cd science && uv run pytest tests/ -q -k "lifecycle or crud or query"`
Expected: green.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/annotation/crud.py \
        science/tests/test_crud_apply.py
git commit -m "feat(annotation/crud): apply_status_change orchestrator + dirty-tree guard"
```

---

### Task 11: `science annotate list` CLI command

**Files:**
- Modify: `science/src/science_tool/annotation/cli.py`
- Test: `science/tests/test_annotate_list_cli.py`

The query/filter projection. Positional `[PATH]` accepts directory,
markdown file, or `.anno.trig`; `--root` and `PATH` are mutually
exclusive.

- [ ] **Step 1: Write the failing tests**

Create `science/tests/test_annotate_list_cli.py`:

```python
"""science annotate list: PATH modes + filters + format."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from click.testing import CliRunner

from science_tool.annotation.cli import annotate_group
from science_tool.annotation.io import write_sidecar
from science_tool.annotation.model import (
    Annotation,
    Motivation,
    Sidecar,
    SpecificResource,
    Status,
    TextQuoteSelector,
    TextualBody,
)


def _ann(id_: str, status: Status = Status.OPEN, source: str = "lint:foo-v1") -> Annotation:
    from dataclasses import replace
    base = Annotation(
        id=id_,
        target=SpecificResource(
            source="x.md",
            selector=TextQuoteSelector(
                exact="A short sample sentence.",
                prefix="Before. ",
                suffix=" After.",
            ),
        ),
        bodies=(TextualBody(value="m"),),
        motivation=Motivation.CLASSIFYING,
        annotation_type="bare-author-year",
        source=source,
        status=Status.OPEN,
        creator="t",
        created=datetime(2026, 5, 11, tzinfo=timezone.utc),
        content_hash="sha256:d",
        match_text="m",
    )
    if status is Status.OPEN:
        return base
    return replace(
        base,
        status=status,
        modified=datetime(2026, 5, 11, 1, tzinfo=timezone.utc),
        modified_by="t",
    )


# ---- happy path: bare list ------------------------------------------

def test_list_default_open_only(tmp_path: Path) -> None:
    write_sidecar(tmp_path / "a.anno.trig", Sidecar(annotations=(
        _ann("a-1", status=Status.OPEN),
        _ann("a-2", status=Status.ACK),
    )))
    runner = CliRunner()
    result = runner.invoke(annotate_group, ["list", "--root", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert "a-1" in result.output
    assert "a-2" not in result.output  # ack hidden by default


def test_list_status_all(tmp_path: Path) -> None:
    write_sidecar(tmp_path / "a.anno.trig", Sidecar(annotations=(
        _ann("a-1", status=Status.OPEN),
        _ann("a-2", status=Status.ACK),
    )))
    runner = CliRunner()
    result = runner.invoke(annotate_group, [
        "list", "--root", str(tmp_path), "--status", "all",
    ])
    assert result.exit_code == 0
    assert "a-1" in result.output
    assert "a-2" in result.output


def test_list_source_glob(tmp_path: Path) -> None:
    write_sidecar(tmp_path / "a.anno.trig", Sidecar(annotations=(
        _ann("a-1", source="lint:foo-v1"),
        _ann("a-2", source="marker-scanner:phase-2"),
    )))
    runner = CliRunner()
    result = runner.invoke(annotate_group, [
        "list", "--root", str(tmp_path), "--source", "lint:*",
    ])
    assert result.exit_code == 0
    assert "a-1" in result.output
    assert "a-2" not in result.output


def test_list_json_format(tmp_path: Path) -> None:
    write_sidecar(tmp_path / "a.anno.trig", Sidecar(annotations=(_ann("a-1"),)))
    runner = CliRunner()
    result = runner.invoke(annotate_group, [
        "list", "--root", str(tmp_path), "--format", "json",
    ])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["summary"]["total_annotations"] == 1
    assert payload["annotations"][0]["id"] == "a-1"


# ---- PATH modes -----------------------------------------------------

def test_list_path_directory(tmp_path: Path) -> None:
    sub = tmp_path / "sub"
    sub.mkdir()
    write_sidecar(sub / "a.anno.trig", Sidecar(annotations=(_ann("a-1"),)))
    runner = CliRunner()
    result = runner.invoke(annotate_group, ["list", str(sub)])
    assert result.exit_code == 0
    assert "a-1" in result.output


def test_list_path_markdown(tmp_path: Path) -> None:
    write_sidecar(tmp_path / "foo.anno.trig", Sidecar(annotations=(_ann("a-1"),)))
    md = tmp_path / "foo.md"
    md.write_text("body", encoding="utf-8")
    runner = CliRunner()
    result = runner.invoke(annotate_group, ["list", str(md)])
    assert result.exit_code == 0
    assert "a-1" in result.output


def test_list_path_sidecar(tmp_path: Path) -> None:
    sidecar = tmp_path / "foo.anno.trig"
    write_sidecar(sidecar, Sidecar(annotations=(_ann("a-1"),)))
    runner = CliRunner()
    result = runner.invoke(annotate_group, ["list", str(sidecar)])
    assert result.exit_code == 0
    assert "a-1" in result.output


def test_list_path_missing_md_is_empty(tmp_path: Path) -> None:
    """Markdown PATH with no sidecar yields empty result, exit 0."""
    md = tmp_path / "nope.md"
    md.write_text("body", encoding="utf-8")
    runner = CliRunner()
    result = runner.invoke(annotate_group, ["list", str(md)])
    assert result.exit_code == 0
    assert "0 annotation" in result.output


def test_list_path_md_with_corrupt_sidecar_friendly_error(tmp_path: Path) -> None:
    """PATH=foo.md with corrupt foo.anno.trig produces ClickException, not raw rdflib trace."""
    md = tmp_path / "foo.md"
    md.write_text("body", encoding="utf-8")
    sidecar = tmp_path / "foo.anno.trig"
    sidecar.write_text("THIS IS NOT VALID TRIG", encoding="utf-8")
    runner = CliRunner()
    result = runner.invoke(annotate_group, ["list", str(md)])
    assert result.exit_code == 1
    assert "foo.anno.trig" in result.output


def test_list_path_anno_trig_corrupt_friendly_error(tmp_path: Path) -> None:
    """PATH=foo.anno.trig (corrupt) produces ClickException, not raw rdflib trace."""
    sidecar = tmp_path / "foo.anno.trig"
    sidecar.write_text("THIS IS NOT VALID TRIG", encoding="utf-8")
    runner = CliRunner()
    result = runner.invoke(annotate_group, ["list", str(sidecar)])
    assert result.exit_code == 1
    assert "foo.anno.trig" in result.output


def test_list_root_and_path_mutually_exclusive(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(annotate_group, [
        "list", "--root", str(tmp_path), str(tmp_path),
    ])
    assert result.exit_code == 1
    assert "mutually exclusive" in result.output


# ---- since plumbing -------------------------------------------------

def test_list_since_outside_repo_errors(tmp_path: Path) -> None:
    write_sidecar(tmp_path / "a.anno.trig", Sidecar(annotations=(_ann("a-1"),)))
    runner = CliRunner()
    result = runner.invoke(annotate_group, [
        "list", "--root", str(tmp_path), "--since", "main",
    ])
    assert result.exit_code == 1
    assert "git" in result.output.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science && uv run pytest tests/test_annotate_list_cli.py -v`
Expected: FAIL — `list` subcommand not registered.

- [ ] **Step 3: Add `list_cmd` to `cli.py`**

Edit `science/src/science_tool/annotation/cli.py`. Add imports near
the top:

```python
from science_tool.annotation import crud, query
from science_tool.annotation.io import (
    markdown_for_sidecar,
    sidecar_for_markdown,
)
from science_tool.annotation.model import Status
```

Append after the `lift_tokens_cmd` definition:

```python
_VALID_STATUS_VALUES = (
    "open", "ack", "fixed", "dismissed", "superseded", "all",
)


def _parse_status_filter(values: tuple[str, ...]) -> frozenset[Status] | None:
    """Convert --status flag values into a query.filter_annotations argument.

    `("all",)` (or any tuple containing "all") → None (no filter).
    Empty tuple is treated by the CLI default; this helper only sees
    explicit values.
    """
    if "all" in values:
        return None
    return frozenset(Status(v) for v in values)


def _scope_to_sidecars(
    root: Path | None,
    path: Path | None,
) -> tuple[Path, list[tuple[Path, Sidecar]]]:
    """Resolve the (--root, PATH) pair into (root_path, sidecars list).

    Caller is responsible for the mutual-exclusion check.
    """
    if path is not None:
        if path.is_dir():
            return path.resolve(), list(query.iter_sidecars(path))
        if path.suffix == ".md":
            sidecar_path = sidecar_for_markdown(path)
            if not sidecar_path.exists():
                return path.parent.resolve(), []
            return (
                path.parent.resolve(),
                [(sidecar_path, query.read_sidecar_strict(sidecar_path))],
            )
        if path.name.endswith(".anno.trig"):
            return (
                path.parent.resolve(),
                [(path, query.read_sidecar_strict(path))],
            )
        raise click.ClickException(
            f"PATH {path} is not a directory, .md, or .anno.trig file"
        )
    effective_root = (root or Path.cwd()).resolve()
    return effective_root, list(query.iter_sidecars(effective_root))


@annotate_group.command("list")
@click.argument("path", required=False, type=click.Path(exists=True, path_type=Path))
@click.option(
    "--root", "root_path", default=None,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
)
@click.option(
    "--status", "statuses_opt", multiple=True,
    type=click.Choice(_VALID_STATUS_VALUES),
)
@click.option("--source", "sources_opt", multiple=True)
@click.option("--since", "since_ref", default=None)
@click.option(
    "--format", "fmt", type=click.Choice(("table", "json")), default="table",
)
def list_cmd(
    path: Path | None,
    root_path: Path | None,
    statuses_opt: tuple[str, ...],
    sources_opt: tuple[str, ...],
    since_ref: str | None,
    fmt: str,
) -> None:
    """List annotations matching filters."""
    if path is not None and root_path is not None:
        raise click.ClickException("--root and PATH are mutually exclusive")

    try:
        effective_root, sidecars = _scope_to_sidecars(root_path, path)
    except query.SidecarParseError as exc:
        raise click.ClickException(str(exc)) from exc

    statuses = _parse_status_filter(
        statuses_opt or ("open",),
    )

    since_changed: frozenset[Path] | None = None
    if since_ref is not None:
        try:
            since_changed = query.git_changed_markdown(effective_root, since_ref)
        except RuntimeError as exc:
            raise click.ClickException(
                f"--since failed: {exc}"
            ) from exc

    rows = list(query.filter_annotations(
        sidecars,
        statuses=statuses,
        sources=sources_opt,
        since_changed=since_changed,
    ))
    rows.sort(key=lambda pa: (
        query.entity_relpath_for_sidecar(pa[0], effective_root),
        pa[1].id,
    ))

    if fmt == "json":
        _emit_list_json(rows, effective_root, len(sidecars))
    else:
        _emit_list_table(rows, effective_root, len(sidecars))


def _emit_list_table(
    rows: list[tuple[Path, "Annotation"]],
    root: Path,
    sidecar_count: int,
) -> None:
    if not rows:
        click.echo(
            f"annotate list: 0 annotation(s) across {sidecar_count} sidecar(s)"
        )
        return
    for sidecar_path, ann in rows:
        qualified = (
            f"{query.entity_relpath_for_sidecar(sidecar_path, root)}:{ann.id}"
        )
        preview = ann.target.selector.exact
        if len(preview) > 60:
            preview = preview[:60] + "…"
        click.echo(
            f"  {qualified}  {ann.status.value:<10}  "
            f"{ann.source}  {ann.annotation_type}  {preview!r}"
        )
    click.echo(
        f"\nannotate list: {len(rows)} annotation(s) across "
        f"{sidecar_count} sidecar(s)"
    )


def _emit_list_json(
    rows: list[tuple[Path, "Annotation"]],
    root: Path,
    sidecar_count: int,
) -> None:
    items = []
    for sidecar_path, ann in rows:
        items.append({
            "id": ann.id,
            "qualified_id":
                f"{query.entity_relpath_for_sidecar(sidecar_path, root)}:{ann.id}",
            "status": ann.status.value,
            "source": ann.source,
            "annotation_type": ann.annotation_type,
            "exact_preview": ann.target.selector.exact[:60],
        })
    click.echo(json.dumps({
        "summary": {
            "total_annotations": len(rows),
            "total_sidecars": sidecar_count,
        },
        "annotations": items,
    }, indent=2))
```

Note on the `Annotation` import: the symbol is already imported at
the top of `cli.py` indirectly via P3.2 code; if a `NameError` appears
during step 4, add an explicit
`from science_tool.annotation.model import Annotation`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && uv run pytest tests/test_annotate_list_cli.py -v`
Expected: PASS (≈10 tests).

- [ ] **Step 5: Confirm broader CLI suite green**

Run: `cd science && uv run pytest tests/ -q -k "annotate"`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/annotation/cli.py \
        science/tests/test_annotate_list_cli.py
git commit -m "feat(annotate): science annotate list command (P3.3)"
```

---

### Task 12: `science annotate ack / dismiss / fix` CLI commands

**Files:**
- Modify: `science/src/science_tool/annotation/cli.py`
- Test: `science/tests/test_annotate_ack_dismiss_fix_cli.py`

Three commands sharing `crud.apply_status_change`. Each takes one
positional `<ID>` (bare frag, bare-stem qualified, or rel-path
qualified). `dismiss` requires `--reason`. Exit code 2 reserved for
ambiguous-id; 1 for everything else.

- [ ] **Step 1: Write the failing tests**

Create `science/tests/test_annotate_ack_dismiss_fix_cli.py`:

```python
"""ack/dismiss/fix CLI happy + error paths."""

from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest
from click.testing import CliRunner

from science_tool.annotation.cli import annotate_group
from science_tool.annotation.io import read_sidecar, write_sidecar
from science_tool.annotation.model import (
    Annotation,
    Motivation,
    Sidecar,
    SpecificResource,
    Status,
    TextQuoteSelector,
    TextualBody,
)


def _ann(id_: str, status: Status = Status.OPEN) -> Annotation:
    from dataclasses import replace
    base = Annotation(
        id=id_,
        target=SpecificResource(
            source="x.md",
            selector=TextQuoteSelector(exact="x", prefix="", suffix=""),
        ),
        bodies=(TextualBody(value="m"),),
        motivation=Motivation.CLASSIFYING,
        annotation_type="bare-author-year",
        source="lint:bare-author-year-v2026-05-11",
        status=Status.OPEN,
        creator="t",
        created=datetime(2026, 5, 11, tzinfo=timezone.utc),
        content_hash="sha256:d",
        match_text="m",
    )
    if status is Status.OPEN:
        return base
    return replace(
        base, status=status,
        modified=datetime(2026, 5, 11, 1, tzinfo=timezone.utc),
        modified_by="t",
    )


def _git_setup(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)
    sidecar_path = tmp_path / "foo.anno.trig"
    write_sidecar(sidecar_path, Sidecar(annotations=(_ann("a-aaa"),)))
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=tmp_path, check=True)
    return sidecar_path


# ---- ack happy path -------------------------------------------------

def test_ack_happy(tmp_path: Path) -> None:
    sidecar_path = _git_setup(tmp_path)
    runner = CliRunner()
    result = runner.invoke(annotate_group, [
        "ack", "a-aaa", "--root", str(tmp_path), "--actor", "alice",
    ])
    assert result.exit_code == 0, result.output
    assert "ack:" in result.output
    assert "open → ack" in result.output
    assert read_sidecar(sidecar_path).annotations[0].status is Status.ACK


# ---- dismiss requires reason ---------------------------------------

def test_dismiss_requires_reason(tmp_path: Path) -> None:
    _git_setup(tmp_path)
    runner = CliRunner()
    result = runner.invoke(annotate_group, [
        "dismiss", "a-aaa", "--root", str(tmp_path), "--actor", "alice",
    ])
    assert result.exit_code != 0


def test_dismiss_empty_reason_rejected(tmp_path: Path) -> None:
    _git_setup(tmp_path)
    runner = CliRunner()
    result = runner.invoke(annotate_group, [
        "dismiss", "a-aaa", "--root", str(tmp_path),
        "--actor", "alice", "--reason", "   ",
    ])
    assert result.exit_code == 1
    assert "reason cannot be empty" in result.output


def test_dismiss_happy(tmp_path: Path) -> None:
    sidecar_path = _git_setup(tmp_path)
    runner = CliRunner()
    result = runner.invoke(annotate_group, [
        "dismiss", "a-aaa", "--root", str(tmp_path),
        "--actor", "alice", "--reason", "not actionable",
    ])
    assert result.exit_code == 0, result.output
    # Verb prefix must be `dismiss:` (the command name), NOT
    # `dismissed:` (Status.DISMISSED.value). Regression sentinel.
    assert "dismiss:" in result.output
    assert "dismissed:" not in result.output  # would indicate verb-not-passed bug
    assert "open → dismissed" in result.output
    assert "(reason: not actionable)" in result.output
    sidecar = read_sidecar(sidecar_path)
    assert sidecar.annotations[0].description == "not actionable"


# ---- fix happy path -------------------------------------------------

def test_fix_happy(tmp_path: Path) -> None:
    sidecar_path = _git_setup(tmp_path)
    runner = CliRunner()
    result = runner.invoke(annotate_group, [
        "fix", "a-aaa", "--root", str(tmp_path), "--actor", "alice",
    ])
    assert result.exit_code == 0
    # Verb prefix must be the user-facing command name, NOT
    # Status.FIXED.value ("fixed"). Regression sentinel.
    assert "fix:" in result.output
    assert "open → fixed" in result.output
    assert read_sidecar(sidecar_path).annotations[0].status is Status.FIXED


# ---- not-found / ambiguous -----------------------------------------

def test_ack_not_found_exits_1(tmp_path: Path) -> None:
    _git_setup(tmp_path)
    runner = CliRunner()
    result = runner.invoke(annotate_group, [
        "ack", "a-zzz", "--root", str(tmp_path), "--actor", "alice",
    ])
    assert result.exit_code == 1
    assert "no annotation" in result.output.lower()


def test_ack_ambiguous_exits_2_with_candidates(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)
    notes = tmp_path / "notes"
    notes.mkdir()
    appendix = tmp_path / "appendix"
    appendix.mkdir()
    write_sidecar(notes / "foo.anno.trig", Sidecar(annotations=(_ann("a-aaa"),)))
    write_sidecar(appendix / "foo.anno.trig", Sidecar(annotations=(_ann("a-aaa"),)))
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=tmp_path, check=True)

    runner = CliRunner()
    result = runner.invoke(annotate_group, [
        "ack", "a-aaa", "--root", str(tmp_path), "--actor", "alice",
    ])
    assert result.exit_code == 2
    assert "notes/foo:a-aaa" in result.output
    assert "appendix/foo:a-aaa" in result.output


# ---- dirty-tree refusal --------------------------------------------

def test_ack_refuses_dirty_sidecar(tmp_path: Path) -> None:
    sidecar_path = _git_setup(tmp_path)
    sidecar_path.write_text(
        sidecar_path.read_text(encoding="utf-8") + "\n# dirty\n",
        encoding="utf-8",
    )
    runner = CliRunner()
    result = runner.invoke(annotate_group, [
        "ack", "a-aaa", "--root", str(tmp_path), "--actor", "alice",
    ])
    assert result.exit_code == 1
    assert "uncommitted" in result.output


def test_ack_force_dirty_bypass(tmp_path: Path) -> None:
    sidecar_path = _git_setup(tmp_path)
    sidecar_path.write_text(
        sidecar_path.read_text(encoding="utf-8") + "\n# dirty\n",
        encoding="utf-8",
    )
    runner = CliRunner()
    result = runner.invoke(annotate_group, [
        "ack", "a-aaa", "--root", str(tmp_path),
        "--actor", "alice", "--force-dirty",
    ])
    assert result.exit_code == 0


# ---- terminal-state refusal ----------------------------------------

def test_fix_refused_when_already_acked(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)
    sidecar_path = tmp_path / "foo.anno.trig"
    write_sidecar(
        sidecar_path,
        Sidecar(annotations=(_ann("a-aaa", status=Status.ACK),)),
    )
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=tmp_path, check=True)
    runner = CliRunner()
    result = runner.invoke(annotate_group, [
        "fix", "a-aaa", "--root", str(tmp_path), "--actor", "alice",
    ])
    assert result.exit_code == 1
    assert "terminal" in result.output


# ---- actor fallback ------------------------------------------------

def test_actor_falls_back_to_git_user_email(tmp_path: Path) -> None:
    sidecar_path = _git_setup(tmp_path)  # sets user.email = t@example.com
    runner = CliRunner()
    result = runner.invoke(annotate_group, [
        "ack", "a-aaa", "--root", str(tmp_path),  # no --actor
    ])
    assert result.exit_code == 0
    sidecar = read_sidecar(sidecar_path)
    assert sidecar.annotations[0].modified_by == "t@example.com"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science && uv run pytest tests/test_annotate_ack_dismiss_fix_cli.py -v`
Expected: FAIL — three commands not registered.

- [ ] **Step 3: Add the three CLI commands to `cli.py`**

Edit `science/src/science_tool/annotation/cli.py`. Append after
`list_cmd`:

```python
def _crud_invoke(
    verb: str,
    new_status: Status,
    *,
    id_arg: str,
    root_path: Path | None,
    actor_opt: str | None,
    force_dirty: bool,
    reason: str | None = None,
) -> None:
    """Shared body for ack_cmd / dismiss_cmd / fix_cmd.

    `verb` is the user-facing command name ("ack", "dismiss", "fix")
    used as the output prefix. Necessary because Status.DISMISSED.value
    is "dismissed" and Status.FIXED.value is "fixed" — the resulting
    status is NOT the verb. The spec output examples are
    `dismiss: ...` and `fix: ...`, not `dismissed: ...` / `fixed: ...`.
    """
    root = (root_path or Path.cwd()).resolve()
    actor = crud._resolve_actor(actor_opt, root)
    now = datetime.now(timezone.utc)
    try:
        result = crud.apply_status_change(
            root, id_arg, new_status,
            actor=actor, now=now, reason=reason, force_dirty=force_dirty,
        )
    except query.AmbiguousAnnotationId as exc:
        click.echo(str(exc), err=True)
        for cand in exc.candidates:
            click.echo(f"  {cand}", err=True)
        raise click.exceptions.Exit(2) from exc
    except query.AnnotationNotFound as exc:
        raise click.ClickException(str(exc)) from exc
    except crud.CrudRefusedDirty as exc:
        raise click.ClickException(str(exc)) from exc
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    suffix = (
        f" (reason: {reason})" if reason else ""
    )
    click.echo(
        f"{verb}: {result.qualified_id} "
        f"{result.prior_status.value} → {result.new_status.value}{suffix}"
    )


@annotate_group.command("ack")
@click.argument("id_arg", metavar="ID")
@click.option(
    "--root", "root_path", default=None,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
)
@click.option("--actor", "actor_opt", default=None)
@click.option("--force-dirty", is_flag=True, default=False)
def ack_cmd(
    id_arg: str, root_path: Path | None,
    actor_opt: str | None, force_dirty: bool,
) -> None:
    """Acknowledge an annotation (status: open → ack)."""
    _crud_invoke(
        "ack", Status.ACK,
        id_arg=id_arg, root_path=root_path,
        actor_opt=actor_opt, force_dirty=force_dirty,
    )


@annotate_group.command("dismiss")
@click.argument("id_arg", metavar="ID")
@click.option(
    "--root", "root_path", default=None,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
)
@click.option("--actor", "actor_opt", default=None)
@click.option("--force-dirty", is_flag=True, default=False)
@click.option("--reason", "reason", required=True)
def dismiss_cmd(
    id_arg: str, root_path: Path | None,
    actor_opt: str | None, force_dirty: bool, reason: str,
) -> None:
    """Dismiss an annotation (status: open → dismissed)."""
    if not reason.strip():
        raise click.ClickException("--reason cannot be empty")
    _crud_invoke(
        "dismiss", Status.DISMISSED,
        id_arg=id_arg, root_path=root_path,
        actor_opt=actor_opt, force_dirty=force_dirty,
        reason=reason,
    )


@annotate_group.command("fix")
@click.argument("id_arg", metavar="ID")
@click.option(
    "--root", "root_path", default=None,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
)
@click.option("--actor", "actor_opt", default=None)
@click.option("--force-dirty", is_flag=True, default=False)
def fix_cmd(
    id_arg: str, root_path: Path | None,
    actor_opt: str | None, force_dirty: bool,
) -> None:
    """Mark an annotation as fixed (status: open → fixed)."""
    _crud_invoke(
        "fix", Status.FIXED,
        id_arg=id_arg, root_path=root_path,
        actor_opt=actor_opt, force_dirty=force_dirty,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && uv run pytest tests/test_annotate_ack_dismiss_fix_cli.py -v`
Expected: PASS (≈11 tests).

- [ ] **Step 5: Confirm broader suite green**

Run: `cd science && uv run pytest tests/ -q -k "annotate"`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/annotation/cli.py \
        science/tests/test_annotate_ack_dismiss_fix_cli.py
git commit -m "feat(annotate): science annotate ack / dismiss / fix commands (P3.3)"
```

---

### Task 13: `science annotate stats` CLI command

**Files:**
- Modify: `science/src/science_tool/annotation/cli.py`
- Test: `science/tests/test_annotate_stats_cli.py`

Three-section table aggregating by status, source, and annotation
type. JSON output mirrors the structure.

- [ ] **Step 1: Write the failing tests**

Create `science/tests/test_annotate_stats_cli.py`:

```python
"""science annotate stats: three sections, table + json."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from click.testing import CliRunner

from science_tool.annotation.cli import annotate_group
from science_tool.annotation.io import write_sidecar
from science_tool.annotation.model import (
    Annotation,
    Motivation,
    Sidecar,
    SpecificResource,
    Status,
    TextQuoteSelector,
    TextualBody,
)


def _ann(
    id_: str, *,
    status: Status = Status.OPEN,
    source: str = "lint:foo-v1",
    annotation_type: str = "bare-author-year",
) -> Annotation:
    base = Annotation(
        id=id_,
        target=SpecificResource(
            source="x.md",
            selector=TextQuoteSelector(exact="x", prefix="", suffix=""),
        ),
        bodies=(TextualBody(value="m"),),
        motivation=Motivation.CLASSIFYING,
        annotation_type=annotation_type,
        source=source,
        status=Status.OPEN,
        creator="t",
        created=datetime(2026, 5, 11, tzinfo=timezone.utc),
        content_hash="sha256:d",
        match_text="m",
    )
    if status is Status.OPEN:
        return base
    return replace(
        base, status=status,
        modified=datetime(2026, 5, 11, 1, tzinfo=timezone.utc),
        modified_by="t",
    )


def test_stats_empty_corpus(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(annotate_group, ["stats", "--root", str(tmp_path)])
    assert result.exit_code == 0
    assert "0 annotation" in result.output


def test_stats_table_sections(tmp_path: Path) -> None:
    write_sidecar(tmp_path / "a.anno.trig", Sidecar(annotations=(
        _ann("a-1", status=Status.OPEN, source="lint:foo-v1", annotation_type="bare-author-year"),
        _ann("a-2", status=Status.OPEN, source="lint:foo-v1", annotation_type="bare-author-year"),
        _ann("a-3", status=Status.ACK, source="marker-scanner:phase-2", annotation_type="unverified"),
    )))
    runner = CliRunner()
    result = runner.invoke(annotate_group, ["stats", "--root", str(tmp_path)])
    assert result.exit_code == 0
    assert "By status" in result.output
    assert "By source" in result.output
    assert "By type" in result.output
    assert "open" in result.output
    assert "ack" in result.output
    assert "lint:foo-v1" in result.output
    assert "marker-scanner:phase-2" in result.output
    assert "bare-author-year" in result.output


def test_stats_json_schema(tmp_path: Path) -> None:
    write_sidecar(tmp_path / "a.anno.trig", Sidecar(annotations=(
        _ann("a-1"),
    )))
    runner = CliRunner()
    result = runner.invoke(annotate_group, [
        "stats", "--root", str(tmp_path), "--format", "json",
    ])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["summary"]["total_annotations"] == 1
    assert payload["summary"]["total_sidecars"] == 1
    assert payload["by_status"] == {"open": 1}
    assert payload["by_source"] == {"lint:foo-v1": 1}
    assert payload["by_type"] == {"bare-author-year": 1}


def test_stats_descending_order_in_json(tmp_path: Path) -> None:
    write_sidecar(tmp_path / "a.anno.trig", Sidecar(annotations=(
        _ann("a-1", source="lint:c-v1"),
        _ann("a-2", source="lint:a-v1"),
        _ann("a-3", source="lint:a-v1"),
        _ann("a-4", source="lint:a-v1"),
        _ann("a-5", source="lint:b-v1"),
        _ann("a-6", source="lint:b-v1"),
    )))
    runner = CliRunner()
    result = runner.invoke(annotate_group, [
        "stats", "--root", str(tmp_path), "--format", "json",
    ])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    keys = list(payload["by_source"].keys())
    assert keys == ["lint:a-v1", "lint:b-v1", "lint:c-v1"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science && uv run pytest tests/test_annotate_stats_cli.py -v`
Expected: FAIL — `stats` command not registered.

- [ ] **Step 3: Add `stats_cmd` to `cli.py`**

Append after `fix_cmd` in `science/src/science_tool/annotation/cli.py`:

```python
@annotate_group.command("stats")
@click.option(
    "--root", "root_path", default=None,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
)
@click.option(
    "--format", "fmt", type=click.Choice(("table", "json")), default="table",
)
def stats_cmd(root_path: Path | None, fmt: str) -> None:
    """Project-wide annotation counts (status / source / type)."""
    root = (root_path or Path.cwd()).resolve()
    try:
        sidecars = list(query.iter_sidecars(root))
    except query.SidecarParseError as exc:
        raise click.ClickException(str(exc)) from exc
    report = query.compute_stats(sidecars)
    if fmt == "json":
        click.echo(json.dumps({
            "summary": {
                "total_annotations": report.total_annotations,
                "total_sidecars": report.total_sidecars,
            },
            "by_status": {k.value: v for k, v in report.by_status.items()},
            "by_source": dict(report.by_source),
            "by_type": dict(report.by_type),
        }, indent=2))
        return
    click.echo(
        f"annotate stats: {report.total_annotations} annotation(s) across "
        f"{report.total_sidecars} sidecar(s)\n"
    )
    if report.by_status:
        click.echo("By status:")
        for status, count in report.by_status.items():
            click.echo(f"  {status.value:<12} {count}")
        click.echo()
    if report.by_source:
        click.echo("By source:")
        for source, count in report.by_source.items():
            click.echo(f"  {source:<40} {count}")
        click.echo()
    if report.by_type:
        click.echo("By type:")
        for type_, count in report.by_type.items():
            click.echo(f"  {type_:<24} {count}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && uv run pytest tests/test_annotate_stats_cli.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Confirm broader suite green**

Run: `cd science && uv run pytest tests/ -q -k "annotate"`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/annotation/cli.py \
        science/tests/test_annotate_stats_cli.py
git commit -m "feat(annotate): science annotate stats command (P3.3)"
```

---

### Task 14: End-to-end integration test

**Files:**
- Test: `science/tests/test_annotate_p33_integration.py`

Exercises the full pipeline: `audit` populates sidecars, then `list`,
`ack`, `dismiss --reason`, `fix`, and `stats` are invoked in sequence
via `CliRunner`. Final state asserted via `read_sidecar` + structural
compare. No production code change.

- [ ] **Step 1: Write the integration test**

Create `science/tests/test_annotate_p33_integration.py`:

```python
"""End-to-end pipeline: audit → list → ack → dismiss → fix → stats."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from click.testing import CliRunner

from science_tool.annotation.cli import annotate_group
from science_tool.annotation.io import read_sidecar
from science_tool.annotation.model import Status


_FIXTURE = """\
---
title: Integration fixture
---

Brunton 2022 wrote about modes. h04 is also referenced bare.

A claim is uncited [UNVERIFIED] and stands alone.
"""


def _git_init(root: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=root, check=True)


def test_full_pipeline(tmp_path: Path) -> None:
    _git_init(tmp_path)
    md = tmp_path / "doc.md"
    md.write_text(_FIXTURE, encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=tmp_path, check=True)

    runner = CliRunner()

    # 1. Audit populates the sidecar.
    result = runner.invoke(annotate_group, [
        "audit", "--root", str(tmp_path), "--actor", "t",
    ])
    assert result.exit_code == 0, result.output
    sidecar_path = tmp_path / "doc.anno.trig"
    assert sidecar_path.exists()

    # Commit the sidecar so dirty-tree guard doesn't trip later.
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "audit"], cwd=tmp_path, check=True,
    )

    # 2. list shows multiple open rows.
    result = runner.invoke(annotate_group, ["list", "--root", str(tmp_path)])
    assert result.exit_code == 0
    open_count_before = result.output.count(":a-")  # rough row counter

    sidecar = read_sidecar(sidecar_path)
    assert open_count_before > 0
    first_id = sidecar.annotations[0].id

    # 3. ack the first one.
    result = runner.invoke(annotate_group, [
        "ack", first_id, "--root", str(tmp_path), "--actor", "alice",
    ])
    assert result.exit_code == 0, result.output
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "ack"], cwd=tmp_path, check=True,
    )

    sidecar = read_sidecar(sidecar_path)
    acked = next(a for a in sidecar.annotations if a.id == first_id)
    assert acked.status is Status.ACK

    # 4. dismiss another with a reason.
    second_id = next(
        a.id for a in sidecar.annotations
        if a.id != first_id and a.status is Status.OPEN
    )
    result = runner.invoke(annotate_group, [
        "dismiss", second_id, "--root", str(tmp_path),
        "--actor", "alice", "--reason", "covered elsewhere",
    ])
    assert result.exit_code == 0, result.output
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "dismiss"], cwd=tmp_path, check=True,
    )

    sidecar = read_sidecar(sidecar_path)
    dismissed = next(a for a in sidecar.annotations if a.id == second_id)
    assert dismissed.status is Status.DISMISSED
    assert dismissed.description == "covered elsewhere"

    # 5. fix a third (if available).
    third = next(
        (a for a in sidecar.annotations if a.status is Status.OPEN),
        None,
    )
    if third is not None:
        result = runner.invoke(annotate_group, [
            "fix", third.id, "--root", str(tmp_path), "--actor", "alice",
        ])
        assert result.exit_code == 0
        subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
        subprocess.run(
            ["git", "commit", "-q", "-m", "fix"], cwd=tmp_path, check=True,
        )
        sidecar = read_sidecar(sidecar_path)
        fixed = next(a for a in sidecar.annotations if a.id == third.id)
        assert fixed.status is Status.FIXED

    # 6. stats reflects the mutations.
    result = runner.invoke(annotate_group, [
        "stats", "--root", str(tmp_path), "--format", "json",
    ])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    by_status = payload["by_status"]
    assert by_status.get("ack", 0) >= 1
    assert by_status.get("dismissed", 0) >= 1

    # 7. list with --status all shows the dismissed/ack rows.
    result = runner.invoke(annotate_group, [
        "list", "--root", str(tmp_path), "--status", "all",
    ])
    assert result.exit_code == 0
    assert "ack" in result.output
    assert "dismissed" in result.output
```

- [ ] **Step 2: Run the integration test**

Run: `cd science && uv run pytest tests/test_annotate_p33_integration.py -v`
Expected: PASS (1 test).

- [ ] **Step 3: Confirm the entire annotation suite is green**

Run: `cd science && uv run pytest tests/ -q -k "annotation or annotate or lifecycle or query or crud or text_segmentation or io_path_helpers or io_atomic"`
Expected: green; total ≥ 60 new tests added across Tasks 1–14.

- [ ] **Step 4: Commit**

```bash
git add science/tests/test_annotate_p33_integration.py
git commit -m "test(annotate): end-to-end P3.3 pipeline integration"
```

---

### Task 15: Acceptance smoke + final review

**Files:** none (verification only).

This task is the final pass. No commits expected unless a regression
surfaces (in which case fix and add a follow-up commit).

- [ ] **Step 1: Run the full project test suite**

```bash
cd science
uv run pytest -q
```
Expected: all green. Note the pass/fail tally and total count for
the report.

- [ ] **Step 2: Smoke `science annotate list` end-to-end**

```bash
mkdir -p /tmp/p33-smoke && cd /tmp/p33-smoke
git init -q
git config user.email t@example.com
git config user.name t
cat > doc.md <<'EOF'
---
title: Smoke
---

Brunton 2022 wrote about modes. h04 is bare.

A claim is uncited [UNVERIFIED].
EOF
git add . && git commit -q -m init
uv run --project ~/d/science/science science annotate audit --root . --actor t
git add . && git commit -q -m audit
uv run --project ~/d/science/science science annotate list --root .
uv run --project ~/d/science/science science annotate stats --root .
```
Expected: `audit` writes the sidecar; `list` shows ≥2 open rows;
`stats` shows non-zero counts in each section.

- [ ] **Step 3: Smoke `ack` / `dismiss` / `fix`**

(continuing from step 2's directory)
```bash
ID=$(uv run --project ~/d/science/science science annotate list --root . --format json | python3 -c "import json,sys; print(json.load(sys.stdin)['annotations'][0]['id'])")
uv run --project ~/d/science/science science annotate ack "$ID" --root . --actor t
git add . && git commit -q -m ack
uv run --project ~/d/science/science science annotate list --root . --status all
```
Expected: `ack:` line in output; subsequent `list --status all` shows
the ack'd row.

- [ ] **Step 4: Smoke ambiguous-id error path**

```bash
mkdir -p /tmp/p33-amb/notes /tmp/p33-amb/appendix && cd /tmp/p33-amb
git init -q
git config user.email t@example.com
git config user.name t
cat > notes/foo.md <<'EOF'
Brunton 2022 wrote.
EOF
cat > appendix/foo.md <<'EOF'
Brunton 2022 wrote.
EOF
git add . && git commit -q -m init
uv run --project ~/d/science/science science annotate audit --root . --actor t
git add . && git commit -q -m audit
ID=$(uv run --project ~/d/science/science science annotate list --root . --format json | python3 -c "import json,sys; print(json.load(sys.stdin)['annotations'][0]['id'].split(':')[-1])")
# Bare frag is ambiguous (a-XXXX exists in both sidecars):
uv run --project ~/d/science/science science annotate ack "$ID" --root . --actor t
echo "exit code: $?"
```
Expected: exit code 2; stderr lists rel-path-qualified candidates.

- [ ] **Step 5: Smoke lift-tokens still works (regression sentinel)**

```bash
mkdir -p /tmp/p33-lift && cd /tmp/p33-lift
git init -q
git config user.email t@example.com
git config user.name t
cat > doc.md <<'EOF'
A claim is uncited [UNVERIFIED] and stands alone.
EOF
git add . && git commit -q -m init
uv run --project ~/d/science/science science annotate lift-tokens --root . --actor t
```
Expected: 1 row written; no error. (Confirms text_segmentation swap
preserved P3.2 behavior.)

- [ ] **Step 6: Smoke `verify` still works (regression sentinel)**

(continuing from step 5)
```bash
uv run --project ~/d/science/science science annotate verify --root .
```
Expected: 0 broken / 0 degraded / 0 fuzzy.

- [ ] **Step 7: Report**

Report back with:
- Total test count and pass/fail tally from step 1.
- Output from steps 2, 3 showing row counts and CRUD output.
- Confirmation that step 4 produced exit code 2 with rel-path candidates.
- Confirmation that step 5 lift-tokens succeeded.
- Confirmation that step 6 verify reported clean.
- Any unexpected stderr from any step.

No commit in this task; verification is pass-only.

---

## Spec coverage check

| Spec section | Covered by |
|---|---|
| §"Path-derivation helpers in io.py" | Task 1 |
| §"Helper migration into io.py" (atomic/serialize) | Task 2 |
| §"Folded follow-ups 1 + 7 — text_segmentation" | Task 3 |
| §"Folded follow-up 2 — assert→ValueError" | Task 4 |
| §"Folded follow-up 3 — mint_id O(N²)→O(N)" | Task 4 |
| §"Decision 12 — tighten lifecycle.mutate_status" | Task 5 |
| §"iter_sidecars + SidecarParseError" | Task 6 |
| §"resolve_id algorithm" + qualified ID forms | Task 7 |
| §"filter_annotations + git_changed_markdown" | Task 8 |
| §"compute_stats + StatsReport" | Task 9 |
| §"crud.apply_status_change" + dirty-tree guard + actor fallback | Task 10 |
| §"CLI surface — list [PATH]" + PATH modes + filters + JSON | Task 11 |
| §"CLI surface — ack / dismiss / fix" + reason guard + ambiguous-id exit 2 | Task 12 |
| §"CLI surface — stats" + three sections + JSON | Task 13 |
| §"Integration test" | Task 14 |
| §Acceptance criteria | Task 15 |

No spec section is unaddressed.

---

## Out-of-scope reminders (do NOT implement here)

These are deferred per spec §Non-goals and §Out of scope reminders.
A subagent that finds itself adding any of the following should
stop and escalate:

- `science annotate render` (terminal + HTML) — P3.4
- Top-N entity stats axis — P3.4
- `--type` filter on `list` — defer until use case demands
- Persistent `.science-annotate-index.json` cache — defer
- `prose lint` deprecation banner / collapse to `list` wrapper
- Batch CRUD (`ack a-1 a-2`, `--from-file`)
- `fix` selector re-resolution
- LLM auditor source — P3.5
- Modifying `markers.py` to add `col` to `MarkerHit`
- Splitting `cli.py` into per-command modules

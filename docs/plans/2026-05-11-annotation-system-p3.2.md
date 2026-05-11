# Annotation System P3.2 — Lift Mechanical Lints + Tokens Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the write-side of the annotation system —
`science annotate audit` (mechanical sources only) and
`science annotate lift-tokens` — plus the inline/sidecar dedupe
wiring (`science markers scan --ignore-lifted` and the matching
`validate.sh` Section 8 bump). Builds on P3.0 (data model) and P3.1
(verify) without breaking either.

**Architecture:** A new `annotation/sources/` directory holds one
adapter per annotation source (`marker_token`, `bare-author-year`,
`short-form-ids`, `numeric-anchor`); each emits `PlannedAnnotation`
records. `annotation/audit.py` orchestrates per-file scans and an
idempotent merge with deterministic ID minting. The CLI module gains
two subcommands. `markers.py` and `markers_cli.py` learn the
`--ignore-lifted` post-filter. `validate.sh` Section 8 picks up the
flag in the same managed-artifact bump.

**Tech Stack:** Python 3.11, click, rdflib (already in P3.0), pytest.
No new dependencies.

---

## Spec references

This plan implements the approved spec at
`docs/plans/2026-05-11-annotation-system-p3.2-spec.md`. Quick map
from spec sections to plan tasks:

| Spec section | Tasks |
|---|---|
| §Persisting `match_text` on the model | Task 1 |
| §Selector construction → `LintIssue.match` contract | Task 2 |
| §Module layout — `sources/base.py` | Task 3 |
| §Module layout — `sources/marker_token.py` | Task 4 |
| §Module layout — `sources/lint.py` + `__init__.py` | Tasks 5–6 |
| §`audit.py` (mint_id, merge_planned, audit_file) | Task 7 |
| §`audit` semantics (CLI) | Task 8 |
| §`lift-tokens` semantics (CLI, mirror + remove) | Task 9 |
| §Section 8 dedupe — `--ignore-lifted` flag | Task 10 |
| §Section 8 dedupe — `validate.sh` + registry bump | Task 11 |

Out of scope (per spec §Non-goals): `prose lint` refactor,
`--since <git-ref>`, body promotion (cites/entity-mention), status
mutation CLI, AuditLedger usage, `frontmatter-inline-gap` lift,
render/list surfaces.

---

## File Structure

**Create (source):**

- `science/src/science_tool/annotation/sources/__init__.py` —
  `SOURCES` registry, `LINT_SOURCES` tuple
- `science/src/science_tool/annotation/sources/base.py` —
  `SourceAdapter` protocol, `PlannedAnnotation` dataclass,
  `IdCollisionError`
- `science/src/science_tool/annotation/sources/marker_token.py` —
  `MarkerTokenSource`
- `science/src/science_tool/annotation/sources/lint.py` —
  `LintSource` (three module-level instances)
- `science/src/science_tool/annotation/audit.py` — `mint_id`,
  `merge_planned`, `audit_file`, `AuditFileReport`

**Modify (source):**

- `science/src/science_tool/annotation/model.py` — add
  `Annotation.match_text: Optional[str] = None`
- `science/src/science_tool/annotation/io.py` — emit / parse
  `sci:matchText`
- `science/src/science_tool/prose_lint.py` — add required
  `LintIssue.match: str` field; populate in all four detectors
- `science/src/science_tool/annotation/cli.py` — add `audit` and
  `lift-tokens` subcommands
- `science/src/science_tool/markers.py` — add `scan_text` line-range
  helper or re-export (consumed by `MarkerTokenSource`)
- `science/src/science_tool/markers_cli.py` — add `--ignore-lifted`
  flag to `scan`
- `science/src/science_tool/project_artifacts/data/validate.sh` —
  Section 8 picks up `--ignore-lifted`
- `science/src/science_tool/project_artifacts/registry.yaml` — version
  + body_hash bump, migration entry, changelog

**Create (tests):**

- `science/tests/test_annotation_model_match_text.py`
- `science/tests/test_prose_lint_match_field.py`
- `science/tests/test_annotation_sources_marker_token.py`
- `science/tests/test_annotation_sources_lint.py`
- `science/tests/test_annotation_audit_merge.py`
- `science/tests/test_annotate_audit_cli.py`
- `science/tests/test_annotate_lift_tokens_cli.py`
- `science/tests/test_markers_scan_ignore_lifted.py`
- `science/tests/test_validate_sh_section_8.py`

**Modify (tests):**

- `science/tests/test_prose_lint.py` — add `match=` to every
  `LintIssue(...)` construction (mechanical edit; covered in Task 2)

**Create (fixtures):**

- `science/tests/_fixtures/annotation/audit/bare-author-year.md`
- `science/tests/_fixtures/annotation/audit/short-form-ids.md`
- `science/tests/_fixtures/annotation/audit/numeric-anchor.md`
- `science/tests/_fixtures/annotation/audit/mixed-tokens.md`
- `science/tests/_fixtures/annotation/audit/clean-after-remove.md`
- `science/tests/_fixtures/annotation/audit/clean-after-remove.expected.md`
- `science/tests/_fixtures/annotation/audit/paper.v1.md`

---

## Tasks

### Task 1: `Annotation.match_text` field + `sci:matchText` round-trip

**Files:**
- Modify: `science/src/science_tool/annotation/model.py`
- Modify: `science/src/science_tool/annotation/io.py`
- Test: `science/tests/test_annotation_model_match_text.py`

This task is the prerequisite for everything else: without persisted
`match_text`, the dedupe key cannot survive a write/read cycle.

- [ ] **Step 1: Write the failing tests**

Create `science/tests/test_annotation_model_match_text.py`:

```python
"""sci:matchText predicate round-trip and Annotation.match_text default."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

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


def _ann(*, match_text=None) -> Annotation:
    return Annotation(
        id="a-abc123",
        target=SpecificResource(
            source="example.md",
            selector=TextQuoteSelector(
                exact="Sample sentence with claim.",
                prefix="Some context before. ",
                suffix=" More context after.",
            ),
        ),
        bodies=(TextualBody(value="explanation"),),
        motivation=Motivation.CLASSIFYING,
        annotation_type="bare-author-year",
        source="lint:bare-author-year-v2026-05-11",
        status=Status.OPEN,
        creator="science-annotate-cli",
        created=datetime(2026, 5, 11, tzinfo=timezone.utc),
        content_hash="sha256:deadbeef",
        match_text=match_text,
    )


def test_match_text_defaults_to_none() -> None:
    ann = _ann()
    assert ann.match_text is None


def test_match_text_round_trip(tmp_path: Path) -> None:
    sidecar_path = tmp_path / "example.anno.trig"
    sidecar = Sidecar(annotations=(_ann(match_text="Brunton 2022"),))
    write_sidecar(sidecar_path, sidecar)
    loaded = read_sidecar(sidecar_path)
    assert loaded.annotations[0].match_text == "Brunton 2022"


def test_match_text_absent_round_trip(tmp_path: Path) -> None:
    sidecar_path = tmp_path / "example.anno.trig"
    sidecar = Sidecar(annotations=(_ann(match_text=None),))
    write_sidecar(sidecar_path, sidecar)
    loaded = read_sidecar(sidecar_path)
    assert loaded.annotations[0].match_text is None
    written = sidecar_path.read_text(encoding="utf-8")
    assert "sci:matchText" not in written


def test_match_text_emission_order(tmp_path: Path) -> None:
    """sci:matchText appears next to sci:liftedFrom in serialized output."""
    sidecar_path = tmp_path / "example.anno.trig"
    sidecar = Sidecar(annotations=(_ann(match_text="[UNVERIFIED]"),))
    write_sidecar(sidecar_path, sidecar)
    text = sidecar_path.read_text(encoding="utf-8")
    assert "sci:matchText" in text
    # Either sci:liftedFrom is absent (this row has no lifted_from) or
    # it appears just before sci:matchText. We accept either ordering
    # but require the predicate to be present and parseable.
    loaded = read_sidecar(sidecar_path)
    assert loaded.annotations[0].match_text == "[UNVERIFIED]"
```

- [ ] **Step 2: Run tests to confirm they fail**

Run: `uv run pytest science/tests/test_annotation_model_match_text.py -v`
Expected: FAIL — `Annotation` has no `match_text` field.

- [ ] **Step 3: Add the field on `Annotation`**

Edit `science/src/science_tool/annotation/model.py`. Add after the
existing `lifted_from` field:

```python
@dataclass(frozen=True)
class Annotation:
    id: str
    target: SpecificResource
    bodies: tuple[Body, ...]
    motivation: Motivation
    annotation_type: str
    source: str
    status: Status
    creator: str                          # original producing agent (preserved across mutations)
    created: datetime
    content_hash: Optional[str] = None
    modified: Optional[datetime] = None
    modified_by: Optional[str] = None     # actor of most recent status mutation
    description: Optional[str] = None
    lifted_from: Optional[str] = None
    match_text: Optional[str] = None      # per-finding identity (P3.2 dedupe key)
    prior_states: tuple[PriorState, ...] = ()
```

Leave `__post_init__` unchanged — `match_text` carries no
invariants.

- [ ] **Step 4: Emit `sci:matchText` from `write_sidecar`**

Edit `science/src/science_tool/annotation/io.py`, function
`_emit_annotation`. Locate the existing `sci:liftedFrom` emission
and add the `sci:matchText` emission next to it. Find the block that
emits `sci:liftedFrom` (search for `lifted_from` in the file) and
add immediately after:

```python
    if ann.match_text is not None:
        out.append(f"    sci:matchText     {_str_lit(ann.match_text)} ;")
```

If no `sci:liftedFrom` block exists yet (P3.0 scaffold did not
include it), add both: search for `sci:source` emission in
`_emit_annotation` and append the `lifted_from` and `match_text`
clauses immediately after, before `dc:creator`.

- [ ] **Step 5: Parse `sci:matchText` in `read_sidecar`**

Edit `science/src/science_tool/annotation/io.py`. Find the
annotation parser (function `_iter_annotations` or equivalent that
constructs an `Annotation`). Locate the existing extraction of
`sci:liftedFrom` (the parser that maps the predicate to the
`lifted_from` constructor arg) and add an analogous extraction:

```python
SCI_MATCH_TEXT = SCI.matchText
...
match_text_value = ds.value(ann_subj, SCI_MATCH_TEXT)
match_text = str(match_text_value) if match_text_value is not None else None
...
return Annotation(
    ...,
    lifted_from=lifted_from,
    match_text=match_text,
    ...
)
```

If the existing parser does not yet expose a `lifted_from` extraction
either, write both. The `SCI` namespace constant at the top of
`io.py` already provides `SCI.matchText` via `Namespace`.

- [ ] **Step 6: Run tests to confirm they pass**

Run: `uv run pytest science/tests/test_annotation_model_match_text.py -v`
Expected: PASS (4 tests).

- [ ] **Step 7: Confirm P3.0/P3.1 tests still pass**

Run: `uv run pytest science/tests/ -q -k "annotation or annotate"`
Expected: all annotation tests green; no regressions.

- [ ] **Step 8: Commit**

```bash
git add science/src/science_tool/annotation/model.py \
        science/src/science_tool/annotation/io.py \
        science/tests/test_annotation_model_match_text.py
git commit -m "feat(annotation): persist match_text via sci:matchText predicate (P3.2 prep)"
```

---

### Task 2: `LintIssue.match` required field + detector population

**Files:**
- Modify: `science/src/science_tool/prose_lint.py`
- Modify: `science/tests/test_prose_lint.py` (additive `match=` argument)
- Test: `science/tests/test_prose_lint_match_field.py`

- [ ] **Step 1: Write the failing tests**

Create `science/tests/test_prose_lint_match_field.py`:

```python
"""LintIssue.match field is populated correctly by all four detectors."""

from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.prose_lint import (
    LintIssue,
    detect_bare_author_year,
    detect_frontmatter_inline_gaps,
    detect_numeric_anchor,
    detect_short_form_ids,
)


def test_lint_issue_match_is_required() -> None:
    """match is required (no default) so detectors cannot forget it."""
    with pytest.raises(TypeError):
        LintIssue(  # type: ignore[call-arg]
            file=Path("x.md"),
            line=1,
            col=1,
            check="bare-author-year",
            severity="warn",
            message="msg",
        )


def test_bare_author_year_match_value(tmp_path: Path) -> None:
    md = tmp_path / "f.md"
    md.write_text("Some background. Brunton 2022 wrote about modes.\n")
    issues = detect_bare_author_year(md)
    assert len(issues) == 1
    assert issues[0].match == "Brunton 2022"


def test_short_form_ids_match_value(tmp_path: Path) -> None:
    md = tmp_path / "f.md"
    md.write_text("Bare reference: h04 needs canonicalization.\n")
    issues = detect_short_form_ids(md)
    assert len(issues) == 1
    assert issues[0].match == "h04"


def test_numeric_anchor_match_value(tmp_path: Path) -> None:
    md = tmp_path / "f.md"
    md.write_text("Some discovery rate of 42% was claimed here.\n")
    issues = detect_numeric_anchor(md, anchor_patterns=[])
    assert len(issues) >= 1
    assert any(i.match == "42%" for i in issues)


def test_frontmatter_inline_gap_match_value(tmp_path: Path) -> None:
    md = tmp_path / "f.md"
    md.write_text(
        "---\nrelated:\n  - hypothesis:h99-missing\n---\nBody text.\n"
    )
    issues = detect_frontmatter_inline_gaps(md)
    assert len(issues) == 1
    assert issues[0].match == "hypothesis:h99-missing"
```

- [ ] **Step 2: Run tests to confirm they fail**

Run: `uv run pytest science/tests/test_prose_lint_match_field.py -v`
Expected: FAIL — `LintIssue` accepts construction without `match`.

- [ ] **Step 3: Add `match: str` to `LintIssue`**

Edit `science/src/science_tool/prose_lint.py`. Replace the existing
dataclass:

```python
@dataclass(frozen=True)
class LintIssue:
    file: Path
    line: int
    col: int
    check: str
    severity: str
    message: str
    match: str
```

`match` is required (no default), positioned after `message` so the
field shows up at the end of the JSON dict (least disruptive ordering
for any consumer that pretty-prints the row).

- [ ] **Step 4: Populate `match` in `detect_bare_author_year`**

Inside the `for match in _BARE_AUTHOR_YEAR_RE.finditer(line):` loop,
the existing code computes `mention = f"{match.group(1)} {match.group(2)}"`.
Update the `LintIssue(...)` construction to pass that as the new
field:

```python
            issues.append(
                LintIssue(
                    file=path,
                    line=lineno,
                    col=match.start() + 1,
                    check="bare-author-year",
                    severity=severity_for("bare-author-year", strict=strict),
                    message=f"bare author-year mention '{mention}' has no adjacent [@key]",
                    match=mention,
                )
            )
```

- [ ] **Step 5: Populate `match` in `detect_short_form_ids`**

Inside the `for match in _SHORT_FORM_RE.finditer(line):` loop, the
existing code computes `short = match.group(0)`. Update construction:

```python
            issues.append(
                LintIssue(
                    file=path,
                    line=lineno,
                    col=match.start() + 1,
                    check="short-form-ids",
                    severity=severity_for("short-form-ids", strict=strict),
                    message=f"short-form ID '{short}' should be canonical '{kind}:…'",
                    match=short,
                )
            )
```

- [ ] **Step 6: Populate `match` in `detect_numeric_anchor`**

Inside the inner loop, `value = match.group(0)` is already computed.
Update construction:

```python
            issues.append(
                LintIssue(
                    file=path,
                    line=lineno,
                    col=match.start() + 1,
                    check="numeric-anchor",
                    severity=severity_for("numeric-anchor", strict=strict),
                    message=f"numeric claim '{value}' has no anchor in this paragraph",
                    match=value,
                )
            )
```

- [ ] **Step 7: Populate `match` in `detect_frontmatter_inline_gaps`**

Update the issue construction in the `for ref in related:` loop:

```python
        issues.append(
            LintIssue(
                file=path,
                line=1,
                col=1,
                check="frontmatter-inline-gap",
                severity=severity_for("frontmatter-inline-gap", strict=strict),
                message=f"frontmatter related entry '{ref}' never appears in body prose",
                match=ref,
            )
        )
```

- [ ] **Step 8: Update existing prose-lint tests**

Run: `uv run pytest science/tests/test_prose_lint.py -v 2>&1 | head -40`
Expected: failures with `TypeError: __init__() missing 1 required positional argument: 'match'`.

For every `LintIssue(...)` construction in
`science/tests/test_prose_lint.py`, add a `match=` argument. The
value should be a literal that mirrors the relevant detector
behavior — for assertions that match by `(file, line, col, check)`
the test still passes; for full-equality tests pick the matching
literal from the underlying regex hit. Use the `message` field's
quoted substring as the source of truth:

```bash
# Find all such constructions:
grep -n "LintIssue(" science/tests/test_prose_lint.py
```

Edit each one in place.

- [ ] **Step 9: Run all prose-lint tests to confirm green**

Run: `uv run pytest science/tests/test_prose_lint.py science/tests/test_prose_lint_match_field.py -v`
Expected: PASS.

- [ ] **Step 10: Sanity-check `science prose lint` JSON shape**

Run:

```bash
mkdir -p /tmp/p32-lint-smoke/doc && cd /tmp/p32-lint-smoke
echo "Background: Brunton 2022 wrote about modes." > doc/x.md
uv run --project /mnt/ssd/Dropbox/science/science science prose lint --root . --format json | python3 -m json.tool
```

Expected: each `hits[*]` object now contains a `"match"` key
alongside the existing keys. Spec endorses this additive change.

- [ ] **Step 11: Commit**

```bash
git add science/src/science_tool/prose_lint.py \
        science/tests/test_prose_lint.py \
        science/tests/test_prose_lint_match_field.py
git commit -m "feat(prose-lint): add required LintIssue.match field for P3.2 dedupe"
```

---

### Task 3: `annotation/sources/base.py` — protocol + dataclasses

**Files:**
- Create: `science/src/science_tool/annotation/sources/__init__.py`
- Create: `science/src/science_tool/annotation/sources/base.py`
- Test: covered indirectly via Task 4/5 source tests; this task adds
  one direct test for `IdCollisionError` formatting.

- [ ] **Step 1: Write the failing test**

Create `science/tests/test_annotation_sources_base.py`:

```python
"""Smoke test for the SourceAdapter protocol + IdCollisionError shape."""

from __future__ import annotations

import pytest

from science_tool.annotation.model import (
    Motivation, SpecificResource, TextQuoteSelector, TextualBody,
)
from science_tool.annotation.sources.base import (
    IdCollisionError,
    PlannedAnnotation,
)


def test_planned_annotation_construction() -> None:
    p = PlannedAnnotation(
        target=SpecificResource(
            source="x.md",
            selector=TextQuoteSelector(exact="abc", prefix="", suffix=""),
        ),
        annotation_type="bare-author-year",
        motivation=Motivation.CLASSIFYING,
        body=TextualBody(value="msg"),
        match_text="Brunton 2022",
        source_name="lint:bare-author-year-v2026-05-11",
    )
    assert p.lifted_from is None
    assert p.match_text == "Brunton 2022"


def test_id_collision_error_carries_message() -> None:
    err = IdCollisionError("boom")
    assert "boom" in str(err)
```

- [ ] **Step 2: Run test to confirm it fails**

Run: `uv run pytest science/tests/test_annotation_sources_base.py -v`
Expected: FAIL — module does not exist.

- [ ] **Step 3: Create the package marker**

Create `science/src/science_tool/annotation/sources/__init__.py`:

```python
# science/src/science_tool/annotation/sources/__init__.py
"""Annotation source adapters.

Each adapter scans a markdown file and emits PlannedAnnotation
records consumed by `annotation.audit.merge_planned`. See spec
docs/plans/2026-05-11-annotation-system-p3.2-spec.md §Module layout.
"""

from __future__ import annotations

from science_tool.annotation.sources.base import (
    IdCollisionError,
    PlannedAnnotation,
    SourceAdapter,
)

__all__ = ["IdCollisionError", "PlannedAnnotation", "SourceAdapter"]
```

The `SOURCES` registry and `LINT_SOURCES` tuple are added in Task 6
once the concrete adapters land.

- [ ] **Step 4: Create `base.py`**

Create `science/src/science_tool/annotation/sources/base.py`:

```python
# science/src/science_tool/annotation/sources/base.py
"""Source adapter protocol and shared dataclasses.

A SourceAdapter scans a single markdown file and returns an iterable
of PlannedAnnotation records. The audit orchestrator calls
adapters per file, then hands the planned rows to merge_planned for
idempotent persistence.

See spec docs/plans/2026-05-11-annotation-system-p3.2-spec.md
§Module layout for the contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Protocol

from science_tool.annotation.model import (
    Body,
    Motivation,
    SpecificResource,
)


class IdCollisionError(RuntimeError):
    """Raised when mint_id encounters an unrelated 4-tuple at a base ID.

    This is a structural problem (hash slice too short for the
    sidecar size); the operator should bump the slice length.
    Distinct from the same-finding-superseded-predecessor case,
    which mint_id resolves by appending `-N`.
    """


@dataclass(frozen=True)
class PlannedAnnotation:
    """A would-be annotation, before idempotence + ID minting.

    `match_text` is the per-finding identity token (the specific
    substring or token literal the source flagged). It distinguishes
    multiple findings within the same target sentence.

    `source_name` is the full source-version string (e.g.,
    "lint:bare-author-year-v2026-05-11"). All planned rows for a
    single merge_planned call MUST share this value.
    """

    target: SpecificResource
    annotation_type: str
    motivation: Motivation
    body: Body
    match_text: str
    source_name: str
    lifted_from: Optional[str] = None


class SourceAdapter(Protocol):
    """Protocol every annotation source implements.

    `name` is the full source-version string written into the
    `sci:source` field on persisted rows. `short_name` is the
    user-facing CLI value accepted by `--source`.
    """

    name: str
    short_name: str

    def scan(self, md_path: Path) -> Iterable[PlannedAnnotation]: ...
```

- [ ] **Step 5: Run test to confirm it passes**

Run: `uv run pytest science/tests/test_annotation_sources_base.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/annotation/sources/__init__.py \
        science/src/science_tool/annotation/sources/base.py \
        science/tests/test_annotation_sources_base.py
git commit -m "feat(annotation): scaffold sources package + SourceAdapter protocol"
```

---

### Task 4: `MarkerTokenSource`

**Files:**
- Create: `science/src/science_tool/annotation/sources/marker_token.py`
- Test: `science/tests/test_annotation_sources_marker_token.py`
- Test fixture: `science/tests/_fixtures/annotation/audit/mixed-tokens.md`

- [ ] **Step 1: Create the fixture**

Create `science/tests/_fixtures/annotation/audit/mixed-tokens.md`:

```markdown
---
title: Mixed tokens fixture
---

This claim is uncited [UNVERIFIED] and stands alone.

Citation pending here [MISSING_CITATION] in another sentence.

A speculative leap [SPECULATION] sits inside its own paragraph.

Only available behind a paywall [INACCESSIBLE].

Inline `[UNVERIFIED]` inside backticks should be skipped.

```bash
# Fenced code: [MISSING_CITATION] is documentation, not an annotation.
```
```

- [ ] **Step 2: Write the failing tests**

Create `science/tests/test_annotation_sources_marker_token.py`:

```python
"""MarkerTokenSource scanning, mirror vs remove selector text."""

from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.annotation.model import Motivation
from science_tool.annotation.sources.marker_token import (
    MarkerTokenSource,
    TOKEN_SOURCE_NAME,
    TOKEN_TYPE_MAP,
)

FIXTURE = (
    Path(__file__).parent
    / "_fixtures" / "annotation" / "audit" / "mixed-tokens.md"
)


def test_token_source_name_constant() -> None:
    assert TOKEN_SOURCE_NAME == "marker-scanner:phase-2"


def test_scan_finds_four_unique_tokens() -> None:
    src = MarkerTokenSource()
    rows = list(src.scan(FIXTURE))
    types = sorted(r.annotation_type for r in rows)
    assert types == ["inaccessible", "missing-citation", "speculation", "unverified"]


def test_scan_skips_documentation_and_fenced() -> None:
    src = MarkerTokenSource()
    rows = list(src.scan(FIXTURE))
    # Only 4 hits — backticked + fenced occurrences excluded.
    assert len(rows) == 4


def test_scan_sets_lifted_from_and_match_text() -> None:
    src = MarkerTokenSource()
    rows = list(src.scan(FIXTURE))
    for row in rows:
        assert row.lifted_from is not None
        assert row.lifted_from == row.match_text
        assert row.lifted_from.startswith("[") and row.lifted_from.endswith("]")
        assert row.source_name == TOKEN_SOURCE_NAME
        assert row.motivation == Motivation.CLASSIFYING


def test_scan_text_uses_provided_text_directly() -> None:
    """scan_text accepts pre-computed text (used by lift-tokens --remove)."""
    src = MarkerTokenSource()
    text = "Sentence with [UNVERIFIED] inline.\n"
    rows = list(src.scan_text(Path("synthetic.md"), text))
    assert len(rows) == 1
    assert rows[0].match_text == "[UNVERIFIED]"
    assert "[UNVERIFIED]" in rows[0].target.selector.exact


def test_scan_text_zero_hits_when_tokens_already_stripped() -> None:
    src = MarkerTokenSource()
    text = "Sentence with  inline.\n"  # tokens already removed
    rows = list(src.scan_text(Path("synthetic.md"), text))
    assert rows == []


def test_token_type_map_covers_all_four_canonical_tokens() -> None:
    assert set(TOKEN_TYPE_MAP) == {
        "UNVERIFIED", "MISSING_CITATION", "SPECULATION", "INACCESSIBLE",
    }
```

- [ ] **Step 3: Run tests to confirm they fail**

Run: `uv run pytest science/tests/test_annotation_sources_marker_token.py -v`
Expected: FAIL — module does not exist.

- [ ] **Step 4: Implement `MarkerTokenSource`**

Create `science/src/science_tool/annotation/sources/marker_token.py`:

```python
# science/src/science_tool/annotation/sources/marker_token.py
"""Marker-token source adapter.

Lifts the four phase-2 inline tokens ([UNVERIFIED], [MISSING_CITATION],
[SPECULATION], [INACCESSIBLE]) into PlannedAnnotation rows.

See spec docs/plans/2026-05-11-annotation-system-p3.2-spec.md
§sources/marker_token.py.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

from science_tool.annotation.model import (
    Motivation,
    SpecificResource,
    TextQuoteSelector,
    TextualBody,
)
from science_tool.annotation.sources.base import PlannedAnnotation
from science_tool.markers import scan_text as _scan_markers_text

TOKEN_SCANNER_VERSION = "phase-2"
TOKEN_SOURCE_NAME = f"marker-scanner:{TOKEN_SCANNER_VERSION}"

# Canonical token → (annotation_type, body_message).
TOKEN_TYPE_MAP: dict[str, tuple[str, str]] = {
    "UNVERIFIED":       ("unverified", "verifiable claim, not yet checked"),
    "MISSING_CITATION": ("missing-citation", "claim needs source pointer"),
    "SPECULATION":      ("speculation", "author conjecture / brainstorming"),
    "INACCESSIBLE":     ("inaccessible", "paywalled / image-only / private source"),
}

_SELECTOR_CONTEXT = 60  # max prefix/suffix length, matches lint selector
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


class MarkerTokenSource:
    name: str = TOKEN_SOURCE_NAME
    short_name: str = "marker-token"

    def scan(self, md_path: Path) -> Iterable[PlannedAnnotation]:
        text = md_path.read_text(encoding="utf-8")
        return self.scan_text(md_path, text)

    def scan_text(
        self, md_path: Path, text: str,
    ) -> Iterable[PlannedAnnotation]:
        # strict=False: severity is informational here; we only care
        # about hit positions and tokens.
        hits = _scan_markers_text(md_path, text, strict=False)
        out: list[PlannedAnnotation] = []
        for hit in hits:
            if hit.in_documentation:
                continue
            atype, body_msg = TOKEN_TYPE_MAP[hit.token]
            literal = f"[{hit.token}]"
            sentence_range = _sentence_range_at(text, hit.line, literal)
            if sentence_range is None:
                continue
            sel = _build_selector(text, sentence_range, _SELECTOR_CONTEXT)
            target = SpecificResource(
                source=md_path.name,
                selector=sel,
            )
            body = TextualBody(value=f"{body_msg} (lifted from {literal})")
            out.append(
                PlannedAnnotation(
                    target=target,
                    annotation_type=atype,
                    motivation=Motivation.CLASSIFYING,
                    body=body,
                    match_text=literal,
                    source_name=TOKEN_SOURCE_NAME,
                    lifted_from=literal,
                )
            )
        return out


def _line_offsets(text: str) -> list[int]:
    """Return char offsets of the start of each 1-indexed line."""
    offsets = [0]
    for i, ch in enumerate(text):
        if ch == "\n":
            offsets.append(i + 1)
    return offsets


def _sentence_range_at(
    text: str, line: int, anchor_literal: str,
) -> tuple[int, int] | None:
    """Return (start, end) char range of the sentence containing `line`.

    If the literal is present on that line, prefer the sentence
    containing the literal occurrence on the line. Otherwise fall back
    to the first sentence overlapping the line.
    """
    offsets = _line_offsets(text)
    if line < 1 or line > len(offsets):
        return None
    line_start = offsets[line - 1]
    line_end = offsets[line] if line < len(offsets) else len(text)
    line_text = text[line_start:line_end]
    anchor_pos_on_line = line_text.find(anchor_literal)
    anchor_pos = (
        line_start + anchor_pos_on_line if anchor_pos_on_line >= 0 else line_start
    )
    # Find the sentence that contains anchor_pos.
    cursor = 0
    for sent in _SENTENCE_SPLIT_RE.split(text):
        start = text.find(sent, cursor)
        if start == -1:
            continue
        end = start + len(sent)
        if start <= anchor_pos < end:
            return (start, end)
        cursor = end
    return None


def _build_selector(
    text: str, sentence_range: tuple[int, int], ctx: int,
) -> TextQuoteSelector:
    start, end = sentence_range
    prefix_start = max(0, start - ctx)
    suffix_end = min(len(text), end + ctx)
    return TextQuoteSelector(
        exact=text[start:end],
        prefix=text[prefix_start:start],
        suffix=text[end:suffix_end],
    )
```

- [ ] **Step 5: Run tests to confirm they pass**

Run: `uv run pytest science/tests/test_annotation_sources_marker_token.py -v`
Expected: PASS (7 tests).

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/annotation/sources/marker_token.py \
        science/tests/test_annotation_sources_marker_token.py \
        science/tests/_fixtures/annotation/audit/mixed-tokens.md
git commit -m "feat(annotation): add MarkerTokenSource lifting four inline tokens"
```

---

### Task 5: `LintSource` (three instances)

**Files:**
- Create: `science/src/science_tool/annotation/sources/lint.py`
- Test: `science/tests/test_annotation_sources_lint.py`
- Test fixtures (3): `bare-author-year.md`, `short-form-ids.md`,
  `numeric-anchor.md` under `_fixtures/annotation/audit/`

- [ ] **Step 1: Create the fixtures**

Create `science/tests/_fixtures/annotation/audit/bare-author-year.md`:

```markdown
---
title: Bare author-year fixture
---

A foundational result from Brunton 2022 reshaped the field.

Two distinct mentions in one sentence: Brunton 2022 and Spivak 1999 both relevant here.

A properly anchored reference [@kutz2016] appears with citation.
```

Create `science/tests/_fixtures/annotation/audit/short-form-ids.md`:

```markdown
---
title: Short-form IDs fixture
---

Bare reference: h04 needs canonicalization elsewhere in prose.

Already canonical: hypothesis:h04-name should NOT be flagged.

Bracketed task heading skip: [t088] in `## [t088] Title` form would be ignored.
```

Create `science/tests/_fixtures/annotation/audit/numeric-anchor.md`:

```markdown
---
title: Numeric anchor fixture
---

Discovery rate of 42% was claimed without supporting figures or tables.

A second paragraph with 3.14 ratio and no anchor either.

Anchored claim: see Figure 2 — the value 7.5 here is anchored by the figure reference.
```

- [ ] **Step 2: Write the failing tests**

Create `science/tests/test_annotation_sources_lint.py`:

```python
"""LintSource adapters: 3 instances, per-finding identity, dedupe shape."""

from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.annotation.model import Motivation
from science_tool.annotation.sources.lint import (
    DETECTOR_VERSIONS,
    LintSource,
    bare_author_year_source,
    numeric_anchor_source,
    short_form_ids_source,
    lint_source_name,
)

FX = Path(__file__).parent / "_fixtures" / "annotation" / "audit"


def test_lint_source_name_format() -> None:
    assert lint_source_name("bare-author-year") == \
        f"lint:bare-author-year-{DETECTOR_VERSIONS['bare-author-year']}"


def test_bare_author_year_source_emits_per_match_rows() -> None:
    rows = list(bare_author_year_source().scan(FX / "bare-author-year.md"))
    matches = sorted(r.match_text for r in rows)
    # Two mentions in one sentence + the standalone Brunton 2022.
    assert "Brunton 2022" in matches
    assert "Spivak 1999" in matches


def test_two_mentions_in_one_sentence_yield_two_rows() -> None:
    rows = list(bare_author_year_source().scan(FX / "bare-author-year.md"))
    # Find rows whose target.exact contains both names.
    multi = [
        r for r in rows
        if "Brunton 2022" in r.target.selector.exact
        and "Spivak 1999" in r.target.selector.exact
    ]
    matches = {r.match_text for r in multi}
    assert matches == {"Brunton 2022", "Spivak 1999"}


def test_short_form_ids_source_skips_canonical() -> None:
    rows = list(short_form_ids_source().scan(FX / "short-form-ids.md"))
    matches = [r.match_text for r in rows]
    assert "h04" in matches
    # The canonical hypothesis:h04-name occurrence must not be flagged.
    assert all(not r.target.selector.exact.startswith("Already canonical")
               or r.match_text == "h04" for r in rows)


def test_numeric_anchor_source_emits_unanchored_only() -> None:
    rows = list(numeric_anchor_source().scan(FX / "numeric-anchor.md"))
    matches = [r.match_text for r in rows]
    assert "42%" in matches
    assert "3.14" in matches


def test_lint_source_records_full_source_name() -> None:
    rows = list(bare_author_year_source().scan(FX / "bare-author-year.md"))
    assert all(
        r.source_name == lint_source_name("bare-author-year") for r in rows
    )


def test_lint_source_motivation_and_type() -> None:
    rows = list(bare_author_year_source().scan(FX / "bare-author-year.md"))
    for r in rows:
        assert r.motivation == Motivation.CLASSIFYING
        assert r.annotation_type == "bare-author-year"


def test_lint_source_lifted_from_is_none() -> None:
    rows = list(bare_author_year_source().scan(FX / "bare-author-year.md"))
    assert all(r.lifted_from is None for r in rows)


def test_lint_source_short_name_attribute() -> None:
    src = bare_author_year_source()
    assert src.short_name == "bare-author-year"
    assert isinstance(src, LintSource)
```

- [ ] **Step 3: Run tests to confirm they fail**

Run: `uv run pytest science/tests/test_annotation_sources_lint.py -v`
Expected: FAIL — module does not exist.

- [ ] **Step 4: Implement `LintSource` and three instances**

Create `science/src/science_tool/annotation/sources/lint.py`:

```python
# science/src/science_tool/annotation/sources/lint.py
"""Lint-detector source adapters.

Three module-level LintSource instances wrap the prose-lint detector
functions and emit PlannedAnnotation rows. frontmatter-inline-gap is
deferred (file-level finding doesn't fit sentence-target selectors —
see spec §Module layout).

See spec docs/plans/2026-05-11-annotation-system-p3.2-spec.md
§sources/lint.py.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from science_tool.annotation.model import (
    Motivation,
    SpecificResource,
    TextQuoteSelector,
    TextualBody,
)
from science_tool.annotation.sources.base import PlannedAnnotation
from science_tool.prose_lint import (
    LintIssue,
    detect_bare_author_year,
    detect_numeric_anchor,
    detect_short_form_ids,
)

DETECTOR_VERSIONS: dict[str, str] = {
    "bare-author-year": "v2026-05-11",
    "short-form-ids":   "v2026-05-11",
    "numeric-anchor":   "v2026-05-11",
}

_SELECTOR_CONTEXT = 60
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def lint_source_name(short: str) -> str:
    return f"lint:{short}-{DETECTOR_VERSIONS[short]}"


@dataclass(frozen=True)
class LintSource:
    short_name: str
    name: str
    annotation_type: str
    detector: Callable[..., list[LintIssue]]

    def scan(self, md_path: Path) -> Iterable[PlannedAnnotation]:
        issues = self.detector(md_path)
        try:
            text = md_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return []
        out: list[PlannedAnnotation] = []
        for issue in issues:
            sel = _selector_for_issue(text, issue)
            if sel is None:
                continue
            target = SpecificResource(source=md_path.name, selector=sel)
            body = TextualBody(value=issue.message)
            out.append(
                PlannedAnnotation(
                    target=target,
                    annotation_type=self.annotation_type,
                    motivation=Motivation.CLASSIFYING,
                    body=body,
                    match_text=issue.match,
                    source_name=self.name,
                    lifted_from=None,
                )
            )
        return out


def _line_offsets(text: str) -> list[int]:
    offsets = [0]
    for i, ch in enumerate(text):
        if ch == "\n":
            offsets.append(i + 1)
    return offsets


def _selector_for_issue(
    text: str, issue: LintIssue,
) -> TextQuoteSelector | None:
    """Build a sentence-level TextQuoteSelector for a LintIssue.

    Locates the sentence that covers the (line, col) char position
    in `text`; returns None if the position is out of range.
    """
    offsets = _line_offsets(text)
    if issue.line < 1 or issue.line > len(offsets):
        return None
    line_start = offsets[issue.line - 1]
    char_pos = line_start + max(0, issue.col - 1)
    cursor = 0
    for sent in _SENTENCE_SPLIT_RE.split(text):
        start = text.find(sent, cursor)
        if start == -1:
            continue
        end = start + len(sent)
        if start <= char_pos < end:
            return TextQuoteSelector(
                exact=text[start:end],
                prefix=text[max(0, start - _SELECTOR_CONTEXT):start],
                suffix=text[end:min(len(text), end + _SELECTOR_CONTEXT)],
            )
        cursor = end
    return None


def bare_author_year_source() -> LintSource:
    return LintSource(
        short_name="bare-author-year",
        name=lint_source_name("bare-author-year"),
        annotation_type="bare-author-year",
        detector=detect_bare_author_year,
    )


def short_form_ids_source() -> LintSource:
    return LintSource(
        short_name="short-form-ids",
        name=lint_source_name("short-form-ids"),
        annotation_type="short-form-ids",
        detector=detect_short_form_ids,
    )


def numeric_anchor_source() -> LintSource:
    return LintSource(
        short_name="numeric-anchor",
        name=lint_source_name("numeric-anchor"),
        annotation_type="numeric-anchor",
        detector=detect_numeric_anchor,
    )
```

- [ ] **Step 5: Run tests to confirm they pass**

Run: `uv run pytest science/tests/test_annotation_sources_lint.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/annotation/sources/lint.py \
        science/tests/test_annotation_sources_lint.py \
        science/tests/_fixtures/annotation/audit/bare-author-year.md \
        science/tests/_fixtures/annotation/audit/short-form-ids.md \
        science/tests/_fixtures/annotation/audit/numeric-anchor.md
git commit -m "feat(annotation): add LintSource adapters for 3 detectors (P3.2)"
```

---

### Task 6: `SOURCES` registry + `LINT_SOURCES`

**Files:**
- Modify: `science/src/science_tool/annotation/sources/__init__.py`

- [ ] **Step 1: Add a registry test**

Append to `science/tests/test_annotation_sources_base.py`:

```python
def test_sources_registry_contains_expected_keys() -> None:
    from science_tool.annotation.sources import LINT_SOURCES, SOURCES
    assert set(SOURCES) == {
        "marker-token", "bare-author-year",
        "short-form-ids", "numeric-anchor",
    }
    assert "frontmatter-inline-gap" not in SOURCES
    assert LINT_SOURCES == (
        "bare-author-year", "short-form-ids", "numeric-anchor",
    )
    assert "marker-token" not in LINT_SOURCES


def test_each_source_exposes_protocol_attrs() -> None:
    from science_tool.annotation.sources import SOURCES
    for short, src in SOURCES.items():
        assert src.short_name == short
        assert isinstance(src.name, str) and src.name
        assert callable(getattr(src, "scan"))
```

- [ ] **Step 2: Run tests to confirm they fail**

Run: `uv run pytest science/tests/test_annotation_sources_base.py -v -k registry`
Expected: FAIL — `LINT_SOURCES` / `SOURCES` not exported.

- [ ] **Step 3: Populate the registry**

Edit `science/src/science_tool/annotation/sources/__init__.py`:

```python
# science/src/science_tool/annotation/sources/__init__.py
"""Annotation source adapters.

Each adapter scans a markdown file and emits PlannedAnnotation
records consumed by `annotation.audit.merge_planned`. See spec
docs/plans/2026-05-11-annotation-system-p3.2-spec.md §Module layout.
"""

from __future__ import annotations

from science_tool.annotation.sources.base import (
    IdCollisionError,
    PlannedAnnotation,
    SourceAdapter,
)
from science_tool.annotation.sources.lint import (
    bare_author_year_source,
    numeric_anchor_source,
    short_form_ids_source,
)
from science_tool.annotation.sources.marker_token import MarkerTokenSource

SOURCES: dict[str, SourceAdapter] = {
    "marker-token":     MarkerTokenSource(),
    "bare-author-year": bare_author_year_source(),
    "short-form-ids":   short_form_ids_source(),
    "numeric-anchor":   numeric_anchor_source(),
}

LINT_SOURCES: tuple[str, ...] = (
    "bare-author-year",
    "short-form-ids",
    "numeric-anchor",
)

__all__ = [
    "IdCollisionError",
    "LINT_SOURCES",
    "PlannedAnnotation",
    "SOURCES",
    "SourceAdapter",
]
```

- [ ] **Step 4: Run tests to confirm they pass**

Run: `uv run pytest science/tests/test_annotation_sources_base.py -v`
Expected: PASS (all four tests now: 2 from Task 3 + 2 from Task 6).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/annotation/sources/__init__.py \
        science/tests/test_annotation_sources_base.py
git commit -m "feat(annotation): register SOURCES + LINT_SOURCES (P3.2)"
```

---

### Task 7: `annotation/audit.py` — `mint_id`, `merge_planned`, `audit_file`

**Files:**
- Create: `science/src/science_tool/annotation/audit.py`
- Test: `science/tests/test_annotation_audit_merge.py`

- [ ] **Step 1: Write the failing tests**

Create `science/tests/test_annotation_audit_merge.py`:

```python
"""audit.py merge + ID-minting semantics."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

import pytest

from science_tool.annotation.audit import (
    AuditFileReport,
    audit_file,
    merge_planned,
    mint_id,
)
from science_tool.annotation.lifecycle import mutate_status
from science_tool.annotation.model import (
    Annotation,
    Motivation,
    Sidecar,
    SpecificResource,
    Status,
    TextQuoteSelector,
    TextualBody,
)
from science_tool.annotation.sources.base import (
    IdCollisionError,
    PlannedAnnotation,
)

NOW = datetime(2026, 5, 11, tzinfo=timezone.utc)


def _sel(exact: str) -> TextQuoteSelector:
    return TextQuoteSelector(exact=exact, prefix="", suffix="")


def _planned(
    *, source_name="lint:bare-author-year-v2026-05-11",
    exact="A claim sentence.",
    match_text="Brunton 2022",
    lifted_from=None,
) -> PlannedAnnotation:
    return PlannedAnnotation(
        target=SpecificResource(source="x.md", selector=_sel(exact)),
        annotation_type="bare-author-year",
        motivation=Motivation.CLASSIFYING,
        body=TextualBody(value="msg"),
        match_text=match_text,
        source_name=source_name,
        lifted_from=lifted_from,
    )


def test_merge_into_empty_sidecar() -> None:
    sidecar = Sidecar()
    plans = [_planned()]
    new_sc, written = merge_planned(sidecar, plans, actor="tester", now=NOW)
    assert len(written) == 1
    assert len(new_sc.annotations) == 1
    assert written[0].status is Status.OPEN
    assert written[0].creator == "tester"
    assert written[0].created == NOW
    assert written[0].content_hash is not None
    assert written[0].content_hash.startswith("sha256:")
    assert written[0].match_text == "Brunton 2022"


def test_clean_rerun_writes_zero_rows() -> None:
    sidecar = Sidecar()
    plans = [_planned()]
    sc1, _ = merge_planned(sidecar, plans, actor="tester", now=NOW)
    sc2, written = merge_planned(sc1, plans, actor="tester", now=NOW)
    assert written == []
    assert len(sc2.annotations) == 1


def test_status_mutated_row_preserved_across_rerun() -> None:
    sidecar = Sidecar()
    plans = [_planned()]
    sc1, written = merge_planned(sidecar, plans, actor="tester", now=NOW)
    acked = mutate_status(written[0], Status.ACK, actor="kh", now=NOW)
    sc_with_ack = Sidecar(
        annotations=(acked,) + sc1.annotations[1:],
    )
    sc2, new = merge_planned(sc_with_ack, plans, actor="tester", now=NOW)
    assert new == []
    assert sc2.annotations[0].status is Status.ACK


def test_superseded_predecessor_yields_dash_2_id() -> None:
    sidecar = Sidecar()
    plans = [_planned()]
    sc1, written = merge_planned(sidecar, plans, actor="tester", now=NOW)
    sup = mutate_status(written[0], Status.SUPERSEDED, actor="auto", now=NOW)
    sc_sup = Sidecar(annotations=(sup,))
    sc2, new = merge_planned(sc_sup, plans, actor="tester", now=NOW)
    assert len(new) == 1
    assert new[0].id.endswith("-2")
    assert len(sc2.annotations) == 2


def test_unrelated_collision_raises() -> None:
    """Force a collision by manually placing an unrelated row at base_id."""
    p = _planned()
    base_id = mint_id(Sidecar(), p)
    fake = Annotation(
        id=base_id,
        target=SpecificResource(
            source="other.md", selector=_sel("Different sentence."),
        ),
        bodies=(TextualBody(value="x"),),
        motivation=Motivation.CLASSIFYING,
        annotation_type="numeric-anchor",
        source="lint:numeric-anchor-v2026-05-11",
        status=Status.OPEN,
        creator="x",
        created=NOW,
        content_hash="sha256:00",
        match_text="42%",
    )
    sc = Sidecar(annotations=(fake,))
    with pytest.raises(IdCollisionError):
        merge_planned(sc, [p], actor="tester", now=NOW)


def test_planned_vs_planned_collision_within_call_raises() -> None:
    """Two planned rows with identical 4-tuple still dedupe; with same
    base_id but different 4-tuple should raise."""
    p1 = _planned(match_text="Brunton 2022")
    p2 = _planned(match_text="Brunton 2022")  # same 4-tuple → dedupes
    sc, written = merge_planned(Sidecar(), [p1, p2], actor="t", now=NOW)
    assert len(written) == 1


def test_mint_id_deterministic_on_4_tuple() -> None:
    p_a = _planned(match_text="Brunton 2022")
    p_b = _planned(match_text="Brunton 2022")
    assert mint_id(Sidecar(), p_a) == mint_id(Sidecar(), p_b)


def test_single_source_invariant_enforced() -> None:
    p1 = _planned(source_name="lint:bare-author-year-v2026-05-11")
    p2 = _planned(source_name="lint:numeric-anchor-v2026-05-11")
    with pytest.raises(AssertionError):
        merge_planned(Sidecar(), [p1, p2], actor="t", now=NOW)


def test_content_hash_uses_target_exact_and_source_name() -> None:
    from science_tool.annotation.hash import content_hash
    p = _planned(exact="A claim sentence.")
    sc, written = merge_planned(Sidecar(), [p], actor="t", now=NOW)
    expected = content_hash("A claim sentence.", p.source_name)
    assert written[0].content_hash == expected


def test_audit_file_writes_sidecar_per_source(tmp_path: Path) -> None:
    """audit_file merges per source sequentially; both rows persisted."""
    md = tmp_path / "x.md"
    md.write_text("Sentence with [UNVERIFIED] inline.\n")
    sidecar = tmp_path / "x.anno.trig"
    from science_tool.annotation.sources import SOURCES
    report = audit_file(
        md, sidecar,
        sources=[SOURCES["marker-token"]],
        actor="tester",
        now=NOW,
    )
    assert isinstance(report, AuditFileReport)
    assert sidecar.exists()
    assert report.rows_written == 1
```

- [ ] **Step 2: Run tests to confirm they fail**

Run: `uv run pytest science/tests/test_annotation_audit_merge.py -v`
Expected: FAIL — module does not exist.

- [ ] **Step 3: Implement `audit.py`**

Create `science/src/science_tool/annotation/audit.py`:

```python
# science/src/science_tool/annotation/audit.py
"""Audit orchestration: per-source merge with deterministic ID minting.

See spec docs/plans/2026-05-11-annotation-system-p3.2-spec.md §audit.py.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Optional, Sequence

from science_tool.annotation.hash import content_hash
from science_tool.annotation.io import read_sidecar, write_sidecar
from science_tool.annotation.model import (
    Annotation,
    Sidecar,
    SpecificResource,
    Status,
)
from science_tool.annotation.sources.base import (
    IdCollisionError,
    PlannedAnnotation,
    SourceAdapter,
)


@dataclass(frozen=True)
class AuditFileReport:
    md_path: Path
    sidecar_path: Path
    rows_written: int
    duplicates_skipped: int
    written_per_source: dict[str, int]


def _annotation_tuple(
    a: Annotation,
) -> tuple[str, str, Optional[str], Optional[str]]:
    return (a.source, a.target.selector.exact, a.lifted_from, a.match_text)


def _planned_tuple(
    p: PlannedAnnotation,
) -> tuple[str, str, Optional[str], str]:
    return (p.source_name, p.target.selector.exact, p.lifted_from, p.match_text)


def _mint_base_id(p: PlannedAnnotation) -> str:
    h = hashlib.sha256()
    h.update(p.source_name.encode("utf-8"))
    h.update(b"\x1e")
    h.update(p.target.selector.exact.encode("utf-8"))
    h.update(b"\x1e")
    h.update((p.lifted_from or "").encode("utf-8"))
    h.update(b"\x1e")
    h.update(p.match_text.encode("utf-8"))
    return f"a-{h.hexdigest()[:6]}"


def mint_id(sidecar: Sidecar, p: PlannedAnnotation) -> str:
    """Mint the on-disk ID for a planned row.

    Same-finding superseded predecessor → suffix `-N`.
    Same-finding non-superseded match → unreachable (caller must
    have run merge_planned dedupe first; assert guards).
    Unrelated 4-tuple at same base_id → IdCollisionError.
    """
    base_id = _mint_base_id(p)
    existing_at_base = next(
        (a for a in sidecar.annotations if a.id == base_id), None,
    )
    if existing_at_base is None:
        return base_id

    if (
        _annotation_tuple(existing_at_base)[:3] == _planned_tuple(p)[:3]
        and existing_at_base.match_text == p.match_text
    ):
        assert existing_at_base.status is Status.SUPERSEDED, (
            "merge_planned should have skipped a non-superseded match"
        )
        existing_ids = {a.id for a in sidecar.annotations}
        n = 2
        while f"{base_id}-{n}" in existing_ids:
            n += 1
        return f"{base_id}-{n}"

    raise IdCollisionError(
        f"base_id {base_id!r} occupied by unrelated 4-tuple "
        f"(existing source={existing_at_base.source!r}, "
        f"planned source={p.source_name!r}); bump hash slice length"
    )


def merge_planned(
    sidecar: Sidecar,
    planned: Sequence[PlannedAnnotation],
    *,
    actor: str,
    now: datetime,
) -> tuple[Sidecar, list[Annotation]]:
    """Merge planned rows into sidecar; return (new_sidecar, written_rows).

    All planned rows MUST share `source_name`. Skip rule: any
    non-superseded annotation matching the 4-tuple suppresses the
    planned row. Superseded matches are ignored for skip but
    influence ID minting.
    """
    if not planned:
        return sidecar, []
    source_name = planned[0].source_name
    assert all(p.source_name == source_name for p in planned), (
        "merge_planned requires single-source planned rows"
    )

    existing = list(sidecar.annotations)
    existing_keys: dict[
        tuple[str, str, Optional[str], Optional[str]], Annotation
    ] = {_annotation_tuple(a): a for a in existing}

    written: list[Annotation] = []
    seen_planned_keys: set[tuple[str, str, Optional[str], str]] = set()
    seen_planned_base_ids: dict[str, PlannedAnnotation] = {}

    for p in planned:
        key = _planned_tuple(p)
        if key in seen_planned_keys:
            continue
        seen_planned_keys.add(key)

        existing_match = existing_keys.get(
            (p.source_name, p.target.selector.exact, p.lifted_from, p.match_text)
        )
        if existing_match is not None and existing_match.status is not Status.SUPERSEDED:
            continue

        base_id = _mint_base_id(p)
        prior_planned = seen_planned_base_ids.get(base_id)
        if prior_planned is not None:
            raise IdCollisionError(
                f"two distinct planned rows hash to base_id {base_id!r} "
                f"in one merge call; bump hash slice length"
            )
        seen_planned_base_ids[base_id] = p

        new_id = mint_id(
            Sidecar(annotations=tuple(existing + written)),
            p,
        )
        new_ann = Annotation(
            id=new_id,
            target=p.target,
            bodies=(p.body,),
            motivation=p.motivation,
            annotation_type=p.annotation_type,
            source=p.source_name,
            status=Status.OPEN,
            creator=actor,
            created=now,
            content_hash=content_hash(p.target.selector.exact, p.source_name),
            lifted_from=p.lifted_from,
            match_text=p.match_text,
        )
        written.append(new_ann)

    new_sidecar = replace(
        sidecar,
        annotations=tuple(existing + written),
    )
    return new_sidecar, written


def audit_file(
    md_path: Path,
    sidecar_path: Path,
    sources: Sequence[SourceAdapter],
    *,
    actor: str,
    now: datetime,
) -> AuditFileReport:
    """Per-file audit: read sidecar, run sources sequentially, persist."""
    if sidecar_path.exists():
        sidecar = read_sidecar(sidecar_path)
    else:
        sidecar = Sidecar()

    total_written = 0
    total_skipped = 0
    per_source: dict[str, int] = {}
    any_writes = False

    for source in sources:
        plans = list(source.scan(md_path))
        if not plans:
            per_source[source.short_name] = 0
            continue
        before_count = len(sidecar.annotations)
        sidecar, written = merge_planned(
            sidecar, plans, actor=actor, now=now,
        )
        per_source[source.short_name] = len(written)
        total_written += len(written)
        total_skipped += len(plans) - len(written)
        if written:
            any_writes = True

    if any_writes:
        sidecar_path.parent.mkdir(parents=True, exist_ok=True)
        write_sidecar(sidecar_path, sidecar)

    return AuditFileReport(
        md_path=md_path,
        sidecar_path=sidecar_path,
        rows_written=total_written,
        duplicates_skipped=total_skipped,
        written_per_source=per_source,
    )
```

- [ ] **Step 4: Run tests to confirm they pass**

Run: `uv run pytest science/tests/test_annotation_audit_merge.py -v`
Expected: PASS.

- [ ] **Step 5: Confirm no regressions**

Run: `uv run pytest science/tests/ -q -k "annotation or annotate"`
Expected: green.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/annotation/audit.py \
        science/tests/test_annotation_audit_merge.py
git commit -m "feat(annotation): add audit.py with mint_id, merge_planned, audit_file"
```

---

### Task 8: `science annotate audit` CLI subcommand

**Files:**
- Modify: `science/src/science_tool/annotation/cli.py`
- Test: `science/tests/test_annotate_audit_cli.py`

- [ ] **Step 1: Write the failing tests**

Create `science/tests/test_annotate_audit_cli.py`:

```python
"""CLI: science annotate audit."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from click.testing import CliRunner

from science_tool.annotation.cli import annotate_group

FX = Path(__file__).parent / "_fixtures" / "annotation" / "audit"


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    doc = tmp_path / "doc"
    doc.mkdir()
    for name in ("bare-author-year.md", "short-form-ids.md", "numeric-anchor.md"):
        shutil.copy(FX / name, doc / name)
    return tmp_path


def test_audit_default_runs_lint_sources(workspace: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        annotate_group,
        ["audit", "--root", str(workspace), "--actor", "tester"],
    )
    assert result.exit_code == 0
    assert any(
        (workspace / "doc" / f"{stem}.anno.trig").exists()
        for stem in ("bare-author-year", "short-form-ids", "numeric-anchor")
    )


def test_audit_source_filter(workspace: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        annotate_group,
        [
            "audit", "--root", str(workspace),
            "--source", "bare-author-year",
            "--actor", "tester",
        ],
    )
    assert result.exit_code == 0
    assert (workspace / "doc" / "bare-author-year.anno.trig").exists()
    assert not (workspace / "doc" / "numeric-anchor.anno.trig").exists()


def test_audit_unknown_source_rejected(workspace: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        annotate_group,
        [
            "audit", "--root", str(workspace),
            "--source", "made-up-source", "--actor", "tester",
        ],
    )
    assert result.exit_code == 1
    assert "made-up-source" in (result.output + (str(result.exception) or ""))


def test_audit_marker_token_accepted_as_source(workspace: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        annotate_group,
        [
            "audit", "--root", str(workspace),
            "--source", "marker-token", "--actor", "tester",
        ],
    )
    assert result.exit_code == 0


def test_audit_frontmatter_inline_gap_rejected(workspace: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        annotate_group,
        [
            "audit", "--root", str(workspace),
            "--source", "frontmatter-inline-gap", "--actor", "tester",
        ],
    )
    assert result.exit_code == 1


def test_audit_dry_run_writes_no_files(workspace: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        annotate_group,
        [
            "audit", "--root", str(workspace),
            "--dry-run", "--actor", "tester",
        ],
    )
    assert result.exit_code == 0
    for stem in ("bare-author-year", "short-form-ids", "numeric-anchor"):
        assert not (workspace / "doc" / f"{stem}.anno.trig").exists()


def test_audit_format_json_shape(workspace: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        annotate_group,
        [
            "audit", "--root", str(workspace),
            "--format", "json", "--actor", "tester",
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert "summary" in payload
    assert "files" in payload
    assert payload["summary"]["files_scanned"] >= 3
    assert isinstance(payload["summary"]["sources_run"], list)
    assert any(
        s.startswith("lint:bare-author-year-")
        for s in payload["summary"]["sources_run"]
    )


def test_audit_records_actor_as_creator(workspace: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        annotate_group,
        [
            "audit", "--root", str(workspace),
            "--source", "bare-author-year",
            "--actor", "operator-alpha",
        ],
    )
    assert result.exit_code == 0
    sidecar = (workspace / "doc" / "bare-author-year.anno.trig").read_text()
    assert "operator-alpha" in sidecar


def test_audit_no_llm_flag_accepted(workspace: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        annotate_group,
        [
            "audit", "--root", str(workspace),
            "--no-llm", "--actor", "tester",
        ],
    )
    assert result.exit_code == 0


def test_audit_rerun_writes_zero_new_rows(workspace: Path) -> None:
    runner = CliRunner()
    args = [
        "audit", "--root", str(workspace),
        "--source", "bare-author-year",
        "--format", "json", "--actor", "tester",
    ]
    runner.invoke(annotate_group, args)
    second = runner.invoke(annotate_group, args)
    assert second.exit_code == 0
    payload = json.loads(second.output)
    assert payload["summary"]["rows_written"] == 0
```

- [ ] **Step 2: Run tests to confirm they fail**

Run: `uv run pytest science/tests/test_annotate_audit_cli.py -v`
Expected: FAIL — `audit` subcommand doesn't exist on `annotate_group`.

- [ ] **Step 3: Add the `audit` subcommand**

Edit `science/src/science_tool/annotation/cli.py`. Add at the top
of the file (after existing imports — preserve the existing
`verify` subcommand wiring):

```python
import json
from datetime import datetime, timezone
from pathlib import Path

import click

from science_tool.annotation.audit import audit_file
from science_tool.annotation.sources import LINT_SOURCES, SOURCES
```

Add the new subcommand to the existing `annotate_group`:

```python
@annotate_group.command("audit")
@click.option(
    "--root", "root_path",
    default=".",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
)
@click.option(
    "--source", "sources_opt",
    multiple=True,
    help=(
        "Source short name (repeatable). Defaults to LINT_SOURCES. "
        "Valid: " + ", ".join(sorted(SOURCES))
    ),
)
@click.option(
    "--no-llm", is_flag=True, default=False,
    help="Skip LLM sources (forward-compat no-op in P3.2).",
)
@click.option("--dry-run", is_flag=True, default=False)
@click.option(
    "--format", "fmt",
    type=click.Choice(("table", "json")), default="table",
)
@click.option("--actor", default="science-annotate-cli")
def audit_cmd(
    root_path: Path,
    sources_opt: tuple[str, ...],
    no_llm: bool,
    dry_run: bool,
    fmt: str,
    actor: str,
) -> None:
    """Run mechanical-audit sources; write planned rows to sidecars."""
    del no_llm  # accepted; P3.2 has no LLM sources to skip
    selected_names = tuple(sources_opt) if sources_opt else LINT_SOURCES
    unknown = [s for s in selected_names if s not in SOURCES]
    if unknown:
        click.echo(f"unknown source(s): {unknown!r}", err=True)
        raise SystemExit(1)
    selected = [SOURCES[s] for s in selected_names]
    full_source_names = sorted({s.name for s in selected})

    root = root_path.resolve()
    md_files = _collect_audit_markdown_files(root)
    now = datetime.now(timezone.utc)

    file_reports: list[dict] = []
    summary = {
        "files_scanned": len(md_files),
        "rows_written": 0,
        "duplicates_skipped": 0,
        "files_with_writes": 0,
        "sources_run": full_source_names,
    }

    for md in md_files:
        sidecar = md.with_suffix(".anno.trig")
        if dry_run:
            planned_per_source = {}
            for src in selected:
                plans = list(src.scan(md))
                planned_per_source[src.short_name] = len(plans)
            file_reports.append({
                "path": str(md.relative_to(root)),
                "rows_planned": planned_per_source,
            })
            continue
        report = audit_file(
            md, sidecar, sources=selected, actor=actor, now=now,
        )
        if report.rows_written or report.duplicates_skipped:
            file_reports.append({
                "path": str(md.relative_to(root)),
                "rows_written": report.written_per_source,
                "duplicates_skipped": report.duplicates_skipped,
            })
        summary["rows_written"] += report.rows_written
        summary["duplicates_skipped"] += report.duplicates_skipped
        if report.rows_written:
            summary["files_with_writes"] += 1

    if fmt == "json":
        click.echo(json.dumps({"summary": summary, "files": file_reports}, indent=2))
    else:
        _emit_audit_table(summary, file_reports, dry_run=dry_run)


def _collect_audit_markdown_files(root: Path) -> list[Path]:
    """Mirror prose_lint._collect_markdown_files but importable here."""
    from science_tool.prose_lint import _collect_markdown_files  # noqa: PLC0415
    return _collect_markdown_files(root)


def _emit_audit_table(
    summary: dict, files: list[dict], *, dry_run: bool,
) -> None:
    if dry_run:
        click.echo(f"audit dry-run over {summary['files_scanned']} file(s):")
    else:
        click.echo(
            f"audit: {summary['rows_written']} row(s) written, "
            f"{summary['duplicates_skipped']} duplicate(s) skipped, "
            f"{summary['files_with_writes']} file(s) modified."
        )
    for entry in files:
        click.echo(f"  {entry['path']}: {entry}")
```

- [ ] **Step 4: Run tests to confirm they pass**

Run: `uv run pytest science/tests/test_annotate_audit_cli.py -v`
Expected: PASS.

- [ ] **Step 5: Sanity check — `--help` listing**

Run: `uv run --project science science annotate audit --help`
Expected: shows `--root`, `--source`, `--no-llm`, `--dry-run`,
`--format`, `--actor`.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/annotation/cli.py \
        science/tests/test_annotate_audit_cli.py
git commit -m "feat(annotate): add 'audit' subcommand for mechanical sources (P3.2)"
```

---

### Task 9: `science annotate lift-tokens` CLI subcommand

**Files:**
- Modify: `science/src/science_tool/annotation/cli.py`
- Test: `science/tests/test_annotate_lift_tokens_cli.py`
- Test fixtures: `clean-after-remove.md`,
  `clean-after-remove.expected.md`, `paper.v1.md` under
  `_fixtures/annotation/audit/`

- [ ] **Step 1: Create the fixtures**

Create `science/tests/_fixtures/annotation/audit/clean-after-remove.md`:

```markdown
---
title: Clean-after-remove fixture
---

The first sentence is uncited [UNVERIFIED] and stands alone.

A second concern is missing citations [MISSING_CITATION] in this paragraph.
```

Create `science/tests/_fixtures/annotation/audit/clean-after-remove.expected.md`:

```markdown
---
title: Clean-after-remove fixture
---

The first sentence is uncited and stands alone.

A second concern is missing citations in this paragraph.
```

Create `science/tests/_fixtures/annotation/audit/paper.v1.md`:

```markdown
---
title: Paper v1 fixture (multi-dotted name)
---

A claim with [UNVERIFIED] inline.
```

- [ ] **Step 2: Write the failing tests**

Create `science/tests/test_annotate_lift_tokens_cli.py`:

```python
"""CLI: science annotate lift-tokens (mirror + remove modes)."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner

from science_tool.annotation.cli import annotate_group
from science_tool.annotation.io import read_sidecar

FX = Path(__file__).parent / "_fixtures" / "annotation" / "audit"


@pytest.fixture
def git_workspace(tmp_path: Path) -> Path:
    doc = tmp_path / "doc"
    doc.mkdir()
    shutil.copy(FX / "mixed-tokens.md", doc / "mixed-tokens.md")
    shutil.copy(FX / "clean-after-remove.md", doc / "clean-after-remove.md")
    shutil.copy(FX / "paper.v1.md", doc / "paper.v1.md")
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t",
         "add", "."],
        cwd=tmp_path, check=True,
    )
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t",
         "commit", "-qm", "init"],
        cwd=tmp_path, check=True,
    )
    return tmp_path


def test_mirror_writes_sidecar_prose_unchanged(git_workspace: Path) -> None:
    runner = CliRunner()
    md = git_workspace / "doc" / "clean-after-remove.md"
    before = md.read_text()
    result = runner.invoke(
        annotate_group,
        ["lift-tokens", "--root", str(git_workspace), "--actor", "tester"],
    )
    assert result.exit_code == 0
    sidecar = git_workspace / "doc" / "clean-after-remove.anno.trig"
    assert sidecar.exists()
    assert md.read_text() == before


def test_remove_strips_tokens_and_writes_sidecar(git_workspace: Path) -> None:
    runner = CliRunner()
    expected_text = (FX / "clean-after-remove.expected.md").read_text()
    md = git_workspace / "doc" / "clean-after-remove.md"
    sidecar = md.with_suffix(".anno.trig")
    result = runner.invoke(
        annotate_group,
        [
            "lift-tokens", "--root", str(git_workspace),
            "--remove", "--actor", "tester",
        ],
    )
    assert result.exit_code == 0, result.output
    assert md.read_text() == expected_text
    sc = read_sidecar(sidecar)
    # Selectors should anchor to cleaned prose (no [UNVERIFIED] etc.).
    for ann in sc.annotations:
        assert "[UNVERIFIED]" not in ann.target.selector.exact
        assert "[MISSING_CITATION]" not in ann.target.selector.exact
        assert ann.lifted_from is not None


def test_remove_refuses_dirty_tree(git_workspace: Path) -> None:
    runner = CliRunner()
    md = git_workspace / "doc" / "clean-after-remove.md"
    md.write_text(md.read_text() + "\n\nExtra dirty line.\n")
    result = runner.invoke(
        annotate_group,
        [
            "lift-tokens", "--root", str(git_workspace),
            "--remove", "--actor", "tester",
        ],
    )
    assert result.exit_code == 1
    assert "dirty" in result.output.lower()


def test_remove_force_dirty_overrides(git_workspace: Path) -> None:
    runner = CliRunner()
    md = git_workspace / "doc" / "clean-after-remove.md"
    md.write_text(md.read_text() + "\n\nExtra dirty line.\n")
    result = runner.invoke(
        annotate_group,
        [
            "lift-tokens", "--root", str(git_workspace),
            "--remove", "--force-dirty", "--actor", "tester",
        ],
    )
    assert result.exit_code == 0


def test_idempotent_mirror_rerun(git_workspace: Path) -> None:
    runner = CliRunner()
    args = ["lift-tokens", "--root", str(git_workspace), "--actor", "t"]
    runner.invoke(annotate_group, args)
    sidecar = git_workspace / "doc" / "clean-after-remove.anno.trig"
    before = sidecar.read_text()
    result = runner.invoke(annotate_group, args)
    assert result.exit_code == 0
    assert sidecar.read_text() == before


def test_multi_dotted_name_sidecar_path(git_workspace: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        annotate_group,
        ["lift-tokens", "--root", str(git_workspace), "--actor", "t"],
    )
    assert result.exit_code == 0
    assert (git_workspace / "doc" / "paper.v1.anno.trig").exists()
    # The double-with_suffix bug would have created paper.anno.trig.
    assert not (git_workspace / "doc" / "paper.anno.trig").exists()


def test_recoverable_replay_after_simulated_partial_failure(
    git_workspace: Path,
) -> None:
    """If sidecar wrote OK but prose write was 'lost' (we simulate by
    restoring the .md), a re-run still produces correct steady-state."""
    runner = CliRunner()
    md = git_workspace / "doc" / "clean-after-remove.md"
    sidecar = md.with_suffix(".anno.trig")
    expected_text = (FX / "clean-after-remove.expected.md").read_text()
    original_text = md.read_text()
    # First run: writes sidecar (cleaned-prose selectors) AND prose.
    runner.invoke(annotate_group, [
        "lift-tokens", "--root", str(git_workspace),
        "--remove", "--actor", "t",
    ])
    assert sidecar.exists()
    # Simulate partial failure: restore prose to original (tokens back).
    md.write_text(original_text)
    # Re-run: dedupe skips existing rows; prose strip succeeds.
    result = runner.invoke(annotate_group, [
        "lift-tokens", "--root", str(git_workspace),
        "--remove", "--force-dirty", "--actor", "t",
    ])
    assert result.exit_code == 0
    assert md.read_text() == expected_text


def test_format_json_summary_shape(git_workspace: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(annotate_group, [
        "lift-tokens", "--root", str(git_workspace),
        "--format", "json", "--actor", "tester",
    ])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert "summary" in payload
    assert payload["summary"]["files_scanned"] >= 1
    assert "rows_written" in payload["summary"]
```

- [ ] **Step 3: Run tests to confirm they fail**

Run: `uv run pytest science/tests/test_annotate_lift_tokens_cli.py -v`
Expected: FAIL — `lift-tokens` subcommand doesn't exist.

- [ ] **Step 4: Add the `lift-tokens` subcommand**

Append to `science/src/science_tool/annotation/cli.py`:

```python
import re as _re
import subprocess
from dataclasses import replace as _replace

from science_tool.annotation.audit import merge_planned
from science_tool.annotation.io import read_sidecar, write_sidecar
from science_tool.annotation.model import Sidecar
from science_tool.annotation.sources import SOURCES
from science_tool.annotation.sources.marker_token import (
    MarkerTokenSource,
    TOKEN_TYPE_MAP,
)
from science_tool.markers import scan_text as _scan_markers_text


_TOKEN_LITERAL_PATTERN = _re.compile(
    r" *\[(?:" + "|".join(TOKEN_TYPE_MAP.keys()) + r")\] *",
)


@annotate_group.command("lift-tokens")
@click.option(
    "--root", "root_path",
    default=".",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
)
@click.option("--remove", "remove_mode", is_flag=True, default=False)
@click.option("--force-dirty", is_flag=True, default=False)
@click.option(
    "--format", "fmt",
    type=click.Choice(("table", "json")), default="table",
)
@click.option("--actor", default="science-annotate-cli")
def lift_tokens_cmd(
    root_path: Path,
    remove_mode: bool,
    force_dirty: bool,
    fmt: str,
    actor: str,
) -> None:
    """Lift inline phase-2 tokens to sidecar annotation rows."""
    root = root_path.resolve()
    md_files = _collect_lift_markdown_files(root)
    now = datetime.now(timezone.utc)
    source = MarkerTokenSource()

    summary = {
        "files_scanned": len(md_files),
        "rows_written": 0,
        "tokens_removed": 0,
        "duplicates_skipped": 0,
        "files_with_writes": 0,
    }
    file_reports: list[dict] = []

    if remove_mode:
        affected = _files_with_hits(md_files, source)
        if not force_dirty and affected:
            dirty = _dirty_files_among(root, affected)
            if dirty:
                click.echo(
                    "lift-tokens --remove refuses on dirty tree:\n  "
                    + "\n  ".join(str(p.relative_to(root)) for p in dirty),
                    err=True,
                )
                raise SystemExit(1)

    for md in md_files:
        sidecar_path = md.with_suffix(".anno.trig")
        original_text = md.read_text(encoding="utf-8")
        original_hits = list(_scan_markers_text(md, original_text, strict=False))
        non_doc_hits = [h for h in original_hits if not h.in_documentation]
        if not non_doc_hits:
            continue

        if remove_mode:
            cleaned_text = _strip_tokens_from_prose(original_text)
            plans = _replan_for_remove(
                source, md, original_text, cleaned_text, non_doc_hits,
            )
        else:
            plans = list(source.scan(md))

        sidecar = read_sidecar(sidecar_path) if sidecar_path.exists() else Sidecar()
        new_sidecar, written = merge_planned(
            sidecar, plans, actor=actor, now=now,
        )

        if remove_mode:
            # Sidecar first, then prose (per spec write-order rationale).
            if written or new_sidecar != sidecar:
                _atomic_write_text(
                    sidecar_path,
                    _serialize_sidecar(new_sidecar),
                )
            _atomic_write_text(md, cleaned_text)
            tokens_removed = len(non_doc_hits)
            summary["tokens_removed"] += tokens_removed
        else:
            if written:
                _atomic_write_text(
                    sidecar_path, _serialize_sidecar(new_sidecar),
                )

        skipped = len(plans) - len(written)
        summary["rows_written"] += len(written)
        summary["duplicates_skipped"] += skipped
        if written:
            summary["files_with_writes"] += 1

        file_reports.append({
            "path": str(md.relative_to(root)),
            "rows_written": len(written),
            "duplicates_skipped": skipped,
            **({"tokens_removed": len(non_doc_hits)} if remove_mode else {}),
        })

    if fmt == "json":
        click.echo(json.dumps({"summary": summary, "files": file_reports}, indent=2))
    else:
        click.echo(
            f"lift-tokens: {summary['rows_written']} row(s) written, "
            f"{summary['tokens_removed']} token(s) removed, "
            f"{summary['duplicates_skipped']} duplicate(s) skipped, "
            f"{summary['files_with_writes']} file(s) modified."
        )


def _collect_lift_markdown_files(root: Path) -> list[Path]:
    from science_tool.markers import _collect_markdown_files  # noqa: PLC0415
    return _collect_markdown_files(root)


def _files_with_hits(
    md_files: list[Path], source: MarkerTokenSource,
) -> list[Path]:
    out: list[Path] = []
    for md in md_files:
        text = md.read_text(encoding="utf-8")
        hits = [h for h in _scan_markers_text(md, text, strict=False)
                if not h.in_documentation]
        if hits:
            out.append(md)
    return out


def _dirty_files_among(root: Path, files: list[Path]) -> list[Path]:
    try:
        proc = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(root), capture_output=True, text=True, check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []  # not a git repo / git unavailable → no dirty check
    dirty_rel: set[str] = set()
    for line in proc.stdout.splitlines():
        if len(line) < 4:
            continue
        dirty_rel.add(line[3:].strip())
    out: list[Path] = []
    for f in files:
        rel = str(f.relative_to(root))
        if rel in dirty_rel:
            out.append(f)
    return out


def _strip_tokens_from_prose(text: str) -> str:
    from science_tool.markdown_utils import is_fence_line  # noqa: PLC0415
    out_lines: list[str] = []
    in_fence = False
    for line in text.splitlines(keepends=True):
        no_nl = line.rstrip("\n")
        if is_fence_line(no_nl):
            in_fence = not in_fence
            out_lines.append(line)
            continue
        if in_fence:
            out_lines.append(line)
            continue
        out_lines.append(_strip_tokens_outside_backticks(line))
    return "".join(out_lines)


def _strip_tokens_outside_backticks(line: str) -> str:
    parts = _re.split(r"(`[^`]*`)", line)
    for i, part in enumerate(parts):
        if part.startswith("`") and part.endswith("`"):
            continue
        parts[i] = _TOKEN_LITERAL_PATTERN.sub(" ", part)
    joined = "".join(parts)
    # Collapse the double-space introduced by removing a token from the
    # middle of a sentence; preserve leading indentation.
    leading = _re.match(r"^[ \t]*", joined).group(0)
    body = joined[len(leading):]
    body = _re.sub(r"  +", " ", body)
    return leading + body


def _replan_for_remove(
    source: MarkerTokenSource,
    md: Path,
    original_text: str,
    cleaned_text: str,
    original_hits,
) -> list:
    """Build planned rows whose selectors anchor to cleaned_text but whose
    `match_text`/`lifted_from` retain the original bracketed token."""
    plans: list = []
    cleaned_sentences = _split_sentences_with_offsets(cleaned_text)
    original_sentences = _split_sentences_with_offsets(original_text)
    for hit in original_hits:
        # Find the sentence index in original_text that covers hit.line.
        ordinal = _sentence_ordinal_for_line(original_text, original_sentences, hit.line)
        if ordinal is None or ordinal >= len(cleaned_sentences):
            continue
        sent_start, sent_end = cleaned_sentences[ordinal]
        sentence = cleaned_text[sent_start:sent_end]
        from science_tool.annotation.model import (  # noqa: PLC0415
            Motivation, SpecificResource, TextQuoteSelector, TextualBody,
        )
        from science_tool.annotation.sources.base import (  # noqa: PLC0415
            PlannedAnnotation,
        )
        atype, body_msg = TOKEN_TYPE_MAP[hit.token]
        literal = f"[{hit.token}]"
        sel = TextQuoteSelector(
            exact=sentence,
            prefix=cleaned_text[max(0, sent_start - 60):sent_start],
            suffix=cleaned_text[sent_end:min(len(cleaned_text), sent_end + 60)],
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


_SENTENCE_SPLIT_RE = _re.compile(r"(?<=[.!?])\s+")


def _split_sentences_with_offsets(text: str) -> list[tuple[int, int]]:
    """Return (start, end) char ranges of each sentence."""
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


def _sentence_ordinal_for_line(
    text: str, sentences: list[tuple[int, int]], line: int,
) -> int | None:
    offsets = [0]
    for i, ch in enumerate(text):
        if ch == "\n":
            offsets.append(i + 1)
    if line < 1 or line > len(offsets):
        return None
    line_start = offsets[line - 1]
    for idx, (start, end) in enumerate(sentences):
        if start <= line_start < end or (
            start <= line_start and end > line_start
        ):
            return idx
        # Allow the line to lie within a multi-line sentence.
        if line - 1 < len(offsets) - 1:
            line_end = offsets[line]
            if start < line_end and end > line_start:
                return idx
    # Fall back: nearest preceding sentence.
    for idx in range(len(sentences) - 1, -1, -1):
        if sentences[idx][0] <= line_start:
            return idx
    return None


def _atomic_write_text(path: Path, text: str) -> None:
    import os, tempfile  # noqa: PLC0415
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


def _serialize_sidecar(sidecar: Sidecar) -> str:
    """Serialize a Sidecar to a string via write_sidecar's emission logic."""
    import io, tempfile, os  # noqa: PLC0415
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

- [ ] **Step 5: Run tests to confirm they pass**

Run: `uv run pytest science/tests/test_annotate_lift_tokens_cli.py -v`
Expected: PASS.

- [ ] **Step 6: Sanity check — `--help` listing**

Run: `uv run --project science science annotate lift-tokens --help`
Expected: shows `--root`, `--remove`, `--force-dirty`, `--format`,
`--actor`.

- [ ] **Step 7: Commit**

```bash
git add science/src/science_tool/annotation/cli.py \
        science/tests/test_annotate_lift_tokens_cli.py \
        science/tests/_fixtures/annotation/audit/clean-after-remove.md \
        science/tests/_fixtures/annotation/audit/clean-after-remove.expected.md \
        science/tests/_fixtures/annotation/audit/paper.v1.md
git commit -m "feat(annotate): add 'lift-tokens' subcommand (mirror + remove)"
```

---

### Task 10: `science markers scan --ignore-lifted`

**Files:**
- Modify: `science/src/science_tool/markers_cli.py`
- Test: `science/tests/test_markers_scan_ignore_lifted.py`

- [ ] **Step 1: Write the failing tests**

Create `science/tests/test_markers_scan_ignore_lifted.py`:

```python
"""markers scan --ignore-lifted post-filter behavior."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from click.testing import CliRunner

from science_tool.annotation.cli import annotate_group
from science_tool.markers_cli import markers_group

FX = Path(__file__).parent / "_fixtures" / "annotation" / "audit"


@pytest.fixture
def workspace_with_lifted(tmp_path: Path) -> Path:
    doc = tmp_path / "doc"
    doc.mkdir()
    shutil.copy(FX / "mixed-tokens.md", doc / "mixed-tokens.md")
    runner = CliRunner()
    runner.invoke(annotate_group, [
        "lift-tokens", "--root", str(tmp_path), "--actor", "tester",
    ])
    return tmp_path


def test_ignore_lifted_skips_lifted_hits(workspace_with_lifted: Path) -> None:
    runner = CliRunner()
    plain = runner.invoke(markers_group, [
        "scan", "--root", str(workspace_with_lifted), "--format", "json",
    ])
    filtered = runner.invoke(markers_group, [
        "scan", "--root", str(workspace_with_lifted),
        "--ignore-lifted", "--format", "json",
    ])
    plain_payload = json.loads(plain.output)
    filtered_payload = json.loads(filtered.output)
    assert sum(plain_payload["counts"].values()) > 0
    assert filtered_payload["counts"] == {}


def test_no_sidecar_means_no_skip(tmp_path: Path) -> None:
    doc = tmp_path / "doc"
    doc.mkdir()
    shutil.copy(FX / "mixed-tokens.md", doc / "mixed-tokens.md")
    runner = CliRunner()
    plain = runner.invoke(markers_group, [
        "scan", "--root", str(tmp_path), "--format", "json",
    ])
    filtered = runner.invoke(markers_group, [
        "scan", "--root", str(tmp_path),
        "--ignore-lifted", "--format", "json",
    ])
    assert plain.output == filtered.output


def test_ignore_lifted_preserves_unrelated_hits(tmp_path: Path) -> None:
    """A row with non-matching lifted_from in sidecar does not skip the hit."""
    doc = tmp_path / "doc"
    doc.mkdir()
    md = doc / "mixed-tokens.md"
    shutil.copy(FX / "mixed-tokens.md", md)
    sidecar = doc / "mixed-tokens.anno.trig"
    sidecar.write_text(
        '@prefix oa: <http://www.w3.org/ns/oa#> .\n'
        '@prefix sci: <http://example.org/science/vocab/> .\n'
        '@prefix anno: <#> .\n'
        '@prefix dc:  <http://purl.org/dc/terms/> .\n'
        '@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .\n'
        'anno:annotations {\n'
        '  anno:a-other a oa:Annotation ;\n'
        '    oa:hasTarget [ oa:hasSource <mixed-tokens.md> ; '
        'oa:hasSelector [ a oa:TextQuoteSelector ; '
        'oa:exact "irrelevant" ; oa:prefix "" ; oa:suffix "" ] ] ;\n'
        '    oa:hasBody [ a oa:TextualBody ; dc:format "text/plain" ; '
        '<http://www.w3.org/1999/02/22-rdf-syntax-ns#value> "x" ] ;\n'
        '    oa:motivatedBy oa:commenting ;\n'
        '    sci:annotationType "comment" ;\n'
        '    sci:source "human:keith" ;\n'
        '    sci:status "open" ;\n'
        '    sci:liftedFrom "[NEVER]" ;\n'
        '    sci:matchText "[NEVER]" ;\n'
        '    dc:creator "k" ;\n'
        '    dc:created "2026-05-11T00:00:00+00:00"^^xsd:dateTime .\n'
        '}\n',
        encoding="utf-8",
    )
    runner = CliRunner()
    filtered = runner.invoke(markers_group, [
        "scan", "--root", str(tmp_path),
        "--ignore-lifted", "--format", "json",
    ])
    payload = json.loads(filtered.output)
    assert sum(payload["counts"].values()) > 0
```

- [ ] **Step 2: Run tests to confirm they fail**

Run: `uv run pytest science/tests/test_markers_scan_ignore_lifted.py -v`
Expected: FAIL — `--ignore-lifted` flag not present.

- [ ] **Step 3: Add the flag + filter**

Edit `science/src/science_tool/markers_cli.py`. Add the option to
the `scan` command and post-filter the hits before rendering:

```python
@markers_group.command("scan")
@click.option(
    "--root",
    "root_path",
    default=".",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(("table", "json")),
    default="table",
    show_default=True,
)
@click.option(
    "--strict",
    is_flag=True,
    help="Promote INFO-severity tokens (SPECULATION, INACCESSIBLE) to WARN.",
)
@click.option(
    "--include-documentation",
    is_flag=True,
    help="Include backticked / fenced-code occurrences (audit / migration).",
)
@click.option(
    "--ignore-lifted",
    is_flag=True,
    help="Skip hits already represented in a sibling .anno.trig sidecar.",
)
def scan(
    root_path: Path,
    output_format: str,
    strict: bool,
    include_documentation: bool,
    ignore_lifted: bool,
) -> None:
    """Scan project markdown for annotation tokens."""
    root = root_path.resolve()
    hits = scan_markers(root, strict=strict, include_documentation=include_documentation)
    if ignore_lifted:
        hits = _filter_lifted(hits)
    counts = Counter(h.token for h in hits)

    # ... rest unchanged ...
```

Add the helper at the bottom of the file:

```python
def _filter_lifted(hits: list) -> list:
    """Drop hits whose enclosing sentence has a sidecar row marker-lifted."""
    from science_tool.annotation.io import read_sidecar  # noqa: PLC0415
    from science_tool.annotation.selector import (  # noqa: PLC0415
        ResolutionStatus, resolve_selector,
    )

    sidecar_cache: dict[Path, "object"] = {}

    def load(p: Path):
        if p in sidecar_cache:
            return sidecar_cache[p]
        try:
            sc = read_sidecar(p) if p.exists() else None
        except Exception as exc:
            click.echo(
                f"warning: could not parse {p}: {exc}", err=True,
            )
            sc = None
        sidecar_cache[p] = sc
        return sc

    out = []
    for hit in hits:
        sidecar_path = hit.file.with_suffix(".anno.trig")
        sc = load(sidecar_path)
        if sc is None:
            out.append(hit)
            continue
        if not _hit_is_lifted(hit, sc):
            out.append(hit)
    return out


def _hit_is_lifted(hit, sidecar) -> bool:
    """True if any sidecar annotation matches this hit by source + token + line."""
    from science_tool.annotation.selector import (  # noqa: PLC0415
        ResolutionStatus, resolve_selector,
    )

    literal = f"[{hit.token}]"
    try:
        source_text = hit.file.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False

    line_offsets = [0]
    for i, ch in enumerate(source_text):
        if ch == "\n":
            line_offsets.append(i + 1)
    if hit.line < 1 or hit.line > len(line_offsets):
        return False
    line_start = line_offsets[hit.line - 1]
    line_end = line_offsets[hit.line] if hit.line < len(line_offsets) else len(source_text)

    for ann in sidecar.annotations:
        if ann.source != "marker-scanner:phase-2":
            continue
        if ann.lifted_from != literal:
            continue
        result = resolve_selector(source_text, ann.target.selector)
        if result.status == ResolutionStatus.SUPERSEDED:
            continue
        if result.start is None or result.end is None:
            continue
        # Containment: any character of the resolved range lies on hit.line.
        if result.start < line_end and result.end > line_start:
            return True
    return False
```

- [ ] **Step 4: Run tests to confirm they pass**

Run: `uv run pytest science/tests/test_markers_scan_ignore_lifted.py -v`
Expected: PASS.

- [ ] **Step 5: Sanity check — `--help` listing**

Run: `uv run --project science science markers scan --help`
Expected: shows `--ignore-lifted` flag.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/markers_cli.py \
        science/tests/test_markers_scan_ignore_lifted.py
git commit -m "feat(markers): add --ignore-lifted post-filter for sidecar dedupe"
```

---

### Task 11: `validate.sh` Section 8 + managed-artifact bump

**Files:**
- Modify: `science/src/science_tool/project_artifacts/data/validate.sh`
- Modify: `science/src/science_tool/project_artifacts/registry.yaml`
- Test: `science/tests/test_validate_sh_section_8.py`

- [ ] **Step 1: Write the failing test**

Create `science/tests/test_validate_sh_section_8.py`:

```python
"""validate.sh Section 8 + managed-artifact registry bump."""

from __future__ import annotations

import hashlib
import re
import subprocess
import tempfile
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATE_SH = REPO_ROOT / "src/science_tool/project_artifacts/data/validate.sh"
REGISTRY_YAML = REPO_ROOT / "src/science_tool/project_artifacts/registry.yaml"


def _body_hash(path: Path) -> str:
    """Match the registry's body_hash semantics: skip 4-line header."""
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    body = "".join(lines[4:])
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def test_section_8_passes_ignore_lifted() -> None:
    text = VALIDATE_SH.read_text(encoding="utf-8")
    section_idx = text.find("8. Unresolved annotation markers")
    assert section_idx >= 0
    section_end = text.find("# ─── 9.", section_idx)
    section = text[section_idx:section_end]
    assert "--ignore-lifted" in section


def test_registry_version_bumped() -> None:
    data = yaml.safe_load(REGISTRY_YAML.read_text(encoding="utf-8"))
    validate = data["managed_artifacts"]["validate.sh"]
    assert validate["version"] == "2026.05.11.2"


def test_registry_current_hash_matches_validate_body() -> None:
    data = yaml.safe_load(REGISTRY_YAML.read_text(encoding="utf-8"))
    validate = data["managed_artifacts"]["validate.sh"]
    assert validate["current_hash"] == _body_hash(VALIDATE_SH)


def test_registry_previous_hashes_grow() -> None:
    data = yaml.safe_load(REGISTRY_YAML.read_text(encoding="utf-8"))
    validate = data["managed_artifacts"]["validate.sh"]
    prev = validate["previous_hashes"]
    # The pre-P3.2 body_hash is preserved at the head of previous_hashes.
    assert (
        "171dada621d6741d0deb7d592ec6ac92f4ceb10d39941d6dc06e8d898824cf23"
        in prev
    )


def test_registry_migration_entry_for_2026_05_11_2() -> None:
    data = yaml.safe_load(REGISTRY_YAML.read_text(encoding="utf-8"))
    validate = data["managed_artifacts"]["validate.sh"]
    migrations = validate["migrations"]
    assert any(
        m.get("from_version") == "2026.05.11.1"
        and m.get("to_version") == "2026.05.11.2"
        for m in migrations
    )


def test_section_8_runs_against_empty_dir() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        result = subprocess.run(
            ["bash", str(VALIDATE_SH)],
            cwd=tmp, capture_output=True, text=True, check=False,
        )
        assert result.returncode in (0, 1)
        assert "annotation markers" in result.stdout.lower()
```

- [ ] **Step 2: Run tests to confirm they fail**

Run: `uv run pytest science/tests/test_validate_sh_section_8.py -v`
Expected: FAIL — `--ignore-lifted` absent, version still
`2026.05.11.1`.

- [ ] **Step 3: Update Section 8 to pass `--ignore-lifted`**

Edit `science/src/science_tool/project_artifacts/data/validate.sh`.
Locate Section 8 (look for `# ─── 8. Unresolved annotation markers`).
Replace the `SCIENCE_MARKERS_FLAGS=()` initializer block with one
that pre-populates the new flag:

```bash
# ─── 8. Unresolved annotation markers ──────────────────────────────
echo ""
echo "Checking for unresolved markers..."

if command -v science >/dev/null 2>&1 && [ -d "$DOC_DIR" ]; then
    SCIENCE_MARKERS_FLAGS=(--ignore-lifted)
    if [ "$STRICT" -eq 1 ]; then
        SCIENCE_MARKERS_FLAGS+=("--strict")
    fi
    markers_json=$(science markers scan --root . --format json "${SCIENCE_MARKERS_FLAGS[@]}" 2>/dev/null) || true
    if [ -z "$markers_json" ]; then
        markers_json='{"counts":{},"hits":[]}'
    fi
    while IFS=$'\t' read -r token count severity; do
        [ -z "$token" ] && continue
        if [ "$severity" = "warn" ] && [ "$count" -gt 0 ]; then
            warn "${count} [${token}] marker(s) found in documents"
        fi
    done < <(printf '%s' "$markers_json" | python3 -c '
import json, sys
data = json.load(sys.stdin)
sev = {}
for h in data["hits"]:
    sev.setdefault(h["token"], h["severity"])
for token, count in sorted(data["counts"].items()):
    print(f"{token}\t{count}\t{sev.get(token, \"warn\")}")
')
fi
```

- [ ] **Step 4: Bump the managed-artifact registry**

Edit `science/src/science_tool/project_artifacts/registry.yaml`.
Compute the new body_hash:

```bash
python3 -c "
from pathlib import Path
import hashlib
p = Path('science/src/science_tool/project_artifacts/data/validate.sh')
lines = p.read_text(encoding='utf-8').splitlines(keepends=True)
print(hashlib.sha256(''.join(lines[4:]).encode('utf-8')).hexdigest())
"
```

Update the `managed_artifacts.validate.sh` block. Replace the
existing `version`, `current_hash`, and prepend the old hash to
`previous_hashes`. Append a new migration entry and changelog entry.

Locate the block (search for `validate.sh:` near the top of
`managed_artifacts:`) and update it as follows (substitute the
computed hash for `<NEW_BODY_HASH>`):

```yaml
managed_artifacts:
  validate.sh:
    version: '2026.05.11.2'
    current_hash: '<NEW_BODY_HASH>'
    previous_hashes:
      - '171dada621d6741d0deb7d592ec6ac92f4ceb10d39941d6dc06e8d898824cf23'
      # ... existing entries follow unchanged ...
    migrations:
      - from_version: '2026.05.11.1'
        to_version: '2026.05.11.2'
        description: |
          Section 8 markers scan now passes --ignore-lifted to dedupe
          inline tokens against lifted sidecar rows.
      # ... existing migrations follow unchanged ...
    changelog:
      - version: '2026.05.11.2'
        date: '2026-05-11'
        notes: |
          Section 8 markers scan now passes --ignore-lifted to dedupe
          inline tokens against lifted sidecar rows (P3.2).
      # ... existing changelog entries follow unchanged ...
```

- [ ] **Step 5: Update the header inside `validate.sh`**

The `validate.sh` file's first 4 lines carry the
`science-managed-version` and `science-managed-source-sha256`
markers. Update them to match the new `version` and `current_hash`
values from the registry.

Read the first 4 lines:

```bash
head -n 4 science/src/science_tool/project_artifacts/data/validate.sh
```

Update the version and SHA256 lines to match the registry.

- [ ] **Step 6: Run tests to confirm they pass**

Run: `uv run pytest science/tests/test_validate_sh_section_8.py -v`
Expected: PASS.

- [ ] **Step 7: Confirm `science init` still passes its acceptance test**

Run: `uv run pytest science/tests/ -k "managed_artifact or registry" -v`
Expected: green.

- [ ] **Step 8: Commit**

```bash
git add science/src/science_tool/project_artifacts/data/validate.sh \
        science/src/science_tool/project_artifacts/registry.yaml \
        science/tests/test_validate_sh_section_8.py
git commit -m "feat(validate): Section 8 passes --ignore-lifted (managed bump → 2026.05.11.2)"
```

---

### Task 12: End-to-end smoke verification

**Files:** none modified; pure verification on merged branch.

This task lives at the end of the plan; a subagent executing it
should run on the merged-to-main state and report findings without
making code changes. If something fails, file follow-up tasks
rather than patching in this task.

- [ ] **Step 1: Full test suite**

```bash
uv run pytest -q
```
Expected: green; total count rises by ~66 over the pre-P3.2 baseline.

- [ ] **Step 2: `science annotate audit --help`**

```bash
uv run --project science science annotate audit --help
```
Expected: shows `--root`, `--source` (multiple), `--no-llm`,
`--dry-run`, `--format`, `--actor`.

- [ ] **Step 3: `science annotate lift-tokens --help`**

```bash
uv run --project science science annotate lift-tokens --help
```
Expected: shows `--root`, `--remove`, `--force-dirty`, `--format`,
`--actor`.

- [ ] **Step 4: End-to-end audit on a fixture**

```bash
cp -r science/tests/_fixtures/annotation/audit /tmp/p32-smoke
cd /tmp/p32-smoke
uv run --project /mnt/ssd/Dropbox/science/science science annotate audit \
    --root . --format json --actor smoke
```
Expected: `summary.rows_written > 0`, multiple `lint:*` source-versions
in `summary.sources_run`, sidecars created next to fixtures.

- [ ] **Step 5: Re-run audit**

```bash
uv run --project /mnt/ssd/Dropbox/science/science science annotate audit \
    --root . --format json --actor smoke
```
Expected: `summary.rows_written == 0`,
`summary.duplicates_skipped == previous_total`.

- [ ] **Step 6: Lift-tokens mirror**

```bash
rm -rf /tmp/p32-smoke && cp -r science/tests/_fixtures/annotation/audit /tmp/p32-smoke
cd /tmp/p32-smoke && git init -q && git add . \
    && git -c user.name=t -c user.email=t@t commit -qm init
uv run --project /mnt/ssd/Dropbox/science/science science annotate lift-tokens \
    --root . --format json --actor smoke
```
Expected: sidecars written; mixed-tokens.md unchanged on disk.

- [ ] **Step 7: Lift-tokens remove**

```bash
uv run --project /mnt/ssd/Dropbox/science/science science annotate lift-tokens \
    --root . --remove --format json --actor smoke
```
Expected: tokens stripped from prose; sidecars updated;
`science annotate verify --root .` reports zero broken/degraded.

- [ ] **Step 8: markers scan dedupe**

```bash
uv run --project /mnt/ssd/Dropbox/science/science science markers scan \
    --root . --format json
uv run --project /mnt/ssd/Dropbox/science/science science markers scan \
    --root . --ignore-lifted --format json
```
Expected: plain reports zero (tokens were stripped); `--ignore-lifted`
also zero. To exercise the post-filter on a non-removed tree, repeat
the smoke from step 6 and compare the two outputs there: plain >
`--ignore-lifted == 0`.

- [ ] **Step 9: validate.sh Section 8**

```bash
mkdir -p /tmp/p32-validate-smoke && cd /tmp/p32-validate-smoke
bash /mnt/ssd/Dropbox/science/science/src/science_tool/project_artifacts/data/validate.sh
```
Expected: exit 0 or 1; output includes a section-8 block; no
`unbound variable` or shell errors.

- [ ] **Step 10: Report**

Report back with:
- Total test count and pass/fail tally.
- Output snippets from steps 4 and 5 (showing the audit summary).
- Confirmation that mixed-tokens.md was unchanged after step 6.
- Confirmation that mixed-tokens.md had tokens stripped after step 7.
- Any unexpected stderr from any step.

No commit in this task; verification is pass-only.

---

## Spec coverage check

| Spec section | Covered by |
|---|---|
| §Persisting `match_text` | Task 1 |
| §LintIssue.match contract | Task 2 |
| §sources/base.py | Task 3 |
| §sources/marker_token.py | Task 4 |
| §sources/lint.py | Task 5 |
| §SOURCES + LINT_SOURCES registry | Task 6 |
| §audit.py (mint_id, merge_planned, audit_file) | Task 7 |
| §audit CLI semantics | Task 8 |
| §lift-tokens CLI semantics (mirror + remove) | Task 9 |
| §`--ignore-lifted` flag | Task 10 |
| §validate.sh Section 8 + registry bump | Task 11 |
| §Acceptance criteria | Task 12 |

No spec section is unaddressed.

---

## Out-of-scope reminders (do NOT implement here)

These are deferred per spec §Non-goals and §Out of scope reminders.
A subagent that finds itself adding any of the following should
stop and escalate:

- `science prose lint` refactor or deprecation banner
- `--since <git-ref>` for `audit`
- Bib-IRI body promotion (`bare-author-year` → `cites`)
- `science annotate ack / dismiss / fix / list / render`
- AuditLedger writes (the model field exists; do not write to it)
- `frontmatter-inline-gap` source adapter

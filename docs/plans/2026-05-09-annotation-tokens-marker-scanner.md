# Annotation Tokens — Phase 2 Marker Scanner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the overloaded `[UNVERIFIED]` / `[NEEDS CITATION]` marker convention with a four-token vocabulary (`[UNVERIFIED]`, `[MISSING_CITATION]`, `[SPECULATION]`, `[INACCESSIBLE]`) backed by a single Python scanner used by both `science refs check` and `validate.sh`.

**Architecture:**
- New `science_tool/markers.py` module owns token definitions, severity table, and the `scan_markers()` API. Single source of truth.
- New `science_tool/markdown_utils.py` factors out fenced-block + inline-code stripping currently inline in `refs.py`, so both modules share one implementation.
- `refs.py` and `refs_cli.py` delegate marker work to `markers.py`. `RefIssue` gains a `severity` field.
- New `science markers` Click group with `scan` (machine output for validate.sh) and `migrate` (heuristic legacy-token rewriter) subcommands.
- `validate.sh` (managed artifact) replaces its bash grep with `science markers scan --format json`. Version + body sha256 + registry.yaml `current_hash` all bumped together.
- Legacy `[NEEDS CITATION]` recognized as alias of `[MISSING_CITATION]` and tagged `legacy: true` in JSON output for the deprecation window.

**Scope decision:** This plan covers deliverables 1, 2, 3, 4, 6, 7 from the phase-2 stub (`docs/plans/2026-05-09-annotation-system-stub.md`). Deliverable 5 (frontmatter `doi:`/`pmid:` mutual-optional + `science paper sync`) is independent and gets a sibling plan.

**Open policy decision baked in:** `[SPECULATION]` default severity = INFO (counted, not WARN'd). `--strict` promotes to WARN. Per user decision 2026-05-09.

**Tech Stack:** Python 3.11+, Click, pytest, ruff. `uv run` for invocations. Existing `science` package layout under `science/src/science_tool/`.

---

## File Structure

**Create:**
- `science/src/science_tool/markers.py` — token vocabulary, `MarkerHit` dataclass, `scan_markers()` API, severity logic.
- `science/src/science_tool/markdown_utils.py` — shared `strip_inline_code()`, `is_fence_line()`, `frontmatter_line_numbers()` helpers extracted from `refs.py`.
- `science/src/science_tool/markers_cli.py` — `science markers` Click group with `scan` and `migrate` subcommands.
- `science/tests/test_markers.py` — unit tests for `scan_markers()`.
- `science/tests/test_markers_cli.py` — Click runner tests for `scan` and `migrate`.
- `science/tests/test_markdown_utils.py` — unit tests for shared helpers.
- `docs/conventions/annotation-tokens.md` — convention doc with severity table, lexical-scope rule, migration guidance.

**Modify:**
- `science/src/science_tool/refs.py` — remove `_UNVERIFIED_RE`, `_NEEDS_CITATION_RE`, the inline marker emitter at lines 564–583, and the local helpers `_is_fence_line` / `_strip_inline_code` / `_frontmatter_line_numbers` (replaced by `markdown_utils.py`). `RefIssue` gains `severity: str = "warn"` field. `check_refs()` calls `scan_markers()` and converts `MarkerHit`s into `RefIssue` rows.
- `science/src/science_tool/refs_cli.py` — replace the hardcoded two-token rendering in `_render_marker_summary` (lines 55–70) with token-agnostic per-token aggregation. `--strict` semantics widened to promote INFO markers to WARN.
- `science/src/science_tool/cli.py` — register `markers_group` from `markers_cli.py`.
- `science/src/science_tool/project_artifacts/data/validate.sh` — replace section 8 (lines 506–529) with a call to `science markers scan --format json` and per-token counter rendering. Bump `science-managed-version` and recompute `science-managed-source-sha256`.
- `science/src/science_tool/project_artifacts/registry.yaml` — bump `current_hash` for `validate.sh`, append previous hash to `previous_hashes`, bump `version`.
- `science/tests/test_refs.py` — update `test_unverified_markers_tracked` and downstream tests for the new severity-aware shape; add tests covering the new tokens flowing through `check_refs`.
- `commands/research-papers.md` — replace bare `[UNVERIFIED]` guidance with token-selection guidance per access status.
- `skills/writing/SKILL.md` — add a section on token selection.
- `templates/paper.md` and `science/model/src/science_model/templates/paper.md` — no source-line preamble exists today; if a future preamble is added it must use backticks. (No edit in this plan; called out in `docs/conventions/annotation-tokens.md`.)

---

## Tokens, severities, and aliases (single source of truth)

These constants must appear exactly once, in `markers.py`. Every later task references this table:

| Canonical token       | Default severity | Legacy alias                          |
|-----------------------|------------------|---------------------------------------|
| `[UNVERIFIED]`        | `warn`           | (none — same spelling pre/post)       |
| `[MISSING_CITATION]`  | `warn`           | `[NEEDS CITATION]` → `MISSING_CITATION` |
| `[SPECULATION]`       | `info`           | (none)                                |
| `[INACCESSIBLE]`      | `info`           | (none)                                |

`--strict` promotes `info` → `warn` uniformly across both `science refs check` and `science markers scan` (and through `validate.sh` which forwards the flag). `--strict` is the **same** flag already documented in `validate.sh:44–46` (semantics widened).

---

## Task 1: Extract markdown helpers into `markdown_utils.py`

**Files:**
- Create: `science/src/science_tool/markdown_utils.py`
- Create: `science/tests/test_markdown_utils.py`
- Modify: `science/src/science_tool/refs.py` (remove the local helpers and import from new module)

- [ ] **Step 1: Write the failing tests**

`science/tests/test_markdown_utils.py`:
```python
"""Shared markdown lexical helpers."""
from pathlib import Path

from science_tool.markdown_utils import (
    frontmatter_line_numbers,
    is_fence_line,
    strip_inline_code,
)


def test_strip_inline_code_removes_backticked_spans() -> None:
    assert strip_inline_code("plain `code` rest") == "plain  rest"


def test_strip_inline_code_leaves_bare_text() -> None:
    assert strip_inline_code("no code here") == "no code here"


def test_strip_inline_code_handles_multiple_spans() -> None:
    assert strip_inline_code("a `b` c `d` e") == "a  c  e"


def test_is_fence_line_triple_backtick() -> None:
    assert is_fence_line("```")
    assert is_fence_line("```python")
    assert is_fence_line("    ```")


def test_is_fence_line_tilde_fence() -> None:
    assert is_fence_line("~~~")


def test_is_fence_line_rejects_inline_backtick() -> None:
    assert not is_fence_line("plain `inline` text")


def test_frontmatter_line_numbers_basic(tmp_path: Path) -> None:
    p = tmp_path / "doc.md"
    p.write_text("---\ntitle: foo\n---\n\nbody line\n")
    assert frontmatter_line_numbers(p) == {1, 2, 3}


def test_frontmatter_line_numbers_no_frontmatter(tmp_path: Path) -> None:
    p = tmp_path / "doc.md"
    p.write_text("# heading\nbody\n")
    assert frontmatter_line_numbers(p) == set()


def test_frontmatter_line_numbers_unterminated(tmp_path: Path) -> None:
    p = tmp_path / "doc.md"
    p.write_text("---\ntitle: foo\nno closing fence\n")
    assert frontmatter_line_numbers(p) == set()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd science && uv run pytest tests/test_markdown_utils.py -q
```
Expected: `ModuleNotFoundError: No module named 'science_tool.markdown_utils'`

- [ ] **Step 3: Create the module**

`science/src/science_tool/markdown_utils.py`:
```python
"""Shared markdown lexical helpers used by refs.py and markers.py.

Centralizes fenced-block detection, inline-code stripping, and frontmatter
line accounting so the two scanners agree on what counts as "in prose"
versus "in code/documentation".
"""

from __future__ import annotations

import re
from pathlib import Path

_FENCE_RE = re.compile(r"^\s*(```|~~~)")
_INLINE_CODE_RE = re.compile(r"`[^`]*`")


def is_fence_line(line: str) -> bool:
    """Return True if the line opens or closes a fenced code block."""
    return _FENCE_RE.match(line) is not None


def strip_inline_code(line: str) -> str:
    """Remove backticked inline-code spans from a line.

    Used to exclude tokens-as-documentation (e.g., `[UNVERIFIED]` discussed
    in prose about the convention itself) from prose-level scanning.
    """
    return _INLINE_CODE_RE.sub("", line)


def frontmatter_line_numbers(path: Path) -> set[int]:
    """Return the 1-based line numbers occupied by the YAML frontmatter block.

    Returns an empty set when the file has no frontmatter or the block is
    unterminated. Callers use this to skip frontmatter during prose scans.
    """
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return set()
    if not lines or lines[0].strip() != "---":
        return set()
    for index, line in enumerate(lines[1:], start=2):
        if line.strip() == "---":
            return set(range(1, index + 1))
    return set()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd science && uv run pytest tests/test_markdown_utils.py -q
```
Expected: 8 passed.

- [ ] **Step 5: Refactor `refs.py` to use the shared helpers**

In `science/src/science_tool/refs.py`:

Replace the imports block (around line 8–18) so it adds:
```python
from science_tool.markdown_utils import (
    frontmatter_line_numbers as _frontmatter_line_numbers,
    is_fence_line as _is_fence_line,
    strip_inline_code as _strip_inline_code,
)
```

Delete the existing local definitions:
- The constants `_FENCE_RE` and `_INLINE_CODE_RE` (lines 39–40).
- The function `_frontmatter_line_numbers` (lines 203–213).
- The function `_is_fence_line` (lines 285–286).
- The function `_strip_inline_code` (lines 289–290).

The call sites (`_is_fence_line(line)`, `_strip_inline_code(line)`, `_frontmatter_line_numbers(file_path)`) keep their existing names because the imports alias the new helpers under those exact names.

- [ ] **Step 6: Run the full refs test suite to verify no regressions**

```bash
cd science && uv run pytest tests/test_refs.py tests/test_markdown_utils.py -q
```
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add science/src/science_tool/markdown_utils.py science/tests/test_markdown_utils.py science/src/science_tool/refs.py
git commit -m "refactor(refs): extract markdown lexical helpers into markdown_utils"
```

---

## Task 2: Token vocabulary and severity table in `markers.py`

**Files:**
- Create: `science/src/science_tool/markers.py`
- Create: `science/tests/test_markers.py` (first portion — vocabulary tests only)

- [ ] **Step 1: Write the failing tests**

`science/tests/test_markers.py`:
```python
"""Unit tests for science_tool.markers."""
from pathlib import Path

import pytest

from science_tool.markers import (
    DEFAULT_SEVERITY,
    LEGACY_ALIASES,
    TOKENS,
    MarkerHit,
    severity_for,
)


def test_tokens_are_the_four_canonical_names() -> None:
    assert TOKENS == ("UNVERIFIED", "MISSING_CITATION", "SPECULATION", "INACCESSIBLE")


def test_default_severity_table() -> None:
    assert DEFAULT_SEVERITY == {
        "UNVERIFIED": "warn",
        "MISSING_CITATION": "warn",
        "SPECULATION": "info",
        "INACCESSIBLE": "info",
    }


def test_legacy_alias_maps_needs_citation_to_missing_citation() -> None:
    assert LEGACY_ALIASES == {"NEEDS CITATION": "MISSING_CITATION"}


def test_severity_for_warn_token_default() -> None:
    assert severity_for("UNVERIFIED", strict=False) == "warn"
    assert severity_for("MISSING_CITATION", strict=False) == "warn"


def test_severity_for_info_token_default() -> None:
    assert severity_for("SPECULATION", strict=False) == "info"
    assert severity_for("INACCESSIBLE", strict=False) == "info"


def test_severity_for_strict_promotes_info_to_warn() -> None:
    assert severity_for("SPECULATION", strict=True) == "warn"
    assert severity_for("INACCESSIBLE", strict=True) == "warn"


def test_severity_for_strict_keeps_warn_as_warn() -> None:
    assert severity_for("UNVERIFIED", strict=True) == "warn"


def test_marker_hit_is_frozen_dataclass() -> None:
    hit = MarkerHit(
        file=Path("doc/x.md"),
        line=10,
        token="UNVERIFIED",
        severity="warn",
        in_documentation=False,
        legacy=False,
    )
    with pytest.raises(Exception):
        hit.line = 11  # type: ignore[misc]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd science && uv run pytest tests/test_markers.py -q
```
Expected: `ModuleNotFoundError: No module named 'science_tool.markers'`

- [ ] **Step 3: Create the module skeleton**

`science/src/science_tool/markers.py`:
```python
"""Annotation-token scanner — single source of truth for marker scanning.

Used by both `science refs check` and `validate.sh` (via
`science markers scan --format json`). See
`docs/conventions/annotation-tokens.md` for the vocabulary and severity rules.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# Canonical token names, ordered for stable display.
TOKENS: tuple[str, ...] = ("UNVERIFIED", "MISSING_CITATION", "SPECULATION", "INACCESSIBLE")

# Default severity per token. `--strict` promotes any "info" entry to "warn".
DEFAULT_SEVERITY: dict[str, str] = {
    "UNVERIFIED": "warn",
    "MISSING_CITATION": "warn",
    "SPECULATION": "info",
    "INACCESSIBLE": "info",
}

# Legacy spellings recognized during the deprecation window. Maps the *literal
# inner text* (without brackets) to the canonical token name.
LEGACY_ALIASES: dict[str, str] = {"NEEDS CITATION": "MISSING_CITATION"}


@dataclass(frozen=True)
class MarkerHit:
    """One marker occurrence found by the scanner."""

    file: Path
    line: int
    token: str  # one of TOKENS
    severity: str  # "warn" | "info"
    in_documentation: bool  # True if backticked or inside a fenced code block
    legacy: bool  # True if the source spelling was a legacy alias


def severity_for(token: str, *, strict: bool) -> str:
    """Resolve effective severity for a canonical token under the strict flag."""
    base = DEFAULT_SEVERITY[token]
    if strict and base == "info":
        return "warn"
    return base
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd science && uv run pytest tests/test_markers.py -q
```
Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/markers.py science/tests/test_markers.py
git commit -m "feat(markers): add token vocabulary and severity table"
```

---

## Task 3: Implement `scan_markers()` over a single file's text

**Files:**
- Modify: `science/src/science_tool/markers.py`
- Modify: `science/tests/test_markers.py`

This task adds the in-memory scanner that classifies each marker as in-prose vs in-documentation (backticked or fenced). File-walking lives in Task 4.

- [ ] **Step 1: Append failing tests for `scan_text()`**

Append to `science/tests/test_markers.py`:
```python
from science_tool.markers import scan_text


def test_scan_text_finds_bare_unverified() -> None:
    hits = scan_text(Path("x.md"), "Some fact [UNVERIFIED] here.\n", strict=False)
    assert len(hits) == 1
    h = hits[0]
    assert h.token == "UNVERIFIED"
    assert h.severity == "warn"
    assert h.in_documentation is False
    assert h.legacy is False
    assert h.line == 1


def test_scan_text_excludes_backticked_token() -> None:
    text = "Mark the claim with `[UNVERIFIED]` per the convention.\n"
    hits = scan_text(Path("x.md"), text, strict=False)
    assert len(hits) == 1
    assert hits[0].in_documentation is True


def test_scan_text_excludes_fenced_code_block() -> None:
    text = "Prose [UNVERIFIED] one.\n```\nblock [UNVERIFIED]\n```\nprose [UNVERIFIED] two.\n"
    hits = scan_text(Path("x.md"), text, strict=False)
    bare = [h for h in hits if not h.in_documentation]
    fenced = [h for h in hits if h.in_documentation]
    assert len(bare) == 2
    assert len(fenced) == 1
    assert fenced[0].line == 3


def test_scan_text_strips_frontmatter() -> None:
    text = "---\ntitle: '[UNVERIFIED] in title'\n---\nbody [UNVERIFIED] here\n"
    hits = scan_text(Path("x.md"), text, strict=False)
    # Frontmatter token is excluded entirely; body token is kept.
    assert len(hits) == 1
    assert hits[0].line == 4


def test_scan_text_recognizes_all_four_tokens() -> None:
    text = "[UNVERIFIED] [MISSING_CITATION] [SPECULATION] [INACCESSIBLE]\n"
    hits = scan_text(Path("x.md"), text, strict=False)
    tokens = sorted(h.token for h in hits)
    assert tokens == ["INACCESSIBLE", "MISSING_CITATION", "SPECULATION", "UNVERIFIED"]


def test_scan_text_legacy_needs_citation_recognized() -> None:
    hits = scan_text(Path("x.md"), "Old style [NEEDS CITATION] here\n", strict=False)
    assert len(hits) == 1
    assert hits[0].token == "MISSING_CITATION"
    assert hits[0].legacy is True


def test_scan_text_strict_promotes_info_tokens() -> None:
    hits = scan_text(Path("x.md"), "[SPECULATION] [INACCESSIBLE]\n", strict=True)
    severities = {h.token: h.severity for h in hits}
    assert severities["SPECULATION"] == "warn"
    assert severities["INACCESSIBLE"] == "warn"


def test_scan_text_multiple_tokens_per_line() -> None:
    hits = scan_text(Path("x.md"), "Two on one line: [UNVERIFIED] and [SPECULATION].\n", strict=False)
    assert len(hits) == 2
    assert {h.token for h in hits} == {"UNVERIFIED", "SPECULATION"}
    assert {h.line for h in hits} == {1}


def test_scan_text_default_severity_for_speculation_is_info() -> None:
    hits = scan_text(Path("x.md"), "[SPECULATION]\n", strict=False)
    assert hits[0].severity == "info"


def test_scan_text_default_severity_for_inaccessible_is_info() -> None:
    hits = scan_text(Path("x.md"), "[INACCESSIBLE]\n", strict=False)
    assert hits[0].severity == "info"


def test_scan_text_skips_hash_headings() -> None:
    # Headings already excluded by refs.py for hypothesis matching; mirror that
    # for markers so an `## [INACCESSIBLE] section` heading isn't double-counted.
    # NB: bracketed token in a heading is unusual but should still be a marker
    # because headings can carry warning intent. Keep heading scanning ON.
    hits = scan_text(Path("x.md"), "## [UNVERIFIED] heading\n", strict=False)
    assert len(hits) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd science && uv run pytest tests/test_markers.py -q
```
Expected: 11 fail with `ImportError: cannot import name 'scan_text'`.

- [ ] **Step 3: Implement `scan_text()`**

Append to `science/src/science_tool/markers.py`:
```python
import re

from science_tool.markdown_utils import is_fence_line

# Pattern matches every literal `[NAME]` or `[NAME WITH SPACE]` we know about.
# The set of recognized inner names is the union of canonical tokens and
# legacy aliases. Anything else inside brackets is left alone.
_RECOGNIZED_INNER = "|".join(
    sorted({*TOKENS, *LEGACY_ALIASES.keys()}, key=len, reverse=True)
)
_TOKEN_RE = re.compile(rf"\[(?P<inner>{_RECOGNIZED_INNER})\]")


def _frontmatter_end_line(lines: list[str]) -> int:
    """Return the 1-based line number of the closing `---` of frontmatter, or 0.

    A return of 0 means: no frontmatter present (or unterminated). Callers
    skip lines `<= return value` from prose scanning.
    """
    if not lines or lines[0].strip() != "---":
        return 0
    for index, line in enumerate(lines[1:], start=2):
        if line.strip() == "---":
            return index
    return 0


def _classify_inner(inner: str) -> tuple[str, bool]:
    """Map an inner bracket name to (canonical_token, legacy_flag)."""
    if inner in LEGACY_ALIASES:
        return LEGACY_ALIASES[inner], True
    return inner, False


def _backtick_spans(line: str) -> list[tuple[int, int]]:
    """Return (start, end) char ranges (inclusive-exclusive) inside backtick spans.

    Single-line spans only. CommonMark inline-code spans do not cross newlines,
    so this is sufficient for marker classification.
    """
    spans: list[tuple[int, int]] = []
    i = 0
    while i < len(line):
        if line[i] == "`":
            j = line.find("`", i + 1)
            if j == -1:
                break
            spans.append((i, j + 1))
            i = j + 1
        else:
            i += 1
    return spans


def _position_inside_any(pos: int, spans: list[tuple[int, int]]) -> bool:
    return any(start <= pos < end for start, end in spans)


def scan_text(file: Path, text: str, *, strict: bool) -> list[MarkerHit]:
    """Scan a single document's text and return all marker hits.

    Tokens are classified as `in_documentation=True` when they appear inside
    a backtick span on a prose line OR anywhere on a line within a fenced
    code block. Tokens on the fence-delimiter line itself are also treated
    as documentation.

    `file` is recorded on each hit but not opened — pass any `Path` (callers
    typically pass the on-disk path so consumers can render `file:line`).
    """
    lines = text.splitlines()
    fm_end = _frontmatter_end_line(lines)
    hits: list[MarkerHit] = []
    in_fenced = False

    for idx, raw_line in enumerate(lines, start=1):
        if idx <= fm_end:
            continue

        is_fence = is_fence_line(raw_line)
        # Compute backtick spans only when needed (prose lines outside fence).
        backticks = [] if (in_fenced or is_fence) else _backtick_spans(raw_line)

        for m in _TOKEN_RE.finditer(raw_line):
            token, legacy = _classify_inner(m.group("inner"))
            in_doc = in_fenced or is_fence or _position_inside_any(m.start(), backticks)
            hits.append(
                MarkerHit(
                    file=file,
                    line=idx,
                    token=token,
                    severity=severity_for(token, strict=strict),
                    in_documentation=in_doc,
                    legacy=legacy,
                )
            )

        if is_fence:
            in_fenced = not in_fenced

    return hits
```

> **Implementer note:** Backtick spans are computed per-line with a simple linear scan (matching pairs of `` ` ``). Tokens whose start position falls inside any span are classified as documentation. This avoids the offset-alignment problem that plagues "strip then re-scan" approaches.

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd science && uv run pytest tests/test_markers.py -q
```
Expected: 19 passed.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/markers.py science/tests/test_markers.py
git commit -m "feat(markers): scan single-document text into MarkerHit list"
```

---

## Task 4: Implement project-walking `scan_markers()`

**Files:**
- Modify: `science/src/science_tool/markers.py`
- Modify: `science/tests/test_markers.py`

- [ ] **Step 1: Append failing tests**

Append to `science/tests/test_markers.py`:
```python
from science_tool.markers import scan_markers


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_scan_markers_walks_doc_and_specs(tmp_path: Path) -> None:
    _write(tmp_path / "doc" / "a.md", "alpha [UNVERIFIED]\n")
    _write(tmp_path / "specs" / "b.md", "beta [SPECULATION]\n")
    _write(tmp_path / "RESEARCH_PLAN.md", "gamma [INACCESSIBLE]\n")
    hits = scan_markers(tmp_path, strict=False)
    files = sorted(h.file.name for h in hits)
    assert files == ["RESEARCH_PLAN.md", "a.md", "b.md"]


def test_scan_markers_skips_templates_and_venv(tmp_path: Path) -> None:
    _write(tmp_path / "doc" / "templates" / "skip.md", "[UNVERIFIED]\n")
    _write(tmp_path / "doc" / ".venv" / "skip.md", "[UNVERIFIED]\n")
    _write(tmp_path / "doc" / "keep.md", "[UNVERIFIED]\n")
    hits = scan_markers(tmp_path, strict=False)
    assert {h.file.name for h in hits} == {"keep.md"}


def test_scan_markers_excludes_documentation_by_default(tmp_path: Path) -> None:
    _write(tmp_path / "doc" / "a.md", "Use the `[UNVERIFIED]` token. Bare [UNVERIFIED] flagged.\n")
    hits = scan_markers(tmp_path, strict=False)
    assert len(hits) == 1
    assert hits[0].in_documentation is False


def test_scan_markers_includes_documentation_when_requested(tmp_path: Path) -> None:
    _write(tmp_path / "doc" / "a.md", "Use the `[UNVERIFIED]` token. Bare [UNVERIFIED] flagged.\n")
    hits = scan_markers(tmp_path, strict=False, include_documentation=True)
    assert len(hits) == 2


def test_scan_markers_strict_promotes_info(tmp_path: Path) -> None:
    _write(tmp_path / "doc" / "a.md", "[SPECULATION]\n")
    hits = scan_markers(tmp_path, strict=True)
    assert hits[0].severity == "warn"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd science && uv run pytest tests/test_markers.py -q
```
Expected: 5 fail with `ImportError: cannot import name 'scan_markers'`.

- [ ] **Step 3: Implement `scan_markers()`**

Append to `science/src/science_tool/markers.py`:
```python
_SCAN_DIRS = ("doc", "specs")
_SCAN_FILES = ("RESEARCH_PLAN.md",)
_SKIP_DIRS = {"templates", ".venv", "data", ".git", "__pycache__"}


def _collect_markdown_files(root: Path) -> list[Path]:
    """Collect all markdown files to scan under a project root.

    Mirrors `refs.py`'s `_collect_markdown_files`. Resolves doc/ and specs/
    via the project's `paths` config when available, falling back to the
    conventional layout.
    """
    try:
        from science_tool.paths import resolve_paths

        pp = resolve_paths(root)
        scan_dirs = [pp.doc_dir, pp.specs_dir]
    except Exception:
        scan_dirs = [root / d for d in _SCAN_DIRS]

    files: list[Path] = []
    for d in scan_dirs:
        if d.is_dir():
            for p in d.rglob("*.md"):
                if not any(part in _SKIP_DIRS for part in p.parts):
                    files.append(p)
    for scan_file in _SCAN_FILES:
        f = root / scan_file
        if f.is_file():
            files.append(f)
    return sorted(files)


def scan_markers(
    root: Path,
    *,
    strict: bool = False,
    include_documentation: bool = False,
) -> list[MarkerHit]:
    """Scan an entire project root and return all marker hits.

    By default, hits with `in_documentation=True` (backticked or fenced) are
    excluded — those are references to the convention itself, not annotations.
    Pass `include_documentation=True` for migration / audit workflows that
    want every occurrence.
    """
    out: list[MarkerHit] = []
    for path in _collect_markdown_files(root):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for hit in scan_text(path, text, strict=strict):
            if hit.in_documentation and not include_documentation:
                continue
            out.append(hit)
    return out
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd science && uv run pytest tests/test_markers.py -q
```
Expected: 24 passed.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/markers.py science/tests/test_markers.py
git commit -m "feat(markers): walk project markdown and return MarkerHit list"
```

---

## Task 5: Wire `markers.scan_markers()` into `refs.check_refs()`

**Files:**
- Modify: `science/src/science_tool/refs.py`
- Modify: `science/tests/test_refs.py`

`RefIssue` gains a `severity` field defaulting to `"warn"`. The marker emission loop in `check_refs` is replaced with a call to `scan_markers()` and a translation step that converts each `MarkerHit` into a `RefIssue`. The `[NEEDS CITATION]` legacy alias is reflected in `ref_value` exactly as the canonical token name (e.g., `[MISSING_CITATION]`) so downstream code is token-canonical; the `legacy:true` provenance is preserved on the message.

- [ ] **Step 1: Update `RefIssue` dataclass**

In `science/src/science_tool/refs.py`, replace the existing `RefIssue` definition (lines 21–30) with:
```python
@dataclass
class RefIssue:
    """A single broken or unresolved reference."""

    file: str
    line: int
    ref_type: str  # "hypothesis" | "citation" | "link" | "marker" | …
    ref_value: str
    message: str
    suggestion: str | None = None
    severity: str = "warn"  # "warn" | "info"
```

- [ ] **Step 2: Replace the marker emission block**

In `science/src/science_tool/refs.py`, delete the old marker block (the two `for m in _UNVERIFIED_RE.finditer(scan_line)` and `for m in _NEEDS_CITATION_RE.finditer(scan_line)` loops, around lines 564–583).

Also delete the now-unused regex constants `_UNVERIFIED_RE` and `_NEEDS_CITATION_RE` (lines 37–38).

At the end of `check_refs()`, *after* the per-file loop has fully run, append:
```python
    from science_tool.markers import scan_markers

    for hit in scan_markers(root, strict=False):
        rel = str(hit.file.relative_to(root))
        token_label = f"[{hit.token}]"
        prefix = "Legacy " if hit.legacy else ""
        issues.append(
            RefIssue(
                file=rel,
                line=hit.line,
                ref_type="marker",
                ref_value=token_label,
                message=f"{prefix}Unresolved {token_label} marker",
                severity=hit.severity,
            )
        )
    return issues
```

(Replace the existing `return issues` at the end of `check_refs()`.)

- [ ] **Step 3: Update existing marker tests**

In `science/tests/test_refs.py`, replace `test_unverified_markers_tracked` (around line 218) with:
```python
def test_unverified_and_legacy_needs_citation_tracked() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "doc").mkdir()
        (root / "doc" / "test.md").write_text(
            "# Test\nSome fact [UNVERIFIED] and another [NEEDS CITATION].\n"
        )
        issues = check_refs(root)
        marker_issues = [i for i in issues if i.ref_type == "marker"]
        assert len(marker_issues) == 2
        markers = {i.ref_value for i in marker_issues}
        # Legacy [NEEDS CITATION] is normalized to canonical [MISSING_CITATION].
        assert markers == {"[UNVERIFIED]", "[MISSING_CITATION]"}
        # Both default to warn severity.
        assert {i.severity for i in marker_issues} == {"warn"}


def test_speculation_and_inaccessible_default_to_info() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "doc").mkdir()
        (root / "doc" / "test.md").write_text(
            "# Test\nMaybe [SPECULATION] and [INACCESSIBLE] paywalled.\n"
        )
        issues = check_refs(root)
        marker_issues = [i for i in issues if i.ref_type == "marker"]
        severities = {i.ref_value: i.severity for i in marker_issues}
        assert severities == {"[SPECULATION]": "info", "[INACCESSIBLE]": "info"}


def test_backticked_marker_excluded_from_check_refs() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "doc").mkdir()
        (root / "doc" / "test.md").write_text(
            "# Test\nUse `[UNVERIFIED]` per convention. Bare [UNVERIFIED] flagged.\n"
        )
        issues = check_refs(root)
        marker_issues = [i for i in issues if i.ref_type == "marker"]
        assert len(marker_issues) == 1
```

- [ ] **Step 4: Update CLI tests that assert marker count or value**

Search `science/tests/test_refs.py` for hardcoded `[NEEDS CITATION]` strings and rewrite test fixtures to use the new token where appropriate. Specifically the lines around 414, 437, and 459 that put `[NEEDS CITATION]` in test markdown — keep one such test with `[NEEDS CITATION]` as a regression test for legacy recognition (asserting the surfaced value is `[MISSING_CITATION]`), and add a sibling test using the new `[MISSING_CITATION]` spelling directly.

Concretely, in each of the three blocks where the test markdown is `"# Test\nH99 is broken, [@Nobody2099] is missing, and [NEEDS CITATION].\n"`, change the inline marker to `[MISSING_CITATION]` and update assertions to look for `[MISSING_CITATION]` in the output. Then add one additional test at the end of the file:

```python
def test_legacy_needs_citation_recognized_in_cli_output() -> None:
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "doc").mkdir()
        (root / "doc" / "test.md").write_text("Old [NEEDS CITATION] in prose.\n")
        result = runner.invoke(refs_group, ["check", "--root", str(root)])
        assert "[MISSING_CITATION]" in result.output
```

(`runner` and `refs_group` are already imported at the top of `test_refs.py` — verify and add if missing.)

- [ ] **Step 5: Run the full refs test suite**

```bash
cd science && uv run pytest tests/test_refs.py tests/test_markers.py tests/test_markdown_utils.py -q
```
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/refs.py science/tests/test_refs.py
git commit -m "feat(refs): delegate marker scanning to markers.scan_markers"
```

---

## Task 6: Update `refs_cli.py` for token-agnostic rendering and `--strict` widening

**Files:**
- Modify: `science/src/science_tool/refs_cli.py`
- Modify: `science/tests/test_refs.py`

- [ ] **Step 1: Replace `_render_marker_summary`**

In `science/src/science_tool/refs_cli.py`, replace the function `_render_marker_summary` (lines 55–70) with:
```python
def _render_marker_summary(markers: list[RefIssue], *, include_locations: bool) -> None:
    from collections import Counter

    counts = Counter(m.ref_value for m in markers)
    click.echo("  Unresolved markers:")
    # Stable display order: warn-severity tokens first, then info, then alpha.
    by_value: dict[str, list[RefIssue]] = {}
    for m in markers:
        by_value.setdefault(m.ref_value, []).append(m)
    ordered = sorted(
        by_value.items(),
        key=lambda kv: (kv[1][0].severity != "warn", kv[0]),
    )
    for value, group in ordered:
        count = len(group)
        sev_tag = "" if group[0].severity == "warn" else " (info)"
        if include_locations:
            locs = ", ".join(f"{m.file}:{m.line}" for m in group)
            click.echo(f"    {count}x {value}{sev_tag} ({locs})")
        else:
            click.echo(f"    {count}x {value}{sev_tag}")
    # Suppress unused-warning for `counts` if any future audit wants it.
    _ = counts
```

- [ ] **Step 2: Widen `--strict` semantics**

In `science/src/science_tool/refs_cli.py`, the `check` command (around line 73) currently exits 1 when `strict and markers`. We need a finer behavior: under `--strict`, INFO marker issues should be re-classified as WARN (matching `validate.sh --strict`), AND any presence of WARN-severity markers should cause exit 1.

Find the body of `check()`. After the `issues = check_refs(...)` call (around line 96), add:
```python
    if strict:
        # Promote info-severity markers to warn under --strict (consistent with
        # validate.sh's --strict semantics).
        from science_tool.markers import severity_for

        for issue in issues:
            if issue.ref_type == "marker" and issue.severity == "info":
                # Recompute severity from the canonical token name in the
                # bracketed value (strip surrounding brackets).
                token = issue.ref_value.strip("[]")
                issue.severity = severity_for(token, strict=True)
```

Then change the final exit decision (around lines 167–170) to:
```python
    if broken:
        raise click.exceptions.Exit(1)
    if any(m.severity == "warn" for m in markers):
        # Under default settings only warn-severity markers trigger exit;
        # info markers (SPECULATION, INACCESSIBLE) are surfaced but non-blocking.
        # Under --strict, the promotion loop above already widened them.
        if strict or any(m.severity == "warn" for m in markers if m.ref_value in ("[UNVERIFIED]", "[MISSING_CITATION]")):
            raise click.exceptions.Exit(1)
```

> **Reviewer note:** the second condition is intentional — without `--strict`, only the historically-blocking tokens (`UNVERIFIED`, `MISSING_CITATION`) trigger exit 1. With `--strict`, every warn-severity marker (including promoted info ones) blocks. This preserves today's exit semantics for non-strict callers while letting `--strict` truly mean "every advisory is now blocking".

- [ ] **Step 3: Add CLI tests for the new behavior**

Append to `science/tests/test_refs.py`:
```python
def test_check_cli_strict_promotes_speculation_to_blocking() -> None:
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "doc").mkdir()
        (root / "doc" / "test.md").write_text("Just [SPECULATION] here.\n")
        # Without --strict: SPECULATION is info, exit 0.
        result = runner.invoke(refs_group, ["check", "--root", str(root)])
        assert result.exit_code == 0
        # With --strict: SPECULATION promoted to warn, exit 1.
        result = runner.invoke(refs_group, ["check", "--root", str(root), "--strict"])
        assert result.exit_code == 1


def test_check_cli_renders_per_token_counts() -> None:
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "doc").mkdir()
        (root / "doc" / "test.md").write_text(
            "[UNVERIFIED] and [SPECULATION] and [INACCESSIBLE]\n"
        )
        result = runner.invoke(refs_group, ["check", "--root", str(root)])
        assert "[UNVERIFIED]" in result.output
        assert "[SPECULATION]" in result.output
        assert "[INACCESSIBLE]" in result.output
        # Info-severity tokens are tagged.
        assert "(info)" in result.output
```

- [ ] **Step 4: Run all tests**

```bash
cd science && uv run pytest tests/test_refs.py tests/test_markers.py tests/test_markdown_utils.py -q
```
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/refs_cli.py science/tests/test_refs.py
git commit -m "feat(refs-cli): per-token marker rendering and widened --strict"
```

---

## Task 7: Add `science markers` CLI group with `scan` subcommand

**Files:**
- Create: `science/src/science_tool/markers_cli.py`
- Create: `science/tests/test_markers_cli.py`
- Modify: `science/src/science_tool/cli.py`

- [ ] **Step 1: Write the failing CLI tests**

`science/tests/test_markers_cli.py`:
```python
"""CLI tests for `science markers`."""
import json
import tempfile
from pathlib import Path

from click.testing import CliRunner

from science_tool.markers_cli import markers_group


def _write(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def test_scan_emits_json_with_per_token_counts() -> None:
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _write(root / "doc" / "a.md", "[UNVERIFIED] [UNVERIFIED] [SPECULATION]\n")
        result = runner.invoke(markers_group, ["scan", "--root", str(root), "--format", "json"])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["counts"] == {"UNVERIFIED": 2, "SPECULATION": 1}
        assert len(payload["hits"]) == 3


def test_scan_json_includes_legacy_flag() -> None:
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _write(root / "doc" / "a.md", "Old [NEEDS CITATION] here.\n")
        result = runner.invoke(markers_group, ["scan", "--root", str(root), "--format", "json"])
        payload = json.loads(result.output)
        assert payload["counts"] == {"MISSING_CITATION": 1}
        hit = payload["hits"][0]
        assert hit["token"] == "MISSING_CITATION"
        assert hit["legacy"] is True


def test_scan_text_format_lists_per_token_counts() -> None:
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _write(root / "doc" / "a.md", "[UNVERIFIED]\n[SPECULATION]\n")
        result = runner.invoke(markers_group, ["scan", "--root", str(root)])
        assert "UNVERIFIED" in result.output
        assert "SPECULATION" in result.output


def test_scan_strict_promotes_info_severity() -> None:
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _write(root / "doc" / "a.md", "[SPECULATION]\n")
        result = runner.invoke(markers_group, ["scan", "--root", str(root), "--format", "json", "--strict"])
        payload = json.loads(result.output)
        assert payload["hits"][0]["severity"] == "warn"


def test_scan_zero_hits_emits_empty_payload() -> None:
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _write(root / "doc" / "a.md", "no markers here\n")
        result = runner.invoke(markers_group, ["scan", "--root", str(root), "--format", "json"])
        payload = json.loads(result.output)
        assert payload["counts"] == {}
        assert payload["hits"] == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd science && uv run pytest tests/test_markers_cli.py -q
```
Expected: 5 fail with `ModuleNotFoundError`.

- [ ] **Step 3: Create `markers_cli.py`**

`science/src/science_tool/markers_cli.py`:
```python
"""Click CLI group for `science markers`."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import click

from science_tool.markers import scan_markers


@click.group("markers")
def markers_group() -> None:
    """Annotation-token tooling for Science projects."""


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
def scan(root_path: Path, output_format: str, strict: bool, include_documentation: bool) -> None:
    """Scan project markdown for annotation tokens."""
    hits = scan_markers(root_path.resolve(), strict=strict, include_documentation=include_documentation)
    counts = Counter(h.token for h in hits)

    if output_format == "json":
        payload = {
            "counts": dict(counts),
            "hits": [
                {
                    "file": str(h.file.relative_to(root_path.resolve())),
                    "line": h.line,
                    "token": h.token,
                    "severity": h.severity,
                    "in_documentation": h.in_documentation,
                    "legacy": h.legacy,
                }
                for h in hits
            ],
        }
        click.echo(json.dumps(payload, indent=2))
        return

    if not hits:
        click.echo("markers scan: no annotation tokens found")
        return

    click.echo("Counts by token:")
    for token, count in sorted(counts.items()):
        click.echo(f"  {token}: {count}")
    click.echo()
    for h in hits:
        rel = h.file.relative_to(root_path.resolve())
        legacy = " (legacy spelling)" if h.legacy else ""
        click.echo(f"  {rel}:{h.line}  [{h.token}]  {h.severity}{legacy}")
```

- [ ] **Step 4: Register the group in `cli.py`**

Open `science/src/science_tool/cli.py`, find the existing `cli.add_command(refs_group)` line (or equivalent registration), and add immediately after:
```python
from science_tool.markers_cli import markers_group
cli.add_command(markers_group)
```

(If the existing import block already collects sub-groups at the top of the file, add the import there and the `add_command` call alongside the others — match local style.)

- [ ] **Step 5: Run CLI tests**

```bash
cd science && uv run pytest tests/test_markers_cli.py -q
```
Expected: 5 passed.

- [ ] **Step 6: Verify the CLI is reachable end-to-end**

```bash
cd science && uv run python -m science_tool markers scan --help
```
Expected: shows the `scan` subcommand under `markers`.

- [ ] **Step 7: Commit**

```bash
git add science/src/science_tool/markers_cli.py science/tests/test_markers_cli.py science/src/science_tool/cli.py
git commit -m "feat(markers): add `science markers scan` CLI"
```

---

## Task 8: Add `science markers migrate` heuristic rewriter

**Files:**
- Modify: `science/src/science_tool/markers_cli.py`
- Modify: `science/tests/test_markers_cli.py`

The migrate command rewrites legacy `[NEEDS CITATION]` to `[MISSING_CITATION]` in-place, with a dry-run preview as the default and `--write` to apply. Inferring the *right* new token from context (UNVERIFIED → SPECULATION, etc.) is intentionally NOT done in this version — that's a heuristic that warrants its own design pass. This task ships only the mechanical legacy-spelling rewrite, which is unambiguous.

- [ ] **Step 1: Append failing tests**

Append to `science/tests/test_markers_cli.py`:
```python
def test_migrate_dry_run_lists_files_with_legacy_tokens() -> None:
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _write(root / "doc" / "a.md", "Old [NEEDS CITATION] here\n")
        _write(root / "doc" / "b.md", "Already [MISSING_CITATION]\n")
        result = runner.invoke(markers_group, ["migrate", "--root", str(root)])
        assert result.exit_code == 0
        assert "doc/a.md" in result.output
        assert "doc/b.md" not in result.output
        # File is unchanged in dry-run.
        assert "[NEEDS CITATION]" in (root / "doc" / "a.md").read_text()


def test_migrate_write_rewrites_legacy_to_canonical() -> None:
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _write(root / "doc" / "a.md", "Old [NEEDS CITATION] here\nand again [NEEDS CITATION].\n")
        result = runner.invoke(markers_group, ["migrate", "--root", str(root), "--write"])
        assert result.exit_code == 0
        new_text = (root / "doc" / "a.md").read_text()
        assert "[NEEDS CITATION]" not in new_text
        assert new_text.count("[MISSING_CITATION]") == 2


def test_migrate_preserves_backticked_legacy_tokens() -> None:
    """Documentation references to the legacy spelling must NOT be rewritten."""
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _write(root / "doc" / "a.md", "Bare [NEEDS CITATION] and `[NEEDS CITATION]` doc-ref.\n")
        result = runner.invoke(markers_group, ["migrate", "--root", str(root), "--write"])
        text = (root / "doc" / "a.md").read_text()
        # Bare occurrence rewritten:
        assert "Bare [MISSING_CITATION]" in text
        # Backticked doc-reference preserved:
        assert "`[NEEDS CITATION]`" in text


def test_migrate_zero_legacy_tokens_is_noop() -> None:
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _write(root / "doc" / "a.md", "Modern [MISSING_CITATION] only.\n")
        result = runner.invoke(markers_group, ["migrate", "--root", str(root), "--write"])
        assert result.exit_code == 0
        assert "no legacy tokens" in result.output.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd science && uv run pytest tests/test_markers_cli.py::test_migrate_dry_run_lists_files_with_legacy_tokens -q
```
Expected: fails with `Error: No such command 'migrate'`.

- [ ] **Step 3: Implement `migrate`**

Append to `science/src/science_tool/markers_cli.py`:
```python
import re

from science_tool.markers import LEGACY_ALIASES, scan_markers
from science_tool.markdown_utils import is_fence_line, strip_inline_code


@markers_group.command("migrate")
@click.option(
    "--root",
    "root_path",
    default=".",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
)
@click.option("--write", is_flag=True, help="Apply rewrites in place (otherwise dry-run).")
def migrate(root_path: Path, write: bool) -> None:
    """Rewrite legacy token spellings to their canonical forms.

    Only bare-prose occurrences are rewritten. Backticked or fenced-code
    occurrences are left alone (they are documentation references to the
    legacy spelling, e.g., in this convention doc itself).
    """
    root = root_path.resolve()
    hits = scan_markers(root, strict=False)
    legacy_hits = [h for h in hits if h.legacy]
    if not legacy_hits:
        click.echo("markers migrate: no legacy tokens found")
        return

    # Group by file for a clean per-file rewrite pass.
    by_file: dict[Path, list[int]] = {}
    for h in legacy_hits:
        by_file.setdefault(h.file, []).append(h.line)

    for path, lines in sorted(by_file.items()):
        rel = path.relative_to(root)
        click.echo(f"  {rel}: {len(lines)} legacy token(s) on lines {sorted(set(lines))}")
        if not write:
            continue
        _rewrite_legacy_tokens_in_file(path)

    if not write:
        click.echo()
        click.echo("Dry-run. Re-run with --write to apply.")


def _rewrite_legacy_tokens_in_file(path: Path) -> None:
    """Rewrite bare-prose legacy tokens in `path` to their canonical spellings.

    Backticked / fenced-code occurrences are preserved verbatim.
    """
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    in_fenced = False
    out_lines: list[str] = []
    for line in lines:
        stripped_newline = line.rstrip("\n")
        if is_fence_line(stripped_newline):
            in_fenced = not in_fenced
            out_lines.append(line)
            continue
        if in_fenced:
            out_lines.append(line)
            continue

        # Substitute only outside backticked spans. Approach: split on inline
        # code spans, rewrite only the prose chunks, rejoin.
        out_lines.append(_rewrite_prose_legacy_tokens(line))
    path.write_text("".join(out_lines), encoding="utf-8")


_INLINE_CODE_SPLIT_RE = re.compile(r"(`[^`]*`)")


def _rewrite_prose_legacy_tokens(line: str) -> str:
    parts = _INLINE_CODE_SPLIT_RE.split(line)
    for i, part in enumerate(parts):
        if part.startswith("`") and part.endswith("`"):
            continue  # preserve backticked content
        rewritten = part
        for legacy_inner, canonical in LEGACY_ALIASES.items():
            rewritten = rewritten.replace(f"[{legacy_inner}]", f"[{canonical}]")
        parts[i] = rewritten
    return "".join(parts)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd science && uv run pytest tests/test_markers_cli.py -q
```
Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/markers_cli.py science/tests/test_markers_cli.py
git commit -m "feat(markers): add `science markers migrate` for legacy spellings"
```

---

## Task 9: Patch `validate.sh` to call `science markers scan`

**Files:**
- Modify: `science/src/science_tool/project_artifacts/data/validate.sh`
- Modify: `science/src/science_tool/project_artifacts/registry.yaml`
- Modify: `science/tests/test_initial_validate_sh.py` (only if existing assertions break)

- [ ] **Step 1: Note the current header values**

Run:
```bash
cd science && grep -E "managed-version|managed-source-sha256" src/science_tool/project_artifacts/data/validate.sh
```
Note the existing version (`2026.05.07.4`) and sha256. We'll move them into `previous_hashes` once the new ones are computed.

- [ ] **Step 2: Replace section 8 of `validate.sh`**

In `science/src/science_tool/project_artifacts/data/validate.sh`, replace lines 506–529 (the entire "─── 8. Unverified/uncited markers ───" block) with:
```bash
# ─── 8. Unresolved annotation markers ──────────────────────────────
echo ""
echo "Checking for unresolved markers..."

if command -v science >/dev/null 2>&1 && [ -d "$DOC_DIR" ]; then
    SCIENCE_MARKERS_FLAGS=()
    if [ "$STRICT" -eq 1 ]; then
        SCIENCE_MARKERS_FLAGS+=("--strict")
    fi
    markers_json=$(science markers scan --root . --format json "${SCIENCE_MARKERS_FLAGS[@]}" 2>/dev/null || echo '{"counts":{},"hits":[]}')
    # Per-token warn counts (info-severity tokens are reported but not warned
    # unless --strict promoted them to warn).
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

> **Implementer note:** the `python3 -c` inline script is unavoidable — bash can't parse JSON. `python3` is a managed-artifact assumption (every project that runs `validate.sh` already has a Python on PATH because `science` is itself a Python tool).

- [ ] **Step 3: Bump the in-file managed-version header**

In the same file, change the header line `# science-managed-version: 2026.05.07.4` to `# science-managed-version: 2026.05.09.1`. Leave the `science-managed-source-sha256:` value alone for now — it'll be recomputed in Step 5.

- [ ] **Step 4: Compute the new body sha256**

Run:
```bash
cd science && uv run python -c "
from pathlib import Path
from science_tool.project_artifacts.hashing import body_hash
from science_tool.project_artifacts.registry_schema import HeaderKind, HeaderProtocol

p = Path('src/science_tool/project_artifacts/data/validate.sh')
proto = HeaderProtocol(kind=HeaderKind.SHEBANG_COMMENT, comment_prefix='#')
print(body_hash(p.read_bytes(), proto))
"
```
Capture the printed sha256 hex string. Call it `<NEW_HASH>`.

- [ ] **Step 5: Update both hash locations**

In `validate.sh`, change the `# science-managed-source-sha256:` line to use `<NEW_HASH>`.

In `science/src/science_tool/project_artifacts/registry.yaml`, find the `validate.sh` artifact entry and:
1. Append the *previous* `current_hash` to `previous_hashes` as a new entry: `- version: '2026.05.07.4'\n        hash: 517199d70d40317733c4974162cbd0fdf635377ab6129000896b178c78a6584a`.
2. Update `version: '2026.05.07.4'` → `version: '2026.05.09.1'`.
3. Update `current_hash:` to `<NEW_HASH>`.

- [ ] **Step 6: Run the managed-artifact integrity tests**

```bash
cd science && uv run pytest tests/test_initial_validate_sh.py tests/test_first_version_bump.py tests/test_acceptance_managed_artifacts.py -q
```
Expected: all pass. If `test_current_hash_matches_body` fails, the hashes don't match — re-run Step 4 and fix.

- [ ] **Step 7: Run `validate.sh` end-to-end against a sample project**

Use the existing acceptance test as the smoke check:
```bash
cd science && uv run pytest tests/test_acceptance_managed_artifacts.py -q
```
Expected: pass — this test already runs `validate.sh` against a minimal generated project.

- [ ] **Step 8: Commit**

```bash
git add science/src/science_tool/project_artifacts/data/validate.sh science/src/science_tool/project_artifacts/registry.yaml
git commit -m "feat(validate): delegate marker counting to science markers scan

Bumps validate.sh to 2026.05.09.1. Replaces the bash grep for
[UNVERIFIED] / [NEEDS CITATION] with a call to science markers scan,
yielding per-token counts that align with the four-token vocabulary
(UNVERIFIED, MISSING_CITATION, SPECULATION, INACCESSIBLE)."
```

---

## Task 10: Update `commands/research-papers.md` skill

**Files:**
- Modify: `commands/research-papers.md`

- [ ] **Step 1: Replace the marker guidance**

Open `commands/research-papers.md` and locate the four sites that mention `[UNVERIFIED]`:
- Line 72 (`mark unverified details as [UNVERIFIED]`)
- Line 81 (`mark every specific number / figure / method detail as [UNVERIFIED]`)
- Line 84 (`mark methods/results as [UNVERIFIED]`)
- Line 139 (`Review any [UNVERIFIED] fields…`)

Update each per the table below. The intent: tokens chosen by *what blocks resolution*, not by uniform default.

- Line 72: change `mark unverified details as [UNVERIFIED]` → `mark each not-yet-checked detail as [UNVERIFIED]; mark paywalled / image-only / DACO-gated source content as [INACCESSIBLE]; mark author conjecture as [SPECULATION]`.
- Line 81 (the "ok_no_pdf" exception — operating from LLM knowledge alone): change `mark every specific number / figure / method detail as [UNVERIFIED]` → `mark every specific number / figure / method detail as [UNVERIFIED] (you may verify later) — but mark conceptual extrapolations beyond what the abstract states as [SPECULATION]`.
- Line 84 (Europe PMC abstract fallback): change `mark methods/results as [UNVERIFIED]` → `mark methods/results as [INACCESSIBLE] (the full text is not reachable from any agent-accessible tier)`.
- Line 139: change `Review any [UNVERIFIED] fields the subagent flagged` → `Review any [UNVERIFIED] / [SPECULATION] fields the subagent flagged ([INACCESSIBLE] markers are permanent and don't need follow-up)`.

Add a new section right before the existing "Review" section (which contains line 139), titled `## Annotation tokens`:
```markdown
## Annotation tokens

Use the four-token vocabulary defined in `docs/conventions/annotation-tokens.md`:

- `[UNVERIFIED]` — the claim is verifiable in principle but you haven't checked.
- `[MISSING_CITATION]` — the claim needs a specific source pointer (the claim itself isn't in dispute).
- `[SPECULATION]` — author conjecture; not from the source.
- `[INACCESSIBLE]` — paywalled / image-only / DACO-gated / private; resolution requires resources you don't have.

Pick by access status, not by reflex. Most paper-summary fields warrant `[UNVERIFIED]` (the PDF is in front of you — it's verifiable). Switch to `[INACCESSIBLE]` only when the source genuinely can't be reached. `[SPECULATION]` is for your own extrapolations, never for things that should have been quoted from the paper.
```

- [ ] **Step 2: Verify the file still parses as markdown**

```bash
cd ~/d/science/.claude/worktrees/annotation-tokens-phase2 && head -200 commands/research-papers.md > /dev/null
```
(No errors expected; this is just a smoke read.)

- [ ] **Step 3: Commit**

```bash
git add commands/research-papers.md
git commit -m "docs(research-papers): annotate by access status using four-token vocabulary"
```

---

## Task 11: Update `skills/writing/SKILL.md`

**Files:**
- Modify: `skills/writing/SKILL.md`

- [ ] **Step 1: Append a token-selection section**

Read the current `skills/writing/SKILL.md` to find an appropriate insertion point (most likely near other prose conventions). Append at the end (or insert after an existing "Conventions" section if one exists):
```markdown
## Annotation tokens

When drafting prose where a specific claim cannot be backed by an in-line citation, choose from the four-token vocabulary defined in `docs/conventions/annotation-tokens.md`:

- `[UNVERIFIED]` — claim is verifiable in principle, not yet checked. Default for "I'll backfill the cite later."
- `[MISSING_CITATION]` — the claim itself isn't in dispute, but a specific source pointer is needed.
- `[SPECULATION]` — author conjecture / brainstorming layer. Marks the claim as belonging to the speculative tier.
- `[INACCESSIBLE]` — source is paywalled / image-only / DACO-gated; resolution requires resources you don't have.

These are bare tokens in prose. References to the *tokens themselves* (e.g., when documenting the convention) must be backticked: ``Use the `[UNVERIFIED]` token``. Validators exclude backticked occurrences automatically.

`validate.sh` and `science refs check` count `[UNVERIFIED]` and `[MISSING_CITATION]` as warnings by default; `[SPECULATION]` and `[INACCESSIBLE]` are reported as info only (use `--strict` to treat them as warnings).
```

- [ ] **Step 2: Commit**

```bash
git add skills/writing/SKILL.md
git commit -m "docs(writing-skill): document four-token annotation vocabulary"
```

---

## Task 12: Write `docs/conventions/annotation-tokens.md`

**Files:**
- Create: `docs/conventions/annotation-tokens.md`

- [ ] **Step 1: Create the directory if it doesn't exist**

```bash
cd ~/d/science/.claude/worktrees/annotation-tokens-phase2 && mkdir -p docs/conventions
```

- [ ] **Step 2: Write the convention doc**

`docs/conventions/annotation-tokens.md`:
```markdown
---
id: "convention:annotation-tokens"
type: "convention"
title: "Annotation tokens"
status: "active"
created: "2026-05-09"
updated: "2026-05-09"
---

# Annotation tokens

Inline marker tokens used in prose to flag specific epistemic states. Counted by `validate.sh` and `science refs check` via the shared scanner in `science_tool/markers.py`.

## Vocabulary

| Token                | Meaning                                                                  | Default severity | Under `--strict` |
|----------------------|--------------------------------------------------------------------------|------------------|------------------|
| `[UNVERIFIED]`       | Verifiable in principle but not yet checked.                              | warn             | warn             |
| `[MISSING_CITATION]` | A specific factual claim needs a source pointer (claim not in dispute). | warn             | warn             |
| `[SPECULATION]`      | Author conjecture / brainstorming layer.                                  | info             | warn             |
| `[INACCESSIBLE]`     | Source paywalled / image-only / DACO-gated / private; expected permanent. | info             | warn             |

`info`-severity tokens are counted by the scanner but do not contribute to `validate.sh`'s warning count nor cause a non-zero exit from `science refs check` unless `--strict` is set.

## Lexical scope

A token's *meaning* depends on whether it appears inside an inline-code span or a fenced code block:

- **Bare token** in prose (e.g., `the n is [UNVERIFIED] in the abstract`) is a **document annotation** and counts toward severity tallies.
- **Backticked token** (e.g., ``mark this `[UNVERIFIED]` per the convention``) is **documentation/example use** — referring to the token as a token. Excluded from tallies.
- Tokens inside fenced code blocks (` ``` `) are also excluded.

This split lets convention docs (this file included) discuss the tokens without polluting validation output.

## Choosing the right token

```
Is the claim verifiable from a source you can reach?
├── Yes → not yet checked → [UNVERIFIED]
├── Yes → checked, just need to write the cite → [MISSING_CITATION]
├── No  → because it's your own conjecture → [SPECULATION]
└── No  → because the source is paywalled / private / image-only → [INACCESSIBLE]
```

## Legacy alias

`[NEEDS CITATION]` is recognized as a synonym for `[MISSING_CITATION]` during the deprecation window. The scanner reports occurrences as canonical `[MISSING_CITATION]` but tags the underlying hit as `legacy: true` in JSON output. Run `science markers migrate --write` to rewrite legacy spellings in place. Backticked legacy spellings (in this doc, for example) are preserved.

## Tooling

- `science markers scan [--root .] [--format json|table] [--strict] [--include-documentation]` — scan project markdown for tokens.
- `science markers migrate [--root .] [--write]` — rewrite legacy `[NEEDS CITATION]` spellings to canonical `[MISSING_CITATION]`.
- `science refs check` and `validate.sh` both delegate marker counting to the same scanner.

## Future work (phase 3)

A richer sub-document annotation system (rich payloads, multi-annotation per ROI, graph integration) is deferred to a follow-up RFC. The four phase-2 tokens become annotation *types* under that design; existing inline tokens continue to work, and richer payloads opt into a sidecar form. See `docs/plans/2026-05-09-annotation-system-stub.md` for the full phase-3 sketch.
```

- [ ] **Step 3: Verify `validate.sh` doesn't flag this doc itself**

```bash
cd ~/d/science/.claude/worktrees/annotation-tokens-phase2 && cd science && uv run python -m science_tool markers scan --root .. --format json | python3 -c "import json,sys; d=json.load(sys.stdin); hits=[h for h in d['hits'] if 'annotation-tokens.md' in h['file']]; print('hits in convention doc:', hits)"
```
Expected: `hits in convention doc: []` (every token in the convention doc is either backticked or in a fenced code block, so none should leak through as annotations).

- [ ] **Step 4: Commit**

```bash
cd ~/d/science/.claude/worktrees/annotation-tokens-phase2
git add docs/conventions/annotation-tokens.md
git commit -m "docs: annotation-tokens convention reference"
```

---

## Task 13: Final verification

**Files:** none modified

- [ ] **Step 1: Run the full test suite for affected modules**

```bash
cd science && uv run pytest tests/test_markers.py tests/test_markers_cli.py tests/test_markdown_utils.py tests/test_refs.py tests/test_initial_validate_sh.py tests/test_first_version_bump.py tests/test_acceptance_managed_artifacts.py -q
```
Expected: all pass.

- [ ] **Step 2: Run the full project test suite**

```bash
cd science && uv run pytest -q
```
Expected: all pass. If anything regresses, triage before declaring done.

- [ ] **Step 3: Run ruff**

```bash
cd science && uv run ruff check src/science_tool/markers.py src/science_tool/markdown_utils.py src/science_tool/markers_cli.py src/science_tool/refs.py src/science_tool/refs_cli.py
```
Expected: no errors.

- [ ] **Step 4: Manual smoke test against the worktree itself**

```bash
cd ~/d/science/.claude/worktrees/annotation-tokens-phase2/science && uv run python -m science_tool markers scan --root .. --format table | head -30
```
Expected: shows per-token counts for the worktree's own markdown. The convention doc should not appear in hits (Task 12 Step 3 verified this).

- [ ] **Step 5: Mark execution handoff to finishing-a-development-branch**

Once all of the above are green, the implementation is complete. Hand off to `superpowers:finishing-a-development-branch` to decide on integration (PR vs direct merge vs further iteration).

---

## Out of scope (sibling-plan candidates)

The following items from the phase-2 stub are intentionally NOT in this plan:

- **Frontmatter `doi:` / `pmid:` mutual-optional validator + `science paper sync` CLI.** Independent deliverable; will land in a sibling plan dated 2026-05-09 with the suffix `-paper-sync`.
- **`science markers migrate` heuristic context inference** (e.g., choosing `[INACCESSIBLE]` vs `[UNVERIFIED]` based on access frontmatter). The mechanical legacy-spelling rewrite is in this plan; the smarter inference is deferred to a follow-up.
- **Phase 3** — rich sub-document annotation system, graph integration, multi-annotation per ROI. Deferred to a follow-up RFC per the original stub.
- **Cross-project rollout** — bumping downstream projects' `validate.sh` via `science health` resync and running `science markers migrate` on each. This is a per-project operational task done after this plan ships.

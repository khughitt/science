# Prose Lint Group Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `science prose lint` — four mechanically-detectable prose-quality lints surfaced by natural-systems's t466 citation-audit pilot, generalized to any Science project.

**Architecture:** Single `prose_lint.py` module with one pure detector function per check, a shared `LintIssue` dataclass, and a `scan_root()` orchestrator that mirrors `markers.scan_markers()`. CLI subcommands in `prose_lint_cli.py` follow the markers pattern. Project config (`science.yaml`) gains a `prose_lint:` block whose `anchor_patterns` field configures the numeric-anchor detector. `validate.sh` adds section 9 calling `science prose lint --format json`.

**Tech Stack:** Python 3.13, Click, Pydantic, PyYAML, pytest.

**Origin:** `doc/interpretations/2026-05-06-citation-audit-pilot.md` in `~/d/natural-systems` identified six recurring statement-citation gap patterns; four are mechanically detectable. This plan generalizes those four into shared `~/d/science` tooling.

---

## File Structure

- Create: `science/src/science_tool/prose_lint.py`
  - Owns `LintIssue` dataclass, four detector functions (`detect_*`), and `scan_root(root, *, checks, strict, config)` orchestrator.
- Create: `science/src/science_tool/prose_lint_cli.py`
  - `prose` Click group with `lint` subcommand (`--root`, `--format json|table`, `--strict`, `--check` multi-select).
- Create: `science/tests/test_prose_lint.py`
  - Unit tests for each detector function plus orchestrator.
- Create: `science/tests/test_prose_lint_cli.py`
  - CLI tests covering format flags, --check filtering, --strict promotion.
- Modify: `science/src/science_tool/markdown_utils.py`
  - Add `parse_frontmatter(path)` returning `(data: dict, body_start_line: int)`.
- Modify: `science/src/science_tool/project_config.py`
  - Add `ProseLintConfig` model and `prose_lint: ProseLintConfig | None = None` field on `ProjectConfig`.
- Modify: `science/src/science_tool/cli.py`
  - Import and register `prose_group`.
- Modify: `science/src/science_tool/project_artifacts/data/validate.sh`
  - Add section 9 (prose lints); bump version `2026.05.09.2` → `2026.05.10.1`.
- Modify: `science/src/science_tool/project_artifacts/registry.yaml`
  - Add new version entry, prepend `2026.05.09.2` hash to `previous_hashes`, update `current_hash`, append migration + changelog entries.
- Create: `docs/conventions/prose-lints.md`
  - User-facing docs: lint table, defaults, project-config schema, severity rules.
- Modify: `docs/conventions/annotation-tokens.md`
  - Add cross-link: prose lints surface candidates for `[SPECULATION]` / `[MISSING_CITATION]` tagging.

## Lint Catalog

| Lint name (CLI flag) | Detects | Default severity | Config? |
|---|---|---|---|
| `bare-author-year` | `<Capitalized Word> <4-digit year>` patterns in body prose without an adjacent `[@<key>]` BibTeX-style anchor | `warn` | none |
| `short-form-ids` | Bare `Q1`, `t088`, `q54`, etc. — short forms of canonical entity refs in body prose. Suggests the `<kind>:<id>` form. | `warn` | none |
| `frontmatter-inline-gap` | Frontmatter `related:` entries that never appear in the document body | `info` | none |
| `numeric-anchor` | Numeric claims (`ρ = 0.168`, `30%`, `n = 184`) in body prose without an anchor token (`task:`, `pipeline/`, `[@…]`, etc.) within the same paragraph | `info` | `prose_lint.anchor_patterns` |

`--strict` promotes all `info` issues to `warn` and exits non-zero. Same semantics as `science markers scan --strict`.

## Project Config Schema

`science.yaml` gains an optional block:

```yaml
prose_lint:
  enabled_checks:
    - bare-author-year
    - short-form-ids
    - frontmatter-inline-gap
    - numeric-anchor
  anchor_patterns:
    - "task:"
    - "pipeline/"
    - "\\[@"
```

If `prose_lint` is absent, all four checks run and `anchor_patterns` defaults to `["task:", "pipeline/", r"\[@", "data/", "scripts/"]`.

---

## Task 1: Add `parse_frontmatter` helper to markdown_utils

**Files:**
- Modify: `science/src/science_tool/markdown_utils.py`
- Modify: `science/tests/test_markdown_utils.py`

- [ ] **Step 1: Write the failing test**

Append to `science/tests/test_markdown_utils.py`:

```python
def test_parse_frontmatter_returns_data_and_body_start(tmp_path):
    from science_tool.markdown_utils import parse_frontmatter

    path = tmp_path / "doc.md"
    path.write_text(
        "---\n"
        "id: question:q01-foo\n"
        "related:\n"
        "  - task:t050\n"
        "---\n"
        "# Body\n"
        "Text here.\n"
    )
    data, body_start = parse_frontmatter(path)
    assert data == {"id": "question:q01-foo", "related": ["task:t050"]}
    assert body_start == 6  # 1-based line number of first body line


def test_parse_frontmatter_returns_empty_when_absent(tmp_path):
    from science_tool.markdown_utils import parse_frontmatter

    path = tmp_path / "doc.md"
    path.write_text("# Just body\n")
    data, body_start = parse_frontmatter(path)
    assert data == {}
    assert body_start == 1


def test_parse_frontmatter_returns_empty_when_unterminated(tmp_path):
    from science_tool.markdown_utils import parse_frontmatter

    path = tmp_path / "doc.md"
    path.write_text("---\nid: question:q01-foo\n# Forgot to close\n")
    data, body_start = parse_frontmatter(path)
    assert data == {}
    assert body_start == 1
```

- [ ] **Step 2: Run the tests to verify failure**

Run:

```bash
cd science && uv run pytest tests/test_markdown_utils.py -v -k parse_frontmatter
```

Expected: FAIL with `ImportError: cannot import name 'parse_frontmatter'`.

- [ ] **Step 3: Implement `parse_frontmatter`**

Append to `science/src/science_tool/markdown_utils.py`:

```python
import yaml


def parse_frontmatter(path: Path) -> tuple[dict, int]:
    """Return ``(frontmatter_data, body_start_line)`` for a markdown file.

    `body_start_line` is the 1-based line number of the first body line
    (or 1 if the file has no parseable frontmatter).
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ({}, 1)
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return ({}, 1)
    for index, line in enumerate(lines[1:], start=2):
        if line.strip() == "---":
            yaml_block = "\n".join(lines[1 : index - 1])
            try:
                data = yaml.safe_load(yaml_block) or {}
            except yaml.YAMLError:
                return ({}, 1)
            if not isinstance(data, dict):
                return ({}, 1)
            return (data, index + 1)
    return ({}, 1)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:

```bash
cd science && uv run pytest tests/test_markdown_utils.py -v -k parse_frontmatter
```

Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/markdown_utils.py science/tests/test_markdown_utils.py
git commit -m "feat(markdown_utils): add parse_frontmatter helper for prose-lint use"
```

---

## Task 2: LintIssue dataclass + bare-author-year detector

**Files:**
- Create: `science/src/science_tool/prose_lint.py`
- Create: `science/tests/test_prose_lint.py`

- [ ] **Step 1: Write the failing tests**

Create `science/tests/test_prose_lint.py`:

```python
"""Unit tests for prose_lint detectors."""

from pathlib import Path

import pytest

from science_tool.prose_lint import LintIssue, detect_bare_author_year


def _write(tmp_path: Path, body: str, frontmatter: str = "") -> Path:
    path = tmp_path / "doc.md"
    if frontmatter:
        path.write_text(f"---\n{frontmatter}\n---\n{body}")
    else:
        path.write_text(body)
    return path


class TestBareAuthorYear:
    def test_flags_bare_author_year(self, tmp_path):
        path = _write(tmp_path, "As shown in Brunton 2022, the result holds.\n")
        issues = detect_bare_author_year(path)
        assert len(issues) == 1
        assert issues[0].check == "bare-author-year"
        assert issues[0].line == 1
        assert "Brunton 2022" in issues[0].message
        assert issues[0].severity == "warn"

    def test_no_flag_when_anchored(self, tmp_path):
        path = _write(tmp_path, "Brunton 2022 [@brunton2022] showed it.\n")
        assert detect_bare_author_year(path) == []

    def test_no_flag_inside_inline_code(self, tmp_path):
        path = _write(tmp_path, "Use the form `Brunton 2022` as a placeholder.\n")
        assert detect_bare_author_year(path) == []

    def test_no_flag_inside_fenced_code(self, tmp_path):
        path = _write(
            tmp_path,
            "```\nExample: Brunton 2022\n```\nProse here.\n",
        )
        assert detect_bare_author_year(path) == []

    def test_no_flag_inside_frontmatter(self, tmp_path):
        path = _write(
            tmp_path,
            "Body.\n",
            frontmatter='note: "Cited Brunton 2022 in earlier draft"',
        )
        assert detect_bare_author_year(path) == []

    def test_handles_multiple_per_line(self, tmp_path):
        path = _write(tmp_path, "Brunton 2022 and Gilpin 2021 both showed this.\n")
        issues = detect_bare_author_year(path)
        assert len(issues) == 2
        assert {i.message for i in issues} == {
            "bare author-year mention 'Brunton 2022' has no adjacent [@key]",
            "bare author-year mention 'Gilpin 2021' has no adjacent [@key]",
        }
```

- [ ] **Step 2: Run the tests to verify failure**

Run:

```bash
cd science && uv run pytest tests/test_prose_lint.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'science_tool.prose_lint'`.

- [ ] **Step 3: Implement the dataclass + detector**

Create `science/src/science_tool/prose_lint.py`:

```python
"""Prose-quality lints derived from natural-systems's t466 citation-audit pilot.

Each detector function takes a markdown file Path and returns a list of
LintIssue records. The CLI orchestrator (`prose_lint_cli.py`) batches these
across a project tree and renders results.

See `docs/conventions/prose-lints.md` for the lint catalog and severity rules.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from science_tool.markdown_utils import (
    is_fence_line,
    parse_frontmatter,
    strip_inline_code,
)

CHECKS: tuple[str, ...] = (
    "bare-author-year",
    "short-form-ids",
    "frontmatter-inline-gap",
    "numeric-anchor",
)

DEFAULT_SEVERITY: dict[str, str] = {
    "bare-author-year": "warn",
    "short-form-ids": "warn",
    "frontmatter-inline-gap": "info",
    "numeric-anchor": "info",
}


@dataclass(frozen=True)
class LintIssue:
    file: Path
    line: int
    col: int
    check: str
    severity: str
    message: str


def severity_for(check: str, *, strict: bool) -> str:
    base = DEFAULT_SEVERITY[check]
    return "warn" if strict and base == "info" else base


# Capture: (Authorname) (Year), where Authorname starts with uppercase and is
# 3+ chars (excludes "I 2022", "A 2022"). Year is 1900–2099.
_BARE_AUTHOR_YEAR_RE = re.compile(
    r"\b([A-Z][A-Za-z]{2,}(?:\s(?:and|&)\s[A-Z][A-Za-z]{2,})?)\s(19\d\d|20\d\d)\b"
)
# Anchor: `[@key]` immediately following or preceding the match (within 30 chars)
_NEARBY_BIBTEX_RE = re.compile(r"\[@[A-Za-z][A-Za-z0-9_-]*\]")


def detect_bare_author_year(path: Path, *, strict: bool = False) -> list[LintIssue]:
    """Detect `<Capitalized> <Year>` mentions in body prose without [@key]."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    _, body_start = parse_frontmatter(path)
    lines = text.splitlines()
    issues: list[LintIssue] = []
    in_fence = False
    for lineno_zero, raw_line in enumerate(lines):
        lineno = lineno_zero + 1
        if lineno < body_start:
            continue
        if is_fence_line(raw_line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        line = strip_inline_code(raw_line)
        for match in _BARE_AUTHOR_YEAR_RE.finditer(line):
            mention = f"{match.group(1)} {match.group(2)}"
            window_start = max(0, match.start() - 30)
            window_end = min(len(line), match.end() + 30)
            if _NEARBY_BIBTEX_RE.search(line[window_start:window_end]):
                continue
            issues.append(
                LintIssue(
                    file=path,
                    line=lineno,
                    col=match.start() + 1,
                    check="bare-author-year",
                    severity=severity_for("bare-author-year", strict=strict),
                    message=f"bare author-year mention '{mention}' has no adjacent [@key]",
                )
            )
    return issues
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:

```bash
cd science && uv run pytest tests/test_prose_lint.py -v
```

Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/prose_lint.py science/tests/test_prose_lint.py
git commit -m "feat(prose_lint): add bare-author-year detector + LintIssue dataclass"
```

---

## Task 3: Short-form ID detector

**Files:**
- Modify: `science/src/science_tool/prose_lint.py`
- Modify: `science/tests/test_prose_lint.py`

- [ ] **Step 1: Write the failing tests**

Append to `science/tests/test_prose_lint.py`:

```python
from science_tool.prose_lint import detect_short_form_ids


class TestShortFormIds:
    def test_flags_bare_q_number(self, tmp_path):
        path = _write(tmp_path, "See Q1 for the framing question.\n")
        issues = detect_short_form_ids(path)
        assert len(issues) == 1
        assert "Q1" in issues[0].message
        assert "question:" in issues[0].message  # suggestion includes canonical kind

    def test_flags_bare_t_number(self, tmp_path):
        path = _write(tmp_path, "Implemented in t088.\n")
        issues = detect_short_form_ids(path)
        assert len(issues) == 1
        assert "t088" in issues[0].message
        assert "task:" in issues[0].message

    def test_no_flag_canonical_form(self, tmp_path):
        path = _write(tmp_path, "Implemented in task:t088.\n")
        assert detect_short_form_ids(path) == []

    def test_no_flag_inside_code(self, tmp_path):
        path = _write(tmp_path, "Refer to `Q1` as a placeholder.\n")
        assert detect_short_form_ids(path) == []

    def test_no_flag_in_task_list_header(self, tmp_path):
        # tasks/active.md uses `## [t088] Title` as its canonical heading shape.
        path = _write(tmp_path, "## [t088] Some task title\n\nDescription.\n")
        assert detect_short_form_ids(path) == []

    def test_flags_multiple_kinds(self, tmp_path):
        path = _write(tmp_path, "Per Q1 and h05, refer to t050.\n")
        issues = detect_short_form_ids(path)
        # Q1 -> question, h05 -> hypothesis, t050 -> task
        assert len(issues) == 3
        kinds_in_messages = {
            "question:" if "question:" in i.message else
            "hypothesis:" if "hypothesis:" in i.message else
            "task:"
            for i in issues
        }
        assert kinds_in_messages == {"question:", "hypothesis:", "task:"}

    def test_no_flag_on_random_caps(self, tmp_path):
        # "X1" is a generic identifier, not a known short form.
        path = _write(tmp_path, "Variable X1 holds the result.\n")
        assert detect_short_form_ids(path) == []
```

- [ ] **Step 2: Run the tests to verify failure**

Run:

```bash
cd science && uv run pytest tests/test_prose_lint.py::TestShortFormIds -v
```

Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement the detector**

Append to `science/src/science_tool/prose_lint.py`:

```python
# Short-form prefix → canonical kind mapping. Lowercase letter prefixes pulled
# from refs._LOCAL_ENTITY_KINDS first letters where a unique mapping exists;
# uppercase variants (Q1, T088) are common ad-hoc shorthand.
_SHORT_FORM_KIND_MAP: dict[str, str] = {
    "q": "question",
    "Q": "question",
    "h": "hypothesis",
    "H": "hypothesis",
    "t": "task",
    "T": "task",
    "d": "discussion",
    "D": "discussion",
    "i": "interpretation",
    "I": "interpretation",
}
_SHORT_FORM_RE = re.compile(r"\b([qQhHtTdDiI])(\d{1,4})\b")
# Canonical form check: `<kind>:<short>` should NOT be flagged.
_CANONICAL_PREFIX_RE = re.compile(r"\b(question|hypothesis|task|discussion|interpretation):")
# Task-list heading shape: `## [t088] Title`. Don't flag the bracketed ID
# inside such a header — it IS the canonical form for that file convention.
_TASK_HEADING_RE = re.compile(r"^\s*##+\s*\[[a-zA-Z]\d+\]")


def detect_short_form_ids(path: Path, *, strict: bool = False) -> list[LintIssue]:
    """Detect bare `Q1` / `t088` style refs that should be `question:q01-…` etc."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    _, body_start = parse_frontmatter(path)
    lines = text.splitlines()
    issues: list[LintIssue] = []
    in_fence = False
    for lineno_zero, raw_line in enumerate(lines):
        lineno = lineno_zero + 1
        if lineno < body_start:
            continue
        if is_fence_line(raw_line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if _TASK_HEADING_RE.match(raw_line):
            continue
        line = strip_inline_code(raw_line)
        for match in _SHORT_FORM_RE.finditer(line):
            # Skip if preceded by `<kind>:` — already canonical.
            preceding = line[max(0, match.start() - 20) : match.start()]
            if _CANONICAL_PREFIX_RE.search(preceding):
                continue
            short = match.group(0)
            kind = _SHORT_FORM_KIND_MAP[match.group(1)]
            issues.append(
                LintIssue(
                    file=path,
                    line=lineno,
                    col=match.start() + 1,
                    check="short-form-ids",
                    severity=severity_for("short-form-ids", strict=strict),
                    message=f"short-form ID '{short}' should be canonical '{kind}:…'",
                )
            )
    return issues
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:

```bash
cd science && uv run pytest tests/test_prose_lint.py::TestShortFormIds -v
```

Expected: PASS (7 tests).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/prose_lint.py science/tests/test_prose_lint.py
git commit -m "feat(prose_lint): add short-form-ids detector"
```

---

## Task 4: Frontmatter-inline gap detector

**Files:**
- Modify: `science/src/science_tool/prose_lint.py`
- Modify: `science/tests/test_prose_lint.py`

- [ ] **Step 1: Write the failing tests**

Append to `science/tests/test_prose_lint.py`:

```python
from science_tool.prose_lint import detect_frontmatter_inline_gaps


class TestFrontmatterInlineGap:
    def test_flags_unmentioned_related_entry(self, tmp_path):
        path = _write(
            tmp_path,
            "# Title\n\nNo mention of the related entries.\n",
            frontmatter="related:\n  - task:t050\n  - question:q01-foo",
        )
        issues = detect_frontmatter_inline_gaps(path)
        refs_flagged = {i.message.split("'")[1] for i in issues}
        assert refs_flagged == {"task:t050", "question:q01-foo"}
        for issue in issues:
            assert issue.check == "frontmatter-inline-gap"
            assert issue.severity == "info"
            assert issue.line == 1  # reported at file start

    def test_no_flag_when_mentioned_in_body(self, tmp_path):
        path = _write(
            tmp_path,
            "# Title\n\nSee task:t050 for details.\n",
            frontmatter="related:\n  - task:t050",
        )
        assert detect_frontmatter_inline_gaps(path) == []

    def test_no_flag_when_no_frontmatter(self, tmp_path):
        path = _write(tmp_path, "Just body.\n")
        assert detect_frontmatter_inline_gaps(path) == []

    def test_no_flag_when_no_related_field(self, tmp_path):
        path = _write(
            tmp_path,
            "# Title\n\nBody.\n",
            frontmatter="id: question:q01-foo",
        )
        assert detect_frontmatter_inline_gaps(path) == []

    def test_strict_promotes_severity(self, tmp_path):
        path = _write(
            tmp_path,
            "Body without mention.\n",
            frontmatter="related:\n  - task:t050",
        )
        issues = detect_frontmatter_inline_gaps(path, strict=True)
        assert all(i.severity == "warn" for i in issues)
```

- [ ] **Step 2: Run the tests to verify failure**

Run:

```bash
cd science && uv run pytest tests/test_prose_lint.py::TestFrontmatterInlineGap -v
```

Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement the detector**

Append to `science/src/science_tool/prose_lint.py`:

```python
def detect_frontmatter_inline_gaps(
    path: Path, *, strict: bool = False
) -> list[LintIssue]:
    """For each `related:` entry in frontmatter, flag if absent from body text.

    Reports all gaps at line 1 (the file is the unit, not the location).
    """
    data, body_start = parse_frontmatter(path)
    related = data.get("related") if isinstance(data, dict) else None
    if not isinstance(related, list) or not related:
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return []
    body = "\n".join(lines[body_start - 1 :])
    issues: list[LintIssue] = []
    for ref in related:
        if not isinstance(ref, str) or not ref.strip():
            continue
        if ref in body:
            continue
        issues.append(
            LintIssue(
                file=path,
                line=1,
                col=1,
                check="frontmatter-inline-gap",
                severity=severity_for("frontmatter-inline-gap", strict=strict),
                message=f"frontmatter related entry '{ref}' never appears in body prose",
            )
        )
    return issues
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:

```bash
cd science && uv run pytest tests/test_prose_lint.py::TestFrontmatterInlineGap -v
```

Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/prose_lint.py science/tests/test_prose_lint.py
git commit -m "feat(prose_lint): add frontmatter-inline-gap detector"
```

---

## Task 5: ProseLintConfig + numeric-anchor detector

**Files:**
- Modify: `science/src/science_tool/project_config.py`
- Modify: `science/src/science_tool/prose_lint.py`
- Modify: `science/tests/test_prose_lint.py`
- Create: `science/tests/test_project_config_prose_lint.py`

- [ ] **Step 1: Write failing config tests**

Create `science/tests/test_project_config_prose_lint.py`:

```python
from pathlib import Path

from science_tool.project_config import (
    DEFAULT_ANCHOR_PATTERNS,
    ProseLintConfig,
    load_project_config,
)


def test_default_anchor_patterns_when_block_absent(tmp_path):
    (tmp_path / "science.yaml").write_text("name: demo\n")
    config = load_project_config(tmp_path)
    assert config.prose_lint is None
    # Caller resolves defaults via DEFAULT_ANCHOR_PATTERNS.
    assert "task:" in DEFAULT_ANCHOR_PATTERNS


def test_explicit_anchor_patterns(tmp_path):
    (tmp_path / "science.yaml").write_text(
        "name: demo\n"
        "prose_lint:\n"
        "  anchor_patterns:\n"
        "    - 'task:'\n"
        "    - 'doc/'\n"
    )
    config = load_project_config(tmp_path)
    assert config.prose_lint is not None
    assert config.prose_lint.anchor_patterns == ["task:", "doc/"]


def test_enabled_checks(tmp_path):
    (tmp_path / "science.yaml").write_text(
        "name: demo\n"
        "prose_lint:\n"
        "  enabled_checks:\n"
        "    - bare-author-year\n"
    )
    config = load_project_config(tmp_path)
    assert config.prose_lint.enabled_checks == ["bare-author-year"]
```

- [ ] **Step 2: Run config tests to verify failure**

Run:

```bash
cd science && uv run pytest tests/test_project_config_prose_lint.py -v
```

Expected: FAIL — `ProseLintConfig`, `DEFAULT_ANCHOR_PATTERNS` not exported.

- [ ] **Step 3: Add `ProseLintConfig` to project_config.py**

Append to `science/src/science_tool/project_config.py` (above `class ProjectConfig`):

```python
DEFAULT_ANCHOR_PATTERNS: list[str] = [
    "task:",
    "pipeline/",
    r"\[@",
    "data/",
    "scripts/",
]


class ProseLintConfig(BaseModel):
    """Configuration for `science prose lint`."""

    model_config = ConfigDict(extra="forbid")

    enabled_checks: list[str] | None = None
    anchor_patterns: list[str] = Field(default_factory=lambda: list(DEFAULT_ANCHOR_PATTERNS))
```

Then add the field to `ProjectConfig` (after `peers`):

```python
    prose_lint: ProseLintConfig | None = None
```

- [ ] **Step 4: Verify config tests pass**

Run:

```bash
cd science && uv run pytest tests/test_project_config_prose_lint.py -v
```

Expected: PASS (3 tests).

- [ ] **Step 5: Write failing numeric-anchor detector tests**

Append to `science/tests/test_prose_lint.py`:

```python
from science_tool.prose_lint import detect_numeric_anchor


class TestNumericAnchor:
    def test_flags_unanchored_numeric_claim(self, tmp_path):
        path = _write(tmp_path, "The correlation rho = 0.168 was observed.\n")
        issues = detect_numeric_anchor(path)
        assert len(issues) == 1
        assert issues[0].check == "numeric-anchor"
        assert issues[0].severity == "info"
        assert "0.168" in issues[0].message

    def test_no_flag_when_anchored_with_task(self, tmp_path):
        path = _write(tmp_path, "We measured rho = 0.168 (task:t050).\n")
        assert detect_numeric_anchor(path) == []

    def test_no_flag_when_anchored_with_pipeline(self, tmp_path):
        path = _write(tmp_path, "Result: 30% accuracy from pipeline/t099/results.\n")
        assert detect_numeric_anchor(path) == []

    def test_no_flag_when_anchored_with_bibtex(self, tmp_path):
        path = _write(tmp_path, "Reported as 0.168 in the paper [@brunton2022].\n")
        assert detect_numeric_anchor(path) == []

    def test_no_flag_in_section_header(self, tmp_path):
        path = _write(tmp_path, "## 3.2 Methods\n\nText.\n")
        assert detect_numeric_anchor(path) == []

    def test_no_flag_on_year_alone(self, tmp_path):
        # Years are too noisy to flag as bare numerics.
        path = _write(tmp_path, "In 2022, the model was published.\n")
        assert detect_numeric_anchor(path) == []

    def test_flags_percent_claim(self, tmp_path):
        path = _write(tmp_path, "Improvement of 47% was observed.\n")
        issues = detect_numeric_anchor(path)
        assert len(issues) == 1

    def test_custom_anchor_patterns(self, tmp_path):
        # Caller passes in extended anchors; "doc/" should now count.
        path = _write(tmp_path, "Result rho = 0.168 (see doc/notes/foo.md).\n")
        issues = detect_numeric_anchor(path, anchor_patterns=["task:", "doc/"])
        assert issues == []
```

- [ ] **Step 6: Run numeric-anchor tests to verify failure**

Run:

```bash
cd science && uv run pytest tests/test_prose_lint.py::TestNumericAnchor -v
```

Expected: FAIL with `ImportError`.

- [ ] **Step 7: Implement the detector**

Append to `science/src/science_tool/prose_lint.py`:

```python
# Numeric claim: float, integer with %, ratio. Excludes bare integers <100
# (too noisy) and bare 4-digit years (handled separately below).
_NUMERIC_CLAIM_RE = re.compile(
    r"(?<![0-9.])"
    r"(?:[0-9]+\.[0-9]+|[0-9]{2,}%|[0-9]{2,}/[0-9]+|[0-9]{3,})"
    r"(?![0-9.])"
)
# Standalone 4-digit years (1900-2099) — never claims, always exclude.
_BARE_YEAR_RE = re.compile(r"^(?:19\d{2}|20\d{2})$")
# Section/list header: leading `#`, `-`, `*`, or `1.` style numbering.
_HEADER_OR_LIST_RE = re.compile(r"^\s*(?:#+|[-*]|\d+\.)\s")


def detect_numeric_anchor(
    path: Path,
    *,
    strict: bool = False,
    anchor_patterns: list[str] | None = None,
) -> list[LintIssue]:
    """Flag numeric claims in body prose without an anchor token in the same paragraph.

    `anchor_patterns` is a list of regex fragments. A claim is considered
    anchored if any pattern matches anywhere in the same paragraph (lines
    separated by blank lines).
    """
    if anchor_patterns is None:
        from science_tool.project_config import DEFAULT_ANCHOR_PATTERNS  # noqa: PLC0415

        anchor_patterns = list(DEFAULT_ANCHOR_PATTERNS)
    anchor_re = re.compile("|".join(anchor_patterns)) if anchor_patterns else None

    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    _, body_start = parse_frontmatter(path)
    lines = text.splitlines()
    issues: list[LintIssue] = []
    in_fence = False
    # Pre-compute paragraph boundaries (1-based line index → paragraph index).
    paragraph_id_per_line: list[int] = [0] * (len(lines) + 1)
    para_id = 0
    for idx, line in enumerate(lines, start=1):
        if not line.strip():
            para_id += 1
        paragraph_id_per_line[idx] = para_id
    paragraph_text: dict[int, str] = {}
    for idx, line in enumerate(lines, start=1):
        pid = paragraph_id_per_line[idx]
        paragraph_text[pid] = paragraph_text.get(pid, "") + line + "\n"

    for lineno_zero, raw_line in enumerate(lines):
        lineno = lineno_zero + 1
        if lineno < body_start:
            continue
        if is_fence_line(raw_line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if _HEADER_OR_LIST_RE.match(raw_line):
            continue
        line = strip_inline_code(raw_line)
        for match in _NUMERIC_CLAIM_RE.finditer(line):
            value = match.group(0)
            if _BARE_YEAR_RE.match(value):
                continue  # standalone year, not a claim
            paragraph = paragraph_text[paragraph_id_per_line[lineno]]
            if anchor_re and anchor_re.search(paragraph):
                continue
            issues.append(
                LintIssue(
                    file=path,
                    line=lineno,
                    col=match.start() + 1,
                    check="numeric-anchor",
                    severity=severity_for("numeric-anchor", strict=strict),
                    message=f"numeric claim '{value}' has no anchor in this paragraph",
                )
            )
    return issues
```

- [ ] **Step 8: Run all prose_lint tests to verify they pass**

Run:

```bash
cd science && uv run pytest tests/test_prose_lint.py tests/test_project_config_prose_lint.py -v
```

Expected: PASS (all tests across the four detectors).

- [ ] **Step 9: Commit**

```bash
git add science/src/science_tool/project_config.py science/src/science_tool/prose_lint.py science/tests/test_prose_lint.py science/tests/test_project_config_prose_lint.py
git commit -m "feat(prose_lint): add numeric-anchor detector + ProseLintConfig"
```

---

## Task 6: scan_root orchestrator

**Files:**
- Modify: `science/src/science_tool/prose_lint.py`
- Modify: `science/tests/test_prose_lint.py`

- [ ] **Step 1: Write failing orchestrator tests**

Append to `science/tests/test_prose_lint.py`:

```python
from science_tool.prose_lint import scan_root


class TestScanRoot:
    def test_scans_doc_tree_with_all_checks(self, tmp_path):
        (tmp_path / "doc").mkdir()
        (tmp_path / "doc" / "a.md").write_text(
            "# A\n\nAs Brunton 2022 showed, the result rho = 0.168 holds.\n"
        )
        (tmp_path / "doc" / "b.md").write_text(
            "---\nrelated:\n  - task:t050\n---\n# B\n\nNo mention.\n"
        )
        result = scan_root(tmp_path)
        assert result["counts"]["bare-author-year"] == 1
        assert result["counts"]["numeric-anchor"] >= 1
        assert result["counts"]["frontmatter-inline-gap"] == 1
        assert all(isinstance(h, LintIssue) for h in result["hits"])

    def test_filters_by_check(self, tmp_path):
        (tmp_path / "doc").mkdir()
        (tmp_path / "doc" / "a.md").write_text(
            "# A\n\nBrunton 2022 and rho = 0.168.\n"
        )
        result = scan_root(tmp_path, checks=["bare-author-year"])
        assert "numeric-anchor" not in result["counts"]
        assert result["counts"]["bare-author-year"] == 1

    def test_skips_non_markdown(self, tmp_path):
        (tmp_path / "doc").mkdir()
        (tmp_path / "doc" / "a.txt").write_text("Brunton 2022\n")
        result = scan_root(tmp_path)
        assert result["counts"] == {}
```

- [ ] **Step 2: Run to verify failure**

Run:

```bash
cd science && uv run pytest tests/test_prose_lint.py::TestScanRoot -v
```

Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement scan_root**

Append to `science/src/science_tool/prose_lint.py`:

```python
from typing import Callable

_DETECTORS: dict[str, Callable[..., list[LintIssue]]] = {
    "bare-author-year": detect_bare_author_year,
    "short-form-ids": detect_short_form_ids,
    "frontmatter-inline-gap": detect_frontmatter_inline_gaps,
    "numeric-anchor": detect_numeric_anchor,
}
_SCAN_DIRS = ("doc", "specs")
_SCAN_ROOT_FILES = ("README.md", "AGENTS.md", "CLAUDE.md", "RESEARCH_PLAN.md")
_SKIP_DIRS = {".git", ".venv", "node_modules", "data", "__pycache__", "templates"}


def _collect_markdown_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for name in _SCAN_DIRS:
        sub = root / name
        if not sub.is_dir():
            continue
        for path in sub.rglob("*.md"):
            if any(part in _SKIP_DIRS for part in path.parts):
                continue
            files.append(path)
    for name in _SCAN_ROOT_FILES:
        candidate = root / name
        if candidate.is_file():
            files.append(candidate)
    return sorted(files)


def scan_root(
    root: Path,
    *,
    checks: list[str] | None = None,
    strict: bool = False,
    anchor_patterns: list[str] | None = None,
) -> dict:
    """Scan a project tree and return ``{"counts": {check: N}, "hits": [...]}``."""
    selected = checks or list(CHECKS)
    unknown = [c for c in selected if c not in _DETECTORS]
    if unknown:
        raise ValueError(f"unknown checks: {unknown!r}; known: {list(CHECKS)}")
    files = _collect_markdown_files(root)
    hits: list[LintIssue] = []
    for path in files:
        for check in selected:
            detector = _DETECTORS[check]
            if check == "numeric-anchor":
                hits.extend(detector(path, strict=strict, anchor_patterns=anchor_patterns))
            else:
                hits.extend(detector(path, strict=strict))
    counts: dict[str, int] = {}
    for hit in hits:
        counts[hit.check] = counts.get(hit.check, 0) + 1
    return {"counts": counts, "hits": hits}
```

- [ ] **Step 4: Run to verify pass**

Run:

```bash
cd science && uv run pytest tests/test_prose_lint.py::TestScanRoot -v
```

Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/prose_lint.py science/tests/test_prose_lint.py
git commit -m "feat(prose_lint): add scan_root orchestrator"
```

---

## Task 7: CLI group registration

**Files:**
- Create: `science/src/science_tool/prose_lint_cli.py`
- Create: `science/tests/test_prose_lint_cli.py`
- Modify: `science/src/science_tool/cli.py`

- [ ] **Step 1: Write failing CLI tests**

Create `science/tests/test_prose_lint_cli.py`:

```python
import json
from pathlib import Path

from click.testing import CliRunner

from science_tool.prose_lint_cli import prose_group


def _write_project(tmp_path: Path, *, science_yaml: str = "name: demo\n") -> Path:
    (tmp_path / "science.yaml").write_text(science_yaml)
    (tmp_path / "doc").mkdir()
    return tmp_path


def test_lint_json_output(tmp_path):
    root = _write_project(tmp_path)
    (root / "doc" / "a.md").write_text("# A\n\nBrunton 2022 showed it.\n")
    runner = CliRunner()
    result = runner.invoke(
        prose_group, ["lint", "--root", str(root), "--format", "json"]
    )
    assert result.exit_code == 0  # warn-level by default doesn't fail
    payload = json.loads(result.output)
    assert payload["counts"]["bare-author-year"] == 1
    assert len(payload["hits"]) == 1
    assert payload["hits"][0]["check"] == "bare-author-year"


def test_lint_table_output(tmp_path):
    root = _write_project(tmp_path)
    (root / "doc" / "a.md").write_text("# A\n\nBrunton 2022 showed it.\n")
    runner = CliRunner()
    result = runner.invoke(prose_group, ["lint", "--root", str(root)])
    assert result.exit_code == 0
    assert "bare-author-year" in result.output
    assert "Brunton 2022" in result.output


def test_lint_filters_by_check(tmp_path):
    root = _write_project(tmp_path)
    (root / "doc" / "a.md").write_text(
        "# A\n\nBrunton 2022 showed rho = 0.168.\n"
    )
    runner = CliRunner()
    result = runner.invoke(
        prose_group,
        ["lint", "--root", str(root), "--check", "bare-author-year", "--format", "json"],
    )
    payload = json.loads(result.output)
    assert "numeric-anchor" not in payload["counts"]
    assert payload["counts"]["bare-author-year"] == 1


def test_lint_strict_exits_nonzero(tmp_path):
    root = _write_project(tmp_path)
    (root / "doc" / "a.md").write_text("# A\n\nBrunton 2022 showed it.\n")
    runner = CliRunner()
    result = runner.invoke(prose_group, ["lint", "--root", str(root), "--strict"])
    assert result.exit_code == 1


def test_lint_warn_severity_does_not_exit_nonzero_without_strict(tmp_path):
    # Mirrors `science markers scan` behavior: warn issues are reported but
    # don't fail the run unless --strict is set.
    root = _write_project(tmp_path)
    (root / "doc" / "a.md").write_text("# A\n\nBrunton 2022 showed it.\n")
    runner = CliRunner()
    result = runner.invoke(prose_group, ["lint", "--root", str(root)])
    assert result.exit_code == 0


def test_lint_uses_project_anchor_patterns(tmp_path):
    root = _write_project(
        tmp_path,
        science_yaml=(
            "name: demo\n"
            "prose_lint:\n"
            "  anchor_patterns:\n"
            "    - 'doc/'\n"
        ),
    )
    (root / "doc" / "a.md").write_text(
        "# A\n\nResult rho = 0.168 (see doc/notes/foo.md).\n"
    )
    runner = CliRunner()
    result = runner.invoke(
        prose_group, ["lint", "--root", str(root), "--format", "json"]
    )
    payload = json.loads(result.output)
    assert "numeric-anchor" not in payload["counts"]
```

- [ ] **Step 2: Run to verify failure**

Run:

```bash
cd science && uv run pytest tests/test_prose_lint_cli.py -v
```

Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement the CLI**

Create `science/src/science_tool/prose_lint_cli.py`:

```python
"""CLI for `science prose lint`. See docs/conventions/prose-lints.md."""

from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

import click

from science_tool.project_config import DEFAULT_ANCHOR_PATTERNS, load_project_config
from science_tool.prose_lint import CHECKS, scan_root


@click.group("prose")
def prose_group() -> None:
    """Prose-quality lints (bare author-year, short-form IDs, etc.)."""


@prose_group.command("lint")
@click.option("--root", type=click.Path(exists=True, file_okay=False, path_type=Path), default=Path("."))
@click.option("--format", "fmt", type=click.Choice(["table", "json"]), default="table")
@click.option(
    "--check",
    "checks",
    type=click.Choice(list(CHECKS)),
    multiple=True,
    help="Run only the named check(s). Defaults to all.",
)
@click.option("--strict", is_flag=True, help="Promote info-severity issues to warn; exit non-zero on any issue.")
def lint_cmd(root: Path, fmt: str, checks: tuple[str, ...], strict: bool) -> None:
    """Run prose-quality lints across the project's doc/ and specs/ trees."""
    selected = list(checks) if checks else None
    anchor_patterns = list(DEFAULT_ANCHOR_PATTERNS)
    enabled_from_config: list[str] | None = None
    science_yaml = root / "science.yaml"
    if science_yaml.is_file():
        config = load_project_config(root)
        if config.prose_lint is not None:
            anchor_patterns = config.prose_lint.anchor_patterns
            enabled_from_config = config.prose_lint.enabled_checks
    if selected is None and enabled_from_config:
        selected = enabled_from_config

    result = scan_root(
        root,
        checks=selected,
        strict=strict,
        anchor_patterns=anchor_patterns,
    )

    if fmt == "json":
        payload = {
            "counts": result["counts"],
            "hits": [
                {**asdict(h), "file": str(h.file.relative_to(root))}
                for h in result["hits"]
            ],
        }
        click.echo(json.dumps(payload, indent=2))
    else:
        _render_table(result, root)

    # Mirrors `science markers scan`: only --strict + issues fails the run.
    if strict and result["hits"]:
        sys.exit(1)


def _render_table(result: dict, root: Path) -> None:
    if not result["hits"]:
        click.echo("prose lint: no issues found.")
        return
    by_file: dict[Path, list] = {}
    for hit in result["hits"]:
        by_file.setdefault(hit.file, []).append(hit)
    for path in sorted(by_file):
        rel = path.relative_to(root)
        click.echo(f"\n{rel}")
        for hit in sorted(by_file[path], key=lambda h: (h.line, h.col)):
            tag = f"({hit.severity})"
            click.echo(f"  {hit.line}:{hit.col} [{hit.check}] {tag} {hit.message}")
    click.echo("\nSummary:")
    for check, count in sorted(result["counts"].items()):
        click.echo(f"  {check}: {count}")
```

- [ ] **Step 4: Register the group in cli.py**

Add the import near the existing `from science_tool.markers_cli import markers_group` line:

```python
from science_tool.prose_lint_cli import prose_group
```

Add the registration alongside the existing `main.add_command(markers_group)`:

```python
main.add_command(prose_group)
```

- [ ] **Step 5: Run CLI tests to verify they pass**

Run:

```bash
cd science && uv run pytest tests/test_prose_lint_cli.py -v
```

Expected: PASS (5 tests).

- [ ] **Step 6: Verify the CLI works end-to-end**

Run:

```bash
uv run --project science science prose --help
uv run --project science science prose lint --help
```

Expected: help text appears for both, `lint` shows `--root`, `--format`, `--check`, `--strict`.

- [ ] **Step 7: Commit**

```bash
git add science/src/science_tool/prose_lint_cli.py science/src/science_tool/cli.py science/tests/test_prose_lint_cli.py
git commit -m "feat(prose_lint): add CLI group with lint subcommand"
```

---

## Task 8: validate.sh integration + managed-artifact bump

**Files:**
- Modify: `science/src/science_tool/project_artifacts/data/validate.sh`
- Modify: `science/src/science_tool/project_artifacts/registry.yaml`

- [ ] **Step 1: Add section 9 to validate.sh**

Find the existing section 8 (`science markers scan`) in `validate.sh` and add an analogous section 9 immediately after it:

```bash
# === SECTION 9: Prose lints ===
echo "[9/N] Prose lints..."
PROSE_JSON=$(science prose lint --root "$PROJECT_ROOT" --format json 2>/dev/null || echo '{"counts":{},"hits":[]}')
PROSE_COUNTS=$(printf '%s' "$PROSE_JSON" | python3 -c "
import json, sys
data = json.load(sys.stdin)
counts = data.get('counts', {})
for check, count in sorted(counts.items()):
    print(f'{check}\t{count}')
")
if [ -n "$PROSE_COUNTS" ]; then
    while IFS=$'\t' read -r check count; do
        if [ "$STRICT" = "1" ]; then
            warn "[$check] $count occurrences"
        else
            # Severity-aware: only warn on warn-level checks (bare-author-year, short-form-ids).
            case "$check" in
                bare-author-year|short-form-ids)
                    warn "[$check] $count occurrences"
                    ;;
                *)
                    info "[$check] $count occurrences (use --strict to promote)"
                    ;;
            esac
        fi
    done <<< "$PROSE_COUNTS"
else
    echo "  no prose-lint issues."
fi
```

(Use the exact `info`/`warn` helper-call style already used by section 8 — adjust if the helper names differ in the actual file.)

Also bump the section count `N` in section header echoes to reflect the new total.

- [ ] **Step 2: Update version in shebang_comment header**

Edit lines 3 and 4 of `validate.sh`:

```
# science-managed-version: 2026.05.10.1
# science-managed-source-sha256: <will be computed in step 4>
```

- [ ] **Step 3: Compute new body hash**

Run:

```bash
uv run --project science python -c "
from pathlib import Path
from science_tool.project_artifacts.hashing import body_hash
from science_tool.project_artifacts.registry_schema import HeaderProtocol, HeaderKind
p = Path('science/src/science_tool/project_artifacts/data/validate.sh')
proto = HeaderProtocol(kind=HeaderKind.SHEBANG_COMMENT, comment_prefix='#')
print(body_hash(p.read_bytes(), proto))
"
```

Save the hex output as `<NEW_HASH>`.

- [ ] **Step 4: Update line 4 of validate.sh with the computed hash**

Replace the `<will be computed in step 4>` placeholder with `<NEW_HASH>`.

- [ ] **Step 5: Update registry.yaml**

Edit `science/src/science_tool/project_artifacts/registry.yaml`:

- Change `version: '2026.05.09.2'` → `version: '2026.05.10.1'`.
- Change `current_hash: 6f8cf6488...` → `current_hash: <NEW_HASH>`.
- Prepend to `previous_hashes`:
  ```yaml
      - version: '2026.05.09.2'
        hash: 6f8cf6488014484d2d93f57654d9ff6500d8638bd122c12864da26a4e05608ca
  ```
- Append to `migrations`:
  ```yaml
        - from: '2026.05.09.2'
          to: '2026.05.10.1'
          kind: byte_replace
          summary: 'Add Section 9: prose lints (bare-author-year, short-form-ids, frontmatter-inline-gap, numeric-anchor) via `science prose lint`.'
          steps: []
  ```
- Append to `changelog`:
  ```yaml
        '2026.05.10.1': 'Add Section 9 prose lints powered by `science prose lint --format json`. Default emits warn for bare-author-year and short-form-ids; info for frontmatter-inline-gap and numeric-anchor (promoted under --strict).'
  ```

- [ ] **Step 6: Verify the artifact roundtrip**

Run:

```bash
uv run --project science python -c "
from pathlib import Path
from science_tool.project_artifacts.hashing import body_hash
from science_tool.project_artifacts.registry_schema import HeaderProtocol, HeaderKind
p = Path('science/src/science_tool/project_artifacts/data/validate.sh')
proto = HeaderProtocol(kind=HeaderKind.SHEBANG_COMMENT, comment_prefix='#')
print('body hash:', body_hash(p.read_bytes(), proto))
"
```

Expected: prints the same `<NEW_HASH>` written into registry.yaml's `current_hash`.

- [ ] **Step 7: Run validate.sh against multiple-myeloma to verify section 9 fires**

Run:

```bash
cd ~/d/cancer/cancer-types/multiple-myeloma
bash ~/d/science/science/src/science_tool/project_artifacts/data/validate.sh 2>&1 | grep -A20 "9/"
```

Expected: section 9 appears with non-zero counts (MM has well-known short-form IDs and bare author-year mentions).

- [ ] **Step 8: Commit**

```bash
git add science/src/science_tool/project_artifacts/data/validate.sh science/src/science_tool/project_artifacts/registry.yaml
git commit -m "feat(validate): wire prose lints into validate.sh as section 9 (v2026.05.10.1)"
```

---

## Task 9: User-facing docs + cross-link

**Files:**
- Create: `docs/conventions/prose-lints.md`
- Modify: `docs/conventions/annotation-tokens.md`

- [ ] **Step 1: Create the prose-lints convention doc**

Create `docs/conventions/prose-lints.md` with content (note the outer fence below uses `~~~` so the inner ` ``` ` blocks render correctly — when copying to the actual file, the outer `~~~markdown` and trailing `~~~` are NOT part of the file content):

~~~markdown
# Prose Lints

`science prose lint` detects four classes of prose-quality issue surfaced
by the natural-systems t466 citation-audit pilot. Each lint is mechanically
detectable; LLM-judgment claims (e.g., "field-state consensus claims") are
handled by the [annotation-token vocabulary](annotation-tokens.md), not by these lints.

## Lints

| Check (`--check=`)        | Detects                                                                                                              | Default severity |
|---------------------------|----------------------------------------------------------------------------------------------------------------------|------------------|
| `bare-author-year`        | `<Capitalized> <Year>` mentions (e.g., `Brunton 2022`) without an adjacent `[@key]` BibTeX-style anchor              | `warn`           |
| `short-form-ids`          | Bare `Q1`, `t088`, `q54` etc. — short forms of canonical entity refs                                                 | `warn`           |
| `frontmatter-inline-gap`  | Frontmatter `related:` entries that never appear in the document body                                                | `info`           |
| `numeric-anchor`          | Numeric claims (`ρ = 0.168`, `30%`, `n = 184`) without an anchor token (`task:`, `pipeline/`, `[@…]`) in the same paragraph | `info` |

`--strict` promotes all `info` issues to `warn` and exits non-zero on any issue.

## Lexical scope

All four lints respect the same scope rules as `science markers scan`:

- Skips YAML frontmatter.
- Skips fenced code blocks (` ``` `).
- Skips inline code (`` ` ``-wrapped).
- Skips lines starting with `#` (markdown headers), `-`/`*` (lists), or `1.` (ordered list) for the numeric-anchor check.
- Skips task-list headers of the shape `## [t088] Title` for the short-form-ids check.

## Project config

`science.yaml` may include an optional `prose_lint:` block:

```yaml
prose_lint:
  enabled_checks:
    - bare-author-year
    - short-form-ids
    - frontmatter-inline-gap
    - numeric-anchor
  anchor_patterns:
    - "task:"
    - "pipeline/"
    - "\\[@"
    - "data/"
    - "scripts/"
```

Defaults: all four checks enabled; `anchor_patterns` defaults to `["task:", "pipeline/", "\\[@", "data/", "scripts/"]`.

## Tooling

- `science prose lint --root . --format table` — run all lints, render to terminal.
- `science prose lint --root . --format json` — JSON output (used by `validate.sh`).
- `science prose lint --check bare-author-year` — run a single lint.
- `science prose lint --strict` — promote info → warn, exit 1 on any issue.

## Validate.sh integration

`validate.sh` runs `science prose lint --format json` as Section 9 and emits per-check counts in its summary. Default behavior reports info-severity issues without failing; `validate.sh --strict` (or `science prose lint --strict`) promotes them.

## Origin

These lints were extracted from the natural-systems citation-audit pilot
(t466) which identified six recurring patterns across audited prose. The
four mechanically-detectable patterns are implemented here. The two
LLM-judgment patterns ("field-state consensus claims unsupported" and the
broader "load-bearing claim has no anchor") are handled by the
[annotation-token vocabulary](annotation-tokens.md): an LLM auditor or
human writer marks them with `[SPECULATION]` or `[MISSING_CITATION]`, and
`science markers scan` counts them.
~~~

- [ ] **Step 2: Cross-link from annotation-tokens.md**

Open `docs/conventions/annotation-tokens.md`. Append a new section at the end:

~~~markdown
## See also

- [Prose lints](prose-lints.md) — mechanically-detectable prose issues
  (bare author-year, short-form IDs, frontmatter-inline gaps, numeric
  anchors). Lints surface candidates; the four-token vocabulary is the
  authoring output for claims that need LLM/human judgment.
~~~

- [ ] **Step 3: Commit**

```bash
git add docs/conventions/prose-lints.md docs/conventions/annotation-tokens.md
git commit -m "docs: add prose-lints convention doc + cross-link annotation-tokens"
```

---

## Task 10: Baseline run on natural-systems and multiple-myeloma

**Files:**
- Create: `docs/audits/2026-05-10-prose-lint-baselines.md`

- [ ] **Step 1: Capture baseline counts on natural-systems**

Run:

```bash
uv run --project science science prose lint --root ~/d/natural-systems --format json > /tmp/ns-prose.json
python3 -c "import json; d=json.load(open('/tmp/ns-prose.json')); print('natural-systems counts:'); [print(f'  {k}: {v}') for k,v in sorted(d['counts'].items())]"
```

Record the output.

- [ ] **Step 2: Capture baseline counts on multiple-myeloma**

Run:

```bash
uv run --project science science prose lint --root ~/d/cancer/cancer-types/multiple-myeloma --format json > /tmp/mm-prose.json
python3 -c "import json; d=json.load(open('/tmp/mm-prose.json')); print('multiple-myeloma counts:'); [print(f'  {k}: {v}') for k,v in sorted(d['counts'].items())]"
```

Record the output.

- [ ] **Step 3: Sample top per-file offenders for each project**

For each project, run:

```bash
python3 -c "
import json
d = json.load(open('/tmp/ns-prose.json'))
by_file = {}
for h in d['hits']:
    by_file.setdefault(h['file'], 0)
    by_file[h['file']] += 1
for f, c in sorted(by_file.items(), key=lambda x: -x[1])[:10]:
    print(f'{c:4d}  {f}')
"
```

Repeat with `/tmp/mm-prose.json`.

- [ ] **Step 4: Write the baseline audit doc**

Create `docs/audits/2026-05-10-prose-lint-baselines.md` containing:

- Date and commit SHA.
- Summary table: project × check → count.
- Top 10 per-file offenders for each project.
- One-sentence interpretation per project (e.g., "natural-systems chapter 20 dominates bare-author-year because it imports textbook-style claims wholesale").
- Pointer to the citation-audit-pilot interpretation (`~/d/natural-systems/doc/interpretations/2026-05-06-citation-audit-pilot.md`) and to MM's marker-triage audit (`~/d/cancer/cancer-types/multiple-myeloma/doc/audits/2026-05-09-unverified-marker-triage.md`).

- [ ] **Step 5: Commit**

```bash
git add docs/audits/2026-05-10-prose-lint-baselines.md
git commit -m "docs(audits): capture prose-lint baselines for natural-systems and multiple-myeloma"
```

---

## Out Of Scope For This Plan

- LLM-driven detection of gap D ("field-state consensus claims unsupported"). This requires the existing four-token vocabulary plus a separate auditor agent; not a regex-shaped problem.
- Citation-resolver migration: natural-systems's `scripts/audit-citations.ts` (t469) overlaps with `science refs check`. Generalizing body-text scanning into refs check is a worthwhile separate refactor but distinct from this lint group.
- Snakemake-driven 3-agent ensemble citation audit (natural-systems t468): project-specific cadence and output format.
- HUD/visualization (natural-systems t467): project-specific UI.
- Auto-fix mode for any of the four lints. Lints report; humans fix.

## Self-Review Notes

- Severity model mirrors `science markers scan`: warn-by-default for high-confidence patterns, info-by-default for noisier ones, `--strict` promotes.
- All four detectors share the same lexical-scope rules already proven by the markers scanner (`markdown_utils` helpers).
- `numeric-anchor` is the only detector with project-config sensitivity. Default anchor list is conservative; projects with unusual layouts (e.g., `data/`-rooted artifacts) should add to it via `science.yaml`.
- The `_TASK_HEADING_RE` exemption in `short-form-ids` is intentional — `tasks/active.md` files use `## [t088] Title` as their canonical heading shape; treating that as a violation would generate hundreds of false positives.
- `frontmatter-inline-gap` reports at line 1 (file-level) rather than per-line because the violation is "this file does not mention X" — there's no specific line to point at.

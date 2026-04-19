# Manuscript + Paper Terminology Rename Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Normalize Science's literature vocabulary so `manuscript:<id>` means user's own publication-in-progress and `paper:<bibkey>` means external literature, and ship a one-shot migration tool that rewrites legacy `article:<bibkey>` → `paper:<bibkey>` across project markdown.

**Architecture:** Pure-function rewrite core in `science_tool/refs_migrate.py` with regex-based rules (scoped to YAML frontmatter for `id:`/`type:`, body-wide for the prefix word-boundary rule). A thin click group in `science_tool/refs_cli.py` wraps it with dry-run/apply/diff/git-clean-check UX. Template renames happen as two `git mv`s with frontmatter edits. Downstream consumers gain a small transition-window canonicalization helper that maps `article:<bibkey>` → `paper:<bibkey>` at comparison boundaries.

**Tech Stack:** Python 3.11+, click (existing CLI), pytest, difflib, pathlib, `re`. No new runtime dependencies.

**Spec:** `docs/specs/2026-04-19-manuscript-paper-rename-design.md`

---

## File Structure

### New files

- `science-tool/src/science_tool/refs_migrate.py` — pure-function rewrite core: per-file rewrite, per-project scan, counts + diffs.
- `science-tool/src/science_tool/refs_cli.py` — click `refs` group with the `migrate-paper` subcommand; registered by top-level `cli.py`.
- `science-tool/src/science_tool/big_picture/literature_prefix.py` — canonicalization helper: `canonical_paper_id(raw_id)` maps `article:<X>` → `paper:<X>`. Consumed by knowledge-gaps and any future external-lit consumer.
- `science-tool/tests/test_refs_migrate_paper.py` — unit tests for the rewrite core.
- `science-tool/tests/test_refs_migrate_cli.py` — integration tests for the CLI.
- `science-tool/tests/test_literature_prefix.py` — unit tests for the canonicalization helper.
- `science-tool/tests/fixtures/refs/legacy_project/` — fixture: a minimal project with `article:<X>` references across `doc/`, `specs/`, and `tasks/`.

### Modified files

- `templates/paper.md` → renamed to `templates/manuscript.md` (frontmatter `id:`/`type:` updated).
- `templates/paper-summary.md` → renamed to `templates/paper.md` (frontmatter `id:`/`type:` updated).
- `science-tool/src/science_tool/cli.py` — register `refs_cli.refs_group`; rewrite `"article"` user-facing strings.
- `commands/research-papers.md`, `commands/search-literature.md`, `commands/bias-audit.md`, `commands/compare-hypotheses.md`, `commands/next-steps.md`, `commands/research-topic.md` — update template path names and example IDs.
- `references/role-prompts/research-assistant.md`, `references/project-structure.md` — update example IDs.
- `docs/specs/2026-03-02-agent-capabilities-design.md` — update filename references.
- Any `templates/*.md` with `article:<X>` examples — rewrite to `paper:<X>` via the same migration tool.
- 9 test files with `article:` literals (triaged per §Python CLI Updates triage rule).

### Unchanged

- `science_tool/refs.py` — existing module; NOT turned into a package.
- `doc/papers/` and `doc/background/papers/` directory names.
- `cite:<bibkey>` prefix.

---

## Task 1: Scaffold `refs_migrate` module with canonical rewrite rules as constants

**Files:**
- Create: `science-tool/src/science_tool/refs_migrate.py`
- Test: `science-tool/tests/test_refs_migrate_paper.py`

- [ ] **Step 1: Write the failing test**

Create `science-tool/tests/test_refs_migrate_paper.py`:

```python
from __future__ import annotations

from science_tool.refs_migrate import ID_REWRITE_RULES, TYPE_REWRITE_RULES, PROSE_REWRITE_RULE


def test_id_rewrite_rules_cover_all_yaml_forms() -> None:
    patterns = {pat.pattern for pat, _ in ID_REWRITE_RULES}
    assert "id: article:" in patterns
    assert 'id: "article:' in patterns
    assert "- article:" in patterns
    assert "[article:" in patterns
    assert '"article:' in patterns
    assert "'article:" in patterns


def test_type_rewrite_rules_cover_all_quote_styles() -> None:
    patterns = {pat.pattern for pat, _ in TYPE_REWRITE_RULES}
    assert any("type: article" in p for p in patterns)
    assert any('type: "article"' in p for p in patterns)
    assert any("type: 'article'" in p for p in patterns)


def test_prose_rewrite_rule_uses_word_boundary() -> None:
    pat, _ = PROSE_REWRITE_RULE
    assert "\\b" in pat.pattern
    assert "article" in pat.pattern
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --frozen pytest science-tool/tests/test_refs_migrate_paper.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'science_tool.refs_migrate'`.

- [ ] **Step 3: Create the module with rewrite rules**

Create `science-tool/src/science_tool/refs_migrate.py`:

```python
"""Pure-function core for migrating legacy ``article:`` IDs to ``paper:``.

See docs/specs/2026-04-19-manuscript-paper-rename-design.md for the
canonical rewrite rules.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

# Entity-ID character class per the spec: [A-Za-z0-9_\-.]
_ENTITY_ID_CLASS = r"[A-Za-z0-9_\-.]"

# YAML-style rewrites for the `article:` prefix embedded in entity IDs.
ID_REWRITE_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"id: article:"), "id: paper:"),
    (re.compile(r'id: "article:'), 'id: "paper:'),
    (re.compile(r"- article:"), "- paper:"),
    (re.compile(r"\[article:"), "[paper:"),
    (re.compile(r'"article:'), '"paper:'),
    (re.compile(r"'article:"), "'paper:"),
]

# Frontmatter `type:` rewrites — must be applied ONLY to the top YAML block.
TYPE_REWRITE_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"^type: article\s*$", re.MULTILINE), "type: paper"),
    (re.compile(r'^type: "article"\s*$', re.MULTILINE), 'type: "paper"'),
    (re.compile(r"^type: 'article'\s*$", re.MULTILINE), "type: 'paper'"),
]

# Prose fallback: `article:<id>` anywhere in body/YAML values.
# Word boundary avoids rewriting `particle:` and similar substrings.
PROSE_REWRITE_RULE: tuple[re.Pattern[str], str] = (
    re.compile(rf"\barticle:(?={_ENTITY_ID_CLASS})"),
    "paper:",
)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --frozen pytest science-tool/tests/test_refs_migrate_paper.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add science-tool/src/science_tool/refs_migrate.py science-tool/tests/test_refs_migrate_paper.py
git commit -m "feat(refs_migrate): scaffold module with rewrite-rule constants"
```

---

## Task 2: Implement `rewrite_text` — apply all rules to a single string

**Files:**
- Modify: `science-tool/src/science_tool/refs_migrate.py`
- Test: `science-tool/tests/test_refs_migrate_paper.py`

- [ ] **Step 1: Write the failing tests**

Append to `science-tool/tests/test_refs_migrate_paper.py`:

```python
from science_tool.refs_migrate import rewrite_text


def test_migrate_rewrites_id_field() -> None:
    before = '---\nid: article:Smith2024\ntype: "article"\n---\n\n# Body\n'
    after, count = rewrite_text(before)
    assert "id: paper:Smith2024" in after
    assert 'type: "paper"' in after
    assert count >= 2


def test_migrate_rewrites_related_list_inline() -> None:
    before = "related: [article:Smith2024, article:Jones2023]\n"
    after, count = rewrite_text(before)
    assert after == "related: [paper:Smith2024, paper:Jones2023]\n"
    assert count == 2


def test_migrate_rewrites_related_list_multiline() -> None:
    before = "related:\n  - article:Smith2024\n  - article:Jones2023\n"
    after, count = rewrite_text(before)
    assert "- paper:Smith2024" in after
    assert "- paper:Jones2023" in after
    assert count == 2


def test_migrate_rewrites_prose_mentions() -> None:
    before = "See article:Smith2024 for the full argument.\n"
    after, count = rewrite_text(before)
    assert after == "See paper:Smith2024 for the full argument.\n"
    assert count == 1


def test_migrate_preserves_particle_substrings() -> None:
    before = "The particle:muon and particle-physics community.\n"
    after, count = rewrite_text(before)
    assert after == before
    assert count == 0


def test_migrate_preserves_cite_prefix() -> None:
    before = "source_refs: [cite:Smith2024]\n"
    after, count = rewrite_text(before)
    assert after == before
    assert count == 0


def test_migrate_idempotent() -> None:
    before = "id: article:Smith2024\n"
    once, _ = rewrite_text(before)
    twice, count = rewrite_text(once)
    assert twice == once
    assert count == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --frozen pytest science-tool/tests/test_refs_migrate_paper.py -v`
Expected: 7 new tests FAIL with `ImportError: cannot import name 'rewrite_text'`.

- [ ] **Step 3: Implement `rewrite_text`**

Append to `science-tool/src/science_tool/refs_migrate.py`:

```python
def rewrite_text(text: str) -> tuple[str, int]:
    """Apply all rewrite rules to ``text``; return (new_text, match_count).

    Rules are applied in this order:
    1. Frontmatter `type:` rewrites (MULTILINE regex; safe across the whole file
       because the pattern is anchored with `^type: article` which won't match
       prose).
    2. ID-field rewrites (literal prefix rewrites).
    3. Prose/word-boundary rewrite for any remaining `article:<X>` matches.

    Idempotent: re-running on already-migrated text returns the same text and
    a count of 0.
    """
    total = 0
    current = text

    for pattern, replacement in TYPE_REWRITE_RULES:
        current, n = pattern.subn(replacement, current)
        total += n

    for pattern, replacement in ID_REWRITE_RULES:
        current, n = pattern.subn(replacement, current)
        total += n

    pattern, replacement = PROSE_REWRITE_RULE
    current, n = pattern.subn(replacement, current)
    total += n

    return current, total
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --frozen pytest science-tool/tests/test_refs_migrate_paper.py -v`
Expected: PASS (all 10 tests).

- [ ] **Step 5: Commit**

```bash
git add science-tool/src/science_tool/refs_migrate.py science-tool/tests/test_refs_migrate_paper.py
git commit -m "feat(refs_migrate): implement rewrite_text with full rule set"
```

---

## Task 3: Build the legacy-project fixture

**Files:**
- Create: `science-tool/tests/fixtures/refs/legacy_project/doc/questions/q01-example.md`
- Create: `science-tool/tests/fixtures/refs/legacy_project/doc/papers/Smith2024.md`
- Create: `science-tool/tests/fixtures/refs/legacy_project/doc/topics/t01-example.md`
- Create: `science-tool/tests/fixtures/refs/legacy_project/doc/interpretations/i01-example.md`
- Create: `science-tool/tests/fixtures/refs/legacy_project/science.yaml`

- [ ] **Step 1: Write `q01-example.md`**

```markdown
---
id: "question:q01"
type: "question"
status: "open"
related:
  - article:Smith2024
  - article:Jones2023
source_refs:
  - cite:Smith2024
---

# Example question

See article:Smith2024 for background.
```

- [ ] **Step 2: Write `Smith2024.md`**

```markdown
---
id: "article:Smith2024"
type: "article"
title: "Example"
source_refs:
  - "cite:Smith2024"
related: []
---

# Smith (2024)

## Key Contribution

Example.
```

- [ ] **Step 3: Write `t01-example.md`**

```markdown
---
id: "topic:t01-example"
type: "topic"
related: [article:Smith2024]
source_refs: []
---

# Example topic
```

- [ ] **Step 4: Write `i01-example.md`**

```markdown
---
id: "interpretation:i01-example"
type: "interpretation"
related: []
---

# Interpretation

Discussion of article:Smith2024 with the particle:muon edge case mentioned to
ensure the word-boundary rule behaves.
```

- [ ] **Step 5: Write `science.yaml`**

```yaml
name: "legacy-project"
aspects:
  - hypothesis-testing
```

- [ ] **Step 6: Commit**

```bash
git add science-tool/tests/fixtures/refs/legacy_project
git commit -m "test(refs_migrate): add legacy_project fixture"
```

---

## Task 4: Implement `scan_project` — walk markdown files, compute rewrites

**Files:**
- Modify: `science-tool/src/science_tool/refs_migrate.py`
- Test: `science-tool/tests/test_refs_migrate_paper.py`

- [ ] **Step 1: Write the failing tests**

Append to `science-tool/tests/test_refs_migrate_paper.py`:

```python
from pathlib import Path

from science_tool.refs_migrate import FileRewrite, scan_project

FIXTURE = Path(__file__).parent / "fixtures" / "refs" / "legacy_project"


def test_scan_project_finds_all_rewrites() -> None:
    rewrites = scan_project(FIXTURE)
    assert len(rewrites) >= 4  # q01, Smith2024, t01, i01
    totals = {r.path.name: r.match_count for r in rewrites}
    assert totals["q01-example.md"] >= 3  # list items + prose
    assert totals["Smith2024.md"] >= 2    # id + type
    assert totals["t01-example.md"] >= 1  # inline-list
    assert totals["i01-example.md"] >= 1  # prose, NOT particle:muon


def test_scan_project_on_migrated_returns_empty() -> None:
    # Apply migration to an in-memory copy; re-scanning a migrated snapshot
    # would produce no rewrites. We verify by rewriting every file's text
    # and confirming the count is now 0.
    rewrites = scan_project(FIXTURE)
    for r in rewrites:
        _, n = __import__("science_tool.refs_migrate", fromlist=["rewrite_text"]).rewrite_text(r.new_text)
        assert n == 0, f"{r.path.name} not idempotent"


def test_scan_project_counts_are_accurate() -> None:
    rewrites = scan_project(FIXTURE)
    for r in rewrites:
        assert r.new_text != r.original_text
        assert r.match_count > 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --frozen pytest science-tool/tests/test_refs_migrate_paper.py -v`
Expected: 3 new tests FAIL with `ImportError: cannot import name 'scan_project'`.

- [ ] **Step 3: Implement `scan_project` and `FileRewrite`**

Append to `science-tool/src/science_tool/refs_migrate.py`:

```python
# Directories to scan, relative to project root. Matches the conventions used
# by `science_tool.refs.check_refs` and the spec's "canonical markdown roots".
_SCAN_ROOTS: tuple[str, ...] = ("doc", "specs", "tasks", "core", "knowledge")
_TOP_LEVEL_MARKDOWN: tuple[str, ...] = ("RESEARCH_PLAN.md", "README.md")


@dataclass(frozen=True)
class FileRewrite:
    path: Path
    original_text: str
    new_text: str
    match_count: int


def scan_project(project_root: Path) -> list[FileRewrite]:
    """Walk ``project_root``; return pending rewrites for markdown files.

    Returns an empty list if the project has no legacy ``article:`` references.
    Does NOT write anything — callers apply the rewrites themselves via
    :func:`apply_rewrites`.
    """
    results: list[FileRewrite] = []
    for md_path in _iter_markdown_files(project_root):
        try:
            text = md_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            # Non-UTF-8 files: skip with a logged warning. Spec §Open Decisions
            # documents this behavior.
            continue
        new_text, count = rewrite_text(text)
        if count > 0:
            results.append(FileRewrite(md_path, text, new_text, count))
    return sorted(results, key=lambda r: r.path.as_posix())


def _iter_markdown_files(project_root: Path):
    for rel in _SCAN_ROOTS:
        root = project_root / rel
        if not root.is_dir():
            continue
        yield from sorted(root.rglob("*.md"))
    for name in _TOP_LEVEL_MARKDOWN:
        path = project_root / name
        if path.is_file():
            yield path
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --frozen pytest science-tool/tests/test_refs_migrate_paper.py -v`
Expected: PASS (all 13 tests).

- [ ] **Step 5: Commit**

```bash
git add science-tool/src/science_tool/refs_migrate.py science-tool/tests/test_refs_migrate_paper.py
git commit -m "feat(refs_migrate): add scan_project walker"
```

---

## Task 5: Implement `apply_rewrites` — atomic per-file write

**Files:**
- Modify: `science-tool/src/science_tool/refs_migrate.py`
- Test: `science-tool/tests/test_refs_migrate_paper.py`

- [ ] **Step 1: Write the failing test**

Append to `science-tool/tests/test_refs_migrate_paper.py`:

```python
def test_apply_rewrites_writes_files(tmp_path: Path) -> None:
    # Copy fixture into tmp_path so the test doesn't mutate the real fixture.
    import shutil
    shutil.copytree(FIXTURE, tmp_path / "legacy_project")
    project = tmp_path / "legacy_project"

    from science_tool.refs_migrate import apply_rewrites
    rewrites = scan_project(project)
    apply_rewrites(rewrites)

    # Verify on-disk text is the new text.
    for r in rewrites:
        assert r.path.read_text(encoding="utf-8") == r.new_text

    # Re-scan: should produce 0 rewrites.
    assert scan_project(project) == []


def test_apply_rewrites_preserves_other_files(tmp_path: Path) -> None:
    import shutil
    shutil.copytree(FIXTURE, tmp_path / "legacy_project")
    project = tmp_path / "legacy_project"
    science_yaml_before = (project / "science.yaml").read_text()

    from science_tool.refs_migrate import apply_rewrites
    apply_rewrites(scan_project(project))

    assert (project / "science.yaml").read_text() == science_yaml_before
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --frozen pytest science-tool/tests/test_refs_migrate_paper.py -v`
Expected: 2 new tests FAIL with `ImportError: cannot import name 'apply_rewrites'`.

- [ ] **Step 3: Implement `apply_rewrites`**

Append to `science-tool/src/science_tool/refs_migrate.py`:

```python
import os
import tempfile


def apply_rewrites(rewrites: list[FileRewrite]) -> None:
    """Apply each rewrite to disk using atomic temp-file + rename.

    Per the spec §Open Decisions, per-file writes are atomic but the overall
    migration is not transactional. Reruns are idempotent.
    """
    for rewrite in rewrites:
        _atomic_write(rewrite.path, rewrite.new_text)


def _atomic_write(path: Path, text: str) -> None:
    directory = path.parent
    fd, tmp_name = tempfile.mkstemp(prefix=".migrate-", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
        os.replace(tmp_name, path)
    except Exception:
        Path(tmp_name).unlink(missing_ok=True)
        raise
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --frozen pytest science-tool/tests/test_refs_migrate_paper.py -v`
Expected: PASS (all 15 tests).

- [ ] **Step 5: Commit**

```bash
git add science-tool/src/science_tool/refs_migrate.py science-tool/tests/test_refs_migrate_paper.py
git commit -m "feat(refs_migrate): add apply_rewrites atomic writer"
```

---

## Task 6: Add unified-diff emission helper

**Files:**
- Modify: `science-tool/src/science_tool/refs_migrate.py`
- Test: `science-tool/tests/test_refs_migrate_paper.py`

- [ ] **Step 1: Write the failing test**

Append to `science-tool/tests/test_refs_migrate_paper.py`:

```python
def test_render_diff_emits_unified_diff() -> None:
    from science_tool.refs_migrate import FileRewrite, render_diff
    rewrite = FileRewrite(
        path=Path("doc/x.md"),
        original_text="id: article:X\n",
        new_text="id: paper:X\n",
        match_count=1,
    )
    diff = render_diff([rewrite])
    assert "--- doc/x.md" in diff
    assert "+++ doc/x.md" in diff
    assert "-id: article:X" in diff
    assert "+id: paper:X" in diff


def test_render_diff_respects_line_cap() -> None:
    from science_tool.refs_migrate import FileRewrite, render_diff
    many = [
        FileRewrite(
            path=Path(f"doc/x{i}.md"),
            original_text=f"article:X{i}\n" * 50,
            new_text=f"paper:X{i}\n" * 50,
            match_count=50,
        )
        for i in range(10)
    ]
    capped = render_diff(many, max_lines=200)
    assert "... " in capped and " more files with changes" in capped
    assert capped.count("\n") <= 220  # 200 diff lines + cap marker + slack
```

- [ ] **Step 2: Run tests to verify they fail**

Expected: 2 new tests FAIL.

- [ ] **Step 3: Implement `render_diff`**

Append to `science-tool/src/science_tool/refs_migrate.py`:

```python
import difflib


def render_diff(rewrites: list[FileRewrite], max_lines: int | None = 200) -> str:
    """Return a human-readable unified diff for a list of rewrites.

    ``max_lines=None`` disables capping (used by ``--verbose`` in the CLI).
    Capped output appends a ``... N more files with changes`` marker.
    """
    lines: list[str] = []
    files_rendered = 0
    for rewrite in rewrites:
        diff = difflib.unified_diff(
            rewrite.original_text.splitlines(keepends=True),
            rewrite.new_text.splitlines(keepends=True),
            fromfile=str(rewrite.path),
            tofile=str(rewrite.path),
            n=2,
        )
        for line in diff:
            lines.append(line.rstrip("\n"))
            if max_lines is not None and len(lines) >= max_lines:
                remaining = len(rewrites) - files_rendered - 1
                if remaining > 0:
                    lines.append(f"... {remaining} more files with changes")
                return "\n".join(lines) + "\n"
        files_rendered += 1
    return "\n".join(lines) + ("\n" if lines else "")
```

- [ ] **Step 4: Run tests to verify they pass**

Expected: PASS (all 17 tests).

- [ ] **Step 5: Commit**

```bash
git add science-tool/src/science_tool/refs_migrate.py science-tool/tests/test_refs_migrate_paper.py
git commit -m "feat(refs_migrate): add render_diff helper"
```

---

## Task 7: Add `check_git_clean` helper

**Files:**
- Modify: `science-tool/src/science_tool/refs_migrate.py`
- Test: `science-tool/tests/test_refs_migrate_paper.py`

- [ ] **Step 1: Write the failing test**

Append to `science-tool/tests/test_refs_migrate_paper.py`:

```python
import subprocess


def _init_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "--allow-empty", "-m", "init", "-q"], cwd=path, check=True)


def test_check_git_clean_true_when_clean(tmp_path: Path) -> None:
    from science_tool.refs_migrate import check_git_clean
    _init_repo(tmp_path)
    assert check_git_clean(tmp_path) is True


def test_check_git_clean_false_when_dirty(tmp_path: Path) -> None:
    from science_tool.refs_migrate import check_git_clean
    _init_repo(tmp_path)
    (tmp_path / "new.txt").write_text("hi")
    assert check_git_clean(tmp_path) is False


def test_check_git_clean_true_for_non_git_dir(tmp_path: Path) -> None:
    from science_tool.refs_migrate import check_git_clean
    # Spec: if project isn't a git repo, don't block. User accepts the risk.
    assert check_git_clean(tmp_path) is True
```

- [ ] **Step 2: Run tests to verify they fail**

Expected: 3 new tests FAIL.

- [ ] **Step 3: Implement `check_git_clean`**

Append to `science-tool/src/science_tool/refs_migrate.py`:

```python
import subprocess


def check_git_clean(project_root: Path) -> bool:
    """Return True if the project's git working tree is clean (or not a repo).

    A non-git directory is treated as clean (returns True) — the user has
    opted out of git tracking and we don't want to block migration on that.
    """
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=project_root,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return True
    if result.returncode != 0:
        return True  # Not a git repo (fatal: not a git repository)
    return result.stdout.strip() == ""
```

- [ ] **Step 4: Run tests to verify they pass**

Expected: PASS (all 20 tests).

- [ ] **Step 5: Commit**

```bash
git add science-tool/src/science_tool/refs_migrate.py science-tool/tests/test_refs_migrate_paper.py
git commit -m "feat(refs_migrate): add check_git_clean guard"
```

---

## Task 8: Create `refs_cli.py` with empty click group

**Files:**
- Create: `science-tool/src/science_tool/refs_cli.py`
- Test: `science-tool/tests/test_refs_migrate_cli.py`

- [ ] **Step 1: Write the failing test**

Create `science-tool/tests/test_refs_migrate_cli.py`:

```python
from __future__ import annotations

from click.testing import CliRunner

from science_tool.refs_cli import refs_group


def test_refs_group_exists_and_has_migrate_paper() -> None:
    runner = CliRunner()
    result = runner.invoke(refs_group, ["--help"])
    assert result.exit_code == 0
    assert "migrate-paper" in result.output
```

- [ ] **Step 2: Run test to verify it fails**

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Create `refs_cli.py`**

Create `science-tool/src/science_tool/refs_cli.py`:

```python
"""Click CLI group for the ``refs`` subcommands."""

from __future__ import annotations

from pathlib import Path

import click

from science_tool.refs_migrate import (
    apply_rewrites,
    check_git_clean,
    render_diff,
    scan_project,
)


@click.group("refs")
def refs_group() -> None:
    """Reference-integrity tooling for Science projects."""


@refs_group.command("migrate-paper")
@click.option(
    "--project-root",
    type=click.Path(file_okay=False, exists=True, path_type=Path),
    default=Path.cwd(),
    show_default=True,
    help="Project root to migrate.",
)
@click.option("--apply", is_flag=True, help="Write changes to disk (otherwise dry-run).")
@click.option("--force", is_flag=True, help="Bypass the clean-git check when applying.")
@click.option("--verbose", is_flag=True, help="Show the full diff without line cap.")
def migrate_paper(project_root: Path, apply: bool, force: bool, verbose: bool) -> None:
    """Migrate legacy ``article:`` entity IDs to canonical ``paper:``."""
    rewrites = scan_project(project_root)
    if not rewrites:
        click.echo("No `article:` references found; project is migrated.")
        return

    if not apply:
        diff = render_diff(rewrites, max_lines=None if verbose else 200)
        click.echo(diff)
        total = sum(r.match_count for r in rewrites)
        click.echo(f"Would rewrite {total} legacy paper references in {len(rewrites)} files.")
        click.echo("Re-run with --apply to write changes.")
        return

    if not force and not check_git_clean(project_root):
        raise click.ClickException(
            "Working tree is not clean. Commit or stash changes first, "
            "or re-run with --force to bypass."
        )

    apply_rewrites(rewrites)
    total = sum(r.match_count for r in rewrites)
    click.echo(
        f"Rewrote {total} legacy paper references in {len(rewrites)} files. "
        "Run `science-tool refs check --root <project-root>` to verify."
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --frozen pytest science-tool/tests/test_refs_migrate_cli.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science-tool/src/science_tool/refs_cli.py science-tool/tests/test_refs_migrate_cli.py
git commit -m "feat(refs_cli): add refs group with migrate-paper subcommand"
```

---

## Task 9: Register `refs_group` in top-level CLI

**Files:**
- Modify: `science-tool/src/science_tool/cli.py`
- Test: `science-tool/tests/test_refs_migrate_cli.py`

- [ ] **Step 1: Write the failing test**

Append to `science-tool/tests/test_refs_migrate_cli.py`:

```python
from science_tool.cli import main as top_level_cli


def test_top_level_cli_exposes_refs_group() -> None:
    runner = CliRunner()
    result = runner.invoke(top_level_cli, ["refs", "--help"])
    assert result.exit_code == 0
    assert "migrate-paper" in result.output
```

- [ ] **Step 2: Run test to verify it fails**

Expected: FAIL with `No such command 'refs'`.

- [ ] **Step 3: Register the group**

In `science-tool/src/science_tool/cli.py`, find the section where click groups are added (search for `add_command` near the bottom of the file). Add:

```python
from science_tool.refs_cli import refs_group

main.add_command(refs_group)
```

If the file already has other `add_command` calls, place this line next to them. If `main` is defined under a different name (e.g., `cli`), substitute that name.

- [ ] **Step 4: Run test to verify it passes**

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science-tool/src/science_tool/cli.py
git commit -m "feat(cli): register refs group"
```

---

## Task 10: End-to-end integration test on the fixture

**Files:**
- Test: `science-tool/tests/test_refs_migrate_cli.py`

- [ ] **Step 1: Write the failing tests**

Append to `science-tool/tests/test_refs_migrate_cli.py`:

```python
import shutil
from pathlib import Path

FIXTURE = Path(__file__).parent / "fixtures" / "refs" / "legacy_project"


def test_migrate_paper_dry_run_does_not_write(tmp_path: Path) -> None:
    shutil.copytree(FIXTURE, tmp_path / "p")
    project = tmp_path / "p"
    before = (project / "doc" / "questions" / "q01-example.md").read_text()

    result = CliRunner().invoke(refs_group, ["migrate-paper", "--project-root", str(project)])
    assert result.exit_code == 0
    assert "Would rewrite" in result.output
    assert (project / "doc" / "questions" / "q01-example.md").read_text() == before


def test_migrate_paper_apply_rewrites_files(tmp_path: Path) -> None:
    shutil.copytree(FIXTURE, tmp_path / "p")
    project = tmp_path / "p"
    # Fixture isn't a git repo: --apply should proceed without --force.
    result = CliRunner().invoke(refs_group, ["migrate-paper", "--project-root", str(project), "--apply"])
    assert result.exit_code == 0, result.output
    assert "Rewrote" in result.output

    text = (project / "doc" / "questions" / "q01-example.md").read_text()
    assert "article:" not in text
    assert "paper:Smith2024" in text


def test_migrate_paper_idempotent(tmp_path: Path) -> None:
    shutil.copytree(FIXTURE, tmp_path / "p")
    project = tmp_path / "p"
    runner = CliRunner()
    runner.invoke(refs_group, ["migrate-paper", "--project-root", str(project), "--apply"])
    result = runner.invoke(refs_group, ["migrate-paper", "--project-root", str(project), "--apply"])
    assert result.exit_code == 0
    assert "No `article:` references found" in result.output


def test_migrate_paper_blocks_when_dirty(tmp_path: Path) -> None:
    import subprocess
    shutil.copytree(FIXTURE, tmp_path / "p")
    project = tmp_path / "p"
    subprocess.run(["git", "init", "-q"], cwd=project, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "add", "-A"],
        cwd=project, check=True,
    )
    # No commit: working tree is dirty (all files untracked).
    result = CliRunner().invoke(
        refs_group, ["migrate-paper", "--project-root", str(project), "--apply"]
    )
    assert result.exit_code != 0
    assert "not clean" in result.output.lower()
```

- [ ] **Step 2: Run tests and verify they pass**

Run: `uv run --frozen pytest science-tool/tests/test_refs_migrate_cli.py -v`
Expected: PASS (4 new tests).

- [ ] **Step 3: Commit**

```bash
git add science-tool/tests/test_refs_migrate_cli.py
git commit -m "test(refs_cli): add end-to-end migrate-paper tests"
```

---

## Task 11: Build the transition-window canonicalization helper

**Files:**
- Create: `science-tool/src/science_tool/big_picture/literature_prefix.py`
- Test: `science-tool/tests/test_literature_prefix.py`

- [ ] **Step 1: Write the failing tests**

Create `science-tool/tests/test_literature_prefix.py`:

```python
from __future__ import annotations

from science_tool.big_picture.literature_prefix import (
    canonical_paper_id,
    is_external_paper_id,
)


def test_canonicalizes_article_prefix() -> None:
    assert canonical_paper_id("article:Smith2024") == "paper:Smith2024"


def test_passes_through_paper_prefix() -> None:
    assert canonical_paper_id("paper:Smith2024") == "paper:Smith2024"


def test_passes_through_other_prefixes_unchanged() -> None:
    assert canonical_paper_id("question:q01") == "question:q01"
    assert canonical_paper_id("cite:Smith2024") == "cite:Smith2024"
    assert canonical_paper_id("manuscript:m01") == "manuscript:m01"


def test_is_external_paper_id_accepts_both() -> None:
    assert is_external_paper_id("paper:Smith2024")
    assert is_external_paper_id("article:Smith2024")
    assert not is_external_paper_id("cite:Smith2024")
    assert not is_external_paper_id("topic:ribosome")
```

- [ ] **Step 2: Run tests to verify they fail**

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement the helper**

Create `science-tool/src/science_tool/big_picture/literature_prefix.py`:

```python
"""Transition-window canonicalization for external-literature entity IDs.

During the window between the manuscript+paper rename shipping and every
tracked project completing its migration, downstream consumers must treat
``article:<bibkey>`` as a legacy alias of canonical ``paper:<bibkey>``.
This helper is the single place that encodes that rule.

Removal: this module is deleted (one-line change per consumer) once all
tracked projects confirm migration. See
docs/specs/2026-04-19-manuscript-paper-rename-design.md §Transition-Window.
"""

from __future__ import annotations

_LEGACY_EXTERNAL_PREFIX = "article:"
_CANONICAL_EXTERNAL_PREFIX = "paper:"


def canonical_paper_id(entity_id: str) -> str:
    """Return the canonical form of ``entity_id``.

    Maps ``article:<X>`` → ``paper:<X>``. All other entity IDs pass through.
    """
    if entity_id.startswith(_LEGACY_EXTERNAL_PREFIX):
        return _CANONICAL_EXTERNAL_PREFIX + entity_id[len(_LEGACY_EXTERNAL_PREFIX):]
    return entity_id


def is_external_paper_id(entity_id: str) -> bool:
    """True iff ``entity_id`` denotes an external literature entity."""
    return entity_id.startswith(
        (_CANONICAL_EXTERNAL_PREFIX, _LEGACY_EXTERNAL_PREFIX)
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science-tool/src/science_tool/big_picture/literature_prefix.py science-tool/tests/test_literature_prefix.py
git commit -m "feat(big_picture): add literature_prefix canonicalization helper"
```

---

## Task 12: Rename `templates/paper.md` → `templates/manuscript.md` with frontmatter update

**Files:**
- Rename: `templates/paper.md` → `templates/manuscript.md`

- [ ] **Step 1: Git-rename the file**

```bash
git mv templates/paper.md templates/manuscript.md
```

- [ ] **Step 2: Update the frontmatter**

In `templates/manuscript.md`, change the frontmatter lines:

```yaml
# Before
id: "paper:{{paper_id}}"
type: "paper"

# After
id: "manuscript:{{manuscript_id}}"
type: "manuscript"
```

Preserve every other line.

- [ ] **Step 3: Verify**

Run: `grep -n "^id:\|^type:" templates/manuscript.md`
Expected output shows the two updated lines.

- [ ] **Step 4: Commit**

```bash
git add templates/manuscript.md
git commit -m "refactor(templates): rename paper.md to manuscript.md (authoring)"
```

---

## Task 13: Rename `templates/paper-summary.md` → `templates/paper.md` with frontmatter update

**Files:**
- Rename: `templates/paper-summary.md` → `templates/paper.md`

- [ ] **Step 1: Git-rename the file**

```bash
git mv templates/paper-summary.md templates/paper.md
```

- [ ] **Step 2: Update the frontmatter**

In `templates/paper.md`, change:

```yaml
# Before
id: "article:{{bibtex_key}}"
type: "article"

# After
id: "paper:{{bibtex_key}}"
type: "paper"
```

- [ ] **Step 3: Verify**

Run: `grep -n "^id:\|^type:" templates/paper.md`
Expected output shows the two updated lines.

- [ ] **Step 4: Commit**

```bash
git add templates/paper.md
git commit -m "refactor(templates): rename paper-summary.md to paper.md (external lit)"
```

---

## Task 14: Cosmetic rewrite of `article` in top-level `cli.py`

**Files:**
- Modify: `science-tool/src/science_tool/cli.py`

- [ ] **Step 1: Find the occurrence**

Run: `grep -n "Added article" science-tool/src/science_tool/cli.py`
Expected: one match around line 1004.

- [ ] **Step 2: Rewrite**

Change `click.echo(f"Added article: {uri}")` → `click.echo(f"Added paper: {uri}")`.

- [ ] **Step 3: Grep for other user-facing `article` strings**

Run: `grep -nE '\barticle\b' science-tool/src/science_tool/cli.py`

For each match, decide:
- **User-facing string referring to the entity concept** → rewrite to `paper`.
- **Comment, grammar ("an article"), or help text where "paper" is wrong** → leave.

- [ ] **Step 4: Run existing tests**

Run: `uv run --frozen pytest science-tool/tests/test_cli.py -v` (or the appropriate CLI test module for this repo).
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science-tool/src/science_tool/cli.py
git commit -m "refactor(cli): rewrite user-facing article → paper"
```

---

## Task 15: Audit the nine `article:`-containing test files

**Files:**
- Audit + potentially modify:
  - `science-tool/tests/test_paper_model.py`
  - `science-tool/tests/test_graph_cli.py`
  - `science-tool/tests/test_inquiry_cli.py`
  - `science-tool/tests/test_cross_impact.py`
  - `science-tool/tests/test_layered_claim_migration.py`
  - `science-tool/tests/test_graph_export.py`
  - `science-tool/tests/test_causal.py`
  - `science-tool/tests/test_project_model_migration.py`
  - `science-tool/tests/test_causal_cli.py`

- [ ] **Step 1: List current matches**

Run: `grep -n "article:" science-tool/tests/test_*.py`

- [ ] **Step 2: Triage each match**

For each match, classify per the spec's triage rule:

- **Assertion on current entity-prefix output (canonical `paper:`)**: rewrite `article:` → `paper:`.
- **Regression fixture intentionally exercising the legacy prefix via the transition-window alias path**: keep as `article:` and add a one-line `# deliberate: legacy alias` comment.
- **Dead fixture with no assertion on the prefix**: rewrite mechanically.

For each file, make the edits. Err on the side of rewriting; only preserve `article:` where a test genuinely needs the legacy form (likely rare).

- [ ] **Step 3: Run all tests**

Run: `uv run --frozen pytest science-tool/tests/ -v`
Expected: PASS. Any failure means a test expects the pre-rename prefix — re-read the test; if the assertion was on canonical output, keep the rewrite and update the expected value.

- [ ] **Step 4: Commit**

```bash
git add science-tool/tests
git commit -m "test: triage article: literals across test suite for rename"
```

---

## Task 16: Update `commands/*.md` documentation

**Files:**
- Modify: `commands/research-papers.md`
- Modify: `commands/search-literature.md`
- Modify: `commands/bias-audit.md`
- Modify: `commands/compare-hypotheses.md`
- Modify: `commands/next-steps.md`
- Modify: `commands/research-topic.md`

- [ ] **Step 1: Find template-path mentions**

Run: `grep -n "paper-summary.md\|paper\.md" commands/*.md`

- [ ] **Step 2: Rewrite template paths**

For each match:
- `paper-summary.md` → `paper.md` (external-lit template).
- `paper.md` (when referring to the authoring concept) → `manuscript.md`.

If a command refers to both concepts, rewrite each independently.

- [ ] **Step 3: Find and rewrite `article:<X>` examples**

Run: `grep -nE '\barticle:[A-Za-z0-9_\-.]+' commands/*.md`

For each match: rewrite `article:<X>` → `paper:<X>`.

- [ ] **Step 4: Commit**

```bash
git add commands/
git commit -m "docs(commands): rewrite paper-summary/paper/article references for rename"
```

---

## Task 17: Update `references/*.md` and referenced specs

**Files:**
- Modify: `references/role-prompts/research-assistant.md`
- Modify: `references/project-structure.md`
- Modify: `docs/specs/2026-03-02-agent-capabilities-design.md`

- [ ] **Step 1: Find matches**

Run: `grep -nE '\barticle:|paper-summary\.md|paper\.md' references/ docs/specs/`

- [ ] **Step 2: Rewrite**

Apply the same rules as Task 16: template paths and `article:<X>` examples.

- [ ] **Step 3: Commit**

```bash
git add references/ docs/specs/
git commit -m "docs(references): rewrite references for rename"
```

---

## Task 18: Grep `science-tool/src/` for hardcoded template filenames

**Files:**
- Audit: `science-tool/src/` (read-only scan first, then targeted edits)

- [ ] **Step 1: Grep**

Run:

```bash
grep -rn "paper-summary.md\|\"paper.md\"\|'paper.md'" science-tool/src/
```

- [ ] **Step 2: Triage**

For each hit:
- If the string refers to the external-lit template, rewrite `paper-summary.md` → `paper.md` and `paper.md` stays `paper.md` (wait — check the context: what concept is being referenced?).
- If the string refers to the authoring template, rewrite `paper.md` → `manuscript.md`.
- If there's no clear mapping, leave a TODO-free comment and flag for user review (prefer not to silently "guess").

- [ ] **Step 3: Apply edits**

Make the rewrites.

- [ ] **Step 4: Run tests**

Run: `uv run --frozen pytest science-tool/tests/ -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science-tool/src/
git commit -m "refactor: rewrite hardcoded template paths for rename"
```

---

## Task 19: Run the migration tool on the Science framework itself

**Files:**
- No new files. This task rewrites existing markdown in the Science repo.

- [ ] **Step 1: Ensure clean working tree**

Run: `git status`
Expected: clean. If not, commit or stash any in-progress work first.

- [ ] **Step 2: Dry-run on the repo root**

Run: `uv run --frozen science-tool refs migrate-paper --project-root .`
Review the emitted diff. Every hit should be an expected `article:<X>` → `paper:<X>` rewrite in non-spec documentation or example fixtures.

- [ ] **Step 3: Apply**

Run: `uv run --frozen science-tool refs migrate-paper --project-root . --apply`
Expected: `Rewrote N legacy paper references in K files.`

- [ ] **Step 4: Verify**

Run: `grep -rn "article:" docs/ commands/ references/ templates/ --include="*.md" | grep -v spec`
Expected: no matches outside the two rename spec files (which intentionally quote `article:` as the prefix being replaced).

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor: migrate article: → paper: across framework docs"
```

---

## Task 20: Smoke-test on tracked projects (manual)

**Files:**
- No repo-side changes. This is a manual validation on external projects (mm30, natural-systems).

- [ ] **Step 1: On mm30**

```bash
cd ~/d/mm30   # or wherever mm30 lives
uv run science-tool refs migrate-paper --project-root .
uv run science-tool refs migrate-paper --project-root . --apply
uv run science-tool refs check --root .
```

Expected: the dry-run shows plausible hits; `--apply` rewrites them; `refs check` reports no new dangling references.

- [ ] **Step 2: On natural-systems**

Same commands in that project.

Expected: same outcome. Note: natural-systems is known to have ~50 pre-existing unresolved references (see project memory); tolerate those if they predate the migration.

- [ ] **Step 3: If any smoke fails**

File an issue in the Science repo describing the failure. Do NOT attempt to hack around it in the migration tool without writing a regression test first.

---

## Self-Review

- [ ] **Spec coverage check**: every section of `docs/specs/2026-04-19-manuscript-paper-rename-design.md` maps to a task (template renames → Tasks 12–13; migration tool → Tasks 1–10; transition-window helper → Task 11; docs updates → Tasks 16–17; CLI cosmetic → Task 14; test audit → Task 15; sequencing/smoke → Tasks 19–20).
- [ ] **No placeholders**: every step has concrete code or an exact command.
- [ ] **Type consistency**: `FileRewrite`, `scan_project`, `apply_rewrites`, `rewrite_text`, `render_diff`, `check_git_clean`, `canonical_paper_id`, `is_external_paper_id` referenced consistently across tasks.

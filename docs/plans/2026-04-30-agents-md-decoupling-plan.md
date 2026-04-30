# AGENTS.md Decoupling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop AGENTS.md from `@`-injecting `core/overview.md` + `core/decisions.md`, replace with a managed one-line "load-bearing constraints" digest refreshed by `/science:curate`.

**Architecture:** AGENTS.md becomes a standalone operational guide with a small managed digest section between explicit markers. A new helper in `science-tool/src/science_tool/curate/agents_md.py` parses both `core/decisions.md` (active decisions only) and AGENTS.md (digest IDs, markers, legacy `@core/*` directives) plus CLAUDE.md (shape check), exposes the result on `CurationInventory`, and `/science:curate` consumes the signals to propose edits. Doc/template/Codex-skill artifacts are updated to reflect the new convention; `meta/AGENTS.md` is rewritten as the worked example.

**Tech Stack:** Python 3.11+, Pydantic, pytest, uv. Markdown templates and slash-command docs.

**Spec:** `docs/plans/2026-04-30-agents-md-decoupling-design.md`

---

## File Structure

**New files:**
- `templates/agents-md.md` — canonical AGENTS.md scaffold for new projects.
- `science-tool/src/science_tool/curate/agents_md.py` — drift-detection helper.
- `science-tool/tests/test_curate_agents_md.py` — unit tests for the helper.

**Modified files:**
- `commands/create-project.md` — point at the new template; drop `@core/*` injection instruction.
- `commands/import-project.md` — same; add explicit removal guidance for legacy directives.
- `references/project-structure.md` — update `core/` and top-level-files sections.
- `commands/curate.md` — document the `agents-md` theme.
- `science-tool/src/science_tool/curate/inventory.py` — extend `CurationInventory` with `agents_md` field; call helper from `collect_inventory()`.
- `science-tool/tests/test_curate_inventory.py` — extend integration test to cover the new field.
- `meta/AGENTS.md` — rewrite to new shape (live example).
- Generated under `codex-skills/` — regenerated via `scripts/generate_codex_skills.py`.

---

## Task 1: Create canonical AGENTS.md template

**Files:**
- Create: `templates/agents-md.md`

- [ ] **Step 1: Write the template**

Create `templates/agents-md.md` with this content:

````markdown
<!--
templates/agents-md.md — canonical scaffold for a project's AGENTS.md.

CLAUDE.md is a single-line `@AGENTS.md` pointer. This file is what the agent
actually reads at session start.

Keep it short. References to core/overview.md and core/decisions.md belong in
the Pointers section, NOT as `@`-includes (those would inline hundreds of
lines per turn). The Load-bearing constraints section between the BEGIN/END
markers is managed by `/science:curate` — edit core/decisions.md instead and
let curate refresh the digest.
-->

# <project> — Agent Guide

## What this is

<1-2 sentence project description.>

## Profile

<software | research>, with <one-line elaboration if useful>.

## Validation

```bash
bash validate.sh --verbose
```

## Conventions

- <bullets — operational rules an agent will need every turn>

## Task execution

- <bullets — how tasks are run, where commits go, etc.>

## Known issues / nuances

- <bullets — gotchas not derivable from the code>

<!-- BEGIN: load-bearing-constraints (managed by /science:curate; edit core/decisions.md instead) -->
## Load-bearing constraints

<!-- One bullet per active decision in core/decisions.md, phrased as an
imperative rule. The "why" stays in core/decisions.md. -->

- _none yet — populated by `/science:curate` once `core/decisions.md` has entries._

<!-- END: load-bearing-constraints -->

## Pointers

- Decisions: `core/decisions.md`
- Project overview: `core/overview.md`
- Active tasks: `tasks/active.md`
- Hypotheses: `specs/hypotheses/`
````

- [ ] **Step 2: Verify the template contains no `@core/`**

Run: `grep -F '@core/' templates/agents-md.md`
Expected: no output (exit code 1).

- [ ] **Step 3: Commit**

```bash
git add templates/agents-md.md
git commit -m "feat(templates): add canonical AGENTS.md scaffold without @core/ includes"
```

---

## Task 2: Update `commands/create-project.md`

**Files:**
- Modify: `commands/create-project.md:223-251`

- [ ] **Step 1: Replace the AGENTS.md section**

In `commands/create-project.md`, find the section starting at line 223 (`### \`CLAUDE.md\``). Confirm the current content matches:

```md
### `CLAUDE.md`

Create:

```md
@AGENTS.md
```

### `AGENTS.md`

Create a concise project-specific operational guide that covers:

- project overview
- validation commands
- conventions
- task execution constraints
- data access notes
- known issues

If the project has (or will have) curated orientation docs under `core/`,
include `@core/overview.md` and `@core/decisions.md` near the top of `AGENTS.md`
so they load at session start. The directives must tolerate missing files —
the `core/` directory is optional. See `core/` in
`${CLAUDE_PLUGIN_ROOT}/references/project-structure.md` for conventions and
length caps.

Offer to scaffold `core/overview.md` and `core/decisions.md` from
`${CLAUDE_PLUGIN_ROOT}/templates/core-overview.md` and
`${CLAUDE_PLUGIN_ROOT}/templates/core-decisions.md`. Skip if the user declines.
```

Replace it with:

```md
### `CLAUDE.md`

Create:

```md
@AGENTS.md
```

`CLAUDE.md` is a single-line pointer. Do not add `@core/*.md` directives or
project-specific guidance here — both belong in `AGENTS.md`.

### `AGENTS.md`

Use the canonical scaffold at `${CLAUDE_PLUGIN_ROOT}/templates/agents-md.md` as the
starting point. Fill in the project-specific sections (What this is, Profile,
Conventions, Task execution, Known issues) from the conversation in Step 1.

Do **not** insert `@core/overview.md` or `@core/decisions.md` directives. The
`core/` files are referenced from the Pointers section instead. The
"Load-bearing constraints" section between the BEGIN/END markers is left empty
on initial scaffold; `/science:curate` populates it once `core/decisions.md`
has entries. See `core/` in
`${CLAUDE_PLUGIN_ROOT}/references/project-structure.md` for the conventions.

Offer to scaffold `core/overview.md` and `core/decisions.md` from
`${CLAUDE_PLUGIN_ROOT}/templates/core-overview.md` and
`${CLAUDE_PLUGIN_ROOT}/templates/core-decisions.md`. Skip if the user declines.
```

- [ ] **Step 2: Verify the file no longer instructs `@core/*` insertion**

Run: `grep -nE '@core/(overview|decisions)\.md' commands/create-project.md`
Expected: no output.

- [ ] **Step 3: Commit**

```bash
git add commands/create-project.md
git commit -m "docs(commands): point create-project at agents-md.md template, drop @core injection"
```

---

## Task 3: Update `commands/import-project.md`

**Files:**
- Modify: `commands/import-project.md:186-201`

- [ ] **Step 1: Replace the AGENTS.md and CLAUDE.md subsections**

In `commands/import-project.md`, find:

```md
### `AGENTS.md`

Extend or create `AGENTS.md` so it reflects:

- the canonical active roots
- validation commands
- conventions
- operational constraints

### `CLAUDE.md`

Create or normalize:

```md
@AGENTS.md
```
```

Replace with:

```md
### `AGENTS.md`

Extend or create `AGENTS.md` so it reflects:

- the canonical active roots
- validation commands
- conventions
- operational constraints

Use `${CLAUDE_PLUGIN_ROOT}/templates/agents-md.md` as the structural reference.

If the existing `AGENTS.md` begins with `@core/overview.md` or
`@core/decisions.md` directives, remove them. Those files routinely run into
the hundreds of lines and would be injected into context every turn. The
"Load-bearing constraints" digest in `AGENTS.md` is maintained by
`/science:curate` based on `core/decisions.md` instead.

### `CLAUDE.md`

Create or normalize to a single line:

```md
@AGENTS.md
```

If the existing `CLAUDE.md` carries duplicated `@core/*` directives or
project-specific guidance, move any non-include guidance into `AGENTS.md` and
collapse `CLAUDE.md` to the single `@AGENTS.md` pointer.
```

- [ ] **Step 2: Verify**

Run: `grep -nE '@core/(overview|decisions)\.md' commands/import-project.md`
Expected: only the line that mentions stripping them, e.g. one match in the explanatory paragraph.

Inspect manually that the only remaining matches are in the "remove them" guidance, not as instructions to insert.

- [ ] **Step 3: Commit**

```bash
git add commands/import-project.md
git commit -m "docs(commands): import-project removes legacy @core directives, points at template"
```

---

## Task 4: Update `references/project-structure.md`

**Files:**
- Modify: `references/project-structure.md:12` (top-level files table) and `:84-101` (the `core/` section).

- [ ] **Step 1: Update the CLAUDE.md row in the top-level files table**

Find the row at line 12:

```md
| `CLAUDE.md` | Single-line pointer to `AGENTS.md` | Agent on project creation |
```

Leave it as-is — it is already correct.

Find the row at line 13:

```md
| `AGENTS.md` | Operational guide (tools, validation, conventions) | Agent during loops |
```

Replace with:

```md
| `AGENTS.md` | Operational guide (tools, validation, conventions, managed load-bearing-constraints digest) | Agent during loops; digest section managed by `/science:curate` |
```

- [ ] **Step 2: Update the `core/` section**

Find lines 84-101 (the `### \`core/\` — Curated Project Orientation (optional)` section) and replace from line 100-101:

```md
`AGENTS.md` should `@core/overview.md` and `@core/decisions.md` when they exist;
both files are optional and AGENTS.md must tolerate their absence.
```

with:

```md
`AGENTS.md` references `core/` via its Pointers section and carries a managed
digest of load-bearing constraints between `<!-- BEGIN: load-bearing-constraints -->`
and `<!-- END: load-bearing-constraints -->` markers. The digest is refreshed
by `/science:curate` from `core/decisions.md` (active decisions only). AGENTS.md
does **not** `@`-include `core/*.md` — those files routinely run into the
hundreds of lines and would inflate every turn's context.
```

- [ ] **Step 3: Verify**

Run: `grep -nE '@core/(overview|decisions)\.md' references/project-structure.md`
Expected: no output.

- [ ] **Step 4: Commit**

```bash
git add references/project-structure.md
git commit -m "docs(references): describe AGENTS.md managed digest, drop @core/ injection guidance"
```

---

## Task 5: Add `AgentsMdDigestState` model + `core/decisions.md` active-ID parser (TDD)

**Files:**
- Create: `science-tool/src/science_tool/curate/agents_md.py`
- Create: `science-tool/tests/test_curate_agents_md.py`

- [ ] **Step 1: Write the failing test for the active-decision parser**

Create `science-tool/tests/test_curate_agents_md.py`:

```python
from __future__ import annotations

from pathlib import Path
import textwrap

import pytest

from science_tool.curate.agents_md import parse_active_decision_ids


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(text).lstrip("\n"), encoding="utf-8")


def test_parse_active_decision_ids_returns_only_active(tmp_path: Path) -> None:
    decisions = tmp_path / "core" / "decisions.md"
    _write(
        decisions,
        """
        # Decisions

        ## D-001: First decision

        - **Date:** 2026-01-01
        - **Status:** active
        - **Decision:** First.

        ---

        ## D-002: Second decision

        - **Date:** 2026-01-02
        - **Status:** superseded by D-004
        - **Decision:** Second.

        ---

        ## D-003: Third decision

        - **Date:** 2026-01-03
        - **Status:** abandoned
        - **Decision:** Third.

        ---

        ## D-004: Fourth decision

        - **Date:** 2026-01-04
        - **Status:** active
        - **Decision:** Fourth.
        """,
    )

    assert parse_active_decision_ids(decisions) == ["D-001", "D-004"]


def test_parse_active_decision_ids_returns_empty_for_missing_file(tmp_path: Path) -> None:
    assert parse_active_decision_ids(tmp_path / "core" / "decisions.md") == []


def test_parse_active_decision_ids_handles_no_status_line(tmp_path: Path) -> None:
    decisions = tmp_path / "core" / "decisions.md"
    _write(
        decisions,
        """
        # Decisions

        ## D-001: A decision without a status line yet

        - **Date:** 2026-01-01
        - **Decision:** Pending.
        """,
    )
    # No `- **Status:** active` line means we cannot confirm active.
    assert parse_active_decision_ids(decisions) == []
```

- [ ] **Step 2: Run the test and confirm it fails**

Run: `cd science-tool && uv run pytest tests/test_curate_agents_md.py -v`
Expected: ImportError or ModuleNotFoundError on `parse_active_decision_ids`.

- [ ] **Step 3: Implement the parser**

Create `science-tool/src/science_tool/curate/agents_md.py`:

```python
"""Drift-detection helper for AGENTS.md and core/decisions.md.

Used by /science:curate to propose:
 - removal of legacy `@core/*` directives from AGENTS.md / CLAUDE.md
 - normalization of CLAUDE.md to a single `@AGENTS.md` pointer
 - insertion of the managed load-bearing-constraints digest markers
 - refresh of digest entries when active decisions change
"""

from __future__ import annotations

import re
from pathlib import Path

_DECISION_HEADING = re.compile(r"^##\s+(D-\d+)\b", re.MULTILINE)
_STATUS_LINE = re.compile(r"^-\s+\*\*Status:\*\*\s*(.+?)\s*$", re.MULTILINE)


def parse_active_decision_ids(decisions_md: Path) -> list[str]:
    """Return the IDs of decisions whose Status line is exactly `active`.

    Skips entries that are superseded, abandoned, or missing a Status line.
    """
    if not decisions_md.is_file():
        return []
    text = decisions_md.read_text(encoding="utf-8")
    sections = _split_decision_sections(text)
    active: list[str] = []
    for decision_id, body in sections:
        match = _STATUS_LINE.search(body)
        if match is None:
            continue
        if match.group(1).strip().lower() == "active":
            active.append(decision_id)
    return active


def _split_decision_sections(text: str) -> list[tuple[str, str]]:
    """Split a decisions.md file into (decision_id, section_body) pairs."""
    matches = list(_DECISION_HEADING.finditer(text))
    sections: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections.append((match.group(1), text[start:end]))
    return sections
```

- [ ] **Step 4: Run the tests and confirm they pass**

Run: `cd science-tool && uv run pytest tests/test_curate_agents_md.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add science-tool/src/science_tool/curate/agents_md.py science-tool/tests/test_curate_agents_md.py
git commit -m "feat(curate): parse active decision IDs from core/decisions.md"
```

---

## Task 6: Add the AGENTS.md digest-IDs + markers parser (TDD)

**Files:**
- Modify: `science-tool/src/science_tool/curate/agents_md.py`
- Modify: `science-tool/tests/test_curate_agents_md.py`

- [ ] **Step 1: Write the failing tests**

Append to `science-tool/tests/test_curate_agents_md.py`:

```python
from science_tool.curate.agents_md import (
    BEGIN_MARKER,
    END_MARKER,
    parse_digest_ids,
    parse_marker_state,
)


def test_parse_marker_state_detects_present_markers(tmp_path: Path) -> None:
    agents_md = tmp_path / "AGENTS.md"
    _write(
        agents_md,
        f"""
        # P — Agent Guide

        {BEGIN_MARKER}
        ## Load-bearing constraints

        - **D-001:** Do the thing.
        {END_MARKER}
        """,
    )
    assert parse_marker_state(agents_md) is True


def test_parse_marker_state_detects_absent_markers(tmp_path: Path) -> None:
    agents_md = tmp_path / "AGENTS.md"
    _write(agents_md, "# P — Agent Guide\n\n## Conventions\n- be nice\n")
    assert parse_marker_state(agents_md) is False


def test_parse_marker_state_returns_false_when_only_one_marker(tmp_path: Path) -> None:
    agents_md = tmp_path / "AGENTS.md"
    _write(agents_md, f"# P\n\n{BEGIN_MARKER}\nstuff but no end\n")
    assert parse_marker_state(agents_md) is False


def test_parse_digest_ids_extracts_ids_between_markers(tmp_path: Path) -> None:
    agents_md = tmp_path / "AGENTS.md"
    _write(
        agents_md,
        f"""
        # P — Agent Guide

        {BEGIN_MARKER}
        ## Load-bearing constraints

        - **D-001:** First rule.
        - **D-004:** Fourth rule.
        {END_MARKER}

        ## Pointers
        - **D-999:** This must NOT be picked up because it is outside the markers.
        """,
    )
    assert parse_digest_ids(agents_md) == ["D-001", "D-004"]


def test_parse_digest_ids_returns_empty_when_markers_missing(tmp_path: Path) -> None:
    agents_md = tmp_path / "AGENTS.md"
    _write(agents_md, "# P\n\n- **D-001:** ignored, no markers\n")
    assert parse_digest_ids(agents_md) == []


def test_parse_digest_ids_returns_empty_when_file_missing(tmp_path: Path) -> None:
    assert parse_digest_ids(tmp_path / "AGENTS.md") == []
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `cd science-tool && uv run pytest tests/test_curate_agents_md.py -v`
Expected: ImportError on `BEGIN_MARKER`, `END_MARKER`, `parse_digest_ids`, `parse_marker_state`.

- [ ] **Step 3: Implement marker constants and parsers**

Append to `science-tool/src/science_tool/curate/agents_md.py`:

```python
BEGIN_MARKER = "<!-- BEGIN: load-bearing-constraints (managed by /science:curate; edit core/decisions.md instead) -->"
END_MARKER = "<!-- END: load-bearing-constraints -->"

_DIGEST_ENTRY = re.compile(r"^-\s+\*\*(D-\d+):\*\*", re.MULTILINE)


def parse_marker_state(agents_md: Path) -> bool:
    """Return True iff both BEGIN and END markers are present."""
    if not agents_md.is_file():
        return False
    text = agents_md.read_text(encoding="utf-8")
    return BEGIN_MARKER in text and END_MARKER in text


def parse_digest_ids(agents_md: Path) -> list[str]:
    """Return D-NNN IDs listed inside the load-bearing-constraints markers."""
    if not agents_md.is_file():
        return []
    text = agents_md.read_text(encoding="utf-8")
    begin = text.find(BEGIN_MARKER)
    end = text.find(END_MARKER, begin + len(BEGIN_MARKER)) if begin != -1 else -1
    if begin == -1 or end == -1:
        return []
    section = text[begin + len(BEGIN_MARKER) : end]
    return [match.group(1) for match in _DIGEST_ENTRY.finditer(section)]
```

- [ ] **Step 4: Run the tests and confirm they pass**

Run: `cd science-tool && uv run pytest tests/test_curate_agents_md.py -v`
Expected: all tests pass (3 prior + 5 new = 8).

- [ ] **Step 5: Commit**

```bash
git add science-tool/src/science_tool/curate/agents_md.py science-tool/tests/test_curate_agents_md.py
git commit -m "feat(curate): parse digest IDs and marker presence from AGENTS.md"
```

---

## Task 7: Add legacy `@core/*` directive detection + CLAUDE.md shape check (TDD)

**Files:**
- Modify: `science-tool/src/science_tool/curate/agents_md.py`
- Modify: `science-tool/tests/test_curate_agents_md.py`

- [ ] **Step 1: Write the failing tests**

Append to `science-tool/tests/test_curate_agents_md.py`:

```python
from science_tool.curate.agents_md import (
    detect_legacy_at_includes,
    is_claude_md_normalizable,
)


def test_detect_legacy_at_includes_finds_directives(tmp_path: Path) -> None:
    agents_md = tmp_path / "AGENTS.md"
    _write(
        agents_md,
        """
        @core/overview.md
        @core/decisions.md

        # P — Agent Guide
        """,
    )
    assert detect_legacy_at_includes(agents_md) == ["@core/overview.md", "@core/decisions.md"]


def test_detect_legacy_at_includes_only_matches_at_top(tmp_path: Path) -> None:
    agents_md = tmp_path / "AGENTS.md"
    _write(
        agents_md,
        """
        # P — Agent Guide

        ## Some section

        @core/overview.md
        """,
    )
    # Directive in the middle of the file is not a Claude Code include directive
    # (those must be at the top of the file). Treat as content, not legacy include.
    assert detect_legacy_at_includes(agents_md) == []


def test_detect_legacy_at_includes_returns_empty_for_missing(tmp_path: Path) -> None:
    assert detect_legacy_at_includes(tmp_path / "AGENTS.md") == []


def test_detect_legacy_at_includes_finds_only_core_paths(tmp_path: Path) -> None:
    agents_md = tmp_path / "AGENTS.md"
    _write(
        agents_md,
        """
        @AGENTS.md
        @core/overview.md
        @other/file.md
        """,
    )
    assert detect_legacy_at_includes(agents_md) == ["@core/overview.md"]


def test_is_claude_md_normalizable_pure_pointer(tmp_path: Path) -> None:
    claude_md = tmp_path / "CLAUDE.md"
    _write(claude_md, "@AGENTS.md\n")
    assert is_claude_md_normalizable(claude_md) is True


def test_is_claude_md_normalizable_pointer_plus_legacy_includes(tmp_path: Path) -> None:
    claude_md = tmp_path / "CLAUDE.md"
    _write(
        claude_md,
        """
        @AGENTS.md
        @core/overview.md
        @core/decisions.md
        """,
    )
    assert is_claude_md_normalizable(claude_md) is True


def test_is_claude_md_normalizable_with_extra_content(tmp_path: Path) -> None:
    claude_md = tmp_path / "CLAUDE.md"
    _write(
        claude_md,
        """
        @AGENTS.md
        @core/overview.md

        # Project-specific Claude Code guidance

        Always use uv, never pip.
        """,
    )
    assert is_claude_md_normalizable(claude_md) is False


def test_is_claude_md_normalizable_with_extra_at_include(tmp_path: Path) -> None:
    claude_md = tmp_path / "CLAUDE.md"
    _write(
        claude_md,
        """
        @AGENTS.md
        @other/notes.md
        """,
    )
    assert is_claude_md_normalizable(claude_md) is False


def test_is_claude_md_normalizable_returns_false_for_missing(tmp_path: Path) -> None:
    assert is_claude_md_normalizable(tmp_path / "CLAUDE.md") is False
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `cd science-tool && uv run pytest tests/test_curate_agents_md.py -v`
Expected: ImportError on `detect_legacy_at_includes`, `is_claude_md_normalizable`.

- [ ] **Step 3: Implement the detectors**

Append to `science-tool/src/science_tool/curate/agents_md.py`:

```python
_AT_INCLUDE_LINE = re.compile(r"^@(\S+)\s*$")


def detect_legacy_at_includes(markdown_file: Path) -> list[str]:
    """Return `@core/*` directives that appear in the top-of-file include block.

    Claude Code only treats `@path` lines at the very top of a markdown file
    (before any non-include content) as include directives. We mirror that:
    walk lines from the top, collect `@path` lines, stop at the first
    non-include, non-blank line, then filter for `core/` paths.
    """
    if not markdown_file.is_file():
        return []
    legacy: list[str] = []
    for line in markdown_file.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        match = _AT_INCLUDE_LINE.match(stripped)
        if match is None:
            break
        path = match.group(1)
        if path.startswith("core/"):
            legacy.append(f"@{path}")
    return legacy


def is_claude_md_normalizable(claude_md: Path) -> bool:
    """Return True iff CLAUDE.md is safe to overwrite with a bare `@AGENTS.md`.

    Safe means: every non-blank line is either `@AGENTS.md` or a legacy
    `@core/*` directive. Anything else (project-specific guidance, other
    `@`-includes, prose) means manual review is required.
    """
    if not claude_md.is_file():
        return False
    seen_pointer = False
    for line in claude_md.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped == "@AGENTS.md":
            seen_pointer = True
            continue
        match = _AT_INCLUDE_LINE.match(stripped)
        if match is None:
            return False
        if not match.group(1).startswith("core/"):
            return False
    return seen_pointer
```

- [ ] **Step 4: Run the tests and confirm they pass**

Run: `cd science-tool && uv run pytest tests/test_curate_agents_md.py -v`
Expected: 16 passed.

- [ ] **Step 5: Commit**

```bash
git add science-tool/src/science_tool/curate/agents_md.py science-tool/tests/test_curate_agents_md.py
git commit -m "feat(curate): detect legacy @core/* directives and CLAUDE.md normalizability"
```

---

## Task 8: Compose `collect_agents_md_state()` with drift signals (TDD)

**Files:**
- Modify: `science-tool/src/science_tool/curate/agents_md.py`
- Modify: `science-tool/tests/test_curate_agents_md.py`

- [ ] **Step 1: Write the failing test for the composed collector**

Append to `science-tool/tests/test_curate_agents_md.py`:

```python
import os
from datetime import datetime, timezone

from science_tool.curate.agents_md import (
    AgentsMdDigestState,
    collect_agents_md_state,
)


def _set_mtime_iso(path: Path, when_iso: str) -> None:
    stamp = datetime.fromisoformat(when_iso).replace(tzinfo=timezone.utc).timestamp()
    os.utime(path, (stamp, stamp))


def test_collect_agents_md_state_pristine_modern_project(tmp_path: Path) -> None:
    _write(tmp_path / "CLAUDE.md", "@AGENTS.md\n")
    _write(
        tmp_path / "AGENTS.md",
        f"""
        # P — Agent Guide

        {BEGIN_MARKER}
        - **D-001:** Stay calm.
        {END_MARKER}
        """,
    )
    _write(
        tmp_path / "core" / "decisions.md",
        """
        ## D-001: Stay calm

        - **Date:** 2026-04-01
        - **Status:** active
        """,
    )
    _set_mtime_iso(tmp_path / "core" / "decisions.md", "2026-04-01T00:00:00")
    _set_mtime_iso(tmp_path / "AGENTS.md", "2026-04-02T00:00:00")

    state = collect_agents_md_state(tmp_path)

    assert state.agents_md_present is True
    assert state.claude_md_present is True
    assert state.markers_present is True
    assert state.active_decision_ids == ["D-001"]
    assert state.digest_ids == ["D-001"]
    assert state.agents_md_legacy_at_includes == []
    assert state.claude_md_legacy_at_includes == []
    assert state.claude_md_normalizable is True  # pure `@AGENTS.md`
    assert state.drift_signals == []


def test_collect_agents_md_state_legacy_project_full_drift(tmp_path: Path) -> None:
    _write(
        tmp_path / "CLAUDE.md",
        """
        @AGENTS.md
        @core/overview.md
        @core/decisions.md
        """,
    )
    _write(
        tmp_path / "AGENTS.md",
        """
        @core/overview.md
        @core/decisions.md

        # P — Agent Guide

        Some prose, no markers.
        """,
    )
    _write(
        tmp_path / "core" / "decisions.md",
        """
        ## D-001: One

        - **Status:** active

        ---

        ## D-002: Two

        - **Status:** active
        """,
    )
    _set_mtime_iso(tmp_path / "AGENTS.md", "2026-01-01T00:00:00")
    _set_mtime_iso(tmp_path / "core" / "decisions.md", "2026-04-01T00:00:00")

    state = collect_agents_md_state(tmp_path)

    assert state.agents_md_legacy_at_includes == ["@core/overview.md", "@core/decisions.md"]
    assert state.claude_md_legacy_at_includes == ["@core/overview.md", "@core/decisions.md"]
    assert state.markers_present is False
    assert state.active_decision_ids == ["D-001", "D-002"]
    assert state.digest_ids == []
    assert state.claude_md_normalizable is True
    assert "agents_md_legacy_includes" in state.drift_signals
    assert "claude_md_legacy_includes" in state.drift_signals
    assert "markers_missing" in state.drift_signals
    assert "core_decisions_newer_than_agents_md" in state.drift_signals
    assert "active_decisions_differ_from_digest" in state.drift_signals


def test_collect_agents_md_state_mtime_drift_only(tmp_path: Path) -> None:
    _write(tmp_path / "CLAUDE.md", "@AGENTS.md\n")
    _write(
        tmp_path / "AGENTS.md",
        f"""
        # P — Agent Guide

        {BEGIN_MARKER}
        - **D-001:** Stay calm.
        {END_MARKER}
        """,
    )
    _write(
        tmp_path / "core" / "decisions.md",
        """
        ## D-001: Stay calm (wording updated)

        - **Status:** active
        """,
    )
    _set_mtime_iso(tmp_path / "AGENTS.md", "2026-04-01T00:00:00")
    _set_mtime_iso(tmp_path / "core" / "decisions.md", "2026-04-15T00:00:00")

    state = collect_agents_md_state(tmp_path)

    assert state.active_decision_ids == ["D-001"]
    assert state.digest_ids == ["D-001"]
    assert "core_decisions_newer_than_agents_md" in state.drift_signals
    assert "active_decisions_differ_from_digest" not in state.drift_signals


def test_collect_agents_md_state_no_agents_md(tmp_path: Path) -> None:
    state = collect_agents_md_state(tmp_path)
    assert state.agents_md_present is False
    assert state.claude_md_present is False
    assert state.drift_signals == []


def test_collect_agents_md_state_claude_md_with_extra_content_not_normalizable(tmp_path: Path) -> None:
    _write(
        tmp_path / "CLAUDE.md",
        """
        @AGENTS.md
        @core/overview.md

        # Project-specific guidance
        Always use uv.
        """,
    )
    _write(tmp_path / "AGENTS.md", "# P\n")
    state = collect_agents_md_state(tmp_path)
    assert state.claude_md_legacy_at_includes == ["@core/overview.md"]
    assert state.claude_md_normalizable is False
    assert "claude_md_legacy_includes" in state.drift_signals
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `cd science-tool && uv run pytest tests/test_curate_agents_md.py -v`
Expected: ImportError on `AgentsMdDigestState`, `collect_agents_md_state`.

- [ ] **Step 3: Implement the model and collector**

Prepend the imports and append the model + collector to `science-tool/src/science_tool/curate/agents_md.py`:

At the top, add to the existing imports:

```python
from pydantic import BaseModel, Field
```

At the bottom, append:

```python
class AgentsMdDigestState(BaseModel):
    agents_md_present: bool = False
    claude_md_present: bool = False
    markers_present: bool = False
    agents_md_legacy_at_includes: list[str] = Field(default_factory=list)
    claude_md_legacy_at_includes: list[str] = Field(default_factory=list)
    claude_md_normalizable: bool = False
    active_decision_ids: list[str] = Field(default_factory=list)
    digest_ids: list[str] = Field(default_factory=list)
    decisions_mtime_seconds: float | None = None
    overview_mtime_seconds: float | None = None
    agents_md_mtime_seconds: float | None = None
    drift_signals: list[str] = Field(default_factory=list)


def collect_agents_md_state(project_root: Path) -> AgentsMdDigestState:
    """Gather the inputs `/science:curate` needs to propose AGENTS.md edits."""
    project_root = Path(project_root)
    agents_md = project_root / "AGENTS.md"
    claude_md = project_root / "CLAUDE.md"
    decisions_md = project_root / "core" / "decisions.md"
    overview_md = project_root / "core" / "overview.md"

    state = AgentsMdDigestState(
        agents_md_present=agents_md.is_file(),
        claude_md_present=claude_md.is_file(),
        markers_present=parse_marker_state(agents_md),
        agents_md_legacy_at_includes=detect_legacy_at_includes(agents_md),
        claude_md_legacy_at_includes=detect_legacy_at_includes(claude_md),
        claude_md_normalizable=is_claude_md_normalizable(claude_md),
        active_decision_ids=parse_active_decision_ids(decisions_md),
        digest_ids=parse_digest_ids(agents_md),
        decisions_mtime_seconds=_mtime_seconds(decisions_md),
        overview_mtime_seconds=_mtime_seconds(overview_md),
        agents_md_mtime_seconds=_mtime_seconds(agents_md),
    )
    state.drift_signals = _compute_drift_signals(state)
    return state


def _mtime_seconds(path: Path) -> float | None:
    return path.stat().st_mtime if path.is_file() else None


def _compute_drift_signals(state: AgentsMdDigestState) -> list[str]:
    if not state.agents_md_present:
        return []
    signals: list[str] = []
    if state.agents_md_legacy_at_includes:
        signals.append("agents_md_legacy_includes")
    if state.claude_md_legacy_at_includes:
        signals.append("claude_md_legacy_includes")
    if not state.markers_present:
        signals.append("markers_missing")
    if (
        state.decisions_mtime_seconds is not None
        and state.agents_md_mtime_seconds is not None
        and state.decisions_mtime_seconds > state.agents_md_mtime_seconds
    ):
        signals.append("core_decisions_newer_than_agents_md")
    if state.active_decision_ids != state.digest_ids and state.active_decision_ids:
        signals.append("active_decisions_differ_from_digest")
    return signals
```

- [ ] **Step 4: Run the tests and confirm they pass**

Run: `cd science-tool && uv run pytest tests/test_curate_agents_md.py -v`
Expected: 21 passed.

- [ ] **Step 5: Run ruff and pyright**

Run: `cd science-tool && uv run ruff check src/science_tool/curate/agents_md.py tests/test_curate_agents_md.py`
Expected: no errors.

Run: `cd science-tool && uv run pyright src/science_tool/curate/agents_md.py`
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add science-tool/src/science_tool/curate/agents_md.py science-tool/tests/test_curate_agents_md.py
git commit -m "feat(curate): collect AGENTS.md drift signals via collect_agents_md_state"
```

---

## Task 9: Wire `agents_md` into `CurationInventory`

**Files:**
- Modify: `science-tool/src/science_tool/curate/inventory.py`
- Modify: `science-tool/tests/test_curate_inventory.py`

- [ ] **Step 1: Write the failing test extension**

In `science-tool/tests/test_curate_inventory.py`, after the existing `test_collect_inventory_tracks_counts_and_candidate_signals` test, append a new test:

```python
def test_collect_inventory_includes_agents_md_state(curated_project: Path) -> None:
    # The curated_project fixture has no AGENTS.md / CLAUDE.md / core/.
    # The agents_md state should still be present and report absence cleanly.
    inventory = collect_inventory(curated_project, today=date(2026, 4, 21))
    assert inventory.agents_md is not None
    assert inventory.agents_md.agents_md_present is False
    assert inventory.agents_md.claude_md_present is False
    assert inventory.agents_md.drift_signals == []


def test_collect_inventory_surfaces_agents_md_drift(curated_project: Path) -> None:
    _write(
        curated_project / "AGENTS.md",
        "@core/overview.md\n@core/decisions.md\n\n# project\n",
    )
    _write(curated_project / "CLAUDE.md", "@AGENTS.md\n")
    _write(
        curated_project / "core/decisions.md",
        "## D-001: Thing\n\n- **Status:** active\n",
    )

    inventory = collect_inventory(curated_project, today=date(2026, 4, 21))
    assert inventory.agents_md is not None
    assert inventory.agents_md.agents_md_legacy_at_includes == [
        "@core/overview.md",
        "@core/decisions.md",
    ]
    assert "agents_md_legacy_includes" in inventory.agents_md.drift_signals
    assert "markers_missing" in inventory.agents_md.drift_signals
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `cd science-tool && uv run pytest tests/test_curate_inventory.py -v`
Expected: AttributeError on `inventory.agents_md` for both new tests.

- [ ] **Step 3: Add the field and call site**

In `science-tool/src/science_tool/curate/inventory.py`:

After the existing `from science_tool.tasks import parse_tasks` import line, add:

```python
from science_tool.curate.agents_md import AgentsMdDigestState, collect_agents_md_state
```

Update the `CurationInventory` model (currently lines 68-72) to add the new field:

```python
class CurationInventory(BaseModel):
    project_root: str
    artifact_counts: dict[str, int] = Field(default_factory=dict)
    artifacts: list[InventoryArtifact] = Field(default_factory=list)
    candidate_signals: CandidateSignals = Field(default_factory=CandidateSignals)
    agents_md: AgentsMdDigestState | None = None
```

In `collect_inventory()`, just before the `return CurationInventory(...)` call, add:

```python
    agents_md_state = collect_agents_md_state(project_root)
```

Update the return:

```python
    return CurationInventory(
        project_root=str(project_root),
        artifact_counts=artifact_counts,
        artifacts=artifacts,
        candidate_signals=candidate_signals,
        agents_md=agents_md_state,
    )
```

- [ ] **Step 4: Run the tests and confirm they pass**

Run: `cd science-tool && uv run pytest tests/test_curate_inventory.py -v`
Expected: all tests pass (existing + 2 new).

- [ ] **Step 5: Run ruff and pyright**

Run: `cd science-tool && uv run ruff check src/science_tool/curate/inventory.py tests/test_curate_inventory.py`
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add science-tool/src/science_tool/curate/inventory.py science-tool/tests/test_curate_inventory.py
git commit -m "feat(curate): include AGENTS.md drift state in CurationInventory output"
```

---

## Task 10: Document the `agents-md` theme in `commands/curate.md`

**Files:**
- Modify: `commands/curate.md`

- [ ] **Step 1: Find the candidate-triage / themes area**

Read `commands/curate.md` end-to-end. Identify the section that lists curation themes (around "Phase 2: Candidate triage" — see line 51 in the file's current state). The exact phrasing varies; the new theme description goes alongside the existing ones (forgotten insights, missed links, drift, duplication).

- [ ] **Step 2: Add the agents-md theme description**

After the bulleted list of "Useful targets include:" (or the corresponding themes list), insert this subsection:

```md
### `agents-md` theme

The CLI inventory exposes `agents_md` with the per-project state of `AGENTS.md`,
`CLAUDE.md`, and `core/decisions.md`. Inspect `inventory.agents_md.drift_signals`
and propose edits as follows:

- `agents_md_legacy_includes` present → propose removing the top-of-file
  `@core/overview.md` / `@core/decisions.md` directives from `AGENTS.md`. This
  is structural (no semantic content lost) and is eligible for `--apply-obvious`.
- `claude_md_legacy_includes` present → propose normalizing `CLAUDE.md` to the
  single line `@AGENTS.md`. Eligible for `--apply-obvious` only when
  `inventory.agents_md.claude_md_normalizable` is `true`. Otherwise show the
  diff and require user approval (CLAUDE.md carries non-include content that
  must be moved manually, typically into `AGENTS.md`).
- `markers_missing` → propose inserting the `BEGIN: load-bearing-constraints`
  / `END: load-bearing-constraints` markers in `AGENTS.md` (canonical wording
  in `templates/agents-md.md`) along with a freshly drafted digest. This
  always requires user approval.
- `core_decisions_newer_than_agents_md` or `active_decisions_differ_from_digest`
  → read `core/decisions.md`, draft a one-line imperative rule per
  `inventory.agents_md.active_decision_ids`, and propose replacing the content
  between the existing markers. Always requires user approval (semantic
  judgement on rule wording).

Drop the entire theme silently when `inventory.agents_md.drift_signals` is
empty.
```

- [ ] **Step 3: Verify**

Run: `grep -nF 'agents-md' commands/curate.md`
Expected: at least one match (the new section heading).

- [ ] **Step 4: Commit**

```bash
git add commands/curate.md
git commit -m "docs(commands): document agents-md theme in /science:curate"
```

---

## Task 11: Rewrite `meta/AGENTS.md` to the new shape

**Files:**
- Modify: `meta/AGENTS.md`

- [ ] **Step 1: Replace `meta/AGENTS.md` end-to-end**

Use the Write tool to overwrite `meta/AGENTS.md` with the following content (drops the two top-of-file `@core/` directives, adds the markers + digest of D-001..D-004, leaves the rest of the operational content intact):

```md
# science-meta — Agent Guide

## What this is

A Science project that takes the **Science toolkit itself** as its object of
study and development. The toolkit code lives at `../science-tool/`, `../aspects/`,
`../skills/`, `../commands/`, `../templates/`, `../references/`. This project
does not contain that code — it contains the research artifacts, decisions,
hypotheses, tasks, knowledge graph, and literature review that drive it.

## Profile

`software` with an embedded research layer (`doc/background/`,
`doc/questions/`, `specs/hypotheses/`, `doc/interpretations/`).

## Working directory convention

Science commands resolve the project from `science.yaml`. Always run them
from `meta/`, or pass `--project meta` / `--project-root .` as appropriate.
The tool lives at `../science-tool/` — `.env` points `SCIENCE_TOOL_PATH` there.

## Validation

```bash
bash validate.sh --verbose
```

## Conventions

- Paths to tool code use `../science-tool/...` from inside `meta/`.
- Hypotheses are about the tool's design and the research-workflow model it
  implements, not about an external scientific domain.
- Literature in `doc/background/papers/` focuses on: research-agent design,
  knowledge-graph modelling, causal inference workflows, scientific-process
  ontologies, and related tooling (e.g. CrossCompute, Galaxy, Nextflow,
  Jupyter, Obsidian-style PKMs).
- Decisions that constrain the tool's architecture go in `core/decisions.md`.
  Decisions about meta-project process only go in `doc/plans/`.

## Task execution

- Use `/science:tasks` for backlog management.
- Tasks that touch tool code should be done from the repo root (`..`) on a
  feature branch; keep the meta-project commits scoped to `meta/`.

## Known issues / nuances

- `meta/src/` holds project-shipped Python packages (starting with
  `h01_simulator`, the H01 test instrument). See `core/decisions.md` D-004.
- `meta/pyproject.toml` is a full package manifest: it declares the shipped
  packages, registers CLI entry points (e.g. `h01-sim`), and carries runtime
  plus dev dependencies. `uv sync` from `meta/` produces a working
  environment.
- Notebooks live at `meta/notebooks/` rather than `meta/code/notebooks/` —
  the software profile warns on top-level `code/`.

<!-- BEGIN: load-bearing-constraints (managed by /science:curate; edit core/decisions.md instead) -->
## Load-bearing constraints

- **D-001:** Run science commands from `meta/` (or with `--project meta`); commits touching tool code stay scoped to the repo root, not `meta/`.
- **D-002:** Implementation root is `src/`, not `code/`; no `RESEARCH_PLAN.md` (the strategic plan lives in `README.md`).
- **D-003:** Tool-level beliefs are continuous probabilities strictly bounded away from 0 and 1; do not collapse beliefs to 0 or 1 in code paths, and decisions that need a binary choice compute it from the belief at the decision point.
- **D-004:** Shipped Python packages live under `meta/src/` (e.g. `h01_simulator`); notebooks under `meta/notebooks/`; `uv sync` from `meta/` is the setup step.
<!-- END: load-bearing-constraints -->

## Pointers

- Decisions: `core/decisions.md`
- Project overview: `core/overview.md`
- Active tasks: `tasks/active.md`
- Hypotheses: `specs/hypotheses/`
- Strategic plan: `README.md`
```

- [ ] **Step 2: Verify the new file has no `@core/` includes and parses through the new collector**

Run: `grep -nF '@core/' meta/AGENTS.md`
Expected: no output.

Run from repo root:

```bash
cd science-tool && uv run python -c "
from pathlib import Path
from science_tool.curate.agents_md import collect_agents_md_state
state = collect_agents_md_state(Path('../meta'))
print('drift_signals:', state.drift_signals)
print('digest_ids:', state.digest_ids)
print('active_decision_ids:', state.active_decision_ids)
print('claude_md_normalizable:', state.claude_md_normalizable)
"
```

Expected output:

- `drift_signals` is `[]` (or contains only `core_decisions_newer_than_agents_md` due to mtime ordering — that is fine; touching the file in step 1 brought AGENTS.md mtime to "now", which is newer than `core/decisions.md` last edit).
- `digest_ids: ['D-001', 'D-002', 'D-003', 'D-004']`
- `active_decision_ids: ['D-001', 'D-002', 'D-003', 'D-004']`
- `claude_md_normalizable: True`

- [ ] **Step 3: Commit**

```bash
git add meta/AGENTS.md
git commit -m "docs(meta): rewrite meta/AGENTS.md as worked example of new shape"
```

---

## Task 12: Regenerate `codex-skills/` and add a smoke test

**Files:**
- Modify (regenerated): `codex-skills/**/SKILL.md`
- Modify: `science-tool/tests/test_codex_skills.py` (or create a new smoke test if no equivalent exists)

- [ ] **Step 1: Regenerate the codex-skills**

Run from the repo root:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run --project science-tool python scripts/generate_codex_skills.py
```

Expected: `Generated Codex skills in /mnt/ssd/Dropbox/science/codex-skills`

- [ ] **Step 2: Verify no generated SKILL.md still references `@core/*`**

Run:

```bash
grep -rnE '@core/(overview|decisions)\.md' codex-skills/
```

Expected: no output.

- [ ] **Step 3: Find or create a codex-skills test file**

Run: `ls science-tool/tests/ | grep -i codex`

If a test file exists, append the smoke test below to it. If none exists, create `science-tool/tests/test_codex_skills_no_core_includes.py`:

```python
"""Smoke test: generated Codex skills do not reference @core/*.md includes."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CODEX_SKILLS_ROOT = REPO_ROOT / "codex-skills"


def test_no_generated_skill_references_at_core_includes() -> None:
    if not CODEX_SKILLS_ROOT.is_dir():
        return  # Repo checkout without generated artifacts; skip silently.
    offenders: list[str] = []
    for skill_md in CODEX_SKILLS_ROOT.rglob("SKILL.md"):
        text = skill_md.read_text(encoding="utf-8")
        if "@core/overview.md" in text or "@core/decisions.md" in text:
            offenders.append(str(skill_md.relative_to(REPO_ROOT)))
    assert not offenders, (
        "Generated codex-skills must not reference @core/*.md includes. "
        "Regenerate via scripts/generate_codex_skills.py after editing commands/. "
        f"Offenders: {offenders}"
    )
```

- [ ] **Step 4: Run the smoke test**

Run: `cd science-tool && uv run pytest tests/test_codex_skills_no_core_includes.py -v`
Expected: PASS.

- [ ] **Step 5: Add a complementary smoke test for the template**

Append to the same file (or a sibling test file):

```python
def test_agents_md_template_has_no_at_core_includes() -> None:
    template = REPO_ROOT / "templates" / "agents-md.md"
    text = template.read_text(encoding="utf-8")
    assert "@core/overview.md" not in text
    assert "@core/decisions.md" not in text
```

Run it: `cd science-tool && uv run pytest tests/test_codex_skills_no_core_includes.py -v`
Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add codex-skills/ science-tool/tests/test_codex_skills_no_core_includes.py
git commit -m "build(codex-skills): regenerate without @core includes; add smoke tests"
```

---

## Task 13: Final validation

- [ ] **Step 1: Run the full test suite**

Run: `cd science-tool && uv run pytest -q`
Expected: all tests pass.

- [ ] **Step 2: Run ruff and pyright on touched modules**

Run: `cd science-tool && uv run ruff check src/science_tool/curate/ tests/test_curate_*.py tests/test_codex_skills_no_core_includes.py`
Expected: no errors.

Run: `cd science-tool && uv run pyright src/science_tool/curate/`
Expected: no errors.

- [ ] **Step 3: Run `meta` validation**

Run: `cd meta && bash validate.sh --verbose`
Expected: no new errors. Pre-existing warnings are acceptable.

- [ ] **Step 4: Verify the meta drift signals are clean**

Run from repo root:

```bash
cd science-tool && uv run python -c "
from pathlib import Path
from science_tool.curate.inventory import collect_inventory
inv = collect_inventory(Path('../meta'))
print(inv.agents_md.model_dump_json(indent=2))
"
```

Expected: `agents_md_legacy_at_includes` is `[]`, `claude_md_legacy_at_includes` is `[]`, `markers_present` is `true`, `digest_ids` matches `active_decision_ids`.

- [ ] **Step 5: Final summary commit (if anything was touched in step 4)**

If steps 1-4 produced no changes, no commit needed; the plan is complete.

---

## Self-Review Notes

- **Spec coverage:** Every section of `docs/plans/2026-04-30-agents-md-decoupling-design.md` is implemented:
  - §1 AGENTS.md shape → Task 1 (template), Task 11 (live example).
  - §2 digest mechanics + active-only → Task 5 (active-ID parser), Task 6 (digest IDs/markers), Task 11 (worked digest).
  - §3 drift detection in /science:curate → Tasks 5-9 (helper + wiring), Task 10 (theme docs).
  - §4 doc/template updates → Tasks 2, 3, 4, 12 (codex-skills regen).
  - §5 meta/AGENTS.md → Task 11.
  - Testing section → Tasks 5-9 (TDD throughout), Task 12 (smoke tests).
- **Placeholder scan:** No "TBD" / "TODO" / "implement appropriate". All code blocks are concrete.
- **Type consistency:** Field names (`drift_signals`, `agents_md_legacy_at_includes`, `claude_md_normalizable`, `digest_ids`, `active_decision_ids`) are stable across Tasks 5-11. Constants (`BEGIN_MARKER`, `END_MARKER`) match between template (Task 1) and parser (Task 6).

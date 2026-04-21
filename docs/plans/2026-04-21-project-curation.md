# Project Curation Sweep Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship `/science:curate`, an agent-led project memory curation workflow that surfaces forgotten insights, missed links, drift, duplication, and safe curation fixes.

**Architecture:** The command and Codex skill carry the semantic workflow. A narrow `science_tool.curate` Python module provides deterministic inventory JSON only; it does not decide what to edit. The agent reads inventory candidates plus targeted source artifacts, optionally applies high-confidence local edits, and writes a durable curation ledger.

**Tech Stack:** Python 3.11+, click, pytest, ruff, pyright, existing `science-tool` graph/task/health helpers, Markdown command and skill docs.

**Spec:** `docs/specs/2026-04-21-project-curation-design.md`

---

## File Structure

### New files

- `science-tool/src/science_tool/curate/__init__.py` - module marker.
- `science-tool/src/science_tool/curate/inventory.py` - deterministic project corpus inventory helpers.
- `science-tool/src/science_tool/curate/cli.py` - `science-tool curate inventory` command.
- `science-tool/tests/test_curate_inventory.py` - unit tests for inventory collection.
- `science-tool/tests/test_curate_cli.py` - CLI registration and JSON smoke tests.
- `commands/curate.md` - `/science:curate` command orchestration.
- `codex-skills/science-curate/SKILL.md` - Codex skill version of the command.

### Modified files

- `science-tool/src/science_tool/cli.py` - register `curate_group`.

### Explicit non-goals

- Do not build automated semantic classification into `science-tool`.
- Do not add embedding search in v1.
- Do not auto-merge hypotheses, retire tasks, or rewrite DAG evidence status.
- Do not modify existing command semantics except to reference `/science:curate` where appropriate in future docs.

## Task 1: Scaffold `science_tool.curate` and register CLI group

**Files:**
- Create: `science-tool/src/science_tool/curate/__init__.py`
- Create: `science-tool/src/science_tool/curate/cli.py`
- Modify: `science-tool/src/science_tool/cli.py`
- Test: `science-tool/tests/test_curate_cli.py`

- [ ] **Step 1: Write failing CLI registration test**

Create `science-tool/tests/test_curate_cli.py`:

```python
from __future__ import annotations

from click.testing import CliRunner

from science_tool.cli import main


def test_curate_group_registered() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["curate", "--help"])
    assert result.exit_code == 0
    assert "inventory" in result.output
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd science-tool
uv run --frozen pytest tests/test_curate_cli.py -v
```

Expected: FAIL because `curate` is not registered.

- [ ] **Step 3: Add module skeleton**

Create `science-tool/src/science_tool/curate/__init__.py`:

```python
"""Project curation inventory helpers for /science:curate."""

from __future__ import annotations
```

Create `science-tool/src/science_tool/curate/cli.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

import click


@click.group("curate")
def curate_group() -> None:
    """Tools supporting the /science:curate command."""


@curate_group.command("inventory")
@click.option("--project-root", type=click.Path(path_type=Path), default=Path("."), show_default=True)
@click.option("--format", "output_format", type=click.Choice(["json"]), default="json", show_default=True)
def inventory_cmd(project_root: Path, output_format: str) -> None:
    """Print a deterministic project corpus inventory."""
    payload = {"project_root": str(project_root), "artifact_counts": {}}
    click.echo(json.dumps(payload, indent=2, sort_keys=True))
```

- [ ] **Step 4: Register the CLI group**

In `science-tool/src/science_tool/cli.py`, import and register `curate_group` using the same pattern as `big_picture_group`.

- [ ] **Step 5: Run test to verify it passes**

```bash
cd science-tool
uv run --frozen pytest tests/test_curate_cli.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add science-tool/src/science_tool/curate science-tool/src/science_tool/cli.py science-tool/tests/test_curate_cli.py
git commit -m "feat(curate): scaffold curation inventory CLI"
```

## Task 2: Implement deterministic project inventory

**Files:**
- Modify: `science-tool/src/science_tool/curate/inventory.py`
- Modify: `science-tool/src/science_tool/curate/cli.py`
- Test: `science-tool/tests/test_curate_inventory.py`

- [ ] **Step 1: Write failing inventory tests**

Create tests that build a tiny project with `science.yaml`, `specs/hypotheses/h1.md`, `doc/questions/q1.md`, `doc/papers/p1.md`, `doc/interpretations/i1.md`, `tasks/active.md`, and `tasks/done/2026-04-01.md`.

Assert that `collect_inventory(project_root)` returns:

- artifact counts by class;
- paths with missing `related`;
- paths with missing `source_refs` for artifact types where that field is expected;
- documents with no outbound links;
- recently modified and long-idle lists are deterministic when `today` is passed in.

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd science-tool
uv run --frozen pytest tests/test_curate_inventory.py -v
```

- [ ] **Step 3: Implement typed inventory models**

Use `dataclasses` or Pydantic following local patterns. Keep the output JSON-serializable and simple:

```python
type ArtifactClass = str


class InventoryArtifact(BaseModel):
    path: str
    artifact_class: ArtifactClass
    id: str | None = None
    title: str | None = None
    related_count: int = 0
    source_refs_count: int = 0
    modified_days_ago: int | None = None
```

Include a top-level `CurationInventory` with `artifact_counts`, `artifacts`, and `candidate_signals`.

- [ ] **Step 4: Implement markdown/frontmatter scanning**

Scan only known Science locations:

- `specs/**/*.md`
- `doc/**/*.md`
- `tasks/active.md`
- `tasks/done/**/*.md`
- `knowledge/sources/**/*.yaml`

Use existing frontmatter helpers if a suitable one exists; otherwise keep a small module-local parser. Do not add broad filesystem traversal.

- [ ] **Step 5: Wire CLI to inventory implementation**

`science-tool curate inventory --project-root . --format json` should print the model as sorted JSON.

- [ ] **Step 6: Run targeted tests**

```bash
cd science-tool
uv run --frozen pytest tests/test_curate_inventory.py tests/test_curate_cli.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add science-tool/src/science_tool/curate science-tool/tests/test_curate_inventory.py science-tool/tests/test_curate_cli.py
git commit -m "feat(curate): add project inventory helper"
```

## Task 3: Write `/science:curate` command

**Files:**
- Create: `commands/curate.md`

- [ ] **Step 1: Draft command frontmatter**

Use this description:

```yaml
---
description: Agent-led project memory curation sweep. Surfaces forgotten insights, missed links, drift, duplication, safe fixes, and pending decisions across a Science project.
---
```

- [ ] **Step 2: Add command workflow**

Include phases from the spec:

1. setup and inventory;
2. candidate triage;
3. targeted reading;
4. semantic curation;
5. ledger write or `--no-write` preview;
6. verification;
7. self-reflection.

- [ ] **Step 3: Add mutation safety rules**

Copy the high/medium/low confidence rules from the spec. Make default mode approval-gated; make `--apply-obvious` limited to small, local, evidence-backed metadata edits.

- [ ] **Step 4: Add ledger template**

Require `doc/meta/curation/curation-sweep-YYYY-MM-DD.md` with the sections from the spec, including **Self-Reflection**.

- [ ] **Step 5: Commit**

```bash
git add commands/curate.md
git commit -m "feat(curate): add curation sweep command"
```

## Task 4: Add Codex skill

**Files:**
- Create: `codex-skills/science-curate/SKILL.md`

- [ ] **Step 1: Convert command to skill format**

Use frontmatter:

```yaml
---
name: science-curate
description: "Run an agent-led project memory curation sweep. Use when the user says curate, curation sweep, forgotten insights, missed connections, drift, cleanup research memory, or explicitly references `science-curate` or `/science:curate`."
---
```

- [ ] **Step 2: Include Science Codex Command Preamble**

Copy the current preamble style from nearby science skills such as `science-big-picture` or `science-next-steps`.

- [ ] **Step 3: Port the command workflow**

Ensure the skill clearly says CLI helpers are evidence-gathering tools and the agent is responsible for semantic judgement.

- [ ] **Step 4: Include self-reflection prompt**

The skill must require a final **Self-Reflection** section in the ledger.

- [ ] **Step 5: Commit**

```bash
git add codex-skills/science-curate/SKILL.md
git commit -m "feat(curate): add Codex curation skill"
```

## Task 5: Verification and polish

**Files:**
- Review: `docs/specs/2026-04-21-project-curation-design.md`
- Review: `docs/plans/2026-04-21-project-curation.md`
- Review: `commands/curate.md`
- Review: `codex-skills/science-curate/SKILL.md`
- Review: `science-tool/src/science_tool/curate/*`
- Review: `science-tool/tests/test_curate_*.py`

- [ ] **Step 1: Run focused tests**

```bash
cd science-tool
uv run --frozen pytest tests/test_curate_inventory.py tests/test_curate_cli.py -v
```

- [ ] **Step 2: Run formatting and lint**

```bash
cd science-tool
uv run --frozen ruff format .
uv run --frozen ruff check .
```

- [ ] **Step 3: Run type check**

```bash
cd science-tool
uv run --frozen pyright
```

If unrelated pre-existing pyright errors appear, record them in the final implementation notes and do not fix them unless they are caused by this work.

- [ ] **Step 4: Smoke test command docs manually**

From a real Science project, invoke `/science:curate --dry-run` or follow `commands/curate.md` manually and confirm the expected ledger shape can be produced without mutation.

- [ ] **Step 5: Final commit**

```bash
git add docs/specs/2026-04-21-project-curation-design.md docs/plans/2026-04-21-project-curation.md
git commit -m "docs(curate): design project curation sweep"
```

## Handoff Notes

- Keep implementation incremental. The useful part is the agent workflow; the CLI inventory should stay boring and deterministic.
- Treat false positives as a design bug. If inventory output is noisy, narrow it rather than adding more candidate categories.
- The self-reflection section is not optional. It is the feedback loop that will make future curation sweeps better.

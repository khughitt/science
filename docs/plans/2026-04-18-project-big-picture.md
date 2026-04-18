# Project Big-Picture Synthesis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship `/science:big-picture`, a command that generates a multi-scale, hypothesis-organized synthesis of a research project.

**Architecture:** The algorithmic core (question→hypothesis resolver, output validator) lives in a new `science_tool.big_picture` Python module with unit tests. Orchestration, bundle assembly, and narrative generation live in a new markdown command (`commands/big-picture.md`) that dispatches two sub-agent prompts (`agents/hypothesis-synthesizer.md`, `agents/emergent-threads-synthesizer.md`). Fixture tests exercise the Python core against synthetic projects; smoke tests exercise end-to-end generation against pinned SHAs of mm30 and natural-systems.

**Tech Stack:** Python 3.11+, click, PyYAML, pytest (for `science-tool`). Markdown prompts for the command and sub-agents. Existing `science-tool graph …` CLI surfaces are reused, not replaced.

**Spec:** `docs/specs/2026-04-18-project-big-picture-design.md`

---

## File Structure

### New files

- `science-tool/src/science_tool/big_picture/__init__.py` — module marker, exposes public types
- `science-tool/src/science_tool/big_picture/frontmatter.py` — tiny YAML-frontmatter parser (`read_frontmatter(path) -> dict | None`)
- `science-tool/src/science_tool/big_picture/resolver.py` — question→hypothesis resolver (many-to-many)
- `science-tool/src/science_tool/big_picture/validator.py` — validates generated synthesis files against spec's acceptance criteria
- `science-tool/src/science_tool/big_picture/cli.py` — registers a `big-picture` click group with `resolve-questions` and `validate` subcommands
- `science-tool/tests/fixtures/big_picture/minimal_project/` — synthetic test project (tiny hypothesis/question/interpretation set)
- `science-tool/tests/test_big_picture_frontmatter.py`
- `science-tool/tests/test_big_picture_resolver.py`
- `science-tool/tests/test_big_picture_validator.py`
- `science-tool/tests/test_big_picture_cli.py`
- `agents/hypothesis-synthesizer.md` — per-hypothesis sub-agent prompt
- `agents/emergent-threads-synthesizer.md` — emergent-threads sub-agent prompt
- `commands/big-picture.md` — main command orchestration

### Modified files

- `science-tool/src/science_tool/cli.py` — register the `big_picture` group onto `main`

### Not changed

- `commands/status.md`, `commands/health.md`, `commands/next-steps.md`, `commands/compare-hypotheses.md` — unchanged per spec.
- `core/overview.md` — unchanged; user continues to curate manually.
- `.edges.yaml` → graph claim migration — deferred (separate roadmap item).
- Question template — Gap-1 fix is a sibling spec, not part of this plan.

### Design notes

- `frontmatter.py` is module-local rather than a cross-cutting utility. `science_tool.prose` has a similar helper but is too narrowly scoped (only pulls `ontology_terms`). Extracting a shared utility is out of scope; module-local is fine and avoids touching unrelated modules.
- The resolver does **not** modify project files. It reads frontmatter and emits JSON.
- The validator does not generate content either; it reads already-generated synthesis files and asserts structural / referential properties against the source project.
- Bundle assembly (reading hypothesis files + related tasks/interpretations/edges.yaml and writing them to a sub-agent bundle) lives entirely in `commands/big-picture.md` as instruction prose and inline bash. This matches the spec's decision not to add a new CLI for bundle assembly in v1.

---

## Task 1: Scaffold `big_picture` module and wire into CLI

**Files:**
- Create: `science-tool/src/science_tool/big_picture/__init__.py`
- Create: `science-tool/src/science_tool/big_picture/cli.py`
- Modify: `science-tool/src/science_tool/cli.py`
- Test: `science-tool/tests/test_big_picture_cli.py`

- [ ] **Step 1: Write the failing test**

Create `science-tool/tests/test_big_picture_cli.py`:

```python
from __future__ import annotations

from click.testing import CliRunner

from science_tool.cli import main


def test_big_picture_group_registered() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["big-picture", "--help"])
    assert result.exit_code == 0
    assert "resolve-questions" in result.output
    assert "validate" in result.output
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /mnt/ssd/Dropbox/science/science-tool && uv run pytest tests/test_big_picture_cli.py -v
```

Expected: FAIL (the `big-picture` group doesn't exist yet).

- [ ] **Step 3: Create the module skeleton**

Create `science-tool/src/science_tool/big_picture/__init__.py`:

```python
"""Big-picture synthesis: question→hypothesis resolver and output validator."""
from __future__ import annotations
```

Create `science-tool/src/science_tool/big_picture/cli.py`:

```python
from __future__ import annotations

import click


@click.group("big-picture")
def big_picture_group() -> None:
    """Tools supporting the /science:big-picture command."""


@big_picture_group.command("resolve-questions")
def resolve_questions_cmd() -> None:
    """Placeholder — implemented in Task 8."""
    raise click.ClickException("Not yet implemented")


@big_picture_group.command("validate")
def validate_cmd() -> None:
    """Placeholder — implemented in Task 12."""
    raise click.ClickException("Not yet implemented")
```

- [ ] **Step 4: Register the group in the main CLI**

Edit `science-tool/src/science_tool/cli.py`. Near the top (with other module imports around lines 1–70), add:

```python
from science_tool.big_picture.cli import big_picture_group
```

At the bottom of the file (after all other `main.add_command(...)` calls, if any; if the pattern is `@main.group()` decorators only, add a `main.add_command(big_picture_group)` line after the `main` definition block). Use the same pattern as existing groups like `research_package_group` — grep `research_package_group` in `cli.py` to see where and how it's wired.

- [ ] **Step 5: Run test to verify it passes**

```bash
cd /mnt/ssd/Dropbox/science/science-tool && uv run pytest tests/test_big_picture_cli.py -v
```

Expected: PASS.

- [ ] **Step 6: Verify the CLI end-to-end**

```bash
cd /mnt/ssd/Dropbox/science/science-tool && uv run science-tool big-picture --help
```

Expected output includes `resolve-questions` and `validate` as subcommands.

- [ ] **Step 7: Commit**

```bash
git add science-tool/src/science_tool/big_picture/ science-tool/src/science_tool/cli.py science-tool/tests/test_big_picture_cli.py
git commit -m "feat(big-picture): scaffold module and register CLI group"
```

---

## Task 2: Frontmatter parser utility

**Files:**
- Create: `science-tool/src/science_tool/big_picture/frontmatter.py`
- Test: `science-tool/tests/test_big_picture_frontmatter.py`

- [ ] **Step 1: Write the failing tests**

Create `science-tool/tests/test_big_picture_frontmatter.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.big_picture.frontmatter import read_frontmatter


def test_parses_valid_frontmatter(tmp_path: Path) -> None:
    f = tmp_path / "q.md"
    f.write_text('---\nid: "question:q01"\nrelated:\n  - "hypothesis:h1"\n---\nBody text.\n')
    assert read_frontmatter(f) == {"id": "question:q01", "related": ["hypothesis:h1"]}


def test_returns_none_when_no_frontmatter(tmp_path: Path) -> None:
    f = tmp_path / "q.md"
    f.write_text("No frontmatter here.\n")
    assert read_frontmatter(f) is None


def test_returns_none_when_unterminated(tmp_path: Path) -> None:
    f = tmp_path / "q.md"
    f.write_text("---\nid: broken\n(no closing)\n")
    assert read_frontmatter(f) is None


def test_returns_empty_dict_when_frontmatter_is_empty(tmp_path: Path) -> None:
    f = tmp_path / "q.md"
    f.write_text("---\n---\nBody.\n")
    assert read_frontmatter(f) == {}


def test_returns_none_on_invalid_yaml(tmp_path: Path) -> None:
    f = tmp_path / "q.md"
    f.write_text("---\nid: [unclosed\n---\n")
    assert read_frontmatter(f) is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /mnt/ssd/Dropbox/science/science-tool && uv run pytest tests/test_big_picture_frontmatter.py -v
```

Expected: FAIL (module not found).

- [ ] **Step 3: Implement the parser**

Create `science-tool/src/science_tool/big_picture/frontmatter.py`:

```python
"""YAML frontmatter parser for Science project markdown files."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def read_frontmatter(path: Path) -> dict[str, Any] | None:
    """Read YAML frontmatter from a markdown file.

    Returns the parsed frontmatter as a dict, or None if the file has no
    frontmatter, the frontmatter block is unterminated, or the YAML is invalid.
    An empty frontmatter block returns an empty dict.
    """
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end == -1:
        return None
    block = text[3:end]
    try:
        data = yaml.safe_load(block)
    except yaml.YAMLError:
        return None
    if data is None:
        return {}
    if not isinstance(data, dict):
        return None
    return data
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /mnt/ssd/Dropbox/science/science-tool && uv run pytest tests/test_big_picture_frontmatter.py -v
```

Expected: 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add science-tool/src/science_tool/big_picture/frontmatter.py science-tool/tests/test_big_picture_frontmatter.py
git commit -m "feat(big-picture): frontmatter parser utility"
```

---

## Task 3: Build synthetic test fixture project

**Files:**
- Create: `science-tool/tests/fixtures/big_picture/minimal_project/specs/hypotheses/h1-alpha.md`
- Create: `science-tool/tests/fixtures/big_picture/minimal_project/specs/hypotheses/h2-beta.md`
- Create: `science-tool/tests/fixtures/big_picture/minimal_project/doc/questions/q01-direct-to-h1.md`
- Create: `science-tool/tests/fixtures/big_picture/minimal_project/doc/questions/q02-inverse-via-h1.md`
- Create: `science-tool/tests/fixtures/big_picture/minimal_project/doc/questions/q03-transitive-via-interp.md`
- Create: `science-tool/tests/fixtures/big_picture/minimal_project/doc/questions/q04-cross-cutting.md`
- Create: `science-tool/tests/fixtures/big_picture/minimal_project/doc/questions/q05-orphan.md`
- Create: `science-tool/tests/fixtures/big_picture/minimal_project/doc/interpretations/i01-h1-q03.md`
- Create: `science-tool/tests/fixtures/big_picture/minimal_project/doc/interpretations/i02-h1-h2-q04.md`
- Create: `science-tool/tests/fixtures/big_picture/minimal_project/science.yaml`

- [ ] **Step 1: Create project manifest**

Create `science-tool/tests/fixtures/big_picture/minimal_project/science.yaml`:

```yaml
name: "big-picture-minimal"
profile: "research"
```

- [ ] **Step 2: Create two hypothesis files**

Create `specs/hypotheses/h1-alpha.md`:

```markdown
---
id: "hypothesis:h1-alpha"
type: "hypothesis"
title: "H1: Alpha"
status: "supported"
related:
  - "question:q02-inverse-via-h1"
  - "question:q04-cross-cutting"
---
Body of h1.
```

Create `specs/hypotheses/h2-beta.md`:

```markdown
---
id: "hypothesis:h2-beta"
type: "hypothesis"
title: "H2: Beta"
status: "supported"
related:
  - "question:q04-cross-cutting"
---
Body of h2.
```

- [ ] **Step 3: Create five question files**

Create `doc/questions/q01-direct-to-h1.md`:

```markdown
---
id: "question:q01-direct-to-h1"
type: "question"
hypothesis: "hypothesis:h1-alpha"
---
Direct-match question.
```

Create `doc/questions/q02-inverse-via-h1.md`:

```markdown
---
id: "question:q02-inverse-via-h1"
type: "question"
related:
  - "topic:something"
---
Inverse-match: linked from h1.
```

Create `doc/questions/q03-transitive-via-interp.md`:

```markdown
---
id: "question:q03-transitive-via-interp"
type: "question"
---
Transitive: linked only via interpretation i01.
```

Create `doc/questions/q04-cross-cutting.md`:

```markdown
---
id: "question:q04-cross-cutting"
type: "question"
---
Cross-cutting: listed in both h1 and h2 as related.
```

Create `doc/questions/q05-orphan.md`:

```markdown
---
id: "question:q05-orphan"
type: "question"
---
Orphan: no hypothesis association anywhere.
```

- [ ] **Step 4: Create two interpretation files**

Create `doc/interpretations/i01-h1-q03.md`:

```markdown
---
id: "interpretation:i01-h1-q03"
type: "interpretation"
created: "2026-04-01"
related:
  - "question:q03-transitive-via-interp"
  - "hypothesis:h1-alpha"
---
Interpretation linking q03 and h1 transitively.
```

Create `doc/interpretations/i02-h1-h2-q04.md`:

```markdown
---
id: "interpretation:i02-h1-h2-q04"
type: "interpretation"
created: "2026-04-10"
related:
  - "question:q04-cross-cutting"
  - "hypothesis:h1-alpha"
  - "hypothesis:h2-beta"
---
Interpretation confirming q04 spans both hypotheses.
```

- [ ] **Step 5: Verify fixture with a quick sanity check**

```bash
find /mnt/ssd/Dropbox/science/science-tool/tests/fixtures/big_picture/minimal_project -type f | sort
```

Expected: 11 files (science.yaml + 2 hypotheses + 5 questions + 2 interpretations + verify the parent dirs exist).

- [ ] **Step 6: Commit**

```bash
git add science-tool/tests/fixtures/big_picture/
git commit -m "test(big-picture): synthetic fixture project for resolver tests"
```

---

## Task 4: Resolver — direct-match fallback

**Files:**
- Create: `science-tool/src/science_tool/big_picture/resolver.py`
- Test: `science-tool/tests/test_big_picture_resolver.py`

- [ ] **Step 1: Write the failing test**

Create `science-tool/tests/test_big_picture_resolver.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.big_picture.resolver import HypothesisMatch, ResolverOutput, resolve_questions

FIXTURE = Path(__file__).parent / "fixtures" / "big_picture" / "minimal_project"


def test_direct_match() -> None:
    result = resolve_questions(FIXTURE)
    q01 = result["question:q01-direct-to-h1"]
    assert q01.primary_hypothesis == "hypothesis:h1-alpha"
    assert any(
        m.id == "hypothesis:h1-alpha" and m.confidence == "direct"
        for m in q01.hypotheses
    )
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /mnt/ssd/Dropbox/science/science-tool && uv run pytest tests/test_big_picture_resolver.py -v
```

Expected: FAIL (module not found).

- [ ] **Step 3: Implement the minimal resolver**

Create `science-tool/src/science_tool/big_picture/resolver.py`:

```python
"""Question→hypothesis resolver.

Resolves many-to-many associations using a fallback chain:
1. Direct: question frontmatter declares `hypothesis: <id>` or list of ids
2. Inverse: hypothesis frontmatter's `related:` lists the question
3. Transitive: interpretation frontmatter's `related:` contains both q and h
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from science_tool.big_picture.frontmatter import read_frontmatter

Confidence = Literal["direct", "inverse", "transitive"]


@dataclass(frozen=True)
class HypothesisMatch:
    id: str
    confidence: Confidence
    score: float


@dataclass(frozen=True)
class ResolverOutput:
    hypotheses: list[HypothesisMatch] = field(default_factory=list)
    primary_hypothesis: str | None = None


def resolve_questions(project_root: Path) -> dict[str, ResolverOutput]:
    """Resolve all questions in ``project_root`` to hypothesis associations."""
    questions = _load_entities(project_root / "doc" / "questions")
    hypotheses = _load_entities(project_root / "specs" / "hypotheses")

    results: dict[str, dict[str, HypothesisMatch]] = {qid: {} for qid in questions}

    # Direct: question frontmatter declares hypothesis.
    for qid, qfm in questions.items():
        for hid in _as_list(qfm.get("hypothesis")):
            results[qid][hid] = HypothesisMatch(hid, "direct", 1.0)

    return {qid: _finalize(matches) for qid, matches in results.items()}


def _load_entities(directory: Path) -> dict[str, dict]:
    if not directory.is_dir():
        return {}
    out: dict[str, dict] = {}
    for path in sorted(directory.glob("*.md")):
        fm = read_frontmatter(path)
        if fm and "id" in fm:
            out[str(fm["id"])] = fm
    return out


def _as_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value]
    return [str(value)]


def _finalize(matches: dict[str, HypothesisMatch]) -> ResolverOutput:
    if not matches:
        return ResolverOutput()
    ranked = sorted(
        matches.values(),
        key=lambda m: (_conf_rank(m.confidence), -m.score),
    )
    return ResolverOutput(hypotheses=ranked, primary_hypothesis=ranked[0].id)


def _conf_rank(c: Confidence) -> int:
    return {"direct": 0, "inverse": 1, "transitive": 2}[c]
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /mnt/ssd/Dropbox/science/science-tool && uv run pytest tests/test_big_picture_resolver.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science-tool/src/science_tool/big_picture/resolver.py science-tool/tests/test_big_picture_resolver.py
git commit -m "feat(big-picture): resolver — direct-match fallback"
```

---

## Task 5: Resolver — inverse-top-down fallback

**Files:**
- Modify: `science-tool/src/science_tool/big_picture/resolver.py`
- Test: `science-tool/tests/test_big_picture_resolver.py`

- [ ] **Step 1: Add the failing test**

Append to `science-tool/tests/test_big_picture_resolver.py`:

```python
def test_inverse_match() -> None:
    result = resolve_questions(FIXTURE)
    q02 = result["question:q02-inverse-via-h1"]
    assert q02.primary_hypothesis == "hypothesis:h1-alpha"
    match = next(m for m in q02.hypotheses if m.id == "hypothesis:h1-alpha")
    assert match.confidence == "inverse"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /mnt/ssd/Dropbox/science/science-tool && uv run pytest tests/test_big_picture_resolver.py::test_inverse_match -v
```

Expected: FAIL (q02 has no match yet).

- [ ] **Step 3: Implement inverse matching**

In `resolver.py`, in the `resolve_questions` function, after the "Direct" loop and before the `return`, add:

```python
    # Inverse: hypothesis.related lists the question.
    for hid, hfm in hypotheses.items():
        for ref in _as_list(hfm.get("related")):
            if ref in results and hid not in results[ref]:
                results[ref][hid] = HypothesisMatch(hid, "inverse", 0.8)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /mnt/ssd/Dropbox/science/science-tool && uv run pytest tests/test_big_picture_resolver.py -v
```

Expected: both tests PASS.

- [ ] **Step 5: Commit**

```bash
git add science-tool/src/science_tool/big_picture/resolver.py science-tool/tests/test_big_picture_resolver.py
git commit -m "feat(big-picture): resolver — inverse-top-down fallback"
```

---

## Task 6: Resolver — transitive-via-interpretation fallback

**Files:**
- Modify: `science-tool/src/science_tool/big_picture/resolver.py`
- Test: `science-tool/tests/test_big_picture_resolver.py`

- [ ] **Step 1: Add the failing test**

Append to `test_big_picture_resolver.py`:

```python
def test_transitive_match() -> None:
    result = resolve_questions(FIXTURE)
    q03 = result["question:q03-transitive-via-interp"]
    assert q03.primary_hypothesis == "hypothesis:h1-alpha"
    match = next(m for m in q03.hypotheses if m.id == "hypothesis:h1-alpha")
    assert match.confidence == "transitive"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /mnt/ssd/Dropbox/science/science-tool && uv run pytest tests/test_big_picture_resolver.py::test_transitive_match -v
```

Expected: FAIL.

- [ ] **Step 3: Implement transitive matching**

In `resolver.py`, after the inverse loop, add:

```python
    # Transitive: interpretation lists both a question and a hypothesis.
    interpretations = _load_entities(project_root / "doc" / "interpretations")
    for _iid, ifm in interpretations.items():
        refs = _as_list(ifm.get("related"))
        q_refs = [r for r in refs if r in results]
        h_refs = [r for r in refs if r in hypotheses]
        for qid in q_refs:
            for hid in h_refs:
                if hid not in results[qid]:
                    results[qid][hid] = HypothesisMatch(hid, "transitive", 0.5)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /mnt/ssd/Dropbox/science/science-tool && uv run pytest tests/test_big_picture_resolver.py -v
```

Expected: 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add science-tool/src/science_tool/big_picture/resolver.py science-tool/tests/test_big_picture_resolver.py
git commit -m "feat(big-picture): resolver — transitive-via-interpretation fallback"
```

---

## Task 7: Resolver — cross-cutting and orphan cases

**Files:**
- Test: `science-tool/tests/test_big_picture_resolver.py`

- [ ] **Step 1: Add failing tests for cross-cutting + orphan**

Append to `test_big_picture_resolver.py`:

```python
def test_cross_cutting_many_to_many() -> None:
    result = resolve_questions(FIXTURE)
    q04 = result["question:q04-cross-cutting"]
    hyp_ids = {m.id for m in q04.hypotheses}
    assert hyp_ids == {"hypothesis:h1-alpha", "hypothesis:h2-beta"}
    # Both are inverse-matched (both hypotheses list q04 in related).
    assert all(m.confidence == "inverse" for m in q04.hypotheses)


def test_orphan_has_null_primary() -> None:
    result = resolve_questions(FIXTURE)
    q05 = result["question:q05-orphan"]
    assert q05.primary_hypothesis is None
    assert q05.hypotheses == []


def test_primary_prefers_higher_confidence() -> None:
    """A question matched both inverse and transitive prefers the inverse match."""
    result = resolve_questions(FIXTURE)
    q02 = result["question:q02-inverse-via-h1"]
    assert q02.primary_hypothesis == "hypothesis:h1-alpha"
    assert q02.hypotheses[0].confidence == "inverse"
```

- [ ] **Step 2: Run tests to verify status**

```bash
cd /mnt/ssd/Dropbox/science/science-tool && uv run pytest tests/test_big_picture_resolver.py -v
```

Expected: all 6 tests PASS. (The resolver logic from Tasks 4–6 already handles many-to-many and orphan naturally; this task verifies it.)

- [ ] **Step 3: If any test fails, fix the resolver**

The existing logic should cover these cases. If a test fails, inspect the failure:
- Cross-cutting failing → check that the inverse loop doesn't early-break on the first hypothesis match.
- Orphan failing → check that `_finalize` returns the default `ResolverOutput()` when `matches` is empty.
- Priority failing → check `_conf_rank` values and `sorted` key.

- [ ] **Step 4: Commit**

```bash
git add science-tool/tests/test_big_picture_resolver.py
git commit -m "test(big-picture): resolver — cross-cutting + orphan cases"
```

---

## Task 8: Resolver CLI — `science-tool big-picture resolve-questions`

**Files:**
- Modify: `science-tool/src/science_tool/big_picture/cli.py`
- Test: `science-tool/tests/test_big_picture_cli.py`

- [ ] **Step 1: Add the failing test**

Append to `test_big_picture_cli.py`:

```python
import json
from pathlib import Path

FIXTURE = Path(__file__).parent / "fixtures" / "big_picture" / "minimal_project"


def test_resolve_questions_emits_json() -> None:
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["big-picture", "resolve-questions", "--project-root", str(FIXTURE)],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert "question:q01-direct-to-h1" in payload
    q04 = payload["question:q04-cross-cutting"]
    assert {h["id"] for h in q04["hypotheses"]} == {
        "hypothesis:h1-alpha",
        "hypothesis:h2-beta",
    }
    assert payload["question:q05-orphan"]["primary_hypothesis"] is None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /mnt/ssd/Dropbox/science/science-tool && uv run pytest tests/test_big_picture_cli.py -v
```

Expected: FAIL (the stub raises ClickException).

- [ ] **Step 3: Implement the CLI subcommand**

Replace the `resolve_questions_cmd` stub in `science-tool/src/science_tool/big_picture/cli.py` with:

```python
import json
from dataclasses import asdict
from pathlib import Path

import click

from science_tool.big_picture.resolver import resolve_questions


@big_picture_group.command("resolve-questions")
@click.option(
    "--project-root",
    type=click.Path(file_okay=False, exists=True, path_type=Path),
    default=Path.cwd(),
    show_default=True,
    help="Path to the project root (containing specs/, doc/, science.yaml).",
)
def resolve_questions_cmd(project_root: Path) -> None:
    """Emit question→hypothesis resolver output as JSON."""
    results = resolve_questions(project_root)
    payload = {qid: asdict(out) for qid, out in results.items()}
    click.echo(json.dumps(payload, indent=2, sort_keys=True))
```

Remove the original stub. Reorganize imports to the top of the file. Final top of `cli.py` should look like:

```python
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import click

from science_tool.big_picture.resolver import resolve_questions


@click.group("big-picture")
def big_picture_group() -> None:
    """Tools supporting the /science:big-picture command."""


@big_picture_group.command("resolve-questions")
# ... (as above)
```

Leave the `validate` stub as-is for now; Task 12 replaces it.

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /mnt/ssd/Dropbox/science/science-tool && uv run pytest tests/test_big_picture_cli.py -v
```

Expected: 2 tests PASS (the help test from Task 1 + the resolver JSON test).

- [ ] **Step 5: Verify the CLI end-to-end**

```bash
cd /mnt/ssd/Dropbox/science/science-tool && uv run science-tool big-picture resolve-questions --project-root tests/fixtures/big_picture/minimal_project | head -30
```

Expected: JSON with 5 questions, each showing hypotheses + primary_hypothesis.

- [ ] **Step 6: Commit**

```bash
git add science-tool/src/science_tool/big_picture/cli.py science-tool/tests/test_big_picture_cli.py
git commit -m "feat(big-picture): CLI — resolve-questions subcommand"
```

---

## Task 9: Validator — citation ID existence check

**Files:**
- Create: `science-tool/src/science_tool/big_picture/validator.py`
- Test: `science-tool/tests/test_big_picture_validator.py`

- [ ] **Step 1: Write the failing test**

Create `science-tool/tests/test_big_picture_validator.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.big_picture.validator import ValidationIssue, validate_synthesis_file

FIXTURE = Path(__file__).parent / "fixtures" / "big_picture" / "minimal_project"


def _write(tmp_path: Path, name: str, body: str) -> Path:
    f = tmp_path / name
    f.write_text(body)
    return f


def test_flags_nonexistent_interpretation_id(tmp_path: Path) -> None:
    synth = _write(
        tmp_path,
        "h1-alpha.md",
        """---
id: "synthesis:h1-alpha"
hypothesis: "hypothesis:h1-alpha"
provenance_coverage: "high"
---

## Arc

The investigation began with interpretation:i99-does-not-exist.
""",
    )
    issues = validate_synthesis_file(synth, project_root=FIXTURE)
    assert any(
        i.kind == "nonexistent_reference" and "i99-does-not-exist" in i.message
        for i in issues
    )


def test_passes_when_all_references_exist(tmp_path: Path) -> None:
    synth = _write(
        tmp_path,
        "h1-alpha.md",
        """---
id: "synthesis:h1-alpha"
hypothesis: "hypothesis:h1-alpha"
provenance_coverage: "high"
---

## Arc

The investigation built on interpretation:i01-h1-q03.
""",
    )
    issues = validate_synthesis_file(synth, project_root=FIXTURE)
    assert not any(i.kind == "nonexistent_reference" for i in issues)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /mnt/ssd/Dropbox/science/science-tool && uv run pytest tests/test_big_picture_validator.py -v
```

Expected: FAIL (module not found).

- [ ] **Step 3: Implement the validator**

Create `science-tool/src/science_tool/big_picture/validator.py`:

```python
"""Post-hoc validator for generated big-picture synthesis files."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from science_tool.big_picture.frontmatter import read_frontmatter

IssueKind = Literal["nonexistent_reference", "thin_coverage_marker_mismatch", "empty_section"]

# Matches "interpretation:<id>", "task:<id>", "question:<id>", "hypothesis:<id>".
REFERENCE_PATTERN = re.compile(r"\b(interpretation|task|question|hypothesis):([a-zA-Z0-9_\-.]+)\b")


@dataclass(frozen=True)
class ValidationIssue:
    kind: IssueKind
    message: str
    path: Path


def validate_synthesis_file(path: Path, project_root: Path) -> list[ValidationIssue]:
    """Return structural issues with a generated synthesis file."""
    issues: list[ValidationIssue] = []
    text = path.read_text(encoding="utf-8")

    known_ids = _collect_project_ids(project_root)
    for match in REFERENCE_PATTERN.finditer(text):
        kind, ident = match.group(1), match.group(2)
        full_id = f"{kind}:{ident}"
        if full_id not in known_ids:
            issues.append(
                ValidationIssue(
                    kind="nonexistent_reference",
                    message=f"Reference {full_id} does not exist in project.",
                    path=path,
                )
            )

    return issues


def _collect_project_ids(project_root: Path) -> set[str]:
    ids: set[str] = set()
    for relative in (
        "specs/hypotheses",
        "doc/questions",
        "doc/interpretations",
        "tasks",
    ):
        directory = project_root / relative
        if not directory.is_dir():
            continue
        for path in directory.rglob("*.md"):
            fm = read_frontmatter(path)
            if fm and "id" in fm:
                ids.add(str(fm["id"]))
    return ids
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /mnt/ssd/Dropbox/science/science-tool && uv run pytest tests/test_big_picture_validator.py -v
```

Expected: 2 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add science-tool/src/science_tool/big_picture/validator.py science-tool/tests/test_big_picture_validator.py
git commit -m "feat(big-picture): validator — nonexistent reference detection"
```

---

## Task 10: Validator — orphan-question count reconciliation

**Files:**
- Modify: `science-tool/src/science_tool/big_picture/validator.py`
- Test: `science-tool/tests/test_big_picture_validator.py`

- [ ] **Step 1: Write the failing test**

Append to `test_big_picture_validator.py`:

```python
from science_tool.big_picture.validator import validate_rollup_file


def test_rollup_orphan_count_mismatch(tmp_path: Path) -> None:
    rollup = _write(
        tmp_path,
        "synthesis.md",
        """---
type: "synthesis-rollup"
orphan_question_count: 99
synthesized_from: []
---
""",
    )
    issues = validate_rollup_file(rollup, project_root=FIXTURE)
    # FIXTURE has exactly one orphan (q05-orphan).
    assert any(
        i.kind == "orphan_count_mismatch" and "expected 1" in i.message for i in issues
    )


def test_rollup_orphan_count_matches(tmp_path: Path) -> None:
    rollup = _write(
        tmp_path,
        "synthesis.md",
        """---
type: "synthesis-rollup"
orphan_question_count: 1
synthesized_from: []
---
""",
    )
    issues = validate_rollup_file(rollup, project_root=FIXTURE)
    assert not any(i.kind == "orphan_count_mismatch" for i in issues)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /mnt/ssd/Dropbox/science/science-tool && uv run pytest tests/test_big_picture_validator.py -v
```

Expected: FAIL (`validate_rollup_file` not defined).

- [ ] **Step 3: Implement the rollup validator**

Edit `science-tool/src/science_tool/big_picture/validator.py`. Add `orphan_count_mismatch` to the `IssueKind` literal:

```python
IssueKind = Literal[
    "nonexistent_reference",
    "thin_coverage_marker_mismatch",
    "empty_section",
    "orphan_count_mismatch",
]
```

Add imports at the top of the file:

```python
from science_tool.big_picture.resolver import resolve_questions
```

Add a new function at the bottom:

```python
def validate_rollup_file(path: Path, project_root: Path) -> list[ValidationIssue]:
    """Return structural issues with a generated rollup (synthesis.md)."""
    issues: list[ValidationIssue] = []
    fm = read_frontmatter(path) or {}

    claimed = fm.get("orphan_question_count")
    if claimed is not None:
        resolved = resolve_questions(project_root)
        actual = sum(1 for r in resolved.values() if r.primary_hypothesis is None)
        if int(claimed) != actual:
            issues.append(
                ValidationIssue(
                    kind="orphan_count_mismatch",
                    message=f"Rollup claims {claimed} orphans but resolver expected {actual}.",
                    path=path,
                )
            )

    return issues
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /mnt/ssd/Dropbox/science/science-tool && uv run pytest tests/test_big_picture_validator.py -v
```

Expected: 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add science-tool/src/science_tool/big_picture/validator.py science-tool/tests/test_big_picture_validator.py
git commit -m "feat(big-picture): validator — orphan count reconciliation"
```

---

## Task 11: Validator — thin-coverage marker consistency

**Files:**
- Modify: `science-tool/src/science_tool/big_picture/validator.py`
- Test: `science-tool/tests/test_big_picture_validator.py`

- [ ] **Step 1: Write the failing test**

Append to `test_big_picture_validator.py`:

```python
def test_thin_coverage_flagged_when_arc_is_long(tmp_path: Path) -> None:
    body = "word " * 400  # A long Arc section.
    synth = _write(
        tmp_path,
        "h1-alpha.md",
        f"""---
id: "synthesis:h1-alpha"
hypothesis: "hypothesis:h1-alpha"
provenance_coverage: "thin"
---

## State

Empty.

## Arc

{body}
""",
    )
    issues = validate_synthesis_file(synth, project_root=FIXTURE)
    assert any(i.kind == "thin_coverage_marker_mismatch" for i in issues)


def test_thin_coverage_passes_when_arc_is_short(tmp_path: Path) -> None:
    synth = _write(
        tmp_path,
        "h1-alpha.md",
        """---
id: "synthesis:h1-alpha"
hypothesis: "hypothesis:h1-alpha"
provenance_coverage: "thin"
---

## Arc

Arc reconstruction is limited because no prior_interpretations chains exist.
""",
    )
    issues = validate_synthesis_file(synth, project_root=FIXTURE)
    assert not any(i.kind == "thin_coverage_marker_mismatch" for i in issues)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /mnt/ssd/Dropbox/science/science-tool && uv run pytest tests/test_big_picture_validator.py -v
```

Expected: FAIL.

- [ ] **Step 3: Implement the check**

In `validate_synthesis_file`, after the reference-check block, add:

```python
    fm = read_frontmatter(path) or {}
    if fm.get("provenance_coverage") == "thin":
        arc = _extract_section(text, "Arc")
        word_count = len(arc.split())
        if word_count > 150:
            issues.append(
                ValidationIssue(
                    kind="thin_coverage_marker_mismatch",
                    message=(
                        f"provenance_coverage is 'thin' but Arc has {word_count} words "
                        "(expected ≤150 when thin)."
                    ),
                    path=path,
                )
            )
```

Add the helper at the end of the file:

```python
def _extract_section(text: str, heading: str) -> str:
    """Extract the body of a markdown section by its heading."""
    lines = text.splitlines()
    out: list[str] = []
    in_section = False
    for line in lines:
        stripped = line.lstrip("#").strip()
        if line.startswith("#"):
            if in_section:
                break
            if stripped == heading:
                in_section = True
                continue
        if in_section:
            out.append(line)
    return "\n".join(out).strip()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /mnt/ssd/Dropbox/science/science-tool && uv run pytest tests/test_big_picture_validator.py -v
```

Expected: 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add science-tool/src/science_tool/big_picture/validator.py science-tool/tests/test_big_picture_validator.py
git commit -m "feat(big-picture): validator — thin-coverage Arc length check"
```

---

## Task 12: Validator CLI — `science-tool big-picture validate`

**Files:**
- Modify: `science-tool/src/science_tool/big_picture/cli.py`
- Test: `science-tool/tests/test_big_picture_cli.py`

- [ ] **Step 1: Add the failing test**

Append to `test_big_picture_cli.py`:

```python
def test_validate_exits_nonzero_on_issues(tmp_path: Path) -> None:
    synth_dir = tmp_path / "doc" / "reports" / "synthesis"
    synth_dir.mkdir(parents=True)
    (synth_dir / "h1-alpha.md").write_text(
        """---
id: "synthesis:h1-alpha"
hypothesis: "hypothesis:h1-alpha"
provenance_coverage: "high"
---

## Arc

Built on interpretation:i99-fake.
"""
    )

    # Copy fixture project files into tmp_path so referenced IDs are available
    import shutil

    shutil.copytree(FIXTURE / "specs", tmp_path / "specs")
    shutil.copytree(FIXTURE / "doc" / "questions", tmp_path / "doc" / "questions")
    shutil.copytree(FIXTURE / "doc" / "interpretations", tmp_path / "doc" / "interpretations")

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["big-picture", "validate", "--project-root", str(tmp_path)],
    )
    assert result.exit_code == 1
    assert "nonexistent_reference" in result.output
    assert "i99-fake" in result.output


def test_validate_passes_on_clean_project(tmp_path: Path) -> None:
    import shutil

    shutil.copytree(FIXTURE / "specs", tmp_path / "specs")
    shutil.copytree(FIXTURE / "doc", tmp_path / "doc")
    (tmp_path / "doc" / "reports" / "synthesis").mkdir(parents=True, exist_ok=True)

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["big-picture", "validate", "--project-root", str(tmp_path)],
    )
    assert result.exit_code == 0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /mnt/ssd/Dropbox/science/science-tool && uv run pytest tests/test_big_picture_cli.py -v
```

Expected: FAIL (validate is still stubbed).

- [ ] **Step 3: Implement the validate CLI**

Replace the `validate_cmd` stub in `cli.py` with:

```python
from science_tool.big_picture.validator import validate_rollup_file, validate_synthesis_file


@big_picture_group.command("validate")
@click.option(
    "--project-root",
    type=click.Path(file_okay=False, exists=True, path_type=Path),
    default=Path.cwd(),
    show_default=True,
    help="Path to the project root.",
)
def validate_cmd(project_root: Path) -> None:
    """Validate generated big-picture synthesis files in this project."""
    synthesis_dir = project_root / "doc" / "reports" / "synthesis"
    rollup_path = project_root / "doc" / "reports" / "synthesis.md"

    issues = []
    if synthesis_dir.is_dir():
        for path in sorted(synthesis_dir.glob("*.md")):
            if path.name.startswith("_"):
                continue
            issues.extend(validate_synthesis_file(path, project_root=project_root))
    if rollup_path.is_file():
        issues.extend(validate_rollup_file(rollup_path, project_root=project_root))

    for issue in issues:
        click.echo(f"[{issue.kind}] {issue.path.name}: {issue.message}")

    if issues:
        raise click.exceptions.Exit(code=1)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /mnt/ssd/Dropbox/science/science-tool && uv run pytest tests/test_big_picture_cli.py -v
```

Expected: 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add science-tool/src/science_tool/big_picture/cli.py science-tool/tests/test_big_picture_cli.py
git commit -m "feat(big-picture): CLI — validate subcommand"
```

---

## Task 13: Write `agents/hypothesis-synthesizer.md`

**Files:**
- Create: `agents/hypothesis-synthesizer.md`

This task has no TDD step — the artifact is a prompt. After writing, a manual review step confirms the prompt encodes all spec requirements.

- [ ] **Step 1: Read existing sub-agent precedent**

```bash
cat /mnt/ssd/Dropbox/science/agents/paper-researcher.md | head -80
```

Note the frontmatter fields (`name`, `description`, `model`, `tools`) and the "You are a dispatched subagent" framing. Match this style.

- [ ] **Step 2: Write the prompt file**

Create `agents/hypothesis-synthesizer.md`:

```markdown
---
name: hypothesis-synthesizer
description: Synthesize one per-hypothesis section of a /science:big-picture report. Accepts a bundle describing a single hypothesis (its file, related questions, tasks, interpretations, and .edges.yaml if present) and writes one markdown file to doc/reports/synthesis/<hyp-id>.md. Use when the main /science:big-picture command dispatches per-hypothesis work in parallel.
model: claude-sonnet-4-6
tools: Read, Write, Glob, Grep, Bash
---

# Hypothesis Synthesizer

You are a dispatched subagent. Your sole job is to produce one per-hypothesis synthesis file for the /science:big-picture command.

## Input you receive

The dispatcher gives you:

- Path to the project root.
- Hypothesis ID (`hypothesis:<id>`) and path to its specs file.
- A pre-assembled bundle listing:
  - related question IDs (direct, inverse, and transitive — with confidence annotations)
  - related task IDs (via task frontmatter `related:`)
  - related interpretation IDs (via interpretation frontmatter `related:`)
  - matching `.edges.yaml` files under `doc/figures/dags/` if any
  - filtered graph uncertainty/gaps output for this hypothesis
- Target output path: `doc/reports/synthesis/<hyp-id>.md`
- `provenance_coverage` value to record in frontmatter (`high` | `partial` | `thin`), pre-computed by the dispatcher.

Read the hypothesis file, the .edges.yaml if present, and each related interpretation. Do not read beyond the bundle — the dispatcher chose what is relevant. If something critical appears missing, report back rather than searching further.

## Output you produce

Write exactly one file at the target output path with this structure:

```yaml
---
id: "synthesis:<hyp-id>"
type: "synthesis"
hypothesis: "hypothesis:<hyp-id>"
generated_at: "<ISO-8601 timestamp provided by dispatcher>"
source_commit: "<git SHA provided by dispatcher>"
provenance_coverage: "<value provided by dispatcher>"
---
```

Followed by three body sections, in this order: **State**, **Arc**, **Research fronts**. Total length target: 400–600 words.

### State (≈200 words)

Current claim status and key questions under this hypothesis.

Data source precedence (use highest-priority source with content):

1. Graph claims if present in the bundle.
2. `.edges.yaml` edges if present — read `edge_status`, `identification`, `data_support`, `lit_support` directly.
3. YAML frontmatter chains as fallback.

**Citation requirement**: every factual claim in this section MUST name its source inline — an `.edges.yaml` edge ID, an interpretation ID, a task ID, a graph claim IRI, or a question ID. If you cannot name a source, omit the claim.

### Arc (≈200 words)

Narrative of how the investigation evolved. Reconstructed by traversing `prior_interpretations` chains and task creation dates. Not a retelling of every step — a story: initial framing → main investigative moves → what each move resolved → current epistemic position.

**Arc grounding**: every sentence MUST reference at least one interpretation or task from the bundle. Narrative that cannot be grounded in a specific artifact is cut.

**Under thin provenance**: if `provenance_coverage: thin`, shorten this section to ≤150 words and open it with a one-line note naming the limitation (e.g., "Arc reconstruction is limited because N interpretations lack `prior_interpretations` chains."). **Never** fill gaps with speculative connective tissue.

### Research fronts (≈150 words)

Live questions under this hypothesis, open tasks, gap/uncertainty areas.

Pull live questions from the bundle's resolver output; open tasks from the task listing; gaps from the bundle's filtered uncertainty/gaps data.

## Hedging discipline

Claims about unreplicated, contested, or transitively-inferred findings use hedged language: "suggestive", "one-source", "not yet replicated", "inferred via interpretation X". Confident prose ("supported by", "established") is reserved for claims whose graph or `.edges.yaml` status is `supported`.

## When you are done

Write the file. Report back with:
- Path written.
- Word count per section.
- Count of distinct interpretations/tasks/edges cited.
- Any bundle items that you could not ground into the output (surface as "unused in synthesis").
```

- [ ] **Step 3: Manual review checklist**

Read your generated file back and confirm:
- Frontmatter fields match the spec's per-hypothesis schema.
- Section order matches: State → Arc → Research fronts.
- Citation requirement, Arc grounding, Hedging discipline, and No-fabrication-under-thin-provenance are each explicit.
- Length budget (400–600 words total, with per-section approximations) is stated.

- [ ] **Step 4: Commit**

```bash
git add agents/hypothesis-synthesizer.md
git commit -m "feat(big-picture): hypothesis-synthesizer subagent prompt"
```

---

## Task 14: Write `agents/emergent-threads-synthesizer.md`

**Files:**
- Create: `agents/emergent-threads-synthesizer.md`

- [ ] **Step 1: Write the prompt file**

Create `agents/emergent-threads-synthesizer.md`:

```markdown
---
name: emergent-threads-synthesizer
description: Synthesize the cross-cutting and orphan material for a /science:big-picture report. Produces doc/reports/synthesis/_emergent-threads.md. Use when /science:big-picture dispatches emergent-thread analysis alongside per-hypothesis sub-agents.
model: claude-sonnet-4-6
tools: Read, Write, Glob, Grep, Bash
---

# Emergent Threads Synthesizer

You are a dispatched subagent. Your sole job is to produce `doc/reports/synthesis/_emergent-threads.md`.

## Input you receive

The dispatcher gives you:

- Path to the project root.
- The full question→hypothesis resolver output as JSON.
- Path to the target output file: `doc/reports/synthesis/_emergent-threads.md`.
- `generated_at` and `source_commit` values.

## Output you produce

Write one file at the target output path. Length target: 200–400 words.

Required sections:

1. **Cross-hypothesis questions** — questions whose resolver output shows ≥2 hypothesis matches at confidence `inverse` or `direct`. For each, give its ID and the matching hypotheses, and briefly (one sentence) note why the cross-cutting nature is interesting (bridge, shared mechanism, etc. — inferable from the question file content).
2. **Orphan questions** — questions with `primary_hypothesis: null`. List each with a one-sentence summary. At the top of this subsection, give the total count.
3. **Orphan interpretations** — interpretations whose `related:` field does not intersect any hypothesis (directly or via questions under any hypothesis). Same format: total count, then per-item summaries.
4. **Candidate hypotheses** — topics recurring across ≥2 orphan questions or ≥2 orphan interpretations that might warrant a new hypothesis. Zero entries is fine; say "none identified this run" if so.

## Citation requirement

Every question, interpretation, or topic mentioned MUST be cited by its canonical ID.

## No fabrication

If the resolver output shows zero orphans, say so explicitly — do not invent content to fill the section. Empty sections are valid output.

## When you are done

Write the file. Report back with:
- Path written.
- Counts: cross-hypothesis questions, orphan questions, orphan interpretations, candidate hypotheses.
- Any questions/interpretations whose IDs did not resolve to known files (suggest a reconciliation).
```

- [ ] **Step 2: Manual review checklist**

Confirm:
- Each of the four sections is listed.
- Citation requirement and No-fabrication are explicit.
- The cross-hypothesis threshold matches the spec (≥2 at confidence `inverse` or `direct`).

- [ ] **Step 3: Commit**

```bash
git add agents/emergent-threads-synthesizer.md
git commit -m "feat(big-picture): emergent-threads-synthesizer subagent prompt"
```

---

## Task 15: Write `commands/big-picture.md` — scaffold + precompute phase

**Files:**
- Create: `commands/big-picture.md`

- [ ] **Step 1: Read the `commands/status.md` file as structural reference**

```bash
cat /mnt/ssd/Dropbox/science/commands/status.md
```

Match its overall shape (frontmatter + prose instructions + bash blocks).

- [ ] **Step 2: Write the scaffold and precompute phase**

Create `commands/big-picture.md`:

```markdown
---
description: Generate a multi-scale, hypothesis-organized synthesis report for the current project. Produces per-hypothesis files, an emergent-threads file, and a project-level rollup (synthesis.md). Use when the user says "big picture", "full synthesis", "deep dive", or wants a shareable project-state artifact.
---

# Project Big Picture

Generate `doc/reports/synthesis/<hyp>.md` files (one per hypothesis), `doc/reports/synthesis/_emergent-threads.md`, and `doc/reports/synthesis.md` (project rollup).

See the design spec at `${CLAUDE_PLUGIN_ROOT}/docs/specs/2026-04-18-project-big-picture-design.md` for full semantics.

## Flags

Parse `$ARGUMENTS` for:

- `--hypothesis <id>` — regenerate only one per-hypothesis file. Skip steps 3 and the non-targeted writes.
- `--dry-run` — print what would be generated without writing.
- `--commit` — auto-commit written files with `doc(big-picture): regenerate synthesis YYYY-MM-DD`.
- `--snapshot` — after writing, copy `doc/reports/synthesis.md` to `doc/reports/synthesis-history/<YYYY-MM-DDTHHMMSSZ>.md`.
- `--since <date>` — produce a scoped Arc. **Requires `--output <path>`. Never overwrites canonical files.** If `--since` is set without `--output`, refuse with a clear error.

## Phase 1: Precompute

Run these in the project root:

```bash
science-tool graph project-summary --format json
science-tool graph question-summary --format json
science-tool graph inquiry-summary --format json
science-tool graph dashboard-summary --format json
science-tool graph uncertainty --format json
science-tool graph gaps --format json
science-tool graph neighborhood-summary --format json
science-tool big-picture resolve-questions --project-root .
```

For `software` profile projects, skip `graph project-summary` (follows `/science:status` precedent).

Enumerate hypotheses from `specs/hypotheses/*.md`.

For each hypothesis, assemble a bundle. The bundle is a dictionary you construct in-memory — it is NOT persisted to disk:

- `hypothesis_path`: path to the `specs/hypotheses/<id>.md` file.
- `hypothesis_frontmatter`: parsed YAML.
- `resolved_questions`: from the resolver output, all questions whose `hypotheses[]` contains this hypothesis. Annotate each with its confidence.
- `tasks`: glob `tasks/*.md` and `tasks/done/*.md`; parse frontmatter; include entries whose `related:` mentions this hypothesis or any of its resolved questions.
- `interpretations`: glob `doc/interpretations/*.md`; parse frontmatter; include entries whose `related:` mentions this hypothesis or any of its resolved questions.
- `edges_yaml`: glob `doc/figures/dags/*.edges.yaml`; include any whose filename stem starts with this hypothesis ID.
- `uncertainty_slice`: filter the global uncertainty output to entries referring to this hypothesis or its resolved questions.
- `gaps_slice`: same filtering for gaps output.

Compute `provenance_coverage` per hypothesis:
- `high` if ≥1 `.edges.yaml` is present OR ≥1 graph claim surfaces AND ≥60% of related interpretations have `prior_interpretations` chains.
- `partial` if neither of those but ≥30% of related interpretations have `prior_interpretations`.
- `thin` otherwise.

Record the project-level `source_commit`:

```bash
git -C <project-root> rev-parse HEAD
```

Record `generated_at` as the current ISO-8601 UTC timestamp.

## Phase 2: Dispatch (see subsequent phases in Task 16+)

(Next phases are added in Task 16.)
```

- [ ] **Step 3: Commit**

```bash
git add commands/big-picture.md
git commit -m "feat(big-picture): command scaffold and precompute phase"
```

---

## Task 16: `commands/big-picture.md` — dispatch phase

**Files:**
- Modify: `commands/big-picture.md`

- [ ] **Step 1: Append the dispatch phase**

Replace the "(Next phases are added in Task 16.)" line with:

```markdown
## Phase 2: Dispatch

Dispatch sub-agents in parallel using `Agent` tool calls. Send all dispatches in a single message.

For each hypothesis (unless `--hypothesis <id>` is set, in which case only that one):

```
Agent(
  subagent_type="hypothesis-synthesizer",
  description="Synthesize <hyp-id>",
  prompt=<<the prompt below>>
)
```

The prompt passed to each sub-agent includes:

- Project root path.
- Hypothesis ID and `hypothesis_path`.
- The bundle (inlined in the prompt as structured text — the sub-agent does not have access to your in-memory bundle directly).
- Target output path: `doc/reports/synthesis/<hyp-id>.md`.
- `generated_at` and `source_commit` values.
- `provenance_coverage` value.
- If `--since <date>` is set: pass it through AND the `--output <path>` target. Tell the sub-agent to include `since: <date>` in its frontmatter.

Also dispatch one emergent-threads sub-agent:

```
Agent(
  subagent_type="emergent-threads-synthesizer",
  description="Synthesize emergent threads",
  prompt=<<the prompt below>>
)
```

The prompt includes:

- Project root path.
- Full resolver output (JSON from Phase 1).
- Target output path: `doc/reports/synthesis/_emergent-threads.md`.
- `generated_at` and `source_commit` values.

**Important**: if `--hypothesis <id>` is set, skip the emergent-threads dispatch (it's a whole-project artifact).

Collect all sub-agent reports. Expect each to report: the path written, word counts, and any bundle items it could not ground.
```

- [ ] **Step 2: Commit**

```bash
git add commands/big-picture.md
git commit -m "feat(big-picture): dispatch phase for parallel sub-agent synthesis"
```

---

## Task 17: `commands/big-picture.md` — synthesize phase (Opus rollup)

**Files:**
- Modify: `commands/big-picture.md`

- [ ] **Step 1: Append the synthesize phase**

Append to `commands/big-picture.md`:

```markdown
## Phase 3: Synthesize (project rollup)

Skip this phase if `--hypothesis <id>` is set.

After the dispatch phase completes, read back each just-written per-hypothesis file and the emergent-threads file. You (the orchestrator, on Opus 4.7) are the only agent with visibility across all hypotheses, so cross-hypothesis synthesis happens here — do not dispatch another sub-agent for this.

Write `doc/reports/synthesis.md` with this structure:

Frontmatter:

```yaml
---
type: "synthesis-rollup"
generated_at: "<ISO-8601>"
source_commit: "<SHA>"
synthesized_from:
  - { hypothesis: "<hyp-id>", file: "doc/reports/synthesis/<hyp-id>.md", sha: "<SHA>" }
  # one entry per hypothesis
emergent_threads_sha: "<SHA>"
orphan_question_count: <int>
---
```

Body sections (~1000–1500 words total):

- **TL;DR** — 5–7 bullets, most salient project-wide facts. Distilled from each per-hypothesis State, not a per-hypothesis recap.
- **State** — cross-hypothesis consolidation. What the project collectively believes, where the strongest evidence sits, what's contested.
- **Arc** — one paragraph per hypothesis, plus a framing paragraph on how the hypotheses relate.
- **Research fronts** — ranked list across all hypotheses. Signals: uncertainty density, recent activity, explicit task priority. Cite source: "from <hyp-id>" for each front.
- **Emergent threads** — 2–3 sentence pointer to `_emergent-threads.md`. Include the orphan-question count.

Computing SHAs:

```bash
git hash-object doc/reports/synthesis/<hyp-id>.md
git hash-object doc/reports/synthesis/_emergent-threads.md
```

**Citation inheritance**: the rollup inherits the citation and grounding requirements from the per-hypothesis files. Every factual claim traces back to a specific per-hypothesis file's content. No new unsupported claims are introduced at the rollup level.
```

- [ ] **Step 2: Commit**

```bash
git add commands/big-picture.md
git commit -m "feat(big-picture): Opus synthesize phase for project rollup"
```

---

## Task 18: `commands/big-picture.md` — write phase + flag handling

**Files:**
- Modify: `commands/big-picture.md`

- [ ] **Step 1: Append the write phase**

Append to `commands/big-picture.md`:

```markdown
## Phase 4: Write

All canonical artifacts are overwritten on regen.

- Per-hypothesis files: already written by sub-agents in Phase 2.
- Emergent-threads file: already written by sub-agent in Phase 2.
- Project rollup: write `doc/reports/synthesis.md` (from Phase 3).

If `--snapshot` is set:

```bash
mkdir -p doc/reports/synthesis-history
ts="$(date -u +%Y-%m-%dT%H%M%SZ)"
cp doc/reports/synthesis.md "doc/reports/synthesis-history/${ts}.md"
```

If `--dry-run` is set: do not write any files. Print, for each intended file, the target path and a summary (section word counts). Do not invoke sub-agents.

If `--commit` is set: stage all written files and commit with message `doc(big-picture): regenerate synthesis YYYY-MM-DD`.

## Staleness check for partial regen

After any `--hypothesis <id>` invocation, the rollup's `synthesized_from` frontmatter still references the old per-hypothesis SHAs. On the next invocation (any invocation), before Phase 1, compare each entry in the rollup's `synthesized_from` to the current file's SHA:

```bash
for each entry in synthesized_from:
  current_sha = git hash-object <entry.file>
  if current_sha != entry.sha:
    print warning: "Rollup is stale relative to <entry.file>. Run /science:big-picture without --hypothesis to refresh."
```

The staleness warning is informational — do not block execution.

## `--since` handling

If `--since <date>` is set:

- Require `--output <path>` as well. If absent, refuse with: "`--since` requires `--output <path>` to avoid overwriting canonical artifacts. Pass `--output doc/reports/some-scoped-name.md`."
- Do NOT write canonical files (`doc/reports/synthesis.md`, `doc/reports/synthesis/`, `_emergent-threads.md`). Write only to `--output`.
- In the output, include `since: <date>` in frontmatter, and a banner at the top: `> **Scoped synthesis:** includes only activity after <date>. Not the authoritative project synthesis.`

## Output to user

After all phases:

- Show the list of files written.
- Show any staleness warnings.
- Show any sub-agent "unused in synthesis" reports — these are candidates for future bundle improvements.
- Suggest running `science-tool big-picture validate --project-root .` to sanity-check the output.
```

- [ ] **Step 2: Final read-through of the command file**

```bash
wc -l /mnt/ssd/Dropbox/science/commands/big-picture.md
cat /mnt/ssd/Dropbox/science/commands/big-picture.md | head -20
cat /mnt/ssd/Dropbox/science/commands/big-picture.md | tail -40
```

Confirm all four phases + flag handling are present, and the structure matches the spec's generation flow.

- [ ] **Step 3: Commit**

```bash
git add commands/big-picture.md
git commit -m "feat(big-picture): write phase, flag handling, staleness warning"
```

---

## Task 19: Full test sweep

**Files:** none (verification only)

- [ ] **Step 1: Run the full science-tool test suite**

```bash
cd /mnt/ssd/Dropbox/science/science-tool && uv run pytest
```

Expected: all tests pass, including the new big-picture ones.

- [ ] **Step 2: Run type checks if present**

```bash
cd /mnt/ssd/Dropbox/science/science-tool && uv run --frozen ruff check . && uv run --frozen pyright 2>/dev/null || echo "pyright not configured — skipping"
```

Expected: ruff passes; pyright passes or is not configured.

- [ ] **Step 3: Confirm the command renders in Claude's command help**

```bash
ls -la /mnt/ssd/Dropbox/science/commands/big-picture.md
```

(No `/science:` command-registration step required — Claude discovers commands by filename.)

- [ ] **Step 4: No commit**

This is a verification-only task.

---

## Task 20: Smoke test on natural-systems (frontmatter-only fixture)

**Files:** none in `science` repo (execution occurs in `/home/keith/d/natural-systems/`)

This task validates end-to-end behavior on a real project. It requires invoking the full `/science:big-picture` command, which involves sub-agent dispatch and costs API tokens. Run once per meaningful change to the command or agent prompts.

- [ ] **Step 1: Capture pre-state**

```bash
cd /home/keith/d/natural-systems
git status
git rev-parse HEAD
```

Record the SHA for reproducibility.

- [ ] **Step 2: Run `/science:big-picture` in a fresh session**

In a Claude Code session opened at `/home/keith/d/natural-systems`, invoke:

```
/science:big-picture
```

Let it complete. Record elapsed time.

- [ ] **Step 3: Validate the output**

```bash
cd /home/keith/d/natural-systems
science-tool big-picture validate --project-root .
```

Expected: exit 0 (no issues). If issues found, read each carefully — they may reflect real bugs in the command or agent prompts. Record in notes.

- [ ] **Step 4: Manual content review against acceptance criteria**

Open each generated file and check:

- `doc/reports/synthesis/<hyp-id>.md` for each of the 4 hypotheses:
  - Word counts: 400–600 per file.
  - All three sections (State, Arc, Research fronts) present and non-empty.
  - No `interpretation:<id>` or `task:<id>` references that don't exist in the project (the validator catches this, but eyeball spot-check too).
  - `provenance_coverage` marker is plausible — natural-systems has no `.edges.yaml` and no graph claims, so expect `partial` or `thin` for most hypotheses.
  - Under `thin`, the Arc section is actually short and names the limitation.
  - Hedging discipline: unreplicated findings use hedged language.

- `doc/reports/synthesis/_emergent-threads.md`:
  - All four required subsections present.
  - Orphan question count is plausible given natural-systems' structure (92 questions; many expected orphans per the audit).

- `doc/reports/synthesis.md`:
  - TL;DR is distillation, not per-hypothesis recap.
  - `synthesized_from` frontmatter lists all four hypotheses with SHAs.
  - `orphan_question_count` matches `_emergent-threads.md`.

- [ ] **Step 5: Record findings and iterate if needed**

If the validator is clean and the manual review finds no egregious issues, the smoke test passes. Record notes (but do not commit `synthesis*.md` files from natural-systems back into the `science` framework — they belong in the natural-systems project's own git history, which the user can choose to commit or discard).

If issues are found that trace back to prompt or command logic, update the agent prompt or command file in this repo, commit there, and re-run this task.

---

## Task 21: Smoke test on mm30 (.edges.yaml fixture)

**Files:** none in `science` repo (execution occurs in `/home/keith/d/r/mm30/`)

Same structure as Task 20, but now exercising the `.edges.yaml` data-source path.

- [ ] **Step 1: Capture pre-state**

```bash
cd /home/keith/d/r/mm30
git status
git rev-parse HEAD
```

- [ ] **Step 2: Run `/science:big-picture` in a fresh session**

In a Claude Code session opened at `/home/keith/d/r/mm30`, invoke:

```
/science:big-picture
```

Record elapsed time.

- [ ] **Step 3: Validate the output**

```bash
cd /home/keith/d/r/mm30
science-tool big-picture validate --project-root .
```

Expected: exit 0.

- [ ] **Step 4: Manual content review with `.edges.yaml`-specific checks**

For each of mm30's 3 hypotheses (`h1-epigenetic-commitment`, `h2-cytogenetic-distinct-entities`, `h4-attractor-convergence`):

- `provenance_coverage` should be `high` for h1 and h2 (both have rich `.edges.yaml` files).
- State section should cite specific edge IDs from the `.edges.yaml` (e.g., "edge 5 in `h1-prognosis.edges.yaml`").
- `edge_status` values (`supported`, `tentative`, etc.) should appear in State with matching hedging.
- Arc section should reconstruct the investigation using interpretation `prior_interpretations` chains that actually exist.

Cross-hypothesis check:

- mm30 has the `h1-h2-bridge.edges.yaml` DAG. The rollup's Arc or Emergent Threads section should reflect that h1 and h2 are bridged — if this content doesn't surface, the bundle assembly for bridge DAGs needs a follow-on task.

Orphan check:

- Per the audit, mm30 has 17+ questions not yet linked to any hypothesis in frontmatter. `_emergent-threads.md`'s orphan count should be in that ballpark. If it's dramatically lower, the resolver is over-matching via transitive inference.

- [ ] **Step 5: Record findings; iterate if needed**

Same disposition as Task 20.

---

## Self-Review Checklist

After the plan lands (this is for the plan author, to run before declaring done):

**Spec coverage**: every section of the spec maps to a task.

- Motivation / Goal / Scope → reflected in the plan's Goal/Architecture headers.
- Command Interface → Tasks 15, 16, 18.
- Artifact Layout → Task 17 (rollup), Task 18 (snapshots), Task 15 (directories implicit).
- Section Structure → Task 13 (per-hypothesis), Task 14 (emergent), Task 17 (rollup).
- Data-Source Precedence → Task 13 (sub-agent prompt bakes the rule in).
- Resolver → Tasks 4–8.
- Generation Flow → Tasks 15–18.
- Degraded-Mode → Task 13 (Arc section rules), Task 11 (validator).
- Verification & Acceptance Criteria → Tasks 9–12 (validator), 20–21 (smoke tests).
- Relationship to Existing Artifacts → unchanged; no new tasks needed.
- Follow-on Work → explicitly out of scope in this plan.

**Placeholder scan**: no "TBD" / "implement later" / bare "add error handling". All steps show concrete code or commands.

**Type / name consistency**:
- `HypothesisMatch`, `ResolverOutput`, `resolve_questions`, `ValidationIssue`, `validate_synthesis_file`, `validate_rollup_file`, `big_picture_group`, `read_frontmatter` — each name is introduced once and used consistently.
- File paths: `science-tool/src/science_tool/big_picture/…` throughout; no inconsistent capitalization.
- Command name `/science:big-picture` → file `commands/big-picture.md` → CLI `science-tool big-picture` — matches conventions.

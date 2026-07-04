# `science explore-ideas apply` CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move all `/science:explore-ideas --apply` mechanics out of command prose into a tested `science explore-ideas apply` CLI, so applying kept candidates is deterministic and fail-loud instead of re-interpreted every run.

**Architecture:** One new pure-ish module `science/src/science_tool/explore_ideas.py` holds report parsing, routing/planning, surgical write-back (all pure) and one impure `apply_report` orchestrator that calls `create_entity` in-process. A thin `@main.group("explore-ideas")` `apply` subcommand in `cli.py` delegates to it. The command's Apply mode collapses to a single CLI call.

**Tech Stack:** Python 3, Click, Pydantic (`science_model.entities.OriginRecord`), PyYAML, pytest + `click.testing.CliRunner`.

## Global Constraints

- All CLI/package work and tests run from `science/`: `cd science && uv run --frozen pytest`. Never run `uv run` from the repo root.
- Run a single test: `cd science && uv run --frozen pytest tests/test_explore_ideas_apply.py::<name> -v`.
- Lint/types from `science/`: `uv run ruff check` and `uv run pyright` (must stay clean for touched files).
- Provenance is metadata only and **MUST NOT affect evidential weight** — `origins`/`added_by` are never scored.
- `--added-by` stamp format is exactly `explore-ideas:<model-id>:<candidate_id>`.
- Idempotence comes from report write-back (`decision: applied` + `applied_as` + `applied_at`), never from slug/id matching.
- The report format is the fixed contract from `docs/plans/2026-07-04-explore-ideas-design.md` §9: candidates are fenced ` ```yaml ` blocks each carrying a `candidate_id` key; surrounding markdown is human-only and ignored.
- Fail early: reject bad *input* wholesale before any write; surface post-create failures loudly (non-zero exit).
- Conventions: composition over inheritance; explicit over defensive; no "legacy"/"compatibility" layers; no `Unified` prefix.
- Commit messages: conventional style (`feat`/`test`/`docs`/`refactor`); **no AI-attribution trailer or footer** (no `Co-Authored-By`, no "Generated with" line).
- In docs, write user paths as `~/d/...`, never `/home/keith/...` or `/mnt/ssd/Dropbox/...`.

## File Structure

- **Create** `science/src/science_tool/explore_ideas.py` — the apply module: dataclasses (`CandidateBlock`, `CreatePlan`, `ReportPlan`, `CreatedEntity`, `ApplyResult`), exceptions (`ApplyValidationError`, `ApplyWriteBackError`), pure helpers (`resolve_report_path`, `parse_report`, `build_create_plan`, `plan_report`, `write_back`), and the one impure boundary `apply_report`.
- **Create** `science/tests/test_explore_ideas_apply.py` — all tests (pure-function units + `apply_report`/CLI integration).
- **Modify** `science/src/science_tool/cli.py` — add `@main.group("explore-ideas")` with an `apply` subcommand; ensure `from datetime import date` is available.
- **Modify** `commands/explore-ideas.md` — rewrite Apply mode to delegate to the CLI; delete the prose create-templates and anchor-routing sections.
- **Regenerate** `codex-skills/science-explore-ideas/SKILL.md` + `codex-skills/INDEX.md` via `scripts/generate_codex_skills.py`.
- **Delete** `docs/plans/2026-07-04-explore-ideas-manual-check.md`; update `docs/plans/2026-07-04-explore-ideas-design.md` §12/§13.

---

### Task 1: Module scaffold — dataclasses, exceptions, `resolve_report_path`, `parse_report`

**Files:**
- Create: `science/src/science_tool/explore_ideas.py`
- Test: `science/tests/test_explore_ideas_apply.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces:
  - `class ApplyValidationError(Exception)`, `class ApplyWriteBackError(Exception)`
  - `@dataclass(frozen=True) class CandidateBlock: candidate_id: str; data: dict`
  - `resolve_report_path(project_root: Path, from_value: str) -> Path`
  - `parse_report(text: str) -> list[CandidateBlock]`
  - Module-level constants `_YAML_BLOCK_RE`, `_VALID_DECISIONS`, `_ROUTABLE_KINDS`, `_MANUAL_KINDS`, `_VALID_KINDS`.

- [ ] **Step 1: Write the failing tests**

Add to `science/tests/test_explore_ideas_apply.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.explore_ideas import (
    ApplyValidationError,
    CandidateBlock,
    parse_report,
    resolve_report_path,
)

_REPORT = """\
---
type: meta
id: explore-2026-07-04
---

# Exploration report

Some human prose that is not a candidate.

```yaml
candidate_id: cand-a
proposed_kind: question
title: First
decision: keep
```

```yaml
not_a_candidate: true
note: ignore me
```

```yaml
candidate_id: cand-b
proposed_kind: hypothesis
title: Second
decision: drop
```
"""


def test_parse_report_extracts_only_candidate_blocks() -> None:
    blocks = parse_report(_REPORT)
    assert [b.candidate_id for b in blocks] == ["cand-a", "cand-b"]
    assert isinstance(blocks[0], CandidateBlock)
    assert blocks[0].data["title"] == "First"


def test_parse_report_ignores_non_yaml_and_non_candidate() -> None:
    assert parse_report("no fenced blocks here") == []


def test_parse_report_malformed_yaml_raises_validation_error() -> None:
    text = "```yaml\ncandidate_id: [unterminated\n```\n"
    with pytest.raises(ApplyValidationError, match="invalid yaml"):
        parse_report(text)


def test_resolve_report_path_direct_file(tmp_path: Path) -> None:
    report = tmp_path / "explore-2026-07-04.md"
    report.write_text("x", encoding="utf-8")
    assert resolve_report_path(tmp_path, str(report)) == report


def test_resolve_report_path_by_id(tmp_path: Path) -> None:
    d = tmp_path / "entities" / "meta" / "explorations"
    d.mkdir(parents=True)
    report = d / "explore-2026-07-04.md"
    report.write_text("x", encoding="utf-8")
    assert resolve_report_path(tmp_path, "explore-2026-07-04") == report


def test_resolve_report_path_no_reprepend(tmp_path: Path) -> None:
    # The id already carries the explore- prefix; it must not be doubled.
    d = tmp_path / "entities" / "meta" / "explorations"
    d.mkdir(parents=True)
    (d / "explore-2026-07-04.md").write_text("x", encoding="utf-8")
    with pytest.raises(ApplyValidationError):
        resolve_report_path(tmp_path, "explore-explore-2026-07-04")


def test_resolve_report_path_missing_raises(tmp_path: Path) -> None:
    with pytest.raises(ApplyValidationError):
        resolve_report_path(tmp_path, "nope")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science && uv run --frozen pytest tests/test_explore_ideas_apply.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'science_tool.explore_ideas'`.

- [ ] **Step 3: Create the module with the scaffold**

Create `science/src/science_tool/explore_ideas.py`:

```python
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

_YAML_BLOCK_RE = re.compile(r"```yaml\n(.*?)```", re.DOTALL)
_VALID_DECISIONS = {"keep", "drop", "defer", "applied"}
_ROUTABLE_KINDS = {"question", "hypothesis"}
_MANUAL_KINDS = {"topic", "theme"}
_VALID_KINDS = _ROUTABLE_KINDS | _MANUAL_KINDS


class ApplyValidationError(Exception):
    """Bad or ambiguous report input; raised before any entity is written."""


class ApplyWriteBackError(Exception):
    """A report write-back failed AFTER an entity was created (fatal, non-resumable)."""


@dataclass(frozen=True)
class CandidateBlock:
    candidate_id: str
    data: dict


def resolve_report_path(project_root: Path, from_value: str) -> Path:
    direct = Path(from_value)
    if direct.is_file():
        return direct
    candidate = project_root / "entities" / "meta" / "explorations" / f"{from_value}.md"
    if candidate.is_file():
        return candidate
    raise ApplyValidationError(
        f"report not found: {from_value!r} (looked for a file path and for "
        f"entities/meta/explorations/{from_value}.md)"
    )


def parse_report(text: str) -> list[CandidateBlock]:
    blocks: list[CandidateBlock] = []
    for raw in _YAML_BLOCK_RE.findall(text):
        try:
            data = yaml.safe_load(raw)
        except yaml.YAMLError as exc:
            raise ApplyValidationError(f"invalid yaml candidate block: {exc}") from exc
        if isinstance(data, dict) and "candidate_id" in data:
            blocks.append(CandidateBlock(candidate_id=str(data["candidate_id"]), data=data))
    return blocks
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_explore_ideas_apply.py -v`
Expected: PASS (7 tests).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/explore_ideas.py science/tests/test_explore_ideas_apply.py
git commit -m "feat(explore-ideas): apply module scaffold — parse_report, resolve_report_path"
```

---

### Task 2: Planning & routing — `build_create_plan`, `plan_report`

**Files:**
- Modify: `science/src/science_tool/explore_ideas.py`
- Test: `science/tests/test_explore_ideas_apply.py`

**Interfaces:**
- Consumes: `CandidateBlock`, `ApplyValidationError`, `_VALID_DECISIONS`, `_ROUTABLE_KINDS`, `_MANUAL_KINDS`, `_VALID_KINDS` (Task 1); `OriginRecord` (`science_model.entities`).
- Produces:
  - `@dataclass(frozen=True) class CreatePlan: candidate_id: str; kind: str; title: str; origins: list[dict]; source_refs: list[str]; added_by: str`
  - `@dataclass(frozen=True) class ReportPlan: to_create: list[CreatePlan]; skipped_applied: list[str]; skipped_other: list[str]; manual: list[tuple[str, str]]`
  - `build_create_plan(candidate_id: str, data: dict, model_id: str) -> CreatePlan`
  - `plan_report(blocks: list[CandidateBlock], model_id: str) -> ReportPlan`

**Routing rules (from design §8):** `origins` ← `origin_plan.origins` verbatim (each validated via `OriginRecord`, date normalized to ISO string); `source_refs` ← each `literature_anchors[]` with a non-null string `ref` whose `note` does **not** start with `predates:`, deduped preserving first-seen order; `added_by` ← `explore-ideas:<model-id>:<candidate_id>`. Anchors with `ref: null` contribute nothing.

- [ ] **Step 1: Write the failing tests**

Append to `science/tests/test_explore_ideas_apply.py`:

```python
from science_tool.explore_ideas import (
    CreatePlan,
    ReportPlan,
    build_create_plan,
    plan_report,
)


def _keep_question(**over):
    data = {
        "candidate_id": "cand-q",
        "proposed_kind": "question",
        "title": "A question",
        "decision": "keep",
        "literature_anchors": [],
        "origin_plan": {"origins": [{"type": "assistant", "ref": "explore-ideas-mechanism"}]},
    }
    data.update(over)
    return data


def test_build_plan_reasoned_only() -> None:
    plan = build_create_plan("cand-q", _keep_question(), "opus")
    assert plan.kind == "question"
    assert plan.title == "A question"
    assert plan.origins == [{"type": "assistant", "ref": "explore-ideas-mechanism"}]
    assert plan.source_refs == []
    assert plan.added_by == "explore-ideas:opus:cand-q"


def test_build_plan_supporting_anchor_becomes_source_ref() -> None:
    data = _keep_question(
        literature_anchors=[{"ref": "cite:chen2022", "note": "supports the framing"}],
    )
    plan = build_create_plan("cand-q", data, "opus")
    assert plan.source_refs == ["cite:chen2022"]
    assert plan.origins == [{"type": "assistant", "ref": "explore-ideas-mechanism"}]


def test_build_plan_predates_anchor_is_not_a_source_ref() -> None:
    # A predates: anchor is already represented as a literature origin; it must
    # NOT be duplicated into source_refs.
    data = _keep_question(
        literature_anchors=[{"ref": "cite:okafor2015", "note": "predates: convergent"}],
        origin_plan={
            "origins": [
                {"type": "assistant", "ref": "explore-ideas-methodology"},
                {"type": "literature", "ref": "cite:okafor2015", "independent": True},
            ]
        },
    )
    plan = build_create_plan("cand-q", data, "opus")
    assert plan.source_refs == []
    assert any(o.get("independent") for o in plan.origins)


def test_build_plan_dedupes_source_refs_in_order() -> None:
    data = _keep_question(
        literature_anchors=[
            {"ref": "cite:a", "note": "x"},
            {"ref": "cite:b", "note": "y"},
            {"ref": "cite:a", "note": "again"},
            {"ref": None, "note": "unresolved"},
        ],
    )
    plan = build_create_plan("cand-q", data, "opus")
    assert plan.source_refs == ["cite:a", "cite:b"]


def test_build_plan_normalizes_yaml_date_object() -> None:
    from datetime import date

    data = _keep_question(
        origin_plan={
            "origins": [
                {"type": "assistant", "ref": "explore-ideas-methodology"},
                {"type": "literature", "ref": "cite:okafor2015", "independent": True, "date": date(2015, 3, 12)},
            ]
        },
    )
    plan = build_create_plan("cand-q", data, "opus")
    lit = [o for o in plan.origins if o["type"] == "literature"][0]
    assert lit["date"] == "2015-03-12"  # coerced to ISO string, not a date object


def test_build_plan_rejects_missing_title() -> None:
    with pytest.raises(ApplyValidationError):
        build_create_plan("cand-q", _keep_question(title=""), "opus")


def test_build_plan_rejects_missing_origins() -> None:
    with pytest.raises(ApplyValidationError):
        build_create_plan("cand-q", _keep_question(origin_plan={"origins": []}), "opus")


def test_build_plan_rejects_bad_origin() -> None:
    with pytest.raises(ApplyValidationError):
        build_create_plan(
            "cand-q",
            _keep_question(origin_plan={"origins": [{"type": "literature"}]}),  # literature needs a ref
            "opus",
        )


def test_build_plan_rejects_non_string_ref() -> None:
    with pytest.raises(ApplyValidationError):
        build_create_plan("cand-q", _keep_question(literature_anchors=[{"ref": 123}]), "opus")


def test_build_plan_rejects_non_string_note() -> None:
    with pytest.raises(ApplyValidationError):
        build_create_plan("cand-q", _keep_question(literature_anchors=[{"ref": "cite:a", "note": 5}]), "opus")


def test_build_plan_missing_note_routes_as_support() -> None:
    plan = build_create_plan("cand-q", _keep_question(literature_anchors=[{"ref": "cite:a"}]), "opus")
    assert plan.source_refs == ["cite:a"]


def test_plan_report_partitions_by_decision_and_kind() -> None:
    blocks = parse_report(
        """\
```yaml
candidate_id: k1
proposed_kind: question
title: One
decision: keep
origin_plan:
  origins:
    - type: assistant
      ref: explore-ideas-mechanism
```
```yaml
candidate_id: a1
proposed_kind: question
title: Two
decision: applied
```
```yaml
candidate_id: d1
proposed_kind: question
title: Three
decision: defer
```
```yaml
candidate_id: t1
proposed_kind: topic
title: Four
decision: keep
```
"""
    )
    plan = plan_report(blocks, "opus")
    assert [p.candidate_id for p in plan.to_create] == ["k1"]
    assert plan.skipped_applied == ["a1"]
    assert plan.skipped_other == ["d1"]
    assert plan.manual == [("t1", "topic")]


def test_plan_report_rejects_duplicate_ids() -> None:
    blocks = parse_report(
        "```yaml\ncandidate_id: dup\ndecision: drop\n```\n```yaml\ncandidate_id: dup\ndecision: drop\n```\n"
    )
    with pytest.raises(ApplyValidationError, match="duplicate"):
        plan_report(blocks, "opus")


def test_plan_report_rejects_unknown_decision() -> None:
    blocks = parse_report("```yaml\ncandidate_id: x\nproposed_kind: question\ndecision: maybe\n```\n")
    with pytest.raises(ApplyValidationError, match="decision"):
        plan_report(blocks, "opus")


def test_plan_report_rejects_unknown_kind() -> None:
    blocks = parse_report("```yaml\ncandidate_id: x\nproposed_kind: proverb\ndecision: keep\n```\n")
    with pytest.raises(ApplyValidationError, match="proposed_kind"):
        plan_report(blocks, "opus")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science && uv run --frozen pytest tests/test_explore_ideas_apply.py -k "plan" -v`
Expected: FAIL — `ImportError: cannot import name 'build_create_plan'`.

- [ ] **Step 3: Implement planning & routing**

Add to `science/src/science_tool/explore_ideas.py` — extend imports at the top and append the functions:

```python
# --- extend the existing imports at the top of the file ---
from datetime import date

from pydantic import ValidationError
from science_model.entities import OriginRecord
```

```python
# --- append below parse_report ---
@dataclass(frozen=True)
class CreatePlan:
    candidate_id: str
    kind: str
    title: str
    origins: list[dict]
    source_refs: list[str]
    added_by: str


@dataclass(frozen=True)
class ReportPlan:
    to_create: list[CreatePlan]
    skipped_applied: list[str]
    skipped_other: list[str]
    manual: list[tuple[str, str]]  # (candidate_id, proposed_kind)


def _normalize_origin(origin: object, candidate_id: str) -> dict:
    if not isinstance(origin, dict):
        raise ApplyValidationError(f"{candidate_id}: origin entry must be a mapping")
    normalized = dict(origin)
    value = normalized.get("date")
    if isinstance(value, date):  # YAML parses YYYY-MM-DD into a date; OriginRecord wants a str
        normalized["date"] = value.isoformat()
    return normalized


def build_create_plan(candidate_id: str, data: dict, model_id: str) -> CreatePlan:
    kind = data.get("proposed_kind")
    title = data.get("title")
    if not isinstance(title, str) or not title.strip():
        raise ApplyValidationError(f"{candidate_id}: keep block missing a non-empty 'title'")

    origin_plan = data.get("origin_plan")
    origins_raw = origin_plan.get("origins") if isinstance(origin_plan, dict) else None
    if not origins_raw:
        raise ApplyValidationError(f"{candidate_id}: keep block missing 'origin_plan.origins'")
    origins: list[dict] = []
    for origin in origins_raw:
        normalized = _normalize_origin(origin, candidate_id)
        try:
            OriginRecord.model_validate(normalized)
        except ValidationError as exc:
            raise ApplyValidationError(f"{candidate_id}: invalid origin {normalized!r}: {exc}") from exc
        origins.append(normalized)

    source_refs: list[str] = []
    seen: set[str] = set()
    for anchor in data.get("literature_anchors") or []:
        if not isinstance(anchor, dict):
            raise ApplyValidationError(f"{candidate_id}: literature_anchors entry must be a mapping")
        ref = anchor.get("ref")
        if ref is None:
            continue
        if not isinstance(ref, str):
            raise ApplyValidationError(f"{candidate_id}: anchor 'ref' must be a string")
        note = anchor.get("note")
        if note is not None and not isinstance(note, str):
            raise ApplyValidationError(f"{candidate_id}: anchor 'note' must be a string")
        if (note or "").startswith("predates:"):
            continue  # already represented as a literature origin
        if ref not in seen:
            seen.add(ref)
            source_refs.append(ref)

    return CreatePlan(
        candidate_id=candidate_id,
        kind=kind,
        title=title,
        origins=origins,
        source_refs=source_refs,
        added_by=f"explore-ideas:{model_id}:{candidate_id}",
    )


def plan_report(blocks: list[CandidateBlock], model_id: str) -> ReportPlan:
    ids = [b.candidate_id for b in blocks]
    duplicates = sorted({cid for cid in ids if ids.count(cid) > 1})
    if duplicates:
        raise ApplyValidationError(f"duplicate candidate_id(s): {', '.join(duplicates)}")

    to_create: list[CreatePlan] = []
    skipped_applied: list[str] = []
    skipped_other: list[str] = []
    manual: list[tuple[str, str]] = []
    errors: list[str] = []

    for block in blocks:
        decision = block.data.get("decision")
        if decision not in _VALID_DECISIONS:
            errors.append(f"{block.candidate_id}: unknown decision {decision!r}")
            continue
        if decision == "applied":
            skipped_applied.append(block.candidate_id)
            continue
        if decision in {"drop", "defer"}:
            skipped_other.append(block.candidate_id)
            continue
        # decision == "keep"
        kind = block.data.get("proposed_kind")
        if kind not in _VALID_KINDS:
            errors.append(f"{block.candidate_id}: unknown proposed_kind {kind!r}")
            continue
        if kind in _MANUAL_KINDS:
            manual.append((block.candidate_id, kind))
            continue
        try:
            to_create.append(build_create_plan(block.candidate_id, block.data, model_id))
        except ApplyValidationError as exc:
            errors.append(str(exc))

    if errors:
        raise ApplyValidationError("invalid keep block(s): " + "; ".join(errors))

    return ReportPlan(
        to_create=to_create,
        skipped_applied=skipped_applied,
        skipped_other=skipped_other,
        manual=manual,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_explore_ideas_apply.py -v`
Expected: PASS (all Task 1 + Task 2 tests).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/explore_ideas.py science/tests/test_explore_ideas_apply.py
git commit -m "feat(explore-ideas): apply planning & origin/source-ref routing"
```

---

### Task 3: Surgical write-back — `write_back`

**Files:**
- Modify: `science/src/science_tool/explore_ideas.py`
- Test: `science/tests/test_explore_ideas_apply.py`

**Interfaces:**
- Consumes: `ApplyWriteBackError` (Task 1).
- Produces: `write_back(text: str, candidate_id: str, entity_id: str, applied_at: str) -> str`. Re-locates the block **by `candidate_id`** in the current text (never a stored offset), replaces the value on its existing `decision:` line with `applied`, and inserts `applied_as:`/`applied_at:` lines right after it at matching indentation. Raises `ApplyWriteBackError` if the block or its `decision:` line is not found. Everything else is byte-for-byte preserved.

- [ ] **Step 1: Write the failing tests**

Append to `science/tests/test_explore_ideas_apply.py`:

```python
from science_tool.explore_ideas import ApplyWriteBackError, write_back

_WB_REPORT = """\
# Report

```yaml
candidate_id: cand-a
proposed_kind: question
title: First
rationale: >
  A folded scalar that must be preserved
  exactly across two lines.
decision: keep
origin_plan:
  origins:
    - type: assistant
      ref: explore-ideas-mechanism
```

```yaml
candidate_id: cand-b
proposed_kind: hypothesis
title: Second
decision: keep
```
"""


def test_write_back_flips_decision_and_inserts_fields() -> None:
    out = write_back(_WB_REPORT, "cand-a", "question-0007", "2026-07-04")
    assert "decision: applied\n" in out
    assert "applied_as: question-0007\n" in out
    assert "applied_at: 2026-07-04\n" in out
    # cand-b block untouched
    assert out.count("decision: keep") == 1


def test_write_back_preserves_everything_else() -> None:
    out = write_back(_WB_REPORT, "cand-a", "question-0007", "2026-07-04")
    # The folded rationale and surrounding prose survive byte-for-byte.
    assert "  A folded scalar that must be preserved\n  exactly across two lines.\n" in out
    assert out.startswith("# Report\n")


def test_write_back_targets_correct_block_by_id() -> None:
    out = write_back(_WB_REPORT, "cand-b", "hypothesis-0003", "2026-07-04")
    # Only cand-b changed; cand-a still keep.
    a_block = out.split("candidate_id: cand-a")[1].split("```")[0]
    assert "decision: keep" in a_block
    b_block = out.split("candidate_id: cand-b")[1].split("```")[0]
    assert "decision: applied" in b_block
    assert "applied_as: hypothesis-0003" in b_block


def test_write_back_is_composable_across_two_candidates() -> None:
    once = write_back(_WB_REPORT, "cand-a", "question-0007", "2026-07-04")
    twice = write_back(once, "cand-b", "hypothesis-0003", "2026-07-04")
    assert twice.count("decision: applied") == 2
    assert "applied_as: question-0007" in twice
    assert "applied_as: hypothesis-0003" in twice


def test_write_back_missing_candidate_raises() -> None:
    with pytest.raises(ApplyWriteBackError):
        write_back(_WB_REPORT, "cand-zzz", "x", "2026-07-04")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science && uv run --frozen pytest tests/test_explore_ideas_apply.py -k write_back -v`
Expected: FAIL — `ImportError: cannot import name 'write_back'`.

- [ ] **Step 3: Implement `write_back`**

Append to `science/src/science_tool/explore_ideas.py`:

```python
def write_back(text: str, candidate_id: str, entity_id: str, applied_at: str) -> str:
    """Mark one candidate's block ``applied`` in place; raise if it cannot be found.

    Re-locates the target block by ``candidate_id`` in the current text (offsets
    from an earlier parse may be stale after a prior write-back), so it is safe to
    call repeatedly, threading the returned text forward.
    """
    lines = text.splitlines(keepends=True)
    cand_re = re.compile(rf"^candidate_id:\s*{re.escape(candidate_id)}\s*$")
    decision_re = re.compile(r"^(\s*)decision:\s*\S.*$")

    i = 0
    n = len(lines)
    while i < n:
        if lines[i].rstrip("\n") == "```yaml":
            start = i + 1
            j = start
            while j < n and lines[j].rstrip("\n") != "```":
                j += 1
            if any(cand_re.match(lines[k].rstrip("\n")) for k in range(start, j)):
                for k in range(start, j):
                    m = decision_re.match(lines[k].rstrip("\n"))
                    if m:
                        indent = m.group(1)
                        lines[k] = f"{indent}decision: applied\n"
                        lines[k + 1 : k + 1] = [
                            f"{indent}applied_as: {entity_id}\n",
                            f"{indent}applied_at: {applied_at}\n",
                        ]
                        return "".join(lines)
                raise ApplyWriteBackError(
                    f"{candidate_id}: block has no 'decision:' line to mark applied"
                )
            i = j + 1
            continue
        i += 1
    raise ApplyWriteBackError(f"{candidate_id}: block not found in report for write-back")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_explore_ideas_apply.py -k write_back -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/explore_ideas.py science/tests/test_explore_ideas_apply.py
git commit -m "feat(explore-ideas): surgical report write-back by candidate_id"
```

---

### Task 4: Orchestration — `ApplyResult`, `CreatedEntity`, `apply_report`

**Files:**
- Modify: `science/src/science_tool/explore_ideas.py`
- Test: `science/tests/test_explore_ideas_apply.py`

**Interfaces:**
- Consumes: `resolve_report_path`, `parse_report`, `plan_report`, `write_back`, `ApplyWriteBackError` (Tasks 1–3); `create_entity`, `EntityCommandError` (`science_tool.entities`).
- Produces:
  - `@dataclass(frozen=True) class CreatedEntity: candidate_id: str; entity_id: str; kind: str; path: Path; warnings: list[str]`
  - `@dataclass(frozen=True) class ApplyResult` with fields `report: Path`, `created: list[CreatedEntity]`, `skipped_applied: list[str]`, `skipped_other: list[str]`, `manual: list[tuple[str, str]]`, `failures: list[tuple[str, str]]`, and a method `to_dict(self) -> dict`.
  - `apply_report(project_root: Path, from_value: str, model_id: str, today: date) -> ApplyResult`

**Behavior (design §5):** resolve + read report → `parse_report` → `plan_report` (fail-early: raises before any write). For each `CreatePlan`: `create_entity(...)` with `today=today`; on `EntityCommandError` record `(candidate_id, str(exc))` in `failures` and continue. On success, `write_back` + flush to disk immediately; if that write-back/flush fails, raise a fatal `ApplyWriteBackError` naming the created entity (do not continue).

- [ ] **Step 1: Write the failing integration tests**

Append to `science/tests/test_explore_ideas_apply.py`:

```python
from datetime import date

from _fixtures.entity_helpers import seed_project

from science_tool.explore_ideas import ApplyResult, apply_report

_FIXTURE = """\
---
type: meta
id: explore-2026-07-04
title: Exploration report — 2026-07-04
created: 2026-07-04
---

# Exploration report — 2026-07-04

```yaml
candidate_id: cand-mechanism-vagal-cytokine-loop
proposed_kind: question
title: Vagal tone as a cytokine feedback regulator
question_or_claim: Does reduced vagal tone sustain systemic inflammation?
lens: mechanism
rationale: >
  Established in acute sepsis, under-explored as chronic feedback failure.
literature_anchors:
  - doi: 10.1000/chen2022-vagal
    title: Vagal afferents and cytokine feedback
    first_author: Chen
    year: 2022
    note: supports the feedback-loop framing
    ref: cite:chen2022
novelty_bucket: novel
related_existing: []
decision: keep
origin_plan:
  origins:
    - type: assistant
      ref: explore-ideas-mechanism
```

```yaml
candidate_id: cand-methodology-retest-drift-threshold
proposed_kind: hypothesis
title: Retest interval drives apparent measurement drift
question_or_claim: A fixed retest interval below the assay autocorrelation timescale manifests as spurious drift.
lens: methodology
rationale: >
  Reasoned independently before locating prior work making the same point.
literature_anchors:
  - doi: 10.1000/okafor2015-retest
    title: Autocorrelation timescales and apparent drift
    first_author: Okafor
    year: 2015
    date: 2015-03-12
    note: "predates: independently reasoned convergence"
    ref: cite:okafor2015
novelty_bucket: novel
related_existing: []
decision: keep
origin_plan:
  origins:
    - type: assistant
      ref: explore-ideas-methodology
    - type: literature
      ref: cite:okafor2015
      independent: true
      date: 2015-03-12
```

```yaml
candidate_id: cand-contrarian-null-effect
proposed_kind: question
title: Is the effect fully explained by selection bias?
lens: contrarian
rationale: >
  Included to exercise the drop path.
literature_anchors: []
novelty_bucket: out-of-scope
related_existing: []
decision: drop
origin_plan:
  origins:
    - type: assistant
      ref: explore-ideas-contrarian
```
"""


def _write_fixture(root: Path) -> Path:
    d = root / "entities" / "meta" / "explorations"
    d.mkdir(parents=True)
    report = d / "explore-2026-07-04.md"
    report.write_text(_FIXTURE, encoding="utf-8")
    return report


def _frontmatter(path: Path) -> dict:
    import yaml as _yaml

    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), text[:40]
    fm, _, _ = text[4:].partition("\n---")
    return _yaml.safe_load(fm)


def test_apply_report_creates_kept_entities(tmp_path: Path) -> None:
    seed_project(tmp_path)
    report = _write_fixture(tmp_path)

    result = apply_report(tmp_path, "explore-2026-07-04", "test-model", date(2026, 7, 4))

    assert isinstance(result, ApplyResult)
    assert len(result.created) == 2
    kinds = sorted(c.kind for c in result.created)
    assert kinds == ["hypothesis", "question"]
    assert result.skipped_other == ["cand-contrarian-null-effect"]
    assert result.failures == []

    q_files = list((tmp_path / "entities" / "questions").glob("*.md"))
    h_files = list((tmp_path / "entities" / "hypotheses").glob("*.md"))
    assert len(q_files) == 1 and len(h_files) == 1


def test_apply_report_routes_origins_and_source_refs(tmp_path: Path) -> None:
    seed_project(tmp_path)
    _write_fixture(tmp_path)
    apply_report(tmp_path, "explore-2026-07-04", "test-model", date(2026, 7, 4))

    q_fm = _frontmatter(next((tmp_path / "entities" / "questions").glob("*.md")))
    # supporting anchor -> source_ref, and it is NOT stored as an origin
    assert q_fm["source_refs"] == ["cite:chen2022"]
    assert all(o.get("ref") != "cite:chen2022" for o in q_fm.get("origins") or [])
    assert q_fm["added_by"] == "explore-ideas:test-model:cand-mechanism-vagal-cytokine-loop"

    h_fm = _frontmatter(next((tmp_path / "entities" / "hypotheses").glob("*.md")))
    lit = [o for o in h_fm["origins"] if o["type"] == "literature"]
    assert len(lit) == 1
    assert lit[0]["ref"] == "cite:okafor2015"
    assert lit[0]["independent"] is True
    assert str(lit[0]["date"]) == "2015-03-12"  # str(): yaml may reload it as a date
    # the predates anchor did NOT also become a source_ref
    assert "cite:okafor2015" not in (h_fm.get("source_refs") or [])


def test_apply_report_writes_back_and_is_idempotent(tmp_path: Path) -> None:
    seed_project(tmp_path)
    report = _write_fixture(tmp_path)

    apply_report(tmp_path, "explore-2026-07-04", "test-model", date(2026, 7, 4))
    text = report.read_text(encoding="utf-8")
    assert text.count("decision: applied") == 2
    assert "applied_at: 2026-07-04" in text
    assert text.count("decision: drop") == 1  # drop block untouched

    # Second apply: nothing new created, both keeps now skipped_applied.
    result2 = apply_report(tmp_path, "explore-2026-07-04", "test-model", date(2026, 7, 4))
    assert result2.created == []
    assert sorted(result2.skipped_applied) == [
        "cand-methodology-retest-drift-threshold",
        "cand-mechanism-vagal-cytokine-loop",
    ]
    assert len(list((tmp_path / "entities" / "questions").glob("*.md"))) == 1
    assert len(list((tmp_path / "entities" / "hypotheses").glob("*.md"))) == 1


def test_apply_report_to_dict_shape(tmp_path: Path) -> None:
    seed_project(tmp_path)
    _write_fixture(tmp_path)
    result = apply_report(tmp_path, "explore-2026-07-04", "test-model", date(2026, 7, 4))
    d = result.to_dict()
    assert set(d) == {"report", "created", "skipped_applied", "skipped_other", "manual", "failures"}
    assert d["created"][0].keys() >= {"candidate_id", "entity_id", "kind", "path", "warnings"}
    assert d["skipped_other"] == ["cand-contrarian-null-effect"]


# Two keep questions: the second title cannot derive a stable slug, so
# create_entity raises EntityCommandError for it while the first succeeds.
_TWO_KEEP = """\
---
type: meta
id: explore-2026-07-04
---

```yaml
candidate_id: cand-good
proposed_kind: question
title: A well-formed question
decision: keep
origin_plan:
  origins:
    - type: assistant
      ref: explore-ideas-mechanism
```

```yaml
candidate_id: cand-bad
proposed_kind: question
title: "!!!"
decision: keep
origin_plan:
  origins:
    - type: assistant
      ref: explore-ideas-mechanism
```
"""


def _write_two_keep(root: Path) -> Path:
    d = root / "entities" / "meta" / "explorations"
    d.mkdir(parents=True)
    report = d / "explore-2026-07-04.md"
    report.write_text(_TWO_KEEP, encoding="utf-8")
    return report


def test_apply_report_continues_past_create_failure(tmp_path: Path) -> None:
    seed_project(tmp_path)
    report = _write_two_keep(tmp_path)

    result = apply_report(tmp_path, "explore-2026-07-04", "m", date(2026, 7, 4))

    assert [c.candidate_id for c in result.created] == ["cand-good"]
    assert [cid for cid, _ in result.failures] == ["cand-bad"]
    # Only the successful block was written back; the failed one stays keep.
    text = report.read_text(encoding="utf-8")
    good = text.split("candidate_id: cand-good")[1].split("```")[0]
    bad = text.split("candidate_id: cand-bad")[1].split("```")[0]
    assert "decision: applied" in good
    assert "decision: keep" in bad
    # Exactly one question file exists (the good one).
    assert len(list((tmp_path / "entities" / "questions").glob("*.md"))) == 1


def test_apply_report_fatal_writeback_names_entity(tmp_path: Path, monkeypatch) -> None:
    seed_project(tmp_path)
    _write_fixture(tmp_path)

    import science_tool.explore_ideas as mod

    def _boom(*args, **kwargs):
        raise ApplyWriteBackError("simulated write-back failure")

    monkeypatch.setattr(mod, "write_back", _boom)

    with pytest.raises(ApplyWriteBackError) as excinfo:
        apply_report(tmp_path, "explore-2026-07-04", "m", date(2026, 7, 4))

    message = str(excinfo.value)
    assert "retry" in message.lower()
    assert "applied_as" in message  # tells the user how to repair the report
    # The entity WAS created before the write-back failed (proves the ordering).
    assert list((tmp_path / "entities" / "questions").glob("*.md"))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science && uv run --frozen pytest tests/test_explore_ideas_apply.py -k apply_report -v`
Expected: FAIL — `ImportError: cannot import name 'apply_report'`.

- [ ] **Step 3: Implement orchestration**

Extend the imports at the top of `science/src/science_tool/explore_ideas.py`:

```python
from science_tool.entities import EntityCommandError, create_entity
```

Append to the module:

```python
@dataclass(frozen=True)
class CreatedEntity:
    candidate_id: str
    entity_id: str
    kind: str
    path: Path
    warnings: list[str]


@dataclass(frozen=True)
class ApplyResult:
    report: Path
    created: list[CreatedEntity]
    skipped_applied: list[str]
    skipped_other: list[str]
    manual: list[tuple[str, str]]
    failures: list[tuple[str, str]]  # (candidate_id, error)

    def to_dict(self) -> dict:
        return {
            "report": str(self.report),
            "created": [
                {
                    "candidate_id": c.candidate_id,
                    "entity_id": c.entity_id,
                    "kind": c.kind,
                    "path": str(c.path),
                    "warnings": list(c.warnings),
                }
                for c in self.created
            ],
            "skipped_applied": list(self.skipped_applied),
            "skipped_other": list(self.skipped_other),
            "manual": [{"candidate_id": cid, "proposed_kind": kind} for cid, kind in self.manual],
            "failures": [{"candidate_id": cid, "error": err} for cid, err in self.failures],
        }


def apply_report(project_root: Path, from_value: str, model_id: str, today: date) -> ApplyResult:
    report_path = resolve_report_path(project_root, from_value)
    text = report_path.read_text(encoding="utf-8")
    blocks = parse_report(text)
    plan = plan_report(blocks, model_id)  # fail-early: raises ApplyValidationError before any write

    created: list[CreatedEntity] = []
    failures: list[tuple[str, str]] = []

    for cp in plan.to_create:
        try:
            result = create_entity(
                project_root,
                kind=cp.kind,
                title=cp.title,
                source_refs=cp.source_refs,
                today=today,
                extra_frontmatter={"origins": cp.origins, "added_by": cp.added_by},
            )
        except EntityCommandError as exc:
            failures.append((cp.candidate_id, str(exc)))
            continue

        try:
            text = write_back(text, cp.candidate_id, result.entity_id, today.isoformat())
            report_path.write_text(text, encoding="utf-8")
        except (ApplyWriteBackError, OSError) as exc:
            raise ApplyWriteBackError(
                f"created entity {result.entity_id} at {result.path}, but failed to record it in "
                f"{report_path}: {exc}. Mark that candidate's block 'decision: applied' with "
                f"'applied_as: {result.entity_id}' before retrying, or a retry may create a duplicate."
            ) from exc

        created.append(
            CreatedEntity(cp.candidate_id, result.entity_id, cp.kind, result.path, list(result.warnings))
        )

    return ApplyResult(
        report=report_path,
        created=created,
        skipped_applied=plan.skipped_applied,
        skipped_other=plan.skipped_other,
        manual=plan.manual,
        failures=failures,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_explore_ideas_apply.py -v`
Expected: PASS (all tests through Task 4).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/explore_ideas.py science/tests/test_explore_ideas_apply.py
git commit -m "feat(explore-ideas): apply_report orchestration + ApplyResult"
```

---

### Task 5: CLI — `science explore-ideas apply`

**Files:**
- Modify: `science/src/science_tool/cli.py`
- Test: `science/tests/test_explore_ideas_apply.py`

**Interfaces:**
- Consumes: `apply_report`, `ApplyValidationError`, `ApplyWriteBackError` (`science_tool.explore_ideas`); `_emit_entity_warnings` (already in `cli.py`).
- Produces: CLI `science explore-ideas apply --from <value> --model-id <id> [--format text|json]`, exit non-zero on validation/write-back error or any per-item failure.

- [ ] **Step 1: Write the failing tests**

Append to `science/tests/test_explore_ideas_apply.py`:

```python
import json

from click.testing import CliRunner

from science_tool.cli import main


def test_cli_apply_requires_from() -> None:
    result = CliRunner().invoke(main, ["explore-ideas", "apply", "--model-id", "m"])
    assert result.exit_code != 0
    assert "from" in result.output.lower()


def test_cli_apply_requires_model_id() -> None:
    result = CliRunner().invoke(main, ["explore-ideas", "apply", "--from", "explore-2026-07-04"])
    assert result.exit_code != 0
    assert "model-id" in result.output.lower()


def test_cli_apply_round_trip_text() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)
        _write_fixture(root)
        result = runner.invoke(
            main,
            ["explore-ideas", "apply", "--from", "explore-2026-07-04", "--model-id", "test-model"],
        )
        assert result.exit_code == 0, result.output
        assert "2 created" in result.output
        assert len(list((root / "entities" / "questions").glob("*.md"))) == 1
        assert len(list((root / "entities" / "hypotheses").glob("*.md"))) == 1


def test_cli_apply_json_format() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)
        _write_fixture(root)
        result = runner.invoke(
            main,
            ["explore-ideas", "apply", "--from", "explore-2026-07-04", "--model-id", "m", "--format", "json"],
        )
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert len(payload["created"]) == 2
        assert payload["skipped_other"] == ["cand-contrarian-null-effect"]


def test_cli_apply_missing_report_errors() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        seed_project(Path.cwd())
        result = runner.invoke(
            main, ["explore-ideas", "apply", "--from", "nope", "--model-id", "m"]
        )
        assert result.exit_code != 0
        assert "not found" in result.output.lower()


def _patch_create_with_warning(monkeypatch, warning: str) -> None:
    import science_tool.explore_ideas as mod
    from science_tool.entities import EntityWriteResult

    real = mod.create_entity

    def _warned(*args, **kwargs):
        res = real(*args, **kwargs)
        return EntityWriteResult(entity_id=res.entity_id, path=res.path, warnings=[warning])

    monkeypatch.setattr(mod, "create_entity", _warned)


def test_cli_apply_emits_warnings_in_text(monkeypatch) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)
        _write_fixture(root)
        _patch_create_with_warning(monkeypatch, "heads up: derived id truncated")
        result = runner.invoke(
            main, ["explore-ideas", "apply", "--from", "explore-2026-07-04", "--model-id", "m"]
        )
        assert result.exit_code == 0, result.output
        assert "heads up: derived id truncated" in result.output


def test_cli_apply_json_stays_valid_with_warnings(monkeypatch) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)
        _write_fixture(root)
        _patch_create_with_warning(monkeypatch, "w!")
        result = runner.invoke(
            main,
            ["explore-ideas", "apply", "--from", "explore-2026-07-04", "--model-id", "m", "--format", "json"],
        )
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)  # must parse: warnings must not be echoed outside the JSON
        assert payload["created"][0]["warnings"] == ["w!"]


def test_cli_apply_nonzero_on_failure() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)
        _write_two_keep(root)
        result = runner.invoke(
            main, ["explore-ideas", "apply", "--from", "explore-2026-07-04", "--model-id", "m"]
        )
        assert result.exit_code != 0
        assert "1 failed" in result.output or "FAILED" in result.output
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science && uv run --frozen pytest tests/test_explore_ideas_apply.py -k cli_apply -v`
Expected: FAIL — no such command `explore-ideas`.

- [ ] **Step 3: Implement the CLI group**

In `science/src/science_tool/cli.py`, ensure `from datetime import date` and `import json` are imported at the top (add whichever is missing). Then add the group near the other `@main.group(...)` definitions (e.g. after the `interpretations` group, before `_build_origin_frontmatter`):

```python
from science_tool.explore_ideas import (
    ApplyValidationError,
    ApplyWriteBackError,
    apply_report,
)


@main.group("explore-ideas")
def explore_ideas_group() -> None:
    """Explore-ideas commands."""


@explore_ideas_group.command("apply")
@click.option("--from", "from_value", required=True, help="Report file path, or report id (basename stem).")
@click.option("--model-id", "model_id", required=True, help="Model id for the --added-by provenance stamp.")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    show_default=True,
)
def explore_ideas_apply(from_value: str, model_id: str, output_format: str) -> None:
    """Apply kept candidates from an exploration report to real entities."""
    try:
        result = apply_report(Path.cwd(), from_value, model_id, date.today())
    except (ApplyValidationError, ApplyWriteBackError) as exc:
        raise click.ClickException(str(exc)) from exc

    if output_format == "json":
        # JSON already carries per-entity warnings; do NOT echo anything else to
        # stdout here or the output stops being parseable JSON.
        click.echo(json.dumps(result.to_dict(), indent=2))
    else:
        click.echo(
            f"{len(result.created)} created, "
            f"{len(result.skipped_applied)} already applied, "
            f"{len(result.skipped_other)} deferred/dropped, "
            f"{len(result.manual)} to apply manually, "
            f"{len(result.failures)} failed"
        )
        for c in result.created:
            click.echo(f"  created {c.candidate_id} -> {c.entity_id} ({c.kind})")
        for cid, kind in result.manual:
            click.echo(f"  apply manually ({kind}): {cid}")
        for cid, err in result.failures:
            click.echo(f"  FAILED {cid}: {err}")
        # Surface create_entity warnings only in text mode.
        for c in result.created:
            _emit_entity_warnings(c.warnings)

    if result.failures:
        raise SystemExit(1)
```

Note: prefer top-of-file imports; if the module's import layout keeps imports grouped at the top, move the `from science_tool.explore_ideas import ...` block there rather than mid-file.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_explore_ideas_apply.py -v`
Then lint/type the touched files:
Run: `cd science && uv run ruff check src/science_tool/explore_ideas.py src/science_tool/cli.py && uv run pyright src/science_tool/explore_ideas.py src/science_tool/cli.py`
Expected: all tests PASS; ruff and pyright clean for both touched files. (If targeted pyright is flaky here, fall back to the header convention `uv run pyright`.)

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/cli.py science/tests/test_explore_ideas_apply.py
git commit -m "feat(explore-ideas): science explore-ideas apply CLI"
```

---

### Task 6: Command rewrite, codex mirror, doc consolidation

**Files:**
- Modify: `commands/explore-ideas.md`
- Regenerate: `codex-skills/science-explore-ideas/SKILL.md`, `codex-skills/INDEX.md`
- Delete: `docs/plans/2026-07-04-explore-ideas-manual-check.md`
- Modify: `docs/plans/2026-07-04-explore-ideas-design.md`
- Test: `science/tests/test_codex_skills.py` (existing sync gate)

**Interfaces:**
- Consumes: the shipped `science explore-ideas apply` CLI (Task 5).
- Produces: no code; a command that delegates to the CLI, and design docs consistent with the shipped surface.

- [ ] **Step 1: Rewrite the Apply mode section of `commands/explore-ideas.md`**

Replace the entire current `## Apply mode` section, including the "Create command
templates" and "Literature anchor routing" subsections, with the block below.
Today that section runs from `## Apply mode` through the end of the file; if a
future edit adds sections after Apply mode, stop before the next `## ` heading
instead of deleting unrelated content.

````markdown
## Apply mode

Apply is a single deterministic CLI call — this command does **not** re-derive
create logic in prose. Require `--from`; if absent, STOP with a clear error (see
Flags).

Run, from the project root:

```bash
uv run science explore-ideas apply --from <report-path-or-id> --model-id <your-model-id>
```

- `<report-path-or-id>` is the `--from` value: a path to the report file, or the
  report id — its basename stem, e.g. `explore-2026-07-04` (the `explore-` prefix
  is already part of the id and is not re-prepended).
- `<your-model-id>` is the id of the model running this command.

The CLI parses every fenced `yaml` block that has a `candidate_id`, and for each
`decision: keep` question/hypothesis it creates a real entity — routing
`origin_plan.origins` to `origins`, supporting (non-`predates:`) resolved anchors
to `source_refs`, and stamping `--added-by explore-ideas:<model-id>:<candidate_id>`
— then writes `decision: applied` + `applied_as` + `applied_at` back into that
block. It is idempotent: a re-run skips blocks already `applied`. `topic`/`theme`
keeps are reported as "apply manually"; `drop`/`defer` are skipped. Bad input
(duplicate ids, unknown `decision`/`proposed_kind`, a `keep` block missing
`title`/`origin_plan.origins`, or an invalid origin) is rejected before anything
is written.

Relay the CLI's created / skipped / manual / failure summary to the user. If
`--commit` was passed, commit the created entities plus the updated report with
`feat(explore-ideas): apply kept candidates YYYY-MM-DD`.

Add `--format json` if you need the machine-readable result instead of the text
summary.
````

- [ ] **Step 2: Regenerate the codex mirror**

Run (from the repo root):

```bash
python scripts/generate_codex_skills.py
```

Expected: `codex-skills/science-explore-ideas/SKILL.md` and `codex-skills/INDEX.md` update to match the rewritten command.

- [ ] **Step 3: Delete the superseded manual-check doc**

```bash
git rm docs/plans/2026-07-04-explore-ideas-manual-check.md
```

- [ ] **Step 4: Update the parent design doc**

In `docs/plans/2026-07-04-explore-ideas-design.md`:

Replace this bullet in §12 (Deferred):

```markdown
- A durable `science explore-ideas classify|apply` CLI, if/when the slash
  command's classify/apply logic outgrows prose orchestration.
```

with:

```markdown
- A durable `science explore-ideas classify` CLI (classify stays agent judgment
  in the command for now). The `apply` half **shipped** — see
  `2026-07-04-explore-ideas-apply-cli-design.md`; apply mechanics are now the
  tested `science explore-ideas apply` CLI, not command prose.
```

Then replace the "Smoke/manual — apply round-trip" bullet in §13 (its text begins
`- **Smoke/manual — apply round-trip:**` and runs to the end of that bullet) with:

```markdown
- **Apply round-trip (now deterministic):** apply mechanics moved into
  `science explore-ideas apply` and are covered by
  `science/tests/test_explore_ideas_apply.py` (routing, write-back, idempotence,
  and an end-to-end create against a seeded project). The former manual smoke-check
  doc (`2026-07-04-explore-ideas-manual-check.md`) is retired; its fixture lives in
  that test.
```

- [ ] **Step 5: Verify the codex sync gate and commit**

Run: `cd science && uv run --frozen pytest tests/test_codex_skills.py -v`
Expected: PASS (mirror is in sync).

```bash
git add commands/explore-ideas.md codex-skills/ docs/plans/2026-07-04-explore-ideas-design.md
git commit -m "refactor(explore-ideas): delegate apply to the CLI; retire manual-check doc"
```

Note: Step 3's `git rm` already staged the deletion; it is included in this commit.

---

## Self-Review

**1. Spec coverage** (against `2026-07-04-explore-ideas-apply-cli-design.md`):
- §3 module/CLI/command layout → Tasks 1–6. ✓
- §4 CLI surface (`--from`/`--model-id` required, `--format`, no `--commit`, exit codes) → Task 5. ✓
- §5 pipeline (resolve/parse/plan/execute/return) + malformed-YAML validation + fatal write-back → Tasks 1,2,4. ✓
- §6 pre-flight rejections (dupe id, unknown decision/kind, missing title/origins, bad origin, non-string ref/note, missing-note-ok) → Task 2 tests. ✓
- §7 `ApplyResult` shape incl. `path`/`warnings` + warnings surfaced → Task 4 (`to_dict`) + Task 5 (`_emit_entity_warnings`). ✓
- §8 routing (origins verbatim, source_refs non-predates + dedupe, added_by, date normalize) → Task 2. ✓
- §9 command rewrite → Task 6. ✓
- §10 tests: integration round-trip + idempotence + frontmatter-parsed routing (Task 4), per-item `EntityCommandError` continuation with only-success write-back (Task 4), fatal write-back naming the entity (Task 4), text-mode warning rendering + JSON-stays-valid-with-warnings + non-zero exit on failure (Task 5). ✓
- §10 doc consolidation (delete manual-check, update §12/§13) → Task 6. ✓

**2. Placeholder scan:** No TBD/TODO; every code step carries complete code and exact commands. ✓

**3. Type consistency:** `apply_report(project_root, from_value, model_id, today)` and `create_entity(project_root, kind=, title=, source_refs=, today=, extra_frontmatter=)` match the read source. `EntityWriteResult.{entity_id,path,warnings}` used consistently. `CreatePlan`/`ReportPlan`/`CreatedEntity`/`ApplyResult` field names identical across Tasks 2/4/5. `write_back(text, candidate_id, entity_id, applied_at)` signature identical in Tasks 3 and 4. ✓

**Note for the executor:** one behavior to confirm during Task 4 review — `create_entity` accepts `origins` as a list of plain dicts inside `extra_frontmatter` (this mirrors `_build_origin_frontmatter`, which stores `parse_origin_spec` dicts the same way). If a future change makes it require `OriginRecord` instances, adapt `apply_report` to construct them; the pre-flight already validates each dict via `OriginRecord.model_validate`.

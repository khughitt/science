# Code-file Registration & Validation (Spec 1, Plan B1) — Core Walk + Gate Ladder — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Walk the declared code roots during `science validate` and flag every in-scope code file that is unregistered (no `# science:code` block), malformed, or incompletely registered (bad status, unknown `task_ids`, no committed content date), and add a default-off `--fail-on` gate ladder so a project can promote selected findings to a nonzero exit.

**Architecture:** A new canonical `@Check` (`code_files.py`) reuses Plan A's `CodeAdapter.discover()` to enumerate code files under `code_roots`, parses each with Plan A's `parse_code_metadata`, and emits **WARN/INFO-only** `Result`s (never ERROR — so Tier 0, report-only, the default, never blocks `validate`). A separate `gates.py` module owns the tier→rule ladder (a stable 4-tier vocabulary) and the cumulative gating decision; the runner attaches the gate decision to `RunResult` on **non-serialized** fields and the CLI grows a `--fail-on` option, so the strict JSON output contract (`additionalProperties: false` at every level) is untouched. Findings travel as validation `Result`s, never as `graph materialize` preconditions (the §6 fragility firewall). This plan implements Tier 0–1 (ghost/malformed) plus the hygiene-tier rules (metadata-gap, unresolved-task, uncommitted); classification, the Snakemake reference parser, orphan detection (Tier 2), and hardcoded-path detection (Tier 3's `code.hardcoded-path`) are **Plan B2**.

**Tech Stack:** Python 3.12+, `click`, pydantic v2. Single `uv` package touched: `science_tool` (in `science/`, tests in `science/tests/`). Run tool tests with `cd science && uv run pytest …`. This plan builds entirely on Plan A's committed work: `science_tool.code.metadata.parse_code_metadata` (three-state `CodeMetadata` with `.present`/`.fields`/`.error`/`.valid`), `science_tool.code.git.last_content_change_date(rel_path, *, repo_root)`, `science_tool.graph.storage_adapters.code.CodeAdapter(code_roots=…, repo_root=…, excludes=…)` with `discover(project_root) -> list[SourceRef]`, and `science_tool.paths.resolve_paths` (which surfaces `code_roots`/`code_excludes`/`tasks_dir`).

**Conventions observed:**
- A check is a function `def check_x(ctx: ValidateContext) -> Iterator[Result]` decorated `@Check(section="…", order=N)`; the decorator appends to `CANONICAL_CHECKS` (sorted by `order`). The module must be added to the import tuple in `science/src/science_tool/validate/checks/__init__.py::_load_canonical_checks` so its decorator runs.
- `Result(severity, path, line, message, rule, task)` is a frozen positional dataclass (`science/src/science_tool/validate/result.py:23`). `Severity` ∈ {`ERROR`, `WARN`, `INFO`}. `rule` is a free string; existing rules use both flat (`"manifest"`, `"directory_structure"`) and dotted (`"demo.warn"`) forms — this plan uses the dotted `code.*` namespace.
- Checks define a local `_result(...)` helper that pins the `rule` (see `directory_structure.py:14`).
- Existing exit contract: `validate_cmd` exits 1 iff `result.errors > 0` (`cli.py:71`). `--strict` is threaded to checks but does **not** promote WARN→ERROR (`test_validate_cli.py::test_validate_strict_is_passed_through_without_promoting_warnings`).
- Free `@Check` order slots are **6** and **15** (0–5, 7–14, 16–22 are taken; 7 is shared by `references`/`papers`). This plan uses **order=6**.

---

## File Structure

**New files:**
- `science/src/science_tool/code/lifecycle.py` — the authoritative code-file lifecycle status vocabulary (`CODE_FILE_STATUSES`). One responsibility: name the legal `status` values. Reused by B2's classification.
- `science/src/science_tool/validate/gates.py` — the `--fail-on` gate ladder: the ordered tier vocabulary, the tier→rule mapping, cumulative-rule resolution, tier resolution from flag/manifest, and the gating decision. Pure functions, no I/O.
- `science/src/science_tool/validate/checks/code_files.py` — the tree-walk `@Check`.
- `science/tests/test_code_lifecycle.py`, `science/tests/validate/test_gates.py`, `science/tests/validate/test_checks_code_files.py` — tests.

**Modified files:**
- `science/src/science_tool/tasks.py` — add `known_task_ids(tasks_dir)` (header-only scan; the resolution oracle for `task_ids`).
- `science/src/science_tool/validate/checks/__init__.py` — register the `code_files` module.
- `science/src/science_tool/validate/runner.py` — add a `fail_on` parameter to `run`, two non-serialized `RunResult` fields (`gate_tier`, `gated`), and attach the gate decision.
- `science/src/science_tool/validate/cli.py` — add `--fail-on`, exit on gated findings, and a gate-aware text summary line.
- `science/tests/validate/test_formatter_snapshots.py` + `science/tests/validate/snapshots/text_default.txt` — add `code_files` to the pinned canonical tuple and regenerate the text snapshot (gains the code-files section banner; the JSON snapshot is unchanged).
- `science/tests/validate/test_parity_corpus.py` — add `code_files` to the pinned tuple (Python-only; silent on the code-less fixture).
- `science/tests/validate/test_parity_canonical_body.py` — record (in a comment) that `code_files` is intentionally excluded from bash-vs-Python parity.
- `docs/conventions/validate.md` — update Synopsis/Flags/Exit Codes/Severity Model (gated warnings can now fail) and add the code-files / `--fail-on` ladder section.

Each file has one responsibility: `lifecycle.py` names statuses, `gates.py` is the gate policy, `code_files.py` walks and reports, the runner/CLI wire the gate to the exit code.

---

## Task 1: The code-file lifecycle status vocabulary

**Files:**
- Create: `science/src/science_tool/code/lifecycle.py`
- Test: `science/tests/test_code_lifecycle.py`

The umbrella design §6 fixes the lifecycle vocabulary: `exploratory`, `workflow-owned`, `library`, `retired`. Per the §6 fragility firewall, this is validated as a `Result` (Task 4), **not** enforced on the pydantic `CodeFileEntity` model (which stays permissive so a typo cannot hard-fail `graph materialize`). So the vocabulary lives here, consumed by the check.

- [ ] **Step 1: Write the failing test**

Create `science/tests/test_code_lifecycle.py`:

```python
from science_tool.code.lifecycle import CODE_FILE_STATUSES


def test_lifecycle_vocabulary_is_exact() -> None:
    assert CODE_FILE_STATUSES == frozenset(
        {"exploratory", "workflow-owned", "library", "retired"}
    )


def test_vocabulary_is_immutable() -> None:
    assert isinstance(CODE_FILE_STATUSES, frozenset)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run pytest tests/test_code_lifecycle.py -q`
Expected: FAIL — `ModuleNotFoundError: science_tool.code.lifecycle`.

- [ ] **Step 3: Implement the module**

Create `science/src/science_tool/code/lifecycle.py`:

```python
"""The code-file lifecycle status vocabulary (umbrella design §6).

`status` is authored in the `# science:code` block and validated as a WARN
`Result` by the code-files check — never enforced on the CodeFileEntity model,
so an unrecognized value cannot hard-fail `graph materialize` (the §6 fragility
firewall). `exploratory` is the pressure-release valve: exempt from
workflow-ownership gating (Tier 2, Plan B2) but never from registration.
"""

from __future__ import annotations

CODE_FILE_STATUSES: frozenset[str] = frozenset(
    {
        "exploratory",
        "workflow-owned",
        "library",
        "retired",
    }
)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science && uv run pytest tests/test_code_lifecycle.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/code/lifecycle.py science/tests/test_code_lifecycle.py
git commit -m "feat(code): add code-file lifecycle status vocabulary"
```

---

## Task 2: `known_task_ids` — the task-id resolution oracle

**Files:**
- Modify: `science/src/science_tool/tasks.py` (add a function after `_task_search_paths`, ~line 284)
- Test: `science/tests/test_tasks_known_ids.py`

`code-file.task_ids` are bare ids like `t491`. To validate they resolve (Task 4), the check needs the set of declared task ids. Tasks are declared as `## [tNNN] Title` headers in `tasks/active.md` and `tasks/done/*.md`. Use a **header-only scan** (reusing the module's `_HEADER_RE`, which matches only valid `tNNN` headers and exposes the id as group 1) rather than the full `parse_tasks` — a field-level problem in one task block must not crash a caller that only needs the id set; `check_tasks` owns reporting malformed blocks.

- [ ] **Step 1: Write the failing test**

Create `science/tests/test_tasks_known_ids.py`:

```python
from pathlib import Path

from science_tool.tasks import known_task_ids


def test_collects_ids_from_active_and_done(tmp_path: Path) -> None:
    tasks = tmp_path / "tasks"
    (tasks / "done").mkdir(parents=True)
    (tasks / "active.md").write_text(
        "## [t491] Active one\n- created: 2026-01-01\n\n## [t492] Active two\n- created: 2026-01-01\n",
        encoding="utf-8",
    )
    (tasks / "done" / "2026-01.md").write_text(
        "## [t100] Done one\n- created: 2026-01-01\n",
        encoding="utf-8",
    )
    assert known_task_ids(tasks) == {"t491", "t492", "t100"}


def test_missing_tasks_dir_is_empty(tmp_path: Path) -> None:
    assert known_task_ids(tmp_path / "tasks") == set()


def test_ignores_invalid_headers(tmp_path: Path) -> None:
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    # 'task-1' is not a valid tNNN id, so it must not be collected.
    (tasks / "active.md").write_text(
        "## [t491] Valid\n- created: 2026-01-01\n\n## [task-1] Invalid\n- created: 2026-01-01\n",
        encoding="utf-8",
    )
    assert known_task_ids(tasks) == {"t491"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run pytest tests/test_tasks_known_ids.py -q`
Expected: FAIL — `ImportError: cannot import name 'known_task_ids'`.

- [ ] **Step 3: Implement the helper**

In `science/src/science_tool/tasks.py`, add immediately after `_task_search_paths` (the helper that returns `[active.md, *sorted(done/*.md, reverse=True)]`):

```python
def known_task_ids(tasks_dir: Path) -> set[str]:
    """Every valid task id (tNNN) declared as a header in active.md and done/*.md.

    A header-only scan (not full parse): a field-level problem in one task block
    must not crash callers that only need the set of declared ids. `_HEADER_RE`
    matches only valid tNNN headers and exposes the id as group 1; check_tasks
    owns reporting malformed task blocks.
    """
    ids: set[str] = set()
    for path in _task_search_paths(tasks_dir):
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            match = _HEADER_RE.match(line)
            if match:
                ids.add(match.group(1))
    return ids
```

(`_HEADER_RE` and `_task_search_paths` are already defined in this module; `Path` is already imported.)

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science && uv run pytest tests/test_tasks_known_ids.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/tasks.py science/tests/test_tasks_known_ids.py
git commit -m "feat(tasks): add known_task_ids resolution oracle"
```

---

## Task 3: The `--fail-on` gate ladder module

**Files:**
- Create: `science/src/science_tool/validate/gates.py`
- Test: `science/tests/validate/test_gates.py`

The ladder is a stable, ordered, **cumulative** 4-tier vocabulary (umbrella design §6). A tier gates the union of its own rules plus every lower tier's rules. B1 populates Tier 1 (`ghost-files`) and the hygiene tier; `decision-bearing-orphans` (Tier 2) and `code.hardcoded-path` (hygiene) are populated by Plan B2 — the tier *names* ship now so the `--fail-on` grammar and `science.yaml code_gate` field are stable from day one.

- [ ] **Step 1: Write the failing tests**

Create `science/tests/validate/test_gates.py`:

```python
from pathlib import Path

import pytest

from science_tool.validate.gates import (
    GATE_TIERS,
    cumulative_rules,
    gated_findings,
    resolve_gate_tier,
)
from science_tool.validate.result import Result, Severity


def _r(rule: str) -> Result:
    return Result(Severity.WARN, Path("code/x.py"), None, "msg", rule, None)


def test_tier_order_is_stable() -> None:
    assert GATE_TIERS == (
        "report",
        "ghost-files",
        "decision-bearing-orphans",
        "hygiene",
    )


def test_report_tier_gates_nothing() -> None:
    assert cumulative_rules("report") == frozenset()


def test_ghost_files_tier_gates_ghost_and_malformed() -> None:
    assert cumulative_rules("ghost-files") == frozenset(
        {"code.ghost", "code.malformed-block"}
    )


def test_hygiene_tier_is_cumulative() -> None:
    rules = cumulative_rules("hygiene")
    assert {"code.ghost", "code.malformed-block"} <= rules  # includes lower tiers
    assert {"code.metadata-gap", "code.unresolved-task", "code.uncommitted"} <= rules


def test_gated_findings_filters_by_cumulative_rules() -> None:
    findings = [_r("code.ghost"), _r("code.metadata-gap"), _r("manifest")]
    assert [f.rule for f in gated_findings(findings, "ghost-files")] == ["code.ghost"]
    assert {f.rule for f in gated_findings(findings, "hygiene")} == {
        "code.ghost",
        "code.metadata-gap",
    }
    assert gated_findings(findings, "report") == []


def test_resolve_prefers_flag_over_manifest() -> None:
    assert resolve_gate_tier("ghost-files", {"code_gate": "report"}) == "ghost-files"


def test_resolve_falls_back_to_manifest_then_default() -> None:
    assert resolve_gate_tier(None, {"code_gate": "hygiene"}) == "hygiene"
    assert resolve_gate_tier(None, {}) == "report"


def test_resolve_rejects_unknown_tier() -> None:
    with pytest.raises(ValueError, match="unknown code gate tier"):
        resolve_gate_tier(None, {"code_gate": "bogus"})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science && uv run pytest tests/validate/test_gates.py -q`
Expected: FAIL — `ModuleNotFoundError: science_tool.validate.gates`.

- [ ] **Step 3: Implement the gate ladder**

Create `science/src/science_tool/validate/gates.py`:

```python
"""The staged `--fail-on` gate ladder (umbrella design §6).

`validate` is report-only by default (Tier 0). A project advances the gate
explicitly via `code_gate:` in science.yaml, or ad hoc via `--fail-on`. The
ladder is cumulative: a tier gates its own rules plus every lower tier's. The
gate operates purely on `Result.rule` at the exit-code layer, leaving the
`Result` dataclass and the JSON output contract untouched.

Tier 2 (`decision-bearing-orphans`) and the hygiene-tier `code.hardcoded-path`
rule are populated by Plan B2; their tier names ship now so the grammar is
stable.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from science_tool.validate.result import Result

# Ordered, cumulative. Index = severity of the gate; each tier adds its rules
# on top of every lower tier.
GATE_TIERS: tuple[str, ...] = (
    "report",
    "ghost-files",
    "decision-bearing-orphans",
    "hygiene",
)

# Rules introduced *at* each tier (not cumulative; see cumulative_rules()).
_TIER_RULES: dict[str, frozenset[str]] = {
    "report": frozenset(),
    "ghost-files": frozenset({"code.ghost", "code.malformed-block"}),
    "decision-bearing-orphans": frozenset(),  # Plan B2: code.orphaned-executable
    "hygiene": frozenset(
        {"code.metadata-gap", "code.unresolved-task", "code.uncommitted"}
        # Plan B2 adds: code.hardcoded-path
    ),
}


def cumulative_rules(tier: str) -> frozenset[str]:
    """All rules gated at `tier`, inclusive of every lower tier."""
    index = GATE_TIERS.index(tier)
    rules: set[str] = set()
    for name in GATE_TIERS[: index + 1]:
        rules |= _TIER_RULES[name]
    return frozenset(rules)


def gated_findings(results: Iterable[Result], tier: str) -> list[Result]:
    """The findings whose rule is gated at `tier`."""
    rules = cumulative_rules(tier)
    return [result for result in results if result.rule in rules]


def resolve_gate_tier(fail_on: str | None, manifest: Mapping[str, Any]) -> str:
    """Resolve the active gate tier: --fail-on flag > science.yaml code_gate > 'report'."""
    if fail_on is not None:
        tier = fail_on
    else:
        raw = manifest.get("code_gate")
        tier = str(raw) if raw is not None else "report"
    if tier not in GATE_TIERS:
        raise ValueError(
            f"unknown code gate tier {tier!r}; expected one of {', '.join(GATE_TIERS)}"
        )
    return tier
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && uv run pytest tests/validate/test_gates.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/validate/gates.py science/tests/validate/test_gates.py
git commit -m "feat(validate): add the --fail-on gate ladder vocabulary"
```

---

## Task 4: The code-files check — ghost & malformed detection

**Files:**
- Create: `science/src/science_tool/validate/checks/code_files.py`
- Modify: `science/src/science_tool/validate/checks/__init__.py` (add `"code_files"` to the `_load_canonical_checks` import tuple)
- Test: `science/tests/validate/test_checks_code_files.py`

The headline "no ghosts" walk. Reuse Plan A's `CodeAdapter.discover()` so the suffix set and exclude handling are defined in exactly one place. Every finding is **WARN** — never ERROR — so Tier 0 never fails `validate`. This task implements the ghost (`code.ghost`) and malformed-block (`code.malformed-block`) findings; the valid-block branch is a no-op here and is filled in by Task 5.

- [ ] **Step 1: Write the failing tests**

Create `science/tests/validate/test_checks_code_files.py`:

```python
from pathlib import Path

from science_tool.validate.checks.code_files import check_code_files
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity


def _ctx(root: Path, *, profile: str = "research", extra: str = "") -> ValidateContext:
    root.joinpath("science.yaml").write_text(
        "\n".join(
            [
                "name: demo",
                "created: 2026-01-01",
                "last_modified: 2026-01-02",
                "status: active",
                "summary: Demo project",
                f"profile: {profile}",
                "layout_version: 1",
                "knowledge_profiles:",
                "  local: knowledge/local",
                extra,
            ]
        ),
        encoding="utf-8",
    )
    return ValidateContext.from_project_root(root, strict=False, verbose=False)


def _by_rule(results: list[Result]) -> dict[str, list[Result]]:
    out: dict[str, list[Result]] = {}
    for r in results:
        out.setdefault(r.rule or "", []).append(r)
    return out


def test_no_code_dir_is_silent(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    assert list(check_code_files(ctx)) == []


def test_blockless_file_is_a_ghost(tmp_path: Path) -> None:
    (tmp_path / "code").mkdir()
    (tmp_path / "code" / "x.py").write_text("print(1)\n", encoding="utf-8")
    ctx = _ctx(tmp_path)
    by_rule = _by_rule(list(check_code_files(ctx)))
    assert len(by_rule["code.ghost"]) == 1
    ghost = by_rule["code.ghost"][0]
    assert ghost.severity is Severity.WARN
    assert ghost.path == Path("code/x.py")


def test_malformed_block_is_reported_with_error(tmp_path: Path) -> None:
    (tmp_path / "code").mkdir()
    # Unterminated block -> present but invalid.
    (tmp_path / "code" / "x.py").write_text(
        "# science:code\n# status: library\nprint(1)\n", encoding="utf-8"
    )
    ctx = _ctx(tmp_path)
    by_rule = _by_rule(list(check_code_files(ctx)))
    assert "code.ghost" not in by_rule
    assert len(by_rule["code.malformed-block"]) == 1
    msg = by_rule["code.malformed-block"][0].message
    assert "unterminated" in msg


def test_valid_block_emits_no_ghost_or_malformed(tmp_path: Path) -> None:
    (tmp_path / "code").mkdir()
    (tmp_path / "code" / "x.py").write_text(
        "# science:code\n# status: library\n# science:end\nprint(1)\n", encoding="utf-8"
    )
    ctx = _ctx(tmp_path)
    by_rule = _by_rule(list(check_code_files(ctx)))
    assert "code.ghost" not in by_rule
    assert "code.malformed-block" not in by_rule


def test_excluded_file_is_not_walked(tmp_path: Path) -> None:
    (tmp_path / "code" / "vendor").mkdir(parents=True)
    (tmp_path / "code" / "vendor" / "lib.py").write_text("print(1)\n", encoding="utf-8")
    ctx = _ctx(tmp_path, extra="code_excludes:\n  - '**/vendor/**'")
    assert list(check_code_files(ctx)) == []


def test_findings_are_never_errors(tmp_path: Path) -> None:
    (tmp_path / "code").mkdir()
    (tmp_path / "code" / "x.py").write_text("print(1)\n", encoding="utf-8")
    ctx = _ctx(tmp_path)
    assert all(r.severity is not Severity.ERROR for r in check_code_files(ctx))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science && uv run pytest tests/validate/test_checks_code_files.py -q`
Expected: FAIL — `ModuleNotFoundError: …checks.code_files`.

- [ ] **Step 3: Implement the check (ghost + malformed only)**

Create `science/src/science_tool/validate/checks/code_files.py`:

```python
"""Walk declared code roots and flag unregistered / malformed code files.

Every finding here is WARN or INFO — never ERROR — so Tier 0 (report-only, the
default) never blocks `science validate`. The `--fail-on` gate ladder
(validate/gates.py) promotes selected rules to a nonzero exit when a project
opts in. Findings travel as validation Results, never as `graph materialize`
preconditions (umbrella design §6 fragility firewall).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from science_tool.code.metadata import parse_code_metadata
from science_tool.graph.storage_adapters.code import CodeAdapter
from science_tool.paths import resolve_paths
from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity


def _result(severity: Severity, rel_path: str, message: str, rule: str) -> Result:
    return Result(severity, Path(rel_path), None, message, rule, None)


@Check(section="code files...", order=6)
def check_code_files(ctx: ValidateContext) -> Iterator[Result]:
    paths = resolve_paths(ctx.project_root)
    adapter = CodeAdapter(
        code_roots=paths.code_roots,
        repo_root=ctx.project_root,
        excludes=paths.code_excludes,
    )
    refs = adapter.discover(ctx.project_root)
    for ref in refs:
        text = (ctx.project_root / ref.path).read_text(errors="replace")
        metadata = parse_code_metadata(text)
        if not metadata.present:
            yield _result(
                Severity.WARN,
                ref.path,
                f"Code artifact has no science:code block: {ref.path}",
                "code.ghost",
            )
            continue
        if metadata.fields is None:
            yield _result(
                Severity.WARN,
                ref.path,
                f"Malformed science:code block in {ref.path}: {metadata.error}",
                "code.malformed-block",
            )
            continue
        # Valid block: per-field completeness checks are added in Task 5.
```

In `science/src/science_tool/validate/checks/__init__.py`, add `"code_files"` to the `_load_canonical_checks` import tuple, immediately after `"directory_structure"`:

```python
        "directory_structure",
        "code_files",
        "research_scope",
```

- [ ] **Step 3b: Sync the canonical-set test tuples and regenerate the formatter snapshot**

Three test modules pin a **hand-copied** mirror of the canonical module list and reload only those modules (they clear the registry first), so a new canonical check does **not** run there unless added explicitly. There is no guard asserting these tuples equal `_load_canonical_checks`, so they can legitimately diverge — and they must, because one of them is a bash-parity test.

- `science/tests/validate/test_formatter_snapshots.py` (CHECK_MODULES ~line 20) — Python-only; snapshots the full canonical **text** output against `_combined`. `code_files` is now part of the canonical set, so the snapshot must reflect it. Add `"code_files"` (anywhere in the tuple; execution order is set by `@Check` order, not tuple position):

```python
        "directory_structure",
        "code_files",
        "research_scope",
```

  Then regenerate the snapshot. There is **no** auto-update flag. Because the repo's default pytest config excludes `@pytest.mark.snapshot` tests, run `cd science && uv run pytest -m snapshot tests/validate/test_formatter_snapshots.py -q`, take the `actual` text from the failure diff, and write it to `science/tests/validate/snapshots/text_default.txt`. Only `text_default.txt` changes: it gains the `code files...` **section banner** line (sections are listed even when they emit nothing). `json_default.json` is **unchanged** — `code_files` emits no results for `_combined` (a research-profile fixture with no `code/` tree), and JSON carries results, not banners.

- `science/tests/validate/test_parity_corpus.py` (CHECK_MODULES ~line 16) — Python-only (no bash comparison; its `_combined` assertions use `>= 1` and specific messages). Safe to keep in sync; add `"code_files"` the same way. It stays silent on `_combined`.

- `science/tests/validate/test_parity_canonical_body.py` (CHECK_MODULES ~line 31) — **DO NOT add `code_files` here.** This test runs the legacy bash `validate.sh` (`subprocess.run(["/usr/bin/bash", str(VALIDATE_SH), …])`) and asserts **exact** WARN/ERROR equality between bash and Python on real projects. `code_files` is net-new with no bash counterpart; adding it would make Python emit `code.*` findings the bash side cannot, breaking semantic parity on any real project with unregistered code. Add a comment recording the intentional exclusion, immediately above the tuple:

```python
# code_files is intentionally NOT listed here: it is a net-new check with no
# counterpart in the legacy bash validate.sh, so including it would break the
# exact bash-vs-Python semantic parity this test asserts.
CHECK_MODULES = (
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && uv run pytest tests/validate/test_checks_code_files.py tests/validate/test_parity_corpus.py tests/validate/test_parity_canonical_body.py -q && uv run pytest -m snapshot tests/validate/test_formatter_snapshots.py -q`
Expected: PASS (the code-files unit tests; the regenerated text snapshot; the corpus test unchanged; bash parity still exact because `code_files` is excluded there).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/validate/checks/code_files.py science/src/science_tool/validate/checks/__init__.py science/tests/validate/test_checks_code_files.py science/tests/validate/test_formatter_snapshots.py science/tests/validate/test_parity_corpus.py science/tests/validate/test_parity_canonical_body.py science/tests/validate/snapshots/text_default.txt
git commit -m "feat(validate): walk code roots for ghost and malformed blocks"
```

---

## Task 5: The code-files check — completeness (status, task_ids, committed date)

**Files:**
- Modify: `science/src/science_tool/validate/checks/code_files.py`
- Test: `science/tests/validate/test_checks_code_files.py` (add cases)

Fill in the valid-block branch with the three hygiene-tier findings: `code.metadata-gap` (missing or out-of-vocabulary `status`), `code.unresolved-task` (a `task_ids` entry that resolves to no real task), and `code.uncommitted` (a valid block whose file has no committed content date — commit-only freshness would silently drop it).

- [ ] **Step 1: Write the failing tests**

Add to `science/tests/validate/test_checks_code_files.py` (the `_ctx`/`_by_rule` helpers exist from Task 4; add `import os`, `import subprocess`, and a `_git` helper at the top):

```python
import os
import subprocess


def _git(repo: Path, *args: str, env: dict | None = None) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True, env=env)


def _commit_all(repo: Path) -> None:
    _git(repo, "init")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Tester")
    _git(repo, "add", "-A")
    env = {**os.environ, "GIT_COMMITTER_DATE": "2026-04-01T00:00:00", "GIT_AUTHOR_DATE": "2026-04-01T00:00:00"}
    _git(repo, "commit", "-m", "init", env=env)


def test_missing_status_is_metadata_gap(tmp_path: Path) -> None:
    (tmp_path / "code").mkdir()
    (tmp_path / "code" / "x.py").write_text(
        "# science:code\n# task_ids: []\n# science:end\nprint(1)\n", encoding="utf-8"
    )
    ctx = _ctx(tmp_path)
    _commit_all(tmp_path)
    by_rule = _by_rule(list(check_code_files(ctx)))
    assert len(by_rule["code.metadata-gap"]) == 1
    assert "missing required `status`" in by_rule["code.metadata-gap"][0].message


def test_invalid_status_is_metadata_gap(tmp_path: Path) -> None:
    (tmp_path / "code").mkdir()
    (tmp_path / "code" / "x.py").write_text(
        "# science:code\n# status: bogus\n# science:end\nprint(1)\n", encoding="utf-8"
    )
    ctx = _ctx(tmp_path)
    _commit_all(tmp_path)
    by_rule = _by_rule(list(check_code_files(ctx)))
    assert len(by_rule["code.metadata-gap"]) == 1
    assert "'bogus'" in by_rule["code.metadata-gap"][0].message


def test_unknown_task_id_is_unresolved(tmp_path: Path) -> None:
    (tmp_path / "code").mkdir()
    (tmp_path / "code" / "x.py").write_text(
        "# science:code\n# status: workflow-owned\n# task_ids: [t999]\n# science:end\nprint(1)\n",
        encoding="utf-8",
    )
    ctx = _ctx(tmp_path)
    _commit_all(tmp_path)
    by_rule = _by_rule(list(check_code_files(ctx)))
    assert len(by_rule["code.unresolved-task"]) == 1
    assert "t999" in by_rule["code.unresolved-task"][0].message


def test_non_list_task_ids_is_metadata_gap(tmp_path: Path) -> None:
    # `task_ids: t999` parses to a scalar string, not a list — must not be
    # silently ignored.
    (tmp_path / "code").mkdir()
    (tmp_path / "code" / "x.py").write_text(
        "# science:code\n# status: workflow-owned\n# task_ids: t999\n# science:end\nprint(1)\n",
        encoding="utf-8",
    )
    ctx = _ctx(tmp_path)
    _commit_all(tmp_path)
    by_rule = _by_rule(list(check_code_files(ctx)))
    assert len(by_rule["code.metadata-gap"]) == 1
    assert "task_ids" in by_rule["code.metadata-gap"][0].message
    assert "code.unresolved-task" not in by_rule


def test_resolved_task_id_is_silent(tmp_path: Path) -> None:
    (tmp_path / "code").mkdir()
    (tmp_path / "tasks").mkdir()
    (tmp_path / "tasks" / "active.md").write_text(
        "## [t491] Real task\n- created: 2026-01-01\n", encoding="utf-8"
    )
    (tmp_path / "code" / "x.py").write_text(
        "# science:code\n# status: workflow-owned\n# task_ids: [t491]\n# science:end\nprint(1)\n",
        encoding="utf-8",
    )
    ctx = _ctx(tmp_path)
    _commit_all(tmp_path)
    assert "code.unresolved-task" not in _by_rule(list(check_code_files(ctx)))


def test_uncommitted_valid_block_is_flagged(tmp_path: Path) -> None:
    # No git repo at all -> last_content_change_date returns None.
    (tmp_path / "code").mkdir()
    (tmp_path / "code" / "x.py").write_text(
        "# science:code\n# status: workflow-owned\n# science:end\nprint(1)\n", encoding="utf-8"
    )
    ctx = _ctx(tmp_path)
    by_rule = _by_rule(list(check_code_files(ctx)))
    assert len(by_rule["code.uncommitted"]) == 1


def test_committed_valid_block_has_no_uncommitted_finding(tmp_path: Path) -> None:
    (tmp_path / "code").mkdir()
    (tmp_path / "code" / "x.py").write_text(
        "# science:code\n# status: workflow-owned\n# science:end\nprint(1)\n", encoding="utf-8"
    )
    ctx = _ctx(tmp_path)
    _commit_all(tmp_path)
    assert "code.uncommitted" not in _by_rule(list(check_code_files(ctx)))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science && uv run pytest tests/validate/test_checks_code_files.py -k "metadata_gap or unresolved or uncommitted or resolved_task" -q`
Expected: FAIL — the valid-block branch is currently a no-op, so none of these findings appear.

- [ ] **Step 3: Implement the completeness checks**

In `science/src/science_tool/validate/checks/code_files.py`, add the new imports below the existing ones:

```python
from science_tool.code.git import last_content_change_date
from science_tool.code.lifecycle import CODE_FILE_STATUSES
from science_tool.tasks import known_task_ids
```

Replace the no-op valid-block comment at the end of `check_code_files` so the loop body becomes:

```python
        if not metadata.present:
            yield _result(
                Severity.WARN,
                ref.path,
                f"Code artifact has no science:code block: {ref.path}",
                "code.ghost",
            )
            continue
        if metadata.fields is None:
            yield _result(
                Severity.WARN,
                ref.path,
                f"Malformed science:code block in {ref.path}: {metadata.error}",
                "code.malformed-block",
            )
            continue
        yield from _check_valid_block(ctx, ref.path, metadata.fields, task_ids)
```

Resolve `task_ids` once, before the loop (right after `refs = adapter.discover(...)`):

```python
    if not refs:
        return
    task_ids = known_task_ids(paths.tasks_dir)
```

Add the helper at the end of the module:

```python
def _check_valid_block(
    ctx: ValidateContext,
    rel_path: str,
    fields: dict[str, object],
    task_ids: set[str],
) -> Iterator[Result]:
    status = str(fields.get("status") or "")
    if status not in CODE_FILE_STATUSES:
        expected = ", ".join(sorted(CODE_FILE_STATUSES))
        message = (
            f"Code-file block has invalid status {status!r}; expected one of {expected}"
            if status
            else f"Code-file block missing required `status` field (expected one of {expected})"
        )
        yield _result(Severity.WARN, rel_path, message, "code.metadata-gap")

    raw_task_ids = fields.get("task_ids")
    if isinstance(raw_task_ids, list):
        for entry in raw_task_ids:
            task_id = str(entry)
            if task_id not in task_ids:
                yield _result(
                    Severity.WARN,
                    rel_path,
                    f"Code-file references unknown task id {task_id!r} (no such task in tasks/)",
                    "code.unresolved-task",
                )
    elif raw_task_ids is not None:
        # Present but not a list (e.g. `task_ids: t999` -> a scalar string):
        # a malformed field, not "no tasks". Flag it rather than silently drop it.
        yield _result(
            Severity.WARN,
            rel_path,
            f"Code-file `task_ids` must be a list, got {type(raw_task_ids).__name__}",
            "code.metadata-gap",
        )

    if last_content_change_date(rel_path, repo_root=ctx.project_root) is None:
        yield _result(
            Severity.WARN,
            rel_path,
            (
                f"Code-file has a valid block but no committed content date "
                f"(untracked or never committed); freshness will not see it: {rel_path}"
            ),
            "code.uncommitted",
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && uv run pytest tests/validate/test_checks_code_files.py -q`
Expected: PASS (Task 4 cases plus the new completeness cases).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/validate/checks/code_files.py science/tests/validate/test_checks_code_files.py
git commit -m "feat(validate): flag code-file status gaps, unresolved tasks, and uncommitted files"
```

---

## Task 6: Wire the gate into the runner and the CLI

**Files:**
- Modify: `science/src/science_tool/validate/runner.py` (`RunResult` ~lines 30-35; `run` ~lines 72-115)
- Modify: `science/src/science_tool/validate/cli.py` (options; `validate_cmd`; `_format_summary`)
- Test: `science/tests/validate/test_validate_cli.py` (add cases)

Thread the resolved gate tier through `run` and into the exit code. `RunResult` gains two fields with defaults (`gate_tier`, `gated`) that `_json_payload` does **not** read, so the strict JSON schema (`additionalProperties: false`) is preserved. The CLI gains a `--fail-on` `click.Choice(GATE_TIERS)` option (click validates it), exits 1 when there are gated findings, and the text summary names the gate failure. With no gate active (the default), behavior is byte-for-byte unchanged.

- [ ] **Step 1: Write the failing tests**

Add to `science/tests/validate/test_validate_cli.py`:

```python
def test_fail_on_ghost_files_exits_nonzero(tmp_path: Path) -> None:
    @Check(section="demo", order=10)
    def demo_check(ctx: ValidateContext) -> list[Result]:
        return [Result(Severity.WARN, Path("code/x.py"), None, "ghost", "code.ghost", None)]

    result = CliRunner().invoke(
        main,
        ["validate", "--fail-on", "ghost-files", "--project-root", str(_project(tmp_path))],
    )
    assert result.exit_code == 1, result.output
    assert "gated at tier 'ghost-files'" in result.output


def test_fail_on_does_not_change_json_payload(tmp_path: Path) -> None:
    @Check(section="demo", order=10)
    def demo_check(ctx: ValidateContext) -> list[Result]:
        return [Result(Severity.WARN, Path("code/x.py"), None, "ghost", "code.ghost", None)]

    result = CliRunner().invoke(
        main,
        ["validate", "--fail-on", "ghost-files", "--format", "json", "--project-root", str(_project(tmp_path))],
    )
    assert result.exit_code == 1, result.output
    payload = json.loads(result.output)
    # Same two-key shape as the contract; gate decision is NOT serialized.
    assert set(payload.keys()) == {"summary", "results"}
    assert payload["summary"] == {"errors": 0, "warnings": 1, "infos": 0}


def test_default_gate_is_report_and_does_not_fail_on_ghost(tmp_path: Path) -> None:
    @Check(section="demo", order=10)
    def demo_check(ctx: ValidateContext) -> list[Result]:
        return [Result(Severity.WARN, Path("code/x.py"), None, "ghost", "code.ghost", None)]

    result = CliRunner().invoke(main, ["validate", "--project-root", str(_project(tmp_path))])
    assert result.exit_code == 0, result.output


def test_code_gate_in_manifest_is_honored(tmp_path: Path) -> None:
    project = tmp_path
    (project / "science.yaml").write_text("name: demo\ncode_gate: ghost-files\n", encoding="utf-8")

    @Check(section="demo", order=10)
    def demo_check(ctx: ValidateContext) -> list[Result]:
        return [Result(Severity.WARN, Path("code/x.py"), None, "ghost", "code.ghost", None)]

    result = CliRunner().invoke(main, ["validate", "--project-root", str(project)])
    assert result.exit_code == 1, result.output


def test_unknown_code_gate_in_manifest_is_clean_error(tmp_path: Path) -> None:
    project = tmp_path
    (project / "science.yaml").write_text("name: demo\ncode_gate: bogus\n", encoding="utf-8")

    result = CliRunner().invoke(main, ["validate", "--project-root", str(project)])
    assert result.exit_code != 0
    assert "unknown code gate tier" in result.output


def test_fail_on_rejects_unknown_tier_value() -> None:
    result = CliRunner().invoke(main, ["validate", "--fail-on", "bogus"])
    assert result.exit_code != 0
    assert "Invalid value for '--fail-on'" in result.output
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science && uv run pytest tests/validate/test_validate_cli.py -k "fail_on or code_gate or default_gate" -q`
Expected: FAIL — `run` has no `fail_on` kwarg / `--fail-on` is not a known option.

- [ ] **Step 3a: Extend `RunResult` and `run`**

In `science/src/science_tool/validate/runner.py`, change the `dataclasses` import and `RunResult`, and resolve the gate inside `run`.

Update the import line:

```python
from dataclasses import dataclass, replace
```

Replace the `RunResult` definition:

```python
@dataclass(frozen=True)
class RunResult:
    results: list[Result]
    errors: int
    warnings: int
    infos: int
    gate_tier: str = "report"
    gated: tuple[Result, ...] = ()
```

Add the gate import near the other validate imports:

```python
from science_tool.validate.context import ValidateContext, ValidateContextError
from science_tool.validate.gates import gated_findings, resolve_gate_tier
```

(`ValidateContext` is already imported; add `ValidateContextError` to that line and add the `gates` import.)

Change the `run` signature to accept `fail_on`:

```python
def run(
    project_root: Path,
    *,
    strict: bool,
    verbose: bool,
    fail_on: str | None = None,
    enable_python_sidecar: bool = True,
) -> RunResult:
```

In `run`, replace the `run_result = _tally(results)` / `return run_result` lines inside the `try` with gate resolution and attachment:

```python
        run_result = _tally(results)
        try:
            tier = resolve_gate_tier(fail_on, ctx.manifest)
        except ValueError as exc:
            raise ValidateContextError(str(exc)) from exc
        run_result = replace(run_result, gate_tier=tier, gated=tuple(gated_findings(results, tier)))
        return run_result
```

(`--fail-on` values are validated by `click.Choice` before `run` is reached, so only an invalid `code_gate:` in the manifest can raise here — surfaced as the existing clean `ValidateContextError` the CLI already renders.)

- [ ] **Step 3b: Add the `--fail-on` option and gate-aware exit/summary**

In `science/src/science_tool/validate/cli.py`, add the gate import:

```python
from science_tool.validate.gates import GATE_TIERS
from science_tool.validate.runner import RunResult, run
```

Add the option (after `--strict`):

```python
@click.option(
    "--fail-on",
    "fail_on",
    type=click.Choice(list(GATE_TIERS)),
    default=None,
    help="Exit nonzero when a finding gated at this tier (or below) is present. "
    "Overrides science.yaml code_gate. Default: report (never blocks).",
)
```

Add `fail_on: str | None` to the `validate_cmd` signature and pass it through:

```python
def validate_cmd(
    ctx: click.Context,
    verbose: bool,
    strict: bool,
    output_format: str,
    project_root: Path,
    fail_on: str | None,
) -> None:
    """Validate a Science project."""
    captured_stdout = StringIO()
    try:
        with redirect_stdout(captured_stdout):
            result = run(
                project_root,
                strict=strict,
                verbose=verbose,
                fail_on=fail_on,
            )
    except ValidateContextError as exc:
        raise click.ClickException(str(exc)) from exc
```

Change the exit condition at the end of `validate_cmd`:

```python
    if result.errors or result.gated:
        ctx.exit(1)
```

Update `_format_summary` to report a gate failure (preserving the existing error/warning/clean branches exactly):

```python
def _format_summary(result: RunResult) -> Text:
    if result.errors:
        status = f"FAILED: {result.errors} error(s), {result.warnings} warning(s)"
        style = ERROR_STYLE
    elif result.gated:
        status = (
            f"FAILED: {len(result.gated)} finding(s) gated at tier "
            f"'{result.gate_tier}', {result.warnings} warning(s)"
        )
        style = ERROR_STYLE
    elif result.warnings:
        status = f"PASSED with {result.warnings} warning(s)"
        style = WARNING_STYLE
    else:
        status = "PASSED: all checks clean"
        style = SUCCESS_STYLE

    text = Text(style=style)
    text.append(status)
    return text
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && uv run pytest tests/validate/test_validate_cli.py -q`
Expected: PASS — the new gate cases plus every existing CLI test (the default-gate path is unchanged, so the JSON/text contract tests still pass).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/validate/runner.py science/src/science_tool/validate/cli.py science/tests/validate/test_validate_cli.py
git commit -m "feat(validate): add --fail-on gate ladder to the validate CLI"
```

---

## Task 7: Documentation + full-suite regression

**Files:**
- Modify: `docs/conventions/validate.md`
- Test: the `science_tool` suite

- [ ] **Step 1: Update the existing sections that gating now contradicts**

`docs/conventions/validate.md` currently states, in four places, that warnings never fail and lists no `--fail-on`. Gated warnings make those statements false unless updated — do **not** only append. Make these edits (match the file's heading depth and tone):

**Synopsis** (~line 9) — add `--fail-on` to the usage line:

```bash
science validate [--verbose] [--strict] [--format text|json] [--fail-on TIER] [--project-root PATH]
```

**Flags** (~line 22) — add a row to the table:

```
| `--fail-on TIER` | Exit `1` when any finding gated at `TIER` (or a lower tier) is present. Tiers: `report` (default, never blocks), `ghost-files`, `decision-bearing-orphans`, `hygiene`. Overrides `code_gate` in `science.yaml`. |
```

**Exit Codes** (~line 34) — replace the "Warnings alone do not fail" sentence with a gate-aware version:

> Validation exits `0` when there are no `error` results **and** no findings are gated by the active `--fail-on` tier (or `code_gate` in `science.yaml`). Warnings alone do not fail the command — including warnings under `--strict` — **unless** their rule is gated. It exits `1` when one or more `error` results are present, or when a gated finding is present. Invocation errors use Click's normal non-zero behavior; an unknown gate tier in `code_gate` is reported as a clean error.

**Severity Model** (~line 42) — amend the `warn` row's exit impact:

```
| `warn` | A non-blocking issue that should be reviewed. | Does not fail the command — unless its rule is gated by `--fail-on`/`code_gate`. |
```

- [ ] **Step 2: Add the code-file registration section**

Add a new `## Code-file registration & the `--fail-on` gate ladder` section. Cover, in prose:

- The code-files check walks every `code_roots` declaration (resolved from `science.yaml`; defaults to the profile code dir), parsing each file's `# science:code … # science:end` block.
- The `code.*` rules and what each means:
  - `code.ghost` — an in-scope code file with no block.
  - `code.malformed-block` — a block that is present but unterminated, non-mapping, or invalid YAML.
  - `code.metadata-gap` — a valid block whose `status` is missing or not one of `exploratory`, `workflow-owned`, `library`, `retired`, or whose `task_ids` is present but not a list.
  - `code.unresolved-task` — a `task_ids` entry that resolves to no task in `tasks/`.
  - `code.uncommitted` — a valid block whose file has no committed content date (untracked/never committed), so commit-only freshness would not see it.
- Every code-file finding is WARN — `validate` is **report-only by default**; only an active gate makes them fail.
- The `--fail-on` ladder and the `code_gate:` `science.yaml` field: the ordered, cumulative tiers `report` → `ghost-files` → `decision-bearing-orphans` → `hygiene`; `--fail-on` overrides `code_gate`.
- A forward note: `decision-bearing-orphans` and `code.hardcoded-path` (the orphan and hardcoded-path detectors) arrive in Plan B2; their tier names ship now so the grammar is stable.

Use `~/d/` (not absolute) for any in-repo path references, per repo doc conventions.

- [ ] **Step 3: Run the full tool suite**

Run: `cd science && uv run pytest -q`
Expected: PASS. The new `code_files` check is canonical (Task 4), so it runs wherever the **full runner / full registry** runs. The pinned-tuple tests were already reconciled in Task 4 Step 3b; this run confirms nothing else regressed:
- `tests/validate/test_validate_cli.py` and the order-assertion tests (`test_checks_papers_gap_analysis.py`, `test_checks_research_documents.py`, `test_checks_prose_lints.py`, …) clear the registry and reload only a **subset**, so `code_files` (at `order=6`) neither runs nor shifts their relative-position assertions.
- `tests/validate/test_parity_canonical_body.py` excludes `code_files` (Task 4 Step 3b), so bash-vs-Python parity stays exact.
- Watch any remaining test that runs `run(...)` against a fixture **containing real `.py`/`.R`/`.sh`/`.smk` files with no `# science:code` block** — it would gain `code.ghost` (WARN) findings. Remediate by giving the fixture no code root or updating expected counts; do **not** weaken the check. All findings are WARN, so no exit flips to 1 on the default report tier.
- `tests/validate/test_checks_basic.py` calls individual check functions directly (not the runner), so `code_files` does not run there unless explicitly invoked.

- [ ] **Step 4: Run the model suite (sanity — untouched, must stay green)**

Run: `cd science/model && uv run pytest -q`
Expected: PASS (this plan does not touch `science-model`).

- [ ] **Step 5: Commit**

```bash
git add docs/conventions/validate.md
git commit -m "docs(validate): document code-file checks and the --fail-on gate ladder"
```

---

## What B1 deliberately leaves to Plan B2

- **Classification** (workflow-owned / orphaned / library / test / package-marker), generalizing MM30's `classify_script`: `__init__.py` → package-marker; `tests/` or `test_*` → test; executable-and-workflow-referenced → workflow-owned; executable-and-unreferenced → orphaned; imported-only → library. Executable detection generalizes MM30's `_is_executable_script` (`.R`/`.r`/`.sh` always; Python with `if __name__ == "__main__"`, `@click.command`, `argparse.ArgumentParser`, or `snakemake`).
- **The Snakemake reference parser** (MM30's "hard-won" `find_workflow_references`): the cross-file symbol table built by fixpoint iteration (`PATH_ASSIGN_RE` / `JOIN_ASSIGN_RE`), rule-block splitting (`RULE_RE`), literal and `{SYMBOL}`-indirected script detection, and wildcard-glob expansion. This is what tells the classifier which files are workflow-referenced — a *static* reference scan, distinct from Plan C's materialized `implements`/`executes` graph edges.
- **Tier 2 — decision-bearing orphans** (`code.orphaned-executable`): an executable, decision-bearing code file not referenced by any workflow. Fail-closed: an un-annotated executable is treated as decision-bearing until downgraded. Plugs into the gate ladder by populating `_TIER_RULES["decision-bearing-orphans"]`.
- **Tier 3 — hardcoded paths** (`code.hardcoded-path`): generalizing MM30's `find_hardcoded_paths` (absolute-path prefixes, `Path("scripts/.../output")` heuristic). Plugs in by adding `code.hardcoded-path` to `_TIER_RULES["hygiene"]`.

B1 ships the stable gate-tier vocabulary and the report-only default, so B2 is purely additive: new rules slot into the existing `_TIER_RULES` map, and new findings flow through the same runner/CLI exit path with no further API change.

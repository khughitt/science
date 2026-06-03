# Entity Organization & Naming — Implementation Plan 2: Validation, Legacy Repointing, Reservation & Templates

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Design:** `docs/plans/2026-06-03-entity-organization-and-naming-design.md`
**Predecessor:** `docs/plans/2026-06-03-entity-organization-and-naming-implementation.md` (Plan 1 — foundation). Plan 2 assumes Plan 1 has landed: the policy table is SSOT, ids are width-4 numeric (citekey for papers), `synthesis` is a core kind, and `entities/` is discovered additively.

**Goal:** Add the five entity-conformance health checks, repoint the legacy semantic checks at `entities/`, derive `id_prefixes` from the policy table, warn when a project is not yet `layout_version: 3`, generalize atomic id reservation to all numeric kinds, and bring the new kinds' domain templates into the `_template` format.

**Architecture:** A single new check module `entity_conformance.py` owns the five new checks (they share one pass over the policy table + `entities/`). Legacy checks gain `entities/`-first lookup (keeping a `doc/`/`specs/` fallback — the no-fallback cutover is Plan 3). `id_prefixes.PREFIX_RULES` becomes a function over the policy table so the two lists cannot drift. Reservation is lifted out of `questions.py` into a kind-agnostic `reserve_entity`. Templates are audited and migrated to the `_template` metadata format with the new numeric local-part placeholder.

**Tech Stack:** Python 3.13, pytest, Click, pydantic, PyYAML. Tests run from `science/`: `cd science && uv run pytest`.

**Severity policy:** Every new check in this plan emits **WARN** (or INFO), never ERROR. The WARN→ERROR promotion and `layout_version: 3` enforcement happen at cutover in Plan 3.

---

## File structure

| File | Responsibility | Change |
|---|---|---|
| `science/src/science_tool/entities.py` | Public policy accessors (`markdown_entity_kinds`, `local_part_conforms`) | Modify |
| `science/src/science_tool/validate/checks/entity_conformance.py` | The 5 new checks | Create |
| `science/src/science_tool/validate/checks/__init__.py` | Register the new module | Modify |
| `science/src/science_tool/validate/checks/id_prefixes.py` | `PREFIX_RULES` derived from policy table | Modify |
| `science/src/science_tool/validate/checks/hypotheses.py` | Repoint `entities/hypotheses/`, drop `h*` glob | Modify |
| `science/src/science_tool/validate/checks/discussions.py` | Repoint `entities/discussions/`, `entities/synthesis/` | Modify |
| `science/src/science_tool/validate/checks/document_structure.py` | Repoint `entities/topics/`, `entities/papers/` | Modify |
| `science/src/science_tool/validate/checks/papers.py` | Repoint messaging to `entities/papers/` | Modify |
| `science/src/science_tool/validate/checks/manifest.py` | Warn when `layout_version < 3` | Modify |
| `science/src/science_tool/entity_reservation.py` | Kind-agnostic `reserve_entity` | Create |
| `science/src/science_tool/questions.py` | Delegate `reserve_question` to `reserve_entity` | Modify |
| `science/model/src/science_model/templates/*.md` | New-kind templates in `_template` format | Modify |
| `science/model/src/science_model/templates.py` | Extend `MIGRATED_KINDS` | Modify |

---

## Task 1: Public policy accessors

**Files:**
- Modify: `science/src/science_tool/entities.py`
- Test: `science/tests/test_entity_policy.py` (extend)

- [ ] **Step 1: Write the failing test**

Append to `science/tests/test_entity_policy.py`:

```python
from science_tool.entities import (
    is_markdown_entity_kind,
    local_part_conforms,
    markdown_entity_kinds,
)


def test_markdown_entity_kinds_includes_synthesis_excludes_task() -> None:
    kinds = markdown_entity_kinds()
    assert "synthesis" in kinds and "question" in kinds
    assert "task" not in kinds and "dataset" not in kinds
    assert is_markdown_entity_kind("hypothesis")
    assert not is_markdown_entity_kind("task")


def test_local_part_conforms_by_strategy() -> None:
    assert local_part_conforms("question", "0005-granularity")
    assert not local_part_conforms("question", "q05-granularity")
    assert not local_part_conforms("question", "5-granularity")
    assert local_part_conforms("paper", "Adams2025")
    assert not local_part_conforms("paper", "0001-not-a-citekey?")
```

- [ ] **Step 2: Run to verify failure**

Run: `cd science && uv run pytest tests/test_entity_policy.py -k "markdown_entity_kinds or local_part_conforms" -v`
Expected: FAIL — names not defined.

- [ ] **Step 3: Add the accessors**

In `science/src/science_tool/entities.py`, after `resolve_path_policy`:

```python
def markdown_entity_kinds() -> tuple[str, ...]:
    """All kinds the policy table governs (markdown entity kinds)."""
    return tuple(_BUILTIN_MARKDOWN_POLICIES)


def is_markdown_entity_kind(kind: str) -> bool:
    return kind in _BUILTIN_MARKDOWN_POLICIES


def local_part_conforms(kind: str, local_part: str) -> bool:
    """True iff ``local_part`` matches the kind's filename strategy."""
    strategy = resolve_path_policy(kind).strategy
    if strategy == "numeric":
        return bool(_NUMERIC_LOCAL_PART_RE.fullmatch(local_part))
    if strategy == "citekey":
        return bool(_CITEKEY_RE.fullmatch(local_part))
    return False  # singletons have no per-instance local part
```

- [ ] **Step 4: Run to verify pass**

Run: `cd science && uv run pytest tests/test_entity_policy.py -k "markdown_entity_kinds or local_part_conforms" -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/entities.py science/tests/test_entity_policy.py
git commit -m "feat(entities): public policy accessors for validation checks"
```

---

## Task 2: Entity-conformance check module — location & filename

**Files:**
- Create: `science/src/science_tool/validate/checks/entity_conformance.py`
- Modify: `science/src/science_tool/validate/checks/__init__.py` (register module)
- Test: `science/tests/validate/test_checks_entity_conformance.py` (create)

- [ ] **Step 1: Write the failing test**

Create `science/tests/validate/test_checks_entity_conformance.py`:

```python
from __future__ import annotations

from pathlib import Path

import yaml

from science_tool.validate.checks.entity_conformance import (
    check_entity_filename_conformance,
    check_entity_location_coherence,
)
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Severity


def _ctx(tmp_path: Path) -> ValidateContext:
    (tmp_path / "science.yaml").write_text(
        "name: t\nlayout_version: 3\nprofile: research\nknowledge_profiles: {local: local}\n",
        encoding="utf-8",
    )
    return ValidateContext.from_project_root(tmp_path, strict=False, verbose=False)


def _write(root: Path, rel: str, fm: dict) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("---\n" + yaml.safe_dump(fm) + "---\n", encoding="utf-8")


def test_location_coherence_flags_stranded_entity(tmp_path: Path) -> None:
    _write(tmp_path, "doc/questions/0001-x.md", {"id": "question:0001-x", "type": "question"})
    ctx = _ctx(tmp_path)
    results = list(check_entity_location_coherence(ctx))
    assert any(r.severity is Severity.WARN and "doc/questions/0001-x.md" in str(r.path) for r in results)


def test_location_coherence_passes_for_correct_home(tmp_path: Path) -> None:
    _write(tmp_path, "entities/questions/0001-x.md", {"id": "question:0001-x", "type": "question", "title": "X", "status": "active", "created": "2026-01-01", "updated": "2026-01-01"})
    ctx = _ctx(tmp_path)
    assert not [r for r in check_entity_location_coherence(ctx) if r.severity is Severity.WARN]


def test_location_coherence_flags_type_in_wrong_dir(tmp_path: Path) -> None:
    # a hypothesis-typed file living under entities/questions/
    _write(tmp_path, "entities/questions/0001-x.md", {"id": "hypothesis:0001-x", "type": "hypothesis"})
    ctx = _ctx(tmp_path)
    results = list(check_entity_location_coherence(ctx))
    assert any(r.severity is Severity.WARN and "type" in r.message for r in results)


def test_filename_conformance_flags_legacy_name(tmp_path: Path) -> None:
    _write(tmp_path, "entities/questions/q01-x.md", {"id": "question:q01-x", "type": "question"})
    ctx = _ctx(tmp_path)
    results = list(check_entity_filename_conformance(ctx))
    assert any(r.severity is Severity.WARN for r in results)


def test_filename_conformance_flags_stem_id_mismatch(tmp_path: Path) -> None:
    # well-formed name, but id local-part does not match the filename stem
    _write(tmp_path, "entities/questions/0001-x.md", {"id": "question:0002-y", "type": "question"})
    ctx = _ctx(tmp_path)
    results = list(check_entity_filename_conformance(ctx))
    assert any(r.severity is Severity.WARN and "id" in r.message for r in results)


def test_filename_conformance_passes_for_padded(tmp_path: Path) -> None:
    _write(tmp_path, "entities/questions/0001-x.md", {"id": "question:0001-x", "type": "question"})
    ctx = _ctx(tmp_path)
    assert not [r for r in check_entity_filename_conformance(ctx) if r.severity is Severity.WARN]
```

- [ ] **Step 2: Run to verify failure**

Run: `cd science && uv run pytest tests/validate/test_checks_entity_conformance.py -v`
Expected: FAIL — module does not exist.

- [ ] **Step 3: Create the module with the first two checks**

Create `science/src/science_tool/validate/checks/entity_conformance.py`:

```python
"""Entity-conformance health checks driven by the policy table.

All checks emit WARN during the transition (layout_version 2→3). The
WARN→ERROR promotion is Plan 3 (cutover).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
import re

import yaml

from science_tool.entities import (
    is_markdown_entity_kind,
    local_part_conforms,
    markdown_entity_kinds,
    resolve_path_policy,
)
from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity

_FRONTMATTER = re.compile(r"^---\n(.*?)\n---", re.DOTALL)
_LEGACY_ROOTS = ("doc", "specs")


def _result(severity: Severity, path: Path | None, message: str) -> Result:
    return Result(severity, path, None, message, "entity-conformance", None)


def _frontmatter_dict(ctx: ValidateContext, path: Path) -> dict:
    match = _FRONTMATTER.match(ctx.read_text_cached(path))
    if match is None:
        return {}
    try:
        data = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        return {}
    return data if isinstance(data, dict) else {}


def _entity_type(ctx: ValidateContext, path: Path) -> str | None:
    data = _frontmatter_dict(ctx, path)
    value = data.get("type") or data.get("kind")
    return str(value) if value else None


def _id_kind_and_local(entity_id: object) -> tuple[str | None, str | None]:
    if isinstance(entity_id, str) and ":" in entity_id:
        kind, local = entity_id.split(":", 1)
        return kind, local
    return None, None


def _rel(ctx: ValidateContext, path: Path) -> Path:
    return path.relative_to(ctx.project_root)


@Check(section="entity location coherence...", order=20)
def check_entity_location_coherence(ctx: ValidateContext) -> Iterator[Result]:
    """(a) Flag entity files stranded in doc/specs; (b) flag files under
    entities/<kind>/ whose frontmatter type or id-kind disagrees with the
    directory (directory/type/id coherence)."""
    # (a) stranded in legacy roots
    for root_name in _LEGACY_ROOTS:
        root = ctx.project_root / root_name
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.md")):
            if "templates" in path.relative_to(ctx.project_root).parts:
                continue
            kind = _entity_type(ctx, path)
            if kind is None or not is_markdown_entity_kind(kind):
                continue  # prose / non-entity markdown is ignored
            yield _result(
                _severity(ctx),
                _rel(ctx, path),
                f"{kind} entity outside its home; expected under {resolve_path_policy(kind).root}/",
            )
    # (b) miscategorized within entities/<kind>/
    for kind in markdown_entity_kinds():
        policy = resolve_path_policy(kind)
        if policy.strategy == "singleton":
            continue
        directory = ctx.project_root / policy.root
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.md")):
            data = _frontmatter_dict(ctx, path)
            ftype = data.get("type") or data.get("kind")
            if ftype and str(ftype) != kind:
                yield _result(_severity(ctx), _rel(ctx, path), f"type {ftype!r} in {kind}/ directory (expected {kind})")
            id_kind, _ = _id_kind_and_local(data.get("id"))
            if id_kind is not None and id_kind != kind:
                yield _result(_severity(ctx), _rel(ctx, path), f"id kind {id_kind!r} in {kind}/ directory (expected {kind})")


@Check(section="entity filename conformance...", order=21)
def check_entity_filename_conformance(ctx: ValidateContext) -> Iterator[Result]:
    """Flag files in entities/<kind>/ whose name violates the kind's strategy
    OR whose stem != the id's local-part."""
    for kind in markdown_entity_kinds():
        policy = resolve_path_policy(kind)
        if policy.strategy == "singleton":
            continue
        directory = ctx.project_root / policy.root
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.md")):
            if not local_part_conforms(kind, path.stem):
                yield _result(
                    _severity(ctx), _rel(ctx, path), f"non-conforming {kind} filename {path.name!r} (strategy={policy.strategy})"
                )
            _, id_local = _id_kind_and_local(_frontmatter_dict(ctx, path).get("id"))
            if id_local is not None and id_local != path.stem:
                yield _result(
                    _severity(ctx), _rel(ctx, path), f"filename stem {path.stem!r} != id local-part {id_local!r}"
                )


def _severity(ctx: ValidateContext) -> Severity:
    # Plan 2 emits WARN; Plan 3 cutover swaps the body for a layout_version gate
    # (ERROR when layout_version >= 3). Single-spot change.
    del ctx
    return Severity.WARN
```

> Plan 2 keeps `_severity(ctx)` returning `Severity.WARN`. Plan 3's cutover replaces the
> body with the `layout_version`-gated severity (see Plan 3, Task 9 Step 5), so the
> WARN→ERROR promotion is a single-function change that lifts **every** conformance
> yield — including the stranded-file branch. A markdown *entity* found in `doc/`/
> `specs/` under v3 is a real invariant violation (ERROR); prose markdown is
> already skipped by the `is_markdown_entity_kind` guard, so prose-only `doc/` is
> unaffected. **All five checks route through `_severity(ctx)` — no bare
> `Severity.WARN` remains in this module** (see Task 3).

- [ ] **Step 4: Register the module**

In `science/src/science_tool/validate/checks/__init__.py`, add `"entity_conformance"` to the `CANONICAL_CHECK_MODULES` tuple (after `"id_prefixes"`).

- [ ] **Step 5: Run to verify pass**

Run: `cd science && uv run pytest tests/validate/test_checks_entity_conformance.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/validate/checks/entity_conformance.py science/src/science_tool/validate/checks/__init__.py science/tests/validate/test_checks_entity_conformance.py
git commit -m "feat(validate): entity location + filename conformance checks (WARN)"
```

---

## Task 3: Entity-conformance — frontmatter, number hygiene, stray files

**Files:**
- Modify: `science/src/science_tool/validate/checks/entity_conformance.py`
- Test: `science/tests/validate/test_checks_entity_conformance.py` (extend)

- [ ] **Step 1: Write the failing tests**

Append to `science/tests/validate/test_checks_entity_conformance.py`:

```python
from science_tool.validate.checks.entity_conformance import (
    check_entity_frontmatter_completeness,
    check_entity_number_hygiene,
    check_entity_stray_files,
)


def test_frontmatter_completeness_flags_missing_fields(tmp_path: Path) -> None:
    # prose-header style: file with no frontmatter at all
    p = tmp_path / "entities" / "interpretations" / "0001-x.md"
    p.parent.mkdir(parents=True)
    p.write_text("**Date:** 2026-05-23\n\nbody\n", encoding="utf-8")
    ctx = _ctx(tmp_path)
    results = list(check_entity_frontmatter_completeness(ctx))
    assert any(r.severity is Severity.WARN for r in results)


def test_number_hygiene_flags_duplicate(tmp_path: Path) -> None:
    _write(tmp_path, "entities/questions/0001-a.md", {"id": "question:0001-a", "type": "question"})
    _write(tmp_path, "entities/questions/0001-b.md", {"id": "question:0001-b", "type": "question"})
    ctx = _ctx(tmp_path)
    results = list(check_entity_number_hygiene(ctx))
    assert any(r.severity is Severity.WARN and "0001" in r.message for r in results)


def test_stray_file_flagged(tmp_path: Path) -> None:
    (tmp_path / "entities" / "questions").mkdir(parents=True)
    (tmp_path / "entities" / "questions" / "README.txt").write_text("notes", encoding="utf-8")
    ctx = _ctx(tmp_path)
    results = list(check_entity_stray_files(ctx))
    assert any(r.severity is Severity.WARN for r in results)
```

- [ ] **Step 2: Run to verify failure**

Run: `cd science && uv run pytest tests/validate/test_checks_entity_conformance.py -k "frontmatter or number_hygiene or stray" -v`
Expected: FAIL — functions not defined.

- [ ] **Step 3: Implement the three checks**

Append to `science/src/science_tool/validate/checks/entity_conformance.py`:

```python
_REQUIRED_FRONTMATTER = ("id", "type", "title", "status", "created", "updated")
_NUMBER_RE = re.compile(r"^(\d{4})-")


@Check(section="entity frontmatter completeness...", order=22)
def check_entity_frontmatter_completeness(ctx: ValidateContext) -> Iterator[Result]:
    for kind in markdown_entity_kinds():
        policy = resolve_path_policy(kind)
        if policy.strategy == "singleton":
            continue
        directory = ctx.project_root / policy.root
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.md")):
            match = _FRONTMATTER.match(ctx.read_text_cached(path))
            if match is None:
                yield _result(_severity(ctx), _rel(ctx, path), f"{path.name}: no YAML frontmatter")
                continue
            try:
                data = yaml.safe_load(match.group(1)) or {}
            except yaml.YAMLError:
                yield _result(_severity(ctx), _rel(ctx, path), f"{path.name}: invalid YAML frontmatter")
                continue
            missing = [field for field in _REQUIRED_FRONTMATTER if field not in data]
            if missing:
                yield _result(
                    _severity(ctx), _rel(ctx, path), f"{path.name}: missing frontmatter fields: {', '.join(missing)}"
                )


@Check(section="entity number hygiene...", order=23)
def check_entity_number_hygiene(ctx: ValidateContext) -> Iterator[Result]:
    for kind in markdown_entity_kinds():
        policy = resolve_path_policy(kind)
        if policy.strategy != "numeric":
            continue
        directory = ctx.project_root / policy.root
        if not directory.is_dir():
            continue
        seen: dict[str, list[str]] = {}
        for path in sorted(directory.glob("*.md")):
            match = _NUMBER_RE.match(path.stem)
            if match is None:
                continue
            seen.setdefault(match.group(1), []).append(path.name)
        for number, names in sorted(seen.items()):
            if len(names) > 1:
                yield _result(
                    _severity(ctx), policy.root, f"duplicate {kind} number {number}: {', '.join(sorted(names))}"
                )


@Check(section="entity stray files...", order=24)
def check_entity_stray_files(ctx: ValidateContext) -> Iterator[Result]:
    for kind in markdown_entity_kinds():
        policy = resolve_path_policy(kind)
        if policy.strategy == "singleton":
            continue
        directory = ctx.project_root / policy.root
        if not directory.is_dir():
            continue
        for path in sorted(directory.iterdir()):
            if path.is_dir():
                yield _result(_severity(ctx), _rel(ctx, path), f"unexpected subdirectory in {policy.root}/")
            elif path.suffix != ".md":
                yield _result(_severity(ctx), _rel(ctx, path), f"non-entity file in {policy.root}/: {path.name}")
```

- [ ] **Step 4: Run to verify pass**

Run: `cd science && uv run pytest tests/validate/test_checks_entity_conformance.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/validate/checks/entity_conformance.py science/tests/validate/test_checks_entity_conformance.py
git commit -m "feat(validate): frontmatter, number-hygiene, stray-file checks (WARN)"
```

---

## Task 4: `id_prefixes.PREFIX_RULES` derived from the policy table

**Files:**
- Modify: `science/src/science_tool/validate/checks/id_prefixes.py:100-115`
- Test: `science/tests/validate/test_checks_id_prefixes.py` (extend)

- [ ] **Step 1: Write the failing test**

Append to `science/tests/validate/test_checks_id_prefixes.py`:

```python
def test_prefix_rules_cover_every_markdown_kind() -> None:
    from science_tool.entities import markdown_entity_kinds
    from science_tool.validate.checks.id_prefixes import prefix_rules

    rules = prefix_rules()
    for kind in markdown_entity_kinds():
        if kind in {"research-question", "claim-registry"}:
            continue  # singletons validated elsewhere
        assert rules.get(kind) == f"{kind}:", f"{kind} missing/incorrect prefix rule"
```

- [ ] **Step 2: Run to verify failure**

Run: `cd science && uv run pytest tests/validate/test_checks_id_prefixes.py -k prefix_rules_cover -v`
Expected: FAIL — `prefix_rules` not defined; static dict misses new kinds.

- [ ] **Step 3: Derive the rules**

In `science/src/science_tool/validate/checks/id_prefixes.py`, replace the static
`PREFIX_RULES = {...}` dict (lines 100-115) with a function plus a module-level
call, keeping the non-markdown reference kinds that the policy table does not own:

```python
from science_tool.entities import markdown_entity_kinds

# Reference/operational kinds not governed by the markdown policy table but
# still subject to id-prefix conformance.
_EXTRA_PREFIX_KINDS = ("paper", "spec")


def prefix_rules() -> dict[str, str]:
    kinds = set(markdown_entity_kinds()) | set(_EXTRA_PREFIX_KINDS)
    kinds -= {"research-question", "claim-registry"}  # singletons
    return {kind: f"{kind}:" for kind in sorted(kinds)}


PREFIX_RULES = prefix_rules()
```

- [ ] **Step 4: Repoint `check_id_prefixes`'s scan roots to include `entities/`**

`check_id_prefixes` currently iterates only `(ctx.doc_dir, ctx.specs_dir)`
(`science/src/science_tool/validate/checks/id_prefixes.py:147`), so after migration
it would never see files under `entities/`. Add a failing test, then fix the roots.

Test (append to `tests/validate/test_checks_id_prefixes.py`):

```python
def test_id_prefixes_scans_entities_dir(tmp_path) -> None:
    # a type/id mismatch under entities/ must be detected
    (tmp_path / "science.yaml").write_text("name: t\nlayout_version: 3\n", encoding="utf-8")
    d = tmp_path / "entities" / "questions"
    d.mkdir(parents=True)
    (d / "0001-x.md").write_text('---\ntype: question\nid: "hypothesis:0001-x"\n---\n', encoding="utf-8")
    from science_tool.validate.context import ValidateContext
    from science_tool.validate.checks.id_prefixes import check_id_prefixes
    ctx = ValidateContext.from_project_root(tmp_path, strict=False, verbose=False)
    assert any(r.severity is Severity.WARN for r in check_id_prefixes(ctx))
```

In `check_id_prefixes`, change the scan roots (line 147) to include `entities/`,
keeping the legacy roots during the Plan 2 transition (the cutover in Plan 3
removes `doc`/`specs`):

```python
    for root in (ctx.project_root / "entities", ctx.doc_dir, ctx.specs_dir):
```

- [ ] **Step 5: Run to verify pass**

Run: `cd science && uv run pytest tests/validate/test_checks_id_prefixes.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/validate/checks/id_prefixes.py science/tests/validate/test_checks_id_prefixes.py
git commit -m "refactor(validate): derive id-prefix rules from policy table; scan entities/"
```

---

## Task 5: Repoint `hypotheses.py` (drop the `h*` glob)

**Files:**
- Modify: `science/src/science_tool/validate/checks/hypotheses.py:31-37`
- Test: `science/tests/validate/test_checks_basic.py` or the hypotheses test module (locate with `grep -rl "check_hypothesis\|hypotheses" science/tests/validate`)

- [ ] **Step 1: Write the failing test**

Create `science/tests/validate/test_checks_hypotheses_entities.py`:

```python
from __future__ import annotations

from pathlib import Path

from science_tool.validate.checks.hypotheses import check_hypotheses
from science_tool.validate.context import ValidateContext


def test_hypotheses_checked_under_entities_with_numeric_names(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text(
        "name: t\nlayout_version: 3\nprofile: research\nknowledge_profiles: {local: local}\n",
        encoding="utf-8",
    )
    d = tmp_path / "entities" / "hypotheses"
    d.mkdir(parents=True)
    (d / "0001-x.md").write_text(
        '---\nid: "hypothesis:0001-x"\ntype: hypothesis\nstatus: proposed\n---\n'
        "## Falsifiability\n\nIt is falsifiable.\n",
        encoding="utf-8",
    )
    ctx = ValidateContext.from_project_root(tmp_path, strict=False, verbose=False)
    results = list(check_hypotheses(ctx))
    # The check emits an INFO "Checking <path>..." result for every file it visits.
    assert any("entities/hypotheses/0001-x.md" in str(r.path) for r in results)
```

- [ ] **Step 2: Run to verify failure**

Expected: FAIL — the check globs `specs/hypotheses/h*.md`, so `entities/hypotheses/0001-x.md` is never visited.

- [ ] **Step 3: Repoint the directory and glob**

In `science/src/science_tool/validate/checks/hypotheses.py`, replace lines 31-37:

```python
@Check(section="hypotheses...", order=5)
def check_hypotheses(ctx: ValidateContext) -> Iterator[Result]:
    hypotheses_dir = ctx.project_root / "entities" / "hypotheses"
    legacy_dir = ctx.specs_dir / "hypotheses"
    target = hypotheses_dir if hypotheses_dir.is_dir() else legacy_dir
    if target.is_dir():
        for path in sorted(target.glob("*.md")):  # was h*.md — numeric names have no letter
            if path.is_file():
                yield from _check_hypothesis(ctx, path)

    yield from _check_review_horizon_days(ctx)
```

- [ ] **Step 4: Run to verify pass**

Run: `cd science && uv run pytest tests/validate/ -k hypoth -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/validate/checks/hypotheses.py science/tests/validate/
git commit -m "fix(validate): check hypotheses under entities/, drop h* glob"
```

---

## Task 6: Repoint `discussions.py` (discussions + synthesis)

**Files:**
- Modify: `science/src/science_tool/validate/checks/discussions.py:48,77`
- Test: the discussions test module (`grep -rl discussions science/tests/validate`)

- [ ] **Step 1: Write the failing test**

Create `science/tests/validate/test_checks_discussions_entities.py`:

```python
from __future__ import annotations

from pathlib import Path

from science_tool.validate.checks.discussions import check_discussions
from science_tool.validate.context import ValidateContext


def test_discussions_checked_under_entities(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text(
        "name: t\nlayout_version: 3\nprofile: research\nknowledge_profiles: {local: local}\n",
        encoding="utf-8",
    )
    d = tmp_path / "entities" / "discussions"
    d.mkdir(parents=True)
    (d / "0001-x.md").write_text(
        '---\nid: "discussion:0001-x"\ntype: discussion\nstatus: active\n---\nbody\n',
        encoding="utf-8",
    )
    ctx = ValidateContext.from_project_root(tmp_path, strict=False, verbose=False)
    results = list(check_discussions(ctx))
    # Emits an INFO "Checking <path>..." per visited discussion.
    assert any("entities/discussions/0001-x.md" in str(r.path) for r in results)
```

- [ ] **Step 2: Run to verify failure**

Expected: FAIL — checks scan `doc/discussions` and `doc/reports/synthesis`.

- [ ] **Step 3: Repoint both directories**

In `check_discussions` (line 48), prefer `entities/discussions`:

```python
    entities_dir = ctx.project_root / "entities" / "discussions"
    legacy_dir = ctx.doc_dir / "discussions"
    discussions_dir = entities_dir if entities_dir.is_dir() else legacy_dir
```

In `_check_synthesis_frontmatter` (line 77), prefer `entities/synthesis`:

```python
    entities_synth = ctx.project_root / "entities" / "synthesis"
    legacy_synth = ctx.doc_dir / "reports" / "synthesis"
    if entities_synth.is_dir():
        candidates = [*sorted(entities_synth.glob("*.md"))]
    else:
        # v2 fallback: keep scanning the legacy dir AND the legacy singleton file.
        candidates = [*sorted(legacy_synth.glob("*.md")), ctx.doc_dir / "reports" / "synthesis.md"]
```

The legacy `doc/reports/synthesis.md` singleton candidate is **retained in the
fallback** so v2 projects keep validating during the transition; it is dropped
only at cutover (Plan 3, Task 9 Step 3 removes the legacy branch entirely).

- [ ] **Step 4: Run to verify pass**

Run: `cd science && uv run pytest tests/validate/ -k discussion -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/validate/checks/discussions.py science/tests/validate/
git commit -m "fix(validate): check discussions + synthesis under entities/"
```

---

## Task 7: Repoint `document_structure.py` and `papers.py`

**Files:**
- Modify: `science/src/science_tool/validate/checks/document_structure.py:37-38`
- Modify: `science/src/science_tool/validate/checks/papers.py:25-31`
- Test: the corresponding test modules

- [ ] **Step 1: Write the failing test**

Create `science/tests/validate/test_checks_document_structure_entities.py`:

```python
from __future__ import annotations

from pathlib import Path

from science_tool.validate.checks.document_structure import check_document_structure
from science_tool.validate.context import ValidateContext


def test_topics_checked_under_entities(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text(
        "name: t\nlayout_version: 3\nprofile: research\nknowledge_profiles: {local: local}\n",
        encoding="utf-8",
    )
    d = tmp_path / "entities" / "topics"
    d.mkdir(parents=True)
    (d / "0001-t.md").write_text(
        '---\nid: "topic:0001-t"\ntype: topic\nstatus: active\n---\n# Topic\n',
        encoding="utf-8",
    )
    ctx = ValidateContext.from_project_root(tmp_path, strict=False, verbose=False)
    results = list(check_document_structure(ctx))
    # Emits an INFO "Checking <path>..." per visited document.
    assert any("entities/topics/0001-t.md" in str(r.path) for r in results)
```

- [ ] **Step 2: Run to verify failure**

Expected: FAIL — scans `doc/background/topics` and `doc/background/papers`.

- [ ] **Step 3: Repoint**

`document_structure.py` (lines 37-38):

```python
    topics_dir = ctx.project_root / "entities" / "topics"
    papers_dir = ctx.project_root / "entities" / "papers"
    yield from _check_documents(ctx, topics_dir if topics_dir.is_dir() else ctx.doc_dir / "background" / "topics", _TOPIC_SECTIONS)
    yield from _check_documents(ctx, papers_dir if papers_dir.is_dir() else ctx.doc_dir / "background" / "papers", _PAPER_SECTIONS)
```

`papers.py` (the INFO message at lines 25-31):

```python
    yield _result(
        Severity.INFO,
        "entities/papers",
        "Paper summary structure is checked in entities/papers/",
    )
```

(Also update `_check_paper_dataset_refs` if it iterates `ctx.papers_dir`; point it
at `entities/papers` with a `doc/background/papers` fallback. Grep the function
body before editing.)

- [ ] **Step 4: Run to verify pass**

Run: `cd science && uv run pytest tests/validate/ -k "document_structure or paper" -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/validate/checks/document_structure.py science/src/science_tool/validate/checks/papers.py science/tests/validate/
git commit -m "fix(validate): check topics + papers under entities/"
```

---

## Task 8: `layout_version` migration notice (WARN)

**Files:**
- Modify: `science/src/science_tool/validate/checks/manifest.py`
- Test: `science/tests/test_health.py` or `tests/validate/test_checks_basic.py` (locate the manifest check test)

- [ ] **Step 1: Write the failing test**

```python
def test_layout_version_below_3_warns(tmp_path) -> None:
    (tmp_path / "science.yaml").write_text(
        "name: t\ncreated: 2026-01-01\nlast_modified: 2026-01-01\nstatus: active\n"
        "summary: s\nprofile: research\nlayout_version: 2\nknowledge_profiles: {local: local}\n",
        encoding="utf-8",
    )
    ctx = ValidateContext.from_project_root(tmp_path, strict=False, verbose=False)
    from science_tool.validate.checks.manifest import check_manifest
    results = list(check_manifest(ctx))
    assert any(r.severity is Severity.WARN and "layout_version" in r.message for r in results)
```

- [ ] **Step 2: Run to verify failure**

Expected: FAIL — no such warning.

- [ ] **Step 3: Add the notice**

In `check_manifest` (after the required-fields loop) in
`science/src/science_tool/validate/checks/manifest.py`:

```python
    layout_version = ctx.manifest.get("layout_version")
    if isinstance(layout_version, int) and layout_version < 3:
        yield _result(
            Severity.WARN,
            "science.yaml: layout_version < 3 — run `science entities migrate` to adopt the entities/ layout",
        )
```

(WARN, not ERROR — the hard cutover is Plan 3.)

- [ ] **Step 4: Run to verify pass**

Run: `cd science && uv run pytest -k "layout_version" -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/validate/checks/manifest.py science/tests/
git commit -m "feat(validate): warn when layout_version < 3 (migration pending)"
```

---

## Task 9: Generalize atomic reservation to all numeric kinds

**Files:**
- Create: `science/src/science_tool/entity_reservation.py`
- Modify: `science/src/science_tool/questions.py` (delegate)
- Test: `science/tests/test_entity_reservation.py` (create)

- [ ] **Step 1: Write the failing test**

Create `science/tests/test_entity_reservation.py`:

```python
from __future__ import annotations

from pathlib import Path

from science_tool.entity_reservation import reserve_entity


def test_reserve_first_is_0001(tmp_path: Path) -> None:
    res = reserve_entity(tmp_path, "hypothesis", "first idea")
    assert res.entity_id == "hypothesis:0001-first-idea"
    assert (tmp_path / "entities" / "hypotheses" / "0001-first-idea.md").is_file()


def test_reserve_is_atomic_and_increments(tmp_path: Path) -> None:
    a = reserve_entity(tmp_path, "finding", "alpha")
    b = reserve_entity(tmp_path, "finding", "beta")
    assert a.entity_id == "finding:0001-alpha"
    assert b.entity_id == "finding:0002-beta"


def test_reserve_tolerates_legacy_letter_siblings(tmp_path: Path) -> None:
    d = tmp_path / "entities" / "hypotheses"
    d.mkdir(parents=True)
    (d / "h03-legacy.md").write_text("x", encoding="utf-8")
    res = reserve_entity(tmp_path, "hypothesis", "next")
    assert res.entity_id == "hypothesis:0004-next"
```

- [ ] **Step 2: Run to verify failure**

Run: `cd science && uv run pytest tests/test_entity_reservation.py -v`
Expected: FAIL — module does not exist.

- [ ] **Step 3: Implement `reserve_entity`**

Create `science/src/science_tool/entity_reservation.py`, lifting the
`O_CREAT|O_EXCL` loop pattern from `questions.py:175`:

```python
"""Atomic, kind-agnostic id reservation for numeric entity kinds.

Generalizes questions.reserve_question: the destination file itself is the
lock (O_CREAT|O_EXCL), so concurrent agents cannot claim the same NNNN.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re

from science_tool.entities import (
    EntityCommandError,
    LOCAL_PART_WIDTH,
    derive_slug,
    resolve_path_policy,
    validate_slug,
)

_NUMERIC_SCAN_RE = re.compile(r"^(?:[A-Za-z])?(\d+)")


@dataclass(frozen=True)
class Reservation:
    entity_id: str
    path: Path


def _max_number(directory: Path) -> int:
    max_n = 0
    if directory.is_dir():
        for entry in directory.glob("*.md"):
            match = _NUMERIC_SCAN_RE.match(entry.stem)
            if match is not None:
                max_n = max(max_n, int(match.group(1)))
    return max_n


def reserve_entity(
    project_root: Path,
    kind: str,
    title: str,
    *,
    slug: str | None = None,
    stub: str = "",
    max_attempts: int = 100,
) -> Reservation:
    policy = resolve_path_policy(kind)
    if policy.strategy != "numeric":
        raise EntityCommandError(f"reserve_entity supports numeric kinds only; {kind} is {policy.strategy}")
    directory = project_root / policy.root
    directory.mkdir(parents=True, exist_ok=True)
    slug_value = validate_slug(slug) if slug is not None else derive_slug(title)

    for _ in range(max_attempts):
        next_n = _max_number(directory) + 1
        local_part = f"{next_n:0{LOCAL_PART_WIDTH}d}-{slug_value}"
        path = directory / f"{local_part}.md"
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        except FileExistsError:
            continue
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(stub)
        return Reservation(entity_id=f"{kind}:{local_part}", path=path)

    raise EntityCommandError(f"could not reserve a {kind} number after {max_attempts} attempts")
```

- [ ] **Step 4: Run to verify pass**

Run: `cd science && uv run pytest tests/test_entity_reservation.py -v`
Expected: PASS.

- [ ] **Step 5: Delegate `reserve_question` and keep its test green**

In `science/src/science_tool/questions.py`, reimplement `reserve_question` to call
`reserve_entity(project_root, "question", title, slug=slug, stub=<rendered stub>)`,
keeping its richer stub rendering (`_render_stub`) by passing it as `stub`. Run
the existing question reservation tests:

Run: `cd science && uv run pytest tests/test_questions.py -v`
Expected: PASS. If a test asserts the old `q##` filename, update it to the
`NNNN-slug` form (the reservation now uses the canonical numeric strategy).

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/entity_reservation.py science/src/science_tool/questions.py science/tests/test_entity_reservation.py science/tests/test_questions.py
git commit -m "feat(entities): kind-agnostic atomic reservation; questions delegates"
```

---

## Task 10: Domain templates for the new kinds

**Files:**
- Modify: `science/model/src/science_model/templates/{finding,inquiry,method,paper,pre-registration,synthesis}.md` (and others as the audit finds)
- Modify: `science/model/src/science_model/templates.py:14` (`MIGRATED_KINDS`)
- Modify: `science/model/src/science_model/templates/hypothesis.md` (fix the literal `h{{nn}}` placeholder)
- Test: `science/model/tests/` template tests + a render assertion

- [ ] **Step 1: Audit which kinds have a usable template**

Run: `ls science/model/src/science_model/templates/` and, for each kind in
`markdown_entity_kinds()`, check whether `<kind>.md` exists and contains a
`_template:` metadata block:

Run: `cd science && for k in finding inquiry method paper pre-registration synthesis topic report plan search observation mechanism; do f=../science/model/src/science_model/templates/$k.md; [ -f "$f" ] && grep -ql "_template:" "$f" && echo "$k: migrated" || echo "$k: needs work"; done`

Record the result; it determines which templates this task migrates vs. which
fall back to generic (acceptable) for now.

- [ ] **Step 2: Write the failing render test**

Create/extend a template test (match the style in `science/model/tests/`):

```python
def test_finding_template_renders_with_numeric_id() -> None:
    from science_model.templates import render_entity  # confirm the public render entrypoint name

    rendered = render_entity(kind="finding", entity_id="finding:0001-x", title="X", ...)
    assert "finding:0001-x" in rendered
    assert "{{nn}}" not in rendered and "h{{nn}}" not in rendered
```

> Confirm the actual render entrypoint/signature from `templates.py:100` (`render`)
> and how `entities.py` calls it; align the test to that signature.

- [ ] **Step 3: Run to verify failure**

Expected: FAIL for any template still carrying `{{nn}}`/`h{{nn}}` placeholders or
lacking a `_template` block.

- [ ] **Step 4: Migrate templates**

For each "needs work" kind from Step 1: add a `_template:` metadata block modeled
on `hypothesis.md` (frontmatter field policy + sections), and replace any literal
id placeholder (`h{{nn}}-{{slug}}`, `{{nn}}`) with `{{local_part}}` so it matches
the numeric strategy. In `hypothesis.md`, change the literal
`id: "hypothesis:h{{nn}}-{{slug}}"` to `id: "hypothesis:{{local_part}}"`.

Add migrated kinds to `MIGRATED_KINDS` in `science/model/src/science_model/templates.py:14`.

> Kinds with no template file (e.g. report/plan/search/observation/mechanism per
> the audit) are intentionally left on the generic scaffold; do NOT fabricate
> domain sections for them here — that is a separate content task.

- [ ] **Step 5: Run to verify pass + full suite**

Run: `cd science && uv run pytest && (cd model && uv run pytest)`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add science/model/src/science_model/templates/ science/model/src/science_model/templates.py science/model/tests/
git commit -m "feat(templates): numeric local-part placeholders; migrate new-kind templates"
```

---

## Task 11: Full suite + lint

- [ ] **Step 1: Run everything**

Run: `cd science && uv run pytest -q && (cd model && uv run pytest -q)`
Expected: PASS. Fix any test still asserting the legacy `doc/`/`specs/` or
`q##`/`h##` shapes — update assertions, do not weaken them.

- [ ] **Step 2: Lint**

Run: `cd science && uv run ruff check src tests && (cd model && uv run ruff check src tests)`
Expected: clean.

- [ ] **Step 3: Commit any fixups**

```bash
git add -A
git commit -m "test: align suites with Plan 2 validation + reservation + templates"
```

---

## Self-review (coverage against the design)

- Five new checks (location, filename, frontmatter, number hygiene, stray) → Tasks 2, 3. ✅ (all WARN)
- `id_prefixes` derived from policy table → Task 4. ✅
- Repoint `hypotheses` (drop `h*` glob), `discussions`+`synthesis`, `document_structure` (topics/papers), `papers` → Tasks 5, 6, 7. ✅
- `layout_version` awareness (WARN) → Task 8. ✅
- Atomic reservation generalized (design §290) → Task 9. ✅
- Domain templates for new kinds + fix letter-prefix placeholder → Task 10. ✅

**Still deferred to Plan 3 (cutover):**
- Remove `doc/`/`specs/` fallbacks added in Plan 1 (discovery scan roots, singleton
  lookups) and in this plan (legacy-dir fallbacks in Tasks 5–7).
- Promote the Task 2/3/8 WARNs to ERROR; make `layout_version: 3` mandatory.
- The `science entities migrate` command (frontmatter synthesis → id-map → raw
  frontmatter/prose rewrite → `git mv` → re-validate), the migration guide, and
  the pilot.

**Verify-before-coding notes (left in-task):** the render entrypoint name/signature
in `templates.py:100`; the exact ctx/seed helpers in each `tests/validate/` module
being extended; and `_check_paper_dataset_refs`'s directory iteration in `papers.py`.

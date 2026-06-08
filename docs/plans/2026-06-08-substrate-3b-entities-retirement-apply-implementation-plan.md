# Substrate Phase 3b — `entities.yaml` retirement `--apply` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the 3a aggregate triage actionable — a `slug` filename strategy plus a `science entities triage-aggregate --apply` executor that promotes `coined` rows to id-preserving owner files and deletes `cruft`/`shadow` rows, v3-gated, dry-run-default, idempotent and crash-recoverable.

**Architecture:** Two halves. (A) A foundation prerequisite in `entities.py` + `entity_layout_migration.py`: a `slug` filename strategy and a core `concept` policy, so coined kebab ids (`concept:1q-gain`) are conforming, id-preserving owners. (B) A new `graph/aggregate_retire.py` (pure planner + impure executor) reading the 3a classifier + compiled model, plus `--apply`/per-bucket flags on the existing CLI. Spec: `~/d/science/docs/plans/2026-06-08-substrate-3b-entities-retirement-apply-design.md`.

**Tech Stack:** Python 3.12, Pydantic v2, `click`, `pytest`, `pyyaml`. All commands from `~/d/science/science`. Tests: `uv run --frozen pytest`. Lint: `uv run --frozen ruff check . && uv run --frozen ruff format --check .` (120-char). Never `pip`; always `uv`. No `Co-Authored-By` trailer in commits.

---

## Background the implementer needs

- **The policy substrate** (`src/science_tool/entities.py`): `EntityFilenameStrategy = Literal["numeric", "citekey", "singleton"]` (line 25); `EntityPathPolicy(root: Path, strategy)` (line 34); the core policy table `_BUILTIN_MARKDOWN_POLICIES` (line 40, **this is the real name — the design called it `_CORE_POLICIES`**); `_VALID_STRATEGIES = frozenset({"numeric", "citekey"})` (line 77, the set a *local* kind may declare); regexes `_SLUG_RE = ^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$` (184), `_CITEKEY_RE` (185), `_NUMERIC_LOCAL_PART_RE = ^\d{4}-…` (186). Helpers: `local_part_conforms(kind, local_part, *, project_root=None)` (336), `validate_entity_id(kind, entity_id)` (393), `generate_entity_id(project_root, kind, title, entity_id, slug, today=None)` (425), `path_for_entity(kind, entity_id, today)` (447), `validate_slug` (387), `derive_slug(title)` (380), `resolve_path_policy(kind, *, project_root=None)` (320, raises `EntityCommandError` for an unknown kind). Local kinds default to `numeric` (`ek.strategy or "numeric"`, line 154).
- **`concept` has no policy today** — it is core-*loadable* (`entity_registry`) but absent from `_BUILTIN_MARKDOWN_POLICIES`. `latent`/`decision` are local kinds (MM30 manifest) that default to `numeric`. None of the coined kebab ids conform to numeric/citekey — hence the `slug` strategy.
- **The migrator** (`src/science_tool/entity_layout_migration.py`): `plan_migration(project_root) -> MigrationPlan` (408); its per-kind loop (428) has `singleton`/`citekey` branches then a `numeric` fallthrough. `_DEST_ROOT_TO_KIND` (203) is **auto-built** from `markdown_entity_kinds()`, so adding `concept` to the policy table makes `entities/concepts` a known destination and lets a `concept` file reach that loop. In the numeric branch, `int(stem.split("-", 1)[0])` (459) crashes on a slug stem like `1q-gain`. `_add_move(plan, entity, new_rel, new_id, kind)` (528). `MigrationPlan.moves[i]` has `.old_id`, `.new_id`, `.new_rel_path`.
- **The 3a classifier** (`src/science_tool/graph/aggregate_triage.py`): `class AggregateBucket(str, Enum)` with `SHADOW/COINED/DECISION_LOG/EXTERNAL_REF/CRUFT/AMBIGUOUS`; `AggregateRowTriage(canonical_id, kind, source_path, has_real_owner, bucket, evidence)`; `classify_aggregate_rows(sources) -> list[AggregateRowTriage]`.
- **The compiled model** (`src/science_tool/graph/sources.py`): `load_project_sources(project_root, *, include_commons, strict_core_schema, strict_identity)`; `ProjectSources.aggregate_rows: list[AggregateRowMeta]` where `AggregateRowMeta(path, line, canonical_id, kind, source_path)` (`path` is the project-root-relative aggregate file, `line` the entry index); `ProjectSources.identity_declarations: list[IdentityDeclaration]` where `IdentityDeclaration(canonical_id, participation_mode, owner_scope, adapter, source_ref, deprecated)` and `source_ref.path`/`source_ref.line`.
- **Aggregate file shape** (`src/science_tool/graph/storage_adapters/aggregate.py`): `_MULTI_TYPE_FILES = {"entities.yaml": "entities", "terms.yaml": "terms"}` — these are **mappings keyed by a root key**, not top-level lists; the entry list is `data["entities"]`. `terms.yaml` is row-normalized on load and is **out of scope** (Phase 4).
- **The 2a promoter** (`src/science_tool/datapackage_promote.py`): `_is_safe_slug(slug)` (55, the path-safety firewall: `^[a-z0-9][a-z0-9._-]*$` and no `..`); owner-file render idiom `"---\n" + yaml.safe_dump(fm, sort_keys=False, allow_unicode=True) + "---\n\n" + body` (115). Reuse both.
- **The 3a CLI command** (`src/science_tool/cli.py:288-329`): `@entities_group.command("triage-aggregate")` → `entities_triage_aggregate_command(project_root, output_format)`. `json` and `Path` and `click` are imported at module top.
- **Fixtures:** a project is discovered via `science.yaml`. `AggregateAdapter` scans `knowledge/sources/<value>/` where `<value>` is the profile-map value — use `profiles: {local: local}` → `knowledge/sources/local/entities.yaml`. For v3 tests add `layout_version: 3`. Because `concept` becomes a core `slug` kind in Task 1, fixtures can use `concept` rows **without** any local-kind registration.

---

## Task 1: the `slug` filename strategy in `entities.py`

**Files:**
- Modify: `src/science_tool/entities.py`
- Modify: `tests/test_entity_layout_migration.py:54-59` (the `type: concept` example becomes recognized)
- Test: `tests/test_slug_strategy.py` (new)

- [ ] **Step 1: Write the failing test**

Create `tests/test_slug_strategy.py`:

```python
from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from science_tool.entities import (
    EntityCommandError,
    generate_entity_id,
    local_part_conforms,
    path_for_entity,
    resolve_path_policy,
    validate_entity_id,
)


def test_concept_is_a_core_slug_policy() -> None:
    policy = resolve_path_policy("concept")
    assert policy.strategy == "slug"
    assert policy.root == Path("entities/concepts")


def test_slug_local_part_conforms() -> None:
    assert local_part_conforms("concept", "1q-gain") is True
    assert local_part_conforms("concept", "age") is True
    assert local_part_conforms("concept", "Not A Slug") is False
    assert local_part_conforms("concept", "trailing-") is False


def test_validate_entity_id_accepts_slug_rejects_garbage() -> None:
    assert validate_entity_id("concept", "concept:1q-gain") == "concept:1q-gain"
    with pytest.raises(EntityCommandError):
        validate_entity_id("concept", "concept:Bad Slug")


def test_generate_slug_id_uses_title_slug_not_number(tmp_path: Path) -> None:
    # No NNNN- prefix: slug strategy preserves the title-slug directly.
    got = generate_entity_id(tmp_path, "concept", "Chromosome 1q Gain", None, None)
    assert got == "concept:chromosome-1q-gain"


def test_path_for_concept_lands_under_entities_concepts() -> None:
    p = path_for_entity("concept", "concept:1q-gain", date(2026, 6, 8))
    assert p == Path("entities/concepts/1q-gain.md")


def test_numeric_and_citekey_unchanged() -> None:
    # Regression: existing strategies are untouched.
    assert local_part_conforms("question", "0001-foo") is True
    assert local_part_conforms("question", "1q-gain") is False
    assert validate_entity_id("question", "question:0001-foo") == "question:0001-foo"
    assert validate_entity_id("paper", "paper:Adams2025") == "paper:Adams2025"
    with pytest.raises(EntityCommandError):
        validate_entity_id("question", "question:1q-gain")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_slug_strategy.py -v`
Expected: FAIL — `test_concept_is_a_core_slug_policy` raises `EntityCommandError: Unsupported source-authored entity kind: concept` (concept has no policy yet).

- [ ] **Step 3: Add `slug` to the strategy literal and valid set**

In `src/science_tool/entities.py`:
- Line 25: `EntityFilenameStrategy = Literal["numeric", "citekey", "singleton", "slug"]`
- Line 77: `_VALID_STRATEGIES: frozenset[str] = frozenset({"numeric", "citekey", "slug"})`

- [ ] **Step 4: Register `concept` as a core slug policy**

In `_BUILTIN_MARKDOWN_POLICIES` (after the `pre-registration` entry, before the singleton comment), add:

```python
    "concept": EntityPathPolicy(Path("entities/concepts"), "slug"),
```

- [ ] **Step 5: Teach the three strategy switches about `slug`**

In `local_part_conforms` (after the `citekey` branch, before `return False`):

```python
    if strategy == "slug":
        return bool(_SLUG_RE.fullmatch(local_part))
```

In `validate_entity_id` (after the `citekey` block that ends `return entity_id`, before the `# numeric` comment):

```python
    if strategy == "slug":
        if not _SLUG_RE.fullmatch(local_part):
            raise EntityCommandError(f"Invalid slug local part: {entity_id}")
        return entity_id
```

In `generate_entity_id`, the tail currently reads:

```python
    slug_value = validate_slug(slug) if slug is not None else derive_slug(title)
    return f"{kind}:{_next_numeric_local_part(project_root, kind, slug_value)}"
```

Insert a slug branch between those two lines:

```python
    slug_value = validate_slug(slug) if slug is not None else derive_slug(title)
    if strategy == "slug":
        return f"{kind}:{slug_value}"
    return f"{kind}:{_next_numeric_local_part(project_root, kind, slug_value)}"
```

(`path_for_entity` needs no change: it is `resolve_path_policy(kind).root / f"{local_part}.md"` and becomes correct once `validate_entity_id` accepts the slug id.)

- [ ] **Step 6: Fix the now-stale migrator discovery test**

`concept` is now a recognized kind, so `tests/test_entity_layout_migration.py:54-59` (which used `type: concept` as its *unrecognized* example) must switch to a genuinely-unregistered type. Replace that test body with:

```python
def test_unrecognized_frontmatter_type_is_skipped(tmp_path: Path) -> None:
    # A file whose frontmatter type is not a known markdown entity kind must be
    # silently excluded from discovery results. (`concept` is now a recognized
    # core slug kind, so use a type that is registered nowhere.)
    _write(tmp_path, "doc/glossary/foo.md", "---\ntype: glossary-entry\n---\nBody.\n")
    found = {e.rel_path: e for e in discover_legacy_entities(tmp_path)}
    assert "doc/glossary/foo.md" not in found
```

- [ ] **Step 7: Run the new test + the migrator suite + full suite**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_slug_strategy.py tests/test_entity_layout_migration.py -v`
Expected: PASS.
Run: `cd ~/d/science/science && uv run --frozen pytest -q`
Expected: green. **If any other test fails because `concept` is now a recognized kind, that is expected fallout of this task** — read the failure; if it merely asserted `concept` was unknown, update it the same way as Step 6. Do not weaken any unrelated assertion.

- [ ] **Step 8: Lint**

Run: `cd ~/d/science/science && uv run --frozen ruff check src/science_tool/entities.py tests/test_slug_strategy.py && uv run --frozen ruff format --check tests/test_slug_strategy.py`
Expected: clean.

- [ ] **Step 9: Commit**

```bash
cd ~/d/science && git add science/src/science_tool/entities.py science/tests/test_slug_strategy.py science/tests/test_entity_layout_migration.py
git commit -m "feat(substrate-3b): slug filename strategy + concept core policy (§3.0)"
```

---

## Task 2: migrator `slug` planning branch (crash guard)

**Files:**
- Modify: `src/science_tool/entity_layout_migration.py` (the per-kind loop, after the `citekey` branch near line 439)
- Test: `tests/test_entity_layout_migration.py` (add one test)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_entity_layout_migration.py` (it already imports `plan_migration`, `discover_legacy_entities`, and the `_write` helper):

```python
def test_plan_keeps_slug_for_concepts_without_numbering(tmp_path: Path) -> None:
    # A slug-strategy kind (concept) with a kebab stem must plan an id-preserving
    # move — never numbered — and must NOT crash the numeric branch on int("1q").
    _write(tmp_path, "doc/concepts/1q-gain.md", '---\nid: "concept:1q-gain"\ntype: concept\n---\nBody.\n')
    plan = plan_migration(tmp_path)
    move = next(m for m in plan.moves if m.old_id == "concept:1q-gain")
    assert move.new_id == "concept:1q-gain"
    assert move.new_rel_path == "entities/concepts/1q-gain.md"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_entity_layout_migration.py::test_plan_keeps_slug_for_concepts_without_numbering -v`
Expected: FAIL — a `ValueError: invalid literal for int() with base 10: '1q'` (the slug stem reaching the numeric branch), or a `KeyError`/no-move if discovery differs. Either way, not PASS.

- [ ] **Step 3: Add the `slug` branch parallel to `citekey`**

In `src/science_tool/entity_layout_migration.py`, the per-kind loop has (near line 435):

```python
        if policy.strategy == "citekey":
            for entity in items:
                local = Path(entity.rel_path).stem
                _add_move(plan, entity, f"{policy.root.as_posix()}/{local}.md", f"{kind}:{local}", kind)
            continue
```

Immediately **after** that block (before the `# numeric:` comment), add the identical-shape slug branch:

```python
        if policy.strategy == "slug":
            # Slug kinds preserve their kebab id; never numbered. Without this branch
            # a stem like "1q-gain" reaches the numeric branch and int("1q") crashes.
            for entity in items:
                local = Path(entity.rel_path).stem
                _add_move(plan, entity, f"{policy.root.as_posix()}/{local}.md", f"{kind}:{local}", kind)
            continue
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_entity_layout_migration.py -v`
Expected: PASS (the new test and all existing migrator tests).

- [ ] **Step 5: Lint + commit**

```bash
cd ~/d/science/science && uv run --frozen ruff check src/science_tool/entity_layout_migration.py
cd ~/d/science && git add science/src/science_tool/entity_layout_migration.py science/tests/test_entity_layout_migration.py
git commit -m "feat(substrate-3b): migrator slug planning branch (crash guard, §3.0)"
```

---

## Task 3: the pure planner — `plan_retirement`

**Files:**
- Create: `src/science_tool/graph/aggregate_retire.py`
- Test: `tests/graph/test_aggregate_retire_plan.py` (new)

- [ ] **Step 1: Write the failing test**

Create `tests/graph/test_aggregate_retire_plan.py`:

```python
from __future__ import annotations

from pathlib import Path

import yaml

from science_tool.graph.aggregate_retire import RetireAction, plan_retirement
from science_tool.graph.sources import load_project_sources

_MANIFEST = "name: demo\nprofile: research\nprofiles: {local: local}\nlayout_version: 3\n"


def _write_entities(root: Path, entries: list[dict]) -> None:
    (root / "science.yaml").write_text(_MANIFEST, encoding="utf-8")
    agg = root / "knowledge" / "sources" / "local"
    agg.mkdir(parents=True, exist_ok=True)
    (agg / "entities.yaml").write_text(yaml.safe_dump({"entities": entries}), encoding="utf-8")


def _write_terms(root: Path, entries: list[dict]) -> None:
    agg = root / "knowledge" / "sources" / "local"
    agg.mkdir(parents=True, exist_ok=True)
    (agg / "terms.yaml").write_text(yaml.safe_dump({"terms": entries}), encoding="utf-8")


def _concept(cid: str) -> dict:
    return {"canonical_id": cid, "kind": "concept", "title": cid, "source_path": "knowledge/sources/local/entities.yaml"}


def _cruft(cid: str, kind: str) -> dict:
    return {"canonical_id": cid, "kind": kind, "title": cid, "source_path": "migration:audit"}


def _load(root: Path):
    return load_project_sources(root, include_commons=False, strict_core_schema=False, strict_identity=False)


def _plan(root: Path, **flags):
    sources = _load(root)
    from science_tool.graph.aggregate_triage import classify_aggregate_rows

    return plan_retirement(root, sources, classify_aggregate_rows(sources), **flags)


def test_coined_promotes_with_policy_target(tmp_path: Path) -> None:
    _write_entities(tmp_path, [_concept("concept:1q-gain")])
    plan = _plan(tmp_path, promote_coined=True, delete_cruft=False, delete_shadow=False)
    assert [p.triage.canonical_id for p in plan.promote] == ["concept:1q-gain"]
    row = plan.promote[0]
    assert row.action is RetireAction.PROMOTE
    assert row.target_path == "entities/concepts/1q-gain.md"
    assert row.source_path == "knowledge/sources/local/entities.yaml"
    assert row.line is not None


def test_cruft_deletes_only_when_enabled(tmp_path: Path) -> None:
    _write_entities(tmp_path, [_cruft("concept:treatment-benefit", "concept")])
    off = _plan(tmp_path, promote_coined=False, delete_cruft=False, delete_shadow=False)
    assert off.delete == ()
    on = _plan(tmp_path, promote_coined=False, delete_cruft=True, delete_shadow=False)
    assert [p.triage.canonical_id for p in on.delete] == ["concept:treatment-benefit"]


def test_terms_yaml_rows_are_never_planned(tmp_path: Path) -> None:
    # A coined/cruft-looking row in terms.yaml must be excluded by the firewall.
    _write_entities(tmp_path, [_concept("concept:keep-me")])
    _write_terms(tmp_path, [{"canonical_id": "concept:in-terms", "kind": "concept", "title": "x",
                             "source_path": "migration:audit"}])
    plan = _plan(tmp_path, promote_coined=True, delete_cruft=True, delete_shadow=True)
    acted = {p.triage.canonical_id for p in (*plan.promote, *plan.delete)}
    assert "concept:in-terms" not in acted
    assert acted == {"concept:keep-me"}


def test_ambiguous_rows_are_never_acted(tmp_path: Path) -> None:
    # A self-sourced `topic` buckets AMBIGUOUS (a never-acted bucket). Even with all
    # three flags on, it must be neither promoted nor deleted.
    _write_entities(tmp_path, [{"canonical_id": "topic:some-topic", "kind": "topic", "title": "x",
                                "source_path": "knowledge/sources/local/entities.yaml"}])
    plan = _plan(tmp_path, promote_coined=True, delete_cruft=True, delete_shadow=True)
    assert plan.promote == ()
    assert plan.delete == ()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/graph/test_aggregate_retire_plan.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'science_tool.graph.aggregate_retire'`.

- [ ] **Step 3: Write the planner module**

Create `src/science_tool/graph/aggregate_retire.py`:

```python
"""Plan + apply `entities.yaml` retirement (design §3, Phase 3b).

The planner is pure over the 3a classification + the compiled model; it never
mutates. It is scoped to `entities.yaml` declarations only (the §3.1 firewall —
`terms.yaml` and single-type aggregates are Phase-4/out of scope). Promotion is
id-preserving: the target is computed from the entity path policy, and a
non-conforming id is rejected, never renumbered. The executor (apply_retirement)
lives in the same module and owns all file mutation.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from science_tool.datapackage_promote import _is_safe_slug
from science_tool.entities import EntityCommandError, local_part_conforms, resolve_path_policy
from science_tool.graph.aggregate_triage import AggregateBucket, AggregateRowTriage

if TYPE_CHECKING:
    from science_tool.graph.sources import ProjectSources

_ENTITIES_FILE = "entities.yaml"


class RetireAction(str, Enum):
    PROMOTE = "promote"
    DELETE = "delete"


@dataclass(frozen=True, slots=True)
class PlannedRow:
    triage: AggregateRowTriage
    action: RetireAction
    source_path: str  # the entities.yaml file (declaration source_ref.path), project-root-relative
    line: int  # entry index within that file
    target_path: str | None  # PROMOTE: policy.root/<local>.md; reconcile: the existing owner file; DELETE: None


@dataclass(frozen=True, slots=True)
class RetirementPlan:
    promote: tuple[PlannedRow, ...]
    delete: tuple[PlannedRow, ...]
    reconcile: tuple[PlannedRow, ...]  # shadow rows to marker-check (promote_coined only); §3.5 step 2
    rejected: tuple[tuple[AggregateRowTriage, str], ...]


def _real_owner_path(sources: "ProjectSources", canonical_id: str) -> str | None:
    """The path of the non-aggregate, non-deprecated owner of `canonical_id`, if any."""
    for decl in sources.identity_declarations:
        if (
            decl.canonical_id == canonical_id
            and decl.adapter != "aggregate"
            and not decl.deprecated
            and decl.source_ref is not None
        ):
            return decl.source_ref.path
    return None


def plan_retirement(
    project_root: Path,
    sources: "ProjectSources",
    rows: list[AggregateRowTriage],
    *,
    promote_coined: bool,
    delete_cruft: bool,
    delete_shadow: bool,
) -> RetirementPlan:
    triage_by_id = {t.canonical_id: t for t in rows}
    action_for: dict[AggregateBucket, RetireAction | None] = {
        AggregateBucket.COINED: RetireAction.PROMOTE if promote_coined else None,
        AggregateBucket.CRUFT: RetireAction.DELETE if delete_cruft else None,
        AggregateBucket.SHADOW: RetireAction.DELETE if delete_shadow else None,
    }
    promote: list[PlannedRow] = []
    delete: list[PlannedRow] = []
    reconcile: list[PlannedRow] = []
    rejected: list[tuple[AggregateRowTriage, str]] = []

    for meta in sources.aggregate_rows:
        if Path(meta.path).name != _ENTITIES_FILE:
            continue  # §3.1 firewall: never touch terms.yaml / single-type aggregates
        triage = triage_by_id.get(meta.canonical_id)
        if triage is None:
            continue
        # Recovery candidate: a shadow whose owner we may have written in a prior run.
        if promote_coined and triage.bucket is AggregateBucket.SHADOW:
            owner = _real_owner_path(sources, meta.canonical_id)
            if owner is not None:
                reconcile.append(PlannedRow(triage, RetireAction.DELETE, meta.path, meta.line, owner))
        action = action_for.get(triage.bucket)
        if action is None:
            continue
        if action is RetireAction.DELETE:
            delete.append(PlannedRow(triage, action, meta.path, meta.line, None))
            continue
        # PROMOTE: resolve the policy and require an id-preserving, conforming, safe target.
        kind = meta.kind
        local_part = meta.canonical_id.split(":", 1)[1] if ":" in meta.canonical_id else meta.canonical_id
        try:
            policy = resolve_path_policy(kind, project_root=project_root)
        except EntityCommandError:
            rejected.append((triage, f"no path policy for kind {kind!r}"))
            continue
        if policy.strategy != "slug" and not local_part_conforms(kind, local_part, project_root=project_root):
            rejected.append((triage, f"id {meta.canonical_id!r} does not conform to {policy.strategy} strategy"))
            continue
        if not _is_safe_slug(local_part):
            rejected.append((triage, "unsafe slug"))
            continue
        target = (policy.root / f"{local_part}.md").as_posix()
        promote.append(PlannedRow(triage, action, meta.path, meta.line, target))

    return RetirementPlan(tuple(promote), tuple(delete), tuple(reconcile), tuple(rejected))
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/graph/test_aggregate_retire_plan.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Lint + commit**

```bash
cd ~/d/science/science && uv run --frozen ruff check src/science_tool/graph/aggregate_retire.py tests/graph/test_aggregate_retire_plan.py && uv run --frozen ruff format src/science_tool/graph/aggregate_retire.py tests/graph/test_aggregate_retire_plan.py
cd ~/d/science && git add science/src/science_tool/graph/aggregate_retire.py science/tests/graph/test_aggregate_retire_plan.py
git commit -m "feat(substrate-3b): pure entities.yaml retirement planner (§3.4)"
```

---

## Task 4: the executor — `apply_retirement` (write, delete, crash recovery)

**Files:**
- Modify: `src/science_tool/graph/aggregate_retire.py` (add `RetirementReport` + `apply_retirement` + helpers)
- Test: `tests/graph/test_aggregate_retire_apply.py` (new)

- [ ] **Step 1: Write the failing test**

Create `tests/graph/test_aggregate_retire_apply.py`:

```python
from __future__ import annotations

from pathlib import Path

import yaml

from science_tool.graph.aggregate_retire import apply_retirement, plan_retirement
from science_tool.graph.aggregate_triage import classify_aggregate_rows
from science_tool.graph.sources import load_project_sources

_MANIFEST = "name: demo\nprofile: research\nprofiles: {local: local}\nlayout_version: 3\n"
_AGG_REL = "knowledge/sources/local/entities.yaml"


def _write_entities(root: Path, entries: list[dict]) -> None:
    (root / "science.yaml").write_text(_MANIFEST, encoding="utf-8")
    agg = root / "knowledge" / "sources" / "local"
    agg.mkdir(parents=True, exist_ok=True)
    (agg / "entities.yaml").write_text(yaml.safe_dump({"entities": entries}), encoding="utf-8")


def _concept(cid: str, title: str = "x") -> dict:
    return {"canonical_id": cid, "kind": "concept", "title": title, "source_path": _AGG_REL}


def _cruft(cid: str) -> dict:
    return {"canonical_id": cid, "kind": "concept", "title": "x", "source_path": "migration:audit"}


def _entities_on_disk(root: Path) -> list[str]:
    data = yaml.safe_load((root / _AGG_REL).read_text(encoding="utf-8")) or {}
    return [e["canonical_id"] for e in data.get("entities") or []]


def _run(root: Path, *, dry_run: bool, **flags):
    sources = load_project_sources(root, include_commons=False, strict_core_schema=False, strict_identity=False)
    plan = plan_retirement(root, sources, classify_aggregate_rows(sources), **flags)
    return apply_retirement(root, plan, dry_run=dry_run)


def test_promote_writes_owner_preserving_id_and_drops_entry(tmp_path: Path) -> None:
    _write_entities(tmp_path, [_concept("concept:1q-gain", "Chromosome 1q gain"), _concept("concept:age", "Age")])
    report = _run(tmp_path, dry_run=False, promote_coined=True, delete_cruft=False, delete_shadow=False)
    assert set(report.promoted) == {"concept:1q-gain", "concept:age"}
    owner = tmp_path / "entities/concepts/1q-gain.md"
    assert owner.exists()
    fm = yaml.safe_load(owner.read_text(encoding="utf-8").split("---")[1])
    assert fm["id"] == "concept:1q-gain"
    assert fm["type"] == "concept"
    assert fm["title"] == "Chromosome 1q gain"
    assert fm["promoted_from"] == _AGG_REL
    assert _entities_on_disk(tmp_path) == []  # both promoted out


def test_delete_cruft_removes_entry_no_owner(tmp_path: Path) -> None:
    _write_entities(tmp_path, [_concept("concept:keep"), _cruft("concept:drop")])
    report = _run(tmp_path, dry_run=False, promote_coined=False, delete_cruft=True, delete_shadow=False)
    assert report.deleted == ("concept:drop",)
    assert _entities_on_disk(tmp_path) == ["concept:keep"]
    assert not (tmp_path / "entities/concepts/drop.md").exists()  # delete never writes an owner


def test_dry_run_writes_nothing(tmp_path: Path) -> None:
    _write_entities(tmp_path, [_concept("concept:1q-gain")])
    report = _run(tmp_path, dry_run=True, promote_coined=True, delete_cruft=False, delete_shadow=False)
    assert report.dry_run is True
    assert report.promoted == ("concept:1q-gain",)
    assert not (tmp_path / "entities/concepts/1q-gain.md").exists()
    assert _entities_on_disk(tmp_path) == ["concept:1q-gain"]


def test_missing_title_is_rejected_entry_retained(tmp_path: Path) -> None:
    _write_entities(tmp_path, [{"canonical_id": "concept:no-title", "kind": "concept", "source_path": _AGG_REL}])
    report = _run(tmp_path, dry_run=False, promote_coined=True, delete_cruft=False, delete_shadow=False)
    assert report.promoted == ()
    assert any(cid == "concept:no-title" for cid, _ in report.rejected)
    assert _entities_on_disk(tmp_path) == ["concept:no-title"]


def test_foreign_real_owner_is_left_as_shadow(tmp_path: Path) -> None:
    # A concept stub shadowed by a real, hand-authored owner (NO promoted_from marker).
    # At load it classifies `shadow`, so promote_coined routes it to the reconcile path,
    # where the missing marker means: do not delete the stub, do not touch the owner.
    # (It stays as shadow debt for `--delete-shadow` / human review.)
    _write_entities(tmp_path, [_concept("concept:1q-gain")])
    owner = tmp_path / "entities/concepts/1q-gain.md"
    owner.parent.mkdir(parents=True, exist_ok=True)
    owner.write_text("---\nid: concept:1q-gain\ntype: concept\ntitle: Hand authored\n---\nReal content.\n", "utf-8")
    report = _run(tmp_path, dry_run=False, promote_coined=True, delete_cruft=False, delete_shadow=False)
    assert "concept:1q-gain" not in report.promoted
    assert "Real content." in owner.read_text(encoding="utf-8")  # owner untouched
    assert _entities_on_disk(tmp_path) == ["concept:1q-gain"]  # stub retained, not clobbered


def test_idempotent_second_run_is_noop(tmp_path: Path) -> None:
    _write_entities(tmp_path, [_concept("concept:1q-gain")])
    _run(tmp_path, dry_run=False, promote_coined=True, delete_cruft=False, delete_shadow=False)
    report2 = _run(tmp_path, dry_run=False, promote_coined=True, delete_cruft=False, delete_shadow=False)
    assert report2.promoted == ()
    assert report2.deleted == ()


def test_crash_recovery_completes_stranded_promotion(tmp_path: Path) -> None:
    # Simulate a crash AFTER the owner was written (with our marker) but BEFORE the
    # entry was deleted. A single --promote-coined rerun must delete the stranded entry.
    _write_entities(tmp_path, [_concept("concept:1q-gain")])
    owner = tmp_path / "entities/concepts/1q-gain.md"
    owner.parent.mkdir(parents=True, exist_ok=True)
    owner.write_text(
        f"---\nid: concept:1q-gain\ntype: concept\ntitle: x\npromoted_from: {_AGG_REL}\n---\n\nstub\n", "utf-8"
    )
    report = _run(tmp_path, dry_run=False, promote_coined=True, delete_cruft=False, delete_shadow=False)
    assert "concept:1q-gain" in report.promoted
    assert _entities_on_disk(tmp_path) == []  # stranded entry now removed
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/graph/test_aggregate_retire_apply.py -v`
Expected: FAIL — `ImportError: cannot import name 'apply_retirement'`.

- [ ] **Step 3: Add the report type and executor to `aggregate_retire.py`**

Append to `src/science_tool/graph/aggregate_retire.py`:

```python
@dataclass(frozen=True, slots=True)
class RetirementReport:
    promoted: tuple[str, ...]
    deleted: tuple[str, ...]
    rejected: tuple[tuple[str, str], ...]
    skipped: tuple[tuple[str, str], ...]
    files_rewritten: tuple[str, ...]
    dry_run: bool


_STUB_BODY = "<!-- promoted from entities.yaml by substrate-3b; add definition -->\n"
_REQUIRED_FIELDS = ("canonical_id", "kind", "title")


def _read_entries(project_root: Path, rel: str) -> list[dict]:
    data = yaml.safe_load((project_root / rel).read_text(encoding="utf-8")) or {}
    return data.get("entities") or []


def _front_matter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---", 4)
    if end == -1:
        return {}
    return yaml.safe_load(text[4:end]) or {}


def _owner_text(entry: dict, *, promoted_from: str) -> str:
    fm: dict[str, object] = {"id": entry["canonical_id"], "type": entry["kind"], "title": entry["title"]}
    if entry.get("profile"):
        fm["profile"] = entry["profile"]
    fm["promoted_from"] = promoted_from
    return "---\n" + yaml.safe_dump(fm, sort_keys=False, allow_unicode=True) + "---\n\n" + _STUB_BODY


def _rewrite_aggregate(project_root: Path, rel: str, drop: set[int]) -> None:
    path = project_root / rel
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    items = data.get("entities") or []
    data["entities"] = [row for i, row in enumerate(items) if i not in drop]
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")


def apply_retirement(project_root: Path, plan: RetirementPlan, *, dry_run: bool) -> RetirementReport:
    promoted: list[str] = []
    deleted: list[str] = []
    rejected: list[tuple[str, str]] = [(t.canonical_id, reason) for t, reason in plan.rejected]
    skipped: list[tuple[str, str]] = []
    drop_by_file: dict[str, set[int]] = defaultdict(set)
    entries_cache: dict[str, list[dict]] = {}

    def entries(rel: str) -> list[dict]:
        if rel not in entries_cache:
            entries_cache[rel] = _read_entries(project_root, rel)
        return entries_cache[rel]

    # 1. Promote / reconcile-on-existing-marker.
    for pr in plan.promote:
        entry = entries(pr.source_path)[pr.line]
        missing = next((f for f in _REQUIRED_FIELDS if not entry.get(f)), None)
        if missing is not None:
            rejected.append((pr.triage.canonical_id, f"missing required field {missing}"))
            continue
        assert pr.target_path is not None
        target = project_root / pr.target_path
        if target.exists():
            if _front_matter(target).get("promoted_from") == pr.source_path:
                # Prior interrupted run wrote it; complete the half-done promote.
                promoted.append(pr.triage.canonical_id)
                drop_by_file[pr.source_path].add(pr.line)
            else:
                skipped.append((pr.triage.canonical_id, "target exists (foreign owner)"))
            continue
        if not dry_run:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(_owner_text(entry, promoted_from=pr.source_path), encoding="utf-8")
        promoted.append(pr.triage.canonical_id)
        drop_by_file[pr.source_path].add(pr.line)

    # 2. Crash-recovery sweep (promote_coined only): a shadow whose owner bears OUR
    #    marker is a completed prior promotion — delete the stranded entry.
    for pr in plan.reconcile:
        assert pr.target_path is not None  # the existing owner file path
        owner = project_root / pr.target_path
        if owner.exists() and _front_matter(owner).get("promoted_from") == pr.source_path:
            if pr.triage.canonical_id not in promoted:
                promoted.append(pr.triage.canonical_id)
            drop_by_file[pr.source_path].add(pr.line)

    # 3. Deletes.
    for pr in plan.delete:
        deleted.append(pr.triage.canonical_id)
        drop_by_file[pr.source_path].add(pr.line)

    # 4. Rewrite each affected aggregate file once.
    files_rewritten = sorted(drop_by_file)
    if not dry_run:
        for rel in files_rewritten:
            _rewrite_aggregate(project_root, rel, drop_by_file[rel])

    return RetirementReport(
        tuple(promoted),
        tuple(deleted),
        tuple(rejected),
        tuple(skipped),
        tuple(files_rewritten),
        dry_run,
    )
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/graph/test_aggregate_retire_apply.py -v`
Expected: PASS (7 tests).

- [ ] **Step 5: Lint + commit**

```bash
cd ~/d/science/science && uv run --frozen ruff check src/science_tool/graph/aggregate_retire.py tests/graph/test_aggregate_retire_apply.py && uv run --frozen ruff format src/science_tool/graph/aggregate_retire.py tests/graph/test_aggregate_retire_apply.py
cd ~/d/science && git add science/src/science_tool/graph/aggregate_retire.py science/tests/graph/test_aggregate_retire_apply.py
git commit -m "feat(substrate-3b): entities.yaml retirement executor + crash recovery (§3.5)"
```

---

## Task 5: CLI `--apply` + per-bucket flags + `layout_version` gate

**Files:**
- Modify: `src/science_tool/cli.py` (extend `entities_triage_aggregate_command`, add `_read_layout_version`)
- Test: `tests/test_cli_entities_triage_aggregate.py` (extend the 3a file)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_cli_entities_triage_aggregate.py`:

```python
def _write_v3(root: Path, entries: list[dict]) -> None:
    (root / "science.yaml").write_text(
        "name: demo\nprofile: research\nprofiles: {local: local}\nlayout_version: 3\n", encoding="utf-8"
    )
    agg = root / "knowledge" / "sources" / "local"
    agg.mkdir(parents=True, exist_ok=True)
    (agg / "entities.yaml").write_text(yaml.safe_dump({"entities": entries}), encoding="utf-8")


def test_bucket_flag_alone_is_dry_run_plan(tmp_path: Path) -> None:
    _write_v3(tmp_path, [{"canonical_id": "concept:1q-gain", "kind": "concept", "title": "x",
                          "source_path": "knowledge/sources/local/entities.yaml"}])
    result = CliRunner().invoke(
        main, ["entities", "triage-aggregate", "--project-root", str(tmp_path), "--promote-coined", "--format", "json"]
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["dry_run"] is True
    assert payload["promoted"] == ["concept:1q-gain"]
    assert not (tmp_path / "entities/concepts/1q-gain.md").exists()  # dry-run wrote nothing


def test_apply_executes(tmp_path: Path) -> None:
    _write_v3(tmp_path, [{"canonical_id": "concept:1q-gain", "kind": "concept", "title": "x",
                          "source_path": "knowledge/sources/local/entities.yaml"}])
    result = CliRunner().invoke(
        main, ["entities", "triage-aggregate", "--project-root", str(tmp_path), "--promote-coined", "--apply"]
    )
    assert result.exit_code == 0, result.output
    assert (tmp_path / "entities/concepts/1q-gain.md").exists()


def test_apply_without_bucket_flag_is_usage_error(tmp_path: Path) -> None:
    _write_v3(tmp_path, [])
    result = CliRunner().invoke(main, ["entities", "triage-aggregate", "--project-root", str(tmp_path), "--apply"])
    assert result.exit_code == 2


def test_apply_refused_on_v2(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text(
        "name: demo\nprofile: research\nprofiles: {local: local}\nlayout_version: 2\n", encoding="utf-8"
    )
    agg = tmp_path / "knowledge" / "sources" / "local"
    agg.mkdir(parents=True, exist_ok=True)
    (agg / "entities.yaml").write_text(yaml.safe_dump({"entities": []}), encoding="utf-8")
    result = CliRunner().invoke(
        main, ["entities", "triage-aggregate", "--project-root", str(tmp_path), "--delete-cruft", "--apply"]
    )
    assert result.exit_code == 1
    assert "layout_version" in result.output


def test_bare_command_is_unchanged_3a_report(tmp_path: Path) -> None:
    # Regression: no bucket flags, no --apply → the original 3a triage report.
    _write_v3(tmp_path, [{"canonical_id": "concept:coined", "kind": "concept", "title": "x",
                          "source_path": "knowledge/sources/local/entities.yaml"}])
    result = CliRunner().invoke(
        main, ["entities", "triage-aggregate", "--project-root", str(tmp_path), "--format", "json"]
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert isinstance(payload, list)  # 3a report is a list of rows, not a report object
    assert payload[0]["bucket"] == "coined"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_cli_entities_triage_aggregate.py -v`
Expected: FAIL — `no such option: --promote-coined`.

- [ ] **Step 3: Extend the CLI command**

In `src/science_tool/cli.py`, replace the `triage-aggregate` command (lines 288-329) with this extended version (the module already imports `json`, `click`, `Path`; `yaml` is imported locally inside `_read_layout_version`):

```python
def _read_layout_version(project_root: Path) -> int | None:
    """layout_version straight from science.yaml (`_read_project_config` drops it)."""
    import yaml

    manifest = yaml.safe_load((project_root / "science.yaml").read_text(encoding="utf-8")) or {}
    value = manifest.get("layout_version")
    return value if isinstance(value, int) else None


@entities_group.command("triage-aggregate")
@click.option(
    "--project-root",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=Path("."),
    help="Project root (default: current directory).",
)
@click.option("--format", "output_format", type=click.Choice(["text", "json"]), default="text")
@click.option("--promote-coined", is_flag=True, help="Promote `coined` rows to owner files.")
@click.option("--delete-cruft", is_flag=True, help="Delete `cruft` (migration:*) rows.")
@click.option("--delete-shadow", is_flag=True, help="Delete `shadow` rows (id already has a real owner).")
@click.option("--apply", "apply_changes", is_flag=True, help="Execute the plan (default: dry-run).")
def entities_triage_aggregate_command(
    project_root: Path,
    output_format: str,
    promote_coined: bool,
    delete_cruft: bool,
    delete_shadow: bool,
    apply_changes: bool,
) -> None:
    """Triage (and, with bucket flags, retire) aggregate (entities.yaml) rows (§B5)."""
    from collections import Counter

    from science_tool.graph.aggregate_retire import apply_retirement, plan_retirement
    from science_tool.graph.aggregate_triage import classify_aggregate_rows
    from science_tool.graph.sources import load_project_sources

    sources = load_project_sources(
        project_root, include_commons=False, strict_core_schema=False, strict_identity=False
    )
    rows = classify_aggregate_rows(sources)
    any_bucket = promote_coined or delete_cruft or delete_shadow

    # No bucket flags → the unchanged 3a read-only report.
    if not any_bucket:
        if apply_changes:
            raise click.UsageError("--apply requires at least one of --promote-coined/--delete-cruft/--delete-shadow.")
        if output_format == "json":
            click.echo(json.dumps(
                [
                    {
                        "canonical_id": r.canonical_id,
                        "kind": r.kind,
                        "source_path": r.source_path,
                        "has_real_owner": r.has_real_owner,
                        "bucket": r.bucket.value,
                        "evidence": r.evidence,
                    }
                    for r in rows
                ],
                indent=2,
            ))
            return
        counts = Counter(r.bucket.value for r in rows)
        click.echo(f"{len(rows)} aggregate rows:")
        for bucket in sorted(counts):
            click.echo(f"  {bucket}: {counts[bucket]}")
        for r in rows:
            click.echo(f"  [{r.bucket.value}] {r.canonical_id} (kind={r.kind}, source_path={r.source_path}) -- {r.evidence}")
        return

    # Retirement plan/apply path. --apply is v3-gated.
    if apply_changes:
        version = _read_layout_version(project_root)
        if version is None or version < 3:
            raise click.ClickException(
                f"promotion needs an `entities/` owner root; this project is layout_version {version} — "
                "complete the v2->v3 migration (`science entities migrate`) first."
            )

    plan = plan_retirement(
        project_root, sources, rows,
        promote_coined=promote_coined, delete_cruft=delete_cruft, delete_shadow=delete_shadow,
    )
    report = apply_retirement(project_root, plan, dry_run=not apply_changes)
    if output_format == "json":
        click.echo(json.dumps(
            {
                "dry_run": report.dry_run,
                "promoted": list(report.promoted),
                "deleted": list(report.deleted),
                "rejected": [list(p) for p in report.rejected],
                "skipped": [list(p) for p in report.skipped],
                "files_rewritten": list(report.files_rewritten),
            },
            indent=2,
        ))
        return
    head = "PLAN (dry-run)" if report.dry_run else "APPLIED"
    click.echo(f"{head}: {len(report.promoted)} promoted, {len(report.deleted)} deleted, "
               f"{len(report.rejected)} rejected, {len(report.skipped)} skipped")
    for cid in report.promoted:
        click.echo(f"  promote {cid}")
    for cid in report.deleted:
        click.echo(f"  delete  {cid}")
    for cid, reason in (*report.rejected, *report.skipped):
        click.echo(f"  skip    {cid} -- {reason}")
```

Note: `click.ClickException` exits 1 (the v3 gate); `click.UsageError` exits 2 (no bucket flag). Both match the spec's §3.6 exit codes.

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_cli_entities_triage_aggregate.py -v`
Expected: PASS (the 3a tests + the 5 new ones).

- [ ] **Step 5: Lint + commit**

```bash
cd ~/d/science/science && uv run --frozen ruff check src/science_tool/cli.py tests/test_cli_entities_triage_aggregate.py && uv run --frozen ruff format --check tests/test_cli_entities_triage_aggregate.py
cd ~/d/science && git add science/src/science_tool/cli.py science/tests/test_cli_entities_triage_aggregate.py
git commit -m "feat(substrate-3b): triage-aggregate --apply + per-bucket flags + v3 gate (§3.6/§3.7)"
```

---

## Task 6: round-trip integration test

**Files:**
- Test: `tests/graph/test_aggregate_retire_roundtrip.py` (new)

- [ ] **Step 1: Write the test**

Create `tests/graph/test_aggregate_retire_roundtrip.py`:

```python
from __future__ import annotations

from pathlib import Path

import yaml

from science_tool.graph.aggregate_retire import apply_retirement, plan_retirement
from science_tool.graph.aggregate_triage import classify_aggregate_rows
from science_tool.graph.sources import load_project_sources

_MANIFEST = "name: demo\nprofile: research\nprofiles: {local: local}\nlayout_version: 3\n"
_AGG_REL = "knowledge/sources/local/entities.yaml"


def _load(root: Path):
    return load_project_sources(root, include_commons=False, strict_core_schema=False, strict_identity=False)


def test_load_plan_apply_reload_resolves_owner_and_shrinks_file(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text(_MANIFEST, encoding="utf-8")
    agg = tmp_path / "knowledge" / "sources" / "local"
    agg.mkdir(parents=True, exist_ok=True)
    agg.joinpath("entities.yaml").write_text(
        yaml.safe_dump(
            {
                "entities": [
                    {"canonical_id": "concept:1q-gain", "kind": "concept", "title": "Chromosome 1q gain",
                     "source_path": _AGG_REL},
                    {"canonical_id": "concept:cruft", "kind": "concept", "title": "x", "source_path": "migration:audit"},
                ]
            }
        ),
        encoding="utf-8",
    )

    sources = _load(tmp_path)
    plan = plan_retirement(tmp_path, sources, classify_aggregate_rows(sources),
                           promote_coined=True, delete_cruft=True, delete_shadow=False)
    apply_retirement(tmp_path, plan, dry_run=False)

    # Owner file exists and the aggregate file is now empty.
    assert (tmp_path / "entities/concepts/1q-gain.md").exists()
    remaining = yaml.safe_load((tmp_path / _AGG_REL).read_text(encoding="utf-8"))["entities"]
    assert remaining == []

    # Reload: the promoted id is now owned by markdown (adapter != aggregate), and no
    # aggregate triage rows remain for it.
    reloaded = _load(tmp_path)
    owner = next(d for d in reloaded.identity_declarations if d.canonical_id == "concept:1q-gain")
    assert owner.adapter != "aggregate"
    triaged_ids = {t.canonical_id for t in classify_aggregate_rows(reloaded)}
    assert "concept:1q-gain" not in triaged_ids
    assert "concept:cruft" not in triaged_ids
```

- [ ] **Step 2: Run the test**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/graph/test_aggregate_retire_roundtrip.py -v`
Expected: PASS.

- [ ] **Step 3: Full suite + lint + commit**

```bash
cd ~/d/science/science && uv run --frozen pytest -q && uv run --frozen ruff check . && uv run --frozen ruff format --check tests/graph/test_aggregate_retire_roundtrip.py
cd ~/d/science && git add science/tests/graph/test_aggregate_retire_roundtrip.py
git commit -m "test(substrate-3b): load->plan->apply->reload round-trip (§5)"
```

Expected: full suite green. (A pre-existing `ruff format --check` drift in `src/science_tool/commons/datapackage.py` predates this branch — do not touch it; only format-check the files you changed.)

---

## Final verification (after all tasks)

- [ ] **Full suite + lint the whole tree**

Run: `cd ~/d/science/science && uv run --frozen pytest -q && uv run --frozen ruff check .`
Expected: all pass.

- [ ] **Read-only smoke on MM30 (still v2 — must REFUSE apply, must dry-run-plan):**

Run: `cd ~/d/science/science && uv run --frozen science entities triage-aggregate --project-root ~/d/cancer/cancer-types/multiple-myeloma --promote-coined --delete-cruft --format json | head -30`
Expected: a dry-run plan listing ~134 `promoted` (concept/latent) + ~26 `deleted` (cruft) with `dry_run: true`, writing nothing.
Run: `cd ~/d/science/science && uv run --frozen science entities triage-aggregate --project-root ~/d/cancer/cancer-types/multiple-myeloma --promote-coined --apply; echo "exit=$?"`
Expected: refusal mentioning `layout_version` (exit 1) — MM30 is v2; nothing mutated.

---

## Self-review notes (for the executor)

- **Spec coverage:** Task 1 ↔ §3.0 items 1-5,7 (slug strategy + concept policy); Task 2 ↔ §3.0 item 6 (migrator branch crash guard); Task 3 ↔ §3.1 firewall + §3.4 planner (policy target, id-preserving rejects); Task 4 ↔ §3.5 (file-shape I/O, `promoted_from` marker, crash recovery) + §3.3 types + §4 error table + §5 idempotency; Task 5 ↔ §3.6 CLI table + §3.7 layout_version gate; Task 6 ↔ §5 round-trip. The `slug`-strategy regression and the migrator crash are pinned by Task 1/2 tests; the terms.yaml firewall by Task 3's `test_terms_yaml_rows_are_never_planned`.
- **Type consistency:** `PlannedRow(triage, action, source_path, line, target_path)`, `RetirementPlan(promote, delete, reconcile, rejected)`, and `RetirementReport(promoted, deleted, rejected, skipped, files_rewritten, dry_run)` are defined in Task 3/4 and consumed unchanged by Task 5's CLI and Task 6's round-trip. `RetireAction.{PROMOTE,DELETE}` values are used by the planner only; the report keys by `canonical_id` strings. The real symbol names are pinned: `_BUILTIN_MARKDOWN_POLICIES` (not `_CORE_POLICIES`), `generate_entity_id`/`path_for_entity` (not `derive_local_part`), `plan_migration`/`MigrationPlan.moves[i].new_id/new_rel_path`.
- **Non-3b safety:** no task touches `terms.yaml`, the `decision-log` bucket, or any Phase-4 path. `--apply` is v3-gated; MM30 (v2) is only ever dry-run-planned or refused.
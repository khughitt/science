# Project-local kinds in the v2→v3 layout migration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `science_tool`'s v2→v3 entity-layout migration and conformance checks treat project-registered local entity kinds (declared in a project's local knowledge profile) identically to core kinds — numbered `entities/<kind>/NNNN-slug.md` residents — so a project with local kinds can complete a clean v3 migration with a `layout_version` bump.

**Architecture:** The entity-policy layer (`entities.py`) is currently static and core-only. We make four policy accessors and two status accessors **additively project-aware** (optional keyword `project_root`; no-arg behavior unchanged). A new `load_local_entity_policies(project_root)` reads the active local profile manifest and yields `entities/<name>/` numeric policies (with optional per-kind overrides), validating `name == canonical_prefix`. The migrator threads `project_root` into discovery (now incl. `id:`-prefix kind inference), frontmatter synthesis (status no longer crashes on local kinds), planning, and `rewrite_references` (unmapped local-kind refs now block `--apply`). Conformance threads `project_root` so local kinds are checked and flagged when stranded. The cutover markdown adapter needs no change — it already loads any `entities/**.md` by frontmatter `type:`.

**Tech Stack:** Python 3.13, pytest, Pydantic v2, PyYAML, Click, git. Repo root `~/d/science`; library code in `science/`; tests run `cd science && uv run pytest`.

**Design:** `docs/plans/2026-06-05-local-kind-layout-migration-design.md`

**Branch:** `feat/local-kind-layout-migration` (already created in `~/d/science`).

## Scope / non-goals

This plan makes **migration and conformance** local-kind-aware. It deliberately
does **not** touch the interactive entity-creation path:
`generate_entity_id` / `validate_entity_id` (`entities.py:245,284`) and
`create_entity` (`entities.py:459-707`) still call the no-context policy/status
accessors, so `science entities create --kind <local-kind>` remains unsupported
and continues to raise `Unsupported source-authored entity kind`. That is
intentional and sufficient for the goal (migrate an existing project to v3): local
kinds are authored as markdown and relocated by the migrator, not minted through
`create`. Making `create` local-kind-aware is a clean follow-up — it would reuse
the same project-aware accessors built here by threading `project_root` through
those three functions — but it is out of scope and has no task below.

---

## File structure

| File | Responsibility | Change |
|---|---|---|
| `model/src/science_model/profiles/schema.py` | `EntityKind` declares optional layout/status overrides | Modify — add `home`, `strategy`, `default_status`, `statuses` (all `None`-defaulted) |
| `science/src/science_tool/graph/sources.py` | Shared local-profile-name resolver reused by the policy loader | Modify — extract `resolve_local_profile_name(project_root)` from `_read_project_config` |
| `science/src/science_tool/entities.py` | Project-aware policy + status layer; local-policy loader | Modify — `load_local_entity_policies`, `entity_policies`, project-aware `resolve_path_policy` / `markdown_entity_kinds` / `is_markdown_entity_kind` / `local_part_conforms` / `default_status` / `valid_statuses` |
| `science/src/science_tool/entity_layout_migration.py` | Discovery (`id:`-prefix inference), synthesis, planning, rewrite — all project-aware | Modify |
| `science/src/science_tool/validate/checks/entity_conformance.py` | Conformance over `core ∪ local` kinds | Modify |
| `science/tests/test_entity_layout_migration.py` | Migrator unit tests | Modify (extend) |
| `science/tests/test_entities_local_policies.py` | Policy/status loader unit tests | Create |
| `science/tests/test_entity_conformance_local_kinds.py` | Conformance unit tests for local kinds | Create |
| `science/tests/test_migrate_local_kinds_integration.py` | End-to-end migrate with a local kind | Create |
| `docs/entity-layout-migration-guide.md` | User guide | Modify — add "Project-local kinds" subsection |

**Ordering invariant:** Tasks 1–9 are additive and keep the suite green at every commit. The policy layer (Tasks 1–4) lands before its consumers (Tasks 5–9). The integration test (Task 10) only passes once all consumers are wired.

All `pytest`/`ruff` commands below are run from `~/d/science/science` (i.e. `cd ~/d/science/science` first). All `git` commands are run from `~/d/science`.

---

## Task 1: `EntityKind` schema — optional layout/status overrides

**Files:**
- Modify: `model/src/science_model/profiles/schema.py:10-16`
- Test: `science/tests/test_entities_local_policies.py` (create)

- [ ] **Step 1: Write the failing test**

Create `science/tests/test_entities_local_policies.py`:

```python
from __future__ import annotations

from science_model.profiles.schema import EntityKind


def test_entity_kind_accepts_optional_layout_and_status_fields() -> None:
    ek = EntityKind(
        name="design",
        canonical_prefix="design",
        layer="layer/local",
        description="Project-local design spec.",
        home="entities/designs",
        strategy="numeric",
        default_status="active",
        statuses=["active", "superseded"],
    )
    assert ek.home == "entities/designs"
    assert ek.strategy == "numeric"
    assert ek.default_status == "active"
    assert ek.statuses == ["active", "superseded"]


def test_entity_kind_overrides_default_to_none() -> None:
    ek = EntityKind(name="note", canonical_prefix="note", layer="layer/local", description="Note.")
    assert ek.home is None
    assert ek.strategy is None
    assert ek.default_status is None
    assert ek.statuses is None
```

- [ ] **Step 2: Run to verify failure**

Run: `cd ~/d/science/science && uv run pytest tests/test_entities_local_policies.py -k entity_kind -v`
Expected: FAIL — `EntityKind` rejects unknown keyword `home` (or the fields are absent).

- [ ] **Step 3: Implement the schema fields**

In `model/src/science_model/profiles/schema.py`, replace the `EntityKind` class body:

```python
class EntityKind(BaseModel):
    """An entity kind declared by a knowledge profile."""

    name: str
    canonical_prefix: str
    layer: str
    description: str
    entity_class: str | None = None  # "epistemic" | "operational" | "reference"; None defaults to caller's choice
    # Layout/status overrides for project-local markdown kinds (v3 layout). All
    # optional; defaults derive name->entities/<name>/, numeric strategy, "active".
    home: str | None = None
    strategy: str | None = None  # "numeric" | "citekey" | "singleton"
    default_status: str | None = None
    statuses: list[str] | None = None
```

- [ ] **Step 4: Run to verify pass**

Run: `cd ~/d/science/science && uv run pytest tests/test_entities_local_policies.py -k entity_kind -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd ~/d/science
git add model/src/science_model/profiles/schema.py science/tests/test_entities_local_policies.py
git commit -m "feat(profiles): EntityKind optional home/strategy/status overrides"
```

---

## Task 2: Shared local-profile-name resolver in `sources.py`

`_read_project_config` (`graph/sources.py:872`) already normalizes the active local profile name (`knowledge_profiles.local`, legacy `profiles: {local: …}` fallback, `"local"` default). Expose that resolution so the policy loader reuses it instead of re-parsing `science.yaml`.

**Files:**
- Modify: `science/src/science_tool/graph/sources.py` (after `_read_project_config`, ~line 905)
- Test: `science/tests/test_entities_local_policies.py` (extend)

- [ ] **Step 1: Write the failing test**

Append to `science/tests/test_entities_local_policies.py`:

```python
from pathlib import Path

from science_tool.graph.sources import resolve_local_profile_name


def _write(root: Path, rel: str, text: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def test_resolve_local_profile_name_knowledge_profiles(tmp_path: Path) -> None:
    _write(tmp_path, "science.yaml", "name: t\nknowledge_profiles:\n  local: mm30-local\n")
    assert resolve_local_profile_name(tmp_path) == "mm30-local"


def test_resolve_local_profile_name_legacy_profiles(tmp_path: Path) -> None:
    _write(tmp_path, "science.yaml", "name: t\nprofiles:\n  local: legacy-local\n")
    assert resolve_local_profile_name(tmp_path) == "legacy-local"


def test_resolve_local_profile_name_defaults_to_local(tmp_path: Path) -> None:
    _write(tmp_path, "science.yaml", "name: t\n")
    assert resolve_local_profile_name(tmp_path) == "local"
```

- [ ] **Step 2: Run to verify failure**

Run: `cd ~/d/science/science && uv run pytest tests/test_entities_local_policies.py -k resolve_local_profile -v`
Expected: FAIL — `cannot import name 'resolve_local_profile_name'`.

- [ ] **Step 3: Implement the resolver**

In `science/src/science_tool/graph/sources.py`, add immediately after `_read_project_config`:

```python
def resolve_local_profile_name(project_root: Path) -> str:
    """The active local knowledge-profile name for a project.

    Reuses `_read_project_config`'s normalization: prefers
    `knowledge_profiles.local`, falls back to legacy `profiles: {local: …}`, and
    defaults to "local".
    """
    return str(_read_project_config(project_root)["knowledge_profiles"]["local"])
```

- [ ] **Step 4: Run to verify pass**

Run: `cd ~/d/science/science && uv run pytest tests/test_entities_local_policies.py -k resolve_local_profile -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd ~/d/science
git add science/src/science_tool/graph/sources.py science/tests/test_entities_local_policies.py
git commit -m "feat(sources): expose resolve_local_profile_name for reuse"
```

---

## Task 3: Project-aware policy layer in `entities.py`

Add the local-policy loader and make the four path accessors project-aware. `entities.py` already imports from `science_tool.graph.sources` at module top (line 17), so adding `local_profile_sources_dir` / `resolve_local_profile_name` imports introduces no new cycle.

**Files:**
- Modify: `science/src/science_tool/entities.py:14-17` (imports), `:167-190` (accessors)
- Test: `science/tests/test_entities_local_policies.py` (extend)

- [ ] **Step 1: Write the failing test**

Append to `science/tests/test_entities_local_policies.py`:

```python
import pytest

from science_tool.entities import (
    EntityCommandError,
    EntityPathPolicy,
    is_markdown_entity_kind,
    load_local_entity_policies,
    markdown_entity_kinds,
    resolve_path_policy,
)

_LOCAL_MANIFEST = """\
name: t-local
imports:
  - core
strictness: typed-extension
entity_kinds:
  - name: design
    canonical_prefix: design
    layer: layer/local
    description: Design.
  - name: gadget
    canonical_prefix: gadget
    layer: layer/local
    description: Gadget.
    home: entities/gizmos
relation_kinds: []
"""


def _project_with_local_kinds(tmp_path: Path) -> Path:
    _write(tmp_path, "science.yaml", "name: t\nknowledge_profiles:\n  local: local\n")
    _write(tmp_path, "knowledge/sources/local/manifest.yaml", _LOCAL_MANIFEST)
    return tmp_path


def test_load_local_entity_policies_derives_verbatim_home(tmp_path: Path) -> None:
    root = _project_with_local_kinds(tmp_path)
    policies = load_local_entity_policies(root)
    assert policies["design"] == EntityPathPolicy(Path("entities/design"), "numeric")
    # home override honored:
    assert policies["gadget"] == EntityPathPolicy(Path("entities/gizmos"), "numeric")


def test_resolve_path_policy_is_project_aware(tmp_path: Path) -> None:
    root = _project_with_local_kinds(tmp_path)
    # core kind, no project context — unchanged:
    assert resolve_path_policy("hypothesis").root == Path("entities/hypotheses")
    # local kind requires project_root:
    assert resolve_path_policy("design", project_root=root).root == Path("entities/design")
    with pytest.raises(EntityCommandError):
        resolve_path_policy("design")  # no project_root → still unsupported


def test_markdown_kinds_and_membership_are_project_aware(tmp_path: Path) -> None:
    root = _project_with_local_kinds(tmp_path)
    assert "design" not in markdown_entity_kinds()
    assert "design" in markdown_entity_kinds(project_root=root)
    assert not is_markdown_entity_kind("design")
    assert is_markdown_entity_kind("design", project_root=root)


def test_local_kind_may_not_shadow_core(tmp_path: Path) -> None:
    manifest = _LOCAL_MANIFEST.replace("name: design", "name: hypothesis").replace(
        "canonical_prefix: design", "canonical_prefix: hypothesis"
    )
    _write(tmp_path, "science.yaml", "name: t\nknowledge_profiles:\n  local: local\n")
    _write(tmp_path, "knowledge/sources/local/manifest.yaml", manifest)
    policies = load_local_entity_policies(tmp_path)
    assert "hypothesis" not in policies  # core wins; local shadow dropped


def test_name_must_equal_canonical_prefix(tmp_path: Path) -> None:
    manifest = _LOCAL_MANIFEST.replace("canonical_prefix: design", "canonical_prefix: dsgn")
    _write(tmp_path, "science.yaml", "name: t\nknowledge_profiles:\n  local: local\n")
    _write(tmp_path, "knowledge/sources/local/manifest.yaml", manifest)
    with pytest.raises(EntityCommandError):
        load_local_entity_policies(tmp_path)


@pytest.mark.parametrize(
    "bad_home",
    [
        "/abs/entities/design",   # absolute path
        "../outside/design",      # parent traversal
        "doc/design",             # not under entities/
        "entities/../escape",     # traversal after entities/
    ],
)
def test_home_override_must_be_relative_under_entities(tmp_path: Path, bad_home: str) -> None:
    manifest = _LOCAL_MANIFEST.replace("    home: entities/gizmos\n", f"    home: {bad_home}\n")
    _write(tmp_path, "science.yaml", "name: t\nknowledge_profiles:\n  local: local\n")
    _write(tmp_path, "knowledge/sources/local/manifest.yaml", manifest)
    with pytest.raises(EntityCommandError):
        load_local_entity_policies(tmp_path)


def test_strategy_override_must_be_known(tmp_path: Path) -> None:
    manifest = _LOCAL_MANIFEST.replace(
        "    home: entities/gizmos\n", "    home: entities/gizmos\n    strategy: banana\n"
    )
    _write(tmp_path, "science.yaml", "name: t\nknowledge_profiles:\n  local: local\n")
    _write(tmp_path, "knowledge/sources/local/manifest.yaml", manifest)
    with pytest.raises(EntityCommandError):
        load_local_entity_policies(tmp_path)


def test_strategy_override_accepts_known_values(tmp_path: Path) -> None:
    manifest = _LOCAL_MANIFEST.replace(
        "    home: entities/gizmos\n", "    home: entities/gizmos\n    strategy: citekey\n"
    )
    _write(tmp_path, "science.yaml", "name: t\nknowledge_profiles:\n  local: local\n")
    _write(tmp_path, "knowledge/sources/local/manifest.yaml", manifest)
    policies = load_local_entity_policies(tmp_path)
    assert policies["gadget"] == EntityPathPolicy(Path("entities/gizmos"), "citekey")


def test_no_local_profile_is_empty(tmp_path: Path) -> None:
    _write(tmp_path, "science.yaml", "name: t\n")
    assert load_local_entity_policies(tmp_path) == {}
```

- [ ] **Step 2: Run to verify failure**

Run: `cd ~/d/science/science && uv run pytest tests/test_entities_local_policies.py -k "load_local or project_aware or shadow or canonical or no_local" -v`
Expected: FAIL — `cannot import name 'load_local_entity_policies'`.

- [ ] **Step 3: Implement the loader + project-aware accessors**

In `science/src/science_tool/entities.py`, extend the imports near line 14-18:

```python
from science_model.entities import ProjectEntity
from science_model.profiles import load_profile_manifest
from science_tool.graph.migrate import audit_project_sources
from science_tool.graph.sources import (
    load_project_sources,
    local_profile_sources_dir,
    resolve_local_profile_name,
)
from science_tool.graph.storage_adapters.markdown import MarkdownAdapter
```

Add, just below `_BUILTIN_MARKDOWN_POLICIES` (after line 58):

```python
# Cache local-policy reads keyed by (project_root, manifest mtime_ns) so repeated
# resolve_path_policy calls during a migration don't re-parse the manifest, while
# still picking up edits (important for tests that rewrite the manifest).
_LOCAL_POLICY_CACHE: dict[tuple[str, int], dict[str, EntityPathPolicy]] = {}

# Strategies a local kind may declare. Mirrors the core policy strategies.
_VALID_STRATEGIES: frozenset[str] = frozenset({"numeric", "citekey", "singleton"})


def _resolve_local_home(name: str, home: str | None) -> Path:
    """Resolve (and validate) a local kind's home directory.

    Default is ``entities/<name>``. An explicit ``home`` override must be a
    *relative* path rooted at ``entities/`` with no parent traversal — anything
    else (absolute, ``../``, a non-``entities/`` root) is rejected fail-loud, so a
    malformed manifest cannot redirect migration writes outside the entity tree.
    """
    if not home:
        return Path(f"entities/{name}")
    candidate = Path(home)
    parts = candidate.parts
    if candidate.is_absolute() or ".." in parts or not parts or parts[0] != "entities":
        raise EntityCommandError(
            f"local kind {name!r} home {home!r} must be a relative path under 'entities/' "
            "with no parent traversal"
        )
    return candidate


def load_local_entity_policies(project_root: Path) -> dict[str, EntityPathPolicy]:
    """Path policies for the project's registered local markdown kinds.

    Reads the active local profile manifest. Each kind maps to
    ``entities/<name>/`` (numeric) unless the manifest declares ``home``/
    ``strategy`` overrides. Kinds shadowing a core kind are dropped (core wins).
    Validates ``name == canonical_prefix`` (Decision 4), that any ``home`` is a
    relative path under ``entities/``, and that any ``strategy`` is known; raises
    on divergence.
    """
    profile_name = resolve_local_profile_name(project_root)
    manifest_path = local_profile_sources_dir(project_root, local_profile=profile_name) / "manifest.yaml"
    if not manifest_path.is_file():
        return {}
    cache_key = (str(manifest_path), manifest_path.stat().st_mtime_ns)
    cached = _LOCAL_POLICY_CACHE.get(cache_key)
    if cached is not None:
        return cached
    manifest = load_profile_manifest(manifest_path)
    policies: dict[str, EntityPathPolicy] = {}
    if manifest is not None:
        for ek in manifest.entity_kinds:
            if ek.name != ek.canonical_prefix:
                raise EntityCommandError(
                    f"local kind {ek.name!r} has canonical_prefix {ek.canonical_prefix!r}; "
                    "they must be equal (the kind name is the id prefix)"
                )
            if ek.name in _BUILTIN_MARKDOWN_POLICIES:
                continue  # a local kind may not shadow a core kind
            if ek.strategy is not None and ek.strategy not in _VALID_STRATEGIES:
                raise EntityCommandError(
                    f"local kind {ek.name!r} strategy {ek.strategy!r} must be one of "
                    f"{sorted(_VALID_STRATEGIES)}"
                )
            root = _resolve_local_home(ek.name, ek.home)
            strategy: EntityFilenameStrategy = ek.strategy or "numeric"  # type: ignore[assignment]
            policies[ek.name] = EntityPathPolicy(root, strategy)
    _LOCAL_POLICY_CACHE[cache_key] = policies
    return policies


def entity_policies(project_root: Path | None = None) -> dict[str, EntityPathPolicy]:
    """The path-policy table: builtins only, or builtins ∪ local when a project
    root is supplied (builtins always win)."""
    if project_root is None:
        return dict(_BUILTIN_MARKDOWN_POLICIES)
    return {**load_local_entity_policies(project_root), **_BUILTIN_MARKDOWN_POLICIES}
```

Replace the four accessors (`entities.py:167-190`):

```python
def resolve_path_policy(kind: str, *, project_root: Path | None = None) -> EntityPathPolicy:
    try:
        return entity_policies(project_root)[kind]
    except KeyError as exc:
        raise EntityCommandError(f"Unsupported source-authored entity kind: {kind}") from exc


def markdown_entity_kinds(project_root: Path | None = None) -> tuple[str, ...]:
    """All kinds the policy table governs (core, plus local when project-scoped)."""
    return tuple(entity_policies(project_root))


def is_markdown_entity_kind(kind: str, *, project_root: Path | None = None) -> bool:
    return kind in entity_policies(project_root)


def local_part_conforms(kind: str, local_part: str, *, project_root: Path | None = None) -> bool:
    """True iff ``local_part`` matches the kind's filename strategy."""
    strategy = resolve_path_policy(kind, project_root=project_root).strategy
    if strategy == "numeric":
        return bool(_NUMERIC_LOCAL_PART_RE.fullmatch(local_part))
    if strategy == "citekey":
        return bool(_CITEKEY_RE.fullmatch(local_part))
    return False  # singletons have no per-instance local part
```

> `singleton_path` (line 193) calls `resolve_path_policy(kind)` with no project root — unchanged, since both singletons are core kinds.

- [ ] **Step 4: Run to verify pass**

Run: `cd ~/d/science/science && uv run pytest tests/test_entities_local_policies.py -v`
Expected: PASS (all policy tests).

- [ ] **Step 5: Regression — existing callers unaffected**

Run: `cd ~/d/science/science && uv run pytest tests/ -k "entities or conformance or migrat" -q`
Expected: PASS (no-arg callers keep core behavior).

- [ ] **Step 6: Commit**

```bash
cd ~/d/science
git add science/src/science_tool/entities.py science/tests/test_entities_local_policies.py
git commit -m "feat(entities): project-aware path-policy layer for local kinds"
```

---

## Task 4: Project-aware status accessors

`default_status`/`valid_statuses` (`entities.py:138-145`) directly index the builtin dicts and crash on local kinds. Make them project-aware. `valid_statuses` returns `None` to mean "open set" (local kind with no declared vocabulary).

**Files:**
- Modify: `science/src/science_tool/entities.py:138-145`
- Test: `science/tests/test_entities_local_policies.py` (extend)

- [ ] **Step 1: Write the failing test**

Append to `science/tests/test_entities_local_policies.py`:

```python
from science_tool.entities import default_status, valid_statuses


def test_status_accessors_core_unchanged() -> None:
    assert default_status("hypothesis") == "proposed"
    assert "supported" in valid_statuses("hypothesis")


def test_local_kind_status_defaults_open(tmp_path: Path) -> None:
    root = _project_with_local_kinds(tmp_path)
    assert default_status("design", project_root=root) == "active"
    assert valid_statuses("design", project_root=root) is None  # open set


def test_local_kind_status_manifest_override(tmp_path: Path) -> None:
    manifest = _LOCAL_MANIFEST.replace(
        "    description: Design.\n",
        "    description: Design.\n    default_status: draft\n    statuses: [draft, active]\n",
    )
    _write(tmp_path, "science.yaml", "name: t\nknowledge_profiles:\n  local: local\n")
    _write(tmp_path, "knowledge/sources/local/manifest.yaml", manifest)
    assert default_status("design", project_root=tmp_path) == "draft"
    assert valid_statuses("design", project_root=tmp_path) == frozenset({"draft", "active"})


def test_status_unknown_kind_raises() -> None:
    with pytest.raises(KeyError):
        default_status("nonexistent-kind")
```

- [ ] **Step 2: Run to verify failure**

Run: `cd ~/d/science/science && uv run pytest tests/test_entities_local_policies.py -k status -v`
Expected: FAIL — `default_status` takes no `project_root` / `KeyError` on `design`.

- [ ] **Step 3: Implement project-aware status**

Add a private helper near the status dicts in `entities.py` (after line 134) and replace the two accessors (lines 138-145):

```python
def _local_entity_kind(project_root: Path, kind: str):
    """Return the manifest EntityKind for a local kind, or None."""
    profile_name = resolve_local_profile_name(project_root)
    manifest_path = local_profile_sources_dir(project_root, local_profile=profile_name) / "manifest.yaml"
    if not manifest_path.is_file():
        return None
    manifest = load_profile_manifest(manifest_path)
    if manifest is None:
        return None
    return next((ek for ek in manifest.entity_kinds if ek.name == kind), None)


def default_status(kind: str, *, project_root: Path | None = None) -> str:
    """The per-kind default status (e.g. hypothesis → 'proposed')."""
    if kind in _DEFAULT_STATUS:
        return _DEFAULT_STATUS[kind]
    if project_root is not None:
        ek = _local_entity_kind(project_root, kind)
        if ek is not None:
            return ek.default_status or "active"
    raise KeyError(kind)


def valid_statuses(kind: str, *, project_root: Path | None = None) -> frozenset[str] | None:
    """The controlled status set for `kind`, or None for a local kind with no
    declared vocabulary (an open set — any status accepted)."""
    if kind in _STATUS_VALUES:
        return _STATUS_VALUES[kind]
    if project_root is not None:
        ek = _local_entity_kind(project_root, kind)
        if ek is not None:
            return frozenset(ek.statuses) if ek.statuses else None
    raise KeyError(kind)
```

> `_local_entity_kind` re-reads the (tiny) manifest. `load_profile_manifest` is cheap; this is called only during frontmatter synthesis. If profiling later shows it hot, memoize like `_LOCAL_POLICY_CACHE`.

- [ ] **Step 4: Run to verify pass**

Run: `cd ~/d/science/science && uv run pytest tests/test_entities_local_policies.py -k status -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd ~/d/science
git add science/src/science_tool/entities.py science/tests/test_entities_local_policies.py
git commit -m "feat(entities): project-aware status accessors for local kinds"
```

---

## Task 5: Migrator discovery — `id:`-prefix inference + local kinds

**Files:**
- Modify: `science/src/science_tool/entity_layout_migration.py:61-119` (`discover_legacy_entities`, `_infer_kind`)
- Test: `science/tests/test_entity_layout_migration.py` (extend)

- [ ] **Step 1: Write the failing test**

Append to `science/tests/test_entity_layout_migration.py` (the module already has a `_write` helper; reuse it):

```python
_LOCAL_PROFILE = """\
name: t-local
imports:
  - core
strictness: typed-extension
entity_kinds:
  - name: design
    canonical_prefix: design
    layer: layer/local
    description: Design.
relation_kinds: []
"""


def _with_local_profile(root) -> None:
    _write(root, "science.yaml", "name: t\nknowledge_profiles:\n  local: local\n")
    _write(root, "knowledge/sources/local/manifest.yaml", _LOCAL_PROFILE)


def test_discovers_local_kind_by_type(tmp_path) -> None:
    _with_local_profile(tmp_path)
    _write(tmp_path, "doc/design/x.md",
           '---\nid: "design:x"\ntype: design\ncreated: "2026-01-01"\n---\nbody\n')
    found = {e.rel_path: e for e in discover_legacy_entities(tmp_path)}
    assert found["doc/design/x.md"].kind == "design"


def test_infers_local_kind_from_id_prefix_in_foreign_dir(tmp_path) -> None:
    # No `type:`, file lives under doc/plans/ — dir-name fallback would say "plan".
    # The `id:` prefix (design) must win.
    _with_local_profile(tmp_path)
    _write(tmp_path, "doc/plans/y.md",
           '---\nid: "design:y"\ncreated: "2026-01-01"\n---\nbody\n')
    found = {e.rel_path: e for e in discover_legacy_entities(tmp_path)}
    assert found["doc/plans/y.md"].kind == "design"


def test_explicit_type_wins_over_divergent_id_prefix(tmp_path) -> None:
    _with_local_profile(tmp_path)
    _write(tmp_path, "doc/plans/z.md",
           '---\nid: "design:z"\ntype: plan\ncreated: "2026-01-01"\n---\nbody\n')
    found = {e.rel_path: e for e in discover_legacy_entities(tmp_path)}
    assert found["doc/plans/z.md"].kind == "plan"
```

- [ ] **Step 2: Run to verify failure**

Run: `cd ~/d/science/science && uv run pytest tests/test_entity_layout_migration.py -k "local_kind or id_prefix or divergent" -v`
Expected: FAIL — local-kind files are skipped (core-only `is_markdown_entity_kind`), and id-prefix inference is absent.

- [ ] **Step 3: Implement project-aware discovery**

In `entity_layout_migration.py`, replace `_infer_kind` (lines 96-106) with a project-aware version that adds the `id:`-prefix step, and update `discover_legacy_entities` (lines 61-83) to pass project context:

```python
def _infer_kind(
    rel_path: str,
    frontmatter: dict | None,
    *,
    known_kinds: set[str],
    dir_to_kind: dict[str, str],
) -> str | None:
    if frontmatter is not None:
        value = frontmatter.get("type") or frontmatter.get("kind")
        if isinstance(value, str) and value:
            return value  # explicit type wins
        raw_id = frontmatter.get("id")
        if isinstance(raw_id, str) and ":" in raw_id:
            prefix = raw_id.split(":", 1)[0]
            if prefix in known_kinds:
                return prefix  # id-prefix beats directory name for foreign-dir files
    if rel_path in _PATH_KIND_OVERRIDES:
        return _PATH_KIND_OVERRIDES[rel_path]
    parent = Path(rel_path).parent.name
    return dir_to_kind.get(parent)


def _project_dir_to_kind(project_root: Path) -> dict[str, str]:
    """Directory-name → kind for core ∪ local non-singleton kinds."""
    mapping = dict(_DIR_TO_KIND)  # core base (module-level constant below)
    for kind, policy in load_local_entity_policies(project_root).items():
        if policy.strategy != "singleton":
            mapping[policy.root.name] = kind
    return mapping
```

Then update `discover_legacy_entities`:

```python
def discover_legacy_entities(project_root: Path) -> list[LegacyEntity]:
    results: list[LegacyEntity] = []
    known = set(markdown_entity_kinds(project_root=project_root))
    dir_to_kind = _project_dir_to_kind(project_root)
    for root_name in _LEGACY_SCAN_ROOTS:
        root = project_root / root_name
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.md")):
            rel = path.relative_to(project_root).as_posix()
            if "templates" in path.parts:
                continue
            text = path.read_text(encoding="utf-8")
            frontmatter, body = _split_frontmatter(text)
            kind = _infer_kind(rel, frontmatter, known_kinds=known, dir_to_kind=dir_to_kind)
            if kind is None or not is_markdown_entity_kind(kind, project_root=project_root):
                continue
            old_id = None
            if frontmatter is not None:
                raw_id = frontmatter.get("id")
                old_id = raw_id if isinstance(raw_id, str) else None
            results.append(
                LegacyEntity(rel_path=rel, kind=kind, old_id=old_id, frontmatter=frontmatter or {}, body=body)
            )
    return results
```

Update imports at the top of `entity_layout_migration.py` to include `load_local_entity_policies` and the project-aware accessors (they share the existing `from science_tool.entities import …` line):

```python
from science_tool.entities import (
    EntityCommandError,
    EntityPathPolicy,
    derive_slug,
    default_status,
    is_markdown_entity_kind,
    load_local_entity_policies,
    local_part_conforms,
    markdown_entity_kinds,
    resolve_path_policy,
    singleton_path,
    valid_statuses,
)
```

(Keep whatever else is already imported there; add the missing names.)

- [ ] **Step 4: Run to verify pass**

Run: `cd ~/d/science/science && uv run pytest tests/test_entity_layout_migration.py -k "local_kind or id_prefix or divergent" -v`
Expected: PASS.

- [ ] **Step 5: Regression**

Run: `cd ~/d/science/science && uv run pytest tests/test_entity_layout_migration.py -q`
Expected: PASS (core discovery still works; `_DIR_TO_KIND` core base unchanged).

- [ ] **Step 6: Commit**

```bash
cd ~/d/science
git add science/src/science_tool/entity_layout_migration.py science/tests/test_entity_layout_migration.py
git commit -m "feat(migrate): discover local kinds + id-prefix kind inference"
```

---

## Task 6: Frontmatter synthesis — project-aware status (no crash on prose local kinds)

**Files:**
- Modify: `science/src/science_tool/entity_layout_migration.py:144-176` (`synthesize_frontmatter`, `ensure_frontmatter`)
- Test: `science/tests/test_entity_layout_migration.py` (extend)

- [ ] **Step 1: Write the failing test**

Append to `science/tests/test_entity_layout_migration.py`:

```python
from science_tool.entity_layout_migration import ensure_frontmatter, synthesize_frontmatter


def test_synthesize_local_kind_prose_status_defaults_active(tmp_path) -> None:
    _with_local_profile(tmp_path)
    body = "# A design\n\n**Date:** 2026-02-02\n\nText.\n"
    fm = synthesize_frontmatter(kind="design", body=body, fallback_created="2026-01-01",
                                project_root=tmp_path)
    assert fm["type"] == "design"
    assert fm["created"] == "2026-02-02"
    assert fm["status"] == "active"   # open-set local kind, no prose status
    assert fm["title"] == "A design"


def test_synthesize_local_kind_keeps_valid_prose_status(tmp_path) -> None:
    _with_local_profile(tmp_path)
    body = "# A design\n\n**Status:** retired\n"
    fm = synthesize_frontmatter(kind="design", body=body, fallback_created="2026-01-01",
                                project_root=tmp_path)
    assert fm["status"] == "retired"  # open set accepts any prose status
```

- [ ] **Step 2: Run to verify failure**

Run: `cd ~/d/science/science && uv run pytest tests/test_entity_layout_migration.py -k synthesize_local -v`
Expected: FAIL — `synthesize_frontmatter` has no `project_root`; `valid_statuses("design")` raises `KeyError`.

- [ ] **Step 3: Implement project-aware synthesis**

Replace `synthesize_frontmatter` and `ensure_frontmatter` (lines 144-176):

```python
def synthesize_frontmatter(
    *, kind: str, body: str, fallback_created: str, project_root: Path | None = None
) -> dict:
    """Build a minimal valid frontmatter dict from prose headers + fallbacks."""
    date_match = _DATE_HEADER_RE.search(body)
    created = date_match.group(1) if date_match else fallback_created
    status_match = _STATUS_HEADER_RE.search(body)
    parsed_status = status_match.group(1).strip() if status_match else ""
    allowed = valid_statuses(kind, project_root=project_root)
    if allowed is None:
        # Open set (local kind, no declared vocabulary): accept any prose status,
        # else the per-kind default.
        status = parsed_status or default_status(kind, project_root=project_root)
    else:
        status = parsed_status if parsed_status in allowed else default_status(kind, project_root=project_root)
    title_match = _H1_RE.search(body)
    title = title_match.group(1).strip() if title_match else f"Untitled {kind}"
    return {
        "type": kind,
        "title": title,
        "status": status,
        "created": created,
        "updated": created,
    }


def ensure_frontmatter(
    entity: "LegacyEntity", *, fallback_created: str, project_root: Path | None = None
) -> dict:
    """Return a complete frontmatter dict, synthesizing missing fields."""
    base = synthesize_frontmatter(
        kind=entity.kind, body=entity.body, fallback_created=fallback_created, project_root=project_root
    )
    base.update({k: v for k, v in entity.frontmatter.items() if v not in (None, "")})
    base["type"] = entity.kind  # canonicalize: type wins over legacy `kind`
    base.pop("kind", None)
    return base
```

- [ ] **Step 4: Run to verify pass**

Run: `cd ~/d/science/science && uv run pytest tests/test_entity_layout_migration.py -k synthesize_local -v`
Expected: PASS.

- [ ] **Step 5: Regression**

Run: `cd ~/d/science/science && uv run pytest tests/test_entity_layout_migration.py -k synthesize -q`
Expected: PASS (core synthesize tests still pass; `project_root=None` preserves old behavior).

- [ ] **Step 6: Commit**

```bash
cd ~/d/science
git add science/src/science_tool/entity_layout_migration.py science/tests/test_entity_layout_migration.py
git commit -m "feat(migrate): project-aware frontmatter status synthesis"
```

---

## Task 7: Planning — number/home local kinds (thread `project_root`)

`plan_migration` (`entity_layout_migration.py:280`) calls `resolve_path_policy`, `local_part_conforms`, and `ensure_frontmatter` without project context. Thread `project_root` through every such call so local kinds get numbered and homed.

**Files:**
- Modify: `science/src/science_tool/entity_layout_migration.py:289-360` (within `plan_migration`)
- Test: `science/tests/test_entity_layout_migration.py` (extend)

- [ ] **Step 1: Write the failing test**

Append to `science/tests/test_entity_layout_migration.py`:

```python
from science_tool.entity_layout_migration import plan_migration


def test_plan_numbers_and_homes_local_kind(tmp_path) -> None:
    _with_local_profile(tmp_path)
    _write(tmp_path, "doc/design/early.md",
           '---\nid: "design:early"\ntype: design\ncreated: "2026-01-01"\ntitle: Early\nstatus: active\n---\nb\n')
    _write(tmp_path, "doc/design/late.md",
           '---\nid: "design:late"\ntype: design\ncreated: "2026-02-01"\ntitle: Late\nstatus: active\n---\nb\n')
    plan = plan_migration(tmp_path)
    by_old = {m.old_id: m for m in plan.moves}
    assert by_old["design:early"].new_id == "design:0001-early"
    assert by_old["design:early"].new_rel_path == "entities/design/0001-early.md"
    assert by_old["design:late"].new_id == "design:0002-late"
    assert plan.id_map["design:early"] == "design:0001-early"
```

- [ ] **Step 2: Run to verify failure**

Run: `cd ~/d/science/science && uv run pytest tests/test_entity_layout_migration.py -k plan_numbers_and_homes_local -v`
Expected: FAIL — `resolve_path_policy("design")` raises `EntityCommandError` inside planning (no `project_root`).

- [ ] **Step 3: Thread `project_root` through `plan_migration`**

In `plan_migration` apply these edits (the only changes are adding `project_root=project_root` to policy/conformance calls and `ensure_frontmatter`):

- Line ~289:
```python
    movable = [e for e in entities if resolve_path_policy(e.kind, project_root=project_root).strategy != "singleton"]
```
- Lines ~292-295:
```python
    normalized: dict[str, dict] = {
        e.rel_path: ensure_frontmatter(e, fallback_created=_fallback_created(e), project_root=project_root)
        for e in movable
    }
```
- Line ~301:
```python
        policy = resolve_path_policy(kind, project_root=project_root)
```
- Line ~330:
```python
            if not is_date_stem and local_part_conforms(kind, stem, project_root=project_root):
```
- Line ~354 (the second `local_part_conforms` call in the final loop):
```python
            if not is_date_stem and local_part_conforms(kind, stem, project_root=project_root):
```

> `_existing_entity_numbers(project_root, policy)` already receives the policy and only globs `policy.root` — no change. `_add_move` is policy-agnostic — no change. `_slug_from_legacy` uses `derive_slug` only — no change.

- [ ] **Step 4: Run to verify pass**

Run: `cd ~/d/science/science && uv run pytest tests/test_entity_layout_migration.py -k plan_numbers_and_homes_local -v`
Expected: PASS.

- [ ] **Step 5: Regression**

Run: `cd ~/d/science/science && uv run pytest tests/test_entity_layout_migration.py -k plan -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
cd ~/d/science
git add science/src/science_tool/entity_layout_migration.py science/tests/test_entity_layout_migration.py
git commit -m "feat(migrate): plan numbering/home for local kinds"
```

---

## Task 8: `rewrite_references` — project-aware unresolved detection

`rewrite_references` (`entity_layout_migration.py:495`) skips non-builtin kinds at line 534, so an **unmapped** local-kind ref (`design:old-slug`) is never flagged and slips the dry-run gate. Make it project-aware and thread `project_root` from `migrate_layout`.

**Files:**
- Modify: `science/src/science_tool/entity_layout_migration.py:495-551` (`rewrite_references`), `:633` (call site)
- Test: `science/tests/test_entity_layout_migration.py` (extend)

- [ ] **Step 1: Write the failing test**

Append to `science/tests/test_entity_layout_migration.py`:

```python
from science_tool.entity_layout_migration import rewrite_references


def test_rewrite_flags_unmapped_local_kind_ref(tmp_path) -> None:
    _with_local_profile(tmp_path)
    id_map = {"design:mapped": "design:0001-mapped"}
    text = "See design:mapped and stale design:old-slug here.\n"
    out, unresolved = rewrite_references(
        text, id_map, policed_kinds={"design"}, project_root=tmp_path
    )
    assert "design:0001-mapped" in out          # mapped ref rewritten
    assert "design:old-slug" in unresolved      # unmapped local-kind ref flagged
```

- [ ] **Step 2: Run to verify failure**

Run: `cd ~/d/science/science && uv run pytest tests/test_entity_layout_migration.py -k rewrite_flags_unmapped_local -v`
Expected: FAIL — `rewrite_references` has no `project_root`; `design:old-slug` is treated as external and not flagged.

- [ ] **Step 3: Make `rewrite_references` project-aware**

Change the signature and the three core-only checks in `rewrite_references`:

```python
def rewrite_references(
    text: str,
    id_map: dict[str, str],
    *,
    policed_kinds: set[str] | None = None,
    project_root: Path | None = None,
) -> tuple[str, list[str]]:
```

In the unresolved-scan loop, replace the policy checks (lines 534-540) with project-aware calls:

```python
        if not is_markdown_entity_kind(kind, project_root=project_root):
            continue  # external prefix / url / kind we do not govern
        if policed_kinds is not None and kind not in policed_kinds:
            continue  # kind not migrated as markdown (e.g. stored in a YAML registry) — out of scope
        if resolve_path_policy(kind, project_root=project_root).strategy == "singleton":
            continue  # singletons carry no per-instance local part
        if local_part_conforms(kind, local, project_root=project_root):
            continue  # already a valid local part for this kind
```

In `migrate_layout`, update the call site (line ~633) to pass `project_root`:

```python
            out, unresolved = rewrite_references(
                text, plan.id_map, policed_kinds=policed_kinds, project_root=project_root
            )
```

- [ ] **Step 4: Run to verify pass**

Run: `cd ~/d/science/science && uv run pytest tests/test_entity_layout_migration.py -k rewrite_flags_unmapped_local -v`
Expected: PASS.

- [ ] **Step 5: Regression**

Run: `cd ~/d/science/science && uv run pytest tests/test_entity_layout_migration.py -k rewrite -q`
Expected: PASS (core rewrite tests unaffected; `project_root=None` preserves old behavior).

- [ ] **Step 6: Commit**

```bash
cd ~/d/science
git add science/src/science_tool/entity_layout_migration.py science/tests/test_entity_layout_migration.py
git commit -m "feat(migrate): flag unmapped local-kind refs in rewrite gate"
```

---

## Task 9: Conformance over `core ∪ local` kinds

`entity_conformance.py` iterates `markdown_entity_kinds()` (core only) and filters stranded files on core-only `is_markdown_entity_kind`. Thread `ctx.project_root`.

**Files:**
- Modify: `science/src/science_tool/validate/checks/entity_conformance.py:51-89`
- Test: `science/tests/test_entity_conformance_local_kinds.py` (create)

- [ ] **Step 1: Write the failing test**

Create `science/tests/test_entity_conformance_local_kinds.py`:

```python
from __future__ import annotations

from pathlib import Path

from science_tool.validate.checks.entity_conformance import (
    check_entity_filename_conformance,
    check_entity_location_coherence,
)
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Severity

_LOCAL_PROFILE = """\
name: t-local
imports:
  - core
strictness: typed-extension
entity_kinds:
  - name: design
    canonical_prefix: design
    layer: layer/local
    description: Design.
relation_kinds: []
"""


def _write(root: Path, rel: str, text: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def _ctx(root: Path) -> ValidateContext:
    return ValidateContext.from_project_root(root, strict=False, verbose=False)


def _seed_profile(root: Path, *, layout_version: int) -> None:
    _write(
        root,
        "science.yaml",
        f"name: t\nlayout_version: {layout_version}\nknowledge_profiles:\n  local: local\n",
    )
    _write(root, "knowledge/sources/local/manifest.yaml", _LOCAL_PROFILE)


def test_local_kind_stranded_in_doc_is_flagged(tmp_path: Path) -> None:
    _seed_profile(tmp_path, layout_version=3)
    _write(tmp_path, "doc/design/x.md", '---\nid: "design:x"\ntype: design\n---\nb\n')
    results = list(check_entity_location_coherence(_ctx(tmp_path)))
    msgs = [r.message for r in results]
    assert any("design entity outside its home" in m for m in msgs)


def test_local_kind_stranded_severity_is_version_gated(tmp_path: Path) -> None:
    # v2 → WARN (transition); v3 → ERROR (cutover). Same stranded file.
    _seed_profile(tmp_path, layout_version=2)
    _write(tmp_path, "doc/design/x.md", '---\nid: "design:x"\ntype: design\n---\nb\n')
    warn = [r for r in check_entity_location_coherence(_ctx(tmp_path)) if "outside its home" in r.message]
    assert warn and all(r.severity is Severity.WARN for r in warn)

    _seed_profile(tmp_path, layout_version=3)
    err = [r for r in check_entity_location_coherence(_ctx(tmp_path)) if "outside its home" in r.message]
    assert err and all(r.severity is Severity.ERROR for r in err)


def test_local_kind_nonconforming_filename_flagged(tmp_path: Path) -> None:
    # A numeric-strategy local kind whose file is not NNNN-slug must be flagged.
    _seed_profile(tmp_path, layout_version=3)
    _write(tmp_path, "entities/design/bad.md",
           '---\nid: "design:bad"\ntype: design\ntitle: Bad\nstatus: active\n'
           'created: "2026-01-01"\nupdated: "2026-01-01"\n---\nb\n')
    msgs = [r.message for r in check_entity_filename_conformance(_ctx(tmp_path))]
    assert any("non-conforming design filename 'bad.md'" in m for m in msgs)


def test_local_kind_conforming_filename_is_clean(tmp_path: Path) -> None:
    _seed_profile(tmp_path, layout_version=3)
    _write(tmp_path, "entities/design/0001-good.md",
           '---\nid: "design:0001-good"\ntype: design\ntitle: Good\nstatus: active\n'
           'created: "2026-01-01"\nupdated: "2026-01-01"\n---\nb\n')
    msgs = [r.message for r in check_entity_filename_conformance(_ctx(tmp_path))]
    assert not any("non-conforming design" in m for m in msgs)
```

> `ValidateContext.from_project_root` loads `science.yaml`; the `layout_version`
> the fixture writes drives `_severity` (WARN at 2, ERROR at 3). The conforming
> `0001-good.md` case proves the check does not false-positive on valid local-kind
> files.

- [ ] **Step 2: Run to verify failure**

Run: `cd ~/d/science/science && uv run pytest tests/test_entity_conformance_local_kinds.py -v`
Expected: FAIL — stranded `design` file is not flagged (core-only `is_markdown_entity_kind`).

- [ ] **Step 3: Thread `project_root` into conformance**

In `entity_conformance.py`, update `_entity_dirs` (line 57) and the stranded scan (line 83):

```python
    for kind in markdown_entity_kinds(ctx.project_root):
        policy = resolve_path_policy(kind, project_root=ctx.project_root)
```

and in `check_entity_location_coherence` part (a), line 83:

```python
            if kind is None or not is_markdown_entity_kind(kind, project_root=ctx.project_root):
                continue  # prose / non-entity markdown is ignored
```

and line 88 (the message's policy lookup):

```python
                f"{kind} entity outside its home; expected under "
                f"{resolve_path_policy(kind, project_root=ctx.project_root).root}/",
```

In part (b) and the other checks (`check_entity_filename_conformance`, `check_entity_number_hygiene`, `check_entity_stray_files`), the directory iteration goes through `_entity_dirs(ctx)` which is now project-aware, and `local_part_conforms(kind, path.stem)` at line 108 must also pass project context:

```python
            if not local_part_conforms(kind, path.stem, project_root=ctx.project_root):
```

- [ ] **Step 4: Run to verify pass**

Run: `cd ~/d/science/science && uv run pytest tests/test_entity_conformance_local_kinds.py -v`
Expected: PASS.

- [ ] **Step 5: Regression**

Run: `cd ~/d/science/science && uv run pytest tests/ -k conformance -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
cd ~/d/science
git add science/src/science_tool/validate/checks/entity_conformance.py science/tests/test_entity_conformance_local_kinds.py
git commit -m "feat(validate): conformance checks cover project-local kinds"
```

---

## Task 10: End-to-end integration — migrate a project with a local kind

**Files:**
- Test: `science/tests/test_migrate_local_kinds_integration.py` (create)

- [ ] **Step 1: Write the integration test**

Create `science/tests/test_migrate_local_kinds_integration.py`:

```python
from __future__ import annotations

import subprocess
from pathlib import Path

import yaml

from science_tool.entity_layout_migration import migrate_layout

_LOCAL_PROFILE = """\
name: t-local
imports:
  - core
strictness: typed-extension
entity_kinds:
  - name: design
    canonical_prefix: design
    layer: layer/local
    description: Design.
relation_kinds: []
"""


def _write(root: Path, rel: str, text: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def _git_init(root: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "seed"],
        cwd=root, check=True,
    )


def test_migrate_applies_local_kind_and_bumps_version(tmp_path: Path) -> None:
    _write(tmp_path, "science.yaml", "name: t\nlayout_version: 2\nknowledge_profiles:\n  local: local\n")
    _write(tmp_path, "knowledge/sources/local/manifest.yaml", _LOCAL_PROFILE)
    # one core kind + one local kind, with a cross-reference core -> local.
    _write(tmp_path, "specs/hypotheses/h01-x.md",
           '---\nid: "hypothesis:h01-x"\ntype: hypothesis\ncreated: "2026-01-01"\n'
           'title: X\nstatus: proposed\nupdated: "2026-01-01"\nrelated: ["design:foo"]\n---\nSee design:foo.\n')
    _write(tmp_path, "doc/design/foo.md",
           '---\nid: "design:foo"\ntype: design\ncreated: "2026-01-02"\n'
           'title: Foo\nstatus: active\nupdated: "2026-01-02"\n---\nbody\n')
    _git_init(tmp_path)

    report = migrate_layout(tmp_path, apply=True)

    assert report["applied"] is True
    assert report.get("graph_validation") == "passed"
    # local-kind file moved + renumbered
    assert (tmp_path / "entities/design/0001-foo.md").is_file()
    assert not (tmp_path / "doc/design/foo.md").exists()
    # core -> local reference rewritten everywhere
    h = (tmp_path / "entities/hypotheses/0001-x.md").read_text()
    assert "design:0001-foo" in h
    assert "design:foo" not in h
    # version bumped
    manifest = yaml.safe_load((tmp_path / "science.yaml").read_text())
    assert manifest["layout_version"] == 3


def test_migrate_blocks_on_unmapped_local_ref(tmp_path: Path) -> None:
    _write(tmp_path, "science.yaml", "name: t\nlayout_version: 2\nknowledge_profiles:\n  local: local\n")
    _write(tmp_path, "knowledge/sources/local/manifest.yaml", _LOCAL_PROFILE)
    _write(tmp_path, "doc/design/foo.md",
           '---\nid: "design:foo"\ntype: design\ncreated: "2026-01-02"\n'
           'title: Foo\nstatus: active\nupdated: "2026-01-02"\n---\nDangling design:ghost.\n')
    _git_init(tmp_path)

    report = migrate_layout(tmp_path, apply=False)
    flat = [t for toks in report["unresolved_references"].values() for t in toks]
    assert "design:ghost" in flat  # dry-run surfaces the unmapped local-kind ref
```

- [ ] **Step 2: Run the integration test**

Run: `cd ~/d/science/science && uv run pytest tests/test_migrate_local_kinds_integration.py -v`
Expected: PASS. If `migrate_layout`'s post-move audit (`load_project_sources`) fails to load the relocated `design` file, capture the error and address it (most likely the synthesized/edited frontmatter must satisfy the local kind's typed-extension schema — see Design "Schema validation on load"; if a required field is missing, that is a real gap to fix here before proceeding).

- [ ] **Step 3: Commit**

```bash
cd ~/d/science
git add science/tests/test_migrate_local_kinds_integration.py
git commit -m "test(migrate): end-to-end local-kind migration + version bump"
```

---

## Task 11: Documentation — migration guide

**Files:**
- Modify: `docs/entity-layout-migration-guide.md` (add a subsection under "What Changes")

- [ ] **Step 1: Add the "Project-local kinds" subsection**

Append after the "What Changes" table in `docs/entity-layout-migration-guide.md`:

```markdown
### Project-local kinds

Kinds registered under `entity_kinds:` in your local knowledge profile
(`knowledge/sources/<profile>/manifest.yaml`) are migrated exactly like core
kinds: each markdown file moves to `entities/<kind>/NNNN-slug.md` with a
zero-padded sequence number, and all references are rewritten. Prose-only files
get synthesized frontmatter (`title` from the first H1, `created` from a
`**Date:**` header, `status` defaulting to `active`).

The kind `name` must equal its `canonical_prefix` (the name is the id prefix and
the directory segment). By default the home is `entities/<name>/` with `numeric`
numbering; override per kind in the manifest with optional `home:` / `strategy:`
fields, and constrain status with `default_status:` / `statuses:`.

Structurally-defined local entities (declared in
`knowledge/sources/<profile>/entities.yaml`, not as markdown files) are not
affected — they load regardless of layout.
```

- [ ] **Step 2: Commit**

```bash
cd ~/d/science
git add docs/entity-layout-migration-guide.md
git commit -m "docs(migrate): document project-local-kind migration"
```

---

## Task 12: Full suite + lint

- [ ] **Step 1: Run the full test suite**

Run: `cd ~/d/science/science && uv run pytest -q`
Expected: PASS (no regressions).

- [ ] **Step 2: Lint / format**

Run: `cd ~/d/science/science && uv run ruff check . && uv run ruff format --check .`
Expected: clean. Fix any findings and re-run.

- [ ] **Step 3: Final commit (if lint required changes)**

`ruff format` only rewrites the files this plan touched. Stage them explicitly —
**never `git add -A`** (the worktree is shared and may hold unrelated changes).
First inspect what changed, then add only the files from this plan that are dirty:

```bash
cd ~/d/science
git status --short   # confirm only this plan's files are modified
git add \
  model/src/science_model/profiles/schema.py \
  science/src/science_tool/entities.py \
  science/src/science_tool/entity_layout_migration.py \
  science/src/science_tool/graph/sources.py \
  science/src/science_tool/validate/checks/entity_conformance.py
git commit -m "chore: lint/format local-kind migration changes"
```

If `git status --short` shows any file *not* in the list above, do not stage it —
investigate first; it is unrelated work that must not ride this commit.

---

## Self-review notes (spec coverage)

- Design "Status policy" → Tasks 1, 4, 6. — covered
- Design "Project-aware policy layer" → Tasks 2, 3. — covered
- Design "Kind inference (`id:` prefix)" → Task 5. — covered
- Design "Migrator threads project context" (plan/rewrite) → Tasks 7, 8. — covered
- Design "rewrite_references project-aware / unmapped blocks apply" → Tasks 8, 10. — covered
- Design "name == canonical_prefix validation" → Task 3. — covered
- Design "home/strategy override validation (fail-loud)" → Task 3. — covered
- Design "entity creation is out of scope" → Scope/non-goals section (no task). — covered
- Design "profile fallback reuse" → Task 2. — covered
- Design "Conformance threads project context" → Task 9. — covered
- Design "Adapter: no change" → no task (intentional). — covered
- Design "Schema additions" → Task 1. — covered
- Design "Edge: schema validation on load" → Task 10 Step 2 (verified by integration). — covered
- Design "Testing strategy" → Tasks 3, 4, 5, 6, 7, 8, 9, 10. — covered
- Design "Documentation" → Task 11. — covered

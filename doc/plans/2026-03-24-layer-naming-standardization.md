# Layer Naming Standardization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename `project_specific` → `local` and `cross-project` → `shared` across all code, tests, commands, docs, and project files.

**Architecture:** Mechanical search-and-replace organized by package. science-model first (profile definitions), then science-tool (consumer code + tests), then commands/docs, then per-project migration with graph rebuild.

**Tech Stack:** Python 3.11+, Pydantic v2, PyYAML, pytest. Project runner: `uv run --frozen`.

**Spec:** `doc/specs/2026-03-24-layer-naming-standardization.md`

---

## File Structure

### Renamed files

```
science-model/src/science_model/profiles/project_specific.py → profiles/local.py
```

### Modified files

```
# science-model
science-model/src/science_model/profiles/__init__.py
science-model/tests/test_profile_manifests.py
science-model/tests/test_profiles.py
science-model/tests/test_source_contracts.py

# science-tool
science-tool/src/science_tool/graph/sources.py
science-tool/src/science_tool/graph/migrate.py
science-tool/src/science_tool/cli.py
science-tool/tests/test_graph_materialize.py
science-tool/tests/test_graph_migrate.py
science-tool/tests/test_validate_script.py
science-tool/tests/test_sync_cli.py
science-tool/tests/test_registry_sync.py
science-tool/scripts/validate.sh

# commands + docs
commands/create-project.md
commands/import-project.md
commands/create-graph.md
commands/update-graph.md
commands/sync.md
docs/project-organization-profiles.md
references/science-yaml-schema.md
README.md

# projects (external)
~/d/seq-feats/science.yaml + knowledge/sources/ rename + source YAML updates
~/d/3d-attention-bias/science.yaml + knowledge/sources/ rename + source YAML updates
~/d/natural-systems/science.yaml + knowledge/sources/ rename + source YAML updates
~/d/cats/science.yaml + knowledge/sources/ rename
```

---

## Task 1: Rename profile in science-model

**Files:**
- Rename: `science-model/src/science_model/profiles/project_specific.py` → `local.py`
- Modify: `science-model/src/science_model/profiles/__init__.py`
- Modify: `science-model/tests/test_profile_manifests.py`
- Modify: `science-model/tests/test_profiles.py`
- Modify: `science-model/tests/test_source_contracts.py`

- [ ] **Step 1: Rename `project_specific.py` → `local.py` and update contents**

Rename file and apply these changes in the new `local.py`:
- `PROJECT_SPECIFIC_PROFILE` → `LOCAL_PROFILE`
- `name="project_specific"` → `name="local"`
- `layer="layer/project_specific/model"` → `layer="layer/local"` (2 occurrences)
- `layer="layer/project_specific/provenance"` → `layer="layer/local"`

Final file content:

```python
"""Formal extension profile for project-local layered knowledge graph semantics."""

from science_model.profiles.schema import EntityKind, ProfileManifest

LOCAL_PROFILE = ProfileManifest(
    name="local",
    imports=["core"],
    entity_kinds=[
        EntityKind(
            name="model",
            canonical_prefix="model",
            layer="layer/local",
            description="Project-local scientific model.",
        ),
        EntityKind(
            name="canonical-parameter",
            canonical_prefix="parameter",
            layer="layer/local",
            description="Project-local canonical model parameter.",
        ),
        EntityKind(
            name="parameter-binding",
            canonical_prefix="binding",
            layer="layer/local",
            description="Provenance node that binds a model to a canonical parameter.",
        ),
    ],
    relation_kinds=[],
    strictness="typed-extension",
)
```

- [ ] **Step 2: Update `profiles/__init__.py`**

```python
"""Shared profile schema and manifest exports."""

from pathlib import Path

import yaml

from science_model.profiles.bio import BIO_PROFILE
from science_model.profiles.core import CORE_PROFILE
from science_model.profiles.local import LOCAL_PROFILE
from science_model.profiles.schema import EntityKind, ProfileManifest, RelationKind

_DEFAULT_MANIFEST_PATH = Path.home() / ".config" / "science" / "registry" / "manifest.yaml"


def load_shared_profile(
    manifest_path: Path = _DEFAULT_MANIFEST_PATH,
) -> ProfileManifest | None:
    """Load the shared cross-project profile from YAML. Returns None if not found."""
    if not manifest_path.is_file():
        return None
    data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return None
    return ProfileManifest.model_validate(data)


__all__ = [
    "BIO_PROFILE",
    "CORE_PROFILE",
    "LOCAL_PROFILE",
    "EntityKind",
    "ProfileManifest",
    "RelationKind",
    "load_shared_profile",
]
```

- [ ] **Step 3: Update tests**

In `test_profile_manifests.py`:
- Change `import PROJECT_SPECIFIC_PROFILE` → `import LOCAL_PROFILE`
- Rename `test_project_specific_profile_is_typed_extension` → `test_local_profile_is_typed_extension`
- Update assertion to use `LOCAL_PROFILE`
- Change `import load_cross_project_profile` → `import load_shared_profile`
- Update `"cross-project"` → `"shared"` and `"layer/cross-project"` → `"layer/shared"` in cross-project profile test
- Update test name and assertion

In `test_profiles.py`:
- Change `name="project_specific"` → `name="local"` in profile name assertion

In `test_source_contracts.py`:
- Replace all `profile="project_specific"` → `profile="local"`
- Replace all `source_path="knowledge/sources/project_specific/` → `source_path="knowledge/sources/local/`

- [ ] **Step 4: Delete old `project_specific.py`**

```bash
rm science-model/src/science_model/profiles/project_specific.py
```

- [ ] **Step 5: Run science-model tests**

Run: `cd science-model && uv run --frozen pytest -v`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add science-model/
git commit -m "refactor(science-model): rename project_specific → local, cross-project → shared"
```

---

## Task 2: Update science-tool code

**Files:**
- Modify: `science-tool/src/science_tool/graph/sources.py`
- Modify: `science-tool/src/science_tool/graph/migrate.py`
- Modify: `science-tool/src/science_tool/cli.py`
- Modify: `science-tool/scripts/validate.sh`

- [ ] **Step 1: Update `sources.py`**

Three changes:
1. Line 67: `local: str = "project_specific"` → `local: str = "local"`
2. Line 104: `if "cross-project" in profiles.curated:` → `if "shared" in profiles.curated:`
3. Line 105: `xp = load_cross_project_profile()` → `xp = load_shared_profile()`
4. Import: `from science_model.profiles import load_cross_project_profile` → `from science_model.profiles import load_shared_profile`
5. Line 460: `"local": str(knowledge_profiles.get("local") or "project_specific"),` → `"local": str(knowledge_profiles.get("local") or "local"),`

- [ ] **Step 2: Update `migrate.py`**

1. Rename function `write_project_specific_sources` → `write_local_sources`
2. Line 354: `return "project_specific"` → `return "local"`

- [ ] **Step 3: Update `cli.py`**

1. Update import: `write_project_specific_sources` → `write_local_sources`
2. Update call site: `write_project_specific_sources(` → `write_local_sources(`

- [ ] **Step 4: Update `scripts/validate.sh`**

Replace all 4 occurrences of `project_specific` with `local`:
- Line 74: `LOCAL_PROFILE="project_specific"` → `LOCAL_PROFILE="local"`
- Lines 102-104: `'project_specific'` → `'local'` (3 occurrences in inline Python)

- [ ] **Step 5: Commit**

```bash
git add science-tool/src/ science-tool/scripts/
git commit -m "refactor(science-tool): rename project_specific → local, cross-project → shared in code"
```

---

## Task 3: Update science-tool tests

**Files:**
- Modify: `science-tool/tests/test_graph_materialize.py`
- Modify: `science-tool/tests/test_graph_migrate.py`
- Modify: `science-tool/tests/test_validate_script.py`
- Modify: `science-tool/tests/test_sync_cli.py`
- Modify: `science-tool/tests/test_registry_sync.py`

- [ ] **Step 1: Global replace in test files**

In all test files, replace:
- `"project_specific"` → `"local"` (string literals in YAML content, profile names, source paths)
- `"knowledge/sources/project_specific/"` → `"knowledge/sources/local/"`
- `project_specific = project / "knowledge" / "sources" / "project_specific"` → `local_sources = project / "knowledge" / "sources" / "local"`
- Variable names `project_specific` → `local_sources` (in test_graph_materialize.py and test_graph_migrate.py)
- `"cross-project"` → `"shared"` in test_graph_materialize.py (cross-project profile test)
- `"layer/cross-project"` → `"layer/shared"` in test_graph_materialize.py
- `write_project_specific_sources` → `write_local_sources` in test_graph_migrate.py imports and calls

- [ ] **Step 2: Run full science-tool test suite**

Run: `cd science-tool && uv run --frozen pytest -v`
Expected: All pass

- [ ] **Step 3: Run ruff**

Run: `cd science-tool && uv run --frozen ruff check . && uv run --frozen ruff format --check .`
Expected: Clean

- [ ] **Step 4: Commit**

```bash
git add science-tool/tests/
git commit -m "refactor(science-tool): rename project_specific → local in tests"
```

---

## Task 4: Update commands and docs

**Files:**
- Modify: `commands/create-project.md`
- Modify: `commands/import-project.md`
- Modify: `commands/create-graph.md`
- Modify: `commands/update-graph.md`
- Modify: `commands/sync.md`
- Modify: `docs/project-organization-profiles.md`
- Modify: `references/science-yaml-schema.md`
- Modify: `README.md`

- [ ] **Step 1: Update commands**

In `create-project.md` and `import-project.md`:
- `local: project_specific` → `local: local`

In `create-graph.md`:
- `local: project_specific` → `local: local`
- `knowledge/sources/project_specific/` → `knowledge/sources/local/`
- `profile: project_specific` → `profile: local`
- `defaults to \`project_specific\`` → `defaults to \`local\``

In `update-graph.md`:
- `project_specific` → `local` in default profile mention

In `sync.md`:
- `cross-project profile` → `shared profile` (line 37 only — keep "cross-project sync" as English prose)

- [ ] **Step 2: Update living docs**

In `docs/project-organization-profiles.md`:
- `project_specific` → `local` throughout

In `references/science-yaml-schema.md`:
- `project_specific` → `local` (lines 29, 76, 100)

In `README.md`:
- `local: project_specific` → `local: local`
- Update prose that says "defaults to `project_specific`" → "defaults to `local`"

- [ ] **Step 3: Commit**

```bash
git add commands/ docs/ references/ README.md
git commit -m "docs: rename project_specific → local, cross-project → shared in commands and docs"
```

---

## Task 5: Migrate user projects

**Projects:** `~/d/seq-feats`, `~/d/3d-attention-bias`, `~/d/natural-systems`, `~/d/cats`

For each project, the steps are identical:

- [ ] **Step 1: Rename source directory**

```bash
for proj in ~/d/seq-feats ~/d/3d-attention-bias ~/d/natural-systems ~/d/cats; do
  if [ -d "$proj/knowledge/sources/project_specific" ]; then
    mv "$proj/knowledge/sources/project_specific" "$proj/knowledge/sources/local"
    echo "Renamed: $proj"
  else
    echo "Skipped (no dir): $proj"
  fi
done
```

- [ ] **Step 2: Update `science.yaml` in each project**

In each project's `science.yaml`, change:
- `local: project_specific` → `local: local`

- [ ] **Step 3: Update internal source YAML references**

For each project that has YAML source files under `knowledge/sources/local/`, update:
- `profile: project_specific` → `profile: local`
- `source_path: knowledge/sources/project_specific/` → `source_path: knowledge/sources/local/`

The main files to update are:
- `knowledge/sources/local/entities.yaml`
- `knowledge/sources/local/models.yaml` (natural-systems)
- `knowledge/sources/local/parameters.yaml` (natural-systems)
- `knowledge/sources/local/bindings.yaml` (natural-systems)

Use search-and-replace within each file:
```bash
for proj in ~/d/seq-feats ~/d/3d-attention-bias ~/d/natural-systems ~/d/cats; do
  for f in "$proj/knowledge/sources/local/"*.yaml; do
    [ -f "$f" ] && sed -i 's/project_specific/local/g' "$f"
  done
done
```

- [ ] **Step 4: Re-materialize graphs**

```bash
for proj in ~/d/seq-feats ~/d/3d-attention-bias ~/d/natural-systems ~/d/cats; do
  echo "Building graph for $(basename $proj)..."
  cd "$proj" && uv run science-tool graph build 2>&1 | tail -1
done
```

If a project's graph build fails (e.g., cats has no graph), that's fine — skip it.

- [ ] **Step 5: Commit in each project**

```bash
for proj in ~/d/seq-feats ~/d/3d-attention-bias ~/d/natural-systems ~/d/cats; do
  cd "$proj"
  git add -A
  if ! git diff --cached --quiet; then
    git commit -m "refactor: rename knowledge profile project_specific → local"
  fi
done
```

---

## Task 6: Final verification

- [ ] **Step 1: Verify no remaining references to old names**

```bash
cd /mnt/ssd/Dropbox/science
rg "project_specific" science-model/ science-tool/src/ science-tool/tests/ commands/ references/ README.md scripts/ --glob '!*.pyc' || echo "Clean"
rg '"cross-project"' science-model/ science-tool/src/ --glob '!*.pyc' || echo "Clean"
```

Expected: No matches (except possibly in historical docs/ plans which are intentionally left).

- [ ] **Step 2: Run full test suites**

```bash
cd science-model && uv run --frozen pytest -v
cd ../science-tool && uv run --frozen pytest -v
```

Expected: All pass

- [ ] **Step 3: Run ruff on both packages**

```bash
cd science-model && uv run --frozen ruff check . && uv run --frozen ruff format --check .
cd ../science-tool && uv run --frozen ruff check . && uv run --frozen ruff format --check .
```

Expected: Clean

- [ ] **Step 4: Final commit if needed**

```bash
git add -A && git diff --cached --quiet || git commit -m "chore: final cleanup for layer naming standardization"
```

# Layer Naming Standardization — Design Spec

**Date:** 2026-03-24
**Status:** Draft

## Problem

The knowledge model layer names are inconsistent: `project_specific` uses
underscores while other names use hyphens; `cross-project` doesn't convey its
role clearly; and there's no naming pattern that distinguishes domain profiles
from structural layers. As domain profiles grow (bio, neuro, chem), a clear
convention is needed.

## Goal

Standardize layer names to: `core`, `domain/<name>` (in layer URIs only),
`shared`, `local`. Rename all references, flatten local sub-layers, and
re-materialize project graphs.

## Naming Convention

| Layer | Profile name | Python constant | Strictness | Layer URI | Source dir | `science.yaml` |
|---|---|---|---|---|---|---|
| Core | `core` | `CORE_PROFILE` | `core` | `layer/core` | (built-in) | (implicit) |
| Domain | `bio` | `BIO_PROFILE` | `curated` | `layer/domain/bio` | `knowledge/sources/bio/` | `curated: [bio]` |
| Shared | `shared` | loaded from YAML | `curated` | `layer/shared` | (registry) | `curated: [shared]` |
| Local | `local` | `LOCAL_PROFILE` | `typed-extension` | `layer/local` | `knowledge/sources/local/` | `local: local` |

**Key decisions:**
- `domain/` prefix only in layer URIs — profile names stay short (`bio`)
- Local sub-layers (`layer/project_specific/model`, `layer/project_specific/provenance`)
  flatten to `layer/local` — entity *kind* distinguishes models from bindings
- `cross-project` → `shared` everywhere

---

## 1. Renames

### `project_specific` → `local`

| What | From | To |
|---|---|---|
| Profile name | `"project_specific"` | `"local"` |
| Python constant | `PROJECT_SPECIFIC_PROFILE` | `LOCAL_PROFILE` |
| Source file | `profiles/project_specific.py` | `profiles/local.py` |
| Layer URIs | `layer/project_specific/model`, `layer/project_specific/provenance` | `layer/local` |
| Default in code | `"project_specific"` fallback | `"local"` fallback |
| Source dirs (projects) | `knowledge/sources/project_specific/` | `knowledge/sources/local/` |
| `science.yaml` | `local: project_specific` | `local: local` |

### `cross-project` → `shared`

| What | From | To |
|---|---|---|
| Profile name | `"cross-project"` | `"shared"` |
| Layer URI | `layer/cross-project` | `layer/shared` |
| Code references | `"cross-project"` string | `"shared"` string |

---

## 2. Affected Files

### science-model

| File | Change |
|---|---|
| `profiles/project_specific.py` → `profiles/local.py` | Rename file, change `name` to `"local"`, flatten layers to `layer/local` |
| `profiles/__init__.py` | Import `LOCAL_PROFILE` from `local`, update `__all__`, change `"cross-project"` → `"shared"` in `load_cross_project_profile` default path |
| `tests/test_profile_manifests.py` | Rename test, update imports, update `"cross-project"` → `"shared"` in cross-project profile tests |
| `tests/test_profiles.py` | Update profile name assertion |
| `tests/test_source_contracts.py` | Update `profile` and `source_path` strings |

### science-tool

| File | Change |
|---|---|
| `graph/sources.py` | Change default `"project_specific"` → `"local"`, change `"cross-project"` → `"shared"` |
| `graph/migrate.py` | Rename `write_project_specific_sources` → `write_local_sources`, update default profile |
| `cli.py` | Update import and call to renamed migrate function |
| `registry/propagation.py` | Update `"cross-project"` tag check to remain as-is (the *tag* on entities is `cross-project`, which is a user-facing label, not a profile name — keep it) |
| `registry/sync.py` | Update `"cross-project"` → `"shared"` if used as profile name |
| Tests (6+ files) | Update `project_specific` → `local` in all test helpers and assertions |

### Commands

| File | Change |
|---|---|
| `create-project.md` | `local: project_specific` → `local: local` |
| `import-project.md` | Same |
| `create-graph.md` | Update profile references and source dir examples |
| `update-graph.md` | Update default profile mention |

### Projects (4 projects)

For each of `seq-feats`, `3d-attention-bias`, `natural-systems`, `cats`:
1. `science.yaml`: `local: project_specific` → `local: local`
2. Rename `knowledge/sources/project_specific/` → `knowledge/sources/local/`
3. Update any internal `profile:` or `source_path:` references in YAML source
   files (e.g., `profile: project_specific` → `profile: local`,
   `source_path: knowledge/sources/project_specific/...` →
   `source_path: knowledge/sources/local/...`)
4. Run `science-tool graph build` to re-materialize

### Docs

Planning docs in `docs/plans/` are historical and should **not** be updated —
they describe what was true at the time. Only update living documentation:
- `docs/project-organization-profiles.md`

---

## 3. Tag vs Profile Name Distinction

The `cross-project` string appears in two contexts:
1. **Profile name** (`"cross-project"` in code) → rename to `"shared"`
2. **Entity tag** (`tags: [cross-project]` in frontmatter) → **keep as-is**

The tag `cross-project` is a user-facing label on entities meaning "this entity
is relevant across projects." It's not a profile name. Renaming it would require
updating entity frontmatter in projects and the propagation tag check. Not worth
the churn — the tag name is fine as-is.

---

## 4. Backward Compatibility

No backward compatibility layer. This is a clean rename:
- Old profile name `project_specific` will no longer be recognized
- Old source dirs will not be found
- Projects must be migrated (rename dir + update science.yaml + rebuild graph)
- The migration is mechanical and can be automated in the implementation plan

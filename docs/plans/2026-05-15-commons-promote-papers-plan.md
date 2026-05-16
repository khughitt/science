# Phase E: Commons Promote for Papers — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement `science commons promote paper` — discover, dedup, and migrate paper entities from per-project `doc/papers/*.md` files into the shared commons store, splitting each source into a canonical surface (commons) plus a project overlay (rewritten in place), with atomic-batch git semantics and an audit log.

**Architecture:** Two deliverables ship together. (1) Schema work in `science_model` adds `mixin-paper-2.0.json` (paper-canonical fields + `merge:` annotations + `x-canonical-body-sections`) and `overlay-1.1.json` (project-only paper fields + relaxed id regex). (2) New module `science_tool/commons/promote.py` owns discovery → plan → apply with three pure-ish phases: `discover_paper_candidates`, `plan_promote`, `apply_promote`. Apply is an atomic batch: one commons git commit, N tags, N path-limited project file rewrites, one `.migrations/` audit entry. Dry-run is the default; `--apply` writes. All git operations are path-limited to defend the commons repo against unrelated work.

**Tech Stack:** Python 3.11+, Pydantic 2, Click, PyYAML, pytest (with `tmp_path`), `uv run pytest`. Repo lives at `/mnt/ssd/Dropbox/science` (a.k.a. `~/d/science`); two Python packages: `science/model` (`science_model`) and `science/` (`science_tool`).

**Design doc:** `docs/plans/2026-05-15-commons-promote-papers-design.md` (commits `51afacf` → `980c0d7`).

**Test commands** (run from `/mnt/ssd/Dropbox/science`):
- Schema tests: `cd science/model && uv run pytest tests/<file>.py -v`
- Tool tests: `cd science && uv run pytest tests/<file>.py -v`
- Full suites must stay green at every commit: `cd science/model && uv run pytest` and `cd science && uv run pytest`.

**Conventions:**
- Every Python file starts with `from __future__ import annotations`.
- Conventional commit messages: `feat:`, `fix:`, `test:`, `docs:`, `refactor:`.
- CLI errors raise `click.ClickException(str(e))` to map to non-zero exits cleanly.
- Tests use `tmp_path` for filesystem fixtures; `pytest.raises` for error assertions; `monkeypatch` for env / config injection.

---

## Task Map

| # | Task | Files |
|---|---|---|
| 1 | Add `mixin-paper-2.0.json` schema | `science/model/src/science_model/schemas/mixin-paper-2.0.json`, `science/model/tests/test_entity_schema_mixin_paper.py` |
| 2 | Add `overlay-1.1.json` + bump validator/merge readers | `science/model/src/science_model/schemas/overlay-1.1.json`, `entity_schema/merge.py`, `entity_schema/validator.py`, `tests/test_entity_schema_overlay.py` |
| 3 | Add `read_canonical_body_sections` helper | `science/model/src/science_model/entity_schema/merge.py`, `tests/test_entity_schema_merge.py` |
| 4 | Add `default_profile_for_kind` helper + exports | `science/model/src/science_model/entity_schema/profile.py`, `entity_schema/__init__.py`, `tests/test_entity_schema_profile.py` (new) |
| 5 | Add `resolve_project_by_id` helper | `science/src/science_tool/commons/config.py`, `tests/test_commons_config.py` |
| 6 | Add four new error classes | `science/src/science_tool/commons/errors.py`, `tests/test_commons_errors.py` |
| 7 | Create `promote.py` module skeleton (dataclasses) | `science/src/science_tool/commons/promote.py`, `tests/test_commons_promote_discovery.py` (new — import smoke test) |
| 8 | Helpers: `_normalize_bibkey_for_match`, `_classify_paper_file_kind` | `promote.py`, `tests/test_commons_promote_discovery.py` |
| 9 | Helpers: `_parse_paper_file`, `_scan_project_papers` | `promote.py`, `tests/test_commons_promote_discovery.py` |
| 10 | Public: `discover_paper_candidates` | `promote.py`, `tests/test_commons_promote_discovery.py` |
| 11 | Classification: `_classify_entity` | `promote.py`, `tests/test_commons_promote_plan.py` (new) |
| 12 | Merging: `_merge_canonical_fields`, `_pick_canonical_bibkey_case` | `promote.py`, `tests/test_commons_promote_plan.py` |
| 13 | Rendering: `_coerce_date_for_yaml`, `_render_canonical`, `_render_overlay` | `promote.py`, `tests/test_commons_promote_plan.py` |
| 14 | Public: `prompt_resolve`, `plan_promote` | `promote.py`, `tests/test_commons_promote_plan.py` |
| 15 | Audit + rollback: `_write_audit_log`, `_rollback_step5` | `promote.py`, `tests/test_commons_promote_apply.py` (new) |
| 16 | `apply_promote` happy path (preflight + commit + tag + rewrite + audit) | `promote.py`, `tests/test_commons_promote_apply.py` |
| 17 | `apply_promote` failure paths (each `failure_stage`) | `promote.py`, `tests/test_commons_promote_apply.py` |
| 18 | Test fixtures: synthetic 2-project corpus | `science/tests/fixtures/promote/` |
| 19 | Wire `commons/__init__.py` exports | `science/src/science_tool/commons/__init__.py` |
| 20 | CLI: `commons promote paper` subgroup | `science/src/science_tool/commons/cli.py`, `tests/test_commons_cli_promote.py` (new) |
| 21 | Docs: pilot rollout runbook | `science/docs/runbooks/promote-papers-pilot.md` (or under `docs/plans/`) |

---

## Task 1: Add `mixin-paper-2.0.json` schema

**Files:**
- Create: `science/model/src/science_model/schemas/mixin-paper-2.0.json`
- Modify: `science/model/tests/test_entity_schema_mixin_paper.py`

- [ ] **Step 1: Write the failing tests**

Append to `science/model/tests/test_entity_schema_mixin_paper.py`:

```python
import json
from pathlib import Path

from science_model.entity_schema import MergePolicy, parse_profile, read_merge_policy


_SCHEMAS = Path(__file__).resolve().parents[1] / "src" / "science_model" / "schemas"


def test_mixin_paper_2_0_schema_loads():
    raw = (_SCHEMAS / "mixin-paper-2.0.json").read_text(encoding="utf-8")
    schema = json.loads(raw)
    assert schema["$id"].endswith("mixin-paper-2.0.json")
    assert "venue" in schema["properties"]
    assert "journal" not in schema["properties"]


def test_mixin_paper_2_0_bibkey_regex_permits_hyphens():
    raw = (_SCHEMAS / "mixin-paper-2.0.json").read_text(encoding="utf-8")
    schema = json.loads(raw)
    pattern = schema["properties"]["bibkey"]["pattern"]
    import re
    assert re.match(pattern, "categorical-composition-trio-2023-2025")
    assert re.match(pattern, "Adams2025")
    assert not re.match(pattern, "1leading-digit")


def test_mixin_paper_2_0_canonical_body_sections_annotation():
    raw = (_SCHEMAS / "mixin-paper-2.0.json").read_text(encoding="utf-8")
    schema = json.loads(raw)
    sections = schema["x-canonical-body-sections"]
    assert "Key Findings" in sections
    assert "Methods Summary" in sections
    assert "Limitations" in sections


def test_mixin_paper_2_0_merge_policy_overrides_base_for_created_updated_status():
    profile = parse_profile("science-entity-base/1.0+paper/2.0")
    policy = read_merge_policy(profile)
    assert policy["created"] == MergePolicy.PROJECT_ONLY
    assert policy["updated"] == MergePolicy.PROJECT_ONLY
    assert policy["status"] == MergePolicy.PROJECT_ONLY
    # Base contributes these; mixin does NOT override:
    assert policy["tags"] == MergePolicy.APPEND
    assert policy["ontology_terms"] == MergePolicy.APPEND
    # Paper-specific canonical fields default to REPLACE:
    assert policy["title"] == MergePolicy.REPLACE
    assert policy["authors"] == MergePolicy.REPLACE
    assert policy["year"] == MergePolicy.REPLACE
    # datasets is paper's own override → append:
    assert policy["datasets"] == MergePolicy.APPEND
```

- [ ] **Step 2: Run tests to verify they fail**

```
cd science/model && uv run pytest tests/test_entity_schema_mixin_paper.py -v
```

Expected: FAIL — `FileNotFoundError` on `mixin-paper-2.0.json`.

- [ ] **Step 3: Create the schema file**

Create `science/model/src/science_model/schemas/mixin-paper-2.0.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://schemas.science/mixin-paper-2.0.json",
  "title": "science entity paper mixin",
  "type": "object",
  "required": ["id", "type"],
  "x-canonical-body-sections": [
    "Key Findings",
    "Methods Summary",
    "Limitations",
    "Summary",
    "One-Sentence Summary"
  ],
  "properties": {
    "id": {"type": "string", "pattern": "^paper:[A-Za-z][A-Za-z0-9-]{1,63}$"},
    "type": {"const": "paper"},
    "bibkey": {"type": "string", "pattern": "^[A-Za-z][A-Za-z0-9-]{1,63}$"},
    "authors": {"type": "array", "items": {"type": "string"}},
    "year": {"type": "integer", "minimum": 1800, "maximum": 2200},
    "venue": {"type": "string"},
    "doi": {"type": "string"},
    "pmid": {"type": "string"},
    "url": {"type": "string"},
    "datasets": {
      "type": "array",
      "items": {"type": "string", "pattern": "^dataset:"},
      "science:merge": "append"
    },
    "key_findings": {"type": "array", "items": {"type": "string"}},
    "methods_summary": {"type": "string"},
    "limitations": {"type": "array", "items": {"type": "string"}},
    "created": {"type": "string", "format": "date", "science:merge": "project_only"},
    "updated": {"type": "string", "format": "date", "science:merge": "project_only"},
    "status": {"type": "string", "science:merge": "project_only"}
  }
}
```

- [ ] **Step 4: Run tests to verify they pass**

```
cd science/model && uv run pytest tests/test_entity_schema_mixin_paper.py -v
```

Expected: all four new tests PASS. Existing 1.0 tests in the file should also still pass.

- [ ] **Step 5: Run full science_model suite**

```
cd science/model && uv run pytest
```

Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add science/model/src/science_model/schemas/mixin-paper-2.0.json \
        science/model/tests/test_entity_schema_mixin_paper.py
git commit -m "$(cat <<'EOF'
feat(science_model): add mixin-paper-2.0 schema

Canonical paper fields + merge annotations + x-canonical-body-sections list.
Overrides base created/updated/status to project_only; keeps base tags/
ontology_terms as append. Bibkey regex permits hyphens. journal→venue rename.

Refs docs/plans/2026-05-15-commons-promote-papers-design.md §4.1.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Add `overlay-1.1.json` + bump validator/merge readers

**Files:**
- Create: `science/model/src/science_model/schemas/overlay-1.1.json`
- Modify: `science/model/src/science_model/entity_schema/merge.py:37`
- Modify: `science/model/src/science_model/entity_schema/validator.py:65`
- Modify: `science/model/tests/test_entity_schema_overlay.py`

- [ ] **Step 1: Write the failing tests**

Append to `science/model/tests/test_entity_schema_overlay.py`:

```python
import json
import re
from pathlib import Path

import pytest

from science_model.entity_schema import EntityValidator, MergePolicy, read_overlay_merge_policy


_SCHEMAS = Path(__file__).resolve().parents[1] / "src" / "science_model" / "schemas"


def test_overlay_1_1_schema_loads():
    schema = json.loads((_SCHEMAS / "overlay-1.1.json").read_text(encoding="utf-8"))
    assert schema["$id"].endswith("overlay-1.1.json")
    for field in ("status", "source", "related", "source_refs", "created", "updated"):
        assert field in schema["properties"], f"{field} missing"
    assert schema["additionalProperties"] is False


def test_overlay_1_1_canonical_id_regex_permits_hyphens_for_papers():
    schema = json.loads((_SCHEMAS / "overlay-1.1.json").read_text(encoding="utf-8"))
    patterns = [arm["pattern"] for arm in schema["$defs"]["canonicalId"]["oneOf"]]
    paper_pattern = next(p for p in patterns if "paper" in p)
    assert re.match(paper_pattern, "paper:categorical-composition-trio-2023-2025")
    assert re.match(paper_pattern, "paper:Adams2025")


def test_read_overlay_merge_policy_uses_1_1_and_returns_project_only_for_new_fields():
    policy = read_overlay_merge_policy()
    # New 1.1 fields default to project_only (no annotation):
    for field in ("status", "source", "related", "source_refs", "created", "updated"):
        assert policy[field] == MergePolicy.PROJECT_ONLY, f"{field} should be project_only"
    # Pre-existing annotations preserved:
    assert policy["tags"] == MergePolicy.APPEND
    assert policy["ontology_terms"] == MergePolicy.APPEND


def test_validate_overlay_accepts_paper_overlay_with_new_fields(tmp_path: Path):
    overlay = {
        "id": "paper:Adams2025",
        "overlay_of": "paper:Adams2025",
        "pin_version": "1.0.0",
        "status": "active",
        "source": "manual",
        "related": ["question:q1"],
        "source_refs": ["doi:10.1/abc"],
        "created": "2026-01-15",
        "updated": "2026-05-15",
    }
    EntityValidator().validate_overlay(overlay)  # should not raise


def test_validate_overlay_rejects_unknown_field():
    overlay = {
        "id": "paper:Adams2025",
        "overlay_of": "paper:Adams2025",
        "bogus_field": "x",
    }
    with pytest.raises(Exception):
        EntityValidator().validate_overlay(overlay)


def test_validate_overlay_accepts_hyphenated_paper_id():
    overlay = {
        "id": "paper:categorical-composition-trio-2023-2025",
        "overlay_of": "paper:categorical-composition-trio-2023-2025",
    }
    EntityValidator().validate_overlay(overlay)  # should not raise
```

- [ ] **Step 2: Run tests to verify they fail**

```
cd science/model && uv run pytest tests/test_entity_schema_overlay.py -v
```

Expected: FAIL — file not found, or merge.py / validator.py still load `1.0`.

- [ ] **Step 3: Create `overlay-1.1.json`**

Create `science/model/src/science_model/schemas/overlay-1.1.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://schemas.science/overlay-1.1.json",
  "title": "science entity project overlay",
  "type": "object",
  "required": ["id", "overlay_of"],
  "$defs": {
    "canonicalId": {
      "type": "string",
      "oneOf": [
        {"pattern": "^dataset:[a-z0-9][a-z0-9-]{0,63}$"},
        {"pattern": "^paper:[A-Za-z][A-Za-z0-9-]{1,63}$"},
        {"pattern": "^topic:[a-z0-9][a-z0-9-]{0,63}$"},
        {"pattern": "^theme:[a-z0-9][a-z0-9-]{0,63}$"}
      ]
    }
  },
  "properties": {
    "id": {"$ref": "#/$defs/canonicalId"},
    "overlay_of": {"$ref": "#/$defs/canonicalId"},
    "pin_version": {"type": "string", "pattern": "^[0-9]+\\.[0-9]+\\.[0-9]+$"},
    "pin_effective_version": {
      "type": "string",
      "pattern": "^[0-9]+\\.[0-9]+\\.[0-9]+\\+[0-9a-f]{7,40}$"
    },
    "relevance": {"type": "string"},
    "hypothesis_links": {"type": "array", "items": {"type": "string"}},
    "task_links": {"type": "array", "items": {"type": "string"}},
    "question_links": {"type": "array", "items": {"type": "string"}},
    "project_tags": {"type": "array", "items": {"type": "string"}},
    "project_notes": {"type": "string"},
    "tags": {
      "type": "array",
      "items": {"type": "string"},
      "science:merge": "append"
    },
    "ontology_terms": {
      "type": "array",
      "items": {"type": "string"},
      "science:merge": "append"
    },
    "status": {"type": "string"},
    "source": {"type": "string"},
    "related": {"type": "array", "items": {"type": "string"}},
    "source_refs": {"type": "array", "items": {"type": "string"}},
    "created": {"type": "string", "format": "date"},
    "updated": {"type": "string", "format": "date"}
  },
  "additionalProperties": false
}
```

- [ ] **Step 4: Bump the version in `merge.py`**

In `science/model/src/science_model/entity_schema/merge.py:37`, change:

```python
    schema = loader.load(ProfileComponent(name="overlay", version="1.0"))
```

to:

```python
    schema = loader.load(ProfileComponent(name="overlay", version="1.1"))
```

- [ ] **Step 5: Bump the version in `validator.py`**

In `science/model/src/science_model/entity_schema/validator.py:65`, change:

```python
        schema = self._loader.load(ProfileComponent(name="overlay", version="1.0"))
```

to:

```python
        schema = self._loader.load(ProfileComponent(name="overlay", version="1.1"))
```

- [ ] **Step 6: Run tests to verify they pass**

```
cd science/model && uv run pytest tests/test_entity_schema_overlay.py -v
```

Expected: all six new tests PASS. Pre-existing overlay tests must also still pass (1.0 → 1.1 is additive).

- [ ] **Step 7: Run the full science_model suite**

```
cd science/model && uv run pytest
```

Expected: all green.

- [ ] **Step 8: Commit**

```bash
git add science/model/src/science_model/schemas/overlay-1.1.json \
        science/model/src/science_model/entity_schema/merge.py \
        science/model/src/science_model/entity_schema/validator.py \
        science/model/tests/test_entity_schema_overlay.py
git commit -m "$(cat <<'EOF'
feat(science_model): bump overlay schema to 1.1

Adds project-side paper fields (status, source, related, source_refs, created,
updated) as named properties so overlay rewrites with these fields don't trip
additionalProperties:false. Relaxes canonicalId paper regex to permit hyphens.
Loader and validator both bumped to load 1.1.

Refs docs/plans/2026-05-15-commons-promote-papers-design.md §4.4.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Add `read_canonical_body_sections` helper

**Files:**
- Modify: `science/model/src/science_model/entity_schema/merge.py`
- Modify: `science/model/tests/test_entity_schema_merge.py`

- [ ] **Step 1: Write the failing test**

Append to `science/model/tests/test_entity_schema_merge.py`:

```python
from science_model.entity_schema import parse_profile, read_canonical_body_sections


def test_read_canonical_body_sections_returns_paper_2_0_sections():
    profile = parse_profile("science-entity-base/1.0+paper/2.0")
    sections = read_canonical_body_sections(profile)
    assert "Key Findings" in sections
    assert "Methods Summary" in sections
    assert "Limitations" in sections


def test_read_canonical_body_sections_returns_empty_when_annotation_absent():
    # base schema has no x-canonical-body-sections
    profile = parse_profile("science-entity-base/1.0")
    assert read_canonical_body_sections(profile) == []
```

- [ ] **Step 2: Run test to verify it fails**

```
cd science/model && uv run pytest tests/test_entity_schema_merge.py -v
```

Expected: FAIL — `ImportError: cannot import name 'read_canonical_body_sections'`.

- [ ] **Step 3: Add the helper**

Append to `science/model/src/science_model/entity_schema/merge.py`:

```python
def read_canonical_body_sections(
    profile: ProfileString, loader: SchemaLoader | None = None
) -> list[str]:
    """Return the union of `x-canonical-body-sections` declared by the profile
    components, in declaration order across (base, mixin, extensions).

    Headings are returned verbatim (with original case); matching is case-
    insensitive at the call site. Returns [] when no component declares the
    annotation.
    """
    loader = loader or SchemaLoader()
    sections: list[str] = []
    seen: set[str] = set()
    for component in _iter_components(profile):
        schema = loader.load(component)
        for heading in schema.get("x-canonical-body-sections", []) or []:
            key = heading.casefold()
            if key not in seen:
                sections.append(heading)
                seen.add(key)
    return sections
```

- [ ] **Step 4: Export from `__init__.py`**

In `science/model/src/science_model/entity_schema/__init__.py`, add `read_canonical_body_sections` to the imports from `.merge` AND to `__all__`. The merge-imports block becomes:

```python
from science_model.entity_schema.merge import (
    MergePolicy,
    read_canonical_body_sections,
    read_merge_policy,
    read_overlay_merge_policy,
)
```

and the corresponding `__all__` entry `"read_canonical_body_sections",` is added (alphabetical position).

- [ ] **Step 5: Run tests to verify they pass**

```
cd science/model && uv run pytest tests/test_entity_schema_merge.py -v
```

Expected: PASS.

- [ ] **Step 6: Run full science_model suite**

```
cd science/model && uv run pytest
```

Expected: all green.

- [ ] **Step 7: Commit**

```bash
git add science/model/src/science_model/entity_schema/merge.py \
        science/model/src/science_model/entity_schema/__init__.py \
        science/model/tests/test_entity_schema_merge.py
git commit -m "$(cat <<'EOF'
feat(science_model): add read_canonical_body_sections helper

Returns the merged x-canonical-body-sections list from a composed profile,
de-duped case-insensitively. Used by promote to decide which markdown body
sections lift to the canonical surface vs stay on the overlay.

Refs docs/plans/2026-05-15-commons-promote-papers-design.md §4.3.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Add `default_profile_for_kind` helper + exports

**Files:**
- Modify: `science/model/src/science_model/entity_schema/profile.py`
- Modify: `science/model/src/science_model/entity_schema/__init__.py`
- Create: `science/model/tests/test_entity_schema_profile.py`

- [ ] **Step 1: Write the failing test**

Create `science/model/tests/test_entity_schema_profile.py`:

```python
"""Tests for science_model.entity_schema.profile helpers."""

from __future__ import annotations

import pytest

from science_model.entity_schema import (
    ProfileParseError,
    default_profile_for_kind,
    parse_profile,
)


def test_default_profile_for_kind_paper():
    profile = default_profile_for_kind("paper")
    assert profile.render() == "science-entity-base/1.0+paper/2.0"


def test_default_profile_for_kind_dataset():
    profile = default_profile_for_kind("dataset")
    assert profile.base.name == "science-entity-base"
    assert profile.mixin is not None
    assert profile.mixin.name == "dataset"


def test_default_profile_for_kind_rejects_unknown_kind():
    with pytest.raises(ProfileParseError):
        default_profile_for_kind("not-a-real-kind")


def test_default_profile_for_kind_returns_parsed_profile():
    profile = default_profile_for_kind("paper")
    # Round-trip through parse_profile to confirm it's a real ProfileString:
    assert parse_profile(profile.render()).render() == profile.render()
```

- [ ] **Step 2: Run test to verify it fails**

```
cd science/model && uv run pytest tests/test_entity_schema_profile.py -v
```

Expected: FAIL — `ImportError: cannot import name 'default_profile_for_kind'`.

- [ ] **Step 3: Add the helper**

Append to `science/model/src/science_model/entity_schema/profile.py`:

```python
# Default mixin version per kind, used by `default_profile_for_kind`.
# Add an entry here when a new mixin version becomes the project default.
_DEFAULT_MIXIN_VERSION: dict[str, str] = {
    "dataset": "1.0",
    "paper": "2.0",
    "topic": "1.0",
    "theme": "1.0",
}

_DEFAULT_BASE_VERSION = "1.0"


def default_profile_for_kind(kind: str) -> ProfileString:
    """Return the default parsed ProfileString for a kind.

    Composes the current default base version with the kind's current default
    mixin version, e.g. `default_profile_for_kind("paper")` returns the parsed
    form of `"science-entity-base/1.0+paper/2.0"`.

    Raises ProfileParseError for an unknown kind.
    """
    if kind not in _DEFAULT_MIXIN_VERSION:
        raise ProfileParseError(
            f"unknown kind {kind!r}; expected one of {sorted(_DEFAULT_MIXIN_VERSION)}"
        )
    return parse_profile(
        f"{BASE_NAME}/{_DEFAULT_BASE_VERSION}+{kind}/{_DEFAULT_MIXIN_VERSION[kind]}"
    )
```

- [ ] **Step 4: Export from `__init__.py`**

In `science/model/src/science_model/entity_schema/__init__.py`, extend the `from .profile import (...)` block to include `default_profile_for_kind`, and add `"default_profile_for_kind",` to `__all__` (alphabetical position).

- [ ] **Step 5: Run test to verify it passes**

```
cd science/model && uv run pytest tests/test_entity_schema_profile.py -v
```

Expected: all four tests PASS.

- [ ] **Step 6: Run full science_model suite**

```
cd science/model && uv run pytest
```

Expected: all green.

- [ ] **Step 7: Commit**

```bash
git add science/model/src/science_model/entity_schema/profile.py \
        science/model/src/science_model/entity_schema/__init__.py \
        science/model/tests/test_entity_schema_profile.py
git commit -m "$(cat <<'EOF'
feat(science_model): add default_profile_for_kind helper

Returns a parsed ProfileString for the kind's current default mixin version
(paper → 2.0, dataset/topic/theme → 1.0). Used by promote and tests as the
canonical way to address the paper canonical schema without hardcoding raw
profile strings.

Refs docs/plans/2026-05-15-commons-promote-papers-design.md §4.5.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Add `resolve_project_by_id` helper

**Files:**
- Modify: `science/src/science_tool/commons/config.py`
- Modify: `science/tests/test_commons_config.py`

Note: the test file may not exist yet — create if needed. Also note: this task adds a new error class is needed at the call site, but we keep that to Task 6. For now this helper raises a generic `CommonsError`, which will be re-classed when `PromoteInputError` lands.

- [ ] **Step 1: Write the failing tests**

Append (or create) `science/tests/test_commons_config.py` with:

```python
"""Tests for science_tool.commons.config (resolve_project_by_id)."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from science_tool.commons.config import resolve_project_by_id
from science_tool.commons.errors import CommonsError


def _write_config(tmp_path: Path, body: str) -> Path:
    cfg_dir = tmp_path / "config" / "science"
    cfg_dir.mkdir(parents=True)
    cfg = cfg_dir / "config.yaml"
    cfg.write_text(dedent(body), encoding="utf-8")
    return tmp_path


def test_resolve_project_by_id_returns_path(tmp_path, monkeypatch):
    root = _write_config(
        tmp_path,
        """
        projects:
          - path: ~/d/natural-systems
            name: natural-systems-guide
            id: natural-systems
            role: standalone
            parent: null
        """,
    )
    monkeypatch.setenv("XDG_CONFIG_HOME", str(root / "config"))
    monkeypatch.setenv("HOME", str(tmp_path))
    p = resolve_project_by_id("natural-systems")
    assert p == (tmp_path / "d" / "natural-systems")


def test_resolve_project_by_id_rejects_unregistered(tmp_path, monkeypatch):
    root = _write_config(
        tmp_path,
        """
        projects:
          - path: ~/d/natural-systems
            name: natural-systems-guide
            id: natural-systems
            role: standalone
            parent: null
        """,
    )
    monkeypatch.setenv("XDG_CONFIG_HOME", str(root / "config"))
    monkeypatch.setenv("HOME", str(tmp_path))
    with pytest.raises(CommonsError, match="no registered project with id"):
        resolve_project_by_id("not-a-real-id")


def test_resolve_project_by_id_rejects_null_id(tmp_path, monkeypatch):
    root = _write_config(
        tmp_path,
        """
        projects:
          - path: ~/d/legacy
            name: legacy-project
            id: null
            role: null
            parent: null
        """,
    )
    monkeypatch.setenv("XDG_CONFIG_HOME", str(root / "config"))
    monkeypatch.setenv("HOME", str(tmp_path))
    with pytest.raises(CommonsError, match="id is null"):
        resolve_project_by_id("legacy-project")
```

- [ ] **Step 2: Run tests to verify they fail**

```
cd science && uv run pytest tests/test_commons_config.py -v
```

Expected: FAIL — `ImportError: cannot import name 'resolve_project_by_id'`.

- [ ] **Step 3: Add the helper**

Append to `science/src/science_tool/commons/config.py`:

```python
def resolve_project_by_id(project_id: str) -> Path:
    """Look up a registered project by `id:` (not `name:`) and return its root path.

    Reads `projects[]` from the global config. Distinguishes three failure modes:

    - id is null on a matching entry → CommonsError("id is null") — caller (promote)
      maps this to "this registration has no id; assign one or deregister"
    - no entry matches the given id → CommonsError("no registered project with id")
    - all good → return the path (expanded `~`).

    Used by `science commons promote --from <id>` to enforce the id-based
    `--from` contract. The legacy `resolve_project_root(name)` matches by name and
    is left alone for callers that still want name-based lookup.
    """
    from science_tool.registry.config import load_global_config

    cfg = load_global_config()
    for project in cfg.projects:
        if project.id == project_id:
            if project.id is None:  # defensive — project.id == project_id == None
                raise CommonsError(
                    f"project at {project.path!r} has id: null; assign an id "
                    "in ~/.config/science/config.yaml or deregister the entry"
                )
            return Path(project.path).expanduser()
    # No match by id; check whether *any* registration uses the same name and
    # has a null id, which is the legacy-registration failure mode we want to
    # diagnose specifically.
    for project in cfg.projects:
        if project.name == project_id and project.id is None:
            raise CommonsError(
                f"project {project_id!r} is registered with id: null; assign an id "
                "in ~/.config/science/config.yaml or deregister the entry"
            )
    raise CommonsError(f"no registered project with id {project_id!r}")
```

- [ ] **Step 4: Run tests to verify they pass**

```
cd science && uv run pytest tests/test_commons_config.py -v
```

Expected: all three new tests PASS.

- [ ] **Step 5: Run full science suite**

```
cd science && uv run pytest
```

Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/commons/config.py \
        science/tests/test_commons_config.py
git commit -m "$(cat <<'EOF'
feat(commons): add resolve_project_by_id helper

Id-based registry lookup; rejects null-id legacy registrations with a clear
message distinct from "no such id." Used by `science commons promote --from
<id>` to enforce the id-based --from contract.

Refs docs/plans/2026-05-15-commons-promote-papers-design.md §5.3.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Add four new error classes

**Files:**
- Modify: `science/src/science_tool/commons/errors.py`
- Modify: `science/tests/test_commons_errors.py`

- [ ] **Step 1: Write the failing tests**

Append to `science/tests/test_commons_errors.py`:

```python
import pytest

from science_tool.commons.errors import (
    CommonsError,
    PromoteCandidateError,
    PromoteConflictAbort,
    PromoteInputError,
    PromoteWriteError,
)


def test_promote_input_error_is_commons_error():
    e = PromoteInputError("missing --from")
    assert isinstance(e, CommonsError)
    assert "missing --from" in str(e)


def test_promote_candidate_error_carries_bibkey_and_path():
    from pathlib import Path
    e = PromoteCandidateError("frontmatter parse error", bibkey="Adams2025", path=Path("/x/y.md"))
    assert e.bibkey == "Adams2025"
    assert e.path == Path("/x/y.md")
    assert isinstance(e, CommonsError)


def test_promote_conflict_abort_is_commons_error():
    e = PromoteConflictAbort("user aborted")
    assert isinstance(e, CommonsError)


def test_promote_write_error_carries_stage_and_partial_state():
    e = PromoteWriteError(
        stage="rewrite_projects",
        detail="overlay write failed",
        commons_commit="abc1234",
        projects_touched=["natural-systems"],
    )
    assert e.stage == "rewrite_projects"
    assert e.detail == "overlay write failed"
    assert e.commons_commit == "abc1234"
    assert e.projects_touched == ["natural-systems"]
    assert isinstance(e, CommonsError)
```

- [ ] **Step 2: Run tests to verify they fail**

```
cd science && uv run pytest tests/test_commons_errors.py -v
```

Expected: FAIL — `ImportError`.

- [ ] **Step 3: Add the error classes**

Append to `science/src/science_tool/commons/errors.py`:

```python
class PromoteInputError(CommonsError):
    """Bad input to `science commons promote`.

    Raised for: missing/unregistered/null-id `--from` slug; commons store missing;
    required positional argument absent; dirty target file at preflight; commons
    repo dirty at preflight; repo mid-merge/rebase/cherry-pick/bisect.
    """


class PromoteCandidateError(CommonsError):
    """A paper file is malformed (parse error, unreadable, schema-failing).

    Constructed per-candidate. NOT raised out of `discover_paper_candidates`;
    instead wrapped as a `FailedCandidate` in the plan. Raised directly only by
    `apply_promote` if an in-plan decision turns out to be unparseable at write
    time (file deleted between plan and apply) — that's a hard-stop case.
    """

    def __init__(
        self,
        message: str,
        *,
        bibkey: str | None = None,
        path: Path | None = None,
    ) -> None:
        super().__init__(message)
        self.bibkey = bibkey
        self.path = path


class PromoteConflictAbort(CommonsError):
    """User aborted at a conflict prompt (Ctrl-C, or 'abort' answer).

    Batch stops cleanly before any commons or project write.
    """


class PromoteWriteError(CommonsError):
    """IO / git failure during apply steps 4–7.

    Carries `stage`, `detail`, and optional partial-state info (commons commit
    hash if step 5 landed, list of projects touched) so the audit log can record
    exactly what landed.
    """

    def __init__(
        self,
        *,
        stage: str,
        detail: str,
        commons_commit: str | None = None,
        projects_touched: list[str] | None = None,
    ) -> None:
        super().__init__(f"[{stage}] {detail}")
        self.stage = stage
        self.detail = detail
        self.commons_commit = commons_commit
        self.projects_touched = projects_touched or []
```

- [ ] **Step 4: Run tests to verify they pass**

```
cd science && uv run pytest tests/test_commons_errors.py -v
```

Expected: all four new tests PASS.

- [ ] **Step 5: Run full science suite**

```
cd science && uv run pytest
```

Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/commons/errors.py \
        science/tests/test_commons_errors.py
git commit -m "$(cat <<'EOF'
feat(commons): add four promote error classes

PromoteInputError / PromoteCandidateError / PromoteConflictAbort /
PromoteWriteError under the existing CommonsError hierarchy. Each carries the
structured fields documented in §7 of the design (bibkey+path,
stage+detail+partial-state, etc.).

Refs docs/plans/2026-05-15-commons-promote-papers-design.md §7.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Create `promote.py` module skeleton (dataclasses)

**Files:**
- Create: `science/src/science_tool/commons/promote.py`
- Create: `science/tests/test_commons_promote_discovery.py`

This task lays down the dataclass surface and module-level imports. No business logic yet — that lands in Tasks 8–14. The smoke test confirms the dataclasses are importable and frozen-slots.

- [ ] **Step 1: Write the failing smoke test**

Create `science/tests/test_commons_promote_discovery.py`:

```python
"""Tests for science_tool.commons.promote — discovery + module surface."""

from __future__ import annotations

from pathlib import Path

import pytest


def test_promote_module_imports():
    from science_tool.commons import promote  # noqa: F401


def test_dataclass_surface_is_frozen():
    from science_tool.commons.promote import (
        ConflictResolution,
        DiscoveryResult,
        FailedCandidate,
        FieldConflict,
        OverlayRewrite,
        PromoteCandidate,
        PromoteDecision,
        PromotePlan,
        PromoteResult,
    )

    for cls in (
        PromoteCandidate,
        FieldConflict,
        ConflictResolution,
        OverlayRewrite,
        PromoteDecision,
        FailedCandidate,
        DiscoveryResult,
        PromotePlan,
        PromoteResult,
    ):
        # frozen=True dataclasses raise on attribute set
        with pytest.raises(AttributeError):
            instance = cls.__new__(cls)
            instance.bogus_attr = 1  # type: ignore[misc]
```

- [ ] **Step 2: Run test to verify it fails**

```
cd science && uv run pytest tests/test_commons_promote_discovery.py -v
```

Expected: FAIL — `ImportError`.

- [ ] **Step 3: Create the module skeleton**

Create `science/src/science_tool/commons/promote.py`:

```python
"""Promote paper entities from per-project files into the commons store.

Pipeline: discover → plan → apply. Atomic-batch transaction semantics
per docs/plans/2026-05-15-commons-promote-papers-design.md §6.3.

This module owns:
- Dataclasses for the public surface (PromoteCandidate, PromotePlan, …).
- `discover_paper_candidates(project_slugs) -> DiscoveryResult` (Task 10).
- `plan_promote(discovery, commons_root, *, resolve_conflict) -> PromotePlan` (Task 14).
- `apply_promote(plan, commons_root, *, invocation) -> PromoteResult` (Tasks 16–17).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Literal


# --------------------------------------------------------------------------- #
# Public dataclasses                                                          #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class PromoteCandidate:
    """One paper file found during discovery.

    `bibkey` is the source's case (filename stem). `bibkey_normalized` is
    casefold() used only for dedup grouping. See design §4.1.3.
    """

    bibkey: str
    bibkey_normalized: str
    project_slug: str
    project_root: Path
    overlay_source_path: Path
    canonical_fields: dict[str, Any]
    project_only_fields: dict[str, Any]
    canonical_body: dict[str, str]
    project_only_body: dict[str, Any]
    # `project_only_body` is `dict[str, Any]` (not `[str, str]`) so the
    # discovery phase can stash the raw `(frontmatter, body)` pair under
    # sentinel keys `__raw_frontmatter__` / `__raw_body__` for `plan_promote`
    # to consume during classification. After `_classify_entity` runs in
    # `plan_promote`, the dict's values are pure `str` again.


@dataclass(frozen=True, slots=True)
class FieldConflict:
    bibkey: str
    field: str
    candidates: dict[str, Any]  # project_slug → value


@dataclass(frozen=True, slots=True)
class ConflictResolution:
    bibkey: str
    field: str
    candidates: dict[str, Any]
    resolved_to: Any
    source_project: str | None  # None if user entered a manual value


@dataclass(frozen=True, slots=True)
class OverlayRewrite:
    project_slug: str
    path: Path
    before_sha: str
    after_content: str
    pin_version: str
    rename_from: Path | None = None  # set when canonical case differs from source


@dataclass(frozen=True, slots=True)
class PromoteDecision:
    bibkey: str
    canonical_path: Path                 # absolute `<commons>/papers/<bibkey>.md`
    canonical_content: str               # rendered canonical file (markdown + frontmatter)
    canonical_version: str               # "1.0.0" etc.
    overlays: dict[str, OverlayRewrite]  # project_slug → rewrite plan
    resolved_conflicts: tuple[ConflictResolution, ...]


@dataclass(frozen=True, slots=True)
class FailedCandidate:
    bibkey: str | None
    project_slug: str
    source_path: Path
    error_class: str
    error_message: str


@dataclass(frozen=True, slots=True)
class DiscoveryResult:
    candidates_by_bibkey: dict[str, list[PromoteCandidate]]
    failed_candidates: list[FailedCandidate]


@dataclass(frozen=True, slots=True)
class PromotePlan:
    decisions: list[PromoteDecision]
    failed_candidates: list[FailedCandidate]


@dataclass(frozen=True, slots=True)
class PromoteResult:
    op_id: str
    started_at: datetime
    finished_at: datetime
    commons_commit: str | None
    tags_created: list[str]
    decisions: list[PromoteDecision]
    failed_candidates: list[FailedCandidate]
    audit_log_path: Path | None
    status: Literal["ok", "failed"]
    failure_stage: Literal[
        "preflight", "validate", "discover", "plan",
        "write_commons", "rewrite_projects", "audit",
    ] | None
    failure_detail: str | None


# --------------------------------------------------------------------------- #
# Public entry points (stubs — implemented in Tasks 10, 14, 16, 17)           #
# --------------------------------------------------------------------------- #


def discover_paper_candidates(project_slugs: list[str]) -> DiscoveryResult:
    raise NotImplementedError  # Task 10


def plan_promote(
    discovery: DiscoveryResult,
    commons_root: Path,
    *,
    resolve_conflict: "Callable[[FieldConflict], Any] | None" = None,
) -> PromotePlan:
    raise NotImplementedError  # Task 14


def apply_promote(
    plan: PromotePlan,
    commons_root: Path,
    *,
    invocation: str,
) -> PromoteResult:
    raise NotImplementedError  # Tasks 16–17
```

- [ ] **Step 4: Run tests to verify they pass**

```
cd science && uv run pytest tests/test_commons_promote_discovery.py -v
```

Expected: both tests PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/commons/promote.py \
        science/tests/test_commons_promote_discovery.py
git commit -m "$(cat <<'EOF'
feat(commons): promote module skeleton (dataclasses + stubs)

Adds the frozen dataclass public surface (PromoteCandidate, PromotePlan,
PromoteResult, etc.) and NotImplementedError stubs for the three entry
points. Concrete behavior lands in subsequent tasks.

Refs docs/plans/2026-05-15-commons-promote-papers-design.md §5.1.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Helpers — `_normalize_bibkey_for_match`, `_classify_paper_file_kind`

**Files:**
- Modify: `science/src/science_tool/commons/promote.py`
- Modify: `science/tests/test_commons_promote_discovery.py`

- [ ] **Step 1: Write the failing tests**

Append to `science/tests/test_commons_promote_discovery.py`:

```python
def test_normalize_bibkey_for_match_casefolds():
    from science_tool.commons.promote import _normalize_bibkey_for_match
    assert _normalize_bibkey_for_match("Huh2024") == "huh2024"
    assert _normalize_bibkey_for_match("ADAMS2025") == "adams2025"
    assert _normalize_bibkey_for_match("Adams2025.md") == "adams2025"


def test_normalize_bibkey_for_match_rejects_empty():
    from science_tool.commons.promote import _normalize_bibkey_for_match
    from science_tool.commons.errors import PromoteCandidateError
    import pytest
    with pytest.raises(PromoteCandidateError):
        _normalize_bibkey_for_match("")
    with pytest.raises(PromoteCandidateError):
        _normalize_bibkey_for_match("   ")


def test_normalize_bibkey_for_match_rejects_regex_failing():
    from science_tool.commons.promote import _normalize_bibkey_for_match
    from science_tool.commons.errors import PromoteCandidateError
    import pytest
    with pytest.raises(PromoteCandidateError):
        _normalize_bibkey_for_match("1leading-digit")
    with pytest.raises(PromoteCandidateError):
        _normalize_bibkey_for_match("has space")


def test_classify_paper_file_kind_explicit_paper():
    from science_tool.commons.promote import _classify_paper_file_kind
    assert _classify_paper_file_kind({"kind": "paper"}) == "paper"
    assert _classify_paper_file_kind({"type": "paper"}) == "paper"


def test_classify_paper_file_kind_explicit_other_kind():
    from science_tool.commons.promote import _classify_paper_file_kind
    assert _classify_paper_file_kind({"kind": "review-article"}) == "skip-other-kind"
    assert _classify_paper_file_kind({"type": "dataset"}) == "skip-other-kind"


def test_classify_paper_file_kind_no_kind_inferred_as_paper():
    from science_tool.commons.promote import _classify_paper_file_kind
    assert _classify_paper_file_kind({"title": "Foo"}) == "paper"
    assert _classify_paper_file_kind({}) == "paper"


def test_classify_paper_file_kind_non_paper_id_prefix():
    from science_tool.commons.promote import _classify_paper_file_kind
    # id present and prefix != paper: → skip-other-id (defense-in-depth)
    assert _classify_paper_file_kind({"id": "dataset:foo"}) == "skip-other-id"
    # id with paper: prefix is fine even without explicit kind:
    assert _classify_paper_file_kind({"id": "paper:Adams2025"}) == "paper"
```

- [ ] **Step 2: Run tests to verify they fail**

```
cd science && uv run pytest tests/test_commons_promote_discovery.py -v
```

Expected: FAIL — `ImportError`.

- [ ] **Step 3: Add the helpers**

Append to `science/src/science_tool/commons/promote.py`:

```python
import re

from science_tool.commons.errors import PromoteCandidateError


_BIBKEY_RE = re.compile(r"^[A-Za-z][A-Za-z0-9-]{1,63}$")


def _normalize_bibkey_for_match(raw: str) -> str:
    """Strip `.md`, casefold for dedup grouping. Raises PromoteCandidateError on
    empty / whitespace / regex-failing inputs. Does NOT mutate canonical case."""
    if raw is None:
        raise PromoteCandidateError("bibkey is None")
    stripped = raw.strip()
    if not stripped:
        raise PromoteCandidateError("bibkey is empty / whitespace")
    if stripped.endswith(".md"):
        stripped = stripped[:-3]
    if not _BIBKEY_RE.match(stripped):
        raise PromoteCandidateError(
            f"bibkey {raw!r} does not match [A-Za-z][A-Za-z0-9-]{{1,63}}"
        )
    return stripped.casefold()


def _classify_paper_file_kind(
    frontmatter: dict,
) -> Literal["paper", "skip-other-kind", "skip-other-id"]:
    """Decide whether a file under `doc/papers/` is a paper candidate.

    Rule (design §6.3 step 2):
    1. Explicit `kind: paper` or `type: paper` → paper.
    2. Explicit `kind` / `type` with any other value → skip-other-kind.
    3. No `kind` / `type` → infer from directory: paper.
    4. `id` present and NOT starting with `paper:` → skip-other-id
       (defense-in-depth; stronger declaration than directory).
    """
    if "id" in frontmatter:
        id_val = frontmatter["id"]
        if isinstance(id_val, str) and not id_val.startswith("paper:"):
            return "skip-other-id"
    kind_val = frontmatter.get("kind") or frontmatter.get("type")
    if kind_val is None:
        return "paper"
    if kind_val == "paper":
        return "paper"
    return "skip-other-kind"
```

- [ ] **Step 4: Run tests to verify they pass**

```
cd science && uv run pytest tests/test_commons_promote_discovery.py -v
```

Expected: 7 new tests PASS (10 total in this file).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/commons/promote.py \
        science/tests/test_commons_promote_discovery.py
git commit -m "$(cat <<'EOF'
feat(commons/promote): bibkey normalization + kind classifier

_normalize_bibkey_for_match: strips .md, casefolds for grouping, rejects empty
or regex-failing values. _classify_paper_file_kind: explicit paper → paper,
explicit other kind → skip, no kind → inferred paper, non-paper id prefix →
skip (defense-in-depth).

Refs docs/plans/2026-05-15-commons-promote-papers-design.md §6.3 step 2.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: Helpers — `_parse_paper_file`, `_scan_project_papers`

**Files:**
- Modify: `science/src/science_tool/commons/promote.py`
- Modify: `science/tests/test_commons_promote_discovery.py`

- [ ] **Step 1: Write the failing tests**

Append to `science/tests/test_commons_promote_discovery.py`:

```python
def test_parse_paper_file_returns_frontmatter_and_body(tmp_path):
    from science_tool.commons.promote import _parse_paper_file
    p = tmp_path / "Adams2025.md"
    p.write_text(
        "---\n"
        "id: paper:Adams2025\n"
        "title: Hello\n"
        "---\n"
        "\n"
        "## Key Findings\n\nOne.\n",
        encoding="utf-8",
    )
    fm, body = _parse_paper_file(p)
    assert fm["id"] == "paper:Adams2025"
    assert fm["title"] == "Hello"
    assert "## Key Findings" in body


def test_parse_paper_file_no_frontmatter_raises(tmp_path):
    from science_tool.commons.promote import _parse_paper_file
    from science_tool.commons.errors import PromoteCandidateError
    import pytest
    p = tmp_path / "broken.md"
    p.write_text("just a body, no frontmatter\n", encoding="utf-8")
    with pytest.raises(PromoteCandidateError, match="no frontmatter"):
        _parse_paper_file(p)


def test_parse_paper_file_malformed_yaml_raises(tmp_path):
    from science_tool.commons.promote import _parse_paper_file
    from science_tool.commons.errors import PromoteCandidateError
    import pytest
    p = tmp_path / "broken.md"
    p.write_text("---\nid: : :\n---\nbody\n", encoding="utf-8")
    with pytest.raises(PromoteCandidateError, match="frontmatter parse"):
        _parse_paper_file(p)


def test_scan_project_papers_walks_doc_papers(tmp_path):
    from science_tool.commons.promote import _scan_project_papers

    papers = tmp_path / "doc" / "papers"
    papers.mkdir(parents=True)
    (papers / "Adams2025.md").write_text(
        "---\nid: paper:Adams2025\ntitle: A\n---\n\nbody\n",
        encoding="utf-8",
    )
    (papers / "Huh2024.md").write_text(
        "---\nid: paper:Huh2024\ntitle: H\nkind: paper\n---\n",
        encoding="utf-8",
    )

    candidates, failures = _scan_project_papers(tmp_path, "test-project")
    bibkeys = sorted(c.bibkey for c in candidates)
    assert bibkeys == ["Adams2025", "Huh2024"]
    assert failures == []


def test_scan_project_papers_skips_already_promoted(tmp_path):
    from science_tool.commons.promote import _scan_project_papers
    papers = tmp_path / "doc" / "papers"
    papers.mkdir(parents=True)
    (papers / "Done2024.md").write_text(
        "---\nid: paper:Done2024\noverlay_of: paper:Done2024\npin_version: '1.0.0'\n---\n",
        encoding="utf-8",
    )
    candidates, failures = _scan_project_papers(tmp_path, "test-project")
    assert candidates == []
    assert failures == []


def test_scan_project_papers_records_failures_without_aborting(tmp_path):
    from science_tool.commons.promote import _scan_project_papers
    papers = tmp_path / "doc" / "papers"
    papers.mkdir(parents=True)
    (papers / "Good2024.md").write_text(
        "---\nid: paper:Good2024\ntitle: G\n---\n",
        encoding="utf-8",
    )
    (papers / "Broken2024.md").write_text(
        "no frontmatter\n",
        encoding="utf-8",
    )
    candidates, failures = _scan_project_papers(tmp_path, "test-project")
    assert [c.bibkey for c in candidates] == ["Good2024"]
    assert len(failures) == 1
    assert failures[0].source_path.name == "Broken2024.md"
    assert failures[0].error_class == "PromoteCandidateError"


def test_scan_project_papers_skips_other_kind_with_warning(tmp_path, caplog):
    from science_tool.commons.promote import _scan_project_papers
    papers = tmp_path / "doc" / "papers"
    papers.mkdir(parents=True)
    (papers / "Misfiled.md").write_text(
        "---\nid: paper:Misfiled\ntitle: X\nkind: dataset\n---\n",
        encoding="utf-8",
    )
    candidates, failures = _scan_project_papers(tmp_path, "test-project")
    assert candidates == []
    assert failures == []  # not a failure, just a skip
```

- [ ] **Step 2: Run tests to verify they fail**

```
cd science && uv run pytest tests/test_commons_promote_discovery.py -v
```

Expected: FAIL — `ImportError`.

- [ ] **Step 3: Add the helpers**

Append to `science/src/science_tool/commons/promote.py`:

```python
import logging

import yaml

logger = logging.getLogger(__name__)


def _parse_paper_file(path: Path) -> tuple[dict, str]:
    """Return (frontmatter_dict, body_text). Raises PromoteCandidateError on
    parse failure, unreadable file, or missing frontmatter delimiters."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise PromoteCandidateError(
            f"unreadable file: {exc}", path=path
        ) from exc
    lines = text.splitlines(keepends=False)
    if not lines or lines[0].strip() != "---":
        raise PromoteCandidateError("no frontmatter (missing leading ---)", path=path)
    closing_idx: int | None = None
    for idx, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            closing_idx = idx
            break
    if closing_idx is None:
        raise PromoteCandidateError("no frontmatter (missing closing ---)", path=path)
    yaml_block = "\n".join(lines[1:closing_idx])
    try:
        fm = yaml.safe_load(yaml_block) or {}
    except yaml.YAMLError as exc:
        raise PromoteCandidateError(
            f"frontmatter parse error: {exc}", path=path
        ) from exc
    if not isinstance(fm, dict):
        raise PromoteCandidateError(
            "frontmatter is not a mapping", path=path
        )
    body = "\n".join(lines[closing_idx + 1 :])
    if text.endswith("\n") and not body.endswith("\n"):
        body += "\n"
    return fm, body


def _scan_project_papers(
    project_root: Path, project_slug: str
) -> tuple[list[PromoteCandidate], list[FailedCandidate]]:
    """Walk `<project_root>/doc/papers/*.md`, classify each file, return
    (candidates, failures). Skips already-promoted files and explicit non-paper
    kinds. Per-file failures become FailedCandidate records; the walk continues."""
    candidates: list[PromoteCandidate] = []
    failures: list[FailedCandidate] = []
    papers_dir = project_root / "doc" / "papers"
    if not papers_dir.is_dir():
        return candidates, failures

    for md_path in sorted(papers_dir.glob("*.md")):
        try:
            fm, body = _parse_paper_file(md_path)
        except PromoteCandidateError as exc:
            failures.append(
                FailedCandidate(
                    bibkey=md_path.stem,
                    project_slug=project_slug,
                    source_path=md_path,
                    error_class="PromoteCandidateError",
                    error_message=str(exc),
                )
            )
            continue

        if "overlay_of" in fm:
            continue  # already promoted; idempotent skip

        classification = _classify_paper_file_kind(fm)
        if classification == "skip-other-kind":
            logger.warning(
                "%s: kind/type is not 'paper'; skipping (explicit non-paper)",
                md_path,
            )
            continue
        if classification == "skip-other-id":
            logger.warning(
                "%s: id prefix is not 'paper:'; skipping (explicit non-paper id)",
                md_path,
            )
            continue

        bibkey_source = md_path.stem
        try:
            bibkey_normalized = _normalize_bibkey_for_match(bibkey_source)
        except PromoteCandidateError as exc:
            failures.append(
                FailedCandidate(
                    bibkey=bibkey_source,
                    project_slug=project_slug,
                    source_path=md_path,
                    error_class="PromoteCandidateError",
                    error_message=str(exc),
                )
            )
            continue

        # canonical_fields / project_only_fields / body splits are filled in
        # later by `_classify_entity` (Task 11). For now we stash raw frontmatter
        # + body so discovery is independent of merge-policy lookup.
        candidates.append(
            PromoteCandidate(
                bibkey=bibkey_source,
                bibkey_normalized=bibkey_normalized,
                project_slug=project_slug,
                project_root=project_root,
                overlay_source_path=md_path,
                canonical_fields={},
                project_only_fields={},
                canonical_body={},
                project_only_body={"__raw_frontmatter__": fm, "__raw_body__": body},
            )
        )

    return candidates, failures
```

Note: `project_only_body` is stashing `{"__raw_frontmatter__": fm, "__raw_body__": body}` as a temporary carrier. Task 11 (`_classify_entity`) will consume those keys and replace them with the real splits. This keeps discovery cheap (no merge-policy load) at the cost of one extra processing pass at plan time.

- [ ] **Step 4: Run tests to verify they pass**

```
cd science && uv run pytest tests/test_commons_promote_discovery.py -v
```

Expected: 7 new tests PASS (17 total in the file).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/commons/promote.py \
        science/tests/test_commons_promote_discovery.py
git commit -m "$(cat <<'EOF'
feat(commons/promote): _parse_paper_file + _scan_project_papers

Direct `doc/papers/*.md` walk: parse frontmatter+body, skip already-promoted
(overlay_of present), skip explicit non-paper kinds with a log warning, wrap
per-file failures as FailedCandidate without aborting the walk.

Raw frontmatter+body are stashed in PromoteCandidate.project_only_body under
sentinel keys for Task 11 to consume — avoids loading merge policy at
discovery time.

Refs docs/plans/2026-05-15-commons-promote-papers-design.md §6.3 step 2.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: Public — `discover_paper_candidates`

**Files:**
- Modify: `science/src/science_tool/commons/promote.py`
- Modify: `science/tests/test_commons_promote_discovery.py`

- [ ] **Step 1: Write the failing tests**

Append to `science/tests/test_commons_promote_discovery.py`:

```python
def test_discover_groups_by_normalized_bibkey(tmp_path, monkeypatch):
    from science_tool.commons.promote import discover_paper_candidates

    # Stand up two synthetic projects with a case-divergent overlap.
    proj_a = tmp_path / "proj_a"
    (proj_a / "doc" / "papers").mkdir(parents=True)
    (proj_a / "doc" / "papers" / "Huh2024.md").write_text(
        "---\nid: paper:Huh2024\ntitle: A\n---\n",
        encoding="utf-8",
    )
    proj_b = tmp_path / "proj_b"
    (proj_b / "doc" / "papers").mkdir(parents=True)
    (proj_b / "doc" / "papers" / "huh2024.md").write_text(
        "---\nid: paper:huh2024\ntitle: B\n---\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: {"proj_a": proj_a, "proj_b": proj_b}[slug],
    )

    result = discover_paper_candidates(["proj_a", "proj_b"])
    assert set(result.candidates_by_bibkey) == {"huh2024"}
    assert len(result.candidates_by_bibkey["huh2024"]) == 2
    assert result.failed_candidates == []


def test_discover_rejects_null_id_via_resolver(tmp_path, monkeypatch):
    from science_tool.commons.errors import CommonsError
    from science_tool.commons.promote import discover_paper_candidates

    def fake_resolve(slug: str):
        raise CommonsError(f"project {slug!r} is registered with id: null; ...")

    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id", fake_resolve
    )
    import pytest
    with pytest.raises(CommonsError, match="id: null"):
        discover_paper_candidates(["legacy-slug"])


def test_discover_carries_failures(tmp_path, monkeypatch):
    from science_tool.commons.promote import discover_paper_candidates

    proj = tmp_path / "proj"
    (proj / "doc" / "papers").mkdir(parents=True)
    (proj / "doc" / "papers" / "Good.md").write_text(
        "---\nid: paper:Good\ntitle: G\n---\n",
        encoding="utf-8",
    )
    (proj / "doc" / "papers" / "Broken.md").write_text(
        "no frontmatter\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: proj,
    )

    result = discover_paper_candidates(["proj"])
    assert set(result.candidates_by_bibkey) == {"good"}
    assert len(result.failed_candidates) == 1
    assert result.failed_candidates[0].source_path.name == "Broken.md"
```

- [ ] **Step 2: Run tests to verify they fail**

```
cd science && uv run pytest tests/test_commons_promote_discovery.py -v
```

Expected: FAIL — `discover_paper_candidates` is still `NotImplementedError`, OR `resolve_project_by_id` import missing in promote.py.

- [ ] **Step 3: Implement `discover_paper_candidates` + add the resolver import**

In `science/src/science_tool/commons/promote.py`, add at the top of the import block:

```python
from science_tool.commons.config import resolve_project_by_id
```

Replace the `discover_paper_candidates` stub with:

```python
def discover_paper_candidates(project_slugs: list[str]) -> DiscoveryResult:
    """Scan each project's `doc/papers/*.md` directly. Group by case-insensitive
    `bibkey_normalized`. Returns successful candidates + failure records."""
    grouped: dict[str, list[PromoteCandidate]] = {}
    failures: list[FailedCandidate] = []

    for slug in project_slugs:
        project_root = resolve_project_by_id(slug)  # raises CommonsError on bad slug
        candidates, project_failures = _scan_project_papers(project_root, slug)
        failures.extend(project_failures)
        for cand in candidates:
            grouped.setdefault(cand.bibkey_normalized, []).append(cand)

    return DiscoveryResult(candidates_by_bibkey=grouped, failed_candidates=failures)
```

- [ ] **Step 4: Run tests to verify they pass**

```
cd science && uv run pytest tests/test_commons_promote_discovery.py -v
```

Expected: all 20 tests in the file PASS.

- [ ] **Step 5: Run full science suite**

```
cd science && uv run pytest
```

Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/commons/promote.py \
        science/tests/test_commons_promote_discovery.py
git commit -m "$(cat <<'EOF'
feat(commons/promote): discover_paper_candidates public entry

Resolves each --from slug via resolve_project_by_id (id-based, rejects
null-id), walks doc/papers/ directly, groups by case-insensitive bibkey,
carries per-file failures forward in DiscoveryResult.

Refs docs/plans/2026-05-15-commons-promote-papers-design.md §5.1, §6.3 step 2.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 11: Classification — `_classify_entity`

**Files:**
- Modify: `science/src/science_tool/commons/promote.py`
- Create: `science/tests/test_commons_promote_plan.py`

This task takes a raw `(frontmatter, body)` and splits it into the four buckets that feed the canonical render and the overlay render: `canonical_fields`, `project_only_fields`, `canonical_body`, `project_only_body`.

- [ ] **Step 1: Write the failing tests**

Create `science/tests/test_commons_promote_plan.py`:

```python
"""Tests for science_tool.commons.promote — plan phase + helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from science_model.entity_schema import (
    MergePolicy,
    default_profile_for_kind,
    read_canonical_body_sections,
    read_merge_policy,
)
from science_tool.commons.promote import (
    PromoteCandidate,
    _classify_entity,
)


_PAPER_PROFILE = default_profile_for_kind("paper")
_PAPER_POLICY = read_merge_policy(_PAPER_PROFILE)
_PAPER_SECTIONS = read_canonical_body_sections(_PAPER_PROFILE)


def test_classify_entity_splits_canonical_vs_project_only():
    fm = {
        "id": "paper:Adams2025",
        "type": "paper",
        "title": "A title",
        "authors": ["Adams, J."],
        "year": 2025,
        "tags": ["foo", "bar"],
        "related": ["question:q1"],
        "status": "active",
        "created": "2026-01-01",
        "updated": "2026-05-15",
    }
    body = "## Key Findings\n\nfoo\n\n## Project Use\n\nbar\n"
    can_f, proj_f, can_b, proj_b = _classify_entity(
        fm, body, _PAPER_POLICY, _PAPER_SECTIONS
    )
    # Canonical surface gets: title, authors, year, id, type
    assert can_f["title"] == "A title"
    assert can_f["authors"] == ["Adams, J."]
    assert can_f["year"] == 2025
    # tags, related, status, created, updated → overlay (project_only/append on overlay side)
    assert "tags" in proj_f
    assert "related" in proj_f
    assert "status" in proj_f
    assert "created" in proj_f
    # Body splits by x-canonical-body-sections:
    assert "Key Findings" in can_b
    assert "Project Use" in proj_b


def test_classify_entity_coerces_string_authors_to_single_element_list():
    fm = {
        "id": "paper:X",
        "type": "paper",
        "title": "T",
        "authors": "Wang et al.",  # string, not list
    }
    can_f, _, _, _ = _classify_entity(fm, "", _PAPER_POLICY, _PAPER_SECTIONS)
    assert can_f["authors"] == ["Wang et al."]


def test_classify_entity_renames_journal_to_venue():
    fm = {"id": "paper:X", "type": "paper", "title": "T", "journal": "Cell"}
    can_f, _, _, _ = _classify_entity(fm, "", _PAPER_POLICY, _PAPER_SECTIONS)
    assert can_f.get("venue") == "Cell"
    assert "journal" not in can_f


def test_classify_entity_strips_overlay_only_keys_from_input():
    """overlay_of / pin_version on a source file (shouldn't happen for first-time
    promote, but be defensive) MUST NOT leak into either canonical or project-only."""
    fm = {
        "id": "paper:X",
        "type": "paper",
        "title": "T",
        "overlay_of": "paper:X",
        "pin_version": "1.0.0",
    }
    can_f, proj_f, _, _ = _classify_entity(fm, "", _PAPER_POLICY, _PAPER_SECTIONS)
    assert "overlay_of" not in can_f
    assert "overlay_of" not in proj_f
    assert "pin_version" not in can_f
    assert "pin_version" not in proj_f


def test_classify_entity_body_section_match_is_case_insensitive():
    fm = {"id": "paper:X", "type": "paper", "title": "T"}
    body = "## key findings\n\nlowercase heading\n"
    _, _, can_b, _ = _classify_entity(fm, body, _PAPER_POLICY, _PAPER_SECTIONS)
    # The canonical bucket uses the original-case heading from the section list,
    # but matches the source heading case-insensitively.
    assert any(k.casefold() == "key findings" for k in can_b)
```

- [ ] **Step 2: Run tests to verify they fail**

```
cd science && uv run pytest tests/test_commons_promote_plan.py -v
```

Expected: FAIL — `ImportError: cannot import name '_classify_entity'`.

- [ ] **Step 3: Implement `_classify_entity` + body splitter**

Append to `science/src/science_tool/commons/promote.py`:

```python
# Overlay-only fields that MUST never leak onto the canonical or project-only
# field dicts (the overlay-rewrite step writes these directly).
_OVERLAY_ONLY_KEYS: frozenset[str] = frozenset({"overlay_of", "pin_version", "pin_effective_version"})

# Base-required fields that the promote tool generates (NOT copied from source).
_GENERATED_BY_PROMOTE_KEYS: frozenset[str] = frozenset(
    {"schema_profile", "version", "created", "updated"}
)


def _split_body_by_headings(body: str) -> dict[str, str]:
    """Parse a markdown body into `{heading: content_after_heading}`.

    Only `## ` (level-2) headings are tracked. Content before the first `## ` is
    keyed as `""` (the empty string). Sub-headings (`###` etc.) stay inside
    whichever level-2 section contains them.
    """
    sections: dict[str, list[str]] = {"": []}
    current = ""
    for line in body.splitlines():
        if line.startswith("## ") and not line.startswith("### "):
            current = line[3:].strip()
            sections.setdefault(current, [])
            continue
        sections[current].append(line)
    return {heading: "\n".join(lines) for heading, lines in sections.items() if lines or heading}


def _classify_entity(
    frontmatter: dict,
    body: str,
    merge_policy: dict[str, "MergePolicy"],
    canonical_body_sections: list[str],
) -> tuple[dict, dict, dict[str, str], dict[str, str]]:
    """Split (frontmatter, body) into (canonical_fields, project_only_fields,
    canonical_body, project_only_body).

    - Promote-generated fields (schema_profile, version, created, updated) are
      NOT copied from source; the canonical writer fills them.
    - Overlay-management fields (overlay_of, pin_version) NEVER appear on either
      side (they're written by the overlay renderer alone).
    - For every remaining source field, the merge policy decides:
        REPLACE / APPEND / FORBIDDEN → canonical bucket
        PROJECT_ONLY                  → project-only bucket
        no policy entry               → conservative default: project-only
    - `authors` is coerced to list[str] if it arrives as a string.
    - `journal` is renamed to `venue` (one-time coercion).
    """
    from science_model.entity_schema import MergePolicy

    canonical: dict = {}
    project_only: dict = {}
    for key, value in frontmatter.items():
        if key in _OVERLAY_ONLY_KEYS:
            continue
        if key in _GENERATED_BY_PROMOTE_KEYS and key not in ("created", "updated"):
            # created/updated still flow to project_only (mixin override); the
            # canonical's created/updated are set by promote.
            continue
        if key == "journal":
            canonical["venue"] = value
            continue
        if key == "authors" and not isinstance(value, list):
            canonical["authors"] = [str(value)]
            continue
        policy = merge_policy.get(key, MergePolicy.PROJECT_ONLY)
        if policy == MergePolicy.PROJECT_ONLY:
            project_only[key] = value
        else:
            canonical[key] = value

    # Body split: lowercase-compare each heading against canonical_body_sections.
    raw_body_sections = _split_body_by_headings(body)
    canonical_set = {s.casefold() for s in canonical_body_sections}
    canonical_body: dict[str, str] = {}
    project_only_body: dict[str, str] = {}
    for heading, content in raw_body_sections.items():
        if heading == "":
            # Untitled prose before the first ## heading lives only on the overlay.
            project_only_body[""] = content
            continue
        if heading.casefold() in canonical_set:
            canonical_body[heading] = content
        else:
            project_only_body[heading] = content

    return canonical, project_only, canonical_body, project_only_body
```

- [ ] **Step 4: Run tests to verify they pass**

```
cd science && uv run pytest tests/test_commons_promote_plan.py -v
```

Expected: all five new tests PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/commons/promote.py \
        science/tests/test_commons_promote_plan.py
git commit -m "$(cat <<'EOF'
feat(commons/promote): _classify_entity field/body splitter

Reads merge policy to split frontmatter into canonical vs project-only;
splits body by ## headings against x-canonical-body-sections; strips
overlay-management keys; coerces string authors to single-element list;
renames journal → venue.

Refs docs/plans/2026-05-15-commons-promote-papers-design.md §4.1, §4.2, §4.3.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 12: Merging — `_merge_canonical_fields`, `_pick_canonical_bibkey_case`

**Files:**
- Modify: `science/src/science_tool/commons/promote.py`
- Modify: `science/tests/test_commons_promote_plan.py`

- [ ] **Step 1: Write the failing tests**

Append to `science/tests/test_commons_promote_plan.py`:

```python
def test_merge_canonical_fields_one_sided_auto_takes():
    from science_tool.commons.promote import _merge_canonical_fields, PromoteCandidate

    def _cand(slug, fields):
        return PromoteCandidate(
            bibkey="X", bibkey_normalized="x", project_slug=slug,
            project_root=Path("/tmp"), overlay_source_path=Path("/tmp/x.md"),
            canonical_fields=fields, project_only_fields={},
            canonical_body={}, project_only_body={},
        )

    a = _cand("A", {"title": "T", "authors": ["a"]})
    b = _cand("B", {"title": "T", "doi": "10.x"})  # b has doi, a does not

    merged, conflicts = _merge_canonical_fields([a, b], _PAPER_POLICY)
    assert merged["title"] == "T"
    assert merged["authors"] == ["a"]
    assert merged["doi"] == "10.x"
    assert conflicts == []


def test_merge_canonical_fields_identical_auto_takes():
    from science_tool.commons.promote import _merge_canonical_fields, PromoteCandidate

    def _cand(slug, fields):
        return PromoteCandidate(
            bibkey="X", bibkey_normalized="x", project_slug=slug,
            project_root=Path("/tmp"), overlay_source_path=Path("/tmp/x.md"),
            canonical_fields=fields, project_only_fields={},
            canonical_body={}, project_only_body={},
        )

    a = _cand("A", {"year": 2025})
    b = _cand("B", {"year": 2025})
    merged, conflicts = _merge_canonical_fields([a, b], _PAPER_POLICY)
    assert merged["year"] == 2025
    assert conflicts == []


def test_merge_canonical_fields_emits_conflict_on_differing_values():
    from science_tool.commons.promote import _merge_canonical_fields, PromoteCandidate

    def _cand(slug, fields):
        return PromoteCandidate(
            bibkey="X", bibkey_normalized="x", project_slug=slug,
            project_root=Path("/tmp"), overlay_source_path=Path("/tmp/x.md"),
            canonical_fields=fields, project_only_fields={},
            canonical_body={}, project_only_body={},
        )

    a = _cand("A", {"year": 2023})
    b = _cand("B", {"year": 2024})
    merged, conflicts = _merge_canonical_fields([a, b], _PAPER_POLICY)
    assert "year" not in merged
    assert len(conflicts) == 1
    assert conflicts[0].field == "year"
    assert conflicts[0].candidates == {"A": 2023, "B": 2024}


def test_merge_canonical_fields_append_unions_deterministically():
    from science_tool.commons.promote import _merge_canonical_fields, PromoteCandidate

    def _cand(slug, fields):
        return PromoteCandidate(
            bibkey="X", bibkey_normalized="x", project_slug=slug,
            project_root=Path("/tmp"), overlay_source_path=Path("/tmp/x.md"),
            canonical_fields=fields, project_only_fields={},
            canonical_body={}, project_only_body={},
        )

    a = _cand("A", {"ontology_terms": ["foo", "bar"], "datasets": ["dataset:d1"]})
    b = _cand("B", {"ontology_terms": ["bar", "baz"], "datasets": ["dataset:d2", "dataset:d1"]})
    merged, conflicts = _merge_canonical_fields([a, b], _PAPER_POLICY)
    assert merged["ontology_terms"] == ["bar", "baz", "foo"]  # sorted, deduped
    assert merged["datasets"] == ["dataset:d1", "dataset:d2"]
    assert conflicts == []


def test_pick_canonical_bibkey_case_from_order_first():
    from science_tool.commons.promote import _pick_canonical_bibkey_case, PromoteCandidate

    def _cand(slug, bibkey):
        return PromoteCandidate(
            bibkey=bibkey, bibkey_normalized=bibkey.casefold(),
            project_slug=slug, project_root=Path("/tmp"),
            overlay_source_path=Path("/tmp/x.md"),
            canonical_fields={}, project_only_fields={},
            canonical_body={}, project_only_body={},
        )

    cands = [_cand("B", "huh2024"), _cand("A", "Huh2024")]
    # from_order = ["A", "B"] — A appears first → A's case wins.
    assert _pick_canonical_bibkey_case(cands, ["A", "B"]) == "Huh2024"
    # Reversed --from order:
    assert _pick_canonical_bibkey_case(cands, ["B", "A"]) == "huh2024"


def test_pick_canonical_bibkey_case_tiebreaks_by_slug():
    from science_tool.commons.promote import _pick_canonical_bibkey_case, PromoteCandidate

    def _cand(slug, bibkey):
        return PromoteCandidate(
            bibkey=bibkey, bibkey_normalized=bibkey.casefold(),
            project_slug=slug, project_root=Path("/tmp"),
            overlay_source_path=Path("/tmp/x.md"),
            canonical_fields={}, project_only_fields={},
            canonical_body={}, project_only_body={},
        )

    # Both projects appear once each in from_order; tie-break by lexical slug.
    cands = [_cand("z-proj", "huh2024"), _cand("a-proj", "Huh2024")]
    assert _pick_canonical_bibkey_case(cands, ["a-proj", "z-proj"]) == "Huh2024"
```

- [ ] **Step 2: Run tests to verify they fail**

```
cd science && uv run pytest tests/test_commons_promote_plan.py -v
```

Expected: FAIL — `ImportError`.

- [ ] **Step 3: Implement the merge + case-pick helpers**

Append to `science/src/science_tool/commons/promote.py`:

```python
def _merge_canonical_fields(
    candidates: list[PromoteCandidate],
    merge_policy: dict[str, "MergePolicy"],
) -> tuple[dict, list[FieldConflict]]:
    """Merge canonical_fields across N candidates of the same bibkey.

    Rule per field (driven by merge_policy lookup):
    - APPEND: union of all candidates' lists, sorted + deduped.
    - Anything else (REPLACE / FORBIDDEN / no entry):
      - if no candidate has the field → omitted.
      - if all candidates agree (equal values) → that value.
      - if candidates disagree → field omitted from `merged`; a FieldConflict
        with `{slug: value}` for every candidate that has the field is appended.
    """
    from science_model.entity_schema import MergePolicy

    all_keys = {key for c in candidates for key in c.canonical_fields}
    merged: dict = {}
    conflicts: list[FieldConflict] = []

    for key in sorted(all_keys):
        present = [c for c in candidates if key in c.canonical_fields]
        policy = merge_policy.get(key, MergePolicy.REPLACE)
        if policy == MergePolicy.APPEND:
            union: set = set()
            for c in present:
                v = c.canonical_fields[key]
                if isinstance(v, list):
                    union.update(v)
                else:
                    union.add(v)
            merged[key] = sorted(union)
            continue

        values = [c.canonical_fields[key] for c in present]
        if all(v == values[0] for v in values):
            merged[key] = values[0]
        else:
            conflicts.append(
                FieldConflict(
                    bibkey=present[0].bibkey,
                    field=key,
                    candidates={c.project_slug: c.canonical_fields[key] for c in present},
                )
            )

    return merged, conflicts


def _pick_canonical_bibkey_case(
    candidates: list[PromoteCandidate],
    from_order: list[str],
) -> str:
    """Pick the canonical bibkey case from a multi-instance group.

    Rule (design §4.1.3):
    1. Walk from_order; the first project_slug with a matching candidate wins.
    2. If two candidates share the earliest slug (impossible in practice but
       defensive) or from_order is empty, tie-break by lexical project_slug.
    """
    order = {slug: idx for idx, slug in enumerate(from_order)}
    sorted_by_order = sorted(
        candidates,
        key=lambda c: (order.get(c.project_slug, len(order)), c.project_slug),
    )
    return sorted_by_order[0].bibkey
```

- [ ] **Step 4: Run tests to verify they pass**

```
cd science && uv run pytest tests/test_commons_promote_plan.py -v
```

Expected: all six new tests PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/commons/promote.py \
        science/tests/test_commons_promote_plan.py
git commit -m "$(cat <<'EOF'
feat(commons/promote): merge + case-pick helpers

_merge_canonical_fields: APPEND fields union deterministically; REPLACE fields
auto-take when one-sided or identical, emit FieldConflict on disagreement.
_pick_canonical_bibkey_case: --from order wins, lexical slug as tie-break.

Refs docs/plans/2026-05-15-commons-promote-papers-design.md §4.1.3, §6.3 step 3.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 13: Rendering — `_coerce_date_for_yaml`, `_render_canonical`, `_render_overlay`

**Files:**
- Modify: `science/src/science_tool/commons/promote.py`
- Modify: `science/tests/test_commons_promote_plan.py`

- [ ] **Step 1: Write the failing tests**

Append to `science/tests/test_commons_promote_plan.py`:

```python
from datetime import date, datetime


def test_coerce_date_for_yaml():
    from science_tool.commons.promote import _coerce_date_for_yaml
    assert _coerce_date_for_yaml(date(2026, 5, 15)) == "2026-05-15"
    assert _coerce_date_for_yaml(datetime(2026, 5, 15, 12, 30)) == "2026-05-15"
    assert _coerce_date_for_yaml("2026-05-15") == "2026-05-15"
    assert _coerce_date_for_yaml("already-not-a-date") == "already-not-a-date"


def test_render_canonical_includes_base_required_fields():
    from science_tool.commons.promote import _render_canonical, PromoteDecision

    decision = PromoteDecision(
        bibkey="Adams2025",
        canonical_path=Path("/c/papers/Adams2025.md"),
        canonical_content="",  # unused by the renderer
        canonical_version="1.0.0",
        overlays={},
        resolved_conflicts=(),
    )
    rendered = _render_canonical(
        decision,
        canonical_fields={"title": "T", "authors": ["A"], "year": 2025},
        canonical_body={"Key Findings": "\nOne.\n"},
        created=date(2026, 5, 15),
        updated=date(2026, 5, 15),
    )
    assert "schema_profile: science-entity-base/1.0+paper/2.0" in rendered
    assert "version: \"1.0.0\"" in rendered or 'version: "1.0.0"' in rendered
    assert "id: paper:Adams2025" in rendered
    assert "type: paper" in rendered
    assert "title: T" in rendered
    assert 'created: "2026-05-15"' in rendered
    assert "tags: []" in rendered
    assert "## Key Findings" in rendered
    assert "One." in rendered


def test_render_canonical_dates_are_quoted_strings():
    from science_tool.commons.promote import _render_canonical, PromoteDecision
    import yaml

    decision = PromoteDecision(
        bibkey="X",
        canonical_path=Path("/c/papers/X.md"),
        canonical_content="",
        canonical_version="1.0.0",
        overlays={},
        resolved_conflicts=(),
    )
    rendered = _render_canonical(
        decision,
        canonical_fields={"title": "T"},
        canonical_body={},
        created=date(2026, 5, 15),
        updated=date(2026, 5, 15),
    )
    # Reparse the frontmatter via safe_load — created should come back as a
    # string, not a datetime.date.
    fm_block = rendered.split("---", 2)[1]
    fm = yaml.safe_load(fm_block)
    assert isinstance(fm["created"], str)
    assert fm["created"] == "2026-05-15"


def test_render_overlay_preserves_project_dates_and_overlay_fields():
    from science_tool.commons.promote import _render_overlay, PromoteDecision

    decision = PromoteDecision(
        bibkey="Adams2025",
        canonical_path=Path("/c/papers/Adams2025.md"),
        canonical_content="",
        canonical_version="1.0.0",
        overlays={},
        resolved_conflicts=(),
    )
    rendered = _render_overlay(
        decision,
        project_slug="natural-systems",
        project_only_fields={
            "tags": ["foo", "bar"],
            "status": "active",
            "created": "2026-01-01",
            "updated": "2026-05-15",
            "related": ["question:q1"],
        },
        project_only_body={"Project Use": "\nused here\n"},
    )
    assert "id: paper:Adams2025" in rendered
    assert "overlay_of: paper:Adams2025" in rendered
    assert "pin_version: \"1.0.0\"" in rendered or 'pin_version: "1.0.0"' in rendered
    assert 'created: "2026-01-01"' in rendered
    assert 'updated: "2026-05-15"' in rendered
    assert "## Project Use" in rendered
    assert "schema_profile" not in rendered  # NEVER on overlay
```

- [ ] **Step 2: Run tests to verify they fail**

```
cd science && uv run pytest tests/test_commons_promote_plan.py -v
```

Expected: FAIL.

- [ ] **Step 3: Implement the renderers**

Append to `science/src/science_tool/commons/promote.py`:

```python
from datetime import date, datetime

from science_model.entity_schema import default_profile_for_kind


def _coerce_date_for_yaml(value: Any) -> str:
    """`datetime.date` / `datetime.datetime` / `str` → ISO-8601 string. Other
    types are returned as-is via `str(value)`."""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


_DATE_KEYS: frozenset[str] = frozenset({"created", "updated"})


def _render_frontmatter(fields: dict) -> str:
    """Render an ordered, deterministic YAML frontmatter block.

    Date fields go through `_coerce_date_for_yaml` and are quoted; lists are
    block style; strings are double-quoted only when they look ambiguous.
    """
    import yaml

    out: dict = {}
    for key, value in fields.items():
        if key in _DATE_KEYS:
            out[key] = _coerce_date_for_yaml(value)
        else:
            out[key] = value
    dumped = yaml.safe_dump(
        out,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
        width=10_000,
    )
    # Force quoting of date scalars — pyyaml sometimes emits unquoted. We do a
    # one-pass line rewrite for the two date keys; their values are already
    # known to be strings from the coercion above.
    lines = []
    for line in dumped.splitlines():
        for k in _DATE_KEYS:
            prefix = f"{k}:"
            if line.startswith(prefix) and not line[len(prefix):].lstrip().startswith('"'):
                val = line[len(prefix):].strip()
                if val and val != "null":
                    line = f'{k}: "{val}"'
        lines.append(line)
    return "\n".join(lines) + "\n"


def _render_body(sections: dict[str, str]) -> str:
    """Render `{heading: content}` back to markdown. Empty heading "" goes first
    (intro prose); the rest are emitted in insertion order with `## ` prefix."""
    parts: list[str] = []
    if "" in sections:
        intro = sections[""].strip("\n")
        if intro:
            parts.append(intro + "\n")
    for heading, content in sections.items():
        if heading == "":
            continue
        parts.append(f"## {heading}\n{content.rstrip()}\n")
    return "\n".join(parts)


def _render_canonical(
    decision: PromoteDecision,
    *,
    canonical_fields: dict,
    canonical_body: dict[str, str],
    created: date,
    updated: date,
) -> str:
    """Render the commons-side papers/<bibkey>.md content.

    Fills base-required fields (schema_profile, version, created, updated) and
    always emits `tags: []` so the per-project overlay-merge produces only the
    project's overlay tags (design §4.1.2).
    """
    profile_str = default_profile_for_kind("paper").render()
    head: dict = {
        "schema_profile": profile_str,
        "id": f"paper:{decision.bibkey}",
        "type": "paper",
        "title": canonical_fields.get("title", ""),
        "version": decision.canonical_version,
        "created": _coerce_date_for_yaml(created),
        "updated": _coerce_date_for_yaml(updated),
        "bibkey": decision.bibkey,
        "tags": [],
    }
    # Merge in any remaining canonical fields (excluding head-priority keys).
    for k, v in canonical_fields.items():
        if k in head:
            continue
        head[k] = v

    fm = _render_frontmatter(head)
    body = _render_body(canonical_body)
    return f"---\n{fm}---\n{body}"


def _render_overlay(
    decision: PromoteDecision,
    *,
    project_slug: str,
    project_only_fields: dict,
    project_only_body: dict[str, str],
) -> str:
    """Render a project-side overlay file. NEVER emits schema_profile; the
    overlay validator is hardcoded to overlay/1.1 (design §4.4)."""
    head: dict = {
        "id": f"paper:{decision.bibkey}",
        "overlay_of": f"paper:{decision.bibkey}",
        "pin_version": decision.canonical_version,
    }
    for k, v in project_only_fields.items():
        if k in _OVERLAY_ONLY_KEYS:
            continue
        head[k] = v

    fm = _render_frontmatter(head)
    # Force-quote pin_version like a date scalar (it's a string but pyyaml
    # may emit it unquoted in semver form).
    fm_lines = []
    for line in fm.splitlines():
        if line.startswith("pin_version:") and not line.split(":", 1)[1].lstrip().startswith('"'):
            v = line.split(":", 1)[1].strip()
            line = f'pin_version: "{v}"'
        fm_lines.append(line)
    fm = "\n".join(fm_lines) + "\n"

    body = _render_body(project_only_body)
    return f"---\n{fm}---\n{body}"
```

- [ ] **Step 4: Run tests to verify they pass**

```
cd science && uv run pytest tests/test_commons_promote_plan.py -v
```

Expected: all four new render tests PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/commons/promote.py \
        science/tests/test_commons_promote_plan.py
git commit -m "$(cat <<'EOF'
feat(commons/promote): canonical + overlay renderers

_render_canonical emits schema_profile / version / created / updated / tags:[]
plus the merged canonical fields. _render_overlay emits id / overlay_of /
pin_version plus project-only fields; never emits schema_profile.

All date scalars (created/updated) are written as quoted ISO-8601 strings to
satisfy schema validation round-trip via safe_load.

Refs docs/plans/2026-05-15-commons-promote-papers-design.md §4.1.1, §4.1.4.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 14: Public — `prompt_resolve`, `plan_promote`

**Files:**
- Modify: `science/src/science_tool/commons/promote.py`
- Modify: `science/tests/test_commons_promote_plan.py`

- [ ] **Step 1: Write the failing tests**

Append to `science/tests/test_commons_promote_plan.py`:

```python
def test_plan_promote_groups_by_bibkey_and_carries_failures(tmp_path):
    from science_tool.commons.promote import (
        DiscoveryResult,
        FailedCandidate,
        plan_promote,
    )

    def _cand(slug, bibkey, fields):
        return PromoteCandidate(
            bibkey=bibkey, bibkey_normalized=bibkey.casefold(),
            project_slug=slug, project_root=Path("/tmp") / slug,
            overlay_source_path=Path("/tmp") / slug / "doc/papers" / f"{bibkey}.md",
            canonical_fields={}, project_only_fields={},
            canonical_body={},
            project_only_body={
                "__raw_frontmatter__": {"id": f"paper:{bibkey}", "type": "paper",
                                        "title": "T", **fields},
                "__raw_body__": "",
            },
        )

    discovery = DiscoveryResult(
        candidates_by_bibkey={
            "adams2025": [_cand("A", "Adams2025", {"year": 2025})],
        },
        failed_candidates=[
            FailedCandidate(bibkey="x", project_slug="A", source_path=Path("/x"),
                            error_class="PromoteCandidateError", error_message="bad")
        ],
    )

    plan = plan_promote(discovery, commons_root=tmp_path, resolve_conflict=lambda c: None)
    assert len(plan.decisions) == 1
    assert plan.decisions[0].bibkey == "Adams2025"
    # Failure carried through:
    assert len(plan.failed_candidates) == 1
    assert plan.failed_candidates[0].error_class == "PromoteCandidateError"


def test_plan_promote_invokes_resolver_on_conflict(tmp_path):
    from science_tool.commons.promote import (
        DiscoveryResult,
        plan_promote,
    )

    def _cand(slug, year):
        return PromoteCandidate(
            bibkey="Dang2023", bibkey_normalized="dang2023",
            project_slug=slug, project_root=Path("/tmp") / slug,
            overlay_source_path=Path("/tmp") / slug / "doc/papers/Dang2023.md",
            canonical_fields={}, project_only_fields={}, canonical_body={},
            project_only_body={
                "__raw_frontmatter__": {
                    "id": "paper:Dang2023", "type": "paper",
                    "title": "T", "year": year,
                },
                "__raw_body__": "",
            },
        )

    discovery = DiscoveryResult(
        candidates_by_bibkey={"dang2023": [_cand("A", 2023), _cand("B", 2024)]},
        failed_candidates=[],
    )

    resolved: list = []
    def picker(conflict):
        resolved.append(conflict.field)
        # Always pick A's value:
        return conflict.candidates["A"]

    plan = plan_promote(discovery, commons_root=tmp_path, resolve_conflict=picker)
    assert resolved == ["year"]
    decision = plan.decisions[0]
    assert len(decision.resolved_conflicts) == 1
    assert decision.resolved_conflicts[0].resolved_to == 2023


def test_plan_promote_case_collision_picks_first_from_order(tmp_path):
    from science_tool.commons.promote import DiscoveryResult, plan_promote

    def _cand(slug, bibkey):
        return PromoteCandidate(
            bibkey=bibkey, bibkey_normalized=bibkey.casefold(),
            project_slug=slug, project_root=Path("/tmp") / slug,
            overlay_source_path=Path("/tmp") / slug / "doc/papers" / f"{bibkey}.md",
            canonical_fields={}, project_only_fields={}, canonical_body={},
            project_only_body={
                "__raw_frontmatter__": {
                    "id": f"paper:{bibkey}", "type": "paper", "title": "T",
                },
                "__raw_body__": "",
            },
        )

    discovery = DiscoveryResult(
        candidates_by_bibkey={"huh2024": [_cand("A", "Huh2024"), _cand("B", "huh2024")]},
        failed_candidates=[],
    )
    plan = plan_promote(discovery, commons_root=tmp_path, resolve_conflict=lambda c: None,
                        from_order=["A", "B"])
    assert plan.decisions[0].bibkey == "Huh2024"
    # B's overlay records a rename:
    b_overlay = plan.decisions[0].overlays["B"]
    assert b_overlay.rename_from is not None
    assert b_overlay.rename_from.name == "huh2024.md"
    assert b_overlay.path.name == "Huh2024.md"
```

- [ ] **Step 2: Run tests to verify they fail**

```
cd science && uv run pytest tests/test_commons_promote_plan.py -v
```

Expected: FAIL — `plan_promote` is still `NotImplementedError`.

- [ ] **Step 3: Implement `prompt_resolve` + replace the `plan_promote` stub**

In `science/src/science_tool/commons/promote.py`, **delete the existing `plan_promote` stub** (the one raising `NotImplementedError` from Task 7) and append:

```python
import click

from science_tool.commons.errors import PromoteConflictAbort


def prompt_resolve(conflict: FieldConflict) -> Any:
    """Interactive terminal prompt — the default `resolve_conflict` callback.

    UI mirrors design §7.1. Returns the resolved value (a candidate value, a
    user-entered manual value, or raises `PromoteConflictAbort` on 'a' / Ctrl-C).
    """
    click.echo(f'\nConflict for paper:{conflict.bibkey}, field "{conflict.field}":')
    ordered = sorted(conflict.candidates.items())  # deterministic numbering
    for idx, (slug, value) in enumerate(ordered, start=1):
        click.echo(f"  [{idx}] {slug}: {value!r}")
    click.echo(f"  [{len(ordered) + 1}] enter value manually")
    click.echo(f"  [a] abort batch")
    while True:
        try:
            choice = click.prompt(
                f"Choose [1-{len(ordered) + 1}/a]",
                type=str,
                show_default=False,
            ).strip()
        except (click.Abort, KeyboardInterrupt):
            raise PromoteConflictAbort("user aborted at conflict prompt")
        if choice.lower() == "a":
            raise PromoteConflictAbort("user chose 'abort batch' at conflict prompt")
        try:
            n = int(choice)
        except ValueError:
            click.echo("invalid selection")
            continue
        if 1 <= n <= len(ordered):
            return ordered[n - 1][1]
        if n == len(ordered) + 1:
            return click.prompt("Manual value", type=str)
        click.echo("out of range")


def plan_promote(
    discovery: DiscoveryResult,
    commons_root: Path,
    *,
    resolve_conflict: Callable[[FieldConflict], Any] | None = None,
    from_order: list[str] | None = None,
) -> PromotePlan:
    """Build a PromotePlan from a DiscoveryResult.

    For each bibkey group:
      1. Run `_classify_entity` per candidate (consumes the raw frontmatter/body
         stashed by discovery in `project_only_body.__raw_*__`).
      2. Pick canonical bibkey case via `_pick_canonical_bibkey_case`.
      3. Merge canonical fields → `(merged_fields, conflicts)`.
      4. Resolve each conflict via `resolve_conflict`.
      5. Build PromoteDecision (canonical_content rendered, overlays planned).

    `from_order` defaults to the discovery's project_slug encounter order.
    `resolve_conflict` defaults to `prompt_resolve`.
    """
    if resolve_conflict is None:
        resolve_conflict = prompt_resolve

    paper_profile = default_profile_for_kind("paper")
    merge_policy = read_merge_policy(paper_profile)
    body_sections = read_canonical_body_sections(paper_profile)

    if from_order is None:
        from_order = []
        seen_slugs: set[str] = set()
        for cands in discovery.candidates_by_bibkey.values():
            for c in cands:
                if c.project_slug not in seen_slugs:
                    from_order.append(c.project_slug)
                    seen_slugs.add(c.project_slug)

    decisions: list[PromoteDecision] = []
    soft_failures: list[FailedCandidate] = list(discovery.failed_candidates)

    for bibkey_norm in sorted(discovery.candidates_by_bibkey):
        raw_group = discovery.candidates_by_bibkey[bibkey_norm]

        # Step 1: re-classify each candidate from the stashed raw payload.
        classified: list[PromoteCandidate] = []
        for c in raw_group:
            raw_fm = c.project_only_body.get("__raw_frontmatter__")
            raw_body = c.project_only_body.get("__raw_body__", "")
            if not isinstance(raw_fm, dict):
                soft_failures.append(
                    FailedCandidate(
                        bibkey=c.bibkey, project_slug=c.project_slug,
                        source_path=c.overlay_source_path,
                        error_class="PromoteCandidateError",
                        error_message="discovery payload missing raw frontmatter",
                    )
                )
                continue
            can_f, proj_f, can_b, proj_b = _classify_entity(
                raw_fm, raw_body, merge_policy, body_sections,
            )
            classified.append(
                PromoteCandidate(
                    bibkey=c.bibkey,
                    bibkey_normalized=c.bibkey_normalized,
                    project_slug=c.project_slug,
                    project_root=c.project_root,
                    overlay_source_path=c.overlay_source_path,
                    canonical_fields=can_f,
                    project_only_fields=proj_f,
                    canonical_body=can_b,
                    project_only_body=proj_b,
                )
            )

        if not classified:
            continue

        canonical_case = _pick_canonical_bibkey_case(classified, from_order)
        merged, conflicts = _merge_canonical_fields(classified, merge_policy)

        resolved_conflicts: list[ConflictResolution] = []
        for conflict in conflicts:
            resolved_value = resolve_conflict(conflict)
            source_project = next(
                (slug for slug, v in conflict.candidates.items() if v == resolved_value),
                None,
            )
            resolved_conflicts.append(
                ConflictResolution(
                    bibkey=canonical_case,
                    field=conflict.field,
                    candidates=conflict.candidates,
                    resolved_to=resolved_value,
                    source_project=source_project,
                )
            )
            merged[conflict.field] = resolved_value

        # Build overlay rewrite plans (one per project that contributed).
        canonical_path = commons_root / "papers" / f"{canonical_case}.md"
        overlays: dict[str, OverlayRewrite] = {}
        for c in classified:
            source_path = c.overlay_source_path
            target_path = source_path.parent / f"{canonical_case}.md"
            rename_from = source_path if source_path.name != target_path.name else None
            rendered_overlay = _render_overlay(
                PromoteDecision(
                    bibkey=canonical_case,
                    canonical_path=canonical_path,
                    canonical_content="",
                    canonical_version="1.0.0",
                    overlays={},
                    resolved_conflicts=(),
                ),
                project_slug=c.project_slug,
                project_only_fields=c.project_only_fields,
                project_only_body=c.project_only_body,
            )
            overlays[c.project_slug] = OverlayRewrite(
                project_slug=c.project_slug,
                path=target_path,
                before_sha="",          # filled in at apply time
                after_content=rendered_overlay,
                pin_version="1.0.0",
                rename_from=rename_from,
            )

        # Render canonical now (apply uses this content verbatim).
        canonical_decision = PromoteDecision(
            bibkey=canonical_case,
            canonical_path=canonical_path,
            canonical_content="",
            canonical_version="1.0.0",
            overlays=overlays,
            resolved_conflicts=tuple(resolved_conflicts),
        )
        canonical_content = _render_canonical(
            canonical_decision,
            canonical_fields=merged,
            canonical_body=classified[0].canonical_body,  # canonical body wins from first
            created=date.today(),
            updated=date.today(),
        )
        decisions.append(
            PromoteDecision(
                bibkey=canonical_case,
                canonical_path=canonical_path,
                canonical_content=canonical_content,
                canonical_version="1.0.0",
                overlays=overlays,
                resolved_conflicts=tuple(resolved_conflicts),
            )
        )

    return PromotePlan(decisions=decisions, failed_candidates=soft_failures)
```

Also add to the imports at the top:

```python
from science_model.entity_schema import (
    default_profile_for_kind,
    read_canonical_body_sections,
    read_merge_policy,
)
```

(consolidate with the existing `default_profile_for_kind` import if you added it in Task 13.)

- [ ] **Step 4: Run tests to verify they pass**

```
cd science && uv run pytest tests/test_commons_promote_plan.py -v
```

Expected: all 18 tests in this file PASS.

- [ ] **Step 5: Run full science suite**

```
cd science && uv run pytest
```

Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/commons/promote.py \
        science/tests/test_commons_promote_plan.py
git commit -m "$(cat <<'EOF'
feat(commons/promote): plan_promote + prompt_resolve

plan_promote re-classifies each candidate, picks canonical case from --from
order, auto-unions fields where one-sided or identical, invokes
resolve_conflict only on real disagreements, plans per-project overlay
rewrites with rename detection. prompt_resolve is the default interactive
terminal callback.

Refs docs/plans/2026-05-15-commons-promote-papers-design.md §5.1, §7.1.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 15: Audit + rollback — `_write_audit_log`, `_rollback_step5`

**Files:**
- Modify: `science/src/science_tool/commons/promote.py`
- Create: `science/tests/test_commons_promote_apply.py`

These are the building blocks the next two tasks (apply happy path, apply failure paths) compose. Doing them first keeps Task 16 and 17 focused on orchestration.

- [ ] **Step 1: Write the failing tests**

Create `science/tests/test_commons_promote_apply.py`:

```python
"""Tests for science_tool.commons.promote — apply phase, audit log, rollback."""

from __future__ import annotations

import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml


def _init_repo(root: Path) -> None:
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.email", "test@x"], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.name", "test"], check=True)


def _init_commons(root: Path) -> None:
    _init_repo(root)
    (root / "papers").mkdir()
    (root / ".migrations").mkdir()
    (root / ".gitignore").write_text("registry.sqlite\n.registry-*.sqlite\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-q", "-m", "init"], check=True)


def test_write_audit_log_writes_yaml_with_expected_shape(tmp_path):
    from science_tool.commons.promote import (
        PromoteResult,
        _write_audit_log,
    )

    _init_commons(tmp_path)
    result = PromoteResult(
        op_id="7a3f2c91",
        started_at=datetime(2026, 5, 15, 14, 30, 11, tzinfo=timezone.utc),
        finished_at=datetime(2026, 5, 15, 14, 30, 47, tzinfo=timezone.utc),
        commons_commit="abc1234",
        tags_created=["paper/Adams2025/1.0.0"],
        decisions=[],
        failed_candidates=[],
        audit_log_path=None,
        status="ok",
        failure_stage=None,
        failure_detail=None,
    )
    path = _write_audit_log(result, tmp_path, invocation="science commons promote paper --apply")
    assert path.exists()
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert data["op_id"] == "7a3f2c91"
    assert data["status"] == "ok"
    assert data["commons_commit"] == "abc1234"
    assert data["commons_tags"] == ["paper/Adams2025/1.0.0"]
    assert "rollback" in data


def test_rollback_step5_deletes_tags_and_restores_path_limited(tmp_path):
    from science_tool.commons.promote import _rollback_step5

    _init_commons(tmp_path)
    # Stage 4 simulation: write a new canonical file and commit it.
    canon = tmp_path / "papers" / "Adams2025.md"
    canon.write_text("---\nid: paper:Adams2025\n---\nbody\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "--", "papers/Adams2025.md"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-q", "-m", "promote test"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "tag", "paper/Adams2025/1.0.0"], check=True)

    # Inject unrelated staged work that should NOT be clobbered:
    (tmp_path / "unrelated.txt").write_text("dirty work\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "--", "unrelated.txt"], check=True)

    _rollback_step5(
        commons_root=tmp_path,
        tags_attempted=["paper/Adams2025/1.0.0"],
        canonical_paths=[canon],
    )

    # Tag removed
    tags = subprocess.run(
        ["git", "-C", str(tmp_path), "tag"], capture_output=True, text=True, check=True
    ).stdout.split()
    assert "paper/Adams2025/1.0.0" not in tags
    # First-promote canonical file unlinked (didn't exist at pre-step-4 HEAD)
    assert not canon.exists()
    # Unrelated staged file is still staged (reset --soft preserved index):
    status = subprocess.run(
        ["git", "-C", str(tmp_path), "status", "--porcelain"],
        capture_output=True, text=True, check=True
    ).stdout
    assert "A  unrelated.txt" in status


def test_rollback_step5_restores_re_promote_file(tmp_path):
    """For an existing canonical file (re-promote), checkout HEAD -- <path>
    restores the prior content."""
    from science_tool.commons.promote import _rollback_step5

    _init_commons(tmp_path)
    canon = tmp_path / "papers" / "X.md"
    canon.write_text("original\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "--", "papers/X.md"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-q", "-m", "v1"], check=True)
    # Promote-like commit overwrites content:
    canon.write_text("promoted v2\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "--", "papers/X.md"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-q", "-m", "promote"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "tag", "paper/X/1.1.0"], check=True)

    _rollback_step5(
        commons_root=tmp_path,
        tags_attempted=["paper/X/1.1.0"],
        canonical_paths=[canon],
    )

    assert canon.exists()
    assert canon.read_text(encoding="utf-8") == "original\n"
```

- [ ] **Step 2: Run tests to verify they fail**

```
cd science && uv run pytest tests/test_commons_promote_apply.py -v
```

Expected: FAIL — `ImportError`.

- [ ] **Step 3: Implement `_write_audit_log` and `_rollback_step5`**

Append to `science/src/science_tool/commons/promote.py`:

```python
import subprocess


def _git(commons_root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    """Run `git -C <commons_root> <args>` and return the CompletedProcess.

    Wrapping makes path-limited call sites readable and centralizes the cwd
    plumbing so individual helpers don't repeat `["git", "-C", str(root), ...]`.
    """
    return subprocess.run(
        ["git", "-C", str(commons_root), *args],
        check=check,
        capture_output=True,
        text=True,
    )


def _write_audit_log(
    result: PromoteResult,
    commons_root: Path,
    *,
    invocation: str,
) -> Path:
    """Write the per-op YAML audit log under `<commons_root>/.migrations/`.

    Filename: `<UTC-YYYYMMDDTHHMMSSZ>-<op_id>.yaml`. The log is NOT committed
    here — `apply_promote` commits it path-limited on the success path; failure
    paths leave it uncommitted (best-effort).
    """
    migrations = commons_root / ".migrations"
    migrations.mkdir(exist_ok=True)
    stamp = result.started_at.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = migrations / f"{stamp}-{result.op_id}.yaml"

    projects_touched: dict = {}
    for decision in result.decisions:
        for slug, overlay in decision.overlays.items():
            projects_touched.setdefault(slug, {"overlay_rewrites": []})
            entry: dict = {
                "bibkey": decision.bibkey,
                "path": str(overlay.path),
                "pin_version": overlay.pin_version,
            }
            if overlay.rename_from is not None:
                entry["rename"] = {
                    "from": overlay.rename_from.name,
                    "to": overlay.path.name,
                }
            projects_touched[slug]["overlay_rewrites"].append(entry)

    log: dict = {
        "op_id": result.op_id,
        "type": "paper",
        "invocation": invocation,
        "status": result.status,
        "started_at": result.started_at.isoformat(),
        "finished_at": result.finished_at.isoformat(),
        "commons_commit": result.commons_commit,
        "commons_tags": result.tags_created,
        "projects_touched": projects_touched,
        "conflict_resolutions": [
            {
                "bibkey": cr.bibkey,
                "field": cr.field,
                "candidates": cr.candidates,
                "resolved_to": cr.resolved_to,
                "source_project": cr.source_project,
            }
            for d in result.decisions
            for cr in d.resolved_conflicts
        ],
        "failed_candidates": [
            {
                "bibkey": f.bibkey,
                "project_slug": f.project_slug,
                "source_path": str(f.source_path),
                "error_class": f.error_class,
                "error_message": f.error_message,
            }
            for f in result.failed_candidates
        ],
        "rollback": {
            "commons": (
                f"git -C {commons_root} revert {result.commons_commit}"
                if result.commons_commit else None
            ),
            "projects": {
                slug: f"git -C <{slug}-root> checkout HEAD -- doc/papers/<paths>"
                for slug in projects_touched
            },
        },
    }
    if result.failure_stage:
        log["failure_stage"] = result.failure_stage
        log["failure_detail"] = result.failure_detail

    path.write_text(yaml.safe_dump(log, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return path


def _rollback_step5(
    commons_root: Path,
    tags_attempted: list[str],
    canonical_paths: list[Path],
) -> None:
    """Non-destructive path-limited rollback for a step-5 mid-failure.

    1. Delete every tag in `tags_attempted` (idempotent — tags that never
       existed silently no-op).
    2. `git reset --soft HEAD~1` — moves HEAD back without disturbing index/wt.
    3. For each canonical_path: if it exists at the new HEAD, `git checkout
       HEAD -- <path>`. If it does NOT exist at HEAD (first-promote), unlink
       the working-tree file.

    Caller must have verified that HEAD~1 is the pre-step-4 state (the immediate
    parent of the just-undone promote commit). NEVER calls `reset --hard`.
    """
    for tag in tags_attempted:
        # Tolerate missing tags so we can be called from partial-failure paths.
        _git(commons_root, "tag", "-d", tag, check=False)

    _git(commons_root, "reset", "--soft", "HEAD~1")

    for canonical_path in canonical_paths:
        rel = canonical_path.relative_to(commons_root)
        exists_at_head = (
            _git(commons_root, "cat-file", "-e", f"HEAD:{rel}", check=False).returncode == 0
        )
        if exists_at_head:
            _git(commons_root, "checkout", "HEAD", "--", str(rel))
        else:
            canonical_path.unlink(missing_ok=True)
```

Also add this import near the top of `promote.py`:

```python
from datetime import timezone
```

- [ ] **Step 4: Run tests to verify they pass**

```
cd science && uv run pytest tests/test_commons_promote_apply.py -v
```

Expected: all three new tests PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/commons/promote.py \
        science/tests/test_commons_promote_apply.py
git commit -m "$(cat <<'EOF'
feat(commons/promote): _write_audit_log + _rollback_step5

Audit log written under .migrations/<ts>-<op>.yaml with the design's §6.5
shape (projects_touched, conflict_resolutions, failed_candidates, rollback
hints). Caller commits the log path-limited; failure path leaves it
uncommitted.

_rollback_step5 deletes attempted tags (idempotent), `git reset --soft HEAD~1`
(NEVER --hard), and per-path `checkout HEAD --` or unlink for first-promote
files. Test confirms an injected staged unrelated file survives.

Refs docs/plans/2026-05-15-commons-promote-papers-design.md §6.3 step 5, §6.5.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 16: `apply_promote` happy path

**Files:**
- Modify: `science/src/science_tool/commons/promote.py`
- Modify: `science/tests/test_commons_promote_apply.py`

Implements step 0 (preflight) + steps 1–7 of the design's §6.3 apply flow, but only the success path. Failure paths come in Task 17.

- [ ] **Step 1: Write the failing tests**

Append to `science/tests/test_commons_promote_apply.py`:

```python
def _build_project(tmp_path: Path, name: str, papers: dict[str, str]) -> Path:
    """Create a project repo at `tmp_path/<name>` with paper files at `doc/papers/`."""
    root = tmp_path / name
    (root / "doc" / "papers").mkdir(parents=True)
    for filename, content in papers.items():
        (root / "doc" / "papers" / filename).write_text(content, encoding="utf-8")
    _init_repo(root)
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-q", "-m", "init"], check=True)
    return root


def test_apply_promote_happy_path_writes_commits_tags_rewrites(tmp_path, monkeypatch):
    from science_tool.commons.promote import (
        apply_promote,
        discover_paper_candidates,
        plan_promote,
    )

    _init_commons(tmp_path / "commons")
    proj = _build_project(
        tmp_path, "proj-a",
        {"Adams2025.md": "---\nid: paper:Adams2025\ntitle: A\nyear: 2025\n---\n\n## Key Findings\n\nfoo\n"},
    )
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: {"proj-a": proj}[slug],
    )

    discovery = discover_paper_candidates(["proj-a"])
    plan = plan_promote(discovery, commons_root=tmp_path / "commons",
                        resolve_conflict=lambda c: None, from_order=["proj-a"])

    result = apply_promote(plan, commons_root=tmp_path / "commons",
                           invocation="science commons promote paper --from proj-a --apply")

    assert result.status == "ok"
    assert result.commons_commit is not None
    assert result.tags_created == ["paper/Adams2025/1.0.0"]
    # Canonical file landed in commons:
    canon = tmp_path / "commons" / "papers" / "Adams2025.md"
    assert canon.exists()
    canon_text = canon.read_text(encoding="utf-8")
    assert "schema_profile: science-entity-base/1.0+paper/2.0" in canon_text
    assert "## Key Findings" in canon_text
    # Project overlay was rewritten in place:
    overlay = proj / "doc" / "papers" / "Adams2025.md"
    overlay_text = overlay.read_text(encoding="utf-8")
    assert "overlay_of: paper:Adams2025" in overlay_text
    assert 'pin_version: "1.0.0"' in overlay_text
    # Audit log written + committed:
    assert result.audit_log_path is not None
    assert result.audit_log_path.exists()
    log_data = yaml.safe_load(result.audit_log_path.read_text(encoding="utf-8"))
    assert log_data["status"] == "ok"


def test_apply_promote_preflight_rejects_dirty_commons(tmp_path, monkeypatch):
    from science_tool.commons.errors import PromoteInputError
    from science_tool.commons.promote import (
        apply_promote,
        discover_paper_candidates,
        plan_promote,
    )

    _init_commons(tmp_path / "commons")
    # Dirty the commons working tree (anywhere):
    (tmp_path / "commons" / "dirty.txt").write_text("WIP\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path / "commons"), "add", "--", "dirty.txt"], check=True)

    proj = _build_project(
        tmp_path, "proj-a",
        {"Adams2025.md": "---\nid: paper:Adams2025\ntitle: A\n---\n"},
    )
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: proj,
    )

    discovery = discover_paper_candidates(["proj-a"])
    plan = plan_promote(discovery, commons_root=tmp_path / "commons",
                        resolve_conflict=lambda c: None, from_order=["proj-a"])
    with pytest.raises(PromoteInputError, match="commons"):
        apply_promote(plan, commons_root=tmp_path / "commons", invocation="...")


def test_apply_promote_preflight_rejects_dirty_target_project_file(tmp_path, monkeypatch):
    from science_tool.commons.errors import PromoteInputError
    from science_tool.commons.promote import (
        apply_promote,
        discover_paper_candidates,
        plan_promote,
    )

    _init_commons(tmp_path / "commons")
    proj = _build_project(
        tmp_path, "proj-a",
        {"Adams2025.md": "---\nid: paper:Adams2025\ntitle: A\n---\n"},
    )
    # Now make the target file dirty:
    (proj / "doc" / "papers" / "Adams2025.md").write_text(
        "---\nid: paper:Adams2025\ntitle: DIRTY\n---\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: proj,
    )

    discovery = discover_paper_candidates(["proj-a"])
    plan = plan_promote(discovery, commons_root=tmp_path / "commons",
                        resolve_conflict=lambda c: None, from_order=["proj-a"])
    with pytest.raises(PromoteInputError, match="dirty"):
        apply_promote(plan, commons_root=tmp_path / "commons", invocation="...")


def test_apply_promote_preflight_allows_dirty_non_target_project_file(tmp_path, monkeypatch):
    from science_tool.commons.promote import (
        apply_promote,
        discover_paper_candidates,
        plan_promote,
    )

    _init_commons(tmp_path / "commons")
    proj = _build_project(
        tmp_path, "proj-a",
        {"Adams2025.md": "---\nid: paper:Adams2025\ntitle: A\n---\n"},
    )
    # Dirty a non-target file:
    (proj / "other.md").write_text("dirty\n", encoding="utf-8")

    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: proj,
    )
    discovery = discover_paper_candidates(["proj-a"])
    plan = plan_promote(discovery, commons_root=tmp_path / "commons",
                        resolve_conflict=lambda c: None, from_order=["proj-a"])
    result = apply_promote(plan, commons_root=tmp_path / "commons", invocation="...")
    assert result.status == "ok"


def test_apply_promote_idempotent_skips_already_overlayed(tmp_path, monkeypatch):
    from science_tool.commons.promote import (
        apply_promote,
        discover_paper_candidates,
        plan_promote,
    )

    _init_commons(tmp_path / "commons")
    proj = _build_project(
        tmp_path, "proj-a",
        {"Adams2025.md": "---\nid: paper:Adams2025\ntitle: A\n---\n"},
    )
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: proj,
    )
    # First run promotes:
    discovery1 = discover_paper_candidates(["proj-a"])
    plan1 = plan_promote(discovery1, commons_root=tmp_path / "commons",
                         resolve_conflict=lambda c: None, from_order=["proj-a"])
    apply_promote(plan1, commons_root=tmp_path / "commons", invocation="first")
    # Commit the project overlay rewrite so the working tree is clean again:
    subprocess.run(["git", "-C", str(proj), "add", "."], check=True)
    subprocess.run(["git", "-C", str(proj), "commit", "-q", "-m", "promote"], check=True)
    # Second run: discovery skips the now-overlayed file:
    discovery2 = discover_paper_candidates(["proj-a"])
    assert discovery2.candidates_by_bibkey == {}


def test_apply_promote_tag_preflight_rejects_existing_tag(tmp_path, monkeypatch):
    from science_tool.commons.errors import PromoteWriteError
    from science_tool.commons.promote import (
        apply_promote,
        discover_paper_candidates,
        plan_promote,
    )

    _init_commons(tmp_path / "commons")
    subprocess.run(["git", "-C", str(tmp_path / "commons"), "tag", "paper/Adams2025/1.0.0"], check=True)

    proj = _build_project(
        tmp_path, "proj-a",
        {"Adams2025.md": "---\nid: paper:Adams2025\ntitle: A\n---\n"},
    )
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: proj,
    )
    discovery = discover_paper_candidates(["proj-a"])
    plan = plan_promote(discovery, commons_root=tmp_path / "commons",
                        resolve_conflict=lambda c: None, from_order=["proj-a"])
    with pytest.raises(PromoteWriteError, match="tag"):
        apply_promote(plan, commons_root=tmp_path / "commons", invocation="...")
```

- [ ] **Step 2: Run tests to verify they fail**

```
cd science && uv run pytest tests/test_commons_promote_apply.py -v
```

Expected: FAIL — `apply_promote` is still `NotImplementedError`.

- [ ] **Step 3: Implement `apply_promote` happy path**

Replace the `apply_promote` stub in `science/src/science_tool/commons/promote.py` with:

```python
import secrets
from datetime import timezone

from science_tool.commons.errors import (
    PromoteCandidateError,
    PromoteInputError,
    PromoteWriteError,
)


def _commons_is_clean(commons_root: Path) -> tuple[bool, list[str]]:
    """Return (clean, dirty_paths). Clean = no staged, no unstaged, no untracked
    inside papers/ or .migrations/."""
    status = _git(commons_root, "status", "--porcelain").stdout
    dirty: list[str] = []
    for line in status.splitlines():
        # status format: XY<space><path>
        if len(line) < 4:
            continue
        path = line[3:]
        # Allow untracked anywhere EXCEPT inside papers/ or .migrations/:
        flags = line[:2]
        if flags == "??":
            if path.startswith("papers/") or path.startswith(".migrations/"):
                dirty.append(path)
        else:
            dirty.append(path)
    return (not dirty, dirty)


def _project_target_files_clean(
    project_root: Path, target_filenames: list[str]
) -> tuple[bool, list[str]]:
    """For each filename in `target_filenames`, check whether `doc/papers/<name>`
    matches HEAD. Returns (clean, dirty_paths)."""
    dirty: list[str] = []
    for name in target_filenames:
        rel = f"doc/papers/{name}"
        absolute = project_root / rel
        if not absolute.exists():
            continue  # missing file → no dirty content to worry about (a new write)
        diff = subprocess.run(
            ["git", "-C", str(project_root), "diff", "--exit-code", "--quiet", "HEAD", "--", rel],
        )
        if diff.returncode != 0:
            dirty.append(rel)
    return (not dirty, dirty)


def _repo_is_idle(root: Path) -> bool:
    """True if the repo is NOT mid-merge/rebase/cherry-pick/bisect."""
    git_dir = root / ".git"
    sentinels = [
        "MERGE_HEAD", "REBASE_HEAD", "CHERRY_PICK_HEAD",
        "BISECT_LOG", "rebase-apply", "rebase-merge",
    ]
    return not any((git_dir / s).exists() for s in sentinels)


def apply_promote(
    plan: PromotePlan,
    commons_root: Path,
    *,
    invocation: str,
) -> PromoteResult:
    """Atomic-batch apply per design §6.3."""
    started_at = datetime.now(tz=timezone.utc)
    op_id = secrets.token_hex(4)

    # ---------- Step 0: preflight ----------
    if not commons_root.exists():
        raise PromoteInputError(
            f"commons store missing at {commons_root}; run `science commons init`"
        )
    if not _repo_is_idle(commons_root):
        raise PromoteInputError(f"commons repo is mid-merge/rebase: {commons_root}")
    clean, dirty = _commons_is_clean(commons_root)
    if not clean:
        raise PromoteInputError(
            "commons repo is not clean. Commit/stash before re-running. Dirty: "
            + ", ".join(dirty)
        )

    # Target file map keyed by project_root:
    target_files_per_project: dict[Path, list[str]] = {}
    for decision in plan.decisions:
        for slug, overlay in decision.overlays.items():
            target_files_per_project.setdefault(
                overlay.path.parent.parent.parent, []
            ).append(overlay.path.name)

    for project_root, names in target_files_per_project.items():
        if not _repo_is_idle(project_root):
            raise PromoteInputError(f"project {project_root} is mid-merge/rebase")
        clean, dirty = _project_target_files_clean(project_root, names)
        if not clean:
            raise PromoteInputError(
                f"project {project_root} has dirty target files: " + ", ".join(dirty)
            )

    # ---------- Step 5.1: tag preflight ----------
    for decision in plan.decisions:
        tag = f"paper/{decision.bibkey}/{decision.canonical_version}"
        existing = _git(commons_root, "rev-parse", "--verify", "--quiet", tag, check=False)
        if existing.returncode == 0:
            raise PromoteWriteError(
                stage="write_commons",
                detail=f"tag {tag!r} already exists in commons; refusing to overwrite",
            )

    # ---------- Step 4: write commons (staged) ----------
    written_canonical_paths: list[Path] = []
    for decision in plan.decisions:
        decision.canonical_path.parent.mkdir(parents=True, exist_ok=True)
        decision.canonical_path.write_text(decision.canonical_content, encoding="utf-8")
        written_canonical_paths.append(decision.canonical_path)

    # ---------- Step 5.2: commit (path-limited) ----------
    rel_paths = [str(p.relative_to(commons_root)) for p in written_canonical_paths]
    try:
        _git(commons_root, "add", "--", *rel_paths)
        _git(
            commons_root,
            "commit", "-m", f"promote: {len(plan.decisions)} papers via op {op_id}",
            "--", *rel_paths,
        )
    except subprocess.CalledProcessError as exc:
        # Step 4 wrote files; on commit failure, restore via path-limited checkout.
        _restore_paths_to_head(commons_root, written_canonical_paths)
        raise PromoteWriteError(
            stage="write_commons",
            detail=f"commons commit failed: {exc.stderr or exc}",
        ) from exc

    commons_commit = _git(commons_root, "rev-parse", "--short", "HEAD").stdout.strip()

    # ---------- Step 5.3: tag (path-limited per-tag) ----------
    tags_created: list[str] = []
    for decision in sorted(plan.decisions, key=lambda d: d.bibkey):
        tag = f"paper/{decision.bibkey}/{decision.canonical_version}"
        try:
            _git(commons_root, "tag", tag, commons_commit)
            tags_created.append(tag)
        except subprocess.CalledProcessError as exc:
            _rollback_step5(commons_root, tags_created, written_canonical_paths)
            raise PromoteWriteError(
                stage="write_commons",
                detail=f"tag {tag!r} failed after commit: {exc.stderr or exc}",
                commons_commit=commons_commit,
            ) from exc

    # ---------- Step 6: rewrite projects ----------
    projects_touched: list[str] = []
    try:
        for decision in plan.decisions:
            for slug, overlay in decision.overlays.items():
                if overlay.rename_from is not None and overlay.rename_from.exists():
                    overlay.rename_from.unlink()
                overlay.path.parent.mkdir(parents=True, exist_ok=True)
                overlay.path.write_text(overlay.after_content, encoding="utf-8")
                if slug not in projects_touched:
                    projects_touched.append(slug)
    except OSError as exc:
        # Per-path rollback for each touched project file:
        for decision in plan.decisions:
            for overlay in decision.overlays.values():
                project_root = overlay.path.parent.parent.parent
                rel = overlay.path.relative_to(project_root)
                subprocess.run(
                    ["git", "-C", str(project_root), "checkout", "HEAD", "--", str(rel)],
                    check=False,
                )
        raise PromoteWriteError(
            stage="rewrite_projects",
            detail=f"overlay write failed: {exc}",
            commons_commit=commons_commit,
            projects_touched=projects_touched,
        ) from exc

    # ---------- Step 7: write audit log (success path) ----------
    finished_at = datetime.now(tz=timezone.utc)
    result = PromoteResult(
        op_id=op_id,
        started_at=started_at,
        finished_at=finished_at,
        commons_commit=commons_commit,
        tags_created=tags_created,
        decisions=plan.decisions,
        failed_candidates=plan.failed_candidates,
        audit_log_path=None,
        status="ok",
        failure_stage=None,
        failure_detail=None,
    )
    audit_path = _write_audit_log(result, commons_root, invocation=invocation)
    # Path-limited audit commit:
    audit_rel = str(audit_path.relative_to(commons_root))
    _git(commons_root, "add", "--", audit_rel)
    _git(commons_root, "commit", "-m", f"audit: op {op_id}", "--", audit_rel)

    # Replace audit_log_path on the result (frozen dataclass → rebuild):
    return PromoteResult(
        op_id=result.op_id,
        started_at=result.started_at,
        finished_at=result.finished_at,
        commons_commit=result.commons_commit,
        tags_created=result.tags_created,
        decisions=result.decisions,
        failed_candidates=result.failed_candidates,
        audit_log_path=audit_path,
        status="ok",
        failure_stage=None,
        failure_detail=None,
    )


def _restore_paths_to_head(commons_root: Path, paths: list[Path]) -> None:
    """For each path, checkout HEAD -- <rel> if it existed at HEAD, else unlink.
    Used in the 'before step 5' failure path."""
    for path in paths:
        rel = path.relative_to(commons_root)
        existed = _git(commons_root, "cat-file", "-e", f"HEAD:{rel}", check=False).returncode == 0
        if existed:
            _git(commons_root, "checkout", "HEAD", "--", str(rel))
        else:
            path.unlink(missing_ok=True)
```

Note: the `overlay.path.parent.parent.parent` walk-up assumes overlay path = `<project_root>/doc/papers/<file>.md`. This is true for every promote-managed overlay; the assumption is asserted via tests in the next step.

- [ ] **Step 4: Run tests to verify they pass**

```
cd science && uv run pytest tests/test_commons_promote_apply.py -v
```

Expected: all 9 tests PASS (6 new + 3 from Task 15).

- [ ] **Step 5: Run full science suite**

```
cd science && uv run pytest
```

Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/commons/promote.py \
        science/tests/test_commons_promote_apply.py
git commit -m "$(cat <<'EOF'
feat(commons/promote): apply_promote happy path

Implements step 0 (strict commons preflight, target-scoped project preflight)
through step 7 (path-limited audit commit). All commons-side commits carry
explicit -- <paths>; tag preflight catches existing tags before the commit.
Step 5 mid-failure uses _rollback_step5; step 6 mid-failure restores project
files per-path via `git checkout HEAD --`.

Idempotency: re-applying a discovery that contains no candidates (because all
papers are already overlayed) is a no-op.

Refs docs/plans/2026-05-15-commons-promote-papers-design.md §6.3 steps 0-7.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 17: `apply_promote` failure paths

**Files:**
- Modify: `science/tests/test_commons_promote_apply.py`
- Modify: `science/src/science_tool/commons/promote.py` (only if a test surfaces a bug)

Task 16 implements the failure-handling code paths; this task hardens them with regression tests. The §6.4 invariants are: no commit operation omits a pathspec; rollback never destroys staged unrelated work; path-limited project rollback preserves dirty non-target files.

- [ ] **Step 1: Write the failing tests (regression coverage)**

Append to `science/tests/test_commons_promote_apply.py`:

```python
def test_apply_promote_failure_before_commit_unlinks_first_promote_canonical(
    tmp_path, monkeypatch
):
    """Force a commit failure (simulate by making the commit fail). The
    canonical file written in step 4 (a first-promote, so not at HEAD) must be
    unlinked, not left dangling."""
    from science_tool.commons.errors import PromoteWriteError
    from science_tool.commons.promote import (
        apply_promote,
        discover_paper_candidates,
        plan_promote,
    )

    _init_commons(tmp_path / "commons")
    proj = _build_project(
        tmp_path, "proj-a",
        {"Adams2025.md": "---\nid: paper:Adams2025\ntitle: A\n---\n"},
    )
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: proj,
    )

    discovery = discover_paper_candidates(["proj-a"])
    plan = plan_promote(discovery, commons_root=tmp_path / "commons",
                        resolve_conflict=lambda c: None, from_order=["proj-a"])

    # Force the commit to fail by removing the commons git config so the commit
    # has no author/email. (Reset the repo config that _init_commons set.)
    subprocess.run(
        ["git", "-C", str(tmp_path / "commons"), "config", "--unset", "user.email"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(tmp_path / "commons"), "config", "--unset", "user.name"],
        check=True,
    )
    monkeypatch.setenv("GIT_AUTHOR_NAME", "")
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "")
    monkeypatch.setenv("GIT_COMMITTER_NAME", "")
    monkeypatch.setenv("GIT_COMMITTER_EMAIL", "")
    monkeypatch.setenv("HOME", str(tmp_path / "no-global-git"))

    with pytest.raises(PromoteWriteError, match="commons commit failed"):
        apply_promote(plan, commons_root=tmp_path / "commons", invocation="...")

    # First-promote canonical must be unlinked (it didn't exist at HEAD):
    assert not (tmp_path / "commons" / "papers" / "Adams2025.md").exists()


def test_apply_promote_path_limited_commit_does_not_pick_up_post_preflight_race(
    tmp_path, monkeypatch
):
    """Simulate a TOCTOU race: between preflight pass and the commit, an
    unrelated file is staged in commons. The promote commit must NOT include it."""
    from science_tool.commons.promote import (
        apply_promote,
        discover_paper_candidates,
        plan_promote,
    )

    _init_commons(tmp_path / "commons")
    proj = _build_project(
        tmp_path, "proj-a",
        {"Adams2025.md": "---\nid: paper:Adams2025\ntitle: A\n---\n"},
    )
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: proj,
    )

    discovery = discover_paper_candidates(["proj-a"])
    plan = plan_promote(discovery, commons_root=tmp_path / "commons",
                        resolve_conflict=lambda c: None, from_order=["proj-a"])

    # Monkeypatch _git so that AFTER preflight (which calls `status --porcelain`
    # and `rev-parse`) and AFTER `add -- papers/Adams2025.md`, but BEFORE the
    # `commit`, an unrelated file is staged. We use a side-effect counter.
    from science_tool.commons import promote as promote_module

    real_git = promote_module._git
    call_count = {"n": 0}

    def racing_git(commons_root, *args, **kw):
        call_count["n"] += 1
        # After the canonical-paths `add --` (call sequence depends on impl,
        # but the first `add --` happens at step 5.2); inject before `commit`.
        if args[:1] == ("add",) and args[2:3] == ("--",):
            result = real_git(commons_root, *args, **kw)
            # Race: stage an unrelated file:
            unrelated = commons_root / "race.txt"
            unrelated.write_text("staged after preflight\n", encoding="utf-8")
            real_git(commons_root, "add", "--", "race.txt")
            return result
        return real_git(commons_root, *args, **kw)

    monkeypatch.setattr(promote_module, "_git", racing_git)

    result = apply_promote(
        plan, commons_root=tmp_path / "commons", invocation="..."
    )
    assert result.status == "ok"
    # Inspect the commit's tree: only papers/Adams2025.md should be in it.
    files = subprocess.run(
        ["git", "-C", str(tmp_path / "commons"), "show", "--stat", result.commons_commit + "~0"],
        capture_output=True, text=True, check=True,
    ).stdout
    assert "papers/Adams2025.md" in files
    assert "race.txt" not in files
    # The race file is still staged (untouched by promote):
    status = subprocess.run(
        ["git", "-C", str(tmp_path / "commons"), "status", "--porcelain"],
        capture_output=True, text=True, check=True,
    ).stdout
    assert "A  race.txt" in status


def test_apply_promote_project_rollback_preserves_dirty_non_target(tmp_path, monkeypatch):
    """A mid-step-6 failure must leave dirty non-target project files untouched."""
    from science_tool.commons.errors import PromoteWriteError
    from science_tool.commons.promote import (
        apply_promote,
        discover_paper_candidates,
        plan_promote,
    )

    _init_commons(tmp_path / "commons")
    proj = _build_project(
        tmp_path, "proj-a",
        {"Adams2025.md": "---\nid: paper:Adams2025\ntitle: A\n---\n",
         "Bravo2024.md": "---\nid: paper:Bravo2024\ntitle: B\n---\n"},
    )
    # Dirty a non-target file:
    (proj / "other.txt").write_text("dirty WIP\n", encoding="utf-8")

    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: proj,
    )

    discovery = discover_paper_candidates(["proj-a"])
    plan = plan_promote(discovery, commons_root=tmp_path / "commons",
                        resolve_conflict=lambda c: None, from_order=["proj-a"])

    # Force the second project write to fail by making the second target path
    # un-writable (read-only).
    second_overlay = plan.decisions[1].overlays["proj-a"]
    second_overlay.path.chmod(0o444)
    try:
        with pytest.raises(PromoteWriteError, match="overlay write"):
            apply_promote(plan, commons_root=tmp_path / "commons", invocation="...")
    finally:
        second_overlay.path.chmod(0o644)

    # The non-target dirty file must still be exactly as we left it:
    assert (proj / "other.txt").read_text(encoding="utf-8") == "dirty WIP\n"
```

- [ ] **Step 2: Run tests**

```
cd science && uv run pytest tests/test_commons_promote_apply.py -v
```

Expected: all three new failure-path tests PASS (they exercise code paths already wired in Task 16).

If any test fails: the implementation has a bug. Fix in `promote.py` until tests pass.

- [ ] **Step 3: Run full science suite**

```
cd science && uv run pytest
```

Expected: all green.

- [ ] **Step 4: Commit**

```bash
git add science/tests/test_commons_promote_apply.py science/src/science_tool/commons/promote.py 2>/dev/null
git commit -m "$(cat <<'EOF'
test(commons/promote): apply_promote failure-path regression tests

- first-promote canonical is unlinked (not orphaned) on commit failure
- path-limited commit ignores a post-preflight staged race file
- mid-step-6 project rollback preserves dirty non-target files

Refs docs/plans/2026-05-15-commons-promote-papers-design.md §6.4.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 18: Test fixtures — synthetic 2-project corpus

**Files:**
- Create: `science/tests/fixtures/promote/README.md`
- Create: `science/tests/fixtures/promote/proj-alpha/doc/papers/*.md` (4 files)
- Create: `science/tests/fixtures/promote/proj-beta/doc/papers/*.md` (4 files)

The fixtures double as a regression bed for the dedup flow and a worked example for new contributors. Most apply/CLI tests run against tmp_path-built projects (so they can mutate freely); these on-disk fixtures are for read-only integration scenarios documented in Task 20.

- [ ] **Step 1: Create the fixture root + README**

Create `science/tests/fixtures/promote/README.md`:

```markdown
# Promote test fixtures

Synthetic two-project corpus exercising the four candidate shapes promote
must handle. Used by `test_commons_promote_apply.py` / `test_commons_cli_promote.py`
as a stable on-disk read-only fixture; tests that need to mutate build their
own corpus under `tmp_path`.

| Bibkey       | Shape                                       | Source projects |
|--------------|---------------------------------------------|-----------------|
| Adams2025    | Single-instance, well-formed                | proj-alpha      |
| Bravo2024    | Single-instance, well-formed                | proj-beta       |
| Huh2024      | Multi-instance, no conflicts (auto-union)   | both            |
| Dang2023     | Multi-instance, real `year` conflict        | both            |

See docs/plans/2026-05-15-commons-promote-papers-design.md §8.
```

- [ ] **Step 2: Create proj-alpha papers**

`science/tests/fixtures/promote/proj-alpha/doc/papers/Adams2025.md`:

```markdown
---
id: paper:Adams2025
title: Adams Alpha Paper
authors:
  - Adams, J.
year: 2025
venue: Cell
doi: 10.1/adams
tags:
  - alpha-tag
related:
  - question:q-alpha
created: "2026-01-01"
updated: "2026-02-01"
---

## Key Findings

A1, A2.

## Project Use

Used in proj-alpha hypothesis HA.
```

`science/tests/fixtures/promote/proj-alpha/doc/papers/Huh2024.md`:

```markdown
---
id: paper:Huh2024
title: Huh Shared Paper
authors:
  - Huh, K.
year: 2024
venue: Nature
tags:
  - shared-tag
created: "2026-03-01"
updated: "2026-04-01"
---

## Key Findings

H1.

## Project Use

Used in proj-alpha.
```

`science/tests/fixtures/promote/proj-alpha/doc/papers/Dang2023.md`:

```markdown
---
id: paper:Dang2023
title: Dang Conflict Paper
authors:
  - Dang, L.
year: 2023
created: "2026-02-15"
updated: "2026-02-15"
---

## Key Findings

D1.

## Project Use

Used in proj-alpha (note: year 2023 here vs 2024 in proj-beta).
```

- [ ] **Step 3: Create proj-beta papers**

`science/tests/fixtures/promote/proj-beta/doc/papers/Bravo2024.md`:

```markdown
---
id: paper:Bravo2024
title: Bravo Beta Paper
authors:
  - Bravo, M.
year: 2024
venue: Science
status: active
created: "2026-01-15"
updated: "2026-03-15"
---

## Key Findings

B1.

## Relevance

Relevant to proj-beta theme T1.
```

`science/tests/fixtures/promote/proj-beta/doc/papers/Huh2024.md`:

```markdown
---
id: paper:Huh2024
title: Huh Shared Paper
authors:
  - Huh, K.
year: 2024
venue: Nature
doi: 10.1/huh
tags:
  - beta-tag
created: "2026-03-10"
updated: "2026-04-10"
---

## Key Findings

H1, H2.

## Relevance

Cross-project paper; proj-beta adds doi + a tag.
```

`science/tests/fixtures/promote/proj-beta/doc/papers/Dang2023.md`:

```markdown
---
id: paper:Dang2023
title: Dang Conflict Paper
authors:
  - Dang, L.
year: 2024
created: "2026-02-20"
updated: "2026-02-20"
---

## Key Findings

D1.

## Relevance

proj-beta records year 2024 (deliberate conflict with proj-alpha).
```

- [ ] **Step 4: Verify the fixture layout**

```
cd science && ls tests/fixtures/promote/proj-alpha/doc/papers/ \
            && ls tests/fixtures/promote/proj-beta/doc/papers/
```

Expected:
```
Adams2025.md  Dang2023.md  Huh2024.md
Bravo2024.md  Dang2023.md  Huh2024.md
```

- [ ] **Step 5: Run the promote suite to confirm nothing breaks**

```
cd science && uv run pytest tests/test_commons_promote_*.py -v
```

Expected: all green (fixtures aren't consumed yet; CLI tests in Task 20 will pull from them).

- [ ] **Step 6: Commit**

```bash
git add science/tests/fixtures/promote/
git commit -m "$(cat <<'EOF'
test(commons/promote): add fixtures for synthetic 2-project corpus

Four candidate shapes: single-instance well-formed (Adams2025, Bravo2024),
multi-instance no-conflict (Huh2024), multi-instance with year conflict
(Dang2023). Used by CLI integration tests in Task 20.

Refs docs/plans/2026-05-15-commons-promote-papers-design.md §8.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 19: Wire `commons/__init__.py` exports

**Files:**
- Modify: `science/src/science_tool/commons/__init__.py`

- [ ] **Step 1: Write the failing test**

Add to `science/tests/test_commons_promote_discovery.py`:

```python
def test_promote_public_surface_exports():
    """Public types live on the science_tool.commons package surface."""
    from science_tool.commons import (
        ConflictResolution,
        DiscoveryResult,
        FailedCandidate,
        FieldConflict,
        OverlayRewrite,
        PromoteCandidate,
        PromoteDecision,
        PromotePlan,
        PromoteResult,
        apply_promote,
        discover_paper_candidates,
        plan_promote,
        prompt_resolve,
        resolve_project_by_id,
    )
```

- [ ] **Step 2: Run test to verify it fails**

```
cd science && uv run pytest tests/test_commons_promote_discovery.py::test_promote_public_surface_exports -v
```

Expected: FAIL — `ImportError`.

- [ ] **Step 3: Update `commons/__init__.py`**

Open `science/src/science_tool/commons/__init__.py`. After the existing `from science_tool.commons.errors import (...)` block, add:

```python
from science_tool.commons.config import resolve_project_by_id
from science_tool.commons.errors import (
    PromoteCandidateError,
    PromoteConflictAbort,
    PromoteInputError,
    PromoteWriteError,
)
from science_tool.commons.promote import (
    ConflictResolution,
    DiscoveryResult,
    FailedCandidate,
    FieldConflict,
    OverlayRewrite,
    PromoteCandidate,
    PromoteDecision,
    PromotePlan,
    PromoteResult,
    apply_promote,
    discover_paper_candidates,
    plan_promote,
    prompt_resolve,
)
```

Then ensure these names appear in `__all__` (alphabetical). If the existing file uses an `__all__` list, extend it; if it doesn't, add one at the bottom listing every re-exported symbol.

- [ ] **Step 4: Run the test to verify it passes**

```
cd science && uv run pytest tests/test_commons_promote_discovery.py -v
```

Expected: all tests in the file PASS.

- [ ] **Step 5: Run full science suite**

```
cd science && uv run pytest
```

Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/commons/__init__.py \
        science/tests/test_commons_promote_discovery.py
git commit -m "$(cat <<'EOF'
feat(commons): expose promote surface on the package __init__

Re-exports PromoteCandidate, PromotePlan, PromoteResult, FailedCandidate,
DiscoveryResult, FieldConflict, ConflictResolution, OverlayRewrite,
discover_paper_candidates, plan_promote, apply_promote, prompt_resolve, the
four promote error classes, and resolve_project_by_id.

Refs docs/plans/2026-05-15-commons-promote-papers-design.md §3.1.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 20: CLI — `commons promote paper` subgroup

**Files:**
- Modify: `science/src/science_tool/commons/cli.py`
- Create: `science/tests/test_commons_cli_promote.py`

- [ ] **Step 1: Write the failing tests**

Create `science/tests/test_commons_cli_promote.py`:

```python
"""Tests for science_tool.commons.cli — promote subgroup."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner

# Shared helpers reused from the apply test module:
from tests.test_commons_promote_apply import _init_commons, _build_project


def _bare_project_from_fixture(tmp_path: Path, fixture_name: str, slug: str) -> Path:
    """Copy a fixture project into tmp_path and init a git repo."""
    src = Path(__file__).parent / "fixtures" / "promote" / fixture_name
    dst = tmp_path / slug
    shutil.copytree(src, dst)
    subprocess.run(["git", "init", "-q", str(dst)], check=True)
    subprocess.run(["git", "-C", str(dst), "config", "user.email", "test@x"], check=True)
    subprocess.run(["git", "-C", str(dst), "config", "user.name", "test"], check=True)
    subprocess.run(["git", "-C", str(dst), "add", "."], check=True)
    subprocess.run(["git", "-C", str(dst), "commit", "-q", "-m", "init"], check=True)
    return dst


@pytest.fixture
def runner():
    return CliRunner()


def test_promote_paper_bulk_dry_run_summary(tmp_path, monkeypatch, runner):
    from science_tool.commons.cli import commons_group

    _init_commons(tmp_path / "commons")
    alpha = _bare_project_from_fixture(tmp_path, "proj-alpha", "proj-alpha")
    beta = _bare_project_from_fixture(tmp_path, "proj-beta", "proj-beta")

    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: {"proj-alpha": alpha, "proj-beta": beta}[slug],
    )
    monkeypatch.setattr(
        "science_tool.commons.cli.resolve_commons_root",
        lambda: tmp_path / "commons",
    )

    # Always pick the first conflict option:
    monkeypatch.setattr(
        "science_tool.commons.promote.prompt_resolve",
        lambda conflict: sorted(conflict.candidates.items())[0][1],
    )

    result = runner.invoke(
        commons_group,
        ["promote", "paper", "--from", "proj-alpha", "--from", "proj-beta"],
    )
    assert result.exit_code == 0, result.output
    assert "Discovered" in result.output
    assert "single-instance" in result.output
    assert "Adams2025" in result.output or "4 single-instance" in result.output
    # Dry-run does NOT write:
    assert not (tmp_path / "commons" / "papers" / "Adams2025.md").exists()


def test_promote_paper_apply_writes_and_tags(tmp_path, monkeypatch, runner):
    from science_tool.commons.cli import commons_group

    _init_commons(tmp_path / "commons")
    alpha = _bare_project_from_fixture(tmp_path, "proj-alpha", "proj-alpha")
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: alpha,
    )
    monkeypatch.setattr(
        "science_tool.commons.cli.resolve_commons_root",
        lambda: tmp_path / "commons",
    )
    # Auto-resolve conflicts:
    monkeypatch.setattr(
        "science_tool.commons.promote.prompt_resolve",
        lambda conflict: sorted(conflict.candidates.items())[0][1],
    )

    result = runner.invoke(
        commons_group,
        ["promote", "paper", "--from", "proj-alpha", "--apply"],
    )
    assert result.exit_code == 0, result.output
    assert (tmp_path / "commons" / "papers" / "Adams2025.md").exists()
    tags = subprocess.run(
        ["git", "-C", str(tmp_path / "commons"), "tag"],
        capture_output=True, text=True, check=True,
    ).stdout.split()
    assert "paper/Adams2025/1.0.0" in tags


def test_promote_paper_null_id_exits_nonzero(tmp_path, monkeypatch, runner):
    from science_tool.commons.cli import commons_group
    from science_tool.commons.errors import CommonsError

    _init_commons(tmp_path / "commons")
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: (_ for _ in ()).throw(CommonsError(f"{slug!r} has id: null")),
    )
    monkeypatch.setattr(
        "science_tool.commons.cli.resolve_commons_root",
        lambda: tmp_path / "commons",
    )

    result = runner.invoke(
        commons_group,
        ["promote", "paper", "--from", "legacy-slug"],
    )
    assert result.exit_code != 0
    assert "id: null" in result.output


def test_promote_paper_missing_commons_exits_nonzero(tmp_path, monkeypatch, runner):
    from science_tool.commons.cli import commons_group

    # Do NOT init commons: directory doesn't exist.
    monkeypatch.setattr(
        "science_tool.commons.cli.resolve_commons_root",
        lambda: tmp_path / "no-commons",
    )

    result = runner.invoke(
        commons_group,
        ["promote", "paper", "--from", "proj-alpha"],
    )
    assert result.exit_code != 0
    assert "science commons init" in result.output


def test_promote_paper_single_entity_form(tmp_path, monkeypatch, runner):
    from science_tool.commons.cli import commons_group

    _init_commons(tmp_path / "commons")
    alpha = _bare_project_from_fixture(tmp_path, "proj-alpha", "proj-alpha")
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: alpha,
    )
    monkeypatch.setattr(
        "science_tool.commons.cli.resolve_commons_root",
        lambda: tmp_path / "commons",
    )

    result = runner.invoke(
        commons_group,
        ["promote", "paper", "paper:Adams2025", "--from", "proj-alpha"],
    )
    # Dry-run summary should mention exactly one paper:
    assert result.exit_code == 0, result.output
    assert "Adams2025" in result.output
```

- [ ] **Step 2: Run tests to verify they fail**

```
cd science && uv run pytest tests/test_commons_cli_promote.py -v
```

Expected: FAIL — CLI subgroup doesn't exist.

- [ ] **Step 3: Add the CLI subgroup**

In `science/src/science_tool/commons/cli.py`, add (near the other group/command definitions; preferred placement: after the `data_group` block):

```python
from science_tool.commons.errors import (
    PromoteConflictAbort,
    PromoteInputError,
    PromoteWriteError,
)
from science_tool.commons.promote import (
    apply_promote,
    discover_paper_candidates,
    plan_promote,
)


@commons_group.group("promote")
def promote_group() -> None:
    """Promote per-project entities into the shared commons store."""


@promote_group.command("paper")
@click.argument("entity_id", required=False, default=None)
@click.option(
    "--from",
    "from_",
    multiple=True,
    required=True,
    metavar="SLUG",
    help="Registered project id (NOT name). Required; repeatable for bulk + dedup.",
)
@click.option("--apply", "apply_flag", is_flag=True, default=False, help="Write changes (default: dry-run).")
@click.option("--limit", type=int, default=None, help="Bulk only: stop after N papers (bibkey-sorted).")
def promote_paper_cmd(
    entity_id: str | None,
    from_: tuple[str, ...],
    apply_flag: bool,
    limit: int | None,
) -> None:
    """Promote paper entities into the commons store.

    Dry-run is the default; pass --apply to write. Conflicts on canonical fields
    prompt interactively in BOTH dry-run and apply (so dry-run is a faithful
    preview). Use --limit 0 to get a discovery-only summary without prompts.
    """
    root = resolve_commons_root()
    if not root.exists():
        raise click.ClickException(
            f"commons store missing at {root}; run `science commons init` first"
        )

    # Single-entity form requires exactly one --from:
    if entity_id is not None and len(from_) != 1:
        raise click.ClickException(
            "single-entity form (`promote paper <id>`) requires exactly one --from"
        )

    try:
        discovery = discover_paper_candidates(list(from_))
    except CommonsError as exc:
        raise click.ClickException(str(exc)) from exc

    # Optional filtering for the single-entity form:
    if entity_id is not None:
        if not entity_id.startswith("paper:"):
            raise click.ClickException(f"expected `paper:<bibkey>`, got {entity_id!r}")
        wanted = entity_id.split(":", 1)[1].casefold()
        filtered = {
            k: v for k, v in discovery.candidates_by_bibkey.items() if k == wanted
        }
        from science_tool.commons import DiscoveryResult  # local import for the rebuild
        discovery = DiscoveryResult(
            candidates_by_bibkey=filtered,
            failed_candidates=discovery.failed_candidates,
        )

    # --limit (bulk only):
    if limit is not None and entity_id is None and limit >= 0:
        sorted_keys = sorted(discovery.candidates_by_bibkey)[:limit] if limit > 0 else []
        truncated = {k: discovery.candidates_by_bibkey[k] for k in sorted_keys}
        from science_tool.commons import DiscoveryResult  # local import
        discovery = DiscoveryResult(
            candidates_by_bibkey=truncated,
            failed_candidates=discovery.failed_candidates,
        )

    # Summary line:
    n_total = sum(len(v) for v in discovery.candidates_by_bibkey.values())
    n_groups = len(discovery.candidates_by_bibkey)
    n_multi = sum(1 for v in discovery.candidates_by_bibkey.values() if len(v) > 1)
    click.echo(
        f"Discovered {n_total} paper candidates across {len(from_)} projects "
        f"({n_groups} unique bibkeys, {n_multi} multi-instance)."
    )
    if discovery.failed_candidates:
        click.echo(f"  • {len(discovery.failed_candidates)} failed candidates:")
        for f in discovery.failed_candidates[:5]:
            click.echo(f"    - {f.source_path}: {f.error_message}")
        if len(discovery.failed_candidates) > 5:
            click.echo(f"    … and {len(discovery.failed_candidates) - 5} more")

    if not discovery.candidates_by_bibkey:
        click.echo("Nothing to promote.")
        return

    # Plan (with conflict prompts in BOTH dry-run and --apply paths):
    try:
        plan = plan_promote(discovery, commons_root=root, from_order=list(from_))
    except PromoteConflictAbort as exc:
        raise click.ClickException(f"aborted at conflict prompt: {exc}") from exc

    click.echo(f"Plan: {len(plan.decisions)} canonical entities, "
               f"{sum(len(d.overlays) for d in plan.decisions)} overlay rewrites.")
    for d in plan.decisions:
        for slug, ov in d.overlays.items():
            if ov.rename_from is not None:
                click.echo(f"  rename in {slug}: {ov.rename_from.name} → {ov.path.name}")

    if not apply_flag:
        click.echo("Re-run with --apply to execute.")
        return

    # Apply:
    try:
        result = apply_promote(plan, commons_root=root, invocation=_invocation())
    except (PromoteInputError, PromoteWriteError) as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(f"Applied op {result.op_id}: commit {result.commons_commit}, "
               f"{len(result.tags_created)} tags, audit log at {result.audit_log_path}")


def _invocation() -> str:
    """Reconstruct an invocation string from sys.argv for audit logging."""
    import sys
    return " ".join(sys.argv)
```

Note: `CommonsError` is already imported at the top of `cli.py` (Phase B). If not, add `from science_tool.commons.errors import CommonsError`.

- [ ] **Step 4: Run tests to verify they pass**

```
cd science && uv run pytest tests/test_commons_cli_promote.py -v
```

Expected: all five new CLI tests PASS.

- [ ] **Step 5: Run full science suite**

```
cd science && uv run pytest
```

Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/commons/cli.py \
        science/tests/test_commons_cli_promote.py
git commit -m "$(cat <<'EOF'
feat(commons/cli): add `commons promote paper` subgroup

Single-entity form `promote paper <paper:bibkey> --from <slug>` and bulk form
`promote paper --from <slug>... [--limit N]`. Dry-run is default; --apply
writes. Conflicts prompt in BOTH dry-run and --apply (faithful preview).

Refs docs/plans/2026-05-15-commons-promote-papers-design.md §6.1.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 21: Pilot rollout runbook

**Files:**
- Create: `docs/runbooks/promote-papers-pilot.md`

Single-task documentation. The pilot run is manual; this runbook captures the exact steps so it can be re-done idempotently. Goes under `docs/runbooks/` (creating the directory if it doesn't already exist — the repo convention is `docs/runbooks/` for one-off operational procedures; if no such directory exists in the repo, fall back to `docs/plans/2026-05-15-commons-promote-papers-pilot.md` to avoid spawning a new top-level docs directory per CLAUDE.md).

- [ ] **Step 1: Check whether `docs/runbooks/` already exists**

```bash
ls docs/runbooks/ 2>/dev/null && echo "USE runbooks" || echo "USE plans/"
```

If it exists, target file is `docs/runbooks/promote-papers-pilot.md`. If not, target file is `docs/plans/2026-05-15-commons-promote-papers-pilot.md`.

- [ ] **Step 2: Write the runbook**

Create the chosen file with:

```markdown
# Phase E pilot: promote papers (manual run)

This runbook records the exact procedure for the first production run of
`science commons promote paper`. It is not part of CI; it's a one-time
operational step after the implementation lands.

## Preconditions

1. **Commons store initialized.** Run once on this machine:
   ```bash
   science commons init
   ```
   This creates `~/d/science-commons/` with `papers/`, `datasets/`,
   `topics/`, `themes/`, `.migrations/`, and a `.git` repo.

2. **Project registry has `id:` for every pilot project.** Confirm:
   ```bash
   yq '.projects[] | select(.id != null) | .id' ~/.config/science/config.yaml
   ```
   Expected output includes `natural-systems`, `multiple-myeloma`, `meta`
   (cancer-meta), `evolution` (cancer-evolution), `protein-landscape`.
   If any of these have `id: null`, edit `~/.config/science/config.yaml`
   to assign an id (must be unique). The legacy `/mnt/ssd/Dropbox/r/mm30`
   registration is intentionally id:null — leave it alone; promote will
   not include it.

3. **Working trees clean.**
   ```bash
   for d in ~/d/science-commons ~/d/natural-systems ~/d/cancer/cancer-types/multiple-myeloma ~/d/cancer/meta ~/d/cancer/mechanisms/evolution ~/d/protein-landscape; do
     echo "== $d =="; cd "$d" && git status --short
   done
   ```
   Commit / stash any pending work in `~/d/science-commons`. For the
   project repos, only files under `doc/papers/*.md` must be clean;
   other dirty files are fine.

## Step 1: Dry-run

```bash
science commons promote paper \
  --from natural-systems \
  --from multiple-myeloma \
  --from meta \
  --from evolution \
  --from protein-landscape
```

Expected: ~503 candidates discovered, ~9 multi-instance bibkeys. The
command will prompt for each canonical-field conflict (most multi-instance
bibkeys will auto-merge without prompts).

Review the summary. If anything looks off, fix the source files and re-run.

## Step 2: Apply

```bash
science commons promote paper \
  --from natural-systems \
  --from multiple-myeloma \
  --from meta \
  --from evolution \
  --from protein-landscape \
  --apply
```

Expected:
- One commit in `~/d/science-commons` with all canonical paper files.
- ~503 tags `paper/<bibkey>/1.0.0`.
- One audit-log commit `audit: op <op-id>`.
- ~503 project overlay rewrites (uncommitted in each project — see step 3).

## Step 3: Commit overlays per project

Promote does NOT commit project rewrites. Review the rewrites in each
project, then commit:

```bash
for d in ~/d/natural-systems ~/d/cancer/cancer-types/multiple-myeloma ~/d/cancer/meta ~/d/cancer/mechanisms/evolution ~/d/protein-landscape; do
  cd "$d"
  echo "== $d =="
  git diff --stat doc/papers/
  echo "(review then run): git add doc/papers/ && git commit -m 'promote papers to commons'"
done
```

## Step 4: Verify

```bash
science commons find paper --type paper | head
science commons show paper:Huh2024
```

Should show the merged canonical entity. Try the dashboard:

```bash
# From ~/d/dashboard (assuming the inventory_v2 pivot is shipped):
make dev
```

Each project's view should show the paper with its project's overlay
applied (tags, related, body sections preserved per project).

## Rollback (if needed)

The audit log in `~/d/science-commons/.migrations/<ts>-<op-id>.yaml` carries
the exact commands to undo the run. Roughly:

```bash
# Revert the commons commit:
cd ~/d/science-commons && git revert <commit-hash>

# Restore project files (per project):
cd ~/d/natural-systems && git checkout HEAD -- doc/papers/
```

Do NOT use `git reset --hard` anywhere — the rollback procedure is
path-limited by design.
```

- [ ] **Step 3: Commit**

```bash
git add docs/runbooks/promote-papers-pilot.md 2>/dev/null || \
  git add docs/plans/2026-05-15-commons-promote-papers-pilot.md
git commit -m "$(cat <<'EOF'
docs: pilot rollout runbook for `commons promote paper`

Preconditions (commons init, registry id check, clean working trees), three-step
procedure (dry-run → apply → per-project commits), verification, and rollback.

Refs docs/plans/2026-05-15-commons-promote-papers-design.md §1 pilot target.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Final verification

After Task 21, run the full suites one last time:

```bash
cd /mnt/ssd/Dropbox/science/science/model && uv run pytest
cd /mnt/ssd/Dropbox/science/science && uv run pytest
```

Both must be green. If anything fails, the failure is a regression — fix in-place and re-commit.

Also try the CLI end-to-end against the fixtures:

```bash
cd /mnt/ssd/Dropbox/science/science && uv run pytest tests/test_commons_cli_promote.py -v
```

Plan ends here.


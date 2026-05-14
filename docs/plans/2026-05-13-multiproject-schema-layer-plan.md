# Multi-project Schema Layer Implementation Plan (Phase A)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the JSON Schema definitions, profile-string composition validator, merge-policy reader, and optional Pydantic wrapper that the shared-entity-store and overlay layers will depend on.

**Architecture:** New `science_model.entity_schema` Python module + new JSON Schema files in the existing `science_model/schemas/` package resource directory. Validator composes base + mixin + optional extensions at runtime via JSON Schema `allOf`. No store directory or resolver work in this phase — that's Phase B/C.

**Tech Stack:** Python 3.11+, Pydantic 2, `jsonschema>=4.26` (currently a dev dep in `science/model/pyproject.toml`; Task 4 promotes it to a runtime dep — phase B consumers installing `science-model` need it at import time), PyYAML 6, pytest.

**Spec:** [`docs/plans/2026-05-13-multiproject-schema-and-shared-store-design.md`](./2026-05-13-multiproject-schema-and-shared-store-design.md), §3 (schema), §3.6.1 (naming), §3.7 (validator), §3.8 (merge policy), §9 phase A.

---

## File Structure

**New JSON Schema files** (in existing `~/d/science/science/model/src/science_model/schemas/`):

```
schemas/
├── science-pkg-entity-1.0.json       # existing — unchanged
├── science-pkg-runtime-1.0.json      # existing — unchanged
├── science-entity-base-1.0.json      # NEW — base profile
├── mixin-dataset-1.0.json            # NEW — dataset mixin
├── mixin-paper-1.0.json              # NEW — paper mixin
├── mixin-topic-1.0.json              # NEW — topic mixin
├── mixin-theme-1.0.json              # NEW — theme mixin
├── extension-bio-rnaseq-1.0.json     # NEW — bio extension placeholder
└── overlay-1.0.json                  # NEW — overlay schema
```

**New Python module** (in `~/d/science/science/model/src/science_model/entity_schema/`):

```
entity_schema/
├── __init__.py        # public API
├── profile.py         # profile-string parser
├── loader.py          # schema file loading + caching
├── validator.py       # composing JSON Schema validator
├── merge.py           # science:merge annotation reader
└── wrapper.py         # optional Pydantic ergonomic wrapper
```

**Tests** (in `~/d/science/science/model/tests/`):

```
tests/
├── fixtures/
│   └── entity_schema/             # NEW — real-world fixture entities
│       ├── paper_Adams2025.md
│       ├── topic_single-cell-foundation-models.md
│       ├── theme_homology-aware-evaluation.md
│       ├── dataset_cath-domains/
│       │   ├── entity.md
│       │   └── datapackage.yaml
│       └── README.md              # provenance for each fixture
├── test_entity_schema_profile.py
├── test_entity_schema_loader.py
├── test_entity_schema_validator.py
├── test_entity_schema_base.py
├── test_entity_schema_mixin_dataset.py
├── test_entity_schema_mixin_paper.py
├── test_entity_schema_mixin_topic.py
├── test_entity_schema_mixin_theme.py
├── test_entity_schema_extension_bio.py
├── test_entity_schema_overlay.py
├── test_entity_schema_merge.py
├── test_entity_schema_wrapper.py
└── test_entity_schema_fixtures.py     # validates fixtures end-to-end
```

---

## Task 1: Bootstrap `entity_schema` module skeleton

**Files:**
- Create: `science/model/src/science_model/entity_schema/__init__.py`
- Create: `science/model/tests/test_entity_schema_smoke.py`

- [ ] **Step 1: Write the failing smoke test**

Create `science/model/tests/test_entity_schema_smoke.py`:

```python
from __future__ import annotations


def test_entity_schema_module_importable() -> None:
    import science_model.entity_schema as es

    assert hasattr(es, "__all__")
    assert isinstance(es.__all__, list)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/d/science/science/model && uv run pytest tests/test_entity_schema_smoke.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'science_model.entity_schema'`

- [ ] **Step 3: Create the module**

Create `science/model/src/science_model/entity_schema/__init__.py`:

```python
"""Multi-project entity schema layer.

Composes a Frictionless-inspired base schema with type mixins (dataset,
paper, topic, theme) and optional domain extensions (e.g. bio.rnaseq).

See docs/plans/2026-05-13-multiproject-schema-and-shared-store-design.md
section 3 for the design.
"""

from __future__ import annotations

__all__: list[str] = []
```

- [ ] **Step 4: Verify test passes**

Run: `cd ~/d/science/science/model && uv run pytest tests/test_entity_schema_smoke.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd ~/d/science/science/model
git add src/science_model/entity_schema/__init__.py tests/test_entity_schema_smoke.py
git commit -m "feat(entity_schema): bootstrap empty module"
```

---

## Task 2: Profile-string parser (`profile.py`)

**Files:**
- Create: `science/model/src/science_model/entity_schema/profile.py`
- Create: `science/model/tests/test_entity_schema_profile.py`

The schema_profile string format is `<schema>/<version>(+<schema>/<version>)*` where the first component is the base (always `science-entity-base/<ver>`), the second is a type mixin (`dataset/<ver>`, `paper/<ver>`, `topic/<ver>`, `theme/<ver>`), and remaining components are extensions (`bio.rnaseq/<ver>`, etc.). See spec §3.6.

- [ ] **Step 1: Write the failing test**

Create `science/model/tests/test_entity_schema_profile.py`:

```python
from __future__ import annotations

import pytest

from science_model.entity_schema.profile import (
    ProfileComponent,
    ProfileParseError,
    ProfileString,
    parse_profile,
)


def test_parse_minimal_base_only() -> None:
    parsed = parse_profile("science-entity-base/1.0")
    assert parsed.base == ProfileComponent(name="science-entity-base", version="1.0")
    assert parsed.mixin is None
    assert parsed.extensions == ()


def test_parse_base_plus_dataset_mixin() -> None:
    parsed = parse_profile("science-entity-base/1.0+dataset/1.0")
    assert parsed.base.name == "science-entity-base"
    assert parsed.mixin == ProfileComponent(name="dataset", version="1.0")
    assert parsed.extensions == ()


def test_parse_base_plus_mixin_plus_extension() -> None:
    parsed = parse_profile("science-entity-base/1.0+dataset/1.0+bio.rnaseq/1.0")
    assert parsed.mixin.name == "dataset"
    assert parsed.extensions == (ProfileComponent(name="bio.rnaseq", version="1.0"),)


def test_parse_multiple_extensions_preserves_order() -> None:
    parsed = parse_profile(
        "science-entity-base/1.0+dataset/1.0+bio.rnaseq/1.0+bio.scrna/1.0"
    )
    assert [ext.name for ext in parsed.extensions] == ["bio.rnaseq", "bio.scrna"]


def test_parse_rejects_missing_base() -> None:
    # f"{BASE_NAME!r}" renders with single quotes, so the regex must include them.
    with pytest.raises(ProfileParseError, match="must start with 'science-entity-base'"):
        parse_profile("dataset/1.0")


def test_parse_rejects_missing_version() -> None:
    with pytest.raises(ProfileParseError, match="missing version"):
        parse_profile("science-entity-base+dataset/1.0")


def test_parse_rejects_empty_string() -> None:
    with pytest.raises(ProfileParseError, match="empty"):
        parse_profile("")


def test_parse_rejects_unknown_mixin_position() -> None:
    # A second base-name in mixin slot is invalid.
    with pytest.raises(ProfileParseError, match="mixin"):
        parse_profile("science-entity-base/1.0+science-entity-base/1.0")


def test_render_round_trips() -> None:
    raw = "science-entity-base/1.0+dataset/1.0+bio.rnaseq/1.0"
    assert parse_profile(raw).render() == raw
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/d/science/science/model && uv run pytest tests/test_entity_schema_profile.py -v`
Expected: FAIL with import error.

- [ ] **Step 3: Implement the parser**

Create `science/model/src/science_model/entity_schema/profile.py`:

```python
"""Parse and render schema_profile strings.

Format: <base>/<ver>(+<mixin>/<ver>)?(+<ext>/<ver>)*

Examples:
  "science-entity-base/1.0"
  "science-entity-base/1.0+dataset/1.0"
  "science-entity-base/1.0+dataset/1.0+bio.rnaseq/1.0+bio.scrna/1.0"
"""

from __future__ import annotations

from dataclasses import dataclass

BASE_NAME = "science-entity-base"
TYPE_MIXIN_NAMES = frozenset({"dataset", "paper", "topic", "theme"})


class ProfileParseError(ValueError):
    """Raised when a schema_profile string is malformed."""


@dataclass(frozen=True, slots=True)
class ProfileComponent:
    name: str
    version: str

    def render(self) -> str:
        return f"{self.name}/{self.version}"


@dataclass(frozen=True, slots=True)
class ProfileString:
    base: ProfileComponent
    mixin: ProfileComponent | None
    extensions: tuple[ProfileComponent, ...]

    def render(self) -> str:
        parts = [self.base.render()]
        if self.mixin is not None:
            parts.append(self.mixin.render())
        parts.extend(ext.render() for ext in self.extensions)
        return "+".join(parts)


def parse_profile(raw: str) -> ProfileString:
    if not raw:
        raise ProfileParseError("schema_profile is empty")
    components = [_parse_component(token) for token in raw.split("+")]
    base = components[0]
    if base.name != BASE_NAME:
        raise ProfileParseError(
            f"schema_profile must start with {BASE_NAME!r}, got {base.name!r}"
        )
    if len(components) == 1:
        return ProfileString(base=base, mixin=None, extensions=())
    mixin = components[1]
    if mixin.name not in TYPE_MIXIN_NAMES:
        raise ProfileParseError(
            f"schema_profile mixin must be one of {sorted(TYPE_MIXIN_NAMES)!r}, "
            f"got {mixin.name!r}"
        )
    return ProfileString(base=base, mixin=mixin, extensions=tuple(components[2:]))


def _parse_component(token: str) -> ProfileComponent:
    if "/" not in token:
        raise ProfileParseError(f"profile component {token!r} missing version (expected 'name/version')")
    name, version = token.split("/", 1)
    if not name or not version:
        raise ProfileParseError(f"profile component {token!r} has empty name or version")
    return ProfileComponent(name=name, version=version)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/d/science/science/model && uv run pytest tests/test_entity_schema_profile.py -v`
Expected: 9 PASS.

- [ ] **Step 5: Commit**

```bash
cd ~/d/science/science/model
git add src/science_model/entity_schema/profile.py tests/test_entity_schema_profile.py
git commit -m "feat(entity_schema): profile-string parser"
```

---

## Task 3: Schema loader (`loader.py`)

**Files:**
- Create: `science/model/src/science_model/entity_schema/loader.py`
- Create: `science/model/tests/test_entity_schema_loader.py`

The loader resolves a `ProfileComponent` to its on-disk JSON Schema file path within the `science_model.schemas` package resource directory, then caches loaded schemas. Filename convention: `<name>-<version>.json` for base/extensions, `mixin-<name>-<version>.json` for mixins.

This task tests **only what can pass without the new schema files yet existing** — filename mapping logic and the `SchemaNotFoundError` path. Task 5 will add the integration test that asserts `loader.load(...)` returns real schema content; Tasks 6–10 do the same for mixins/extensions as those land.

- [ ] **Step 1: Write the failing test**

Create `science/model/tests/test_entity_schema_loader.py`:

```python
from __future__ import annotations

import pytest

from science_model.entity_schema.loader import (
    SchemaLoader,
    SchemaNotFoundError,
    _filename_for,
)
from science_model.entity_schema.profile import ProfileComponent


def test_filename_for_base() -> None:
    component = ProfileComponent(name="science-entity-base", version="1.0")
    assert _filename_for(component) == "science-entity-base-1.0.json"


def test_filename_for_mixin() -> None:
    assert _filename_for(ProfileComponent(name="dataset", version="1.0")) == "mixin-dataset-1.0.json"
    assert _filename_for(ProfileComponent(name="paper", version="1.0")) == "mixin-paper-1.0.json"


def test_filename_for_extension_flattens_dots() -> None:
    component = ProfileComponent(name="bio.rnaseq", version="1.0")
    assert _filename_for(component) == "extension-bio-rnaseq-1.0.json"


def test_loader_raises_schema_not_found_for_unknown_component() -> None:
    loader = SchemaLoader()
    with pytest.raises(SchemaNotFoundError, match="nonexistent"):
        loader.load(ProfileComponent(name="nonexistent", version="1.0"))


def test_loader_caches_lookups_per_component() -> None:
    # Cache hit returns the same dict instance without re-loading. Prime the
    # private cache directly to avoid depending on schema files that don't
    # exist yet in this task.
    loader = SchemaLoader()
    fake = {"$id": "stub.json"}
    loader._cache[("science-entity-base", "1.0")] = fake
    first = loader.load(ProfileComponent(name="science-entity-base", version="1.0"))
    second = loader.load(ProfileComponent(name="science-entity-base", version="1.0"))
    assert first is fake
    assert first is second
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/d/science/science/model && uv run pytest tests/test_entity_schema_loader.py -v`
Expected: FAIL with import error (`science_model.entity_schema.loader` does not exist yet).

- [ ] **Step 3: Implement the loader**

Create `science/model/src/science_model/entity_schema/loader.py`:

```python
"""Load JSON Schema files for the multi-project entity schema layer."""

from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources
from typing import Any

from science_model.entity_schema.profile import (
    BASE_NAME,
    TYPE_MIXIN_NAMES,
    ProfileComponent,
)

_SCHEMAS_PACKAGE = "science_model.schemas"


class SchemaNotFoundError(FileNotFoundError):
    """Raised when a profile component does not map to a known schema file."""


class SchemaLoader:
    """Resolve profile components to JSON Schema dicts, with caching."""

    def __init__(self) -> None:
        self._cache: dict[tuple[str, str], dict[str, Any]] = {}

    def load(self, component: ProfileComponent) -> dict[str, Any]:
        key = (component.name, component.version)
        if key in self._cache:
            return self._cache[key]
        filename = _filename_for(component)
        schema = _load_resource(filename)
        self._cache[key] = schema
        return schema


def _filename_for(component: ProfileComponent) -> str:
    if component.name == BASE_NAME:
        return f"{component.name}-{component.version}.json"
    if component.name in TYPE_MIXIN_NAMES:
        return f"mixin-{component.name}-{component.version}.json"
    # Extensions: replace dots with hyphens (e.g. bio.rnaseq -> bio-rnaseq).
    flat = component.name.replace(".", "-")
    return f"extension-{flat}-{component.version}.json"


@lru_cache(maxsize=None)
def _list_resources() -> frozenset[str]:
    return frozenset(r.name for r in resources.files(_SCHEMAS_PACKAGE).iterdir())


def _load_resource(filename: str) -> dict[str, Any]:
    if filename not in _list_resources():
        raise SchemaNotFoundError(f"schema resource {filename!r} not found in {_SCHEMAS_PACKAGE}")
    text = resources.files(_SCHEMAS_PACKAGE).joinpath(filename).read_text(encoding="utf-8")
    return json.loads(text)
```

- [ ] **Step 4: Verify tests pass**

Run: `cd ~/d/science/science/model && uv run pytest tests/test_entity_schema_loader.py -v`
Expected: 5 PASS (filename mapping + cache + not-found path all green; no real schema dependencies).

- [ ] **Step 5: Commit**

```bash
cd ~/d/science/science/model
git add src/science_model/entity_schema/loader.py tests/test_entity_schema_loader.py
git commit -m "feat(entity_schema): schema loader with package-resource discovery"
```

---

## Task 4: Composing validator (`validator.py`)

**Files:**
- Modify: `science/model/pyproject.toml` (promote `jsonschema` to runtime dep)
- Modify: `science/model/uv.lock` (regenerated by `uv sync`)
- Create: `science/model/src/science_model/entity_schema/validator.py`
- Create: `science/model/tests/test_entity_schema_validator.py`

The validator parses an entity's `schema_profile`, composes base+mixin+extensions into a single `allOf` schema, and validates with `jsonschema.Draft202012Validator`. **Format strings (`format: date`)** are enforced via `Draft202012Validator.FORMAT_CHECKER`. **Base-only profiles are rejected at `.validate()`** — every entity payload must carry at least one type mixin. The parser still accepts base-only strings so unit tests and internal code paths can construct them, but `EntityValidator.validate()` is the entity-payload entry point and refuses them.

This task's tests do not depend on any new schema file existing (composition + mixin-driven validation arrives in Task 6, which runs the validator against a `base+dataset/1.0` entity). Here we cover only the error paths that are reachable without real schemas: missing `schema_profile`, malformed `schema_profile`, and base-only `schema_profile`.

- [ ] **Step 1: Promote `jsonschema` from dev to runtime dep**

Modify `science/model/pyproject.toml`:

```toml
dependencies = [
  "pydantic>=2.0",
  "pyyaml>=6.0.3",
  "jsonschema>=4.26",
]
```

Also remove `jsonschema>=4.26.0` from the `[dependency-groups].dev` list. Then regenerate the lockfile:

```bash
cd ~/d/science/science/model && uv sync
```

This refreshes `uv.lock`; both `pyproject.toml` and `uv.lock` MUST be staged in the same commit as the validator code so the dependency change lands atomically.

- [ ] **Step 2: Write the failing test**

Create `science/model/tests/test_entity_schema_validator.py`:

```python
from __future__ import annotations

import pytest

from science_model.entity_schema.validator import (
    EntityValidationError,
    EntityValidator,
)


def test_validator_rejects_entity_with_missing_schema_profile() -> None:
    validator = EntityValidator()
    with pytest.raises(EntityValidationError, match="schema_profile"):
        validator.validate({"id": "paper:Adams2025", "type": "paper"})


def test_validator_rejects_malformed_schema_profile() -> None:
    validator = EntityValidator()
    with pytest.raises(EntityValidationError, match="invalid schema_profile"):
        validator.validate({"schema_profile": "not-a-real-base/1.0", "id": "x:y"})


def test_validator_rejects_base_only_schema_profile() -> None:
    # A base-only profile bypasses type-specific constraints, so refuse it.
    validator = EntityValidator()
    with pytest.raises(EntityValidationError, match="mixin"):
        validator.validate({
            "schema_profile": "science-entity-base/1.0",
            "id": "paper:Adams2025",
            "type": "paper",
            "title": "x",
            "version": "1.0.0",
            "created": "2026-05-13",
            "updated": "2026-05-13",
        })
```

(Composition + happy-path validation are exercised in Task 6, which has the `dataset` mixin available.)

- [ ] **Step 3: Run test to verify it fails**

Run: `cd ~/d/science/science/model && uv run pytest tests/test_entity_schema_validator.py -v`
Expected: FAIL with module import error.

- [ ] **Step 4: Implement the validator**

Create `science/model/src/science_model/entity_schema/validator.py`:

```python
"""Compose and apply multi-component entity schemas."""

from __future__ import annotations

from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError as _JsonValidationError

from science_model.entity_schema.loader import SchemaLoader
from science_model.entity_schema.profile import (
    ProfileParseError,
    ProfileString,
    parse_profile,
)


class EntityValidationError(ValueError):
    """Raised when an entity does not satisfy its composed schema."""

    def __init__(self, message: str, errors: list[_JsonValidationError] | None = None) -> None:
        super().__init__(message)
        self.errors = errors or []


class EntityValidator:
    """Validate an entity against its declared schema_profile."""

    def __init__(self, loader: SchemaLoader | None = None) -> None:
        self._loader = loader or SchemaLoader()

    def validate(self, entity: dict[str, Any]) -> None:
        profile_str = entity.get("schema_profile")
        if not profile_str:
            raise EntityValidationError("entity is missing required schema_profile field")
        try:
            profile = parse_profile(profile_str)
        except ProfileParseError as exc:
            raise EntityValidationError(f"invalid schema_profile: {exc}") from exc
        if profile.mixin is None:
            raise EntityValidationError(
                "schema_profile must include a type mixin "
                "(dataset/paper/topic/theme) — base-only profiles are not "
                "valid for entity payloads",
            )
        composed = self._compose(profile)
        validator = Draft202012Validator(
            composed,
            format_checker=Draft202012Validator.FORMAT_CHECKER,
        )
        errors = sorted(validator.iter_errors(entity), key=lambda e: list(e.absolute_path))
        if errors:
            joined = "; ".join(_format_error(err) for err in errors)
            raise EntityValidationError(
                f"entity failed schema validation: {joined}",
                errors=errors,
            )

    def _compose(self, profile: ProfileString) -> dict[str, Any]:
        parts = [self._loader.load(profile.base)]
        if profile.mixin is not None:
            parts.append(self._loader.load(profile.mixin))
        parts.extend(self._loader.load(ext) for ext in profile.extensions)
        return {"allOf": parts}


def _format_error(err: _JsonValidationError) -> str:
    path = ".".join(str(segment) for segment in err.absolute_path) or "<root>"
    return f"{path}: {err.message}"
```

- [ ] **Step 5: Verify tests pass**

Run: `cd ~/d/science/science/model && uv run pytest tests/test_entity_schema_validator.py -v`
Expected: 3 PASS (all three error paths reachable without real schemas).

- [ ] **Step 6: Commit**

```bash
cd ~/d/science/science/model
git add pyproject.toml uv.lock \
        src/science_model/entity_schema/validator.py \
        tests/test_entity_schema_validator.py
git commit -m "feat(entity_schema): composing JSON Schema validator"
```

---

## Task 5: Base schema (`science-entity-base-1.0.json`)

**Files:**
- Create: `science/model/src/science_model/schemas/science-entity-base-1.0.json`
- Create: `science/model/tests/test_entity_schema_base.py`

The base schema declares the shared frontmatter fields per spec §3.1. Per-type slug regex is enforced in mixins (Task 6+), not the base. The base only requires the universal fields.

- [ ] **Step 1: Write the failing test**

Create `science/model/tests/test_entity_schema_base.py`:

```python
from __future__ import annotations

import pytest
from jsonschema import Draft202012Validator

from science_model.entity_schema.loader import SchemaLoader
from science_model.entity_schema.profile import ProfileComponent


@pytest.fixture
def base_schema() -> dict:
    loader = SchemaLoader()
    return loader.load(ProfileComponent(name="science-entity-base", version="1.0"))


def test_base_accepts_minimal_valid_entity(base_schema: dict) -> None:
    entity = {
        "schema_profile": "science-entity-base/1.0+paper/1.0",
        "id": "paper:Adams2025",
        "type": "paper",
        "title": "Example",
        "version": "1.0.0",
        "created": "2026-05-13",
        "updated": "2026-05-13",
    }
    Draft202012Validator(base_schema).validate(entity)


def test_base_rejects_missing_id(base_schema: dict) -> None:
    entity = {
        "schema_profile": "science-entity-base/1.0+paper/1.0",
        "type": "paper",
        "title": "x",
        "version": "1.0.0",
        "created": "2026-05-13",
        "updated": "2026-05-13",
    }
    with pytest.raises(Exception):
        Draft202012Validator(base_schema).validate(entity)


def test_base_rejects_invalid_version_format(base_schema: dict) -> None:
    entity = {
        "schema_profile": "science-entity-base/1.0+paper/1.0",
        "id": "paper:Adams2025",
        "type": "paper",
        "title": "x",
        "version": "v1",  # invalid; must be semver
        "created": "2026-05-13",
        "updated": "2026-05-13",
    }
    with pytest.raises(Exception):
        Draft202012Validator(base_schema).validate(entity)


def test_base_rejects_invalid_type_value(base_schema: dict) -> None:
    entity = {
        "schema_profile": "science-entity-base/1.0+paper/1.0",
        "id": "x:y",
        "type": "unknown-type",
        "title": "x",
        "version": "1.0.0",
        "created": "2026-05-13",
        "updated": "2026-05-13",
    }
    with pytest.raises(Exception):
        Draft202012Validator(base_schema).validate(entity)


def test_base_accepts_optional_fields_when_present(base_schema: dict) -> None:
    entity = {
        "schema_profile": "science-entity-base/1.0+paper/1.0",
        "id": "paper:Adams2025",
        "type": "paper",
        "title": "x",
        "version": "1.0.0",
        "description": "A description",
        "created": "2026-05-13",
        "updated": "2026-05-13",
        "sources": ["doi:10.1234/abc", "cite:Adams2025"],
        "licenses": ["CC-BY-4.0"],
        "contributors": [{"name": "Ada", "role": "author"}],
        "ontology_terms": ["EFO:0000001"],
        "tags": ["high-priority"],
    }
    Draft202012Validator(base_schema).validate(entity)


def test_base_rejects_invalid_date_format(base_schema: dict) -> None:
    # Validator must construct Draft202012Validator with FORMAT_CHECKER for
    # format: "date" to actually fire (jsonschema default ignores formats).
    entity = {
        "schema_profile": "science-entity-base/1.0+paper/1.0",
        "id": "paper:Adams2025",
        "type": "paper",
        "title": "x",
        "version": "1.0.0",
        "created": "not-a-date",
        "updated": "2026-05-13",
    }
    with pytest.raises(Exception, match="date"):
        Draft202012Validator(
            base_schema,
            format_checker=Draft202012Validator.FORMAT_CHECKER,
        ).validate(entity)


def test_loader_resolves_base_schema_now_that_it_exists() -> None:
    # This is the integration test we deferred from Task 3.
    schema = SchemaLoader().load(ProfileComponent(name="science-entity-base", version="1.0"))
    assert schema["$id"].endswith("science-entity-base-1.0.json")
    assert schema["type"] == "object"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/d/science/science/model && uv run pytest tests/test_entity_schema_base.py -v`
Expected: FAIL with `SchemaNotFoundError`.

- [ ] **Step 3: Create the base schema**

Create `science/model/src/science_model/schemas/science-entity-base-1.0.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://schemas.science/science-entity-base-1.0.json",
  "title": "science entity base profile",
  "type": "object",
  "required": [
    "schema_profile",
    "id",
    "type",
    "title",
    "version",
    "created",
    "updated"
  ],
  "properties": {
    "schema_profile": {
      "type": "string",
      "pattern": "^science-entity-base/[0-9]+\\.[0-9]+(\\+[a-z][a-z0-9.-]*/[0-9]+\\.[0-9]+)*$"
    },
    "id": {
      "type": "string",
      "pattern": "^(dataset|paper|topic|theme):[A-Za-z0-9][A-Za-z0-9-]{0,63}$"
    },
    "type": {
      "enum": ["dataset", "paper", "topic", "theme"]
    },
    "title": {"type": "string", "minLength": 1},
    "version": {
      "type": "string",
      "pattern": "^[0-9]+\\.[0-9]+\\.[0-9]+$"
    },
    "description": {"type": "string"},
    "created": {"type": "string", "format": "date"},
    "updated": {"type": "string", "format": "date"},
    "sources": {"type": "array", "items": {"type": "string"}},
    "licenses": {
      "type": "array",
      "items": {
        "oneOf": [
          {"type": "string"},
          {
            "type": "object",
            "required": ["name"],
            "properties": {
              "name": {"type": "string"},
              "path": {"type": "string"},
              "title": {"type": "string"}
            }
          }
        ]
      }
    },
    "contributors": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["name"],
        "properties": {
          "name": {"type": "string"},
          "email": {"type": "string"},
          "role": {"type": "string"}
        }
      }
    },
    "ontology_terms": {"type": "array", "items": {"type": "string"}},
    "tags": {"type": "array", "items": {"type": "string"}},
    "status": {"type": "string"}
  }
}
```

- [ ] **Step 4: Verify tests pass**

Run: `cd ~/d/science/science/model && uv run pytest tests/test_entity_schema_base.py tests/test_entity_schema_loader.py -v`
Expected: all PASS — base tests (including the new date-format negative case and the loader integration test deferred from Task 3) plus the loader unit tests from Task 3.

- [ ] **Step 5: Commit**

```bash
cd ~/d/science/science/model
git add src/science_model/schemas/science-entity-base-1.0.json tests/test_entity_schema_base.py
git commit -m "feat(entity_schema): base profile JSON Schema"
```

---

## Task 6: Dataset mixin (`mixin-dataset-1.0.json`)

**Files:**
- Create: `science/model/src/science_model/schemas/mixin-dataset-1.0.json`
- Create: `science/model/tests/test_entity_schema_mixin_dataset.py`

The dataset mixin tightens `type` to `dataset`, requires the dataset-specific fields per spec §3.2, and enforces the existing `if/then/else` invariants from `science-pkg-entity-1.0.json` (`access` required for `origin: external`, `derivation` required for `origin: derived`). It explicitly forbids `resources[]` — those live in the sibling `datapackage.yaml` (spec §3.2).

- [ ] **Step 1: Write the failing test**

Create `science/model/tests/test_entity_schema_mixin_dataset.py`:

```python
from __future__ import annotations

import pytest

from science_model.entity_schema.validator import EntityValidationError, EntityValidator


@pytest.fixture
def base_entity() -> dict:
    return {
        "schema_profile": "science-entity-base/1.0+dataset/1.0",
        "id": "dataset:cath-domains",
        "type": "dataset",
        "title": "CATH domain database",
        "version": "1.0.0",
        "created": "2026-05-13",
        "updated": "2026-05-13",
        "datapackage": "datapackage.yaml",
        "tier": "use-now",
    }


def test_dataset_external_with_access_validates(base_entity: dict) -> None:
    entity = base_entity | {
        "origin": "external",
        "access": {"level": "public", "verified": True},
        "accessions": ["CATH:v4_3_0"],
    }
    EntityValidator().validate(entity)


def test_dataset_derived_with_derivation_validates(base_entity: dict) -> None:
    entity = base_entity | {
        "origin": "derived",
        "derivation": {
            "workflow_recipe": "recipe/Snakefile",
            "recipe_lockfile": "recipe/lockfile.yaml",
            "inputs": ["dataset:upstream"],
        },
    }
    EntityValidator().validate(entity)


def test_dataset_external_missing_access_rejected(base_entity: dict) -> None:
    entity = base_entity | {"origin": "external"}
    with pytest.raises(EntityValidationError, match="access"):
        EntityValidator().validate(entity)


def test_dataset_with_resources_field_rejected(base_entity: dict) -> None:
    entity = base_entity | {
        "origin": "external",
        "access": {"level": "public", "verified": True},
        "resources": [{"name": "x", "path": "x.parquet"}],
    }
    with pytest.raises(EntityValidationError, match="resources"):
        EntityValidator().validate(entity)


def test_dataset_id_must_start_with_dataset_prefix(base_entity: dict) -> None:
    entity = base_entity | {
        "id": "paper:wrong",
        "origin": "external",
        "access": {"level": "public", "verified": True},
    }
    with pytest.raises(EntityValidationError):
        EntityValidator().validate(entity)


def test_dataset_id_slug_lowercase_kebab_only(base_entity: dict) -> None:
    entity = base_entity | {
        "id": "dataset:NotKebab",  # uppercase rejected for datasets
        "origin": "external",
        "access": {"level": "public", "verified": True},
    }
    with pytest.raises(EntityValidationError):
        EntityValidator().validate(entity)


# --- composition + aggregated-error coverage previously deferred from Task 4 ---


def test_validator_composes_base_plus_dataset_mixin() -> None:
    # End-to-end happy path: base + dataset/1.0 schemas now both exist, so a
    # real entity should validate. Confirms the validator's allOf composition
    # actually combines schemas correctly.
    entity = {
        "schema_profile": "science-entity-base/1.0+dataset/1.0",
        "id": "dataset:cath-domains",
        "type": "dataset",
        "title": "CATH domain database",
        "version": "1.0.0",
        "created": "2026-05-13",
        "updated": "2026-05-13",
        "datapackage": "datapackage.yaml",
        "origin": "external",
        "tier": "use-now",
        "access": {"level": "public", "verified": True},
    }
    EntityValidator().validate(entity)


def test_validator_aggregates_errors_across_base_and_mixin() -> None:
    bad = {
        "schema_profile": "science-entity-base/1.0+dataset/1.0",
        # missing base-required (id, type, title, version, created, updated)
        # AND mixin-required (datapackage, origin, tier).
    }
    with pytest.raises(EntityValidationError) as info:
        EntityValidator().validate(bad)
    message = str(info.value)
    # At least one base error and one mixin error present in the joined message.
    assert "title" in message
    assert "datapackage" in message
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/d/science/science/model && uv run pytest tests/test_entity_schema_mixin_dataset.py -v`
Expected: FAIL with `SchemaNotFoundError`.

- [ ] **Step 3: Create the dataset mixin schema**

Create `science/model/src/science_model/schemas/mixin-dataset-1.0.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://schemas.science/mixin-dataset-1.0.json",
  "title": "science entity dataset mixin",
  "type": "object",
  "required": ["id", "type", "datapackage", "origin", "tier"],
  "properties": {
    "id": {"type": "string", "pattern": "^dataset:[a-z0-9][a-z0-9-]{0,63}$"},
    "type": {"const": "dataset"},
    "datapackage": {"type": "string", "minLength": 1},
    "origin": {"enum": ["external", "derived"]},
    "tier": {"enum": ["use-now", "evaluate-next", "track"]},
    "update_cadence": {"type": "string"},
    "accessions": {"type": "array", "items": {"type": "string"}},
    "access": {"$ref": "#/$defs/access"},
    "derivation": {"$ref": "#/$defs/derivation"},
    "parent_dataset": {"type": "string"},
    "siblings": {"type": "array", "items": {"type": "string"}},
    "consumed_by": {"type": "array", "items": {"type": "string"}}
  },
  "not": {"required": ["resources"]},
  "allOf": [
    {
      "if": {"properties": {"origin": {"const": "external"}}, "required": ["origin"]},
      "then": {
        "required": ["access"],
        "not": {"required": ["derivation"]}
      }
    },
    {
      "if": {"properties": {"origin": {"const": "derived"}}, "required": ["origin"]},
      "then": {
        "required": ["derivation"],
        "not": {"anyOf": [{"required": ["access"]}, {"required": ["accessions"]}]}
      }
    }
  ],
  "$defs": {
    "access": {
      "type": "object",
      "required": ["level", "verified"],
      "properties": {
        "level": {"enum": ["public", "registration", "controlled", "commercial", "mixed"]},
        "availability": {"enum": ["available", "embargoed", "withdrawn"]},
        "verified": {"type": "boolean"},
        "verification_method": {"enum": ["", "retrieved", "credential-confirmed"]},
        "last_reviewed": {"type": "string"},
        "verified_by": {"type": "string"},
        "source_url": {"type": "string"},
        "credentials_required": {"type": "string"}
      }
    },
    "derivation": {
      "type": "object",
      "required": ["workflow_recipe", "inputs"],
      "properties": {
        "workflow_recipe": {"type": "string"},
        "recipe_lockfile": {"type": "string"},
        "inputs": {"type": "array", "items": {"type": "string", "pattern": "^dataset:"}}
      }
    }
  }
}
```

- [ ] **Step 4: Verify tests pass**

Run: `cd ~/d/science/science/model && uv run pytest tests/test_entity_schema_mixin_dataset.py tests/test_entity_schema_validator.py -v`
Expected: PASS — dataset mixin tests + the previously-passing validator error-path tests (unchanged).

- [ ] **Step 5: Commit**

```bash
cd ~/d/science/science/model
git add src/science_model/schemas/mixin-dataset-1.0.json tests/test_entity_schema_mixin_dataset.py
git commit -m "feat(entity_schema): dataset mixin schema + validator composition tests"
```

---

## Task 7: Paper mixin (`mixin-paper-1.0.json`)

**Files:**
- Create: `science/model/src/science_model/schemas/mixin-paper-1.0.json`
- Create: `science/model/tests/test_entity_schema_mixin_paper.py`

Per spec §3.3 + §3.1, paper IDs use bibkey form (`^[A-Za-z][A-Za-z0-9]{1,63}$`). Required fields match the existing template; spec-specific richer fields (bibkey, authors, year, doi, datasets, key_findings, methods_summary, limitations, model_or_tool_availability) are optional and validated when present.

- [ ] **Step 1: Write the failing test**

Create `science/model/tests/test_entity_schema_mixin_paper.py`:

```python
from __future__ import annotations

import pytest

from science_model.entity_schema.validator import EntityValidationError, EntityValidator


@pytest.fixture
def base_entity() -> dict:
    return {
        "schema_profile": "science-entity-base/1.0+paper/1.0",
        "id": "paper:Adams2025",
        "type": "paper",
        "title": "An interesting paper",
        "version": "1.0.0",
        "status": "active",
        "created": "2026-05-13",
        "updated": "2026-05-13",
    }


def test_paper_minimal_validates(base_entity: dict) -> None:
    EntityValidator().validate(base_entity)


def test_paper_with_rich_fields_validates(base_entity: dict) -> None:
    entity = base_entity | {
        "bibkey": "Adams2025",
        "authors": ["Adams, A.", "Baker, B."],
        "year": 2025,
        "journal": "Nature Methods",
        "doi": "10.1038/x.y.z",
        "url": "https://example.org/Adams2025",
        "datasets": ["dataset:cath-domains"],
        "key_findings": ["finding 1", "finding 2"],
        "methods_summary": "They used method X.",
        "limitations": ["small sample"],
        "model_or_tool_availability": "available at https://...",
    }
    EntityValidator().validate(entity)


def test_paper_id_lowercase_slug_rejected(base_entity: dict) -> None:
    entity = base_entity | {"id": "paper:adams-2025"}  # kebab rejected for papers
    with pytest.raises(EntityValidationError):
        EntityValidator().validate(entity)


def test_paper_id_bibkey_accepted(base_entity: dict) -> None:
    entity = base_entity | {"id": "paper:BarrioHernandez2023"}
    EntityValidator().validate(entity)


def test_paper_year_rejects_non_integer(base_entity: dict) -> None:
    entity = base_entity | {"year": "2025"}
    with pytest.raises(EntityValidationError):
        EntityValidator().validate(entity)


def test_paper_datasets_must_be_dataset_refs(base_entity: dict) -> None:
    entity = base_entity | {"datasets": ["paper:OtherThing"]}
    with pytest.raises(EntityValidationError):
        EntityValidator().validate(entity)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/d/science/science/model && uv run pytest tests/test_entity_schema_mixin_paper.py -v`
Expected: FAIL with `SchemaNotFoundError`.

- [ ] **Step 3: Create the paper mixin schema**

Create `science/model/src/science_model/schemas/mixin-paper-1.0.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://schemas.science/mixin-paper-1.0.json",
  "title": "science entity paper mixin",
  "type": "object",
  "required": ["id", "type"],
  "properties": {
    "id": {"type": "string", "pattern": "^paper:[A-Za-z][A-Za-z0-9]{1,63}$"},
    "type": {"const": "paper"},
    "bibkey": {"type": "string", "pattern": "^[A-Za-z][A-Za-z0-9]{1,63}$"},
    "authors": {"type": "array", "items": {"type": "string"}},
    "year": {"type": "integer", "minimum": 1800, "maximum": 2200},
    "journal": {"type": "string"},
    "doi": {"type": "string"},
    "url": {"type": "string"},
    "datasets": {
      "type": "array",
      "items": {"type": "string", "pattern": "^dataset:"}
    },
    "key_findings": {"type": "array", "items": {"type": "string"}},
    "methods_summary": {"type": "string"},
    "limitations": {"type": "array", "items": {"type": "string"}},
    "model_or_tool_availability": {"type": "string"}
  }
}
```

- [ ] **Step 4: Verify tests pass**

Run: `cd ~/d/science/science/model && uv run pytest tests/test_entity_schema_mixin_paper.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd ~/d/science/science/model
git add src/science_model/schemas/mixin-paper-1.0.json tests/test_entity_schema_mixin_paper.py
git commit -m "feat(entity_schema): paper mixin schema"
```

---

## Task 8: Topic mixin (`mixin-topic-1.0.json`)

**Files:**
- Create: `science/model/src/science_model/schemas/mixin-topic-1.0.json`
- Create: `science/model/tests/test_entity_schema_mixin_topic.py`

Mirrors current `topic.md` template (frontmatter: id, type, title, status, ontology_terms, datasets, source_refs, related, created, updated). Slug is lowercase-kebab.

- [ ] **Step 1: Write the failing test**

Create `science/model/tests/test_entity_schema_mixin_topic.py`:

```python
from __future__ import annotations

import pytest

from science_model.entity_schema.validator import EntityValidationError, EntityValidator


@pytest.fixture
def base_entity() -> dict:
    return {
        "schema_profile": "science-entity-base/1.0+topic/1.0",
        "id": "topic:single-cell-foundation-models",
        "type": "topic",
        "title": "Single-cell foundation models",
        "version": "1.0.0",
        "status": "active",
        "created": "2026-05-13",
        "updated": "2026-05-13",
    }


def test_topic_minimal_validates(base_entity: dict) -> None:
    EntityValidator().validate(base_entity)


def test_topic_full_validates(base_entity: dict) -> None:
    entity = base_entity | {
        "datasets": ["dataset:cellxgene"],
        "source_refs": ["cite:Cui2025"],
        "related": ["theme:cross-modal-representation"],
    }
    EntityValidator().validate(entity)


def test_topic_id_uppercase_rejected(base_entity: dict) -> None:
    entity = base_entity | {"id": "topic:Single-Cell"}
    with pytest.raises(EntityValidationError):
        EntityValidator().validate(entity)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/d/science/science/model && uv run pytest tests/test_entity_schema_mixin_topic.py -v`
Expected: FAIL with `SchemaNotFoundError`.

- [ ] **Step 3: Create the topic mixin schema**

Create `science/model/src/science_model/schemas/mixin-topic-1.0.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://schemas.science/mixin-topic-1.0.json",
  "title": "science entity topic mixin",
  "type": "object",
  "required": ["id", "type"],
  "properties": {
    "id": {"type": "string", "pattern": "^topic:[a-z0-9][a-z0-9-]{0,63}$"},
    "type": {"const": "topic"},
    "datasets": {
      "type": "array",
      "items": {"type": "string", "pattern": "^dataset:"}
    },
    "source_refs": {"type": "array", "items": {"type": "string"}},
    "related": {"type": "array", "items": {"type": "string"}}
  }
}
```

- [ ] **Step 4: Verify tests pass**

Run: `cd ~/d/science/science/model && uv run pytest tests/test_entity_schema_mixin_topic.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd ~/d/science/science/model
git add src/science_model/schemas/mixin-topic-1.0.json tests/test_entity_schema_mixin_topic.py
git commit -m "feat(entity_schema): topic mixin schema"
```

---

## Task 9: Theme mixin (`mixin-theme-1.0.json`)

**Files:**
- Create: `science/model/src/science_model/schemas/mixin-theme-1.0.json`
- Create: `science/model/tests/test_entity_schema_mixin_theme.py`

Mirrors current `theme.md` template, adding `theme_kind` and `theme_scope` as required.

- [ ] **Step 1: Write the failing test**

Create `science/model/tests/test_entity_schema_mixin_theme.py`:

```python
from __future__ import annotations

import pytest

from science_model.entity_schema.validator import EntityValidationError, EntityValidator


@pytest.fixture
def base_entity() -> dict:
    return {
        "schema_profile": "science-entity-base/1.0+theme/1.0",
        "id": "theme:homology-aware-evaluation",
        "type": "theme",
        "title": "Homology-aware evaluation",
        "version": "1.0.0",
        "status": "active",
        "theme_kind": "methodological",
        "theme_scope": "cross-project",
        "created": "2026-05-13",
        "updated": "2026-05-13",
    }


def test_theme_minimal_validates(base_entity: dict) -> None:
    EntityValidator().validate(base_entity)


def test_theme_rejects_missing_theme_kind(base_entity: dict) -> None:
    entity = {k: v for k, v in base_entity.items() if k != "theme_kind"}
    with pytest.raises(EntityValidationError, match="theme_kind"):
        EntityValidator().validate(entity)


def test_theme_kind_enum_enforced(base_entity: dict) -> None:
    entity = base_entity | {"theme_kind": "vibes"}
    with pytest.raises(EntityValidationError):
        EntityValidator().validate(entity)


def test_theme_scope_enum_enforced(base_entity: dict) -> None:
    entity = base_entity | {"theme_scope": "galactic"}
    with pytest.raises(EntityValidationError):
        EntityValidator().validate(entity)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/d/science/science/model && uv run pytest tests/test_entity_schema_mixin_theme.py -v`
Expected: FAIL with `SchemaNotFoundError`.

- [ ] **Step 3: Create the theme mixin schema**

Create `science/model/src/science_model/schemas/mixin-theme-1.0.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://schemas.science/mixin-theme-1.0.json",
  "title": "science entity theme mixin",
  "type": "object",
  "required": ["id", "type", "theme_kind", "theme_scope"],
  "properties": {
    "id": {"type": "string", "pattern": "^theme:[a-z0-9][a-z0-9-]{0,63}$"},
    "type": {"const": "theme"},
    "theme_kind": {
      "enum": ["methodological", "conceptual", "empirical", "domain"]
    },
    "theme_scope": {
      "enum": ["project", "cross-project"]
    },
    "source_refs": {"type": "array", "items": {"type": "string"}},
    "evidence_refs": {"type": "array", "items": {"type": "string"}},
    "related": {"type": "array", "items": {"type": "string"}}
  }
}
```

- [ ] **Step 4: Verify tests pass**

Run: `cd ~/d/science/science/model && uv run pytest tests/test_entity_schema_mixin_theme.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd ~/d/science/science/model
git add src/science_model/schemas/mixin-theme-1.0.json tests/test_entity_schema_mixin_theme.py
git commit -m "feat(entity_schema): theme mixin schema"
```

---

## Task 10: Bio extension placeholder (`extension-bio-rnaseq-1.0.json`)

**Files:**
- Create: `science/model/src/science_model/schemas/extension-bio-rnaseq-1.0.json`
- Create: `science/model/tests/test_entity_schema_extension_bio.py`

A single extension proves the composition mechanism end-to-end (base + dataset mixin + bio.rnaseq). Other bio extensions (`bio.scrna`, `bio.cna`, etc.) come in Phase H.

- [ ] **Step 1: Write the failing test**

Create `science/model/tests/test_entity_schema_extension_bio.py`:

```python
from __future__ import annotations

import pytest

from science_model.entity_schema.loader import SchemaLoader
from science_model.entity_schema.profile import ProfileComponent
from science_model.entity_schema.validator import EntityValidationError, EntityValidator


@pytest.fixture
def base_rnaseq_entity() -> dict:
    return {
        "schema_profile": "science-entity-base/1.0+dataset/1.0+bio.rnaseq/1.0",
        "id": "dataset:tcga-brca-rnaseq",
        "type": "dataset",
        "title": "TCGA-BRCA RNA-seq",
        "version": "1.0.0",
        "created": "2026-05-13",
        "updated": "2026-05-13",
        "datapackage": "datapackage.yaml",
        "origin": "external",
        "tier": "use-now",
        "access": {"level": "public", "verified": True},
        "species": "Homo sapiens",
        "assay": "bulk-rnaseq",
        "n_samples": 1080,
    }


def test_loader_resolves_extension_schema_now_that_it_exists() -> None:
    # Integration assertion for the loader's extension path (filename
    # mapping for dotted names → "extension-bio-rnaseq-1.0.json"). The
    # Task 3 loader test covered the mapping logic; this confirms the
    # real file is wired in.
    schema = SchemaLoader().load(ProfileComponent(name="bio.rnaseq", version="1.0"))
    assert schema["$id"].endswith("extension-bio-rnaseq-1.0.json")


def test_rnaseq_extension_composes_with_base_and_dataset(base_rnaseq_entity: dict) -> None:
    EntityValidator().validate(base_rnaseq_entity)


def test_rnaseq_rejects_missing_species(base_rnaseq_entity: dict) -> None:
    entity = {k: v for k, v in base_rnaseq_entity.items() if k != "species"}
    with pytest.raises(EntityValidationError, match="species"):
        EntityValidator().validate(entity)


def test_rnaseq_rejects_invalid_assay(base_rnaseq_entity: dict) -> None:
    entity = base_rnaseq_entity | {"assay": "RNA-seq"}  # uppercase rejected
    with pytest.raises(EntityValidationError):
        EntityValidator().validate(entity)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/d/science/science/model && uv run pytest tests/test_entity_schema_extension_bio.py -v`
Expected: FAIL with `SchemaNotFoundError`.

- [ ] **Step 3: Create the extension schema**

Create `science/model/src/science_model/schemas/extension-bio-rnaseq-1.0.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://schemas.science/extension-bio-rnaseq-1.0.json",
  "title": "science entity bio.rnaseq extension",
  "type": "object",
  "required": ["species", "assay"],
  "properties": {
    "species": {"type": "string", "minLength": 1},
    "assay": {"enum": ["bulk-rnaseq", "ribo-zero-rnaseq", "polya-rnaseq", "3prime-tag-rnaseq"]},
    "n_samples": {"type": "integer", "minimum": 1},
    "n_genes": {"type": "integer", "minimum": 1},
    "preprocessing_version": {"type": "string"},
    "reference_genome": {"type": "string"}
  }
}
```

- [ ] **Step 4: Verify tests pass**

Run: `cd ~/d/science/science/model && uv run pytest tests/test_entity_schema_extension_bio.py tests/test_entity_schema_loader.py -v`
Expected: PASS — the new extension tests (composition, missing-species, invalid-assay, plus the inline loader integration assertion) and the existing Task 3 loader unit tests all green.

- [ ] **Step 5: Commit**

```bash
cd ~/d/science/science/model
git add src/science_model/schemas/extension-bio-rnaseq-1.0.json tests/test_entity_schema_extension_bio.py
git commit -m "feat(entity_schema): bio.rnaseq extension placeholder"
```

---

## Task 11: Overlay schema (`overlay-1.0.json`)

**Files:**
- Create: `science/model/src/science_model/schemas/overlay-1.0.json`
- Create: `science/model/tests/test_entity_schema_overlay.py`
- Modify: `science/model/src/science_model/entity_schema/validator.py`

The overlay schema permits only ID/version-pin fields plus `merge: project_only` and `merge: append` fields per spec §5.3. Overlays use a different validator entry point because they don't carry `schema_profile`.

- [ ] **Step 1: Write the failing test**

Create `science/model/tests/test_entity_schema_overlay.py`:

```python
from __future__ import annotations

import pytest

from science_model.entity_schema.validator import (
    EntityValidationError,
    EntityValidator,
)


def test_overlay_minimal_validates() -> None:
    overlay = {
        "id": "paper:Adams2025",
        "overlay_of": "paper:Adams2025",
    }
    EntityValidator().validate_overlay(overlay)


def test_overlay_with_project_only_fields_validates() -> None:
    overlay = {
        "id": "paper:Adams2025",
        "overlay_of": "paper:Adams2025",
        "pin_version": "1.2.0",
        "relevance": "H2 — supports homology-split argument",
        "hypothesis_links": ["H2", "H4"],
        "task_links": ["t087"],
        "project_tags": ["high-priority"],
    }
    EntityValidator().validate_overlay(overlay)


def test_overlay_with_pin_effective_version_validates() -> None:
    overlay = {
        "id": "dataset:cath-domains",
        "overlay_of": "dataset:cath-domains",
        "pin_effective_version": "1.2.0+abc1234",
    }
    EntityValidator().validate_overlay(overlay)


def test_overlay_rejects_canonical_field() -> None:
    overlay = {
        "id": "paper:Adams2025",
        "overlay_of": "paper:Adams2025",
        "title": "I'm trying to override the title",  # base merge: replace — forbidden in overlay
    }
    with pytest.raises(EntityValidationError, match="title"):
        EntityValidator().validate_overlay(overlay)


def test_overlay_rejects_mismatched_overlay_of() -> None:
    overlay = {
        "id": "paper:Adams2025",
        "overlay_of": "paper:Different",
    }
    with pytest.raises(EntityValidationError, match="overlay_of"):
        EntityValidator().validate_overlay(overlay)


def test_overlay_permits_append_fields() -> None:
    # tags + ontology_terms have merge: append on the canonical schema, so
    # overlays must be allowed to add to them.
    overlay = {
        "id": "paper:Adams2025",
        "overlay_of": "paper:Adams2025",
        "tags": ["project-relevant", "discussed-in-meeting-3"],
        "ontology_terms": ["EFO:0000400"],
    }
    EntityValidator().validate_overlay(overlay)


def test_overlay_rejects_dataset_id_with_uppercase() -> None:
    # Dataset canonical IDs are lowercase-kebab. Overlay ids reference
    # canonical ids, so the same per-type slug rules apply.
    overlay = {
        "id": "dataset:NotKebab",
        "overlay_of": "dataset:NotKebab",
    }
    with pytest.raises(EntityValidationError):
        EntityValidator().validate_overlay(overlay)


def test_overlay_accepts_paper_id_with_bibkey_casing() -> None:
    # Paper bibkey IDs allow mixed case (e.g. Adams2025); the per-type
    # oneOf must accept this form.
    overlay = {
        "id": "paper:Adams2025",
        "overlay_of": "paper:Adams2025",
    }
    EntityValidator().validate_overlay(overlay)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/d/science/science/model && uv run pytest tests/test_entity_schema_overlay.py -v`
Expected: FAIL (`validate_overlay` not implemented).

- [ ] **Step 3: Create the overlay schema**

Create `science/model/src/science_model/schemas/overlay-1.0.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://schemas.science/overlay-1.0.json",
  "title": "science entity project overlay",
  "type": "object",
  "required": ["id", "overlay_of"],
  "$defs": {
    "canonicalId": {
      "type": "string",
      "oneOf": [
        {"pattern": "^dataset:[a-z0-9][a-z0-9-]{0,63}$"},
        {"pattern": "^paper:[A-Za-z][A-Za-z0-9]{1,63}$"},
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
    }
  },
  "additionalProperties": false
}
```

The `tags` and `ontology_terms` fields are carried through here so overlays can append to the canonical lists. They MUST match the canonical merge mode (`append`) — Task 12's `science:merge` annotations on the base schema confirm that. Any further append-mode fields added to canonical schemas in later phases must also appear here.

- [ ] **Step 4: Add `validate_overlay` to the validator**

Modify `science/model/src/science_model/entity_schema/validator.py` — add a method at the end of the `EntityValidator` class (before any module-level helpers):

```python
    def validate_overlay(self, overlay: dict[str, Any]) -> None:
        """Validate a project overlay (different schema than canonical entities)."""
        from science_model.entity_schema.profile import ProfileComponent

        # Overlay schema is identified by a synthetic ProfileComponent: name="overlay".
        # Filename convention is special-cased in loader._filename_for.
        schema = self._loader.load(ProfileComponent(name="overlay", version="1.0"))
        validator = Draft202012Validator(schema)
        errors = sorted(validator.iter_errors(overlay), key=lambda e: list(e.absolute_path))
        if errors:
            joined = "; ".join(_format_error(err) for err in errors)
            raise EntityValidationError(
                f"overlay failed schema validation: {joined}",
                errors=errors,
            )
        if overlay.get("id") != overlay.get("overlay_of"):
            raise EntityValidationError(
                f"overlay_of {overlay.get('overlay_of')!r} must equal id {overlay.get('id')!r}"
            )
```

- [ ] **Step 5: Special-case `overlay` in the loader**

Modify `science/model/src/science_model/entity_schema/loader.py` — update `_filename_for`:

```python
def _filename_for(component: ProfileComponent) -> str:
    if component.name == BASE_NAME:
        return f"{component.name}-{component.version}.json"
    if component.name == "overlay":
        return f"overlay-{component.version}.json"
    if component.name in TYPE_MIXIN_NAMES:
        return f"mixin-{component.name}-{component.version}.json"
    flat = component.name.replace(".", "-")
    return f"extension-{flat}-{component.version}.json"
```

- [ ] **Step 6: Verify tests pass**

Run: `cd ~/d/science/science/model && uv run pytest tests/test_entity_schema_overlay.py -v`
Expected: 8 PASS.

- [ ] **Step 7: Commit**

```bash
cd ~/d/science/science/model
git add src/science_model/schemas/overlay-1.0.json \
        src/science_model/entity_schema/validator.py \
        src/science_model/entity_schema/loader.py \
        tests/test_entity_schema_overlay.py
git commit -m "feat(entity_schema): overlay schema + validate_overlay()"
```

---

## Task 12: Merge-policy annotation reader (`merge.py`)

**Files:**
- Create: `science/model/src/science_model/entity_schema/merge.py`
- Create: `science/model/tests/test_entity_schema_merge.py`
- Modify: schema files to add `science:merge` annotations to selected fields.

Per spec §3.8, merge modes are `replace` (default), `append`, `forbidden`, `project_only`. The reader walks a composed schema and returns a flat map `{field_name: merge_mode}`.

- [ ] **Step 1: Write the failing test**

Create `science/model/tests/test_entity_schema_merge.py`:

```python
from __future__ import annotations

from science_model.entity_schema.merge import MergePolicy, read_merge_policy
from science_model.entity_schema.profile import parse_profile


def test_default_merge_mode_is_replace_for_base_title() -> None:
    policy = read_merge_policy(parse_profile("science-entity-base/1.0+paper/1.0"))
    assert policy["title"] == MergePolicy.REPLACE


def test_tags_field_is_append() -> None:
    policy = read_merge_policy(parse_profile("science-entity-base/1.0+paper/1.0"))
    assert policy["tags"] == MergePolicy.APPEND


def test_canonical_only_dataset_fields_are_forbidden() -> None:
    # Required-from-canonical fields (derivation, access, datapackage,
    # accessions) carry merge: forbidden so overlays cannot override them.
    policy = read_merge_policy(parse_profile("science-entity-base/1.0+dataset/1.0"))
    assert policy["derivation"] == MergePolicy.FORBIDDEN
    assert policy["datapackage"] == MergePolicy.FORBIDDEN


def test_overlay_specific_fields_are_project_only() -> None:
    # Project-only annotations live on the overlay schema, not mixins. The
    # reader treats overlay-permitted fields as project_only when invoked
    # via the overlay variant, EXCEPT those carrying an explicit
    # science:merge annotation (e.g. tags / ontology_terms = append).
    from science_model.entity_schema.merge import read_overlay_merge_policy
    policy = read_overlay_merge_policy()
    assert policy["hypothesis_links"] == MergePolicy.PROJECT_ONLY
    assert policy["relevance"] == MergePolicy.PROJECT_ONLY
    assert policy["tags"] == MergePolicy.APPEND
    assert policy["ontology_terms"] == MergePolicy.APPEND
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/d/science/science/model && uv run pytest tests/test_entity_schema_merge.py -v`
Expected: FAIL with import error.

- [ ] **Step 3: Implement the merge reader**

Create `science/model/src/science_model/entity_schema/merge.py`:

```python
"""Read `science:merge` annotations from composed entity schemas."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from science_model.entity_schema.loader import SchemaLoader
from science_model.entity_schema.profile import ProfileComponent, ProfileString


class MergePolicy(StrEnum):
    REPLACE = "replace"
    APPEND = "append"
    FORBIDDEN = "forbidden"
    PROJECT_ONLY = "project_only"


_ANNOTATION_KEY = "science:merge"


def read_merge_policy(profile: ProfileString, loader: SchemaLoader | None = None) -> dict[str, MergePolicy]:
    """Return field → merge policy for a composed entity schema."""
    loader = loader or SchemaLoader()
    policy: dict[str, MergePolicy] = {}
    for component in _iter_components(profile):
        schema = loader.load(component)
        for field, spec in (schema.get("properties") or {}).items():
            raw = spec.get(_ANNOTATION_KEY)
            policy[field] = MergePolicy(raw) if raw else MergePolicy.REPLACE
    return policy


def read_overlay_merge_policy(loader: SchemaLoader | None = None) -> dict[str, MergePolicy]:
    """Project-only / append fields declared on the overlay schema."""
    loader = loader or SchemaLoader()
    schema = loader.load(ProfileComponent(name="overlay", version="1.0"))
    policy: dict[str, MergePolicy] = {}
    for field, spec in (schema.get("properties") or {}).items():
        if field in {"id", "overlay_of", "pin_version", "pin_effective_version"}:
            continue
        raw = spec.get(_ANNOTATION_KEY, MergePolicy.PROJECT_ONLY.value)
        policy[field] = MergePolicy(raw)
    return policy


def _iter_components(profile: ProfileString) -> list[ProfileComponent]:
    components = [profile.base]
    if profile.mixin is not None:
        components.append(profile.mixin)
    components.extend(profile.extensions)
    return components
```

- [ ] **Step 4: Add `science:merge` annotations to selected schema fields**

Modify `science/model/src/science_model/schemas/science-entity-base-1.0.json` — add `"science:merge": "append"` to the `tags` and `ontology_terms` properties. Add `"science:merge": "forbidden"` to `version` (overlays must not override).

Modify `science/model/src/science_model/schemas/mixin-dataset-1.0.json` — add `"science:merge": "forbidden"` to `datapackage`, `derivation`, `access`, `accessions` (these are canonical-only).

Example (showing one annotated property in the base schema):

```json
    "tags": {
      "type": "array",
      "items": {"type": "string"},
      "science:merge": "append"
    },
```

Note on overlay-schema annotations: `read_overlay_merge_policy` treats every overlay-permitted field as `project_only` by default, so project-only fields (`relevance`, `hypothesis_links`, etc.) need no annotation. Append fields, however, MUST carry an explicit `"science:merge": "append"` annotation — Task 11 already added these for `tags` and `ontology_terms` in `overlay-1.0.json`, and the test below relies on them being present.

- [ ] **Step 5: Verify tests pass**

Run: `cd ~/d/science/science/model && uv run pytest tests/test_entity_schema_merge.py -v`
Expected: 4 PASS (the fourth asserts overlay-specific PROJECT_ONLY defaults *and* explicit APPEND on tags / ontology_terms).

- [ ] **Step 6: Commit**

```bash
cd ~/d/science/science/model
git add src/science_model/entity_schema/merge.py \
        src/science_model/schemas/science-entity-base-1.0.json \
        src/science_model/schemas/mixin-dataset-1.0.json \
        tests/test_entity_schema_merge.py
git commit -m "feat(entity_schema): science:merge annotation reader"
```

---

## Task 13: Pydantic wrapper (`wrapper.py`)

**Files:**
- Create: `science/model/src/science_model/entity_schema/wrapper.py`
- Create: `science/model/tests/test_entity_schema_wrapper.py`

A thin ergonomic Pydantic model for in-code access. JSON Schema is authoritative; the wrapper just makes Python access pleasant. Not exhaustive — only fields a typical consumer reads. Unknown fields land in `extra`.

- [ ] **Step 1: Write the failing test**

Create `science/model/tests/test_entity_schema_wrapper.py`:

```python
from __future__ import annotations

import pytest

from science_model.entity_schema.wrapper import SharedEntity


def test_wrapper_loads_paper_entity() -> None:
    raw = {
        "schema_profile": "science-entity-base/1.0+paper/1.0",
        "id": "paper:Adams2025",
        "type": "paper",
        "title": "An example",
        "version": "1.0.0",
        "created": "2026-05-13",
        "updated": "2026-05-13",
        "bibkey": "Adams2025",
        "year": 2025,
        "datasets": ["dataset:cath-domains"],
    }
    entity = SharedEntity.model_validate(raw)
    assert entity.id == "paper:Adams2025"
    assert entity.type == "paper"
    assert entity.version == "1.0.0"
    assert entity.extra.get("bibkey") == "Adams2025"
    assert entity.extra.get("datasets") == ["dataset:cath-domains"]


def test_wrapper_validates_with_validator() -> None:
    # The wrapper does NOT replace the JSON Schema validator; it's a convenience layer.
    raw = {
        "schema_profile": "science-entity-base/1.0+paper/1.0",
        "id": "paper:Adams2025",
        "type": "paper",
        "title": "An example",
        "version": "1.0.0",
        "created": "2026-05-13",
        "updated": "2026-05-13",
    }
    entity = SharedEntity.model_validate(raw)
    entity.validate_schema()  # delegates to EntityValidator under the hood


def test_wrapper_raises_on_schema_violation() -> None:
    raw = {
        "schema_profile": "science-entity-base/1.0+paper/1.0",
        "id": "paper:Adams2025",
        "type": "paper",
        "title": "An example",
        "version": "1.0.0",
        # missing required: created, updated
    }
    entity = SharedEntity.model_validate(raw)
    with pytest.raises(Exception, match="created"):
        entity.validate_schema()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/d/science/science/model && uv run pytest tests/test_entity_schema_wrapper.py -v`
Expected: FAIL with import error.

- [ ] **Step 3: Implement the wrapper**

Create `science/model/src/science_model/entity_schema/wrapper.py`:

```python
"""Pydantic ergonomic wrapper around composed entity schemas.

JSON Schema is the source of truth — this wrapper exists only for nice
in-code field access. Unknown fields land in `extra: dict[str, Any]`.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from science_model.entity_schema.validator import EntityValidator


class SharedEntity(BaseModel):
    """Frontmatter projection of a shared canonical entity."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    schema_profile: str
    id: str
    type: str
    title: str
    version: str
    created: date | None = None
    updated: date | None = None
    description: str = ""
    sources: list[str] = Field(default_factory=list)
    licenses: list[Any] = Field(default_factory=list)
    contributors: list[dict[str, Any]] = Field(default_factory=list)
    ontology_terms: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    status: str = ""

    # Everything not declared above lands here at validation time.
    extra: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _capture_extras(cls, values: Any) -> Any:
        if not isinstance(values, dict):
            return values
        declared = set(cls.model_fields.keys()) - {"extra"}
        extra = {k: v for k, v in values.items() if k not in declared}
        # Keep declared fields in the top-level mapping; copy extras into 'extra'.
        out = {k: v for k, v in values.items() if k in declared}
        out["extra"] = extra
        return out

    def validate_schema(self, validator: EntityValidator | None = None) -> None:
        """Run JSON Schema validation against this entity's `schema_profile`."""
        validator = validator or EntityValidator()
        # Flatten the wrapper back into a plain dict for the validator.
        payload: dict[str, Any] = self.model_dump(mode="json", exclude={"extra"})
        payload.update(self.extra)
        validator.validate(payload)
```

- [ ] **Step 4: Verify tests pass**

Run: `cd ~/d/science/science/model && uv run pytest tests/test_entity_schema_wrapper.py -v`
Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
cd ~/d/science/science/model
git add src/science_model/entity_schema/wrapper.py tests/test_entity_schema_wrapper.py
git commit -m "feat(entity_schema): Pydantic ergonomic wrapper"
```

---

## Task 14: Real-fixture validation suite

**Files:**
- Create: `science/model/tests/fixtures/entity_schema/README.md`
- Create: `science/model/tests/fixtures/entity_schema/paper_Adams2025.md`
- Create: `science/model/tests/fixtures/entity_schema/topic_single-cell-foundation-models.md`
- Create: `science/model/tests/fixtures/entity_schema/theme_homology-aware-evaluation.md`
- Create: `science/model/tests/fixtures/entity_schema/dataset_cath-domains/entity.md`
- Create: `science/model/tests/fixtures/entity_schema/dataset_cath-domains/datapackage.yaml`
- Create: `science/model/tests/test_entity_schema_fixtures.py`

Fixtures are synthetic-but-realistic entities matching the new shared-store conventions. They prove the schemas work on entity-shaped content end-to-end.

- [ ] **Step 1: Write the fixtures**

Create `science/model/tests/fixtures/entity_schema/README.md`:

```markdown
# entity_schema fixtures

Synthetic shared-store-style entities for validating the JSON Schema +
validator layer. Each fixture exercises a different mixin/extension.

| File | Profile |
| --- | --- |
| `paper_Adams2025.md` | `science-entity-base/1.0+paper/1.0` |
| `topic_single-cell-foundation-models.md` | `science-entity-base/1.0+topic/1.0` |
| `theme_homology-aware-evaluation.md` | `science-entity-base/1.0+theme/1.0` |
| `dataset_cath-domains/entity.md` | `science-entity-base/1.0+dataset/1.0` |
| `dataset_cath-domains/datapackage.yaml` | (Frictionless sidecar) |

These are NOT production entities. They are crafted for schema coverage.
```

Create `science/model/tests/fixtures/entity_schema/paper_Adams2025.md`:

```markdown
---
schema_profile: "science-entity-base/1.0+paper/1.0"
id: "paper:Adams2025"
type: "paper"
title: "A representative paper about homology-aware evaluation"
version: "1.0.0"
status: "active"
created: "2026-05-13"
updated: "2026-05-13"
sources:
  - "doi:10.1038/example"
  - "cite:Adams2025"
ontology_terms: []
tags: []
bibkey: "Adams2025"
authors: ["Adams, A.", "Baker, B."]
year: 2025
journal: "Nature Methods"
doi: "10.1038/example"
url: "https://example.org/Adams2025"
datasets: ["dataset:cath-domains"]
key_findings:
  - "Random splits inflate accuracy on CATH-derived test sets."
  - "Homology-aware splits recover a more realistic estimate."
limitations:
  - "Only one homology metric evaluated."
---

# Body content (not schema-relevant for Phase A)
```

Create `science/model/tests/fixtures/entity_schema/topic_single-cell-foundation-models.md`:

```markdown
---
schema_profile: "science-entity-base/1.0+topic/1.0"
id: "topic:single-cell-foundation-models"
type: "topic"
title: "Single-cell foundation models"
version: "1.0.0"
status: "active"
created: "2026-05-13"
updated: "2026-05-13"
ontology_terms: []
datasets: ["dataset:cath-domains"]
source_refs:
  - "cite:Adams2025"
related: ["theme:homology-aware-evaluation"]
---
```

Create `science/model/tests/fixtures/entity_schema/theme_homology-aware-evaluation.md`:

```markdown
---
schema_profile: "science-entity-base/1.0+theme/1.0"
id: "theme:homology-aware-evaluation"
type: "theme"
title: "Homology-aware evaluation"
version: "1.0.0"
status: "active"
theme_kind: "methodological"
theme_scope: "cross-project"
created: "2026-05-13"
updated: "2026-05-13"
related: ["topic:single-cell-foundation-models"]
source_refs:
  - "cite:Adams2025"
---
```

Create `science/model/tests/fixtures/entity_schema/dataset_cath-domains/entity.md`:

```markdown
---
schema_profile: "science-entity-base/1.0+dataset/1.0"
id: "dataset:cath-domains"
type: "dataset"
title: "CATH domain database"
version: "1.0.0"
status: "active"
created: "2026-05-13"
updated: "2026-05-13"
datapackage: "datapackage.yaml"
origin: "external"
tier: "use-now"
access:
  level: "public"
  verified: true
  source_url: "https://www.cathdb.info/"
accessions: ["CATH:v4_3_0"]
ontology_terms: []
---
```

Create `science/model/tests/fixtures/entity_schema/dataset_cath-domains/datapackage.yaml`:

```yaml
name: cath-domains
profile: "data-package"
resources:
  - name: cath_domains
    path: cath_domains.parquet
    hash: "sha256:0000000000000000000000000000000000000000000000000000000000000000"
    bytes: 4521339201
    format: "parquet"
```

- [ ] **Step 2: Write the integration test**

Create `science/model/tests/test_entity_schema_fixtures.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from science_model.entity_schema.validator import EntityValidator

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "entity_schema"


def _read_frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), f"{path}: no frontmatter"
    _, raw, *_ = text.split("---\n", 2)
    return yaml.safe_load(raw)


@pytest.mark.parametrize(
    "relpath",
    [
        "paper_Adams2025.md",
        "topic_single-cell-foundation-models.md",
        "theme_homology-aware-evaluation.md",
        "dataset_cath-domains/entity.md",
    ],
)
def test_fixture_validates(relpath: str) -> None:
    entity = _read_frontmatter(FIXTURE_DIR / relpath)
    EntityValidator().validate(entity)


def test_dataset_fixture_datapackage_parses() -> None:
    text = (FIXTURE_DIR / "dataset_cath-domains" / "datapackage.yaml").read_text(encoding="utf-8")
    dp = yaml.safe_load(text)
    assert dp["name"] == "cath-domains"
    assert len(dp["resources"]) == 1
    assert dp["resources"][0]["hash"].startswith("sha256:")
    assert dp["resources"][0]["bytes"] > 0
```

- [ ] **Step 3: Run tests to verify they pass**

Run: `cd ~/d/science/science/model && uv run pytest tests/test_entity_schema_fixtures.py -v`
Expected: 5 PASS (4 parametrized fixtures + 1 datapackage test).

- [ ] **Step 4: Commit**

```bash
cd ~/d/science/science/model
git add tests/fixtures/entity_schema/ tests/test_entity_schema_fixtures.py
git commit -m "test(entity_schema): real-fixture validation suite"
```

---

## Task 15: Public API surface

**Files:**
- Modify: `science/model/src/science_model/entity_schema/__init__.py`
- Modify: `science/model/src/science_model/__init__.py`
- Create: `science/model/tests/test_entity_schema_public_api.py`

Expose the validated public surface so consumers (Phase B and beyond) have a single import path.

- [ ] **Step 1: Write the failing test**

Create `science/model/tests/test_entity_schema_public_api.py`:

```python
from __future__ import annotations


def test_public_api_exports() -> None:
    from science_model.entity_schema import (
        EntityValidator,
        EntityValidationError,
        MergePolicy,
        ProfileString,
        SharedEntity,
        parse_profile,
        read_merge_policy,
        read_overlay_merge_policy,
    )

    assert EntityValidator is not None
    assert EntityValidationError is not None
    assert MergePolicy.REPLACE.value == "replace"
    assert callable(parse_profile)
    assert callable(read_merge_policy)
    assert callable(read_overlay_merge_policy)
    assert ProfileString is not None
    assert SharedEntity is not None


def test_top_level_export() -> None:
    import science_model

    assert hasattr(science_model, "EntityValidator")
    assert hasattr(science_model, "SharedEntity")


def test_top_level_all_contains_entity_schema_exports() -> None:
    import science_model

    for name in ("EntityValidator", "EntityValidationError", "MergePolicy", "SharedEntity"):
        assert name in science_model.__all__, f"{name!r} missing from science_model.__all__"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/d/science/science/model && uv run pytest tests/test_entity_schema_public_api.py -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Wire up the public API**

Modify `science/model/src/science_model/entity_schema/__init__.py` (replace the contents):

```python
"""Multi-project entity schema layer.

Composes a Frictionless-inspired base schema with type mixins (dataset,
paper, topic, theme) and optional domain extensions (e.g. bio.rnaseq).

See docs/plans/2026-05-13-multiproject-schema-and-shared-store-design.md
section 3 for the design.
"""

from __future__ import annotations

from science_model.entity_schema.merge import (
    MergePolicy,
    read_merge_policy,
    read_overlay_merge_policy,
)
from science_model.entity_schema.profile import (
    BASE_NAME,
    TYPE_MIXIN_NAMES,
    ProfileComponent,
    ProfileParseError,
    ProfileString,
    parse_profile,
)
from science_model.entity_schema.loader import (
    SchemaLoader,
    SchemaNotFoundError,
)
from science_model.entity_schema.validator import (
    EntityValidationError,
    EntityValidator,
)
from science_model.entity_schema.wrapper import SharedEntity

__all__ = [
    "BASE_NAME",
    "TYPE_MIXIN_NAMES",
    "EntityValidationError",
    "EntityValidator",
    "MergePolicy",
    "ProfileComponent",
    "ProfileParseError",
    "ProfileString",
    "SchemaLoader",
    "SchemaNotFoundError",
    "SharedEntity",
    "parse_profile",
    "read_merge_policy",
    "read_overlay_merge_policy",
]
```

- [ ] **Step 4: Re-export the most-used names from the top-level package**

Modify `science/model/src/science_model/__init__.py`:

1. Add after the existing imports (e.g. alongside the other re-exports):

```python
from science_model.entity_schema import (
    EntityValidationError,
    EntityValidator,
    MergePolicy,
    SharedEntity,
)
```

2. Add the four names to the existing `__all__` list (the package keeps an explicit `__all__`; new top-level exports must appear there). Insert them alphabetically:

```python
__all__ = [
    # ... existing entries ...
    "EntityValidationError",
    "EntityValidator",
    "MergePolicy",
    "SharedEntity",
    # ... existing entries ...
]
```

Verify by grepping the file: `grep -n '"EntityValidator"' src/science_model/__init__.py` should return a hit, and the names should not be duplicated elsewhere in the list.

- [ ] **Step 5: Verify tests pass**

Run: `cd ~/d/science/science/model && uv run pytest tests/test_entity_schema_public_api.py -v`
Expected: 3 PASS.

- [ ] **Step 6: Run the entire entity_schema suite to confirm no regressions**

Run: `cd ~/d/science/science/model && uv run pytest tests/test_entity_schema_*.py -v`
Expected: ALL tests for tasks 1–15 PASS.

- [ ] **Step 7: Commit**

```bash
cd ~/d/science/science/model
git add src/science_model/entity_schema/__init__.py \
        src/science_model/__init__.py \
        tests/test_entity_schema_public_api.py
git commit -m "feat(entity_schema): wire up public API"
```

---

## Phase A complete

All schema-layer pieces are now in place. Phase B (shared store scaffolding) can begin:

- `SharedEntityAdapter` (composes `entity.md` + `datapackage.yaml`)
- `~/d/science-shared/` directory creation + `.git/` init
- `registry.sqlite` builder + `science index rebuild`
- CLI: `science show`, `science find`, `science validate`

Run the full test suite once more before handing off:

```bash
cd ~/d/science/science/model && uv run pytest -v
```

Then push the commits and the next phase's writing-plans cycle can start.

# Generic Reference-Collection Substrate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land the C/D-agnostic substrate — `derivation.kind: member_of` as a core dataset-mixin variant, virtual-member resolution that delegates to the parent collection, and a reference-collection validation check (parent-collection resolution + declared key-status semantics) — so Pillars C (assembly registry) and D (gene sets) consume one mechanism instead of two look-alikes.

**Architecture:** Two layers, no bio and no network. (1) **science-model**: an additive, backward-compatible discriminated-union change to the dataset mixin's `derivation` schema. (2) **science-tool**: a pure parser for the `member_of` derivation, a resolver that maps a promoted member to `(parent collection, member_key)` via the existing commons adapter, a reusable key-resolution evaluator (`resolved | unresolved | declared_unresolved | unknown`), and a `science validate` check that enforces **parent-collection resolution** (structural — always required) plus **declared key-status semantics**. Implements §RCM-D1/D2/D5 of `docs/plans/2026-05-26-reference-collection-member-promotion-design.md`. **Verifying that a member key is actually present in its collection's rows** needs instance-specific collection metadata (a key index) and is **out of scope** — it belongs to Plan 2 / the consuming instance, alongside row-level byte slicing.

**Tech Stack:** Python 3.11, `jsonschema` Draft 2020-12, `pytest`, `uv` (`uv run --frozen`), the `science-model` and `science` (`science_tool`) packages. All paths are relative to the repo root `~/d/science`.

---

## Background the implementer must read first

- `docs/plans/2026-05-26-reference-collection-member-promotion-design.md` — the primitive. RCM-D5 defines `derivation.kind: member_of` (`parent_dataset` + `member_key`) and the virtual-member rule; RCM-D2 defines resolve-or-`declared_unresolved` (guardrail 1).
- `science/model/src/science_model/schemas/mixin-dataset-1.0.json` — the schema you will change. Today `$defs.derivation` requires `workflow_recipe` + `inputs`; the top-level `allOf` requires `derivation` when `origin: derived`.
- `science/model/tests/test_entity_schema_mixin_dataset.py` — the test conventions to mirror (a `base_entity` fixture; `EntityValidator().validate(entity)` for the happy path; `pytest.raises(EntityValidationError)` for rejects).
- `science/src/science_tool/commons/resolver.py` — `resolve(dataset_id, logical_path)` and `CommonsEntityAdapter(commons_root).load(dataset_id)` returning a record with `.slug`, `.datapackage_path`, `.body_path`. The member resolver reuses this adapter.
- `science/src/science_tool/validate/checks/code_files.py` — the canonical check idiom: `load_project_sources(ctx.project_root, include_commons=False)`, iterate `sources.entities`, read fields with `getattr(entity, "<field>", default)`, use `entity.canonical_id` and `entity.file_path`, register via the `@Check(section=..., order=...)` decorator, and add the module name to `_load_canonical_checks()` in `validate/checks/__init__.py`.

**Backward-compatibility invariant (verify it holds after Task 1):** every existing `origin: derived` dataset has a `derivation` with `workflow_recipe` + `inputs` and **no** `kind` field. The new schema must keep those valid. This is why the change is additive (a `oneOf` whose first branch matches a `kind`-less workflow derivation) and stays at `mixin-dataset-1.0.json` rather than bumping the version (a version bump would ripple into `default_profile_for_kind`, `commons/promote.py:203`, and every dataset `schema_profile` string for no behavioural gain).

---

## File Structure

| File | Create/Modify | Responsibility |
|---|---|---|
| `science/model/src/science_model/schemas/mixin-dataset-1.0.json` | Modify | `$defs.derivation` becomes a `oneOf` discriminated on `kind` (`workflow` \| `member_of`), additive. |
| `science/model/tests/test_entity_schema_mixin_dataset.py` | Modify | Schema tests: member_of validates; backward-compat workflow derivation still validates; malformed member_of rejected. |
| `science/src/science_tool/commons/member.py` | Create | Pure `MemberOf` parse + `resolve_member()` (delegates to parent via `CommonsEntityAdapter`) + `evaluate_key_resolution()` (the reusable resolved/declared_unresolved evaluator). |
| `science/tests/test_commons_member.py` | Create | Unit tests for parse / resolve / evaluate, using a tiny in-repo commons fixture. |
| `science/tests/fixtures/commons/refcoll/` | Create | Minimal commons fixture: a parent collection dataset + a promoted member dataset + a member with a missing parent. |
| `science/src/science_tool/validate/checks/reference_collections.py` | Create | The `science validate` check enforcing the member-of resolution contract. |
| `science/src/science_tool/validate/checks/__init__.py` | Modify | Register `reference_collections` in `_load_canonical_checks()`. |
| `science/tests/validate/test_checks_reference_collections.py` | Create | Check tests: resolved member passes; missing parent → ERROR; `declared_unresolved` → INFO pass; non-member datasets ignored. |

---

## Task 1: `member_of` derivation variant in the dataset mixin

**Files:**
- Modify: `science/model/src/science_model/schemas/mixin-dataset-1.0.json` (the `$defs.derivation` block, lines 53–61)
- Test: `science/model/tests/test_entity_schema_mixin_dataset.py`

- [ ] **Step 1: Write the failing tests**

Add to `science/model/tests/test_entity_schema_mixin_dataset.py`:

```python
def test_dataset_member_of_derivation_validates(base_entity: dict) -> None:
    entity = base_entity | {
        "origin": "derived",
        "parent_dataset": "dataset:reactome-v89",
        "derivation": {
            "kind": "member_of",
            "parent_dataset": "dataset:reactome-v89",
            "member_key": "R-HSA-12345",
        },
    }
    EntityValidator().validate(entity)


def test_dataset_workflow_derivation_without_kind_still_validates(base_entity: dict) -> None:
    # Backward-compatibility: existing derived datasets carry no `kind`.
    entity = base_entity | {
        "origin": "derived",
        "derivation": {
            "workflow_recipe": "recipe/Snakefile",
            "recipe_lockfile": "recipe/lockfile.yaml",
            "inputs": ["dataset:upstream"],
        },
    }
    EntityValidator().validate(entity)


def test_dataset_member_of_missing_member_key_rejected(base_entity: dict) -> None:
    entity = base_entity | {
        "origin": "derived",
        "derivation": {"kind": "member_of", "parent_dataset": "dataset:reactome-v89"},
    }
    with pytest.raises(EntityValidationError):
        EntityValidator().validate(entity)


def test_dataset_member_of_with_workflow_fields_rejected(base_entity: dict) -> None:
    # member_of must not also carry workflow fields (RCM-D5: a member has no workflow).
    entity = base_entity | {
        "origin": "derived",
        "derivation": {
            "kind": "member_of",
            "parent_dataset": "dataset:reactome-v89",
            "member_key": "R-HSA-12345",
            "workflow_recipe": "recipe/Snakefile",
            "inputs": ["dataset:upstream"],
        },
    }
    with pytest.raises(EntityValidationError):
        EntityValidator().validate(entity)


def test_dataset_member_of_with_recipe_lockfile_rejected(base_entity: dict) -> None:
    # recipe_lockfile is a workflow field; a member_of has no workflow (RCM-D5).
    entity = base_entity | {
        "origin": "derived",
        "derivation": {
            "kind": "member_of",
            "parent_dataset": "dataset:reactome-v89",
            "member_key": "R-HSA-12345",
            "recipe_lockfile": "recipe/lockfile.yaml",
        },
    }
    with pytest.raises(EntityValidationError):
        EntityValidator().validate(entity)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd ~/d/science/science/model && uv run --frozen pytest tests/test_entity_schema_mixin_dataset.py -v`
Expected: the five new tests FAIL — `test_dataset_member_of_derivation_validates` raises `EntityValidationError` (member_of has no `workflow_recipe`/`inputs` so it violates the current single-shape `derivation`), and the three reject tests FAIL because nothing yet forbids the malformed shapes. The pre-existing tests still PASS.

- [ ] **Step 3: Implement the schema change**

In `science/model/src/science_model/schemas/mixin-dataset-1.0.json`, replace the `$defs.derivation` object (currently lines 53–61) with a discriminated `oneOf`:

```json
    "derivation": {
      "type": "object",
      "oneOf": [
        {
          "title": "workflow derivation",
          "properties": {
            "kind": {"const": "workflow"},
            "workflow_recipe": {"type": "string"},
            "recipe_lockfile": {"type": "string"},
            "inputs": {"type": "array", "items": {"type": "string", "pattern": "^dataset:"}}
          },
          "required": ["workflow_recipe", "inputs"],
          "not": {"anyOf": [{"required": ["parent_dataset"]}, {"required": ["member_key"]}]}
        },
        {
          "title": "member_of derivation",
          "properties": {
            "kind": {"const": "member_of"},
            "parent_dataset": {"type": "string", "pattern": "^dataset:"},
            "member_key": {"type": "string", "minLength": 1}
          },
          "required": ["kind", "parent_dataset", "member_key"],
          "not": {"anyOf": [{"required": ["workflow_recipe"]}, {"required": ["inputs"]}, {"required": ["recipe_lockfile"]}]}
        }
      ]
    }
```

Why this satisfies every case:
- A `kind`-less `{workflow_recipe, inputs}` matches branch 1 (the `kind` `const` does not apply when `kind` is absent) and fails branch 2 (which `required`s `kind`) → exactly one match (backward compatible).
- A `{kind: member_of, parent_dataset, member_key}` fails branch 1 (`kind` ≠ `workflow`) and matches branch 2 → one match.
- A member_of missing `member_key`, or carrying `workflow_recipe`/`inputs`, matches neither branch → invalid.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd ~/d/science/science/model && uv run --frozen pytest tests/test_entity_schema_mixin_dataset.py -v`
Expected: all tests PASS (the four new ones plus the pre-existing ones).

- [ ] **Step 5: Run the full model schema suite to confirm no regression**

Run: `cd ~/d/science/science/model && uv run --frozen pytest -q`
Expected: PASS. (Confirms no existing dataset fixture/entity broke under the additive `oneOf`.)

- [ ] **Step 6: Commit**

```bash
cd ~/d/science
git add science/model/src/science_model/schemas/mixin-dataset-1.0.json science/model/tests/test_entity_schema_mixin_dataset.py
git commit -m "feat(dataset): add member_of derivation variant (RCM-D5, additive)"
```

---

## Task 2: `MemberOf` parser + `evaluate_key_resolution` evaluator

**Files:**
- Create: `science/src/science_tool/commons/member.py`
- Test: `science/tests/test_commons_member.py`

- [ ] **Step 1: Write the failing tests**

Create `science/tests/test_commons_member.py`:

```python
from __future__ import annotations

import pytest

from science_tool.commons.member import (
    MemberOf,
    ResolutionState,
    evaluate_key_resolution,
    parse_member_of,
)


def test_parse_member_of_extracts_parent_and_key() -> None:
    entity = {
        "origin": "derived",
        "derivation": {
            "kind": "member_of",
            "parent_dataset": "dataset:reactome-v89",
            "member_key": "R-HSA-12345",
        },
    }
    assert parse_member_of(entity) == MemberOf(
        parent_dataset="dataset:reactome-v89", member_key="R-HSA-12345"
    )


def test_parse_member_of_returns_none_for_workflow_derivation() -> None:
    entity = {"origin": "derived", "derivation": {"workflow_recipe": "r", "inputs": []}}
    assert parse_member_of(entity) is None


def test_parse_member_of_returns_none_when_no_derivation() -> None:
    assert parse_member_of({"origin": "external"}) is None


def test_evaluate_key_resolution_resolved_when_key_present() -> None:
    state = evaluate_key_resolution(
        key="R-HSA-12345", available_keys={"R-HSA-12345", "R-HSA-2"}, declared_status=None
    )
    assert state is ResolutionState.RESOLVED


def test_evaluate_key_resolution_unresolved_when_key_absent() -> None:
    state = evaluate_key_resolution(
        key="R-HSA-999", available_keys={"R-HSA-1"}, declared_status=None
    )
    assert state is ResolutionState.UNRESOLVED


def test_evaluate_key_resolution_declared_unresolved_is_first_class() -> None:
    # An explicit declared_unresolved is honoured even with no key index available.
    state = evaluate_key_resolution(
        key="X", available_keys=None, declared_status="declared_unresolved"
    )
    assert state is ResolutionState.DECLARED_UNRESOLVED


def test_evaluate_key_resolution_unknown_when_no_index_and_no_declaration() -> None:
    # No key index to check against and no explicit declaration: the contract is
    # unverifiable here, reported as UNKNOWN (the check decides severity).
    state = evaluate_key_resolution(key="X", available_keys=None, declared_status=None)
    assert state is ResolutionState.UNKNOWN


def test_evaluate_key_resolution_rejects_unknown_declared_status() -> None:
    with pytest.raises(ValueError, match="resolution_status"):
        evaluate_key_resolution(key="X", available_keys=None, declared_status="bogus")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_commons_member.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'science_tool.commons.member'`.

- [ ] **Step 3: Implement the parser + evaluator**

Create `science/src/science_tool/commons/member.py`:

```python
"""Reference-collection member primitives (RCM-D2/D5).

Pure helpers shared by every reference-collection instance (assembly registry,
gene-set collection, crosswalks). No network, no bio. See
docs/plans/2026-05-26-reference-collection-member-promotion-design.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

_VALID_DECLARED_STATUS = frozenset({"resolved", "declared_unresolved"})


@dataclass(frozen=True, slots=True)
class MemberOf:
    """The parsed `derivation.kind: member_of` block (RCM-D5)."""

    parent_dataset: str
    member_key: str


class ResolutionState(str, Enum):
    """Outcome of evaluating a keyed reference against its collection (RCM-D2)."""

    RESOLVED = "resolved"
    UNRESOLVED = "unresolved"
    DECLARED_UNRESOLVED = "declared_unresolved"
    UNKNOWN = "unknown"


def parse_member_of(entity: dict[str, Any]) -> MemberOf | None:
    """Return the MemberOf block if `entity` is a promoted member, else None.

    Trusts schema validation for shape; this only extracts. Returns None for a
    workflow derivation, a missing derivation, or a derivation whose `kind` is
    not `member_of`.
    """
    derivation = entity.get("derivation")
    if not isinstance(derivation, dict) or derivation.get("kind") != "member_of":
        return None
    return MemberOf(
        parent_dataset=derivation["parent_dataset"],
        member_key=derivation["member_key"],
    )


def evaluate_key_resolution(
    *,
    key: str,
    available_keys: set[str] | None,
    declared_status: str | None,
) -> ResolutionState:
    """Evaluate a keyed reference against its collection (guardrail 1, RCM-D2).

    - `declared_status == "declared_unresolved"` → DECLARED_UNRESOLVED (a
      first-class, honoured state; never an error).
    - else if `available_keys` is known → RESOLVED iff `key` is present, else
      UNRESOLVED.
    - else (no index, no declaration) → UNKNOWN; the caller decides severity.

    `declared_status` must be one of {"resolved", "declared_unresolved"} or None.
    """
    if declared_status is not None and declared_status not in _VALID_DECLARED_STATUS:
        raise ValueError(
            f"resolution_status must be one of {sorted(_VALID_DECLARED_STATUS)} or absent; "
            f"got {declared_status!r}"
        )
    if declared_status == "declared_unresolved":
        return ResolutionState.DECLARED_UNRESOLVED
    if available_keys is not None:
        return ResolutionState.RESOLVED if key in available_keys else ResolutionState.UNRESOLVED
    return ResolutionState.UNKNOWN
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_commons_member.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
cd ~/d/science
git add science/src/science_tool/commons/member.py science/tests/test_commons_member.py
git commit -m "feat(commons): member_of parser + key-resolution evaluator (RCM-D2)"
```

---

## Task 3: `resolve_member` — virtual-member resolution delegating to the parent

**Files:**
- Modify: `science/src/science_tool/commons/member.py`
- Create: `science/tests/fixtures/commons/refcoll/` (commons fixture)
- Test: `science/tests/test_commons_member.py`

A promoted member is a **virtual derived dataset** (RCM-D5): it has no bytes of its own. `resolve_member` loads the member entity, parses its `member_of`, confirms the parent collection exists in the commons, and returns the parent record plus the `member_key`. Byte-level slicing of the parent on the key is the consumer's responsibility and is **not** implemented here.

- [ ] **Step 1: Create the commons fixture**

Create three files mirroring `science/tests/fixtures/commons/valid/datasets/cath-domains/` (a dataset = an `entity.md` + a `datapackage.yaml`).

`science/tests/fixtures/commons/refcoll/datasets/parent-collection/entity.md`:

```markdown
---
schema_profile: "science-entity-base/1.0+dataset/1.0"
id: "dataset:parent-collection"
type: "dataset"
title: "Parent reference collection"
version: "1.0.0"
status: "active"
created: "2026-05-26"
updated: "2026-05-26"
datapackage: "datapackage.yaml"
origin: "external"
tier: "use-now"
access:
  level: "public"
  verified: true
  source_url: "https://example.org/collection"
---

# Parent reference collection

A reference collection whose members are addressed by key.
```

`science/tests/fixtures/commons/refcoll/datasets/parent-collection/datapackage.yaml`:

```yaml
name: parent-collection
profile: "data-package"
resources:
  - name: members
    path: members.parquet
    hash: "sha256:0000000000000000000000000000000000000000000000000000000000000000"
    bytes: 1024
    format: "parquet"
    mediatype: "application/vnd.apache.parquet"
```

`science/tests/fixtures/commons/refcoll/datasets/promoted-member/entity.md`:

```markdown
---
schema_profile: "science-entity-base/1.0+dataset/1.0"
id: "dataset:promoted-member"
type: "dataset"
title: "Promoted member m-1"
version: "1.0.0"
status: "active"
created: "2026-05-26"
updated: "2026-05-26"
datapackage: "datapackage.yaml"
origin: "derived"
tier: "use-now"
parent_dataset: "dataset:parent-collection"
derivation:
  kind: member_of
  parent_dataset: "dataset:parent-collection"
  member_key: "m-1"
---

# Promoted member m-1

A virtual member of dataset:parent-collection.
```

`science/tests/fixtures/commons/refcoll/datasets/promoted-member/datapackage.yaml`:

```yaml
name: promoted-member
profile: "data-package"
resources:
  - name: member
    path: member.parquet
    hash: "sha256:0000000000000000000000000000000000000000000000000000000000000000"
    bytes: 64
    format: "parquet"
    mediatype: "application/vnd.apache.parquet"
```

`science/tests/fixtures/commons/refcoll/datasets/orphan-member/entity.md` (parent does not exist):

```markdown
---
schema_profile: "science-entity-base/1.0+dataset/1.0"
id: "dataset:orphan-member"
type: "dataset"
title: "Orphan member"
version: "1.0.0"
status: "active"
created: "2026-05-26"
updated: "2026-05-26"
datapackage: "datapackage.yaml"
origin: "derived"
tier: "use-now"
parent_dataset: "dataset:does-not-exist"
derivation:
  kind: member_of
  parent_dataset: "dataset:does-not-exist"
  member_key: "x-9"
---

# Orphan member

A member whose parent collection is not in the commons.
```

`science/tests/fixtures/commons/refcoll/datasets/orphan-member/datapackage.yaml`:

```yaml
name: orphan-member
profile: "data-package"
resources:
  - name: member
    path: member.parquet
    hash: "sha256:0000000000000000000000000000000000000000000000000000000000000000"
    bytes: 64
    format: "parquet"
    mediatype: "application/vnd.apache.parquet"
```

- [ ] **Step 2: Write the failing tests**

Append to `science/tests/test_commons_member.py`:

```python
from pathlib import Path

from science_tool.commons.member import ResolvedMember, resolve_member

_COMMONS = Path(__file__).parent / "fixtures" / "commons" / "refcoll"


def test_resolve_member_returns_parent_and_key() -> None:
    resolved = resolve_member("dataset:promoted-member", commons_root=_COMMONS)
    assert isinstance(resolved, ResolvedMember)
    assert resolved.member_key == "m-1"
    assert resolved.parent_dataset == "dataset:parent-collection"
    assert resolved.parent_slug == "parent-collection"


def test_resolve_member_none_for_non_member() -> None:
    assert resolve_member("dataset:parent-collection", commons_root=_COMMONS) is None


def test_resolve_member_raises_when_parent_missing() -> None:
    import pytest

    from science_tool.commons.errors import CommonsError

    with pytest.raises(CommonsError):
        resolve_member("dataset:orphan-member", commons_root=_COMMONS)
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_commons_member.py -k resolve_member -v`
Expected: FAIL with `ImportError: cannot import name 'ResolvedMember'` / `resolve_member`.

- [ ] **Step 4: Implement `resolve_member`**

Append to `science/src/science_tool/commons/member.py` (add the imports at the top of the file):

```python
from pathlib import Path

from science_tool.commons.adapter import CommonsEntityAdapter
from science_tool.commons.config import resolve_commons_root
```

```python
@dataclass(frozen=True, slots=True)
class ResolvedMember:
    """A promoted member resolved to its parent collection + key (RCM-D5).

    Byte-level slicing of the parent on `member_key` is the consumer's job; this
    only resolves the delegation target.
    """

    member_id: str
    parent_dataset: str
    parent_slug: str
    member_key: str


def resolve_member(
    member_id: str, *, commons_root: Path | None = None
) -> ResolvedMember | None:
    """Resolve a promoted member to its parent collection and key.

    Returns None if `member_id` is not a `member_of` dataset. Raises a
    CommonsError (via the adapter) if the member entity, or its declared parent
    collection, is not present in the commons.
    """
    commons_root = commons_root or resolve_commons_root()
    adapter = CommonsEntityAdapter(commons_root)

    member_record = adapter.load(member_id)  # raises if the member entity is absent
    member_of = parse_member_of(member_record.frontmatter)
    if member_of is None:
        return None

    parent_record = adapter.load(member_of.parent_dataset)  # raises if absent
    return ResolvedMember(
        member_id=member_id,
        parent_dataset=member_of.parent_dataset,
        parent_slug=parent_record.slug,
        member_key=member_of.member_key,
    )
```

`CommonsEntityAdapter.load(dataset_id)` returns a `CommonsEntityRecord` exposing `.frontmatter` (the parsed frontmatter dict), `.slug`, `.datapackage_path`, and `.body_path`, raising on absence — so no separate parser or `load_raw` is needed.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_commons_member.py -v`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
cd ~/d/science
git add science/src/science_tool/commons/member.py science/tests/test_commons_member.py science/tests/fixtures/commons/refcoll
git commit -m "feat(commons): resolve_member delegates a promoted member to its parent (RCM-D5)"
```

---

## Task 4: `reference_collections` validate check

**Files:**
- Create: `science/src/science_tool/validate/checks/reference_collections.py`
- Modify: `science/src/science_tool/validate/checks/__init__.py`
- Test: `science/tests/validate/test_checks_reference_collections.py`

The check enforces the **structural** half of RCM-D2 at the entity layer: for every `member_of` dataset, the declared `parent_dataset` must resolve to a dataset entity in **project or commons** sources. Parent-collection resolution is structural, so a missing parent is **always** an ERROR — `resolution_status: declared_unresolved` does **not** bypass it. `declared_unresolved` is a property of the member **key/row** lookup, not of parent existence: once the parent resolves, a `declared_unresolved` member yields an INFO (the key is explicitly declared unresolved against the resolved collection). A `member_of` whose `derivation.parent_dataset` disagrees with the top-level `parent_dataset` is a WARN. **Verifying the member key against the collection's rows is out of scope** — it needs instance-specific collection metadata (a key index) and belongs to Plan 2 / the consuming instance, alongside row-level byte slicing.

- [ ] **Step 1: Write the failing tests**

Create `science/tests/validate/test_checks_reference_collections.py`, mirroring the structure of `science/tests/validate/test_checks_code_files.py` (which builds a temp project, runs one check function, and asserts on the yielded `Result`s). Use that file as the template for the project-scaffolding helper and imports.

```python
from __future__ import annotations

from science_tool.validate.checks.reference_collections import check_reference_collections
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Severity


def _ctx(project_root) -> ValidateContext:
    return ValidateContext.from_project_root(project_root, strict=False, verbose=False)


def test_member_with_existing_parent_passes(refcoll_project) -> None:
    # refcoll_project: a parent-collection dataset + a member_of dataset pointing at it.
    results = list(check_reference_collections(_ctx(refcoll_project)))
    assert not [r for r in results if r.severity is Severity.ERROR]


def test_member_with_missing_parent_errors(refcoll_project_missing_parent) -> None:
    results = list(check_reference_collections(_ctx(refcoll_project_missing_parent)))
    errors = [r for r in results if r.severity is Severity.ERROR]
    assert len(errors) == 1
    assert "parent_dataset" in errors[0].message
    assert errors[0].rule == "reference-collection.unresolved-parent"


def test_declared_unresolved_with_present_parent_infos(refcoll_project_declared_unresolved) -> None:
    # Parent EXISTS + member declares declared_unresolved → no ERROR, one INFO.
    results = list(check_reference_collections(_ctx(refcoll_project_declared_unresolved)))
    assert not [r for r in results if r.severity is Severity.ERROR]
    infos = [r for r in results if r.rule == "reference-collection.declared-unresolved"]
    assert len(infos) == 1


def test_declared_unresolved_does_not_bypass_missing_parent(
    refcoll_project_declared_unresolved_missing_parent,
) -> None:
    # Structural rule (finding 1): a missing parent is an ERROR even when the
    # member declares declared_unresolved.
    results = list(
        check_reference_collections(_ctx(refcoll_project_declared_unresolved_missing_parent))
    )
    errors = [r for r in results if r.severity is Severity.ERROR]
    assert len(errors) == 1
    assert errors[0].rule == "reference-collection.unresolved-parent"


def test_non_member_datasets_ignored(refcoll_project_workflow_only) -> None:
    results = list(check_reference_collections(_ctx(refcoll_project_workflow_only)))
    assert results == []
```

Build the five `refcoll_project*` pytest fixtures as local `@pytest.fixture`s using `tmp_path`, following the project-scaffolding pattern in `test_checks_code_files.py` (write a minimal `science.yaml` + the project layout it expects, then the dataset markdown files under the datasets directory). Each fixture writes the dataset entity markdown shown in Task 3's fixture (adjusting `derivation`/`parent_dataset`/`resolution_status` per case):

- `refcoll_project` — parent-collection dataset **present** + a `member_of` member pointing at it, no `resolution_status`.
- `refcoll_project_missing_parent` — the member only; its `derivation.parent_dataset` names a dataset not in the project.
- `refcoll_project_declared_unresolved` — parent-collection **present** + member with `resolution_status: "declared_unresolved"` in its frontmatter.
- `refcoll_project_declared_unresolved_missing_parent` — member with `resolution_status: "declared_unresolved"` but **no** parent present (locks finding 1).
- `refcoll_project_workflow_only` — a single ordinary `origin: derived` dataset with a workflow derivation (no `member_of`), to prove non-members are ignored.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/validate/test_checks_reference_collections.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'science_tool.validate.checks.reference_collections'`.

- [ ] **Step 3: Implement the check**

Create `science/src/science_tool/validate/checks/reference_collections.py`:

```python
"""Reference-collection resolution checks (RCM-D2, guardrail 1).

A promoted member (`derivation.kind: member_of`) must resolve to an existing
parent collection, unless it explicitly declares `resolution_status:
declared_unresolved`. See
docs/plans/2026-05-26-reference-collection-member-promotion-design.md.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from science_tool.commons.member import parse_member_of
from science_tool.graph.sources import load_project_sources
from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity


def _result(severity: Severity, path: Path | None, message: str, rule: str) -> Result:
    return Result(severity, path, None, message, rule, None)


@Check(section="reference collections", order=24)
def check_reference_collections(ctx: ValidateContext) -> Iterator[Result]:
    # include_commons=True: reference collections (the parents) typically live in
    # the commons, so a project member's parent must resolve against both sources.
    sources = load_project_sources(ctx.project_root, include_commons=True)
    dataset_ids = {
        e.canonical_id for e in sources.entities if getattr(e, "kind", None) == "dataset"
    }

    for entity in sources.entities:
        if getattr(entity, "kind", None) != "dataset":
            continue
        derivation = getattr(entity, "derivation", None)
        member_of = parse_member_of({"derivation": derivation}) if derivation else None
        if member_of is None:
            continue

        top_parent = getattr(entity, "parent_dataset", None)
        if top_parent is not None and top_parent != member_of.parent_dataset:
            yield _result(
                Severity.WARN,
                getattr(entity, "file_path", None),
                f"{entity.canonical_id}: parent_dataset {top_parent!r} disagrees with "
                f"derivation.parent_dataset {member_of.parent_dataset!r}",
                "reference-collection.parent-mismatch",
            )

        # Parent-collection resolution is structural: always required. A missing
        # parent is an ERROR even when declared_unresolved is set (RCM-D2 —
        # declared_unresolved is about the key/row lookup, not parent existence).
        if member_of.parent_dataset not in dataset_ids:
            yield _result(
                Severity.ERROR,
                getattr(entity, "file_path", None),
                f"{entity.canonical_id}: member_of parent_dataset "
                f"{member_of.parent_dataset!r} does not resolve to a dataset entity",
                "reference-collection.unresolved-parent",
            )
            continue

        # Parent resolved. declared_unresolved is a property of the member key/row
        # lookup (the row check itself is deferred to the consuming instance),
        # surfaced here as an INFO state against the resolved collection.
        if getattr(entity, "resolution_status", None) == "declared_unresolved":
            yield _result(
                Severity.INFO,
                getattr(entity, "file_path", None),
                f"{entity.canonical_id}: member key declared_unresolved against resolved "
                f"collection {member_of.parent_dataset!r} (honoured, RCM-D2)",
                "reference-collection.declared-unresolved",
            )
```

Note: `derivation` may arrive as a pydantic submodel rather than a plain dict. If `getattr(entity, "derivation", None)` is not a dict, coerce with `derivation.model_dump()` (or `dict(derivation)`) before passing to `parse_member_of` — match whatever `code_files.py`/`graph/sources.py` already do for nested fields.

- [ ] **Step 4: Register the check**

In `science/src/science_tool/validate/checks/__init__.py`, add `"reference_collections"` to the tuple inside `_load_canonical_checks()` (after `"cross_references"` keeps related-entity checks grouped):

```python
        "cross_references",
        "reference_collections",
        "prose_lints",
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/validate/test_checks_reference_collections.py -v`
Expected: all PASS.

- [ ] **Step 6: Run the full validate-check suite to confirm registration is clean**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/validate -q`
Expected: PASS. (Confirms the new check registers without disturbing ordering/section assertions in `test_checks_basic.py`. If `test_checks_basic.py` asserts an exact check inventory, update that inventory to include `reference-collection.*`.)

- [ ] **Step 7: Commit**

```bash
cd ~/d/science
git add science/src/science_tool/validate/checks/reference_collections.py science/src/science_tool/validate/checks/__init__.py science/tests/validate/test_checks_reference_collections.py
git commit -m "feat(validate): reference-collection resolve-or-declared_unresolved check (RCM-D2)"
```

---

## Task 5: Lint, format, and final substrate verification

**Files:** none (verification only)

- [ ] **Step 1: Ruff lint + format both packages**

Run:
```bash
cd ~/d/science/science && uv run --frozen ruff check . && uv run --frozen ruff format --check .
cd ~/d/science/science/model && uv run --frozen ruff check . && uv run --frozen ruff format --check .
```
Expected: clean. If `ruff format --check` reports diffs in files you created, run `uv run --frozen ruff format <file>` and re-commit.

- [ ] **Step 2: Full test sweep of both packages**

Run:
```bash
cd ~/d/science/science/model && uv run --frozen pytest -q
cd ~/d/science/science && uv run --frozen pytest -q
```
Expected: PASS in both. This is the substrate's acceptance gate: schema variant + parser + resolver + check all green, no regression.

- [ ] **Step 3: Confirm the backward-compatibility invariant explicitly**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_commons_member.py science/model/tests/test_entity_schema_mixin_dataset.py -q` (adjust the model path if pytest rootdir differs; otherwise run the model test from `science/model`).
Expected: PASS, including `test_dataset_workflow_derivation_without_kind_still_validates` — the proof that no existing derived dataset broke.

- [ ] **Step 4: Final commit (if any format fixes were needed)**

```bash
cd ~/d/science
git add -A
git commit -m "chore(substrate): ruff format + final substrate verification" || echo "nothing to commit"
```

---

## Self-Review (completed by plan author)

**Spec coverage** (against the design's bullets 1–3 / RCM-D2, D5):
- *`derivation.kind: member_of` as a core discriminated-union variant* → Task 1 (schema) ✓
- *virtual member descriptor/resolution semantics* → Task 3 (`resolve_member` delegates to parent; byte slicing explicitly deferred to consumer) ✓
- *reference-collection validation: member key resolves or is `declared_unresolved`* → Task 2 ships the reusable `evaluate_key_resolution` evaluator (`resolved | unresolved | declared_unresolved | unknown`); Task 4's check enforces the **structural** half — parent-collection resolution is **always** required (a missing parent is an ERROR regardless of `declared_unresolved`), and `declared_unresolved` is honoured only as a key/row-status INFO **after** the parent resolves. **Member-key-in-collection verification is deferred to Plan 2 / instance-specific key indices** — the substrate provides the evaluator, not a row-index check. ✓
- *no bio, no network* → confirmed: nothing imports a bio extension or makes a network call ✓

**Type consistency:** `MemberOf(parent_dataset, member_key)`, `ResolvedMember(member_id, parent_dataset, parent_slug, member_key)`, `ResolutionState` enum, `parse_member_of(entity)->MemberOf|None`, `resolve_member(member_id, *, commons_root)->ResolvedMember|None`, `evaluate_key_resolution(*, key, available_keys, declared_status)->ResolutionState` are used identically across Tasks 2–4. The check passes `{"derivation": derivation}` to `parse_member_of`, matching its `entity.get("derivation")` contract.

**Adapter surface (resolved):** `resolve_member` uses `CommonsEntityAdapter.load(member_id).frontmatter` — the `CommonsEntityRecord` exposes `.frontmatter` (parsed frontmatter dict) plus `.slug`/`.datapackage_path`/`.body_path`, raising on absence. There is no `load_raw()` and no parser fallback is needed.

**Out of scope (deliberate, per the two-plan split):** `bio.identity_context/1.0`, the assembly registry dataset + digest-table recipe, the resolver over registry rows, checks 1 & 3, and the free-text `reference_genome` migration are **Plan 2 (C1 assembly identity)**. C2 (gene crosswalk) and D (gene-set type) consume this substrate directly.

---

## Execution Handoff

Two execution options:

1. **Subagent-Driven (recommended)** — a fresh subagent per task with two-stage review between tasks (REQUIRED SUB-SKILL: superpowers:subagent-driven-development).
2. **Inline Execution** — execute tasks in this session with checkpoints (REQUIRED SUB-SKILL: superpowers:executing-plans).

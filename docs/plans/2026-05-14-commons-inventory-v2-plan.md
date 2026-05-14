# Phase D2: Commons inventory_v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the `inventory_v2` export contract plus two producers — a standalone commons-store inventory builder and v2 support in the project inventory builder — so the dashboard can consume the shared tier and overlay views without scanning files.

**Architecture:** `inventory_v2.py` is a sibling contract module that imports the unchanged `inventory_v1` models and adds `InventoryOverlay`, a v2 `InventoryPayload` (with `overlays[]`), and overlay-aware hash machinery. `build_commons_inventory()` walks the commons store via `CommonsEntityAdapter` and projects dataset resources; `build_inventory(..., schema_version="2")` scans a project's overlay files into `overlays[]`. A small Phase B prerequisite makes `CommonsEntityAdapter.scan()` walk-safe (yield, not raise, on a per-entity layout error).

**Tech Stack:** Python 3.11+, Pydantic 2, Click 8.1, pytest, `uv run pytest`. Reference design: `docs/plans/2026-05-14-commons-inventory-v2-design.md`.

**Conventions:**
- TDD throughout; one commit per task.
- Test invocation from `~/d/science/science`: `uv run pytest <path> -v`. Model-package tests live under `model/tests/` and run the same way (e.g. `uv run pytest model/tests/test_inventory_contract_v2.py -v`).
- All paths below are relative to `~/d/science/` unless prefixed with `science/` (the inner package dir is `~/d/science/science/`).

---

### Task 1: Phase B prerequisite — make `CommonsEntityAdapter.scan()` walk-safe

`_scan_type` currently **raises** `CommonsLayoutError` mid-generator when a dataset directory has `entity.md` but no `datapackage.yaml`. A raised exception aborts the whole walk — and crashes `CommonsValidator.validate()` and `RegistryBuilder.rebuild()`, which both iterate the same `scan()`.

This task makes `scan()` *yield* an error item instead. Crucially it yields the **existing `CommonsEntityError` type** (with a `CommonsLayoutError` as its `cause`) — *not* a new type and *not* a bare `CommonsLayoutError`. Because the yielded item is still a `CommonsEntityError`, every existing consumer (`CommonsValidator`, `RegistryBuilder`, and both `--json` CLI paths, which read `.path`/`.canonical_id`/`.cause`) handles it correctly with **zero code change**. `scan()`'s return type does not widen. `load()` is left untouched — single-id lookup, raising is correct there.

Steps 5-8 are regression coverage proving the no-consumer-change claim.

**Files:**
- Modify: `science/src/science_tool/commons/adapter.py:73-77` (the `raise` block in `_scan_type`)
- Test: `science/tests/test_commons_adapter.py`, `science/tests/test_commons_cli.py`

- [ ] **Step 1: Replace the adapter test that asserts `scan()` raises**

In `science/tests/test_commons_adapter.py`, **delete** `test_scan_raises_layout_error_for_dataset_missing_datapackage` (lines 59-65) and replace it with:

```python
def test_scan_yields_entity_error_for_dataset_missing_datapackage(
    tmp_path: Path,
) -> None:
    root = _make_store(tmp_path, "valid")
    no_dp = root / "datasets" / "no-dp"
    no_dp.mkdir()
    (no_dp / "entity.md").write_text(
        "---\n"
        'schema_profile: "science-entity-base/1.0+dataset/1.0"\n'
        'id: "dataset:no-dp"\n'
        'type: "dataset"\n'
        'title: "No datapackage"\n'
        'version: "1.0.0"\n'
        'status: "active"\n'
        'created: "2026-05-13"\n'
        'updated: "2026-05-13"\n'
        'datapackage: "datapackage.yaml"\n'
        'origin: "external"\n'
        'tier: "use-now"\n'
        "access:\n"
        '  level: "public"\n'
        "  verified: true\n"
        '  source_url: "https://example.org"\n'
        "ontology_terms: []\n"
        "tags: []\n"
        "---\nbody\n",
        encoding="utf-8",
    )
    items = list(CommonsEntityAdapter(root).scan())
    errors = [it for it in items if isinstance(it, CommonsEntityError)]
    records = [it for it in items if isinstance(it, CommonsEntityRecord)]
    # The missing datapackage is yielded as a CommonsEntityError, not raised,
    # and not a bare CommonsLayoutError.
    assert len(errors) == 1
    assert errors[0].path == no_dp
    assert errors[0].canonical_id == "dataset:no-dp"
    assert isinstance(errors[0].cause, CommonsLayoutError)
    # Entities discovered after the bad dataset are still emitted.
    assert "dataset:rnaseq-example" in {r.canonical_id for r in records}
    assert "paper:Adams2025" in {r.canonical_id for r in records}
```

`CommonsEntityError`, `CommonsEntityRecord`, and `CommonsLayoutError` are all already imported at the top of `test_commons_adapter.py`.

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_commons_adapter.py::test_scan_yields_entity_error_for_dataset_missing_datapackage -v`
Expected: FAIL — `scan()` currently raises `CommonsLayoutError` instead of yielding a `CommonsEntityError`.

- [ ] **Step 3: Make `_scan_type` yield a `CommonsEntityError` instead of raising**

In `science/src/science_tool/commons/adapter.py`, in `_scan_type`, replace the `raise` block:

```python
                if not dp_path.is_file():
                    raise CommonsLayoutError(
                        child,
                        reason="dataset directory missing required datapackage.yaml sibling",
                    )
                yield self._build(type_name, child.name, entity_path, dp_path)
```

with:

```python
                if not dp_path.is_file():
                    yield CommonsEntityError(
                        child,
                        canonical_id=f"dataset:{child.name}",
                        cause=CommonsLayoutError(
                            child,
                            reason=(
                                "dataset directory missing required "
                                "datapackage.yaml sibling"
                            ),
                        ),
                    )
                    continue
                yield self._build(type_name, child.name, entity_path, dp_path)
```

Both `CommonsEntityError` and `CommonsLayoutError` are already imported in `adapter.py`. The `scan()` / `_scan_type()` signatures are unchanged — they still return `Iterator[CommonsEntityRecord | CommonsEntityError]`.

- [ ] **Step 4: Run the adapter test file to verify it passes**

Run: `uv run pytest tests/test_commons_adapter.py -v`
Expected: PASS (all adapter tests, including the new one).

- [ ] **Step 5: Write the regression tests for the downstream CLI consumers**

In `science/tests/test_commons_cli.py`, add at the end. These prove that `index rebuild` and `validate` handle the yielded `CommonsEntityError` with no code change:

```python
_NO_DP_ENTITY = (
    "---\n"
    'schema_profile: "science-entity-base/1.0+dataset/1.0"\n'
    'id: "dataset:no-dp"\n'
    'type: "dataset"\n'
    'title: "No datapackage"\n'
    'version: "1.0.0"\n'
    'status: "active"\n'
    'created: "2026-05-13"\n'
    'updated: "2026-05-13"\n'
    'datapackage: "datapackage.yaml"\n'
    'origin: "external"\n'
    'tier: "use-now"\n'
    "access:\n"
    '  level: "public"\n'
    "  verified: true\n"
    '  source_url: "https://example.org"\n'
    "ontology_terms: []\n"
    "tags: []\n"
    "---\nbody\n"
)


def test_index_rebuild_reports_missing_datapackage_as_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _seeded_store(tmp_path)
    no_dp = root / "datasets" / "no-dp"
    no_dp.mkdir()
    (no_dp / "entity.md").write_text(_NO_DP_ENTITY, encoding="utf-8")
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))
    runner = CliRunner()
    result = runner.invoke(commons_group, ["index", "rebuild", "--json"])
    assert result.exit_code == 1, result.output
    payload = json.loads(result.output)
    assert payload["entities_indexed"] == 5
    assert any("no-dp" in err["path"] for err in payload["errors"])


def test_validate_reports_missing_datapackage_as_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _seeded_store(tmp_path)
    no_dp = root / "datasets" / "no-dp"
    no_dp.mkdir()
    (no_dp / "entity.md").write_text(_NO_DP_ENTITY, encoding="utf-8")
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))
    runner = CliRunner()
    result = runner.invoke(commons_group, ["validate", "--json"])
    assert result.exit_code == 1, result.output
    payload = json.loads(result.output)
    assert any("no-dp" in err["path"] for err in payload["errors"])
```

- [ ] **Step 6: Run the regression tests to verify they pass**

Run: `uv run pytest tests/test_commons_cli.py -k "missing_datapackage" -v`
Expected: PASS — `RegistryBuilder.rebuild()` and `CommonsValidator.validate()` both already route `CommonsEntityError` items into their report's `errors` list, and the `--json` CLI paths read `.path`/`.canonical_id`/`.cause` (all present on `CommonsEntityError`). No code change was needed in `registry.py`, `validator.py`, or `cli.py`.

- [ ] **Step 7: Run both touched test files to confirm nothing else regressed**

Run: `uv run pytest tests/test_commons_adapter.py tests/test_commons_cli.py tests/test_commons_validator.py tests/test_commons_registry.py -v`
Expected: PASS (all tests — the existing `test_load_dataset_missing_datapackage_raises_layout_error` still passes because `load()` is untouched).

- [ ] **Step 8: Commit**

```bash
git add science/src/science_tool/commons/adapter.py science/tests/test_commons_adapter.py science/tests/test_commons_cli.py
git commit -m "fix(commons): scan() yields CommonsEntityError instead of raising mid-walk"
```

---

### Task 2: Datapackage reader — `DataResource` gains `bytes`/`format`/`mediatype`

Extend Phase C's `read_datapackage` so projected resources can carry the display-useful Frictionless fields. Additive — existing callers (the Phase C resolver) read only `.path`/`.hash` and are unaffected; the new fields default to `None`.

**Files:**
- Modify: `science/src/science_tool/commons/datapackage.py:81-87` (`DataResource`), `:134-178` (`read_datapackage` resource loop)
- Test: `science/tests/test_commons_datapackage.py`

- [ ] **Step 1: Write the failing tests**

In `science/tests/test_commons_datapackage.py`, add at the end:

```python
def test_read_datapackage_captures_bytes_format_mediatype(tmp_path: Path) -> None:
    dp = _write(
        tmp_path / "datapackage.yaml",
        "resources:\n"
        "  - path: counts.parquet\n"
        f'    hash: "{_GOOD_HASH}"\n'
        "    bytes: 12345678\n"
        '    format: "parquet"\n'
        '    mediatype: "application/vnd.apache.parquet"\n',
    )
    descriptor = read_datapackage(dp)
    resource = descriptor.resources[0]
    assert resource.bytes == 12345678
    assert resource.format == "parquet"
    assert resource.mediatype == "application/vnd.apache.parquet"


def test_read_datapackage_optional_fields_default_to_none(tmp_path: Path) -> None:
    dp = _write(
        tmp_path / "datapackage.yaml",
        "resources:\n  - path: counts.parquet\n" f'    hash: "{_GOOD_HASH}"\n',
    )
    resource = read_datapackage(dp).resources[0]
    assert resource.bytes is None
    assert resource.format is None
    assert resource.mediatype is None


def test_read_datapackage_rejects_non_int_bytes(tmp_path: Path) -> None:
    dp = _write(
        tmp_path / "datapackage.yaml",
        "resources:\n"
        "  - path: counts.parquet\n"
        f'    hash: "{_GOOD_HASH}"\n'
        '    bytes: "lots"\n',
    )
    with pytest.raises(CommonsDatapackageError, match="bytes"):
        read_datapackage(dp)


def test_read_datapackage_rejects_bool_bytes(tmp_path: Path) -> None:
    dp = _write(
        tmp_path / "datapackage.yaml",
        "resources:\n"
        "  - path: counts.parquet\n"
        f'    hash: "{_GOOD_HASH}"\n'
        "    bytes: true\n",
    )
    with pytest.raises(CommonsDatapackageError, match="bytes"):
        read_datapackage(dp)


def test_read_datapackage_rejects_non_str_format(tmp_path: Path) -> None:
    dp = _write(
        tmp_path / "datapackage.yaml",
        "resources:\n"
        "  - path: counts.parquet\n"
        f'    hash: "{_GOOD_HASH}"\n'
        "    format: 5\n",
    )
    with pytest.raises(CommonsDatapackageError, match="format"):
        read_datapackage(dp)


def test_read_datapackage_rejects_non_str_mediatype(tmp_path: Path) -> None:
    dp = _write(
        tmp_path / "datapackage.yaml",
        "resources:\n"
        "  - path: counts.parquet\n"
        f'    hash: "{_GOOD_HASH}"\n'
        "    mediatype: 5\n",
    )
    with pytest.raises(CommonsDatapackageError, match="mediatype"):
        read_datapackage(dp)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_commons_datapackage.py -k "bytes or format or mediatype or optional_fields" -v`
Expected: FAIL — `DataResource` has no `bytes`/`format`/`mediatype` fields; `read_datapackage` does not parse them.

- [ ] **Step 3: Add the fields to `DataResource`**

In `science/src/science_tool/commons/datapackage.py`, replace the `DataResource` dataclass (lines 81-87):

```python
@dataclass(frozen=True, slots=True)
class DataResource:
    """One resource entry from a datapackage.yaml."""

    path: str  # validated forward-slash relative logical path
    hash: str  # full "sha256:<hex>" string, verbatim from resources[].hash
    bytes: int | None = None  # resources[].bytes if present
    format: str | None = None  # resources[].format if present
    mediatype: str | None = None  # resources[].mediatype if present
```

- [ ] **Step 4: Parse the new fields in `read_datapackage`**

In `science/src/science_tool/commons/datapackage.py`, in the resource loop of `read_datapackage`, replace the final line that appends the resource:

```python
        resources.append(DataResource(path=logical_path, hash=raw_hash))
```

with:

```python
        raw_bytes = entry.get("bytes")
        if raw_bytes is not None and (
            not isinstance(raw_bytes, int) or isinstance(raw_bytes, bool)
        ):
            raise CommonsDatapackageError(
                path,
                reason=(
                    f"resources[{index}] ({logical_path}) has a non-integer 'bytes'"
                ),
            )
        raw_format = entry.get("format")
        if raw_format is not None and not isinstance(raw_format, str):
            raise CommonsDatapackageError(
                path,
                reason=f"resources[{index}] ({logical_path}) has a non-string 'format'",
            )
        raw_mediatype = entry.get("mediatype")
        if raw_mediatype is not None and not isinstance(raw_mediatype, str):
            raise CommonsDatapackageError(
                path,
                reason=(
                    f"resources[{index}] ({logical_path}) has a non-string 'mediatype'"
                ),
            )

        resources.append(
            DataResource(
                path=logical_path,
                hash=raw_hash,
                bytes=raw_bytes,
                format=raw_format,
                mediatype=raw_mediatype,
            )
        )
```

- [ ] **Step 5: Run the full datapackage test file to verify it passes**

Run: `uv run pytest tests/test_commons_datapackage.py -v`
Expected: PASS (new tests plus all existing ones — existing `DataResource(path=..., hash=...)` equality checks still hold because the new fields default to `None`).

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/commons/datapackage.py science/tests/test_commons_datapackage.py
git commit -m "feat(commons): datapackage reader captures bytes/format/mediatype"
```

---

### Task 3: `inventory_v2` contract — module skeleton + `InventoryOverlay`

Create the v2 contract module: imports of the unchanged v1 pieces, `SCHEMA_VERSION`, and the new `InventoryOverlay` model.

**Files:**
- Create: `science/model/src/science_model/contracts/inventory_v2.py`
- Test: `science/model/tests/test_inventory_contract_v2.py` (create)

- [ ] **Step 1: Write the failing tests**

Create `science/model/tests/test_inventory_contract_v2.py`:

```python
from __future__ import annotations

import pytest
from pydantic import ValidationError

from science_model.contracts.inventory_v2 import (
    InventoryOverlay,
    InventorySourceLocation,
)


def _source() -> InventorySourceLocation:
    return InventorySourceLocation(
        adapter="commons-overlay", path="doc/papers/Adams2025.md"
    )


def test_inventory_overlay_accepts_minimal_fields() -> None:
    overlay = InventoryOverlay(
        overlay_of="paper:Adams2025",
        project_id="proj-alpha",
        source=_source(),
    )
    assert overlay.overlay_of == "paper:Adams2025"
    assert overlay.pin_version is None
    assert overlay.project_only_fields == {}
    assert overlay.append_fields == {}
    assert overlay.body_sections == []


def test_inventory_overlay_carries_split_fields_and_body() -> None:
    overlay = InventoryOverlay(
        overlay_of="paper:Adams2025",
        project_id="proj-alpha",
        source=_source(),
        pin_version="1.2.0",
        project_only_fields={"relevance": "H2", "hypothesis_links": ["H2", "H4"]},
        append_fields={"tags": ["overlay-added"]},
        body_sections=["## Project-Specific Notes\nText."],
    )
    assert overlay.pin_version == "1.2.0"
    assert overlay.project_only_fields["hypothesis_links"] == ["H2", "H4"]
    assert overlay.append_fields["tags"] == ["overlay-added"]
    assert overlay.body_sections == ["## Project-Specific Notes\nText."]


def test_inventory_overlay_rejects_overlay_of_without_separator() -> None:
    with pytest.raises(ValidationError, match="canonical"):
        InventoryOverlay(
            overlay_of="Adams2025", project_id="proj-alpha", source=_source()
        )


def test_inventory_overlay_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        InventoryOverlay(
            overlay_of="paper:Adams2025",
            project_id="proj-alpha",
            source=_source(),
            mystery="value",
        )


def test_inventory_overlay_rejects_non_json_field_values() -> None:
    with pytest.raises(ValidationError, match="JSON"):
        InventoryOverlay(
            overlay_of="paper:Adams2025",
            project_id="proj-alpha",
            source=_source(),
            project_only_fields={"bad": object()},
        )
    with pytest.raises(ValidationError, match="JSON"):
        InventoryOverlay(
            overlay_of="paper:Adams2025",
            project_id="proj-alpha",
            source=_source(),
            append_fields={"bad": object()},
        )
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest model/tests/test_inventory_contract_v2.py -v`
Expected: FAIL — `science_model.contracts.inventory_v2` does not exist.

- [ ] **Step 3: Create the v2 module with imports and `InventoryOverlay`**

Create `science/model/src/science_model/contracts/inventory_v2.py`:

```python
"""inventory_v2: sibling export contract to inventory_v1.

Adds a top-level `overlays[]` list (the project-overlay projection) and pins
`schema_version` to "2". All v1 models except `InventoryPayload` are reused
verbatim; the `_`-prefixed v1 helpers are imported here on purpose, so a future
v1 rename fails this module's tests loudly.

The commons inventory is an `InventoryPayload` with `project_id="commons"`
(a fixed sentinel — the commons store is not a project), `project=None`,
`project_path` set to the commons root, and `overlays=[]`. A project payload
has `entities` of `scope="project"` only and may carry a non-empty `overlays`.
"""

from __future__ import annotations

import hashlib
from typing import Any, Final, Literal

from pydantic import Field, field_validator

from science_model.contracts.inventory_v1 import (
    InventoryAlias,
    InventoryEntity,
    InventoryFindingCandidate,
    InventoryGraphAddress,
    InventoryProjectMetadata,
    InventoryReference,
    InventorySourceLocation,
    InventoryWarning,
    _InventoryContractModel,
    _normalize_entity_for_content_hash,
    _normalize_finding_candidate_for_content_hash,
    _normalize_project_for_content_hash,
    _sort_key_with_canonical_tie_breaker,
    _validate_json_value,
    canonical_json_bytes,
)

__all__ = [
    "SCHEMA_VERSION",
    "InventoryAlias",
    "InventoryEntity",
    "InventoryFindingCandidate",
    "InventoryGraphAddress",
    "InventoryOverlay",
    "InventoryPayload",
    "InventoryProjectMetadata",
    "InventoryReference",
    "InventorySourceLocation",
    "InventoryWarning",
    "compute_audit_hash",
    "compute_content_hash",
    "finalize_inventory_payload",
]

SCHEMA_VERSION: Final = "2"


class InventoryOverlay(_InventoryContractModel):
    overlay_of: str
    project_id: str
    source: InventorySourceLocation
    pin_version: str | None = None
    pin_effective_version: str | None = None
    project_only_fields: dict[str, Any] = Field(default_factory=dict)
    append_fields: dict[str, Any] = Field(default_factory=dict)
    body_sections: list[str] = Field(default_factory=list)

    @field_validator("overlay_of")
    @classmethod
    def overlay_of_has_separator(cls, value: str) -> str:
        if ":" not in value:
            msg = (
                "Inventory overlay overlay_of must be canonical "
                f"'<kind>:<local-id>', got {value!r}."
            )
            raise ValueError(msg)
        return value

    @field_validator("project_only_fields", "append_fields")
    @classmethod
    def merge_fields_are_json_serializable(
        cls, value: dict[str, Any]
    ) -> dict[str, Any]:
        _validate_json_value(value, "merge_fields")
        return value
```

Note: `InventoryPayload`, `compute_content_hash`, `compute_audit_hash`, and
`finalize_inventory_payload` are named in `__all__` now but are added in
Tasks 4-5. The module will not import cleanly until Task 5 is done — that is
expected; Task 3's tests only touch `InventoryOverlay` and
`InventorySourceLocation`, both defined/imported above.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest model/tests/test_inventory_contract_v2.py -v`
Expected: PASS — all five `InventoryOverlay` tests. (Importing the names listed in `__all__` is not exercised yet; pytest only imports what the test file imports.)

- [ ] **Step 5: Commit**

```bash
git add science/model/src/science_model/contracts/inventory_v2.py science/model/tests/test_inventory_contract_v2.py
git commit -m "feat(contracts): inventory_v2 module skeleton + InventoryOverlay"
```

---

### Task 4: `inventory_v2` contract — v2 `InventoryPayload`

Add the v2 payload model: v1's `InventoryPayload` field-for-field, with `schema_version` pinned to `"2"` and a new `overlays` list.

**Files:**
- Modify: `science/model/src/science_model/contracts/inventory_v2.py`
- Test: `science/model/tests/test_inventory_contract_v2.py`

- [ ] **Step 1: Write the failing tests**

Append to `science/model/tests/test_inventory_contract_v2.py`:

```python
def test_inventory_payload_v2_defaults_schema_version_and_overlays() -> None:
    from science_model.contracts.inventory_v2 import InventoryPayload

    payload = InventoryPayload(
        generated_at="2026-05-14T10:00:00Z", project_id="commons"
    )
    assert payload.schema_version == "2"
    assert payload.overlays == []
    assert payload.entities == []


def test_inventory_payload_v2_rejects_schema_version_1() -> None:
    from science_model.contracts.inventory_v2 import InventoryPayload

    with pytest.raises(ValidationError):
        InventoryPayload(
            generated_at="2026-05-14T10:00:00Z",
            project_id="commons",
            schema_version="1",
        )


def test_inventory_payload_v2_rejects_unknown_fields() -> None:
    from science_model.contracts.inventory_v2 import InventoryPayload

    with pytest.raises(ValidationError):
        InventoryPayload(
            generated_at="2026-05-14T10:00:00Z",
            project_id="commons",
            mystery="value",
        )


def test_inventory_payload_v2_carries_overlays() -> None:
    from science_model.contracts.inventory_v2 import InventoryPayload

    payload = InventoryPayload(
        generated_at="2026-05-14T10:00:00Z",
        project_id="proj-alpha",
        overlays=[
            InventoryOverlay(
                overlay_of="paper:Adams2025",
                project_id="proj-alpha",
                source=_source(),
            )
        ],
    )
    assert payload.overlays[0].overlay_of == "paper:Adams2025"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest model/tests/test_inventory_contract_v2.py -k payload_v2 -v`
Expected: FAIL — `ImportError`: `InventoryPayload` is named in `__all__` but not yet defined.

- [ ] **Step 3: Add the v2 `InventoryPayload`**

In `science/model/src/science_model/contracts/inventory_v2.py`, append after `InventoryOverlay`:

```python
class InventoryPayload(_InventoryContractModel):
    schema_version: Literal["2"] = SCHEMA_VERSION
    generated_at: str
    project_id: str
    project_path: str | None = None
    project: InventoryProjectMetadata | None = None
    content_hash: str | None = None
    audit_hash: str | None = None
    entities: list[InventoryEntity] = Field(default_factory=list)
    aliases: list[InventoryAlias] = Field(default_factory=list)
    graph_addresses: list[InventoryGraphAddress] = Field(default_factory=list)
    finding_candidates: list[InventoryFindingCandidate] = Field(default_factory=list)
    warnings: list[InventoryWarning] = Field(default_factory=list)
    watch_paths: list[str] = Field(default_factory=list)
    overlays: list[InventoryOverlay] = Field(default_factory=list)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest model/tests/test_inventory_contract_v2.py -k payload_v2 -v`
Expected: PASS — all four `payload_v2` tests.

- [ ] **Step 5: Commit**

```bash
git add science/model/src/science_model/contracts/inventory_v2.py science/model/tests/test_inventory_contract_v2.py
git commit -m "feat(contracts): inventory_v2 InventoryPayload model"
```

---

### Task 5: `inventory_v2` contract — hash machinery

Add v2's content/audit hash functions. They reuse v1's `_normalize_*` helpers and additionally sort `overlays` for the content hash; the audit hash drops `overlays` entirely (overlays are content, not audit metadata).

**Files:**
- Modify: `science/model/src/science_model/contracts/inventory_v2.py`
- Test: `science/model/tests/test_inventory_contract_v2.py`

- [ ] **Step 1: Write the failing tests**

Append to `science/model/tests/test_inventory_contract_v2.py`:

```python
def test_v2_hashes_ignore_generated_at() -> None:
    from science_model.contracts.inventory_v2 import (
        InventoryPayload,
        compute_audit_hash,
        compute_content_hash,
    )

    first = InventoryPayload(
        generated_at="2026-05-14T10:00:00Z",
        project_id="commons",
        overlays=[
            InventoryOverlay(
                overlay_of="paper:Adams2025",
                project_id="proj-alpha",
                source=_source(),
            )
        ],
    )
    second = first.model_copy(update={"generated_at": "2026-05-14T11:00:00Z"})
    assert compute_content_hash(first) == compute_content_hash(second)
    assert compute_audit_hash(first) == compute_audit_hash(second)


def test_v2_content_hash_is_stable_under_overlay_reordering() -> None:
    from science_model.contracts.inventory_v2 import (
        InventoryPayload,
        compute_content_hash,
    )

    left = InventoryPayload(
        generated_at="2026-05-14T10:00:00Z",
        project_id="proj-alpha",
        overlays=[
            InventoryOverlay(
                overlay_of="paper:Beta2025",
                project_id="proj-alpha",
                source=_source(),
            ),
            InventoryOverlay(
                overlay_of="paper:Alpha2025",
                project_id="proj-alpha",
                source=_source(),
            ),
        ],
    )
    right = left.model_copy(update={"overlays": list(reversed(left.overlays))})
    assert compute_content_hash(left) == compute_content_hash(right)


def test_v2_content_hash_changes_when_overlay_field_changes() -> None:
    from science_model.contracts.inventory_v2 import (
        InventoryPayload,
        compute_content_hash,
    )

    base = InventoryPayload(
        generated_at="2026-05-14T10:00:00Z",
        project_id="proj-alpha",
        overlays=[
            InventoryOverlay(
                overlay_of="paper:Adams2025",
                project_id="proj-alpha",
                source=_source(),
                project_only_fields={"relevance": "H2"},
            )
        ],
    )
    changed = base.model_copy(
        update={
            "overlays": [
                base.overlays[0].model_copy(
                    update={"project_only_fields": {"relevance": "H9"}}
                )
            ]
        }
    )
    assert compute_content_hash(base) != compute_content_hash(changed)


def test_v2_audit_hash_ignores_overlays() -> None:
    from science_model.contracts.inventory_v2 import (
        InventoryPayload,
        compute_audit_hash,
    )

    base = InventoryPayload(
        generated_at="2026-05-14T10:00:00Z",
        project_id="proj-alpha",
        overlays=[
            InventoryOverlay(
                overlay_of="paper:Adams2025",
                project_id="proj-alpha",
                source=_source(),
                project_only_fields={"relevance": "H2"},
            )
        ],
    )
    no_overlays = base.model_copy(update={"overlays": []})
    assert compute_audit_hash(base) == compute_audit_hash(no_overlays)


def test_v2_finalize_populates_stable_hashes() -> None:
    from science_model.contracts.inventory_v2 import (
        InventoryPayload,
        compute_audit_hash,
        compute_content_hash,
        finalize_inventory_payload,
    )

    payload = InventoryPayload(
        generated_at="2026-05-14T10:00:00Z", project_id="commons"
    )
    finalized = finalize_inventory_payload(payload)
    assert finalized.content_hash == compute_content_hash(payload)
    assert finalized.audit_hash == compute_audit_hash(payload)
    assert finalize_inventory_payload(finalized).content_hash == finalized.content_hash
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest model/tests/test_inventory_contract_v2.py -k "v2_hashes or v2_content or v2_audit or v2_finalize" -v`
Expected: FAIL — `ImportError`: `compute_content_hash` / `compute_audit_hash` / `finalize_inventory_payload` are named in `__all__` but not defined.

- [ ] **Step 3: Add the hash machinery**

In `science/model/src/science_model/contracts/inventory_v2.py`, append at the end of the file:

```python
def _payload_for_content_hash(payload: InventoryPayload) -> dict[str, Any]:
    data = payload.model_dump(mode="json", exclude_none=True)
    for key in ("generated_at", "content_hash", "audit_hash", "warnings"):
        data.pop(key, None)
    if "project" in data:
        data["project"] = _normalize_project_for_content_hash(data["project"])
    data["entities"] = sorted(
        (_normalize_entity_for_content_hash(item) for item in data.get("entities", [])),
        key=lambda item: _sort_key_with_canonical_tie_breaker(item, ("id",)),
    )
    data["aliases"] = sorted(
        data.get("aliases", []),
        key=lambda item: _sort_key_with_canonical_tie_breaker(item, ("alias",)),
    )
    data["graph_addresses"] = sorted(
        data.get("graph_addresses", []),
        key=lambda item: _sort_key_with_canonical_tie_breaker(item, ("address",)),
    )
    data["finding_candidates"] = sorted(
        (
            _normalize_finding_candidate_for_content_hash(item)
            for item in data.get("finding_candidates", [])
        ),
        key=lambda item: _sort_key_with_canonical_tie_breaker(item, ("candidate_id",)),
    )
    data["overlays"] = sorted(
        data.get("overlays", []),
        key=lambda item: _sort_key_with_canonical_tie_breaker(
            item, ("overlay_of", "project_id")
        ),
    )
    data["watch_paths"] = sorted(data.get("watch_paths", []))
    return data


def _payload_for_audit_hash(payload: InventoryPayload) -> dict[str, Any]:
    data = payload.model_dump(mode="json", exclude_none=True)
    for key in (
        "generated_at",
        "content_hash",
        "audit_hash",
        "entities",
        "aliases",
        "graph_addresses",
        "finding_candidates",
        "overlays",
    ):
        data.pop(key, None)
    if "project" in data:
        data["project"] = _normalize_project_for_content_hash(data["project"])
    data["warnings"] = sorted(
        data.get("warnings", []),
        key=lambda item: _sort_key_with_canonical_tie_breaker(
            item, ("severity", "code", "path", "canonical_id")
        ),
    )
    data["watch_paths"] = sorted(data.get("watch_paths", []))
    return data


def compute_content_hash(payload: InventoryPayload) -> str:
    return hashlib.sha256(
        canonical_json_bytes(_payload_for_content_hash(payload))
    ).hexdigest()


def compute_audit_hash(payload: InventoryPayload) -> str:
    return hashlib.sha256(
        canonical_json_bytes(_payload_for_audit_hash(payload))
    ).hexdigest()


def finalize_inventory_payload(payload: InventoryPayload) -> InventoryPayload:
    content_hash = compute_content_hash(payload)
    audit_hash = compute_audit_hash(payload)
    return payload.model_copy(
        update={"content_hash": content_hash, "audit_hash": audit_hash}
    )
```

- [ ] **Step 4: Run the full v2 contract test file to verify it passes**

Run: `uv run pytest model/tests/test_inventory_contract_v2.py -v`
Expected: PASS (every test in the file — Tasks 3, 4, 5).

- [ ] **Step 5: Verify the v1 contract still passes (the imported helpers are unchanged)**

Run: `uv run pytest model/tests/test_inventory_contract_v1.py -v`
Expected: PASS — `inventory_v2` only imports from `inventory_v1`; it does not modify it.

- [ ] **Step 6: Commit**

```bash
git add science/model/src/science_model/contracts/inventory_v2.py science/model/tests/test_inventory_contract_v2.py
git commit -m "feat(contracts): inventory_v2 overlay-aware hash machinery"
```

---

### Task 6: `build_commons_inventory()` — entity projection

Create `commons/inventory.py` with `build_commons_inventory()`. This task handles all three `scan()` arms (record, entity error, layout error) and projects entities — **without** dataset resources yet (Task 7 adds those).

**Files:**
- Create: `science/src/science_tool/commons/inventory.py`
- Test: `science/tests/test_commons_inventory.py` (create)

- [ ] **Step 1: Write the failing tests**

Create `science/tests/test_commons_inventory.py`:

```python
"""Tests for science_tool.commons.inventory."""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from science_tool.commons.errors import CommonsRootNotFoundError
from science_tool.commons.inventory import build_commons_inventory

FIXTURES = Path(__file__).parent / "fixtures" / "commons"

_NO_DP_ENTITY = (
    "---\n"
    'schema_profile: "science-entity-base/1.0+dataset/1.0"\n'
    'id: "dataset:no-dp"\n'
    'type: "dataset"\n'
    'title: "No datapackage"\n'
    'version: "1.0.0"\n'
    'status: "active"\n'
    'created: "2026-05-13"\n'
    'updated: "2026-05-13"\n'
    'datapackage: "datapackage.yaml"\n'
    'origin: "external"\n'
    'tier: "use-now"\n'
    "access:\n"
    '  level: "public"\n'
    "  verified: true\n"
    '  source_url: "https://example.org"\n'
    "ontology_terms: []\n"
    "tags: []\n"
    "---\nbody\n"
)

_BAD_PAPER = (
    "---\n"
    'schema_profile: "science-entity-base/1.0+paper/1.0"\n'
    'id: "paper:badname"\n'
    'type: "paper"\n'
    'title: "Bad"\n'
    'version: "1.0.0"\n'
    'status: "active"\n'
    'created: "2026-05-13"\n'
    'updated: "2026-05-13"\n'
    'bibkey: "bad-name"\n'
    'authors: ["X"]\n'
    "year: 2025\n"
    'journal: "T"\n'
    "ontology_terms: []\n"
    "tags: []\n"
    "---\nbody\n"
)


def _make_store(tmp_path: Path) -> Path:
    root = tmp_path / "commons"
    shutil.copytree(FIXTURES / "valid", root)
    return root


def test_build_commons_inventory_clean_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _make_store(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))
    payload = build_commons_inventory()

    assert payload.schema_version == "2"
    assert payload.project_id == "commons"
    assert payload.project is None
    assert payload.project_path == str(root)
    assert payload.overlays == []
    assert payload.content_hash
    assert payload.audit_hash
    assert {e.id for e in payload.entities} == {
        "dataset:cath-domains",
        "dataset:rnaseq-example",
        "paper:Adams2025",
        "topic:single-cell-foundation-models",
        "theme:research-hygiene",
    }
    assert all(e.scope == "cross-project" for e in payload.entities)
    paper = next(e for e in payload.entities if e.id == "paper:Adams2025")
    assert paper.kind == "paper"
    assert paper.local_id == "Adams2025"
    assert paper.source.adapter == "commons-entity"
    # schema_profile is not a promoted field, so it lands in data.
    assert paper.data["schema_profile"] == "science-entity-base/1.0+paper/1.0"
    assert sorted(payload.watch_paths) == ["datasets", "papers", "themes", "topics"]


def test_build_commons_inventory_warns_on_malformed_entity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _make_store(tmp_path)
    (root / "papers" / "badname.md").write_text(_BAD_PAPER, encoding="utf-8")
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))
    payload = build_commons_inventory()

    codes = {w.code for w in payload.warnings}
    assert "commons-entity-invalid" in codes
    # The five valid entities are still emitted.
    assert len(payload.entities) == 5


def test_build_commons_inventory_warns_on_missing_datapackage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _make_store(tmp_path)
    no_dp = root / "datasets" / "no-dp"
    no_dp.mkdir()
    (no_dp / "entity.md").write_text(_NO_DP_ENTITY, encoding="utf-8")
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))
    payload = build_commons_inventory()

    dp_warnings = [w for w in payload.warnings if w.code == "commons-datapackage-invalid"]
    assert len(dp_warnings) == 1
    # The valid entities discovered after the bad dataset are still emitted.
    assert "dataset:rnaseq-example" in {e.id for e in payload.entities}


def test_build_commons_inventory_missing_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(tmp_path / "nope"))
    with pytest.raises(CommonsRootNotFoundError):
        build_commons_inventory()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_commons_inventory.py -v`
Expected: FAIL — `science_tool.commons.inventory` does not exist.

- [ ] **Step 3: Create `commons/inventory.py`**

Create `science/src/science_tool/commons/inventory.py`:

```python
"""Build the inventory_v2 payload for the whole commons store.

Walks the commons store via CommonsEntityAdapter, projects each canonical
entity as an InventoryEntity with scope="cross-project", and (Task 7) projects
dataset resources into data["resources"]. Per-entity problems become
InventoryWarning entries; the only hard failure is a missing commons root.
"""

from __future__ import annotations

from datetime import UTC, datetime

from science_model.contracts.inventory_v2 import (
    InventoryAlias,
    InventoryEntity,
    InventoryPayload,
    InventoryReference,
    InventorySourceLocation,
    InventoryWarning,
    finalize_inventory_payload,
)

from science_tool.commons.adapter import CommonsEntityAdapter, CommonsEntityRecord
from science_tool.commons.config import resolve_commons_root
from science_tool.commons.errors import (
    CommonsEntityError,
    CommonsLayoutError,
    CommonsRootNotFoundError,
)

_TYPE_DIRS = ("datasets", "papers", "topics", "themes")
_PROMOTED_KEYS = frozenset({"id", "type", "title", "status", "aliases", "related"})


def build_commons_inventory() -> InventoryPayload:
    """Return the inventory_v2 payload describing the whole commons store."""
    root = resolve_commons_root()
    if not root.is_dir():
        raise CommonsRootNotFoundError(root)

    entities: list[InventoryEntity] = []
    aliases: list[InventoryAlias] = []
    warnings: list[InventoryWarning] = []

    for item in CommonsEntityAdapter(root).scan():
        if isinstance(item, CommonsEntityError):
            # scan() yields CommonsEntityError for both schema/parse failures
            # and (per design §3.6) a dataset missing datapackage.yaml — the
            # latter carries a CommonsLayoutError cause.
            code = (
                "commons-datapackage-invalid"
                if isinstance(item.cause, CommonsLayoutError)
                else "commons-entity-invalid"
            )
            warnings.append(
                InventoryWarning(
                    code=code,
                    severity="error",
                    message=str(item),
                    path=str(item.path),
                    canonical_id=item.canonical_id,
                )
            )
            continue
        entity, entity_aliases = _entity_from_record(item, warnings)
        entities.append(entity)
        aliases.extend(entity_aliases)

    payload = InventoryPayload(
        generated_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        project_id="commons",
        project_path=str(root),
        entities=sorted(entities, key=lambda e: e.id),
        aliases=sorted(aliases, key=lambda a: a.alias),
        overlays=[],
        warnings=warnings,
        watch_paths=[name for name in _TYPE_DIRS if (root / name).is_dir()],
    )
    return finalize_inventory_payload(payload)


def _entity_from_record(
    record: CommonsEntityRecord, warnings: list[InventoryWarning]
) -> tuple[InventoryEntity, list[InventoryAlias]]:
    frontmatter = record.frontmatter
    related = [
        InventoryReference(relation="related", target_id=str(target))
        for target in frontmatter.get("related", [])
        if target
    ]
    entity_aliases = [str(alias) for alias in frontmatter.get("aliases", [])]
    data = {
        key: value
        for key, value in frontmatter.items()
        if key not in _PROMOTED_KEYS
    }
    entity = InventoryEntity(
        id=record.canonical_id,
        kind=record.type,
        local_id=record.slug,
        title=frontmatter.get("title"),
        status=frontmatter.get("status"),
        scope="cross-project",
        registration_state="unknown",
        source=InventorySourceLocation(
            adapter="commons-entity", path=str(record.body_path)
        ),
        aliases=entity_aliases,
        related=related,
        data=data,
    )
    aliases = [
        InventoryAlias(alias=alias, canonical_id=record.canonical_id)
        for alias in entity_aliases
    ]
    return entity, aliases
```

Note: `warnings` is passed into `_entity_from_record` because Task 7 adds
dataset-resource projection there, which can append a warning.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_commons_inventory.py -v`
Expected: PASS — all four tests.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/commons/inventory.py science/tests/test_commons_inventory.py
git commit -m "feat(commons): build_commons_inventory entity projection"
```

---

### Task 7: `build_commons_inventory()` — dataset resource projection

Project dataset resources into `data["resources"]`. A `read_datapackage` failure becomes a `commons-datapackage-invalid` warning; the entity is still emitted, just without `data["resources"]`.

**Files:**
- Modify: `science/src/science_tool/commons/inventory.py` (`_entity_from_record`)
- Modify: `science/tests/fixtures/commons/valid/datasets/cath-domains/datapackage.yaml` (add `mediatype` to the resource)
- Test: `science/tests/test_commons_inventory.py`

- [ ] **Step 1: Add `mediatype` to the cath-domains fixture datapackage**

Edit `science/tests/fixtures/commons/valid/datasets/cath-domains/datapackage.yaml` — add a `mediatype` line to the single resource so the test can assert a non-`None` mediatype. The file becomes:

```yaml
name: cath-domains
profile: "data-package"
resources:
  - name: cath_domains
    path: cath_domains.parquet
    hash: "sha256:0000000000000000000000000000000000000000000000000000000000000000"
    bytes: 4521339201
    format: "parquet"
    mediatype: "application/vnd.apache.parquet"
```

- [ ] **Step 2: Write the failing tests**

Append to `science/tests/test_commons_inventory.py`:

```python
def test_build_commons_inventory_projects_dataset_resources(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _make_store(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))
    payload = build_commons_inventory()

    cath = next(e for e in payload.entities if e.id == "dataset:cath-domains")
    assert cath.data["resources"] == [
        {
            "path": "cath_domains.parquet",
            "hash": "sha256:" + "0" * 64,
            "bytes": 4521339201,
            "format": "parquet",
            "mediatype": "application/vnd.apache.parquet",
        }
    ]
    # rnaseq-example's fixture datapackage has no mediatype -> None.
    rnaseq = next(e for e in payload.entities if e.id == "dataset:rnaseq-example")
    assert rnaseq.data["resources"][0]["mediatype"] is None
    # Non-dataset entities have no resources key.
    paper = next(e for e in payload.entities if e.id == "paper:Adams2025")
    assert "resources" not in paper.data


def test_build_commons_inventory_warns_on_malformed_datapackage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _make_store(tmp_path)
    (root / "datasets" / "cath-domains" / "datapackage.yaml").write_text(
        "resources: [unclosed\n", encoding="utf-8"
    )
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))
    payload = build_commons_inventory()

    dp_warnings = [
        w for w in payload.warnings if w.code == "commons-datapackage-invalid"
    ]
    assert len(dp_warnings) == 1
    assert dp_warnings[0].canonical_id == "dataset:cath-domains"
    # The entity is still emitted, just without data["resources"].
    cath = next(e for e in payload.entities if e.id == "dataset:cath-domains")
    assert "resources" not in cath.data
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run pytest tests/test_commons_inventory.py -k "projects_dataset_resources or malformed_datapackage" -v`
Expected: FAIL — `_entity_from_record` does not populate `data["resources"]`.

- [ ] **Step 4: Add resource projection to `_entity_from_record`**

In `science/src/science_tool/commons/inventory.py`, add the import:

```python
from science_tool.commons.datapackage import read_datapackage
from science_tool.commons.errors import (
    CommonsDatapackageError,
    CommonsEntityError,
    CommonsLayoutError,
    CommonsRootNotFoundError,
)
```

(`CommonsDatapackageError` is the only new name; the others were already imported — replace the existing `from science_tool.commons.errors import (...)` block with the four-name version above, and add the `read_datapackage` import line next to it.)

Then in `_entity_from_record`, insert the resource-projection block **after** the `data = {...}` dict comprehension and **before** the `entity = InventoryEntity(...)` construction:

```python
    if record.type == "dataset" and record.datapackage_path is not None:
        try:
            descriptor = read_datapackage(record.datapackage_path)
        except CommonsDatapackageError as exc:
            warnings.append(
                InventoryWarning(
                    code="commons-datapackage-invalid",
                    severity="error",
                    message=str(exc),
                    path=str(record.datapackage_path),
                    canonical_id=record.canonical_id,
                )
            )
        else:
            data["resources"] = [
                {
                    "path": resource.path,
                    "hash": resource.hash,
                    "bytes": resource.bytes,
                    "format": resource.format,
                    "mediatype": resource.mediatype,
                }
                for resource in descriptor.resources
            ]
```

- [ ] **Step 5: Run the full commons inventory test file to verify it passes**

Run: `uv run pytest tests/test_commons_inventory.py -v`
Expected: PASS — all six tests (Tasks 6 + 7).

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/commons/inventory.py science/tests/test_commons_inventory.py science/tests/fixtures/commons/valid/datasets/cath-domains/datapackage.yaml
git commit -m "feat(commons): project dataset resources into commons inventory"
```

---

### Task 8: Project builder — `schema_version` parameter + v2 payload

Add the `schema_version` parameter to `build_inventory`. The v1 path is byte-for-byte unchanged; the v2 path emits an `inventory_v2.InventoryPayload` (with `overlays=[]` for now — Task 9 fills it in). The function default flips to `"2"`, so existing v1 tests are updated to pass `schema_version="1"` explicitly.

**Files:**
- Modify: `science/src/science_tool/entities_inventory.py:1-22` (imports), `:46-103` (`build_inventory`)
- Test: `science/tests/test_entities_inventory.py`

- [ ] **Step 1: Update existing v1 tests to pin `schema_version="1"`**

In `science/tests/test_entities_inventory.py`, every call to `build_inventory(project)` or `build_inventory(project, ...)` in the **existing** tests must pass `schema_version="1"`. There are five call sites — update each:

- `test_build_inventory_includes_entities_aliases_dag_candidates_and_watch_paths` (line 51): `inventory = build_inventory(project, schema_version="1")`
- `test_build_inventory_metadata_uses_config_path_and_project_name_default` (line 79): `inventory = build_inventory(project, schema_version="1")`
- `test_build_inventory_metadata_preserves_project_dates` (line 101): `inventory = build_inventory(project, schema_version="1")`
- `test_build_inventory_metadata_without_science_yaml_uses_project_root_name` (line 112): `inventory = build_inventory(project, schema_version="1")`
- `test_build_inventory_preserves_task_dsl_type_in_data` (line 136): `inventory = build_inventory(project, schema_version="1")`
- `test_build_inventory_fails_when_entity_source_adapter_mapping_is_missing` (line 161): `build_inventory(project, schema_version="1")`
- `test_build_inventory_promotes_targets_without_duplicating_them_in_data` (line 216): `inventory = build_inventory(project, schema_version="1")`

(That is seven call sites across the file — update all of them. They keep asserting v1 behavior.)

- [ ] **Step 2: Write the failing v2 test**

Append to `science/tests/test_entities_inventory.py`:

```python
def test_build_inventory_v2_returns_v2_payload_with_empty_overlays(tmp_path) -> None:
    from science_model.contracts.inventory_v2 import (
        InventoryPayload as InventoryPayloadV2,
    )

    project = tmp_path / "project"
    (project / "doc").mkdir(parents=True)
    (project / "science.yaml").write_text("id: v2-project\n", encoding="utf-8")
    (project / "doc" / "finding.md").write_text(
        "---\nkind: finding\nid: finding:f001\ntitle: Finding\n---\n",
        encoding="utf-8",
    )

    inventory = build_inventory(project, schema_version="2")

    assert isinstance(inventory, InventoryPayloadV2)
    assert inventory.schema_version == "2"
    assert inventory.project_id == "v2-project"
    assert inventory.overlays == []
    assert [e.id for e in inventory.entities] == ["finding:f001"]
    assert inventory.content_hash
    assert inventory.audit_hash


def test_build_inventory_defaults_to_v2(tmp_path) -> None:
    project = tmp_path / "project"
    (project / "doc").mkdir(parents=True)
    (project / "science.yaml").write_text("id: default-project\n", encoding="utf-8")

    inventory = build_inventory(project)

    assert inventory.schema_version == "2"


def test_build_inventory_rejects_unknown_schema_version_before_loading(
    tmp_path, monkeypatch
) -> None:
    project = tmp_path / "project"
    project.mkdir()

    def _fail(_project_root):
        raise AssertionError(
            "load_project_sources must not run for a bad schema_version"
        )

    monkeypatch.setattr(entities_inventory, "load_project_sources", _fail)

    # The guard at the top of build_inventory raises ValueError before any
    # project filesystem work — so the monkeypatched _fail is never reached.
    with pytest.raises(ValueError, match="schema_version"):
        build_inventory(project, schema_version="3")
```

`pytest` and `entities_inventory` are already imported at the top of `test_entities_inventory.py`.

- [ ] **Step 3: Run the tests to verify the new ones fail**

Run: `uv run pytest tests/test_entities_inventory.py -k "v2 or defaults_to_v2 or unknown_schema_version" -v`
Expected: FAIL — `build_inventory` does not accept `schema_version` and returns a v1 payload.

- [ ] **Step 4: Update `build_inventory` imports and signature**

In `science/src/science_tool/entities_inventory.py`, the current import (lines 9-18) is:

```python
from science_model.contracts.inventory_v1 import (
    InventoryAlias,
    InventoryEntity,
    InventoryPayload,
    InventoryProjectMetadata,
    InventoryWarning,
    InventoryReference,
    InventorySourceLocation,
    finalize_inventory_payload,
)
```

Replace it with:

```python
from science_model.contracts import inventory_v2
from science_model.contracts.inventory_v1 import (
    InventoryAlias,
    InventoryEntity,
    InventoryPayload,
    InventoryProjectMetadata,
    InventoryWarning,
    InventoryReference,
    InventorySourceLocation,
    finalize_inventory_payload,
)
```

`Literal` is already imported at the top of the file (`from typing import Any, Literal` on line 5) — no typing-import change is needed.

- [ ] **Step 5: Branch `build_inventory` on `schema_version`**

In `science/src/science_tool/entities_inventory.py`, replace the `build_inventory` signature and its final payload-assembly block. The current function (lines 46-103) ends with:

```python
    payload = InventoryPayload(
        generated_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        project_id=project_metadata.id,
        project_path=project_root.as_posix(),
        project=project_metadata,
        entities=entities,
        aliases=sorted(aliases, key=lambda item: item.alias),
        graph_addresses=dag_records.graph_addresses,
        finding_candidates=dag_records.finding_candidates,
        warnings=warnings,
        watch_paths=_watch_paths(project_root),
    )
    return finalize_inventory_payload(payload)
```

Change the signature **and add the schema-version guard as the very first
statements of the function body** — before `project_root = project_root.resolve()`
and `load_project_sources(...)`, so a bad value fails immediately without doing
any project filesystem work. The current function head (lines 46-48) is:

```python
def build_inventory(project_root: Path) -> InventoryPayload:
    project_root = project_root.resolve()
    sources = load_project_sources(project_root)
```

Replace it with:

```python
def build_inventory(
    project_root: Path, schema_version: Literal["1", "2"] = "2"
) -> InventoryPayload | inventory_v2.InventoryPayload:
    if schema_version not in ("1", "2"):
        raise ValueError(
            f"unsupported schema_version {schema_version!r}; expected '1' or '2'"
        )
    project_root = project_root.resolve()
    sources = load_project_sources(project_root)
```

This is the "fail early / no silent fallbacks" rule: the CLI's
`click.Choice(["1", "2"])` blocks bad values at the command boundary, but a
direct Python API caller must get an immediate `ValueError` — not a payload, and
not an unrelated failure from `load_project_sources`.

Then replace the final payload-assembly block (the `payload = InventoryPayload(...)`
through `return finalize_inventory_payload(payload)` shown above) with:

```python
    generated_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    sorted_aliases = sorted(aliases, key=lambda item: item.alias)
    watch_paths = _watch_paths(project_root)

    if schema_version == "1":
        payload = InventoryPayload(
            generated_at=generated_at,
            project_id=project_metadata.id,
            project_path=project_root.as_posix(),
            project=project_metadata,
            entities=entities,
            aliases=sorted_aliases,
            graph_addresses=dag_records.graph_addresses,
            finding_candidates=dag_records.finding_candidates,
            warnings=warnings,
            watch_paths=watch_paths,
        )
        return finalize_inventory_payload(payload)

    payload_v2 = inventory_v2.InventoryPayload(
        generated_at=generated_at,
        project_id=project_metadata.id,
        project_path=project_root.as_posix(),
        project=project_metadata,
        entities=entities,
        aliases=sorted_aliases,
        graph_addresses=dag_records.graph_addresses,
        finding_candidates=dag_records.finding_candidates,
        warnings=warnings,
        watch_paths=watch_paths,
        overlays=[],
    )
    return inventory_v2.finalize_inventory_payload(payload_v2)
```

The `schema_version` value is already validated by the top-of-function guard, so
the tail only needs the `"1"` vs `"2"` branch — no second `ValueError` here.

The v1 `InventoryEntity` / `InventoryAlias` / `InventoryProjectMetadata` / `InventoryWarning` objects already built above are reused as-is: `inventory_v2` imports those exact classes from `inventory_v1`, so they are type-compatible with `inventory_v2.InventoryPayload`.

- [ ] **Step 6: Run the full entities_inventory test file to verify it passes**

Run: `uv run pytest tests/test_entities_inventory.py -v`
Expected: PASS — the seven updated v1 tests plus the two new v2 tests.

- [ ] **Step 7: Commit**

```bash
git add science/src/science_tool/entities_inventory.py science/tests/test_entities_inventory.py
git commit -m "feat(entities): build_inventory schema_version param + v2 payload"
```

---

### Task 9: Project builder v2 — overlay scanning into `overlays[]`

Fill in the v2 path's `overlays[]` by scanning the project's `doc/` overlay files with `OverlayAdapter`, splitting each overlay's frontmatter fields into `project_only_fields` / `append_fields` via `read_overlay_merge_policy()`, and turning `OverlayValidationError`s into warnings.

**Files:**
- Modify: `science/src/science_tool/entities_inventory.py` (imports + a new `_scan_overlays` helper + v2 branch)
- Test: `science/tests/test_entities_inventory.py`

- [ ] **Step 1: Write the failing tests**

Append to `science/tests/test_entities_inventory.py`:

```python
def test_build_inventory_v2_scans_project_overlays(tmp_path) -> None:
    project = tmp_path / "project"
    (project / "doc" / "papers").mkdir(parents=True)
    (project / "science.yaml").write_text("id: overlay-project\n", encoding="utf-8")
    (project / "doc" / "papers" / "Adams2025.md").write_text(
        "---\n"
        'id: "paper:Adams2025"\n'
        'overlay_of: "paper:Adams2025"\n'
        'relevance: "H2 — supports the homology-split argument"\n'
        'hypothesis_links: ["H2", "H4"]\n'
        'project_tags: ["high-priority"]\n'
        'tags: ["overlay-added"]\n'
        "---\n\n## Project-Specific Notes\n\nText.\n",
        encoding="utf-8",
    )

    inventory = build_inventory(project, schema_version="2")

    assert len(inventory.overlays) == 1
    overlay = inventory.overlays[0]
    assert overlay.overlay_of == "paper:Adams2025"
    assert overlay.project_id == "overlay-project"
    assert overlay.source.adapter == "commons-overlay"
    # `tags` carries science:merge: append on the overlay schema.
    assert overlay.append_fields == {"tags": ["overlay-added"]}
    # relevance / hypothesis_links / project_tags are project-only.
    assert overlay.project_only_fields == {
        "relevance": "H2 — supports the homology-split argument",
        "hypothesis_links": ["H2", "H4"],
        "project_tags": ["high-priority"],
    }
    assert overlay.body_sections == ["\n## Project-Specific Notes\n\nText.\n"]


def test_build_inventory_v2_overlay_validation_error_becomes_warning(tmp_path) -> None:
    project = tmp_path / "project"
    (project / "doc" / "papers").mkdir(parents=True)
    (project / "science.yaml").write_text("id: broken-overlay\n", encoding="utf-8")
    # overlay_of contradicts the path-derived canonical id paper:Adams2025.
    (project / "doc" / "papers" / "Adams2025.md").write_text(
        "---\n"
        'id: "paper:Wrong2025"\n'
        'overlay_of: "paper:Wrong2025"\n'
        'relevance: "mismatch"\n'
        "---\n\n## Notes\n",
        encoding="utf-8",
    )

    inventory = build_inventory(project, schema_version="2")

    assert inventory.overlays == []
    overlay_warnings = [w for w in inventory.warnings if w.code == "overlay-invalid"]
    assert len(overlay_warnings) == 1
    assert overlay_warnings[0].path.endswith("doc/papers/Adams2025.md")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_entities_inventory.py -k "scans_project_overlays or overlay_validation_error" -v`
Expected: FAIL — the v2 path always produces `overlays=[]`.

- [ ] **Step 3: Add the overlay-scanning imports**

In `science/src/science_tool/entities_inventory.py`, add to the imports near the top (after the existing `from science_tool.graph.sources import load_project_sources` line):

```python
from science_model.entity_schema import MergePolicy, read_overlay_merge_policy

from science_tool.commons.errors import OverlayValidationError
from science_tool.commons.overlay import OverlayAdapter
```

(`science_model.entity_schema` already exports `MergePolicy` and `read_overlay_merge_policy` — confirmed by `science_tool/commons/overlay.py`, which imports them from there.)

- [ ] **Step 4: Add the `_scan_overlays` helper**

In `science/src/science_tool/entities_inventory.py`, add this function (place it near the other module-level helpers, e.g. after `_optional_str`):

```python
_SKIP_OVERLAY_FIELDS = frozenset(
    {"id", "overlay_of", "pin_version", "pin_effective_version"}
)


def _scan_overlays(
    project_root: Path, project_id: str, warnings: list[InventoryWarning]
) -> list[inventory_v2.InventoryOverlay]:
    """Scan the project's doc/ overlay files into InventoryOverlay records.

    Overlay-schema failures become `overlay-invalid` warnings. Fields are split
    project-only vs append per the overlay schema's science:merge annotations.
    """
    overlay_policy = read_overlay_merge_policy()
    overlays: list[inventory_v2.InventoryOverlay] = []
    for item in OverlayAdapter(project_root, project_id).scan():
        if isinstance(item, OverlayValidationError):
            warnings.append(
                InventoryWarning(
                    code="overlay-invalid",
                    severity="error",
                    message=str(item),
                    path=str(item.overlay_path),
                    canonical_id=item.canonical_id,
                )
            )
            continue
        project_only: dict[str, Any] = {}
        append: dict[str, Any] = {}
        for field, value in item.frontmatter.items():
            if field in _SKIP_OVERLAY_FIELDS:
                continue
            if overlay_policy.get(field) is MergePolicy.APPEND:
                append[field] = value
            else:
                project_only[field] = value
        overlays.append(
            inventory_v2.InventoryOverlay(
                overlay_of=item.canonical_id,
                project_id=project_id,
                source=InventorySourceLocation(
                    adapter="commons-overlay", path=str(item.overlay_path)
                ),
                pin_version=item.pin_version,
                pin_effective_version=item.pin_effective_version,
                project_only_fields=project_only,
                append_fields=append,
                body_sections=[item.body] if item.body.strip() else [],
            )
        )
    return sorted(overlays, key=lambda o: (o.overlay_of, o.project_id))
```

- [ ] **Step 5: Wire `_scan_overlays` into the v2 branch**

In `science/src/science_tool/entities_inventory.py`, in the v2 branch of `build_inventory` (added in Task 8), change the `overlays=[]` argument so the v2 payload uses the scanned overlays. Replace:

```python
    payload_v2 = inventory_v2.InventoryPayload(
        generated_at=generated_at,
        project_id=project_metadata.id,
        project_path=project_root.as_posix(),
        project=project_metadata,
        entities=entities,
        aliases=sorted_aliases,
        graph_addresses=dag_records.graph_addresses,
        finding_candidates=dag_records.finding_candidates,
        warnings=warnings,
        watch_paths=watch_paths,
        overlays=[],
    )
    return inventory_v2.finalize_inventory_payload(payload_v2)
```

with:

```python
    overlays = _scan_overlays(project_root, project_metadata.id, warnings)
    payload_v2 = inventory_v2.InventoryPayload(
        generated_at=generated_at,
        project_id=project_metadata.id,
        project_path=project_root.as_posix(),
        project=project_metadata,
        entities=entities,
        aliases=sorted_aliases,
        graph_addresses=dag_records.graph_addresses,
        finding_candidates=dag_records.finding_candidates,
        warnings=warnings,
        watch_paths=watch_paths,
        overlays=overlays,
    )
    return inventory_v2.finalize_inventory_payload(payload_v2)
```

`_scan_overlays` appends to the same `warnings` list before the payload is
built, so overlay-invalid warnings are included.

- [ ] **Step 6: Run the full entities_inventory test file to verify it passes**

Run: `uv run pytest tests/test_entities_inventory.py -v`
Expected: PASS — all tests, including the two new overlay tests. Note that `test_build_inventory_v2_returns_v2_payload_with_empty_overlays` (Task 8) still passes because its project has no `doc/papers/` overlay files, so `_scan_overlays` returns `[]`.

- [ ] **Step 7: Commit**

```bash
git add science/src/science_tool/entities_inventory.py science/tests/test_entities_inventory.py
git commit -m "feat(entities): scan project overlays into inventory_v2 overlays[]"
```

---

### Task 10: CLI — `science commons inventory`

Add the `science commons inventory` subcommand that emits the commons inventory_v2 payload.

**Files:**
- Modify: `science/src/science_tool/commons/cli.py` (imports + new command)
- Test: `science/tests/test_commons_cli.py`

- [ ] **Step 1: Write the failing tests**

Append to `science/tests/test_commons_cli.py`:

```python
def test_commons_inventory_to_stdout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _seeded_store(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))
    runner = CliRunner()
    result = runner.invoke(commons_group, ["inventory"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["schema_version"] == "2"
    assert payload["project_id"] == "commons"
    assert {e["id"] for e in payload["entities"]} == {
        "dataset:cath-domains",
        "dataset:rnaseq-example",
        "paper:Adams2025",
        "topic:single-cell-foundation-models",
        "theme:research-hygiene",
    }


def test_commons_inventory_to_output_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _seeded_store(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))
    output = tmp_path / "commons-inventory.json"
    runner = CliRunner()
    result = runner.invoke(commons_group, ["inventory", "--output", str(output)])
    assert result.exit_code == 0, result.output
    assert result.output == ""
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["project_id"] == "commons"


def test_commons_inventory_missing_root_exits_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(tmp_path / "nope"))
    runner = CliRunner()
    result = runner.invoke(commons_group, ["inventory"])
    assert result.exit_code == 1
    assert "commons store not found" in result.output
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_commons_cli.py -k commons_inventory -v`
Expected: FAIL — there is no `inventory` subcommand on `commons_group`.

- [ ] **Step 3: Add the `inventory` command**

In `science/src/science_tool/commons/cli.py`, add the import (next to the other commons-submodule imports, e.g. after the `from science_tool.commons.errors import ...` line):

```python
from science_tool.commons.inventory import build_commons_inventory
```

Then add this command (place it after `validate_cmd`, before the `data` group):

```python
@commons_group.command("inventory")
@click.option(
    "--output",
    type=click.Path(path_type=Path),
    default=None,
    help="Write the payload to FILE instead of stdout.",
)
def inventory_cmd(output: Path | None) -> None:
    """Emit the inventory_v2 payload for the whole commons store."""
    try:
        payload = build_commons_inventory()
    except CommonsError as exc:
        raise click.ClickException(str(exc)) from exc
    rendered = payload.model_dump_json(indent=2) + "\n"
    if output is None:
        click.echo(rendered, nl=False)
    else:
        output.write_text(rendered, encoding="utf-8")
```

`CommonsError` and `Path` are already imported in `cli.py`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_commons_cli.py -k commons_inventory -v`
Expected: PASS — all three tests.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/commons/cli.py science/tests/test_commons_cli.py
git commit -m "feat(commons): science commons inventory CLI command"
```

---

### Task 11: CLI — `science entities inventory --schema-version`

Add the `--schema-version` option to `science entities inventory` (default `2`) and update the two existing CLI tests that validate against the v1 contract.

**Files:**
- Modify: `science/src/science_tool/cli.py:224-235` (`entities_inventory_command`)
- Test: `science/tests/test_entities_cli.py:259-298`

- [ ] **Step 1: Update the two existing CLI inventory tests**

In `science/tests/test_entities_cli.py`:

Change the import on line 11 from:
```python
from science_model.contracts.inventory_v1 import InventoryPayload
```
to:
```python
from science_model.contracts.inventory_v1 import InventoryPayload
from science_model.contracts.inventory_v2 import InventoryPayload as InventoryPayloadV2
```

In `test_entities_inventory_cli_outputs_contract_json` (lines 259-274), the command now defaults to v2. Replace the assertion block (lines 271-274):
```python
    assert result.exit_code == 0, result.output
    payload = InventoryPayload.model_validate_json(result.output)
    assert payload.project_id == "cli-project"
    assert payload.entities[0].id == "finding:f001"
```
with:
```python
    assert result.exit_code == 0, result.output
    payload = InventoryPayloadV2.model_validate_json(result.output)
    assert payload.schema_version == "2"
    assert payload.project_id == "cli-project"
    assert payload.entities[0].id == "finding:f001"
```

In `test_entities_inventory_cli_writes_contract_json_to_output_file` (lines 277-297), replace the final assertion block (lines 293-297):
```python
    assert result.exit_code == 0, result.output
    assert result.output == ""
    payload = InventoryPayload.model_validate_json(output.read_text(encoding="utf-8"))
    assert payload.project_id == "cli-output-project"
    assert payload.entities[0].id == "finding:f001"
```
with:
```python
    assert result.exit_code == 0, result.output
    assert result.output == ""
    payload = InventoryPayloadV2.model_validate_json(
        output.read_text(encoding="utf-8")
    )
    assert payload.project_id == "cli-output-project"
    assert payload.entities[0].id == "finding:f001"
```

- [ ] **Step 2: Write the failing test for `--schema-version 1`**

Append to `science/tests/test_entities_cli.py`:

```python
def test_entities_inventory_cli_schema_version_1_emits_v1(tmp_path) -> None:
    project = tmp_path / "project"
    (project / "doc").mkdir(parents=True)
    (project / "science.yaml").write_text("id: v1-cli-project\n", encoding="utf-8")
    (project / "doc" / "finding.md").write_text(
        "---\nkind: finding\nid: finding:f001\ntitle: Finding\n---\n",
        encoding="utf-8",
    )
    runner = CliRunner()

    result = runner.invoke(
        main,
        [
            "entities",
            "inventory",
            "--project",
            str(project),
            "--format",
            "json",
            "--schema-version",
            "1",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = InventoryPayload.model_validate_json(result.output)
    assert payload.schema_version == "1"
    assert payload.project_id == "v1-cli-project"
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run pytest tests/test_entities_cli.py -k "inventory" -v`
Expected: FAIL — the updated tests expect v2 output / a `--schema-version` option, but the command still emits v1 and rejects the unknown option.

- [ ] **Step 4: Add the `--schema-version` option**

In `science/src/science_tool/cli.py`, replace `entities_inventory_command` (lines 224-235):

```python
@entities_group.command("inventory")
@click.option("--project", "project_path", type=click.Path(path_type=Path), default=Path.cwd())
@click.option("--format", "output_format", type=click.Choice(["json"]), default="json")
@click.option("--output", type=click.Path(path_type=Path), default=None)
def entities_inventory_command(project_path: Path, output_format: str, output: Path | None) -> None:
    """Emit the versioned Science entity inventory for a project."""
    inventory = build_inventory(project_path)
    rendered = inventory.model_dump_json(indent=2) + "\n"
    if output is None:
        click.echo(rendered, nl=False)
    else:
        output.write_text(rendered, encoding="utf-8")
```

with:

```python
@entities_group.command("inventory")
@click.option("--project", "project_path", type=click.Path(path_type=Path), default=Path.cwd())
@click.option("--format", "output_format", type=click.Choice(["json"]), default="json")
@click.option("--output", type=click.Path(path_type=Path), default=None)
@click.option(
    "--schema-version",
    type=click.Choice(["1", "2"]),
    default="2",
    help="Inventory contract version to emit (default: 2).",
)
def entities_inventory_command(
    project_path: Path,
    output_format: str,
    output: Path | None,
    schema_version: str,
) -> None:
    """Emit the versioned Science entity inventory for a project."""
    inventory = build_inventory(project_path, schema_version=schema_version)
    rendered = inventory.model_dump_json(indent=2) + "\n"
    if output is None:
        click.echo(rendered, nl=False)
    else:
        output.write_text(rendered, encoding="utf-8")
```

- [ ] **Step 5: Run the inventory CLI tests to verify they pass**

Run: `uv run pytest tests/test_entities_cli.py -k "inventory" -v`
Expected: PASS — the two updated tests plus the new `--schema-version 1` test.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/cli.py science/tests/test_entities_cli.py
git commit -m "feat(entities): entities inventory --schema-version flag"
```

---

### Task 12: Public API export

Export `build_commons_inventory` from the `commons` package.

**Files:**
- Modify: `science/src/science_tool/commons/__init__.py:61-64` (imports), `:66-109` (`__all__`)
- Test: `science/tests/test_commons_public_api.py`

- [ ] **Step 1: Update the public API test**

In `science/tests/test_commons_public_api.py`, add `"build_commons_inventory"` to the `expected` set — insert it after the `# Phase D1` block (after line 51, `"OverlayMergeError",`):

```python
        "OverlayMergeError",
        # Phase D2
        "build_commons_inventory",
    }
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_commons_public_api.py -v`
Expected: FAIL — `build_commons_inventory` is not exported from `science_tool.commons`.

- [ ] **Step 3: Add the import and `__all__` entry**

In `science/src/science_tool/commons/__init__.py`:

Add the import — insert after line 60 (the end of the `from science_tool.commons.overlay import (...)` block) and before `from science_tool.commons.query import CommonsQuery`:

```python
from science_tool.commons.inventory import build_commons_inventory
```

Add `"build_commons_inventory"` to the `__all__` list (keep it alphabetically ordered — it goes after `"ValidationReport"` and before `"commons_group"`):

```python
    "ValidationReport",
    "build_commons_inventory",
    "commons_group",
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/test_commons_public_api.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/commons/__init__.py science/tests/test_commons_public_api.py
git commit -m "feat(commons): export build_commons_inventory"
```

---

### Task 13: Full-suite verification

Confirm the whole `science` test suite and the `science/model` suite are green. No code changes expected; if a regression surfaces, fix it and commit.

**Files:** none (verification only)

- [ ] **Step 1: Run the model-package suite**

Run: `uv run pytest model/tests/ -q`
Expected: PASS — in particular `test_inventory_contract_v1.py` and `test_inventory_contract_v2.py`.

- [ ] **Step 2: Run the full `science` suite**

Run: `uv run pytest -q`
Expected: PASS — all tests, including the modified `test_commons_adapter.py`, `test_commons_validator.py`, `test_commons_datapackage.py`, `test_commons_inventory.py`, `test_commons_cli.py`, `test_commons_public_api.py`, `test_entities_inventory.py`, `test_entities_cli.py`.

- [ ] **Step 3: CLI smoke test**

Run:
```bash
uv run science commons inventory --output /tmp/d2-commons-inventory.json && head -c 200 /tmp/d2-commons-inventory.json
```
Expected: exits 0; the output begins with a JSON object whose `"schema_version"` is `"2"` and `"project_id"` is `"commons"`. (If no commons store is configured on the machine, this exits 1 with "commons store not found" — that is acceptable; the test suite already covers the success path with fixtures.)

- [ ] **Step 4: Commit any fixes**

If Steps 1-2 surfaced regressions and you fixed them, stage **only the files you
actually edited** (name them explicitly — do not use `git add -A` / `git add .`,
which can sweep in unrelated worktree changes):
```bash
git add <explicit/path/to/each/fixed/file> ...
git commit -m "fix(commons): address D2 full-suite regressions"
```
If no fixes were needed, this task makes no commit.

---

## Self-Review

**1. Spec coverage** — every design section maps to a task:
- §3.1 (standalone commons inventory, overlays on project payloads) → Tasks 6, 8, 9 (project payloads carry only `overlays[]`; commons entities only in `build_commons_inventory`).
- §3.6 (walk-safe `scan()`) → Task 1.
- §4.1-4.2 (`inventory_v2` imports, `InventoryOverlay`) → Task 3.
- §4.3 (v2 `InventoryPayload`) → Task 4.
- §4.4 (hash machinery) → Task 5.
- §5 (datapackage reader extension) → Task 2.
- §6 (`build_commons_inventory` entity projection) → Task 6.
- §6 step 3 (dataset resource projection) → Task 7.
- §7 (project builder v2 + `_scan_overlays`) → Tasks 8, 9.
- §8.1 (`science commons inventory`) → Task 10.
- §8.2 (`entities inventory --schema-version`) → Task 11.
- §8.3 (public API export) → Task 12.
- §9 (error handling — warning codes `commons-entity-invalid`, `commons-datapackage-invalid`, `overlay-invalid`) → Tasks 6, 7, 9.
- §10 (testing) → test steps in every task + Task 13.

**2. Placeholder scan** — no "TBD"/"TODO"/"handle edge cases"/"similar to Task N". Every code step has complete code; every test step has full test bodies; every run step has an exact command and expected result.

**3. Type consistency** — `build_commons_inventory() -> InventoryPayload` (v2) consistent across Tasks 6, 7, 10, 12. `build_inventory(project_root, schema_version="2")` consistent across Tasks 8, 9, 11. `InventoryOverlay` field names (`overlay_of`, `project_id`, `source`, `pin_version`, `pin_effective_version`, `project_only_fields`, `append_fields`, `body_sections`) identical in Tasks 3, 4, 5 (contract), 9 (producer), and the test assertions. Warning codes (`commons-entity-invalid`, `commons-datapackage-invalid`, `overlay-invalid`) consistent between Tasks 6/7/9 and their tests. `_entity_from_record(record, warnings)` signature defined in Task 6 and extended (not re-signatured) in Task 7. `_scan_overlays(project_root, project_id, warnings)` defined and wired in Task 9. Task 1 keeps `scan()`'s return type `Iterator[CommonsEntityRecord | CommonsEntityError]` unchanged — the missing-datapackage case is a `CommonsEntityError` with a `CommonsLayoutError` `cause`, so `RegistryBuilder`, `CommonsValidator`, and the `--json` CLI paths need no change; Task 6 discriminates the warning code via `isinstance(item.cause, CommonsLayoutError)`. `build_inventory` raises `ValueError` on any `schema_version` other than `"1"`/`"2"` (Task 8).

**Deviations from spec:** none.

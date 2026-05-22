# Inventory v1 Retirement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove `inventory_v1` from Science runtime inventory paths while preserving the historical v1 contract module for explicit tests and any archival consumers.

**Architecture:** Move shared inventory model primitives and hash helpers into a version-neutral contract module, then make `inventory_v2` and Science runtime producers depend on that module instead of `inventory_v1`. Keep `inventory_v1` as a thin schema-version-1 contract that imports shared primitives, but stop exposing schema-version 1 through `science entities inventory`.

**Tech Stack:** Python 3.13, Pydantic 2, Click, pytest, uv.

---

## Current Runtime Gate

Run from `~/d/science/science`:

```bash
rg -n 'inventory_v1|--schema-version 1|schema_version: Literal\["1"\]' src model/src/science_model/contracts/inventory_v2.py ~/d/dashboard/backend ~/d/dashboard/tests 2>/dev/null
```

Expected before this plan: matches in Science runtime files:

- `science/model/src/science_model/contracts/inventory_v2.py`
- `science/src/science_tool/entities_inventory.py`
- `science/src/science_tool/dag/inventory.py`
- `science/src/science_tool/entity_identity.py`
- `science/src/science_tool/graph/health.py`

Expected after this plan: no matches in the runtime gate. Historical `inventory_v1` tests and `science_model.contracts.inventory_v1` remain outside this runtime gate.

## Status

Tasks 1 and 2 have landed. Runtime paths no longer import `inventory_v1`; the historical schema-version-1 contract remains available as `science_model.contracts.inventory_v1` for explicit contract tests and archival consumers.

## File Structure

- Create: `~/d/science/science/model/src/science_model/contracts/inventory_common.py`
- Modify: `~/d/science/science/model/src/science_model/contracts/inventory_v1.py`
- Modify: `~/d/science/science/model/src/science_model/contracts/inventory_v2.py`
- Modify: `~/d/science/science/src/science_tool/entities_inventory.py`
- Modify: `~/d/science/science/src/science_tool/dag/inventory.py`
- Modify: `~/d/science/science/src/science_tool/entity_identity.py`
- Modify: `~/d/science/science/src/science_tool/graph/health.py`
- Modify: `~/d/science/science/src/science_tool/cli.py`
- Modify tests in `~/d/science/science/tests/` and `~/d/science/science/model/tests/`

## Task 1: Split shared inventory contract primitives out of v1

**Files:**
- Create: `~/d/science/science/model/src/science_model/contracts/inventory_common.py`
- Modify: `~/d/science/science/model/src/science_model/contracts/inventory_v1.py`
- Modify: `~/d/science/science/model/src/science_model/contracts/inventory_v2.py`
- Test: `~/d/science/science/model/tests/test_inventory_contract_v1.py`
- Test: `~/d/science/science/model/tests/test_inventory_contract_v2.py`

- [x] **Step 1: Write or update a v2 contract test that fails while v2 imports v1**

Add an assertion to `science/model/tests/test_inventory_contract_v2.py`:

```python
def test_inventory_v2_contract_does_not_import_inventory_v1() -> None:
    import science_model.contracts.inventory_v2 as inventory_v2

    assert "science_model.contracts.inventory_v1" not in {
        value.__module__ for value in inventory_v2.__dict__.values() if hasattr(value, "__module__")
    }
```

Run:

```bash
cd ~/d/science/science
uv run --frozen pytest model/tests/test_inventory_contract_v2.py::test_inventory_v2_contract_does_not_import_inventory_v1 -q
```

Expected before implementation: fail because v2 re-exports classes imported from `inventory_v1`.

- [x] **Step 2: Create `inventory_common.py`**

Move these version-neutral definitions from `inventory_v1.py` to `inventory_common.py` without changing behavior:

- `WarningSeverity`
- `_InventoryContractModel`
- `InventorySourceLocation`
- `InventoryAlias`
- `InventoryReference`
- `InventoryGraphAddress`
- `InventoryFindingCandidate`
- `InventoryWarning`
- `InventoryProjectMetadata`
- `InventoryEntity`
- `canonical_json_bytes`
- `_validate_json_value`
- `_sort_key_with_canonical_tie_breaker`
- `_normalize_entity_for_content_hash`
- `_normalize_project_for_content_hash`
- `_normalize_finding_candidate_for_content_hash`

Keep the imports needed by those definitions in `inventory_common.py`.

- [x] **Step 3: Make v1 and v2 import shared primitives from common**

Update `inventory_v1.py` so it keeps only schema-version-1 payload and hash/finalize behavior, importing shared primitives and helpers from `inventory_common.py`.

Update `inventory_v2.py` so it imports shared primitives and helpers from `inventory_common.py`, not from `inventory_v1.py`. Update the module docstring so it no longer documents purposeful v1 imports.

- [x] **Step 4: Verify contract tests**

Run:

```bash
cd ~/d/science/science
uv run --frozen pytest model/tests/test_inventory_contract_v1.py model/tests/test_inventory_contract_v2.py -q
```

Expected: all selected contract tests pass.

- [x] **Step 5: Commit**

```bash
cd ~/d/science
git add science/model/src/science_model/contracts/inventory_common.py science/model/src/science_model/contracts/inventory_v1.py science/model/src/science_model/contracts/inventory_v2.py science/model/tests/test_inventory_contract_v2.py
git commit -m "refactor: split inventory contract common models"
```

## Task 2: Remove schema-version 1 from Science runtime inventory producers

**Files:**
- Modify: `~/d/science/science/src/science_tool/entities_inventory.py`
- Modify: `~/d/science/science/src/science_tool/dag/inventory.py`
- Modify: `~/d/science/science/src/science_tool/entity_identity.py`
- Modify: `~/d/science/science/src/science_tool/graph/health.py`
- Modify: `~/d/science/science/src/science_tool/cli.py`
- Test: `~/d/science/science/tests/test_entities_inventory.py`
- Test: `~/d/science/science/tests/test_entities_cli.py`

- [x] **Step 1: Write failing runtime gate tests**

Add or update tests so they expect:

- `build_inventory(project)` and `build_inventory(project, schema_version="2")` return `inventory_v2.InventoryPayload`.
- `build_inventory(project, schema_version="1")` raises `ValueError` before project loading.
- `science entities inventory --schema-version 1` exits non-zero because the option is no longer accepted.

Run the focused tests:

```bash
cd ~/d/science/science
uv run --frozen pytest tests/test_entities_inventory.py tests/test_entities_cli.py -q
```

Expected before implementation: fail on the schema-version 1 expectations.

- [x] **Step 2: Update runtime imports to version-neutral or v2 contract modules**

Use `science_model.contracts.inventory_common` for shared warning/source/graph-address/finding-candidate types in:

- `science/src/science_tool/dag/inventory.py`
- `science/src/science_tool/entity_identity.py`
- `science/src/science_tool/graph/health.py`

Use `science_model.contracts.inventory_v2` for the runtime inventory payload, entities, aliases, project metadata, references, source locations, warnings, and finalize helper in `science/src/science_tool/entities_inventory.py`.

- [x] **Step 3: Remove v1 payload construction from `build_inventory`**

In `science/src/science_tool/entities_inventory.py`:

- Keep `schema_version: str = "2"` only as a fail-fast guard for callers still passing a value.
- Raise `ValueError("unsupported schema_version ... expected '2'")` for anything other than `"2"` before loading project sources.
- Return only `inventory_v2.InventoryPayload`.
- Delete the v1 overload and the `if schema_version == "1"` payload branch.

- [x] **Step 4: Remove the CLI `--schema-version` option**

In `science/src/science_tool/cli.py`, remove the `--schema-version` Click option from `entities_inventory_command` and call `build_inventory(project_path)` directly.

- [x] **Step 5: Verify runtime gate and focused tests**

Run:

```bash
cd ~/d/science/science
rg -n 'inventory_v1|--schema-version 1|schema_version: Literal\["1"\]' src model/src/science_model/contracts/inventory_v2.py ~/d/dashboard/backend ~/d/dashboard/tests 2>/dev/null
uv run --frozen pytest tests/test_entities_inventory.py tests/test_entities_cli.py tests/dag/test_dag_inventory.py tests/test_entity_identity_health.py tests/test_health.py -q
```

Expected: the `rg` command prints no matches and exits 1; pytest exits 0.

- [x] **Step 6: Commit**

```bash
cd ~/d/science
git add science/src/science_tool/entities_inventory.py science/src/science_tool/dag/inventory.py science/src/science_tool/entity_identity.py science/src/science_tool/graph/health.py science/src/science_tool/cli.py science/tests/test_entities_inventory.py science/tests/test_entities_cli.py
git commit -m "fix: retire runtime inventory v1 producer"
```

## Task 3: Document retirement status and run final gate

**Files:**
- Modify: `~/d/science/science/docs/plans/2026-05-21-inventory-v1-retirement-plan.md`
- Modify if needed: `~/d/science/science/model/tests/test_inventory_contract_v1.py`
- Modify if needed: `~/d/science/science/model/tests/test_inventory_contract_v2.py`
- Modify if needed: `~/d/science/science/tests/test_entities_inventory.py`
- Modify if needed: `~/d/science/science/tests/test_entities_cli.py`

- [x] **Step 1: Update this plan status**

Mark completed task checkboxes after Tasks 1 and 2 land. Add a short status note that runtime paths no longer import `inventory_v1`, while the historical `inventory_v1` contract remains in `science_model.contracts.inventory_v1`.

- [x] **Step 2: Run the final verification gate**

Run:

```bash
cd ~/d/science/science
uv run --frozen pytest model/tests/test_inventory_contract_v1.py model/tests/test_inventory_contract_v2.py tests/test_entities_inventory.py tests/test_entities_cli.py tests/dag/test_dag_inventory.py tests/test_entity_identity_health.py tests/test_health.py -q
uv run --frozen ruff check src model/src tests model/tests
uv run --frozen pyright
rg -n 'inventory_v1|--schema-version 1|schema_version: Literal\["1"\]' src model/src/science_model/contracts/inventory_v2.py ~/d/dashboard/backend ~/d/dashboard/tests 2>/dev/null
```

Expected:

- pytest exits 0.
- ruff exits 0.
- pyright exits 0.
- runtime gate prints no matches and exits 1.

- [x] **Step 3: Commit plan and final test adjustments**

```bash
cd ~/d/science
git add science/docs/plans/2026-05-21-inventory-v1-retirement-plan.md science/model/tests/test_inventory_contract_v1.py science/model/tests/test_inventory_contract_v2.py science/tests/test_entities_inventory.py science/tests/test_entities_cli.py
git commit -m "docs: record inventory v1 retirement"
```

## Acceptance Criteria

- `science_model.contracts.inventory_v2` does not import `science_model.contracts.inventory_v1`.
- Science runtime files under `science/src` do not import `science_model.contracts.inventory_v1`.
- `science entities inventory` emits schema version 2 only.
- Calling `build_inventory(..., schema_version="1")` fails before project source loading.
- The runtime gate command returns no matches.
- Focused contract, entity inventory, DAG inventory, identity health, and health tests pass.

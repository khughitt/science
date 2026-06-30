# Schema Adoption Campaign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring ~14 durable-reference datapackages (data present) up to shape + structural invariants using the Spec 3 `infer-schema` scaffold, behind a real validation gate.

**Architecture:** One code prerequisite (Phase 0: a descriptor-targeting validation gate in `science_tool`), then a two-phase data-authoring runbook driven off a resumable manifest — Phase 1 machine shape (`infer-schema --write`), Phase 2 human/subagent structural meaning. The authored schemas land in-place in foreign git repos (no push) and are the precondition for Spec 4.

**Tech Stack:** Python 3 / Click / Pydantic v2 (Spec 1 models) / pandas + pyarrow (infer-schema) / pyyaml; pytest + `uv run`.

**Companion design:** `docs/plans/2026-06-14-schema-adoption-campaign-design.md` (read it first).

**Two kinds of task below.** Tasks 1–2 are TDD code in the science repo (`~/d/science/science`). Tasks 3–6 are a **data-authoring runbook**: they have no red-green cycle; their "test" is the Phase 0 validator passing and a human/manifest gate. Each runbook task states its exact commands and its done-criteria.

---

## File Structure

**Phase 0 (code, science repo `~/d/science/science`):**
- Modify `src/science_tool/datasets/validate.py` — add `DESCRIPTOR_NAMES`, `validate_package_descriptor()`, `_validate_resource_tables()` (file presence + schema↔table agreement), `_is_descriptor_target()`, `validate_path()`. Reuses `load_descriptor` / `observed_fields` / `diff_schema` (infer_schema) and the existing `_validate_resource_descriptors()`.
- Modify `src/science_tool/cli.py:3104-3106` — `datasets_validate` calls `validate_path()` instead of `validate_data_packages()`.
- Test `tests/test_datasets_validate.py` — add `TestDescriptorTargetValidation`.
- Test `tests/test_datasets_validate_cli.py` (create) — CLI exit-code behaviour.

**Campaign artifacts (science repo `docs/plans/`):**
- Create `docs/plans/2026-06-14-schema-adoption-campaign-manifest.md` — the resumable per-package × per-phase status table.

**Authored schemas (foreign repos, in-place, no push):** the `datapackage.{json,yaml}` files listed in the manifest. No new files there.

---

## Reusable snippets (referenced by runbook tasks)

**S1 — Commit protocol (foreign repo, run from inside the target repo's working tree):**

```bash
# $REPO = the data repo root (e.g. ~/d/cancer/cancer-types/multiple-myeloma)
cd "$REPO"
git rev-parse --show-toplevel                 # confirm we are in the intended repo
git branch --show-current                      # mm30 is Dropbox-synced & branch-volatile — eyeball this
git add <exact/path/to/datapackage.json>       # NAMED files only — never -A / .
git commit -m "<message>"                       # NO push; NO Co-Authored-By trailer
```

**S2 — Phase 0 validation gate, clean-package case (run from `~/d/science/science`):**

```bash
cd ~/d/science/science
uv run --quiet science datasets validate --path "<PKG_DIR>"   # PKG_DIR contains datapackage.{json,yaml}
echo "exit=$?"   # 0 = pass; non-zero = a real descriptor/consistency/file/schema failure
```

**S3 — Done-check for a partially-blocked package** (walker_2024, dgidb — where the gate
*will* fail on the manifest-recorded missing-data resources). Confirm every failure names
a known-blocked resource and nothing else:

```bash
cd ~/d/science/science
uv run --quiet science datasets validate --path "<PKG_DIR>" --format json > /tmp/val.json
python3 - <<'PY'
import json
rows = json.load(open("/tmp/val.json"))["rows"]
fails = [r for r in rows if r["status"] == "fail"]
print("\n".join(f'{r["check"]}: {r["details"]}' for r in fails) or "(no fails)")
PY
# Done iff every printed fail names a resource the manifest marks blocked-data; else fix.
```

---

### Task 1: Phase 0 — `validate_package_descriptor()` (exact-descriptor validation)

**Files:**
- Modify: `src/science_tool/datasets/validate.py`
- Test: `tests/test_datasets_validate.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_datasets_validate.py`:

```python
import yaml  # add to imports at top if not present

from science_tool.datasets.validate import validate_package_descriptor


def _pkg_dir(tmp_path: Path, pkg: dict, fmt: str = "json", csv: str = "a\n1\n") -> Path:
    """Write a self-contained package dir (descriptor + one data file) and return it."""
    d = tmp_path / "pkg"
    d.mkdir(parents=True, exist_ok=True)
    (d / "x.csv").write_text(csv)
    if fmt == "json":
        (d / "datapackage.json").write_text(json.dumps(pkg))
    else:
        (d / "datapackage.yaml").write_text(yaml.safe_dump(pkg))
    return d


class TestDescriptorTargetValidation:
    def test_valid_json_package_dir_passes(self, tmp_path: Path) -> None:
        pkg = {"name": "p", "resources": [
            {"name": "x", "path": "x.csv",
             "schema": {"fields": [{"name": "a", "type": "integer"}]}}]}
        results = validate_package_descriptor(_pkg_dir(tmp_path, pkg))
        assert results and all(r["status"] == "pass" for r in results)

    def test_valid_yaml_package_dir_passes(self, tmp_path: Path) -> None:
        pkg = {"name": "p", "resources": [
            {"name": "x", "path": "x.csv",
             "schema": {"fields": [{"name": "a", "type": "integer"}]}}]}
        results = validate_package_descriptor(_pkg_dir(tmp_path, pkg, fmt="yaml"))
        assert results and all(r["status"] == "pass" for r in results)

    def test_descriptor_file_path_accepted(self, tmp_path: Path) -> None:
        pkg = {"name": "p", "resources": [
            {"name": "x", "path": "x.csv",
             "schema": {"fields": [{"name": "a", "type": "integer"}]}}]}
        d = _pkg_dir(tmp_path, pkg)
        results = validate_package_descriptor(d / "datapackage.json")
        assert results and all(r["status"] == "pass" for r in results)

    def test_invalid_descriptor_fails(self, tmp_path: Path) -> None:
        # qa.low_variance on a string field violates Spec 1 (schema.py:94).
        pkg = {"name": "p", "resources": [
            {"name": "x", "path": "x.csv",
             "schema": {"fields": [{"name": "a", "type": "string", "qa": {"low_variance": True}}]}}]}
        results = validate_package_descriptor(_pkg_dir(tmp_path, pkg))
        assert any(r["status"] == "fail" for r in results)

    def test_consistency_failure_reported(self, tmp_path: Path) -> None:
        pkg = {"name": "p", "resources": [
            {"name": "edges", "path": "x.csv",
             "schema": {"fields": [{"name": "src"}],
                        "foreignKeys": [{"fields": "src",
                                         "reference": {"resource": "ghost", "fields": "id"}}]}}]}
        results = validate_package_descriptor(_pkg_dir(tmp_path, pkg))
        assert any("consistency" in r["check"] and r["status"] == "fail" for r in results)

    def test_no_descriptor_is_fail_not_silent(self, tmp_path: Path) -> None:
        empty = tmp_path / "empty"
        empty.mkdir()
        results = validate_package_descriptor(empty)
        assert results and all(r["status"] == "fail" for r in results)

    def test_no_resources_is_fail(self, tmp_path: Path) -> None:
        results = validate_package_descriptor(_pkg_dir(tmp_path, {"name": "p", "resources": []}))
        assert any(r["status"] == "fail" for r in results)

    # --- resource-level table checks (file presence + schema↔table agreement) ---

    def test_missing_data_file_fails(self, tmp_path: Path) -> None:
        d = tmp_path / "pkg"
        d.mkdir()
        pkg = {"name": "p", "resources": [
            {"name": "x", "path": "absent.csv",
             "schema": {"fields": [{"name": "a", "type": "integer"}]}}]}
        (d / "datapackage.json").write_text(json.dumps(pkg))
        results = validate_package_descriptor(d)
        assert any(r["status"] == "fail" and "file" in r["check"].lower() for r in results)

    def test_stale_schema_field_fails(self, tmp_path: Path) -> None:
        # schema declares 'ghost'; the table's only column is 'a' -> add/remove mismatch.
        pkg = {"name": "p", "resources": [
            {"name": "x", "path": "x.csv",
             "schema": {"fields": [{"name": "ghost", "type": "integer"}]}}]}
        results = validate_package_descriptor(_pkg_dir(tmp_path, pkg, csv="a\n1\n"))
        assert any("matches table" in r["check"] and r["status"] == "fail" for r in results)

    def test_type_conflict_with_table_fails(self, tmp_path: Path) -> None:
        # declared string, but the column is integer-valued -> coarse-type conflict.
        pkg = {"name": "p", "resources": [
            {"name": "x", "path": "x.csv",
             "schema": {"fields": [{"name": "a", "type": "string"}]}}]}
        results = validate_package_descriptor(_pkg_dir(tmp_path, pkg, csv="a\n1\n2\n"))
        assert any("matches table" in r["check"] and r["status"] == "fail" for r in results)

    def test_missing_or_any_type_fails_shape_gate(self, tmp_path: Path) -> None:
        # Phase 1's done depth is names + concrete coarse types. Omitted type / "any"
        # is valid DP syntax, but not sufficient for this campaign's shape gate.
        for field in ({"name": "a"}, {"name": "a", "type": "any"}):
            pkg = {"name": "p", "resources": [
                {"name": "x", "path": "x.csv", "schema": {"fields": [field]}}]}
            results = validate_package_descriptor(_pkg_dir(tmp_path, pkg, csv="a\n1\n2\n"))
            assert any("matches table" in r["check"] and r["status"] == "fail" for r in results)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd ~/d/science/science && uv run --quiet pytest tests/test_datasets_validate.py::TestDescriptorTargetValidation -q`
Expected: FAIL — `ImportError: cannot import name 'validate_package_descriptor'`.

- [ ] **Step 3: Implement `validate_package_descriptor`**

Edit the import block at the top of `src/science_tool/datasets/validate.py` to add:

```python
from science_tool.datasets.infer_schema import (
    InferSchemaError,
    diff_schema,
    load_descriptor,
    observed_fields,
)
```

Add near the top of the module (after imports):

```python
DESCRIPTOR_NAMES = ("datapackage.json", "datapackage.yaml", "datapackage.yml")
_TABULAR_SUFFIXES = (".csv", ".tsv", ".parquet")
_VALIDATE_SAMPLE = 10000
```

Append these functions to `src/science_tool/datasets/validate.py`:

```python
def _validate_resource_tables(resources: list[dict], base_dir: Path) -> list[dict[str, str]]:
    """Resource-level checks the Spec 1 models cannot do: the data file exists (resolved
    relative to the descriptor dir), and — for tabular resources that declare a schema —
    the declared fields[] agree with the table's observed names+types. Reuses
    infer-schema's `observed_fields` (Arrow for parquet, sampled for CSV/TSV) and
    `diff_schema` (the Spec 3 add/remove/conflict semantics)."""
    rows: list[dict[str, str]] = []
    for res in resources:
        name = res.get("name", res.get("path", "unknown"))
        table = base_dir / res.get("path", "")
        if not table.exists():
            rows.append({"check": f"{name} file exists", "status": "fail",
                         "details": f"file not found: {table}"})
            continue
        rows.append({"check": f"{name} file exists", "status": "pass", "details": str(table)})

        declared = (res.get("schema") or {}).get("fields")
        if table.suffix.lower() not in _TABULAR_SUFFIXES or not declared:
            continue
        try:
            observed = observed_fields(table, _VALIDATE_SAMPLE)
        except InferSchemaError as exc:
            rows.append({"check": f"{name} observed fields", "status": "fail", "details": str(exc)})
            continue
        problems = [d for d in diff_schema(declared, observed)
                    if d.action in ("add", "remove", "change")]
        if problems:
            detail = "; ".join(
                f"{d.name}: " + (
                    "in table, not in schema" if d.action == "add"
                    else "in schema, not in table" if d.action == "remove"
                    else f"declared {d.old_type!r} != observed {d.new_type!r}"
                )
                for d in problems
            )
            rows.append({"check": f"{name} schema matches table", "status": "fail", "details": detail})
        else:
            rows.append({"check": f"{name} schema matches table", "status": "pass",
                         "details": f"{len(declared)} fields agree"})
    return rows


def validate_package_descriptor(target: Path) -> list[dict[str, str]]:
    """Validate ONE package descriptor (JSON or YAML) at `target` (the descriptor file
    or the directory containing it) through the Spec 1 models AND against its tables —
    the same SSOT that `infer-schema --write` validates against.

    An explicit target must validate *something*: a missing/malformed descriptor, or a
    descriptor with no resources, is a `fail` row (never a silent warn). Beyond the Spec 1
    model + consistency checks, it confirms each resource's file exists and that declared
    fields agree with the observed table — so a stale `schema.fields[]` or an absent data
    file cannot pass. This is the campaign's real done-gate.
    """
    try:
        mapping, _fmt = load_descriptor(target)
    except InferSchemaError as exc:
        return [{"check": f"{target} descriptor", "status": "fail", "details": str(exc)}]

    resources = mapping.get("resources") or []
    if not resources:
        return [{
            "check": f"{target} descriptor resources",
            "status": "fail",
            "details": "descriptor defines no resources to validate",
        }]
    base_dir = target.parent if target.is_file() else target
    rows = _validate_resource_descriptors(resources, str(target))
    rows += _validate_resource_tables(resources, base_dir)
    return rows
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd ~/d/science/science && uv run --quiet pytest tests/test_datasets_validate.py::TestDescriptorTargetValidation -q`
Expected: PASS (11 passed).

- [ ] **Step 5: Run the full validate test module (no regressions)**

Run: `cd ~/d/science/science && uv run --quiet pytest tests/test_datasets_validate.py -q`
Expected: PASS (all prior tests + 10 new).

- [ ] **Step 6: Commit**

```bash
cd ~/d/science/science
git add src/science_tool/datasets/validate.py tests/test_datasets_validate.py
git commit -m "feat(datasets): exact-descriptor validation for JSON/YAML package dirs"
```

---

### Task 2: Phase 0 — CLI dispatch so `validate --path <pkg>` uses the gate

**Files:**
- Modify: `src/science_tool/datasets/validate.py` (add `validate_path` + `_is_descriptor_target`)
- Modify: `src/science_tool/cli.py:3106`
- Test: `tests/test_datasets_validate_cli.py` (create)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_datasets_validate_cli.py`:

```python
"""CLI behaviour for `science datasets validate` descriptor-target dispatch."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from science_tool.cli import cli


def _pkg_dir(tmp_path: Path, pkg: dict, csv: str = "a\n1\n") -> Path:
    d = tmp_path / "pkg"
    d.mkdir(parents=True, exist_ok=True)
    (d / "x.csv").write_text(csv)
    (d / "datapackage.json").write_text(json.dumps(pkg))
    return d


def test_valid_package_dir_exits_zero(tmp_path: Path) -> None:
    pkg = {"name": "p", "resources": [
        {"name": "x", "path": "x.csv",
         "schema": {"fields": [{"name": "a", "type": "integer"}]}}]}
    res = CliRunner().invoke(cli, ["datasets", "validate", "--path", str(_pkg_dir(tmp_path, pkg))])
    assert res.exit_code == 0, res.output


def test_invalid_package_dir_exits_nonzero(tmp_path: Path) -> None:
    pkg = {"name": "p", "resources": [
        {"name": "x", "path": "x.csv",
         "schema": {"fields": [{"name": "a", "type": "string", "qa": {"low_variance": True}}]}}]}
    res = CliRunner().invoke(cli, ["datasets", "validate", "--path", str(_pkg_dir(tmp_path, pkg))])
    assert res.exit_code != 0, res.output


def test_empty_dir_exits_nonzero(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    res = CliRunner().invoke(cli, ["datasets", "validate", "--path", str(empty)])
    # An explicit target with no descriptor must fail, not warn-and-pass.
    assert res.exit_code != 0, res.output


def test_legacy_raw_scan_still_works(tmp_path: Path) -> None:
    raw = tmp_path / "data" / "raw"
    raw.mkdir(parents=True)
    (raw / "x.csv").write_text("a\n1\n")
    (raw / "datapackage.json").write_text(json.dumps(
        {"name": "p", "resources": [
            {"name": "x", "path": "x.csv",
             "schema": {"fields": [{"name": "a", "type": "integer"}]}}]}))
    res = CliRunner().invoke(cli, ["datasets", "validate", "--path", str(tmp_path / "data")])
    assert res.exit_code == 0, res.output
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd ~/d/science/science && uv run --quiet pytest tests/test_datasets_validate_cli.py -q`
Expected: FAIL — `test_empty_dir_exits_nonzero` fails (legacy code warns→exit 0) and/or descriptor-dir tests mis-handle the path.

- [ ] **Step 3: Implement the dispatcher in `validate.py`**

Append to `src/science_tool/datasets/validate.py`:

```python
def _is_descriptor_target(target: Path) -> bool:
    """True when `target` is a datapackage descriptor file, or a directory holding one."""
    if target.is_file():
        return target.name in DESCRIPTOR_NAMES
    if target.is_dir():
        return any((target / name).exists() for name in DESCRIPTOR_NAMES)
    return False


def validate_path(target: Path) -> list[dict[str, str]]:
    """Dispatch validation by what `target` is.

    1. A datapackage descriptor file (or a directory directly containing one) → the
       exact-descriptor gate.
    2. Otherwise, a directory with a `raw/` or `processed/` subdir → the legacy scan
       (backward-compatible: the default `data` directory takes this path).
    3. Otherwise → fail. An explicit target that is neither a package nor a data tree
       must not silently warn-and-pass (fail early, per project rules).
    """
    if _is_descriptor_target(target):
        return validate_package_descriptor(target)
    if (target / "raw").is_dir() or (target / "processed").is_dir():
        return validate_data_packages(target)
    return [{
        "check": f"{target}",
        "status": "fail",
        "details": "no datapackage descriptor and no raw/ or processed/ subdirectory",
    }]
```

- [ ] **Step 4: Wire the CLI to the dispatcher**

In `src/science_tool/cli.py`, change the body of `datasets_validate` (line ~3106):

```python
    results = validate_path(data_path)
```

and update the import line for the validate module. Find the existing import of `validate_data_packages` (grep `from science_tool.datasets.validate import`) and replace it with `validate_path`:

```python
from science_tool.datasets.validate import validate_path
```

- [ ] **Step 5: Run the CLI tests to verify they pass**

Run: `cd ~/d/science/science && uv run --quiet pytest tests/test_datasets_validate_cli.py -q`
Expected: PASS (4 passed).

- [ ] **Step 6: Run both validate modules + a fast import smoke (no regressions)**

Run: `cd ~/d/science/science && uv run --quiet pytest tests/test_datasets_validate.py tests/test_datasets_validate_cli.py -q && uv run --quiet science datasets validate --help >/dev/null && echo OK`
Expected: PASS, then `OK`.

- [ ] **Step 7: Commit**

```bash
cd ~/d/science/science
git add src/science_tool/datasets/validate.py src/science_tool/cli.py tests/test_datasets_validate_cli.py
git commit -m "feat(datasets): validate --path dispatches to descriptor gate for package dirs"
```

---

### Task 3: Create the resumable campaign manifest

**Files:**
- Create: `docs/plans/2026-06-14-schema-adoption-campaign-manifest.md`

This is the single source of truth for campaign progress: every target package, its tabular-resource count, and its Phase-1 / Phase-2 status. Runbook tasks read and update it. Statuses: `pending` / `done` / `no-op` (no tabular resources) / `blocked-data` (local data missing).

- [ ] **Step 1: Write the manifest file**

Create `docs/plans/2026-06-14-schema-adoption-campaign-manifest.md` with exactly this content:

```markdown
# Schema Adoption Campaign — Manifest

Audited 2026-06-14. Statuses: `pending` | `done` | `no-op` | `blocked-data`.
Paths are package directories relative to each project root. No pushes — all commits stay local.

## mm30  [~/d/cancer/cancer-types/multiple-myeloma]

| Package | Fmt | Tabular | Phase 1 (shape) | Phase 2 (meaning) | Notes |
|---|---|---|---|---|---|
| data/external/ccle_proteomics/2020-01 | json | 2 | pending | pending | |
| data/external/ctrp_v2/2015 | json | 3 | pending | pending | |
| data/external/gdsc_v2/2022-07-24 | json | 3 | pending | pending | |
| data/external/oetjen_2018/2018-10 | json | 1 | pending | pending | |
| data/external/opentargets/25.03 | json | 3 | pending | pending | |
| data/external/walker_2024/2024-05 | json | 6 | pending | pending | 2 resources blocked-data (parquet absent) |

## cancer-therapeutics  [~/d/cancer/therapeutics]

| Package | Fmt | Tabular | Phase 1 (shape) | Phase 2 (meaning) | Notes |
|---|---|---|---|---|---|
| data/raw/chembl-activities | yaml | 1 | pending | pending | |
| data/raw/chembl | yaml | 1 | pending | pending | YAML smoke-test package (do first) |
| data/raw/dgidb | yaml | 2 | pending | pending | 1 resource blocked-data (../../processed path) |
| data/raw/drugcomb | yaml | 1 | pending | pending | |
| data/raw/nci-almanac | yaml | 0 | no-op | no-op | no tabular resources |
| data/raw/nsc-crosswalk | yaml | 1 | pending | pending | |
| data/raw/opentargets | yaml | 1 | pending | pending | |
| data/raw/string | yaml | 0 | no-op | no-op | no tabular resources |

## cancer-evolution  [~/d/cancer/mechanisms/evolution]

| Package | Fmt | Tabular | Phase 1 (shape) | Phase 2 (meaning) | Notes |
|---|---|---|---|---|---|
| data/raw/ampliconrepository-kim2024-pcawg | json | 9 | pending | pending | |
| data/raw/ampliconrepository-kim2024-tcga | json | 9 | pending | pending | |
| data/raw/kim2024-supplement | json | 0 | no-op | no-op | no tabular resources |
| data/raw/nct02415621-trial-patient-data | json | 0 | no-op | no-op | no tabular resources |

## health-meta  [~/d/health/meta]

| Package | Fmt | Tabular | Phase 1 (shape) | Phase 2 (meaning) | Notes |
|---|---|---|---|---|---|
| code/scripts/external/reactome | yaml | 6 | blocked-data | blocked-data | all 6 CSVs absent locally — needs hydration |

## Summary

- Effective working set: 14 packages with present local data.
- no-op (no tabular): nci-almanac, string, kim2024-supplement, nct02415621-trial-patient-data.
- blocked-data: reactome (whole package); 2 resources in walker_2024; 1 resource in dgidb.
```

- [ ] **Step 2: Commit**

```bash
cd ~/d/science
git add docs/plans/2026-06-14-schema-adoption-campaign-manifest.md
git commit -m "doc(schema-campaign): add resumable target manifest"
```

---

### Task 4: Phase 1 — bulk shape stage (per package)

**Procedure task (no red-green cycle).** For every `pending` package in the manifest, populate names+types on each tabular resource with `infer-schema --write`, gate with the Phase 0 validator, commit per repo. Order: **`cancer-therapeutics/data/raw/chembl` first** as the YAML write-path smoke test; confirm the descriptor round-trips before processing the rest of the YAML packages.

For each package `PKG_DIR` (absolute path = project root + manifest path):

- [ ] **Step 1: List the tabular resources to process**

```bash
cd ~/d/science/science
python3 - "$PKG_DIR" <<'PY'
import json, yaml, os, sys
d=sys.argv[1]
desc=next(p for p in ("datapackage.json","datapackage.yaml","datapackage.yml") if os.path.exists(os.path.join(d,p)))
path=os.path.join(d,desc)
m=json.load(open(path)) if desc.endswith(".json") else yaml.safe_load(open(path))
for r in m.get("resources",[]):
    p=r.get("path","")
    ext=os.path.splitext(p)[1].lower()
    tab=ext in {".csv",".parquet",".tsv"}
    present=os.path.exists(os.path.join(d,p))
    print(f"{r.get('name')}\ttabular={tab}\tpresent={present}\tpath={p}")
PY
```

Process only rows with `tabular=True present=True`. Record any `tabular=True present=False` resource in the manifest Notes as `blocked-data` and skip it.

- [ ] **Step 2: Read-only inference per resource (sanity-check the diff)**

For each `RES` to process:

```bash
cd ~/d/science/science
uv run --quiet science datasets infer-schema "$PKG_DIR" --resource "$RES"
```

Expected: a "Proposed schema" table of `+ add` rows (schema-less resource) or `= same` rows (already named+typed), plus a review report. Confirm proposed types look sane (no column collapsed to the wrong coarse type). If a resource errors (e.g. unreadable/escaping path), mark it `blocked-data` in the manifest and skip.

- [ ] **Step 3: Apply the names+types patch per resource**

```bash
cd ~/d/science/science
uv run --quiet science datasets infer-schema "$PKG_DIR" --resource "$RES" --write
```

Expected: `Applied names+types patch to <descriptor>`. The command runs Spec 1 whole-package post-validation internally and refuses on type conflict.

- [ ] **Step 4: Gate with the Phase 0 validator**

For a package with **no** blocked-data resources, use snippet **S2** and expect `exit=0`:

```bash
cd ~/d/science/science
uv run --quiet science datasets validate --path "$PKG_DIR"; echo "exit=$?"
```

For the two **partially-blocked** packages (`walker_2024`, `dgidb`), the gate will fail on
the absent-data resources by design — use snippet **S3** and confirm every reported fail
names a manifest-recorded blocked-data resource (and nothing else). In either case, if an
*unexpected* failure appears, stop and inspect — do not commit a failing descriptor.

- [ ] **Step 5: For the FIRST YAML package only (`chembl`) — verify clean round-trip**

```bash
cd "$REPO"   # cancer-therapeutics root
git diff -- data/raw/chembl/datapackage.yaml | head -60
```

Expected: the diff adds a `schema:` block with `fields:` (name+type) on the tabular resource and is a canonical re-render (sorted keys; comments/quoting not preserved — this is expected per Spec 3). Confirm no data-value or resource-path corruption before continuing with the other YAML packages.

- [ ] **Step 6: Commit the package's shape patch** (snippet S1)

```bash
cd "$REPO"
git rev-parse --show-toplevel && git branch --show-current
git add "<manifest-path>/datapackage.json"   # or .yaml — the one descriptor touched
git commit -m "chore(schema): infer names+types for <package-name>"
```

- [ ] **Step 7: Mark the package `done` for Phase 1 in the manifest**

Edit `docs/plans/2026-06-14-schema-adoption-campaign-manifest.md`: set the package's **Phase 1 (shape)** cell to `done`. Commit the manifest update in the science repo (batch several packages per manifest commit is fine).

- [ ] **Step 8: Repeat Steps 1–7 for every `pending` package**, then commit the final manifest state.

Run a **column-aware** coverage check before declaring Phase 1 complete. The Phase 1
status is the 5th `|`-delimited column; a bare `grep pending` would also match Phase 2
cells (still pending by design), so check that column specifically:

```bash
M=docs/plans/2026-06-14-schema-adoption-campaign-manifest.md
if awk -F'|' '$5 ~ /pending/' "$M" | grep -q .; then
  echo "FAIL: Phase-1 'pending' rows remain:"; awk -F'|' '$5 ~ /pending/' "$M"
else
  echo "no pending Phase-1 rows remain"
fi
```

Expected: `no pending Phase-1 rows remain` (every Phase 1 cell is `done` / `no-op` / `blocked-data`).

---

### Task 5: Phase 2 — structural meaning (subagent per package)

**Procedure task (no red-green cycle).** Dispatch one implementer subagent per Phase-1-`done` package to author structural invariants, then review each for over-authoring. Subagents work **in-place in the foreign repo**; the dispatch prompt MUST pin the repo path and forbid `-A` commits and pushes.

For each package:

- [ ] **Step 1: Generate the review report sidecar**

```bash
cd ~/d/science/science
for RES in <tabular resources>; do
  uv run --quiet science datasets infer-schema "$PKG_DIR" --resource "$RES" \
    --emit-suggestions "/tmp/report-<pkg>-$RES.yaml" >/dev/null
done
```

- [ ] **Step 2: Dispatch the authoring subagent**

Dispatch a subagent (sonnet) with a prompt containing, verbatim: the package's absolute path; the resource list; the report sidecar paths; and these rules (from design §4 Phase 2):

> Author structural invariants into the descriptor at `$PKG_DIR`, editing the existing `datapackage.{json,yaml}` in place. **Two tiers, each with its own evidence rule:**
> - **Per-resource** (`constraints.required`, `constraints.enum`, single-column `primaryKey`): author ONLY where the review report surfaced it AND the data confirms it. Reject sample coincidences — a column unique in-sample is not a primaryKey unless it is the dataset's real identifier (the `Description`-as-PK trap).
> - **Relational** (`foreignKeys`, composite `primaryKey`/`uniqueKeys`): the per-resource report cannot surface these. Author ONLY with direct cross-resource evidence — verify local field values are a subset of the target resource's key column(s), or that a column tuple is unique-and-non-null across the data. If you cannot verify it from the data, do NOT author it.
> - NEVER author `minimum`/`maximum` bounds, `qa:` of any kind, or any per-resource invariant the report did not surface.
> - After editing, run `cd ~/d/science/science && uv run --quiet science datasets validate --path "$PKG_DIR"`. For a fully-present package it must exit 0; for `walker_2024`/`dgidb` the ONLY failures allowed are the absent-data resources already recorded as blocked-data in the manifest (your authored changes must introduce no new failures).
> - Commit IN THE TARGET REPO: `cd <repo-root>`; verify branch with `git branch --show-current`; `git add` the single descriptor file by name (never `-A`); `git commit -m "feat(schema): author structural invariants for <package>"`. Do NOT push. Do NOT add a Co-Authored-By trailer.
> Report which invariants you authored per resource and the evidence for each.

- [ ] **Step 3: Review the subagent's work for over-authoring**

Inspect the diff against the report sidecar:

```bash
cd "$REPO" && git show --stat HEAD && git show HEAD -- "<manifest-path>/datapackage.json"
```

Confirm every authored per-resource invariant maps to a report recommendation, every relational invariant has stated cross-resource evidence, and nothing is a promoted sample coincidence. If anything is unsupported, re-dispatch the subagent to remove it (receiving-code-review applies: verify, then correct).

- [ ] **Step 4: Re-gate and mark `done`**

Re-run the Phase 0 gate: snippet **S2** (expect `exit=0`) for fully-present packages, or
snippet **S3** for `walker_2024`/`dgidb` (every fail must name a blocked-data resource).
Then set the package's **Phase 2 (meaning)** manifest cell to `done`; commit the manifest
update in the science repo.

- [ ] **Step 5: Repeat for every Phase-1-`done` package.** User spot-checks a sample of completed packages (surface 2–3 diffs for review).

Column-aware coverage check before declaring Phase 2 complete (Phase 2 is the 6th column;
check that no Phase-1 *or* Phase-2 cell is still `pending`):

```bash
M=docs/plans/2026-06-14-schema-adoption-campaign-manifest.md
if awk -F'|' '$5 ~ /pending/ || $6 ~ /pending/' "$M" | grep -q .; then
  echo "FAIL: pending rows remain:"; awk -F'|' '$5 ~ /pending/ || $6 ~ /pending/' "$M"
else
  echo "no pending rows remain"
fi
```

Expected: `no pending rows remain`.

---

### Task 6: Campaign close-out

**Files:**
- Modify: `docs/plans/2026-06-14-schema-adoption-campaign-manifest.md` (final state)
- Modify: `/home/keith/.claude/projects/-mnt-ssd-Dropbox-science/memory/project_discovery_improvements_umbrella.md` and `MEMORY.md`

- [ ] **Step 1: Verify no work is silently dropped**

Confirm every manifest row is `done`, `no-op`, or `blocked-data` (no `pending`), and that each `blocked-data` row's Notes names the missing data. Run the Phase-1 and Phase-2 coverage greps from Tasks 4 and 5; both must report no pending rows.

- [ ] **Step 2: Confirm each foreign repo has the expected un-pushed commits**

```bash
for REPO in ~/d/cancer/cancer-types/multiple-myeloma \
            ~/d/cancer/therapeutics \
            ~/d/cancer/mechanisms/evolution; do
  echo "== $REPO =="; cd "$REPO"; git log --oneline -5 -- '**/datapackage.*' 2>/dev/null | head
done
```

Expected: schema commits present; nothing pushed (these repos have no/unused remotes — do not push).

- [ ] **Step 3: Update memory**

In `project_discovery_improvements_umbrella.md`, record the campaign outcome (packages done/no-op/blocked, that Spec 4's precondition — real authored schemas — is now met) with absolute dates. Update the matching one-line pointer in `MEMORY.md`. Note that the Phase 0 validator gate (`validate --path <pkg-dir>` descriptor mode) shipped to local `main`, not pushed.

- [ ] **Step 4: Commit the close-out**

```bash
cd ~/d/science
git add docs/plans/2026-06-14-schema-adoption-campaign-manifest.md
git commit -m "doc(schema-campaign): finalize manifest — campaign complete"
```

Then run `superpowers:finishing-a-development-branch` for the science-repo code (Tasks 1–2) if a feature branch was used; otherwise the work is already on local `main`.

---

## Notes for the executor

- **Science-repo code** (Tasks 1–2) lives at `~/d/science/science`; run tests with `uv run --quiet pytest`. The science repo is Dropbox-only/local-main — **do not push**.
- **Foreign data repos** (Tasks 4–5): work in-place; verify branch before every commit; `git add` named descriptor files only; never push. mm30 is Dropbox-synced and branch-volatile — re-check `git branch --show-current` each time.
- **No scaffold patching mid-campaign.** If `infer-schema` or the compiler misbehaves on real data, record it in the manifest Notes and fix it in a separate science-repo cycle.
- **Reports over-recommend by design.** Phase 2's value is filtering them; never bulk-accept report recommendations into invariants.

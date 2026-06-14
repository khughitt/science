"""Data package validation using Frictionless."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from science_tool.datasets.infer_schema import (
    InferSchemaError,
    diff_schema,
    load_descriptor,
    observed_fields,
)
from science_tool.datasets.schema import ResourceDescriptor, package_consistency_issues

DESCRIPTOR_NAMES = ("datapackage.json", "datapackage.yaml", "datapackage.yml")
_TABULAR_SUFFIXES = (".csv", ".tsv", ".parquet")
_VALIDATE_SAMPLE = 10000


def validate_data_packages(data_dir: Path) -> list[dict[str, str]]:
    """Validate datapackage.json files in raw/ and processed/ subdirectories.

    Returns a list of check results with keys: check, status, details.
    Status is one of: pass, fail, warn.
    """
    results: list[dict[str, str]] = []

    for subdir_name in ("raw", "processed"):
        subdir = data_dir / subdir_name
        pkg_path = subdir / "datapackage.json"

        if not subdir.exists():
            continue

        # Check 1: datapackage.json presence
        if not pkg_path.exists():
            results.append(
                {
                    "check": f"{subdir_name}/datapackage.json presence",
                    "status": "warn",
                    "details": f"No datapackage.json in {subdir_name}/",
                }
            )
            continue

        results.append(
            {
                "check": f"{subdir_name}/datapackage.json presence",
                "status": "pass",
                "details": f"Found {pkg_path}",
            }
        )

        # Check 2: valid JSON
        try:
            with pkg_path.open() as f:
                pkg = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            results.append(
                {
                    "check": f"{subdir_name}/datapackage.json valid JSON",
                    "status": "fail",
                    "details": str(e),
                }
            )
            continue

        results.append(
            {
                "check": f"{subdir_name}/datapackage.json valid JSON",
                "status": "pass",
                "details": "Valid JSON",
            }
        )

        # Check 3: has resources
        resources = pkg.get("resources", [])
        if not resources:
            results.append(
                {
                    "check": f"{subdir_name} resources defined",
                    "status": "warn",
                    "details": "No resources defined in datapackage.json",
                }
            )
            continue

        # Check 3.5: typed-schema descriptor validation (Spec 1, additive)
        results.extend(_validate_resource_descriptors(resources, subdir_name))

        # Check 4: each resource file exists and schema validates
        for res in resources:
            res_name = res.get("name", res.get("path", "unknown"))
            res_path = subdir / res.get("path", "")

            if not res_path.exists():
                results.append(
                    {
                        "check": f"{subdir_name}/{res_name} file exists",
                        "status": "fail",
                        "details": f"File not found: {res_path}",
                    }
                )
                continue

            results.append(
                {
                    "check": f"{subdir_name}/{res_name} file exists",
                    "status": "pass",
                    "details": str(res_path),
                }
            )

            # Check 5: schema validation
            schema = res.get("schema")
            if schema:
                schema_results = _validate_resource_schema(res_path, schema, f"{subdir_name}/{res_name}")
                results.extend(schema_results)

    if not results:
        results.append(
            {
                "check": "data directory structure",
                "status": "warn",
                "details": "No raw/ or processed/ subdirectories found",
            }
        )

    return results


def _validate_resource_descriptors(resources: list[dict], prefix: str) -> list[dict[str, str]]:
    """Additive descriptor-validation pass (Spec 1): parse each resource against the
    typed-schema models and run cross-resource consistency. Emits pass|fail rows."""
    rows: list[dict[str, str]] = []
    descriptors: list[ResourceDescriptor] = []
    for res in resources:
        res_name = res.get("name", res.get("path", "unknown"))
        try:
            descriptors.append(ResourceDescriptor.model_validate(res))
        except ValidationError as exc:
            # One fail row per error → rich, located authoring feedback (design §7).
            for err in exc.errors():
                loc = ".".join(str(p) for p in err.get("loc", ()))
                msg = str(err.get("msg", ""))
                rows.append({
                    "check": f"{prefix}/{res_name} descriptor",
                    "status": "fail",
                    "details": f"{loc}: {msg}" if loc else msg,
                })
            continue
        rows.append({
            "check": f"{prefix}/{res_name} descriptor",
            "status": "pass",
            "details": "resource descriptor valid",
        })
    for issue in package_consistency_issues(descriptors):
        rows.append({
            "check": f"{prefix} descriptor consistency",
            "status": "fail",
            "details": issue,
        })
    return rows


def _validate_resource_schema(file_path: Path, schema: dict, prefix: str) -> list[dict[str, str]]:
    """Validate a CSV file against a Frictionless-style schema."""
    results: list[dict[str, str]] = []

    try:
        import csv

        with file_path.open(newline="") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames is None:
                results.append(
                    {
                        "check": f"{prefix} schema validation",
                        "status": "fail",
                        "details": "Could not read CSV headers",
                    }
                )
                return results

            # Check field names match
            expected_fields = [f["name"] for f in schema.get("fields", [])]
            actual_fields = list(reader.fieldnames)
            missing = set(expected_fields) - set(actual_fields)
            extra = set(actual_fields) - set(expected_fields)

            if missing:
                results.append(
                    {
                        "check": f"{prefix} field presence",
                        "status": "fail",
                        "details": f"Missing fields: {sorted(missing)}",
                    }
                )
            elif extra:
                results.append(
                    {
                        "check": f"{prefix} field presence",
                        "status": "warn",
                        "details": f"Extra fields not in schema: {sorted(extra)}",
                    }
                )
            else:
                results.append(
                    {
                        "check": f"{prefix} field presence",
                        "status": "pass",
                        "details": f"All {len(expected_fields)} fields present",
                    }
                )

            # Check type conformance for a sample of rows
            field_types = {f["name"]: f.get("type", "string") for f in schema.get("fields", [])}
            type_errors: list[str] = []
            for row_num, row in enumerate(reader, start=2):
                if row_num > 100:  # Sample first 100 rows
                    break
                for fname, ftype in field_types.items():
                    value = row.get(fname, "")
                    if value == "" or value is None:
                        continue
                    if not _check_type(value, ftype):
                        type_errors.append(f"Row {row_num}, {fname}: {value!r} is not {ftype}")

            if type_errors:
                results.append(
                    {
                        "check": f"{prefix} type conformance",
                        "status": "fail",
                        "details": f"{len(type_errors)} type error(s): {type_errors[0]}"
                        + (f" (and {len(type_errors) - 1} more)" if len(type_errors) > 1 else ""),
                    }
                )
            else:
                results.append(
                    {
                        "check": f"{prefix} type conformance",
                        "status": "pass",
                        "details": "All sampled values match declared types",
                    }
                )

    except Exception as e:
        results.append(
            {
                "check": f"{prefix} schema validation",
                "status": "fail",
                "details": f"Validation error: {e}",
            }
        )

    return results


def _check_type(value: str, declared_type: str) -> bool:
    """Check if a string value is compatible with a Frictionless field type."""
    if declared_type in ("string",):
        return True
    if declared_type in ("integer",):
        try:
            int(value)
            return True
        except ValueError:
            return False
    if declared_type in ("number",):
        try:
            float(value)
            return True
        except ValueError:
            return False
    if declared_type in ("boolean",):
        return value.lower() in ("true", "false", "1", "0")
    # For other types (date, datetime, etc.), accept anything for now
    return True


def _validate_resource_tables(resources: list[dict], base_dir: Path) -> list[dict[str, str]]:
    """Resource-level checks the Spec 1 models cannot do: the data file exists (resolved
    relative to the descriptor dir), and — for tabular resources that declare a schema —
    the declared fields[] agree with the table's observed names+types. Reuses
    infer-schema's `observed_fields` (Arrow for parquet, sampled for CSV/TSV) and
    `diff_schema` (the Spec 3 add/remove/conflict semantics)."""
    rows: list[dict[str, str]] = []
    for res in resources:
        name = res.get("name", res.get("path", "unknown"))
        path_val = res.get("path")
        if not isinstance(path_val, str) or not path_val:
            rows.append({"check": f"{name} path", "status": "fail",
                         "details": f"resource path must be a non-empty string, got {path_val!r}"})
            continue
        table = base_dir / path_val
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
                    if d.action in ("add", "remove") or d.conflict]
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

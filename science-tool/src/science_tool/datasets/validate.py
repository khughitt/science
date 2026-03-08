"""Data package validation using Frictionless."""

from __future__ import annotations

import json
from pathlib import Path


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
            results.append({
                "check": f"{subdir_name}/datapackage.json presence",
                "status": "warn",
                "details": f"No datapackage.json in {subdir_name}/",
            })
            continue

        results.append({
            "check": f"{subdir_name}/datapackage.json presence",
            "status": "pass",
            "details": f"Found {pkg_path}",
        })

        # Check 2: valid JSON
        try:
            with pkg_path.open() as f:
                pkg = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            results.append({
                "check": f"{subdir_name}/datapackage.json valid JSON",
                "status": "fail",
                "details": str(e),
            })
            continue

        results.append({
            "check": f"{subdir_name}/datapackage.json valid JSON",
            "status": "pass",
            "details": "Valid JSON",
        })

        # Check 3: has resources
        resources = pkg.get("resources", [])
        if not resources:
            results.append({
                "check": f"{subdir_name} resources defined",
                "status": "warn",
                "details": "No resources defined in datapackage.json",
            })
            continue

        # Check 4: each resource file exists and schema validates
        for res in resources:
            res_name = res.get("name", res.get("path", "unknown"))
            res_path = subdir / res.get("path", "")

            if not res_path.exists():
                results.append({
                    "check": f"{subdir_name}/{res_name} file exists",
                    "status": "fail",
                    "details": f"File not found: {res_path}",
                })
                continue

            results.append({
                "check": f"{subdir_name}/{res_name} file exists",
                "status": "pass",
                "details": str(res_path),
            })

            # Check 5: schema validation
            schema = res.get("schema")
            if schema:
                schema_results = _validate_resource_schema(res_path, schema, f"{subdir_name}/{res_name}")
                results.extend(schema_results)

    if not results:
        results.append({
            "check": "data directory structure",
            "status": "warn",
            "details": "No raw/ or processed/ subdirectories found",
        })

    return results


def _validate_resource_schema(
    file_path: Path, schema: dict, prefix: str
) -> list[dict[str, str]]:
    """Validate a CSV file against a Frictionless-style schema."""
    results: list[dict[str, str]] = []

    try:
        import csv

        with file_path.open(newline="") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames is None:
                results.append({
                    "check": f"{prefix} schema validation",
                    "status": "fail",
                    "details": "Could not read CSV headers",
                })
                return results

            # Check field names match
            expected_fields = [f["name"] for f in schema.get("fields", [])]
            actual_fields = list(reader.fieldnames)
            missing = set(expected_fields) - set(actual_fields)
            extra = set(actual_fields) - set(expected_fields)

            if missing:
                results.append({
                    "check": f"{prefix} field presence",
                    "status": "fail",
                    "details": f"Missing fields: {sorted(missing)}",
                })
            elif extra:
                results.append({
                    "check": f"{prefix} field presence",
                    "status": "warn",
                    "details": f"Extra fields not in schema: {sorted(extra)}",
                })
            else:
                results.append({
                    "check": f"{prefix} field presence",
                    "status": "pass",
                    "details": f"All {len(expected_fields)} fields present",
                })

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
                results.append({
                    "check": f"{prefix} type conformance",
                    "status": "fail",
                    "details": f"{len(type_errors)} type error(s): {type_errors[0]}"
                    + (f" (and {len(type_errors) - 1} more)" if len(type_errors) > 1 else ""),
                })
            else:
                results.append({
                    "check": f"{prefix} type conformance",
                    "status": "pass",
                    "details": "All sampled values match declared types",
                })

    except Exception as e:
        results.append({
            "check": f"{prefix} schema validation",
            "status": "fail",
            "details": f"Validation error: {e}",
        })

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

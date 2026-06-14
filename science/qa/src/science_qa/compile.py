"""Compile a Frictionless resource descriptor into a QAConfig (Spec 2).

Plain-dict only (no pydantic): the on-disk Table Schema + its `qa:` extension are the
single source of truth, read at run time. Native constraints map to structural checks;
the `qa:` extension maps to distribution checks. See
docs/plans/2026-06-14-qa-schema-compiler-design.md.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from science_qa.config import QAConfig

_BOUND_KEYS = ("minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum")


class CompileError(Exception):
    """Raised on a descriptor that cannot be compiled (fail early, exit 2)."""


def _validate_bound_value(field: str, key: str, value: object) -> None:
    """A bound value must be a number or a parseable ISO date/datetime string (design §8).

    This is a *descriptor-only* check (no table) — it uses the same parser (`pd.Timestamp`)
    the bounds aspect uses at run time, so a value the compiler accepts is one the aspect
    can parse. A non-scalar, or an unparseable string, is a CompileError (exit 2).
    """
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise CompileError(f"field {field!r} bound {key} has non-scalar value {value!r}")
    if isinstance(value, str):
        try:
            pd.Timestamp(value)
        except (ValueError, TypeError) as exc:
            raise CompileError(
                f"field {field!r} bound {key}={value!r} is neither a number nor a parseable ISO date"
            ) from exc


def schema_to_config(resource: dict, package_dir: Path, package: dict) -> QAConfig:
    schema = resource.get("schema")
    name = resource.get("name", "?")
    if not isinstance(schema, dict) or "fields" not in schema:
        raise CompileError(f"resource {name!r} has no usable schema (need schema.fields)")
    if "path" not in resource:
        raise CompileError(f"resource {name!r} has no path")

    cfg = QAConfig(program="", base_dir=package_dir)

    for f in schema.get("fields", []):
        fname = f["name"]
        ftype = f.get("type", "any")
        constraints = f.get("constraints", {}) or {}
        if constraints.get("required"):
            cfg.required_complete.append(fname)
        if constraints.get("unique"):
            cfg.unique_keys.append([fname])
        if ftype in ("integer", "number"):
            cfg.expected_types[fname] = "numeric"
        elif ftype != "any":
            cfg.expected_types[fname] = "non-numeric"
        bound = {k: constraints[k] for k in _BOUND_KEYS if k in constraints}
        if bound:
            for bkey, bval in bound.items():
                _validate_bound_value(fname, bkey, bval)
            cfg.bounds[fname] = bound
        if "enum" in constraints:
            cfg.categoricals[fname] = {"allowed": list(constraints["enum"])}

    pk = schema.get("primaryKey")
    if pk:
        cfg.unique_keys.append(pk if isinstance(pk, list) else [pk])
    for group in schema.get("uniqueKeys", []) or []:
        cfg.unique_keys.append(list(group))

    for entry in schema.get("missingValues", [""]):
        value = entry if isinstance(entry, str) else entry.get("value")
        if value not in ("", None):
            cfg.missing_sentinels.append(value)

    table_qa = schema.get("qa", {}) or {}
    for pair in table_qa.get("exclusive_flags", []) or []:
        cfg.exclusive_flags.append(list(pair))

    _compile_foreign_keys(resource, schema, package, cfg)  # added in next task
    return cfg


def _as_one(value) -> tuple[str, bool]:
    """Return (single_name, is_composite) for a FK fields value (str or list)."""
    if isinstance(value, list):
        return (value[0] if value else "", len(value) > 1)
    return (value, False)


def _compile_foreign_keys(resource: dict, schema: dict, package: dict, cfg: QAConfig) -> None:
    by_name = {r.get("name"): r for r in package.get("resources", [])}
    self_name = resource.get("name")
    for fk in schema.get("foreignKeys", []) or []:
        local, local_composite = _as_one(fk["fields"])
        ref = fk.get("reference", {})
        ref_field, ref_composite = _as_one(ref.get("fields"))
        if local_composite or ref_composite:
            raise CompileError(f"composite foreignKey not supported (single-column only): {fk}")
        target_name = ref.get("resource") or self_name
        target = by_name.get(target_name)
        if target is None:
            raise CompileError(f"foreignKey on {self_name!r} references unknown resource {target_name!r}")
        target_fields = {f["name"] for f in (target.get("schema", {}) or {}).get("fields", [])}
        if ref_field not in target_fields:
            raise CompileError(
                f"foreignKey on {self_name!r} reference field {ref_field!r} not in resource {target_name!r}")
        cfg.categoricals[local] = {"allowed_from": f"{target['path']}#{ref_field}"}

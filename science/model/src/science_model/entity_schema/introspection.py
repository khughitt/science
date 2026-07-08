"""Inspect effective entity schema constraints for authoring help."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from science_model.entity_schema.loader import SchemaLoader
from science_model.entity_schema.profile import ProfileComponent, ProfileString


@dataclass(frozen=True, slots=True)
class FrontmatterField:
    key: str
    required: bool
    type: str | None
    constraints: dict[str, Any]


def read_effective_frontmatter_fields(
    profile: ProfileString, loader: SchemaLoader | None = None
) -> list[FrontmatterField]:
    """Return effective frontmatter field constraints for a composed profile.

    Profile components are composed with JSON Schema ``allOf``, so constraints
    intersect. This helper reports the practical intersection for authoring
    surfaces: root required fields are unioned, consts narrow enums, enum sets
    intersect, and independent patterns/formats remain simultaneous constraints.
    Conditional requirements are not included because they depend on field
    values rather than the profile alone.
    """
    loader = loader or SchemaLoader()
    schemas = [loader.load(component) for component in _iter_components(profile)]

    required = {
        field
        for schema in schemas
        for field in schema.get("required", []) or []
        if isinstance(field, str)
    }
    specs_by_field: dict[str, list[dict[str, Any]]] = {}
    field_order: list[str] = []
    for schema in schemas:
        properties = schema.get("properties") or {}
        for key, spec in properties.items():
            if not isinstance(spec, dict):
                continue
            if key not in specs_by_field:
                field_order.append(key)
                specs_by_field[key] = []
            specs_by_field[key].append(spec)

    return [
        FrontmatterField(
            key=key,
            required=key in required,
            type=_effective_type(specs_by_field[key]),
            constraints=_effective_constraints(specs_by_field[key]),
        )
        for key in field_order
    ]


def _effective_constraints(specs: list[dict[str, Any]]) -> dict[str, Any]:
    constraints: dict[str, Any] = {}
    const = _effective_const(specs)
    if const is not _ABSENT:
        constraints["const"] = const
        return constraints

    enum = _effective_enum(specs)
    if enum is not None:
        constraints["enum"] = enum
    patterns = _unique_values(spec.get("pattern") for spec in specs)
    if len(patterns) == 1:
        constraints["pattern"] = patterns[0]
    elif patterns:
        constraints["patterns"] = patterns
    formats = _unique_values(spec.get("format") for spec in specs)
    if len(formats) == 1:
        constraints["format"] = formats[0]
    elif formats:
        constraints["formats"] = formats
    return constraints


def _effective_const(specs: list[dict[str, Any]]) -> Any:
    consts = [spec["const"] for spec in specs if "const" in spec]
    if not consts:
        return _ABSENT
    first = consts[0]
    if any(value != first for value in consts):
        raise ValueError(f"incompatible const constraints: {consts!r}")
    enums = [spec["enum"] for spec in specs if isinstance(spec.get("enum"), list)]
    for enum in enums:
        if first not in enum:
            raise ValueError(f"const {first!r} is outside enum constraint {enum!r}")
    return first


def _effective_enum(specs: list[dict[str, Any]]) -> list[Any] | None:
    enums = [spec["enum"] for spec in specs if isinstance(spec.get("enum"), list)]
    if not enums:
        return None
    values = list(enums[0])
    for enum in enums[1:]:
        values = [value for value in values if value in enum]
    return values


def _effective_type(specs: list[dict[str, Any]]) -> str | None:
    const = _effective_const(specs)
    if const is not _ABSENT:
        return _json_type(const)
    types = _unique_values(_normalize_type(spec.get("type")) for spec in specs)
    enum = _effective_enum(specs)
    if enum:
        enum_type = _single_json_type(enum)
        if enum_type is not None:
            types = [value for value in types if value == enum_type] or [enum_type]
    if len(types) == 1:
        return types[0]
    return None


def _normalize_type(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    return None


def _single_json_type(values: list[Any]) -> str | None:
    types = {_json_type(value) for value in values}
    if len(types) == 1:
        return next(iter(types))
    return None


def _json_type(value: Any) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int) and not isinstance(value, bool):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    if value is None:
        return "null"
    return type(value).__name__


def _unique_values(values: Iterable[Any]) -> list[Any]:
    unique: list[Any] = []
    for value in values:
        if value is None:
            continue
        if value not in unique:
            unique.append(value)
    return unique


def _iter_components(profile: ProfileString) -> list[ProfileComponent]:
    components = [profile.base]
    if profile.mixin is not None:
        components.append(profile.mixin)
    components.extend(profile.extensions)
    return components


class _Absent:
    pass


_ABSENT = _Absent()

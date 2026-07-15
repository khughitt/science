"""Compose and apply multi-component entity schemas."""

from __future__ import annotations

from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError as _JsonValidationError

from science_model.entity_schema.loader import SchemaLoader
from science_model.entity_schema.profile import (
    PROJECT_MIXIN_NAMES,
    TYPE_MIXIN_NAMES,
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
        """Validate against the entity's OWN declared `schema_profile` (the commons path)."""
        profile_str = entity.get("schema_profile")
        if not profile_str:
            raise EntityValidationError("entity is missing required schema_profile field")
        try:
            profile = parse_profile(profile_str)
        except ProfileParseError as exc:
            raise EntityValidationError(f"invalid schema_profile: {exc}") from exc
        self.validate_as(entity, profile)

    def validate_as(self, entity: dict[str, Any], profile: ProfileString) -> None:
        """Validate against an EXPLICIT profile, without mutating the caller's dict.

        Project entities do not author `schema_profile`; it is derived from `kind`
        (`default_profile_for_kind`), so the profile must be passed in rather than read out.
        """
        if profile.mixin is None:
            raise EntityValidationError(
                f"schema_profile must include a type mixin (one of {sorted(TYPE_MIXIN_NAMES)}) "
                "— base-only profiles are not valid for entity payloads",
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

    def validate_overlay(self, overlay: dict[str, Any]) -> None:
        """Validate a project overlay (different schema than canonical entities)."""
        from science_model.entity_schema.profile import ProfileComponent

        # Overlay schema is identified by a synthetic ProfileComponent: name="overlay".
        # Filename convention is special-cased in loader._filename_for.
        schema = self._loader.load(ProfileComponent(name="overlay", version="1.1"))
        validator = Draft202012Validator(
            schema,
            format_checker=Draft202012Validator.FORMAT_CHECKER,
        )
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

    def _compose(self, profile: ProfileString) -> dict[str, Any]:
        parts = [self._loader.load(profile.base)]
        if profile.mixin is not None:
            parts.append(self._loader.load(profile.mixin))
        parts.extend(self._loader.load(ext) for ext in profile.extensions)

        # `unevaluatedProperties` -- NOT `additionalProperties`. Inside an allOf,
        # `additionalProperties` in one branch cannot see properties declared by a SIBLING branch,
        # so it would reject every field the mixin declares. `unevaluatedProperties` is evaluated
        # after the whole allOf and sees the union. This is THE line that turns the original defect
        # (Entity's extra="ignore" silently dropping undeclared keys) into a loud failure.
        #
        # Commons profiles are deliberately NOT closed: `SharedEntity` is extra="allow" by design
        # and 369 records rely on it. `strict` is gated on PROJECT_MIXIN_NAMES so each kind opts in
        # as it migrates.
        composed: dict[str, Any] = {"allOf": parts}
        if profile.mixin is not None and profile.mixin.name in PROJECT_MIXIN_NAMES:
            composed["unevaluatedProperties"] = False
        return composed


def _format_error(err: _JsonValidationError) -> str:
    path = ".".join(str(segment) for segment in err.absolute_path) or "<root>"
    return f"{path}: {err.message}"

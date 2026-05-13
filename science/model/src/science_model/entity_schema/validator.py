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

    def validate_overlay(self, overlay: dict[str, Any]) -> None:
        """Validate a project overlay (different schema than canonical entities)."""
        from science_model.entity_schema.profile import ProfileComponent

        # Overlay schema is identified by a synthetic ProfileComponent: name="overlay".
        # Filename convention is special-cased in loader._filename_for.
        schema = self._loader.load(ProfileComponent(name="overlay", version="1.0"))
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
        return {"allOf": parts}


def _format_error(err: _JsonValidationError) -> str:
    path = ".".join(str(segment) for segment in err.absolute_path) or "<root>"
    return f"{path}: {err.message}"

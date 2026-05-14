"""Pydantic ergonomic wrapper around composed entity schemas.

JSON Schema is the source of truth — this wrapper exists only for nice
in-code field access. Unknown fields land in `extra: dict[str, Any]`.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from science_model.entity_schema.validator import EntityValidator


class SharedEntity(BaseModel):
    """Frontmatter projection of a shared canonical entity."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    schema_profile: str
    id: str
    type: str
    title: str
    version: str
    created: date | None = None
    updated: date | None = None
    description: str = ""
    sources: list[str] = Field(default_factory=list)
    licenses: list[Any] = Field(default_factory=list)
    contributors: list[dict[str, Any]] = Field(default_factory=list)
    ontology_terms: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    status: str = ""

    # Everything not declared above lands here at validation time.
    extra: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _capture_extras(cls, values: Any) -> Any:
        if not isinstance(values, dict):
            return values
        declared = set(cls.model_fields.keys()) - {"extra"}
        extra = {k: v for k, v in values.items() if k not in declared}
        # Keep declared fields in the top-level mapping; copy extras into 'extra'.
        out = {k: v for k, v in values.items() if k in declared}
        out["extra"] = extra
        return out

    def validate_schema(self, validator: EntityValidator | None = None) -> None:
        """Run JSON Schema validation against this entity's `schema_profile`."""
        validator = validator or EntityValidator()
        # Flatten the wrapper back into a plain dict for the validator.
        payload: dict[str, Any] = self.model_dump(mode="json", exclude={"extra"})
        payload.update(self.extra)
        validator.validate(payload)

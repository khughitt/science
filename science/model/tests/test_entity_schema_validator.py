from __future__ import annotations

import pytest

from science_model.entity_schema.validator import (
    EntityValidationError,
    EntityValidator,
)


def test_validator_rejects_entity_with_missing_schema_profile() -> None:
    validator = EntityValidator()
    with pytest.raises(EntityValidationError, match="schema_profile"):
        validator.validate({"id": "paper:Adams2025", "type": "paper"})


def test_validator_rejects_malformed_schema_profile() -> None:
    validator = EntityValidator()
    with pytest.raises(EntityValidationError, match="invalid schema_profile"):
        validator.validate({"schema_profile": "not-a-real-base/1.0", "id": "x:y"})


def test_validator_rejects_base_only_schema_profile() -> None:
    # A base-only profile bypasses type-specific constraints, so refuse it.
    validator = EntityValidator()
    with pytest.raises(EntityValidationError, match="mixin"):
        validator.validate({
            "schema_profile": "science-entity-base/1.0",
            "id": "paper:Adams2025",
            "type": "paper",
            "title": "x",
            "version": "1.0.0",
            "created": "2026-05-13",
            "updated": "2026-05-13",
        })

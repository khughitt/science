"""PropositionEntity — typed entity carrying factored relational axes."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from science_model.entities import EntityType, ProjectEntity
from science_model.reasoning import (
    ClaimLayer,
    IdentificationStrength,
    Polarity,
    Predicate,
    SIGN_MEANINGFUL_PREDICATES,
)


class PropositionEntity(ProjectEntity):
    """Proposition — typed entity with factored predicate/polarity relational axes.

    Constructable programmatically from relational fields alone (no markdown
    source file required at mint time). Base-required content/source fields
    default to empty so the entity can be created before a file exists (minted
    from workbench rows in Task 5b).
    """

    # Fix kind and type to "proposition" so the base validator passes.
    kind: str = "proposition"
    type: Literal[EntityType.PROPOSITION] = EntityType.PROPOSITION  # type: ignore[assignment]

    # Base-required fields that may not exist at mint time — safe defaults.
    title: str = ""
    project: str = ""
    ontology_terms: list[str] = Field(default_factory=list)
    related: list[str] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)
    content_preview: str = ""
    file_path: str = ""

    # Relational axes
    subject: str | None = None
    object: str | None = None
    predicate: Predicate | None = None
    polarity: Polarity | None = None
    legacy_relation_label: str | None = None

    # Reasoning metadata
    claim_layer: ClaimLayer | None = None
    identification_strength: IdentificationStrength | None = None

    @model_validator(mode="after")
    def _validate_relational_fields(self) -> "PropositionEntity":
        # Rule 1: predicate set → both subject and object must be set.
        if self.predicate is not None:
            if self.subject is None or self.object is None:
                raise ValueError(
                    "predicate requires both subject and object to be set"
                )
            # Rule 2: sign-meaningful predicate → polarity must be positive/negative/unsigned.
            if self.predicate in SIGN_MEANINGFUL_PREDICATES:
                if self.polarity == Polarity.NOT_APPLICABLE:
                    raise ValueError(
                        f"predicate {self.predicate!r} is sign-meaningful; "
                        f"polarity must be positive, negative, or unsigned (not not_applicable)"
                    )
            else:
                # Rule 3: sign-less predicate → polarity must be not_applicable.
                if self.polarity is not None and self.polarity != Polarity.NOT_APPLICABLE:
                    raise ValueError(
                        f"predicate {self.predicate!r} is sign-less; "
                        f"polarity must be not_applicable (got {self.polarity!r})"
                    )
        return self

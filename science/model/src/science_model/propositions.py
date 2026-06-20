"""PropositionEntity — typed entity carrying factored relational axes."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from science_model.entities import EntityType, ProjectEntity
from science_model.reasoning import (
    SIGN_MEANINGFUL_PREDICATES,
    ClaimLayer,
    IdentificationStrength,
    MembershipRole,
    Polarity,
    Predicate,
)


class DiscussesMembership(BaseModel):
    """Object form of a `discusses` entry: a frame plus the proposition's role in it.

    `frame` is a bundle reference (hypothesis or mechanism). A bare string in the
    `discusses` list is sugar for `{frame: <string>, role: core}`.
    """

    model_config = ConfigDict(extra="forbid")  # malformed membership hard-fails (spec §5)

    frame: str = Field(min_length=1)
    role: MembershipRole = MembershipRole.CORE


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

    # Migration provenance: origin patch/edge id in a legacy edges.yaml store (set during corpus migration).
    legacy_patch: str | None = None
    legacy_edge_id: int | None = None

    # Bundle membership: focal hypothesis/mechanism(s) this proposition discusses (→ cito:discusses).
    # A bare string means role=core; an object carries an explicit MembershipRole (spec §3).
    discusses: list[str | DiscussesMembership] = Field(default_factory=list)

    # Reasoning metadata
    claim_layer: ClaimLayer | None = None
    identification_strength: IdentificationStrength | None = None
    # Versioned identity of the synthesizer that authored the reasoning fields above
    # (Phase 4c: "llm-synth:<model>:proposition-synthesize-v1"). Answers "is this
    # reasoning stale under the current synthesizer?"; a free string the validators ignore.
    reasoning_source: str | None = None

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
                if self.polarity not in (Polarity.POSITIVE, Polarity.NEGATIVE, Polarity.UNSIGNED):
                    raise ValueError(
                        f"predicate {self.predicate!r} is sign-meaningful; "
                        f"polarity must be positive, negative, or unsigned "
                        f"(got {self.polarity!r}; use unsigned for sign-apt but undetermined)"
                    )
            else:
                # Rule 3: sign-less predicate → polarity must be not_applicable.
                if self.polarity is not None and self.polarity != Polarity.NOT_APPLICABLE:
                    raise ValueError(
                        f"predicate {self.predicate!r} is sign-less; "
                        f"polarity must be not_applicable (got {self.polarity!r})"
                    )
        return self

    def iter_memberships(self) -> Iterator[tuple[str, MembershipRole]]:
        """Yield de-duped (frame_ref, role) pairs; bare strings are core."""
        seen: set[tuple[str, MembershipRole]] = set()
        for item in self.discusses:
            if isinstance(item, str):
                pair = (item, MembershipRole.CORE)
            else:
                pair = (item.frame, item.role)
            if pair in seen:
                continue
            seen.add(pair)
            yield pair

    @model_validator(mode="after")
    def _validate_membership_roles(self) -> "PropositionEntity":
        """A proposition has exactly one role per bundle frame (spec §5 rule 3).

        Enforced here, at the model layer, so the invariant holds at EVERY load
        site — materialize, workbench compile, and `science validate` alike — not
        only in the standalone validator. Identical-role duplicates are harmless.
        """
        roles_by_frame: dict[str, set[MembershipRole]] = {}
        for frame, role in self.iter_memberships():
            roles_by_frame.setdefault(frame, set()).add(role)
        conflicts = {f: r for f, r in roles_by_frame.items() if len(r) > 1}
        if conflicts:
            detail = ", ".join(
                f"{f}: {sorted(x.value for x in r)}" for f, r in sorted(conflicts.items())
            )
            raise ValueError(
                f"discusses lists conflicting membership roles for the same frame ({detail}); "
                "a proposition has exactly one role per bundle"
            )
        return self

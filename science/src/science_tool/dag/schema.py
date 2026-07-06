"""Pydantic models for DAG reference entries."""

from __future__ import annotations

from pydantic import BaseModel, model_validator


class SchemaError(ValueError):
    """Raised when a DAG reference entry violates a structural invariant."""


# Kind tags that identify the type of a reference entry.
REF_KINDS: frozenset[str] = frozenset(
    {
        "task",
        "interpretation",
        "discussion",
        "proposition",
        "paper",
        "doi",
        "accession",
        "dataset",
    }
)


class RefEntry(BaseModel):
    """A single reference entry.

    Exactly one of REF_KINDS must appear as a key with a non-null value.
    All other keys (e.g. ``author_year``, ``notes``) are kept as-is via
    ``extra="allow"``.
    """

    model_config = {"extra": "allow"}

    description: str

    @model_validator(mode="after")
    def _exactly_one_kind(self) -> "RefEntry":
        extra: dict = self.__pydantic_extra__ or {}
        found = [k for k, v in extra.items() if k in REF_KINDS and v is not None]
        if len(found) != 1:
            raise SchemaError(
                f"ref entry must have exactly one non-null kind tag from {sorted(REF_KINDS)}; got {found!r}"
            )
        return self

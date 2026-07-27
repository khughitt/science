"""Supporting evidence on a finding (design §1).

A discriminated union, not a free-form list: ingestion validates every evidence
path, which is impossible against a list that cannot tell a path from prose.

`extra="forbid"` on both variants is deliberate. `Entity` uses `extra="ignore"`,
which is why a hand-written `phase:` could be written and never reach the graph.
A silently dropped field on an audit record would cost the same diagnosis.
"""

from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from science_model.audit.subjects import normalize_project_path

MAX_EVIDENCE_ENTRIES = 100
MAX_TEXT_LENGTH = 4000
MAX_LABEL_LENGTH = 200
MAX_POINTER_LENGTH = 200


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Span(_Base):
    """A 1-based, END-INCLUSIVE region. Columns are optional as a PAIR."""

    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    start_col: int | None = Field(default=None, ge=1)
    end_col: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def _ordered(self) -> "Span":
        if self.end_line < self.start_line:
            raise ValueError("end_line must be >= start_line")
        if (self.start_col is None) != (self.end_col is None):
            raise ValueError(
                "start_col and end_col are optional as a pair; supplying one without "
                "the other is ambiguous"
            )
        if (
            self.start_col is not None
            and self.end_col is not None
            and self.start_line == self.end_line
            and self.end_col < self.start_col
        ):
            raise ValueError("on a single line, end_col must be >= start_col")
        return self


class LocationEvidence(_Base):
    type: Literal["location"] = "location"
    path: str
    pointer: str | None = None
    line: int | None = Field(default=None, ge=1)
    span: Span | None = None

    @field_validator("path")
    @classmethod
    def _normalize(cls, value: str) -> str:
        return normalize_project_path(value)

    @field_validator("pointer")
    @classmethod
    def _bounded_pointer(cls, value: str | None) -> str | None:
        # Positional segments ARE permitted here: evidence is not identity-bearing.
        if value is not None and len(value) > MAX_POINTER_LENGTH:
            raise ValueError(f"pointer exceeds {MAX_POINTER_LENGTH} characters")
        return value

    @model_validator(mode="after")
    def _line_xor_span(self) -> "LocationEvidence":
        if self.line is not None and self.span is not None:
            raise ValueError(
                "line and span are mutually exclusive; supplying both is rejected "
                "rather than resolved by precedence"
            )
        return self


class TextEvidence(_Base):
    type: Literal["text"] = "text"
    label: str | None = Field(default=None, max_length=MAX_LABEL_LENGTH)
    text: str = Field(max_length=MAX_TEXT_LENGTH)


Evidence = Annotated[Union[LocationEvidence, TextEvidence], Field(discriminator="type")]

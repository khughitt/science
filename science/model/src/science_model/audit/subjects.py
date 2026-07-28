"""The four finding subjects (design §2).

One REQUIRED, discriminated primary subject. There is deliberately no
entity-then-path fallback: an invalid entity subject fails rather than silently
degrading to a path, which would change a case's identity unnoticed.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator

_ENTITY_REF_RE = re.compile(r"^[a-z][a-z0-9-]*:[A-Za-z0-9._-]+$")
_POSITIONAL_RE = re.compile(r"\[\d+\]")
_NAMESPACE_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

MAX_POINTER_LENGTH = 200


class SubjectError(ValueError):
    """A subject could not be normalized or is not permitted."""


def normalize_utf8_nfc(value: str) -> str:
    """Return the one storable NFC spelling, refusing invalid UTF-8 text."""
    normalized = unicodedata.normalize("NFC", value)
    try:
        normalized.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise SubjectError("identity string must be encodable as UTF-8") from exc
    return normalized


def normalize_identifier_namespace(value: str) -> str:
    """The one kebab-case namespace spelling accepted by declarations and subjects."""
    lowered = normalize_utf8_nfc(value).lower()
    if not _NAMESPACE_RE.match(lowered):
        raise SubjectError(f"namespace must be kebab-case, got {value!r}")
    return lowered


def normalize_project_path(raw: str) -> str:
    """Project-relative POSIX form.

    A `..` segment is REFUSED, never collapsed. `a/../b` does not become `b`: the
    design forbids traversal segments, and normalizing one away would accept a path
    on the strength of where it happens to land rather than on what it says. `.` and
    duplicate separators are collapsed, because neither is traversal.
    """
    if "\0" in raw:
        raise SubjectError("path contains a NUL character")
    candidate = normalize_utf8_nfc(raw).replace("\\", "/")
    if candidate.startswith("/"):
        raise SubjectError(f"path must be project-relative, got {raw!r}")
    segments = [s for s in candidate.split("/") if s not in ("", ".")]
    if any(segment == ".." for segment in segments):
        raise SubjectError(
            f"path contains a `..` segment and is refused, not normalized: {raw!r}"
        )
    if not segments:
        raise SubjectError(f"path names no file, got {raw!r}")
    return "/".join(segments)


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class EntitySubject(_Base):
    type: Literal["entity"] = "entity"
    ref: str

    @field_validator("ref")
    @classmethod
    def _canonical_ref(cls, value: str) -> str:
        normalized = normalize_utf8_nfc(value)
        if not _ENTITY_REF_RE.match(normalized):
            raise SubjectError(
                f"entity ref must be `<prefix>:<slug>`, got {normalized!r}"
            )
        return normalized


class PathSubject(_Base):
    type: Literal["path"] = "path"
    path: str
    pointer: str | None = None

    @field_validator("path")
    @classmethod
    def _normalize(cls, value: str) -> str:
        return normalize_project_path(value)

    @field_validator("pointer")
    @classmethod
    def _stable_pointer(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = normalize_utf8_nfc(value)
        if not normalized.strip():
            raise SubjectError("pointer must not be blank; omit it instead")
        if len(normalized) > MAX_POINTER_LENGTH:
            raise SubjectError(f"pointer exceeds {MAX_POINTER_LENGTH} characters")
        if _POSITIONAL_RE.search(normalized):
            raise SubjectError(
                f"pointer {normalized!r} contains a positional segment; identity must not "
                "depend on list position (design §2)"
            )
        return normalized


class IdentifierSubject(_Base):
    type: Literal["identifier"] = "identifier"
    namespace: str
    value: str

    @field_validator("namespace")
    @classmethod
    def _lower_namespace(cls, value: str) -> str:
        return normalize_identifier_namespace(value)

    @field_validator("value")
    @classmethod
    def _nonblank(cls, value: str) -> str:
        normalized = normalize_utf8_nfc(value)
        if not normalized.strip():
            raise SubjectError("identifier value must not be blank")
        return normalized


class ProjectSubject(_Base):
    type: Literal["project"] = "project"


FindingSubject = Annotated[
    Union[EntitySubject, PathSubject, IdentifierSubject, ProjectSubject],
    Field(discriminator="type"),
]

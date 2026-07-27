"""The four finding subjects (design §2).

One REQUIRED, discriminated primary subject. There is deliberately no
entity-then-path fallback: an invalid entity subject fails rather than silently
degrading to a path, which would change a case's identity unnoticed.
"""

from __future__ import annotations

import re
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator

_ENTITY_REF_RE = re.compile(r"^[a-z][a-z0-9-]*:[A-Za-z0-9._-]+$")
_POSITIONAL_RE = re.compile(r"\[\d+\]")
_NAMESPACE_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

MAX_POINTER_LENGTH = 200


class SubjectError(ValueError):
    """A subject could not be normalized or is not permitted."""


def normalize_project_path(raw: str) -> str:
    """Project-relative POSIX form.

    A `..` segment is REFUSED, never collapsed. `a/../b` does not become `b`: the
    design forbids traversal segments, and normalizing one away would accept a path
    on the strength of where it happens to land rather than on what it says. `.` and
    duplicate separators are collapsed, because neither is traversal.
    """
    candidate = raw.replace("\\", "/")
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
        if not _ENTITY_REF_RE.match(value):
            raise SubjectError(f"entity ref must be `<prefix>:<slug>`, got {value!r}")
        return value


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
        if not value.strip():
            raise SubjectError("pointer must not be blank; omit it instead")
        if len(value) > MAX_POINTER_LENGTH:
            raise SubjectError(f"pointer exceeds {MAX_POINTER_LENGTH} characters")
        if _POSITIONAL_RE.search(value):
            raise SubjectError(
                f"pointer {value!r} contains a positional segment; identity must not "
                "depend on list position (design §2)"
            )
        return value


class IdentifierSubject(_Base):
    type: Literal["identifier"] = "identifier"
    namespace: str
    value: str

    @field_validator("namespace")
    @classmethod
    def _lower_namespace(cls, value: str) -> str:
        lowered = value.lower()
        if not _NAMESPACE_RE.match(lowered):
            raise SubjectError(f"namespace must be kebab-case, got {value!r}")
        return lowered

    @field_validator("value")
    @classmethod
    def _nonblank(cls, value: str) -> str:
        if not value.strip():
            raise SubjectError("identifier value must not be blank")
        return value


class ProjectSubject(_Base):
    type: Literal["project"] = "project"


FindingSubject = Annotated[
    Union[EntitySubject, PathSubject, IdentifierSubject, ProjectSubject],
    Field(discriminator="type"),
]

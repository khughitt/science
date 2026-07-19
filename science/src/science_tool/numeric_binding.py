"""Fail-closed YAML binding schema for numeric-provenance entries.

Pure module -- no disk I/O. `validate_entry` is the single public entry point:
it takes a raw (already YAML-parsed) entry mapping and returns either a
`ParsedEntry` on success or a `BindingError` describing why the entry was
rejected. Every rejection path is deliberate: an entry that does not
unambiguously identify one locator shape, or that pairs `tolerance` with an
`opaque` locator, or that mismatches its declared artifact extension, is
refused rather than guessed at.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from science_tool.numeric_literal import parse_prose_literal
from science_tool.numeric_provenance import DocumentContext


class PointerLocator(BaseModel):
    """Locates a value via a JSON Pointer into a `.json` artifact."""

    model_config = ConfigDict(extra="forbid")

    pointer: str = Field(min_length=1)


class ColumnLocator(BaseModel):
    """Locates a value via a column (optionally filtered by `where`) in a `.feather` artifact."""

    model_config = ConfigDict(extra="forbid")

    column: str = Field(min_length=1)
    where: dict[str, Any] | None = None

    @model_validator(mode="after")
    def _where_non_empty_if_present(self) -> "ColumnLocator":
        if self.where is not None and len(self.where) == 0:
            raise ValueError("where must be a non-empty mapping when present")
        return self


class OpaqueLocator(BaseModel):
    """Locates a value by free-text description (e.g. 'read off panel B'). Any artifact extension."""

    model_config = ConfigDict(extra="forbid")

    opaque: str = Field(min_length=1)


# The locator's type dictates the extension its artifact must carry. A locator
# type absent from this map (currently just OpaqueLocator) is unconstrained --
# opaque claims may point at any artifact extension.
_REQUIRED_EXTENSION_BY_LOCATOR: dict[type[BaseModel], str] = {
    PointerLocator: ".json",
    ColumnLocator: ".feather",
}

_LOCATOR_MODELS: tuple[type[BaseModel], ...] = (PointerLocator, ColumnLocator, OpaqueLocator)


class _EntryModel(BaseModel):
    """Entry-level shape: only `artifact`, `locator`, and optional `tolerance` are legal."""

    model_config = ConfigDict(extra="forbid")

    artifact: str = Field(min_length=1)
    locator: dict[str, Any]
    tolerance: Any = None


@dataclass(frozen=True)
class ParsedEntry:
    artifact: str
    locator: PointerLocator | ColumnLocator | OpaqueLocator
    tolerance: Decimal | None


@dataclass(frozen=True)
class BindingError:
    id: str | None
    line: int | None
    message: str


def validate_entry(id: str, raw: Any, artifact_ext: str) -> ParsedEntry | BindingError:
    """Validate one raw binding entry. Fail-closed: any ambiguity or malformation rejects.

    On success, returns a `ParsedEntry` holding the resolved locator (exactly one of
    `PointerLocator`, `ColumnLocator`, `OpaqueLocator`) and the parsed `tolerance`
    (`None` if absent). On any failure -- non-mapping entry, schema violation, ambiguous
    or absent locator shape, artifact-extension mismatch, or an invalid `tolerance` --
    returns a `BindingError` describing the first problem found.
    """
    if not isinstance(raw, Mapping):
        return BindingError(id, None, "entry must be a mapping")

    try:
        entry = _EntryModel.model_validate(raw)
    except ValidationError as exc:
        return BindingError(id, None, str(exc))

    if not isinstance(entry.locator, Mapping):
        return BindingError(id, None, "locator must be a mapping")

    matches: list[BaseModel] = []
    for model_cls in _LOCATOR_MODELS:
        try:
            matches.append(model_cls.model_validate(entry.locator))
        except ValidationError:
            continue

    if len(matches) != 1:
        return BindingError(
            id, None, "locator must match exactly one of {pointer, column, opaque} with a non-empty value"
        )

    locator = matches[0]

    required_ext = _REQUIRED_EXTENSION_BY_LOCATOR.get(type(locator))
    if required_ext is not None and artifact_ext != required_ext:
        return BindingError(
            id, None, f"{type(locator).__name__} requires artifact extension {required_ext!r}, got {artifact_ext!r}"
        )

    tolerance: Decimal | None = None
    if entry.tolerance is not None:
        if isinstance(locator, OpaqueLocator):
            return BindingError(id, None, "tolerance is forbidden together with an opaque locator")
        try:
            tolerance = Decimal(str(entry.tolerance))
        except InvalidOperation:
            return BindingError(id, None, f"tolerance is not a valid decimal number: {entry.tolerance!r}")
        if not tolerance.is_finite():
            return BindingError(id, None, "tolerance must be finite")
        if not tolerance > 0:
            return BindingError(id, None, "tolerance must be > 0")

    return ParsedEntry(artifact=entry.artifact, locator=locator, tolerance=tolerance)


# --- Marker attachment: `[^id]` footnote-style pins in body prose -----------
#
# A `numeric_claims` frontmatter mapping declares *where* each claimed value
# lives; `parse_claim_bindings` finds *which prose token* it pins by locating
# the single `[^id]` marker for that id in the body and reading the numeric-ish
# run immediately preceding it. This keeps the YAML binding schema (above)
# decoupled from prose scanning -- `validate_entry` never sees a document,
# and this function never invents locator/tolerance semantics of its own.

_MARKER_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")
_MARKER_RE = re.compile(r"\[\^([A-Za-z0-9_-]+)\]")
# Maximal contiguous numeric-ish run immediately before a marker, after
# stripping trailing bold/italic markup (`*`) and whitespace. Deliberately
# does NOT strip `)` -- a closing paren right before the marker is left in
# place so it fails `parse_prose_literal` rather than being silently dropped.
_TOKEN_RE = re.compile(r"([-+0-9.,eE/×%–]+)\s*\**\s*$")


@dataclass(frozen=True)
class ClaimBinding:
    id: str
    artifact: str
    locator: PointerLocator | ColumnLocator | OpaqueLocator
    tolerance: Decimal | None
    span: tuple[int, int, int]   # (line, col_start, col_end), 1-based, col_end exclusive
    value_text: str              # the pinned prose token; always a numeric literal


def parse_claim_bindings(document: DocumentContext) -> tuple[list[ClaimBinding], list[BindingError]]:
    """Attach each `numeric_claims` entry to its `[^id]` marker in the body prose.

    Fail-closed at every step: a malformed `numeric_claims` mapping, an id
    outside the marker charset, a missing/duplicated marker, a non-numeric
    pinned token, or a `validate_entry` rejection each produce a `BindingError`
    and no binding for that id. Real footnotes (`[^x]` where `x` is not a
    declared claim id) are left untouched.
    """
    claims = document.frontmatter.get("numeric_claims") if isinstance(document.frontmatter, Mapping) else None
    if not isinstance(claims, Mapping):
        return [], [BindingError(None, None, "numeric_claims frontmatter must be a mapping")]

    errors: list[BindingError] = []
    valid_entries: dict[str, Any] = {}
    for raw_id, raw_entry in claims.items():
        if not isinstance(raw_id, str) or not _MARKER_ID_RE.match(raw_id):
            errors.append(
                BindingError(
                    raw_id if isinstance(raw_id, str) else str(raw_id),
                    None,
                    f"claim id {raw_id!r} does not match the marker charset ^[A-Za-z0-9_-]+$ "
                    "and can never be referenced by a [^id] marker",
                )
            )
            continue
        valid_entries[raw_id] = raw_entry

    # Scan body lines only -- frontmatter is never prose to pin against.
    occurrences: dict[str, list[tuple[int, re.Match[str]]]] = {}
    for lineno in range(document.body_start, len(document.lines) + 1):
        line = document.lines[lineno - 1]
        for m in _MARKER_RE.finditer(line):
            marker_id = m.group(1)
            if marker_id in valid_entries:
                occurrences.setdefault(marker_id, []).append((lineno, m))

    bindings: list[ClaimBinding] = []
    for claim_id, raw_entry in valid_entries.items():
        occ = occurrences.get(claim_id, [])
        if len(occ) == 0:
            errors.append(BindingError(claim_id, None, f"claim {claim_id!r} has no [^{claim_id}] marker in the body"))
            continue
        if len(occ) > 1:
            lineno, _ = occ[0]
            errors.append(
                BindingError(
                    claim_id, lineno,
                    f"claim {claim_id!r} has {len(occ)} [^{claim_id}] markers in the body; expected exactly one",
                )
            )
            continue

        lineno, marker_match = occ[0]
        line = document.lines[lineno - 1]
        prefix = line[: marker_match.start()]
        token_match = _TOKEN_RE.search(prefix)
        token = token_match.group(1) if token_match is not None else ""

        parsed = parse_prose_literal(token)
        if parsed is None:
            errors.append(
                BindingError(claim_id, lineno, f"pinned token {token!r} before [^{claim_id}] is not a single numeric literal")
            )
            continue

        artifact = raw_entry.get("artifact") if isinstance(raw_entry, Mapping) else None
        artifact_ext = Path(artifact).suffix if isinstance(artifact, str) and artifact else ""
        validated = validate_entry(claim_id, raw_entry, artifact_ext)
        if isinstance(validated, BindingError):
            errors.append(validated)
            continue

        col_start = token_match.start(1) + 1
        col_end = token_match.end(1) + 1
        bindings.append(
            ClaimBinding(
                id=claim_id,
                artifact=validated.artifact,
                locator=validated.locator,
                tolerance=validated.tolerance,
                span=(lineno, col_start, col_end),
                value_text=token,
            )
        )

    return bindings, errors

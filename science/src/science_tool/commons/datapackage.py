"""Reader for the Frictionless datapackage.yaml sidecar of a commons dataset.

Phase C only needs resources[].path + resources[].hash; schemas, dialects and
other Frictionless fields are ignored. See
docs/plans/2026-05-14-commons-data-resolver-design.md §5.2.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

import yaml

from science_tool.commons.errors import CommonsDatapackageError, DataLogicalPathError

_SHA256_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_DRIVE_LETTER = re.compile(r"^[A-Za-z]:")


def validate_logical_path(logical_path: str) -> str:
    """Assert a logical path is a safe forward-slash relative path within a dataset.

    Returns the path unchanged on success. Raises `DataLogicalPathError` on any
    unsafe form: empty/whitespace, backslash-containing, a Windows drive-letter
    form, absolute, containing a `..` parent-traversal segment, or any path that
    does not round-trip cleanly as a normalized forward-slash relative path
    (this catches `.` segments, trailing slashes, and doubled slashes).
    """
    if not logical_path or not logical_path.strip():
        raise DataLogicalPathError(logical_path, reason="path is empty")
    if logical_path == ".":
        raise DataLogicalPathError(logical_path, reason="path must name a resource file")
    if "\\" in logical_path:
        raise DataLogicalPathError(
            logical_path,
            reason="backslashes are not allowed; use forward slashes",
        )
    if _DRIVE_LETTER.match(logical_path):
        raise DataLogicalPathError(
            logical_path, reason="Windows drive-letter paths are not allowed"
        )
    if PurePosixPath(logical_path).is_absolute():
        raise DataLogicalPathError(logical_path, reason="path must be relative")
    if ".." in PurePosixPath(logical_path).parts:
        raise DataLogicalPathError(
            logical_path, reason="path may not contain '..' segments"
        )
    if str(PurePosixPath(logical_path)) != logical_path:
        raise DataLogicalPathError(
            logical_path,
            reason="path must be a normalized forward-slash relative path",
        )
    return logical_path


def parse_resource_hash(raw: str) -> tuple[str, str]:
    """Parse a 'sha256:<64 lowercase hex>' string into (algorithm, hexdigest).

    Phase C accepts only sha256. Raises `ValueError` on a missing prefix, an
    unsupported algorithm, or a malformed digest. (`read_datapackage` wraps this
    into a `CommonsDatapackageError` that names the descriptor file.)
    """
    if not isinstance(raw, str) or ":" not in raw:
        raise ValueError(
            f"hash {raw!r} must be of the form 'sha256:<64 hex chars>'"
        )
    algorithm, _, digest = raw.partition(":")
    if algorithm != "sha256":
        raise ValueError(
            f"unsupported hash algorithm {algorithm!r}; Phase C accepts only sha256"
        )
    if not _SHA256_DIGEST.fullmatch(digest):
        raise ValueError(
            f"malformed sha256 digest {digest!r}; expected 64 lowercase hex chars"
        )
    return (algorithm, digest)


@dataclass(frozen=True, slots=True)
class DataResource:
    """One resource entry from a datapackage.yaml."""

    path: str  # validated forward-slash relative logical path
    hash: str  # full "sha256:<hex>" string, verbatim from resources[].hash
    bytes: int | None = None  # resources[].bytes if present
    format: str | None = None  # resources[].format if present
    mediatype: str | None = None  # resources[].mediatype if present


@dataclass(frozen=True, slots=True)
class DatapackageDescriptor:
    """The Phase C view of a datapackage.yaml: its source path + its resources."""

    source_path: Path
    resources: tuple[DataResource, ...]

    def resource(self, logical_path: str) -> DataResource:
        """Return the resource with the given logical path.

        Raises `CommonsDatapackageError` (naming `source_path`) if absent.
        """
        for resource in self.resources:
            if resource.path == logical_path:
                return resource
        raise CommonsDatapackageError(
            self.source_path,
            reason=f"no resource with logical path {logical_path!r}",
        )


def read_datapackage(path: Path) -> DatapackageDescriptor:
    """Parse a datapackage.yaml into a `DatapackageDescriptor`.

    Raises `CommonsDatapackageError` on unreadable/malformed YAML, a missing or
    empty `resources` list, a resource with a missing/invalid `path`, a
    duplicate logical path, or a resource with a missing/malformed `hash`.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CommonsDatapackageError(path, reason=f"cannot read file: {exc}") from exc
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise CommonsDatapackageError(path, reason=f"malformed YAML: {exc}") from exc

    if not isinstance(raw, dict):
        raise CommonsDatapackageError(path, reason="top level is not a mapping")
    raw_resources = raw.get("resources")
    if not isinstance(raw_resources, list) or not raw_resources:
        raise CommonsDatapackageError(
            path, reason="missing or empty 'resources' list"
        )

    resources: list[DataResource] = []
    seen: set[str] = set()
    for index, entry in enumerate(raw_resources):
        if not isinstance(entry, dict):
            raise CommonsDatapackageError(
                path, reason=f"resources[{index}] is not a mapping"
            )

        raw_path = entry.get("path")
        if not isinstance(raw_path, str):
            raise CommonsDatapackageError(
                path,
                reason=f"resources[{index}] has a missing or non-string 'path'",
            )
        try:
            logical_path = validate_logical_path(raw_path)
        except DataLogicalPathError as exc:
            raise CommonsDatapackageError(
                path,
                reason=f"resources[{index}] has an invalid path: {exc.reason}",
            ) from exc
        if logical_path in seen:
            raise CommonsDatapackageError(
                path, reason=f"duplicate resource path {logical_path!r}"
            )
        seen.add(logical_path)

        raw_hash = entry.get("hash")
        if not isinstance(raw_hash, str):
            raise CommonsDatapackageError(
                path,
                reason=(
                    f"resources[{index}] ({logical_path}) has a missing or "
                    f"non-string 'hash'"
                ),
            )
        try:
            parse_resource_hash(raw_hash)
        except ValueError as exc:
            raise CommonsDatapackageError(
                path,
                reason=f"resources[{index}] ({logical_path}) has an invalid hash: {exc}",
            ) from exc

        raw_bytes = entry.get("bytes")
        if raw_bytes is not None and (
            not isinstance(raw_bytes, int) or isinstance(raw_bytes, bool)
        ):
            raise CommonsDatapackageError(
                path,
                reason=(
                    f"resources[{index}] ({logical_path}) has a non-integer 'bytes'"
                ),
            )
        raw_format = entry.get("format")
        if raw_format is not None and not isinstance(raw_format, str):
            raise CommonsDatapackageError(
                path,
                reason=f"resources[{index}] ({logical_path}) has a non-string 'format'",
            )
        raw_mediatype = entry.get("mediatype")
        if raw_mediatype is not None and not isinstance(raw_mediatype, str):
            raise CommonsDatapackageError(
                path,
                reason=(
                    f"resources[{index}] ({logical_path}) has a non-string 'mediatype'"
                ),
            )

        resources.append(
            DataResource(
                path=logical_path,
                hash=raw_hash,
                bytes=raw_bytes,
                format=raw_format,
                mediatype=raw_mediatype,
            )
        )

    return DatapackageDescriptor(source_path=path, resources=tuple(resources))

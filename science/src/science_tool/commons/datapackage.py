"""Reader for the Frictionless datapackage.yaml sidecar of a commons dataset.

Phase C only needs resources[].path + resources[].hash; schemas, dialects and
other Frictionless fields are ignored. See
docs/plans/2026-05-14-commons-data-resolver-design.md §5.2.
"""

from __future__ import annotations

import re
from pathlib import PurePosixPath

from science_tool.commons.errors import DataLogicalPathError

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

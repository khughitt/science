"""Error hierarchy for the commons subpackage."""

from __future__ import annotations

from pathlib import Path


class CommonsError(Exception):
    """Base class for all commons-layer errors."""


class CommonsRootNotFoundError(CommonsError):
    """The configured commons store root does not exist on disk."""

    def __init__(self, root: Path) -> None:
        super().__init__(
            f"commons store not found at {root}; run `science commons init` to create it"
        )
        self.root = root


class CommonsRootMalformedError(CommonsError):
    """The root exists but does not look like a commons store."""

    def __init__(self, root: Path, *, missing: list[str]) -> None:
        super().__init__(
            f"commons store at {root} is malformed; missing: {', '.join(missing)}"
        )
        self.root = root
        self.missing = missing


class CommonsLayoutError(CommonsError):
    """Filesystem layout invariant violated (e.g., dataset missing datapackage.yaml)."""

    def __init__(self, path: Path, *, reason: str) -> None:
        super().__init__(f"commons layout error at {path}: {reason}")
        self.path = path
        self.reason = reason


class CommonsEntityError(CommonsError):
    """A single entity failed parsing or schema validation."""

    def __init__(
        self,
        path: Path,
        *,
        canonical_id: str | None,
        cause: Exception,
    ) -> None:
        super().__init__(f"commons entity {path} failed: {cause}")
        self.path = path
        self.canonical_id = canonical_id
        self.cause = cause


class CommonsRegistryError(CommonsError):
    """SQLite-level failure (corruption, locked file, schema mismatch)."""

    def __init__(self, db_path: Path, *, cause: Exception) -> None:
        super().__init__(f"commons registry at {db_path} failed: {cause}")
        self.db_path = db_path
        self.cause = cause


class CommonsDatapackageError(CommonsError):
    """A datapackage.yaml is malformed, missing resources[], has an invalid or
    duplicate resource path, or has a resource with a missing/malformed hash."""

    def __init__(self, path: Path, *, reason: str) -> None:
        super().__init__(f"commons datapackage error at {path}: {reason}")
        self.path = path
        self.reason = reason


class DataLogicalPathError(CommonsError):
    """A logical path string is not a safe forward-slash relative path.

    Carries the offending string (not a Path) so a bad CLI argument is not
    forced to masquerade as a datapackage file.
    """

    def __init__(self, logical_path: str, *, reason: str) -> None:
        super().__init__(f"invalid logical path {logical_path!r}: {reason}")
        self.logical_path = logical_path
        self.reason = reason


class DataResourceNotFoundError(CommonsError):
    """The bytes for a resource were not found in any lookup source."""

    def __init__(
        self, dataset_id: str, logical_path: str, *, tried: list[Path]
    ) -> None:
        tried_str = ", ".join(str(p) for p in tried)
        super().__init__(
            f"data resource {dataset_id} / {logical_path} not found; tried: {tried_str}"
        )
        self.dataset_id = dataset_id
        self.logical_path = logical_path
        self.tried = tried


class DataIntegrityError(CommonsError):
    """A resource file was found but its sha256 does not match the expected hash."""

    def __init__(self, path: Path, *, expected: str, actual: str) -> None:
        super().__init__(
            f"data integrity error at {path}: expected {expected}, got {actual}"
        )
        self.path = path
        self.expected = expected
        self.actual = actual

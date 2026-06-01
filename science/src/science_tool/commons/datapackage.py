"""Reader for the Frictionless datapackage.yaml sidecar of a commons dataset.

Phase C only needs resources[].path + resources[].hash; schemas, dialects and
other Frictionless fields are ignored. See
docs/plans/2026-05-14-commons-data-resolver-design.md §5.2.
"""

from __future__ import annotations

import os
import re
import urllib.parse
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import final

import yaml

from science_tool.commons.errors import (
    CommonsDatapackageError,
    CommonsError,
    DataLogicalPathError,
)

_SHA256_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_DRIVE_LETTER = re.compile(r"^[A-Za-z]:")
_PROJECT_ONLY_DATAPACKAGE_KEYS = frozenset({"id", "conformsTo", "mm30", "derivedFrom"})
_RESOURCE_COMPUTED_KEYS = frozenset({"hash", "bytes"})

SOURCE_TYPES = frozenset({"local", "zenodo", "github", "url", "daemon"})
OUTPUT_ROOT_TOKEN = "${OUTPUT_ROOT}"


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


def validate_source(raw: object) -> ResourceSource:
    """Validate a resource `source` mapping and return a `ResourceSource`.

    Raises `ValueError` on any unsafe/malformed form. Callers wrap this into
    their own error type. Only `local` and `url` refs are shape-checked beyond
    "non-empty string"; the other remote kinds are opaque this iteration.
    """
    if not isinstance(raw, dict):
        raise ValueError("source must be a mapping with 'type' and 'ref'")
    type_ = raw.get("type")
    if type_ not in SOURCE_TYPES:
        raise ValueError(
            f"source.type {type_!r} is not one of {sorted(SOURCE_TYPES)}"
        )
    ref = raw.get("ref")
    if not isinstance(ref, str) or not ref.strip():
        raise ValueError(f"source.ref must be a non-empty string, got {ref!r}")

    if type_ == "local":
        _validate_local_ref_shape(ref)
    elif type_ == "url":
        parsed = urllib.parse.urlparse(ref)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError(
                f"url source.ref must be an absolute http(s) URL with a host, got {ref!r}"
            )
    # zenodo / github / daemon: opaque non-empty string (already checked).
    return ResourceSource(type=type_, ref=ref)


def _validate_local_ref_shape(ref: str) -> None:
    """Allow only: an absolute path, exactly `${OUTPUT_ROOT}`, or `${OUTPUT_ROOT}/...`."""
    if ref == OUTPUT_ROOT_TOKEN or (
        ref.startswith(OUTPUT_ROOT_TOKEN + "/")
        and len(ref) > len(OUTPUT_ROOT_TOKEN) + 1
    ):
        return
    if "${" in ref:
        raise ValueError(
            f"local source.ref {ref!r} uses an unsupported or malformed token; "
            f"only {OUTPUT_ROOT_TOKEN} (bare or followed by '/') is allowed"
        )
    if not PurePosixPath(ref).is_absolute():
        raise ValueError(
            f"local source.ref {ref!r} must be absolute or use the "
            f"{OUTPUT_ROOT_TOKEN} token; a plain relative path is ambiguous"
        )


class RefResolution:
    """Sealed result of resolving a `local` source ref on this host."""


@final
@dataclass(frozen=True, slots=True)
class Unexpandable(RefResolution):
    """The ref carries the `${OUTPUT_ROOT}` token but OUTPUT_ROOT is unset.

    Reported as `skipped_off_host` by promote — non-fatal.
    """

    ref: str


@final
@dataclass(frozen=True, slots=True)
class Resolved(RefResolution):
    """The ref resolved to a concrete local path (which may or may not exist)."""

    path: Path
    exists: bool


def resolve_local_ref(ref: str) -> RefResolution:
    """Resolve a validated `local` source ref against this host.

    - absolute ref → `Resolved(path, exists)`.
    - `${OUTPUT_ROOT}`-token ref, OUTPUT_ROOT unset → `Unexpandable` (off-host).
    - `${OUTPUT_ROOT}`-token ref, OUTPUT_ROOT set to an absolute path →
      `Resolved(expanded_path, exists)`.

    Raises `ValueError` only on a configuration error that blocks resolution:
    OUTPUT_ROOT set but blank or relative. (Malformed refs are already rejected
    by `validate_source`; this function assumes a validated ref.)
    """
    if ref == OUTPUT_ROOT_TOKEN or ref.startswith(OUTPUT_ROOT_TOKEN + "/"):
        root = os.environ.get("OUTPUT_ROOT")
        if root is None:
            return Unexpandable(ref=ref)
        if not root.strip() or not Path(root).is_absolute():
            raise ValueError(
                f"OUTPUT_ROOT must be a non-blank absolute path to expand {ref!r}; "
                f"got {root!r}"
            )
        suffix = ref[len(OUTPUT_ROOT_TOKEN):].lstrip("/")
        path = Path(root) / suffix if suffix else Path(root)
        return Resolved(path=path, exists=path.exists())
    # validate_source guarantees the only remaining shape is an absolute path.
    path = Path(ref)
    return Resolved(path=path, exists=path.exists())


def stream_sha256_and_bytes(path: Path) -> tuple[str, int]:
    """Return (`sha256:<hex>`, byte_count) streaming the file in 1 MiB chunks."""
    import hashlib

    h = hashlib.sha256()
    n = 0
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
            n += len(chunk)
    return f"sha256:{h.hexdigest()}", n


def render_canonical_datapackage_yaml(
    *,
    project_doc: dict,
    canonical_slug: str,
    per_resource: dict[str, tuple[str, int]],
) -> str:
    """Render a canonical commons datapackage.yaml from a project descriptor."""
    if not isinstance(project_doc, dict):
        raise CommonsError("project datapackage document must be a mapping")

    out = {"name": canonical_slug}
    for key, value in project_doc.items():
        if key in _PROJECT_ONLY_DATAPACKAGE_KEYS or key in {"name", "resources"}:
            continue
        out[key] = value

    raw_resources = project_doc.get("resources")
    if not isinstance(raw_resources, list) or not raw_resources:
        raise CommonsError("project datapackage has a missing or empty 'resources' list")
    _validate_resource_aliases(raw_resources)

    resources = []
    for index, resource in enumerate(raw_resources):
        if not isinstance(resource, dict):
            raise CommonsError(f"resources[{index}] is not a mapping")
        rendered_resource = {
            key: value
            for key, value in resource.items()
            if key not in _RESOURCE_COMPUTED_KEYS
        }
        resource_hash, resource_bytes = _metadata_for_resource(
            resource=rendered_resource,
            resource_index=index,
            per_resource=per_resource,
        )
        rendered_resource["hash"] = resource_hash
        rendered_resource["bytes"] = resource_bytes
        resources.append(rendered_resource)
    out["resources"] = resources

    return yaml.safe_dump(out, sort_keys=False, allow_unicode=True)


def _validate_resource_aliases(resources: list) -> None:
    aliases: dict[str, int] = {}
    for index, resource in enumerate(resources):
        if not isinstance(resource, dict):
            raise CommonsError(f"resources[{index}] is not a mapping")
        for alias in _resource_aliases(resource):
            previous_index = aliases.get(alias)
            if previous_index is not None and previous_index != index:
                raise CommonsError(
                    f"ambiguous resource alias {alias!r} used by "
                    f"resources[{previous_index}] and resources[{index}]"
                )
            aliases[alias] = index


def _resource_aliases(resource: dict) -> set[str]:
    aliases = set()
    for field in ("name", "path"):
        value = resource.get(field)
        if isinstance(value, str):
            aliases.add(value)
    return aliases


def _metadata_for_resource(
    *,
    resource: dict,
    resource_index: int,
    per_resource: dict[str, tuple[str, int]],
) -> tuple[str, int]:
    matches = {
        key: per_resource[key]
        for key in _resource_aliases(resource)
        if key in per_resource
    }
    if not matches:
        raise CommonsError(
            f"resources[{resource_index}] is missing computed hash/bytes metadata"
        )

    metadata_values = set(matches.values())
    if len(metadata_values) > 1:
        raise CommonsError(
            f"resources[{resource_index}] has conflicting computed metadata aliases"
        )

    return next(iter(metadata_values))


def parse_canonical_datapackage_yaml(yaml_text: str) -> dict:
    """Parse and validate a canonical commons datapackage.yaml document."""
    try:
        raw = yaml.safe_load(yaml_text)
    except yaml.YAMLError as exc:
        raise CommonsError(f"malformed canonical datapackage YAML: {exc}") from exc

    if not isinstance(raw, dict):
        raise CommonsError("canonical datapackage top level is not a mapping")
    if not isinstance(raw.get("name"), str):
        raise CommonsError("canonical datapackage has a missing or non-string 'name'")

    raw_resources = raw.get("resources")
    if not isinstance(raw_resources, list) or not raw_resources:
        raise CommonsError("canonical datapackage has a missing or empty 'resources' list")

    seen_paths: set[str] = set()
    for index, entry in enumerate(raw_resources):
        if not isinstance(entry, dict):
            raise CommonsError(f"resources[{index}] is not a mapping")

        raw_path = entry.get("path")
        if not isinstance(raw_path, str):
            raise CommonsError(
                f"resources[{index}] has a missing or non-string 'path'"
            )
        try:
            logical_path = validate_logical_path(raw_path)
        except DataLogicalPathError as exc:
            raise CommonsError(
                f"resources[{index}] has an invalid path: {exc.reason}"
            ) from exc
        if logical_path in seen_paths:
            raise CommonsError(f"duplicate resource path {logical_path!r}")
        seen_paths.add(logical_path)

        raw_hash = entry.get("hash")
        if not isinstance(raw_hash, str):
            raise CommonsError(
                f"resources[{index}] ({logical_path}) has a missing or non-string 'hash'"
            )
        try:
            parse_resource_hash(raw_hash)
        except ValueError as exc:
            raise CommonsError(
                f"resources[{index}] ({logical_path}) has an invalid hash: {exc}"
            ) from exc

        raw_bytes = entry.get("bytes")
        if (
            not isinstance(raw_bytes, int)
            or isinstance(raw_bytes, bool)
            or raw_bytes < 0
        ):
            raise CommonsError(
                f"resources[{index}] ({logical_path}) has a missing or invalid 'bytes'"
            )

        raw_source = entry.get("source")
        if raw_source is not None:
            try:
                validate_source(raw_source)
            except ValueError as exc:
                raise CommonsError(
                    f"resources[{index}] ({logical_path}) has an invalid source: {exc}"
                ) from exc

    return raw


@dataclass(frozen=True, slots=True)
class DataResource:
    """One resource entry from a datapackage.yaml."""

    path: str  # validated forward-slash relative logical path
    hash: str  # full "sha256:<hex>" string, verbatim from resources[].hash
    name: str | None = None  # resources[].name if present
    bytes: int | None = None  # resources[].bytes if present
    format: str | None = None  # resources[].format if present
    mediatype: str | None = None  # resources[].mediatype if present
    source: ResourceSource | None = None  # resources[].source if present


@dataclass(frozen=True, slots=True)
class ResourceSource:
    """An off-repo origin for a content-addressed resource.

    `type` is one of SOURCE_TYPES; `ref` is the type-specific locator (a
    filesystem path or `${OUTPUT_ROOT}` token for `local`, an http(s) URL for
    `url`, an opaque non-empty string for the remote kinds).
    """

    type: str
    ref: str


@dataclass(frozen=True, slots=True)
class DatapackageDescriptor:
    """The Phase C view of a datapackage.yaml: its source path + its resources."""

    source_path: Path
    resources: tuple[DataResource, ...]

    def resource(self, logical_path: str) -> DataResource:
        """Return the resource with the given logical path or resource name.

        Raises `CommonsDatapackageError` (naming `source_path`) if absent.
        """
        for resource in self.resources:
            if resource.path == logical_path or resource.name == logical_path:
                return resource
        raise CommonsDatapackageError(
            self.source_path,
            reason=f"no resource with logical path or name {logical_path!r}",
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
    aliases: dict[str, int] = {}
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

        raw_name = entry.get("name")
        if raw_name is not None and (not isinstance(raw_name, str) or not raw_name.strip()):
            raise CommonsDatapackageError(
                path,
                reason=f"resources[{index}] ({logical_path}) has a blank or non-string 'name'",
            )
        for alias in {logical_path, raw_name} - {None}:
            assert isinstance(alias, str)
            previous = aliases.get(alias)
            if previous is not None and previous != index:
                raise CommonsDatapackageError(
                    path,
                    reason=(
                        f"ambiguous resource alias {alias!r} used by "
                        f"resources[{previous}] and resources[{index}]"
                    ),
                )
            aliases[alias] = index

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

        raw_source = entry.get("source")
        source = None
        if raw_source is not None:
            try:
                source = validate_source(raw_source)
            except ValueError as exc:
                raise CommonsDatapackageError(
                    path,
                    reason=f"resources[{index}] ({logical_path}) has an invalid source: {exc}",
                ) from exc

        resources.append(
            DataResource(
                path=logical_path,
                hash=raw_hash,
                name=raw_name,
                bytes=raw_bytes,
                format=raw_format,
                mediatype=raw_mediatype,
                source=source,
            )
        )

    return DatapackageDescriptor(source_path=path, resources=tuple(resources))

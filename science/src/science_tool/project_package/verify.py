"""Integrity self-checks for serialized project-package bundles."""

from __future__ import annotations

import hashlib
import tarfile
import zlib
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from science_tool.project_package.core import content_version
from science_tool.project_package.manifest import SerializedManifest, data_version_chunks

MAX_ARCHIVE_MEMBERS = 50_000
MAX_MEMBER_BYTES = 100 * 1024 * 1024
MAX_TOTAL_UNCOMPRESSED_BYTES = 1024 * 1024 * 1024


class VerifyError(Exception):
    """Raised for operational/precondition failures."""


class BundleIntegrityError(Exception):
    """Raised when a bundle is malformed or fails integrity checks."""


@dataclass(frozen=True)
class LoadedBundle:
    project_id: str
    manifest: SerializedManifest
    manifest_bytes: bytes
    members: dict[str, bytes]


def load_bundle(bundle_path: Path) -> LoadedBundle:
    """Load and integrity-check a gzip+tar project bundle."""
    if not bundle_path.exists():
        raise VerifyError(f"bundle does not exist: {bundle_path}")
    if not bundle_path.is_file():
        raise VerifyError(f"bundle path is not a file: {bundle_path}")

    try:
        archived = _read_archive(bundle_path)
    except (FileNotFoundError, PermissionError) as exc:
        raise VerifyError(f"bundle is not readable: {bundle_path}") from exc
    except (tarfile.TarError, EOFError, OSError, zlib.error) as exc:
        raise BundleIntegrityError(f"bundle is not a valid gzip tar: {bundle_path}") from exc

    prefix = _single_prefix(archived)
    manifest_name = f"{prefix}/manifest.json"
    try:
        manifest_bytes = archived[manifest_name]
    except KeyError as exc:
        raise BundleIntegrityError(f"bundle is missing manifest member: {manifest_name}") from exc

    try:
        manifest = SerializedManifest.model_validate_json(manifest_bytes)
    except ValidationError as exc:
        raise BundleIntegrityError(f"invalid manifest.json: {exc}") from exc

    if prefix != manifest.project.id:
        raise BundleIntegrityError(
            f"archive prefix {prefix!r} does not match manifest project id {manifest.project.id!r}"
        )

    members = {name.removeprefix(f"{prefix}/"): data for name, data in archived.items() if name != manifest_name}
    _verify_source_members(members, manifest)
    _verify_data_version(manifest)

    return LoadedBundle(
        project_id=manifest.project.id,
        manifest=manifest,
        manifest_bytes=manifest_bytes,
        members=members,
    )


def _read_archive(bundle_path: Path) -> dict[str, bytes]:
    members: dict[str, bytes] = {}
    seen: set[str] = set()
    total_size = 0
    with tarfile.open(bundle_path, "r:gz") as tar:
        while member := tar.next():
            if len(seen) >= MAX_ARCHIVE_MEMBERS:
                raise BundleIntegrityError(f"archive member count exceeds limit: {MAX_ARCHIVE_MEMBERS}")
            _validate_member(member, seen=seen)
            total_size = _checked_total_size(total_size, member)
            fileobj = tar.extractfile(member)
            if fileobj is None:
                raise BundleIntegrityError(f"cannot read regular member: {member.name}")
            data = fileobj.read()
            if len(data) != member.size:
                raise BundleIntegrityError(
                    f"archive member size changed while reading {member.name}: header={member.size} read={len(data)}"
                )
            seen.add(member.name)
            members[member.name] = data
    return members


def _validate_member(member: tarfile.TarInfo, *, seen: set[str]) -> None:
    name = member.name
    if name in seen:
        raise BundleIntegrityError(f"duplicate archive member: {name}")
    if not member.isfile():
        raise BundleIntegrityError(f"archive member is not a regular file: {name}")
    _validate_member_name(name)
    if member.size < 0:
        raise BundleIntegrityError(f"archive member has negative size: {name}")
    if member.size > MAX_MEMBER_BYTES:
        raise BundleIntegrityError(
            f"archive member exceeds size limit ({MAX_MEMBER_BYTES} bytes): {name} ({member.size} bytes)"
        )


def _validate_member_name(name: str) -> None:
    parts = name.split("/")
    if (
        name == ""
        or name.startswith("/")
        or "\\" in name
        or "\0" in name
        or any(part in ("", ".", "..") for part in parts)
    ):
        raise BundleIntegrityError(f"unsafe archive member path: {name!r}")
    if len(parts) < 2:
        raise BundleIntegrityError(f"archive member lacks project prefix: {name!r}")


def _single_prefix(members: dict[str, bytes]) -> str:
    if not members:
        raise BundleIntegrityError("bundle contains no members")
    prefixes = {name.split("/", 1)[0] for name in members}
    if len(prefixes) != 1:
        raise BundleIntegrityError(f"bundle uses mixed project prefixes: {sorted(prefixes)}")
    return next(iter(prefixes))


def _checked_total_size(total_size: int, member: tarfile.TarInfo) -> int:
    next_total = total_size + member.size
    if next_total > MAX_TOTAL_UNCOMPRESSED_BYTES:
        raise BundleIntegrityError(
            "archive total uncompressed size exceeds limit "
            f"({MAX_TOTAL_UNCOMPRESSED_BYTES} bytes) at {member.name}: "
            f"{next_total} bytes"
        )
    return next_total


def _verify_source_members(
    members: dict[str, bytes],
    manifest: SerializedManifest,
) -> None:
    expected = {record.path for record in manifest.files}
    actual = set(members)
    missing = expected - actual
    extra = actual - expected
    if missing or extra:
        details = []
        if missing:
            details.append(f"missing={sorted(missing)}")
        if extra:
            details.append(f"extra={sorted(extra)}")
        raise BundleIntegrityError("source member set does not match manifest: " + ", ".join(details))

    records = {record.path: record for record in manifest.files}
    for path, data in members.items():
        record = records[path]
        digest = hashlib.sha256(data).hexdigest()
        if digest != record.sha256:
            raise BundleIntegrityError(f"sha256 mismatch for {path}: archive={digest} manifest={record.sha256}")
        if len(data) != record.bytes:
            raise BundleIntegrityError(f"byte count mismatch for {path}: archive={len(data)} manifest={record.bytes}")


def _verify_data_version(manifest: SerializedManifest) -> None:
    try:
        base, _stored_digest = manifest.data_version.rsplit("+", 1)
    except ValueError as exc:
        raise BundleIntegrityError(
            f"manifest data_version is missing '+' separator: {manifest.data_version!r}"
        ) from exc
    if not base:
        raise BundleIntegrityError(f"manifest data_version has empty base: {manifest.data_version!r}")

    files = [record.model_dump() for record in manifest.files]
    payloads = [record.model_dump() for record in manifest.payloads]
    expected = content_version(base, data_version_chunks(files, payloads))
    if manifest.data_version != expected:
        raise BundleIntegrityError(
            f"manifest data_version mismatch: manifest={manifest.data_version!r} computed={expected!r}"
        )

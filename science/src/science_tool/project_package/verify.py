"""Integrity self-checks for serialized project-package bundles."""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import tarfile
import tempfile
import zlib
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from science_tool.data_worktree import DEFAULT_DATA_DIRS
from science_tool.project_package.core import content_version
from science_tool.project_package.core import file_resource
from science_tool.project_package.manifest import SerializedManifest, data_version_chunks
from science_tool.project_package.payload import PayloadError, payload_inventory

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


@dataclass(frozen=True)
class CommitCompare:
    bundle: str
    head: str
    match: bool


@dataclass(frozen=True)
class SourceCompare:
    total: int
    match: int
    differ: list[str]
    absent: list[str]


@dataclass(frozen=True)
class PayloadCompare:
    ok: int
    differ: list[str]
    missing: list[str]
    extra: list[str]


@dataclass(frozen=True)
class AgainstResult:
    root: str
    commit: CommitCompare
    source: SourceCompare
    payloads: PayloadCompare


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


def preflight_against(root: Path) -> str:
    """Validate a target checkout and return its HEAD commit."""
    root = root.expanduser()
    if not root.exists():
        raise VerifyError(f"--against root does not exist: {root}")
    if not root.is_dir():
        raise VerifyError(f"--against root is not a directory: {root}")

    try:
        inside = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--is-inside-work-tree"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        raise VerifyError(f"--against root is not a git worktree: {root}") from exc
    if inside != "true":
        raise VerifyError(f"--against root is not a git worktree or has no working tree: {root}")

    try:
        return subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        raise VerifyError(f"--against root has no HEAD commit: {root}") from exc


def preflight_extract(dest: Path) -> None:
    """Validate that an extract target is absent or an existing empty directory."""
    if not dest.exists():
        return
    if dest.is_symlink():
        raise VerifyError(f"--extract target is a symlink, not a directory: {dest}")
    if not dest.is_dir():
        raise VerifyError(f"--extract target exists and is not a directory: {dest}")
    try:
        has_entries = any(dest.iterdir())
    except OSError as exc:
        raise VerifyError(f"cannot inspect --extract target: {dest}: {exc}") from exc
    if has_entries:
        raise VerifyError(f"--extract target is not empty: {dest}")


def extract_bundle(bundle: LoadedBundle, dest: Path) -> Path:
    """Write the bundle's source tree to dest/<project-id>/ atomically."""
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=".verify-extract-", dir=str(dest.parent)))
    except OSError as exc:
        raise VerifyError(f"failed to prepare --extract target: {exc}") from exc

    try:
        root = staging / bundle.project_id
        root.mkdir(parents=True)
        (root / "manifest.json").write_bytes(bundle.manifest_bytes)
        for rel, data in bundle.members.items():
            out = root / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(data)
        os.rename(staging, dest)
    except OSError as exc:
        shutil.rmtree(staging, ignore_errors=True)
        raise VerifyError(f"failed to extract bundle: {exc}") from exc
    return dest


def compare_against(bundle: LoadedBundle, root: Path, head: str) -> AgainstResult:
    """Compare a loaded bundle with a target checkout."""
    root = root.expanduser()
    commit = CommitCompare(
        bundle=bundle.manifest.provenance.git_commit,
        head=head,
        match=bundle.manifest.provenance.git_commit == head,
    )
    return AgainstResult(
        root=str(root),
        commit=commit,
        source=_compare_source(bundle, root),
        payloads=_compare_payloads(bundle, root),
    )


def _compare_source(bundle: LoadedBundle, root: Path) -> SourceCompare:
    match = 0
    differ: list[str] = []
    absent: list[str] = []
    for record in bundle.manifest.files:
        path = root / record.path
        if path.is_symlink() or not path.is_file():
            absent.append(record.path)
            continue
        try:
            actual = file_resource(root, record.path)
        except OSError as exc:
            raise VerifyError(f"filesystem error reading --against source {record.path} under {root}: {exc}") from exc
        if actual.sha256 == record.sha256 and actual.bytes == record.bytes:
            match += 1
        else:
            differ.append(record.path)
    return SourceCompare(
        total=len(bundle.manifest.files),
        match=match,
        differ=sorted(differ),
        absent=sorted(absent),
    )


def _compare_payloads(bundle: LoadedBundle, root: Path) -> PayloadCompare:
    tracked = _tracked_set(root)
    try:
        actual_payloads = payload_inventory(root, DEFAULT_DATA_DIRS, tracked)
    except PayloadError as exc:
        raise VerifyError(f"payload inventory failed for --against root {root}: {exc}") from exc

    expected = {record.path: record for record in bundle.manifest.payloads}
    actual = {record["path"]: record for record in actual_payloads}

    ok = 0
    differ: list[str] = []
    missing: list[str] = []
    extra: list[str] = []
    for path, expected_record in expected.items():
        actual_record = actual.get(path)
        if actual_record is None:
            missing.append(path)
            continue
        if actual_record["sha256"] == expected_record.sha256 and actual_record["bytes"] == expected_record.bytes:
            ok += 1
        else:
            differ.append(path)
    for path in actual:
        if path not in expected:
            extra.append(path)

    return PayloadCompare(
        ok=ok,
        differ=sorted(differ),
        missing=sorted(missing),
        extra=sorted(extra),
    )


def _tracked_set(root: Path) -> set[str]:
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z"],
            capture_output=True,
            check=True,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        raise VerifyError(f"cannot list git-tracked files for --against root: {root}") from exc
    return {path for path in out.decode("utf-8").split("\0") if path}


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

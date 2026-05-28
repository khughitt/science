"""Map (dataset_id, logical_path) to a hash-verified filesystem path.

The commons store holds the source of truth for what the bytes should be (the
resources[].hash in datapackage.yaml); this module finds the actual bytes via a
path lookup chain and verifies them.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from science_tool.commons.adapter import CommonsEntityAdapter
from science_tool.commons.config import (
    load_data_overrides,
    resolve_commons_data_root,
    resolve_commons_root,
)
from science_tool.commons.datapackage import (
    parse_resource_hash,
    read_datapackage,
    validate_logical_path,
)
from science_tool.commons.errors import (
    CommonsError,
    CommonsEntityError,
    DataIntegrityError,
    DataResourceNotFoundError,
)

_HASH_CHUNK_BYTES = 1 << 20
_DATASET_ID = re.compile(r"^dataset:[a-z0-9][a-z0-9-]{1,63}$")


@dataclass(frozen=True, slots=True)
class ResolvedDataResource:
    """The result of a successful resolve: a verified resource and provenance."""

    path: Path
    hash: str
    source: str
    logical_path: str
    dataset_id: str


def _sha256_file(path: Path) -> str:
    """Stream the file and return its lowercase hex sha256 digest."""
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            while chunk := handle.read(_HASH_CHUNK_BYTES):
                digest.update(chunk)
    except OSError as exc:
        raise CommonsError(f"cannot read data resource at {path}: {exc}") from exc
    return digest.hexdigest()


def resolve(
    dataset_id: str,
    logical_path: str,
    *,
    commons_root: Path | None = None,
    data_root: Path | None = None,
) -> ResolvedDataResource:
    """Resolve a commons dataset resource to a verified absolute filesystem path.

    Lookup order: `<data_root>/<slug>/<logical_path>`, then the per-machine
    override directory from `~/.config/science/data.yaml`. The chosen file's
    sha256 is verified against the datapackage hash on every call.
    """
    logical_path = validate_logical_path(logical_path)
    commons_root = commons_root or resolve_commons_root()
    data_root = data_root or resolve_commons_data_root()

    if not _DATASET_ID.fullmatch(dataset_id):
        raise CommonsEntityError(
            commons_root,
            canonical_id=dataset_id,
            cause=ValueError(f"data resolve requires a dataset id of the form 'dataset:<slug>', got {dataset_id!r}"),
        )

    record = CommonsEntityAdapter(commons_root).load(dataset_id)
    if record.datapackage_path is None:
        raise CommonsEntityError(
            record.body_path,
            canonical_id=dataset_id,
            cause=ValueError("dataset record is missing its datapackage path"),
        )

    descriptor = read_datapackage(record.datapackage_path)
    resource = descriptor.resource(logical_path)
    _, expected_digest = parse_resource_hash(resource.hash)

    resolved_logical_path = resource.path
    data_root_candidate = data_root / record.slug / resolved_logical_path

    if data_root_candidate.is_file():
        candidate, source = data_root_candidate, "data_root"
    else:
        override_dir = load_data_overrides().get(record.slug)
        override_candidate = override_dir / resolved_logical_path if override_dir is not None else None
        if override_candidate is not None and override_candidate.is_file():
            candidate, source = override_candidate, "override"
        else:
            tried = [data_root_candidate]
            if override_candidate is not None:
                tried.append(override_candidate)
            raise DataResourceNotFoundError(dataset_id, resolved_logical_path, tried=tried)

    actual_digest = _sha256_file(candidate)
    if actual_digest != expected_digest:
        raise DataIntegrityError(
            candidate,
            expected=resource.hash,
            actual=f"sha256:{actual_digest}",
        )

    return ResolvedDataResource(
        path=candidate.resolve(),
        hash=resource.hash,
        source=source,
        logical_path=resolved_logical_path,
        dataset_id=dataset_id,
    )

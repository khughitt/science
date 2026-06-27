"""Walk a commons store and produce validated entity records.

In Phase B the adapter parses frontmatter, validates against
Phase A's EntityValidator, and emits CommonsEntityRecord (or
CommonsEntityError) per entity. The validated frontmatter dict is
carried as-is — no `science_model.Entity` materialization (deferred
to Phase D, see the design spec).
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from science_model.entity_schema import EntityValidationError, EntityValidator

from science_tool.commons.errors import CommonsEntityError, CommonsLayoutError
from science_tool.markdown_utils import parse_frontmatter

_TYPE_DIRS = ("datasets", "papers", "topics", "themes")
_SKIP_NAMES = frozenset({".git", ".migrations", "__pycache__", "registry.sqlite"})

_TYPE_DIR_TO_TYPE = {
    "datasets": "dataset",
    "papers": "paper",
    "topics": "topic",
    "themes": "theme",
}


def _dataset_datapackage_path(root: Path, slug: str, entity_path: Path) -> Path | None:
    dataset_dir = root / "datasets" / slug
    default_dp_path = dataset_dir / "datapackage.yaml"
    frontmatter, _ = parse_frontmatter(entity_path)
    dataset_class = frontmatter.get("dataset_class")
    datapackage = frontmatter.get("datapackage")

    if isinstance(datapackage, str) and datapackage.strip():
        if not default_dp_path.is_file():
            raise CommonsLayoutError(
                dataset_dir,
                reason=(
                    f"explicit datapackage field {datapackage!r} requires missing "
                    "datapackage.yaml sibling"
                ),
            )
        return default_dp_path

    requires_default_dp = (
        dataset_class is None
        or (isinstance(dataset_class, str) and dataset_class.strip() == "")
        or dataset_class == "deposit"
    )
    if requires_default_dp and not default_dp_path.is_file():
        raise CommonsLayoutError(
            dataset_dir,
            reason="deposit dataset directory missing required datapackage.yaml sibling",
        )
    return default_dp_path if default_dp_path.is_file() else None


@dataclass(frozen=True, slots=True)
class CommonsEntityRecord:
    """One validated entity from the commons store."""

    canonical_id: str
    type: str
    slug: str
    schema_profile: str
    frontmatter: dict[str, Any]
    body_path: Path
    datapackage_path: Path | None
    mtime_ns: int


class CommonsEntityAdapter:
    """Walk the commons store and yield records or per-entity errors."""

    def __init__(self, root: Path, validator: EntityValidator | None = None) -> None:
        self._root = root
        self._validator = validator or EntityValidator()

    def scan(self) -> Iterator[CommonsEntityRecord | CommonsEntityError]:
        for type_name in _TYPE_DIRS:
            type_dir = self._root / type_name
            if not type_dir.is_dir():
                continue
            yield from self._scan_type(type_name, type_dir)

    def _scan_type(
        self, type_name: str, type_dir: Path
    ) -> Iterator[CommonsEntityRecord | CommonsEntityError]:
        if type_name == "datasets":
            for child in sorted(type_dir.iterdir()):
                if child.name in _SKIP_NAMES or child.name.startswith("."):
                    continue
                if not child.is_dir():
                    continue
                entity_path = child / "entity.md"
                if not entity_path.is_file():
                    continue
                try:
                    dp_path = _dataset_datapackage_path(
                        self._root, child.name, entity_path
                    )
                except CommonsLayoutError as exc:
                    yield CommonsEntityError(
                        child,
                        canonical_id=f"dataset:{child.name}",
                        cause=exc,
                    )
                    continue
                yield self._build(type_name, child.name, entity_path, dp_path)
        else:
            for child in sorted(type_dir.iterdir()):
                if child.name in _SKIP_NAMES or child.name.startswith("."):
                    continue
                if child.is_dir():
                    continue
                if child.suffix != ".md":
                    continue
                yield self._build(type_name, child.stem, child, None)

    def load(self, canonical_id: str) -> CommonsEntityRecord:
        """Load one entity by canonical id. Raises CommonsEntityError on failure."""
        if ":" not in canonical_id:
            raise CommonsEntityError(
                self._root,
                canonical_id=canonical_id,
                cause=ValueError(
                    f"canonical id {canonical_id!r} is not in '<type>:<slug>' form"
                ),
            )
        type_name, slug = canonical_id.split(":", 1)
        type_dir = next(
            (k for k, v in _TYPE_DIR_TO_TYPE.items() if v == type_name),
            None,
        )
        if type_dir is None:
            raise CommonsEntityError(
                self._root,
                canonical_id=canonical_id,
                cause=ValueError(f"unknown entity type {type_name!r}"),
            )
        if type_dir == "datasets":
            body = self._root / "datasets" / slug / "entity.md"
            dp = None
        else:
            body = self._root / type_dir / f"{slug}.md"
            dp = None
        if not body.is_file():
            raise CommonsEntityError(
                body,
                canonical_id=canonical_id,
                cause=FileNotFoundError(str(body)),
            )
        if type_dir == "datasets":
            dp = _dataset_datapackage_path(self._root, slug, body)
        result = self._build(type_dir, slug, body, dp)
        if isinstance(result, CommonsEntityError):
            raise result
        return result

    def _build(
        self,
        type_dir: str,
        slug: str,
        body_path: Path,
        datapackage_path: Path | None,
    ) -> CommonsEntityRecord | CommonsEntityError:
        type_name = _TYPE_DIR_TO_TYPE[type_dir]
        canonical_id = f"{type_name}:{slug}"
        try:
            frontmatter, _ = parse_frontmatter(body_path)
            if not frontmatter:
                raise EntityValidationError(
                    f"{body_path} has no parseable frontmatter"
                )
            self._validator.validate(frontmatter)
            declared_id = frontmatter.get("id")
            if declared_id != canonical_id:
                raise EntityValidationError(
                    f"frontmatter id {declared_id!r} does not match path-derived "
                    f"canonical id {canonical_id!r}"
                )
            declared_type = frontmatter.get("type")
            if declared_type != type_name:
                raise EntityValidationError(
                    f"frontmatter type {declared_type!r} does not match path-derived "
                    f"type {type_name!r}"
                )
        except EntityValidationError as exc:
            return CommonsEntityError(
                body_path, canonical_id=canonical_id, cause=exc
            )
        except Exception as exc:  # pragma: no cover — unexpected I/O / yaml errors
            return CommonsEntityError(
                body_path, canonical_id=canonical_id, cause=exc
            )

        mtime_ns = body_path.stat().st_mtime_ns
        if datapackage_path is not None:
            mtime_ns = max(mtime_ns, datapackage_path.stat().st_mtime_ns)
        return CommonsEntityRecord(
            canonical_id=canonical_id,
            type=type_name,
            slug=slug,
            schema_profile=str(frontmatter["schema_profile"]),
            frontmatter=frontmatter,
            body_path=body_path,
            datapackage_path=datapackage_path,
            mtime_ns=mtime_ns,
        )

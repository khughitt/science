"""Shared knowledge store (commons) for Science multi-project entities.

Phase B (scaffolding): directory bootstrap, schema-validated entity adapter,
SQLite index, and CLI surface for `science commons {init, index rebuild,
show, find, validate}`.

Phase C (data resolver): datapackage.yaml reader, hash-verified bulk-data
resolution, and the `science commons data resolve` CLI command.

See docs/plans/2026-05-13-multiproject-commons-scaffolding-design.md and
docs/plans/2026-05-14-commons-data-resolver-design.md.
"""

from __future__ import annotations

from science_tool.commons.adapter import (
    CommonsEntityAdapter,
    CommonsEntityRecord,
)
from science_tool.commons.bootstrap import init_commons
from science_tool.commons.cli import commons_group
from science_tool.commons.config import (
    CommonsSettings,
    load_data_overrides,
    resolve_commons_data_root,
    resolve_commons_root,
    resolve_project_root,
)
from science_tool.commons.datapackage import (
    DatapackageDescriptor,
    DataResource,
    parse_resource_hash,
    read_datapackage,
    validate_logical_path,
)
from science_tool.commons.errors import (
    CommonsDatapackageError,
    CommonsEntityError,
    CommonsError,
    CommonsLayoutError,
    CommonsRegistryError,
    CommonsRootMalformedError,
    CommonsRootNotFoundError,
    DataIntegrityError,
    DataLogicalPathError,
    DataResourceNotFoundError,
    OverlayMergeError,
    OverlayValidationError,
    ProjectDirectoryMissingError,
    ProjectNotRegisteredError,
)
from science_tool.commons.overlay import (
    MergedEntity,
    OverlayAdapter,
    OverlayRecord,
    OverlayValidationReport,
    merge_entity,
    resolve_entity,
    validate_project_overlays,
)
from science_tool.commons.inventory import build_commons_inventory
from science_tool.commons.query import CommonsQuery
from science_tool.commons.registry import RebuildReport, RegistryBuilder
from science_tool.commons.resolver import ResolvedDataResource, resolve
from science_tool.commons.validator import CommonsValidator, ValidationReport

__all__ = [
    "CommonsDatapackageError",
    "CommonsEntityAdapter",
    "CommonsEntityError",
    "CommonsEntityRecord",
    "CommonsError",
    "CommonsLayoutError",
    "CommonsQuery",
    "CommonsRegistryError",
    "CommonsRootMalformedError",
    "CommonsRootNotFoundError",
    "CommonsSettings",
    "CommonsValidator",
    "DataIntegrityError",
    "DataLogicalPathError",
    "DataResource",
    "DataResourceNotFoundError",
    "DatapackageDescriptor",
    "MergedEntity",
    "OverlayAdapter",
    "OverlayMergeError",
    "OverlayRecord",
    "OverlayValidationError",
    "OverlayValidationReport",
    "ProjectDirectoryMissingError",
    "ProjectNotRegisteredError",
    "RebuildReport",
    "RegistryBuilder",
    "ResolvedDataResource",
    "ValidationReport",
    "build_commons_inventory",
    "commons_group",
    "init_commons",
    "load_data_overrides",
    "merge_entity",
    "parse_resource_hash",
    "read_datapackage",
    "resolve",
    "resolve_commons_data_root",
    "resolve_commons_root",
    "resolve_entity",
    "resolve_project_root",
    "validate_project_overlays",
    "validate_logical_path",
]

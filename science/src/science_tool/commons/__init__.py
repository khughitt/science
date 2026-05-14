"""Shared knowledge store (commons) for Science multi-project entities.

Phase B (scaffolding): directory bootstrap, schema-validated entity adapter,
SQLite index, and CLI surface for `science commons {init, index rebuild,
show, find, validate}`. No inventory integration, no overlay merge, no data
resolver — those land in Phases C/D/E.

See docs/plans/2026-05-13-multiproject-commons-scaffolding-design.md.
"""

from __future__ import annotations

from science_tool.commons.adapter import (
    CommonsEntityAdapter,
    CommonsEntityRecord,
)
from science_tool.commons.bootstrap import init_commons
from science_tool.commons.cli import commons_group
from science_tool.commons.config import CommonsSettings, resolve_commons_root
from science_tool.commons.errors import (
    CommonsEntityError,
    CommonsError,
    CommonsLayoutError,
    CommonsRegistryError,
    CommonsRootMalformedError,
    CommonsRootNotFoundError,
)
from science_tool.commons.query import CommonsQuery
from science_tool.commons.registry import RebuildReport, RegistryBuilder
from science_tool.commons.validator import CommonsValidator, ValidationReport

__all__ = [
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
    "RebuildReport",
    "RegistryBuilder",
    "ValidationReport",
    "commons_group",
    "init_commons",
    "resolve_commons_root",
]

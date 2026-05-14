"""Shared knowledge store (commons) for Science multi-project entities.

Phase B (scaffolding): directory bootstrap, schema-validated entity adapter,
SQLite index, and CLI surface for `science commons {init, index rebuild,
show, find, validate}`. No inventory integration, no overlay merge, no data
resolver — those land in Phases C/D/E.

See docs/plans/2026-05-13-multiproject-commons-scaffolding-design.md.
"""

from __future__ import annotations

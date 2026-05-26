"""Reference-collection resolution checks (RCM-D2, guardrail 1).

A promoted member (`derivation.kind: member_of`) must resolve to an existing
parent collection, unless it explicitly declares `resolution_status:
declared_unresolved`. See
docs/plans/2026-05-26-reference-collection-member-promotion-design.md.

Reads RAW frontmatter, NOT the typed graph `Entity`. The graph `Entity` is a
closed pydantic model: its `derivation` is a typed `DerivationBlock` with no
`kind`/`member_key`/`parent_dataset` (it requires `workflow`/`workflow_run`),
and `resolution_status` is not modelled at all (pydantic `extra="ignore"` drops
it). Reading those via `getattr(entity, ...)` would therefore silently no-op on
every `member_of` dataset. We re-read each entity's `file_path` (resolved under
`ctx.project_root`, so the check works from any cwd) as raw frontmatter and feed
Plan 1's dict-based helpers, which already accept a frontmatter dict.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import yaml

from science_tool.commons.member import parse_member_of
from science_tool.graph.sources import load_project_sources
from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity


def _result(severity: Severity, path: str | None, message: str, rule: str) -> Result:
    return Result(severity, Path(path) if path else None, None, message, rule, None)


def _raw_frontmatter(path: Path) -> dict[str, Any]:
    """Raw frontmatter for either an entity.md (fenced YAML) or a datapackage.yaml."""
    text = path.read_text(encoding="utf-8")
    if path.suffix in (".yaml", ".yml"):
        data = yaml.safe_load(text) or {}
    elif text.startswith("---"):
        end = text.find("\n---", 3)
        data = yaml.safe_load(text[3:end]) if end != -1 else {}
    else:
        data = {}
    return data if isinstance(data, dict) else {}


def _dataset_frontmatters(ctx: ValidateContext) -> tuple[list[dict[str, Any]], set[str]]:
    """Raw frontmatter per dataset entity + the set of all known dataset ids.

    include_commons=True: a reference collection (the parent) typically lives in
    the commons, so the id set must span project + commons. Commons loading is
    reference-driven (`collect_referenced_commons_ids`), not a bulk scan, so this
    does not leak the whole commons into a tmp_path test project. Note: that
    extractor does not yet follow scalar `parent_dataset` into the commons, so a
    member whose parent exists ONLY in the commons is not resolvable through this
    check today; the assembly instance (Plan 2) resolves its collection directly
    via the commons resolver instead.
    """
    sources = load_project_sources(ctx.project_root, include_commons=True)
    dataset_ids = {e.canonical_id for e in sources.entities if getattr(e, "kind", None) == "dataset"}
    frontmatters: list[dict[str, Any]] = []
    for entity in sources.entities:
        if getattr(entity, "kind", None) != "dataset":
            continue
        rel = Path(getattr(entity, "file_path", ""))
        abs_path = rel if rel.is_absolute() else ctx.project_root / rel
        if not abs_path.is_file():
            continue
        fm = _raw_frontmatter(abs_path)
        fm.setdefault("type", "dataset")
        if not fm.get("id"):
            fm["id"] = getattr(entity, "canonical_id", "?")
        fm["_path"] = str(rel)
        frontmatters.append(fm)
    return frontmatters, dataset_ids


@Check(section="reference collections", order=24)
def check_reference_collections(ctx: ValidateContext) -> Iterator[Result]:
    frontmatters, dataset_ids = _dataset_frontmatters(ctx)

    for fm in frontmatters:
        member_of = parse_member_of(fm)
        if member_of is None:
            continue

        ident = fm.get("id", "?")
        path = fm.get("_path")

        top_parent = fm.get("parent_dataset")
        if top_parent is not None and top_parent != member_of.parent_dataset:
            yield _result(
                Severity.WARN,
                path,
                f"{ident}: parent_dataset {top_parent!r} disagrees with "
                f"derivation.parent_dataset {member_of.parent_dataset!r}",
                "reference-collection.parent-mismatch",
            )

        # Parent-collection resolution is structural: always required. A missing
        # parent is an ERROR even when declared_unresolved is set (RCM-D2 —
        # declared_unresolved is about the key/row lookup, not parent existence).
        if member_of.parent_dataset not in dataset_ids:
            yield _result(
                Severity.ERROR,
                path,
                f"{ident}: member_of parent_dataset {member_of.parent_dataset!r} does not resolve to a dataset entity",
                "reference-collection.unresolved-parent",
            )
            continue

        # Parent resolved. declared_unresolved is a property of the member key/row
        # lookup (the row check itself is deferred to the consuming instance),
        # surfaced here as an INFO state against the resolved collection.
        if fm.get("resolution_status") == "declared_unresolved":
            yield _result(
                Severity.INFO,
                path,
                f"{ident}: member key declared_unresolved against resolved "
                f"collection {member_of.parent_dataset!r} (honoured, RCM-D2)",
                "reference-collection.declared-unresolved",
            )

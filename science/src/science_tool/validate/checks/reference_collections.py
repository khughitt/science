"""Reference-collection resolution checks (RCM-D2, guardrail 1).

A promoted member (`derivation.kind: member_of`) must resolve to an existing
parent collection, unless it explicitly declares `resolution_status:
declared_unresolved`. See
docs/plans/2026-05-26-reference-collection-member-promotion-design.md.

Gathers dataset frontmatter by TOLERANT FILE DISCOVERY, not via
`load_project_sources`. The graph loader strict-validates every dataset through
pydantic and RAISES on a malformed core-kind entity (e.g. a member_of missing
its `member_key`), which would crash the whole `science validate` run before
this check could report the defect; it also aborts with CommonsRootNotFoundError
when a member's commons-hosted parent is referenced but no commons root is
configured. To stay robust on both counts, this check reads raw frontmatter
directly (DatapackageAdapter discovery + `_raw_frontmatter`) and resolves a
non-local parent against the commons directly, reporting `commons-unavailable`
(INFO) instead of crashing or falsely claiming the parent is unresolved.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import yaml

from science_tool.commons.adapter import CommonsEntityAdapter
from science_tool.commons.config import resolve_commons_root
from science_tool.commons.errors import CommonsError
from science_tool.commons.member import parse_member_of
from science_tool.graph.storage_adapters.datapackage import DatapackageAdapter
from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity


def _result(severity: Severity, path: str | None, message: str, rule: str) -> Result:
    return Result(severity, Path(path) if path else None, None, message, rule, None)


def _raw_frontmatter(path: Path) -> dict[str, Any]:
    """Raw frontmatter for either a datapackage.yaml or an entity.md (fenced YAML)."""
    text = path.read_text(encoding="utf-8")
    if path.suffix in (".yaml", ".yml"):
        data = yaml.safe_load(text) or {}
    elif text.startswith("---"):
        end = text.find("\n---", 3)
        data = yaml.safe_load(text[3:end]) if end != -1 else {}
    else:
        data = {}
    return data if isinstance(data, dict) else {}


def _discover_dataset_frontmatters(project_root: Path) -> list[dict[str, Any]]:
    """Raw frontmatter for every project dataset entity, tolerant of bad shapes.

    Project datasets live as `<data|results>/**/datapackage.yaml` entity packages;
    `DatapackageAdapter.discover` finds them without typed-validating the
    derivation, so a malformed member_of is surfaced as a diagnostic below rather
    than crashing the loader.
    """
    out: list[dict[str, Any]] = []
    for ref in DatapackageAdapter().discover(project_root):
        abs_path = project_root / ref.path
        if not abs_path.is_file():
            continue
        fm = _raw_frontmatter(abs_path)
        if fm.get("type") != "dataset":
            continue
        fm["_path"] = ref.path
        out.append(fm)
    return out


def _member_defect(derivation: dict[str, Any]) -> str | None:
    """Return a defect message if a ``kind: member_of`` derivation is malformed.

    Raw frontmatter is not schema-validated, so the schema-critical member_of
    fields are re-enforced here (mirroring the assembly check's `_assembly_defect`)
    rather than crashing in `parse_member_of`. Returns None when well formed.
    """
    parent = derivation.get("parent_dataset")
    if not isinstance(parent, str) or not parent.startswith("dataset:"):
        return "member_of derivation requires a parent_dataset 'dataset:' reference"
    key = derivation.get("member_key")
    if not isinstance(key, str) or not key.strip():
        return "member_of derivation requires a non-empty member_key"
    return None


def _commons_has_dataset(parent_id: str, cache: dict[str, bool | None]) -> bool | None:
    """Resolve a parent id against the commons directly.

    Returns True if present, False if the commons is available but lacks the id,
    and None if the commons root is not configured/available (cannot verify — the
    check reports this as INFO, never a false unresolved-parent ERROR).
    """
    if parent_id in cache:
        return cache[parent_id]
    root = resolve_commons_root()
    if not root.is_dir():
        cache[parent_id] = None
        return None
    try:
        CommonsEntityAdapter(root).load(parent_id)
        result: bool | None = True
    except CommonsError:
        result = False
    cache[parent_id] = result
    return result


@Check(section="reference collections", order=24)
def check_reference_collections(ctx: ValidateContext) -> Iterator[Result]:
    frontmatters = _discover_dataset_frontmatters(ctx.project_root)
    local_ids = {fm["id"] for fm in frontmatters if isinstance(fm.get("id"), str) and fm["id"]}
    commons_cache: dict[str, bool | None] = {}

    for fm in frontmatters:
        derivation = fm.get("derivation")
        if not isinstance(derivation, dict) or derivation.get("kind") != "member_of":
            continue

        ident = fm.get("id", "?")
        path = fm.get("_path")

        defect = _member_defect(derivation)
        if defect is not None:
            yield _result(
                Severity.ERROR,
                path,
                f"{ident}: {defect}",
                "reference-collection.malformed-member",
            )
            continue

        member_of = parse_member_of(fm)
        if member_of is None:  # unreachable: _member_defect validated the fields
            continue

        top_parent = fm.get("parent_dataset")
        if top_parent is not None and top_parent != member_of.parent_dataset:
            yield _result(
                Severity.WARN,
                path,
                f"{ident}: parent_dataset {top_parent!r} disagrees with "
                f"derivation.parent_dataset {member_of.parent_dataset!r}",
                "reference-collection.parent-mismatch",
            )

        parent = member_of.parent_dataset
        if parent not in local_ids:
            present = _commons_has_dataset(parent, commons_cache)
            if present is None:
                yield _result(
                    Severity.INFO,
                    path,
                    f"{ident}: parent collection {parent!r} is not local and the commons is not available to verify it",
                    "reference-collection.commons-unavailable",
                )
                continue
            if not present:
                yield _result(
                    Severity.ERROR,
                    path,
                    f"{ident}: member_of parent_dataset {parent!r} does not resolve to a "
                    f"dataset entity (not in project or commons)",
                    "reference-collection.unresolved-parent",
                )
                continue

        # Parent resolved (locally or in commons). declared_unresolved is a
        # property of the member key/row lookup (deferred to the consuming
        # instance), surfaced here as an INFO against the resolved collection.
        if fm.get("resolution_status") == "declared_unresolved":
            yield _result(
                Severity.INFO,
                path,
                f"{ident}: member key declared_unresolved against resolved "
                f"collection {member_of.parent_dataset!r} (honoured, RCM-D2)",
                "reference-collection.declared-unresolved",
            )

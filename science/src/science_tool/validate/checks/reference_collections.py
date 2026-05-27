"""Reference-collection resolution checks (RCM-D2, guardrail 1).

A promoted member (`derivation.kind: member_of`) must resolve to an existing
parent collection, unless it explicitly declares `resolution_status:
declared_unresolved`. See
docs/plans/2026-05-26-reference-collection-member-promotion-design.md.

Reads RAW frontmatter, NOT the typed graph `Entity`, for two reasons: (1)
`resolution_status` is not modelled on `Entity` at all (pydantic drops unknown
keys), so a typed read would miss it entirely; and (2) `parse_member_of` and the
malformed-member guard operate on a plain frontmatter dict, whereas the typed
`derivation` is a pydantic object (`DerivationBlock` | `MemberOfDerivationBlock`).
Raw frontmatter is therefore also the un-schema-validated surface for locally
authored files, so this check re-enforces the schema-critical member_of fields
itself (mirroring the assembly check's `_assembly_defect`). Each entity's
`file_path` is resolved under `ctx.project_root` so the check works from any cwd.
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
    does not leak the whole commons into a tmp_path test project.
    `collect_referenced_commons_ids` follows a member's `parent_dataset` (scalar
    and the member_of derivation's), so a parent collection hosted only in the
    commons is loaded here and resolves correctly.
    """
    sources = load_project_sources(ctx.project_root, include_commons=True)
    dataset_ids: set[str] = set()
    frontmatters: list[dict[str, Any]] = []
    for entity in sources.entities:
        if getattr(entity, "kind", None) != "dataset":
            continue
        dataset_ids.add(entity.canonical_id)
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


def _member_defect(derivation: dict[str, Any]) -> str | None:
    """Return a defect message if a ``kind: member_of`` derivation is malformed.

    Raw frontmatter bypasses JSON-schema validation for locally authored files,
    so the schema-critical member_of fields are re-enforced here rather than
    trusting the typed load. Without this, a member_of block missing its keys
    would crash the whole check via a KeyError in ``parse_member_of``. Returns
    None when the block is well formed.
    """
    parent = derivation.get("parent_dataset")
    if not isinstance(parent, str) or not parent.startswith("dataset:"):
        return "member_of derivation requires a parent_dataset 'dataset:' reference"
    key = derivation.get("member_key")
    if not isinstance(key, str) or not key.strip():
        return "member_of derivation requires a non-empty member_key"
    return None


@Check(section="reference collections", order=24)
def check_reference_collections(ctx: ValidateContext) -> Iterator[Result]:
    frontmatters, dataset_ids = _dataset_frontmatters(ctx)

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
        if member_of is None:
            # unreachable: _member_defect validated the fields
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

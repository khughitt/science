from __future__ import annotations

import re
from pathlib import Path

import yaml
from science_model.contracts.inventory_v1 import InventoryWarning
from science_tool.graph.sources import ProjectSources

CANONICAL_ID_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*:[A-Za-z0-9][A-Za-z0-9_.-]*$")
PROSE_REFERENCE_PATTERN = re.compile(
    r"\[\[((?:[A-Za-z][A-Za-z0-9_-]*:[A-Za-z0-9][A-Za-z0-9_.-]*)|(?:[thqf]\d{2,}[a-z0-9_.-]*))\]\]",
    re.IGNORECASE,
)


def collect_identity_warnings(project_root: Path, *, sources: ProjectSources) -> list[InventoryWarning]:
    warnings: list[InventoryWarning] = []
    baseline_paths = _baseline_paths(project_root)
    canonical_ids = _canonical_ids(sources)

    for document in sorted(sources.markdown_documents, key=lambda item: item.path):
        rel_path = document.path
        frontmatter = document.frontmatter
        if not frontmatter:
            warnings.extend(_prose_reference_warnings(rel_path, document.body, canonical_ids))
            continue
        kind = frontmatter.get("kind")
        if not kind:
            warnings.extend(_prose_reference_warnings(rel_path, document.body, canonical_ids))
            continue
        entity_id = frontmatter.get("id")
        if not isinstance(entity_id, str) or not entity_id:
            severity = "warning" if rel_path in baseline_paths else "error"
            warnings.append(
                InventoryWarning(
                    code="missing-canonical-id",
                    severity=severity,
                    message="Entity frontmatter is missing canonical '<kind>:<local-id>' id.",
                    path=rel_path,
                )
            )
        elif not CANONICAL_ID_PATTERN.match(entity_id):
            severity = "warning" if rel_path in baseline_paths else "error"
            warnings.append(
                InventoryWarning(
                    code="invalid-canonical-id",
                    severity=severity,
                    message=f"Entity id {entity_id!r} does not match '<kind>:<local-id>'.",
                    path=rel_path,
                    canonical_id=entity_id,
                )
            )
        warnings.extend(_prose_reference_warnings(rel_path, document.body, canonical_ids))
    return warnings


def _baseline_paths(project_root: Path) -> set[str]:
    path = project_root / "knowledge" / "entity-identity-baseline.yaml"
    if not path.exists():
        return set()
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {
        str(record["path"]) for record in data.get("records", []) if isinstance(record, dict) and record.get("path")
    }


def _canonical_ids(sources: ProjectSources) -> set[str]:
    ids: set[str] = set()
    for entity in sources.entities:
        ids.add(entity.canonical_id or entity.id)
        for alias in entity.aliases:
            ids.update(_alias_keys(str(alias)))
    for alias in sources.manual_aliases:
        ids.update(_alias_keys(str(alias)))
    return ids


def _alias_keys(alias: str) -> set[str]:
    return {alias, alias.lower()}


def _prose_reference_warnings(rel_path: str, text: str, canonical_ids: set[str]) -> list[InventoryWarning]:
    warnings: list[InventoryWarning] = []
    for match in PROSE_REFERENCE_PATTERN.finditer(text):
        target = match.group(1)
        if target not in canonical_ids and target.lower() not in canonical_ids:
            warnings.append(
                InventoryWarning(
                    code="unresolved-prose-reference",
                    severity="warning",
                    message=f"Markdown prose reference {target!r} does not resolve to a canonical id or alias.",
                    path=rel_path,
                    canonical_id=target,
                )
            )
    return warnings

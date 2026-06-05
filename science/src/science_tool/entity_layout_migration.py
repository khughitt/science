"""One-time migration of legacy doc/ + specs/ entity layouts into entities/.

Pure functions (discover → synthesize → plan → rewrite) plus a `migrate_layout`
orchestrator. Dry-run by default; `--apply` performs git mv + writes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re

import yaml

from science_tool.entities import is_markdown_entity_kind, markdown_entity_kinds, resolve_path_policy

_FRONTMATTER = re.compile(r"^---\n(.*?)\n?---\n?(.*)$", re.DOTALL)
# Roots scanned for legacy entities. entities/ is intentionally excluded.
_LEGACY_SCAN_ROOTS = ("doc", "specs")


@dataclass(frozen=True)
class LegacyEntity:
    rel_path: str
    kind: str
    old_id: str | None
    frontmatter: dict
    body: str


def _split_frontmatter(text: str) -> tuple[dict | None, str]:
    match = _FRONTMATTER.match(text)
    if match is None:
        return None, text
    try:
        data = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        return None, match.group(2)   # body without fences, not the full text
    return (data if isinstance(data, dict) else None), match.group(2)


def discover_legacy_entities(project_root: Path) -> list[LegacyEntity]:
    results: list[LegacyEntity] = []
    for root_name in _LEGACY_SCAN_ROOTS:
        root = project_root / root_name
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.md")):
            rel = path.relative_to(project_root).as_posix()
            if "templates" in path.parts:
                continue
            text = path.read_text(encoding="utf-8")
            frontmatter, body = _split_frontmatter(text)
            kind = _infer_kind(rel, frontmatter)
            if kind is None or not is_markdown_entity_kind(kind):
                continue
            old_id = None
            if frontmatter is not None:
                raw_id = frontmatter.get("id")
                old_id = raw_id if isinstance(raw_id, str) else None
            results.append(
                LegacyEntity(rel_path=rel, kind=kind, old_id=old_id, frontmatter=frontmatter or {}, body=body)
            )
    return results


# Specific legacy file paths whose kind cannot be inferred from the parent dir.
# `doc/reports/synthesis.md` is the legacy synthesis singleton: its parent dir is
# "reports", which the generic map would misclassify as `report`. Validation
# already treats this exact path as synthesis (discussions.py), so the migrator
# must agree.
_PATH_KIND_OVERRIDES: dict[str, str] = {
    "doc/reports/synthesis.md": "synthesis",
}


def _infer_kind(rel_path: str, frontmatter: dict | None) -> str | None:
    if frontmatter is not None:
        value = frontmatter.get("type") or frontmatter.get("kind")
        if isinstance(value, str) and value:
            return value
    # Frontmatterless file: explicit by-path override first, then the parent
    # directory name (singularized) via the derived map.
    if rel_path in _PATH_KIND_OVERRIDES:
        return _PATH_KIND_OVERRIDES[rel_path]
    parent = Path(rel_path).parent.name
    return _DIR_TO_KIND.get(parent)


# Legacy directory name → kind, for frontmatterless files. DERIVED from the
# policy table (SSOT) so EVERY numeric/citekey kind's plural directory is covered
# — including evidence-lines, reports, plans, searches, methods, and
# pre-registrations that a hand-written map would silently omit (and thereby
# strand valid legacy entities through cutover). Singletons have no per-kind dir,
# so they are excluded.
_DIR_TO_KIND: dict[str, str] = {
    resolve_path_policy(kind).root.name: kind
    for kind in markdown_entity_kinds()
    if resolve_path_policy(kind).strategy != "singleton"
}

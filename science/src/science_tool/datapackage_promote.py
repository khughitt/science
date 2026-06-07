"""`science data-package promote-orphans` — promote orphan datapackages to real
`entities/datasets/<id>.md` owner files (design §B4, Phase 2).

An orphan datapackage is a `datapackage.yaml` (profile `science-pkg-entity-1.0`)
with no entity-file owner. After Phase 1.5, such a datapackage is the (deprecated,
transitional) owner of its id. Promotion lifts the datapackage's identity/project
metadata into a real markdown owner and adds a `datapackage:` pointer back to the
datapackage, which stays in place as the attachment holding resource metadata. On
the next load the datapackage DEFERS to the new owner.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from science_tool.graph.sources import load_project_sources

# Datapackage fields that are *resource* metadata — they stay in the datapackage
# and are never copied into the identity owner file (§B4). `profiles` is the
# datapackage profile marker, not an entity field.
_RESOURCE_ONLY_FIELDS = frozenset(
    {
        "profiles",
        "schema_profile",
        "resources",
        "members_resource",
        "member_key_column",
        "n_sets",
        "set_size_summary",
        "identifier_space",
        "datapackage",  # never let a datapackage self-pointer through; we set it
    }
)

# Reuse migrate_layout's undated sentinel so the existing `--apply` undated gate
# surfaces a datapackage that carries no `created` rather than inventing a date.
_UNDATED_SENTINEL = "9999-99-99"

# Path-safety: a promoted owner is written at entities/datasets/<slug>.md. The
# dataset-id schema only requires a `dataset:` prefix (no path-safe slug
# constraint), so an id like `dataset:../../x` would otherwise escape the tree.
_SAFE_SLUG = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


def _is_safe_slug(slug: str) -> bool:
    # This is the SOLE path-safety firewall: DatapackageAdapter.discover() validates
    # only that id/type/title are non-empty, not that the id is path-safe, so a
    # `dataset:../../x` id loads and compiles fine — it must be caught here before it
    # becomes a write path. The character class already excludes path separators; `..`
    # is the only traversal token the class would otherwise admit (it permits `.`).
    return bool(_SAFE_SLUG.match(slug)) and ".." not in slug


@dataclass(frozen=True)
class OrphanPromotion:
    canonical_id: str
    datapackage_rel: str
    owner_rel: str  # entities/datasets/<slug>.md


def _scan_orphans(project_root: Path) -> tuple[list[OrphanPromotion], list[tuple[str, str]]]:
    """Return (promotable orphans, rejected). Rejected = (canonical_id, datapackage_rel)
    pairs whose slug is not path-safe — reported, never written."""
    sources = load_project_sources(
        project_root,
        include_commons=False,
        strict_core_schema=False,
        strict_identity=False,
    )
    plans: list[OrphanPromotion] = []
    rejected: list[tuple[str, str]] = []
    for decl in sources.identity_declarations:
        if decl.adapter != "datapackage" or decl.source_ref is None:
            continue
        slug = decl.canonical_id.split(":", 1)[-1]
        if not _is_safe_slug(slug):
            rejected.append((decl.canonical_id, decl.source_ref.path))
            continue
        plans.append(
            OrphanPromotion(
                canonical_id=decl.canonical_id,
                datapackage_rel=decl.source_ref.path,
                owner_rel=f"entities/datasets/{slug}.md",
            )
        )
    return plans, rejected


def plan_orphan_promotions(project_root: Path) -> list[OrphanPromotion]:
    """Every path-safe orphan datapackage owner in the compiled model, as a plan."""
    return _scan_orphans(project_root)[0]


def _owner_frontmatter(dp: dict, *, datapackage_rel: str) -> dict:
    fm = {k: v for k, v in dp.items() if k not in _RESOURCE_ONLY_FIELDS}
    fm["type"] = fm.get("type") or fm.pop("kind", None) or "dataset"
    fm.pop("kind", None)
    fm["datapackage"] = datapackage_rel
    created = str(dp.get("created") or _UNDATED_SENTINEL)
    fm["created"] = created
    fm["updated"] = str(dp.get("updated") or created)
    return fm


def _render_owner(fm: dict, *, datapackage_rel: str) -> str:
    return (
        "---\n"
        + yaml.safe_dump(fm, sort_keys=False, allow_unicode=True)
        + "---\n\n"
        + f"Promoted from orphan datapackage `{datapackage_rel}` (design §B4).\n"
    )


def promote_orphan_datapackages(project_root: Path, *, apply: bool) -> dict:
    """Plan (and optionally write) owner files for every path-safe orphan datapackage.
    Unsafe-slug orphans are returned under ``rejected`` and never written."""
    plans, rejected = _scan_orphans(project_root)
    for plan in plans:
        dp = yaml.safe_load((project_root / plan.datapackage_rel).read_text(encoding="utf-8")) or {}
        fm = _owner_frontmatter(dp, datapackage_rel=plan.datapackage_rel)
        body = _render_owner(fm, datapackage_rel=plan.datapackage_rel)
        owner_path = project_root / plan.owner_rel
        if apply:
            owner_path.parent.mkdir(parents=True, exist_ok=True)
            if not (owner_path.exists() and owner_path.read_text(encoding="utf-8") == body):
                owner_path.write_text(body, encoding="utf-8")
    return {"promotions": plans, "rejected": rejected, "applied": apply}

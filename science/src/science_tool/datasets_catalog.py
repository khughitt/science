"""Catalog commands for the singular `dataset` group: add / list / show / consumers.

`dataset` has no path policy, so ids are synthesized directly (validate_slug +
f-string) rather than via generate_entity_id. See
docs/plans/2026-06-21-dataset-catalog-cli-design.md.
"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

import yaml

from science_tool.entities import (
    EntityCommandError,
    _validate_prospective_write,
    validate_slug,
)


def _render_candidate(
    entity_id: str,
    *,
    title: str,
    origin: str,
    tier: str,
    level: str,
    source_url: str,
    ontology_terms,
    related,
    today: date,
) -> str:
    # Build the frontmatter as a dict and serialize with yaml.safe_dump so any
    # quote/newline/colon in user input cannot break the document or inject
    # fields ahead of _validate_prospective_write's parse.
    iso = today.isoformat()
    fm: dict = {
        "id": entity_id,
        "type": "dataset",
        "title": title,
        "status": "candidate",
        "created": iso,
        "updated": iso,
        "origin": origin,
        "source_class": "observational",
        "tier": tier,
        "license": "unknown",
        "access": {
            "level": level,
            "availability": "available",
            "verified": False,
            "source_url": source_url,
        },
        "accessions": [],
        "ontology_terms": list(ontology_terms),
        "related": list(related),
    }
    front = yaml.safe_dump(fm, sort_keys=False, allow_unicode=True, default_flow_style=False)
    body = (
        f"# {title}\n\n"
        "**Candidate dataset.** `status: candidate` — catalogued but not yet acquired.\n\n"
        "## What it is\n\n_One-paragraph description (fill in)._\n\n"
        "## Why it fits\n\n_Relevance to the task/question that motivated cataloguing it (fill in)._\n\n"
        "## Access / caveats\n\n_Access level, gating, and known limitations (fill in)._\n"
    )
    return f"---\n{front}---\n\n{body}"


def add_dataset(
    project_root: Path,
    slug: str,
    *,
    title: str,
    origin: str = "external",
    tier: str = "track",
    level: str = "controlled",
    source_url: str = "",
    ontology_terms=(),
    related=(),
    today: date | None = None,
) -> tuple[str, Path, list[str]]:
    if origin != "external":
        raise EntityCommandError(
            "dataset add authors external candidate entities only; derived datasets "
            "are machine-authored by `science dataset register-run`."
        )
    slug = validate_slug(slug)
    entity_id = f"dataset:{slug}"
    today = today or date.today()
    rel_path = Path("doc") / "datasets" / f"{slug}.md"
    dest = project_root / rel_path
    if dest.exists():
        raise EntityCommandError(f"Destination already exists: {rel_path}")

    text = _render_candidate(
        entity_id,
        title=title,
        origin=origin,
        tier=tier,
        level=level,
        source_url=source_url,
        ontology_terms=ontology_terms,
        related=related,
        today=today,
    )
    warnings = _validate_prospective_write(
        project_root=project_root,
        rel_path=rel_path,
        text=text,
        target_entity_id=entity_id,
        include_commons=False,  # local-only: a commons-looking related ref must not crash author-time
    )
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, dest)
    finally:
        if tmp.exists():
            tmp.unlink()
    return entity_id, dest, warnings


from science_model.frontmatter import parse_frontmatter


def _local_rows(project_root: Path) -> list[dict]:
    ds_dir = project_root / "doc" / "datasets"
    rows: list[dict] = []
    if not ds_dir.is_dir():
        return rows
    for md in sorted(ds_dir.glob("*.md")):
        parsed = parse_frontmatter(md)
        if parsed is None:
            continue
        fm, _ = parsed
        if (fm.get("kind") or fm.get("type")) != "dataset":
            continue
        access = fm.get("access") or {}
        rows.append(
            {
                "id": fm.get("id", md.stem),
                "title": fm.get("title", ""),
                "status": fm.get("status", ""),
                "tier": fm.get("tier", ""),
                "origin": fm.get("origin", ""),
                "level": access.get("level", "") if isinstance(access, dict) else "",
                "verified": bool(access.get("verified")) if isinstance(access, dict) else False,
                "scope": "local",
            }
        )
    return rows


def _matches(row: dict, *, origin, status, tier, unverified, level) -> bool:
    if origin is not None and row["origin"] != origin:
        return False
    if status is not None and row["status"] != status:
        return False
    if tier is not None and row["tier"] != tier:
        return False
    if level is not None and row["level"] != level:
        return False
    if unverified and not (row["origin"] == "external" and not row["verified"]):
        # --unverified means "external entities awaiting verification", not
        # "anything lacking an access block" (derived rows have no access →
        # verified defaults False and must NOT show up here).
        return False
    return True


def list_datasets(
    project_root: Path,
    *,
    origin: str | None = None,
    status: str | None = None,
    tier: str | None = None,
    unverified: bool = False,
    level: str | None = None,
    include_commons: bool = False,
) -> tuple[list[dict], str | None]:
    """Return (filtered rows, commons-unavailable notice). Local rows are always
    returned; if `include_commons` and the commons registry can't be read, the
    notice is set and local rows still come back (graceful degradation)."""
    rows = _local_rows(project_root)
    notice: str | None = None
    if include_commons:
        try:
            rows.extend(_commons_rows())
        except CommonsUnavailable as exc:
            notice = str(exc)
    filtered = [
        r
        for r in rows
        if _matches(r, origin=origin, status=status, tier=tier, unverified=unverified, level=level)
    ]
    return filtered, notice


def _commons_rows() -> list[dict]:
    """Commons catalog rows via CommonsQuery.find('dataset'); [] if unavailable.

    Raises CommonsUnavailable so the CLI can print a single notice. The registry
    must exist; CommonsQuery warns on staleness.
    """
    from science_tool.commons.config import resolve_commons_root
    from science_tool.commons.errors import CommonsRegistryError
    from science_tool.commons.query import CommonsQuery

    try:
        records = CommonsQuery(resolve_commons_root()).find("dataset")
    except (CommonsRegistryError, FileNotFoundError) as exc:
        raise CommonsUnavailable(str(exc)) from exc
    rows: list[dict] = []
    for rec in records:
        fm = rec.frontmatter or {}
        access = fm.get("access") or {}
        rows.append(
            {
                "id": rec.canonical_id,
                "title": fm.get("title", ""),
                "status": fm.get("status", ""),
                "tier": fm.get("tier", ""),
                "origin": fm.get("origin", ""),
                "level": access.get("level", "") if isinstance(access, dict) else "",
                "verified": bool(access.get("verified")) if isinstance(access, dict) else False,
                "scope": "commons",
            }
        )
    return rows


class CommonsUnavailable(Exception):
    """Raised when the commons registry cannot be read for a --commons listing."""

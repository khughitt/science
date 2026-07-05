"""Catalog commands for the singular `dataset` group: add / list / show / consumers.

`dataset` has no path policy, so ids are synthesized directly (validate_slug +
f-string) rather than via generate_entity_id. See docs/user-guide/entities.md.
"""

from __future__ import annotations

import os
import re
from datetime import date
from pathlib import Path

import yaml

from science_model.frontmatter import parse_frontmatter
from science_tool.entities import (
    EntityCommandError,
    _validate_prospective_write,
    validate_slug,
)
from science_tool.identity_authoring import (
    BASE_DATASET_SCHEMA_PROFILE,
    IdentityAuthoringError,
    require_profile_identity,
)

# access.level values that put a dataset behind registration, application, or
# purchase — i.e. not something you can just download. `list`/`prioritize` hide
# these by default so suggestions stay actionable; surface them with
# --include-gated (or by naming the level explicitly via --level). Derived rows
# (no access block → level "") and public/mixed are never gated.
GATED_LEVELS = frozenset({"registration", "controlled", "commercial"})


def _render_candidate(
    entity_id: str,
    *,
    schema_profile: str,
    identity_context: dict | None,
    title: str,
    origin: str,
    dataset_class: str,
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
        "schema_profile": schema_profile,
        "id": entity_id,
        "kind": "dataset",
        "title": title,
        "status": "candidate",
        "created": iso,
        "updated": iso,
        "origin": origin,
        "dataset_class": dataset_class,
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
    if identity_context:
        fm["identity_context"] = identity_context
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
    dataset_class: str = "deposit",
    tier: str = "track",
    level: str = "controlled",
    source_url: str = "",
    ontology_terms=(),
    related=(),
    schema_profile: str = BASE_DATASET_SCHEMA_PROFILE,
    identity_context: dict | None = None,
    today: date | None = None,
) -> tuple[str, Path, list[str]]:
    if origin != "external":
        raise EntityCommandError(
            "dataset add authors external candidate entities only; derived datasets "
            "are machine-authored by `science dataset register-run`."
        )
    if dataset_class not in {"deposit", "reference", "pointer"}:
        raise EntityCommandError("dataset class must be one of: deposit, reference, pointer")
    if dataset_class == "reference" and not source_url:
        raise EntityCommandError("dataset add --class reference requires --source-url")
    slug = validate_slug(slug)
    entity_id = f"dataset:{slug}"
    today = today or date.today()
    rel_path = Path("entities") / "datasets" / f"{slug}.md"
    dest = project_root / rel_path
    if dest.exists():
        raise EntityCommandError(f"Destination already exists: {rel_path}")
    identity_context = identity_context or {}
    try:
        require_profile_identity(schema_profile, identity_context)
    except IdentityAuthoringError as exc:
        raise EntityCommandError(str(exc)) from exc

    text = _render_candidate(
        entity_id,
        schema_profile=schema_profile,
        identity_context=identity_context,
        title=title,
        origin=origin,
        dataset_class=dataset_class,
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


_VERIFY_LOG_HEADING = "## Access verification log"


def _load_local_dataset(project_root: Path, ref: str) -> tuple[str, Path, dict, str]:
    """Resolve `slug`/`dataset:slug` to (slug, dest, fm, body) for a LOCAL dataset.

    verify-access edits a file in place, so commons-backed datasets (not editable
    here) and non-dataset files are clean refusals.
    """
    slug = ref[len("dataset:"):] if ref.startswith("dataset:") else ref
    slug = validate_slug(slug)  # raises EntityCommandError on a malformed slug
    dest = project_root / "entities" / "datasets" / f"{slug}.md"
    if not dest.exists():
        raise EntityCommandError(f"no such local dataset {ref!r} under entities/datasets/")
    parsed = parse_frontmatter(dest)
    if parsed is None or (parsed[0].get("kind")) != "dataset":
        raise EntityCommandError(f"{ref!r} is not a dataset entity")
    fm, body = parsed
    return slug, dest, fm, body


def _append_verification_log(body: str, line: str) -> str:
    """Append a dated log line under the `## Access verification log` section,
    creating the section if absent. Idempotent re-runs add lines, not sections."""
    trimmed = body.rstrip("\n")
    if _VERIFY_LOG_HEADING in trimmed:
        return f"{trimmed}\n{line}\n"
    return f"{trimmed}\n\n{_VERIFY_LOG_HEADING}\n\n{line}\n"


def _render_entity(frontmatter: dict, body: str) -> str:
    front = yaml.safe_dump(frontmatter, sort_keys=False, allow_unicode=True, default_flow_style=False)
    return f"---\n{front}---\n\n{body.strip()}\n"


def _iter_local_entities(project_root: Path):
    for path in sorted((project_root / "entities").glob("**/*.md")):
        parsed = parse_frontmatter(path)
        if parsed is None:
            continue
        fm, body = parsed
        entity_id = fm.get("id")
        if isinstance(entity_id, str) and entity_id:
            yield path, fm, body


def _load_entity_by_id(project_root: Path, entity_id: str) -> tuple[Path, dict, str] | None:
    for path, fm, body in _iter_local_entities(project_root):
        if fm.get("id") == entity_id:
            return path, fm, body
    return None


def _dataset_match_key(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value).lower())


def _dataset_resolution_index(project_root: Path) -> dict[str, tuple[str, str] | None]:
    index: dict[str, tuple[str, str] | None] = {}
    for path, fm, _body in _iter_local_entities(project_root):
        if fm.get("kind") != "dataset":
            continue
        dataset_id = fm.get("id")
        if not isinstance(dataset_id, str) or not dataset_id.startswith("dataset:"):
            continue
        slug = dataset_id.split(":", 1)[1]
        candidates: list[tuple[object, str]] = [(slug, "slug")]
        title = fm.get("title")
        if title:
            candidates.append((title, "title"))
        accessions = fm.get("accessions")
        if isinstance(accessions, list):
            candidates.extend((item, "accession") for item in accessions if isinstance(item, str) and item)
        for value, reason in candidates:
            key = _dataset_match_key(value)
            if not key:
                continue
            next_value = (dataset_id, reason)
            existing = index.get(key)
            if existing is not None and existing[0] == dataset_id:
                continue
            if key in index and existing != next_value:
                index[key] = None
            else:
                index[key] = next_value
    return index


def reconcile_dataset_links(project_root: Path, *, fix: bool = False) -> list[dict[str, str]]:
    """Find Q/H free-text ``datasets:`` entries that resolve to local datasets."""
    index = _dataset_resolution_index(project_root)
    rows: list[dict[str, str]] = []
    rewrites: list[tuple[Path, dict, str]] = []
    for path, fm, body in _iter_local_entities(project_root):
        entity_kind = fm.get("kind")
        if entity_kind not in {"question", "hypothesis"}:
            continue
        entity_id = fm.get("id")
        if not isinstance(entity_id, str):
            continue
        raw_datasets = fm.get("datasets")
        if not isinstance(raw_datasets, list):
            continue
        changed = False
        next_datasets: list[object] = []
        for entry in raw_datasets:
            if not isinstance(entry, str) or entry.startswith("dataset:"):
                next_datasets.append(entry)
                continue
            resolved = index.get(_dataset_match_key(entry))
            if resolved is None:
                next_datasets.append(entry)
                continue
            dataset_id, reason = resolved
            rows.append(
                {
                    "file": path.relative_to(project_root).as_posix(),
                    "entity_id": entity_id,
                    "entry": entry,
                    "resolved_dataset": dataset_id,
                    "reason": reason,
                }
            )
            next_datasets.append(dataset_id if fix else entry)
            changed = changed or fix
        if changed:
            fm["datasets"] = next_datasets
            rewrites.append((path, fm, body))

    for path, fm, body in rewrites:
        tmp = path.with_suffix(path.suffix + ".tmp")
        try:
            tmp.write_text(_render_entity(fm, body), encoding="utf-8")
            os.replace(tmp, path)
        finally:
            if tmp.exists():
                tmp.unlink()
    return rows


def link_dataset_to_target(project_root: Path, dataset_ref: str, target_ref: str) -> tuple[str, str, Path, bool]:
    """Append a dataset id to a question/hypothesis entity's ``datasets:`` list.

    Returns (dataset_id, target_ref, target_path, changed). The operation is
    idempotent and preserves the target body while normalizing frontmatter YAML.
    """
    _slug, _dataset_path, dataset_fm, _dataset_body = _load_local_dataset(project_root, dataset_ref)
    dataset_id = dataset_fm.get("id")
    if not isinstance(dataset_id, str) or not dataset_id.startswith("dataset:"):
        raise EntityCommandError(f"{dataset_ref!r} is not a dataset entity")

    if not (target_ref.startswith("question:") or target_ref.startswith("hypothesis:")):
        raise EntityCommandError("dataset link target must be a question or hypothesis ref")
    loaded = _load_entity_by_id(project_root, target_ref)
    if loaded is None:
        raise EntityCommandError(f"no such target entity {target_ref!r}")
    target_path, target_fm, target_body = loaded
    target_kind = target_fm.get("kind")
    if target_kind not in {"question", "hypothesis"}:
        raise EntityCommandError("dataset link target must be a question or hypothesis entity")

    raw_datasets = target_fm.get("datasets")
    if raw_datasets is None:
        datasets: list[str] = []
    elif isinstance(raw_datasets, list) and all(isinstance(item, str) for item in raw_datasets):
        datasets = list(raw_datasets)
    else:
        raise EntityCommandError(f"{target_ref}: datasets must be a list of dataset ids")

    if dataset_id in datasets:
        return dataset_id, target_ref, target_path, False

    target_fm["datasets"] = [*datasets, dataset_id]
    tmp = target_path.with_suffix(target_path.suffix + ".tmp")
    text = _render_entity(target_fm, target_body)
    try:
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, target_path)
    finally:
        if tmp.exists():
            tmp.unlink()
    return dataset_id, target_ref, target_path, True


def verify_access(
    project_root: Path,
    ref: str,
    *,
    level: str | None = None,
    license_: str | None = None,
    dataset_class: str | None = None,
    method: str | None = None,
    verified_by: str = "agent (verify-access)",
    source_url: str | None = None,
    tier: str | None = None,
    note: str = "",
    exception: str | None = None,
    rationale: str = "",
    superseded_by: str | None = None,
    followup_task: str | None = None,
    today: date | None = None,
) -> tuple[str, Path, str, float, list[str]]:
    """Verify (or exception-gate) a local dataset's accessibility in one atomic edit.

    Writes the coupled origin/license/access fields together (doubling as the
    legacy backfill), appends a verification-log line, and returns
    (entity_id, dest, readiness_state, readiness_weight, warnings).
    """
    from science_tool.dataset_prioritize import readiness_for, readiness_weight
    from science_tool.validate.checks.dataset_metadata import evaluate_dataset_metadata

    today = today or date.today()
    slug, dest, fm, body = _load_local_dataset(project_root, ref)
    entity_id = fm.get("id") or f"dataset:{slug}"

    if fm.get("origin") == "derived":
        raise EntityCommandError(
            f"{entity_id}: cannot verify-access a derived dataset (invariant #8 forbids an "
            "access block); derived datasets are authored by `science dataset register-run`."
        )

    # origin: any verified/exception-gated dataset is external.
    fm["origin"] = "external"
    if dataset_class is not None:
        if dataset_class not in {"deposit", "reference", "pointer"}:
            raise EntityCommandError("dataset class must be one of: deposit, reference, pointer")
        fm["dataset_class"] = dataset_class
    elif not (isinstance(fm.get("dataset_class"), str) and fm["dataset_class"].strip()):
        fm["dataset_class"] = "deposit"

    # license — path-independent: an empty license on an external dataset trips
    # dataset.license-missing regardless of verified/exception state.
    if license_:
        fm["license"] = license_
    elif not (isinstance(fm.get("license"), str) and fm["license"].strip()):
        raise EntityCommandError(
            f"{entity_id}: no license recorded — pass --license (an SPDX id, or the "
            "'unknown' sentinel if it genuinely can't be determined)."
        )

    access = dict(fm.get("access")) if isinstance(fm.get("access"), dict) else {}
    access["level"] = level or access.get("level") or "public"
    access["availability"] = "available"
    if source_url is not None:
        access["source_url"] = source_url
    effective_class = fm["dataset_class"]
    if effective_class in {"reference", "pointer"} and not access.get("source_url"):
        raise EntityCommandError(f"{entity_id}: dataset_class {effective_class} requires --source-url")

    if exception:
        # Branch B: exception decision. verified ⊥ exception.mode → clear verified.
        access["verified"] = False
        access["verification_method"] = ""
        exc: dict = {"mode": exception, "decision_date": today.isoformat()}
        if rationale:
            exc["rationale"] = rationale
        if followup_task:
            exc["followup_task"] = followup_task
        if superseded_by:
            exc["superseded_by_dataset"] = superseded_by
        access["exception"] = exc
        summary = note or f"{exception}" + (f" — {rationale}" if rationale else "")
    else:
        # Branch A: verified.
        if not method:
            raise EntityCommandError(
                f"{entity_id}: the verified path requires --method "
                "(retrieved|credential-confirmed|landing-confirmed|metadata-confirmed)."
            )
        allowed_methods = {
            "deposit": {"retrieved", "credential-confirmed", "landing-confirmed"},
            "reference": {"credential-confirmed", "landing-confirmed", "metadata-confirmed"},
            "pointer": {"landing-confirmed", "metadata-confirmed"},
        }[effective_class]
        if method not in allowed_methods:
            allowed = "|".join(sorted(allowed_methods))
            raise EntityCommandError(
                f"{entity_id}: --method {method!r} is invalid for dataset_class "
                f"{effective_class!r}; use one of ({allowed})."
            )
        access["verified"] = True
        access["verification_method"] = method
        access["last_reviewed"] = today.isoformat()
        access["verified_by"] = verified_by
        # mutual exclusivity, other direction: clear any prior exception mode.
        if isinstance(access.get("exception"), dict) and access["exception"].get("mode"):
            access["exception"] = {**access["exception"], "mode": ""}
        summary = note or method

    fm["access"] = access
    if tier is not None:
        fm["tier"] = tier
    fm["updated"] = today.isoformat()

    body = _append_verification_log(body, f"- {today.isoformat()} ({verified_by}): {summary}")

    front = yaml.safe_dump(fm, sort_keys=False, allow_unicode=True, default_flow_style=False)
    body = body.lstrip("\n")
    text = f"---\n{front}---\n\n{body}"

    rel_path = Path("entities") / "datasets" / f"{slug}.md"
    warnings = _validate_prospective_write(
        project_root=project_root,
        rel_path=rel_path,
        text=text,
        target_entity_id=entity_id,
        include_commons=False,
    )
    # Second pass: metadata vocabulary checks (license/tier/cadence) — these are NOT
    # run by _validate_prospective_write, which only diffs source-audit rows.
    warnings.extend(r.message for r in evaluate_dataset_metadata([fm]))

    tmp = dest.with_suffix(dest.suffix + ".tmp")
    try:
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, dest)
    finally:
        if tmp.exists():
            tmp.unlink()

    state = readiness_for(fm).state
    weight = readiness_weight(fm)[0]
    return entity_id, dest, state, weight, warnings


def _local_rows(project_root: Path) -> list[dict]:
    ds_dir = project_root / "entities" / "datasets"
    rows: list[dict] = []
    if not ds_dir.is_dir():
        return rows
    for md in sorted(ds_dir.glob("*.md")):
        parsed = parse_frontmatter(md)
        if parsed is None:
            continue
        fm, _ = parsed
        if fm.get("kind") != "dataset":
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


def _matches(row: dict, *, origin, status, tier, unverified, level, include_gated) -> bool:
    if origin is not None and row["origin"] != origin:
        return False
    if status is not None and row["status"] != status:
        return False
    if tier is not None and row["tier"] != tier:
        return False
    if level is not None and row["level"] != level:
        return False
    if not include_gated and level is None and row["level"] in GATED_LEVELS:
        # Non-gated by default. An explicit --level (level is not None) is an
        # intent to see that level, so it overrides this exclusion.
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
    include_gated: bool = False,
    include_commons: bool = False,
) -> tuple[list[dict], str | None]:
    """Return (filtered rows, commons-unavailable notice). Local rows are always
    returned; if `include_commons` and the commons registry can't be read, the
    notice is set and local rows still come back (graceful degradation).

    Gated datasets (`access.level` in GATED_LEVELS) are excluded unless
    `include_gated` is set or a specific `level` is requested."""
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
        if _matches(
            r, origin=origin, status=status, tier=tier,
            unverified=unverified, level=level, include_gated=include_gated,
        )
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


def resolve_dataset(project_root: Path, ref: str) -> tuple[str, dict, str] | None:
    """Resolve `foo` or `dataset:foo` to (scope, frontmatter, body); local then commons."""
    slug = ref[len("dataset:"):] if ref.startswith("dataset:") else ref
    # Validate before building any path: a ref like "../other/x" must not escape
    # entities/datasets/. An invalid slug is a clean miss (CLI maps None → exit 2).
    try:
        slug = validate_slug(slug)
    except EntityCommandError:
        return None
    local = project_root / "entities" / "datasets" / f"{slug}.md"
    if local.exists():
        parsed = parse_frontmatter(local)
        if parsed is not None:
            fm, body = parsed
            # Same guard as `list`: a non-dataset file under entities/datasets/ is a
            # local miss, not a match — fall through to commons.
            if fm.get("kind") == "dataset":
                return ("local", fm, body)
    from science_tool.commons.config import resolve_commons_root
    from science_tool.commons.errors import CommonsEntityError, CommonsRegistryError
    from science_tool.commons.query import CommonsQuery

    try:
        rec = CommonsQuery(resolve_commons_root()).show(f"dataset:{slug}")
    except (CommonsEntityError, CommonsRegistryError, FileNotFoundError):
        return None
    fm = rec.frontmatter or {}
    # body_path is the full entity.md (frontmatter + body); strip the frontmatter
    # so `show` prints body-only, matching the local path's parse_frontmatter result.
    body = ""
    if rec.body_path and Path(rec.body_path).exists():
        parsed_commons = parse_frontmatter(Path(rec.body_path))
        body = parsed_commons[1] if parsed_commons else ""
    return ("commons", fm, body)


def format_show(scope: str, fm: dict, body: str) -> list[str]:
    """Render a dataset entity to display lines (keeps the CLI wrapper thin)."""
    access = fm.get("access") or {}
    lines = [
        f"id:       {fm.get('id', '?')}  ({scope})",
        f"title:    {fm.get('title', '')}",
        f"status:   {fm.get('status', '')}    tier: {fm.get('tier', '')}",
        f"origin:   {fm.get('origin', '')}    license: {fm.get('license', '')}",
    ]
    if isinstance(access, dict) and access:
        lines.append(f"access:   level={access.get('level', '')} verified={access.get('verified')}")
        if access.get("source_url"):
            lines.append(f"url:      {access['source_url']}")
    if fm.get("accessions"):
        lines.append(f"accessions: {fm['accessions']}")
    if fm.get("related"):
        lines.append(f"related:  {fm['related']}")
    if fm.get("consumed_by"):
        lines.append(f"consumed_by: {fm['consumed_by']}")
    lines.append("")
    lines.append(body.strip())
    return lines


def consumers_of(fm: dict) -> list[str]:
    """The entity's consumers (consumed_by), as a list of refs."""
    return list(fm.get("consumed_by") or [])

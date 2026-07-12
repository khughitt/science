"""String builders for commons promotion.

Canonical entities, project overlays, and the audit log are all rendered here.
Every function is a pure string builder: it takes a decision or a plan and returns
text. No I/O, no subprocess, no git.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, Mapping

import yaml
from science_model.entity_schema import ProfileString
from science_model.frontmatter import render_frontmatter

from science_tool.commons.errors import PromoteCandidateError, PromoteInputError
from science_tool.commons.promote_types import (
    PromoteDecision,
    PromoteKindConfig,
    PromoteResult,
    _OVERLAY_ONLY_KEYS,
    _resolve_canonical_artifact_path,
)


def _rewrite_rendered_frontmatter(rendered: str, updates: Mapping[str, Any]) -> str:
    if not rendered.startswith("---\n"):
        raise PromoteCandidateError("rendered content has no opening --- fence", slug=None)
    rest = rendered[len("---\n") :]
    fm_raw, sep, body = rest.partition("\n---\n")
    if not sep:
        raise PromoteCandidateError("rendered content has no closing --- fence", slug=None)
    parsed = yaml.safe_load(fm_raw) or {}
    if not isinstance(parsed, dict):
        raise PromoteCandidateError(
            f"frontmatter is not a mapping: {type(parsed).__name__}",
            slug=None,
        )
    parsed.update(updates)
    return render_frontmatter(parsed, body)


def _render_body(sections: dict[str, str]) -> str:
    """Render `{heading: content}` back to markdown. Empty heading "" goes first
    (intro prose); the rest are emitted in insertion order with `## ` prefix."""
    parts: list[str] = []
    if "" in sections:
        intro = sections[""].strip("\n")
        if intro:
            parts.append(intro + "\n")
    for heading, content in sections.items():
        if heading == "":
            continue
        parts.append(f"## {heading}\n{content.rstrip()}\n")
    return "\n".join(parts)


def _render_canonical(
    decision: PromoteDecision,
    *,
    canonical_fields: dict,
    canonical_body: dict[str, str],
    created: date,
    updated: date,
    kind: PromoteKindConfig,
    active_profile: "ProfileString",
) -> str:
    """Render the commons-side <commons_subdir>/<slug>.md content.

    Emits schema_profile from `active_profile` (which equals
    `kind.default_profile` for bare promotes, or `kind.default_profile`
    augmented with `--mixin` extensions for Phase H bio promotes). id
    from kind.id_prefix, kind from kind.kind. For paper kind only, also
    emits a `bibkey:` field (preserved from Phase E; not in topic/theme
    mixins).
    """
    profile_str = active_profile.render()
    head: dict = {
        "schema_profile": profile_str,
        "id": f"{kind.id_prefix}{decision.slug}",
        "kind": kind.kind,
        "title": canonical_fields.get("title", ""),
        "version": decision.canonical_version,
        "created": created,
        "updated": updated,
    }
    if kind.kind == "paper":
        head["bibkey"] = decision.slug
    head["tags"] = []
    for k, v in canonical_fields.items():
        if k == "bibkey" and kind.kind != "paper":
            continue
        if k in head:
            continue
        head[k] = v

    body = _render_body(canonical_body)
    return render_frontmatter(head, body)


def _render_overlay(
    decision: PromoteDecision,
    *,
    project_only_fields: dict,
    project_only_body: dict[str, str],
    kind: PromoteKindConfig,
) -> str:
    """Render a project-side overlay file. NEVER emits schema_profile; the
    overlay validator is hardcoded to overlay/1.1 (design §4.4)."""
    head: dict = {
        "id": f"{kind.id_prefix}{decision.slug}",
        "overlay_of": f"{kind.id_prefix}{decision.slug}",
        "pin_version": decision.canonical_version,
    }
    # Skip overlay-only-management keys (overlay_of/pin_version/pin_effective_version)
    # AND any head-priority key, so project_only_fields can't accidentally
    # overwrite the promote-derived id/overlay_of/pin_version (mirrors
    # _render_canonical's guard pattern).
    for k, v in project_only_fields.items():
        if k in _OVERLAY_ONLY_KEYS:
            continue
        if k in head:
            continue
        head[k] = v

    body = _render_body(project_only_body)
    return render_frontmatter(head, body)


def _build_project_rollback_command(
    overlay_rewrites: list[dict],
    kind: PromoteKindConfig,
) -> str:
    """Build a concrete `git checkout HEAD -- <paths>` command for one project,
    given its overlay_rewrites entries from the audit log. Each entry's `path`
    is the absolute target overlay path. Optional `unlinked_source` (flatten
    case) is added to the rollback set so the source-file deletion can also be
    reverted.

    Project root is derived by stripping len(overlay_dest_subdir.parts)+1
    segments from the path (last segment is the file; preceding segments are
    the overlay_dest_subdir).
    """
    if not overlay_rewrites:
        return ""
    first_path = Path(overlay_rewrites[0]["path"])
    parents_to_strip = len(Path(kind.overlay_dest_subdir).parts) + 1
    project_root = first_path.parents[parents_to_strip - 1]

    paths: list[str] = []
    for entry in overlay_rewrites:
        target = Path(entry["path"])
        paths.append(str(target.relative_to(project_root)))
        if "unlinked_source" in entry:
            source = Path(entry["unlinked_source"])
            paths.append(str(source.relative_to(project_root)))
    paths_sorted = sorted(set(paths))
    return f"git -C {project_root} checkout HEAD -- {' '.join(paths_sorted)}"


def _audit_canonical_paths(decision: PromoteDecision, commons_root: Path) -> list[str]:
    paths: list[str] = []
    for artifact in decision.canonical_artifacts:
        try:
            _resolve_canonical_artifact_path(commons_root, artifact.path)
        except PromoteInputError:
            continue
        paths.append(str(artifact.path))
    return paths


def _render_audit_log_yaml(
    result: PromoteResult,
    commons_root: Path,
    *,
    invocation: str,
) -> str:
    """Serialize the audit log dict to YAML. Pure function — no disk I/O.
    Used by both the success path (which then writes + commits) and the
    failure path (which writes uncommitted, or falls back to stderr if the
    write itself fails)."""
    touched_set = set(result.projects_touched)
    projects_touched: dict = {}
    for decision in result.decisions:
        for slug, overlay in decision.overlays.items():
            if slug not in touched_set:
                continue
            projects_touched.setdefault(slug, {"overlay_rewrites": []})
            entry: dict = {
                "slug": decision.slug,
                "path": str(overlay.path),
                "pin_version": overlay.pin_version,
            }
            if overlay.rename_from is not None:
                entry["rename"] = {
                    "from": overlay.rename_from.name,
                    "to": overlay.path.name,
                }
            unlinked_source = getattr(overlay, "unlinked_source", None)
            if unlinked_source is not None:
                entry["unlinked_source"] = str(unlinked_source)
            projects_touched[slug]["overlay_rewrites"].append(entry)

    log: dict = {
        "op_id": result.op_id,
        "kind": result.kind.kind,
        "invocation": invocation,
        "status": result.status,
        "started_at": result.started_at.isoformat(),
        "finished_at": result.finished_at.isoformat(),
        "commons_commit": result.commons_commit,
        "commons_tags": result.tags_created,
        **(
            {
                "mixin_extensions": [
                    f"{component.name}/{component.version}" for component in result.mixin_extensions
                ]
            }
            if result.mixin_extensions
            else {}
        ),
        "projects_touched": projects_touched,
        "decisions": [_audit_decision_entry(d, result, commons_root) for d in result.decisions],
        "conflict_resolutions": [
            {
                "slug": cr.slug,
                "field": cr.field,
                "candidates": cr.candidates,
                "resolved_to": cr.resolved_to,
                "source_project": cr.source_project,
            }
            for d in result.decisions
            for cr in d.resolved_conflicts
        ],
        "failed_candidates": [
            {
                "slug": f.slug,
                "project_slug": f.project_slug,
                "source_path": str(f.source_path),
                "error_class": f.error_class,
                "error_message": f.error_message,
            }
            for f in result.failed_candidates
        ],
        "rollback": {
            "commons": (f"git -C {commons_root} revert {result.commons_commit}" if result.commons_commit else None),
            # Per design §6.5: each entry is a copy-pasteable git command,
            # not a placeholder. Derive project_root by walking up from each
            # overlay path and list every rewritten path so the operator can
            # restore exactly the touched files.
            "projects": {
                slug: _build_project_rollback_command(rewrites["overlay_rewrites"], result.kind)
                for slug, rewrites in projects_touched.items()
            },
        },
    }
    if result.failure_stage:
        log["failure_stage"] = result.failure_stage
        log["failure_detail"] = result.failure_detail

    return yaml.safe_dump(log, sort_keys=False, allow_unicode=True)


def _audit_decision_entry(
    decision: PromoteDecision,
    result: PromoteResult,
    commons_root: Path,
) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "slug": decision.slug,
        "canonical_version": decision.canonical_version,
        "canonical_paths": _audit_canonical_paths(decision, commons_root),
    }
    if result.kind.kind != "dataset":
        return entry

    extras = result.plan_audit_extras.get(decision.slug, {})
    if not isinstance(extras, Mapping):
        extras = {}
    per_resource = extras.get("per_resource", {})
    if not isinstance(per_resource, Mapping):
        per_resource = {}
    entry["per_resource_hashes"] = {
        str(name): {"hash": str(value[0]), "bytes": value[1]}
        for name, value in per_resource.items()
        if (
            isinstance(value, tuple | list)
            and len(value) == 2
            and isinstance(value[0], str)
            and isinstance(value[1], int)
        )
    }
    entry["recipe_stubbed"] = extras.get("recipe_stubbed") is True
    dropped_fields = extras.get("dropped_fields", [])
    if not isinstance(dropped_fields, list | tuple | set):
        dropped_fields = []
    entry["dropped_fields"] = [str(field) for field in dropped_fields]

    side_channel = result.side_channel_results.get(decision.slug)
    if side_channel is not None:
        if side_channel.artifact_paths:
            entry["override_file"] = str(side_channel.artifact_paths[0])
        if side_channel.backup_paths:
            entry["override_backup"] = str(side_channel.backup_paths[0])

    return entry

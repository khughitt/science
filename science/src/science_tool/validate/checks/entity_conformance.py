"""Entity-conformance health checks driven by the policy table."""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

import yaml

from science_tool.validate.findings import validation_observation
from science_tool.validate.findings import declare_validation_rules
from science_tool.entities import (
    LOCAL_PART_WIDTH,
    EntityPathPolicy,
    local_kind_warnings,
    local_part_conforms,
    markdown_entity_kinds,
    resolve_path_policy,
)
from science_tool.annotation.io import markdown_for_sidecar
from science_tool.entity_scan import iter_entity_markdown
from science_tool.validate.checks import Check, CheckObservation
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Severity

SECTION, RULES = declare_validation_rules(
    section_id="entity-conformance",
    section_title="entity conformance",
    section_order=125,
    rule_ids=("entity-conformance.check",),
    severities=frozenset({"error", "warn", "info"}),
)


def _result(
    severity: Severity,
    path: Path | None,
    message: str,
    *,
    key: list[str],
) -> CheckObservation:
    return validation_observation(
        severity=severity,
        path=path,
        line=None,
        message=message,
        rule=RULES["entity-conformance.check"],
        task=None,
        qualifiers={"key": key},
    )


def _entity_type(ctx: ValidateContext, path: Path) -> str | None:
    data = ctx.frontmatter(path)
    value = data.get("kind")
    return str(value) if value else None


def _id_kind_and_local(entity_id: object) -> tuple[str | None, str | None]:
    if isinstance(entity_id, str) and ":" in entity_id:
        kind, local = entity_id.split(":", 1)
        return kind, local
    return None, None


def _rel(ctx: ValidateContext, path: Path) -> Path:
    return path.relative_to(ctx.project_root)


def _is_paired_annotation_sidecar(path: Path) -> bool:
    try:
        markdown_path = markdown_for_sidecar(path)
    except ValueError:
        return False
    return markdown_path.is_file()


def _entity_dirs(ctx: ValidateContext, *, strategy: str | None = None) -> Iterator[tuple[str, EntityPathPolicy, Path]]:
    """Yield (kind, policy, directory) for every non-singleton markdown entity
    kind whose entities/<kind>/ directory exists. With ``strategy`` set, only
    kinds of that strategy are yielded."""
    for kind in markdown_entity_kinds(project_root=ctx.project_root):
        policy = resolve_path_policy(kind, project_root=ctx.project_root)
        if policy.strategy == "singleton":
            continue
        if strategy is not None and policy.strategy != strategy:
            continue
        directory = ctx.project_root / policy.root
        if not directory.is_dir():
            continue
        yield kind, policy, directory


@Check(
    section=SECTION,
    order=36,
    producer_id="validate.entity-conformance.local-kind-manifest",
    rules=tuple(RULES.values()),
)
def check_local_kind_manifest(ctx: ValidateContext) -> Iterator[CheckObservation]:
    """Surface local entity kinds skipped during policy loading (bad
    canonical_prefix/home/strategy, or home colliding with a core directory) as
    warnings, so a vestigial kind is visible without aborting validation."""
    for kind, reason in local_kind_warnings(ctx.project_root):
        # Always WARN: a vestigial/malformed manifest kind has no v3 entity to
        # migrate, so it does not promote to ERROR at cutover like the other checks.
        yield _result(
            Severity.WARN,
            None,
            f"local kind {kind!r} skipped during load: {reason}",
            key=["local-kind", kind],
        )


@Check(section=SECTION, order=37, producer_id="validate.entity-conformance.entity-location-coherence", rules=())
def check_entity_location_coherence(ctx: ValidateContext) -> Iterator[CheckObservation]:
    """Flag files under entities/<kind>/ whose frontmatter kind or id-kind
    disagrees with the directory (directory/kind/id coherence)."""
    for kind, policy, directory in _entity_dirs(ctx):
        for path in sorted(directory.glob("*.md")):
            data = ctx.frontmatter(path)
            ftype = data.get("kind")
            if ftype and str(ftype) != kind:
                yield _result(
                    _severity(ctx),
                    _rel(ctx, path),
                    f"kind {ftype!r} in {kind}/ directory (expected {kind})",
                    key=["directory-kind"],
                )
            id_kind, _ = _id_kind_and_local(data.get("id"))
            if id_kind is not None and id_kind != kind:
                yield _result(
                    _severity(ctx),
                    _rel(ctx, path),
                    f"id kind {id_kind!r} in {kind}/ directory (expected {kind})",
                    key=["id-kind"],
                )


@Check(section=SECTION, order=38, producer_id="validate.entity-conformance.entity-filename-conformance", rules=())
def check_entity_filename_conformance(ctx: ValidateContext) -> Iterator[CheckObservation]:
    """Flag files in entities/<kind>/ whose name violates the kind's strategy
    OR whose stem != the id's local-part."""
    for kind, policy, directory in _entity_dirs(ctx):
        for path in sorted(directory.glob("*.md")):
            if not local_part_conforms(kind, path.stem, project_root=ctx.project_root):
                yield _result(
                    _severity(ctx),
                    _rel(ctx, path),
                    f"non-conforming {kind} filename {path.name!r} (strategy={policy.strategy})",
                    key=["filename-strategy"],
                )
            data = ctx.frontmatter(path)
            _, id_local = _id_kind_and_local(data.get("id"))
            if id_local is not None and id_local != path.stem:
                yield _result(
                    _severity(ctx),
                    _rel(ctx, path),
                    f"filename stem {path.stem!r} != id local-part {id_local!r}",
                    key=["filename-id"],
                )


def _severity(ctx: ValidateContext) -> Severity:
    version = ctx.manifest.get("layout_version")
    return Severity.ERROR if isinstance(version, int) and version >= 3 else Severity.WARN


_REQUIRED_FRONTMATTER = ("id", "kind", "title", "status", "created", "updated")
_NUMBER_RE = re.compile(rf"^(\d{{{LOCAL_PART_WIDTH}}})-")


@Check(section=SECTION, order=39, producer_id="validate.entity-conformance.entity-frontmatter-completeness", rules=())
def check_entity_frontmatter_completeness(ctx: ValidateContext) -> Iterator[CheckObservation]:
    for kind, policy, directory in _entity_dirs(ctx):
        for path in sorted(directory.glob("*.md")):
            text = ctx.read_text_cached(path)
            if not text.startswith("---\n"):
                yield _result(
                    _severity(ctx),
                    _rel(ctx, path),
                    f"{path.name}: no YAML frontmatter",
                    key=["frontmatter"],
                )
                continue
            try:
                data = ctx.frontmatter(path)
            except yaml.YAMLError:
                yield _result(
                    _severity(ctx),
                    _rel(ctx, path),
                    f"{path.name}: invalid YAML frontmatter",
                    key=["frontmatter"],
                )
                continue
            missing = [field for field in _REQUIRED_FRONTMATTER if field not in data]
            if missing:
                yield _result(
                    _severity(ctx),
                    _rel(ctx, path),
                    f"{path.name}: missing frontmatter fields: {', '.join(missing)}",
                    key=["frontmatter"],
                )


@Check(section=SECTION, order=40, producer_id="validate.entity-conformance.entity-number-hygiene", rules=())
def check_entity_number_hygiene(ctx: ValidateContext) -> Iterator[CheckObservation]:
    for kind, policy, directory in _entity_dirs(ctx, strategy="numeric"):
        seen: dict[str, list[str]] = {}
        for path in sorted(directory.glob("*.md")):
            match = _NUMBER_RE.match(path.stem)
            if match is None:
                continue
            seen.setdefault(match.group(1), []).append(path.name)
        for number, names in sorted(seen.items()):
            if len(names) > 1:
                yield _result(
                    _severity(ctx),
                    policy.root,
                    f"duplicate {kind} number {number}: {', '.join(sorted(names))}",
                    key=["duplicate-number", kind, number],
                )


@Check(section=SECTION, order=41, producer_id="validate.entity-conformance.entity-stray-files", rules=())
def check_entity_stray_files(ctx: ValidateContext) -> Iterator[CheckObservation]:
    for kind, policy, directory in _entity_dirs(ctx):
        for path in sorted(directory.iterdir()):
            if path.name.startswith("."):
                # Skip hidden dotfiles: reservation sentinels (.NNNN.reserving,
                # see entity_reservation.py) and OS/editor cruft are not entities.
                continue
            if _is_paired_annotation_sidecar(path):
                continue
            if path.is_dir():
                yield _result(
                    _severity(ctx),
                    _rel(ctx, path),
                    f"unexpected subdirectory in {policy.root}/",
                    key=["unexpected-directory"],
                )
            elif path.suffix != ".md":
                yield _result(
                    _severity(ctx),
                    _rel(ctx, path),
                    f"non-entity file in {policy.root}/: {path.name}",
                    key=["non-entity-file"],
                )


@Check(section=SECTION, order=42, producer_id="validate.entity-conformance.overlay-of-in-owner-root", rules=())
def check_overlay_of_in_owner_root(ctx: ValidateContext) -> Iterator[CheckObservation]:
    """An overlay (`overlay_of:` frontmatter) is a borrow attachment and belongs
    under the dedicated overlays/<type>/ root — never under the framework owner
    root entities/ (where MarkdownAdapter would silently mint it as a spurious
    OWNER) and never in the prose-only doc/ tree (where the OverlayAdapter, which
    reads only overlays/, can no longer see it). Both placements are flagged —
    WARN during the v2->v3 transition, ERROR at layout_version >= 3. See
    docs/user-guide/project-layout.md."""
    for root_name in ("entities", "doc"):
        root = ctx.project_root / root_name
        if not root.is_dir():
            continue
        for path in iter_entity_markdown(root):
            if "templates" in path.relative_to(ctx.project_root).parts:
                continue
            text = ctx.read_text_cached(path)
            if not text.startswith("---\n"):
                continue  # no frontmatter -> cannot declare overlay_of
            try:
                data = ctx.frontmatter(path)
            except yaml.YAMLError:
                continue  # invalid YAML in registered-kind dirs is reported by check_entity_frontmatter_completeness
            if "overlay_of" in data:
                yield _result(
                    _severity(ctx),
                    _rel(ctx, path),
                    f"{path.name}: overlay_of under {root_name}/ "
                    "(overlays belong under overlays/<type>/; entities/ holds owner "
                    "declarations and doc/ is prose-only)",
                    key=["overlay-location"],
                )

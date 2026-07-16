"""Project-overlay discovery and read-time merge for the commons store.

A project carries a thin overlay file (`<project>/overlays/<type>/<slug>.md`)
for a commons entity. This module discovers, parses, validates overlay files,
checks overlay pins against the live canonical version, and merges them onto
the canonical entity per the schema's `science:merge` policy.

See docs/plans/historical/2026-05-13-multiproject-schema-and-shared-store-design.md
and docs/user-guide/project-layout.md. Overlays moved out of the prose-only doc/
tree into the dedicated overlays/ root.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from science_model.entity_schema import (
    EntityValidationError,
    EntityValidator,
    MergePolicy,
    parse_profile,
    read_merge_policy,
    read_overlay_merge_policy,
)

from science_tool.commons.adapter import CommonsEntityAdapter, CommonsEntityRecord
from science_tool.commons.config import resolve_commons_root, registry_root_for_name
from science_tool.commons.errors import (
    CommonsEntityError,
    CommonsRootNotFoundError,
    OverlayMergeError,
    OverlayValidationError,
    ProjectDirectoryMissingError,
)
from science_tool.commons.query import CommonsQuery
from science_tool.unset import is_unset
from science_tool.markdown_utils import frontmatter_span

_TYPE_TO_DIR = {
    "dataset": "datasets",
    "paper": "papers",
    "topic": "topics",
    "theme": "themes",
}
_OVERLAYS_ROOT = "overlays"


def _read_markdown_body(path: Path) -> str:
    """Return the markdown body of `path`: everything after the frontmatter."""
    _, body_start = frontmatter_span(path)
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    return "".join(lines[body_start - 1 :])


@dataclass(frozen=True, slots=True)
class OverlayRecord:
    """One validated project overlay for a commons entity."""

    canonical_id: str
    type: str
    slug: str
    project: str
    project_root: Path
    overlay_path: Path
    frontmatter: dict[str, Any]
    body: str
    pin_version: str | None
    pin_effective_version: str | None


class OverlayAdapter:
    """Discover, parse, and validate overlay files in one registered project."""

    def __init__(
        self,
        project_root: Path,
        project: str,
        validator: EntityValidator | None = None,
    ) -> None:
        self._project_root = project_root
        self._project = project
        self._validator = validator or EntityValidator()

    def load(self, canonical_id: str) -> OverlayRecord | None:
        """Load the overlay for `canonical_id`, or None if no overlay file exists.

        Raises OverlayValidationError on a malformed id, unparseable frontmatter,
        a schema failure, or an `overlay_of` that does not match the path-derived
        canonical id.
        """
        type_dir, slug = self._split_id(canonical_id)
        overlay_path = self._project_root / _OVERLAYS_ROOT / type_dir / f"{slug}.md"
        if not overlay_path.is_file():
            return None
        return self._build(canonical_id, overlay_path)

    def scan(self) -> Iterator[OverlayRecord | OverlayValidationError]:
        """Walk the project's overlays/{datasets,papers,topics,themes}/*.md overlays.

        Yields an OverlayRecord or an OverlayValidationError per file. A missing
        overlays/ directory or a missing type subdirectory yields nothing -- a
        project need not overlay every type.
        """
        for type_name, type_dir in _TYPE_TO_DIR.items():
            subdir = self._project_root / _OVERLAYS_ROOT / type_dir
            if not subdir.is_dir():
                continue
            for child in sorted(subdir.iterdir()):
                if child.suffix != ".md" or not child.is_file():
                    continue
                frontmatter, _ = frontmatter_span(child)
                if "overlay_of" not in frontmatter:
                    continue
                canonical_id = f"{type_name}:{child.stem}"
                try:
                    yield self._build(canonical_id, child)
                except OverlayValidationError as exc:
                    yield exc

    def _split_id(self, canonical_id: str) -> tuple[str, str]:
        if ":" not in canonical_id:
            raise OverlayValidationError(
                self._project_root,
                canonical_id=None,
                cause=ValueError(f"canonical id {canonical_id!r} is not in '<type>:<slug>' form"),
            )
        type_name, slug = canonical_id.split(":", 1)
        type_dir = _TYPE_TO_DIR.get(type_name)
        if type_dir is None:
            raise OverlayValidationError(
                self._project_root,
                canonical_id=canonical_id,
                cause=ValueError(f"unknown entity type {type_name!r}"),
            )
        if not slug:
            raise OverlayValidationError(
                self._project_root,
                canonical_id=canonical_id,
                cause=ValueError(f"canonical id {canonical_id!r} has an empty slug"),
            )
        if ":" in slug:
            raise OverlayValidationError(
                self._project_root,
                canonical_id=canonical_id,
                cause=ValueError(f"canonical id {canonical_id!r} has an invalid ':' in slug"),
            )
        if "/" in slug or "\\" in slug:
            raise OverlayValidationError(
                self._project_root,
                canonical_id=canonical_id,
                cause=ValueError(f"canonical id {canonical_id!r} has a path separator in slug"),
            )
        return type_dir, slug

    def _build(self, canonical_id: str, overlay_path: Path) -> OverlayRecord:
        type_name, slug = canonical_id.split(":", 1)
        try:
            frontmatter, _ = frontmatter_span(overlay_path)
            if not frontmatter:
                raise EntityValidationError(f"{overlay_path} has no parseable frontmatter")
            self._validator.validate_overlay(frontmatter)
            declared = frontmatter.get("overlay_of")
            if declared != canonical_id:
                raise EntityValidationError(
                    f"overlay_of {declared!r} does not match path-derived canonical id {canonical_id!r}"
                )
        except EntityValidationError as exc:
            raise OverlayValidationError(overlay_path, canonical_id=canonical_id, cause=exc) from exc

        return OverlayRecord(
            canonical_id=canonical_id,
            type=type_name,
            slug=slug,
            project=self._project,
            project_root=self._project_root,
            overlay_path=overlay_path,
            frontmatter=frontmatter,
            body=_read_markdown_body(overlay_path),
            pin_version=frontmatter.get("pin_version") or None,
            pin_effective_version=frontmatter.get("pin_effective_version") or None,
        )


def validate_overlay_pin(canonical: CommonsEntityRecord, overlay: OverlayRecord | None) -> None:
    """Fail if a pinned overlay does not match the resolved canonical version."""
    if overlay is None:
        return
    if overlay.pin_version is None and overlay.pin_effective_version is None:
        return
    if overlay.pin_version and overlay.pin_effective_version and overlay.pin_version != overlay.pin_effective_version:
        raise OverlayValidationError(
            overlay.overlay_path,
            canonical_id=overlay.canonical_id,
            cause=EntityValidationError(
                f"{overlay.canonical_id} pin_version {overlay.pin_version} conflicts "
                f"with pin_effective_version {overlay.pin_effective_version}"
            ),
        )
    pinned_version = overlay.pin_effective_version or overlay.pin_version
    canonical_version = canonical.frontmatter.get("version")
    if not isinstance(canonical_version, str) or not canonical_version:
        raise OverlayValidationError(
            overlay.overlay_path,
            canonical_id=overlay.canonical_id,
            cause=EntityValidationError(
                f"{overlay.canonical_id} commons canonical has no version for pin validation"
            ),
        )
    if canonical_version != pinned_version:
        raise OverlayValidationError(
            overlay.overlay_path,
            canonical_id=overlay.canonical_id,
            cause=EntityValidationError(
                f"{overlay.canonical_id} pins {pinned_version} but commons canonical is {canonical_version}"
            ),
        )


# Public: arbitration skips the same structural fields. A second frozenset in the graph would
# be a second declaration of which fields an overlay may never carry.
SKIP_OVERLAY_FIELDS = frozenset({"id", "overlay_of", "pin_version", "pin_effective_version"})


@dataclass(frozen=True, slots=True)
class MergedEntity:
    """A canonical commons entity with an optional project overlay merged in."""

    canonical: CommonsEntityRecord
    overlay: OverlayRecord | None
    merged_frontmatter: dict[str, Any]
    merged_body: str
    field_sources: dict[str, str]  # field -> canonical | overlay | canonical+overlay


def _dedup(items: list[Any]) -> list[Any]:
    """Order-preserving de-duplication for arrays of primitives."""
    seen: set[Any] = set()
    out: list[Any] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


@dataclass(frozen=True, slots=True)
class OverlayFieldConflict:
    """A borrower value the owner's policy does not admit.

    Data, not an exception: the graph arbitrates many contributions at once and must ledger
    every conflict deterministically, while the CLI merges exactly one overlay and raises on the
    first. One composition, two dispositions -- so composition reports and callers decide.
    """

    field: str
    policy: MergePolicy


@dataclass(frozen=True, slots=True)
class FrontmatterComposition:
    frontmatter: dict[str, Any]
    field_sources: dict[str, str]
    conflicts: tuple[OverlayFieldConflict, ...]


@dataclass(frozen=True, slots=True)
class FieldProposal:
    """One contributor's offer for one field.

    `contests` is the borrower/external asymmetry, and it is about STANDING, not content: a
    borrower is explicit project input and may contest an owner (producing an attributed
    conflict), while an external reference merely supports a node and is silently not offered
    when the owner has already spoken.
    """

    value: Any
    contests: bool


@dataclass(frozen=True, slots=True)
class FieldOutcome:
    """What the matrix decided, and which proposals it credits or faults for it."""

    value: Any
    changed: bool
    contributed: tuple[int, ...]
    conflicting: tuple[int, ...]


def lookup_merge_policy(
    field: str, merge_policy: Mapping[str, MergePolicy]
) -> MergePolicy | None:
    """The entity profile's policy for `field`, else the overlay schema's, else None.

    Explicit membership, not `entity_policy.get(f) or overlay_policy.get(f)`: `or` reads a
    policy's TRUTHINESS to decide whose policy applies, so a falsey policy value would silently
    hand the field to the overlay map. Which map declares a field is a fact about the maps, not
    about the value found in one.
    """
    if field in merge_policy:
        return merge_policy[field]
    overlay_policy = read_overlay_merge_policy()
    if field in overlay_policy:
        return overlay_policy[field]
    return None


def distinct_values(values: list[Any]) -> list[Any]:
    """Distinct by equality, not by hash -- proposals are frequently lists and dicts."""
    out: list[Any] = []
    for value in values:
        if not any(value == seen for seen in out):
            out.append(value)
    return out


def resolve_field(
    policy: MergePolicy,
    owner_value: Any,
    proposals: Sequence[FieldProposal],
) -> FieldOutcome:
    """Apply one merge policy to an owner's value and every proposal against it.

    THE role matrix -- the CLI (one overlay) and the graph (n contributions) both resolve here,
    so an overlay cannot mean one thing to `science commons show` and another to the graph.

    Position never decides a scalar. Proposal order is meaningful for APPEND, where sequence is
    the value, and meaningless everywhere else: differing scalar proposals are a CONFLICT, not a
    race the earliest source wins. Letting a lower source position confer authority would make a
    bib line number decide an entity's DOI.
    """
    if policy is MergePolicy.APPEND:
        base = [] if is_unset(owner_value) else list(owner_value)
        merged = list(base)
        contributed: list[int] = []
        for index, proposal in enumerate(proposals):
            if is_unset(proposal.value):
                continue
            added = False
            for item in list(proposal.value):
                if item not in merged:
                    merged.append(item)
                    added = True
            if added:
                contributed.append(index)
        return FieldOutcome(
            value=merged,
            changed=merged != base,
            contributed=tuple(contributed),
            conflicting=(),
        )

    if policy is MergePolicy.PROJECT_ONLY:
        # A project's own field. An external reference has no project standing and does not
        # propose one; only borrowers are considered.
        offers = [(i, p) for i, p in enumerate(proposals) if p.contests]
        if not offers:
            return FieldOutcome(owner_value, False, (), ())
        distinct = distinct_values([p.value for _, p in offers])
        if len(distinct) == 1:
            return FieldOutcome(
                value=distinct[0],
                changed=distinct[0] != owner_value,
                contributed=tuple(i for i, _ in offers),
                conflicting=(),
            )
        return FieldOutcome(owner_value, False, (), tuple(i for i, _ in offers))

    if policy is MergePolicy.REPLACE:
        if not is_unset(owner_value):
            # The owner has spoken. A borrower contesting that is an attributed conflict; an
            # external offering it is simply not offered.
            return FieldOutcome(
                value=owner_value,
                changed=False,
                contributed=(),
                conflicting=tuple(
                    i for i, p in enumerate(proposals) if p.contests and not is_unset(p.value)
                ),
            )
        offers = [(i, p) for i, p in enumerate(proposals) if not is_unset(p.value)]
        if not offers:
            return FieldOutcome(owner_value, False, (), ())
        distinct = distinct_values([p.value for _, p in offers])
        if len(distinct) == 1:
            # Every proposal agrees: collapse, and credit all of them.
            return FieldOutcome(
                value=distinct[0],
                changed=True,
                contributed=tuple(i for i, _ in offers),
                conflicting=(),
            )
        # They disagree. The vacancy STAYS a vacancy: filling it from the lowest-ordered source
        # would resolve a genuine disagreement by file position.
        return FieldOutcome(owner_value, False, (), tuple(i for i, _ in offers))

    # FORBIDDEN
    return FieldOutcome(
        value=owner_value,
        changed=False,
        contributed=(),
        conflicting=tuple(
            i for i, p in enumerate(proposals) if p.contests and not is_unset(p.value)
        ),
    )


def compose_frontmatter(
    canonical: Mapping[str, Any],
    overlay: Mapping[str, Any],
    merge_policy: Mapping[str, MergePolicy],
    *,
    canonical_id: str,
) -> FrontmatterComposition:
    """Compose validated canonical and overlay frontmatter without I/O.

    The CLI's single-overlay wrapper over `resolve_field`, which is the shared matrix.
    """
    merged = dict(canonical)
    field_sources: dict[str, str] = {key: "canonical" for key in merged}
    conflicts: list[OverlayFieldConflict] = []

    for field, value in overlay.items():
        if field in SKIP_OVERLAY_FIELDS:
            continue
        policy = lookup_merge_policy(field, merge_policy)
        if policy is None:
            raise OverlayMergeError(field=field, canonical_id=canonical_id)

        outcome = resolve_field(
            policy, merged.get(field), (FieldProposal(value=value, contests=True),)
        )
        if outcome.conflicting:
            conflicts.append(OverlayFieldConflict(field=field, policy=policy))
            continue
        if policy is MergePolicy.APPEND:
            merged[field] = outcome.value
            field_sources[field] = "canonical+overlay"
        elif outcome.contributed:
            merged[field] = outcome.value
            field_sources[field] = "overlay"

    return FrontmatterComposition(
        frontmatter=merged,
        field_sources=field_sources,
        conflicts=tuple(conflicts),
    )


def merge_entity(
    canonical: CommonsEntityRecord,
    overlay: OverlayRecord | None,
    merge_policy: dict[str, MergePolicy],
) -> MergedEntity:
    """Merge an overlay onto a canonical entity per the `science:merge` policy.

    `merge_policy` is read_merge_policy(parse_profile(canonical.schema_profile)).
    Overlay-only fields (relevance, hypothesis_links, ...) resolve via
    read_overlay_merge_policy(). pin_version is carried on the overlay but is
    NOT acted on in D1 — the CLI emits the "pinning inactive" warning.
    """
    canonical_body = _read_markdown_body(canonical.body_path)

    if overlay is None:
        merged = dict(canonical.frontmatter)
        return MergedEntity(
            canonical=canonical,
            overlay=None,
            merged_frontmatter=merged,
            merged_body=canonical_body,
            field_sources={key: "canonical" for key in merged},
        )

    composition = compose_frontmatter(
        canonical.frontmatter,
        overlay.frontmatter,
        merge_policy,
        canonical_id=canonical.canonical_id,
    )
    if composition.conflicts:
        # The CLI merges one overlay, so the first conflict is the answer. Sorted by field, so
        # an overlay conflicting on two fields names the same one on every run.
        first = sorted(composition.conflicts, key=lambda conflict: conflict.field)[0]
        raise OverlayMergeError(field=first.field, canonical_id=canonical.canonical_id)
    merged = composition.frontmatter
    field_sources = composition.field_sources

    if overlay.body.strip():
        merged_body = canonical_body + "\n\n" + overlay.body
    else:
        merged_body = canonical_body

    return MergedEntity(
        canonical=canonical,
        overlay=overlay,
        merged_frontmatter=merged,
        merged_body=merged_body,
        field_sources=field_sources,
    )


def resolve_entity(canonical_id: str, project: str | None = None) -> MergedEntity:
    """Resolve a commons entity, optionally merged with a project overlay.

    With `project=None`, returns a canonical-only MergedEntity. With a project
    name, reads the project's overlay (if any) and merges it. Raises
    CommonsRootNotFoundError, CommonsEntityError (unknown id),
    ProjectNotRegisteredError (unknown project name), or
    ProjectDirectoryMissingError (registered project whose directory is gone).
    """
    root = resolve_commons_root()
    if not root.is_dir():
        raise CommonsRootNotFoundError(root)

    record = CommonsQuery(root).show(canonical_id)
    policy = read_merge_policy(parse_profile(record.schema_profile))

    if project is None:
        return merge_entity(record, None, policy)

    project_root = registry_root_for_name(project)
    if not project_root.is_dir():
        raise ProjectDirectoryMissingError(project, project_root)

    overlay = OverlayAdapter(project_root, project).load(canonical_id)
    return merge_entity(record, overlay, policy)


@dataclass(frozen=True)
class OverlayValidationReport:
    """Result of validating every overlay file in one project."""

    checked: int
    errors: list[OverlayValidationError]


def validate_project_overlays(project: str) -> OverlayValidationReport:
    """Validate every overlay file in a registered project.

    Each overlay is checked against the overlay schema (via OverlayAdapter.scan)
    and its `overlay_of` is confirmed to resolve to a real canonical entity in
    the commons store. Raises CommonsRootNotFoundError, ProjectNotRegisteredError,
    or ProjectDirectoryMissingError before scanning.
    """
    root = resolve_commons_root()
    if not root.is_dir():
        raise CommonsRootNotFoundError(root)

    project_root = registry_root_for_name(project)
    if not project_root.is_dir():
        raise ProjectDirectoryMissingError(project, project_root)

    commons_adapter = CommonsEntityAdapter(root)
    checked = 0
    errors: list[OverlayValidationError] = []
    for item in OverlayAdapter(project_root, project).scan():
        checked += 1
        if isinstance(item, OverlayValidationError):
            errors.append(item)
            continue
        try:
            commons_adapter.load(item.canonical_id)
        except CommonsEntityError as exc:
            errors.append(
                OverlayValidationError(
                    item.overlay_path,
                    canonical_id=item.canonical_id,
                    cause=exc,
                )
            )
    return OverlayValidationReport(checked=checked, errors=errors)

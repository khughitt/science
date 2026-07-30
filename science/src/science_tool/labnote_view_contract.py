"""Structural contract for Labnote view descriptors.

Both the exporter and `science validate` consume this module, so a descriptor that
the exporter will write is judged by exactly the rules the validator enforces.

Routes are derived, never declared: the surface set is closed and owned by the
consumer, and the route suffix is the view ID with underscores replaced by hyphens.
`view.id` is the routing identity; `entity_types` is the declared bridge from that
identity to producer kinds. A view ID is never compared against an entity type.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

from science_model.audit.fingerprint import canonical_json

PRODUCER_VIEW_SURFACES: frozenset[str] = frozenset({"explore", "findings"})
VIEW_ID_RE: re.Pattern[str] = re.compile(r"^[a-z][a-z0-9_]*$")
HIDDEN_KIND_REASONS: frozenset[str] = frozenset({"declared_hidden", "fallback_hidden"})


@dataclass(frozen=True)
class DescriptorError:
    """One structural defect in a view descriptor.

    `identity` is a stable canonical key for the element the error refers to, so
    consumers can deduplicate on `(code, field, identity)` without re-deriving
    descriptor identity. It is the canonical content of the element for ordinary
    errors, the shared key for duplicate-group errors, and `None` for errors about
    the document as a whole.
    """

    code: str
    field: str
    message: str
    identity: str | None


def route_for_view(view_id: str, surface: str) -> str:
    """Derive the conventional route for a view, validating both inputs first."""
    if surface not in PRODUCER_VIEW_SURFACES:
        legal = ", ".join(sorted(PRODUCER_VIEW_SURFACES))
        raise ValueError(f"invalid surface {surface!r}: must be one of {legal}")
    if not isinstance(view_id, str) or not VIEW_ID_RE.match(view_id):
        raise ValueError(f"invalid view id {view_id!r}: must match {VIEW_ID_RE.pattern}")
    return f"/{surface}/{view_id.replace('_', '-')}"


def _identity(value: object) -> str:
    return canonical_json(value).decode("utf-8")


def _valid_entity_types(value: object) -> bool:
    return (
        isinstance(value, list)
        and len(value) > 0
        and all(isinstance(item, str) and item.strip() for item in value)
    )


def _valid_entity_count(value: object) -> bool:
    # bool is a subclass of int; True must not pass as a count.
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _view_errors(index: int, view: object) -> list[DescriptorError]:
    field = f"views[{index}]"
    if not isinstance(view, dict):
        return [
            DescriptorError(
                code="view-malformed",
                field=field,
                message=f"{field}: view must be a mapping",
                identity=_identity(view),
            )
        ]

    identity = _identity(view)
    errors: list[DescriptorError] = []
    view_id = view.get("id")
    surface = view.get("surface")

    id_ok = isinstance(view_id, str) and bool(VIEW_ID_RE.match(view_id))
    surface_ok = surface in PRODUCER_VIEW_SURFACES

    if not surface_ok:
        legal = ", ".join(sorted(PRODUCER_VIEW_SURFACES))
        errors.append(
            DescriptorError(
                code="view-surface-invalid",
                field=f"{field}.surface",
                message=f"{field}: surface {surface!r} must be one of {legal}",
                identity=identity,
            )
        )
    if not id_ok:
        errors.append(
            DescriptorError(
                code="view-id-invalid",
                field=f"{field}.id",
                message=f"{field}: id {view_id!r} must match {VIEW_ID_RE.pattern}",
                identity=identity,
            )
        )
    if id_ok and surface_ok:
        expected = route_for_view(view_id, surface)  # type: ignore[arg-type]
        if view.get("route") != expected:
            errors.append(
                DescriptorError(
                    code="view-route-mismatch",
                    field=f"{field}.route",
                    message=(
                        f"view {view_id}: route {view.get('route')!r} must be derived as {expected!r}"
                    ),
                    identity=identity,
                )
            )
    if not _valid_entity_types(view.get("entity_types")):
        errors.append(
            DescriptorError(
                code="view-entity-types-missing",
                field=f"{field}.entity_types",
                message=f"{field}: views must declare non-empty entity_types of strings",
                identity=identity,
            )
        )
    return errors


def _hidden_entry_errors(index: int, entry: object) -> list[DescriptorError]:
    field = f"hidden_kinds[{index}]"
    if not isinstance(entry, dict):
        return [
            DescriptorError(
                code="hidden-kinds-malformed",
                field=field,
                message=f"{field}: hidden kind entry must be a mapping",
                identity=_identity(entry),
            )
        ]

    identity = _identity(entry)
    errors: list[DescriptorError] = []
    entity_type = entry.get("entity_type")
    if not isinstance(entity_type, str) or not entity_type.strip():
        errors.append(
            DescriptorError(
                code="hidden-kinds-malformed",
                field=f"{field}.entity_type",
                message=f"{field}: entity_type must be a non-empty string",
                identity=identity,
            )
        )
    reason = entry.get("reason")
    if reason not in HIDDEN_KIND_REASONS:
        legal = ", ".join(sorted(HIDDEN_KIND_REASONS))
        errors.append(
            DescriptorError(
                code="hidden-kinds-malformed",
                field=f"{field}.reason",
                message=f"{field}: reason {reason!r} must be one of {legal}",
                identity=identity,
            )
        )
    if not _valid_entity_count(entry.get("entity_count")):
        errors.append(
            DescriptorError(
                code="hidden-kinds-malformed",
                field=f"{field}.entity_count",
                message=(
                    f"{field}: entity_count {entry.get('entity_count')!r} "
                    "must be a non-negative integer"
                ),
                identity=identity,
            )
        )
    return errors


def descriptor_errors(views: object) -> list[DescriptorError]:
    """Return every structural error in a view descriptor, never just the first."""
    if not isinstance(views, dict):
        return [
            DescriptorError(
                code="views-json-invalid",
                field="views.json",
                message="views.json must contain a JSON object",
                identity=None,
            )
        ]

    raw_views = views.get("views", [])
    if not isinstance(raw_views, list):
        return [
            DescriptorError(
                code="views-json-invalid",
                field="views",
                message=f"views must be an array, got {type(raw_views).__name__}",
                identity=None,
            )
        ]

    errors: list[DescriptorError] = []
    for index, view in enumerate(raw_views):
        errors.extend(_view_errors(index, view))

    # view.id is the routing identity: Labnote keys its overlay map on it and would
    # silently keep only the last of a duplicate pair.
    view_ids = [view["id"] for view in raw_views if isinstance(view, dict) and isinstance(view.get("id"), str)]
    for view_id, count in sorted(Counter(view_ids).items()):
        if count > 1:
            errors.append(
                DescriptorError(
                    code="view-malformed",
                    field="views[].id",
                    message=f"view id {view_id!r} is declared {count} times; view ids must be unique",
                    identity=view_id,
                )
            )

    raw_hidden = views.get("hidden_kinds", [])
    if not isinstance(raw_hidden, list):
        errors.append(
            DescriptorError(
                code="hidden-kinds-malformed",
                field="hidden_kinds",
                message=f"hidden_kinds must be an array, got {type(raw_hidden).__name__}",
                identity=None,
            )
        )
        return errors

    for index, entry in enumerate(raw_hidden):
        errors.extend(_hidden_entry_errors(index, entry))

    hidden_types = [
        entry["entity_type"]
        for entry in raw_hidden
        if isinstance(entry, dict) and isinstance(entry.get("entity_type"), str)
    ]
    for entity_type, count in sorted(Counter(hidden_types).items()):
        if count > 1:
            errors.append(
                DescriptorError(
                    code="hidden-kinds-malformed",
                    field="hidden_kinds[].entity_type",
                    message=(
                        f"entity_type {entity_type!r} is declared {count} times; "
                        "there must be at most one entry per kind"
                    ),
                    identity=entity_type,
                )
            )

    visible_types = {
        entity_type
        for view in raw_views
        if isinstance(view, dict) and _valid_entity_types(view.get("entity_types"))
        for entity_type in view["entity_types"]
    }
    for entity_type in sorted(visible_types.intersection(hidden_types)):
        errors.append(
            DescriptorError(
                code="kind-visible-and-hidden",
                field="hidden_kinds[].entity_type",
                message=(
                    f"kind {entity_type!r} is both declared visible through entity_types "
                    "and listed in hidden_kinds"
                ),
                identity=entity_type,
            )
        )
    return errors

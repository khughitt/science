"""Collect commons references needed by graph builds.

Graph loading can depend on Science Commons entries, but commons loading
must remain independent of project graph materialization. This module keeps
that dependency one-way by extracting referenced commons IDs from already
loaded project graph sources without performing I/O or commons access.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from science_model.entities import Entity
from science_model.entity_schema import MergePolicy, parse_profile, read_merge_policy
from science_model.ontologies.schema import OntologyCatalog
from science_model.source_contracts import BindingSource
from science_model.source_ref import SourceRef

from science_tool.commons.adapter import CommonsEntityRecord
from science_tool.commons.config import resolve_commons_root
from science_tool.commons.errors import (
    CommonsEntityError,
    CommonsRootNotFoundError,
    OverlayValidationError,
)
from science_tool.commons.geneset import GenesetCollectionError, parse_geneset_rows
from science_tool.commons.geneset_resources import geneset_resource_frontmatter, read_member_rows
from science_tool.commons.overlay import OverlayAdapter, OverlayRecord, validate_overlay_pin
from science_tool.commons.query import CommonsQuery
from science_tool.graph.entity_registry import EntityRegistry
from science_tool.graph.identity_arbitration import (
    AttachmentContribution,
    EntityContribution,
    SourceContribution,
)
from science_tool.graph.identity_table import COMMONS_SCOPE, IdentityDeclaration, ParticipationMode
from science_tool.graph.sources import (
    SourceRelation,
    _enrich_raw,
    _normalize_kind,
    is_external_reference,
    is_metadata_reference,
)

# The PUBLIC adapter name for a commons owner row. `classify_owner_scope` already maps it to
# owner_scope "commons"; a second alias would be a second name for one fact.
_COMMONS_ADAPTER = "commons-merged"

_COMMONS_TYPES = frozenset({"dataset", "paper", "topic", "theme"})
_TYPE_TO_DIR = {"dataset": "datasets", "paper": "papers", "topic": "topics", "theme": "themes"}
_OVERLAY_ONLY_FIELDS = (
    "relevance",
    "hypothesis_links",
    "task_links",
    "question_links",
    "project_tags",
    "project_notes",
    "source",
)
_AUDITED_LIST_FIELDS = (
    "related",
    "commits_to",
    "blocked_by",
    "source_refs",
    "evidence_refs",
    "chain",
    "proposition_refs",
    "same_as",
)
_MATERIALIZED_LIST_FIELDS = ("participants", "propositions")


@dataclass(frozen=True)
class CommonsClosure:
    """Everything commons contributes to this load, decided by nobody."""

    contributions: tuple[SourceContribution, ...]
    field_policies: dict[tuple[str, str], dict[str, MergePolicy]]


def collect_commons_contributions(
    *,
    project_root: Path,
    project_slug: str,
    seed_entities: Iterable[Entity],
    project_relations: list[SourceRelation],
    project_bindings: list[BindingSource],
    registry: EntityRegistry,
    active_kinds: frozenset[str],
    ontology_catalogs: list[OntologyCatalog],
) -> CommonsClosure:
    """Close over every commons id this project reaches, and contribute all of them.

    Takes no identity table, no owned-id set, no selection of any kind. Those are arbitration's
    concepts, and letting them in here is how commons came to be suppressed for any id the
    project had already materialized -- including ids a bib entry merely cited. Close answers
    "what does commons say"; whether commons WINS is decided later, once everything has spoken.
    """
    collector = _CommonsClosureCollector(
        project_root=project_root,
        project_slug=project_slug,
        registry=registry,
        active_kinds=active_kinds,
        ontology_catalogs=ontology_catalogs,
    )
    return collector.collect(
        seed_entities=seed_entities,
        project_relations=project_relations,
        project_bindings=project_bindings,
    )


class _CommonsClosureCollector:
    def __init__(
        self,
        *,
        project_root: Path,
        project_slug: str,
        registry: EntityRegistry,
        active_kinds: frozenset[str],
        ontology_catalogs: list[OntologyCatalog],
    ) -> None:
        self._project_root = project_root
        self._project_slug = project_slug
        self._registry = registry
        self._active_kinds = active_kinds
        self._ontology_catalogs = ontology_catalogs

    def collect(
        self,
        *,
        seed_entities: Iterable[Entity],
        project_relations: list[SourceRelation],
        project_bindings: list[BindingSource],
    ) -> CommonsClosure:
        overlays = self._scan_overlays()
        pending = self._seed(
            seed_entities=seed_entities,
            project_relations=project_relations,
            project_bindings=project_bindings,
            overlays=overlays,
        )
        if not pending:
            return CommonsClosure(contributions=(), field_policies={})

        commons_root = resolve_commons_root()
        if not commons_root.is_dir():
            raise CommonsRootNotFoundError(commons_root)
        # A stale commons registry silently composes an out-of-date snapshot into the
        # project graph while `validate` reports green. Warn (once, via the query's
        # own warn-once guard) rather than silence it (fb-2026-07-16-005).
        query = CommonsQuery(commons_root)

        contributions: list[SourceContribution] = []
        field_policies: dict[tuple[str, str], dict[str, MergePolicy]] = {}
        # `visited` deduplicates I/O ONLY. It never suppresses a declaration: an id reached
        # again from another authority has already contributed, and contributing twice from one
        # commons record would be a second claim commons never made.
        visited: set[str] = set()

        while pending:
            canonical_id = min(pending)
            pending.discard(canonical_id)
            if canonical_id in visited:
                continue
            visited.add(canonical_id)

            overlay = overlays.get(canonical_id)
            record = self._resolve(query, canonical_id, overlay)
            if record is None:
                continue

            # BEFORE any contribution exists, and for every resolved overlay -- including one
            # whose id a project owner or bib entry also claims. The pin is a statement about
            # the commons version this overlay was written against; whether the overlay ends up
            # composing into the graph does not make a stale pin true.
            validate_overlay_pin(record, overlay)
            field_policies[(COMMONS_SCOPE, canonical_id)] = read_merge_policy(
                parse_profile(record.schema_profile)
            )

            candidate = _materialize_commons_candidate(
                record,
                registry=self._registry,
                project_slug=self._project_slug,
                active_kinds=self._active_kinds,
                ontology_catalogs=self._ontology_catalogs,
            )
            contributions.append(
                EntityContribution(
                    declaration=IdentityDeclaration(
                        canonical_id=canonical_id,
                        participation_mode=ParticipationMode.OWNER,
                        owner_scope=COMMONS_SCOPE,
                        adapter=_COMMONS_ADAPTER,
                        source_ref=SourceRef(
                            adapter_name=_COMMONS_ADAPTER,
                            path=_commons_source_ref_path(record.type, record.slug),
                        ),
                    ),
                    candidate=candidate,
                )
            )
            if overlay is not None:
                contributions.append(
                    AttachmentContribution(
                        declaration=IdentityDeclaration(
                            canonical_id=canonical_id,
                            participation_mode=ParticipationMode.BORROWER,
                            owner_scope=COMMONS_SCOPE,
                            adapter="overlay",
                            source_ref=SourceRef(
                                adapter_name="overlay", path=str(overlay.overlay_path)
                            ),
                        ),
                        record=overlay,
                    )
                )

            pending |= self._references_of(candidate) - visited

        return CommonsClosure(
            contributions=tuple(contributions),
            field_policies=field_policies,
        )

    def _scan_overlays(self) -> dict[str, OverlayRecord]:
        overlays: dict[str, OverlayRecord] = {}
        if not (self._project_root / "overlays").exists():
            return overlays
        for item in OverlayAdapter(self._project_root, self._project_slug).scan():
            if isinstance(item, OverlayValidationError):
                raise item
            overlays[item.canonical_id] = item
        return overlays

    def _seed(
        self,
        *,
        seed_entities: Iterable[Entity],
        project_relations: list[SourceRelation],
        project_bindings: list[BindingSource],
        overlays: dict[str, OverlayRecord],
    ) -> set[str]:
        pending = collect_referenced_commons_ids(
            project_root=self._project_root,
            project_entities=list(seed_entities),
            project_relations=project_relations,
            project_bindings=project_bindings,
        )
        # Every overlay seeds its own id. An overlay is a project's explicit statement that it
        # borrows this entity, which is a reference in its own right -- it does not need some
        # other file to also mention the id before commons is consulted.
        pending |= set(overlays)
        for overlay in overlays.values():
            pending |= _overlay_references(overlay)
        return pending

    def _resolve(
        self, query: CommonsQuery, canonical_id: str, overlay: OverlayRecord | None
    ) -> CommonsEntityRecord | None:
        try:
            return query.show(canonical_id)
        except CommonsEntityError as exc:
            if overlay is not None:
                # An overlay whose canonical does not exist is a broken overlay, not a missing
                # reference: the project asserted it borrows something commons does not have.
                raise OverlayValidationError(
                    overlay.overlay_path, canonical_id=canonical_id, cause=exc
                ) from exc
            # A plain unknown reference is not this layer's error; it surfaces downstream as an
            # unresolved reference, where the reader can see what pointed at it.
            return None

    def _references_of(self, candidate: Entity) -> set[str]:
        """A resolved canonical's own references.

        Overlays are NOT re-scanned here. Every overlay is known before the loop starts, so
        `_seed` has already contributed all of their references; scanning them again per
        canonical would be a second path to the same ids -- and two paths to one fact means
        neither is load-bearing, so breaking either leaves every test green.
        """
        return collect_referenced_commons_ids(
            project_root=self._project_root,
            project_entities=[candidate],
            project_relations=[],
            project_bindings=[],
        )


def _overlay_references(overlay: OverlayRecord) -> set[str]:
    """Commons ids an overlay's frontmatter reaches.

    Read off the raw frontmatter rather than a materialized entity: an overlay is a partial
    record that need not validate as an Entity on its own, so there is nothing to walk fields
    on. `overlay_of` is excluded -- it names the entity being borrowed, which is already this
    id, not a reference out to another one.
    """
    found: set[str] = set()
    for field_name, value in overlay.frontmatter.items():
        if field_name in {"id", "overlay_of"}:
            continue
        if isinstance(value, str):
            _maybe_add(found, value)
        elif isinstance(value, list):
            for item in value:
                _maybe_add(found, item)
    return found


def collect_referenced_commons_ids(
    *,
    project_root: Path | None = None,
    project_entities: list[Entity],
    project_relations: list[SourceRelation],
    project_bindings: list[BindingSource],
) -> set[str]:
    """Return commons canonical IDs referenced by project graph sources."""
    found: set[str] = set()
    for entity in project_entities:
        for field_name in (*_AUDITED_LIST_FIELDS, *_MATERIALIZED_LIST_FIELDS):
            for raw in getattr(entity, field_name, None) or []:
                _maybe_add(found, raw)
        _maybe_add(found, getattr(entity, "audits", None))
        for usage in getattr(entity, "dataset_usage", None) or []:
            _maybe_add(found, getattr(usage, "ref", None))
        derivation = getattr(entity, "derivation", None)
        for raw in getattr(derivation, "inputs", None) or []:
            _maybe_add(found, raw)
        if project_root is not None:
            _collect_geneset_row_usage_refs(found, project_root=project_root, entity=entity)

    for relation in project_relations:
        _maybe_add(found, relation.subject)
        _maybe_add(found, relation.object)

    for binding in project_bindings:
        _maybe_add(found, binding.model)
        _maybe_add(found, binding.parameter)
        for raw in binding.source_refs:
            _maybe_add(found, raw)

    return found


def _collect_geneset_row_usage_refs(found: set[str], *, project_root: Path, entity: Entity) -> None:
    if getattr(entity, "kind", None) != "dataset":
        return
    file_path = getattr(entity, "file_path", None)
    if not isinstance(file_path, str) or not file_path:
        return
    rel_path = Path(file_path)
    fm = geneset_resource_frontmatter(project_root, rel_path)
    if fm is None:
        return
    raw_rows = read_member_rows(project_root, fm)
    if raw_rows is None or isinstance(raw_rows, Exception):
        return
    try:
        rows = parse_geneset_rows(raw_rows)
    except GenesetCollectionError:
        return
    for row in rows:
        for usage in row.dataset_usage:
            _maybe_add(found, usage.get("ref"))


def _materialize_commons_candidate(
    record: CommonsEntityRecord,
    *,
    registry: EntityRegistry,
    project_slug: str,
    active_kinds: frozenset[str],
    ontology_catalogs: list[OntologyCatalog],
) -> Entity:
    """The commons canonical as a CANDIDATE -- the overlay is not applied here.

    Close produces contributions; it does not compose them. The overlay travels beside this
    candidate as its own AttachmentContribution, and arbitration composes the two under the
    field policy. Merging here would compose before the full contribution set existed, which is
    what let a project overlay silently beat contributors nobody had collected yet.
    """
    fm = dict(record.frontmatter)
    raw_kind = fm.get("kind")
    if not isinstance(raw_kind, str) or not raw_kind:
        canonical_id = fm.get("id")
        raise CommonsEntityError(
            record.body_path,
            canonical_id=canonical_id if isinstance(canonical_id, str) else None,
            cause=ValueError("missing kind"),
        )
    kind = _normalize_kind(raw_kind)
    schema = registry.resolve(kind)
    raw: dict[str, object] = dict(fm)
    raw["kind"] = kind
    raw["canonical_id"] = fm["id"]
    # Only for kinds that actually DECLARE `summary`. This used to be unconditional, and it worked
    # only because `Entity` was `extra="ignore"`: on a `topic` (no `summary` field) the key was set
    # here and silently eaten at `model_validate`. With the projection preserving what the schema
    # admits (D3.3), an eaten key becomes a kept one -- and `materialize._add_entity` reads
    # `getattr(entity, "summary", "")` into `schema:description`, so every commons topic would have
    # started emitting a triple it has never had. The drop was load-bearing and nobody knew.
    if "description" in fm and "summary" not in fm and "summary" in schema.model_fields:
        raw["summary"] = fm["description"]
    if kind == "paper" and "journal" in fm and not raw.get("venue"):
        raw["venue"] = fm["journal"]
    raw["scope"] = "shared"
    raw["profile"] = "shared"
    raw["file_path"] = str(record.body_path)
    for overlay_only in _OVERLAY_ONLY_FIELDS:
        raw.pop(overlay_only, None)
    raw.pop("schema_profile", None)
    _enrich_raw(
        raw,
        kind=kind,
        project_slug=project_slug,
        local_profile="shared",
        active_kinds=active_kinds,
        ontology_catalogs=ontology_catalogs,
    )
    return schema.model_validate(raw)


def _commons_source_ref_path(type_name: str, slug: str) -> str:
    type_dir = _TYPE_TO_DIR[type_name]
    if type_name == "dataset":
        return f"commons://{type_dir}/{slug}/entity.md"
    return f"commons://{type_dir}/{slug}.md"


def _maybe_add(found: set[str], raw: object) -> None:
    if not isinstance(raw, str):
        return
    if not raw:
        return
    if is_external_reference(raw):
        return
    if is_metadata_reference(raw):
        return
    if ":" not in raw:
        return
    prefix, value = raw.split(":", 1)
    if prefix in _COMMONS_TYPES:
        if value:
            found.add(raw)
        return
    # Scoped reference form commons:<kind>:<slug> (design §B3a): strip the leading
    # "commons" scope and collect the underlying commons id, so a scoped ref pulls
    # and records its commons owner. (Only the "commons" scope is recognized here;
    # project-name and federated scopes are out of scope until t068.)
    if prefix == "commons" and ":" in value:
        inner_prefix, inner_value = value.split(":", 1)
        if inner_prefix in _COMMONS_TYPES and inner_value:
            found.add(value)

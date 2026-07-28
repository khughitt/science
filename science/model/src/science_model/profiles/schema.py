"""Profile schema for layered Science knowledge graph models."""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import Any, Literal, cast

from pydantic import BaseModel, Field, SerializerFunctionWrapHandler, model_serializer, model_validator

from science_model.identity import CurationScope, EntityClass

EntityFilenameStrategy = Literal["numeric", "citekey", "singleton", "slug", "verbatim", "id-local"]


# Fields the toolkit rules, which an externally loaded manifest may not author. A project cannot
# install a packaged type mixin, so it cannot arm schema closure for itself.
_TOOLKIT_RESERVED_KIND_FIELDS = frozenset({"schema_closed"})


class KindCategory(StrEnum):
    """Named-contract taxonomy for kinds (design §2.3)."""

    AUTHORED_CORE = "authored-core"
    RESERVED = "reserved"
    SOURCE_ONLY = "source-only"


class EntityKind(BaseModel):
    """An entity kind declared by a knowledge profile."""

    name: str
    canonical_prefix: str
    layer: str
    description: str
    entity_class: EntityClass | None = None
    category: KindCategory | None = None  # None for project-local kinds (only built-in profiles set it)
    template_ready: bool = False  # renders through the migrated Renderer path (== today's MIGRATED_KINDS)
    curation_scope: CurationScope | None = None  # design §5: authored per kind; None = undeclared (registry applies the default)
    shortform: str | None = None  # single-letter CLI alias, e.g. "h" -> hypothesis
    # Layout/status overrides for project-local markdown kinds (v3 layout). All
    # optional; defaults derive name->entities/<name>/, numeric strategy, "active".
    home: str | None = None
    strategy: str | None = None  # raw manifest input; the EntityFilenameStrategy vocab is enforced tool-side by the path-policy loader, not at the schema boundary
    default_status: str | None = None
    statuses: list[str] | None = None
    # Lineage capability (S2): can an entity of this kind be replaced as canonical by a newer one?
    # DECLARED per kind -- never inferred from `statuses`, which is how the two drifted. Defaults
    # False because project-authored manifest kinds validate through this model and must not be
    # forced to declare; a test asserts every SHIPPED kind sets it explicitly.
    supersedable: bool = False
    # Schema-first closure: does this kind validate through a COMPOSED entity profile with
    # `unevaluatedProperties: false`? DECLARED per kind. `PROJECT_MIXIN_NAMES` derives from this,
    # so flipping it to True arms strictness, Markdown load validation, write-boundary validation
    # and `strict_schema_kinds` in ONE edit -- there is deliberately no separate strictness switch.
    # Defaults False because project-authored manifest kinds validate through this same model and
    # must not be forced to declare; a test asserts every SHIPPED kind sets it explicitly, so a
    # shipped kind that merely FORGOT is distinguishable from one ruled open. A project manifest
    # that authors it is REJECTED (see ProfileManifest) -- a project cannot install a packaged
    # type mixin, so honouring the field there would be a claim the toolkit cannot make true.
    schema_closed: bool = False
    # Structured-source declaration: a project-local kind whose entities are
    # generated/maintained as rows in a single-type YAML data file under
    # knowledge/sources/<profile>/ (NOT the multi-type entities.yaml/terms.yaml
    # aggregate). Each row loads as an owner of this kind. `structured_source` is
    # the filename relative to the profile sources dir; `structured_source_root_key`
    # is the YAML root key holding the row list (defaults to the kind `name`).
    structured_source: str | None = None
    structured_source_root_key: str | None = None

    @model_serializer(mode="wrap")
    def _omit_unset_toolkit_fields(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        """Do not turn an internal default into externally authored manifest input.

        Explicit declarations remain visible. A dumped packaged profile is therefore not an
        external manifest: once trusted objects become raw mappings, accepting their reserved
        fields would let an external author claim the same trust with no distinguishable
        provenance.
        """
        dumped = cast(dict[str, Any], handler(self))
        if "schema_closed" not in self.model_fields_set:
            dumped.pop("schema_closed", None)
        return dumped


class CoreStructuredSource(BaseModel):
    """Attach a structured-source data file to an existing CORE entity kind.

    Unlike `EntityKind.structured_source` (which declares a project-LOCAL kind),
    this augments a core kind the project does not own: its rows are generated
    into a single-type YAML file under knowledge/sources/<profile>/ and load as
    owners of that core kind, WITHOUT registering/shadowing the core kind. Use
    for generated bulk core entities (e.g. `finding` rows emitted by an audit)
    that would otherwise have to ride the multi-type aggregate v3 retirement
    forbids. `structured_source` is the filename relative to the profile sources
    dir; `structured_source_root_key` is the YAML root key holding the row list
    (defaults to `kind`).
    """

    kind: str
    structured_source: str
    structured_source_root_key: str | None = None


class RelationEndpointPair(BaseModel):
    """One allowed source-kind / target-kind pair for a relation kind."""

    source_kind: str
    target_kind: str


class RelationKind(BaseModel):
    """A relation kind declared by a knowledge profile."""

    name: str
    predicate: str
    source_kinds: list[str]
    target_kinds: list[str]
    allowed_kind_pairs: list[RelationEndpointPair] = Field(default_factory=list)
    layer: str
    description: str = ""


class ProfileManifest(BaseModel):
    """A composable profile describing supported entity and relation kinds."""

    name: str
    imports: list[str]
    entity_kinds: list[EntityKind]
    relation_kinds: list[RelationKind]
    strictness: Literal["core", "curated", "typed-extension"]
    core_structured_sources: list[CoreStructuredSource] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _refuse_toolkit_reserved_fields(cls, data: Any) -> Any:
        """Refuse toolkit-ruled kind fields authored by an EXTERNAL manifest.

        Both external entry points (`load_profile_manifest` and the tool's
        `_validate_manifest_shape`) reach us through `model_validate` on a mapping parsed from
        YAML, so their entity_kinds entries arrive as `Mapping`. The packaged profiles construct
        `EntityKind` instances directly, so theirs do not -- which is exactly what lets one rule
        here serve both loaders without touching the 53 shipped declarations.
        """
        if not isinstance(data, Mapping):
            return data
        for entry in data.get("entity_kinds") or ():
            if not isinstance(entry, Mapping):
                continue  # a constructed EntityKind: packaged, not external
            reserved = _TOOLKIT_RESERVED_KIND_FIELDS & set(entry)
            if reserved:
                name = entry.get("name", "<unnamed>")
                msg = (
                    f"entity_kinds[{name!r}] may not author {sorted(reserved)}: these are ruled by "
                    "the toolkit. A project cannot install a packaged type mixin, so it cannot arm "
                    "schema closure for its own kinds."
                )
                raise ValueError(msg)
        return data

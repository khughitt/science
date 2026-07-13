"""Multi-project entity schema layer.

Composes a Frictionless-inspired base schema with type mixins (dataset,
paper, topic, theme) and optional domain extensions (e.g. bio.rnaseq).

See docs/plans/historical/2026-05-13-multiproject-schema-and-shared-store-design.md
section 3 for the design.
"""

from __future__ import annotations

from science_model.entity_schema.loader import (
    SchemaLoader,
    SchemaNotFoundError,
    filename_for,
)
from science_model.entity_schema.introspection import (
    FrontmatterField,
    read_effective_frontmatter_fields,
)
from science_model.entity_schema.merge import (
    MergePolicy,
    read_canonical_body_sections,
    read_merge_policy,
    read_overlay_merge_policy,
)
from science_model.entity_schema.profile import (
    BASE_NAME,
    TYPE_MIXIN_NAMES,
    ProfileComponent,
    ProfileParseError,
    ProfileString,
    default_profile_for_kind,
    parse_component,
    parse_profile,
)
from science_model.entity_schema.resolve import (
    ExtensionContractError,
    ExtensionRedefinesCoreField,
    resolve_profile,
)
from science_model.entity_schema.resolution import (
    LineageTargets,
    ResolutionViolation,
    check_resolution,
)
from science_model.entity_schema.validator import (
    EntityValidationError,
    EntityValidator,
)
from science_model.entity_schema.wrapper import SharedEntity

__all__ = [
    "BASE_NAME",
    "TYPE_MIXIN_NAMES",
    "EntityValidationError",
    "EntityValidator",
    "ExtensionContractError",
    "ExtensionRedefinesCoreField",
    "FrontmatterField",
    "LineageTargets",
    "MergePolicy",
    "ProfileComponent",
    "ProfileParseError",
    "ProfileString",
    "ResolutionViolation",
    "SchemaLoader",
    "SchemaNotFoundError",
    "SharedEntity",
    "check_resolution",
    "default_profile_for_kind",
    "filename_for",
    "parse_component",
    "parse_profile",
    "read_canonical_body_sections",
    "resolve_profile",
    "read_effective_frontmatter_fields",
    "read_merge_policy",
    "read_overlay_merge_policy",
]

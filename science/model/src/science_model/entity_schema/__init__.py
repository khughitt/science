"""Multi-project entity schema layer.

Composes a Frictionless-inspired base schema with type mixins (dataset,
paper, topic, theme) and optional domain extensions (e.g. bio.rnaseq).

See docs/plans/2026-05-13-multiproject-schema-and-shared-store-design.md
section 3 for the design.
"""

from __future__ import annotations

from science_model.entity_schema.merge import (
    MergePolicy,
    read_merge_policy,
    read_overlay_merge_policy,
)
from science_model.entity_schema.profile import (
    BASE_NAME,
    TYPE_MIXIN_NAMES,
    ProfileComponent,
    ProfileParseError,
    ProfileString,
    parse_profile,
)
from science_model.entity_schema.loader import (
    SchemaLoader,
    SchemaNotFoundError,
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
    "MergePolicy",
    "ProfileComponent",
    "ProfileParseError",
    "ProfileString",
    "SchemaLoader",
    "SchemaNotFoundError",
    "SharedEntity",
    "parse_profile",
    "read_merge_policy",
    "read_overlay_merge_policy",
]

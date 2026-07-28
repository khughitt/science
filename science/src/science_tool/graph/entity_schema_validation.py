"""The composed-schema checks, extracted from `sources.py` so the registry can call them.

They live here rather than in `sources.py` because `entity_registry.py` must call them and
`sources.py:64` already imports `EntityRegistry` -- importing back would close a cycle. This
module imports nothing from `sources.py` and nothing from `entity_registry.py`, which is what
keeps that true.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from science_model.entity_schema import PROJECT_MIXIN_NAMES, EntityValidationError

from science_tool.datasets.capability_shape import gen3_shape_issue

if TYPE_CHECKING:
    from science_tool.entity_profiles import ProjectSchema


def validate_against_schema(
    raw: dict[str, Any],
    *,
    kind: str,
    path: str,
    project_schema: ProjectSchema | None,
    injected: frozenset[str],
) -> None:
    """D3.1/D3.2 — the composed JSON Schema is checked BEFORE the projection is built.

    `project_schema` is None unless the project DECLARED `entity_schema_version: 2`, so an unmigrated
    project is untouched: it keeps today's behaviour, and its hypotheses keep the verdict in `status`.
    Nothing here infers the version from the files (see `ProjectConfig.entity_schema_version`).

    The profile is the project-COMPOSED one, never the package default: mm30's `identification` and
    evolution's `source_stated_evidence` are declared by project EXTENSIONS, so against the package
    default they are unknown keys and `unevaluatedProperties: false` would reject the files of the two
    projects that did nothing wrong.

    This is the half that makes `Entity`'s `extra="allow"` safe. The schema refuses what it does not
    know; the projection preserves what the schema admitted. Apart, each is a defect -- preservation
    without validation is just `extra="allow"` over an unvalidated corpus.

    `PROJECT_MIXIN_NAMES` is the migration slice list, and enforcement is gated on it rather than on a
    second frozenset of the same names. It also gates schema STRICTNESS in the validator, so a kind
    enforced here but absent there would be checked against a profile that admits anything: a green
    check over an unchecked record. Two hand-maintained copies of one list is how that happens.
    """
    if project_schema is None or kind not in PROJECT_MIXIN_NAMES:
        return
    authored = {key: value for key, value in raw.items() if key not in injected}
    try:
        project_schema.validator.validate_as(authored, project_schema.profile_for(kind))
    except EntityValidationError as exc:
        raise ValueError(
            f"{path}: {kind} frontmatter does not satisfy its schema "
            f"(project is pinned to entity_schema_version: {project_schema._generation})\n  {exc}"
        ) from exc


def validate_dataset_gen3(
    raw: dict[str, Any],
    *,
    kind: str,
    path: str,
    project_schema: ProjectSchema | None,
) -> None:
    """Task 6 -- a SEPARATE, generation-gated hook for `dataset`'s capability SHAPE.

    Dataset is a COMMONS kind and stays out of `PROJECT_MIXIN_NAMES`, so project datasets are loose
    records the load path never validates as full dataset/3.0 documents (they carry no
    `origin`/`tier`/`version`/`datapackage`). The ONLY gen-3 obligation on a project dataset is a
    well-formed `provided_capabilities` shape; validate exactly that via the canonical parser, not
    the full commons profile.
    """
    if project_schema is None or project_schema._generation != 3 or kind != "dataset":
        return
    if gen3_shape_issue(raw.get("provided_capabilities")) == "malformed":
        raise ValueError(
            f"{path}: dataset provided_capabilities is not a valid gen-3 "
            f"{{data_product, qualifiers}} shape (project is pinned to entity_schema_version: 3)"
        )

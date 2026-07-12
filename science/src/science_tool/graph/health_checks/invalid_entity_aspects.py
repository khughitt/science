"""Invalid-entity-aspects health check: entity files carrying invalid explicit `aspects:` values."""

from __future__ import annotations

from pathlib import Path
from typing import TypedDict

from science_tool.graph.health_checks.base import HealthCheck
from science_tool.instruments import InstrumentResult


class InvalidEntityAspectsFinding(TypedDict):
    entity_id: str
    source_file: str
    message: str


def collect_invalid_entity_aspects(project_root: Path) -> InstrumentResult[InvalidEntityAspectsFinding]:
    """Return the entity files carrying invalid explicit `aspects:` values.

    Two preconditions, both previously silent:

    - ``aspect_catalog_missing`` — ``load_project_aspects`` raises ``FileNotFoundError``
      when science.yaml is absent. The catalog this check validates AGAINST failed to
      load; it used to swallow that and answer "no invalid aspects".
    - ``entities_dir_missing`` — no ``entities/`` directory, so no entity was read.
    """
    from science_model.aspects import (
        AspectValidationError,
        load_project_aspects,
        validate_entity_aspects,
    )
    from science_model.frontmatter import parse_frontmatter

    try:
        project_aspects = load_project_aspects(project_root)
    except FileNotFoundError as exc:
        return InstrumentResult.unwired(
            code="aspect_catalog_missing",
            reason=f"the aspect catalog could not be loaded, so no aspect could be validated: {exc}",
        )

    entities_root = project_root / "entities"
    if not entities_root.is_dir():
        return InstrumentResult.unwired(
            code="entities_dir_missing",
            reason="entities/ does not exist; no entity aspects were read",
        )

    from science_tool.entity_scan import iter_entity_markdown

    findings: list[InvalidEntityAspectsFinding] = []
    for path in iter_entity_markdown(entities_root):
        result = parse_frontmatter(path)
        if result is None:
            continue
        fm, _ = result
        if "aspects" not in fm:
            continue
        raw = fm.get("aspects")
        if not isinstance(raw, list):
            findings.append(
                InvalidEntityAspectsFinding(
                    entity_id=str(fm.get("id", path.stem)),
                    source_file=str(path.relative_to(project_root)),
                    message="aspects must be a list",
                )
            )
            continue
        try:
            validate_entity_aspects([str(a) for a in raw], project_aspects)
        except AspectValidationError as exc:
            findings.append(
                InvalidEntityAspectsFinding(
                    entity_id=str(fm.get("id", path.stem)),
                    source_file=str(path.relative_to(project_root)),
                    message=str(exc),
                )
            )
    return InstrumentResult.from_rows(findings)


CHECK = HealthCheck(
    name="invalid_entity_aspects",
    description="Validate explicit entity aspects against the project aspect catalog.",
    requires_sources=False,
    run=lambda context: collect_invalid_entity_aspects(context.project_root),
    empty=lambda _root: [],
)

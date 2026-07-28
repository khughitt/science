"""Migration-nudge check for lens_views.

Structural invariants (lens vocabulary membership, origin_ref resolution, one
view per lens) are enforced at the model layer and surface as conformance
errors. This check is advisory: it WARNs when an entity's origins encode a lens
in their ref (``explore-ideas-<slug>``) but the entity carries no ``lens_views``,
so pre-lens_views explore-ideas entities are surfaced for backfill.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from science_model.lenses import LENS_SLUGS
from science_tool.validate.findings import validation_observation
from science_tool.validate.findings import declare_validation_rules
from science_tool.entity_scan import iter_entity_markdown
from science_tool.validate.checks import Check, CheckObservation
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Severity


SECTION, RULES = declare_validation_rules(
    section_id="lens-views",
    section_title="lens views",
    section_order=152,
    rule_ids=("lens-views.check",),
    severities=frozenset({"error", "warn", "info"}),
)


def _result(path: Path, lenses: list[str]) -> CheckObservation:
    return validation_observation(
        severity=Severity.WARN,
        path=path,
        line=None,
        message=f"{path.name}: origins encode lens(es) {lenses} but no lens_views; run 'science explore-ideas backfill-lens-views'",
        rule=RULES["lens-views.check"],
        task=None,
        qualifiers={"key": []},
    )


@Check(section=SECTION, order=0, producer_id="validate.lens-views", rules=tuple(RULES.values()))
def check_lens_view_backfill(ctx: ValidateContext) -> Iterator[CheckObservation]:
    entities_dir = ctx.project_root / "entities"
    if not entities_dir.is_dir():
        return

    for path in iter_entity_markdown(entities_dir):
        fm = ctx.frontmatter(path)
        if fm.get("lens_views"):
            continue
        origins = fm.get("origins")
        if not isinstance(origins, list):
            continue
        lenses = sorted(
            {
                o["ref"].removeprefix("explore-ideas-")
                for o in origins
                if isinstance(o, dict)
                and isinstance(o.get("ref"), str)
                and o["ref"].startswith("explore-ideas-")
                and o["ref"].removeprefix("explore-ideas-") in LENS_SLUGS
            }
        )
        if lenses:
            yield _result(path, lenses)

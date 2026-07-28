"""Conformance check: a local owner that shadows a commons canonical.

Distinct from `identity_collision`, which is a SAME-scope duplicate (two owners
for one `(owner_scope, canonical_id)` key). This is the CROSS-scope shadow: a
project entity under `entities/` locally OWNS an id that a commons canonical
already owns. The two are different owner_scopes, so the identity table does not
call it a collision — yet it is still a defect. A local owner claims the id first,
so the commons canonical is never contributed; identity arbitration can drop
edges, and a commons entity's reference to that id resolves to nothing and
surfaces as a misleading `unresolved_reference` ("no local entity, no commons
canonical") even though both exist.

The fix is to convert the local owner into an overlay (`overlay_of: <id>`,
carrying any project-specific content) or give it a distinct id.

ERROR: the corpus was reconciled to zero collisions before the severity
ratcheted from WARN, so any new occurrence is a fresh defect to reject at the
gate rather than a latent backlog to tolerate.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from science_tool.validate.findings import validation_observation
from science_tool.validate.findings import declare_validation_rules
from science_tool.commons.config import resolve_commons_root
from science_tool.commons.errors import CommonsEntityError, CommonsError
from science_tool.commons.query import CommonsQuery
from science_tool.commons.registry import REGISTRY_FILENAME
from science_tool.entity_scan import iter_entity_markdown
from science_tool.validate._helpers import entity_frontmatters
from science_tool.validate.checks import Check, CheckObservation
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Severity

RULE = "commons.owner-collision"


SECTION, RULES = declare_validation_rules(
    section_id="commons-owner-collision",
    section_title="commons owner collision",
    section_order=139,
    rule_ids=("commons.owner-collision",),
    severities=frozenset({"error", "warn", "info"}),
)


def _project_overlay_ids(ctx: ValidateContext) -> set[str]:
    """Canonical ids the project carries as overlays under ``overlays/``."""
    overlays_root = ctx.project_root / "overlays"
    if not overlays_root.is_dir():
        return set()
    ids: set[str] = set()
    for path in iter_entity_markdown(overlays_root):
        canonical_id = ctx.frontmatter(path).get("id")
        if isinstance(canonical_id, str) and ":" in canonical_id:
            ids.add(canonical_id)
    return ids


@Check(section=SECTION, order=1, producer_id="validate.commons-owner-collision", rules=tuple(RULES.values()))
def check_commons_owner_collision(ctx: ValidateContext) -> Iterator[CheckObservation]:
    commons_root = resolve_commons_root()
    # No commons store, or no built index: this project cannot collide with what
    # it cannot resolve. Skipping here is not a silent fail-open — the graph load
    # path is what warns on a stale/absent index (fb-2026-07-16-005).
    if not commons_root.is_dir() or not (commons_root / REGISTRY_FILENAME).is_file():
        return
    query = ctx.cached_resource(
        ("commons-owner-collision-query", commons_root),
        lambda: CommonsQuery(commons_root, warn_stale=False),
    )
    overlay_ids = _project_overlay_ids(ctx)

    for fm in entity_frontmatters(ctx):
        path = fm.get("_path")
        if not isinstance(path, str) or not path.startswith("entities/"):
            continue  # overlays (overlays/) are the correct form; skip them
        canonical_id = fm.get("id")
        if not isinstance(canonical_id, str) or ":" not in canonical_id:
            continue
        if canonical_id in overlay_ids:
            # The project ALSO holds an overlay for this id: that is the
            # overlay/local-duplicate class (`commons.overlay-local-duplicate`),
            # whose remedy is "delete the local copy", not this check's "convert
            # to an overlay" (one already exists). Defer so the two never conflict.
            continue
        try:
            record = query.show(canonical_id)
        except CommonsEntityError:
            continue  # commons does not own this id -> no collision
        except CommonsError:
            return  # registry unreadable -> cannot audit; do not emit phantom findings
        version = record.frontmatter.get("version")
        version_note = f" (v{version})" if isinstance(version, str) and version else ""
        yield validation_observation(
            severity=Severity.ERROR,
            path=Path(path),
            line=None,
            message=f"{canonical_id}: owned locally by {path} but a commons canonical of the same id already exists{version_note}. A local owner shadows the canonical: it is never contributed, so references to {canonical_id} from commons entities resolve to nothing. Convert this entity to an overlay (overlay_of: {canonical_id}) to keep any project-specific content, or give it a distinct id.",
            rule=RULES["commons.owner-collision"],
            task=None,
            qualifiers={"key": []},
        )

"""Conformance check: forbidden second owner declaration (design §B1/§B4/§C3).

The one identity error the compiler must reject is a COLLISION: two owner
declarations for the same canonical id in one address space — the key
(owner_scope, canonical_id). A strict load raises EntityIdentityCollisionError
before this point; this diagnostic loads NON-STRICT so the collision surfaces as
a standing `science validate` result instead of an opaque load crash. Rows are
collected pre-dedup in load_project_sources, so both colliding owner rows survive
a non-strict load even though the second Entity is skipped.

This is intended to be the SINGLE validate-surface for the collision diagnostic:
a follow-on change routes check_graph's identity_collision rows here (rather than
re-emitting them) so the two paths do not report the same condition with
different policies.

Graded policy:
- >=2 NON-deprecated owners -> ERROR: the genuine duplicate §B1 forbids.
- otherwise -> WARN: a deprecated transitional owner (an entities.yaml aggregate
  stub, §C3) shadows a real owner — rollout debt carried until §B5 retirement.
  Visible so the debt is not lost, but non-blocking (the migration must not be
  bricked before its content migrates, §C4).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from science_tool.graph.identity_table import (
    IdentityCollision,
    IdentityTable,
    build_identity_table,
)
from science_tool.graph.sources import load_project_sources
from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity


def graded_collisions(table: IdentityTable) -> list[tuple[Severity, IdentityCollision]]:
    """Each (owner_scope, canonical_id) collision paired with its severity.

    ERROR for a genuine §B1 duplicate (>=2 non-deprecated owners); WARN otherwise (a
    deprecated transitional owner shadows a real owner — §C3 rollout debt carried until
    §B5, visible but non-blocking). Grade via IdentityCollision.is_genuine so this check,
    the graph audit, and the migrator share one source of truth.
    """
    return [(Severity.ERROR if collision.is_genuine else Severity.WARN, collision) for collision in table.collisions()]


@Check(section="forbidden second owner declaration (identity collision)...", order=50)
def check_forbidden_second_declaration(ctx: ValidateContext) -> Iterator[Result]:
    # Non-strict + no commons, matching the orphan check: a diagnostic must not abort
    # on the collision it reports, and a commons owner + a local owner of the same id
    # are two DIFFERENT keys (different owner_scope), never a same-scope collision.
    sources = load_project_sources(
        ctx.project_root,
        include_commons=False,
        strict_core_schema=False,
        strict_identity=False,
    )
    table = build_identity_table(sources)
    for severity, collision in graded_collisions(table):
        paths = sorted(row.source_ref.path for row in collision.rows if row.source_ref)
        first = Path(paths[0]) if paths else None  # deterministic (sorted) tiebreak for the Result path
        joined = ", ".join(paths) if paths else "?"
        if severity is Severity.ERROR:
            detail = (
                "exactly one canonical owner per (owner_scope, canonical_id) is "
                "required (design §B1) — keep one owner declaration and remove the other."
            )
        else:
            detail = (
                "a deprecated transitional declaration shadows the owner (design "
                "§C3) — rollout debt carried until §B5 retirement; remove the stub "
                "to clear it."
            )
        yield Result(
            severity,
            first,
            None,
            f"{collision.canonical_id}: two owner declarations in scope '{collision.owner_scope}' ({joined}); {detail}",
            "forbidden-second-declaration",
            None,
        )

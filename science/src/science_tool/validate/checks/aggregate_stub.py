"""Conformance check: a lone aggregate (`entities.yaml`) stub (design §B5).

A deprecated aggregate owner row that is the SOLE owner of its id is fileless
rollout debt: it sole-sources an entity §B5 will retire to an owner file (or
delete). It is not a collision, so the forbidden-second-declaration check (which
fires only when a second owner shadows a real one) never surfaces it. This check
makes the lone-stub debt visible. WARN unconditionally: the retirement tool (3b
`--apply`) does not exist yet, so the debt must stay visible without blocking
(design §C4 -- a half-rolled project is never bricked). The richer per-bucket
inventory lives in `science entities triage-aggregate`; this check is only the
standing gate for the lone-stub subset.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from science_tool.graph.identity_table import build_identity_table
from science_tool.graph.sources import load_project_sources
from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity


@Check(section="lone aggregate stub (entities.yaml retirement, design §B5)", order=51)
def check_lone_aggregate_stub(ctx: ValidateContext) -> Iterator[Result]:
    # Non-strict, no commons, lenient core schema -- matching the identity-collision
    # check: a diagnostic must not abort on the condition it reports, and a malformed
    # row must not take the visibility tool offline.
    sources = load_project_sources(
        ctx.project_root,
        include_commons=False,
        strict_core_schema=False,
        strict_identity=False,
    )
    table = build_identity_table(sources)
    for (_scope, canonical_id), rows in sorted(table.owners().items()):
        if len(rows) != 1:
            continue  # >=2 owners is a collision -> forbidden-second-declaration's surface
        (row,) = rows
        if row.adapter != "aggregate" or not row.deprecated:
            continue
        path = Path(row.source_ref.path) if row.source_ref else None
        yield Result(
            Severity.WARN,
            path,
            None,
            f"{canonical_id}: lone aggregate stub (entities.yaml) sole-sources this "
            "entity (design §B5) -- retire it to an owner file or delete it via "
            "`science entities triage-aggregate` + Phase 3b --apply; carried as WARN "
            "until then.",
            "lone-aggregate-stub",
            None,
        )

# src/science_tool/validate/checks/aggregate_retired.py
"""Conformance check: aggregate manifests must be retired at layout_version >= 3
(design §B5/§C3, Phase 4c).

`check_lone_aggregate_stub` (order=51) WARNs on lone fileless stubs for visibility
while a project is mid-rollout. This check is the executable END-STATE assertion:
once a project declares layout_version >= 3 it claims the v2->v3 migration is done,
so ANY remaining multi-type aggregate (entities.yaml/terms.yaml) owner row is an
ERROR. Below v3 it is silent (the lone-stub WARN already provides visibility). This
keeps the AggregateAdapter deprecated-owner mode loadable for v2 projects while
asserting that no aggregate rows survive into v3 -- the precondition for eventually
deleting that adapter mode.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import yaml

from science_tool.graph.identity_table import build_identity_table
from science_tool.graph.storage_adapters.aggregate import MULTI_TYPE_AGGREGATE_ROOT_KEYS
from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity


def _layout_version(project_root: Path) -> int | None:
    manifest = yaml.safe_load((project_root / "science.yaml").read_text(encoding="utf-8")) or {}
    v = manifest.get("layout_version")
    return v if isinstance(v, int) else None


@Check(section="aggregate retirement end-state (design §B5/§C3)", order=52)
def check_aggregate_retired_at_v3(ctx: ValidateContext) -> Iterator[Result]:
    version = _layout_version(ctx.project_root)
    if version is None or version < 3:
        return  # below v3 the lone-stub WARN covers visibility; this gate is silent
    sources = ctx.project_sources(
        include_commons=False,
        strict_core_schema=False,
        strict_identity=False,
    )
    table = build_identity_table(sources)
    for (_scope, canonical_id), rows in sorted(table.owners().items()):
        for row in rows:
            if not (row.adapter == "aggregate" and row.deprecated):
                continue
            path = Path(row.source_ref.path) if row.source_ref else None
            # Scope to MULTI-TYPE aggregates (entities.yaml/terms.yaml) only. The
            # AggregateAdapter ALSO discovers single-type aggregates
            # (doc/<plural>/<plural>.{json,yaml}) and marks them deprecated, but 4c's
            # retirement actions target only the multi-type files; flagging single-type
            # rows here would assert an end-state 4c does not provide a path to reach.
            if path is None or path.name not in MULTI_TYPE_AGGREGATE_ROOT_KEYS:
                continue
            yield Result(
                Severity.ERROR,
                path,
                None,
                f"{canonical_id}: aggregate (entities.yaml/terms.yaml) row survives at "
                f"layout_version {version} -- retire it via `science entities triage-aggregate` "
                "(promote/migrate/delete) before the v2->v3 migration is considered complete.",
                "aggregate-not-retired-at-v3",
                None,
            )

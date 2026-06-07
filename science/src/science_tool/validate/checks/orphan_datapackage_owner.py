"""Conformance check: synthesized/orphan datapackage owners (design §B4).

A datapackage is attached resource metadata, not an identity declaration. After
the loader's orphan-aware synthesis (§B4), a datapackage that has a real owner of
the same id DEFERS to it and emits no owner declaration — so any datapackage
owner declaration that remains in the compiled model is an ORPHAN (a
datapackage-only dataset with no entity-file owner). Surface each one for
migration to a real entities/datasets/<id>.md owner. WARN during the v2->v3
transition; ERROR at layout_version >= 3 (the deliberate synthesize+warn -> error
cutover is Phase 2).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from science_tool.graph.sources import load_project_sources
from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity


def _severity(ctx: ValidateContext) -> Severity:
    # Mirrors validate/checks/entity_conformance._severity (module-private there).
    version = ctx.manifest.get("layout_version")
    return Severity.ERROR if isinstance(version, int) and version >= 3 else Severity.WARN


@Check(section="orphan datapackage owner (no entity-file owner)...", order=49)
def check_orphan_datapackage_owner(ctx: ValidateContext) -> Iterator[Result]:
    # Non-strict + no commons: a diagnostic must not abort on unrelated strictness
    # failures, and commons owners are a different scope (never this-project orphans).
    sources = load_project_sources(
        ctx.project_root,
        include_commons=False,
        strict_core_schema=False,
        strict_identity=False,
    )
    for decl in sources.identity_declarations:
        if decl.adapter != "datapackage":
            continue
        path = Path(decl.source_ref.path) if decl.source_ref else None
        yield Result(
            _severity(ctx),
            path,
            None,
            f"{decl.canonical_id}: datapackage has no entity-file owner "
            "(orphan datapackage; synthesized transitional owner — migrate to "
            "entities/datasets/<id>.md per design §B4)",
            "orphan-datapackage-owner",
            None,
        )

"""Conformance check: orphan datapackage owners (design §B4).

A datapackage is attached resource metadata, not an identity declaration. After
the loader's orphan-aware synthesis (§B4), a datapackage that has a real owner of
the same id DEFERS to it and emits no owner declaration — so any datapackage
owner declaration that remains in the compiled model is an ORPHAN (a
datapackage-only dataset with no entity-file owner).

Phase 2b cutover: promotion tooling now exists (`science data-package
promote-orphans --apply`, design §B4), so an orphan is always actionable and is
an ERROR regardless of layout_version. The loader still SYNTHESIZES a transitional
owner so the project keeps loading and the promoter can read the orphan; only this
conformance severity flips warn -> error.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from science_tool.graph.sources import load_project_sources
from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity


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
            Severity.ERROR,
            path,
            None,
            f"{decl.canonical_id}: datapackage has no entity-file owner "
            "(orphan datapackage); run `science data-package promote-orphans "
            "--apply` to create an entities/datasets/<id>.md owner (design §B4)",
            "orphan-datapackage-owner",
            None,
        )

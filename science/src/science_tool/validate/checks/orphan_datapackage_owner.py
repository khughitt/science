"""Conformance check: orphan datapackage owners.

A datapackage is attached resource metadata, not an identity declaration. A datapackage is an
ORPHAN when NOTHING ELSE owns its id — that is the question this check asks, directly, of the
declarations.

It used to ask a different question and trust the answer to coincide. The loader deferred a
datapackage that had a real owner, deleting its declaration, so "a datapackage declaration
survived" happened to mean "orphan" — and this check merely tested `adapter == "datapackage"`.
The predicate lived in the loader, not here. Once collection became exhaustive and every
datapackage declared, the same code flagged datasets that plainly had a markdown owner sitting
next to them. A check that borrows its meaning from another layer's deletions is only ever
accidentally right.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from science_tool.graph.identity_table import ParticipationMode
from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity


@Check(section="orphan datapackage owner (no entity-file owner)...", order=49)
def check_orphan_datapackage_owner(ctx: ValidateContext) -> Iterator[Result]:
    # Non-strict + no commons: a diagnostic must not abort on unrelated strictness
    # failures, and commons owners are a different scope (never this-project orphans).
    sources = ctx.project_sources(
        include_commons=False,
        strict_core_schema=False,
        strict_identity=False,
    )
    # The ids some NON-datapackage owner declares. A datapackage whose id appears here has an
    # entity-file owner and is not an orphan, whatever the loader did with its declaration.
    owned_elsewhere = {
        decl.canonical_id
        for decl in sources.identity_declarations
        if decl.participation_mode is ParticipationMode.OWNER and decl.adapter != "datapackage"
    }
    for decl in sources.identity_declarations:
        if decl.adapter != "datapackage" or decl.canonical_id in owned_elsewhere:
            continue
        path = Path(decl.source_ref.path) if decl.source_ref else None
        yield Result(
            Severity.ERROR,
            path,
            None,
            f"{decl.canonical_id}: datapackage has no entity-file owner "
            "(orphan datapackage); create an entities/datasets/<id>.md owner "
            "with a datapackage pointer",
            "orphan-datapackage-owner",
            None,
        )

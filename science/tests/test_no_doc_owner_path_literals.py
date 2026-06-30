"""Phase 3 audit gate: no source-tree literal points dataset/workflow owner or
overlay readers back at the prose-only doc/<type>/ tree.

After the 2026-06-21 adapter-entity-layout migration, dataset/workflow/workflow-run
OWNERS live under entities/<kind>/ and commons OVERLAYS under overlays/<type>/. A
stray ``doc/datasets`` / ``doc/workflows`` / ``doc/workflow-runs`` literal in a
reader is silently load-bearing — it strands all migrated coverage with no error
(this is exactly how validate/_helpers.py and graph/health.py were nearly missed).
This frozen guard is the backstop: it greps the source tree and fails on any such
literal outside the one legitimate exception.

Scope note: this gate covers the THREE kinds this slice moved. The federated
``doc/papers`` / ``doc/topics`` / ``doc/themes`` owner-discovery readers carry
pre-existing v2/v3 dual-layout support from the earlier paper/topic migration and
are out of this slice; they are not policed here.

See docs/audits/plans-cleanup/2026-06-03-entity-layout-v3-checkpoint.md and
docs/user-guide/project-layout.md.
"""

from __future__ import annotations

import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "science_tool"

# Both the string form (``doc/datasets``) and the pathlib-join form
# (``"doc" / "datasets"``) for each in-scope owner kind.
_FORBIDDEN = re.compile(
    r"""doc/(?:datasets|workflows|workflow-runs)"""
    r"""|["']doc["']\s*/\s*["'](?:datasets|workflows|workflow-runs)["']"""
)

# The ONLY legitimate reader of doc/<type>/ for these kinds: the one-time layout
# migrator, whose entire job is to read the legacy doc/ tree as MIGRATION INPUT and
# relocate it into entities/ + overlays/.
_ALLOWLIST: set[str] = {
    "entity_layout_migration.py",
}


def test_no_doc_owner_path_literals_in_source() -> None:
    offenders: dict[str, list[int]] = {}
    for py in sorted(SRC.rglob("*.py")):
        if py.name in _ALLOWLIST:
            continue
        for lineno, line in enumerate(py.read_text(encoding="utf-8").splitlines(), start=1):
            if _FORBIDDEN.search(line):
                offenders.setdefault(py.relative_to(SRC).as_posix(), []).append(lineno)
    assert not offenders, (
        "Found doc/<type>/ literal(s) for an in-scope owner kind (dataset/workflow/"
        "workflow-run). Owners now live under entities/<kind>/ — flip the literal "
        "to entities/, or (if it is a legitimate legacy-input reader) add the file "
        "to _ALLOWLIST with a reason:\n" + "\n".join(f"  {f}: lines {nums}" for f, nums in sorted(offenders.items()))
    )

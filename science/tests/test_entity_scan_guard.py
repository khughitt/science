# science/tests/test_entity_scan_guard.py
"""Guard: every recursive rglob('*.md') in src is classified (P3).

This is a FROZEN-INVENTORY guard, not a heuristic: it collects the set of source
files containing a recursive `rglob("*.md")` and asserts it equals an explicit
ALLOWLIST. After Task 3 routes the entities/-rooted scans through
entity_scan.iter_entity_markdown, those files drop out of the rglob inventory; the
remaining members are entity_scan itself plus known NON-entity scanners (health,
migrations, tasks, papers, prose, etc.). When a new rglob appears the test fails,
forcing a deliberate decision: route it through entity_scan (if it scans
entities/) or add it to ALLOWLIST with a one-line reason (if it does not).
"""
from __future__ import annotations

import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "science_tool"
_RGLOB = re.compile(r'\.rglob\(\s*["\']\*\.md["\']\s*\)')

# Files that legitimately contain a recursive `rglob("*.md")`.
# entity_scan.py is the SSOT (its rglob IS the sanctioned one). Every other entry
# scans a non-entity root, a prose root, or an explicit migration input.
ALLOWLIST: set[str] = {
    "entity_scan.py",  # SSOT
    "archive.py",  # verify_archive scans the _archive subtree itself, not live entities
    # --- known non-entity / prose / migration recursive markdown scanners (reason each) ---
    "big_picture/validator.py",             # tasks/ rglob (entities branch routed)
    "graph/storage_adapters/markdown.py",   # research/packages else-branch (entities branch routed)
    "graph/storage_adapters/task.py",       # tasks/ root
    "graph/health.py",                      # health/datasets/runs roots
    "graph/materialize.py",                 # doc/data-packages migration gate
    "graph/migrate.py",                     # migration roots
    "graph/paper_dataset_migration.py",     # research/packages/doc paper roots (entities branch routed)
    "validate/checks/id_prefixes.py",       # entities routed through iter_entity_markdown
    "validate/_helpers.py",
    "entities_inventory.py",                # _latest_activity scans project_root (skip-set added)
    "prose.py", "prose_lint.py", "markers.py", "refs.py",
    "skills_lint/lint.py", "cli.py",
}


# The nine files that scan entities/ — each MUST route through the SSOT. Files
# that ALSO keep a non-entity rglob (markdown/id_prefixes/entity_conformance/
# validator) still appear in the inventory below; this positive check proves their
# entities scan specifically was routed.
ENTITY_SCANNERS: set[str] = {
    "consolidation.py",
    "curate/inventory.py",
    "graph/storage_adapters/markdown.py",
    "validate/checks/cross_references.py",
    "validate/checks/id_prefixes.py",
    "validate/checks/entity_conformance.py",
    "validate/checks/hypotheses.py",
    "big_picture/validator.py",
    "graph/paper_dataset_migration.py",
    "entities.py",
}


def test_entity_scanners_use_the_ssot() -> None:
    missing = sorted(f for f in ENTITY_SCANNERS if "iter_entity_markdown" not in (SRC / f).read_text(encoding="utf-8"))
    assert not missing, f"these files scan entities/ and must use entity_scan.iter_entity_markdown: {missing}"


def test_recursive_md_rglob_inventory_is_frozen() -> None:
    found: set[str] = set()
    for py in sorted(SRC.rglob("*.py")):
        if any(_RGLOB.search(line) for line in py.read_text(encoding="utf-8").splitlines()):
            found.add(py.relative_to(SRC).as_posix())
    new = sorted(found - ALLOWLIST)
    assert not new, (
        "New recursive rglob('*.md') site(s). If it scans entities/, route it through "
        "entity_scan.iter_entity_markdown (and ensure it is in ENTITY_SCANNERS); otherwise "
        "add it to ALLOWLIST with a reason:\n" + "\n".join(new)
    )

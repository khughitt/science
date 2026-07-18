"""Sweep configured projects, report numeric-anchor counts (acceptance check).

Usage: uv run python scripts/numeric_provenance_before_after.py PROJECT_ROOT [PROJECT_ROOT ...]

Prints per-project numeric-anchor finding counts under the new engine, so the
reduction can be confirmed and survivors spot-checked (e.g. pan-disease ~587
under the old paragraph-substring check → 218 under the new engine; the residual
is dominated by genuinely-ungrounded computed statistics plus not-yet-migrated
project config, not by old false positives). Kept as a reproducible acceptance harness, not a
throwaway probe — re-run it whenever the numeric-provenance engine or a swept
project's vocabulary changes.
"""

from __future__ import annotations

import sys
from pathlib import Path

from science_tool.prose_lint import scan_root


def main(roots: list[str]) -> None:
    for r in roots:
        root = Path(r).resolve()
        result = scan_root(root, checks=["numeric-anchor"])
        n = result["counts"].get("numeric-anchor", 0)
        print(f"{root.name:40s} numeric-anchor={n}")
        for hit in result["hits"][:20]:
            print(f"    {hit.file}:{hit.line} {hit.match}  {hit.message}")


if __name__ == "__main__":
    main(sys.argv[1:] or ["."])

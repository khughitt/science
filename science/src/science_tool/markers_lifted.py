"""Drop marker hits that a `.anno.trig` sidecar records as already adjudicated.

The sidecar is the record of a deliberate ruling made by `science annotate
lift-tokens`, so every surface that counts markers has to honour it or the counts
disagree. They did: `validate`'s `unresolved_markers` check filtered lifted hits
while `science refs check` scanned the same tokens and did not, so one tree
reported 53 on one surface and 65 on the other (fb-2026-07-26-012). Two surfaces
disagreeing about whether an adjudication happened makes both counts
untrustworthy, so this lives in one module that all of them import.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from science_tool.markers import MarkerHit


def _line_bounds(source_text: str, line: int) -> tuple[int, int] | None:
    line_offsets = [0]
    for i, ch in enumerate(source_text):
        if ch == "\n":
            line_offsets.append(i + 1)
    if line < 1 or line > len(line_offsets):
        return None
    start = line_offsets[line - 1]
    end = line_offsets[line] if line < len(line_offsets) else len(source_text)
    return start, end


def hit_is_lifted(hit: MarkerHit, sidecar: Any) -> bool:
    """True if any sidecar annotation matches this hit by source + token + line."""
    from science_tool.annotation.selector import (  # noqa: PLC0415
        ResolutionStatus,
        resolve_selector,
    )

    # `hit.literal` is the exact matched text, not a reconstruction: a marker
    # carrying a `: reason` payload has a literal the old `f"[{token}]"` form
    # could never produce, and the mismatch silently failed to match its lift.
    literal = hit.literal
    try:
        source_text = hit.file.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False

    bounds = _line_bounds(source_text, hit.line)
    if bounds is None:
        return False
    line_start, line_end = bounds

    for ann in sidecar.annotations:
        if ann.source != "marker-scanner:phase-2":
            continue
        if ann.lifted_from != literal:
            continue
        result = resolve_selector(source_text, ann.target.selector)
        if result.status == ResolutionStatus.SUPERSEDED:
            continue
        if result.start is None or result.end is None:
            continue
        # Containment: any character of the resolved range lies on hit.line.
        if result.start < line_end and result.end > line_start:
            return True
    return False


def filter_lifted(hits: list[MarkerHit]) -> list[MarkerHit]:
    """Drop hits whose enclosing sentence has a sidecar row marker-lifted."""
    from science_tool.annotation.io import read_sidecar  # noqa: PLC0415

    sidecar_cache: dict[Path, Any] = {}

    def load(path: Path) -> Any:
        if path in sidecar_cache:
            return sidecar_cache[path]
        try:
            sidecar = read_sidecar(path) if path.exists() else None
        except Exception as exc:  # noqa: BLE001 -- an unreadable sidecar must not
            # blind the scan: warn and treat every hit in that file as unlifted.
            print(f"warning: could not parse {path}: {exc}", file=sys.stderr)
            sidecar = None
        sidecar_cache[path] = sidecar
        return sidecar

    out: list[MarkerHit] = []
    for hit in hits:
        sidecar = load(hit.file.with_suffix(".anno.trig"))
        if sidecar is None or not hit_is_lifted(hit, sidecar):
            out.append(hit)
    return out

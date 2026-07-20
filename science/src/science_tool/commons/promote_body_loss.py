"""What `keep existing` would destroy, counted before it destroys it.

fb-2026-07-16-004 (addendum). On an ExistingCanonicalConflict the promote
pipeline offers `[k] keep existing (overlay)`. That path writes no canonical
artifacts (`overlay_existing`, promote.py) and renders only `project_only_body`
into the overlay (`promote_render._render_overlay`), so every canonical body
section the source carried is dropped: no diff, no warning, no count.

Measured across three real cbioportal papers, keep-existing would have
destroyed 347 lines. The loss runs backwards from quality — those commons
canonicals were themselves promoted from a thinner project's copies, so the
worse document wins and the operator following the tool's own sanctioned
remediation destroys the better one.

This module only measures. It decides nothing: the caller presents the count
and the operator chooses.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Mapping

# `dropped`    — commons has no such section; the content has no counterpart at all.
# `downgraded` — commons has a shorter one; the richer text loses to the thinner.
# `replaced`   — commons has a different one, not shorter. Still a loss of the source text.
Disposition = Literal["dropped", "downgraded", "replaced"]


@dataclass(frozen=True)
class BodyLossEntry:
    section: str
    source_lines: int
    existing_lines: int
    disposition: Disposition


@dataclass(frozen=True)
class CanonicalBodyLoss:
    """The canonical body content keep-existing would discard."""

    entries: list[BodyLossEntry]

    @property
    def has_loss(self) -> bool:
        return bool(self.entries)

    @property
    def lines_dropped(self) -> int:
        """Source lines that would be discarded."""
        return sum(entry.source_lines for entry in self.entries)

    @property
    def lines_kept(self) -> int:
        """Commons lines that would survive in their place."""
        return sum(entry.existing_lines for entry in self.entries)


def _line_count(text: str) -> int:
    return len([line for line in text.strip().splitlines() if line.strip()])


def canonical_body_loss(
    source_body: Mapping[str, str],
    existing_body: Mapping[str, str],
) -> CanonicalBodyLoss:
    """Count what the source contributes that keep-existing would not preserve.

    Only source-present sections can be lost. A section that exists solely in
    commons is preserved by keep-existing and is therefore not at risk, and a
    blank source section had nothing to contribute in the first place.
    """
    entries: list[BodyLossEntry] = []
    for section, source_text in source_body.items():
        source_lines = _line_count(source_text or "")
        if source_lines == 0:
            continue
        existing_text = existing_body.get(section) or ""
        if (source_text or "").strip() == existing_text.strip():
            continue

        existing_lines = _line_count(existing_text)
        if existing_lines == 0:
            disposition: Disposition = "dropped"
        elif source_lines > existing_lines:
            disposition = "downgraded"
        else:
            disposition = "replaced"
        entries.append(
            BodyLossEntry(
                section=section,
                source_lines=source_lines,
                existing_lines=existing_lines,
                disposition=disposition,
            )
        )

    # Worst loss first, so a truncated display still shows the most damage.
    entries.sort(key=lambda entry: (-(entry.source_lines - entry.existing_lines), entry.section))
    return CanonicalBodyLoss(entries=entries)


def format_body_loss(loss: CanonicalBodyLoss, *, kind: str, slug: str) -> list[str]:
    """Render the loss as display lines. Presentation-only; no click dependency."""
    if not loss.has_loss:
        return []
    detail = {
        "dropped": "absent from commons — PURE LOSS",
        "downgraded": "commons text is shorter",
        "replaced": "commons text differs",
    }
    lines = [
        f"! keep-existing would DISCARD canonical content from the source for {kind}:{slug}:"
    ]
    width = max(len(entry.section) for entry in loss.entries)
    for entry in loss.entries:
        existing = "absent" if entry.existing_lines == 0 else f"{entry.existing_lines}"
        lines.append(
            f"    {entry.section.ljust(width)}  {entry.source_lines:>4} lines -> {existing:>6}"
            f"   ({detail[entry.disposition]})"
        )
    lines.append(
        f"  total: {loss.lines_dropped} source lines discarded, "
        f"{loss.lines_kept} commons lines kept in their place"
    )
    return lines

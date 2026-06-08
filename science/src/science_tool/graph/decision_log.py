"""Phase 3c: parse + render the decision log.

`core/decisions.md` is a hand-authored, append-only log today. 3c makes it a
*generated view* over `entities/decision/*.md` owner files: each decision's
identity and full prose live in an owner file; this module is the only place
that knows how to (a) parse the legacy log into per-decision sections and
(b) render owner files back into the log. The 3b retirement executor delegates
all decision-prose work here via an injected `DecisionLogIndex`.

The section delimiter is the `## ` heading ONLY. A lone `---` is view
formatting, never a hard boundary — so an intentional horizontal rule inside a
decision body survives. The section body is opaque verbatim markdown; only the
trailing separator is stripped.
"""

from __future__ import annotations

from dataclasses import dataclass

# Where the generated log lives, and where promoted owners declare they came from.
DECISIONS_REL = "core/decisions.md"

_GENERATED_BANNER = (
    "<!-- GENERATED — do not edit. Source: entities/decision/*.md. Regenerate: science entities generate-decisions -->"
)


@dataclass(frozen=True, slots=True)
class DecisionSection:
    canonical_id: str
    local_id: str
    title: str
    date: str | None
    status: str | None
    body: str  # opaque verbatim markdown (trailing separator stripped)


@dataclass(frozen=True, slots=True)
class DecisionLogIndex:
    sections: dict[str, DecisionSection]

    def get(self, canonical_id: str) -> DecisionSection | None:
        return self.sections.get(canonical_id)


def _label_value(line: str, label: str) -> str | None:
    """Return the value after a `**Label**:` / `- **Label:**` style line, else None.

    Both forms normalize identically once `**` and a leading `- ` are removed:
    `- **Date:** 2026-03-31` and `**Date**: 2026-03-31` -> `Date: 2026-03-31`.
    """
    norm = line.strip().replace("**", "").lstrip("- ").strip()
    prefix = f"{label.lower()}:"
    if norm.lower().startswith(prefix):
        return norm[len(prefix) :].strip() or None
    return None


def _split_heading(heading_text: str) -> tuple[str, str]:
    """`D1. Title` -> (`D1`, `Title`); `D-001: Title` -> (`D-001`, `Title`)."""
    token = ""
    for ch in heading_text:
        if ch in ". :\t":
            break
        token += ch
    title = heading_text[len(token) :].lstrip(". :\t").strip()
    return token, title


def _normalized_status(raw: str | None) -> str | None:
    if raw is None:
        return None
    value = raw.strip()
    if value.lower().startswith("superseded by "):
        return "superseded"
    return value


def parse_decision_log(text: str) -> DecisionLogIndex:
    lines = text.splitlines()
    sections: dict[str, DecisionSection] = {}
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        if line.startswith("## "):
            heading_text = line[3:].strip()
            local_id, title = _split_heading(heading_text)
            # Capture body until the next `## ` heading or EOF.
            j = i + 1
            body_lines: list[str] = []
            while j < n and not lines[j].startswith("## "):
                body_lines.append(lines[j])
                j += 1
            # Strip a single trailing view separator (--- plus surrounding blanks).
            while body_lines and body_lines[-1].strip() == "":
                body_lines.pop()
            if body_lines and body_lines[-1].strip() == "---":
                body_lines.pop()
            while body_lines and body_lines[-1].strip() == "":
                body_lines.pop()
            date = None
            status = None
            for bl in body_lines:
                if date is None:
                    date = _label_value(bl, "Date")
                if status is None:
                    status = _normalized_status(_label_value(bl, "Status"))
            canonical_id = f"decision:{local_id}"
            sections[canonical_id] = DecisionSection(
                canonical_id=canonical_id,
                local_id=local_id,
                title=title,
                date=date,
                status=status,
                body="\n".join(body_lines).strip("\n"),
            )
            i = j
            continue
        i += 1
    return DecisionLogIndex(sections)

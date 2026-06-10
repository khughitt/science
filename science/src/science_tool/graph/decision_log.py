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
from pathlib import Path

import yaml

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


@dataclass(frozen=True, slots=True)
class DecisionOwner:
    local_id: str
    title: str
    date: str | None
    status: str | None
    body: str


def render_owner_file(section: DecisionSection, *, promoted_from: str, today: str) -> str:
    """Render one promoted decision owner: conformant frontmatter + opaque body.

    `status`/`created`/`updated` are always emitted so the owner satisfies
    entity_conformance._REQUIRED_FRONTMATTER. The log's parsed `Status:`/`Date:`
    are authoritative when present; otherwise fall back to the decision default
    status ("active", per entities._DEFAULT_STATUS) and the run date `today`.
    The informational `date` field is preserved when the log carried one.
    """
    created = section.date or today
    fm: dict[str, object] = {
        "id": section.canonical_id,
        "type": "decision",
        "title": section.title,
        "status": section.status or "active",
        "created": created,
        "updated": created,
    }
    if section.date is not None:
        fm["date"] = section.date
    fm["source_path"] = DECISIONS_REL
    fm["promoted_from"] = promoted_from
    front = yaml.safe_dump(fm, sort_keys=False, allow_unicode=True)
    return f"---\n{front}---\n\n{section.body.rstrip()}\n"


def _front_matter_and_body(text: str) -> tuple[dict, str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---", 4)
    if end == -1:
        return {}, text
    fm = yaml.safe_load(text[4:end]) or {}
    body = text[end + 4 :].lstrip("\n")
    return fm, body


def read_decision_owners(decision_dir: Path) -> list[DecisionOwner]:
    owners: list[DecisionOwner] = []
    if not decision_dir.is_dir():
        return owners
    for path in sorted(decision_dir.glob("*.md")):
        fm, body = _front_matter_and_body(path.read_text(encoding="utf-8"))
        canonical_id = str(fm.get("id", ""))
        local_id = canonical_id.split(":", 1)[1] if ":" in canonical_id else path.stem
        date = fm.get("date")
        status = fm.get("status")
        owners.append(
            DecisionOwner(
                local_id=local_id,
                title=str(fm.get("title", "")),
                date=str(date) if date is not None else None,
                status=str(status) if status is not None else None,
                body=body.rstrip("\n"),
            )
        )
    return owners


def _natural_key(local_id: str) -> tuple[str, int, str]:
    """Natural sort: D1 < D2 < D10. Split into (alpha-prefix, first-int, suffix)."""
    i = 0
    while i < len(local_id) and not local_id[i].isdigit():
        i += 1
    prefix = local_id[:i]
    j = i
    while j < len(local_id) and local_id[j].isdigit():
        j += 1
    number = int(local_id[i:j]) if j > i else -1
    return (prefix, number, local_id[j:])


def render_decisions_view(owners: list[DecisionOwner]) -> str:
    ordered = sorted(owners, key=lambda o: _natural_key(o.local_id))
    parts: list[str] = [_GENERATED_BANNER, "", "# Decisions", ""]
    for o in ordered:
        parts.append(f"## {o.local_id}. {o.title}")
        parts.append("")
        if o.body:
            parts.append(o.body.rstrip())
            parts.append("")
        parts.append("---")
        parts.append("")
    return "\n".join(parts).rstrip() + "\n"

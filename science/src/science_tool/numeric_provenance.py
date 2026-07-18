"""Numeric-claim provenance assessment (Part A of the numeric-provenance redesign).

Pure core: `assess_numeric_claims(document, index, config)` classifies each numeric
claim in a document's body prose as exactly one of NotClaim / Exempt / Anchored /
Unanchored. The scanning layer builds the `DocumentContext` and `ResolutionIndex`
and passes them in, keeping this module free of disk I/O.

See docs/plans/2026-07-18-numeric-provenance-check-design.md (Part A).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from science_tool.markdown_utils import frontmatter_span, is_fence_line

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
_TITLE_RE = re.compile(r"^#\s+(.+?)\s*$")


@dataclass(frozen=True)
class NumericClaim:
    value: str
    line: int
    col: int
    paragraph_id: int
    section_id: int


@dataclass(frozen=True)
class SourceCandidate:
    reference: str
    origin: str          # "frontmatter" | "title" | "body"
    field_or_line: str
    resolution_status: str  # "resolved" | "unresolved"


@dataclass(frozen=True)
class NotClaim:
    claim: NumericClaim
    reason: str


@dataclass(frozen=True)
class Exempt:
    claim: NumericClaim
    reason: str
    scope: str           # "document" | "section" | "block"


@dataclass(frozen=True)
class Anchored:
    claim: NumericClaim
    candidates: tuple[SourceCandidate, ...]


@dataclass(frozen=True)
class Unanchored:
    claim: NumericClaim
    kind_hint: str | None
    local_evidence: bool


ClaimAssessment = NotClaim | Exempt | Anchored | Unanchored


@dataclass(frozen=True)
class NumericProvenanceConfig:
    anchor_patterns: tuple[str, ...]
    spec_class_kinds: frozenset[str]
    provenance_fields: tuple[str, ...]


@dataclass(frozen=True)
class Section:
    section_id: int
    heading_level: int          # 0 for the pre-first-heading preamble
    start_line: int             # 1-based, inclusive
    end_line: int               # 1-based, inclusive


@dataclass(frozen=True)
class DocumentContext:
    path: Path
    kind: str | None
    frontmatter: dict
    title: str | None
    body_start: int
    lines: tuple[str, ...]              # full file lines, 1-based via lines[i-1]
    paragraph_id_per_line: tuple[int, ...]   # index by line number; [0] unused
    paragraph_text: dict[int, str]
    sections: tuple[Section, ...]
    section_id_per_line: tuple[int, ...]


def build_document_context(path: Path) -> DocumentContext | None:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    frontmatter, body_start = frontmatter_span(path)
    kind = frontmatter.get("kind") if isinstance(frontmatter, dict) else None
    lines = text.splitlines()
    n = len(lines)

    # Paragraphs: blank-line separated, mirroring detect_numeric_anchor's counter.
    paragraph_id_per_line = [0] * (n + 1)
    para_id = 0
    for idx, line in enumerate(lines, start=1):
        if not line.strip():
            para_id += 1
        paragraph_id_per_line[idx] = para_id
    paragraph_text: dict[int, str] = {}
    for idx, line in enumerate(lines, start=1):
        pid = paragraph_id_per_line[idx]
        paragraph_text[pid] = paragraph_text.get(pid, "") + line + "\n"

    # Sections: fail-closed at the next equal-or-higher heading. Fences are skipped
    # so a `#` inside a code block is not read as a heading.
    section_id_per_line = [0] * (n + 1)
    built_sections: list[Section] = []
    stack: list[tuple[int, int]] = []  # (heading_level, section_id)
    next_id = 1
    in_fence = False
    title: str | None = None
    for idx, raw in enumerate(lines, start=1):
        if is_fence_line(raw):
            in_fence = not in_fence
        heading = None if in_fence else _HEADING_RE.match(raw)
        if heading is not None:
            level = len(heading.group(1))
            if title is None:
                t = _TITLE_RE.match(raw)
                if t is not None:
                    title = t.group(1).strip()
            while stack and stack[-1][0] >= level:
                stack.pop()
            sid = next_id
            next_id += 1
            stack.append((level, sid))
            built_sections.append(Section(section_id=sid, heading_level=level, start_line=idx, end_line=idx))
        section_id_per_line[idx] = stack[-1][1] if stack else 0

    # Fix up each section's end_line to the last line it owns.
    end_by_id: dict[int, int] = {}
    for idx in range(1, n + 1):
        end_by_id[section_id_per_line[idx]] = idx
    sections = tuple(
        Section(s.section_id, s.heading_level, s.start_line, end_by_id.get(s.section_id, s.start_line))
        for s in built_sections
    )

    return DocumentContext(
        path=path,
        kind=kind if isinstance(kind, str) else None,
        frontmatter=frontmatter if isinstance(frontmatter, dict) else {},
        title=title,
        body_start=body_start,
        lines=tuple(lines),
        paragraph_id_per_line=tuple(paragraph_id_per_line),
        paragraph_text=paragraph_text,
        sections=sections,
        section_id_per_line=tuple(section_id_per_line),
    )


# --- ResolutionIndex: project-wide existence oracle -------------------------
#
# `resolve()` answers "does this reference exist?" for task ids, typed entity
# ids, citation keys, DOIs/PMIDs, URLs (well-formed only — remote existence is
# out of scope for Part A), and relative artifact paths. All inputs are cheap
# file reads (task ledgers, entity frontmatter, references.bib) — building
# this index must NOT trigger a full graph build.

_TASK_REF_RE = re.compile(r"^(?:task:)?t(\d{2,})$")
_TYPED_REF_RE = re.compile(r"^[a-z][a-z0-9_-]*:[A-Za-z0-9][A-Za-z0-9_.-]*$")
_CITE_RE = re.compile(r"^(?:cite:|\[@)([A-Za-z][A-Za-z0-9_:.-]*)\]?$")
_DOI_RE = re.compile(r"^(?:doi:)?10\.\d{4,9}/\S+$", re.IGNORECASE)
_PMID_RE = re.compile(r"^(?:pmid:)?\d{5,9}$", re.IGNORECASE)
_URL_RE = re.compile(r"^https?://\S+$", re.IGNORECASE)


def _normalize_task_number(token: str) -> str:
    """Strip leading zeros so `"064"` and `"64"` compare equal; keep >=1 digit."""
    return token.lstrip("0") or "0"


@dataclass(frozen=True)
class ResolutionIndex:
    project_root: Path
    task_numbers: frozenset[str]     # normalized (leading zeros stripped), e.g. {"64"}
    entity_ids: frozenset[str]       # canonical, e.g. {"dataset:xyz", "task:t064"}
    bib_keys: frozenset[str]
    doi_corpus: frozenset[str]
    pmid_corpus: frozenset[str]
    data_root: Path

    def resolve(self, reference: str) -> bool:
        ref = reference.strip()
        if not ref:
            return False
        m = _TASK_REF_RE.match(ref)
        if m:
            return _normalize_task_number(m.group(1)) in self.task_numbers
        if _URL_RE.match(ref):
            return True  # well-formed; remote existence is out of scope for Part A
        m = _CITE_RE.match(ref)
        if m:
            return m.group(1) in self.bib_keys
        if _DOI_RE.match(ref):
            token = ref[len("doi:") :] if ref.lower().startswith("doi:") else ref
            return token.strip().lower() in self.doi_corpus
        if _PMID_RE.match(ref):
            return ref.split(":")[-1] in self.pmid_corpus
        if _TYPED_REF_RE.match(ref):
            return ref in self.entity_ids
        # Treat anything else as a candidate artifact path. Reject non-relative
        # paths outright: `Path(base) / ref` silently discards `base` when `ref`
        # is absolute, and `..` segments can escape the project root — a
        # fabricated/malicious absolute or traversal ref must never resolve.
        candidate = Path(ref)
        if candidate.is_absolute() or ".." in candidate.parts:
            return False
        for base in (self.project_root, self.data_root):
            if (base / ref).is_file():
                return True
        return False


# --- NotClaim structural layer -----------------------------------------------
#
# Recognizes numbers that are mechanically NOT quantitative claims: hardware
# IDs, accessions, license versions, and download sizes. Narrow by design —
# DOI/PMID/version/compact-ID span masking already lives in
# `prose_lint._mask_numeric_identifier_spans` and runs before the claim regex;
# this layer adds only the new categories that masking misses. Model
# dimensions and file sizes are context-gated, never blanket-masked, so a
# factual size like "3.2 Gb genome" stays a claim.

_HARDWARE_PREFIX_RE = re.compile(
    r"(?:RTX|GTX|GPU|CPU|NovaSeq|HiSeq|NextSeq|MiSeq|Tesla|A100|H100|V100)[\s:-]*$", re.IGNORECASE
)
_ACCESSION_PREFIX_RE = re.compile(r"\bGCST\d+\b")
_LICENSE_RE = re.compile(r"\b(?:CC-BY|CC-BY-SA|CC0|GPL|MIT|Apache)-?\d")
_FILE_SIZE_CONTEXT_RE = re.compile(
    r"^\s*(?:[KMGT]i?B)\s+(?:download|file|upload|payload|archive|dump)\b", re.IGNORECASE
)


def classify_structural(value: str, line: str, col: int) -> str | None:
    """Return a NotClaim reason for a clearly structural number, else None.

    `col` is the 1-based column of `value` within `line`. Narrow by design:
    only tokens that are mechanically not quantitative claims. Model
    dimensions / file sizes are context-gated, never blanket-masked, so a
    factual size like "3.2 Gb genome" stays a claim.

    Both hardware-id and file-size require ADJACENCY to their trigger word —
    a number merely sharing a sentence with "GPU" or "file" is not enough,
    since that over-masks genuine numeric claims (e.g. "the GPU processed
    4096 samples", "3.2 Gb genome file was archived").
    """
    start = col - 1
    end = start + len(value)
    prefix = line[:start]
    suffix = line[end : min(len(line), end + 24)]
    if _HARDWARE_PREFIX_RE.search(prefix):
        return "hardware-id"
    window = line[max(0, start - 24) : min(len(line), end + 24)]
    if _ACCESSION_PREFIX_RE.search(window):
        return "accession"
    if _LICENSE_RE.search(window):
        return "license-version"
    if _FILE_SIZE_CONTEXT_RE.search(suffix):
        return "file-size"
    return None


_SECTION_MARKER_RE = re.compile(r"^\s*<!--\s*stipulated\s*-->\s*$")
_BLOCK_START_RE = re.compile(r"^\s*<!--\s*stipulated:start\s*-->\s*$")
_BLOCK_END_RE = re.compile(r"^\s*<!--\s*stipulated:end\s*-->\s*$")


@dataclass(frozen=True)
class MarkerScope:
    scope: str                      # "document" | "section" | "block"
    covered_lines: frozenset[int]   # empty when scope == "document"
    whole_document: bool


def compute_marker_scopes(document: DocumentContext) -> tuple[MarkerScope, ...]:
    """Locate stipulated-marker declarations and their covered line ranges.

    Marker syntax is fixed (not a config knob) so templates/tooling agree
    across projects:
      - frontmatter `stipulated: true` -> whole-document scope, subsuming
        (and short-circuiting past) any finer section/block markers.
      - `<!-- stipulated -->` immediately under a heading -> that heading's
        section, fail-closed at the next equal-or-higher heading (reuses
        `DocumentContext.sections`).
      - `<!-- stipulated:start -->` ... `<!-- stipulated:end -->` -> the
        lines strictly between the fence pair.
    """
    scopes: list[MarkerScope] = []
    fm = document.frontmatter
    if isinstance(fm, dict) and fm.get("stipulated") is True:
        scopes.append(MarkerScope(scope="document", covered_lines=frozenset(), whole_document=True))
        return tuple(scopes)  # document flag subsumes all finer markers

    # Section markers: a `<!-- stipulated -->` on the line just after a heading
    # marks that heading's section (fail-closed via DocumentContext.sections).
    heading_line_to_section = {s.start_line: s for s in document.sections}
    for lineno in range(1, len(document.lines) + 1):
        if _SECTION_MARKER_RE.match(document.lines[lineno - 1]):
            heading_line = lineno - 1
            section = heading_line_to_section.get(heading_line)
            if section is not None:
                covered = frozenset(range(section.start_line, section.end_line + 1))
                scopes.append(MarkerScope(scope="section", covered_lines=covered, whole_document=False))

    # Block markers: lines strictly between a start/end fence pair.
    open_line: int | None = None
    for lineno in range(1, len(document.lines) + 1):
        raw = document.lines[lineno - 1]
        if _BLOCK_START_RE.match(raw):
            open_line = lineno
        elif _BLOCK_END_RE.match(raw) and open_line is not None:
            covered = frozenset(range(open_line + 1, lineno))
            scopes.append(MarkerScope(scope="block", covered_lines=covered, whole_document=False))
            open_line = None
    return tuple(scopes)


def marked_scope_for_line(scopes: tuple[MarkerScope, ...], line: int) -> str | None:
    for marker in scopes:
        if marker.whole_document or line in marker.covered_lines:
            return marker.scope
    return None


_TITLE_TASK_RE = re.compile(r"\bt(\d{2,})\b")


def _as_refs(value: object) -> list[str]:
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    if isinstance(value, list):
        return [v.strip() for v in value if isinstance(v, str) and v.strip()]
    return []


def _is_papers_path(path: Path) -> bool:
    parts = path.parts
    return any(left == "entities" and right == "papers" for left, right in zip(parts, parts[1:]))


def entity_source_candidates(
    document: DocumentContext, index: ResolutionIndex, config: NumericProvenanceConfig
) -> tuple[SourceCandidate, ...]:
    """Extract the explicit provenance an entity declares, existence-checked.

    Entity-scoped candidates come from exactly: (1) frontmatter fields listed
    in `config.provenance_fields`; (2) paper-note identity (`source_refs` plus
    doi/pmid/url/bibkey); (3) interpretation identity (`artifact`/`artifacts`);
    (4) an owning task named in the title. `related` is deliberately never
    read — it holds topical links, not sources (finding 2).
    """
    fm = document.frontmatter
    out: list[SourceCandidate] = []

    def add(reference: str, field_or_line: str, origin: str = "frontmatter") -> None:
        out.append(SourceCandidate(
            reference=reference, origin=origin, field_or_line=field_or_line,
            resolution_status="resolved" if index.resolve(reference) else "unresolved",
        ))

    for field in config.provenance_fields:
        for ref in _as_refs(fm.get(field)):
            add(ref, field)

    is_paper = (
        str(fm.get("kind")) == "paper"
        or _is_papers_path(document.path)
        or str(fm.get("id", "")).startswith("paper:")
    )
    if is_paper:
        for ref in _as_refs(fm.get("source_refs")):
            add(ref, "source_refs")
        for key in ("doi", "pmid", "url", "bibkey"):
            for ref in _as_refs(fm.get(key)):
                add(ref, key)

    if str(fm.get("kind")) == "interpretation" or str(fm.get("id", "")).startswith("interpretation:"):
        for field in ("artifact", "artifacts"):
            for ref in _as_refs(fm.get(field)):
                add(ref, field)

    if document.title:
        m = _TITLE_TASK_RE.search(document.title)
        if m:
            add(f"task:t{m.group(1)}", "title", origin="title")

    # Dedupe by (reference, field_or_line) preserving order.
    seen: set[tuple[str, str]] = set()
    deduped: list[SourceCandidate] = []
    for c in out:
        key = (c.reference, c.field_or_line)
        if key not in seen:
            seen.add(key)
            deduped.append(c)
    return tuple(deduped)


# --- LOCAL paragraph-scoped anchoring layer ----------------------------------
#
# A resolvable body reference anchors only its OWN paragraph (finding 2: one
# incidental body citation must not clear unrelated numbers elsewhere). A
# generic `config.anchor_patterns` regex match is weaker still: it suppresses
# that paragraph's finding but produces no `SourceCandidate` and never clears
# entity-wide.

_BODY_REF_RE = re.compile(
    r"(?:task:t\d{2,}"
    r"|\[@[A-Za-z][A-Za-z0-9_:.-]*\]"
    r"|cite:[A-Za-z][A-Za-z0-9_:.-]*"
    r"|dataset:[A-Za-z0-9][A-Za-z0-9_.-]*"
    r"|\[\[[^\]\n]+\]\])"
)


def local_candidates_for_paragraph(
    paragraph_text: str, index: ResolutionIndex
) -> tuple[SourceCandidate, ...]:
    """Extract resolvable body references scoped to a single paragraph.

    Matches `task:tNNN`, `[@key]`, `cite:key`, `dataset:slug`. A `[[wiki]]`
    link is topical (like `related`) — treated as evidence, not a candidate.
    """
    out: list[SourceCandidate] = []
    for m in _BODY_REF_RE.finditer(paragraph_text):
        ref = m.group(0)
        if ref.startswith("[["):
            continue
        out.append(SourceCandidate(
            reference=ref, origin="body", field_or_line="paragraph",
            resolution_status="resolved" if index.resolve(ref) else "unresolved",
        ))
    return tuple(out)


def paragraph_has_anchor_evidence(paragraph_text: str, anchor_patterns: tuple[str, ...]) -> bool:
    """True if any generic `anchor_patterns` regex matches anywhere in the paragraph.

    This is weak evidence only: it suppresses the paragraph's finding but
    never yields a `SourceCandidate` and never clears entity-wide.
    """
    if not anchor_patterns:
        return False
    return re.search("|".join(anchor_patterns), paragraph_text) is not None


def build_resolution_index(project_root: Path) -> ResolutionIndex:
    """Build a `ResolutionIndex` from cheap file-based sources only.

    Deliberately avoids `load_project_sources` / graph construction — every
    loader here is a direct, narrowly-scoped file read.
    """
    from science_tool import refs
    from science_tool.bibliography import load_bib_keys
    from science_tool.data_root import resolve_data_root

    root = project_root.resolve()
    task_numbers = {_normalize_task_number(n) for n in refs._load_task_ids(root)}
    return ResolutionIndex(
        project_root=root,
        task_numbers=frozenset(task_numbers),
        entity_ids=frozenset(refs._load_entity_index(root)),
        bib_keys=frozenset(load_bib_keys(root)),
        doi_corpus=frozenset(d.strip().lower() for d in refs._load_doi_corpus(root)),
        pmid_corpus=frozenset(refs._load_pmid_corpus(root)),
        data_root=resolve_data_root(root),
    )

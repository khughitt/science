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
    entity_prefix_owners: dict[str, int]

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
            # Exact canonical id, or a digit-lead short prefix owned by exactly
            # one entity (`interpretation:0013` -> the sole `interpretation:0013-…`).
            # Non-numeric leads never enter the map; ambiguous (multi-owner)
            # prefixes have owners > 1 — neither resolves, so a citation cannot
            # silently anchor to a guessed entity. Shared with refs body-scan.
            from science_tool import refs

            return refs.resolve_local_entity_ref(
                ref, self.entity_ids, self.entity_prefix_owners
            )
        # Treat anything else as a candidate artifact path. Reject non-relative
        # paths outright: `Path(base) / ref` silently discards `base` when `ref`
        # is absolute, and `..` segments can escape the project root — a
        # fabricated/malicious absolute or traversal ref must never resolve.
        candidate = Path(ref)
        if candidate.is_absolute() or ".." in candidate.parts:
            return False
        for base in (self.project_root, self.data_root):
            try:
                if (base / ref).exists():
                    return True
            except OSError:
                # Fail-closed: `Path.exists()` swallows only ENOENT/ENOTDIR/
                # EBADF/ELOOP (pathlib._ignore_error), so a ref that overruns
                # NAME_MAX/PATH_MAX -- e.g. a provenance field holding a path
                # followed by narrative prose -- raises ENAMETOOLONG straight
                # through and aborts the whole lint. Treat any probe failure as
                # "does not resolve under this root" and try the next.
                continue
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
_ACCESSION_PREFIX_ADJ_RE = re.compile(r"GCST[-\s]?$")
_LICENSE_PREFIX_ADJ_RE = re.compile(
    r"(?:CC-BY(?:-SA)?|CC-BY-NC|CC0|GPL|LGPL|MIT|Apache|BSD)-?$", re.IGNORECASE
)
_FILE_SIZE_CONTEXT_RE = re.compile(
    r"^\s*(?:[KMGT]i?B)\s+(?:download|file|upload|payload|archive|dump)\b", re.IGNORECASE
)


def classify_structural(value: str, line: str, col: int) -> str | None:
    """Return a NotClaim reason for a clearly structural number, else None.

    `col` is the 1-based column of `value` within `line`. Narrow by design:
    only tokens that are mechanically not quantitative claims. Model
    dimensions / file sizes are context-gated, never blanket-masked, so a
    factual size like "3.2 Gb genome" stays a claim.

    Hardware-id, accession, license-version, and file-size all require
    ADJACENCY to their trigger word — a number merely sharing a sentence
    with "GPU", "GCST", "CC-BY", or "file" is not enough, since that
    over-masks genuine numeric claims (e.g. "the GPU processed 4096
    samples", "GCST90441 lists 500 associated loci", "3.2 Gb genome file
    was archived").
    """
    start = col - 1
    end = start + len(value)
    prefix = line[:start]
    suffix = line[end : min(len(line), end + 24)]
    if _HARDWARE_PREFIX_RE.search(prefix):
        return "hardware-id"
    if _ACCESSION_PREFIX_ADJ_RE.search(prefix):
        return "accession"
    if _LICENSE_PREFIX_ADJ_RE.search(prefix):
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
    # marks that heading's section, fail-closed at the next equal-or-higher
    # heading. `DocumentContext.section_id_per_line` attributes a subsection's
    # own lines to the CHILD section id, so the marked `Section.end_line`
    # alone stops short of nested subsections. Recompute the upper bound by
    # scanning `document.sections` (in document order) for the next heading
    # whose level is <= the marked heading's level; deeper subsections in
    # between stay covered, matching the doc's stated coverage promise.
    heading_line_to_section = {s.start_line: s for s in document.sections}
    sections_by_start = sorted(document.sections, key=lambda s: s.start_line)
    for lineno in range(1, len(document.lines) + 1):
        if _SECTION_MARKER_RE.match(document.lines[lineno - 1]):
            heading_line = lineno - 1
            section = heading_line_to_section.get(heading_line)
            if section is not None:
                end_line = len(document.lines)
                for other in sections_by_start:
                    if other.start_line > section.start_line and other.heading_level <= section.heading_level:
                        end_line = other.start_line - 1
                        break
                covered = frozenset(range(section.start_line, end_line + 1))
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


def _vehicle_paths(value: object) -> list[str]:
    """Extract the `path` of each well-formed `vehicles:` entry, in order.

    A vehicle is a `{path, sha256}` mapping. Only `path` is a reference; the
    hash is verified elsewhere. Malformed entries — a bare string, a mapping
    with no usable `path` — yield nothing rather than a guess, so an
    unfreezable vehicle never anchors anything.
    """
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for entry in value:
        if not isinstance(entry, dict):
            continue
        path = entry.get("path")
        if isinstance(path, str) and path.strip():
            out.append(path.strip())
    return out


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
    (4) pre-registration identity (`vehicles[].path`); (5) an owning task named
    in the title. `related` is deliberately never read — it holds topical links,
    not sources (finding 2).
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

    # A pre-registration's provenance field is `vehicles:`, not `source_refs`:
    # that is what `templates/pre-registration.md` declares and what
    # `check:prereg.vehicle-undeclared` requires. Its entries are
    # `{path, sha256}` mappings, so `_as_refs` — which reads strings — cannot
    # see them, and until this block existed a pre-registration could not
    # declare entity-scope provenance at all (fb-2026-07-26-018). Reading
    # `path` here also makes the anchor stronger than a bare string ref: the
    # same entry is content-addressed and hash-verified by the vehicle check.
    if str(fm.get("kind")) == "pre-registration" or str(fm.get("id", "")).startswith("pre-registration:"):
        for ref in _vehicle_paths(fm.get("vehicles")):
            add(ref, "vehicles")

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

# Provenance-bearing entity kinds whose typed citations may anchor a numeric
# claim. Deliberately EXCLUDES topical/framing kinds (hypothesis, question,
# topic, theme, concept, discussion, …): existence-checking proves identity,
# not that the number is sourced there. `task:`/`[@]`/`cite:` remain anchors
# through their own alternatives below.
_ANCHOR_ENTITY_KINDS = frozenset({
    # result / evidence artifacts produced by project work
    "interpretation", "report", "synthesis", "observation", "finding",
    "evidence-line", "validation-report", "experiment", "workflow-run",
    "data-package",
    # external sources
    "dataset", "paper", "book", "source",
    # registered / planned parameters
    "pre-registration", "plan",
})

# Longest-first so hyphenated kinds (validation-report) win over any prefix.
_ANCHOR_KIND_ALT = "|".join(sorted(_ANCHOR_ENTITY_KINDS, key=len, reverse=True))

_BODY_REF_RE = re.compile(
    r"(?:(?<![A-Za-z])task:t\d{2,}"
    r"|\[@[A-Za-z][A-Za-z0-9_:.-]*\]"
    r"|(?<![A-Za-z])cite:[A-Za-z][A-Za-z0-9_:.-]*"
    # Provenance-bearing typed entity-ref (incl. dataset). Three guards:
    #  (1) left lookbehind — rejects an id embedded in a larger token
    #      (x_interpretation, path/…, a:…);
    #  (2) id-scoped no-`..` lookahead — a malformed id whose char-run contains
    #      consecutive dots matches NOTHING here (not even a truncated prefix),
    #      mirroring _VERBATIM_RE's sole no-`..` prohibition;
    #  (3) atomic id body `(?>…)` over the FULL _VERBATIM_RE id charset
    #      (`[0-9A-Za-z](?:[0-9A-Za-z._-]*[0-9A-Za-z])?` — alnum start, alnum
    #      terminal so a trailing sentence period stays outside, arbitrary
    #      internal `._-` incl. `.-`), locked so it cannot backtrack to a
    #      shorter id: `interpretation:0007.foo@host` fails outright rather
    #      than truncating to a resolvable `interpretation:0007`;
    #  followed by a right lookahead rejecting @host / /path / :extra.
    r"|(?<![A-Za-z0-9_.:/@-])(?:" + _ANCHOR_KIND_ALT + r"):"
    r"(?![A-Za-z0-9._-]*\.\.)"
    r"(?>[0-9A-Za-z](?:[0-9A-Za-z._-]*[0-9A-Za-z])?)"
    r"(?![A-Za-z0-9_:/@-])"
    r"|\[\[[^\]\n]+\]\])"
)


def local_candidates_for_paragraph(
    paragraph_text: str, index: ResolutionIndex
) -> tuple[SourceCandidate, ...]:
    """Extract resolvable body references scoped to a single paragraph.

    Matches `task:tNNN`, `[@key]`, `cite:key`, and provenance-bearing typed
    entity-refs (`_ANCHOR_ENTITY_KINDS`, e.g. `interpretation:0011-…`,
    `dataset:slug`), full-id or unique digit-lead prefix. A `[[wiki]]` link is
    topical (like `related`) — treated as evidence, not a candidate.
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


def _within_bound_span(line: int, col: int, length: int, spans: frozenset[tuple[int, int, int]]) -> bool:
    """True if the claim occupying columns `[col, col+length)` on `line` overlaps
    any `(sl, cs, ce)` span (1-based, `ce` exclusive) with `sl == line`.

    A real overlap test, not exact-equality: the claim and the bound token are
    the same token in practice, but this must hold even if their extents
    merely intersect.
    """
    claim_start, claim_end = col, col + length
    for sl, cs, ce in spans:
        if sl == line and claim_start < ce and cs < claim_end:
            return True
    return False


def assess_numeric_claims(
    document: DocumentContext,
    index: ResolutionIndex,
    config: NumericProvenanceConfig,
    *,
    bound_spans: frozenset[tuple[int, int, int]] = frozenset(),
) -> list[ClaimAssessment]:
    """Classify every numeric claim in a document's body prose.

    Resolution order per claim (first match wins): skip-if-bound -> NotClaim
    -> Exempt -> Anchored(entity) -> Anchored(local) -> Unanchored. Reuses the
    claim extraction and line-walking gates from
    `prose_lint.detect_numeric_anchor` rather than re-implementing them, so
    behavior stays consistent with the existing detector.

    `bound_spans` are (line, col_start, col_end) spans (1-based, col_end
    exclusive) of numeric tokens already pinned by a Part-B `numeric_claims`
    binding (see `numeric_binding.parse_claim_bindings`). A claim whose span
    falls inside a bound span is skipped entirely -- no assessment is
    emitted for it -- because Part B verifies it instead. The default empty
    frozenset preserves existing callers' behavior byte-for-byte.
    """
    from science_tool.prose_lint import (  # reuse, do not duplicate
        _BARE_YEAR_RE, _BOLD_STRUCTURAL_LABEL_RE, _CROSS_REFERENCE_RE,
        _HEADER_OR_LIST_RE, _LIST_RE, _NUMERIC_CLAIM_RE, _mask_numeric_identifier_spans,
    )
    # `blank_inline_code`, not `strip_inline_code`: every column below -- the
    # one reported to the author, the one `classify_structural` slices a window
    # around, and the one `_within_bound_span` compares -- is measured on this
    # line and must index the real file line (fb-2026-07-26-007).
    from science_tool.markdown_utils import blank_inline_code

    marker_scopes = compute_marker_scopes(document)
    entity_cands = entity_source_candidates(document, index, config)
    entity_resolved = tuple(c for c in entity_cands if c.resolution_status == "resolved")
    kind_hint = "stipulated" if (document.kind in config.spec_class_kinds) else None

    out: list[ClaimAssessment] = []
    in_fence = False
    in_list_item = False
    for lineno_zero, raw in enumerate(document.lines):
        lineno = lineno_zero + 1
        if lineno < document.body_start:
            continue
        if is_fence_line(raw):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if not raw.strip():
            in_list_item = False
            continue
        if _HEADER_OR_LIST_RE.match(raw):
            in_list_item = bool(_LIST_RE.match(raw))
            continue
        if _BOLD_STRUCTURAL_LABEL_RE.match(raw):
            continue
        if in_list_item and raw.startswith((" ", "\t")):
            continue
        in_list_item = False
        if raw.lstrip().startswith("|"):
            continue
        line = _mask_numeric_identifier_spans(blank_inline_code(raw))
        crossref_spans = [m.span() for m in _CROSS_REFERENCE_RE.finditer(line)]
        pid = document.paragraph_id_per_line[lineno]
        sid = document.section_id_per_line[lineno]
        paragraph = document.paragraph_text.get(pid, "")
        for match in _NUMERIC_CLAIM_RE.finditer(line):
            value = match.group(0)
            if _BARE_YEAR_RE.match(value):
                continue
            if any(s <= match.start() < e for s, e in crossref_spans):
                continue
            claim = NumericClaim(value=value, line=lineno, col=match.start() + 1,
                                 paragraph_id=pid, section_id=sid)
            if _within_bound_span(lineno, match.start() + 1, len(value), bound_spans):
                continue
            # 1 — NotClaim. Classified against `line`, the string the column was
            # measured on; its adjacency triggers are prose words, never the
            # identifier spans the maskers blank, so nothing it looks for is lost.
            reason = classify_structural(value, line, match.start() + 1)
            if reason is not None:
                out.append(NotClaim(claim=claim, reason=reason))
                continue
            # 2 — Exempt
            scope = marked_scope_for_line(marker_scopes, lineno)
            if scope is not None:
                out.append(Exempt(claim=claim, reason="stipulated", scope=scope))
                continue
            # 3 — Anchored (entity)
            if entity_resolved:
                out.append(Anchored(claim=claim, candidates=entity_resolved))
                continue
            # 3 — Anchored (local, paragraph-scoped)
            local = tuple(c for c in local_candidates_for_paragraph(paragraph, index)
                          if c.resolution_status == "resolved")
            if local:
                out.append(Anchored(claim=claim, candidates=local))
                continue
            # anchor_evidence (weak local suppression, no candidate)
            evidence = paragraph_has_anchor_evidence(paragraph, config.anchor_patterns)
            if evidence:
                out.append(Unanchored(claim=claim, kind_hint=kind_hint, local_evidence=True))
                continue
            # 4 — Unanchored (the signal)
            out.append(Unanchored(claim=claim, kind_hint=kind_hint, local_evidence=False))
    return out


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
    entity_ids = frozenset(refs._load_entity_index(root))
    entity_prefix_owners = refs.build_entity_prefix_owners(entity_ids)
    return ResolutionIndex(
        project_root=root,
        task_numbers=frozenset(task_numbers),
        entity_ids=entity_ids,
        bib_keys=frozenset(load_bib_keys(root)),
        doi_corpus=frozenset(d.strip().lower() for d in refs._load_doi_corpus(root)),
        pmid_corpus=frozenset(refs._load_pmid_corpus(root)),
        data_root=resolve_data_root(root),
        entity_prefix_owners=entity_prefix_owners,
    )

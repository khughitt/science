"""Prose-quality lints derived from natural-systems's t466 citation-audit pilot.

Each detector function takes a markdown file Path and returns a list of
LintIssue records. The CLI orchestrator (`prose_lint_cli.py`) batches these
across a project tree and renders results.

See `docs/conventions/prose-lints.md` for the lint catalog and severity rules.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path
from typing import Callable

from science_tool.markdown_utils import (
    is_fence_line,
    frontmatter_span,
    strip_inline_code,
)

logger = logging.getLogger(__name__)

CHECKS: tuple[str, ...] = (
    "bare-author-year",
    "short-form-ids",
    "frontmatter-inline-gap",
    "numeric-anchor",
    "unsupported-citation-syntax",
)

DEFAULT_SEVERITY: dict[str, str] = {
    "bare-author-year": "warn",
    "short-form-ids": "warn",
    "frontmatter-inline-gap": "info",
    "numeric-anchor": "info",
    "unsupported-citation-syntax": "warn",
}


@dataclass(frozen=True)
class LintIssue:
    file: Path
    line: int
    col: int
    check: str
    severity: str
    message: str
    match: str
    byte_col: int | None = None


def severity_for(check: str, *, strict: bool) -> str:
    base = DEFAULT_SEVERITY[check]
    if check == "frontmatter-inline-gap":
        return base
    return "warn" if strict and base == "info" else base


# Capture: (Authorname) (Year), where Authorname starts with uppercase and is
# 3+ chars (excludes "I 2022", "A 2022"). Year is 1900-2099.
_BARE_AUTHOR_YEAR_RE = re.compile(r"\b([A-Z][A-Za-z]{2,}(?:\s(?:and|&)\s[A-Z][A-Za-z]{2,})?)\s(19\d\d|20\d\d)\b")
# Anchor: `[@key]` immediately following or preceding the match (within 30 chars)
_NEARBY_BIBTEX_RE = re.compile(r"\[@[A-Za-z][A-Za-z0-9_-]*\]")
# An adjacent `[[WikiLink]]` (the project's citation convention) also anchors a
# mention, mirroring `[@key]`.
_NEARBY_WIKILINK_RE = re.compile(r"\[\[[^\]\n]+\]\]")
_TRAILING_CITATION_RE = re.compile(r"\s*(?:\[[^\]\n]*@[^\]\n]*\]|\[\[[^\]\n]+\]\])")
# Calendar words that match the <Capitalized> <Year> shape but are dates
# ("May 2026", "Summer 2024"), not author-year citations.
_DATE_WORDS: frozenset[str] = frozenset(
    {
        "january",
        "february",
        "march",
        "april",
        "may",
        "june",
        "july",
        "august",
        "september",
        "october",
        "november",
        "december",
        "jan",
        "feb",
        "mar",
        "apr",
        "jun",
        "jul",
        "aug",
        "sep",
        "sept",
        "oct",
        "nov",
        "dec",
        "spring",
        "summer",
        "fall",
        "autumn",
        "winter",
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
    }
)
# Common non-author leading tokens that match the <Capitalized> <Year> shape in
# dated status/prose lines ("Backfilled 2026-05-04:", "The 2026 audit ..."),
# not author-year citations.
_LEADING_STOPWORDS: frozenset[str] = frozenset(
    {
        "the",
        "this",
        "these",
        "those",
        "that",
        "done",
        "resolved",
        "fixed",
        "closed",
        "merged",
        "completed",
        "backfilled",
        "published",
        "updated",
        "added",
        "created",
        "removed",
        "in",
        "by",
        "on",
        "at",
        "see",
        "per",
        "via",
        "note",
        "since",
        "as",
    }
)
# Year immediately followed by `-NN` (the month/day of an ISO date like
# `2026-05-04` or year-month `2026-05`).
_ISO_DATE_TAIL_RE = re.compile(r"-\d\d")

# Short-form prefix → canonical kind mapping. Lowercase letter prefixes pulled
# from refs._LOCAL_ENTITY_KINDS first letters where a unique mapping exists;
# uppercase variants (Q1, T088) are common ad-hoc shorthand.
_SHORT_FORM_KIND_MAP: dict[str, str] = {
    "q": "question",
    "Q": "question",
    "h": "hypothesis",
    "H": "hypothesis",
    "t": "task",
    "T": "task",
    "d": "discussion",
    "D": "discussion",
    "i": "interpretation",
    "I": "interpretation",
}
_SHORT_FORM_RE = re.compile(r"\b([qQhHtTdDiI])(\d{1,4})\b")
# Canonical form check: `<kind>:<short>` should NOT be flagged.
_CANONICAL_PREFIX_RE = re.compile(r"\b(question|hypothesis|task|discussion|interpretation):")
# Task-list heading shape: `## [t088] Title`. Don't flag the bracketed ID
# inside such a header — it IS the canonical form for that file convention.
_TASK_HEADING_RE = re.compile(r"^\s*##+\s*\[[a-zA-Z]\d+\]")
# `[[h006-regime-sequence]]` wiki-links are the toolchain's linking convention;
# their inner text (e.g. `h006`) is a resolvable reference, not a bare short form.
_WIKILINK_SPAN_RE = re.compile(r"\[\[[^\]\n]*\]\]")
_CANONICAL_ID_SPAN_RE = re.compile(r"\b[a-z][a-z0-9_-]*:[A-Za-z0-9][A-Za-z0-9_.-]*\b")
_CELL_LINE_CONTEXT_RE = re.compile(r"\bcell[-\s]?lines?\b", re.IGNORECASE)
_KNOWN_CELL_LINE_SHORT_FORMS: frozenset[str] = frozenset({"H929", "H1112", "H1634"})
_BIOMED_TIMEPOINT_CONTEXT_RE = re.compile(
    r"\b(sample|samples|timepoint|timepoints|day|days|collected|collection|baseline|post[-\s]?treatment)\b",
    re.IGNORECASE,
)
_BIOMED_REAGENT_CONTEXT_RE = re.compile(
    r"\b(histone|reagent|stain|stained|staining|blockade|inhibitor|perturbation|mark|methylation)\b",
    re.IGNORECASE,
)


def _mask_wikilinks(line: str) -> str:
    """Blank out `[[...]]` spans, preserving column offsets for other matches."""
    return _WIKILINK_SPAN_RE.sub(lambda m: " " * len(m.group(0)), line)


def _mask_canonical_id_spans(line: str) -> str:
    """Blank out namespaced canonical IDs, preserving columns for other matches."""
    return _CANONICAL_ID_SPAN_RE.sub(lambda m: " " * len(m.group(0)), line)


def _is_cell_line_context(line: str, match: re.Match[str]) -> bool:
    window = line[max(0, match.start() - 40) : min(len(line), match.end() + 40)]
    return bool(_CELL_LINE_CONTEXT_RE.search(window))


def _is_cell_line_short_form(line: str, match: re.Match[str]) -> bool:
    short = match.group(0)
    return short in _KNOWN_CELL_LINE_SHORT_FORMS or (match.group(1).isupper() and _is_cell_line_context(line, match))


def _is_non_reference_h1_context(line: str, match: re.Match[str]) -> bool:
    if match.group(0) != "H1":
        return False
    window = line[max(0, match.start() - 30) : min(len(line), match.end() + 30)].lower()
    return "heading" in window or "homology" in window


def _is_local_discussion_label(line: str, match: re.Match[str]) -> bool:
    if match.group(1) != "D" or len(match.group(2)) != 1:
        return False
    if match.start() > 0 and line[match.start() - 1] in {"/", "§"}:
        return True
    if match.end() < len(line) and line[match.end()] == "/":
        return True
    preceding = line[max(0, match.start() - 16) : match.start()]
    return bool(re.search(r"(?:\b(?:task|tasks|domain|domains|section|appendix)\s|§)\s*$", preceding, re.IGNORECASE))


def _is_biomedical_short_form_context(line: str, match: re.Match[str]) -> bool:
    prefix = match.group(1)
    number = match.group(2)
    window = line[max(0, match.start() - 48) : min(len(line), match.end() + 48)]
    if prefix == "D" and len(number) <= 2:
        return bool(_BIOMED_TIMEPOINT_CONTEXT_RE.search(window))
    if prefix == "H" and number in {"1", "2", "3", "4"}:
        return bool(_BIOMED_REAGENT_CONTEXT_RE.search(window))
    if prefix == "T" and len(number) <= 2:
        return bool(_BIOMED_TIMEPOINT_CONTEXT_RE.search(window) or re.search(r"\bMRI\b", window))
    return False


def _utf8_byte_col(line: str, char_index: int) -> int:
    return len(line[:char_index].encode("utf-8")) + 1


def detect_bare_author_year(
    path: Path,
    *,
    strict: bool = False,
    deny: list[str] | None = None,
    bib_surnames: set[str] | None = None,
) -> list[LintIssue]:
    """Detect `<Capitalized> <Year>` mentions in body prose without [@key].

    `deny` lists exact mentions (e.g. ``"IMMULITE 2000"``) to skip — residual
    false positives, parity with short-form-ids' deny-list.

    `bib_surnames` (lowercased author surnames from `references.bib`) makes the
    check bib-aware: when provided, only a mention whose author surname is in the
    bib is flagged — i.e. "you have this paper but didn't cite it". This skips
    secondary citations to papers not in the bib and non-author false positives
    (journal/org/product fragments) by construction, mirroring short-form-ids'
    resolver. When ``None`` (no bibliography), the check falls back to flagging
    every unanchored mention.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    _, body_start = frontmatter_span(path)
    lines = text.splitlines()
    issues: list[LintIssue] = []
    in_fence = False
    for lineno_zero, raw_line in enumerate(lines):
        lineno = lineno_zero + 1
        if lineno < body_start:
            continue
        if is_fence_line(raw_line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        line = strip_inline_code(raw_line)
        for match in _BARE_AUTHOR_YEAR_RE.finditer(line):
            mention = f"{match.group(1)} {match.group(2)}"
            if deny and mention in deny:
                continue
            leading_token = match.group(1).split()[0].lower()
            if leading_token in _DATE_WORDS or leading_token in _LEADING_STOPWORDS:
                continue
            if bib_surnames is not None:
                surnames = {tok.lower() for tok in match.group(1).split() if tok.lower() not in {"and", "&"}}
                if surnames.isdisjoint(bib_surnames):
                    continue
            if _ISO_DATE_TAIL_RE.match(line, match.end()):
                continue
            if _TRAILING_CITATION_RE.match(line[match.end() :]):
                continue
            window_start = max(0, match.start() - 30)
            window_end = min(len(line), match.end() + 30)
            window = line[window_start:window_end]
            if _NEARBY_BIBTEX_RE.search(window) or _NEARBY_WIKILINK_RE.search(window):
                continue
            issues.append(
                LintIssue(
                    file=path,
                    line=lineno,
                    col=match.start() + 1,
                    check="bare-author-year",
                    severity=severity_for("bare-author-year", strict=strict),
                    message=f"bare author-year mention '{mention}' has no adjacent [@key]",
                    match=mention,
                )
            )
    return issues


def detect_short_form_ids(
    path: Path,
    *,
    strict: bool = False,
    deny: list[str] | None = None,
    resolver: dict[str, str] | None = None,
) -> list[LintIssue]:
    """Detect bare `Q1` / `t088` style refs that should be `question:q01-…` etc.

    `resolver` maps known aliases (and canonical ids) to canonical ids; a token
    that resolves through it is an authored reference to a real entity, not a
    style violation, so it is skipped — aligning this check with entity_identity.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    _, body_start = frontmatter_span(path)
    lines = text.splitlines()
    issues: list[LintIssue] = []
    in_fence = False
    for lineno_zero, raw_line in enumerate(lines):
        lineno = lineno_zero + 1
        if lineno < body_start:
            continue
        if is_fence_line(raw_line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if _TASK_HEADING_RE.match(raw_line):
            continue
        line = _mask_canonical_id_spans(_mask_wikilinks(strip_inline_code(raw_line)))
        for match in _SHORT_FORM_RE.finditer(line):
            # Skip if preceded by `<kind>:` — already canonical.
            preceding = line[max(0, match.start() - 20) : match.start()]
            if _CANONICAL_PREFIX_RE.search(preceding):
                continue
            short = match.group(0)
            if deny and short in deny:
                continue
            if _is_cell_line_short_form(line, match):
                continue
            if _is_non_reference_h1_context(line, match):
                continue
            if _is_local_discussion_label(line, match):
                continue
            if _is_biomedical_short_form_context(line, match):
                continue
            if resolver and (short in resolver or short.lower() in resolver):
                continue
            kind = _SHORT_FORM_KIND_MAP[match.group(1)]
            issues.append(
                LintIssue(
                    file=path,
                    line=lineno,
                    col=match.start() + 1,
                    check="short-form-ids",
                    severity=severity_for("short-form-ids", strict=strict),
                    message=f"short-form ID '{short}' should be canonical '{kind}:…'",
                    match=short,
                    byte_col=_utf8_byte_col(raw_line, match.start()),
                )
            )
    return issues


def detect_frontmatter_inline_gaps(
    path: Path, *, strict: bool = False, alias_map: dict[str, str] | None = None
) -> list[LintIssue]:
    """For each `related:` entry in frontmatter, flag if absent from body text.

    Reports all gaps at line 1 (the file is the unit, not the location).

    `alias_map` (alias → canonical-id, e.g. from `build_short_form_resolver`)
    lets the body satisfy a `related:` entry via any equivalent spelling — a
    project shorthand like `mm30` counts as a mention of `multiple-myeloma`.
    """
    data, body_start = frontmatter_span(path)
    related = data.get("related") if isinstance(data, dict) else None
    if not isinstance(related, list) or not related:
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return []
    body = "\n".join(lines[body_start - 1 :])
    equivalents_by_canonical: dict[str, set[str]] = {}
    for alias, canonical in (alias_map or {}).items():
        equivalents_by_canonical.setdefault(canonical, set()).add(alias)
    issues: list[LintIssue] = []
    for ref in related:
        if not isinstance(ref, str) or not ref.strip():
            continue
        if ref in body:
            continue
        if alias_map:
            canonical = alias_map.get(ref) or alias_map.get(ref.lower()) or ref
            equivalents = equivalents_by_canonical.get(canonical, set())
            if any(equiv in body for equiv in equivalents):
                continue
        issues.append(
            LintIssue(
                file=path,
                line=1,
                col=1,
                check="frontmatter-inline-gap",
                severity=severity_for("frontmatter-inline-gap", strict=strict),
                message=f"frontmatter related entry '{ref}' never appears in body prose",
                match=ref,
            )
        )
    return issues


# Numeric claim: float, integer with %, ratio. Excludes bare integers <100
# (too noisy) and bare 4-digit years (handled separately below).
_NUMERIC_CLAIM_RE = re.compile(
    r"(?<![A-Za-z0-9_.,])"
    r"(?:[0-9]{1,3}(?:,[0-9]{3})+(?:\.[0-9]+)?%?|[0-9]+\.[0-9]+|[0-9]{2,}%|[0-9]{2,}/[0-9]+|[0-9]{3,})"
    r"(?![A-Za-z0-9_.,])"
)
# Standalone 4-digit years (1900-2099) — never claims, always exclude.
_BARE_YEAR_RE = re.compile(r"^(?:19\d{2}|20\d{2})$")
# DOI and accession-like identifiers frequently contain punctuation-delimited
# numeric fragments; those are identifiers, not prose claims needing anchors.
_DOI_SPAN_RE = re.compile(
    r"\b(?:doi\s*:\s*|https?://(?:dx\.)?doi\.org/)?10\.\d{4,9}/[-._;()/:A-Z0-9]+",
    re.IGNORECASE,
)
_IDENTIFIER_SPAN_RE = re.compile(
    r"\b(?:"
    r"(?:PMID|PMCID|PMC|NCT|GSE|GSM|SRR|ERR|DRR|PRJNA|PRJEB|PRJDB|ENSG|ENST|RS)"
    r"\s*:?\s*[A-Z]*\d[A-Z0-9_.-]*"
    r"|[A-Z]{2,}(?:-[A-Z0-9]{2,})*-\d{2,}[A-Z0-9_.-]*"
    r")\b",
    re.IGNORECASE,
)
_IDENTIFIER_LABEL_SPAN_RE = re.compile(
    r"\b(?:accessions?|identifiers?|samples?|aliquots?|runs?|barcodes?)\s*:?\s*[A-Z]*\d[A-Z0-9_.-]*\b",
    re.IGNORECASE,
)
_VERSION_LABEL_SPAN_RE = re.compile(
    r"\b[A-Za-z][A-Za-z0-9_-]*(?:DB|db|[A-Z][A-Za-z0-9_-]*)\s+v?\d+(?:\.\d+)+\b"
)
_RUNTIME_VERSION_SPAN_RE = re.compile(
    r"\b(?:Python|Node(?:\.js)?|R|NumPy|numpy|pandas|polars|pytest|Click|Typer)\s+v?\d+(?:\.\d+)+(?:\+)?\b"
)
_COMPACT_STRUCTURAL_ID_SPAN_RE = re.compile(r"\b[A-Z]{1,3}-\d{3,}\b")
# Section/list header: leading `#`, `-`, `*`, or `1.` style numbering.
_HEADER_OR_LIST_RE = re.compile(r"^\s*(?:#+|[-*]|\d+\.)\s")
_LIST_RE = re.compile(r"^\s*(?:[-*]|\d+\.)\s")
# Internal cross-references (`Figure 3.2`, `Section 4.1`, `Table 100`, `§4.2`,
# `Eq. 2`) name a structural element, not a numeric claim that needs a data
# anchor. The number (including dotted/ranged forms) is consumed alongside the
# keyword so its span can be excluded from numeric-claim matching.
_CROSS_REFERENCE_RE = re.compile(
    r"(?:\b(?:Sections?|Secs?|Chapters?|Chaps?|Figures?|Figs?|Tables?|Tbls?|Lines?|"
    r"Equations?|Eqs?|Appendix|Appendices|Appx|Panels?)|§)"
    r"\.?\s*~?\d+(?:\.\d+)*(?:[-–]\d+(?:\.\d+)*)?\+?",
    re.IGNORECASE,
)
_BOLD_STRUCTURAL_LABEL_RE = re.compile(
    r"^\s*(?:\*\*|__)(?=[^*_]*(?:Task|Batch|Wave)\b)[^*_]+(?:\*\*|__)\s*$",
    re.IGNORECASE,
)


def _mask_numeric_identifier_spans(line: str) -> str:
    """Blank identifier spans, preserving columns for remaining numeric claims."""
    line = _DOI_SPAN_RE.sub(lambda match: " " * len(match.group(0)), line)
    line = _IDENTIFIER_SPAN_RE.sub(lambda match: " " * len(match.group(0)), line)
    line = _IDENTIFIER_LABEL_SPAN_RE.sub(lambda match: " " * len(match.group(0)), line)
    line = _VERSION_LABEL_SPAN_RE.sub(lambda match: " " * len(match.group(0)), line)
    line = _RUNTIME_VERSION_SPAN_RE.sub(lambda match: " " * len(match.group(0)), line)
    line = _COMPACT_STRUCTURAL_ID_SPAN_RE.sub(lambda match: " " * len(match.group(0)), line)
    return _mask_canonical_id_spans(line)


def detect_numeric_anchor(
    path: Path,
    *,
    strict: bool = False,
    anchor_patterns: list[str] | None = None,
) -> list[LintIssue]:
    """Flag numeric claims in body prose without an anchor token in the same paragraph.

    `anchor_patterns` is a list of regex fragments. A claim is considered
    anchored if any pattern matches anywhere in the same paragraph (lines
    separated by blank lines).
    """
    if anchor_patterns is None:
        from science_tool.project_config import DEFAULT_ANCHOR_PATTERNS  # noqa: PLC0415

        anchor_patterns = list(DEFAULT_ANCHOR_PATTERNS)
    anchor_re = re.compile("|".join(anchor_patterns)) if anchor_patterns else None

    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    data, body_start = frontmatter_span(path)
    if _paper_note_has_source_context(path, data) or _interpretation_has_artifact_context(data):
        return []
    lines = text.splitlines()
    issues: list[LintIssue] = []
    in_fence = False
    in_list_item = False
    # Pre-compute paragraph boundaries (1-based line index → paragraph index).
    paragraph_id_per_line: list[int] = [0] * (len(lines) + 1)
    para_id = 0
    for idx, line in enumerate(lines, start=1):
        if not line.strip():
            para_id += 1
        paragraph_id_per_line[idx] = para_id
    paragraph_text: dict[int, str] = {}
    for idx, line in enumerate(lines, start=1):
        pid = paragraph_id_per_line[idx]
        paragraph_text[pid] = paragraph_text.get(pid, "") + line + "\n"

    for lineno_zero, raw_line in enumerate(lines):
        lineno = lineno_zero + 1
        if lineno < body_start:
            continue
        if is_fence_line(raw_line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if not raw_line.strip():
            in_list_item = False
            continue
        if _HEADER_OR_LIST_RE.match(raw_line):
            in_list_item = bool(_LIST_RE.match(raw_line))
            continue
        if _BOLD_STRUCTURAL_LABEL_RE.match(raw_line):
            continue
        if in_list_item and raw_line.startswith((" ", "\t")):
            continue
        in_list_item = False
        if raw_line.lstrip().startswith("|"):
            continue
        line = _mask_numeric_identifier_spans(strip_inline_code(raw_line))
        crossref_spans = [m.span() for m in _CROSS_REFERENCE_RE.finditer(line)]
        for match in _NUMERIC_CLAIM_RE.finditer(line):
            value = match.group(0)
            if _BARE_YEAR_RE.match(value):
                continue  # standalone year, not a claim
            if any(start <= match.start() < end for start, end in crossref_spans):
                continue  # internal cross-reference (Figure/Section/Table/…)
            paragraph = paragraph_text[paragraph_id_per_line[lineno]]
            if anchor_re and anchor_re.search(paragraph):
                continue
            issues.append(
                LintIssue(
                    file=path,
                    line=lineno,
                    col=match.start() + 1,
                    check="numeric-anchor",
                    severity=severity_for("numeric-anchor", strict=strict),
                    message=f"numeric claim '{value}' has no anchor in this paragraph",
                    match=value,
                )
            )
    return issues


def _paper_note_has_source_context(path: Path, frontmatter: dict) -> bool:
    """Paper notes with explicit source identity are already single-source anchored."""
    parts = path.parts
    is_paper_path = any(left == "entities" and right == "papers" for left, right in zip(parts, parts[1:]))
    if not is_paper_path:
        return False
    if frontmatter.get("kind") != "paper" and not str(frontmatter.get("id", "")).startswith("paper:"):
        return False
    source_refs = frontmatter.get("source_refs")
    if isinstance(source_refs, list) and any(isinstance(ref, str) and ref.strip() for ref in source_refs):
        return True
    return any(
        isinstance(frontmatter.get(key), str) and frontmatter[key].strip() for key in ("doi", "pmid", "url", "bibkey")
    )


def _interpretation_has_artifact_context(frontmatter: dict) -> bool:
    """Interpretations with an artifact field are result reports over that artifact."""
    if frontmatter.get("kind") != "interpretation" and not str(frontmatter.get("id", "")).startswith("interpretation:"):
        return False
    return isinstance(frontmatter.get("artifact"), str) and frontmatter["artifact"].strip()


def detect_unsupported_citation_syntax(path: Path, *, strict: bool = False) -> list[LintIssue]:
    """Flag `@key` tokens outside a recognized `[@key]` block.

    Emits one finding per unsupported token so authors are warned before export.
    Unsupported forms include bare `@key`, `[see @key]`, and `[-@key]`.
    """
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return []
    _, body_start = frontmatter_span(path)
    issues: list[LintIssue] = []
    in_fence = False
    for lineno_zero, raw_line in enumerate(lines):
        lineno = lineno_zero + 1
        if lineno < body_start:
            continue
        if is_fence_line(raw_line):
            in_fence = not in_fence
            continue
        if in_fence or _is_agent_include_directive(raw_line):
            continue
        code_spans = _inline_code_spans(raw_line)
        supported_spans = _supported_citation_token_spans(raw_line)
        for match in _UNSUPPORTED_CITATION_TOKEN_RE.finditer(raw_line):
            if _span_contains(code_spans, match.start()):
                continue
            if _span_contains(supported_spans, match.start()):
                continue
            if not _is_bare_citation_candidate(raw_line, match):
                continue
            token = match.group(1)
            issues.append(
                LintIssue(
                    file=path,
                    line=lineno,
                    col=match.start() + 1,
                    check="unsupported-citation-syntax",
                    severity=severity_for("unsupported-citation-syntax", strict=strict),
                    message=(
                        f"unsupported citation syntax '@{token}' — v1 supports only [@{token}]; "
                        "rewrite prefixed/suppressed/bare forms"
                    ),
                    match=token,
                    byte_col=_utf8_byte_col(raw_line, match.start()),
                )
            )
    return issues


_INLINE_CODE_SPAN_RE = re.compile(r"`[^`]*`")
_SUPPORTED_CITATION_BLOCK_RE = re.compile(r"\[\s*@[^\]]*\]")
_SUPPORTED_CITATION_ITEM_RE = re.compile(r"\s*@([A-Za-z][A-Za-z0-9_:.-]*)")
_UNSUPPORTED_CITATION_TOKEN_RE = re.compile(r"@([A-Za-z][A-Za-z0-9_:-]*(?:\.[A-Za-z0-9_:-]+)*)")


def _inline_code_spans(line: str) -> list[tuple[int, int]]:
    return [match.span() for match in _INLINE_CODE_SPAN_RE.finditer(line)]


def _span_contains(spans: list[tuple[int, int]], index: int) -> bool:
    return any(start <= index < end for start, end in spans)


def _is_bare_citation_candidate(line: str, match: re.Match[str]) -> bool:
    at_index = match.start()
    if match.end() < len(line) and line[match.end()] == "/":
        return False
    if at_index > 0 and line[at_index - 1] == "'":
        return False
    if at_index <= 0:
        return True
    return not line[at_index - 1].isalnum()


def _supported_citation_token_spans(line: str) -> list[tuple[int, int]]:
    """Return spans for syntactically supported `@key` tokens in `[@...]` blocks."""
    spans: list[tuple[int, int]] = []
    for block in _SUPPORTED_CITATION_BLOCK_RE.finditer(line):
        inner_start = block.start() + 1
        inner = line[inner_start : block.end() - 1]
        item_start = 0
        for raw_item in inner.split(";"):
            item_match = _SUPPORTED_CITATION_ITEM_RE.match(raw_item)
            if item_match:
                rest = raw_item[item_match.end() :].strip()
                if not rest or rest.startswith(","):
                    absolute_start = inner_start + item_start + item_match.start()
                    absolute_end = inner_start + item_start + item_match.end()
                    spans.append((absolute_start, absolute_end))
            item_start += len(raw_item) + 1
    return spans


def _is_agent_include_directive(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith("@") and stripped.endswith(".md") and " " not in stripped


_DETECTORS: dict[str, Callable[..., list[LintIssue]]] = {
    "bare-author-year": detect_bare_author_year,
    "short-form-ids": detect_short_form_ids,
    "frontmatter-inline-gap": detect_frontmatter_inline_gaps,
    "numeric-anchor": detect_numeric_anchor,
    "unsupported-citation-syntax": detect_unsupported_citation_syntax,
}
_SCAN_DIRS = ("doc", "entities")
_SCAN_ROOT_FILES = ("README.md", "AGENTS.md", "CLAUDE.md")
_SKIP_DIRS = {".git", ".venv", "node_modules", "data", "__pycache__", "templates"}
_SKIP_RELATIVE_DIRS = {("doc", "explorations")}


def _collect_markdown_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for name in _SCAN_DIRS:
        sub = root / name
        if not sub.is_dir():
            continue
        for path in sub.rglob("*.md"):
            if any(part in _SKIP_DIRS for part in path.parts):
                continue
            rel_parts = path.relative_to(root).parts
            if any(rel_parts[: len(skip)] == skip for skip in _SKIP_RELATIVE_DIRS):
                continue
            files.append(path)
    for name in _SCAN_ROOT_FILES:
        candidate = root / name
        if candidate.is_file():
            files.append(candidate)
    return sorted(files)


def _archived_task_aliases(root: Path) -> dict[str, str]:
    """Map historical task short-forms (e.g. ``t075``) to a canonical task id.

    Archived tasks live only in ``tasks/archive.md``; the graph TaskAdapter
    deliberately skips that file, so archived IDs never reach the entity alias
    map and a prose mention of one would be flagged as a style violation. This
    reads the archive declarations directly so historical references stay green.
    Returns ``{}`` on any read error (the lint must not hard-fail).
    """
    try:
        from science_tool.refs import _load_task_ids  # noqa: PLC0415

        aliases: dict[str, str] = {}
        for num in _load_task_ids(root):
            canonical = f"task:t{num}"
            aliases[f"t{num}"] = canonical
            compact_num = num.lstrip("0").zfill(2)
            if compact_num != num:
                aliases[f"t{compact_num}"] = canonical
                aliases[f"T{compact_num}"] = canonical
        return aliases
    except Exception as exc:  # noqa: BLE001 - a lint must not hard-fail on read issues
        logger.warning("archived task aliases unavailable (%s)", exc)
        return {}


def build_short_form_resolver(root: Path) -> dict[str, str] | None:
    """Build an alias → canonical-id map for resolver-aware short-form-ids.

    A bare short form (e.g. ``h006``) that resolves through this map is an
    authored reference to a real entity, not a style violation. Returns ``None``
    and logs a warning if project sources can't be loaded — short-form-ids then
    falls back to deny-list-only behavior rather than failing the lint.

    Archived task IDs (from ``tasks/archive.md``) are merged in so prose
    references to retired tasks resolve too.
    """
    try:
        from science_tool.graph.sources import build_alias_map, load_project_sources

        sources = load_project_sources(root.resolve())
    except Exception as exc:  # noqa: BLE001 - a lint must not hard-fail on graph-load issues
        logger.warning("short-form-ids resolver unavailable (%s); falling back to deny-list only", exc)
        return None
    alias_map = build_alias_map(sources.entities, sources.manual_aliases)
    for alias, canonical in _archived_task_aliases(root.resolve()).items():
        alias_map.setdefault(alias, canonical)
    return alias_map


def scan_root(
    root: Path,
    *,
    checks: list[str] | None = None,
    strict: bool = False,
    anchor_patterns: list[str] | None = None,
    exclude_paths: list[str] | None = None,
    short_form_ids_deny: list[str] | None = None,
    resolver: dict[str, str] | None = None,
    bare_author_year_deny: list[str] | None = None,
    bib_surnames: set[str] | None = None,
) -> dict:
    """Scan a project tree and return ``{"counts": {check: N}, "hits": [...]}``.

    `resolver` (alias → canonical-id map) is forwarded to the short-form-ids
    detector so references that resolve to real entities are not flagged. Build
    it with `build_short_form_resolver(root)`.

    `bib_surnames` (lowercased author surnames from `references.bib`) and
    `bare_author_year_deny` are forwarded to the bare-author-year detector so it
    flags only mentions of papers actually in the bibliography (minus deny-listed
    residuals). Build the surnames with `science_tool.bibliography.load_bib_author_surnames`.
    """
    selected = checks or list(CHECKS)
    unknown = [c for c in selected if c not in _DETECTORS]
    if unknown:
        raise ValueError(f"unknown checks: {unknown!r}; known: {list(CHECKS)}")
    files = [
        path
        for path in _collect_markdown_files(root)
        if not _matches_excluded_path(root, path, exclude_paths or [])
    ]
    hits: list[LintIssue] = []
    for path in files:
        for check in selected:
            detector = _DETECTORS[check]
            if check == "numeric-anchor":
                hits.extend(detector(path, strict=strict, anchor_patterns=anchor_patterns))
            elif check == "short-form-ids":
                hits.extend(detector(path, strict=strict, deny=short_form_ids_deny, resolver=resolver))
            elif check == "frontmatter-inline-gap":
                hits.extend(detector(path, strict=strict, alias_map=resolver))
            elif check == "bare-author-year":
                hits.extend(detector(path, strict=strict, deny=bare_author_year_deny, bib_surnames=bib_surnames))
            else:
                hits.extend(detector(path, strict=strict))
    counts: dict[str, int] = {}
    for hit in hits:
        counts[hit.check] = counts.get(hit.check, 0) + 1
    return {"counts": counts, "hits": hits}


def _matches_excluded_path(root: Path, path: Path, patterns: list[str]) -> bool:
    if not patterns:
        return False
    try:
        rel = path.relative_to(root).as_posix()
    except ValueError:
        rel = path.as_posix()
    return any(fnmatch(rel, pattern) for pattern in patterns)

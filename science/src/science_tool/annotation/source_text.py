"""Phase 1: the `.source.md` anchor surface.

Resolve a pmid|doi to an existing paper entity, acquire its article text
(PubTator3 BioC abstract preferred, Europe PMC abstract fallback), license-gate
full-text persistence, and render a `<citekey>.source.md` artifact carrying a
verifiable per-passage character-offset map plus provenance frontmatter.

Network I/O reuses paper_fetch's injectable httpx.Client + RateLimiter + FetchConfig
so callers (and tests) control every request.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from science_tool.commons.frontmatter import raw_frontmatter
from science_tool.commons.promote import PROMOTE_KIND_PAPER
from science_tool.paper_fetch import normalize_doi, normalize_pmid


class SourceTextError(ValueError):
    """Raised for user-correctable persist-source errors (fail-loud)."""


# Pinned PubTator3 API release marker used when the BioC payload omits one.
PUBTATOR3_API_VERSION = "pubtator3-api"


@dataclass(frozen=True)
class Passage:
    """One BioC passage: its section, BioC char offset, and raw decoded text.

    `text` is the raw UTF-8-decoded BioC string, NOT Unicode-normalized: PubTator
    offsets only align with the text BioC returns, so applying NFC here could
    shift character indices and silently mis-anchor later selectors.
    """

    section: str
    bioc_offset: int
    text: str


@dataclass(frozen=True)
class SourcePassages:
    passages: tuple[Passage, ...]
    release: str


def parse_bioc_passages(record: dict[str, Any]) -> SourcePassages | None:
    """Parse a PubTator3 BioC JSON record into ordered passages.

    Accepts either the `PubTator3` or `documents` top-level key. Returns None when
    the record carries no usable passages.
    """
    docs = record.get("PubTator3") or record.get("documents")
    if not isinstance(docs, list) or not docs:
        return None
    doc = docs[0]
    if not isinstance(doc, dict):
        return None
    raw_passages = doc.get("passages")
    if not isinstance(raw_passages, list):
        return None

    passages: list[Passage] = []
    for raw in raw_passages:
        if not isinstance(raw, dict):
            continue
        text = raw.get("text")
        offset = raw.get("offset")
        if not isinstance(text, str) or not text or not isinstance(offset, int):
            continue
        ri = raw.get("infons")
        infons = ri if isinstance(ri, dict) else {}
        section = str(infons.get("type") or "passage")
        passages.append(Passage(section=section, bioc_offset=offset, text=text))

    if not passages:
        return None

    di = doc.get("infons")
    doc_infons = di if isinstance(di, dict) else {}
    release = str(doc_infons.get("_release") or "") or PUBTATOR3_API_VERSION
    return SourcePassages(passages=tuple(passages), release=release)


# Sidecar artifacts that must not be mistaken for paper-entity markdown.
_SIDECAR_SUFFIXES = (".source.md",)


@dataclass(frozen=True)
class ResolvedPaper:
    citekey: str
    path: Path
    directory: Path
    doi: str | None  # normalized doi from the entity frontmatter (may differ from the input)
    pmid: str | None  # normalized pmid from the entity frontmatter


def _paper_dirs(project_root: Path) -> list[Path]:
    """Directories that may hold paper-entity markdown in this project.

    `resolve_path_policy("paper")` is NOT usable here: `paper` is a builtin kind, so
    the policy table always returns `entities/papers` (builtins win the merge in
    `entity_policies`, and a project-local `papers` home is rejected as a core-dir
    collision). Real checkouts store paper summaries under any of the canonical
    paper subdirs — this meta checkout uses `doc/background/papers/`. Reuse the one
    authoritative list (`PROMOTE_KIND_PAPER.source_subdirs`) so resolution and
    promotion never diverge.
    """
    return [project_root / sub for sub in PROMOTE_KIND_PAPER.source_subdirs]


def _as_str(value: Any) -> str | None:
    # pmid/doi may parse as int from YAML (e.g. `pmid: 123456`); stringify for the normalizers.
    if value is None:
        return None
    if isinstance(value, (int, str)):
        return str(value)
    return None


def resolve_paper_entity(
    project_root: Path, *, doi: str | None, pmid: str | None
) -> ResolvedPaper:
    """Map a pmid|doi to the paper entity (citekey + directory).

    Scans paper-entity frontmatter under the kind's resolved home, matching a
    normalized doi/pmid. No match -> SourceTextError (actionable). Two entities
    claiming the same identifier -> SourceTextError naming both files.
    """
    want_doi = normalize_doi(doi)
    want_pmid = normalize_pmid(pmid)
    if not want_doi and not want_pmid:
        raise SourceTextError(
            "persist-source requires a DOI or PMID to resolve a paper entity."
        )

    # Each match carries the entity's own normalized identifiers so acquisition can
    # use the entity's PMID even when the user invoked persist-source with a DOI.
    paper_dirs = _paper_dirs(project_root)
    matches: list[tuple[Path, str | None, str | None]] = []
    for root in paper_dirs:
        if not root.is_dir():
            continue
        for path in sorted(root.glob("*.md")):
            if any(path.name.endswith(sfx) for sfx in _SIDECAR_SUFFIXES):
                continue
            fm = raw_frontmatter(path)
            entity_doi = normalize_doi(_as_str(fm.get("doi")))
            entity_pmid = normalize_pmid(_as_str(fm.get("pmid")))
            if (want_doi and entity_doi == want_doi) or (
                want_pmid and entity_pmid == want_pmid
            ):
                matches.append((path, entity_doi, entity_pmid))

    ident = want_doi or want_pmid
    if not matches:
        searched = ", ".join(str(d) for d in paper_dirs)
        raise SourceTextError(
            f"no paper entity has doi/pmid {ident!r} under any of {searched}; "
            "run `science paper-fetch` and create the paper entity first."
        )
    if len(matches) > 1:
        named = ", ".join(str(m[0]) for m in matches)
        raise SourceTextError(
            f"multiple paper entities claim doi/pmid {ident!r}: {named}. "
            "This is a data error; fix the duplicate before persisting source text."
        )
    path, entity_doi, entity_pmid = matches[0]
    return ResolvedPaper(
        citekey=path.stem, path=path, directory=path.parent, doi=entity_doi, pmid=entity_pmid
    )


# Full-text persistence whitelist. Verbatim license strings are normalized to a
# canonical token (uppercased, spaces/underscores -> hyphens, version stripped)
# before membership testing; versioned forms (CC-BY-4.0) therefore match.
# Permissiveness order: CC0 > CC-BY > CC-BY-SA > CC-BY-ND (more restrictive last).
LICENSE_WHITELIST: tuple[str, ...] = ("CC0", "CC-BY", "CC-BY-SA", "CC-BY-ND")

_LICENSE_PERMISSIVENESS: dict[str, int] = {
    "CC0": 0,
    "CC-BY": 1,
    "CC-BY-SA": 2,
    "CC-BY-ND": 3,
}
_VERSION_SUFFIX = re.compile(r"-\d+(?:\.\d+)*$")


def normalize_license_token(raw: str | None) -> str:
    """Canonical token for whitelist comparison (NOT the persisted value)."""
    if not raw:
        return ""
    token = raw.strip().upper().replace("_", "-").replace(" ", "-")
    token = re.sub(r"-{2,}", "-", token).strip("-")
    token = _VERSION_SUFFIX.sub("", token)
    return token


def is_whitelisted(raw: str | None) -> bool:
    return normalize_license_token(raw) in LICENSE_WHITELIST


def resolve_license(candidates: list[str | None]) -> tuple[str, bool]:
    """Resolve a license from OA-source candidate strings.

    Returns ``(license, whitelisted)``: the most-permissive whitelisted candidate
    (verbatim) when any qualifies, else the first non-empty raw value (for
    provenance) or ``"unknown"``. ``whitelisted`` gates full-text persistence.
    """
    whitelisted = [c for c in candidates if c and is_whitelisted(c)]
    if whitelisted:
        best = min(whitelisted, key=lambda c: _LICENSE_PERMISSIVENESS[normalize_license_token(c)])
        return best.strip(), True
    for c in candidates:
        if c and c.strip():
            return c.strip(), False
    return "unknown", False


@dataclass(frozen=True)
class PassageOffset:
    """Where one passage body sits in the *rendered* `.source.md` file.

    `file_char_base` is the absolute character index (Python str index) into the
    full rendered file at which this passage's verbatim text begins; `length` is
    its character count. Slicing the file at [base, base+length) reproduces the
    passage text exactly. Phase 2 maps a BioC (passage, local_char_offset) to an
    absolute file index via `file_char_base + local_char_offset`, then computes
    prefix/suffix windows clamped to [base, base+length) so they never cross a
    heading or passage boundary.
    """

    section: str
    file_char_base: int
    length: int


@dataclass(frozen=True)
class RenderedSource:
    text: str
    offset_map: tuple[PassageOffset, ...]
    text_sha256: str


def verify_offset_map(
    file_text: str, offset_map: list[PassageOffset], passages: SourcePassages
) -> None:
    """Slice-verify: every map entry must reproduce its source passage text.

    Raises SourceTextError (fail-early) on any mismatch — never a silently
    mis-placed anchor. Pairs entries to passages positionally (render order is
    preserved 1:1).
    """
    entries = list(offset_map)
    if len(entries) != len(passages.passages):
        raise SourceTextError(
            f"offset map has {len(entries)} entries but {len(passages.passages)} passages"
        )
    for off, passage in zip(entries, passages.passages, strict=True):
        sliced = file_text[off.file_char_base : off.file_char_base + off.length]
        if sliced != passage.text:
            raise SourceTextError(
                f"offset-map mismatch for section {off.section!r}: "
                f"rendered slice {sliced!r} != BioC passage text {passage.text!r}"
            )


# Section -> rendered heading. "title" + "abstract" go under "## Abstract";
# any full-text sections render under "## Full Text".
_ABSTRACT_SECTIONS = frozenset({"title", "abstract"})


def render_source_md(
    *,
    citekey: str,
    passages: SourcePassages,
    retrieved_from: str,
    license_: str,
    pmid: str | None,
    doi: str | None,
    fulltext: SourcePassages | None,
    fulltext_omitted_reason: str | None = None,
) -> RenderedSource:
    """Render `<citekey>.source.md` and the matching per-passage offset map.

    Body layout (offsets index ONLY passage bodies, never frontmatter/headings):

        ---
        <frontmatter>
        ---

        ## Abstract

        <title passage text>

        <abstract passage text>

        ## Full Text   (only when fulltext is not None)

        <full-text passage text...>

    Each passage body is written verbatim on its own block, preceded by a blank
    line, so no passage body abuts a heading; offsets are recomputed against the
    fully rendered string (including frontmatter) so they are absolute file
    indices.
    """
    # ---- Build the body region (everything after the closing frontmatter fence)
    body_lines: list[str] = []
    # Track (section, char_offset_within_body, length) while building.
    rel_offsets: list[tuple[str, int, int]] = []

    def _emit_section(heading: str, items: list[Passage]) -> None:
        if not items:
            return
        body_lines.append(f"## {heading}")
        body_lines.append("")
        for p in items:
            # char offset of this passage = length of the body text emitted so far.
            so_far = "\n".join(body_lines)
            base = len(so_far) + (1 if so_far else 0)  # +1 for the join newline before this line
            body_lines.append(p.text)
            rel_offsets.append((p.section, base, len(p.text)))
            body_lines.append("")  # blank separator

    abstract_items = [p for p in passages.passages]
    fulltext_items = list(fulltext.passages) if fulltext is not None else []
    _emit_section("Abstract", abstract_items)
    if fulltext_items:
        _emit_section("Full Text", fulltext_items)

    body = "\n".join(body_lines).rstrip("\n") + "\n"
    text_sha256 = hashlib.sha256(body.encode("utf-8")).hexdigest()

    # 2) Render frontmatter (Task 5 fills the full set; here just enough to render).
    fm = _build_frontmatter(
        retrieved_from=retrieved_from,
        source_release=passages.release,
        license_=license_,
        text_sha256=text_sha256,
        pmid=pmid,
        doi=doi,
        offsets=rel_offsets,  # recomputed to absolute below before serialization
        fulltext_omitted_reason=fulltext_omitted_reason,
        body_offset=0,  # patched after we know header length
    )
    header = "---\n" + yaml.safe_dump(fm, sort_keys=False, allow_unicode=True) + "---\n\n"
    header_len = len(header)

    # 3) Recompute absolute offsets and patch the frontmatter map.
    offset_map = tuple(
        PassageOffset(section=sec, file_char_base=header_len + rel, length=length)
        for (sec, rel, length) in rel_offsets
    )
    fm["passages"] = [
        {"section": o.section, "file_char_base": o.file_char_base, "length": o.length}
        for o in offset_map
    ]
    header = "---\n" + yaml.safe_dump(fm, sort_keys=False, allow_unicode=True) + "---\n\n"
    # Header length must be stable across the patch (we only replaced a placeholder
    # list with the real one); recompute and assert no drift, else fail loud.
    if len(header) != header_len:
        # The map serialization changed the header length; re-derive once more.
        header_len2 = len(header)
        offset_map = tuple(
            PassageOffset(section=sec, file_char_base=header_len2 + rel, length=length)
            for (sec, rel, length) in rel_offsets
        )
        fm["passages"] = [
            {"section": o.section, "file_char_base": o.file_char_base, "length": o.length}
            for o in offset_map
        ]
        header = "---\n" + yaml.safe_dump(fm, sort_keys=False, allow_unicode=True) + "---\n\n"
        if len(header) != header_len2:
            raise SourceTextError("offset-map serialization did not converge; refusing to write")

    text = header + body
    return RenderedSource(text=text, offset_map=offset_map, text_sha256=text_sha256)


def _build_frontmatter(
    *,
    retrieved_from: str,
    source_release: str,
    license_: str,
    text_sha256: str,
    pmid: str | None,
    doi: str | None,
    offsets: list[tuple[str, int, int]],
    fulltext_omitted_reason: str | None,
    body_offset: int,
) -> dict[str, Any]:
    fm: dict[str, Any] = {
        "kind": "paper-source",
        "retrieved_from": retrieved_from,
        # PubTator3 data release (or pinned API marker) the text was drawn from —
        # provenance/reproducibility; Phase 2 may re-query but records the basis.
        "source_release": source_release,
        "license": license_,
        "text_sha256": text_sha256,
    }
    if doi:
        fm["doi"] = doi
    if pmid:
        fm["pmid"] = pmid
    if fulltext_omitted_reason:
        fm["fulltext_omitted_reason"] = fulltext_omitted_reason
    fm["passages"] = [
        {"section": sec, "file_char_base": body_offset + rel, "length": length}
        for (sec, rel, length) in offsets
    ]
    return fm

# Sub-Article Annotation — Phase 1: Source-Text Anchor Surface — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a `science paper persist-source <pmid|doi>` CLI command that resolves an identifier to an existing paper entity, acquires the article text (PubTator3 BioC abstract preferred, Europe PMC abstract fallback), license-gates full-text persistence, and writes a `<citekey>.source.md` artifact next to the paper entity containing the abstract (always), the full text (best-effort — when the PubTator3 BioC record supplies body passages **and** the license is whitelisted), a verifiable per-passage character-offset map, and provenance frontmatter (`retrieved_from`, `source_release`, `license`, `text_sha256`, `pmid`/`doi`, `fulltext_omitted_reason`). This is the *anchor surface* the later seeder/agent/promotion phases consume — and it must round-trip and ship on its own with zero dependency on annotations.

**Architecture:** A new focused module `science/src/science_tool/annotation/source_text.py` holds the pure, testable core (identifier→entity resolver, license resolution/whitelist, BioC parsing into passages, offset-map construction + slice-verification, and the `.source.md` renderer). Network I/O reuses `paper_fetch.py`'s injectable-`httpx.Client` + `RateLimiter` + `FetchConfig` pattern exactly (so tests use `httpx.MockTransport`). A thin `persist-source` Click command in `cli.py` wires resolver → acquisition → license gate → writer, mirroring `paper-fetch`. The module lives under `annotation/` because the offset map it produces is consumed by the Phase-2 annotation seeder/verifier and the `oa:TextQuoteSelector` machinery in `annotation/verify.py` / `annotation/selector.py`; placing it there keeps the anchor-surface logic beside its only consumers and keeps `paper_fetch.py` (already ~1000 lines, tier-orchestration focused) from bloating.

**Tech Stack:** Python 3.13, Click, httpx, pytest, uv workspace.

---

## Conventions

- This repo is a **uv workspace**. The tool package lives in the `science/` subdirectory.
- **Run tests from `science/`:** `cd science && uv run --frozen pytest <path> -v`. Never run pytest from the repo root.
- **Tool code** under `science/src/science_tool/`; **tests** under `science/tests/`.
- **Commits from the repo root** (the directory above `science/`), staging with `git add science/...`. Do **not** add a `Co-Authored-By` trailer to commits in this plan.
- In doc prose, refer to paths under the meta checkout as `~/d/science/...` (this checkout stores paper summaries at `~/d/science/meta/doc/background/papers/`, which is exactly why the resolver scans the canonical paper subdirs — `entities/papers`, `doc/papers`, `doc/background/papers` — instead of the single path-policy root `entities/papers/`, which builtins pin and a project cannot override).
- **Hermetic tests only:** every `httpx` call goes through an injected `httpx.Client` built with `httpx.MockTransport` (mirror `_make_client` in `test_paper_fetch.py`); every filesystem operation is under `tmp_path`. No test touches the network or the real home directory.
- All new public functions are **pure where possible** (operate on passed-in data / a `tmp_path` project dir), so they are unit-testable without the CLI.

## File Structure

| File | Responsibility | Task(s) |
|------|----------------|---------|
| `science/src/science_tool/annotation/source_text.py` | **New.** Pure core + acquisition: `resolve_paper_entity`, `resolve_license`/`is_whitelisted`, `parse_bioc_passages`, `Passage`/`SourcePassages`, `build_offset_map`/`verify_offset_map`, `render_source_md`, and the network-facing `acquire_source_text` (injectable `httpx.Client`). | 1–6 |
| `science/tests/test_source_text.py` | **New.** Unit + integration tests for every function above; `MockTransport` for network, `tmp_path` for filesystem. Mirrors `test_paper_fetch.py` idioms (`_make_client`, `_cfg`). | 1–6 |
| `science/src/science_tool/cli.py` (modify, after `paper_fetch_cmd` at ~4600) | **New `persist-source` command** wiring resolver → acquisition → license gate → writer; mirrors `paper-fetch` option/`FetchConfig`/email pattern. | 7 |
| `science/tests/test_cli_persist_source.py` | **New.** `CliRunner` end-to-end test of `persist-source` with `tmp_path` project + `MockTransport` (injected via a seam). | 7 |
| `docs/conventions/annotation-tokens.md` | **Modify (append).** File already exists (marker-token conventions). Append a full-text **license whitelist** section. | 3 |
| `science/src/science_tool/graph/storage_adapters/markdown.py` (modify, `discover` ~27-42) | Exclude `*.source.md` sidecars from entity ingestion (they live inside entity roots but are not entities). | 8 |

---

## Task 1 — Identifier → paper-entity resolver

Resolve a `pmid|doi` to the paper entity (citekey + directory) by scanning paper-entity frontmatter, normalizing via `normalize_doi`/`normalize_pmid`. No-match fails loud with an actionable message; multi-match fails loud naming both files. Pure: operates over a project directory.

**Files**
- Create: `science/src/science_tool/annotation/source_text.py`
- Create: `science/tests/test_source_text.py`

**Steps**

- [ ] **1.1 Write the failing test.** In `science/tests/test_source_text.py`:

```python
"""Tests for the .source.md anchor-surface module (Phase 1)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import httpx
import pytest

from science_tool.annotation.source_text import (
    ResolvedPaper,
    SourceTextError,
    resolve_paper_entity,
)


def _make_client(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def _write_paper(
    project_root: Path, citekey: str, *, doi: str = "", pmid: str = "",
    subdir: str = "entities/papers",
) -> Path:
    papers_dir = project_root / subdir
    papers_dir.mkdir(parents=True, exist_ok=True)
    path = papers_dir / f"{citekey}.md"
    fm = [f"id: paper:{citekey}", f"title: {citekey}"]
    if doi:
        fm.append(f"doi: {doi}")
    if pmid:
        fm.append(f'pmid: "{pmid}"')
    path.write_text("---\n" + "\n".join(fm) + "\n---\n\n## Key Findings\n\nx\n", encoding="utf-8")
    return path


class TestResolvePaperEntity:
    def test_resolves_by_doi_case_insensitive(self, tmp_path: Path) -> None:
        path = _write_paper(tmp_path, "Smith2024", doi="10.1038/Foo-1")
        resolved = resolve_paper_entity(tmp_path, doi="https://doi.org/10.1038/foo-1", pmid=None)
        assert resolved == ResolvedPaper(
            citekey="Smith2024", path=path, directory=path.parent, doi="10.1038/foo-1", pmid=None
        )

    def test_resolves_by_pmid(self, tmp_path: Path) -> None:
        path = _write_paper(tmp_path, "Jones2025", pmid="123456")
        resolved = resolve_paper_entity(tmp_path, doi=None, pmid="123456")
        assert resolved.citekey == "Jones2025"
        assert resolved.path == path

    def test_resolves_paper_under_doc_background_papers(self, tmp_path: Path) -> None:
        # Real checkouts (this meta repo) store paper summaries outside entities/papers;
        # the resolver must scan every canonical paper subdir, not the policy root.
        path = _write_paper(
            tmp_path, "Meta2026", doi="10.1/meta", subdir="doc/background/papers"
        )
        resolved = resolve_paper_entity(tmp_path, doi="10.1/meta", pmid=None)
        assert resolved.path == path
        assert resolved.directory == tmp_path / "doc" / "background" / "papers"

    def test_carries_entity_pmid_when_resolved_by_doi(self, tmp_path: Path) -> None:
        # Core of the resolver→acquisition contract: a DOI-invoked resolve still
        # surfaces the entity's PMID, so acquisition can prefer PubTator.
        _write_paper(tmp_path, "Smith2024", doi="10.1038/foo-1", pmid="123456")
        resolved = resolve_paper_entity(tmp_path, doi="10.1038/foo-1", pmid=None)
        assert resolved.doi == "10.1038/foo-1"
        assert resolved.pmid == "123456"

    def test_no_match_fails_loud(self, tmp_path: Path) -> None:
        _write_paper(tmp_path, "Smith2024", doi="10.1038/foo-1")
        with pytest.raises(SourceTextError) as exc:
            resolve_paper_entity(tmp_path, doi="10.9999/missing", pmid=None)
        msg = str(exc.value)
        assert "no paper entity" in msg
        assert "10.9999/missing" in msg
        assert "paper-fetch" in msg

    def test_multi_match_fails_loud_naming_both(self, tmp_path: Path) -> None:
        a = _write_paper(tmp_path, "Aaa2024", doi="10.1/dup")
        b = _write_paper(tmp_path, "Bbb2024", doi="10.1/dup")
        with pytest.raises(SourceTextError) as exc:
            resolve_paper_entity(tmp_path, doi="10.1/dup", pmid=None)
        msg = str(exc.value)
        assert str(a) in msg and str(b) in msg

    def test_requires_an_identifier(self, tmp_path: Path) -> None:
        with pytest.raises(SourceTextError):
            resolve_paper_entity(tmp_path, doi=None, pmid=None)
```

- [ ] **1.2 Run it — expect failure** (module does not exist yet):
  `cd science && uv run --frozen pytest tests/test_source_text.py -v`
  Expected: `ModuleNotFoundError: No module named 'science_tool.annotation.source_text'` (collection error).

- [ ] **1.3 Minimal implementation.** Create `science/src/science_tool/annotation/source_text.py`:

```python
"""Phase 1: the `.source.md` anchor surface.

Resolve a pmid|doi to an existing paper entity, acquire its article text
(PubTator3 BioC abstract preferred, Europe PMC abstract fallback), license-gate
full-text persistence, and render a `<citekey>.source.md` artifact carrying a
verifiable per-passage character-offset map plus provenance frontmatter.

Network I/O reuses paper_fetch's injectable httpx.Client + RateLimiter + FetchConfig
so callers (and tests) control every request.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from science_tool.commons.frontmatter import raw_frontmatter
from science_tool.commons.promote import PROMOTE_KIND_PAPER
from science_tool.paper_fetch import normalize_doi, normalize_pmid


class SourceTextError(ValueError):
    """Raised for user-correctable persist-source errors (fail-loud)."""


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
        named = ", ".join(str(p) for p, _d, _p in matches)
        raise SourceTextError(
            f"multiple paper entities claim doi/pmid {ident!r}: {named}. "
            "This is a data error; fix the duplicate before persisting source text."
        )
    path, entity_doi, entity_pmid = matches[0]
    return ResolvedPaper(
        citekey=path.stem, path=path, directory=path.parent, doi=entity_doi, pmid=entity_pmid
    )


def _as_str(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (int, str)):
        return str(value)
    return None
```

- [ ] **1.4 Run it — expect pass:**
  `cd science && uv run --frozen pytest tests/test_source_text.py -v`
  Expected: 7 passed.

- [ ] **1.5 Commit** (from repo root):
  `git add science/src/science_tool/annotation/source_text.py science/tests/test_source_text.py`
  `git commit -m "persist-source: identifier->paper-entity resolver"`

---

## Task 2 — BioC passage parsing

Parse a PubTator3 BioC JSON record into ordered passages (section + raw decoded text), the raw basis for the offset map. No network here — pure parsing of a dict.

**Files**
- Modify: `science/src/science_tool/annotation/source_text.py` (add `Passage`, `SourcePassages`, `parse_bioc_passages`)
- Modify: `science/tests/test_source_text.py` (add `TestParseBiocPassages`)

**Steps**

- [ ] **2.1 Write the failing test.** Add to `science/tests/test_source_text.py`:

```python
from science_tool.annotation.source_text import (  # noqa: E402  (append to existing import)
    Passage,
    SourcePassages,
    parse_bioc_passages,
)


# Representative PubTator3 BioC abstract record: title + abstract passages, with a
# multi-codepoint character to exercise character-offset (not byte) handling.
_BIOC_RECORD = {
    "PubTator3": [
        {
            "id": "123456",
            "infons": {"_release": "2024.01"},
            "passages": [
                {"offset": 0, "text": "BRCA1 in cancer", "infons": {"type": "title"}},
                {
                    "offset": 16,
                    "text": "We show BRCA1 drives tumours — clearly.",
                    "infons": {"type": "abstract", "section_type": "ABSTRACT"},
                },
            ],
        }
    ]
}


class TestParseBiocPassages:
    def test_parses_title_and_abstract_in_order(self) -> None:
        parsed = parse_bioc_passages(_BIOC_RECORD)
        assert parsed.release == "2024.01"
        assert parsed.passages == (
            Passage(section="title", bioc_offset=0, text="BRCA1 in cancer"),
            Passage(
                section="abstract",
                bioc_offset=16,
                text="We show BRCA1 drives tumours — clearly.",
            ),
        )

    def test_documents_key_is_accepted(self) -> None:
        record = {"documents": _BIOC_RECORD["PubTator3"]}
        parsed = parse_bioc_passages(record)
        assert parsed.passages[0].text == "BRCA1 in cancer"

    def test_release_falls_back_to_constant_when_absent(self) -> None:
        record = {"PubTator3": [{"passages": [{"offset": 0, "text": "t", "infons": {"type": "title"}}]}]}
        parsed = parse_bioc_passages(record)
        assert parsed.release  # non-empty pinned constant

    def test_returns_none_for_empty_record(self) -> None:
        assert parse_bioc_passages({"PubTator3": []}) is None
        assert parse_bioc_passages({}) is None
        assert parse_bioc_passages({"PubTator3": [{"passages": []}]}) is None
```

- [ ] **2.2 Run it — expect failure:**
  `cd science && uv run --frozen pytest tests/test_source_text.py::TestParseBiocPassages -v`
  Expected: `ImportError: cannot import name 'Passage'`.

- [ ] **2.3 Minimal implementation.** Add to `source_text.py` (near the top, after `SourceTextError`):

```python
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
        infons = raw.get("infons") if isinstance(raw.get("infons"), dict) else {}
        section = str(infons.get("type") or "passage")
        passages.append(Passage(section=section, bioc_offset=offset, text=text))

    if not passages:
        return None

    doc_infons = doc.get("infons") if isinstance(doc.get("infons"), dict) else {}
    release = str(doc_infons.get("_release") or "") or PUBTATOR3_API_VERSION
    return SourcePassages(passages=tuple(passages), release=release)
```

- [ ] **2.4 Run it — expect pass:**
  `cd science && uv run --frozen pytest tests/test_source_text.py::TestParseBiocPassages -v`
  Expected: 4 passed.

- [ ] **2.5 Commit:**
  `git add science/src/science_tool/annotation/source_text.py science/tests/test_source_text.py`
  `git commit -m "persist-source: parse PubTator3 BioC passages (raw, un-normalized)"`

---

## Task 3 — License resolution + whitelist (and conventions doc)

Pure `is_whitelisted(...)` + `resolve_license(...)`. Whitelist `CC0`, `CC-BY`, `CC-BY-SA`, `CC-BY-ND` and versioned forms (`CC-BY-4.0`). Resolve from candidate values; most-permissive whitelisted value wins, else `unknown`. **Phase 1 source of candidates: Europe PMC `license` only.** `_try_unpaywall` (`paper_fetch.py:412`) returns `oa_locations[].license` but does not currently extract it, so Unpaywall is NOT a candidate source in Phase 1 — `resolve_license` takes a generic candidate list so an Unpaywall license can be added later without an interface change.

**Files**
- Modify: `science/src/science_tool/annotation/source_text.py` (add `normalize_license_token`, `is_whitelisted`, `resolve_license`, `LICENSE_WHITELIST`)
- Modify: `science/tests/test_source_text.py` (add `TestLicense`)
- Modify: `docs/conventions/annotation-tokens.md` (**append** a license-whitelist section — the file already exists with marker-token conventions; do NOT overwrite it)

**Steps**

- [ ] **3.1 Write the failing test.** Add:

```python
from science_tool.annotation.source_text import (  # noqa: E402
    is_whitelisted,
    resolve_license,
)


class TestLicense:
    @pytest.mark.parametrize(
        "raw",
        ["CC0", "cc-by", "CC BY", "CC-BY-4.0", "cc-by-sa-3.0", "CC-BY-ND", "CC BY 4.0"],
    )
    def test_whitelisted_values(self, raw: str) -> None:
        assert is_whitelisted(raw) is True

    @pytest.mark.parametrize("raw", ["CC-BY-NC", "CC-BY-NC-4.0", "all-rights-reserved", "", "unknown", "  "])
    def test_non_whitelisted_values(self, raw: str) -> None:
        assert is_whitelisted(raw) is False

    def test_resolve_returns_verbatim_whitelisted_value(self) -> None:
        # Most-permissive whitelisted wins; the raw verbatim form is returned.
        license_, ok = resolve_license(["CC-BY-NC", "CC-BY-4.0"])
        assert ok is True
        assert license_ == "CC-BY-4.0"

    def test_resolve_prefers_more_permissive(self) -> None:
        license_, ok = resolve_license(["CC-BY-ND", "CC-BY"])
        assert ok is True
        assert license_ == "CC-BY"

    def test_resolve_unknown_when_none_whitelisted(self) -> None:
        license_, ok = resolve_license(["CC-BY-NC", "all-rights-reserved"])
        assert ok is False
        assert license_ == "CC-BY-NC"  # raw value retained for provenance

    def test_resolve_unknown_when_no_candidates(self) -> None:
        license_, ok = resolve_license([None, "", "  "])
        assert ok is False
        assert license_ == "unknown"
```

- [ ] **3.2 Run it — expect failure:**
  `cd science && uv run --frozen pytest tests/test_source_text.py::TestLicense -v`
  Expected: `ImportError: cannot import name 'is_whitelisted'`.

- [ ] **3.3 Minimal implementation.** Add to `source_text.py`:

```python
import re

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
```

- [ ] **3.4 Run it — expect pass:**
  `cd science && uv run --frozen pytest tests/test_source_text.py::TestLicense -v`
  Expected: tests pass (15 parametrized + cases).

- [ ] **3.5 Append to the conventions doc.** `docs/conventions/annotation-tokens.md` **already exists** (marker-token conventions, with `id: convention:annotation-tokens` frontmatter). Do NOT overwrite it — append the following section to the end of the file (and bump the frontmatter `updated:` date to today):

```markdown

## Full-text license whitelist (Phase 1 — source-text persistence)

`<citekey>.source.md` persists full text only when the resolved license is on
this whitelist. The persisted `license` frontmatter field records the raw value
verbatim; the canonical token below is used only for membership testing
(uppercased, spaces/underscores → hyphens, version suffix stripped).

| Canonical token | Versioned forms accepted | Persist full text? |
|-----------------|--------------------------|--------------------|
| `CC0`           | `CC0-1.0`                | yes |
| `CC-BY`         | `CC-BY-4.0`, `CC-BY-3.0` | yes |
| `CC-BY-SA`      | `CC-BY-SA-4.0`           | yes |
| `CC-BY-ND`      | `CC-BY-ND-4.0`           | yes |
| anything else (incl. `CC-BY-NC*`, `unknown`, absent) | — | **no** — abstract only; `fulltext_omitted_reason` is `license-not-whitelisted` when full text existed, else `no-fulltext-available` |

License is resolved from Europe PMC `license` in Phase 1 (Unpaywall's `oa_locations[].license` is deferred, with EPMC license the Phase 1 primary); with multiple values the most-permissive whitelisted one
wins, else `unknown`.

> Annotation-type and source-prefix vocabularies (e.g. `entity-gene`,
> `pubtator3:<release>:seeder-vN`) are introduced in Phase 2+; only the license
> whitelist is in scope for Phase 1.
```

- [ ] **3.6 Commit:**
  `git add science/src/science_tool/annotation/source_text.py science/tests/test_source_text.py docs/conventions/annotation-tokens.md`
  `git commit -m "persist-source: license whitelist + resolution; conventions doc"`

---

## Task 4 — Offset map construction + slice-verification

Given the persisted body and the source passages, build a per-passage offset map keyed to the **rendered file** (absolute character base of each passage body within the final `.source.md`), and verify by slicing. The map's invariant: slicing the rendered file at `[file_char_base, file_char_base + length)` reproduces the passage's raw text exactly, and `prefix`/`suffix` windows never cross a heading or passage boundary. This is what lets Phase 2 convert a BioC `(passage, local_char_offset)` into an absolute file slice the standard verifier (`annotation/verify.py::_load_source`, which reads the whole file) can re-anchor.

**Files**
- Modify: `science/src/science_tool/annotation/source_text.py` (add `PassageOffset`, `render_source_md` returning body+map, `verify_offset_map`)
- Modify: `science/tests/test_source_text.py` (add `TestOffsetMap`)

Note: `render_source_md` both renders the file and emits the offset map in one pass, so the map and the rendered bytes can never drift.

**Steps**

- [ ] **4.1 Write the failing test.** Add:

```python
from science_tool.annotation.source_text import (  # noqa: E402
    PassageOffset,
    RenderedSource,
    render_source_md,
    verify_offset_map,
)


class TestOffsetMap:
    def _passages(self) -> SourcePassages:
        return SourcePassages(
            passages=(
                Passage(section="title", bioc_offset=0, text="BRCA1 in cancer"),
                Passage(section="abstract", bioc_offset=16, text="We show BRCA1 drives tumours — clearly."),
            ),
            release="2024.01",
        )

    def test_offsets_slice_back_to_passage_text(self) -> None:
        rendered = render_source_md(
            citekey="Smith2024",
            passages=self._passages(),
            retrieved_from="pubtator3",
            license_="CC-BY-4.0",
            pmid="123456",
            doi="10.1038/foo-1",
            fulltext=None,
        )
        file_text = rendered.text
        # Entries are positional 1:1 with passages (render order preserved).
        for off, src in zip(rendered.offset_map, self._passages().passages, strict=True):
            sliced = file_text[off.file_char_base : off.file_char_base + off.length]
            assert off.section == src.section
            assert sliced == src.text

    def test_offset_base_is_character_not_byte(self) -> None:
        # The em dash (U+2014) is 3 bytes but 1 character; offsets must stay in chars.
        rendered = render_source_md(
            citekey="Smith2024",
            passages=self._passages(),
            retrieved_from="pubtator3",
            license_="CC-BY-4.0",
            pmid=None,
            doi="10.1038/foo-1",
            fulltext=None,
        )
        abstract_off = next(o for o in rendered.offset_map if o.section == "abstract")
        sliced = rendered.text[abstract_off.file_char_base : abstract_off.file_char_base + abstract_off.length]
        assert "—" in sliced
        assert abstract_off.length == len("We show BRCA1 drives tumours — clearly.")

    def test_verify_offset_map_passes_on_self(self) -> None:
        rendered = render_source_md(
            citekey="Smith2024",
            passages=self._passages(),
            retrieved_from="pubtator3",
            license_="CC-BY-4.0",
            pmid=None,
            doi="10.1038/foo-1",
            fulltext=None,
        )
        # Must not raise: each map entry slices back to its source passage text.
        verify_offset_map(rendered.text, rendered.offset_map, self._passages())

    def test_verify_offset_map_raises_on_corruption(self) -> None:
        rendered = render_source_md(
            citekey="Smith2024",
            passages=self._passages(),
            retrieved_from="pubtator3",
            license_="CC-BY-4.0",
            pmid=None,
            doi="10.1038/foo-1",
            fulltext=None,
        )
        bad = [PassageOffset(section=o.section, file_char_base=o.file_char_base + 1, length=o.length) for o in rendered.offset_map]
        with pytest.raises(SourceTextError):
            verify_offset_map(rendered.text, bad, self._passages())
```

- [ ] **4.2 Run it — expect failure:**
  `cd science && uv run --frozen pytest tests/test_source_text.py::TestOffsetMap -v`
  Expected: `ImportError: cannot import name 'PassageOffset'`.

- [ ] **4.3 Minimal implementation.** Add to `source_text.py`. `render_source_md` is the single renderer (Task 5 reuses it for frontmatter); here implement it body-first so the offset map is exact, then Task 5 layers frontmatter on top using the same offsets.

```python
import hashlib

import yaml


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
```

Add `render_source_md` (used here and in Task 5). The body region (what offsets index) is the passage text written verbatim under its `##` heading, separated by blank lines so a passage body never touches a heading; `prefix`/`suffix` windows stay inside `[base, base+length)` by construction:

```python
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
    all_passages = list(passages.passages)
    if fulltext is not None:
        all_passages += list(fulltext.passages)

    # 1) Render frontmatter first to know its character length.
    body_sha = hashlib.sha256()  # placeholder; real hash computed after body built
    # We need text_sha256 of the persisted *body*; build the body region first,
    # hash it, then prepend frontmatter and recompute absolute offsets.

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
```

> Implementation note for the worker: the two-pass header-length convergence above is correct but fiddly. The cleaner equivalent — **build the body, hash it, serialize the frontmatter WITHOUT the `passages` list, then compute offsets against `header + body`, then append a deterministic-length `passages` block** — is acceptable; whichever you choose, the **`test_verify_offset_map_passes_on_self` and `test_offsets_slice_back_to_passage_text` tests are the contract**: offsets must slice back to passage text from the final rendered file. Do not weaken the tests to fit the implementation.

Add the `_build_frontmatter` helper (final field set lands in Task 5; stub the full shape now):

```python
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
```

- [ ] **4.4 Run it — expect pass:**
  `cd science && uv run --frozen pytest tests/test_source_text.py::TestOffsetMap -v`
  Expected: 4 passed. (If the header-convergence path is awkward, simplify per the implementation note — keep tests green.)

- [ ] **4.5 Commit:**
  `git add science/src/science_tool/annotation/source_text.py science/tests/test_source_text.py`
  `git commit -m "persist-source: per-passage offset map + slice-verification"`

---

## Task 5 — `.source.md` writer (frontmatter completeness + full-text gating)

Finalize the renderer so frontmatter carries the complete field set and the body has `## Abstract` always and `## Full Text` only when licensed; add the file-writing entry point `write_source_md`.

**Files**
- Modify: `science/src/science_tool/annotation/source_text.py` (add `write_source_md`; confirm `_build_frontmatter` field set)
- Modify: `science/tests/test_source_text.py` (add `TestWriteSourceMd`)

**Steps**

- [ ] **5.1 Write the failing test.** Add:

```python
from science_tool.annotation.source_text import write_source_md  # noqa: E402


class TestWriteSourceMd:
    def _abstract(self) -> SourcePassages:
        return SourcePassages(
            passages=(Passage(section="abstract", bioc_offset=0, text="An abstract sentence."),),
            release="2024.01",
        )

    def _fulltext(self) -> SourcePassages:
        return SourcePassages(
            passages=(Passage(section="body", bioc_offset=0, text="Full text body paragraph."),),
            release="2024.01",
        )

    def test_abstract_only_when_unlicensed(self, tmp_path: Path) -> None:
        # Full text WAS available but the license blocks it -> abstract only +
        # fulltext_omitted_reason. (The reason is recorded only when full text
        # actually existed; see `write_source_md`.)
        out = write_source_md(
            directory=tmp_path,
            citekey="Smith2024",
            abstract=self._abstract(),
            fulltext=self._fulltext(),
            retrieved_from="pubtator3",
            license_="CC-BY-NC",
            licensed=False,
            pmid="123456",
            doi="10.1038/foo-1",
        )
        text = out.read_text(encoding="utf-8")
        assert out.name == "Smith2024.source.md"
        assert "## Abstract" in text
        assert "## Full Text" not in text
        assert "Full text body paragraph." not in text
        assert "fulltext_omitted_reason: license-not-whitelisted" in text
        assert "license: CC-BY-NC" in text
        assert "An abstract sentence." in text

    def test_no_fulltext_records_distinct_reason(self, tmp_path: Path) -> None:
        # No full text was retrievable -> record `no-fulltext-available`, NOT the
        # license reason, so provenance distinguishes the two cases.
        out = write_source_md(
            directory=tmp_path,
            citekey="Smith2024",
            abstract=self._abstract(),
            fulltext=None,
            retrieved_from="europepmc",
            license_="unknown",
            licensed=False,
            pmid=None,
            doi="10.1038/foo-1",
        )
        text = out.read_text(encoding="utf-8")
        assert "## Full Text" not in text
        assert "fulltext_omitted_reason: no-fulltext-available" in text
        assert "license-not-whitelisted" not in text

    def test_full_text_persisted_when_licensed(self, tmp_path: Path) -> None:
        out = write_source_md(
            directory=tmp_path,
            citekey="Smith2024",
            abstract=self._abstract(),
            fulltext=self._fulltext(),
            retrieved_from="europepmc",
            license_="CC-BY-4.0",
            licensed=True,
            pmid=None,
            doi="10.1038/foo-1",
        )
        text = out.read_text(encoding="utf-8")
        assert "## Full Text" in text
        assert "Full text body paragraph." in text
        assert "fulltext_omitted_reason" not in text
        assert "license: CC-BY-4.0" in text

    def test_text_sha256_is_hash_of_body_region(self, tmp_path: Path) -> None:
        import hashlib

        from science_tool.commons.frontmatter import raw_frontmatter

        out = write_source_md(
            directory=tmp_path,
            citekey="Smith2024",
            abstract=self._abstract(),
            fulltext=None,
            retrieved_from="pubtator3",
            license_="CC-BY",
            licensed=True,
            pmid=None,
            doi="10.1038/foo-1",
        )
        fm = raw_frontmatter(out)
        text = out.read_text(encoding="utf-8")
        body = text.split("---\n", 2)[2].lstrip("\n")
        assert fm["text_sha256"] == hashlib.sha256(body.encode("utf-8")).hexdigest()

    def test_offsets_in_written_file_slice_back(self, tmp_path: Path) -> None:
        from science_tool.commons.frontmatter import raw_frontmatter

        out = write_source_md(
            directory=tmp_path,
            citekey="Smith2024",
            abstract=self._abstract(),
            fulltext=self._fulltext(),
            retrieved_from="europepmc",
            license_="CC-BY-4.0",
            licensed=True,
            pmid=None,
            doi="10.1038/foo-1",
        )
        text = out.read_text(encoding="utf-8")
        fm = raw_frontmatter(out)
        for entry in fm["passages"]:
            base, length = entry["file_char_base"], entry["length"]
            assert text[base : base + length] in {"An abstract sentence.", "Full text body paragraph."}
```

- [ ] **5.2 Run it — expect failure:**
  `cd science && uv run --frozen pytest tests/test_source_text.py::TestWriteSourceMd -v`
  Expected: `ImportError: cannot import name 'write_source_md'`.

- [ ] **5.3 Minimal implementation.** Add to `source_text.py`. `write_source_md` composes Task 4's `render_source_md`, runs `verify_offset_map`, and writes the file:

```python
def write_source_md(
    *,
    directory: Path,
    citekey: str,
    abstract: SourcePassages,
    fulltext: SourcePassages | None,
    retrieved_from: str,
    license_: str,
    licensed: bool,
    pmid: str | None,
    doi: str | None,
) -> Path:
    """Render, slice-verify, and write `<citekey>.source.md` next to the entity.

    Full text is included ONLY when `licensed` is True and full text exists.
    Otherwise `fulltext_omitted_reason` records why it is absent:
    `license-not-whitelisted` (full text existed but its license is not whitelisted)
    or `no-fulltext-available` (no full text was retrievable). The
    offset map is slice-verified against the rendered file before writing — a
    mismatch raises SourceTextError and nothing is written.
    """
    persisted_fulltext = fulltext if licensed else None
    # Distinguish the two reasons full text can be absent: a non-whitelisted license
    # on full text that DID exist, vs. no full text being retrievable at all. Both are
    # recorded so provenance always states why full text is absent.
    if fulltext is not None and not licensed:
        omitted_reason: str | None = "license-not-whitelisted"
    elif fulltext is None:
        omitted_reason = "no-fulltext-available"
    else:
        omitted_reason = None

    rendered = render_source_md(
        citekey=citekey,
        passages=abstract,
        retrieved_from=retrieved_from,
        license_=license_,
        pmid=pmid,
        doi=doi,
        fulltext=persisted_fulltext,
        fulltext_omitted_reason=omitted_reason,
    )

    # Self-consistency: every offset entry must slice back to its passage text.
    combined = SourcePassages(
        passages=abstract.passages + (persisted_fulltext.passages if persisted_fulltext else ()),
        release=abstract.release,
    )
    verify_offset_map(rendered.text, list(rendered.offset_map), combined)

    out = directory / f"{citekey}.source.md"
    out.write_text(rendered.text, encoding="utf-8")
    return out
```

Ensure `_build_frontmatter` emits, in order: `kind: paper-source`, `retrieved_from`, `license`, `text_sha256`, `doi`/`pmid` (when present), `fulltext_omitted_reason` (when present), `passages` (the offset map). (Already done in Task 4; adjust if the test asserts a key not yet present.)

- [ ] **5.4 Run it — expect pass:**
  `cd science && uv run --frozen pytest tests/test_source_text.py::TestWriteSourceMd -v`
  Expected: 4 passed.

- [ ] **5.5 Commit:**
  `git add science/src/science_tool/annotation/source_text.py science/tests/test_source_text.py`
  `git commit -m "persist-source: .source.md writer with full-text license gating"`

---

## Task 6 — Text acquisition (network, injectable httpx.Client)

Fetch the PubTator3 BioC record (preferred), splitting passages into the abstract floor (title/abstract) and best-effort full text (body sections); fall back to the Europe PMC abstract (single passage) when no BioC record. Resolve a license from Europe PMC `license` (Unpaywall's `oa_locations[].license` is a deferred secondary source; EPMC is the Phase 1 primary). All requests go through an injected `httpx.Client` via `RateLimiter`, exactly like `fetch_paper`.

**Files**
- Modify: `science/src/science_tool/annotation/source_text.py` (add `AcquiredSource`, `acquire_source_text`, `_fetch_bioc`, `_fetch_europepmc_core`)
- Modify: `science/tests/test_source_text.py` (add `TestAcquireSourceText`, `_cfg`, `_make_client`)

**Steps**

- [ ] **6.1 Write the failing test.** Add (reuse `_make_client`; add `_cfg` mirroring `test_paper_fetch.py`):

```python
from science_tool.annotation.source_text import (  # noqa: E402
    EUROPEPMC_API_VERSION,
    AcquiredSource,
    acquire_source_text,
)
from science_tool.paper_fetch import FetchConfig


def _cfg(tmp_path: Path) -> FetchConfig:
    return FetchConfig(email="test@example.com", cache_dir=tmp_path, sleep=lambda _s: None)


_PUBTATOR_HOST = "www.ncbi.nlm.nih.gov"
_EPMC_HOST = "www.ebi.ac.uk"


class TestAcquireSourceText:
    def test_prefers_pubtator_bioc_abstract(self, tmp_path: Path) -> None:
        def handler(req: httpx.Request) -> httpx.Response:
            if req.url.host == _PUBTATOR_HOST:
                return httpx.Response(200, json=_BIOC_RECORD)
            if req.url.host == _EPMC_HOST:
                return httpx.Response(
                    200,
                    json={"resultList": {"result": [{"license": "CC-BY"}]}},
                )
            raise AssertionError(f"unexpected host {req.url.host}")

        acquired = acquire_source_text(
            pmid="123456", doi="10.1038/foo-1", cfg=_cfg(tmp_path), http=_make_client(handler)
        )
        assert acquired.retrieved_from == "pubtator3"
        assert acquired.abstract.passages[0].text == "BRCA1 in cancer"
        assert acquired.license == "CC-BY"
        assert acquired.licensed is True
        # _BIOC_RECORD has only title+abstract -> no full text.
        assert acquired.fulltext is None
        assert acquired.abstract.release == "2024.01"  # BioC release, not a marker

    def test_bioc_body_sections_become_fulltext(self, tmp_path: Path) -> None:
        record = {
            "PubTator3": [
                {
                    "infons": {"_release": "2024.01"},
                    "passages": [
                        {"offset": 0, "text": "T", "infons": {"type": "title"}},
                        {"offset": 2, "text": "Abstract here.", "infons": {"type": "abstract"}},
                        {"offset": 17, "text": "Methods paragraph.", "infons": {"type": "methods"}},
                    ],
                }
            ]
        }

        def handler(req: httpx.Request) -> httpx.Response:
            if req.url.host == _PUBTATOR_HOST:
                return httpx.Response(200, json=record)
            if req.url.host == _EPMC_HOST:
                return httpx.Response(200, json={"resultList": {"result": [{"license": "CC-BY-4.0"}]}})
            raise AssertionError(f"unexpected host {req.url.host}")

        acquired = acquire_source_text(
            pmid="123456", doi="10.1038/foo-1", cfg=_cfg(tmp_path), http=_make_client(handler)
        )
        assert {p.section for p in acquired.abstract.passages} == {"title", "abstract"}
        assert acquired.fulltext is not None
        assert acquired.fulltext.passages == (
            Passage(section="methods", bioc_offset=17, text="Methods paragraph."),
        )
        assert acquired.licensed is True

    def test_falls_back_to_europepmc_abstract(self, tmp_path: Path) -> None:
        def handler(req: httpx.Request) -> httpx.Response:
            if req.url.host == _PUBTATOR_HOST:
                return httpx.Response(404)
            if req.url.host == _EPMC_HOST:
                return httpx.Response(
                    200,
                    json={"resultList": {"result": [{"abstractText": "Fallback abstract.", "license": "CC-BY-NC"}]}},
                )
            raise AssertionError(f"unexpected host {req.url.host}")

        acquired = acquire_source_text(
            pmid="123456", doi="10.1038/foo-1", cfg=_cfg(tmp_path), http=_make_client(handler)
        )
        assert acquired.retrieved_from == "europepmc"
        assert acquired.abstract.passages == (
            Passage(section="abstract", bioc_offset=0, text="Fallback abstract."),
        )
        # source_release must reflect the EPMC source, not a PubTator marker.
        assert acquired.abstract.release == EUROPEPMC_API_VERSION
        assert acquired.license == "CC-BY-NC"
        assert acquired.licensed is False

    def test_raises_when_no_abstract_anywhere(self, tmp_path: Path) -> None:
        def handler(req: httpx.Request) -> httpx.Response:
            if req.url.host == _PUBTATOR_HOST:
                return httpx.Response(404)
            if req.url.host == _EPMC_HOST:
                return httpx.Response(200, json={"resultList": {"result": []}})
            raise AssertionError(f"unexpected host {req.url.host}")

        with pytest.raises(SourceTextError):
            acquire_source_text(
                pmid="123456", doi="10.1038/foo-1", cfg=_cfg(tmp_path), http=_make_client(handler)
            )
```

- [ ] **6.2 Run it — expect failure:**
  `cd science && uv run --frozen pytest tests/test_source_text.py::TestAcquireSourceText -v`
  Expected: `ImportError: cannot import name 'AcquiredSource'`.

- [ ] **6.3 Minimal implementation.** Add to `source_text.py` (reuse `RateLimiter`, `FetchConfig`, `_get_json` from `paper_fetch`):

```python
import httpx

from science_tool.paper_fetch import FetchConfig, RateLimiter, _get_json

# PubTator3 BioC export endpoint (live API, JSON format). PubMed-only by design.
_PUBTATOR3_BIOC_URL = (
    "https://www.ncbi.nlm.nih.gov/research/pubtator3-api/publications/export/biocjson"
)
_PUBTATOR3_HOST = "www.ncbi.nlm.nih.gov"
_EPMC_SEARCH_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
_EPMC_HOST = "www.ebi.ac.uk"


# Marker for Europe-PMC-sourced text (no PubTator release applies).
EUROPEPMC_API_VERSION = "europepmc-api"


@dataclass(frozen=True)
class AcquiredSource:
    abstract: SourcePassages
    fulltext: SourcePassages | None
    retrieved_from: str
    license: str
    licensed: bool
    # NOTE: the source release lives on `abstract.release` (BioC release for
    # PubTator, EUROPEPMC_API_VERSION for the fallback) and the renderer reads it
    # from there via `passages.release`; there is no separate `release` field to
    # drift out of sync.


def _fetch_bioc(
    pmid: str, client: httpx.Client, limiter: RateLimiter, cfg: FetchConfig
) -> SourcePassages | None:
    data, _err = _get_json(
        client, limiter, _PUBTATOR3_BIOC_URL, _PUBTATOR3_HOST, params={"pmids": pmid}
    )
    if not data:
        return None
    return parse_bioc_passages(data)


def _fetch_europepmc_core(
    doi: str | None, pmid: str | None, client: httpx.Client, limiter: RateLimiter
) -> dict[str, Any] | None:
    if doi:
        query = f'DOI:"{doi}"'
    elif pmid:
        query = f"EXT_ID:{pmid} AND SRC:MED"
    else:
        return None
    data, _err = _get_json(
        client,
        limiter,
        _EPMC_SEARCH_URL,
        _EPMC_HOST,
        params={"query": query, "format": "json", "resultType": "core", "pageSize": "1"},
    )
    if not data:
        return None
    results = data.get("resultList")
    if not isinstance(results, dict):
        return None
    items = results.get("result") or []
    return items[0] if items and isinstance(items[0], dict) else None


def acquire_source_text(
    *,
    pmid: str | None,
    doi: str | None,
    cfg: FetchConfig,
    http: httpx.Client | None = None,
) -> AcquiredSource:
    """Acquire abstract text (BioC preferred, Europe PMC fallback) + license.

    Full-text acquisition is best-effort and license-gated at the writer; Phase 1
    persists the abstract floor. Raises SourceTextError when no abstract resolves.
    """
    owns = http is None
    client = http or httpx.Client(
        timeout=cfg.http_timeout, headers={"User-Agent": f"science/0.1 (mailto:{cfg.email})"}
    )
    try:
        limiter = RateLimiter(cfg)
        epmc = _fetch_europepmc_core(doi, pmid, client, limiter)
        license_candidates: list[str | None] = []
        if epmc:
            license_candidates.append(_as_str(epmc.get("license")))

        abstract: SourcePassages | None = None
        fulltext: SourcePassages | None = None
        retrieved_from = ""
        if pmid:
            bioc = _fetch_bioc(pmid, client, limiter, cfg)
            if bioc is not None:
                # PubTator3 BioC returns title+abstract always and body sections for
                # PMC-OA articles. Split by section: abstract floor vs best-effort
                # full text. Both share the same release; the writer license-gates
                # full text.
                abstract, fulltext = _split_passages(bioc)
                retrieved_from = "pubtator3"

        if abstract is None and epmc:
            text = _as_str(epmc.get("abstractText"))
            if text and text.strip():
                abstract = SourcePassages(
                    passages=(Passage(section="abstract", bioc_offset=0, text=text.strip()),),
                    release=EUROPEPMC_API_VERSION,  # NOT a PubTator release
                )
                retrieved_from = "europepmc"
                # Europe PMC fallback yields abstract only; full text stays None.

        if abstract is None:
            raise SourceTextError(
                f"no abstract available from PubTator3 or Europe PMC for doi={doi!r} pmid={pmid!r}"
            )

        license_, licensed = resolve_license(license_candidates)
        return AcquiredSource(
            abstract=abstract,
            fulltext=fulltext,
            retrieved_from=retrieved_from,
            license=license_,
            licensed=licensed,
        )
    finally:
        if owns:
            client.close()
```

Add the `_split_passages` helper near `parse_bioc_passages`:

```python
# BioC passage sections that constitute the abstract floor; everything else
# (intro/methods/results/discussion/etc.) is best-effort full text.
_ABSTRACT_BIOC_SECTIONS = frozenset({"title", "abstract"})


def _split_passages(parsed: SourcePassages) -> tuple[SourcePassages, SourcePassages | None]:
    """Partition BioC passages into (abstract, full-text-or-None) by section.

    Falls back to treating all passages as the abstract when none is labeled
    title/abstract (defensive; a malformed record should still yield the floor).
    """
    abstract = tuple(p for p in parsed.passages if p.section in _ABSTRACT_BIOC_SECTIONS)
    body = tuple(p for p in parsed.passages if p.section not in _ABSTRACT_BIOC_SECTIONS)
    abstract_sp = SourcePassages(
        passages=abstract or parsed.passages, release=parsed.release
    )
    fulltext_sp = (
        SourcePassages(passages=body, release=parsed.release) if body else None
    )
    return abstract_sp, fulltext_sp
```

> Scope note: full text is **best-effort and license-gated**. PubTator3 BioC returns body passages only for PMC-OA articles; when present and the license is whitelisted, `## Full Text` is written. Common cases — non-OA article (BioC returns title+abstract only) or Europe PMC fallback — yield abstract only, which is the guaranteed floor. Phase 1 does NOT add a separate Europe PMC full-text-XML path (deferred); full text in Phase 1 comes solely from the BioC record already fetched, preserving offset alignment.

- [ ] **6.4 Run it — expect pass:**
  `cd science && uv run --frozen pytest tests/test_source_text.py::TestAcquireSourceText -v`
  Expected: 4 passed.

- [ ] **6.5 Commit:**
  `git add science/src/science_tool/annotation/source_text.py science/tests/test_source_text.py`
  `git commit -m "persist-source: BioC + Europe PMC text acquisition (injectable client)"`

---

## Task 7 — `persist-source` CLI command

Wire resolver → acquisition → license gate → writer behind `science paper persist-source <pmid|doi>`, mirroring `paper-fetch` (email/`FetchConfig`/`--cache-dir`, injectable client seam for tests).

**Files**
- Modify: `science/src/science_tool/cli.py` (add command after `paper_fetch_cmd`, ~line 4600)
- Create: `science/tests/test_cli_persist_source.py`

**Steps**

- [ ] **7.1 Write the failing test.** Create `science/tests/test_cli_persist_source.py`:

```python
"""End-to-end CliRunner tests for `science paper persist-source`."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import httpx
from click.testing import CliRunner

from science_tool.cli import main


def _make_client(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def _write_paper(project_root: Path, citekey: str, *, doi: str, pmid: str) -> Path:
    papers_dir = project_root / "entities" / "papers"
    papers_dir.mkdir(parents=True, exist_ok=True)
    path = papers_dir / f"{citekey}.md"
    path.write_text(
        f'---\nid: paper:{citekey}\ntitle: {citekey}\ndoi: {doi}\npmid: "{pmid}"\n---\n\n## Key Findings\n\nx\n',
        encoding="utf-8",
    )
    return path


_BIOC = {
    "PubTator3": [
        {
            "infons": {"_release": "2024.01"},
            "passages": [
                {"offset": 0, "text": "Title here", "infons": {"type": "title"}},
                {"offset": 11, "text": "Abstract body.", "infons": {"type": "abstract"}},
            ],
        }
    ]
}


def test_persist_source_writes_source_md(tmp_path: Path, monkeypatch) -> None:
    project = tmp_path / "proj"
    _write_paper(project, "Smith2024", doi="10.1038/foo-1", pmid="123456")

    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.host == "www.ncbi.nlm.nih.gov":
            return httpx.Response(200, json=_BIOC)
        if req.url.host == "www.ebi.ac.uk":
            return httpx.Response(200, json={"resultList": {"result": [{"license": "CC-BY-4.0"}]}})
        raise AssertionError(f"unexpected host {req.url.host}")

    # Inject the mocked client through the documented test seam.
    monkeypatch.setattr(
        "science_tool.annotation.source_text._test_http_client", _make_client(handler), raising=False
    )

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["paper", "persist-source", "10.1038/foo-1", "--project-root", str(project), "--email", "t@example.com"],
    )
    assert result.exit_code == 0, result.output
    out = project / "entities" / "papers" / "Smith2024.source.md"
    assert out.is_file()
    assert "## Abstract" in out.read_text(encoding="utf-8")


def test_persist_source_no_match_fails_loud(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    _write_paper(project, "Smith2024", doi="10.1038/foo-1", pmid="123456")
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["paper", "persist-source", "10.9999/missing", "--project-root", str(project), "--email", "t@example.com"],
    )
    assert result.exit_code != 0
    assert "no paper entity" in result.output
```

> Test-seam note: rather than threading an `httpx.Client` through Click options, expose a module-level optional `_test_http_client` in `source_text.py` that `acquire_source_text` uses when set (and the CLI passes `http=None`). This keeps the command signature clean while staying hermetic. Check the existing `paper-fetch` command + tests first; if there is already a project convention for injecting a client into a command (there is not for `paper-fetch` — it constructs its own), adopt the `_test_http_client` seam.

- [ ] **7.2 Run it — expect failure:**
  `cd science && uv run --frozen pytest tests/test_cli_persist_source.py -v`
  Expected: failure — `persist-source` command does not exist (Click reports "No such command").

- [ ] **7.3 Minimal implementation.** In `source_text.py`, add the seam and a `persist_source` orchestration entry point:

```python
# Optional test seam: when set, acquire_source_text uses this client instead of
# constructing its own. Production code leaves it None.
_test_http_client: httpx.Client | None = None


def persist_source(
    *, project_root: Path, identifier: str, cfg: FetchConfig
) -> Path:
    """Resolve identifier -> entity, acquire text, gate license, write .source.md."""
    doi = normalize_doi(identifier)
    pmid = None if doi else normalize_pmid(identifier)
    if not doi and not pmid:
        raise SourceTextError(
            f"{identifier!r} is neither a DOI nor a PMID; pass a bare DOI/PMID or doi.org URL."
        )
    resolved = resolve_paper_entity(project_root, doi=doi, pmid=pmid)
    # Use the ENTITY's identifiers, not just the input shape: a DOI-invoked command
    # must still hand PubTator the entity's PMID (acquisition prefers BioC by PMID).
    acquired = acquire_source_text(
        pmid=resolved.pmid, doi=resolved.doi, cfg=cfg, http=_test_http_client
    )
    return write_source_md(
        directory=resolved.directory,
        citekey=resolved.citekey,
        abstract=acquired.abstract,
        fulltext=acquired.fulltext,
        retrieved_from=acquired.retrieved_from,
        license_=acquired.license,
        licensed=acquired.licensed,
        pmid=resolved.pmid,
        doi=resolved.doi,
    )
```

In `cli.py`, add after `paper_fetch_cmd` (~line 4600). Note `paper-fetch` is a flat `@main.command`; the spec asks for `science paper persist-source`, so introduce a `paper` group and register `persist-source` under it (leave the existing top-level `paper-fetch` untouched for back-compat):

```python
@main.group("paper")
def paper() -> None:
    """Paper-entity source-text commands."""


@paper.command("persist-source")
@click.argument("identifier")
@click.option(
    "--project-root",
    default=None,
    type=click.Path(path_type=Path, file_okay=False),
    help="Project root (defaults to the current directory).",
)
@click.option(
    "--email",
    default=None,
    help="Contact email for polite-pool APIs (falls back to $SCIENCE_CONTACT_EMAIL)",
)
@click.option(
    "--cache-dir",
    default=None,
    type=click.Path(path_type=Path),
    help="Override cache directory (defaults to $SCIENCE_CACHE_DIR or ~/.cache/science)",
)
def persist_source_cmd(
    identifier: str,
    project_root: Path | None,
    email: str | None,
    cache_dir: Path | None,
) -> None:
    """Persist <citekey>.source.md (abstract always; full text when OA-licensed).

    Resolves a DOI or PMID to an existing paper entity, fetches the article text
    (PubTator3 BioC preferred, Europe PMC abstract fallback), license-gates
    full-text persistence, and writes the anchor surface next to the entity.
    """
    import os as _os

    from science_tool.annotation.source_text import SourceTextError, persist_source
    from science_tool.paper_fetch import FetchConfig

    resolved_email = email or _os.environ.get("SCIENCE_CONTACT_EMAIL")
    if not resolved_email:
        raise click.ClickException("Contact email is required. Pass --email or set $SCIENCE_CONTACT_EMAIL.")
    cfg_kwargs: dict[str, Any] = {"email": resolved_email}
    if cache_dir is not None:
        cfg_kwargs["cache_dir"] = cache_dir
    cfg = FetchConfig(**cfg_kwargs)
    root = (project_root or Path.cwd()).resolve()
    try:
        out = persist_source(project_root=root, identifier=identifier, cfg=cfg)
    except SourceTextError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"Wrote {out}")
```

- [ ] **7.4 Run it — expect pass:**
  `cd science && uv run --frozen pytest tests/test_cli_persist_source.py -v`
  Expected: 2 passed. Then run the whole module: `cd science && uv run --frozen pytest tests/test_source_text.py tests/test_cli_persist_source.py -v` — all green.

- [ ] **7.5 Commit:**
  `git add science/src/science_tool/cli.py science/tests/test_cli_persist_source.py science/src/science_tool/annotation/source_text.py`
  `git commit -m "persist-source: CLI command wiring resolver/acquisition/gate/writer"`

---

## Task 8 — Exclude `.source.md` sidecars from entity discovery (correctness gate)

`<citekey>.source.md` is written **into a scanned entity root** (e.g. `entities/papers/`). `MarkdownAdapter.discover` ingests every `*.md` under its scan roots via `root.rglob("*.md")` (`science/src/science_tool/graph/storage_adapters/markdown.py:33`), so without an exclusion a persisted `.source.md` (frontmatter `kind: paper-source`) would be ingested as an unknown-kind entity and break `science graph build`. The anchor surface is a sidecar, **not** an entity — discovery must skip it. (Numeric-scan globs like `entities.py:453` only match `_NUMERIC_SCAN_RE` stems and `graph_is_stale` only reads mtimes, so this is the one ingestion chokepoint that matters.)

**Files**
- Modify: `science/src/science_tool/graph/storage_adapters/markdown.py` (`discover`, ~line 27-42)
- Modify: `science/tests/test_source_text.py` (add `TestSidecarNotDiscovered`)

**Steps**

- [ ] **8.1 Write the failing test.** Add to `science/tests/test_source_text.py`:

```python
from science_tool.graph.storage_adapters.markdown import MarkdownAdapter  # noqa: E402


class TestSidecarNotDiscovered:
    def test_source_md_sidecar_is_not_ingested_as_entity(self, tmp_path: Path) -> None:
        papers = tmp_path / "entities" / "papers"
        papers.mkdir(parents=True)
        (papers / "Smith2024.md").write_text(
            "---\nid: paper:Smith2024\ntitle: Smith2024\n---\n\nx\n", encoding="utf-8"
        )
        (papers / "Smith2024.source.md").write_text(
            "---\nkind: paper-source\ntext_sha256: abc\n---\n\n## Abstract\n\nx\n", encoding="utf-8"
        )
        refs = MarkdownAdapter(scan_roots=["entities"]).discover(tmp_path)
        paths = {r.path for r in refs}
        assert "entities/papers/Smith2024.md" in paths
        assert "entities/papers/Smith2024.source.md" not in paths
```

- [ ] **8.2 Run it — expect failure:**
  `cd science && uv run --frozen pytest tests/test_source_text.py::TestSidecarNotDiscovered -v`
  Expected: FAIL — the `.source.md` sidecar is currently discovered (assertion on the second `assert` fails).

- [ ] **8.3 Minimal implementation.** In `science/src/science_tool/graph/storage_adapters/markdown.py`, add a module-level constant near the top of the file (after the imports):

```python
# Anchor-surface sidecars (paper `.source.md`) live inside entity roots but are
# NOT entities; never ingest them as source records.
SIDECAR_MARKDOWN_SUFFIX = ".source.md"
```

Then skip sidecars in both discovery branches of `discover`:

```python
            for path in sorted(root.rglob("*.md")):
                if path.name.endswith(SIDECAR_MARKDOWN_SUFFIX):
                    continue
                try:
                    rel_path = str(path.relative_to(project_root))
                except ValueError:
                    rel_path = str(path)
                refs_by_path[rel_path] = SourceRef(adapter_name=self.name, path=rel_path)
        for rel_path in self._virtual_files:
            if rel_path.endswith(".md") and not rel_path.endswith(SIDECAR_MARKDOWN_SUFFIX):
                refs_by_path[rel_path] = SourceRef(adapter_name=self.name, path=rel_path)
```

- [ ] **8.4 Run it — expect pass:**
  `cd science && uv run --frozen pytest tests/test_source_text.py::TestSidecarNotDiscovered -v`
  Expected: 1 passed.

- [ ] **8.5 Regression — confirm nothing else broke.** The exclusion changes a core discovery path; run the graph/entity suites:
  `cd science && uv run --frozen pytest tests/test_source_text.py tests/ -k "markdown or sources or discover or graph_build" -v`
  Expected: green (no entity that legitimately ends in `.source.md` exists — this suffix is new and reserved by this feature).

- [ ] **8.6 Commit:**
  `git add science/src/science_tool/graph/storage_adapters/markdown.py science/tests/test_source_text.py`
  `git commit -m "persist-source: exclude .source.md sidecars from entity discovery"`

---

## Self-review

### Spec-coverage table

| Spec requirement (section) | Where covered |
|---|---|
| `<citekey>.source.md` co-located with resolved entity (Data artifacts) | Task 5 (`write_source_md` writes into `resolved.directory`); Task 1 resolves the directory by scanning the canonical paper subdirs |
| Identifier → paper-entity resolver; scan frontmatter `doi`/`pmid`, normalized (Identifier→resolution) | Task 1 (`resolve_paper_entity`, `normalize_doi`/`normalize_pmid`) |
| No-match fails loud + actionable (`paper-fetch`/create) (Identifier→resolution) | Task 1 (`test_no_match_fails_loud`) |
| Multi-match fails loud naming both files (Identifier→resolution) | Task 1 (`test_multi_match_fails_loud_naming_both`) |
| Resolver surfaces the entity's own normalized doi+pmid so acquisition can prefer PubTator even on DOI invocation | Task 1 (`ResolvedPaper.doi`/`.pmid`, `test_carries_entity_pmid_when_resolved_by_doi`); Task 7 (`persist_source` uses `resolved.pmid`/`resolved.doi`) |
| Placement follows the resolved entity's own directory — any canonical paper subdir (`entities/papers`, `doc/papers`, `doc/background/papers`), not a single hardcoded root | Task 1 (`_paper_dirs` reuses `PROMOTE_KIND_PAPER.source_subdirs`; `test_resolves_paper_under_doc_background_papers`) |
| Offset basis = raw UTF-8-decoded, NOT NFC-normalized (Offset basis) | Task 2 (`Passage.text` verbatim; docstring states no NFC); Task 4 (`test_offset_base_is_character_not_byte`) |
| Character offsets end-to-end, no byte layer (Offset basis) | Task 4 (`PassageOffset.file_char_base` is a `str` index; em-dash test) |
| Per-passage offset map: section + char base + length (Offset basis: provenance) | Task 4 (`PassageOffset`); Task 5 (`passages` frontmatter) |
| Verify by slicing (self-consistency) (Verify-and-fail-early) | Task 4 (`verify_offset_map`); Task 5 (`write_source_md` calls it pre-write) |
| Anchor region excludes frontmatter/headings; windows don't cross headings/passages (Anchor region) | Task 4 (`render_source_md` body layout; offsets index passage bodies only; docstring) |
| BioC abstract (title+abstract passages) preferred (Components #1) | Task 2 + Task 6 (`_fetch_bioc`, `test_prefers_pubtator_bioc_abstract`) |
| Europe PMC abstract single-passage fallback (Components #1) | Task 6 (`test_falls_back_to_europepmc_abstract`) |
| License whitelist `CC0/CC-BY/CC-BY-SA/CC-BY-ND` + versioned (License gating) | Task 3 (`LICENSE_WHITELIST`, `is_whitelisted`) |
| Resolve license from EPMC `license`; most-permissive whitelisted wins else unknown (Unpaywall `oa_locations[].license` exists but is deferred; EPMC license is the Phase 1 primary) | Task 3 (`resolve_license`); Task 6 (candidate from EPMC core) |
| Abstract never gated; non-whitelisted ⇒ abstract only + `fulltext_omitted_reason` (License gating) | Task 5 (`test_abstract_only_when_unlicensed`) |
| Full text acquired from BioC body sections (best-effort) and persisted only when whitelisted (License gating) | Task 6 (`_split_passages`, `test_bioc_body_sections_become_fulltext`); Task 5 (`test_full_text_persisted_when_licensed`) |
| Frontmatter: `retrieved_from`, `source_release`, `license`, `text_sha256`, `pmid`/`doi`, offset map, `fulltext_omitted_reason` (artifact row) | Task 4/5 (`_build_frontmatter`; `test_text_sha256_is_hash_of_body_region`) |
| `text_sha256` = sha256 of persisted body (Dedup: document hash provenance) | Task 4/5 (`test_text_sha256_is_hash_of_body_region`) |
| CLI mirrors `paper-fetch` (email/`FetchConfig`/`--cache-dir`/`--project-root`) (Components #1) | Task 7 |
| Network through injectable `httpx.Client` + `MockTransport` (Testing; Be testable) | Tasks 6–7 (`http=` param, `_test_http_client` seam, `MockTransport`) |
| Conventions registration of license whitelist | Task 3 (`docs/conventions/annotation-tokens.md`) |
| `.source.md` is a sidecar, not an entity — must not corrupt `science graph build` (integration correctness) | Task 8 (`MarkdownAdapter.discover` excludes `*.source.md`) |

### Deferred to Phase 2+ (explicitly NOT in this plan)

- **PubTator entity/relation annotations** — entity mentions, relations, the `entity-<type>`→Biolink map, offset→`TextQuoteSelector` conversion that re-resolves via `annotation/verify.py`. (Phase 1 only emits the offset map; it does not create selectors or annotations.)
- **`sci:annotationType` vocabulary** (`entity-*`, `relation`, `proposition`/`question`/`hypothesis`, `metaphor`/`analogy`) and the versioned `source` prefixes (`pubtator3:<release>:seeder-vN`, `llm-annot:<model>:paper-annotate-vN`).
- **JSON `TextualBody` bodies** (relation/statement/metaphor schemas) and `application/json` round-trip validation.
- **`sci:sourceTextHash`** and the per-source `sci:AuditLedger` document-level short-circuit — this is a **Phase-2 ledger field**, not a `.source.md` frontmatter field. (`text_sha256` here is only the document's current-body provenance hash.)
- **`content_hash` / `HASH_REQUIRED_SOURCE_PREFIXES` / re-audit caching** and per-annotation idempotency.
- **Agent extraction skill** (`paper-annotate`) and **promotion** into epistemic entities.
- **Europe PMC full-text-XML acquisition** (`_try_europepmc_fulltext` JATS → passages) for articles where PubTator BioC carries no body sections. Phase 1 sources full text **only** from the BioC record already fetched (preserving offset alignment); a separate EPMC-XML full-text path is deferred. (Phase 1 does write `## Full Text` when BioC supplies licensed body sections — see Task 6 `test_bioc_body_sections_become_fulltext`.)
- **Unpaywall license extraction** — `_try_unpaywall` *does* return `oa_locations[].license`, but Phase 1 resolves license from Europe PMC only; Unpaywall is a deferred secondary source.
- **`<citekey>.source.anno.trig`** sidecar (created by the seeder, not the anchor surface).
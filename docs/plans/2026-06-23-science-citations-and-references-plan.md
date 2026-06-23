# Science Citations and References Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn Pandoc-style citations (`[@Key]`) in Science project prose into numbered inline references with a generated References section in Labnote, driven by a versioned reference bundle exported from Science's `papers/references.bib`.

**Architecture:** Science owns citation identity, BibTeX normalization, display-string formatting, the citation-syntax grammar, the reference-bundle builder, and fail-closed export validation. MM30's `app_export` calls the Science builder, writes `references/index.json`, scans its Markdown surfaces, and registers a manifest bundle. Labnote loads the bundle and renders inline numeric citations + a References section, with a citation grammar verified byte-for-byte against Science via a shared JSON corpus.

**Tech Stack:** Python 3.12 (science_tool, pytest), MM30 app_export scripts (Python + polars), Labnote (JS/ESM, markdown-it, vitest + jsdom, playwright for e2e).

**Design doc:** `~/d/science/docs/plans/2026-06-23-science-citations-and-references-design.md` — read sections referenced per task.

## Global Constraints

- Contract identity is fixed: every reference bundle and record carries `"contract": "science.references"` and `"schema_version": "1"` (bare string, matching `GRAPH_EXPORT_SCHEMA_VERSION = "1"`). Copy these exact literals.
- Fail-closed: duplicate citekeys, unknown citekeys in exported prose, and unsupported citation syntax (`[see @x]`, `[-@x]`, bare `@x`, malformed `[@x extra]`) are all errors during normal export. Malformed/unbalanced BibTeX entries are excluded from the normalized bundle; if exported prose cites such a key, validation fails as `unknown-citekey`.
- Reference DOM ids are `ref-` + lowercase hex of the UTF-8 bytes of the bare citekey (e.g. `Smith2020` → `ref-536d69746832303230`). The original citekey is preserved in `data-citekey`.
- Both citation parsers (Python in Science, JS in Labnote) must produce the identical citekey/locator/unsupported sets on the shared corpus `science/tests/fixtures/citation_grammar_v1.json`.
- Commit messages: do NOT include any `Co-Authored-By` trailer.
- Use `~/d/` (not `/home/keith/d/` or `/mnt/ssd/Dropbox/`) for file paths in docs and code comments.
- Phase boundaries (A = Science, B = MM30, C = Labnote, D = end-to-end) are independently reviewable. Phase A must land before B and D. Phase C depends on A only for the shared corpus fixture and contract shape, and can otherwise proceed in parallel.

---

## Phase A — Science (Python)

All Phase A code lives in a new module `science_tool/references.py` plus extensions to `science_tool/bibliography.py` and `science_tool/prose_lint.py`. Tests in `science/tests/test_references.py`. Run tests with `PYTHONPATH=src:model/src` if working in a worktree (science_model is editable-installed from main and shadows worktree edits).

### Task A1: Extend `BibEntry` with bibliographic fields

**Files:**
- Modify: `~/d/science/science/src/science_tool/bibliography.py:87-96` (the `BibEntry` dataclass) and `:160-167` (the `BibEntry(...)` construction in `load_bib_entries`)
- Test: `~/d/science/science/tests/test_bibliography_entries.py`

**Interfaces:**
- Produces: `BibEntry` gains fields `author: str | None`, `journal: str | None`, `booktitle: str | None`, `publisher: str | None`, `volume: str | None`, `number: str | None`, `pages: str | None`, `pmid: str | None` (all default `None`, appended after the existing `url` field to preserve positional construction).

- [ ] **Step 1: Write the failing test**

Add to `~/d/science/science/tests/test_bibliography_entries.py`:

```python
def test_load_bib_entries_parses_extended_fields(tmp_path: Path) -> None:
    _write_bib(
        tmp_path,
        "@article{Williams2018,\n"
        "  author = {Williams, Donald R. and Rast, Philippe},\n"
        "  title = {Bayesian Meta-Analysis},\n"
        "  journal = {PsyArXiv},\n"
        "  year = {2018},\n"
        "  volume = {12},\n"
        "  number = {3},\n"
        "  pages = {45--67},\n"
        "  pmid = {29876543},\n"
        "}\n",
    )
    entry = load_bib_entries(tmp_path)["Williams2018"]
    assert entry.author == "Williams, Donald R. and Rast, Philippe"
    assert entry.journal == "PsyArXiv"
    assert entry.volume == "12"
    assert entry.number == "3"
    assert entry.pages == "45--67"
    assert entry.pmid == "29876543"
    assert entry.booktitle is None  # absent optional field stays None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/d/science/science && PYTHONPATH=src:model/src python -m pytest tests/test_bibliography_entries.py::test_load_bib_entries_parses_extended_fields -v`
Expected: FAIL with `AttributeError: 'BibEntry' object has no attribute 'author'`

- [ ] **Step 3: Extend the dataclass**

In `bibliography.py`, replace the `BibEntry` dataclass body (lines 91-96) so the new fields follow `url`:

```python
@dataclass(frozen=True)
class BibEntry:
    """One balanced bibliography entry — the subset Phase 4b materializes."""

    key: str
    entry_type: str = "misc"
    title: str | None = None
    year: int | None = None
    doi: str | None = None
    url: str | None = None
    author: str | None = None
    journal: str | None = None
    booktitle: str | None = None
    publisher: str | None = None
    volume: str | None = None
    number: str | None = None
    pages: str | None = None
    pmid: str | None = None
```

- [ ] **Step 4: Populate the new fields in `load_bib_entries`**

In `load_bib_entries`, replace the `entries[key] = BibEntry(...)` block (lines 160-167) with:

```python
        entries[key] = BibEntry(
            key=key,
            entry_type=entry_type,
            title=_field_value(block, "title"),
            year=year,
            doi=_field_value(block, "doi"),
            url=_field_value(block, "url"),
            author=_field_value(block, "author"),
            journal=_field_value(block, "journal"),
            booktitle=_field_value(block, "booktitle"),
            publisher=_field_value(block, "publisher"),
            volume=_field_value(block, "volume"),
            number=_field_value(block, "number"),
            pages=_field_value(block, "pages"),
            pmid=_field_value(block, "pmid"),
        )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd ~/d/science/science && PYTHONPATH=src:model/src python -m pytest tests/test_bibliography_entries.py -v`
Expected: PASS (all existing tests + the new one)

- [ ] **Step 6: Commit**

```bash
cd ~/d/science && git add science/src/science_tool/bibliography.py science/tests/test_bibliography_entries.py
git commit -m "feat(bibliography): parse extended BibEntry fields for references"
```

### Task A2: Author-name formatter

**Files:**
- Create: `~/d/science/science/src/science_tool/references.py`
- Test: `~/d/science/science/tests/test_references.py`

**Interfaces:**
- Produces: `format_authors(raw_author: str | None) -> str` — renders a BibTeX `author` field into a display string per design §5. Returns `""` for `None`/empty.

- [ ] **Step 1: Write the failing test**

Create `~/d/science/science/tests/test_references.py`:

```python
from __future__ import annotations

from science_tool.references import format_authors


def test_format_authors_last_first_with_initials() -> None:
    raw = "Williams, Donald R. and Rast, Philippe and Buerkner, Paul-Christian"
    assert format_authors(raw) == "Williams DR, Rast P, Buerkner P-C"


def test_format_authors_first_last_and_jr() -> None:
    assert format_authors("Donald Williams") == "Williams D"
    assert format_authors("King, Jr, Martin Luther") == "King ML"


def test_format_authors_braced_corporate_is_literal() -> None:
    assert format_authors("{World Health Organization}") == "World Health Organization"


def test_format_authors_truncates_beyond_six() -> None:
    raw = " and ".join(f"Last{i}, First{i}" for i in range(1, 9))  # 8 authors
    assert format_authors(raw) == "Last1 F, Last2 F, Last3 F, et al."


def test_format_authors_empty() -> None:
    assert format_authors(None) == ""
    assert format_authors("") == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/d/science/science && PYTHONPATH=src:model/src python -m pytest tests/test_references.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'science_tool.references'`

- [ ] **Step 3: Implement the formatter**

Create `~/d/science/science/src/science_tool/references.py`:

```python
"""Reference-record contract: BibTeX normalization, display formatting, the
citation-syntax grammar, and the app-export reference bundle (design doc
2026-06-23-science-citations-and-references)."""

from __future__ import annotations

import re


def _split_authors(raw: str) -> list[str]:
    """Split a BibTeX author field on top-level ` and `, respecting braces."""
    parts: list[str] = []
    depth = 0
    start = 0
    i = 0
    n = len(raw)
    while i < n:
        ch = raw[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth = max(0, depth - 1)
        elif depth == 0 and raw[i : i + 5].lower() == " and ":
            parts.append(raw[start:i])
            i += 5
            start = i
            continue
        i += 1
    parts.append(raw[start:])
    return [p.strip() for p in parts if p.strip()]


def _initials(given: str) -> str:
    """Initials from a given-name string: 'Donald R.' -> 'DR', 'Paul-Christian' -> 'P-C'."""
    out: list[str] = []
    for token in given.split():
        hyphen_parts = [p for p in token.split("-") if p]
        letters = [p[0].upper() for p in hyphen_parts if p[0].isalpha()]
        if letters:
            out.append("-".join(letters))
    return "".join(out)


def _format_one_author(name: str) -> str:
    """Render one BibTeX author name as 'Family II'."""
    name = name.strip()
    if name.startswith("{") and name.endswith("}"):
        return name[1:-1].strip()  # corporate/literal author
    if "," in name:
        fields = [f.strip() for f in name.split(",")]
        family = fields[0]
        given = fields[-1] if len(fields) >= 2 else ""  # 'Last, Jr, First' -> given is 'First'
    else:
        tokens = name.split()
        family = tokens[-1] if tokens else ""
        given = " ".join(tokens[:-1])
    initials = _initials(given)
    return f"{family} {initials}".strip() if initials else family


def format_authors(raw_author: str | None) -> str:
    """Render a BibTeX author field per design §5 (max 6, else first 3 + et al.)."""
    if not raw_author or not raw_author.strip():
        return ""
    authors = _split_authors(raw_author)
    if len(authors) > 6:
        rendered = [_format_one_author(a) for a in authors[:3]]
        return ", ".join(rendered) + ", et al."
    return ", ".join(_format_one_author(a) for a in authors)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/d/science/science && PYTHONPATH=src:model/src python -m pytest tests/test_references.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd ~/d/science && git add science/src/science_tool/references.py science/tests/test_references.py
git commit -m "feat(references): BibTeX author-name display formatter"
```

### Task A3: `ReferenceRecord` model + display formatter

**Files:**
- Modify: `~/d/science/science/src/science_tool/references.py`
- Test: `~/d/science/science/tests/test_references.py`

**Interfaces:**
- Consumes: `BibEntry` (Task A1), `format_authors` (Task A2).
- Produces:
  - `CONTRACT = "science.references"`, `SCHEMA_VERSION = "1"` module constants.
  - `reference_record(entry: BibEntry) -> dict` — returns the design §4 record dict (with `contract`, `schema_version`, `id`, `citekey`, `kind`, `title`, `authors`, `issued`, `container_title`, `publisher`, `volume`, `issue`, `pages`, `doi`, `pmid`, `url`, `display`, `source`).
  - `format_display(entry: BibEntry) -> str` — the fallback bibliography string.

- [ ] **Step 1: Write the failing test**

Add to `~/d/science/science/tests/test_references.py`:

```python
from science_tool.bibliography import BibEntry
from science_tool.references import CONTRACT, SCHEMA_VERSION, format_display, reference_record


def test_reference_record_rich() -> None:
    entry = BibEntry(
        key="Williams2018",
        entry_type="article",
        title="Bayesian Meta-Analysis",
        year=2018,
        url="https://osf.io/9n4zp/",
        author="Williams, Donald R. and Rast, Philippe",
        journal="PsyArXiv",
        volume="12",
        number="3",
        pages="45-67",
    )
    rec = reference_record(entry)
    assert rec["contract"] == CONTRACT
    assert rec["schema_version"] == SCHEMA_VERSION
    assert rec["id"] == "cite:Williams2018"
    assert rec["citekey"] == "Williams2018"
    assert rec["kind"] == "article"
    assert rec["issued"] == {"year": 2018}
    assert rec["container_title"] == "PsyArXiv"
    assert rec["authors"] == [
        {"family": "Williams", "given": "Donald R."},
        {"family": "Rast", "given": "Philippe"},
    ]
    assert rec["source"]["raw_author"] == "Williams, Donald R. and Rast, Philippe"
    assert rec["display"] == (
        "Williams DR, Rast P. Bayesian Meta-Analysis. PsyArXiv. 2018;12(3):45-67."
    )


def test_format_display_sparse_falls_back_to_citekey() -> None:
    entry = BibEntry(key="Williams2018", title="Bayesian Meta-Analysis", year=2018)
    assert format_display(entry) == "Williams2018. Bayesian Meta-Analysis. 2018."


def test_reference_record_kind_normalization() -> None:
    assert reference_record(BibEntry(key="X", entry_type="inproceedings"))["kind"] == "chapter"
    assert reference_record(BibEntry(key="X", entry_type="incollection"))["kind"] == "chapter"
    assert reference_record(BibEntry(key="X", entry_type="book"))["kind"] == "book"
    assert reference_record(BibEntry(key="X", entry_type="online"))["kind"] == "misc"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/d/science/science && PYTHONPATH=src:model/src python -m pytest tests/test_references.py -v`
Expected: FAIL with `ImportError: cannot import name 'reference_record'`

- [ ] **Step 3: Implement the model + display**

Append to `~/d/science/science/src/science_tool/references.py`:

```python
from science_tool.bibliography import BibEntry

CONTRACT = "science.references"
SCHEMA_VERSION = "1"

# BibTeX entry_type -> normalized record kind (design §4: article|book|chapter|preprint|misc).
# Driven solely by entry_type, NOT by container name: the design's §4 example maps a
# PsyArXiv @article to kind "article", so container sniffing would contradict the contract.
# "preprint" is emitted only for entry types that explicitly mean preprint.
_KIND_MAP = {
    "article": "article",
    "book": "book",
    "inbook": "chapter",
    "incollection": "chapter",
    "inproceedings": "chapter",
    "conference": "chapter",
    "preprint": "preprint",
    "unpublished": "preprint",
    "misc": "misc",
}


def _normalize_kind(entry: BibEntry) -> str:
    return _KIND_MAP.get(entry.entry_type, "misc")


def _authors_struct(raw_author: str | None) -> list[dict[str, str]]:
    if not raw_author:
        return []
    out: list[dict[str, str]] = []
    for name in _split_authors(raw_author):
        if name.startswith("{") and name.endswith("}"):
            out.append({"family": name[1:-1].strip(), "given": ""})
            continue
        if "," in name:
            fields = [f.strip() for f in name.split(",")]
            family, given = fields[0], (fields[-1] if len(fields) >= 2 else "")
        else:
            tokens = name.split()
            family = tokens[-1] if tokens else ""
            given = " ".join(tokens[:-1])
        out.append({"family": family, "given": given})
    return out


def format_display(entry: BibEntry) -> str:
    """Conservative numeric-style display string (design §5)."""
    authors = format_authors(entry.author) or entry.key
    container = entry.journal or entry.booktitle or entry.publisher
    head = f"{authors}."
    parts = [head]
    if entry.title:
        parts.append(f"{entry.title}.")
    if container:
        parts.append(f"{container}.")
    tail = ""
    if entry.year is not None:
        tail = str(entry.year)
        if entry.volume:
            tail += f";{entry.volume}"
            if entry.number:
                tail += f"({entry.number})"
            if entry.pages:
                tail += f":{entry.pages}"
        tail += "."
        parts.append(tail)
    if entry.doi:
        parts.append(f"doi:{entry.doi}.")
    return " ".join(parts)


def reference_record(entry: BibEntry) -> dict:
    """Build the design §4 reference record dict for one bibliography entry."""
    source = {"path": "papers/references.bib", "entry_type": entry.entry_type}
    if entry.author:
        source["raw_author"] = entry.author
    return {
        "contract": CONTRACT,
        "schema_version": SCHEMA_VERSION,
        "id": f"cite:{entry.key}",
        "citekey": entry.key,
        "kind": _normalize_kind(entry),
        "title": entry.title or entry.key,
        "authors": _authors_struct(entry.author),
        "issued": {"year": entry.year} if entry.year is not None else {},
        "container_title": entry.journal or entry.booktitle,
        "publisher": entry.publisher,
        "volume": entry.volume,
        "issue": entry.number,
        "pages": entry.pages,
        "doi": entry.doi,
        "pmid": entry.pmid,
        "url": entry.url,
        "display": format_display(entry),
        "source": source,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/d/science/science && PYTHONPATH=src:model/src python -m pytest tests/test_references.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd ~/d/science && git add science/src/science_tool/references.py science/tests/test_references.py
git commit -m "feat(references): ReferenceRecord model and display formatter"
```

### Task A4: Citation-syntax grammar parser + shared corpus

**Files:**
- Modify: `~/d/science/science/src/science_tool/references.py`
- Create: `~/d/science/science/tests/fixtures/citation_grammar_v1.json`
- Test: `~/d/science/science/tests/test_references.py`

**Interfaces:**
- Consumes: `science_tool.markdown_utils.is_fence_line`, `strip_inline_code` (already used by `refs.py`).
- Produces: `parse_citations(markdown: str) -> CitationScan` where `CitationScan` is a frozen dataclass with `citations: list[Citation]` and `unsupported: list[str]`. `Citation` is a frozen dataclass with `citekey: str` and `locator: str | None`. Citations preserve document order, including repeats and per-block order.

- [ ] **Step 1: Author the shared corpus fixture**

Create `~/d/science/science/tests/fixtures/citation_grammar_v1.json`:

```json
{
  "contract": "science.citation-grammar",
  "schema_version": "1",
  "cases": [
    {
      "name": "single",
      "markdown": "Background [@Smith2020].",
      "citations": [{ "citekey": "Smith2020", "locator": null }],
      "unsupported": []
    },
    {
      "name": "compound",
      "markdown": "Prior work [@Smith2020; @Jones2021].",
      "citations": [
        { "citekey": "Smith2020", "locator": null },
        { "citekey": "Jones2021", "locator": null }
      ],
      "unsupported": []
    },
    {
      "name": "locator",
      "markdown": "See [@Smith2020, p. 42].",
      "citations": [{ "citekey": "Smith2020", "locator": "p. 42" }],
      "unsupported": []
    },
    {
      "name": "narrative",
      "markdown": "Smith et al. [@Smith2020] found that...",
      "citations": [{ "citekey": "Smith2020", "locator": null }],
      "unsupported": []
    },
    {
      "name": "code-span-ignored",
      "markdown": "Use `[@NotACite]` literally.",
      "citations": [],
      "unsupported": []
    },
    {
      "name": "fenced-ignored",
      "markdown": "```\n[@NotACite]\n```\n",
      "citations": [],
      "unsupported": []
    },
    {
      "name": "unsupported-prefix",
      "markdown": "As shown [see @Smith2020].",
      "citations": [],
      "unsupported": ["Smith2020"]
    },
    {
      "name": "unsupported-suppressed",
      "markdown": "The year [-@Smith2020].",
      "citations": [],
      "unsupported": ["Smith2020"]
    },
    {
      "name": "unsupported-bare",
      "markdown": "See @Smith2020 for details.",
      "citations": [],
      "unsupported": ["Smith2020"]
    },
    {
      "name": "malformed-mixed-block",
      "markdown": "Prior work [@Smith2020; see @Jones2021].",
      "citations": [{ "citekey": "Smith2020", "locator": null }],
      "unsupported": ["Jones2021"]
    },
    {
      "name": "malformed-no-at-item",
      "markdown": "Prior work [@Smith2020; garbage].",
      "citations": [{ "citekey": "Smith2020", "locator": null }],
      "unsupported": ["garbage"]
    },
    {
      "name": "malformed-missing-comma-locator",
      "markdown": "See [@Smith2020 p. 42].",
      "citations": [],
      "unsupported": ["Smith2020 p. 42"]
    },
    {
      "name": "malformed-extra-text-before-compound",
      "markdown": "See [@Smith2020 extra; @Jones2021].",
      "citations": [{ "citekey": "Jones2021", "locator": null }],
      "unsupported": ["Smith2020 extra"]
    }
  ]
}
```

This corpus is the single source of truth for parity (design §6, 229-232). After
authoring it, record its hash so both repos can detect drift (Task A4 Step 1b and
Task C1 Step 1b):

```bash
cd ~/d/science/science && python -c "import hashlib,pathlib; \
print(hashlib.sha256(pathlib.Path('tests/fixtures/citation_grammar_v1.json').read_bytes()).hexdigest())"
```

Record the printed value as `CITATION_GRAMMAR_V1_SHA256` in both the Science and
Labnote parity tests (Steps below). It is the one constant that must be updated,
deliberately, whenever the corpus changes.

- [ ] **Step 2: Write the failing test (drives the parser against the corpus)**

Add to `~/d/science/science/tests/test_references.py`:

```python
import hashlib
import json
from pathlib import Path

from science_tool.references import parse_citations

_CORPUS = Path(__file__).parent / "fixtures" / "citation_grammar_v1.json"
# Drift guard: the identical constant lives in Labnote's test/citations.test.js.
# Both repos hash their copy of the corpus against this value, so a hand-edit to
# either copy fails CI until the corpus is re-synced and the constant updated in
# both places (deliberate, visible). Fill in with the Step 1b command output.
CITATION_GRAMMAR_V1_SHA256 = "<paste sha256 from Step 1b>"


def test_corpus_hash_is_pinned() -> None:
    digest = hashlib.sha256(_CORPUS.read_bytes()).hexdigest()
    assert digest == CITATION_GRAMMAR_V1_SHA256


def test_parse_citations_matches_shared_corpus() -> None:
    cases = json.loads(_CORPUS.read_text(encoding="utf-8"))["cases"]
    for case in cases:
        scan = parse_citations(case["markdown"])
        got = [{"citekey": c.citekey, "locator": c.locator} for c in scan.citations]
        assert got == case["citations"], case["name"]
        assert sorted(scan.unsupported) == sorted(case["unsupported"]), case["name"]
```

After the corpus file is final, run the Step 1b hash command and replace
`<paste sha256 from Step 1b>` with the printed digest.

- [ ] **Step 3: Run test to verify it fails**

Run: `cd ~/d/science/science && PYTHONPATH=src:model/src python -m pytest tests/test_references.py::test_parse_citations_matches_shared_corpus -v`
Expected: FAIL with `ImportError: cannot import name 'parse_citations'`

- [ ] **Step 4: Implement the grammar parser**

Append to `~/d/science/science/src/science_tool/references.py`:

```python
from dataclasses import dataclass

from science_tool.markdown_utils import is_fence_line, strip_inline_code

# Outer block detector (design §6): a bracketed run whose first non-space char is '@'.
_BLOCK_RE = re.compile(r"\[\s*@[^\]]*\]")
# Any @citekey-shaped token, used for unsupported-syntax detection.
_BARE_AT_RE = re.compile(r"@([A-Za-z][A-Za-z0-9_:.\-]*)")
# A bare citekey within an item: text after '@' until whitespace/comma/semicolon/bracket.
_ITEM_KEY_RE = re.compile(r"@\s*([^\s,;\]]+)")


@dataclass(frozen=True)
class Citation:
    citekey: str
    locator: str | None


@dataclass(frozen=True)
class CitationScan:
    citations: list[Citation]
    unsupported: list[str]


def _parse_block(inner: str) -> tuple[list[Citation], list[str]]:
    """Parse the inside of a recognized `[@...]` block.

    Returns (citations, unsupported). A `;`-separated item that does not begin
    with `@<citekey>` is malformed (e.g. `see @Jones2021` in
    `[@Smith2020; see @Jones2021]`). Such an item is NOT silently dropped — its
    `@`-tokens (or, failing that, its raw text) are reported as unsupported so
    Science export fails closed instead of losing a citation.
    """
    citations: list[Citation] = []
    unsupported: list[str] = []
    for raw_item in inner.split(";"):
        item = raw_item.strip()
        if not item:
            continue
        key_match = _ITEM_KEY_RE.match(item)
        if key_match:
            citekey = key_match.group(1)
            rest = item[key_match.end():].strip()
            locator = None
            if rest:
                if not rest.startswith(","):
                    unsupported.append(item)
                    continue
                locator = rest[1:].strip() or None
            citations.append(Citation(citekey=citekey, locator=locator))
            continue
        ats = _BARE_AT_RE.findall(item)
        unsupported.extend(ats if ats else [item])
    return citations, unsupported


def _prose_lines(markdown: str) -> list[str]:
    """Lines with inline code stripped and fenced-code blocks removed."""
    lines: list[str] = []
    in_fence = False
    for line in markdown.splitlines():
        if is_fence_line(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        lines.append(strip_inline_code(line))
    return lines


def parse_citations(markdown: str) -> CitationScan:
    """Parse Markdown into the v1 citation grammar (design §6).

    Recognizes only `[@key ...]` blocks. `@key` tokens that are not inside a
    recognized block (bare `@key`, `[see @key]`, `[-@key]`) are reported as
    unsupported syntax, never silently dropped.
    """
    citations: list[Citation] = []
    unsupported: list[str] = []
    for line in _prose_lines(markdown):
        consumed_spans: list[tuple[int, int]] = []
        for block in _BLOCK_RE.finditer(line):
            block_citations, block_unsupported = _parse_block(block.group(0)[1:-1])
            citations.extend(block_citations)
            unsupported.extend(block_unsupported)
            consumed_spans.append(block.span())
        for at in _BARE_AT_RE.finditer(line):
            if any(start <= at.start() < end for start, end in consumed_spans):
                continue
            unsupported.append(at.group(1))
    return CitationScan(citations=citations, unsupported=unsupported)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd ~/d/science/science && PYTHONPATH=src:model/src python -m pytest tests/test_references.py -v`
Expected: PASS (all corpus cases)

- [ ] **Step 6: Commit**

```bash
cd ~/d/science && git add science/src/science_tool/references.py science/tests/test_references.py science/tests/fixtures/citation_grammar_v1.json
git commit -m "feat(references): v1 citation-syntax grammar parser + shared corpus"
```

### Task A5: Reference-bundle builder (with duplicate-citekey detection)

Malformed/unbalanced BibTeX entries remain excluded by `load_bib_entries`; they do not produce
reference records, and any exported prose that cites them fails later as `unknown-citekey`.
`load_bib_entries` returns a `dict` keyed by citekey, so a duplicate `@article{Smith2020,...}`
silently overwrites its predecessor — duplicates can never reach the builder. Per the
fail-closed contract (design §5, "Duplicate citekeys are errors") the builder must detect
duplicates by scanning the *raw* entries before the dict collapses them. This task adds a
raw-key scanner to `bibliography.py` and a duplicate gate to the builder.

**Files:**
- Modify: `~/d/science/science/src/science_tool/bibliography.py` (add `raw_bib_entry_keys`)
- Modify: `~/d/science/science/src/science_tool/references.py`
- Test: `~/d/science/science/tests/test_references.py`, `~/d/science/science/tests/test_bibliography_entries.py`

**Interfaces:**
- Consumes: `load_bib_entries`, `raw_bib_entry_keys` (bibliography.py), `reference_record` (A3).
- Produces:
  - `bibliography.raw_bib_entry_keys(project_root: Path) -> list[str]` — every `@type{key,` key in file order, including duplicates (uses the existing `_BIBTEX_ENTRY_TYPED_RE`).
  - `references.DuplicateCitekeyError(ValueError)` with `.duplicates: dict[str, int]` (citekey → count).
  - `references.build_reference_bundle(project_root: Path) -> dict` — the design §7 bundle `{"contract", "schema_version", "style": "numeric", "references": {citekey: record}, "unresolved": {}}`. Raises `DuplicateCitekeyError` when any citekey appears more than once in the raw bibliography.

- [ ] **Step 1: Write the failing test**

Add to `~/d/science/science/tests/test_references.py`:

```python
from science_tool.references import build_reference_bundle


def test_build_reference_bundle_shape(tmp_path: Path) -> None:
    (tmp_path / "papers").mkdir()
    (tmp_path / "papers" / "references.bib").write_text(
        "@article{Williams2018,\n  author = {Williams, Donald R.},\n"
        "  title = {Bayesian Meta-Analysis},\n  journal = {PsyArXiv},\n  year = {2018},\n}\n",
        encoding="utf-8",
    )
    bundle = build_reference_bundle(tmp_path)
    assert bundle["contract"] == "science.references"
    assert bundle["schema_version"] == "1"
    assert bundle["style"] == "numeric"
    assert bundle["unresolved"] == {}
    rec = bundle["references"]["Williams2018"]
    assert rec["id"] == "cite:Williams2018"
    assert rec["display"].startswith("Williams DR. Bayesian Meta-Analysis.")


def test_build_reference_bundle_includes_all_entries_not_only_cited(tmp_path: Path) -> None:
    (tmp_path / "papers").mkdir()
    (tmp_path / "papers" / "references.bib").write_text(
        "@article{A2020,\n  title = {A},\n  year = {2020},\n}\n\n"
        "@article{B2021,\n  title = {B},\n  year = {2021},\n}\n",
        encoding="utf-8",
    )
    bundle = build_reference_bundle(tmp_path)
    assert set(bundle["references"]) == {"A2020", "B2021"}  # locked decision §16.1


def test_build_reference_bundle_rejects_duplicate_citekeys(tmp_path: Path) -> None:
    (tmp_path / "papers").mkdir()
    (tmp_path / "papers" / "references.bib").write_text(
        "@article{Dup2020,\n  title = {First},\n  year = {2020},\n}\n\n"
        "@article{Dup2020,\n  title = {Second},\n  year = {2021},\n}\n",
        encoding="utf-8",
    )
    with pytest.raises(DuplicateCitekeyError) as exc:
        build_reference_bundle(tmp_path)
    assert exc.value.duplicates == {"Dup2020": 2}
```

Also add a `raw_bib_entry_keys` test to `~/d/science/science/tests/test_bibliography_entries.py`:

```python
def test_raw_bib_entry_keys_preserves_duplicates(tmp_path: Path) -> None:
    from science_tool.bibliography import raw_bib_entry_keys

    _write_bib(
        tmp_path,
        "@article{Dup2020,\n  title = {First},\n}\n\n@article{Dup2020,\n  title = {Second},\n}\n",
    )
    assert raw_bib_entry_keys(tmp_path) == ["Dup2020", "Dup2020"]
```

(Import `DuplicateCitekeyError` and `pytest` at the top of `test_references.py` alongside the
existing imports.)

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/d/science/science && PYTHONPATH=src:model/src python -m pytest tests/test_references.py -k build_reference_bundle -v`
Expected: FAIL with `ImportError: cannot import name 'build_reference_bundle'`

- [ ] **Step 3: Add the raw-key scanner to `bibliography.py`**

In `bibliography.py`, after `load_bib_keys` (around line 46), add:

```python
def raw_bib_entry_keys(project_root: Path) -> list[str]:
    """Return every BibTeX entry key in file order, INCLUDING duplicates.

    Unlike load_bib_keys (a set) and load_bib_entries (a dict), this preserves
    repeats so callers can detect duplicate citekeys, which the dict/set forms
    silently collapse.
    """
    bib_path = project_root / "papers" / "references.bib"
    if not bib_path.is_file():
        return []
    text = bib_path.read_text(encoding="utf-8")
    return [m.group(2) for m in _BIBTEX_ENTRY_TYPED_RE.finditer(text)]
```

- [ ] **Step 4: Implement the builder with the duplicate gate**

Append to `~/d/science/science/src/science_tool/references.py`:

```python
from collections import Counter
from pathlib import Path

from science_tool.bibliography import load_bib_entries, raw_bib_entry_keys


class DuplicateCitekeyError(ValueError):
    """Raised when papers/references.bib declares the same citekey more than once."""

    def __init__(self, duplicates: dict[str, int]) -> None:
        self.duplicates = duplicates
        listed = ", ".join(f"{key} (x{count})" for key, count in sorted(duplicates.items()))
        super().__init__(f"duplicate citekeys in papers/references.bib: {listed}")


def build_reference_bundle(project_root: Path) -> dict:
    """Build the app-export reference bundle from papers/references.bib (design §7).

    Includes ALL normalized bibliography records, not only cited ones (locked
    decision §16.1). Fails closed on duplicate citekeys (design §5). `unresolved`
    is empty here; partial-export callers populate it via validate_exported_markdown.
    """
    counts = Counter(raw_bib_entry_keys(project_root))
    duplicates = {key: n for key, n in counts.items() if n > 1}
    if duplicates:
        raise DuplicateCitekeyError(duplicates)
    entries = load_bib_entries(project_root)
    references = {key: reference_record(entry) for key, entry in entries.items()}
    return {
        "contract": CONTRACT,
        "schema_version": SCHEMA_VERSION,
        "style": "numeric",
        "references": references,
        "unresolved": {},
    }
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd ~/d/science/science && PYTHONPATH=src:model/src python -m pytest tests/test_references.py tests/test_bibliography_entries.py -v`
Expected: PASS (bundle shape, all-entries, duplicate rejection, raw-key duplicates)

- [ ] **Step 6: Commit**

```bash
cd ~/d/science && git add science/src/science_tool/references.py science/src/science_tool/bibliography.py science/tests/test_references.py science/tests/test_bibliography_entries.py
git commit -m "feat(references): reference bundle builder with duplicate-citekey gate"
```

### Task A6: Fail-closed export validation

**Files:**
- Modify: `~/d/science/science/src/science_tool/references.py`
- Test: `~/d/science/science/tests/test_references.py`

**Interfaces:**
- Consumes: `parse_citations` (A4).
- Produces:
  - `class UnresolvedCitationError(ValueError)` with `.unresolved: dict[str, list[dict]]`.
  - `class UnsupportedCitationSyntaxError(ValueError)`.
  - `MarkdownPayload` = a frozen dataclass `(path: str, field: str, text: str)`.
  - `validate_exported_markdown(payloads: list[MarkdownPayload], known_citekeys: set[str], *, allow_partial: bool = False) -> dict[str, list[dict]]` — scans payloads; raises `UnsupportedCitationSyntaxError` on any unsupported token; raises `UnresolvedCitationError` on unknown citekeys unless `allow_partial`, in which case returns the `unresolved` map (design §7 shape).

- [ ] **Step 1: Write the failing test**

Add to `~/d/science/science/tests/test_references.py`:

```python
import pytest

from science_tool.references import (
    MarkdownPayload,
    UnresolvedCitationError,
    UnsupportedCitationSyntaxError,
    validate_exported_markdown,
)


def _payload(text: str) -> list[MarkdownPayload]:
    return [MarkdownPayload(path="findings/leads/x.json", field="sections[0].body", text=text)]


def test_validate_passes_known_keys() -> None:
    assert validate_exported_markdown(_payload("ok [@Smith2020]"), {"Smith2020"}) == {}


def test_validate_fails_closed_on_unknown_key() -> None:
    with pytest.raises(UnresolvedCitationError) as exc:
        validate_exported_markdown(_payload("bad [@Missing2026]"), {"Smith2020"})
    assert "Missing2026" in exc.value.unresolved


def test_validate_partial_returns_unresolved_block() -> None:
    unresolved = validate_exported_markdown(
        _payload("bad [@Missing2026]"), {"Smith2020"}, allow_partial=True
    )
    entry = unresolved["Missing2026"][0]
    assert entry["citekey"] == "Missing2026"
    assert entry["reason"] == "unknown-citekey"
    assert entry["path"] == "findings/leads/x.json"
    assert entry["field"] == "sections[0].body"
    assert "Missing2026" in entry["snippet"]


def test_validate_fails_on_unsupported_syntax_even_with_partial() -> None:
    with pytest.raises(UnsupportedCitationSyntaxError):
        validate_exported_markdown(_payload("see [-@Smith2020]"), {"Smith2020"}, allow_partial=True)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/d/science/science && PYTHONPATH=src:model/src python -m pytest tests/test_references.py -k validate -v`
Expected: FAIL with `ImportError: cannot import name 'validate_exported_markdown'`

- [ ] **Step 3: Implement the validators**

Append to `~/d/science/science/src/science_tool/references.py`:

```python
class UnsupportedCitationSyntaxError(ValueError):
    """Raised when exported prose uses citation syntax outside the v1 grammar."""


class UnresolvedCitationError(ValueError):
    """Raised when exported prose cites a key absent from the bibliography."""

    def __init__(self, unresolved: dict[str, list[dict]]) -> None:
        self.unresolved = unresolved
        keys = ", ".join(sorted(unresolved))
        super().__init__(f"unresolved citation keys in exported prose: {keys}")


@dataclass(frozen=True)
class MarkdownPayload:
    path: str
    field: str
    text: str


def _snippet(text: str, citekey: str) -> str:
    idx = text.find(citekey)
    if idx == -1:
        return text[:60]
    start = max(0, idx - 20)
    end = min(len(text), idx + len(citekey) + 20)
    return f"... {text[start:end]} ..."


def validate_exported_markdown(
    payloads: list[MarkdownPayload],
    known_citekeys: set[str],
    *,
    allow_partial: bool = False,
) -> dict[str, list[dict]]:
    """Scan exported Markdown for citation keys (design §7). Fail-closed.

    - Any unsupported-syntax token (`[see @x]`, `[-@x]`, bare `@x`) raises
      UnsupportedCitationSyntaxError regardless of allow_partial.
    - Unknown citekeys raise UnresolvedCitationError unless allow_partial, in
      which case the design §7 `unresolved` map is returned instead.
    """
    unsupported_hits: list[str] = []
    unresolved: dict[str, list[dict]] = {}
    for payload in payloads:
        scan = parse_citations(payload.text)
        for token in scan.unsupported:
            unsupported_hits.append(f"{payload.path}:{payload.field} @{token}")
        for cite in scan.citations:
            if cite.citekey in known_citekeys:
                continue
            unresolved.setdefault(cite.citekey, []).append(
                {
                    "citekey": cite.citekey,
                    "reason": "unknown-citekey",
                    "path": payload.path,
                    "field": payload.field,
                    "snippet": _snippet(payload.text, cite.citekey),
                }
            )
    if unsupported_hits:
        raise UnsupportedCitationSyntaxError(
            "unsupported citation syntax (use [@key] only): " + "; ".join(unsupported_hits)
        )
    if unresolved and not allow_partial:
        raise UnresolvedCitationError(unresolved)
    return unresolved
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/d/science/science && PYTHONPATH=src:model/src python -m pytest tests/test_references.py -k validate -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd ~/d/science && git add science/src/science_tool/references.py science/tests/test_references.py
git commit -m "feat(references): fail-closed export citation validation"
```

### Task A7: Authoring lint for unsupported citation syntax

**Files:**
- Read first: `~/d/science/science/src/science_tool/prose_lint.py` (understand how `_NEARBY_BIBTEX_RE` at line 63 and existing lint findings are produced/emitted)
- Modify: `~/d/science/science/src/science_tool/prose_lint.py`
- Test: `~/d/science/science/tests/test_prose_lint.py` (or the existing prose-lint test module — confirm its name with `ls tests | grep prose`)

**Interfaces:**
- Consumes: `parse_citations` (A4).
- Produces: a new lint check that, for each scanned prose file, emits a finding for every `parse_citations(text).unsupported` token, so authors are warned before export. Reuse the existing prose-lint finding/issue type and emission path; do not invent a new reporting channel.

- [ ] **Step 1: Read the existing lint structure**

Run: `cd ~/d/science/science && grep -n "def \|Issue\|Finding\|append\|severity" src/science_tool/prose_lint.py | head -40`
Expected: identifies the finding dataclass and the per-file scan loop to hook into. Match its exact field names in Step 3.

- [ ] **Step 2: Write the failing test**

Add a test to the prose-lint test module (mirror the file-writing pattern already used there). Example:

```python
def test_prose_lint_flags_unsupported_citation_syntax(tmp_path: Path) -> None:
    doc = tmp_path / "doc"
    doc.mkdir()
    (doc / "note.md").write_text("Background: see @Smith2020 and [-@Jones2021].\n", encoding="utf-8")
    findings = run_prose_lint(tmp_path)  # use the module's actual entry point
    messages = " ".join(f.message for f in findings)
    assert "Smith2020" in messages
    assert "unsupported citation syntax" in messages.lower()
```

Adjust `run_prose_lint` / `f.message` to the real entry point and field names found in Step 1.

- [ ] **Step 3: Run test to verify it fails**

Run: `cd ~/d/science/science && PYTHONPATH=src:model/src python -m pytest tests/test_prose_lint.py -k unsupported_citation -v`
Expected: FAIL (no such finding emitted)

- [ ] **Step 4: Implement the lint check**

In `prose_lint.py`, import `parse_citations` and, inside the existing per-file prose scan, after the body text is available, emit one finding per unsupported token:

```python
from science_tool.references import parse_citations

# inside the per-file scan, with `text` = file body and the module's finding ctor:
for token in parse_citations(text).unsupported:
    findings.append(
        ProseLintFinding(  # use the module's real finding type + fields
            file=rel_path,
            message=(
                f"unsupported citation syntax '@{token}' — v1 supports only [@{token}]; "
                "rewrite prefixed/suppressed/bare forms"
            ),
            severity="warn",
        )
    )
```

Match `ProseLintFinding`, `findings`, and field names to the real module.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd ~/d/science/science && PYTHONPATH=src:model/src python -m pytest tests/test_prose_lint.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
cd ~/d/science && git add science/src/science_tool/prose_lint.py science/tests/test_prose_lint.py
git commit -m "feat(prose-lint): warn on unsupported citation syntax pre-export"
```

---

## Phase B — MM30 app_export adoption (Python)

MM30 lives at `~/d/cancer/cancer-types/multiple-myeloma`. The app_export stage is at `scripts/stages/app_export/`. `science_tool` is importable in MM30's env (MM30 is a Science project). Re-verify the MM30 working branch before committing — the working copy is Dropbox-synced and HEAD can switch mid-session.

### Task B1: `build_references.py` export step

**Files:**
- Read first: `~/d/cancer/cancer-types/multiple-myeloma/scripts/stages/app_export/findings/build_findings.py` and `findings/resource_helpers.py` (mirror how a bundle file is written + inventoried). **Also open a real built `out_dir`** (the findings bundle, e.g. `findings/index.json`, and the entity-prose bundle) and record the exact JSON field paths for `narrative`, `sections[*]`, `synthesis`, `propositions[*].text`, and entity-prose block `text`. `collect_markdown_payloads` (below) must match those real paths — the Step 1 test fixture encodes them.
- Create: `~/d/cancer/cancer-types/multiple-myeloma/scripts/stages/app_export/build_references.py`
- Create: `~/d/cancer/cancer-types/multiple-myeloma/scripts/stages/app_export/tests/test_build_references.py` (mirror the existing app_export test location — confirm with `find scripts/stages/app_export -name 'test_*'`)

**Interfaces:**
- Consumes: `science_tool.references.build_reference_bundle`, `validate_exported_markdown`, `MarkdownPayload`; `findings.resource_helpers.resource_entry`.
- Produces:
  - `collect_markdown_payloads(out_dir: Path) -> list[MarkdownPayload]` — reads the already-built app-export JSON in `out_dir` and yields one `MarkdownPayload(path, field, text)` per Markdown-bearing field enumerated in design §7: finding `narrative`, each `sections[*]` body, `synthesis`, each `propositions[*].text`, and each entity-prose block `text`. This is the function the whole fail-closed guarantee depends on, so it is tested directly.
  - `build_references(*, project_root: Path, out_dir: Path, markdown_payloads: list[MarkdownPayload]) -> dict` that (1) builds the bundle, (2) calls `validate_exported_markdown(payloads, set(bundle["references"]))` fail-closed, (3) writes `out_dir/references/index.json`, (4) writes `out_dir/references_resources.json` with one `resource_entry(out_dir, "references/index.json", "bundle", "application/json")`.
  - `main()` wires `collect_markdown_payloads(out_dir)` into `build_references(...)` — no payload logic lives in `main()` itself.

- [ ] **Step 1: Write the failing test**

Create the test (validate fail-closed + file written + inventory shape):

```python
from __future__ import annotations

import json
from pathlib import Path

import pytest

from science_tool.references import MarkdownPayload, UnresolvedCitationError
from build_references import build_references  # adjust import to app_export package layout


def _project(tmp_path: Path) -> Path:
    (tmp_path / "papers").mkdir(parents=True)
    (tmp_path / "papers" / "references.bib").write_text(
        "@article{Shi2025,\n  title = {Shi study},\n  year = {2025},\n}\n", encoding="utf-8"
    )
    return tmp_path


def test_build_references_writes_bundle_and_inventory(tmp_path: Path) -> None:
    project = _project(tmp_path)
    out = tmp_path / "out"
    out.mkdir()
    payloads = [MarkdownPayload(path="findings/leads/lead3.json", field="narrative", text="See [@Shi2025].")]
    build_references(project_root=project, out_dir=out, markdown_payloads=payloads)

    bundle = json.loads((out / "references" / "index.json").read_text())
    assert bundle["references"]["Shi2025"]["id"] == "cite:Shi2025"

    inv = json.loads((out / "references_resources.json").read_text())
    assert inv[0]["kind"] == "bundle"
    assert inv[0]["path"] == "references/index.json"
    assert inv[0]["media_type"] == "application/json"
    assert isinstance(inv[0]["bytes"], int) and inv[0]["sha256"]


def test_build_references_fails_closed_on_unknown_key(tmp_path: Path) -> None:
    project = _project(tmp_path)
    out = tmp_path / "out"
    out.mkdir()
    payloads = [MarkdownPayload(path="findings/leads/lead3.json", field="narrative", text="See [@Missing2026].")]
    with pytest.raises(UnresolvedCitationError):
        build_references(project_root=project, out_dir=out, markdown_payloads=payloads)
```

Then add a test for the payload collector. **Build the fixture from the real JSON shapes
recorded in the read-first step** — the structure below is the design §7 contract; adjust
field names/nesting to match the actual built bundles before relying on it:

```python
from build_references import collect_markdown_payloads


def test_collect_markdown_payloads_covers_all_surfaces(tmp_path: Path) -> None:
    out = tmp_path / "out"
    (out / "findings").mkdir(parents=True)
    (out / "findings" / "index.json").write_text(json.dumps({
        "findings": [{
            "id": "lead3",
            "narrative": "Narrative [@A].",
            "sections": [{"body": "Section [@B]."}],
            "synthesis": "Synthesis [@C].",
            "propositions": [{"text": "Proposition [@D]."}],
        }],
    }))
    (out / "entity_prose.json").write_text(json.dumps({
        "modules": [{"blocks": [{"text": "Prose [@E]."}]}],
    }))

    payloads = collect_markdown_payloads(out)
    fields_to_keys = {p.field: p.text for p in payloads}
    # every enumerated surface contributes a payload (design §7)
    assert any("[@A]" in t for t in fields_to_keys.values())  # narrative
    assert any("[@B]" in t for t in fields_to_keys.values())  # sections[*]
    assert any("[@C]" in t for t in fields_to_keys.values())  # synthesis
    assert any("[@D]" in t for t in fields_to_keys.values())  # propositions[*].text
    assert any("[@E]" in t for t in fields_to_keys.values())  # entity prose block text
    # every payload carries a source path + field for diagnostics
    assert all(p.path and p.field for p in payloads)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/d/cancer/cancer-types/multiple-myeloma && python -m pytest scripts/stages/app_export/tests/test_build_references.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'build_references'`

- [ ] **Step 3: Implement the step**

Create `build_references.py`:

```python
# MM30_SCRIPT_METADATA
# task_ids: []
# workflow: workflows/stages/app_export.smk
# decision_bearing: true
# status: workflow-owned
# MM30_SCRIPT_METADATA_END
"""Export the generic Science reference bundle into the app data package.

Calls the Science reference-bundle builder (no MM30-owned reference schema),
validates exported prose citations fail-closed, writes references/index.json,
and emits the references_resources.json inventory fragment with bytes + sha256.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from science_tool.references import (
    MarkdownPayload,
    build_reference_bundle,
    validate_exported_markdown,
)

from findings.resource_helpers import resource_entry


def _finding_payloads(out_dir: Path) -> list[MarkdownPayload]:
    """Markdown fields of each finding (design §7). Adjust the JSON paths to the
    real built findings bundle recorded in the read-first step."""
    path = out_dir / "findings" / "index.json"
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    rel = "findings/index.json"
    payloads: list[MarkdownPayload] = []
    for finding in data.get("findings", []):
        fid = finding.get("id", "?")
        if isinstance(finding.get("narrative"), str):
            payloads.append(MarkdownPayload(rel, f"findings[{fid}].narrative", finding["narrative"]))
        for i, section in enumerate(finding.get("sections", []) or []):
            body = section.get("body")
            if isinstance(body, str):
                payloads.append(MarkdownPayload(rel, f"findings[{fid}].sections[{i}].body", body))
        if isinstance(finding.get("synthesis"), str):
            payloads.append(MarkdownPayload(rel, f"findings[{fid}].synthesis", finding["synthesis"]))
        for i, prop in enumerate(finding.get("propositions", []) or []):
            text = prop.get("text")
            if isinstance(text, str):
                payloads.append(MarkdownPayload(rel, f"findings[{fid}].propositions[{i}].text", text))
    return payloads


def _entity_prose_payloads(out_dir: Path) -> list[MarkdownPayload]:
    """Markdown text of each exported entity-prose block (design §7)."""
    path = out_dir / "entity_prose.json"  # confirm the real filename in the read-first step
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    rel = "entity_prose.json"
    payloads: list[MarkdownPayload] = []
    for m, module in enumerate(data.get("modules", []) or []):
        for b, block in enumerate(module.get("blocks", []) or []):
            text = block.get("text")
            if isinstance(text, str):
                payloads.append(MarkdownPayload(rel, f"modules[{m}].blocks[{b}].text", text))
    return payloads


def collect_markdown_payloads(out_dir: Path) -> list[MarkdownPayload]:
    """All Markdown-bearing app-export fields the citation scanner must cover (design §7)."""
    return _finding_payloads(out_dir) + _entity_prose_payloads(out_dir)


def build_references(
    *, project_root: Path, out_dir: Path, markdown_payloads: list[MarkdownPayload]
) -> dict:
    bundle = build_reference_bundle(project_root)
    validate_exported_markdown(markdown_payloads, set(bundle["references"]))
    refs_dir = out_dir / "references"
    refs_dir.mkdir(parents=True, exist_ok=True)
    (refs_dir / "index.json").write_text(json.dumps(bundle, indent=2), encoding="utf-8")
    inventory = [resource_entry(out_dir, "references/index.json", "bundle", "application/json")]
    (out_dir / "references_resources.json").write_text(json.dumps(inventory, indent=2), encoding="utf-8")
    return bundle


def main() -> None:
    import argparse

    from paths import app_export_out

    parser = argparse.ArgumentParser(description="Export the Science reference bundle")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    out_dir = args.out or app_export_out()
    build_references(
        project_root=args.project_root,
        out_dir=out_dir,
        markdown_payloads=collect_markdown_payloads(out_dir),
    )


if __name__ == "__main__":
    main()
```

The exact JSON field paths in `_finding_payloads` / `_entity_prose_payloads` are derived
from the design §7 surface list; reconcile them with the real built bundles (read-first
step) so the `collect_markdown_payloads` test fixture and these readers agree.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/d/cancer/cancer-types/multiple-myeloma && python -m pytest scripts/stages/app_export/tests/test_build_references.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd ~/d/cancer/cancer-types/multiple-myeloma && git rev-parse --abbrev-ref HEAD  # verify branch first
git add scripts/stages/app_export/build_references.py scripts/stages/app_export/tests/test_build_references.py
git commit -m "feat(app_export): export Science reference bundle with fail-closed validation"
```

### Task B2: Register the references bundle in the manifest

**Files:**
- Modify: `~/d/cancer/cancer-types/multiple-myeloma/scripts/stages/app_export/build_manifest.py:29-35` (the `INVENTORY_FILES` tuple)
- Modify: `~/d/cancer/cancer-types/multiple-myeloma/workflows/stages/app_export.smk` (add the build_references rule before manifest; confirm rule wiring by reading the smk file)
- Test: `~/d/cancer/cancer-types/multiple-myeloma/scripts/stages/app_export/tests/test_app_export_manifest.py`

**Interfaces:**
- Consumes: `references_resources.json` (Task B1).
- Produces: `manifest.json` includes the `references/index.json` bundle resource (passed through with `bytes`/`sha256`/`media_type` by the existing `kind == "bundle"` branch at `build_manifest.py:148-159`).

- [ ] **Step 1: Write the failing test**

Add to `test_app_export_manifest.py` (mirror its existing fixture style that writes inventory fragments then calls `build_manifest`):

```python
def test_manifest_includes_references_bundle(tmp_path: Path) -> None:
    (tmp_path / "references_resources.json").write_text(
        json.dumps([{
            "name": "references/index.json", "path": "references/index.json",
            "kind": "bundle", "sensitivity": "public",
            "bytes": 42, "sha256": "abc", "media_type": "application/json",
        }]),
    )
    manifest = build_manifest(out_dir=tmp_path, data_version="0")
    refs = [r for r in manifest["resources"] if r["path"] == "references/index.json"]
    assert len(refs) == 1
    assert refs[0]["kind"] == "bundle"
    assert refs[0]["media_type"] == "application/json"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/d/cancer/cancer-types/multiple-myeloma && python -m pytest scripts/stages/app_export/tests/test_app_export_manifest.py -k references_bundle -v`
Expected: FAIL — the resource is absent because `references_resources.json` is not in `INVENTORY_FILES`.

- [ ] **Step 3: Register the inventory fragment**

In `build_manifest.py`, add `"references_resources.json"` to the `INVENTORY_FILES` tuple:

```python
INVENTORY_FILES = (
    "resources.json",
    "index_resources.json",
    "findings_resources.json",
    "links_resources.json",
    "descriptor_resources.json",
    "references_resources.json",
)
```

Then add the `app_export_references` rule to `app_export.smk` so `build_references.py` runs before `build_manifest.py` and its output is a manifest input (mirror the `findings`/`descriptor` rule wiring).

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/d/cancer/cancer-types/multiple-myeloma && python -m pytest scripts/stages/app_export/tests/test_app_export_manifest.py -v`
Expected: PASS

- [ ] **Step 5: Re-export and sync, then commit**

```bash
cd ~/d/cancer/cancer-types/multiple-myeloma && git rev-parse --abbrev-ref HEAD
# Run the app_export stage per the project's normal command, then sync into Labnote.
git add scripts/stages/app_export/build_manifest.py workflows/stages/app_export.smk scripts/stages/app_export/tests/test_app_export_manifest.py
git commit -m "feat(app_export): register references bundle in manifest.json"
```

---

## Phase C — Labnote (JS)

Labnote lives at `~/d/labnote`. Tests use vitest (`npm test`) + jsdom; e2e uses playwright (`npm run test:e2e`). New module: `src/app/citations.js`. The shared corpus from Task A4 must be synced to `~/d/labnote/test/fixtures/citation_grammar_v1.json` (the same file content as `science/tests/fixtures/citation_grammar_v1.json`, via the normal cross-repo sync path — copy it as part of Task C1).

### Task C1: Citation grammar parser (parity with Science)

**Files:**
- Create: `~/d/labnote/src/app/citations.js`
- Create: `~/d/labnote/test/fixtures/citation_grammar_v1.json` (exact copy of the Science corpus)
- Test: `~/d/labnote/test/citations.test.js`

**Interfaces:**
- Produces: `parseCitations(markdown: string) -> { citations: Array<{citekey, locator}>, unsupported: string[] }` — same semantics and outputs as Python `parse_citations`. Locator is `null` when absent. Code spans (backtick runs) and fenced blocks are ignored.

- [ ] **Step 1: Sync the Science-owned corpus + write the failing parity + drift-guard tests**

The corpus is owned by Science (Task A4). It is a *test fixture*, so the package `cp`
sync in `sync-data.mjs` (which only copies `package_source.path` → `src/data/package`) does
NOT carry it — bring it over the cross-repo path explicitly and pin its hash so the JS copy
cannot silently drift from the Python source:

```bash
cp ~/d/science/science/tests/fixtures/citation_grammar_v1.json \
   ~/d/labnote/test/fixtures/citation_grammar_v1.json
```

Create `~/d/labnote/test/citations.test.js`. `CITATION_GRAMMAR_V1_SHA256` is the SAME
constant pinned in Science's `test_references.py` (Task A4) — both repos hashing their copy
against one value is what enforces byte-for-byte parity:

```js
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { parseCitations } from "../src/app/citations.js";

const corpusPath = fileURLToPath(new URL("./fixtures/citation_grammar_v1.json", import.meta.url));
const corpusBytes = readFileSync(corpusPath);
const corpus = JSON.parse(corpusBytes);

// Identical to CITATION_GRAMMAR_V1_SHA256 in ~/d/science/science/tests/test_references.py.
const CITATION_GRAMMAR_V1_SHA256 = "<paste the same sha256 pinned in Science>";

describe("citation grammar corpus", () => {
  it("matches the Science-owned corpus hash (drift guard)", () => {
    expect(createHash("sha256").update(corpusBytes).digest("hex")).toBe(CITATION_GRAMMAR_V1_SHA256);
  });

  for (const c of corpus.cases) {
    it(`parity: ${c.name}`, () => {
      const scan = parseCitations(c.markdown);
      const got = scan.citations.map((x) => ({ citekey: x.citekey, locator: x.locator }));
      expect(got).toEqual(c.citations);
      expect([...scan.unsupported].sort()).toEqual([...c.unsupported].sort());
    });
  }
});
```

If the corpus ever changes, it is edited only in Science; re-run the `cp` and update the
single pinned hash in both repos — a deliberate, reviewable two-line change. Editing the JS
copy alone fails the drift-guard test.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/d/labnote && npx vitest run test/citations.test.js`
Expected: FAIL — `parseCitations` is not exported.

- [ ] **Step 3: Implement the parser**

Create `~/d/labnote/src/app/citations.js`:

```js
// v1 citation-syntax grammar (design §6). Must stay parity-equal to Science's
// science_tool.references.parse_citations — both are checked against
// test/fixtures/citation_grammar_v1.json.

const BLOCK_RE = /\[\s*@[^\]]*\]/g;
const BARE_AT_RE = /@([A-Za-z][A-Za-z0-9_:.\-]*)/g;
const ITEM_KEY_RE = /^@\s*([^\s,;\]]+)/;

function proseLines(markdown) {
  const lines = [];
  let inFence = false;
  for (const raw of String(markdown).split("\n")) {
    if (/^\s*(```|~~~)/.test(raw)) {
      inFence = !inFence;
      continue;
    }
    if (inFence) continue;
    lines.push(raw.replace(/`[^`]*`/g, ""));
  }
  return lines;
}

function parseBlock(inner) {
  // Mirrors Python _parse_block: a ;-item that does not start with @<key> is
  // malformed; its @-tokens (or raw text) are reported unsupported, never dropped.
  const citations = [];
  const unsupported = [];
  for (const rawItem of inner.split(";")) {
    const item = rawItem.trim();
    if (item === "") continue;
    const m = ITEM_KEY_RE.exec(item);
    if (m) {
      const rest = item.slice(m[0].length).trim();
      let locator = null;
      if (rest) {
        if (!rest.startsWith(",")) {
          unsupported.push(item);
          continue;
        }
        const loc = rest.slice(1).trim();
        locator = loc === "" ? null : loc;
      }
      citations.push({ citekey: m[1], locator });
      continue;
    }
    const ats = [...item.matchAll(BARE_AT_RE)].map((x) => x[1]);
    if (ats.length) unsupported.push(...ats);
    else unsupported.push(item);
  }
  return { citations, unsupported };
}

export function parseCitations(markdown) {
  const citations = [];
  const unsupported = [];
  for (const line of proseLines(markdown)) {
    const spans = [];
    for (const block of line.matchAll(BLOCK_RE)) {
      const parsed = parseBlock(block[0].slice(1, -1));
      citations.push(...parsed.citations);
      unsupported.push(...parsed.unsupported);
      spans.push([block.index, block.index + block[0].length]);
    }
    for (const at of line.matchAll(BARE_AT_RE)) {
      if (spans.some(([s, e]) => at.index >= s && at.index < e)) continue;
      unsupported.push(at[1]);
    }
  }
  return { citations, unsupported };
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/d/labnote && npx vitest run test/citations.test.js`
Expected: PASS (every corpus case)

- [ ] **Step 5: Commit**

```bash
cd ~/d/labnote && git add src/app/citations.js test/citations.test.js test/fixtures/citation_grammar_v1.json
git commit -m "feat(citations): v1 grammar parser with Science corpus parity"
```

### Task C2: Citation session + ref-id encoding

**Files:**
- Modify: `~/d/labnote/src/app/citations.js`
- Test: `~/d/labnote/test/citations.test.js`

**Interfaces:**
- Produces:
  - `refId(citekey: string) -> string` — `"ref-" + hex(utf8(citekey))`.
  - `createCitationSession(referenceIndex: object) -> CitationSession` where `referenceIndex` is the bundle's `references` map. The session exposes `use(citekey) -> { number, resolved }` (first use assigns the next number; repeats reuse it; unknown keys resolve `false` but still get a number-less marker — see C4), and `ordered() -> Array<{citekey, number, record}>` in first-use order for resolved citations.

- [ ] **Step 1: Write the failing test**

Add to `~/d/labnote/test/citations.test.js`:

```js
import { createCitationSession, refId } from "../src/app/citations.js";

describe("refId", () => {
  it("hex-encodes UTF-8 bytes of the citekey", () => {
    expect(refId("Smith2020")).toBe("ref-536d69746832303230");
  });
});

describe("createCitationSession", () => {
  const index = { Smith2020: { display: "Smith." }, Jones2021: { display: "Jones." } };

  it("numbers first use and reuses for repeats", () => {
    const s = createCitationSession(index);
    expect(s.use("Smith2020")).toEqual({ number: 1, resolved: true });
    expect(s.use("Jones2021")).toEqual({ number: 2, resolved: true });
    expect(s.use("Smith2020")).toEqual({ number: 1, resolved: true });
  });

  it("ordered() returns resolved records in first-use order", () => {
    const s = createCitationSession(index);
    s.use("Jones2021");
    s.use("Smith2020");
    expect(s.ordered().map((r) => r.citekey)).toEqual(["Jones2021", "Smith2020"]);
    expect(s.ordered()[0].number).toBe(1);
  });

  it("marks unknown keys unresolved", () => {
    const s = createCitationSession(index);
    expect(s.use("Missing2026").resolved).toBe(false);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/d/labnote && npx vitest run test/citations.test.js`
Expected: FAIL — `createCitationSession`/`refId` not exported.

- [ ] **Step 3: Implement the session**

Append to `~/d/labnote/src/app/citations.js`:

```js
export function refId(citekey) {
  const bytes = new TextEncoder().encode(String(citekey));
  let hex = "";
  for (const b of bytes) hex += b.toString(16).padStart(2, "0");
  return `ref-${hex}`;
}

export function createCitationSession(referenceIndex) {
  const index = referenceIndex ?? {};
  const numbers = new Map(); // citekey -> number (resolved only)
  const order = []; // citekeys in first-resolved-use order
  let next = 1;
  return {
    use(citekey) {
      const record = index[citekey];
      if (!record) return { number: null, resolved: false };
      if (!numbers.has(citekey)) {
        numbers.set(citekey, next++);
        order.push(citekey);
      }
      return { number: numbers.get(citekey), resolved: true };
    },
    ordered() {
      return order.map((citekey) => ({
        citekey,
        number: numbers.get(citekey),
        record: index[citekey],
      }));
    },
  };
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/d/labnote && npx vitest run test/citations.test.js`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd ~/d/labnote && git add src/app/citations.js test/citations.test.js
git commit -m "feat(citations): per-view citation session and ref-id encoding"
```

### Task C3: Inline citation rendering in `renderMarkdown`

**Files:**
- Modify: `~/d/labnote/src/app/markdown.js:29-35` (the `renderMarkdown` function)
- Modify: `~/d/labnote/src/app/citations.js`
- Test: `~/d/labnote/test/markdown.test.js`

**Interfaces:**
- Consumes: `parseCitations`, `createCitationSession`, `refId` (C1, C2).
- Produces:
  - `renderMarkdown(text, options = {})` — backward compatible. When `options.citationSession` is present, citation blocks in rendered text are replaced with `<sup class="citation"><a href="#<refId>" data-citekey="..." [title="key, locator"]>N</a></sup>`; unknown keys become `<span class="citation-unresolved" data-citekey="...">[Missing citation: key]</span>`.
  - `applyCitations(rootEl, session)` (exported from citations.js) — walks text nodes outside `code`/`pre`, replaces citation syntax. Used by `renderMarkdown`.

- [ ] **Step 1: Write the failing test**

Add to `~/d/labnote/test/markdown.test.js`:

```js
import { createCitationSession } from "../src/app/citations.js";

describe("renderMarkdown citations", () => {
  const index = { Smith2020: { display: "Smith S. Title. 2020." } };

  it("renders a single citation as a numbered superscript link", () => {
    const session = createCitationSession(index);
    const el = renderMarkdown("Background [@Smith2020].", { citationSession: session });
    const a = el.querySelector("sup.citation a");
    expect(a.textContent).toBe("1");
    expect(a.getAttribute("href")).toBe("#ref-536d69746832303230");
    expect(a.getAttribute("data-citekey")).toBe("Smith2020");
  });

  it("preserves locator text in the title attribute", () => {
    const session = createCitationSession(index);
    const el = renderMarkdown("See [@Smith2020, p. 42].", { citationSession: session });
    expect(el.querySelector("sup.citation a").getAttribute("title")).toBe("Smith2020, p. 42");
  });

  it("renders a visible marker for unknown keys", () => {
    const session = createCitationSession(index);
    const el = renderMarkdown("Bad [@Missing2026].", { citationSession: session });
    expect(el.querySelector(".citation-unresolved").textContent).toBe("[Missing citation: Missing2026]");
  });

  it("does not touch citations inside code spans", () => {
    const session = createCitationSession(index);
    const el = renderMarkdown("Use `[@Smith2020]` literally.", { citationSession: session });
    expect(el.querySelector("sup.citation")).toBe(null);
    expect(el.querySelector("code").textContent).toContain("[@Smith2020]");
  });

  it("leaves output unchanged when no session is supplied", () => {
    const el = renderMarkdown("Background [@Smith2020].");
    expect(el.textContent).toContain("[@Smith2020]");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/d/labnote && npx vitest run test/markdown.test.js`
Expected: FAIL — citations are not rendered.

- [ ] **Step 3: Implement `applyCitations` and thread it through `renderMarkdown`**

Append to `~/d/labnote/src/app/citations.js`:

```js
function citationNodes(line, session, doc) {
  // Replace recognized [@...] blocks in a single text string; return an array of
  // DOM nodes (text + sup/span). Unsupported bare @tokens are left as literal text.
  const frag = [];
  let cursor = 0;
  for (const block of String(line).matchAll(/\[\s*@[^\]]*\]/g)) {
    const { citations } = parseCitations(block[0]);
    if (citations.length === 0) continue;
    if (block.index > cursor) frag.push(doc.createTextNode(line.slice(cursor, block.index)));
    for (const cite of citations) {
      const { number, resolved } = session.use(cite.citekey);
      if (resolved) {
        const sup = doc.createElement("sup");
        sup.className = "citation";
        const a = doc.createElement("a");
        a.setAttribute("href", `#${refId(cite.citekey)}`);
        a.setAttribute("data-citekey", cite.citekey);
        if (cite.locator) a.setAttribute("title", `${cite.citekey}, ${cite.locator}`);
        a.textContent = String(number);
        sup.appendChild(a);
        frag.push(sup);
      } else {
        const span = doc.createElement("span");
        span.className = "citation-unresolved";
        span.setAttribute("data-citekey", cite.citekey);
        span.textContent = `[Missing citation: ${cite.citekey}]`;
        frag.push(span);
      }
    }
    cursor = block.index + block[0].length;
  }
  if (cursor < line.length) frag.push(doc.createTextNode(line.slice(cursor)));
  return frag.length ? frag : null;
}

export function applyCitations(rootEl, session) {
  const doc = rootEl.ownerDocument;
  const walker = doc.createTreeWalker(rootEl, 4 /* SHOW_TEXT */);
  const targets = [];
  while (walker.nextNode()) {
    const node = walker.currentNode;
    if (node.parentElement?.closest("code, pre")) continue;
    if (!/\[\s*@[^\]]*\]/.test(node.nodeValue)) continue;
    targets.push(node);
  }
  for (const node of targets) {
    const replacement = citationNodes(node.nodeValue, session, doc);
    if (!replacement) continue;
    for (const child of replacement) node.parentNode.insertBefore(child, node);
    node.parentNode.removeChild(node);
  }
}
```

Then modify `renderMarkdown` in `markdown.js`:

```js
import { applyCitations } from "./citations.js";

export function renderMarkdown(text, options = {}) {
  if (text == null || String(text).trim() === "") return null;
  const container = document.createElement("div");
  container.className = "markdown-body";
  container.innerHTML = md.render(String(text));
  if (options.citationSession) applyCitations(container, options.citationSession);
  return container;
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/d/labnote && npx vitest run test/markdown.test.js test/citations.test.js`
Expected: PASS (new citation tests + all existing image-hydration tests)

- [ ] **Step 5: Commit**

```bash
cd ~/d/labnote && git add src/app/markdown.js src/app/citations.js test/markdown.test.js
git commit -m "feat(markdown): render inline numeric citations from a session"
```

### Task C4: References section component

**Files:**
- Modify: `~/d/labnote/src/app/citations.js`
- Test: `~/d/labnote/test/citations.test.js`

**Interfaces:**
- Consumes: `createCitationSession.ordered()`, `refId` (C2).
- Produces: `renderCitationReferences(session) -> HTMLElement | null` — returns `null` when no citations were used; otherwise a `<section class="references">` with an `<ol>` of `<li id="<refId>" data-citekey="...">` items in assigned-number order, each with a `.reference-display` span (the record `display`) and DOI/URL links only when present.

- [ ] **Step 1: Write the failing test**

Add to `~/d/labnote/test/citations.test.js`:

```js
import { renderCitationReferences } from "../src/app/citations.js";

describe("renderCitationReferences", () => {
  it("returns null when nothing was cited", () => {
    expect(renderCitationReferences(createCitationSession({}))).toBe(null);
  });

  it("lists records in first-use order with deterministic ids and doi link", () => {
    const index = {
      Smith2020: { display: "Smith S. Title. 2020.", doi: "10.1/x" },
      Jones2021: { display: "Jones J. Other. 2021." },
    };
    const s = createCitationSession(index);
    s.use("Jones2021");
    s.use("Smith2020");
    const section = renderCitationReferences(s);
    const items = section.querySelectorAll("ol > li");
    expect(items.length).toBe(2);
    expect(items[0].id).toBe(refId("Jones2021"));
    expect(items[0].querySelector(".reference-display").textContent).toBe("Jones J. Other. 2021.");
    expect(items[1].querySelector('a[href="https://doi.org/10.1/x"]')).not.toBe(null);
    expect(items[0].querySelector("a")).toBe(null); // no doi/url -> no link
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/d/labnote && npx vitest run test/citations.test.js`
Expected: FAIL — `renderCitationReferences` not exported.

- [ ] **Step 3: Implement the component**

Append to `~/d/labnote/src/app/citations.js`:

```js
export function renderCitationReferences(session) {
  const ordered = session.ordered();
  if (ordered.length === 0) return null;
  const section = document.createElement("section");
  section.className = "references";
  section.setAttribute("aria-labelledby", "references-heading");
  const heading = document.createElement("h2");
  heading.id = "references-heading";
  heading.textContent = "References";
  section.appendChild(heading);
  const ol = document.createElement("ol");
  for (const { citekey, record } of ordered) {
    const li = document.createElement("li");
    li.id = refId(citekey);
    li.setAttribute("data-citekey", citekey);
    const display = document.createElement("span");
    display.className = "reference-display";
    display.textContent = record.display ?? citekey;
    li.appendChild(display);
    if (record.doi) {
      const a = document.createElement("a");
      a.setAttribute("href", `https://doi.org/${record.doi}`);
      a.textContent = `doi:${record.doi}`;
      li.appendChild(document.createTextNode(" "));
      li.appendChild(a);
    } else if (record.url) {
      const a = document.createElement("a");
      a.setAttribute("href", record.url);
      a.textContent = record.url;
      li.appendChild(document.createTextNode(" "));
      li.appendChild(a);
    }
    ol.appendChild(li);
  }
  section.appendChild(ol);
  return section;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/d/labnote && npx vitest run test/citations.test.js`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd ~/d/labnote && git add src/app/citations.js test/citations.test.js
git commit -m "feat(citations): References section component"
```

### Task C5: Load the reference bundle in the package loader

**Files:**
- Modify: `~/d/labnote/src/app/package-loader.js:9-22` (`loadPackageDescriptors`)
- Test: `~/d/labnote/test/package-fixture.test.js` (mirror its existing loader-fixture pattern; confirm how it stubs `fetch`)

**Interfaces:**
- Produces: `loadReferences(base) -> bundle` and `loadPackageDescriptors` returns the bundle as `references`. A genuinely-absent bundle (HTTP 404) is tolerated as `{ references: {}, unresolved: {} }` so a project without citations still loads. Any OTHER fetch failure, malformed JSON, wrong `contract`, or unsupported `schema_version` THROWS — the design (§111-114) requires consumers to check `schema_version` before use, and a corrupt bundle must not be silently treated as "no citations".

- [ ] **Step 1: Write the failing tests**

Add to `~/d/labnote/test/package-fixture.test.js` (match the existing `fetch`-stub helper; the sketch below shows the three behaviors to cover):

```js
function stubFetch(routes) {
  // routes: { [path]: { status, body } }. Mirror the file's existing stub if present.
  globalThis.fetch = async (url) => {
    const route = routes[url] ?? { status: 404, body: null };
    return {
      ok: route.status >= 200 && route.status < 300,
      status: route.status,
      json: async () => route.body,
    };
  };
}

const REFS = "/data/package/references/index.json";

it("loads a valid references bundle", async () => {
  stubFetch({
    "/data/package/project.json": { status: 200, body: validProject },
    "/data/package/views.json": { status: 200, body: validViews },
    "/data/package/manifest.json": { status: 200, body: validManifest },
    [REFS]: { status: 200, body: {
      contract: "science.references", schema_version: "1", style: "numeric",
      references: { Smith2020: { display: "Smith. 2020." } }, unresolved: {},
    } },
  });
  const { references } = await loadPackageDescriptors();
  expect(references.references.Smith2020).toBeDefined();
});

it("tolerates a missing bundle (404) as empty", async () => {
  stubFetch({
    "/data/package/project.json": { status: 200, body: validProject },
    "/data/package/views.json": { status: 200, body: validViews },
    "/data/package/manifest.json": { status: 200, body: validManifest },
    [REFS]: { status: 404, body: null },
  });
  const { references } = await loadPackageDescriptors();
  expect(references).toEqual({ references: {}, unresolved: {} });
});

it("rejects a wrong-version bundle", async () => {
  stubFetch({
    "/data/package/project.json": { status: 200, body: validProject },
    "/data/package/views.json": { status: 200, body: validViews },
    "/data/package/manifest.json": { status: 200, body: validManifest },
    [REFS]: { status: 200, body: { contract: "science.references", schema_version: "2" } },
  });
  await expect(loadPackageDescriptors()).rejects.toThrow(/schema|version/i);
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/d/labnote && npx vitest run test/package-fixture.test.js -t references`
Expected: FAIL — `references` is undefined, and the wrong-version bundle is not rejected.

- [ ] **Step 3: Implement the validated load**

In `package-loader.js`, add a dedicated reference loader and use it in `loadPackageDescriptors`:

```js
const EMPTY_REFERENCES = { references: {}, unresolved: {} };

async function loadReferences(base) {
  const response = await fetch(`${base}/references/index.json`);
  if (response.status === 404) return EMPTY_REFERENCES; // no bundle == no citations
  if (!response.ok) {
    throw new Error(`failed to load references bundle: ${response.status}`);
  }
  const bundle = await response.json();
  if (bundle?.contract !== "science.references") {
    throw new Error(`references bundle has unexpected contract: ${bundle?.contract}`);
  }
  if (bundle?.schema_version !== "1") {
    throw new Error(`unsupported references schema_version: ${bundle?.schema_version}`);
  }
  return bundle;
}

export async function loadPackageDescriptors(base = "/data/package") {
  const [project, views, manifest, references] = await Promise.all([
    loadJson(`${base}/project.json`),
    loadJson(`${base}/views.json`),
    loadJson(`${base}/manifest.json`),
    loadReferences(base),
  ]);
  const validation = validatePackageContract({ project, views, manifest });
  if (!validation.ok) {
    throw new Error(
      `invalid project package: ${validation.errors.map((e) => e.message).join("; ")}`,
    );
  }
  return { project, views, manifest, references, validation };
}
```

Thread `references` through `loadAppState`'s return value as well.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/d/labnote && npx vitest run test/package-fixture.test.js`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd ~/d/labnote && git add src/app/package-loader.js test/package-fixture.test.js
git commit -m "feat(loader): load references/index.json bundle (tolerant of absence)"
```

### Task C6: Wire one session per page into finding + entity-prose views

**Files:**
- Read first: the finding-detail render path (find with `grep -rln "renderMarkdown" src/app`) and `src/app/entity-page-templates.js:177-230` (`renderEntityProse`)
- Modify: `~/d/labnote/src/app/entity-page-templates.js` (`renderEntityProse` to accept `options.citationSession` and append the References section once), and the finding-detail renderer
- Test: `~/d/labnote/test/entity-page-templates.test.js` and the finding-detail test

**Interfaces:**
- Consumes: `createCitationSession(references)`, `renderCitationReferences`, `renderMarkdown(text, { citationSession })`.
- Produces: each page builds exactly one `CitationSession` from `appState.references.references`, passes it into every `renderMarkdown` call on that page, and appends a single References section after the page content. One session per page, not per block (design §13 / test matrix).

- [ ] **Step 1: Write the failing test**

Add to `~/d/labnote/test/entity-page-templates.test.js`:

```js
it("shares one citation session across prose blocks and appends one References section", () => {
  const session = createCitationSession({
    Smith2020: { display: "Smith. 2020." },
    Jones2021: { display: "Jones. 2021." },
  });
  const module = {
    title: "Context",
    blocks: [
      { text: "First [@Smith2020]." },
      { text: "Second [@Jones2021] and again [@Smith2020]." },
    ],
  };
  const section = renderEntityProse(module, { citationSession: session });
  const sups = section.querySelectorAll("sup.citation a");
  expect([...sups].map((a) => a.textContent)).toEqual(["1", "2", "1"]); // shared numbering
  // The page (not the prose module) owns the References section; assert via the session:
  expect(session.ordered().map((r) => r.number)).toEqual([1, 2]);
});
```

Add a finding-detail test asserting the rendered page contains a single `section.references` and that an inline `sup.citation` `href` matches a `li` `id` in that section.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/d/labnote && npx vitest run test/entity-page-templates.test.js -t "citation session"`
Expected: FAIL — `renderEntityProse` ignores `options.citationSession`.

- [ ] **Step 3: Implement the wiring**

In `renderEntityProse`, pass the session into `renderMarkdown`:

```js
      const body = renderMarkdown(block.text, { citationSession: options.citationSession });
```

In the finding-detail and entity-page top-level render functions, build one session and append the References section after content:

```js
import { createCitationSession, renderCitationReferences } from "./citations.js";

const citationSession = createCitationSession(appState.references?.references ?? {});
// ... pass { citationSession } into every renderMarkdown / renderEntityProse call ...
const refs = renderCitationReferences(citationSession);
if (refs) pageRoot.appendChild(refs);
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/d/labnote && npx vitest run`
Expected: PASS (full suite, including existing entity-page and finding tests)

- [ ] **Step 5: Commit**

```bash
cd ~/d/labnote && git add src/app/entity-page-templates.js test/entity-page-templates.test.js
git commit -m "feat(views): one citation session per page + References section"
```

---

## Phase D — End-to-end fixture (MM30 Lead 3)

### Task D1: Lead 3 citation e2e test

**Files:**
- Read first: an existing playwright spec (e.g. `~/d/labnote/test/finding-detail-polish.spec.js`) to mirror navigation + fixture setup
- Test: `~/d/labnote/test/citations-lead3.spec.js`

**Interfaces:**
- Consumes: the synced MM30 package data containing `references/index.json` and Lead 3 prose with `[@Shi2025]`, `[@Elbahoty2024]`, `[@Lindstrom2022]`.

- [ ] **Step 1: Write the failing e2e test**

Create `~/d/labnote/test/citations-lead3.spec.js`:

```js
import { expect, test } from "@playwright/test";

test("Lead 3 renders numeric citations and a References section", async ({ page }) => {
  await page.goto("/"); // navigate to the Lead 3 finding detail per the app's routing
  // ... navigate to Lead 3 (mirror finding-detail-polish.spec.js navigation) ...

  // No literal citation text leaks:
  await expect(page.locator("body")).not.toContainText("[@Shi2025]");

  // Inline superscripts exist and link into the References list:
  const firstCite = page.locator("sup.citation a").first();
  await expect(firstCite).toBeVisible();
  const href = await firstCite.getAttribute("href");
  await expect(page.locator(`li${href}`)).toBeVisible();

  // A References section is present with non-empty display text:
  const refs = page.locator("section.references");
  await expect(refs.locator("h2")).toHaveText("References");
  await expect(refs.locator("li .reference-display").first()).not.toBeEmpty();
});
```

- [ ] **Step 2: Run test to verify it fails (before MM30 data is re-synced)**

Run: `cd ~/d/labnote && npx playwright test test/citations-lead3.spec.js`
Expected: FAIL — citations still render as literal text until the MM30 references bundle is synced (Phase B Task B2 Step 5).

- [ ] **Step 3: Ensure MM30 export + sync produced the bundle**

Confirm `references/index.json` is present in the synced Labnote package data and that Lead 3 prose citation keys all exist in it (Phase A validation guarantees this; if export failed closed, fix the bib first).

- [ ] **Step 4: Run the e2e test to verify it passes**

Run: `cd ~/d/labnote && npx playwright test test/citations-lead3.spec.js`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd ~/d/labnote && git add test/citations-lead3.spec.js
git commit -m "test(e2e): Lead 3 numeric citations + References section"
```

---

## Self-Review Notes

- **Spec coverage:** §4 record → A3; §5 parser/formatter/author rules + **duplicate-citekey errors → A5** → A1/A2/A3/A5; §6 grammar + shared corpus + unsupported-syntax + **malformed-in-block diagnostics** + parity → A4/A7/C1; §7 bundle + manifest entry + **scanner-surface coverage (tested collector) → B1** + unresolved block → A5/A6/B1/B2; §8 session → C2; §9 inline rendering + ref-id → C3/C2; §10 References section → C4; §11 unresolved markers → C3; §12 integration ownership → Phases A/B/C respect the boundaries (Labnote never parses BibTeX; MM30 owns no schema); §13 migration order → Phase order; §14 test matrix → tasks' tests + D1; §16 locked decisions → A5 (all-records test), B1/B2 (app export owns the file), A6 (fail-closed).
- **Fail-closed coverage (review fixes):**
  - Duplicate citekeys: detected on the *raw* entries (`raw_bib_entry_keys` + `Counter`) before the dict collapses them; `DuplicateCitekeyError` raised by the builder; tested in A5.
  - Malformed in-block items (`[@A; see @B]`, `[@A extra]`, `[@A p. 42]`): `_parse_block`/`parseBlock` report the offending item as unsupported instead of dropping it; corpus cases `malformed-mixed-block`, `malformed-no-at-item`, `malformed-missing-comma-locator`, and `malformed-extra-text-before-compound` enforce this in both languages.
  - MM30 surface coverage: `collect_markdown_payloads` is a tested pure function over the design §7 surfaces; `main()` only wires it in, so an uncovered surface fails its own test rather than slipping through.
  - Parity drift: one corpus owned by Science, pinned by `CITATION_GRAMMAR_V1_SHA256` asserted in BOTH repos' tests; the JS copy cannot diverge silently.
  - Loader: `loadReferences` tolerates only HTTP 404; any other failure, malformed JSON, wrong `contract`, or unsupported `schema_version` throws.
- **Type consistency:** `parse_citations`/`parseCitations` (both now return citations + unsupported, including in-block diagnostics), `Citation{citekey,locator}`, `createCitationSession().use()/.ordered()`, `refId`, `reference_record`/bundle `references` map, `MarkdownPayload{path,field,text}`, and `CITATION_GRAMMAR_V1_SHA256` are used identically across producing and consuming tasks.
- **Open items flagged for the implementer (not placeholders — real lookups):** A7's exact prose-lint finding type/entry point; B1's exact JSON field paths in `_finding_payloads`/`_entity_prose_payloads` (reconcile with real built bundles in the read-first step — the collector test fixture encodes the assumed shape); B2's `app_export.smk` rule wiring; C5/C6's exact fetch-stub helper and finding-detail render entry point. Each task names the file to read first.

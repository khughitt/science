# PubTator3 Entity-Mention Seeder (Phase 2a) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship `science annotate pubtator <pmid|doi>` — a deterministic CLI that converts PubTator3 BioC entity mentions into `oa:TextQuoteSelector` annotations anchored in an existing `<citekey>.source.md`, written to the `<citekey>.source.anno.trig` sidecar by reusing the existing W3C annotation machinery (no annotation-model change beyond one prefix registration).

**Architecture:** A new focused module `annotation/pubtator_seed.py` holds: (1) a `PUBTATOR_TYPE_SPEC` mapping + concept-IRI builders, (2) BioC entity-annotation parsing, (3) the `.source.md` offset-map loader + ordered passage bridge, (4) mention→`PlannedAnnotation` conversion with a span-discriminating `match_text`, and (5) the `seed_pubtator` orchestrator. The CLI subcommand lives on the existing top-level `annotate` group in `annotation/cli.py`. Network I/O reuses Phase 1's injectable `httpx.Client` + `RateLimiter` + `FetchConfig`; annotation persistence reuses `merge_planned`/`read_sidecar`/`write_sidecar`.

**Tech Stack:** Python 3.12, click, httpx (+`httpx.MockTransport` for hermetic tests), PyYAML, pytest, uv workspace. Tests + lint/type gates run from `science/`.

**Design reference:** `~/d/science/docs/plans/2026-06-15-pubtator-seeder-phase2a-design.md`.

---

## Conventions for every task

- Work in the worktree `.worktrees/sub-article-annotation-phase2` on branch `feat/sub-article-annotation-phase2`. Verify with `git branch --show-current` before committing.
- Run tests/lint/types from the `science/` directory:
  - Test (one): `uv run --frozen pytest tests/<file>::<test> -v`
  - Test (module): `uv run --frozen pytest tests/<file> -q`
  - Types: `uv run --frozen pyright src/science_tool/annotation/pubtator_seed.py tests/<file>` — **run pyright on BOTH the source AND the test file** (a Phase 1 lesson: test-only type errors slipped through when only src was checked).
  - Lint: `uv run --frozen ruff check src/science_tool/annotation/pubtator_seed.py tests/<file>`
- The harness editor-index may report `reportMissingImports` for `science_tool.*`; `uv run --frozen pyright` resolves them — trust the `uv` run.
- No `Co-Authored-By` trailers in commits.

## File structure (locked)

- **Create** `science/src/science_tool/annotation/pubtator_seed.py` — all seeder logic.
- **Modify** `science/src/science_tool/annotation/model.py:34` — add `"pubtator3:"` to `HASH_REQUIRED_SOURCE_PREFIXES`.
- **Modify** `science/src/science_tool/annotation/source_text.py` — factor a public `fetch_bioc_record(...)` out of `_fetch_bioc` so the seeder can reuse the raw-BioC fetch (it needs the annotations, which `_fetch_bioc` discards).
- **Modify** `science/src/science_tool/annotation/cli.py` — add the `pubtator` subcommand to `annotate_group`.
- **Modify** `docs/conventions/annotation-tokens.md` — register the six `entity-<type>` types, the Biolink-class map, and the `pubtator3:<release>:seeder-vN` source prefix.
- **Create** `science/tests/test_pubtator_seed.py` — unit + hermetic integration tests.
- **Create** `science/tests/test_cli_annotate_pubtator.py` — `CliRunner` + `MockTransport` CLI tests.

## Shared test fixture (BioC)

Several tests use a small BioC record. Define it **once** at the top of `tests/test_pubtator_seed.py` as `BIOC_FIXTURE` and reuse it. It is a representative PubTator3 `biocjson` shape; **Task 3 pins the `infons` key handling against it**, and a comment marks it as "validate against a live response before v1 release."

```python
# A title+abstract record with one body passage (non-persisted in abstract-only mode),
# duplicate-surface mentions in the same passage, and one unnormalized variant.
BIOC_FIXTURE = {
    "PubTator3": [
        {
            "id": "12345678",
            "infons": {"_release": "2025-01"},
            "passages": [
                {
                    "infons": {"type": "title"},
                    "offset": 0,
                    "text": "BRCA1 and BRCA1 in breast cancer",
                    "annotations": [
                        {
                            "infons": {"identifier": "672", "type": "Gene"},
                            "text": "BRCA1",
                            "locations": [{"offset": 0, "length": 5}],
                        },
                        {
                            "infons": {"identifier": "672", "type": "Gene"},
                            "text": "BRCA1",
                            "locations": [{"offset": 10, "length": 5}],
                        },
                        {
                            "infons": {"identifier": "MESH:D001943", "type": "Disease"},
                            "text": "breast cancer",
                            "locations": [{"offset": 19, "length": 13}],
                        },
                    ],
                },
                {
                    "infons": {"type": "abstract"},
                    "offset": 33,
                    "text": "Tamoxifen treats it in Homo sapiens with rs80357065.",
                    "annotations": [
                        {
                            "infons": {"identifier": "MESH:D013629", "type": "Chemical"},
                            "text": "Tamoxifen",
                            "locations": [{"offset": 33, "length": 9}],
                        },
                        {
                            "infons": {"identifier": "9606", "type": "Species"},
                            "text": "Homo sapiens",
                            "locations": [{"offset": 56, "length": 12}],
                        },
                        {
                            "infons": {"identifier": "rs80357065", "type": "Mutation"},
                            "text": "rs80357065",
                            "locations": [{"offset": 74, "length": 10}],
                        },
                        {
                            "infons": {"identifier": "tmVar:c|SUB|A|1|T", "type": "Mutation"},
                            "text": "rs80357065",
                            "locations": [{"offset": 74, "length": 10}],
                        },
                    ],
                },
                {
                    "infons": {"type": "INTRO"},
                    "offset": 86,
                    "text": "A body sentence mentioning TP53 here.",
                    "annotations": [
                        {
                            "infons": {"identifier": "7157", "type": "Gene"},
                            "text": "TP53",
                            "locations": [{"offset": 113, "length": 4}],
                        }
                    ],
                },
            ],
        }
    ]
}
```

Note: the title passage contains `"BRCA1"` twice at different offsets (same persisted passage) — the merge-collapse regression case. The abstract has the same span tagged twice (a normalizable rsID and an unnormalizable tmVar) — the unnormalized-skip case. The `INTRO` body passage is non-persisted in abstract-only mode — the non-persisted-skip case.

---

### Task 1: Register the Phase 2a vocabulary

**Files:**
- Modify: `science/src/science_tool/annotation/model.py:34`
- Modify: `docs/conventions/annotation-tokens.md`
- Test: `science/tests/test_pubtator_seed.py`

- [ ] **Step 1: Write the failing test**

Create `science/tests/test_pubtator_seed.py` with the `BIOC_FIXTURE` constant above and this test:

```python
from science_tool.annotation.model import HASH_REQUIRED_SOURCE_PREFIXES


def test_pubtator3_prefix_is_hash_required():
    assert "pubtator3:" in HASH_REQUIRED_SOURCE_PREFIXES
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `uv run --frozen pytest tests/test_pubtator_seed.py::test_pubtator3_prefix_is_hash_required -v`
Expected: FAIL (`"pubtator3:"` not in the tuple).

- [ ] **Step 3: Add the prefix**

In `science/src/science_tool/annotation/model.py`, change line 34 from:

```python
HASH_REQUIRED_SOURCE_PREFIXES: tuple[str, ...] = ("llm-audit:", "lint:", "marker-scanner:")
```

to:

```python
HASH_REQUIRED_SOURCE_PREFIXES: tuple[str, ...] = (
    "llm-audit:",
    "lint:",
    "marker-scanner:",
    "pubtator3:",
)
```

- [ ] **Step 4: Run it to confirm it passes**

Run: `uv run --frozen pytest tests/test_pubtator_seed.py::test_pubtator3_prefix_is_hash_required -v`
Expected: PASS.

- [ ] **Step 5: Register tokens in the conventions doc**

Append a section to `docs/conventions/annotation-tokens.md` (read the file first to match its heading style and bump any `updated:` field to `2026-06-15`):

```markdown
## PubTator3 entity-mention seeding (Phase 2a)

Source prefix: `pubtator3:<release>:seeder-vN` — `<release>` is the BioC `_release`
infon (fallback `pubtator3-api`); bump `seeder-vN` when the offset-mapping or
concept-normalization logic changes (invalidates the re-audit cache).

Entity annotation types (`sci:annotationType`), motivation `oa:identifying`, single
`IriBody` carrying the concept IRI (identifiers.org compact form
`https://identifiers.org/<namespace>:<accession>`):

| annotation_type | Biolink class | concept IRI namespace |
|---|---|---|
| `entity-gene` | `biolink:Gene` | `ncbigene` |
| `entity-disease` | `biolink:Disease` | `mesh` |
| `entity-chemical` | `biolink:ChemicalEntity` | `mesh` |
| `entity-species` | `biolink:OrganismTaxon` | `taxonomy` |
| `entity-variant` | `biolink:SequenceVariant` | `dbsnp` (rsID only) |
| `entity-cellline` | `biolink:CellLine` | `cellosaurus` |

The Biolink class is derived from `annotation_type` via this table; it is NOT stored
in the annotation. Mentions PubTator left unnormalized (no id matching the namespace
shape) are skipped, not stored with a fallback body.
```

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/annotation/model.py docs/conventions/annotation-tokens.md science/tests/test_pubtator_seed.py
git commit -m "pubtator-seed: register pubtator3 hash prefix + token vocabulary"
```

---

### Task 2: Type→spec table and concept-IRI builders

**Files:**
- Create: `science/src/science_tool/annotation/pubtator_seed.py`
- Test: `science/tests/test_pubtator_seed.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_pubtator_seed.py`:

```python
import pytest

from science_tool.annotation.pubtator_seed import (
    annotation_type_for,
    concept_iri_for,
)


@pytest.mark.parametrize(
    "pubtator_type,expected",
    [
        ("Gene", "entity-gene"),
        ("Disease", "entity-disease"),
        ("Chemical", "entity-chemical"),
        ("Species", "entity-species"),
        ("CellLine", "entity-cellline"),
        ("Mutation", "entity-variant"),
        ("DNAMutation", "entity-variant"),
        ("SNP", "entity-variant"),
        ("Variant", "entity-variant"),
        ("Unsupported", None),
    ],
)
def test_annotation_type_for(pubtator_type, expected):
    assert annotation_type_for(pubtator_type) == expected


@pytest.mark.parametrize(
    "pubtator_type,identifier,expected",
    [
        ("Gene", "672", "https://identifiers.org/ncbigene:672"),
        ("Gene", "Gene:672", "https://identifiers.org/ncbigene:672"),
        ("Gene", "672;675", "https://identifiers.org/ncbigene:672"),  # first of multi
        ("Species", "9606", "https://identifiers.org/taxonomy:9606"),
        ("Disease", "MESH:D001943", "https://identifiers.org/mesh:D001943"),
        ("Disease", "D001943", "https://identifiers.org/mesh:D001943"),
        ("Chemical", "MESH:D013629", "https://identifiers.org/mesh:D013629"),
        ("Mutation", "rs80357065", "https://identifiers.org/dbsnp:rs80357065"),
        ("Mutation", "RS#:80357065", "https://identifiers.org/dbsnp:rs80357065"),
        ("CellLine", "CVCL_0031", "https://identifiers.org/cellosaurus:CVCL_0031"),
        # unnormalizable -> None (skip-and-count upstream)
        ("Mutation", "tmVar:c|SUB|A|1|T", None),
        ("Gene", "", None),
        ("Gene", None, None),
        ("Disease", "OMIM:114480", None),  # non-MeSH disease id out of Phase 2a scope
        ("CellLine", "12345", None),       # non-Cellosaurus
        ("Unsupported", "1", None),
    ],
)
def test_concept_iri_for(pubtator_type, identifier, expected):
    assert concept_iri_for(pubtator_type, identifier) == expected
```

- [ ] **Step 2: Run them to confirm they fail**

Run: `uv run --frozen pytest tests/test_pubtator_seed.py -k "annotation_type_for or concept_iri_for" -v`
Expected: FAIL (`ModuleNotFoundError` / names undefined).

- [ ] **Step 3: Implement the table + builders**

Create `science/src/science_tool/annotation/pubtator_seed.py`:

```python
"""Phase 2a: PubTator3 entity-mention seeder.

Convert PubTator3 BioC entity mentions into oa:TextQuoteSelector annotations
anchored in an existing `<citekey>.source.md`, written to the
`<citekey>.source.anno.trig` sidecar via the existing annotation machinery.

See docs/plans/2026-06-15-pubtator-seeder-phase2a-design.md.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Any

# --- Entity type -> annotation_type ------------------------------------------

# PubTator BioC `infons.type` (lowercased) -> our kebab entity slug.
_TYPE_TO_ENTITY: dict[str, str] = {
    "gene": "gene",
    "disease": "disease",
    "chemical": "chemical",
    "species": "species",
    "cellline": "cellline",
    "variant": "variant",
    "mutation": "variant",
    "dnamutation": "variant",
    "proteinmutation": "variant",
    "snp": "variant",
}


def annotation_type_for(pubtator_type: str) -> str | None:
    """`entity-<slug>` for a supported PubTator type, else None (unsupported)."""
    slug = _TYPE_TO_ENTITY.get(pubtator_type.strip().lower())
    return f"entity-{slug}" if slug else None


# --- Concept identifier -> identifiers.org compact IRI ------------------------

_IDENTIFIERS_BASE = "https://identifiers.org"

_DIGITS = re.compile(r"^\d+$")
_MESH = re.compile(r"^[A-Z]\d{6,}$")  # MeSH descriptor/supplementary, e.g. D001943
_RSID = re.compile(r"^rs\d+$")
_RS_HASH = re.compile(r"^RS#:(\d+)$")
_CVCL = re.compile(r"^CVCL_\w+$")


def _first_id(identifier: str | None) -> str:
    """First id of a possibly `;`-joined list, with a leading `NS:` prefix stripped."""
    if not identifier:
        return ""
    head = identifier.split(";")[0].strip()
    # Strip a leading source-namespace prefix PubTator sometimes prepends,
    # e.g. "Gene:672" / "NCBIGene:672". Keep "MESH:"/"RS#:" handling to callers.
    if ":" in head:
        prefix, rest = head.split(":", 1)
        if prefix.lower() in {"gene", "ncbigene", "entrez"}:
            return rest.strip()
    return head


def _compact(namespace: str, accession: str) -> str:
    return f"{_IDENTIFIERS_BASE}/{namespace}:{accession}"


def concept_iri_for(pubtator_type: str, identifier: str | None) -> str | None:
    """Build the identifiers.org concept IRI, or None if unnormalizable (skip).

    Only ids matching each namespace's expected shape are accepted; anything else
    (tmVar variant strings, OMIM disease ids, non-Cellosaurus cell lines, empty) is
    rejected so the seeder skips-and-counts rather than minting a junk anchor.
    """
    entity = _TYPE_TO_ENTITY.get(pubtator_type.strip().lower())
    if entity is None:
        return None
    raw = _first_id(identifier)
    if not raw:
        return None

    if entity == "gene":
        return _compact("ncbigene", raw) if _DIGITS.match(raw) else None
    if entity == "species":
        return _compact("taxonomy", raw) if _DIGITS.match(raw) else None
    if entity in ("disease", "chemical"):
        mesh = raw[5:] if raw.upper().startswith("MESH:") else raw
        return _compact("mesh", mesh) if _MESH.match(mesh) else None
    if entity == "variant":
        if _RSID.match(raw):
            return _compact("dbsnp", raw)
        m = _RS_HASH.match(raw)
        return _compact("dbsnp", f"rs{m.group(1)}") if m else None
    if entity == "cellline":
        return _compact("cellosaurus", raw) if _CVCL.match(raw) else None
    return None
```

- [ ] **Step 4: Run them to confirm they pass**

Run: `uv run --frozen pytest tests/test_pubtator_seed.py -k "annotation_type_for or concept_iri_for" -v`
Expected: PASS (all parametrizations).

- [ ] **Step 5: Lint + type-check**

Run: `uv run --frozen ruff check src/science_tool/annotation/pubtator_seed.py tests/test_pubtator_seed.py`
Run: `uv run --frozen pyright src/science_tool/annotation/pubtator_seed.py tests/test_pubtator_seed.py`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/annotation/pubtator_seed.py science/tests/test_pubtator_seed.py
git commit -m "pubtator-seed: type->annotation_type map + concept-IRI builders"
```

---

### Task 3: Parse BioC entity annotations

**Files:**
- Modify: `science/src/science_tool/annotation/pubtator_seed.py`
- Test: `science/tests/test_pubtator_seed.py`

- [ ] **Step 1: Write the failing test**

Add:

```python
from science_tool.annotation.pubtator_seed import (
    BiocMention,
    parse_bioc_entity_annotations,
)


def test_parse_bioc_entity_annotations():
    mentions = parse_bioc_entity_annotations(BIOC_FIXTURE)
    # 3 (title) + 4 (abstract) + 1 (intro) = 8 mention rows, all preserved in order.
    assert len(mentions) == 8
    first = mentions[0]
    assert isinstance(first, BiocMention)
    assert (first.pubtator_type, first.identifier, first.text) == ("Gene", "672", "BRCA1")
    assert (first.offset, first.length) == (0, 5)
    # The two BRCA1 mentions in the title differ only by offset.
    assert mentions[0].offset == 0 and mentions[1].offset == 10
    assert mentions[0].text == mentions[1].text == "BRCA1"
    # The duplicate-tagged abstract span yields two rows (rsID + tmVar).
    variants = [m for m in mentions if m.pubtator_type == "Mutation"]
    assert {m.identifier for m in variants} == {"rs80357065", "tmVar:c|SUB|A|1|T"}


def test_parse_bioc_entity_annotations_empty():
    assert parse_bioc_entity_annotations({"PubTator3": []}) == []
    assert parse_bioc_entity_annotations({}) == []
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `uv run --frozen pytest tests/test_pubtator_seed.py -k parse_bioc_entity -v`
Expected: FAIL (`BiocMention` / `parse_bioc_entity_annotations` undefined).

- [ ] **Step 3: Implement the parser**

Add to `pubtator_seed.py` (after the imports / dataclass section):

```python
@dataclass(frozen=True)
class BiocMention:
    """One PubTator entity mention: type, normalized id, surface text, and the
    document-global BioC char offset+length of its span."""

    pubtator_type: str
    identifier: str | None
    text: str
    offset: int
    length: int


def parse_bioc_entity_annotations(record: dict[str, Any]) -> list[BiocMention]:
    """Flatten all passage entity annotations into ordered BiocMention rows.

    Reads the same `PubTator3`/`documents` top-level shape as parse_bioc_passages.
    A mention with no usable `text`/`type`/location is skipped at parse time
    (malformed); concept-id normalization happens later (concept_iri_for).
    """
    docs = record.get("PubTator3") or record.get("documents")
    if not isinstance(docs, list) or not docs:
        return []
    doc = docs[0]
    if not isinstance(doc, dict):
        return []
    passages = doc.get("passages")
    if not isinstance(passages, list):
        return []

    mentions: list[BiocMention] = []
    for passage in passages:
        if not isinstance(passage, dict):
            continue
        anns = passage.get("annotations")
        if not isinstance(anns, list):
            continue
        for ann in anns:
            if not isinstance(ann, dict):
                continue
            infons = ann.get("infons")
            infons = infons if isinstance(infons, dict) else {}
            ptype = infons.get("type")
            text = ann.get("text")
            locations = ann.get("locations")
            if not isinstance(ptype, str) or not isinstance(text, str) or not text:
                continue
            if not isinstance(locations, list) or not locations:
                continue
            loc = locations[0]
            if not isinstance(loc, dict):
                continue
            offset = loc.get("offset")
            length = loc.get("length")
            if not isinstance(offset, int) or not isinstance(length, int):
                continue
            identifier = infons.get("identifier")
            mentions.append(
                BiocMention(
                    pubtator_type=ptype,
                    identifier=identifier if isinstance(identifier, str) else None,
                    text=text,
                    offset=offset,
                    length=length,
                )
            )
    return mentions
```

- [ ] **Step 4: Run it to confirm it passes**

Run: `uv run --frozen pytest tests/test_pubtator_seed.py -k parse_bioc_entity -v`
Expected: PASS.

- [ ] **Step 5: Lint + type-check**

Run: `uv run --frozen ruff check src/science_tool/annotation/pubtator_seed.py tests/test_pubtator_seed.py`
Run: `uv run --frozen pyright src/science_tool/annotation/pubtator_seed.py tests/test_pubtator_seed.py`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/annotation/pubtator_seed.py science/tests/test_pubtator_seed.py
git commit -m "pubtator-seed: parse BioC entity annotations into ordered mentions"
```

---

### Task 4: Offset-map loader + ordered passage bridge

**Files:**
- Modify: `science/src/science_tool/annotation/pubtator_seed.py`
- Test: `science/tests/test_pubtator_seed.py`

This task pairs each persisted `.source.md` passage to its live BioC offset base by an **ordered left-to-right scan** (never an unordered text search), so duplicate-text passages map by occurrence order and non-persisted passages are skipped.

- [ ] **Step 1: Write the failing tests**

Add:

```python
from science_tool.annotation.source_text import Passage, SourcePassages
from science_tool.annotation.pubtator_seed import (
    PairedPassage,
    PersistedPassage,
    pair_passages,
)


def _bioc(*sections):
    # sections: (section, bioc_offset, text)
    return SourcePassages(
        passages=tuple(Passage(section=s, bioc_offset=o, text=t) for s, o, t in sections),
        release="2025-01",
    )


def test_pair_passages_skips_nonpersisted_body():
    # Persisted = title + abstract only (abstract-only paper); BioC also has a body.
    file_text = "HEADER\n\nTitle text\n\nAbstract text\n"
    persisted = [
        PersistedPassage(section="title", file_char_base=8, length=10),     # "Title text"
        PersistedPassage(section="abstract", file_char_base=20, length=13),  # "Abstract text"
    ]
    assert file_text[8:18] == "Title text"
    assert file_text[20:33] == "Abstract text"
    bioc = _bioc(
        ("title", 0, "Title text"),
        ("abstract", 11, "Abstract text"),
        ("INTRO", 25, "Body text not persisted"),
    )
    paired = pair_passages(file_text, persisted, bioc)
    assert paired == [
        PairedPassage(bioc_offset=0, bioc_len=10, file_char_base=8),
        PairedPassage(bioc_offset=11, bioc_len=13, file_char_base=20),
    ]


def test_pair_passages_duplicate_text_pairs_by_order():
    # Two persisted passages with identical text pair to successive BioC occurrences.
    file_text = "H\n\nDUP\n\nDUP\n"
    persisted = [
        PersistedPassage(section="a", file_char_base=3, length=3),  # first "DUP"
        PersistedPassage(section="b", file_char_base=8, length=3),  # second "DUP"
    ]
    assert file_text[3:6] == "DUP" and file_text[8:11] == "DUP"
    bioc = _bioc(("a", 0, "DUP"), ("b", 100, "DUP"))
    paired = pair_passages(file_text, persisted, bioc)
    assert [p.file_char_base for p in paired] == [3, 8]
    assert [p.bioc_offset for p in paired] == [0, 100]


def test_pair_passages_drift_fails_loud():
    from science_tool.annotation.source_text import SourceTextError

    file_text = "H\n\nPersisted only here\n"
    persisted = [PersistedPassage(section="a", file_char_base=3, length=19)]
    assert file_text[3:22] == "Persisted only here"
    bioc = _bioc(("a", 0, "Different text entirely"))
    with pytest.raises(SourceTextError, match="not found in re-fetched BioC"):
        pair_passages(file_text, persisted, bioc)
```

- [ ] **Step 2: Run them to confirm they fail**

Run: `uv run --frozen pytest tests/test_pubtator_seed.py -k pair_passages -v`
Expected: FAIL (names undefined).

- [ ] **Step 3: Implement loader + bridge**

Add to `pubtator_seed.py` (note the new imports at the top of the file):

```python
from pathlib import Path

from science_tool.annotation.source_text import (
    SourcePassages,
    SourceTextError,
)
from science_tool.commons.frontmatter import raw_frontmatter
```

```python
@dataclass(frozen=True)
class PersistedPassage:
    """One persisted passage from `.source.md` frontmatter `passages` (render order)."""

    section: str
    file_char_base: int
    length: int


@dataclass(frozen=True)
class PairedPassage:
    """A persisted passage paired to its live BioC document offset base."""

    bioc_offset: int
    bioc_len: int
    file_char_base: int


def load_persisted_passages(source_md: Path) -> tuple[str, list[PersistedPassage]]:
    """Read `.source.md`: return (full file text, persisted passages in render order)."""
    file_text = source_md.read_text(encoding="utf-8")
    fm = raw_frontmatter(source_md)
    raw = fm.get("passages")
    if not isinstance(raw, list) or not raw:
        raise SourceTextError(
            f"{source_md} has no `passages` offset map; re-run `persist-source`."
        )
    persisted: list[PersistedPassage] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        section = str(entry.get("section") or "passage")
        base = entry.get("file_char_base")
        length = entry.get("length")
        if not isinstance(base, int) or not isinstance(length, int):
            raise SourceTextError(f"{source_md}: malformed passages offset map entry {entry!r}")
        persisted.append(PersistedPassage(section=section, file_char_base=base, length=length))
    return file_text, persisted


def pair_passages(
    file_text: str,
    persisted: list[PersistedPassage],
    bioc: SourcePassages,
) -> list[PairedPassage]:
    """Pair persisted passages to live BioC offset bases by ordered occurrence.

    Iterate persisted entries in render order, advancing a single pointer through
    the BioC passage list to the next passage whose text equals the entry's file
    slice. Duplicate-text passages therefore pair to successive BioC occurrences,
    and non-persisted BioC passages are skipped. A persisted passage with no
    remaining ordered match means the source text drifted -> fail loud.
    """
    paired: list[PairedPassage] = []
    j = 0
    bioc_passages = bioc.passages
    for e in persisted:
        slice_ = file_text[e.file_char_base : e.file_char_base + e.length]
        while j < len(bioc_passages) and bioc_passages[j].text != slice_:
            j += 1
        if j >= len(bioc_passages):
            raise SourceTextError(
                f"persisted passage at {e.file_char_base} (section {e.section!r}) "
                "not found in re-fetched BioC (source text drift); re-run persist-source"
            )
        p = bioc_passages[j]
        paired.append(
            PairedPassage(bioc_offset=p.bioc_offset, bioc_len=e.length, file_char_base=e.file_char_base)
        )
        j += 1
    return paired
```

- [ ] **Step 4: Run them to confirm they pass**

Run: `uv run --frozen pytest tests/test_pubtator_seed.py -k pair_passages -v`
Expected: PASS.

- [ ] **Step 5: Lint + type-check**

Run: `uv run --frozen ruff check src/science_tool/annotation/pubtator_seed.py tests/test_pubtator_seed.py`
Run: `uv run --frozen pyright src/science_tool/annotation/pubtator_seed.py tests/test_pubtator_seed.py`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/annotation/pubtator_seed.py science/tests/test_pubtator_seed.py
git commit -m "pubtator-seed: offset-map loader + ordered passage bridge"
```

---

### Task 5: Mention → PlannedAnnotation conversion

**Files:**
- Modify: `science/src/science_tool/annotation/pubtator_seed.py`
- Test: `science/tests/test_pubtator_seed.py`

Convert one `BiocMention` to a `PlannedAnnotation`, or return a skip reason. This is where the slice-verify, passage-clamped selector, span-discriminating `match_text`, and concept `IriBody` all come together.

- [ ] **Step 1: Write the failing tests**

Add:

```python
from science_tool.annotation.model import IriBody, Motivation
from science_tool.annotation.sources.base import PlannedAnnotation
from science_tool.annotation.pubtator_seed import plan_mention

# Reusable mini-file: header + a single persisted title passage "BRCA1 and BRCA1".
_FILE = "---\nkind: paper-source\n---\n\n## Abstract\n\nBRCA1 and BRCA1\n"
_BASE = _FILE.index("BRCA1")  # absolute file index where the passage body begins


def _paired_for_title():
    from science_tool.annotation.pubtator_seed import PairedPassage
    # The title passage is BioC offset 0, 15 chars ("BRCA1 and BRCA1"), at _BASE.
    return [PairedPassage(bioc_offset=0, bioc_len=15, file_char_base=_BASE)]


def test_plan_mention_builds_annotation():
    m = BiocMention(pubtator_type="Gene", identifier="672", text="BRCA1", offset=0, length=5)
    planned, reason = plan_mention(
        _FILE, _paired_for_title(), m, release="2025-01", source_md_name="x.source.md"
    )
    assert reason is None
    assert isinstance(planned, PlannedAnnotation)
    assert planned.annotation_type == "entity-gene"
    assert planned.motivation is Motivation.IDENTIFYING
    assert planned.body == IriBody(iri="https://identifiers.org/ncbigene:672")
    assert planned.source_name == "pubtator3:2025-01:seeder-v1"
    assert planned.target.source == "x.source.md"
    assert planned.target.selector.exact == "BRCA1"
    # match_text carries the MENTION file index, not the passage base.
    file_idx = _BASE  # first BRCA1 sits at the passage base
    assert planned.match_text == f"entity-gene|https://identifiers.org/ncbigene:672|{file_idx}:5|BRCA1"


def test_plan_mention_two_same_surface_in_one_passage_distinct():
    # Two BRCA1 mentions, same passage, different offsets -> distinct match_text.
    m1 = BiocMention(pubtator_type="Gene", identifier="672", text="BRCA1", offset=0, length=5)
    m2 = BiocMention(pubtator_type="Gene", identifier="672", text="BRCA1", offset=10, length=5)
    p1, _ = plan_mention(_FILE, _paired_for_title(), m1, release="2025-01", source_md_name="x.source.md")
    p2, _ = plan_mention(_FILE, _paired_for_title(), m2, release="2025-01", source_md_name="x.source.md")
    assert p1 is not None and p2 is not None
    assert p1.match_text != p2.match_text
    # The second mention's prefix differs (anchored later in the passage).
    assert p1.target.selector.prefix != p2.target.selector.prefix


def test_plan_mention_skips_unnormalized():
    m = BiocMention(pubtator_type="Mutation", identifier="tmVar:c|SUB|A|1|T", text="BRCA1", offset=0, length=5)
    planned, reason = plan_mention(_FILE, _paired_for_title(), m, release="2025-01", source_md_name="x.source.md")
    assert planned is None and reason == "unnormalized-concept"


def test_plan_mention_skips_unsupported_type():
    m = BiocMention(pubtator_type="Anatomy", identifier="x", text="BRCA1", offset=0, length=5)
    planned, reason = plan_mention(_FILE, _paired_for_title(), m, release="2025-01", source_md_name="x.source.md")
    assert planned is None and reason == "unsupported-type"


def test_plan_mention_skips_nonpersisted_passage():
    # Mention at BioC offset 500 is in no paired passage -> non-persisted.
    m = BiocMention(pubtator_type="Gene", identifier="7157", text="TP53", offset=500, length=4)
    planned, reason = plan_mention(_FILE, _paired_for_title(), m, release="2025-01", source_md_name="x.source.md")
    assert planned is None and reason == "non-persisted-passage"


def test_plan_mention_slice_mismatch_fails_loud():
    # Mention claims "XXXXX" but the file slice is "BRCA1" -> hard error.
    m = BiocMention(pubtator_type="Gene", identifier="672", text="XXXXX", offset=0, length=5)
    with pytest.raises(SourceTextError, match="slice"):
        plan_mention(_FILE, _paired_for_title(), m, release="2025-01", source_md_name="x.source.md")
```

- [ ] **Step 2: Run them to confirm they fail**

Run: `uv run --frozen pytest tests/test_pubtator_seed.py -k plan_mention -v`
Expected: FAIL (`plan_mention` undefined).

- [ ] **Step 3: Implement the conversion**

Add the imports and function to `pubtator_seed.py`:

```python
from science_tool.annotation.model import IriBody, Motivation, SpecificResource, TextQuoteSelector
from science_tool.annotation.sources.base import PlannedAnnotation
```

```python
# Prefix/suffix context window (chars), clamped to the passage bounds.
_CONTEXT = 60


def _containing(paired: list[PairedPassage], offset: int, length: int) -> PairedPassage | None:
    end = offset + length
    for pp in paired:
        if pp.bioc_offset <= offset and end <= pp.bioc_offset + pp.bioc_len:
            return pp
    return None


def plan_mention(
    file_text: str,
    paired: list[PairedPassage],
    mention: BiocMention,
    *,
    release: str,
    source_md_name: str,
) -> tuple[PlannedAnnotation | None, str | None]:
    """Convert a BiocMention to a PlannedAnnotation, or (None, skip_reason).

    Skip reasons: "unsupported-type", "non-persisted-passage", "unnormalized-concept".
    A mention whose mapped file slice does not equal its reported text is a hard
    SourceTextError (never a silently mis-placed anchor).
    """
    annotation_type = annotation_type_for(mention.pubtator_type)
    if annotation_type is None:
        return None, "unsupported-type"

    pp = _containing(paired, mention.offset, mention.length)
    if pp is None:
        return None, "non-persisted-passage"

    concept_iri = concept_iri_for(mention.pubtator_type, mention.identifier)
    if concept_iri is None:
        return None, "unnormalized-concept"

    file_idx = pp.file_char_base + (mention.offset - pp.bioc_offset)
    exact = file_text[file_idx : file_idx + mention.length]
    if exact != mention.text:
        raise SourceTextError(
            f"offset slice {exact!r} != BioC mention text {mention.text!r} "
            f"at file index {file_idx} (offset drift); aborting"
        )

    passage_start = pp.file_char_base
    passage_end = pp.file_char_base + pp.bioc_len
    prefix_start = max(passage_start, file_idx - _CONTEXT)
    suffix_end = min(passage_end, file_idx + mention.length + _CONTEXT)
    selector = TextQuoteSelector(
        exact=exact,
        prefix=file_text[prefix_start:file_idx],
        suffix=file_text[file_idx + mention.length : suffix_end],
    )

    match_text = f"{annotation_type}|{concept_iri}|{file_idx}:{mention.length}|{exact}"
    planned = PlannedAnnotation(
        target=SpecificResource(source=source_md_name, selector=selector),
        annotation_type=annotation_type,
        motivation=Motivation.IDENTIFYING,
        body=IriBody(iri=concept_iri),
        match_text=match_text,
        source_name=f"pubtator3:{release}:seeder-v1",
    )
    return planned, None
```

- [ ] **Step 4: Run them to confirm they pass**

Run: `uv run --frozen pytest tests/test_pubtator_seed.py -k plan_mention -v`
Expected: PASS (all six).

- [ ] **Step 5: Lint + type-check**

Run: `uv run --frozen ruff check src/science_tool/annotation/pubtator_seed.py tests/test_pubtator_seed.py`
Run: `uv run --frozen pyright src/science_tool/annotation/pubtator_seed.py tests/test_pubtator_seed.py`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/annotation/pubtator_seed.py science/tests/test_pubtator_seed.py
git commit -m "pubtator-seed: mention -> PlannedAnnotation (slice-verify, clamped selector, span match_text)"
```

---

### Task 6: Orchestrator `seed_pubtator` (+ reusable raw-BioC fetch)

**Files:**
- Modify: `science/src/science_tool/annotation/source_text.py` (factor out `fetch_bioc_record`)
- Modify: `science/src/science_tool/annotation/pubtator_seed.py`
- Test: `science/tests/test_pubtator_seed.py`

- [ ] **Step 1: Factor a reusable raw-BioC fetch out of Phase 1**

In `source_text.py`, refactor `_fetch_bioc` so the raw record is reachable. Replace the existing `_fetch_bioc` with a public `fetch_bioc_record` plus a thin `_fetch_bioc` that delegates:

```python
def fetch_bioc_record(
    pmid: str, client: httpx.Client, limiter: RateLimiter, cfg: FetchConfig
) -> tuple[dict[str, Any] | None, str | None]:
    """Fetch the raw PubTator3 BioC JSON record. Returns (record-or-None, err-or-None)."""
    _ = cfg  # reserved for future polite-pool identification / API key
    return _get_json(
        client, limiter, _PUBTATOR3_BIOC_URL, _PUBTATOR3_HOST, params={"pmids": pmid}
    )


def _fetch_bioc(
    pmid: str, client: httpx.Client, limiter: RateLimiter, cfg: FetchConfig
) -> tuple[SourcePassages | None, str | None]:
    """Fetch PubTator3 BioC passages. Returns (passages-or-None, err-or-None)."""
    data, err = fetch_bioc_record(pmid, client, limiter, cfg)
    if not data:
        return None, err
    return parse_bioc_passages(data), err
```

Run the existing Phase 1 suite to confirm the refactor is behavior-preserving:
Run: `uv run --frozen pytest tests/test_source_text.py -q`
Expected: PASS (unchanged count).

- [ ] **Step 2: Write the failing orchestrator test**

Add to `tests/test_pubtator_seed.py` (helpers + the main hermetic round-trip). This reuses Phase 1's persist path to lay down a real `.source.md`, so the offset map is authentic:

```python
from datetime import datetime, timezone

import httpx

from science_tool.annotation.io import read_sidecar, sidecar_for_markdown
from science_tool.annotation.pubtator_seed import SeedReport, seed_pubtator
from science_tool.paper_fetch import FetchConfig

NOW = datetime(2026, 6, 15, tzinfo=timezone.utc)


def _cfg(tmp_path):
    return FetchConfig(email="t@example.com", cache_dir=tmp_path / "cache")


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def _paper_entity(tmp_path):
    """Create a paper entity whose pmid resolves, under doc/background/papers/."""
    d = tmp_path / "doc" / "background" / "papers"
    d.mkdir(parents=True)
    (d / "doe2020.md").write_text("---\nkind: paper\npmid: 12345678\n---\n\n# Doe 2020\n")
    return d / "doe2020.md"


def _bioc_handler(request: httpx.Request) -> httpx.Response:
    # PubTator3 BioC export endpoint -> the fixture; Europe PMC -> empty.
    if "pubtator3-api" in str(request.url):
        return httpx.Response(200, json=BIOC_FIXTURE)
    return httpx.Response(200, json={"resultList": {"result": []}})


def test_seed_pubtator_end_to_end(tmp_path):
    from science_tool.annotation.source_text import persist_source

    entity = _paper_entity(tmp_path)
    cfg = _cfg(tmp_path)
    # Phase 1: write a real .source.md (abstract floor only; INTRO body is non-persisted).
    persist_source(
        project_root=tmp_path, identifier="12345678", cfg=cfg, http=_client(_bioc_handler)
    )
    source_md = entity.parent / "doe2020.source.md"
    assert source_md.exists()

    # Phase 2a: seed.
    report = seed_pubtator(
        project_root=tmp_path,
        identifier="12345678",
        cfg=cfg,
        actor="tester",
        now=NOW,
        http=_client(_bioc_handler),
    )
    assert isinstance(report, SeedReport)
    # 2 BRCA1 (gene) + 1 disease + 1 chemical + 1 species + 1 rsID variant = 6 written.
    assert report.written == 6
    # Skips: 1 tmVar (unnormalized) + 1 TP53 (non-persisted INTRO body).
    assert report.skipped.get("unnormalized-concept") == 1
    assert report.skipped.get("non-persisted-passage") == 1

    sidecar = read_sidecar(sidecar_for_markdown(source_md))
    assert len(sidecar.annotations) == 6
    # Every seeded annotation carries a content_hash (pubtator3: is hash-required).
    assert all(a.content_hash for a in sidecar.annotations)


def test_seed_pubtator_idempotent_rerun(tmp_path):
    from science_tool.annotation.source_text import persist_source

    _paper_entity(tmp_path)
    cfg = _cfg(tmp_path)
    persist_source(project_root=tmp_path, identifier="12345678", cfg=cfg, http=_client(_bioc_handler))
    first = seed_pubtator(project_root=tmp_path, identifier="12345678", cfg=cfg, actor="t", now=NOW, http=_client(_bioc_handler))
    second = seed_pubtator(project_root=tmp_path, identifier="12345678", cfg=cfg, actor="t", now=NOW, http=_client(_bioc_handler))
    assert first.written == 6
    assert second.written == 0  # 4-tuple skip -> fully idempotent


def test_seed_pubtator_missing_source_md_fails_loud(tmp_path):
    _paper_entity(tmp_path)  # entity exists, but no .source.md
    cfg = _cfg(tmp_path)
    with pytest.raises(SourceTextError, match="persist-source"):
        seed_pubtator(project_root=tmp_path, identifier="12345678", cfg=cfg, actor="t", now=NOW, http=_client(_bioc_handler))


def test_seed_pubtator_no_bioc_record_is_noop(tmp_path):
    from science_tool.annotation.source_text import persist_source

    _paper_entity(tmp_path)
    cfg = _cfg(tmp_path)

    def epmc_only(request: httpx.Request) -> httpx.Response:
        # PubTator empty so persist falls back to EPMC abstract; seed then no-ops.
        if "pubtator3-api" in str(request.url):
            return httpx.Response(200, json={"PubTator3": []})
        return httpx.Response(
            200,
            json={"resultList": {"result": [{"abstractText": "An abstract.", "license": "CC-BY"}]}},
        )

    persist_source(project_root=tmp_path, identifier="12345678", cfg=cfg, http=_client(epmc_only))
    report = seed_pubtator(project_root=tmp_path, identifier="12345678", cfg=cfg, actor="t", now=NOW, http=_client(epmc_only))
    assert report.written == 0
    assert report.note is not None
```

- [ ] **Step 3: Run them to confirm they fail**

Run: `uv run --frozen pytest tests/test_pubtator_seed.py -k seed_pubtator -v`
Expected: FAIL (`SeedReport` / `seed_pubtator` undefined).

- [ ] **Step 4: Implement the orchestrator**

Add to `pubtator_seed.py`. New imports at the top:

```python
import httpx

from science_tool.annotation.io import (
    atomic_write_text,
    read_sidecar,
    serialize_sidecar,
    sidecar_for_markdown,
)
from science_tool.annotation.audit import merge_planned
from science_tool.annotation.model import Sidecar
from science_tool.annotation.source_text import (
    PUBTATOR3_API_VERSION,
    fetch_bioc_record,
    normalize_doi,
    normalize_pmid,
    parse_bioc_passages,
    resolve_paper_entity,
)
from science_tool.paper_fetch import FetchConfig, RateLimiter
from datetime import datetime
```

(Several of these — `SourcePassages`, `SourceTextError`, `raw_frontmatter`, `Path` — are already imported from earlier tasks; do not duplicate. `normalize_doi`/`normalize_pmid`/`parse_bioc_passages`/`PUBTATOR3_API_VERSION` are re-exported from `source_text`.)

```python
@dataclass(frozen=True)
class SeedReport:
    written: int
    skipped: dict[str, int]
    note: str | None = None


def seed_pubtator(
    *,
    project_root: Path,
    identifier: str,
    cfg: FetchConfig,
    actor: str,
    now: datetime,
    http: httpx.Client | None = None,
) -> SeedReport:
    """Seed PubTator3 entity-mention annotations into `<citekey>.source.anno.trig`.

    Requires an existing `<citekey>.source.md` (fail loud otherwise). Re-fetches the
    raw BioC record for the entity's PMID, converts each entity mention, and merges
    the planned rows idempotently. PubMed-only: no PMID / no BioC record -> no-op.
    """
    doi = normalize_doi(identifier)
    pmid = None if doi else normalize_pmid(identifier)
    resolved = resolve_paper_entity(project_root, doi=doi, pmid=pmid)

    source_md = resolved.directory / f"{resolved.citekey}.source.md"
    if not source_md.is_file():
        raise SourceTextError(
            f"{source_md} not found; run `science paper persist-source {identifier}` first."
        )
    file_text, persisted = load_persisted_passages(source_md)

    skipped: Counter[str] = Counter()
    if not resolved.pmid:
        return SeedReport(written=0, skipped={}, note="no PMID; PubTator3 is PubMed-only")

    owns = http is None
    client = http or httpx.Client(
        timeout=cfg.http_timeout, headers={"User-Agent": f"science/0.1 (mailto:{cfg.email})"}
    )
    try:
        limiter = RateLimiter(cfg)
        record, err = fetch_bioc_record(resolved.pmid, client, limiter, cfg)
    finally:
        if owns:
            client.close()

    if not record:
        return SeedReport(written=0, skipped={}, note=f"no PubTator3 record ({err or 'no record'})")

    parsed = parse_bioc_passages(record)
    if parsed is None:
        return SeedReport(written=0, skipped={}, note="PubTator3 record had no usable passages")

    release = parsed.release or PUBTATOR3_API_VERSION
    paired = pair_passages(file_text, persisted, parsed)
    mentions = parse_bioc_entity_annotations(record)

    planned = []
    for m in mentions:
        p, reason = plan_mention(
            file_text, paired, m, release=release, source_md_name=source_md.name
        )
        if p is not None:
            planned.append(p)
        elif reason is not None:
            skipped[reason] += 1

    sidecar_path = sidecar_for_markdown(source_md)
    sidecar = read_sidecar(sidecar_path) if sidecar_path.exists() else Sidecar()
    new_sidecar, written = merge_planned(sidecar, planned, actor=actor, now=now)
    if written:
        atomic_write_text(sidecar_path, serialize_sidecar(new_sidecar))

    return SeedReport(written=len(written), skipped=dict(skipped), note=None)
```

- [ ] **Step 5: Run the full module to confirm it passes**

Run: `uv run --frozen pytest tests/test_pubtator_seed.py -q`
Expected: PASS (all tasks' tests green).

- [ ] **Step 6: Lint + type-check both touched source files + the test**

Run: `uv run --frozen ruff check src/science_tool/annotation/pubtator_seed.py src/science_tool/annotation/source_text.py tests/test_pubtator_seed.py`
Run: `uv run --frozen pyright src/science_tool/annotation/pubtator_seed.py src/science_tool/annotation/source_text.py tests/test_pubtator_seed.py`
Expected: clean.

- [ ] **Step 7: Commit**

```bash
git add science/src/science_tool/annotation/pubtator_seed.py science/src/science_tool/annotation/source_text.py science/tests/test_pubtator_seed.py
git commit -m "pubtator-seed: seed_pubtator orchestrator + reusable raw-BioC fetch"
```

---

### Task 7: CLI subcommand `science annotate pubtator`

**Files:**
- Modify: `science/src/science_tool/annotation/cli.py`
- Test: `science/tests/test_cli_annotate_pubtator.py`

- [ ] **Step 1: Write the failing CLI test**

Create `science/tests/test_cli_annotate_pubtator.py`:

```python
from __future__ import annotations

import httpx
from click.testing import CliRunner

from science_tool.annotation.cli import annotate_group

# Inline a minimal BioC record (do NOT cross-import from tests.test_pubtator_seed —
# `tests` is not an importable package here; only a conftest.py exists).
_CLI_BIOC = {
    "PubTator3": [
        {
            "id": "12345678",
            "infons": {"_release": "2025-01"},
            "passages": [
                {
                    "infons": {"type": "title"},
                    "offset": 0,
                    "text": "BRCA1 in breast cancer",
                    "annotations": [
                        {"infons": {"identifier": "672", "type": "Gene"}, "text": "BRCA1", "locations": [{"offset": 0, "length": 5}]},
                        {"infons": {"identifier": "MESH:D001943", "type": "Disease"}, "text": "breast cancer", "locations": [{"offset": 9, "length": 13}]},
                    ],
                },
                {"infons": {"type": "abstract"}, "offset": 23, "text": "An abstract sentence.", "annotations": []},
            ],
        }
    ]
}


def _handler(request: httpx.Request) -> httpx.Response:
    if "pubtator3-api" in str(request.url):
        return httpx.Response(200, json=_CLI_BIOC)
    return httpx.Response(200, json={"resultList": {"result": []}})


def _entity(tmp_path):
    d = tmp_path / "doc" / "background" / "papers"
    d.mkdir(parents=True)
    (d / "doe2020.md").write_text("---\nkind: paper\npmid: 12345678\n---\n\n# Doe 2020\n")
    return d


def test_cli_pubtator_seeds(tmp_path, monkeypatch):
    from science_tool.annotation import source_text

    _entity(tmp_path)
    # Inject the MockTransport client into both persist + seed by monkeypatching the
    # module-level httpx.Client constructor used when http=None is passed through CLI.
    real_client = httpx.Client

    def _factory(*args, **kwargs):
        return real_client(transport=httpx.MockTransport(_handler))

    monkeypatch.setattr("science_tool.annotation.source_text.httpx.Client", _factory)
    monkeypatch.setattr("science_tool.annotation.pubtator_seed.httpx.Client", _factory)

    runner = CliRunner()
    # First persist the source via the Phase 1 path, then seed.
    from science_tool.cli import main as root_main

    persist = runner.invoke(
        root_main,
        ["paper", "persist-source", "12345678", "--project-root", str(tmp_path), "--email", "t@example.com"],
    )
    assert persist.exit_code == 0, persist.output

    result = runner.invoke(
        annotate_group,
        ["pubtator", "12345678", "--project-root", str(tmp_path), "--email", "t@example.com", "--actor", "tester"],
    )
    assert result.exit_code == 0, result.output
    assert "Wrote 2" in result.output  # gene + disease from the inline title passage


def test_cli_pubtator_missing_source_md_errors(tmp_path):
    _entity(tmp_path)  # entity but no .source.md
    runner = CliRunner()
    result = runner.invoke(
        annotate_group,
        ["pubtator", "12345678", "--project-root", str(tmp_path), "--email", "t@example.com"],
    )
    assert result.exit_code != 0
    assert "persist-source" in result.output
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `uv run --frozen pytest tests/test_cli_annotate_pubtator.py -v`
Expected: FAIL (`annotate pubtator` command does not exist → click usage error / nonzero).

- [ ] **Step 3: Implement the subcommand**

In `science/src/science_tool/annotation/cli.py`, add (mirror the `persist-source` idiom; place it near the other `annotate_group` commands):

```python
@annotate_group.command("pubtator")
@click.argument("identifier")
@click.option(
    "--project-root",
    "project_root",
    default=None,
    type=click.Path(path_type=Path, file_okay=False),
    help="Project root (defaults to the current directory).",
)
@click.option(
    "--email",
    default=None,
    help="Contact email for polite-pool APIs (falls back to $SCIENCE_CONTACT_EMAIL).",
)
@click.option(
    "--cache-dir",
    default=None,
    type=click.Path(path_type=Path),
    help="Override cache directory (defaults to $SCIENCE_CACHE_DIR or ~/.cache/science).",
)
@click.option("--actor", default="science-annotate-cli", help="Identity recorded as the annotation creator.")
def pubtator_cmd(
    identifier: str,
    project_root: Optional[Path],
    email: Optional[str],
    cache_dir: Optional[Path],
    actor: str,
) -> None:
    """Seed PubTator3 entity-mention annotations into `<citekey>.source.anno.trig`.

    Requires an existing `<citekey>.source.md` (run `science paper persist-source`
    first). PubMed-only: papers with no PubTator3 record are a graceful no-op.
    """
    import os

    from science_tool.annotation.pubtator_seed import seed_pubtator
    from science_tool.annotation.source_text import SourceTextError
    from science_tool.paper_fetch import FetchConfig

    resolved_email = email or os.environ.get("SCIENCE_CONTACT_EMAIL")
    if not resolved_email:
        raise click.ClickException(
            "Contact email is required. Pass --email or set $SCIENCE_CONTACT_EMAIL."
        )
    cfg_kwargs: dict[str, object] = {"email": resolved_email}
    if cache_dir is not None:
        cfg_kwargs["cache_dir"] = cache_dir
    cfg = FetchConfig(**cfg_kwargs)
    root = (project_root or Path.cwd()).resolve()
    try:
        report = seed_pubtator(
            project_root=root,
            identifier=identifier,
            cfg=cfg,
            actor=actor,
            now=datetime.now(timezone.utc),
        )
    except SourceTextError as exc:
        raise click.ClickException(str(exc)) from exc

    if report.note:
        click.echo(report.note)
    skips = ", ".join(f"{k}={v}" for k, v in sorted(report.skipped.items()))
    click.echo(f"Wrote {report.written} annotation(s)" + (f"; skipped {skips}" if skips else ""))
```

Confirm the file already imports `Path`, `Optional`, `datetime`, `timezone`, and `click` at module top (it does — lines 1-20). If `Optional` is not imported there, use `Path | None` in the signature instead.

- [ ] **Step 4: Run it to confirm it passes**

Run: `uv run --frozen pytest tests/test_cli_annotate_pubtator.py -v`
Expected: PASS (both tests).

- [ ] **Step 5: Lint + type-check**

Run: `uv run --frozen ruff check src/science_tool/annotation/cli.py tests/test_cli_annotate_pubtator.py`
Run: `uv run --frozen pyright src/science_tool/annotation/cli.py tests/test_cli_annotate_pubtator.py`
Expected: clean (cli.py may carry pre-existing pyright findings unrelated to this change; do not introduce new ones in the added block).

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/annotation/cli.py science/tests/test_cli_annotate_pubtator.py
git commit -m "pubtator-seed: science annotate pubtator CLI subcommand"
```

---

### Task 8: Full-suite gate + verifier round-trip check

**Files:**
- Test: `science/tests/test_pubtator_seed.py` (one added test)

- [ ] **Step 1: Add a verifier round-trip test**

Confirm every seeded selector re-resolves through the standard annotation verifier against the rendered `.source.md` (the parent spec's primary correctness guarantee). Add to `tests/test_pubtator_seed.py`:

```python
def test_seeded_selectors_resolve_via_verifier(tmp_path):
    from science_tool.annotation.source_text import persist_source
    from science_tool.annotation.verify import verify_path

    _paper_entity(tmp_path)
    cfg = _cfg(tmp_path)
    persist_source(project_root=tmp_path, identifier="12345678", cfg=cfg, http=_client(_bioc_handler))
    seed_pubtator(project_root=tmp_path, identifier="12345678", cfg=cfg, actor="t", now=NOW, http=_client(_bioc_handler))

    # verify_path(root) walks the root for *.anno.trig and re-resolves every selector
    # against its rendered source file. VerifyReport exposes count properties
    # (.broken/.fuzzy/.source_missing) — there is no `.unresolved`.
    report = verify_path(tmp_path)
    assert report.broken == 0, report.issues
    assert report.fuzzy == 0, report.issues
    assert report.source_missing == 0, report.issues
```

- [ ] **Step 2: Run the new test**

Run: `uv run --frozen pytest tests/test_pubtator_seed.py::test_seeded_selectors_resolve_via_verifier -v`
Expected: PASS.

- [ ] **Step 3: Run the full annotation + seeder suite**

Run: `uv run --frozen pytest tests/test_pubtator_seed.py tests/test_cli_annotate_pubtator.py tests/test_source_text.py tests/test_cli_persist_source.py -q`
Expected: PASS (Phase 1 + Phase 2a all green).

- [ ] **Step 4: Run the whole project test suite**

Run: `uv run --frozen pytest -q`
Expected: PASS (no regressions; project addopts already exclude `snapshot`/`real_projects`).

- [ ] **Step 5: Final lint + type sweep**

Run: `uv run --frozen ruff check src/science_tool/annotation/pubtator_seed.py src/science_tool/annotation/source_text.py src/science_tool/annotation/cli.py src/science_tool/annotation/model.py tests/test_pubtator_seed.py tests/test_cli_annotate_pubtator.py`
Run: `uv run --frozen pyright src/science_tool/annotation/pubtator_seed.py src/science_tool/annotation/source_text.py tests/test_pubtator_seed.py tests/test_cli_annotate_pubtator.py`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add science/tests/test_pubtator_seed.py
git commit -m "pubtator-seed: verifier round-trip + full-suite gate"
```

---

## Self-review notes (author checklist — already applied)

- **Spec coverage:** CLI name/home (Task 7), require-`.source.md`-fail-loud (Task 6), ordered passage bridge + duplicate-text + drift-fail-loud (Task 4), slice-verify (Task 5), span-discriminating `match_text` by mention `file_idx` (Task 5), six `entity-<type>` types + identifiers.org colon IRIs + Biolink-class docs map (Tasks 1–2), `pubtator3:` hash prefix + `seeder-v1` source identity + idempotency (Tasks 1, 6), skip-and-count by reason (Tasks 5–6), graceful no-op (Task 6), verifier round-trip (Task 8). All present.
- **No model change beyond the one registered prefix** — `sci:sourceTextHash` and relations stay out (later phases).
- **Type consistency:** `BiocMention`, `PersistedPassage`, `PairedPassage`, `SeedReport`, `plan_mention`, `pair_passages`, `seed_pubtator`, `fetch_bioc_record`, `concept_iri_for`, `annotation_type_for` are used with identical signatures across tasks.
- **Residual risk (accepted):** PubTator `infons` identifier/type variants — the `concept_iri_for` validators and `_TYPE_TO_ENTITY` map are pinned against `BIOC_FIXTURE`; the fixture is marked for validation against a live response before a `seeder-v1` release. This is the known fixture-realism risk the design called out.

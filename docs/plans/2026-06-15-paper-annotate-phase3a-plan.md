# Paper-Annotate Phase 3a — Statement Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** An LLM agent extracts proposition/question/hypothesis statements from a paper's `.source.md`, grounded in its existing PubTator annotations, persisted as verified span annotations through a new deterministic `science annotate extract` command.

**Architecture:** The agent (brain) emits a `candidates.json`; the deterministic `extract` command (hands) anchors each quote (exact + prefix/suffix → unique-or-skip), derives a normalized section from the offset map, verifies opportunistic concept grounding against active `entity-*` annotations, builds JSON-body `TextualBody` annotations via `merge_planned`, and enforces document-level idempotency through a new `AuditLedger.source_text_hash`. Mirrors the Phase 2 seeder split.

**Tech Stack:** Python 3.11+, `dataclasses`, `rdflib` (TriG sidecars), `click` CLI, `pytest`. Run all commands from the `science/` directory with `uv run --frozen`.

**Design:** `docs/plans/2026-06-15-paper-annotate-phase3a-design.md`.

**New module:** `science/src/science_tool/annotation/statement_extract.py` (the producer, mirroring `pubtator_seed.py`).
**Modified:** `annotation/model.py`, `annotation/io.py`, `annotation/ledger.py`, `annotation/cli.py`, `docs/conventions/annotation-tokens.md`.
**New skill files:** `agents/paper-annotate.md`, `commands/annotate-paper.md`.
**Tests:** `science/tests/test_statement_extract.py`, `science/tests/test_annotate_extract_cli.py`.

**Key reused machinery (read before starting):**
- `pubtator_seed.py`: `load_persisted_passages` + `PersistedPassage` (offset-map loader), `_CONTEXT = 60` (prefix/suffix window), the producer/orchestrator shape. **Import `load_persisted_passages` and `PersistedPassage` from `pubtator_seed`.**
- `audit.py::merge_planned` (single-`source_name` batch → written rows; 4-tuple dedup `(source, selector.exact, lifted_from, match_text)`; sets `content_hash(exact, source)`).
- `sources/base.py::PlannedAnnotation(target, annotation_type, motivation, body, match_text, source_name, lifted_from=None)`.
- `ledger.py::find_or_create_ledger(sidecar, source_version, *, now) -> (sidecar, ledger)` and `_ledger_id_for`.
- `io.py`: `read_sidecar`, `serialize_sidecar`, `sidecar_for_markdown`, `atomic_write_text`; `_iter_ledgers` / `_emit_ledger` (ledger round-trip).
- `source_text.py`: `write_source_md(*, directory, citekey, abstract, fulltext, retrieved_from, license_, licensed, pmid, doi)`, `SourcePassages`, `Passage`, `SourceTextError`; frontmatter `text_sha256` is the hash of the body.
- `commons/frontmatter.py::raw_frontmatter`.
- `model.py`: `Status`, `Motivation.CLASSIFYING`, `IriBody`, `TextualBody`, `TextQuoteSelector`, `SpecificResource`, `Sidecar`, `AuditLedger`, `HASH_REQUIRED_SOURCE_PREFIXES`.

---

## Task 1: Ledger plumbing — `AuditLedger.source_text_hash` + I/O round-trip + `llm-annot:` hash prefix

**Files:**
- Modify: `science/src/science_tool/annotation/model.py` (`AuditLedger`, `HASH_REQUIRED_SOURCE_PREFIXES`)
- Modify: `science/src/science_tool/annotation/io.py` (`_iter_ledgers`, `_emit_ledger`)
- Modify: `science/src/science_tool/annotation/ledger.py` (new `ledger_set_source_text_hash`)
- Test: `science/tests/test_statement_extract.py`

- [ ] **Step 1: Write the failing test**

Create `science/tests/test_statement_extract.py` with:

```python
import json
from datetime import datetime, timezone
from pathlib import Path

from science_tool.annotation.io import read_sidecar, serialize_sidecar, write_sidecar
from science_tool.annotation.ledger import (
    find_or_create_ledger,
    ledger_set_source_text_hash,
)
from science_tool.annotation.model import (
    AuditLedger,
    HASH_REQUIRED_SOURCE_PREFIXES,
    Sidecar,
)

_NOW = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)


def test_llm_annot_is_hash_required():
    assert "llm-annot:" in HASH_REQUIRED_SOURCE_PREFIXES


def test_ledger_source_text_hash_defaults_none():
    led = AuditLedger(id="ledger-x", source="s", audited_hashes=(), modified=_NOW)
    assert led.source_text_hash is None


def test_ledger_set_source_text_hash_replaces_and_bumps_modified():
    led = AuditLedger(id="ledger-x", source="s", audited_hashes=(), modified=_NOW)
    later = datetime(2026, 6, 16, tzinfo=timezone.utc)
    updated = ledger_set_source_text_hash(led, "abc123", now=later)
    assert updated.source_text_hash == "abc123"
    assert updated.modified == later
    # idempotent: same hash returns the same object, no modified bump
    assert ledger_set_source_text_hash(updated, "abc123", now=_NOW) is updated


def test_ledger_source_text_hash_trig_round_trip(tmp_path: Path):
    led = AuditLedger(
        id="ledger-claude-sonnet-4-6-paper-annotate-v1",
        source="llm-annot:claude-sonnet-4-6:paper-annotate-v1",
        audited_hashes=("h1", "h2"),
        modified=_NOW,
        source_text_hash="deadbeef",
    )
    path = tmp_path / "p.anno.trig"
    write_sidecar(path, Sidecar(ledgers=(led,)))
    assert "sci:sourceTextHash" in path.read_text(encoding="utf-8")
    back = read_sidecar(path)
    assert back.ledgers[0].source_text_hash == "deadbeef"
    assert back.ledgers[0].audited_hashes == ("h1", "h2")


def test_legacy_ledger_without_predicate_reads_none(tmp_path: Path):
    led = AuditLedger(id="ledger-y", source="lint:x", audited_hashes=(), modified=_NOW)
    path = tmp_path / "q.anno.trig"
    write_sidecar(path, Sidecar(ledgers=(led,)))
    text = path.read_text(encoding="utf-8")
    assert "sci:sourceTextHash" not in text  # None → predicate omitted
    assert read_sidecar(path).ledgers[0].source_text_hash is None
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `science/`): `uv run --frozen pytest tests/test_statement_extract.py -v`
Expected: FAIL — `ImportError: cannot import name 'ledger_set_source_text_hash'` (and the field/prefix assertions fail).

- [ ] **Step 3: Implement**

In `model.py`, add `"llm-annot:"` to the tuple:

```python
HASH_REQUIRED_SOURCE_PREFIXES: tuple[str, ...] = (
    "llm-audit:",
    "lint:",
    "marker-scanner:",
    "pubtator3:",
    "llm-annot:",
)
```

In `model.py`, extend `AuditLedger`:

```python
@dataclass(frozen=True)
class AuditLedger:
    id: str
    source: str
    audited_hashes: tuple[str, ...]
    modified: datetime
    source_text_hash: str | None = None
```

In `io.py::_iter_ledgers`, read the new predicate (insert after the `hashes` block, before `modified`):

```python
        sth_node = ds.value(subj, SCI.sourceTextHash)
        source_text_hash = str(sth_node) if sth_node is not None else None
        modified = _read_dt(_required(ds, subj, DCTERMS.modified, context=ctx))
        out.append(
            AuditLedger(
                id=led_id,
                source=source,
                audited_hashes=hashes,
                modified=modified,
                source_text_hash=source_text_hash,
            )
        )
```

In `io.py::_emit_ledger`, emit it only when present (keeps `dc:modified` as the `.`-terminated final line):

```python
def _emit_ledger(led: AuditLedger) -> "list[str]":
    hashes = " ".join(_str_lit(h) for h in led.audited_hashes)
    lines = [
        f"  anno:{led.id} a sci:AuditLedger ;",
        f"    sci:source         {_str_lit(led.source)} ;",
        f"    sci:auditedHashes  ( {hashes} ) ;",
    ]
    if led.source_text_hash is not None:
        lines.append(f"    sci:sourceTextHash {_str_lit(led.source_text_hash)} ;")
    lines.append(f"    dc:modified        {_dt_lit(led.modified)} .")
    return lines
```

In `ledger.py`, add the setter (after `ledger_append_hash`):

```python
def ledger_set_source_text_hash(
    ledger: AuditLedger, source_text_hash: str, *, now: datetime
) -> AuditLedger:
    """Return a ledger with the document-level source_text_hash set; idempotent.

    Unchanged hash returns the SAME object (no modified bump), so a re-run that
    re-records an identical hash produces no sidecar churn.
    """
    if ledger.source_text_hash == source_text_hash:
        return ledger
    return replace(
        ledger,
        source_text_hash=source_text_hash,
        modified=now,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --frozen pytest tests/test_statement_extract.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/annotation/model.py science/src/science_tool/annotation/io.py science/src/science_tool/annotation/ledger.py science/tests/test_statement_extract.py
git commit -m "feat(annotation): add AuditLedger.source_text_hash doc guard + llm-annot hash prefix"
```

---

## Task 2: Section normalization + containing-passage lookup

**Files:**
- Create: `science/src/science_tool/annotation/statement_extract.py`
- Test: `science/tests/test_statement_extract.py`

- [ ] **Step 1: Write the failing test** (append)

```python
from science_tool.annotation.pubtator_seed import PersistedPassage
from science_tool.annotation.statement_extract import (
    CANONICAL_SECTIONS,
    _containing_passage,
    normalize_section,
)


def test_normalize_known_sections():
    assert normalize_section("title") == "title"
    assert normalize_section("abstract") == "abstract"
    assert normalize_section("INTRO") == "introduction"
    assert normalize_section("METHODS") == "methods"
    assert normalize_section("RESULTS") == "results"
    assert normalize_section("DISCUSS") == "discussion"
    assert normalize_section("CONCL") == "conclusion"
    assert normalize_section("FIG") == "figure"
    assert normalize_section("TABLE") == "table"


def test_normalize_unknown_section_is_other():
    assert normalize_section("ACK_FUND") == "other"
    assert normalize_section("") == "other"
    assert normalize_section("passage") == "other"


def test_canonical_sections_closed_set():
    assert "results" in CANONICAL_SECTIONS
    assert "other" in CANONICAL_SECTIONS


def test_containing_passage_finds_enclosing():
    passages = [
        PersistedPassage(section="title", file_char_base=100, length=10),
        PersistedPassage(section="RESULTS", file_char_base=200, length=50),
    ]
    pp = _containing_passage(passages, 210, 5)
    assert pp is not None and pp.section == "RESULTS"
    # span straddling a passage boundary → None
    assert _containing_passage(passages, 248, 5) is None
    # span outside every passage (e.g. a heading) → None
    assert _containing_passage(passages, 130, 5) is None
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run --frozen pytest tests/test_statement_extract.py -k "section or containing" -v`
Expected: FAIL — `ModuleNotFoundError`/`ImportError` for `statement_extract`.

- [ ] **Step 3: Implement** — create `statement_extract.py` with the module preamble + these:

```python
"""Phase 3a: agent statement-extraction persistence.

Turn an LLM agent's candidate proposition/question/hypothesis spans into
oa:TextQuoteSelector annotations anchored in an existing `<citekey>.source.md`,
written to its `.source.anno.trig` sidecar via the existing annotation machinery.
The agent decides; this module owns anchoring, section derivation, grounding
verification, dedup, and document-level idempotency.

See docs/plans/2026-06-15-paper-annotate-phase3a-design.md.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Any

from science_tool.annotation.audit import merge_planned
from science_tool.annotation.io import (
    atomic_write_text,
    read_sidecar,
    serialize_sidecar,
    sidecar_for_markdown,
)
from science_tool.annotation.ledger import (
    find_or_create_ledger,
    ledger_set_source_text_hash,
)
from science_tool.annotation.model import (
    IriBody,
    Motivation,
    Sidecar,
    SpecificResource,
    Status,
    TextQuoteSelector,
    TextualBody,
)
from science_tool.annotation.pubtator_seed import (
    PersistedPassage,
    load_persisted_passages,
    _CONTEXT,
)
from science_tool.annotation.source_text import SourceTextError
from science_tool.annotation.sources.base import PlannedAnnotation
from science_tool.commons.frontmatter import raw_frontmatter

# --- Section normalization ----------------------------------------------------

CANONICAL_SECTIONS: frozenset[str] = frozenset({
    "title", "abstract", "introduction", "methods", "results",
    "discussion", "conclusion", "figure", "table", "other",
})

# Raw BioC `infons.type` (lowercased) -> canonical section. Anything absent -> "other".
_SECTION_NORMALIZE: dict[str, str] = {
    "title": "title",
    "abstract": "abstract",
    "intro": "introduction",
    "introduction": "introduction",
    "methods": "methods",
    "method": "methods",
    "materials and methods": "methods",
    "results": "results",
    "result": "results",
    "discuss": "discussion",
    "discussion": "discussion",
    "concl": "conclusion",
    "conclusion": "conclusion",
    "conclusions": "conclusion",
    "fig": "figure",
    "figure": "figure",
    "table": "table",
}


def normalize_section(raw: str) -> str:
    """Map a raw `.source.md` passage section to the closed canonical vocabulary."""
    return _SECTION_NORMALIZE.get(raw.strip().lower(), "other")


def _containing_passage(
    persisted: list[PersistedPassage], file_idx: int, length: int
) -> PersistedPassage | None:
    """The persisted passage wholly containing [file_idx, file_idx+length), or None.

    None means the span anchored outside every passage body (e.g. a heading or
    frontmatter) or straddles a passage boundary — the caller skips it.
    """
    end = file_idx + length
    for pp in persisted:
        if pp.file_char_base <= file_idx and end <= pp.file_char_base + pp.length:
            return pp
    return None
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run --frozen pytest tests/test_statement_extract.py -k "section or containing" -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/annotation/statement_extract.py science/tests/test_statement_extract.py
git commit -m "feat(statement-extract): section normalization + containing-passage lookup"
```

---

## Task 3: Strict candidate parsing

**Files:**
- Modify: `science/src/science_tool/annotation/statement_extract.py`
- Test: `science/tests/test_statement_extract.py`

- [ ] **Step 1: Write the failing test** (append)

```python
import json

import pytest

from science_tool.annotation.statement_extract import (
    Candidate,
    CandidateError,
    MAX_CANDIDATES,
    MAX_FIELD_CHARS,
    parse_candidates,
)


def _one(**over):
    base = {
        "type": "proposition", "exact": "X drives Y", "prefix": "we found ",
        "suffix": " here.", "stance": "asserted",
    }
    base.update(over)
    return json.dumps({"candidates": [base]})


def test_parse_minimal_valid():
    [c] = parse_candidates(_one())
    assert isinstance(c, Candidate)
    assert c.type == "proposition" and c.stance == "asserted"
    assert c.subject is None and c.subject_concept is None


def test_parse_optional_fields():
    raw = _one(subject="X", object="Y",
               subject_concept="https://identifiers.org/ncbigene:672")
    [c] = parse_candidates(raw)
    assert c.subject == "X" and c.object == "Y"
    assert c.subject_concept == "https://identifiers.org/ncbigene:672"


def test_parse_rejects_unknown_top_level_key():
    raw = json.dumps({"candidates": [], "junk": 1})
    with pytest.raises(CandidateError, match="unknown top-level"):
        parse_candidates(raw)


def test_parse_rejects_unknown_candidate_field():
    with pytest.raises(CandidateError, match="unknown fields"):
        parse_candidates(_one(weight=0.9))


def test_parse_rejects_unknown_type():
    with pytest.raises(CandidateError, match="type"):
        parse_candidates(_one(type="metaphor"))


def test_parse_rejects_unknown_stance():
    with pytest.raises(CandidateError, match="stance"):
        parse_candidates(_one(stance="maybe"))


def test_parse_rejects_missing_required():
    raw = json.dumps({"candidates": [{"type": "question", "exact": "Q?"}]})
    with pytest.raises(CandidateError, match="missing required"):
        parse_candidates(raw)


def test_parse_rejects_non_string_field():
    with pytest.raises(CandidateError, match="must be a string"):
        parse_candidates(_one(exact=123))


def test_parse_rejects_empty_exact():
    with pytest.raises(CandidateError, match="non-empty"):
        parse_candidates(_one(exact=""))


def test_parse_rejects_over_count():
    many = json.dumps({"candidates": [
        {"type": "proposition", "exact": f"s{i}", "prefix": "",
         "suffix": "", "stance": "asserted"}
        for i in range(MAX_CANDIDATES + 1)
    ]})
    with pytest.raises(CandidateError, match="too many"):
        parse_candidates(many)


def test_parse_rejects_over_length():
    with pytest.raises(CandidateError, match="exceeds"):
        parse_candidates(_one(exact="z" * (MAX_FIELD_CHARS + 1)))


def test_parse_rejects_non_object_input():
    with pytest.raises(CandidateError, match="JSON object"):
        parse_candidates(json.dumps([1, 2]))


def test_parse_rejects_bad_json():
    with pytest.raises(CandidateError, match="not valid JSON"):
        parse_candidates("{not json")
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run --frozen pytest tests/test_statement_extract.py -k parse -v`
Expected: FAIL — `ImportError` for `Candidate`/`parse_candidates`/etc.

- [ ] **Step 3: Implement** — append to `statement_extract.py`:

```python
# --- Candidate parsing (strict, fail-loud) ------------------------------------

STATEMENT_TYPES: frozenset[str] = frozenset({"proposition", "question", "hypothesis"})
STANCES: frozenset[str] = frozenset({"asserted", "negated", "hypothesized", "open"})
MAX_CANDIDATES = 500
MAX_FIELD_CHARS = 2000

_ALLOWED_KEYS = frozenset({
    "type", "exact", "prefix", "suffix", "stance",
    "subject", "object", "subject_concept", "object_concept",
})
_REQUIRED_KEYS = frozenset({"type", "exact", "prefix", "suffix", "stance"})


class CandidateError(ValueError):
    """A candidates.json file that is structurally invalid. Fail loud; write nothing."""


@dataclass(frozen=True)
class Candidate:
    type: str
    exact: str
    prefix: str
    suffix: str
    stance: str
    subject: str | None = None
    object: str | None = None
    subject_concept: str | None = None
    object_concept: str | None = None


def parse_candidates(raw: str) -> list[Candidate]:
    """Parse + strictly validate a candidates.json string into Candidate rows.

    Any structural problem (bad JSON, unknown key, unknown type/stance, wrong field
    type, over-count, over-length, empty exact) raises CandidateError — no silent
    coercion, no partial acceptance.
    """
    try:
        doc = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CandidateError(f"candidates input is not valid JSON: {exc}") from exc
    if not isinstance(doc, dict):
        raise CandidateError("candidates input must be a JSON object with a 'candidates' array")
    extra = set(doc) - {"candidates"}
    if extra:
        raise CandidateError(f"unknown top-level keys: {sorted(extra)}")
    items = doc.get("candidates")
    if not isinstance(items, list):
        raise CandidateError("'candidates' must be a JSON array")
    if len(items) > MAX_CANDIDATES:
        raise CandidateError(f"too many candidates ({len(items)} > {MAX_CANDIDATES})")
    return [_parse_one(item, idx) for idx, item in enumerate(items)]


def _parse_one(item: Any, idx: int) -> Candidate:
    if not isinstance(item, dict):
        raise CandidateError(f"candidate[{idx}] must be a JSON object")
    keys = set(item)
    extra = keys - _ALLOWED_KEYS
    if extra:
        raise CandidateError(f"candidate[{idx}] unknown fields: {sorted(extra)}")
    missing = _REQUIRED_KEYS - keys
    if missing:
        raise CandidateError(f"candidate[{idx}] missing required fields: {sorted(missing)}")

    def _str(name: str, *, optional: bool) -> str | None:
        if optional and (name not in item or item[name] is None):
            return None
        val = item[name]
        if not isinstance(val, str):
            suffix = " or null" if optional else ""
            raise CandidateError(f"candidate[{idx}].{name} must be a string{suffix}")
        if len(val) > MAX_FIELD_CHARS:
            raise CandidateError(
                f"candidate[{idx}].{name} exceeds {MAX_FIELD_CHARS} chars"
            )
        return val

    ctype = _str("type", optional=False)
    if ctype not in STATEMENT_TYPES:
        raise CandidateError(
            f"candidate[{idx}].type {ctype!r} not in {sorted(STATEMENT_TYPES)}"
        )
    exact = _str("exact", optional=False)
    if not exact:
        raise CandidateError(f"candidate[{idx}].exact must be non-empty")
    stance = _str("stance", optional=False)
    if stance not in STANCES:
        raise CandidateError(
            f"candidate[{idx}].stance {stance!r} not in {sorted(STANCES)}"
        )
    return Candidate(
        type=ctype,
        exact=exact,
        prefix=_str("prefix", optional=False),
        suffix=_str("suffix", optional=False),
        stance=stance,
        subject=_str("subject", optional=True),
        object=_str("object", optional=True),
        subject_concept=_str("subject_concept", optional=True),
        object_concept=_str("object_concept", optional=True),
    )
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run --frozen pytest tests/test_statement_extract.py -k parse -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/annotation/statement_extract.py science/tests/test_statement_extract.py
git commit -m "feat(statement-extract): strict candidate JSON parsing"
```

---

## Task 4: Deterministic statement body JSON

**Files:**
- Modify: `science/src/science_tool/annotation/statement_extract.py`
- Test: `science/tests/test_statement_extract.py`

- [ ] **Step 1: Write the failing test** (append)

```python
from science_tool.annotation.statement_extract import statement_body_json


def test_body_minimal_sorted_compact():
    body = statement_body_json(
        section="results", stance="asserted",
        subject=None, object_=None,
        subject_concept=None, object_concept=None,
    )
    assert body == '{"section":"results","stance":"asserted"}'


def test_body_includes_present_optionals_sorted():
    body = statement_body_json(
        section="results", stance="asserted",
        subject="BRCA1 loss", object_="genomic instability",
        subject_concept="https://identifiers.org/ncbigene:672", object_concept=None,
    )
    # keys sorted: object, section, stance, subject, subject_concept
    assert body == (
        '{"object":"genomic instability","section":"results","stance":"asserted",'
        '"subject":"BRCA1 loss","subject_concept":"https://identifiers.org/ncbigene:672"}'
    )


def test_body_is_byte_stable():
    kw = dict(section="methods", stance="hypothesized", subject="A", object_="B",
              subject_concept=None, object_concept=None)
    assert statement_body_json(**kw) == statement_body_json(**kw)
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run --frozen pytest tests/test_statement_extract.py -k body -v`
Expected: FAIL — `ImportError` for `statement_body_json`.

- [ ] **Step 3: Implement** — append to `statement_extract.py`:

```python
# --- Statement body JSON ------------------------------------------------------


def statement_body_json(
    *,
    section: str,
    stance: str,
    subject: str | None,
    object_: str | None,
    subject_concept: str | None,
    object_concept: str | None,
) -> str:
    """Build the deterministic JSON for a statement's TextualBody.

    Always carries section + stance. Optional subject/object phrases and verified
    concept IRIs are included only when present. Sorted keys + compact separators +
    allow_nan=False guarantee finite, byte-stable serialization (clean diffs).
    """
    obj: dict[str, Any] = {"section": section, "stance": stance}
    if subject is not None:
        obj["subject"] = subject
    if object_ is not None:
        obj["object"] = object_
    if subject_concept is not None:
        obj["subject_concept"] = subject_concept
    if object_concept is not None:
        obj["object_concept"] = object_concept
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False)
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run --frozen pytest tests/test_statement_extract.py -k body -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/annotation/statement_extract.py science/tests/test_statement_extract.py
git commit -m "feat(statement-extract): deterministic statement body JSON"
```

---

## Task 5: Anchoring — `find_qualified_spans`

**Files:**
- Modify: `science/src/science_tool/annotation/statement_extract.py`
- Test: `science/tests/test_statement_extract.py`

- [ ] **Step 1: Write the failing test** (append)

```python
from science_tool.annotation.statement_extract import find_qualified_spans


def test_anchor_unique_no_context():
    text = "alpha beta gamma"
    assert find_qualified_spans(text, "beta", "", "") == [6]


def test_anchor_not_found():
    assert find_qualified_spans("alpha beta", "delta", "", "") == []


def test_anchor_repeated_quote_is_ambiguous_without_context():
    text = "the cell. the cell."
    assert find_qualified_spans(text, "the cell", "", "") == [0, 10]


def test_anchor_prefix_disambiguates_repeat():
    text = "the cell. the cell."
    # only the second "the cell" is preceded by ". " ... use a distinguishing prefix
    spans = find_qualified_spans(text, "the cell", ". ", "")
    assert spans == [10]


def test_anchor_suffix_disambiguates_repeat():
    text = "the cell grows. the cell dies."
    spans = find_qualified_spans(text, "the cell", "", " dies")
    assert spans == [16]


def test_anchor_requires_adjacent_prefix():
    text = "we found the result here"
    # prefix must be the text IMMEDIATELY before exact
    assert find_qualified_spans(text, "result", "found ", "") == []  # not adjacent
    assert find_qualified_spans(text, "result", "the ", "") == [9]


def test_anchor_empty_exact_returns_empty():
    assert find_qualified_spans("anything", "", "", "") == []
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run --frozen pytest tests/test_statement_extract.py -k anchor -v`
Expected: FAIL — `ImportError` for `find_qualified_spans`.

- [ ] **Step 3: Implement** — append to `statement_extract.py`:

```python
# --- Anchoring ----------------------------------------------------------------


def find_qualified_spans(
    file_text: str, exact: str, prefix: str, suffix: str
) -> list[int]:
    """Return the start indices of every occurrence of `exact` in `file_text`
    whose immediately-preceding text ends with `prefix` and whose immediately-
    following text starts with `suffix`.

    Empty prefix/suffix impose no constraint on that side. The caller treats
    0 matches as `extract-quote-not-found` and >1 as `extract-quote-ambiguous`.
    """
    if not exact:
        return []
    out: list[int] = []
    start = 0
    while True:
        i = file_text.find(exact, start)
        if i == -1:
            break
        start = i + 1
        if prefix and not file_text[:i].endswith(prefix):
            continue
        if suffix and not file_text[i + len(exact):].startswith(suffix):
            continue
        out.append(i)
    return out
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run --frozen pytest tests/test_statement_extract.py -k anchor -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/annotation/statement_extract.py science/tests/test_statement_extract.py
git commit -m "feat(statement-extract): prefix/suffix span anchoring"
```

---

## Task 6: Grounding + `plan_statement`

**Files:**
- Modify: `science/src/science_tool/annotation/statement_extract.py`
- Test: `science/tests/test_statement_extract.py`

`plan_statement` converts one `Candidate` into a `(PlannedAnnotation | None, skip_reason | None, grounding_dropped)` triple. Skip reasons: `extract-quote-not-found`, `extract-quote-ambiguous`, `extract-anchored-outside-passage`. `grounding_dropped` counts each unverified concept field dropped (statement still planned).

- [ ] **Step 1: Write the failing test** (append)

```python
from science_tool.annotation.model import (
    Annotation,
    IriBody,
    Motivation,
    Sidecar,
    SpecificResource,
    Status,
    TextQuoteSelector,
)
from science_tool.annotation.statement_extract import (
    active_entity_iris,
    plan_statement,
)

_MODEL = "claude-sonnet-4-6"
_GENE = "https://identifiers.org/ncbigene:672"
# A file whose passage body spans [0, len). Build a simple single-passage doc.
_TEXT = "BRCA1 loss drives genomic instability in these tumors and elsewhere."
_PASSAGES = [PersistedPassage(section="RESULTS", file_char_base=0, length=len(_TEXT))]


def _entity_ann(iri: str, status: Status = Status.OPEN) -> Annotation:
    return Annotation(
        id="e1",
        target=SpecificResource(
            source="P.source.md",
            selector=TextQuoteSelector(exact="BRCA1", prefix="", suffix=" loss"),
        ),
        bodies=(IriBody(iri=iri),),
        motivation=Motivation.IDENTIFYING,
        annotation_type="entity-gene",
        source="pubtator3:2024:seeder-v1",
        status=status,
        creator="x",
        created=_NOW,
        content_hash="h",
        modified=(None if status is Status.OPEN else _NOW),
        modified_by=(None if status is Status.OPEN else "x"),
        match_text="entity-gene|...",
    )


def test_active_entity_iris_includes_open_and_ack_excludes_others():
    sc = Sidecar(annotations=(
        _entity_ann(_GENE, Status.OPEN),
        _entity_ann("https://identifiers.org/mesh:D1", Status.ACK),
        _entity_ann("https://identifiers.org/mesh:D2", Status.DISMISSED),
        _entity_ann("https://identifiers.org/mesh:D3", Status.SUPERSEDED),
    ))
    iris = active_entity_iris(sc)
    assert _GENE in iris
    assert "https://identifiers.org/mesh:D1" in iris
    assert "https://identifiers.org/mesh:D2" not in iris
    assert "https://identifiers.org/mesh:D3" not in iris


def _cand(**over) -> Candidate:
    base = dict(type="proposition", exact="BRCA1 loss drives genomic instability",
                prefix="", suffix=" in these", stance="asserted")
    base.update(over)
    return Candidate(**base)  # type: ignore[arg-type]


def test_plan_statement_anchors_and_builds_body():
    p, reason, dropped = plan_statement(
        _TEXT, _PASSAGES, _cand(), active_iris=set(),
        model=_MODEL, source_md_name="P.source.md",
    )
    assert reason is None and dropped == 0 and p is not None
    assert p.annotation_type == "proposition"
    assert p.motivation is Motivation.CLASSIFYING
    assert p.source_name == "llm-annot:claude-sonnet-4-6:paper-annotate-v1"
    assert p.body.format == "application/json"
    assert '"section":"results"' in p.body.value
    # match_text carries the offset discriminator: type|file_idx:length|normalized_exact
    assert p.match_text.startswith("proposition|0:37|")


def test_plan_statement_quote_not_found():
    p, reason, _ = plan_statement(
        _TEXT, _PASSAGES, _cand(exact="absent text"), active_iris=set(),
        model=_MODEL, source_md_name="P.source.md",
    )
    assert p is None and reason == "extract-quote-not-found"


def test_plan_statement_ambiguous():
    text = "the cell. the cell."
    passages = [PersistedPassage(section="RESULTS", file_char_base=0, length=len(text))]
    p, reason, _ = plan_statement(
        text, passages, _cand(exact="the cell", suffix=""), active_iris=set(),
        model=_MODEL, source_md_name="P.source.md",
    )
    assert p is None and reason == "extract-quote-ambiguous"


def test_plan_statement_outside_passage():
    # passage occupies [10, len); anchor at 0 is outside it
    passages = [PersistedPassage(section="RESULTS", file_char_base=10, length=len(_TEXT) - 10)]
    p, reason, _ = plan_statement(
        _TEXT, passages, _cand(exact="BRCA1 loss", suffix=" drives"), active_iris=set(),
        model=_MODEL, source_md_name="P.source.md",
    )
    assert p is None and reason == "extract-anchored-outside-passage"


def test_plan_statement_keeps_verified_grounding():
    p, reason, dropped = plan_statement(
        _TEXT, _PASSAGES, _cand(subject_concept=_GENE), active_iris={_GENE},
        model=_MODEL, source_md_name="P.source.md",
    )
    assert reason is None and dropped == 0 and p is not None
    assert _GENE in p.body.value


def test_plan_statement_drops_unverified_grounding_keeps_statement():
    p, reason, dropped = plan_statement(
        _TEXT, _PASSAGES,
        _cand(subject_concept="https://identifiers.org/ncbigene:999"),
        active_iris={_GENE},
        model=_MODEL, source_md_name="P.source.md",
    )
    assert reason is None and p is not None  # statement kept
    assert dropped == 1
    assert "ncbigene:999" not in p.body.value  # bad grounding dropped


def test_plan_statement_match_text_distinguishes_repeated_identical():
    text = "X drives Y. Later, X drives Y again."
    passages = [PersistedPassage(section="RESULTS", file_char_base=0, length=len(text))]
    p1, _, _ = plan_statement(
        text, passages, _cand(exact="X drives Y", prefix="", suffix=". Later"),
        active_iris=set(), model=_MODEL, source_md_name="P.source.md",
    )
    p2, _, _ = plan_statement(
        text, passages, _cand(exact="X drives Y", prefix="Later, ", suffix=" again"),
        active_iris=set(), model=_MODEL, source_md_name="P.source.md",
    )
    assert p1 is not None and p2 is not None
    assert p1.match_text != p2.match_text  # different file_idx ⇒ distinct dedup keys
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run --frozen pytest tests/test_statement_extract.py -k "active_entity or plan_statement" -v`
Expected: FAIL — `ImportError` for `active_entity_iris`/`plan_statement`.

- [ ] **Step 3: Implement** — append to `statement_extract.py`:

```python
# --- Grounding + planning -----------------------------------------------------


def _llm_annot_source_name(model: str) -> str:
    """The Phase-3a source identity. The `paper-annotate-v1` segment bumps when the
    prompt or body schema changes (see annotation-tokens.md)."""
    return f"llm-annot:{model}:paper-annotate-v1"


def _normalize_text(text: str) -> str:
    """Whitespace-collapsed form used in match_text (stable across trivial respacing)."""
    return " ".join(text.split())


def active_entity_iris(sidecar: Sidecar) -> set[str]:
    """Concept IRIs of all ACTIVE (open|ack) `entity-*` annotations in the sidecar.

    Dismissed/superseded entity annotations are excluded — the same active-set policy
    the agent is told to pass to `annotate list --status open --status ack`.
    """
    out: set[str] = set()
    for a in sidecar.annotations:
        if not a.annotation_type.startswith("entity-"):
            continue
        if a.status not in (Status.OPEN, Status.ACK):
            continue
        for body in a.bodies:
            if isinstance(body, IriBody):
                out.add(body.iri)
    return out


def plan_statement(
    file_text: str,
    persisted: list[PersistedPassage],
    candidate: Candidate,
    *,
    active_iris: set[str],
    model: str,
    source_md_name: str,
) -> tuple[PlannedAnnotation | None, str | None, int]:
    """Convert a Candidate to (PlannedAnnotation | None, skip_reason | None, dropped).

    skip reasons: "extract-quote-not-found", "extract-quote-ambiguous",
    "extract-anchored-outside-passage". `dropped` counts unverified concept fields
    removed (the statement is still planned — grounding is a bonus, never a gate).
    """
    spans = find_qualified_spans(
        file_text, candidate.exact, candidate.prefix, candidate.suffix
    )
    if not spans:
        return None, "extract-quote-not-found", 0
    if len(spans) > 1:
        return None, "extract-quote-ambiguous", 0
    file_idx = spans[0]
    length = len(candidate.exact)

    pp = _containing_passage(persisted, file_idx, length)
    if pp is None:
        return None, "extract-anchored-outside-passage", 0
    section = normalize_section(pp.section)

    dropped = 0
    subject_concept = candidate.subject_concept
    if subject_concept is not None and subject_concept not in active_iris:
        subject_concept = None
        dropped += 1
    object_concept = candidate.object_concept
    if object_concept is not None and object_concept not in active_iris:
        object_concept = None
        dropped += 1

    body = statement_body_json(
        section=section,
        stance=candidate.stance,
        subject=candidate.subject,
        object_=candidate.object,
        subject_concept=subject_concept,
        object_concept=object_concept,
    )

    passage_start = pp.file_char_base
    passage_end = pp.file_char_base + pp.length
    prefix_start = max(passage_start, file_idx - _CONTEXT)
    suffix_end = min(passage_end, file_idx + length + _CONTEXT)
    selector = TextQuoteSelector(
        exact=candidate.exact,
        prefix=file_text[prefix_start:file_idx],
        suffix=file_text[file_idx + length:suffix_end],
    )

    match_text = (
        f"{candidate.type}|{file_idx}:{length}|{_normalize_text(candidate.exact)}"
    )
    planned = PlannedAnnotation(
        target=SpecificResource(source=source_md_name, selector=selector),
        annotation_type=candidate.type,
        motivation=Motivation.CLASSIFYING,
        body=TextualBody(value=body, format="application/json"),
        match_text=match_text,
        source_name=_llm_annot_source_name(model),
    )
    return planned, None, dropped
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run --frozen pytest tests/test_statement_extract.py -k "active_entity or plan_statement" -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/annotation/statement_extract.py science/tests/test_statement_extract.py
git commit -m "feat(statement-extract): grounding verification + plan_statement"
```

---

## Task 7: Orchestrator — `extract_statements` + `check_source_changed` + `ExtractReport`

**Files:**
- Modify: `science/src/science_tool/annotation/statement_extract.py`
- Test: `science/tests/test_statement_extract.py`

- [ ] **Step 1: Write the failing test** (append)

This test builds a REAL `.source.md` via `write_source_md`, so offsets + `text_sha256` are authentic.

```python
from science_tool.annotation.source_text import Passage, SourcePassages, write_source_md
from science_tool.annotation.statement_extract import (
    ExtractReport,
    check_source_changed,
    extract_statements,
)


def _make_source_md(tmp_path: Path) -> Path:
    abstract = SourcePassages(
        passages=(
            Passage(section="title", bioc_offset=0, text="A study of BRCA1."),
            Passage(
                section="abstract", bioc_offset=18,
                text="BRCA1 loss drives genomic instability in tumors.",
            ),
        ),
        release="2024",
    )
    return write_source_md(
        directory=tmp_path, citekey="Brca2024", abstract=abstract, fulltext=None,
        retrieved_from="https://example.org", license_="unknown", licensed=False,
        pmid="1", doi=None,
    )


def _cands(*objs) -> list[Candidate]:
    return [Candidate(**o) for o in objs]  # type: ignore[arg-type]


def test_extract_end_to_end_writes_and_records_hash(tmp_path: Path):
    src = _make_source_md(tmp_path)
    cands = _cands(dict(
        type="proposition", exact="BRCA1 loss drives genomic instability",
        prefix="", suffix=" in tumors", stance="asserted",
    ))
    report = extract_statements(
        source_md=src, model=_MODEL, candidates=cands, now=_NOW, actor="paper-annotate",
    )
    assert isinstance(report, ExtractReport)
    assert report.written == 1 and report.skipped == {}
    assert report.source_text_hash_recorded is True
    # sidecar persisted with the statement + the ledger hash
    sidecar = read_sidecar(src.with_name("Brca2024.source.anno.trig"))
    assert any(a.annotation_type == "proposition" for a in sidecar.annotations)
    led = next(l for l in sidecar.ledgers
               if l.source == "llm-annot:claude-sonnet-4-6:paper-annotate-v1")
    assert led.source_text_hash is not None
    # and now --check reports unchanged
    assert check_source_changed(source_md=src, model=_MODEL) is False


def test_extract_identical_rerun_is_idempotent(tmp_path: Path):
    src = _make_source_md(tmp_path)
    cands = _cands(dict(
        type="proposition", exact="BRCA1 loss drives genomic instability",
        prefix="", suffix=" in tumors", stance="asserted",
    ))
    extract_statements(source_md=src, model=_MODEL, candidates=cands, now=_NOW, actor="a")
    again = extract_statements(
        source_md=src, model=_MODEL, candidates=cands, now=_NOW, actor="a",
    )
    assert again.written == 0  # all-duplicate
    assert again.source_text_hash_recorded is True  # valid no-op still records


def test_extract_empty_candidates_records_hash(tmp_path: Path):
    src = _make_source_md(tmp_path)
    report = extract_statements(
        source_md=src, model=_MODEL, candidates=[], now=_NOW, actor="a",
    )
    assert report.written == 0
    assert report.source_text_hash_recorded is True  # valid no-op
    assert check_source_changed(source_md=src, model=_MODEL) is False


def test_extract_all_unanchored_does_not_record_hash(tmp_path: Path):
    src = _make_source_md(tmp_path)
    cands = _cands(dict(
        type="proposition", exact="text that is absent from the document",
        prefix="", suffix="", stance="asserted",
    ))
    report = extract_statements(
        source_md=src, model=_MODEL, candidates=cands, now=_NOW, actor="a",
    )
    assert report.written == 0
    assert report.skipped == {"extract-quote-not-found": 1}
    assert report.source_text_hash_recorded is False  # failed no-op
    assert check_source_changed(source_md=src, model=_MODEL) is True  # re-run allowed


def test_extract_partial_anchor_failure_does_not_record_hash(tmp_path: Path):
    # one candidate anchors, one does not → the document is NOT fully processed.
    src = _make_source_md(tmp_path)
    cands = _cands(
        dict(type="proposition", exact="BRCA1 loss drives genomic instability",
             prefix="", suffix=" in tumors", stance="asserted"),
        dict(type="hypothesis", exact="a clause that is absent from the document",
             prefix="", suffix="", stance="hypothesized"),
    )
    report = extract_statements(
        source_md=src, model=_MODEL, candidates=cands, now=_NOW, actor="a",
    )
    assert report.written == 1  # the good one persisted
    assert report.skipped == {"extract-quote-not-found": 1}
    assert report.source_text_hash_recorded is False  # defective set → re-run allowed
    assert check_source_changed(source_md=src, model=_MODEL) is True


def test_check_changed_when_no_sidecar(tmp_path: Path):
    src = _make_source_md(tmp_path)
    assert check_source_changed(source_md=src, model=_MODEL) is True


def test_extract_reports_grounding_dropped(tmp_path: Path):
    src = _make_source_md(tmp_path)
    cands = _cands(dict(
        type="proposition", exact="BRCA1 loss drives genomic instability",
        prefix="", suffix=" in tumors", stance="asserted",
        subject_concept="https://identifiers.org/ncbigene:999",  # not a persisted entity
    ))
    report = extract_statements(
        source_md=src, model=_MODEL, candidates=cands, now=_NOW, actor="a",
    )
    assert report.written == 1 and report.grounding_dropped == 1
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run --frozen pytest tests/test_statement_extract.py -k "extract_ or check_changed" -v`
Expected: FAIL — `ImportError` for `extract_statements`/`check_source_changed`/`ExtractReport`.

- [ ] **Step 3: Implement** — append to `statement_extract.py`:

```python
# --- Orchestrator -------------------------------------------------------------


@dataclass(frozen=True)
class ExtractReport:
    written: int
    skipped: dict[str, int]
    grounding_dropped: int
    source_text_hash_recorded: bool
    note: str | None = None


def _read_text_sha256(source_md: Path) -> str:
    fm = raw_frontmatter(source_md)
    value = fm.get("text_sha256")
    if not isinstance(value, str) or not value:
        raise SourceTextError(
            f"{source_md} has no `text_sha256` frontmatter; re-run `persist-source`."
        )
    return value


def extract_statements(
    *,
    source_md: Path,
    model: str,
    candidates: list[Candidate],
    now: datetime,
    actor: str,
) -> ExtractReport:
    """Anchor + persist statement candidates into `<citekey>.source.anno.trig`.

    Document idempotency: the source_text_hash is advanced only when the document was
    FULLY processed (no candidate hit an anchoring failure) — incl. empty / all-duplicate
    runs — but NOT when any candidate failed to anchor (a defective set worth re-running,
    even if other candidates persisted).
    """
    if not source_md.is_file():
        raise SourceTextError(f"{source_md} not found.")
    file_text, persisted = load_persisted_passages(source_md)

    sidecar_path = sidecar_for_markdown(source_md)
    sidecar = read_sidecar(sidecar_path) if sidecar_path.exists() else Sidecar()
    active = active_entity_iris(sidecar)

    skipped: Counter[str] = Counter()
    grounding_dropped = 0
    planned: list[PlannedAnnotation] = []
    for cand in candidates:
        p, reason, dropped = plan_statement(
            file_text, persisted, cand,
            active_iris=active, model=model, source_md_name=source_md.name,
        )
        grounding_dropped += dropped
        if p is not None:
            planned.append(p)
        elif reason is not None:
            skipped[reason] += 1

    new_sidecar, written = merge_planned(sidecar, planned, actor=actor, now=now)

    # Valid no-op vs failed no-op: advance the hash only when the document was FULLY
    # processed — i.e. NO candidate hit an anchoring failure. Every skip reason
    # (quote-not-found / ambiguous / anchored-outside-passage) is a locatability defect,
    # so `not skipped` means every candidate either persisted or cleanly deduped. A
    # partial run (some anchored, some failed) does NOT advance: re-running is idempotent
    # (written rows dedupe) and gives the failed candidates another shot. Empty and
    # all-duplicate runs have no skips, so they advance.
    advance = not skipped
    hash_recorded = False
    if advance:
        text_sha = _read_text_sha256(source_md)
        source_name = _llm_annot_source_name(model)
        new_sidecar, ledger = find_or_create_ledger(new_sidecar, source_name, now=now)
        updated = ledger_set_source_text_hash(ledger, text_sha, now=now)
        new_sidecar = replace(
            new_sidecar,
            ledgers=tuple(
                updated if led.id == updated.id else led
                for led in new_sidecar.ledgers
            ),
        )
        hash_recorded = True

    if written or new_sidecar != sidecar:
        atomic_write_text(sidecar_path, serialize_sidecar(new_sidecar))

    return ExtractReport(
        written=len(written),
        skipped=dict(skipped),
        grounding_dropped=grounding_dropped,
        source_text_hash_recorded=hash_recorded,
        note=None,
    )


def check_source_changed(*, source_md: Path, model: str) -> bool:
    """True if the agent should run: the `.source.md` text differs from the last
    value processed for this source (or no sidecar/ledger exists yet)."""
    current = _read_text_sha256(source_md)
    sidecar_path = sidecar_for_markdown(source_md)
    if not sidecar_path.exists():
        return True
    sidecar = read_sidecar(sidecar_path)
    source_name = _llm_annot_source_name(model)
    for led in sidecar.ledgers:
        if led.source == source_name:
            return led.source_text_hash != current
    return True
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run --frozen pytest tests/test_statement_extract.py -v`
Expected: PASS (entire file).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/annotation/statement_extract.py science/tests/test_statement_extract.py
git commit -m "feat(statement-extract): extract_statements orchestrator + check guard"
```

---

## Task 8: CLI — `annotate extract` command + extend `annotate list` JSON

**Files:**
- Modify: `science/src/science_tool/annotation/cli.py` (`_emit_list_json`; new `extract_cmd`)
- Test: `science/tests/test_annotate_extract_cli.py`

- [ ] **Step 1: Write the failing test**

Create `science/tests/test_annotate_extract_cli.py`:

```python
import json
from datetime import datetime, timezone
from pathlib import Path

from click.testing import CliRunner

from science_tool.annotation.cli import annotate_group
from science_tool.annotation.io import read_sidecar
from science_tool.annotation.source_text import Passage, SourcePassages, write_source_md

_MODEL = "claude-sonnet-4-6"


def _make_source_md(tmp_path: Path) -> Path:
    abstract = SourcePassages(
        passages=(
            Passage(section="title", bioc_offset=0, text="A study of BRCA1."),
            Passage(section="abstract", bioc_offset=18,
                    text="BRCA1 loss drives genomic instability in tumors."),
        ),
        release="2024",
    )
    return write_source_md(
        directory=tmp_path, citekey="Brca2024", abstract=abstract, fulltext=None,
        retrieved_from="https://example.org", license_="unknown", licensed=False,
        pmid="1", doi=None,
    )


def test_extract_cli_check_then_seed_round_trip(tmp_path: Path):
    src = _make_source_md(tmp_path)
    runner = CliRunner()

    # --check on a fresh paper → changed
    r = runner.invoke(annotate_group, [
        "extract", "--source-md", str(src), "--model", _MODEL, "--check",
    ])
    assert r.exit_code == 0, r.output
    assert json.loads(r.output)["status"] == "changed"

    # write candidates + run extract
    cand_file = tmp_path / "candidates.json"
    cand_file.write_text(json.dumps({"candidates": [{
        "type": "proposition",
        "exact": "BRCA1 loss drives genomic instability",
        "prefix": "", "suffix": " in tumors", "stance": "asserted",
    }]}), encoding="utf-8")
    r = runner.invoke(annotate_group, [
        "extract", "--source-md", str(src), "--model", _MODEL,
        "--input", str(cand_file), "--format", "json",
    ])
    assert r.exit_code == 0, r.output
    out = json.loads(r.output)
    assert out["written"] == 1

    sidecar = read_sidecar(src.with_name("Brca2024.source.anno.trig"))
    assert any(a.annotation_type == "proposition" for a in sidecar.annotations)

    # --check now → unchanged
    r = runner.invoke(annotate_group, [
        "extract", "--source-md", str(src), "--model", _MODEL, "--check",
    ])
    assert json.loads(r.output)["status"] == "unchanged"


def test_extract_cli_malformed_input_fails_loud(tmp_path: Path):
    src = _make_source_md(tmp_path)
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"candidates": [{"type": "metaphor", "exact": "x",
                   "prefix": "", "suffix": "", "stance": "asserted"}]}),
                   encoding="utf-8")
    r = CliRunner().invoke(annotate_group, [
        "extract", "--source-md", str(src), "--model", _MODEL, "--input", str(bad),
    ])
    assert r.exit_code != 0
    # nothing written: no sidecar created
    assert not src.with_name("Brca2024.source.anno.trig").exists()


def test_list_json_exposes_bodies_and_full_selector(tmp_path: Path):
    # Seed one statement, then `annotate list --format json` must carry bodies+selector.
    src = _make_source_md(tmp_path)
    cand_file = tmp_path / "c.json"
    cand_file.write_text(json.dumps({"candidates": [{
        "type": "proposition",
        "exact": "BRCA1 loss drives genomic instability",
        "prefix": "", "suffix": " in tumors", "stance": "asserted",
    }]}), encoding="utf-8")
    runner = CliRunner()
    runner.invoke(annotate_group, ["extract", "--source-md", str(src),
                  "--model", _MODEL, "--input", str(cand_file)])

    r = runner.invoke(annotate_group, ["list", "--root", str(tmp_path),
                      "--format", "json"])
    assert r.exit_code == 0, r.output
    item = json.loads(r.output)["annotations"][0]
    # backward-compatible keys still present
    assert "exact_preview" in item and "annotation_type" in item
    # new additive keys
    assert "bodies" in item and isinstance(item["bodies"], list)
    assert item["bodies"][0]["type"] == "textual"
    assert "selector" in item
    assert item["selector"]["exact"] == "BRCA1 loss drives genomic instability"
    assert "prefix" in item["selector"] and "suffix" in item["selector"]
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run --frozen pytest tests/test_annotate_extract_cli.py -v`
Expected: FAIL — `extract` is not a command (`No such command 'extract'`), and `bodies`/`selector` KeyError on list JSON.

- [ ] **Step 3a: Extend `_emit_list_json`** in `cli.py` (replace the item dict construction):

```python
def _emit_list_json(
    rows: list[tuple[Path, Annotation]],
    root: Path,
    sidecar_count: int,
) -> None:
    items = []
    for sidecar_path, ann in rows:
        sel = ann.target.selector
        items.append({
            "id": ann.id,
            "qualified_id":
                f"{query.entity_relpath_for_sidecar(sidecar_path, root)}:{ann.id}",
            "status": ann.status.value,
            "source": ann.source,
            "annotation_type": ann.annotation_type,
            "exact_preview": ann.target.selector.exact[:60],
            "selector": {
                "exact": sel.exact,
                "prefix": sel.prefix,
                "suffix": sel.suffix,
            },
            "bodies": [_body_json(b) for b in ann.bodies],
        })
    click.echo(json.dumps({
        "summary": {
            "total_annotations": len(rows),
            "total_sidecars": sidecar_count,
        },
        "annotations": items,
    }, indent=2))


def _body_json(body: Body) -> dict[str, str]:
    """JSON view of a body for grounding consumers (IRI value / textual value)."""
    if isinstance(body, IriBody):
        return {"type": "iri", "value": body.iri}
    return {"type": "textual", "format": body.format, "value": body.value}
```

Ensure `Body` and `IriBody` are imported in `cli.py` (add to the existing `from science_tool.annotation.model import (...)` block if absent):

```python
from science_tool.annotation.model import (
    # ... existing imports ...
    Body,
    IriBody,
)
```

- [ ] **Step 3b: Add the `extract` command** in `cli.py` (place after `pubtator_cmd`, before the module's closing helpers; mirror `pubtator_cmd`'s option style):

```python
@annotate_group.command("extract")
@click.option(
    "--source-md", "source_md", required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Path to the paper's <citekey>.source.md.",
)
@click.option("--model", required=True, help="Exact extracting model id (source identity).")
@click.option(
    "--input", "input_path", default=None,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="candidates.json produced by the paper-annotate agent.",
)
@click.option("--check", "check_only", is_flag=True, default=False,
              help="Read-only: print whether the source changed since last extraction.")
@click.option("--actor", default="paper-annotate",
              help="Identity recorded as the annotation creator.")
@click.option("--format", "fmt", type=click.Choice(("table", "json")), default="table")
def extract_cmd(
    source_md: Path,
    model: str,
    input_path: Path | None,
    check_only: bool,
    actor: str,
    fmt: str,
) -> None:
    """Persist agent-extracted statement candidates as anchored annotations.

    `--check` reports changed/unchanged without writing. Otherwise reads
    `--input candidates.json`, anchors each quote, verifies grounding, and merges
    idempotently into `<citekey>.source.anno.trig`.
    """
    from science_tool.annotation.source_text import SourceTextError
    from science_tool.annotation.statement_extract import (
        CandidateError,
        check_source_changed,
        extract_statements,
        parse_candidates,
    )

    if check_only:
        if input_path is not None:
            raise click.ClickException("--check takes no --input")
        try:
            changed = check_source_changed(source_md=source_md, model=model)
        except SourceTextError as exc:
            raise click.ClickException(str(exc)) from exc
        click.echo(json.dumps({"status": "changed" if changed else "unchanged"}))
        return

    if input_path is None:
        raise click.ClickException("--input <candidates.json> is required (or use --check)")
    try:
        candidates = parse_candidates(input_path.read_text(encoding="utf-8"))
    except CandidateError as exc:
        raise click.ClickException(str(exc)) from exc

    try:
        report = extract_statements(
            source_md=source_md, model=model, candidates=candidates,
            now=datetime.now(timezone.utc), actor=actor,
        )
    except SourceTextError as exc:
        raise click.ClickException(str(exc)) from exc

    if fmt == "json":
        click.echo(json.dumps({
            "written": report.written,
            "skipped": report.skipped,
            "grounding_dropped": report.grounding_dropped,
            "source_text_hash_recorded": report.source_text_hash_recorded,
        }, indent=2))
    else:
        skips = ", ".join(f"{k}:{v}" for k, v in sorted(report.skipped.items())) or "none"
        click.echo(
            f"annotate extract: {report.written} statement(s) written, "
            f"{report.grounding_dropped} grounding field(s) dropped, "
            f"skipped [{skips}], "
            f"hash recorded: {report.source_text_hash_recorded}"
        )
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run --frozen pytest tests/test_annotate_extract_cli.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/annotation/cli.py science/tests/test_annotate_extract_cli.py
git commit -m "feat(annotate-cli): extract command + grounding-rich list JSON"
```

---

## Task 9: Vocabulary docs + `paper-annotate` subagent + `annotate-paper` command

**Files:**
- Modify: `docs/conventions/annotation-tokens.md`
- Create: `agents/paper-annotate.md`
- Create: `commands/annotate-paper.md`
- Test: `science/tests/test_annotate_extract_cli.py` (one structural assertion)

- [ ] **Step 1: Write the failing test** (append to `test_annotate_extract_cli.py`)

```python
def test_paper_annotate_agent_file_has_frontmatter():
    # repo root is three levels up from science/tests/
    repo_root = Path(__file__).resolve().parents[2]
    agent = repo_root / "agents" / "paper-annotate.md"
    assert agent.is_file(), "agents/paper-annotate.md must exist"
    text = agent.read_text(encoding="utf-8")
    assert text.startswith("---")
    assert "name: paper-annotate" in text
    assert "science annotate extract" in text  # documents the deterministic call
    cmd = repo_root / "commands" / "annotate-paper.md"
    assert cmd.is_file(), "commands/annotate-paper.md must exist"
    assert "--check" in cmd.read_text(encoding="utf-8")  # documents the precheck
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run --frozen pytest tests/test_annotate_extract_cli.py -k paper_annotate_agent -v`
Expected: FAIL — files do not exist.

- [ ] **Step 3a: Append to `docs/conventions/annotation-tokens.md`** (a new section):

````markdown
## Statement annotations (paper-annotate Phase 3a)

Agent-extracted sub-article statements. Produced by the `paper-annotate` subagent →
`science annotate extract`.

- **`annotation_type`**: `proposition` | `question` | `hypothesis` (kebab; no `sci:` prefix).
- **Motivation**: `oa:classifying`.
- **Source identity**: `llm-annot:<model>:paper-annotate-v1`, where `<model>` is the exact
  extracting model id (e.g. `claude-sonnet-4-6`). Bump the `paper-annotate-vN` segment when
  the extraction prompt or the statement body schema changes (invalidates `content_hash`
  and the document `sci:sourceTextHash` guard for that source).
- **Body**: a single `TextualBody` with `format = application/json`, serialized with sorted
  keys + compact separators + `allow_nan=False`:

  ```json
  {"section":"results","stance":"asserted","subject":"BRCA1 loss",
   "object":"genomic instability","subject_concept":"https://identifiers.org/ncbigene:672"}
  ```

  - `section` (required, CLI-derived): one of
    `title · abstract · introduction · methods · results · discussion · conclusion · figure · table · other`.
  - `stance` (required): `asserted · negated · hypothesized · open`.
  - `subject` / `object` (optional): short phrases.
  - `subject_concept` / `object_concept` (optional): concept IRIs, kept ONLY when they match an
    active (`open`/`ack`) `entity-*` annotation in the same paper; otherwise dropped (counted as
    `grounding_dropped`), the statement still persisted.

- **Document guard**: `sci:sourceTextHash` on the per-source `sci:AuditLedger` records the last
  `.source.md` `text_sha256` processed for this source; `extract --check` skips re-running the
  agent when unchanged. Advanced for any validly-processed document (incl. empty / all-duplicate)
  but not when a non-empty candidate set anchored nothing.

`metaphor` / `analogy` statement types are Phase 3b (additive), not registered here yet.
````

- [ ] **Step 3b: Create `agents/paper-annotate.md`:**

```markdown
---
name: paper-annotate
description: Extract proposition/question/hypothesis statements from one paper's persisted .source.md, grounded in its existing PubTator entity annotations, and persist them via `science annotate extract`. Requires an existing <citekey>.source.md (run `science paper persist-source` first). Returns the written/skipped counts.
model: claude-sonnet-4-6
tools: Read, Bash
---

# Paper Annotate

You are a dispatched subagent. Your sole job is to extract sub-article **statements**
(propositions, questions, hypotheses) from ONE paper and hand them to the deterministic
`science annotate extract` command. You do not summarize, you do not edit the sidecar, you
do not touch the `.source.md`.

## Inputs you are given

- `--source-md <path>`: the paper's `<citekey>.source.md` (already persisted).
- `--model <id>`: the model id to record as the source identity (your own model).

## Workflow

1. **Read existing grounding annotations** (active set only):

   ```bash
   uv run science annotate list --root <paper-dir> --status open --status ack --format json
   ```

   Each item carries `annotation_type`, `bodies` (for `entity-*` rows, an `iri` body = the
   concept IRI), and `selector` (`exact`/`prefix`/`suffix` = where the entity sits). Use these
   to ground statement subjects/objects: when a statement is about an entity that appears here,
   reuse that exact concept IRI.

2. **Read the source text**: `Read` the `.source.md`. Statements must be quoted verbatim from
   the passage bodies (the text under `## Abstract` / `## Full Text`), never from headings or
   frontmatter.

3. **Extract statements.** For each proposition/question/hypothesis the authors actually state:
   - `type`: `proposition` (a claim), `question` (an open question the paper poses), or
     `hypothesis` (a proposed-but-not-established mechanism).
   - `exact`: the verbatim span (one sentence or clause).
   - `prefix` / `suffix`: the text IMMEDIATELY before / after `exact` (a few words is enough;
     include more only to disambiguate a repeated quote). Empty string is allowed.
   - `stance`: `asserted` (affirmed), `negated` (explicitly denied), `hypothesized` (proposed),
     `open` (for a question).
   - `subject` / `object` (optional): short phrases naming what the statement relates.
   - `subject_concept` / `object_concept` (optional): a concept IRI from step 1, ONLY when the
     subject/object clearly IS that annotated entity. Do not invent IRIs — an unrecognized IRI
     is dropped by the CLI.

4. **Write `candidates.json`** to a temp path: `{"candidates": [ ... ]}` (max 500 candidates).

5. **Persist deterministically:**

   ```bash
   uv run science annotate extract --source-md <path> --model <id> --input candidates.json --format json
   ```

   Read the JSON report (`written`, `skipped`, `grounding_dropped`). If `skipped` shows
   `extract-quote-not-found` / `extract-quote-ambiguous`, your `exact`/`prefix`/`suffix` did not
   match the document — fix those candidates and re-run; do not fabricate spans.

## Scope discipline

- ONE paper. Statements only (no metaphors/analogies — that is a later phase).
- Quote verbatim; never paraphrase into `exact`. A mis-anchored quote is a failure.
- Do not commit. Report counts back to the orchestrator.

## Reporting back

Return ≤120 words: the `written` / `skipped` / `grounding_dropped` counts, and any candidates
you could not anchor (with why). Do not paste the full candidate list.
```

- [ ] **Step 3c: Create `commands/annotate-paper.md`:**

```markdown
# /annotate-paper

Extract sub-article **statements** (propositions/questions/hypotheses) from a paper that already
has a persisted `.source.md` and PubTator annotations, via the `paper-annotate` subagent.

## Usage

`/annotate-paper <pmid|doi|citekey>` — optionally `--force` to re-run even if unchanged.

## Workflow

1. **Resolve the paper** to its `<citekey>.source.md` path and directory. If no `.source.md`
   exists, stop and tell the user to run `science paper persist-source <id>` first (this command
   does not auto-persist).

2. **Precheck the document guard** (skip burning the model on unchanged text):

   ```bash
   uv run science annotate extract --source-md <path> --model <model-id> --check
   ```

   If it prints `{"status":"unchanged"}` and `--force` was not given, stop: report "already
   extracted, source unchanged." Otherwise continue.

3. **Dispatch the `paper-annotate` subagent** with `--source-md <path>` and `--model <model-id>`.
   The subagent reads existing annotations + the source text, emits `candidates.json`, and runs
   `science annotate extract`.

4. **Surface the report** the subagent returns (written / skipped / grounding_dropped). For bulk
   runs, dispatch one subagent per paper (they are independent; the deterministic command
   serializes its own writes per sidecar).

## Notes

- The `paper-annotate-v1` source version means a prompt/schema change later (a `v2` bump) will
  correctly re-run all papers; the `--check` guard is keyed per source version.
- Promotion of statements into epistemic entities is a separate, later step — this command only
  writes raw evidence annotations.
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run --frozen pytest tests/test_annotate_extract_cli.py -k paper_annotate_agent -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add docs/conventions/annotation-tokens.md agents/paper-annotate.md commands/annotate-paper.md science/tests/test_annotate_extract_cli.py
git commit -m "doc(paper-annotate): statement vocab + paper-annotate subagent + annotate-paper command"
```

---

## Final verification (after all tasks)

- [ ] **Full module + CLI suite green:**

Run (from `science/`):
```bash
uv run --frozen pytest tests/test_statement_extract.py tests/test_annotate_extract_cli.py -v
```
Expected: all PASS.

- [ ] **No regressions in the annotation system:**

```bash
uv run --frozen pytest tests/ -k "annotation or pubtator or sidecar or annotate or ledger" -q
```
Expected: all PASS (existing seeder/io/ledger tests unaffected by the additive `source_text_hash` field and the additive list-JSON keys).

- [ ] **Types + lint:**

```bash
uv run --frozen pyright src/science_tool/annotation/statement_extract.py src/science_tool/annotation/cli.py src/science_tool/annotation/io.py src/science_tool/annotation/model.py src/science_tool/annotation/ledger.py
uv run --frozen ruff check src/science_tool/annotation/
```
Expected: clean. (`reportMissingImports` for `science_tool.*` under a bare editor is a known artifact; it resolves under `uv run --frozen pyright`.)

- [ ] Then proceed to **superpowers:finishing-a-development-branch**.

---

## Notes for the implementer

- **Run everything from the `science/` directory** with `uv run --frozen` (uv workspace; Python 3.11/3.13 venvs).
- **`_CONTEXT`, `PersistedPassage`, `load_persisted_passages` are imported from `pubtator_seed`** — do not re-implement them. (Importing the underscore-prefixed `_CONTEXT` across these two sibling producer modules is intentional shared infra, not a new public API.)
- **`merge_planned` requires a single `source_name` per call** — all statement rows share `llm-annot:<model>:paper-annotate-v1`, so this holds. Never mix sources in one call.
- **The ledger update is separate from `merge_planned`** (which only touches annotations). Find-or-create the ledger, set `source_text_hash`, then write the sidecar — exactly as Task 7 shows.
- **`pytest`'s summary line may not reach piped logs in this project** — rely on exit code 0 + `[100%]` + zero `FAILED`/`ERROR` markers as the gate.
- **Do not push.** This branch stays local (science work convention).

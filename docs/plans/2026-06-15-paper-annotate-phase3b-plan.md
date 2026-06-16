# Paper-Annotate Phase 3b Implementation Plan — Figurative Annotation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the existing `paper-annotate` agent + `science annotate extract` command to also
extract **metaphor** and **analogy** spans, persisting them with a figurative body schema —
purely additive over Phase 3a.

**Architecture:** One mixed `candidates.json` whose `type` discriminates statement vs figurative
candidates. The `extract` command dispatches only candidate *parsing* and *body generation* by
kind; anchoring, section derivation, dedup, the document idempotency guard, and the
`paper-annotate-v1` source identity are reused unchanged. No grounding for figurative; no version
bump (Phase 3a has processed zero papers — verified).

**Tech Stack:** Python 3.12, `click`, `rdflib`, `uv` workspace. Run all commands from the
`science/` subdir: `uv run --frozen pytest|pyright|ruff`.

**Reference design:** `docs/plans/2026-06-15-paper-annotate-phase3b-design.md`.

**Module under change:** `science/src/science_tool/annotation/statement_extract.py` (read it once
before Task 1 — every task edits it).

---

### Task 1: Rename `Candidate` → `StatementCandidate`, `extract_statements` → `extract_candidates`

Pure mechanical rename so the two candidate kinds read honestly. **No behavior change.** `metaphor`
is still an invalid type after this task.

**Files:**
- Modify: `science/src/science_tool/annotation/statement_extract.py`
- Modify: `science/src/science_tool/annotation/cli.py` (import + call site only)
- Test: `science/tests/test_statement_extract.py`

**Rename ONLY these exact tokens** (do NOT touch `CandidateError`, `parse_candidates`, the
`candidates` variable/param, or `_parse_one`):

- `class Candidate:` → `class StatementCandidate:`
- every constructor call `Candidate(` → `StatementCandidate(`
- every type annotation `Candidate` → `StatementCandidate` (in `_parse_one`'s `-> Candidate` return,
  `parse_candidates`'s `-> list[Candidate]`, `plan_statement`'s `candidate: Candidate`)
- `def extract_statements(` → `def extract_candidates(`
- in `cli.py`: the import `extract_statements` → `extract_candidates` and the call
  `report = extract_statements(` → `report = extract_candidates(`
- in `test_statement_extract.py`: the imports of `Candidate` and `extract_statements`, and the
  helpers `_cand(...) -> Candidate` / `_cands` (uses `Candidate(**o)`) and the `extract_statements(`
  call sites and the `isinstance(c, Candidate)` assertion.

- [ ] **Step 1: Apply the rename**

In `statement_extract.py`, update the dataclass + all references:

```python
@dataclass(frozen=True)
class StatementCandidate:
    type: str
    exact: str
    prefix: str
    suffix: str
    stance: str
    subject: str | None = None
    object: str | None = None
    subject_concept: str | None = None
    object_concept: str | None = None
```

`parse_candidates` return type → `list[StatementCandidate]`; `_parse_one(...) -> StatementCandidate`
and its `return Candidate(` → `return StatementCandidate(`; `plan_statement(..., candidate: StatementCandidate, ...)`;
`def extract_statements(` → `def extract_candidates(`.

In `cli.py` `extract_cmd`:

```python
    from science_tool.annotation.statement_extract import (
        CandidateError,
        check_source_changed,
        extract_candidates,
        parse_candidates,
    )
```
and `report = extract_candidates(` at the call site.

In `test_statement_extract.py`: change the two import blocks
(`from science_tool.annotation.statement_extract import (Candidate, ...)` →
`StatementCandidate`; `import (... extract_statements ...)` → `extract_candidates`), the
`isinstance(c, Candidate)` → `isinstance(c, StatementCandidate)`, the `_cand` / `_cands` helper
return-types + `Candidate(**...)` constructors → `StatementCandidate`, and **all**
`extract_statements(` call sites in the orchestrator tests → `extract_candidates(` (there are
several — replace every one).

- [ ] **Step 2: Verify no stale references remain, then run the full annotation suite**

First confirm the old names are fully gone from the three touched files (the only allowed `Candidate`
hits are `CandidateError`):

```bash
rg -n "extract_statements" science/src/science_tool/annotation/ science/tests/test_statement_extract.py
rg -n "\bCandidate\b" science/src/science_tool/annotation/statement_extract.py science/tests/test_statement_extract.py | rg -v "StatementCandidate|CandidateError"
```
Expected: **no output** from either command.

Run: `uv run --frozen pytest tests/test_statement_extract.py tests/test_annotate_extract_cli.py -q`
Expected: PASS (same count as before — this is a rename only).

- [ ] **Step 3: Typecheck + lint the two touched source files**

Run: `uv run --frozen pyright src/science_tool/annotation/statement_extract.py src/science_tool/annotation/cli.py`
Run: `uv run --frozen ruff check src/science_tool/annotation/statement_extract.py src/science_tool/annotation/cli.py`
Expected: clean (ignore any pre-existing `reportMissingImports` editor-artifact lines for
`science_tool.*` / `rdflib` — they resolve under `uv run`).

- [ ] **Step 4: Commit**

```bash
git add science/src/science_tool/annotation/statement_extract.py \
        science/src/science_tool/annotation/cli.py \
        science/tests/test_statement_extract.py
git commit -m "refactor(paper-annotate): rename Candidate->StatementCandidate, extract_statements->extract_candidates"
```

---

### Task 2: `FigurativeCandidate` + discriminated `parse_candidates`

Add the figurative candidate kind and dispatch parsing on `type`. Lift the shared string-field
helpers to module level so both parsers reuse them.

**Files:**
- Modify: `science/src/science_tool/annotation/statement_extract.py`
- Test: `science/tests/test_statement_extract.py`

- [ ] **Step 1: Write failing parse tests**

Append to `test_statement_extract.py` (the `parse_candidates` / `StatementCandidate` imports already
exist near the top; add `FigurativeCandidate` to that import block):

```python
from science_tool.annotation.statement_extract import FigurativeCandidate


def _fig(**over):
    base = {
        "type": "metaphor", "exact": "the immune system mounts an attack",
        "prefix": "", "suffix": " on pathogens.",
        "source_domain": "warfare", "target_domain": "immune response",
    }
    base.update(over)
    return json.dumps({"candidates": [base]})


def test_parse_figurative_minimal_valid():
    [c] = parse_candidates(_fig())
    assert isinstance(c, FigurativeCandidate)
    assert c.type == "metaphor"
    assert c.source_domain == "warfare" and c.target_domain == "immune response"
    assert c.mapping is None and c.cue is None


def test_parse_analogy_with_optionals():
    [c] = parse_candidates(_fig(type="analogy", mapping="cells as soldiers", cue="like"))
    assert isinstance(c, FigurativeCandidate)
    assert c.type == "analogy" and c.mapping == "cells as soldiers" and c.cue == "like"


def test_parse_mixed_statement_and_figurative():
    raw = json.dumps({"candidates": [
        {"type": "proposition", "exact": "X drives Y", "prefix": "", "suffix": ".",
         "stance": "asserted"},
        {"type": "metaphor", "exact": "a cellular factory", "prefix": "", "suffix": ".",
         "source_domain": "manufacturing", "target_domain": "the cell"},
    ]})
    cands = parse_candidates(raw)
    assert isinstance(cands[0], StatementCandidate)
    assert isinstance(cands[1], FigurativeCandidate)


def test_parse_figurative_missing_domain_fails():
    bad = json.dumps({"candidates": [{
        "type": "metaphor", "exact": "x", "prefix": "", "suffix": "",
        "source_domain": "warfare",  # target_domain missing
    }]})
    with pytest.raises(CandidateError, match="missing required"):
        parse_candidates(bad)


def test_parse_figurative_blank_required_domain_fails():
    with pytest.raises(CandidateError, match="non-empty"):
        parse_candidates(_fig(target_domain="   "))


def test_parse_figurative_blank_optional_fails():
    with pytest.raises(CandidateError, match="non-empty"):
        parse_candidates(_fig(mapping="   "))


def test_parse_figurative_rejects_statement_field():
    # `stance` is a statement-only field -> unknown for figurative
    with pytest.raises(CandidateError, match="unknown fields"):
        parse_candidates(_fig(stance="asserted"))


def test_parse_statement_rejects_figurative_field():
    # `source_domain` is figurative-only -> unknown for a statement
    with pytest.raises(CandidateError, match="unknown fields"):
        parse_candidates(_one(source_domain="warfare"))


def test_parse_figurative_over_length_field():
    with pytest.raises(CandidateError, match="exceeds"):
        parse_candidates(_fig(source_domain="z" * (MAX_FIELD_CHARS + 1)))
```

Also **update the two existing tests** that used `metaphor` as a negative example (it is now a
valid type):

```python
def test_parse_rejects_unknown_type():
    with pytest.raises(CandidateError, match="type"):
        parse_candidates(_one(type="banana"))   # was type="metaphor"
```

- [ ] **Step 2: Run to verify the new tests fail**

Run: `uv run --frozen pytest tests/test_statement_extract.py -q -k "figurative or mixed or unknown_type"`
Expected: FAIL (`ImportError: FigurativeCandidate` / assertion failures).

- [ ] **Step 3: Implement the discriminated parser**

In `statement_extract.py`, replace the constants + `_parse_one` region. First the constants
(rename the statement key-sets and add figurative type/key-sets):

```python
STATEMENT_TYPES: frozenset[str] = frozenset({"proposition", "question", "hypothesis"})
FIGURATIVE_TYPES: frozenset[str] = frozenset({"metaphor", "analogy"})
STANCES: frozenset[str] = frozenset({"asserted", "negated", "hypothesized", "open"})
MAX_CANDIDATES = 500
MAX_FIELD_CHARS = 2000

_STATEMENT_ALLOWED_KEYS = frozenset({
    "type", "exact", "prefix", "suffix", "stance",
    "subject", "object", "subject_concept", "object_concept",
})
_STATEMENT_REQUIRED_KEYS = frozenset({"type", "exact", "prefix", "suffix", "stance"})

_FIGURATIVE_ALLOWED_KEYS = frozenset({
    "type", "exact", "prefix", "suffix",
    "source_domain", "target_domain", "mapping", "cue",
})
_FIGURATIVE_REQUIRED_KEYS = frozenset({
    "type", "exact", "prefix", "suffix", "source_domain", "target_domain",
})
```

Add the new dataclass next to `StatementCandidate`:

```python
@dataclass(frozen=True)
class FigurativeCandidate:
    type: str
    exact: str
    prefix: str
    suffix: str
    source_domain: str
    target_domain: str
    mapping: str | None = None
    cue: str | None = None
```

Lift the shared field helpers to module level (these preserve the exact 3a error strings) and add
the non-blank variants:

```python
def _field_len_ok(idx: int, name: str, val: str) -> str:
    if len(val) > MAX_FIELD_CHARS:
        raise CandidateError(f"candidate[{idx}].{name} exceeds {MAX_FIELD_CHARS} chars")
    return val


def _req_str(item: dict[str, Any], idx: int, name: str) -> str:
    val = item[name]
    if not isinstance(val, str):
        raise CandidateError(f"candidate[{idx}].{name} must be a string")
    return _field_len_ok(idx, name, val)


def _opt_str(item: dict[str, Any], idx: int, name: str) -> str | None:
    if name not in item or item[name] is None:
        return None
    val = item[name]
    if not isinstance(val, str):
        raise CandidateError(f"candidate[{idx}].{name} must be a string or null")
    return _field_len_ok(idx, name, val)


def _req_nonblank(item: dict[str, Any], idx: int, name: str) -> str:
    """A required figurative content field: string, in-bounds, non-empty after trim. Stored trimmed."""
    s = _req_str(item, idx, name).strip()
    if not s:
        raise CandidateError(f"candidate[{idx}].{name} must be non-empty")
    return s


def _opt_nonblank(item: dict[str, Any], idx: int, name: str) -> str | None:
    """An optional figurative content field: omit, or string non-empty after trim. Stored trimmed.

    A present-but-blank optional is a defect (a low-value placeholder), not 'absent' — fail loud.
    """
    if name not in item or item[name] is None:
        return None
    s = _req_str(item, idx, name).strip()
    if not s:
        raise CandidateError(f"candidate[{idx}].{name} must be non-empty when present (omit it instead)")
    return s
```

Replace `_parse_one` with a dispatcher + two per-kind parsers:

```python
def _parse_one(item: Any, idx: int) -> StatementCandidate | FigurativeCandidate:
    if not isinstance(item, dict):
        raise CandidateError(f"candidate[{idx}] must be a JSON object")
    ctype = item.get("type")
    if not isinstance(ctype, str):
        raise CandidateError(f"candidate[{idx}].type must be a string")
    if ctype in STATEMENT_TYPES:
        return _parse_statement(item, idx)
    if ctype in FIGURATIVE_TYPES:
        return _parse_figurative(item, idx)
    raise CandidateError(
        f"candidate[{idx}].type {ctype!r} not in "
        f"{sorted(STATEMENT_TYPES | FIGURATIVE_TYPES)}"
    )


def _parse_statement(item: dict[str, Any], idx: int) -> StatementCandidate:
    extra = set(item) - _STATEMENT_ALLOWED_KEYS
    if extra:
        raise CandidateError(f"candidate[{idx}] unknown fields: {sorted(extra)}")
    missing = _STATEMENT_REQUIRED_KEYS - set(item)
    if missing:
        raise CandidateError(f"candidate[{idx}] missing required fields: {sorted(missing)}")
    exact = _req_str(item, idx, "exact")
    if not exact:
        raise CandidateError(f"candidate[{idx}].exact must be non-empty")
    stance = _req_str(item, idx, "stance")
    if stance not in STANCES:
        raise CandidateError(f"candidate[{idx}].stance {stance!r} not in {sorted(STANCES)}")
    return StatementCandidate(
        type=item["type"],
        exact=exact,
        prefix=_req_str(item, idx, "prefix"),
        suffix=_req_str(item, idx, "suffix"),
        stance=stance,
        subject=_opt_str(item, idx, "subject"),
        object=_opt_str(item, idx, "object"),
        subject_concept=_opt_str(item, idx, "subject_concept"),
        object_concept=_opt_str(item, idx, "object_concept"),
    )


def _parse_figurative(item: dict[str, Any], idx: int) -> FigurativeCandidate:
    extra = set(item) - _FIGURATIVE_ALLOWED_KEYS
    if extra:
        raise CandidateError(f"candidate[{idx}] unknown fields: {sorted(extra)}")
    missing = _FIGURATIVE_REQUIRED_KEYS - set(item)
    if missing:
        raise CandidateError(f"candidate[{idx}] missing required fields: {sorted(missing)}")
    exact = _req_str(item, idx, "exact")
    if not exact:
        raise CandidateError(f"candidate[{idx}].exact must be non-empty")
    return FigurativeCandidate(
        type=item["type"],
        exact=exact,
        prefix=_req_str(item, idx, "prefix"),
        suffix=_req_str(item, idx, "suffix"),
        source_domain=_req_nonblank(item, idx, "source_domain"),
        target_domain=_req_nonblank(item, idx, "target_domain"),
        mapping=_opt_nonblank(item, idx, "mapping"),
        cue=_opt_nonblank(item, idx, "cue"),
    )
```

Update `parse_candidates`'s return annotation:

```python
def parse_candidates(raw: str) -> list[StatementCandidate | FigurativeCandidate]:
```

(The body is unchanged: it still does the JSON-object / `candidates`-array / `MAX_CANDIDATES`
checks and `return [_parse_one(item, idx) for idx, item in enumerate(items)]`.) Delete the old
nested `_checked` / `_req` / `_opt` helpers inside the former `_parse_one` — they are now the
module-level `_field_len_ok` / `_req_str` / `_opt_str`.

- [ ] **Step 4: Run the parse tests — green**

Run: `uv run --frozen pytest tests/test_statement_extract.py -q`
Expected: PASS (all prior statement parse tests + the new figurative ones).

- [ ] **Step 5: Typecheck + lint**

Run: `uv run --frozen pyright src/science_tool/annotation/statement_extract.py`
Run: `uv run --frozen ruff check src/science_tool/annotation/statement_extract.py`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/annotation/statement_extract.py science/tests/test_statement_extract.py
git commit -m "feat(paper-annotate): FigurativeCandidate + discriminated parse (metaphor/analogy)"
```

---

### Task 3: `figurative_body_json`

**Files:**
- Modify: `science/src/science_tool/annotation/statement_extract.py`
- Test: `science/tests/test_statement_extract.py`

- [ ] **Step 1: Write failing body tests**

Append to `test_statement_extract.py` (add `figurative_body_json` to the existing
`statement_body_json` import line, or add a new import):

```python
from science_tool.annotation.statement_extract import figurative_body_json


def test_figurative_body_minimal_sorted_compact():
    body = figurative_body_json(
        section="discussion", source_domain="warfare",
        target_domain="immune response", mapping=None, cue=None,
    )
    # keys sorted: section, source_domain, target_domain
    assert body == (
        '{"section":"discussion","source_domain":"warfare",'
        '"target_domain":"immune response"}'
    )


def test_figurative_body_includes_present_optionals_sorted():
    body = figurative_body_json(
        section="results", source_domain="a factory", target_domain="the cell",
        mapping="ribosome as machine", cue="like",
    )
    # keys sorted: cue, mapping, section, source_domain, target_domain
    assert body == (
        '{"cue":"like","mapping":"ribosome as machine","section":"results",'
        '"source_domain":"a factory","target_domain":"the cell"}'
    )


def test_figurative_body_omits_absent_optionals():
    body = figurative_body_json(
        section="results", source_domain="a", target_domain="b",
        mapping=None, cue="like",
    )
    assert '"mapping"' not in body and '"cue":"like"' in body
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run --frozen pytest tests/test_statement_extract.py -q -k figurative_body`
Expected: FAIL (`ImportError: figurative_body_json`).

- [ ] **Step 3: Implement (next to `statement_body_json`)**

```python
def figurative_body_json(
    *,
    section: str,
    source_domain: str,
    target_domain: str,
    mapping: str | None,
    cue: str | None,
) -> str:
    """Build the deterministic JSON for a figurative annotation's TextualBody.

    Always carries section + source_domain + target_domain. Optional mapping/cue are
    included only when present. Sorted keys + compact separators + allow_nan=False give
    finite, byte-stable serialization (clean diffs). No grounding/concept fields.
    """
    obj: dict[str, Any] = {
        "section": section,
        "source_domain": source_domain,
        "target_domain": target_domain,
    }
    if mapping is not None:
        obj["mapping"] = mapping
    if cue is not None:
        obj["cue"] = cue
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False)
```

- [ ] **Step 4: Run — green**

Run: `uv run --frozen pytest tests/test_statement_extract.py -q -k figurative_body`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/annotation/statement_extract.py science/tests/test_statement_extract.py
git commit -m "feat(paper-annotate): figurative_body_json (deterministic figurative body)"
```

---

### Task 4: Shared `_anchor_candidate` helper + `plan_figurative`

Extract the locate-and-anchor step shared by both kinds, refactor `plan_statement` to use it
(**byte-identical behavior**), and add `plan_figurative` with a **delimiter-safe** domain-keyed
`match_text`.

**Files:**
- Modify: `science/src/science_tool/annotation/statement_extract.py`
- Test: `science/tests/test_statement_extract.py`

- [ ] **Step 1: Write failing plan tests**

Append to `test_statement_extract.py` (the `plan_statement`, `PersistedPassage`, model imports
already exist; add `plan_figurative`):

```python
from science_tool.annotation.statement_extract import plan_figurative

_FIG_TEXT = "We describe how the immune system mounts an attack on invading pathogens."
_FIG_PASSAGES = [PersistedPassage(section="DISCUSS", file_char_base=0, length=len(_FIG_TEXT))]


def _figc(**over) -> FigurativeCandidate:
    base = dict(type="metaphor", exact="the immune system mounts an attack",
                prefix="", suffix=" on invading",
                source_domain="warfare", target_domain="immune response")
    base.update(over)
    return FigurativeCandidate(**base)  # type: ignore[arg-type]


def test_plan_figurative_anchors_and_builds_body():
    p, reason, dropped = plan_figurative(
        _FIG_TEXT, _FIG_PASSAGES, _figc(),
        model=_MODEL, source_md_name="P.source.md",
    )
    assert reason is None and dropped == 0 and p is not None
    assert p.annotation_type == "metaphor"
    assert p.motivation is Motivation.CLASSIFYING
    assert p.source_name == "llm-annot:claude-sonnet-4-6:paper-annotate-v1"
    assert '"section":"discussion"' in p.body.value
    assert '"source_domain":"warfare"' in p.body.value


def test_plan_figurative_quote_not_found():
    p, reason, _ = plan_figurative(
        _FIG_TEXT, _FIG_PASSAGES, _figc(exact="absent text"),
        model=_MODEL, source_md_name="P.source.md",
    )
    assert p is None and reason == "extract-quote-not-found"


def test_plan_figurative_same_span_different_domains_are_distinct():
    # identical span, different required domains -> different match_text (must not collapse)
    p1, _, _ = plan_figurative(
        _FIG_TEXT, _FIG_PASSAGES, _figc(source_domain="warfare", target_domain="immune response"),
        model=_MODEL, source_md_name="P.source.md",
    )
    p2, _, _ = plan_figurative(
        _FIG_TEXT, _FIG_PASSAGES, _figc(source_domain="machinery", target_domain="immune response"),
        model=_MODEL, source_md_name="P.source.md",
    )
    assert p1 is not None and p2 is not None
    assert p1.match_text != p2.match_text


def test_plan_figurative_match_text_is_delimiter_safe():
    # a literal '|' inside a domain must not let two different pairs collide
    p1, _, _ = plan_figurative(
        _FIG_TEXT, _FIG_PASSAGES, _figc(source_domain="a|b", target_domain="c"),
        model=_MODEL, source_md_name="P.source.md",
    )
    p2, _, _ = plan_figurative(
        _FIG_TEXT, _FIG_PASSAGES, _figc(source_domain="a", target_domain="b|c"),
        model=_MODEL, source_md_name="P.source.md",
    )
    assert p1 is not None and p2 is not None
    assert p1.match_text != p2.match_text


def test_plan_figurative_match_text_prefix_shape():
    p, _, _ = plan_figurative(
        _FIG_TEXT, _FIG_PASSAGES, _figc(),
        model=_MODEL, source_md_name="P.source.md",
    )
    assert p is not None
    file_idx = _FIG_TEXT.index("the immune system mounts an attack")
    assert p.match_text.startswith(f"metaphor|{file_idx}:34|")
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run --frozen pytest tests/test_statement_extract.py -q -k plan_figurative`
Expected: FAIL (`ImportError: plan_figurative`).

- [ ] **Step 3: Add `_anchor_candidate`; refactor `plan_statement`; add `plan_figurative`**

Insert the shared helper above `plan_statement`:

```python
def _anchor_candidate(
    file_text: str,
    persisted: list[PersistedPassage],
    exact: str,
    prefix: str,
    suffix: str,
) -> tuple[int, int, PersistedPassage, TextQuoteSelector] | str:
    """Locate `exact` (bounded by prefix/suffix) at a unique in-passage offset.

    Returns either a skip reason string ("extract-quote-not-found" /
    "extract-quote-ambiguous" / "extract-anchored-outside-passage") or the anchored locus
    `(file_idx, length, containing_passage, passage-clamped selector)`. Kind-agnostic: the
    caller builds match_text + body. `match_text` is NOT built here because its discriminator
    differs per kind.
    """
    spans = find_qualified_spans(file_text, exact, prefix, suffix)
    if not spans:
        return "extract-quote-not-found"
    if len(spans) > 1:
        return "extract-quote-ambiguous"
    file_idx = spans[0]
    length = len(exact)
    pp = _containing_passage(persisted, file_idx, length)
    if pp is None:
        return "extract-anchored-outside-passage"
    passage_start = pp.file_char_base
    passage_end = pp.file_char_base + pp.length
    prefix_start = max(passage_start, file_idx - _CONTEXT)
    suffix_end = min(passage_end, file_idx + length + _CONTEXT)
    selector = TextQuoteSelector(
        exact=exact,
        prefix=file_text[prefix_start:file_idx],
        suffix=file_text[file_idx + length:suffix_end],
    )
    return (file_idx, length, pp, selector)
```

Replace the body of `plan_statement` (signature unchanged) to call the helper, preserving the
**3a-identical** `match_text`:

```python
def plan_statement(
    file_text: str,
    persisted: list[PersistedPassage],
    candidate: StatementCandidate,
    *,
    active_iris: set[str],
    model: str,
    source_md_name: str,
) -> tuple[PlannedAnnotation | None, str | None, int]:
    """Convert a StatementCandidate to (PlannedAnnotation | None, skip_reason | None, dropped)."""
    anchored = _anchor_candidate(
        file_text, persisted, candidate.exact, candidate.prefix, candidate.suffix
    )
    if isinstance(anchored, str):
        return None, anchored, 0
    file_idx, length, pp, selector = anchored
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

Add `plan_figurative` right after it (no grounding; domain-keyed delimiter-safe `match_text`):

```python
def plan_figurative(
    file_text: str,
    persisted: list[PersistedPassage],
    candidate: FigurativeCandidate,
    *,
    model: str,
    source_md_name: str,
) -> tuple[PlannedAnnotation | None, str | None, int]:
    """Convert a FigurativeCandidate to (PlannedAnnotation | None, skip_reason | None, 0).

    No grounding (figurative domains are free-text), so the dropped count is always 0. The
    dedup match_text JSON-encodes the (source_domain, target_domain) pair so two same-span
    figures with different required domains stay distinct AND a literal '|' inside a domain
    cannot create a cross-field collision.
    """
    anchored = _anchor_candidate(
        file_text, persisted, candidate.exact, candidate.prefix, candidate.suffix
    )
    if isinstance(anchored, str):
        return None, anchored, 0
    file_idx, length, pp, selector = anchored
    section = normalize_section(pp.section)

    body = figurative_body_json(
        section=section,
        source_domain=candidate.source_domain,
        target_domain=candidate.target_domain,
        mapping=candidate.mapping,
        cue=candidate.cue,
    )
    identity = json.dumps(
        [_normalize_text(candidate.source_domain), _normalize_text(candidate.target_domain)],
        separators=(",", ":"),
        ensure_ascii=False,
    )
    match_text = f"{candidate.type}|{file_idx}:{length}|{identity}"
    planned = PlannedAnnotation(
        target=SpecificResource(source=source_md_name, selector=selector),
        annotation_type=candidate.type,
        motivation=Motivation.CLASSIFYING,
        body=TextualBody(value=body, format="application/json"),
        match_text=match_text,
        source_name=_llm_annot_source_name(model),
    )
    return planned, None, 0
```

- [ ] **Step 4: Run plan tests + the full statement-extract suite — green**

Run: `uv run --frozen pytest tests/test_statement_extract.py -q`
Expected: PASS (the refactored `plan_statement` keeps every prior assertion, incl.
`test_plan_statement_match_text_distinguishes_repeated_identical`, green).

- [ ] **Step 5: Typecheck + lint**

Run: `uv run --frozen pyright src/science_tool/annotation/statement_extract.py`
Run: `uv run --frozen ruff check src/science_tool/annotation/statement_extract.py`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/annotation/statement_extract.py science/tests/test_statement_extract.py
git commit -m "feat(paper-annotate): shared _anchor_candidate + plan_figurative (delimiter-safe domain match_text)"
```

---

### Task 5: Dispatch in `extract_candidates`

Make the orchestrator route each candidate to the right planner by kind. The merge / guard /
idempotency path is unchanged.

**Files:**
- Modify: `science/src/science_tool/annotation/statement_extract.py`
- Test: `science/tests/test_statement_extract.py`

- [ ] **Step 1: Write failing orchestrator tests**

Append (the `extract_candidates`, `read_sidecar`, `write_source_md`, `Passage`/`SourcePassages`
imports already exist):

```python
def _make_fig_source_md(tmp_path: Path) -> Path:
    abstract = SourcePassages(
        passages=(
            Passage(section="title", bioc_offset=0, text="On immunity."),
            Passage(section="discussion", bioc_offset=13,
                    text="The immune system mounts an attack on pathogens."),
        ),
        release="2024",
    )
    return write_source_md(
        directory=tmp_path, citekey="Imm2024", abstract=abstract, fulltext=None,
        retrieved_from="https://example.org", license_="unknown", licensed=False,
        pmid="2", doi=None,
    )


def test_extract_mixed_statement_and_figurative_persist(tmp_path: Path):
    src = _make_source_md(tmp_path)  # text: "BRCA1 loss drives genomic instability in tumors."
    cands = parse_candidates(json.dumps({"candidates": [
        {"type": "proposition", "exact": "BRCA1 loss drives genomic instability",
         "prefix": "", "suffix": " in tumors", "stance": "asserted"},
        {"type": "metaphor", "exact": "BRCA1 loss drives genomic instability",
         "prefix": "", "suffix": " in tumors",
         "source_domain": "a driver", "target_domain": "BRCA1 loss"},
    ]}))
    report = extract_candidates(
        source_md=src, model=_MODEL, candidates=cands, now=_NOW, actor="a",
    )
    assert report.written == 2  # same span, different type -> both persist
    assert report.grounding_dropped == 0
    sidecar = read_sidecar(src.with_name("Brca2024.source.anno.trig"))
    types = {a.annotation_type for a in sidecar.annotations}
    assert {"proposition", "metaphor"} <= types


def test_extract_figurative_only_records_hash_no_grounding(tmp_path: Path):
    src = _make_fig_source_md(tmp_path)
    cands = parse_candidates(json.dumps({"candidates": [
        {"type": "analogy", "exact": "The immune system mounts an attack",
         "prefix": "", "suffix": " on pathogens",
         "source_domain": "warfare", "target_domain": "immune response"},
    ]}))
    report = extract_candidates(
        source_md=src, model=_MODEL, candidates=cands, now=_NOW, actor="a",
    )
    assert report.written == 1
    assert report.grounding_dropped == 0
    assert report.source_text_hash_recorded is True


def test_extract_figurative_unanchored_does_not_record_hash(tmp_path: Path):
    src = _make_fig_source_md(tmp_path)
    cands = parse_candidates(json.dumps({"candidates": [
        {"type": "metaphor", "exact": "a phrase absent from the document",
         "prefix": "", "suffix": "",
         "source_domain": "warfare", "target_domain": "immune response"},
    ]}))
    report = extract_candidates(
        source_md=src, model=_MODEL, candidates=cands, now=_NOW, actor="a",
    )
    assert report.written == 0
    assert report.skipped == {"extract-quote-not-found": 1}
    assert report.source_text_hash_recorded is False
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run --frozen pytest tests/test_statement_extract.py -q -k "mixed or figurative_only or figurative_unanchored"`
Expected: FAIL (the orchestrator still calls `plan_statement` for every candidate → a
`FigurativeCandidate` has no `.stance`, raising `AttributeError`).

- [ ] **Step 3: Dispatch by kind in `extract_candidates`**

In `extract_candidates`, replace the per-candidate loop body:

```python
    skipped: Counter[str] = Counter()
    grounding_dropped = 0
    planned: list[PlannedAnnotation] = []
    for cand in candidates:
        if isinstance(cand, StatementCandidate):
            p, reason, dropped = plan_statement(
                file_text, persisted, cand,
                active_iris=active, model=model, source_md_name=source_md.name,
            )
        else:
            p, reason, dropped = plan_figurative(
                file_text, persisted, cand,
                model=model, source_md_name=source_md.name,
            )
        grounding_dropped += dropped
        if p is not None:
            planned.append(p)
        elif reason is not None:
            skipped[reason] += 1
```

Update the `candidates` parameter annotation on `extract_candidates`:

```python
def extract_candidates(
    *,
    source_md: Path,
    model: str,
    candidates: list[StatementCandidate | FigurativeCandidate],
    now: datetime,
    actor: str,
) -> ExtractReport:
```

Everything below the loop (`merge_planned`, the `advance = not skipped` guard, the
`source_text_hash` ledger update, the write, the `note`) is unchanged.

- [ ] **Step 4: Run the full statement-extract suite — green**

Run: `uv run --frozen pytest tests/test_statement_extract.py -q`
Expected: PASS.

- [ ] **Step 5: Typecheck + lint**

Run: `uv run --frozen pyright src/science_tool/annotation/statement_extract.py`
Run: `uv run --frozen ruff check src/science_tool/annotation/statement_extract.py`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/annotation/statement_extract.py science/tests/test_statement_extract.py
git commit -m "feat(paper-annotate): extract_candidates dispatches statement vs figurative by kind"
```

---

### Task 6: CLI surface — type-neutral output + updated malformed test

`extract_cmd` already calls `extract_candidates` (renamed in Task 1). Make its human-readable
output and docstring type-neutral, and fix the CLI test that used `metaphor` as a malformed example.

**Files:**
- Modify: `science/src/science_tool/annotation/cli.py`
- Test: `science/tests/test_annotate_extract_cli.py`

- [ ] **Step 1: Update the malformed-input test + add a figurative round-trip test**

In `test_annotate_extract_cli.py`, change `test_extract_cli_malformed_input_fails_loud` so the bad
input is malformed for a real reason (a figurative candidate missing its required domains):

```python
def test_extract_cli_malformed_input_fails_loud(tmp_path: Path):
    src = _make_source_md(tmp_path)
    bad = tmp_path / "bad.json"
    # metaphor is a valid type now, but this one is missing required domains -> fail loud
    bad.write_text(json.dumps({"candidates": [{"type": "metaphor", "exact": "x",
                   "prefix": "", "suffix": ""}]}),
                   encoding="utf-8")
    r = CliRunner().invoke(annotate_group, [
        "extract", "--source-md", str(src), "--model", _MODEL, "--input", str(bad),
    ])
    assert r.exit_code != 0
    # nothing written: no sidecar created
    assert not src.with_name("Brca2024.source.anno.trig").exists()
```

Add a figurative round-trip + type-neutral-output test:

```python
def test_extract_cli_figurative_round_trip_and_neutral_output(tmp_path: Path):
    # source text whose abstract passage contains the figurative span
    abstract = SourcePassages(
        passages=(
            Passage(section="title", bioc_offset=0, text="On immunity."),
            Passage(section="abstract", bioc_offset=13,
                    text="The immune system mounts an attack on pathogens."),
        ),
        release="2024",
    )
    src = write_source_md(
        directory=tmp_path, citekey="Imm2024", abstract=abstract, fulltext=None,
        retrieved_from="https://example.org", license_="unknown", licensed=False,
        pmid="2", doi=None,
    )
    cand_file = tmp_path / "candidates.json"
    cand_file.write_text(json.dumps({"candidates": [{
        "type": "metaphor", "exact": "The immune system mounts an attack",
        "prefix": "", "suffix": " on pathogens",
        "source_domain": "warfare", "target_domain": "immune response",
    }]}), encoding="utf-8")
    runner = CliRunner()
    # table output (default) must be type-neutral: "annotation(s) written"
    r = runner.invoke(annotate_group, [
        "extract", "--source-md", str(src), "--model", _MODEL, "--input", str(cand_file),
    ])
    assert r.exit_code == 0, r.output
    assert "annotation(s) written" in r.output
    assert "statement(s) written" not in r.output

    sidecar = read_sidecar(src.with_name("Imm2024.source.anno.trig"))
    assert any(a.annotation_type == "metaphor" for a in sidecar.annotations)
```

- [ ] **Step 2: Run to verify the new round-trip test fails**

Run: `uv run --frozen pytest tests/test_annotate_extract_cli.py -q -k "figurative_round_trip or malformed"`
Expected: the round-trip test FAILs on the `"annotation(s) written"` assertion (output still says
"statement(s)"); the malformed test passes (it fails loud either way) but is now correctly scoped.

- [ ] **Step 3: Make the CLI output + docstring type-neutral**

In `cli.py` `extract_cmd`, update the docstring first line:

```python
    """Persist agent-extracted annotation candidates as anchored spans.

    Handles both statement (proposition/question/hypothesis) and figurative
    (metaphor/analogy) candidates in one mixed candidates.json. `--check` reports
    changed/unchanged without writing. Otherwise reads `--input candidates.json`,
    anchors each quote, and merges idempotently into `<citekey>.source.anno.trig`.
    """
```

And the table-format branch — change `statement(s) written` to the type-neutral form:

```python
    else:
        skips = ", ".join(f"{k}:{v}" for k, v in sorted(report.skipped.items())) or "none"
        click.echo(
            f"annotate extract: {report.written} annotation(s) written, "
            f"{report.grounding_dropped} grounding field(s) dropped, "
            f"skipped [{skips}], "
            f"hash recorded: {report.source_text_hash_recorded}"
        )
        if report.note:
            click.echo(report.note)
```

(The `--json` branch keys are unchanged.)

- [ ] **Step 4: Run the CLI suite — green**

Run: `uv run --frozen pytest tests/test_annotate_extract_cli.py -q`
Expected: PASS.

- [ ] **Step 5: Typecheck + lint**

Run: `uv run --frozen pyright src/science_tool/annotation/cli.py`
Run: `uv run --frozen ruff check src/science_tool/annotation/cli.py`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/annotation/cli.py science/tests/test_annotate_extract_cli.py
git commit -m "feat(paper-annotate): type-neutral extract CLI output + figurative round-trip test"
```

---

### Task 7: Register the figurative vocabulary in `annotation-tokens.md`

**Files:**
- Modify: `docs/conventions/annotation-tokens.md`

- [ ] **Step 1: Replace the Phase-3a trailing line + add a figurative section**

The Statement section currently ends with:

```
`metaphor` / `analogy` statement types are Phase 3b (additive), not registered here yet.
```

Replace that single line with the figurative section below:

```markdown
## Figurative annotations (paper-annotate Phase 3b)

Agent-extracted metaphors and analogies. Same `paper-annotate` subagent + `science annotate extract`
command + `llm-annot:<model>:paper-annotate-v1` source as statements — emitted in the **same**
`candidates.json`, discriminated by `type`.

- **`annotation_type`**: `metaphor` | `analogy` (kebab; no `sci:` prefix).
  - **metaphor**: figurative framing / identity transfer between two domains, often *implicit*
    ("the cell is a factory").
  - **analogy**: an *explicit* comparison or structural mapping between two domains
    ("like a factory line, the ribosome assembles ...").
- **Motivation**: `oa:classifying`.
- **Body**: a single `TextualBody` (`format = application/json`), sorted keys + compact separators
  + `allow_nan=False`:

  ```json
  {"section":"discussion","source_domain":"warfare","target_domain":"immune response",
   "mapping":"immune cells framed as soldiers","cue":"attack"}
  ```

  - `section` (required, CLI-derived): same closed vocabulary as statements.
  - `source_domain` / `target_domain` (required, non-empty after trim): the domain borrowed FROM
    (the vehicle) and the actual subject described (the tenor).
  - `mapping` (optional, non-empty if present): the correspondence being transferred.
  - `cue` (optional, non-empty if present): the lexical trigger (e.g. "like" / "as" / "mounts").
  - **No `stance`, no concept grounding** — figurative domains are free-text (entity linking is
    Phase 4). A blank/whitespace-only required-or-present field is rejected (fail loud), not stored.

- **Dedup**: `match_text` for figurative is
  `type|file_idx:length|json([normalized_source_domain, normalized_target_domain])` — the
  whitespace-normalized, JSON-encoded domain pair is the semantic identity (delimiter-safe), so two
  same-span figures with different domains both persist. `mapping`/`cue` are enrichment, not identity.
- **Document guard**: identical to statements (`sci:sourceTextHash`); a mixed statement+figurative
  run advances the hash only when no candidate fails to anchor.
```

- [ ] **Step 2: Sanity-check the doc renders (no broken fences)**

Run: `grep -n "Figurative annotations" docs/conventions/annotation-tokens.md`
Expected: one match; confirm the surrounding ```` ```json ```` / ```` ``` ```` fences balance.

- [ ] **Step 3: Commit**

```bash
git add docs/conventions/annotation-tokens.md
git commit -m "doc(annotation-tokens): register metaphor/analogy figurative vocabulary (Phase 3b)"
```

---

### Task 8: Agent prompt + command + agent-file test

Teach the `paper-annotate` subagent to also extract figurative annotations, drop the
"statements only" scope line, and de-scope the command wording. Extend the existing agent-file test.

**Files:**
- Modify: `agents/paper-annotate.md`
- Modify: `commands/annotate-paper.md`
- Test: `science/tests/test_annotate_extract_cli.py`

- [ ] **Step 1: Extend the agent-file test (figurative coverage assertions)**

In `test_annotate_extract_cli.py`, extend `test_paper_annotate_agent_file_has_frontmatter`:

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
    # Phase 3b: the agent must document figurative extraction
    assert "metaphor" in text and "analogy" in text
    assert "source_domain" in text and "target_domain" in text
    cmd = repo_root / "commands" / "annotate-paper.md"
    assert cmd.is_file(), "commands/annotate-paper.md must exist"
    assert "--check" in cmd.read_text(encoding="utf-8")  # documents the precheck
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run --frozen pytest tests/test_annotate_extract_cli.py -q -k agent_file`
Expected: FAIL (`metaphor`/`source_domain` not yet in the agent file).

- [ ] **Step 3: Update `agents/paper-annotate.md`**

Update the frontmatter `description` (line 3) to mention both:

```
description: Extract proposition/question/hypothesis statements AND metaphor/analogy figures from one paper's persisted .source.md, using existing PubTator entity annotations for optional statement grounding (figurative domains remain free-text), and persist them via `science annotate extract`. Requires an existing <citekey>.source.md (run `science paper persist-source` first). Returns the written/skipped counts.
```

Update the opening sentence (lines 10–13) from "extract sub-article **statements** ... You do not"
to include figures:

```
from one paper and hand them to the deterministic `science annotate extract` command. You extract
two kinds of span: **statements** (propositions, questions, hypotheses) and **figures** (metaphors,
analogies). You do not summarize, you do not edit the sidecar, you do not touch the `.source.md`.
```

Add a new step after the statement-extraction step (step 3), renumbering the later steps
(`candidates.json` write becomes step 5, persist step 6):

```markdown
4. **Extract figures.** For each metaphor or analogy the authors actually use:
   - `type`: `metaphor` (figurative framing or identity transfer between two domains, often
     implicit — "the cell is a factory") or `analogy` (an explicit comparison or structural mapping
     — "like a factory line, the ribosome assembles ...").
   - `exact` / `prefix` / `suffix`: same verbatim anchoring rules as statements (quote from passage
     bodies, never headings).
   - `source_domain` (required): the domain borrowed FROM — the vehicle ("warfare", "a factory").
   - `target_domain` (required): the actual subject being described — the tenor ("immune response",
     "the cell").
   - `mapping` (optional): the correspondence being transferred ("immune cells as soldiers").
   - `cue` (optional): the lexical trigger word(s) ("like", "as", "mounts").
   - Figures carry NO `stance` and NO concept IRIs (free-text domains). Omit optional fields you
     cannot fill confidently — never emit a blank string (the CLI rejects blank fields).

   Statements and figures go in the SAME `candidates.json`, mixed freely.
```

Update the **Scope discipline** section: replace
`Statements only (no metaphors/analogies — that is a later phase).` with
`Statements AND figures (metaphors/analogies). One paper.`

- [ ] **Step 4: Update `commands/annotate-paper.md`**

Change the opening description (lines 3–4) from "Extract sub-article **statements**
(propositions/questions/hypotheses)" to:

```
Extract sub-article **statements** (propositions/questions/hypotheses) and **figures**
(metaphors/analogies) from a paper that already has a persisted `.source.md` and PubTator
annotations, via the `paper-annotate` subagent.
```

In the Workflow step 4 "Surface the report" line, no change is needed (it already surfaces
`written / skipped / grounding_dropped`, which covers both kinds).

- [ ] **Step 5: Run the agent-file test — green**

Run: `uv run --frozen pytest tests/test_annotate_extract_cli.py -q -k agent_file`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add agents/paper-annotate.md commands/annotate-paper.md science/tests/test_annotate_extract_cli.py
git commit -m "feat(paper-annotate): agent + command extract metaphors/analogies (Phase 3b)"
```

---

## Final verification (after all tasks)

- [ ] **Full annotation-module suite + the broader regression slice it touches:**

```bash
cd science
uv run --frozen pytest tests/test_statement_extract.py tests/test_annotate_extract_cli.py \
    tests/test_annotation_audit_merge.py tests/test_annotation_io.py -q
```
Expected: all PASS, exit 0. (Rely on exit code + zero FAILED/ERROR; the pytest summary line may not
reach piped logs.)

- [ ] **Typecheck + lint the whole annotation package:**

```bash
uv run --frozen pyright src/science_tool/annotation/
uv run --frozen ruff check src/science_tool/annotation/
```
Expected: clean (modulo the known editor-artifact `reportMissingImports` lines).

- [ ] Hand off to **superpowers:finishing-a-development-branch**.

---

## Self-review notes (author)

- **Spec coverage:** FigurativeCandidate (T2), figurative body (T3), shared anchor + plan_figurative
  with delimiter-safe domain match_text (T4), dispatch (T5), CLI type-neutral surface (T6),
  conventions (T7), agent/command (T8). Rename (T1) precedes all. Non-empty-after-trim (T2),
  cross-kind rejection (T2), no-grounding (T4/T5), unchanged guard/source (T5) — all covered.
- **Type consistency:** `StatementCandidate` / `FigurativeCandidate` / `extract_candidates` used
  identically across tasks; `parse_candidates -> list[StatementCandidate | FigurativeCandidate]`;
  `plan_figurative` has no `active_iris` param (no grounding) and always returns `dropped=0`;
  `_anchor_candidate` returns `tuple | str` (skip reason), checked via `isinstance(_, str)`.
- **Behavior neutrality:** `plan_statement`'s `match_text` and body are byte-identical to 3a, so the
  3a statement tests stay green after the T4 refactor. The two `metaphor`-as-negative tests are
  fixed in T2/T6.

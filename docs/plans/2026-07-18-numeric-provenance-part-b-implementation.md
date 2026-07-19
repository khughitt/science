# Numeric-Provenance Part B (MVP) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the `numeric-verification` prose lint — an opt-in per-claim binding of a prose number to `artifact + locator`, verified by reading the artifact and testing `Decimal` interval membership at displayed precision.

**Architecture:** Two new pure modules (`numeric_literal.py` grammar+compare, `numeric_binding.py` schema+parse), one new I/O module (`artifact_value_reader.py` typed resolver + reader), a new detector `detect_numeric_verification` wired into `scan_root` as an atomic pair with `numeric-anchor`, and a `bound_spans` suppression seam so bound claims never draw a `numeric-anchor` finding. Follows Part A's purity split: pure classification/parse core, all disk I/O injected.

**Tech Stack:** Python 3.12, pydantic v2 (`extra="forbid"` models), pandas/pyarrow (feather), stdlib `json`/`decimal`. No new dependency.

**Design:** `docs/plans/2026-07-18-numeric-provenance-part-b-design.md` (rev 3). Read it before starting; every task below implements a section of it.

## Global Constraints

- **Severity model is `info`/`warn` only.** `numeric-verification` base severity is **`warn`**. No new `error` severity tier. `mismatch` and `error` outcomes both emit a `warn` `LintIssue`; `verified` and `unverifiable` emit **no** `LintIssue`.
- **`counts` stays flat** (`{check: emitted_issue_count}`, built in `prose_lint.py:820`). Outcome tallies go in a **separate** `coverage` field. Never nest tallies inside `counts` (breaks `prose_lints.py:140`).
- **Atomic pair.** Selecting `numeric-anchor` runs `numeric-verification` and vice versa, in `scan_root`, the CLI, and validation. Suppression of bound spans is **unconditional wherever `numeric-anchor` runs** (including the annotation adapter, which calls the detector with no extra args).
- **Binding artifact is always a file path** — never a `task:`/`cite:` ref. `unverifiable` is reached only via an `opaque` locator (or a `%` unit).
- **Grammar parses whole tokens** (`re.fullmatch`) — never prefix-parse. `12/15` must be captured whole and rejected, never verified as `12`.
- **JSON parses directly to `Decimal`** (`parse_float=Decimal, parse_int=Decimal`, reject `NaN`/`Infinity`). Feather binary floats use `Decimal(str(x))`.
- **Default precision interval is open**; an exact boundary hit → `unverifiable`. Author `tolerance` interval is closed.
- Purity: `numeric_literal.py` and `numeric_binding.py` do **no** disk I/O. All I/O lives in `artifact_value_reader.py`.
- Run from `science/`: `uv run --frozen python -m pytest tests/<file> -q`. No AI-attribution trailers in commits.

## Shared Types (defined by the tasks that create them; pinned here for cross-task agreement)

```python
# numeric_literal.py
@dataclass(frozen=True)
class ParsedLiteral:
    value: Decimal        # numeric value, exponent applied (7.94e3 -> Decimal("7940"))
    quantum: Decimal      # 10**(exponent - fractional_digits); place value of last shown digit
    unit: str | None      # "%" or None ("×" is dropped to None)

# MatchOutcome / BindingOutcome string constants (module-level Final):
VERIFIED = "verified"; MISMATCH = "mismatch"; UNVERIFIABLE = "unverifiable"; ERROR = "error"

# numeric_binding.py
@dataclass(frozen=True)
class ClaimBinding:
    id: str
    artifact: str
    locator: PointerLocator | ColumnLocator | OpaqueLocator
    tolerance: Decimal | None
    span: tuple[int, int, int]        # (line, col_start, col_end), 1-based, inclusive-exclusive col
    value_text: str | None            # the pinned prose token; None only for opaque-on-non-numeric

@dataclass(frozen=True)
class BindingError:
    id: str | None
    line: int | None
    message: str                      # becomes a warn LintIssue (outcome ERROR)

# artifact_value_reader.py
@dataclass(frozen=True)
class ResolvedArtifact:
    path: Path
    kind: str                         # "json" | "feather"
@dataclass(frozen=True)
class ArtifactError:
    detail: str
@dataclass(frozen=True)
class ReaderError:
    detail: str

# coverage payload (scan_root return, new key alongside "counts"/"hits"):
# coverage["numeric-verification"] = {"verified": int, "unverifiable": int, "mismatch": int, "error": int}
```

---

### Task 1: Prose numeric grammar (`parse_prose_literal`)

**Files:**
- Create: `science/src/science_tool/numeric_literal.py`
- Test: `science/tests/test_numeric_literal.py`

**Interfaces:**
- Produces: `ParsedLiteral(value: Decimal, quantum: Decimal, unit: str | None)`; `parse_prose_literal(text: str) -> ParsedLiteral | None` (None ⇒ not a whole single scalar literal).

- [ ] **Step 1: Write the failing test**

```python
# science/tests/test_numeric_literal.py
from decimal import Decimal
import pytest
from science_tool.numeric_literal import parse_prose_literal

@pytest.mark.parametrize("text,value,quantum,unit", [
    ("8",       Decimal("8"),    Decimal("1"),     None),
    ("7.94",    Decimal("7.94"), Decimal("0.01"),  None),
    ("-7.94×",  Decimal("-7.94"),Decimal("0.01"),  None),   # × dropped
    ("0.001",   Decimal("0.001"),Decimal("0.001"), None),
    ("1,234",   Decimal("1234"), Decimal("1"),     None),
    ("7.94e3",  Decimal("7940"), Decimal("10"),    None),
    ("58%",     Decimal("58"),   Decimal("1"),     "%"),
])
def test_accepts_single_scalar(text, value, quantum, unit):
    p = parse_prose_literal(text)
    assert p is not None
    assert p.value == value and p.quantum == quantum and p.unit == unit

@pytest.mark.parametrize("text", ["12/15", "3–5", "3-5", "7.94 7.95", "abc", "", "1.2.3"])
def test_rejects_non_scalar(text):
    assert parse_prose_literal(text) is None
```

- [ ] **Step 2: Run — expect ImportError/fail.** `uv run --frozen python -m pytest tests/test_numeric_literal.py -q`

- [ ] **Step 3: Implement**

```python
# science/src/science_tool/numeric_literal.py
"""Pure prose-numeric grammar and displayed-precision comparison (Part B)."""
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from typing import Final
import re

VERIFIED: Final = "verified"
MISMATCH: Final = "mismatch"
UNVERIFIABLE: Final = "unverifiable"

@dataclass(frozen=True)
class ParsedLiteral:
    value: Decimal
    quantum: Decimal
    unit: str | None

# Whole-token grammar. Optional sign, digits with optional thousands-commas OR
# plain digits, optional fraction, optional exponent, optional trailing ×/%.
_LITERAL_RE = re.compile(
    r"(?P<sign>[+-]?)"
    r"(?P<int>\d{1,3}(?:,\d{3})+|\d+)"
    r"(?:\.(?P<frac>\d+))?"
    r"(?:[eE](?P<exp>[+-]?\d+))?"
    r"(?P<unit>[×%]?)"
)

def parse_prose_literal(text: str) -> ParsedLiteral | None:
    m = _LITERAL_RE.fullmatch(text.strip())
    if m is None:
        return None
    int_part = m.group("int").replace(",", "")
    frac = m.group("frac") or ""
    exp = int(m.group("exp")) if m.group("exp") else 0
    unit_glyph = m.group("unit") or ""
    mantissa = Decimal(f"{m.group('sign')}{int_part}" + (f".{frac}" if frac else ""))
    value = mantissa * (Decimal(10) ** exp)
    quantum = Decimal(10) ** (exp - len(frac))
    unit = "%" if unit_glyph == "%" else None   # × is dropped
    return ParsedLiteral(value=value, quantum=quantum, unit=unit)
```

- [ ] **Step 4: Run — expect PASS.**
- [ ] **Step 5: Commit** — `git add science/src/science_tool/numeric_literal.py science/tests/test_numeric_literal.py && git commit -m "feat(numeric-verification): prose numeric-literal grammar"`

---

### Task 2: Displayed-precision comparison (`compare_at_precision`)

**Files:**
- Modify: `science/src/science_tool/numeric_literal.py`
- Test: `science/tests/test_numeric_literal.py`

**Interfaces:**
- Consumes: `ParsedLiteral`.
- Produces: `compare_at_precision(parsed: ParsedLiteral, value: Decimal, tolerance: Decimal | None = None) -> str` returning `VERIFIED | MISMATCH | UNVERIFIABLE`.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_numeric_literal.py
from science_tool.numeric_literal import compare_at_precision, parse_prose_literal
def _c(text, artifact, tol=None):
    return compare_at_precision(parse_prose_literal(text), Decimal(str(artifact)), tol)

def test_open_interval_and_boundary():
    assert _c("7.94", "7.94312") == "verified"
    assert _c("8", "7.9449") == "verified"
    assert _c("7.94", "7.951") == "mismatch"
    assert _c("7.94", "7.945") == "unverifiable"      # exact boundary (midpoint)
    assert _c("7.94e3", "7943.1") == "verified"
def test_percent_is_unverifiable():
    assert _c("58%", "0.58") == "unverifiable"
    assert _c("58%", "58", Decimal("0.5")) == "unverifiable"   # tolerance can't rescue %
def test_tolerance_is_closed():
    assert _c("0.001", "0.0015", Decimal("0.0005")) == "verified"   # boundary included
    assert _c("0.001", "0.0016", Decimal("0.0005")) == "mismatch"
```

- [ ] **Step 2: Run — expect fail.**

- [ ] **Step 3: Implement (append to `numeric_literal.py`)**

```python
def compare_at_precision(parsed: ParsedLiteral, value: Decimal, tolerance: Decimal | None = None) -> str:
    if parsed.unit == "%":
        return UNVERIFIABLE            # scale normalization deferred; tolerance cannot bridge
    if tolerance is not None:
        return VERIFIED if abs(value - parsed.value) <= tolerance else MISMATCH
    half = parsed.quantum / 2
    lo, hi = parsed.value - half, parsed.value + half
    if value == lo or value == hi:
        return UNVERIFIABLE            # exact midpoint shared with adjacent display value
    return VERIFIED if lo < value < hi else MISMATCH
```

- [ ] **Step 4: Run — expect PASS.**
- [ ] **Step 5: Commit** — `git commit -am "feat(numeric-verification): displayed-precision comparison"`

---

### Task 3: Binding schema models (fail-closed)

**Files:**
- Create: `science/src/science_tool/numeric_binding.py`
- Test: `science/tests/test_numeric_binding.py`

**Interfaces:**
- Produces: `PointerLocator(pointer: str)`, `ColumnLocator(column: str, where: dict | None)`, `OpaqueLocator(opaque: str)`; `NumericClaimEntry` (validates one map entry → typed `ClaimBinding` minus span/value_text); `validate_entry(id: str, raw: dict, artifact_ext: str) -> ParsedEntry | BindingError`.

Design rules (§2): `extra="forbid"`; exactly one of `{pointer, column, opaque}`; `where` non-empty if present; `pointer`↔`.json`, `column`↔`.feather`; `tolerance` finite `>0`, forbidden with `opaque`.

- [ ] **Step 1: Write the failing test**

```python
# science/tests/test_numeric_binding.py
from decimal import Decimal
from science_tool.numeric_binding import validate_entry, BindingError, PointerLocator, ColumnLocator, OpaqueLocator

def test_pointer_ok():
    e = validate_entry("b1", {"artifact": "r.json", "locator": {"pointer": "/a/0"}}, ".json")
    assert isinstance(e.locator, PointerLocator) and e.artifact == "r.json"
def test_column_where_ok():
    e = validate_entry("b1", {"artifact": "x.feather", "locator": {"column": "c", "where": {"d": "D1"}}}, ".feather")
    assert isinstance(e.locator, ColumnLocator) and e.locator.where == {"d": "D1"}
def test_opaque_ok_any_ext():
    e = validate_entry("b1", {"artifact": "f.png", "locator": {"opaque": "read off panel"}}, ".png")
    assert isinstance(e.locator, OpaqueLocator)
def test_tolerance_positive_finite():
    e = validate_entry("b1", {"artifact": "r.json", "locator": {"pointer": "/a"}, "tolerance": 5e-4}, ".json")
    assert e.tolerance == Decimal("0.0005")

import pytest
@pytest.mark.parametrize("raw,ext", [
    ({"artifact": "r.json", "locator": {"pointer": "/a", "column": "c"}}, ".json"),   # two shapes
    ({"artifact": "r.json", "locator": {}}, ".json"),                                  # no shape
    ({"artifact": "x.feather", "locator": {"column": "c", "where": {}}}, ".feather"),  # empty where
    ({"artifact": "r.json", "locator": {"column": "c"}}, ".json"),                     # ext mismatch
    ({"artifact": "r.json", "locator": {"pointer": "/a"}, "bogus": 1}, ".json"),       # extra field
    ({"artifact": "r.json", "locator": {"pointer": "/a"}, "tolerance": -1}, ".json"),  # bad tol
    ({"artifact": "f.png", "locator": {"opaque": "x"}, "tolerance": 1}, ".png"),       # tol w/ opaque
    ({"locator": {"pointer": "/a"}}, ".json"),                                          # missing artifact
])
def test_rejects(raw, ext):
    assert isinstance(validate_entry("b1", raw, ext), BindingError)
```

- [ ] **Step 2: Run — expect fail.**

- [ ] **Step 3: Implement** — pydantic models with `model_config = ConfigDict(extra="forbid")`; a discriminated locator validator; `validate_entry` catches `ValidationError` and the extension/tolerance rules, returning `BindingError(id, None, msg)` on any violation, else a `ParsedEntry(artifact, locator, tolerance: Decimal | None)`. Convert `tolerance` to `Decimal(str(v))`; reject non-finite/`<=0`. (Full pydantic model per design §2; ~60 lines.)

- [ ] **Step 4: Run — expect PASS.**
- [ ] **Step 5: Commit** — `git commit -m "feat(numeric-verification): fail-closed binding schema"`

---

### Task 4: Marker attachment & `parse_claim_bindings`

**Files:**
- Modify: `science/src/science_tool/numeric_binding.py`
- Test: `science/tests/test_numeric_binding.py`

**Interfaces:**
- Consumes: `DocumentContext` (from `numeric_provenance`), `parse_prose_literal` (Task 1), `validate_entry` (Task 3).
- Produces: `parse_claim_bindings(document) -> tuple[list[ClaimBinding], list[BindingError]]`.

Rules (§1): `numeric_claims` from `document.frontmatter`; scan body lines for `[^id]` where `id ∈ numeric_claims`; exactly-one-marker per id (0 orphan / >1 duplicate → `BindingError`); the pinned token is the maximal contiguous numeric-ish run (char class `[-+0-9.,eE/×%–]`) immediately before the marker after stripping trailing markup (`*`, whitespace, `)`); feed that whole token to `parse_prose_literal` — `None` ⇒ `error` (rejects `12/15`); opaque bindings may pin a non-numeric word (`value_text=None`).

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_numeric_binding.py
from science_tool.numeric_provenance import build_document_context
from science_tool.numeric_binding import parse_claim_bindings

def _doc(tmp_path, body, fm):
    p = tmp_path / "e.md"; p.write_text(f"---\n{fm}\n---\n{body}\n"); return build_document_context(p)

def test_attaches_and_pins_span(tmp_path):
    fm = "numeric_claims:\n  b1:\n    artifact: x.feather\n    locator: {column: c}"
    doc = _doc(tmp_path, "The value was **7.94×**[^b1] here.", fm)
    binds, errs = parse_claim_bindings(doc)
    assert errs == [] and len(binds) == 1
    assert binds[0].value_text == "7.94×" and binds[0].span[0] == 5   # line

def test_ratio_before_marker_is_error(tmp_path):
    fm = "numeric_claims:\n  b1:\n    artifact: x.feather\n    locator: {column: c}"
    doc = _doc(tmp_path, "ratio 12/15[^b1] no.", fm)
    binds, errs = parse_claim_bindings(doc)
    assert binds == [] and any("not a" in e.message.lower() or "single" in e.message.lower() for e in errs)

def test_orphan_and_duplicate_are_errors(tmp_path):
    fm = "numeric_claims:\n  b1:\n    artifact: x.feather\n    locator: {column: c}"
    assert parse_claim_bindings(_doc(tmp_path, "no marker here.", fm))[1]           # orphan
    assert parse_claim_bindings(_doc(tmp_path, "a 1.0[^b1] b 2.0[^b1].", fm))[1]    # duplicate

def test_real_footnote_untouched(tmp_path):
    fm = "numeric_claims:\n  b1:\n    artifact: x.feather\n    locator: {column: c}"
    doc = _doc(tmp_path, "cited 3.0[^b1]. Unrelated[^x] note.", fm)
    binds, errs = parse_claim_bindings(doc)
    assert len(binds) == 1 and errs == []      # [^x] ignored (not in map)
```

- [ ] **Step 2: Run — expect fail.**
- [ ] **Step 3: Implement** `parse_claim_bindings` per rules above (~70 lines; marker regex `re.compile(r"\[\^([A-Za-z0-9_-]+)\]")`, token-extraction regex `re.compile(r"([-+0-9.,eE/×%–]+)\s*\**\s*$")` on the line prefix). Non-`.json`/`.feather`/other artifact extension passed to `validate_entry` as-is; opaque entries skip token parsing.
- [ ] **Step 4: Run — expect PASS.**
- [ ] **Step 5: Commit** — `git commit -m "feat(numeric-verification): marker attachment and binding parse"`

---

### Task 5: `bound_spans` suppression seam

**Files:**
- Modify: `science/src/science_tool/numeric_provenance.py` (`assess_numeric_claims` signature + skip)
- Modify: `science/src/science_tool/prose_lint.py` (`detect_numeric_anchor` computes bindings internally)
- Test: `science/tests/test_numeric_provenance.py`

**Interfaces:**
- `assess_numeric_claims(document, index, config, *, bound_spans: frozenset[tuple[int,int,int]] = frozenset())` — a claim whose `(line, col)` falls within any bound span is **skipped entirely** (no assessment emitted).
- `detect_numeric_anchor` unchanged signature to external callers; internally calls `parse_claim_bindings(document)` and passes the resulting spans as `bound_spans` (so the annotation adapter, which calls `detector(md_path)` with no kwargs, still suppresses).

- [ ] **Step 1: Write the failing test** — a doc with a bound number that Part A *would* flag as `Unanchored` (no provenance) asserts `detect_numeric_anchor(path)` returns **no** finding on that line; an *unbound* ungrounded number on another line still flags. Include a dangling-artifact binding (still suppressed).

```python
# tests/test_numeric_provenance.py (new test)
def test_bound_claim_suppressed_from_anchor(tmp_path):
    from science_tool.prose_lint import detect_numeric_anchor
    fm = "numeric_claims:\n  b1:\n    artifact: nope.feather\n    locator: {column: c}"
    p = tmp_path / "e.md"
    p.write_text(f"---\n{fm}\n---\nBound 3.14159[^b1] here.\n\nUnbound 2.71828 there.\n")
    lines = {i.line for i in detect_numeric_anchor(p)}
    assert 4 not in lines        # bound line suppressed even though artifact is dangling
    assert 6 in lines            # unbound ungrounded number still flags
```

- [ ] **Step 2: Run — expect fail.**
- [ ] **Step 3: Implement** the `bound_spans` param + skip in `assess_numeric_claims` (add a check right after the `NumericClaim(...)` is built, before "1 — NotClaim": `if _within_bound_span(lineno, match.start()+1, len(value), bound_spans): continue`), and the internal `parse_claim_bindings` call in `detect_numeric_anchor`. Add helper `_within_bound_span(line, col, length, spans)`.
- [ ] **Step 4: Run — expect PASS**, and run the full `tests/test_numeric_provenance.py` + `tests/test_numeric_provenance_oracle.py` to confirm no Part-A regression (unbound behavior byte-for-byte unchanged).
- [ ] **Step 5: Commit** — `git commit -m "feat(numeric-verification): suppress bound claims from numeric-anchor"`

---

### Task 6: Typed artifact resolver (`resolve_artifact`)

**Files:**
- Create: `science/src/science_tool/artifact_value_reader.py`
- Test: `science/tests/test_artifact_value_reader.py`

**Interfaces:**
- Produces: `ResolvedArtifact(path, kind)`, `ArtifactError(detail)`; `resolve_artifact(ref: str, project_root: Path, data_root: Path, *, max_json_bytes: int, max_feather_bytes: int) -> ResolvedArtifact | ArtifactError`.

Rules (§4/§6): reject absolute / `..`; locate under `project_root` then `data_root`; present under **both** → ambiguity error; `realpath` must stay within the **same** chosen root (symlink escape → error); must be a **regular file**; extension `.json`→kind `json` (cap `max_json_bytes`), `.feather`→kind `feather` (cap `max_feather_bytes`); size over cap → error. (Non-data extensions never reach here — opaque handled upstream; `pointer`/`column` on them fail schema.)

- [ ] **Step 1: Write the failing test** — tmp project with a real `.json` under root (resolves), one under both roots (ambiguity error), a symlink pointing outside root (escape error), a `../x` (rejected), an absolute path (rejected), an over-cap file (error). Assert `ResolvedArtifact.kind` and `ArtifactError` per case.
- [ ] **Step 2: Run — expect fail.**
- [ ] **Step 3: Implement** using `Path.resolve(strict=True)` for realpath, `os.path.commonpath`/`Path.is_relative_to` for containment against `root.resolve()`, `stat().st_size` for the cap, `.is_file()` after realpath (rejects dirs/symlinks-to-dir). Absolute/`..` guard first, mirroring `ResolutionIndex.resolve` (`numeric_provenance.py:224`).
- [ ] **Step 4: Run — expect PASS.**
- [ ] **Step 5: Commit** — `git commit -m "feat(numeric-verification): typed symlink-safe artifact resolver"`

---

### Task 7: Scalar reader (`read_scalar`)

**Files:**
- Modify: `science/src/science_tool/artifact_value_reader.py`
- Test: `science/tests/test_artifact_value_reader.py`
- Create fixtures: `science/tests/fixtures/numeric_verification/{summary.feather,per_disease.feather,results.json}` (built by a committed helper script `science/tests/fixtures/numeric_verification/_build.py`, run once; commit the outputs)

**Interfaces:**
- Consumes: `ResolvedArtifact`, `PointerLocator`/`ColumnLocator` (Task 3).
- Produces: `read_scalar(resolved: ResolvedArtifact, locator) -> Decimal | ReaderError`.

Rules (§3/§4): JSON via `json.load(fh, parse_float=Decimal, parse_int=Decimal, parse_constant=_reject_nonfinite)`; resolve RFC-6901 pointer to exactly one node; non-scalar / string / bool / null → error. Feather via `pandas.read_feather(path, columns=[column])` (column-selective); `where` equality-filter; 0/>1 rows (or >1 with no `where`) → error; coerce cell via `.item()`, reject `bool`/`NaN`/`±inf`, `Decimal(str(x))`.

- [ ] **Step 1: Write the failing test** — JSON pointer hit returns exact `Decimal` (choose a value that a binary `float` round-trip would corrupt, e.g. `0.1` stored as `"0.1"` in JSON → `Decimal("0.1")`, assert `== Decimal("0.1")`); pointer miss / non-scalar / bool / null → `ReaderError`. Feather single-row hit; keyed-row hit; 0-match; >1-match; missing column; NaN cell → `ReaderError`.
- [ ] **Step 2: Run — expect fail.**
- [ ] **Step 3: Implement** `read_scalar` + `_json_pointer(doc, pointer)` (split on `/`, unescape `~1`/`~0`, index lists numerically) + `_reject_nonfinite`.
- [ ] **Step 4: Run — expect PASS.**
- [ ] **Step 5: Commit** — `git add -A science/tests/fixtures/numeric_verification && git commit -m "feat(numeric-verification): JSON/feather scalar reader with Decimal fidelity"`

---

### Task 8: Verification runner (`run_numeric_verification`)

**Files:**
- Modify: `science/src/science_tool/artifact_value_reader.py` (or a new `numeric_verification.py` runner — see note)
- Test: `science/tests/test_numeric_verification.py`

**Interfaces:**
- Consumes: `list[ClaimBinding]`, `list[BindingError]`, `resolve_artifact`, `read_scalar`, `compare_at_precision`.
- Produces: `run_numeric_verification(document, project_root, data_root, *, max_json_bytes, max_feather_bytes) -> tuple[list[LintIssue], dict[str,int]]` — the `LintIssue`s (one `warn` per `mismatch`/`error`, none for `verified`/`unverifiable`) and the coverage tally `{"verified","unverifiable","mismatch","error"}`.

Note: put the runner in a new `numeric_verification.py` (imports `LintIssue` from `prose_lint` lazily, like `detect_numeric_anchor` does, to avoid a cycle). Opaque locator → `unverifiable` (no I/O). `BindingError` → `error` (warn LintIssue at its line). Per binding: resolve → read → `compare_at_precision(parse_prose_literal(binding.value_text), value, binding.tolerance)`.

- [ ] **Step 1: Write the failing test** — a fixture doc binding to the Task-7 fixtures: one `verified` (no issue, coverage.verified=1), one `mismatch` (warn issue), one dangling-artifact `error` (warn issue), one `opaque` (`unverifiable`, no issue). Assert issue lines/messages, all `severity == "warn"`, and the coverage dict.
- [ ] **Step 2: Run — expect fail.**
- [ ] **Step 3: Implement** the runner.
- [ ] **Step 4: Run — expect PASS.**
- [ ] **Step 5: Commit** — `git commit -m "feat(numeric-verification): verification runner + coverage"`

---

### Task 9: Wire `numeric-verification` into `scan_root` (registry, coupling, coverage, config)

**Files:**
- Modify: `science/src/science_tool/prose_lint.py` (CHECKS, DEFAULT_SEVERITY, _DETECTORS, `detect_numeric_verification` wrapper, `couple_checks`, scan_root)
- Modify: `science/src/science_tool/project_config.py` (`ProseLintConfig.max_json_bytes`, `.max_feather_bytes`)
- Test: `science/tests/test_prose_lint.py`, `science/tests/test_project_config_prose_lint.py`

**Interfaces:**
- Produces: `couple_checks(selected: list[str]) -> list[str]` (if either of `numeric-anchor`/`numeric-verification` present, ensure both, order-stable); `detect_numeric_verification(path, *, strict=False, project_root=None, data_root=None, max_json_bytes=..., max_feather_bytes=...) -> list[LintIssue]`; `scan_root(...)` return dict gains `"coverage": {check: {...}}`.

- [ ] **Step 1: Write the failing test** — `scan_root(root, checks=["numeric-anchor"])` returns a result whose selected checks include `numeric-verification` (coupling) and whose `["coverage"]["numeric-verification"]` tallies the fixture project; `counts["numeric-verification"]` equals `mismatch+error` only. Config test: `ProseLintConfig(max_json_bytes=10)` round-trips; unknown field still rejected (`extra="forbid"`).
- [ ] **Step 2: Run — expect fail.**
- [ ] **Step 3: Implement** — add `"numeric-verification"` to `CHECKS`, `DEFAULT_SEVERITY` (`"warn"`), `_DETECTORS`; add `couple_checks` and call it on `selected` at `scan_root:783`; special-case `numeric-verification` in the scan loop to call `run_numeric_verification` and accumulate a `coverage` dict; return `{"counts", "hits", "coverage"}`; add the two `int` config fields with defaults `50*1024*1024` / `256*1024*1024`; forward them from `scan_root` params.
- [ ] **Step 4: Run — expect PASS** (plus full `tests/test_prose_lint.py`).
- [ ] **Step 5: Commit** — `git commit -m "feat(numeric-verification): scan_root wiring, coupling, coverage, config caps"`

---

### Task 10: CLI — coupling + coverage rendering

**Files:**
- Modify: `science/src/science_tool/prose_lint_cli.py`
- Test: `science/tests/test_prose_lint_cli.py`

**Interfaces:**
- Consumes: `couple_checks`, the `coverage` field.
- Produces: CLI applies `couple_checks` to the selected checks; `_render_table` prints a coverage line **even when there are no hits** (replacing the bare early-return at `prose_lint_cli.py:104`); JSON output includes `coverage`.

- [ ] **Step 1: Write the failing test** — invoke the CLI (via `CliRunner`) with `--check numeric-verification` on a fully-`verified` fixture: exit 0, stdout contains a coverage summary (e.g. `numeric-verification: 1 verified`), not just "no issues found". With a `mismatch` fixture under `--strict`: exit 1.
- [ ] **Step 2: Run — expect fail.**
- [ ] **Step 3: Implement** — apply `couple_checks(selected)` where checks are resolved; in `_render_table`, render coverage before the `if not result["hits"]` early return (or restructure so coverage always prints); include `coverage` in the JSON `payload`.
- [ ] **Step 4: Run — expect PASS.**
- [ ] **Step 5: Commit** — `git commit -m "feat(numeric-verification): CLI coupling and coverage output"`

---

### Task 11: Validation — coupling + coverage advisory

**Files:**
- Modify: `science/src/science_tool/validate/checks/prose_lints.py`
- Test: `science/tests/` (the validation check's test; mirror existing prose-lint validation test)

**Interfaces:**
- Consumes: `couple_checks`, `coverage`.
- Produces: validation runs the atomic pair; `mismatch`/`error` `warn` hits become detailed `Result`s (existing path at `prose_lints.py:139`); `coverage` is surfaced as a single **advisory** (`info`) `Result` per project, separate from `counts`.

- [ ] **Step 1: Write the failing test** — a fixture project with one `mismatch` binding produces a `warn` validation Result on that line; a fully-`verified` project produces the advisory coverage Result and **no** `warn`. Assert the coverage advisory does not go through the `counts` numeric compare.
- [ ] **Step 2: Run — expect fail.**
- [ ] **Step 3: Implement** — apply `couple_checks` where `configured_checks` is resolved; after the existing hit loop, append one advisory `Result` built from `lint_result.get("coverage", {})`.
- [ ] **Step 4: Run — expect PASS.**
- [ ] **Step 5: Commit** — `git commit -m "feat(numeric-verification): validation coupling and coverage advisory"`

---

### Task 12: Annotation adapter — detector-version bump

**Files:**
- Modify: `science/src/science_tool/annotation/sources/lint.py`
- Test: `science/tests/test_annotation_lint_source_numeric.py`

**Interfaces:** `DETECTOR_VERSIONS["numeric-anchor"]` bumped (suppression changes its output, so historical annotations must re-key). No new source — `numeric-verification` is not annotated in this cycle.

- [ ] **Step 1: Write the failing test** — assert `lint_source_name("numeric-anchor")` reflects the new version string; assert a document with a bound number yields no numeric-anchor annotation on that span (adapter suppression via the internal `parse_claim_bindings` from Task 5).
- [ ] **Step 2: Run — expect fail.**
- [ ] **Step 3: Implement** — bump `"numeric-anchor"` to `"v2026-07-18b"` (or dated to today). 
- [ ] **Step 4: Run — expect PASS.**
- [ ] **Step 5: Commit** — `git commit -m "chore(numeric-verification): bump numeric-anchor detector version"`

---

### Task 13: Documentation

**Files:**
- Modify: `docs/conventions/prose-lints.md`
- Test: none (doc) — but run `tests/test_command_docs.py`/`test_user_guide_docs.py` if they assert on this file.

- [ ] **Step 1:** Add a `## numeric-verification (structured numeric claims)` section: the `numeric_claims:` + `[^id]` authoring shape, the three locator forms (`pointer`/`column`+`where`/`opaque`), the four outcomes and their severities, the atomic-pair coupling note, the `%`/`opaque`→unverifiable and open-interval-boundary rules, and the `max_json_bytes`/`max_feather_bytes` config.
- [ ] **Step 2: Commit** — `git commit -m "docs(numeric-verification): document the check and binding syntax"`

---

### Task 14: Oracle + end-to-end acceptance

**Files:**
- Create: `science/tests/fixtures/numeric_verification/oracle.jsonl` (labeled per-outcome rows), fixture entities under `science/tests/fixtures/numeric_verification/entities/`
- Create: `science/tests/test_numeric_verification_oracle.py`

**Interfaces:** Consumes `scan_root`. Each oracle row: `{file, line, id, expected_outcome ∈ {verified,mismatch,unverifiable,error}, reason}`. Labels reflect **design**, never bent to the engine (Part A oracle discipline).

- [ ] **Step 1: Write the failing test** — build a fixture project (entities binding to committed feather/json across all outcomes incl. `opaque`, `%`, dangling, ambiguous-row, symlink-escape, orphan, duplicate); run `scan_root(root)`; assert each labeled row's outcome via `coverage` + hit lines. Also assert a bound claim draws no `numeric-anchor` finding (composition), and that unbound Part-A behavior is unchanged (a control ungrounded number still flags).
- [ ] **Step 2: Run — expect fail.**
- [ ] **Step 3:** Author fixtures + oracle rows to satisfy the design outcomes.
- [ ] **Step 4: Run — expect PASS**; then run the whole suite `uv run --frozen python -m pytest -q` and record any pre-existing unrelated failures (the two known doc-consistency tests) separately.
- [ ] **Step 5: Commit** — `git add -A science/tests/fixtures/numeric_verification && git commit -m "test(numeric-verification): labeled oracle and end-to-end acceptance"`

---

## Self-Review

- **Spec coverage:** §1 authoring → T3,T4; §2 schema → T3; §3 locator → T3,T7; grammar → T1; §4 verify/compare → T2,T6,T7,T8; §5 outcomes/severity/coverage/composition → T5,T8,T9,T10,T11; §6 modules → T1–T8; §7 config → T9; §8 error matrix → exercised across T3,T4,T6,T7,T8,T14; §9 testing → every task + T14; §10 deferred → not built (correct). All sections covered.
- **Type consistency:** `ParsedLiteral`, `ClaimBinding`, locator union, `ResolvedArtifact`/`ArtifactError`/`ReaderError`, and the `coverage` dict shape are pinned in Shared Types and used identically across tasks. Outcome strings `verified/mismatch/unverifiable/error` are the single vocabulary from T1 onward.
- **Placeholder scan:** the two large pydantic/reader implementations (T3, T7) are described by exact rules + full tests rather than full inline bodies; every other step carries runnable code. Flagged deliberately — the tests pin behavior precisely.
- **Ordering:** pure cores (T1–T5) before I/O (T6–T8) before wiring (T9–T12) before docs/oracle (T13–T14); each task ends with an independently testable deliverable.

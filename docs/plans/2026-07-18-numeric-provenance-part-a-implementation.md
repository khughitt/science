# Numeric-Claim Provenance Check — Part A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the paragraph-scoped `numeric-anchor` substring heuristic with a precision provenance check that classifies each numeric claim as NotClaim / Exempt / Anchored / Unanchored, existence-checks cited sources, and fires only on genuinely ungrounded numbers.

**Architecture:** A new pure core module `numeric_provenance.py` exposes `assess_numeric_claims(document_context, resolution_index, config) -> list[ClaimAssessment]`. The scanning layer builds a `DocumentContext` (parsed once) and a project-wide `ResolutionIndex` (built once) and hands both in. `detect_numeric_anchor` becomes a thin adapter that filters `Unanchored` assessments into `LintIssue`s, preserving every existing caller (validation check, CLI, annotation adapter).

**Tech Stack:** Python 3.12+, pydantic v2 (`science.yaml` schema), dataclasses (core types), pytest. No new dependencies.

**Design source:** `~/d/science/.worktrees/numeric-provenance-redesign/docs/plans/2026-07-18-numeric-provenance-check-design.md` (Part A). Part B (per-claim value binding + verifier) is **out of scope** for this plan — specified there, deferred to its own cycle.

## Global Constraints

- **Run everything from the science worktree root** `~/d/science/.worktrees/numeric-provenance-redesign/science/` via `uv run --frozen`. Tests: `uv run --frozen python -m pytest tests/<file> -v`.
- **Package path:** all source under `science/src/science_tool/`; all tests under `science/tests/`.
- **No AI-attribution trailer/footer** on any commit message (no `Co-Authored-By`, no "Generated with" line).
- **Docs use `~/d/…`** paths, never `/home/keith/…` or `/mnt/ssd/…`.
- **Structural masking rules are hardcoded** (mechanical, not a project knob) — matching the existing `_mask_numeric_identifier_spans` convention. Only `additional_anchor_patterns`, `spec_class_kinds`, and `provenance_fields` are new config knobs.
- **Marker syntax is fixed recognized syntax** (resolved open question — see Task 6), not a per-project token knob: stable tokens are required so templates and cross-project tooling agree.
- **Severity stays `info`** (strict → `warn`). Do not change default severity.
- **Existence checking may add new findings** — the rollout is intentionally *not* strictly monotonic (fabricated `task:t999` / `artifact:` paths that previously passed will now flag). This is expected; do not "fix" it by weakening existence checks.
- **TDD, frequent commits, DRY, YAGNI.** One failing test → minimal code → green → commit.

---

## File Structure

**New files**
- `science/src/science_tool/numeric_provenance.py` — pure core: `ClaimAssessment` types, `SourceCandidate`, `NumericProvenanceConfig`, `DocumentContext`, `ResolutionIndex`, `assess_numeric_claims`, and the four resolution-layer helpers. Sole owner of the assessment logic.
- `science/tests/test_numeric_provenance.py` — pure-unit tests, one class per resolution layer.
- `science/tests/test_numeric_provenance_oracle.py` — the materialized regression oracle + adversarial controls.
- `science/tests/fixtures/numeric_provenance_oracle.jsonl` — row-level labeled dataset (generated in Task 13).

**Modified files**
- `science/src/science_tool/project_config.py` — add `additional_anchor_patterns`, `spec_class_kinds`, `provenance_fields` to `ProseLintConfig`.
- `science/src/science_tool/prose_lint.py` — rewrite `detect_numeric_anchor` as a thin adapter; delete `_paper_note_has_source_context` / `_interpretation_has_artifact_context` (subsumed); thread `DocumentContext` + `ResolutionIndex` through `scan_root`.
- `science/src/science_tool/validate/checks/prose_lints.py` — merge `additional_anchor_patterns`; forward new config.
- `science/src/science_tool/prose_lint_cli.py` — same merge/forward.
- `science/src/science_tool/annotation/sources/lint.py` — build context/index for numeric-anchor; bump `DETECTOR_VERSIONS["numeric-anchor"]`.
- `science/docs/conventions/prose-lints.md` — document the four outcomes + marker authoring.

**Interface contract (locked — later tasks depend on these exact names/types):**

```python
# numeric_provenance.py

@dataclass(frozen=True)
class NumericClaim:
    value: str          # the matched literal, e.g. "7.94" or "60%"
    line: int           # 1-based
    col: int            # 1-based
    paragraph_id: int
    section_id: int

@dataclass(frozen=True)
class SourceCandidate:
    reference: str                 # e.g. "task:t064", "Foo2024", "results/x.json"
    origin: str                    # "frontmatter" | "title" | "body"
    field_or_line: str             # "source_refs" | "L42" | "title"
    resolution_status: str         # "resolved" | "unresolved"

@dataclass(frozen=True)
class NotClaim:
    claim: NumericClaim
    reason: str

@dataclass(frozen=True)
class Exempt:
    claim: NumericClaim
    reason: str
    scope: str                     # "document" | "section" | "block"

@dataclass(frozen=True)
class Anchored:
    claim: NumericClaim
    candidates: tuple[SourceCandidate, ...]   # >=1, all resolution_status == "resolved"

@dataclass(frozen=True)
class Unanchored:
    claim: NumericClaim
    kind_hint: str | None          # "stipulated" for spec-class kinds, else None
    local_evidence: bool           # True if a generic anchor_pattern suppressed nothing but was present

ClaimAssessment = NotClaim | Exempt | Anchored | Unanchored

@dataclass(frozen=True)
class NumericProvenanceConfig:
    anchor_patterns: tuple[str, ...]      # already-merged effective patterns
    spec_class_kinds: frozenset[str]
    provenance_fields: tuple[str, ...]

def assess_numeric_claims(
    document: "DocumentContext",
    index: "ResolutionIndex",
    config: NumericProvenanceConfig,
) -> list[ClaimAssessment]: ...
```

---

### Task 1: Config surface — additive vocabulary + new knobs

**Files:**
- Modify: `science/src/science_tool/project_config.py:77-86` (`ProseLintConfig`)
- Test: `science/tests/test_project_config_prose_lint.py`

**Interfaces:**
- Produces: `ProseLintConfig.additional_anchor_patterns: list[str]`, `.spec_class_kinds: list[str]`, `.provenance_fields: list[str]`, and module constants `DEFAULT_SPEC_CLASS_KINDS`, `DEFAULT_PROVENANCE_FIELDS`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_project_config_prose_lint.py (append)
def test_additive_anchor_patterns_default_empty(tmp_path):
    (tmp_path / "science.yaml").write_text("name: demo\nprose_lint: {}\n")
    from science_tool.project_config import load_project_config
    config = load_project_config(tmp_path)
    assert config.prose_lint.additional_anchor_patterns == []
    assert config.prose_lint.spec_class_kinds == ["pre-registration", "plan"]
    assert config.prose_lint.provenance_fields == ["source_refs", "task_links", "input"]

def test_additional_anchor_patterns_are_additive(tmp_path):
    (tmp_path / "science.yaml").write_text(
        "name: demo\nprose_lint:\n  anchor_patterns: ['task:']\n"
        "  additional_anchor_patterns: ['paper:', 'cite:']\n"
    )
    from science_tool.project_config import load_project_config
    config = load_project_config(tmp_path)
    assert config.prose_lint.anchor_patterns == ["task:"]
    assert config.prose_lint.additional_anchor_patterns == ["paper:", "cite:"]
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run --frozen python -m pytest tests/test_project_config_prose_lint.py::test_additive_anchor_patterns_default_empty -v`
Expected: FAIL — `AttributeError: 'ProseLintConfig' object has no attribute 'additional_anchor_patterns'`

- [ ] **Step 3: Add the fields**

```python
# project_config.py — after DEFAULT_ANCHOR_PATTERNS
DEFAULT_SPEC_CLASS_KINDS: list[str] = ["pre-registration", "plan"]
DEFAULT_PROVENANCE_FIELDS: list[str] = ["source_refs", "task_links", "input"]


class ProseLintConfig(BaseModel):
    """Configuration for `science prose lint`."""

    model_config = ConfigDict(extra="forbid")

    enabled_checks: list[str] | None = None
    anchor_patterns: list[str] = Field(default_factory=lambda: list(DEFAULT_ANCHOR_PATTERNS))
    # Additive vocabulary merged on top of whatever `anchor_patterns` resolves to.
    # Unlike `anchor_patterns` (a full-override escape hatch), this always applies,
    # so shared vocabulary reaches projects that have overridden anchor_patterns.
    additional_anchor_patterns: list[str] = Field(default_factory=list)
    spec_class_kinds: list[str] = Field(default_factory=lambda: list(DEFAULT_SPEC_CLASS_KINDS))
    provenance_fields: list[str] = Field(default_factory=lambda: list(DEFAULT_PROVENANCE_FIELDS))
    exclude_paths: list[str] = Field(default_factory=list)
    short_form_ids_deny: list[str] = Field(default_factory=list)
    bare_author_year_deny: list[str] = Field(default_factory=list)
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run --frozen python -m pytest tests/test_project_config_prose_lint.py -v`
Expected: PASS (all, including the two new tests)

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/project_config.py science/tests/test_project_config_prose_lint.py
git commit -m "feat(prose-lint): add additive anchor patterns + spec-class/provenance config"
```

---

### Task 2: Discriminated assessment types + resolved config

**Files:**
- Create: `science/src/science_tool/numeric_provenance.py`
- Test: `science/tests/test_numeric_provenance.py`

**Interfaces:**
- Produces: `NumericClaim`, `SourceCandidate`, `NotClaim`, `Exempt`, `Anchored`, `Unanchored`, `ClaimAssessment`, `NumericProvenanceConfig` (exactly as in the locked contract above).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_numeric_provenance.py
from science_tool.numeric_provenance import (
    Anchored, Exempt, NotClaim, NumericClaim, NumericProvenanceConfig,
    SourceCandidate, Unanchored,
)


def test_types_construct_and_are_frozen():
    claim = NumericClaim(value="7.94", line=42, col=3, paragraph_id=2, section_id=1)
    cand = SourceCandidate(reference="task:t064", origin="frontmatter",
                           field_or_line="source_refs", resolution_status="resolved")
    assert Anchored(claim=claim, candidates=(cand,)).candidates[0].resolution_status == "resolved"
    assert Exempt(claim=claim, reason="stipulated", scope="section").scope == "section"
    assert Unanchored(claim=claim, kind_hint="stipulated", local_evidence=False).kind_hint == "stipulated"
    assert NotClaim(claim=claim, reason="hardware-id").reason == "hardware-id"
    cfg = NumericProvenanceConfig(anchor_patterns=("task:",), spec_class_kinds=frozenset({"plan"}),
                                  provenance_fields=("source_refs",))
    assert "task:" in cfg.anchor_patterns
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run --frozen python -m pytest tests/test_numeric_provenance.py::test_types_construct_and_are_frozen -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'science_tool.numeric_provenance'`

- [ ] **Step 3: Create the module skeleton with the types**

```python
# science/src/science_tool/numeric_provenance.py
"""Numeric-claim provenance assessment (Part A of the numeric-provenance redesign).

Pure core: `assess_numeric_claims(document, index, config)` classifies each numeric
claim in a document's body prose as exactly one of NotClaim / Exempt / Anchored /
Unanchored. The scanning layer builds the `DocumentContext` and `ResolutionIndex`
and passes them in, keeping this module free of disk I/O.

See docs/plans/2026-07-18-numeric-provenance-check-design.md (Part A).
"""

from __future__ import annotations

from dataclasses import dataclass


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
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run --frozen python -m pytest tests/test_numeric_provenance.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/numeric_provenance.py science/tests/test_numeric_provenance.py
git commit -m "feat(numeric-provenance): add discriminated ClaimAssessment types"
```

---

### Task 3: DocumentContext — parsed-once document model

**Files:**
- Modify: `science/src/science_tool/numeric_provenance.py`
- Test: `science/tests/test_numeric_provenance.py`

**Interfaces:**
- Consumes: `science_model.frontmatter.split_frontmatter`, `science_tool.markdown_utils.frontmatter_span`, `is_fence_line`.
- Produces:
  ```python
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
  def build_document_context(path: Path) -> DocumentContext | None: ...
  ```
  `section_id_per_line` maps each body line to the id of the innermost section it belongs to; section scope ends at the next heading of **equal-or-higher** level (fail-closed).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_numeric_provenance.py (append)
from pathlib import Path
from science_tool.numeric_provenance import build_document_context


def _doc(tmp_path: Path, body: str, frontmatter: str = "") -> Path:
    p = tmp_path / "doc.md"
    p.write_text(f"---\n{frontmatter}\n---\n{body}" if frontmatter else body)
    return p


def test_document_context_parses_kind_title_paragraphs(tmp_path):
    path = _doc(tmp_path, "# Results\n\nThe effect was 7.94 fold.\n\nAnother para 12.3.\n",
                frontmatter="kind: interpretation")
    ctx = build_document_context(path)
    assert ctx.kind == "interpretation"
    assert ctx.title == "Results"
    # the two body paragraphs land in distinct paragraph ids
    pid_first = ctx.paragraph_id_per_line[ctx.lines.index("The effect was 7.94 fold.") + 1]
    pid_second = ctx.paragraph_id_per_line[ctx.lines.index("Another para 12.3.") + 1]
    assert pid_first != pid_second


def test_section_scope_is_fail_closed_at_equal_or_higher_heading(tmp_path):
    body = ("## Decision thresholds\n\nUse alpha 0.05.\n\n"
            "## Results\n\nWe saw 7.94 fold.\n")
    path = _doc(tmp_path, body, frontmatter="kind: plan")
    ctx = build_document_context(path)
    sid_alpha = ctx.section_id_per_line[ctx.lines.index("Use alpha 0.05.") + 1]
    sid_result = ctx.section_id_per_line[ctx.lines.index("We saw 7.94 fold.") + 1]
    assert sid_alpha != sid_result   # the second H2 closes the first section
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run --frozen python -m pytest tests/test_numeric_provenance.py -k document_context -v`
Expected: FAIL — `ImportError: cannot import name 'build_document_context'`

- [ ] **Step 3: Implement DocumentContext + builder**

```python
# numeric_provenance.py (add imports + code)
import re
from pathlib import Path

from science_model.frontmatter import split_frontmatter
from science_tool.markdown_utils import frontmatter_span, is_fence_line

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
_TITLE_RE = re.compile(r"^#\s+(.+?)\s*$")


@dataclass(frozen=True)
class Section:
    section_id: int
    heading_level: int
    start_line: int
    end_line: int


@dataclass(frozen=True)
class DocumentContext:
    path: Path
    kind: str | None
    frontmatter: dict
    title: str | None
    body_start: int
    lines: tuple[str, ...]
    paragraph_id_per_line: tuple[int, ...]
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
    sections: list[Section] = []
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
            sections.append(Section(section_id=sid, heading_level=level, start_line=idx, end_line=idx))
        section_id_per_line[idx] = stack[-1][1] if stack else 0

    # Fix up each section's end_line to the last line it owns.
    end_by_id: dict[int, int] = {}
    for idx in range(1, n + 1):
        end_by_id[section_id_per_line[idx]] = idx
    sections = tuple(
        Section(s.section_id, s.heading_level, s.start_line, end_by_id.get(s.section_id, s.start_line))
        for s in sections
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
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run --frozen python -m pytest tests/test_numeric_provenance.py -k "document_context or section_scope" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/numeric_provenance.py science/tests/test_numeric_provenance.py
git commit -m "feat(numeric-provenance): add DocumentContext with fail-closed sections"
```

---

### Task 4: ResolutionIndex — existence oracle

**Files:**
- Modify: `science/src/science_tool/numeric_provenance.py`
- Test: `science/tests/test_numeric_provenance.py`

**Interfaces:**
- Consumes (all cheap, no graph build): `refs._load_task_ids`, `refs._load_entity_index`, `bibliography.load_bib_keys`, `refs._load_doi_corpus`, `refs._load_pmid_corpus`, `data_root.resolve_data_root`.
- Produces:
  ```python
  @dataclass(frozen=True)
  class ResolutionIndex:
      project_root: Path
      task_numbers: frozenset[str]     # bare, e.g. {"64"}
      entity_ids: frozenset[str]       # canonical, e.g. {"dataset:xyz","task:t064"}
      bib_keys: frozenset[str]
      doi_corpus: frozenset[str]
      pmid_corpus: frozenset[str]
      data_root: Path
      def resolve(self, reference: str) -> bool: ...
  def build_resolution_index(project_root: Path) -> ResolutionIndex: ...
  ```
- `resolve()` recognizes: `task:tNNN`/`tNNN`, typed `<kind>:<slug>` entity ids, `cite:key`/`[@key]`, bare DOI/PMID, `http(s)://…` URLs (well-formed → resolved; remote existence not checked in Part A), and relative artifact paths (`(project_root / ref).is_file()` or `(data_root / ref).is_file()`).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_numeric_provenance.py (append)
from science_tool.numeric_provenance import build_resolution_index


def _project(tmp_path: Path) -> Path:
    (tmp_path / "science.yaml").write_text("name: demo\n")
    (tmp_path / "tasks").mkdir()
    (tmp_path / "tasks" / "active.md").write_text("## [t064] Do the thing\n\nbody\n")
    (tmp_path / "entities" / "datasets").mkdir(parents=True)
    (tmp_path / "entities" / "datasets" / "xyz.md").write_text("---\nid: dataset:xyz\nkind: dataset\n---\n\nbody\n")
    (tmp_path / "papers").mkdir()
    (tmp_path / "papers" / "references.bib").write_text("@article{Foo2024, title={T}, year={2024}}\n")
    (tmp_path / "results").mkdir()
    (tmp_path / "results" / "qap.json").write_text("{}")
    return tmp_path


def test_resolution_index_resolves_real_refs_and_rejects_fakes(tmp_path):
    idx = build_resolution_index(_project(tmp_path))
    assert idx.resolve("task:t064") is True
    assert idx.resolve("task:t999") is False        # finding 5
    assert idx.resolve("dataset:xyz") is True
    assert idx.resolve("dataset:nope") is False
    assert idx.resolve("[@Foo2024]") is True
    assert idx.resolve("cite:Foo2024") is True
    assert idx.resolve("[@Ghost2099]") is False
    assert idx.resolve("results/qap.json") is True
    assert idx.resolve("results/invented.json") is False   # finding 5
    assert idx.resolve("https://example.org/x") is True
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run --frozen python -m pytest tests/test_numeric_provenance.py -k resolution_index -v`
Expected: FAIL — `ImportError: cannot import name 'build_resolution_index'`

- [ ] **Step 3: Implement the index**

```python
# numeric_provenance.py (add)
_TASK_REF_RE = re.compile(r"^(?:task:)?t(\d{2,})$")
_TYPED_REF_RE = re.compile(r"^[a-z][a-z0-9_-]*:[A-Za-z0-9][A-Za-z0-9_.-]*$")
_CITE_RE = re.compile(r"^(?:cite:|\[@)([A-Za-z][A-Za-z0-9_:.-]*)\]?$")
_DOI_RE = re.compile(r"^(?:doi:)?10\.\d{4,9}/\S+$", re.IGNORECASE)
_PMID_RE = re.compile(r"^(?:pmid:)?\d{5,9}$", re.IGNORECASE)
_URL_RE = re.compile(r"^https?://\S+$", re.IGNORECASE)


@dataclass(frozen=True)
class ResolutionIndex:
    project_root: Path
    task_numbers: frozenset[str]
    entity_ids: frozenset[str]
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
            return m.group(1).lstrip("0").zfill(2) in self.task_numbers or m.group(1) in self.task_numbers
        if _URL_RE.match(ref):
            return True  # well-formed; remote existence is Part B's problem
        m = _CITE_RE.match(ref)
        if m:
            return m.group(1) in self.bib_keys
        if _DOI_RE.match(ref):
            return _normalize(ref).split("doi:")[-1] in self.doi_corpus
        if _PMID_RE.match(ref):
            return ref.split(":")[-1] in self.pmid_corpus
        if _TYPED_REF_RE.match(ref):
            return ref in self.entity_ids
        # Treat anything else as a candidate artifact path.
        for base in (self.project_root, self.data_root):
            if (base / ref).is_file():
                return True
        return False


def _normalize(token: str) -> str:
    return token.strip().lower()


def build_resolution_index(project_root: Path) -> ResolutionIndex:
    from science_tool import refs
    from science_tool.bibliography import load_bib_keys
    from science_tool.data_root import resolve_data_root

    root = project_root.resolve()
    task_numbers = {n.lstrip("0").zfill(2) for n in refs._load_task_ids(root)} | set(refs._load_task_ids(root))
    return ResolutionIndex(
        project_root=root,
        task_numbers=frozenset(task_numbers),
        entity_ids=frozenset(refs._load_entity_index(root)),
        bib_keys=frozenset(load_bib_keys(root)),
        doi_corpus=frozenset(_normalize(d) for d in refs._load_doi_corpus(root)),
        pmid_corpus=frozenset(refs._load_pmid_corpus(root)),
        data_root=resolve_data_root(root),
    )
```

> Implementer note: confirm the exact return shape of `refs._load_task_ids` (bare numeric strings like `"64"`), `refs._load_entity_index` (canonical `"kind:slug"`), `refs._load_doi_corpus`/`_load_pmid_corpus` before wiring — read `refs.py` and adjust the `_normalize`/zfill handling to match. The test above is the contract.

- [ ] **Step 4: Run to verify it passes**

Run: `uv run --frozen python -m pytest tests/test_numeric_provenance.py -k resolution_index -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/numeric_provenance.py science/tests/test_numeric_provenance.py
git commit -m "feat(numeric-provenance): add ResolutionIndex existence oracle"
```

---

### Task 5: NotClaim structural layer

**Files:**
- Modify: `science/src/science_tool/numeric_provenance.py`
- Test: `science/tests/test_numeric_provenance.py`

**Interfaces:**
- Produces: `classify_structural(value: str, line: str, col: int) -> str | None` — returns a `reason` slug when the number is structural (→ `NotClaim`), else `None`. Reasons: `"hardware-id"`, `"accession"`, `"license-version"`, `"slug-digit"`, `"config-line"`, `"file-size"`. **Model dimensions and file sizes are context-gated**, not blanket-masked.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_numeric_provenance.py (append)
from science_tool.numeric_provenance import classify_structural


def test_structural_masks_hardware_and_accession_and_license():
    assert classify_structural("3070", "trained on an RTX 3070 GPU", 24) == "hardware-id"
    assert classify_structural("6000", "sequenced on NovaSeq 6000", 20) == "hardware-id"
    assert classify_structural("90084", "association GCST90084 was used", 14) == "accession"
    assert classify_structural("4.0", "released under CC-BY-4.0 terms", 20) == "license-version"


def test_structural_is_context_gated_for_sizes_not_facts():
    # a download size is structural; a genome size is a factual claim
    assert classify_structural("516.9", "the 516.9 MB download completed", 8) == "file-size"
    assert classify_structural("3.2", "the human genome is 3.2 Gb", 20) is None
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run --frozen python -m pytest tests/test_numeric_provenance.py -k structural -v`
Expected: FAIL — `ImportError: cannot import name 'classify_structural'`

- [ ] **Step 3: Implement narrow, context-gated structural classification**

```python
# numeric_provenance.py (add)
_HARDWARE_CONTEXT_RE = re.compile(
    r"\b(RTX|GTX|GPU|CPU|NovaSeq|HiSeq|NextSeq|MiSeq|Tesla|A100|H100|V100)\b", re.IGNORECASE
)
_ACCESSION_PREFIX_RE = re.compile(r"\bGCST\d+\b")
_LICENSE_RE = re.compile(r"\b(?:CC-BY|CC-BY-SA|CC0|GPL|MIT|Apache)-?\d")
_FILE_SIZE_RE = re.compile(r"\d[\d.,]*\s?(?:[KMGT]i?B)\b.*\b(?:download|file|upload|payload|archive|dump)\b",
                           re.IGNORECASE)
_SIZE_UNIT_AFTER_RE = re.compile(r"^\s*(?:[KMGT]i?B)\b", re.IGNORECASE)


def classify_structural(value: str, line: str, col: int) -> str | None:
    """Return a NotClaim reason for a clearly structural number, else None.

    Narrow by design: only tokens that are mechanically not quantitative claims.
    Model dimensions / file sizes are context-gated, never blanket-masked, so a
    factual size like "3.2 Gb genome" stays a claim.
    """
    window = line[max(0, col - 1 - 24): min(len(line), col - 1 + len(value) + 24)]
    if _HARDWARE_CONTEXT_RE.search(window):
        return "hardware-id"
    if _ACCESSION_PREFIX_RE.search(window):
        return "accession"
    if _LICENSE_RE.search(window):
        return "license-version"
    if _FILE_SIZE_RE.search(window):
        return "file-size"
    return None
```

> Implementer note: DOI/PMID/version/compact-ID masking already lives in `prose_lint._mask_numeric_identifier_spans` and runs before the claim regex; do **not** duplicate it here. This layer adds only the *new* narrow categories from the design that the existing masking misses, plus the context-gating. Slug-digit and config-line reasons are reserved for cases the existing masking does not already cover — add them only when a fixture demonstrates a real miss (YAGNI).

- [ ] **Step 4: Run to verify it passes**

Run: `uv run --frozen python -m pytest tests/test_numeric_provenance.py -k structural -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/numeric_provenance.py science/tests/test_numeric_provenance.py
git commit -m "feat(numeric-provenance): add narrow context-gated structural classification"
```

---

### Task 6: Exempt (stipulated marker) layer

**Files:**
- Modify: `science/src/science_tool/numeric_provenance.py`
- Test: `science/tests/test_numeric_provenance.py`

**Resolved open questions (locked here):**
- **Marker syntax (fixed, not a config knob):**
  - Document-level: frontmatter `stipulated: true` — reserved for pure-spec docs (no empirical numbers in the body). Producing `Exempt(scope="document")`.
  - Section-level: an HTML comment `<!-- stipulated -->` on its own line immediately under a heading marks that heading's section; scope is **fail-closed** (ends at the next equal-or-higher heading), reusing `DocumentContext.sections`. Producing `Exempt(scope="section")`.
  - Block-level: a fenced pair `<!-- stipulated:start -->` … `<!-- stipulated:end -->` marks the lines between them (for mixed empirical/parameter sections). Producing `Exempt(scope="block")`.
- HTML comments are invisible in rendered markdown, greppable, and stable across projects — hence hardcoded, matching Global Constraints.

**Interfaces:**
- Produces:
  ```python
  @dataclass(frozen=True)
  class MarkerScope:
      scope: str                 # "document" | "section" | "block"
      covered_lines: frozenset[int]   # empty when scope == "document"
      whole_document: bool
  def compute_marker_scopes(document: DocumentContext) -> tuple[MarkerScope, ...]: ...
  def marked_scope_for_line(scopes: tuple[MarkerScope, ...], line: int) -> str | None: ...
  ```

- [ ] **Step 1: Write the failing test**

```python
# tests/test_numeric_provenance.py (append)
from science_tool.numeric_provenance import compute_marker_scopes, marked_scope_for_line


def test_document_marker_covers_whole_body(tmp_path):
    path = _doc(tmp_path, "The alpha is 0.05 and power 0.8.\n", frontmatter="kind: plan\nstipulated: true")
    ctx = build_document_context(path)
    scopes = compute_marker_scopes(ctx)
    line = ctx.lines.index("The alpha is 0.05 and power 0.8.") + 1
    assert marked_scope_for_line(scopes, line) == "document"


def test_section_marker_is_fail_closed(tmp_path):
    body = ("## Decision thresholds\n<!-- stipulated -->\n\nUse alpha 0.05.\n\n"
            "## Results\n\nWe saw 7.94 fold.\n")
    path = _doc(tmp_path, body, frontmatter="kind: plan")
    ctx = build_document_context(path)
    scopes = compute_marker_scopes(ctx)
    assert marked_scope_for_line(scopes, ctx.lines.index("Use alpha 0.05.") + 1) == "section"
    assert marked_scope_for_line(scopes, ctx.lines.index("We saw 7.94 fold.") + 1) is None


def test_block_marker_covers_only_fenced_lines(tmp_path):
    body = ("We saw 7.94 fold.\n\n<!-- stipulated:start -->\nalpha 0.05\n<!-- stipulated:end -->\n\nAnd 3.1 more.\n")
    path = _doc(tmp_path, body, frontmatter="kind: interpretation")
    ctx = build_document_context(path)
    scopes = compute_marker_scopes(ctx)
    assert marked_scope_for_line(scopes, ctx.lines.index("alpha 0.05") + 1) == "block"
    assert marked_scope_for_line(scopes, ctx.lines.index("We saw 7.94 fold.") + 1) is None
    assert marked_scope_for_line(scopes, ctx.lines.index("And 3.1 more.") + 1) is None
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run --frozen python -m pytest tests/test_numeric_provenance.py -k marker -v`
Expected: FAIL — `ImportError: cannot import name 'compute_marker_scopes'`

- [ ] **Step 3: Implement marker parsing + scope**

```python
# numeric_provenance.py (add)
_SECTION_MARKER_RE = re.compile(r"^\s*<!--\s*stipulated\s*-->\s*$")
_BLOCK_START_RE = re.compile(r"^\s*<!--\s*stipulated:start\s*-->\s*$")
_BLOCK_END_RE = re.compile(r"^\s*<!--\s*stipulated:end\s*-->\s*$")


@dataclass(frozen=True)
class MarkerScope:
    scope: str
    covered_lines: frozenset[int]
    whole_document: bool


def compute_marker_scopes(document: DocumentContext) -> tuple[MarkerScope, ...]:
    scopes: list[MarkerScope] = []
    fm = document.frontmatter
    if isinstance(fm, dict) and fm.get("stipulated") is True:
        scopes.append(MarkerScope(scope="document", covered_lines=frozenset(), whole_document=True))
        return tuple(scopes)   # document flag subsumes all finer markers

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
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run --frozen python -m pytest tests/test_numeric_provenance.py -k marker -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/numeric_provenance.py science/tests/test_numeric_provenance.py
git commit -m "feat(numeric-provenance): add stipulated-marker scoping (doc/section/block)"
```

---

### Task 7: Anchored layer — entity-scoped provenance (existence-checked)

**Files:**
- Modify: `science/src/science_tool/numeric_provenance.py`
- Test: `science/tests/test_numeric_provenance.py`

**Resolved open question (unification set, locked):** entity-scoped candidates are drawn from exactly —
1. frontmatter fields in `config.provenance_fields` (default `source_refs`, `task_links`, `input`), each list entry or scalar a candidate;
2. paper-note identity (path under `entities/papers` **or** `kind: paper`): `source_refs` entries, and `doi`/`pmid`/`url`/`bibkey` scalars;
3. interpretation identity (`kind: interpretation`): `artifact` and `artifacts` (scalar or list);
4. an owning task named in the title (e.g. `# t064 — …` or `## [t064] …`).

Every candidate is existence-checked via `index.resolve`. `related` is **excluded**. This unifies and replaces `_paper_note_has_source_context` and `_interpretation_has_artifact_context`.

**Interfaces:**
- Produces: `entity_source_candidates(document: DocumentContext, index: ResolutionIndex, config: NumericProvenanceConfig) -> tuple[SourceCandidate, ...]` — all candidates with their `resolution_status` filled in. An entity is entity-anchored iff at least one candidate resolves.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_numeric_provenance.py (append)
from science_tool.numeric_provenance import NumericProvenanceConfig, entity_source_candidates

_CFG = NumericProvenanceConfig(
    anchor_patterns=("task:", r"\[@"),
    spec_class_kinds=frozenset({"pre-registration", "plan"}),
    provenance_fields=("source_refs", "task_links", "input"),
)


def test_frontmatter_provenance_resolves(tmp_path):
    idx = build_resolution_index(_project(tmp_path))
    path = _doc(tmp_path, "The effect was 7.94 fold.\n",
                frontmatter="kind: interpretation\nsource_refs:\n  - task:t064")
    ctx = build_document_context(path)
    cands = entity_source_candidates(ctx, idx, _CFG)
    assert any(c.reference == "task:t064" and c.resolution_status == "resolved" for c in cands)


def test_fabricated_task_ref_does_not_anchor(tmp_path):
    idx = build_resolution_index(_project(tmp_path))
    path = _doc(tmp_path, "The effect was 7.94 fold.\n",
                frontmatter="kind: interpretation\nsource_refs:\n  - task:t999")
    ctx = build_document_context(path)
    cands = entity_source_candidates(ctx, idx, _CFG)
    assert all(c.resolution_status == "unresolved" for c in cands)   # finding 5


def test_interpretation_artifact_existence_checked(tmp_path):
    idx = build_resolution_index(_project(tmp_path))
    good = _doc(tmp_path, "Value 7.94.\n", frontmatter="kind: interpretation\nartifact: results/qap.json")
    assert any(c.resolution_status == "resolved" for c in entity_source_candidates(
        build_document_context(good), idx, _CFG))
    bad = tmp_path / "bad.md"
    bad.write_text("---\nkind: interpretation\nartifact: results/invented.json\n---\nValue 7.94.\n")
    assert all(c.resolution_status == "unresolved" for c in entity_source_candidates(
        build_document_context(bad), idx, _CFG))


def test_related_is_excluded(tmp_path):
    idx = build_resolution_index(_project(tmp_path))
    path = _doc(tmp_path, "Value 7.94.\n", frontmatter="kind: interpretation\nrelated:\n  - task:t064")
    cands = entity_source_candidates(build_document_context(path), idx, _CFG)
    assert all(c.reference != "task:t064" for c in cands)   # finding 2 (related != source)
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run --frozen python -m pytest tests/test_numeric_provenance.py -k "provenance or artifact or related" -v`
Expected: FAIL — `ImportError: cannot import name 'entity_source_candidates'`

- [ ] **Step 3: Implement entity-scoped candidate extraction**

```python
# numeric_provenance.py (add)
_TITLE_TASK_RE = re.compile(r"\bt(\d{2,})\b")


def _as_refs(value) -> list[str]:
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    if isinstance(value, list):
        return [v.strip() for v in value if isinstance(v, str) and v.strip()]
    return []


def entity_source_candidates(
    document: DocumentContext, index: ResolutionIndex, config: NumericProvenanceConfig
) -> tuple[SourceCandidate, ...]:
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

    is_paper = str(fm.get("kind")) == "paper" or _is_papers_path(document.path) \
        or str(fm.get("id", "")).startswith("paper:")
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


def _is_papers_path(path: Path) -> bool:
    parts = path.parts
    return any(left == "entities" and right == "papers" for left, right in zip(parts, parts[1:]))
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run --frozen python -m pytest tests/test_numeric_provenance.py -k "provenance or artifact or related" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/numeric_provenance.py science/tests/test_numeric_provenance.py
git commit -m "feat(numeric-provenance): add existence-checked entity-scoped anchoring"
```

---

### Task 8: Anchored layer — local (paragraph-scoped) references + anchor_evidence

**Files:**
- Modify: `science/src/science_tool/numeric_provenance.py`
- Test: `science/tests/test_numeric_provenance.py`

**Resolved open question (locked):** local anchor scope is the **paragraph** (the tighter, safer default — directly serves finding 2). A resolvable body reference (`task:tNNN`, `[@key]`, `cite:key`, `dataset:slug`, `[[wiki]]`, an artifact path) anchors only its own paragraph. A generic `config.anchor_patterns` regex match is weak `anchor_evidence`: it suppresses that paragraph's finding but yields **no `SourceCandidate`** and never clears entity-wide.

**Interfaces:**
- Produces:
  ```python
  def local_candidates_for_paragraph(paragraph_text: str, index: ResolutionIndex) -> tuple[SourceCandidate, ...]: ...
  def paragraph_has_anchor_evidence(paragraph_text: str, anchor_patterns: tuple[str, ...]) -> bool: ...
  ```

- [ ] **Step 1: Write the failing test**

```python
# tests/test_numeric_provenance.py (append)
from science_tool.numeric_provenance import (
    local_candidates_for_paragraph, paragraph_has_anchor_evidence,
)


def test_local_body_ref_resolves_only_when_it_exists(tmp_path):
    idx = build_resolution_index(_project(tmp_path))
    good = local_candidates_for_paragraph("The effect (task:t064) was 7.94 fold.", idx)
    assert any(c.reference == "task:t064" and c.resolution_status == "resolved" for c in good)
    bad = local_candidates_for_paragraph("The effect (task:t999) was 7.94 fold.", idx)
    assert all(c.resolution_status == "unresolved" for c in bad)


def test_generic_anchor_pattern_is_evidence_not_candidate():
    assert paragraph_has_anchor_evidence("see config/thresholds.yaml for 0.05", (r"config/",)) is True
    assert local_candidates_for_paragraph("see config/thresholds.yaml for 0.05",
                                           build_resolution_index) == ()  # no typed ref => no candidate
```

> Note: the second assertion's second call is illustrative — in the real test pass a built index; a paragraph with only `config/` yields no typed candidates.

- [ ] **Step 2: Run to verify it fails**

Run: `uv run --frozen python -m pytest tests/test_numeric_provenance.py -k "local_body or anchor_pattern" -v`
Expected: FAIL — `ImportError: cannot import name 'local_candidates_for_paragraph'`

- [ ] **Step 3: Implement local candidate + evidence detection**

```python
# numeric_provenance.py (add)
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
    out: list[SourceCandidate] = []
    for m in _BODY_REF_RE.finditer(paragraph_text):
        ref = m.group(0)
        # [[wiki]] links are topical, not sources — treat as evidence, not candidate.
        if ref.startswith("[["):
            continue
        out.append(SourceCandidate(
            reference=ref, origin="body", field_or_line="paragraph",
            resolution_status="resolved" if index.resolve(ref) else "unresolved",
        ))
    return tuple(out)


def paragraph_has_anchor_evidence(paragraph_text: str, anchor_patterns: tuple[str, ...]) -> bool:
    if not anchor_patterns:
        return False
    return re.search("|".join(anchor_patterns), paragraph_text) is not None
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run --frozen python -m pytest tests/test_numeric_provenance.py -k "local_body or anchor_pattern" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/numeric_provenance.py science/tests/test_numeric_provenance.py
git commit -m "feat(numeric-provenance): add paragraph-scoped local anchoring + anchor_evidence"
```

---

### Task 9: `assess_numeric_claims` orchestrator (resolution order + Unanchored)

**Files:**
- Modify: `science/src/science_tool/numeric_provenance.py`
- Test: `science/tests/test_numeric_provenance.py`

**Interfaces:**
- Consumes: everything from Tasks 2–8, plus the claim-extraction regexes from `prose_lint.py` (reused, not duplicated — import `_NUMERIC_CLAIM_RE`, `_BARE_YEAR_RE`, `_CROSS_REFERENCE_RE`, `_mask_numeric_identifier_spans`, and the header/list/table gates).
- Produces: `assess_numeric_claims(document, index, config) -> list[ClaimAssessment]` returning **all** assessments in document order. Resolution order per claim: **NotClaim → Exempt → Anchored(entity) → Anchored(local) → Unanchored**. `Unanchored.kind_hint = "stipulated"` when `document.kind in config.spec_class_kinds`, else `None`; `local_evidence` set from `paragraph_has_anchor_evidence`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_numeric_provenance.py (append)
from science_tool.numeric_provenance import (
    Anchored, Exempt, NotClaim, Unanchored, assess_numeric_claims,
)


def _assess(tmp_path, body, frontmatter=""):
    idx = build_resolution_index(_project(tmp_path))
    path = _doc(tmp_path, body, frontmatter=frontmatter)
    return assess_numeric_claims(build_document_context(path), idx, _CFG)


def test_unanchored_number_is_the_signal(tmp_path):
    out = _assess(tmp_path, "The improvement was 7.94 fold over baseline.\n",
                  frontmatter="kind: interpretation")
    assert any(isinstance(a, Unanchored) and a.claim.value == "7.94" for a in out)


def test_entity_provenance_anchors_all_numbers(tmp_path):
    out = _assess(tmp_path, "The improvement was 7.94 fold; p was 0.001.\n",
                  frontmatter="kind: interpretation\nsource_refs:\n  - task:t064")
    assert all(isinstance(a, Anchored) for a in out if a.claim.value in {"7.94", "0.001"})


def test_spec_class_kind_sets_kind_hint(tmp_path):
    out = _assess(tmp_path, "Gate coverage at 60% of diseases.\n", frontmatter="kind: plan")
    hit = next(a for a in out if a.claim.value == "60%")
    assert isinstance(hit, Unanchored) and hit.kind_hint == "stipulated"   # finding 1


def test_marked_stipulated_number_is_exempt(tmp_path):
    body = "## Decision thresholds\n<!-- stipulated -->\n\nGate coverage at 60%.\n"
    out = _assess(tmp_path, body, frontmatter="kind: plan")
    assert any(isinstance(a, Exempt) and a.claim.value == "60%" for a in out)


def test_incidental_body_anchor_does_not_clear_distant_number(tmp_path):
    body = ("Background cites task:t064 for context.\n\n"
            "A separate paragraph reports 7.94 fold.\n")
    out = _assess(tmp_path, body, frontmatter="kind: report")
    hit = next(a for a in out if a.claim.value == "7.94")
    assert isinstance(hit, Unanchored)   # finding 2: paragraph-scoped, not entity-wide
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run --frozen python -m pytest tests/test_numeric_provenance.py -k "signal or anchors_all or kind_hint or marked_stipulated or distant" -v`
Expected: FAIL — `ImportError: cannot import name 'assess_numeric_claims'`

- [ ] **Step 3: Implement the orchestrator**

```python
# numeric_provenance.py (add)
def assess_numeric_claims(
    document: DocumentContext, index: ResolutionIndex, config: NumericProvenanceConfig
) -> list[ClaimAssessment]:
    from science_tool.prose_lint import (  # reuse, do not duplicate
        _BARE_YEAR_RE, _BOLD_STRUCTURAL_LABEL_RE, _CROSS_REFERENCE_RE,
        _HEADER_OR_LIST_RE, _LIST_RE, _NUMERIC_CLAIM_RE, _mask_numeric_identifier_spans,
    )
    from science_tool.markdown_utils import is_fence_line, strip_inline_code

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
        line = _mask_numeric_identifier_spans(strip_inline_code(raw))
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
            # 1 — NotClaim
            reason = classify_structural(value, raw, match.start() + 1)
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
```

> Design note for the implementer: `local_evidence=True` still yields `Unanchored`, but the thin detector (Task 10) treats `local_evidence` as suppressing the emitted finding — preserving today's paragraph-anchor behavior for generic patterns while keeping the assessment honest ("no resolvable candidate, only weak evidence"). This keeps the `anchor_evidence` outcome distinct in the returned data (for Part B) without changing what fires.

- [ ] **Step 4: Run to verify it passes**

Run: `uv run --frozen python -m pytest tests/test_numeric_provenance.py -v`
Expected: PASS (all)

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/numeric_provenance.py science/tests/test_numeric_provenance.py
git commit -m "feat(numeric-provenance): add assess_numeric_claims orchestrator"
```

---

### Task 10: Rewrite `detect_numeric_anchor` as a thin adapter

**Files:**
- Modify: `science/src/science_tool/prose_lint.py:495-603` (rewrite detector; delete both ad-hoc helpers)
- Modify: `science/src/science_tool/prose_lint.py:792-841` (`scan_root` builds context + index once)
- Test: `science/tests/test_prose_lint.py` (existing `TestNumericAnchor` must stay green)

**Interfaces:**
- Consumes: `numeric_provenance.build_document_context`, `build_resolution_index`, `assess_numeric_claims`, `Unanchored`, `NumericProvenanceConfig`.
- Produces (new signature — back-compatible defaults):
  ```python
  def detect_numeric_anchor(
      path: Path, *, strict: bool = False,
      anchor_patterns: list[str] | None = None,
      resolution_index: "ResolutionIndex | None" = None,
      spec_class_kinds: list[str] | None = None,
      provenance_fields: list[str] | None = None,
  ) -> list[LintIssue]: ...
  ```
  When `resolution_index is None` (direct/legacy callers, e.g. the annotation adapter), the detector builds one from the file's project root. Emits a `LintIssue` for each `Unanchored` assessment with `local_evidence is False`.

- [ ] **Step 1: Run the existing suite to capture the baseline (must stay green)**

Run: `uv run --frozen python -m pytest tests/test_prose_lint.py::TestNumericAnchor -v`
Expected: PASS (record which tests pass now; they must still pass after the rewrite, except `test_flags_paper_note_without_source_context` and the fabricated-artifact behavior, which tighten — see Step 2).

- [ ] **Step 2: Write the new/adjusted failing tests**

```python
# tests/test_prose_lint.py — in TestNumericAnchor (append)
def test_interpretation_with_missing_artifact_now_flags(self, tmp_path):
    # existence-checking: a nonexistent artifact path no longer clears (finding 5)
    path = _write(tmp_path,
        "The effect was 7.94 fold.\n",
        frontmatter="kind: interpretation\nartifact: results/does-not-exist.json")
    issues = detect_numeric_anchor(path)
    assert any(i.match == "7.94" for i in issues)

def test_interpretation_with_real_artifact_clears(self, tmp_path):
    (tmp_path / "results").mkdir()
    (tmp_path / "results" / "real.json").write_text("{}")
    (tmp_path / "science.yaml").write_text("name: demo\n")
    path = _write(tmp_path,
        "The effect was 7.94 fold.\n",
        frontmatter="kind: interpretation\nartifact: results/real.json")
    assert detect_numeric_anchor(path) == []
```

- [ ] **Step 3: Run to verify the first new test fails**

Run: `uv run --frozen python -m pytest tests/test_prose_lint.py::TestNumericAnchor::test_interpretation_with_missing_artifact_now_flags -v`
Expected: FAIL — the old helper clears any nonempty `artifact` string (no existence check), so no issue is emitted.

- [ ] **Step 4: Rewrite the detector + delete the two helpers**

```python
# prose_lint.py — replace detect_numeric_anchor and delete
# _paper_note_has_source_context / _interpretation_has_artifact_context
def detect_numeric_anchor(
    path: Path,
    *,
    strict: bool = False,
    anchor_patterns: list[str] | None = None,
    resolution_index=None,
    spec_class_kinds: list[str] | None = None,
    provenance_fields: list[str] | None = None,
) -> list[LintIssue]:
    """Flag numeric claims that lack resolvable provenance (Part A).

    Thin adapter over `numeric_provenance.assess_numeric_claims`: emits a
    LintIssue for each Unanchored assessment with no weak local evidence.
    """
    from science_tool.numeric_provenance import (  # noqa: PLC0415
        NumericProvenanceConfig, Unanchored, assess_numeric_claims,
        build_document_context, build_resolution_index,
    )
    from science_tool.project_config import (  # noqa: PLC0415
        DEFAULT_ANCHOR_PATTERNS, DEFAULT_PROVENANCE_FIELDS, DEFAULT_SPEC_CLASS_KINDS,
    )
    from science_model.frontmatter import nearest_project_root  # noqa: PLC0415

    document = build_document_context(path)
    if document is None:
        return []
    if resolution_index is None:
        root = nearest_project_root(path) or path.parent
        resolution_index = build_resolution_index(root)
    config = NumericProvenanceConfig(
        anchor_patterns=tuple(anchor_patterns if anchor_patterns is not None else DEFAULT_ANCHOR_PATTERNS),
        spec_class_kinds=frozenset(spec_class_kinds if spec_class_kinds is not None else DEFAULT_SPEC_CLASS_KINDS),
        provenance_fields=tuple(provenance_fields if provenance_fields is not None else DEFAULT_PROVENANCE_FIELDS),
    )
    issues: list[LintIssue] = []
    for a in assess_numeric_claims(document, resolution_index, config):
        if isinstance(a, Unanchored) and not a.local_evidence:
            issues.append(LintIssue(
                file=path, line=a.claim.line, col=a.claim.col, check="numeric-anchor",
                severity=severity_for("numeric-anchor", strict=strict),
                message=_numeric_anchor_message(a),
                match=a.claim.value,
            ))
    return issues


def _numeric_anchor_message(a) -> str:
    if a.kind_hint == "stipulated":
        return (f"stipulated parameter '{a.claim.value}' lacks grounding — "
                "mark as stipulated or provide resolvable provenance")
    return f"numeric claim '{a.claim.value}' has no resolvable source"
```

- [ ] **Step 5: Thread context/index through `scan_root`**

```python
# prose_lint.py — in scan_root, add parameters and build the index once
def scan_root(
    root: Path,
    *,
    checks: list[str] | None = None,
    strict: bool = False,
    anchor_patterns: list[str] | None = None,
    spec_class_kinds: list[str] | None = None,
    provenance_fields: list[str] | None = None,
    exclude_paths: list[str] | None = None,
    short_form_ids_deny: list[str] | None = None,
    resolver: dict[str, str] | None = None,
    bare_author_year_deny: list[str] | None = None,
    bib_surnames: set[str] | None = None,
) -> dict:
    ...  # existing selection/validation unchanged
    resolution_index = None
    if "numeric-anchor" in selected:
        from science_tool.numeric_provenance import build_resolution_index  # noqa: PLC0415
        resolution_index = build_resolution_index(root)
    ...
    for path in files:
        for check in selected:
            detector = _DETECTORS[check]
            if check == "numeric-anchor":
                hits.extend(detector(
                    path, strict=strict, anchor_patterns=anchor_patterns,
                    resolution_index=resolution_index,
                    spec_class_kinds=spec_class_kinds, provenance_fields=provenance_fields,
                ))
            elif check == "short-form-ids":
                ...
```

- [ ] **Step 6: Run the full detector + scan suites**

Run: `uv run --frozen python -m pytest tests/test_prose_lint.py -v`
Expected: PASS. Update `test_flags_paper_note_without_source_context` / any test asserting the old no-existence-check behavior to reflect existence-checking; keep all genuine-clear cases green.

- [ ] **Step 7: Commit**

```bash
git add science/src/science_tool/prose_lint.py science/tests/test_prose_lint.py
git commit -m "refactor(prose-lint): make numeric-anchor a thin adapter over numeric_provenance"
```

---

### Task 11: Wire config through validation check + CLI (additive vocabulary)

**Files:**
- Modify: `science/src/science_tool/validate/checks/prose_lints.py:72-113`
- Modify: `science/src/science_tool/prose_lint_cli.py:37-72`
- Test: `science/tests/validate/test_checks_prose_lints.py`, `science/tests/test_prose_lint_cli.py`

**Interfaces:**
- Consumes: `ProseLintConfig.additional_anchor_patterns`, `.spec_class_kinds`, `.provenance_fields`.
- Produces: both callers compute `effective_anchor_patterns = anchor_patterns + additional_anchor_patterns` (dedup, order-preserving) and forward `spec_class_kinds` / `provenance_fields` into `scan_root`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_prose_lint_cli.py (append)
def test_additional_anchor_patterns_reach_numeric_anchor(tmp_path):
    (tmp_path / "science.yaml").write_text(
        "name: demo\nprose_lint:\n  anchor_patterns: ['task:']\n"
        "  additional_anchor_patterns: ['paper:']\n")
    (tmp_path / "entities").mkdir()
    (tmp_path / "entities" / "e.md").write_text(
        "---\nkind: report\n---\n\nGrounded via paper:Foo2024 the value 7.94 holds.\n")
    from click.testing import CliRunner
    from science_tool.prose_lint_cli import prose_group
    import json
    res = CliRunner().invoke(prose_group, ["lint", "--root", str(tmp_path), "--format", "json",
                                           "--check", "numeric-anchor"])
    payload = json.loads(res.output)
    # `paper:` is only reachable because it was *additional*, not in anchor_patterns
    assert "numeric-anchor" not in payload["counts"]
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run --frozen python -m pytest tests/test_prose_lint_cli.py::test_additional_anchor_patterns_reach_numeric_anchor -v`
Expected: FAIL — additional patterns not yet merged, so `paper:` isn't an anchor and `7.94` flags.

- [ ] **Step 3: Merge additive vocabulary + forward config (both callers)**

```python
# a shared helper — add to prose_lint.py
def merge_anchor_patterns(base: list[str], additional: list[str]) -> list[str]:
    """base + additional, order-preserving, de-duplicated."""
    merged: list[str] = []
    for p in [*base, *additional]:
        if p not in merged:
            merged.append(p)
    return merged
```

```python
# prose_lint_cli.py — in lint_cmd, after loading config
additional = []
spec_class_kinds = list(DEFAULT_SPEC_CLASS_KINDS)
provenance_fields = list(DEFAULT_PROVENANCE_FIELDS)
if science_yaml.is_file() and config.prose_lint is not None:
    additional = config.prose_lint.additional_anchor_patterns
    spec_class_kinds = config.prose_lint.spec_class_kinds
    provenance_fields = config.prose_lint.provenance_fields
effective_anchor_patterns = merge_anchor_patterns(anchor_patterns, additional)
# ...pass to scan_root:
result = scan_root(
    root, checks=selected, strict=strict,
    anchor_patterns=effective_anchor_patterns,
    spec_class_kinds=spec_class_kinds, provenance_fields=provenance_fields,
    exclude_paths=exclude_paths, short_form_ids_deny=short_form_ids_deny,
    resolver=resolver, bare_author_year_deny=bare_author_year_deny, bib_surnames=bib_surnames,
)
```

Apply the identical merge/forward in `validate/checks/prose_lints.py` (import `DEFAULT_SPEC_CLASS_KINDS`, `DEFAULT_PROVENANCE_FIELDS`, `merge_anchor_patterns`).

- [ ] **Step 4: Run to verify it passes**

Run: `uv run --frozen python -m pytest tests/test_prose_lint_cli.py tests/validate/test_checks_prose_lints.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/prose_lint_cli.py science/src/science_tool/validate/checks/prose_lints.py science/src/science_tool/prose_lint.py science/tests/test_prose_lint_cli.py science/tests/validate/test_checks_prose_lints.py
git commit -m "feat(prose-lint): merge additive vocabulary + forward numeric-provenance config"
```

---

### Task 12: Annotation adapter + detector-version bump

**Files:**
- Modify: `science/src/science_tool/annotation/sources/lint.py:34-38` (bump version), `:96-102` (numeric_anchor_source scan)
- Test: `science/tests/` (add a targeted test near the annotation-source tests)

**Interfaces:**
- Consumes: `numeric_provenance.build_resolution_index`.
- Produces: `DETECTOR_VERSIONS["numeric-anchor"] = "v2026-07-18"`; `LintSource.scan` builds a resolution index for numeric-anchor so annotations key on the new detector.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_annotation_lint_source_numeric.py
from science_tool.annotation.sources.lint import DETECTOR_VERSIONS, lint_source_name


def test_numeric_anchor_detector_version_bumped():
    assert DETECTOR_VERSIONS["numeric-anchor"] == "v2026-07-18"
    assert lint_source_name("numeric-anchor") == "lint:numeric-anchor-v2026-07-18"
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run --frozen python -m pytest tests/test_annotation_lint_source_numeric.py -v`
Expected: FAIL — version still `v2026-05-11`.

- [ ] **Step 3: Bump the version and make scan index-aware**

```python
# annotation/sources/lint.py
DETECTOR_VERSIONS: dict[str, str] = {
    "bare-author-year": "v2026-05-11",
    "short-form-ids":   "v2026-05-11",
    "numeric-anchor":   "v2026-07-18",   # numeric-provenance Part A: existence-checked
}
```

The existing `LintSource.scan` calls `self.detector(md_path)` with no kwargs; `detect_numeric_anchor` now builds its own index from the file's project root when `resolution_index is None` (Task 10, Step 4), so `numeric_anchor_source` needs **no** scan-body change beyond the version bump. Confirm by test; only touch `scan` if a per-file index build proves too slow in the annotation batch (then build once and thread it — out of scope unless demonstrated).

- [ ] **Step 4: Run to verify it passes**

Run: `uv run --frozen python -m pytest tests/test_annotation_lint_source_numeric.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/annotation/sources/lint.py science/tests/test_annotation_lint_source_numeric.py
git commit -m "feat(annotation): bump numeric-anchor detector version for Part A"
```

---

### Task 13: Materialize the regression oracle + adversarial controls

**Files:**
- Create: `science/tests/fixtures/numeric_provenance_oracle.jsonl`
- Create: `science/tests/test_numeric_provenance_oracle.py`
- Reference (read-only): `~/d/science/.worktrees/numeric-provenance-redesign/docs/audits/2026-07-18-numeric-anchor-audit/samples/*.jsonl`

**Interfaces:**
- Oracle row schema (JSONL):
  ```
  {"finding_id","file","line","number","origin","traceability",
   "expected_part_a_outcome","expected_reason","fixture_md","frontmatter"}
  ```
  `expected_part_a_outcome ∈ {"NotClaim","Exempt","Anchored","Unanchored"}`. `fixture_md`/`frontmatter` hold a **self-contained** minimal document reproducing the case (so the oracle runs without the real projects).

- [ ] **Step 1: Author the oracle rows (re-label the 320 audit findings + add adversarial controls)**

Build `numeric_provenance_oracle.jsonl`. For the re-labeled audit findings, derive `expected_part_a_outcome` from the audit's `origin`/`traceability`:
- `origin=structural` → `NotClaim`
- `origin=stipulated-param` **with a marker in the fixture** → `Exempt`; **without** → `Unanchored` (kind_hint stipulated)
- `traceability=frontmatter-source-covers` (resolvable) → `Anchored`
- `traceability=cited-elsewhere-in-doc` where the cite is in the **same paragraph** → `Anchored`; a **distant** cite → `Unanchored`
- `traceability=truly-orphaned` → `Unanchored`

Then append the seven **adversarial controls** verbatim from the design's Testing section, each as a self-contained fixture:

```jsonl
{"finding_id":"adv-empirical-in-prereg","expected_part_a_outcome":"Unanchored","expected_reason":"empirical prior in pre-registration without its own source","frontmatter":"kind: pre-registration","fixture_md":"We assume a base rate of 12.3% from prior work.\n","number":"12.3%"}
{"finding_id":"adv-distant-citation","expected_part_a_outcome":"Unanchored","expected_reason":"unrelated citation elsewhere must not clear a distant number","frontmatter":"kind: report","fixture_md":"Background cites task:t064.\n\nSeparately, we report 7.94 fold.\n","number":"7.94"}
{"finding_id":"adv-fake-task","expected_part_a_outcome":"Unanchored","expected_reason":"nonexistent task:t999 must not anchor","frontmatter":"kind: interpretation\nsource_refs:\n  - task:t999","fixture_md":"The effect was 7.94 fold.\n","number":"7.94"}
{"finding_id":"adv-fake-artifact","expected_part_a_outcome":"Unanchored","expected_reason":"nonexistent artifact path must not anchor","frontmatter":"kind: interpretation\nartifact: results/nope.json","fixture_md":"The effect was 7.94 fold.\n","number":"7.94"}
{"finding_id":"adv-orphan-in-sourced-entity","expected_part_a_outcome":"Anchored","expected_reason":"documented Part-A miss: orphan inside otherwise-sourced entity (B closes it)","frontmatter":"kind: interpretation\nsource_refs:\n  - task:t064","fixture_md":"Main result 7.94; incidental aside 42.0 fold.\n","number":"42.0"}
{"finding_id":"adv-custom-patterns","expected_part_a_outcome":"Unanchored","expected_reason":"project with only overridden anchor_patterns still flags an orphan","frontmatter":"kind: report","fixture_md":"An orphan 7.94 with no anchor at all.\n","number":"7.94"}
{"finding_id":"adv-size-fact-vs-download","expected_part_a_outcome":"Unanchored","expected_reason":"factual genome size is a claim; 516.9 MB download is NotClaim","frontmatter":"kind: report","fixture_md":"The human genome is 3.2 Gb in length.\n","number":"3.2"}
```

- [ ] **Step 2: Write the oracle-driven test**

```python
# tests/test_numeric_provenance_oracle.py
import json
from pathlib import Path

import pytest

from science_tool.numeric_provenance import (
    Anchored, Exempt, NotClaim, NumericProvenanceConfig, Unanchored,
    assess_numeric_claims, build_document_context, build_resolution_index,
)

ORACLE = Path(__file__).parent / "fixtures" / "numeric_provenance_oracle.jsonl"
_OUTCOME = {"NotClaim": NotClaim, "Exempt": Exempt, "Anchored": Anchored, "Unanchored": Unanchored}


def _rows():
    return [json.loads(line) for line in ORACLE.read_text().splitlines() if line.strip()]


@pytest.mark.parametrize("row", _rows(), ids=lambda r: r["finding_id"])
def test_oracle_expected_outcome(row, tmp_path):
    # Build a self-contained project reproducing the fixture, with real anchors present.
    (tmp_path / "science.yaml").write_text("name: oracle\n")
    (tmp_path / "tasks").mkdir()
    (tmp_path / "tasks" / "active.md").write_text("## [t064] Anchor task\n\nbody\n")
    (tmp_path / "results").mkdir()
    (tmp_path / "results" / "qap.json").write_text("{}")
    fm = row.get("frontmatter", "")
    path = tmp_path / f"{row['finding_id']}.md"
    path.write_text(f"---\n{fm}\n---\n{row['fixture_md']}" if fm else row["fixture_md"])
    cfg = NumericProvenanceConfig(
        anchor_patterns=("task:", r"\[@", "cite:"),
        spec_class_kinds=frozenset({"pre-registration", "plan"}),
        provenance_fields=("source_refs", "task_links", "input"),
    )
    assessments = assess_numeric_claims(build_document_context(path), build_resolution_index(tmp_path), cfg)
    match = [a for a in assessments if a.claim.value == row["number"]]
    assert match, f"{row['finding_id']}: number {row['number']!r} not assessed"
    assert isinstance(match[0], _OUTCOME[row["expected_part_a_outcome"]]), (
        f"{row['finding_id']}: {row['expected_reason']}")
```

- [ ] **Step 3: Run to verify it fails, then iterate**

Run: `uv run --frozen python -m pytest tests/test_numeric_provenance_oracle.py -v`
Expected: initially some FAIL. Fix any genuine core-logic gaps in `numeric_provenance.py` (re-running the relevant Task 2–9 unit tests after each change); adjust an oracle **label** only when the design says that outcome is correct (never to paper over a real regression). Iterate to all-PASS.

- [ ] **Step 4: Commit**

```bash
git add science/tests/fixtures/numeric_provenance_oracle.jsonl science/tests/test_numeric_provenance_oracle.py
git commit -m "test(numeric-provenance): materialize labeled oracle + adversarial controls"
```

---

### Task 14: Cross-project before/after acceptance + convention docs

**Files:**
- Modify: `science/docs/conventions/prose-lints.md`
- Create: `science/scripts/numeric_provenance_before_after.py` (throwaway acceptance harness kept for reproducibility)

**Interfaces:** none (acceptance + documentation).

- [ ] **Step 1: Document the four outcomes + marker authoring**

Add a `## numeric-anchor (numeric provenance)` subsection to `docs/conventions/prose-lints.md` describing: the four outcomes; that a firing finding means "no resolvable declared source at the right scope"; the two-way remediation ("mark as stipulated or provide resolvable provenance"); and the marker syntax — frontmatter `stipulated: true` (pure-spec docs only, never a template default), `<!-- stipulated -->` under a heading (section, fail-closed), `<!-- stipulated:start -->`/`<!-- stipulated:end -->` (block, for mixed sections). Note existence-checking may surface previously-hidden fabricated refs.

- [ ] **Step 2: Write the before/after harness**

```python
# science/scripts/numeric_provenance_before_after.py
"""Sweep configured projects, report numeric-anchor counts (acceptance check).

Usage: uv run python science/scripts/numeric_provenance_before_after.py PROJECT_ROOT [PROJECT_ROOT ...]
Prints per-project numeric-anchor finding counts under the new engine, so the
order-of-magnitude drop (e.g. pan-disease ~587 -> tens) can be confirmed and
survivors spot-checked.
"""
import sys
from pathlib import Path

from science_tool.prose_lint import scan_root


def main(roots: list[str]) -> None:
    for r in roots:
        root = Path(r).resolve()
        result = scan_root(root, checks=["numeric-anchor"])
        n = result["counts"].get("numeric-anchor", 0)
        print(f"{root.name:40s} numeric-anchor={n}")
        for hit in result["hits"][:20]:
            print(f"    {hit.file}:{hit.line} {hit.match}  {hit.message}")


if __name__ == "__main__":
    main(sys.argv[1:] or ["."])
```

- [ ] **Step 3: Run the acceptance sweep (record numbers)**

Run: `uv run --frozen python science/scripts/numeric_provenance_before_after.py ~/d/health/comparisons/pan-disease`
Expected: numeric-anchor count collapses from the ~587 baseline to an order-of-magnitude-smaller residual; manually spot-check ~10 survivors are genuinely ungrounded (or genuinely fabricated refs the existence-check newly surfaced). Record the count in the commit message.

- [ ] **Step 4: Run the full science suite**

Run: `uv run --frozen python -m pytest -q`
Expected: PASS (no regressions across the toolkit).

- [ ] **Step 5: Commit**

```bash
git add science/docs/conventions/prose-lints.md science/scripts/numeric_provenance_before_after.py
git commit -m "docs(prose-lint): document numeric-provenance outcomes + record before/after"
```

---

## Rollout notes (post-implementation, not tasks in this plan)

- **pan-disease t107 closes for free:** once Part A ships, migrate pan-disease's `science.yaml` — move its project-local `paper:` anchor and any reverted `exclude_paths` into `additional_anchor_patterns`, drop the numeric-anchor `exclude_paths` hack, and re-run validate. Close t107 via `uv run science tasks done t107` from the pan-disease root.
- **Shared default vocabulary:** consider promoting `cite:`, `paper:`, `dataset:`, and inline `t\d{3,}` into a shipped `DEFAULT_ANCHOR_PATTERNS` extension in a follow-up, once the additive path is proven downstream.
- **Non-monotonic tightening is expected:** downstream projects should anticipate a few *new* findings (fabricated `task:`/`artifact:` refs the existence-check surfaces) alongside the large reduction.

## Self-review (completed)

- **Spec coverage:** discriminated outcomes (T2, T9) · structural narrow+context-gated (T5) · marker-based Exempt with fail-closed section/block scoping and no template auto-mark (T6, docs T14) · entity-scoped vs local vs anchor_evidence (T7, T8) · existence-checking in Part A (T4, T7, T8) · unify/replace the two ad-hoc helpers (T10) · `assess_numeric_claims` returns all assessments (T9) · additive vocabulary reaching configured projects (T1, T11) · annotation adapter + version bump (T12) · DocumentContext shared by callers (T3, T10) · labeled oracle + adversarial controls (T13) · cross-project before/after (T14). Part B intentionally excluded.
- **Open questions resolved in-plan:** marker syntax (T6, fixed tokens) · local anchor scope = paragraph (T8) · unification preservation set (T7).
- **Type consistency:** `ClaimAssessment` variants, `SourceCandidate`, `NumericClaim`, `NumericProvenanceConfig`, `DocumentContext`, `ResolutionIndex`, `assess_numeric_claims`, `build_document_context`, `build_resolution_index`, `merge_anchor_patterns` are used with identical signatures across tasks.
- **Placeholder scan:** none — every code step carries real code; the one illustrative test line in T8 is called out explicitly.

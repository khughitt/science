# Annotation System P3.1 — `science annotate verify` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship `science annotate verify` — drift detection across every
`*.anno.trig` sidecar in a project. No LLM, no auditors. The first user-
facing CLI on top of the P3.0 data model; exercises the parser, writer,
selector resolver, and lifecycle mutator on real annotations before
heavier consumers (lift, list, render, audit) arrive.

**Architecture:** Two new modules and one new CLI group:

- `science_tool/annotation/verify.py` — pure orchestration: discover
  sidecars under a root, resolve every annotation's
  `oa:TextQuoteSelector` against the source markdown, classify each as
  `ok | degraded | fuzzy | broken | source-missing`, and emit a
  `VerifyReport`. A separate `apply_supersessions(report, *, actor,
  now)` helper writes back `sci:status "superseded"` to broken rows
  using the existing `mutate_status` API and rewrites only the sidecars
  that actually changed.
- `science_tool/annotation/cli.py` — Click group `annotate` with one
  subcommand `verify`. Mirrors `refs check` for option layout
  (`--root`, `--format table|json`, `--summary-only`, `--strict`) plus
  `--apply` and `--actor` for the write-back path. Default is dry-run.
- `science_tool/cli.py` registration: import `annotate_group` and
  `main.add_command(annotate_group)`.

`validate.sh` integration is bundled (Section 19 + managed-artifact
bump) so the drift check ships in the same release as the CLI it
depends on. The hook calls `science annotate verify --format json
--summary-only` exactly the way Section 6 calls `refs check` and
Section 18 calls `prose lint`.

**Tech Stack:** Python 3.11, click, rdflib (already in P3.0), pytest.
No new dependencies.

---

## Spec references

This plan implements the following sections of
`docs/plans/2026-05-10-annotation-system-spec.md`:

- §Span addressing — selector resolution semantics (already done in
  P3.0; this plan exercises it project-wide)
- §Status lifecycle — `* → superseded` automatic transition
- §Verify loop (CI drift detection) — primary requirement
- §`validate.sh` integration — optional Section 19 (this plan
  promotes it to required for the version bump that ships P3.1)
- §CLI surface — `science annotate verify` row. Note: the spec's
  shorthand `verify [<path>]` is realized as `verify --root <path>` to
  match the sibling commands `science refs check --root` and `science
  prose lint --root`. The positional form is not added in P3.1; the
  `--root` flag is the load-bearing surface and matches CI usage in
  validate.sh Section 19.

Out of scope for P3.1 (deferred to later phases):

- `science annotate audit / lift-tokens / list / ack / dismiss / fix /
  render / stats` — P3.2–P3.4
- LLM auditor calls — P3.5
- Graph ingest into `knowledge/graph.trig` — P3.6
- `--since <git-ref>` paragraph-scope optimization — explicitly *not*
  implemented; verify always walks every annotation. Cheap on current
  project size; can be added later if the wall-clock crosses the pain
  threshold.

---

## File Structure

**Create (source):**

- `science/src/science_tool/annotation/verify.py` — `VerifyIssue`,
  `VerifyReport`, `verify_path()`, `apply_supersessions()`,
  `iter_sidecars()`
- `science/src/science_tool/annotation/cli.py` — `annotate_group` and
  `verify` subcommand

**Modify (source):**

- `science/src/science_tool/cli.py` — import and register
  `annotate_group`
- `science/src/science_tool/project_artifacts/data/validate.sh` — add
  Section 19: annotation drift check
- `science/src/science_tool/project_artifacts/registry.yaml` — bump
  `validate.sh` version, append migration + changelog entries, recompute
  current_hash

**Create (tests):**

- `science/tests/test_annotation_verify.py` — orchestration tests
  (`iter_sidecars`, `verify_path`, `apply_supersessions`)
- `science/tests/test_annotate_cli.py` — Click runner tests for the
  `annotate verify` subcommand (table + json output, exit codes,
  `--apply` behavior, `--strict`)
- `science/tests/_fixtures/annotation/verify/` — purpose-built fixture
  tree with multiple sidecars and source markdown that exercises every
  resolution outcome (see Task 1 for the fixture layout)

**Note on the existing fixture.** `tests/_fixtures/annotation/citation-
audit-pilot.anno.trig` was hand-typed for the P3.0 round-trip test and
its prefix/suffix do not anchor against any real markdown. P3.1 builds
its own fixture set rather than retrofitting the P3.0 one; the P3.0
fixture stays untouched so its byte-identical round-trip test keeps
working.

---

## Task list

1. Verify orchestration core (`verify.py` — discovery + classification)
2. Write-back helper (`verify.py::apply_supersessions`)
3. CLI `annotate verify` — table output + dry-run default
4. CLI `annotate verify --format json`
5. CLI `annotate verify --apply` — write-back path with `--actor` + clean-tree guard
6. `validate.sh` Section 19 + managed-artifact bump

---

### Task 1: Verify orchestration core

**Files:**
- Create: `science/src/science_tool/annotation/verify.py`
- Create: `science/tests/test_annotation_verify.py`
- Create fixtures: `science/tests/_fixtures/annotation/verify/source.md`
- Create fixtures: `science/tests/_fixtures/annotation/verify/source.anno.trig`
- Create fixtures: `science/tests/_fixtures/annotation/verify/no-source.anno.trig`
- Create fixtures: `science/tests/_fixtures/annotation/verify/nested/deep.md`
- Create fixtures: `science/tests/_fixtures/annotation/verify/nested/deep.anno.trig`

**Goal:** Pure (no I/O write) orchestration: walk a project root, parse
every `*.anno.trig`, resolve every annotation's selector against the
referenced source markdown, classify outcomes, return a `VerifyReport`.

**Design points to encode:**

- **Discovery scope.** Walk the root recursively for `**/*.anno.trig`,
  but skip the standard noise directories: `.git`, `.venv`,
  `node_modules`, `.worktrees`, `worktrees`, `__pycache__`. Return paths
  in sorted order for deterministic output.
- **Source path resolution.** `annotation.target.source` is stored as
  authored — typically a bare relative path against the sidecar's
  directory. Resolve it as `sidecar.parent / source`. If the resolved
  path does not exist, classify the annotation as `source-missing` and
  do not call the resolver. Absolute URIs (anything containing `://`)
  are out of scope for v1; classify those as `source-missing` too with
  a marker in the issue payload so the user sees them.
- **Resolution outcomes** (one issue per non-OK annotation):
  - `ResolutionStatus.RESOLVED` → no issue
  - `ResolutionStatus.DEGRADED` → `kind="degraded"`
  - `ResolutionStatus.FUZZY` → `kind="fuzzy"`
  - `ResolutionStatus.SUPERSEDED` → `kind="broken"`
  - source file absent → `kind="source-missing"` (skip resolver)
- **Already-superseded skip.** Annotations whose status is already
  `Status.SUPERSEDED` are not re-classified — their selector is known
  to be lost; re-running the resolver wastes work and would either
  no-op or surface noise. Count them in `superseded_skipped` so the
  table makes the skip visible.
- **Source text caching.** Within a single `verify_path` call, cache
  source markdown by resolved absolute path. A typical project has
  many annotations per source file; reading the file once per call
  avoids quadratic I/O.
- **Per-sidecar parse failure.** If `read_sidecar` raises, surface as
  a `VerifyIssue` with `kind="parse-error"` and `annotation_id=""`,
  then continue to the next sidecar. Do not abort the whole walk on
  one bad file. Count parse errors in the summary.

- [ ] **Step 1: Write the failing tests**

```python
# science/tests/test_annotation_verify.py
"""Tests for the verify orchestration core."""

from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.annotation.verify import (
    VerifyIssue,
    VerifyReport,
    iter_sidecars,
    verify_path,
)

FIX = Path(__file__).parent / "_fixtures" / "annotation" / "verify"


def test_iter_sidecars_finds_all_anno_trig_files(tmp_path: Path) -> None:
    (tmp_path / "a.anno.trig").write_text("")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.anno.trig").write_text("")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "ignored.anno.trig").write_text("")
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "ignored.anno.trig").write_text("")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "ignored.anno.trig").write_text("")
    (tmp_path / "unrelated.md").write_text("")

    found = list(iter_sidecars(tmp_path))
    rels = sorted(p.relative_to(tmp_path).as_posix() for p in found)
    assert rels == ["a.anno.trig", "sub/b.anno.trig"]


def test_iter_sidecars_returns_paths_in_sorted_order(tmp_path: Path) -> None:
    (tmp_path / "z.anno.trig").write_text("")
    (tmp_path / "a.anno.trig").write_text("")
    (tmp_path / "m.anno.trig").write_text("")
    found = list(iter_sidecars(tmp_path))
    assert [p.name for p in found] == ["a.anno.trig", "m.anno.trig", "z.anno.trig"]


def test_verify_path_classifies_resolved_degraded_fuzzy_broken_supersession() -> None:
    """The `source.anno.trig` fixture has one annotation per outcome.

    See the fixture for the exact prose and selectors. Outcomes:
      - a-ok            → RESOLVED, no issue
      - a-degraded      → DEGRADED (bare exact unique, anchors don't match)
      - a-fuzzy         → FUZZY (1-char same-length substitution within margin;
                          the resolver only matches same-length windows, so the
                          source typo MUST be a substitution, not an insert/delete)
      - a-broken        → SUPERSEDED (exact text removed from source)
    """
    report = verify_path(FIX)
    sidecar_rel = "source.anno.trig"
    issues_for_source = [i for i in report.issues if i.sidecar.name == sidecar_rel]
    by_kind: dict[str, list[VerifyIssue]] = {}
    for i in issues_for_source:
        by_kind.setdefault(i.kind, []).append(i)
    assert sorted(by_kind.keys()) == ["broken", "degraded", "fuzzy"]
    broken_ids = sorted(i.annotation_id for i in by_kind["broken"])
    degraded_ids = sorted(i.annotation_id for i in by_kind["degraded"])
    fuzzy_ids = sorted(i.annotation_id for i in by_kind["fuzzy"])
    assert broken_ids == ["a-broken"]
    assert degraded_ids == ["a-degraded"]
    assert fuzzy_ids == ["a-fuzzy"]


def test_verify_path_reports_source_missing_when_target_file_absent() -> None:
    report = verify_path(FIX)
    no_source = [i for i in report.issues if i.sidecar.name == "no-source.anno.trig"]
    assert len(no_source) == 1
    assert no_source[0].kind == "source-missing"
    assert no_source[0].annotation_id == "a-orphan"


def test_verify_path_walks_nested_directories() -> None:
    report = verify_path(FIX)
    nested = [i for i in report.issues if i.sidecar.parent.name == "nested"]
    # The nested fixture has one broken annotation.
    assert len(nested) == 1
    assert nested[0].kind == "broken"


def test_verify_path_skips_already_superseded_annotations(tmp_path: Path) -> None:
    """An annotation that is already 'superseded' should not be re-classified."""
    # Copy the broken sidecar but flip its status to 'superseded' first; we
    # expect it to be counted in superseded_skipped, not in issues.
    src_text = (FIX / "source.md").read_text()
    (tmp_path / "source.md").write_text(src_text)
    sidecar = tmp_path / "source.anno.trig"
    sidecar.write_text(_sidecar_with_one_already_superseded())
    report = verify_path(tmp_path)
    assert report.superseded_skipped == 1
    assert all(i.kind != "broken" for i in report.issues)


def test_verify_path_summary_counts_match_issues() -> None:
    report = verify_path(FIX)
    assert report.broken == sum(1 for i in report.issues if i.kind == "broken")
    assert report.degraded == sum(1 for i in report.issues if i.kind == "degraded")
    assert report.fuzzy == sum(1 for i in report.issues if i.kind == "fuzzy")
    assert report.source_missing == sum(
        1 for i in report.issues if i.kind == "source-missing"
    )
    assert report.parse_errors == sum(
        1 for i in report.issues if i.kind == "parse-error"
    )
    assert report.sidecars >= 3  # source, no-source, nested/deep


def test_verify_path_records_parse_error_without_aborting(tmp_path: Path) -> None:
    (tmp_path / "broken.anno.trig").write_text("this is not trig at all {{{")
    (tmp_path / "good.anno.trig").write_text(_minimal_empty_sidecar())
    report = verify_path(tmp_path)
    parse_errors = [i for i in report.issues if i.kind == "parse-error"]
    assert len(parse_errors) == 1
    assert parse_errors[0].sidecar.name == "broken.anno.trig"
    # 'good.anno.trig' was still walked.
    assert report.sidecars == 2


def _minimal_empty_sidecar() -> str:
    return (
        "@prefix oa: <http://www.w3.org/ns/oa#> .\n"
        "@prefix anno: <#> .\n"
        "anno:annotations { }\n"
    )


def _sidecar_with_one_already_superseded() -> str:
    """A sidecar whose one annotation has status='superseded'.

    Selector exact text is intentionally absent from source.md, so if
    verify_path mistakenly re-classifies it, we'd see kind='broken'.
    """
    return (
        "@prefix rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .\n"
        "@prefix oa:   <http://www.w3.org/ns/oa#> .\n"
        "@prefix dc:   <http://purl.org/dc/terms/> .\n"
        "@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .\n"
        "@prefix sci:  <http://example.org/science/vocab/> .\n"
        "@prefix anno: <#> .\n"
        "anno:annotations {\n"
        "  anno:a-stale a oa:Annotation ;\n"
        "    oa:hasTarget [\n"
        "      oa:hasSource <source.md> ;\n"
        "      oa:hasSelector [\n"
        "        a oa:TextQuoteSelector ;\n"
        '        oa:exact   "text that has been deleted entirely" ;\n'
        '        oa:prefix  "" ;\n'
        '        oa:suffix  ""\n'
        "      ]\n"
        "    ] ;\n"
        '    oa:hasBody         [ a oa:TextualBody ; dc:format "text/plain" ; rdf:value "x" ] ;\n'
        "    oa:motivatedBy     oa:commenting ;\n"
        '    sci:annotationType "comment" ;\n'
        '    sci:source         "human:test" ;\n'
        '    sci:status         "superseded" ;\n'
        '    dc:creator         "test" ;\n'
        '    dc:created         "2026-05-11T00:00:00+00:00"^^xsd:dateTime ;\n'
        '    dc:modified        "2026-05-11T00:00:00+00:00"^^xsd:dateTime ;\n'
        '    dc:contributor     "test" .\n'
        "}\n"
    )
```

- [ ] **Step 2: Write the fixtures**

Create `science/tests/_fixtures/annotation/verify/source.md`:

```markdown
# Verify fixture source

The original sentence reads exactly: the annotation system uses TextQuoteSelector for span addressing.

A second paragraph contains the bare phrase "category theory is the right framework" without any disambiguating anchors that match the recorded prefix.

A third paragraph anchors a slightly misspelled phrase: the framework is built on solid theoreticel foundations, with one substitution.

A fourth paragraph used to mention semantic line breaks but no longer does.
```

Create `science/tests/_fixtures/annotation/verify/source.anno.trig`:

```
@prefix rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix oa:   <http://www.w3.org/ns/oa#> .
@prefix dc:   <http://purl.org/dc/terms/> .
@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .
@prefix sci:  <http://example.org/science/vocab/> .
@prefix anno: <#> .

anno:annotations {
  anno:a-ok a oa:Annotation ;
    oa:hasTarget [
      oa:hasSource <source.md> ;
      oa:hasSelector [
        a oa:TextQuoteSelector ;
        oa:exact   "the annotation system uses TextQuoteSelector for span addressing" ;
        oa:prefix  "the original sentence reads exactly: " ;
        oa:suffix  ".\n\nA second paragraph"
      ]
    ] ;
    oa:hasBody         [ a oa:TextualBody ; dc:format "text/plain" ; rdf:value "ok body" ] ;
    oa:motivatedBy     oa:commenting ;
    sci:annotationType "comment" ;
    sci:source         "human:test" ;
    sci:status         "open" ;
    dc:creator         "test" ;
    dc:created         "2026-05-11T00:00:00+00:00"^^xsd:dateTime .

  anno:a-degraded a oa:Annotation ;
    oa:hasTarget [
      oa:hasSource <source.md> ;
      oa:hasSelector [
        a oa:TextQuoteSelector ;
        oa:exact   "category theory is the right framework" ;
        oa:prefix  "PREFIX_THAT_DOES_NOT_MATCH_ANYTHING " ;
        oa:suffix  " SUFFIX_THAT_DOES_NOT_MATCH_ANYTHING"
      ]
    ] ;
    oa:hasBody         [ a oa:TextualBody ; dc:format "text/plain" ; rdf:value "degraded body" ] ;
    oa:motivatedBy     oa:commenting ;
    sci:annotationType "comment" ;
    sci:source         "human:test" ;
    sci:status         "open" ;
    dc:creator         "test" ;
    dc:created         "2026-05-11T00:00:00+00:00"^^xsd:dateTime .

  anno:a-fuzzy a oa:Annotation ;
    oa:hasTarget [
      oa:hasSource <source.md> ;
      oa:hasSelector [
        a oa:TextQuoteSelector ;
        oa:exact   "the framework is built on solid theoretical foundations" ;
        oa:prefix  "" ;
        oa:suffix  ""
      ]
    ] ;
    oa:hasBody         [ a oa:TextualBody ; dc:format "text/plain" ; rdf:value "fuzzy body" ] ;
    oa:motivatedBy     oa:commenting ;
    sci:annotationType "comment" ;
    sci:source         "human:test" ;
    sci:status         "open" ;
    dc:creator         "test" ;
    dc:created         "2026-05-11T00:00:00+00:00"^^xsd:dateTime .

  anno:a-broken a oa:Annotation ;
    oa:hasTarget [
      oa:hasSource <source.md> ;
      oa:hasSelector [
        a oa:TextQuoteSelector ;
        oa:exact   "deleted text that does not appear anywhere in the source" ;
        oa:prefix  "" ;
        oa:suffix  ""
      ]
    ] ;
    oa:hasBody         [ a oa:TextualBody ; dc:format "text/plain" ; rdf:value "broken body" ] ;
    oa:motivatedBy     oa:commenting ;
    sci:annotationType "comment" ;
    sci:source         "human:test" ;
    sci:status         "open" ;
    dc:creator         "test" ;
    dc:created         "2026-05-11T00:00:00+00:00"^^xsd:dateTime .
}
```

Create `science/tests/_fixtures/annotation/verify/no-source.anno.trig`:

```
@prefix rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix oa:   <http://www.w3.org/ns/oa#> .
@prefix dc:   <http://purl.org/dc/terms/> .
@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .
@prefix sci:  <http://example.org/science/vocab/> .
@prefix anno: <#> .

anno:annotations {
  anno:a-orphan a oa:Annotation ;
    oa:hasTarget [
      oa:hasSource <does-not-exist.md> ;
      oa:hasSelector [
        a oa:TextQuoteSelector ;
        oa:exact   "anything" ;
        oa:prefix  "" ;
        oa:suffix  ""
      ]
    ] ;
    oa:hasBody         [ a oa:TextualBody ; dc:format "text/plain" ; rdf:value "orphan" ] ;
    oa:motivatedBy     oa:commenting ;
    sci:annotationType "comment" ;
    sci:source         "human:test" ;
    sci:status         "open" ;
    dc:creator         "test" ;
    dc:created         "2026-05-11T00:00:00+00:00"^^xsd:dateTime .
}
```

Create `science/tests/_fixtures/annotation/verify/nested/deep.md`:

```markdown
# Nested fixture

This file's prose was different in an earlier draft.
```

Create `science/tests/_fixtures/annotation/verify/nested/deep.anno.trig`:

```
@prefix rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix oa:   <http://www.w3.org/ns/oa#> .
@prefix dc:   <http://purl.org/dc/terms/> .
@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .
@prefix sci:  <http://example.org/science/vocab/> .
@prefix anno: <#> .

anno:annotations {
  anno:a-nested-broken a oa:Annotation ;
    oa:hasTarget [
      oa:hasSource <deep.md> ;
      oa:hasSelector [
        a oa:TextQuoteSelector ;
        oa:exact   "completely removed sentence from an earlier draft" ;
        oa:prefix  "" ;
        oa:suffix  ""
      ]
    ] ;
    oa:hasBody         [ a oa:TextualBody ; dc:format "text/plain" ; rdf:value "x" ] ;
    oa:motivatedBy     oa:commenting ;
    sci:annotationType "comment" ;
    sci:source         "human:test" ;
    sci:status         "open" ;
    dc:creator         "test" ;
    dc:created         "2026-05-11T00:00:00+00:00"^^xsd:dateTime .
}
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd science && uv run pytest tests/test_annotation_verify.py -v`
Expected: every test fails with `ModuleNotFoundError: No module named
'science_tool.annotation.verify'`.

- [ ] **Step 4: Implement `verify.py`**

```python
# science/src/science_tool/annotation/verify.py
"""Verify orchestration: walk a project, classify selector resolution outcomes.

Pure read-side: parses sidecars, resolves selectors, returns a report.
The write-back path (apply_supersessions) lives next door but is opt-in
and called separately by the CLI's --apply branch.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional

from science_tool.annotation.io import read_sidecar
from science_tool.annotation.model import Sidecar, Status
from science_tool.annotation.selector import (
    ResolutionStatus,
    resolve_selector,
)

# Directory names we never descend into when walking for sidecars.
_SKIP_DIRS: frozenset[str] = frozenset(
    {".git", ".venv", "node_modules", ".worktrees", "worktrees", "__pycache__"}
)

# Issue kinds. Match the spec's wording where possible:
#   "selector-broken" → "broken"
#   "selector-degraded" → "degraded"
#   "selector-fuzzy" → "fuzzy"
# Plus two operational kinds not in the spec but unavoidable in practice:
#   "source-missing" — annotation points at a file that no longer exists
#   "parse-error"    — the sidecar itself failed to parse
ISSUE_KINDS: tuple[str, ...] = ("broken", "degraded", "fuzzy", "source-missing", "parse-error")


@dataclass(frozen=True)
class VerifyIssue:
    sidecar: Path
    annotation_id: str
    source: str
    kind: str
    exact_preview: str

    def __post_init__(self) -> None:
        if self.kind not in ISSUE_KINDS:
            raise ValueError(f"unknown issue kind: {self.kind!r}")


@dataclass(frozen=True)
class VerifyReport:
    sidecars: int
    annotations: int
    superseded_skipped: int
    issues: tuple[VerifyIssue, ...]

    @property
    def broken(self) -> int:
        return sum(1 for i in self.issues if i.kind == "broken")

    @property
    def degraded(self) -> int:
        return sum(1 for i in self.issues if i.kind == "degraded")

    @property
    def fuzzy(self) -> int:
        return sum(1 for i in self.issues if i.kind == "fuzzy")

    @property
    def source_missing(self) -> int:
        return sum(1 for i in self.issues if i.kind == "source-missing")

    @property
    def parse_errors(self) -> int:
        return sum(1 for i in self.issues if i.kind == "parse-error")


def iter_sidecars(root: Path) -> Iterable[Path]:
    """Yield every `*.anno.trig` under `root` in deterministic sorted order.

    Skips a fixed set of noise directories. The yielded paths are absolute.
    """
    out: list[Path] = []
    for path in root.rglob("*.anno.trig"):
        if any(part in _SKIP_DIRS for part in path.parts):
            continue
        out.append(path.resolve())
    out.sort()
    return out


def verify_path(root: Path) -> VerifyReport:
    """Walk `root`, parse every sidecar, classify every annotation."""
    issues: list[VerifyIssue] = []
    sidecar_count = 0
    annotation_count = 0
    superseded_skipped = 0
    source_cache: dict[Path, Optional[str]] = {}

    for sidecar_path in iter_sidecars(root):
        sidecar_count += 1
        try:
            sidecar = read_sidecar(sidecar_path)
        except Exception as exc:  # parse failures must not abort the walk
            issues.append(
                VerifyIssue(
                    sidecar=sidecar_path,
                    annotation_id="",
                    source="",
                    kind="parse-error",
                    exact_preview=_truncate(str(exc), 80),
                )
            )
            continue

        for ann in sidecar.annotations:
            annotation_count += 1
            if ann.status is Status.SUPERSEDED:
                superseded_skipped += 1
                continue

            source_str = ann.target.source
            text = _load_source(sidecar_path, source_str, source_cache)
            preview = _truncate(ann.target.selector.exact, 80)

            if text is None:
                issues.append(
                    VerifyIssue(
                        sidecar=sidecar_path,
                        annotation_id=ann.id,
                        source=source_str,
                        kind="source-missing",
                        exact_preview=preview,
                    )
                )
                continue

            result = resolve_selector(text, ann.target.selector)
            kind = _classify(result.status)
            if kind is None:
                continue
            issues.append(
                VerifyIssue(
                    sidecar=sidecar_path,
                    annotation_id=ann.id,
                    source=source_str,
                    kind=kind,
                    exact_preview=preview,
                )
            )

    return VerifyReport(
        sidecars=sidecar_count,
        annotations=annotation_count,
        superseded_skipped=superseded_skipped,
        issues=tuple(issues),
    )


def _classify(status: ResolutionStatus) -> Optional[str]:
    if status is ResolutionStatus.RESOLVED:
        return None
    if status is ResolutionStatus.DEGRADED:
        return "degraded"
    if status is ResolutionStatus.FUZZY:
        return "fuzzy"
    if status is ResolutionStatus.SUPERSEDED:
        return "broken"
    raise ValueError(f"unhandled resolution status: {status!r}")


def _load_source(
    sidecar_path: Path,
    source: str,
    cache: dict[Path, Optional[str]],
) -> Optional[str]:
    """Resolve and read a source file referenced from a sidecar.

    Returns None when the source is absent or is an absolute (non-file)
    URI. Caches successful and unsuccessful reads alike.
    """
    if "://" in source:
        # v1 supports only relative file paths.
        return None
    resolved = (sidecar_path.parent / source).resolve()
    if resolved in cache:
        return cache[resolved]
    if not resolved.is_file():
        cache[resolved] = None
        return None
    text = resolved.read_text(encoding="utf-8")
    cache[resolved] = text
    return text


def _truncate(s: str, n: int) -> str:
    if len(s) <= n:
        return s
    return s[: n - 1] + "…"
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd science && uv run pytest tests/test_annotation_verify.py -v`
Expected: all tests pass.

- [ ] **Step 6: Run the full project test suite**

Run: `cd science && uv run pytest -q`
Expected: no regressions; new tests included in the count.

- [ ] **Step 7: Commit**

```bash
git add science/src/science_tool/annotation/verify.py \
        science/tests/test_annotation_verify.py \
        science/tests/_fixtures/annotation/verify/
git commit -m "feat(annotate): verify orchestration core (P3.1 task 1)"
```

---

### Task 2: Write-back of `superseded` status

**Files:**
- Modify: `science/src/science_tool/annotation/verify.py` (add `apply_supersessions`)
- Modify: `science/tests/test_annotation_verify.py` (add tests)

**Goal:** Given a `VerifyReport`, mutate every `kind="broken"`
annotation in place via the existing `mutate_status` API and rewrite
only the sidecars that actually changed. Idempotent: a second run on
the same input is a no-op (the broken annotations are now `superseded`
and will be skipped by `verify_path`).

**Design points to encode:**

- `apply_supersessions(report, *, actor, now)` returns the set of
  sidecar paths it rewrote.
- Only `kind="broken"` issues trigger writes; `degraded`, `fuzzy`,
  `source-missing`, `parse-error` are advisory and never auto-mutate.
- Rewrites happen at most once per sidecar even when multiple
  annotations in that sidecar went broken — group issues by sidecar,
  load the sidecar, mutate each annotation, write once.
- Use `dataclasses.replace` on the `Sidecar` to swap in the new
  annotation tuple; preserve `ledgers` and `shared_targets` untouched.

- [ ] **Step 1: Write the failing tests**

Append to `science/tests/test_annotation_verify.py`:

```python
from datetime import datetime, timezone
import shutil

from science_tool.annotation.io import read_sidecar
from science_tool.annotation.model import Status
from science_tool.annotation.verify import apply_supersessions


def test_apply_supersessions_marks_broken_annotations(tmp_path: Path) -> None:
    # Copy the verify fixture so we can mutate freely.
    work = tmp_path / "project"
    shutil.copytree(FIX, work)
    report = verify_path(work)
    assert report.broken >= 1

    now = datetime(2026, 5, 11, 12, 0, tzinfo=timezone.utc)
    rewritten = apply_supersessions(report, actor="ci@science", now=now)

    # source.anno.trig and nested/deep.anno.trig each had a broken row.
    rewritten_names = sorted(p.name for p in rewritten)
    assert "source.anno.trig" in rewritten_names
    assert "deep.anno.trig" in rewritten_names

    # Re-parse and check the broken annotation is now superseded with
    # creator preserved and modified_by recorded.
    sidecar = read_sidecar(work / "source.anno.trig")
    by_id = {a.id: a for a in sidecar.annotations}
    broken = by_id["a-broken"]
    assert broken.status is Status.SUPERSEDED
    assert broken.modified == now
    assert broken.modified_by == "ci@science"
    assert broken.creator == "test"  # preserved from original
    # prov:wasRevisionOf chain captures the prior 'open' state.
    assert len(broken.prior_states) == 1
    assert broken.prior_states[0].status is Status.OPEN

    # Annotations that were not broken are untouched.
    ok = by_id["a-ok"]
    assert ok.status is Status.OPEN
    assert ok.modified is None


def test_apply_supersessions_is_idempotent(tmp_path: Path) -> None:
    work = tmp_path / "project"
    shutil.copytree(FIX, work)
    now = datetime(2026, 5, 11, 12, 0, tzinfo=timezone.utc)
    apply_supersessions(verify_path(work), actor="ci@science", now=now)
    # Second pass: report.broken should now be 0; apply returns empty.
    second_report = verify_path(work)
    assert second_report.broken == 0
    second_rewrites = apply_supersessions(
        second_report, actor="ci@science", now=now
    )
    assert second_rewrites == set()


def test_apply_supersessions_does_not_touch_degraded_or_fuzzy(tmp_path: Path) -> None:
    work = tmp_path / "project"
    shutil.copytree(FIX, work)
    now = datetime(2026, 5, 11, 12, 0, tzinfo=timezone.utc)
    apply_supersessions(verify_path(work), actor="ci@science", now=now)
    sidecar = read_sidecar(work / "source.anno.trig")
    by_id = {a.id: a for a in sidecar.annotations}
    assert by_id["a-degraded"].status is Status.OPEN
    assert by_id["a-fuzzy"].status is Status.OPEN


def test_apply_supersessions_writes_each_sidecar_at_most_once(tmp_path: Path) -> None:
    """Two broken annotations in one sidecar produce one write, not two.

    We assert this by counting file mtimes: after apply, the sidecar's
    mtime moved forward exactly once, even with multiple broken rows.
    Implementation MUST group issues by sidecar before writing.
    """
    work = tmp_path / "project"
    work.mkdir()
    (work / "src.md").write_text("kept paragraph.\n")
    (work / "src.anno.trig").write_text(_two_broken_in_one_sidecar())
    report = verify_path(work)
    assert report.broken == 2
    rewritten = apply_supersessions(
        report,
        actor="ci@science",
        now=datetime(2026, 5, 11, 12, 0, tzinfo=timezone.utc),
    )
    assert len(rewritten) == 1


def _two_broken_in_one_sidecar() -> str:
    return (
        "@prefix rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .\n"
        "@prefix oa:   <http://www.w3.org/ns/oa#> .\n"
        "@prefix dc:   <http://purl.org/dc/terms/> .\n"
        "@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .\n"
        "@prefix sci:  <http://example.org/science/vocab/> .\n"
        "@prefix anno: <#> .\n"
        "anno:annotations {\n"
        "  anno:a-1 a oa:Annotation ;\n"
        "    oa:hasTarget [ oa:hasSource <src.md> ;\n"
        "      oa:hasSelector [ a oa:TextQuoteSelector ;\n"
        '        oa:exact "deleted one" ; oa:prefix "" ; oa:suffix "" ] ] ;\n'
        '    oa:hasBody [ a oa:TextualBody ; dc:format "text/plain" ; rdf:value "x" ] ;\n'
        "    oa:motivatedBy oa:commenting ;\n"
        '    sci:annotationType "comment" ; sci:source "human:test" ;\n'
        '    sci:status "open" ; dc:creator "test" ;\n'
        '    dc:created "2026-05-11T00:00:00+00:00"^^xsd:dateTime .\n'
        "  anno:a-2 a oa:Annotation ;\n"
        "    oa:hasTarget [ oa:hasSource <src.md> ;\n"
        "      oa:hasSelector [ a oa:TextQuoteSelector ;\n"
        '        oa:exact "deleted two" ; oa:prefix "" ; oa:suffix "" ] ] ;\n'
        '    oa:hasBody [ a oa:TextualBody ; dc:format "text/plain" ; rdf:value "y" ] ;\n'
        "    oa:motivatedBy oa:commenting ;\n"
        '    sci:annotationType "comment" ; sci:source "human:test" ;\n'
        '    sci:status "open" ; dc:creator "test" ;\n'
        '    dc:created "2026-05-11T00:00:00+00:00"^^xsd:dateTime .\n'
        "}\n"
    )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science && uv run pytest tests/test_annotation_verify.py -v -k apply`
Expected: all four `apply_supersessions` tests fail with `ImportError`
or `AttributeError`.

- [ ] **Step 3: Implement `apply_supersessions`**

Append to `science/src/science_tool/annotation/verify.py`:

```python
from dataclasses import replace
from datetime import datetime

from science_tool.annotation.io import write_sidecar
from science_tool.annotation.lifecycle import mutate_status


def apply_supersessions(
    report: VerifyReport,
    *,
    actor: str,
    now: datetime,
) -> set[Path]:
    """Mutate broken annotations to status='superseded' and rewrite sidecars.

    Returns the set of sidecar paths that were actually rewritten. Only
    `kind="broken"` issues trigger writes; degraded/fuzzy/source-missing/
    parse-error are advisory and never auto-mutate.
    """
    by_sidecar: dict[Path, set[str]] = {}
    for issue in report.issues:
        if issue.kind != "broken":
            continue
        by_sidecar.setdefault(issue.sidecar, set()).add(issue.annotation_id)

    rewritten: set[Path] = set()
    for sidecar_path, broken_ids in by_sidecar.items():
        sidecar = read_sidecar(sidecar_path)
        new_annotations = tuple(
            mutate_status(ann, Status.SUPERSEDED, actor=actor, now=now)
            if ann.id in broken_ids and ann.status is not Status.SUPERSEDED
            else ann
            for ann in sidecar.annotations
        )
        if new_annotations == sidecar.annotations:
            continue  # nothing actually changed
        new_sidecar = replace(sidecar, annotations=new_annotations)
        write_sidecar(sidecar_path, new_sidecar)
        rewritten.add(sidecar_path)
    return rewritten
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && uv run pytest tests/test_annotation_verify.py -v`
Expected: all tests pass.

- [ ] **Step 5: Run the full project test suite**

Run: `cd science && uv run pytest -q`
Expected: no regressions.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/annotation/verify.py \
        science/tests/test_annotation_verify.py
git commit -m "feat(annotate): apply_supersessions write-back (P3.1 task 2)"
```

---

### Task 3: CLI `science annotate verify` — table output, dry-run default

**Files:**
- Create: `science/src/science_tool/annotation/cli.py`
- Modify: `science/src/science_tool/cli.py` (register `annotate_group`)
- Create: `science/tests/test_annotate_cli.py`

**Goal:** Wire the orchestration core into a Click subcommand. This
task ships the table output path only; the JSON branch lands in Task 4
and `--apply` lands in Task 5. Dry-run is the default, so this task's
CLI never writes to disk.

**CLI shape (this task):**

```
science annotate verify [--root PATH] [--summary-only] [--strict]
```

**Exit codes:**
- 0 — no `broken` issues (degraded / fuzzy / source-missing remain
  warnings; printed but do not fail).
- 1 — at least one `broken` or `parse-error` issue.
- Under `--strict`: also exit 1 when `degraded` or `fuzzy` count > 0
  (matches the `refs check --strict` promotion pattern).

- [ ] **Step 1: Write the failing tests**

```python
# science/tests/test_annotate_cli.py
"""CLI tests for `science annotate verify`."""

from __future__ import annotations

import shutil
from pathlib import Path

from click.testing import CliRunner

from science_tool.annotation.cli import annotate_group

FIX = Path(__file__).parent / "_fixtures" / "annotation" / "verify"


def _seed(tmp_path: Path) -> Path:
    work = tmp_path / "project"
    shutil.copytree(FIX, work)
    return work


def test_verify_table_reports_each_kind(tmp_path: Path) -> None:
    work = _seed(tmp_path)
    result = CliRunner().invoke(annotate_group, ["verify", "--root", str(work)])
    # Broken issues exist → non-zero exit.
    assert result.exit_code == 1, result.output
    assert "broken" in result.output.lower()
    assert "degraded" in result.output.lower()
    assert "fuzzy" in result.output.lower()
    # Per-issue lines reference the sidecar relative path.
    assert "source.anno.trig" in result.output


def test_verify_clean_project_exits_zero(tmp_path: Path) -> None:
    # An empty project (no sidecars at all) is clean.
    result = CliRunner().invoke(
        annotate_group, ["verify", "--root", str(tmp_path)]
    )
    assert result.exit_code == 0, result.output
    assert "0 broken" in result.output or "all clean" in result.output.lower()


def test_verify_summary_only_suppresses_per_issue_lines(tmp_path: Path) -> None:
    work = _seed(tmp_path)
    result = CliRunner().invoke(
        annotate_group, ["verify", "--root", str(work), "--summary-only"]
    )
    assert result.exit_code == 1
    # Issue annotation IDs should not appear in summary-only mode.
    assert "a-broken" not in result.output
    assert "a-degraded" not in result.output
    # But aggregate counts should.
    assert "broken" in result.output.lower()


def test_verify_strict_promotes_degraded_and_fuzzy(tmp_path: Path) -> None:
    """In a fixture with no broken rows but degraded ones, --strict fails."""
    work = tmp_path / "project"
    work.mkdir()
    (work / "s.md").write_text("the bare phrase appears once here.\n")
    (work / "s.anno.trig").write_text(_one_degraded_sidecar())
    # Without --strict: degraded is a warning → exit 0.
    r1 = CliRunner().invoke(annotate_group, ["verify", "--root", str(work)])
    assert r1.exit_code == 0, r1.output
    # With --strict: degraded promoted → exit 1.
    r2 = CliRunner().invoke(
        annotate_group, ["verify", "--root", str(work), "--strict"]
    )
    assert r2.exit_code == 1, r2.output


def test_verify_does_not_write_back_without_apply(tmp_path: Path) -> None:
    work = _seed(tmp_path)
    before = (work / "source.anno.trig").read_text()
    CliRunner().invoke(annotate_group, ["verify", "--root", str(work)])
    after = (work / "source.anno.trig").read_text()
    assert before == after  # dry-run did not mutate the sidecar


def _one_degraded_sidecar() -> str:
    return (
        "@prefix rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .\n"
        "@prefix oa:   <http://www.w3.org/ns/oa#> .\n"
        "@prefix dc:   <http://purl.org/dc/terms/> .\n"
        "@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .\n"
        "@prefix sci:  <http://example.org/science/vocab/> .\n"
        "@prefix anno: <#> .\n"
        "anno:annotations {\n"
        "  anno:a-d a oa:Annotation ;\n"
        "    oa:hasTarget [ oa:hasSource <s.md> ;\n"
        "      oa:hasSelector [ a oa:TextQuoteSelector ;\n"
        '        oa:exact "the bare phrase" ;\n'
        '        oa:prefix "PREFIX_THAT_DOES_NOT_MATCH " ;\n'
        '        oa:suffix " SUFFIX_THAT_DOES_NOT_MATCH" ] ] ;\n'
        '    oa:hasBody [ a oa:TextualBody ; dc:format "text/plain" ; rdf:value "x" ] ;\n'
        "    oa:motivatedBy oa:commenting ;\n"
        '    sci:annotationType "comment" ; sci:source "human:test" ;\n'
        '    sci:status "open" ; dc:creator "test" ;\n'
        '    dc:created "2026-05-11T00:00:00+00:00"^^xsd:dateTime .\n'
        "}\n"
    )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science && uv run pytest tests/test_annotate_cli.py -v`
Expected: every test fails with `ModuleNotFoundError`.

- [ ] **Step 3: Implement the CLI module**

```python
# science/src/science_tool/annotation/cli.py
"""Click CLI group for the `annotate` subcommands.

Phase 3.1 ships the `verify` subcommand. Later phases (P3.2+) will add
`audit`, `lift-tokens`, `list`, `ack`, `dismiss`, `fix`, `render`, and
`stats` to this group.
"""

from __future__ import annotations

from pathlib import Path

import click

from science_tool.annotation.verify import VerifyReport, verify_path


@click.group("annotate")
def annotate_group() -> None:
    """Annotation-system tooling (W3C Web Annotation sidecars)."""


@annotate_group.command("verify")
@click.option(
    "--root",
    "root_path",
    default=".",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Project root to walk for *.anno.trig files.",
)
@click.option(
    "--summary-only",
    is_flag=True,
    help="Print only aggregate counts, not per-issue lines.",
)
@click.option(
    "--strict",
    is_flag=True,
    help="Promote degraded/fuzzy warnings to failures (exit 1).",
)
def verify(root_path: Path, summary_only: bool, strict: bool) -> None:
    """Resolve every annotation's selector against its source; report drift."""
    report = verify_path(root_path.resolve())
    _emit_table(report, summary_only=summary_only)
    _exit_for_report(report, strict=strict)


def _emit_table(report: VerifyReport, *, summary_only: bool) -> None:
    if (
        report.broken == 0
        and report.degraded == 0
        and report.fuzzy == 0
        and report.source_missing == 0
        and report.parse_errors == 0
    ):
        click.echo(
            f"annotate verify: all clean "
            f"({report.annotations} annotations across {report.sidecars} sidecars; "
            f"0 broken, 0 degraded, 0 fuzzy)"
        )
        if report.superseded_skipped:
            click.echo(
                f"  ({report.superseded_skipped} already-superseded annotations skipped)"
            )
        return

    click.echo(
        f"annotate verify: {report.broken} broken, "
        f"{report.degraded} degraded, {report.fuzzy} fuzzy, "
        f"{report.source_missing} source-missing, "
        f"{report.parse_errors} parse-errors "
        f"({report.annotations} annotations across {report.sidecars} sidecars)"
    )
    if report.superseded_skipped:
        click.echo(
            f"  ({report.superseded_skipped} already-superseded annotations skipped)"
        )

    if summary_only:
        return

    for issue in report.issues:
        click.echo(
            f"  [{issue.kind}] {issue.sidecar.name} :: {issue.annotation_id}"
        )
        if issue.source:
            click.echo(f"      source: {issue.source}")
        if issue.exact_preview:
            click.echo(f"      exact:  {issue.exact_preview!r}")


def _exit_for_report(report: VerifyReport, *, strict: bool) -> None:
    if report.broken > 0 or report.parse_errors > 0:
        raise click.exceptions.Exit(1)
    if strict and (report.degraded > 0 or report.fuzzy > 0):
        raise click.exceptions.Exit(1)
```

- [ ] **Step 4: Register the group in the top-level CLI**

Open `science/src/science_tool/cli.py`. Find the existing import block
near line 95-100 (where `markers_cli` and `refs_cli` are imported) and
add the `annotate_group` import alongside them.

Add to the imports:

```python
from science_tool.annotation.cli import annotate_group
```

Find the `main.add_command(...)` block (around line 198-209) and add:

```python
main.add_command(annotate_group)
```

Place it next to the other `add_command` lines; alphabetical order is
not enforced in this file, so insert after `main.add_command(refs_group)`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd science && uv run pytest tests/test_annotate_cli.py -v`
Expected: all five tests pass.

- [ ] **Step 6: Smoke-test the CLI end-to-end**

Run: `cd science && uv run science annotate verify --help`
Expected: usage text printed, exit 0. Quick sanity that the group
registration worked.

Run: `cd science && uv run science annotate verify --root tests/_fixtures/annotation/verify`
Expected: exit 1, table output mentioning the broken/degraded/fuzzy
issues from the fixture.

- [ ] **Step 7: Run the full project test suite**

Run: `cd science && uv run pytest -q`
Expected: no regressions.

- [ ] **Step 8: Commit**

```bash
git add science/src/science_tool/annotation/cli.py \
        science/src/science_tool/cli.py \
        science/tests/test_annotate_cli.py
git commit -m "feat(annotate): verify CLI table output (P3.1 task 3)"
```

---

### Task 4: CLI `--format json` output

**Files:**
- Modify: `science/src/science_tool/annotation/cli.py`
- Modify: `science/tests/test_annotate_cli.py`

**Goal:** Add JSON output for CI consumers. Schema mirrors the layout
that `science refs check --format json` and `science prose lint --format
json` use, so `validate.sh` Section 19 (Task 6) can grep counts the
same way Section 6 and Section 18 do.

**JSON schema:**

```json
{
  "summary": {
    "sidecars": 3,
    "annotations": 5,
    "broken": 2,
    "degraded": 1,
    "fuzzy": 1,
    "source_missing": 1,
    "parse_errors": 0,
    "superseded_skipped": 0
  },
  "issues": [
    {
      "sidecar": "tests/_fixtures/annotation/verify/source.anno.trig",
      "annotation_id": "a-broken",
      "source": "source.md",
      "kind": "broken",
      "exact_preview": "deleted text that does not appear anywhere in the source"
    }
  ]
}
```

`--summary-only` omits the `issues` array entirely. `sidecar` paths are
emitted relative to the supplied `--root` (the same convention
`refs check` uses).

- [ ] **Step 1: Write the failing tests**

Append to `science/tests/test_annotate_cli.py`:

```python
import json


def test_verify_json_schema_summary_keys(tmp_path: Path) -> None:
    work = _seed(tmp_path)
    result = CliRunner().invoke(
        annotate_group, ["verify", "--root", str(work), "--format", "json"]
    )
    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert set(payload.keys()) == {"summary", "issues"}
    summary = payload["summary"]
    assert set(summary.keys()) == {
        "sidecars",
        "annotations",
        "broken",
        "degraded",
        "fuzzy",
        "source_missing",
        "parse_errors",
        "superseded_skipped",
    }
    assert summary["broken"] >= 1
    assert summary["degraded"] >= 1
    assert summary["fuzzy"] >= 1


def test_verify_json_issues_use_relative_sidecar_paths(tmp_path: Path) -> None:
    work = _seed(tmp_path)
    result = CliRunner().invoke(
        annotate_group, ["verify", "--root", str(work), "--format", "json"]
    )
    payload = json.loads(result.output)
    for issue in payload["issues"]:
        # No absolute paths leaked into the JSON.
        assert not issue["sidecar"].startswith("/")
        assert "annotation_id" in issue
        assert "source" in issue
        assert "kind" in issue
        assert issue["kind"] in (
            "broken",
            "degraded",
            "fuzzy",
            "source-missing",
            "parse-error",
        )


def test_verify_json_summary_only_omits_issues_array(tmp_path: Path) -> None:
    work = _seed(tmp_path)
    result = CliRunner().invoke(
        annotate_group,
        ["verify", "--root", str(work), "--format", "json", "--summary-only"],
    )
    payload = json.loads(result.output)
    assert "issues" not in payload
    assert "summary" in payload


def test_verify_json_clean_project(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        annotate_group, ["verify", "--root", str(tmp_path), "--format", "json"]
    )
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["summary"]["broken"] == 0
    assert payload["summary"]["sidecars"] == 0
    assert payload["issues"] == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science && uv run pytest tests/test_annotate_cli.py -v -k json`
Expected: all four JSON tests fail with `Click usage error: no such
option --format`.

- [ ] **Step 3: Implement the JSON branch**

In `science/src/science_tool/annotation/cli.py`:

1. Add the import at the top:

```python
import json

from science_tool.output import OUTPUT_FORMATS
```

2. Add a `--format` option to the `verify` command:

```python
@click.option(
    "--format",
    "output_format",
    type=click.Choice(OUTPUT_FORMATS),
    default="table",
    show_default=True,
)
```

3. Update the `verify` function signature to accept `output_format`,
   and dispatch on it. Note: Task 5 will further extend this signature
   for `--apply`; Task 4's version is the intermediate form.

```python
def verify(
    root_path: Path,
    summary_only: bool,
    strict: bool,
    output_format: str,
) -> None:
    """Resolve every annotation's selector against its source; report drift."""
    root = root_path.resolve()
    report = verify_path(root)
    if output_format == "json":
        _emit_json(report, root=root, summary_only=summary_only)
    else:
        _emit_table(report, summary_only=summary_only)
    _exit_for_report(report, strict=strict)
```

4. Implement `_emit_json`. The `apply_meta` parameter is unused in
   Task 4 (always `None`); Task 5 wires it for the `--apply` branch
   so the JSON consumer sees apply outcomes alongside the summary
   without having human-readable text spliced into the payload.

```python
from typing import Optional


def _emit_json(
    report: VerifyReport,
    *,
    root: Path,
    summary_only: bool,
    apply_meta: Optional[dict[str, int]] = None,
) -> None:
    summary = {
        "sidecars": report.sidecars,
        "annotations": report.annotations,
        "broken": report.broken,
        "degraded": report.degraded,
        "fuzzy": report.fuzzy,
        "source_missing": report.source_missing,
        "parse_errors": report.parse_errors,
        "superseded_skipped": report.superseded_skipped,
    }
    payload: dict[str, object] = {"summary": summary}
    if apply_meta is not None:
        payload["apply"] = apply_meta
    if not summary_only:
        payload["issues"] = [
            {
                "sidecar": _relpath(issue.sidecar, root),
                "annotation_id": issue.annotation_id,
                "source": issue.source,
                "kind": issue.kind,
                "exact_preview": issue.exact_preview,
            }
            for issue in report.issues
        ]
    click.echo(json.dumps(payload, indent=2))


def _relpath(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && uv run pytest tests/test_annotate_cli.py -v`
Expected: all CLI tests (table + JSON) pass.

- [ ] **Step 5: Run the full project test suite**

Run: `cd science && uv run pytest -q`
Expected: no regressions.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/annotation/cli.py \
        science/tests/test_annotate_cli.py
git commit -m "feat(annotate): verify --format json (P3.1 task 4)"
```

---

### Task 5: CLI `--apply` write-back path with `--actor` + clean-tree guard

**Files:**
- Modify: `science/src/science_tool/annotation/cli.py`
- Modify: `science/tests/test_annotate_cli.py`

**Goal:** Add the destructive write-back path. When `--apply` is set,
mutate every `broken` annotation to `superseded` via the Task 2 helper.
Two guardrails:

1. `--actor <email>` is required when `--apply` is set. Verify never
   guesses author identity from git config; the user makes it explicit.
   This matches the spec's stance that supersession is set "by tooling,
   not by author" — the `--actor` value documents *which tooling run*
   applied the change.
2. Clean-tree check: refuse to `--apply` when any `*.anno.trig` file
   under the root has uncommitted changes (`git status --porcelain`
   shows it). This prevents mixing automated supersession into a commit
   that already has unrelated annotation edits. Override with
   `--force-dirty`.

**Exit codes:**
- 0 — `--apply` succeeded (or there was nothing to apply); follow-up
  table/JSON output may still report degraded/fuzzy for visibility, but
  those are advisory and never fail when `--apply` is the user's
  intent.
- 1 — `--apply` was requested but the clean-tree guard rejected it, OR
  `--apply` was set without `--actor`.
- 1 — `--strict` and degraded/fuzzy still present after apply.

**Note on dry-run/apply asymmetry.** Without `--apply`, broken issues
fail (exit 1) — that's the CI signal. With `--apply` and no failures
during the write itself, exit 0 — the user's intent was to fix the
drift, and we did.

- [ ] **Step 1: Write the failing tests**

Append to `science/tests/test_annotate_cli.py`:

```python
import subprocess


def _git_init(work: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=work, check=True)
    subprocess.run(["git", "add", "."], cwd=work, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "-q", "-m", "init"],
        cwd=work,
        check=True,
    )


def test_verify_apply_requires_actor(tmp_path: Path) -> None:
    work = _seed(tmp_path)
    _git_init(work)
    result = CliRunner().invoke(
        annotate_group, ["verify", "--root", str(work), "--apply"]
    )
    assert result.exit_code != 0
    assert "actor" in result.output.lower()


def test_verify_apply_writes_back_supersessions(tmp_path: Path) -> None:
    work = _seed(tmp_path)
    _git_init(work)
    result = CliRunner().invoke(
        annotate_group,
        [
            "verify",
            "--root",
            str(work),
            "--apply",
            "--actor",
            "ci@science",
        ],
    )
    assert result.exit_code == 0, result.output
    # Subsequent dry-run shows zero broken.
    follow = CliRunner().invoke(annotate_group, ["verify", "--root", str(work)])
    assert "0 broken" in follow.output
    # The mutated sidecar carries dc:contributor for the actor.
    text = (work / "source.anno.trig").read_text()
    assert "ci@science" in text
    assert '"superseded"' in text


def test_verify_apply_refuses_dirty_anno_files(tmp_path: Path) -> None:
    work = _seed(tmp_path)
    _git_init(work)
    # Dirty an annotation file before --apply runs.
    (work / "source.anno.trig").write_text(
        (work / "source.anno.trig").read_text() + "\n# dirty\n"
    )
    result = CliRunner().invoke(
        annotate_group,
        [
            "verify",
            "--root",
            str(work),
            "--apply",
            "--actor",
            "ci@science",
        ],
    )
    assert result.exit_code != 0
    assert "dirty" in result.output.lower() or "uncommitted" in result.output.lower()


def test_verify_apply_force_dirty_overrides_guard(tmp_path: Path) -> None:
    work = _seed(tmp_path)
    _git_init(work)
    (work / "source.anno.trig").write_text(
        (work / "source.anno.trig").read_text() + "\n# dirty\n"
    )
    result = CliRunner().invoke(
        annotate_group,
        [
            "verify",
            "--root",
            str(work),
            "--apply",
            "--actor",
            "ci@science",
            "--force-dirty",
        ],
    )
    # The dirty trailer broke the parse for that one sidecar (parse-error),
    # but the other sidecars are still applied. Exit code reflects parse
    # failure (still surfaces broken state via parse-error count).
    # The important assertion: the guard did not refuse the call.
    assert "dirty" not in result.output.lower()


def test_verify_apply_json_emits_pure_json_with_apply_block(tmp_path: Path) -> None:
    """--apply --format json must emit valid JSON only, no human prose mixed in.

    The apply outcome lives under payload["apply"] so JSON consumers
    (CI, validate.sh) can parse it without splitting on free-form lines.
    """
    work = _seed(tmp_path)
    _git_init(work)
    result = CliRunner().invoke(
        annotate_group,
        [
            "verify",
            "--root",
            str(work),
            "--apply",
            "--actor",
            "ci@science",
            "--format",
            "json",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)  # must parse — no prose splice
    assert "apply" in payload
    assert payload["apply"]["rewritten_sidecars"] >= 1
    assert payload["apply"]["superseded_annotations"] >= 1
    # Post-apply broken count is zero in summary.
    assert payload["summary"]["broken"] == 0


def test_verify_apply_exits_nonzero_when_parse_errors_present(tmp_path: Path) -> None:
    """Parse errors are not fixable by --apply, so they remain hard failures.

    Without this test, a malformed sidecar would cause --apply to silently
    pass (the apply branch only re-checked --strict + degraded/fuzzy in an
    earlier draft, which let parse errors slip through).
    """
    work = tmp_path / "project"
    work.mkdir()
    (work / "broken.anno.trig").write_text("not valid trig {{{")
    subprocess.run(["git", "init", "-q"], cwd=work, check=True)
    subprocess.run(["git", "add", "."], cwd=work, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "-q", "-m", "init"],
        cwd=work,
        check=True,
    )
    result = CliRunner().invoke(
        annotate_group,
        [
            "verify",
            "--root",
            str(work),
            "--apply",
            "--actor",
            "ci@science",
        ],
    )
    assert result.exit_code == 1, result.output


def test_verify_apply_zero_broken_is_noop(tmp_path: Path) -> None:
    """When there's nothing broken, --apply still exits 0 and writes nothing."""
    # Empty project.
    result = CliRunner().invoke(
        annotate_group,
        [
            "verify",
            "--root",
            str(tmp_path),
            "--apply",
            "--actor",
            "ci@science",
        ],
    )
    assert result.exit_code == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science && uv run pytest tests/test_annotate_cli.py -v -k apply`
Expected: every test fails (the option doesn't exist yet).

- [ ] **Step 3: Implement the `--apply` path**

In `science/src/science_tool/annotation/cli.py`:

1. Add imports at the top:

```python
import subprocess
from datetime import datetime, timezone

from science_tool.annotation.verify import apply_supersessions
```

2. Add new options to the `verify` command:

```python
@click.option(
    "--apply",
    "apply_changes",
    is_flag=True,
    help="Mutate broken annotations to status='superseded' and rewrite sidecars.",
)
@click.option(
    "--actor",
    type=str,
    default=None,
    help="Required with --apply. Identity recorded as dc:contributor on each mutation.",
)
@click.option(
    "--force-dirty",
    is_flag=True,
    help="Bypass the clean-tree guard when --apply is set.",
)
```

3. Update the `verify` function. This rewrite also DELETES the
   `_exit_for_report` helper added in Task 3 — its policy is folded
   into the unified post-emit exit block at the bottom so apply and
   dry-run share one rule. Search for `def _exit_for_report` and
   remove the function entirely.

```python
def verify(
    root_path: Path,
    summary_only: bool,
    strict: bool,
    output_format: str,
    apply_changes: bool,
    actor: str | None,
    force_dirty: bool,
) -> None:
    """Resolve every annotation's selector against its source; report drift.

    Default is dry-run. With --apply, broken annotations are mutated to
    status='superseded' and their sidecars rewritten. --apply requires
    --actor.
    """
    root = root_path.resolve()

    if apply_changes:
        if not actor:
            raise click.ClickException("--apply requires --actor <identity>")
        if not force_dirty:
            dirty = _dirty_anno_files(root)
            if dirty:
                raise click.ClickException(
                    "Refusing to --apply: the following annotation files have "
                    "uncommitted changes:\n  "
                    + "\n  ".join(sorted(d.as_posix() for d in dirty))
                    + "\nCommit or stash, or pass --force-dirty to override."
                )

    report = verify_path(root)

    rewritten_count = 0
    pre_apply_broken = 0
    if apply_changes:
        pre_apply_broken = report.broken
        rewritten = apply_supersessions(
            report,
            actor=actor,
            now=datetime.now(timezone.utc),
        )
        rewritten_count = len(rewritten)
        # Re-run after apply so the table/JSON reflects the post-mutation
        # state. Broken count drops to 0 (or near-zero if a rewrite raced
        # with a concurrent edit); degraded/fuzzy/parse-errors unchanged.
        report = verify_path(root)

    if output_format == "json":
        _emit_json(
            report,
            root=root,
            summary_only=summary_only,
            apply_meta=(
                {
                    "rewritten_sidecars": rewritten_count,
                    "superseded_annotations": pre_apply_broken,
                }
                if apply_changes
                else None
            ),
        )
    else:
        if apply_changes:
            click.echo(
                f"annotate verify --apply: rewrote {rewritten_count} sidecar(s); "
                f"superseded {pre_apply_broken} broken annotation(s)."
            )
        _emit_table(report, summary_only=summary_only)

    # Unified exit policy. Parse errors and post-apply broken rows are
    # always hard failures (a sidecar that won't parse can't be fixed
    # by --apply, and a still-broken row after apply means something
    # raced or apply_supersessions itself failed silently — either is
    # CI-failure-worthy). Strict additionally promotes degraded/fuzzy.
    if report.broken > 0 or report.parse_errors > 0:
        raise click.exceptions.Exit(1)
    if strict and (report.degraded > 0 or report.fuzzy > 0 or report.source_missing > 0):
        raise click.exceptions.Exit(1)


def _dirty_anno_files(root: Path) -> list[Path]:
    """Return *.anno.trig files with uncommitted changes under `root`.

    Returns an empty list when `root` is not a git repo (we don't
    refuse to apply in non-git contexts; the guard is a convenience for
    CI/dev workflows, not a hard correctness requirement).
    """
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
    except (OSError, FileNotFoundError):
        return []
    if result.returncode != 0:
        return []
    dirty: list[Path] = []
    for line in result.stdout.splitlines():
        # Porcelain format: "XY path\n" — first two chars are status, then space, then path.
        if len(line) < 4:
            continue
        rel = line[3:].strip()
        if rel.endswith(".anno.trig"):
            dirty.append(Path(rel))
    return dirty
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && uv run pytest tests/test_annotate_cli.py -v`
Expected: all CLI tests pass.

- [ ] **Step 5: Run the full project test suite**

Run: `cd science && uv run pytest -q`
Expected: no regressions.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/annotation/cli.py \
        science/tests/test_annotate_cli.py
git commit -m "feat(annotate): verify --apply write-back (P3.1 task 5)"
```

---

### Task 6: `validate.sh` Section 19 + managed-artifact bump

**Files:**
- Modify: `science/src/science_tool/project_artifacts/data/validate.sh`
- Modify: `science/src/science_tool/project_artifacts/registry.yaml`

**Goal:** Wire `science annotate verify` into `validate.sh` as a new
section, and bump the managed-artifact version. Mirrors Sections 6
(`refs check`) and 18 (`prose lint`) — both invoke a `science`
subcommand with `--format json`, parse counts with `python3`, emit
warn/info via the existing helpers, and degrade gracefully when
`SCIENCE_TOOL` is unavailable.

**Section 19 design:**

- Number it Section 19 (Section 18 is the prose-lint check that landed
  in the 2026.05.10.1 bump). Place it after Section 18 in the script.
- Run only when `SCIENCE_TOOL` resolves (the prose-lint section already
  has this guard; copy the pattern). When unavailable, print one
  `info` line ("annotation drift skipped: SCIENCE_TOOL not available")
  and continue.
- Always advisory in the default profile: `warn` for `broken`, `info`
  for `degraded`/`fuzzy`/`source-missing`/`parse-errors`. Under
  `--strict`, all of those promote to `warn`.
- Never invoke `--apply`. Validate is a check; the user runs `science
  annotate verify --apply --actor <me>` deliberately. This matches the
  spec's wording ("invoke `science annotate verify` and report
  `selector-broken` count").
- Use `--summary-only` so the JSON stays small.

**Managed-artifact bump:**

- New version: `2026.05.11.1`
- Compute new SHA-256 of the modified `validate.sh` file
- Append previous version `2026.05.10.2` to `previous_hashes`
- Append migration entry `from: 2026.05.10.2 → to: 2026.05.11.1`,
  `kind: byte_replace`, `summary: 'Add Section 19: annotation drift
  via science annotate verify --format json'`
- Append changelog entry for `2026.05.11.1`

- [ ] **Step 1: Read the current Section 18 and the immediately following block to understand the existing pattern**

Open `science/src/science_tool/project_artifacts/data/validate.sh` and
locate the Section 18 ("Prose lint") block. Note:

- How `SCIENCE_TOOL` is resolved (a helper near the top sets
  `SCIENCE_TOOL` to the resolved binary or empty string).
- How counts are extracted from JSON via `python3 -c`.
- How `warn` and `info` helpers are called.

The new Section 19 follows the identical shape, replacing the command
and the JSON keys.

- [ ] **Step 2: Append Section 19 to `validate.sh`**

After the closing of Section 18 (before the summary block at the end
of the script), insert:

```bash
# ----------------------------------------------------------------------
# Section 19: Annotation drift (`science annotate verify`)
# ----------------------------------------------------------------------
section "19. Annotation drift"

if [ -z "$SCIENCE_TOOL" ]; then
    info "annotation drift skipped: SCIENCE_TOOL not available"
else
    # `science annotate verify` exits 1 when broken/parse-error issues
    # exist; capture stdout with `|| true` (Section 6 pattern) so a
    # nonzero exit doesn't truncate the assignment, then fall back to
    # an empty-summary stub only when stdout was empty (binary missing,
    # crash before output, etc.).
    annotate_json=$($SCIENCE_TOOL annotate verify --root . --format json --summary-only 2>/dev/null) || true
    if [ -z "$annotate_json" ]; then
        annotate_json='{"summary":{"broken":0,"degraded":0,"fuzzy":0,"source_missing":0,"parse_errors":0,"sidecars":0,"annotations":0,"superseded_skipped":0}}'
    fi

    # Extract counts via python3 (matches Section 6/18 pattern).
    annotate_counts=$(python3 -c "
import json, sys
data = json.loads(sys.stdin.read())
s = data.get('summary', {})
print(f\"{s.get('broken', 0)} {s.get('degraded', 0)} {s.get('fuzzy', 0)} {s.get('source_missing', 0)} {s.get('parse_errors', 0)} {s.get('sidecars', 0)} {s.get('annotations', 0)}\")
" <<< "$annotate_json")
    read -r ANNOT_BROKEN ANNOT_DEGRADED ANNOT_FUZZY ANNOT_SRC_MISSING ANNOT_PARSE ANNOT_SIDECARS ANNOT_TOTAL <<< "$annotate_counts"

    if [ "$ANNOT_SIDECARS" = "0" ]; then
        info "no annotation sidecars (*.anno.trig) in this project"
    else
        if [ "$ANNOT_BROKEN" -gt 0 ]; then
            warn "${ANNOT_BROKEN} annotation(s) with broken selectors (run \`science annotate verify --apply --actor <you>\` to mark superseded)"
        fi
        if [ "$ANNOT_PARSE" -gt 0 ]; then
            warn "${ANNOT_PARSE} sidecar parse error(s)"
        fi
        if [ "$ANNOT_DEGRADED" -gt 0 ]; then
            strict_warn "${ANNOT_DEGRADED} annotation(s) with degraded selectors (anchors no longer match)"
        fi
        if [ "$ANNOT_FUZZY" -gt 0 ]; then
            strict_warn "${ANNOT_FUZZY} annotation(s) resolved via fuzzy match"
        fi
        if [ "$ANNOT_SRC_MISSING" -gt 0 ]; then
            strict_warn "${ANNOT_SRC_MISSING} annotation(s) point at missing source files"
        fi
        if [ "$ANNOT_BROKEN" = "0" ] && [ "$ANNOT_PARSE" = "0" ] && [ "$ANNOT_DEGRADED" = "0" ] && [ "$ANNOT_FUZZY" = "0" ] && [ "$ANNOT_SRC_MISSING" = "0" ]; then
            info "${ANNOT_TOTAL} annotation(s) across ${ANNOT_SIDECARS} sidecar(s); all selectors clean"
        fi
    fi
fi
```

Notes:
- `strict_warn` is the helper introduced in version 2026.05.05.2 — it
  emits `info` by default and `warn` under `--strict`. We use it for
  the advisory issue kinds (degraded/fuzzy/source-missing) so they
  promote when the user opts into strict mode.
- `warn` is unconditional for `broken` and `parse-error` — these are
  the spec's CI-failure threshold.
- The Python here-doc tolerates missing keys via `.get(..., 0)` so a
  malformed payload degrades to "all zero" rather than crashing the
  whole validate run.

- [ ] **Step 3: Verify the script still parses and runs**

Run: `bash -n science/src/science_tool/project_artifacts/data/validate.sh`
Expected: exit 0 (script is syntactically valid bash).

- [ ] **Step 4: Recompute the SHA-256 of the modified script**

Run: `sha256sum science/src/science_tool/project_artifacts/data/validate.sh`
Record the hex digest. We'll call it `<NEW_HASH>` below.

- [ ] **Step 5: Update `registry.yaml`**

Open `science/src/science_tool/project_artifacts/registry.yaml`. The
file is a YAML list with one entry per artifact; `validate.sh` is the
first entry. Make four edits:

a. Update `version` from `'2026.05.10.2'` to `'2026.05.11.1'`.

b. Update `current_hash` to `<NEW_HASH>` (the value from Step 4).

c. Prepend a new `previous_hashes` entry. The existing `current_hash`
   value (the one being replaced in step 5b) moves to the top of
   `previous_hashes`. As of this writing the value at line 33 is
   `7dd9b28ddc728071dafd4ab03592cb20ef47c1f08f5be81aab52783245ca3e6a`,
   but if upstream has bumped the artifact again before this plan runs,
   use the actual current value at registry.yaml line 33 instead:

```yaml
      - version: '2026.05.10.2'
        hash: 7dd9b28ddc728071dafd4ab03592cb20ef47c1f08f5be81aab52783245ca3e6a
```

The list is ordered with newest at the top, oldest at the bottom;
insert at the top of that list.

d. Append a new migration entry to the `migrations` list (newest at
   the bottom, matching the existing pattern):

```yaml
      - from: '2026.05.10.2'
        to: '2026.05.11.1'
        kind: byte_replace
        summary: 'Add Section 19: annotation drift via `science annotate verify --format json`.'
        steps: []
```

e. Append a changelog entry to the `changelog` mapping:

```yaml
      '2026.05.11.1': 'Section 19 (Annotation drift): invokes `science annotate verify --format json --summary-only` and reports broken / degraded / fuzzy / source-missing / parse-error counts. Broken and parse-errors warn unconditionally; the rest promote under --strict (via `strict_warn`).'
```

- [ ] **Step 6: Verify the registry parses and the artifact validates**

Run: `cd science && uv run pytest tests/test_acceptance_managed_artifacts.py -v`
Expected: pass. The acceptance test re-hashes the artifact source and
checks it matches `current_hash`.

- [ ] **Step 7: Run the full project test suite**

Run: `cd science && uv run pytest -q`
Expected: no regressions.

- [ ] **Step 8: Smoke-test validate.sh against an empty temp directory**

Run validate against a clean temp dir so the test fixtures created by
this plan don't pollute the smoke output:

```bash
SMOKE=$(mktemp -d)
cd "$SMOKE"
git init -q
SCIENCE_TOOL="$(command -v science || true)" \
    bash "$OLDPWD/science/src/science_tool/project_artifacts/data/validate.sh" || true
```

Expected: Section 19 prints "no annotation sidecars (*.anno.trig) in
this project" (the temp dir has no sidecars). Verify the section runs
without shell errors. Exit code is non-zero because other sections
(refs check, etc.) will object to the bare temp dir; that's fine — we
only care that Section 19 itself is clean and the script parses.

**Why an isolated dir, not the science repo root.** The fixtures
created by Task 1 (`science/tests/_fixtures/annotation/verify/*.anno.trig`)
are *intentionally broken* and live inside the science package. Running
validate.sh from any ancestor of those fixtures will discover them and
report broken / degraded / fuzzy / source-missing / parse-error counts.
That is correct behavior (the sidecars are genuinely broken) but it
makes the smoke test noisy. The temp-dir approach exercises the empty-
project path, which is the more useful smoke for "did the section
itself run without bash errors."

If you want to additionally smoke-test the populated path, run:

```bash
$SCIENCE_TOOL annotate verify --root science/tests/_fixtures/annotation/verify --format json --summary-only
```

Expected: a JSON payload with non-zero broken/degraded/fuzzy counts.
This bypasses validate.sh and exercises the CLI directly.

- [ ] **Step 9: Commit**

```bash
git add science/src/science_tool/project_artifacts/data/validate.sh \
        science/src/science_tool/project_artifacts/registry.yaml
git commit -m "feat(validate): Section 19 annotation drift; bump to 2026.05.11.1 (P3.1 task 6)"
```

---

## Self-review

After finishing all six tasks, the implementer should re-read this plan
against the spec sections referenced at the top:

- §Span addressing — selector resolution semantics: covered by
  delegating to `resolve_selector` (P3.0); P3.1 adds no new resolution
  logic, only walks all annotations.
- §Status lifecycle — `* → superseded` transition: implemented via
  `mutate_status(... SUPERSEDED ...)` in `apply_supersessions`.
  `creator` preservation, `modified_by` recording, and
  `prov:wasRevisionOf` chain all fall out of the existing
  lifecycle.py — Task 2 tests assert each.
- §Verify loop (CI drift detection): the `verify` command's exit
  policy implements the spec's "CI failure threshold is
  selector-broken count > 0", with `--strict` extending the threshold
  per the existing `refs check --strict` precedent.
- §`validate.sh` integration: Section 19 + managed-artifact bump.
- §CLI surface: `science annotate verify --root <path>` row, with
  `--format`, `--summary-only`, `--strict`, `--apply`, `--actor`,
  `--force-dirty` consistent with the rest of the `science` CLI.
  Positional `[<path>]` deliberately not added — see Spec references
  note above.

Out-of-scope reminders (do NOT add):

- `science annotate audit / lift-tokens / list / ack / dismiss / fix /
  render / stats` — defer to P3.2-P3.4.
- `--since <git-ref>` paragraph-scope filtering — defer.
- Any LLM call — defer to P3.5.
- Graph-ingest of sidecars into `knowledge/graph.trig` — defer to P3.6.

## Cross-references

- `plan:2026-05-10-annotation-system-spec` — the spec being implemented.
- `plan:2026-05-11-annotation-system-p3.0` — predecessor plan (data
  model + sidecar I/O); P3.1 builds directly on its public surface.
- `docs/conventions/refs-check.md` — `refs check` is the structural
  precedent for the JSON-payload + validate.sh-section pattern that
  P3.1 follows.
- `docs/plans/historical/2026-04-26-managed-artifacts-long-term-design.md`
  — managed-artifact bump procedure (registry.yaml fields).

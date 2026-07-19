# Skills Provenance Coverage — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring every canonical skill under `skills/` to an explicit provenance
declaration — registered external `sources:` or `provenance: internal` — and
teach the skills linter to enforce coverage, WARN first and ratcheted to ERROR
once the corpus is clean.

**Architecture:** Three infrastructure changes to the skills linter
(source-kind taxonomy + `leaf_source_refs` strengthening; an issue-severity
model; a provenance classifier + coverage check), then a five-wave sweep that
declares all 36 currently-undeclared files and extends `skills/sources.yaml`,
then a repository coverage test, then the WARN→ERROR ratchet.

**Tech Stack:** Python ≥3.11, `click`, `PyYAML`, `pytest`. All CLI/lint work
runs from `science/` (`science/pyproject.toml`).

**Design reference:** `docs/plans/2026-07-18-skills-provenance-coverage-design.md`.

## Global Constraints

- Run all commands from `science/`: `uv run --frozen pytest`,
  `uv run ruff check`, `uv run pyright`. Default pytest excludes `snapshot` /
  `real_projects` markers.
- Python floor is 3.11. Test directories are not type-checked by pyright.
- No AI-attribution trailers on commits (no `Co-Authored-By`, no "Generated
  with" footer). Use `~/d/` in any doc/code path text.
- **WARN-first:** `missing-provenance` is emitted at
  `MISSING_PROVENANCE_SEVERITY`, initialized `"warn"`. The ratchet to `"error"`
  is the **final task**, valid only after the corpus is swept to zero
  `missing-provenance`.
- **Severity default is `"error"`** on `SkillIssue`; every pre-existing finding
  stays ERROR. Exit code is nonzero iff any finding is ERROR-severity; a
  WARN-only run exits 0.
- **Text render order is a CLI contract:**
  `"<severity>: <path>: <kind>[: <field>][: <detail>]"` — severity leading,
  lowercase (`error` / `warn`).
- **Scope:** every `skills/**/*.md` **except `skills/INDEX.md`**. `codex-skills/`
  is out of scope (linter defaults to `--root skills`).
- **`provenance: internal`** means the document's substantive guidance is a
  Science-native convention **not materially derived from an external source**.
  Being maintained in this repo does not make externally-informed guidance
  internal. A router (`SKILL.md`) that materially summarizes external methods
  uses `sources:`.
- **Kind boundary:** `software` = reference to a tool/library/API/service, no
  pinned revision, freshness `not_applicable`. `package-docs` = material adapted
  from a specific repo revision, Git-backed (`upstream_ref`). Never use
  `software` to pin a revision.
- Each sweep wave must leave `science skills lint` exiting 0 (WARN-only) with
  **zero** `invalid-source-record` / `unknown-source-ref` / `invalid-provenance`
  / `invalid-field` findings for the files it touched.

---

## File Structure

- `science/src/science_tool/skills_lint/sources.py` — add `spec`, `software` to
  `REFERENCE_KINDS`; strengthen `leaf_source_refs`; rename `_leaf_frontmatter`
  → public `leaf_frontmatter`.
- `science/src/science_tool/skills_lint/lint.py` — `Severity` type + `severity`
  field on `SkillIssue` (+ `to_json`); `_relative_issues` copies `severity`;
  `missing-provenance` + `invalid-provenance` issue kinds;
  `MISSING_PROVENANCE_SEVERITY` constant; `classify_provenance` +
  `check_provenance`; `check_skills` integration with `INDEX.md` exclusion.
- `science/src/science_tool/skills_lint/cli.py` — severity-leading text render;
  `_has_error` exit helper; severity-aware exit code.
- `skills/sources.yaml` — new `spec` / `software` / `paper` / `book` records
  surfaced by the sweep.
- `skills/**/*.md` — 36 files gain `sources:` or `provenance: internal`.
- `science/tests/skills_lint/` — new + updated tests per task.

---

## Task 1: Source-kind taxonomy + `leaf_source_refs` strengthening

**Files:**
- Modify: `science/src/science_tool/skills_lint/sources.py`
- Test: `science/tests/skills_lint/test_sources.py`

**Interfaces:**
- Produces: `REFERENCE_KINDS` now includes `"spec"`, `"software"`; public
  `leaf_frontmatter(path: Path) -> dict[str, Any] | None`; `leaf_source_refs`
  rejects empty/blank `sources`.
- Consumes: nothing from other tasks.

- [ ] **Step 1: Write failing tests for the new kinds and strengthening**

Add to `science/tests/skills_lint/test_sources.py`:

```python
def test_spec_and_software_kinds_validate() -> None:
    from science_tool.skills_lint.sources import validate_record
    base = {
        "title": "Frictionless Data Package",
        "authors": ["Frictionless Data"],
        "url": "https://specs.frictionlessdata.io/data-package/",
        "last_checked": "2026-07-18",
    }
    assert validate_record("frictionless-spec", {**base, "kind": "spec"}) == []
    assert validate_record("snakemake-tool", {**base, "kind": "software"}) == []


def test_spec_software_reject_upstream_ref() -> None:
    from science_tool.skills_lint.sources import validate_record
    rec = {
        "title": "T", "authors": ["A"], "url": "https://example.org/x",
        "last_checked": "2026-07-18", "kind": "software",
        "upstream_ref": "a" * 40,
    }
    problems = validate_record("x", rec)
    assert any("must not set upstream_ref" in p for p in problems)


def test_leaf_source_refs_rejects_empty_and_blank(tmp_path) -> None:
    from science_tool.skills_lint.sources import leaf_source_refs
    empty = tmp_path / "empty.md"
    empty.write_text("---\nname: x\ndescription: d\nsources: []\n---\n# X\n", encoding="utf-8")
    refs, err = leaf_source_refs(empty)
    assert refs is None and err is not None

    blank = tmp_path / "blank.md"
    blank.write_text('---\nname: x\ndescription: d\nsources: ["  "]\n---\n# X\n', encoding="utf-8")
    refs, err = leaf_source_refs(blank)
    assert refs is None and err is not None

    ok = tmp_path / "ok.md"
    ok.write_text("---\nname: x\ndescription: d\nsources: [real-id]\n---\n# X\n", encoding="utf-8")
    refs, err = leaf_source_refs(ok)
    assert refs == ["real-id"] and err is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science && uv run --frozen pytest tests/skills_lint/test_sources.py -k "spec_and_software or upstream_ref or empty_and_blank" -v`
Expected: FAIL (`spec`/`software` not valid kinds; empty/blank accepted).

- [ ] **Step 3: Add the kinds**

In `sources.py`, extend `REFERENCE_KINDS`:

```python
REFERENCE_KINDS = frozenset({"book", "paper", "course", "spec", "software"})
```

(`VALID_KINDS = GIT_BACKED_KINDS | REFERENCE_KINDS` picks them up automatically;
the existing `elif kind in REFERENCE_KINDS and "upstream_ref" in raw` guard at
`sources.py:134` now rejects `upstream_ref` on `spec`/`software` for free.)

- [ ] **Step 4: Strengthen `leaf_source_refs` and expose `leaf_frontmatter`**

Rename `_leaf_frontmatter` to `leaf_frontmatter` (public) and update
`leaf_source_refs`:

```python
def leaf_frontmatter(path: Path) -> dict[str, Any] | None:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---\n", 4)
    if end == -1:
        return None
    try:
        parsed = yaml.safe_load(text[4:end]) or {}
    except yaml.YAMLError:
        return None
    return parsed if isinstance(parsed, dict) else None


def leaf_source_refs(path: Path) -> tuple[list[str] | None, str | None]:
    frontmatter = leaf_frontmatter(path)
    if frontmatter is None or "sources" not in frontmatter:
        return None, None
    raw = frontmatter["sources"]
    if (
        not isinstance(raw, list)
        or not raw
        or not all(isinstance(x, str) and x.strip() for x in raw)
    ):
        return None, "sources must be a non-empty list of non-blank strings"
    return list(raw), None
```

- [ ] **Step 5: Run the full sources suite**

Run: `cd science && uv run --frozen pytest tests/skills_lint/test_sources.py tests/skills_lint/test_sources_cli.py tests/skills_lint/test_sources_registry_repo.py -q`
Expected: PASS.

- [ ] **Step 6: Lint + types**

Run: `cd science && uv run ruff check && uv run pyright`
Expected: clean.

- [ ] **Step 7: Commit**

```bash
git add science/src/science_tool/skills_lint/sources.py science/tests/skills_lint/test_sources.py
git commit -m "feat(skills): add spec/software source kinds; require non-empty sources"
```

---

## Task 2: Issue-severity model

**Files:**
- Modify: `science/src/science_tool/skills_lint/lint.py`
- Modify: `science/src/science_tool/skills_lint/cli.py`
- Test: `science/tests/skills_lint/test_lint.py`

**Interfaces:**
- Produces: `Severity = Literal["error", "warn"]`; `SkillIssue.severity`
  (default `"error"`) surfaced in `to_json`; `_relative_issues` preserves
  `severity`; `cli._has_error(issues) -> bool`; severity-leading text render.
- Consumes: nothing from Task 1.

- [ ] **Step 1: Update the JSON test and add severity plumbing tests**

In `test_lint.py`, update `test_skill_issue_json_uses_posix_path` to expect the
new key, and add plumbing tests:

```python
def test_skill_issue_json_uses_posix_path() -> None:
    issue = SkillIssue(Path("nested") / "bad.md", "missing-frontmatter")
    assert issue.to_json() == {
        "path": "nested/bad.md",
        "kind": "missing-frontmatter",
        "field": None,
        "detail": "",
        "severity": "error",
    }


def test_skill_issue_defaults_to_error_severity() -> None:
    assert SkillIssue(Path("x.md"), "missing-frontmatter").severity == "error"


def test_relative_issues_preserves_severity() -> None:
    from science_tool.skills_lint.lint import _relative_issues
    root = Path("/root")
    warn = SkillIssue(root / "leaf.md", "missing-provenance", severity="warn")
    out = _relative_issues([warn], root)
    assert out[0].severity == "warn"
    assert out[0].path == Path("leaf.md")


def test_has_error_is_severity_aware() -> None:
    from science_tool.skills_lint.cli import _has_error
    warn = SkillIssue(Path("a.md"), "missing-provenance", severity="warn")
    err = SkillIssue(Path("b.md"), "missing-frontmatter")
    assert _has_error([]) is False
    assert _has_error([warn]) is False
    assert _has_error([warn, err]) is True


def test_text_render_leads_with_severity() -> None:
    from science_tool.skills_lint.cli import _format_text_issue
    warn = SkillIssue(Path("leaf.md"), "missing-provenance", severity="warn")
    assert _format_text_issue(warn) == "warn: leaf.md: missing-provenance"
```

Note: `missing-provenance` as an `IssueKind` value is added in Task 3; for Task 2
these tests only construct `SkillIssue` with that string. Add `"missing-provenance"`
to the `IssueKind` union now (a Literal member is inert until emitted) so the
constructions type-check — or add it in Task 3 and run these tests after Task 3.
Add it now.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science && uv run --frozen pytest tests/skills_lint/test_lint.py -k "json_uses_posix or defaults_to_error or preserves_severity or has_error or leads_with_severity" -v`
Expected: FAIL (no `severity` field/key; `_has_error` absent).

- [ ] **Step 3: Add severity to `SkillIssue` and `IssueKind`**

In `lint.py`:

```python
Severity = Literal["error", "warn"]

IssueKind = Literal[
    "missing-frontmatter",
    "invalid-yaml",
    "missing-field",
    "invalid-field",
    "missing-section",
    "broken-relative-link",
    "missing-index-entry",
    "unknown-source-ref",
    "invalid-source-record",
    "missing-provenance",
    "invalid-provenance",
]


@dataclass(frozen=True)
class SkillIssue:
    path: Path
    kind: IssueKind
    field: str | None = None
    detail: str = ""
    severity: Severity = "error"

    def to_json(self) -> dict[str, str | None]:
        return {
            "path": self.path.as_posix(),
            "kind": self.kind,
            "field": self.field,
            "detail": self.detail,
            "severity": self.severity,
        }
```

- [ ] **Step 4: Preserve severity through `_relative_issues`**

```python
def _relative_issues(issues: list[SkillIssue], root: Path) -> list[SkillIssue]:
    return [
        SkillIssue(
            path=issue.path.relative_to(root),
            kind=issue.kind,
            field=issue.field,
            detail=issue.detail,
            severity=issue.severity,
        )
        for issue in issues
    ]
```

- [ ] **Step 5: Severity-leading render + severity-aware exit in `cli.py`**

```python
def _format_text_issue(issue: SkillIssue) -> str:
    parts = [issue.severity, issue.path.as_posix(), issue.kind]
    if issue.field is not None:
        parts.append(issue.field)
    if issue.detail:
        parts.append(issue.detail)
    return ": ".join(parts)


def _has_error(issues: list[SkillIssue]) -> bool:
    return any(issue.severity == "error" for issue in issues)
```

In `lint_cmd`, replace `if issues: raise click.exceptions.Exit(1)` with:

```python
    if _has_error(issues):
        raise click.exceptions.Exit(1)
```

- [ ] **Step 6: Run the skills_lint suite**

Run: `cd science && uv run --frozen pytest tests/skills_lint/ -q`
Expected: PASS (existing `test_lint_cli_against_fixtures` still passes — no
`missing-provenance` is emitted yet, so the fixture output is unchanged and exit
stays 1 from the ERROR fixtures).

- [ ] **Step 7: Lint + types**

Run: `cd science && uv run ruff check && uv run pyright`
Expected: clean.

- [ ] **Step 8: Commit**

```bash
git add science/src/science_tool/skills_lint/lint.py science/src/science_tool/skills_lint/cli.py science/tests/skills_lint/test_lint.py
git commit -m "feat(skills): add issue-severity model + severity-aware exit"
```

---

## Task 3: Provenance classifier + coverage check

**Files:**
- Modify: `science/src/science_tool/skills_lint/lint.py`
- Modify: `science/tests/skills_lint/fixtures/good.md`,
  `good-with-companion.md`, `good-deep-reference.md`,
  `data/embeddings-manifold-qa.md`
- Test: `science/tests/skills_lint/test_lint.py`

**Interfaces:**
- Consumes: `leaf_frontmatter` (Task 1); `Severity`, `severity`,
  `MISSING_PROVENANCE_SEVERITY` (Task 2 + here).
- Produces: `classify_provenance(frontmatter: dict) -> ProvenanceState`;
  `check_provenance(path: Path) -> list[SkillIssue]`; `check_skills` emits
  `missing-provenance` (WARN) / `invalid-provenance` (ERROR), `INDEX.md`
  excluded.

- [ ] **Step 1: Write failing classifier + integration tests**

Add to `test_lint.py`:

```python
def _leaf(dirpath: Path, name: str, body: str) -> Path:
    p = dirpath / name
    p.write_text(body, encoding="utf-8")
    return p


def test_classify_provenance_four_outcomes() -> None:
    from science_tool.skills_lint.lint import classify_provenance
    assert classify_provenance({"sources": ["a"]}) == "attributed"
    assert classify_provenance({"provenance": "internal"}) == "internal"
    assert classify_provenance({"name": "x"}) == "undeclared"
    assert classify_provenance({"sources": ["a"], "provenance": "internal"}) == "contradiction"
    assert classify_provenance({"provenance": "external"}) == "bad-marker"


def test_undeclared_leaf_yields_warn(tmp_path: Path) -> None:
    from science_tool.skills_lint.lint import check_provenance
    leaf = _leaf(tmp_path, "leaf.md", "---\nname: x\ndescription: d\n---\n# X\n")
    issues = check_provenance(leaf)
    assert len(issues) == 1
    assert issues[0].kind == "missing-provenance"
    assert issues[0].severity == "warn"


def test_internal_and_attributed_yield_no_coverage_finding(tmp_path: Path) -> None:
    from science_tool.skills_lint.lint import check_provenance
    internal = _leaf(tmp_path, "i.md", "---\nname: x\ndescription: d\nprovenance: internal\n---\n# X\n")
    attributed = _leaf(tmp_path, "a.md", "---\nname: x\ndescription: d\nsources: [known]\n---\n# X\n")
    assert check_provenance(internal) == []
    assert check_provenance(attributed) == []


def test_contradiction_and_bad_marker_yield_invalid_provenance(tmp_path: Path) -> None:
    from science_tool.skills_lint.lint import check_provenance
    both = _leaf(tmp_path, "b.md", "---\nname: x\ndescription: d\nsources: [k]\nprovenance: internal\n---\n# X\n")
    bad = _leaf(tmp_path, "m.md", "---\nname: x\ndescription: d\nprovenance: nope\n---\n# X\n")
    for leaf in (both, bad):
        issues = check_provenance(leaf)
        assert len(issues) == 1
        assert issues[0].kind == "invalid-provenance"
        assert issues[0].severity == "error"


def test_no_cascade_on_broken_frontmatter(tmp_path: Path) -> None:
    from science_tool.skills_lint.lint import check_provenance
    nofm = _leaf(tmp_path, "n.md", "# no frontmatter\n")
    assert check_provenance(nofm) == []


def test_missing_provenance_not_double_reported_with_unknown_ref(tmp_path: Path) -> None:
    skills_root = tmp_path / "skills"
    skills_root.mkdir()
    (skills_root / "sources.yaml").write_text("", encoding="utf-8")
    (skills_root / "INDEX.md").write_text("`skills/leaf.md`\n", encoding="utf-8")
    (skills_root / "leaf.md").write_text(
        "---\nname: leaf\ndescription: d\nsources: [ghost]\n---\n# Leaf\n## Companion Skills\n- none\n",
        encoding="utf-8",
    )
    from science_tool.skills_lint.lint import check_skills
    kinds = {i.kind for i in check_skills(skills_root)}
    assert "unknown-source-ref" in kinds
    assert "missing-provenance" not in kinds  # sources present => attributed, not undeclared


def test_index_md_excluded_from_coverage(tmp_path: Path) -> None:
    skills_root = tmp_path / "skills"
    skills_root.mkdir()
    # INDEX.md has valid frontmatter but no declaration; must NOT be flagged.
    (skills_root / "INDEX.md").write_text(
        "---\nname: idx\ndescription: d\n---\n# Index\n`skills/leaf.md`\n## Companion Skills\n- none\n",
        encoding="utf-8",
    )
    (skills_root / "leaf.md").write_text(
        "---\nname: leaf\ndescription: d\nprovenance: internal\n---\n# Leaf\n## Companion Skills\n- none\n",
        encoding="utf-8",
    )
    from science_tool.skills_lint.lint import check_skills
    provenance_paths = {i.path.as_posix() for i in check_skills(skills_root) if i.kind == "missing-provenance"}
    assert provenance_paths == set()


def test_warn_only_run_exits_zero(tmp_path: Path) -> None:
    import json
    from click.testing import CliRunner
    from science_tool.cli import main
    skills_root = tmp_path / "skills"
    skills_root.mkdir()
    # INDEX.md itself must be error-free (valid frontmatter + companion section +
    # it indexes leaf.md), so the ONLY finding is leaf.md's WARN.
    (skills_root / "INDEX.md").write_text(
        "---\nname: idx\ndescription: d\n---\n# Index\n`skills/leaf.md`\n## Companion Skills\n- none\n",
        encoding="utf-8",
    )
    (skills_root / "leaf.md").write_text(
        "---\nname: leaf\ndescription: d\n---\n# Leaf\n## Companion Skills\n- none\n",
        encoding="utf-8",
    )
    result = CliRunner().invoke(main, ["skills", "lint", "--root", str(skills_root), "--format", "json"])
    assert result.exit_code == 0  # WARN-only => exit 0
    kinds = {(i["kind"], i["severity"]) for i in json.loads(result.output)["issues"]}
    assert ("missing-provenance", "warn") in kinds  # severity reported in JSON
```

- [ ] **Step 2: Run to verify failure**

Run: `cd science && uv run --frozen pytest tests/skills_lint/test_lint.py -k "classify or undeclared or internal_and_attributed or contradiction or no_cascade or not_double or index_md_excluded or warn_only" -v`
Expected: FAIL (`classify_provenance` / `check_provenance` absent).

- [ ] **Step 3: Implement the classifier and coverage check**

In `lint.py`, add the import and functions:

```python
from science_tool.skills_lint.sources import (
    SourcesRegistry,
    leaf_frontmatter,
    leaf_source_refs,
    load_sources,
)

MISSING_PROVENANCE_SEVERITY: Severity = "warn"

ProvenanceState = Literal[
    "attributed", "internal", "undeclared", "contradiction", "bad-marker"
]


def classify_provenance(frontmatter: dict) -> ProvenanceState:
    has_sources = "sources" in frontmatter
    has_provenance = "provenance" in frontmatter
    if has_sources and has_provenance:
        return "contradiction"
    if has_sources:
        return "attributed"  # source-ref check owns list validity
    if has_provenance:
        return "internal" if frontmatter.get("provenance") == "internal" else "bad-marker"
    return "undeclared"


def check_provenance(path: Path) -> list[SkillIssue]:
    frontmatter = leaf_frontmatter(path)
    if frontmatter is None:
        return []  # missing/unparsable frontmatter already reported; no cascade
    state = classify_provenance(frontmatter)
    if state == "undeclared":
        return [SkillIssue(path, "missing-provenance", severity=MISSING_PROVENANCE_SEVERITY)]
    if state == "contradiction":
        return [SkillIssue(path, "invalid-provenance", detail="sources: and provenance: are mutually exclusive")]
    if state == "bad-marker":
        value = frontmatter.get("provenance")
        return [SkillIssue(path, "invalid-provenance", field="provenance", detail=f"unknown value {value!r}; only 'internal' is allowed")]
    return []
```

- [ ] **Step 4: Integrate into `check_skills`, excluding `INDEX.md`**

In the per-path loop of `check_skills`, add coverage for every file except the
corpus index:

```python
    for path in sorted(root.rglob("*.md")):
        issues.extend(_relative_issues(check_frontmatter(path), root))
        issues.extend(_relative_issues(check_companion_skills(path), root))
        issues.extend(_relative_issues(check_halt_on_conditions(path, root), root))
        issues.extend(_relative_issues(check_relative_links(path), root))
        issues.extend(_relative_issues(check_source_refs(path, registry), root))
        if path != root / "INDEX.md":
            issues.extend(_relative_issues(check_provenance(path), root))
    issues.extend(check_index_coverage(root))
```

- [ ] **Step 5: Declare the four "good" fixtures**

The full-tree CLI test asserts the "good" fixtures produce no output. Add
`provenance: internal` to each fixture's frontmatter so they stay clean:

- `science/tests/skills_lint/fixtures/good.md`
- `science/tests/skills_lint/fixtures/good-with-companion.md`
- `science/tests/skills_lint/fixtures/good-deep-reference.md`
- `science/tests/skills_lint/fixtures/data/embeddings-manifold-qa.md`

For each, insert `provenance: internal` as a frontmatter line (e.g. after the
`description:` line, before the closing `---`). Example for `good.md`:

```markdown
---
name: good-skill
description: A well-formed skill fixture.
provenance: internal
---
```

(Read each fixture first and preserve its existing keys; only add the one line.)

- [ ] **Step 6: Run to verify pass, including the untouched fixture CLI test**

Run: `cd science && uv run --frozen pytest tests/skills_lint/ -q`
Expected: PASS. `test_lint_cli_against_fixtures` still passes: `good.md`,
`good-with-companion.md`, `good-deep-reference.md`,
`data/embeddings-manifold-qa.md` now declare `provenance: internal` (no
`missing-provenance`); the bad fixtures still appear for their ERROR findings.

- [ ] **Step 7: Confirm real-corpus behavior (WARN, exit 0)**

Run: `cd science && uv run --frozen python -c "from pathlib import Path; from collections import Counter; from science_tool.skills_lint.lint import check_skills; c=Counter(i.kind for i in check_skills(Path('../skills'))); print(c)"`
Expected: `Counter({'missing-provenance': 36})` (INDEX.md excluded; no ERROR
kinds). Confirms the sweep target is exactly 36.

- [ ] **Step 8: Lint + types + commit**

Run: `cd science && uv run ruff check && uv run pyright`

```bash
git add science/src/science_tool/skills_lint/lint.py science/tests/skills_lint/
git commit -m "feat(skills): enforce provenance coverage (WARN) with a declaration classifier"
```

---

## Sweep waves (Tasks 4–8)

**Shared method for every wave.** For each file:

1. Read the file. Decide `internal` vs external per the Global-Constraints
   definition of `provenance: internal` (Science-native convention vs.
   materially derived from an external tool/spec/method).
2. **Internal** → add one frontmatter line `provenance: internal`.
3. **External** → add `sources: [id, …]`; ensure each id has a record in
   `skills/sources.yaml`. New records follow this schema (reference-style, no
   `upstream_ref`):

   ```yaml
   <id>:
     title: "<canonical title>"
     authors: ["<author or org>"]
     url: "https://<canonical https url>"
     kind: <paper|book|spec|software>
     last_checked: "2026-07-18"
     doi: "<10....>"        # papers, when available
     isbn: "<digits>"       # books, when available
   ```

   **Citation identifiers must be verified during execution** (WebSearch / known
   DOIs), not invented. The tables below name each source's identity and kind;
   execution finalizes the exact `url` / `doi` / `isbn`. This research is
   well-suited to parallel subagents; the controller curates the registry.
4. Do **not** modify the 5 already-attributed statistics leaves unless research
   adds a citation.

**Per-wave verification (identical shape).** After editing a wave's files:

```bash
cd science && uv run --frozen python -c "
from pathlib import Path
from science_tool.skills_lint.lint import check_skills
issues = check_skills(Path('../skills'))
bad = [(i.path.as_posix(), i.kind, i.detail) for i in issues
       if i.kind in {'invalid-source-record','unknown-source-ref','invalid-provenance','invalid-field'}]
mp = sorted(i.path.as_posix() for i in issues if i.kind == 'missing-provenance')
print('ERRORS:', bad)
print('remaining missing-provenance:', len(mp))
"
```
Expected: `ERRORS: []` and `remaining missing-provenance` decreased by exactly
the count of files this wave declared. Then
`cd science && uv run --frozen pytest tests/skills_lint/test_sources_registry_repo.py -q`
(registry still valid), and commit.

---

### Task 4: Wave A — statistics (10 files)

**Files (modify each):** `skills/statistics/{bias-vs-variance-decomposition,
compositional-data, estimator-certification, population-genetics-likelihood,
power-floor-acknowledgement, prereg-amendment-vs-fresh,
prereg-defensive-instrumentation, replicate-count-justification,
time-series-and-longitudinal-models}.md`, `skills/statistics/SKILL.md`.

**Classification guidance (confirm per file during execution):**

| File | Likely | Candidate source(s) → id (kind) |
|---|---|---|
| bias-vs-variance-decomposition | external | Hastie, Tibshirani, Friedman, *Elements of Statistical Learning* → `hastie-esl` (book) |
| compositional-data | external | Aitchison, *The Statistical Analysis of Compositional Data* → `aitchison-compositional` (book) |
| estimator-certification | internal | Science-native doctrine (a check must be able to fail) |
| population-genetics-likelihood | external | Wakeley, *Coalescent Theory: An Introduction* → `wakeley-coalescent` (book) |
| power-floor-acknowledgement | internal (confirm) | Science-native framing; cite Cohen, *Statistical Power Analysis* (`cohen-power`, book) only if guidance is materially derived |
| prereg-amendment-vs-fresh | internal | Science-native pre-registration workflow |
| prereg-defensive-instrumentation | internal | Science-native |
| replicate-count-justification | internal (confirm) | Science-native; cite a power reference only if materially derived |
| time-series-and-longitudinal-models | external | Hyndman & Athanasopoulos, *Forecasting: Principles and Practice* → `hyndman-fpp` (book) |
| statistics/SKILL.md | internal | navigational router |

- [ ] Step 1: Classify + edit each of the 10 files (frontmatter line(s)); add
  the confirmed `book` records to `skills/sources.yaml`.
- [ ] Step 2: Run the per-wave verification (ERRORS empty; `missing-provenance`
  down by 10).
- [ ] Step 3: `uv run ruff check` (no code changed, but keep the habit) and the
  registry test.
- [ ] Step 4: Commit — `git add skills/statistics skills/sources.yaml && git commit -m "docs(skills): declare provenance for statistics leaves + routers"`.

---

### Task 5: Wave B — data QA leaves (10 files)

**Files (modify each):** `skills/data/{embeddings-manifold-qa,
functional-genomics-qa, protein-sequence-structure-qa, proteomics-qa}.md`,
`skills/data/expression/{bulk-rnaseq-qa, microarray-qa, scrna-qa}.md`,
`skills/data/genomics/{copy-number-sv-qa, somatic-mutation-qa,
mutational-signatures-and-selection}.md`.

**Classification guidance:** these are externally derived from domain tools +
method papers. Confirm the canonical source per file:

| File | Candidate source(s) → id (kind) |
|---|---|
| expression/scrna-qa | scanpy (`scanpy`, software) + a QC method paper (e.g. Luecken & Theis best-practices) → `luecken-scrna-best-practices` (paper) |
| expression/bulk-rnaseq-qa | limma/edgeR/DESeq2 (`deseq2`/`edger`, software) + method paper → `love-deseq2` (paper) |
| expression/microarray-qa | limma (`limma`, software) + `ritchie-limma` (paper) |
| genomics/somatic-mutation-qa | GATK best practices (`gatk`, software) |
| genomics/copy-number-sv-qa | a CN/SV caller/tool (`gatk`/`cnvkit`, software) |
| genomics/mutational-signatures-and-selection | COSMIC / SigProfiler (`cosmic-signatures`, spec/software) + Alexandrov et al. → `alexandrov-signatures` (paper) |
| functional-genomics-qa | domain tool/method (confirm) → software + paper |
| proteomics-qa | proteomics QC tool/method (confirm) → software + paper |
| protein-sequence-structure-qa | UniProt/PDB/AlphaFold (`uniprot`/`alphafold`, software/spec) |
| embeddings-manifold-qa | UMAP/t-SNE method papers → `mcinnes-umap` (paper) + software |

- [ ] Step 1: Classify + edit each of the 10 leaves; register the confirmed
  `software`/`paper`/`spec` records.
- [ ] Step 2: Per-wave verification (`missing-provenance` down by 10; ERRORS
  empty).
- [ ] Step 3: registry test.
- [ ] Step 4: Commit — `git add skills/data skills/sources.yaml && git commit -m "docs(skills): declare provenance for data QA leaves"`.

---

### Task 6: Wave C — data specs, sources & routers (6 files)

**Files:** `skills/data/frictionless.md`, `skills/data/sources/openalex.md`,
`skills/data/sources/pubmed.md`, `skills/data/SKILL.md`,
`skills/data/expression/SKILL.md`, `skills/data/genomics/SKILL.md`.

| File | Likely | Source(s) → id (kind) |
|---|---|---|
| frictionless | external | Frictionless Data Package spec → `frictionless-spec` (spec) + `frictionless` (software) |
| sources/openalex | external | OpenAlex API → `openalex` (software) |
| sources/pubmed | external | NCBI PubMed E-utilities → `ncbi-eutilities` (software) |
| data/SKILL.md | internal (confirm) | router; `provenance: internal` unless it materially summarizes EDAM — if it does, cite EDAM → `edam-ontology` (spec) |
| data/expression/SKILL.md | internal | router |
| data/genomics/SKILL.md | internal | router |

- [ ] Step 1: Classify + edit; register `frictionless-spec` (spec),
  `frictionless` (software), `openalex` (software), `ncbi-eutilities`
  (software), and `edam-ontology` (spec) if the data router cites it.
- [ ] Step 2: Per-wave verification (down by 6).
- [ ] Step 3: registry test.
- [ ] Step 4: Commit — `git add skills/data skills/sources.yaml && git commit -m "docs(skills): declare provenance for data specs, sources, and routers"`.

---

### Task 7: Wave D — pipelines (4 files)

**Files:** `skills/pipelines/{snakemake, marimo, runpod}.md`,
`skills/pipelines/SKILL.md`.

| File | Likely | Source(s) → id (kind) |
|---|---|---|
| snakemake | external | Snakemake tool → `snakemake` (software) + Mölder et al. 2021 → `molder-snakemake` (paper) |
| marimo | external | marimo → `marimo` (software) |
| runpod | external | RunPod service → `runpod` (software) |
| pipelines/SKILL.md | internal | router |

- [ ] Step 1: Classify + edit; register `snakemake` (software),
  `molder-snakemake` (paper), `marimo` (software), `runpod` (software).
- [ ] Step 2: Per-wave verification (down by 4).
- [ ] Step 3: registry test.
- [ ] Step 4: Commit — `git add skills/pipelines skills/sources.yaml && git commit -m "docs(skills): declare provenance for pipelines leaves + router"`.

---

### Task 8: Wave E — research & writing (6 files)

**Files:** `skills/research/{annotation-curation-qa, proposition-schema,
research-package-rendering, research-package-spec, SKILL}.md`,
`skills/writing/SKILL.md`.

| File | Likely | Source(s) → id (kind) |
|---|---|---|
| annotation-curation-qa | external (confirm) | PubTator / annotation method → `pubtator` (software) if materially derived; else internal |
| proposition-schema | internal | Science-native schema |
| research-package-rendering | internal | Science-native |
| research-package-spec | internal | Science-native (built on Frictionless — cite `frictionless-spec` only if it materially adapts the spec) |
| research/SKILL.md | internal | router |
| writing/SKILL.md | internal | Science-native writing conventions |

- [ ] Step 1: Classify + edit; register any confirmed external record
  (`pubtator`, or reuse `frictionless-spec` from Wave C).
- [ ] Step 2: Per-wave verification (down by 6 → **0** remaining).
- [ ] Step 3: registry test.
- [ ] Step 4: Commit — `git add skills/research skills/writing skills/sources.yaml && git commit -m "docs(skills): declare provenance for research + writing"`.

---

## Task 9: Repository coverage test

**Files:**
- Test: `science/tests/skills_lint/test_provenance_coverage_repo.py` (create)

**Interfaces:**
- Consumes: `check_skills` (Task 3); the completed sweep (Tasks 4–8).

- [ ] **Step 1: Write the coverage test**

```python
from pathlib import Path

from science_tool.skills_lint.lint import check_skills

REPO_ROOT = Path(__file__).resolve().parents[3]
SKILLS = REPO_ROOT / "skills"


def test_corpus_has_zero_missing_provenance() -> None:
    issues = check_skills(SKILLS)
    undeclared = sorted(i.path.as_posix() for i in issues if i.kind == "missing-provenance")
    assert undeclared == [], f"undeclared skills: {undeclared}"


def test_corpus_has_no_error_severity_findings() -> None:
    issues = check_skills(SKILLS)
    errors = [(i.path.as_posix(), i.kind, i.detail) for i in issues if i.severity == "error"]
    assert errors == [], f"error-severity findings: {errors}"
```

- [ ] **Step 2: Run it**

Run: `cd science && uv run --frozen pytest tests/skills_lint/test_provenance_coverage_repo.py -v`
Expected: PASS (the sweep brought `missing-provenance` to zero and introduced no
ERROR findings). If it fails, an undeclared or mis-registered file remains — fix
in the owning wave, do not weaken the test.

- [ ] **Step 3: Commit**

```bash
git add science/tests/skills_lint/test_provenance_coverage_repo.py
git commit -m "test(skills): assert corpus provenance coverage is complete"
```

---

## Task 10: Ratchet `missing-provenance` to ERROR

**Files:**
- Modify: `science/src/science_tool/skills_lint/lint.py`
- Modify/Test: `science/tests/skills_lint/test_lint.py`

**Interfaces:**
- Consumes: everything above; requires Task 9 green (corpus clean).

- [ ] **Step 1: Update the undeclared-fixture expectation and add a synthetic-WARN test**

In `test_lint.py`, change `test_undeclared_leaf_yields_warn` to expect ERROR and
nonzero exit through the CLI, and rename it accordingly; add a synthetic-WARN
test that keeps warning exit-code coverage after no shipped rule is WARN:

```python
def test_undeclared_leaf_yields_error_and_nonzero_exit(tmp_path: Path) -> None:
    from click.testing import CliRunner
    from science_tool.cli import main
    from science_tool.skills_lint.lint import check_provenance
    leaf = _leaf(tmp_path, "leaf.md", "---\nname: x\ndescription: d\n---\n# X\n")
    issues = check_provenance(leaf)
    assert issues[0].kind == "missing-provenance"
    assert issues[0].severity == "error"

    skills_root = tmp_path / "skills"
    skills_root.mkdir()
    # INDEX.md is error-free so the ONLY error is the ratcheted missing-provenance
    # on leaf.md — otherwise exit==1 could pass for the wrong reason.
    (skills_root / "INDEX.md").write_text(
        "---\nname: idx\ndescription: d\n---\n# Index\n`skills/leaf.md`\n## Companion Skills\n- none\n",
        encoding="utf-8",
    )
    (skills_root / "leaf.md").write_text(
        "---\nname: leaf\ndescription: d\n---\n# Leaf\n## Companion Skills\n- none\n",
        encoding="utf-8",
    )
    result = CliRunner().invoke(main, ["skills", "lint", "--root", str(skills_root)])
    assert result.exit_code == 1  # ratcheted: undeclared now blocks
    assert "missing-provenance" in result.output


def test_warn_only_run_still_exits_zero_synthetic() -> None:
    # Infrastructure guard: severity-aware exit must still let WARN-only pass,
    # independent of which real rules are WARN.
    from science_tool.skills_lint.cli import _has_error
    from science_tool.skills_lint.lint import SkillIssue
    synthetic = SkillIssue(Path("x.md"), "missing-provenance", severity="warn")
    assert _has_error([synthetic]) is False
```

(Delete the now-superseded `test_warn_only_run_exits_zero` from Task 3, which
asserted `missing-provenance` was WARN — that expectation is what this ratchet
changes. The synthetic test preserves the WARN-only-exits-zero contract.)

- [ ] **Step 2: Run to verify the new expectations fail pre-ratchet**

Run: `cd science && uv run --frozen pytest tests/skills_lint/test_lint.py -k "undeclared_leaf_yields_error or synthetic" -v`
Expected: `undeclared_leaf_yields_error…` FAILS (still WARN);
`…synthetic` PASSES.

- [ ] **Step 3: Flip the constant**

In `lint.py`:

```python
MISSING_PROVENANCE_SEVERITY: Severity = "error"
```

- [ ] **Step 4: Run the full skills suite + repo coverage**

Run: `cd science && uv run --frozen pytest tests/skills_lint/ -q`
Expected: PASS — including `test_provenance_coverage_repo.py`
(`test_corpus_has_no_error_severity_findings` still holds because the corpus is
fully declared, so the now-ERROR rule finds nothing).

- [ ] **Step 5: Confirm real `science skills lint` exits 0**

Run: `cd science && uv run --frozen python -c "import subprocess,sys; sys.exit(subprocess.run(['uv','run','--frozen','python','-c','from pathlib import Path;from science_tool.skills_lint.lint import check_skills;from science_tool.skills_lint.cli import _has_error;print(1 if _has_error(check_skills(Path(\"../skills\"))) else 0)']).returncode)"`
Simpler: `cd science && uv run --frozen science skills lint --root ../skills; echo "exit=$?"`
Expected: `exit=0` (corpus fully declared; no ERROR findings).

- [ ] **Step 6: Lint + types + commit**

Run: `cd science && uv run ruff check && uv run pyright`

```bash
git add science/src/science_tool/skills_lint/lint.py science/tests/skills_lint/test_lint.py
git commit -m "feat(skills): ratchet missing-provenance to ERROR"
```

---

## Self-Review

**Spec coverage:**
- Three states + invalid → Task 3 (`classify_provenance`, four outcomes +
  attributed). ✓
- No cascade on broken frontmatter / no double-report → Task 3
  (`test_no_cascade…`, `test_missing_provenance_not_double_reported…`). ✓
- Severity model (default error, `_relative_issues` copies, text+JSON, exit) →
  Task 2. ✓
- `_relative_issues` severity copy + real-tree CLI test → Task 2 Step 4 + Task 3
  `test_warn_only_run_exits_zero`. ✓
- `spec`/`software` kinds + `upstream_ref` regression + `leaf_source_refs`
  strengthening → Task 1. ✓
- `INDEX.md` exclusion (valid frontmatter, still excluded) → Task 3 Step 4 +
  `test_index_md_excluded_from_coverage`. ✓
- Sweep all 41 (36 edited) in waves → Tasks 4–8. ✓
- Repository coverage test (coverage, not severity) → Task 9. ✓
- Ratchet phase-specific + synthetic-WARN test → Task 10. ✓

**Placeholder scan:** No `TBD`/`TODO`. Sweep-wave citation identifiers are
explicitly a verified-research step with a fixed record schema, not invented
values — the one legitimate deferral, called out in the shared method.

**Type consistency:** `Severity`, `SkillIssue.severity`,
`MISSING_PROVENANCE_SEVERITY`, `classify_provenance`/`ProvenanceState`,
`check_provenance`, `leaf_frontmatter`, `_has_error`, and the two new
`IssueKind` members are named identically wherever referenced across Tasks 1–3,
9, 10.

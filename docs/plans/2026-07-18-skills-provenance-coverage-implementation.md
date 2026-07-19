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

- **Working directory:** all `uv run` commands (pytest, ruff, pyright, the
  `science` CLI) run from `science/`. All `git` commands (the `git add …` /
  `git commit` steps, whose paths like `science/…` and `skills/…` are
  **repository-root-relative**) run from the **repository root**. The `--root
  ../skills` argument in verification commands is relative to `science/`.
  Default pytest excludes `snapshot` / `real_projects` markers.
- **Registry `last_checked` uses the actual verification date** — the day the
  research for that record is performed — not a hardcoded value. Plan snippets
  that show `2026-07-18` in *registry records* are placeholders for that date;
  test fixtures may keep a literal date.
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


def test_leaf_frontmatter_rejects_non_mappings(tmp_path) -> None:
    from science_tool.skills_lint.sources import leaf_frontmatter
    cases = {
        "list.md": "---\n[]\n---\n# X\n",          # falsy non-mapping
        "false.md": "---\nfalse\n---\n# X\n",       # falsy scalar
        "scalar.md": "---\n42\n---\n# X\n",         # truthy scalar
        "unterminated.md": "---\nname: x\n# no close\n",
        "unparsable.md": "---\nfoo: [unclosed\n---\n# X\n",
        "none.md": "not frontmatter at all\n",
    }
    for name, body in cases.items():
        p = tmp_path / name
        p.write_text(body, encoding="utf-8")
        assert leaf_frontmatter(p) is None, name
    empty = tmp_path / "empty.md"
    empty.write_text("---\n---\n# X\n", encoding="utf-8")
    assert leaf_frontmatter(empty) == {}   # empty block is a valid empty mapping


def test_sources_wellformed_predicate() -> None:
    from science_tool.skills_lint.sources import sources_wellformed
    assert sources_wellformed(["a", "b"]) is True
    assert sources_wellformed([]) is False
    assert sources_wellformed(["  "]) is False
    assert sources_wellformed("oops") is False
    assert sources_wellformed([1]) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science && uv run --frozen pytest tests/skills_lint/test_sources.py -k "spec_and_software or upstream_ref or empty_and_blank or leaf_frontmatter or sources_wellformed" -v`
Expected: FAIL (`spec`/`software` not valid kinds; empty/blank accepted;
`leaf_frontmatter`/`sources_wellformed` not yet public).

- [ ] **Step 3: Add the kinds**

In `sources.py`, extend `REFERENCE_KINDS`:

```python
REFERENCE_KINDS = frozenset({"book", "paper", "course", "spec", "software"})
```

(`VALID_KINDS = GIT_BACKED_KINDS | REFERENCE_KINDS` picks them up automatically;
the existing `elif kind in REFERENCE_KINDS and "upstream_ref" in raw` guard at
`sources.py:134` now rejects `upstream_ref` on `spec`/`software` for free.)

- [ ] **Step 4: Fix the frontmatter parser, extract `sources_wellformed`, strengthen `leaf_source_refs`, expose `leaf_frontmatter`**

Rename `_leaf_frontmatter` → public `leaf_frontmatter` and **fix its non-mapping
bug**: `yaml.safe_load(...) or {}` turns falsy non-mappings (`[]`, `false`, `0`,
`""`) into `{}`, masking a malformed block as valid-empty. Handle the empty
document (`None`) separately and reject every actual non-mapping:

```python
def leaf_frontmatter(path: Path) -> dict[str, Any] | None:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---\n", 4)
    if end == -1:
        return None
    try:
        parsed = yaml.safe_load(text[4:end])
    except yaml.YAMLError:
        return None
    if parsed is None:
        return {}  # an empty frontmatter block is a valid, empty mapping
    return parsed if isinstance(parsed, dict) else None  # reject [] / false / scalars


def sources_wellformed(raw: object) -> bool:
    return isinstance(raw, list) and bool(raw) and all(
        isinstance(x, str) and x.strip() for x in raw
    )


def leaf_source_refs(path: Path) -> tuple[list[str] | None, str | None]:
    frontmatter = leaf_frontmatter(path)
    if frontmatter is None or "sources" not in frontmatter:
        return None, None
    if not sources_wellformed(frontmatter["sources"]):
        return None, "sources must be a non-empty list of non-blank strings"
    return list(frontmatter["sources"]), None
```

`sources_wellformed` is the **single source of truth** for source-field
well-formedness, reused by the provenance classifier in Task 3 (so `sources: []`
is classified consistently, not re-derived).

- [ ] **Step 5: Add the `spec`/`software` freshness `not_applicable` test**

In `science/tests/skills_lint/test_sources_cli.py`, add (the design requires
proving the new reference kinds report `not_applicable`, as `book` already does
at `test_check_offline_is_clean`):

```python
def test_spec_and_software_report_not_applicable_freshness(tmp_path: Path) -> None:
    root = tmp_path / "skills"
    root.mkdir()
    (root / "sources.yaml").write_text(
        "spec1:\n  title: S\n  authors: [Org]\n  url: https://specs.example.org/x\n"
        "  kind: spec\n  last_checked: 2026-07-18\n"
        "soft1:\n  title: T\n  authors: [Org]\n  url: https://tool.example.org/\n"
        "  kind: software\n  last_checked: 2026-07-18\n",
        encoding="utf-8",
    )
    (root / "INDEX.md").write_text("`skills/leaf.md`\n", encoding="utf-8")
    (root / "leaf.md").write_text(
        "---\nname: leaf\ndescription: d\nsources: [spec1, soft1]\n---\n"
        "# Leaf\n## Companion Skills\n- none\n",
        encoding="utf-8",
    )
    # fetch_upstream=True proves reference kinds are never fetched (fetch raises if called).
    def _boom(url):  # pragma: no cover - must not be invoked
        raise AssertionError("reference kinds must not be fetched")
    report = check_sources(root, fetch_upstream=True, fetch=_boom)
    freshness = {s.id: s.freshness for s in report.sources}
    assert freshness["spec1"] == "not_applicable"
    assert freshness["soft1"] == "not_applicable"
    assert report.failed() is False
```

- [ ] **Step 6: Run the full sources suite**

Run: `cd science && uv run --frozen pytest tests/skills_lint/test_sources.py tests/skills_lint/test_sources_cli.py tests/skills_lint/test_sources_registry_repo.py -q`
Expected: PASS.

- [ ] **Step 7: Lint + types**

Run: `cd science && uv run ruff check && uv run pyright`
Expected: clean.

- [ ] **Step 8: Commit** (from the repository root)

```bash
git add science/src/science_tool/skills_lint/sources.py science/tests/skills_lint/test_sources.py science/tests/skills_lint/test_sources_cli.py
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


def test_classify_provenance_outcomes() -> None:
    from science_tool.skills_lint.lint import classify_provenance
    assert classify_provenance({"sources": ["a"]}) == "attributed"
    assert classify_provenance({"provenance": "internal"}) == "internal"
    assert classify_provenance({"name": "x"}) == "undeclared"
    assert classify_provenance({"sources": ["a"], "provenance": "internal"}) == "contradiction"
    assert classify_provenance({"provenance": "external"}) == "bad-marker"
    # malformed sources is NOT "attributed" (design: sources: [] is invalid)
    assert classify_provenance({"sources": []}) == "malformed-sources"
    assert classify_provenance({"sources": ["  "]}) == "malformed-sources"
    assert classify_provenance({"sources": "oops"}) == "malformed-sources"


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
    # Every "classification impossible" shape must yield NO missing-provenance.
    broken = {
        "n.md": "# no frontmatter\n",
        "unterminated.md": "---\nname: x\n# never closes\n",
        "unparsable.md": "---\nfoo: [unclosed\n---\n# X\n",
        "nonmap-list.md": "---\n[]\n---\n# X\n",
        "nonmap-false.md": "---\nfalse\n---\n# X\n",
    }
    for name, body in broken.items():
        leaf = _leaf(tmp_path, name, body)
        assert check_provenance(leaf) == [], name


def test_empty_or_blank_sources_are_invalid_field_not_missing_provenance(tmp_path: Path) -> None:
    skills_root = tmp_path / "skills"
    skills_root.mkdir()
    (skills_root / "sources.yaml").write_text("", encoding="utf-8")
    (skills_root / "INDEX.md").write_text(
        "---\nname: idx\ndescription: d\n---\n# Index\n`skills/e.md`\n`skills/b.md`\n## Companion Skills\n- none\n",
        encoding="utf-8",
    )
    (skills_root / "e.md").write_text(
        "---\nname: e\ndescription: d\nsources: []\n---\n# E\n## Companion Skills\n- none\n", encoding="utf-8")
    (skills_root / "b.md").write_text(
        '---\nname: b\ndescription: d\nsources: ["  "]\n---\n# B\n## Companion Skills\n- none\n', encoding="utf-8")
    from science_tool.skills_lint.lint import check_skills
    per = {(i.path.as_posix(), i.kind) for i in check_skills(skills_root)}
    assert ("e.md", "invalid-field") in per      # empty list rejected by source-ref check
    assert ("b.md", "invalid-field") in per      # blank string rejected
    assert not any(kind == "missing-provenance" for _, kind in per)  # never cascaded


def test_nonmapping_frontmatter_is_invalid_yaml_not_missing_field(tmp_path: Path) -> None:
    # check_frontmatter's `or {}` used to turn falsy non-mappings ([], false) into
    # {}, which then emitted missing-field for name/description. A non-mapping is an
    # invalid frontmatter document (invalid-yaml), and it must NOT cascade into
    # missing-field or missing-provenance.
    skills_root = tmp_path / "skills"
    skills_root.mkdir()
    (skills_root / "sources.yaml").write_text("", encoding="utf-8")
    (skills_root / "INDEX.md").write_text(
        "---\nname: idx\ndescription: d\n---\n# Index\n`skills/lst.md`\n`skills/fls.md`\n## Companion Skills\n- none\n",
        encoding="utf-8",
    )
    (skills_root / "lst.md").write_text("---\n[]\n---\n# L\n## Companion Skills\n- none\n", encoding="utf-8")
    (skills_root / "fls.md").write_text("---\nfalse\n---\n# F\n## Companion Skills\n- none\n", encoding="utf-8")
    from science_tool.skills_lint.lint import check_skills
    per = {(i.path.as_posix(), i.kind) for i in check_skills(skills_root)}
    for name in ("lst.md", "fls.md"):
        assert (name, "invalid-yaml") in per                        # non-mapping => invalid-yaml
        assert (name, "missing-field") not in per                   # not treated as an empty mapping
        assert (name, "missing-provenance") not in per              # no provenance cascade


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

Run: `cd science && uv run --frozen pytest tests/skills_lint/test_lint.py -k "classify or undeclared or internal_and_attributed or contradiction or no_cascade or not_double or index_md_excluded or warn_only or empty_or_blank or nonmapping_frontmatter" -v`
Expected: FAIL (`classify_provenance` / `check_provenance` absent; the
`or {}` parser bug still emits `missing-field` for non-mappings).

- [ ] **Step 3: Fix the `check_frontmatter` parser (same `or {}` bug)**

Task 1 fixed `leaf_frontmatter` in `sources.py`, but `check_frontmatter` in
`lint.py` has **two** parity defects vs. the now-fixed `leaf_frontmatter`:
1. `yaml.safe_load(block) or {}` turns falsy non-mappings (`[]`, `false`, `0`,
   `""`) into `{}`, defeating the `isinstance` guard below so they emit
   `missing-field` instead of `invalid-yaml`.
2. `text.find("\n---\n", 4)` misses a truly-empty block (`---\n---\n`), because
   the closing delimiter's leading newline is at index 3 (the same newline that
   closes the opening `---`). Task 1 fixed the identical bug in
   `leaf_frontmatter` by searching from `3`; `check_frontmatter` must match so
   an empty frontmatter block parses to `{}` (→ `missing-field`) instead of
   being misreported as `missing-frontmatter`/unterminated.

Handle `None` (empty block → empty mapping) separately and let every actual
non-mapping fall through to the existing `invalid-yaml` return. In `lint.py`,
replace:

```python
    end = text.find("\n---\n", 4)
    if end == -1:
        return [SkillIssue(path, "missing-frontmatter", detail="unterminated YAML block")]
    block = text[4:end]
    try:
        parsed = yaml.safe_load(block) or {}
    except yaml.YAMLError as exc:
        return [SkillIssue(path, "invalid-yaml", detail=str(exc))]
    if not isinstance(parsed, dict):
        return [SkillIssue(path, "invalid-yaml", detail="frontmatter is not a mapping")]
```

with:

```python
    end = text.find("\n---\n", 3)
    if end == -1:
        return [SkillIssue(path, "missing-frontmatter", detail="unterminated YAML block")]
    block = text[4:end]
    try:
        parsed = yaml.safe_load(block)
    except yaml.YAMLError as exc:
        return [SkillIssue(path, "invalid-yaml", detail=str(exc))]
    if parsed is None:
        parsed = {}  # empty frontmatter block is a valid, empty mapping
    if not isinstance(parsed, dict):
        return [SkillIssue(path, "invalid-yaml", detail="frontmatter is not a mapping")]
```

(For a truly-empty block `end` becomes `3` and `text[4:3]` is `""`, which
`safe_load` returns as `None` → `{}`; for every non-empty block the searched
index is unchanged from before.)

- [ ] **Step 4: Implement the classifier and coverage check**

In `lint.py`, add the import and functions:

```python
from science_tool.skills_lint.sources import (
    SourcesRegistry,
    leaf_frontmatter,
    leaf_source_refs,
    load_sources,
    sources_wellformed,
)

MISSING_PROVENANCE_SEVERITY: Severity = "warn"

ProvenanceState = Literal[
    "attributed", "internal", "undeclared", "contradiction", "bad-marker", "malformed-sources"
]


def classify_provenance(frontmatter: dict) -> ProvenanceState:
    has_sources = "sources" in frontmatter
    has_provenance = "provenance" in frontmatter
    if has_sources and has_provenance:
        return "contradiction"
    if has_sources:
        # A present `sources` key is a declaration attempt; well-formedness is the
        # source-ref check's job to REPORT, but the classifier must not call a
        # malformed list "attributed" (design: sources: [] is invalid, not attributed).
        return "attributed" if sources_wellformed(frontmatter["sources"]) else "malformed-sources"
    if has_provenance:
        return "internal" if frontmatter.get("provenance") == "internal" else "bad-marker"
    return "undeclared"


def check_provenance(path: Path) -> list[SkillIssue]:
    frontmatter = leaf_frontmatter(path)
    if frontmatter is None:
        return []  # missing/unterminated/unparsable/non-mapping frontmatter already reported; no cascade
    state = classify_provenance(frontmatter)
    if state == "undeclared":
        return [SkillIssue(path, "missing-provenance", severity=MISSING_PROVENANCE_SEVERITY)]
    if state == "contradiction":
        return [SkillIssue(path, "invalid-provenance", detail="sources: and provenance: are mutually exclusive")]
    if state == "bad-marker":
        value = frontmatter.get("provenance")
        return [SkillIssue(path, "invalid-provenance", field="provenance", detail=f"unknown value {value!r}; only 'internal' is allowed")]
    # attributed / internal → clean. malformed-sources → silent HERE; check_source_refs
    # reports it as invalid-field (single report, no missing-provenance cascade).
    return []
```

- [ ] **Step 5: Integrate into `check_skills`, excluding `INDEX.md`**

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

- [ ] **Step 6: Declare the four "good" fixtures**

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

- [ ] **Step 7: Run to verify pass, including the untouched fixture CLI test**

Run: `cd science && uv run --frozen pytest tests/skills_lint/ -q`
Expected: PASS. `test_lint_cli_against_fixtures` still passes: `good.md`,
`good-with-companion.md`, `good-deep-reference.md`,
`data/embeddings-manifold-qa.md` now declare `provenance: internal` (no
`missing-provenance`); the bad fixtures still appear for their ERROR findings.

- [ ] **Step 8: Confirm real-corpus behavior (WARN, exit 0)**

Run: `cd science && uv run --frozen python -c "from pathlib import Path; from collections import Counter; from science_tool.skills_lint.lint import check_skills; c=Counter(i.kind for i in check_skills(Path('../skills'))); print(c)"`
Expected: `Counter({'missing-provenance': 36})` (INDEX.md excluded; no ERROR
kinds). Confirms the sweep target is exactly 36.

- [ ] **Step 9: Lint + types + commit**

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
     authors: ["<author or maintaining org>"]   # required, non-empty
     url: "https://<canonical https homepage/docs/spec url>"
     kind: <software|spec|paper|book>
     last_checked: "<actual verification date>"
     doi: "<10....>"        # papers only, when available
     isbn: "<digits>"       # books only, when available
   ```

   **Register the PRIMARY 1–2 sources the leaf's guidance is materially built
   on — not every tool it name-drops.** Acceptance criterion for "primary": the
   tool/DB/method whose *specific behavior the QA guidance targets* (the caller
   whose version must be pinned, the engine whose settings the leaf configures,
   the DB whose label semantics the leaf keys on). Tools named only as
   vocabulary or failure-mode labels are **not** registered. The classification
   from a read-through is already captured in each wave table below; execution
   confirms it and **verifies the canonical `url`** (and, for the one real
   in-file citation, the DOI). Do not invent identifiers. Most external sources
   here are `software` (a tool/service homepage) or `spec` (a standard/ontology);
   only `data/expression/scrna-qa.md` carries a literal method-paper citation
   (Tirosh et al. 2016). Research is subagent-friendly; the controller curates
   the registry.
4. Do **not** modify the 5 already-attributed statistics leaves unless research
   adds a citation.

**Reuse ids across waves.** A source id is registered once and reused. If a
later wave cites an id an earlier wave already registered, reference it — do not
duplicate the record.

**Per-wave verification (identical shape).** After editing a wave's files, run
this from `science/`. It fails on **any** ERROR-severity finding (not a
hand-picked subset — broken YAML, missing fields, links, sections all count) and
asserts the **exact** remaining `missing-provenance` count for this wave:

```bash
cd science && EXPECT=<remaining-after-this-wave> uv run --frozen python -c "
import os
from pathlib import Path
from science_tool.skills_lint.lint import check_skills
issues = check_skills(Path('../skills'))
errors = [(i.path.as_posix(), i.kind, i.detail) for i in issues if i.severity == 'error']
assert errors == [], f'ERROR findings introduced: {errors}'
mp = sorted(i.path.as_posix() for i in issues if i.kind == 'missing-provenance')
expect = int(os.environ['EXPECT'])
assert len(mp) == expect, f'expected {expect} undeclared, got {len(mp)}: {mp}'
print('OK — 0 errors,', len(mp), 'undeclared remain')
"
```

Then confirm the real CLI exits 0 (WARN-only) and the registry is still valid:

```bash
cd science && uv run --frozen science skills lint --root ../skills && echo "lint exit=0 (WARN-only)"
cd science && uv run --frozen pytest tests/skills_lint/test_sources_registry_repo.py -q
```

The `&&` (not `;`) is load-bearing: a non-zero lint exit short-circuits, the
`echo` never runs, and the line's status is lint's failure — a `; echo` would
mask it behind `echo`'s exit 0. Expected: the `lint exit=0` line prints and the
registry test passes. Per-wave `EXPECT` values: Wave A
→ 26, Wave B → 16, Wave C → 10, Wave D → 6, Wave E → 0. Then commit (from the
repository root).

---

### Task 4: Wave A — statistics (10 files, all INTERNAL)

A read-through classified **all 10** as `provenance: internal`: each teaches
Science-native epistemic/design doctrine and names external methods only as
standard vocabulary (e.g. `estimator-certification` names Cox–Reid/Neyman–Scott;
`time-series` names GEE/state-space). No registry changes in this wave.

| File | Verdict | Frontmatter outcome |
|---|---|---|
| bias-vs-variance-decomposition.md | INTERNAL | `provenance: internal` |
| estimator-certification.md | INTERNAL | `provenance: internal` |
| power-floor-acknowledgement.md | INTERNAL | `provenance: internal` |
| prereg-amendment-vs-fresh.md | INTERNAL | `provenance: internal` |
| prereg-defensive-instrumentation.md | INTERNAL | `provenance: internal` |
| replicate-count-justification.md | INTERNAL | `provenance: internal` |
| time-series-and-longitudinal-models.md | INTERNAL | `provenance: internal` |
| SKILL.md | INTERNAL | `provenance: internal` |
| compositional-data.md | INTERNAL — **bounded** | default `provenance: internal` |
| population-genetics-likelihood.md | INTERNAL — **bounded** | default `provenance: internal` |

**Bounded decision (2 files).** `compositional-data` rests on Aitchison
log-ratio transforms; `population-genetics-likelihood` on Wright–Fisher/Moran
likelihoods. Both teach native QA discipline *over* those methods. **Decision
rule:** keep `provenance: internal` unless, on reading, the leaf's *load-bearing
claims are the external method's mechanics* (the transform/model derivation)
rather than QA discipline over it. **Acceptance:** if justifying the leaf's core
claims would require citing the textbook, register `aitchison-compositional`
(book) / `wakeley-coalescent` (book) and use `sources:` instead; otherwise
`internal`. The read-through recommends `internal` for both.

- [ ] Step 1: Add `provenance: internal` to all 10 files (resolve the 2 bounded
  cases per the rule above; if either flips to external, register the book
  record with a verified ISBN/URL and use `sources:`).
- [ ] Step 2: Per-wave verification with `EXPECT=26`.
- [ ] Step 3: `uv run ruff check`; registry test.
- [ ] Step 4: Commit (repo root) — `git add skills/statistics && git commit -m "docs(skills): declare provenance for statistics leaves + router"` (add `skills/sources.yaml` only if a bounded case flipped).

---

### Task 5: Wave B — data QA leaves (10 files: 8 external, 2 internal)

Eight leaves are QA guidance keyed to a **specific** external tool/DB/reference
whose behavior the guidance targets — those get `sources:`. Two
(`proteomics-qa`, `genomics/somatic-mutation-qa`) are generic
measurement-QA discipline spanning many interchangeable engines/resources with
no single owner — those are `provenance: internal`, exactly like the Wave A
statistics leaves that name external methods only as vocabulary. **Acceptance
test for `sources:` vs `internal`:** does the leaf's load-bearing guidance
target one named tool's behavior/output (→ `sources:`), or is it native
grain/denominator/missingness discipline that merely *lists* tools as examples
(→ `internal`)? Register each external `url` as the tool/DB canonical
homepage/docs (verify). Only `scrna-qa` has an in-file paper citation.

| File | Verdict | Source(s) → id (kind) | Acceptance criterion (why this outcome) | Frontmatter |
|---|---|---|---|---|
| embeddings-manifold-qa.md | EXTERNAL | `umap` (software), `hdbscan` (software) | the projection + clustering tools whose parameters the QA tunes (neighbors/min_dist; min_cluster_size) | `sources: [umap, hdbscan]` |
| functional-genomics-qa.md | EXTERNAL | `depmap` (software/service), `mageck` (software) | the screen resource + screen-analysis tool the QA normalizes/targets | `sources: [depmap, mageck]` |
| protein-sequence-structure-qa.md | EXTERNAL | `uniprot` (software/service), `foldseek` (software) | the annotation DB + structure-search tool whose label/cluster semantics the QA keys on | `sources: [uniprot, foldseek]` |
| proteomics-qa.md | **INTERNAL** | — | generic MS-proteomics QA (grain/rollup, MNAR, batch/run structure, PTM localization) that names MaxQuant/FragPipe/Spectronaut/CPTAC only as interchangeable examples; **no single engine owns the guidance** | `provenance: internal` |
| expression/bulk-rnaseq-qa.md | EXTERNAL | `deseq2` (software), `edger` (software) | the DE tools the QA is explicitly "required for" | `sources: [deseq2, edger]` |
| expression/microarray-qa.md | EXTERNAL | `limma` (software) | the linear-model package + normalization the QA configures | `sources: [limma]` |
| expression/scrna-qa.md | EXTERNAL | `scanpy` (software), `tirosh-2016` (**paper**, DOI) | the QC toolkit + the literally-cited cell-cycle method ("Tirosh et al. 2016") | `sources: [scanpy, tirosh-2016]` |
| genomics/copy-number-sv-qa.md | EXTERNAL | `ampliconarchitect` (software) | the CN/SV caller whose version + output non-independence the QA targets | `sources: [ampliconarchitect]` |
| genomics/somatic-mutation-qa.md | **INTERNAL** | — | generic callable-territory/denominator/NaN-vs-0 discipline spanning cBioPortal, GENIE, MC3, ICGC, MAF and panels; **cBioPortal alone does not own** the panel/callability guidance — the sources are named as examples | `provenance: internal` |
| genomics/mutational-signatures-and-selection.md | EXTERNAL | `cosmic-signatures` (software), `dndscv` (software) | the leaf keys on a **specific versioned reference** ("Record COSMIC version", SBS40a/b/c) + the named selection method `dNdScv`. **Note:** the design anticipated "SigProfiler / Alexandrov et al.", but neither appears in-file — attribute what the leaf actually cites (COSMIC + dNdScv); do not invent the Alexandrov paper | `sources: [cosmic-signatures, dndscv]` |

- [ ] Step 1: For the 8 external leaves, add the `sources:` line and register
  each new id in `skills/sources.yaml` (`software` for tools/services;
  `paper` for `tirosh-2016` with its verified DOI). `cosmic-signatures` is
  `software` (the Sanger COSMIC Mutational Signatures database/service,
  `url https://cancer.sanger.ac.uk/signatures/`) — a reference-kind record,
  freshness `not_applicable`; the version-pinning discipline lives in the leaf,
  not the registry. Verify each `url` and `authors` (maintaining org, e.g.
  `scanpy` → `["scverse"]`, `depmap` → `["Broad Institute"]`,
  `dndscv` → `["Inigo Martincorena"]`). Do **not** register `maxquant` or
  `cbioportal` — the two internal leaves cite no owning source.
- [ ] Step 2: For the 2 internal leaves (`proteomics-qa`,
  `genomics/somatic-mutation-qa`), add `provenance: internal` (no registry
  change). Before doing so, re-read each and confirm the acceptance test above
  still holds (native discipline, tools as examples); if a leaf turns out to be
  built on one owning tool's behavior, register that source instead and use
  `sources:`.
- [ ] Step 3: Per-wave verification with `EXPECT=16` (both declaration styles
  clear `missing-provenance`, so the count is unchanged by the split).
- [ ] Step 4: registry test.
- [ ] Step 5: Commit (repo root) — `git add skills/data skills/sources.yaml && git commit -m "docs(skills): declare provenance for data QA leaves"`.

---

### Task 6: Wave C — data specs, sources & routers (6 files)

3 EXTERNAL leaves + 3 INTERNAL routers.

| File | Verdict | Source(s) → id (kind) / outcome | Acceptance |
|---|---|---|---|
| frictionless.md | EXTERNAL | `frictionless-spec` (spec), `frictionless` (software), `edam` (spec) → `sources: [frictionless-spec, frictionless, edam]` | file teaches the Data Package spec + the `frictionless` CLI, and embeds `edamontology.org` term URIs |
| sources/openalex.md | EXTERNAL | `openalex` (software) → `sources: [openalex]` | documents the OpenAlex `works` API (url present: developers.openalex.org) |
| sources/pubmed.md | EXTERNAL | `ncbi-eutilities` (software) → `sources: [ncbi-eutilities]` | documents the PubMed E-utilities (esearch/esummary/efetch) |
| SKILL.md (data) | INTERNAL | `provenance: internal` | data-management conventions hub; EDAM/Frictionless delegated to leaves |
| expression/SKILL.md | INTERNAL | `provenance: internal` | navigation hub over the modality leaves |
| genomics/SKILL.md | INTERNAL | `provenance: internal` | navigation hub + native ordering convention |

- [ ] Step 1: Edit the 6 files; register `frictionless-spec` (spec; url
  `https://specs.frictionlessdata.io/data-package/`, authors
  `["Open Knowledge Foundation"]`), `frictionless` (software;
  `https://framework.frictionlessdata.io/`), `edam` (spec;
  `https://edamontology.org/`), `openalex` (software;
  `https://docs.openalex.org/`), `ncbi-eutilities` (software;
  `https://www.ncbi.nlm.nih.gov/books/NBK25501/`). Verify each url.
- [ ] Step 2: Per-wave verification with `EXPECT=10`.
- [ ] Step 3: registry test.
- [ ] Step 4: Commit (repo root) — `git add skills/data skills/sources.yaml && git commit -m "docs(skills): declare provenance for data specs, sources, and routers"`.

---

### Task 7: Wave D — pipelines (4 files)

3 EXTERNAL leaves + 1 INTERNAL router.

| File | Verdict | Source(s) → id (kind) / outcome |
|---|---|---|
| snakemake.md | EXTERNAL | `snakemake` (software) **and** `molder-snakemake` (paper, DOI) → `sources: [snakemake, molder-snakemake]` — the whole leaf teaches Snakemake's workflow model; per the approved design this is tool + Mölder et al. method paper (**required, not optional**), the canonical reference for the tool the guidance derives from |
| marimo.md | EXTERNAL | `marimo` (software) → `sources: [marimo]` |
| runpod.md | EXTERNAL | `runpod` (software) → `sources: [runpod]` |
| SKILL.md (pipelines) | INTERNAL | `provenance: internal` |

- [ ] Step 1: Edit the 4 files; register `snakemake` (software;
  `https://snakemake.readthedocs.io/`, authors `["Snakemake developers"]`),
  `molder-snakemake` (paper; Mölder F, Jablonski KP, Letcher B, et al.,
  "Sustainable data analysis with Snakemake", F1000Research 2021;
  `url https://doi.org/10.12688/f1000research.29032.2` — verify the DOI resolves
  and confirm the final author list/version from the resolved page),
  `marimo` (software; `https://marimo.io/`), `runpod` (software;
  `https://www.runpod.io/`). Verify urls.
- [ ] Step 2: Per-wave verification with `EXPECT=6`.
- [ ] Step 3: registry test.
- [ ] Step 4: Commit (repo root) — `git add skills/pipelines skills/sources.yaml && git commit -m "docs(skills): declare provenance for pipelines leaves + router"`.

---

### Task 8: Wave E — research & writing (6 files, all INTERNAL)

A read-through classified **all 6** as Science-native: the `research/` leaves
define Science's own proposition/evidence model, research-package profile, and
rendering conventions (Frictionless/Vega are substrate they *extend*, not derive
from); `writing/SKILL.md` is Science's writing conventions;
`annotation-curation-qa` is native curation-as-measurement discipline (kappa/
alpha named as standard metrics only). No registry changes.

| File | Verdict | Frontmatter outcome |
|---|---|---|
| annotation-curation-qa.md | INTERNAL | `provenance: internal` |
| proposition-schema.md | INTERNAL | `provenance: internal` |
| research-package-rendering.md | INTERNAL | `provenance: internal` |
| research-package-spec.md | INTERNAL | `provenance: internal` |
| research/SKILL.md | INTERNAL | `provenance: internal` |
| writing/SKILL.md | INTERNAL | `provenance: internal` |

- [ ] Step 1: Add `provenance: internal` to all 6 files.
- [ ] Step 2: Per-wave verification with `EXPECT=0` (corpus now fully declared).
- [ ] Step 3: registry test.
- [ ] Step 4: Commit (repo root) — `git add skills/research skills/writing && git commit -m "docs(skills): declare provenance for research + writing"`.

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


def test_warn_only_run_still_exits_zero_synthetic(tmp_path: Path, monkeypatch) -> None:
    # Infrastructure guard: after the ratchet, NO shipped rule is WARN, so exercise
    # the WARN-only exit path through the REAL CLI with a synthetic WARN issue —
    # proving exit code and severity rendering, not just the _has_error predicate.
    import json
    from click.testing import CliRunner
    from science_tool.cli import main
    from science_tool.skills_lint.lint import SkillIssue
    synthetic = [SkillIssue(Path("synthetic.md"), "missing-provenance", severity="warn")]
    monkeypatch.setattr("science_tool.skills_lint.cli.check_skills", lambda root: list(synthetic))
    root = tmp_path / "skills"
    root.mkdir()

    js = CliRunner().invoke(main, ["skills", "lint", "--root", str(root), "--format", "json"])
    assert js.exit_code == 0  # WARN-only still exits 0
    assert ("missing-provenance", "warn") in {(i["kind"], i["severity"]) for i in json.loads(js.output)["issues"]}

    txt = CliRunner().invoke(main, ["skills", "lint", "--root", str(root)])
    assert txt.exit_code == 0
    assert "warn: synthetic.md: missing-provenance" in txt.output  # severity-leading render
```

(Delete the now-superseded `test_warn_only_run_exits_zero` from Task 3, which
asserted `missing-provenance` was WARN — that expectation is what this ratchet
changes. This synthetic CLI test preserves the WARN-only-exits-zero contract
independent of which real rules are WARN.)

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

Run: `cd science && uv run --frozen science skills lint --root ../skills && echo "lint exit=0"`
Expected: the `lint exit=0` line prints (corpus fully declared; the now-ERROR
rule finds nothing). The `&&` ensures a non-zero exit short-circuits instead of
being masked by a trailing `echo`.

- [ ] **Step 6: Full-suite verification (whole package, not just skills-lint)**

Run:
```bash
cd science && uv run --frozen pytest
cd science && uv run ruff check
cd science && uv run pyright
```
Expected: ruff + pyright clean. For pytest, **this branch must introduce zero
new failures vs. `main`.** The only acceptable reds are the two pre-existing,
unrelated failures
`tests/test_command_docs.py::test_entities_doc_documents_workflow_identity_contract`
and `tests/test_user_guide_docs.py::test_entities_doc_documents_split_storage_data_root`
(a concurrent entities-doc refactor; already red on `main` at this branch's base
`95e032f6`). If any *other* test fails, fix it before committing. To confirm the
two are pre-existing, run just those two node-ids in a detached worktree at
`main` and verify they fail identically there.

- [ ] **Step 7: Commit** (from the repository root)

```bash
git add science/src/science_tool/skills_lint/lint.py science/tests/skills_lint/test_lint.py
git commit -m "feat(skills): ratchet missing-provenance to ERROR"
```

---

## Self-Review

**Spec coverage:**
- Classifier contract — `attributed` / `internal` / `undeclared` /
  `contradiction` / `bad-marker` / **`malformed-sources`**, with `sources: []`
  classified `malformed-sources` (not attributed) and reported once as
  `invalid-field` → Task 3 (`test_classify_provenance_outcomes`,
  `test_empty_or_blank_sources_are_invalid_field_not_missing_provenance`). ✓
- No cascade on broken frontmatter (absent, unterminated, unparsable,
  non-mapping) + **both** parsers' `or {}` bug fixed (`leaf_frontmatter` in
  `sources.py` → Task 1; `check_frontmatter` in `lint.py` → Task 3 Step 3) + no
  double-report → Task 1 (`test_leaf_frontmatter_rejects_non_mappings`) and
  Task 3 (`test_no_cascade_on_broken_frontmatter`,
  `test_nonmapping_frontmatter_is_invalid_yaml_not_missing_field` — integrated
  `check_skills` test proving non-mappings emit `invalid-yaml`, never
  `missing-field` or `missing-provenance`,
  `test_missing_provenance_not_double_reported_with_unknown_ref`). ✓
- Severity model (default error, `_relative_issues` copies, text+JSON, exit) →
  Task 2. ✓
- `_relative_issues` severity copy + real-tree CLI test → Task 2 Step 4 + Task 3
  `test_warn_only_run_exits_zero`. ✓
- `spec`/`software` kinds + `upstream_ref` regression + `not_applicable`
  freshness + `leaf_source_refs`/`sources_wellformed` strengthening → Task 1
  (incl. `test_spec_and_software_report_not_applicable_freshness`). ✓
- `INDEX.md` exclusion (valid frontmatter, still excluded) → Task 3 Step 4 +
  `test_index_md_excluded_from_coverage`. ✓
- Sweep all 41 (36 edited: 22 INTERNAL, 14 EXTERNAL) — decomposed per-file with
  verdict + primary source ids + acceptance criteria + frontmatter outcome →
  Tasks 4–8. Wave B splits 8 external / 2 internal (`proteomics-qa` and
  `somatic-mutation-qa` are generic measurement-QA discipline with no owning
  tool); `cosmic-signatures` fixed to `software` and attributed to what the leaf
  actually cites (COSMIC + dNdScv); snakemake carries the required Mölder
  method paper. ✓
- Per-wave verification fails on any ERROR severity + asserts exact `EXPECT`
  count + requires `science skills lint` exit 0 (via `&&`, so a non-zero exit
  short-circuits instead of being masked by a trailing `echo`) → shared
  method + Task 10 Step 5. ✓
- Repository coverage test (coverage, not severity) → Task 9. ✓
- Ratchet phase-specific + synthetic-WARN **CLI** test + full-suite verification
  → Task 10. ✓

**Placeholder scan:** No `TBD`/`TODO`. Every sweep file has an explicit verdict
and outcome; the only execution-time deferral is verifying each external
source's canonical `url`/DOI (a bounded lookup with a fixed record schema and
acceptance criteria), not open-ended "confirm." The two bounded statistics
files carry an explicit decision rule.

**Type consistency:** `Severity`, `SkillIssue.severity`,
`MISSING_PROVENANCE_SEVERITY`, `classify_provenance`/`ProvenanceState` (incl.
`malformed-sources`), `check_provenance`, `leaf_frontmatter`,
`sources_wellformed`, `_has_error`, and the two new `IssueKind` members are
named identically wherever referenced across Tasks 1–3, 9, 10.

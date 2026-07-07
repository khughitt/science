# Explore-Ideas Gap Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a read-only `science explore-ideas gaps` command that inspects applied exploration candidates and reports deterministic follow-up gaps.

**Architecture:** Extend `science_tool.explore_ideas` beside the existing apply and anchor resolver code. The core function returns structured dataclasses; the Click layer only renders text or JSON. Entity lookup uses `iter_entity_markdown` plus frontmatter parsing instead of path guessing.

**Tech Stack:** Python 3.13, Click, Pytest, Pyright, Ruff, Science entity frontmatter utilities.

---

### Task 1: Add result contracts and clean-result tests

**Files:**
- Modify: `science/src/science_tool/explore_ideas.py`
- Modify: `science/tests/test_explore_ideas_apply.py`

- [ ] **Step 1: Add imports in tests**

In `science/tests/test_explore_ideas_apply.py`, add `inspect_gaps_report` to the existing `science_tool.explore_ideas` import block:

```python
from science_tool.explore_ideas import (
    ApplyResult,
    ApplyValidationError,
    ApplyWriteBackError,
    CandidateBlock,
    apply_report,
    build_create_plan,
    check_report,
    derive_lens_views,
    inspect_gaps_report,
    parse_report,
    plan_report,
    resolve_report_path,
    write_back,
)
```

- [ ] **Step 2: Add a clean-result JSON shape test**

Append near the existing `apply_report` tests:

```python
def test_inspect_gaps_report_clean_applied_entity(tmp_path: Path) -> None:
    seed_project(tmp_path)
    report = _write_fixture(tmp_path)
    apply_report(tmp_path, "explore-2026-07-04", "test-model", date(2026, 7, 4))

    # Fill bodies so the newly-created scaffolds are no longer gap-only.
    for path in (tmp_path / "entities").rglob("*.md"):
        text = path.read_text(encoding="utf-8")
        path.write_text(text + "\nSubstantive follow-up note.\n", encoding="utf-8")

    result = inspect_gaps_report(tmp_path, "explore-2026-07-04")

    payload = result.to_dict()
    assert payload["report"] == str(report)
    assert payload["counts"] == {"entities": 2, "gaps": 0, "errors": 0, "warnings": 0}
    assert [row["candidate_id"] for row in payload["entities"]] == [
        "cand-mechanism-vagal-cytokine-loop",
        "cand-methodology-retest-drift-threshold",
    ]
    assert all(row["gaps"] == [] for row in payload["entities"])
```

- [ ] **Step 3: Run the new test and confirm it fails**

Run from `science/`:

```bash
PYTEST_DEBUG_TEMPROOT=/tmp uv run --frozen pytest \
  tests/test_explore_ideas_apply.py::test_inspect_gaps_report_clean_applied_entity \
  -q
```

Expected: import failure for `inspect_gaps_report`.

- [ ] **Step 4: Add dataclasses and a minimal clean implementation**

In `science/src/science_tool/explore_ideas.py`, add these dataclasses after `ApplyCheckResult`:

```python
@dataclass(frozen=True)
class GapItem:
    code: str
    severity: str
    message: str
    suggested_action: str

    def to_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "suggested_action": self.suggested_action,
        }


@dataclass(frozen=True)
class GapEntity:
    candidate_id: str
    entity_id: str | None
    kind: str | None
    path: Path | None
    gaps: list[GapItem]

    def to_dict(self, project_root: Path) -> dict[str, object]:
        path = None
        if self.path is not None:
            try:
                path = str(self.path.relative_to(project_root))
            except ValueError:
                path = str(self.path)
        return {
            "candidate_id": self.candidate_id,
            "entity_id": self.entity_id,
            "kind": self.kind,
            "path": path,
            "gaps": [gap.to_dict() for gap in self.gaps],
        }


@dataclass(frozen=True)
class GapReportResult:
    report: Path
    project_root: Path
    entities: list[GapEntity]

    @property
    def counts(self) -> dict[str, int]:
        gaps = [gap for entity in self.entities for gap in entity.gaps]
        return {
            "entities": len(self.entities),
            "gaps": len(gaps),
            "errors": sum(1 for gap in gaps if gap.severity == "error"),
            "warnings": sum(1 for gap in gaps if gap.severity == "warn"),
        }

    def to_dict(self) -> dict[str, object]:
        return {
            "report": str(self.report),
            "counts": self.counts,
            "entities": [entity.to_dict(self.project_root) for entity in self.entities],
        }
```

Add helper functions and a minimal inspector near `check_report`:

```python
def _entity_index(project_root: Path) -> dict[str, tuple[Path, dict, str]]:
    index: dict[str, tuple[Path, dict, str]] = {}
    for path in iter_entity_markdown(project_root / "entities"):
        parsed = _parse_markdown_file_preserving_body(path)
        entity_id = parsed.frontmatter.get("id")
        if isinstance(entity_id, str):
            index[entity_id] = (path, parsed.frontmatter, parsed.body)
    return index


def inspect_gaps_report(project_root: Path, from_value: str) -> GapReportResult:
    project_root = project_root.resolve()
    report_path = resolve_report_path(project_root, from_value)
    blocks = parse_report(report_path.read_text(encoding="utf-8"))
    index = _entity_index(project_root)

    entities: list[GapEntity] = []
    for block in blocks:
        if block.data.get("decision") != "applied":
            continue
        entity_id = block.data.get("applied_as")
        if not isinstance(entity_id, str) or not entity_id.strip():
            entities.append(
                GapEntity(
                    candidate_id=block.candidate_id,
                    entity_id=None,
                    kind=None,
                    path=None,
                    gaps=[
                        GapItem(
                            code="missing_applied_as",
                            severity="error",
                            message="applied block has no applied_as entity id",
                            suggested_action="Repair the report block with the created entity id.",
                        )
                    ],
                )
            )
            continue
        hit = index.get(entity_id.strip())
        if hit is None:
            entities.append(
                GapEntity(
                    candidate_id=block.candidate_id,
                    entity_id=entity_id.strip(),
                    kind=None,
                    path=None,
                    gaps=[
                        GapItem(
                            code="missing_entity",
                            severity="error",
                            message=f"{entity_id.strip()} does not resolve to a local entity",
                            suggested_action="Check whether the entity was moved, renamed, or never created.",
                        )
                    ],
                )
            )
            continue
        path, frontmatter, body = hit
        kind = frontmatter.get("kind") if isinstance(frontmatter.get("kind"), str) else None
        entities.append(GapEntity(block.candidate_id, entity_id.strip(), kind, path, gaps=[]))

    return GapReportResult(report=report_path, project_root=project_root, entities=entities)
```

- [ ] **Step 5: Run the clean-result test**

Run from `science/`:

```bash
PYTEST_DEBUG_TEMPROOT=/tmp uv run --frozen pytest \
  tests/test_explore_ideas_apply.py::test_inspect_gaps_report_clean_applied_entity \
  -q
```

Expected: pass.

### Task 2: Detect deterministic gap codes

**Files:**
- Modify: `science/src/science_tool/explore_ideas.py`
- Modify: `science/tests/test_explore_ideas_apply.py`

- [ ] **Step 1: Add gap-code tests**

Append these tests near `test_inspect_gaps_report_clean_applied_entity`:

```python
def _gap_codes(result) -> list[str]:
    return [gap["code"] for row in result.to_dict()["entities"] for gap in row["gaps"]]


def test_inspect_gaps_report_reports_missing_applied_as(tmp_path: Path) -> None:
    seed_project(tmp_path)
    report = tmp_path / "doc" / "explorations" / "explore-missing.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("```yaml\ncandidate_id: cand-x\ndecision: applied\n```\n", encoding="utf-8")

    result = inspect_gaps_report(tmp_path, str(report))

    assert _gap_codes(result) == ["missing_applied_as"]
    assert result.counts == {"entities": 1, "gaps": 1, "errors": 1, "warnings": 0}


def test_inspect_gaps_report_reports_missing_entity(tmp_path: Path) -> None:
    seed_project(tmp_path)
    report = tmp_path / "doc" / "explorations" / "explore-stale.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(
        "```yaml\ncandidate_id: cand-x\ndecision: applied\napplied_as: question:no-such\n```\n",
        encoding="utf-8",
    )

    result = inspect_gaps_report(tmp_path, str(report))

    assert _gap_codes(result) == ["missing_entity"]


def test_inspect_gaps_report_reports_entity_gaps(tmp_path: Path) -> None:
    seed_project(tmp_path)
    report = _write_fixture(tmp_path)
    apply_report(tmp_path, "explore-2026-07-04", "test-model", date(2026, 7, 4))
    text = report.read_text(encoding="utf-8").replace("ref: cite:chen2022", "ref: null")
    report.write_text(text, encoding="utf-8")
    q_path = next((tmp_path / "entities" / "questions").glob("*.md"))
    fm = _frontmatter(q_path)
    fm.pop("source_refs", None)
    fm.pop("related", None)
    body = "# Vagal tone as a cytokine feedback regulator\n\n## Summary\n\n\n## Notes\n"
    q_path.write_text("---\n" + yaml.safe_dump(fm, sort_keys=False) + "---\n" + body, encoding="utf-8")

    result = inspect_gaps_report(tmp_path, "explore-2026-07-04")

    first_codes = [gap["code"] for gap in result.to_dict()["entities"][0]["gaps"]]
    assert first_codes == ["empty_body", "unresolved_anchors", "missing_related"]
```

- [ ] **Step 2: Run the gap-code tests and confirm failure**

Run from `science/`:

```bash
PYTEST_DEBUG_TEMPROOT=/tmp uv run --frozen pytest \
  tests/test_explore_ideas_apply.py::test_inspect_gaps_report_reports_missing_applied_as \
  tests/test_explore_ideas_apply.py::test_inspect_gaps_report_reports_missing_entity \
  tests/test_explore_ideas_apply.py::test_inspect_gaps_report_reports_entity_gaps \
  -q
```

Expected: the first two pass after Task 1; `test_inspect_gaps_report_reports_entity_gaps` fails because entity-level gap detection is not implemented.

- [ ] **Step 3: Add entity-level gap helpers**

In `science/src/science_tool/explore_ideas.py`, add:

```python
def _body_has_substantive_text(body: str) -> bool:
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith("<!--"):
            continue
        if line.endswith("-->"):
            continue
        return True
    return False


def _supporting_anchor_refs(data: dict) -> list[str]:
    refs: list[str] = []
    seen: set[str] = set()
    anchors = data.get("literature_anchors") or []
    if not isinstance(anchors, list):
        return []
    for anchor in anchors:
        if not isinstance(anchor, dict):
            continue
        ref = anchor.get("ref")
        note = anchor.get("note")
        if not isinstance(ref, str) or not ref.strip():
            continue
        if isinstance(note, str) and note.startswith("predates:"):
            continue
        if ref not in seen:
            seen.add(ref)
            refs.append(ref)
    return refs


def _unresolved_anchor_count(data: dict) -> int:
    anchors = data.get("literature_anchors") or []
    if not isinstance(anchors, list):
        return 0
    count = 0
    for anchor in anchors:
        if isinstance(anchor, dict) and not anchor.get("ref"):
            count += 1
    return count


def _candidate_has_lens_views(data: dict) -> bool:
    if data.get("lens_views"):
        return True
    return isinstance(data.get("lens"), str) and isinstance(data.get("rationale"), str) and bool(data["rationale"].strip())


def _entity_gap_items(block: CandidateBlock, frontmatter: dict, body: str, report_path: Path) -> list[GapItem]:
    gaps: list[GapItem] = []
    if not _body_has_substantive_text(body):
        gaps.append(
            GapItem(
                code="empty_body",
                severity="warn",
                message="entity body is still scaffold-only",
                suggested_action="Fill the entity body from the candidate rationale and supporting evidence.",
            )
        )

    unresolved = _unresolved_anchor_count(block.data)
    if unresolved:
        plural = "anchor is" if unresolved == 1 else "anchors are"
        gaps.append(
            GapItem(
                code="unresolved_anchors",
                severity="warn",
                message=f"{unresolved} literature {plural} unresolved",
                suggested_action=f"Run science explore-ideas resolve-anchors --from {report_path}",
            )
        )

    if _supporting_anchor_refs(block.data) and not frontmatter.get("source_refs"):
        gaps.append(
            GapItem(
                code="missing_source_refs",
                severity="warn",
                message="candidate has resolved supporting anchors but entity has no source_refs",
                suggested_action="Add the resolved supporting refs to source_refs.",
            )
        )

    if block.data.get("related_existing") and not frontmatter.get("related"):
        gaps.append(
            GapItem(
                code="missing_related",
                severity="warn",
                message="candidate has related_existing but entity has no related links",
                suggested_action="Add the canonical related refs to related.",
            )
        )

    if _candidate_has_lens_views(block.data) and not frontmatter.get("lens_views"):
        gaps.append(
            GapItem(
                code="missing_lens_views",
                severity="warn",
                message="candidate has lens views but entity has no lens_views",
                suggested_action="Backfill lens views from the exploration report.",
            )
        )
    return gaps
```

Then replace the clean `GapEntity(..., gaps=[])` construction in `inspect_gaps_report` with:

```python
        gaps = _entity_gap_items(block, frontmatter, body, report_path)
        entities.append(GapEntity(block.candidate_id, entity_id.strip(), kind, path, gaps=gaps))
```

- [ ] **Step 4: Run the gap-code tests**

Run from `science/`:

```bash
PYTEST_DEBUG_TEMPROOT=/tmp uv run --frozen pytest \
  tests/test_explore_ideas_apply.py::test_inspect_gaps_report_reports_missing_applied_as \
  tests/test_explore_ideas_apply.py::test_inspect_gaps_report_reports_missing_entity \
  tests/test_explore_ideas_apply.py::test_inspect_gaps_report_reports_entity_gaps \
  -q
```

Expected: pass.

### Task 3: Add CLI command and renderers

**Files:**
- Modify: `science/src/science_tool/cli.py`
- Modify: `science/tests/test_explore_ideas_apply.py`

- [ ] **Step 1: Add CLI tests**

Append:

```python
def test_cli_explore_ideas_gaps_text() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir="/tmp"):
        root = Path.cwd()
        seed_project(root)
        _write_fixture(root)
        apply_report(root, "explore-2026-07-04", "test-model", date(2026, 7, 4))

        result = runner.invoke(main, ["explore-ideas", "gaps", "--from", "explore-2026-07-04"])

        assert result.exit_code == 0, result.output
        assert "applied entities inspected" in result.output
        assert "empty_body" in result.output


def test_cli_explore_ideas_gaps_json() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir="/tmp"):
        root = Path.cwd()
        seed_project(root)
        _write_fixture(root)
        apply_report(root, "explore-2026-07-04", "test-model", date(2026, 7, 4))

        result = runner.invoke(main, ["explore-ideas", "gaps", "--from", "explore-2026-07-04", "--format", "json"])

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["counts"]["entities"] == 2
        assert payload["counts"]["gaps"] >= 1
```

- [ ] **Step 2: Run CLI tests and confirm failure**

Run from `science/`:

```bash
PYTEST_DEBUG_TEMPROOT=/tmp uv run --frozen pytest \
  tests/test_explore_ideas_apply.py::test_cli_explore_ideas_gaps_text \
  tests/test_explore_ideas_apply.py::test_cli_explore_ideas_gaps_json \
  -q
```

Expected: fail because `explore-ideas gaps` does not exist.

- [ ] **Step 3: Wire CLI command**

In `science/src/science_tool/cli.py`, import `inspect_gaps_report` from `science_tool.explore_ideas` where the other explore-ideas helpers are imported.

Add this renderer and command after `explore_ideas_apply`:

```python
def _render_gap_result_text(result) -> None:
    counts = result.counts
    click.echo(
        f"{counts['entities']} applied entities inspected, "
        f"{counts['gaps']} gaps ({counts['errors']} errors, {counts['warnings']} warnings)"
    )
    for entity in result.entities:
        if not entity.gaps:
            continue
        label = entity.entity_id or "<missing applied_as>"
        kind = entity.kind or "unknown"
        click.echo("")
        click.echo(f"{entity.candidate_id} -> {label} ({kind})")
        for gap in entity.gaps:
            click.echo(f"  {gap.severity.upper()} {gap.code}: {gap.message}")
            click.echo(f"    next: {gap.suggested_action}")


@explore_ideas_group.command("gaps")
@click.option("--from", "from_value", required=True, help="Report file path, or report id (basename stem).")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    show_default=True,
)
def explore_ideas_gaps(from_value: str, output_format: str) -> None:
    """Inspect applied exploration entities for deterministic follow-up gaps."""
    try:
        result = inspect_gaps_report(Path.cwd(), from_value)
    except ApplyValidationError as exc:
        raise click.ClickException(str(exc)) from exc

    if output_format == "json":
        click.echo(json.dumps(result.to_dict(), indent=2))
    else:
        _render_gap_result_text(result)
```

- [ ] **Step 4: Run CLI tests**

Run from `science/`:

```bash
PYTEST_DEBUG_TEMPROOT=/tmp uv run --frozen pytest \
  tests/test_explore_ideas_apply.py::test_cli_explore_ideas_gaps_text \
  tests/test_explore_ideas_apply.py::test_cli_explore_ideas_gaps_json \
  -q
```

Expected: pass.

### Task 4: Update command and skill docs

**Files:**
- Modify: `commands/explore-ideas.md`
- Modify: `codex-skills/science-explore-ideas/SKILL.md`
- Modify: `science/tests/test_command_docs.py`

- [ ] **Step 1: Add command-doc test**

In `science/tests/test_command_docs.py`, add:

```python
def test_explore_ideas_documents_gap_closure_command() -> None:
    text = _read("commands/explore-ideas.md")
    assert "science explore-ideas gaps --from" in text
    assert "unresolved_anchors" in text
    assert "missing_source_refs" in text
```

- [ ] **Step 2: Update command docs**

In `commands/explore-ideas.md`, after the apply section, add:

```markdown
After apply, inspect the created entities for deterministic follow-up gaps:

```bash
uv run science explore-ideas gaps --from <report-path-or-id>
```

Use `--format json` when another tool needs the structured result. The gaps
command is read-only. It inspects only `decision: applied` blocks and reports
repair work such as `missing_applied_as`, `missing_entity`, `empty_body`,
`unresolved_anchors`, `missing_source_refs`, `missing_related`, and
`missing_lens_views`.
```
```

- [ ] **Step 3: Mirror command docs in Codex skill**

Make the same addition in `codex-skills/science-explore-ideas/SKILL.md`.

- [ ] **Step 4: Run docs tests**

Run from `science/`:

```bash
PYTEST_DEBUG_TEMPROOT=/tmp uv run --frozen pytest \
  tests/test_command_docs.py \
  tests/test_codex_skills.py \
  -q
```

Expected: pass.

### Task 5: Focused verification

**Files:**
- No code changes expected.

- [ ] **Step 1: Run focused tests**

Run from `science/`:

```bash
PYTEST_DEBUG_TEMPROOT=/tmp uv run --frozen pytest \
  tests/test_explore_ideas_apply.py \
  tests/test_explore_ideas_anchor_resolver.py \
  tests/test_command_docs.py \
  tests/test_codex_skills.py \
  -q
```

Expected: pass.

- [ ] **Step 2: Run Ruff**

Run from `science/`:

```bash
uv run --frozen ruff check
```

Expected: pass.

- [ ] **Step 3: Run Pyright**

Run from `science/`:

```bash
uv run --frozen pyright \
  src/science_tool/explore_ideas.py \
  src/science_tool/cli.py \
  tests/test_explore_ideas_apply.py
```

Expected: pass.

- [ ] **Step 4: Inspect final diff**

Run from the worktree root:

```bash
git diff --stat
git diff -- science/src/science_tool/explore_ideas.py science/src/science_tool/cli.py science/tests/test_explore_ideas_apply.py commands/explore-ideas.md codex-skills/science-explore-ideas/SKILL.md
```

Expected: diff contains only the gap-report command, tests, docs, and the design/plan docs.

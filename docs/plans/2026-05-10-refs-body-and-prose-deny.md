# Refs Body-Entity Scan + Prose-Lint Deny List Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Two related additions:

1. **`science refs check --include-body`** — extend reference checking to scan body prose for typed `<kind>:<id>` entity refs (e.g., `task:t050`, `question:q01-foo`). Generalizes the body-text entity-ref portion of natural-systems's `scripts/audit-citations.ts` (t469).
2. **`prose_lint.short_form_ids_deny`** — `science.yaml` config knob to suppress `short-form-ids` detector hits on a deny-list (e.g., `H1`, `D1`, `T1` in biology-heavy projects).

**Architecture:**

- `science refs check` already scans body text for short-form refs (`tNN`, `HNN`), `[@bibkey]` citations, DOIs, PMIDs, and markdown links. The new check adds detection of **typed-form** entity refs in body (currently only validated in frontmatter via `_extract_frontmatter_refs`). Implementation: build an entity-index helper, add a body-scan function, gate behind `--include-body` (opt-in to avoid surprise warnings on existing projects).
- `prose_lint` deny-list is a small extension: new optional field on `ProseLintConfig`, threaded through `detect_short_form_ids` and `scan_root` and the CLI.

**Tech Stack:** Python 3.13, Click, Pydantic, pytest. No new deps.

**Origin:**
- Section A is the natural-systems `audit-citations.ts` body-entity-ref check generalized to use `_LOCAL_ENTITY_KINDS` (27 kinds) instead of the project-local 10-kind subset.
- Section B is the tuning option called out in `docs/audits/2026-05-10-prose-lint-baselines.md`: even though the audited projects didn't show biology-shorthand false-positives at scale, biology-heavy projects (real cyclins, histones, T1-weighted MRI) need an escape hatch.

---

## File Structure

- Modify: `science/src/science_tool/refs.py`
  - Add `_load_entity_index(root) -> set[str]` (project-wide `<kind>:<id>` registry from frontmatter sweep).
  - Add `_TYPED_ENTITY_REF_RE` constant.
  - Add `_scan_body_typed_refs()` helper.
  - Modify `check_refs()` to accept `include_body: bool = False` and run the body-typed-ref scan when set.
- Modify: `science/src/science_tool/refs_cli.py`
  - Add `--include-body` flag on the `check` subcommand; pass through to `check_refs`.
- Modify: `science/tests/test_refs.py`
  - Add tests covering the new check.
- Modify: `science/src/science_tool/project_config.py`
  - Add `short_form_ids_deny: list[str] = Field(default_factory=list)` to `ProseLintConfig`.
- Modify: `science/tests/test_project_config_prose_lint.py`
  - Add a test for the new field.
- Modify: `science/src/science_tool/prose_lint.py`
  - Thread `deny: list[str] | None = None` through `detect_short_form_ids` and `scan_root`.
- Modify: `science/src/science_tool/prose_lint_cli.py`
  - Read deny-list from config; pass to `scan_root`.
- Modify: `science/tests/test_prose_lint.py` and `science/tests/test_prose_lint_cli.py`
  - Add tests covering the new param.
- Modify: `docs/conventions/prose-lints.md`
  - Document `short_form_ids_deny` schema.
- Create: `docs/audits/2026-05-10-refs-body-baselines.md` (final task)
  - Capture per-project counts from running `science refs check --include-body`.

---

## Section A — `science refs check --include-body`

### Task 1: Add entity-index loader

**Files:**
- Modify: `science/src/science_tool/refs.py`
- Modify: `science/tests/test_refs.py`

- [ ] **Step 1: Write the failing test**

Append to `science/tests/test_refs.py`:

```python
def test_load_entity_index_collects_kind_id_pairs(tmp_path):
    """`_load_entity_index` returns the set of <kind>:<id> values discovered in frontmatter."""
    from science_tool.refs import _load_entity_index

    (tmp_path / "doc").mkdir()
    (tmp_path / "doc" / "q01.md").write_text(
        "---\n"
        "id: question:q01-foo\n"
        "type: question\n"
        "---\n"
        "Body.\n"
    )
    (tmp_path / "doc" / "t050.md").write_text(
        "---\n"
        "id: task:t050\n"
        "type: task\n"
        "---\n"
        "Body.\n"
    )
    (tmp_path / "doc" / "no-id.md").write_text(
        "---\n"
        "type: discussion\n"
        "---\n"
        "Body.\n"
    )

    index = _load_entity_index(tmp_path)
    assert "question:q01-foo" in index
    assert "task:t050" in index
    assert len(index) == 2  # no-id.md contributes nothing
```

- [ ] **Step 2: Verify failure**

```bash
cd /mnt/ssd/Dropbox/science/science
uv run pytest tests/test_refs.py::test_load_entity_index_collects_kind_id_pairs -v
```

Expected: FAIL with `ImportError: cannot import name '_load_entity_index'`.

- [ ] **Step 3: Implement the loader**

Add to `science/src/science_tool/refs.py` (near the other `_load_*` helpers, e.g., after `_load_project_ids`):

```python
def _load_entity_index(root: Path) -> set[str]:
    """Return the set of canonical `<kind>:<id>` strings declared in frontmatter.

    Walks the project's markdown tree, parses each file's frontmatter, and
    collects values from the `id:` field that already include a kind prefix
    (i.e., match the `<kind>:<slug>` shape with kind in `_LOCAL_ENTITY_KINDS`).

    Used by body-prose scanning (`--include-body`) to validate typed refs.
    """
    index: set[str] = set()
    for path in _collect_markdown_files(root):
        try:
            fm = parse_frontmatter(path)
        except Exception:  # noqa: BLE001 — frontmatter helper is robust; defensive only.
            continue
        if not isinstance(fm, dict):
            continue
        raw_id = fm.get("id")
        if not isinstance(raw_id, str):
            continue
        if ":" not in raw_id:
            continue
        kind, _, slug = raw_id.partition(":")
        if kind in _LOCAL_ENTITY_KINDS and slug:
            index.add(raw_id)
    return index
```

Note: `parse_frontmatter` is already imported at the top of refs.py (`from science_model.frontmatter import parse_frontmatter`).

- [ ] **Step 4: Verify pass**

```bash
cd /mnt/ssd/Dropbox/science/science
uv run pytest tests/test_refs.py::test_load_entity_index_collects_kind_id_pairs -v
uv run ruff check src/science_tool/refs.py tests/test_refs.py
```

Expected: PASS; ruff clean.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/refs.py science/tests/test_refs.py
git commit -m "feat(refs): add _load_entity_index for typed body-ref validation"
```

---

### Task 2: Add typed-body-ref scanner

**Files:**
- Modify: `science/src/science_tool/refs.py`
- Modify: `science/tests/test_refs.py`

- [ ] **Step 1: Write the failing tests**

Append to `science/tests/test_refs.py`:

```python
class TestBodyTypedRefScan:
    def _project(self, tmp_path):
        (tmp_path / "doc").mkdir()
        (tmp_path / "doc" / "q01.md").write_text(
            "---\nid: question:q01-foo\ntype: question\n---\nBody.\n"
        )
        (tmp_path / "doc" / "t050.md").write_text(
            "---\nid: task:t050\ntype: task\n---\nBody.\n"
        )
        return tmp_path

    def test_flags_unknown_typed_ref_in_body(self, tmp_path):
        from science_tool.refs import check_refs

        root = self._project(tmp_path)
        (root / "doc" / "report.md").write_text(
            "---\ntype: report\n---\nSee task:t999 for the gap.\n"
        )
        issues = check_refs(root, include_body=True)
        body_issues = [i for i in issues if i.ref_type == "body-entity-ref"]
        assert len(body_issues) == 1
        assert body_issues[0].ref_value == "task:t999"
        assert "doc/report.md" in body_issues[0].file
        assert body_issues[0].line == 4

    def test_no_flag_for_resolved_typed_ref(self, tmp_path):
        from science_tool.refs import check_refs

        root = self._project(tmp_path)
        (root / "doc" / "report.md").write_text(
            "---\ntype: report\n---\nSee task:t050 for the work.\n"
        )
        issues = check_refs(root, include_body=True)
        assert [i for i in issues if i.ref_type == "body-entity-ref"] == []

    def test_skips_typed_refs_in_fenced_code(self, tmp_path):
        from science_tool.refs import check_refs

        root = self._project(tmp_path)
        (root / "doc" / "report.md").write_text(
            "---\ntype: report\n---\n```\nExample: task:t999\n```\n"
        )
        issues = check_refs(root, include_body=True)
        assert [i for i in issues if i.ref_type == "body-entity-ref"] == []

    def test_skips_typed_refs_in_inline_code(self, tmp_path):
        from science_tool.refs import check_refs

        root = self._project(tmp_path)
        (root / "doc" / "report.md").write_text(
            "---\ntype: report\n---\nUse the `task:tNN` placeholder.\n"
        )
        issues = check_refs(root, include_body=True)
        assert [i for i in issues if i.ref_type == "body-entity-ref"] == []

    def test_default_off_when_include_body_false(self, tmp_path):
        from science_tool.refs import check_refs

        root = self._project(tmp_path)
        (root / "doc" / "report.md").write_text(
            "---\ntype: report\n---\nSee task:t999 for the gap.\n"
        )
        issues = check_refs(root)  # include_body=False default
        assert [i for i in issues if i.ref_type == "body-entity-ref"] == []

    def test_skips_cross_project_refs(self, tmp_path):
        from science_tool.refs import check_refs

        root = self._project(tmp_path)
        # Triple-segment refs like `mm30:task:t050` are cross-project; not our concern.
        (root / "doc" / "report.md").write_text(
            "---\ntype: report\n---\nSee mm30:task:t050.\n"
        )
        issues = check_refs(root, include_body=True)
        assert [i for i in issues if i.ref_type == "body-entity-ref"] == []
```

- [ ] **Step 2: Verify failure**

```bash
cd /mnt/ssd/Dropbox/science/science
uv run pytest tests/test_refs.py::TestBodyTypedRefScan -v
```

Expected: FAIL — `check_refs()` doesn't accept `include_body` kwarg.

- [ ] **Step 3: Implement the scanner**

Add to `science/src/science_tool/refs.py` (near the other regex constants, around line 60):

```python
# Typed entity ref in body prose: `<kind>:<slug>` where kind is canonical.
# Uses a kind-list alternation to avoid matching unrelated `word:word` patterns.
# Slug pattern: starts with a-z or 0-9, followed by [a-z0-9_-]+ (no spaces).
_TYPED_ENTITY_REF_RE = re.compile(
    r"\b(" + "|".join(sorted(_LOCAL_ENTITY_KINDS, key=len, reverse=True)) + r"):([a-z0-9][a-z0-9_-]+)\b"
)
```

Note: ordering by length-descending prevents `"data" + ":foo"` from matching when `"data-package"` is a kind (longest-first wins in alternation).

Add this helper function near the other `_scan_*` helpers (or alongside `check_refs()` if no such grouping exists):

```python
def _scan_body_typed_refs(
    file_path: Path,
    rel_path: str,
    lines: list[str],
    frontmatter_lines: set[int],
    entity_index: set[str],
) -> list[RefIssue]:
    """Scan body prose for typed `<kind>:<slug>` refs not in the entity index.

    Skips frontmatter, fenced code, inline code, and cross-project triple-form
    refs (those have a peer `<project-id>:` prefix and are validated separately).
    """
    issues: list[RefIssue] = []
    in_fence = False
    for line_num, line in enumerate(lines, start=1):
        if line_num in frontmatter_lines:
            continue
        if _is_fence_line(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        scan_line = _strip_inline_code(line)
        for match in _TYPED_ENTITY_REF_RE.finditer(scan_line):
            kind, slug = match.group(1), match.group(2)
            ref = f"{kind}:{slug}"
            # Cross-project refs have an extra `<project-id>:` prefix; the
            # alternation matched only the kind:slug portion. Skip if the
            # preceding character is also `:` (signaling a triple-form).
            if match.start() > 0 and scan_line[match.start() - 1] == ":":
                continue
            if ref in entity_index:
                continue
            issues.append(
                RefIssue(
                    file=rel_path,
                    line=line_num,
                    ref_type="body-entity-ref",
                    ref_value=ref,
                    message=f"{ref} — typed entity ref not found in project frontmatter `id:` index",
                )
            )
    return issues
```

- [ ] **Step 4: Wire into `check_refs()`**

Modify the `check_refs` signature and body. Find the existing line:

```python
def check_refs(root: Path) -> list[RefIssue]:
```

Replace with:

```python
def check_refs(root: Path, *, include_body: bool = False) -> list[RefIssue]:
```

Inside the function, after the existing `bib_keys = _load_bib_keys(root)` line (around line 333), add:

```python
    entity_index = _load_entity_index(root) if include_body else set()
```

Then inside the per-file loop, AFTER the existing per-line `for line_num, line in enumerate(...)` loop closes, add (8-space indent — same level as the per-line `for` statement):

```python
        if include_body:
            issues.extend(
                _scan_body_typed_refs(
                    file_path,
                    rel_path,
                    lines,
                    frontmatter_lines,
                    entity_index,
                )
            )
```

The insertion point is between the closing of the per-line loop (currently around line 543) and the start of the post-file marker-scan block (currently around line 545 with the `from science_tool.markers import scan_markers` import). Reuse the already-bound `lines` and `frontmatter_lines` variables; do not re-read.

- [ ] **Step 5: Verify pass**

```bash
cd /mnt/ssd/Dropbox/science/science
uv run pytest tests/test_refs.py -v
uv run ruff check src/science_tool/refs.py tests/test_refs.py
```

Expected: all pre-existing test_refs tests still pass, plus 6 new TestBodyTypedRefScan tests; ruff clean.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/refs.py science/tests/test_refs.py
git commit -m "feat(refs): add --include-body typed entity-ref body scanner"
```

---

### Task 3: Wire `--include-body` flag into refs_cli

**Files:**
- Modify: `science/src/science_tool/refs_cli.py`
- Modify: `science/tests/test_refs.py` (or add a new CLI test file if appropriate)

- [ ] **Step 1: Find the existing `check` subcommand**

```bash
grep -n "@refs_group.command(\"check\"\|def check" science/src/science_tool/refs_cli.py | head -5
```

This shows the existing `check` Click command and its signature.

- [ ] **Step 2: Write the failing CLI test**

Append to `science/tests/test_refs.py`:

```python
def test_refs_check_include_body_flag_emits_typed_ref_issues(tmp_path):
    """The CLI `--include-body` flag enables body-typed-ref scanning."""
    from click.testing import CliRunner

    from science_tool.refs_cli import refs_group

    (tmp_path / "doc").mkdir()
    (tmp_path / "doc" / "t050.md").write_text(
        "---\nid: task:t050\ntype: task\n---\nBody.\n"
    )
    (tmp_path / "doc" / "report.md").write_text(
        "---\ntype: report\n---\nSee task:t999 for the gap.\n"
    )

    runner = CliRunner()
    result_no_body = runner.invoke(refs_group, ["check", "--root", str(tmp_path), "--format", "json"])
    result_with_body = runner.invoke(
        refs_group, ["check", "--root", str(tmp_path), "--include-body", "--format", "json"]
    )

    import json

    payload_no = json.loads(result_no_body.output)
    payload_yes = json.loads(result_with_body.output)
    types_no = {h["ref_type"] for h in payload_no.get("issues", payload_no.get("hits", []))}
    types_yes = {h["ref_type"] for h in payload_yes.get("issues", payload_yes.get("hits", []))}
    assert "body-entity-ref" not in types_no
    assert "body-entity-ref" in types_yes
```

(The fallback `payload.get("issues", payload.get("hits", []))` is defensive — different code paths may use different output key names; check the actual JSON structure produced by `science refs check --format json` and adjust the assertion accordingly.)

- [ ] **Step 3: Verify failure**

```bash
cd /mnt/ssd/Dropbox/science/science
uv run pytest tests/test_refs.py::test_refs_check_include_body_flag_emits_typed_ref_issues -v
```

Expected: FAIL — `--include-body` is not a recognized option.

- [ ] **Step 4: Add the flag**

Open `science/src/science_tool/refs_cli.py`. On the `check` subcommand:

1. Add a new Click option declaration (place it near the other options like `--strict`, `--summary-only`):

```python
@click.option(
    "--include-body",
    is_flag=True,
    help="Additionally scan body prose for typed `<kind>:<slug>` refs (not just frontmatter).",
)
```

2. Add `include_body: bool` to the function's signature in the same position as the other `is_flag` options.

3. Pass it through to `check_refs`:

```python
issues = check_refs(root, include_body=include_body)
```

(or whatever the existing call shape is — modify it in place).

- [ ] **Step 5: Verify pass**

```bash
cd /mnt/ssd/Dropbox/science/science
uv run pytest tests/test_refs.py::test_refs_check_include_body_flag_emits_typed_ref_issues -v
uv run ruff check src/science_tool/refs_cli.py
```

Expected: PASS; ruff clean.

- [ ] **Step 6: End-to-end smoke test**

```bash
cd /mnt/ssd/Dropbox/science/.claude/worktrees/<this-worktree>
uv run --project science science refs check --help | grep -A1 include-body
uv run --project science science refs check --root /home/keith/d/natural-systems --include-body --format json --summary-only 2>&1 | tail -20
```

Expected: `--include-body` appears in `--help` output; the natural-systems run produces a non-zero count for `body-entity-ref` issues (we know audit-citations.ts finds many).

- [ ] **Step 7: Commit**

```bash
git add science/src/science_tool/refs_cli.py science/tests/test_refs.py
git commit -m "feat(refs): add --include-body CLI flag for refs check"
```

---

## Section B — Prose-lint `short_form_ids_deny`

### Task 4: Add `short_form_ids_deny` field to `ProseLintConfig`

**Files:**
- Modify: `science/src/science_tool/project_config.py`
- Modify: `science/tests/test_project_config_prose_lint.py`

- [ ] **Step 1: Write the failing test**

Append to `science/tests/test_project_config_prose_lint.py`:

```python
def test_short_form_ids_deny_defaults_to_empty(tmp_path):
    (tmp_path / "science.yaml").write_text(
        "name: demo\nprose_lint:\n  anchor_patterns: ['task:']\n"
    )
    config = load_project_config(tmp_path)
    assert config.prose_lint is not None
    assert config.prose_lint.short_form_ids_deny == []


def test_short_form_ids_deny_explicit_list(tmp_path):
    (tmp_path / "science.yaml").write_text(
        "name: demo\n"
        "prose_lint:\n"
        "  short_form_ids_deny:\n"
        "    - 'D1'\n"
        "    - 'H3'\n"
        "    - 'T1'\n"
    )
    config = load_project_config(tmp_path)
    assert config.prose_lint.short_form_ids_deny == ["D1", "H3", "T1"]
```

- [ ] **Step 2: Verify failure**

```bash
cd /mnt/ssd/Dropbox/science/science
uv run pytest tests/test_project_config_prose_lint.py -v
```

Expected: FAIL — field doesn't exist.

- [ ] **Step 3: Add the field**

Open `science/src/science_tool/project_config.py`. Find the `ProseLintConfig` class. Add a new field:

```python
    short_form_ids_deny: list[str] = Field(default_factory=list)
```

Place it after the existing `anchor_patterns` field.

- [ ] **Step 4: Verify pass**

```bash
cd /mnt/ssd/Dropbox/science/science
uv run pytest tests/test_project_config_prose_lint.py -v
uv run ruff check src/science_tool/project_config.py
```

Expected: PASS; ruff clean.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/project_config.py science/tests/test_project_config_prose_lint.py
git commit -m "feat(project_config): add short_form_ids_deny to ProseLintConfig"
```

---

### Task 5: Thread `deny` through `detect_short_form_ids` and `scan_root`

**Files:**
- Modify: `science/src/science_tool/prose_lint.py`
- Modify: `science/tests/test_prose_lint.py`

- [ ] **Step 1: Write failing tests**

Append to `science/tests/test_prose_lint.py`:

```python
class TestShortFormIdsDeny:
    def test_deny_list_suppresses_matching_token(self, tmp_path):
        path = _write(tmp_path, "Cyclin D1 is upregulated. Histone H3 marks chromatin.\n")
        # Without deny: both D1 and H3 are flagged
        issues_default = detect_short_form_ids(path)
        flagged = {i.message.split("'")[1] for i in issues_default}
        assert "D1" in flagged
        assert "H3" in flagged

        # With deny: D1 and H3 are skipped
        issues_denied = detect_short_form_ids(path, deny=["D1", "H3"])
        flagged_denied = {i.message.split("'")[1] for i in issues_denied}
        assert "D1" not in flagged_denied
        assert "H3" not in flagged_denied

    def test_deny_list_does_not_affect_other_tokens(self, tmp_path):
        path = _write(tmp_path, "Refer to t050 and D1 here.\n")
        issues = detect_short_form_ids(path, deny=["D1"])
        flagged = {i.message.split("'")[1] for i in issues}
        assert "t050" in flagged  # unaffected
        assert "D1" not in flagged

    def test_scan_root_threads_deny_list(self, tmp_path):
        from science_tool.prose_lint import scan_root

        (tmp_path / "doc").mkdir()
        (tmp_path / "doc" / "a.md").write_text("Cyclin D1 effect on cells.\n")
        result = scan_root(tmp_path, short_form_ids_deny=["D1"])
        assert result["counts"].get("short-form-ids", 0) == 0
```

- [ ] **Step 2: Verify failure**

```bash
cd /mnt/ssd/Dropbox/science/science
uv run pytest tests/test_prose_lint.py::TestShortFormIdsDeny -v
```

Expected: FAIL — `detect_short_form_ids` doesn't accept `deny`; `scan_root` doesn't accept `short_form_ids_deny`.

- [ ] **Step 3: Modify `detect_short_form_ids`**

Open `science/src/science_tool/prose_lint.py`. Modify the `detect_short_form_ids` signature:

```python
def detect_short_form_ids(
    path: Path,
    *,
    strict: bool = False,
    deny: list[str] | None = None,
) -> list[LintIssue]:
```

Inside the function body, just after the loop entry that extracts `short = match.group(0)`, add the deny check:

```python
            if deny and short in deny:
                continue
```

Place it BEFORE the existing canonical-prefix skip and BEFORE the issue append. This way denied tokens are silently skipped just like canonical-form refs.

- [ ] **Step 4: Modify `scan_root`**

In the same file, modify `scan_root`:

```python
def scan_root(
    root: Path,
    *,
    checks: list[str] | None = None,
    strict: bool = False,
    anchor_patterns: list[str] | None = None,
    short_form_ids_deny: list[str] | None = None,
) -> dict:
```

Inside the dispatch loop, modify the per-detector call to forward `deny` for `short-form-ids`:

```python
            if check == "numeric-anchor":
                hits.extend(detector(path, strict=strict, anchor_patterns=anchor_patterns))
            elif check == "short-form-ids":
                hits.extend(detector(path, strict=strict, deny=short_form_ids_deny))
            else:
                hits.extend(detector(path, strict=strict))
```

- [ ] **Step 5: Verify pass**

```bash
cd /mnt/ssd/Dropbox/science/science
uv run pytest tests/test_prose_lint.py -v
uv run ruff check src/science_tool/prose_lint.py
```

Expected: 32 prose_lint tests PASS (29 + 3 new); ruff clean.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/prose_lint.py science/tests/test_prose_lint.py
git commit -m "feat(prose_lint): thread short_form_ids_deny through detector and scan_root"
```

---

### Task 6: Wire deny-list through CLI

**Files:**
- Modify: `science/src/science_tool/prose_lint_cli.py`
- Modify: `science/tests/test_prose_lint_cli.py`

- [ ] **Step 1: Write the failing CLI test**

Append to `science/tests/test_prose_lint_cli.py`:

```python
def test_lint_uses_short_form_ids_deny_from_config(tmp_path):
    root = _write_project(
        tmp_path,
        science_yaml=(
            "name: demo\n"
            "prose_lint:\n"
            "  short_form_ids_deny:\n"
            "    - 'D1'\n"
            "    - 'H3'\n"
        ),
    )
    (root / "doc" / "a.md").write_text("Cyclin D1 effect; H3 marks chromatin.\n")
    runner = CliRunner()
    result = runner.invoke(
        prose_group, ["lint", "--root", str(root), "--format", "json"]
    )
    payload = json.loads(result.output)
    assert payload["counts"].get("short-form-ids", 0) == 0
```

- [ ] **Step 2: Verify failure**

```bash
cd /mnt/ssd/Dropbox/science/science
uv run pytest tests/test_prose_lint_cli.py::test_lint_uses_short_form_ids_deny_from_config -v
```

Expected: FAIL — config field is not threaded through.

- [ ] **Step 3: Modify the CLI**

Open `science/src/science_tool/prose_lint_cli.py`. In `lint_cmd`, find the block that reads from `science.yaml`:

```python
    science_yaml = root / "science.yaml"
    if science_yaml.is_file():
        config = load_project_config(root)
        if config.prose_lint is not None:
            anchor_patterns = config.prose_lint.anchor_patterns
            enabled_from_config = config.prose_lint.enabled_checks
```

Add a `short_form_ids_deny` extraction and a fallback default. Replace with:

```python
    short_form_ids_deny: list[str] = []
    science_yaml = root / "science.yaml"
    if science_yaml.is_file():
        config = load_project_config(root)
        if config.prose_lint is not None:
            anchor_patterns = config.prose_lint.anchor_patterns
            enabled_from_config = config.prose_lint.enabled_checks
            short_form_ids_deny = config.prose_lint.short_form_ids_deny
```

Then update the `scan_root(...)` call to forward it:

```python
    result = scan_root(
        root,
        checks=selected,
        strict=strict,
        anchor_patterns=anchor_patterns,
        short_form_ids_deny=short_form_ids_deny,
    )
```

- [ ] **Step 4: Verify pass**

```bash
cd /mnt/ssd/Dropbox/science/science
uv run pytest tests/test_prose_lint_cli.py -v
uv run ruff check src/science_tool/prose_lint_cli.py
```

Expected: 7 CLI tests PASS (6 + 1 new); ruff clean.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/prose_lint_cli.py science/tests/test_prose_lint_cli.py
git commit -m "feat(prose_lint): wire short_form_ids_deny through CLI from config"
```

---

## Section C — Documentation + baselines

### Task 7: Update docs

**Files:**
- Modify: `docs/conventions/prose-lints.md`

- [ ] **Step 1: Document `short_form_ids_deny`**

Open `docs/conventions/prose-lints.md`. Find the `## Project config` section. Append `short_form_ids_deny` to the example YAML block:

```yaml
prose_lint:
  enabled_checks: [...]
  anchor_patterns: [...]
  short_form_ids_deny:
    - "D1"   # cyclin D1 — biology shorthand, not a project entity ref
    - "H3"   # histone H3
    - "T1"   # T1-weighted MRI
```

Below the YAML block, add a paragraph:

```markdown
`short_form_ids_deny` is a list of token strings (e.g., `D1`, `H3`, `t1`)
that the `short-form-ids` detector will skip. Useful for biology-heavy
projects where common shorthand collides with the canonical short-form
regex `\b([qQhHtTdDiI])(\d{1,4})\b`. See
[`docs/audits/2026-05-10-prose-lint-baselines.md`](../audits/2026-05-10-prose-lint-baselines.md)
for diagnostic guidance on whether your project actually needs a deny-list.
```

Append to the `## Tooling` section:

```markdown
## Related: `science refs check --include-body`

Where prose-lint detects authoring patterns ("you wrote a short-form ID;
canonical form is `<kind>:<id>`"), `science refs check --include-body`
detects unresolved typed refs in body prose ("you wrote `task:t999` but no
project file declares that `id:`"). The two are complementary; run both.
```

- [ ] **Step 2: Commit**

```bash
git add docs/conventions/prose-lints.md
git commit -m "docs(prose-lints): document short_form_ids_deny + refs --include-body cross-link"
```

---

### Task 8: Baseline run + audit doc

**Files:**
- Create: `docs/audits/2026-05-10-refs-body-baselines.md`

- [ ] **Step 1: Run `science refs check --include-body` against natural-systems**

```bash
cd /mnt/ssd/Dropbox/science/.claude/worktrees/<this-worktree>
uv run --project science science refs check --root /home/keith/d/natural-systems --include-body --format json --summary-only > /tmp/ns-refs-body.json 2>&1
python3 -c "
import json
d = json.load(open('/tmp/ns-refs-body.json'))
issues = d.get('issues', d.get('hits', []))
from collections import Counter
counts = Counter(i['ref_type'] for i in issues)
print('natural-systems counts by ref_type:')
for kind, c in counts.most_common():
    print(f'  {kind}: {c}')
"
```

If the JSON shape doesn't include the issues list (e.g., `--summary-only` collapsed it), drop `--summary-only` and re-run.

Record the output.

- [ ] **Step 2: Compare to natural-systems's existing `audit-citations.ts`**

```bash
cd /home/keith/d/natural-systems
npm run audit:citations 2>&1 | tail -20
```

Record the headline count from audit-citations.ts (it uses `knowledge/graph.trig` as its truth source rather than the frontmatter sweep). Note any directional difference (e.g., "audit-citations.ts found 47 unresolved entity refs; science refs check --include-body found 52 — overlap is X").

- [ ] **Step 3: Run against multiple-myeloma**

```bash
uv run --project science science refs check --root /home/keith/d/cancer/cancer-types/multiple-myeloma --include-body --format json > /tmp/mm-refs-body.json 2>&1
python3 -c "
import json
d = json.load(open('/tmp/mm-refs-body.json'))
issues = d.get('issues', d.get('hits', []))
from collections import Counter
counts = Counter(i['ref_type'] for i in issues)
print('multiple-myeloma counts by ref_type:')
for kind, c in counts.most_common():
    print(f'  {kind}: {c}')
"
```

- [ ] **Step 4: Write the audit doc**

Create `docs/audits/2026-05-10-refs-body-baselines.md`:

```markdown
---
title: "Refs body-scan baselines: natural-systems and multiple-myeloma"
date: 2026-05-10
related:
  - "docs/conventions/prose-lints.md"
  - "docs/audits/2026-05-10-prose-lint-baselines.md"
---

# Refs body-scan baselines (2026-05-10)

First-run baselines for `science refs check --include-body` against the same
two projects audited in the prose-lint baselines doc.

## Per-project totals (by ref_type)

| ref_type             | natural-systems | multiple-myeloma |
|----------------------|----------------:|-----------------:|
| (paste actual rows)  |                 |                  |

## Comparison to natural-systems's `audit-citations.ts`

(Paste the comparison from Step 2: counts, agreement, divergence, and a
one-sentence interpretation of where they diverge — typically because the
two tools use different truth sources, `knowledge/graph.trig` vs the
frontmatter `id:` sweep.)

## Observations

- (Top file offenders, like in the prose-lint audit doc.)
- (Whether the new check finds anything the existing checks didn't.)

## Migration note

Once `science refs check --include-body` reaches feature parity with
`audit-citations.ts`, natural-systems can retire its custom TS script in
favor of the shared tool. Open question: whether the frontmatter-`id:`
sweep matches the breadth of the `knowledge/graph.trig` index in practice.
```

Fill in the placeholder rows from your captured data.

- [ ] **Step 5: Commit**

```bash
git add docs/audits/2026-05-10-refs-body-baselines.md
git commit -m "docs(audits): capture refs --include-body baselines for ns and mm"
```

---

## Out Of Scope For This Plan

- **Migration of natural-systems off `audit-citations.ts`.** Once the audit doc shows feature parity, that script can be retired in a follow-up.
- **Section 6 (Citation integrity) consolidation in `validate.sh`.** The new `--include-body` does richer body bib-key validation than Section 6's bash grep, but consolidating is a separate refactor with its own managed-artifact bump.
- **Auto-fix or auto-suggest mode** for either feature.
- **Smart deny-list inference** — e.g., scanning `papers/references.bib` to learn that "H3K27me3" is a real biological term. Cleaner to keep the deny-list explicit and project-controlled.
- **Tightening the short-form regex itself** — e.g., requiring leading-zero (`q01` not `q1`) for canonical Science short forms. The deny-list is the lighter-touch alternative; regex changes carry breakage risk.

## Self-Review Notes

- Section A is ~3 tasks (entity-index loader, scanner, CLI wiring). Section B is ~3 tasks (config, detector+orchestrator, CLI). Plus 2 doc/baseline tasks.
- All new code mirrors existing patterns (loaders structured like `_load_task_ids`, body scanners structured like the existing per-line scanners in `check_refs`, deny-list threading mirrors how `anchor_patterns` is already threaded).
- The CLI test approach mirrors `test_prose_lint_cli.py` — Click runner with JSON output assertions.
- Deny-list is a list-of-strings (exact match), not regexes. If projects want regex matching they can submit that as a follow-up; YAGNI for now.
- `_TYPED_ENTITY_REF_RE` uses length-descending kind alternation to avoid `data-package` being shadowed by `data` (no `data` kind exists, but the principle generalizes).
- The `body-entity-ref` ref_type is new but follows the existing naming convention (other types are `task`, `hypothesis`, `citation`, `link`, `doi`, `pmid`, `namespace`, `legacy-cross-project`).

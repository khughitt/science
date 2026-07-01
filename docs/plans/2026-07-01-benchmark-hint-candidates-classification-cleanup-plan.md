# Benchmark Hint Candidates Classification Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Clean up `science benchmark hint-candidates` so default review files use the canonical project doc directory and term categories stop presenting project shorthand and generic prose as domain-candidate terms.

**Architecture:** Keep `gaps_report(..., evidence_report=True)` as the source of truth. Add small deterministic classification inputs before `_term_categories()` projects evidence terms, and use `resolve_paths(project_root).doc_dir` for default review artifact paths.

**Tech Stack:** Python, Click, PyYAML, pytest, ruff, existing `science_tool.benchmark_opportunities`, `science_tool.cli`, and `science_tool.paths`.

---

## Files

- Modify: `science/src/science_tool/benchmark_opportunities.py`
  - Add project identity token loading from `science.yaml` `name` and `id`.
  - Split entity id-stems into project-local tokens.
  - Route a small generic prose set into `workflow-or-modeling`.
- Modify: `science/src/science_tool/cli.py`
  - Change default hint-candidate review path to use `resolve_paths(project_root).doc_dir`.
- Modify: `science/tests/test_benchmark_opportunities.py`
  - Add report-level category regression tests.
- Modify: `science/tests/test_benchmark_cli.py`
  - Add default review path tests for canonical `doc/`.
- Optional operator cleanup after implementation: remove old untracked generated files in active projects only if still untracked.

---

### Task 1: Classification Cleanup

**Files:**
- Modify: `science/src/science_tool/benchmark_opportunities.py`
- Test: `science/tests/test_benchmark_opportunities.py`

- [ ] **Step 1: Add failing report-level tests**

Append these tests after the existing hint-candidate report tests in `science/tests/test_benchmark_opportunities.py`.

```python
def test_hint_candidates_report_routes_generic_terms_to_workflow_category(tmp_path: Path) -> None:
    from science_tool.benchmark_opportunities import benchmark_hint_candidates_report

    _write_entity(
        tmp_path,
        "hypotheses",
        "0001-generic-prose",
        """
id: hypothesis:0001-generic-prose
type: hypothesis
title: Generic prose
""",
        body="All our organizing conjecture goes beyond shared structure.",
    )

    payload = benchmark_hint_candidates_report(tmp_path)
    by_term = {row["term"]: row for row in payload["hint_candidates"]}

    assert "conjecture" in by_term
    assert "organizing" in by_term
    for term in {"all", "beyond", "conjecture", "organizing", "our", "shared"} & set(by_term):
        assert by_term[term]["category"] == "workflow-or-modeling"

    domain_terms = {row["term"] for row in payload["hint_candidates"] if row["category"] == "domain-candidate"}
    assert "beyond" not in domain_terms
    assert "conjecture" not in domain_terms
    assert "organizing" not in domain_terms
    assert "our" not in domain_terms
    assert "shared" not in domain_terms
```

```python
def test_hint_candidates_report_classifies_project_identity_from_science_yaml(tmp_path: Path) -> None:
    from science_tool.benchmark_opportunities import benchmark_hint_candidates_report

    (tmp_path / "science.yaml").write_text(
        "name: mm30\nid: multiple-myeloma\nprofile: research\n",
        encoding="utf-8",
    )
    _write_entity(
        tmp_path,
        "hypotheses",
        "0001-mm30-signal",
        """
id: hypothesis:0001-mm30-signal
type: hypothesis
title: MM30 signal
""",
        body="MM30 multiple myeloma expression signal.",
    )

    payload = benchmark_hint_candidates_report(tmp_path)
    rows = {row["term"]: row for row in payload["hint_candidates"]}

    assert rows["mm30"]["category"] == "project-local"
    assert rows["multiple"]["category"] == "project-local"
    assert rows["myeloma"]["category"] == "project-local"
```

```python
def test_hint_candidates_report_classifies_split_entity_id_stems_as_project_local(tmp_path: Path) -> None:
    from science_tool.benchmark_opportunities import benchmark_hint_candidates_report

    _write_entity(
        tmp_path,
        "propositions",
        "0014-pais-small-fiber-structural-lesion",
        """
id: proposition:0014-pais-small-fiber-structural-lesion
type: proposition
title: PAIS small fiber lesion
""",
        body="PAIS small fiber lesion.",
    )

    payload = benchmark_hint_candidates_report(tmp_path)
    rows = {row["term"]: row for row in payload["hint_candidates"]}

    assert rows["pais"]["category"] == "project-local"
    assert rows["small"]["category"] == "project-local"
    assert rows["fiber"]["category"] == "project-local"
```

```python
def test_hint_candidates_report_missing_science_yaml_keeps_existing_project_local_sources(tmp_path: Path) -> None:
    from science_tool.benchmark_opportunities import benchmark_hint_candidates_report

    project_root = tmp_path / "project-alpha"
    project_root.mkdir()
    _write_entity(
        project_root,
        "questions",
        "0001-project-alpha-check",
        """
id: question:0001-project-alpha-check
type: question
title: Project alpha check
""",
        body="Project alpha signal.",
    )

    payload = benchmark_hint_candidates_report(project_root)
    rows = {row["term"]: row for row in payload["hint_candidates"]}

    assert rows["project"]["category"] == "project-local"
    assert rows["alpha"]["category"] == "project-local"
```

These fixtures intentionally mirror the existing `_write_entity()` usage: plural entity directories, YAML mapping frontmatter, and candidate terms in the entity body. Invalid YAML frontmatter or singular directories will cause the loader to skip the entity and make the red/green gate meaningless.

Expected current result: at least the `mm30`, `multiple`/`myeloma`, `pais`, and generic-term assertions fail because `science.yaml` identity tokens are not loaded, entity id-stems are not split, and the generic terms are not routed through `_WORKFLOW_OR_MODELING_TERMS`.

- [ ] **Step 2: Run the failing tests**

```bash
rtk uv run --frozen --project science pytest \
  science/tests/test_benchmark_opportunities.py::test_hint_candidates_report_routes_generic_terms_to_workflow_category \
  science/tests/test_benchmark_opportunities.py::test_hint_candidates_report_classifies_project_identity_from_science_yaml \
  science/tests/test_benchmark_opportunities.py::test_hint_candidates_report_classifies_split_entity_id_stems_as_project_local \
  science/tests/test_benchmark_opportunities.py::test_hint_candidates_report_missing_science_yaml_keeps_existing_project_local_sources \
  -q
```

Expected: FAIL.

- [ ] **Step 3: Implement project identity and generic classification**

In `science/src/science_tool/benchmark_opportunities.py`, add `import yaml` near the existing imports if it is not already present.

Add these helpers near `_tokens_from_label()`:

```python
def _project_identity_tokens(project_root: Path) -> set[str]:
    manifest_path = project_root / "science.yaml"
    if not manifest_path.is_file():
        return set()
    data = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, Mapping):
        return set()
    tokens: set[str] = set()
    for key in ("name", "id"):
        value = data.get(key)
        if isinstance(value, str):
            tokens.update(_tokens_from_label(value))
    return tokens
```

Add this helper near `_entity_id_only_tokens()`:

```python
def _entity_id_stem_tokens(entity_id: str) -> set[str]:
    local = entity_id.split(":", 1)[1] if ":" in entity_id else entity_id
    without_prefix = re.sub(r"^\d+-", "", local)
    return _tokens_from_label(without_prefix)
```

Extend `_WORKFLOW_OR_MODELING_TERMS`:

```python
_WORKFLOW_OR_MODELING_TERMS = frozenset(
    {
        "all",
        "beyond",
        "catalog",
        "conjecture",
        "model",
        "models",
        "organizing",
        "our",
        "project",
        "shared",
    }
)
```

Update `_project_local_tokens()` so it includes identity tokens and split id-stem tokens:

```python
def _project_local_tokens(project_root: Path, entities: list[ProjectBenchmarkEntity]) -> set[str]:
    tokens: set[str] = set()
    tokens.update(_tokens_from_label(project_root.resolve().name))
    tokens.update(_project_identity_tokens(project_root))
    for entity in entities:
        tokens.update(_entity_id_only_tokens(entity.id, entity.kind))
        tokens.update(_entity_id_stem_tokens(entity.id))
    return tokens
```

Do not add `science.yaml` `tags` to the token source.

- [ ] **Step 4: Run the focused classification tests**

```bash
rtk uv run --frozen --project science pytest \
  science/tests/test_benchmark_opportunities.py::test_hint_candidates_report_routes_generic_terms_to_workflow_category \
  science/tests/test_benchmark_opportunities.py::test_hint_candidates_report_classifies_project_identity_from_science_yaml \
  science/tests/test_benchmark_opportunities.py::test_hint_candidates_report_classifies_split_entity_id_stems_as_project_local \
  science/tests/test_benchmark_opportunities.py::test_hint_candidates_report_missing_science_yaml_keeps_existing_project_local_sources \
  -q
```

Expected: PASS.

- [ ] **Step 5: Run existing hint-candidate report tests**

```bash
rtk uv run --frozen --project science pytest science/tests/test_benchmark_opportunities.py -k hint_candidates -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
rtk git add science/src/science_tool/benchmark_opportunities.py science/tests/test_benchmark_opportunities.py
rtk git commit -m "fix(benchmark): clean up hint candidate categories"
```

---

### Task 2: Canonical Review Artifact Path

**Files:**
- Modify: `science/src/science_tool/cli.py`
- Test: `science/tests/test_benchmark_cli.py`

- [ ] **Step 1: Add failing CLI path tests**

Update `test_benchmark_hint_candidates_cli_writes_default_review_file()` in `science/tests/test_benchmark_cli.py` so the expected review path uses `doc/`, not `docs/`:

```python
review_path = tmp_path / "doc" / "audits" / "benchmark-hint-candidates" / f"2026-06-30-{tmp_path.name}.yaml"
```

Add these new tests after it:

```python
def test_benchmark_hint_candidates_cli_default_review_file_always_uses_canonical_doc_dir(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr("science_tool.cli._benchmark_hint_candidates_today", lambda: date(2026, 6, 30))
    (tmp_path / "doc").mkdir()
    (tmp_path / "docs").mkdir()
    _write_entity(
        tmp_path,
        "hypotheses",
        "0074-alpha",
        """
id: hypothesis:0074-alpha
type: hypothesis
title: Cytogenetic benchmark gap
""",
        body="Cytogenetic lesion mutation evidence should be reviewed.",
    )

    result = _invoke_hint_candidates(tmp_path, "--write-review-file", "--format", "json")

    assert result.exit_code == 0, result.output
    review_path = tmp_path / "doc" / "audits" / "benchmark-hint-candidates" / f"2026-06-30-{tmp_path.name}.yaml"
    wrong_path = tmp_path / "docs" / "audits" / "benchmark-hint-candidates" / f"2026-06-30-{tmp_path.name}.yaml"
    payload = json.loads(result.output)
    assert payload["review_file"] == str(review_path)
    assert review_path.exists()
    assert not wrong_path.exists()
    assert f"wrote benchmark hint candidate review file: {review_path}" in result.stderr
```

```python
def test_benchmark_hint_candidates_cli_default_review_file_creates_doc_for_docs_only_project(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr("science_tool.cli._benchmark_hint_candidates_today", lambda: date(2026, 6, 30))
    (tmp_path / "docs").mkdir()
    _write_entity(
        tmp_path,
        "hypotheses",
        "0075-beta",
        """
id: hypothesis:0075-beta
type: hypothesis
title: Cytogenetic benchmark gap
""",
        body="Cytogenetic lesion mutation evidence should be reviewed.",
    )

    result = _invoke_hint_candidates(tmp_path, "--write-review-file", "--format", "json")

    assert result.exit_code == 0, result.output
    review_path = tmp_path / "doc" / "audits" / "benchmark-hint-candidates" / f"2026-06-30-{tmp_path.name}.yaml"
    wrong_path = tmp_path / "docs" / "audits" / "benchmark-hint-candidates" / f"2026-06-30-{tmp_path.name}.yaml"
    payload = json.loads(result.output)
    assert payload["review_file"] == str(review_path)
    assert review_path.exists()
    assert not wrong_path.exists()
    assert f"wrote benchmark hint candidate review file: {review_path}" in result.stderr
```

Expected current result: FAIL because `_default_hint_candidates_review_path()` hardcodes `docs/`.

- [ ] **Step 2: Run the failing CLI tests**

```bash
rtk uv run --frozen --project science pytest \
  science/tests/test_benchmark_cli.py::test_benchmark_hint_candidates_cli_writes_default_review_file \
  science/tests/test_benchmark_cli.py::test_benchmark_hint_candidates_cli_default_review_file_always_uses_canonical_doc_dir \
  science/tests/test_benchmark_cli.py::test_benchmark_hint_candidates_cli_default_review_file_creates_doc_for_docs_only_project \
  -q
```

Expected: FAIL.

- [ ] **Step 3: Implement canonical doc_dir path**

In `science/src/science_tool/cli.py`, update `_default_hint_candidates_review_path()` to use `resolve_paths()`:

```python
def _default_hint_candidates_review_path(project_root: Path, generated: date) -> Path:
    from science_tool.paths import resolve_paths

    doc_dir = resolve_paths(project_root).doc_dir
    return (
        doc_dir
        / "audits"
        / "benchmark-hint-candidates"
        / f"{generated.isoformat()}-{project_root.name}.yaml"
    )
```

Keep `_resolve_hint_candidates_output_path()` unchanged for explicit `--output`; custom paths remain relative to project root and must stay under it.

This intentionally makes default review-file creation subject to the same `science.yaml` validation that `resolve_paths()` applies elsewhere. A malformed manifest or unsupported profile should fail early rather than silently writing to a fallback path.

- [ ] **Step 4: Run the focused CLI tests**

```bash
rtk uv run --frozen --project science pytest \
  science/tests/test_benchmark_cli.py::test_benchmark_hint_candidates_cli_writes_default_review_file \
  science/tests/test_benchmark_cli.py::test_benchmark_hint_candidates_cli_default_review_file_always_uses_canonical_doc_dir \
  science/tests/test_benchmark_cli.py::test_benchmark_hint_candidates_cli_default_review_file_creates_doc_for_docs_only_project \
  science/tests/test_benchmark_cli.py::test_benchmark_hint_candidates_cli_rejects_relative_output_outside_project_root \
  science/tests/test_benchmark_cli.py::test_benchmark_hint_candidates_cli_rejects_absolute_output_outside_project_root \
  -q
```

Expected: PASS.

- [ ] **Step 5: Run all hint-candidate CLI tests**

```bash
rtk uv run --frozen --project science pytest science/tests/test_benchmark_cli.py -k hint_candidates -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
rtk git add science/src/science_tool/cli.py science/tests/test_benchmark_cli.py
rtk git commit -m "fix(benchmark): use canonical doc path for hint reviews"
```

---

### Task 3: Verification and Real-Project Smoke

**Files:**
- No code changes expected.
- Optional operator cleanup outside this repo for old exploratory files, only if still untracked.

- [ ] **Step 1: Run focused tests**

```bash
rtk uv run --frozen --project science pytest science/tests/test_benchmark_opportunities.py science/tests/test_benchmark_cli.py -q
```

Expected: PASS.

- [ ] **Step 2: Run ruff**

```bash
rtk uv run --frozen --project science ruff check science/src/science_tool/benchmark_opportunities.py science/src/science_tool/cli.py science/tests/test_benchmark_opportunities.py science/tests/test_benchmark_cli.py
```

Expected: PASS with `All checks passed!`.

- [ ] **Step 3: Run read-only active-project smoke commands**

```bash
rtk uv run --frozen --project science science benchmark hint-candidates --commons --domain biology --project-root ~/d/cancer/cancer-types/multiple-myeloma --format json
rtk uv run --frozen --project science science benchmark hint-candidates --commons --domain biology --project-root ~/d/health/processes/post-acute-infection --format json
rtk uv run --frozen --project science science benchmark hint-candidates --commons --domain biology --project-root ~/d/natural-systems --format json
rtk uv run --frozen --project science science benchmark hint-candidates --commons --domain biology --project-root ~/d/cancer/data-sources/cbioportal --format json
```

Expected:
- commands exit 0;
- `review_file` is `null`;
- `mm30` is not a `domain-candidate` for multiple myeloma;
- `pais` is not a `domain-candidate` for post-acute infection if it appears in split entity id-stems;
- generic terms such as `our`, `all`, `beyond`, `conjecture`, `organizing`, and `shared` are not `domain-candidate` rows.

- [ ] **Step 4: Optional one-off cleanup of old exploratory artifacts**

Check whether the old generated files are still untracked:

```bash
rtk git -C ~/d/cancer/cancer-types/multiple-myeloma status --short --untracked-files=all
rtk git -C ~/d/cancer/data-sources/cbioportal status --short --untracked-files=all
```

If the only matching files are still these generated reports:

```text
docs/audits/benchmark-hint-candidates/2026-06-30-multiple-myeloma.yaml
docs/audits/benchmark-hint-candidates/2026-06-30-cbioportal.yaml
```

then ask before deleting them, because this is a destructive filesystem cleanup outside the science repo. Do not touch unrelated project changes.

- [ ] **Step 5: Final status check**

```bash
rtk git status --short
```

Expected: only unrelated pre-existing files may remain dirty. The benchmark code/test paths touched by this plan should be clean after commits.

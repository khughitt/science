# Validation Sidecar Retirement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop `science validate` from importing and executing project-authored `validate_local.py`, promote the one reusable project check into the canonical check set, and migrate all four consumer repositories atomically.

**Architecture:** The `hook` API and Python-sidecar import are deleted outright from `validate/runner.py`; a new `validate.python-sidecar-removed` rule on the existing `VALIDATION_RUNTIME_PRODUCER` reports a stale sidecar file as a structured ERROR instead of crashing. The `reviews-are-not-evidence` policy — currently duplicated in two projects and scanning a directory the papers left — becomes three WARN rules on the existing `validate.papers` producer, with roots resolved through `resolve_path_policy`. Consumer repositories then update their toolkit pin, delete their sidecar, and fix their docs in one commit each.

**Tech Stack:** Python 3.13, Pydantic v2, click, pytest, uv. Findings model in `science-model` (`science_model.audit`); validation in `science_tool.validate`.

**Design doc:** [`2026-07-29-validation-sidecar-retirement-design.md`](2026-07-29-validation-sidecar-retirement-design.md)

## Global Constraints

- **No compatibility layer.** No shim for `hook`, no deprecation wrapper, no re-export. Deliberate breaking change.
- **Run from the package directory.** `cd science` before any `uv run`. There is no root `pyproject.toml`.
- **Test commands:** `cd science && uv run --frozen pytest`. Default runs exclude `snapshot` and `real_projects` markers; opt in with `-m snapshot` / `-m real_projects`.
- **Full suite is ~10k tests / 2-3 min** — longer than the default 120s timeout. Run scoped selections per task; reserve the full run for Task 7 with an explicit long timeout.
- **Never run two suites concurrently in the same worktree** — they race on shared test-output paths.
- **Lint/types from `science/`:** `uv run ruff check` and `uv run pyright`. Pyright is configured once by the repo-root `pyrightconfig.json`; test directories are not type-checked.
- **Conventional commits.** No AI-attribution trailers on commits, PRs, or comments.
- **Privacy:** use `~/d/` in docs and code, never `/home/keith/` or `/mnt/ssd/Dropbox/`.
- **Working branch:** `sidecar-retirement`, worktree `.worktrees/sidecar-retirement/`.
- **Baselines are captured in Task 1, before any code change.** Tasks 4–5 delete the very mechanism (`enable_python_sidecar`, the env-var branch) that a with-sidecars-disabled baseline needs. Capturing later is impossible.

---

## File Structure

**Toolkit — created:**
- `science/tests/validate/test_checks_papers_background_reviews.py` — all promoted-check coverage
- `science/tests/validate/test_sidecar_retirement.py` — retirement rule + non-execution coverage

**Toolkit — modified:**
- `science/src/science_tool/validate/checks/papers.py` — three new rules + two check arms
- `science/src/science_tool/validate/runtime.py` — `RULE_PYTHON_SIDECAR_REMOVED`
- `science/src/science_tool/validate/runner.py` — delete hook API and sidecar import; drop `enable_python_sidecar`
- `science/src/science_tool/validate/__init__.py` — drop `hook` export
- `science/src/science_tool/validate/context.py` — drop three stale `doc/`-rooted fields
- `science/src/science_tool/graph/health_checks/validate.py` — drop `enable_python_sidecar=False`
- `science/src/science_tool/project_artifacts/registry.yaml` — drop `extension_protocol`, bump version
- `science/src/science_tool/project_artifacts/cli.py` — drop the porting command
- `science/src/science_tool/budget/registry.py` — drop the porting command's entry
- `science/tests/validate/test_context.py:24-26` — drop assertions on deleted fields
- `docs/conventions/validate.md`, `docs/migration/*.md`
- `skills/generated/science-command-preamble/references/docs/conventions/validate.md` — regenerated, never hand-edited

**Toolkit — deleted:**
- `science/src/science_tool/project_artifacts/port_validate_sidecar.py` and its tests

**Consumers — deleted:** `validate_local.py` in `~/d/health/meta`, `~/d/cancer/mechanisms/evolution`, `~/d/protein-landscape`, `~/d/science/meta`

---

### Task 1: Capture all baselines before any change

**Files:**
- Create: `~/scratch/sidecar-baselines/` (outside all repos — never commit baselines)

**Interfaces:**
- Produces: four baseline JSON files that Task 7 diffs against.

Per design §5.1 the four projects are in three different states. Health/meta pins the toolkit at pre–Plan 2 `3b72db60` and runs clean; the other three are locked at post–Plan 2 `ed6b50dc` (or editable) and crash.

- [ ] **Step 1: Create the baseline directory**

```bash
mkdir -p ~/scratch/sidecar-baselines
```

- [ ] **Step 2: Capture health/meta's real baseline — its sidecar executes**

```bash
cd ~/d/health/meta
.venv/bin/science validate --format json > ~/scratch/sidecar-baselines/health-meta.json
echo "exit=$?"
```

Expected: `exit=0`, valid JSON, `summary.warnings == 153`, `summary.infos == 0`.

This is the only project whose baseline includes sidecar execution. Note that it contains **zero** rows from the guardrail — `doc/papers/` holds only an `archive/` subdirectory, so the check found an empty background set and reported a pass as an INFO that never reached the summary.

- [ ] **Step 3: Confirm the other three crash, and record the traceback**

```bash
for p in ~/d/cancer/mechanisms/evolution ~/d/protein-landscape ~/d/science/meta; do
  echo "=== $p ==="
  (cd "$p" && uv run --frozen science validate --format json 2>&1 | tail -5)
done > ~/scratch/sidecar-baselines/crashes.txt 2>&1
cat ~/scratch/sidecar-baselines/crashes.txt
```

Expected: each ends with `TypeError: Result.__init__() missing 1 required positional argument: 'qualifiers'`.

- [ ] **Step 4: Capture canonical-validator baselines for the three crashing projects**

The sidecar-disabling env var still exists at this point. This is the last moment it can be used.

```bash
for p in ~/d/cancer/mechanisms/evolution ~/d/protein-landscape ~/d/science/meta; do
  name=$(basename "$p")
  (cd "$p" && SCIENCE_VALIDATE_DISABLE_SIDECAR=1 uv run --frozen science validate --format json) \
    > ~/scratch/sidecar-baselines/"$name"-canonical.json
  echo "$name exit=$?"
done
```

Expected: each exits 0 with valid JSON.

- [ ] **Step 5: Capture health/meta's canonical baseline too**

```bash
cd ~/d/health/meta
SCIENCE_VALIDATE_DISABLE_SIDECAR=1 .venv/bin/science validate --format json \
  > ~/scratch/sidecar-baselines/health-meta-canonical.json
```

- [ ] **Step 6: Verify all five files parse**

```bash
for f in ~/scratch/sidecar-baselines/*.json; do
  python3 -c "import json,sys; d=json.load(open('$f')); print('$f', d['summary'])"
done
```

Expected: five lines, each printing a summary dict. No commit — baselines live outside the repos.

---

### Task 2: Declare the three background-review rules and implement the evidence-ref arm

**Files:**
- Modify: `science/src/science_tool/validate/checks/papers.py`
- Test: `science/tests/validate/test_checks_papers_background_reviews.py`

**Interfaces:**
- Consumes: `declare_validation_rules` from `science_tool.validate.findings`; `resolve_path_policy` from `science_tool.entities`; `Check` from `science_tool.validate.checks`.
- Produces: `BACKGROUND_REVIEW_RULES: dict[str, FindingRule]` keyed by the three rule ids; `check_background_reviews(ctx) -> Iterator[CheckObservation]`.

- [ ] **Step 1: Write the failing test**

```python
"""Promoted reviews-are-not-evidence guardrail."""

from __future__ import annotations

from pathlib import Path

from science_tool.validate.checks.papers import (
    RULE_EVIDENCE_REF,
    check_background_reviews,
)
from science_tool.validate.context import ValidateContext
from science_tool.validate.observations import ValidationNotice
from science_tool.validate.result import Result


def _paper(root: Path, key: str, status: str) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / f"{key}.md").write_text(
        f"---\nkind: paper\ntitle: {key}\nstatus: {status}\n---\n",
        encoding="utf-8",
    )


def _ctx(tmp_path: Path) -> ValidateContext:
    return ValidateContext.from_project_root(
        tmp_path, strict=False, verbose=False, include_all_checks=False
    )


def test_background_paper_in_evidence_refs_warns(tmp_path: Path) -> None:
    _paper(tmp_path / "entities" / "papers", "Tasci2022", "background")
    hyp = tmp_path / "entities" / "hypotheses"
    hyp.mkdir(parents=True)
    (hyp / "0001-h.md").write_text(
        "---\nkind: hypothesis\nevidence_refs:\n- paper:Tasci2022\n---\n",
        encoding="utf-8",
    )

    issues = [o for o in check_background_reviews(_ctx(tmp_path)) if isinstance(o, Result)]

    assert len(issues) == 1
    assert issues[0].rule is RULE_EVIDENCE_REF
    assert issues[0].qualifiers["paper_ref"] == "Tasci2022"


def test_active_paper_in_evidence_refs_is_silent(tmp_path: Path) -> None:
    _paper(tmp_path / "entities" / "papers", "Smith2024", "active")
    hyp = tmp_path / "entities" / "hypotheses"
    hyp.mkdir(parents=True)
    (hyp / "0001-h.md").write_text(
        "---\nkind: hypothesis\nevidence_refs:\n- paper:Smith2024\n---\n",
        encoding="utf-8",
    )

    issues = [o for o in check_background_reviews(_ctx(tmp_path)) if isinstance(o, Result)]

    assert issues == []


def test_source_refs_are_not_evidence_refs(tmp_path: Path) -> None:
    """The health/meta corpus cites background papers under source_refs."""
    _paper(tmp_path / "entities" / "papers", "Tasci2022", "background")
    themes = tmp_path / "entities" / "themes"
    themes.mkdir(parents=True)
    (themes / "0007-t.md").write_text(
        "---\nkind: theme\nsource_refs:\n- paper:Tasci2022\n"
        "evidence_refs:\n- report:0012-x\n---\n",
        encoding="utf-8",
    )

    issues = [o for o in check_background_reviews(_ctx(tmp_path)) if isinstance(o, Result)]

    assert issues == []


def test_duplicate_citation_across_blocks_dedupes_file_wide(tmp_path: Path) -> None:
    """Identity is (rule, path, paper_ref); a per-block seen set would collide."""
    _paper(tmp_path / "entities" / "papers", "Tasci2022", "background")
    hyp = tmp_path / "entities" / "hypotheses"
    hyp.mkdir(parents=True)
    (hyp / "0001-h.md").write_text(
        "---\nkind: hypothesis\nevidence_refs:\n- paper:Tasci2022\n---\n"
        "\n## Later\n\nevidence_refs:\n- paper:Tasci2022\n",
        encoding="utf-8",
    )

    issues = [o for o in check_background_reviews(_ctx(tmp_path)) if isinstance(o, Result)]

    assert len(issues) == 1


def test_no_background_papers_emits_notice(tmp_path: Path) -> None:
    _paper(tmp_path / "entities" / "papers", "Smith2024", "active")

    observations = list(check_background_reviews(_ctx(tmp_path)))

    assert all(isinstance(o, ValidationNotice) for o in observations)
    assert any("no status:background" in o.message for o in observations)
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd science && uv run --frozen pytest tests/validate/test_checks_papers_background_reviews.py -v
```

Expected: FAIL — `ImportError: cannot import name 'RULE_EVIDENCE_REF'`.

- [ ] **Step 3: Declare the qualifier schema and three rules**

Append to `science/src/science_tool/validate/checks/papers.py`:

```python
class BackgroundReviewQualifiers(BaseModel):
    model_config = ConfigDict(extra="forbid")
    paper_ref: str
    task: str | None = None


BACKGROUND_SECTION, BACKGROUND_REVIEW_RULES = declare_validation_rules(
    section_id="papers-background-reviews",
    section_title="background reviews are not evidence",
    section_order=111,
    rule_ids=(
        "papers.background-review-evidence-ref",
        "papers.background-review-source-typing",
        "papers.background-review-evidence-tier",
    ),
    severities=frozenset({"warn"}),
    subject_types=frozenset({"path"}),
    qualifier_schema=BackgroundReviewQualifiers,
    identity_qualifiers=("paper_ref",),
)

RULE_EVIDENCE_REF = BACKGROUND_REVIEW_RULES["papers.background-review-evidence-ref"]
RULE_SOURCE_TYPING = BACKGROUND_REVIEW_RULES["papers.background-review-source-typing"]
RULE_EVIDENCE_TIER = BACKGROUND_REVIEW_RULES["papers.background-review-evidence-tier"]
```

Add to the imports at the top of the file:

```python
import re

from pydantic import BaseModel, ConfigDict

from science_tool.validate.findings import declare_validation_rules, validation_observation
```

Three separate rules, not one discriminated by qualifier: a single provenance record can violate both typing conditions at once, and a shared rule id would collide on identity.

- [ ] **Step 4: Implement the background-paper set and the evidence-ref arm**

```python
_REF_RE = re.compile(r"(?:paper|cite):([A-Za-z0-9_]+)")
_EVIDENCE_REFS_RE = re.compile(r"(?m)^evidence_refs:\s*\n((?:[ \t]+-.*(?:\n|$))+)")


def _background_papers(ctx: ValidateContext) -> set[str]:
    papers_root = ctx.project_root / resolve_path_policy("paper").root
    if not papers_root.is_dir():
        return set()
    return {
        path.stem
        for path in sorted(papers_root.glob("*.md"))
        if ctx.frontmatter(path).get("status") == "background"
    }


def _citation_roots(ctx: ValidateContext) -> tuple[Path, ...]:
    return tuple(
        ctx.project_root / resolve_path_policy(kind).root
        for kind in ("theme", "report", "hypothesis")
    )


@Check(
    section=BACKGROUND_SECTION,
    order=8,
    producer_id="validate.papers-background-reviews",
    rules=tuple(BACKGROUND_REVIEW_RULES.values()),
)
def check_background_reviews(ctx: ValidateContext) -> Iterator[object]:
    background = _background_papers(ctx)
    if not background:
        yield ValidationNotice(
            path=None,
            line=None,
            message="no status:background papers; reviews-are-not-evidence checks pass",
        )
        return

    violations = 0
    for root in _citation_roots(ctx):
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.md")):
            text = ctx.read_text_cached(path)
            # Dedupe per (path, paper_ref) across the WHOLE file, not per block:
            # finding identity is (rule, path, paper_ref), so two blocks citing the
            # same paper would emit two identical identities and the producer
            # boundary would reject them.
            seen: set[str] = set()
            for block in _EVIDENCE_REFS_RE.findall(text):
                for match in _REF_RE.finditer(block):
                    key = match.group(1)
                    if key not in background or key in seen:
                        continue
                    seen.add(key)
                    violations += 1
                    yield validation_observation(
                        severity=Severity.WARN,
                        path=path,
                        line=None,
                        message=(
                            f"evidence_refs cites paper:{key} (status:background); "
                            "use a primary citation or synthesis report instead of "
                            "the review directly"
                        ),
                        rule=RULE_EVIDENCE_REF,
                        task=None,
                        qualifiers={"paper_ref": key},
                    )

    yield ValidationNotice(
        path=None,
        line=None,
        message=(
            f"{len(background)} status:background paper(s); "
            f"{violations} reviews-are-not-evidence violation(s)"
        ),
    )
```

Note `resolve_path_policy(...).root` is project-relative — join it to `ctx.project_root`. Reports live **flat** under the `report` root; there is no `synthesis/` subdirectory in either live project, which is why `rglob` walks the root itself.

- [ ] **Step 5: Run the tests to verify they pass**

```bash
cd science && uv run --frozen pytest tests/validate/test_checks_papers_background_reviews.py -v
```

Expected: 5 passed.

- [ ] **Step 6: Lint and typecheck**

```bash
cd science && uv run ruff check && uv run pyright
```

Expected: both clean.

- [ ] **Step 7: Commit**

```bash
git add science/src/science_tool/validate/checks/papers.py \
        science/tests/validate/test_checks_papers_background_reviews.py
git commit -m "feat(validate): promote the reviews-are-not-evidence evidence-ref arm"
```

---

### Task 3: Implement the provenance typing arm

**Files:**
- Modify: `science/src/science_tool/validate/checks/papers.py`
- Test: `science/tests/validate/test_checks_papers_background_reviews.py`

**Interfaces:**
- Consumes: `RULE_SOURCE_TYPING`, `RULE_EVIDENCE_TIER`, `_background_papers` from Task 2.
- Produces: nothing new; extends `check_background_reviews`.

This is the arm health/meta has and evolution lacks. Its root is `ctx.doc_dir / "provenance"` — the one deliberately non-entity root, because there is no canonical `entities/provenance` kind.

- [ ] **Step 1: Write the failing test**

Append to `science/tests/validate/test_checks_papers_background_reviews.py`:

```python
from science_tool.validate.checks.papers import RULE_EVIDENCE_TIER, RULE_SOURCE_TYPING


def _provenance(root: Path, name: str, body: str) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / f"{name}.yaml").write_text(body, encoding="utf-8")


def test_compliant_provenance_record_is_silent(tmp_path: Path) -> None:
    """Both health/meta Tasci2022 records are already correctly typed."""
    _paper(tmp_path / "entities" / "papers", "Tasci2022", "background")
    _provenance(
        tmp_path / "doc" / "provenance",
        "tasci",
        "source_ref: paper:Tasci2022\nevidence_tier: background\nreview_typed_source: true\n",
    )

    issues = [o for o in check_background_reviews(_ctx(tmp_path)) if isinstance(o, Result)]

    assert issues == []


def test_provenance_record_violating_both_conditions_yields_two_findings(
    tmp_path: Path,
) -> None:
    """Separate rules exist precisely so these two do not collide on identity."""
    _paper(tmp_path / "entities" / "papers", "Tasci2022", "background")
    _provenance(
        tmp_path / "doc" / "provenance",
        "tasci",
        "source_ref: paper:Tasci2022\nevidence_tier: primary\nreview_typed_source: false\n",
    )

    issues = [o for o in check_background_reviews(_ctx(tmp_path)) if isinstance(o, Result)]

    assert len(issues) == 2
    assert {i.rule for i in issues} == {RULE_SOURCE_TYPING, RULE_EVIDENCE_TIER}
    assert {i.qualifiers["paper_ref"] for i in issues} == {"Tasci2022"}


def test_provenance_for_active_paper_is_silent(tmp_path: Path) -> None:
    _paper(tmp_path / "entities" / "papers", "Smith2024", "active")
    _provenance(
        tmp_path / "doc" / "provenance",
        "smith",
        "source_ref: paper:Smith2024\nevidence_tier: primary\n",
    )

    issues = [o for o in check_background_reviews(_ctx(tmp_path)) if isinstance(o, Result)]

    assert issues == []
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd science && uv run --frozen pytest tests/validate/test_checks_papers_background_reviews.py -k provenance -v
```

Expected: FAIL — `ImportError: cannot import name 'RULE_SOURCE_TYPING'` is already resolved by Task 2, so expect assertion failures (`assert 0 == 2`).

- [ ] **Step 3: Implement the provenance arm**

Add to `papers.py`:

```python
_SOURCE_REF_RE = re.compile(r"^source_ref:\s*([^\s#]+)", re.MULTILINE)
_EVIDENCE_TIER_RE = re.compile(r"^evidence_tier:\s*([^\s#]+)", re.MULTILINE)
_REVIEW_TYPED_RE = re.compile(r"^review_typed_source:\s*([^\s#]+)", re.MULTILINE)


def _match_value(pattern: re.Pattern[str], text: str) -> str | None:
    match = pattern.search(text)
    return match.group(1) if match else None


def _check_provenance(
    ctx: ValidateContext,
    path: Path,
    background: set[str],
) -> Iterator[object]:
    text = ctx.read_text_cached(path)
    source_ref = _match_value(_SOURCE_REF_RE, text)
    if source_ref is None:
        return
    match = _REF_RE.fullmatch(source_ref)
    if match is None or match.group(1) not in background:
        return
    key = match.group(1)

    if _match_value(_REVIEW_TYPED_RE, text) != "true":
        yield validation_observation(
            severity=Severity.WARN,
            path=path,
            line=None,
            message=(
                f"source_ref names paper:{key} (status:background) without "
                "review_typed_source: true"
            ),
            rule=RULE_SOURCE_TYPING,
            task=None,
            qualifiers={"paper_ref": key},
        )

    if _match_value(_EVIDENCE_TIER_RE, text) != "background":
        yield validation_observation(
            severity=Severity.WARN,
            path=path,
            line=None,
            message=(
                f"source_ref names paper:{key} (status:background) without "
                "evidence_tier: background"
            ),
            rule=RULE_EVIDENCE_TIER,
            task=None,
            qualifiers={"paper_ref": key},
        )
```

Then, inside `check_background_reviews`, immediately after the `if not background:` early return and before the citation-root loop:

```python
    provenance_root = ctx.doc_dir / "provenance"
    if provenance_root.is_dir():
        for path in sorted(provenance_root.glob("*.yaml")):
            for observation in _check_provenance(ctx, path, background):
                violations += 1
                yield observation
```

Move `violations = 0` above this block so both arms increment the same counter.

- [ ] **Step 4: Run the full test module**

```bash
cd science && uv run --frozen pytest tests/validate/test_checks_papers_background_reviews.py -v
```

Expected: 8 passed.

- [ ] **Step 5: Assert the check runs in both profiles and is not `--all`-gated**

Append:

```python
from science_tool.validate.runner import VALIDATE_PROFILES, _checks_for_profile


def test_check_runs_in_every_profile() -> None:
    """A guardrail that only runs in the slow path is a guardrail that stops running."""
    for profile in VALIDATE_PROFILES:
        names = {entry.fn.__name__ for entry in _checks_for_profile(profile)}
        assert "check_background_reviews" in names, profile
```

- [ ] **Step 6: Run it**

```bash
cd science && uv run --frozen pytest tests/validate/test_checks_papers_background_reviews.py::test_check_runs_in_every_profile -v
```

Expected: PASS. If it fails, the section or function name has been added to `_COMMIT_EXCLUDED_SECTIONS` / `_COMMIT_EXCLUDED_FUNCTIONS` in `runner.py` — remove it.

- [ ] **Step 7: Lint, typecheck, commit**

```bash
cd science && uv run ruff check && uv run pyright
git add science/src/science_tool/validate/checks/papers.py \
        science/tests/validate/test_checks_papers_background_reviews.py
git commit -m "feat(validate): add the provenance typing arm to the background-review check"
```

---

### Task 4: Add the retirement rule and stop executing project Python

**Files:**
- Modify: `science/src/science_tool/validate/runtime.py`
- Modify: `science/src/science_tool/validate/runner.py`
- Modify: `science/src/science_tool/validate/__init__.py`
- Test: `science/tests/validate/test_sidecar_retirement.py`

**Interfaces:**
- Consumes: `FindingProducer`, `FindingRule`, `RUNTIME_SECTION`, `RuntimeEmptyQualifiers` from `runtime.py`.
- Produces: `RULE_PYTHON_SIDECAR_REMOVED`, registered on `VALIDATION_RUNTIME_PRODUCER`.

- [ ] **Step 1: Write the failing test**

```python
"""Python validation sidecars are reported, never executed."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from science_tool.validate.runner import run
from science_tool.validate.runtime import RULE_PYTHON_SIDECAR_REMOVED, RULE_SIDECAR_REMOVED

SENTINEL = "science_sidecar_executed_sentinel"

SIDECAR = f'''
import pathlib
pathlib.Path(__file__).parent.joinpath("{SENTINEL}").write_text("ran")
'''


def _run(root: Path):
    return run(root, strict=False, verbose=False)


def test_sidecar_file_yields_exactly_one_retirement_finding(tmp_path: Path) -> None:
    (tmp_path / "validate_local.py").write_text(SIDECAR, encoding="utf-8")

    result = _run(tmp_path)

    matching = [f for f in result.results if f.rule_id == RULE_PYTHON_SIDECAR_REMOVED.id]
    assert len(matching) == 1
    assert matching[0].severity == "error"
    assert matching[0].subject.type == "project"


def test_sidecar_is_never_imported_or_executed(tmp_path: Path) -> None:
    (tmp_path / "validate_local.py").write_text(SIDECAR, encoding="utf-8")

    _run(tmp_path)

    assert "validate_local" not in sys.modules
    assert not (tmp_path / SENTINEL).exists()


def test_python_and_legacy_sidecars_are_distinct_rules(tmp_path: Path) -> None:
    (tmp_path / "validate_local.py").write_text(SIDECAR, encoding="utf-8")
    (tmp_path / "validate.local.sh").write_text("#!/bin/sh\n", encoding="utf-8")

    result = _run(tmp_path)

    rule_ids = {f.rule_id for f in result.results}
    assert RULE_PYTHON_SIDECAR_REMOVED.id in rule_ids
    assert RULE_SIDECAR_REMOVED.id in rule_ids
    assert RULE_PYTHON_SIDECAR_REMOVED.id != RULE_SIDECAR_REMOVED.id


def test_hook_api_is_gone() -> None:
    import science_tool.validate as validate_pkg

    assert not hasattr(validate_pkg, "hook")


def test_run_has_no_sidecar_parameter() -> None:
    import inspect

    assert "enable_python_sidecar" not in inspect.signature(run).parameters
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd science && uv run --frozen pytest tests/validate/test_sidecar_retirement.py -v
```

Expected: FAIL — `ImportError: cannot import name 'RULE_PYTHON_SIDECAR_REMOVED'`.

- [ ] **Step 3: Add the rule in `runtime.py`**

Insert after `RULE_SIDECAR_REMOVED`:

```python
RULE_PYTHON_SIDECAR_REMOVED = FindingRule(
    id="validate.python-sidecar-removed",
    severities=frozenset({"error"}),
    subject_types=frozenset({"project"}),
    qualifier_schema=RuntimeEmptyQualifiers,
    title="Python validation sidecar removed",
    section=RUNTIME_SECTION.id,
    display_order=19903,
    default_visibility="visible",
)
```

Empty identity qualifiers are correct: a project either carries the file or does not. Then extend the producer:

```python
VALIDATION_RUNTIME_PRODUCER = FindingProducer(
    producer_id="validate.runtime",
    namespace="validate_checks",
    source_module="validate/runtime.py",
    rules=(RULE_CHECK_ERROR, RULE_SIDECAR_REMOVED, RULE_PYTHON_SIDECAR_REMOVED),
    sections=(RUNTIME_SECTION,),
)
```

- [ ] **Step 4: Delete the hook API and sidecar import from `runner.py`**

Delete: `HookFn`, `_HOOK_NAMES`, `_HOOKS`, `_MISSING_MODULE`, `HookName` (both branches of the `TYPE_CHECKING` block), `_PythonSidecarState`, `hook`, `_dispatch_hooks`, `_clear_hooks`, `_install_python_sidecar`, `_module_is_from_project`, and `_legacy_sidecar_removed_result` if it becomes unused.

Replace lines 131–150 of `run()` with:

```python
    python_sidecar_path = ctx.project_root / "validate_local.py"
    legacy_sidecar_path = ctx.project_root / "validate.local.sh"
    try:
        if legacy_sidecar_path.exists():
            runtime_findings.append(
                RULE_SIDECAR_REMOVED.build(
                    subject=ProjectSubject(),
                    severity="error",
                    qualifiers={},
                    message=(
                        "validate.local.sh is no longer supported; see "
                        f"{_SIDECAR_RETIREMENT_GUIDE}"
                    ),
                )
            )
        if python_sidecar_path.is_file():
            runtime_findings.append(
                RULE_PYTHON_SIDECAR_REMOVED.build(
                    subject=ProjectSubject(),
                    severity="error",
                    qualifiers={},
                    message=(
                        "validate_local.py is no longer executed; project checks "
                        f"belong in the toolkit. See {_SIDECAR_RETIREMENT_GUIDE}"
                    ),
                )
            )
```

Delete the `if sidecar_enabled:` block that dispatched `extra_checks` (lines 187–190), and replace the entire `finally:` block (lines 217–225) with nothing — `run()` no longer needs teardown, so the `try:` becomes plain sequential code. Remove the now-unused `import importlib.util`, `import os`, `import sys`, `from types import ModuleType`, and `cast` if unused.

Replace the guide constant:

```python
_SIDECAR_RETIREMENT_GUIDE = "docs/migration/2026-05-19-validate-local-sh-porting-guide.md"
```

- [ ] **Step 5: Drop the `hook` export**

In `science/src/science_tool/validate/__init__.py`, remove `hook` from both the import from `runner` and `__all__`.

- [ ] **Step 6: Run the tests**

```bash
cd science && uv run --frozen pytest tests/validate/test_sidecar_retirement.py -v
```

Expected: 5 passed. `test_run_has_no_sidecar_parameter` will still fail until Task 5 — that is expected; mark it `xfail` only if you are committing between tasks, otherwise complete Task 5 before committing.

- [ ] **Step 7: Commit**

```bash
git add science/src/science_tool/validate/runtime.py \
        science/src/science_tool/validate/runner.py \
        science/src/science_tool/validate/__init__.py \
        science/tests/validate/test_sidecar_retirement.py
git commit -m "feat(validate)!: stop executing project-authored validation sidecars"
```

---

### Task 5: Remove the rest of the extension surface

**Files:**
- Modify: `science/src/science_tool/validate/runner.py` (drop `enable_python_sidecar`)
- Modify: `science/src/science_tool/graph/health_checks/validate.py`
- Modify: `science/src/science_tool/validate/context.py`
- Modify: `science/tests/validate/test_context.py:24-26`
- Modify: `science/src/science_tool/project_artifacts/registry.yaml`
- Modify: `science/src/science_tool/project_artifacts/cli.py`
- Modify: `science/src/science_tool/budget/registry.py`
- Delete: `science/src/science_tool/project_artifacts/port_validate_sidecar.py` and its tests

**Interfaces:**
- Consumes: nothing new.
- Produces: `run()` without `enable_python_sidecar`.

Deleting the env-var branch while leaving the parameter would leave a keyword that silently does nothing — explicit over defensive.

- [ ] **Step 1: Drop the parameter and fix its production caller**

Remove `enable_python_sidecar: bool = True,` from `run()`'s signature in `runner.py`. Then remove the `enable_python_sidecar=False,` argument from the `run(...)` call in `science/src/science_tool/graph/health_checks/validate.py`.

- [ ] **Step 2: Delete the stale context fields**

In `science/src/science_tool/validate/context.py`, delete the `papers_dir`, `provenance_dir`, and `themes_dir` field declarations and their assignments in `from_project_root`. These carry `doc/`-rooted paths and have zero production consumers. Delete the corresponding assertions at `science/tests/validate/test_context.py:24-26`.

A field whose sole consumer is a test pinning it to a wrong value is how the drift stayed invisible.

- [ ] **Step 3: Delete the porting command**

```bash
git rm science/src/science_tool/project_artifacts/port_validate_sidecar.py
git rm science/tests/test_cli_artifacts_port_validate_sidecar.py
```

Do **not** touch `science/tests/test_query_iter_sidecars.py` — "sidecar" there refers to query iteration, an unrelated concept.

Remove its click command and its lazy import from `science/src/science_tool/project_artifacts/cli.py`, and remove its `"single generated-sidecar path"` entry from `science/src/science_tool/budget/registry.py`.

- [ ] **Step 4: Remove the advertised extension protocol**

In `science/src/science_tool/project_artifacts/registry.yaml`, delete the `extension_protocol:` block from the `validate.sh` artifact (the `kind: python_sidecar` / `sidecar_path: validate_local.py` / `contract:` keys). Bump the artifact's `version`, move the current hash into `previous_hashes`, and add a `migrations` entry, following the existing `2026.05.12.1 → 2026.05.21.1` pattern in that file.

The artifact body itself does not change — only its metadata — so `current_hash` stays the same. Verify with `science/tests/test_validate_sh_section_8.py`, which asserts the hash/version relationship, and update the version constants it pins.

- [ ] **Step 5: Run the affected tests**

```bash
cd science && uv run --frozen pytest \
  tests/validate/test_sidecar_retirement.py \
  tests/validate/test_context.py \
  tests/test_validate_sh_section_8.py \
  tests/test_budget_regression.py -v
```

Expected: all pass, including `test_run_has_no_sidecar_parameter`.

- [ ] **Step 6: Lint, typecheck, commit**

```bash
cd science && uv run ruff check && uv run pyright
git add -A science/
git commit -m "refactor(validate)!: remove the sidecar extension surface"
```

---

### Task 6: Documentation and regenerated mirrors

**Files:**
- Modify: `docs/conventions/validate.md`
- Modify: `docs/migration/2026-05-19-validate-local-sh-porting-guide.md`
- Modify: `docs/migration/managed-artifacts-template.md`
- Regenerate: `skills/generated/science-command-preamble/references/docs/conventions/validate.md`

- [ ] **Step 1: Update `docs/conventions/validate.md`**

Remove the Python-sidecar discovery contract and the `SCIENCE_VALIDATE_DISABLE_SIDECAR` row from the environment-variable table. State that `science validate` never executes project code, and that a `validate_local.py` present in a project produces a `validate.python-sidecar-removed` error.

- [ ] **Step 2: Retarget the porting guide**

Rewrite `docs/migration/2026-05-19-validate-local-sh-porting-guide.md` from "port your shell sidecar to Python" to "sidecars are retired." It must answer: where does a reusable policy check go (a toolkit check — open a design conversation), and where does a genuinely project-specific check go (a project-owned command the project runs itself, with nothing enforcing it).

- [ ] **Step 3: Fix `docs/migration/managed-artifacts-template.md`**

This file is **not** historical and still instructs projects to migrate logic *into* a sidecar (line ~157, "Use when the project has substantial logic that needs to migrate into the sidecar"; line ~262 references `validate.local.sh`). Leaving it is an active instruction to recreate what this work removes. Update or retire it.

- [ ] **Step 4: Regenerate the committed mirror**

Never hand-edit files under `skills/generated/`. Regenerate them with the skills generator, then confirm exact fresh-generation equality:

```bash
cd science && uv run --frozen science agents generate
git diff --stat skills/generated/
```

The command is `science agents generate` — `science skills` has only `coverage`, `curate`, `lint`, and `sources`, none of which regenerate the mirror.

Expected: only `science-command-preamble/references/docs/conventions/validate.md` changes, matching the Step 1 edit.

- [ ] **Step 5: Verify no stale references remain**

```bash
cd /mnt/ssd/Dropbox/science/.worktrees/sidecar-retirement
grep -rn "validate_local\|SCIENCE_VALIDATE_DISABLE_SIDECAR\|@hook" docs/ templates/ skills/ \
  | grep -v "docs/plans/" | grep -v "historical/"
```

Expected: only retirement-context mentions (the porting guide describing what was removed). No instructions to create a sidecar.

- [ ] **Step 6: Commit**

```bash
git add docs/ skills/
git commit -m "docs(validate): retarget sidecar documentation to retirement"
```

---

### Task 7: Full-suite and real-project verification

**Files:** none modified — this task only verifies.

- [ ] **Step 1: Run the full toolkit suite with an explicit long timeout**

```bash
cd science && uv run --frozen pytest
```

Run this with a 600000 ms tool timeout. ~10k tests, 2–3 min. Expected: all pass.

- [ ] **Step 2: Run the model suite**

```bash
cd science/model && uv run --frozen pytest
```

- [ ] **Step 3: Run the opt-in markers**

```bash
cd science && uv run --frozen pytest -m snapshot
cd science && uv run --frozen pytest -m real_projects
```

- [ ] **Step 4: Confirm canonical parity against the Task 1 baselines**

Install the branch toolkit into a scratch venv and re-run each project, diffing finding-by-finding against `~/scratch/sidecar-baselines/*-canonical.json`. The retirement must not perturb canonical output.

```bash
python3 - <<'PY'
import json, sys
from pathlib import Path
base = Path.home() / "scratch/sidecar-baselines"
for name in ("evolution", "protein-landscape", "meta", "health-meta"):
    b = base / f"{name}-canonical.json"
    a = base / f"{name}-after.json"
    if not (b.exists() and a.exists()):
        print(f"SKIP {name}"); continue
    def ident(d):
        return sorted((r.get("rule"), r.get("path"), r.get("message")) for r in json.load(open(d))["results"])
    print(name, "MATCH" if ident(b) == ident(a) else "DIFF")
PY
```

Expected: `MATCH` for every project, apart from the newly-added `papers.background-review-*` notice rows.

- [ ] **Step 5: Confirm the expected delta is zero new warnings**

Per design §5.2 the corpus is compliant. Expected after promotion:

| project | expected |
|---|---|
| evolution | notice: no `status: background` papers. **Zero warnings.** |
| health/meta | notice: 9 background papers, 0 violations. **Zero warnings.** |

If either produces a warning, **stop** — either the corpus changed since 2026-07-29 or the roots are wrong. Do not adjust the expectation to match the output.

- [ ] **Step 6: Commit nothing; record results**

Paste the parity table into the PR description or a results doc. No code change.

---

### Task 8: Push the toolkit to the public default branch

**Files:** none.

A consumer cannot resolve an unpushed revision. No consumer commit may be authored before this lands.

- [ ] **Step 1: Merge to `main`**

Verify the branch first — this repo's `main` checkout floats because it is Dropbox-synced.

```bash
cd /mnt/ssd/Dropbox/science
git branch --show-current   # must print: main
git merge --no-ff sidecar-retirement
```

- [ ] **Step 2: Push and confirm reachability**

```bash
git push origin main
git ls-remote origin main
```

Expected: the remote SHA matches local `main`. Record that SHA — Tasks 9–11 pin to it.

---

### Task 9: Migrate `~/d/health/meta` atomically

**Files:**
- Modify: `~/d/health/meta/pyproject.toml:13`, `~/d/health/meta/uv.lock`, `~/d/health/meta/AGENTS.md`
- Delete: `~/d/health/meta/validate_local.py`

This project pins an explicit `rev`. One commit: pin, deletion, docs.

- [ ] **Step 1: Update the pin**

Replace `rev = "3b72db60b8d591cf3dbac8ae25ca194f6cda9c8b"` in `[tool.uv.sources]` with the Task 8 SHA.

- [ ] **Step 2: Relock and sync**

```bash
cd ~/d/health/meta && uv lock && uv sync --frozen
```

- [ ] **Step 3: Delete the sidecar**

```bash
cd ~/d/health/meta && git rm validate_local.py
```

- [ ] **Step 4: Update `AGENTS.md`**

Record that the reviews-are-not-evidence guardrail is now a toolkit check and the project no longer owns it. Remove any instruction to edit `validate_local.py`.

- [ ] **Step 5: Verify**

```bash
cd ~/d/health/meta && uv run science validate --format json | python3 -c "
import json,sys; d=json.load(sys.stdin); print(d['summary'])"
```

Expected: exit 0, `errors: 0`, and **zero** `papers.background-review-*` warnings. The nine background papers are cited under `source_refs`, not `evidence_refs`, and both `paper:Tasci2022` provenance records already carry `evidence_tier: background` and `review_typed_source: true`.

- [ ] **Step 6: Commit atomically**

```bash
cd ~/d/health/meta
git add pyproject.toml uv.lock AGENTS.md
git commit -m "chore: adopt toolkit background-review check and drop the validation sidecar"
```

Note this repo has **no GitHub remote** — commit only, never push.

---

### Task 10: Migrate `~/d/cancer/mechanisms/evolution` atomically

**Files:**
- Modify: `~/d/cancer/mechanisms/evolution/uv.lock:3062`, `AGENTS.md`
- Delete: `~/d/cancer/mechanisms/evolution/validate_local.py`

Unqualified Git source; the revision lives only in `uv.lock`, currently `ed6b50dc`.

- [ ] **Step 1: Relock to the Task 8 SHA**

```bash
cd ~/d/cancer/mechanisms/evolution && uv lock --upgrade-package science && uv sync --frozen
grep -A2 '^name = "science"' uv.lock
```

Expected: the `source = { git = ... #<sha> }` line shows the Task 8 SHA.

- [ ] **Step 2: Delete the sidecar and update docs**

```bash
cd ~/d/cancer/mechanisms/evolution && git rm validate_local.py
```

Update `AGENTS.md` as in Task 9 Step 4.

- [ ] **Step 3: Verify the original crashing command now succeeds**

```bash
cd ~/d/cancer/mechanisms/evolution && uv run science validate --format json | head -c 200; echo; echo "exit=$?"
```

Expected: `exit=0`, valid JSON, no traceback. This is the reproduction from Task 1 Step 3 now passing.

- [ ] **Step 4: Confirm the expected notice**

Expected: a notice reporting no `status: background` papers (all 15 are active), and **zero** `papers.background-review-*` warnings.

- [ ] **Step 5: Commit atomically**

```bash
cd ~/d/cancer/mechanisms/evolution
git add uv.lock AGENTS.md
git commit -m "chore: adopt toolkit background-review check and drop the validation sidecar"
```

This repo is Dropbox-synced — verify the branch before committing.

---

### Task 11: Migrate `~/d/protein-landscape` atomically

**Files:**
- Modify: `~/d/protein-landscape/uv.lock:4412`, `AGENTS.md`
- Delete: `~/d/protein-landscape/validate_local.py`

Its check is **not** promoted — the expensive-pipeline-artifact check becomes a project-owned command with nothing enforcing it (design §4).

- [ ] **Step 1: Relock to the Task 8 SHA**

```bash
cd ~/d/protein-landscape && uv lock --upgrade-package science && uv sync --frozen
```

- [ ] **Step 2: Convert the sidecar to a standalone script**

Move the artifact-presence logic out of `validate_local.py` into a plain project script (for example `scripts/check_expensive_artifacts.py`). The existing hook is 66 lines using `json` and `subprocess` and yields four `Result` sites plus one INFO. Port each of the four to a printed message and a non-zero exit; drop the INFO ("All expensive pipeline artifacts present") to a success message on stdout. The script imports nothing from `science_tool.validate`.

```bash
cd ~/d/protein-landscape && git rm validate_local.py
```

- [ ] **Step 3: Document the loss in `AGENTS.md`**

State plainly: this check no longer runs as part of `science validate`, it is not in `--format json` output, and **nothing enforces that it runs**. Give the exact command.

- [ ] **Step 4: Verify**

```bash
cd ~/d/protein-landscape && uv run science validate --format json | head -c 200; echo; echo "exit=$?"
```

Expected: `exit=0`, valid JSON, no traceback — the crash recorded in the method-slice inventory is resolved.

- [ ] **Step 5: Commit atomically**

```bash
cd ~/d/protein-landscape
git add uv.lock AGENTS.md scripts/
git commit -m "chore: drop the validation sidecar and run artifact checks standalone"
```

---

### Task 12: Migrate `~/d/science/meta` atomically

**Files:**
- Modify: `~/d/science/meta/AGENTS.md`
- Delete: `~/d/science/meta/validate_local.py`

No pin step — its toolkit source is editable and in-repository, so toolkit and consumer move together by construction.

- [ ] **Step 1: Delete the sidecar**

```bash
cd ~/d/science && git rm meta/validate_local.py
```

- [ ] **Step 2: Repair the documentation**

This is a **repair, not an addition**: `meta/AGENTS.md` currently states that t034 validation is invoked through `validate_local.py`, which is now false. Replace it with the direct `t034_validator` CLI invocation, and state that it no longer runs as part of `science validate` and nothing enforces it.

- [ ] **Step 3: Verify**

```bash
cd ~/d/science/meta && uv run science validate --format json | head -c 200; echo; echo "exit=$?"
```

Expected: `exit=0`, valid JSON, no traceback, and no t034 findings.

- [ ] **Step 4: Confirm the t034 CLI still works standalone**

```bash
cd ~/d/science/meta && uv run python -m t034_validator
```

`src/t034_validator/__main__.py` exists, so `python -m` is the invocation. The package has **no** console script — `[project.scripts]` declares only `h01-sim` — so do not document a `t034-validate` entry point that does not exist.

- [ ] **Step 5: Commit atomically**

```bash
cd ~/d/science
git add meta/AGENTS.md
git commit -m "chore(meta): drop the validation sidecar and invoke t034 directly"
```

---

## Verification Checklist

Design §5.3 coverage, mapped to tasks:

| § | Requirement | Task |
|---|---|---|
| 5.3.1 | exactly one occurrence of `validate.python-sidecar-removed`, valid JSON | 4 |
| 5.3.2 | sidecar never imported or executed (`sys.modules` + sentinel) | 4 |
| 5.3.3 | project-authored `FindingRule` cannot enter the registry | pre-existing; confirmed by Task 7 full suite |
| 5.3.4 | the two sidecar rules are distinct | 4 |
| 5.3.5 | three rules fire; both typing conditions yield two findings | 2, 3 |
| 5.3.6 | check present in `full` and `commit` profiles | 3 |
| 5.3.7 | the check can fail — mutation turns the fixture red | 2, 3 |

**On §5.3.7:** §5.2 means the real corpus cannot falsify this check — it is compliant. The fixtures in Tasks 2 and 3 are the only falsification available, which is exactly why `test_background_paper_in_evidence_refs_warns` and `test_provenance_record_violating_both_conditions_yields_two_findings` are load-bearing rather than decorative. Before declaring Task 3 done, mutate `_citation_roots` to return an empty tuple and confirm those tests go red.

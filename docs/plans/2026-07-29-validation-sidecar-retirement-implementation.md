# Validation Sidecar Retirement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop `science validate` from importing and executing project-authored `validate_local.py`, promote the one reusable project check into the canonical check set, and migrate all four consumer repositories atomically.

**Architecture:** The `hook` API and Python-sidecar import are deleted outright from `validate/runner.py`; a new `validate.python-sidecar-removed` rule on the existing `VALIDATION_RUNTIME_PRODUCER` reports a stale sidecar file as a structured ERROR instead of crashing. The `reviews-are-not-evidence` policy — currently duplicated in two projects and scanning a directory the papers left — becomes three WARN rules on the **existing `validate.papers` producer**, with roots resolved through `resolve_path_policy` and refs read through parsed frontmatter rather than regex. Consumer repositories then update their toolkit pin, delete their sidecar, and fix their docs in one commit each.

**Tech Stack:** Python 3.13, Pydantic v2, click, pytest, uv. Findings model in `science-model` (`science_model.audit`); validation in `science_tool.validate`.

**Design doc:** [`2026-07-29-validation-sidecar-retirement-design.md`](2026-07-29-validation-sidecar-retirement-design.md)

## Global Constraints

- **No compatibility layer.** No shim for `hook`, no deprecation wrapper, no re-export. Deliberate breaking change.
- **Run from the package directory.** `cd science` before any `uv run`. There is no root `pyproject.toml`.
- **Test commands:** `cd science && uv run --frozen pytest`. Default runs exclude `snapshot` and `real_projects` markers; opt in with `-m snapshot` / `-m real_projects`.
- **Full suite is ~10k tests / 2-3 min** — longer than the default 120s timeout. Run scoped selections per task; reserve the full run for Task 8 with an explicit long timeout.
- **Never run two suites concurrently in the same worktree** — they race on shared test-output paths.
- **Lint/types from `science/`:** `uv run ruff check` and `uv run pyright`. Pyright is configured once by the repo-root `pyrightconfig.json`; test directories are not type-checked.
- **Every check fixture must contain a `science.yaml`.** `ValidateContext.from_project_root` raises `ValidateContextError` without it, before any check runs.
- **Parse, don't regex.** Use `ctx.frontmatter(path)` for entity refs and `ctx.read_yaml(path)` for provenance. The sidecars' regexes require indented list items; every live entity uses top-level `- paper:...`, and they mishandle quoted YAML scalars and hyphenated or dotted paper IDs.
- **Conventional commits.** No AI-attribution trailers on commits, PRs, or comments.
- **Privacy:** use `~/d/` in docs and code, never `/home/keith/` or `/mnt/ssd/Dropbox/`.
- **Search with `rg`,** not `grep` pipelines.
- **Working branch:** `sidecar-retirement`, worktree `~/d/science/.worktrees/sidecar-retirement/`.
- **Consumer work happens in isolated worktrees,** never in a consumer's primary checkout. Two of the consumer repos are Dropbox-synced and their primary checkouts float off their working branch.

---

## Preconditions

Both must hold before Task 1. Neither is optional.

- [ ] **P1: Plan 3 is merged to `main`.** `finding-convergence-plan-3` changes `validate/findings.py`, `validate/acceptance.py`, and `findings/acceptance_migration.py` — the finding and acceptance interfaces this work declares new rules against.
- [ ] **P2: This branch is rebased onto post–Plan 3 `main`.**

```bash
cd ~/d/science/.worktrees/sidecar-retirement
git fetch origin && git rebase origin/main
cd science && uv run --frozen pytest tests/validate -q
```

Expected: rebase clean, validate tests green.

---

## File Structure

**Toolkit — created:**
- `science/tests/validate/test_checks_papers_background_reviews.py`
- `science/tests/validate/test_sidecar_retirement.py`

**Toolkit — modified:**
- `science/src/science_tool/validate/checks/papers.py` — three rules on the existing section/producer
- `science/src/science_tool/validate/runtime.py` — `RULE_PYTHON_SIDECAR_REMOVED`
- `science/src/science_tool/validate/runner.py` — delete hook API and sidecar import; drop `enable_python_sidecar`
- `science/src/science_tool/validate/__init__.py` — drop `hook` export
- `science/src/science_tool/validate/context.py` — drop three stale `doc/`-rooted fields
- `science/src/science_tool/graph/health_checks/validate.py` — drop `enable_python_sidecar=False`
- `science/src/science_tool/project_artifacts/registry.yaml` — `extension_protocol.kind: none`
- `science/src/science_tool/project_artifacts/cli.py`, `science/src/science_tool/budget/registry.py`
- `science/tests/validate/test_context.py:24-26`
- `meta/validate_local.py` (deleted), `meta/evidence/README.md`, `meta/evidence/t034-causal-graph-contract.md`, `meta/entities/questions/0010-causal-graph-construction-pipeline.md`, `meta/src/t034_validator/__main__.py`
- `docs/conventions/validate.md`, `docs/migration/*.md`, `skills/generated/…` (regenerated)

**Toolkit — deleted:**
- `science/src/science_tool/project_artifacts/port_validate_sidecar.py`
- `science/tests/test_cli_artifacts_port_validate_sidecar.py`

---

### Task 1: Capture all baselines with one pinned toolkit revision

**Files:** none in-repo. Baselines land in `~/scratch/sidecar-baselines/`.

**Interfaces:**
- Produces: five baseline JSON files that Task 8 diffs against.

Design §5.1: the four projects sit in three different states, and their installed revisions differ (`3b72db60` vs `ed6b50dc`). Comparing each project's own installed revision to a post-retirement toolkit would conflate this change with everything between those revisions. **All canonical baselines use one revision: post–Plan 3 `main`, pre-retirement.**

- [ ] **Step 1: Build the pinned baseline environment**

```bash
mkdir -p ~/scratch/sidecar-baselines
cd ~/d/science && git rev-parse origin/main > ~/scratch/sidecar-baselines/BASELINE_SHA
uv venv ~/scratch/sidecar-baselines/venv
~/scratch/sidecar-baselines/venv/bin/pip install \
  "science @ git+https://github.com/khughitt/science.git@$(cat ~/scratch/sidecar-baselines/BASELINE_SHA)#subdirectory=science"
```

- [ ] **Step 2: Record the pre-existing crashes**

```bash
BIN=~/scratch/sidecar-baselines/venv/bin/science
for p in ~/d/cancer/mechanisms/evolution ~/d/protein-landscape ~/d/science/meta ~/d/health/meta; do
  echo "=== $p ==="
  (cd "$p" && "$BIN" validate --format json 2>&1 | tail -3)
done > ~/scratch/sidecar-baselines/crashes.txt 2>&1
cat ~/scratch/sidecar-baselines/crashes.txt
```

Expected: all four end with `TypeError: Result.__init__() missing 1 required positional argument: 'qualifiers'`. Under the pinned post–Plan 2 revision health/meta crashes too; its clean run only happens against its own pinned `3b72db60`.

- [ ] **Step 3: Capture health/meta's own-revision baseline separately**

This is the one baseline in which a sidecar actually executes, and it is informational — not the parity target.

```bash
cd ~/d/health/meta
.venv/bin/science validate --format json > ~/scratch/sidecar-baselines/health-meta-own-rev.json
test $? -eq 0 || { echo "FAIL: expected exit 0"; exit 1; }
```

Expected: exit 0, `summary.warnings == 153`, `summary.infos == 0`, and **zero** guardrail rows — `doc/papers/` holds only an `archive/` subdirectory.

- [ ] **Step 4: Capture the four canonical baselines — the parity targets**

The sidecar-disabling env var still exists at this point. This is the last moment it can be used.

```bash
BIN=~/scratch/sidecar-baselines/venv/bin/science
set -e
for p in ~/d/cancer/mechanisms/evolution ~/d/protein-landscape ~/d/science/meta ~/d/health/meta; do
  name=$(basename "$p")
  ( cd "$p" && SCIENCE_VALIDATE_DISABLE_SIDECAR=1 "$BIN" validate --all --strict --format json ) \
    > ~/scratch/sidecar-baselines/"$name"-canonical.json
  echo "$name captured"
done
```

`~/d/science/meta` and `~/d/health/meta` both basename to `meta` — capture them to distinct names:

```bash
mv ~/scratch/sidecar-baselines/meta-canonical.json ~/scratch/sidecar-baselines/health-meta-canonical.json
BIN=~/scratch/sidecar-baselines/venv/bin/science
( cd ~/d/science/meta && SCIENCE_VALIDATE_DISABLE_SIDECAR=1 "$BIN" validate --all --strict --format json ) \
  > ~/scratch/sidecar-baselines/science-meta-canonical.json
```

- [ ] **Step 5: Verify all five files parse, and fail loudly if any is missing**

```bash
python3 - <<'PY'
import json, sys
from pathlib import Path
base = Path.home() / "scratch/sidecar-baselines"
expected = [
    "health-meta-own-rev.json", "health-meta-canonical.json",
    "evolution-canonical.json", "protein-landscape-canonical.json",
    "science-meta-canonical.json",
]
missing = [n for n in expected if not (base / n).exists()]
if missing:
    sys.exit(f"FAIL missing baselines: {missing}")
for n in expected:
    print(n, json.loads((base / n).read_text())["summary"])
PY
```

Expected: five summary lines, no `FAIL`. No commit — baselines live outside the repos.

---

### Task 2: Add the background-review rules to the existing papers producer

**Files:**
- Modify: `science/src/science_tool/validate/checks/papers.py`
- Test: `science/tests/validate/test_checks_papers_background_reviews.py`

**Interfaces:**
- Consumes: existing `SECTION`, `RULES`, `check_papers` in `papers.py`; `declare_validation_rules`, `validation_observation` from `science_tool.validate.findings`; `resolve_path_policy` from `science_tool.entities`; `CheckObservation` from `science_tool.validate.checks`.
- Produces: `RULE_EVIDENCE_REF`, `RULE_SOURCE_TYPING`, `RULE_EVIDENCE_TIER`; helper `_background_review_observations(ctx) -> Iterator[CheckObservation]` called from the existing decorated `check_papers`.

The architecture promises the existing `validate.papers` producer. Do **not** create a second producer — extend the existing section and rules, and make the new logic an undecorated helper the existing `@Check` function yields from.

- [ ] **Step 1: Write the failing tests**

```python
"""Promoted reviews-are-not-evidence guardrail."""

from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.validate.checks.papers import (
    RULE_EVIDENCE_REF,
    RULE_EVIDENCE_TIER,
    RULE_SOURCE_TYPING,
    _background_review_observations,
)
from science_tool.validate.context import ValidateContext
from science_tool.validate.observations import ValidationNotice
from science_tool.validate.result import Result


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """A minimal Science project. Without science.yaml the context refuses to build."""
    (tmp_path / "science.yaml").write_text("name: fixture\n", encoding="utf-8")
    return tmp_path


def _paper(root: Path, key: str, status: str) -> None:
    papers = root / "entities" / "papers"
    papers.mkdir(parents=True, exist_ok=True)
    (papers / f"{key}.md").write_text(
        f'---\nkind: paper\ntitle: "{key}"\nstatus: {status}\n---\n', encoding="utf-8"
    )


def _entity(root: Path, kind_dir: str, name: str, frontmatter: str) -> None:
    d = root / "entities" / kind_dir
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{name}.md").write_text(f"---\n{frontmatter}---\n\nbody\n", encoding="utf-8")


def _provenance(root: Path, name: str, body: str) -> None:
    d = root / "doc" / "provenance"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{name}.yaml").write_text(body, encoding="utf-8")


def _ctx(root: Path) -> ValidateContext:
    return ValidateContext.from_project_root(
        root, strict=False, verbose=False, include_all_checks=False
    )


def _issues(root: Path) -> list[Result]:
    return [o for o in _background_review_observations(_ctx(root)) if isinstance(o, Result)]


def test_background_paper_in_evidence_refs_warns(project: Path) -> None:
    _paper(project, "Tasci2022", "background")
    _entity(
        project, "hypotheses", "0001-h",
        "kind: hypothesis\nevidence_refs:\n- paper:Tasci2022\n",
    )

    issues = _issues(project)

    assert len(issues) == 1
    assert issues[0].rule is RULE_EVIDENCE_REF
    assert issues[0].qualifiers["paper_ref"] == "Tasci2022"


def test_unindented_list_items_are_parsed(project: Path) -> None:
    """Every live entity writes top-level `- paper:...`; the sidecar regex required indentation."""
    _paper(project, "Tasci2022", "background")
    _entity(
        project, "themes", "0007-t",
        "kind: theme\nevidence_refs:\n- paper:Tasci2022\n- report:0012-x\n",
    )

    assert len(_issues(project)) == 1


def test_hyphenated_and_dotted_paper_ids(project: Path) -> None:
    _paper(project, "van-der-Berg-2021.v2", "background")
    _entity(
        project, "reports", "0001-r",
        "kind: report\nevidence_refs:\n- paper:van-der-Berg-2021.v2\n",
    )

    issues = _issues(project)

    assert len(issues) == 1
    assert issues[0].qualifiers["paper_ref"] == "van-der-Berg-2021.v2"


def test_active_paper_in_evidence_refs_is_silent(project: Path) -> None:
    _paper(project, "Smith2024", "active")
    _entity(
        project, "hypotheses", "0001-h",
        "kind: hypothesis\nevidence_refs:\n- paper:Smith2024\n",
    )

    assert _issues(project) == []


def test_source_refs_are_not_evidence_refs(project: Path) -> None:
    """The health/meta corpus cites background papers under source_refs."""
    _paper(project, "Tasci2022", "background")
    _entity(
        project, "themes", "0007-t",
        "kind: theme\nsource_refs:\n- paper:Tasci2022\nevidence_refs:\n- report:0012-x\n",
    )

    assert _issues(project) == []


def test_duplicate_citation_dedupes_file_wide(project: Path) -> None:
    """Identity is (rule, path, paper_ref); duplicates would collide at the producer."""
    _paper(project, "Tasci2022", "background")
    _entity(
        project, "hypotheses", "0001-h",
        "kind: hypothesis\nevidence_refs:\n- paper:Tasci2022\n- cite:Tasci2022\n",
    )

    assert len(_issues(project)) == 1


def test_no_background_papers_emits_notice(project: Path) -> None:
    _paper(project, "Smith2024", "active")

    observations = list(_background_review_observations(_ctx(project)))

    assert all(isinstance(o, ValidationNotice) for o in observations)
    assert any("no status:background" in o.message for o in observations)


def test_compliant_provenance_record_is_silent(project: Path) -> None:
    """Both live health/meta Tasci2022 records are already correctly typed."""
    _paper(project, "Tasci2022", "background")
    _provenance(
        project, "tasci",
        "source_ref: paper:Tasci2022\nevidence_tier: background\nreview_typed_source: true\n",
    )

    assert _issues(project) == []


def test_quoted_source_ref_and_real_booleans(project: Path) -> None:
    """YAML quoting and native booleans must not defeat the check."""
    _paper(project, "Tasci2022", "background")
    _provenance(
        project, "tasci",
        'source_ref: "paper:Tasci2022"\nevidence_tier: "background"\nreview_typed_source: yes\n',
    )

    assert _issues(project) == []


def test_provenance_violating_both_conditions_yields_two_findings(project: Path) -> None:
    """Separate rules exist precisely so these two do not collide on identity."""
    _paper(project, "Tasci2022", "background")
    _provenance(
        project, "tasci",
        "source_ref: paper:Tasci2022\nevidence_tier: primary\nreview_typed_source: false\n",
    )

    issues = _issues(project)

    assert len(issues) == 2
    assert {i.rule for i in issues} == {RULE_SOURCE_TYPING, RULE_EVIDENCE_TIER}
    assert {i.qualifiers["paper_ref"] for i in issues} == {"Tasci2022"}


def test_provenance_for_active_paper_is_silent(project: Path) -> None:
    _paper(project, "Smith2024", "active")
    _provenance(project, "smith", "source_ref: paper:Smith2024\nevidence_tier: primary\n")

    assert _issues(project) == []
```

- [ ] **Step 2: Run to verify failure**

```bash
cd science && uv run --frozen pytest tests/validate/test_checks_papers_background_reviews.py -v
```

Expected: FAIL — `ImportError: cannot import name 'RULE_EVIDENCE_REF'`.

- [ ] **Step 3: Extend the existing rule table in `papers.py`**

Replace the existing `declare_validation_rules(...)` call — keep the same `section_id`, so the rules join the existing `validate.papers` section:

```python
SECTION, RULES = declare_validation_rules(
    section_id="papers",
    section_title="papers",
    section_order=110,
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

RULE_EVIDENCE_REF = RULES["papers.background-review-evidence-ref"]
RULE_SOURCE_TYPING = RULES["papers.background-review-source-typing"]
RULE_EVIDENCE_TIER = RULES["papers.background-review-evidence-tier"]
```

with `BackgroundReviewQualifiers` declared above it:

```python
class BackgroundReviewQualifiers(BaseModel):
    model_config = ConfigDict(extra="forbid")
    paper_ref: str
    task: str | None = None
```

Add to the imports:

```python
from typing import Any

from pydantic import BaseModel, ConfigDict

from science_tool.validate.checks import Check, CheckObservation
from science_tool.validate.findings import declare_validation_rules, validation_observation
```

Three rules, not one discriminated by qualifier: a single provenance record can violate both typing conditions at once, and a shared rule id would collide on identity.

- [ ] **Step 4: Implement the helper — parsed refs, no regex**

```python
_REF_PREFIXES = ("paper", "cite")


def _paper_key(ref: Any) -> str | None:
    """Extract the paper key from a `paper:Key` / `cite:Key` reference scalar."""
    if not isinstance(ref, str):
        return None
    prefix, separator, key = ref.partition(":")
    if not separator or prefix not in _REF_PREFIXES:
        return None
    return key.strip() or None


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


def _evidence_ref_observations(
    ctx: ValidateContext, background: set[str]
) -> Iterator[CheckObservation]:
    for root in _citation_roots(ctx):
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.md")):
            refs = ctx.frontmatter(path).get("evidence_refs")
            if not isinstance(refs, list):
                continue
            # Dedupe per (path, paper_ref) across the WHOLE file: finding identity
            # is (rule, path, paper_ref), so a repeated citation would emit two
            # identical identities and the producer boundary would reject them.
            seen: set[str] = set()
            for ref in refs:
                key = _paper_key(ref)
                if key is None or key not in background or key in seen:
                    continue
                seen.add(key)
                yield validation_observation(
                    severity=Severity.WARN,
                    path=path,
                    line=None,
                    message=(
                        f"evidence_refs cites paper:{key} (status:background); use a "
                        "primary citation or synthesis report instead of the review directly"
                    ),
                    rule=RULE_EVIDENCE_REF,
                    task=None,
                    qualifiers={"paper_ref": key},
                )


def _provenance_observations(
    ctx: ValidateContext, background: set[str]
) -> Iterator[CheckObservation]:
    provenance_root = ctx.doc_dir / "provenance"
    if not provenance_root.is_dir():
        return
    for path in sorted(provenance_root.glob("*.yaml")):
        record = ctx.read_yaml(path)
        if not isinstance(record, dict):
            continue
        key = _paper_key(record.get("source_ref"))
        if key is None or key not in background:
            continue

        if record.get("review_typed_source") is not True:
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

        if record.get("evidence_tier") != "background":
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


def _background_review_observations(ctx: ValidateContext) -> Iterator[CheckObservation]:
    background = _background_papers(ctx)
    if not background:
        yield ValidationNotice(
            path=None,
            line=None,
            message="no status:background papers; reviews-are-not-evidence checks pass",
        )
        return

    violations = 0
    for observation in _provenance_observations(ctx, background):
        violations += 1
        yield observation
    for observation in _evidence_ref_observations(ctx, background):
        violations += 1
        yield observation

    yield ValidationNotice(
        path=None,
        line=None,
        message=(
            f"{len(background)} status:background paper(s); "
            f"{violations} reviews-are-not-evidence violation(s)"
        ),
    )
```

`ctx.read_yaml` resolves quoted scalars and native booleans, so `review_typed_source: yes` is `True` and `"paper:Tasci2022"` is unquoted for us. `resolve_path_policy(...).root` is project-relative — join it to `ctx.project_root`. Reports live **flat** under the `report` root; there is no `synthesis/` subdirectory in either live project.

- [ ] **Step 5: Yield the helper from the existing decorated check**

Change the existing `check_papers` body to yield its current notice and then delegate:

```python
@Check(section=SECTION, order=7, producer_id="validate.papers", rules=tuple(RULES.values()))
def check_papers(ctx: ValidateContext) -> Iterator[CheckObservation]:
    papers_root = resolve_path_policy("paper").root
    yield _result(
        Severity.INFO,
        papers_root.as_posix(),
        f"Paper summary structure is checked in {papers_root.as_posix()}/",
    )
    yield from _background_review_observations(ctx)
```

Annotate every generator `Iterator[CheckObservation]`, never `Iterator[object]` — pyright rejects the latter against `InternalCheckFn`.

- [ ] **Step 6: Run the tests**

```bash
cd science && uv run --frozen pytest tests/validate/test_checks_papers_background_reviews.py -v
```

Expected: 11 passed.

- [ ] **Step 7: Assert both profiles, no `--all` gate**

Append:

```python
from science_tool.validate.runner import VALIDATE_PROFILES, _checks_for_profile


def test_check_runs_in_every_profile() -> None:
    """A guardrail that only runs in the slow path is a guardrail that stops running."""
    for profile in VALIDATE_PROFILES:
        names = {entry.fn.__name__ for entry in _checks_for_profile(profile)}
        assert "check_papers" in names, profile


def test_check_is_not_gated_on_include_all(project: Path) -> None:
    _paper(project, "Tasci2022", "background")
    _entity(project, "hypotheses", "0001-h", "kind: hypothesis\nevidence_refs:\n- paper:Tasci2022\n")

    ctx = ValidateContext.from_project_root(
        project, strict=False, verbose=False, include_all_checks=False
    )
    issues = [o for o in _background_review_observations(ctx) if isinstance(o, Result)]

    assert len(issues) == 1
```

- [ ] **Step 8: Run, lint, typecheck**

```bash
cd science && uv run --frozen pytest tests/validate/test_checks_papers_background_reviews.py -v
cd science && uv run ruff check && uv run pyright
```

Expected: 13 passed; ruff and pyright clean. If `test_check_runs_in_every_profile` fails, `check_papers` or the `papers` section has been added to `_COMMIT_EXCLUDED_SECTIONS` / `_COMMIT_EXCLUDED_FUNCTIONS` in `runner.py` — remove it.

- [ ] **Step 9: Prove the check can fail — mutate, confirm red, restore**

§5.2 says the live corpus is compliant, so these fixtures are the only falsification available. Verify they are load-bearing.

```bash
cd science
cp src/science_tool/validate/checks/papers.py /tmp/papers.py.bak
python3 - <<'PY'
from pathlib import Path
p = Path("src/science_tool/validate/checks/papers.py")
p.write_text(p.read_text().replace(
    'for kind in ("theme", "report", "hypothesis")',
    'for kind in ()',
))
PY
uv run --frozen pytest tests/validate/test_checks_papers_background_reviews.py -q
```

Expected: **FAILURES** in `test_background_paper_in_evidence_refs_warns`, `test_unindented_list_items_are_parsed`, `test_hyphenated_and_dotted_paper_ids`, `test_duplicate_citation_dedupes_file_wide`, `test_check_is_not_gated_on_include_all`. If any of those still pass, the fixture is not exercising the citation-root walk.

- [ ] **Step 10: Restore and confirm green**

```bash
cd science && cp /tmp/papers.py.bak src/science_tool/validate/checks/papers.py && rm /tmp/papers.py.bak
uv run --frozen pytest tests/validate/test_checks_papers_background_reviews.py -q
git diff --quiet src/science_tool/validate/checks/papers.py || echo "RESTORE FAILED"
```

Expected: 13 passed; no `RESTORE FAILED`.

- [ ] **Step 11: Commit**

```bash
git add science/src/science_tool/validate/checks/papers.py \
        science/tests/validate/test_checks_papers_background_reviews.py
git commit -m "feat(validate): promote the reviews-are-not-evidence guardrail to a canonical check"
```

---

### Task 3: Retire the sidecar — rule, non-execution, and the whole extension surface

**Files:**
- Modify: `science/src/science_tool/validate/runtime.py`, `runner.py`, `__init__.py`, `context.py`
- Modify: `science/src/science_tool/graph/health_checks/validate.py`
- Modify: `science/src/science_tool/project_artifacts/registry.yaml`, `cli.py`
- Modify: `science/src/science_tool/budget/registry.py`
- Modify: `science/tests/validate/test_context.py:24-26`
- Delete: `science/src/science_tool/project_artifacts/port_validate_sidecar.py`, `science/tests/test_cli_artifacts_port_validate_sidecar.py`
- Test: `science/tests/validate/test_sidecar_retirement.py`

**Interfaces:**
- Consumes: `RUNTIME_SECTION`, `RuntimeEmptyQualifiers`, `FindingProducer` from `runtime.py`.
- Produces: `RULE_PYTHON_SIDECAR_REMOVED`; `run()` without `enable_python_sidecar`.

This is one task, not two. The parameter removal and the hook removal are not independently green — a plan that commits a knowingly-red test is not a plan.

- [ ] **Step 1: Write the failing tests**

```python
"""Python validation sidecars are reported, never executed."""

from __future__ import annotations

import inspect
import sys
from pathlib import Path

from science_tool.validate.runner import run
from science_tool.validate.runtime import RULE_PYTHON_SIDECAR_REMOVED, RULE_SIDECAR_REMOVED

SENTINEL = "science_sidecar_executed_sentinel"

SIDECAR = f'''
import pathlib
pathlib.Path(__file__).parent.joinpath("{SENTINEL}").write_text("ran")
'''


def _project(tmp_path: Path) -> Path:
    (tmp_path / "science.yaml").write_text("name: fixture\n", encoding="utf-8")
    return tmp_path


def _run(root: Path):
    return run(root, strict=False, verbose=False)


def test_sidecar_file_yields_exactly_one_retirement_finding(tmp_path: Path) -> None:
    root = _project(tmp_path)
    (root / "validate_local.py").write_text(SIDECAR, encoding="utf-8")

    result = _run(root)

    matching = [f for f in result.results if f.rule_id == RULE_PYTHON_SIDECAR_REMOVED.id]
    assert len(matching) == 1
    assert matching[0].severity == "error"
    assert matching[0].subject.type == "project"


def test_sidecar_is_never_imported_or_executed(tmp_path: Path) -> None:
    root = _project(tmp_path)
    (root / "validate_local.py").write_text(SIDECAR, encoding="utf-8")

    _run(root)

    assert "validate_local" not in sys.modules
    assert not (root / SENTINEL).exists()


def test_python_and_legacy_sidecars_are_distinct_rules(tmp_path: Path) -> None:
    root = _project(tmp_path)
    (root / "validate_local.py").write_text(SIDECAR, encoding="utf-8")
    (root / "validate.local.sh").write_text("#!/bin/sh\n", encoding="utf-8")

    result = _run(root)

    rule_ids = {f.rule_id for f in result.results}
    assert RULE_PYTHON_SIDECAR_REMOVED.id in rule_ids
    assert RULE_SIDECAR_REMOVED.id in rule_ids
    assert RULE_PYTHON_SIDECAR_REMOVED.id != RULE_SIDECAR_REMOVED.id


def test_clean_project_has_no_retirement_finding(tmp_path: Path) -> None:
    result = _run(_project(tmp_path))

    assert not [f for f in result.results if f.rule_id == RULE_PYTHON_SIDECAR_REMOVED.id]


def test_hook_api_is_gone() -> None:
    import science_tool.validate as validate_pkg

    assert not hasattr(validate_pkg, "hook")


def test_run_has_no_sidecar_parameter() -> None:
    assert "enable_python_sidecar" not in inspect.signature(run).parameters
```

- [ ] **Step 2: Run to verify failure**

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

Empty identity qualifiers are correct: a project either carries the file or does not. Then extend the producer's `rules` tuple to `(RULE_CHECK_ERROR, RULE_SIDECAR_REMOVED, RULE_PYTHON_SIDECAR_REMOVED)`.

- [ ] **Step 4: Rewrite `run()` as straight-line code**

Delete from `runner.py`: `HookFn`, `_HOOK_NAMES`, `_HOOKS`, `_MISSING_MODULE`, `HookName` (both `TYPE_CHECKING` branches), `_PythonSidecarState`, `hook`, `_dispatch_hooks`, `_clear_hooks`, `_install_python_sidecar`, `_module_is_from_project`, `_legacy_sidecar_removed_result`, `_LEGACY_SIDECAR_PORTING_GUIDE`, and `enable_python_sidecar` from the signature. Remove the now-unused `importlib.util`, `os`, `sys`, `ModuleType`, `Literal`/`cast` imports if nothing else uses them.

There is no residual `try:`. `run()`'s body from the registry line through the return becomes:

```python
    registry = _validation_registry(ctx.project_root)
    producer_results: dict[str, FindingProducerResult] = {}
    notices: list[ValidationNotice] = []
    runtime_findings: list[AuditFinding] = []

    if (ctx.project_root / "validate.local.sh").exists():
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
    if (ctx.project_root / "validate_local.py").is_file():
        runtime_findings.append(
            RULE_PYTHON_SIDECAR_REMOVED.build(
                subject=ProjectSubject(),
                severity="error",
                qualifiers={},
                message=(
                    "validate_local.py is no longer executed; project checks belong "
                    f"in the toolkit. See {_SIDECAR_RETIREMENT_GUIDE}"
                ),
            )
        )

    for entry in checks:
        # ... unchanged check loop, including its per-check try/except ...

    runtime_result = FindingProducerResult(
        instrument=InstrumentResult.from_rows(runtime_findings),
    )
    producer_results[VALIDATION_RUNTIME_PRODUCER.producer_id] = validate_producer_result(
        registry, VALIDATION_RUNTIME_PRODUCER.producer_id, runtime_result
    )
    results = [
        finding
        for producer_result in producer_results.values()
        for finding in producer_result.instrument.rows
    ]
    run_result = _tally(
        results, producer_results, tuple(notices), registry, checks, skipped_checks, profile
    )
    try:
        tier = resolve_gate_tier(fail_on, ctx.manifest)
    except ValueError as exc:
        raise ValidateContextError(str(exc)) from exc
    return replace(run_result, gate_tier=tier, gated=tuple(gated_findings(results, tier)))
```

The only remaining `try:` blocks are the per-check exception handler and the `resolve_gate_tier` conversion. The `run_result: RunResult | None = None` pre-declaration is no longer needed. Add:

```python
_SIDECAR_RETIREMENT_GUIDE = "docs/migration/2026-05-19-validate-local-sh-porting-guide.md"
```

- [ ] **Step 5: Drop the `hook` export and fix the production caller**

Remove `hook` from the `runner` import and `__all__` in `science/src/science_tool/validate/__init__.py`. Remove the `enable_python_sidecar=False,` argument from the `run(...)` call in `science/src/science_tool/graph/health_checks/validate.py`.

- [ ] **Step 6: Delete the stale context fields**

In `context.py`, delete the `papers_dir`, `provenance_dir`, and `themes_dir` declarations and their `from_project_root` assignments. Delete the matching assertions at `science/tests/validate/test_context.py:24-26`. A field whose sole consumer is a test pinning it to a wrong value is how the drift stayed invisible.

- [ ] **Step 7: Delete the porting command**

```bash
git rm science/src/science_tool/project_artifacts/port_validate_sidecar.py
git rm science/tests/test_cli_artifacts_port_validate_sidecar.py
```

Remove its click command and lazy import from `project_artifacts/cli.py`, and its `"single generated-sidecar path"` entry from `budget/registry.py`. Do **not** touch `science/tests/test_query_iter_sidecars.py` — "sidecar" there is query iteration, an unrelated concept.

- [ ] **Step 8: Replace the advertised extension protocol**

In `project_artifacts/registry.yaml`, replace the `validate.sh` artifact's `extension_protocol` block with:

```yaml
    extension_protocol:
      kind: none
      rationale: >
        science validate never executes project-authored code. Project checks
        belong in the toolkit's canonical check set.
```

`extension_protocol` is a **required** field on `Artifact`, and `ExtensionKind.NONE` is a valid pairing for `consumer: direct_execute` — deleting the block outright fails schema validation.

**Do not touch `version`, `current_hash`, `previous_hashes`, or `migrations`.** The `validate.sh` body does not change, so `current_hash` is unchanged, and the registry's `_no_duplicate_hash` validator rejects a `current_hash` that also appears in `previous_hashes`. The registry versions artifact *bytes* and has no vocabulary for a metadata-only revision; introducing one is out of scope.

- [ ] **Step 9: Run the affected tests**

```bash
cd science && uv run --frozen pytest \
  tests/validate/test_sidecar_retirement.py \
  tests/validate/test_context.py \
  tests/test_validate_sh_section_8.py \
  tests/test_budget_regression.py \
  tests/test_registry_schema.py -v
```

Expected: all pass, including `test_run_has_no_sidecar_parameter`.

- [ ] **Step 10: Lint, typecheck, commit**

```bash
cd science && uv run ruff check && uv run pyright
git add -A science/
git commit -m "feat(validate)!: retire the project Python validation sidecar"
```

---

### Task 4: Documentation and regenerated mirrors

**Files:**
- Modify: `docs/conventions/validate.md`, `docs/migration/2026-05-19-validate-local-sh-porting-guide.md`, `docs/migration/managed-artifacts-template.md`
- Regenerate: `skills/generated/…`

- [ ] **Step 1: Update `docs/conventions/validate.md`**

Remove the Python-sidecar discovery contract and the `SCIENCE_VALIDATE_DISABLE_SIDECAR` row from the environment-variable table. State that `science validate` never executes project code, and that a `validate_local.py` present in a project produces a `validate.python-sidecar-removed` error.

- [ ] **Step 2: Retarget the porting guide**

Rewrite `docs/migration/2026-05-19-validate-local-sh-porting-guide.md` from "port your shell sidecar to Python" to "sidecars are retired." It must answer: where a reusable policy check goes (a toolkit check — open a design conversation), and where a genuinely project-specific check goes (a project-owned command the project runs itself, with nothing enforcing it).

- [ ] **Step 3: Fix `docs/migration/managed-artifacts-template.md`**

Not historical, and still instructs projects to migrate logic *into* a sidecar (~line 157) and references `validate.local.sh` (~line 262). Leaving it is an active instruction to recreate what this work removes.

- [ ] **Step 4: Regenerate committed mirrors**

Never hand-edit files under `skills/generated/`.

```bash
cd science && uv run --frozen science agents generate
git diff --stat ../skills/generated/
```

The command is `science agents generate` — `science skills` has only `coverage`, `curate`, `lint`, and `sources`, none of which regenerate the mirror.

- [ ] **Step 5: Confirm no stale instructions remain**

```bash
cd ~/d/science/.worktrees/sidecar-retirement
rg -n --glob '!docs/plans/**' --glob '!**/historical/**' \
   'validate_local|SCIENCE_VALIDATE_DISABLE_SIDECAR|@hook' docs/ templates/ skills/
```

Expected: only retirement-context mentions in the porting guide. No instruction to create a sidecar.

- [ ] **Step 6: Commit**

```bash
git add docs/ skills/
git commit -m "docs(validate): retarget sidecar documentation to retirement"
```

---

### Task 5: Migrate `meta/` on this branch

**Files:**
- Delete: `meta/validate_local.py`
- Modify: `meta/evidence/README.md`, `meta/evidence/t034-causal-graph-contract.md`, `meta/entities/questions/0010-causal-graph-construction-pipeline.md`, `meta/src/t034_validator/__main__.py`

`meta/` is an in-repository consumer with an editable toolkit source. It must move **on this branch, before the push** — pushing a toolkit that reports `validate.python-sidecar-removed` while the repo still carries the sidecar it reports on would contradict the atomicity claim.

- [ ] **Step 1: Delete the sidecar**

```bash
cd ~/d/science/.worktrees/sidecar-retirement && git rm meta/validate_local.py
```

- [ ] **Step 2: Repair every active t034 reference**

`meta/AGENTS.md` makes **no** t034 or `validate_local` claim — do not edit it. The live stale references are:

| file | current claim |
|---|---|
| `meta/evidence/README.md:6-7` | "`validate.sh` runs `python -m t034_validator evidence/` via `validate.local.sh`" — wrong on both counts |
| `meta/evidence/t034-causal-graph-contract.md` | references `validate_local` |
| `meta/entities/questions/0010-causal-graph-construction-pipeline.md` | references `validate_local` |
| `meta/src/t034_validator/__main__.py` docstring | "CLI for the t034 validator. Invoked from validate.local.sh." |

Leave `meta/tasks/done/2026-06.md` alone — a completed task record is history.

Each replacement states the direct invocation and that nothing enforces it:

```
Run t034 validation directly: `uv run python -m t034_validator evidence/`.
It is no longer part of `science validate`; nothing enforces that it runs.
```

- [ ] **Step 3: Verify the t034 CLI standalone**

The directory argument is required — `__main__.main` returns 2 on `len(argv) != 2`.

```bash
cd ~/d/science/.worktrees/sidecar-retirement/meta && uv run python -m t034_validator evidence/
echo "exit=$?"
```

Expected: a `t034: N payload(s), 0 error(s), 0 load error(s)` summary and `exit=0`.

- [ ] **Step 4: Verify meta validates cleanly**

```bash
cd ~/d/science/.worktrees/sidecar-retirement/meta
uv run --frozen science validate --all --strict --format json > /tmp/meta-after.json
status=$?
echo "validator exit=$status"
python3 - <<'PY'
import json
d = json.load(open("/tmp/meta-after.json"))
print(d["summary"])
rules = {r.get("rule") for r in d["results"]}
assert "validate.python-sidecar-removed" not in rules, "sidecar finding still present"
assert not any(str(r or "").startswith("papers.background-review") for r in rules), rules
print("OK")
PY
```

Expected: `validator exit=0`, `OK`. Capture the status immediately — never `| head` before reading `$?`, which reports the pipe's last command.

- [ ] **Step 5: Commit**

```bash
cd ~/d/science/.worktrees/sidecar-retirement
git add -A meta/
git commit -m "chore(meta): drop the validation sidecar and invoke t034 directly"
```

---

### Task 6: Full-suite and canonical parity verification

**Files:** none modified.

- [ ] **Step 1: Full toolkit suite**

```bash
cd science && uv run --frozen pytest
```

Run with a 600000 ms tool timeout. Expected: all pass.

- [ ] **Step 2: Model suite and opt-in markers**

```bash
cd science/model && uv run --frozen pytest
cd science && uv run --frozen pytest -m snapshot
cd science && uv run --frozen pytest -m real_projects
```

- [ ] **Step 3: Build the after-toolkit environment and capture after-states**

Task 1 never produced these; they must be created here.

```bash
set -e
uv venv ~/scratch/sidecar-baselines/after-venv
~/scratch/sidecar-baselines/after-venv/bin/pip install -e ~/d/science/.worktrees/sidecar-retirement/science
BIN=~/scratch/sidecar-baselines/after-venv/bin/science
declare -A ROOTS=(
  [evolution]=~/d/cancer/mechanisms/evolution
  [protein-landscape]=~/d/protein-landscape
  [science-meta]=~/d/science/.worktrees/sidecar-retirement/meta
  [health-meta]=~/d/health/meta
)
for name in "${!ROOTS[@]}"; do
  ( cd "${ROOTS[$name]}" && "$BIN" validate --all --strict --format json ) \
    > ~/scratch/sidecar-baselines/"$name"-after.json
  echo "$name captured"
done
```

- [ ] **Step 4: Diff finding-by-finding, failing on any missing file**

```bash
python3 - <<'PY'
import json, sys
from pathlib import Path

base = Path.home() / "scratch/sidecar-baselines"
names = ["evolution", "protein-landscape", "science-meta", "health-meta"]
NEW_PREFIXES = ("papers.background-review", "validate.python-sidecar-removed")
failed = False

def rows(p: Path):
    if not p.exists():
        sys.exit(f"FAIL missing required file: {p}")   # never SKIP
    return json.loads(p.read_text())["results"]

def ident(rs):
    return sorted(
        (r.get("rule"), r.get("path"), r.get("message"))
        for r in rs
        if not str(r.get("rule") or "").startswith(NEW_PREFIXES)
    )

for n in names:
    before = ident(rows(base / f"{n}-canonical.json"))
    after = ident(rows(base / f"{n}-after.json"))
    if before == after:
        print(f"{n}: MATCH ({len(before)} rows)")
    else:
        failed = True
        print(f"{n}: DIFF")
        for row in set(before) ^ set(after):
            print("   ", row)

sys.exit(1 if failed else 0)
PY
```

Expected: `MATCH` for all four, exit 0. Any missing file is a hard failure, never a skip.

- [ ] **Step 5: Confirm zero new warnings, and check notices out-of-band**

Per design §5.2 the corpus is compliant.

```bash
python3 - <<'PY'
import json, sys
from pathlib import Path
base = Path.home() / "scratch/sidecar-baselines"
for n in ("evolution", "health-meta"):
    rs = json.loads((base / f"{n}-after.json").read_text())["results"]
    warns = [r for r in rs if str(r.get("rule") or "").startswith("papers.background-review")]
    print(n, "background-review warnings:", len(warns))
    if warns:
        sys.exit(f"FAIL {n}: expected zero; corpus changed or roots are wrong")
PY
```

**Notices are not carried in `--format json`.** Verify them through verbose text instead:

```bash
BIN=~/scratch/sidecar-baselines/after-venv/bin/science
( cd ~/d/cancer/mechanisms/evolution && "$BIN" validate --all --strict --verbose ) \
  | rg 'no status:background papers'
( cd ~/d/health/meta && "$BIN" validate --all --strict --verbose ) \
  | rg '9 status:background paper'
```

Expected: evolution matches the no-background notice (all 15 papers are active); health/meta matches the 9-paper, 0-violation notice.

If either produces a **warning**, stop. Either the corpus changed since 2026-07-29 or the roots are wrong. Do not adjust the expectation to match the output.

- [ ] **Step 6: Record results — no code change**

---

### Task 7: Approval gate, then publish

**Files:** none.

A consumer cannot resolve an unpushed revision, so this must precede Tasks 8–10. It is also the one irreversible step in the plan.

- [ ] **Step 1: Obtain explicit approval to merge and push**

Present the Task 6 parity table and ask for a go/no-go on pushing `origin/main`. **Do not proceed without an explicit yes.** Prior approval of the design is not approval of the push.

- [ ] **Step 2: Merge on a verified branch**

This repo's `main` checkout floats because it is Dropbox-synced.

```bash
cd ~/d/science
git branch --show-current   # must print: main — stop if it does not
git merge --no-ff sidecar-retirement
```

- [ ] **Step 3: Push and confirm reachability**

```bash
git push origin main
git ls-remote origin main
```

Expected: remote SHA matches local `main`. Record it — Tasks 8–10 pin to it.

---

### Task 8: Migrate `~/d/health/meta` atomically

**Files:** `pyproject.toml:13`, `uv.lock`, `AGENTS.md`; delete `validate_local.py`

- [ ] **Step 1: Work in an isolated worktree**

```bash
cd ~/d/health && git worktree add .worktrees/sidecar-retirement -b sidecar-retirement
cd .worktrees/sidecar-retirement && git branch --show-current
```

- [ ] **Step 2: Update the explicit pin and relock**

Replace `rev = "3b72db60b8d591cf3dbac8ae25ca194f6cda9c8b"` in `[tool.uv.sources]` with the Task 7 SHA, then:

```bash
uv lock && uv sync
rg -A2 '^name = "science"' uv.lock
```

Expected: the `source = { git = ... #<sha> }` line shows the Task 7 SHA.

- [ ] **Step 3: Delete the sidecar and update `AGENTS.md`**

```bash
git rm meta/validate_local.py 2>/dev/null || git rm validate_local.py
```

Record in `AGENTS.md` that the reviews-are-not-evidence guardrail is now a toolkit check the project no longer owns.

- [ ] **Step 4: Verify, capturing status before parsing**

```bash
uv run --frozen science validate --all --strict --format json > /tmp/hm-after.json
status=$?
echo "validator exit=$status"
python3 - <<'PY'
import json
d = json.load(open("/tmp/hm-after.json"))
print(d["summary"])
rules = {r.get("rule") for r in d["results"]}
assert "validate.python-sidecar-removed" not in rules
assert not any(str(r or "").startswith("papers.background-review") for r in rules), rules
print("OK")
PY
```

Expected: `validator exit=0`, `OK`. The nine background papers are cited under `source_refs`, not `evidence_refs`, and both `paper:Tasci2022` provenance records already carry `evidence_tier: background` and `review_typed_source: true`.

- [ ] **Step 5: Commit atomically, merge, clean up**

```bash
git add -A && git commit -m "chore: adopt toolkit background-review check and drop the validation sidecar"
cd ~/d/health && git branch --show-current   # verify before merging
git merge --no-ff sidecar-retirement
git worktree remove .worktrees/sidecar-retirement
```

This repo has **no GitHub remote** — commit and merge only, never push.

---

### Task 9: Migrate `~/d/cancer/mechanisms/evolution` atomically

**Files:** `uv.lock:3062`, `AGENTS.md`; delete `validate_local.py`

Unqualified Git source; the revision lives only in `uv.lock`, currently `ed6b50dc`.

- [ ] **Step 1: Isolated worktree**

```bash
cd ~/d/cancer && git worktree add .worktrees/sidecar-retirement -b sidecar-retirement
cd .worktrees/sidecar-retirement/mechanisms/evolution
```

- [ ] **Step 2: Relock to the Task 7 SHA**

```bash
uv lock --upgrade-package science && uv sync
rg -A2 '^name = "science"' uv.lock
```

- [ ] **Step 3: Delete the sidecar and update `AGENTS.md`**

```bash
git rm validate_local.py
```

- [ ] **Step 4: Run the exact original command that crashed**

```bash
uv run --frozen science validate --all --strict --format json > /tmp/evo-after.json
status=$?
echo "validator exit=$status"
python3 - <<'PY'
import json
d = json.load(open("/tmp/evo-after.json"))
print(d["summary"])
rules = {r.get("rule") for r in d["results"]}
assert "validate.python-sidecar-removed" not in rules
assert not any(str(r or "").startswith("papers.background-review") for r in rules), rules
print("OK")
PY
```

Expected: `validator exit=0`, `OK`, no traceback. This is the Task 1 Step 2 reproduction now resolved.

- [ ] **Step 5: Confirm the notice out-of-band**

```bash
uv run --frozen science validate --all --strict --verbose | rg 'no status:background papers'
```

Expected: a match — all 15 papers are active, so a notice and zero warnings.

- [ ] **Step 6: Commit atomically, merge, clean up**

```bash
git add -A && git commit -m "chore: adopt toolkit background-review check and drop the validation sidecar"
cd ~/d/cancer && git branch --show-current   # Dropbox-synced; verify before merging
git merge --no-ff sidecar-retirement
git worktree remove .worktrees/sidecar-retirement
```

---

### Task 10: Migrate `~/d/protein-landscape` atomically

**Files:** `uv.lock:4412`, `AGENTS.md`; delete `validate_local.py`

Its check is **not** promoted — the expensive-artifact check becomes a project-owned command with nothing enforcing it (design §4).

- [ ] **Step 1: Isolated worktree, relock**

```bash
cd ~/d/protein-landscape && git worktree add .worktrees/sidecar-retirement -b sidecar-retirement
cd .worktrees/sidecar-retirement
uv lock --upgrade-package science && uv sync
rg -A2 '^name = "science"' uv.lock
```

- [ ] **Step 2: Delete the wrapper only**

The standalone checker **already exists** at `code/scripts/check_expensive_artifacts.py` (6 KB). `validate_local.py` is a thin hook wrapper around it. Delete the wrapper; **do not** create a duplicate script.

```bash
git rm validate_local.py
```

- [ ] **Step 3: Document the loss in `AGENTS.md`**

State plainly: this check no longer runs as part of `science validate`, it is not in `--format json` output, and **nothing enforces that it runs**. Give the exact command:

```
uv run --frozen python code/scripts/check_expensive_artifacts.py
```

- [ ] **Step 4: Confirm the standalone checker runs**

```bash
uv run --frozen python code/scripts/check_expensive_artifacts.py
echo "checker exit=$?"
```

- [ ] **Step 5: Verify validation**

```bash
uv run --frozen science validate --all --strict --format json > /tmp/pl-after.json
status=$?
echo "validator exit=$status"
python3 -c "
import json; d=json.load(open('/tmp/pl-after.json')); print(d['summary'])
assert 'validate.python-sidecar-removed' not in {r.get('rule') for r in d['results']}
print('OK')"
```

Expected: `validator exit=0`, `OK`, no traceback — the crash in the method-slice inventory is resolved.

- [ ] **Step 6: Commit atomically, merge, clean up**

```bash
git add -A && git commit -m "chore: drop the validation sidecar; run artifact checks standalone"
cd ~/d/protein-landscape && git branch --show-current
git merge --no-ff sidecar-retirement
git worktree remove .worktrees/sidecar-retirement
```

---

## Verification Checklist

Design §5.3 coverage:

| § | Requirement | Task |
|---|---|---|
| 5.3.1 | exactly one `validate.python-sidecar-removed`, valid JSON | 3 |
| 5.3.2 | never imported or executed (`sys.modules` + sentinel) | 3 |
| 5.3.3 | project-authored `FindingRule` cannot enter the registry | pre-existing; Task 6 full suite |
| 5.3.4 | the two sidecar rules are distinct | 3 |
| 5.3.5 | three rules fire; both typing conditions yield two findings | 2 |
| 5.3.6 | check present in `full` and `commit` profiles, not `--all`-gated | 2 |
| 5.3.7 | the check can fail — mutate, confirm red, restore green | 2, steps 9–10 |

**On §5.3.7:** §5.2 means the real corpus cannot falsify this check — it is compliant. Task 2's fixtures are the only falsification available, which is why steps 9 and 10 are executable steps rather than a closing remark.

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
- **Full suite is ~10k tests / 2-3 min** — longer than the default 120s timeout. Run scoped selections per task; reserve the full run for Task 6 with an explicit long timeout.
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

Both must hold before any further verification. Neither is optional. The
recorded reconciliation target is
`a7f3337e98515bc289781ef0a1eae7b9c2fe73a5`; a different remote value is a
hard stop for a fresh reassessment, not permission to proceed against a moving
target.

- [ ] **P1: Freshly fetch and record the reconciled `origin/main` SHA.**

```bash
set -euo pipefail
toolkit_root=~/d/science/.worktrees/sidecar-retirement
recorded_origin_main_sha=a7f3337e98515bc289781ef0a1eae7b9c2fe73a5
git -C "$toolkit_root" fetch --prune origin
actual_origin_main_sha=$(git -C "$toolkit_root" rev-parse origin/main)
test "$actual_origin_main_sha" = "$recorded_origin_main_sha" || {
  echo "HARD STOP: origin/main is $actual_origin_main_sha; reassess before continuing"
  exit 1
}
printf '%s\n' "$recorded_origin_main_sha" > "$toolkit_root/.superpowers/sdd/2026-07-29-validation-sidecar-retirement-implementation/reconciled-origin-main.sha"
```

- [ ] **P2: Rebase `sidecar-retirement` onto that exact remote commit before verification.**

During conflict resolution, retain current main's deferred classification and
tests for `findings migrate-acceptances`, and retain this feature's removal of
`project artifacts port-validate-sidecar` plus the audited partition of
`69 budgeted / 121 exempt / 102 deferred`. The only expected overlapping files
are `science/src/science_tool/budget/registry.py` and
`science/tests/test_budget_boundary.py`.

```bash
set -euo pipefail
toolkit_root=~/d/science/.worktrees/sidecar-retirement
recorded_origin_main_sha=$(cat "$toolkit_root/.superpowers/sdd/2026-07-29-validation-sidecar-retirement-implementation/reconciled-origin-main.sha")
test "$recorded_origin_main_sha" = a7f3337e98515bc289781ef0a1eae7b9c2fe73a5 || {
  echo "HARD STOP: recorded origin/main requires reassessment"
  exit 1
}
set +e
git -C "$toolkit_root" rebase "$recorded_origin_main_sha"
rebase_status=$?
set -e
if [ "$rebase_status" -ne 0 ]; then
  mapfile -t unmerged_paths < <(git -C "$toolkit_root" diff --name-only --diff-filter=U)
  expected_paths=(
    science/src/science_tool/budget/registry.py
    science/tests/test_budget_boundary.py
  )
  test "${unmerged_paths[*]}" = "${expected_paths[*]}" || {
    printf 'HARD STOP: unexpected rebase conflicts: %s\n' "${unmerged_paths[*]}"
    exit 1
  }
  printf '%s\n' 'PAUSE: resolve the two verified conflicts before continuing.'
  exit 2
fi
```

When the command pauses, make the semantic resolution manually — do not stage
conflict-marker text and do not use `--ours`/`--theirs` for either whole file.
Use the current-main version as the base, then apply precisely this feature
delta: remove the `project artifacts port-validate-sidecar` classification and
its test/history accounting. In `registry.py`, retain current main's
`DEFERRED["findings migrate-acceptances"]` entry with growth reason
`"one output row per configured validation acceptance"`. In
`test_budget_boundary.py`, retain its Plan 3 coverage and set the partition to
exactly `69` budgeted, `121` exempt, and `102` deferred. Apply those two
semantic edits in the paused worktree (for example with `apply_patch`), then
run this continuation block.

```bash
set -euo pipefail
toolkit_root=~/d/science/.worktrees/sidecar-retirement
test -n "$(git -C "$toolkit_root" rebase --show-current-patch)" || {
  echo "HARD STOP: no paused rebase to continue"; exit 1;
}
git -C "$toolkit_root" diff --check
if rg -n '^(<<<<<<<|=======|>>>>>>>)' \
  "$toolkit_root/science/src/science_tool/budget/registry.py" \
  "$toolkit_root/science/tests/test_budget_boundary.py"; then
  echo "HARD STOP: conflict markers remain"
  exit 1
fi
( cd "$toolkit_root/science" && uv run --frozen python - <<'PY'
import click
from science_tool.budget.registry import BUDGETS, DEFERRED, EXEMPTIONS
from science_tool.cli import main

assert DEFERRED["findings migrate-acceptances"].growth_reason == "one output row per configured validation acceptance"
assert "project artifacts port-validate-sidecar" not in BUDGETS | EXEMPTIONS | DEFERRED
assert (len(BUDGETS), len(EXEMPTIONS), len(DEFERRED)) == (69, 121, 102)

def leaves(command: click.Command, prefix: tuple[str, ...] = ()) -> set[str]:
    if isinstance(command, click.Group):
        return {leaf for name in command.list_commands(click.Context(command)) for leaf in leaves(command.get_command(click.Context(command), name), prefix + (name,))}
    return {" ".join(prefix)}

assert "project artifacts port-validate-sidecar" not in leaves(main)
PY
)
( cd "$toolkit_root/science" && uv run --frozen pytest -q \
  tests/test_budget_boundary.py::test_every_leaf_command_is_classified \
  tests/test_budget_boundary.py::test_classification_partition_has_the_audited_cardinality )
git -C "$toolkit_root" add \
  science/src/science_tool/budget/registry.py \
  science/tests/test_budget_boundary.py
for resolved_path in \
  science/src/science_tool/budget/registry.py \
  science/tests/test_budget_boundary.py; do
  test "$(git -C "$toolkit_root" diff --cached --name-only -- "$resolved_path")" = "$resolved_path" || {
    echo "HARD STOP: resolved path is not staged: $resolved_path"; exit 1;
  }
done
test -z "$(git -C "$toolkit_root" diff --name-only --diff-filter=U)" || {
  echo "HARD STOP: unmerged paths remain after staging"; exit 1;
}
if rg -n '^(<<<<<<<|=======|>>>>>>>)' \
  "$toolkit_root/science/src/science_tool/budget/registry.py" \
  "$toolkit_root/science/tests/test_budget_boundary.py"; then
  echo "HARD STOP: conflict markers remain after staging"
  exit 1
fi
GIT_EDITOR=true git -C "$toolkit_root" rebase --continue
test -z "$(git -C "$toolkit_root" diff --name-only --diff-filter=U)" || {
  echo "HARD STOP: unresolved rebase paths remain"; exit 1;
}
( cd "$toolkit_root/science" && uv run --frozen python - <<'PY'
import click
from science_tool.budget.registry import BUDGETS, DEFERRED, EXEMPTIONS
from science_tool.cli import main

assert DEFERRED["findings migrate-acceptances"].growth_reason == "one output row per configured validation acceptance"
assert "project artifacts port-validate-sidecar" not in BUDGETS | EXEMPTIONS | DEFERRED
assert (len(BUDGETS), len(EXEMPTIONS), len(DEFERRED)) == (69, 121, 102)

def leaves(command: click.Command, prefix: tuple[str, ...] = ()) -> set[str]:
    if isinstance(command, click.Group):
        return {leaf for name in command.list_commands(click.Context(command)) for leaf in leaves(command.get_command(click.Context(command), name), prefix + (name,))}
    return {" ".join(prefix)}

assert "project artifacts port-validate-sidecar" not in leaves(main)
PY
)
( cd "$toolkit_root/science" && uv run --frozen pytest -q \
  tests/test_budget_boundary.py::test_every_leaf_command_is_classified \
  tests/test_budget_boundary.py::test_classification_partition_has_the_audited_cardinality )
```

Expected: the rebase is clean after the explicit two-file resolution, the
affected budget tests pass, and their audited partition remains
`69 budgeted / 121 exempt / 102 deferred`.

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

### Task 1: Capture all baselines with one pinned toolkit revision (historical evidence)

**Files:** none in-repo. Baselines land in `~/scratch/sidecar-baselines/`.

**Interfaces:**
- Produces: five historical baseline JSON files. The `b4af2a16` artifacts are
  preserved as evidence of completed Task 1, but are superseded as parity
  targets after the required rebase; Task 6 recaptures the four canonical
  reports from `a7f3337e` and identical pinned consumer snapshots.

**Historical record — do not rerun this completed task.** Its original
`~/scratch/sidecar-baselines/` files must never be overwritten. The separate
health/meta own-revision report remains informational and is not a parity
target.

Design §5.1: the four projects sit in three different states, and their installed revisions differ (`3b72db60` vs `ed6b50dc`). Comparing each project's own installed revision to a post-retirement toolkit would conflate this change with everything between those revisions. **All canonical baselines use one revision: post–Plan 3 `main`, pre-retirement.**

- [ ] **Step 1: Build the pinned baseline environment**

`uv venv` creates **no `bin/pip`** — install through `uv pip install --python`.

```bash
set -e
mkdir -p ~/scratch/sidecar-baselines
git -C ~/d/science rev-parse origin/main > ~/scratch/sidecar-baselines/BASELINE_SHA
uv venv ~/scratch/sidecar-baselines/venv
uv pip install --python ~/scratch/sidecar-baselines/venv/bin/python \
  "science @ git+https://github.com/khughitt/science.git@$(cat ~/scratch/sidecar-baselines/BASELINE_SHA)#subdirectory=science"
test -x ~/scratch/sidecar-baselines/venv/bin/science || { echo "FAIL: science not installed"; exit 1; }
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
( cd ~/d/health/meta && .venv/bin/science validate --all --strict --format json \
    --output ~/scratch/sidecar-baselines/health-meta-own-rev.json )
status=$?
test "$status" -le 1 || { echo "FAIL: validator crashed, exit $status"; exit 1; }
test -s ~/scratch/sidecar-baselines/health-meta-own-rev.json || { echo "FAIL: empty"; exit 1; }
```

Expected: exit 0, `summary.warnings == 153`, `summary.infos == 0`, and **zero** guardrail rows — `doc/papers/` holds only an `archive/` subdirectory.

- [ ] **Step 4: Capture the four canonical baselines — the parity targets**

The sidecar-disabling env var still exists at this point. This is the last moment it can be used.

Use `--output`, not stdout JSON. Normal JSON output is **budget-capped** — health/meta's baseline showed 40 rows rendered and 113 omitted — so a stdout capture cannot support finding-by-finding parity. `--output PATH` writes "the complete, unbudgeted validation report."

Names are explicit: `~/d/science/meta` and `~/d/health/meta` both basename to `meta`.

```bash
BIN=~/scratch/sidecar-baselines/venv/bin/science
OUT=~/scratch/sidecar-baselines
declare -A ROOTS=(
  [evolution]=~/d/cancer/mechanisms/evolution
  [protein-landscape]=~/d/protein-landscape
  [science-meta]=~/d/science/meta
  [health-meta]=~/d/health/meta
)
for name in "${!ROOTS[@]}"; do
  ( cd "${ROOTS[$name]}" && SCIENCE_VALIDATE_DISABLE_SIDECAR=1 "$BIN" validate \
      --all --strict --format json --output "$OUT/$name-canonical.json" )
  status=$?
  # Canonical baselines carry pre-existing findings; 0 and 1 are both acceptable
  # here, but a crash (2+) is not.
  if [ "$status" -gt 1 ]; then echo "FAIL $name: validator exited $status"; exit 1; fi
  test -s "$OUT/$name-canonical.json" || { echo "FAIL $name: empty report"; exit 1; }
  echo "$name captured (exit $status)"
done
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
( cd ~/d/science/.worktrees/sidecar-retirement/science && uv run --frozen pytest tests/validate/test_checks_papers_background_reviews.py -v )
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
( cd ~/d/science/.worktrees/sidecar-retirement/science && uv run --frozen pytest tests/validate/test_checks_papers_background_reviews.py -v )
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

- [ ] **Step 8: Update the existing `check_papers` consumer test**

`tests/validate/test_checks_papers_gap_analysis.py:64` does `results = list(check_papers(_ctx(tmp_path)))` and asserts on that list. Step 5 makes `check_papers` yield an additional notice, so that assertion changes. Update it to filter to the observation it actually cares about rather than pinning the total count.

- [ ] **Step 9: Run, lint, typecheck**

```bash
( cd ~/d/science/.worktrees/sidecar-retirement/science && \
  uv run --frozen pytest tests/validate/test_checks_papers_background_reviews.py \
                         tests/validate/test_checks_papers_gap_analysis.py \
                         tests/validate/test_checks_papers_datasets.py -v && \
  uv run ruff check && uv run pyright )
```

Expected: 13 new tests pass, the two existing papers modules stay green, ruff and pyright clean. If `test_check_runs_in_every_profile` fails, `check_papers` or the `papers` section has been added to `_COMMIT_EXCLUDED_SECTIONS` / `_COMMIT_EXCLUDED_FUNCTIONS` in `runner.py` — remove it.

- [ ] **Step 10: Prove the check can fail — mutate via the patch tool**

§5.2 says the live corpus is compliant, so these fixtures are the only falsification available. Verify they are load-bearing.

Use the editing tool (`apply_patch` / `Edit`) for both the mutation and the revert — never `cp`/`sed`/`python -c` rewriting of a tracked file. In `papers.py`, change:

```python
        for kind in ("theme", "report", "hypothesis")
```

to:

```python
        for kind in ()
```

Then run:

```bash
( cd ~/d/science/.worktrees/sidecar-retirement/science && \
  uv run --frozen pytest tests/validate/test_checks_papers_background_reviews.py -q )
```

Expected: **FAILURES** in `test_background_paper_in_evidence_refs_warns`, `test_unindented_list_items_are_parsed`, `test_hyphenated_and_dotted_paper_ids`, `test_duplicate_citation_dedupes_file_wide`, `test_check_is_not_gated_on_include_all`. If any still passes, that fixture is not exercising the citation-root walk.

- [ ] **Step 11: Revert via the patch tool and confirm green**

Apply the inverse edit — `for kind in ()` back to `for kind in ("theme", "report", "hypothesis")` — then:

```bash
( cd ~/d/science/.worktrees/sidecar-retirement && \
  git diff --quiet science/src/science_tool/validate/checks/papers.py \
    && echo "REVERT MATCHES HEAD (expected only if already committed)" ; \
  cd science && uv run --frozen pytest tests/validate/test_checks_papers_background_reviews.py -q )
```

Expected: 13 passed. Confirm by inspection that the only diff versus the pre-mutation state is nil — the mutation must leave no residue.

- [ ] **Step 12: Commit**

Step 8 modified `test_checks_papers_gap_analysis.py`; stage it here. Left unstaged it would be swept up by Task 3's `git add -A science/` and land in the wrong commit.

```bash
git add science/src/science_tool/validate/checks/papers.py \
        science/tests/validate/test_checks_papers_background_reviews.py \
        science/tests/validate/test_checks_papers_gap_analysis.py
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
- Modify (test migration, Step 9): `science/tests/validate/test_runner.py`, `test_parity_corpus.py`, `test_parity_with_sidecar.py`, `test_legacy_precedence.py`, `test_checks_dataset_metadata.py`, `test_checks_aggregation_support.py`, `test_checks_benchmark_metadata.py`, `test_checks_dataset_capabilities.py`; `science/tests/test_registry_loader.py`, `science/tests/test_validate_sh_section_8.py`
- Delete: `science/src/science_tool/project_artifacts/port_validate_sidecar.py`, `science/tests/test_cli_artifacts_port_validate_sidecar.py`
- Test: `science/tests/validate/test_sidecar_retirement.py`
- **Not** in this task: `science/tests/test_command_docs.py` — it pins documentation strings, and moves with the documentation in Task 4.

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


def test_cli_emits_valid_json_with_one_retirement_rule(tmp_path: Path) -> None:
    """Design §5.3.1 is about CLI JSON, not run() — the crash was a CLI traceback."""
    import json

    from click.testing import CliRunner

    from science_tool.validate.cli import validate_cmd

    root = _project(tmp_path)
    (root / "validate_local.py").write_text(SIDECAR, encoding="utf-8")
    report = tmp_path / "report.json"

    result = CliRunner().invoke(
        validate_cmd,
        ["--project-root", str(root), "--format", "json", "--output", str(report)],
    )

    assert result.exception is None or isinstance(result.exception, SystemExit)
    assert "Traceback" not in result.output
    payload = json.loads(report.read_text(encoding="utf-8"))
    rules = [r.get("rule") for r in payload["results"]]
    assert rules.count(RULE_PYTHON_SIDECAR_REMOVED.id) == 1
```

`--output` writes the complete, unbudgeted report; plain stdout JSON is budget-capped and would make the count unreliable.

- [ ] **Step 2: Run to verify failure**

```bash
( cd ~/d/science/.worktrees/sidecar-retirement/science && uv run --frozen pytest tests/validate/test_sidecar_retirement.py -v )
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

Delete from `runner.py`: `HookFn`, `_HOOK_NAMES`, `_HOOKS`, `_MISSING_MODULE`, `HookName` (both `TYPE_CHECKING` branches), `_PythonSidecarState`, `hook`, `_dispatch_hooks`, `_clear_hooks`, `_install_python_sidecar`, `_module_is_from_project`, `_legacy_sidecar_removed_result`, and `enable_python_sidecar` from the signature. Remove the now-unused `importlib.util`, `os`, `sys`, `ModuleType`, `Literal`/`cast` imports if nothing else uses them.

**Keep `_LEGACY_SIDECAR_PORTING_GUIDE` and the legacy message byte-for-byte.** Only the `_legacy_sidecar_removed_result()` wrapper goes; its message string is inlined unchanged. Do not introduce a second guide constant — one constant, both messages.

The current text at `runner.py:320` is:

```python
message = f"validate.local.sh is no longer supported; migrate it using {_LEGACY_SIDECAR_PORTING_GUIDE}"
```

Four places pin that exact string, and this task has no business changing the output contract of a rule it is not retiring:

- `tests/validate/test_parity_with_sidecar.py:27` — `_REMOVED_MESSAGE`
- `tests/validate/snapshots/json_default.json:12`
- `tests/validate/snapshots/text_default.txt:5`
- the bash `validate.local.sh` implementation the parity tests compare against

Rewording it to "see" would turn a retained-behaviour test red for no reason and force a snapshot regeneration that hides the real diff.

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
                    "validate.local.sh is no longer supported; migrate it using "
                    f"{_LEGACY_SIDECAR_PORTING_GUIDE}"
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
                    f"in the toolkit. See {_LEGACY_SIDECAR_PORTING_GUIDE}"
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

The only remaining `try:` blocks are the per-check exception handler and the `resolve_gate_tier` conversion. The `run_result: RunResult | None = None` pre-declaration is no longer needed.

`_LEGACY_SIDECAR_PORTING_GUIDE` already exists in `runner.py` with the value `docs/migration/2026-05-19-validate-local-sh-porting-guide.md`. Leave it exactly as it is — Task 4 retargets the *contents* of that document, not its path.

- [ ] **Step 5: Drop the `hook` export and fix the production caller**

Remove `hook` from the `runner` import and `__all__` in `science/src/science_tool/validate/__init__.py`. Remove the `enable_python_sidecar=False,` argument from the `run(...)` call in `science/src/science_tool/graph/health_checks/validate.py`.

**This changes graph-health behaviour, deliberately.** In today's `runner.py:135`, `legacy_sidecar_exists = sidecar_enabled and legacy_sidecar_path.exists()` — so the flag named for the *Python* sidecar also suppresses the *legacy* `validate.sidecar-removed` hard error. The graph health check is the only caller passing `False`, so it is currently the one surface that silently tolerates a `validate.local.sh`. Once the flag is gone, that hard error becomes unconditional and graph health reports it like every other surface.

That is the correct outcome and not a scope creep: the legacy hard error is a file-existence check that executes nothing, so no control-plane concern ever justified suppressing it. Note the shape of the bug — one flag quietly gating two unrelated behaviours is exactly the coupling this task removes.

Delta check: none of `~/d/health/meta`, `~/d/cancer/mechanisms/evolution`, `~/d/protein-landscape`, or in-repo `meta/` carries a `validate.local.sh`, so the observable baseline delta is zero. Confirm before relying on it:

```bash
for d in ~/d/health/meta ~/d/cancer/mechanisms/evolution ~/d/protein-landscape \
         ~/d/science/.worktrees/sidecar-retirement/meta; do
  printf '%s: ' "$d"
  test -e "$d/validate.local.sh" && echo PRESENT || echo absent
done
```

Expected: `absent` four times. A `PRESENT` means Task 6's parity run will show a new `validate.sidecar-removed` row for that project and the comparator's `NEW_PREFIXES` must be widened to admit it.

Pin the new behaviour so it cannot silently regress. Post–Plan 3, `graph/health_checks/validate.py` exposes `execute_validation(project_root) -> ValidationHealthRun` (a frozen dataclass of `run_result` and `producer_result`), and `run_check` is a one-line projection of it. `tests/validate/test_runner.py` already imports the module as `validate_health` and has a `_project(tmp_path)` helper. Append there:

```python
def test_graph_health_reports_the_legacy_sidecar(tmp_path: Path) -> None:
    project = _project(tmp_path)
    (project / "validate.local.sh").write_text("#!/bin/sh\n", encoding="utf-8")

    execution = validate_health.execute_validation(project)

    rows = [
        finding
        for finding in execution.producer_result.instrument.rows
        if finding.rule_id == "validate.sidecar-removed"
    ]
    assert len(rows) == 1
    assert rows[0].severity == "error"


def test_graph_health_is_clean_without_a_legacy_sidecar(tmp_path: Path) -> None:
    execution = validate_health.execute_validation(_project(tmp_path))

    assert not [
        finding
        for finding in execution.producer_result.instrument.rows
        if finding.rule_id == "validate.sidecar-removed"
    ]
```

Both are red before Step 5 and green after: today `enable_python_sidecar=False` suppresses the row, so the first test fails on `len(rows) == 1`. The second guards the other direction — that the row is driven by the file, not emitted unconditionally.

Note the second call site while you are in this file: `test_execute_validation_projects_one_fixed_run_result_without_a_second_stream` (post–Plan 3, ~line 289) passes `enable_python_sidecar=False` to `run(...)` when building its `expected` fixture. Drop that argument; it is covered by the Step 9 `test_runner.py` row but is easy to miss because it sits in a health test rather than a hook test.

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

- [ ] **Step 9: Migrate the obsolete test surface**

Eight existing test modules reference the removed API and will fail to import or fail outright. This is not optional cleanup — it is part of the change. (`tests/test_command_docs.py` also carries stale sidecar expectations, but they are assertions *about documentation* — they are migrated in Task 4 alongside the prose they pin.)

| file | what to do |
|---|---|
| `tests/validate/test_runner.py` | drop hook-registration and `_dispatch_hooks` tests; keep runner behaviour tests |
| `tests/validate/test_parity_corpus.py` | drop the `SCIENCE_VALIDATE_DISABLE_SIDECAR` monkeypatching; the canonical path is now the only path |
| `tests/validate/test_legacy_precedence.py` | keep `validate.local.sh` precedence coverage; drop anything asserting Python-sidecar precedence |
| `tests/validate/test_checks_dataset_metadata.py` | drop `enable_python_sidecar=` from its `run(...)` calls |
| `tests/validate/test_checks_aggregation_support.py` | same |
| `tests/validate/test_checks_benchmark_metadata.py` | same |
| `tests/validate/test_checks_dataset_capabilities.py` | same |
| `tests/test_registry_loader.py` | migrate the packaged-registry protocol assertion — see below |

**`tests/validate/test_parity_with_sidecar.py` is retained, not deleted.** Read it before touching it. Despite the module name, all six of its test functions cover the *retained* `validate.local.sh` behaviour — the `validate.sidecar-removed` hard error and the guarantee that the shell sidecar is never executed. None of them compare Python-sidecar-on against Python-sidecar-off. Keep the module and its name (it matches the retained rule id), and remove only what assumes the deleted environment variable:

- Delete `test_cli_validate_hard_errors_despite_ambient_disable_sidecar_env_for_parity_harness`. Its entire premise is that `SCIENCE_VALIDATE_DISABLE_SIDECAR=1` in the ambient environment must not suppress the hard error; with the variable gone there is nothing left to assert.
- In `_cli_validate_env()`, drop the `"SCIENCE_VALIDATE_DISABLE_SIDECAR": None` entry. Leave `SCIENCE_VALIDATE_SKIP_DOTENV`, `SCIENCE_TOOL`, and `SCIENCE_TOOL_PATH` alone — `test_cli_validate_does_not_execute_legacy_sidecar_environment_checks` still depends on them.

Five test functions remain, all green.

Then update the two managed-artifact tests that assert the protocol Step 8 replaces:

**`tests/test_registry_loader.py:55`** — `test_packaged_validate_sh_uses_python_sidecar_extension_protocol` asserts `validate_artifacts[0].extension_protocol.kind.value == "python_sidecar"` against the packaged registry. Rename to `test_packaged_validate_sh_declares_no_extension_protocol` and assert `== "none"`. Leave `test_direct_execute_rejects_merged_sidecar_protocol` (~line 42, `match="merged_sidecar.*direct_execute"`) untouched — it builds its own inline fixture and exercises `ExtensionKind.MERGED_SIDECAR`, which remains a valid schema value.

**`tests/test_validate_sh_section_8.py:104-118`** — `test_registry_extension_protocol_uses_python_sidecar` asserts far more than the kind: `protocol["sidecar_path"] == "validate_local.py"`, `"import" in protocol["contract"].lower()`, `"@hook" in protocol["contract"]`, and each of `pre_validation`, `extra_checks`, `post_validation` appearing in the contract. Changing only the kind still leaves five failing assertions against keys the `none` protocol does not carry. Replace the whole function body:

```python
def test_registry_extension_protocol_is_none() -> None:
    data = yaml.safe_load(REGISTRY_YAML.read_text(encoding="utf-8"))
    validate = next(a for a in data["artifacts"] if a["name"] == "validate.sh")
    protocol = validate["extension_protocol"]

    assert protocol["kind"] == "none"
    assert "never executes project-authored code" in protocol["rationale"]
    assert "sidecar_path" not in protocol
    assert "contract" not in protocol
```

Leave the rest of that module untouched. Its `version`, `current_hash`, and changelog assertions — including the `2026.05.20.1` entry naming `validate_local.py` and the `2026.05.21.1` Phase 3 entry — are historical records of what shipped when, not claims about the current protocol. Step 8 changes no bytes, so the hash and version assertions still hold.

- [ ] **Step 10: Confirm nothing still references the removed API**

```bash
( cd ~/d/science/.worktrees/sidecar-retirement/science && \
  rg -n --glob '!tests/test_command_docs.py' \
     'enable_python_sidecar\s*(?:=|:)|_dispatch_hooks|SCIENCE_VALIDATE_DISABLE_SIDECAR|validate import .*\bhook\b' src tests )
```

Expected: no output.

The `enable_python_sidecar` pattern is anchored to `\s*(?:=|:)` so it matches declarations (`enable_python_sidecar: bool = True`) and call-site keywords (`enable_python_sidecar=False`) but not the bare identifier. Step 1's `test_run_has_no_sidecar_parameter` asserts `"enable_python_sidecar" not in inspect.signature(run).parameters` — a quoted string with no `=` or `:` after it. An unanchored pattern would match the regression test that exists to prove the removal, so the scan could never come back clean.

`tests/test_command_docs.py` is excluded deliberately. Its `SCIENCE_VALIDATE_DISABLE_SIDECAR` occurrences are assertions that the string appears in `docs/conventions/validate.md`, which this task does not edit — so the module is still green here and goes red only when Task 4 rewrites that document. Drop the `--glob` exclusion from this command once Task 4 lands and re-run it as part of Task 4 Step 6.

- [ ] **Step 11: Run the affected tests**

```bash
( cd ~/d/science/.worktrees/sidecar-retirement/science && uv run --frozen pytest \
    tests/validate/test_sidecar_retirement.py \
    tests/validate/test_runner.py \
    tests/validate/test_context.py \
    tests/validate/test_parity_corpus.py \
    tests/validate/test_parity_with_sidecar.py \
    tests/validate/test_legacy_precedence.py \
    tests/validate/test_checks_dataset_metadata.py \
    tests/validate/test_checks_aggregation_support.py \
    tests/validate/test_checks_benchmark_metadata.py \
    tests/validate/test_checks_dataset_capabilities.py \
    tests/test_validate_sh_section_8.py \
    tests/test_registry_loader.py \
    tests/test_budget_regression.py \
    tests/test_registry_schema.py \
    tests/test_command_docs.py -v )
```

Expected: all pass, including `test_run_has_no_sidecar_parameter` and the five retained tests in `test_parity_with_sidecar.py`. `test_command_docs.py` is run here as a *guard* — it must still be green, because Task 3 touches no documentation. If it fails, this task has edited docs it should not have.

- [ ] **Step 12: Lint, typecheck, commit**

```bash
( cd ~/d/science/.worktrees/sidecar-retirement/science && uv run ruff check && uv run pyright )
cd ~/d/science/.worktrees/sidecar-retirement && git add -A science/ && \
  git commit -m "feat(validate)!: retire the project Python validation sidecar"
```

Note the subshell: `git add -A science/` must run from the repo root, not from inside `science/`.

---

### Task 4: Documentation and regenerated mirrors

**Files:**
- Modify: `README.md`, `docs/conventions/validate.md`, `docs/migration/2026-05-19-validate-local-sh-porting-guide.md`, `docs/migration/managed-artifacts-template.md`
- Modify: `science/tests/test_command_docs.py`
- Regenerate: `skills/generated/…`

`test_command_docs.py` migrates here, not in Task 3. Its sidecar assertions are pins on documentation prose; they go red the moment this task edits that prose, and they stay green through Task 3. Updating the prose and its pin in one commit is what keeps both tasks independently green.

- [ ] **Step 1: Update `docs/conventions/validate.md`**

Remove the Python-sidecar discovery contract and the `SCIENCE_VALIDATE_DISABLE_SIDECAR` row from the environment-variable table. State that `science validate` never executes project code, and that a `validate_local.py` present in a project produces a `validate.python-sidecar-removed` error.

Keep documenting `validate.sh` as the managed shim that delegates to `science validate` — that is unchanged and still pinned by `test_command_docs.py`.

- [ ] **Step 2: Update the root `README.md`**

`README.md:78` currently reads:

> Validation also supports Python sidecar hooks for project-specific checks.

Replace it with a statement that `science validate` runs only toolkit-defined checks and never executes project-authored code.

- [ ] **Step 3: Retarget the porting guide**

Rewrite `docs/migration/2026-05-19-validate-local-sh-porting-guide.md` from "port your shell sidecar to Python" to "sidecars are retired." It must answer: where a reusable policy check goes (a toolkit check — open a design conversation), and where a genuinely project-specific check goes (a project-owned command the project runs itself, with nothing enforcing it).

- [ ] **Step 4: Fix `docs/migration/managed-artifacts-template.md`**

Not historical, and still instructs projects to migrate logic *into* a sidecar (~line 157) and references `validate.local.sh` (~line 262). Leaving it is an active instruction to recreate what this work removes.

- [ ] **Step 5: Migrate `science/tests/test_command_docs.py`**

`test_validate_cli_reference_documents_shim_contract` (~line 1001) pins four now-stale expectations. Read the whole function before editing — several neighbouring strings in `expected_reference_strings` cover the synopsis, flags, exit codes, severity model, and JSON schema, and all of those stay.

Remove from `expected_reference_strings`:

```python
        "SCIENCE_VALIDATE_DISABLE_SIDECAR=1",
        "For `science validate`, disables both Python sidecar discovery and deprecated legacy `validate.local.sh` discovery.",
        "`validate_local.py` is imported by default when it exists in the project root.",
        "Because `validate.sh` delegates to `science validate`, this environment variable affects validation reached through the shim as well.",
```

Keep `"## Environment Variables"`, `"NO_COLOR"`, `"## Discovery"`, and the `validate.sh`-is-the-shim line — those sections survive, only their sidecar rows go.

Then replace the two README assertions (~lines 1038-1039):

```python
    assert "Python sidecar hooks" in readme
    assert "experimental Python sidecars" not in readme
```

with a positive pin on the Step 2 replacement text plus a negative guard, e.g.:

```python
    assert "never executes project-authored code" in readme
    assert "sidecar" not in readme.lower()
```

Whatever wording Step 2 lands on, the assertion must quote it exactly.

- [ ] **Step 6: Regenerate committed mirrors**

Never hand-edit files under `skills/generated/`.

```bash
( cd ~/d/science/.worktrees/sidecar-retirement/science && uv run --frozen science agents generate )
git -C ~/d/science/.worktrees/sidecar-retirement diff --stat skills/generated/
```

The command is `science agents generate` — `science skills` has only `coverage`, `curate`, `lint`, and `sources`, none of which regenerate the mirror.

- [ ] **Step 7: Confirm no stale instructions remain**

```bash
cd ~/d/science/.worktrees/sidecar-retirement
rg -n --glob '!docs/plans/**' --glob '!**/historical/**' --glob '!docs/audits/**' \
   'validate_local|SCIENCE_VALIDATE_DISABLE_SIDECAR|@hook|[Pp]ython sidecar' \
   README.md docs/ templates/ skills/
```

`README.md` is scanned explicitly — it is not under `docs/` and was the source of the sidecar claim fixed in Step 2.

Three exclusions, each for a different reason:
- `docs/plans/**` — design and implementation records, including this plan. They describe the change; they do not instruct.
- `**/historical/**` — e.g. `docs/plans/historical/2026-05-29-external-datapackage-resources-implementation.md`, a completed plan preserved as-is.
- `docs/audits/**` — audit records (`plans-cleanup/reviews.jsonl`, `project-plans-cleanup/meta/*.md` and its `reviews.jsonl`). These are dated observations of what the tree contained at audit time. Rewriting them would falsify the record. They are history, not instruction; do not edit them.

Expected: retirement-context mentions only — in the retargeted porting guide, and in `docs/conventions/validate.md`, which after Step 1 names `validate_local.py` when documenting the `validate.python-sidecar-removed` error. Both describe the retirement. Neither instructs a project to create a sidecar; that is the property being checked.

- [ ] **Step 8: Re-run the Task 3 API scan without its exclusion**

Task 3 Step 10 had to exempt `tests/test_command_docs.py`. Step 5 removed the reason for that exemption, so the scan must now come back clean unqualified:

```bash
( cd ~/d/science/.worktrees/sidecar-retirement/science && \
  rg -n 'enable_python_sidecar\s*(?:=|:)|_dispatch_hooks|SCIENCE_VALIDATE_DISABLE_SIDECAR|validate import .*\bhook\b' src tests )
```

Expected: no output. Same anchored `enable_python_sidecar` pattern as Task 3 Step 10, for the same reason — the bare identifier still appears in `test_run_has_no_sidecar_parameter`, by design.

- [ ] **Step 9: Run the documentation tests**

```bash
( cd ~/d/science/.worktrees/sidecar-retirement/science && \
  uv run --frozen pytest tests/test_command_docs.py -v )
```

Expected: all pass. This is the step where the Step 1/2/5 edits are proved consistent with each other — the assertions quote the prose, so a mismatch here means the prose and the pin disagree.

- [ ] **Step 10: Commit**

```bash
cd ~/d/science/.worktrees/sidecar-retirement
git add README.md docs/ skills/ science/tests/test_command_docs.py
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
( cd ~/d/science/.worktrees/sidecar-retirement/meta && uv run python -m t034_validator evidence/ )
status=$?
test "$status" -eq 0 || { echo "FAIL: t034 exited $status"; exit 1; }
```

Expected: a `t034: N payload(s), 0 error(s), 0 load error(s)` summary and no `FAIL` line.

- [ ] **Step 4: Verify meta validates cleanly**

```bash
cd ~/d/science/.worktrees/sidecar-retirement/meta
uv run --frozen science validate --all --strict --format json > /tmp/meta-after.json
status=$?
test "$status" -eq 0 || { echo "FAIL: validator exited $status, expected 0"; exit 1; }
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

Expected: no `FAIL` line and `OK`. Capture the status immediately — never `| head` before reading `$?`, which reports the pipe's last command, so a failing validator would read as success.

- [ ] **Step 5: Commit**

```bash
cd ~/d/science/.worktrees/sidecar-retirement
git add -A meta/
git commit -m "chore(meta): drop the validation sidecar and invoke t034 directly"
```

---

### Task 6: Rebase, full-suite, and immutable canonical parity verification

**Files:** none modified. Every prior Task 6 result, including the
`af031823` suite and parity evidence, is superseded by this rebase. Preserve
the old files; do not overwrite them or describe them as approval evidence.

- [ ] **Step 1: Rebase on the recorded current main, resolve the two budget overlaps, and run focused budget tests first**

Run Preconditions P1 and P2. Resolve only
`science/src/science_tool/budget/registry.py` and
`science/tests/test_budget_boundary.py` by retaining both current main's
`findings migrate-acceptances` deferral and tests, and this feature's removal
of `project artifacts port-validate-sidecar`. Confirm the resulting audited
partition before any broader verification.

```bash
set -euo pipefail
toolkit_root=~/d/science/.worktrees/sidecar-retirement
( cd "$toolkit_root/science" && uv run --frozen pytest -q tests/test_budget_boundary.py )
rg -n 'findings migrate-acceptances|port-validate-sidecar|69 budgeted|121 exempt|102 deferred' \
  "$toolkit_root/science/src/science_tool/budget/registry.py" \
  "$toolkit_root/science/tests/test_budget_boundary.py"
```

Expected: focused budget tests pass and the inspected registry/test evidence
states `69 budgeted / 121 exempt / 102 deferred`.

- [ ] **Step 2: Create immutable, clean consumer snapshots and initialize the Task 6 manifest**

The historical `~/scratch/sidecar-baselines/` directory is read-only evidence.
Each retry gets a new UTC-labelled attempt beneath the revision-labelled
directory; never reuse or delete a prior attempt. Use the exact same consumer
snapshots for before and after reports. Do not use either live feature path:
both the after toolkit and science/meta must come from an immutable detached
worktree at the recorded feature SHA.

```bash
set -euo pipefail
toolkit_root=~/d/science/.worktrees/sidecar-retirement
baseline_toolkit_sha=a7f3337e98515bc289781ef0a1eae7b9c2fe73a5
feature_branch_sha=$(git -C "$toolkit_root" rev-parse HEAD)
test -z "$(git -C "$toolkit_root" status --porcelain)" || {
  echo "HARD STOP: feature worktree is dirty"; exit 1;
}
attempt_id=$(date -u +%Y%m%dT%H%M%SZ)
attempt_root=~/scratch/sidecar-baselines/a7f3337e98515bc289781ef0a1eae7b9c2fe73a5/attempt-"$attempt_id"
test ! -e "$attempt_root" || { echo "HARD STOP: attempt collision at $attempt_root"; exit 1; }
mkdir -p "$attempt_root/snapshots"
printf '%s\n' "$attempt_root" > ~/scratch/sidecar-baselines/a7f3337e98515bc289781ef0a1eae7b9c2fe73a5/latest-attempt.txt
declare -A source_root=(
  [health-meta]=~/d/health/meta
  [evolution]=~/d/cancer/mechanisms/evolution
  [protein-landscape]=~/d/protein-landscape
)
declare -A required_head=(
  [health-meta]=36ba8ec83f91d35ba82961836bfc1731b00d9e8b
  [evolution]=25fd2cb475807c8f5af0d2553244368c55fd3ad2
  [protein-landscape]=6796628c06a562ff45029f317a0f0fdf1a2fec9e
)
for consumer_name in health-meta evolution protein-landscape; do
  test -z "$(git -C "${source_root[$consumer_name]}" status --porcelain)" || {
    echo "HARD STOP: $consumer_name source checkout is dirty"; exit 1;
  }
  actual_head=$(git -C "${source_root[$consumer_name]}" rev-parse HEAD)
  test "$actual_head" = "${required_head[$consumer_name]}" || {
    echo "HARD STOP: $consumer_name is $actual_head, expected ${required_head[$consumer_name]}"; exit 1;
  }
  git -C "${source_root[$consumer_name]}" worktree add --detach \
    "$attempt_root/snapshots/$consumer_name" "$actual_head"
done
git -C "$toolkit_root" worktree add --detach "$attempt_root/toolkit-after" "$feature_branch_sha"
test -z "$(git -C "$attempt_root/toolkit-after" status --porcelain)" || {
  echo "HARD STOP: detached after-toolkit worktree is dirty"; exit 1;
}
test "$(git -C "$attempt_root/toolkit-after" rev-parse HEAD)" = "$feature_branch_sha" || {
  echo "HARD STOP: detached after-toolkit SHA differs from feature branch"; exit 1;
}
science_meta_tree=$(git -C "$attempt_root/toolkit-after" rev-parse HEAD:meta)
printf 'toolkit-before\t%s\nfeature-branch\t%s\nconsumer\thealth-meta\t%s\t%s\tclean\nconsumer\tevolution\t%s\t%s\tclean\nconsumer\tprotein-landscape\t%s\t%s\tclean\nconsumer\tscience-meta\t%s\t%s\tclean\n' \
  "$baseline_toolkit_sha" "$feature_branch_sha" "${source_root[health-meta]}" "${required_head[health-meta]}" \
  "${source_root[evolution]}" "${required_head[evolution]}" "${source_root[protein-landscape]}" "${required_head[protein-landscape]}" \
  "$attempt_root/toolkit-after/meta" "$science_meta_tree" \
  > "$attempt_root/task-6-manifest.tsv"
printf 'toolkit-after\t%s\nattempt-root\t%s\n' "$feature_branch_sha" "$attempt_root" >> "$attempt_root/task-6-manifest.tsv"
```

**Retry cleanup:** if an attempt stops before verification, read its path from
`latest-attempt.txt` and remove only the registered detached worktrees; do not
delete its reports or directory. This command is safe to repeat and lets the
next run create a fresh attempt directory:

```bash
set -euo pipefail
toolkit_root=~/d/science/.worktrees/sidecar-retirement
revision_root=~/scratch/sidecar-baselines/a7f3337e98515bc289781ef0a1eae7b9c2fe73a5
attempt_root=$(cat "$revision_root/latest-attempt.txt")
for worktree_path in "$attempt_root/toolkit-before" "$attempt_root/toolkit-after"; do
  if git -C "$toolkit_root" worktree list --porcelain | rg -Fqx "worktree $worktree_path"; then
    git -C "$toolkit_root" worktree remove --force "$worktree_path"
  fi
done
git -C "$toolkit_root" worktree prune
declare -A source_root=(
  [health-meta]=~/d/health/meta
  [evolution]=~/d/cancer/mechanisms/evolution
  [protein-landscape]=~/d/protein-landscape
)
for consumer_name in health-meta evolution protein-landscape; do
  worktree_path="$attempt_root/snapshots/$consumer_name"
  if git -C "${source_root[$consumer_name]}" worktree list --porcelain | rg -Fqx "worktree $worktree_path"; then
    git -C "${source_root[$consumer_name]}" worktree remove --force "$worktree_path"
  fi
  git -C "${source_root[$consumer_name]}" worktree prune
done
```

- [ ] **Step 3: Run broader verification sequentially and explicitly compare known real-project failures with current main**

Run no suites concurrently. The toolkit suite, model suite, snapshot marker,
and real-project marker must all be rerun from the rebased feature worktree.
The three known real-project failures are not waived: capture the complete
output, then run their exact node IDs against both the `a7f3337e` toolkit
worktree and the rebased feature worktree. Any changed result, or any
additional failed node in the rebased marker, is a hard failure.
If an explicit `--basetemp` is used for any suite, precheck that neither that
path nor any ancestor contains a `.git` marker; the default pytest temp path is
preferred.

```bash
set -euo pipefail
toolkit_root=~/d/science/.worktrees/sidecar-retirement
revision_root=~/scratch/sidecar-baselines/a7f3337e98515bc289781ef0a1eae7b9c2fe73a5
attempt_root=$(cat "$revision_root/latest-attempt.txt")
git -C "$toolkit_root" worktree add --detach "$attempt_root/toolkit-before" a7f3337e98515bc289781ef0a1eae7b9c2fe73a5
run_zero_suite() {
  local command_key=$1
  local suite_dir=$2
  local suite_args=$3
  local output_path=$4
  set +e
  ( cd "$suite_dir" && uv run --frozen pytest $suite_args ) > "$output_path" 2>&1
  local suite_status=$?
  set -e
  test "$suite_status" = 0 || { echo "HARD STOP: $command_key exited $suite_status"; exit 1; }
  printf 'command\t%s\tcd %s && uv run --frozen pytest %s\texit\t%s\t%s\n' \
    "$command_key" "$suite_dir" "$suite_args" "$suite_status" "$output_path" >> "$attempt_root/task-6-manifest.tsv"
}
run_zero_suite toolkit-suite "$attempt_root/toolkit-after/science" "" "$attempt_root/toolkit-suite.txt"
run_zero_suite model-suite "$attempt_root/toolkit-after/science/model" "" "$attempt_root/model-suite.txt"
run_zero_suite snapshot-marker "$attempt_root/toolkit-after/science" "-m snapshot" "$attempt_root/snapshot-marker.txt"
set +e
( cd "$attempt_root/toolkit-after/science" && uv run --frozen pytest -m real_projects ) > "$attempt_root/rebased-real-projects.txt" 2>&1
rebased_real_status=$?
set -e
printf 'command\trebased-real-project-marker\tcd %s/science && uv run --frozen pytest -m real_projects\texit\t%s\t%s\n' "$attempt_root/toolkit-after" "$rebased_real_status" "$attempt_root/rebased-real-projects.txt" >> "$attempt_root/task-6-manifest.tsv"
test "$(rg -c '^FAILED ' "$attempt_root/rebased-real-projects.txt")" -eq 3 || {
  echo "HARD STOP: rebased real-project marker did not have exactly the three recorded failures"; exit 1;
}
run_case() {
  local label=$1
  local case_toolkit_root=$2
  local node_id=$3
  set +e
  ( cd "$case_toolkit_root/science" && uv run --frozen pytest -q -m real_projects "$node_id" ) \
    > "$attempt_root/$label-$(basename "$node_id").txt" 2>&1
  local case_status=$?
  set -e
  printf '%s\t%s\t%s\t%s\n' "$label" "$node_id" "$case_status" "$attempt_root/$label-$(basename "$node_id").txt" >> "$attempt_root/known-real-project-statuses.tsv"
}
for node_id in \
  tests/skills_coverage/test_coverage_real_projects.py::test_health_meta_commons_datasets_are_grounded_and_not_owned \
  tests/test_correspondence_drift_real_projects.py::test_detector_fires_on_multiple_myeloma \
  tests/validate/test_parity_canonical_body.py::test_real_downstream_projects_match_bash_validate_semantics; do
  run_case current-main "$attempt_root/toolkit-before" "$node_id"
  run_case rebased-feature "$attempt_root/toolkit-after" "$node_id"
done
awk -F '\t' '$1 == "current-main" { before[$2] = $3 } $1 == "rebased-feature" { if (!($2 in before) || before[$2] != $3) { print "HARD STOP: real-project behavior changed for " $2; failed = 1 } } END { exit failed }' \
  "$attempt_root/known-real-project-statuses.tsv"
awk -F '\t' '$3 == 0 { print "HARD STOP: expected nonzero known failure: " $2; failed = 1 } END { exit failed }' \
  "$attempt_root/known-real-project-statuses.tsv"
for label in current-main rebased-feature; do
  rg --no-filename '^FAILED ' "$attempt_root"/"$label"-*.txt | sort > "$attempt_root/$label-failure-signatures.txt"
done
test -s "$attempt_root/current-main-failure-signatures.txt" || { echo "HARD STOP: missing current-main failure signature"; exit 1; }
test -s "$attempt_root/rebased-feature-failure-signatures.txt" || { echo "HARD STOP: missing rebased-feature failure signature"; exit 1; }
diff -u "$attempt_root/current-main-failure-signatures.txt" "$attempt_root/rebased-feature-failure-signatures.txt"
```

Record the three matched nonzero statuses as known external-state failures in
the final parity table. Step 6 is the single owner of their manifest artifact
rows and checksums. They remain visible evidence, not a green result or an
implicit exception.

- [ ] **Step 4: Recapture four canonical before reports from `a7f3337e` and the pinned snapshots**

Build the before environment from the exact old toolkit worktree, then write
only into the new revision-labelled directory. The source path for science/meta
is the rebased feature worktree's migrated tree for both before and after.

```bash
set -euo pipefail
revision_root=~/scratch/sidecar-baselines/a7f3337e98515bc289781ef0a1eae7b9c2fe73a5
attempt_root=$(cat "$revision_root/latest-attempt.txt")
uv venv "$attempt_root/before-venv"
uv pip install --python "$attempt_root/before-venv/bin/python" -e "$attempt_root/toolkit-before/science"
before_bin="$attempt_root/before-venv/bin/science"
declare -A project_root=(
  [health-meta]="$attempt_root/snapshots/health-meta"
  [evolution]="$attempt_root/snapshots/evolution"
  [protein-landscape]="$attempt_root/snapshots/protein-landscape"
  [science-meta]="$attempt_root/toolkit-after/meta"
)
for consumer_name in health-meta evolution protein-landscape science-meta; do
  set +e
  ( cd "${project_root[$consumer_name]}" && SCIENCE_VALIDATE_DISABLE_SIDECAR=1 "$before_bin" validate --all --strict --format json \
      --output "$attempt_root/$consumer_name-canonical.json" )
  command_status=$?
  set -e
  test "$command_status" -le 1 || { echo "HARD STOP: before capture crashed for $consumer_name"; exit 1; }
  test -s "$attempt_root/$consumer_name-canonical.json" || { echo "HARD STOP: missing before report for $consumer_name"; exit 1; }
  printf 'command\tbefore-%s\tSCIENCE_VALIDATE_DISABLE_SIDECAR=1 science validate --all --strict --format json --output %s\texit\t%s\t%s\n' "$consumer_name" "$attempt_root/$consumer_name-canonical.json" "$command_status" "$attempt_root/$consumer_name-canonical.json" >> "$attempt_root/task-6-manifest.tsv"
done
```

- [ ] **Step 5: Build the after environment from the rebased feature worktree and capture the same snapshots**

```bash
set -euo pipefail
revision_root=~/scratch/sidecar-baselines/a7f3337e98515bc289781ef0a1eae7b9c2fe73a5
attempt_root=$(cat "$revision_root/latest-attempt.txt")
feature_branch_sha=$(awk -F '\t' '$1 == "feature-branch" {print $2}' "$attempt_root/task-6-manifest.tsv")
toolkit_after_sha=$(awk -F '\t' '$1 == "toolkit-after" {print $2}' "$attempt_root/task-6-manifest.tsv")
test "$toolkit_after_sha" = "$feature_branch_sha" || { echo "HARD STOP: manifest feature/toolkit-after mismatch"; exit 1; }
test "$(git -C "$attempt_root/toolkit-after" rev-parse HEAD)" = "$feature_branch_sha" || { echo "HARD STOP: after worktree drift"; exit 1; }
uv venv "$attempt_root/after-venv"
uv pip install --python "$attempt_root/after-venv/bin/python" -e "$attempt_root/toolkit-after/science"
after_bin="$attempt_root/after-venv/bin/science"
declare -A project_root=(
  [health-meta]="$attempt_root/snapshots/health-meta"
  [evolution]="$attempt_root/snapshots/evolution"
  [protein-landscape]="$attempt_root/snapshots/protein-landscape"
  [science-meta]="$attempt_root/toolkit-after/meta"
)
declare -A expected_exit=( [health-meta]=1 [evolution]=1 [protein-landscape]=1 [science-meta]=0 )
for consumer_name in health-meta evolution protein-landscape science-meta; do
  set +e
  ( cd "${project_root[$consumer_name]}" && "$after_bin" validate --all --strict --format json \
      --output "$attempt_root/$consumer_name-after.json" )
  command_status=$?
  set -e
  test "$command_status" = "${expected_exit[$consumer_name]}" || {
    echo "HARD STOP: after capture for $consumer_name exited $command_status"; exit 1;
  }
  test -s "$attempt_root/$consumer_name-after.json" || { echo "HARD STOP: missing after report for $consumer_name"; exit 1; }
  printf 'command\tafter-%s\tscience validate --all --strict --format json --output %s\texit\t%s\t%s\n' "$consumer_name" "$attempt_root/$consumer_name-after.json" "$command_status" "$attempt_root/$consumer_name-after.json" >> "$attempt_root/task-6-manifest.tsv"
done
```

- [ ] **Step 6: Assert counts, complete-public-result parity, warnings, notices, and publish the auditable record**

Use the existing complete-public-result projection: exclude only the two new
rule prefixes, retain duplicate rows, and compare the resulting complete public
dicts. Missing reports, dirty/mismatched consumer state, a new background
review warning, or a parity mismatch are hard failures. Capture the report
paths and SHA-256 checksums, both toolkit SHAs, branch SHA, every consumer
path/HEAD-or-tree/clean state, each command and exit status in the manifest;
missing data is a hard failure.

```bash
set -euo pipefail
revision_root=~/scratch/sidecar-baselines/a7f3337e98515bc289781ef0a1eae7b9c2fe73a5
attempt_root=$(cat "$revision_root/latest-attempt.txt")
ATTEMPT_ROOT="$attempt_root" python3 - <<'PY'
import json
import sys
from pathlib import Path

base = Path(__import__("os").environ["ATTEMPT_ROOT"])
names = ("health-meta", "evolution", "protein-landscape", "science-meta")
new_prefixes = ("papers.background-review", "validate.python-sidecar-removed")
expected_retirement = {"health-meta": 1, "evolution": 1, "protein-landscape": 1, "science-meta": 0}
table = ["| Consumer | Before rows | After rows | Retirement | Parity |", "| --- | ---: | ---: | ---: | --- |"]
for name in names:
    before_path = base / f"{name}-canonical.json"
    after_path = base / f"{name}-after.json"
    if not before_path.is_file() or not after_path.is_file():
        sys.exit(f"HARD STOP: missing report for {name}")
    before = json.loads(before_path.read_text())["results"]
    after = json.loads(after_path.read_text())["results"]
    before_public = sorted(json.dumps(row, sort_keys=True) for row in before if not str(row.get("rule") or "").startswith(new_prefixes))
    after_public = sorted(json.dumps(row, sort_keys=True) for row in after if not str(row.get("rule") or "").startswith(new_prefixes))
    retirement = sum(row.get("rule") == "validate.python-sidecar-removed" for row in after)
    warnings = [row for row in after if str(row.get("rule") or "").startswith("papers.background-review")]
    if before_public != after_public or retirement != expected_retirement[name] or warnings:
        sys.exit(f"HARD STOP: parity/count/warning failure for {name}")
    table.append(f"| {name} | {len(before)} | {len(after)} | {retirement} | MATCH |")
(base / "parity-table.md").write_text("\n".join(table) + "\n")
PY
after_bin="$attempt_root/after-venv/bin/science"
set +e
( cd "$attempt_root/snapshots/evolution" && "$after_bin" validate --all --strict --verbose --output "$attempt_root/evolution-verbose.txt" ) > "$attempt_root/evolution-verbose-command.txt" 2>&1
evolution_notice_status=$?
( cd "$attempt_root/snapshots/health-meta" && "$after_bin" validate --all --strict --verbose --output "$attempt_root/health-meta-verbose.txt" ) > "$attempt_root/health-meta-verbose-command.txt" 2>&1
health_meta_notice_status=$?
set -e
test "$evolution_notice_status" = 1 || { echo "HARD STOP: evolution verbose exit $evolution_notice_status"; exit 1; }
test "$health_meta_notice_status" = 1 || { echo "HARD STOP: health/meta verbose exit $health_meta_notice_status"; exit 1; }
rg -q 'no status:background papers' "$attempt_root/evolution-verbose.txt"
rg -q '9 status:background paper' "$attempt_root/health-meta-verbose.txt"
printf 'command\tevolution-verbose\tscience validate --all --strict --verbose\texit\t%s\t%s\ncommand\thealth-meta-verbose\tscience validate --all --strict --verbose\texit\t%s\t%s\n' \
  "$evolution_notice_status" "$attempt_root/evolution-verbose.txt" "$health_meta_notice_status" "$attempt_root/health-meta-verbose.txt" >> "$attempt_root/task-6-manifest.tsv"
record_artifact() {
  local artifact_key=$1
  local artifact_path=$2
  test -s "$artifact_path" || { echo "HARD STOP: missing artifact $artifact_key"; exit 1; }
  printf 'artifact\t%s\t%s\t%s\n' "$artifact_key" "$artifact_path" "$(sha256sum "$artifact_path" | awk '{print $1}')" >> "$attempt_root/task-6-manifest.tsv"
}
for consumer_name in health-meta evolution protein-landscape science-meta; do
  record_artifact "$consumer_name-canonical" "$attempt_root/$consumer_name-canonical.json"
  record_artifact "$consumer_name-after" "$attempt_root/$consumer_name-after.json"
done
record_artifact parity-table "$attempt_root/parity-table.md"
record_artifact toolkit-suite "$attempt_root/toolkit-suite.txt"
record_artifact model-suite "$attempt_root/model-suite.txt"
record_artifact snapshot-marker "$attempt_root/snapshot-marker.txt"
record_artifact rebased-real-projects "$attempt_root/rebased-real-projects.txt"
record_artifact known-real-project-statuses "$attempt_root/known-real-project-statuses.tsv"
record_artifact current-main-failure-signatures "$attempt_root/current-main-failure-signatures.txt"
record_artifact rebased-feature-failure-signatures "$attempt_root/rebased-feature-failure-signatures.txt"
record_artifact evolution-verbose "$attempt_root/evolution-verbose.txt"
record_artifact health-meta-verbose "$attempt_root/health-meta-verbose.txt"
ATTEMPT_ROOT="$attempt_root" python3 - <<'PY'
import os
from pathlib import Path

root = Path(os.environ["ATTEMPT_ROOT"])
lines = [line.split("\t") for line in (root / "task-6-manifest.tsv").read_text().splitlines()]
singletons = {row[0]: row for row in lines if row and row[0] in {"toolkit-before", "toolkit-after", "feature-branch", "attempt-root"}}
required_artifacts = {
    *(f"{name}-{phase}" for name in ("health-meta", "evolution", "protein-landscape", "science-meta") for phase in ("canonical", "after")),
    "parity-table", "toolkit-suite", "model-suite", "snapshot-marker",
    "rebased-real-projects", "known-real-project-statuses",
    "current-main-failure-signatures", "rebased-feature-failure-signatures",
    "evolution-verbose", "health-meta-verbose",
}
artifact_keys = {row[1] for row in lines if len(row) == 4 and row[0] == "artifact"}
consumer_names = {row[1] for row in lines if len(row) == 5 and row[0] == "consumer"}
command_names = {row[1] for row in lines if len(row) >= 5 and row[0] == "command"}
required_commands = {"toolkit-suite", "model-suite", "snapshot-marker", "rebased-real-project-marker", "evolution-verbose", "health-meta-verbose", *(f"{phase}-{name}" for name in ("health-meta", "evolution", "protein-landscape", "science-meta") for phase in ("before", "after"))}
missing = ({"toolkit-before", "toolkit-after", "feature-branch", "attempt-root"} - singletons.keys()) | (required_artifacts - artifact_keys) | ({"health-meta", "evolution", "protein-landscape", "science-meta"} - consumer_names) | (required_commands - command_names)
if missing or singletons["toolkit-after"][1] != singletons["feature-branch"][1]:
    raise SystemExit(f"HARD STOP: incomplete or inconsistent manifest: {sorted(missing)}")
PY
sha256sum "$attempt_root/task-6-manifest.tsv" > "$attempt_root/task-6-manifest.sha256"
{
  printf '# Task 6 parity — toolkit before %s; toolkit after %s; branch %s\n\n' \
    a7f3337e98515bc289781ef0a1eae7b9c2fe73a5 "$(awk -F '\t' '$1 == "toolkit-after" {print $2}' "$attempt_root/task-6-manifest.tsv")" "$(awk -F '\t' '$1 == "feature-branch" {print $2}' "$attempt_root/task-6-manifest.tsv")"
  printf 'Pinned consumers: health/meta `36ba8ec83f91d35ba82961836bfc1731b00d9e8b`; evolution `25fd2cb475807c8f5af0d2553244368c55fd3ad2`; protein-landscape `6796628c06a562ff45029f317a0f0fdf1a2fec9e`; science/meta tree `%s`.\n\n' "$(awk -F '\t' '$1 == "consumer" && $2 == "science-meta" {print $4}' "$attempt_root/task-6-manifest.tsv")"
  printf 'Known real-project failure signatures matched current main; see manifest artifacts.\n\n'
  cat "$attempt_root/parity-table.md"
} > "$attempt_root/final-parity-table.md"
record_artifact final-parity-table "$attempt_root/final-parity-table.md"
duplicate_artifact_keys=$(awk -F '\t' '
  $1 == "artifact" { count[$2]++ }
  END {
    for (key in count) {
      if (count[key] != 1) print key
    }
  }
' "$attempt_root/task-6-manifest.tsv")
test -z "$duplicate_artifact_keys" || {
  printf 'HARD STOP: manifest artifact keys are not unique:\n%s\n' "$duplicate_artifact_keys"
  exit 1
}
sha256sum "$attempt_root/task-6-manifest.tsv" > "$attempt_root/task-6-manifest.sha256"
```

The manifest, its detached SHA-256 file, `final-parity-table.md`, four before
reports, four after reports, verbose-notice evidence, and the explicit
current-main comparison are the Task 6 result. Re-run this entire task after
any rebase, merge-resolution change, or consumer snapshot drift.

---

### Task 7: Approval gate, then publish from a verified integration worktree

**Files:** none.

A consumer cannot resolve an unpushed revision, so this must precede Tasks 8–10. It is the one irreversible step in the plan. Never merge or publish from
the divergent local `main` checkout at `395f3af22425ac30926fc6c46b71d76366e70902`.

- [ ] **Step 1: Obtain explicit approval to merge and push**

Present Task 6's final parity table, manifest SHA-256, and explicitly recorded
real-project comparison; ask for a go/no-go on pushing `origin/main`. **Do not
proceed without an explicit yes.** Prior approval of the design is not approval
of the push. Immediately after that yes, create this immutable approval record.
It is the only point at which `latest-attempt.txt` may be read for publication;
copy the printed `approval_record` path verbatim into Steps 2 and 3.

```bash
set -euo pipefail
revision_root=~/scratch/sidecar-baselines/a7f3337e98515bc289781ef0a1eae7b9c2fe73a5
approved_attempt_root=$(cat "$revision_root/latest-attempt.txt")
approval_id=$(date -u +%Y%m%dT%H%M%SZ)
approval_record="$revision_root/approval-$approval_id.tsv"
approval_digest_path="$approval_record.sha256"
test ! -e "$approval_record" && test ! -e "$approval_digest_path" || {
  echo "HARD STOP: approval record collision"; exit 1;
}
test "$(sha256sum "$approved_attempt_root/task-6-manifest.tsv")" = "$(cat "$approved_attempt_root/task-6-manifest.sha256")" || {
  echo "HARD STOP: approved attempt manifest digest mismatch"; exit 1;
}
duplicate_artifact_keys=$(awk -F '\t' '
  $1 == "artifact" { count[$2]++ }
  END {
    for (key in count) {
      if (count[key] != 1) print key
    }
  }
' "$approved_attempt_root/task-6-manifest.tsv")
test -z "$duplicate_artifact_keys" || {
  printf 'HARD STOP: approved manifest artifact keys are not unique:\n%s\n' "$duplicate_artifact_keys"
  exit 1
}
for artifact_path in "$approved_attempt_root/final-parity-table.md" "$approved_attempt_root/parity-table.md" \
  "$approved_attempt_root/rebased-real-projects.txt" "$approved_attempt_root/current-main-failure-signatures.txt" \
  "$approved_attempt_root/rebased-feature-failure-signatures.txt"; do
  test -s "$artifact_path" || { echo "HARD STOP: missing approval artifact $artifact_path"; exit 1; }
done
printf 'attempt-root\t%s\nmanifest-digest\t%s\nbaseline-sha\t%s\nfeature-sha\t%s\nparity-artifact\t%s\nreal-project-artifact\t%s\ncurrent-main-signatures\t%s\nfeature-signatures\t%s\n' \
  "$approved_attempt_root" "$(sha256sum "$approved_attempt_root/task-6-manifest.tsv" | awk '{print $1}')" \
  "$(awk -F '\t' '$1 == "toolkit-before" {print $2}' "$approved_attempt_root/task-6-manifest.tsv")" \
  "$(awk -F '\t' '$1 == "feature-branch" {print $2}' "$approved_attempt_root/task-6-manifest.tsv")" \
  "$approved_attempt_root/final-parity-table.md" "$approved_attempt_root/rebased-real-projects.txt" \
  "$approved_attempt_root/current-main-failure-signatures.txt" "$approved_attempt_root/rebased-feature-failure-signatures.txt" \
  > "$approval_record"
printf 'evidence\ttask-6-manifest\t%s\t%s\n' "$approved_attempt_root/task-6-manifest.tsv" \
  "$(sha256sum "$approved_attempt_root/task-6-manifest.tsv" | awk '{print $1}')" >> "$approval_record"
declare -A evidence_key=(
  [final-parity-table]=final-parity-table
  [parity-table]=parity-table
  [rebased-real-projects]=rebased-real-projects
  [current-main-signatures]=current-main-failure-signatures
  [feature-signatures]=rebased-feature-failure-signatures
)
for approval_key in final-parity-table parity-table rebased-real-projects current-main-signatures feature-signatures; do
  manifest_key=${evidence_key[$approval_key]}
  mapfile -t manifest_evidence_rows < <(
    awk -F '\t' -v key="$manifest_key" \
      '$1 == "artifact" && $2 == key {print $3 "\t" $4}' \
      "$approved_attempt_root/task-6-manifest.tsv"
  )
  test "${#manifest_evidence_rows[@]}" -eq 1 || {
    echo "HARD STOP: expected exactly one manifest path/hash row for $manifest_key"; exit 1;
  }
  IFS=$'\t' read -r artifact_path expected_digest <<< "${manifest_evidence_rows[0]}"
  test -n "$artifact_path" && test -n "$expected_digest" || { echo "HARD STOP: incomplete manifest evidence $manifest_key"; exit 1; }
  test "$(sha256sum "$artifact_path" | awk '{print $1}')" = "$expected_digest" || { echo "HARD STOP: manifest evidence checksum mismatch for $manifest_key"; exit 1; }
  printf 'evidence\t%s\t%s\t%s\n' "$approval_key" "$artifact_path" "$expected_digest" >> "$approval_record"
done
sha256sum "$approval_record" > "$approval_digest_path"
printf 'Approved publication record: %s\n' "$approval_record"
```

- [ ] **Step 2: Refetch, require the recorded remote SHA, and merge only in a temporary integration worktree**

```bash
set -euo pipefail
toolkit_root=~/d/science/.worktrees/sidecar-retirement
recorded_origin_main_sha=a7f3337e98515bc289781ef0a1eae7b9c2fe73a5
revision_root=~/scratch/sidecar-baselines/a7f3337e98515bc289781ef0a1eae7b9c2fe73a5
read -r -p 'Paste the exact approval record printed by Task 7 Step 1: ' approval_record
approval_digest_path="$approval_record.sha256"
test -s "$approval_record" && test -s "$approval_digest_path" || { echo "HARD STOP: missing explicit approval record"; exit 1; }
test "$(sha256sum "$approval_record")" = "$(cat "$approval_digest_path")" || { echo "HARD STOP: approval record changed"; exit 1; }
approved_attempt_root=$(awk -F '\t' '$1 == "attempt-root" {print $2}' "$approval_record")
approved_manifest_digest=$(awk -F '\t' '$1 == "manifest-digest" {print $2}' "$approval_record")
approved_baseline_sha=$(awk -F '\t' '$1 == "baseline-sha" {print $2}' "$approval_record")
approved_feature_sha=$(awk -F '\t' '$1 == "feature-sha" {print $2}' "$approval_record")
test "$approved_baseline_sha" = "$recorded_origin_main_sha" || { echo "HARD STOP: approval baseline SHA mismatch"; exit 1; }
test "$(sha256sum "$approved_attempt_root/task-6-manifest.tsv" | awk '{print $1}')" = "$approved_manifest_digest" || { echo "HARD STOP: approved attempt changed"; exit 1; }
test "$(awk -F '\t' '$1 == "feature-branch" {print $2}' "$approved_attempt_root/task-6-manifest.tsv")" = "$approved_feature_sha" || { echo "HARD STOP: approval feature SHA mismatch"; exit 1; }
test "$(awk -F '\t' '$1 == "toolkit-after" {print $2}' "$approved_attempt_root/task-6-manifest.tsv")" = "$approved_feature_sha" || { echo "HARD STOP: approval after-toolkit SHA mismatch"; exit 1; }
verify_approved_evidence() {
  local evidence_key=$1
  local evidence_path
  local evidence_digest
  evidence_path=$(awk -F '\t' -v key="$evidence_key" '$1 == "evidence" && $2 == key {print $3}' "$approval_record")
  evidence_digest=$(awk -F '\t' -v key="$evidence_key" '$1 == "evidence" && $2 == key {print $4}' "$approval_record")
  test -n "$evidence_path" && test -n "$evidence_digest" || { echo "HARD STOP: missing frozen evidence $evidence_key"; exit 1; }
  test "$(sha256sum "$evidence_path" | awk '{print $1}')" = "$evidence_digest" || { echo "HARD STOP: approved evidence changed: $evidence_key"; exit 1; }
}
for evidence_key in task-6-manifest final-parity-table parity-table rebased-real-projects current-main-signatures feature-signatures; do
  verify_approved_evidence "$evidence_key"
done
integration_root=~/scratch/sidecar-publish-a7f3337e-"$(basename "$approval_record" .tsv)"
test ! -e "$integration_root" || { echo "HARD STOP: preserve prior publish worktree $integration_root"; exit 1; }
test "$(git -C "$toolkit_root" rev-parse sidecar-retirement)" = "$approved_feature_sha" || {
  echo "HARD STOP: sidecar-retirement advanced after Task 6 approval"; exit 1;
}
git -C "$toolkit_root" fetch --prune origin
actual_origin_main_sha=$(git -C "$toolkit_root" rev-parse origin/main)
test "$actual_origin_main_sha" = "$recorded_origin_main_sha" || {
  echo "HARD STOP: origin/main changed; reassess and recapture Task 6"; exit 1;
}
git -C "$toolkit_root" worktree add -b sidecar-retirement-publish "$integration_root" "$recorded_origin_main_sha"
git -C "$integration_root" merge --no-ff "$approved_feature_sha" -m "merge: retire validation sidecar"
merge_sha=$(git -C "$integration_root" rev-parse HEAD)
first_parent_sha=$(git -C "$integration_root" rev-parse HEAD^1)
second_parent_sha=$(git -C "$integration_root" rev-parse HEAD^2)
test "$first_parent_sha" = "$recorded_origin_main_sha" || {
  echo "HARD STOP: merge first parent is $first_parent_sha"; exit 1;
}
test "$second_parent_sha" = "$approved_feature_sha" || {
  echo "HARD STOP: merge second parent is $second_parent_sha"; exit 1;
}
```

- [ ] **Step 3: Reconfirm the approved Task 6 gate, push the integration HEAD, and verify the remote**

```bash
set -euo pipefail
revision_root=~/scratch/sidecar-baselines/a7f3337e98515bc289781ef0a1eae7b9c2fe73a5
read -r -p 'Paste the exact approval record printed by Task 7 Step 1: ' approval_record
approval_digest_path="$approval_record.sha256"
test "$(sha256sum "$approval_record")" = "$(cat "$approval_digest_path")" || { echo "HARD STOP: approval record changed"; exit 1; }
approved_attempt_root=$(awk -F '\t' '$1 == "attempt-root" {print $2}' "$approval_record")
approved_manifest_digest=$(awk -F '\t' '$1 == "manifest-digest" {print $2}' "$approval_record")
approved_baseline_sha=$(awk -F '\t' '$1 == "baseline-sha" {print $2}' "$approval_record")
approved_feature_sha=$(awk -F '\t' '$1 == "feature-sha" {print $2}' "$approval_record")
test "$approved_baseline_sha" = a7f3337e98515bc289781ef0a1eae7b9c2fe73a5 || { echo "HARD STOP: approval baseline SHA mismatch"; exit 1; }
test "$(sha256sum "$approved_attempt_root/task-6-manifest.tsv" | awk '{print $1}')" = "$approved_manifest_digest" || { echo "HARD STOP: approved attempt changed"; exit 1; }
test "$(awk -F '\t' '$1 == "feature-branch" {print $2}' "$approved_attempt_root/task-6-manifest.tsv")" = "$approved_feature_sha" || { echo "HARD STOP: approval feature SHA mismatch"; exit 1; }
verify_approved_evidence() {
  local evidence_key=$1
  local evidence_path
  local evidence_digest
  evidence_path=$(awk -F '\t' -v key="$evidence_key" '$1 == "evidence" && $2 == key {print $3}' "$approval_record")
  evidence_digest=$(awk -F '\t' -v key="$evidence_key" '$1 == "evidence" && $2 == key {print $4}' "$approval_record")
  test -n "$evidence_path" && test -n "$evidence_digest" || { echo "HARD STOP: missing frozen evidence $evidence_key"; exit 1; }
  test "$(sha256sum "$evidence_path" | awk '{print $1}')" = "$evidence_digest" || { echo "HARD STOP: approved evidence changed: $evidence_key"; exit 1; }
}
for evidence_key in task-6-manifest final-parity-table parity-table rebased-real-projects current-main-signatures feature-signatures; do
  verify_approved_evidence "$evidence_key"
done
integration_root=~/scratch/sidecar-publish-a7f3337e-"$(basename "$approval_record" .tsv)"
test -d "$integration_root" || { echo "HARD STOP: missing approved integration worktree"; exit 1; }
merge_sha=$(git -C "$integration_root" rev-parse HEAD)
git -C "$integration_root" push origin HEAD:main
remote_main_sha=$(git -C "$integration_root" ls-remote origin refs/heads/main | awk '{print $1}')
test "$remote_main_sha" = "$merge_sha" || { echo "HARD STOP: remote main is $remote_main_sha"; exit 1; }
printf '%s\n' "$merge_sha" > "$approved_attempt_root/published-main.sha"
git -C ~/d/science/.worktrees/sidecar-retirement worktree remove "$integration_root"
git -C ~/d/science/.worktrees/sidecar-retirement branch -D sidecar-retirement-publish
```

Expected: the merge commit's first parent is the recorded remote SHA and
`git ls-remote` confirms that exact merge commit on `origin/main`.

If publication stops before the successful cleanup, retain the immutable
approval record and its SHA-256 file. Remove only the explicitly derived
temporary worktree and branch before retrying with that same approval record:

```bash
set -euo pipefail
toolkit_root=~/d/science/.worktrees/sidecar-retirement
read -r -p 'Paste the exact approval record printed by Task 7 Step 1: ' approval_record
test "$(sha256sum "$approval_record")" = "$(cat "$approval_record.sha256")" || { echo "HARD STOP: approval record changed"; exit 1; }
integration_root=~/scratch/sidecar-publish-a7f3337e-"$(basename "$approval_record" .tsv)"
if git -C "$toolkit_root" worktree list --porcelain | rg -Fqx "worktree $integration_root"; then
  git -C "$toolkit_root" worktree remove --force "$integration_root"
fi
git -C "$toolkit_root" branch -D sidecar-retirement-publish 2>/dev/null || true
git -C "$toolkit_root" worktree prune
```

---

### Task 8: Migrate `~/d/health/meta` atomically

**Files:** `pyproject.toml:13`, `uv.lock`, `AGENTS.md`; delete `validate_local.py`

**Entry gate:** Before creating a worktree, require the recorded Task 6
manifest SHA and the exact clean source snapshot. Drift means recapturing and
reverifying Task 6 before editing.

```bash
set -euo pipefail
revision_root=~/scratch/sidecar-baselines/a7f3337e98515bc289781ef0a1eae7b9c2fe73a5
attempt_root=$(cat "$revision_root/latest-attempt.txt")
source_root=~/d/health/meta
required_head=$(awk -F '\t' '$1 == "consumer" && $2 == "health-meta" {print $4}' "$attempt_root/task-6-manifest.tsv")
published_main_sha=$(cat "$attempt_root/published-main.sha")
test "$(sha256sum "$attempt_root/task-6-manifest.tsv")" = "$(cat "$attempt_root/task-6-manifest.sha256")" || { echo "HARD STOP: Task 6 manifest drift"; exit 1; }
test "$(git -C ~/d/science/.worktrees/sidecar-retirement ls-remote origin refs/heads/main | awk '{print $1}')" = "$published_main_sha" || { echo "HARD STOP: published main is not recorded SHA"; exit 1; }
test "$required_head" = 36ba8ec83f91d35ba82961836bfc1731b00d9e8b || { echo "HARD STOP: health/meta missing from manifest"; exit 1; }
test -z "$(git -C "$source_root" status --porcelain)" || { echo "HARD STOP: health/meta source drift"; exit 1; }
test "$(git -C "$source_root" rev-parse HEAD)" = "$required_head" || { echo "HARD STOP: health/meta HEAD drift; recapture Task 6"; exit 1; }
```

- [ ] **Step 1: Work in an isolated worktree**

The repository root is `~/d/health/meta`, **not** `~/d/health` — the latter is not a Git repository at all.

```bash
cd ~/d/health/meta && git rev-parse --show-toplevel   # confirm before proceeding
git worktree add .worktrees/sidecar-retirement -b sidecar-retirement
cd .worktrees/sidecar-retirement && git branch --show-current
```

- [ ] **Step 2: Update the explicit pin and relock**

Replace `rev = "3b72db60b8d591cf3dbac8ae25ca194f6cda9c8b"` in `[tool.uv.sources]` with the published SHA recorded by Task 7, then:

```bash
revision_root=~/scratch/sidecar-baselines/a7f3337e98515bc289781ef0a1eae7b9c2fe73a5
attempt_root=$(cat "$revision_root/latest-attempt.txt")
published_main_sha=$(cat "$attempt_root/published-main.sha")
uv lock && uv sync
rg -A2 '^name = "science"' uv.lock
rg -q "#$published_main_sha" uv.lock || { echo "FAIL: lock did not pin published SHA"; exit 1; }
```

Expected: the `source = { git = ... #<sha> }` line shows the Task 7 SHA.

- [ ] **Step 3: Delete the sidecar and update `AGENTS.md`**

```bash
git rm validate_local.py
```

Record in `AGENTS.md` that the reviews-are-not-evidence guardrail is now a toolkit check the project no longer owns.

- [ ] **Step 4: Verify, capturing status before parsing**

```bash
uv run --frozen science validate --all --strict --format json > /tmp/hm-after.json
status=$?
test "$status" -eq 0 || { echo "FAIL: validator exited $status, expected 0"; exit 1; }
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

Expected: no `FAIL` line and `OK`. The nine background papers are cited under `source_refs`, not `evidence_refs`, and both `paper:Tasci2022` provenance records already carry `evidence_tier: background` and `review_typed_source: true`.

- [ ] **Step 5: Commit atomically, merge, clean up**

```bash
git add -A && git commit -m "chore: adopt toolkit background-review check and drop the validation sidecar"
cd ~/d/health/meta && git branch --show-current   # must print the working branch; stop if not
git merge --no-ff sidecar-retirement
git worktree remove .worktrees/sidecar-retirement
```

This repo has **no GitHub remote** — commit and merge only, never push. It is also Dropbox-synced, so its primary checkout floats; verify the branch before merging.

---

### Task 9: Migrate `~/d/cancer/mechanisms/evolution` atomically

**Files:** `uv.lock:3062`, `AGENTS.md`; delete `validate_local.py`

**Entry gate:** Run the same manifest integrity and clean-snapshot gate before
editing; no migration is authorized after drift.

```bash
set -euo pipefail
revision_root=~/scratch/sidecar-baselines/a7f3337e98515bc289781ef0a1eae7b9c2fe73a5
attempt_root=$(cat "$revision_root/latest-attempt.txt")
source_root=~/d/cancer/mechanisms/evolution
required_head=$(awk -F '\t' '$1 == "consumer" && $2 == "evolution" {print $4}' "$attempt_root/task-6-manifest.tsv")
published_main_sha=$(cat "$attempt_root/published-main.sha")
test "$(sha256sum "$attempt_root/task-6-manifest.tsv")" = "$(cat "$attempt_root/task-6-manifest.sha256")" || { echo "HARD STOP: Task 6 manifest drift"; exit 1; }
test "$(git -C ~/d/science/.worktrees/sidecar-retirement ls-remote origin refs/heads/main | awk '{print $1}')" = "$published_main_sha" || { echo "HARD STOP: published main is not recorded SHA"; exit 1; }
test "$required_head" = 25fd2cb475807c8f5af0d2553244368c55fd3ad2 || { echo "HARD STOP: evolution missing from manifest"; exit 1; }
test -z "$(git -C "$source_root" status --porcelain)" || { echo "HARD STOP: evolution source drift"; exit 1; }
test "$(git -C "$source_root" rev-parse HEAD)" = "$required_head" || { echo "HARD STOP: evolution HEAD drift; recapture Task 6"; exit 1; }
```

Unqualified Git source; the revision lives only in `uv.lock`, currently `ed6b50dc`.

- [ ] **Step 1: Isolated worktree**

The repository root is `~/d/cancer/mechanisms/evolution`, **not** `~/d/cancer` — the latter is not a Git repository.

```bash
cd ~/d/cancer/mechanisms/evolution && git rev-parse --show-toplevel   # confirm
git worktree add .worktrees/sidecar-retirement -b sidecar-retirement
cd .worktrees/sidecar-retirement && git branch --show-current
```

- [ ] **Step 2: Relock to the Task 7 SHA**

```bash
revision_root=~/scratch/sidecar-baselines/a7f3337e98515bc289781ef0a1eae7b9c2fe73a5
attempt_root=$(cat "$revision_root/latest-attempt.txt")
published_main_sha=$(cat "$attempt_root/published-main.sha")
uv lock --upgrade-package science && uv sync
rg -A2 '^name = "science"' uv.lock
rg -q "#$published_main_sha" uv.lock || { echo "FAIL: lock did not pin published SHA"; exit 1; }
```

- [ ] **Step 3: Delete the sidecar and update `AGENTS.md`**

```bash
git rm validate_local.py
```

- [ ] **Step 4: Run the exact original command that crashed**

```bash
uv run --frozen science validate --all --strict --format json > /tmp/evo-after.json
status=$?
test "$status" -eq 0 || { echo "FAIL: validator exited $status, expected 0"; exit 1; }
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

Expected: no `FAIL` line, `OK`, no traceback. This is the Task 1 Step 2 reproduction now resolved.

- [ ] **Step 5: Confirm the notice out-of-band**

```bash
uv run --frozen science validate --all --strict --verbose | rg 'no status:background papers'
```

Expected: a match — all 15 papers are active, so a notice and zero warnings.

- [ ] **Step 6: Commit atomically, merge, clean up**

```bash
git add -A && git commit -m "chore: adopt toolkit background-review check and drop the validation sidecar"
cd ~/d/cancer/mechanisms/evolution && git branch --show-current   # Dropbox-synced; verify
git merge --no-ff sidecar-retirement
git worktree remove .worktrees/sidecar-retirement
```

---

### Task 10: Migrate `~/d/protein-landscape` atomically

**Files:** `uv.lock:4412`, `AGENTS.md`; delete `validate_local.py`

**Entry gate:** Run the same manifest integrity and clean-snapshot gate before
editing; no migration is authorized after drift.

```bash
set -euo pipefail
revision_root=~/scratch/sidecar-baselines/a7f3337e98515bc289781ef0a1eae7b9c2fe73a5
attempt_root=$(cat "$revision_root/latest-attempt.txt")
source_root=~/d/protein-landscape
required_head=$(awk -F '\t' '$1 == "consumer" && $2 == "protein-landscape" {print $4}' "$attempt_root/task-6-manifest.tsv")
published_main_sha=$(cat "$attempt_root/published-main.sha")
test "$(sha256sum "$attempt_root/task-6-manifest.tsv")" = "$(cat "$attempt_root/task-6-manifest.sha256")" || { echo "HARD STOP: Task 6 manifest drift"; exit 1; }
test "$(git -C ~/d/science/.worktrees/sidecar-retirement ls-remote origin refs/heads/main | awk '{print $1}')" = "$published_main_sha" || { echo "HARD STOP: published main is not recorded SHA"; exit 1; }
test "$required_head" = 6796628c06a562ff45029f317a0f0fdf1a2fec9e || { echo "HARD STOP: protein-landscape missing from manifest"; exit 1; }
test -z "$(git -C "$source_root" status --porcelain)" || { echo "HARD STOP: protein-landscape source drift"; exit 1; }
test "$(git -C "$source_root" rev-parse HEAD)" = "$required_head" || { echo "HARD STOP: protein-landscape HEAD drift; recapture Task 6"; exit 1; }
```

Its check is **not** promoted — the expensive-artifact check becomes a project-owned command with nothing enforcing it (design §4).

- [ ] **Step 1: Isolated worktree, relock**

```bash
cd ~/d/protein-landscape && git worktree add .worktrees/sidecar-retirement -b sidecar-retirement
cd .worktrees/sidecar-retirement
revision_root=~/scratch/sidecar-baselines/a7f3337e98515bc289781ef0a1eae7b9c2fe73a5
attempt_root=$(cat "$revision_root/latest-attempt.txt")
published_main_sha=$(cat "$attempt_root/published-main.sha")
uv lock --upgrade-package science && uv sync
rg -A2 '^name = "science"' uv.lock
rg -q "#$published_main_sha" uv.lock || { echo "FAIL: lock did not pin published SHA"; exit 1; }
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
status=$?
test "$status" -eq 0 || { echo "FAIL: artifact checker exited $status"; exit 1; }
```

- [ ] **Step 5: Verify validation**

```bash
uv run --frozen science validate --all --strict --format json > /tmp/pl-after.json
status=$?
test "$status" -eq 0 || { echo "FAIL: validator exited $status, expected 0"; exit 1; }
python3 -c "
import json; d=json.load(open('/tmp/pl-after.json')); print(d['summary'])
assert 'validate.python-sidecar-removed' not in {r.get('rule') for r in d['results']}
print('OK')"
```

Expected: no `FAIL` line, `OK`, no traceback — the crash in the method-slice inventory is resolved.

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
| 5.3.1 | exactly one `validate.python-sidecar-removed`; **valid CLI JSON, no traceback** | 3 (`test_cli_emits_valid_json_with_one_retirement_rule`) |
| 5.3.2 | never imported or executed (`sys.modules` + sentinel) | 3 |
| 5.3.3 | project-authored `FindingRule` cannot enter the registry | pre-existing; Task 6 full suite |
| 5.3.4 | the two sidecar rules are distinct | 3 |
| 5.3.5 | three rules fire; both typing conditions yield two findings | 2 |
| 5.3.6 | check present in `full` and `commit` profiles, not `--all`-gated | 2 |
| 5.3.7 | the check can fail — mutate, confirm red, restore green | 2, steps 9–10 |

**On §5.3.1:** the unit tests call `run()` directly, which never exercises the CLI layer where the original crash surfaced as a traceback. The `CliRunner` test is what actually covers the requirement; the `run()` tests cover the finding itself.

**On §5.3.7:** §5.2 means the real corpus cannot falsify this check — it is compliant. Task 2's fixtures are the only falsification available, which is why steps 9 and 10 are executable steps rather than a closing remark.

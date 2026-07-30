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

Both must hold before any fresh Task 6 verification. Neither is optional.
`origin/main` is moving, so the plan does not embed today's tip. It fetches and
freezes one exact commit in
`.superpowers/sdd/2026-07-29-validation-sidecar-retirement-implementation/reconciled-origin-main.sha`;
that file is the sole baseline authority for the rebase, evidence paths,
manifest, approval, and publication.

- [ ] **P1: Freshly fetch and record the reconciled `origin/main` SHA.**

```bash
set -euo pipefail
toolkit_root=~/d/science/.worktrees/sidecar-retirement
sdd_workspace="$toolkit_root/.superpowers/sdd/2026-07-29-validation-sidecar-retirement-implementation"
plan3_sha=a7f3337e98515bc289781ef0a1eae7b9c2fe73a5
git -C "$toolkit_root" fetch --prune origin
recorded_origin_main_sha=$(git -C "$toolkit_root" rev-parse origin/main)
git -C "$toolkit_root" merge-base --is-ancestor "$plan3_sha" "$recorded_origin_main_sha" || {
  echo "HARD STOP: fetched origin/main does not contain completed Finding Convergence Plan 3"
  exit 1
}
printf '%s\n' "$recorded_origin_main_sha" > "$sdd_workspace/reconciled-origin-main.sha"
test "$(cat "$sdd_workspace/reconciled-origin-main.sha")" = "$recorded_origin_main_sha"
```

- [ ] **P2: Rebase `sidecar-retirement` onto that exact remote commit before verification.**

Use an ordinary rebase: do **not** pass `--reapply-cherry-picks`. Git is expected
to skip feature commits `b9eecc7a` and `3f6ecafa`, whose patches are already
present upstream. The only expected conflict is
`science/tests/validate/test_checks_labnote_export.py` while replaying
`ecd2960a`. Any other conflict, a conflict at another replayed commit, or a
clean rebase where this expected overlap did not occur is a hard stop for
reassessment.

```bash
set -euo pipefail
toolkit_root=~/d/science/.worktrees/sidecar-retirement
sdd_workspace="$toolkit_root/.superpowers/sdd/2026-07-29-validation-sidecar-retirement-implementation"
recorded_origin_main_sha=$(cat "$sdd_workspace/reconciled-origin-main.sha")
test "$(git -C "$toolkit_root" rev-parse origin/main)" = "$recorded_origin_main_sha" || {
  echo "HARD STOP: fetched origin/main no longer matches the frozen baseline"
  exit 1
}
baseline_budget_test=$(git -C "$toolkit_root" show "$recorded_origin_main_sha:science/tests/test_budget_boundary.py")
rg -q '"budgeted": 69' <<< "$baseline_budget_test"
rg -q '"exempt": 122' <<< "$baseline_budget_test"
rg -q '"deferred": 102' <<< "$baseline_budget_test"
pre_rebase_head=$(git -C "$toolkit_root" rev-parse HEAD)
cherry_output=$(git -C "$toolkit_root" cherry "$recorded_origin_main_sha" "$pre_rebase_head")
mapfile -t actual_patch_equivalent_shas < <(
  awk '$1 == "-" {print $2}' <<< "$cherry_output" | LC_ALL=C sort
)
mapfile -t expected_patch_equivalent_shas < <(
  printf '%s\n' \
    "$(git -C "$toolkit_root" rev-parse 'b9eecc7a^{commit}')" \
    "$(git -C "$toolkit_root" rev-parse '3f6ecafa^{commit}')" |
    LC_ALL=C sort
)
test "${actual_patch_equivalent_shas[*]}" = "${expected_patch_equivalent_shas[*]}" || {
  printf 'HARD STOP: unexpected patch-equivalent set before rebase\nexpected: %s\nactual: %s\n' \
    "${expected_patch_equivalent_shas[*]}" "${actual_patch_equivalent_shas[*]}"
  exit 1
}
expected_replay_count=$(awk '$1 == "+" {count++} END {print count + 0}' <<< "$cherry_output")
test "$expected_replay_count" -gt 0 || {
  echo "HARD STOP: pre-rebase unique replay count is not positive"
  exit 1
}
rebase_audit="$sdd_workspace/expected-rebase-replay.tsv"
printf 'baseline\t%s\npre-rebase-head\t%s\nexpected-unique-replays\t%s\npatch-equivalent\t%s\npatch-equivalent\t%s\n' \
  "$recorded_origin_main_sha" "$pre_rebase_head" "$expected_replay_count" \
  "${expected_patch_equivalent_shas[0]}" "${expected_patch_equivalent_shas[1]}" \
  > "$rebase_audit"
set +e
git -C "$toolkit_root" rebase "$recorded_origin_main_sha"
rebase_status=$?
set -e
test "$rebase_status" -ne 0 || {
  echo "HARD STOP: expected the verified Labnote test conflict; reassess the replay"
  exit 1
}
mapfile -t unmerged_paths < <(git -C "$toolkit_root" diff --name-only --diff-filter=U)
expected_paths=(science/tests/validate/test_checks_labnote_export.py)
test "${unmerged_paths[*]}" = "${expected_paths[*]}" || {
  printf 'HARD STOP: unexpected rebase conflicts: %s\n' "${unmerged_paths[*]}"
  exit 1
}
current_rebase_subject=$(git -C "$toolkit_root" show -s --format=%s REBASE_HEAD)
test "$current_rebase_subject" = 'fix(validate): close sidecar retirement test gaps' || {
    echo "HARD STOP: Labnote conflict occurred while replaying an unexpected commit"
    exit 1
  }
printf '%s\n' 'PAUSE: compose the verified Labnote test conflict, then run the continuation block.'
exit 2
```

Resolve the one file by retaining **all** Labnote tests from upstream
`f65c85f3`, while changing only
`test_labnote_export_check_is_registered` to preserve the feature's registry
isolation:

```python
def test_labnote_export_check_is_registered() -> None:
    import sys

    import science_tool.validate.checks as checks

    module_name = "science_tool.validate.checks.labnote_export"
    original_entries = list(checks.CANONICAL_CHECKS)
    original_module = sys.modules.get(module_name)
    try:
        checks.clear_checks_for_tests()
        sys.modules.pop(module_name, None)
        checks._load_canonical_checks()

        assert any(entry.fn.__name__ == "check_labnote_export" for entry in checks.CANONICAL_CHECKS)
    finally:
        checks.CANONICAL_CHECKS[:] = original_entries
        if original_module is None:
            sys.modules.pop(module_name, None)
        else:
            sys.modules[module_name] = original_module
```

Do not choose either whole side of the conflict: that would discard either the
upstream contract tests or the feature's `try/finally` restoration. Apply the
composed edit with `apply_patch`, then run this continuation block.

```bash
set -euo pipefail
toolkit_root=~/d/science/.worktrees/sidecar-retirement
conflict_path=science/tests/validate/test_checks_labnote_export.py
test -n "$(git -C "$toolkit_root" rebase --show-current-patch)" || {
  echo "HARD STOP: no paused rebase to continue"; exit 1;
}
test "$(git -C "$toolkit_root" diff --name-only --diff-filter=U)" = "$conflict_path" || {
  echo "HARD STOP: unexpected or missing unmerged path"; exit 1;
}
if rg -n '^(<<<<<<<|=======|>>>>>>>)' "$toolkit_root/$conflict_path"; then
  echo "HARD STOP: conflict markers remain"
  exit 1
fi
git -C "$toolkit_root" diff --check
git -C "$toolkit_root" add "$conflict_path"
GIT_EDITOR=true git -C "$toolkit_root" rebase --continue
test -z "$(git -C "$toolkit_root" diff --name-only --diff-filter=U)" || {
  echo "HARD STOP: unresolved rebase paths remain"; exit 1;
}
recorded_origin_main_sha=$(cat "$toolkit_root/.superpowers/sdd/2026-07-29-validation-sidecar-retirement-implementation/reconciled-origin-main.sha")
rebase_audit="$toolkit_root/.superpowers/sdd/2026-07-29-validation-sidecar-retirement-implementation/expected-rebase-replay.tsv"
test -s "$rebase_audit" || {
  echo "HARD STOP: missing pre-rebase replay audit"; exit 1;
}
test "$(awk -F '\t' '$1 == "baseline" {print $2}' "$rebase_audit")" = "$recorded_origin_main_sha" || {
  echo "HARD STOP: replay audit baseline differs from the frozen baseline"; exit 1;
}
mapfile -t audited_patch_equivalent_shas < <(
  awk -F '\t' '$1 == "patch-equivalent" {print $2}' "$rebase_audit" | LC_ALL=C sort
)
mapfile -t expected_patch_equivalent_shas < <(
  printf '%s\n' \
    "$(git -C "$toolkit_root" rev-parse 'b9eecc7a^{commit}')" \
    "$(git -C "$toolkit_root" rev-parse '3f6ecafa^{commit}')" |
    LC_ALL=C sort
)
test "${audited_patch_equivalent_shas[*]}" = "${expected_patch_equivalent_shas[*]}" || {
  echo "HARD STOP: replay audit patch-equivalent set is incomplete or unexpected"; exit 1;
}
expected_replay_count=$(awk -F '\t' '$1 == "expected-unique-replays" {print $2}' "$rebase_audit")
[[ "$expected_replay_count" =~ ^[1-9][0-9]*$ ]] || {
  echo "HARD STOP: invalid expected replay count in pre-rebase audit"; exit 1;
}
actual_replay_count=$(git -C "$toolkit_root" rev-list --count "$recorded_origin_main_sha..HEAD")
test "$actual_replay_count" -eq "$expected_replay_count" || {
  echo "HARD STOP: rebase produced $actual_replay_count commits above baseline; expected $expected_replay_count"
  exit 1
}
rebased_subjects=$(git -C "$toolkit_root" log --format=%s "$recorded_origin_main_sha..HEAD")
for skipped_subject in \
  'fix(schema): drop the premature status enum via mixin-concept-1.1' \
  'docs(schema-closure): record the concept status-enum closure'; do
  if rg -Fxq "$skipped_subject" <<< "$rebased_subjects"; then
    echo "HARD STOP: patch-equivalent commit was replayed instead of skipped: $skipped_subject"
    exit 1
  fi
done
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
  tests/validate/test_checks_labnote_export.py \
  tests/test_labnote_view_contract.py \
  tests/test_labnote_export.py \
  tests/test_budget_boundary.py )
```

Expected: Git reports the two patch-equivalent commits as skipped; the single
Labnote conflict is resolved by composition; every upstream Labnote test
remains; the feature registry-restoration guard remains; the focused tests
pass; the frozen baseline partition is `69 / 122 / 102`; and the rebased
feature partition is `69 / 121 / 102`. Before starting the rebase, the gate
requires `git cherry`'s complete minus set to be exactly `b9eecc7a` and
`3f6ecafa` and records the plus count in ignored SDD execution state. After
continuation, the number of commits above the frozen baseline must equal that
recorded unique-replay count and both duplicate subjects must be absent, so no
additional commit can be silently skipped.

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
  targets after the required rebase. Their `a7f3337e` revision is historical
  evidence only; Task 6 recaptures the four canonical reports from the
  run-time-frozen reconciled `origin/main` and identical pinned consumer
  snapshots.

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
Every later attempt and plan revision through
`8e2043781b8baa2dc80f5aa1f064aa3540235702` is also invalidated as approval
evidence by the current-main reassessment. Preserve all outputs as diagnostic
evidence and start a fresh attempt from the commit containing this amended
gate and the run-time-frozen baseline.

- [ ] **Step 1: Rebase on the frozen current main, compose the Labnote overlap, and run focused tests first**

Run Preconditions P1 and P2. The baseline must report
`69 budgeted / 122 exempt / 102 deferred`; the feature removes
`project artifacts port-validate-sidecar` and must report
`69 budgeted / 121 exempt / 102 deferred`. Confirm the composed Labnote tests
and resulting budget partition before any broader verification.

```bash
set -euo pipefail
toolkit_root=~/d/science/.worktrees/sidecar-retirement
( cd "$toolkit_root/science" && uv run --frozen pytest -q tests/test_budget_boundary.py )
rg -n 'findings migrate-acceptances|port-validate-sidecar|69 budgeted|121 exempt|102 deferred|try:|finally:' \
  "$toolkit_root/science/src/science_tool/budget/registry.py" \
  "$toolkit_root/science/tests/test_budget_boundary.py" \
  "$toolkit_root/science/tests/validate/test_checks_labnote_export.py"
```

Expected: focused budget tests pass and the inspected registry/test evidence
states `69 budgeted / 121 exempt / 102 deferred`.

- [ ] **Step 2: Create immutable consumer and real-project snapshots and initialize the Task 6 manifest**

The historical `~/scratch/sidecar-baselines/` directory is read-only evidence.
Each retry gets a new UTC-labelled attempt beneath the frozen-baseline
directory; never reuse or delete a prior attempt. Use the exact same consumer
snapshots for before and after reports. The three canonical consumers retain
their exact reviewed SHAs. Freeze the other six external repositories at their
current HEADs. All nine external repositories become detached worktrees at
their captured commits under `$attempt_root/real-project-home/d/...`, which is
the synthetic `HOME` used by both marker runs. Do not use a live project path
for verification. The after toolkit and science/meta likewise come from an
immutable detached worktree at the recorded feature SHA.

```bash
set -euo pipefail
toolkit_root=~/d/science/.worktrees/sidecar-retirement
sdd_workspace="$toolkit_root/.superpowers/sdd/2026-07-29-validation-sidecar-retirement-implementation"
baseline_toolkit_sha=$(cat "$sdd_workspace/reconciled-origin-main.sha")
feature_branch_sha=$(git -C "$toolkit_root" rev-parse HEAD)
test -z "$(git -C "$toolkit_root" status --porcelain)" || {
  echo "HARD STOP: feature worktree is dirty"; exit 1;
}
attempt_id=$(date -u +%Y%m%dT%H%M%SZ)
revision_root=~/scratch/sidecar-baselines/"$baseline_toolkit_sha"
attempt_root="$revision_root/attempt-$attempt_id"
test ! -e "$attempt_root" || { echo "HARD STOP: attempt collision at $attempt_root"; exit 1; }
mkdir -p "$attempt_root/real-project-home/d"
printf '%s\n' "$attempt_root" > "$revision_root/latest-attempt.txt"
real_project_names=(
  natural-systems
  multiple-myeloma
  post-acute-infection
  health-meta
  evolution
  cbioportal
  protein-landscape
  seq-feats
  science-commons
)
declare -A source_root=(
  [natural-systems]=~/d/natural-systems
  [multiple-myeloma]=~/d/cancer/cancer-types/multiple-myeloma
  [post-acute-infection]=~/d/health/processes/post-acute-infection
  [health-meta]=~/d/health/meta
  [evolution]=~/d/cancer/mechanisms/evolution
  [cbioportal]=~/d/cancer/data-sources/cbioportal
  [protein-landscape]=~/d/protein-landscape
  [seq-feats]=~/d/seq-feats
  [science-commons]=~/d/science-commons
)
declare -A source_label=(
  [natural-systems]='~/d/natural-systems'
  [multiple-myeloma]='~/d/cancer/cancer-types/multiple-myeloma'
  [post-acute-infection]='~/d/health/processes/post-acute-infection'
  [health-meta]='~/d/health/meta'
  [evolution]='~/d/cancer/mechanisms/evolution'
  [cbioportal]='~/d/cancer/data-sources/cbioportal'
  [protein-landscape]='~/d/protein-landscape'
  [seq-feats]='~/d/seq-feats'
  [science-commons]='~/d/science-commons'
)
declare -A snapshot_relpath=(
  [natural-systems]=d/natural-systems
  [multiple-myeloma]=d/cancer/cancer-types/multiple-myeloma
  [post-acute-infection]=d/health/processes/post-acute-infection
  [health-meta]=d/health/meta
  [evolution]=d/cancer/mechanisms/evolution
  [cbioportal]=d/cancer/data-sources/cbioportal
  [protein-landscape]=d/protein-landscape
  [seq-feats]=d/seq-feats
  [science-commons]=d/science-commons
)
declare -A required_head=(
  [health-meta]=36ba8ec83f91d35ba82961836bfc1731b00d9e8b
  [evolution]=25fd2cb475807c8f5af0d2553244368c55fd3ad2
  [protein-landscape]=6796628c06a562ff45029f317a0f0fdf1a2fec9e
)
printf 'toolkit-before\t%s\nfeature-branch\t%s\n' \
  "$baseline_toolkit_sha" "$feature_branch_sha" > "$attempt_root/task-6-manifest.tsv"
: > "$attempt_root/real-project-snapshot-inventory.tsv"
for project_name in "${real_project_names[@]}"; do
  actual_head=$(git -C "${source_root[$project_name]}" rev-parse HEAD)
  if [[ -n "${required_head[$project_name]:-}" ]]; then
    test -z "$(git -C "${source_root[$project_name]}" status --porcelain)" || {
      echo "HARD STOP: $project_name canonical source checkout is dirty"; exit 1;
    }
    test "$actual_head" = "${required_head[$project_name]}" || {
      echo "HARD STOP: $project_name is $actual_head, expected ${required_head[$project_name]}"; exit 1;
    }
  fi
  tree_sha=$(git -C "${source_root[$project_name]}" rev-parse "$actual_head^{tree}")
  snapshot_path="$attempt_root/real-project-home/${snapshot_relpath[$project_name]}"
  mkdir -p "$(dirname "$snapshot_path")"
  git -C "${source_root[$project_name]}" worktree add --detach "$snapshot_path" "$actual_head"
  test -z "$(git -C "$snapshot_path" status --porcelain=v1 --ignored --untracked-files=all)" || {
    echo "HARD STOP: $project_name detached snapshot is not completely clean"; exit 1;
  }
  test "$(git -C "$snapshot_path" rev-parse HEAD)" = "$actual_head"
  test "$(git -C "$snapshot_path" rev-parse 'HEAD^{tree}')" = "$tree_sha"
  printf 'real-project-snapshot\t%s\t%s\t%s\t%s\t%s\tclean\n' \
    "$project_name" "${source_label[$project_name]}" "$actual_head" "$tree_sha" "$snapshot_path" \
    >> "$attempt_root/real-project-snapshot-inventory.tsv"
  if [[ -n "${required_head[$project_name]:-}" ]]; then
    printf 'consumer\t%s\t%s\t%s\tclean\n' \
      "$project_name" "${source_label[$project_name]}" "$actual_head" \
      >> "$attempt_root/task-6-manifest.tsv"
  fi
done
cat "$attempt_root/real-project-snapshot-inventory.tsv" >> "$attempt_root/task-6-manifest.tsv"
git -C "$toolkit_root" worktree add --detach "$attempt_root/toolkit-after" "$feature_branch_sha"
test -z "$(git -C "$attempt_root/toolkit-after" status --porcelain)" || {
  echo "HARD STOP: detached after-toolkit worktree is dirty"; exit 1;
}
test "$(git -C "$attempt_root/toolkit-after" rev-parse HEAD)" = "$feature_branch_sha" || {
  echo "HARD STOP: detached after-toolkit SHA differs from feature branch"; exit 1;
}
science_meta_tree=$(git -C "$attempt_root/toolkit-after" rev-parse HEAD:meta)
printf 'consumer\tscience-meta\t%s\t%s\tclean\ntoolkit-after\t%s\nattempt-root\t%s\n' \
  "$attempt_root/toolkit-after/meta" "$science_meta_tree" "$feature_branch_sha" "$attempt_root" \
  >> "$attempt_root/task-6-manifest.tsv"
```

**Retry cleanup:** if an attempt stops before verification, read its path from
`latest-attempt.txt` and remove only the registered detached worktrees; do not
delete its reports or directory. The nine external paths are derived from
`$attempt_root` plus the explicit source-root and snapshot-relative-path
arrays, not from inventory or manifest rows that may not have been appended
when Step 2 stopped. The two toolkit paths are likewise deterministic. Absent
or never-registered paths are safe. This command is safe to repeat and lets
the next run create a fresh attempt directory:

```bash
set -euo pipefail
toolkit_root=~/d/science/.worktrees/sidecar-retirement
sdd_workspace="$toolkit_root/.superpowers/sdd/2026-07-29-validation-sidecar-retirement-implementation"
baseline_sha=$(cat "$sdd_workspace/reconciled-origin-main.sha")
revision_root=~/scratch/sidecar-baselines/"$baseline_sha"
attempt_root=$(cat "$revision_root/latest-attempt.txt")
for worktree_path in "$attempt_root/toolkit-before" "$attempt_root/toolkit-after"; do
  if git -C "$toolkit_root" worktree list --porcelain | rg -Fqx "worktree $worktree_path"; then
    git -C "$toolkit_root" worktree remove --force "$worktree_path"
  fi
done
git -C "$toolkit_root" worktree prune
declare -A source_root=(
  [natural-systems]=~/d/natural-systems
  [multiple-myeloma]=~/d/cancer/cancer-types/multiple-myeloma
  [post-acute-infection]=~/d/health/processes/post-acute-infection
  [health-meta]=~/d/health/meta
  [evolution]=~/d/cancer/mechanisms/evolution
  [cbioportal]=~/d/cancer/data-sources/cbioportal
  [protein-landscape]=~/d/protein-landscape
  [seq-feats]=~/d/seq-feats
  [science-commons]=~/d/science-commons
)
real_project_names=(
  natural-systems
  multiple-myeloma
  post-acute-infection
  health-meta
  evolution
  cbioportal
  protein-landscape
  seq-feats
  science-commons
)
declare -A snapshot_relpath=(
  [natural-systems]=d/natural-systems
  [multiple-myeloma]=d/cancer/cancer-types/multiple-myeloma
  [post-acute-infection]=d/health/processes/post-acute-infection
  [health-meta]=d/health/meta
  [evolution]=d/cancer/mechanisms/evolution
  [cbioportal]=d/cancer/data-sources/cbioportal
  [protein-landscape]=d/protein-landscape
  [seq-feats]=d/seq-feats
  [science-commons]=d/science-commons
)
for project_name in "${real_project_names[@]}"; do
  worktree_path="$attempt_root/real-project-home/${snapshot_relpath[$project_name]}"
  if git -C "${source_root[$project_name]}" worktree list --porcelain | rg -Fqx "worktree $worktree_path"; then
    git -C "${source_root[$project_name]}" worktree remove --force "$worktree_path"
  fi
  git -C "${source_root[$project_name]}" worktree prune
done
```

- [ ] **Step 3: Run broader verification sequentially and compare the complete real-project marker with stable current-main state**

Run no suites concurrently. The toolkit suite, model suite, and snapshot marker
must be rerun from the rebased feature worktree. Run the complete
`real_projects` marker once from the immutable current-main toolkit and once
from the immutable feature toolkit. Capture the full logs and statuses, then
require equal statuses and exact equality of the sorted `FAILED ...`
signatures. Empty signature files are valid only when both markers exit zero.
A current-main-only or feature-only failure is a hard stop. Matching nonzero
markers remain visible external-failure evidence; they are not green.

Run both markers with the identical synthetic `HOME` created in Step 2. Bracket
the runs with byte-identical snapshot-state records for all nine detached
worktrees. Each row must match the manifest's captured HEAD and tree SHA and
must remain completely clean. Each capture runs the complete, cheap
`git status --porcelain=v1 --ignored --untracked-files=all` check, so any
tracked modification or newly created ignored or untracked path stops the
attempt. The between-markers capture completes before the feature marker can
start, so no state created by the current-main marker can be hidden from the
feature comparison. The marker uses an explicit host `UV_CACHE_DIR`; it must
not materialize a `.venv`, cache, or other ignored payload in a snapshot. The
gate never reads a live project checkout.
`science/meta` remains supplied independently by each immutable toolkit
worktree.
If an explicit `--basetemp` is used for any suite, precheck that neither that
path nor any ancestor contains a `.git` marker; the default pytest temp path is
preferred.

```bash
set -euo pipefail
toolkit_root=~/d/science/.worktrees/sidecar-retirement
sdd_workspace="$toolkit_root/.superpowers/sdd/2026-07-29-validation-sidecar-retirement-implementation"
baseline_sha=$(cat "$sdd_workspace/reconciled-origin-main.sha")
revision_root=~/scratch/sidecar-baselines/"$baseline_sha"
attempt_root=$(cat "$revision_root/latest-attempt.txt")
git -C "$toolkit_root" worktree add --detach "$attempt_root/toolkit-before" "$baseline_sha"
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

capture_snapshot_state() {
  local output_path=$1
  test ! -e "$output_path" || {
    echo "HARD STOP: snapshot-state capture path already exists: $output_path"; exit 1;
  }
  : > "$output_path"
  while IFS=$'\t' read -r row_kind project_name source_label expected_head expected_tree snapshot_path expected_clean; do
    [[ "$row_kind" = real-project-snapshot ]] || continue
    test "$expected_clean" = clean
    test -z "$(git -C "$snapshot_path" status --porcelain=v1 --ignored --untracked-files=all)" || {
      echo "HARD STOP: detached snapshot is no longer completely clean: $project_name"; exit 1;
    }
    actual_head=$(git -C "$snapshot_path" rev-parse HEAD)
    actual_tree=$(git -C "$snapshot_path" rev-parse 'HEAD^{tree}')
    test "$actual_head" = "$expected_head" && test "$actual_tree" = "$expected_tree" || {
      echo "HARD STOP: detached snapshot identity changed: $project_name"; exit 1;
    }
    printf 'real-project-snapshot\t%s\t%s\t%s\t%s\t%s\tclean\n' \
      "$project_name" "$source_label" "$actual_head" "$actual_tree" "$snapshot_path" \
      >> "$output_path"
  done < "$attempt_root/task-6-manifest.tsv"
  test "$(wc -l < "$output_path")" -eq 9 || {
    echo "HARD STOP: snapshot-state record does not contain exactly nine projects"; exit 1;
  }
}
run_real_project_marker() {
  local command_key=$1
  local suite_dir=$2
  local output_path=$3
  local marker_home="$attempt_root/real-project-home"
  local host_uv_cache="${UV_CACHE_DIR:-$HOME/.cache/uv}"
  set +e
  ( cd "$suite_dir" && HOME="$marker_home" UV_CACHE_DIR="$host_uv_cache" \
      uv run --frozen pytest -m real_projects ) > "$output_path" 2>&1
  local marker_status=$?
  set -e
  printf 'command\t%s\tcd %s && HOME=%s UV_CACHE_DIR=%s uv run --frozen pytest -m real_projects\texit\t%s\t%s\n' \
    "$command_key" "$suite_dir" "$marker_home" "$host_uv_cache" "$marker_status" "$output_path" \
    >> "$attempt_root/task-6-manifest.tsv"
}

capture_snapshot_state "$attempt_root/snapshot-state-before-current-main.tsv"
cmp -s "$attempt_root/real-project-snapshot-inventory.tsv" \
  "$attempt_root/snapshot-state-before-current-main.tsv" || {
    echo "HARD STOP: initial snapshot state differs from captured inventory"; exit 1;
  }
run_real_project_marker current-main-real-project-marker \
  "$attempt_root/toolkit-before/science" "$attempt_root/current-main-real-projects.txt"
capture_snapshot_state "$attempt_root/snapshot-state-between-real-project-markers.tsv"
if ! cmp -s "$attempt_root/snapshot-state-before-current-main.tsv" \
  "$attempt_root/snapshot-state-between-real-project-markers.tsv"; then
  diff -u "$attempt_root/snapshot-state-before-current-main.tsv" \
    "$attempt_root/snapshot-state-between-real-project-markers.tsv" || true
  echo "HARD STOP: detached snapshot state changed during the current-main marker; preserve this attempt and start fresh"
  exit 1
fi
run_real_project_marker feature-real-project-marker \
  "$attempt_root/toolkit-after/science" "$attempt_root/feature-real-projects.txt"
capture_snapshot_state "$attempt_root/snapshot-state-after-feature.tsv"
if ! cmp -s "$attempt_root/snapshot-state-before-current-main.tsv" \
  "$attempt_root/snapshot-state-after-feature.tsv"; then
  diff -u "$attempt_root/snapshot-state-before-current-main.tsv" \
    "$attempt_root/snapshot-state-after-feature.tsv" || true
  echo "HARD STOP: detached snapshot state changed during the feature marker; preserve this attempt and start fresh"
  exit 1
fi

for marker_label in current-main feature; do
  marker_log="$attempt_root/$marker_label-real-projects.txt"
  raw_signatures="$attempt_root/$marker_label-real-project-failure-signatures.unsorted.txt"
  sorted_signatures="$attempt_root/$marker_label-real-project-failure-signatures.txt"
  set +e
  rg --no-filename '^FAILED ' "$marker_log" > "$raw_signatures"
  rg_status=$?
  set -e
  test "$rg_status" -le 1 || {
    echo "HARD STOP: could not extract failure signatures from $marker_log"; exit 1;
  }
  LC_ALL=C sort "$raw_signatures" > "$sorted_signatures"
done

current_main_real_status=$(awk -F '\t' '$1 == "command" && $2 == "current-main-real-project-marker" {print $5}' "$attempt_root/task-6-manifest.tsv")
feature_real_status=$(awk -F '\t' '$1 == "command" && $2 == "feature-real-project-marker" {print $5}' "$attempt_root/task-6-manifest.tsv")
test -n "$current_main_real_status" && test -n "$feature_real_status" || {
  echo "HARD STOP: missing full real-project marker status"; exit 1;
}
test "$current_main_real_status" = "$feature_real_status" || {
  echo "HARD STOP: full real-project marker statuses differ: current main $current_main_real_status, feature $feature_real_status"
  exit 1
}
case "$current_main_real_status" in
  0)
    test ! -s "$attempt_root/current-main-real-project-failure-signatures.txt" \
      && test ! -s "$attempt_root/feature-real-project-failure-signatures.txt" || {
        echo "HARD STOP: a green marker emitted FAILED signatures"; exit 1;
      }
    ;;
  1)
    test -s "$attempt_root/current-main-real-project-failure-signatures.txt" \
      && test -s "$attempt_root/feature-real-project-failure-signatures.txt" || {
        echo "HARD STOP: a failing marker has no FAILED signatures"; exit 1;
      }
    ;;
  *)
    echo "HARD STOP: full real-project markers exited $current_main_real_status, not a test result"
    exit 1
    ;;
esac
diff -u "$attempt_root/current-main-real-project-failure-signatures.txt" \
  "$attempt_root/feature-real-project-failure-signatures.txt" || {
    echo "HARD STOP: current-main-only or feature-only real-project failure"; exit 1;
  }
```

Record matching nonzero full-marker statuses and their complete sorted
signatures in the final parity evidence. Step 6 is the single owner of the
marker-log, signature, and snapshot-state manifest artifact rows and checksums.
Matching snapshot failures remain visible evidence, not a green result or an
implicit exception.

- [ ] **Step 4: Recapture four canonical before reports from the frozen baseline and pinned snapshots**

Build the before environment from the exact old toolkit worktree, then write
only into the new revision-labelled directory. The source path for science/meta
is the rebased feature worktree's migrated tree for both before and after.

```bash
set -euo pipefail
toolkit_root=~/d/science/.worktrees/sidecar-retirement
sdd_workspace="$toolkit_root/.superpowers/sdd/2026-07-29-validation-sidecar-retirement-implementation"
baseline_sha=$(cat "$sdd_workspace/reconciled-origin-main.sha")
revision_root=~/scratch/sidecar-baselines/"$baseline_sha"
attempt_root=$(cat "$revision_root/latest-attempt.txt")
uv venv "$attempt_root/before-venv"
uv pip install --python "$attempt_root/before-venv/bin/python" -e "$attempt_root/toolkit-before/science"
before_bin="$attempt_root/before-venv/bin/science"
declare -A project_root=(
  [health-meta]="$attempt_root/real-project-home/d/health/meta"
  [evolution]="$attempt_root/real-project-home/d/cancer/mechanisms/evolution"
  [protein-landscape]="$attempt_root/real-project-home/d/protein-landscape"
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
toolkit_root=~/d/science/.worktrees/sidecar-retirement
sdd_workspace="$toolkit_root/.superpowers/sdd/2026-07-29-validation-sidecar-retirement-implementation"
baseline_sha=$(cat "$sdd_workspace/reconciled-origin-main.sha")
revision_root=~/scratch/sidecar-baselines/"$baseline_sha"
attempt_root=$(cat "$revision_root/latest-attempt.txt")
feature_branch_sha=$(awk -F '\t' '$1 == "feature-branch" {print $2}' "$attempt_root/task-6-manifest.tsv")
toolkit_after_sha=$(awk -F '\t' '$1 == "toolkit-after" {print $2}' "$attempt_root/task-6-manifest.tsv")
test "$toolkit_after_sha" = "$feature_branch_sha" || { echo "HARD STOP: manifest feature/toolkit-after mismatch"; exit 1; }
test "$(git -C "$attempt_root/toolkit-after" rev-parse HEAD)" = "$feature_branch_sha" || { echo "HARD STOP: after worktree drift"; exit 1; }
uv venv "$attempt_root/after-venv"
uv pip install --python "$attempt_root/after-venv/bin/python" -e "$attempt_root/toolkit-after/science"
after_bin="$attempt_root/after-venv/bin/science"
declare -A project_root=(
  [health-meta]="$attempt_root/real-project-home/d/health/meta"
  [evolution]="$attempt_root/real-project-home/d/cancer/mechanisms/evolution"
  [protein-landscape]="$attempt_root/real-project-home/d/protein-landscape"
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
toolkit_root=~/d/science/.worktrees/sidecar-retirement
sdd_workspace="$toolkit_root/.superpowers/sdd/2026-07-29-validation-sidecar-retirement-implementation"
baseline_sha=$(cat "$sdd_workspace/reconciled-origin-main.sha")
revision_root=~/scratch/sidecar-baselines/"$baseline_sha"
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
( cd "$attempt_root/real-project-home/d/cancer/mechanisms/evolution" && "$after_bin" validate --all --strict --verbose --output "$attempt_root/evolution-verbose.txt" ) > "$attempt_root/evolution-verbose-command.txt" 2>&1
evolution_notice_status=$?
( cd "$attempt_root/real-project-home/d/health/meta" && "$after_bin" validate --all --strict --verbose --output "$attempt_root/health-meta-verbose.txt" ) > "$attempt_root/health-meta-verbose-command.txt" 2>&1
health_meta_notice_status=$?
set -e
test "$evolution_notice_status" = 1 || { echo "HARD STOP: evolution verbose exit $evolution_notice_status"; exit 1; }
test "$health_meta_notice_status" = 1 || { echo "HARD STOP: health/meta verbose exit $health_meta_notice_status"; exit 1; }
rg -q 'no status:background papers' "$attempt_root/evolution-verbose.txt"
rg -q '9 status:background paper' "$attempt_root/health-meta-verbose.txt"
printf 'command\tevolution-verbose\tscience validate --all --strict --verbose --output %s\texit\t%s\t%s\ncommand\thealth-meta-verbose\tscience validate --all --strict --verbose --output %s\texit\t%s\t%s\n' \
  "$attempt_root/evolution-verbose.txt" "$evolution_notice_status" "$attempt_root/evolution-verbose.txt" "$attempt_root/health-meta-verbose.txt" "$health_meta_notice_status" "$attempt_root/health-meta-verbose.txt" >> "$attempt_root/task-6-manifest.tsv"
record_artifact() {
  local artifact_key=$1
  local artifact_path=$2
  test -s "$artifact_path" || { echo "HARD STOP: missing artifact $artifact_key"; exit 1; }
  printf 'artifact\t%s\t%s\t%s\n' "$artifact_key" "$artifact_path" "$(sha256sum "$artifact_path" | awk '{print $1}')" >> "$attempt_root/task-6-manifest.tsv"
}
record_file_artifact() {
  local artifact_key=$1
  local artifact_path=$2
  test -f "$artifact_path" || { echo "HARD STOP: missing artifact file $artifact_key"; exit 1; }
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
record_artifact current-main-real-projects "$attempt_root/current-main-real-projects.txt"
record_artifact feature-real-projects "$attempt_root/feature-real-projects.txt"
record_file_artifact current-main-real-project-failure-signatures "$attempt_root/current-main-real-project-failure-signatures.txt"
record_file_artifact feature-real-project-failure-signatures "$attempt_root/feature-real-project-failure-signatures.txt"
record_artifact real-project-snapshot-inventory "$attempt_root/real-project-snapshot-inventory.tsv"
record_artifact snapshot-state-before-current-main "$attempt_root/snapshot-state-before-current-main.tsv"
record_artifact snapshot-state-between-real-project-markers "$attempt_root/snapshot-state-between-real-project-markers.tsv"
record_artifact snapshot-state-after-feature "$attempt_root/snapshot-state-after-feature.tsv"
record_artifact evolution-verbose "$attempt_root/evolution-verbose.txt"
record_artifact health-meta-verbose "$attempt_root/health-meta-verbose.txt"
ATTEMPT_ROOT="$attempt_root" python3 - <<'PY'
import os
from collections import Counter
from pathlib import Path

root = Path(os.environ["ATTEMPT_ROOT"])
lines = [line.split("\t") for line in (root / "task-6-manifest.tsv").read_text().splitlines()]
singleton_rows = [row for row in lines if row and row[0] in {"toolkit-before", "toolkit-after", "feature-branch", "attempt-root"}]
singletons = {row[0]: row for row in singleton_rows}
required_artifacts = {
    *(f"{name}-{phase}" for name in ("health-meta", "evolution", "protein-landscape", "science-meta") for phase in ("canonical", "after")),
    "parity-table", "toolkit-suite", "model-suite", "snapshot-marker",
    "current-main-real-projects", "feature-real-projects",
    "current-main-real-project-failure-signatures", "feature-real-project-failure-signatures",
    "real-project-snapshot-inventory",
    "snapshot-state-before-current-main", "snapshot-state-between-real-project-markers",
    "snapshot-state-after-feature",
    "evolution-verbose", "health-meta-verbose",
}
artifact_keys = {row[1] for row in lines if len(row) == 4 and row[0] == "artifact"}
consumer_names = {row[1] for row in lines if len(row) == 5 and row[0] == "consumer"}
snapshot_names = {row[1] for row in lines if len(row) == 7 and row[0] == "real-project-snapshot"}
command_names = {row[1] for row in lines if len(row) >= 5 and row[0] == "command"}
required_commands = {"toolkit-suite", "model-suite", "snapshot-marker", "current-main-real-project-marker", "feature-real-project-marker", "evolution-verbose", "health-meta-verbose", *(f"{phase}-{name}" for name in ("health-meta", "evolution", "protein-landscape", "science-meta") for phase in ("before", "after"))}
required_snapshots = {"natural-systems", "multiple-myeloma", "post-acute-infection", "health-meta", "evolution", "cbioportal", "protein-landscape", "seq-feats", "science-commons"}
missing = ({"toolkit-before", "toolkit-after", "feature-branch", "attempt-root"} - singletons.keys()) | (required_artifacts - artifact_keys) | ({"health-meta", "evolution", "protein-landscape", "science-meta"} - consumer_names) | (required_snapshots - snapshot_names) | (required_commands - command_names)
if missing or singletons["toolkit-after"][1] != singletons["feature-branch"][1]:
    raise SystemExit(f"HARD STOP: incomplete or inconsistent manifest: {sorted(missing)}")
key_counts = {
    "singleton": Counter(row[0] for row in singleton_rows),
    "artifact": Counter(row[1] for row in lines if len(row) == 4 and row[0] == "artifact"),
    "consumer": Counter(row[1] for row in lines if len(row) == 5 and row[0] == "consumer"),
    "real-project-snapshot": Counter(row[1] for row in lines if len(row) == 7 and row[0] == "real-project-snapshot"),
    "command": Counter(row[1] for row in lines if len(row) >= 5 and row[0] == "command"),
}
duplicates = {
    f"{kind}:{key}"
    for kind, counts in key_counts.items()
    for key, count in counts.items()
    if count != 1
}
if duplicates or artifact_keys != required_artifacts or consumer_names != {"health-meta", "evolution", "protein-landscape", "science-meta"} or snapshot_names != required_snapshots or command_names != required_commands:
    raise SystemExit(f"HARD STOP: non-unique or unexpected manifest rows: {sorted(duplicates)}")
PY
sha256sum "$attempt_root/task-6-manifest.tsv" > "$attempt_root/task-6-manifest.sha256"
{
  printf '# Task 6 parity — toolkit before %s; toolkit after %s; branch %s\n\n' \
    "$baseline_sha" "$(awk -F '\t' '$1 == "toolkit-after" {print $2}' "$attempt_root/task-6-manifest.tsv")" "$(awk -F '\t' '$1 == "feature-branch" {print $2}' "$attempt_root/task-6-manifest.tsv")"
  printf 'Pinned consumers: health/meta `36ba8ec83f91d35ba82961836bfc1731b00d9e8b`; evolution `25fd2cb475807c8f5af0d2553244368c55fd3ad2`; protein-landscape `6796628c06a562ff45029f317a0f0fdf1a2fec9e`; science/meta tree `%s`.\n\n' "$(awk -F '\t' '$1 == "consumer" && $2 == "science-meta" {print $4}' "$attempt_root/task-6-manifest.tsv")"
  current_main_real_status=$(awk -F '\t' '$1 == "command" && $2 == "current-main-real-project-marker" {print $5}' "$attempt_root/task-6-manifest.tsv")
  feature_real_status=$(awk -F '\t' '$1 == "command" && $2 == "feature-real-project-marker" {print $5}' "$attempt_root/task-6-manifest.tsv")
  printf 'Full real-project marker parity: current main exit `%s`; feature exit `%s`. All nine detached snapshot states matched before, between, and after the marker runs; see the checksummed manifest artifacts.\n\n' \
    "$current_main_real_status" "$feature_real_status"
  if test "$current_main_real_status" = 0; then
    printf 'Both full real-project markers were green and emitted no `FAILED ...` signatures.\n\n'
  else
    printf 'Both full real-project markers remained nonzero. These matching external failures are visible evidence, not a green result:\n\n```text\n'
    cat "$attempt_root/current-main-real-project-failure-signatures.txt"
    printf '```\n\n'
  fi
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
reports, four after reports, verbose-notice evidence, both complete
real-project marker logs and statuses, both complete failure-signature files,
and all three identical nine-project snapshot-state records are the Task 6
result. Re-run this entire task after any rebase or merge-resolution change.

---

### Task 7: Approval gate, then publish from a verified integration worktree

**Files:** none.

A consumer cannot resolve an unpushed revision, so this must precede Tasks 8–10. It is the one irreversible step in the plan. Never merge or publish from
the local `main` checkout; publication starts from the exact approved baseline
in a temporary integration worktree.

- [ ] **Step 1: Obtain explicit approval to merge and push**

Present Task 6's final parity table, manifest SHA-256, both full-marker statuses
and logs, both signature files, and the three identical nine-project
snapshot-state records;
ask for a go/no-go on pushing `origin/main`. **Do not
proceed without an explicit yes.** Prior approval of the design is not approval
of the push. Immediately after that yes, create this immutable approval record.
The command discovers every exact `artifact` row in the Task 6 manifest,
checks its current SHA-256, and writes one evidence row for it; the manifest
itself is an additional evidence row. It does not maintain a selected artifact
list, so canonical reports, suite logs, marker logs and signatures, all
snapshot records, verbose reports, and both parity tables are frozen together.
It is the only point at which `latest-attempt.txt` may be read for publication;
copy the printed `approval_record` path verbatim into Steps 2 and 3.

```bash
set -euo pipefail
toolkit_root=~/d/science/.worktrees/sidecar-retirement
sdd_workspace="$toolkit_root/.superpowers/sdd/2026-07-29-validation-sidecar-retirement-implementation"
baseline_sha=$(cat "$sdd_workspace/reconciled-origin-main.sha")
revision_root=~/scratch/sidecar-baselines/"$baseline_sha"
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
test "$(awk -F '\t' '$1 == "toolkit-before" {print $2}' "$approved_attempt_root/task-6-manifest.tsv")" = "$baseline_sha" || {
  echo "HARD STOP: latest attempt does not use the frozen baseline"; exit 1;
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
malformed_artifact_rows=$(awk -F '\t' '$1 == "artifact" && NF != 4 {print NR}' "$approved_attempt_root/task-6-manifest.tsv")
test -z "$malformed_artifact_rows" || {
  printf 'HARD STOP: malformed manifest artifact rows: %s\n' "$malformed_artifact_rows"
  exit 1
}
mapfile -t manifest_artifact_rows < <(
  awk -F '\t' '$1 == "artifact" {print $2 "\t" $3 "\t" $4}' \
    "$approved_attempt_root/task-6-manifest.tsv"
)
test "${#manifest_artifact_rows[@]}" -gt 0 || {
  echo "HARD STOP: approved manifest contains no artifact rows"; exit 1;
}
printf 'attempt-root\t%s\nmanifest-digest\t%s\nbaseline-sha\t%s\nfeature-sha\t%s\nparity-artifact\t%s\ncurrent-main-real-project-log\t%s\nfeature-real-project-log\t%s\ncurrent-main-signatures\t%s\nfeature-signatures\t%s\nsnapshot-state-before-current-main\t%s\nsnapshot-state-between-markers\t%s\nsnapshot-state-after-feature\t%s\n' \
  "$approved_attempt_root" "$(sha256sum "$approved_attempt_root/task-6-manifest.tsv" | awk '{print $1}')" \
  "$(awk -F '\t' '$1 == "toolkit-before" {print $2}' "$approved_attempt_root/task-6-manifest.tsv")" \
  "$(awk -F '\t' '$1 == "feature-branch" {print $2}' "$approved_attempt_root/task-6-manifest.tsv")" \
  "$approved_attempt_root/final-parity-table.md" \
  "$approved_attempt_root/current-main-real-projects.txt" "$approved_attempt_root/feature-real-projects.txt" \
  "$approved_attempt_root/current-main-real-project-failure-signatures.txt" "$approved_attempt_root/feature-real-project-failure-signatures.txt" \
  "$approved_attempt_root/snapshot-state-before-current-main.tsv" "$approved_attempt_root/snapshot-state-between-real-project-markers.tsv" \
  "$approved_attempt_root/snapshot-state-after-feature.tsv" \
  > "$approval_record"
printf 'evidence\ttask-6-manifest\t%s\t%s\n' "$approved_attempt_root/task-6-manifest.tsv" \
  "$(sha256sum "$approved_attempt_root/task-6-manifest.tsv" | awk '{print $1}')" >> "$approval_record"
for manifest_artifact_row in "${manifest_artifact_rows[@]}"; do
  IFS=$'\t' read -r manifest_key artifact_path expected_digest <<< "$manifest_artifact_row"
  test -n "$manifest_key" && test -n "$artifact_path" && test -n "$expected_digest" || {
    echo "HARD STOP: incomplete manifest artifact row"; exit 1;
  }
  test "$manifest_key" != task-6-manifest || {
    echo "HARD STOP: manifest artifact key collides with task-6-manifest evidence"; exit 1;
  }
  test -f "$artifact_path" || {
    echo "HARD STOP: missing manifest artifact $manifest_key at $artifact_path"; exit 1;
  }
  test "$(sha256sum "$artifact_path" | awk '{print $1}')" = "$expected_digest" || {
    echo "HARD STOP: manifest evidence checksum mismatch for $manifest_key"; exit 1;
  }
  printf 'evidence\t%s\t%s\t%s\n' "$manifest_key" "$artifact_path" "$expected_digest" >> "$approval_record"
done
duplicate_evidence_keys=$(awk -F '\t' '
  $1 == "evidence" { count[$2]++ }
  END {
    for (key in count) {
      if (count[key] != 1) print key
    }
  }
' "$approval_record")
test -z "$duplicate_evidence_keys" || {
  printf 'HARD STOP: approval evidence keys are not unique:\n%s\n' "$duplicate_evidence_keys"
  exit 1
}
mapfile -t expected_evidence_keys < <(
  {
    printf '%s\n' task-6-manifest
    awk -F '\t' '$1 == "artifact" {print $2}' "$approved_attempt_root/task-6-manifest.tsv"
  } | LC_ALL=C sort
)
mapfile -t actual_evidence_keys < <(
  awk -F '\t' '$1 == "evidence" {print $2}' "$approval_record" | LC_ALL=C sort
)
test "${actual_evidence_keys[*]}" = "${expected_evidence_keys[*]}" || {
  echo "HARD STOP: approval evidence coverage differs from the manifest artifact set"
  exit 1
}
sha256sum "$approval_record" > "$approval_digest_path"
printf 'Approved publication record: %s\n' "$approval_record"
```

- [ ] **Step 2: Refetch, require the recorded remote SHA, and merge only in a temporary integration worktree**

```bash
set -euo pipefail
toolkit_root=~/d/science/.worktrees/sidecar-retirement
read -r -p 'Paste the exact approval record printed by Task 7 Step 1: ' approval_record
approval_digest_path="$approval_record.sha256"
test -s "$approval_record" && test -s "$approval_digest_path" || { echo "HARD STOP: missing explicit approval record"; exit 1; }
test "$(sha256sum "$approval_record")" = "$(cat "$approval_digest_path")" || { echo "HARD STOP: approval record changed"; exit 1; }
approved_attempt_root=$(awk -F '\t' '$1 == "attempt-root" {print $2}' "$approval_record")
approved_manifest_digest=$(awk -F '\t' '$1 == "manifest-digest" {print $2}' "$approval_record")
approved_baseline_sha=$(awk -F '\t' '$1 == "baseline-sha" {print $2}' "$approval_record")
approved_feature_sha=$(awk -F '\t' '$1 == "feature-sha" {print $2}' "$approval_record")
test -n "$approved_baseline_sha" && test -n "$approved_feature_sha" || { echo "HARD STOP: approval SHAs missing"; exit 1; }
test "$(sha256sum "$approved_attempt_root/task-6-manifest.tsv" | awk '{print $1}')" = "$approved_manifest_digest" || { echo "HARD STOP: approved attempt changed"; exit 1; }
test "$(awk -F '\t' '$1 == "feature-branch" {print $2}' "$approved_attempt_root/task-6-manifest.tsv")" = "$approved_feature_sha" || { echo "HARD STOP: approval feature SHA mismatch"; exit 1; }
test "$(awk -F '\t' '$1 == "toolkit-after" {print $2}' "$approved_attempt_root/task-6-manifest.tsv")" = "$approved_feature_sha" || { echo "HARD STOP: approval after-toolkit SHA mismatch"; exit 1; }
verify_approved_evidence_set() {
  local manifest_path="$approved_attempt_root/task-6-manifest.tsv"
  local malformed_artifact_rows
  local duplicate_manifest_keys
  local duplicate_evidence_keys
  local evidence_kind
  local evidence_key
  local evidence_path
  local evidence_digest
  local expected_path
  local expected_digest
  local current_digest
  local -a expected_evidence_keys
  local -a actual_evidence_keys
  local -a expected_artifact_rows

  malformed_artifact_rows=$(awk -F '\t' '$1 == "artifact" && NF != 4 {print NR}' "$manifest_path")
  test -z "$malformed_artifact_rows" || {
    printf 'HARD STOP: malformed manifest artifact rows: %s\n' "$malformed_artifact_rows"
    exit 1
  }
  duplicate_manifest_keys=$(awk -F '\t' '
    $1 == "artifact" { count[$2]++ }
    END { for (key in count) if (count[key] != 1) print key }
  ' "$manifest_path")
  duplicate_evidence_keys=$(awk -F '\t' '
    $1 == "evidence" { count[$2]++ }
    END { for (key in count) if (count[key] != 1) print key }
  ' "$approval_record")
  test -z "$duplicate_manifest_keys" && test -z "$duplicate_evidence_keys" || {
    echo "HARD STOP: manifest artifact or approval evidence keys are not unique"
    exit 1
  }
  mapfile -t expected_evidence_keys < <(
    {
      printf '%s\n' task-6-manifest
      awk -F '\t' '$1 == "artifact" {print $2}' "$manifest_path"
    } | LC_ALL=C sort
  )
  mapfile -t actual_evidence_keys < <(
    awk -F '\t' '$1 == "evidence" {print $2}' "$approval_record" | LC_ALL=C sort
  )
  test "${#expected_evidence_keys[@]}" -gt 1 || {
    echo "HARD STOP: manifest has no artifact evidence"; exit 1;
  }
  test "${actual_evidence_keys[*]}" = "${expected_evidence_keys[*]}" || {
    echo "HARD STOP: approval evidence coverage differs from manifest artifacts plus task-6-manifest"
    exit 1
  }
  while IFS=$'\t' read -r evidence_kind evidence_key evidence_path evidence_digest; do
    [[ "$evidence_kind" = evidence ]] || continue
    if [[ "$evidence_key" = task-6-manifest ]]; then
      expected_path="$manifest_path"
      expected_digest="$approved_manifest_digest"
    else
      mapfile -t expected_artifact_rows < <(
        awk -F '\t' -v key="$evidence_key" \
          '$1 == "artifact" && $2 == key {print $3 "\t" $4}' "$manifest_path"
      )
      test "${#expected_artifact_rows[@]}" -eq 1 || {
        echo "HARD STOP: expected exactly one manifest artifact row for $evidence_key"; exit 1;
      }
      IFS=$'\t' read -r expected_path expected_digest <<< "${expected_artifact_rows[0]}"
    fi
    test "$evidence_path" = "$expected_path" && test "$evidence_digest" = "$expected_digest" || {
      echo "HARD STOP: approval row differs from exact manifest evidence for $evidence_key"
      exit 1
    }
    test -f "$evidence_path" || {
      echo "HARD STOP: approved evidence file is missing: $evidence_key"; exit 1;
    }
    current_digest=$(sha256sum "$evidence_path" | awk '{print $1}')
    test "$current_digest" = "$evidence_digest" || {
      echo "HARD STOP: approved evidence changed: $evidence_key"; exit 1;
    }
  done < "$approval_record"
}
verify_approved_evidence_set
integration_root=~/scratch/sidecar-integration-"${approved_baseline_sha:0:8}"-"$(basename "$approval_record" .tsv)"
integration_branch=validation-sidecar-integration-"${approved_baseline_sha:0:8}"
test ! -e "$integration_root" || { echo "HARD STOP: preserve prior publish worktree $integration_root"; exit 1; }
test "$(git -C "$toolkit_root" rev-parse sidecar-retirement)" = "$approved_feature_sha" || {
  echo "HARD STOP: sidecar-retirement advanced after Task 6 approval"; exit 1;
}
git -C "$toolkit_root" fetch --prune origin
actual_origin_main_sha=$(git -C "$toolkit_root" rev-parse origin/main)
test "$actual_origin_main_sha" = "$approved_baseline_sha" || {
  echo "HARD STOP: origin/main changed; reassess and recapture Task 6"; exit 1;
}
git -C "$toolkit_root" worktree add -b "$integration_branch" "$integration_root" "$approved_baseline_sha"
git -C "$integration_root" merge --no-ff "$approved_feature_sha" -m "merge: retire validation sidecar"
merge_sha=$(git -C "$integration_root" rev-parse HEAD)
first_parent_sha=$(git -C "$integration_root" rev-parse HEAD^1)
second_parent_sha=$(git -C "$integration_root" rev-parse HEAD^2)
integration_tree_sha=$(git -C "$integration_root" rev-parse "HEAD^{tree}")
approved_feature_tree_sha=$(git -C "$integration_root" rev-parse "$approved_feature_sha^{tree}")
test -z "$(git -C "$integration_root" status --porcelain)" || {
  echo "HARD STOP: integration worktree is dirty after merge"; exit 1;
}
test "$(git -C "$integration_root" branch --show-current)" = "$integration_branch" || {
  echo "HARD STOP: integration worktree is not on $integration_branch"; exit 1;
}
test "$first_parent_sha" = "$approved_baseline_sha" || {
  echo "HARD STOP: merge first parent is $first_parent_sha"; exit 1;
}
test "$second_parent_sha" = "$approved_feature_sha" || {
  echo "HARD STOP: merge second parent is $second_parent_sha"; exit 1;
}
test "$integration_tree_sha" = "$approved_feature_tree_sha" || {
  echo "HARD STOP: merge tree differs from the approved feature tree"; exit 1;
}
```

- [ ] **Step 3: Reconfirm the approved Task 6 gate, push the integration HEAD, and verify the remote**

```bash
set -euo pipefail
read -r -p 'Paste the exact approval record printed by Task 7 Step 1: ' approval_record
approval_digest_path="$approval_record.sha256"
test "$(sha256sum "$approval_record")" = "$(cat "$approval_digest_path")" || { echo "HARD STOP: approval record changed"; exit 1; }
approved_attempt_root=$(awk -F '\t' '$1 == "attempt-root" {print $2}' "$approval_record")
approved_manifest_digest=$(awk -F '\t' '$1 == "manifest-digest" {print $2}' "$approval_record")
approved_baseline_sha=$(awk -F '\t' '$1 == "baseline-sha" {print $2}' "$approval_record")
approved_feature_sha=$(awk -F '\t' '$1 == "feature-sha" {print $2}' "$approval_record")
test -n "$approved_baseline_sha" && test -n "$approved_feature_sha" || { echo "HARD STOP: approval SHAs missing"; exit 1; }
test "$(sha256sum "$approved_attempt_root/task-6-manifest.tsv" | awk '{print $1}')" = "$approved_manifest_digest" || { echo "HARD STOP: approved attempt changed"; exit 1; }
test "$(awk -F '\t' '$1 == "feature-branch" {print $2}' "$approved_attempt_root/task-6-manifest.tsv")" = "$approved_feature_sha" || { echo "HARD STOP: approval feature SHA mismatch"; exit 1; }
verify_approved_evidence_set() {
  local manifest_path="$approved_attempt_root/task-6-manifest.tsv"
  local malformed_artifact_rows
  local duplicate_manifest_keys
  local duplicate_evidence_keys
  local evidence_kind
  local evidence_key
  local evidence_path
  local evidence_digest
  local expected_path
  local expected_digest
  local current_digest
  local -a expected_evidence_keys
  local -a actual_evidence_keys
  local -a expected_artifact_rows

  malformed_artifact_rows=$(awk -F '\t' '$1 == "artifact" && NF != 4 {print NR}' "$manifest_path")
  test -z "$malformed_artifact_rows" || {
    printf 'HARD STOP: malformed manifest artifact rows: %s\n' "$malformed_artifact_rows"
    exit 1
  }
  duplicate_manifest_keys=$(awk -F '\t' '
    $1 == "artifact" { count[$2]++ }
    END { for (key in count) if (count[key] != 1) print key }
  ' "$manifest_path")
  duplicate_evidence_keys=$(awk -F '\t' '
    $1 == "evidence" { count[$2]++ }
    END { for (key in count) if (count[key] != 1) print key }
  ' "$approval_record")
  test -z "$duplicate_manifest_keys" && test -z "$duplicate_evidence_keys" || {
    echo "HARD STOP: manifest artifact or approval evidence keys are not unique"
    exit 1
  }
  mapfile -t expected_evidence_keys < <(
    {
      printf '%s\n' task-6-manifest
      awk -F '\t' '$1 == "artifact" {print $2}' "$manifest_path"
    } | LC_ALL=C sort
  )
  mapfile -t actual_evidence_keys < <(
    awk -F '\t' '$1 == "evidence" {print $2}' "$approval_record" | LC_ALL=C sort
  )
  test "${#expected_evidence_keys[@]}" -gt 1 || {
    echo "HARD STOP: manifest has no artifact evidence"; exit 1;
  }
  test "${actual_evidence_keys[*]}" = "${expected_evidence_keys[*]}" || {
    echo "HARD STOP: approval evidence coverage differs from manifest artifacts plus task-6-manifest"
    exit 1
  }
  while IFS=$'\t' read -r evidence_kind evidence_key evidence_path evidence_digest; do
    [[ "$evidence_kind" = evidence ]] || continue
    if [[ "$evidence_key" = task-6-manifest ]]; then
      expected_path="$manifest_path"
      expected_digest="$approved_manifest_digest"
    else
      mapfile -t expected_artifact_rows < <(
        awk -F '\t' -v key="$evidence_key" \
          '$1 == "artifact" && $2 == key {print $3 "\t" $4}' "$manifest_path"
      )
      test "${#expected_artifact_rows[@]}" -eq 1 || {
        echo "HARD STOP: expected exactly one manifest artifact row for $evidence_key"; exit 1;
      }
      IFS=$'\t' read -r expected_path expected_digest <<< "${expected_artifact_rows[0]}"
    fi
    test "$evidence_path" = "$expected_path" && test "$evidence_digest" = "$expected_digest" || {
      echo "HARD STOP: approval row differs from exact manifest evidence for $evidence_key"
      exit 1
    }
    test -f "$evidence_path" || {
      echo "HARD STOP: approved evidence file is missing: $evidence_key"; exit 1;
    }
    current_digest=$(sha256sum "$evidence_path" | awk '{print $1}')
    test "$current_digest" = "$evidence_digest" || {
      echo "HARD STOP: approved evidence changed: $evidence_key"; exit 1;
    }
  done < "$approval_record"
}
verify_approved_evidence_set
integration_root=~/scratch/sidecar-integration-"${approved_baseline_sha:0:8}"-"$(basename "$approval_record" .tsv)"
integration_branch=validation-sidecar-integration-"${approved_baseline_sha:0:8}"
test -d "$integration_root" || { echo "HARD STOP: missing approved integration worktree"; exit 1; }
git -C "$integration_root" fetch --prune origin
test "$(git -C "$integration_root" rev-parse origin/main)" = "$approved_baseline_sha" || {
  echo "HARD STOP: origin/main advanced after integration; reassess and recapture Task 6"; exit 1;
}
merge_sha=$(git -C "$integration_root" rev-parse HEAD)
first_parent_sha=$(git -C "$integration_root" rev-parse HEAD^1)
second_parent_sha=$(git -C "$integration_root" rev-parse HEAD^2)
integration_tree_sha=$(git -C "$integration_root" rev-parse "HEAD^{tree}")
approved_feature_tree_sha=$(git -C "$integration_root" rev-parse "$approved_feature_sha^{tree}")
test -z "$(git -C "$integration_root" status --porcelain)" || {
  echo "HARD STOP: integration worktree became dirty before push"; exit 1;
}
test "$(git -C "$integration_root" branch --show-current)" = "$integration_branch" || {
  echo "HARD STOP: integration worktree left $integration_branch before push"; exit 1;
}
test "$first_parent_sha" = "$approved_baseline_sha" || {
  echo "HARD STOP: pre-push merge first parent is $first_parent_sha"; exit 1;
}
test "$second_parent_sha" = "$approved_feature_sha" || {
  echo "HARD STOP: pre-push merge second parent is $second_parent_sha"; exit 1;
}
test "$integration_tree_sha" = "$approved_feature_tree_sha" || {
  echo "HARD STOP: pre-push merge tree differs from the approved feature tree"; exit 1;
}
git -C "$integration_root" push origin HEAD:main
remote_main_sha=$(git -C "$integration_root" ls-remote origin refs/heads/main | awk '{print $1}')
test "$remote_main_sha" = "$merge_sha" || { echo "HARD STOP: remote main is $remote_main_sha"; exit 1; }
printf '%s\n' "$merge_sha" > "$approved_attempt_root/published-main.sha"
git -C ~/d/science/.worktrees/sidecar-retirement worktree remove "$integration_root"
git -C ~/d/science/.worktrees/sidecar-retirement branch -D "$integration_branch"
```

Expected: the integration worktree is clean and on the derived integration
branch; the merge commit's first parent is the recorded remote SHA, its second
parent and tree are the approved feature's, and `git ls-remote` confirms that
exact merge commit on `origin/main`.

If publication stops before the successful cleanup, retain the immutable
approval record and its SHA-256 file. Remove only the explicitly derived
temporary worktree and branch before retrying with that same approval record:

```bash
set -euo pipefail
toolkit_root=~/d/science/.worktrees/sidecar-retirement
read -r -p 'Paste the exact approval record printed by Task 7 Step 1: ' approval_record
test "$(sha256sum "$approval_record")" = "$(cat "$approval_record.sha256")" || { echo "HARD STOP: approval record changed"; exit 1; }
approved_baseline_sha=$(awk -F '\t' '$1 == "baseline-sha" {print $2}' "$approval_record")
test -n "$approved_baseline_sha" || { echo "HARD STOP: approval baseline SHA missing"; exit 1; }
integration_root=~/scratch/sidecar-integration-"${approved_baseline_sha:0:8}"-"$(basename "$approval_record" .tsv)"
integration_branch=validation-sidecar-integration-"${approved_baseline_sha:0:8}"
if git -C "$toolkit_root" worktree list --porcelain | rg -Fqx "worktree $integration_root"; then
  git -C "$toolkit_root" worktree remove --force "$integration_root"
fi
git -C "$toolkit_root" branch -D "$integration_branch" 2>/dev/null || true
git -C "$toolkit_root" worktree prune
```

---

### Task 8: Migrate `~/d/health/meta` atomically

**Files:** `pyproject.toml:13`, `uv.lock`, `AGENTS.md`; delete `validate_local.py`

**Entry gate:** Paste the exact immutable approval-record path from Task 7;
never discover authorization through `latest-attempt.txt`. Derive the attempt,
baseline, feature, published SHA, manifest digest, and exact clean consumer
snapshot from that record. Drift means recapturing and reverifying Task 6
before editing. Capture the primary checkout's exact nonempty branch in the
approved attempt before creating the migration worktree.

```bash
set -euo pipefail
read -r -p 'Paste the exact approval record printed by Task 7 Step 1: ' approval_record
test "$(sha256sum "$approval_record")" = "$(cat "$approval_record.sha256")" || { echo "HARD STOP: approval record changed"; exit 1; }
attempt_root=$(awk -F '\t' '$1 == "attempt-root" {print $2}' "$approval_record")
approved_baseline_sha=$(awk -F '\t' '$1 == "baseline-sha" {print $2}' "$approval_record")
approved_feature_sha=$(awk -F '\t' '$1 == "feature-sha" {print $2}' "$approval_record")
approved_manifest_digest=$(awk -F '\t' '$1 == "manifest-digest" {print $2}' "$approval_record")
test -n "$attempt_root" && test -n "$approved_baseline_sha" && test -n "$approved_feature_sha" || { echo "HARD STOP: incomplete approval record"; exit 1; }
test "$(sha256sum "$attempt_root/task-6-manifest.tsv" | awk '{print $1}')" = "$approved_manifest_digest" || { echo "HARD STOP: Task 6 manifest drift"; exit 1; }
test "$(awk -F '\t' '$1 == "toolkit-before" {print $2}' "$attempt_root/task-6-manifest.tsv")" = "$approved_baseline_sha"
test "$(awk -F '\t' '$1 == "feature-branch" {print $2}' "$attempt_root/task-6-manifest.tsv")" = "$approved_feature_sha"
source_root=~/d/health/meta
required_head=$(awk -F '\t' '$1 == "consumer" && $2 == "health-meta" {print $4}' "$attempt_root/task-6-manifest.tsv")
published_main_sha=$(cat "$attempt_root/published-main.sha")
test "$(git -C ~/d/science/.worktrees/sidecar-retirement ls-remote origin refs/heads/main | awk '{print $1}')" = "$published_main_sha" || { echo "HARD STOP: published main is not recorded SHA"; exit 1; }
test "$(git -C ~/d/science/.worktrees/sidecar-retirement rev-parse "$published_main_sha^1")" = "$approved_baseline_sha" || { echo "HARD STOP: published first parent is not approved baseline"; exit 1; }
test "$(git -C ~/d/science/.worktrees/sidecar-retirement rev-parse "$published_main_sha^2")" = "$approved_feature_sha" || { echo "HARD STOP: published second parent is not approved feature"; exit 1; }
test "$required_head" = 36ba8ec83f91d35ba82961836bfc1731b00d9e8b || { echo "HARD STOP: health/meta missing from manifest"; exit 1; }
test -z "$(git -C "$source_root" status --porcelain)" || { echo "HARD STOP: health/meta source drift"; exit 1; }
test "$(git -C "$source_root" rev-parse HEAD)" = "$required_head" || { echo "HARD STOP: health/meta HEAD drift; recapture Task 6"; exit 1; }
intended_source_branch=$(git -C "$source_root" symbolic-ref --quiet --short HEAD) || {
  echo "HARD STOP: health/meta primary checkout is detached"; exit 1;
}
test -n "$intended_source_branch" || { echo "HARD STOP: health/meta primary branch is empty"; exit 1; }
branch_state_path="$attempt_root/consumer-primary-branch-health-meta.tsv"
branch_state_digest_path="$branch_state_path.sha256"
approval_record_digest=$(sha256sum "$approval_record" | awk '{print $1}')
expected_branch_state=$(printf 'consumer\thealth-meta\nattempt-root\t%s\napproval-record-digest\t%s\nsource-root\t%s\nbranch\t%s' \
  "$attempt_root" "$approval_record_digest" "$source_root" "$intended_source_branch")
if [[ -e "$branch_state_path" || -L "$branch_state_path" || -e "$branch_state_digest_path" || -L "$branch_state_digest_path" ]]; then
  test -f "$branch_state_path" && test ! -L "$branch_state_path" &&
    test -f "$branch_state_digest_path" && test ! -L "$branch_state_digest_path" || {
      echo "HARD STOP: health/meta branch-state collision is incomplete or not a regular file"; exit 1;
    }
  test "$(sha256sum "$branch_state_path")" = "$(cat "$branch_state_digest_path")" || {
    echo "HARD STOP: health/meta branch-state digest drift"; exit 1;
  }
  test "$(cat "$branch_state_path")" = "$expected_branch_state" || {
    echo "HARD STOP: health/meta branch-state collision differs from current approved state"; exit 1;
  }
else
  (set -o noclobber; printf '%s\n' "$expected_branch_state" > "$branch_state_path") || {
    echo "HARD STOP: health/meta branch-state creation collision"; exit 1;
  }
  (set -o noclobber; sha256sum "$branch_state_path" > "$branch_state_digest_path") || {
    echo "HARD STOP: health/meta branch-state digest creation collision"; exit 1;
  }
fi
```

- [ ] **Step 1: Work in an isolated worktree**

The repository root is `~/d/health/meta`, **not** `~/d/health` — the latter is not a Git repository at all.

```bash
cd ~/d/health/meta && git rev-parse --show-toplevel   # confirm before proceeding
git worktree add .worktrees/sidecar-retirement -b sidecar-retirement
cd .worktrees/sidecar-retirement
test "$(git branch --show-current)" = sidecar-retirement || {
  echo "HARD STOP: health/meta migration worktree is on the wrong branch"; exit 1;
}
```

- [ ] **Step 2: Update the explicit pin and relock**

Replace `rev = "3b72db60b8d591cf3dbac8ae25ca194f6cda9c8b"` in `[tool.uv.sources]` with the published SHA recorded by Task 7, then:

```bash
read -r -p 'Paste the exact approval record printed by Task 7 Step 1: ' approval_record
test "$(sha256sum "$approval_record")" = "$(cat "$approval_record.sha256")" || { echo "HARD STOP: approval record changed"; exit 1; }
attempt_root=$(awk -F '\t' '$1 == "attempt-root" {print $2}' "$approval_record")
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
read -r -p 'Paste the exact approval record printed by Task 7 Step 1: ' approval_record
test "$(sha256sum "$approval_record")" = "$(cat "$approval_record.sha256")" || { echo "HARD STOP: approval record changed"; exit 1; }
attempt_root=$(awk -F '\t' '$1 == "attempt-root" {print $2}' "$approval_record")
canonical_report=$(awk -F '\t' '$1 == "artifact" && $2 == "health-meta-canonical" {print $3}' "$attempt_root/task-6-manifest.tsv")
test -f "$canonical_report" || { echo "HARD STOP: approved health/meta canonical report missing"; exit 1; }
uv run --frozen science validate --all --strict --format json \
  --output /tmp/hm-after-complete.json > /tmp/hm-after.json
validation_status=$?
test "$validation_status" -eq 1 || {
  echo "FAIL: validator exited $validation_status, expected approved baseline status 1"; exit 1;
}
python3 - "$canonical_report" <<'PY'
import json
import sys

expected = json.load(open(sys.argv[1]))
actual = json.load(open("/tmp/hm-after-complete.json"))
print(actual["summary"])
assert actual == expected, "complete result differs from approved canonical baseline"
rules = {r.get("rule") for r in actual["results"]}
assert "validate.python-sidecar-removed" not in rules
assert not any(str(r or "").startswith("papers.background-review") for r in rules), rules
print("OK")
PY
```

Expected: status `1`, summary `16 errors / 139 warnings`, exact complete-report
parity with the approved canonical baseline, and `OK`. Strict validation already
failed at the frozen consumer snapshot for unrelated corpus findings; changing
that to zero would falsify the parity gate. The nine background papers are cited
under `source_refs`, not `evidence_refs`, and both `paper:Tasci2022` provenance
records already carry `evidence_tier: background` and
`review_typed_source: true`.

- [ ] **Step 5: Commit atomically, merge, clean up**

```bash
set -euo pipefail
git add -A && git commit -m "chore: adopt toolkit background-review check and drop the validation sidecar"
read -r -p 'Paste the exact approval record printed by Task 7 Step 1: ' approval_record
test "$(sha256sum "$approval_record")" = "$(cat "$approval_record.sha256")" || { echo "HARD STOP: approval record changed"; exit 1; }
attempt_root=$(awk -F '\t' '$1 == "attempt-root" {print $2}' "$approval_record")
test -n "$attempt_root" || { echo "HARD STOP: approval attempt root missing"; exit 1; }
source_root=~/d/health/meta
branch_state_path="$attempt_root/consumer-primary-branch-health-meta.tsv"
branch_state_digest_path="$branch_state_path.sha256"
test -f "$branch_state_path" && test ! -L "$branch_state_path" &&
  test -f "$branch_state_digest_path" && test ! -L "$branch_state_digest_path" || {
    echo "HARD STOP: approved health/meta branch state is missing or not a regular file"; exit 1;
  }
test "$(sha256sum "$branch_state_path")" = "$(cat "$branch_state_digest_path")" || {
  echo "HARD STOP: approved health/meta branch-state digest drift"; exit 1;
}
intended_source_branch=$(awk -F '\t' '$1 == "branch" {print $2}' "$branch_state_path")
test -n "$intended_source_branch" || { echo "HARD STOP: saved health/meta primary branch is empty"; exit 1; }
expected_branch_state=$(printf 'consumer\thealth-meta\nattempt-root\t%s\napproval-record-digest\t%s\nsource-root\t%s\nbranch\t%s' \
  "$attempt_root" "$(sha256sum "$approval_record" | awk '{print $1}')" "$source_root" "$intended_source_branch")
test "$(cat "$branch_state_path")" = "$expected_branch_state" || {
  echo "HARD STOP: saved health/meta branch state is malformed or belongs to another task"; exit 1;
}
current_source_branch=$(git -C "$source_root" symbolic-ref --quiet --short HEAD) || {
  echo "HARD STOP: health/meta primary checkout is detached before merge"; exit 1;
}
test "$current_source_branch" = "$intended_source_branch" || {
  echo "HARD STOP: health/meta primary branch changed from $intended_source_branch to $current_source_branch"; exit 1;
}
test -z "$(git -C "$source_root" status --porcelain)" || {
  echo "HARD STOP: health/meta primary checkout is dirty before merge"; exit 1;
}
git -C "$source_root" merge --no-ff sidecar-retirement
git -C "$source_root" worktree remove .worktrees/sidecar-retirement
```

This repo has **no GitHub remote** — commit and merge only, never push. It is also Dropbox-synced, so its primary checkout floats; verify the branch before merging.

---

### Task 9: Migrate `~/d/cancer/mechanisms/evolution` atomically

**Files:** `uv.lock:3062`, `AGENTS.md`; delete `validate_local.py`

**Entry gate:** Paste the exact immutable approval-record path from Task 7;
never discover authorization through `latest-attempt.txt`. Derive the attempt,
baseline, feature, published SHA, manifest digest, and exact clean consumer
snapshot from that record. No migration is authorized after drift. Capture the
primary checkout's exact nonempty branch in the approved attempt before
creating the migration worktree.

```bash
set -euo pipefail
read -r -p 'Paste the exact approval record printed by Task 7 Step 1: ' approval_record
test "$(sha256sum "$approval_record")" = "$(cat "$approval_record.sha256")" || { echo "HARD STOP: approval record changed"; exit 1; }
attempt_root=$(awk -F '\t' '$1 == "attempt-root" {print $2}' "$approval_record")
approved_baseline_sha=$(awk -F '\t' '$1 == "baseline-sha" {print $2}' "$approval_record")
approved_feature_sha=$(awk -F '\t' '$1 == "feature-sha" {print $2}' "$approval_record")
approved_manifest_digest=$(awk -F '\t' '$1 == "manifest-digest" {print $2}' "$approval_record")
test -n "$attempt_root" && test -n "$approved_baseline_sha" && test -n "$approved_feature_sha" || { echo "HARD STOP: incomplete approval record"; exit 1; }
test "$(sha256sum "$attempt_root/task-6-manifest.tsv" | awk '{print $1}')" = "$approved_manifest_digest" || { echo "HARD STOP: Task 6 manifest drift"; exit 1; }
test "$(awk -F '\t' '$1 == "toolkit-before" {print $2}' "$attempt_root/task-6-manifest.tsv")" = "$approved_baseline_sha"
test "$(awk -F '\t' '$1 == "feature-branch" {print $2}' "$attempt_root/task-6-manifest.tsv")" = "$approved_feature_sha"
source_root=~/d/cancer/mechanisms/evolution
required_head=$(awk -F '\t' '$1 == "consumer" && $2 == "evolution" {print $4}' "$attempt_root/task-6-manifest.tsv")
published_main_sha=$(cat "$attempt_root/published-main.sha")
test "$(git -C ~/d/science/.worktrees/sidecar-retirement ls-remote origin refs/heads/main | awk '{print $1}')" = "$published_main_sha" || { echo "HARD STOP: published main is not recorded SHA"; exit 1; }
test "$(git -C ~/d/science/.worktrees/sidecar-retirement rev-parse "$published_main_sha^1")" = "$approved_baseline_sha" || { echo "HARD STOP: published first parent is not approved baseline"; exit 1; }
test "$(git -C ~/d/science/.worktrees/sidecar-retirement rev-parse "$published_main_sha^2")" = "$approved_feature_sha" || { echo "HARD STOP: published second parent is not approved feature"; exit 1; }
test "$required_head" = 25fd2cb475807c8f5af0d2553244368c55fd3ad2 || { echo "HARD STOP: evolution missing from manifest"; exit 1; }
test -z "$(git -C "$source_root" status --porcelain)" || { echo "HARD STOP: evolution source drift"; exit 1; }
test "$(git -C "$source_root" rev-parse HEAD)" = "$required_head" || { echo "HARD STOP: evolution HEAD drift; recapture Task 6"; exit 1; }
intended_source_branch=$(git -C "$source_root" symbolic-ref --quiet --short HEAD) || {
  echo "HARD STOP: evolution primary checkout is detached"; exit 1;
}
test -n "$intended_source_branch" || { echo "HARD STOP: evolution primary branch is empty"; exit 1; }
branch_state_path="$attempt_root/consumer-primary-branch-evolution.tsv"
branch_state_digest_path="$branch_state_path.sha256"
approval_record_digest=$(sha256sum "$approval_record" | awk '{print $1}')
expected_branch_state=$(printf 'consumer\tevolution\nattempt-root\t%s\napproval-record-digest\t%s\nsource-root\t%s\nbranch\t%s' \
  "$attempt_root" "$approval_record_digest" "$source_root" "$intended_source_branch")
if [[ -e "$branch_state_path" || -L "$branch_state_path" || -e "$branch_state_digest_path" || -L "$branch_state_digest_path" ]]; then
  test -f "$branch_state_path" && test ! -L "$branch_state_path" &&
    test -f "$branch_state_digest_path" && test ! -L "$branch_state_digest_path" || {
      echo "HARD STOP: evolution branch-state collision is incomplete or not a regular file"; exit 1;
    }
  test "$(sha256sum "$branch_state_path")" = "$(cat "$branch_state_digest_path")" || {
    echo "HARD STOP: evolution branch-state digest drift"; exit 1;
  }
  test "$(cat "$branch_state_path")" = "$expected_branch_state" || {
    echo "HARD STOP: evolution branch-state collision differs from current approved state"; exit 1;
  }
else
  (set -o noclobber; printf '%s\n' "$expected_branch_state" > "$branch_state_path") || {
    echo "HARD STOP: evolution branch-state creation collision"; exit 1;
  }
  (set -o noclobber; sha256sum "$branch_state_path" > "$branch_state_digest_path") || {
    echo "HARD STOP: evolution branch-state digest creation collision"; exit 1;
  }
fi
```

Unqualified Git source; the revision lives only in `uv.lock`, currently `ed6b50dc`.

- [ ] **Step 1: Isolated worktree**

The repository root is `~/d/cancer/mechanisms/evolution`, **not** `~/d/cancer` — the latter is not a Git repository.

```bash
cd ~/d/cancer/mechanisms/evolution && git rev-parse --show-toplevel   # confirm
git worktree add .worktrees/sidecar-retirement -b sidecar-retirement
cd .worktrees/sidecar-retirement
test "$(git branch --show-current)" = sidecar-retirement || {
  echo "HARD STOP: evolution migration worktree is on the wrong branch"; exit 1;
}
```

- [ ] **Step 2: Relock to the Task 7 SHA**

```bash
read -r -p 'Paste the exact approval record printed by Task 7 Step 1: ' approval_record
test "$(sha256sum "$approval_record")" = "$(cat "$approval_record.sha256")" || { echo "HARD STOP: approval record changed"; exit 1; }
attempt_root=$(awk -F '\t' '$1 == "attempt-root" {print $2}' "$approval_record")
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
validation_status=$?
test "$validation_status" -eq 1 || {
  echo "FAIL: validator exited $validation_status, expected approved baseline status 1"; exit 1;
}
read -r -p 'Paste the exact approval record printed by Task 7 Step 1: ' approval_record
test "$(sha256sum "$approval_record")" = "$(cat "$approval_record.sha256")" || { echo "HARD STOP: approval record changed"; exit 1; }
attempt_root=$(awk -F '\t' '$1 == "attempt-root" {print $2}' "$approval_record")
canonical_report=$(awk -F '\t' '$1 == "artifact" && $2 == "evolution-canonical" {print $3}' "$attempt_root/task-6-manifest.tsv")
test -f "$canonical_report" || { echo "HARD STOP: approved evolution canonical report missing"; exit 1; }
uv run --frozen science validate --all --strict --format json \
  --output /tmp/evo-after-complete.json > /tmp/evo-after-rendered.json
complete_status=$?
test "$complete_status" -eq 1 || {
  echo "FAIL: complete-report validator exited $complete_status, expected approved baseline status 1"; exit 1;
}
python3 - "$canonical_report" <<'PY'
import json
import sys

expected = json.load(open(sys.argv[1]))
actual = json.load(open("/tmp/evo-after-complete.json"))
print(actual["summary"])
assert actual == expected, "complete result differs from approved canonical baseline"
rules = {r.get("rule") for r in actual["results"]}
assert "validate.python-sidecar-removed" not in rules
assert not any(str(r or "").startswith("papers.background-review") for r in rules), rules
print("OK")
PY
```

Expected: both commands exit `1`, summary `18 errors / 41 warnings`, exact
complete-report parity with the approved canonical baseline, `OK`, and no
traceback. Strict validation already failed at the frozen consumer snapshot for
unrelated corpus findings; the resolved regression is the traceback, not those
findings. The first command is the exact Task 1 Step 2 reproduction.

- [ ] **Step 5: Confirm the notice out-of-band**

```bash
uv run --frozen science validate --all --strict --verbose | rg 'no status:background papers'
```

Expected: a match — all 15 papers are active, so a notice and zero warnings.

- [ ] **Step 6: Commit atomically, merge, clean up**

```bash
set -euo pipefail
git add -A && git commit -m "chore: adopt toolkit background-review check and drop the validation sidecar"
read -r -p 'Paste the exact approval record printed by Task 7 Step 1: ' approval_record
test "$(sha256sum "$approval_record")" = "$(cat "$approval_record.sha256")" || { echo "HARD STOP: approval record changed"; exit 1; }
attempt_root=$(awk -F '\t' '$1 == "attempt-root" {print $2}' "$approval_record")
test -n "$attempt_root" || { echo "HARD STOP: approval attempt root missing"; exit 1; }
source_root=~/d/cancer/mechanisms/evolution
branch_state_path="$attempt_root/consumer-primary-branch-evolution.tsv"
branch_state_digest_path="$branch_state_path.sha256"
test -f "$branch_state_path" && test ! -L "$branch_state_path" &&
  test -f "$branch_state_digest_path" && test ! -L "$branch_state_digest_path" || {
    echo "HARD STOP: approved evolution branch state is missing or not a regular file"; exit 1;
  }
test "$(sha256sum "$branch_state_path")" = "$(cat "$branch_state_digest_path")" || {
  echo "HARD STOP: approved evolution branch-state digest drift"; exit 1;
}
intended_source_branch=$(awk -F '\t' '$1 == "branch" {print $2}' "$branch_state_path")
test -n "$intended_source_branch" || { echo "HARD STOP: saved evolution primary branch is empty"; exit 1; }
expected_branch_state=$(printf 'consumer\tevolution\nattempt-root\t%s\napproval-record-digest\t%s\nsource-root\t%s\nbranch\t%s' \
  "$attempt_root" "$(sha256sum "$approval_record" | awk '{print $1}')" "$source_root" "$intended_source_branch")
test "$(cat "$branch_state_path")" = "$expected_branch_state" || {
  echo "HARD STOP: saved evolution branch state is malformed or belongs to another task"; exit 1;
}
current_source_branch=$(git -C "$source_root" symbolic-ref --quiet --short HEAD) || {
  echo "HARD STOP: evolution primary checkout is detached before merge"; exit 1;
}
test "$current_source_branch" = "$intended_source_branch" || {
  echo "HARD STOP: evolution primary branch changed from $intended_source_branch to $current_source_branch"; exit 1;
}
test -z "$(git -C "$source_root" status --porcelain)" || {
  echo "HARD STOP: evolution primary checkout is dirty before merge"; exit 1;
}
git -C "$source_root" merge --no-ff sidecar-retirement
git -C "$source_root" worktree remove .worktrees/sidecar-retirement
```

---

### Task 10: Migrate `~/d/protein-landscape` atomically

**Files:** `uv.lock:4412`, `AGENTS.md`; delete `validate_local.py`

**Entry gate:** Paste the exact immutable approval-record path from Task 7;
never discover authorization through `latest-attempt.txt`. Derive the attempt,
baseline, feature, published SHA, manifest digest, and exact clean consumer
snapshot from that record. No migration is authorized after drift. Capture the
primary checkout's exact nonempty branch in the approved attempt before
creating the migration worktree.

```bash
set -euo pipefail
read -r -p 'Paste the exact approval record printed by Task 7 Step 1: ' approval_record
test "$(sha256sum "$approval_record")" = "$(cat "$approval_record.sha256")" || { echo "HARD STOP: approval record changed"; exit 1; }
attempt_root=$(awk -F '\t' '$1 == "attempt-root" {print $2}' "$approval_record")
approved_baseline_sha=$(awk -F '\t' '$1 == "baseline-sha" {print $2}' "$approval_record")
approved_feature_sha=$(awk -F '\t' '$1 == "feature-sha" {print $2}' "$approval_record")
approved_manifest_digest=$(awk -F '\t' '$1 == "manifest-digest" {print $2}' "$approval_record")
test -n "$attempt_root" && test -n "$approved_baseline_sha" && test -n "$approved_feature_sha" || { echo "HARD STOP: incomplete approval record"; exit 1; }
test "$(sha256sum "$attempt_root/task-6-manifest.tsv" | awk '{print $1}')" = "$approved_manifest_digest" || { echo "HARD STOP: Task 6 manifest drift"; exit 1; }
test "$(awk -F '\t' '$1 == "toolkit-before" {print $2}' "$attempt_root/task-6-manifest.tsv")" = "$approved_baseline_sha"
test "$(awk -F '\t' '$1 == "feature-branch" {print $2}' "$attempt_root/task-6-manifest.tsv")" = "$approved_feature_sha"
source_root=~/d/protein-landscape
required_head=$(awk -F '\t' '$1 == "consumer" && $2 == "protein-landscape" {print $4}' "$attempt_root/task-6-manifest.tsv")
published_main_sha=$(cat "$attempt_root/published-main.sha")
test "$(git -C ~/d/science/.worktrees/sidecar-retirement ls-remote origin refs/heads/main | awk '{print $1}')" = "$published_main_sha" || { echo "HARD STOP: published main is not recorded SHA"; exit 1; }
test "$(git -C ~/d/science/.worktrees/sidecar-retirement rev-parse "$published_main_sha^1")" = "$approved_baseline_sha" || { echo "HARD STOP: published first parent is not approved baseline"; exit 1; }
test "$(git -C ~/d/science/.worktrees/sidecar-retirement rev-parse "$published_main_sha^2")" = "$approved_feature_sha" || { echo "HARD STOP: published second parent is not approved feature"; exit 1; }
test "$required_head" = 6796628c06a562ff45029f317a0f0fdf1a2fec9e || { echo "HARD STOP: protein-landscape missing from manifest"; exit 1; }
test -z "$(git -C "$source_root" status --porcelain)" || { echo "HARD STOP: protein-landscape source drift"; exit 1; }
test "$(git -C "$source_root" rev-parse HEAD)" = "$required_head" || { echo "HARD STOP: protein-landscape HEAD drift; recapture Task 6"; exit 1; }
intended_source_branch=$(git -C "$source_root" symbolic-ref --quiet --short HEAD) || {
  echo "HARD STOP: protein-landscape primary checkout is detached"; exit 1;
}
test -n "$intended_source_branch" || { echo "HARD STOP: protein-landscape primary branch is empty"; exit 1; }
branch_state_path="$attempt_root/consumer-primary-branch-protein-landscape.tsv"
branch_state_digest_path="$branch_state_path.sha256"
approval_record_digest=$(sha256sum "$approval_record" | awk '{print $1}')
expected_branch_state=$(printf 'consumer\tprotein-landscape\nattempt-root\t%s\napproval-record-digest\t%s\nsource-root\t%s\nbranch\t%s' \
  "$attempt_root" "$approval_record_digest" "$source_root" "$intended_source_branch")
if [[ -e "$branch_state_path" || -L "$branch_state_path" || -e "$branch_state_digest_path" || -L "$branch_state_digest_path" ]]; then
  test -f "$branch_state_path" && test ! -L "$branch_state_path" &&
    test -f "$branch_state_digest_path" && test ! -L "$branch_state_digest_path" || {
      echo "HARD STOP: protein-landscape branch-state collision is incomplete or not a regular file"; exit 1;
    }
  test "$(sha256sum "$branch_state_path")" = "$(cat "$branch_state_digest_path")" || {
    echo "HARD STOP: protein-landscape branch-state digest drift"; exit 1;
  }
  test "$(cat "$branch_state_path")" = "$expected_branch_state" || {
    echo "HARD STOP: protein-landscape branch-state collision differs from current approved state"; exit 1;
  }
else
  (set -o noclobber; printf '%s\n' "$expected_branch_state" > "$branch_state_path") || {
    echo "HARD STOP: protein-landscape branch-state creation collision"; exit 1;
  }
  (set -o noclobber; sha256sum "$branch_state_path" > "$branch_state_digest_path") || {
    echo "HARD STOP: protein-landscape branch-state digest creation collision"; exit 1;
  }
fi
```

Its check is **not** promoted — the expensive-artifact check becomes a project-owned command with nothing enforcing it (design §4).

- [ ] **Step 1: Isolated worktree, relock**

```bash
cd ~/d/protein-landscape && git worktree add .worktrees/sidecar-retirement -b sidecar-retirement
cd .worktrees/sidecar-retirement
test "$(git branch --show-current)" = sidecar-retirement || {
  echo "HARD STOP: protein-landscape migration worktree is on the wrong branch"; exit 1;
}
read -r -p 'Paste the exact approval record printed by Task 7 Step 1: ' approval_record
test "$(sha256sum "$approval_record")" = "$(cat "$approval_record.sha256")" || { echo "HARD STOP: approval record changed"; exit 1; }
attempt_root=$(awk -F '\t' '$1 == "attempt-root" {print $2}' "$approval_record")
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
read -r -p 'Paste the exact approval record printed by Task 7 Step 1: ' approval_record
test "$(sha256sum "$approval_record")" = "$(cat "$approval_record.sha256")" || { echo "HARD STOP: approval record changed"; exit 1; }
attempt_root=$(awk -F '\t' '$1 == "attempt-root" {print $2}' "$approval_record")
canonical_report=$(awk -F '\t' '$1 == "artifact" && $2 == "protein-landscape-canonical" {print $3}' "$attempt_root/task-6-manifest.tsv")
test -f "$canonical_report" || { echo "HARD STOP: approved protein-landscape canonical report missing"; exit 1; }
uv run --frozen science validate --all --strict --format json \
  --output /tmp/pl-after-complete.json > /tmp/pl-after.json
validation_status=$?
test "$validation_status" -eq 1 || {
  echo "FAIL: validator exited $validation_status, expected approved baseline status 1"; exit 1;
}
python3 - "$canonical_report" <<'PY'
import json
import sys

expected = json.load(open(sys.argv[1]))
actual = json.load(open("/tmp/pl-after-complete.json"))
print(actual["summary"])
assert actual == expected, "complete result differs from approved canonical baseline"
assert "validate.python-sidecar-removed" not in {
    r.get("rule") for r in actual["results"]
}
print("OK")
PY
```

Expected: status `1`, summary `13 errors / 642 warnings`, exact complete-report
parity with the approved canonical baseline, `OK`, and no traceback. Strict
validation already failed at the frozen consumer snapshot for unrelated corpus
findings; the resolved regression is the method-slice traceback, not those
findings.

- [ ] **Step 6: Commit atomically, merge, clean up**

```bash
set -euo pipefail
git add -A && git commit -m "chore: drop the validation sidecar; run artifact checks standalone"
read -r -p 'Paste the exact approval record printed by Task 7 Step 1: ' approval_record
test "$(sha256sum "$approval_record")" = "$(cat "$approval_record.sha256")" || { echo "HARD STOP: approval record changed"; exit 1; }
attempt_root=$(awk -F '\t' '$1 == "attempt-root" {print $2}' "$approval_record")
test -n "$attempt_root" || { echo "HARD STOP: approval attempt root missing"; exit 1; }
source_root=~/d/protein-landscape
branch_state_path="$attempt_root/consumer-primary-branch-protein-landscape.tsv"
branch_state_digest_path="$branch_state_path.sha256"
test -f "$branch_state_path" && test ! -L "$branch_state_path" &&
  test -f "$branch_state_digest_path" && test ! -L "$branch_state_digest_path" || {
    echo "HARD STOP: approved protein-landscape branch state is missing or not a regular file"; exit 1;
  }
test "$(sha256sum "$branch_state_path")" = "$(cat "$branch_state_digest_path")" || {
  echo "HARD STOP: approved protein-landscape branch-state digest drift"; exit 1;
}
intended_source_branch=$(awk -F '\t' '$1 == "branch" {print $2}' "$branch_state_path")
test -n "$intended_source_branch" || { echo "HARD STOP: saved protein-landscape primary branch is empty"; exit 1; }
expected_branch_state=$(printf 'consumer\tprotein-landscape\nattempt-root\t%s\napproval-record-digest\t%s\nsource-root\t%s\nbranch\t%s' \
  "$attempt_root" "$(sha256sum "$approval_record" | awk '{print $1}')" "$source_root" "$intended_source_branch")
test "$(cat "$branch_state_path")" = "$expected_branch_state" || {
  echo "HARD STOP: saved protein-landscape branch state is malformed or belongs to another task"; exit 1;
}
current_source_branch=$(git -C "$source_root" symbolic-ref --quiet --short HEAD) || {
  echo "HARD STOP: protein-landscape primary checkout is detached before merge"; exit 1;
}
test "$current_source_branch" = "$intended_source_branch" || {
  echo "HARD STOP: protein-landscape primary branch changed from $intended_source_branch to $current_source_branch"; exit 1;
}
test -z "$(git -C "$source_root" status --porcelain)" || {
  echo "HARD STOP: protein-landscape primary checkout is dirty before merge"; exit 1;
}
git -C "$source_root" merge --no-ff sidecar-retirement
git -C "$source_root" worktree remove .worktrees/sidecar-retirement
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

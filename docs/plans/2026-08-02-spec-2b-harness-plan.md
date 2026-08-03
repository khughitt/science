# Spec 2b — Supervised Run Harness Implementation Plan

**Status: complete.** All 9 tasks executed, all 56 steps done, all 42 mutation rows certified
killed ([`2026-08-02-spec-2b-mutation-ledger.md`](2026-08-02-spec-2b-mutation-ledger.md)).
Verified on the finished branch: full CLI suite 12,843 passed / 7 skipped / 0 failed
(pytest exit 0), `ruff check` clean, `pyright` 0 errors. Task 9 was added mid-execution and is
not in the numbered task list below; its brief closed the ingestion-lock defect Task 5's review
surfaced. Follow-ups deliberately carried past merge are named in design §9.

> **For agentic workers:** this plan is finished — it is kept as the execution record, not as
> work to pick up. Its steps are checked off; do not re-execute them.

**Goal:** Build `science autonomy run` — one command that opens an autonomous run, runs
`science health` as its actor, gates the result, and ingests the report under an attestation
the supervisor dictated.

**Architecture:** A deterministic supervisor owns the working tree, the branch, and two
commits; the actor owns bytes at one path. The loop is a library function in
`autonomy/harness.py` returning a `HarnessOutcome` or raising `HarnessError`; the CLI renders
it and maps it to exit codes. Every git call goes through `autonomy/git.py`, which builds the
argv so no call site can forget the hardening.

**Tech Stack:** Python 3.13, click, pydantic v2, pytest, git 2.55.

**Design:** [`2026-08-02-supervised-run-harness-design.md`](2026-08-02-supervised-run-harness-design.md),
now at revision 8. Section references below point at it, and were written against revision 5;
revisions 6–8 came out of reviews *of the built loop* and changed three things this plan's task
text predates — `_settle` gates the graph on a CLEAN disposition, the actor writes to
supervisor-owned temporary storage rather than a project path, and every gateway call carries a
`--work-tree` pin. The design is authoritative; where this plan and the design disagree, the
design is what shipped.

## Global Constraints

- There is **no root `pyproject.toml`**: python tooling runs from `science/`.
  Tests: `uv run --frozen pytest`. Lint: `uv run ruff check`. Types: `uv run pyright`.
  Every such command below is written as `(cd science && …)` — in a **subshell**, so the
  directory change does not persist. Git commands that follow name paths from the repository
  root, and a lingering `cd science` would turn `git add science/src/…` into a path that does
  not exist.
- Use **scoped** pytest selections. The full CLI suite is ~12k tests and takes 6:42–7:24,
  longer than the default command timeout. Never run it inside a subagent.
- Conventional commits. **No AI-attribution trailer or footer** on any commit, PR, or comment.
- No "legacy"/"compatibility" layers. No `Unified` prefix. Composition over inheritance.
  Explicit over defensive. Fail early rather than falling back silently.
- No absolute paths beginning `/home/` or `/mnt/` in code, comments, or docs.
- Fixed values, from design §3.4: `agent="health-audit"`, `model="deterministic"`,
  `tier=RunTier.REPORT_ONLY`, `tokens=None`, full health check selection.
- Identities, from design §3.4.3: `AGENT_EMAIL = "agent@science.local"` (existing),
  `SUPERVISOR_NAME = "science-supervisor"`, `SUPERVISOR_EMAIL = "supervisor@science.local"`.
- Exit codes, from design §3.4: 0 clean+ingested, 1 quarantined, 2 unwired, 3 `HarnessError`,
  4 clean-but-ingestion-refused.
- **Shared test helpers and fixtures go in `science/tests/conftest.py`**, requested by name —
  not imported from a sibling test module.

  Correcting the reason this constraint used to give: cross-module imports *do* resolve here.
  `science/tests/` has no `__init__.py`, and under pytest's default `prepend` import mode that
  is precisely why `tests/` lands on `sys.path`. Ten modules in the suite already rely on it
  (`test_autonomous_run_predicates.py` imports from `test_autonomous_runs.py`,
  `test_graph_origins.py` from `test_graph_materialize.py`, …); both were run and pass. The
  constraint stands as a **convention**, not a limitation: an import makes one test module's
  collection depend on another's contents, and a helper two modules need is shared state, which
  is what `conftest.py` is for. Do not "fix" the existing importers.

---

## File Structure

| File | Responsibility |
|---|---|
| `src/science_tool/autonomy/git.py` | **modified** — named write primitives; the argv for `checkout`/`clean`/`add`/`commit` is built here |
| `src/science_tool/autonomy/marks.py` | **modified** — two supervisor identity constants |
| `src/science_tool/autonomy/lifecycle.py` | **modified** — `start_run` restore postcondition |
| `src/science_tool/autonomy/harness.py` | **new** — `HarnessOutcome`, `HarnessError`, `run_supervised_audit` |
| `src/science_tool/autonomy/cli.py` | **modified** — the `run` command |
| `src/science_tool/graph/health.py` | **modified** — `expected_producer_ids` |
| `src/science_tool/graph/health_cli.py` | **modified** — `--ingestion-ref` / `--generated-at` |
| `src/science_tool/findings/ingest.py` | **modified** — `ingestion_authority` |
| `src/science_tool/findings/cli.py` | **modified** — cut over to `ingestion_authority` |
| `src/science_tool/budget/registry.py` | **modified** — classify `autonomy run` |
| `docs/user-guide/cli-and-workflows.md` | **modified** — register the command surface |
| `tests/conftest.py` | **modified** — `plant_attacks`, `ungraphed_project`, `supervised_project` fixtures |
| `tests/test_autonomy_git_writes.py` | **new** — Task 1 |
| `tests/test_autonomy_start_restore.py` | **new** — Task 2 |
| `tests/test_health_attested_provenance.py` | **new** — Task 3 |
| `tests/test_findings_ingestion_authority.py` | **new** — Task 4 |
| `tests/test_autonomy_harness.py` | **new** — Tasks 5, 6; extended by Task 7 |
| `docs/plans/2026-08-02-spec-2b-mutation-ledger.md` | **new** — Task 7 |

**Dependencies:** Tasks 1–4 are independent of each other, though 1, 2 and 5 each append a
fixture to `tests/conftest.py` — run them in order rather than concurrently. Task 5 needs all
four. Task 6 needs
5. Task 7 needs 6. Task 8 is independent of everything and may run at any point.

---

## Task 1: Git write primitives

Design §3.5. The loop introduces the first *write* subcommands in the autonomy surface. Their
argv is built in `autonomy/git.py` so no call site can omit the hardening — that module's own
rule: "what none of them may differ on is the argv, which is why it is built here and nowhere
else."

**Files:**
- Modify: `src/science_tool/autonomy/git.py`
- Modify: `science/tests/conftest.py` — the `plant_attacks` factory fixture
- Test: `science/tests/test_autonomy_git_writes.py` (create)

**Interfaces:**
- Consumes: `run_git(repo_root, *args) -> CompletedProcess[bytes]`, `GitError` — both existing
  in `autonomy/git.py`.
- Produces, in `science/tests/conftest.py`:
  - `plant_attacks` — a fixture returning `plant(root: Path) -> Path` (the sentinels directory).
    Task 7 uses it too; see design §8.3 for why both levels are needed.
- Produces, all in `autonomy/git.py`:
  - `current_branch(repo_root: Path) -> str | None` — `None` on a detached HEAD
  - `create_branch(repo_root: Path, name: str) -> None` — fails if it exists
  - `switch_branch(repo_root: Path, name: str) -> None`
  - `restore_worktree(repo_root: Path) -> None`
  - `stage_all(repo_root: Path) -> None`
  - `worktree_status(repo_root: Path) -> str` — `git status --porcelain`, stripped
  - `commit_tree(repo_root: Path, *, message: str, author: str, committer_name: str, committer_email: str) -> str` — returns the new sha
  - All raise `GitError` on a non-zero exit.

- [x] **Step 1: Write the failing tests**

Create `science/tests/test_autonomy_git_writes.py`:

```python
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from science_tool.autonomy.git import (
    GitError,
    commit_tree,
    create_branch,
    current_branch,
    restore_worktree,
    stage_all,
    switch_branch,
    worktree_status,
)

SUPERVISOR = {"committer_name": "science-supervisor", "committer_email": "supervisor@science.local"}


def _plain_git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "-C", str(root), *args],
        capture_output=True, text=True, check=True,
    ).stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _plain_git(root, "init", "-q")
    (root / "a.txt").write_text("one\n", encoding="utf-8")
    _plain_git(root, "add", "-A")
    _plain_git(root, "commit", "-q", "-m", "base")
    return root


def test_current_branch_names_the_checked_out_branch(repo: Path):
    assert current_branch(repo) == _plain_git(repo, "rev-parse", "--abbrev-ref", "HEAD")


def test_current_branch_is_none_on_a_detached_head(repo: Path):
    _plain_git(repo, "checkout", "-q", "--detach")
    assert current_branch(repo) is None


def test_create_branch_switches_to_it(repo: Path):
    create_branch(repo, "auto/x")
    assert current_branch(repo) == "auto/x"


def test_create_branch_refuses_an_existing_name(repo: Path):
    create_branch(repo, "auto/x")
    switch_branch(repo, _plain_git(repo, "rev-parse", "--abbrev-ref", "HEAD@{-1}"))
    with pytest.raises(GitError):
        create_branch(repo, "auto/x")


def test_restore_worktree_discards_modifications_and_untracked_files(repo: Path):
    (repo / "a.txt").write_text("two\n", encoding="utf-8")
    (repo / "new.txt").write_text("x\n", encoding="utf-8")
    (repo / "sub").mkdir()
    (repo / "sub" / "deep.txt").write_text("y\n", encoding="utf-8")

    restore_worktree(repo)

    assert worktree_status(repo) == ""
    assert (repo / "a.txt").read_text(encoding="utf-8") == "one\n"
    assert not (repo / "new.txt").exists()
    assert not (repo / "sub").exists()


def test_commit_tree_splits_author_from_committer(repo: Path):
    (repo / "b.txt").write_text("b\n", encoding="utf-8")
    stage_all(repo)

    sha = commit_tree(
        repo,
        message="audit: report\n\nScience-Run: run:2026-08-02-health-audit-a1b2",
        author="health-audit <agent@science.local>",
        **SUPERVISOR,
    )

    assert sha == _plain_git(repo, "rev-parse", "HEAD")
    assert _plain_git(repo, "log", "-1", "--format=%an <%ae>") == "health-audit <agent@science.local>"
    assert _plain_git(repo, "log", "-1", "--format=%cn <%ce>") == "science-supervisor <supervisor@science.local>"
    trailer = _plain_git(repo, "log", "-1", "--format=%(trailers:key=Science-Run,valueonly)").strip()
    assert trailer == "run:2026-08-02-health-audit-a1b2"


def test_commit_tree_raises_when_there_is_nothing_to_commit(repo: Path):
    with pytest.raises(GitError):
        commit_tree(repo, message="empty", author="a <a@b.c>", **SUPERVISOR)
```

- [x] **Step 2: Run the tests to verify they fail**

Run: `(cd science && uv run --frozen pytest tests/test_autonomy_git_writes.py -q)`
Expected: collection error — `ImportError: cannot import name 'commit_tree'`.

- [x] **Step 3: Add the primitives**

Append to `src/science_tool/autonomy/git.py`, after `run_git`:

```python
def _checked(repo_root: Path, *args: str) -> bytes:
    """Run one hardened git command, failing closed on anything but a clean exit.

    `run_git` deliberately returns the exit status because its readers need different
    dispositions. Every WRITE has the same one: a write that did not happen is not a state
    this harness may continue from.
    """
    result = run_git(repo_root, *args)
    if result.returncode != 0:
        message = result.stderr.decode("utf-8", "replace").strip()
        raise GitError(f"git {' '.join(args)} failed in {repo_root}: {message}")
    return result.stdout


def current_branch(repo_root: Path) -> str | None:
    """The checked-out branch, or None on a detached HEAD.

    `--abbrev-ref HEAD` answers the literal string `HEAD` when detached, which is not a
    branch name any caller may compare against.
    """
    name = _checked(repo_root, "rev-parse", "--abbrev-ref", "HEAD").decode("utf-8", "replace").strip()
    return None if name == "HEAD" else name


def worktree_status(repo_root: Path) -> str:
    return _checked(repo_root, "status", "--porcelain").decode("utf-8", "replace").strip()


def create_branch(repo_root: Path, name: str) -> None:
    """Create `name` and check it out. Fails if it already exists.

    Exclusive on purpose: a run id collision must refuse rather than resume another run's
    branch, matching `write_baseline` and `write_run_record`.
    """
    _checked(repo_root, "checkout", "-b", name)


def switch_branch(repo_root: Path, name: str) -> None:
    _checked(repo_root, "checkout", name)


def restore_worktree(repo_root: Path) -> None:
    """Discard every tracked modification and remove every untracked file.

    Restores TO the commit, not away from a named path: a caller that lists the paths it
    expects to have written has a hole the moment something else writes one.
    """
    _checked(repo_root, "checkout", "--", ".")
    _checked(repo_root, "clean", "-fd")


def stage_all(repo_root: Path) -> None:
    _checked(repo_root, "add", "-A")


def commit_tree(
    repo_root: Path,
    *,
    message: str,
    author: str,
    committer_name: str,
    committer_email: str,
) -> str:
    """Commit the index and return the new sha.

    `--no-gpg-sign` is pinned HERE rather than at the call site. `_HARDENING`'s
    `log.showSignature=false` governs signature VERIFICATION under `log`; it says nothing
    about `commit.gpgsign=true` with an actor-supplied `gpg.program`, which reaches a program
    during this commit. A flag a caller must remember is a flag a later caller forgets.

    The committer identity is passed as `-c` overrides so the commit succeeds in a repository
    with no configured `user.name`, and so the supervisor's identity cannot be supplied by the
    repository the actor controls.
    """
    _checked(
        repo_root,
        "-c", f"user.name={committer_name}",
        "-c", f"user.email={committer_email}",
        "commit", "--no-gpg-sign", "--author", author, "-m", message,
    )
    return _checked(repo_root, "rev-parse", "HEAD").decode("utf-8", "replace").strip()
```

- [x] **Step 4: Run the tests to verify they pass**

Run: `(cd science && uv run --frozen pytest tests/test_autonomy_git_writes.py -q)`
Expected: 7 passed.

- [x] **Step 5: Add the hostile-configuration fixture**

Design §8.3. Two tests at two levels plant the same vectors — this one over the write
primitives, Task 7's over the whole loop — so the planter is a **conftest factory fixture**, not
a helper one test module imports from another.

`tmp_path` is the anchor for the workshop because every repository fixture here is a *subdirectory*
of it (`tmp_path / "repo"`, `tmp_path / "ungraphed"`), so `tmp_path / "workshop"` is a sibling
of the repository under test and never inside it — which is the property the docstring below
depends on.

Append to `science/tests/conftest.py`:

```python
@pytest.fixture
def plant_attacks(tmp_path: Path):
    """Factory: arm a repository with every git-config vector the write primitives reach.

    Returns `plant(root) -> sentinels_dir`. Each vector writes a sentinel file into that
    directory; a test's assertion is that the directory is still empty afterwards.

    NOTHING IS PLANTED AS AN UNTRACKED FILE IN THE PROJECT. `start_run`'s
    `assert_repository_is_at` refuses any dirty tree, untracked files included, so a driver
    script dropped beside the entities would make the run refuse BEFORE the vector was
    reached -- the test would pass without the defence ever running. The scripts live in
    `workshop`, a SIBLING of the repository under test; everything else lives under `.git/`,
    which git does not report.

    For the same reason the filter attribute goes in `$GIT_DIR/info/attributes` rather than an
    untracked `.gitattributes`. That is also the stronger probe: it is one of the three
    attribute layers `_filter_driver_overrides` covers, `--attr-source` does not reach it, and
    it is invisible to `git status` -- the actor-controlled layer the threat model is about.
    """
    workshop = tmp_path / "workshop"
    sentinels = workshop / "sentinels"
    sentinels.mkdir(parents=True, exist_ok=True)

    def _script(name: str, body: str = "") -> Path:
        path = workshop / f"{name}.sh"
        path.write_text(f"#!/bin/sh\ntouch {sentinels / name}\n{body}", encoding="utf-8")
        path.chmod(0o755)
        return path

    def _plant(root: Path) -> Path:
        hooks = root / ".git" / "hooks"
        hooks.mkdir(parents=True, exist_ok=True)
        # `prepare-commit-msg` is planted because the probe claims it: a hook named in the
        # docstring and absent from the fixture is a coverage claim nothing backs.
        for hook in (
            "pre-commit", "prepare-commit-msg", "commit-msg", "post-commit", "post-checkout"
        ):
            path = hooks / hook
            path.write_text(f"#!/bin/sh\ntouch {sentinels / hook}\n", encoding="utf-8")
            path.chmod(0o755)

        driver = _script("filter", "cat\n")
        gpg = _script("gpg", "exit 1\n")
        fsmonitor = _script("fsmonitor")

        (root / ".git" / "info").mkdir(parents=True, exist_ok=True)
        (root / ".git" / "info" / "attributes").write_text("* filter=evil\n", encoding="utf-8")
        config = root / ".git" / "config"
        config.write_text(
            config.read_text(encoding="utf-8")
            + f'[filter "evil"]\n\tclean = {driver}\n\tsmudge = {driver}\n'
            + f"[core]\n\tfsmonitor = {fsmonitor}\n"
            + "[commit]\n\tgpgsign = true\n"
            + f"[gpg]\n\tprogram = {gpg}\n",
            encoding="utf-8",
        )
        return sentinels

    return _plant
```

- [x] **Step 6: Write the hostile-configuration test**

Append to `science/tests/test_autonomy_git_writes.py`:

```python
def test_no_planted_vector_executes_through_the_write_primitives(repo: Path, plant_attacks):
    sentinels = plant_attacks(repo)

    create_branch(repo, "auto/hostile")
    (repo / "c.txt").write_text("c\n", encoding="utf-8")
    stage_all(repo)
    commit_tree(repo, message="hostile", author="a <a@b.c>", **SUPERVISOR)
    worktree_status(repo)
    restore_worktree(repo)

    assert sorted(p.name for p in sentinels.iterdir()) == [], (
        "a planted git-config vector reached a program through the write primitives"
    )
```

- [x] **Step 7: Run it**

Run: `(cd science && uv run --frozen pytest tests/test_autonomy_git_writes.py -q)`
Expected: 8 passed. If the `gpg` sentinel appears, `--no-gpg-sign` is missing from
`commit_tree`; if `filter` appears, the call is not going through `run_git`.

- [x] **Step 8: Record the probe in the module docstring**

`git.py`'s docstring records, per subcommand, what was built as a working attack and what
executed. Add a paragraph in the same form, after the existing `cat-file` rows:

```
* `checkout -b`, `checkout -- .`, `clean -fd`, `add -A` and `commit` -- the harness's write
  subcommands (Spec 2b design §3.5). Every key `_HARDENING` already pins is INERT here for the
  reason it is inert elsewhere: `core.hooksPath=/dev/null` disarms `pre-commit`,
  `prepare-commit-msg`, `commit-msg`, `post-commit` and `post-checkout` alike, and a hook
  dropped straight into `$GIT_DIR/hooks/` with it. `filter.<driver>.clean` bound through
  `$GIT_DIR/info/attributes` -- the layer no `--attr-source` reaches -- EXECUTES under `add`
  and is neutralized by `_filter_driver_overrides`, not by a fixed key.
* `commit.gpgsign=true` with `gpg.program=./gpg.sh` -- EXECUTES, under `commit`. This is the
  one row the existing set does not cover: `log.showSignature=false` governs VERIFICATION
  under `log` and has no bearing on SIGNING. `--no-gpg-sign` on the commit argv disarms it;
  blanking `gpg.program` does not, because signing stays enabled and git falls back to the
  default `gpg` on `PATH`. Pinned in `commit_tree`, not at the call site.
```

- [x] **Step 9: Lint, type-check, and commit**

```bash
(cd science && uv run ruff check && uv run pyright)
git add science/src/science_tool/autonomy/git.py science/tests/test_autonomy_git_writes.py \
  science/tests/conftest.py
git commit -m "feat(autonomy): build the harness's git write argv in the gateway"
```

---

## Task 2: `start_run` leaves the tree at `base_commit`

Design §4.1. `start_run` materializes the graph and leaves the result behind. The postcondition
is scoped: *once `assert_repository_is_at` has succeeded and capture has begun*, `start_run`
removes its own residue before returning or raising. A failure of the precondition itself must
leave the caller's dirty tree untouched.

**Files:**
- Modify: `src/science_tool/autonomy/lifecycle.py:211-291` (`start_run`)
- Modify: `science/tests/conftest.py` (add `ungraphed_project`)
- Test: `science/tests/test_autonomy_start_restore.py` (create)

**Interfaces:**
- Consumes: `restore_worktree`, `worktree_status` from Task 1.
- Produces: `ungraphed_project` fixture — a git project with a real belief basis and **no
  committed `knowledge/graph.trig`**.

**The fixture choice is load-bearing.** `test_autonomy_lifecycle.py`'s `project` fixture
materializes and commits the graph *before* `git init`, precisely so the supervisor's own
rebuild leaves a clean tree. Against that fixture the broken and the fixed implementation are
indistinguishable — measured: `git status --porcelain` is empty after `start_run` either way.
A test for this defect needs a project whose graph is **absent**.

- [x] **Step 1: Add the fixture**

Append to `science/tests/conftest.py`:

```python
@pytest.fixture
def ungraphed_project(tmp_path: Path) -> Path:
    """A git project with a real belief basis and NO committed `knowledge/graph.trig`.

    The distinction from `test_autonomy_lifecycle.py`'s `project` fixture is the whole point.
    That one materializes and commits the graph before `git init`, so `start_run`'s rebuild is
    byte-identical and leaves the tree clean -- which makes it useless for testing that
    `start_run` cleans up after itself, because nothing is left to clean. This one has never
    materialized, so the rebuild is the supervisor's own residue.
    """
    import subprocess

    root = tmp_path / "ungraphed"
    (root / "entities" / "propositions").mkdir(parents=True)
    (root / "entities" / "papers").mkdir(parents=True)
    (root / "entities" / "evidence-lines").mkdir(parents=True)
    (root / "science.yaml").write_text(
        "name: harness-fixture\nknowledge_profiles:\n  local: local\n", encoding="utf-8"
    )
    (root / "entities" / "propositions" / "p1.md").write_text(
        "---\nid: proposition:p1\nkind: proposition\ntitle: P1\n---\n\nClaim.\n", encoding="utf-8"
    )
    (root / "entities" / "papers" / "x.md").write_text(
        "---\nid: paper:x\nkind: paper\ntitle: X\nvenue: Nature\n"
        'pmid: "111"\nyear: 2020\nurl: https://example.org/x\n---\n\nBody.\n',
        encoding="utf-8",
    )
    (root / "entities" / "evidence-lines" / "e1.md").write_text(
        "---\nid: evidence-line:e1\nkind: evidence-line\ntitle: Evidence line\n"
        "stance: supports\ntarget: proposition:p1\nsource: paper:x\n"
        "strength: strong\nbelief_eligible: true\n---\n",
        encoding="utf-8",
    )
    for args in (("init", "-q"), ("add", "-A"), ("commit", "-q", "-m", "base")):
        subprocess.run(
            ["git", "-c", "user.email=t@t", "-c", "user.name=t", "-C", str(root), *args],
            capture_output=True, check=True,
        )
    return root
```

- [x] **Step 2: Write the failing tests**

Create `science/tests/test_autonomy_start_restore.py`:

```python
from __future__ import annotations

import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest
from science_model.autonomous_runs import RunTier

from science_tool.autonomy import lifecycle as lifecycle_module
from science_tool.autonomy.baseline import BaselineError
from science_tool.autonomy.git import worktree_status
from science_tool.autonomy.lifecycle import start_run


def _start(project: Path, baseline_out: Path):
    return start_run(
        project, agent="health-audit", model="deterministic", tier=RunTier.REPORT_ONLY,
        short_id="a1b2", started=datetime(2026, 8, 2, 9, 0, tzinfo=UTC),
        baseline_out=baseline_out,
    )


def test_start_leaves_no_materialization_residue(ungraphed_project: Path, tmp_path: Path):
    """Design §1.1: `_capture` materializes into the project, and a supervisor that then
    stages the actor's output sweeps its own write into the actor's attested range."""
    _start(ungraphed_project, tmp_path / "state" / "baseline.json")

    assert worktree_status(ungraphed_project) == ""


def test_start_removes_its_residue_when_it_raises(
    ungraphed_project: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """The postcondition must survive the error paths: `start_run` can raise four more times
    after materializing, and residue left behind blocks the NEXT run rather than this one."""
    real_capture = lifecycle_module._capture

    def _capture_then_fail(project_root: Path):
        real_capture(project_root)
        raise RuntimeError("capture blew up after materializing")

    monkeypatch.setattr(lifecycle_module, "_capture", _capture_then_fail)

    with pytest.raises(RuntimeError):
        _start(ungraphed_project, tmp_path / "state" / "baseline.json")

    assert worktree_status(ungraphed_project) == ""


def test_a_dirty_input_tree_is_refused_byte_for_byte_unchanged(
    ungraphed_project: Path, tmp_path: Path
):
    """Design §4.1: the postcondition begins AFTER `assert_repository_is_at` succeeds. On the
    one path where the tree is legitimately dirty, the dirt is the CALLER's."""
    tracked = ungraphed_project / "entities" / "propositions" / "p1.md"
    tracked.write_text(tracked.read_text(encoding="utf-8") + "\nEdited.\n", encoding="utf-8")
    untracked = ungraphed_project / "entities" / "propositions" / "p2.md"
    untracked.write_text("---\nid: proposition:p2\nkind: proposition\ntitle: P2\n---\n", encoding="utf-8")
    before = (tracked.read_text(encoding="utf-8"), untracked.read_text(encoding="utf-8"))

    with pytest.raises(BaselineError):
        _start(ungraphed_project, tmp_path / "state" / "baseline.json")

    assert tracked.exists() and untracked.exists()
    assert (tracked.read_text(encoding="utf-8"), untracked.read_text(encoding="utf-8")) == before
```

- [x] **Step 3: Run them to verify they fail**

Run: `(cd science && uv run --frozen pytest tests/test_autonomy_start_restore.py -q)`
Expected: the first two FAIL with a non-empty status naming `?? knowledge/`. The third
PASSES already — `assert_repository_is_at` raises before anything is written. Keep it: it is
the regression guard that stops Step 4 from over-restoring.

- [x] **Step 4: Scope the restore around `_capture`**

In `src/science_tool/autonomy/lifecycle.py`, add the import:

```python
from science_tool.autonomy.git import (
    GitOutputTooLarge,
    history_traversal_error,
    restore_worktree,
    run_git,
)
```

Then replace the single `result = _capture(project_root)` line inside `start_run` with:

```python
    # The restore is scoped to `_capture` ALONE, and both halves of that matter.
    #
    # `materialize_graph` writes `knowledge/graph.trig` into the project, so a run opened
    # against a project whose committed graph is absent or stale leaves residue -- which the
    # harness would then sweep into the ACTOR's attested range, where `report-only` denies it
    # (design §1.1). Restoring here, rather than in the caller, means every caller of
    # `start_run` gets it, including `science autonomy start`.
    #
    # `try`/`finally` rather than a restore before each `return`/`raise`: `start_run` can raise
    # four more times below, and residue left behind blocks the NEXT run rather than this one.
    #
    # It must NOT wrap `assert_repository_is_at`. That is the one path where a dirty tree is
    # the CALLER's uncommitted work, and restoring it would destroy what the check exists to
    # refuse.
    try:
        result = _capture(project_root)
    finally:
        restore_worktree(project_root)
```

- [x] **Step 5: Run them to verify they pass**

Run: `(cd science && uv run --frozen pytest tests/test_autonomy_start_restore.py -q)`
Expected: 3 passed.

- [x] **Step 6: Run the neighbouring suites**

Run: `(cd science && uv run --frozen pytest tests/test_autonomy_lifecycle.py tests/test_autonomy_record_writer.py tests/test_autonomy_perturbation_alarm.py -q)`
Expected: all pass. The `project` fixture commits its graph, so the restore is a no-op there.
If a test fails because it *expected* residue, stop and report it — that is a real behaviour
change the design should name, not a test to adjust.

- [x] **Step 7: Commit**

```bash
(cd science && uv run ruff check && uv run pyright)
git add science/src/science_tool/autonomy/lifecycle.py science/tests/test_autonomy_start_restore.py science/tests/conftest.py
git commit -m "fix(autonomy): leave no materialization residue when a run opens"
```

---

## Task 3: `health` accepts a dictated provenance

Design §5.1, §5.2. `execute_health_report` already takes `ingestion_ref` and `generated_at`;
only the CLI invents them. And the producer set the supervisor must attest is derivable from
the same selection function health uses.

**Files:**
- Modify: `src/science_tool/graph/health.py` (add `expected_producer_ids`)
- Modify: `src/science_tool/graph/health_cli.py:217-218`
- Test: `science/tests/test_health_attested_provenance.py` (create)

**Interfaces:**
- Consumes: `_select_health_checks(*, checks, skip_checks, fast) -> tuple[HealthCheck, ...]`,
  `SCHEMA_INVALID_PRODUCER` — both existing in `graph/health.py`.
- Produces:
  - `expected_producer_ids(*, checks=None, skip_checks=None, fast=False) -> frozenset[str]`
  - `science health --ingestion-ref TEXT --generated-at TEXT`, required together.

- [x] **Step 1: Write the failing tests**

Create `science/tests/test_health_attested_provenance.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from science_tool.cli import cli
from science_tool.graph.health import execute_health_report, expected_producer_ids


def _declared(report) -> frozenset[str]:
    """What ingestion will demand: every producer the report says ran, either way."""
    return frozenset(report.meta.producers_run) | {u.producer_id for u in report.unwired}


@pytest.mark.parametrize(
    "selection",
    [
        {},
        {"fast": True},
        {"checks": frozenset({"managed_artifacts", "tooling_scaffold"})},
        {"checks": frozenset({"entity_identity"})},
        {"skip_checks": frozenset({"validate"})},
    ],
    ids=["full", "fast", "two-source-free", "one-source-requiring", "skip-one"],
)
def test_the_prediction_equals_what_the_report_declares(ungraphed_project: Path, selection):
    """Design §8.1: one full-health fixture cannot kill a literal-list mutation, because a
    list transcribed correctly today matches today's set. Source-free and source-requiring
    selections differ by `schema_invalid`, which appears in neither `--list-checks` nor any
    check's producer id."""
    execution = execute_health_report(
        ungraphed_project,
        ingestion_ref="run:2026-08-02-health-audit-a1b2",
        generated_at="2026-08-02T09:00:00.000000+00:00",
        **selection,
    )

    assert expected_producer_ids(**selection) == _declared(execution.report)


def test_schema_invalid_is_predicted_only_when_sources_load(ungraphed_project: Path):
    assert "schema_invalid" in expected_producer_ids()
    assert "schema_invalid" not in expected_producer_ids(fast=True)


def test_the_cli_echoes_the_dictated_provenance(ungraphed_project: Path, tmp_path: Path):
    out = tmp_path / "report.json"
    result = CliRunner().invoke(
        cli,
        [
            "health", "--project-root", str(ungraphed_project),
            "--format", "json", "--output", str(out),
            "--ingestion-ref", "run:2026-08-02-health-audit-a1b2",
            "--generated-at", "2026-08-02T09:00:00.000000+00:00",
        ],
    )

    assert result.exit_code in (0, 2), result.output
    import json

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["ingestion_ref"] == "run:2026-08-02-health-audit-a1b2"
    assert payload["generated_at"] == "2026-08-02T09:00:00.000000+00:00"


def test_the_two_provenance_options_are_required_together(ungraphed_project: Path):
    result = CliRunner().invoke(
        cli,
        ["health", "--project-root", str(ungraphed_project), "--ingestion-ref", "run:x"],
    )

    assert result.exit_code != 0
    assert "--generated-at" in result.output
```

- [x] **Step 2: Run them to verify they fail**

Run: `(cd science && uv run --frozen pytest tests/test_health_attested_provenance.py -q)`
Expected: `ImportError: cannot import name 'expected_producer_ids'`.

- [x] **Step 3: Add `expected_producer_ids`**

In `src/science_tool/graph/health.py`, immediately after `_select_health_checks`:

```python
def expected_producer_ids(
    *,
    checks: set[str] | frozenset[str] | None = None,
    skip_checks: set[str] | frozenset[str] | None = None,
    fast: bool = False,
) -> frozenset[str]:
    """The producer ids a run of this selection will declare.

    A supervisor attesting an ingestion must know the complete producer set WITHOUT reading
    the report -- an attestation derived from the thing it attests is not an attestation.

    Derived from `_select_health_checks`, the same function `execute_health_report` calls, so
    there is no second list to drift. `schema_invalid` is not a health check and never appears
    in `--list-checks`; it is produced whenever sources are loaded, under the same condition
    `execute_health_report` applies.
    """
    selected = _select_health_checks(checks=checks, skip_checks=skip_checks, fast=fast)
    ids = {check.producer.producer_id for check in selected}
    if any(check.requires_sources for check in selected):
        ids.add(SCHEMA_INVALID_PRODUCER.producer_id)
    return frozenset(ids)
```

- [x] **Step 4: Add the CLI options**

In `src/science_tool/graph/health_cli.py`, add two options to the `health` command declaration
in `src/science_tool/cli.py` where the other `health` options are declared, or to
`health_command`'s decorators if they live in `health_cli.py` — follow whichever file already
carries `--severity`. The option declarations:

```python
@click.option(
    "--ingestion-ref", default=None,
    help="Supervisor-dictated ingestion reference. Requires --generated-at.",
)
@click.option(
    "--generated-at", default=None,
    help="Supervisor-dictated ISO-8601 generation instant. Requires --ingestion-ref.",
)
```

Add both to `health_command`'s signature as `ingestion_ref: str | None` and
`generated_at: str | None`, then replace lines 217-218:

```python
    if (ingestion_ref is None) != (generated_at is None):
        raise click.UsageError(
            "--ingestion-ref and --generated-at must be supplied together: a dictated "
            "reference with an invented timestamp is not an attestable provenance"
        )
    if ingestion_ref is None:
        ingestion_ref = f"health:{uuid4().hex}"
        generated_at = datetime.now(timezone.utc).isoformat(timespec="microseconds")
```

- [x] **Step 5: Run them to verify they pass**

Run: `(cd science && uv run --frozen pytest tests/test_health_attested_provenance.py -q)`
Expected: 8 passed (5 parametrized + 3).

- [x] **Step 6: Run the health suites**

Run: `(cd science && uv run --frozen pytest tests/test_health.py tests/test_health_projection.py tests/test_health_subject_contract.py tests/test_command_docs.py -q)`
Expected: all pass.

- [x] **Step 7: Commit**

```bash
(cd science && uv run ruff check && uv run pyright)
git add science/src/science_tool/graph/health.py science/src/science_tool/graph/health_cli.py science/src/science_tool/cli.py science/tests/test_health_attested_provenance.py
git commit -m "feat(health): accept a dictated ingestion provenance and predict its producers"
```

---

## Task 4: One derivation of the ingestion authority

Design §5.4. `ingest_report` requires a `FindingRegistry` and an `IngestionContext`, and both
are authority. Today only a private CLI helper knows how to build them.

**Files:**
- Modify: `src/science_tool/findings/ingest.py`
- Modify: `src/science_tool/findings/cli.py:44-52`
- Test: `science/tests/test_findings_ingestion_authority.py` (create)

**Interfaces:**
- Produces: `ingestion_authority(project_root: Path) -> tuple[FindingRegistry, IngestionContext]`
  in `findings/ingest.py`.

- [x] **Step 1: Write the failing test**

Create `science/tests/test_findings_ingestion_authority.py`:

```python
from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from science_tool.findings import cli as findings_cli
from science_tool.findings.ingest import IngestionContext, ingestion_authority


def test_it_returns_a_registry_and_a_context_over_the_project(ungraphed_project: Path):
    registry, context = ingestion_authority(ungraphed_project)

    assert isinstance(context, IngestionContext)
    assert "proposition:p1" in context.canonical_entity_ids
    assert registry.rule("managed-artifact.missing") is not None


def test_it_loads_sources_without_relaxing_identity(
    ungraphed_project: Path, monkeypatch: pytest.MonkeyPatch
):
    """Spec 1 §8: ingestion keeps `strict_identity=True`, so an identity conflict refuses the
    write. Health passes `strict_identity=False` on purpose, to carry conflicts into its audit
    gate -- reusing the health loader here would silently ingest what should be refused.

    Asserted on the CALL, not on the source text: a source-text assertion cannot tell a
    docstring from an argument, so a correct implementation that merely EXPLAINS the rule in a
    comment would fail it.
    """
    import science_tool.findings.ingest as ingest_module
    from science_tool.graph import sources as sources_module

    seen: dict[str, object] = {}
    real = sources_module.load_project_sources

    def _record(project_root, **kwargs):
        seen.update(kwargs)
        return real(project_root, **kwargs)

    monkeypatch.setattr(sources_module, "load_project_sources", _record)
    ingest_module.ingestion_authority(ungraphed_project)

    assert seen.get("strict_identity", True) is True, (
        "the strict default must stand: a relaxed identity check ingests a conflict that "
        "Spec 1 refuses"
    )


def test_the_cli_uses_the_shared_derivation():
    """One spelling, not two that can drift. The old private helpers are gone.

    `.callback`, not the command object: `@findings_group.command("ingest")` rebinds the name
    to a `click.core.Command`, and `inspect.getsource` on that raises
    `TypeError: module, class, method, function, traceback, frame, or code object was
    expected` -- measured. Click keeps the undecorated function on `.callback`.
    """
    assert not hasattr(findings_cli, "_load_ingestion_context")
    assert not hasattr(findings_cli, "_registry")
    assert "ingestion_authority" in inspect.getsource(findings_cli.ingest_command.callback)
```

- [x] **Step 2: Run it to verify it fails**

Run: `(cd science && uv run --frozen pytest tests/test_findings_ingestion_authority.py -q)`
Expected: `ImportError: cannot import name 'ingestion_authority'`.

- [x] **Step 3: Add the derivation**

In `src/science_tool/findings/ingest.py`, after the `IngestionContext` class:

```python
def ingestion_authority(project_root: Path) -> tuple[FindingRegistry, IngestionContext]:
    """The registry and entity universe `ingest_report` judges a report against.

    BOTH ARE AUTHORITY, NOT DATA. Neither may come from the report, and three wrong answers
    are each one step away: reusing anything the actor produced; reusing the health run's
    `load_project_sources(..., strict_identity=False)`, which is lenient on purpose so
    materialization can carry identity conflicts into its audit gate; or reaching into
    `findings/cli.py` for its private helper.

    `load_project_sources` is called with its defaults, which include `strict_identity=True`:
    an identity conflict refuses the write rather than being ingested (Spec 1 design §8).
    """
    from science_tool.findings.catalog import build_registry_for_entity_registry
    from science_tool.graph.sources import load_project_sources

    sources = load_project_sources(project_root)
    context = IngestionContext(
        canonical_entity_ids=frozenset(entity.canonical_id for entity in sources.entities)
    )
    return build_registry_for_entity_registry(sources.registry), context
```

- [x] **Step 4: Cut the CLI over**

**Do not keep the old helpers as adapters.** The existing call site
(`findings/cli.py:262`) reads

```python
        context, entity_registry = _load_ingestion_context(project_root)
        outcome = ingest_report(project_root, report, _registry(entity_registry), ...)
```

so `_load_ingestion_context` returns an **`EntityRegistry`** which `_registry` then converts to
a `FindingRegistry`. `ingestion_authority` returns the `FindingRegistry` already, so wrapping it
in `_registry` would pass the wrong type — `build_registry_for_entity_registry` would receive a
`FindingRegistry`. Change the call site instead:

```python
        registry, context = ingestion_authority(project_root)
        outcome = ingest_report(
            project_root,
            report,
            registry,
            provenance=provenance,
            context=context,
        )
```

Then **delete** `_load_ingestion_context` and `_registry` from `findings/cli.py:37-52`, and add
`from science_tool.findings.ingest import ingestion_authority` to the imports the command
already makes. Before deleting `_registry`, check for other callers:

```bash
(cd science && grep -rn "_registry(\|_load_ingestion_context" src/ tests/)
```

If either has another caller, cut that one over too rather than keeping the helper — two
spellings of one derivation is the defect this task removes.

- [x] **Step 5: Run the tests**

Run: `(cd science && uv run --frozen pytest tests/test_findings_ingestion_authority.py tests/test_findings_cli.py tests/test_findings_ingest.py -q)`
Expected: all pass.

- [x] **Step 6: Commit**

```bash
(cd science && uv run ruff check && uv run pyright)
git add science/src/science_tool/findings/ingest.py science/src/science_tool/findings/cli.py science/tests/test_findings_ingestion_authority.py
git commit -m "refactor(findings): give the ingestion authority one derivation"
```

---

## Task 5: The supervised run loop

Design §3.4, §4, §4.5. The nine-step loop, end to end.

**Files:**
- Create: `src/science_tool/autonomy/harness.py`
- Modify: `src/science_tool/autonomy/marks.py` (two constants)
- Modify: `science/tests/conftest.py` (add `supervised_project`)
- Test: `science/tests/test_autonomy_harness.py` (create)

**Interfaces:**
- Consumes: Task 1's git primitives; Task 2's restored `start_run`; Task 3's
  `expected_producer_ids` and the two health CLI options; Task 4's `ingestion_authority`.
- Produces:
  - `HarnessError(RuntimeError)`
  - `HarnessOutcome` — frozen pydantic model, fields per design §3.4
  - `run_supervised_audit(project_root: Path, *, started: datetime, short_id: str) -> HarnessOutcome`

- [x] **Step 1: Add the identity constants**

In `src/science_tool/autonomy/marks.py`, beside `AGENT_EMAIL`:

```python
#: The supervisor's own commit identity. Observable in every repository's history, and
#: therefore contract: `verify_marks` reads the AUTHOR of a run's commits, so the supervisor
#: commits the actor's bytes under the agent's authorship while committing as itself.
SUPERVISOR_NAME = "science-supervisor"
SUPERVISOR_EMAIL = "supervisor@science.local"
```

- [x] **Step 2: Add the fixture**

Append to `science/tests/conftest.py`:

```python
@pytest.fixture
def supervised_project(ungraphed_project: Path, monkeypatch) -> Path:
    """`ungraphed_project` with the toolkit-cleanliness check pinned.

    `assert_toolkit_matches` refuses a dirty judging toolkit, and the checkout these tests run
    in is dirty exactly while this plan is being implemented -- which is not what any harness
    test is about. Lifted from `test_autonomy_lifecycle.py`'s `pinned_toolkit` fixture.
    """
    from science_tool.autonomy import toolkit as toolkit_module

    monkeypatch.setattr(toolkit_module, "toolkit_is_clean", lambda root=None: True)
    return ungraphed_project
```

- [x] **Step 3: Write the end-to-end test**

Create `science/tests/test_autonomy_harness.py`:

```python
from __future__ import annotations

import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest
from science_model.autonomous_runs import RunDisposition

from science_tool.autonomy.git import current_branch, worktree_status
from science_tool.autonomy.harness import HarnessError, run_supervised_audit

STARTED = datetime(2026, 8, 2, 9, 0, tzinfo=UTC)


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True, check=True
    ).stdout.strip()


def test_a_supervised_run_completes_and_leaves_the_tree_clean(supervised_project: Path):
    """Design §8: asserting the disposition alone would pass for a loop that stranded the
    operator on `auto/<slug>` with a dirty tree -- which is the failure §1.1 found by hand."""
    start_branch = current_branch(supervised_project)

    outcome = run_supervised_audit(supervised_project, started=STARTED, short_id="a1b2")

    assert outcome.disposition is RunDisposition.CLEAN
    assert outcome.ingestion is not None and outcome.ingestion.records_written > 0
    assert outcome.ingestion_refusal is None
    assert outcome.record_written is True

    assert current_branch(supervised_project) == start_branch
    assert worktree_status(supervised_project) == ""

    slug = outcome.run_id.removeprefix("run:")
    report = f"doc/audits/reports/{slug}.json"
    assert _git(supervised_project, "ls-tree", "--name-only", f"auto/{slug}", report) == report
    assert _git(supervised_project, "ls-tree", "--name-only", "HEAD", report) == ""
    assert _git(supervised_project, "ls-tree", "--name-only", "HEAD", f"runs/{slug}.md")
    assert _git(supervised_project, "ls-tree", "-d", "--name-only", "HEAD", "doc/audits/cases")


def test_the_record_is_not_inside_its_own_range(supervised_project: Path):
    """`validate/checks/autonomous_runs.py`'s forgery discriminator: a supervisor-written
    record cannot appear inside the range it names."""
    outcome = run_supervised_audit(supervised_project, started=STARTED, short_id="a1b2")
    slug = outcome.run_id.removeprefix("run:")

    added = _git(
        supervised_project, "log", "--format=%H", "--diff-filter=A", "-1",
        f"{_git(supervised_project, 'rev-parse', 'HEAD~1')}..{outcome.capture_commit}",
        "--", f"runs/{slug}.md",
    )

    assert added == ""


def test_the_capture_commit_carries_the_agent_authorship_and_the_run_trailer(
    supervised_project: Path,
):
    outcome = run_supervised_audit(supervised_project, started=STARTED, short_id="a1b2")

    author = _git(supervised_project, "log", "-1", "--format=%an <%ae>", outcome.capture_commit)
    trailer = _git(
        supervised_project, "log", "-1",
        "--format=%(trailers:key=Science-Run,valueonly)", outcome.capture_commit,
    ).strip()

    assert author == "health-audit <agent@science.local>"
    assert trailer == outcome.run_id


def test_the_post_verdict_commit_is_the_supervisors_and_unmarked(supervised_project: Path):
    outcome = run_supervised_audit(supervised_project, started=STARTED, short_id="a1b2")
    assert outcome.post_verdict_commit is not None

    author = _git(
        supervised_project, "log", "-1", "--format=%an <%ae>", outcome.post_verdict_commit
    )
    trailer = _git(
        supervised_project, "log", "-1",
        "--format=%(trailers:key=Science-Run,valueonly)", outcome.post_verdict_commit,
    ).strip()

    assert author == "science-supervisor <supervisor@science.local>"
    assert trailer == ""


def test_the_autonomous_runs_check_is_silent_from_the_starting_branch(supervised_project: Path):
    """The whole point of committing the record OUTSIDE the auto branch: `_marked_commits`
    scans `--all` while `load_run_records` reads the current tree."""
    from science_tool.validate.checks.autonomous_runs import check_autonomous_runs
    from science_tool.validate.context import ValidateContext

    run_supervised_audit(supervised_project, started=STARTED, short_id="a1b2")

    # `ValidateContext` is a dataclass with six required fields; this check reads only
    # `project_root`. Shape lifted from `test_autonomy_validate_check.py::_ctx`.
    ctx = ValidateContext(
        project_root=supervised_project,
        doc_dir=supervised_project / "doc",
        specs_dir=supervised_project / "entities" / "specs",
        manifest={},
        strict=False,
        verbose=False,
    )
    observations = list(check_autonomous_runs(ctx))

    assert observations == []


def test_a_detached_head_is_refused_before_the_run_opens(supervised_project: Path):
    _git(supervised_project, "checkout", "-q", "--detach")

    with pytest.raises(HarnessError, match="named branch"):
        run_supervised_audit(supervised_project, started=STARTED, short_id="a1b2")


def test_an_existing_auto_branch_refuses_the_run(supervised_project: Path):
    _git(supervised_project, "branch", "auto/2026-08-02-health-audit-a1b2")

    with pytest.raises(HarnessError):
        run_supervised_audit(supervised_project, started=STARTED, short_id="a1b2")


def test_the_actor_runs_the_supervisors_own_toolkit(supervised_project: Path):
    """Design §3.2: `-P` keeps the project root off `sys.path`, so a planted package cannot
    shadow the real one. The project tree is actor-controlled; it is the one directory this
    subprocess must not import from."""
    shadow = supervised_project / "science_tool"
    shadow.mkdir()
    (shadow / "__init__.py").write_text("raise SystemExit('shadowed')\n", encoding="utf-8")
    (shadow / "__main__.py").write_text("raise SystemExit('shadowed')\n", encoding="utf-8")
    _git(supervised_project, "add", "-A")
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "-C", str(supervised_project),
         "commit", "-q", "-m", "plant"],
        capture_output=True, check=True,
    )

    outcome = run_supervised_audit(supervised_project, started=STARTED, short_id="a1b2")

    assert outcome.actor_exit_code in (0, 2)
```

- [x] **Step 4: Run them to verify they fail**

Run: `(cd science && uv run --frozen pytest tests/test_autonomy_harness.py -q)`
Expected: collection error — `No module named 'science_tool.autonomy.harness'`.

- [x] **Step 5: Write the harness**

Create `src/science_tool/autonomy/harness.py`:

```python
"""The supervised run loop (Spec 2b design §4).

THE ACTOR OWNS BYTES AT ONE PATH; THE SUPERVISOR OWNS EVERYTHING ELSE -- the working tree, the
branch, both commits, the commit identities, and every attested value. Every value this module
attests is worth something only because its authority lives outside the actor, which is also
why the supervisor is deterministic code rather than a model reasoning about the work.
"""

from __future__ import annotations

import secrets
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

from pydantic import BaseModel, ConfigDict
from science_model.autonomous_runs import RunDisposition, RunTier

from science_tool.autonomy.control_plane import run_dir
from science_tool.autonomy.git import (
    commit_tree,
    create_branch,
    current_branch,
    restore_worktree,
    stage_all,
    switch_branch,
    worktree_status,
)
from science_tool.autonomy.lifecycle import finish_run, start_run
from science_tool.autonomy.marks import AGENT_EMAIL, SUPERVISOR_EMAIL, SUPERVISOR_NAME
from science_tool.autonomy.record_writer import generate_run_id
from science_tool.findings.ingest import (
    IngestError,
    IngestionProvenance,
    IngestOutcome,
    ingest_report,
    ingestion_authority,
    load_report,
)
from science_tool.graph.health import expected_producer_ids

AGENT = "health-audit"
MODEL = "deterministic"
TIER = RunTier.REPORT_ONLY


class HarnessError(RuntimeError):
    """An orchestration step failed. No outcome exists.

    Distinct from `unwired`, which is a VERDICT -- the run was judged and could not be seen.
    A `HarnessOutcome` is returned only when the loop reached a verdict, which is why
    `capture_commit` is not optional.
    """


class HarnessOutcome(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: str
    disposition: RunDisposition
    reason: str
    actor_exit_code: int
    capture_commit: str
    post_verdict_commit: str | None
    record_written: bool
    ingestion: IngestOutcome | None
    ingestion_refusal: str | None


def generate_short_id() -> str:
    return secrets.token_hex(2)


def _now() -> datetime:
    return datetime.now(UTC)


def _run_actor(project_root: Path, *, report_path: Path, ingestion_ref: str, generated_at: str):
    """Run `science health` as a subprocess, pinned to the supervisor's own installation.

    `sys.executable` rather than a bare `science` from `PATH`: a different toolkit revision
    than the one attested in `toolkit_revision` would be invisible, since
    `assert_toolkit_matches` checks the SUPERVISOR's toolkit, not the actor's.

    `-P` keeps the current directory and the script directory off `sys.path`, and `cwd` is a
    supervisor-owned temporary directory rather than the project. The project tree is
    actor-controlled; it is the one directory this subprocess must not import from, and it is
    named only by the explicit `--project-root`.
    """
    with tempfile.TemporaryDirectory() as neutral_cwd:
        return subprocess.run(
            [
                sys.executable, "-P", "-m", "science_tool", "health",
                "--project-root", str(project_root),
                "--format", "json",
                "--output", str(report_path),
                "--ingestion-ref", ingestion_ref,
                "--generated-at", generated_at,
            ],
            cwd=neutral_cwd,
            capture_output=True,
        )


def _settle(project_root: Path, *, record_written: bool, run_id: str) -> str | None:
    """Leave the starting branch clean, and say whether a commit was made (design §4.5).

    Branches on whether a RECORD exists, not on the disposition: `finish_run` returns
    `unwired` with `record=None` on five paths, and a run that produced no attestation must
    not have derived state committed on its behalf.

    Checks for nothing to settle rather than passing `--allow-empty`: a `finish_run` that
    failed before `_capture` leaves no materialization behind, and an empty commit would
    record something that means nothing.
    """
    if not worktree_status(project_root):
        return None
    if not record_written:
        restore_worktree(project_root)
        return None
    stage_all(project_root)
    return commit_tree(
        project_root,
        message=f"chore(autonomy): record {run_id}",
        author=f"{SUPERVISOR_NAME} <{SUPERVISOR_EMAIL}>",
        committer_name=SUPERVISOR_NAME,
        committer_email=SUPERVISOR_EMAIL,
    )


@contextmanager
def _step(description: str):
    """Normalize one orchestration step's failure into `HarnessError`.

    "Every orchestration failure raises `HarnessError`" is a claim about NORMALIZATION, not
    about the functions this loop happens to call. `current_branch`, `run_dir`, `stage_all` and
    the report directory's `mkdir` all raise `GitError` or `OSError` of their own, and the CLI
    catches only `HarnessError` -- so an unnormalized path exits 1 with a traceback instead of
    3. Every step goes through here, and the message names the step.

    `GitError`, `BaselineError`, `RepositoryStateError` and `IngestError` are all `ValueError`
    subclasses -- verified, not assumed -- so `ValueError` covers every expected refusal in the
    loop and naming them individually would be noise that goes stale.
    """
    try:
        yield
    except HarnessError:
        raise
    except (OSError, ValueError) as exc:
        raise HarnessError(f"{description}: {exc}") from exc


def run_supervised_audit(
    project_root: Path, *, started: datetime, short_id: str
) -> HarnessOutcome:
    """Open a run, run the deterministic actor, gate it, and ingest its report.

    `started` and `short_id` are parameters rather than internals so the loop is testable
    without patching a clock or a random source.
    """
    with _step("could not read the current branch"):
        starting_branch = current_branch(project_root)
    if starting_branch is None:
        raise HarnessError(
            "the harness must start from a named branch: it returns there when the run ends, "
            "and a detached HEAD gives that no destination"
        )

    # The run id must be known BEFORE `start_run`, because the baseline's location is derived
    # from it. Built with the same function `start_run` uses, not by formatting the parts by
    # hand: `generate_run_id` also validates the agent and short id, so a value the record
    # could never carry is refused here rather than after the tree has been touched.
    with _step("the run id could not be built"):
        run_id = generate_run_id(started.date(), AGENT, short_id)
        baseline_path = run_dir(project_root, run_id) / "baseline.json"

    with _step("the run could not be opened"):
        baseline = start_run(
            project_root,
            agent=AGENT, model=MODEL, tier=TIER, short_id=short_id, started=started,
            baseline_out=baseline_path,
        )

    assert baseline.run_id == run_id
    slug = run_id.removeprefix("run:")
    report_relative = f"doc/audits/reports/{slug}.json"

    with _step(
        f"could not create {baseline.branch} -- an existing branch is a run-id collision, "
        "and resuming another run's branch is not a recovery"
    ):
        create_branch(project_root, baseline.branch)

    report_path = project_root / report_relative
    with _step("the report directory could not be created"):
        report_path.parent.mkdir(parents=True, exist_ok=True)

    generated_at = _now().isoformat(timespec="microseconds")
    elapsed = perf_counter()
    with _step("the actor could not be started"):
        completed = _run_actor(
            project_root,
            report_path=report_path,
            ingestion_ref=run_id,
            generated_at=generated_at,
        )
    wall_clock_seconds = perf_counter() - elapsed

    # Exit 2 is NOT actor failure: `science health` writes a complete report and then exits 2
    # for an invalid acceptance configuration (design §4.2).
    if completed.returncode not in (0, 2):
        raise HarnessError(
            f"the actor exited {completed.returncode}: "
            f"{completed.stderr.decode('utf-8', 'replace').strip()}"
        )

    with _step("could not re-read the current branch"):
        landed_on = current_branch(project_root)
    if landed_on != baseline.branch:
        raise HarnessError(
            f"the actor left {baseline.branch} for {landed_on!r}; nothing is captured, "
            "finished, or ingested, and every branch is left intact for triage"
        )

    with _step("the actor's output could not be captured"):
        stage_all(project_root)
        capture_commit = commit_tree(
            project_root,
            message=f"audit: {AGENT} report\n\nScience-Run: {run_id}",
            author=f"{AGENT} <{AGENT_EMAIL}>",
            committer_name=SUPERVISOR_NAME,
            committer_email=SUPERVISOR_EMAIL,
        )

    with _step("the run could not be finished"):
        outcome = finish_run(
            project_root,
            baseline_path=baseline_path,
            expect_run=run_id,
            head=capture_commit,
            ended=_now(),
            tokens=None,
            wall_clock_seconds=wall_clock_seconds,
            report_path=report_relative,
        )

    ingestion: IngestOutcome | None = None
    refusal: str | None = None
    if outcome.disposition is RunDisposition.CLEAN:
        try:
            registry, context = ingestion_authority(project_root)
            report = load_report(project_root, report_path)
            ingestion = ingest_report(
                project_root,
                report,
                registry,
                provenance=IngestionProvenance(
                    ingestion_ref=run_id,
                    generated_at=generated_at,
                    producer_ids=frozenset(expected_producer_ids()),
                ),
                context=context,
                actor=AGENT,
            )
        # `OSError` belongs here with the rest: `load_report` reaches the filesystem, so an
        # unreadable report is a refusal to INGEST -- not a reason to abandon the tree before
        # step 9, which is what letting it escape would do.
        except (IngestError, OSError, ValueError) as exc:
            refusal = str(exc)

    with _step("the run's results could not be settled"):
        switch_branch(project_root, starting_branch)
        post_verdict_commit = _settle(
            project_root, record_written=outcome.record is not None, run_id=run_id
        )

    return HarnessOutcome(
        run_id=run_id,
        disposition=outcome.disposition,
        reason=outcome.reason,
        actor_exit_code=completed.returncode,
        capture_commit=capture_commit,
        post_verdict_commit=post_verdict_commit,
        record_written=outcome.record is not None,
        ingestion=ingestion,
        ingestion_refusal=refusal,
    )
```

- [x] **Step 6: Run the tests**

Run: `(cd science && uv run --frozen pytest tests/test_autonomy_harness.py -q)`
Expected: 8 passed.

`IngestionProvenance`'s fields are `ingestion_ref: str`, `generated_at: str`, and
`producer_ids: frozenset[str]` (`findings/ingest.py:81-89`), each with a validator that refuses
empty or NUL-bearing values — verified, not assumed.

- [x] **Step 7: Commit**

```bash
(cd science && uv run ruff check && uv run pyright)
git add science/src/science_tool/autonomy/harness.py science/src/science_tool/autonomy/marks.py science/tests/test_autonomy_harness.py science/tests/conftest.py
git commit -m "feat(autonomy): run a supervised audit end to end"
```

---

## Task 6: The `science autonomy run` command

Design §3.4, §6.1.

**Files:**
- Modify: `src/science_tool/autonomy/cli.py`
- Modify: `src/science_tool/budget/registry.py:281-292`
- Modify: `docs/user-guide/cli-and-workflows.md`
- Test: `science/tests/test_autonomy_harness.py` (extend)

**Interfaces:**
- Consumes: `run_supervised_audit`, `HarnessOutcome`, `HarnessError`, `generate_short_id`.

- [x] **Step 1: Write the failing tests**

Append to `science/tests/test_autonomy_harness.py`:

```python
def test_the_command_exits_zero_on_a_clean_ingested_run(supervised_project: Path):
    from click.testing import CliRunner

    from science_tool.cli import cli

    result = CliRunner().invoke(
        cli, ["autonomy", "run", "--project-root", str(supervised_project)]
    )

    assert result.exit_code == 0, result.output


def test_the_command_exits_three_on_an_orchestration_failure(supervised_project: Path):
    from click.testing import CliRunner

    from science_tool.cli import cli

    _git(supervised_project, "checkout", "-q", "--detach")

    result = CliRunner().invoke(
        cli, ["autonomy", "run", "--project-root", str(supervised_project)]
    )

    assert result.exit_code == 3, result.output


def test_the_command_exits_four_when_ingestion_refuses(
    supervised_project: Path, monkeypatch: pytest.MonkeyPatch
):
    """Design §7: a run that produced an unusable report has not achieved its purpose, even
    though the autonomous disposition is clean."""
    from click.testing import CliRunner

    from science_tool.autonomy import harness as harness_module
    from science_tool.cli import cli
    from science_tool.findings.ingest import IngestError

    def _refuse(*args, **kwargs):
        raise IngestError("refused for the test")

    monkeypatch.setattr(harness_module, "ingest_report", _refuse)

    result = CliRunner().invoke(
        cli, ["autonomy", "run", "--project-root", str(supervised_project)]
    )

    assert result.exit_code == 4, result.output


@pytest.mark.parametrize(
    ("disposition", "expected_code"),
    [("quarantined", 1), ("unwired", 2)],
)
def test_the_command_maps_each_disposition_to_its_exit_code(
    supervised_project: Path, monkeypatch: pytest.MonkeyPatch, disposition, expected_code
):
    """Codes 1 and 2 need no end-to-end run: the mapping is the thing under test, and a
    constructed outcome exercises it without a second full loop."""
    from click.testing import CliRunner

    from science_tool.autonomy import harness as harness_module
    from science_tool.autonomy.harness import HarnessOutcome
    from science_tool.cli import cli

    outcome = HarnessOutcome(
        run_id="run:2026-08-02-health-audit-a1b2",
        disposition=RunDisposition(disposition),
        reason="constructed for the exit-code mapping",
        actor_exit_code=0,
        capture_commit="0" * 40,
        post_verdict_commit=None,
        record_written=True,
        ingestion=None,
        ingestion_refusal=None,
    )
    # Patch the HARNESS module, not the CLI one: `run_command` imports the function inside its
    # body, so the name is resolved from `science_tool.autonomy.harness` at call time and an
    # attribute set on the CLI module would never be consulted.
    monkeypatch.setattr(harness_module, "run_supervised_audit", lambda *a, **k: outcome)

    result = CliRunner().invoke(
        cli, ["autonomy", "run", "--project-root", str(supervised_project)]
    )

    assert result.exit_code == expected_code, result.output


def test_the_command_is_classified_for_the_budget_boundary():
    from science_tool.budget.registry import BUDGETS, DEFERRED, EXEMPTIONS

    assert "autonomy run" in (set(BUDGETS) | set(DEFERRED) | set(EXEMPTIONS))
```

- [x] **Step 2: Run them to verify they fail**

Run: `(cd science && uv run --frozen pytest tests/test_autonomy_harness.py -q -k 'command_exits or classified')`
Expected: `Error: No such command 'run'`.

- [x] **Step 3: Add the command**

In `src/science_tool/autonomy/cli.py`, after `finish_command`:

```python
@autonomy_group.command("run")
@click.option(
    "--project-root", type=click.Path(path_type=Path), default=Path("."), show_default=True,
)
@click.option(
    "--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table",
    show_default=True,
)
def run_command(project_root: Path, output_format: str) -> None:
    """Run one supervised audit: open, run the actor, gate, ingest, record.

    Exit codes: 0 clean and ingested, 1 quarantined, 2 unwired, 3 an orchestration failure,
    4 clean but ingestion refused. Code 4 is not a success: the run's purpose was an
    ingestible report, and a refused one did not achieve it.
    """
    import sys
    from datetime import UTC, datetime

    from science_model.autonomous_runs import RunDisposition

    from science_tool.autonomy.harness import (
        HarnessError,
        generate_short_id,
        run_supervised_audit,
    )

    try:
        outcome = run_supervised_audit(
            project_root.resolve(),
            started=datetime.now(UTC),
            short_id=generate_short_id(),
        )
    except HarnessError as exc:
        click.echo(f"harness error: {exc}", err=True)
        sys.exit(3)

    payload = outcome.model_dump(mode="json")

    def render_text() -> None:
        click.echo(f"{outcome.disposition.value}: {outcome.reason}")
        if outcome.ingestion is not None:
            click.echo(
                f"  ingested {outcome.ingestion.records_written} new case(s), "
                f"{outcome.ingestion.occurrences_appended} occurrence(s)"
            )
        if outcome.ingestion_refusal is not None:
            click.echo(f"  ingestion refused: {outcome.ingestion_refusal}")

    emit(output_format=output_format, payload=payload, render_text=render_text)

    if outcome.disposition is RunDisposition.QUARANTINED:
        sys.exit(1)
    if outcome.disposition is RunDisposition.UNWIRED:
        sys.exit(2)
    if outcome.ingestion_refusal is not None:
        sys.exit(4)
```

If `emit` is not already imported in `autonomy/cli.py`, follow how `start_command` renders its
summary and match it.

- [x] **Step 4: Classify the command**

In `src/science_tool/budget/registry.py`, beside its three siblings:

```python
    "autonomy run": DeferredCommand(
        "one fixed summary record per invocation, plus what `finish` reports",
        "1b",
    ),
```

- [x] **Step 5: Register the surface**

Add a row for `science autonomy run` to `docs/user-guide/cli-and-workflows.md`, in the same
form as the neighbouring `autonomy start` / `autonomy finish` entries.

- [x] **Step 6: Run the tests**

Run: `(cd science && uv run --frozen pytest tests/test_autonomy_harness.py tests/test_budget_boundary.py tests/test_command_docs.py -q)`
Expected: all pass.

- [x] **Step 7: Commit**

```bash
(cd science && uv run ruff check && uv run pyright)
git add science/src/science_tool/autonomy/cli.py science/src/science_tool/budget/registry.py docs/user-guide/cli-and-workflows.md science/tests/test_autonomy_harness.py
git commit -m "feat(autonomy): register the supervised run command surface"
```

---

## Task 7: Certify every mutation row

Design §8. Twenty-nine rows. The discipline, from plan 4c: apply **one** mutation alone,
require a **named** test to fail **for the stated reason**, revert, require the same test to
pass before the next row.

A row whose test fails for a different reason than the one stated certifies nothing. If a
mutation leaves every test green, that is a finding: either the guard is not guarded or the
row is wrong. Record it either way.

**Files:**
- Create: `docs/plans/2026-08-02-spec-2b-mutation-ledger.md`

**Interfaces:**
- Consumes: every test written in Tasks 1–6.

- [x] **Step 1: Write the ledger header**

Create `docs/plans/2026-08-02-spec-2b-mutation-ledger.md` with a header naming the production
baseline sha, and a table with columns `# | Mutation | Test node | Observed result`.

- [x] **Step 2: Certify rows 1–9 (the loop)**

| # | Mutation | Test node |
|---|---|---|
| 1 | Delete the `try`/`finally` restore in `start_run` | `test_autonomy_start_restore.py::test_start_leaves_no_materialization_residue` |
| 2 | Restore after `_capture` returns, not in a `finally` | `test_autonomy_start_restore.py::test_start_removes_its_residue_when_it_raises` |
| 3 | Restore `knowledge/graph.trig` by name instead of `restore_worktree` | `test_autonomy_git_writes.py::test_restore_worktree_discards_modifications_and_untracked_files` |
| 4 | Delete the `current_branch != baseline.branch` check | `test_autonomy_harness.py::test_an_actor_that_leaves_the_branch_is_refused` |
| 5 | `create_branch` uses `checkout -B` instead of `-b` | `test_autonomy_harness.py::test_an_existing_auto_branch_refuses_the_run` |
| 6 | Author the capture commit as the supervisor | `test_autonomy_harness.py::test_the_capture_commit_carries_the_agent_authorship_and_the_run_trailer` |
| 7 | Drop the `Science-Run` trailer from the capture message | `test_autonomy_harness.py::test_a_supervised_run_completes_and_leaves_the_tree_clean` |
| 8 | `_settle` before `switch_branch` | `test_autonomy_harness.py::test_the_autonomous_runs_check_is_silent_from_the_starting_branch` |
| 9 | Return before `_settle` | `test_autonomy_harness.py::test_a_supervised_run_completes_and_leaves_the_tree_clean` |

**Row 4's test must *induce* the condition, not merely be able to notice it.** The happy path
never leaves `auto/<slug>`, so it passes with the check deleted. Add this to
`test_autonomy_harness.py` before certifying, and point the row at it:

```python
def test_an_actor_that_leaves_the_branch_is_refused(
    supervised_project: Path, monkeypatch: pytest.MonkeyPatch
):
    from science_tool.autonomy import harness as harness_module

    real = harness_module._run_actor

    def _wander(project_root: Path, **kwargs):
        completed = real(project_root, **kwargs)
        subprocess.run(
            ["git", "-C", str(project_root), "checkout", "-q", "-b", "elsewhere"],
            capture_output=True, check=True,
        )
        return completed

    monkeypatch.setattr(harness_module, "_run_actor", _wander)

    with pytest.raises(HarnessError, match="left"):
        run_supervised_audit(supervised_project, started=STARTED, short_id="a1b2")
```

- [x] **Step 3: Certify rows 10–14 (attestation and the actor)**

| # | Mutation | Test node |
|---|---|---|
| 10 | Ingest regardless of disposition | add `test_a_quarantined_run_ingests_nothing` (below) |
| 11 | Replace `expected_producer_ids` with a literal 16-element list | `test_health_attested_provenance.py::test_the_prediction_equals_what_the_report_declares[fast]` |
| 12 | Read `generated_at` from the loaded report | add `test_the_attested_instant_is_the_commissioned_one` (below) |
| 13 | Accept a `None` starting branch | `test_autonomy_harness.py::test_a_detached_head_is_refused_before_the_run_opens` |
| 14 | Accept only exit 0 from the actor | add `test_an_actor_exit_two_still_completes` (below) |

Add all three tests to `test_autonomy_harness.py` before certifying:

```python
def test_a_quarantined_run_ingests_nothing(
    supervised_project: Path, monkeypatch: pytest.MonkeyPatch
):
    """A denied run's report is not evidence of anything."""
    from science_tool.autonomy import harness as harness_module

    real = harness_module._run_actor

    def _also_write_elsewhere(project_root: Path, **kwargs):
        completed = real(project_root, **kwargs)
        (project_root / "entities" / "propositions" / "p9.md").write_text(
            "---\nid: proposition:p9\nkind: proposition\ntitle: P9\n---\n", encoding="utf-8"
        )
        return completed

    monkeypatch.setattr(harness_module, "_run_actor", _also_write_elsewhere)

    outcome = run_supervised_audit(supervised_project, started=STARTED, short_id="a1b2")

    assert outcome.disposition is RunDisposition.QUARANTINED
    assert outcome.ingestion is None
    assert not (supervised_project / "doc" / "audits" / "cases").exists()


def test_the_attested_instant_is_the_commissioned_one(
    supervised_project: Path, monkeypatch: pytest.MonkeyPatch
):
    """Design §8.2: real `health` echoes the dictated timestamp, so 'dictate it' and 'read it
    back' are observationally identical against the real actor. This patches the FIXED
    subprocess seam rather than introducing an actor abstraction -- §3.2 declined actor
    selection, and a test-only seam would put that interface back through the suite's door."""
    import json

    from science_tool.autonomy import harness as harness_module

    real = harness_module._run_actor

    def _shift_the_timestamp(project_root: Path, *, report_path: Path, **kwargs):
        completed = real(project_root, report_path=report_path, **kwargs)
        payload = json.loads(report_path.read_text(encoding="utf-8"))
        payload["generated_at"] = "2099-01-01T00:00:00.000000+00:00"
        report_path.write_text(json.dumps(payload), encoding="utf-8")
        return completed

    monkeypatch.setattr(harness_module, "_run_actor", _shift_the_timestamp)

    outcome = run_supervised_audit(supervised_project, started=STARTED, short_id="a1b2")

    assert outcome.ingestion is None
    assert outcome.ingestion_refusal is not None


def test_an_actor_exit_two_still_completes(
    supervised_project: Path, monkeypatch: pytest.MonkeyPatch
):
    """`science health` writes a complete report and THEN exits 2 for an invalid acceptance
    configuration (design §4.2)."""
    (supervised_project / "science.yaml").write_text(
        "name: harness-fixture\nknowledge_profiles:\n  local: local\n"
        "health:\n  accepted_validation: scalar\n",
        encoding="utf-8",
    )
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "-C", str(supervised_project),
         "commit", "-aqm", "bad acceptance"],
        capture_output=True, check=True,
    )

    outcome = run_supervised_audit(supervised_project, started=STARTED, short_id="a1b2")

    assert outcome.actor_exit_code == 2
    assert outcome.disposition is RunDisposition.CLEAN
```

If `test_an_actor_exit_two_still_completes` does not observe exit 2, read
`report_has_invalid_acceptance_configuration` in `graph/health_cli.py` and produce the
configuration it actually rejects. Do not weaken the assertion to `in (0, 2)` — a row that
cannot distinguish the two certifies nothing.

- [x] **Step 4: Certify rows 15–21 (the revision-2 rows)**

| # | Mutation | Test node |
|---|---|---|
| 15 | Wrap `assert_repository_is_at` in the restore | `test_autonomy_start_restore.py::test_a_dirty_input_tree_is_refused_byte_for_byte_unchanged` |
| 16 | Call `subprocess.run(["git", ...])` directly in `_settle` | add `test_no_planted_vector_executes_through_the_supervised_loop` (below) |
| 17 | Drop `--no-gpg-sign` from `commit_tree` | `test_autonomy_git_writes.py::test_no_planted_vector_executes_through_the_write_primitives` |
| 18 | `_settle` commits on the record-less path | add `test_a_recordless_outcome_commits_nothing` (below) |
| 19 | `_settle` passes `--allow-empty` and skips the status check | add `test_settling_a_clean_tree_creates_no_commit` (below) |
| 20 | `ingestion_authority` passes `strict_identity=False` | `test_findings_ingestion_authority.py::test_it_loads_sources_without_relaxing_identity` |
| 21 | Exit 0 on an ingestion refusal | `test_autonomy_harness.py::test_the_command_exits_four_when_ingestion_refuses` |

**Rows 18 and 19 look like one row and are not.** Row 18 removes the `record_written` guard;
row 19 removes the *status* guard and adds `--allow-empty`. The record-less test kills 18 and
cannot kill 19: on that path control reaches `if not record_written: restore; return None` and
returns before any commit call, so the mutation's code never executes and
`test_a_recordless_outcome_commits_nothing` stays green. Row 19's condition is the other one —
`record_written=True` over a *clean* tree — and the full loop never produces it, because
`finish_run` always leaves the record file on disk. It has to be induced by calling `_settle`
directly.

**Row 16's mutation lives in `_settle`**, which the primitives test never calls. Proving the
write primitives are hardened does not prove the loop uses them: a direct
`subprocess.run(["git", ...])` in `_settle` bypasses every defence while
`test_no_planted_vector_executes_through_the_write_primitives` stays green. The kill needs the
whole loop run over a hostile repository, which means the `supervised_project` fixture — so the
test belongs in `test_autonomy_harness.py`, requesting Task 1's `plant_attacks` fixture rather
than re-inlining the vectors.

Add rows 16, 18 and 19's tests to `test_autonomy_harness.py`:

```python
def test_a_recordless_outcome_commits_nothing(
    supervised_project: Path, monkeypatch: pytest.MonkeyPatch
):
    """Design §4.5: `finish_run` returns `unwired` with `record=None` on five paths. A run
    that produced no attestation must not have derived state committed on its behalf."""
    from science_model.autonomous_runs import RunDisposition as D

    from science_tool.autonomy import harness as harness_module
    from science_tool.autonomy.lifecycle import RunOutcome

    monkeypatch.setattr(
        harness_module, "finish_run",
        lambda *a, **k: RunOutcome(disposition=D.UNWIRED, record=None, reason="forced"),
    )
    head_before = _git(supervised_project, "rev-parse", "HEAD")

    outcome = run_supervised_audit(supervised_project, started=STARTED, short_id="a1b2")

    assert outcome.record_written is False
    assert outcome.post_verdict_commit is None
    assert _git(supervised_project, "rev-parse", "HEAD") == head_before
    assert worktree_status(supervised_project) == ""


def test_settling_a_clean_tree_creates_no_commit(supervised_project: Path):
    """Row 19: the status check is the only thing standing between `_settle` and an empty
    commit, and only the `record_written=True` branch reaches the commit call at all.

    Called directly, because the loop cannot produce this state: `finish_run` writes the record
    file, so every run that sets `record_written` arrives here with a dirty tree. Asserting on
    the happy path would certify a guard whose condition was never false.
    """
    from science_tool.autonomy.harness import _settle

    assert worktree_status(supervised_project) == ""
    head_before = _git(supervised_project, "rev-parse", "HEAD")

    assert _settle(
        supervised_project, record_written=True, run_id="run:2026-08-02-health-audit-a1b2"
    ) is None
    assert _git(supervised_project, "rev-parse", "HEAD") == head_before


def test_no_planted_vector_executes_through_the_supervised_loop(
    supervised_project: Path, plant_attacks
):
    """Row 16: the whole loop over a hostile repository.

    `.git/config`, `.git/hooks/` and `$GIT_DIR/info/attributes` all belong to the ACTOR, so
    every git invocation the supervisor makes AFTER the actor runs is executing against a
    configuration the actor wrote. `test_no_planted_vector_executes_through_the_write_primitives`
    proves the primitives are hardened; it says nothing about whether `_settle` calls them.

    The `plant_attacks` fixture is shared with that test rather than re-inlined -- its workshop
    is a sibling of the repository precisely so `start_run`'s clean-tree assertion still passes
    (Task 1, Step 5).
    """
    sentinels = plant_attacks(supervised_project)

    outcome = run_supervised_audit(supervised_project, started=STARTED, short_id="a1b2")

    assert outcome.disposition is RunDisposition.CLEAN
    fired = sorted(path.name for path in sentinels.iterdir())
    assert fired == [], f"a hostile git configuration executed during the run: {fired}"
```

If `test_no_planted_vector_executes_through_the_supervised_loop` errors rather than failing
when row 16 is applied, that is still a kill — a raw `subprocess.run(["git", ...])` in `_settle`
inherits `[commit] gpgsign = true` with a `gpg.program` that exits 1, so the commit fails before
any sentinel is written. Record the row as certified on either signal, but read the failure
output to confirm it is that one and not an unrelated fixture error.

- [x] **Step 5: Certify rows 22–29 (the revision-3 and -4 rows)**

| # | Mutation | Test node |
|---|---|---|
| 22 | `_run_actor` uses `["science", "health", ...]` | `test_autonomy_harness.py::test_the_actor_runs_the_supervisors_own_toolkit` |
| 23 | Drop `-P` **and** pass `cwd=project_root` | `test_autonomy_harness.py::test_the_actor_runs_the_supervisors_own_toolkit` |
| 24 | Swallow a `_settle` failure instead of raising | add `test_a_settlement_failure_raises` (below) |
| 25 | Take `ended` from the loaded report | add `test_the_record_ended_is_the_supervisors_clock` (below) |
| 26 | Remove the `_step` wrapper from `current_branch` | add `test_a_raw_git_failure_is_normalized` (below) |
| 27 | Catch only `ValueError` around ingestion | add `test_an_unreadable_report_is_a_refusal_not_an_abort` (below) |
| 28 | Return exit 0 for a quarantined outcome | `test_autonomy_harness.py::test_the_command_maps_each_disposition_to_its_exit_code[quarantined-1]` |
| 29 | Return exit 0 for an unwired outcome | `test_autonomy_harness.py::test_the_command_maps_each_disposition_to_its_exit_code[unwired-2]` |

**Row 23 is one mutation with two halves, and that is deliberate.** Measured under Python 3.14:
`python -m` puts `''` on `sys.path`, and `''` resolves to the *cwd* — which the harness sets to
a neutral temporary directory. So dropping `-P` alone changes nothing observable, and setting
`cwd=project_root` alone is covered by `-P`. Each measure suffices independently; only removing
both reaches the planted package. Splitting this into two rows would put two mutations in the
ledger that cannot fail (design §3.2).

Row 22 needs a `science` on `PATH` that is not the supervisor's. The test plants one in a
directory prepended to `PATH` via `monkeypatch.setenv`; with the real argv it is never
consulted, and with the mutation it runs and the report is never written. Add that setup to
`test_the_actor_runs_the_supervisors_own_toolkit` before certifying, so one test kills 22 and
23 both.

Add the four new tests to `test_autonomy_harness.py`:

```python
def test_a_settlement_failure_raises(supervised_project: Path, monkeypatch: pytest.MonkeyPatch):
    """Design §8.4: the happy path cannot distinguish raising from swallowing, because nothing
    raises. The condition has to be induced."""
    from science_tool.autonomy import harness as harness_module
    from science_tool.autonomy.git import GitError

    def _explode(*args, **kwargs):
        raise GitError("settlement blew up")

    monkeypatch.setattr(harness_module, "_settle", _explode)

    with pytest.raises(HarnessError, match="settled"):
        run_supervised_audit(supervised_project, started=STARTED, short_id="a1b2")


def test_a_raw_git_failure_is_normalized(
    supervised_project: Path, monkeypatch: pytest.MonkeyPatch
):
    """Every orchestration failure raises `HarnessError`, including one from a helper that
    raises on its own -- the CLI catches nothing else."""
    from science_tool.autonomy import harness as harness_module
    from science_tool.autonomy.git import GitError

    def _explode(*args, **kwargs):
        raise GitError("cannot read HEAD")

    monkeypatch.setattr(harness_module, "current_branch", _explode)

    with pytest.raises(HarnessError):
        run_supervised_audit(supervised_project, started=STARTED, short_id="a1b2")


def test_an_unreadable_report_is_a_refusal_not_an_abort(
    supervised_project: Path, monkeypatch: pytest.MonkeyPatch
):
    """`load_report` reaches the filesystem, so an `OSError` there is a refusal to INGEST --
    letting it escape would abandon the tree before step 9 and leave the operator on
    `auto/<slug>` with uncommitted supervisor output."""
    from science_tool.autonomy import harness as harness_module

    def _unreadable(*args, **kwargs):
        raise OSError("report vanished")

    monkeypatch.setattr(harness_module, "load_report", _unreadable)
    start_branch = current_branch(supervised_project)

    outcome = run_supervised_audit(supervised_project, started=STARTED, short_id="a1b2")

    assert outcome.ingestion is None
    assert outcome.ingestion_refusal is not None
    assert current_branch(supervised_project) == start_branch
    assert worktree_status(supervised_project) == ""


def test_the_record_ended_is_the_supervisors_clock(supervised_project: Path):
    """Design §3.4.2: every wall instant comes from the supervisor, never from the actor."""
    from science_tool.graph.autonomous_runs import load_run_records

    before = datetime.now(UTC)
    outcome = run_supervised_audit(supervised_project, started=STARTED, short_id="a1b2")
    after = datetime.now(UTC)

    record = {r.id: r for r in load_run_records(supervised_project)}[outcome.run_id]

    assert before <= record.ended <= after
```

`load_run_records` lives in `graph/autonomous_runs.py:77`, not in `record_writer.py` — the
writer and the reader are deliberately in different modules.

- [x] **Step 6: Run the whole 2b test set**

Run: `(cd science && uv run --frozen pytest tests/test_autonomy_harness.py tests/test_autonomy_git_writes.py tests/test_autonomy_start_restore.py tests/test_health_attested_provenance.py tests/test_findings_ingestion_authority.py -q)`
Expected: all pass.

- [x] **Step 7: Commit the ledger**

```bash
git add docs/plans/2026-08-02-spec-2b-mutation-ledger.md science/tests/
git commit -m "test(autonomy): certify spec 2b's mutation rows"
```

---

## Task 8: Adjacent 2a closure

Design §10. Independent of Tasks 1–7; may run at any point.

**Files:**
- Modify: `docs/plans/2026-07-30-agent-evidence-broker-design.md:16-19`
- Modify: `src/science_tool/autonomy/lifecycle.py:309`
- Test: `science/tests/test_autonomy_lifecycle.py` (extend)

- [x] **Step 1: Refresh the 2a status rows**

In `docs/plans/2026-07-30-agent-evidence-broker-design.md`, change the plan-4c row from
"**implemented on `feat/evidence-broker-boundary` and settled through revision 38; not
merged**" to "**merged** at `1c11c922`", and change §0's Spec 2a row from "this document —
plans 1–3 merged, 4a/4b designed at revision 17" to "this document — **all seven plans
merged**; 4c at `1c11c922`". Add a Spec 2b row pointing at the harness design.

- [x] **Step 2: Write the failing test**

Append to `science/tests/test_autonomy_lifecycle.py`:

```python
def test_an_inline_input_counts_lines_the_way_the_checker_does(project: Path, tmp_path: Path):
    """`InlineInput.lines` and `correspondence._line_count` both feed the same `Full(...)`
    ceiling. `splitlines()` splits on CR, FF, LS, PS and NEL; the checker counts `\\n` only, so
    a bare CR would give an inline input a HIGHER ceiling than the same bytes served through
    `read` -- an agent could cite a line the LF convention says does not exist."""
    from science_tool.autonomy.lifecycle import _read_inline_manifest
    from science_tool.evidence_broker.correspondence import _line_count

    payload = b"alpha\rbeta\ngamma\n"
    target = project / "instrument.md"
    target.write_bytes(payload)

    manifest = _read_inline_manifest((Path("instrument.md"),), project_root=project)

    assert manifest[0].lines == _line_count(payload)
```

- [x] **Step 3: Run it to verify it fails**

Run: `(cd science && uv run --frozen pytest tests/test_autonomy_lifecycle.py::test_an_inline_input_counts_lines_the_way_the_checker_does -q)`
Expected: FAIL — `3 != 2`.

- [x] **Step 4: Use one line-counting rule**

In `src/science_tool/autonomy/lifecycle.py`, replace `lines=len(payload.splitlines())` at
line 309 with `lines=_line_count(payload)`, importing the checker's own function:

```python
from science_tool.evidence_broker.correspondence import _line_count
```

If that import creates a cycle, move `_line_count` to `science_model/evidence_broker.py` beside
the `InlineInput` model it bounds and import it from there in both places. Do not duplicate the
arithmetic — two spellings of one rule is the defect being fixed.

- [x] **Step 5: Run it and its neighbours**

Run: `(cd science && uv run --frozen pytest tests/test_autonomy_lifecycle.py tests/test_evidence_broker_correspondence.py -q)`
Expected: all pass. If no `test_evidence_broker_correspondence.py` exists, find the
correspondence tests with `ls science/tests | grep correspondence` and run those.

- [x] **Step 6: Commit**

```bash
(cd science && uv run ruff check && uv run pyright)
git add science/src/science_tool/autonomy/lifecycle.py science/tests/test_autonomy_lifecycle.py docs/plans/2026-07-30-agent-evidence-broker-design.md
git commit -m "fix(evidence-broker): count an inline input's lines the way the checker does"
```

---

## Self-review notes for the implementer

**Three places where a test can pass for the wrong reason.** Each is called out at the step, but
they are the plan's highest-risk points:

1. **Task 2's fixture.** Against `test_autonomy_lifecycle.py`'s `project` fixture — which
   commits its graph — the broken and the fixed `start_run` both leave a clean tree. Use
   `ungraphed_project`.
2. **Task 1's hostile-configuration test.** An untracked `.gitattributes` makes `start_run`
   refuse before the vector is reached. Use `$GIT_DIR/info/attributes`.
3. **Row 12's fake actor.** Real `health` echoes the dictated timestamp, so against it
   "dictate" and "read back" are indistinguishable. Patch the subprocess seam.

**One convention with no guard.** "No `Science-Run` trailer on the post-verdict commit" is a
convention, not a certifiable invariant: `verify_marks` reads only `base..head`, and
`check_autonomous_runs` accepts any marked commit whose run id has a record. It has a test
(`test_the_post_verdict_commit_is_the_supervisors_and_unmarked`) but **no mutation row**, and
claiming one would be false.

**A mutation must be reachable by the test that names it.** Five rows named a mutation their
test never induced — the happy path cannot notice a branch check that only fires when the actor
wanders, and no test that returns before `_settle`'s commit call can execute a mutation on it.
Rows 16 and 19 were each caught *after* a first repair had already moved them to a nearer test,
which is the part to carry: a row matched to the right *subject* is not thereby a row whose
inputs put control on the mutated line. Before certifying any row, name the input that reaches
it. The rule: **name the test that induces the condition, not the test that would notice it if
the condition arose.**

**If a mutation leaves every test green,** that is a finding, not a step to skip. Record it in
the ledger with what you tried, and report it — either the guard is not guarded or the row is
wrong, and both matter. Row 23 is the worked example: `-P` and the neutral cwd are independent
defences, so each alone is unkillable, and the honest response was one row removing both rather
than two rows that cannot fail.

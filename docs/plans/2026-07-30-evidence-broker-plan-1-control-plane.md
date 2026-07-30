# Evidence Broker Plan 1 — Control Plane and Canonical Git Invocation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make an autonomous run addressable from its id, and make `git grep` / `git log` produce byte-identical output regardless of repository configuration or parent locale.

**Architecture:** Two independent modules under `science/src/science_tool/autonomy/`, neither of which mentions evidence. `control_plane.py` is a pure path calculator: a project-scoped, digest-keyed root under which a run id resolves to exactly one directory. `git.py` gains a probed hardening set for two subcommands it has never run, plus an environment pin, so that a later replay comparing two hashes of the same query is comparing the same query.

**Tech Stack:** Python 3.12+, Pydantic v2 (already present; this plan adds no models), `click`, `pytest`. No new dependencies.

## Provenance

Implements Spec 2a of the autonomous-audit program:
[`2026-07-30-agent-evidence-broker-design.md`](2026-07-30-agent-evidence-broker-design.md)
revision 8 — §0 (program placement and ordering), §3.2.1 (canonical invocation),
§3.4.2 (control plane), §7 (the `control_plane.py` and canonical-invocation test
bullets).

## Scope: what this plan does NOT include, and why

**The `--broker-spec` and `--session` flag pairs move to plan 2.** The design specifies
them as mutually exclusive with `--baseline-out` and `--baseline` respectively (§3.4.2),
and it is tempting to land the mutual exclusion here since `run_dir` is what they resolve
against. They are deferred because `--broker-spec` carries an `EvidenceSessionSpec`, whose
fields are `SurfacePolicy`, `InstrumentIdentity` and the inline manifest — model types plan
2 defines. A flag landed here would carry no value, which is precisely the defect the
design's own revision 4 was corrected for ("`autonomy start --broker` could not have built
its baseline"). `--session` on `finish` is deferred for a dependent reason: it resolves a
baseline that only a `--broker-spec` run ever places in the control plane, so it would have
nothing to find.

Plan 1's deliverable is therefore two modules with complete tests and no production caller.
That is the intended shape: §0 argues `control_plane.py` is infrastructure 2b needs whether
or not evidence is ever brokered, and this plan is what makes that true rather than
asserted.

**Which §7 bullets this leaves for plan 2, named so they are deferred rather than lost:**

| §7 requirement | Why it cannot land here |
|---|---|
| `--broker-spec` and `--baseline-out` together are refused | The flag carries `EvidenceSessionSpec` |
| `--session` and `--baseline` on `finish` are refused | Resolves a control-plane baseline only `--broker-spec` places |
| A brokered run whose baseline is elsewhere is refused rather than searched for | "Brokered" is a property of `RunBaseline.evidence`, added in plan 2 |
| A handle that parses but whose baseline carries a different `run_id` is refused after loading | Needs a baseline in the control plane to load |
| `grep.patternType=fixed` and `basic` produce the same **served bytes**; `color.ui=always` does not colour; `log.showSignature=true` does not change the served log | These pin *per-op argv*, which `evidence_broker/serve.py` builds. Plan 1 owns the module-level half — the environment and the `-c` hardening — because that is the half `run_git` can be held to on its own |

Plan 1 covers the remaining §7 control-plane bullets in full: `run_dir` purity, the
same-slug collision, the fork case, the hostile `science.yaml` name, the in-project
control-plane root, and handle refusal before any path join.

## Design deviations recorded here

**One, and it is a narrowing.** §3.4.1 says the `--session` handle is "parsed as a
*generated run id* — the same constructive check `AutonomousRunRecord._validate_identity`
performs, rebuilding `<date>-<agent>-<short-id>` and comparing". That check is constructive
*because the record names its own agent* (`autonomous_runs.py:195-228`, "the agent slug
contains hyphens, so `<date>-<agent>-<short>` has more than one reading"). A bare handle
names no agent, so nothing can be rebuilt from it and compared.

What a bare handle can be checked for is structure — a real ISO date, then a kebab-case
remainder with no path separator, no `..`, no NUL — which is sufficient for the property the
check exists to provide: the handle cannot escape the control plane when joined to a path.
The *identity* guarantee comes from the second half of the same design bullet, which is
unchanged and is what actually carries it: after loading, the baseline's own `run_id` must
equal the handle. Task 3 implements both halves and Task 3's tests assert both.

This plan implements the narrowed rule. Amending §3.4.1's wording is a one-line design
follow-up, not a blocker.

## Global Constraints

- Work in the `feat/review-plans` worktree at `.worktrees/review-plans`, on branch
  `feat/review-plans`. Verify with `git branch --show-current` before the first commit.
- All CLI/package work runs from `science/`. There is **no root `pyproject.toml`** —
  `cd science` first, always. Model work would run from `science/model/`; this plan
  touches no model code.
- Tests: `cd science && uv run --frozen pytest <paths>`. Never run the full suite in a
  subagent — it exceeds the 120s default timeout. Scoped runs only.
- Lint and types, from `science/`: `uv run ruff check` and `uv run pyright`. Pyright is
  configured once by the repo-root `pyrightconfig.json`; test directories are not
  type-checked.
- Conventional commits. **No AI-attribution trailer or footer** on any commit.
- Composition over inheritance; explicit over defensive; fail early rather than fall back
  silently. No "legacy"/"compatibility" layers. No `Unified` prefix.
- Use `~/d/` or repo-relative paths in any doc or comment text, never `/home/keith/` or
  `/mnt/ssd/Dropbox/`.
- `git.py`'s standing rule, which Task 2 must honour verbatim: **"Only what was shown to
  execute is neutralized. Blanking the rest would assert a defense against behaviour this
  code has been shown not to have."** Task 1 exists to establish what "shown" means for
  `grep` and `log`.

## File Structure

| File | Responsibility |
|---|---|
| `science/src/science_tool/autonomy/control_plane.py` (**create**) | Resolve the control-plane root, the project key, and a run's directory. Pure path calculation plus containment; creates nothing. |
| `science/src/science_tool/autonomy/git.py` (**modify**) | Add the probed hardening for `grep`/`log` and pin the child environment. Remains the single place autonomy's git argv is built. |
| `science/tests/test_autonomy_control_plane.py` (**create**) | Every §7 control-plane bullet. |
| `science/tests/test_autonomy_git_canonical.py` (**create**) | Locale independence, and the probe's findings as assertions. |
| `docs/plans/2026-07-30-agent-evidence-broker-design.md` (**modify**) | §3.2.1 gains the probe's recorded results. |

---

### Task 1: Probe `git grep` and `git log`

**This task is discovery, not TDD.** The design refuses to guess what the probe will find
("`--textconv` is off by default; the probe establishes whether anything reaches a driver
anyway rather than assuming it does not"), and §7 requires the canonical-invocation tests to
be *written from* the probe. There is therefore no test to write first: Task 2's assertions
do not exist until this task produces its findings. Do not skip ahead and invent them.

**Files:**
- Scratch only: `$SCRATCH/probe_git_ops.py` (do **not** commit the script)
- Modify: `docs/plans/2026-07-30-agent-evidence-broker-design.md` §3.2.1

**Interfaces:**
- Consumes: nothing.
- Produces: a recorded findings table in §3.2.1 naming, for each probed config key, one of
  `EXECUTES`, `RENDERS` (changes output but spawns nothing), or `INERT`. Task 2 turns
  `EXECUTES` rows into `-c` overrides and `RENDERS` rows into either argv pins or
  environment pins.

- [ ] **Step 1: Write the probe script**

Write to your scratchpad directory (not the repo):

```python
#!/usr/bin/env python3
"""Which git config keys execute a program, or change output, under `grep` and `log`?

Mirrors the analysis git.py already records for `status` / `show` / `diff`. For each
candidate: build a scratch repo, set the key, run EXACTLY the argv the broker will use,
and report whether a marker file appeared (EXECUTES) or the bytes differed (RENDERS).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

GREP_ARGV = ("grep", "-n", "-e", "alpha", "HEAD")
LOG_ARGV = ("log", "--pretty=format:%H %aI", "HEAD", "--", "sample.txt")


def build_repo(root: Path, marker: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    run(root, "init", "-q")
    run(root, "config", "user.email", "probe@example.invalid")
    run(root, "config", "user.name", "Probe")
    (root / "sample.txt").write_text("alpha beta\ngamma delta\n", encoding="utf-8")
    (root / "unicode.txt").write_text("éalpha übergamma\n", encoding="utf-8")
    run(root, "add", "-A")
    run(root, "commit", "-q", "-m", "seed")
    # A program that proves execution by creating a file, and is silent otherwise.
    spawn = root / "spawn.sh"
    spawn.write_text(f"#!/bin/sh\ntouch {marker}\ncat\n", encoding="utf-8")
    spawn.chmod(0o755)


def run(root: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", "--no-replace-objects", "-C", str(root), *args], capture_output=True
    )


def probe(key: str, value: str, argv: tuple[str, ...], *, attribute: str | None = None) -> str:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "repo"
        marker = Path(tmp) / "EXECUTED"
        build_repo(root, marker)
        baseline = run(root, *argv).stdout

        run(root, "config", key, value)
        if attribute is not None:
            (root / ".gitattributes").write_text(attribute, encoding="utf-8")
            run(root, "add", "-A")
            run(root, "commit", "-q", "-m", "attr")
            baseline = run(root, "-c", f"{key}=", *argv).stdout

        after = run(root, *argv).stdout
        if marker.exists():
            return "EXECUTES"
        return "RENDERS" if after != baseline else "INERT"


CANDIDATES: list[tuple[str, str, tuple[str, ...], str | None]] = [
    # grep -- rendering and meaning
    ("grep.patternType", "fixed", GREP_ARGV, None),
    ("grep.extendedRegexp", "true", GREP_ARGV, None),
    ("grep.lineNumber", "false", GREP_ARGV, None),
    ("grep.fullName", "true", GREP_ARGV, None),
    ("grep.column", "true", GREP_ARGV, None),
    ("grep.threads", "1", GREP_ARGV, None),
    ("color.grep", "always", GREP_ARGV, None),
    ("color.ui", "always", GREP_ARGV, None),
    ("core.quotePath", "true", GREP_ARGV, None),
    # grep -- execution
    ("diff.probe.textconv", "./spawn.sh", GREP_ARGV, "*.txt diff=probe\n"),
    ("core.pager", "./spawn.sh", GREP_ARGV, None),
    ("pager.grep", "./spawn.sh", GREP_ARGV, None),
    # log -- rendering
    ("log.date", "rfc", LOG_ARGV, None),
    ("log.decorate", "full", LOG_ARGV, None),
    ("log.abbrevCommit", "true", LOG_ARGV, None),
    ("log.mailmap", "true", LOG_ARGV, None),
    ("format.pretty", "oneline", LOG_ARGV, None),
    # log -- execution
    ("log.showSignature", "true", LOG_ARGV, None),
    ("gpg.program", "./spawn.sh", LOG_ARGV, None),
    ("core.pager", "./spawn.sh", LOG_ARGV, None),
]


def main() -> int:
    version = subprocess.run(["git", "--version"], capture_output=True, text=True).stdout.strip()
    print(f"# {version}\n")
    print("| key | value | op | verdict |")
    print("|---|---|---|---|")
    for key, value, argv, attribute in CANDIDATES:
        verdict = probe(key, value, argv, attribute=attribute)
        print(f"| `{key}` | `{value}` | `{argv[0]}` | **{verdict}** |")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run the probe and capture its output**

Run: `python3 $SCRATCH/probe_git_ops.py | tee $SCRATCH/probe-results.md`

Expected: a table, one row per candidate. Every row must read `EXECUTES`, `RENDERS`, or
`INERT` — no crashes, no blank verdicts. If `log.showSignature=true` reports `INERT`, that
is a red flag that the repo has no signed commits to verify: re-run that row against a
commit created with `-S` if a signing key is available, and if none is, record the row as
`UNDETERMINED` rather than `INERT`. An untested key must not be recorded as safe.

- [ ] **Step 3: Record the findings in the design**

Add a subsection to §3.2.1 of
`docs/plans/2026-07-30-agent-evidence-broker-design.md`, immediately after the pinning
table, in the same voice as `git.py`'s own probe record:

```markdown
**What was probed, and what actually executes.** Against git <version> in a scratch
repository, under exactly the argv the broker builds:

<the generated table>

Keys that EXECUTE are neutralized by `-c` in `_HARDENING`. Keys that only RENDER are
pinned in argv, or by the environment where argv cannot reach them. Keys recorded
INERT are left alone, per this module's standing rule: blanking them would assert a
defense against behaviour this code has been shown not to have.
```

Replace `<version>` with the exact version the probe printed. Do not paraphrase the verdicts.

- [ ] **Step 4: Commit the findings**

```bash
cd ~/d/science/.worktrees/review-plans
git add docs/plans/2026-07-30-agent-evidence-broker-design.md
git commit -m "docs: record what git grep and log execute under probe"
```

---

### Task 2: Canonical invocation for `grep` and `log`

**Files:**
- Modify: `science/src/science_tool/autonomy/git.py` (module docstring; `_run`; `_HARDENING`)
- Test: `science/tests/test_autonomy_git_canonical.py` (create)

**Interfaces:**
- Consumes: Task 1's findings table.
- Produces: `run_git(repo_root: Path, *args: str) -> subprocess.CompletedProcess[bytes]`
  — unchanged signature, now locale-pinned and hardened for `grep`/`log`. Plan 2's
  `evidence_broker/serve.py` calls it and builds the per-op argv itself.

- [ ] **Step 1: Write the failing locale test**

Create `science/tests/test_autonomy_git_canonical.py`:

```python
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from science_tool.autonomy.git import run_git


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    for args in (
        ("init", "-q"),
        ("config", "user.email", "probe@example.invalid"),
        ("config", "user.name", "Probe"),
    ):
        subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)
    # Non-ASCII content: `[[:alpha:]]` classifies these differently under C and UTF-8.
    (root / "sample.txt").write_text("éalpha\nplain\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(root), "commit", "-q", "-m", "seed"], check=True, capture_output=True
    )
    return root


def test_grep_output_does_not_depend_on_the_parent_locale(tmp_path: Path, monkeypatch):
    """A POSIX class means different things under C and under UTF-8, so an unpinned
    locale makes two honest replays of one query disagree -- and correspondence refuses
    on disagreement."""
    root = _repo(tmp_path)
    argv = ("grep", "-n", "-e", "[[:alpha:]]alpha", "HEAD")

    monkeypatch.setenv("LC_ALL", "C")
    under_c = run_git(root, *argv).stdout

    monkeypatch.setenv("LC_ALL", "en_US.UTF-8")
    monkeypatch.setenv("LANG", "en_US.UTF-8")
    under_utf8 = run_git(root, *argv).stdout

    assert under_c == under_utf8


def test_a_missing_path_is_reported_in_a_pinned_locale(tmp_path: Path, monkeypatch):
    """The defined-miss classifier reads git's stderr. Localized text would not match,
    and an ordinary absent path would halt the run instead of answering."""
    root = _repo(tmp_path)
    monkeypatch.setenv("LC_ALL", "fr_FR.UTF-8")
    monkeypatch.setenv("LANGUAGE", "fr")

    completed = run_git(root, "show", "HEAD:no-such-file.txt")

    assert completed.returncode != 0
    assert b"exists on disk" in completed.stderr or b"does not exist" in completed.stderr
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd science && uv run --frozen pytest tests/test_autonomy_git_canonical.py -v`

Expected: `test_grep_output_does_not_depend_on_the_parent_locale` FAILS — the two byte
strings differ, because `run_git` passes no `env` and git inherits the parent locale.
`test_a_missing_path_is_reported_in_a_pinned_locale` FAILS on a system with French
locale data and passes vacuously on one without; treat a pass here as inconclusive until
the implementation lands, and rely on the first test as the gate.

- [ ] **Step 3: Pin the child environment**

In `science/src/science_tool/autonomy/git.py`, add the constant beside `_HARDENING`:

```python
#: The environment every autonomy git call runs under. `LC_ALL` and `LANG` are pinned
#: because argv is not the whole invocation: a POSIX class such as `[[:alpha:]]` matches a
#: different character set under `C` than under a UTF-8 locale, so two honest replays of one
#: pattern against one commit would disagree -- and §5.3 refuses on disagreement. The same
#: pin fixes git's DIAGNOSTIC text, which the broker's defined-miss classifier reads: under a
#: translated locale the miss messages would not match and an absent path would halt the run.
#:
#: `TZ` is deliberately NOT pinned: `%aI` carries its own offset, so the rendered log does not
#: depend on the reader's zone. Pinning it would assert a defense against behaviour the chosen
#: format has been shown not to have.
_ENVIRONMENT: dict[str, str] = {"LC_ALL": "C", "LANG": "C"}
```

Then thread it through `_run`:

```python
def _run(
    repo_root: Path, overrides: tuple[str, ...], args: tuple[str, ...]
) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(
            _argv(repo_root, overrides, args),
            capture_output=True,
            env={**os.environ, **_ENVIRONMENT},
        )
    except (OSError, ValueError) as exc:
        raise GitError(f"could not execute git {' '.join(args)} in {repo_root}: {exc}") from exc
```

Add `import os` to the imports.

Inherit-and-override, not a bare `env=_ENVIRONMENT`: git needs `PATH` to find its own
subprocesses and `HOME` to resolve `~`, and a hermetic environment would break the very
calls this module exists to make.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_autonomy_git_canonical.py -v`

Expected: PASS.

- [ ] **Step 5: Run the existing autonomy suite for regressions**

Run:

```bash
cd science && uv run --frozen pytest \
  tests/test_autonomy_extract.py tests/test_autonomy_toolkit.py \
  tests/test_autonomy_lifecycle.py tests/test_autonomy_marks.py \
  tests/test_autonomy_changes.py -q
```

Expected: PASS. Every existing caller goes through `_run`, so a broken environment pin
surfaces here rather than in plan 2.

- [ ] **Step 6: Add the probe's `EXECUTES` rows to the hardening**

For each key Task 1 recorded `EXECUTES`, add it to `_HARDENING` in the blanking spelling
(`key=`, or `key=/dev/null` where a blank value is not accepted — match what the probe
showed disarms it). **Add nothing for `RENDERS` or `INERT` rows.**

If Task 1 found no new `EXECUTES` key, change `_HARDENING` not at all and say so in the
commit message. An empty result is a finding.

Then extend the module docstring's probed-command list, which currently reads:

```
`rev-parse`, `status --porcelain`, `log`, `show <commit>:<path>`, `diff --raw`,
`diff --name-status`:
```

to name `grep` explicitly, and append the new verdicts to the bullet list below it in the
existing style (one line per key, `-- EXECUTES, under <op>.` or `-- do NOT fire.`, with the
reason). The docstring is the module's probe record; a key added to `_HARDENING` without a
line here is a key nobody can later justify.

- [ ] **Step 7: Write the failing neutralization test**

For each `EXECUTES` key, add a test to `tests/test_autonomy_git_canonical.py` in this
shape — substituting the real key and op:

```python
def test_a_configured_executing_key_does_not_fire_under_run_git(tmp_path: Path):
    """Reconstruct the attack the probe demonstrated, and assert the hardening disarms
    it. A guard nobody has watched fail is a guard nobody has tested."""
    root = _repo(tmp_path)
    marker = tmp_path / "EXECUTED"
    spawn = root / "spawn.sh"
    spawn.write_text(f"#!/bin/sh\ntouch {marker}\ncat\n", encoding="utf-8")
    spawn.chmod(0o755)
    subprocess.run(
        ["git", "-C", str(root), "config", "<the.key>", "./spawn.sh"],
        check=True, capture_output=True,
    )

    run_git(root, "<op>", "<args...>")

    assert not marker.exists()
```

And a companion asserting the attack still reproduces without the hardening, so the guard
is proven to be watching something rather than passing because the vector died:

```python
def test_the_executing_key_still_fires_without_the_hardening(tmp_path: Path):
    """The negative control. If this ever stops failing, the guard above proves nothing
    and the pair should be revisited -- not deleted."""
    root = _repo(tmp_path)
    marker = tmp_path / "EXECUTED"
    spawn = root / "spawn.sh"
    spawn.write_text(f"#!/bin/sh\ntouch {marker}\ncat\n", encoding="utf-8")
    spawn.chmod(0o755)
    subprocess.run(
        ["git", "-C", str(root), "config", "<the.key>", "./spawn.sh"],
        check=True, capture_output=True,
    )

    subprocess.run(["git", "-C", str(root), "<op>", "<args...>"], capture_output=True)

    assert marker.exists()
```

Write the negative control first and watch it pass before writing the guard test.

If Task 1 found no `EXECUTES` key, skip this step entirely and note it in the commit.

- [ ] **Step 8: Run the full canonical test module**

Run: `cd science && uv run --frozen pytest tests/test_autonomy_git_canonical.py -v`

Expected: PASS.

- [ ] **Step 9: Lint, type-check, and commit**

```bash
cd ~/d/science/.worktrees/review-plans/science
uv run ruff check
uv run pyright
cd ~/d/science/.worktrees/review-plans
git add science/src/science_tool/autonomy/git.py science/tests/test_autonomy_git_canonical.py
git commit -m "feat(autonomy): pin the git child environment and harden grep/log"
```

---

### Task 3: The control plane

**Files:**
- Create: `science/src/science_tool/autonomy/control_plane.py`
- Test: `science/tests/test_autonomy_control_plane.py`

**Interfaces:**
- Consumes: `reject_baseline_inside_project(path: Path, project_root: Path) -> None` from
  `science_tool.autonomy.baseline` (raises `BaselineError`); `RUN_ID_PREFIX` from
  `science_model.autonomous_runs`.
- Produces, for plan 2 and for 2b:

```python
CONTROL_PLANE_ENV = "SCIENCE_CONTROL_PLANE"

class ControlPlaneError(ValueError): ...

def control_plane_root(project_root: Path) -> Path
def project_key(project_root: Path) -> str
def run_slug(handle: str) -> str
def run_dir(project_root: Path, handle: str) -> Path
def project_metadata_path(project_root: Path) -> Path
```

`handle` accepts either spelling — `run:2026-07-30-lens-a3f1` or the bare slug — and
`run_slug` returns the bare form. Plan 2's `--session` passes what the operator typed.

- [ ] **Step 1: Write the failing tests**

Create `science/tests/test_autonomy_control_plane.py`:

```python
from __future__ import annotations

import re
from pathlib import Path

import pytest

from science_tool.autonomy.baseline import BaselineError
from science_tool.autonomy.control_plane import (
    CONTROL_PLANE_ENV,
    ControlPlaneError,
    control_plane_root,
    project_key,
    project_metadata_path,
    run_dir,
    run_slug,
)

HANDLE = "2026-07-30-review-plans-a3f1"


def _project(tmp_path: Path, name: str) -> Path:
    root = tmp_path / name
    (root / "doc").mkdir(parents=True)
    (root / "science.yaml").write_text(f"name: {name}\n", encoding="utf-8")
    return root


def test_run_dir_is_a_pure_function_of_project_root_and_handle(tmp_path, monkeypatch):
    monkeypatch.setenv(CONTROL_PLANE_ENV, str(tmp_path / "cp"))
    project = _project(tmp_path, "alpha")

    assert run_dir(project, HANDLE) == run_dir(project, HANDLE)
    assert not (tmp_path / "cp").exists(), "resolving a path must create nothing"


def test_two_projects_sharing_a_run_slug_get_different_directories(tmp_path, monkeypatch):
    """A run id is <date>-<agent>-<short-id>. Two projects running the same agent role on
    the same day with the same disambiguator produce the same slug; a single global root
    would let one project's session resolve the other's baseline."""
    monkeypatch.setenv(CONTROL_PLANE_ENV, str(tmp_path / "cp"))

    assert run_dir(_project(tmp_path, "alpha"), HANDLE) != run_dir(
        _project(tmp_path, "beta"), HANDLE
    )


def test_a_fork_does_not_resolve_its_parents_run(tmp_path, monkeypatch):
    """A fork inherits its parent's science.yaml name outright, and shares its base
    commit -- so a collision here would replay successfully and prove nothing."""
    monkeypatch.setenv(CONTROL_PLANE_ENV, str(tmp_path / "cp"))
    parent = _project(tmp_path, "alpha")
    fork = tmp_path / "fork-of-alpha"
    fork.mkdir()
    (fork / "science.yaml").write_text("name: alpha\n", encoding="utf-8")

    assert run_dir(parent, HANDLE) != run_dir(fork, HANDLE)


@pytest.mark.parametrize(
    "hostile",
    ["../../escape", "a/b/c", "x" * 4096, "..", "with\nnewline"],
)
def test_a_hostile_project_name_changes_no_path(tmp_path, monkeypatch, hostile):
    """ProjectConfig.name is an unconstrained str on a model with extra="allow". The
    digest is the whole directory name precisely so a name can never reach a path."""
    monkeypatch.setenv(CONTROL_PLANE_ENV, str(tmp_path / "cp"))
    project = _project(tmp_path, "alpha")
    before = run_dir(project, HANDLE)

    (project / "science.yaml").write_text(f"name: {hostile}\n", encoding="utf-8")

    assert run_dir(project, HANDLE) == before


def test_a_control_plane_root_inside_the_project_is_refused(tmp_path, monkeypatch):
    """An environment variable must not relocate the control plane into the tree the
    actor writes."""
    project = _project(tmp_path, "alpha")
    monkeypatch.setenv(CONTROL_PLANE_ENV, str(project / "state"))

    with pytest.raises(BaselineError):
        control_plane_root(project)


def test_the_control_plane_root_falls_back_to_the_xdg_state_dir(tmp_path, monkeypatch):
    monkeypatch.delenv(CONTROL_PLANE_ENV, raising=False)
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))

    assert control_plane_root(_project(tmp_path, "alpha")) == tmp_path / "state" / "science" / "runs"


@pytest.mark.parametrize(
    "hostile",
    [
        "../../other-project/2026-07-30-lens-a3f1",
        "..",
        "/absolute/2026-07-30-lens-a3f1",
        "2026-13-99-lens-a3f1",
        "not-a-run-id",
        "2026-07-30-lens-a3f1/../../escape",
        "2026-07-30-lens-a3f1\x00",
        "",
    ],
)
def test_a_hostile_handle_is_refused_before_any_join(tmp_path, monkeypatch, hostile):
    """The handle is actor-supplied and becomes a path component. Refuse it as a handle,
    not as a path -- a check applied after joining has already lost."""
    monkeypatch.setenv(CONTROL_PLANE_ENV, str(tmp_path / "cp"))

    with pytest.raises(ControlPlaneError):
        run_dir(_project(tmp_path, "alpha"), hostile)


def test_both_handle_spellings_resolve_to_one_directory(tmp_path, monkeypatch):
    monkeypatch.setenv(CONTROL_PLANE_ENV, str(tmp_path / "cp"))
    project = _project(tmp_path, "alpha")

    assert run_slug(f"run:{HANDLE}") == HANDLE
    assert run_dir(project, f"run:{HANDLE}") == run_dir(project, HANDLE)


def test_the_run_directory_sits_under_the_project_key(tmp_path, monkeypatch):
    monkeypatch.setenv(CONTROL_PLANE_ENV, str(tmp_path / "cp"))
    project = _project(tmp_path, "alpha")
    key = project_key(project)

    # NOT `key.islower()`: a digest that happened to be all digits has no cased character
    # and would report False, failing on one run in ~10^-13 and never reproducing.
    assert re.fullmatch(r"[0-9a-f]{16}", key)
    assert run_dir(project, HANDLE) == tmp_path / "cp" / key / HANDLE
    assert project_metadata_path(project) == tmp_path / "cp" / key / "project.json"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd science && uv run --frozen pytest tests/test_autonomy_control_plane.py -v`

Expected: every test FAILS at import — `ModuleNotFoundError: No module named
'science_tool.autonomy.control_plane'`.

- [ ] **Step 3: Write the module**

Create `science/src/science_tool/autonomy/control_plane.py`:

```python
"""The project-and-run-keyed canonical root a run id resolves against.

Today `science autonomy start --baseline-out` takes an arbitrary supervisor-chosen path,
so a run is addressable only by whoever placed it. A handle that names a baseline requires
that a run id DETERMINE where its baseline is, which is what this module supplies.

Nothing here mentions evidence. Addressing a run by its id is what a dispatch harness needs
to spawn N assignments and later resolve them, brokered or not (design §0).

THE KEY IS PROJECT-SCOPED. A run id is `<date>-<agent>-<short-id>`; two projects running the
same agent role on the same day with the same disambiguator produce the same slug, and a
fork inherits its parent's `science.yaml` name outright. A single global root would let one
project's session resolve another's baseline -- and between a fork and its parent, which
share a base commit, the replay would even succeed.

THE DIGEST IS THE WHOLE DIRECTORY NAME. `ProjectConfig.name` is an unconstrained `str` on a
model with `extra="allow"`, so a name containing `/` or `..`, or one long enough to blow a
path limit, would become a control-plane path that escapes or fails to create. The digest
already carries the whole identity; legibility costs nothing in a `project.json` beside the
run directories, where a human can read it and a path resolver never does.
"""

from __future__ import annotations

import hashlib
import os
import re
from datetime import date
from pathlib import Path

from science_model.autonomous_runs import RUN_ID_PREFIX

from science_tool.autonomy.baseline import reject_baseline_inside_project

#: Overrides the XDG state location. Still containment-checked: an environment variable must
#: not be able to relocate the control plane into the tree the actor writes.
CONTROL_PLANE_ENV = "SCIENCE_CONTROL_PLANE"

_DATE_LENGTH = len("YYYY-MM-DD")
#: The remainder after the date: `<agent>-<short-id>` jointly. NOT split into its two parts --
#: the agent slug contains hyphens, so the split has more than one reading, and a bare handle
#: names no agent to rebuild against. What this guarantees is what a path component needs:
#: no separator, no `..`, no NUL, no newline. IDENTITY is established by the caller, which
#: must compare the loaded baseline's own `run_id` against the handle (design §3.4.1).
_REMAINDER_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class ControlPlaneError(ValueError):
    """A handle or root that cannot address a run."""


def control_plane_root(project_root: Path) -> Path:
    """Where every project's run directories live.

    Raises `BaselineError` -- not `ControlPlaneError` -- when the resolved root is inside
    the project: it is the same containment failure `write_baseline` refuses, judged by the
    same function, and one failure should not have two names.
    """
    configured = os.environ.get(CONTROL_PLANE_ENV)
    if configured:
        root = Path(configured).expanduser()
    else:
        xdg_state_home = os.environ.get("XDG_STATE_HOME")
        base = Path(xdg_state_home).expanduser() if xdg_state_home else Path.home() / ".local" / "state"
        root = base / "science" / "runs"
    reject_baseline_inside_project(root, project_root)
    return root


def project_key(project_root: Path) -> str:
    """A digest of the resolved project root, and nothing else.

    Resolved, not as spelled: two worktrees of one project get two keys, which is correct --
    they are two trees at two commits -- but one project reached by two spellings must not.
    """
    resolved = str(project_root.resolve())
    return hashlib.sha256(resolved.encode("utf-8")).hexdigest()[:16]


def run_slug(handle: str) -> str:
    """The bare `<date>-<agent>-<short-id>` form, refusing anything that is not one.

    Validated BEFORE it is joined to anything. A check applied to the joined path has
    already lost: `run_dir(project, "../../elsewhere")` would have produced a real
    directory belonging to another project, and a containment check on the result would
    then be arguing with a path that should never have been built.
    """
    slug = handle.removeprefix(RUN_ID_PREFIX)
    if len(slug) <= _DATE_LENGTH or slug[_DATE_LENGTH] != "-":
        raise ControlPlaneError(f"run handle must begin with a YYYY-MM-DD date, got {handle!r}")
    try:
        date.fromisoformat(slug[:_DATE_LENGTH])
    except ValueError as exc:
        raise ControlPlaneError(
            f"run handle must begin with a real YYYY-MM-DD date, got {slug[:_DATE_LENGTH]!r}"
        ) from exc
    remainder = slug[_DATE_LENGTH + 1 :]
    if not _REMAINDER_RE.fullmatch(remainder):
        raise ControlPlaneError(
            f"run handle must be <date>-<agent>-<short-id> in lowercase kebab-case, got {handle!r}"
        )
    return slug


def project_metadata_path(project_root: Path) -> Path:
    """`project.json` -- the human label, as metadata beside the run directories."""
    return control_plane_root(project_root) / project_key(project_root) / "project.json"


def run_dir(project_root: Path, handle: str) -> Path:
    """One run's directory. Creates nothing: this is a path calculation.

    Layout, for the slices that fill it:
        <root>/<project-key>/project.json      the human label
        <root>/<project-key>/<run-slug>/       this directory
    """
    return control_plane_root(project_root) / project_key(project_root) / run_slug(handle)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_autonomy_control_plane.py -v`

Expected: PASS, all cases.

If `test_a_hostile_handle_is_refused_before_any_join` fails on the `"..."`-free case
`"not-a-run-id"`, check that `_REMAINDER_RE` is being reached: a handle shorter than the
date length must fail at the first branch, not the regex.

- [ ] **Step 5: Verify no directory is created as a side effect**

Run: `cd science && uv run --frozen pytest tests/test_autonomy_control_plane.py -q -k pure -v`

Expected: PASS. `run_dir` must remain a pure calculation — plan 2's `start` is what creates
directories, and a resolver that creates them would leave an empty directory for every
handle anyone ever typed, including refused ones.

- [ ] **Step 6: Lint, type-check, and commit**

```bash
cd ~/d/science/.worktrees/review-plans/science
uv run ruff check
uv run pyright
cd ~/d/science/.worktrees/review-plans
git add science/src/science_tool/autonomy/control_plane.py \
        science/tests/test_autonomy_control_plane.py
git commit -m "feat(autonomy): add the project-scoped control plane"
```

---

### Task 4: Verification and handoff

**Files:**
- Modify: `docs/plans/2026-07-30-evidence-broker-plan-1-control-plane.md` (this file)

- [ ] **Step 1: Run the whole affected surface**

```bash
cd ~/d/science/.worktrees/review-plans/science
uv run --frozen pytest \
  tests/test_autonomy_control_plane.py tests/test_autonomy_git_canonical.py \
  tests/test_autonomy_baseline.py tests/test_autonomy_extract.py \
  tests/test_autonomy_lifecycle.py tests/test_autonomy_lifecycle_cli.py \
  tests/test_autonomy_cli.py tests/test_autonomy_toolkit.py \
  tests/test_autonomy_marks.py tests/test_autonomy_changes.py \
  tests/test_autonomy_path_gate.py tests/test_autonomy_policy.py \
  tests/test_autonomy_record_writer.py tests/test_autonomy_validate_check.py -q
```

Expected: PASS.

- [ ] **Step 2: Run the full toolkit suite**

Run from the top level, not from a subagent, with a long timeout:

```bash
cd ~/d/science/.worktrees/review-plans/science && uv run --frozen pytest -q
```

Expected: PASS. Takes 2–3 minutes. `git.py` is on the path of every autonomy caller, so an
environment regression can surface far from the modules this plan touched.

- [ ] **Step 3: Confirm the branch and the absence of a production caller**

```bash
cd ~/d/science/.worktrees/review-plans
git branch --show-current    # expect: feat/review-plans
grep -rn "control_plane" science/src --include="*.py"
```

Expected: matches only inside `control_plane.py` itself. Plan 1 deliberately ships no
caller; a match elsewhere means scope crept in from plan 2.

- [ ] **Step 4: Append the implementation record**

Add an `## Implementation record` section to the end of this file: the commit SHAs per task,
the probe's git version and verdict counts, whether `_HARDENING` gained any key (and if not,
that the empty result was the finding), and the suite results. Record what was measured, not
what was expected.

- [ ] **Step 5: Commit the record**

```bash
git add docs/plans/2026-07-30-evidence-broker-plan-1-control-plane.md
git commit -m "docs: record the plan 1 control-plane implementation"
```

---

## Notes for the implementer

**`reject_baseline_inside_project` is reused deliberately, and its name is now slightly
wrong.** It judges "is this supervisor-owned path inside the tree the actor writes", which
is exactly the question the control-plane root asks; the word "baseline" in the name is
historical. Do not rename it in this plan — it is called from `write_baseline`,
`read_baseline` and `lifecycle`, and a rename would enlarge a plan whose whole claim is that
it touches nothing that ships. Note it for a later cleanup.

**The design cites `findings/paths.py` nowhere in this plan's scope, and that is correct.**
Revision 8 corrected an earlier citation: every primitive there anchors *inside* a project
root, and the control plane is deliberately outside one. If you find yourself reaching for
`open_dir_inside` or `resolve_inside` here, you are in the wrong module.

**Nothing in this plan creates a directory.** `control_plane_root` resolves and validates;
`run_dir` calculates. Exclusive creation of `baseline.json`, the journal, and `served/` is
plan 2's, through `autonomy/baseline.py`'s `open("x")` + containment pairing.

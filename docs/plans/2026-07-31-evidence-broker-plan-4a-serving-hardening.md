# Evidence broker plan 4a — serving hardening

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the evidence broker's serving surface deterministic and bounded, so that plan 4b's
checker can replay a sealed exposure and trust that any difference it sees is the reviewer's doing.

**Architecture:** Four independent hardenings of already-merged code, plus a protocol bump that
declares them. Two git environment pins remove actor-controlled inputs (`.git/shallow`, promisor
remotes) rather than checking for them; one output ceiling in `run_git` bounds every capture the
broker makes, with the *disposition* of an overflow chosen by each of the four call sites; and one
scan at `start_run` refuses to open a run against a tree whose paths cannot be cited honestly.

**Tech Stack:** Python 3.12+, pydantic v2 (`science-model`), `subprocess`/`selectors` from the
standard library, pytest, real `git` (2.55 on the development machine).

**Design:** [`2026-07-30-agent-evidence-broker-design.md`](2026-07-30-agent-evidence-broker-design.md)
at revision 26 — §2.2 (slice contracts), §3.1 (the tree rule), §3.2 (pins, ceiling, payload bound),
§3.2.1 (canonical invocation), §7 (mutation roster). Read §2.2 first: it is authoritative for what
this slice may and may not touch.

## Global Constraints

- **Run all commands from `science/`** (CLI package) or `science/model/` (model package). There is
  **no root `pyproject.toml`**; `uv run` from the repo root fails. Tests are `uv run --frozen pytest`.
- **This slice must not touch `science_model/audit/*`, and must not change any stored-record model.**
  The stated rule is the second one; the directory is only where it usually lives.
- **This slice must not create `evidence_broker/hits.py` or `evidence_broker/correspondence.py`,**
  and must not assume any checker exists. Those are plan 4b.
- **`evidence_broker/session.py` is not modified.** The tree scan belongs at
  `autonomy/lifecycle.py::start_run`, which is the only place that sees a pinned commit before any
  request exists. Putting it in `session.py` would rescan per request and still miss a run that opens
  and never serves.
- **Fail early; no silent fallbacks.** Every ceiling in this plan **refuses rather than truncates**.
  A truncated config listing silently under-blanks filter drivers; a truncated tree scan silently
  declares an unscanned tree NFC. Both are fail-opens dressed as robustness.
- **No compatibility or legacy shims**, and no `Unified` prefix on any name.
- **Conventional commits**, no AI-attribution trailer or footer.
- **Use `~/d/` or relative paths in docs and code**, never `/home/keith/` or `/mnt/ssd/Dropbox/`.
- `MAX_SERVED_BYTES = 1 << 20` (1 MiB) and `MAX_RUN_SERVED_BYTES = MAX_BUDGET * MAX_SERVED_BYTES`.
- `REPLAY_PROTOCOL_VERSION` becomes `2`.
- Environment pins, exact spellings: `GIT_SHALLOW_FILE=/dev/null`, `GIT_NO_LAZY_FETCH=1`.

---

## File Structure

| File | Change | Responsibility after this slice |
|---|---|---|
| `science/model/src/science_model/evidence_broker.py` | modify | Adds `MAX_SERVED_BYTES`, `MAX_RUN_SERVED_BYTES`; `REPLAY_PROTOCOL_VERSION = 2`. Bounds live beside the ones plan 3 added, so the journal's and the payload's ceilings are derivable from one place. |
| `science/src/science_tool/autonomy/git.py` | modify | Gains two `_ENVIRONMENT` pins, `is_shallow()`, and the bounded-capture ceiling with `GitOutputTooLarge`. Remains the single place autonomy's git argv and environment are built. |
| `science/src/science_tool/evidence_broker/serve.py` | modify | Passes `stdout_limit=MAX_SERVED_BYTES` on the three served ops, pre-checks `read` with `cat-file -s`, and converts a **stdout** overflow into a journaled `Denial` while letting a **stderr** overflow propagate. |
| `science/src/science_tool/autonomy/lifecycle.py` | modify | `start_run` refuses to open a brokered run against a non-NFC/non-UTF-8 tree, or a shallow repository. |
| `science/tests/test_autonomy_git_canonical.py` | modify | Real-git probes: the two pins, `is_shallow`, the ceiling. |
| `science/tests/test_evidence_broker_serve.py` | modify | The payload bound and its disposition split. |
| `science/tests/test_autonomy_lifecycle.py` | modify | The tree scan and shallow refusal at open. |
| `science/model/tests/test_evidence_broker_model.py` | modify | The bounds and the protocol value. |

**Task order is dependency order.** Task 1 defines constants Tasks 3–5 import. Task 3's ceiling is a
prerequisite for Task 4's disposition split. Task 2 is independent of Task 3 and could be done in
either order; it is first because it is the smallest and establishes the real-git fixture style the
later tasks reuse.

---

## Vocabulary this plan introduces

The implementer of any task may rely on these exact names:

```python
# science_model/evidence_broker.py
MAX_SERVED_BYTES: int          # 1 << 20
MAX_RUN_SERVED_BYTES: int      # MAX_BUDGET * MAX_SERVED_BYTES
REPLAY_PROTOCOL_VERSION: int   # 2

# science_tool/autonomy/git.py
class GitOutputTooLarge(GitError):     # a GitError SUBCLASS -- see Task 3
    stream: str    # "stdout" or "stderr"
    limit: int
    consumed: int  # bytes buffered when it raised; how §7 proves the check runs during capture
def is_shallow(repo_root: Path) -> bool: ...
def run_git(
    repo_root: Path, *args: str, input: bytes | None = None, stdout_limit: int | None = None
) -> subprocess.CompletedProcess[bytes]: ...
```

---

### Task 1: Bounds and the protocol bump

**Files:**
- Modify: `science/model/src/science_model/evidence_broker.py:71-84` (the bounds block)
- Test: `science/model/tests/test_evidence_broker_model.py`

**Interfaces:**
- Consumes: `MAX_BUDGET` (already present, `= 100`).
- Produces: `MAX_SERVED_BYTES`, `MAX_RUN_SERVED_BYTES`, `REPLAY_PROTOCOL_VERSION = 2` — imported by
  Tasks 3, 4 and 5.

**Context.** Every existing reference to `REPLAY_PROTOCOL_VERSION` uses the symbol, not the literal
`1` (verified across `science/src`, `science/model/src`, and both test trees), so the bump breaks no
assertion. That is exactly why the test below pins the *value*: without it, a future edit could drift
the number with nothing failing.

Run everything in this task from `science/model/`.

- [ ] **Step 1: Write the failing test**

Append to `science/model/tests/test_evidence_broker_model.py`:

```python
def test_replay_protocol_version_is_two() -> None:
    """Pinned as a VALUE, not just a symbol.

    Every reference in the toolkit imports the name, so a drifting number would break nothing
    and be noticed by no one. Serving changed in plan 4a -- bounds, two environment pins -- and
    §5.2 makes that a bump. Changing this constant means deciding that prior exposures no longer
    replay; that decision belongs in a diff someone reviews.
    """
    from science_model.evidence_broker import REPLAY_PROTOCOL_VERSION

    assert REPLAY_PROTOCOL_VERSION == 2


def test_served_bounds_are_derived_from_the_budget() -> None:
    """The per-run ceiling is the per-request one times the budget, not an independent number.

    Plan 3 derived MAX_JOURNAL_BYTES from model bounds so a run could not write a journal it
    could not read back. The same argument applies to `served/`: a run whose disk ceiling was
    chosen separately could accept a request it cannot store.
    """
    from science_model.evidence_broker import (
        MAX_BUDGET,
        MAX_RUN_SERVED_BYTES,
        MAX_SERVED_BYTES,
    )

    assert MAX_SERVED_BYTES == 1 << 20
    assert MAX_RUN_SERVED_BYTES == MAX_BUDGET * MAX_SERVED_BYTES
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd science/model && uv run --frozen pytest tests/test_evidence_broker_model.py -k "replay_protocol_version_is_two or served_bounds" -v
```

Expected: FAIL — `ImportError: cannot import name 'MAX_SERVED_BYTES'`, and the protocol assertion
fails with `assert 1 == 2`.

- [ ] **Step 3: Add the constants**

In `science/model/src/science_model/evidence_broker.py`, change line 73 and extend the bounds block
that follows it:

```python
#: Bumped only when serving or parsing changes: defined misses, canonical argv, or hit parsing.
#: It is not the toolkit revision; a signal that fires on every release is ignored.
#:
#: 2 (plan 4a): serving is now bounded per request, and the child environment pins
#: `GIT_SHALLOW_FILE` and `GIT_NO_LAZY_FETCH`. Both change what an identical request returns
#: -- an oversized payload refuses where it used to be served, and a partial clone fails where
#: it used to be silently completed from its promisor remote -- so a v1 exposure replayed under
#: v2 rules is not comparable, which is what this number exists to say.
REPLAY_PROTOCOL_VERSION = 2

#: Character bounds make the journal's byte ceiling derivable before it is read. Pydantic counts
#: characters, not bytes; journal encoding accounts separately for the worst-case byte expansion.
MAX_TARGET_CHARS = 4096
MAX_BUDGET = 100
MAX_INLINE_INPUTS = 100
MAX_INLINE_LINES = (1 << 63) - 1

#: DERIVED FROM WHAT A REVIEWER COULD HAVE CONSUMED, not chosen for roundness. A payload no agent
#: can read is not evidence of exposure, and at roughly four bytes per token a mebibyte already
#: exceeds the context of the reviewers this program contemplates. Serving more would inflate
#: §5.1 coverage over material nobody saw.
MAX_SERVED_BYTES = 1 << 20

#: The disk one run can occupy: `run_git` holds a payload whole in memory, the session writes it
#: to `served/`, and replay reads it again, so the per-request bound is spent at least twice per
#: request and `MAX_BUDGET` times per run.
MAX_RUN_SERVED_BYTES = MAX_BUDGET * MAX_SERVED_BYTES
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
cd science/model && uv run --frozen pytest tests/test_evidence_broker_model.py -v
```

Expected: PASS, whole module.

- [ ] **Step 5: Run the consumers of the symbol**

```bash
cd science/model && uv run --frozen pytest tests/test_autonomous_run_record.py -v
cd science && uv run --frozen pytest tests/test_evidence_broker_session.py tests/test_autonomy_lifecycle.py -q
```

Expected: PASS. These seal `replay_protocol=REPLAY_PROTOCOL_VERSION` and would catch a bump that
broke sealing.

- [ ] **Step 6: Commit**

```bash
git add science/model/src/science_model/evidence_broker.py science/model/tests/test_evidence_broker_model.py
git commit -m "feat(evidence-broker): bound served payloads and bump the replay protocol to 2"
```

---

### Task 2: Pin the git environment and add `is_shallow`

**Files:**
- Modify: `science/src/science_tool/autonomy/git.py:99-116` (`_ENVIRONMENT`), and append `is_shallow`
- Test: `science/tests/test_autonomy_git_canonical.py`

**Interfaces:**
- Consumes: `run_git`, `_ENVIRONMENT` (both already present).
- Produces: `is_shallow(repo_root: Path) -> bool` — used by Task 5 at `start_run`, and by plan 4b at
  replay. This is the one function; do not write a second spelling of the check anywhere.

**Context — why pins and not checks.** `.git/shallow` is an ordinary file in the actor-owned `.git`
directory. **Measured, git 2.55:** in a three-commit repository, `git log <commit>` returned 3
commits; after a single `echo <sha> > .git/shallow`, the identical argv against the identical commit
returned 2 — *both at exit 0*. A check at run open cannot hold, because the actor writes the file
afterwards. The defense is an input git no longer reads, exactly as `-c` outranks `.git/config`.

A partial clone is the second door and it is worse: `--filter=tree:0` neither truncates nor fails —
it **lazily fetches from its promisor remote mid-request at exit 0** (measured: 2 `git fetch`
subprocesses spawned, full answer returned). That remote's URL lives in `.git/config`, so lazy fetch
is an egress channel out of the control plane. `-c` cannot close it: the neutralization would have to
name the remote, and the remote's name is the actor's to pick.

`is_shallow` survives as a **diagnostic**, not the guarantee — it turns a genuinely shallow clone
into an operator error at open with a sentence naming the cause, instead of a
`fatal: Failed to traverse parents` in the middle of a run. **Measured: `rev-parse
--is-shallow-repository` does NOT honour `GIT_SHALLOW_FILE`** — it reads `true` under the pin — so
the detector keeps working through hardened `run_git` with no special case.

- [ ] **Step 1: Write the failing tests**

Append to `science/tests/test_autonomy_git_canonical.py`. These use real git. The module already has
`_repo(tmp_path) -> Path`, `_bare_git`, `_signed_repo` and `_filtered_repo`; the fixture and helper
below are new names that do not collide with any of them. `_commit` is used by Tasks 2 and 3, so
define it once.

```python
def _commit(repo: Path, name: str, body: str) -> None:
    """Write `body` to `name` and commit it. The commit MESSAGE is the file name, not the body:
    a 4 KiB commit message would work but makes `git log` output unreadable when a test fails."""
    (repo / name).write_text(body, encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", name], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-q", "-m", name],
        check=True,
        capture_output=True,
        env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@e",
             "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@e"},
    )


@pytest.fixture
def three_commit_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "src"
    repo.mkdir()
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True, capture_output=True)
    for text in ("one", "two", "three"):
        _commit(repo, "f.txt", text)
    return repo


def test_a_planted_shallow_file_does_not_shorten_history(three_commit_repo: Path) -> None:
    """The actor writes `.git/shallow` AFTER the run opens; a check at open cannot see it.

    Unpinned, this is 2 commits at exit 0 -- a silently shortened answer to a pinned commit.
    """
    commit = run_git(three_commit_repo, "rev-parse", "HEAD").stdout.decode().strip()
    parent = run_git(three_commit_repo, "rev-parse", "HEAD~1").stdout.decode().strip()

    before = run_git(three_commit_repo, "log", "--pretty=format:%H", commit).stdout

    (three_commit_repo / ".git" / "shallow").write_text(f"{parent}\n", encoding="utf-8")
    after = run_git(three_commit_repo, "log", "--pretty=format:%H", commit).stdout

    assert after == before
    assert len(before.decode().split()) == 3


def test_a_partial_clone_fails_rather_than_fetching(tmp_path: Path, three_commit_repo: Path) -> None:
    """A promisor remote is an egress channel, not just a source of non-determinism.

    `uploadpack.allowFilter` MUST be set on the serving side: it defaults to false, and without
    it the filtered clone comes back COMPLETE and this test passes against the defect.
    """
    subprocess.run(
        ["git", "-C", str(three_commit_repo), "config", "uploadpack.allowFilter", "true"],
        check=True,
        capture_output=True,
    )
    clone = tmp_path / "partial"
    subprocess.run(
        ["git", "clone", "-q", "--filter=tree:0", "--no-checkout",
         f"file://{three_commit_repo}", str(clone)],
        check=True,
        capture_output=True,
    )
    # PRECONDITION, and it must not be built out of the thing under test: derive the OID from the
    # SOURCE repository and check absence with our own explicit pin. Unpinned `cat-file -e` in the
    # clone exits 0 AND fetches the object in, destroying the condition it was establishing.
    tree = run_git(three_commit_repo, "rev-parse", "HEAD~1^{tree}").stdout.decode().strip()
    probe = subprocess.run(
        ["git", "-C", str(clone), "cat-file", "-e", tree],
        capture_output=True,
        env={**os.environ, "GIT_NO_LAZY_FETCH": "1"},
    )
    assert probe.returncode != 0, "the filter did not take; check uploadpack.allowFilter"

    commit = run_git(clone, "rev-parse", "HEAD").stdout.decode().strip()
    completed = run_git(clone, "log", "--pretty=format:%H", commit, "--", "f.txt")

    assert completed.returncode != 0
    assert b"unable to read tree" in completed.stderr


def test_is_shallow_reports_a_genuine_shallow_clone(tmp_path: Path, three_commit_repo: Path) -> None:
    """And keeps working through hardened `run_git`: `--is-shallow-repository` ignores the pin."""
    clone = tmp_path / "shallow"
    subprocess.run(
        ["git", "clone", "-q", "--depth", "1", f"file://{three_commit_repo}", str(clone)],
        check=True,
        capture_output=True,
    )

    assert is_shallow(clone) is True
    assert is_shallow(three_commit_repo) is False
```

Add `import os`, `import subprocess`, and `from science_tool.autonomy.git import is_shallow, run_git`
to the module's imports if they are not already there.

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd science && uv run --frozen pytest tests/test_autonomy_git_canonical.py -k "planted_shallow or partial_clone or is_shallow" -v
```

Expected: FAIL — `ImportError: cannot import name 'is_shallow'` for the third, and the first two fail
on the assertions (3 vs 2 commits; a successful `log` instead of a non-zero exit).

- [ ] **Step 3: Add the pins and the detector**

In `science/src/science_tool/autonomy/git.py`, extend `_ENVIRONMENT` and its docstring:

```python
#: The environment every autonomy git call runs under. `LC_ALL` and `LANG` are pinned
#: because argv is not the whole invocation: a POSIX class such as `[[:alpha:]]` matches a
#: different character set under `C` than under a UTF-8 locale, so two honest replays of one
#: pattern against one commit would disagree -- and §5.3 refuses on disagreement. The same
#: pin fixes git's DIAGNOSTIC text, which the broker's defined-miss classifier reads: under a
#: translated locale the miss messages would not match and an absent path would halt the run.
#:
#: `GIT_SHALLOW_FILE` and `GIT_NO_LAZY_FETCH` are here for the reason `-c` hardening is here: the
#: actor owns the file. `.git/shallow` is an ordinary file in the actor-owned `.git` directory --
#: MEASURED, git 2.55: one `echo <sha> > .git/shallow` takes `git log <commit>` from 3 commits to
#: 2, at exit 0 both ways, against an unchanged pinned commit. A check at run open cannot hold
#: against a file written after the run opens, so the defense is an input git no longer reads.
#:
#: A partial clone is the same problem in the worse direction. `--filter=tree:0` does not truncate
#: and does not fail: it LAZILY FETCHES the missing objects from its promisor remote, mid-request,
#: at exit 0 -- MEASURED, two `git fetch` subprocesses spawned under the canonical `log` argv. That
#: remote's URL lives in `.git/config`, so lazy fetch hands the actor an egress channel out of the
#: control plane and a payload whose content depends on a host it named. `-c` cannot close it: the
#: neutralization would have to name the remote, and the name is the actor's to choose.
#:
#: Under both pins a repository that cannot answer locally EXITS NON-ZERO instead of answering
#: short or phoning home, which every call site here already treats as a refusal to answer. Both
#: are no-ops in an ordinary complete clone, which has no boundary file and nothing to fetch.
#:
#: They apply to all three broker ops, not to `history` alone: a partial clone withholds blobs as
#: readily as trees, so `cat-file blob` and `grep` reach a promisor remote by the same mechanism.
#: Putting them in `_ENVIRONMENT` rather than at one call site is what makes that automatic.
#:
#: `TZ` is deliberately NOT pinned: `%aI` carries its own offset, so the rendered log does not
#: depend on the reader's zone. Pinning it would assert a defense against behaviour the chosen
#: format has been shown not to have.
_ENVIRONMENT: dict[str, str] = {
    "LC_ALL": "C",
    "LANG": "C",
    "GIT_SHALLOW_FILE": "/dev/null",
    "GIT_NO_LAZY_FETCH": "1",
}
```

Then append `is_shallow` at the end of the module:

```python
def is_shallow(repo_root: Path) -> bool:
    """Whether `repo_root` holds a shallow boundary.

    A DIAGNOSTIC, not the guarantee. `GIT_SHALLOW_FILE` above is what makes history answer
    completely or fail; this exists so that a genuinely shallow clone is reported as an operator
    error at run open, with a sentence naming the cause, rather than as a
    `fatal: Failed to traverse parents` in the middle of a run.

    The two cover disjoint intervals and neither depends on the other: at `start_run` no actor
    exists yet, so a boundary present then is genuine; a boundary appearing later is the actor's,
    and the pin neutralizes it.

    MEASURED: `--is-shallow-repository` does NOT honour `GIT_SHALLOW_FILE` -- it reads `true`
    under the pin -- so this keeps working through hardened `run_git` with no special case.
    """
    completed = run_git(repo_root, "rev-parse", "--is-shallow-repository")
    if completed.returncode != 0:
        raise GitError(
            f"could not determine whether {repo_root} is a shallow repository: "
            f"{completed.stderr.decode('utf-8', 'replace').strip()}"
        )
    return completed.stdout.decode("utf-8", "replace").strip() == "true"
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
cd science && uv run --frozen pytest tests/test_autonomy_git_canonical.py -v
```

Expected: PASS.

- [ ] **Step 5: Run the callers that share this environment**

`run_git` is shared beyond the broker: `autonomy/extract.py`, `autonomy/toolkit.py`,
`boundary/gitio.py`, and two `validate` checks.

```bash
cd science && uv run --frozen pytest tests/test_autonomy_extract.py tests/test_autonomy_toolkit.py tests/test_evidence_broker_serve.py tests/test_evidence_broker_canonical.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/autonomy/git.py science/tests/test_autonomy_git_canonical.py
git commit -m "feat(autonomy): pin GIT_SHALLOW_FILE and GIT_NO_LAZY_FETCH in the git environment"
```

---

### Task 3: The `run_git` output ceiling

**Files:**
- Modify: `science/src/science_tool/autonomy/git.py:133-149` (`_run`), `:151-206`
  (`_filter_driver_overrides`), `:209-234` (`run_git`)
- Test: `science/tests/test_autonomy_git_canonical.py`

**Interfaces:**
- Consumes: `MAX_SERVED_BYTES` is *not* used here — this task supplies the mechanism, Task 4 supplies
  that value at the served call sites.
- Produces:
  - `class GitOutputTooLarge(GitError)` with attributes `stream: str` (`"stdout"` or `"stderr"`),
    `limit: int`, and `consumed: int`.
  - `run_git(repo_root, *args, input=None, stdout_limit: int | None = None)`.
  - `MAX_GIT_STDERR_BYTES: int` and `MAX_CONFIG_LIST_BYTES: int`, module-level in `git.py`.

**Context — one ceiling, four dispositions.** The design's table (§3.2) is the specification:

| Overflow | Determined by | Disposition |
|---|---|---|
| served stdout (`read`, `search`, `history`) | the pinned commit | a journaled `Denial` — replays identically |
| `stderr`, on any call | mutable repository and runtime state | **fail the git invocation**; never journaled |
| the `config --list` preflight | `.git/config`, which the actor may edit at any time | **fail the git invocation**; never journaled |
| the §3.1 tree scan | the pinned commit, but runs before a run exists | **refuse to open the session** |

`run_git` supplies the *mechanism* and raises one exception; each of the four call sites chooses the
*disposition*. Journaling an environment-dependent refusal would be a fail-open with a delay — an
entry served before `.git/config` grew would refuse at replay, the bytes would not match, and §5.3
would return `EXPOSURE_UNREPRODUCIBLE`, refusing an honest review for a file the actor edited
afterwards.

**`stdout_limit` defaults to `None`, meaning unbounded, and that is deliberate.** `autonomy/extract.py`
and `boundary/gitio.py` legitimately capture large diffs and sync payloads through this same
function; a blanket stdout ceiling would regress them for a guarantee this design never claimed. The
four call sites that need a bound pass one.

**The check must happen during capture, not after.** A cap tested after `communicate()` returns has
already spent the memory it exists to protect.

- [ ] **Step 1: Write the failing tests**

Append to `science/tests/test_autonomy_git_canonical.py`:

```python
def test_stdout_overflow_refuses_and_does_not_truncate(three_commit_repo: Path) -> None:
    """Refuse, never truncate. A truncated answer is a wrong answer that looks like an answer."""
    _commit(three_commit_repo, "big.txt", "x" * 4096)
    commit = run_git(three_commit_repo, "rev-parse", "HEAD").stdout.decode().strip()

    with pytest.raises(GitOutputTooLarge) as caught:
        run_git(three_commit_repo, "cat-file", "blob", f"{commit}:big.txt", stdout_limit=64)

    assert caught.value.stream == "stdout"
    assert caught.value.limit == 64


def test_a_payload_at_the_limit_is_served(three_commit_repo: Path) -> None:
    """The boundary is inclusive; a payload of exactly `stdout_limit` bytes is not an overflow.

    Without this pair, an off-by-one that refused every payload would pass the test above.
    """
    body = "y" * 100
    _commit(three_commit_repo, "exact.txt", body)
    commit = run_git(three_commit_repo, "rev-parse", "HEAD").stdout.decode().strip()

    completed = run_git(
        three_commit_repo, "cat-file", "blob", f"{commit}:exact.txt", stdout_limit=len(body)
    )

    assert completed.returncode == 0
    assert completed.stdout == body.encode()


def test_stderr_is_bounded_on_every_call(three_commit_repo: Path, monkeypatch) -> None:
    """`stderr` is captured alongside stdout on EVERY call and is actor-influenced.

    §3.2.1 records `.git/objects/info/alternates` emitting a warning on ordinary commands, so an
    unbounded diagnostic is an unbounded allocation on a path the actor reaches without asking.
    """
    monkeypatch.setattr("science_tool.autonomy.git.MAX_GIT_STDERR_BYTES", 32)
    alternates = three_commit_repo / ".git" / "objects" / "info"
    alternates.mkdir(parents=True, exist_ok=True)
    (alternates / "alternates").write_text("/" + "n" * 4096 + "\n", encoding="utf-8")

    with pytest.raises(GitOutputTooLarge) as caught:
        run_git(three_commit_repo, "rev-parse", "HEAD")

    assert caught.value.stream == "stderr"


def test_a_large_stdin_payload_does_not_deadlock(three_commit_repo: Path) -> None:
    """The regression guard for the shape this task replaces.

    Writing all of stdin before reading anything deadlocks once the child's own output fills its
    pipe: the child blocks on stdout, stops reading stdin, and the parent blocks on stdin.
    MEASURED with `cat` and a 4 MiB write -- never returns. `check-ignore --stdin -z --verbose`
    both consumes a large stdin and emits a large stdout, so it exercises both directions at once.

    THE ALARM IS LOAD-BEARING. `pytest-timeout` is not a dependency of this package, and a
    deadlock's failure mode is SILENCE -- without this the regression hangs the suite instead of
    failing it, which is worse than not testing it at all. SIGALRM is POSIX-only; this suite
    already runs Linux-only tooling, and a handler that raises propagates through the blocked
    write (PEP 475 retries on EINTR only when the handler does NOT raise).
    """
    def _timeout(signum, frame):
        raise TimeoutError("run_git deadlocked writing stdin while the child wrote stdout")

    paths = b"\0".join(f"dir{n}/file{n}.txt".encode() for n in range(50000))
    previous = signal.signal(signal.SIGALRM, _timeout)
    signal.alarm(30)
    try:
        completed = run_git(
            three_commit_repo, "check-ignore", "--stdin", "-z", "--verbose", "--no-index",
            input=paths,
        )
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous)

    assert completed.returncode in (0, 1)  # 1 == nothing ignored, which is an answer


def test_the_config_preflight_is_bounded(three_commit_repo: Path, monkeypatch) -> None:
    """The preflight runs before EVERY `run_git` call and its size is the actor's to choose.

    `include.path` pulls in arbitrary files, so this is unbounded input on the path that executes
    most often -- and it is spent before the request it precedes is even authorized.
    """
    monkeypatch.setattr("science_tool.autonomy.git.MAX_CONFIG_LIST_BYTES", 64)
    included = three_commit_repo / "extra.config"
    included.write_text(
        "".join(f"[filter \"d{n}\"]\n\tclean = cat\n" for n in range(200)), encoding="utf-8"
    )
    subprocess.run(
        ["git", "-C", str(three_commit_repo), "config", "include.path", str(included)],
        check=True,
        capture_output=True,
    )

    with pytest.raises(GitError):
        run_git(three_commit_repo, "rev-parse", "HEAD")
```

Add `GitError, GitOutputTooLarge` to the module's imports from `science_tool.autonomy.git`, and
`import signal`.

**`pytest-timeout` is NOT installed in this package** — do not reach for `@pytest.mark.timeout`; it
is silently ignored as an unknown mark, which is how a deadlock guard becomes a hang.

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd science && uv run --frozen pytest tests/test_autonomy_git_canonical.py -k "overflow or at_the_limit or stderr_is_bounded or preflight_is_bounded" -v
```

Expected: FAIL — `ImportError: cannot import name 'GitOutputTooLarge'`.

- [ ] **Step 3: Implement bounded capture**

In `science/src/science_tool/autonomy/git.py`, add the exception and the two ceilings beside the
existing constants:

```python
class GitOutputTooLarge(GitError):
    """A git invocation produced more output than its caller allowed.

    A SUBCLASS OF `GitError`, so the DEFAULT disposition is the safe one. Five call sites already
    convert `GitError` into a run-level `unwired` -- `autonomy/extract.py:48`,
    `autonomy/toolkit.py:43`, `boundary/gitio.py:83` and `:166`, and
    `validate/checks/autonomous_runs.py:75`. An exception outside that hierarchy would escape all
    five and surface as an unhandled traceback: exit 1, which the documented codes read as
    `quarantined` rather than `unwired`. Overflow IS a failure to complete the invocation, which
    is what `GitError` already means.

    Subclassing costs no precision. A call site wanting a different disposition catches
    `GitOutputTooLarge` specifically, and `serve.py` does exactly that for its stdout case. ORDER
    MATTERS: an `except GitOutputTooLarge` must precede any `except GitError` in the same `try`.

    `consumed` is how §7 certifies that the ceiling is enforced DURING capture rather than after:
    a check moved to the end of the loop would report the whole output here.
    """

    def __init__(self, stream: str, limit: int, consumed: int, args: tuple[str, ...]) -> None:
        super().__init__(
            f"git {' '.join(args)} produced more than {limit} bytes on {stream}; refused rather "
            "than truncated, because a truncated answer is indistinguishable from a short one"
        )
        self.stream = stream
        self.limit = limit
        self.consumed = consumed


#: Diagnostics are never legitimately large, and this one is actor-influenced (§3.2.1).
MAX_GIT_STDERR_BYTES = 1 << 20

#: `include.path` makes the configuration listing arbitrarily large, and the preflight runs before
#: every call. Generous enough for any real configuration, bounded because the actor writes it.
MAX_CONFIG_LIST_BYTES = 1 << 20
```

Replace `_run` with a bounded capture. It reads both pipes with `selectors` so neither can fill and
deadlock the other, and kills the child the moment a ceiling is passed:

```python
_CHUNK = 65536


def _capture(
    process: subprocess.Popen[bytes],
    *,
    input: bytes | None,
    stdout_limit: int | None,
    stderr_limit: int,
    args: tuple[str, ...],
) -> tuple[bytes, bytes]:
    """Pump stdin and drain both output pipes in ONE loop.

    ALL THREE STREAMS MUST SHARE THE LOOP, and this is not defensive coding -- it is the only
    shape that terminates. Pipe buffers are finite (~64 KiB each). Writing all of stdin before
    reading anything deadlocks the moment the child's own output fills its pipe: the child blocks
    writing stdout, so it stops reading stdin, so the parent blocks writing stdin, forever.
    MEASURED: `Popen(["cat"])` plus a 4 MiB `stdin.write` never returns. `boundary/sync.py` and
    `boundary/gitio.py` both pass payloads through `input=`, so this is a live path, not a
    hypothetical. Draining stdout fully before stderr fails the same way for the same reason.

    The ceiling is checked as the bytes ARRIVE. A cap tested after the loop has already spent the
    memory it exists to protect, which is why `GitOutputTooLarge` carries `consumed`.
    """
    limits = {"stdout": stdout_limit, "stderr": stderr_limit}
    buffers: dict[str, bytearray] = {"stdout": bytearray(), "stderr": bytearray()}

    selector = selectors.DefaultSelector()
    pending = memoryview(input) if input else None
    if pending is not None:
        assert process.stdin is not None
        selector.register(process.stdin, selectors.EVENT_WRITE, "stdin")
    elif process.stdin is not None:
        process.stdin.close()
    for name in ("stdout", "stderr"):
        stream = getattr(process, name)
        assert stream is not None
        selector.register(stream, selectors.EVENT_READ, name)

    try:
        while selector.get_map():
            for key, _ in selector.select():
                if key.data == "stdin":
                    assert pending is not None
                    try:
                        written = key.fileobj.write(pending[:_CHUNK])  # type: ignore[union-attr]
                    except BrokenPipeError:
                        # The child exited without reading its input. That is an ANSWER (git
                        # refused early), not a failure to invoke, so it is not an error here.
                        written = None
                    if written is None:
                        pending = None
                    else:
                        pending = pending[written:]
                    if not pending:
                        selector.unregister(key.fileobj)
                        key.fileobj.close()  # type: ignore[union-attr]
                        pending = None
                    continue

                name = key.data
                chunk = key.fileobj.read1(_CHUNK)  # type: ignore[union-attr]
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                buffers[name] += chunk
                limit = limits[name]
                if limit is not None and len(buffers[name]) > limit:
                    process.kill()
                    raise GitOutputTooLarge(name, limit, len(buffers[name]), args)
    finally:
        selector.close()
        for stream in (process.stdin, process.stdout, process.stderr):
            if stream is not None and not stream.closed:
                stream.close()
        if process.poll() is None:
            process.kill()
        process.wait()
    return bytes(buffers["stdout"]), bytes(buffers["stderr"])


def _run(
    repo_root: Path,
    overrides: tuple[str, ...],
    args: tuple[str, ...],
    *,
    input: bytes | None = None,
    stdout_limit: int | None = None,
    stderr_limit: int = MAX_GIT_STDERR_BYTES,
) -> subprocess.CompletedProcess[bytes]:
    argv = _argv(repo_root, overrides, args)
    try:
        process = subprocess.Popen(
            argv,
            stdin=subprocess.PIPE if input is not None else subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env={**os.environ, **_ENVIRONMENT},
        )
    except (OSError, ValueError) as exc:
        raise GitError(f"could not execute git {' '.join(args)} in {repo_root}: {exc}") from exc

    stdout, stderr = _capture(
        process,
        input=input,
        stdout_limit=stdout_limit,
        stderr_limit=stderr_limit,
        args=args,
    )
    return subprocess.CompletedProcess(argv, process.returncode, stdout, stderr)
```

`read1` rather than `read`: `read(n)` on a `BufferedReader` loops until it has `n` bytes or hits
EOF, which re-serialises the very interleaving the selector exists to avoid. `read1` returns what
one underlying read produced.

Add `import selectors` to the module's imports.

Then bound the preflight in `_filter_driver_overrides` — replace its first line:

```python
    try:
        completed = _run(
            repo_root,
            _HARDENING,
            ("config", "--list", "--name-only", "-z"),
            stdout_limit=MAX_CONFIG_LIST_BYTES,
        )
    except GitOutputTooLarge as exc:
        # FAILS THE INVOCATION, and is never journaled. Its size is determined by `.git/config`,
        # which the actor may edit at any time -- so a journaled refusal would replay differently
        # once the file changed, and §5.3 would return EXPOSURE_UNREPRODUCIBLE for an honest run.
        raise GitError(
            f"the git configuration of {repo_root} is too large to read, so its filter drivers "
            f"could not be neutralized: {exc}"
        ) from exc
```

Finally, thread the parameter through `run_git`:

```python
def run_git(
    repo_root: Path,
    *args: str,
    input: bytes | None = None,
    stdout_limit: int | None = None,
) -> subprocess.CompletedProcess[bytes]:
```

extending its docstring with:

```
    `stdout_limit` bounds the captured payload and RAISES `GitOutputTooLarge` rather than
    truncating. It defaults to `None` -- unbounded -- because `extract` and `boundary/gitio`
    legitimately capture large diffs and sync payloads through this same function, and a blanket
    ceiling would regress them for a guarantee this design never made. The four call sites that
    need a bound pass one, and each chooses its own disposition (design §3.2).

    `stderr` is bounded on EVERY call at `MAX_GIT_STDERR_BYTES`, with no opt-out: it is captured
    alongside stdout regardless, it is actor-influenced, and no caller has a reason to want an
    unbounded diagnostic.
```

and its body:

```python
    return _run(
        repo_root,
        (*_HARDENING, *_filter_driver_overrides(repo_root)),
        args,
        input=input,
        stdout_limit=stdout_limit,
    )
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
cd science && uv run --frozen pytest tests/test_autonomy_git_canonical.py -v
```

Expected: PASS.

- [ ] **Step 5: Run every caller of `run_git`**

This task rewrites the process plumbing under six modules. This selection is not optional.

```bash
cd science && uv run --frozen pytest tests/test_autonomy_extract.py tests/test_autonomy_toolkit.py tests/test_autonomy_changes.py tests/test_autonomy_validate_check.py tests/test_evidence_broker_serve.py tests/test_evidence_broker_canonical.py tests/test_evidence_broker_session.py -q
cd science && uv run --frozen pytest tests/test_boundary_gitio.py tests/test_boundary_sync.py -q
```

Expected: PASS. `boundary/sync.py` and `boundary/gitio.py` pass `input=` with a payload, which is the
path most likely to expose a stdin-handling regression. **Do not run `pytest tests/ -k …`** — that
collects the whole ~12k-test suite before filtering and exceeds the default command timeout.

- [ ] **Step 6: Lint and typecheck**

```bash
cd science && uv run ruff check && uv run pyright
```

Expected: clean.

- [ ] **Step 7: Commit**

```bash
git add science/src/science_tool/autonomy/git.py science/tests/test_autonomy_git_canonical.py
git commit -m "feat(autonomy): bound git output during capture and refuse rather than truncate"
```

---

### Task 4: Bound served payloads

**Files:**
- Modify: `science/src/science_tool/evidence_broker/serve.py:186-215` (`_serve_read`), `:218-263`
  (`_serve_search`), and `_serve_history`
- Test: `science/tests/test_evidence_broker_serve.py`

**Interfaces:**
- Consumes: `MAX_SERVED_BYTES` (Task 1); `GitOutputTooLarge`, `run_git(..., stdout_limit=...)`
  (Task 3).
- Produces: a new `Denial.reason` value, `"payload-too-large"`. It joins the existing vocabulary
  (`path-malformed`, `path-denied`, `pattern-malformed`).

**Context.** `read` is **pre-checked, not captured-and-refused**: `cat-file -s <commit>:<path>` yields
the blob size before any content is read, so an oversized read never allocates. `search` and
`history` have unknown output size in advance, so they are bounded during capture.

The refusal is deterministic given the commit — the same request refuses identically at replay, which
is what keeps §5.2 sound. Under §5.1 it contributes no coverage, like every other refusal.

**A `stderr` overflow on a served op must NOT become a `Denial`.** It is determined by mutable
repository and runtime state, so journaling it would refuse an honest review later. Catch
`stream == "stdout"` only, and let the rest propagate.

- [ ] **Step 1: Write the failing tests**

This module has **no fixtures** — it uses module-level helpers `_repo(tmp_path) -> (root, commit)`,
`_read(target)`, `_search(pattern, pathspec=None)`, and a module constant `OPEN` (an unrestricted
`SurfacePolicy`). Use them; do not introduce a parallel fixture.

`_repo` already writes `a.txt` with `alpha\nbeta\n`. **Add one line to `_repo`** so there is a blob
that can exceed a lowered ceiling:

```python
    (root / "big.txt").write_text("x" * 4096, encoding="utf-8")
```

Then append to `science/tests/test_evidence_broker_serve.py`:

```python
def test_an_oversized_read_refuses_without_reading_the_blob(tmp_path: Path, monkeypatch):
    """Pre-checked with `cat-file -s`, so the bytes are never allocated.

    The spy is the point: a `read` that refuses AFTER capturing has already spent the memory the
    bound exists to protect, and a test asserting only the outcome cannot tell the two apart.
    """
    root, commit = _repo(tmp_path)
    monkeypatch.setattr("science_tool.evidence_broker.serve.MAX_SERVED_BYTES", 16)
    blob_reads: list[tuple[str, ...]] = []
    real = serve_module.run_git

    def spy(repo_root, *args, **kwargs):
        if args[:2] == ("cat-file", "blob"):
            blob_reads.append(args)
        return real(repo_root, *args, **kwargs)

    monkeypatch.setattr("science_tool.evidence_broker.serve.run_git", spy)

    served = serve(root, commit, _read("big.txt"), OPEN)

    assert served.outcome is Outcome.REFUSED
    assert served.denial is not None
    assert served.denial.reason == "payload-too-large"
    assert blob_reads == [], "the blob was read despite the size pre-check"


def test_a_read_at_the_limit_is_still_served(tmp_path: Path, monkeypatch):
    """The boundary is inclusive. Without this, refusing everything would pass the test above."""
    root, commit = _repo(tmp_path)
    monkeypatch.setattr("science_tool.evidence_broker.serve.MAX_SERVED_BYTES", len(b"alpha\nbeta\n"))

    served = serve(root, commit, _read("a.txt"), OPEN)

    assert served.outcome is Outcome.SERVED
    assert served.payload == b"alpha\nbeta\n"


def test_an_oversized_search_refuses(tmp_path: Path, monkeypatch):
    """`search` output size is unknown in advance, so it is bounded DURING capture."""
    root, commit = _repo(tmp_path)
    monkeypatch.setattr("science_tool.evidence_broker.serve.MAX_SERVED_BYTES", 16)

    served = serve(root, commit, _search("secret"), OPEN)

    assert served.outcome is Outcome.REFUSED
    assert served.denial is not None
    assert served.denial.reason == "payload-too-large"


def test_an_oversized_refusal_is_identical_on_a_second_serve(tmp_path: Path, monkeypatch):
    """Deterministic given the commit -- which is the whole reason it MAY be journaled."""
    root, commit = _repo(tmp_path)
    monkeypatch.setattr("science_tool.evidence_broker.serve.MAX_SERVED_BYTES", 16)

    first = serve(root, commit, _search("secret"), OPEN)
    second = serve(root, commit, _search("secret"), OPEN)

    assert first == second


def test_an_oversized_history_refuses(tmp_path: Path, monkeypatch):
    """`history` has its OWN try/except in `_serve_history`, so it needs its own row.

    Count the rules, not the functions: `search` and `history` are two call sites bounded by two
    separate guards. A test that covers only `search` leaves `_serve_history`'s guard deletable
    with the roster still green.
    """
    root, commit = _repo(tmp_path)
    monkeypatch.setattr("science_tool.evidence_broker.serve.MAX_SERVED_BYTES", 8)

    # No `_history` helper exists in this module; history requests are built inline, as at line 185.
    served = serve(root, commit, EvidenceRequest(op=EvidenceOp.HISTORY, target="a.txt"), OPEN)

    assert served.outcome is Outcome.REFUSED
    assert served.denial is not None
    assert served.denial.reason == "payload-too-large"


def test_a_stderr_overflow_on_a_served_op_is_not_a_denial(tmp_path: Path, monkeypatch):
    """The disposition split, in one test.

    `stderr` is determined by mutable repository and runtime state. Journaled, it would replay
    differently once the environment changed and §5.3 would return EXPOSURE_UNREPRODUCIBLE --
    refusing an honest review for a file the actor edited afterwards.
    """
    root, commit = _repo(tmp_path)
    real = serve_module.run_git

    def boom(repo_root, *args, **kwargs):
        if args[:2] == ("cat-file", "blob"):
            raise GitOutputTooLarge("stderr", 32, args)
        return real(repo_root, *args, **kwargs)

    monkeypatch.setattr("science_tool.evidence_broker.serve.run_git", boom)

    with pytest.raises(GitOutputTooLarge):
        serve(root, commit, _read("a.txt"), OPEN)
```

Add to the module's imports: `from science_model.evidence_broker import MAX_SERVED_BYTES`,
`from science_tool.autonomy.git import GitOutputTooLarge`, and
`import science_tool.evidence_broker.serve as serve_module` (the spy patches the name `run_git` as
`serve.py` sees it, so it must be patched on that module, not on `autonomy.git`).

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd science && uv run --frozen pytest tests/test_evidence_broker_serve.py -k "oversized or stderr_overflow" -v
```

Expected: FAIL — the oversized read and search are served rather than refused.

- [ ] **Step 3: Implement the bound**

In `science/src/science_tool/evidence_broker/serve.py`, add the imports
(`MAX_SERVED_BYTES` from `science_model.evidence_broker`; `GitOutputTooLarge` from
`science_tool.autonomy.git`) and a shared helper:

```python
def _too_large(target: str, pathspec: str | None = None) -> Served:
    """A refusal, not an error, and DETERMINISTIC GIVEN THE COMMIT.

    That determinism is what licenses journaling it: the same request against the same commit
    refuses identically at replay, so §5.2's comparison stays sound. Under §5.1 it contributes no
    coverage, exactly like a policy denial.

    The notice names no size and no path. A blinded requester learning "this file is larger than
    1 MiB" has learned the file exists, which is what the policy's uniform notice withholds.
    """
    return Served(
        outcome=Outcome.REFUSED,
        payload=b"",
        target=target,
        denial=Denial(
            reason="payload-too-large",
            notice="the requested material exceeds the per-request serving limit",
        ),
        pathspec=pathspec,
    )
```

In `_serve_read`, after the `kind != b"blob"` check and **before** `cat-file blob`:

```python
    # PRE-CHECKED, NOT TRUNCATED. `-s` yields the blob size from the object header without
    # reading its content, so an oversized read never allocates the bytes it is about to refuse.
    sized = run_git(repo_root, "cat-file", "-s", f"{commit}:{target}")
    if sized.returncode != 0:
        raise ServeError(
            f"read of {target!r} at {commit} typed as a blob and then could not be sized: "
            f"{sized.stderr.decode('utf-8', 'replace').strip()}"
        )
    if int(sized.stdout.decode("ascii").strip()) > MAX_SERVED_BYTES:
        return _too_large(target)
```

In `_serve_search` and `_serve_history`, pass the bound and convert only a stdout overflow:

```python
    try:
        completed = run_git(
            repo_root,
            *_GREP_ARGV,
            "-e",
            pattern,
            commit,
            "--",
            *pathspecs,
            stdout_limit=MAX_SERVED_BYTES,
        )
    except GitOutputTooLarge as exc:
        # STDOUT ONLY. A `stderr` overflow is determined by mutable repository and runtime state,
        # so it must fail the invocation rather than enter the journal (design §3.2).
        if exc.stream != "stdout":
            raise
        return _too_large(pattern, pathspec)
```

Apply the same `try`/`except` shape to `_serve_history`'s `run_git` call, returning
`_too_large(target)`.

- [ ] **Step 4: Run the tests to verify they pass**

```bash
cd science && uv run --frozen pytest tests/test_evidence_broker_serve.py -v
```

Expected: PASS.

- [ ] **Step 5: Run the broker's adjacent guards**

```bash
cd science && uv run --frozen pytest tests/test_evidence_broker_canonical.py tests/test_evidence_broker_session.py tests/test_evidence_broker_journal.py tests/test_evidence_broker_cli.py -q
```

Expected: PASS. The session tests seal `Denial` reasons into journal entries, so a new reason that
did not round-trip would surface here.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/evidence_broker/serve.py science/tests/test_evidence_broker_serve.py
git commit -m "feat(evidence-broker): bound served payloads and refuse oversized requests"
```

---

### Task 5: Refuse to open against an unciteable tree or a shallow clone

**Files:**
- Modify: `science/src/science_tool/autonomy/lifecycle.py:138-205` (`start_run`)
- Test: `science/tests/test_autonomy_lifecycle.py`

**Interfaces:**
- Consumes: `is_shallow` (Task 2); `GitOutputTooLarge`, `run_git(..., stdout_limit=...)` (Task 3);
  `normalize_utf8_nfc` (already used by `SurfacePolicy`'s validator in
  `science_model/evidence_broker.py`); `BaselineError` (already raised by `start_run`).
- Produces: nothing consumed by 4b or 4c. This is the last piece of 4a's forward guarantee.

**Context — why the tree and not the request.** `normalize_project_path` maps a path to NFC; git
stores path bytes verbatim and matches pathspecs byte-exactly. Against a tree holding an NFD path
(`cafe\xcc\x81/x.txt`), an NFC deny prefix denies under `read` and **still serves under `search`**.

Revisions 11–16 parked this as that one leak and nominated `serve` inspecting the tree's path bytes as
the fix. Both were wrong. There are **three** directions, and the decisive one — a `read` returning
`MISS_ABSENT` for a path that exists under another spelling, **certifying a false absence claim** — is
reachable with no deny prefix and no search at all, so no amount of filtering on the serving side
closes it. One check, one layer: refuse the tree.

UTF-8 travels with NFC in the same check because a path that does not decode cannot be spelled as a
`LocationEvidence.path` either, so it can never be cited honestly.

**The scan runs before the session is created** — before `create_journal`, before `EvidenceSession` is
built. It is only for brokered runs (`evidence is not None`): a non-brokered run serves nothing and
has no citations to keep honest.

**A tree-scan overflow refuses to open the session** (fourth row of §3.2's table) — it does not become
a `Denial`, because there is no run yet to journal one against.

The cost, stated rather than buried: a genuinely NFD-authored repository cannot be brokered until it
renames. That is narrower than it sounds — git on macOS sets `core.precomposeunicode=true` by
default, so macOS-authored trees are usually already NFC even where the working filesystem is not.

- [ ] **Step 1: Write the failing tests**

This module has a `project` fixture returning a `Path`, a `baseline_path` fixture, and helpers
`_git(root, *args) -> str`, `_start(project, baseline_path)`, `_start_brokered(project, tmp_path,
monkeypatch, *, inline_paths=())` and `_spec(...)`. Use them.

Append to `science/tests/test_autonomy_lifecycle.py`:

```python
def _add_nfd_path(project: Path) -> None:
    """A directory whose name is NFD (`cafe` + COMBINING ACUTE), committed.

    Written through `os.fsdecode` of raw bytes rather than a literal, so the NFD spelling survives
    regardless of what the source file's own encoding normalizes to.
    """
    directory = project / os.fsdecode(b"cafe\xcc\x81")
    directory.mkdir()
    (directory / "x.txt").write_text("secret\n", encoding="utf-8")
    _git(project, "add", "-A")
    _git(project, "commit", "-q", "-m", "add an NFD path")


def test_a_brokered_run_refuses_to_open_against_an_nfd_tree(
    project: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The decisive direction needs no deny prefix and no search.

    A `read` of the NFC spelling returns MISS_ABSENT for a path that IS at the commit under an NFD
    spelling -- a certified false absence claim, which §5.1 calls frequently the decisive finding.
    """
    _add_nfd_path(project)

    with pytest.raises(BaselineError, match="NFC"):
        _start_brokered(project, tmp_path, monkeypatch)


def test_a_brokered_run_refuses_to_open_against_a_non_utf8_path(
    project: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A SEPARATE BRANCH from the NFD case, and therefore a separate row.

    `_assert_tree_is_citeable` enforces two rules -- decodes as UTF-8, and is already NFC. One
    test covering only NFD leaves the decode branch deletable with the roster green. Count the
    rules, not the functions.

    The filename is written as raw bytes: `0xff` is valid in a POSIX filename and in a git tree,
    and invalid as UTF-8, which is exactly the gap `LocationEvidence.path` cannot express.
    """
    (project / os.fsdecode(b"bad\xff.txt")).write_bytes(b"content\n")
    _git(project, "add", "-A")
    _git(project, "commit", "-q", "-m", "add a non-UTF-8 path")

    with pytest.raises(BaselineError, match="UTF-8"):
        _start_brokered(project, tmp_path, monkeypatch)


def test_a_non_brokered_run_opens_against_an_nfd_tree(
    project: Path, baseline_path: Path
) -> None:
    """The rule is about CITATIONS, not about trees.

    A run that serves nothing has nothing to cite, so refusing it would be a cost with no
    corresponding guarantee.
    """
    _add_nfd_path(project)

    baseline = _start(project, baseline_path)

    assert baseline.evidence is None


def test_a_valid_utf8_nfc_tree_opens_a_brokered_run(
    project: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The negative case, so the scan cannot pass by refusing every tree."""
    baseline = _start_brokered(project, tmp_path, monkeypatch)

    assert baseline.evidence is not None


def test_a_brokered_run_refuses_to_open_against_a_shallow_clone(
    project: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A DIAGNOSTIC: the pin is what makes history correct, this names the cause at open.

    Without it the operator meets `fatal: Failed to traverse parents` mid-run instead.
    """
    # A second commit, so `--depth 1` actually truncates something.
    (project / "later.txt").write_text("later\n", encoding="utf-8")
    _git(project, "add", "-A")
    _git(project, "commit", "-q", "-m", "later")
    clone = tmp_path / "shallow"
    subprocess.run(
        ["git", "clone", "-q", "--depth", "1", f"file://{project}", str(clone)],
        check=True,
        capture_output=True,
    )

    with pytest.raises(BaselineError, match="shallow"):
        _start_brokered(clone, tmp_path, monkeypatch)
```

Add `import os` to the module's imports if it is not already there (`subprocess` and `pytest` are).

And one test for the fourth row of §3.2's disposition table — a tree-scan overflow refuses to open
the session rather than becoming a `Denial`, because there is no run yet to journal one against:

```python
def test_an_oversized_tree_scan_refuses_to_open(
    project: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Refuses rather than truncating: a truncated scan silently declares an unscanned tree NFC.

    And refuses to OPEN rather than journaling a Denial -- at this point there is no run.
    """
    monkeypatch.setattr("science_tool.autonomy.lifecycle.MAX_TREE_SCAN_BYTES", 8)

    with pytest.raises(BaselineError, match="too large to scan"):
        _start_brokered(project, tmp_path, monkeypatch)
```

**Note on the shallow test:** a `--depth 1` clone of a project fixture carries the committed
`knowledge/graph.trig`, so `_capture` finds a belief basis and the run reaches the shallow check
rather than failing earlier for an unrelated reason. If it does fail earlier, the fixture — not the
guard — is what needs fixing; do not weaken the check to accommodate it.

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd science && uv run --frozen pytest tests/test_autonomy_lifecycle.py -k "nfd_tree or shallow_clone or utf8_nfc_tree or tree_scan" -v
```

Expected: FAIL — the brokered run opens in all cases.

- [ ] **Step 3: Implement the scan**

In `science/src/science_tool/autonomy/lifecycle.py`, add a module-level helper:

```python
#: `ls-tree -r` over a whole tree is proportional to the REPOSITORY, not to any request, and it
#: runs before a session is allowed to open. Overflow refuses the session: a truncated scan would
#: silently declare an unscanned tree NFC, which is a fail-open dressed as robustness.
MAX_TREE_SCAN_BYTES = 64 << 20


def _assert_tree_is_citeable(project_root: Path, commit: str) -> None:
    """Refuse a pinned tree holding a path no citation could name.

    `normalize_project_path` maps a path to NFC; git stores path bytes verbatim and matches
    pathspecs byte-exactly. So a policy and a repository can be spelled differently and both be
    right, and the disagreement runs in three directions -- a deny prefix that leaks under
    `search`, an honest citation refused, and a `read` answering MISS_ABSENT for a path that
    exists under another spelling. The third CERTIFIES A FALSE ABSENCE CLAIM, needs no deny prefix
    and no search at all, and is therefore unreachable by any filter on the serving side.

    One check, one layer, once per run: the tree is immutable at the pinned commit, so replay
    inherits the guarantee rather than repeating the scan. `serve` is unchanged.

    UTF-8 travels with NFC here because a path that does not decode cannot be spelled as a
    `LocationEvidence.path` either -- it can never be cited honestly, so it is the same rule.
    """
    try:
        completed = run_git(
            project_root,
            "ls-tree",
            "-r",
            "-z",
            "--name-only",
            commit,
            stdout_limit=MAX_TREE_SCAN_BYTES,
        )
    except GitOutputTooLarge as exc:
        raise BaselineError(
            f"the tree at {commit} is too large to scan for citeable paths, so a brokered run "
            f"cannot be opened against it: {exc}"
        ) from exc
    if completed.returncode != 0:
        raise BaselineError(
            f"could not list the tree at {commit}: "
            f"{completed.stderr.decode('utf-8', 'replace').strip()}"
        )
    for raw in completed.stdout.split(b"\0"):
        if not raw:
            continue
        try:
            path = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise BaselineError(
                f"the tree at {commit} holds a path that is not valid UTF-8 ({raw!r}), which no "
                "citation can name, so a brokered run cannot be opened against it"
            ) from exc
        if normalize_utf8_nfc(path) != path:
            raise BaselineError(
                f"the tree at {commit} holds the path {path!r}, which is not in NFC. Citations "
                "normalize to NFC and git matches pathspecs byte-exactly, so this path would be "
                "served by `search` while `read` reported it absent -- certifying a false absence "
                "claim. Rename it before brokering a run against this repository."
            )
```

Then, in `start_run`, inside the `if evidence is not None:` block and **before** `create_journal`:

```python
    session: EvidenceSession | None = None
    if evidence is not None:
        # BEFORE the journal and the session: this is the only place that sees the pinned commit
        # while no actor exists yet, and a run that opens and never serves must be covered too.
        if is_shallow(project_root):
            raise BaselineError(
                f"{project_root} is a shallow repository, so `history` cannot be served completely "
                "and a brokered run cannot be opened against it; clone with full history"
            )
        _assert_tree_is_citeable(project_root, base_commit)
        directory = run_dir(project_root, run_id)
        ...
```

Add the imports: `is_shallow`, `GitOutputTooLarge` and `run_git` from `science_tool.autonomy.git`,
and `from science_model.audit.subjects import normalize_utf8_nfc`.

**That import is allowed.** The constraint on this slice is *"changes no stored-record model"*, not
*"never mentions `audit/`"* — `normalize_utf8_nfc` is a pure function and `SurfacePolicy`'s own
validator already imports it from the same module. Writing the rule as a directory ban is what would
force the wrong structure here, which is the mistake §2.2 records for `Correspondence`.

- [ ] **Step 4: Run the tests to verify they pass**

```bash
cd science && uv run --frozen pytest tests/test_autonomy_lifecycle.py -v
```

Expected: PASS.

- [ ] **Step 5: Run the lifecycle's adjacent guards**

```bash
cd science && uv run --frozen pytest tests/test_autonomy_lifecycle_cli.py tests/test_autonomy_cli.py tests/test_autonomy_baseline.py tests/test_evidence_broker_session.py tests/test_evidence_broker_cli.py -q
```

Expected: PASS.

- [ ] **Step 6: Lint and typecheck**

```bash
cd science && uv run ruff check && uv run pyright
```

Expected: clean.

- [ ] **Step 7: Commit**

```bash
git add science/src/science_tool/autonomy/lifecycle.py science/tests/test_autonomy_lifecycle.py
git commit -m "feat(autonomy): refuse to broker a run against an unciteable tree or a shallow clone"
```

---

## Task 6: Certify the guards by mutation

**Files:**
- Test only. No production file is modified by this task; if one needs to be, that is a finding.

**Context.** §7's standing rule: *a guard nobody has watched fail is a guard nobody has tested.*
Every row below is a **pair** — break the guard, watch the named test fail, restore it. A mutation
that leaves its test green certifies nothing, and the roster is written to be run, not read.

**Two rows in this slice have known ways to go vacuously green**, and both must be closed before the
row counts:

1. **The lazy-fetch row.** `uploadpack.allowFilter` defaults to **false**: a `--filter=tree:0` clone
   from a serving repository without it comes back *complete*, so the mutation has nothing to expose.
   And the promisor remote must still hold the objects and be reachable — with the remote gone, both
   the pinned and unpinned runs fail and the pair proves nothing.
2. **The lazy-fetch row's own precondition.** Every obvious way to ask "is this tree absent?" is
   itself a lazy-fetch trigger: **measured**, unpinned `git cat-file -e <tree>` in a fresh
   `--filter=tree:0` clone **exits 0 and spawns a fetch**, and unpinned `git rev-parse 'HEAD~1^{tree}'`
   inside the clone spawns one too. A fixture that derives the OID in the partial clone, or checks
   absence through `run_git`, does not merely misreport under the mutation — **it fetches the object
   in and destroys the condition it was establishing**, so the row dies in setup and certifies
   nothing about serving. Derive the OID from the **source** repository; run the absence check with a
   *test-owned, explicit* `GIT_NO_LAZY_FETCH=1`.

**Ask of every fixture: which line does the mutation break first?** If the answer is a setup line,
the row is not testing what its name says.

- [ ] **Step 1: Run the roster**

For each row: apply the mutation to the production file, run the named test, confirm it **fails**,
then `git checkout` the file.

| Mutation | Test that must fail |
|---|---|
| Drop `GIT_SHALLOW_FILE` from `_ENVIRONMENT` | `test_a_planted_shallow_file_does_not_shorten_history` |
| Drop `GIT_NO_LAZY_FETCH` from `_ENVIRONMENT` | `test_a_partial_clone_fails_rather_than_fetching` |
| Drop the shallow check at open | `test_a_brokered_run_refuses_to_open_against_a_shallow_clone` |
| Check the payload cap after `_capture` returns instead of during | `test_stdout_overflow_refuses_and_does_not_truncate` (see Step 2 — this one needs care) |
| Truncate at the ceiling instead of raising | `test_stdout_overflow_refuses_and_does_not_truncate` |
| Bound stdout only (drop `stderr_limit`) | `test_stderr_is_bounded_on_every_call` |
| Exempt the `config --list` preflight | `test_the_config_preflight_is_bounded` |
| Exempt the tree scan from the ceiling | `test_an_oversized_tree_scan_refuses_to_open` |
| Remove the `cat-file -s` pre-check and refuse after capture | `test_an_oversized_read_refuses_without_reading_the_blob` |
| Delete `_serve_history`'s bound, leaving `_serve_search`'s | `test_an_oversized_history_refuses` |
| Journal a `stderr` overflow as a `Denial` | `test_a_stderr_overflow_on_a_served_op_is_not_a_denial` |
| Make `GitOutputTooLarge` inherit `RuntimeError` again | `test_an_overflow_reaches_an_existing_git_error_handler` (Step 2) |
| Write all of stdin before draining the pipes | `test_a_large_stdin_payload_does_not_deadlock` |
| Delete the NFC branch of the tree check | `test_a_brokered_run_refuses_to_open_against_an_nfd_tree` |
| Delete the UTF-8 branch of the tree check | `test_a_brokered_run_refuses_to_open_against_a_non_utf8_path` |
| Make the tree check refuse every tree | `test_a_valid_utf8_nfc_tree_opens` |
| Apply the tree check to non-brokered runs | `test_a_non_brokered_run_opens_against_an_nfd_tree` |
| Revert `REPLAY_PROTOCOL_VERSION` to 1 | `test_replay_protocol_version_is_two` |

- [ ] **Step 2: Close the two rows that cannot be certified by outcome alone**

The `GitError` subclassing row needs a test of its own, because nothing else notices it. Every
existing caller catches `GitError`; if `GitOutputTooLarge` leaves that hierarchy, an overflow in
`extract`, `toolkit`, `gitio` or the `validate` check escapes as an unhandled traceback — exit 1,
which the documented codes read as `quarantined` rather than `unwired`. Add to
`science/tests/test_autonomy_git_canonical.py`:

```python
def test_an_overflow_reaches_an_existing_git_error_handler(three_commit_repo: Path) -> None:
    """Five call sites convert `GitError` into `unwired`. An overflow must land in that net.

    Asserted through the HIERARCHY rather than by importing a caller: the claim is that any of
    the five keeps working, and `except GitError` is exactly what all five spell.
    """
    _commit(three_commit_repo, "big.txt", "x" * 4096)
    commit = run_git(three_commit_repo, "rev-parse", "HEAD").stdout.decode().strip()

    assert issubclass(GitOutputTooLarge, GitError)
    with pytest.raises(GitError):
        run_git(three_commit_repo, "cat-file", "blob", f"{commit}:big.txt", stdout_limit=64)
```

And the during-capture row: 

"Check the cap after capture" and "refuse rather than truncate" produce the *same outcome* for a
caller that only inspects the exception type — both raise. The difference is **how many bytes were
buffered before it raised**, and that has to be asserted, not described. This is why
`GitOutputTooLarge` carries `consumed`.

```python
def test_the_ceiling_is_checked_during_capture_not_after(three_commit_repo: Path) -> None:
    """A cap tested after the loop has already spent the memory it exists to protect.

    ASSERTED ON `consumed`, not on the exception type: both dispositions raise
    `GitOutputTooLarge`, so `pytest.raises` alone cannot separate them. Enforced during capture,
    the buffer holds at most the limit plus the one chunk that crossed it; enforced afterwards, it
    holds the entire 1 MiB blob. A comment claiming the call "returns promptly" measures nothing.
    """
    payload = "z" * (1 << 20)
    _commit(three_commit_repo, "huge.txt", payload)
    commit = run_git(three_commit_repo, "rev-parse", "HEAD").stdout.decode().strip()

    with pytest.raises(GitOutputTooLarge) as caught:
        run_git(three_commit_repo, "cat-file", "blob", f"{commit}:huge.txt", stdout_limit=1024)

    assert caught.value.consumed <= 1024 + 65536, (
        f"buffered {caught.value.consumed} bytes before refusing a 1024-byte ceiling; "
        "the check ran after capture, not during it"
    )
    assert caught.value.consumed < len(payload)
```

- [ ] **Step 3: Record the result**

For any row whose test did **not** fail under mutation, stop and report it. That is a real finding: a
guard certified by nothing. Do not "fix" it by making the mutation larger.

- [ ] **Step 4: Commit any test added in Steps 1–2**

```bash
git add science/tests/
git commit -m "test(evidence-broker): certify plan 4a's guards by mutation"
```

---

## Final verification

Both suites, because this slice changed shared process plumbing (`run_git`) and a model constant that
crosses the package boundary — two of AGENTS.md's stated triggers for a full run.

```bash
cd science/model && uv run --frozen pytest
cd science && uv run --frozen pytest
```

The CLI suite is ~12k tests and takes 6:42–7:24 on a Dropbox-backed checkout — longer than the
default 120s command timeout. **Pass an explicit long timeout on the tool call** (900000 ms), not as
a pytest flag: `pytest-timeout` is not a dependency here and `--timeout=…` would fail as an
unrecognized argument. **Run it from the top-level agent** — a foreground full run otherwise
auto-backgrounds and a subagent that yields waiting on it will not reliably resume. **Never run two
suites concurrently in one worktree**; they race on shared test-output paths.

---

## Self-review notes

**Spec coverage.** §3.1's tree rule → Task 5. §3.2's pins → Task 2; the payload bound → Task 4; the
`run_git` ceiling and its four dispositions → Task 3 (mechanism) plus Tasks 4 and 5 (dispositions).
§3.2.1's environment row → Task 2. The `REPLAY_PROTOCOL_VERSION` bump → Task 1. §7's 4a rows → Task 6.

**Out of scope, deliberately.** `evidence_broker/hits.py`, `correspondence.py`, `Correspondence`,
`ReviewAttestation`, `append_review`, and every §5 outcome belong to 4b and 4c. The `is_shallow`
call at *replay* is 4b's; this slice ships the function and calls it only at open.

**Known residual.** `autonomy/baseline.py` still resolves `baseline.json` by pathname rather than
through an anchored descriptor (design §3.5, carried from plan 3's revision 15). It is untouched here
and remains open for whichever slice next modifies that module.

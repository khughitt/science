# Evidence broker plan 2 — the serving surface

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Given a repository, a pinned commit, a request and a surface policy, produce
deterministic served bytes or a refusal — with no session, no journal, no control plane and no
CLI.

**Architecture:** One new model type (`SurfacePolicy`) and one new tool package
(`science_tool/evidence_broker/`) holding `policy.py` and `serve.py`. `policy.authorize` decides
whether a request may be answered and translates deny prefixes into pathspecs; `serve` builds the
canonical argv, runs it through plan 1's hardened `run_git`, and classifies the result. Nothing
here holds state, so every behaviour is provable from `(repo, commit, request, policy)` alone.

**Tech Stack:** Python 3.11+, Pydantic v2 (`science-model`), `subprocess` via
`science_tool.autonomy.git.run_git`, pytest.

## Scope: what this plan does NOT include, and why

Spec 2a is **four plans, not three**. Plan 1 (`control_plane.py`, `run_git` hardening) is merged
at `57b09bf0`. This is plan 2. The remaining two:

- **Plan 3 — the session and its record.** `InstrumentIdentity`, `InlineInput`, `EvidenceSession`,
  `RunBaseline.evidence`, `EvidenceSessionSpec`, `ExposureEntry`, `EvidenceExposure` and its four
  validators, `AutonomousRunRecord.evidence`, `evidence_broker/session.py` (journal, rounds,
  inline seeding), `served/<sha256>`, the CLI (`evidence open` / `evidence serve`,
  `--broker-spec`/`--baseline-out`, `--session`/`--baseline`), and the seal in `finish_run`.
- **Plan 4 — correspondence.** §5 entire, plus `Review` / `ReviewSubmission` / `Correspondence`,
  `append_review`, eligibility, and the replay protocol version.

**Why the cut falls here.** `policy.py` needs `SurfacePolicy` and the shipped
`normalize_project_path`. `serve.py` needs `policy.py` and plan 1's `run_git`. Neither touches a
session, a journal, a baseline, the control plane, or `ExposureEntry` — the session builds those.
Serving is therefore the largest piece of 2a that is completely testable with no state at all,
and every §7 determinism bullet lives inside it.

**Which §7 bullets this plan closes in full:** `serve.py`; canonical invocation; locale;
pathspec translation; `read` refuses a directory; the `policy.py` bullet; and the derived
dispatch guard. Everything else in §7 belongs to plan 3 or plan 4.

**Which §7 bullets this plan deliberately leaves, named so they are deferred rather than lost:**

| §7 requirement | Why it cannot land here |
|---|---|
| A denial spends a round; exhaustion refuses without further spend | Rounds are `session.py`'s; `serve` is stateless by design |
| Served bytes land in `served/<sha256>` and the write gate finds an empty `ChangeSet` | The destination is derived from `run_dir` + a session |
| `finish_run` seals a run whose `served/` has been emptied | No seal exists yet |

`serve` returns bytes to its caller and writes nothing. That is the intended shape: the
destination is a session concern, and putting it here would reintroduce the caller-chosen
`--output PATH` the design refused in §3.5.

## Design deviations recorded here

**None.** Three corrections that would have been deviations were instead made to the design
first, as revision 9 (`ac6e06c4`, `c297a57a`), because each was a defect in the design rather
than a choice this plan is making:

1. The seal no longer replays (§3.4.1 contradicted §5.2 and §6).
2. `read` is `git cat-file blob`, not `git show` — `show` serves a **directory** as a tree
   listing at exit 0, which would have recorded `FULL` coverage over a listing.
3. §3.2's account of why search pathspecs need `literal` was invented. The measured behaviour is
   over-exclusion, not a leak. `literal` stays; the reason is replaced.

Read §3.2 and §3.2.1 of the design at revision 9 before starting. Do not work from an older copy.

## What review found in this plan's first draft

Six findings, all reproduced against git 2.55 before being fixed. They are recorded because each
predicts a way the implementation can still go wrong, and four of them were guards that looked
correct on the page:

1. **Raw paths became pathspecs.** `authorize` normalized and then discarded the result, so git
   received the caller's own string. With deny prefix `private`, the history target `priv*`
   authorized and git expanded it onto `private/x.txt` — a policy bypass in both `log` and
   `grep`. Fixed by `Authorization.path` and `literal_pathspec`.
2. **Read-miss classification was substring-based.** A committed directory named
   `does not exist in` produced an error containing git's own miss sentence, so a present tree
   classified as an absent path. Fixed by `cat-file -t` plus fully interpolated sentences.
3. **The unknown-stderr test never reached the code it named.** Its fake failed every call, so
   `verify_commit` raised first. Fixed by answering the verification truthfully.
4. **The dispatch guard proved membership, not ordering.** Moving a helper above `authorize`
   still passed. Fixed by comparing source positions.
5. **Authorization ordering contradicted its own documentation**, including a test named
   `..._without_reaching_git` that never checked whether git was reached. Fixed by authorizing
   first and asserting it with a landmine.
6. **NUL-bearing patterns halted the run** as `GitError` instead of being refused as retryable.
   Fixed by judging argv validity in `authorize`.

The through-line: **four of the six were tests that passed against the defect they were written
to catch.** Step 5 of Task 3 and Step 3 of Task 4 exist to make that impossible to repeat by
accident — do not treat them as optional.

A second round found six more, all likewise reproduced first:

7. **A stale `request.target` survived the signature change** in `_serve_search`'s error branch —
   a `NameError` on the one path no green test exercises. Nothing structural; everything to do
   with editing code by hand in a document.
8. **History bypassed nested deny prefixes through an ancestor.** With deny prefix
   `private/x.txt`, the target `private` is beneath no prefix and authorizes, and `log` selects
   recursively. `read` refuses it as a tree and `grep` carries the exclusions, so `log` was the
   one operation where authorization's answer was not enough. Fixed by carrying the exclusions on
   `log` as well, with a control proving they suppress only the denied descendant.
9. **`cat-file -t` shipped unprobed.** Task 1 probed `cat-file blob`; the type check added in
   round 1 is a different subcommand, and this module's rule is about the invocation that ships.
   Probed: identical table.
10. **Pattern validation was both too strict and too loose.** An empty ERE is valid and matches
    every line — refused on a guess about intent. A lone high surrogate still could not cross
    argv. Now judged with `os.fsencode`, the same function `subprocess` uses, so
    surrogateescape-representable patterns are accepted exactly as git accepts them.
11. **The derived git guard parsed only `serve.py`**, so its own prescribed mutation — add
    `run_git` to `policy.py` — passed. The file the guard was written about was the one file it
    could not have been wrong about.
12. **The §7 policy bullet was claimed closed without its symlink regression.** Now tested:
    replacing a committed file with a working-tree symlink changes nothing, because the blob read
    never consults the working tree.

Findings 8 and 11 are the same shape as 1 and 4 — a check whose scope was narrower than the rule
it enforced. That is the failure mode this plan's own guards are most likely to repeat.

A third round found two more, both in the guards rather than the serving code:

13. **The subprocess guard was a text scan, so it rejected its own package's documentation.**
    `policy.py`'s docstring explains why a NUL cannot cross `subprocess`'s argv boundary, and the
    guard forbade the substring anywhere in any module — it would have failed on the first run
    against the code this plan tells the implementer to write. A guard that forbids *discussing*
    the hazard pushes the explanation out of the code, which inverts its purpose. Now an AST
    check on imports and calls, widened to `os`'s spawning family since `policy.py` now imports
    `os`.
14. **The history control could not distinguish precision from over-exclusion.** It queried
    `a.txt`, outside the ancestor, so dropping all of `private/` would have satisfied both tests.
    Measured: the over-broad spelling returns no commits at all. The control now lives *inside*
    the ancestor — two commits under `private/`, one touching the denied file and one an allowed
    sibling — and asserts the allowed commit still appears from the same query.

Finding 13 is worth keeping in view beyond this plan: a guard implemented as a text scan is a
guard whose scope is the whole file, including its prose.

A fourth round found one, in finding 13's own repair:

15. **The rewritten process-boundary guard was narrower than the claim it advertised.** It listed
    nine `os` spawn names and inspected attribute calls only on a receiver literally spelled `os`,
    so `os.spawnvp`, `os.spawnl`, `os.posix_spawnp`, `import os as o` then `o.system(...)`, and
    `from os import system` then `system(...)` all passed a guard whose docstring claimed no
    module in the package launches a process. Step 3 also certified it with no mutation at all,
    so nothing would have exposed the gap. It now matches the spawn *family* by prefix, ignores
    the receiver, rejects dynamic imports, and carries three mutation rows — two of which the
    roster version survives.

The lesson is finding 8 and 11's again, now for the third time, and the pattern is specific enough
to name: **every one of these was a check whose scope was narrower than the rule it enforced, and
in each case the narrowing was an enumeration** — one file rather than the package, one substring
rather than the concept, nine names rather than the family. Whenever a guard's scope is a list,
the guard has a hole exactly where the list ends. Prefer a predicate over a roster, and certify
with a mutation that lands *outside* the roster the previous draft would have caught.

## Global Constraints

- Work in the `feat/evidence-broker-serving` worktree at `.worktrees/evidence-broker-serving`, on
  branch `feat/evidence-broker-serving`. Verify with `git branch --show-current` before the first
  commit. Commits landing on `main` instead are the failure mode this constraint exists for.
- There is **no root `pyproject.toml`**. CLI/package work runs from `science/`; model work runs
  from `science/model/`. `cd` into the package directory before any `uv run`.
- Tests: `cd science && uv run --frozen pytest <paths>` and
  `cd science/model && uv run --frozen pytest <paths>`. **Never run the full suite** — it is ~12k
  tests and ~10 minutes, longer than the default command timeout. Run the specific test files this
  plan creates. Never run two suites concurrently in one worktree.
- Lint from the package you changed: `uv run ruff check`. Types: `uv run pyright` from `science/`
  (one repo-root `pyrightconfig.json` governs all three source trees; test directories are not
  type-checked).
- `line-length = 120` in both packages.
- Conventional commits. **No AI-attribution trailer or footer** on any commit.
- Composition over inheritance; explicit over defensive; fail early instead of silent fallbacks.
  No "legacy"/"compatibility" layers. No `Unified` prefix.
- Every guard is proven by **restoring the prior behaviour and confirming its test fails**. A
  guard nobody has watched fail is a guard nobody has tested. Where a task says "verify it fails",
  that step is not optional and its output goes in the commit message or the task report.
- All git invocations in production code go through `science_tool.autonomy.git.run_git`. A direct
  `subprocess.run(["git", ...])` in `src/` is a defect regardless of what it does — see Task 4's
  dispatch guard. Test *fixtures* may call git directly to build repositories.

---

## File Structure

| File | Responsibility |
|---|---|
| `science/model/src/science_model/evidence_broker.py` | **Create.** The broker's shared model vocabulary. This plan puts `SurfacePolicy` here; plan 3 adds `InstrumentIdentity`, `InlineInput`, `ExposureEntry`, `EvidenceExposure`. It must be a model module and not a tool module because plan 3 hangs `EvidenceExposure` on `AutonomousRunRecord` (`science_model/autonomous_runs.py`), and `science_model` cannot import `science_tool`. |
| `science/src/science_tool/evidence_broker/__init__.py` | **Create.** Package marker; no re-exports (callers import from the submodule that owns the name). |
| `science/src/science_tool/evidence_broker/policy.py` | **Create.** `EvidenceOp`, `EvidenceRequest`, `Denial`, `Authorization`, `authorize`, `exclude_pathspecs`, `literal_pathspec`. Decides *whether*, and owns the one normalized spelling every downstream caller must use. Never runs git. |
| `science/src/science_tool/evidence_broker/serve.py` | **Create.** `verify_commit`, `serve`, `ServeError`, the canonical argv, the defined-miss classifier. Decides *what bytes*; never decides policy. |
| `science/src/science_tool/autonomy/git.py` | **Modify** (Task 1, docstring only). Admit `cat-file` to the documented probe set. |
| `science/model/tests/test_evidence_broker_model.py` | **Create.** `SurfacePolicy` normalization and refusal. |
| `science/tests/test_evidence_broker_policy.py` | **Create.** Authorization, prefix boundaries, pathspec translation, and the read/search agreement table. |
| `science/tests/test_evidence_broker_serve.py` | **Create.** Each operation, defined misses, the commit-ordering regression, the directory refusal. |
| `science/tests/test_evidence_broker_canonical.py` | **Create.** Byte-equality across hostile repository configuration, locale replay, and the derived dispatch guard. |
| `science/tests/test_autonomy_git_canonical.py` | **Modify** (Task 1). `cat-file` is unaffected by filters, textconv and eol configuration. |

The split between `policy.py` and `serve.py` is the one the design's §7 depends on: it tests the
`read` denial and the `search` exclusion **against each other**, which is only possible when one
module answers both questions and no git call is involved in either.

---

## Task 1: Admit `cat-file` to `git.py`'s probe set

`autonomy/git.py` states a standing rule — *only what was shown to execute is neutralized* — and
documents the exact subcommands it probed. `read` now uses `cat-file blob`, which is not in that
list. Plan 1 gave `grep` this treatment before adding it; this task does the same for `cat-file`,
so the module's rule holds rather than being asserted.

**Files:**
- Modify: `science/src/science_tool/autonomy/git.py` (module docstring only — no code change)
- Test: `science/tests/test_autonomy_git_canonical.py` (append)

**Interfaces:**
- Consumes: `run_git(repo_root: Path, *args: str) -> subprocess.CompletedProcess[bytes]`
- Produces: nothing new. Task 3 relies on `cat-file blob` being safe under `run_git`; this task is
  what makes that true rather than assumed.

**Both `cat-file` invocations are probed, because production runs both.** `read` types the object
with `cat-file -t` and only then reads it with `cat-file blob` (Task 3), and this module's rule is
about the exact subcommand that ships, not about a subcommand that resembles it. The probe below
was run twice, once per spelling, and produced the identical table.

**The probe result, already measured** (git 2.55, scratch repository, under exactly
`git --no-replace-objects -c <key> -C <root> cat-file blob <commit>:a.txt` and again under
`… cat-file -t <commit>:a.txt`, with `.gitattributes` carrying `a.txt diff=probe filter=probe`
so the driver keys have a reason to fire, and a marker-touching `./spawn.sh` as every named
program):

| keys | verdict |
|---|---|
| `core.pager`, `pager.cat-file` | **INERT** |
| `diff.probe.textconv`, `diff.probe.command`, `diff.external` | **INERT** |
| `filter.probe.clean`, `filter.probe.smudge`, `filter.probe.process` | **INERT** |
| `core.fsmonitor`, `core.hooksPath` | **INERT** |
| `core.quotePath`, `core.autocrlf`, `core.eol` | **INERT** |
| `log.showSignature`, `gpg.program` | **INERT** |
| `core.sshCommand`, `core.alternateRefsCommand` | **INERT** |

Seventeen keys per spelling, nothing executes and nothing renders differently. `cat-file` is a raw
object read under both: no smudge filter, no textconv, no eol conversion, and no pager because
output is captured. **`_HARDENING` therefore gains nothing.** Adding a key here would assert a defense against
behaviour this command has been shown not to have, which is precisely what the module's rule
forbids.

- [ ] **Step 1: Write the failing test**

Append to `science/tests/test_autonomy_git_canonical.py`:

```python
def _filtered_repo(tmp_path: Path) -> tuple[Path, str, bytes]:
    """A repository whose configuration WOULD mangle a checkout, and its committed bytes."""
    root = tmp_path / "filtered"
    root.mkdir()
    for args in (
        ("init", "-q"),
        ("config", "user.email", "probe@example.invalid"),
        ("config", "user.name", "Probe"),
        ("config", "core.autocrlf", "true"),
        ("config", "filter.probe.smudge", "sed s/alpha/MANGLED/"),
        ("config", "filter.probe.clean", "cat"),
        ("config", "diff.probe.textconv", "sed s/alpha/MANGLED/"),
    ):
        subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)
    (root / ".gitattributes").write_text("a.txt diff=probe filter=probe\n", encoding="utf-8")
    committed = b"alpha\nbeta\n"
    (root / "a.txt").write_bytes(committed)
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(root), "commit", "-q", "-m", "seed"], check=True, capture_output=True
    )
    commit = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"], check=True, capture_output=True
    ).stdout.decode().strip()
    return root, commit, committed


def test_cat_file_blob_serves_the_object_not_a_filtered_checkout(tmp_path: Path):
    """`read` must serve what the commit holds, not what a checkout would produce.

    The repository configures a smudge filter, a textconv driver and `core.autocrlf`, all
    reachable through `.gitattributes` and all owned by the actor. `cat-file blob` is a raw
    object read, so none of them applies -- which is why `read` can be a pure function of the
    commit. The control below proves the configuration is genuinely live, so that INERT here
    means "this command ignores it" rather than "the fixture forgot to set it".
    """
    root, commit, committed = _filtered_repo(tmp_path)

    completed = run_git(root, "cat-file", "blob", f"{commit}:a.txt")

    assert completed.returncode == 0
    assert completed.stdout == committed
    assert completed.stderr == b""


def test_cat_file_type_is_unaffected_by_the_same_configuration(tmp_path: Path):
    """The other half of `read`. Production runs BOTH spellings, so both are held to the
    module's rule -- a probe of a subcommand that merely resembles the one that ships is
    not a probe of the one that ships."""
    root, commit, _committed = _filtered_repo(tmp_path)

    completed = run_git(root, "cat-file", "-t", f"{commit}:a.txt")

    assert completed.returncode == 0
    assert completed.stdout.strip() == b"blob"
    assert completed.stderr == b""


def test_the_filter_fixture_is_live(tmp_path: Path):
    """Negative control for the test above: a checkout DOES mangle, so INERT is a finding."""
    root, _commit, committed = _filtered_repo(tmp_path)
    subprocess.run(
        ["git", "-C", str(root), "checkout", "--", "a.txt"], check=True, capture_output=True
    )
    subprocess.run(
        ["git", "-C", str(root), "checkout-index", "-f", "--", "a.txt"],
        check=True,
        capture_output=True,
    )

    assert (root / "a.txt").read_bytes() != committed
```

- [ ] **Step 2: Run the tests to verify the first passes and the control passes**

```bash
cd science && uv run --frozen pytest tests/test_autonomy_git_canonical.py -v
```

Expected: both PASS. This is the unusual case where the implementation already satisfies the
test — the probe found nothing to fix. **If `test_the_filter_fixture_is_live` fails, stop**: the
fixture is not exercising the configuration, so the first test proves nothing. Fix the fixture
until the control fails to produce the committed bytes, then continue.

- [ ] **Step 3: Record the probe in `git.py`'s docstring**

In the `WHAT WAS PROBED, AND WHAT ACTUALLY EXECUTES` list, extend the probed-subcommand sentence
to include `cat-file blob <commit>:<path>`, and add this bullet after the `grep` INERT bullet:

```
* `cat-file -t <commit>:<path>` and `cat-file blob <commit>:<path>` -- probed separately,
  identical results. Every key probed is INERT: `core.pager`, `pager.cat-file`,
  `diff.<driver>.textconv`, `diff.<driver>.command`, `diff.external`, `filter.<driver>.clean`
  / `.smudge` / `.process`, `core.fsmonitor`, `core.hooksPath`, `core.quotePath`,
  `core.autocrlf`, `core.eol`, `log.showSignature`, `gpg.program`, `core.sshCommand`,
  `core.alternateRefsCommand` -- probed with `.gitattributes` binding the driver keys to the
  path, so each had a reason to fire. `cat-file blob` is a raw object read: it applies no
  smudge filter, no textconv and no eol conversion, and captured output means no pager. So
  `_HARDENING` gains NOTHING for this subcommand, per this module's standing rule.

  The broker uses this rather than `show <commit>:<path>` because `show` answers a path naming
  a TREE with a directory listing at exit 0, which the evidence broker cannot distinguish from
  a file read (design §3.2). `cat-file blob` refuses it.
```

- [ ] **Step 4: Lint, type-check, and re-run**

```bash
cd science && uv run ruff check && uv run pyright && uv run --frozen pytest tests/test_autonomy_git_canonical.py -q
```

Expected: clean, and tests pass.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/autonomy/git.py science/tests/test_autonomy_git_canonical.py
git commit -m "test(autonomy): probe cat-file before the broker adds it

The broker's read op is cat-file blob, a subcommand git.py had not probed.
Seventeen keys under .gitattributes bindings that give each a reason to fire:
all INERT. cat-file blob is a raw object read, so no smudge filter, textconv
or eol conversion applies and captured output means no pager. _HARDENING gains
nothing, per the module's rule that only what was shown to execute is
neutralized.

The paired control checks out the same path and asserts it IS mangled, so
INERT is a finding about the command rather than about the fixture."
```

---

## Task 2: `SurfacePolicy` and `evidence_broker/policy.py`

**Files:**
- Create: `science/model/src/science_model/evidence_broker.py`
- Create: `science/src/science_tool/evidence_broker/__init__.py`
- Create: `science/src/science_tool/evidence_broker/policy.py`
- Test: `science/model/tests/test_evidence_broker_model.py`
- Test: `science/tests/test_evidence_broker_policy.py`

**Interfaces:**
- Consumes: `science_model.audit.subjects.normalize_project_path(raw: str) -> str`, which raises
  `SubjectError` on `..`, absolute paths, NUL, and paths naming no file.
- Produces, for Task 3 and for plan 3:
  ```python
  # science_model/evidence_broker.py
  class SurfacePolicy(BaseModel):          # frozen, extra="forbid"
      deny_prefixes: tuple[str, ...] = ()
      notice: str

  # science_tool/evidence_broker/policy.py
  class EvidenceOp(StrEnum):
      READ = "read"; SEARCH = "search"; HISTORY = "history"

  @dataclass(frozen=True)
  class EvidenceRequest:
      op: EvidenceOp
      target: str                  # a path for READ/HISTORY; a PATTERN for SEARCH
      pathspec: str | None = None  # a path, for SEARCH only

  @dataclass(frozen=True)
  class Denial:
      reason: str      # categorised, parent-side, for the audit
      notice: str      # policy-supplied, what the requester sees

  @dataclass(frozen=True)
  class Authorization:
      denial: Denial | None      # None means: may be served
      path: str | None           # THE NORMALIZED PATH GIT MUST USE. None when the op names none.

  def authorize(request: EvidenceRequest, policy: SurfacePolicy) -> Authorization
  def exclude_pathspecs(policy: SurfacePolicy) -> tuple[str, ...]
  def literal_pathspec(path: str) -> str
  ```

**`authorize` returns the normalized path, and callers must use it.** An earlier draft returned
only `Denial | None` and discarded the normalized value, so `serve` passed the caller's *raw*
string to git. Measured, that is a policy bypass and a wrong-file read at once: `a\b` normalizes
to `a/b` and authorizes against that, while git reads a file literally named `a\b`; the
authorization and the read are then about two different paths. Normalizing twice would be no
better — one function must own the spelling, and the only way to enforce that is to make the
authorized spelling the thing it hands back.

- [ ] **Step 1: Write the failing model test**

`science/model/tests/test_evidence_broker_model.py`:

```python
from __future__ import annotations

import pytest
from pydantic import ValidationError

from science_model.evidence_broker import SurfacePolicy


def test_deny_prefixes_are_normalized_on_construction():
    policy = SurfacePolicy(deny_prefixes=("./notes//drafts", "a\\b"), notice="withheld")
    assert policy.deny_prefixes == ("notes/drafts", "a/b")


def test_a_traversal_prefix_is_refused_not_collapsed():
    with pytest.raises(ValidationError):
        SurfacePolicy(deny_prefixes=("notes/../secrets",), notice="withheld")


def test_an_absolute_prefix_is_refused():
    with pytest.raises(ValidationError):
        SurfacePolicy(deny_prefixes=("/etc/passwd",), notice="withheld")


def test_a_notice_is_required():
    """A policy that denies without telling the requester anything is a policy that
    cannot be honoured uniformly, which is the property a blinding study needs."""
    with pytest.raises(ValidationError):
        SurfacePolicy(deny_prefixes=("notes",))


def test_the_policy_is_frozen_and_forbids_extras():
    policy = SurfacePolicy(deny_prefixes=("notes",), notice="withheld")
    with pytest.raises(ValidationError):
        policy.deny_prefixes = ()
    with pytest.raises(ValidationError):
        SurfacePolicy(deny_prefixes=(), notice="withheld", budget=3)
```

- [ ] **Step 2: Run it to verify it fails**

```bash
cd science/model && uv run --frozen pytest tests/test_evidence_broker_model.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'science_model.evidence_broker'`.

- [ ] **Step 3: Write `science_model/evidence_broker.py`**

```python
"""The evidence broker's model vocabulary, shared by the baseline and the run record.

This is a MODEL module and not a tool module because `EvidenceExposure` (design §4.1) hangs on
`AutonomousRunRecord`, which lives here, and `science_model` cannot import `science_tool`. The
session-side types of §4.3 name the same classes, so one definition serves both sides of the
control plane.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, field_validator

from science_model.audit.subjects import SubjectError, normalize_project_path


class SurfacePolicy(BaseModel):
    """What the broker will not show, and what it says instead.

    DENY PREFIXES ARE A PARAMETER, NOT A CONSTANT. 2a guarantees only that a supplied policy is
    HONOURED. Proving a policy COMPLETE -- that it covers every artifact a study must withhold --
    stays the caller's obligation, and a default here would look like the toolkit had discharged
    it.

    `notice` is what the requester sees and is policy-supplied, because this toolkit's existing
    denials are deliberately informative -- a human triages them -- while a blinding study needs
    them uniform and information-free, since a specific reason confirms the denied thing exists.
    2a cannot decide which is correct for a caller, so it does not.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    deny_prefixes: tuple[str, ...] = ()
    notice: str

    @field_validator("deny_prefixes")
    @classmethod
    def _normalized(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        """Normalized HERE, so `authorize` compares two paths in one spelling.

        A prefix normalized at match time would be normalized once per request and could differ
        between serving and replay if the normalizer ever changed. Doing it on construction means
        the policy that reaches the baseline is already the policy that will be compared.
        """
        try:
            return tuple(normalize_project_path(raw) for raw in value)
        except SubjectError as exc:
            raise ValueError(f"deny prefix is not a project path: {exc}") from exc
```

- [ ] **Step 4: Run the model tests to verify they pass**

```bash
cd science/model && uv run --frozen pytest tests/test_evidence_broker_model.py -v
```

Expected: PASS (5 tests).

- [ ] **Step 5: Write the failing policy test**

`science/tests/test_evidence_broker_policy.py`:

```python
from __future__ import annotations

import pytest
from science_model.evidence_broker import SurfacePolicy

from science_tool.evidence_broker.policy import (
    EvidenceOp,
    EvidenceRequest,
    authorize,
    exclude_pathspecs,
    literal_pathspec,
)

POLICY = SurfacePolicy(deny_prefixes=("private", "notes/a[b].md"), notice="withheld by policy")


def _read(target: str) -> EvidenceRequest:
    return EvidenceRequest(op=EvidenceOp.READ, target=target)


def test_a_path_under_a_deny_prefix_is_refused():
    auth = authorize(_read("private/x.txt"), POLICY)
    assert auth.denial is not None
    assert auth.denial.notice == "withheld by policy"
    assert auth.denial.reason == "path-denied"
    assert auth.path is None


def test_the_prefix_itself_is_refused():
    assert authorize(_read("private"), POLICY).denial is not None


def test_a_prefix_denies_on_component_boundaries_only():
    """`private` must deny `private/x` and must NOT deny `privateer/x`. A bare
    `startswith` would deny both, and would silently withhold an unrelated tree."""
    assert authorize(_read("privateer/x.txt"), POLICY).denial is None


def test_containment_is_checked_before_any_prefix():
    """A prefix check alone is walked around with `..`, so traversal is refused first
    and is refused as MALFORMED rather than as denied -- the two are different facts and
    a requester that cannot tell them apart cannot correct its own input."""
    auth = authorize(_read("private/../public/x.txt"), POLICY)
    assert auth.denial is not None
    assert auth.denial.reason == "path-malformed"


def test_an_absolute_path_is_refused_lexically():
    auth = authorize(_read("/etc/passwd"), POLICY)
    assert auth.denial is not None
    assert auth.denial.reason == "path-malformed"


def test_an_undenied_path_is_authorized():
    assert authorize(_read("src/main.py"), POLICY).denial is None


def test_the_authorized_path_is_the_normalized_one():
    """The value the caller must hand to git. `a\\b` normalizes to `a/b`, and a caller
    that passed its own raw string would authorize one path and read another -- git
    reads a file literally named `a\\b`, which no prefix was ever compared against."""
    auth = authorize(_read("./docs//a\\b"), POLICY)
    assert auth.denial is None
    assert auth.path == "docs/a/b"


def test_a_search_carries_no_path_so_only_its_pathspec_is_judged():
    """SEARCH's target is a PATTERN. Judging it as a path would refuse legitimate
    patterns for containing `/` or `..`, and would say nothing about what git reads."""
    assert authorize(EvidenceRequest(op=EvidenceOp.SEARCH, target="../secret"), POLICY).denial is None
    denied = EvidenceRequest(op=EvidenceOp.SEARCH, target="x", pathspec="private/x.txt")
    assert authorize(denied, POLICY).denial is not None


@pytest.mark.parametrize("pattern", ["a\0b", "\ud800"])
def test_a_pattern_that_cannot_cross_argv_is_refused_not_passed_to_git(pattern: str):
    """Measured: a NUL raises `ValueError` inside `subprocess` and a lone high surrogate
    raises `UnicodeEncodeError`, a `ValueError` subclass. `run_git` turns either into
    `GitError`, halting the run over input §6 calls retryable."""
    auth = authorize(EvidenceRequest(op=EvidenceOp.SEARCH, target=pattern), POLICY)
    assert auth.denial is not None
    assert auth.denial.reason == "pattern-malformed"


def test_an_empty_pattern_is_authorized():
    """An empty ERE is VALID and matches every line -- measured, exit 0 with every file
    listed. Refusing it would deny a real query on a guess about the requester's intent,
    and whether a pattern compiles is git's answer to give."""
    assert authorize(EvidenceRequest(op=EvidenceOp.SEARCH, target=""), POLICY).denial is None


def test_a_surrogateescape_byte_pattern_is_authorized():
    """`\\udcff` round-trips through `os.fsencode` to a byte and git accepts it. Judging
    with strict UTF-8 instead would refuse a pattern the instrument can actually run --
    a check that looks stricter and is simply wrong."""
    assert authorize(EvidenceRequest(op=EvidenceOp.SEARCH, target="\udcff"), POLICY).denial is None


def test_history_is_judged_as_a_path():
    auth = authorize(EvidenceRequest(op=EvidenceOp.HISTORY, target="private/x.txt"), POLICY)
    assert auth.denial is not None


def test_a_glob_target_is_authorized_but_must_reach_git_literally():
    """MEASURED policy bypass: `priv*` is not under any deny prefix as text, and as a
    bare pathspec git expands it onto `private/x.txt`. `literal_pathspec` is what makes
    the authorized spelling and the searched spelling the same string."""
    assert authorize(EvidenceRequest(op=EvidenceOp.HISTORY, target="priv*"), POLICY).denial is None
    assert literal_pathspec("priv*") == ":(top,literal)priv*"


def test_exclusions_are_top_literal_and_exclude():
    assert exclude_pathspecs(POLICY) == (
        ":(top,literal,exclude)private",
        ":(top,literal,exclude)notes/a[b].md",
    )


def test_an_empty_policy_excludes_nothing():
    assert exclude_pathspecs(SurfacePolicy(notice="n")) == ()


# The agreement table. Two mechanisms for one policy is how a policy comes to be half
# enforced, so the READ denial and the SEARCH exclusion are asserted against each other on
# one set of inputs rather than each against its own expectations.
AGREEMENT = (
    ("private/x.txt", True),
    ("private", True),
    ("privateer/x.txt", False),
    ("notes/a[b].md", True),
    ("notes/ab.md", False),
    ("src/main.py", False),
)


@pytest.mark.parametrize("path,denied", AGREEMENT)
def test_read_denial_matches_the_table(path: str, denied: bool):
    assert (authorize(_read(path), POLICY).denial is not None) is denied
```

The other half of this table — that `git grep` under `exclude_pathspecs(POLICY)` withholds
exactly the same paths — needs a real repository and lands in Task 3, which owns the git call.
Leaving it here would mean testing `serve` from the policy module.

- [ ] **Step 6: Run it to verify it fails**

```bash
cd science && uv run --frozen pytest tests/test_evidence_broker_policy.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'science_tool.evidence_broker'`.

- [ ] **Step 7: Write the package marker and `policy.py`**

`science/src/science_tool/evidence_broker/__init__.py`:

```python
"""The evidence broker: what an agent was shown, served deterministically from a pinned commit."""
```

`science/src/science_tool/evidence_broker/policy.py`:

```python
"""Whether a request may be answered. Nothing here runs git.

Keeping the decision out of the serving module is what makes design §7's agreement table
possible: the `read` denial and the `search` exclusion are independent implementations of one
policy, and they can only be tested against each other while both are pure functions.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import StrEnum

from science_model.audit.subjects import SubjectError, normalize_project_path
from science_model.evidence_broker import SurfacePolicy


class EvidenceOp(StrEnum):
    READ = "read"
    SEARCH = "search"
    HISTORY = "history"


@dataclass(frozen=True)
class EvidenceRequest:
    """One question about the pinned tree.

    `target` is a PATH for `READ` and `HISTORY` and a PATTERN for `SEARCH`. Search is the one
    operation that never names a path, which is why its `pathspec` is separate and optional and
    why its target is never put through a path normalizer.
    """

    op: EvidenceOp
    target: str
    pathspec: str | None = None


@dataclass(frozen=True)
class Denial:
    """Two strings, for two audiences.

    `reason` is categorised and stays parent-side, for the audit. `notice` is what the requester
    sees and comes from the policy, never from this module: a specific reason confirms that the
    denied thing exists, which a blinding study cannot afford.
    """

    reason: str
    notice: str


@dataclass(frozen=True)
class Authorization:
    """The verdict AND the spelling git must use.

    Returning only a verdict is what let an earlier draft authorize one path and read another:
    `a\\b` normalizes to `a/b` and is judged as that, while git reads a file literally named
    `a\\b`. Handing the normalized value back makes the authorized spelling the only spelling
    available downstream, which is stronger than asking every caller to normalize again.
    """

    denial: Denial | None
    path: str | None = None


def _denied_by_prefix(path: str, prefix: str) -> bool:
    """Component-boundary matching. `private` denies `private` and `private/x`, not `privateer`."""
    return path == prefix or path.startswith(f"{prefix}/")


def _judge_path(raw: str, policy: SurfacePolicy) -> Authorization:
    try:
        path = normalize_project_path(raw)
    except SubjectError as exc:
        # Containment BEFORE any prefix: a prefix check alone is walked around with `..`.
        # Reported as malformed rather than denied because they are different facts -- one is
        # the requester's own error and correctable, the other is the study's boundary.
        return Authorization(denial=Denial(reason="path-malformed", notice=str(exc)))
    if any(_denied_by_prefix(path, prefix) for prefix in policy.deny_prefixes):
        return Authorization(denial=Denial(reason="path-denied", notice=policy.notice))
    return Authorization(denial=None, path=path)


def _judge_pattern(pattern: str) -> Authorization:
    """ARGV validity only, judged by the same function `subprocess` uses.

    Whether the regex compiles is git's answer to give, and an EMPTY pattern is NOT refused here:
    an empty ERE is valid and matches every line, which is a legitimate request measured to exit
    0 with every file listed. Refusing it would deny a real query on a guess about intent.

    What genuinely cannot cross the argv boundary halts the run instead of being refused, which
    is the wrong disposition for the requester's own input (§6 calls it retryable). Two cases,
    both measured: a NUL raises `ValueError`, and a lone high surrogate such as `\\ud800` raises
    `UnicodeEncodeError` -- a `ValueError` subclass, so `run_git` catches it and re-raises
    `GitError` either way.

    `os.fsencode` is the test rather than `str.encode("utf-8")` because it is exactly what
    `subprocess` applies on POSIX: it uses `surrogateescape`, so `\\udcff` round-trips to a byte
    and IS accepted by git. Encoding as strict UTF-8 would refuse that as well -- correct-looking,
    and wrong, because it would deny a pattern the instrument can actually run.
    """
    if "\0" in pattern:
        return Authorization(
            denial=Denial(
                reason="pattern-malformed", notice="search pattern contains a NUL character"
            )
        )
    try:
        os.fsencode(pattern)
    except (UnicodeEncodeError, ValueError) as exc:
        return Authorization(
            denial=Denial(reason="pattern-malformed", notice=f"search pattern is not encodable: {exc}")
        )
    return Authorization(denial=None)


def authorize(request: EvidenceRequest, policy: SurfacePolicy) -> Authorization:
    """Judge one request. Happens before any join, any pathspec build, and any git call.

    `Authorization.path` is populated for the operations that name a path and is `None` for a
    search, whose target is a pattern. A search's optional pathspec IS a path and is judged and
    normalized like any other.
    """
    if request.op is not EvidenceOp.SEARCH:
        return _judge_path(request.target, policy)
    pattern = _judge_pattern(request.target)
    if pattern.denial is not None:
        return pattern
    if request.pathspec is None:
        return Authorization(denial=None)
    return _judge_path(request.pathspec, policy)


def literal_pathspec(path: str) -> str:
    """A caller-supplied path as a pathspec git cannot expand.

    MEASURED against git 2.55: with a deny prefix `private`, the history target `priv*` is under
    no prefix as text and passes authorization -- and as a bare pathspec git expands it onto
    `private/x.txt`, so `log` and `grep` both report the denied tree. `:(literal)priv*` matches
    nothing. Without this, every deny prefix is walked around by a glob, which is the policy
    bypass `exclude_pathspecs` exists to prevent on the other side of the same call.
    """
    return f":(top,literal){path}"


def exclude_pathspecs(policy: SurfacePolicy) -> tuple[str, ...]:
    """The deny prefixes as pathspecs every search carries, whether or not one was supplied.

    `literal` disables wildmatch. Measured against git 2.55 (design §3.2), the bare `:(exclude)`
    spelling does not leak denied material -- git also tries a literal prefix match -- it
    OVER-excludes: `:(exclude)notes/a[b].md` also removes the innocent sibling `notes/ab.md`,
    which the policy never denied and which `read` serves without objection. The exclusion set
    would then be a function of glob syntax rather than of the policy text, and "I searched and
    found nothing" would go false for reasons invisible in the policy.

    `top` anchors to the repository root so the exclusion does not drift with the caller's own
    pathspec.
    """
    return tuple(f":(top,literal,exclude){prefix}" for prefix in policy.deny_prefixes)
```

- [ ] **Step 8: Run the policy tests to verify they pass**

```bash
cd science && uv run --frozen pytest tests/test_evidence_broker_policy.py -v
```

Expected: PASS (all, including the 6 parametrized table rows).

- [ ] **Step 9: Prove each guard can fail**

For each, restore the prior behaviour, confirm the named test fails, then restore:

| Change | Expected failure |
|---|---|
| `_denied_by_prefix` → `return path.startswith(prefix)` | `test_a_prefix_denies_on_component_boundaries_only` and the `privateer/x.txt` table row |
| `_judge_path` returns `Authorization(denial=None)` without `path` | `test_the_authorized_path_is_the_normalized_one` |
| `literal_pathspec` → `return path` | `test_a_glob_target_is_authorized_but_must_reach_git_literally` |
| `_judge_pattern` → `return Authorization(denial=None)` | both `..._cannot_cross_argv...` rows |
| `_judge_pattern` uses `pattern.encode("utf-8")` instead of `os.fsencode` | `test_a_surrogateescape_byte_pattern_is_authorized` |
| `_judge_pattern` refuses `not pattern` | `test_an_empty_pattern_is_authorized` |

Record the observed failures in the commit message.

- [ ] **Step 10: Lint, type-check, commit**

```bash
cd science/model && uv run ruff check
cd ../ && uv run ruff check && uv run pyright
git add science/model/src/science_model/evidence_broker.py \
        science/model/tests/test_evidence_broker_model.py \
        science/src/science_tool/evidence_broker/ \
        science/tests/test_evidence_broker_policy.py
git commit -m "feat(evidence-broker): surface policy and the authorization boundary

SurfacePolicy normalizes its deny prefixes on construction, so authorize
compares two paths in one spelling and the policy that reaches the baseline is
the policy that will be compared at replay. It lives in science_model because
plan 3 hangs EvidenceExposure on AutonomousRunRecord and the model cannot
import the tool.

authorize checks containment before any prefix, since a prefix check alone is
walked around with '..', and reports traversal as malformed rather than denied:
one is the requester's correctable error, the other is the study's boundary.
Prefixes match on component boundaries -- 'private' denies 'private/x' and not
'privateer/x'; a startswith spelling was confirmed to fail that test.

It returns the NORMALIZED path rather than a bare verdict. Discarding it let a
caller authorize one path and read another: 'a\\b' is judged as 'a/b' while git
reads a file literally named 'a\\b'.

literal_pathspec closes the matching bypass on the other side. Measured against
git 2.55, the history target 'priv*' is under no deny prefix as text and, as a
bare pathspec, git expands it onto private/x.txt; ':(literal)priv*' matches
nothing.

SEARCH's target is a pattern and is never judged as a path; only its optional
pathspec is. Argv validity of the pattern IS judged here -- a NUL would raise
ValueError inside subprocess and surface as GitError, halting the run over input
6 classifies as retryable."
```

---

## Task 3: `evidence_broker/serve.py`

**Files:**
- Create: `science/src/science_tool/evidence_broker/serve.py`
- Test: `science/tests/test_evidence_broker_serve.py`

**Interfaces:**
- Consumes: `run_git` (plan 1); `authorize`, `exclude_pathspecs`, `literal_pathspec`,
  `EvidenceOp`, `EvidenceRequest`, `Authorization`, `Denial` (Task 2); `SurfacePolicy`.

**`authorize` runs before any git call, including `verify_commit`.** An earlier draft verified
first and then authorized, while claiming in the same docstring that a refused request never
reaches git. Both cannot be true. The contract this task implements and tests is the one the
design's threat model wants: **a denied request produces no git invocation at all**, so a
withheld path leaves no trace in a process table, a trace log, or a timing difference. The
`0`×40 regression still holds, because an *authorized* request reaches `verify_commit` before
anything is classified.
- Produces, for plan 3's `session.py`:
  ```python
  class ServeError(RuntimeError): ...

  class Outcome(StrEnum):
      SERVED = "served"
      MISS_ABSENT = "miss-absent"        # read: the path is not at the commit
      MISS_NO_MATCH = "miss-no-match"    # search: the pattern did not appear
      MISS_NO_COMMITS = "miss-no-commits"  # history: the query returned no commits
      REFUSED = "refused"                # policy denial or malformed pattern

  @dataclass(frozen=True)
  class Served:
      outcome: Outcome
      payload: bytes            # the served bytes, marker included; b"" when REFUSED
      denial: Denial | None = None

  def verify_commit(repo_root: Path, commit: str) -> str
  def serve(repo_root: Path, commit: str, request: EvidenceRequest, policy: SurfacePolicy) -> Served
  ```

**Measured git behaviour this task encodes** (git 2.55; every string below was observed, not
inferred):

| situation | exit | output |
|---|---|---|
| `cat-file -t <c>:<directory>` | 0 | `tree` |
| `cat-file -t <c>:<file>` | 0 | `blob` |
| `cat-file blob <c>:<absent, not on disk>` | 128 | `fatal: path 'x' does not exist in '<c>'` |
| `cat-file blob <c>:<absent, present on disk>` | 128 | `fatal: path 'x' exists on disk, but not in '<c>'` |
| `cat-file blob <c>:<directory>` | 128 | `fatal: git cat-file <c>:<path>: bad file` |
| `cat-file blob <c>:<empty file>` | 0 | zero bytes — **distinguishable from absent** |
| `grep … -e <pattern> <c>` with hits | 0 | `<c>:<path>\0<line>\0<text>\n` per hit |
| `grep … -e <pattern> <c>` no hits | 1 | empty |
| `grep … -e 'a[' <c>` | 128 | `fatal: -e option, 'a[': Invalid regular expression` |
| `log … <c> -- <path with no commits>` | 0 | empty |
| any op against `0`×40 | 128 | varies; `rev-parse --verify` gives `fatal: Needed a single revision` |

**The `0`×40 trap.** `cat-file blob 000…0:a.txt` reports `path 'a.txt' exists on disk, but not in
'000…0'` — the *miss* message. A miss classifier that runs before the commit is verified
therefore answers "absent at commit" for an entirely bogus revision, and every later request in
that session answers the same way. `verify_commit` first is what makes classification sound, and
§7 names this as the regression test precisely because `"0" * 40` would let a broken
implementation pass.

**Miss classification is anchored, not substring-matched.** An earlier draft asked whether
`does not exist in` appeared anywhere in stderr. Measured on git 2.55, a committed **directory
named `does not exist in`** yields
`fatal: git cat-file <c>:does not exist in: bad file` — which contains that substring, so a tree
would have been served as a defined miss and the reviewer told the path was absent when it was
present. The classifier therefore does two structured things instead: it asks `cat-file -t` for
the object type, which answers `tree` at exit 0 and removes the "bad file" case entirely, and it
compares stderr against the **fully interpolated sentences** git emits for the path and commit
in hand. Neither can be spoofed by a filename, because a filename cannot make the whole sentence
match while naming a different path.

- [ ] **Step 1: Write the failing test**

`science/tests/test_evidence_broker_serve.py`:

```python
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from science_model.evidence_broker import SurfacePolicy

from science_tool.evidence_broker.policy import EvidenceOp, EvidenceRequest
from science_tool.evidence_broker.serve import Outcome, ServeError, serve, verify_commit

OPEN = SurfacePolicy(notice="withheld")
CLOSED = SurfacePolicy(deny_prefixes=("private", "notes/a[b].md"), notice="withheld")
ZERO = "0" * 40


def _repo(tmp_path: Path) -> tuple[Path, str]:
    root = tmp_path / "repo"
    (root / "private").mkdir(parents=True)
    (root / "privateer").mkdir()
    (root / "notes").mkdir()
    for args in (
        ("init", "-q"),
        ("config", "user.email", "p@example.invalid"),
        ("config", "user.name", "P"),
    ):
        subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)
    (root / "a.txt").write_text("alpha\nbeta\n", encoding="utf-8")
    (root / "empty.txt").write_text("", encoding="utf-8")
    (root / "private" / "x.txt").write_text("secret\n", encoding="utf-8")
    (root / "privateer" / "p.txt").write_text("secret\n", encoding="utf-8")
    (root / "notes" / "a[b].md").write_text("secret\n", encoding="utf-8")
    (root / "notes" / "ab.md").write_text("secret\n", encoding="utf-8")
    # A directory whose NAME is git's own miss sentence, so a substring classifier reports
    # it absent. It is committed, so `cat-file -t` must answer `tree`.
    (root / "does not exist in").mkdir()
    (root / "does not exist in" / "f.txt").write_text("present\n", encoding="utf-8")
    # A file whose name contains a literal backslash, with NOTHING at `a/b`. The two
    # spellings therefore read different things, which is what makes the normalization
    # test below able to fail.
    (root / "a\\b").write_text("raw\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(root), "commit", "-q", "-m", "seed"], check=True, capture_output=True
    )
    commit = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"], check=True, capture_output=True
    ).stdout.decode().strip()
    return root, commit


def _read(target: str) -> EvidenceRequest:
    return EvidenceRequest(op=EvidenceOp.READ, target=target)


def _search(pattern: str, pathspec: str | None = None) -> EvidenceRequest:
    return EvidenceRequest(op=EvidenceOp.SEARCH, target=pattern, pathspec=pathspec)


def test_read_serves_the_blob(tmp_path: Path):
    root, commit = _repo(tmp_path)
    served = serve(root, commit, _read("a.txt"), OPEN)
    assert served.outcome is Outcome.SERVED
    assert served.payload == b"alpha\nbeta\n"


def test_an_empty_file_is_served_not_missed(tmp_path: Path):
    """"Shipped as a stub" is a different fact from "never shipped", and a reviewer that
    cannot tell them apart will report the wrong one."""
    root, commit = _repo(tmp_path)
    served = serve(root, commit, _read("empty.txt"), OPEN)
    assert served.outcome is Outcome.SERVED
    assert served.payload == b""


def test_an_absent_path_is_a_defined_miss(tmp_path: Path):
    root, commit = _repo(tmp_path)
    served = serve(root, commit, _read("nope.txt"), OPEN)
    assert served.outcome is Outcome.MISS_ABSENT
    assert served.payload  # the marker, so the hash covers the answer


def test_an_absent_path_that_exists_on_disk_is_the_same_miss(tmp_path: Path):
    """git spells this miss two ways depending on the working tree, which the actor owns.
    A classifier that knows only one turns an ordinary absent path into a halted run for
    exactly the paths the actor happened to create."""
    root, commit = _repo(tmp_path)
    (root / "later.txt").write_text("added after the commit\n", encoding="utf-8")
    served = serve(root, commit, _read("later.txt"), OPEN)
    assert served.outcome is Outcome.MISS_ABSENT


def test_read_refuses_a_directory(tmp_path: Path):
    """`git show <commit>:<dir>` answers this with a tree listing at exit 0. Served that
    way it would record FULL coverage over a directory listing, and a citation into it
    would correspond while resting on no file at all."""
    root, commit = _repo(tmp_path)
    # OPEN, deliberately: under CLOSED this path is refused by policy and the tree would
    # never be reached, so the test would pass without proving anything about `read`.
    with pytest.raises(ServeError):
        serve(root, commit, _read("private"), OPEN)


def test_a_directory_named_like_the_miss_message_is_not_a_miss(tmp_path: Path):
    """MEASURED: `cat-file blob <c>:does not exist in` fails with
    `fatal: git cat-file <c>:does not exist in: bad file`, which CONTAINS git's miss
    sentence. A substring classifier serves a present directory as an absent path, and
    tells the reviewer a file is missing when it is there."""
    root, commit = _repo(tmp_path)
    with pytest.raises(ServeError):
        serve(root, commit, _read("does not exist in"), OPEN)


def test_a_denied_read_makes_no_git_call_at_all(tmp_path: Path, monkeypatch):
    """Not merely "is refused": a withheld path must leave no trace in a process table or
    a timing difference, so `authorize` runs before `verify_commit` and before anything
    else. `run_git` is replaced with a landmine rather than observed after the fact."""
    root, commit = _repo(tmp_path)
    import science_tool.evidence_broker.serve as serve_module

    def _landmine(*args, **kwargs):
        raise AssertionError(f"a denied request reached git: {args}")

    monkeypatch.setattr(serve_module, "run_git", _landmine)
    served = serve(root, commit, _read("private/x.txt"), CLOSED)

    assert served.outcome is Outcome.REFUSED
    assert served.denial is not None
    assert served.payload == b""


def test_a_history_glob_cannot_walk_around_a_deny_prefix(tmp_path: Path):
    """MEASURED policy bypass: `priv*` is under no deny prefix as text, and as a bare
    pathspec git expands it onto `private/x.txt`. The literal pathspec is what keeps the
    authorized spelling and the searched spelling the same string."""
    root, commit = _repo(tmp_path)
    served = serve(root, commit, EvidenceRequest(op=EvidenceOp.HISTORY, target="priv*"), CLOSED)
    assert served.outcome is Outcome.MISS_NO_COMMITS


def test_a_search_pathspec_glob_cannot_walk_around_a_deny_prefix(tmp_path: Path):
    root, commit = _repo(tmp_path)
    served = serve(root, commit, _search("secret", pathspec="priv*"), CLOSED)
    assert served.outcome is Outcome.MISS_NO_MATCH


FILE_DENY = SurfacePolicy(deny_prefixes=("private/x.txt",), notice="withheld")


def _repo_with_split_history(tmp_path: Path) -> tuple[Path, str, str]:
    """Two commits under ONE ancestor: one touching a denied file, one touching an allowed
    sibling. Returns `(root, allowed_commit, denied_commit)`; the denied one is HEAD.

    Both descendants live under `private/`, which is the whole point. A control that asked
    about a path OUTSIDE the ancestor cannot tell a precise exclusion from one that dropped
    the entire subtree -- both answer the same way -- so it would pass against the
    over-broad fix as readily as the correct one.
    """
    root = tmp_path / "split"
    (root / "private").mkdir(parents=True)
    for args in (
        ("init", "-q"),
        ("config", "user.email", "p@example.invalid"),
        ("config", "user.name", "P"),
    ):
        subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)

    def _commit(message: str) -> str:
        subprocess.run(["git", "-C", str(root), "add", "-A"], check=True, capture_output=True)
        subprocess.run(
            ["git", "-C", str(root), "commit", "-q", "-m", message], check=True, capture_output=True
        )
        return subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"], check=True, capture_output=True
        ).stdout.decode().strip()

    (root / "private" / "public.txt").write_text("allowed\n", encoding="utf-8")
    allowed = _commit("touch the allowed sibling")
    (root / "private" / "x.txt").write_text("secret\n", encoding="utf-8")
    denied = _commit("touch the denied descendant")
    return root, allowed, denied


def test_history_of_an_ancestor_does_not_report_a_denied_descendant(tmp_path: Path):
    """MEASURED: with deny prefix `private/x.txt`, the target `private` is beneath no
    prefix and authorizes -- `read` refuses it as a tree, but `log` selects paths
    RECURSIVELY, so `:(top,literal)private` reports every commit touching the denied file.

    Authorization answers "is this path denied". It cannot answer "does this path CONTAIN
    something denied", so `log` carries the exclusions exactly as `grep` does.
    """
    root, _allowed, denied = _repo_with_split_history(tmp_path)
    served = serve(
        root, denied, EvidenceRequest(op=EvidenceOp.HISTORY, target="private"), FILE_DENY
    )
    assert denied.encode() not in served.payload


def test_the_history_exclusions_withhold_only_the_denied_descendant(tmp_path: Path):
    """The control, and it must live INSIDE the ancestor. Dropping all of `private` would
    satisfy the test above just as well, so precision is what this asserts: the allowed
    sibling's commit is still reported, from the same query."""
    root, allowed, denied = _repo_with_split_history(tmp_path)
    served = serve(
        root, denied, EvidenceRequest(op=EvidenceOp.HISTORY, target="private"), FILE_DENY
    )
    assert served.outcome is Outcome.SERVED
    assert allowed.encode() in served.payload


def test_a_working_tree_symlink_does_not_redirect_or_deny_a_read(tmp_path: Path):
    """§7's policy bullet. The served surface is a blob read at a pinned commit, which
    never consults the working tree -- so replacing a committed file with a symlink must
    change nothing. A `resolve()`-based containment check would have denied this request,
    and would have bought no security doing so: there is no filesystem lookup to protect.
    """
    root, commit = _repo(tmp_path)
    outside = tmp_path / "outside.txt"
    outside.write_text("not the committed bytes\n", encoding="utf-8")
    (root / "a.txt").unlink()
    (root / "a.txt").symlink_to(outside)

    served = serve(root, commit, _read("a.txt"), OPEN)

    assert served.outcome is Outcome.SERVED
    assert served.payload == b"alpha\nbeta\n"


def test_the_normalized_path_is_what_git_reads(tmp_path: Path):
    """`a\\b` normalizes to `a/b`, and the fixture commits a file at the FORMER and nothing
    at the latter. So the two spellings read different things, and the outcome says which
    one `serve` used: a request judged as `a/b` must miss, while a caller passing its own
    raw string would be served `raw\\n` -- authorizing one path and reading another.

    A gentler spelling such as `.//a.txt` proves nothing here: git resolves it to `a.txt`
    itself, so both the raw and the normalized form succeed and the test cannot fail.
    """
    root, commit = _repo(tmp_path)
    served = serve(root, commit, _read("a\\b"), OPEN)
    assert served.outcome is Outcome.MISS_ABSENT
    assert served.payload != b"raw\n"


def test_search_hits_carry_commit_path_and_line(tmp_path: Path):
    root, commit = _repo(tmp_path)
    served = serve(root, commit, _search("alpha"), OPEN)
    assert served.outcome is Outcome.SERVED
    assert served.payload == f"{commit}:a.txt".encode() + b"\x001\x00alpha\n"


def test_a_search_with_no_matches_is_a_defined_miss(tmp_path: Path):
    root, commit = _repo(tmp_path)
    served = serve(root, commit, _search("zzzznope"), OPEN)
    assert served.outcome is Outcome.MISS_NO_MATCH


def test_a_malformed_pattern_is_refused_not_raised(tmp_path: Path):
    """The requester's own input, carrying no repository fact. Raising would halt an
    honest run over a typo."""
    root, commit = _repo(tmp_path)
    served = serve(root, commit, _search("a["), OPEN)
    assert served.outcome is Outcome.REFUSED
    assert served.denial is not None
    assert served.denial.reason == "pattern-malformed"


def test_search_carries_the_policy_exclusions_even_with_no_pathspec(tmp_path: Path):
    """Search never names a path, so denying a directory to `read` while grep returns
    hits from inside it denies nothing."""
    root, commit = _repo(tmp_path)
    served = serve(root, commit, _search("secret"), CLOSED)
    assert served.outcome is Outcome.SERVED
    assert b"private/x.txt" not in served.payload
    assert b"notes/a[b].md" not in served.payload
    assert b"privateer/p.txt" in served.payload
    assert b"notes/ab.md" in served.payload


def test_history_serves_commits(tmp_path: Path):
    root, commit = _repo(tmp_path)
    served = serve(root, commit, EvidenceRequest(op=EvidenceOp.HISTORY, target="a.txt"), OPEN)
    assert served.outcome is Outcome.SERVED
    assert served.payload.startswith(commit.encode())


def test_history_with_no_commits_is_a_defined_miss(tmp_path: Path):
    root, commit = _repo(tmp_path)
    served = serve(
        root, commit, EvidenceRequest(op=EvidenceOp.HISTORY, target="nope.txt"), OPEN
    )
    assert served.outcome is Outcome.MISS_NO_COMMITS


def test_a_wellformed_nonexistent_commit_halts_rather_than_answering(tmp_path: Path):
    """THE regression test. `0`*40 makes git emit the MISS message, so an implementation
    that classifies before verifying answers "absent at commit" for a bogus revision --
    and passes a test written with a malformed ref instead."""
    root, _commit = _repo(tmp_path)
    with pytest.raises(ServeError):
        verify_commit(root, ZERO)
    with pytest.raises(ServeError):
        serve(root, ZERO, _read("a.txt"), OPEN)


def test_unrecognised_git_output_raises(tmp_path: Path, monkeypatch):
    """Anything git reports that is not a defined miss halts the run. A broker that
    guessed would turn an instrument failure into evidence.

    THE EARLIER FAKE FAILED EVERY CALL, so `verify_commit` raised and the read
    classifier was never reached -- the test passed without exercising the code it
    names. This one answers the verification truthfully and only then goes strange.
    """
    root, commit = _repo(tmp_path)
    import science_tool.evidence_broker.serve as serve_module

    real_run_git = serve_module.run_git
    calls: list[tuple] = []

    def _fake(repo_root, *args, **kwargs):
        calls.append(args)
        if args[0] == "rev-parse":
            return real_run_git(repo_root, *args, **kwargs)

        class _Strange:
            returncode = 128
            stdout = b""
            stderr = b"fatal: something nobody has seen before\n"

        return _Strange()

    monkeypatch.setattr(serve_module, "run_git", _fake)
    with pytest.raises(ServeError, match="could not be classified"):
        serve(root, commit, _read("a.txt"), OPEN)

    # The verification really did run, so the raise came from the read classifier.
    assert calls[0][0] == "rev-parse"
    assert len(calls) > 1
```

- [ ] **Step 2: Run it to verify it fails**

```bash
cd science && uv run --frozen pytest tests/test_evidence_broker_serve.py -v
```

Expected: FAIL — `ImportError: cannot import name 'Outcome' from 'science_tool.evidence_broker.serve'`.

- [ ] **Step 3: Write `serve.py`**

```python
"""What bytes a request is answered with. Policy is decided elsewhere.

Determinism is the whole product: two honest replays of one request against one commit must
produce identical bytes, because §5.3 refuses a review on disagreement. That needs three things
at once -- the commit pin, the canonical argv below, and the environment `run_git` pins -- and
losing any one of them silently converts an honest run into a refused one.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from science_model.evidence_broker import SurfacePolicy

from science_tool.autonomy.git import run_git
from science_tool.evidence_broker.policy import (
    Denial,
    EvidenceOp,
    EvidenceRequest,
    authorize,
    exclude_pathspecs,
    literal_pathspec,
)


class ServeError(RuntimeError):
    """git said something this module has not been shown how to read.

    Halts the run. A broker that guessed at unfamiliar output would turn an instrument failure
    into evidence, which is the one thing a record of what an agent was shown may not do.
    """


class Outcome(StrEnum):
    SERVED = "served"
    MISS_ABSENT = "miss-absent"
    MISS_NO_MATCH = "miss-no-match"
    MISS_NO_COMMITS = "miss-no-commits"
    REFUSED = "refused"


#: Defined-miss markers. They are part of the served bytes so the hash covers the ANSWER and not
#: merely its absence, and they are fixed strings because replay compares bytes.
MISS_MARKERS: dict[Outcome, bytes] = {
    Outcome.MISS_ABSENT: b"science-evidence: path absent at commit\n",
    Outcome.MISS_NO_MATCH: b"science-evidence: pattern matched nothing\n",
    Outcome.MISS_NO_COMMITS: b"science-evidence: no commits for this query\n",
}

def _absent_sentences(commit: str, path: str) -> tuple[bytes, ...]:
    """The two spellings git gives one fact, FULLY INTERPOLATED.

    Which one appears depends on whether the path is in the working tree, which the actor owns,
    so both must classify the same way. They are built with the path and commit in hand and
    compared whole, rather than searched for as substrings: a committed directory named
    `does not exist in` makes `cat-file blob` fail with
    `fatal: git cat-file <c>:does not exist in: bad file`, which CONTAINS the shorter marker.
    A substring test therefore serves a present tree as an absent path -- measured, git 2.55.
    A filename cannot make the whole sentence match while naming a different path.
    """
    return (
        f"fatal: path '{path}' does not exist in '{commit}'".encode(),
        f"fatal: path '{path}' exists on disk, but not in '{commit}'".encode(),
    )

#: `grep` renders through config unless argv says otherwise; `-E` is passed explicitly so
#: `grep.patternType` cannot decide what the caller's pattern MEANS.
_GREP_ARGV: tuple[str, ...] = (
    "grep",
    "-n",
    "-z",
    "-E",
    "--no-color",
    "--no-column",
    "--no-recurse-submodules",
)

#: `log.showSignature=false` is already in `run_git`'s `_HARDENING` -- it EXECUTES, so it is
#: neutralized there rather than pinned here. What argv owns is rendering.
_LOG_ARGV: tuple[str, ...] = (
    "log",
    "--pretty=format:%H %aI",
    "--no-decorate",
    "--no-notes",
    "--no-abbrev-commit",
)


@dataclass(frozen=True)
class Served:
    outcome: Outcome
    payload: bytes
    denial: Denial | None = None


def _miss(outcome: Outcome) -> Served:
    return Served(outcome=outcome, payload=MISS_MARKERS[outcome])


def verify_commit(repo_root: Path, commit: str) -> str:
    """Resolve `commit` to a full object name, or halt.

    RUNS ONCE BEFORE ANY REQUEST, and the ordering is load-bearing. For a well-formed but
    nonexistent commit git reports `path 'x' exists on disk, but not in '<commit>'` -- the same
    sentence it emits for a path added after the pinned commit. Miss classification is sound only
    once the revision is known good, so a broker that verified lazily would answer "absent at
    commit" for every path in a bogus revision.
    """
    completed = run_git(repo_root, "rev-parse", "--verify", "--end-of-options", f"{commit}^{{commit}}")
    if completed.returncode != 0:
        raise ServeError(
            f"{commit!r} does not name a commit in {repo_root}: "
            f"{completed.stderr.decode('utf-8', 'replace').strip()}"
        )
    return completed.stdout.decode("utf-8").strip()


def _serve_read(repo_root: Path, commit: str, target: str) -> Served:
    """Object TYPE first, then the blob. Two calls, because one cannot answer both questions.

    Asking `cat-file blob` alone conflates "not there" with "there but not a file": both exit
    128, and the tree's error text embeds git's own miss sentence. `-t` answers `tree` at exit 0,
    which removes the ambiguous case entirely rather than parsing around it.
    """
    typed = run_git(repo_root, "cat-file", "-t", f"{commit}:{target}")
    if typed.returncode != 0:
        if typed.stderr.strip() in _absent_sentences(commit, target):
            return _miss(Outcome.MISS_ABSENT)
        raise ServeError(
            f"read of {target!r} at {commit} could not be classified: "
            f"{typed.stderr.decode('utf-8', 'replace').strip()}"
        )
    kind = typed.stdout.strip()
    if kind != b"blob":
        # A tree, or a submodule's commit. The path IS at the commit; it simply is not a file,
        # and `git show` would answer it with a directory listing at exit 0 -- FULL coverage
        # over a listing nobody can cite honestly.
        raise ServeError(
            f"read of {target!r} at {commit} names a {kind.decode('ascii', 'replace')}, not a file"
        )
    completed = run_git(repo_root, "cat-file", "blob", f"{commit}:{target}")
    if completed.returncode != 0:
        raise ServeError(
            f"read of {target!r} at {commit} typed as a blob and then failed: "
            f"{completed.stderr.decode('utf-8', 'replace').strip()}"
        )
    return Served(outcome=Outcome.SERVED, payload=completed.stdout)


def _serve_search(
    repo_root: Path, commit: str, pattern: str, policy: SurfacePolicy, pathspec: str | None
) -> Served:
    # A PATTERN, not a request: the helper is given the two values it may use, so there is no
    # `request.target` in reach for it to mistake for a path.
    #
    # `literal_pathspec` on the caller's own path, for the same reason the exclusions carry it:
    # a bare `priv*` is under no deny prefix as text and expands onto `private/x.txt`.
    pathspecs = [*exclude_pathspecs(policy)]
    if pathspec is not None:
        pathspecs.insert(0, literal_pathspec(pathspec))
    completed = run_git(repo_root, *_GREP_ARGV, "-e", pattern, commit, "--", *pathspecs)
    if completed.returncode == 0:
        return Served(outcome=Outcome.SERVED, payload=completed.stdout)
    if completed.returncode == 1:
        return _miss(Outcome.MISS_NO_MATCH)
    stderr = completed.stderr
    if b"Invalid regular expression" in stderr or b"-e option" in stderr:
        # The requester's own input. It carries no repository fact, so it is retryable rather
        # than an instrument failure -- halting an honest run over a typo would be worse.
        return Served(
            outcome=Outcome.REFUSED,
            payload=b"",
            denial=Denial(
                reason="pattern-malformed",
                notice=stderr.decode("utf-8", "replace").strip(),
            ),
        )
    raise ServeError(
        f"search for {pattern!r} at {commit} could not be classified: "
        f"{stderr.decode('utf-8', 'replace').strip()}"
    )


def _serve_history(
    repo_root: Path, commit: str, target: str, policy: SurfacePolicy
) -> Served:
    """The exclusions ride on `log` too, for a reason `read` does not have.

    A deny prefix may name a FILE, and `log` selects a path RECURSIVELY. With deny prefix
    `private/x.txt`, the target `private` is beneath no prefix and authorizes -- `read` refuses it
    as a tree, but `:(top,literal)private` makes `log` report every commit touching
    `private/x.txt`. Measured on git 2.55. The authorization check answers "is this path denied";
    it cannot answer "does this path CONTAIN something denied", so the exclusions must answer
    that here, exactly as they do for `search`.
    """
    completed = run_git(
        repo_root,
        *_LOG_ARGV,
        commit,
        "--",
        literal_pathspec(target),
        *exclude_pathspecs(policy),
    )
    if completed.returncode != 0:
        raise ServeError(
            f"history of {target!r} at {commit} could not be classified: "
            f"{completed.stderr.decode('utf-8', 'replace').strip()}"
        )
    if not completed.stdout:
        return _miss(Outcome.MISS_NO_COMMITS)
    return Served(outcome=Outcome.SERVED, payload=completed.stdout)


def serve(
    repo_root: Path, commit: str, request: EvidenceRequest, policy: SurfacePolicy
) -> Served:
    """Answer one request at a pinned commit, or refuse it, or halt.

    ORDER: authorize, then verify, then dispatch. `authorize` comes first so a denied request
    produces NO git invocation at all -- a withheld path must leave no trace in a process table
    and no timing difference, and a refusal that had already spawned a process would be a
    refusal only in the return value. `verify_commit` comes second because miss classification
    is unsound against an unverified revision (see its docstring), and every path below
    classifies.

    THE AUTHORIZED SPELLING IS THE ONLY SPELLING USED BELOW. `request.target` is not read again
    for the operations that name a path: `auth.path` is the normalized value the policy was
    actually compared against, and using the raw one would authorize one path and read another.
    """
    auth = authorize(request, policy)
    if auth.denial is not None:
        return Served(outcome=Outcome.REFUSED, payload=b"", denial=auth.denial)
    resolved = verify_commit(repo_root, commit)
    if request.op is EvidenceOp.READ:
        assert auth.path is not None  # a READ that authorized always carries its path
        return _serve_read(repo_root, resolved, auth.path)
    if request.op is EvidenceOp.SEARCH:
        return _serve_search(repo_root, resolved, request.target, policy, auth.path)
    assert auth.path is not None  # likewise for HISTORY
    return _serve_history(repo_root, resolved, auth.path, policy)
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
cd science && uv run --frozen pytest tests/test_evidence_broker_serve.py -v
```

Expected: PASS (14 tests).

- [ ] **Step 5: Prove every load-bearing guard can fail**

These are guards the design says have looked right on the page before. For each, restore the
prior behaviour, confirm the named test fails, then restore:

| Change | Expected failure |
|---|---|
| Delete the `verify_commit` call from `serve` | `test_a_wellformed_nonexistent_commit_halts_rather_than_answering` reports `MISS_ABSENT` instead of raising |
| Drop the second sentence from `_absent_sentences` | `test_an_absent_path_that_exists_on_disk_is_the_same_miss` raises `ServeError` |
| Replace `_absent_sentences` matching with `b"does not exist in" in stderr` | `test_a_directory_named_like_the_miss_message_is_not_a_miss` returns `MISS_ABSENT` |
| Skip the `cat-file -t` call and classify from `cat-file blob` alone | the same directory test |
| `_serve_history` passes `target` instead of `literal_pathspec(target)` | `test_a_history_glob_cannot_walk_around_a_deny_prefix` serves the denied commit |
| `_serve_search` inserts `pathspec` instead of `literal_pathspec(pathspec)` | `test_a_search_pathspec_glob_cannot_walk_around_a_deny_prefix` |
| `serve` passes `request.target` instead of `auth.path` | `test_the_normalized_path_is_what_git_reads` |
| `_serve_history` drops `*exclude_pathspecs(policy)` | `test_history_of_an_ancestor_does_not_report_a_denied_descendant` |
| `_serve_history` excludes the ancestor wholesale (`":(top,literal,exclude)" + target`) | `test_the_history_exclusions_withhold_only_the_denied_descendant` — measured: the over-broad spelling returns no commits at all, so only a control INSIDE the ancestor can tell it from the correct fix |
| `_serve_read` uses `path.resolve()`-style containment before reading | `test_a_working_tree_symlink_does_not_redirect_or_deny_a_read` |
| Move `verify_commit` back above the `authorize` branch | `test_a_denied_read_makes_no_git_call_at_all` trips the landmine |

**Do not skip the last row.** Verifying ahead of authorizing is the ordering the first draft of
this plan had, and it passed every other test in the file — including one *named*
`..._without_reaching_git`, which asserted the outcome and never checked the claim in its own
name.

Record the observed failures in the commit message.

- [ ] **Step 6: Lint, type-check, commit**

```bash
cd science && uv run ruff check && uv run pyright
git add science/src/science_tool/evidence_broker/serve.py \
        science/tests/test_evidence_broker_serve.py
git commit -m "feat(evidence-broker): serve read, search and history at a pinned commit

verify_commit runs before anything is classified. Against 0*40 git emits the
MISS message, so a lazy implementation answers 'absent at commit' for a bogus
revision; deleting the call was confirmed to turn the regression test's raise
into MISS_ABSENT.

read types the object with cat-file -t before reading it. cat-file blob alone
conflates 'not there' with 'there but not a file', and the tree's error text
embeds git's own miss sentence: a committed directory named 'does not exist in'
was confirmed to classify as MISS_ABSENT under substring matching. The two miss
spellings are now compared as fully interpolated sentences, so a filename cannot
spoof one.

authorize runs before any git call, including verify_commit, so a denied request
spawns no process at all -- asserted with a landmine rather than by inspecting
the return value. The earlier ordering passed a test named
'without_reaching_git' that never checked its own claim.

Caller-supplied paths reach git as :(top,literal) pathspecs and as the
normalized spelling authorize returned. Without either, 'priv*' walks around the
deny prefix 'private' -- measured on git 2.55 for both log and grep.

A malformed pattern is refused as retryable rather than raised -- it is the
requester's own input and carries no repository fact. Search AND history carry
the policy exclusions whether or not a pathspec was supplied: authorization
answers whether a path is denied, not whether it CONTAINS something denied, and
log selects recursively, so 'private' reported commits touching the denied
private/x.txt."
```

---

## Task 4: Certify determinism and the dispatch boundary

Task 3 proved `serve` answers correctly in a clean repository. This task proves it answers
**identically in a hostile one** — which is the property replay actually depends on, and the one
no test inside Task 3 establishes.

**Files:**
- Test: `science/tests/test_evidence_broker_canonical.py`

**Interfaces:**
- Consumes: everything from Tasks 2 and 3. Adds no production code. If a test here fails, the fix
  belongs in `serve.py`'s argv constants, not in the test.

- [ ] **Step 1: Write the failing tests**

`science/tests/test_evidence_broker_canonical.py`:

```python
from __future__ import annotations

import ast
import os
import subprocess
from pathlib import Path

import pytest
from science_model.evidence_broker import SurfacePolicy

from science_tool.evidence_broker.policy import EvidenceOp, EvidenceRequest
from science_tool.evidence_broker.serve import Outcome, serve

OPEN = SurfacePolicy(notice="withheld")
UTF8_LOCALE = "en_US.UTF-8"


def _configured_repo(tmp_path: Path, name: str, config: dict[str, str]) -> tuple[Path, str]:
    """A repository the ACTOR configured. `.git/config` is untracked and invisible to the
    path gate, so every key here is one the actor can set during its own run."""
    root = tmp_path / name
    root.mkdir()
    for args in (
        ("init", "-q"),
        ("config", "user.email", "p@example.invalid"),
        ("config", "user.name", "P"),
    ):
        subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)
    for key, value in config.items():
        subprocess.run(
            ["git", "-C", str(root), "config", key, value], check=True, capture_output=True
        )
    # Non-ASCII, so `[[:alpha:]]` classifies differently under C and under UTF-8.
    (root / "sample.txt").write_text("éalpha\nplain\nalpha.beta\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True, capture_output=True)
    # DATES ARE PINNED. `_LOG_ARGV` renders `%aI`, so two fixture repositories built a
    # second apart would produce different bytes and the log comparison would fail for a
    # reason that has nothing to do with configuration -- a false alarm on the exact test
    # meant to catch a real one.
    subprocess.run(
        ["git", "-C", str(root), "commit", "-q", "-m", "seed"],
        check=True,
        capture_output=True,
        env={
            **os.environ,
            "GIT_AUTHOR_DATE": "2026-01-01T00:00:00+00:00",
            "GIT_COMMITTER_DATE": "2026-01-01T00:00:00+00:00",
        },
    )
    commit = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"], check=True, capture_output=True
    ).stdout.decode().strip()
    return root, commit


def _search(pattern: str) -> EvidenceRequest:
    return EvidenceRequest(op=EvidenceOp.SEARCH, target=pattern)


def _payload(tmp_path: Path, name: str, config: dict[str, str], request) -> bytes:
    root, commit = _configured_repo(tmp_path, name, config)
    served = serve(root, commit, request, OPEN)
    # The commit differs per fixture; strip it so the comparison is about RENDERING.
    return served.payload.replace(commit.encode(), b"<commit>")


HOSTILE_GREP_CONFIGS = (
    ("fixed", {"grep.patternType": "fixed"}),
    ("basic", {"grep.patternType": "basic"}),
    ("perl", {"grep.patternType": "perl"}),
    ("colour", {"color.ui": "always", "color.grep": "always"}),
    ("column", {"grep.column": "true"}),
    ("quote", {"core.quotePath": "true"}),
    ("nolineno", {"grep.lineNumber": "false"}),
)


@pytest.mark.parametrize("name,config", HOSTILE_GREP_CONFIGS)
def test_grep_renders_identically_under_hostile_configuration(
    tmp_path: Path, name: str, config: dict[str, str]
):
    """`grep.patternType` decides what the caller's PATTERN MEANS, not merely how output
    looks, so an inherited value makes one request two different queries. The rest change
    rendering. Replay compares bytes, so either kind refuses an honest run."""
    baseline = _payload(tmp_path, "baseline", {}, _search("alpha.beta"))
    assert _payload(tmp_path, name, config, _search("alpha.beta")) == baseline


HOSTILE_LOG_CONFIGS = (
    ("date", {"log.date": "rfc"}),
    ("decorate", {"log.decorate": "full"}),
    ("abbrev", {"log.abbrevCommit": "true"}),
    ("pretty", {"format.pretty": "oneline"}),
    ("signature", {"log.showSignature": "true"}),
)


@pytest.mark.parametrize("name,config", HOSTILE_LOG_CONFIGS)
def test_log_renders_identically_under_hostile_configuration(
    tmp_path: Path, name: str, config: dict[str, str]
):
    request = EvidenceRequest(op=EvidenceOp.HISTORY, target="sample.txt")
    baseline = _payload(tmp_path, "log-baseline", {}, request)
    assert _payload(tmp_path, name, config, request) == baseline


@pytest.mark.parametrize("locale", ["C", UTF8_LOCALE, "fr_FR.UTF-8"])
def test_a_posix_class_replays_identically_across_parent_locales(
    tmp_path: Path, locale: str, monkeypatch
):
    """Run as a REPLAY across differing parent locales, since that is the failure being
    prevented: `[[:alpha:]]` matches a different character set under C than under UTF-8,
    so an unpinned locale makes two honest replays of one query disagree."""
    baseline = _payload(tmp_path, "locale-baseline", {}, _search("[[:alpha:]]alpha"))
    monkeypatch.setenv("LC_ALL", locale)
    monkeypatch.setenv("LANG", locale)
    monkeypatch.setenv("LANGUAGE", locale.split(".")[0])
    assert _payload(tmp_path, f"locale-{locale}", {}, _search("[[:alpha:]]alpha")) == baseline


def test_the_defined_miss_classifier_survives_a_translated_parent(tmp_path: Path, monkeypatch):
    """git's DIAGNOSTIC text is localized and the classifier reads it. Under a translated
    parent an absent path would fall through to "anything else raises" -- an ordinary miss
    becoming a halted run. `LANGUAGE` selects git's catalogue; `LC_ALL=C` must defeat it."""
    root, commit = _configured_repo(tmp_path, "translated", {})
    monkeypatch.setenv("LANGUAGE", "fr")
    served = serve(root, commit, EvidenceRequest(op=EvidenceOp.READ, target="nope.txt"), OPEN)
    assert served.outcome is Outcome.MISS_ABSENT


GIT_TOUCHING = ("verify_commit", "_serve_read", "_serve_search", "_serve_history")


def _package_dir() -> Path:
    import science_tool.evidence_broker as package

    # Located from the module, not from the working directory: a relative path here would
    # make the guard's reach depend on where pytest was invoked from.
    return Path(package.__file__).parent


def _module_asts() -> dict[str, ast.Module]:
    """EVERY module in the package. A guard that parses one file has already decided where
    the defect will be, which is the assumption a new module exists to violate."""
    return {
        path.name: ast.parse(path.read_text(encoding="utf-8"))
        for path in sorted(_package_dir().glob("*.py"))
    }


def test_every_git_call_in_the_package_sits_in_a_known_helper():
    """Derived from the code, not from a list someone maintains -- same spirit as
    `tests/test_instrument_boundary.py`. A `run_git` call added to `policy.py`, or to a
    module that does not exist yet, fails here rather than quietly acquiring an unaudited
    path to git."""
    callers: dict[str, set[str]] = {}
    for name, tree in _module_asts().items():
        callers[name] = {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
            and any(
                isinstance(inner, ast.Call)
                and isinstance(inner.func, ast.Name)
                and inner.func.id == "run_git"
                for inner in ast.walk(node)
            )
        }
    assert callers.pop("serve.py") == set(GIT_TOUCHING)
    assert all(not found for found in callers.values()), f"git reached from: {callers}"


def test_authorize_precedes_every_git_call_in_serve():
    """ORDERING, not membership. Asserting only that `serve` CONTAINS a call to
    `authorize` passes when a helper is invoked above it -- which is exactly the defect
    this guard exists to catch, and exactly the shape the first draft shipped.

    THIS IS A STRUCTURAL PROXY, NOT A PROOF OF DOMINANCE. Source position is not control
    flow: a call textually below `authorize` could still run first through a construct this
    check cannot see. It is cheap and it catches the mistake people actually make -- moving
    a line. `test_a_denied_read_makes_no_git_call_at_all` is the behavioural guard, and it
    is the one that would survive a cleverer rearrangement; this one localizes the failure
    to a line number when it fires.
    """
    serve_fn = next(
        node
        for node in ast.walk(_module_asts()["serve.py"])
        if isinstance(node, ast.FunctionDef) and node.name == "serve"
    )
    positions: dict[str, list[tuple[int, int]]] = {}
    for inner in ast.walk(serve_fn):
        if isinstance(inner, ast.Call) and isinstance(inner.func, ast.Name):
            positions.setdefault(inner.func.id, []).append((inner.lineno, inner.col_offset))

    assert "authorize" in positions, "serve does not authorize at all"
    assert len(positions["authorize"]) == 1, "one authorization, so there is one thing to order"
    authorized_at = positions["authorize"][0]

    reached = {name: positions[name] for name in GIT_TOUCHING if name in positions}
    assert set(reached) == set(GIT_TOUCHING), f"serve does not dispatch to {set(GIT_TOUCHING) - set(reached)}"
    for name, sites in reached.items():
        for site in sites:
            assert site > authorized_at, f"{name} is called at {site}, before authorize at {authorized_at}"


#: MATCHED BY SHAPE, NOT BY ROSTER. An enumeration of `os` spawn names is a list someone has
#: to keep complete against a stdlib that has ~20 of them (`spawnl`, `spawnlp`, `spawnvp`,
#: `spawnvpe`, `posix_spawnp`, the whole `exec*` family), and the one left off the list is the
#: one a mutation reaches for. `_spawns` matches the family by prefix instead, and the call
#: check ignores the receiver entirely -- so `os.spawnvp`, `o.system` under an aliased import,
#: and a bare `system(...)` after `from os import system` all land the same way.
_SPAWNING_MODULES = frozenset({"subprocess", "pty", "multiprocessing"})
_SPAWNING_PREFIXES = ("exec", "spawn", "popen", "posix_spawn", "fork")
#: `import_module` and `__import__` are here because a dynamic import defeats the import check
#: above: without them, `importlib.import_module("subprocess").run(...)` passes.
_SPAWNING_NAMES = frozenset({"system", "startfile", "import_module", "__import__"})


def _spawns(name: str) -> bool:
    lowered = name.lower()
    return lowered in _SPAWNING_NAMES or lowered.startswith(_SPAWNING_PREFIXES)


def test_the_broker_makes_no_direct_subprocess_call():
    """A git call that skips `run_git` is a call the actor can turn into arbitrary
    execution inside the control plane, and no layer of this design would report it.

    AN AST CHECK, NOT A TEXT SCAN. Searching each module for the substring `subprocess`
    reads as stricter and is simply broken: `policy.py`'s own docstring explains why a NUL
    cannot cross `subprocess`'s argv boundary, and the guard would reject the module for
    documenting the reason it exists. A guard that forbids discussing the hazard forces the
    explanation out of the code, which is the opposite of what it was written for.

    STILL A STRUCTURAL PROXY. `getattr(os, "sys" + "tem")` defeats it, as does any other
    computed name. The claim is bounded accordingly: no module in this package *spells* a
    process launch. That is worth asserting because it is the spelling a refactor or a
    convenience helper would actually use.
    """
    for name, tree in _module_asts().items():
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    # alias.name, not alias.asname: `import subprocess as sp` is still an import.
                    assert alias.name.split(".")[0] not in _SPAWNING_MODULES, f"{name}: {alias.name}"
            elif isinstance(node, ast.ImportFrom):
                root = (node.module or "").split(".")[0]
                assert root not in _SPAWNING_MODULES, f"{name}: from {node.module}"
                for alias in node.names:
                    # Catches `from os import system`, where the module is innocent and the
                    # imported name is not.
                    assert not _spawns(alias.name), f"{name}: from {node.module} import {alias.name}"
            elif isinstance(node, ast.Call):
                func = node.func
                called = (
                    func.attr
                    if isinstance(func, ast.Attribute)
                    else func.id
                    if isinstance(func, ast.Name)
                    else None
                )
                assert called is None or not _spawns(called), f"{name}: calls {called}"
```

Before relying on it, confirm the predicate on the seventeen spellings it is meant to reject and the
three module shapes it must accept — the roster version passed every module in this package while
still admitting `os.spawnvp`, so "the guard is green" is not evidence about the guard:

| Must fail | Must pass |
|---|---|
| `import subprocess` / `import subprocess as sp` | `policy.py`'s shape: a docstring naming `subprocess`, `import os`, `os.fsencode` |
| `from subprocess import run` / `import Popen` | `serve.py`'s shape: `from science_tool.autonomy.git import run_git` |
| `os.spawnvp`, `os.spawnvpe`, `os.spawnl`, `os.posix_spawnp` | `__init__.py`'s shape: a re-export |
| `os.execl`, `os.execlp`, `os.popen`, `os.system` | |
| `from os import system` then `system(...)` | |
| `import os as o` then `o.system(...)` | |
| `importlib.import_module("subprocess")`, `__import__("subprocess")` | |
| `import pty` then `pty.spawn(...)` | |

- [ ] **Step 2: Run them and record what fails**

```bash
cd science && uv run --frozen pytest tests/test_evidence_broker_canonical.py -v
```

Expected: **all PASS**, because Task 3 already built the canonical argv. This task's value is the
certification, not a code change.

Two exceptions to handle honestly rather than by loosening an assertion:

- `fr_FR.UTF-8` and `en_US.UTF-8` may not be installed. `monkeypatch.setenv` sets the variable
  regardless, and `LC_ALL=C` in `run_git` defeats it either way, so the test is meaningful even
  when the locale is absent — but **verify** with `locale -a | grep -i utf` and note in the task
  report which locales were actually present. Do **not** add a `pytest.skip`: a guard that skips
  on the machine where it matters is a guard that never runs.
- If `grep.patternType=perl` fails because PCRE is not compiled in, git exits non-zero with a
  `fatal:` this module has not been shown, so `serve` raises `ServeError`. That is the designed
  behaviour, not a bug. Replace that one row with a test asserting the raise, and say so in the
  commit message.

- [ ] **Step 3: Prove each certification can fail**

For each, restore the prior behaviour, confirm the named test fails, then restore:

| Remove from `serve.py` | Expected failure |
|---|---|
| `-E` from `_GREP_ARGV` | the `fixed`, `basic` and `perl` rows |
| `--no-color` | the `colour` row |
| `--no-column` | the `column` row |
| `--pretty=format:%H %aI` | the `pretty` row |
| `--no-decorate` | the `decorate` row |
| `LC_ALL`/`LANG` from `git.py`'s `_ENVIRONMENT` | the locale replay and the translated-parent rows |
| Move `verify_commit(repo_root, commit)` above the `authorize` branch in `serve` | `test_authorize_precedes_every_git_call_in_serve` |
| Add a `run_git` call to a function in `policy.py` | `test_every_git_call_in_the_package_sits_in_a_known_helper` |
| Add `import subprocess` + `subprocess.run(["git", "log"], ...)` to `serve.py` | `test_the_broker_makes_no_direct_subprocess_call` |
| Instead add `os.spawnvp(os.P_WAIT, "git", ["git", "log"])` to `policy.py` | the same test — **this is the row that matters** |
| Instead add `from os import system` + `system("git log")` to `policy.py` | the same test |

The three spawn rows are not redundant. The first fails against any spelling of the guard,
including the roster version that shipped in the third draft. The second and third are the ones
that distinguish them: the roster listed nine `os` names and omitted `spawnvp` and `spawnl`
entirely, and it only ever inspected attribute calls on a receiver literally named `os`, so a
bare `system(...)` was invisible to it. **Run all three.** A guard certified only by the mutation
it was designed against is certified by its author's imagination.

**Run the `policy.py` `run_git` row against `policy.py` specifically.** An earlier draft parsed only `serve.py`,
so this exact mutation passed both derived guards — the file the guard was written about was the
one file it could not have been wrong about. Confirm the failure message names `policy.py`.

The ordering row matters for a different reason: the guard it exercises replaced a membership
check that passed against the very defect it was written to catch.

The `log.showSignature` row is disarmed in `run_git`'s `_HARDENING`, not in `serve.py` — plan 1
already proved that guard can fail, so do not re-prove it here.

- [ ] **Step 4: Lint, type-check, commit**

```bash
cd science && uv run ruff check && uv run pyright
git add science/tests/test_evidence_broker_canonical.py
git commit -m "test(evidence-broker): certify determinism under hostile configuration

Task 3 proved serve answers correctly in a clean repository. Replay depends on
it answering identically in one the actor configured, which no test there
establishes: .git/config is untracked and invisible to the path gate, so every
key exercised here is one the actor can set mid-run.

Seven grep configurations and five log configurations produce byte-identical
served output; grep.patternType is the one that changes what the pattern MEANS
rather than how it looks. A POSIX class replays identically across parent
locales, and the defined-miss classifier survives a translated parent, which is
the case that would turn an ordinary absent path into a halted run.

Three derived guards, all from the AST and all over the whole package: every
run_git call sits in a known helper, authorize precedes every one of them by
source position rather than by set membership, and no module spells a process
launch. The membership spelling passed against a helper invoked above the
authorization, which is the defect the guard exists to catch; the process-boundary
guard was first a text scan that rejected policy.py for documenting why the NUL
check exists, and then a roster of nine os names that admitted spawnvp, spawnl
and a bare system() imported by name. It matches the family by prefix now, and
two of its three mutations are ones the roster survived."
```

---

## Self-Review

Run this yourself after the last task, before the whole-branch review.

**1. Spec coverage.** Every §7 bullet this plan claimed is either closed by a named test or
appears in the deferred table above. Check each of: `serve.py`; canonical invocation; locale;
pathspec translation; `read` refuses a directory; `policy.py`; the derived dispatch guard.

**2. The design's own §7 discipline.** Where this plan *claims* a property, does the suite
establish it **under the condition the claim names**? Specifically: the locale tests run as a
replay across differing parents, not as a single run under one locale; the hostile-config tests
compare against a baseline built in a *separate* repository, not against a hard-coded string.

**3. Type consistency.** `Outcome`, `Served`, `ServeError`, `Denial`, `Authorization`,
`EvidenceOp`, `EvidenceRequest`, `SurfacePolicy`, `authorize`, `exclude_pathspecs`,
`literal_pathspec`, `verify_commit`, `serve` — spelled identically in every task and in plan 3's
Interfaces expectations.

**4. The path-spelling invariant.** Grep the finished `serve.py` for `request.`. It must appear
**only inside `serve` itself**, which destructures the request once and passes a pattern or an
`auth.path` downward; no `_serve_*` helper may take an `EvidenceRequest` at all. A helper holding
the request is a helper that can reach the raw target, which is the defect review found in the
first draft — authorizing one spelling and handing git another. Then grep for `"--"` and confirm
every caller-supplied path in the argv built after it is wrapped in `literal_pathspec`.

**5. Parked items from plan 1 that do NOT belong here.** `run_slug`'s unbounded handle length and
the `ControlPlaneError`/`BaselineError` CLI handler both wait for plan 3, where the first `mkdir`
and the first CLI handler appear. Do not fix them here — there is nothing to hold them to.

## Execution Handoff

Plan complete and saved to `docs/plans/2026-07-30-evidence-broker-plan-2-serving.md`. Two
execution options:

**1. Subagent-Driven (recommended)** — a fresh subagent per task, review between tasks, fast
iteration. This is what plan 1 used; the per-task reviews caught four defects and the final
whole-branch review caught four more that no per-task review could see, because they were
contradictions *between* files.

**2. Inline Execution** — tasks executed in this session with checkpoints.

Task 1 is the natural gate: it is small, it touches a module with a standing rule, and whether
its probe record reads correctly is a good early signal about the rest.

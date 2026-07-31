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
| `science/src/science_tool/evidence_broker/policy.py` | **Create.** `EvidenceOp`, `EvidenceRequest`, `Denial`, `authorize`, `exclude_pathspecs`. Decides *whether*; never runs git. |
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

**The probe result, already measured** (git 2.55, scratch repository, under exactly
`git --no-replace-objects -c <key> -C <root> cat-file blob <commit>:a.txt`, with
`.gitattributes` carrying `a.txt diff=probe filter=probe` so the driver keys have a reason to
fire, and a marker-touching `./spawn.sh` as every named program):

| keys | verdict |
|---|---|
| `core.pager`, `pager.cat-file` | **INERT** |
| `diff.probe.textconv`, `diff.probe.command`, `diff.external` | **INERT** |
| `filter.probe.clean`, `filter.probe.smudge`, `filter.probe.process` | **INERT** |
| `core.fsmonitor`, `core.hooksPath` | **INERT** |
| `core.quotePath`, `core.autocrlf`, `core.eol` | **INERT** |
| `log.showSignature`, `gpg.program` | **INERT** |
| `core.sshCommand`, `core.alternateRefsCommand` | **INERT** |

Seventeen keys, nothing executes and nothing renders differently. `cat-file blob` is a raw object
read: no smudge filter, no textconv, no eol conversion, and no pager because output is captured.
**`_HARDENING` therefore gains nothing.** Adding a key here would assert a defense against
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
* `cat-file blob <commit>:<path>` -- every key probed is INERT: `core.pager`, `pager.cat-file`,
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

  def authorize(request: EvidenceRequest, policy: SurfacePolicy) -> Denial | None
  def exclude_pathspecs(policy: SurfacePolicy) -> tuple[str, ...]
  ```

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
    Denial,
    EvidenceOp,
    EvidenceRequest,
    authorize,
    exclude_pathspecs,
)

POLICY = SurfacePolicy(deny_prefixes=("private", "notes/a[b].md"), notice="withheld by policy")


def _read(target: str) -> EvidenceRequest:
    return EvidenceRequest(op=EvidenceOp.READ, target=target)


def test_a_path_under_a_deny_prefix_is_refused():
    denial = authorize(_read("private/x.txt"), POLICY)
    assert isinstance(denial, Denial)
    assert denial.notice == "withheld by policy"
    assert denial.reason == "path-denied"


def test_the_prefix_itself_is_refused():
    assert authorize(_read("private"), POLICY) is not None


def test_a_prefix_denies_on_component_boundaries_only():
    """`private` must deny `private/x` and must NOT deny `privateer/x`. A bare
    `startswith` would deny both, and would silently withhold an unrelated tree."""
    assert authorize(_read("privateer/x.txt"), POLICY) is None


def test_containment_is_checked_before_any_prefix():
    """A prefix check alone is walked around with `..`, so traversal is refused first
    and is refused as MALFORMED rather than as denied -- the two are different facts and
    a requester that cannot tell them apart cannot correct its own input."""
    denial = authorize(_read("private/../public/x.txt"), POLICY)
    assert denial is not None
    assert denial.reason == "path-malformed"


def test_an_absolute_path_is_refused_lexically():
    denial = authorize(_read("/etc/passwd"), POLICY)
    assert denial is not None
    assert denial.reason == "path-malformed"


def test_an_undenied_path_is_authorized():
    assert authorize(_read("src/main.py"), POLICY) is None


def test_a_search_carries_no_path_so_only_its_pathspec_is_judged():
    """SEARCH's target is a PATTERN. Judging it as a path would refuse legitimate
    patterns for containing `/` or `..`, and would say nothing about what git reads."""
    assert authorize(EvidenceRequest(op=EvidenceOp.SEARCH, target="../secret"), POLICY) is None
    denied = EvidenceRequest(op=EvidenceOp.SEARCH, target="x", pathspec="private/x.txt")
    assert authorize(denied, POLICY) is not None


def test_history_is_judged_as_a_path():
    assert authorize(EvidenceRequest(op=EvidenceOp.HISTORY, target="private/x.txt"), POLICY) is not None


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
    assert (authorize(_read(path), POLICY) is not None) is denied
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


def _denied_by_prefix(path: str, prefix: str) -> bool:
    """Component-boundary matching. `private` denies `private` and `private/x`, not `privateer`."""
    return path == prefix or path.startswith(f"{prefix}/")


def _judge_path(raw: str, policy: SurfacePolicy) -> Denial | None:
    try:
        path = normalize_project_path(raw)
    except SubjectError as exc:
        # Containment BEFORE any prefix: a prefix check alone is walked around with `..`.
        # Reported as malformed rather than denied because they are different facts -- one is
        # the requester's own error and correctable, the other is the study's boundary.
        return Denial(reason="path-malformed", notice=str(exc))
    if any(_denied_by_prefix(path, prefix) for prefix in policy.deny_prefixes):
        return Denial(reason="path-denied", notice=policy.notice)
    return None


def authorize(request: EvidenceRequest, policy: SurfacePolicy) -> Denial | None:
    """`None` means the request may be served. Judging happens before any join or any git call."""
    if request.op is EvidenceOp.SEARCH:
        return None if request.pathspec is None else _judge_path(request.pathspec, policy)
    return _judge_path(request.target, policy)


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

- [ ] **Step 9: Prove the boundary guard can fail**

Temporarily change `_denied_by_prefix` to `return path.startswith(prefix)` and re-run.

Expected: `test_a_prefix_denies_on_component_boundaries_only` and the
`privateer/x.txt` table row FAIL. Restore the correct implementation and confirm green. Record
the observed failure in the commit message.

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

SEARCH's target is a pattern and is never judged as a path; only its optional
pathspec is."
```

---

## Task 3: `evidence_broker/serve.py`

**Files:**
- Create: `science/src/science_tool/evidence_broker/serve.py`
- Test: `science/tests/test_evidence_broker_serve.py`

**Interfaces:**
- Consumes: `run_git` (plan 1); `authorize`, `exclude_pathspecs`, `EvidenceOp`,
  `EvidenceRequest`, `Denial` (Task 2); `SurfacePolicy`.
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


def test_a_denied_read_is_refused_without_reaching_git(tmp_path: Path):
    root, commit = _repo(tmp_path)
    served = serve(root, commit, _read("private/x.txt"), CLOSED)
    assert served.outcome is Outcome.REFUSED
    assert served.denial is not None
    assert served.payload == b""


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
    guessed would turn an instrument failure into evidence."""
    root, commit = _repo(tmp_path)
    import science_tool.evidence_broker.serve as serve_module

    class _Fake:
        returncode = 128
        stdout = b""
        stderr = b"fatal: something nobody has seen before\n"

    monkeypatch.setattr(serve_module, "run_git", lambda *a, **k: _Fake())
    with pytest.raises(ServeError):
        serve(root, commit, _read("a.txt"), OPEN)
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

#: The two spellings git gives one fact. Which one appears depends on the working tree, which the
#: actor owns, so both must classify the same way.
_ABSENT_MARKERS: tuple[bytes, ...] = (b"does not exist in", b"exists on disk, but not in")

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
    completed = run_git(repo_root, "cat-file", "blob", f"{commit}:{target}")
    if completed.returncode == 0:
        return Served(outcome=Outcome.SERVED, payload=completed.stdout)
    stderr = completed.stderr
    if any(marker in stderr for marker in _ABSENT_MARKERS):
        return _miss(Outcome.MISS_ABSENT)
    # `bad file` is how `cat-file blob` refuses a TREE. It is not a miss: the path is at the
    # commit, it simply is not a file, and serving `git show`'s directory listing instead would
    # record FULL coverage over a listing nobody can cite honestly.
    raise ServeError(
        f"read of {target!r} at {commit} could not be classified: "
        f"{stderr.decode('utf-8', 'replace').strip()}"
    )


def _serve_search(
    repo_root: Path, commit: str, request: EvidenceRequest, policy: SurfacePolicy
) -> Served:
    pathspecs = [*exclude_pathspecs(policy)]
    if request.pathspec is not None:
        pathspecs.insert(0, request.pathspec)
    completed = run_git(
        repo_root, *_GREP_ARGV, "-e", request.target, commit, "--", *pathspecs
    )
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
        f"search for {request.target!r} at {commit} could not be classified: "
        f"{stderr.decode('utf-8', 'replace').strip()}"
    )


def _serve_history(repo_root: Path, commit: str, target: str) -> Served:
    completed = run_git(repo_root, *_LOG_ARGV, commit, "--", target)
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

    `verify_commit` runs first and `authorize` runs second: a request that is going to be refused
    should not reach git at all, and a request that IS going to reach git must not do so against
    an unverified revision.
    """
    resolved = verify_commit(repo_root, commit)
    denial = authorize(request, policy)
    if denial is not None:
        return Served(outcome=Outcome.REFUSED, payload=b"", denial=denial)
    if request.op is EvidenceOp.READ:
        return _serve_read(repo_root, resolved, request.target)
    if request.op is EvidenceOp.SEARCH:
        return _serve_search(repo_root, resolved, request, policy)
    return _serve_history(repo_root, resolved, request.target)
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
cd science && uv run --frozen pytest tests/test_evidence_broker_serve.py -v
```

Expected: PASS (14 tests).

- [ ] **Step 5: Prove the two load-bearing guards can fail**

Both of these are guards the design says have looked right on the page before:

1. **Commit ordering.** Move the `verify_commit(repo_root, commit)` call in `serve` to *after*
   the `authorize` branch and pass `commit` through unresolved to the `_serve_*` helpers. Re-run.
   Expected: `test_a_wellformed_nonexistent_commit_halts_rather_than_answering` still passes,
   because `serve` still calls `verify_commit` at all — **so also** delete the call entirely and
   confirm the test then reports `MISS_ABSENT` instead of raising. Restore.
2. **The second absent spelling.** Remove `b"exists on disk, but not in"` from `_ABSENT_MARKERS`
   and re-run. Expected:
   `test_an_absent_path_that_exists_on_disk_is_the_same_miss` FAILS with `ServeError`. Restore.

Record both observed failures in the commit message.

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

read is cat-file blob: it refuses a tree, where show answers with a listing at
exit 0. The absent miss has two spellings depending on the working tree, which
the actor owns; dropping either was confirmed to raise on an ordinary absent
path.

A malformed pattern is refused as retryable rather than raised -- it is the
requester's own input and carries no repository fact. Every search carries the
policy exclusions whether or not a pathspec was supplied, because search is the
one operation that never names a path."
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


def test_no_path_reaches_git_without_passing_authorize():
    """Derived from the code, not from a list someone maintains -- same spirit as
    `tests/test_instrument_boundary.py`. Every `run_git` call in the broker must sit in a
    function `serve` reaches only after `authorize` has returned None, and `serve` is the
    only exported entry point that takes a request."""
    # Located from the module, not from the working directory: a relative path here would
    # make the guard's reach depend on where pytest was invoked from.
    import science_tool.evidence_broker.serve as serve_module

    tree = ast.parse(Path(serve_module.__file__).read_text(encoding="utf-8"))
    callers = {
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
    assert callers == {"verify_commit", "_serve_read", "_serve_search", "_serve_history"}

    serve_fn = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "serve"
    )
    called = {
        inner.func.id
        for inner in ast.walk(serve_fn)
        if isinstance(inner, ast.Call) and isinstance(inner.func, ast.Name)
    }
    assert "authorize" in called
    # Every git-touching helper other than `verify_commit` is reached only from `serve`.
    assert {"_serve_read", "_serve_search", "_serve_history"} <= called


def test_the_broker_makes_no_direct_subprocess_call():
    """A git call that skips `run_git` is a call the actor can turn into arbitrary
    execution inside the control plane, and no layer of this design would report it."""
    import science_tool.evidence_broker as package

    for path in Path(package.__file__).parent.glob("*.py"):
        assert "subprocess" not in path.read_text(encoding="utf-8"), path
```

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

Two derived guards, from the AST rather than a maintained list: every run_git
call sits behind authorize, and the package makes no direct subprocess call."
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

**3. Type consistency.** `Outcome`, `Served`, `ServeError`, `Denial`, `EvidenceOp`,
`EvidenceRequest`, `SurfacePolicy`, `authorize`, `exclude_pathspecs`, `verify_commit`, `serve` —
spelled identically in every task and in plan 3's Interfaces expectations.

**4. Parked items from plan 1 that do NOT belong here.** `run_slug`'s unbounded handle length and
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

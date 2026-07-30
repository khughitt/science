# Evidence Broker Plan 1 — Control Plane and Canonical Git Invocation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make an autonomous run addressable from its id, and close the two determinism hazards that live *below* argv — the parent locale, and any git config key that executes a program under `grep` or `log`.

**Architecture:** Two independent modules under `science/src/science_tool/autonomy/`, neither of which mentions evidence. `control_plane.py` is a pure path calculator: a project-scoped, digest-keyed root under which a run id resolves to exactly one directory. `git.py` gains a probed hardening set for two subcommands it has never run, plus an environment pin.

**What this does not claim.** Byte-identical output *regardless of repository configuration* is a two-part property, and this plan delivers one part. The per-operation argv pins of §3.2.1's table — explicit pattern type, `--no-color`, `-n`, `-z`, `--no-decorate`, an explicit `--pretty` — are built by `evidence_broker/serve.py` and land with it in plan 2, along with the §7 tests that compare served bytes across configurations. Plan 1 owns the half `run_git` can be held to on its own: the environment, and the `-c` hardening for keys that execute.

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

**None.** §3.4.1's two-part rule is implemented as written, and its first half is stronger
than it might read. The handle *is* validated as a generated run id, not merely as a safe
path component: `_SHORT_ID_RE` is `[a-z0-9]{4,}` (`autonomous_runs.py:30`), so a short id
can never contain a hyphen, which makes `rpartition("-")` an unambiguous split of
`<agent>-<short-id>` even though the agent slug may contain hyphens. Task 3 splits that way
and hands both parts to the shipped `validate_run_identity`, so a handle no `generate_run_id`
call could ever have produced — `2026-07-30-a`, a three-character suffix, an agent with an
underscore — is refused before any path join.

The second half — after loading, the baseline's own `run_id` must equal the handle — is
plan 2's, because it needs a baseline in the control plane to load, and only a
`--broker-spec` run places one there. It appears in the deferred table above; the two halves
are not both in Task 3.

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
SIGNED_LOG_ARGV = ("log", "--pretty=format:%H %aI", "SIGNED")

FAKE_SIGNATURE = """-----BEGIN PGP SIGNATURE-----

 not a real signature; git must still hand it to the configured program
 -----END PGP SIGNATURE-----"""


def make_signed_commit(root: Path) -> None:
    """A commit carrying a `gpgsig` header, built WITHOUT a signing key.

    Signature verification is the one execution path here that needs an object to verify:
    against unsigned history `log.showSignature` finds nothing to verify and `gpg.program`
    is never consulted, so probing them separately against an unsigned repo reports INERT
    twice and concludes, falsely, that git log executes nothing. git does not validate the
    header's contents before handing it to the program, so a fabricated block is enough to
    trigger the call.
    """
    tree = run(root, "rev-parse", "HEAD^{tree}").stdout.decode().strip()
    parent = run(root, "rev-parse", "HEAD").stdout.decode().strip()
    ident = "Probe <probe@example.invalid> 0 +0000"
    body = (
        f"tree {tree}\n"
        f"parent {parent}\n"
        f"author {ident}\n"
        f"committer {ident}\n"
        f"gpgsig {FAKE_SIGNATURE}\n"
        "\n"
        "signed\n"
    )
    completed = subprocess.run(
        ["git", "-C", str(root), "hash-object", "-t", "commit", "-w", "--stdin"],
        input=body.encode("utf-8"),
        capture_output=True,
    )
    sha = completed.stdout.decode().strip()
    if not sha:
        raise SystemExit(f"could not write the signed commit: {completed.stderr.decode()}")
    run(root, "update-ref", "refs/heads/SIGNED", sha)


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


def probe(
    config: tuple[tuple[str, str], ...],
    argv: tuple[str, ...],
    *,
    attribute: str | None = None,
    signed: bool = False,
) -> str:
    """`config` is a TUPLE of key/value pairs, not one pair.

    Some execution paths need two keys set together and neither alone demonstrates
    anything -- `log.showSignature` plus `gpg.program` is the case that motivated the
    shape. Probing key-at-a-time would report both INERT and harden neither.
    """
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "repo"
        marker = Path(tmp) / "EXECUTED"
        build_repo(root, marker)
        if signed:
            make_signed_commit(root)
        baseline = run(root, *argv).stdout

        for key, value in config:
            run(root, "config", key, value)
        if attribute is not None:
            (root / ".gitattributes").write_text(attribute, encoding="utf-8")
            run(root, "add", "-A")
            run(root, "commit", "-q", "-m", "attr")
            # Re-baseline with every configured key blanked, so the comparison isolates the
            # keys rather than the attribute commit that had to be added alongside them.
            blanked = [arg for key, _ in config for arg in ("-c", f"{key}=")]
            baseline = run(root, *blanked, *argv).stdout

        after = run(root, *argv).stdout
        if marker.exists():
            return "EXECUTES"
        return "RENDERS" if after != baseline else "INERT"


Candidate = tuple[tuple[tuple[str, str], ...], tuple[str, ...], str | None, bool]

CANDIDATES: list[Candidate] = [
    # grep -- rendering and meaning
    ((("grep.patternType", "fixed"),), GREP_ARGV, None, False),
    ((("grep.extendedRegexp", "true"),), GREP_ARGV, None, False),
    ((("grep.lineNumber", "false"),), GREP_ARGV, None, False),
    ((("grep.fullName", "true"),), GREP_ARGV, None, False),
    ((("grep.column", "true"),), GREP_ARGV, None, False),
    ((("grep.threads", "1"),), GREP_ARGV, None, False),
    ((("color.grep", "always"),), GREP_ARGV, None, False),
    ((("color.ui", "always"),), GREP_ARGV, None, False),
    ((("core.quotePath", "true"),), GREP_ARGV, None, False),
    # grep -- execution
    ((("diff.probe.textconv", "./spawn.sh"),), GREP_ARGV, "*.txt diff=probe\n", False),
    ((("core.pager", "./spawn.sh"),), GREP_ARGV, None, False),
    ((("pager.grep", "./spawn.sh"),), GREP_ARGV, None, False),
    # log -- rendering
    ((("log.date", "rfc"),), LOG_ARGV, None, False),
    ((("log.decorate", "full"),), LOG_ARGV, None, False),
    ((("log.abbrevCommit", "true"),), LOG_ARGV, None, False),
    ((("log.mailmap", "true"),), LOG_ARGV, None, False),
    ((("format.pretty", "oneline"),), LOG_ARGV, None, False),
    # log -- execution. The signature rows run against the CRAFTED signed commit. The
    # combined row is the one whose program is OURS; `log.showSignature` alone spawns the
    # default `gpg` instead, which this marker cannot see (see Step 2).
    ((("log.showSignature", "true"),), SIGNED_LOG_ARGV, None, True),
    ((("gpg.program", "./spawn.sh"),), SIGNED_LOG_ARGV, None, True),
    (
        (("log.showSignature", "true"), ("gpg.program", "./spawn.sh")),
        SIGNED_LOG_ARGV,
        None,
        True,
    ),
    ((("core.pager", "./spawn.sh"),), LOG_ARGV, None, False),
]


def main() -> int:
    version = subprocess.run(["git", "--version"], capture_output=True, text=True).stdout.strip()
    print(f"# {version}\n")
    print("| keys | op | verdict |")
    print("|---|---|---|")
    for config, argv, attribute, signed in CANDIDATES:
        verdict = probe(config, argv, attribute=attribute, signed=signed)
        spelled = " + ".join(f"`{key}={value}`" for key, value in config)
        print(f"| {spelled} | `{argv[0]}` | **{verdict}** |")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run the probe and capture its output**

Run: `python3 $SCRATCH/probe_git_ops.py | tee $SCRATCH/probe-results.md`

Expected: a table, one row per candidate. Every row must read `EXECUTES`, `RENDERS`, or
`INERT` — no crashes, no blank verdicts.

**The signature rows are the ones to read carefully**, and the single-key rows are not
symmetric. Measured on git 2.55.0:

| keys | verdict |
|---|---|
| `log.showSignature=true` | **RENDERS** |
| `gpg.program=./spawn.sh` | **INERT** |
| `log.showSignature=true` + `gpg.program=./spawn.sh` | **EXECUTES** |

`gpg.program` alone is inert because nothing asks for a verification. `log.showSignature`
alone is *not* inert, and the reason matters more than the verdict: git verifies the
crafted commit using the **default `gpg` on `PATH`**, whose complaint lands in the captured
output —

```
gpg: no valid OpenPGP data found.
gpg: the signature could not be verified.
```

— so the row reads `RENDERS` only because the marker watches `./spawn.sh` and not the
program git actually spawned. Read it as *executes something this probe cannot name*.
Setting `gpg.program` merely redirects an already-live call to an attacker-chosen binary.
This is the measurement behind Step 6's choice of `log.showSignature=false` over a blanked
`gpg.program=`: blanking the program name leaves the verification itself enabled, which is
precisely the state this row shows already reaches a program on `PATH`.

If the combined row does not report `EXECUTES`, stop and diagnose before continuing: either
`make_signed_commit` failed to produce an object git treats as signed (check `git -C <repo>
cat-file commit SIGNED` for the `gpgsig` header), or this git version takes a path this
probe does not model. Record it `UNDETERMINED` rather than `INERT` and say so in the design.
**An untested key must not be recorded as safe** — and this one is not hypothetical:
`verify_marks` (`autonomy/marks.py:31-39`) already runs `git log` on every `finish`, with no
signature control of any kind.

Re-measure rather than copying the table above: it is this plan's evidence that the probe
discriminates, not a substitute for running it on the git the implementer has.

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


UTF8_LOCALE = "en_US.UTF-8"
FRENCH_LOCALE = "fr_FR.UTF-8"
GREP_ARGV = ("grep", "-n", "-e", "[[:alpha:]]alpha", "HEAD")


def _bare_git(root: Path, overrides: dict[str, str], *args: str) -> subprocess.CompletedProcess:
    """git WITHOUT this module's hardening, for negative controls."""
    return subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, env={**os.environ, **overrides}
    )


def test_grep_output_does_not_depend_on_the_parent_locale(tmp_path: Path, monkeypatch):
    """A POSIX class means different things under C and under UTF-8, so an unpinned
    locale makes two honest replays of one query disagree -- and correspondence refuses
    on disagreement.

    The negative control comes FIRST. Locale data is not guaranteed to be installed, and
    when it is missing the C library falls back to C -- so the two outputs would be equal
    for a reason that has nothing to do with the fix, and this test would pass green
    against unpatched code. Skipping is honest; passing would be a lie.
    """
    root = _repo(tmp_path)
    control_c = _bare_git(root, {"LC_ALL": "C", "LANG": "C"}, *GREP_ARGV).stdout
    control_utf8 = _bare_git(
        root, {"LC_ALL": UTF8_LOCALE, "LANG": UTF8_LOCALE}, *GREP_ARGV
    ).stdout
    if control_c == control_utf8:
        pytest.skip(
            f"{UTF8_LOCALE} data is unavailable here, so the hazard does not reproduce and "
            "the guard would pass vacuously"
        )

    monkeypatch.setenv("LC_ALL", "C")
    monkeypatch.setenv("LANG", "C")
    under_c = run_git(root, *GREP_ARGV).stdout

    monkeypatch.setenv("LC_ALL", UTF8_LOCALE)
    monkeypatch.setenv("LANG", UTF8_LOCALE)
    under_utf8 = run_git(root, *GREP_ARGV).stdout

    assert under_c == under_utf8


def test_a_missing_path_is_reported_in_a_pinned_locale(tmp_path: Path, monkeypatch):
    """The defined-miss classifier reads git's stderr. Localized text would not match,
    and an ordinary absent path would halt the run instead of answering."""
    root = _repo(tmp_path)
    missing = ("show", "HEAD:no-such-file.txt")
    english = _bare_git(root, {"LC_ALL": "C", "LANGUAGE": ""}, *missing).stderr
    translated = _bare_git(
        root, {"LC_ALL": FRENCH_LOCALE, "LANGUAGE": "fr"}, *missing
    ).stderr
    if english == translated:
        pytest.skip(
            f"{FRENCH_LOCALE} message catalogues are unavailable here, so git's diagnostics "
            "do not translate and the guard would pass vacuously"
        )

    monkeypatch.setenv("LC_ALL", FRENCH_LOCALE)
    monkeypatch.setenv("LANGUAGE", "fr")
    completed = run_git(root, *missing)

    assert completed.returncode != 0
    assert completed.stderr == english
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd science && uv run --frozen pytest tests/test_autonomy_git_canonical.py -v`

Expected: both tests either FAIL or SKIP — never pass.

- FAIL means the negative control reproduced the hazard and `run_git` did not defend
  against it, which is the state this task fixes.
- SKIP means the locale data is not installed on this machine. That is an honest
  inconclusive, not a pass.
- **A PASS at this step is a bug in the test**, not good news: nothing has been
  implemented yet, so a green assertion means it is asserting something other than what it
  claims. Investigate before proceeding.

If both tests skip, the locale work cannot be verified on this machine. Install the locale
data (`locale-gen en_US.UTF-8 fr_FR.UTF-8`, or the distribution's equivalent) rather than
implementing blind — a pin nobody has watched fail is a pin nobody has tested.

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

For each key Task 1 recorded `EXECUTES`, add it to `_HARDENING` in the spelling the probe
showed disarms it. **Add nothing for `RENDERS` or `INERT` rows.**

For the signature path the spelling is `log.showSignature=false`, **not** a blanked
`gpg.program=`. Do not let the probe's marker talk you out of this: blanking the program
name does clear the marker, because git then tries to execute the empty name and fails
(`error: cannot run : No such file or directory`). Verification is still enabled, and in a
repo where the attacker configured no program at all git falls back to the default `gpg` on
`PATH` — Step 2's single-key row measured exactly that. The marker asks "did *my* binary
run"; the requirement is "did git reach verification". Only `log.showSignature=false`
answers the second, and Step 7's stderr assertion is what holds the distinction.

This one also has a caller today. `verify_marks` (`autonomy/marks.py:31-39`) runs
`git log` on every `finish` through this module, so the hardening takes effect there
immediately; Task 4's scoped run includes `tests/test_autonomy_marks.py` for that reason.

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

Every `EXECUTES` row gets a **pair**: a negative control that reproduces the vector against
bare git, and a guard that asserts `run_git` disarms it. Write the negative control first
and watch it pass — a guard nobody has watched fail is a guard nobody has tested.

**The signature vector is composite and its test must reconstruct all three conditions**:
`log.showSignature=true`, `gpg.program=./spawn.sh`, *and* a commit carrying a `gpgsig`
header. Configuring one key on the ordinary unsigned `_repo` reproduces nothing, so the
guard would pass against unhardened code and prove exactly nothing. Add these helpers and
both tests to `tests/test_autonomy_git_canonical.py`:

```python
FAKE_SIGNATURE = """-----BEGIN PGP SIGNATURE-----

 not a real signature; git must still hand it to the configured program
 -----END PGP SIGNATURE-----"""

SIGNED_LOG_ARGV = ("log", "--pretty=format:%H %aI", "SIGNED")


def _signed_repo(tmp_path: Path) -> tuple[Path, Path]:
    """A repo whose `SIGNED` ref carries a `gpgsig` header, plus the marker path a
    configured `gpg.program` would touch. No signing key is involved: git hands the
    block to the program before deciding whether it is well formed."""
    root = _repo(tmp_path)
    marker = tmp_path / "EXECUTED"
    spawn = root / "spawn.sh"
    spawn.write_text(f"#!/bin/sh\ntouch {marker}\ncat\n", encoding="utf-8")
    spawn.chmod(0o755)

    def git(*args: str) -> str:
        out = subprocess.run(
            ["git", "-C", str(root), *args], check=True, capture_output=True
        )
        return out.stdout.decode().strip()

    ident = "Probe <probe@example.invalid> 0 +0000"
    body = (
        f"tree {git('rev-parse', 'HEAD^{tree}')}\n"
        f"parent {git('rev-parse', 'HEAD')}\n"
        f"author {ident}\ncommitter {ident}\n"
        f"gpgsig {FAKE_SIGNATURE}\n\nsigned\n"
    )
    sha = subprocess.run(
        ["git", "-C", str(root), "hash-object", "-t", "commit", "-w", "--stdin"],
        input=body.encode("utf-8"), check=True, capture_output=True,
    ).stdout.decode().strip()
    git("update-ref", "refs/heads/SIGNED", sha)

    for key, value in (("log.showSignature", "true"), ("gpg.program", "./spawn.sh")):
        git("config", key, value)
    return root, marker


def test_signature_verification_still_spawns_the_configured_program(tmp_path: Path):
    """The negative control. Both keys AND a signed object are required -- each alone is
    harmless, which is why this is a composite. If this ever stops failing under bare git,
    the guard below proves nothing and the pair should be revisited, not deleted."""
    root, marker = _signed_repo(tmp_path)

    subprocess.run(["git", "-C", str(root), *SIGNED_LOG_ARGV], capture_output=True)

    assert marker.exists()


def test_run_git_never_reaches_signature_verification(tmp_path: Path):
    """Two assertions, because there are two ways to get this wrong, and the marker only
    catches one. The marker proves the attacker's binary did not run. The EMPTY STDERR
    proves no verification was attempted at all -- hardening `gpg.program=` instead leaves
    verification enabled, and git then tries to run a program regardless: the blanked name
    (`error: cannot run : No such file or directory`) here, or the default `gpg` on PATH in
    a repo where the attacker configured no program. Both write to stderr; neither clears
    the marker, so `assert not marker.exists()` alone would green-light the weak fix."""
    root, marker = _signed_repo(tmp_path)

    completed = run_git(root, *SIGNED_LOG_ARGV)

    assert not marker.exists()
    assert completed.stderr == b""
    assert len(completed.stdout.splitlines()) == 2  # the signed commit and its parent
```

Any *other* `EXECUTES` key is single and takes this simpler shape — substitute the real
key and op, and write the control first here too:

```python
def test_a_configured_executing_key_does_not_fire_under_run_git(tmp_path: Path):
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
    assert marker.exists()  # the control: the vector reproduces
    marker.unlink()

    run_git(root, "<op>", "<args...>")
    assert not marker.exists()
```

If Task 1 found no `EXECUTES` key beyond the signature pair, write only the pair above and
note it in the commit.

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


@pytest.mark.parametrize(
    "ungenerated",
    [
        "2026-07-30-a",            # no agent at all; the whole remainder is one token
        "2026-07-30-lens-a3f",     # short id is 3 characters; _SHORT_ID_RE demands 4+
        "2026-07-30-lens-A3F1",    # short id is not lowercase
        "2026-07-30-Lens-a3f1",    # agent is not a kebab-case slug
        "2026-07-30-lens_x-a3f1",  # underscore is not in the agent alphabet
        "2026-07-30--a3f1",        # empty agent
    ],
)
def test_a_handle_no_generate_run_id_call_could_produce_is_refused(
    tmp_path, monkeypatch, ungenerated
):
    """Structure is not enough. A handle that is a safe path component but that
    `generate_run_id` could never have emitted names no run, and resolving it would
    silently create an addressable directory for a run that does not exist.

    The split works despite hyphenated agent slugs because a short id cannot contain a
    hyphen, so the last hyphen is always the boundary."""
    monkeypatch.setenv(CONTROL_PLANE_ENV, str(tmp_path / "cp"))

    with pytest.raises(ControlPlaneError):
        run_dir(_project(tmp_path, "alpha"), ungenerated)


def test_a_hyphenated_agent_slug_still_resolves(tmp_path, monkeypatch):
    """The regression guard for the split: `review-plans` must survive rpartition."""
    monkeypatch.setenv(CONTROL_PLANE_ENV, str(tmp_path / "cp"))

    assert run_slug("run:2026-07-30-review-plans-a3f1") == "2026-07-30-review-plans-a3f1"


@pytest.mark.parametrize("variable", [CONTROL_PLANE_ENV, "XDG_STATE_HOME"])
def test_a_relative_control_plane_root_is_refused(tmp_path, monkeypatch, variable):
    monkeypatch.delenv(CONTROL_PLANE_ENV, raising=False)
    monkeypatch.setenv(variable, "relative/state")

    with pytest.raises(ControlPlaneError):
        control_plane_root(_project(tmp_path, "alpha"))


def test_the_working_directory_does_not_change_where_a_run_resolves(tmp_path, monkeypatch):
    """The companion guard to the rejection above, and it is deliberately trivial TODAY.

    It holds only because a relative root is refused outright; it is here so that softening
    that rejection into a "helpful" resolve-against-cwd fails this test rather than shipping.
    `start` and `finish` are separate processes and need not share a working directory, so a
    control plane that moved with the cwd would send `finish` to a different baseline, find
    no journal, and report every citation unserved -- a configuration error wearing the
    costume of actor misbehaviour."""
    monkeypatch.setenv(CONTROL_PLANE_ENV, str(tmp_path / "cp"))
    project = _project(tmp_path, "alpha")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()

    monkeypatch.chdir(tmp_path)
    from_here = run_dir(project, HANDLE)
    monkeypatch.chdir(elsewhere)
    from_there = run_dir(project, HANDLE)

    assert from_here == from_there


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
from datetime import date
from pathlib import Path

from science_model.autonomous_runs import (
    RUN_ID_PREFIX,
    RunRecordError,
    validate_run_identity,
)

from science_tool.autonomy.baseline import reject_baseline_inside_project

#: Overrides the XDG state location. Still containment-checked: an environment variable must
#: not be able to relocate the control plane into the tree the actor writes.
CONTROL_PLANE_ENV = "SCIENCE_CONTROL_PLANE"

_DATE_LENGTH = len("YYYY-MM-DD")


class ControlPlaneError(ValueError):
    """A handle or root that cannot address a run."""


def _absolute_or_refuse(value: str, variable: str) -> Path:
    """A relative control-plane root is refused, not resolved.

    Resolving it would bind the control plane to the current directory AT THE MOMENT OF
    THE CALL. `science autonomy start` and `science autonomy finish` are separate processes
    run by a supervisor that need not share a working directory, so the same run id would
    address two different baselines -- `finish` would find no journal, and every citation
    against that run would come back unserved. The failure is silent and looks like actor
    misbehaviour, which is the worst possible disguise for a configuration error.
    """
    path = Path(value).expanduser()
    if not path.is_absolute():
        raise ControlPlaneError(
            f"{variable} must be an absolute path, got {value!r}: a relative control plane "
            "resolves against the current directory, so a run opened from one directory "
            "would not be found from another"
        )
    return path


def control_plane_root(project_root: Path) -> Path:
    """Where every project's run directories live.

    Raises `BaselineError` -- not `ControlPlaneError` -- when the resolved root is inside
    the project: it is the same containment failure `write_baseline` refuses, judged by the
    same function, and one failure should not have two names.
    """
    configured = os.environ.get(CONTROL_PLANE_ENV)
    if configured:
        root = _absolute_or_refuse(configured, CONTROL_PLANE_ENV)
    else:
        xdg_state_home = os.environ.get("XDG_STATE_HOME")
        base = (
            _absolute_or_refuse(xdg_state_home, "XDG_STATE_HOME")
            if xdg_state_home
            else Path.home() / ".local" / "state"
        )
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
    """The bare `<date>-<agent>-<short-id>` form, refusing anything no run could carry.

    Validated as a GENERATED RUN ID, not merely as a safe path component, and validated
    BEFORE it is joined to anything. A check applied to the joined path has already lost:
    `run_dir(project, "../../elsewhere")` would have produced a real directory belonging to
    another project, and a containment check on the result would then be arguing with a path
    that should never have been built.

    The split is unambiguous despite the agent slug containing hyphens, because
    `_SHORT_ID_RE` forbids them in the short id: the LAST hyphen is always the one between
    agent and suffix. That is what lets a bare handle -- which names no agent of its own --
    still be checked by the same `validate_run_identity` that guards `generate_run_id`,
    rather than by a looser shape test that would admit `2026-07-30-a`.
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
    agent, separator, short_id = slug[_DATE_LENGTH + 1 :].rpartition("-")
    if not separator:
        raise ControlPlaneError(
            f"run handle must be <date>-<agent>-<short-id>; {handle!r} carries no short id"
        )
    try:
        validate_run_identity(agent=agent, short_id=short_id)
    except RunRecordError as exc:
        raise ControlPlaneError(f"{handle!r} is not a run id that could have been generated: {exc}") from exc
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
`"not-a-run-id"`, check which branch rejected it: a handle shorter than the date length must
fail at the length check, not reach `rpartition`. If a case in
`test_a_handle_no_generate_run_id_call_could_produce_is_refused` passes when it should fail,
confirm `validate_run_identity` is being called rather than the split being trusted on its
own — the split establishes *where* the boundary is, never that either side is valid.

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

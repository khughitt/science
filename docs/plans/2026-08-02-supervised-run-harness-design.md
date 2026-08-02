# Supervised run harness — design (autonomous-audit Spec 2b)

**Status:** designed, unbuilt (revision 5)
**Spec 2b** of the autonomous-audit program (§0), scoped to **the loop, not the fleet**.

**Revision 2** closes five defects found in review of revision 1. Two are omissions of a
contract the loop cannot be built without — the harness's own signature (§3.4) and the
authority `ingest_report` requires (§5.4). Two are the same mistake in opposite directions: a
rule stated too narrowly (git calls, §3.5) and a guarantee stated too broadly (the restore
postcondition, §4.1) — the second would have destroyed a caller's uncommitted work. The fifth
is a tail that assumed every outcome carries a record (§7), which `finish_run` does not
promise.

**Revision 3** closes four more, all of the same kind: **a value the design named without
pinning.** The actor was "`science health`" and not an interpreter (§3.2); the failure contract
was an exit code with no library counterpart (§3.4.1); two wall-clock instants were used and
never sourced (§3.4.2); and the supervisor's commit identity was promised as fixed without
being written down (§3.4.3), though it is observable in every repository's history. A named
value that is not pinned is a value an implementer picks.

**Revision 5** is revision 4's own defect, one layer in. Two of the four rows revision 4
"repaired" were repointed to a nearer test that still could not execute the mutation — rows 16
and 19, both of which live in `_settle` (§8.4). The repair had matched the row to the right
*subject* and never asked which inputs put control on the mutated line.

**Revision 4** comes from review of the implementation plan, and its findings are about
**claims that no test could reach**. Four mutation rows named a condition their test never
induced (§8.4); `-P` and the neutral cwd turned out to be independent defences, so neither was
individually observable and the honest row removes both (§3.2); and "every orchestration
failure raises `HarnessError`" was a statement about intent rather than about the several
functions in the loop that raise on their own (§3.4.1). It also aligns §3.5's helper names with
the ones the plan actually builds — a design that names a different interface than the code is
no longer authoritative over it.

This slice builds one thing: a supervised autonomous run, end to end, with a deterministic
actor. It ships no concurrency, no assignment records, no LLM actor, and no dispatch policy.
The name "dispatch harness" comes from the program map; what 2b actually answers is *how a
supervised run is shaped*, and 2c inherits that shape when it introduces the first real
reviewer.

Every empirical claim below was measured against a scratch project on `main` at `1c3ce165`.
Where a claim is a reproduction, the observed output is quoted.

## 0. Where this sits

| Slice | Owns | State |
|---|---|---|
| Spec 1 | finding convergence — one emitted `AuditFinding`, fingerprint identity, the `doc/audits/cases/` store, trusted ingestion | **shipped** |
| Spec 2a | the evidence broker — what an agent was shown, recorded and replayable; the addressable control plane | **shipped**, seven plans, 4c merged at `1c11c922` |
| **Spec 2b** | **the supervised run loop — this document** | **designed here** |
| Spec 2c | `/science:review-plans` — the first lens agent | not designed |
| Spec 3 | how many confirmations promote a finding, and by whose authority | not designed |

2b consumes Spec 1's ingestion boundary and the autonomy envelope's S1 contract
(`start_run`, `finish_run`, the path gate, the commit marks). It consumes nothing from 2a:
the deterministic actor never touches the broker, so 2b's runs are **unbrokered**. 2a's
contribution to this program arrives with 2c, which needs `run_dir` to address a reviewer's
session.

## 1. The problem

Nothing calls `start_run`, an actor, and `finish_run` in sequence. The envelope shipped the
contract a run happens inside; Spec 1 shipped the boundary its output crosses; neither
shipped the thing that runs. There is no orchestrator and no command surface for one —
`commands/` holds nothing autonomy-related.

**The mechanism works; the wiring is unexercised.** Running it by hand end to end produces
cases:

```
$ science health --project-root <p> --format json --output <p>/doc/audits/run-report.json
$ science findings ingest <p>/doc/audits/run-report.json --project-root <p> \
    --attest-ingestion-ref … --attest-generated-at … --attest-producer-id … (×16)
16 new case(s), 16 occurrence(s) appended, 0 skipped as already recorded
```

So the frequently-repeated claim that "Spec 1's ingestion path has never processed a report"
is **false about the mechanism**. What is true, and is the gap 2b closes: no test feeds real
`science health` output to ingestion — every case in `test_findings_ingest.py` hand-builds
findings under a synthetic `health_checks` producer — and no supervisor exists to drive the
two commands as one attested run.

### 1.1 Three defects the first end-to-end run exposed

These were found by running the loop, not by reading it. Each is load-bearing for the design.

**`start_run` leaves the tree dirty before the actor exists.** `_capture`
(`autonomy/lifecycle.py:132`) materializes the graph, and `materialize_graph` writes into the
project. Measured immediately after `science autonomy start` on a clean repository:

```
$ git status --porcelain
?? knowledge/
```

A supervisor that then stages the actor's output with `git add -A` sweeps its own write into
the actor's attested range. Under `report-only` the gate denies it, and the run quarantines for
the supervisor's own materialization:

```
quarantined: 0 belief-basis delta(s), 1 path-gate denial(s), 1 commit-mark issue(s)
  denied: knowledge/graph.trig -- tier 'report-only' may write only the run's own report path
```

**The condition, stated precisely, because it decides how this is tested.** The residue appears
when the committed `knowledge/graph.trig` differs from a fresh materialization — most commonly
when the project has never materialized and the file is absent, which is the state of any
project that has not run `science graph`. Measured the other way: with the graph already
committed and the rebuild byte-identical, `start_run` leaves `git status --porcelain` **empty**.

That is why `test_autonomy_lifecycle.py`'s `project` fixture materializes and commits before
`git init` — its docstring says so outright, that otherwise "every dirty-tree test below would
then pass because of the supervisor's own write instead of the condition it names." The same
fixture is therefore **unusable** for testing this defect: against it, both the fixed and the
broken implementation leave a clean tree. §8 row 1 requires a project whose graph is absent.

**The capture commit's author identity is fixed and undocumented.** `verify_marks`
(`autonomy/marks.py:55`) requires the commit author *name* to equal the run's `agent` and the
*email* to equal `AGENT_EMAIL` — `agent@science.local` (`marks.py:20`). Nothing surfaces this
to whoever writes the commit. The same run above also reported:

```
  mark: 005cae177fb9 -- author health-audit <a@a> is not this run's agent
        health-audit <agent@science.local>
```

**Committing the run record on the run's own branch makes every completed run an error.**
`_marked_commits` (`validate/checks/autonomous_runs.py:116`) scans `--all` deliberately — a
quarantined run keeps its branch, so scanning `HEAD` alone would hide exactly the commits the
check exists to find. `load_run_records` reads `runs/` from the *current tree*. Put the record
only on `auto/<slug>`, return to the starting branch, and the two land on opposite sides:

```
ERROR commit bb8f5afb4fa7 carries Science-Run: run:2026-08-02-health-audit-a1b2 but there is
no run record for it -- unwired: autonomous commits with no attestation [autonomous-runs.check]
```

With the record committed on the starting branch instead, the same project validates with the
check silent (`grep -c "autonomous-runs.check"` → `0`).

## 2. Scope

**In scope.**

1. `autonomy/harness.py` — the supervised run loop, as a library function returning a result.
2. `science autonomy run` — the CLI surface over it.
3. `science health --ingestion-ref` / `--generated-at` — so the attestation is dictated
   rather than read back.
4. `graph/health.py::expected_producer_ids` — the shared producer-set derivation.
5. The `start_run` restore postcondition (§4.1).
6. `autonomy/git.py` extended to cover the harness's write subcommands (§3.5).
7. `findings/ingest.py::ingestion_authority` — the shared registry/context derivation (§5.4).

**Out of scope, deliberately.** Concurrency and N-way dispatch; assignment records; actor
selection (§3.2); LLM actors; brokered runs; belief-neutral actors (§4.4); served-evidence
retention; token and wall-clock caps.

**Adjacent 2a closure carried on this branch but not part of 2b's design** (§10): the 2a
design's two stale status rows, and the `InlineInput.lines` coverage-ceiling defect.

## 3. Architecture

### 3.1 The supervisor is deterministic code

Every value the supervisor attests — the tier, the run id, the verdict, the ingestion
provenance — is worth something only because its authority lives outside the actor. An
orchestrator that is itself a language-model session reasoning about the work is not outside
the actor; its attestations are self-attestation, which is the failure the envelope was built
to prevent. The harness is therefore ordinary Python invoked by a CLI command, and 2a's
statement that sessions are "held in the supervisor" already presumes this: a chat session
cannot hold a `Session` object.

**The actor owns bytes at one path. The harness owns everything else** — the working tree,
the branch, every commit, the commit identity, and every attested value.

### 3.2 There is one actor, and it is not selectable

`science autonomy run` runs `science health` as a subprocess. There is no `--actor` flag.

With exactly one actor, a selection flag is an interface designed from a single example. 2c
introduces the second actor and the generalization falls out of having two — including the
question this slice cannot answer well, which is how a generic actor learns the report path
and the dictated provenance. Declining to answer it now also keeps the toolkit from acquiring
"spawn an arbitrary command" as a capability in the slice that introduces supervision.

The subprocess boundary is kept even though the actor is our own code: the path gate and the
capture commit need real writes in the real tree, and the subprocess seam is precisely what 2c
replaces. Running health in-process would let harness and actor share state and would exercise
the trusted ingestion path rather than the untrusted one.

**The invocation is pinned to the supervisor's own installation.** "Runs `science health`"
would permit a bare `science` resolved from `PATH` — a *different toolkit revision* than the
one the supervisor attests in `toolkit_revision`, which nothing would notice:
`assert_toolkit_matches` checks the supervisor's toolkit, not the actor's. The argv is

```python
[sys.executable, "-P", "-m", "science_tool", "health", "--project-root", str(project_root), …]
```

`sys.executable` is the interpreter already running the supervisor, so the actor is the same
installation by construction. Measured: exit 0, report written.

**Two independent defences keep the project off the actor's `sys.path`, and each alone
suffices.** `-m` puts the current directory on `sys.path` as `''`; `cwd` is a
supervisor-created temporary directory, so that entry names the temp dir and not the project.
`-P` removes the entry altogether. Measured under Python 3.14: without `-P`, `sys.path[:3]`
begins `['', …]` where `''` resolves to the neutral cwd; with `-P` it begins with the stdlib
zip. Either measure alone already makes a project-local `science_tool/` unreachable.

**That redundancy has a testing consequence, and it is stated rather than papered over: neither
measure is individually certifiable by mutation.** Removing `-P` while the cwd stays neutral
changes nothing observable, and so does the reverse. §8 row 23 therefore removes **both** — the
only mutation that actually reaches the shadowing package. Writing two rows, one per flag,
would put two mutations in the ledger that cannot fail.

### 3.3 The report path is derived

`doc/audits/reports/<run-slug>.json`, from the run id. It cannot collide across runs, needs no
flag, and is the single path `report-only` permits (`autonomy/path_gate.py:123`).

### 3.4 The contract

```python
class HarnessError(RuntimeError):
    """An orchestration step failed. No outcome exists."""

class HarnessOutcome(BaseModel):          # frozen, extra="forbid"
    run_id: str
    disposition: RunDisposition
    reason: str
    actor_exit_code: int
    capture_commit: str                   # a returned outcome always has one
    post_verdict_commit: str | None       # None when there was nothing to settle (§4.5)
    record_written: bool
    ingestion: IngestOutcome | None
    ingestion_refusal: str | None

def run_supervised_audit(
    project_root: Path,
    *,
    started: datetime,
    short_id: str,
) -> HarnessOutcome
```

**Everything else is fixed, because there is one actor.** Exposing a flag for a value the
slice cannot vary invites a false claim in an attested record.

| Value | Fixed to | Why |
|---|---|---|
| `agent` | `health-audit` | a role, not a model — the only actor 2b has |
| `model` | `deterministic` | no model executed this run; the record should say so rather than name one |
| `tier` | `report-only` | `science health` writes its report and nothing else |
| check selection | the full set | an audit run that skipped checks would under-report; `--fast` yields a partial audit. `expected_producer_ids` still accepts a selection, and §8.1 exercises the others at unit level |
| `tokens` | `None` | a deterministic actor consumes none |
| `wall_clock_seconds` | measured across the actor subprocess | caps are out of scope; accounting is not |

`started` and `short_id` are parameters rather than internals so the loop is testable without
patching a clock or a random source. The CLI supplies `datetime.now(UTC)` and four hex
characters from `secrets.token_hex(2)`, matching the existing run-id spelling.

### 3.4.1 Failure is an exception, not a field

**Every orchestration failure, at any stage, raises `HarnessError`; the CLI maps it to exit 3.**
A `HarnessOutcome` is returned only when the loop reached a verdict.

Revision 2 had these disagreeing. Exit 3 was described as "any step before `finish_run`", which
left a step-9 switch, commit, or restore failure with no code at all — and `HarnessOutcome`
could not represent a failure before the capture commit, since every other field would have
been meaningless. Making failure an exception settles both, and it is why `capture_commit` is
now non-optional: an outcome that exists is an outcome whose capture commit exists.

`unwired` is *not* a harness failure. It is a verdict — the run was judged and could not be
seen — so it returns an outcome and exits 2.

**"Every failure raises `HarnessError`" is a claim about *normalization*, not about the
functions the loop happens to call.** `current_branch`, `run_dir`, `stage_all`, the report
directory's `mkdir`, and the actor subprocess itself all raise `GitError` or `OSError` of their
own, and the CLI catches only `HarnessError` — so an unnormalized path exits 1 with a traceback
instead of 3. Each orchestration step is wrapped at the library boundary and re-raised as
`HarnessError` naming the step. The ingestion step's refusal set is `IngestError`, `OSError`,
and `ValueError` together: `load_report` reaches the filesystem, so an unreadable report is a
refusal to ingest, not a reason to abandon the tree before step 9.

### 3.4.2 Which clock, and when

Three wall-clock instants and one duration, all from the supervisor:

| Value | Read | Source |
|---|---|---|
| `started` | at loop entry, before `start_run` | `datetime.now(UTC)` |
| `generated_at` | immediately before spawning the actor | `datetime.now(UTC).isoformat(timespec="microseconds")` |
| `ended` | immediately after the actor's capture commit, before `finish_run` | `datetime.now(UTC)` |
| `wall_clock_seconds` | around the subprocess only | `perf_counter()` |

`perf_counter` for the duration and wall clocks for the instants: a duration must not go
backwards when the system clock is adjusted, and a recorded instant must be comparable across
machines.

`generated_at` is a **string**, formatted once and used twice — passed to the actor as
`--generated-at` and attested unchanged. That round-trips exactly because
`AuditReport.generated_at` is `str` with a validating-but-non-normalizing field validator
(`audit/report.py:218-233`): the report echoes the supervisor's spelling verbatim, and
`_assert_attested_provenance` compares strings. Had it been a `datetime`, re-serialization
could have changed the spelling and refused every ingestion.

### 3.4.3 The two identities, named

Both are observable in every repository's history, so both are contract, not implementation.

| Constant | Value | Used for |
|---|---|---|
| `AGENT_EMAIL` (existing, `marks.py:20`) | `agent@science.local` | capture commit **author**, with the run's `agent` as the name |
| `SUPERVISOR_NAME` (new) | `science-supervisor` | capture commit committer; post-verdict commit author and committer |
| `SUPERVISOR_EMAIL` (new) | `supervisor@science.local` | the same |

The new pair lands in `autonomy/marks.py` beside `AGENT_EMAIL`, because that module already
owns the question of who a commit claims to be.

**The baseline** goes to `control_plane.run_dir(project_root, run_id)/baseline.json` — outside
the project root, as `start_run` requires, addressable from the run id, and retained after the
run for triage. Using the control plane's addressing is not the same as opening a brokered
run: `evidence` stays `None` and no journal is created. An aborted run leaves its baseline in
place.

**The commit identities are different on purpose.** The capture commit is *authored* by
`<agent> <agent@science.local>`, which is what `verify_marks` reads (`%an`/`%ae`), and
*committed* by the supervisor. The post-verdict commit is both authored and committed by the
supervisor and carries no trailer. That is the whole semantic in two commits: the actor
produced these bytes, the supervisor froze them. Both identities are pinned with `-c
user.name` / `-c user.email` (§3.4.3) so the loop works in a repository with no configured
identity.

**CLI.** `science autonomy run --project-root PATH [--format table|json]`. Exit codes extend
`autonomy finish`'s rather than inventing a scheme:

| Code | Meaning |
|---|---|
| 0 | `clean`, and the report was ingested |
| 1 | `quarantined` |
| 2 | `unwired` |
| 3 | `HarnessError` — an orchestration step failed at any stage (§3.4.1) |
| 4 | `clean`, but ingestion refused |

Code 4 exists because **an ingestion refusal is a failure of the run's purpose even when the
autonomous disposition is clean.** A run that produced an unusable report and reported success
would be the silent direction this program refuses everywhere else.

### 3.5 Every git call goes through `run_git`

The loop introduces `checkout`, `clean`, `add`, and `commit` — the first *write* subcommands
in the autonomy surface. Every one of them goes through `autonomy/git.py::run_git`, with the
return code checked; the harness builds no argv of its own.

The reason is the one that module already states: **the actor owns `.git/config`**. It is
untracked, absent from `base..head`, and invisible to `git status`, so neither the path gate
nor the belief-basis capture can see it change — and several keys name a *program* git then
runs with the supervisor's privileges. A git call that skips the gateway is a call the actor
can turn into arbitrary execution, and no layer of this design would report it.

Most of what the new subcommands need is already there. `run_git` applies `_HARDENING` plus
`_filter_driver_overrides(repo_root)` on **every** call (`git.py:435`), so
`core.hooksPath=/dev/null` disarms `commit`'s `pre-commit` / `prepare-commit-msg` /
`commit-msg` / `post-commit` hooks and `checkout`'s `post-checkout`, and the dynamic filter
blanking covers the `clean` filter `add` would otherwise run.

**One gap is genuinely new.** `log.showSignature=false` governs signature *verification* under
`log`; it says nothing about *signing* under `commit`. `commit.gpgsign=true` with
`gpg.program` pointing at an actor-supplied script reaches a program during the harness's own
commit. The commit invocation therefore pins `--no-gpg-sign`, and supplies its message with
`-m` so `core.editor` is never reached.

**The argv is built in the gateway, not at the call site.** `--no-gpg-sign` passed by the
harness is a flag that can be forgotten by the next caller; `git.py`'s own rule is that "what
none of them may differ on is the argv, which is why it is built here and nowhere else". The
four write subcommands therefore get named functions in `autonomy/git.py` — `current_branch`,
`worktree_status`, `create_branch`, `switch_branch`, `restore_worktree`, `stage_all`,
`commit_tree` — each building its own argv and failing closed on a non-zero exit. The harness
passes values, never flags.

**The hardening set is probed, not assumed.** `git.py`'s standing rule is that a key is pinned
only where it demonstrably reaches a program under that subcommand, and each row in its
docstring records what was built as a working attack. The four new subcommands get the same
treatment, and the results — including the inert ones — are recorded there in the same form.
Asserting the set by analogy to `status` would be exactly the reasoning that module exists to
replace.

## 4. The loop

Nine steps. The harness aborts on any failure before `finish_run`, leaving every branch and
every file intact for triage and writing no run record — which is `start_run`'s own stated
posture: it writes no record so that "a supervisor that dies mid-run leaves an unattested
branch rather than a half-attested one."

| # | Step | On failure |
|---|---|---|
| 1 | Assert HEAD is a named branch; remember it as the starting branch | abort |
| 2 | `start_run` → baseline (restores the tree itself, §4.1) | raises; abort |
| 3 | `git checkout -b auto/<slug>`, exclusively | abort — an existing branch is a run-id collision |
| 4 | Spawn `science health` as a subprocess | exit ∉ {0, 2} → abort (§4.2) |
| 5 | Assert HEAD is still `baseline.branch`; detached HEAD counts as a mismatch | abort, work left intact |
| 6 | `git add -A`; commit as `<agent> <agent@science.local>` with `Science-Run: <run-id>` | abort |
| 7 | `finish_run(head=HEAD, report_path=…)` | returns `unwired`; continue to 9 |
| 8 | If the disposition is `clean`: load and ingest (§5) | refusal is reported; continue to 9 |
| 9 | Switch to the starting branch, then settle the tree per §4.5 | abort naming the dirty tree |

Step 1 exists because step 9 otherwise has no defined destination.

Step 9 runs on **every** disposition. A quarantined run dirties the tree exactly as a clean one
does — `runs/<slug>.md` from `_finalize`, plus `knowledge/graph.trig` from `finish_run`'s
re-materialization — and the next `start_run` refuses a dirty tree. Only step 8 is conditional
on the verdict.

The actor's report stays on the retained `auto/<slug>` branch. The record, the rebuilt graph,
and any cases land on the starting branch, outside `base..head`, where
`check_autonomous_runs` reads them.

### 4.1 `start_run` restores the tree

The residue in §1.1 is a defect in shipped code, not merely an inconvenience for the harness:
`science autonomy start` leaves an untracked `knowledge/graph.trig` behind today. The fix
belongs in `autonomy/lifecycle.py`, and the harness inherits it.

**The postcondition, scoped precisely:** *once `assert_repository_is_at` has succeeded and
capture has begun*, `start_run` removes its own materialization residue before returning or
raising, leaving the working tree at `base_commit`.

The scope matters. The broader phrasing — "when `start_run` returns or raises, the tree is at
`base_commit`" — also covers the case where `assert_repository_is_at` itself fails, and there
the tree is dirty with the **caller's** uncommitted work. Restoring then would destroy it. A
dirty input tree must be refused byte-for-byte unchanged, which is certified by its own test
(§8, row 15).

**It must hold on the error paths.** `start_run` materializes at `_capture` and can then raise
at least four more times: an unwired basis, an untraversable history, an uncitable tree, a
failed `write_baseline`. Residue after any of those leaves the project dirty and the *next*
`start_run` unable to open. The restore is therefore a tight `try`/`finally` around `_capture`
alone — restore and re-assert `base_commit` immediately, **before** the unwired, history,
citability, and baseline-writing results are processed — so that no later branch can return or
raise past it.

**Restore by predicate, not by roster.** `git checkout -- .` followed by `git clean -fd`
restores *to `base_commit`*. The tempting alternative — restoring `knowledge/graph.trig` by
name, since it is the only file materialization writes today — has a hole by construction: a
second materialized file would survive silently. The predicate form is exactly safe because
`assert_repository_is_at` proved the tree clean *including untracked files* immediately
before, so everything present afterwards is `start_run`'s own residue.

`finish_run` is deliberately **not** given the same postcondition. Its materialization happens
after the range is fixed and reflects the actor's work; step 9 commits it.

### 4.2 The actor's exit code

`science health` writes a complete report and *then* exits 2 when the project's acceptance
configuration is invalid (`graph/health_cli.py`, after `emit` and `sink.flush()`). Exit 2 is
therefore not actor failure. The harness accepts **0 and 2**; any other exit aborts. The
observed exit code is surfaced in the harness result.

### 4.3 Branch identity

`baseline.branch` is `auto/<run-id without the "run:" prefix>`, set by `start_run`, created by
nobody today — a clean run is achievable with no branch at all, because `finish_run` never
checks. The harness closes that: it creates the branch, and after the actor exits it asserts
HEAD still names it. `git rev-parse --abbrev-ref HEAD` returns `HEAD` on a detached HEAD, so
a string comparison already refuses that case; it is asserted deliberately rather than relied
on as an accident.

On mismatch the harness aborts without capture, `finish_run`, ingestion, or a record. Putting
this check inside `finish_run` would be worse: its record *requires* a `branch`, so on mismatch
it could only persist the intended branch as though it had been observed.

### 4.4 What step 9 assumes

Carrying uncommitted output across the branch switch is safe here because 2b's post-verdict
artifacts are untracked (`runs/`, `doc/audits/cases/`) or unchanged — measured.

A **belief-neutral** actor breaks that assumption. It edits entities and rebuilds
`knowledge/graph.trig`, leaving a modified *tracked* file whose base is `auto`'s HEAD while the
starting branch holds `base_commit`'s version. `git checkout` then either refuses or carries a
graph inconsistent with a branch that lacks the run's entity edits. **This is an open ruling
for whichever slice first ships a belief-neutral actor**, named rather than guessed at.

### 4.5 Settling the tree: a record may not exist

`finish_run` returns `unwired` **with `record=None`** on five paths — an unreadable or
mismatched baseline, an unsealable exposure, a record that fails model validation, and a
record the writer refuses (`lifecycle.py:543-563`). Revision 1's tail said the record "already
exists"; on those paths it does not, and nothing was written.

Step 9 therefore branches on whether a record was written, not on the disposition:

- **A record was written** (`clean`, `quarantined`, or `unwired`-with-identity). Commit the
  supervisor's output on the starting branch — `runs/<slug>.md`, `knowledge/graph.trig`, and
  any cases — with the supervisor identity and no trailer. `post_verdict_commit` is that sha.
- **No record was written.** The run produced no attestation, so there is nothing to publish
  and derived state must not be committed on its behalf. Restore instead: `checkout -- .` plus
  `clean -fd` on the starting branch. `post_verdict_commit` is `None` and `record_written` is
  `False`.

The restore is safe by §4.1's argument, unchanged: `start_run` proved the tree clean including
untracked files, and the actor's own work is committed on `auto/<slug>`, so everything the
restore removes is supervisor residue.

Either branch may find **nothing to settle** — a `finish_run` that failed before `_capture`
leaves no materialization behind. The harness checks `status --porcelain` first and skips the
commit rather than passing `--allow-empty`, which would record a commit that means nothing.

Step 9 ends with the tree clean on the starting branch in every case. That is the property the
next `start_run` depends on, and it is what the step exists to guarantee.

## 5. The attestation

### 5.1 Dictated, not read back

`science health` gains `--ingestion-ref` and `--generated-at`, required together; omitting both
preserves today's behaviour. `execute_health_report` already accepts both — only
`graph/health_cli.py:217-218` invents them, as `health:{uuid4().hex}` and `datetime.now(...)`.

The harness supplies **the run id** as the ingestion ref. Every case's provenance then resolves
to the run that found it, where `health:<random uuid>` resolves to nothing.

It dictates `generated_at` from the supervisor's clock. The precedent is 2a's own ruling that
`Review.at` is attested, not clocked: the value means *the instant the supervisor commissioned
this report*, which is what an attested provenance timestamp should mean. Reading the actor's
timestamp and attesting it back attests nothing.

### 5.2 The producer set

`graph/health.py::expected_producer_ids(checks, skip_checks, fast) -> frozenset[str]` is built
from the same `_select_health_checks` that `execute_health_report` calls, plus
`SCHEMA_INVALID_PRODUCER.producer_id` under the same sources condition
(`health.py:130-155`). There is no second list to drift.

Measured: 15 health checks with 15 unique producer ids, 8 requiring sources; a full run attests
those 15 plus `schema_invalid` — 16, which is what the successful ingestion above supplied.
`schema_invalid` never appears in `--list-checks`, which is why the naive set is wrong and why
a hand-driven operator discovers the right one only by failing once.

Enforcement is the mechanism Spec 1 already ships: ingestion refuses an inexact producer set, so
a wrong prediction fails closed and loudly. 2b adds no new trust mechanism here.

### 5.3 The report is still untrusted

The harness calls `load_report(project_root, report_path)` (`findings/ingest.py:153`) before
`ingest_report`. **Supervisor-chosen arguments do not make the bytes trusted** — the actor still
wrote them. `load_report` enforces path containment, symlink refusal, byte-size and JSON-nesting
ceilings, schema and version validation, and the finding-count limit. The harness then
constructs its own `IngestionProvenance` and ingests the loaded report in-process.

### 5.4 Where the registry and the context come from

`ingest_report(project_root, report, registry, *, provenance, context, actor)`
(`findings/ingest.py:511`) requires a `FindingRegistry` and an `IngestionContext`, and **both
are authority, not data**. Neither may come from the report.

The derivation is Spec 1's, spelled out here because three wrong answers are each one step
away: reusing anything the actor produced; reusing the health run's `load_project_sources(...,
strict_identity=False)`, which is lenient on purpose so materialization can carry identity
conflicts into its audit gate; or importing `findings/cli.py::_load_ingestion_context`, a
private CLI helper, into a library.

```python
def ingestion_authority(project_root: Path) -> tuple[FindingRegistry, IngestionContext]
```

lands in `findings/ingest.py` beside the boundary it serves, calling `load_project_sources`
with its **strict defaults** — `strict_identity=True`, so an identity conflict refuses the
write — and `build_registry_for_entity_registry(sources.registry)`. The `findings ingest` CLI
is cut over to it, so there is one spelling rather than two that can drift.

## 6. Toolkit changes

| File | Change |
|---|---|
| `autonomy/harness.py` | new — the loop of §4 |
| `autonomy/cli.py` | new `run` command |
| `autonomy/lifecycle.py` | `start_run` restore postcondition (§4.1) |
| `autonomy/git.py` | probe and pin the four write subcommands (§3.5) |
| `autonomy/marks.py` | `SUPERVISOR_NAME` / `SUPERVISOR_EMAIL` (§3.4.3) |
| `findings/ingest.py` | `ingestion_authority` (§5.4) |
| `findings/cli.py` | cut `_load_ingestion_context` over to it |
| `graph/health.py` | `expected_producer_ids` |
| `graph/health_cli.py` | `--ingestion-ref` / `--generated-at` |
| `budget/registry.py` | classify `autonomy run` (§6.1) |
| `docs/user-guide/cli-and-workflows.md` | the `run` command surface |

### 6.1 Registering the command is enforced, not optional

`test_budget_boundary.py::test_every_leaf_command_is_classified` requires every leaf CLI
command to appear in `BUDGETS`, `DEFERRED`, or `EXEMPTIONS`. Its three siblings —
`autonomy path-gate`, `autonomy start`, `autonomy finish` — are all `DeferredCommand`
entries at `budget/registry.py:281-292`, and `autonomy run` joins them: its output is one
fixed summary per invocation plus whatever `finish_run` reports, so it is bounded by the same
argument. Registering the surface also means the `cli-and-workflows.md` entry, which the same
suite covers.

`autonomy/path_gate.py` and `validate/checks/autonomous_runs.py` are **consumed unchanged**, as
are `verify_marks` and `ingest_report` themselves — §3.4.3 adds two constants beside the first
and §5.4 a derivation beside the second, but neither behaviour changes. If the loop appears to
need a change to any of those four, that is a signal the loop is wrong, not that the contract
is.

## 7. Errors

Every orchestration failure raises `HarnessError` naming the step and exits 3 (§3.4.1) — before
`finish_run` or after it, since a step-9 switch, commit, or restore can fail too. The branch and
every file are left in place for triage.

`finish_run` never raises for an expected condition — it returns `unwired`, which blocks — so
steps 7 through 9 always complete once reached. Two things revision 1 got wrong about that
tail:

- **A record may not exist** (§4.5). Step 9 branches on `record_written`, not on the
  disposition, and settles the tree either way.
- **An ingestion refusal is a failure.** It does not stop step 9 — the tree must be left clean
  regardless — but it is reported in `ingestion_refusal` and exits **4**, not 0, even though
  the autonomous disposition is `clean`. The run's purpose was to produce an ingestible report;
  a refused one did not achieve it.

`HarnessOutcome` (§3.4) carries the disposition, the actor's exit code, both commit shas or
`None`, whether a record was written, and the ingestion outcome or refusal. The library
function returns it; the CLI renders it and maps it to the exit codes in §3.4.

## 8. Testing

The end-to-end test is the deliverable. Run the loop against a fixture project and assert all
of it, not only the verdict:

- the disposition is `clean` and the exit code is 0;
- the starting branch is restored and `status --porcelain` is empty;
- the report exists on `auto/<slug>` and **only** there;
- `runs/<slug>.md` and `doc/audits/cases/` exist on the starting branch;
- the record is not inside `base..head`;
- `check_autonomous_runs` is silent from the starting branch.

Asserting the disposition alone would pass for a loop that left the operator on `auto/<slug>`
with a dirty tree — which is exactly the failure §1.1 found by hand.

Mutation rows, in the discipline plan 4c established — apply one mutation alone, require a
*named* test to fail for the stated reason, restore, require it to pass:

| # | Mutation | Expected failure |
|---|---|---|
| 1 | Drop the restore postcondition | a report-only run quarantines on `knowledge/graph.trig` — **against a project with no committed graph** (§1.1); a fixture that commits one leaves both implementations clean |
| 2 | Restore on return but not on `_capture`'s raise | the next `start_run` refuses a dirty tree |
| 3 | Restore `knowledge/graph.trig` by name | a second materialized path survives the restore |
| 4 | Skip the branch-identity check | off-branch actor work is attested to a branch it never touched |
| 5 | Create the auto branch non-exclusively | a run-id collision reuses another run's branch |
| 6 | Author the capture commit as anyone else | `verify_marks` reports a wrong-agent issue |
| 7 | Omit the capture commit's trailer | `verify_marks` reports no trailer |
| 8 | Commit the record on `auto` and switch away | `no run record for it` from `check_autonomous_runs` |
| 9 | Skip the post-verdict commit | the next `start_run` refuses |
| 10 | Ingest on a non-`clean` disposition | cases created from a denied run |
| 11 | Predict the producer set as a literal list | ingestion refuses (§8.1) |
| 12 | Read `generated_at` off the report | the attested value differs from the commissioned one (§8.2) |
| 13 | Start from a detached HEAD | refused before `start_run` |
| 14 | Accept only exit 0 from the actor | a project with an invalid acceptance configuration aborts |
| 15 | Widen the restore postcondition to cover a failed precondition | a dirty input tree loses the caller's uncommitted work (§4.1) |
| 16 | Build a git argv directly instead of routing through `run_git` | a hostile `.git/config` reaches a program (§8.3) |
| 17 | Drop `--no-gpg-sign` from the capture commit | `commit.gpgsign` + `gpg.program` reaches an actor-named program |
| 18 | Commit on the record-less path instead of restoring | a commit is recorded for a run with no attestation (§4.5) |
| 19 | Pass `--allow-empty` rather than checking for nothing to settle | an empty post-verdict commit is recorded |
| 20 | Derive the ingestion context from the health run's lenient sources | an identity conflict is ingested instead of refused (§5.4) |
| 21 | Exit 0 on an ingestion refusal | a run that produced an unusable report reports success |
| 22 | Invoke the actor as a bare `science` from `PATH` | a shadowing `science` on `PATH` runs instead of the supervisor's toolkit |
| 23 | Drop `-P` **and** run the actor with `cwd=project_root` | a `science_tool/` planted in the project root is imported by the actor (§3.2 — neither half alone is observable) |
| 24 | Return an outcome instead of raising when `_settle` fails | a failed switch-back reports the run's own disposition (§8.4) |
| 25 | Take `ended` from the actor's report rather than the supervisor's clock | the record's `ended` is actor-supplied |
| 26 | Leave `current_branch` / `stage_all` / `mkdir` unnormalized | a raw `GitError` escapes the library and the CLI exits 1 with a traceback |
| 27 | Catch only `ValueError` around ingestion | an unreadable report aborts before the tree is settled |
| 28 | Return exit 0 for a quarantined outcome | a denied run reports success |
| 29 | Return exit 0 for an unwired outcome | a run that could not be judged reports success |

### 8.1 Row 11 needs more than one fixture

A single full-health run does not kill a literal-list mutation: a list transcribed correctly
today matches the real set today. The row is certified across **full, `--fast`, and scoped
selections, covering both source-requiring and source-free cases** — or by registering a new
check and requiring the prediction to follow it without edit. A row that a correct literal
would also pass certifies nothing.

### 8.2 Row 12 needs a fake actor

Real `health` echoes the dictated timestamp, so "dictate it" and "read it back" are
observationally identical against the real actor. The row needs an actor whose report carries a
`generated_at` different from the commissioned one; only then does reading it back produce a
different attested value.

**It gets there by monkeypatching the harness's fixed subprocess seam**, not by introducing a
production actor abstraction. §3.2 declined actor selection deliberately, and adding a seam so
a test can vary the actor would put the interface back through the test suite's door. The
patched seam writes a report at the same path with a shifted timestamp; nothing in the shipped
code learns that actors are pluggable.

### 8.3 The hostile-configuration test

Rows 16 and 17 need a repository configured to attack. One planting function writes, into
`.git/config` and `$GIT_DIR/hooks/`, every vector the four new subcommands can reach — a
`pre-commit` hook, a `prepare-commit-msg` hook, a `commit-msg` hook, a `post-commit` hook, a
`post-checkout` hook, a `filter.<driver>.clean` bound by an attribute, `core.fsmonitor`, and
`commit.gpgsign=true` with `gpg.program` naming a script — each writing a sentinel file. The
executables live **outside the repository**, for the same reason the attribute does (below).

**Two tests share that planting function, at two levels, and both are needed.** One drives the
write primitives directly: it certifies row 17, the missing flag. The other runs
`run_supervised_audit` end to end over the same hostile repository: it certifies row 16, a git
argv built by hand inside `_settle`. The first cannot reach row 16's mutation at all — proving
the primitives are hardened says nothing about whether the loop calls them (§8.4). Each ends
with the same assertion: **no sentinel exists**.

**The attribute goes in `$GIT_DIR/info/attributes`, not an untracked `.gitattributes`.** An
untracked file makes `start_run`'s `assert_repository_is_at` refuse the run outright, so the
test would never reach the vector it exists to probe — a fixture that passes for the wrong
reason. `info/attributes` is also the better probe: it is one of the three attribute layers
`_filter_driver_overrides` was written to cover, it is invisible to `git status`, and it is
exactly the actor-controlled layer the gateway's threat model is about. (Committing the
`.gitattributes` in the fixture, or planting it after `start_run` returns, would also work; both
are weaker, because they exercise a layer the actor does not need.)

The test asserts on the sentinels, not on the argv. An argv assertion passes for a harness that
builds the right flags by hand and would keep passing when a later call site forgets them;
the sentinel asserts the property the flags exist to produce.

### 8.4 A mutation must be reachable by the test that names it

Five rows named a mutation their test could not reach, which is the same defect as a vacuous
fixture wearing different clothes. Each is now paired with a test that *induces* the condition:

- **Row 4** (skip the branch-identity check) needs an actor that changes branch. The happy path
  never leaves `auto/<slug>`, so it passes with the check deleted.
- **Row 16** (build a git argv by hand inside `_settle`) needs the hostile repository run
  through the *whole loop*. The primitives test proves the primitives are hardened and says
  nothing about whether `_settle` calls them.
- **Row 19** (`--allow-empty` instead of checking for nothing to settle) needs
  `record_written=True` over a *clean* tree — a state the loop never produces, since
  `finish_run` always leaves the record file on disk. The record-less test returns before the
  commit call, so the mutated code never executes.
- **Row 23**: see §3.2 — one mutation, both halves.
- **Row 24** (swallow a `_settle` failure) needs a `_settle` that fails. The happy path cannot
  distinguish raising from swallowing, because nothing raises.

Rows 16 and 19 were each found *after* a first repair, which is the part worth noticing: the
first pass repointed row 19 from a `commit_tree` test to the record-less harness test, and that
test cannot reach it either. A row moved to a nearer test is not thereby a row whose test
executes the mutation.

The general rule, in the form worth carrying forward: **name the test that induces the
condition, not the test that would notice it if the condition arose.**

### 8.5 One convention with no guard

**"No `Science-Run` trailer on the post-verdict commit" is a convention, not a certifiable
invariant.** `verify_marks` reads only `base..head`, and `check_autonomous_runs` accepts any
marked commit whose run id has a record — so adding a trailer there breaks nothing observable.
It is stated as a convention and claims no mutation row.

## 9. Consequences

**Gained.** The first end-to-end autonomous run this toolkit has produced. Spec 1's ingestion
boundary exercised by a real producer rather than a synthetic one. Three defects in shipped
code closed, all three found by running the loop. A run id that resolves from a case's
provenance. `science autonomy start` that no longer dirties the tree it just declared clean.

**Costs.** A supervisor that owns the working tree, the branch, and two commits — a large
responsibility concentrated in one function. A `git clean -fd` inside `start_run`, safe only
because of the cleanliness assertion immediately preceding it. One actor, hard-wired. Four
write subcommands added to the hardened gateway, each owing its own probe. Five exit codes
where `finish` has three.

**Deliberately not addressed.** Concurrency and fan-out; how a generic actor receives its
report path and provenance; belief-neutral actors across the branch switch (§4.4); whether a
quarantined run's branch is ever cleaned up; retention of anything.

## 10. Adjacent 2a closure

Carried on this branch, scoped as 2a closure rather than 2b:

1. **The 2a design's status rows.** `docs/plans/2026-07-30-agent-evidence-broker-design.md`
   still describes plan 4c as "implemented on `feat/evidence-broker-boundary` … not merged",
   and its §0 row still reads "plans 1–3 merged, 4a/4b designed at revision 17". Both are
   stale as of `1c11c922`. The document declares that table its only status claim.
2. **`InlineInput.lines` counts lines by a different rule than the checker.**
   `autonomy/lifecycle.py:309` sets `lines=len(payload.splitlines())`, which splits on CR, FF,
   LS, PS and NEL as well as LF; `evidence_broker/correspondence.py:49` counts `\n` only. Both
   feed the same `Full(...)` coverage ceiling in `_build_served_map`, so a payload containing a
   bare CR gives an inline input a higher ceiling than the same bytes served through `read` —
   an agent can cite a line the LF convention says does not exist, and the checker calls it
   covered. Brokered runs remain out of 2b's scope; this is a correction to 2a's own
   arithmetic.

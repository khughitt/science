# Spec 2b — mutation ledger

Design §8. Forty-two rows, each certified by the plan-4c discipline: apply **one** mutation
alone, require a **named** test to fail **for the stated reason**, revert, require that same
test to pass before the next row.

**Production baseline:** `51a22c07` (`feat(autonomy): register the supervised run command
surface`) — the tree rows 1–29 were applied to and reverted back to. Only
`science/tests/test_autonomy_harness.py` differs from it in the commit that carries this
ledger; no production file was left changed.

**Second baseline:** the whole-branch fix wave (§ *Re-certification after the fix wave*)
changed `_settle`'s signature and body and `_step`'s catch set. Rows **26a–26d and 30–33** are
new and were certified against that tree; rows **9, 16, 18, 19 and 24** touch the two changed
functions and were re-run against it. Row 19's failure *mode* changed, which is recorded in its
own line rather than smoothed over.

**Final-review baseline (FIX_BASE):** `46eb7c1835e23e24510768bff25b56d644bb05f4`
(`fix(autonomy): close supervised run review gaps`) records the exact reviewed snapshot before
revision 7. Rows **34–38** are new and were certified against the revision-7 working tree;
row **33** was re-certified because the unforeseen exception now leaves as a caused
`HarnessError` after settlement rather than escaping raw.

**Nested-worktree correction baseline:** `51b83f4f` (`docs(plans): record supervised run final
fixes`) is the tree on which the full suite exposed the project-root pin regression. Row **39**
was certified against the revision-8 correction: falling back to the resolved Science project
directory loses the enclosing repository's nested prefix while the malicious
`core.worktree=<sibling>` remains overridden.

A row whose test fails for a *different* reason than the one stated certifies nothing, so the
observed result below records the actual failure text rather than "fails". Every row was also
re-run after reverting; all reverted runs exited 0.

## Reading the table

`Test node` is the node **as it exists**, which is not always the node the implementation plan
named — Tasks 5, 6 and 9 renamed and reorganized tests after the plan was written. Rows whose
plan-named node did not exist are listed under [Drift](#drift-from-the-plans-row-table).

## Rows 1–9 — the loop

| # | Mutation | Test node | Observed result |
|---|---|---|---|
| 1 | Delete the `try`/`finally` restore in `start_run` | `test_autonomy_start_restore.py::test_start_leaves_no_materialization_residue` | KILLED — `AssertionError: assert '?? knowledge/' == ''`; the materialized graph is left in the tree |
| 2 | Restore after `_capture` returns, not in a `finally` | `test_autonomy_start_restore.py::test_start_removes_its_residue_when_it_raises` | KILLED — `AssertionError: assert '?? knowledge/' == ''`; `_capture` raised, so the trailing restore never ran |
| 3 | Restore `knowledge/graph.trig` by name instead of restoring the tree | `test_autonomy_git_writes.py::test_restore_worktree_discards_modifications_and_untracked_files` | KILLED — `AssertionError: assert '?? new.txt\n?? sub/' == ''`; a named-path restore leaves everything it did not name |
| 4 | Delete the `current_branch != baseline.branch` check | `test_autonomy_harness.py::test_an_actor_that_leaves_the_branch_is_refused` | KILLED — `Failed: DID NOT RAISE HarnessError`; the wandering actor's run completed |
| 5 | `create_branch` uses `checkout -B` instead of `-b` | `test_autonomy_harness.py::test_an_existing_auto_branch_refuses_the_run` | KILLED — `Failed: DID NOT RAISE HarnessError`; `-B` resumed the colliding branch |
| 6 | Author the capture commit as the supervisor | `test_autonomy_harness.py::test_the_capture_commit_carries_the_agent_authorship_and_the_run_trailer` | KILLED — `assert 'science-supervisor <supervisor@science.local>' == 'health-audit <agent@science.local>'` |
| 7 | Drop the `Science-Run` trailer from the capture message | `test_autonomy_harness.py::test_a_supervised_run_completes_and_leaves_the_tree_clean` | KILLED — `assert <RunDisposition.QUARANTINED> is <RunDisposition.CLEAN>`; `verify_marks` refuses the unmarked commit |
| 8 | `_settle` before `switch_branch` | `test_autonomy_harness.py::test_the_autonomous_runs_check_is_silent_from_the_starting_branch` | KILLED — one `Result(severity=ERROR, ...)` observation: `commit f39f275fdc3b carries Science-Run: run... missing-record`; the record commit landed on `auto/<slug>`, so the starting branch's tree cannot see it |
| 9 | Return before `_settle` | `test_autonomy_harness.py::test_a_supervised_run_completes_and_leaves_the_tree_clean` | KILLED — `assert 'auto/2026-08-02-health-audit-a1b2' == 'main'`; the operator is stranded on the run's branch. **As applied this certifies "skip step 9 entirely", not `_settle` alone**: the assertion that fires is the BRANCH SWITCH's, and the mutation removes the switch along with the settle. A mutation that kept `switch_branch` and dropped only `_settle` would leave this assertion green. That is not a gap — rows 18 and 19 certify the two commit conditions independently, and row 24 certifies that a `_settle` failure raises — but the row's evidence should not be read as being about `_settle` on its own. |

## Rows 10–14 — attestation and the actor

| # | Mutation | Test node | Observed result |
|---|---|---|---|
| 10 | Ingest regardless of disposition | `test_autonomy_harness.py::test_a_quarantined_run_ingests_nothing` | KILLED — `assert IngestOutcome(records_written=31, ...) is None` against a `QUARANTINED` outcome |
| 11 | Replace `expected_producer_ids`' derivation with a literal 16-element list | `test_health_attested_provenance.py::test_the_prediction_equals_what_the_report_declares[fast]` | KILLED — extra items in the predicted set (`layered_claim_migration`, `invalid_entity_aspects`, …): the literal is today's *full* set and the `fast` selection declares 7 |
| 12 | Read `generated_at` from the loaded report | `test_autonomy_harness.py::test_the_attested_instant_is_the_commissioned_one` | KILLED — `assert IngestOutcome(...) is None`; a self-sourced attestation agrees with the shifted report instead of refusing it |
| 13 | Accept a `None` starting branch | `test_autonomy_harness.py::test_a_detached_head_is_refused_before_the_run_opens` | KILLED — the expected `HarnessError` never arrives; the run proceeds to `switch_branch(root, None)` and dies with `TypeError: expected str, bytes or os.PathLike object, not NoneType`. Detached HEAD was not refused before the run opened, which is the stated reason; the raised type differs because nothing downstream normalizes it. |
| 14 | Accept only exit 0 from the actor | `test_autonomy_harness.py::test_an_actor_exit_two_still_completes` | KILLED — `HarnessError: the actor exited 2:` on a report that was written completely |

## Rows 15–21 — the revision-2 rows

| # | Mutation | Test node | Observed result |
|---|---|---|---|
| 15 | Wrap `assert_repository_is_at` in the restore | `test_autonomy_start_restore.py::test_a_dirty_input_tree_is_refused_byte_for_byte_unchanged` | KILLED — `assert (True and False)`: the caller's untracked `p2.md` no longer exists; the restore destroyed the work the check exists to refuse |
| 16 | Call `subprocess.run(["git", ...])` directly in `_settle` | `test_autonomy_harness.py::test_no_planted_vector_executes_through_the_supervised_loop` | KILLED (as an error, as predicted) — `CalledProcessError ... exit 128` from the raw commit, with git's stderr reading `warning: Empty last update token.` (the actor's `core.fsmonitor` executed) and `error: gpg failed to sign the data: (no gpg output) / fatal: failed to write commit object` (the actor's `commit.gpgsign` + `gpg.program` executed). Not an unrelated fixture error: the traceback is `harness.py:291 _settle -> harness.py:128 subprocess.run`, i.e. the mutated line. |
| 17 | Drop `--no-gpg-sign` from `commit_tree` | `test_autonomy_git_writes.py::test_no_planted_vector_executes_through_the_write_primitives` | KILLED — `GitError: git ... commit ... failed: error: gpg failed to sign the data: (no gpg output) / fatal: failed to write commit object` |
| 18 | `_settle` commits on the record-less path | `test_autonomy_harness.py::test_a_run_with_no_record_commits_nothing` | KILLED — `assert '4f0456fb…' is None`; a run with `record=None` published a post-verdict commit |
| 19 | `_settle` passes `--allow-empty` and skips the status check | `test_autonomy_harness.py::test_settling_a_clean_tree_creates_no_commit` | KILLED — `assert 'd69dd299…' is None` from the direct `_settle(record_written=True)` call over a clean tree |
| 20 | `ingestion_authority` passes `strict_identity=False` | `test_findings_ingestion_authority.py::test_it_loads_sources_without_relaxing_identity` | KILLED — `AssertionError: the strict default must stand …; {'strict_identity': False}.get(...) is False` |
| 21 | Exit 0 on an ingestion refusal | `test_autonomy_harness.py::test_the_command_exits_four_when_ingestion_refuses` | KILLED — `assert 0 == 4` with `ingestion refused: refused for the test` in the output |

**Rows 18 and 19 are two rows, not one.** Row 18 removes the `record_written` guard; row 19
removes the *status* guard and adds `--allow-empty`. Measured: the record-less test cannot kill
row 19, because on that path control returns at `if not record_written: restore; return None`
before any commit call, so the mutated line never executes. Row 19's condition —
`record_written=True` over a **clean** tree — is one the full loop never produces, since
`finish_run` always leaves the record file on disk. `test_settling_a_clean_tree_creates_no_commit`
calls `_settle` directly for exactly that reason.

**Row 16 needs the whole loop, not the primitives.** Proving the write primitives are hardened
says nothing about whether `_settle` calls them;
`test_no_planted_vector_executes_through_the_write_primitives` (row 17's test) stays green
against a raw `subprocess.run` in `_settle`. That is why row 16 has its own test over the
`supervised_project` fixture, sharing Task 1's `plant_attacks` factory.

## Rows 22–39 — revisions 3 through 8

| # | Mutation | Test node | Observed result |
|---|---|---|---|
| 22 | `_run_actor` uses `["science", "health", ...]` | `test_autonomy_harness.py::test_the_actor_runs_the_supervisors_own_toolkit` | KILLED — `HarnessError: the actor exited 1: impostor toolkit`; the `science` planted ahead of the supervisor's on `PATH` ran |
| 23 | Drop `-P` **and** pass `cwd=project_root` | `test_autonomy_harness.py::test_the_actor_runs_the_supervisors_own_toolkit` | KILLED — `HarnessError: the actor exited 1: shadowed`; the `science_tool` package planted in the project was imported |
| 24 | Swallow a `_settle` failure instead of raising | `test_autonomy_harness.py::test_a_settlement_failure_raises` | KILLED — `Failed: DID NOT RAISE HarnessError` |
| 25 | Take `ended` from the loaded report | `test_autonomy_harness.py::test_the_record_ended_is_the_supervisors_clock` | KILLED — `assert datetime(2099, 1, 1, …) <= datetime(2026, 8, 3, …)`; the record carried the actor's instant |
| 26a | Remove the `_step` wrapper from the **first** `current_branch` read (step 1) | `test_autonomy_harness.py::test_a_raw_git_failure_is_normalized` | KILLED — the raw `GitError: cannot read HEAD` escapes instead of a `HarnessError` |
| 26b | Remove the `_step` wrapper from the **second** `current_branch` read (the post-actor re-read) | `test_autonomy_harness.py::test_the_second_branch_read_is_normalized_too` | KILLED — the raw `GitError: cannot re-read HEAD` escapes |
| 26c | Move `stage_all` outside `_step("the actor's output could not be captured")` | `test_autonomy_harness.py::test_a_raw_staging_failure_is_normalized` | KILLED — the raw `GitError: cannot stage the actor's output` escapes |
| 26d | Remove the `_step` wrapper from the anchored report-directory open | `test_autonomy_harness.py::test_a_raw_report_directory_failure_is_normalized` | KILLED — the raw `OSError: cannot create the report directory` escapes; a different exception type through the same wrapper |
| 27 | Catch only `ValueError` around ingestion | `test_autonomy_harness.py::test_a_failed_ingestion_is_a_refusal_and_not_an_abort` | KILLED — `OSError: report is unreadable` escapes the loop, abandoning the tree before step 9 |
| 28 | Return exit 0 for a quarantined outcome | `test_autonomy_harness.py::test_the_command_maps_each_disposition_to_its_exit_code[quarantined-1]` | KILLED — `assert 0 == 1` |
| 29 | Return exit 0 for an unwired outcome | `test_autonomy_harness.py::test_the_command_maps_each_disposition_to_its_exit_code[unwired-2]` | KILLED — `assert 0 == 2` |
| 30 | `_settle` blanket-stages (`add -A`) instead of the named set, committing the graph on every disposition | `test_autonomy_harness.py::test_a_quarantined_run_ingests_nothing` | KILLED — `assert 'knowledge/graph.trig' not in ['knowledge/graph.trig', 'runs/2026-08-02-health-audit-a1b2.md']`; the denied write's derived graph is published on the starting branch. Measured separately against the same mutation: `git grep -l proposition:p9 HEAD` answers `HEAD:knowledge/graph.trig`, so the leaked graph really does name the entity the gate denied. |
| 31 | `_step` catches only `(OSError, ValueError)` | `test_autonomy_harness.py::test_a_source_layer_failure_is_normalized` | KILLED, both parameters — `CommonsError: commons store not found` and `yaml.error.YAMLError: relations.yaml is malformed` each escape `_step` uncaught, where §3.4.1 promises a `HarnessError` |
| 32 | The **ingestion** block catches only `(OSError, ValueError)` | `test_autonomy_harness.py::test_an_ingestion_authority_failure_is_a_refusal_and_not_an_abort` | KILLED, both parameters — `CommonsError: commons store not found` and `yaml.error.YAMLError: relations.yaml is malformed` escape the ingestion block instead of being recorded as a refusal |
| 33 | Run step 9 **sequentially** instead of in a `finally` | `test_autonomy_harness.py::test_an_unforeseen_ingestion_failure_still_settles_the_tree` | KILLED — the caused `HarnessError` is raised as required, then `assert 'auto/2026-08-02-health-audit-a1b2' == 'main'`; sequential settlement is skipped and strands the operator on the run's branch |
| 34 | Drop `_argv`'s command-line `--work-tree` pin | `test_autonomy_git_writes.py::test_repo_local_core_worktree_cannot_redirect_write_primitives` | KILLED — `assert 'outside named' == 'inside named'`; repository-local `core.worktree` made the gateway stage and commit the sibling's bytes |
| 35 | Pass the derived project report path directly to `_run_actor` | `test_autonomy_harness.py::test_actor_output_cannot_follow_a_project_symlink` | KILLED — the external reports directory contains `2026-08-02-health-audit-a1b2.json`; the actor followed the committed parent symlink before anchored installation could refuse it |
| 36 | Re-raise an unforeseen ingestion exception unchanged | `test_autonomy_harness.py::test_an_unforeseen_ingestion_failure_still_settles_the_tree` | KILLED — raw `_Unforeseen: nobody foresaw this` escapes instead of the required caused `HarnessError` |
| 37 | Remove `_settle`'s post-commit `worktree_status` check | `test_autonomy_harness.py::test_settlement_names_an_unaccounted_dirty_path` | KILLED — `Failed: DID NOT RAISE HarnessError`; the named commit succeeds while `?? unexpected.txt` remains unaccounted |
| 38 | Treat every nonzero `cat-file -t` answer as absence | `test_autonomy_git_writes.py::test_restore_path_fails_closed_when_cat_file_does_not_prove_absence` | KILLED — `Failed: DID NOT RAISE GitError`; the simulated object-database failure fell through to cleanup |
| 39 | Pin `--work-tree` to the resolved Science project directory instead of the nearest enclosing worktree root | `test_autonomy_git_writes.py::test_nested_project_uses_enclosing_worktree_without_trusting_core_worktree` | KILLED — `build/x.csv` appeared despite the enclosing ignore rule, and the indexed `science.yaml` also appeared as `projects/demo/science.yaml`; the project-root pin destroyed the nested prefix |

**Rows 32, 33, and 36 split one hazard into three observable contracts.** Row 32's expected
project-state failures become refusals. Row 36's private `_Unforeseen(Exception)` becomes a
`HarnessError` whose `__cause__` is that same exception, never a refusal or raw leak. Row 33
uses the same failure to prove the `finally`: moving settlement after the ingestion block still
raises the normalized error, but the branch assertion finds the operator stranded on
`auto/<slug>`. A test inducing a refusal cannot certify row 33 because no error leaves the
ingestion block.

**Row 26 was one row claiming three helpers, and certified one.** Its test patched
`current_branch` to raise unconditionally, so control died at the FIRST of two wrapped call
sites; deleting the second wrapper alone (`harness.py`'s post-actor re-read) left the test
green, and `stage_all`'s and the report-open wrappers were never exercised at all. Four rows
now, one per wrapped call site, each with a test that induces a failure only that wrapper can
normalize — and 26a's test gained a `match=`, since a bare `pytest.raises(HarnessError)` is
satisfied by the run dying anywhere at all (the module's own convention, see
`test_an_existing_auto_branch_refuses_the_run`). Lettered rather than renumbered so rows 27–29
keep the numbers the design table gives them.

**Row 23 is one mutation with two halves, deliberately.** Re-measured here and consistent with
the earlier measurement recorded in the test's docstring: `-P` alone with `cwd=project_root`
passes, and the neutral `cwd` alone with `-P` dropped passes. `python -m` puts `''` on
`sys.path` and `''` resolves to the *cwd*, so aiming the cwd somewhere harmless and refusing to
trust the cwd are two answers to one question. Splitting it would put two individually
unkillable mutations in this ledger.

Rows 22 and 23 share one test, which is why it now carries **two** plants: a `science_tool`
package inside the project (for 23) and a `science` executable prepended to `PATH` from a
directory *outside* the project (for 22 — an untracked executable beside the entities would
make `start_run` refuse the dirty tree before the actor ever started).

## Drift from the plan's row table

The plan was written before Tasks 5, 6 and 9 ran. Four of its named nodes did not exist:

| Plan's node | Resolution |
|---|---|
| `test_a_recordless_outcome_commits_nothing` (row 18) | Already covered by `test_a_run_with_no_record_commits_nothing`; row repointed, no duplicate added |
| `test_an_unreadable_report_is_a_refusal_not_an_abort` (row 27) | Already covered by `test_a_failed_ingestion_is_a_refusal_and_not_an_abort`; row repointed, no duplicate added |
| `test_settling_a_clean_tree_creates_no_commit` (row 19) | Did not exist — added |
| `test_no_planted_vector_executes_through_the_supervised_loop` (row 16) | Did not exist — added, requesting `plant_attacks` from `tests/conftest.py` |

Six further tests named "(below)" by the plan were also absent and were added:
`test_an_actor_that_leaves_the_branch_is_refused` (4),
`test_a_quarantined_run_ingests_nothing` (10),
`test_the_attested_instant_is_the_commissioned_one` (12),
`test_an_actor_exit_two_still_completes` (14),
`test_a_settlement_failure_raises` (24),
`test_the_record_ended_is_the_supervisors_clock` (25),
`test_a_raw_git_failure_is_normalized` (26).

## Two places where the plan's prescribed test could not have certified its row

Both were found by asking, before certifying, *what input puts control on the mutated line* —
the same question that caught the third instance during Task 5.

**Row 14's fixture.** The plan prescribed `health:\n  accepted_validation: scalar\n`. Measured:
`accepted_validation_entries` returns `[]` when the value is not a **list**, so no
`accepted-validation.invalid-entry` finding is produced and `science health` exits **0**. The
assertion `outcome.actor_exit_code == 2` would then fail on a *correct* implementation. The
fixture is a one-element list holding an unusable entry instead, which does produce the finding
and the exit code. The assertion was not weakened to `in (0, 2)`.

**Row 25's assertion.** The plan's `test_the_record_ended_is_the_supervisors_clock` ran the
untouched fixture and asserted `before <= record.ended <= after`. Against an honest actor the
report's `generated_at` *is* the instant the supervisor dictated, and that instant lies inside
`[before, after]` — so the assertion holds whichever source `ended` came from, and the mutation
survives. The test now shifts the report's `generated_at` to 2099 through the same fixed
`_run_actor` seam row 12 uses (factored into `_shift_the_reported_instant`), which is what makes
"the supervisor's clock" and "the actor's report" distinguishable at all.

## Re-certification after the fix wave

The whole-branch review's fix wave changed `_settle`'s signature and body (named-set staging,
the disposition-conditioned graph) and `_step`'s catch set. Every row touching either function
was applied again against the fixed tree:

| # | Verdict on re-run |
|---|---|
| 9 | KILLED, same evidence — and annotated above, because that evidence is the branch switch's |
| 16 | KILLED, and more directly than before: the hand-built `add -A` fires the actor's `core.fsmonitor` and `filter.<driver>.clean`, so the test now fails on its own sentinel assertion (`['filter', 'fsmonitor']`) rather than on a `CalledProcessError` from a later commit |
| 18 | KILLED, same evidence |
| 19 | KILLED — **failure mode changed**, see below |
| 24 | KILLED, same evidence (`DID NOT RAISE HarnessError`) |
| 26a–26d, 30–33 | KILLED — new rows, evidence in the tables above |

**Row 19's failure mode changed, and the row is weaker for it.** The mutation removes the
"nothing to settle" status guard. Under `add -A` that let control reach
`commit --allow-empty` and record an empty commit, which is what the row's stated reason
describes. Under named-set staging control now dies one line earlier, in `stage_paths`:

> `GitError: git add -A -- runs/2026-08-02-health-audit-a1b2.md knowledge/graph.trig failed …:
> fatal: pathspec 'runs/2026-08-02-health-audit-a1b2.md' did not match any files`

A clean tree has no record file to name, so `--allow-empty` is now unreachable and the second
half of the mutation is inert. The test still goes red, and it goes red *on the line the
removed guard exists to skip* — so the guard is still certified as load-bearing — but the harm
it demonstrates is "the harness refuses" rather than "an empty commit is recorded". Recorded
rather than restated, because a row whose observed failure is quietly re-described is exactly
what this ledger exists to prevent.

## Final-review certification

Rows 34–38 were applied one at a time against revision 7, with no other mutation active. Each
named node failed for the table's stated reason; after restoring the production line, the same
node passed before the next mutation. Row 33 was repeated under the revised exception contract
and killed on the restored-branch assertion while still observing the required caused
`HarnessError`.

## Nested-worktree regression certification

Row 39 was applied alone against revision 8 by replacing `_worktree_root(root)` with `root` in
the central `--work-tree` argument. The named node failed on its literal visible-path list:
`build/x.csv` was the first unexpected path and `projects/demo/science.yaml` was also present.
After restoring the nearest-marker derivation, the same node passed. No other mutation was
active.

## Result

42 rows applied, 42 killed, 0 unkillable. Every reverted re-run passed.

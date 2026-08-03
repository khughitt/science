# Spec 2b final review fixes

## Status

DONE. All five behavioral findings and both documentation findings from the final
whole-branch review are fixed. The relevant mutation ledger is fully certified at
41/41 killed.

## Commits

- Initial snapshot (`FIX_BASE`): `46eb7c1835e23e24510768bff25b56d644bb05f4`
- Production, tests, design, and ledger:
  `bdada2d377117669aec0d0b0eb37744b1076a1b4`

The reviewed working tree was already clean when this fixing wave began, so the
required initial snapshot is an empty checkpoint that preserves the exact reviewed
state.

## Findings closed

### 1. Repository-local `core.worktree` could redirect Git writes

Red test:

```text
uv run --frozen pytest tests/test_autonomy_git_writes.py::test_repo_local_core_worktree_cannot_redirect_write_primitives -q
```

Before the fix, the assertion read `HEAD:named` as `outside named` rather than
`inside named`, proving the repository-local configuration redirected a write to a
sibling worktree.

Fix: `autonomy/git.py::_argv` now supplies
`--work-tree=<resolved-project-root>` on every gateway invocation, including the
configuration preflight. Every production Git operation still goes through this
gateway.

Green evidence: the same test passes and exercises create/switch, `stage_paths`,
`commit`, `restore_path`, `stage_all`, and `restore_worktree` while asserting the
sibling is unchanged.

### 2. The actor could follow a committed project symlink

Red test:

```text
uv run --frozen pytest tests/test_autonomy_harness.py::test_actor_output_cannot_follow_a_project_symlink -q
```

Before the fix, the external target contained the derived report file.

Fix: the fixed actor receives a supervisor-owned temporary output path. After an
accepted actor exit, the harness bounded-reads that regular file and copies its bytes
verbatim to the derived report path using the existing descriptor-anchored directory,
exclusive-create, write-all, and unlink primitives in `findings/paths.py`. The fixed
actor, model, and service tier are unchanged, and no generic actor API was added.

Green evidence: the same test passes and the external directory remains empty. The
new `read_regular_file_bytes_at` primitive is separately guarded by
`test_read_regular_file_bytes_at_preserves_non_utf8_bytes`.

### 3. An unforeseen ingestion exception leaked raw after settlement

Red test:

```text
uv run --frozen pytest tests/test_autonomy_harness.py::test_an_unforeseen_ingestion_failure_still_settles_the_tree -q
```

Before the fix, the private `_Unforeseen` exception escaped unchanged.

Fix: an unforeseen ordinary `Exception` becomes a caused `HarnessError` inside the
ingestion `try`; the outer `finally` settles the run before it propagates. Expected
ingestion errors retain the refusal contract.

Green evidence: the same test requires the `HarnessError`, its `_Unforeseen` cause,
the restored starting branch, and a clean tree.

### 4. Named settlement did not verify its clean-tree postcondition

Red test:

```text
uv run --frozen pytest tests/test_autonomy_harness.py::test_settlement_names_an_unaccounted_dirty_path -q
```

Before the fix, the harness returned successfully with `unexpected.txt` left dirty.

Fix: after committing the named settlement set, `_settle` re-reads porcelain status
and raises `HarnessError` containing the complete residue if any path remains.

Green evidence: the same test passes and names `unexpected.txt` in the error.

### 5. `restore_path` treated every `cat-file` failure as path absence

Red test:

```text
uv run --frozen pytest tests/test_autonomy_git_writes.py::test_restore_path_fails_closed_when_cat_file_does_not_prove_absence -q
```

Before the fix, the abnormal object lookup did not raise.

Fix: `restore_path` selects cleanup only when the last non-empty stderr line is one
of Git's exact, fully interpolated absent-path verdicts. Every other nonzero answer
raises `GitError` before a write.

Green evidence: the same test passes.

### 6. Exit-code 3 documentation overstated the failure phase

`docs/user-guide/agent-workflows.md` now says exit 3 means no harness outcome was
returned because orchestration failed, including possible post-verdict settlement
failure. It no longer claims every exit-3 failure occurred before a verdict.

### 7. No-root boundary migration guidance contradicted the CLI

`docs/migration/2026-08-02-gitignore-ingestion-lock.md` now says a project without
declared roots takes no action until enrollment and that `science boundary sync`
refuses such a project.

## Files changed

- `science/src/science_tool/autonomy/git.py`
- `science/src/science_tool/autonomy/harness.py`
- `science/src/science_tool/findings/paths.py`
- `science/tests/test_autonomy_git_writes.py`
- `science/tests/test_autonomy_harness.py`
- `science/tests/test_findings_paths.py`
- `docs/user-guide/agent-workflows.md`
- `docs/migration/2026-08-02-gitignore-ingestion-lock.md`
- `docs/plans/2026-08-02-supervised-run-harness-design.md`
- `docs/plans/2026-08-02-spec-2b-mutation-ledger.md`

## Mutation certification

Each mutant was applied alone, the named guard was run and observed failing for the
intended reason, the original implementation was restored, and the same guard was
observed passing before the next mutant.

| Row | Mutation | Kill evidence |
|---|---|---|
| 34 | Remove `_argv`'s `--work-tree` pin | `test_repo_local_core_worktree_cannot_redirect_write_primitives` read `outside named` from `HEAD:named` instead of `inside named` |
| 35 | Pass the derived project report path directly to the actor | `test_actor_output_cannot_follow_a_project_symlink` found the report in the external symlink target |
| 36 | Re-raise an unforeseen ingestion exception unchanged | `test_an_unforeseen_ingestion_failure_still_settles_the_tree` received raw `_Unforeseen` instead of caused `HarnessError` |
| 37 | Remove `_settle`'s post-commit status check | `test_settlement_names_an_unaccounted_dirty_path` did not raise |
| 38 | Treat every nonzero `cat-file -t` answer as absence | `test_restore_path_fails_closed_when_cat_file_does_not_prove_absence` did not raise |

Row 33 was also re-certified against the final exception contract. Moving settlement
after ingestion caused the unforeseen-ingestion guard to observe the required caused
`HarnessError` while the branch remained `auto/<run-id>` rather than returning to the
starting branch. Restoring the `finally` made the guard pass.

Ledger result: **41/41 killed; no surviving or flaky mutants; no mutant left active.**

## Verification

Focused modules while developing:

```text
uv run --frozen pytest tests/test_autonomy_git_writes.py -q
15 passed

uv run --frozen pytest tests/test_findings_paths.py -q
54 passed

uv run --frozen pytest tests/test_autonomy_harness.py -q
36 passed
```

Full Spec 2b scoped set:

```text
uv run --frozen pytest tests/test_autonomy_harness.py tests/test_autonomy_git_writes.py tests/test_autonomy_start_restore.py tests/test_health_attested_provenance.py tests/test_findings_ingestion_authority.py -q
65 passed
```

Adjacent path, Git, broker, and ingestion guards:

```text
uv run --frozen pytest tests/test_autonomy_git_canonical.py tests/test_evidence_broker_serve.py tests/test_findings_paths.py tests/test_findings_ingest.py -q
193 passed
```

Adjacent lifecycle, record, alarm, documentation, and budget guards:

```text
uv run --frozen pytest tests/test_autonomy_lifecycle.py tests/test_autonomy_record_writer.py tests/test_autonomy_perturbation_alarm.py tests/test_command_docs.py tests/test_budget_boundary.py -q
227 passed
```

Static checks:

```text
uv run --frozen ruff check
All checks passed!

uv run --frozen pyright
0 errors, 0 warnings, 0 informations

git diff --check
passed with no output
```

Total distinct tests in the final required scoped and adjacent runs: **485 passed**.
The approximately 12,000-test full CLI suite was not run because this work did not
meet the repository guide's full-suite triggers; the complete affected and adjacent
contract surfaces were run instead.

## Self-review

- The actor, model, and service tier remain fixed; no `Assignment`, generic actor
  surface, compatibility layer, or `Unified` component was introduced.
- Production Git calls remain centralized through `autonomy/git.py`.
- Actor output installation reuses the existing anchored path vocabulary and copies
  bytes verbatim, including non-UTF-8 content; schema validation remains later at the
  report trust boundary.
- Unforeseen ingestion failures retain their original exception as `__cause__` and
  settle before propagation.
- All five production regressions have direct red/green guards and individually
  certified mutants.
- Documentation uses project-relative examples and contains no AI-attribution trailer.
- `git diff --check`, Ruff, and Pyright are clean.

## Concerns

None.

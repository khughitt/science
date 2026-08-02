# Plan 4c mutation ledger

Rows 1–38 were certified against production baseline `24547746`; the revision 38 final-review rows
39–44 were certified on `feat/evidence-broker-boundary` based at `69a39b22`. Each mutation was
applied alone, its named node was required to fail for the stated reason, the mutation was reversed,
and the same node was required to pass before the next row began. Model nodes ran from
`science/model/`; CLI nodes ran from `science/`, each with `uv run --frozen pytest -q`.

Design revision 37 removed the former row 32, “unknown `finding_id` surfaces as
`CaseStorageError`.” The exact scan-specific mutant stayed green because the enclosing
`except CaseStorageError` translates it to the same public `IngestError`; only cause, message, or
source structure distinguishes the implementations. It is therefore recorded in the design's
“must not be added” list and is not one of the 44 certifiable rows below.

| # | Mutation | Test node | Observed result |
|---:|---|---|---|
| 1 | Import `Correspondence` from `evidence_broker.py` | `test_audit_import_cycle.py::test_evidence_broker_imports_in_a_fresh_interpreter` | **FAILED as required:** the fresh interpreter reported the circular import from partially initialized `science_model.evidence_broker`; restored node passed. |
| 2 | Leaf imports `_Base` from `audit.subjects` | `test_audit_import_cycle.py::test_correspondence_leaf_imports_in_a_fresh_interpreter` and `test_correspondence.py::test_running_correspondence_leaf_does_not_load_audit` | **FAILED as required (Task 3 measurement carried forward):** the isolated fresh-import guard reached its assertion and failed; the existing `test_correspondence` node failed earlier at collection because that module imports `Correspondence` at module scope. Restored nodes pass. |
| 3 | Re-add `reviewer_kind` to `ReviewSubmission` | `test_audit_review_contract.py::test_submission_cannot_express_a_reviewer_kind` | **FAILED as required:** the submission accepted the field, so the expected validation error was not raised; restored node passed. |
| 4 | Skip the `reviewer_ref` cross-check | `test_findings_reviews.py::test_a_reviewer_ref_mismatch_is_refused` | **FAILED as required:** the mismatched review was stored instead of raising; restored node passed. |
| 5 | Skip the `model` cross-check | `test_findings_reviews.py::test_a_model_mismatch_is_refused` | **FAILED as required:** the mismatched review was stored instead of raising; restored node passed. |
| 6 | Skip the lens cross-check | `test_findings_reviews.py::test_a_lens_mismatch_against_an_EXPOSED_run_is_refused` | **FAILED as required:** the mismatched review was stored instead of raising; restored node passed. |
| 7 | Apply the lens cross-check unconditionally | `test_findings_reviews.py::test_the_lens_check_is_skipped_when_the_run_has_no_exposure` | **FAILED as required:** the unbrokered run dereferenced `None.evidence` instead of storing `unwired`; restored node passed. |
| 8 | Store an unresolvable `run_ref` as a correspondence | `test_findings_reviews.py::test_a_run_ref_with_no_record_is_refused_and_writes_nothing` | **FAILED as required:** the append completed instead of raising; restored node passed. |
| 9 | Resolve a baseline / open the control plane | `test_findings_reviews.py::test_a_sealed_run_replays_with_the_control_plane_deleted` | **FAILED as required:** deleted control-plane state raised `BaselineError`; restored node passed from the sealed run record alone. |
| 10 | Stamp `Review.at` from a clock | `test_findings_reviews.py::test_the_stored_at_is_the_attested_instant` | **FAILED as required:** the stored current time differed from the attested 2020 instant; restored node passed. |
| 11 | Drop the stored-`violated` invariant | `test_audit_review_contract.py::test_violated_is_unstorable` | **FAILED as required:** the expected validation error was not raised; restored node passed. |
| 12 | Drop agent-requires-`correspondence` | `test_audit_review_contract.py::test_agent_review_requires_a_correspondence` | **FAILED as required:** the expected validation error was not raised; restored node passed. |
| 13 | Drop `max_length` from `ReviewSubmission.uncertainty` | `test_audit_review_contract.py::test_submission_bounds_uncertainty` | **FAILED as required:** the over-bound tuple validated; restored node passed. |
| 14 | Drop `max_length` from `Review.uncertainty` | `test_audit_review_contract.py::test_review_bounds_uncertainty` | **FAILED as required:** the over-bound tuple validated; restored node passed. |
| 15 | `== "human"` instead of `!= "agent"` | `test_audit_review_contract.py::test_human_and_deterministic_count_regardless` | **FAILED as required:** the deterministic confirmation no longer counted; restored node passed. |
| 16 | Drop the `status == "verified"` clause | `test_audit_review_contract.py::test_unwired_does_not_count_even_with_location_evidence` | **FAILED as required:** an `unwired` agent confirmation counted; restored node passed. |
| 17 | Drop the non-empty `evidence` clause | `test_audit_review_contract.py::test_a_vacuous_verified_confirmation_does_not_count` | **FAILED as required:** a vacuous verified confirmation counted; restored node passed. |
| 18 | `any` instead of `all` | `test_audit_review_contract.py::test_one_location_mixed_with_prose_does_not_count` | **FAILED as required:** mixed location/prose evidence counted; restored node passed. |
| 19 | Check reports only non-`verified` correspondence | `test_review_confirmations_check.py::test_a_vacuously_verified_agent_confirmation_is_reported` | **FAILED as required:** the vacuously verified confirmation produced no observation; restored node passed. |
| 20 | Omit the rule from `_POLICY_INFO_RULE_IDS` | `test_review_confirmations_check.py::test_the_finding_keeps_its_rule_and_fingerprint` | **FAILED as required:** `is_policy_info_rule` returned false; restored node passed. |
| 21 | Drop the `outcome == "confirms"` clause | `test_audit_review_contract.py::test_outcome_must_be_confirms` | **FAILED as required:** a human refutation counted as support; restored node passed. |
| 22 | Drop `max_length` from `ReviewSubmission.evidence` | `test_audit_review_contract.py::test_submission_bounds_evidence` | **FAILED as required:** the over-bound tuple validated; restored node passed. |
| 23 | Drop `max_length` from `Review.evidence` | `test_audit_review_contract.py::test_review_bounds_evidence` | **FAILED as required:** the over-bound tuple validated; restored node passed. |
| 24 | Drop the attestation's agent-requires-`lens` | `test_audit_review_contract.py::test_agent_attestation_requires_a_lens` | **FAILED as required:** the expected validation error was not raised; restored node passed. |
| 25 | Drop the attestation's agent-requires-`model` | `test_audit_review_contract.py::test_agent_attestation_requires_a_model` | **FAILED as required:** the expected validation error was not raised; restored node passed. |
| 26 | `ReviewSubmission` accepts a `correspondence` key | `test_audit_review_contract.py::test_submission_cannot_express_a_correspondence` | **FAILED as required:** the submission accepted the key; restored node passed. |
| 27 | Skip step 0 for `submission` | `test_findings_reviews.py::test_a_forged_submission_raises_ingest_error_not_validation_error` and `::test_a_forged_submission_is_refused_before_the_checker` | **FAILED as required:** the human path did not raise and the agent path reached the injected checker assertion; both restored nodes passed. |
| 28 | Skip step 0 for `attestation` | `test_findings_reviews.py::test_a_forged_attestation_is_refused_before_the_run_lookup` | **FAILED as required:** the forged attestation reached the injected run-lookup assertion; restored node passed. |
| 29 | Step 0 as `T.model_validate(arg)`, no dump | `test_findings_reviews.py::test_a_forged_submission_is_refused_before_the_checker` | **FAILED as required:** instance validation skipped the forged nested member and reached the checker; restored node passed. |
| 30 | Dump in `mode="json"` at step 0 | `test_findings_reviews.py::test_step_zero_accepts_a_well_formed_pair` | **FAILED as required:** strict validation rejected JSON-mode list output for tuple fields; restored node passed. |
| 31 | Run `check_correspondence` before the cross-checks | `test_findings_reviews.py::test_the_cross_checks_run_before_the_checker` | **FAILED as required:** injected replay `ServeError` escaped before the model mismatch refusal; restored node passed. |
| 32 | Rely on `_validate_reviews` for the duplicate | `test_findings_reviews.py::test_a_duplicate_review_is_refused_and_writes_nothing` | **FAILED as required:** raw `ValidationError` escaped instead of the boundary's duplicate `IngestError`; restored node passed. |
| 33 | Catch only `RunRecordError` | `test_findings_reviews.py::test_an_unreadable_runs_directory_is_an_ingest_error` | **FAILED as required:** raw `PermissionError` escaped; restored node passed. |
| 34 | `OSError` from `flock` acquisition escapes | `test_findings_locked_store.py::test_flock_acquisition_failure_becomes_case_storage_error` and `test_findings_reviews.py::test_a_lock_acquisition_failure_surfaces_as_ingest_error` | **FAILED as required at both layers:** raw acquisition `OSError` escaped the storage and append boundaries; both restored nodes passed. |
| 35 | `OSError` from `flock` release escapes or replaces an active body exception | `test_findings_locked_store.py::test_flock_release_failure_becomes_case_storage_error`, `::test_body_exception_is_not_replaced_by_teardown_failures`, and `test_findings_reviews.py::test_a_lock_release_failure_surfaces_as_ingest_error` | **FAILED as required:** raw release `OSError` escaped both public layers; under the unconditional-conversion mutant, release replaced the exact body sentinel. Restored nodes passed. |
| 36 | `OSError` from lock `os.close` escapes or replaces an active body exception | `test_findings_locked_store.py::test_close_failure_becomes_case_storage_error`, `::test_body_exception_is_not_replaced_by_teardown_failures`, and `test_findings_reviews.py::test_a_lock_close_failure_surfaces_as_ingest_error` | **FAILED as required:** raw lock-close `OSError` escaped both public layers; under the unconditional-conversion mutant, lock close replaced the exact body sentinel. Restored nodes passed. |
| 37 | Widen `locked_store`'s `try` across its `yield` | `test_findings_locked_store.py::test_body_exception_is_not_relabelled` | **FAILED as required:** the sentinel body `OSError` was relabelled `CaseStorageError`; restored node passed. |
| 38 | Derive `review_id` before the case scan | `test_findings_reviews.py::test_an_unknown_nul_bearing_finding_id_is_an_ingest_error` | **FAILED as required:** raw `RecordError` escaped before the unknown-case refusal; restored node passed. |
| 39 | Accept a behavioural `ReviewSubmission` subtype by rebuilding through `type(value)` | `test_findings_reviews.py::test_a_behavioral_submission_subclass_is_rejected_before_any_side_effect` | **FAILED as required:** the subtype was accepted, so the expected exact-type `IngestError` was not raised; restored node rejected it before any caller method, field, run lookup, checker call, or storage access. |
| 40 | Accept a behavioural `ReviewAttestation` subtype by rebuilding through `type(value)` | `test_findings_reviews.py::test_a_behavioral_attestation_subclass_is_rejected_before_any_side_effect` | **FAILED as required:** the subtype was accepted, so the expected exact-type `IngestError` was not raised. The restored node rejects it before reading either argument or reaching run lookup, checker, or storage. |
| 41 | Let lock `fstat` `OSError` escape `open_lock_at` | `test_findings_locked_store.py::test_lock_validation_failure_becomes_case_storage_error` and `test_findings_reviews.py::test_a_lock_validation_failure_surfaces_as_ingest_error` | **FAILED as required at both layers:** raw `OSError(EIO)` escaped instead of `CaseStorageError` / `IngestError`; both restored nodes passed. |
| 42 | Let validation-cleanup lock close replace the path failure | `test_findings_locked_store.py::test_lock_validation_cleanup_failure_does_not_escape_storage_boundary` and `test_findings_reviews.py::test_a_lock_validation_cleanup_failure_surfaces_as_ingest_error` | **FAILED as required at both layers:** the cleanup `OSError(EIO)` replaced the lock-validation failure and escaped raw; both restored nodes kept cleanup secondary and passed. |
| 43 | Let the directory-descriptor close escape or replace an active body exception | `test_findings_locked_store.py::test_directory_close_failure_becomes_case_storage_error`, `::test_body_exception_is_not_replaced_by_teardown_failures`, and `test_findings_reviews.py::test_a_directory_close_failure_surfaces_as_ingest_error` | **FAILED as required:** raw directory-close `OSError` escaped both public layers, and under simultaneous body/release/close failures it replaced the exact body sentinel; all restored nodes passed. |
| 44 | Restore `confirmation_count`'s outcome-only filter | `test_audit_record.py::test_confirmation_count_excludes_an_unwired_agent_confirmation`, `::test_confirmation_count_excludes_a_vacuous_verified_agent_confirmation`, and `::test_confirmation_count_excludes_a_mixed_evidence_agent_confirmation` | **FAILED as required:** every excluded review counted as 1 instead of 0; all three restored nodes passed. |

Restored-tree focused verification:

```text
science/model: uv run --frozen pytest tests/test_audit_import_cycle.py tests/test_audit_review_contract.py tests/test_correspondence.py tests/test_audit_record.py
106 passed

science: uv run --frozen pytest tests/test_findings_reviews.py tests/test_findings_locked_store.py tests/test_review_confirmations_check.py
49 passed
```

The adjacent `test_findings_paths.py` and `test_findings_storage.py` modules also passed in the same
restored tree. The top-level integration agent owns the full model and CLI suites.

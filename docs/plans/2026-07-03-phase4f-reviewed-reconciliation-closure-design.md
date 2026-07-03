# Proposition Reconciliation Phase 4f: Reviewed Reconciliation Closure

Date: 2026-07-03

## 1. Goal

Phase 4e can now generate proposition reconciliation candidates, validate reviewed
judgments, persist advisory reviewed decisions, plan and apply safe canonicalization
or factorization resynthesis, expose lineage, and archive settled superseded
propositions.

Dogfooding the full path on the BES / meta-analysis corpus left a narrower queue
problem: some low-priority factorization candidates correctly report
`insufficient_hints`, but the right reviewed outcome is sometimes "no proposition
mutation is needed." Today that outcome cannot be persisted. The candidate therefore
keeps resurfacing even after review.

Phase 4f adds a reviewed closure path for these cases. It lets a reviewer record
that a current sparse-hint factorization candidate has been inspected and accepted
as not needing reconciliation work, while keeping stale or changed candidates visible.

## 2. Scope

In scope:

- a reviewed Lane B closure decision for current `insufficient_hints` candidates;
- action-plan and decision-log support for recording that closure;
- report-time suppression of currently covered sparse-hint candidates;
- stale detection when the underlying assertion set changes;
- diagnostics that distinguish active candidates from closed, stale, and conflicting
  closure records;
- real-corpus dogfood on the two remaining low-priority factorization candidates.

Out of scope:

- changing cross-paper belief aggregation;
- changing proposition, sidecar, or graph materialization state;
- adding automatic factorization hints;
- tuning away `insufficient_hints` generation globally;
- accepting closure for high-risk factorization candidates such as
  `stance_review_needed` or `factorization_needs_resynthesis`;
- agent-authored scientific judgment without the existing reviewed-file validation
  boundary;
- a general waiver system for arbitrary validation warnings.

## 3. Current State

The current project-wide reconciliation report has no same-claim candidates and two
factorization disagreements. Both are low-priority `insufficient_hints` candidates:

- `proposition:bes-does-not-rescue-underpowered-studies-by-pooling-data`
- `proposition:conceptual-replication-evidence-can-be-aggregated-over-informative-hypotheses`

The first is already factored in proposition frontmatter and is supported by two
asserted annotations whose JSON statement bodies lack subject/object hints. The
second is broader: it intentionally spans BES and product Bayes factor examples, but
its supporting annotations also lack statement-level factorization hints. Both are
reasonable candidates for reviewed closure, but they should resurface if new
assertions change the evidence shape.

Phase 4e reviewed-decision persistence deliberately persists only a small advisory
set today:

- Lane A `related_but_distinct`
- Lane A `conflict_or_negation`
- Lane B `split_possible`

Half B already maps Lane B `insufficient_hints` to an advisory
`cleanup_factorization_hints` action, but the persistence layer does not accept that
decision. Phase 4f closes that gap.

## 4. Reviewed Decision

Add one reviewed Lane B decision:

```text
accepted_sparse_hints
```

Meaning:

> The reviewer inspected the current sparse-hint factorization candidate and accepts
> the current proposition/evidence shape without immediate reconciliation mutation or
> mandatory hint cleanup.

The decision is valid only when all of these are true:

- lane is `factorization_disagreement`;
- the current candidate exists for the reviewed proposition;
- the candidate's `recommended_action` is `insufficient_hints`;
- every candidate disagreement is compatible with sparse hints, currently
  `"multiple assertions have insufficient factorization hints"`;
- the reviewed judgment references the current candidate id and judgment id;
- the reviewed judgment carries a non-empty rationale.

The decision does not claim the proposition is final forever. It only closes the
current reconciliation candidate shape.

Rejected vocabulary:

- `no_action_needed`: too broad; it sounds applicable to any candidate class.
- `accepted_factorization`: too strong; these candidates often lack factorization
  hints rather than proving that factorization is complete.
- `waived`: too validator-like and suggests a generic waiver mechanism.

## 5. Candidate Freshness

`candidate_id` for factorization candidates is intentionally stable per proposition.
For sparse-hint closure, that is not enough freshness. A closure must also be scoped
to the assertion set that produced the candidate.

Store a deterministic input fingerprint on the decision record. The canonical
serialized value includes the `sha256:` prefix:

```text
assertion_fingerprint = "sha256:" + sha256(
  "factorization-assertions-v1" \0
  proposition-ref \0
  sorted(annotation-ref \0 paper-ref \0 stance \0 subject \0 object \0
         subject-concept \0 object-concept \0 exact-text)...
)
```

Use annotation refs when present. If an assertion lacks an annotation ref, include an
empty annotation slot and still include paper, stance, subject/object hints, concept
hints, and exact text. The fingerprint is derived from the candidate's
`observed_statement_hints`, not from sidecar files directly, so record evaluation and
report generation use one shared candidate view.

The live recommended action is the primary freshness guard. A saved closure remains
current only while the current candidate still recommends `insufficient_hints`.
Subject/object hint edits can change `recommended_action` to
`factorization_needs_resynthesis`; that transition must make the closure stale even
if other fingerprint inputs happened to match.

A closure record is current only when:

- the normal decision record shape validates;
- the candidate still resolves;
- the candidate is still an `insufficient_hints` candidate;
- the current assertion fingerprint equals the recorded fingerprint.

If the assertion set grows, shrinks, changes stance, or changes exact text, the record
becomes stale and the candidate resurfaces. If the candidate remains present but its
recommended action is no longer `insufficient_hints`, the stale reason is
`candidate-no-longer-sparse-hints`. If it remains an `insufficient_hints` candidate
but the fingerprint changed, the stale reason is `assertion-fingerprint-changed`.
Saved closure cannot hide new evidence, changed statement hints, or escalated
factorization work.

## 6. Storage Model

Reuse the existing decision log:

```text
results/proposition-reconciliation/decisions.jsonl
```

Extend Lane B decision records with an optional `assertion_fingerprint` field. The
field is required for `accepted_sparse_hints` and absent for existing decision types.
Because `DecisionRecord` is a frozen dataclass with fixed load/save helpers, this
field must be added explicitly to:

- `DecisionRecord`;
- `decision_record_to_json`;
- `decision_record_from_json`;
- `_validate_record_shape`.

Example:

```json
{
  "schema_version": 1,
  "decision_id": "reconcile-decision:...",
  "judgment_id": "reconcile:judgment/...",
  "candidate_id": "reconcile:factorization/...",
  "lane": "factorization_disagreement",
  "decision": "accepted_sparse_hints",
  "members": [],
  "proposition": "proposition:bes-does-not-rescue-underpowered-studies-by-pooling-data",
  "assertion_fingerprint": "sha256:...",
  "confidence": "high",
  "rationale": "The current proposition is already factored; the remaining candidate reflects sparse source-statement hint metadata, not a reconciliation need.",
  "source_review": "results/proposition-reconciliation/review.json",
  "review_source": "llm-review:codex-gpt-5:proposition-reconcile-v1",
  "recorded_at": "2026-07-03"
}
```

Do not bump the decision-log schema version solely for this additive field. Existing
records remain valid. Unknown fields remain load-time errors under the existing
fail-loud record parser; this field is explicitly known and validated.

For `accepted_sparse_hints`, `decision_id` must include
`assertion_fingerprint` in its hashed refs. This is required for re-closure:

1. a reviewer records closure for fingerprint `F1`;
2. the assertion set changes and the `F1` record becomes stale;
3. a reviewer records closure for fingerprint `F2`;
4. `F2` must produce a distinct `decision_id`, while a repeated `F2` apply remains
   idempotent.

Existing decision types keep their current ID inputs. The implementation can either
pass the fingerprint as an extra ref to `decision_record_id` for
`accepted_sparse_hints`, or add a narrow helper that derives closure IDs with the
same canonical ordering.

## 7. Command And Data Flow

Review flow:

1. `science annotate reconcile-propositions --all --format scaffold` includes current
   sparse-hint factorization candidates.
2. Reviewer writes a reviewed judgment with decision `accepted_sparse_hints`.
3. `validate-proposition-reconciliation` validates the reviewed file against the
   current report.
4. `plan-proposition-reconciliation --input review.json` emits an advisory
   `record_reconciliation_decision` action for `accepted_sparse_hints`. The action
   carries `assertion_fingerprint`, computed by `_action_from_factorization` from the
   candidate's `observed_statement_hints`.
5. `record-proposition-reconciliation-decisions --input plan.json --apply` appends
   the decision record with the assertion fingerprint. `record_from_action_payload`
   reads the fingerprint from the action payload; it must not try to recompute it,
   because it has only the serialized action, not the live candidate.
6. Future `reconcile-propositions --all` reports suppress the candidate while the
   closure record remains current.

The existing `cleanup_factorization_hints` advisory action can remain as a suggested
operation for unreviewed `insufficient_hints` candidates. Once the reviewer chooses
`accepted_sparse_hints`, the action kind should be the persistable
`record_reconciliation_decision`, not a hint-cleanup action.

## 8. Diagnostics

Extend reviewed-decision diagnostics with sparse-hint closure state:

- active reviewed decisions include `accepted_sparse_hints` records that currently
  suppress candidates;
- stale reviewed decisions include a reason, using existing broad stale reasons where
  possible and adding `candidate-no-longer-sparse-hints` for action-class drift and
  `assertion-fingerprint-changed` for changed sparse-hint inputs;
- conflicting records for the same proposition and lane suppress nothing;
- duplicate records remain benign and reported as duplicates.

This relies on the existing factorization decision scope: Lane B decisions on the
same proposition share a scope. A current `split_possible` record and a current
`accepted_sparse_hints` record for the same proposition therefore conflict, and the
report suppresses nothing for that scope.

JSON summary fields should continue to distinguish generated from active candidate
counts:

- `generated_factorization_disagreements`
- `factorization_disagreements`
- `reviewed_decisions`
- `stale_reviewed_decisions`
- `conflicting_reviewed_decisions`

Table output should make closed sparse-hint candidates visible in the reviewed
decision counts without listing them as active work by default. `--show-reviewed`
should include them with the covering `decision_id`.

## 9. Error Handling

Fail early on malformed closure records:

- missing `assertion_fingerprint` for `accepted_sparse_hints`;
- fingerprint with the wrong prefix or shape;
- `accepted_sparse_hints` used outside Lane B;
- empty rationale;
- unsupported extra fields.

Live-report conditions are not record-shape conditions. A current recommended-action
mismatch is a `build_record_decision_plan` blocker for a new action and an
evaluation-time stale reason for an existing record; it must not live in
`_validate_record_shape` or `load_decision_records`, because aged records must not
make the whole decision log load-fatal. Similarly, missing candidates and stale
fingerprints are evaluation-time stale states, not malformed JSON records.

Do not silently downgrade these to ordinary stale decisions when the record itself is
malformed. Staleness is for once-valid decisions whose live candidate changed.

## 10. Testing

Unit tests:

- `accepted_sparse_hints` validates for a current `insufficient_hints` factorization
  candidate.
- It is rejected for `stance_review_needed`, `factorization_needs_resynthesis`,
  Lane A candidates, and missing candidates.
- Decision records require `assertion_fingerprint` only for
  `accepted_sparse_hints`.
- A closure record becomes stale when the current assertion fingerprint changes.
- A closure record becomes stale when the current candidate no longer recommends
  `insufficient_hints`.
- Re-closing after stale fingerprint drift appends a new decision record instead of
  reporting `already_recorded`; re-applying the same fingerprint remains idempotent.
- Current closure suppresses the candidate from JSON and scaffold output by default.
- `--show-reviewed` includes the closed candidate with the reviewed decision id.

CLI tests:

- scaffold -> review -> validate -> plan -> record dry-run -> record apply -> report
  suppression.
- duplicate apply is idempotent and reports `already_recorded`.
- stale closure does not suppress a resurfaced candidate.

Real-corpus smoke:

- Record reviewed closure for
  `proposition:bes-does-not-rescue-underpowered-studies-by-pooling-data`.
- Inspect
  `proposition:conceptual-replication-evidence-can-be-aggregated-over-informative-hypotheses`
  with the same vocabulary; choose closure only if the review rationale explicitly
  accepts the broad cross-method claim.
- After accepted closures, `reconcile-propositions --all` should report zero active
  candidates, zero faults, and reviewed decision counts greater than zero.

## 11. Non-Goals And Follow-Ups

Phase 4f is not the richer claim-family feature. It does not cluster statement hints,
infer missing subject/object fields, or decide whether BES and PBF should be modeled
as separate narrower propositions.

Likely follow-ups:

- richer claim-family suggestions for candidates that truly need more context;
- a dedicated stale-decision review surface if decision logs accumulate many stale
  records;
- optional hint-cleanup tooling for cases where the reviewer decides metadata should
  be improved rather than accepted as sparse.

The important boundary is that closure is reviewed, scoped, and stale-aware. It keeps
the reconciliation queue quiet only when the live candidate still matches the exact
evidence shape that was reviewed.

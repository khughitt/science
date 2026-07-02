# Proposition Reconciliation Phase 4e: Reviewed Decision Persistence

Date: 2026-07-02

## 1. Goal

Phase 4e can now generate reconciliation candidates, validate reviewed judgments,
plan safe actions, apply canonicalization and factorization resynthesis, expose
lineage in the graph, and archive settled superseded propositions.

One workflow gap remains: reviewed advisory decisions are not durable inputs to
future candidate generation. Half B emits advisory `record_reconciliation_decision`
actions for judgments such as `related_but_distinct`, `conflict_or_negation`,
and `split_possible`, but no command records those decisions as project state. The
same reviewed candidate can therefore keep resurfacing.

This phase adds a narrow persistence surface for reviewed reconciliation decisions
and teaches reconciliation reporting to acknowledge current saved decisions without
letting stale decisions hide real work.

## 2. Scope

In scope:

- a project-local, append-only reconciliation decision log;
- a deterministic apply command for Half B advisory
  `record_reconciliation_decision` actions;
- validation that every saved decision still anchors to the current reconciliation
  report;
- report-time suppression or annotation of candidates covered by current saved
  decisions;
- table and JSON diagnostics for active, stale, duplicate, and superseded decisions.

Out of scope:

- changing review-file validation vocabulary;
- changing candidate heuristics or belief aggregation;
- persisting mutation decisions that already have stateful apply surfaces
  (`same_claim` canonicalization and `factorization_needs_resynthesis` resynthesis);
- persisting blocked review outcomes such as `stance_review_needed` and `needs_human`;
- accepting unreviewed agent output;
- making decision logs a graph materialization input;
- signing or approval metadata beyond the existing reviewed source string.

## 3. Storage Model

Use a project-local JSONL file:

```text
results/proposition-reconciliation/decisions.jsonl
```

Each line is one immutable record:

```json
{
  "schema_version": 1,
  "decision_id": "reconcile-decision:5f0b...",
  "judgment_id": "reconcile:judgment/...",
  "candidate_id": "reconcile:same-claim/...",
  "lane": "same_claim",
  "decision": "related_but_distinct",
  "members": ["proposition:a", "proposition:b"],
  "proposition": null,
  "confidence": "high",
  "rationale": "The propositions share sources but make different claims.",
  "source_review": "results/proposition-reconciliation/review.json",
  "review_source": "llm-review:codex-gpt-5:proposition-reconcile-v1",
  "recorded_at": "2026-07-02"
}
```

For Lane A, `members` is the reviewed member set and `proposition` is `null`. For
Lane B `split_possible` decisions use `proposition` for the reviewed proposition and
leave `members` empty.

`decision_id` is deterministic:

```text
reconcile-decision: + sha256(lane\0decision\0judgment-id\0primary-ref\0sorted-refs...)
```

The ID does not include file paths, model names, rationale, confidence, or dates.
Those fields can change without altering the semantic decision key. The append path
deduplicates by `decision_id`: an existing identical semantic decision is reported
as already recorded and not appended again.

The log is intentionally outside `entities/`. It is reviewed project state, not a
proposition or evidence entity. The reconciliation commands should treat it as a
first-class input, but graph materialization should ignore it in this phase.

## 4. Command Surface

Add a flat `annotate` command:

```text
science annotate record-proposition-reconciliation-decisions \
  --input results/proposition-reconciliation/plan.json \
  [--root .] \
  [--decisions results/proposition-reconciliation/decisions.jsonl] \
  [--format table|json] \
  [--apply]
```

`--input` is a Half B action plan, not a raw review file. That keeps this command
small: Half B has already resolved review documents, classified actions, and detected
cross-action conflicts. The persistence command only considers actions with:

```text
kind == "record_reconciliation_decision"
status == "advisory"
```

Dry run reports records that would be appended, records already present, and blockers.
`--apply` appends only unrecorded, currently valid decisions. The command creates the
parent directory when applying, but dry run does not write.

Invalid or blocked action-plan inputs fail early:

- malformed JSON;
- unsupported `schema_version`;
- plan contains top-level `errors`;
- advisory action has local blockers;
- advisory action lacks the fields required for its lane;
- action no longer validates against the current reconciliation report.

This command deliberately does not persist ready mutation actions. Canonicalization
and resynthesis have their own apply commands that mutate proposition files and
sidecars; duplicating them in the decision log would create a second source of truth.

## 5. Validation Semantics

Validation rebuilds the current reconciliation report before accepting a saved or
new decision. A decision is current only when it can be resolved back to the current
candidate graph using the same anchoring rules as review validation.

Lane A current decision:

- `candidate_id` either matches a current same-claim candidate directly, or is a
  splittable subset candidate ID that reanchors through the current splittable
  component;
- `members` is non-empty and is the reviewed set;
- `judgment_id` equals `judgment_id("same_claim", decision, members)`;
- the decision is one of `related_but_distinct` or `conflict_or_negation`;
- current candidate evidence still includes at least one pair edge among `members`.

Lane B current decision:

- `candidate_id` matches the current factorization candidate for `proposition`;
- `judgment_id` equals `judgment_id("factorization_disagreement", decision, [proposition])`;
- the decision is `split_possible`;
- the candidate is still present in the current factorization report.

Stale decisions are not used for suppression. They remain in the append-only log as
historical review records and are surfaced by diagnostics. The first implementation
should report at least `candidate-missing` and `members-no-longer-edge-connected`.
More specific stale reasons such as `judgment-id-mismatch` or `proposition-missing`
can be added when they are useful, but the read path must not pretend a stale record
covers the current candidate.

## 6. Report Integration

`science annotate reconcile-propositions` should load the decision log by default
when it exists. The default report should separate:

- active candidates that still need review;
- reviewed decisions that currently cover generated candidates;
- stale decision records that no longer anchor to the current report.

For JSON output, add a block such as:

```json
{
  "reviewed_decisions": {
    "active": [
      {
        "decision_id": "reconcile-decision:...",
        "candidate_id": "reconcile:same-claim/...",
        "lane": "same_claim",
        "decision": "related_but_distinct",
        "members": ["proposition:a", "proposition:b"]
      }
    ],
    "stale": [
      {
        "decision_id": "reconcile-decision:...",
        "reason": "candidate-missing"
      }
    ]
  }
}
```

By default, current covered advisory candidates should be omitted from the main
candidate lists and counted in `summary.reviewed_decisions`. The filtered list counts
must match the post-filter lists; if generated totals are useful, expose them under
separate names such as `generated_same_claim_candidates`. A `--show-reviewed` option
can include covered candidates in the main lists with `reviewed_decision_id`
annotations.

The existing `scaffold` format shares the JSON payload path. It should use the same
default suppression behavior as JSON so scaffold output does not keep asking for
review of already-recorded advisory decisions. `--show-reviewed` should affect
`scaffold` and `json` consistently.

This keeps normal review queues focused while preserving auditability. Stale
decisions should never suppress candidates; if a candidate resurfaces because its
shape changed, it belongs back in the active queue.

## 7. Conflict And Duplicate Handling

The decision log is append-only, but report-time interpretation should stay usable:

- duplicate `decision_id` records are benign and reported as duplicates;
- two current decision records covering the same Lane A member set with different
  decisions are reported as conflicts and suppress nothing for that member set;
- a current advisory decision conflicting with a current ready mutation action should
  still be handled by Half B plan conflict rules before persistence;
- stale records are never conflicts with current records.

The persistence command deduplicates before append, so duplicate records should only
come from manual edits or merges. Conflicts can happen when a reviewer legitimately
changes their mind about an unchanged candidate, or when two branches append different
decisions. Since this phase has no explicit supersede record, the read path must not
make `reconcile-propositions` unusable. It should surface the conflict in diagnostics,
leave the candidate active, and let a later revision/supersede mechanism decide how
to retire the older decision.

The persistence command should be stricter than the read path: if appending a new
record would create a current same-scope conflict with an existing current record, it
should report a blocker and not append that record.

## 8. Data Flow

Dry-run/apply flow:

1. Load the Half B action plan.
2. Select advisory `record_reconciliation_decision` actions.
3. Rebuild the current reconciliation report.
4. Resolve each selected action against the current report.
5. Build deterministic decision records.
6. Load existing decision log if present.
7. Report would-append, already-recorded, stale-existing, and blockers.
8. On `--apply`, append only would-append records, sorted by `decision_id`.

Report flow:

1. Build reconciliation candidates as today.
2. Load and validate decision-log records if present.
3. Remove current covered advisory candidates from the active queue by default.
4. Include active/stale reviewed decision diagnostics in JSON and table summaries.

## 9. Testing

Core tests:

- advisory Half B action maps to a deterministic decision record;
- dry run does not create the log;
- apply appends one JSONL line and is idempotent on repeat;
- stale action-plan input fails before append;
- current saved Lane A decision suppresses the matching same-claim candidate;
- current saved Lane B decision suppresses the matching factorization candidate;
- stale saved decision does not suppress a candidate and reports a reason;
- splittable subset decisions reanchor through a larger current component;
- conflicting current decision records are reported as diagnostics and suppress
  nothing;
- malformed JSONL records fail loud with line numbers.

CLI tests:

- `record-proposition-reconciliation-decisions --input plan.json --format json` reports
  would-append records;
- `--apply` creates the default decisions file;
- `reconcile-propositions --format json` includes reviewed decision diagnostics;
- `reconcile-propositions --show-reviewed --format json` includes covered candidates
  annotated with decision ids.

Real-corpus smoke:

1. Generate a reconciliation plan from a reviewed advisory file.
2. Dry-run record decisions and inspect JSON output.
3. Apply the decision log in a worktree.
4. Re-run `reconcile-propositions` and confirm the reviewed candidate leaves the
   active queue while appearing under reviewed diagnostics.

## 10. Non-Goals And Future Work

This phase is only review-memory for reconciliation candidates. Later work may add:

- agent-assisted filling of Half D resynthesis drafts;
- richer claim-family clustering for factorization candidates;
- signed approval snapshots;
- graph materialization of decision records if a concrete consumer needs it;
- pruning or compaction tools for stale historical decisions.

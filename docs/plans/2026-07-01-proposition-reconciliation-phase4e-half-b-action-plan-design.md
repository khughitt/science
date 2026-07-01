# Proposition Reconciliation Phase 4e Half B: Reviewed Judgments to Action Plans

Date: 2026-07-01

## 1. Goal

Phase 4e Half A generates deterministic reconciliation candidates and validates
reviewed judgments. Half B consumes those validated judgments and turns them into
a safe, inspectable action plan.

The action plan is not an apply engine. It is a durable bridge between reviewed
judgment and future mutation/resynthesis work:

- it validates that reviewed judgments still match the current corpus;
- it translates each judgment into explicit intended actions;
- it reports blockers and preconditions before any write path exists;
- it gives humans and later tooling a stable artifact to review.

The immediate motivating case is the reviewed BES judgment in
`meta/results/proposition-reconciliation/2026-07-01-bes-pooled-meta-analysis-review.json`:
`proposition:bes-behaves-like-pooled-meta-analysis` should be resynthesized rather
than treated as one stable proposition with simple support/dispute evidence.

## 2. Scope

In scope:

- read one or more reviewed reconciliation JSON files;
- validate each review with the existing `validate_review_doc` gate;
- build a deterministic action plan from accepted judgments;
- detect conflicts between reviewed judgments;
- expose table and JSON CLI output;
- optionally write the plan JSON to a user-selected path.

Out of scope:

- editing proposition files;
- rewriting sidecar `sci:promotedTo` backlinks;
- archiving, redirecting, or canonicalizing propositions;
- running 4c synthesis automatically;
- changing belief aggregation or cross-paper evidence derivation;
- accepting unreviewed agent output.

## 3. CLI Surface

Add a flat `annotate` command, following the existing 4e CLI convention:
This follows the validator-style command naming (`validate-proposition-reconciliation`)
rather than the generator's verb-first `reconcile-propositions` name because this
command consumes reviewed artifacts. Unlike the validator, `--input` is repeatable so
one project-level plan can be built from several reviewed files.

```text
science annotate plan-proposition-reconciliation \
  --input results/proposition-reconciliation/review.json \
  [--input another-review.json] \
  [--root .] \
  [--format table|json] \
  [--output results/proposition-reconciliation/plan.json]
```

Behavior:

- `--input` is repeatable and required;
- `--root` defaults to the current working directory;
- `--format table` prints a compact summary plus one row per action;
- `--format json` prints the full action plan;
- `--output` writes the full JSON action plan and does not mutate entities.

If `--output` is passed with `--format table`, the command still writes the JSON plan
and prints the table summary. This mirrors the common pattern that reports are
human-readable by default but durable artifacts are JSON.

## 4. Plan Model

The output is a single versioned object:

```json
{
  "schema_version": 1,
  "source_reviews": [
    "results/proposition-reconciliation/2026-07-01-bes-pooled-meta-analysis-review.json"
  ],
  "summary": {
    "ready_actions": 1,
    "blocked_actions": 0,
    "advisory_actions": 0,
    "errors": 0
  },
  "actions": [
    {
      "action_id": "reconcile-action:202e96c08faed3d7ab68aa2d520efe01cde36a6e87c8c06dda56b6e4dcb315ff",
      "kind": "resynthesize_proposition",
      "status": "ready",
      "decision": "factorization_needs_resynthesis",
      "candidate_id": "reconcile:factorization/b5053575c4f70203eb346acdc3e124e7063ed43c7ed6a9f0d4e6ab1ba593ff7d",
      "judgment_id": "reconcile:judgment/027c49e1e3cbbfd09e158b8e06ae02631eaf7fbb54aa7bdd03f9f849d9c7521c",
      "source_review": "results/proposition-reconciliation/2026-07-01-bes-pooled-meta-analysis-review.json",
      "review_source": "llm-review:codex-gpt-5:proposition-reconcile-v1",
      "proposition": "proposition:bes-behaves-like-pooled-meta-analysis",
      "confidence": "high",
      "rationale": "The current proposition bundles conditional meta-analysis similarity with non-pooling divergence under weak evidence.",
      "inputs": {
        "annotations": [
          "annotation:entities/papers/VanWonderen2024.source#bes-similar-meta-analysis",
          "annotation:entities/papers/VanWonderen2024.source#bes-not-pooling-underpowered",
          "annotation:entities/papers/Volker2023.source#bes-not-data-pooling"
        ],
        "papers": [
          "paper:VanWonderen2024",
          "paper:Volker2023"
        ]
      },
      "suggested_operations": [
        {
          "kind": "draft_proposition",
          "description": "Draft one or more narrower propositions from the reviewed factorization disagreement and the observed statement hints."
        },
        {
          "kind": "draft_proposition",
          "description": "Use the reviewer rationale as context, but do not synthesize new claim-family prose in the planner."
        },
        {
          "kind": "reassign_annotations",
          "description": "After new propositions are reviewed, move each annotation backlink to the proposition it actually supports or disputes."
        }
      ],
      "preconditions": [
        "review judgment validates against the current reconciliation candidate",
        "target proposition exists in the current reconciliation report"
      ],
      "blockers": [],
      "writes": []
    }
  ],
  "errors": []
}
```

`writes` is deliberately empty in Half B. It reserves the field for a later apply
phase while making it impossible to confuse the Half B artifact with an executable
mutation plan.

`source_review` is the path to the reviewed JSON file that produced the action.
`review_source` is the reviewed file's declared `llm-review:<model>:proposition-reconcile-v1`
source string. Both are kept because one anchors the artifact on disk and the other
records the reviewed agent/source identity.

## 5. Judgment Mapping

### `factorization_needs_resynthesis`

Emit a `resynthesize_proposition` action.

Status is `ready` when:

- the current review validates;
- the proposition exists;
- there is no competing action for the same proposition.

The action includes the factorization candidate's observed statement hints, papers,
annotations, disagreement labels, and reviewer rationale. Suggested operations are
deterministic templates keyed by the reviewed decision and candidate disagreement
labels. The planner may copy the reviewer rationale and observed statement hints into
the action, but it must not invent polished claim-family descriptions. For the BES
case, the plan can say "draft narrower propositions from this factorization
disagreement"; the human or a later reviewed synthesis step supplies the actual new
claim wording.

### `same_claim`

Emit a `canonicalize_propositions` action.

The action records:

- canonical proposition;
- duplicate members from the judged member set only;
- source refs that would move to the canonical proposition;
- sidecar backlinks that would need rewriting;
- propositions that would eventually be archived or redirected.

Status is `ready` only if all member propositions still exist in the current
reconciliation snapshot and no member appears in another action. Half B does not choose
new canonicalization behavior beyond what the review already approved.

For splittable same-claim components, the action payload is scoped to the reviewed
`members` list, not the full generated component. If a generated component contains
`{a,b,c}` and the reviewer marks only `{a,b}` as `same_claim`, the resulting
`canonicalize_propositions` action may move only `b` into `a`; it must not propose
source-ref moves, sidecar rewrites, or archive candidates for `c`.

### `related_but_distinct` and `conflict_or_negation`

Emit advisory actions. These are reviewed decisions not to merge. The plan records the
decision and rationale so future tooling can avoid repeatedly surfacing the same
candidate without re-review.

### `stance_review_needed`, `split_possible`, `insufficient_hints`, `needs_human`

Emit blocked or advisory actions, depending on the decision:

- `stance_review_needed`: blocked until the relevant annotation stances are reviewed;
- `split_possible`: advisory; if another reviewed file also chooses a mutation-oriented
  action for the same proposition, the generic cross-action conflict rule blocks both
  actions;
- `insufficient_hints`: advisory metadata cleanup action;
- `needs_human`: blocked with the reviewer rationale as the next-step description.

## 6. Conflict and Error Handling

The planner fails early for invalid review documents. It does not produce a partial
plan when `validate_review_doc` rejects an input. It also treats non-empty
`review_incomplete` from `validate_review_doc` as a blocker: the reviewed file is
schema-valid, but the generated same-claim component has unreviewed members, so
canonicalization actions from that file are blocked until the component is fully
accounted for.

`ReconciliationReport.faults` become top-level plan `errors`. These are project-level
reconciliation problems such as scanner faults or `component-too-large` groups. The
planner may still emit actions for reviewed candidates that validate cleanly, but the
summary reports non-zero `errors`, and each fault is preserved with `reason`, `detail`,
and `members`.

Each input review file must contribute at least one resolved judgment. A review file
with an empty `judgments` list is rejected even if other `--input` files contain valid
judgments; silently dropping empty reviewed artifacts would make batch plans ambiguous.

After validation, conflicts become plan-level blockers rather than Python exceptions
when a complete report is still useful:

- two different actions target the same proposition;
- a proposition is both canonical and duplicate in different reviewed judgments;
- two `same_claim` judgments choose different canonical propositions for overlapping
  member sets;
- a reviewed advisory decision conflicts with a ready mutation-oriented action.

A cross-action conflict blocks every action it involves, not just one: for the
different-canonical case above, both `canonicalize_propositions` actions are marked
`blocked` and each carries a `blockers` entry naming the other action, so the conflict
is legible from either side.

The plan's top-level `errors` list is reserved for project-level reconciliation
problems (scanner faults, `component-too-large` groups) and input-level issues, whether
or not they block individual actions. Each blocked action carries local `blockers` with
enough context to resolve the issue.

## 7. Deterministic IDs

Action IDs are deterministic full-SHA-256 refs:

```text
reconcile-action: + sha256(action-kind\0judgment-id\0primary-ref\0each-sorted-secondary-ref)
```

Examples:

- `resynthesize_proposition` primary ref: the proposition;
- `canonicalize_propositions` primary ref: the canonical proposition, secondary refs:
  duplicate members;
- Lane B advisory decisions primary ref: the proposition;
- Lane A advisory decisions primary ref: the candidate id, secondary refs: judged
  members.

IDs change when the reviewed judgment or action target changes. They do not include
file paths, model names, timestamps, or table ordering.

The `actions` array is sorted by `action_id`. This keeps JSON output reproducible
without coupling the IDs to presentation order.

## 8. Validation and State Anchoring

The planner reuses the Half A validation stack:

1. build the current reconciliation report from the project root;
2. load each review JSON;
3. run `validate_review_doc(review, current_report)`;
4. resolve each validated judgment back to its current candidate object;
5. translate resolved judgments into plan actions;
6. check action-level conflicts.

This means candidate IDs and judgment IDs stay stale-sensitive. A plan cannot be built
from a review file that no longer matches the current candidate graph.

The action plan should include the review file paths that produced it. It should not
embed wall-clock timestamps; reproducibility comes from the validated inputs and
deterministic IDs.

Half A currently builds `PropositionSnapshot` values inside `build_reconciliation_report`
and discards them after candidate generation. Half B needs those snapshots for
`same_claim` action payloads (`source_refs`, `annotation_refs`, and paper refs). The
implementation should extend `ReconciliationReport` with a non-serialized
`proposition_snapshots` mapping, populated by the same `snapshot_from_entity` pass used
to generate candidates. This avoids a second project load and keeps the planner anchored
to the same snapshot set that validation used.

Half B should also add a small resolver helper in `proposition_reconciliation.py`, for
example `resolve_review_doc(doc, report)`, that wraps `validate_review_doc` and returns
each judgment paired with the resolved `SameClaimCandidate` or `FactorizationCandidate`.
The helper must surface, not swallow, the full `validate_review_doc` result — in
particular its `review_incomplete` list — so the planner's §6 blocker logic can consume
it alongside the resolved pairs. The planner should use that helper rather than
reimplementing the private `_candidate_indexes` / `_resolve_same_claim_candidate` logic
in another module.

## 9. Testing

Core tests:

- valid factorization review maps to one `resynthesize_proposition` action;
- valid `same_claim` review maps to one `canonicalize_propositions` action;
- stale review input fails before planning;
- non-empty `review_incomplete` blocks same-claim canonicalization;
- `ReconciliationReport.faults` populate top-level plan errors;
- duplicate or conflicting judgments produce blocked actions or top-level errors;
- deterministic `action_id` is stable across input ordering;
- actions are sorted by `action_id`;
- JSON output contains no proposed writes in Half B.

CLI tests:

- `plan-proposition-reconciliation --input review.json --format json` emits a valid plan;
- repeated `--input` files are accepted;
- `--output plan.json` writes the JSON plan while table output remains readable;
- invalid review input exits non-zero with the validation message.

Real-corpus smoke:

```text
cd meta
PYTHONPATH=../science/src:../science/model/src uv run --frozen --project ../science \
  science annotate plan-proposition-reconciliation \
  --input results/proposition-reconciliation/2026-07-01-bes-pooled-meta-analysis-review.json \
  --format json
```

Expected: if the committed review still matches the current generated candidate, the
command emits a JSON plan containing a `resynthesize_proposition` action for
`proposition:bes-behaves-like-pooled-meta-analysis` with `status: ready` and
`writes: []`. Inspect `summary.errors` rather than pinning it to zero; those errors
reflect current project-wide reconciliation faults, not necessarily Half B failures.

## 10. Future Apply Phase

A later phase may consume `canonicalize_propositions` and `resynthesize_proposition`
actions, but it should be a separate design because it must choose mutation semantics:

- how new proposition files are drafted or accepted;
- whether 4c synthesis is invoked or only scaffolded;
- how old broad propositions are archived, superseded, or retained as synthesis nodes;
- how sidecar backlinks are rewritten safely;
- how cross-references and graph freshness are preserved.

Half B intentionally stops before those choices. Its job is to make the reviewed intent
concrete enough that the future apply phase can be designed against real action-plan
artifacts instead of raw review judgments.

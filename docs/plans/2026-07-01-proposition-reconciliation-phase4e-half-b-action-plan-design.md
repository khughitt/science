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
          "description": "Draft a narrower proposition for BES/meta-analysis similarity under adequate-power or compatible-study settings."
        },
        {
          "kind": "draft_proposition",
          "description": "Draft a narrower proposition for BES not behaving as pooled data rescue when individual studies are underpowered."
        },
        {
          "kind": "reassign_annotations",
          "description": "After new propositions are reviewed, move each annotation backlink to the proposition it actually supports or disputes."
        }
      ],
      "preconditions": [
        "review judgment validates against the current reconciliation candidate",
        "target proposition exists and is active"
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

## 5. Judgment Mapping

### `factorization_needs_resynthesis`

Emit a `resynthesize_proposition` action.

Status is `ready` when:

- the current review validates;
- the proposition exists;
- the proposition is active;
- there is no competing action for the same proposition.

The action includes the factorization candidate's observed statement hints, papers,
annotations, disagreement labels, and reviewer rationale. Suggested operations are
derived from the observed stance/context pattern, but remain descriptive. For the BES
case, the suggested operations name the two claim families already visible in the
review: conditional similarity to meta-analysis, and non-pooling divergence under
weak or boundary-adjacent evidence.

### `same_claim`

Emit a `canonicalize_propositions` action.

The action records:

- canonical proposition;
- duplicate members;
- source refs that would move to the canonical proposition;
- sidecar backlinks that would need rewriting;
- propositions that would eventually be archived or redirected.

Status is `ready` only if all member propositions still exist and no member appears in
another action. Half B does not choose new canonicalization behavior beyond what the
review already approved.

### `related_but_distinct` and `conflict_or_negation`

Emit advisory actions. These are reviewed decisions not to merge. The plan records the
decision and rationale so future tooling can avoid repeatedly surfacing the same
candidate without re-review.

### `stance_review_needed`, `split_possible`, `insufficient_hints`, `needs_human`

Emit blocked or advisory actions, depending on the decision:

- `stance_review_needed`: blocked until the relevant annotation stances are reviewed;
- `split_possible`: advisory unless the reviewer also chose
  `factorization_needs_resynthesis`;
- `insufficient_hints`: advisory metadata cleanup action;
- `needs_human`: blocked with the reviewer rationale as the next-step description.

## 6. Conflict and Error Handling

The planner fails early for invalid review documents. It does not produce a partial
plan when `validate_review_doc` rejects an input.

After validation, conflicts become plan-level blockers rather than Python exceptions
when a complete report is still useful:

- two different actions target the same proposition;
- a proposition is both canonical and duplicate in different reviewed judgments;
- two `same_claim` judgments choose different canonical propositions for overlapping
  member sets;
- an action references a proposition that exists but is inactive;
- a reviewed advisory decision conflicts with a ready mutation-oriented action.

The plan's top-level `errors` list is reserved for input-level or project-level issues
that prevented action construction but did not invalidate the review file itself. Each
blocked action carries local `blockers` with enough context to resolve the issue.

## 7. Deterministic IDs

Action IDs are deterministic full-SHA-256 refs:

```text
reconcile-action: + sha256(action-kind\0judgment-id\0primary-ref\0each-sorted-secondary-ref)
```

Examples:

- `resynthesize_proposition` primary ref: the proposition;
- `canonicalize_propositions` primary ref: the canonical proposition, secondary refs:
  duplicate members;
- advisory candidate decisions primary ref: the candidate id.

IDs change when the reviewed judgment or action target changes. They do not include
file paths, model names, timestamps, or table ordering.

## 8. Validation and State Anchoring

The planner reuses the Half A validation stack:

1. build the current reconciliation report from the project root;
2. load each review JSON;
3. run `validate_review_doc(review, current_report)`;
4. translate validated judgments into plan actions;
5. check action-level conflicts.

This means candidate IDs and judgment IDs stay stale-sensitive. A plan cannot be built
from a review file that no longer matches the current candidate graph.

The action plan should include the review file paths that produced it. It should not
embed wall-clock timestamps; reproducibility comes from the validated inputs and
deterministic IDs.

## 9. Testing

Core tests:

- valid factorization review maps to one `resynthesize_proposition` action;
- valid `same_claim` review maps to one `canonicalize_propositions` action;
- stale review input fails before planning;
- duplicate or conflicting judgments produce blocked actions or top-level errors;
- inactive target proposition blocks a mutation-oriented action;
- deterministic `action_id` is stable across input ordering;
- JSON output contains no proposed writes in Half B.

CLI tests:

- `plan-proposition-reconciliation --input review.json --format json` emits a valid plan;
- repeated `--input` files are accepted;
- `--output plan.json` writes the JSON plan while table output remains readable;
- invalid review input exits non-zero with the validation message.

Real-corpus smoke:

```text
cd meta
PYTHONPATH=../science/src uv run --frozen --project ../science \
  science annotate plan-proposition-reconciliation \
  --input results/proposition-reconciliation/2026-07-01-bes-pooled-meta-analysis-review.json \
  --format json
```

Expected: one `resynthesize_proposition` action with `status: ready`, zero writes,
and no blockers.

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

# Proposition Reconciliation Phase 4e Half D: Reviewed Factorization Resynthesis

Date: 2026-07-01

## 1. Goal

Phase 4e Half A generates deterministic reconciliation candidates and validates
reviewed judgments. Half B turns accepted judgments into a read-only action plan.
Half C applies only reviewed `same_claim` canonicalization. Half D closes the other
ready action shape: reviewed `factorization_needs_resynthesis` judgments that Half B
reports as `resynthesize_proposition`.

Half D should make factorization resynthesis executable without letting the executor
invent scientific claims. It does this by inserting a reviewed resynthesis draft
artifact between the Half B action and mutation:

1. `reconcile-propositions` detects factorization disagreement.
2. A review marks the candidate `factorization_needs_resynthesis`.
3. `plan-proposition-reconciliation` emits a ready `resynthesize_proposition`
   action.
4. A new scaffold command creates a draft artifact from that action.
5. An agent or curator fills the draft with explicit replacement propositions and
   annotation assignments.
6. A validate/apply command checks the draft against the live corpus and applies only
   mechanical writes.

The central invariant is that the apply command consumes only explicit draft
decisions. It can reject stale or incomplete drafts, but it cannot infer replacement
claims or decide where an annotation should go.

## 2. Scope

In scope:

- scaffolding a reviewed resynthesis draft from one ready `resynthesize_proposition`
  action;
- validating draft shape, provenance, candidate identity, annotation assignments,
  and replacement proposition records;
- minting replacement proposition files from reviewed draft content;
- rewriting selected annotation sidecar `promoted_to` backlinks from the broad
  original proposition to replacement propositions;
- deriving required `paper:` and `annotation:` `source_refs` from assignments;
- marking the broad original proposition superseded when the draft says it is fully
  replaced;
- partial split behavior where some annotations remain on the original proposition;
- table and JSON reports for scaffold, validate, and apply surfaces.

Out of scope:

- automatic claim wording;
- automatic grouping of hints into replacement claim families;
- applying saved Half B plan JSON as executable authority;
- applying Half B `resynthesize_proposition` actions directly;
- changing belief semantics;
- deleting proposition files;
- moving proposition files into archive storage;
- materializing the graph as an implicit side effect;
- authoring explicit `sci:supersedes` relations.

## 3. Design Choice

Use a new reviewed resynthesis draft artifact, not an extension of the Half B review
file.

Half B review files answer one question: "what kind of reconciliation decision does
this candidate need?" A Half D draft answers a different question: "what exact
replacement propositions and annotation rewrites have been reviewed?" Keeping those
artifacts separate avoids overloading the candidate-review vocabulary and keeps the
mutation boundary explicit.

Alternatives considered:

- **Direct apply from Half B action.** Rejected because the current action contains
  observed hints and reviewer rationale, but not enough structured, reviewed claim
  text to create valid proposition files.
- **Manual-only checklist.** Rejected because it leaves a real ready action without a
  repeatable close-the-loop path and encourages inconsistent sidecar/source-ref edits.

## 4. CLI Surface

Add three flat `annotate` commands.

```text
science annotate scaffold-proposition-resynthesis \
  --input results/proposition-reconciliation/review.json \
  --action reconcile-action:... \
  [--root .] \
  [--output results/proposition-reconciliation/resynthesis-draft.json] \
  [--format table|json]
```

The scaffold command is read-only except for writing the optional output JSON. It
rebuilds the current reconciliation report and Half B action plan from the review
input, requires exactly one selected action, and requires that action to be ready and
`kind == "resynthesize_proposition"`.

```text
science annotate validate-proposition-resynthesis \
  --input results/proposition-reconciliation/resynthesis-draft.json \
  [--root .] \
  [--format table|json]

science annotate apply-proposition-resynthesis \
  --input results/proposition-reconciliation/resynthesis-draft.json \
  [--root .] \
  [--format table|json]
```

The validate command performs the same live-corpus checks as apply and writes nothing.
The apply command uses the command name as the mutation boundary; there is no `--apply`
flag. Both commands rebuild live state and do not trust saved action-plan JSON.

## 5. Draft Artifact

The scaffold emits a JSON document with schema version `1` and source string
`llm-review:<model>:proposition-resynthesis-v1`. The `llm-review:` prefix is modeled
on the existing 4e review source convention, but the suffix is a new draft contract.

Conceptual shape:

```json
{
  "schema_version": 1,
  "source": "llm-review:codex-gpt-5:proposition-resynthesis-v1",
  "action_id": "reconcile-action:...",
  "candidate_id": "reconcile:factorization/...",
  "judgment_id": "reconcile:judgment/...",
  "source_review": "results/proposition-reconciliation/review.json",
  "original_proposition": "proposition:bes-behaves-like-pooled-meta-analysis",
  "disposition": "replace",
  "new_propositions": [
    {
      "id": "proposition:bes-behaves-like-meta-analysis-under-adequate-study-information",
      "title": "BES behaves like meta-analysis under adequate study information",
      "body": "Bayesian Evidence Synthesis can behave similarly to meta-analysis when study evidence is informative enough that adding studies increases support for the correct hypothesis.",
      "frontmatter": {
        "type": "proposition",
        "status": "active",
        "related": [],
        "source_refs": [],
        "subject": null,
        "predicate": null,
        "object": null,
        "polarity": null,
        "claim_layer": null,
        "identification_strength": null
      }
    }
  ],
  "annotation_assignments": [
    {
      "annotation": "annotation:entities/papers/VanWonderen2024.source#bes-similar-meta-analysis",
      "from": "proposition:bes-behaves-like-pooled-meta-analysis",
      "to": "proposition:bes-behaves-like-meta-analysis-under-adequate-study-information"
    }
  ],
  "context": {
    "rationale": "...",
    "observed_statement_hints": []
  },
  "notes": ""
}
```

The scaffold fills immutable identity/context fields and leaves the reviewed proposal
fields empty or skeletal. Apply treats `context` as non-authoritative. Mutation is
driven only by:

- `disposition`;
- `new_propositions`;
- `annotation_assignments`.

## 6. Draft Semantics

`disposition` is a closed enum:

- `replace`: the broad original proposition is fully replaced by the new
  proposition or propositions. Every input annotation from the Half B action must be
  assigned away from the original proposition.
- `split_partial`: some annotation assignments move to new propositions, but the
  original proposition remains active for the remaining scope. Assignments may target
  either a new proposition or the original proposition.

`new_propositions` contains reviewed proposition records. Each item supplies:

- `id`: full canonical proposition id, such as `proposition:...`;
- `title`: frontmatter title and body heading;
- `body`: reviewed markdown body content below the heading;
- `frontmatter`: additional proposition frontmatter fields.

The renderer owns canonical frontmatter ordering and dates. It may derive or override:

- `id`;
- `type`;
- `title`;
- `status`;
- `created`;
- `updated`;
- `source_refs`.

Draft frontmatter may include proposition model fields such as `subject`, `predicate`,
`object`, `polarity`, `claim_layer`, `identification_strength`, `related`, and
`ontology_terms`. Unknown frontmatter keys should fail validation rather than being
silently preserved.

`annotation_assignments` is the authoritative annotation rewrite list. Each assignment
names:

- the annotation ref;
- the expected current target in `from`;
- the requested target in `to`.

The target may be a new proposition id from the draft. For `split_partial`, it may also
be the original proposition id, which records that the annotation has been reviewed and
intentionally left in place.

## 7. Validation

Validation rebuilds the current reconciliation report and Half B action plan from the
draft's `source_review`. The draft is valid only if its `action_id`, `candidate_id`,
`judgment_id`, and `original_proposition` still resolve to exactly one current ready
`resynthesize_proposition` action.

Boundary checks:

- `schema_version == 1`;
- `source` matches `^llm-review:[A-Za-z0-9._-]+:proposition-resynthesis-v1$`;
- `source_review` exists and validates as a Phase 4e reconciliation review;
- the referenced Half B action has no blockers and no top-level plan errors;
- every assignment annotation is in the action's input annotation set;
- every input annotation appears at most once in assignments;
- every assignment `from` equals the draft's original proposition;
- every live sidecar assignment currently points to `from`, unless it already points
  to `to` and all other planned writes are no-ops;
- every assignment `to` is either a draft new proposition id or, for `split_partial`,
  the original proposition id;
- `replace` assigns every action input annotation away from the original;
- `split_partial` assigns at least one annotation to a new proposition;
- every new proposition id is valid and does not already exist;
- new proposition ids are unique;
- every new proposition has at least one assigned annotation or explicit source ref;
- rendered new proposition files load through the existing entity/proposition model
  validation;
- derived `paper:` and `annotation:` source refs can be resolved for every assignment.

The validator should derive assignment source refs for reporting rather than requiring
draft authors to duplicate them. Draft-provided `source_refs` are allowed as additional
reviewed provenance, but assigned annotation and paper refs are always added by the
planner so the draft cannot drift from sidecar reality.

## 8. Apply Semantics

Apply uses the same safety model as Half C:

1. Rebuild live reconciliation state and validate the draft.
2. Scan live sidecars and current proposition files.
3. Compute final file text for every changed path in memory.
4. Refuse before writing on validation/preflight conflicts.
5. Write changed files.
6. Run postflight checks and report written paths honestly if a late failure occurs.

For each replacement proposition:

- create a new proposition file under the canonical proposition entity location;
- render reviewed title/body/frontmatter;
- derive and append assigned `paper:` and `annotation:` source refs;
- preserve explicit reviewed related/source refs where valid;
- set `status: active`;
- set `created` and `updated` to the apply date.

For each moved annotation assignment:

- rewrite the live sidecar annotation `promoted_to` from the original proposition to
  the target proposition;
- preserve all unrelated annotations and sidecar metadata;
- merge all rewrites for a shared sidecar into one final file edit.

For the original proposition:

- `replace`: mark `status: superseded`, set `superseded_by` to the sorted replacement
  proposition id when there is exactly one replacement, preserve the body, and update
  `updated`;
- `replace` with multiple replacements: mark `status: superseded`, set
  `resynthesized_into` to the sorted replacement proposition ids, leave
  `superseded_by` unset to preserve the existing scalar `superseded_by` convention,
  preserve the body, and update `updated`;
- `split_partial`: keep `status: active`; only update source refs if the planner
  needs to add explicitly retained provenance.

Half D does not add explicit `sci:supersedes` graph relations. The durable supersession
record is frontmatter on the original proposition. `superseded_by` remains the
existing single-successor field used by Half C canonicalization; `resynthesized_into`
is the Half D multi-successor field for factorized replacement.

## 9. Idempotency And No-Ops

Re-running apply with the same valid draft should converge:

- already-created replacement proposition files with exactly matching rendered content
  are no-ops;
- sidecar annotations already pointing to their requested targets are no-ops;
- an original proposition already marked with the expected `status`,
  `superseded_by`, and/or `resynthesized_into` is a no-op;
- any drift from the reviewed draft, such as changed proposition body text or an
  assignment pointing to a third proposition, is a hard error rather than silently
  overwritten.

This depends on the current project loader continuing to include superseded
propositions in reconciliation snapshots. If future archive behavior filters
superseded entities, Half D will need an explicit archived-entity lookup for
idempotent re-runs.

## 10. Postflight

Postflight rebuilds the relevant live views and checks:

- every replacement proposition file exists and loads as a proposition entity;
- every assigned annotation now points to the requested proposition;
- no `replace` input annotation remains promoted to the original proposition;
- `split_partial` assignments intentionally targeting the original still point to it;
- every replacement proposition's `source_refs` include its assigned annotation refs
  and paper refs;
- a fresh cross-paper evidence scan attributes moved literature evidence to the new
  proposition refs, not the superseded broad proposition;
- the original proposition has the expected final status and supersession fields.

Postflight failure after writes should not claim atomic rollback. The report must
include stage, written paths, and the failing invariant so the user can inspect and
repair deliberately.

## 11. Module Boundaries

Add two focused modules:

- `science_tool.annotation.proposition_resynthesis`
  - draft schema constants;
  - scaffold builder;
  - draft parser/validator;
  - JSON/table serialization for scaffold and validate reports.
- `science_tool.annotation.proposition_resynthesis_apply`
  - preflight file edit planner;
  - sidecar rewrite planner;
  - apply report;
  - postflight checks.

Half D should reuse existing helpers where possible:

- Half B `build_reconciliation_action_plan` and review loading for current action
  resolution;
- Half C sidecar scanning and final-text planning patterns;
- entity rendering helpers for proposition frontmatter/body writes;
- strict sidecar parsing and `entity_relpath_for_sidecar` for annotation refs.

This split keeps draft/review semantics separate from mutation and avoids turning
`proposition_reconciliation_apply.py` into a general reconciliation executor.

## 12. Reports

Scaffold JSON should include:

- `schema_version`;
- selected `action_id`;
- output path, if written;
- original proposition;
- input annotation count;
- replacement template count;
- scaffold document.

Validate JSON should include:

- `schema_version`;
- `status`;
- `original_proposition`;
- replacement proposition count;
- moved annotation count;
- retained annotation count;
- planned changed/no-op path counts;
- errors and warnings.

Apply JSON should include:

- `schema_version`;
- `status`;
- original proposition;
- created replacement proposition paths;
- changed and no-op paths;
- rewritten annotation refs;
- superseded original proposition state;
- diagnostics;
- written paths.

Table output should stay compact, following Half C:

```text
proposition resynthesis apply: replacements=2 moved_annotations=3 changed=4 noop=0
```

## 13. Tests

Unit tests:

- scaffold requires a ready `resynthesize_proposition` action;
- scaffold emits deterministic identity/context for the BES-style review action;
- validator rejects invalid source string;
- validator rejects stale action id, candidate id, judgment id, or original proposition;
- validator rejects unknown annotation refs;
- validator rejects duplicate annotation assignments;
- validator rejects assignments to non-draft propositions;
- validator rejects existing new proposition ids;
- validator rejects incomplete `replace`;
- validator rejects `split_partial` with no moved annotation;
- validator rejects rendered proposition records that fail existing proposition
  validation;
- apply creates replacement propositions and derives source refs;
- apply rewrites sidecar `promoted_to` values;
- apply supersedes the original proposition for `replace`;
- apply keeps the original active for `split_partial`;
- apply merges multiple rewrites in one sidecar;
- apply rejects drift where an annotation now points to a third proposition;
- second apply is a no-op;
- preflight failure writes nothing.

CLI tests:

- `scaffold-proposition-resynthesis` writes or prints a scaffold;
- `validate-proposition-resynthesis` reports valid and invalid drafts;
- `apply-proposition-resynthesis` applies a valid draft;
- malformed drafts include the input path in error output;
- selecting/applying a direct Half B `resynthesize_proposition` action through Half C
  remains refused.

End-to-end fixture:

- start with one broad proposition and three promoted literature annotations;
- review factorization as `factorization_needs_resynthesis`;
- scaffold and fill a draft with two narrower propositions;
- apply;
- rebuild cross-paper evidence;
- assert moved evidence aggregates on the replacement propositions and the broad
  proposition is superseded for `replace`.

## 14. Non-Goals And Future Work

Future work may add:

- agent-assisted draft filling from hints and reviewer rationale;
- richer claim-family suggestions from statement hints;
- archive movement for long-settled superseded broad propositions;
- explicit `sci:supersedes` relation authoring once relation conventions are pinned;
- saved-draft signing or approval metadata beyond the source string.

None of those are required for Half D. The first resynthesis surface should be
review-backed, explicit, deterministic, and narrow.

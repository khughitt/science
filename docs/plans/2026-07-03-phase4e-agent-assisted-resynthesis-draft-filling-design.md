# Proposition Reconciliation Phase 4e: Agent-Assisted Resynthesis Draft Filling

Date: 2026-07-03

## 1. Goal

Phase 4e can now take a reviewed factorization judgment all the way to a
deterministic apply surface:

1. Half A finds factorization candidates.
2. Half B turns reviewed `factorization_needs_resynthesis` judgments into ready
   `resynthesize_proposition` actions.
3. Half D scaffolds, validates, and applies reviewed resynthesis draft JSON.

The remaining friction is between Half D scaffold and Half D validate: the scaffold
is structurally safe but intentionally empty. A curator or agent must still write
replacement proposition records and annotation assignments by hand.

This phase adds an agent-assisted draft-filling workflow that turns one existing
Half D scaffold into a completed candidate draft, while preserving the same safety
boundary:

- the agent may propose claim wording and annotation assignment choices;
- the existing Half D validator remains authoritative;
- apply remains deterministic and never consumes unvalidated agent output.

## 2. Scope

In scope:

- building a deterministic resynthesis context packet from an existing Half D
  scaffold and the live project;
- giving an agent enough bounded context to propose replacement propositions and
  assignments without scanning the whole repository;
- writing a completed Half D draft JSON artifact in the existing schema;
- immediately validating the completed draft with the existing
  `validate-proposition-resynthesis` semantics;
- reporting validation failures as review feedback, not silently repairing them;
- documenting an agent-facing workflow that can be run by Codex or another reviewed
  assistant.

Out of scope:

- changing Half D draft schema version `1`;
- changing Half D apply semantics;
- accepting direct writes to proposition files or sidecars from the agent;
- adding an in-process LLM provider dependency to `science_tool`;
- changing belief aggregation, graph materialization, or archive behavior;
- automatically accepting low-confidence or ambiguous factorization choices;
- adding richer deterministic claim-family clustering. That remains a later
  improvement.

## 3. Design Choice

Use a deterministic context packet plus an agent-authored filled draft.

The Python side should own only facts and validation:

```text
science annotate scaffold-proposition-resynthesis ... --output draft.scaffold.json
science annotate resynthesis-draft-context --input draft.scaffold.json --output draft.context.json
agent fills draft.scaffold.json -> draft.filled.json
science annotate validate-proposition-resynthesis --input draft.filled.json
science annotate apply-proposition-resynthesis --input draft.filled.json
```

The new command is read-only except for its optional output file. It does not call an
LLM. It expands the existing scaffold into a bounded, stable packet that an agent can
use to author the existing Half D draft. The completed draft is still just the Half D
artifact, so the current validator and apply command remain the only authority.

Alternatives considered:

- **Call an LLM directly from `science annotate`.** Rejected for this phase. It would
  add provider configuration, network behavior, retry policy, and model-version
  concerns to a command whose important job is actually deterministic context
  assembly.
- **Extend the Half D scaffold command to fill drafts.** Rejected. Scaffold creation
  is deterministic and safe today. Mixing it with agent-authored scientific wording
  would blur the authority boundary.
- **Add `--include-context` to `scaffold-proposition-resynthesis`.** Rejected for the
  first implementation. The existing scaffold is the durable draft artifact consumed
  by validate/apply. The context packet is an ephemeral prompt/input artifact that
  can be regenerated from a scaffold or from a partially filled draft during revision.
  Keeping it as a separate read-only command avoids making the mutation draft larger
  and lets the same command serve the iterative "explain this draft again" loop.
- **Use only prompt instructions, no Python context packet.** Rejected. The agent
  would have to rediscover sidecars, source refs, and current action state by
  convention, which is exactly where stale or over-broad edits tend to enter.

## 4. Command Surface

Add a flat annotation command:

```text
science annotate resynthesis-draft-context \
  --input results/proposition-reconciliation/resynthesis-draft.json \
  [--root .] \
  [--output results/proposition-reconciliation/resynthesis-context.json] \
  [--format json|markdown]
```

This intentionally diverges from sibling `table|json` commands by using
`json|markdown`. The output is a context/prompt packet, not a status table; markdown
exists only as an agent-readable rendering of the same JSON facts.

`--input` is an existing Half D scaffold or partially filled draft. The command:

1. parses the draft with `parse_resynthesis_draft`;
2. rebuilds the live Half B action plan from `draft.source_review`;
3. resolves the ready `resynthesize_proposition` action through the same live-state
   path used by Half D validation;
4. reads only the bounded files needed to explain the action;
5. emits a context packet or a markdown prompt packet.

If `--output` is omitted, output goes to stdout. `json` is the default because it is
lossless and testable. `markdown` is an agent-friendly rendering of the same content,
not a separate source of truth.

No `--apply` flag is added. This command does not mutate project state except for
writing its own optional packet file.

## 5. Context Packet

The JSON packet has schema version `1` and is derived from the current live corpus:

```json
{
  "schema_version": 1,
  "source": "derived:proposition-resynthesis-context-v1",
  "draft_path": "results/proposition-reconciliation/resynthesis-draft.json",
  "action_id": "reconcile-action:...",
  "candidate_id": "reconcile:factorization/...",
  "judgment_id": "reconcile:judgment/...",
  "original_proposition": {
    "id": "proposition:broad",
    "title": "Broad proposition",
    "body": "Current proposition body.",
    "frontmatter": {
      "subject": null,
      "predicate": null,
      "object": null,
      "polarity": null,
      "claim_layer": null,
      "identification_strength": null,
      "source_refs": []
    }
  },
  "review": {
    "decision": "factorization_needs_resynthesis",
    "confidence": "high",
    "rationale": "The annotations assert different scoped claims."
  },
  "input_annotations": [
    {
      "annotation": "annotation:entities/papers/A.source#a1",
      "paper": "paper:A",
      "stance": "asserted",
      "section": "results",
      "exact": "Quoted statement text.",
      "subject": "BES",
      "object": "meta-analysis under informative studies",
      "subject_concept": null,
      "object_concept": null,
      "current_promoted_to": "proposition:broad"
    }
  ],
  "draft_progress": {
    "disposition": "replace",
    "new_propositions": [],
    "annotation_assignments": [],
    "notes": ""
  },
  "constraints": {
    "allowed_dispositions": ["replace", "split_partial"],
    "required_assignment_annotations": ["annotation:entities/papers/A.source#a1"],
    "replacement_id_prefix": "proposition:",
    "replacement_id_policy": "canonical proposition local part; lowercase words joined by hyphens",
    "allowed_replacement_frontmatter_keys": [
      "type",
      "kind",
      "status",
      "related",
      "source_refs",
      "subject",
      "predicate",
      "object",
      "polarity",
      "claim_layer",
      "identification_strength",
      "ontology_terms",
      "discusses"
    ]
  },
  "output_contract": {
    "write": "a Half D proposition resynthesis draft JSON",
    "validate_with": "science annotate validate-proposition-resynthesis --input <draft>",
    "do_not_write": ["proposition files", "annotation sidecars", "archive rows"]
  }
}
```

The packet intentionally repeats the Half D identity fields so an agent can detect it
is filling the intended draft. The Half D validator still checks those fields against
live state; the packet is guidance, not authority.

`original_proposition` is deliberately expanded in the context packet. In the Half D
draft schema, `original_proposition` is only the proposition id string. In this
packet, the same key names an object containing that id plus title, body, and selected
frontmatter so an agent can inspect the claim it is replacing. The packet `source`
discriminator distinguishes the two schemas.

The new command's delta over the existing Half D scaffold is intentionally small:

- original proposition body and selected frontmatter;
- current live `promoted_to` per input annotation;
- current paper refs derived from each annotation sidecar;
- validator-derived constraints and output-contract guidance;
- any current partial draft progress.

The existing scaffold already carries `context.rationale`, `context.papers`, and
`context.observed_statement_hints`; this command re-presents those hints as rows keyed
by annotation ref, rather than inventing a second extraction path.

The packet should include only bounded source text:

- the original proposition body and relevant frontmatter;
- the reviewed rationale and decision metadata already present in the action;
- observed statement hints from the action inputs;
- current live `promoted_to` target for each input annotation;
- paper refs resolved from each annotation sidecar.

Per-annotation fields such as `stance`, `section`, `exact`, `subject`, `object`,
`subject_concept`, and `object_concept` come from
`action.inputs.observed_statement_hints`, joined by the `annotation` ref. The live
sidecar scan supplies only current state such as `current_promoted_to` and paper-ref
resolution. A missing observed hint for an action input is a hard context-generation
error, because the filler would otherwise receive an assignment target with no claim
text to evaluate. This is a defensive invariant rather than a user-facing recovery
path: the current Half B action input annotations are themselves derived from hint
rows, so a plain fail-loud exception is enough. The packet should not include a
statement `predicate` field until the reconciliation hint model actually exposes one.

Observed statement hints without an `annotation` ref are intentionally excluded from
`input_annotations`. They can explain why a factorization candidate exists, but they
cannot be assigned in a Half D draft because assignments require concrete annotation
refs. Keeping them out of the assignment packet avoids asking the agent to route
unassignable claim text.

`constraints.allowed_dispositions` and
`constraints.allowed_replacement_frontmatter_keys` must be derived from
`RESYNTHESIS_DISPOSITIONS` and `ALLOWED_REPLACEMENT_FRONTMATTER_KEYS`, not copied into
a second hardcoded list. The replacement id policy text is explanatory, but the actual
check remains `_replacement_local_part(...)` and the project path policy.

`draft_progress` echoes the current input draft's mutable fields so an iterative
review can regenerate context without losing partially authored work. The context
packet does not become the editable artifact; agents still write a Half D draft JSON.

It should not embed full paper text by default. If a future implementation needs more
context, add explicit opt-in fields such as nearby sentence windows. Do not silently
expand to whole-source ingestion.

The packet must contain no timestamps. Stable live input should produce byte-stable
JSON after sorted-key serialization.

## 6. Agent Workflow

The agent-facing workflow is a reviewed drafting loop:

1. Read the context packet.
2. Propose the smallest set of replacement propositions that explains the input
   annotation clusters.
3. Choose `replace` only when every input annotation belongs on a replacement
   proposition and the original broad proposition should be superseded.
4. Choose `split_partial` only when at least one input annotation should remain on
   the original proposition.
5. Assign every input annotation exactly once.
6. Use only replacement proposition ids declared in `new_propositions`, except that
   `split_partial` may assign retained annotations back to the original proposition.
7. Preserve the scaffold action identity fields unchanged:
   `action_id`, `candidate_id`, `judgment_id`, `source_review`,
   `original_proposition`, and `input_annotations`.
8. Run `science annotate validate-proposition-resynthesis` and revise until it
   passes, or stop with the validation error when scientific ambiguity prevents a
   reviewed draft.

The agent may draft:

- replacement proposition ids;
- titles;
- markdown bodies;
- recognized proposition frontmatter fields;
- annotation assignments;
- notes explaining unresolved choices.

The agent must not:

- edit source sidecars directly;
- create proposition files directly;
- invent annotations not listed in the packet;
- drop input annotations;
- weaken validation by changing schema or action identity fields;
- copy reviewer rationale wholesale into proposition bodies unless it is itself a
  claim that should be authored as proposition prose.

The draft `source` may be updated to name the actual filling model or agent, as long
as it still matches the existing Half D source contract
`llm-review:<model>:proposition-resynthesis-v1`. Changing `source` records authorship
of the draft proposal; it must not be used to bypass validation.

## 7. ID And Claim-Wording Rules

Replacement proposition ids are proposed by the agent, not assigned by an opaque
deterministic slugger. That is intentional: the id is part of the reviewed claim
surface, and a human should be able to reject a misleading local part.

The context packet still provides a deterministic policy:

- full ids must start with `proposition:`;
- local parts must satisfy the project proposition path policy;
- ids should describe the narrowed claim scope, not the source paper;
- when two replacement propositions differ only by condition, include the condition
  in the local part;
- do not encode confidence, paper count, or reviewer initials in the id.

The draft filler should prefer conservative claim wording:

- state only what the assigned annotations support;
- preserve hedging when annotations are hypothesized rather than asserted;
- split claims rather than conjoining incompatible subject/object scopes;
- use `split_partial` instead of forcing a replacement when the original broad claim
  still has a coherent residual meaning.

These are drafting rules. The validator can enforce structure and freshness, but it
cannot prove scientific adequacy of wording. That is why the output remains a reviewed
draft.

## 8. Failure Modes

The context command fails early when:

- the draft JSON is malformed;
- the draft does not resolve to a current ready `resynthesize_proposition` action;
- the live action has top-level plan errors or blockers;
- `draft.input_annotations` is stale relative to the live action;
- an input annotation no longer resolves to a live sidecar annotation;
- an input annotation has no matching `observed_statement_hints` row;
- paper ref resolution fails for an input annotation.

The agent workflow stops rather than patching around validation failures when:

- the scientific split is ambiguous;
- no replacement wording can be made faithful to the observed hints;
- replacement ids would collide with existing propositions;
- assignments require annotations outside the input set.

The completed draft may be partially useful even when validation fails. The failure
is surfaced as review feedback; no project state is mutated.

## 9. Testing

Core tests:

- context command rejects malformed draft input;
- context command rebuilds live Half B state and fails on stale action identity;
- context packet includes original proposition body/frontmatter;
- context packet includes every input annotation with paper, stance, exact text,
  subject/object hints, and current `promoted_to`;
- context generation fails when an input annotation has no matching observed
  statement hint;
- context packet omits non-input annotations from the same sidecar;
- context packet derives allowed dispositions and frontmatter keys from the existing
  Half D constants;
- context packet echoes partially filled `new_propositions`,
  `annotation_assignments`, and `notes` under `draft_progress`;
- markdown format renders the same packet content without adding new fields;
- packet generation is deterministic for stable live input and contains no
  timestamps;
- validation still rejects an agent-filled draft that drops an input annotation;
- an end-to-end fixture can scaffold, emit context, fill a draft fixture, validate,
  and then apply through existing Half D commands.

CLI tests:

- `resynthesis-draft-context --format json` prints a parseable packet;
- `--output` writes the packet and stdout behavior is explicit;
- stale sidecar or paper-ref failures are surfaced as `ClickException` messages.

Real-corpus smoke:

1. Generate or select one real reviewed `factorization_needs_resynthesis` artifact.
2. Scaffold a Half D draft.
3. Emit a context packet.
4. Have an agent fill a draft in a worktree.
5. Run validation and inspect failures or success.

The smoke should not require apply. Applying real-corpus resynthesis remains a
separate reviewed action.

## 10. Relationship To Later Work

This phase deliberately does not implement richer claim-family clustering. The agent
can use observed statement hints directly, and the context packet can expose the
current raw hints. If repeated draft attempts show the same grouping burden, a later
phase can add deterministic or reviewable claim-family suggestions to the packet.

This phase also does not persist agent attempts. The durable project state remains:

- reviewed reconciliation judgments;
- optional reviewed decision log records;
- reviewed Half D draft JSON files;
- proposition and sidecar mutations only after deterministic apply.

If a later consumer needs audit trails for failed agent attempts, add a separate
results artifact. Do not make failed draft attempts graph inputs.

## 11. Acceptance

- A user can create a Half D scaffold, generate a bounded context packet, ask an
  agent to fill the existing draft schema, and validate the result without reading
  unrelated project files.
- The new command is read-only except for its own optional output file.
- The completed draft is accepted or rejected by the existing Half D validator.
- No direct proposition, sidecar, graph, belief, or archive writes are introduced.
- The workflow makes resynthesis drafting faster while preserving the same
  epistemic boundary: agent proposes; validator checks; apply writes mechanically.

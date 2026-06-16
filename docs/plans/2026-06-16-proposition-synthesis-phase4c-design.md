# Phase 4c — Proposition reasoning synthesis (design)

**Status:** design approved (brainstorming), pending implementation plan.
**Branch:** `feat/sub-article-annotation-phase4c` (worktree `.worktrees/sub-article-annotation-phase4c`), based on local `main`.
**Predecessors:** Phase 4a (statement→proposition promotion) + 4b (question/hypothesis
promotion) shipped; this phase enriches the propositions 4a minted.

---

## 1. Goal & context

Promoting a statement annotation to a `proposition` entity (Phase 4a) deliberately
leaves the proposition's *reasoning* fields **unset**: `predicate`, `polarity`,
`claim_layer`, and frequently `subject`/`object` (4a copies subject/object only as
free-text "extraction hints" when present in the statement body, and many statements
have neither). Because `write_entity_file` serialises with `model_dump(exclude_none=True)`
(`entities.py:407`), these fields are simply **absent** from a minted proposition's
frontmatter — there is no phantom template default. "Unset" is therefore a clean,
reliable signal.

Phase 4c fills those fields. The values are *judgment-bearing*: mapping a natural-language
claim onto a closed controlled vocabulary, with interlocking validity rules. That is
agent work, not deterministic derivation — stance does not map cleanly to polarity,
PubTator relations are incomplete and often relation-level rather than claim-level, and
defaulting `claim_layer` would quietly assert semantics. So 4c follows the project's
**brain/hands split**: an LLM agent *proposes* a factorization, a deterministic Python
layer *validates and persists* it, and a curator reviews — exactly the shape of
`science annotate promote` and `science curate consolidate`.

## 2. The target vocabularies and interlocks (the rules Python enforces)

All three enums live in `science_model.reasoning`; the proposition model is
`science_model.propositions.PropositionEntity`.

- **`predicate`** (`Predicate`, 9 values, sign-free binary relations):
  `affects`, `regulates`, `associates_with`, `binds`, `is_proxy_for`,
  `induces_state`, `transitions_to`, `subtype_of`, `part_of`.
- **`polarity`** (`Polarity`, 4 values): `positive`, `negative`, `unsigned`
  (sign-apt but undetermined), `not_applicable`.
- **`claim_layer`** (`ClaimLayer`, 4 values): `empirical_regularity`, `causal_effect`,
  `mechanistic_narrative`, `structural_claim`. Independent of subject/object/predicate.

**Interlocks** — enforced in two places that this design must keep both happy:

| Rule | Model validator (`propositions.py:59-82`) | Corpus QA check (`validate/checks/propositions.py:46-93`) |
| --- | --- | --- |
| `predicate` set ⇒ `subject` **and** `object` set | raises | (n/a) |
| sign-meaningful predicate (`affects`/`regulates`/`associates_with`) ⇒ polarity ∈ {positive, negative, unsigned} | raises if not | ERROR if missing or `not_applicable` |
| sign-less predicate (the other 6) ⇒ polarity | permits `None` **or** `not_applicable` | **ERROR unless exactly `not_applicable`** |

The divergence in the last row is the reason for the **sign-less canonicalization** rule
in §7: the model accepts `None`, but the QA check (`proposition.polarity.aptitude`)
rejects it. Synthesis writes the validate-clean form so a freshly-synthesised corpus
passes `science validate` with no follow-up.

`SIGN_MEANINGFUL_PREDICATES = {affects, regulates, associates_with}` is the single
source of truth (`reasoning.py`); the synthesizer derives its sign logic from it, never
hard-codes the set.

## 3. Architecture

A new **brain** and a new **hands**, plus one small model field:

- **Agent** `proposition-synthesize` (`agents/proposition-synthesize.md`) + an
  orchestrator command (`commands/synthesize-propositions.md`). Its own prompt and its
  own versioned source identity: **`llm-synth:<model>:proposition-synthesize-v1`**
  (distinct from `paper-annotate`, which stays focused on finding grounded spans).
  The agent **self-declares** this string — including its own `<model>` — in the
  top-level `source` field of the candidates file (§6), exactly as the seeders/annotators
  self-declare their `source`. That is the *only* path by which `<model>` reaches
  deterministic apply; there is no `--model` flag to drift out of sync with the model that
  actually produced the proposals. Apply validates the string against the exact pattern
  `^llm-synth:[^:]+:proposition-synthesize-v1$` and stamps it verbatim into
  `reasoning_source` (§7).
- **CLI** `science annotate synthesize <source.md>` (a new subcommand on the existing
  `annotate` group), backed by a new module `annotation/synthesize.py` (sibling to
  `promote.py`; reuses `entity_dest`, the markdown-parse helper, and the
  `find_qualified_spans` anchorer).
  - default (read-only): emit the **scaffold** (json/yaml) for the agent;
  - `--apply --input <edited.json>`: validate + write. **Agent output is never applied
    directly** — only a curator-reviewed `--input` file is.

The agent's `candidates.json` is untrusted input. Determinism, idempotency, interlock
validation, and persistence all live in Python.

## 4. Scope — which propositions

`synthesize <source.md>` operates on the propositions reachable from **this sidecar's**
annotations via the `sci:promotedTo` backlink, where the target is a `proposition:`
(questions and hypotheses are excluded — `PropositionEntity` is the only kind carrying
these reasoning fields). Grouping the sidecar's annotations by `promoted_to` guarantees
every in-scope proposition has ≥1 supporting statement *in this sidecar*. A proposition
may also carry evidence from other papers; 4c factors from the evidence visible in this
sidecar and the curator reviews — cross-paper reconciliation is out of scope (that is 4d).

## 5. Read-only scaffold (default invocation)

The scaffold is a single object sharing the candidates file's outer wrapper (a top-level
`source` + a list): a `source` template line the agent fills with its own model, plus a
`propositions` list with one rich context entry per in-scope proposition. The agent reads
each `propositions[]` entry and emits one `candidates[]` patch (§6) — a different, smaller
shape — under the same `source`.

```jsonc
{
  "source": "llm-synth:<MODEL>:proposition-synthesize-v1",  // agent replaces <MODEL>
  "propositions": [
  {
  "proposition": "proposition:brca1-loss-genomic-instability",
  "title": "BRCA1 loss drives genomic instability",
  "current": {                         // present fields only (unset omitted)
    "subject": "BRCA1 loss", "object": null,
    "predicate": null, "polarity": null, "claim_layer": null
  },
  "statements": [                      // every supporting statement in THIS sidecar
    {
      "annotation": "annotation:papers/brca1#stmt1",
      "exact": "loss of BRCA1 leads to widespread genomic instability",
      "stance": "asserted", "section": "results",
      "subject": "BRCA1 loss", "object": "genomic instability",
      "subject_concept": "https://identifiers.org/ncbigene:672", "object_concept": null
    }
  ],
  "relation_hints": [                  // co-located Phase-2b relation predicates (NON-authoritative)
    { "predicate": "biolink:affects", "subject_iri": "...", "object_iri": "...",
      "annotation": "annotation:papers/brca1#rel3" }
  ]
  }
  ]
}
```

**Relation-hint co-location** is computed deterministically: resolve both the supporting
statement's `TextQuoteSelector` and each `relation` annotation's selector against the
**current `.source.md`** (via `find_qualified_spans`: exact + prefix/suffix, unique),
then include a relation whose resolved `[start,end)` range overlaps the statement's
range. If either selector fails to resolve cleanly (drift, ambiguity), **omit that
relation** and count/report `synthesize-relation-hint-unresolved` — never fail the
scaffold. Hints are context for the agent only; they carry no authority over the
agent's proposed `predicate`.

## 6. Candidate patch — one per proposition

The agent resolves all supporting statements + hints into **one coherent proposal per
proposition** (per-statement patches would push semantic reconciliation into the
deterministic layer, which is wrong — disagreements are semantic, not mechanical).

```jsonc
{
  "source": "llm-synth:claude-opus-4-8:proposition-synthesize-v1",  // self-declared; validated
  "candidates": [
  {
    "proposition": "proposition:brca1-loss-genomic-instability",
    "annotation": "annotation:papers/brca1#stmt1",   // anchoring evidence; validated (§7)
    "subject": "BRCA1 loss",
    "predicate": "affects",
    "object": "genomic instability",
    "polarity": "positive",
    "claim_layer": "causal_effect",
    "override": ["claim_layer"]                       // optional; see §7
  }
  ]
}
```

- The top-level `source` is required and validated against
  `^llm-synth:[^:]+:proposition-synthesize-v1$`; it is stamped verbatim into
  `reasoning_source` on any proposition that is actually written (§7).
- `annotation` is **required** and must be one of that proposition's supporting-statement
  refs from the scaffold (untrusted input is checked, not trusted). It records which
  evidence anchored the factorization; it is not separately persisted — the prop↔annotation
  link already lives in `source_refs` from 4a.
- Any of `subject`/`object`/`predicate`/`polarity`/`claim_layer` may be **omitted** —
  omitted means *leave unset*, never "guess a default".
- `override` (optional) is a closed list drawn from
  `{subject, object, predicate, polarity, claim_layer}` naming already-set fields the
  curator authorises replacing. `reasoning_source` is **never** overrideable from input.

## 7. Deterministic apply — two-pass (validate-before-write)

Validation failures here are semantic-contract failures, not per-row best-effort skips,
so the whole input is validated before **any** proposition file is written.

**Pass 1 — validate the whole input (no writes):**
1. **Top-level `source`, fail-loud:** required; must match
   `^llm-synth:[^:]+:proposition-synthesize-v1$`. Held for the Pass-2 stamp.
2. **Parse each candidate, fail-loud:** unknown keys; non-canonical enum values;
   `proposition` not in the in-scope set; missing `annotation`, or an `annotation` that is
   not one of that proposition's supporting-statement refs from the scaffold; `override`
   entries outside the closed field set, naming a field not present in the patch, or naming
   a field that is currently unset; `override` naming `reasoning_source`.
3. **predicate→operands contract:** if the patch proposes `predicate`, an **effective**
   `subject` and `object` must exist — either already on the proposition or proposed in
   the same patch. Otherwise hard error.
4. **polarity→predicate contract:** a patch that writes `polarity` (any value) without an
   **effective** `predicate` is a hard error. Polarity is relation-scoped; the model would
   permit a bare polarity, but a polarity-only proposition is semantically incoherent, so
   synthesis forbids it. (`not_applicable` for a sign-less predicate is *written by*
   canonicalization, never *proposed* bare.)
5. **Interlocks:** construct the *would-be* updated `PropositionEntity` from the current
   frontmatter plus the **fields this patch will actually write** (computed by applying the
   Pass-2 fill-only-unset + override + sign-less-canonicalization rules, so Pass 1 validates
   exactly the state Pass 2 persists — never a value Pass 2 would block), and let the model's
   own `_validate_relational_fields` run. A sign-meaningful predicate with missing/`not_applicable`
   polarity is a hard error (the agent must supply a signed polarity — sign cannot be
   guessed). Enum membership is already guaranteed by step 2. Operand presence (step 3) is
   evaluated against this same effective state.

Any Pass-1 failure aborts with a non-zero `ClickException` and writes nothing.

**Pass 2 — apply (writes), per proposition:**
1. **Fill-only-unset:** write a field only when it is currently None/absent. A field that
   is already set and whose proposed value *differs*, with no matching `override`, is a
   **benign skip-and-count** (`synthesize-existing-value-blocks`) — reported, not an
   error. An `override`-authorised field replaces the existing value.
2. **Sign-less polarity canonicalization:** when the effective predicate is sign-less and
   polarity is omitted/unset, write `polarity: not_applicable` (the validate-clean form;
   §2). Sign-meaningful predicates are never canonicalized — their polarity is
   agent-supplied or a Pass-1 hard error.
3. **Provenance stamp:** set `reasoning_source` to the **validated top-level `source`**
   string (Pass 1 step 1) **only when ≥1 synthesis-owned field is actually written** for
   that proposition. A proposition whose every proposed field was already filled (a pure
   no-op) is left **completely untouched** — no `reasoning_source`, no `updated` bump, no
   rewrite. `reasoning_source` is itself a synthesis-owned write, so stamping it on an
   otherwise-changed proposition does not by itself make a no-op proposition "changed".
4. **Persist preserving the existing body.** A minted proposition may carry curated prose
   (`## Claim`, `## Evidence Summary`, `## Caveats`, hand-authored `## Measurement Model`,
   etc.). Synthesis writes **only frontmatter fields** and must never rebuild the body. The
   write is: `_parse_markdown_file(dest)` → `(frontmatter, body)`; reconstruct the typed
   `PropositionEntity` from the current frontmatter with the synthesis-owned fields updated;
   call `write_entity_file(prop, project_root=…, body=body, as_of=…)` passing the **original
   `body` verbatim**. (This mirrors 4a's LINK path, which uses `append_entity_source_ref` to
   "preserve the possibly hand-authored prose body" — promote.py:386.) `created` is preserved
   and `updated` advances only on a real change.

**Failure boundary (not transactional).** "Validate-before-write" guarantees that no
*semantic*-contract failure ever writes a partial corpus. It does **not** make the
multi-file Pass 2 a single transaction: each proposition is written with
`_atomic_replace_text` (per-file atomic — no torn file), but an OS/IO error partway
through Pass 2 can leave the earlier propositions written and the rest not. No rollback is
specified or needed, because fill-only-unset makes re-apply idempotent: re-running the
same input writes only the propositions that did not get through, and the already-written
ones are clean no-ops. The CLI reports per-proposition write counts so a partial run is
visible.

## 8. Idempotency

Re-running `--apply` with the same curator-reviewed input after a full apply is a clean
no-op: every proposed field is now set, no `override` is present, nothing is written, and
`reasoning_source`/`updated` are unchanged. This mirrors `promote`'s order-free idempotency
and means a corrected re-run (after editing one bad patch) only writes the propositions
that genuinely changed.

## 9. Model change

`PropositionEntity` gains one optional field: **`reasoning_source: str | None = None`**
(added last, after `identification_strength`). It round-trips through frontmatter
automatically via `model_dump`/`_parse_markdown_file` (no template or io change needed,
no annotation-model change, no new graph edge — the evidentiary paper/annotation
provenance is already in `source_refs` from 4a). It answers the operational question
"is this reasoning stale under the current synthesizer prompt/model/vocab?"; a future
`...-v2` bump makes stale propositions queryable. Per-field provenance is **out of scope**
— curator review + git history already record who changed what.

The `validate/checks/propositions.py` checks need no change: `reasoning_source` is a free
string they ignore, and the interlock/enum checks already cover the fields 4c writes.

## 10. Error handling (fail-loud, mirroring promote)

- `SynthesisReadError` — malformed candidates file / unreadable proposition / bad
  top-level `source` shape / `annotation` not a supporting-statement ref of its proposition.
- `SynthesisApplyError` — interlock violation, predicate-without-operands,
  polarity-without-predicate, write-boundary refusal.
- `SynthesisOverrideError` — malformed/illegal `override` (unknown field, field not in
  patch, field currently unset, or `reasoning_source`).
- All surface as non-zero `ClickException`.
- **Benign skip-and-count reasons** (reported, never abort): `synthesize-existing-value-blocks`
  (set field, different value, no override), `synthesize-nothing-to-fill` (all proposed
  fields already match current), `synthesize-relation-hint-unresolved` (scaffold-stage
  hint omission).

## 11. Files

- `science/model/src/science_model/propositions.py` — add `reasoning_source` field.
- `science/src/science_tool/annotation/synthesize.py` — **new**: scaffold builder, candidate
  parse, two-pass validate/apply, error classes.
- `science/src/science_tool/annotation/cli.py` — `synthesize_cmd` on the `annotate` group.
- `agents/proposition-synthesize.md` — **new** agent prompt.
- `commands/synthesize-propositions.md` — **new** orchestrator command.
- `docs/conventions/annotation-tokens.md` — synthesize source string + candidate vocab.
- `science/tests/test_proposition_synthesize.py` (+ a CLI integration test) — **new**.

## 12. Testing

- **Unit** (`synthesize.py`): scaffold grouping/scope; relation-hint co-location +
  unresolved omission; top-level `source` shape validation; `annotation`-membership
  validation; candidate parse fail-loud (keys/enums/scope/override); the predicate→operands
  contract (already-present vs in-patch operands); the polarity→predicate contract
  (bare-polarity rejected); interlock validation via the real model validator
  (sign-meaningful-missing-polarity hard error; sign-less + omitted polarity canonicalized
  to `not_applicable`); fill-only-unset + existing-value block + override replacement;
  **body preservation** (curated prose survives a frontmatter-only write); provenance stamp
  only on real write (and the no-op-leaves-file-untouched case); validate-before-write
  (one bad candidate ⇒ no file written); idempotent re-apply.
- **Integration** (CLI): persist a `.source.md` + statement annotation, promote it (4a),
  run `synthesize` read-only → edit the candidate → `--apply` → assert proposition
  frontmatter (`subject`/`object`/`predicate`/`polarity`/`claim_layer`/`reasoning_source`),
  assert the interlocks hold, run `science validate` clean, and assert a second `--apply`
  is a byte-level no-op.

## 13. Out of scope (later phases)

- **4d** — cross-paper evidence aggregation / belief over synthesised propositions;
  reconciling factorizations proposed from different papers for the same proposition.
- Embedding/paraphrase dedup of propositions; figurative promotion; promoting
  `identification_strength` (left to the existing template default / future work).

# S2 — Lineage capability as a declared per-kind fact

Part of the **system-cohesion** program (`meta/doc/plans/2026-07-25-multi-surface-fact-inventory.md`,
`meta/doc/plans/2026-07-25-ideal-core-target.md`). Follows S7a (`d9e79f91`) and S1a (`649e9b06`).

Baseline for every measurement in this document: `649e9b06`.

## Goal

Declare, once per kind, whether entities of that kind can be superseded — and make the status
vocabulary, the relation endpoint list, and the auto-stamping policy all derive from that one
declaration instead of inferring it from each other.

## The problem, measured

`sci:supersedes` is answered today by three surfaces that were never compared:

| Surface | Answer | Mechanism |
|---|---|---|
| Status vocabulary | 18 kinds | `EntityKind.statuses ∋ "superseded"` |
| Relation admissibility | 9 kinds | `allowed_kind_pairs` on `supersedes` |
| Auto-stamping policy | 18 kinds | `supported_kinds`, built from `_STATUS_VALUES` (`consolidation.py:648`) |

Of 50 core entity kinds, 18 declare a `superseded` status and 9 are admissible `sci:supersedes`
endpoints. The subject and object endpoint sets are identical; `allowed_kind_pairs` holds 39 pairs
(9 self-pairs plus 30 cross-kind pairs, of which
`discussion`/`finding`/`interpretation`/`report`/`story`/`validation-report` form a fully connected
clique, while `hypothesis`, `spec` and `workflow-run` are self-only).

That yields two gaps in opposite directions:

- **Forward gap — 12 kinds** declare `superseded` but are forbidden as endpoints, so authoring the
  canonical edge raises `ValueError` in `materialize`: `decision`, `inquiry`, `mechanism`, `method`,
  `observation`, `plan`, `pre-registration`, `proposition`, `synthesis`, `theme`, `topic`,
  `workflow-step`. This is already guarded — `model/tests/test_supersedable_gate.py` derives it and
  ratchets it with a **subset** assertion against a frozen `_KNOWN_HALF_WIRED` allowlist.
- **Reverse gap — 3 kinds** are admissible endpoints but declare no `superseded` status: `story`,
  `validation-report`, `workflow-run`. Nothing guards this. The edge materializes and the graph
  records the lineage, but `mark_superseded` skips the object because it has no such status to
  write, so **the entity file never learns it was superseded**. `consolidation.py:105-111`
  documents the skip rather than resolving it.

Their status axes are not lifecycle vocabularies at all, which is why "just add the status" is not
the answer on its own:

| kind | `statuses` | what the axis means |
|---|---|---|
| `story` | draft / developing / mature | maturity |
| `workflow-run` | running / complete / failed | execution outcome |
| `validation-report` | *(none declared — open set)* | — |

**Both gaps are symptoms of one missing fact.** Nothing declares "can this kind be superseded."
The tool infers it from `status ∋ superseded`, and that proxy fails silently for exactly the kinds
whose status axis means something else.

### What is already correct

The ideal-core-target names "the validator's legit-reader set and `mark_superseded`'s stamping
policy" as ownership violations. Re-measured, **both are already clean** and this design does not
touch them as such:

- `_STATUS_VALUES` (`entities.py:200`) is `DECLARED_STATUSES`, built in `kind_descriptors.py` from
  the shipped profiles.
- `validate/checks/status_vocabulary.py` states outright that there is deliberately no table in it.
- `mark_superseded`'s `supported_kinds` is derived from that same map.

No second per-kind table exists. The real defect is narrower and different: one fact is being
carried by another fact's declaration.

## The declaration

`EntityKind` gains one field:

```python
supersedable: bool = False
```

It answers exactly one question: **can an entity of this kind be replaced as canonical by a newer
one?** It is declared explicitly on all 50 core kinds and all 3 local-profile kinds — 53 boring
declarations, not a derivation. Per the program's ranking, a fact is *stated* explicitly and
*derived* only for consumers.

### Why it carries a default

Projects may author their own entity kinds in a local profile manifest, validated through
`ProfileManifest.model_validate` (`entity_kinds.py:125`). A required field would reject every
existing project manifest. So the field defaults to `False` — the inert value — and a test asserts
`"supersedable" in ek.model_fields_set` for every kind in the **shipped** profiles. Undeclared in
our own code fails loudly; undeclared in a user manifest means "not supersedable," which is both
safe and true.

### The three derived surfaces

| Surface | Today | After |
|---|---|---|
| Status vocabulary | `statuses ∋ "superseded"` *is* the de-facto declaration | gated: `"superseded" ∈ statuses` ⟺ `supersedable` |
| Relation endpoints | hand-listed `allowed_kind_pairs` | gated: every `target_kind` is supersedable, and every supersedable kind is some pair's target |
| Auto-stamping policy | `supported_kinds` built from `_STATUS_VALUES` (`consolidation.py:648`) | `supported_kinds` built from `DECLARED_SUPERSEDABLE` |

`DECLARED_SUPERSEDABLE` is built in `kind_descriptors.py` from `KIND_DESCRIPTORS`, mirroring
`DECLARED_STATUSES` exactly. That shape is load-bearing, not cosmetic: `KIND_DESCRIPTORS` covers the
shipped profiles only, so a kind declared in a project manifest is **absent** from the map and
resolves to `False`. This preserves the existing protection that a project-local kind must never be
auto-stamped, because the write boundary's `_validate_status` indexes `_STATUS_VALUES[kind]` and
would raise `KeyError`. Deriving from a map built over the same population keeps that guarantee
without reintroducing a join.

**The stamping policy is `supported_kinds`, not `_supports_superseded`.** This matters, and an
earlier draft of this design got it wrong. `_supports_superseded` (`consolidation.py:101`) has **no
production callers** — it survives only in comments and two test references. The live policy is
serialized at `consolidation.py:648` directly from `_STATUS_VALUES`, frozen onto the graph as
`SupersedesGraph.supported_kinds` (I4: the policy travels *with* the graph), and consumed by
`_disposition_report` at `consolidation.py:713`. Repointing the dead helper would leave the
declaration owning nothing and make its mutation proof exercise dead code — the precise failure S1a
shipped three times. The change is therefore at line 648, and `_supports_superseded` is **deleted**
rather than updated, so no decoy remains for a future reader to mistake for the policy.

Deleting it touches two tests that reference it. `test_decision_material.py:311` monkeypatches it as
a negative control proving `_disposition_report` reads the authenticated `graph.supported_kinds`
rather than a live module value; that intent is preserved by re-pointing the monkeypatch at
`DECLARED_SUPERSEDABLE`. `test_consolidation_mark_superseded.py` mentions it only in prose.

**The endpoint list stays hand-authored.** Supersedability is *necessary* for the object endpoint,
not *sufficient* for a pair: the cross-kind pairs encode real restriction (`hypothesis` is
self-only) that a generated Cartesian product would destroy. Only the **object** side is gated — a
subject is the replacement, and a non-supersedable kind replacing a supersedable one is legitimate.

### The relation descriptor has three more surfaces

`allowed_kind_pairs` is the admission rule, but `RelationKind` also carries `source_kinds`,
`target_kinds`, and a prose `description` — and all three currently enumerate `workflow-run` and
omit the ten additions (`core.py:744-757`). The flat lists are the fallback admission rule when a
relation declares no pairs, so they cannot simply be deleted; they must be *reconciled*. Editing
only the pairs would leave three surfaces contradicting the one that decides — the same
multi-surface defect this program exists to close, reintroduced by its own fix.

All four are updated together, and a new guard asserts **`set(source_kinds)` equals the pairs'
source union and `set(target_kinds)` equals the target union, for every relation declaring pairs**.
Measured at baseline: 2 relations declare pairs (`supersedes`, `amends`) and both already satisfy
this, so the guard is free to add today and blocks exactly the drift described above. The stale
comment block at `core.py:735-742`, which describes the twelve half-wired kinds as this arc's frozen
debt, is rewritten — S2 dissolves that debt rather than carrying it.

## The rulings

Ruling principle, chosen deliberately: **a kind is supersedable iff its entities make a standing
claim that a newer entity can replace as canonical.** Event and observation records are immutable
history — you re-run or re-measure; you do not replace what happened.

The 50 core kinds partition as 6 already wired, 12 in the forward gap, 3 in the reverse gap, and 29
inert. The rulings below produce **18 `supersedable: True` and 32 `False`**, and both derived
surfaces land on exactly that 18-kind set: the post-change `superseded`-declaring set and the
post-change endpoint-target set are each equal to it.

### Gain the endpoint (10)

`decision`, `inquiry`, `mechanism`, `method`, `plan`, `proposition`, `synthesis`, `theme`, `topic`,
`workflow-step` — each is a standing definition or claim that a newer entity replaces as canonical.
`topic` is the clearest: it is the legacy note kind explicitly being replaced by typed entities, so
supersession is its use case. `plan` and `proposition` each already have a live entity carrying
`status: superseded` with no edge able to back it.

**Each is added as a SELF-PAIR** (`decision → decision`, and so on), matching how `hypothesis` and
`spec` are already wired. They must **not** be added to `_CONCLUSION_KINDS` (`core.py:12-19`): that
list has six members and is shared with the `amends` relation, so widening it would silently give
all ten cross-kind amendment admissibility that nothing in this design ruled on.

### Lose the status (2)

| kind | ruling |
|---|---|
| `observation` | "Concrete empirical fact anchored to specific data." A later measurement is a *new* observation; the old one stays true of the data it was anchored to. An empirical record, not a standing claim. |
| `pre-registration` | A commitment timestamped *before* analysis. Retroactively replacing it defeats the point of pre-registering. Revisions already have a home: `sci:amends`, defined as revising "without replacing." |

### Gain the status (2)

- `story` — a narrative arc synthesizing interpretations; a newer arc replaces it.
- `validation-report` — a re-validation replaces the prior report as canonical. It declares no
  vocabulary today, so this also gives it one, mirroring `report`:
  `active` / `archived` / `complete` / `draft` / `retired` / `superseded`.

### Lose the endpoint (1)

- `workflow-run` — "Concrete execution of a workflow producing durable outputs." A re-run produces a
  new record; it does not replace an execution that genuinely happened.

  This ruling has a second half. `workflow-run` also carries a **top-level `supersedes:` field**,
  recommended by its template and specially exempted from the non-materializing-field check. Left
  alone, the repository would answer this question both ways. That field is retired — see
  "`workflow-run`'s top-level `supersedes:` is retired" under Files.

### Already wired (6)

`discussion`, `finding`, `hypothesis`, `interpretation`, `report`, `spec` declare `superseded` *and*
are admissible endpoints today. They are declared `supersedable: True`; nothing else about them
changes.

### The remaining 29 kinds

Declared `supersedable: False`, which records their current behavior: none can author the edge or
reach the state today.

**This is not a principle ruling for all of them.** Applying the principle honestly, six are real
candidates deliberately left unanswered rather than rejected: `question`, `dataset`, `workflow`,
`prose-source`, `structural-chain`, `assumption`. The ideal-core-target names the 12 half-wired plus
3 unstampable kinds as S2's acceptance corpus, and this design keeps to it. Enabling any of the six
later is a one-line declaration change plus its endpoint pairs — the gate will demand both.

## Migration

**Zero data changes.** Measured across all seven local Science projects
(`~/d/3d-attention-bias`, `~/d/cats`, `~/d/natural-systems`, `~/d/protein-landscape`,
`~/d/science-commons`, `~/d/seq-feats`, and `meta/`):

- 7 entities carry `status: superseded` — 4 `interpretation`, 1 `plan`, 1 `discussion`, 1 archived
  `proposition`. None is a kind this design removes the status from.
- `story`: **0** entities. `validation-report`: **0** entities. Both additions are free.
- `observation`: 11, `pre-registration`: 41, `workflow-run`: 4 entities exist, and **none** carries
  `status: superseded`. Both removals are free.
- The only `sci:supersedes` occurrences in authored entity files are template boilerplate in
  `interpretation` scaffolds, not authored edges.
- None of the 4 `workflow-run` entities carries a top-level `supersedes:` key, so retiring that
  field is also a zero-migration change.

Downstream consumers pin the toolkit revision in `uv.lock`, so no compatibility layer is written.

## The gate

`model/tests/test_supersedable_gate.py` is rewritten. `_KNOWN_HALF_WIRED` is **deleted, not
shrunk**: with all 15 kinds ruled there is no debt left to ratchet, so the assertions become exact
equality in both directions, and a stale exemption fails as loudly as a new gap.

Five properties, each executable:

1. **Every shipped kind declares the fact.** `"supersedable" in ek.model_fields_set` for every kind
   in `CORE_PROFILE` and `LOCAL_PROFILE`. This is what makes kind 51 impossible to add silently.
2. **Status vocabulary agrees, exactly.** `{k.name for k in kinds if "superseded" in (k.statuses or ())}`
   equals `{k.name for k in kinds if k.supersedable}` — both directions, one failure message naming
   each side.
3. **Endpoints agree, exactly.** The set of `target_kind` values across `allowed_kind_pairs` equals
   the supersedable set. Asked through `relation_allows_kinds`, the authoritative admission helper —
   not `source_kinds & target_kinds`, which is not the admission rule when `allowed_kind_pairs` is
   present.
4. **The flat projections agree with the pairs.** For every relation declaring
   `allowed_kind_pairs`, `set(source_kinds)` equals the pairs' source union and `set(target_kinds)`
   equals the target union. Universal over the profile, not scoped to `supersedes`.
5. **Stamping agrees.** The policy actually carried on the graph matches the declaration:
   `build_decision_material(project_root).supported_kinds` equals the sorted supersedable set, and a
   member whose kind is **omitted from its material's frozen policy** is skipped. Note the fixture is
   a normally supersedable kind held out of the policy — *not* a "non-supersedable kind", which after
   S2 cannot be an admitted member at all. Asserted against the live policy path, never against the
   deleted helper.

### Anti-tautology

Property 2 would be vacuous if the status vocabulary were generated from `supersedable`, and
property 3 would be vacuous if the endpoint pairs were. Neither is generated: `statuses` and
`allowed_kind_pairs` stay hand-authored declarations, and the gate compares two independently
authored surfaces. A test that derived one side from the other would be the identity function —
the failure mode S7a hit and S1a re-derived.

Property 5 is guarded against a different vacuity. `supported_kinds` will be *built* from
`DECLARED_SUPERSEDABLE`, so comparing it back to `DECLARED_SUPERSEDABLE` is the identity function.
The test compares it to the **profile declaration** (`EntityKind.supersedable` read off
`CORE_PROFILE`), reached independently of `kind_descriptors`, and adds the behavioural half — that a
non-supersedable member is actually skipped by `_disposition_report` — so the property is proven by
what the code does, not by what two expressions spell.

### Mutation proofs

Each property must be shown able to fail, by a temporary local mutation run manually and reverted —
not committed:

| Property | Mutation | Expected |
|---|---|---|
| 1 | delete `supersedable=` from one core kind's `EntityKind(...)` | fails, naming that kind |
| 2 | set `topic.supersedable = False` while leaving `superseded` in its statuses | fails, naming `topic` on the vocabulary side |
| 3 | remove the `decision → decision` self-pair while leaving `decision.supersedable = True` | fails, naming `decision` on the endpoint side (and trips 4, since `source_kinds` still lists it) |
| 4 | append `"workflow-run"` to `supersedes.source_kinds` only | fails, naming the source-union mismatch |
| 5 | drop `topic` from the set built at `consolidation.py:648` | fails twice: the material no longer equals the declaration, and a `topic` member stops being stamped |

The public `mark_superseded` return documentation (`consolidation.py:799`) defines `skipped_kinds`
as "members whose kind does not declare `superseded`" and `to_mark` as excluding "members whose kind
can't carry the status". Both describe the eliminated semantics. They are rewritten to describe
**policy disagreement** — a member whose kind is absent from the graph's frozen `supported_kinds` —
along with the affected test names and comments, which currently read `..._kind_lacks_superseded_vocab...`.

Mutation 5 is deliberately *not* "revert line 648 to `_STATUS_VALUES`". Once the rulings land,
property 2 forces the two sources equal, so that mutation produces an identical set and proves
nothing — an inert probe of exactly the kind S1a shipped. The mutation must remove a kind the
assertion reads.

These are proofs of a *live* gate, distinct from the suite passing. S1a's plan shipped three
mutation proofs that could not run as written; each mutation above was chosen to touch a value the
assertion actually reads.

## Files

- `science/model/src/science_model/profiles/schema.py` — add `supersedable` to `EntityKind`.
- `science/model/src/science_model/profiles/core.py` — 50 declarations; add `superseded` to
  `story` and `validation-report` (the latter also gains a full vocabulary); remove it from
  `observation` and `pre-registration`; add 10 self-pairs to the `supersedes`
  `allowed_kind_pairs` and drop `workflow-run`; bring `source_kinds`, `target_kinds`, and the
  `description` into line with the pairs; rewrite the frozen-debt comment at lines 735-742.
- `science/model/src/science_model/profiles/local.py` — 3 declarations.
- `science/src/science_tool/kind_descriptors.py` — add `DECLARED_SUPERSEDABLE`.
- `science/src/science_tool/consolidation.py` — build `supported_kinds` (line 648) from
  `DECLARED_SUPERSEDABLE`; **delete** `_supports_superseded` and the comments describing it;
  rewrite the `mark_superseded` return documentation at line 799 (`to_mark`, `skipped_kinds`) to
  describe policy disagreement rather than status capability.
- `science/model/tests/test_supersedable_gate.py` — rewritten; `_KNOWN_HALF_WIRED` deleted.
- `science/tests/test_kind_map_equivalence.py` — re-freeze `FROZEN_STATUS_VALUES` (see below).
- `science/model/tests/test_profile_manifests.py` — `line 99` asserts
  `relation_allows_kinds(supersedes, "workflow-run", "workflow-run")`, which this design makes
  false; revise it to assert the *absence* of that pair, and extend the pair coverage to the ten
  new self-pairs.
- `science/tests/test_decision_material.py` — **two** changes, not one. Line 311's
  `_supports_superseded` monkeypatch is re-pointed at `DECLARED_SUPERSEDABLE`, preserving the
  negative control. Line 287's digest test injects a fake auto-apply-eligible kind by patching
  `_STATUS_VALUES` and asserts the digest moves; once `supported_kinds` derives from
  `DECLARED_SUPERSEDABLE` that patch is inert and the assertion fails. It must inject into
  `DECLARED_SUPERSEDABLE` instead, with its comment updated to name the new authority.

### Three tests exercise a state S2 eliminates

Removing `workflow-run` from the endpoint pairs invalidates three executable tests that use it
precisely *because* it is the admitted-but-unstampable kind:

| test | what it asserts | disposition |
|---|---|---|
| `test_consolidation_candidates.py:62` `test_lineage_reports_kind_lacking_superseded_vocab` | the read-only detector still reports a lineage whose kind cannot be stamped | **delete** — see below |
| `test_consolidation_mark_superseded.py:298` `test_member_whose_kind_lacks_superseded_vocab_is_skipped_not_crashed` | such a member lands in `skipped_kinds` rather than crashing | rebuild through the **material** path (see below) |
| `test_graph_materialize.py:1109` `test_materialize_graph_preserves_workflow_run_supersedes` | the edge materializes | invert into a **rejection** test, or move to a retained endpoint kind |

#### `skipped_kinds` after S2: retained, and reachable from exactly one direction

**After S2 no authored project input can reach the skip path — including a project-local kind.**
An earlier draft of this design claimed a project-local kind could still reach it. That is **false**:
`_profile_relation_for_predicate` (`materialize.py:1907`) resolves an authored `sci:supersedes`
against `CORE_PROFILE.relation_kinds` and nothing else, so admission is decided by the core pairs
whatever a project profile declares. A project-local kind is never admitted, so it never becomes a
member to skip. Combined with property 3, every admitted object kind is one of the 18 supersedable
kinds — which is exactly `supported_kinds`.

One direction remains: **decision material whose `supported_kinds` disagrees with its admitted
edges** — stale or hand-built material. That is a real state by construction, since I4 freezes the
policy onto the graph precisely so preview/apply drift is detectable, and `_disposition_report`
reads the authenticated `graph.supported_kinds` rather than a live module value.

**Ruling: the skip behaviour is retained**, because deleting it would make `_disposition_report`
assume its graph's policy always covers every member — the assumption that stale material violates.

**The regression must go through the material path, not around it.** Hand-building a
`SupersedesGraph` whose `supported_kinds` omits a member's kind proves only that
`_disposition_report` branches on that field. It does not prove the reachable case, which requires
inconsistent material to *survive* `build_supersedes_graph_from_material` in the first place. So the
test constructs an inconsistent `SupersessionDecisionMaterial` — admitted edges whose object kind is
absent from its `supported_kinds` — rebuilds through `build_supersedes_graph_from_material`, and
asserts the skip through **`derive_supersede_plan`** (`supersede_plan.py:145`), which is the actual
consumer: it builds the graph from material and calls `_disposition_report` with no filesystem read.
That covers the boundary end to end — reachable from material, unreachable from authored input.

**The consolidation-candidates test is deleted, not rebuilt.** It cannot cover this boundary:
`detect_consolidation_candidates` (`consolidation_candidates.py:292`) always loads authored input
and builds a live graph — it never consumes saved material — and `_lineage_section` reads only
`graph.linear` / `graph.non_linear`, never `supported_kinds`. So it never exercised the skip path
even today; what it actually asserted is that the read-only detector reports a chain regardless of
stampability. After S2 no shipped kind can be admitted-but-unstampable, so that assertion is no
longer distinguishable from the ordinary lineage test sitting directly above it, and retasking it
would mean keeping a duplicate under a name that describes a state the profile forbids.

### `workflow-run`'s top-level `supersedes:` is retired

Ruling `workflow-run` non-supersedable would otherwise leave the repository answering "can workflow
runs supersede?" **both ways**: `sci:supersedes` would reject the edge, while
`templates/workflow-run.md:9` still tells authors to write
`supersedes: []  # ["workflow-run:<prior-slug>"] when re-run with changed params`, and
`materialization.py:50` exempts that key from the check that errors on every other
non-materializing field.

Measured, the field sustains nothing:

- **No reader.** `qa_audit/runs.py:47` loads it into `RunRecord.supersedes`, and **nothing consumes
  that attribute** — it is the only occurrence in the package. The exemption's stated
  justification, "read by `qa_audit/runs.py:47` for the QA-audit chain," is false in its operative
  half.
- **No chain.** `chain_depth` is `sum(1 for r in runs if r.workflow == workflow)` — it counts runs
  per workflow and never follows a `supersedes` link. Both its own docstring ("its supersession
  chain") and `verdicts.py:33` ("a supersedes re-run") describe behaviour the function does not
  have.
- **No authors.** None of the 4 `workflow-run` entities across all seven projects carries the key.

So it is precisely the dead non-materializing field `fb-2026-07-11-017` exists to flag, kept alive
by a one-entry exemption whose reason does not hold. The program's own rule — compat projections get
deleted, not documented — applies directly. It is removed, not re-labelled:

- `templates/workflow-run.md` — **two** places, not one: the `supersedes:` frontmatter line (line 9)
  and the `- **Supersedes:** \`workflow-run:<slug>\` (if applicable)` bullet in the body's Entity
  Cross-References section (line 54). Leaving the prose would keep recommending a field the
  validator now rejects.
- `science/src/science_tool/qa_audit/runs.py` — drop `supersedes` from `RunRecord` and from the
  loader; correct `chain_depth`'s docstring to say it counts runs recorded for the workflow.
- `science/src/science_tool/qa_audit/verdicts.py` — correct the `iteration_verdict` docstring,
  which currently calls `chain_depth >= 2` "a supersedes re-run."
- `science/src/science_tool/validate/checks/materialization.py` — remove the
  `("workflow-run", "supersedes")` entry. It is the **only** member of `_LEGIT_TOP_LEVEL`, so the
  set and the filtering it drives are removed with it; a future key with a genuine reader can
  reintroduce the mechanism together with the reader that justifies it. The docstring paragraph at
  lines 13-19 explaining the exemption goes too.
- `science/tests/test_qa_audit_runs.py` — remove the `supersedes` fixture argument, and rename
  `test_chain_depth_counts_supersession`. That test authors `supersedes:` on two of three runs and
  asserts `chain_depth == 3`, which the function returns whether or not those keys exist: it is
  tautological with respect to its own name and must be renamed to what it actually asserts.
- `science/tests/test_qa_audit_audit.py` — remove the same fixture argument.
- `science/tests/validate/test_checks_materialization.py` — **two** tests change.
  `test_supersedes_on_workflow_run_is_accepted` (line 77) asserts no result and must **invert** to
  expect a single `ERROR`, with its docstring — which cites the now-deleted `qa_audit/runs.py:47`
  reader — rewritten. `test_inadmissible_kind_is_not_told_to_author_the_relation` (line 141) picks
  `plan` as its inadmissible kind, and S2 makes `plan` an admissible `sci:supersedes` source; it
  must be **retargeted** to a kind that stays non-supersedable (`question` is the natural choice)
  or it silently stops testing the behaviour it names. The comment block at lines 135-138, which
  enumerates the twelve half-wired kinds as the reason for the kind-aware remediation, is rewritten
  — after S2 that set is empty and the remediation's population is the 32 non-supersedable kinds.

- `docs/process/pipeline-audit-and-refactor.md` — line 238 tells readers `science qa-audit` "reads
  each workflow's `workflow-run` / `sci:supersedes` chain." After S2 that relation is rejected for
  `workflow-run`, and the sentence was already wrong about the mechanism: `qa-audit` counts runs
  recorded per workflow and follows no chain. Corrected to describe what it does.

Removing the exemption means the materialization check will now ERROR on a `workflow-run` carrying
`supersedes:`. That is the intended behaviour and affects no existing entity.

- `commands/next-steps.md` — **two** lines instruct agents to look for workflow-run states S2 makes
  unreachable: line 76 (`#### Workflow Runs`) reports "superseded runs, runs with status `draft`",
  and line 210 (**Unreflected failures**) names "a discarded / superseded / `draft` workflow run",
  back-referencing line 76. Only `superseded` is S2's doing. `discarded` and `draft` were *already*
  unreachable: `workflow-run` declares the closed vocabulary `["running", "complete", "failed"]`
  (`core.py:568-578`). All three are corrected against that vocabulary, because leaving a
  known-false state name inside a sentence being rewritten is not defensible. `codex-skills/
  science-next-steps/SKILL.md` is the generated mirror and is **regenerated**, never hand-edited —
  `test_committed_codex_skills_match_fresh_generation` fails otherwise.

**The live-surface sweep found three files, and its first pass found two.** `commands/next-steps.md`
was missed and surfaced in review — a reminder that this sweep is exactly the kind of enumeration
whose holes are invisible from inside it. Every file under `docs/`, `skills/`, `commands/`,
`templates/`, `references/` and `agents/` mentioning both `workflow-run` and supersession was
checked; the three above are the only *live guidance*. The remaining matches are about other kinds
(`interpretation`, `dataset`, `spec`) or are dated design and plan documents — including
`docs/plans/2026-07-15-non-materializing-fields-plan.md:20`, which records the exemption being
introduced, and `docs/plans/2026-07-12-d4-status-vocabulary-audit.md:47`, which references
`_supports_superseded`. Those are historical records of completed work and are **left untouched**;
rewriting them would falsify the record of why the exemption existed.

### The frozen status oracle must be re-frozen, deliberately

`test_kind_map_equivalence.py` holds `FROZEN_STATUS_VALUES` — a literal snapshot of every kind's
vocabulary — and `test_status_values_equal_prior_literal` (line 181) asserts `_STATUS_VALUES` equals
it **exactly**. Four of this design's rulings necessarily break it:

| kind | edit to the frozen literal |
|---|---|
| `observation` | remove `"superseded"` |
| `pre-registration` | remove `"superseded"` |
| `story` | add `"superseded"` |
| `validation-report` | add a new entry — it is absent today, having declared no vocabulary |

**A second oracle in the same file also breaks.** Giving `validation-report` a `default_status`
(mirroring `report`, so a closed vocabulary is not left without a default) adds an entry to
`FROZEN_DEFAULT_STATUS`, which `test_default_status_equals_prior_literal` asserts by exact equality.
This was found by running the change, not by reading — neither the design review nor the file list
predicted it.

This is an **intentional re-freeze against a written ruling**, and it is called out here precisely
so it cannot happen quietly. That oracle exists to catch *unintended* vocabulary drift; editing it
to match a change nobody ruled on would be tuning the instrument to silence the check. Every edit
above traces to a ruling in this document, and the implementation plan must require the ruling be
cited in the commit that touches the literal.

## Out of scope

- **F4 — what `status` means per kind.** `story` will carry a maturity axis plus exactly one
  lifecycle terminal, and `workflow-run` keeps an execution-outcome axis. The broader question of
  the five state axes across 50 kinds is not S2's.
- **F3 — the lineage taxonomy.** Whether `status: superseded` and the derived `superseded_by`
  inverse are two spellings of one fact is S3's question. S2 rules *capability*, not spelling, and
  removes nothing from the **canonical** lineage vocabulary — `sci:supersedes`, `sci:amends`,
  `superseded_by`, `resynthesized_into`, `deprecated_ids` and `consolidated_into` are all untouched.
  It does delete one non-canonical surface: `workflow-run`'s top-level `supersedes:` key, which
  materializes no triple and which the inventory already classed as the single clearly disposable
  member of that list.
- **The six candidate kinds** listed above.
- **S1b** — widening value-reconciliation batteries; unrelated and independently sequenced.

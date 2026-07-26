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
| Auto-stamping policy | 18 kinds | `_supports_superseded` (`consolidation.py:111`) |

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
| Auto-stamping | `_SUPERSEDED in _STATUS_VALUES.get(kind, …)` | `DECLARED_SUPERSEDABLE.get(kind, False)` |

`DECLARED_SUPERSEDABLE` is built in `kind_descriptors.py` from `KIND_DESCRIPTORS`, mirroring
`DECLARED_STATUSES` exactly. That shape is load-bearing, not cosmetic: `KIND_DESCRIPTORS` covers the
shipped profiles only, so a kind declared in a project manifest is **absent** from the map and
resolves to `False`. This preserves the existing protection that `_supports_superseded`'s docstring
describes — a project-local kind must never be auto-stamped, because the write boundary's
`_validate_status` indexes `_STATUS_VALUES[kind]` and would raise `KeyError`. Deriving from a map
built over the same population keeps that guarantee without reintroducing a join.

**The endpoint list stays hand-authored.** Supersedability is *necessary* for the object endpoint,
not *sufficient* for a pair: the cross-kind pairs encode real restriction (`hypothesis` is
self-only) that a generated Cartesian product would destroy. Only the **object** side is gated — a
subject is the replacement, and a non-supersedable kind replacing a supersedable one is legitimate.

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

Downstream consumers pin the toolkit revision in `uv.lock`, so no compatibility layer is written.

## The gate

`model/tests/test_supersedable_gate.py` is rewritten. `_KNOWN_HALF_WIRED` is **deleted, not
shrunk**: with all 15 kinds ruled there is no debt left to ratchet, so the assertions become exact
equality in both directions, and a stale exemption fails as loudly as a new gap.

Four properties, each executable:

1. **Every shipped kind declares the fact.** `"supersedable" in ek.model_fields_set` for every kind
   in `CORE_PROFILE` and `LOCAL_PROFILE`. This is what makes kind 51 impossible to add silently.
2. **Status vocabulary agrees, exactly.** `{k.name for k in kinds if "superseded" in (k.statuses or ())}`
   equals `{k.name for k in kinds if k.supersedable}` — both directions, one failure message naming
   each side.
3. **Endpoints agree, exactly.** The set of `target_kind` values across `allowed_kind_pairs` equals
   the supersedable set. Asked through `relation_allows_kinds`, the authoritative admission helper —
   not `source_kinds & target_kinds`, which is not the admission rule when `allowed_kind_pairs` is
   present.
4. **Stamping agrees.** `_supports_superseded(kind) == supersedable(kind)` for all 53 shipped kinds,
   and a project-local kind name absent from `KIND_DESCRIPTORS` returns `False`.

### Anti-tautology

Property 2 would be vacuous if the status vocabulary were generated from `supersedable`, and
property 3 would be vacuous if the endpoint pairs were. Neither is generated: `statuses` and
`allowed_kind_pairs` stay hand-authored declarations, and the gate compares two independently
authored surfaces. A test that derived one side from the other would be the identity function —
the failure mode S7a hit and S1a re-derived.

Property 4 is guarded against a different vacuity: `_supports_superseded` must be changed to read
`DECLARED_SUPERSEDABLE`, so asserting it equals `supersedable` would be trivially true if the
comparison were against the same expression. The test asserts it against the **profile declaration**
(`EntityKind.supersedable`), reached independently of `kind_descriptors`, plus the explicit
absent-kind case.

### Mutation proofs

Each property must be shown able to fail, by a temporary local mutation run manually and reverted —
not committed:

| Property | Mutation | Expected |
|---|---|---|
| 1 | delete `supersedable=` from one core kind's `EntityKind(...)` | fails, naming that kind |
| 2 | set `topic.supersedable = False` while leaving `superseded` in its statuses | fails, naming `topic` on the vocabulary side |
| 3 | remove `story` from the `supersedes` pairs while leaving `supersedable=True` | fails, naming `story` on the endpoint side |
| 4 | make `_supports_superseded` return `True` unconditionally | fails on every non-supersedable kind |

These are proofs of a *live* gate, distinct from the suite passing. S1a's plan shipped three
mutation proofs that could not run as written; each mutation above was chosen to touch a value the
assertion actually reads.

## Files

- `science/model/src/science_model/profiles/schema.py` — add `supersedable` to `EntityKind`.
- `science/model/src/science_model/profiles/core.py` — 50 declarations; add `superseded` to
  `story` and `validation-report` (the latter also gains a full vocabulary); remove it from
  `observation` and `pre-registration`; edit the `supersedes` `allowed_kind_pairs` to add the 10
  and drop `workflow-run`.
- `science/model/src/science_model/profiles/local.py` — 3 declarations.
- `science/src/science_tool/kind_descriptors.py` — add `DECLARED_SUPERSEDABLE`.
- `science/src/science_tool/consolidation.py` — `_supports_superseded` reads it; update the
  docstring, which currently explains the `_STATUS_VALUES` membership check.
- `science/model/tests/test_supersedable_gate.py` — rewritten; `_KNOWN_HALF_WIRED` deleted.

## Out of scope

- **F4 — what `status` means per kind.** `story` will carry a maturity axis plus exactly one
  lifecycle terminal, and `workflow-run` keeps an execution-outcome axis. The broader question of
  the five state axes across 50 kinds is not S2's.
- **F3 — the lineage taxonomy.** Whether `status: superseded` and the derived `superseded_by`
  inverse are two spellings of one fact is S3's question. S2 rules *capability*, not spelling, and
  deletes nothing from the lineage vocabulary.
- **The six candidate kinds** listed above.
- **S1b** — widening value-reconciliation batteries; unrelated and independently sequenced.

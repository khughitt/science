# Paper-Annotate Phase 3a Design — Statement Extraction

> Sub-article annotation project, Phase 3 (split: **3a = statements**, 3b = metaphors/analogies).
> Builds on Phase 1 (`.source.md` anchor surface) and Phase 2 (PubTator entity + relation seeders).

**Goal:** An LLM agent extracts **proposition / question / hypothesis** statements from a
paper's `.source.md`, grounded in its already-persisted PubTator annotations, and persists
them as verified span annotations through a deterministic CLI. **Annotate-first, promote-later**:
extraction writes raw evidence spans; linking into epistemic entities is Phase 4.

**Architecture (one sentence):** the agent is the *brain* (it produces a candidate list only);
a new deterministic `science annotate extract` command is the *hands* (it owns anchoring,
section derivation, grounding verification, body validation, merge/dedup, and document-level
idempotency). This mirrors the Phase 2 seeder split.

---

## Decisions (resolved via brainstorming)

| # | Decision | Choice |
|---|----------|--------|
| 1 | Persistence path | Agent → `candidates.json` → deterministic `science annotate extract`; agent never touches the sidecar |
| 2 | Span anchoring | Exact quote + prefix/suffix (`TextQuoteSelector`); **unique-or-skip**, fail loud |
| 3 | Section facet | **CLI-derived** from the anchored offset → normalized vocab; never agent-supplied |
| 4 | Phase scope | **3a = statements only**; 3b adds metaphor/analogy as a purely additive body schema + prompt section |
| 5 | Statement body | Light-typed + opportunistic grounding (`stance` required; `subject`/`object`/`*_concept` optional); full SPO deferred to promotion |
| 6 | Packaging | Dedicated `paper-annotate` subagent + `annotate-paper` command (reuses `command-preamble.md`); not folded into `paper-researcher` |
| 7 | Re-run guard | Document-level `source_text_hash` short-circuit, implemented in 3a (agent is expensive **and** non-deterministic) |

---

## Data flow

```
/annotate-paper <paper>            (command: orchestrator workflow)
  │
  ├─ 1. precheck (read-only):
  │       science annotate extract --check --paper <p> --model <m>
  │         → {"status":"unchanged"}  → skip (do NOT dispatch the LLM)
  │         → {"status":"changed"}    → proceed   (--force overrides)
  │
  ├─ 2. dispatch paper-annotate subagent  (only if changed / forced)
  │       ├─ science annotate list <p> --status open --status ack --format json
  │       │       → existing entity-* / relation anchors (grounding set)
  │       ├─ read <p>.source.md   → text + section structure
  │       └─ write candidates.json   ← the agent's ONLY deliverable
  │
  └─ 3. science annotate extract --input candidates.json --paper <p> --model <m>
          ├─ strict-validate candidates (fail loud on malformed input)
          ├─ anchor each: locate exact bounded by prefix+suffix → offset   [unique-or-skip]
          ├─ derive + normalize section from the offset map
          ├─ verify *_concept IRIs against persisted entity-* annotations (open+ack)
          ├─ build TextualBody(json) → PlannedAnnotation → merge_planned → .anno.trig
          └─ ON SUCCESS ONLY: record new source_text_hash for this source on the ledger
```

The agent produces candidates; everything verifiable lives in tested deterministic Python.

---

## `science annotate extract` — the deterministic hands (keystone deliverable)

New subcommand on the existing `annotate` group (`annotation/cli.py`), alongside `pubtator`.

### Input (`candidates.json`)

```json
{
  "candidates": [
    {
      "type": "proposition",
      "exact": "BRCA1 loss drives genomic instability",
      "prefix": "we found that ",
      "suffix": " in these tumors.",
      "stance": "asserted",
      "subject": "BRCA1 loss",
      "object": "genomic instability",
      "subject_concept": "https://identifiers.org/ncbigene:672"
    }
  ]
}
```

- `type` ∈ `{proposition, question, hypothesis}` (required).
- `exact` (required), `prefix` / `suffix` (required, may be empty strings but the fields must be present).
- `stance` ∈ `{asserted, negated, hypothesized, open}` (required).
- `subject`, `object`, `subject_concept`, `object_concept` — optional.
- **Strict validation:** unknown top-level keys, unknown candidate fields, unknown `type`/`stance`
  values, or wrong JSON types → **fail loud** (non-zero exit, nothing written, **ledger not updated**).
  No silent coercion, no partial-batch acceptance of a structurally invalid file.

### `--check` mode (no `--input`)

Read-only precheck. Computes the current `.source.md` `text_sha256` (the existing frontmatter /
hashing path) and compares it to the last value recorded for
`llm-annot:<model>:paper-annotate-v1` on that document's per-source `AuditLedger`. Prints
`{"status":"changed"|"unchanged"}`. No writes, no side effects.

### Anchoring

For each candidate, locate `exact` bounded by `prefix`+`suffix` in `.source.md`, reusing the
existing `TextQuoteSelector` builder + slice-verify. Resolve to a unique occurrence:

- 0 surviving matches → skip + count `extract-quote-not-found`.
- >1 surviving matches → skip + count `extract-quote-ambiguous`.
- exactly 1 → build the passage-clamped selector (same machinery Phase 2 uses).

`file_idx` = the absolute character offset of the anchored span in `.source.md`; `length` = its
character length. Both feed the dedup discriminator (below).

### Section derivation

From the anchored `file_idx`, find the containing `PassageOffset` in the offset map and read its
`section` (BioC `infons.type`). Normalize to the fixed vocabulary:

`title · abstract · introduction · methods · results · discussion · conclusion · figure · table · other`

Mapping is a small explicit table over the BioC section types PubTator emits (e.g. `INTRO`→`introduction`,
`METHODS`→`methods`, `RESULTS`→`results`, `DISCUSS`→`discussion`, `CONCL`→`conclusion`, `FIG`→`figure`,
`TABLE`→`table`, `title`→`title`, `abstract`→`abstract`); anything unrecognized → `other`. The
agent never supplies section; consistency is guaranteed by construction.

### Grounding verification (status-pinned)

A candidate's `subject_concept` / `object_concept` must equal the `IriBody` IRI of a persisted
`entity-*` annotation **in that paper** whose status is **active** (`open` or `ack`); annotations
that are `dismissed` or `superseded` are excluded from the grounding set. This SAME active-set
policy is what the agent is told to pass to `annotate list` (`--status open --status ack`), so the
agent's context and the deterministic verifier see the same anchors.

- Verified IRI → keep the field.
- Unverified / unknown IRI → **drop that field, keep the statement, count `extract-unverified-concept`**.
  Optional grounding is a bonus, never a hard gate; the statement span is the primary artifact. The
  drop is reported (counted), so it is explicit, not silent.

### Persistence

- `annotation_type` = the candidate `type` (kebab `proposition` / `question` / `hypothesis`).
- `Motivation.CLASSIFYING` (`oa:classifying`).
- One `TextualBody(value=<json>, format="application/json")`. The JSON body is serialized
  deterministically: `json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False)`
  (matching the Phase 2b relation-body rule; `allow_nan=False` guarantees finite, valid JSON).
- `source = llm-annot:<model>:paper-annotate-v1`, where `<model>` is the exact extracting model
  id passed via `--model` (e.g. `claude-sonnet-4-6`). Joins `HASH_REQUIRED_SOURCE_PREFIXES`.
- **`match_text` (dedup discriminator):** `f"{type}|{file_idx}:{length}|{normalized_exact}"`.
  The dedup key is `(source, selector.exact, lifted_from, match_text)`
  (`audit.py::_annotation_tuple`) and carries **no positional component**, so two
  legitimately-repeated identical statements at different offsets would collapse on
  `(source, exact, …)` alone — the `file_idx:length` segment keeps them distinct, mirroring the
  Phase 2a/2b offset-discriminator fix. `type` keeps same-span/different-kind rows distinct.
- Build all `PlannedAnnotation`s, then a single `merge_planned(sidecar, planned, …)` →
  `serialize_sidecar` → `.anno.trig` (idempotent re-audit via `content_hash`).

### Document-level idempotency — `AuditLedger.source_text_hash` (explicit model change)

`AuditLedger` today is `(id, source, audited_hashes, modified)` (`model.py:119`) and
`content_hash` is strictly per-span `content_hash(selector.exact, source_version)`
(`hash.py:13`). The document guard is a **different concern** from the per-row audit cache, so it
gets its own field rather than overloading `audited_hashes`:

- Add `source_text_hash: str | None = None` to the `AuditLedger` dataclass.
- Add Turtle (de)serialization round-trip for it in `annotation/io.py` (a new `sci:sourceTextHash`
  predicate on the ledger node), defaulting to `None`/absent for legacy ledgers (read path tolerant
  of its absence; no migration needed because the field is additive and optional).
- `extract` (non-`--check`) records the current `.source.md` `text_sha256` into this field for the
  `llm-annot:<model>:paper-annotate-v1` ledger **only after deterministic extraction completes
  successfully**. A run that fails validation or anchoring-with-zero-writes does not advance the
  hash, so a fixed re-run is not falsely skipped.

This makes the **non-deterministic** agent idempotent at the document level — which per-annotation
`content_hash` structurally cannot do, since an LLM re-run that quotes a slightly different span
produces a genuinely new (un-deduped) row. The guard is keyed by the full versioned source
identity, so a `paper-annotate-v2` bump (or `--force`) correctly re-runs.

### Report

A structured `ExtractReport` (mirroring `SeedReport`): `written: int`,
`skipped: dict[str, int]` (by reason: `extract-quote-not-found`, `extract-quote-ambiguous`,
`extract-unverified-concept` is a *field-drop* count rather than a row-skip and is reported
separately as `grounding_dropped: int`), `source_text_hash_recorded: bool`, `note: str | None`.

### Input hardening (fail-early)

- **Bounded candidate count:** reject an input with more than `MAX_CANDIDATES` (e.g. 500) candidates
  — a single paper producing more is a prompt/agent malfunction, fail loud.
- **Bounded field length:** reject any `exact`/`prefix`/`suffix`/`subject`/`object` longer than
  `MAX_FIELD_CHARS` (e.g. 2000) — guards against a run-away quote spanning the whole document.
- **Finite JSON only:** body emission uses `allow_nan=False`; any non-finite value is a bug, not data.
- **Atomicity of the guard:** malformed input fails before any write and never touches the ledger.

---

## Statement JSON body (validated at emit; schema in `annotation-tokens.md`)

```json
{ "section": "results",
  "stance": "asserted",
  "subject": "BRCA1 loss",
  "object": "genomic instability",
  "subject_concept": "https://identifiers.org/ncbigene:672" }
```

`section` (CLI-written) and `stance` (required) always present; `subject` / `object` /
`subject_concept` / `object_concept` present only when supplied and (for concepts) verified. Keys
sorted, finite, compact — byte-deterministic for stable `content_hash`.

---

## Subagent + command

- **`agents/paper-annotate.md`** — subagent (frontmatter `name/description/model/tools`),
  `model: claude-sonnet-4-6` (parallels `paper-researcher`). Contract: read existing annotations
  (`annotate list --status open --status ack --format json`) + `.source.md`; emit a well-formed
  `candidates.json`; call `science annotate extract`; report `written` / `skipped` / dropped
  grounding back to the orchestrator. Does **one** paper. Does not touch the sidecar or summarize.
- **`commands/annotate-paper.md`** — the orchestrator workflow: resolve the project profile via
  `references/command-preamble.md`, run the `--check` precheck, dispatch the subagent on `changed`
  (or `--force`), surface the final report. Bulk-dispatchable, exactly like `research-papers.md`.

---

## Vocabulary registration

`docs/conventions/annotation-tokens.md` gains a Phase-3a section:

- `annotation_type` values `proposition` / `question` / `hypothesis` (Motivation `oa:classifying`).
- The versioned source prefix `llm-annot:<model>:paper-annotate-vN` and its bump policy
  (prompt / body-schema changes bump `vN`).
- The statement body schema, the `stance` enum, and the normalized `section` enum + BioC mapping table.

---

## Testing

Deterministic `extract` carries the bulk of coverage (no live LLM):

- **Anchoring:** unique match; `extract-quote-not-found`; `extract-quote-ambiguous`
  (same quote twice, prefix/suffix disambiguates one); empty prefix/suffix.
- **Section:** derivation from offset + normalization (known BioC types + unknown→`other`).
- **Grounding:** verified concept kept; unknown IRI dropped + counted; dismissed/superseded entity
  IRI excluded from the active set (status policy).
- **Body:** deterministic byte-string (`sort_keys`/`separators`/`allow_nan=False`); optional fields
  omitted when absent.
- **Dedup:** two identical statements at different offsets both persist (the `file_idx:length`
  discriminator); a byte-identical re-run dedupes to zero new rows.
- **Strict validation:** unknown field / unknown `type` / unknown `stance` / over-count /
  over-length → fail loud, nothing written, ledger unchanged.
- **`--check`:** `changed` vs `unchanged`; the hash is recorded only after a successful write run;
  a failed run leaves the prior hash intact.
- **Round-trip:** an end-to-end `.source.md` + entity-sidecar fixture → `candidates.json` →
  `extract` → `annotate verify` confirms every seeded selector re-anchors.
- **Ledger I/O:** `source_text_hash` Turtle round-trip; legacy ledger without the predicate reads as
  `None`.
- **Agent:** a small `candidates.json` → `extract` integration test exercises the contract; the
  subagent prompt itself is not run against a live model in tests.

---

## Out of scope (→ 3b / Phase 4)

- **Metaphors / analogies** (3b): additive — one new body schema (`source_domain`/`target_domain`/
  `mapping`/`cue?`), one new `annotation_type` pair, one prompt section. The `extract` command,
  anchoring, section derivation, dedup, and guard are all reused unchanged.
- **Predicate / full-SPO decomposition**, claim-layer assignment, embedding-based promotion, and
  entity linking beyond exact-coincidence grounding — all Phase 4 (promotion).

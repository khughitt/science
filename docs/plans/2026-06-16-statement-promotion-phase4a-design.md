# Phase 4a — Statement→Proposition Promotion (design)

**Project:** `lit-annot` sub-article annotation (EXTEND `science`). Phase 4 = promotion of
raw span annotations into epistemic entities. This spec is **slice 4a**: the
statement→proposition spine only.

**Status:** approved design (brainstorming complete; 5 architectural forks resolved with
the user). Next step: implementation plan.

---

## Goal

A deterministic, curator-reviewed path that turns `proposition`-type **statement
annotations** on a paper's `.source.md` sidecar into `proposition` **entities** — minting
new ones or linking to existing ones — with clean provenance and **no factoring or
inference**. The value of 4a is the *spine*: the mint-or-link decision, provenance, and
idempotency that every later slice (4b/4c/4d) reuses.

## Where it fits

```
Phase 3a/3b (DONE): paper-annotate agent + `science annotate extract`
  → statement annotations  (annotation_type ∈ {proposition, question, hypothesis})
  → figurative annotations  (metaphor, analogy)

Phase 4a (THIS):    proposition-type statement annotation → proposition entity
Phase 4b (later):   question/hypothesis statement → question/hypothesis entity
Phase 4c (later):   predicate/polarity/claim_layer synthesis (factoring)
Phase 4d (later):   cross-paper evidence (cito:supports/disputes) → belief layer
```

## What 4a consumes and produces

**Consumes** — `proposition`-type statement annotations (Phase 3a output) on a single
paper's `.source.md` sidecar. Each carries:
- a `TextQuoteSelector` whose `exact` is the **claim text** (the statement span);
- a JSON `TextualBody`: `{section, stance, subject?, object?, subject_concept?, object_concept?}`
  (`stance ∈ {asserted, negated, hypothesized, open}`; `subject`/`object` are free-text
  phrases; `*_concept` are verified entity IRIs);
- a lifecycle `Status` (`OPEN`/`ACK`/…).

**Produces** — `proposition` entities (canonical `entities/propositions/<slug>.md`), each a
minimal valid `PropositionEntity`, plus a provenance edge and a sidecar backlink.

---

## Architecture: candidate → review → apply

New subcommand **`science annotate promote <source.md path>`** (on the existing `annotate`
group, alongside `extract`/`pubtator`). Mirrors the established `consolidate`
candidate→apply idiom.

- **Read-only by default.** Scans the sidecar's *promotable* proposition annotations (queue
  rule below) and prints a **candidate list** — each row is `MINT <new-slug>` or
  `LINK <existing-slug>`, with the claim text and the decision reason. `--json` emits the
  same for tooling/agents. **Writes nothing.**
- **`--apply`.** Executes the candidates: mints/links propositions, writes the provenance
  edge, adds the sidecar backlink. Idempotent (see below).

**Run scope & granularity.** One sidecar (one paper) per invocation. The mint-or-link
dedup checks against the **whole project's** proposition corpus (not just this sidecar).
**1 statement annotation → 1 proposition** (MINT a new one, or LINK to an existing one).

---

## Decision 1 — mint-or-link (precision-first, deterministic)

For each promotable annotation:

1. Compute `key = normalize_text(claim_exact)` (reuse the existing `_normalize_text` from
   `statement_extract` — lowercase + whitespace-collapse).
2. If `key` equals `normalize_text(title)` of an **existing proposition** → **LINK**
   (suggest that slug).
3. Else → **MINT** a new proposition.

**Match target is the proposition `title`** specifically. Because 4a mints `title = claim`,
two papers asserting the *identical* sentence dedup to one proposition — the main
cross-paper win. Hand-authored propositions have concise titles that won't match a claim
sentence; that is **intentional** — the curator redirects a `MINT` to a `LINK` at review
time. Paraphrase/embedding dedup is explicitly a **later slice**, not 4a.

The decision is fully deterministic and explainable in the review output (every row states
MINT-vs-LINK and why).

## Decision 2 — the minted proposition (minimal, valid, no inference)

`PropositionEntity` is constructable from relational fields alone — `predicate`,
`polarity`, `subject`, `object`, `claim_layer`, `identification_strength` are all optional
(`| None`), and the relational validator only fires *when `predicate` is set*. So 4a mints
a minimal **valid** proposition:

| Field | Value at mint |
|---|---|
| `id` | `proposition:<slug>` where `slug = slug_for_claim_text(claim)` (word-boundary slug, same helper behavior as workbench) |
| `title` | the claim text (verbatim) |
| Claim section body | the full claim text |
| `subject` / `object` | the annotation's free-text phrases **when present**, else `None` (harmless: no `predicate` ⇒ validator dormant) |
| `predicate`, `polarity` | **unset** (4c) |
| `claim_layer`, `identification_strength`, `proxy_directness`, `supports_scope` | **unset** (4c / curator) |
| `status` | `draft` |
| `source_refs` | the source paper (citekey) — existing entity→paper provenance |

**Reasoning fields are left unset, not defaulted.** 4a's value is the spine, not premature
factoring; baking the template defaults (`empirical_regularity`/`observational`/…) would
assert un-reviewed claims. **Caveat to verify in planning:** if a `validate`/health build
gate actually *requires* `claim_layer` on a proposition, fall back to the template default
for that one field and note it; otherwise leave unset.

Persisted through the canonical entity writer (path policy + frontmatter dump + atomic
replace) — **not** a parallel writer.

## Decision 3 — provenance (a materialization fact, orthogonal to status)

Promotion is recorded as a *materialization fact*, never as a status disposition (the
`Status` enum keeps meaning annotation disposition: `open`/`ack`/`fixed`/`dismissed`/
`superseded`). Both sides of the link are recorded so idempotency is robust if one side is
missing or repaired:

- **Entity side:** the proposition gets `prov:wasDerivedFrom` → the source annotation, and
  references the source paper via `source_refs`. *(Plan resolves the exact frontmatter
  representation that materializes this edge, and confirms the existing
  `graph/materialize` provenance path supports an entity→annotation `wasDerivedFrom` edge;
  if it does not, the spine records the link from the annotation `sci:promotedTo` side and
  materializes the inverse — the entity→annotation edge is the requirement, the carrier is
  a plan detail.)*
- **Annotation side:** the sidecar annotation gets a `sci:promotedTo "proposition:<slug>"`
  backlink (new annotation metadata; status untouched).

**Idempotency / promote queue.** The promote queue is: active (`OPEN`/`ACK`)
`proposition`-type annotations with **no `sci:promotedTo` AND no existing derived
proposition**. Re-running `promote --apply` skips already-promoted rows. Checking *either*
signal (backlink OR a proposition whose `wasDerivedFrom` names this annotation) makes the
skip robust to a half-written pair.

- `FIXED` is **not** reused (it means "issue resolved").
- No `promoted` value is added to `Status` (orthogonal to disposition).

---

## Shared-primitive refactor (reuse workbench minting cleanly)

4a must reuse the workbench's entity-minting machinery **without depending on
`dag.workbench` privates**. The plan will:

1. **Promote the entity writer to a shared, intentional helper.** `dag.workbench._write_entity_file`
   is currently private. Extract it (or a thin public wrapper) into an entity-writing
   module that both `workbench` and `promote` call. It already reuses `resolve_path_policy`
   + `_render_markdown` + `_atomic_replace_text` + `default_status` + created-stamp
   preservation on upsert — keep that behavior verbatim. **Extension:** it must accept the
   **Claim section body** so the minted proposition's Claim section carries the claim text
   (workbench rows have empty bodies; 4a needs one populated section).
2. **Add a `slug_for_claim_text(claim)` slug variant.** Keep the workbench slug helpers'
   behavior (`truncate_slug_on_word_boundary(normalize_to_slug(...), DERIVED_SLUG_MAX_LENGTH)`
   + the `len < 2` fail-loud guard), but seeded from claim text instead of a
   `subject-predicate-object` triple. Factor so workbench's `_slug_for_triple` and the new
   variant share the underlying call.

This keeps a single canonical entity writer and a single slug behavior — no parallel
implementations.

---

## Fail-loud behavior (skip-and-count, nothing silent)

Consistent with the seeders/extract: the read side fails loud on structural problems and
**skips with a counted reason** on per-annotation issues. Reasons (each surfaced in the
candidate list + `--json`, nothing silent):

- `promote-already-promoted` — has `sci:promotedTo` or an existing derived proposition (queue exclusion, reported as skipped not error).
- `promote-claim-unsluggable` — claim text cannot derive a stable slug (`len < 2`).
- `promote-not-proposition-type` — annotation is `question`/`hypothesis`/figurative (out of 4a scope; skipped).
- `promote-inactive-status` — not `OPEN`/`ACK`.

A malformed sidecar / unparseable annotation body is a **hard, loud failure** (not a skip).

## Output

- **Default (read-only):** a table — one row per promotable annotation: `{annotation id,
  decision (MINT <slug> | LINK <slug>), claim (truncated), reason}` — plus a skipped-count
  summary by reason. `--json` emits the structured candidate list.
- **`--apply`:** the same candidate list, then an applied summary
  (`minted` / `linked` / `skipped`), and the written entity paths.

---

## Testing strategy

- **Mint-or-link unit:** identical normalized claim → LINK to existing; novel claim → MINT;
  case/whitespace-only differences collapse; a near-paraphrase does **not** auto-link
  (precision-first).
- **Minimal-proposition unit:** minted entity is a valid `PropositionEntity` with
  `title=claim`, Claim section = claim text, `subject`/`object` copied when present,
  relational/reasoning fields unset, `status=draft`.
- **Provenance unit:** entity carries `prov:wasDerivedFrom` → annotation + paper
  `source_refs`; sidecar gains `sci:promotedTo`; annotation status unchanged.
- **Idempotency:** second `--apply` is a no-op (skip `promote-already-promoted`); the
  backlink-present and derived-proposition-present paths each independently suppress
  re-mint; a half-written pair (only one side) still suppresses.
- **Read-only guarantee:** default invocation writes no entity files and no sidecar edits.
- **Shared-writer round-trip:** the extracted/ wrapped writer produces byte-identical output
  to the prior workbench path for an equivalent entity (no regression); the Claim-section
  body extension renders correctly and re-parses.
- **CLI:** `science annotate promote <path>` round-trip (candidate list → `--apply` →
  entity on disk + backlink in sidecar); malformed input fails loud.

## Out of scope (later slices)

- `question` / `hypothesis` promotion (4b).
- `predicate` / `polarity` / `claim_layer` / `identification_strength` synthesis (4c).
- Cross-paper evidence aggregation (`cito:supports`/`disputes`) and belief-layer wiring (4d).
- Embedding / paraphrase dedup.
- Figurative (metaphor/analogy) promotion — no truth-apt target.
- Any agent/LLM in the loop (4a is fully deterministic).

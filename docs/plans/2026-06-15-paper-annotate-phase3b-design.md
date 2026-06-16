# Paper-Annotate Phase 3b Design — Figurative Annotation (metaphor / analogy)

> Sub-article annotation project, Phase 3 (split: 3a = statements **[shipped]**, **3b = metaphors / analogies**).
> Builds directly on Phase 3a (`science annotate extract`, the `paper-annotate` agent, the
> `.source.anno.trig` sidecar machinery). See `docs/plans/2026-06-15-paper-annotate-phase3a-design.md`.

**Goal:** Extend the existing `paper-annotate` agent + `science annotate extract` command to also
extract **metaphor** and **analogy** spans from a paper's `.source.md`, persisting them as
`oa:classifying` span annotations with a figurative body schema. **Annotate-first, promote-later**:
extraction writes verified figurative spans; richer linking is Phase 4.

**Architecture (one sentence):** purely additive — the same agent (brain) emits a single mixed
`candidates.json` whose `type` field discriminates statement vs figurative candidates, and the same
deterministic `extract` command (hands) dispatches **only** candidate parsing and body generation by
kind; anchoring, section derivation, dedup, the document idempotency guard, and the source identity
are reused **byte-for-byte unchanged**.

---

## Why this is genuinely additive (no migration, no version bump)

Phase 3a has processed **zero** papers — verified: no `.source.anno.trig` sidecar carries the
`paper-annotate` source, and no `proposition`/`hypothesis` annotation exists in the repo. The agent
is therefore being **expanded before first real use**. Consequences:

- The source identity stays `llm-annot:<model>:paper-annotate-v1`. Expanding the agent's scope before
  any observed v1 behavior is *defining* v1, not changing it — so no `vN` bump (a bump would, via the
  per-annotation `source`, duplicate every statement row on re-run, and there is nothing to re-run).
- The `--check` re-run guard and the `AuditLedger.source_text_hash` ledger are **untouched**.
- No legacy/compat shims, no data migration.

---

## Candidate kinds — discriminated parse on `type`

`parse_candidates` becomes a discriminated parser. The `type` field selects the kind:

| `type` | Kind | Dataclass |
|--------|------|-----------|
| `proposition` / `question` / `hypothesis` | statement | `StatementCandidate` (the 3a `Candidate`, **renamed**) |
| `metaphor` / `analogy` | figurative | `FigurativeCandidate` (**new**) |
| anything else | — | `CandidateError` (fail loud, unchanged) |

**Renames (approved):** `Candidate` → `StatementCandidate`; `extract_statements` →
`extract_candidates` (it now handles both kinds). The 3a unit/CLI tests are updated to the new names —
mechanical churn, zero behavior change. The clearer contract makes future
`RelationCandidate`-style additions less awkward.

Each kind owns its own allowed/required key sets. Shared anchoring fields
(`type` / `exact` / `prefix` / `suffix`) validate identically for both. `parse_candidates` returns
`list[StatementCandidate | FigurativeCandidate]`; a single `candidates.json` array may freely mix the
two kinds.

### `FigurativeCandidate` fields

```json
{
  "type": "metaphor",
  "exact": "the immune system mounts an attack",
  "prefix": "we describe how ",
  "suffix": " on invading pathogens.",
  "source_domain": "warfare",
  "target_domain": "immune response",
  "mapping": "immune cells framed as soldiers defending tissue",
  "cue": "attack"
}
```

- `type` ∈ `{metaphor, analogy}` (required).
- `exact` (required, non-empty), `prefix` / `suffix` (required; may be empty strings — the anchoring
  fields keep 3a semantics, empty = no constraint on that side).
- `source_domain`, `target_domain` — **required, non-empty after trim**.
- `mapping`, `cue` — optional; if the key is present it must be **non-empty after trim** (a blank /
  whitespace-only optional field is a defect, not "absent" — fail loud rather than store a placeholder).

**Non-empty-after-trim rule (figurative only).** Every figurative *content* field
(`source_domain` / `target_domain` / `mapping` / `cue`) is validated with `value.strip()`:

- required field blank-after-trim → `CandidateError` (fail loud).
- optional field present but blank-after-trim → `CandidateError` (fail loud) — callers must omit, not
  blank.
- the **stored** value is the trimmed string (these are descriptive body text, not verbatim anchors,
  so trimming surrounding whitespace is safe and keeps the body clean).

This rule is scoped to figurative fields. Statement fields are unchanged: `exact` keeps its existing
non-empty check; `prefix`/`suffix` may legitimately be empty; `subject`/`object` keep 3a behavior.
The shared `MAX_FIELD_CHARS` over-length bound applies to figurative fields too.

**Cross-kind field rejection.** A statement-only field (`stance` / `subject` / `object` /
`subject_concept` / `object_concept`) on a figurative candidate is an unknown key for that kind →
`CandidateError`. Symmetrically, a figurative-only field
(`source_domain` / `target_domain` / `mapping` / `cue`) on a statement candidate is an unknown key →
`CandidateError`. Each kind's `_ALLOWED_KEYS` enforces this; no field bleeds across kinds.

---

## Figurative body schema

```json
{ "section": "discussion",
  "source_domain": "warfare",
  "target_domain": "immune response",
  "mapping": "immune cells framed as soldiers defending tissue",
  "cue": "attack" }
```

- `section` (CLI-derived from the anchored offset) + `source_domain` + `target_domain` always present.
- `mapping` / `cue` present only when supplied (same None-gating as statement optional fields).
- **No `stance`, no `*_concept`, no grounding.** Figurative domains are free-text;
  `active_entity_iris` is **not** consulted on the figurative path. Entity-grounded domains are Phase 4.
- Same deterministic serialization as 3a:
  `json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False)` — byte-stable, clean diffs.

A new `figurative_body_json(*, section, source_domain, target_domain, mapping, cue)` mirrors
`statement_body_json` (now both live alongside each other in `statement_extract.py`).

---

## Planning — shared anchor core, per-kind body

The 3a `plan_statement` body is **already** type-agnostic except for grounding + body JSON:
`match_text = f"{type}|{file_idx}:{length}|{normalized_exact}"`, `annotation_type = candidate.type`,
`Motivation.CLASSIFYING`, the passage-clamped `TextQuoteSelector`, and the unique-or-skip anchoring all
key off `type` / `exact` generically.

Refactor: extract the shared **locate-and-anchor** step into a helper
`_anchor_candidate(file_text, persisted, exact, prefix, suffix)` returning either a skip reason
(`extract-quote-not-found` / `extract-quote-ambiguous` / `extract-anchored-outside-passage`) or the
anchored locus `(file_idx, length, pp, selector)`. The helper does **not** build `match_text` —
`match_text` is composed **per kind** by the planner, because its discriminator differs (below). Then
two thin planners:

- `plan_statement(...)` — calls the helper, applies opportunistic grounding drop, builds the statement
  body, and composes the 3a-identical `match_text = f"{type}|{file_idx}:{length}|{normalized_exact}"`.
  **Behavior byte-identical to 3a.**
- `plan_figurative(...)` — calls the helper, **no grounding**, builds the figurative body, and composes
  a domain-discriminated `match_text` (below). Returns `grounding_dropped = 0` always.

### `match_text` dedup discriminator (per kind)

`merge_planned` dedupes on `(source, selector.exact, lifted_from, match_text)`
(`audit.py::_annotation_tuple`) — there is **no positional component**, so `match_text` must carry
everything that makes a row a distinct annotation. The two kinds differ in what that is:

- **statement:** `f"{type}|{file_idx}:{length}|{normalized_exact}"` — unchanged from 3a. The
  `file_idx:length` segment distinguishes repeated identical statements at different offsets; the
  optional `subject`/`object` are *not* identity (they may be absent), so they stay out of the key.
- **figurative:** `f"{type}|{file_idx}:{length}|{normalize_text(source_domain)}|{normalize_text(target_domain)}"`.
  `source_domain` + `target_domain` are **required semantic identity** — two `metaphor` candidates
  anchored at the **same span** but asserting different domains are genuinely different annotations and
  must not collapse. They are therefore part of the figurative key (`mapping`/`cue` are optional
  enrichment, not identity, so they stay out, mirroring how `subject`/`object` are excluded for
  statements). `normalize_text` is the existing whitespace-collapse helper.

Both return the same `(PlannedAnnotation | None, skip_reason | None, dropped)` shape, so the
orchestrator loop is kind-uniform.

`extract_candidates` (renamed) iterates the mixed candidate list, dispatches each to the right planner
by kind, then runs the **same** `merge_planned` → guard (`advance = not skipped`) →
`source_text_hash` ledger update → `serialize_sidecar` path as 3a. `ExtractReport` is unchanged
(`written` / `skipped` / `grounding_dropped` / `source_text_hash_recorded` / `note`); a figurative-only
run simply reports `grounding_dropped = 0`.

---

## Agent + command + conventions

### `agents/paper-annotate.md`
- Update `description` to cover statements **and** metaphors/analogies.
- Replace the "Statements only (no metaphors/analogies — that is a later phase)" scope line.
- Add a **figurative extraction** section defining the split and fields:
  - **metaphor**: figurative framing or identity transfer between two domains, often *implicit*
    ("the cell is a factory"; "the immune system mounts an attack").
  - **analogy**: an *explicit* comparison or structural mapping between two domains
    ("like a factory line, the ribosome assembles...").
  - fields: `source_domain` (the domain being borrowed FROM — the vehicle), `target_domain` (the
    actual subject being described — the tenor), `mapping` (optional: the correspondence being
    transferred), `cue` (optional: the lexical trigger, e.g. "like" / "as" / "mounts").
  - same anchoring discipline as statements (verbatim `exact` from passage bodies; never headings).
  - both kinds go in the **same** `candidates.json`, mixed with statements.

### `science/src/science_tool/annotation/cli.py` (the public CLI surface)
`extract_cmd` (the `annotate extract` command) is the caller of the renamed orchestrator and must be
updated:
- import + call `extract_candidates` (was `extract_statements`).
- the human-readable (table) output is **type-neutral**: `"{written} annotation(s) written"` (was
  `"statement(s) written"`), since a run may now write statements and/or figurative rows. The `--json`
  output keys are unchanged (`written` / `skipped` / `grounding_dropped` /
  `source_text_hash_recorded` / `note`).
- the docstring is reworded from "statement candidates" to "annotation candidates" (statements +
  figurative); `--check` / `--input` / grounding behavior is otherwise unchanged.

### `commands/annotate-paper.md`
- Type-agnostic orchestration — **no logic change**. Wording touch so it no longer says "statements"
  exclusively (it dispatches the same agent + surfaces the same report).

### `docs/conventions/annotation-tokens.md`
- Add `metaphor` / `analogy` to the `annotation_type` table (Motivation `oa:classifying`).
- Document the figurative body schema, the `source_domain` / `target_domain` / `mapping` / `cue`
  field semantics, the required-vs-optional + non-empty-after-trim rule, and the metaphor/analogy
  distinction.
- The versioned-source prefix and bump policy are unchanged (still `paper-annotate-v1`; bumps remain
  reserved for a future prompt/body-schema change *after* first real use).

---

## Testing (mirrors 3a, figurative-specific)

Deterministic `extract` carries the coverage (no live LLM):

- **Parse — valid:** a `metaphor` and an `analogy` candidate parse to `FigurativeCandidate`; a mixed
  statement+figurative array parses to the right kinds.
- **Parse — fail loud:** missing `source_domain` / `target_domain`; blank-after-trim required field;
  optional `mapping`/`cue` present-but-blank; unknown figurative field; a statement-only field
  (`stance`/`subject`) on a figurative candidate; a figurative-only field (`source_domain`) on a
  statement candidate; over-length figurative field.
- **Body:** deterministic byte-string (`sort_keys`/compact/`allow_nan=False`); `mapping`/`cue` omitted
  when absent; trimmed value stored (leading/trailing whitespace removed).
- **Plan / anchor:** figurative reuses the shared anchor path — `extract-quote-not-found`,
  `extract-quote-ambiguous`, `extract-anchored-outside-passage`, and section derivation behave
  identically to statements (one shared-helper test plus a figurative happy-path test).
- **Grounding:** a figurative run never consults `active_entity_iris` and always reports
  `grounding_dropped = 0`, even when the paper has active entity annotations.
- **Dedup / guard:** a `metaphor` and a `proposition` anchored at the **same span** both persist
  (distinct `type` segment in `match_text`); **two `metaphor` candidates at the same span with
  different `source_domain`/`target_domain` both persist** (domain segments keep them distinct), while
  a byte-identical mixed re-run dedupes to zero new rows; the idempotency hash advances on a clean
  figurative-only run and does **not** advance when a figurative candidate fails to anchor.
- **CLI round-trip:** a mixed `candidates.json` → `extract` → `annotate verify` re-anchors every
  written row (statement and figurative); the table output reads `annotation(s) written` (type-neutral).

---

## Out of scope (→ Phase 4)

- Entity-grounded figurative domains, predicate/full-mapping decomposition, claim-layer assignment,
  embedding-based promotion, and any linking of figurative spans into epistemic entities.

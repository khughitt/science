---
id: "convention:annotation-tokens"
type: "convention"
title: "Annotation tokens"
status: "active"
created: "2026-05-09"
updated: "2026-06-15"
---

# Annotation tokens

Inline marker tokens used in prose to flag specific epistemic states. Counted by `validate.sh` and `science refs check` via the shared scanner in `science_tool/markers.py`.

## Vocabulary

| Token                | Meaning                                                                  | Default severity | Under `--strict` |
|----------------------|--------------------------------------------------------------------------|------------------|------------------|
| `[UNVERIFIED]`       | Verifiable in principle but not yet checked.                              | warn             | warn             |
| `[MISSING_CITATION]` | A specific factual claim needs a source pointer (claim not in dispute). | warn             | warn             |
| `[SPECULATION]`      | Author conjecture / brainstorming layer.                                  | info             | warn             |
| `[INACCESSIBLE]`     | Source paywalled / image-only / DACO-gated / private; expected permanent. | info             | warn             |

`info`-severity tokens are counted by the scanner but do not contribute to `validate.sh`'s warning count nor cause a non-zero exit from `science refs check` unless `--strict` is set.

## Lexical scope

A token's *meaning* depends on whether it appears inside an inline-code span or a fenced code block:

- **Bare token** in prose (e.g., `the n is [UNVERIFIED] in the abstract`) is a **document annotation** and counts toward severity tallies.
- **Backticked token** (e.g., ``mark this `[UNVERIFIED]` per the convention``) is **documentation/example use** — referring to the token as a token. Excluded from tallies.
- Tokens inside fenced code blocks (` ``` `) are also excluded.

This split lets convention docs (this file included) discuss the tokens without polluting validation output.

## Choosing the right token

```
Is the claim verifiable from a source you can reach?
├── Yes → not yet checked → [UNVERIFIED]
├── Yes → checked, just need to write the cite → [MISSING_CITATION]
├── No  → because it's your own conjecture → [SPECULATION]
└── No  → because the source is paywalled / private / image-only → [INACCESSIBLE]
```

## Legacy alias

`[NEEDS CITATION]` is recognized as a synonym for `[MISSING_CITATION]` during the deprecation window. The scanner reports occurrences as canonical `[MISSING_CITATION]` but tags the underlying hit as `legacy: true` in JSON output. Run `science markers migrate --write` to rewrite legacy spellings in place. Backticked legacy spellings (in this doc, for example) are preserved.

## Tooling

- `science markers scan [--root .] [--format json|table] [--strict] [--include-documentation]` — scan project markdown for tokens.
- `science markers migrate [--root .] [--write]` — rewrite legacy `[NEEDS CITATION]` spellings to canonical `[MISSING_CITATION]`.
- `science refs check` and `validate.sh` both delegate marker counting to the same scanner.

## Future work (phase 3)

A richer sub-document annotation system (rich payloads, multi-annotation per ROI, graph integration) is deferred to a follow-up RFC. The four phase-2 tokens become annotation *types* under that design; existing inline tokens continue to work, and richer payloads opt into a sidecar form. See `docs/plans/2026-05-09-annotation-system-stub.md` for the full phase-3 sketch.

## See also

- [Prose lints](prose-lints.md) — mechanically-detectable prose issues
  (bare author-year, short-form IDs, frontmatter-inline gaps, numeric
  anchors). Lints surface candidates; the four-token vocabulary is the
  authoring output for claims that need LLM/human judgment.

## Full-text license whitelist (Phase 1 — source-text persistence)

`<citekey>.source.md` persists full text only when the resolved license is on
this whitelist. The persisted `license` frontmatter field records the raw value
verbatim; the canonical token below is used only for membership testing
(uppercased, spaces/underscores → hyphens, version suffix stripped).

| Canonical token | Versioned forms accepted | Persist full text? |
|-----------------|--------------------------|--------------------|
| `CC0`           | `CC0-1.0`                | yes |
| `CC-BY`         | `CC-BY-4.0`, `CC-BY-3.0` | yes |
| `CC-BY-SA`      | `CC-BY-SA-4.0`           | yes |
| `CC-BY-ND`      | `CC-BY-ND-4.0`           | yes |
| anything else (incl. `CC-BY-NC*`, `unknown`, absent) | — | **no** — abstract only; `fulltext_omitted_reason` is `license-not-whitelisted` when full text existed, else `no-fulltext-available` |

License is resolved from Europe PMC `license` in Phase 1 (Unpaywall's `oa_locations[].license` is deferred, with EPMC license the Phase 1 primary); with multiple values the most-permissive whitelisted one
wins, else `unknown`.

> Annotation-type and source-prefix vocabularies (e.g. `entity-gene`,
> `pubtator3:<release>:seeder-vN`) are introduced in Phase 2+; only the license
> whitelist is in scope for Phase 1.

## PubTator3 entity-mention seeding (Phase 2a)

Source prefix: `pubtator3:<release>:seeder-vN` — `<release>` is the BioC `_release`
infon (fallback `pubtator3-api`); bump `seeder-vN` when the offset-mapping or
concept-normalization logic changes (invalidates the re-audit cache).

Entity annotation types (`sci:annotationType`), motivation `oa:identifying`, single
`IriBody` carrying the concept IRI (identifiers.org compact form
`https://identifiers.org/<namespace>:<accession>`):

| annotation_type | Biolink class | concept IRI namespace |
|---|---|---|
| `entity-gene` | `biolink:Gene` | `ncbigene` |
| `entity-disease` | `biolink:Disease` | `mesh` |
| `entity-chemical` | `biolink:ChemicalEntity` | `mesh` |
| `entity-species` | `biolink:OrganismTaxon` | `taxonomy` |
| `entity-variant` | `biolink:SequenceVariant` | `dbsnp` (rsID only) |
| `entity-cellline` | `biolink:CellLine` | `cellosaurus` |

The Biolink class is derived from `annotation_type` via this table; it is NOT stored
in the annotation. Mentions PubTator left unnormalized (no id matching the namespace
shape) are skipped, not stored with a fallback body.

## PubTator3 relation seeding (Phase 2b)

`science annotate pubtator <pmid|doi>` also seeds **document-level relations** from the
same BioC record, alongside entity mentions, under the same
`pubtator3:<release>:seeder-v1` source.

- **`annotation_type`:** `relation`. **Motivation:** `oa:linking`.
- **Target:** the smallest covering span of the closest subject×object entity-mention
  pair within a single persisted passage (PubTator supplies no relation offset).
- **Body:** one `TextualBody` with `format = "application/json"`, carrying a
  deterministic JSON object (`json.dumps(sort_keys=True, separators=(",", ":"))`):
  - always `subject`, `predicate`, `object`, `predicate_source` (`"biolink"` | `"sci"`)
  - `raw_predicate_type` only when the PubTator relation type is unmapped
  - `score` only when PubTator supplied a numeric confidence (excluded from identity)

### Relation-type → predicate map (BioRED 8-type set)

| PubTator `infons.type` | predicate | source |
|---|---|---|
| `Association` | `biolink:associated_with` | biolink |
| `Positive_Correlation` | `biolink:positively_correlated_with` | biolink |
| `Negative_Correlation` | `biolink:negatively_correlated_with` | biolink |
| `Bind` | `biolink:directly_physically_interacts_with` | biolink |
| `Drug_Interaction` | `biolink:interacts_with` | biolink |
| `Cotreatment` | `sci:cotreatment` | sci |
| `Comparison` | `sci:comparison` | sci |
| `Conversion` | `sci:conversion` | sci |

`Drug_Interaction` maps to the broad `biolink:interacts_with`; promotion (Phase 4) may
specialize it. Any unexpected/future type maps to `sci:pubtator_<slug>` (lowercased,
non-`[a-z0-9_]` → `_`) with the verbatim type preserved in `raw_predicate_type` —
never dropped, never presented as a curated predicate.

## Statement annotations (paper-annotate Phase 3a)

Agent-extracted sub-article statements. Produced by the `paper-annotate` subagent →
`science annotate extract`.

- **`annotation_type`**: `proposition` | `question` | `hypothesis` (kebab; no `sci:` prefix).
- **Motivation**: `oa:classifying`.
- **Source identity**: `llm-annot:<model>:paper-annotate-v1`, where `<model>` is the exact
  extracting model id (e.g. `claude-sonnet-4-6`). Bump the `paper-annotate-vN` segment when
  the extraction prompt or the statement body schema changes (invalidates `content_hash`
  and the document `sci:sourceTextHash` guard for that source).
- **Body**: a single `TextualBody` with `format = application/json`, serialized with sorted
  keys + compact separators + `allow_nan=False`:

  ```json
  {"section":"results","stance":"asserted","subject":"BRCA1 loss",
   "object":"genomic instability","subject_concept":"https://identifiers.org/ncbigene:672"}
  ```

  - `section` (required, CLI-derived): one of
    `title · abstract · introduction · methods · results · discussion · conclusion · figure · table · other`.
  - `stance` (required): `asserted · negated · hypothesized · open`.
  - `subject` / `object` (optional): short phrases.
  - `subject_concept` / `object_concept` (optional): concept IRIs, kept ONLY when they match an
    active (`open`/`ack`) `entity-*` annotation in the same paper; otherwise dropped (counted as
    `grounding_dropped`), the statement still persisted.

- **Document guard**: `sci:sourceTextHash` on the per-source `sci:AuditLedger` records the last
  `.source.md` `text_sha256` processed for this source; `extract --check` skips re-running the
  agent when unchanged. Advanced for any validly-processed document (incl. empty / all-duplicate)
  but not when a candidate fails to anchor.

## Figurative annotations (paper-annotate Phase 3b)

Agent-extracted metaphors and analogies. Same `paper-annotate` subagent + `science annotate extract`
command + `llm-annot:<model>:paper-annotate-v1` source as statements — emitted in the **same**
`candidates.json`, discriminated by `type`.

- **`annotation_type`**: `metaphor` | `analogy` (kebab; no `sci:` prefix).
  - **metaphor**: figurative framing / identity transfer between two domains, often *implicit*
    ("the cell is a factory").
  - **analogy**: an *explicit* comparison or structural mapping between two domains
    ("like a factory line, the ribosome assembles ...").
- **Motivation**: `oa:classifying`.
- **Body**: a single `TextualBody` (`format = application/json`), sorted keys + compact separators
  + `allow_nan=False`:

  ```json
  {"section":"discussion","source_domain":"warfare","target_domain":"immune response",
   "mapping":"immune cells framed as soldiers","cue":"attack"}
  ```

  - `section` (required, CLI-derived): same closed vocabulary as statements.
  - `source_domain` / `target_domain` (required, non-empty after trim): the domain borrowed FROM
    (the vehicle) and the actual subject described (the tenor).
  - `mapping` (optional, non-empty if present): the correspondence being transferred.
  - `cue` (optional, non-empty if present): the lexical trigger (e.g. "like" / "as" / "mounts").
  - **No `stance`, no concept grounding** — figurative domains are free-text (entity linking is
    Phase 4). A blank/whitespace-only required-or-present field is rejected (fail loud), not stored.

- **Dedup**: `match_text` for figurative is
  `type|file_idx:length|json([normalized_source_domain, normalized_target_domain])` — the
  whitespace-normalized, JSON-encoded domain pair is the semantic identity (delimiter-safe), so two
  same-span figures with different domains both persist. `mapping`/`cue` are enrichment, not identity.
- **Document guard**: identical to statements (`sci:sourceTextHash`); a mixed statement+figurative
  run advances the hash only when no candidate fails to anchor.

## Statement promotion (Phase 4a)

`science annotate promote <source.md>` turns `proposition`-type statement annotations into
`proposition` entities (mint-or-link). It is **read-only by default**; `--apply` writes,
`--apply --input <candidates.json>` applies curator overrides.

- **Mint-or-link:** a statement LINKs to an existing proposition when `normalize_claim(claim)`
  (casefold + whitespace-collapse) equals `normalize_claim(title)` of an existing proposition;
  otherwise it MINTs `proposition:<slug>` (`slug_for_claim_text`, ≤72 chars). A slug already
  taken by a different-titled proposition is a `promote-slug-collision` (never overwritten;
  resolve with an explicit `id` via `--input`).
- **Minted proposition:** `title` = claim, `## Claim` = claim text, `subject`/`object` copied
  from the statement body when present; `predicate`/`polarity`/`claim_layer`/… left unset
  (Phase 4c). `status: draft`.
- **Provenance (materialization fact, not a status change):** the proposition's `source_refs`
  carries `paper:<paper-id>` (→ `prov:wasDerivedFrom` paper) and the new
  `annotation:<entity-relpath>#<frag>` source ref (→ `prov:wasDerivedFrom` annotation, via the
  materialize bypass branch). The annotation gains a `sci:promotedTo "proposition:<slug>"`
  backlink. Annotation `status` is untouched.
- **Promote queue / idempotency:** active (`open`/`ack`) `proposition` annotations with no
  `sci:promotedTo` and no existing derived proposition. Re-running skips already-promoted rows.
- **Out of scope (later slices):** question/hypothesis promotion (4b), factoring (4c),
  cross-paper evidence (4d), embedding/paraphrase dedup, figurative promotion.

## Question / hypothesis promotion (Phase 4b)

`science annotate promote` also promotes `question`- and `hypothesis`-type statement
annotations into `question` / `hypothesis` entities, alongside `proposition`:

- **Mint-or-link is kind-local.** A claim links only to an existing entity *of the same kind*
  with an equal normalized title; otherwise it mints. A normalized title held by ≥2 same-kind
  entities is skipped `promote-link-ambiguous` (resolve with an explicit id via `--apply --input`).
- **Numeric identity.** Question/hypothesis entities are minted at `entities/questions/NNNN-slug.md`
  / `entities/hypotheses/NNNN-slug.md` via atomic number reservation (no slug-collision case).
- **Template-faithful.** A minted entity carries every required section (claim text in the lead
  section — question `## Summary`, hypothesis `## Organizing Conjecture`) and the descriptor
  default status (`active` / `proposed`). A promoted **hypothesis** is minted `phase: candidate`
  (a literature-sourced framing the project has not committed to).
- **Provenance & idempotency** match Phase 4a: `source_refs` carry `paper:<id>` +
  `annotation:<relpath>#<frag>`; the annotation gains `sci:promotedTo "<kind>:<id>"`; a second
  `--apply` is a no-op.
- **Non-promotable:** metaphor/analogy and entity/relation seeder annotations are skipped
  `promote-non-promotable-type` (no truth/inquiry-apt target).

## Proposition reasoning synthesis (Phase 4c)

`science annotate synthesize <source.md>` is a **curator-reviewed** step that fills the reasoning
fields a promoted proposition left unset — `predicate`, `polarity`, `claim_layer` — and refines
`subject` / `object`. It is **read-only by default** (a scaffold of the in-scope propositions);
`--apply --input <candidates.json>` validates the candidates and writes. The brain/hands split:
the `proposition-synthesize` subagent proposes an **untrusted** candidates file, the deterministic
CLI validates + writes, and the curator runs `--apply`.

- **Source identity**: `llm-synth:<model>:proposition-synthesize-v1`, where `<model>` is the exact
  proposing model id (e.g. `claude-sonnet-4-6`). Bump the `proposition-synthesize-vN` segment when
  the agent prompt, the controlled vocabularies, or the candidate schema change. On `--apply` this
  string is stamped into each touched proposition's `PropositionEntity.reasoning_source`.
- **Candidate file shape**: a top-level `source` (the identity above) plus `candidates[]`. Each
  candidate is one patch for one proposition:

  ```json
  {"source": "llm-synth:claude-sonnet-4-6:proposition-synthesize-v1",
   "candidates": [
     {"proposition": "proposition:<slug>", "annotation": "annotation:<relpath>#<frag>",
      "subject": "BRCA1 loss", "object": "genomic instability",
      "predicate": "affects", "polarity": "positive", "claim_layer": "causal_effect",
      "override": ["claim_layer"]}
   ]}
  ```

  - `proposition` (required): the target proposition id from the scaffold.
  - `annotation` (required): one of *that proposition's own* statement refs from the scaffold —
    the anchor for the patch.
  - `subject` / `object` / `predicate` / `polarity` / `claim_layer` (each optional): the fields
    the patch proposes. An omitted field is left unset — `null` / empty string are rejected
    (fail loud), never written.
  - `override` (optional): a closed set `{subject, object, predicate, polarity, claim_layer}`
    naming already-set fields the curator/agent is deliberately replacing. By default apply fills
    only **unset** fields; a field is overwritten only when listed here. **`reasoning_source` is
    never overrideable.**
- **Controlled vocabularies + interlocks** (enforced by the CLI, fail loud):
  - `predicate` ∈
    `{affects, regulates, associates_with, binds, is_proxy_for, induces_state, transitions_to, subtype_of, part_of}`.
    Setting `predicate` requires an **effective subject AND object** (already in `current`, or
    supplied in the same patch).
  - **Sign-meaningful** predicates `affects` / `regulates` / `associates_with` **require**
    `polarity` ∈ `{positive, negative, unsigned}`. ALL other (**sign-less**) predicates take no
    polarity — the tool writes `not_applicable` automatically; a patch must not send a polarity
    for them. A bare `polarity` with no `predicate` is rejected.
  - `claim_layer` ∈
    `{empirical_regularity, causal_effect, mechanistic_narrative, structural_claim}` —
    independent of subject/object.
- **Skip / error reason tokens**:
  - `synthesize-existing-value-blocks` — the patch sets a field already non-null in `current`
    without listing it in `override`.
  - `synthesize-nothing-to-fill` — the patch contributes no field the proposition can accept
    (all proposed fields already set, none overridden).
  - `synthesize-proposition-uncovered` — the `proposition` id is not one of the in-scope
    propositions for this paper.
  - `synthesize-relation-hint-unresolved` — a referenced relation hint did not resolve to a
    usable subject/object in scope.

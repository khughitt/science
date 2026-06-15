# PubTator3 relation seeder (sub-article annotation — Phase 2b)

- **Status:** Design approved 2026-06-15 → ready for implementation plan.
- **Parent spec:** `~/d/science/docs/plans/2026-06-14-sub-article-annotation-spec.md`
  (Component 2, "PubTator3 seeder", *Relations*). This doc narrows that to an
  implementable **Phase 2b** (document-level relations) and records the decisions made
  while planning it.
- **Builds on:** Phase 2a (`pubtator_seed.py` entity-mention seeder), shipped on
  `main` at `7ba4bdee`. Reuses its BioC fetch, passage bridge, `concept_iri_for`,
  context-window logic, and the `merge_planned` / sidecar machinery.

## Goal

Extend the existing `science annotate pubtator <pmid|doi>` command so the **same**
`seed_pubtator` run that seeds entity mentions also converts each PubTator3
**document-level relation** into an `oa:TextQuoteSelector` annotation — anchored to the
evidence span where the relation's subject and object concepts co-occur, carrying a
JSON `TextualBody` with subject/predicate/object. One BioC fetch, both annotation
shapes, no annotation-model change.

## Empirical grounding (live API, 2026-06-15)

Confirmed against real records (PMID 28483577 and four others) before designing:

- **Relations are document-level** (`doc["relations"]`), each:
  `infons.role1` / `infons.role2` (rich concept objects: `identifier` e.g.
  `"MESH:D000068298"` or bare gene `"8841"`, `type` `"Chemical"/"Disease"/"Gene"`,
  `name`, `accession`), `infons.type` (the predicate, Title_Case), `infons.score`
  (a stringified float), plus a `nodes` list.
- **No evidence-span offset exists on a relation.** `nodes`
  (`{"refid":"2","role":"23,25"}`) and the doc-level `relations_display`
  (`{"name":"treat|@CHEMICAL_…|@DISEASE_…"}`) are an undocumented / separate display
  view — `relations_display` predicates do **not** even align with the raw
  `relations[].infons.type` (observed `treat` vs raw `Negative_Correlation`). Neither
  is a reliable anchor. **We do not use them.**
- **`sentences` is present but empty** in the BioC export — true sentence spans are
  not supplied; sentence-scoped targeting would require our own biomedical
  segmentation (rejected for 2b).
- **Observed `infons.type` values** (`Association`, `Negative_Correlation`,
  `Cotreatment`) are members of the **BioRED / BioREx 8-type relation set** PubTator3
  uses — a small, fixed, well-documented vocabulary.
- **Role `identifier` formats feed the existing `concept_iri_for` verbatim**:
  `"MESH:Dxxxxxx"` / `"MESH:Cxxxxxx"` (disease/chemical, the `MESH:` prefix already
  stripped + `^[A-Z]\d{6,}$`-validated), bare digit genes (`ncbigene`). Role `type`
  is Title_Case; `concept_iri_for` already lowercases.

## Decisions

| # | Decision | Choice |
|---|----------|--------|
| 1 | Span source | PubTator supplies none → **minimal covering span** of the closest co-occurring subject×object mention pair (see *Targeting*). No `nodes`/`relations_display`, no sentence segmentation. |
| 2 | Co-occurrence scope | **Same persisted passage only** for 2b. Subject & object must each have a persisted mention *and* share a passage. Cross-passage targeting deferred (no fixture demands it). |
| 3 | Concept resolution | **Reuse `concept_iri_for`** on each role's `(type, identifier)`. Either role unnormalizable → skip + count. |
| 4 | Predicate map | The **BioRED 8-type** map below; clean Biolink where it exists, `sci:` for the rest. Unexpected types → sanitized `sci:pubtator_<slug>` (never dropped). |
| 5 | Body | One `TextualBody` carrying **deterministic** JSON (sorted keys, compact separators); `Motivation.LINKING`; `annotation_type = "relation"`. No model change. |
| 6 | `score` | **Optional** body field — included only when PubTator supplies a numeric confidence; **never** in `match_text`. |
| 7 | `match_text` | `f"{predicate}|{subject_iri}|{object_iri}|{span_start}:{span_length}"` — predicate + both IRIs + selected span start/length (no `score`, no `exact`). |
| 8 | Source identity | Same `pubtator3:<release>:seeder-v1` as entities. **Additive** — relations are new `annotation_type`/`match_text` rows; entity rows skip unchanged on re-run. No version bump. |
| 9 | One per relation | Exactly one annotation per document-level relation (the single minimal-covering span), matching PubTator's document-level relation semantics. |
| 10 | `SeedReport` | **Structurally separate** entity vs relation counts: `entity_written` / `entity_skipped` / `relation_written` / `relation_skipped`. The CLI prints a combined summary; the API contract does not blur them. |

## Architecture

### CLI & flow (extends 2a — no new command)

`science annotate pubtator <pmid|doi>` is unchanged in surface. `seed_pubtator` now,
after planning entity mentions, **also** plans relations from the *same* already-fetched
BioC record and the *same* paired-passage map, merges both planned lists in one
`merge_planned` call, and reports the two shapes separately.

### Targeting (the heart) — minimal covering span

The relation gives only `(subject_concept, object_concept, predicate, score?)`. Anchor
it to the evidence text deterministically, using the entity mentions Phase 2a already
parses:

For each document-level relation `r = (role1=subject, role2=object, type)`:

1. `subject_iri = concept_iri_for(role1.type, role1.identifier)`;
   `object_iri = concept_iri_for(role2.type, role2.identifier)`. Either `None` ⇒
   **skip, count `relation-unnormalized-concept`.**
2. From the parsed `BiocMention`s, gather **persisted** subject mentions (mentions whose
   span lands in a persisted passage and whose `concept_iri_for(...)` equals
   `subject_iri`) and persisted object mentions (equals `object_iri`). Matching on the
   resolved IRI (not the raw id string) makes subject↔mention identity normalization-
   consistent with the body.
3. If either side has **zero** persisted mentions ⇒ **skip, count
   `relation-no-persisted-mentions`.**
4. Form candidate `(subj_mention, obj_mention)` pairs **within the same persisted
   passage** (both mentions contained by one `PairedPassage`). If no same-passage pair
   exists (the concepts are persisted but never co-occur in one passage) ⇒ **skip, count
   `relation-cross-passage`.**
5. Among same-passage pairs, select the one with the **smallest covering span**:
   `span_start = min(subj.file_idx, obj.file_idx)`,
   `span_end = max(subj.file_idx + subj.len, obj.file_idx + obj.len)`; minimize
   `span_end - span_start`. Ties broken by earliest `span_start` (determinism).
6. `exact = file_text[span_start:span_end]`; `prefix` / `suffix` windows **clamped to
   that passage's bounds** (the 2a `_CONTEXT` logic).
7. Build the `PlannedAnnotation` (body + `match_text` below).

`file_idx` for each mention is the absolute file index already computed by the 2a
offset bridge (`pp.file_char_base + (mention.offset - pp.bioc_offset)`), with the same
`exact == mention.text` slice-verify guard — so the covering span is built only from
mentions that already passed 2a's hard offset check.

### Predicate map (BioRED 8-type set)

| PubTator `infons.type` | predicate CURIE | `predicate_source` |
|---|---|---|
| `Association` | `biolink:associated_with` | `biolink` |
| `Positive_Correlation` | `biolink:positively_correlated_with` | `biolink` |
| `Negative_Correlation` | `biolink:negatively_correlated_with` | `biolink` |
| `Bind` | `biolink:directly_physically_interacts_with` | `biolink` |
| `Drug_Interaction` | `biolink:interacts_with` | `biolink` |
| `Cotreatment` | `sci:cotreatment` | `sci` |
| `Comparison` | `sci:comparison` | `sci` |
| `Conversion` | `sci:conversion` | `sci` |

- **`Bind` → `biolink:directly_physically_interacts_with`** — Biolink's canonical
  binding predicate (Biolink lists `binds` beneath it; the parent is the less
  over-specific choice for PubTator's coarse BioRED "binding" label).
- **`Drug_Interaction` → `biolink:interacts_with`** — accepted but broad; Biolink
  itself flags `interacts_with` as broad and recommends specialization. BioRED drug
  interaction is chemical/drug–drug and not necessarily physical contact, so we keep
  `interacts_with` for 2b and **document that promotion (Phase 4) may specialize it**.
- Matching on `infons.type` is **case-insensitive** (normalized to the table's
  Title_Case keys).
- **Unexpected / future type** (not in the table) ⇒ **never dropped**: emit
  `predicate = "sci:pubtator_<slug>"` where `slug` lowercases the raw type and replaces
  every non-`[a-z0-9_]` character with `_`; `predicate_source = "sci"`; and the JSON body
  additionally carries `raw_predicate_type` = the verbatim original, so no data is lost
  and we never pretend an uncurated value is a curated project predicate.

### Body, identity, dedup

- **Body:** a single
  `TextualBody(value=<json>, format="application/json")`, `Motivation.LINKING`,
  `annotation_type = "relation"`. The JSON object:
  - Always: `subject` (subject IRI), `predicate` (CURIE), `object` (object IRI),
    `predicate_source` (`"biolink"` | `"sci"`).
  - When the relation type was unmapped: also `raw_predicate_type`.
  - When PubTator supplied a numeric confidence: also `score` (float).
  - **Serialization is deterministic:** `json.dumps(obj, sort_keys=True,
    separators=(",", ":"))`. Sorted keys + compact separators + Python's standard float
    encoding give a byte-stable body, so re-runs produce identical `content_hash` /
    `TextualBody.value` and the sidecar does not churn.
- **`match_text`** = `f"{predicate}|{subject_iri}|{object_iri}|{span_start}:{span_length}"`.
  The merge 4-tuple `(source, selector.exact, lifted_from, match_text)` carries no
  position, so the span coordinates keep two relations over the same `exact` text but
  different predicates — or the same triple anchored to different spans — distinct.
  `score` is excluded so a re-extraction with a jittered confidence does not duplicate a
  row. `lifted_from = None`.
- **`content_hash`** stays the spec-pinned `content_hash(selector.exact, source_name)`
  (the re-audit cache key, unchanged); the `match_text` span discriminator governs
  insertion. `pubtator3:` is already in `HASH_REQUIRED_SOURCE_PREFIXES` (added in 2a).
- **Source:** `pubtator3:<release>:seeder-v1` (same as entities; `<release>` from the
  BioC `_release`, fallback `PUBTATOR3_API_VERSION`). Additive: re-running the seeder
  after 2b ships adds relation rows to existing sidecars and leaves entity rows
  untouched (4-tuple skip). The `seeder-vN` segment bumps only when entity behavior,
  relation targeting, normalization, or predicate mapping changes after 2b ships.

### `SeedReport` (restructured — entity / relation kept separate)

```python
@dataclass(frozen=True)
class SeedReport:
    entity_written: int
    entity_skipped: dict[str, int]
    relation_written: int
    relation_skipped: dict[str, int]
    note: str | None = None
```

This **replaces** the 2a `written` / `skipped` fields (no compatibility aliases —
explicit rename). Callers migrate:
- `annotation/cli.py` (the `pubtator` command, ~lines 1034-1037) prints a combined
  summary, e.g. `Wrote 6 entity + 2 relation annotation(s)` plus a merged skip line that
  labels each count's side.
- `science/tests/test_pubtator_seed.py` (6 entity-side assertions) → `entity_written` /
  `entity_skipped`.

The single `merge_planned` call returns one `written` list; the orchestrator partitions
it by `annotation_type` (`relation` vs `entity-*`) to fill the two `*_written` counts.

## File structure

- **Modify** `science/src/science_tool/annotation/pubtator_seed.py`:
  - `@dataclass BiocRelation` (`subject_type`, `subject_id`, `object_type`,
    `object_id`, `rel_type`, `score: float | None`).
  - `parse_bioc_relations(record) -> tuple[list[BiocRelation], dict[str,int]]` — read
    `doc["relations"]`, validate `infons.role1/role2/type`; malformed (missing roles /
    type, non-dict) counted under `malformed-bioc-relation`. `score` parsed to float
    when the `infons.score` string is numeric, else `None`.
  - `RELATION_PREDICATES: dict[str, tuple[str, str]]` (the 8-type table) +
    `predicate_for(rel_type) -> tuple[str, str, str | None]` returning
    `(curie, source, raw_predicate_type_or_None)` with the `sci:pubtator_<slug>`
    sanitizer fallback.
  - `relation_body_json(...)` — builds the dict and the deterministic `json.dumps`.
  - `plan_relation(file_text, paired, relation, mentions_by_iri, *, release,
    source_md_name) -> tuple[PlannedAnnotation | None, str | None]` — the targeting
    algorithm above.
  - Extend `seed_pubtator` to parse relations, plan them, merge entities+relations in
    one `merge_planned`, and return the restructured `SeedReport`.
- **Modify** `science/src/science_tool/annotation/cli.py` — combined report summary
  against the new `SeedReport` fields.
- **Modify** `docs/conventions/annotation-tokens.md` — register the `relation`
  annotation type, `oa:linking` motivation, the 8-type predicate map + the
  `sci:pubtator_<slug>` rule, and the relation JSON body schema.
- **Create** `science/tests/test_pubtator_relations.py` — see *Testing*.

## Reuse vs. new

- **Reuse (unchanged):** `fetch_bioc_record`, `parse_bioc_passages`,
  `parse_bioc_entity_annotations`, `load_persisted_passages`, `pair_passages`,
  `_containing`, `concept_iri_for`, `_CONTEXT` window logic, `merge_planned` /
  `read_sidecar` / `write_sidecar`, `annotation/verify.py` (tests).
- **New:** `BiocRelation` + `parse_bioc_relations`, the predicate map + sanitizer, the
  deterministic JSON body builder, `plan_relation` (covering-span targeting), the
  `seed_pubtator` relation pass, and the `SeedReport` restructure.

## Testing

Fixtures pinned from the **real** record fetched 2026-06-15 (PMID 28483577:
Fluticasone / Formoterol Fumarate / Inflammation / HDAC3; types `Association`,
`Negative_Correlation`, `Cotreatment`).

- **`parse_bioc_relations`:** real-shape relation rows parsed; malformed relation
  (missing role / type) counted under `malformed-bioc-relation`, not dropped silently;
  numeric `score` parsed, non-numeric → `None`.
- **Predicate map:** each of the 8 BioRED types → expected `(curie, source)`;
  case-insensitive match; an unexpected type → `sci:pubtator_<slug>` with the
  non-`[a-z0-9_]`→`_` sanitizer and `raw_predicate_type` in the body.
- **Targeting:** minimal covering span chosen among multiple same-passage candidate
  pairs; tie broken by earliest start; `exact` equals the expected substring; prefix /
  suffix clamped to the passage.
- **Skip taxonomy (nothing silent):** `relation-unnormalized-concept` (a role with no
  normalizable id), `relation-no-persisted-mentions` (concept absent from persisted
  text), `relation-cross-passage` (both persisted but never in one passage) — each
  skipped, counted, reported.
- **Body:** deterministic JSON — `json.dumps(sort_keys=True, separators=(",", ":"))`
  byte-equality across builds; `score` present only when supplied; `raw_predicate_type`
  present only for unmapped types; round-trips through `TextualBody` serialize → parse.
- **`match_text`:** two relations sharing one `exact` span but different predicates both
  survive `merge_planned`; idempotency — re-run at the same release writes zero new
  relation rows.
- **Verifier round-trip:** every seeded relation selector re-resolves via
  `annotation/verify.py` against the rendered `.source.md` (`.broken` / `.fuzzy` /
  `.source_missing` all 0).
- **`SeedReport`:** entity and relation counts populated separately; an end-to-end run
  reports both shapes; the 2a entity assertions pass against `entity_written` /
  `entity_skipped`.
- **CLI:** `CliRunner` + `MockTransport`, combined summary line; existing 2a CLI test
  still green against the new report.

## Out of scope (this phase)

Cross-passage relation targeting; sentence-segmented spans; the `nodes` /
`relations_display` evidence pointers; promotion of relation bodies into the epistemic
graph (Phase 4); statements / metaphors / analogies (Phase 3); first-class structured
RDF relation predicates (the body stays JSON in a `TextualBody` for this iteration).

## Sources checked

Biolink Model predicate docs (`directly_physically_interacts_with`, `interacts_with`,
`positively_correlated_with`, `negatively_correlated_with`, `associated_with`); BioRED
relation-type descriptions (BioRED track paper) + PubTator3 API docs; live PubTator3
BioC export inspected 2026-06-15 (PMID 28483577 + four others).

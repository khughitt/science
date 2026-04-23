# Entity Identity And Creation Policy Follow-Up

## Why

The MM30 migration showed that the real problem is not just naming style. The
upstream gap is broader:

- when a thing deserves entity status at all
- how internal canonical ids relate to external ontology identifiers
- how to handle ambiguous biological references such as gene vs protein vs
  family vs complex
- how to avoid project-local concept sprawl
- how to enforce these rules in tooling rather than relying on memory

This follow-up should therefore define an **entity identity and creation
policy**, not just a naming convention.

## Goal

Define a curator-facing and tool-enforceable policy for:

1. creating entities
2. assigning canonical ids
3. attaching external identifiers and cross-references
4. choosing the right semantic kind and granularity
5. managing lifecycle states such as provisional, deprecated, and promoted

The output should guide both human curation and future `science` lints / skill
behavior.

## Core Design

### 1. Separate Internal Identity From External Authority

Every entity needs a stable internal `canonical_id`, but external identifiers
must be treated as a separate layer.

Recommended structure:

- `canonical_id`
  - the stable internal `science` identifier, for example `gene:EZH2`
- `primary_external_id`
  - one preferred authority-backed identifier when available
- `xrefs`
  - additional external identifiers
- `aliases`
  - human-facing alternate names and synonyms
- `title`
  - preferred display label

The current model already has `canonical_id`, `aliases`, `ontology_terms`, and
`accessions`, but this is not yet enough to express a clean policy. The design
should clarify whether to extend the schema with explicit `primary_external_id`
and `xrefs`, or define a disciplined use of existing fields.

#### Xref shape

Pick a structured representation, not flat strings.

Recommended default:

- `primary_external_id`
  - structured object with fields such as:
    - `source`
    - `id`
    - `curie`
    - optional `version`
    - optional provenance metadata
- `xrefs`
  - list of the same structured object type

This is preferable to a flat `["HGNC:2146", ...]` array because provenance,
version handling, linting, and authority-specific policy become explicit.

#### Canonical rule

- `canonical_id` is internal and stable.
- External identifiers do not replace the internal canonical id.
- Exactly one external identifier should be treated as primary when an entity
  has recognized authority-backed identity.
- Additional identifiers belong in `xrefs`, not as competing canonical forms.

#### Collision rule

- No two internal `canonical_id`s may claim the same `primary_external_id`.
- Add a dedicated collision lint for this, distinct from alias duplication.
- Curators should treat a primary-external-id collision as a hard review stop,
  because it usually signals accidental duplication, unresolved synonymy, or a
  missing split/merge decision.

#### Provenance rule

- Never add a guessed xref without provenance.
- External identifiers should record source provenance such as:
  - manual curation
  - exact resolver hit
  - imported from upstream source
  - author assertion
- If confidence is uncertain, prefer no xref over speculative xref.

#### Versioned accession rule

- Strip version suffixes from the canonical external identifier by default.
  - example:
    - canonical external id: `ENST00000381578`
    - provenance may retain: `ENST00000381578.7`
- Preserve versioned forms only in provenance or source-specific metadata unless
  the version itself is semantically required.

### 2. Required Identifier Policy By Kind

The policy should state which kinds require external identifiers and which do
not.

#### Must carry external identity when available

- genes
- proteins
- chemicals / drugs
- diseases
- cell types
- phenotypes
- anatomy entities
- pathways / processes / functions backed by established ontologies
- taxa / species

#### Usually optional

- `concept:*`
- `mechanism:*`
- `hypothesis:*`
- `story:*`
- `interpretation:*`
- `discussion:*`

These can remain internal-only unless a widely used upstream authority exists
and materially improves interoperability.

Hard rule:

- if a recommended shared kind already exists and cleanly fits the entity, use
  that kind rather than creating a local `concept:*` placeholder
- treat this as a hard rule when a recommended ontology-backed or
  catalog-backed kind already exists; treat it as a preference only when the
  fit is partial or ambiguous

#### Authority preference order

Start with explicit default precedence for the domains we actively use:

- genes
  - HGNC for human, MGI for mouse, species-appropriate authority otherwise
  - NCBIGene as broad fallback
- proteins
  - UniProt accession, species-scoped
- diseases
  - MONDO, then DO, then MeSH for literature-oriented backfill
- drugs / chemicals
  - ChEBI, then PubChem CID, then DrugBank
- cell types
  - Cell Ontology
- phenotypes
  - HPO for human, MP for mouse
- anatomy
  - UBERON
- pathways
  - Reactome, then WikiPathways, then KEGG where license constraints are
    acceptable
- processes / functions / components
  - GO
- taxa
  - NCBITaxon

This should be treated as the first supported policy surface, not a complete
ontology-unification plan for every scientific domain.

### 3. Entity Creation Threshold

The policy needs an explicit answer to “when should this become an entity?”

Recommended default test: create an entity only if at least one is true:

- it participates in two or more typed relations
- it appears in multiple authored sources with non-trivial claims
- it has a recognized external identifier in a recommended authority
- it is needed by a downstream consumer such as a query, graph report,
  dashboard, or workflow

If none apply, keep it as prose.

#### Additional creation rules

- Quantitative states are not entities by default.
  - Example: “high EZH2 expression” is an attribute or observation on
    `gene:EZH2`, not its own entity.
- Event reification is opt-in, not default.
  - Model as relations first.
  - Reify as an event entity only when the event carries its own properties
    such as timing, magnitude, perturbation, or inhibitors.
- Parent-child grounding is required for narrower local concepts.
  - Example: `concept:h3k27me3` should link upward to a broader chromatin or
    ontology-backed parent.

Dependency note:

- the attribute / observation model must be expressive enough to absorb
  quantitative-state use cases
- otherwise curators will predictably invent workaround entities such as
  `concept:high-ezh2-expression`
- this policy therefore depends on adequate support for attributes,
  observations, and measurement states

### 4. Resolution And Granularity Rules

This is the main guardrail against `concept:*` sprawl.

#### Lumper default for vague abstractions

- Collapse near-synonyms into one entity with aliases unless claims materially
  diverge.

#### Splitter default for named molecules / taxa / diseases

- One entity per canonical authority-backed identity.
- Never merge distinct molecules just because the literature is sloppy.

#### Avoid transient modifiers as entities

- Do not create entities for one-off modified labels like
  `concept:high-ezh2-expression`.
- Use attributes, observations, or measurement values instead.

#### Orphan policy

- Add a linter rule for orphan entities with no meaningful graph participation.
- Orphans should be flagged for demotion to prose after a grace period rather
  than silently accumulating.

#### Merge rule

- Merge two entities only when at least one is true:
  - they share a confirmed primary external id
  - they are confirmed synonyms and do not carry diverging claims
- If either entity has claims that could not simultaneously hold for both
  referents, do not merge.

#### Split rule

- Split an entity when a claim attached to it could not simultaneously be true
  of all referents currently collapsed into that entity.
- The gene/protein collision is the canonical example:
  - if one entity is carrying both expression claims and protein-activity
    claims, it should be retroactively split.

### 5. Naming Rules

Naming still matters, but it should be framed as one layer of the broader
policy.

#### General rules

- Use semantic ids, not document-title labels.
- Prefer existing ontology-backed or catalog-backed kinds before creating local
  `concept:*` terms.
- Use lowercase kebab-case for local concept / method / mechanism ids.
- Use singular ids for conceptually singular entities.
- Use plural only when the entity is inherently plural or denotes a stable
  collective class.
- Avoid parentheses and punctuation in ids when the kind already disambiguates.
- Use ASCII transliteration in ids.
- Preserve canonical typography and Unicode in `title`.

Examples:

- `concept:snorna` with title `snoRNA`
- `protein:TNF` vs `gene:TNF`
- `concept:h3k27me3` with title `H3K27me3`

#### Disambiguation rule

- Kind prefix is the primary disambiguator.
- The title should remain human-readable and, when needed, explicitly clarify
  ambiguous homonyms.
- For same-kind homonyms, the primary tie-breaker is the external identity
  layer, especially `primary_external_id`.

#### Alias rule

- Include stable alternate names and search-relevant forms.
- Include:
  - official acronym expansions
  - prior official symbols after authority rename
  - commonly used legacy symbols with clear provenance
- Do not include:
  - arbitrary author paraphrases
  - whole-sentence descriptions
  - unstable contextual shorthand

#### ID syntax rule

- Reserve `:` as the kind separator only.
- Do not allow additional colons in the local part.
- Use lowercase kebab-case for local concept-like ids unless the kind uses a
  canonical authority-backed symbol convention, such as `gene:EZH2`.
- Document reserved characters, maximum length, and normalization rules
  explicitly in the implementation follow-up so the regex lint is deterministic.

### 6. Biology-Specific Rules

Biology needs explicit curation rules beyond generic naming advice.

#### Gene vs protein

The same symbol often names both the gene and its protein product. The split is
still mandatory when the claim attaches to different biology.

Decision rule:

- use `gene:*` for expression, mutation, copy number, transcription, genomic
  alteration
- use `protein:*` for activity, inhibition, phosphorylation, localization,
  complex membership, catalytic function
- use `family:*` for family-level claims
- use a broader `concept:*` or `mechanism:*` only when the literature is
  intentionally conflating multiple layers and that conflation is itself what
  is being modeled

#### Species policy

Capitalization alone is not enough. Add an explicit species / taxon rule.

Recommended default:

- keep separate entities for distinct species-specific genes or proteins
- require a species / taxon field for biology entities that are organism-bound
- link orthologs explicitly rather than collapsing them into one entity

#### Family vs member

- `family:E2F` is not interchangeable with `gene:E2F1` or `protein:E2F1`
- family-level and member-level claims must stay separated

#### Complex vs subunit

- `protein:EZH2` is not the same as the complex containing EZH2
- prefer a shared `complex:*` kind over `concept:prc2-complex` once the model
  supports it cleanly
- use ComplexPortal or similar authority where available

#### Isoforms and PTMs

Default rule:

- one protein entity per canonical accession
- isoforms and PTM states are attributes or modifiers by default
- create separate entities only when the claim materially depends on the
  specific isoform or modified form

#### Pathways and processes

- distinguish pathway/process entities from interventions
- example:
  - `concept:mapk-signaling`
  - `drug:tazemetostat`

#### Histone marks and chromatin features

- allow explicit entities for widely used marks and chromatin features when
  they carry stable semantics
- example:
  - `concept:h3k27me3`

### 7. Lifecycle Policy

The policy should define how entities evolve over time.

#### Provisional entities

Allow provisional local entities when:

- they are semantically useful now
- they lack a good upstream home
- there is an expectation of later promotion, merge, or retirement
- or their authority mapping is unresolved even though the semantic identity is
  already clear enough to warrant temporary entity status

Recommended metadata:

- `provisional: true`
- `review_after`
- optional rationale / promotion target

Clarification:

- provisional status can mean either:
  - the concept is locally useful but not yet promotable into a shared model
  - the external authority mapping is unresolved and needs later completion
- these are different workflows and should not be conflated in tooling

#### Deprecation / rename

Add a minimal rename policy:

- old ids should not silently disappear
- use a `deprecated_ids` / `replaced_by` style field
- lint inbound refs to deprecated ids
- migrate authored refs on a planned cadence

This is not a broad compatibility layer; it is a controlled migration surface.

#### Promotion path

Recurring local concepts should have a documented path for promotion into shared
catalogs when they prove durable and reusable.

#### Fix-on-touch legacy policy

- New guidance applies immediately to new entities.
- Legacy entities are not bulk-rewritten by default.
- When a curator touches a legacy entity:
  - fix it immediately if the change is a safe rename, xref addition, or other
    low-risk conformance improvement
  - flag it for review instead of auto-fixing if the change would require a
    merge, split, or broader semantic reinterpretation

### 8. Governance

The design should say who is allowed to create what.

Recommended policy:

- local project entities can be created freely within project scope, but should
  follow linted rules
- recurring or cross-project local concepts should trigger review for promotion
  into shared catalogs
- promotion should require:
  - repeated reuse across projects or durable reuse within one project
  - stable semantics
  - acceptable authority mapping or justified internal-only identity

#### Scope field

Do not encode project scope into the canonical id by default.

Instead, add explicit scope metadata such as:

- `scope: project`
- `scope: shared`

Promotion can then change scope without forcing an id-format rewrite.

#### Cross-project consistency

Because cross-project sync already exists, scope and identity rules must work
across projects.

- shared entities with the same canonical id must resolve to the same thing
  across projects
- project-scoped entities with colliding canonical ids must be namespaced or
  collision-flagged at sync time
- add a cross-project collision lint for synced registries

### 9. Tooling And Linting

Without enforcement, this guidance will drift.

Add concrete lint targets:

- id regex per kind
- unknown-prefix rejection
- required external-id presence for configured kinds
- primary-external-id collision detection
- duplicate alias detection
- deprecated-id inbound ref detection
- orphan detection
- missing taxon on species-bound biology entities
- local concept creation without justification metadata when required
- cross-project canonical-id collision under sync
- same-authority duplicate mapping across entities
- unresolved relation endpoint disambiguation

Relation rule:

- once gene and protein entities are distinct, relations must reference
  explicitly typed endpoints
- relations written against bare symbols should fail lint or enter a
  disambiguation queue rather than silently attaching to the wrong entity

Tooling follow-up:

- `science-health` should apply these rules directly during triage
- skills should present entity-creation decision trees, not just naming
  suggestions
- legacy entities should be linted, but not auto-rewritten by default

### 10. Cookbook

The highest-leverage deliverable is a curator cookbook with filled examples for:

- gene
- protein
- family
- complex
- disease
- drug / chemical
- cell type
- phenotype
- pathway / process
- histone mark
- mechanism
- prose-only note

Each example should show:

- canonical id
- title
- primary external id
- xrefs
- aliases
- scope if not shared-by-default
- taxon if applicable
- lifecycle metadata if applicable
- when not to create the entity

Also include explicit negative examples such as:

- `concept:high-proliferation-rate`
- `concept:patient-responded-well`
- `concept:authors-argued-x`
- `concept:ezh2-inhibits-prc2`

## Non-Goals

- full ontology ingestion or resolver expansion
- backfilling every legacy entity in one pass
- solving global synonym unification across all ontologies
- introducing a broad compatibility alias layer
- forcing project scope into the canonical id format by default

## Success Metrics

The implementation follow-up should define concrete targets and report them via
lint or health output.

Suggested metrics:

- fraction of eligible biology entities with a primary external id
- primary-external-id collision count
- orphan count and trend
- deprecated-id inbound-ref count
- unresolved relation-endpoint disambiguation count
- cross-project canonical-id collision count

## Recommended Next Step

Turn this policy into a concrete implementation plan with at least three work
streams:

1. model/schema changes
2. lint / health enforcement
3. curator-facing cookbook and skill guidance

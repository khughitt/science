# Entity Creation Cookbook

Use this guide before creating a new entity or rewriting an unresolved reference.

## Core Rule

Create an entity only when it has stable semantic identity. If the phrase is just a document title, shorthand, temporary label, or quantitative state, keep it in prose instead.

## Decision Order

1. Check whether the thing already has a recommended shared kind and external authority.
2. Reuse an existing shared or project entity before creating a new one.
3. Prefer a typed domain entity over a local `concept:*`.
4. Prefer prose-only notes when the phrase does not name a stable thing.
5. Use `mechanism:*` only for structured explanatory units, not for catchy labels.

## Identity Rules

- Internal `canonical_id` is separate from external authority identifiers.
- Use exactly one `primary_external_id` when the entity kind requires one.
- Store additional authority mappings as typed `xrefs`.
- Keep project scope in metadata, not in the id:
  - `scope: project`
  - `scope: shared`
- Preserve canonical external ids without version suffixes. Keep versioned accessions only in provenance.

Example typed external ids:

```yaml
primary_external_id:
  source: HGNC
  id: "3527"
  curie: HGNC:3527
  provenance: manual
xrefs:
  - source: NCBIGene
    id: "2146"
    curie: NCBIGene:2146
    provenance: manual
```

## When To Create An Entity

Create an entity when at least one is true:

- it participates in multiple typed relations
- it appears in multiple documents with non-trivial claims
- it has a recommended external authority id
- it is needed by a query, dashboard, or downstream workflow

Otherwise keep it as prose-only.

## Worked Examples

### Gene

Use `gene:*` for mutation, copy-number, transcription, or expression claims.

```yaml
id: gene:EZH2
kind: gene
title: EZH2
scope: shared
taxon: NCBITaxon:9606
primary_external_id:
  source: HGNC
  id: "3527"
  curie: HGNC:3527
  provenance: manual
```

### Protein

Use `protein:*` for activity, inhibition, localization, phosphorylation, or complex-membership claims.

```yaml
id: protein:EZH2
kind: protein
title: EZH2
scope: shared
taxon: NCBITaxon:9606
primary_external_id:
  source: UniProt
  id: Q15910
  curie: UniProt:Q15910
  provenance: manual
```

### Family

Use `family:*` when the claim applies to the family as a class rather than a single member.

```yaml
id: family:E2F
kind: family
title: E2F family
scope: shared
```

### Complex

Use `complex:*` for real complexes, not `concept:*` labels like `concept:prc2-complex`.

```yaml
id: complex:PRC2
kind: complex
title: PRC2 complex
scope: shared
```

### Disease

Use `disease:*` for modeled disease entities.

```yaml
id: disease:multiple-myeloma
kind: disease
title: Multiple myeloma
scope: shared
primary_external_id:
  source: MONDO
  id: "0005147"
  curie: MONDO:0005147
  provenance: manual
```

### Drug

Use `drug:*` or `chemical:*` when the entity is a real intervention or compound.

```yaml
id: drug:lenalidomide
kind: drug
title: Lenalidomide
scope: shared
```

### Cell Type

Use `cell-type:*` for stable cell type entities, not for transient states. This is the default pattern for a reusable cell type.

```yaml
id: cell-type:plasma-cell
kind: cell_type
title: Plasma cell
scope: shared
primary_external_id:
  source: CL
  id: "0000786"
  curie: CL:0000786
  provenance: manual
```

### Phenotype

Use `phenotype:*` for modeled phenotype terms.

```yaml
id: phenotype:anemia
kind: phenotype
title: Anemia
scope: shared
```

### Pathway

Use `pathway:*` or a GO/Reactome-backed entity for stable pathways and processes.

```yaml
id: pathway:interferon-signaling
kind: pathway
title: Interferon signaling
scope: shared
```

### Histone mark

Use a stable concept or ontology-backed mark entity for a reusable histone mark.

```yaml
id: concept:h3k27me3
kind: concept
title: H3K27me3
scope: project
```

### Mechanism

Use `mechanism:*` only when the entity bundles typed participants and propositions into one explanatory unit.

```yaml
id: mechanism:phf19-prc2-ifn-silencing
kind: mechanism
title: PHF19/PRC2-mediated IFN silencing
scope: project
related:
  - protein:PHF19
  - complex:PRC2
  - pathway:interferon-signaling
  - proposition:ifn-silencing
```

### Prose-Only Note

Keep broad synthesis titles as prose-only notes when they are not stable semantic objects. A prose-only note is documentation, not a semantic entity.

- Good prose-only note:
  - `doc/background/chromosomal-alterations-and-3d-genome.md`
- Do not create:
  - `topic:chromosomal-3d-genome-continuum`

## What Not To Create

This section lists what not to create as standalone entities.

These should stay as prose, attributes, or relations instead of standalone entities:

- `concept:high-proliferation-rate`
- `concept:patient-responded-well`
- `concept:authors-argued-x`
- `concept:ezh2-inhibits-prc2`
- vague buckets like `topic:methodology`, `topic:background-synthesis`, or `topic:mechanism`

## Legacy Fix-On-Touch

When a curator lands on a non-conforming legacy entity:

- fix it on touch if the change is a safe rename or xref addition
- escalate for review if the change requires a split or merge
- do not preserve bad placeholder entities just because they already exist

## Local Concepts

Use local `concept:*` only when all of the following are true:

- no recommended shared kind fits
- the term is reused across multiple authored sources
- the meaning is stable enough to survive rename pressure
- the entity is still more useful than keeping the phrase in prose-only form

If a local concept starts recurring across projects, promote it into shared guidance or a domain catalog instead of duplicating project-local copies.

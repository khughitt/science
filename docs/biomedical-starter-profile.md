# Biomedical Starter Profile

This document describes the first curated `science-model/bio` profile: a practical biomedical layer that composes with `science-model/core` and any project-local `project_specific` extension.

## Purpose

Use `bio` when a project needs a reusable biomedical subset drawn from common sources such as Biolink, GO, MeSH, Disease Ontology, or related biology ontologies. The goal is not to mirror whole upstream ontologies. The goal is to provide a stable, useful default profile for bio projects.

## Composition Model

Every Science project composes knowledge layers in this order:

```text
core -> optional curated profiles (for example bio) -> project_specific
```

Example `science.yaml`:

```yaml
knowledge_profiles:
  curated: [bio]
  local: project_specific
```

`core` provides the shared Science-native entities and relations. `bio` adds curated biomedical semantics. `project_specific` captures anything local to a project that does not yet belong in `core` or `bio`.

## What Belongs In `bio`

Good candidates:

- frequently used biomedical entity kinds such as `gene`, `protein`, `pathway`, `protein-family`
- common relations that are stable across projects
- bridge mappings to upstream ontology terms that many projects will need

Bad candidates:

- one-off project concepts
- raw imports of large external ontologies
- temporary aliases needed only during a single project migration

## Recommended Upstream Sources

Model biomedical knowledge through canonical sources, not direct graph edits:

- typed markdown docs in `doc/` and `specs/`
- tasks in `tasks/*.md`
- project-local extensions in `knowledge/sources/project_specific/*.yaml`

`knowledge/graph.trig` is always generated from those sources.

## Useful Prefixes

| Prefix | URI | Typical Use |
|---|---|---|
| `skos:` | `http://www.w3.org/2004/02/skos/core#` | Labels, definitions, related/broader links |
| `cito:` | `http://purl.org/spar/cito/` | Evidence and citation typing |
| `prov:` | `http://www.w3.org/ns/prov#` | Provenance |
| `schema:` | `https://schema.org/` | Metadata |
| `biolink:` | `https://w3id.org/biolink/vocab/` | Curated biomedical typing |

## Suggested Biomedical Semantics

Start with a small bundle like:

| Kind | Example |
|---|---|
| `gene` | `NCBIGene:7157` |
| `protein` | `UniProtKB:P04637` |
| `protein-family` | Homeobox family |
| `pathway` | apoptosis signaling |

| Relation | Example |
|---|---|
| `encodes` | gene -> protein |
| `member_of_family` | protein -> protein-family |
| `participates_in` | protein -> pathway |

## Project-Specific Extensions

If a bio project needs local entities that do not belong in the curated profile yet, add them under `knowledge/sources/project_specific/`.

Example:

```yaml
entities:
  - canonical_id: topic:evaluation
    kind: topic
    title: Evaluation
    profile: project_specific
    source_path: knowledge/sources/project_specific/entities.yaml
```

If a local concept proves broadly reusable across projects, promote it later into `bio`.

## Build Workflow

After updating canonical sources:

```bash
science-tool graph audit --project-root . --format json
science-tool graph build --project-root .
science-tool graph validate --format json
```

The graph should be clean before you consider the profile integration complete.

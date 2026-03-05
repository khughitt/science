# Graph Enrichment Design

**Date:** 2026-03-05
**Context:** Comparison of hand-curated vs CLI-assisted knowledge graphs revealed significant gaps in per-entity richness, ontology expressiveness, and entity type coverage. This design addresses those gaps.

## Problem

The CLI produces skeleton entities (label + type only). Real research knowledge graphs need 5-8 properties per entity (architecture, parameters, status, notes, provenance links). Additionally, the tool uses custom predicates where established standards exist, reducing interoperability.

## Ontology Changes

### Adopt CiTO (Citation Typing Ontology)

Add `cito:` prefix (`http://purl.org/spar/cito/`). Migrate evidence predicates:

| Old (custom) | New (standard) | Use case |
|---|---|---|
| `sci:supports` | `cito:supports` | Evidence for a claim |
| `sci:refutes` | `cito:disputes` | Evidence against a claim |
| `sci:addresses` | `cito:discusses` | Paper addresses topic |
| (none) | `cito:extends` | Building on prior work |
| (none) | `cito:usesMethodIn` | Methodological borrowing |
| (none) | `cito:citesAsDataSource` | Dataset provenance |

### Replace `sci:relatedTo` with `skos:related`

For generic concept-concept associations. Keep specific `sci:` predicates: `sci:evaluates`, `sci:hasModality`, `sci:detectedBy`, `sci:storedIn`.

### Add Dublin Core Terms

Add `dcterms:` prefix (`http://purl.org/dc/terms/`). Use `dcterms:identifier` and `dcterms:description` where appropriate.

### Keep custom namespaces for unique predicates

**`sci:` (research project management):**
- `sci:epistemicStatus` -- `established`, `hypothesized`, `disputed`, `retracted`
- `sci:confidence` -- 0.0-1.0 scoring
- `sci:projectStatus` -- `selected-primary`, `deferred`, `active`, `candidate`, `speculative`
- `sci:maturity` -- for questions: `open`, `partially-resolved`, `resolved`
- `sci:hasModality`, `sci:evaluates`, `sci:detectedBy`, `sci:storedIn`
- Domain properties: `sci:hasArchitecture`, `sci:hasTokenization`, `sci:hasParameters`, `sci:hasEmbeddingDim`

**`scic:` (causal modeling):**
- `scic:causes`, `scic:confounds`, `scic:Variable`, `scic:isObserved`

### Backward compatibility

Old `sci:supports` etc. CURIEs still resolve in `_resolve_term`. We stop emitting them in new commands. Existing graphs remain valid.

## CLI Enhancements

### `add concept` -- new flags

| Flag | Predicate | Layer |
|---|---|---|
| `--note TEXT` | `skos:note` | knowledge |
| `--definition TEXT` | `skos:definition` | knowledge |
| `--property KEY VALUE` (repeatable) | `sci:KEY` or resolved CURIE | knowledge |
| `--status STATUS` | `sci:projectStatus` | knowledge |
| `--source PATH` | `prov:wasDerivedFrom` | provenance |

`--property` behavior: bare KEY (e.g. `hasArchitecture`) defaults to `sci:hasArchitecture`. KEY with colon (e.g. `schema:url`) resolves as full CURIE.

### `add hypothesis` -- new flag

| Flag | Predicate | Layer |
|---|---|---|
| `--status STATUS` | `sci:projectStatus` | knowledge |

### New command: `add question`

```
science-tool graph add question <QUESTION_ID> --text "<text>" --source <ref>
    [--status open|partially-resolved|resolved]
    [--maturity open|partially-resolved|resolved]
    [--related-hypothesis <HYP_ID>]  # repeatable
```

Emits:
- `sci:Question` type in knowledge layer
- `schema:text` with question text
- `schema:identifier` with question ID
- `prov:wasDerivedFrom` in provenance layer
- `sci:maturity` literal (default `open`)
- `skos:related` edges to each related hypothesis

### New command: `graph predicates`

Lists all supported predicates with namespace, description, and typical graph layer. Supports `--format table|json`.

## Skill/Prompt Updates

### `knowledge-graph/SKILL.md`

- Update relation table with CiTO, SKOS, and sci: predicates
- Add `Question` to entity types table with `add question` usage
- Add "Entity Properties" section showing `--note`, `--property`, `--status` usage
- Add "Preferred Predicates" guide: when to use `cito:` vs `skos:` vs `sci:`

### `commands/create-graph.md`

- Step 3: Add entity richness guidance -- capture properties, notes, status
- New Step 3.5: Open question extraction from prose
- Step 4: Expand entity checklist with property/note/status fields
- Add guidance on creating `knowledge/deferred-entities.md` for peripheral entities

### `commands/update-graph.md`

No structural changes -- the workflow benefits from richer CLI commands without prompt changes.

## Testing

Each feature gets tests following existing patterns in `test_graph_cli.py`:

- `add concept --note` writes `skos:note` triple
- `add concept --property` with bare key and CURIE key
- `add concept --status` writes `sci:projectStatus`
- `add concept --source` writes `prov:wasDerivedFrom` in provenance layer
- `add concept --definition` writes `skos:definition`
- `add question` creates entity with type, provenance, maturity, hypothesis links
- `add question` without optional flags uses defaults
- `graph predicates` outputs table and JSON formats
- CiTO and dcterms prefixes resolve correctly in `_resolve_term`
